-- Universal work queue: one claimable ledger for pre-prepared runs
-- (axiom-encode#1509). Git inventories stay the PR-gated admission
-- record; this schema carries the OPERATIONAL state no repo should:
-- claims, leases, attempts, dispositions, live-adjustable priorities.
--
-- Purely additive — a new `ops` schema; nothing here touches corpus.*
-- or encodings.*. Rollback is `drop schema ops cascade`.
--
-- Access model mirrors encodings.rulespec_files: only service_role
-- reads/writes. Agents never talk to the database — they call the
-- axiom-api claim/disposition endpoints, which hold the key and
-- enforce leases and budgets.

create schema ops;

-- One row per admitted inventory. `source` pins the git provenance of
-- the admission (repo@sha:path), so every operational row traces back
-- to a reviewed artifact. Priorities are operational state: changing
-- them is an UPDATE, effective on the next claim, no re-admission.
create table ops.work_queues (
  queue_id    text primary key,
  status      text not null default 'paused'
              check (status in ('paused', 'active', 'retired')),
  priority    integer not null default 100,
  source      text not null,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- One row per pre-prepared run. `payload` is the self-contained run
-- manifest (pinned corpus/rulespec/engine SHAs, exact command or
-- contract, acceptance criteria) — a claimant needs zero context
-- beyond this row. `depends_on` orders items; `failure_fingerprint`
-- plus `attempts` feed the dead-letter rule (repeat-identical
-- failures flip status to 'blocked' instead of burning retries).
create table ops.work_items (
  id                  text primary key,
  queue_id            text not null references ops.work_queues (queue_id),
  kind                text not null,
  payload             jsonb not null,
  priority            integer not null default 100,
  depends_on          text[] not null default '{}',
  budget_class        text,
  status              text not null default 'pending'
                      check (status in
                        ('pending', 'leased', 'completed', 'failed', 'blocked')),
  attempts            integer not null default 0,
  failure_fingerprint text,
  failure_detail      text,
  claimed_by          text,
  lease_expires_at    timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint work_items_leased_expiry_required
    check (status <> 'leased' or lease_expires_at is not null)
);

-- The claim path scans (status, queue, priority); keep it index-shaped.
create index work_items_claim_order
  on ops.work_items (status, priority, id)
  where status = 'pending';
create index work_items_queue on ops.work_items (queue_id, status);
create index work_items_lease_expiry
  on ops.work_items (lease_expires_at)
  where status = 'leased';

-- Priorities are cheap to change and painful to reconstruct — every
-- reordering leaves a row so /ops can answer "why did the fleet
-- switch to X on Tuesday?".
create table ops.priority_events (
  id            bigint generated always as identity primary key,
  queue_id      text,
  item_id       text,
  actor         text not null,
  from_priority integer,
  to_priority   integer,
  reason        text,
  at            timestamptz not null default now()
);

-- Atomic claim: expire stale leases, then hand exactly one eligible
-- item to the caller. FOR UPDATE SKIP LOCKED is the whole trick —
-- concurrent agents can hammer this and no item is ever double-leased.
-- Eligibility: pending item, active queue, kind matches the caller's
-- capabilities (null = any), every dependency exists and is completed. Ordering:
-- queue priority, then item priority, then id (stable).
create function ops.claim_work(
  p_agent         text,
  p_kinds         text[] default null,
  p_lease_seconds integer default 900
) returns setof ops.work_items
language plpgsql
as $$
declare
  v_id text;
begin
  if p_lease_seconds is null or p_lease_seconds <= 0 then
    raise exception 'lease duration must be positive'
      using errcode = '22023';
  end if;

  -- A locked expired lease must not stall claims for unrelated work.
  update ops.work_items
     set status = 'pending',
         claimed_by = null,
         lease_expires_at = null,
         updated_at = now()
   where id in (
     select expired.id
       from ops.work_items expired
      where expired.status = 'leased'
        and expired.lease_expires_at < now()
        for update skip locked
   );

  select i.id
    into v_id
    from ops.work_items i
    join ops.work_queues q on q.queue_id = i.queue_id
   where i.status = 'pending'
     and q.status = 'active'
     and (p_kinds is null or i.kind = any (p_kinds))
     and not exists (
       select 1
         from unnest(i.depends_on) as dep(id)
         left join ops.work_items di on di.id = dep.id
        -- Missing IDs (including null array elements) are unsatisfied,
        -- just like dependencies that exist but have not completed.
        where di.status is distinct from 'completed'
     )
   order by q.priority, i.priority, i.id
     for update of i skip locked
   limit 1;

  if v_id is null then
    return;
  end if;

  return query
  update ops.work_items
     set status = 'leased',
         claimed_by = p_agent,
         attempts = attempts + 1,
         lease_expires_at = now() + make_interval(secs => p_lease_seconds),
         updated_at = now()
   where id = v_id
   returning *;
end;
$$;

-- Same posture as encodings.rulespec_files: the migration admin owns
-- the schema; service_role gets explicit grants; no anon/authenticated
-- access — the public surface is axiom-api, never the tables.
grant usage on schema ops to service_role;
grant select, insert, update, delete on all tables in schema ops to service_role;
grant usage, select on all sequences in schema ops to service_role;
revoke execute on function ops.claim_work(text, text[], integer) from public;
grant execute on function ops.claim_work(text, text[], integer) to service_role;

notify pgrst, 'reload schema';
