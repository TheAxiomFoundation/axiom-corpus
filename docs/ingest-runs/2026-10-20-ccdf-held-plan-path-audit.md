# CCDF held plan-path audit (2026-10-20)

Audit and queue annotation only. Nothing was fetched, ingested or extracted; no
scope was created; `data/corpus` was not written by this run.

## Why

Two CCDF runs in one wave did the same work twice on 2026-10-20. Missouri's Initial
Plan was extracted and the whole scope was then withdrawn, because the uniqueness
check found all 42 citation paths already held by
`us-mo/policy/2026-10-12-w7-state-benefits-policy-mo`. Maryland's plan text turned
out to be held the same way, under
`us-md/policy/2026-10-12-w7-state-benefits-policy-md`. Both are recorded in
`docs/ingest-runs/2026-10-20-w8-ccdf-index-repair.md`. Nothing in
`manifests/ccdf-agent-queue.yaml` told either run beforehand which jurisdictions'
plan text the corpus already holds, so the cost was paid twice and could be paid
again.

## Reconciliation with the pushed CCDF branch

`discovery/ingest-w8-ccdf-index` (commit b0de54c70, pushed 2026-10-20) repairs the
relocated ACF index across 112 CCDF manifests and the queue, and adds the Indiana
plan scope. Its parent is exactly the commit this audit branch was cut from, so
this branch was fast-forwarded onto it and the audit is a single commit on top. No
line of that commit is reverted or rewritten: the diff of this commit against it is
62 added lines and no removed line. Where that branch had already recorded the
knowledge — the `ccdf_plan_text_held_elsewhere` family rows it added for us-md and
us-mo, each carrying `held_in_scope` — this audit reuses that field name and that
exact value instead of introducing a second convention.

## Method, and why a sweep of `data/corpus` is not the answer

The family root is `<jurisdiction>/policy/acf/ccdf-plan/<plan-version>`, confirmed
against held scopes (for example
`us-mo/policy/acf/ccdf-plan/fy2025-2027`) rather than assumed. A sweep of every
provisions JSONL under `data/corpus/provisions` for any `citation_path` containing
"ccdf" returns 2,928 rows in 30 distinct path shapes; the only shapes under an `acf`
agency segment are `policy/acf/ccdf-plan` (the plan family),
`policy/acf/tanf-plan`, `policy/acf/liheap-plan`, `guidance/acf/ocs` and
`guidance/acf/occ`. Searching instead by **label** — every row whose
`citation_label` names a CCDF plan or an ACF-118 — finds exactly one row outside the
family root:

