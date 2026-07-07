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

## Confirmed root causes
- **Class 1 (23505 ×11)**: `upsert_supabase_rows` uses `on_conflict=id` (supabase.py:1276)
  but the live table enforces `UNIQUE(citation_path)` (`rules_citation_path_unique`).
  Default publisher load uses `versioned_ids=True` → id=f(path,**version**); a
  citation_path reused under a new version gets a fresh id → no id-conflict → INSERT
  → citation_path constraint rejects. All 11 are newer-replaces-older (live=Apr/May,
  publish=Jul), verified against DB. `--preserve-existing-ids` (reuse existing row id
  per path; already implemented, publisher never passed it) resolves it.
- **Class 2a (22023 ×31)**: DATE columns `expression_date` and sometimes `source_as_of`
  hold the full version slug `YYYY-MM-DD-<slug>` not `YYYY-MM-DD`; PG parses trailing
  text as a timezone. 33 files / 6010 records. Correct value = version[:10] (matches
  successful `cadastral`: expr_date `2026-07-03`).
- **Class 2b (23503 ×17)**: 26 instrument-level container parents (loi/arrete/
  ordonnance/decret + `us/statute/42/1396a`) referenced by child articles but defined
  nowhere (files or DB). Ingest emitted L2 articles without their L1 root container.
  Includes `be/statute/loi/1978/07/03/1978070303` — parent of ALL 6 employment-law
  worklist articles (in be/statute/2026-07-05-be-birth-leave).

## Fix plan
1. Loader (corpus/supabase.py): (a) coerce DATE cols to valid date/ null + warn +
   stash original; (b) synthesize missing ancestor container rows; (c) opt-in
   version-aware superseded-skip. New CLI flags; default-off for other callers.
2. Publisher (publish_corpus.py): load with --preserve-existing-ids
   --synthesize-missing-parents --skip-superseded; SKIP(superseded) reporting.
3. Data repair: de-slug expression_date/source_as_of in 33 files (version[:10]).
4. Staleness guard: alarm on never-published (committed-but-never-loaded) scopes +
   negative fixture test.

## Staleness-guard hole (confirmed empirically)
`--since 025f5d98` (a 2026-07-06 commit) hard-excludes scopes committed before it;
the BE scopes are 7/3–7/5, so `collect_git_scopes` never considered them and the
guard reported "current" while ~50 scopes sat never-published. Fix: split
never-published (no release_scopes row → alarms past grace, ignores `--since`)
from drift (inactive row → graced); run the CI job under the service key so
inactive rows are visible.

## Status log
- [x] Worktree from origin/main (37b925e3). Baseline counts captured (us-ca/statute=185590).
- [x] Categorized all 59; root-caused all 3 classes against live DB.
- [x] Loader fixes (date coercion, ancestor synthesis, superseded skip) + 12 unit tests.
- [x] Publisher fixes (preserve-ids + synthesize + skip-superseded; SKIP(superseded)).
- [x] Staleness guard never-published detection + negative test; CI uses service key.
- [x] Full fast suite green (3404 passed), ruff clean.
- [ ] Data repair (de-slug expression_date/source_as_of in 33 files).
- [ ] Re-run publish → Failed 0; verify 7 BE worklist paths; row counts stable.
- [ ] PRs merged on green; comment/close #257.
