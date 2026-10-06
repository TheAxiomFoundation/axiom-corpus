# Fix round 1 report: axiom-corpus PR #779 (layered serving)

**PR:** https://github.com/TheAxiomFoundation/axiom-corpus/pull/779. It is still a draft, as asked. The head moved from `52e49750` to `a32437da` in nine commits. `origin/main` had not moved, so nothing needed merging.

**CI on `a32437da` (run 37290832960): every check passes.** `gh pr checks` exits 0, and GitHub reports MERGEABLE.
- `test (3.14)`: the full corpus, 5,214 passed and 0 failed.
- `postgres`: PostgreSQL 15, 174 passed, including the MERGE test that is skipped locally.
- `Validate named release selectors`, `Citation-path grammar (A6)` and `Validate GitHub workflows`.

I updated the PR body: findings addressed with test names, what was deliberately not changed, new deployment steps, the production root-count check, and fresh plans at 1.52M rows.

## Per finding

**1. Membership writes desynchronized derived state.** Fixed in `6c1a9787`, `88b95bf4` and `db2c81c7`; all of the following are in `supabase/migrations/20260927110000_layered_release_serving.sql`, section 3.
- **Membership guard** (`guard_release_scope_membership`): every `release_scopes` UPDATE, DELETE and TRUNCATE is rejected. The foreign key already makes every row part of a signed release.
- **Insert check** (`guard_release_scope_membership_insert`): an inserted row must be one of its release object's signed scopes, with the signed layer. It runs once per statement over the transition table.
- **Restoring insert:** a signed scope that joins a pair its release already serves re-derives that pair in the same statement (`sync_layered_serving_membership`). This covers membership altered before the guard existed and restored by re-activation or by an insert.
- **Release objects** (`guard_release_object_immutable`): immutable except `created_at`, which the staging RPC repairs. An object with membership cannot be deleted, which closes the delete-and-reinsert-in-one-statement bypass the in-session review reproduced.
- **Isolation:** derivation and membership inserts run only under READ COMMITTED.
- **Activation still works:** first activation, reaffirm, re-activation of an earlier signed release, and v2/v3 objects. The atomic module passes in both modes.
- **The test near line 1709**, `test_activation_compares_the_stored_layer_with_the_signed_one`, now asserts the snapshot and a fresh-derivation check right after the write. It checks activation's layer comparison separately, with triggers off to simulate pre-guard data.
- **Tests that failed at `52e49750`** (mostly at `_assert_serving_is_consistent`, where the stored derived rows differed from a fresh derivation):
  - `test_writes_under_a_served_layered_release_are_rejected`, 18 cases. Twelve are membership, release-object and hide-the-object writes; the truncate and derived-table cases belong to finding 2.
  - `test_only_signed_scopes_join_membership`
  - `test_restoring_membership_lost_before_the_guard_rederives_the_pair[reactivation|insert]`
  - `test_derivation_and_membership_inserts_need_read_committed[REPEATABLE READ|SERIALIZABLE]`
  - `test_release_objects_change_only_their_publication_time`
  - `test_merge_into_membership_meets_the_same_guards`: needs PostgreSQL 15; it passed in CI.
- **Regression test:** `test_reactivating_an_earlier_signed_release_restores_its_serving`.

**2. Owner TRUNCATE left copied overrides served.**
- `guard_released_scope_rows_truncate` is a BEFORE TRUNCATE trigger on `provisions` and `navigation_nodes`. It rejects the truncate while the table holds a row of a signed release's scope: the statement-level twin of the released-row guard, layered or not. A table holding only unreleased staged rows can still be truncated.
- The derived tables accept only the derivation's writes (`guard_layered_serving_write`).
- Truncating the pointers runs `ANALYZE` on the emptied tables.
- **Tests:**
  - `test_writes_…[truncate navigation / truncate provisions / truncate both staged tables / truncate membership / truncate release objects / delete derived rows / truncate a derived table / add a derived row]`
  - `test_released_rows_and_membership_refuse_truncate_for_every_release`
  - `test_truncate_still_clears_rows_no_release_signs`
- **Test resets:** they now truncate with `session_replication_role = replica`. The CI and local test user is a superuser.