* `us/guidance/acf/occ/approved-ccdf-plans-fy-2025-2027` ("FY 2025-2027
  State/Territory CCDF Plans"), in `us/guidance/2026-10-12-w7-federal-guidance`.
  That is the ACF index page itself, not a jurisdiction's plan text. It is reported
  by the check and is not counted as plan text.

That sweep alone would have given the wrong answer, and this is the finding that
matters most. `.axiom/corpus-locks/` exists, so the corpus holds every locked scope
while `data/corpus` holds only what has been fetched. A fetched-bytes sweep saw
plan-root paths in 5 jurisdictions at the start of this audit and in 7 an hour
later, because another process was fetching into the working tree during the run.
The lock set did not move: 112 CCDF plan-family scopes across 52 jurisdictions, the
same set before and after. **The authoritative holdings below come from
`.axiom/corpus-locks/` plus the `coverage` block of each scope's signed ingest
manifest in `.axiom/ingest-manifests/`, both tracked in git.** Fetched provisions
are used only to corroborate and to read exact citation paths.

Path counts marked `manifest` are `coverage.provision_count` of the signed ingest
manifest; counts marked `sweep` are the exact number of distinct citation paths
under the family root read from the fetched provisions JSONL, with the plan-version
segment named.

## Per-jurisdiction holdings

Every scope below is locked and signed unless the cell says otherwise. The three
columns are the three sub-families under the one family root, so a plan collides
only with a plan.

| jurisdiction | plan-text scope(s) (paths) | amendments scope (paths) | appendix scope (paths) |
| --- | --- | --- | --- |
| us-al | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (16, manifest) |
| us-ak | none | none | `2026-09-13-ccdf-state-plan-appendices` (21, sweep, fy2025-2027-appendix-1) |
| us-as | none | none | none |
| us-az | none | none | `2026-09-13-ccdf-state-plan-appendices` (20, manifest) |
| us-ar | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (5, manifest) |
| us-ca | `2026-09-10-ccdf-plan-fy2025-2027` (42, sweep, fy2025-2027) | `2026-09-13-ccdf-state-plan-amendments` (42, sweep, fy2025-2027-amendment-1) | `2026-09-13-ccdf-state-plan-appendices` (31, sweep, fy2025-2027-appendix-1) |
| us-co | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (9, manifest) |
| us-ct | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (8, manifest) |
| us-de | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (21, manifest) |
| us-dc | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (4, manifest) | `2026-09-13-ccdf-state-plan-appendices` (10, manifest) |
| us-fl | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (7, manifest) |
| us-ga | `2026-09-13-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (7, manifest) |
| us-gu | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | none |
| us-hi | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (17, manifest) |
| us-id | `2026-09-10-ccdf-plan-fy2025-2027` (42, sweep, fy2025-2027) | none | `2026-09-13-ccdf-state-plan-appendices` (17, sweep, fy2025-2027-appendix-1) |
| us-il | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest)<br>`2026-10-12-w7-state-benefits-policy-il` (42, sweep, fy2025-2027-amendment-2) | none | `2026-09-13-ccdf-state-plan-appendices` (22, manifest) |
| us-in | `2026-10-20-w8-ccdf-plan-fy2025-2027` (42, sweep, fy2025-2027) **unlocked, unsigned** | none | `2026-09-13-ccdf-state-plan-appendices` (17, manifest) |
| us-ia | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (19, manifest) |
| us-ks | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (20, manifest) |
| us-ky | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (13, manifest) |
| us-la | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (5, manifest) |
| us-me | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (126, manifest) | `2026-09-13-ccdf-state-plan-appendices` (7, manifest) |
| us-md | `2026-10-12-w7-state-benefits-policy-md` (42, sweep, fy2025-2027) | none | `2026-09-13-ccdf-state-plan-appendices` (16, manifest) |
| us-ma | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (84, manifest) | `2026-09-13-ccdf-state-plan-appendices` (18, manifest) |
| us-mi | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (23, manifest) |
| us-mn | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (22, manifest) |
| us-ms | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (25, manifest) |
| us-mo | `2026-10-12-w7-state-benefits-policy-mo` (42, sweep, fy2025-2027) | none | `2026-09-13-ccdf-state-plan-appendices` (13, manifest) |
| us-mt | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (8, manifest) |
| us-ne | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (25, manifest) |
| us-nv | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (15, manifest) |
| us-nh | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (18, manifest) |
| us-nj | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (12, manifest) |
| us-nm | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (2, manifest) |
| us-ny | none | none | `2026-09-13-ccdf-state-plan-appendices` (5, manifest) |
| us-nc | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (42, manifest) | `2026-09-13-ccdf-state-plan-appendices` (11, manifest) |
| us-nd | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (84, manifest) | `2026-09-13-ccdf-state-plan-appendices` (17, manifest) |
| us-mp | none | none | none |
| us-oh | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (84, manifest) | `2026-09-13-ccdf-state-plan-appendices` (9, manifest) |
| us-ok | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (19, manifest) |
| us-or | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (42, manifest) | `2026-09-13-ccdf-state-plan-appendices` (8, manifest) |
| us-pa | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (8, manifest) |
| us-pr | none | none | none |
| us-ri | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (7, manifest) |
| us-sc | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (11, manifest) |
| us-sd | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (126, manifest) | `2026-09-13-ccdf-state-plan-appendices` (6, manifest) |
| us-tn | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (19, manifest) |
| us-tx | `2026-09-13-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (5, manifest) |
| us-ut | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (8, manifest) |
| us-vt | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (2, manifest) | `2026-09-13-ccdf-state-plan-appendices` (21, manifest) |
| us-vi | none | none | none |
| us-va | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (9, manifest) |
| us-wa | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | `2026-09-13-ccdf-state-plan-amendments` (42, manifest) | `2026-09-13-ccdf-state-plan-appendices` (23, manifest) |
| us-wv | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (30, manifest) |
| us-wi | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (22, manifest) |
| us-wy | `2026-09-10-ccdf-plan-fy2025-2027` (42, manifest) | none | `2026-09-13-ccdf-state-plan-appendices` (14, manifest) |

Totals from the lock set: **49 of the 56 jurisdictions already hold CCDF plan
text**, 11 also hold a separately posted amendments scope, and 51 hold an appendix
scope. Seven hold no plan text: us-ak, us-as, us-az, us-mp, us-ny, us-pr and us-vi.
Four of those hold nothing at all under the family root: us-as, us-mp, us-pr,
us-vi. Those seven rows are the only ones where fetching a plan is still real work.

## Overlaps

**No citation path is held by more than one scope.** Across all ten fetched scopes
that hold family-root paths, the count of paths owned by two or more scopes is zero.
Every overlap below is an overlap of jurisdiction and document, not of path, and the
bodies therefore have no path at which to disagree.

1. **us-ca, three scopes, one jurisdiction.** `2026-09-10-ccdf-plan-fy2025-2027`
   (Initial Plan, root `fy2025-2027`), `2026-09-13-ccdf-state-plan-amendments`
   (Amendment 1, root `fy2025-2027-amendment-1`) and
   `2026-09-13-ccdf-state-plan-appendices` (root `fy2025-2027-appendix-1`). The
   initial plan and the amendment carry **the same 42 relative leaf names** under
   different roots. Comparing body sha256 leaf by leaf: 20 of the 42 bodies are
   byte-identical and 22 differ. The amendment is a real revision of the plan, and
   putting it under its own root is what kept it from colliding.
2. **us-il, two plan-family scopes.** The locked, signed
   `us-il/policy/2026-09-10-ccdf-plan-fy2025-2027` (42 provisions, Initial Plan) and
   `us-il/policy/2026-10-12-w7-state-benefits-policy-il`, which holds Amendment 2
   (approved 2026-07-01) at `fy2025-2027-amendment-2`. Distinct roots, no collision.
   The Illinois queue row described only the Initial Plan and said nothing about
   Amendment 2 being held.
3. **us-id**, plan (42) and appendix (17), both fetched. Same shape as us-ca minus
   the amendment.
4. **The case that caused today's rework.** us-md (Amendment 1), us-mo (Amendment 2)
   and us-in (Amendment 3) each hold an amendment at the **bare** `fy2025-2027`
   root, while us-ca (Amendment 1) and us-il (Amendment 2) hold amendments at
   `fy2025-2027-amendment-N`. A run that extracts the Initial Plan for Maryland,
   Missouri or Indiana writes the bare root and therefore collides on all 42 paths.
   That is exactly what happened to Missouri's Initial Plan: the collision was not a
   duplicate document, it was two different documents competing for one path.

## What was annotated

`manifests/ccdf-agent-queue.yaml`, 62 added lines, no line changed or removed. No
`queue_status` was touched and `status_counts` is unchanged (agent_ready 49,
blocked_primary_source 4, needs_review 7, as `discovery/ingest-w8-ccdf-index` left
it). The field is `held_in_scope`, the name and the
`<jurisdiction>/<document_class>/<version>` form that branch already used on the two
`ccdf_plan_text_held_elsewhere` rows, placed as it placed them: after the target
scope and before `taken_count`.

* **49 top-level plan rows** got `held_in_scope`, one per jurisdiction that holds
  plan text — including the us-md and us-mo rows, whose pointer repeats the value
  the w8 branch put on their `ccdf_plan_text_held_elsewhere` family rows. A run
  keys on the top-level row first, so the fact has to be readable there.
* **us-il** got `held_in_scopes` with both of its holding scopes. The plural follows
  the queue's own singular/plural pairs (`target_scope`/`target_scopes`,
  `target_manifest`/`target_manifests`); it is not a new convention.
