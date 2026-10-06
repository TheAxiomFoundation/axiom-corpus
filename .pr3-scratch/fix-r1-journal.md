# Fix round 1 journal (PR #779)

Start: head 52e497502, origin/main unchanged (no merge needed), 2026-10-05.
Baseline: 206 passed in 50.71s (both PG modules + query + layers + staging v4), local PG14 on :55432.

## Decisions
- Item 1: release_scopes guard. UPDATE/DELETE of signed membership rejected; TRUNCATE rejected while signed
  membership exists; INSERT only of a signed scope (with its signed layer) of the release object; AFTER INSERT
  statement trigger re-derives any pair whose serving release gained a row (repair of pre-guard tampering,
  and the reaffirm path of activation). Rationale for signed-scope INSERT check: DELETE is now impossible,
  so a stray INSERT would be permanent.
- Item 2: BEFORE TRUNCATE on provisions/navigation_nodes rejects while the table holds a row of a signed
  release's scope (statement-level twin of guard_released_scope_row_immutable). Test resets use
  session_replication_role = replica (superuser; CI user `test` is superuser).
- Item 5: file no longer derives when a base scope is served; corpus.rederive_layered_serving() is the
  separate step (EXCLUSIVE on active_scope_pointer only). lock_timeout 2s.
- Item 6: refresh ANALYZEs both derived tables when it changed any row; rederive ANALYZEs at end.
- Item 8: heading blankness uses Python's str.isspace set (29 chars); citation_label not stored -> documented.
- Headless: no Workflow tool (no notifications); synchronous Agent reviews only.

## Log
- [done] Items 1, 2, 5, 6, 8(NBSP) migration + tests: commit 6c1a97878. Pre-fix: 24 failed (log
  .pr3-scratch/fix-r1-prefix-db.log, incl. Hypothesis NBSP counterexample on arbitrary parents).
  Post-fix: both PG modules 159 passed in 47.43s.
- [done] Item 3 client: commit (see git log). Pre-fix 7 failed (.pr3-scratch/fix-r1-prefix-query.log;
  reproduces ['1/1','1/2'] vs ['1/1'], 500 vs 1000, 1000 vs 1300). Property test found id read-back
  also capped when max_rows < 100 -> paged with at_most. Production probe (anon, read-only):
  current_release_scopes 200 with 29 us/statute rows; select=layer -> 400 42703 (column absent).
- Item 4 production check (read-only, anon, GET; script .pr3-scratch/root_counts_production_check.py,
  output .json, at 2026-10-05T07:45:30Z): 469 pairs, rpc == served-root count (current_navigation_nodes
  count=exact, parent_path is null) for 469/469, total 35,252. 41 pairs have 167 versions signed by one of
  31 activated releases (scope_activation_history) that are not served now -> repo 20260910120000 would
  count >= served + 167 there. us/statute 373 (9 unserved released versions), us/regulation 110 (2).
  First RPC call returned a transient 500; retried.
- [done] Item 4 test commit a038b3bf6 (documents difference; passes before and after: function unchanged).
- [done] Item 7: navigation.scope_parent_paths / merge_layered_parent_paths; release_quality _LayeredScopeParents.
  Pre-fix (old release_quality.py): 3 warning tests failed (.pr3-scratch/fix-r1-prefix-validation.log).
  Non-PG modules touching validation/navigation: 130 failures identical before/after source changes (all
  missing corpus data, e.g. FileNotFoundError), lists in .pr3-scratch/fix-r1-nonpg-failed-{before,after}.txt.
- [done] docs/changelog aee202bd8; client-plan check committed. Scale CI 401k: derivation 6.9 s; production
  1.52M (load 11-17): derivation 7.3 s; plans in .pr3-scratch/fix-r1-plans-{ci,production}.md.
- Next: independent review (synchronous agents), then required checks, push, PR body, CI.
- In-session adversarial review (2 Opus agents, synchronous): SQL REQUEST_CHANGES (CTE hide-the-object
  bypass, 6 s guard cost, RR race, derived-table owner writes, lock doc, pointer-truncate ANALYZE);
  Python APPROVE (warning crowding/noise, cycle wording). All fixed in the "Close the guard bypasses"
  commit. Reviewer scratch: .review-scratch/r2-sql, r2-py. After fix: 40-seed stateful invariant pass,
  RR repro refused, 761-row insert 13.7 ms (was 6.0 s), reaffirm 4.8 ms (was 6.07 s). Apply-file locks:
  .pr3-scratch/fix-r1-apply-locks.txt (10 ms; AccessExclusive only on 4 views, navigation_nodes,
  release_scopes, derived tables); rederive 2.9 s at 401k.
- [done] Pushed a32437da; PR body updated (draft kept). CI run 37290832960 all pass (test 5214 passed;
  postgres PG15 174 passed incl. MERGE test; selectors pass). gh pr checks exit 0, MERGEABLE.
  Local cluster stopped; scratch DBs dropped; memory note updated. Report: .pr3-scratch/fix-r1-report.md