**3. Query client.** Fixed in `762e9297`, in `src/axiom_corpus/query/supabase.py`.
- **Unlayered pairs:** a pair whose serving release has no base scope sends `origin/main`'s exact `parent_id` request.
- **The base-scope check** reads `current_release_scopes?select=*`. Production's view has no `layer` column yet, and a `layer` filter returns HTTP 400; I checked that read-only.
- **Layered pairs:** the client reads every page of the navigation tree past the row cap before keeping one child per path. The id read-back is paged too: the property test found that it was truncated when the cap is under 100.
- **Tests in `tests/test_query_supabase.py`.** They use an emulated PostgREST over rows built by `iter_supabase_rows` and `build_navigation_nodes`.
  - These failed at `52e49750` with the reviewers' numbers:
    - `test_unlayered_children_are_the_parent_id_children_origin_main_returns`: HEAD returned `['fx/statute/1/1', 'fx/statute/1/2']`.
    - `test_unlayered_children_with_a_path_in_two_scopes_match_origin_main`
    - `test_unlayered_children_equal_origin_main_on_any_served_rows`: a Hypothesis differential against origin/main's code, with row caps 1–4.
    - `test_layered_children_page_through_the_row_cap`: 1,000 instead of 1,300.
    - `test_layered_children_page_before_keeping_one_per_path`: 500 instead of 1,000.
    - `test_layered_children_are_the_served_navigation_children`
  - **Also new:** `test_the_query_client_reads_children_through_the_serving_views` runs the real client against the PostgreSQL views as anon with a row cap of 2.
  - **Review differential:** the in-session reviewer ran 400 more examples against the real `origin/main` module, and the results were identical.

**4. Root-count baseline.** Committed in `a038b3bf`.
- **Decision:** served roots only. The migration comment, docs and test comment say so.
- **(a)** The no-base differential against #666 stays (`_assert_matches_reference`).
- **(b)** `test_root_counts_are_served_roots_not_every_stored_root` installs `20260910120000`'s function verbatim. The two agree when only served roots are stored, and differ by exactly the superseded and never-released roots otherwise. This test passes before and after, because the function did not change; it documents the difference rather than a fix.
- **(c)** The PR body states the change relative to the repository's history, and the read-only production check:
  - **Method:** on 2026-10-05 at 07:45 UTC, anon GETs only, with the script at `.pr3-scratch/root_counts_production_check.py`.
  - **Served counts match:** the RPC equals the served-root `count=exact` for all 469 pairs, 35,252 roots in total; `us/statute` is 373 and `us/regulation` 110.
  - **Unserved versions:** 41 pairs have 167 versions signed by one of the 31 activated releases that are no longer served. `20260910120000` would therefore count at least 167 more roots, so production is not running it.
  - **#666** is superseded.
  - **Not readable:** the production function body, because anon cannot read the catalog.

**5. Deployment locking.**
- **The file:**
  - It no longer derives a served base layer, and with no base served it only empties the derived tables.
  - `lock_timeout` is now 2 s.
  - Triggers use `CREATE OR REPLACE TRIGGER`, which takes SHARE ROW EXCLUSIVE instead of ACCESS EXCLUSIVE on `provisions` and `active_scope_pointer`.
- **Measured in `pg_locks`:** the file holds ACCESS EXCLUSIVE only on the four replaced views, `navigation_nodes` (its policies), `release_scopes` (the new column) and the two derived tables. Re-applying it to a 401,299-row copy with base scopes served took 8 ms.
- **`corpus.rederive_layered_serving()`** is the separate step. It takes only activation's locks: EXCLUSIVE on the pointers, plus row writes and ANALYZE on the derived tables. It refreshes counts only when the shadowed provisions change. It took 2.9 s at 401,299 rows.
- **Docs:** the Deployment section in `docs/named-release-publication.md` and in the PR covers retrying on the timeout, low traffic, and ANALYZE.
- **Tests:**
  - `test_applying_the_file_with_a_base_scope_served_leaves_the_derivation_to_its_own_step`: failed before, because the file re-derived.
  - `test_rederivation_takes_only_activation_locks_and_blocks_no_read`: anon reads succeed under a 1 s lock timeout while it is open, and a pointer write times out.
  - `test_migration_is_rerunnable_and_rederivation_reproduces_the_state`
  - `test_applying_the_file_with_no_base_scope_served_empties_the_derived_state`
  - `test_rederivation_refreshes_served_counts_when_the_shadowed_rows_change`

**6. ANALYZE.** `analyze_layered_serving()` runs after every derivation that changes the derived tables: activation through the pointer trigger, a restoring insert, the rederive step and a pointer truncate. An unlayered activation does not analyze. Test: `test_derivation_analyzes_the_layered_tables`, which failed before because `reltuples` stayed at -1.

**7. Validation warnings.** Committed in `0587d7ab` and `88b95bf4`.
- **New merge helpers:** `navigation.scope_parent_paths` and `merge_layered_parent_paths` merge each layered pair as serving does.
- **New warnings** from `release_quality._LayeredScopeParents`:
  - `layered_primary_root_unattached`: one per primary scope.
  - `layered_parent_cycle_broken`
- **Order:** both are reported after the scope checks, so a capped list still shows errors first.
- **Tests that failed before:**
  - `test_a_primary_root_under_no_served_ancestor_is_a_warning`
  - `test_a_new_title_warns_once_and_its_sections_attach_to_it`
  - `test_a_parent_cycle_between_the_layers_is_a_warning`