* **11 `ccdf_plan_amendments` family rows** (us-ca, us-dc, us-ma, us-me, us-nc,
  us-nd, us-oh, us-or, us-sd, us-vt, us-wa) got `held_in_scope` naming their
  `2026-09-13-ccdf-state-plan-amendments` scope.
* The second `us-in` top-level row was **not** annotated. It is the CCDF policy
  manual row (`target_scope.version: 2026-09-10-ccdf-in-policy-manual`), not a plan
  row; the queue holds two us-in rows, which is the same trap the w8 run hit with
  `--only`.
* `ccdf_plan_appendix_1` rows were **not** annotated (judgment 8).

## The reusable check

`scripts/check_ccdf_plan_held.py`. Read-only: it opens files for reading, fetches
nothing and writes nothing, not even a report. It reads the lock set first, then the
signed ingest manifests, then the queue's `held_in_scope`/`held_in_scopes` pointers,
then fetched provisions when they are there, and it reports a variant-spelling path
separately instead of counting it as plan text.

```bash
# One jurisdiction, before fetching its plan.
uv run python scripts/check_ccdf_plan_held.py us-mo

# As a pre-fetch gate: exits 1 when the plan text is already held.
uv run python scripts/check_ccdf_plan_held.py us-mo --exit-code

# Every jurisdiction the queue lists, as JSON.
uv run python scripts/check_ccdf_plan_held.py --json

# From outside the repo, or against a working tree with corpus bytes fetched.
uv run python scripts/check_ccdf_plan_held.py us-in --repo-root /path/to/axiom-corpus
```

