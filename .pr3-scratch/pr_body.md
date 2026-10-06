PR 3 of the base-layer restore plan on #728 (layered serving). It lets a release serve a base scope underneath its primary scopes. Precedence follows the #728 ruling: for a citation path both layers carry, the primary row is served. It adds no selector, no signed manifest and no corpus data. #755 has merged, and this branch contains `origin/main` at `595a64c5`.

A previous lane started this work and its session ended on 2026-09-27. This branch keeps its signed-layer commit (`c96011df`) and its uncommitted migrations, committed unchanged as `42709a2a` and marked as work in progress. It then merges #755, which carries #769, and finishes the job. The serving design was rebuilt after measurement (see "Deviations").

## Problem

The May whole-Code (60,446 rows) and whole-eCFR (246,477 rows) artifacts are to be restored as an immutable base that every US successor reuses byte for byte. Newly encoded sections must take precedence over the base text without re-cutting it. That needs four things:

1. A signed scope layer.
2. Activation that installs the layer.
3. Serving views that pick the winner for each path.
4. Navigation, counts and child lookups that stay correct, and stay inside the 3 s anon statement timeout, once 307k more `us` rows are served.

## Change

### Signed scope layers (Python; mostly from the previous lane's `c96011df`)

- **One encoding per layer.** A selector scope or signed scope entry carries `"layer": "base"`, or no `layer` key for a primary scope. An explicit `"primary"` or any other value is rejected. A release may have at most one base scope per `(jurisdiction, document_class)`.
- **v3 stays byte-identical.** `build_unsigned_release_object` emits `release-object/v3` for every release without a base scope, byte for byte as before. `tests/fixtures/release_layers/pre_layer_v3_release.json` was generated at `f1916d73`, and the merged tree reproduces its content, selector digest and signed bytes. It emits `release-object/v4` only when a release has a base scope.
- **Verification.** A v4 object without a base scope fails verification, and so does a v2 or v3 object with a layer anywhere. `selector_sha256` is unchanged without a base scope (checked against all tracked selectors) and covers base layers otherwise.
- **Reuse.** A scope's signed dictionary includes its layer, so `_scope_publication_identity` keeps every historical primary scope reusable unchanged. A version cannot change layer on reuse.
- **Validation** (`release_quality.py`):
  - Citation paths stay unique within each layer.
  - A base/primary overlap is allowed only inside one pair.
  - This now sits inside #755's streaming `_release_citation_paths`, with one owner map per layer.