- **Also new:**
  - `test_primary_roots_the_merge_attaches_raise_no_warning`
  - `test_new_documents_of_a_flat_class_warn_once_per_scope_after_the_errors`
  - `test_releases_without_a_base_scope_get_no_layered_warning`
  - Hypothesis: forest property, and equality with `build_navigation_nodes` on well-formed pairs.
  - Both PostgreSQL property tests now assert that validation's predicted parents equal the parents SQL serves.

**8. Label parity (optional).**
- **Non-breaking spaces:** fixed. `navigation_heading_is_blank` uses `str.strip()`'s 29 whitespace characters.
- **Tests:**
  - `test_sql_heading_blankness_equals_python_strip` (Hypothesis, 300)
  - `test_a_blank_heading_follows_its_segment_as_navigation_py_does` (failed before)
  - The arbitrary-parents property now draws such headings, and found the mismatch on the old code.
- **`citation_label`: not fixed.** It is not stored in Supabase rows, so SQL cannot tell it from a segment fallback. This is documented as the only known label difference.

## Independent review this round

I ran two adversarial Opus reviewers synchronously, and the headless rules ruled out the Workflow tool. The SQL reviewer returned REQUEST_CHANGES. It reproduced:
- the hide-the-object bypass;
- a 6.0 s per-row guard cost for 761 scopes, now 14 ms;
- a REPEATABLE READ race;
- owner writes to the derived tables;
- a lock-documentation gap;
- the missing pointer-truncate ANALYZE.

The Python reviewer returned APPROVE, asking for the warning order, per-scope aggregation and the cycle wording. All of these are fixed in `88b95bf4`.

A verification pass then returned APPROVE. All six were closed, and a 60-seed random-statement invariant test passed. It raised three small points, fixed in `db2c81c7`: jsonb compared as text, a pointer lock in a direct refresh call, and the guard comment.

The reviewers' scratch work is in `.review-scratch/r2-sql`, `r2-py` and `r3-sql`. None of it is committed.

## Command output tails (at `db2c81c7`; `a32437da` changes only docs)

```text
$ uv run --extra dev ruff check . --extend-exclude .pr3-scratch --extend-exclude .review-scratch
All checks passed!          (plain `ruff check .` flags only untracked scratch files; `git ls-files` set passes)
$ uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports
Success: no issues found in 98 source files
$ uv run --extra dev towncrier check --compare-with origin/main
Found:
1. …/changelog.d/layered-release-serving.added.md
$ DATABASE_URL=postgresql://test@localhost:55432/axiom_corpus_test AXIOM_CORPUS_PARTIAL_TESTS=1 \
  uv run --extra dev python -m pytest -q <both PostgreSQL modules + query, layers, staging v4,
  streaming validation/edge cases/projection, bounded memory, navigation, atomic migration text>
410 passed, 2 skipped in 168.30s          (skips: the MERGE test needs PostgreSQL 15)
$ (same env) uv run --extra dev python -m pytest -q            # full suite, partial corpus
287 failed, 5125 passed, 37 skipped, 208 deselected, 38 warnings in 268.70s
  -> the 287 failures are exactly the 287 node IDs that failed at 52e49750 (missing corpus data); none new
CI run 37290832960 (a32437da): test (3.14) 5214 passed; postgres (PG15) 174 passed + 24 passed (ops queue)
```

## Not changed, and open items

- **Counts follow activation.** `current_provision_counts` follows activation, and rederive only when the shadowed rows change. A restoration by re-activating the serving release does not refresh counts, as before this PR.
- **Owner bypass.** An owner who sets the derivation setting, or turns triggers off, can still write the derived tables.
- **Extra request.** The client makes one more request per unlayered call (the base-scope check).
- **Unbounded paging loop.** The client's paging loop has no iteration bound; PostgREST honours `offset`.
- **Production isolation setting not checked.** Production's `default_transaction_isolation` was not checked. No repository code sets an isolation level, and the direct activation path uses psycopg2 autocommit (`corpus/supabase.py:1176-1180`).
- **Still owed by the dispatcher:**
  - review round 2;
  - taking the PR out of draft;
  - hand-applying `20260927110000` in PR 5;
  - the axiom.org switch to `current_navigation_nodes`.
- **Scratch evidence**, in the worktree under `.pr3-scratch/`, all untracked:
  - pre-fix logs: `fix-r1-prefix-*.log`;
  - plans: `fix-r1-plans-{ci,production}.md`;
  - lock measurement: `fix-r1-apply-locks.txt`;
  - production check: `root_counts_production_check.{py,json}`;
  - journal: `fix-r1-journal.md`.

The local PostgreSQL cluster in `.pg/` is stopped, and I dropped every scratch database. I updated the memory note `layered-serving-pr779.md` with the new deployment steps and guards.