It prints, per scope, the sub-family, whether the scope is locked, signed and
fetched, and the path count with its source. `us-in` reports `UNLOCKED, UNSIGNED`,
which is the honest answer (judgment 5).

## Reviewer judgments

1. **The lock set is the authority, not `data/corpus`.** A fetched-bytes sweep
   answers "which scopes have I fetched", not "what does the corpus hold". During
   this audit the fetched set grew from 5 to 7 plan-holding jurisdictions while the
   lock set stayed at 112 scopes, so another process was writing `data/corpus` in
   the shared working tree. The five jurisdictions the earlier quick scan reported
   were an artifact of partial fetch; the real number is 49. Both the audit table
   and the check are built on the lock set and the signed ingest manifests for this
   reason.
2. **The amendment-path convention is inconsistent, and that inconsistency is the
   defect that cost today's rework.** Five jurisdictions hold an amendment:
   us-ca and us-il under `fy2025-2027-amendment-N`, us-md, us-mo and us-in under the
   bare `fy2025-2027`. Needs a human decision: either every amendment takes its own
   `-amendment-N` root, or the bare root always means "the current approved
   version" and an initial plan that arrives later is the one that must move. Until
   one rule is written down, the next MD/MO/IN-shaped run collides again.
3. **The us-md and us-mo top-level rows still misstate their target.** Both name
   `target_scope.version: 2026-09-10-ccdf-plan-fy2025-2027`, and no such scope is
   locked, signed or fetched for either jurisdiction. The rows stay `needs_review`,
   so a future run reads that target and extracts straight into the 42 paths the w7
   scope already holds. This audit records `held_in_scope` on both rows but did not
   repoint or withdraw `target_scope`, because that is a triage decision. Needs a
   human decision.
4. **The us-il row understated its holdings.** Its notes describe the Initial Plan
   only. Illinois also holds Amendment 2 under the w7 scope, and unlike the eleven
   jurisdictions with a `ccdf_plan_amendments` family row, it has no row for that
   document. `held_in_scopes` now records both scopes; whether Illinois should also
   get a `ccdf_plan_amendments` row is a schema decision left open.
5. **Indiana's holding is unlocked and unsigned.** The w8 run deliberately left
   `data/corpus` uncommitted, so `us-in/policy/2026-10-20-w8-ccdf-plan-fy2025-2027`
   has no lock file and no signed ingest manifest. On any other machine the corpus
   does not hold Indiana's plan, and the `held_in_scope` pointer on the us-in row is
   true only in this working tree. Needs a human decision: sign and lock the scope,
   or mark the pointer provisional.
6. **Indiana's row metadata does not follow the amendment convention of the other
   amendment holders.** The scope carries `plan_version: Amendment 3` but its
   `citation_label` is "Indiana CCDF Plan, FFY 2025-2027" with no amendment in it,
   and its `expression_date` is 2024-10-01, the plan-period start, where us-il,
   us-md and us-mo all use the approval date (us-in's approval date is 2026-07-01
   per the w8 run note). So Indiana's Amendment 3 is labelled and dated like an
   initial plan. Needs a human decision; this audit changed no `data/corpus` byte.
7. **Two scope versions spell the plan family differently.** us-ga and us-tx hold
   `2026-09-13-ccdf-plan-fy2025-2027`; the other 45 hold `2026-09-10-...`. A check
   keyed on the literal `2026-09-10-ccdf-plan-fy2025-2027` would report Georgia and
   Texas as not held. The check matches `ccdf-plan-fy\d{4}-\d{4}$` instead.