- **Lock-pinned base scopes.** A base scope whose artifacts are pinned by a committed corpus lock (#769) builds and signs v4 content through `_require_tracked_release_inputs`. New test, plus a test that a lock pinning other bytes is rejected.

### Registration RPC: `20260927100000_stage_signed_release_object_v4.sql`

- The file holds only `corpus.stage_corpus_release_object`.
- It accepts v4 and enforces the layer rules: exact `"base"`, at least one base scope, at most one per pair.
- It registers v2 and v3 exactly as `20260803175000` does. `tests/test_release_object_staging_v4_migration.py` undoes the three v4 edits and requires `20260803175000`'s function text back.
- `scripts/apply_release_object_staging_migration.py` now points at this file (`MIGRATION`, `REQUIRED_FRAGMENTS`). Before, every ordinary publication would have reinstalled a v3-only function.

### Layered serving: `20260927110000_layered_release_serving.sql`

This file is applied by hand; see Deployment.

- **Layer column.** `release_scopes.layer` (`primary` by default, so historical rows are primary), with a check constraint and a partial unique index for one base per release and pair. `current_release_scopes` appends `layer`.
- **Derived state, rebuilt whenever a pair's serving release changes.** An AFTER row trigger and an AFTER TRUNCATE trigger on `active_scope_pointer` run in the same transaction, so a maintenance repoint, a delete or a truncate is covered as well as activation. They maintain two tables, both empty for a pair served without a base scope:
  - `layered_shadowed_rows`: the base provision and navigation rows that a primary row of the same pair shadows.
  - `layered_navigation_overrides`: the merged-tree row of every served node whose tree fields differ from its stored ones.
- **How the merged tree is built:**
  - A primary node keeps the parent its own scope gives it.
  - A node that is a root of its scope takes its base twin's parent. Without a base twin, it takes the nearest served path prefix, as `build_navigation_nodes` does.
  - A parent cycle is broken at its smallest member, in code-point order, as `_break_parent_cycles` does.
  - Depth, child counts and encoded-descendant counts are recomputed. Segment and sort key are recomputed when a node's parent changed, and so is a label that was the segment fallback (no heading).
- **Views.** Each is the previous rule minus the shadowed rows.
  - `current_provisions` and `legacy_provisions` keep their single-SELECT form, plus an anti-join on a small table.
  - `current_navigation_nodes` is a UNION ALL of `navigation_nodes` and the overrides with no branch filters, filtered once outside. PostgreSQL flattens a UNION ALL into one append relation only when its branches carry no WHERE clause (`is_safe_append_member`), and only then can an ordered page merge two ordered index scans.
- **Direct `navigation_nodes` reads.** The `anon_read` and `authenticated_read` policies are the previous policy minus shadowed ids. The ids come from an owner-run set-returning function that is evaluated once per query and hashed.
- **`get_root_document_counts()`** counts exactly the roots the view serves. It reads the stored roots of each served scope through the 20260910150000 root index. It supersedes #666's `20260910140000` definition.
- **`activate_corpus_release`:**
  - Every check of `20260719043000` is kept for v2 and v3.
  - It accepts v4 and stores the signed layer in membership and in both `EXCEPT` comparisons.
  - It rejects a v2 or v3 object that carries a layer.
  - It rejects a layered pair whose layer carries a citation path twice.
- **Indexes:**
  - New: `navigation_nodes (jurisdiction, citation_path)`, which makes the ordered page possible.
  - Also included: #699's `idx_navigation_nodes_release_scope_version`. The definition is identical, so either migration is a no-op after the other.
  - The index statements run first, under `SET lock_timeout = '10s'`. A guard refuses an existing INVALID index left by a failed `CREATE INDEX CONCURRENTLY`.

### Direct-child lookup: `SupabaseQuery.get_section_with_children`

- The old lookup asked for `parent_id = <served id>`. A provision's `parent_id` is its parent's versioned id in its own scope, so it misses base sections under a primary title and primary sections under a base title.
- Children now come from `current_navigation_nodes?parent_path=eq.<citation_path>` and are read back from `current_provisions` by their winning ids, in batches of 100 and in navigation order. One child is kept per citation path.
- `include_legacy` keeps the old lookup.

### Docs

`docs/named-release-publication.md` has a new "Layered scopes" section, and a changelog fragment is added.

## Invariants (stated and tested)

| Invariant | Where tested |
|---|---|
| With no base scope active, every served view, both navigation policies, `get_root_document_counts()` and `current_provision_counts` return exactly what the previous definitions return. | `test_without_a_base_scope_every_view_is_the_previous_definition` (Hypothesis, multi-release histories, compared with the pre-layer definitions kept unchanged in a `reference` schema); `test_a_primary_only_successor_drops_the_layered_state`; `test_memberships_that_exist_when_the_migration_is_applied_become_primary` (migration applied to a database with activated releases) |
| Each citation path is served at most once per pair: the primary row when both layers carry it, the base row otherwise, whatever the dates or scope order. | `test_each_citation_path_serves_the_primary_row…`, `test_primary_wins_whatever_the_dates_and_scope_order`, and both property tests |
| `current_provisions` and `legacy_provisions` partition the staged rows. Served plus shadowed equals the signed rows of the active scopes. Counts, root counts and the two navigation policies agree with the served set. | `test_served_and_suppressed_rows_partition_the_staged_rows`, `_check_layered_pair` (every property example) |
| On well-formed pairs (declared parent = immediate path prefix, base closed under ancestors, no primary scope skipping a level), the merged navigation equals `build_navigation_nodes` over the winning records. With arbitrary parents and cross-layer cycles it follows the stated rules, using navigation.py's own cycle, depth, segment and sort-key helpers. | `test_merge_equals_building_navigation_over_the_winning_records`, `test_merge_follows_its_rules_on_arbitrary_parents` (Hypothesis, 40 examples each), plus example tests |
| Activation is atomic: a failed evidence, membership or ambiguity check leaves pointers, scopes, derived state and counts unchanged. A reaffirm writes nothing. Any pointer move keeps the derived state in step. Unrelated pairs are untouched, and rolling back to an earlier layered release restores its exact derived state. | `test_failed_evidence_leaves…`, `test_same_layer_duplicate…atomically`, `test_reaffirming…writes_nothing`, `test_any_pointer_move…`, `test_successor_keeps_the_base_and_unrelated_pairs`, `test_two_layered_pairs_register_activate_and_move_independently` |
| v3 objects and selectors without base scopes are byte-identical to pre-PR output. | `tests/test_release_layers.py` against the committed `f1916d73` fixture and all tracked selectors |
| The SQL helpers equal navigation.py's `_segment` and `_normalize_sort_segment`. | `test_sql_segment_helpers_equal_navigation_py` (Hypothesis, 200 examples) |

**Independent review.** Three reviews ran before this PR was opened: SQL, Python and contract, and tests. The test review ran 62 mutants against the migration. Thirteen non-equivalent mutants survived the first version of the tests. The tests added since kill all of them except two that are now pinned as intended behaviour. That reviewer also ran the layered and atomic modules on `postgres:15` (15.19, en_US.utf8, the CI image), and all passed.

## Query plans at representative scale

`tests/test_layered_serving_postgres.py::test_serving_plans_stay_index_driven_at_representative_scale`:

- **What it builds:**
  - the May base layers' 306,923 `us` rows: 53 titles and 60,393 sections, plus 49 titles, 4,900 parts and 241,528 sections;
  - 48 primary `us` scopes, half without their title or part row, colliding with 456 base paths;
  - stored `us` history and other jurisdictions.
- **Scale.** 401,299 provision rows per table in CI. `AXIOM_CORPUS_PLAN_SCALE=production` gives 1,521,299, with 721,299 `us` navigation rows.
- **How it serves them.** Through the active scope map, whose trigger derives the layered state as activation would.
- **What it asserts.**
  - Both single-path lookups are index scans on `idx_provisions_citation_path_version`, with no sequential scan and no sort.
  - The `us` page is a Merge Append of ordered index scans.

Results below are from `AXIOM_CORPUS_PLAN_SCALE=production`, on local PostgreSQL 14.24 with `shared_buffers` 3 GB and the default `work_mem` (4 MB), run as `anon` under a 3 s statement timeout. The laptop is shared, with a load average of 10 to 25.

| Request | Execution |
|---|---|
| `current_provisions?citation_path=eq.us/statute/30/500` (base only) | 0.075 ms |
| `current_provisions?citation_path=eq.us/statute/3/1` (collision; primary served) | 0.029 ms |
| `current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000` | 2.3 ms |
| `current_navigation_nodes?jurisdiction=eq.us&doc_type=eq.statute&parent_path=eq.us/statute/2&order=sort_key` (merged children) | 1.2 ms |
| `rpc/get_root_document_counts` | 10.6 ms |
| `navigation_nodes?…&parent_path=eq.us/statute/3` (direct anon read, policy) | 0.45 ms |
| Deriving the layered state when the release is served (all pairs) | 14.9 s (28.2 s in an earlier run under heavier load) |

For comparison, the previous lane's live-probe views on the same 1.52M-row data gave:

- the `us` page in 0.6–1.0 s;
- an offset-250,000 page that passed the 3 s timeout;
- root counts above 300 ms.

With no base scope active, the new views were as fast as or faster than the previous definitions on the same data and load (`us` page 37 ms vs 237 ms; root counts 11 ms vs 25 ms). One query got slower: the per-pair roots page of `current_navigation_nodes` (110 ms vs 66 ms). The synthetic data has 400k stored historical `us` roots; production has about 9k.

<details><summary>EXPLAIN (ANALYZE, BUFFERS): base-only single-path lookup</summary>

```
Nested Loop Anti Join  (cost=1.12..54.92 rows=4 width=719) (actual time=0.045..0.063 rows=1 loops=1)
  Buffers: shared hit=61
  ->  Nested Loop Semi Join  (cost=0.85..38.75 rows=4 width=719) (actual time=0.044..0.062 rows=1 loops=1)
        Buffers: shared hit=59
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.17 rows=4 width=719) (actual time=0.007..0.016 rows=11 loops=1)
              Index Cond: (citation_path = 'us/statute/30/500'::text)
              Buffers: shared hit=14
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.004..0.004 rows=0 loops=11)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 23
              Buffers: shared hit=45
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=11)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=22
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.002..0.003 rows=23 loops=11)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=23
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=1)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=30
Planning Time: 0.210 ms
Execution Time: 0.075 ms
```

</details>

<details><summary>EXPLAIN (ANALYZE, BUFFERS): collision single-path lookup</summary>

```
Nested Loop Anti Join  (cost=1.12..54.92 rows=4 width=719) (actual time=0.021..0.021 rows=1 loops=1)
  Buffers: shared hit=24
  ->  Nested Loop Semi Join  (cost=0.85..38.75 rows=4 width=719) (actual time=0.015..0.019 rows=2 loops=1)
        Buffers: shared hit=19
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.17 rows=4 width=719) (actual time=0.005..0.007 rows=3 loops=1)
              Index Cond: (citation_path = 'us/statute/3/1'::text)
              Buffers: shared hit=6
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.003..0.004 rows=1 loops=3)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 9
              Buffers: shared hit=13
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=3)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=6
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.002..0.002 rows=10 loops=3)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=7
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=2)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=5
Planning:
  Buffers: shared hit=30
Planning Time: 0.169 ms
Execution Time: 0.029 ms
```

</details>

<details><summary>EXPLAIN (ANALYZE, BUFFERS): us page of current_navigation_nodes</summary>

```
Limit  (cost=48.01..27172.76 rows=1000 width=48) (actual time=1.257..2.284 rows=1000 loops=1)
  Buffers: shared hit=1345
  ->  Merge Append  (cost=48.01..6398042.63 rows=235873 width=48) (actual time=1.256..2.255 rows=1000 loops=1)
        Sort Key: n.citation_path
        Buffers: shared hit=1345
        ->  Index Scan using idx_navigation_nodes_jurisdiction_citation_path on navigation_nodes n  (cost=47.72..6393882.10 rows=225037 width=47) (actual time=1.250..2.125 rows=699 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 310
              Buffers: shared hit=1054
              SubPlan 1
                ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.028..0.081 rows=250 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=10
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.002..0.021 rows=490 loops=1)
                            Buffers: shared hit=6
                      ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.023..0.024 rows=202 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 20kB
                            Buffers: shared hit=4
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.001..0.010 rows=202 loops=1)
                                  Buffers: shared hit=4
              SubPlan 2
                ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.006..0.034 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 402
                      Buffers: shared hit=6
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.001..0.004 rows=202 loops=1)
                            Buffers: shared hit=4
                      ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                            Buffers: shared hit=2
                            ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.001..0.002 rows=2 loops=1)
                                  Heap Fetches: 0
                                  Buffers: shared hit=2
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.001..0.023 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.009..0.366 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=101
        ->  Index Scan using idx_layered_navigation_overrides_citation_path on layered_navigation_overrides o  (cost=0.29..1801.79 rows=10836 width=66) (actual time=0.006..0.089 rows=302 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Buffers: shared hit=291
Planning:
  Buffers: shared hit=8
Planning Time: 0.200 ms
Execution Time: 2.318 ms
```

</details>

<details><summary>EXPLAIN (ANALYZE, BUFFERS): merged children and direct policy read</summary>

```
Limit  (cost=48.01..3831.30 rows=100 width=249) (actual time=1.110..1.225 rows=100 loops=1)
  Buffers: shared hit=234
  ->  Merge Append  (cost=48.01..41475.04 rows=1095 width=249) (actual time=1.110..1.222 rows=100 loops=1)
        Sort Key: n.sort_key
        Buffers: shared hit=234
        ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=47.72..41455.77 rows=1094 width=249) (actual time=1.107..1.216 rows=100 loops=1)
              Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 2
              Buffers: shared hit=232
              SubPlan 1
                ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.026..0.077 rows=250 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=10
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.002..0.020 rows=490 loops=1)
                            Buffers: shared hit=6
                      ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.022..0.022 rows=202 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 20kB
                            Buffers: shared hit=4
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.001..0.009 rows=202 loops=1)
                                  Buffers: shared hit=4
              SubPlan 2
                ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.005..0.033 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 402
                      Buffers: shared hit=6
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.001..0.004 rows=202 loops=1)
                            Buffers: shared hit=4
                      ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                            Buffers: shared hit=2
                            ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.001..0.001 rows=2 loops=1)
                                  Heap Fetches: 0
                                  Buffers: shared hit=2
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.001..0.021 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.002..0.309 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=101
        ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=286) (actual time=0.003..0.003 rows=0 loops=1)
              Index Cond: (parent_path = 'us/statute/2'::text)
              Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
              Buffers: shared hit=2
Planning:
  Buffers: shared hit=8
Planning Time: 0.209 ms
Execution Time: 1.245 ms
```

```
Limit  (cost=4.44..6021.09 rows=100 width=249) (actual time=0.378..0.441 rows=100 loops=1)
  Buffers: shared hit=136
  ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes  (cost=4.44..60531.94 rows=1006 width=249) (actual time=0.378..0.438 rows=100 loops=1)
        Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/3'::text))
        Filter: ((NOT (hashed SubPlan 3)) AND (hashed SubPlan 2))
        Rows Removed by Filter: 10
        Buffers: shared hit=136
        SubPlan 3
          ->  ProjectSet  (cost=0.00..2.77 rows=500 width=32) (actual time=0.021..0.244 rows=456 loops=1)
                Buffers: shared hit=12
                ->  Result  (cost=0.00..0.01 rows=1 width=0) (actual time=0.000..0.000 rows=1 loops=1)
        SubPlan 2
          ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.023..0.073 rows=250 loops=1)
                Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                Buffers: shared hit=10
                ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.001..0.020 rows=490 loops=1)
                      Buffers: shared hit=6
                ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.020..0.020 rows=202 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 20kB
                      Buffers: shared hit=4
                      ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.001..0.008 rows=202 loops=1)
                            Buffers: shared hit=4
Planning:
  Buffers: shared hit=4
Planning Time: 0.115 ms
Execution Time: 0.454 ms
```

</details>

## Deployment

1. **Merging this PR changes what two workflows apply.** `.github/workflows/publish.yml:112` and `.github/workflows/register-release-object.yml:121` run `scripts/apply_release_object_staging_migration.py`. From the next run, that script applies `20260927100000_stage_signed_release_object_v4.sql` instead of `20260803175000`.
   - It contains only the registration function.
   - v2 and v3 objects register exactly as before.
   - The insert trigger stays as `20260803175000` installed it.
   - `publish.yml:111`, `register-release-object.yml:120` and `activate-release.yml:193` still apply `20260722021000` only, through `scripts/apply_release_activation_upload_migration.py`; that is unchanged.
2. **No workflow applies `20260927110000_layered_release_serving.sql`.** Until it is applied, the production activation RPC (`20260719043000`) rejects every v4 object, so registering a v4 object is harmless. Apply it by hand, as `postgres` and with human approval, before the first layered activation (PR 5):
   1. Build the two `navigation_nodes` indexes with `CREATE INDEX CONCURRENTLY IF NOT EXISTS` and the exact definitions in section 1 of the file. Confirm `pg_index.indisvalid` for both.
   2. Apply the file in one transaction. It sets `lock_timeout` to 10 s, so it fails rather than queueing serving reads. Retry at a quiet moment if it times out.
   3. With no base scope active, both derived tables stay empty and every view returns the same rows.
3. **Prerequisite outside this repo.** Before the first layered activation, axiom.org must read its navigation tree from `current_navigation_nodes`. A direct `navigation_nodes` read hides shadowed rows but returns the stored per-scope tree fields. On axiom.org `master` (`src/lib/axiom/navigation-index/read.ts`, `section-page.ts`, `coverage-page.ts`) the tree reads `navigation_nodes` directly. There, a primary section that leaves its title to the base would show as a top-level document and be missing from its title's children.
4. **Root counts.** Production already runs #666's served-only `get_root_document_counts()`. I checked this read-only with the anon key: the RPC returns `us/statute` 373 and `us/regulation` 110, which equal `count=exact` of served roots through `current_navigation_nodes`. The new definition returns the same rows while no base scope is active, so no published coverage number changes when the file is applied. #666 can be closed as superseded once this lands.

## Deviations from the plan and the brief, and why

- **The previous lane's serving design was replaced.** Its views tested every base row against served primary rows with a correlated probe inside one EXISTS, and kept a separate summaries table for child counts. That made the planner sort every stored `us` navigation row for a page (numbers above). It also left a primary root of its own scope as a root of the merged tree, although its title is in the base. The derived shadow and override tables restore indexed plans and place such nodes in the base tree.
- **Brief contract item 3 (parent resolution in validation sees both layers) is not done.** Parent closure stays per scope, as `169dbb46` ("Require parent closure within each immutable release scope") made it. Supabase derives a row's `parent_id` from the parent's path and the row's own version, so a parent only the base carries cannot satisfy it. Cross-layer parenting happens in serving instead: a primary section that leaves its title to the base declares no parent and is placed under the base title. `test_parent_closure_stays_per_scope_across_layers` pins both cases.
- **The previous lane's SQL check against base/primary overlaps across pairs was dropped.** Serving resolves precedence per pair, so such an overlap cannot make serving ambiguous. Release validation still rejects it.
- **The same-layer ambiguity check runs only for layered pairs.** Running it for every pair would cost a full GROUP BY over a large release. An unlayered pair keeps its previous behaviour; validation rejects duplicates in new releases.
- **The `.github/workflows/ci.yml` postgres job's pytest line adds `tests/test_layered_serving_postgres.py`.** No action or toolchain pins changed.

## Not verified, known limits, follow-ups

- **Production state.** Nothing was run against production. The only production contact was the read-only anon checks above. Live function definitions other than root counts were not inspected.
- **Activation duration.** Deriving the layered state takes 15 to 28 s locally for the whole release. Activation of the restoration also recomputes every scope's projection digests. Its end-to-end time through the activation path's transport has to be measured in PR 5, as the plan already requires.
- **Placement of new eCFR sections.** Staged rows keep no declared parent path, only a versioned parent id. So a primary root that the base does not carry goes under its nearest served path prefix, even if it declares a non-prefix parent. eCFR sections declare their subpart, so a newly added eCFR section absent from the May base lands under its part rather than its subpart. No text is wrong, and sections the base carries are placed under their base twin's parent.
- **Repealed base sections stay served.** Precedence is per path. A primary re-encoding of a section cannot retire a base descendant it no longer has, such as a repealed subsection; the base row stays served.
- **Activation gate.** `scripts/check_release_gate.py` compares scope triples only and does not compare layers. That is PR 4 work in the plan.
- **Partial-corpus test run.** The full suite ran in partial-corpus mode; see the test results below.

## Tests

Commands, each run at the final head unless noted:

```text
$ uv run --extra dev ruff check . --extend-exclude .pr3-scratch --extend-exclude .review-scratch
All checks passed!
$ uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports
Success: no issues found in 98 source files
$ uv run --extra dev towncrier check --compare-with origin/main
Found:
1. changelog.d/layered-release-serving.added.md
$ DATABASE_URL=postgresql://test@localhost:55432/axiom_corpus_test AXIOM_CORPUS_PARTIAL_TESTS=1 \
    uv run --extra dev python -m pytest -q tests/test_layered_serving_postgres.py tests/test_atomic_release_postgres.py
137 passed in 65.93s
$ AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev python -m pytest -q tests/test_release_layers.py tests/test_query_supabase.py tests/test_release_object_staging_v4_migration.py
(41 + 26 + 2 passed)
```

The ruff run excludes the untracked scratch directories `.pr3-scratch` and `.review-scratch`. The atomic module runs every test with and without the layered migration.

**Full suite.** It ran in partial-corpus mode at the final head `52e49750`, with `DATABASE_URL` set so the PostgreSQL modules ran too. This worktree has not fetched most of the 15 GB corpus, which `docs/corpus-storage.md` allows via `AXIOM_CORPUS_PARTIAL_TESTS=1`.

```text
$ DATABASE_URL=… AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev python -m pytest -q
287 failed, 5076 passed, 36 skipped, 208 deselected, 38 warnings in 254.24s
```

All 287 failures are real-corpus-data tests: state manuals, recovery audits, ingests. Each of the same node IDs, re-run on `origin/main` (`595a64c5`) in this same worktree and data tree, fails there too; the two failure sets are identical. An earlier full run at `788741e8` had 26 more failures. They had failed with `FileNotFoundError` on corpus files that were fetched during the re-runs, and they pass on both the branch and `origin/main` once present. CI fetches the full corpus, so CI is the authoritative full run.

**CI on `52e49750`: every check passes** (run 37270685500):
- `test (3.14)`: the full suite on the full corpus.
- `postgres`: PostgreSQL 15. `137 passed in 154.47s` covers both modules, including `test_serving_plans_stay_index_driven_at_representative_scale` and the Hypothesis properties.
- `Validate named release selectors`, `Citation-path grammar (A6)` and `Validate GitHub workflows`.

## Callers of modified functions

GitNexus was not used. Callers come from `git grep`:

- `_release_citation_paths`: `release_quality.py:167`.
- `selector_sha256`: `release_quality.py:206`, `release/manifest.py:308`, `scripts/build_nz_rulespec_legacy_migration.py:477`.
- `build_release_content`: `scripts/publish_corpus.py:205,382,472`, `scripts/probes/hts_ch50_signed_fixture.py:84`.
- `build_unsigned_release_object` and `sign_release_object`: `scripts/publish_corpus.py:392-393`, `scripts/probes/hts_ch50_signed_fixture.py:96`.
- `_validate_unsigned_release_object`: `release/manifest.py:376,389`. `_validate_scope_entries`: `release/manifest.py:494`. `_parse_scope` (releases): `releases.py:113`.
- `get_section_with_children`: `src/axiom_corpus/cli.py:1952`, `query/supabase.py:329,405`.
- `fetch_provision_counts` (docstring only): `corpus/cli.py:870`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
