# Backlog publish health — PROGRESS

Owner: Claude (Fable 5). Branch: `fix/backlog-publish-health` (from origin/main).
Tracking issue: axiom-corpus#257. Worktree: `_worktrees/corpus-pub-health`.

## Goal
Re-run backlog publish (workflow_dispatch, `--since a2a8eac83b6d`) to
Planned N / Published+Skipped = N / Failed 0. Verify 7 rulespec-be worklist
paths live in Supabase `current_provisions`. Staleness guard alarms on
never-published scopes (proven by negative test). Comment + close/update #257.

## Diagnosis of run 28877938237 (wide, 59 failed)
Three SQL error codes, each one failure class:

| Code  | Count | Meaning | Class |
| ----- | ----- | ------- | ----- |
| 22023 | 31 | `time zone "<slug>" not recognized` — version slug reaches a timestamp-typed column | 2a expression_date |
| 23503 | 17 | FK `parent_id not present in table "provisions"` — container/ancestor row missing | 2b container-parents |
| 23505 | 11 | duplicate key `rules_citation_path_unique` on citation_path — cross-version container/section collision | 1 idempotency |

- Class 1 (23505) paths: us/statute/26, us-md/regulation, us-wa/regulation,
  us-ca/statute/rtc/17041, us-ny/statute/TAX/601, us-dc/statute/4,
  us-al/statute/title-38, us-hi/statute/volume-01, us-hi/regulation/har/17/676,
  us-ut/regulation/admin-rules/r986/200, be-vlg/guidance/.../schedule-1.
- Full per-scope map: scratchpad/failure-map.txt.

## Guardrails (active)
- Row counts before/after EVERY load; us-ca/statute must stay ~185,590. Drop = STOP.
- No replace/delete-scope semantics. Upserts + explicit-version inserts only.
- Never alter captured provision text. Ingest metadata (dates/parents) only, via PR review.
- Foreground CI polling. Rate-limited → 90s retry. Spend-limit → write state, exit.
- No admin-merge, no split-verdict merges. Rebase before merge (main moving:
  4 UK parity lanes merging concurrently; --since range picks them up).

## Status log
- [x] Worktree from origin/main (37b925e3).
- [x] Pulled full failed logs, categorized all 59 by error code.
- [ ] Read publisher + supabase load + schema; pinpoint each root cause.
- [ ] Fix class 1 (publisher idempotency / conflict target).
- [ ] Repair class 2a + 2b scopes.
- [ ] Extend staleness guard + negative test.
- [ ] Re-run publish → Failed 0; verify BE worklist paths; row counts.
- [ ] PRs merged on green; comment/close #257.