8. **Appendix rows were not annotated, by choice.** The appendix text sits under the
   same family root, so the same duplicated-work risk exists for 51 appendix scopes.
   It is a distinct document family with its own path root and its own queue rows
   that already carry `target_scope` and `taken_count`, and annotating them would
   have tripled the diff for a family no run has duplicated yet. The check covers
   all three sub-families, so the knowledge is available even where the queue field
   is not. A reviewer who wants the field on appendix rows should say so.
9. **No status triage was done.** `queue_status` and `status_counts` are untouched,
   including on the seven rows where this audit proves nothing is held and the four
   where nothing at all is held.
10. **One variant spelling exists and it is not plan text.**
    `us/guidance/acf/occ/approved-ccdf-plans-fy-2025-2027` is the ACF index page,
    held as federal guidance in `us/guidance/2026-10-12-w7-federal-guidance`. The
    check prints it as a variant and excludes it from the verdict, so no run mistakes
    the index for a plan.
11. **The seven unheld rows are the real work queue**: us-ak, us-az and us-ny hold
    appendix text but no plan text; us-as, us-mp, us-pr and us-vi hold nothing. All
    seven are already `blocked_primary_source` or `needs_review` for the reasons the
    w8 run re-probed, so this audit adds no new fetch target.

## Verification

* `uv run ruff check scripts/check_ccdf_plan_held.py` — clean.
* The annotated queue parses with `yaml.safe_load`: 60 top-level rows, 61
  `held_in_scope` fields (59 added plus the two the w8 branch added) and one
  `held_in_scopes`.
* `git diff` against `discovery/ingest-w8-ccdf-index` for the queue: 62 insertions,
  0 deletions.

## Controller corrections to the check, 2026-10-20

The agent that wrote this audit was stopped by a usage limit before it ran the check
against every jurisdiction. The controller ran it and fixed two defects in
`scripts/check_ccdf_plan_held.py`. Both mattered, and the second was the one the
check exists to prevent.

1. **Crash on an unclassified scope.** `_print_report` built its marker list as
   `[entry["subfamily"]]`, so a scope whose subfamily is `None` raised a `TypeError`
   inside `", ".join(marks)`. `us-mo` crashed after printing one line. The subfamily
   now falls back to the literal `unclassified` in the printed markers.

2. **False negative on a queue pointer, which is the Missouri and Maryland case.**
   A scope reached only through a `held_in_scope` pointer kept the subfamily that
   `_subfamily_of_version` returned, and a wave-named version such as
   `2026-10-12-w7-state-benefits-policy-mo` matches none of the three CCDF patterns,
   so it classified as `None`, dropped out of `plan_scopes`, and the check reported
   `us-mo: CCDF plan text NOT HELD`. That is precisely the jurisdiction whose held
   plan text caused a whole extracted scope to be withdrawn earlier the same day. A
   pointer exists because somebody recorded that the scope holds plan text, so it now
   answers for itself: an unclassifiable pointer classifies as `mixed`, which counts
   as plan text and raises the warning. `us-mo` and `us-md` now both report
   `HELD` with the collision warning.

**Remaining limit, and a correction to how it can be closed.** A scope that is
locked but neither fetched nor named by a queue pointer is still invisible to the
check when its version name carries no CCDF subfamily, because the lock sweep
deliberately skips an unclassified version to avoid listing every unrelated scope a
jurisdiction holds.

An earlier draft of this section said the gap could be closed by reading each signed
ingest manifest's citation paths. **That is wrong, and the controller checked it.**
Neither record holds citation paths for an unfetched scope: a lock file
(`.axiom/corpus-locks/...`) lists only artifact paths with their sha256 and size, and
a signed ingest manifest (`.axiom/ingest-manifests/...`) holds a coverage summary
(`complete`, `matched_count`, `provision_count`, `source_count`) and a `command` that
is only a pointer to the run note. An unfetched scope's paths are not available
locally, which is what "not fetched" means.

So the gap has two real closures, not that one. Either fetch the scope's bytes, or
record the holding in the queue, which is exactly what this audit does for 59 rows.
After this audit the residual gap therefore covers only a scope that is locked,
unfetched **and** recorded nowhere in the queue, which is a scope nobody has yet
written down. A `NOT HELD` verdict is evidence of absence for every jurisdiction whose
CCDF scopes are fetched or pointed at from the queue, and this audit's own
per-jurisdiction table remains the stronger record.
