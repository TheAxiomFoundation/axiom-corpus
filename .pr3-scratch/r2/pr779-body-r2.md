PR 3 of the base-layer restore plan on #728 (layered serving). It lets a release serve a base scope underneath its primary scopes. Precedence follows the #728 ruling: for a citation path both layers carry, the primary row is served. It adds no selector, no signed manifest and no corpus data. #755 has merged, and this branch contains `origin/main` at `595a64c5`.

A previous lane started this work and its session ended on 2026-09-27. This branch keeps its signed-layer commit (`c96011df`) and its uncommitted migrations, committed unchanged as `42709a2a` and marked as work in progress. It then merges #755, which carries #769, and finishes the job. The serving design was rebuilt after measurement (see "Deviations").

**Review round 2** (Opus APPROVE with three low findings, GPT-6.1 Sol REQUEST_CHANGES with three) is addressed in `90fad9bf` through `affd452a`; see "Review round 2" below. Every SQL finding was reproduced with two real PostgreSQL sessions before it was fixed, and each fix was attacked by further independent reviews with the database available.

**Review round 1** (two independent reviews, Opus and GPT-6.1 Sol, both REQUEST_CHANGES) is addressed in `6c1a9787` through `a32437da`; see "Review round 1" below. Before pushing, two more independent Opus reviews attacked this round. The SQL one reproduced a bypass and a cost problem, both now fixed (`88b95bf4`). A verification pass then approved, and its three small points are fixed in `db2c81c7`.

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
  - Citation paths stay unique within each layer. A base/primary overlap is allowed only inside one pair, checked inside #755's streaming `_release_citation_paths` with one owner map per layer.
  - New this round: validation merges each layered pair's trees as serving does (`navigation.merge_layered_parent_paths` over `navigation.scope_parent_paths`). It warns, without failing, in two cases:
    - `layered_primary_root_unattached`: a primary root lands under no served ancestor, so a mistyped path would become a new top-level document. One warning per primary scope.
    - `layered_parent_cycle_broken`: the scopes disagree about which of two paths is the ancestor, so serving breaks a parent cycle.

    Both are reported after the per-scope checks, so a capped issue list still shows errors first. The parents are read in the citation pass validation already makes: one string pair per row, no bodies.
- **Lock-pinned base scopes.** A base scope whose artifacts are pinned by a committed corpus lock (#769) builds and signs v4 content through `_require_tracked_release_inputs`. New test, plus a test that a lock pinning other bytes is rejected.

### Registration RPC: `20260927100000_stage_signed_release_object_v4.sql`

- The file holds only `corpus.stage_corpus_release_object`.
- It accepts v4 and enforces the layer rules: exact `"base"`, at least one base scope, at most one per pair.
- It registers v2 and v3 exactly as `20260803175000` does. `tests/test_release_object_staging_v4_migration.py` undoes the three v4 edits and requires `20260803175000`'s function text back.
- `scripts/apply_release_object_staging_migration.py` now points at this file (`MIGRATION`, `REQUIRED_FRAGMENTS`). Before, every ordinary publication would have reinstalled a v3-only function.

### Layered serving: `20260927110000_layered_release_serving.sql`

This file is applied by hand; see Deployment.

- **Layer column.** `release_scopes.layer` (`primary` by default, so historical rows are primary), with a check constraint and a partial unique index for one base per release and pair. `current_release_scopes` appends `layer`.
- **Derived state.** Two tables, both empty for a pair served without a base scope:
  - `layered_shadowed_rows`: the base provision and navigation rows that a primary row of the same pair shadows.
  - `layered_navigation_overrides`: the merged-tree row of every served node whose tree fields differ from its stored ones.
- **The derived state stays a function of what is served, whoever writes (short of turning triggers off).** New this round, after review:
  - **Pointer writes.** An AFTER row trigger and an AFTER TRUNCATE trigger on `active_scope_pointer` re-derive the pair in the same transaction as a pointer write that moves it to or from a release with a base scope for it: activation, a maintenance repoint, a delete or a truncate. A move between releases without one derives nothing (round 2, finding 5). Under `READ COMMITTED`, a pair that still has derived rows (left by membership altered with triggers off) is re-derived on any move. The trigger takes no further lock on the pointers; the write's row lock orders it against other writes of the pair.
  - **Membership.** Membership of a signed release is immutable. Every row belongs to a signed release (`release_scopes_release_object_fkey`), so an `UPDATE`, `DELETE` or `TRUNCATE` of `release_scopes` is rejected (`guard_release_scope_membership`).
  - **Inserted membership.** An inserted row must be one of its release object's signed scopes, with its signed layer. The check runs once per statement over the inserted rows (`guard_release_scope_membership_insert`). A signed scope that joins a pair its release already serves re-derives that pair in the same statement (`sync_layered_serving_membership`); that covers membership altered before the guard and then restored, by re-activation or by an insert.
  - **Release objects.** A signed release object is immutable: only `created_at` may change, which `stage_corpus_release_object` repairs. An object with membership cannot be deleted (`guard_release_object_immutable`). So no statement can hide it from the membership guard or from the released-row guard of `20260710180000`.
  - **Truncation of released rows.** `TRUNCATE` of `provisions` or `navigation_nodes` is rejected while either holds a row of a signed release's scope (`guard_released_scope_rows_truncate`). This is the statement-level twin of `guard_released_scope_row_immutable`, and it applies whether or not the release is layered. A table holding only unreleased staged rows can still be truncated, under `READ COMMITTED` (round 2, finding 1).
  - **Derived tables.** Only the derivation writes them: it marks its writes with a transaction-local setting, and any other write is rejected (`guard_layered_serving_write`).
  - **Isolation.** Derivation runs only under `READ COMMITTED` (`READ UNCOMMITTED` counts as it). There each statement reads what was committed when it started, and every writer of a pair's derived rows is ordered against the others: pointer writes by the pointer row, a layered membership insert, activation, re-derivation and a direct refresh by `EXCLUSIVE` on the pointers. An older `REPEATABLE READ` or `SERIALIZABLE` snapshot could miss rows committed meanwhile. Writes that involve no release with a base scope for the pair they touch (every v2 and v3 release) need no derivation and run under any isolation level, as before this PR. `TRUNCATE` of the pointers, membership or released rows runs only under `READ COMMITTED`.
  - **Statistics.** Every derivation that changes the derived tables runs `ANALYZE` on both.
- **How the merged tree is built:**
  - A primary node keeps the parent its own scope gives it.
  - A node that is a root of its scope takes its base twin's parent. Without a base twin, it takes the nearest served path prefix, as `build_navigation_nodes` does.
  - A parent cycle is broken at its smallest member, in code-point order, as `_break_parent_cycles` does.
  - Depth, child counts and encoded-descendant counts are recomputed. Segment and sort key are recomputed when a node's parent changed. So is a label that was the segment fallback, meaning the provision has no heading blank to `str.strip()`. That check now uses Python's 29 whitespace characters (`navigation_heading_is_blank`), not ASCII whitespace only.
- **Views.** Each is the previous rule minus the shadowed rows.
  - `current_provisions` and `legacy_provisions` keep their single-SELECT form, plus an anti-join on a small table.
  - `current_navigation_nodes` is a UNION ALL of `navigation_nodes` and the overrides with no branch filters, filtered once outside. PostgreSQL flattens a UNION ALL into one append relation only when its branches carry no WHERE clause (`is_safe_append_member`), and only then can an ordered page merge two ordered index scans.
- **Direct `navigation_nodes` reads.** The `anon_read` and `authenticated_read` policies are the previous policy minus shadowed ids. The ids come from an owner-run set-returning function that is evaluated once per query and hashed.
- **`get_root_document_counts()`** counts exactly the roots the view serves. It reads the stored roots of each served scope through the 20260910150000 root index, and names `navigation_nodes` before `current_release_scopes` so it takes its locks in the order every other serving read does. It counts served roots only; see "Root counts" under Deployment for how that compares with the repository's history and with production.
- **`corpus.rederive_layered_serving()`** (new) re-derives every served pair. It is a separate deployment step, and it takes only locks activation takes. It refreshes `current_provision_counts` only when the shadowed provisions change.
- **`activate_corpus_release`:**
  - Every check of `20260719043000` is kept for v2 and v3.
  - It accepts v4 and stores the signed layer in membership and in both `EXCEPT` comparisons.
  - It rejects a v2 or v3 object that carries a layer.
  - It rejects a layered pair whose layer carries a citation path twice.
- **Deployment locks** (round 2, finding 4). The file takes a transaction advisory lock, then `SHARE ROW EXCLUSIVE` on the tables writes use, then `ACCESS EXCLUSIVE` on the six relations serving reads use, in the order those reads take their locks; after that it waits for no lock a read or a row write can hold. See Deployment.
- **Indexes:**
  - New: `navigation_nodes (jurisdiction, citation_path)`, which makes the ordered page possible.
  - Also included: #699's `idx_navigation_nodes_release_scope_version`. The definition is identical, so either migration is a no-op after the other.
  - A guard refuses an existing INVALID index left by a failed `CREATE INDEX CONCURRENTLY`.

### Direct-child lookup: `SupabaseQuery.get_section_with_children`

- **Unlayered pairs.** A pair whose serving release has no base scope gets exactly `origin/main`'s request (`parent_id=eq.<served id>&order=ordinal`), so it gets exactly what it got before. The client checks for a base scope with `current_release_scopes?select=*&jurisdiction=eq.<j>&document_class=eq.<dc>&order=release_name,version`, paged past the row cap (round 2, finding 3). It selects every column and orders only by columns the view always had, because production's view has no `layer` column until `20260927110000` is applied, and a filter on it returns HTTP 400 (checked read-only).
- **Layered pairs.** A served title's sections may be base rows whose `parent_id` names the base title. So the children come from `current_navigation_nodes?parent_path=eq.<path>&doc_type=eq.<class>&order=sort_key,path,id`.
  - It pages by offset past PostgREST's row cap until an empty page.
  - The provisions are read back by their winning ids in batches of 100, also paged.
  - One child is kept per citation path.
- `include_legacy` and `deep=True` are unchanged.
- **Cost.** A non-legacy, non-deep call for an unlayered pair now makes two more requests than `origin/main` (the base-scope page and the empty page that ends paging): four instead of two. An exact single-request check would need the `Content-Range` header, which `_request` does not return.

### Docs

`docs/named-release-publication.md` has a "Layered scopes" section with a "Deploying the serving migration" subsection, and a changelog fragment is added.

## Invariants (stated and tested)

| Invariant | Where tested |
|---|---|
| With no base scope active, every served view, both navigation policies, `get_root_document_counts()` and `current_provision_counts` return exactly what the previous definitions return. | `test_without_a_base_scope_every_view_is_the_previous_definition` (Hypothesis, multi-release histories, compared with the pre-layer definitions kept unchanged in a `reference` schema); `test_a_primary_only_successor_drops_the_layered_state`; `test_memberships_that_exist_when_the_migration_is_applied_become_primary` |
| After any committed statement made without turning triggers off, the derived tables equal a derivation from scratch of what is served, a layered pair serves each citation path at most once, and navigation serves exactly the served provisions. | `_assert_serving_is_consistent`, asserted right after each of the 18 writes in `test_writes_under_a_served_layered_release_are_rejected`; also in the restoration, re-activation, deployment, isolation, counts and MERGE tests. An in-session reviewer also ran random sequences of up to 60 owner statements over 60 seeds (scratch, not committed). |
| Membership of a signed release is exactly its signed scopes, and the signed object does not change. | `test_only_signed_scopes_join_membership`, `test_release_objects_change_only_their_publication_time`, `test_writes_…[sign an extra scope into the stored object]` |
| Each citation path is served at most once per pair: the primary row when both layers carry it, the base row otherwise, whatever the dates or scope order. | `test_each_citation_path_serves_the_primary_row…`, `test_primary_wins_whatever_the_dates_and_scope_order`, and both property tests |
| `current_provisions` and `legacy_provisions` partition the staged rows. Served plus shadowed equals the signed rows of the active scopes. Counts, root counts and the two navigation policies agree with the served set. | `test_served_and_suppressed_rows_partition_the_staged_rows`, `_check_layered_pair` (every property example) |
| On well-formed pairs the merged navigation equals `build_navigation_nodes` over the winning records. With arbitrary parents and cross-layer cycles it follows the stated rules. Release validation's prediction (`merge_layered_parent_paths`) equals the parents serving builds. | `test_merge_equals_building_navigation_over_the_winning_records`, `test_merge_follows_its_rules_on_arbitrary_parents` (Hypothesis, 40 examples each, now with blank-Unicode headings and the validation prediction compared); `test_the_merge_equals_building_navigation_over_the_winning_records`, `test_the_merged_tree_is_a_forest_of_the_served_paths` (Hypothesis, 300 each) |
| For a pair served without a base scope, `get_section_with_children` returns exactly what `origin/main` returns, under any row cap. For a layered pair it returns each served navigation child once, in navigation order, under any row cap. | `test_unlayered_children_equal_origin_main_on_any_served_rows` (Hypothesis, 150, row caps 1–4); `test_layered_children_are_the_served_navigation_children` (Hypothesis, 150, row caps 1–3); `test_the_query_client_reads_children_through_the_serving_views` (the client against the real views as anon, row cap 2) |
| Root counts are served roots only: equal to #666's definition with no base scope, and differing from `20260910120000` by exactly the superseded and never-released stored roots. | `_assert_matches_reference`; `test_root_counts_are_served_roots_not_every_stored_root` |
| Activation is atomic: a failed check leaves pointers, scopes, derived state and counts unchanged. A reaffirm writes nothing. Re-activating an earlier signed release restores its exact derived state. | `test_failed_evidence_leaves…`, `test_same_layer_duplicate…atomically`, `test_reaffirming…writes_nothing`, `test_reactivating_an_earlier_signed_release_restores_its_serving`, `test_two_layered_pairs_register_activate_and_move_independently` |
| The SQL helpers equal navigation.py's `_segment`, `_normalize_sort_segment` and `_label_text`'s blankness test. | `test_sql_segment_helpers_equal_navigation_py` (Hypothesis, 200); `test_sql_heading_blankness_equals_python_strip` (Hypothesis, 300) |
| Concurrent writers of a pair's derived rows are ordered: a direct refresh, pointer writes, layered membership inserts, activations and re-derivations leave the derived tables equal to a derivation from scratch, whatever the interleaving. A `TRUNCATE` under an old snapshot is refused. | `test_a_direct_refresh_is_ordered_against_an_owner_pointer_write`, `test_two_direct_refreshes_of_one_pair_are_ordered`, `test_truncate_under_a_snapshot_older_than_an_activation_is_refused`, `test_truncate_waiting_on_an_activation_sees_what_it_committed` (two real sessions each) |
| Applying the file never deadlocks with a single-statement serving read: a read blocked at any of the file's six `ACCESS EXCLUSIVE` relations holds none the file takes after it, and the file, waiting at one, holds `ACCESS EXCLUSIVE` on none that a read takes after it. | `test_serving_reads_take_their_locks_in_the_order_the_file_takes_its_own`, `test_the_file_takes_its_exclusive_locks_first_in_the_order_reads_take_theirs`, `test_the_file_takes_access_exclusive_only_where_it_orders_it`, `test_applying_the_file_under_serving_reads_does_not_deadlock`, `test_applying_the_file_under_looping_serving_reads_deadlocks_nothing`, `test_two_applications_at_once_wait_for_each_other`, `test_a_write_in_progress_delays_the_file_before_it_blocks_reads`, `test_restoring_a_base_row_while_the_file_is_applied_does_not_deadlock` |
| Releases without a base scope activate, re-activate, roll back, move by hand and insert membership exactly as before, under every isolation level. | `test_unlayered_releases_activate_and_move_under_any_isolation`, `test_an_unlayered_move_after_a_concurrent_removal_works_under_any_isolation`, `test_read_uncommitted_counts_as_read_committed` |
| The client finds a base scope wherever membership lists it, under any row cap. | `test_the_base_scope_is_found_wherever_membership_lists_it`; the layered-children property draws the base row's position and sort order |
| v3 objects and selectors without base scopes are byte-identical to pre-PR output. | `tests/test_release_layers.py` against the committed `f1916d73` fixture and all tracked selectors |

## Review round 2

Round 2 reviewed `a32437da`. Opus approved with three low findings; GPT-6.1 Sol requested changes with three. Neither could run PostgreSQL, so each SQL finding was first written as a two-session test (real connections to a local PostgreSQL 14 cluster, interleaved step by step) and run against `a32437da`. **All six findings reproduced.** The fixes are `90fad9bf` (client), `04bd2077` (ordering), then three verification rounds (`9f2e331e`, `8d735f86`, `affd452a`, with a docs commit `ff52e847`). Every test named below failed on the commit before its fix and passes at the head. Pre-fix logs and the scratch harnesses are kept outside the branch.

| # | Finding | Reproduced on `a32437da` | Change | Tests |
|---|---|---|---|---|
| 1 | `TRUNCATE` guards decide from an old snapshot (Sol P1) | **Yes.** A `REPEATABLE READ` or `SERIALIZABLE` session whose snapshot predates an activation truncated `navigation_nodes`, `provisions`, `release_scopes` or the pointers: all 8 cases committed. After `TRUNCATE navigation_nodes`, 0 stored navigation rows and 5 merged override rows still served; after `TRUNCATE release_scopes`, 0 provisions served and the same 5 override rows; after truncating the pointers, the same. | The three `TRUNCATE` triggers (membership guard, released-row guard, the pointers' cleanup) run only under `READ COMMITTED` (`guard_truncate_reads_committed_state`). There `TRUNCATE` holds `ACCESS EXCLUSIVE` before its triggers fire, and each statement of a volatile function reads a fresh snapshot, so the guard sees everything committed before the lock was granted. | `test_truncate_under_a_snapshot_older_than_an_activation_is_refused` (4 statements × 2 levels); `test_truncate_waiting_on_an_activation_sees_what_it_committed` (READ COMMITTED is enough; passes before and after) |
| 2 | A direct `refresh_layered_serving()` races an owner's pointer write (both) | **Yes, every shape.** Refresh first, then a repoint to a release that shadows a different path: the repoint committed, the first release's shadow row survived, and `fx/statute/1/2` was served by neither `current_provisions` nor `current_navigation_nodes`. With overlapping shadows, with the repoint first, and with two direct refreshes: `UniqueViolation` on `layered_shadowed_rows_pkey`. | A direct call (not from a trigger) takes `EXCLUSIVE` on `active_scope_pointer` before reading anything, which every pointer write, activation, layered membership insert and re-derivation conflicts with. Trigger callers are already ordered by the pointer row or by `EXCLUSIVE`. | `test_a_direct_refresh_is_ordered_against_an_owner_pointer_write` (3 orders), `test_two_direct_refreshes_of_one_pair_are_ordered` |
| 3 | The client's base-layer probe is capped (Sol) | **Yes.** 1 child returned of 1,001 when the base scope's row comes after 1,000 primary scopes. Hypothesis minimized it to a one-row cap with the base second. | `_serves_base_layer` pages the pair's membership with `_all_rows`, ordered by `release_name,version`. That order is total, because one release serves a pair and membership's key is `(release_name, jurisdiction, document_class, version)`, and both columns exist before the migration, so it stays valid against the pre-migration view. The emulated PostgREST now rejects an `order` on a missing column, as PostgREST does. | `test_the_base_scope_is_found_wherever_membership_lists_it` (base row at positions 0, 500, 1000); `test_layered_children_are_the_served_navigation_children` now draws the base row's position and sort order |
| 4 | Deployment deadlocks with concurrent reads (Opus 1) | **Yes.** In the deterministic interleaving (a read in flight on `current_release_scopes`, the file waiting, a second read queued behind it), 6 of 6 cases ended in `DeadlockDetected`. In a loop of 12 anon readers, 40 of 40 re-applications deadlocked and 436 reads failed; for first applications, 39 of 40 and 484 reads. `get_root_document_counts()` also locked `current_release_scopes` before `navigation_nodes`, the reverse of every other read. | The file takes a transaction advisory lock (one application at a time). Then `SHARE ROW EXCLUSIVE` on the tables writes use (`provisions`, `navigation_nodes`, `release_objects`, `release_scopes`, `active_scope_pointer`, the derived tables), so a write in progress delays it before it blocks any read. Then `ACCESS EXCLUSIVE` on `current_provisions`, `legacy_provisions`, `current_navigation_nodes`, `navigation_nodes`, `current_release_scopes`, `release_scopes`, in the order reads take theirs. `LOCK TABLE` on a view recurses into its definition, so views are locked by a no-op `ALTER VIEW … OWNER TO <its owner>`, which locks the view alone and changes no catalog row. The root-count RPC names `navigation_nodes` first. Re-applying no longer re-enables row security on the derived tables (an `ACCESS EXCLUSIVE` lock). Same loop after `04bd2077`: 0 deadlocks and 0 failed reads in 40 re-applications and 40 first applications; a verifier repeated it on `8d735f86` with staging writers and an activation loop added, and all 40 applications committed with no errors. | `test_serving_reads_take_their_locks_in_the_order_the_file_takes_its_own` (each of the 6 relations × 7 serving reads); `test_the_file_takes_its_exclusive_locks_first_in_the_order_reads_take_theirs`; `test_the_file_takes_access_exclusive_only_where_it_orders_it`; `test_applying_the_file_under_serving_reads_does_not_deadlock`; `test_applying_the_file_under_looping_serving_reads_deadlocks_nothing`; `test_two_applications_at_once_wait_for_each_other`; `test_a_write_in_progress_delays_the_file_before_it_blocks_reads`; `test_restoring_a_base_row_while_the_file_is_applied_does_not_deadlock` (each for a first application and a re-application) |
| 5 | `READ COMMITTED` required for every activation (both) | **Yes.** Activating a v3 release under `REPEATABLE READ` or `SERIALIZABLE` raised `release membership is inserted only under READ COMMITTED`. | A pointer move or membership insert that involves no release with a base scope for the pair derives nothing, takes no extra lock and runs under any isolation level, as before. Whether a release layers a pair: under `READ COMMITTED`, its membership (an index probe, read exactly as the derivation reads it); otherwise its signed release object, compared with `->>` as the guards compare it and read once per release per transaction. The membership trigger reads each inserted release's object once per statement. Layered moves still run only under `READ COMMITTED`; `READ UNCOMMITTED` counts as `READ COMMITTED`. | `test_unlayered_releases_activate_and_move_under_any_isolation` (activate, successor, rollback, reaffirm, hand repoint, pointer removal and restore, membership insert); `test_layered_serving_still_moves_only_under_read_committed`; `test_an_unlayered_move_after_a_concurrent_removal_works_under_any_isolation`; `test_read_uncommitted_counts_as_read_committed`; `test_layering_is_read_from_signed_scopes_as_the_guards_read_them`; `test_layering_is_matched_by_pair_not_by_its_values`; `test_derivation_and_membership_inserts_need_read_committed` (updated: its pointer case moved to the test above) |
| 6 | Doc mismatch on pointer locks (Opus 4) | The round-1 report said triggers no longer take exclusive locks on the pointer table; `sync_layered_serving_membership` took `EXCLUSIVE` for any non-empty membership insert. | Corrected in code and text. The membership trigger takes `EXCLUSIVE` on the pointers only for a statement inserting a row whose release has a base scope for that row's pair (activation already holds it; an owner restoring a row takes it). The pointer trigger takes no further lock on the pointers. A direct refresh takes `EXCLUSIVE`. When a layered move derives, `ANALYZE` holds `SHARE UPDATE EXCLUSIVE` on both derived tables until commit. | Docs and comments; lock behavior covered by the tests above |

**Verification rounds.** After `04bd2077`, two more independent Opus reviews ran with the local cluster and reproduced their findings. A third and a fourth checked each fix. Everything they found is fixed and tested:
- **Type-mismatch regression.** The first version of the unlayered check compared signed scopes with jsonb containment, while the guards use `->>`. A base scope signed with a non-string document class could be served with nothing derived. An owner can activate such an object; Python's selector rejects it.
- **Cost.** The check read the whole release object once per inserted row and once per pointer move. On a 7.3 MB object (1,042 scopes, 288 pairs, 45,880 artifacts), a 1,042-row membership insert took 6,908 ms and 288 pointer moves 1,824 ms. Now they take 38 ms and 10 ms (22 ms under `REPEATABLE READ`), against 22.6 ms and 8.9 ms with the sync triggers off.
- **Two applications at once deadlocked**, because section 1 locks `navigation_nodes` first.
- **A write in progress** made the file wait while already holding the serving views.
- **An owner restoring a base membership row** while the file was applied deadlocked with it.
- **A memo matched swapped pairs**, because nested-array containment ignores element order.
- **A stale `REPEATABLE READ` snapshot** refused an unlayered move after a concurrent pointer removal.
- **`READ UNCOMMITTED` was refused.**
- **Doc overclaims.** The docs now give the exact `psql --single-transaction` command and say that the no-deadlock guarantee covers single-statement reads. They say `lock_timeout` caps each wait, not the total, so a queued read can still reach its own statement timeout. They also say re-activating a serving layered release works under any level.
- **Test robustness.** The two-session tests replace the file's 2 s `lock_timeout`, so a slow runner cannot fail them; the read-order test requires that the read of the blocked relation actually waited.

The final verification pass, on `8d735f86`, approved; its low findings (the restore deadlock, the stale-snapshot refusal, three doc lines) are fixed in `affd452a`.

**Flagged, not changed**
- **The July row guard decides from an old snapshot** (`guard_released_scope_row_immutable`, `20260710180000`). A reviewer reproduced it: a `REPEATABLE READ` snapshot taken before a layered activation deleted a released primary row, and `fx/statute/1/1` was then served by neither view. The fix would refuse every non-`READ COMMITTED` write to `provisions` and `navigation_nodes`, including staging. Whether that is safe depends on production writers' isolation, which I could not check read-only. Nothing in this repository sets an isolation level (PostgREST and the scripts use the server default). The docs record the gap. **Recommend a follow-up issue.**
- **An owner's raw membership insert during a `READ COMMITTED` `TRUNCATE` of `provisions`.** It can commit after the truncate's guard read. The result equals the serial order truncate-then-insert, which current rules allow; activating that release would then fail its count check.
- **Multi-statement read transactions.** One that reads one relation and then another can deadlock with the file, which then rolls back. PostgREST requests and RPC calls are single statements.
- **Two owner transactions that each write a pointer and then call `refresh` directly** deadlock on the lock upgrade. The docs say to run a direct refresh in its own transaction; a pointer write derives its pair anyway.
- **Two concurrent owner moves of different layered pairs** can deadlock through `ANALYZE`'s `SHARE UPDATE EXCLUSIVE`. This predates this round. Activations serialize on `EXCLUSIVE`, so only hand writes meet it.
- **Owner bypasses.** Turning triggers off, or setting `corpus.layered_serving_derivation` or a `corpus.layered_base_pairs_*` setting by hand, bypasses the guards. All are documented.
- **An owner's uncommitted `GRANT`** on one of the file's objects can still make it wait while it holds its locks, bounded by the 2 s lock timeout.
- **The no-op `ALTER VIEW … OWNER TO` on Supabase.** I could not check locally how Supabase's hooks (supautils, event triggers) react to it. It changes no catalog row (`pg_class.xmin` is unchanged), and the file already requires owning the views it replaces.

## Review round 1

Each must-fix item has a test that failed at `52e49750`. The pre-fix runs were saved: 24 PostgreSQL tests failed, mostly at the consistency check, where the stored derived rows differed from a fresh derivation; 7 query-client tests failed with the reviewers' numbers; 3 validation tests failed.

| Finding | Change | Tests (fail before, pass after) |
|---|---|---|
| 1. Membership writes desynchronize derived state | Membership guards, release-object immutability, re-derivation on a restoring insert, READ COMMITTED (`6c1a9787`, `88b95bf4`, `db2c81c7`). The test that mutated membership and then deleted the pointer now asserts the state right after the write, and checks activation's layer comparison separately with triggers off. | `test_writes_under_a_served_layered_release_are_rejected[demote the base scope / move a primary scope to another version / delete a primary scope / delete the base scope / add an unsigned primary scope / … while the object is hidden / sign an extra scope into the stored object / delete the release object]`, `test_activation_compares_the_stored_layer_with_the_signed_one`, `test_only_signed_scopes_join_membership`, `test_restoring_membership_lost_before_the_guard_rederives_the_pair[reactivation, insert]`, `test_derivation_and_membership_inserts_need_read_committed[REPEATABLE READ, SERIALIZABLE]`; `test_reactivating_an_earlier_signed_release_restores_its_serving` (regression) |
| 2. Owner `TRUNCATE` leaves copied overrides served | `guard_released_scope_rows_truncate` on `provisions` and `navigation_nodes`; `TRUNCATE` of membership rejected; derived tables accept only the derivation's writes | `test_writes_…[truncate navigation / truncate provisions / truncate both staged tables / truncate membership / truncate release objects / delete derived rows / truncate a derived table / add a derived row]`, `test_released_rows_and_membership_refuse_truncate_for_every_release`; `test_truncate_still_clears_rows_no_release_signs` |
| 3. Client changes unlayered results; loses children under pagination | `762e9297` | `test_unlayered_children_are_the_parent_id_children_origin_main_returns` (Sol's case: HEAD returned `['fx/statute/1/1', 'fx/statute/1/2']`), `test_unlayered_children_with_a_path_in_two_scopes_match_origin_main`, `test_unlayered_children_equal_origin_main_on_any_served_rows`, `test_layered_children_page_through_the_row_cap` (1,000 instead of 1,300 before), `test_layered_children_page_before_keeping_one_per_path` (500 instead of 1,000 before), `test_layered_children_are_the_served_navigation_children`, `test_layered_children_follow_the_served_navigation_tree` |
| 4. Root-count baseline | Decision: served-only is the intended definition. The migration comment and docs say so; the no-base differential against #666 stays; production checked read-only (Deployment, item 4) (`a038b3bf`). | `test_root_counts_are_served_roots_not_every_stored_root`: installs `20260910120000`'s function verbatim and shows the two agree when only served roots are stored and differ by exactly the superseded and unreleased roots otherwise. It passes before and after, because the function did not change; it documents the difference. |
| 5. Deployment locking | The file no longer derives a served base layer. `rederive_layered_serving()` is its own step. `lock_timeout` is 2 s. Triggers use `CREATE OR REPLACE TRIGGER` (`SHARE ROW EXCLUSIVE`, not `ACCESS EXCLUSIVE`). | `test_applying_the_file_with_a_base_scope_served_leaves_the_derivation_to_its_own_step` (before: the file re-derived), `test_rederivation_takes_only_activation_locks_and_blocks_no_read`, `test_migration_is_rerunnable_and_rederivation_reproduces_the_state`, `test_applying_the_file_with_no_base_scope_served_empties_the_derived_state`, `test_rederivation_refreshes_served_counts_when_the_shadowed_rows_change` |
| 6. `ANALYZE` after derivation | `analyze_layered_serving()` after every derivation that changes the tables, including a pointer `TRUNCATE` | `test_derivation_analyzes_the_layered_tables` (before: `reltuples` stayed -1) |
| 7. Validation warning for unattached roots | `0587d7ab`, `88b95bf4` | `test_a_primary_root_under_no_served_ancestor_is_a_warning`, `test_a_new_title_warns_once_and_its_sections_attach_to_it`, `test_a_parent_cycle_between_the_layers_is_a_warning` (all three failed before); `test_primary_roots_the_merge_attaches_raise_no_warning`, `test_new_documents_of_a_flat_class_warn_once_per_scope_after_the_errors`, `test_releases_without_a_base_scope_get_no_layered_warning` |
| 8. Label parity (optional) | Blank headings use `str.strip()`'s character set. | `test_a_blank_heading_follows_its_segment_as_navigation_py_does`, `test_sql_heading_blankness_equals_python_strip`. The arbitrary-parents property, now drawing blank-Unicode headings, found the mismatch on the old code. |

**What the in-session reviews changed.**
- **SQL review (REQUEST_CHANGES).** It found three problems:
  - One statement could delete a served release's object and re-insert it, because foreign keys are checked only at the end of the statement. That hid the object from the row-time guards: membership could be deleted, an unsigned scope added, and a released navigation row removed (the last through the old `20260710180000` guard).
  - The per-row signed-scope check cost 6.0 s for a 761-scope object, and 6.1 s for a re-activation that inserts nothing. It now costs 14 ms and 5 ms.
  - A `REPEATABLE READ` pointer write racing a restoring insert could leave the derived state stale.

  All three are fixed in `88b95bf4`.
- **Python review (APPROVE).** It asked for the warning order and the per-scope warnings, also in `88b95bf4`.
- **Verification pass (APPROVE).** It confirmed the fixes and raised three small points, fixed in `db2c81c7`: compare the stored object as text, take the pointer lock in a direct `refresh_layered_serving` call, and correct the guard comment.

**Deliberately not changed**
- **Citation labels.** Staged rows do not keep a provision's `citation_label`. So where the merge moves a node that has no heading and whose citation label equals its old segment, the served label follows the new segment, while `build_navigation_nodes` would keep the citation label. This is documented, and it is the only known label difference.
- **Served counts.** `current_provision_counts` follows activation, and `rederive_layered_serving()` when the shadowed provisions change. A pointer moved by hand, or membership restored by re-activating the serving release, does not refresh it, as before this PR.
- **Owner bypass of the derived-table guard.** An owner who sets `corpus.layered_serving_derivation` or turns triggers off can still write the derived tables. The guard stops accidents; no API role has any write privilege on these tables.
- **No bound on the paging loop.** The client's paging loop has no iteration cap; PostgREST honours `offset`.

## Query plans at representative scale

`tests/test_layered_serving_postgres.py::test_serving_plans_stay_index_driven_at_representative_scale`:

- **What it builds:**
  - the May base layers' 306,923 `us` rows: 53 titles and 60,393 sections, plus 49 titles, 4,900 parts and 241,528 sections;
  - 48 primary `us` scopes, half without their title or part row, colliding with 456 base paths;
  - stored `us` history and other jurisdictions.
- **Scale.** 401,299 provision rows per table in CI. `AXIOM_CORPUS_PLAN_SCALE=production` gives 1,521,299.
- **What it asserts.**
  - Both single-path lookups are index scans on `idx_provisions_citation_path_version`, with no sequential scan and no sort.
  - The `us` page is a Merge Append of ordered index scans.
  - New this round: the client's children page reads `navigation_nodes` by index.

Results at this head with `AXIOM_CORPUS_PLAN_SCALE=production` (1,521,299 rows per table), on local PostgreSQL 14.24, run as `anon` under a 3 s statement timeout. The laptop was shared, with a load average of 11 to 17.

| Request | Execution |
|---|---|
| `current_provisions?citation_path=eq.us/statute/30/500` (base only) | 0.165 ms |
| `current_provisions?citation_path=eq.us/statute/3/1` (collision; primary served) | 0.093 ms |
| `current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000` | 4.8 ms |
| `current_navigation_nodes?…&parent_path=eq.us/statute/2&order=sort_key` (merged children) | 2.6 ms |
| The client's children page (`order=sort_key,path,id&limit=1000`) | 4.3 ms |
| `rpc/get_root_document_counts` | 23.5 ms |
| `navigation_nodes?…&parent_path=eq.us/statute/3` (direct anon read, policy) | 1.05 ms |
| Deriving the layered state when the release is served (all pairs, with `ANALYZE`) | 7.3 s (6.9 s at 401,299 rows) |
| `rederive_layered_serving()` at 401,299 rows | 2.9 s |

The previous run reported 14.9 s and 28.2 s for the derivation under heavier load. With no base scope active, the new views were as fast as or faster than the previous definitions on the same data in the previous round's measurement (`us` page 37 ms vs 237 ms; root counts 11 ms vs 25 ms).

<details><summary>EXPLAIN (ANALYZE, BUFFERS): base-only single-path lookup</summary>

```
Nested Loop Anti Join  (cost=1.12..54.90 rows=4 width=719) (actual time=0.097..0.141 rows=1 loops=1)
  Buffers: shared hit=48 read=13
  ->  Nested Loop Semi Join  (cost=0.85..38.72 rows=4 width=719) (actual time=0.095..0.139 rows=1 loops=1)
        Buffers: shared hit=46 read=13
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.15 rows=4 width=719) (actual time=0.022..0.052 rows=11 loops=1)
              Index Cond: (citation_path = 'us/statute/30/500'::text)
              Buffers: shared hit=1 read=13
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.007..0.007 rows=0 loops=11)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 23
              Buffers: shared hit=45
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=11)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=22
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.004..0.005 rows=23 loops=11)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=23
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=1)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=30
Planning Time: 0.415 ms
Execution Time: 0.165 ms
```

</details>

<details><summary>EXPLAIN (ANALYZE, BUFFERS): collision single-path lookup</summary>

```
Nested Loop Anti Join  (cost=1.12..54.90 rows=4 width=719) (actual time=0.066..0.067 rows=1 loops=1)
  Buffers: shared hit=20 read=4
  ->  Nested Loop Semi Join  (cost=0.85..38.72 rows=4 width=719) (actual time=0.045..0.061 rows=2 loops=1)
        Buffers: shared hit=15 read=4
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.15 rows=4 width=719) (actual time=0.022..0.032 rows=3 loops=1)
              Index Cond: (citation_path = 'us/statute/3/1'::text)
              Buffers: shared hit=2 read=4
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.009..0.009 rows=1 loops=3)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 9
              Buffers: shared hit=13
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.002..0.002 rows=1 loops=3)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=6
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.004..0.005 rows=10 loops=3)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=7
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.002..0.002 rows=0 loops=2)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=5
Planning:
  Buffers: shared hit=30
Planning Time: 0.423 ms
Execution Time: 0.093 ms
```

</details>

<details><summary>EXPLAIN (ANALYZE, BUFFERS): us page of current_navigation_nodes</summary>

```
Limit  (cost=48.01..27179.25 rows=1000 width=48) (actual time=2.558..4.677 rows=1000 loops=1)
  Buffers: shared hit=1083 read=262
  ->  Merge Append  (cost=48.01..6449142.58 rows=237700 width=48) (actual time=2.557..4.623 rows=1000 loops=1)
        Sort Key: n.citation_path
        Buffers: shared hit=1083 read=262
        ->  Index Scan using idx_navigation_nodes_jurisdiction_citation_path on navigation_nodes n  (cost=47.72..6444963.78 rows=226864 width=47) (actual time=2.543..4.401 rows=699 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 310
              Buffers: shared hit=792 read=262
              SubPlan 1
                ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.055..0.166 rows=250 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=10
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.004..0.041 rows=490 loops=1)
                            Buffers: shared hit=6
                      ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.047..0.048 rows=202 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 20kB
                            Buffers: shared hit=4
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.018 rows=202 loops=1)
                                  Buffers: shared hit=4
              SubPlan 2
                ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.021..0.097 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 402
                      Buffers: shared hit=6
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.006..0.016 rows=202 loops=1)
                            Buffers: shared hit=4
                      ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                            Buffers: shared hit=2
                            ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.006..0.006 rows=2 loops=1)
                                  Heap Fetches: 0
                                  Buffers: shared hit=2
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.003..0.045 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.011..0.650 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=101
        ->  Index Scan using idx_layered_navigation_overrides_citation_path on layered_navigation_overrides o  (cost=0.29..1801.79 rows=10836 width=66) (actual time=0.013..0.133 rows=302 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Buffers: shared hit=291
Planning:
  Buffers: shared hit=8
Planning Time: 0.511 ms
Execution Time: 4.754 ms
```

</details>

The client's children page plan is an index scan on `navigation_nodes`, which the scale test asserts; set `AXIOM_CORPUS_PLAN_REPORT=<file>` to write every plan.

Round 2 rewrote `get_root_document_counts()` to name `navigation_nodes` first (finding 4). At 401,299 rows it returned the same rows as before, and its body still reads roots through `idx_navigation_nodes_roots_by_scope_version` with no sequential scan on `navigation_nodes` (5.0 ms against 6.9 ms, measured by a round-2 reviewer). The scale test ran it in 6.5 ms as `anon`.

## Deployment

1. **Merging this PR changes what two workflows apply.** `.github/workflows/publish.yml:112` and `.github/workflows/register-release-object.yml:121` run `scripts/apply_release_object_staging_migration.py`. From the next run, that script applies `20260927100000_stage_signed_release_object_v4.sql` instead of `20260803175000`.
   - It contains only the registration function.
   - v2 and v3 objects register exactly as before.
   - The insert trigger stays as `20260803175000` installed it.
   - `publish.yml:111`, `register-release-object.yml:120` and `activate-release.yml:193` still apply `20260722021000` only, through `scripts/apply_release_activation_upload_migration.py`; that is unchanged.
2. **No workflow applies `20260927110000_layered_release_serving.sql`.** Until it is applied, the production activation RPC (`20260719043000`) rejects every v4 object, so registering a v4 object is harmless. Apply it by hand, as `postgres`, with human approval, at a time of low traffic, before the first layered activation (PR 5):
   1. Build the two `navigation_nodes` indexes with `CREATE INDEX CONCURRENTLY IF NOT EXISTS` and the exact definitions in section 1 of the file. Confirm `pg_index.indisvalid` for both.
   2. Apply the file in one transaction, with no publication or activation running: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction -f supabase/migrations/20260927110000_layered_release_serving.sql`. Without `--single-transaction`, psql commits each statement separately and neither the lock order nor the roll-back on failure holds.
      - **Locks, in order.**
        - A transaction advisory lock, so a second application waits for the first.
        - `SHARE` on `navigation_nodes` (section 1's index statements).
        - `SHARE ROW EXCLUSIVE`, which writes wait for and reads do not, on `provisions`, `navigation_nodes`, `release_objects`, `release_scopes`, `active_scope_pointer` and, when re-applied, the derived tables. A write in progress therefore delays the file before it blocks any read.
        - `ACCESS EXCLUSIVE` on `current_provisions`, `legacy_provisions`, `current_navigation_nodes`, `navigation_nodes`, `current_release_scopes` and `release_scopes`, in the order serving reads take their locks. The first time it also holds the two derived tables it creates, which no read can reach yet.

        After that it waits for no lock a read or a row write can hold. Measured in `pg_locks` and pinned by `test_the_file_takes_access_exclusive_only_where_it_orders_it`.
      - **What a concurrent read sees.** A read that got its locks before the file got the one it needs runs on the old definitions, and the file waits for it. A read that needs a relation the file holds, or is queued for, waits for the commit and then runs on the new definitions. A single-statement read and the file never deadlock. A read can still reach its own statement timeout (3 s for anon) if the file waits up to 2 s on each of several locks while the read queues behind the ones it holds.
      - **Duration.** The file does no derivation work. One-off local measurements on PostgreSQL 14:
        - an earlier revision, re-applied to an otherwise idle copy of 401,299 rows per table with its indexes built, took 8 ms;
        - the current file, applied 20 times to the small test fixture on a busy machine, took a median of 12 ms re-applied and 92 ms the first time, which creates the derived tables and indexes.
      - **Timeout.** It sets `lock_timeout` to 2 s, which caps each lock wait. A failed run (a timeout or any other error) rolls back whole and changes nothing; run it again at a quieter moment.
   3. **The first time.** No base scope is served: the file empties the derived tables, and every view returns what it returned before.
   4. **Later applications.** When a base scope is served, for example re-applying the file after a layered activation, the file prints a notice and leaves the derived state as the triggers kept it. Then run `SELECT corpus.rederive_layered_serving();` as its own transaction, under `READ COMMITTED`.
      - **Locks.** It takes only locks activation takes: `EXCLUSIVE` on `active_scope_pointer`, which blocks activations and pointer writes but not reads, plus row writes and `ANALYZE` on the two derived tables.
      - **Counts.** Only when the shadowed provisions change does it refresh `current_provision_counts`, as activation does.
      - **Reads.** Serving reads see the previous state until it commits.
3. **Owner-level writes change as soon as the file is applied, for every release.** The new guards reject what the owner could do before:
   - updating, deleting or truncating release membership;
   - inserting membership that is not a signed scope;
   - changing a signed release object other than its `created_at`, or deleting one that has membership;
   - truncating released rows;
   - writing the derived tables;
   - under `REPEATABLE READ` or `SERIALIZABLE`: moving a pair to or from a release with a base scope for it, inserting such a release's membership for that pair, and any `TRUNCATE` of the pointers, membership or released rows. Releases without a base scope keep every isolation level.

   No code in this repository sets an isolation level (`git grep`). The direct activation path uses psycopg2 autocommit (`src/axiom_corpus/corpus/supabase.py:1176-1180`), and the management-API path uses the server default. I did not check production's `default_transaction_isolation`.
4. **Root counts.**
   - **Against the repository's migration history, the result changes.** This repository last defined `get_root_document_counts()` in `20260910120000`, which counts every stored root, superseded and never-released versions included. This one counts served roots only.
   - **Against production, it does not change while no base scope is served.** I checked read-only on 2026-10-05 at 07:45 UTC, using GET requests with the public anon key:
     - **Equal everywhere.** The RPC returned 469 `(jurisdiction, doc_type)` pairs and 35,252 roots. For all 469 pairs, the count equals `count=exact` of `current_navigation_nodes?parent_path=is.null` for that pair, for example `us/statute` 373 and `us/regulation` 110.
     - **Unserved versions exist.** For 41 of those pairs, 167 versions are no longer served although one of the 31 releases recorded in `scope_activation_history` signed them (`us/statute` 9, `us/regulation` 2). I read the signed scopes from `release_objects` and the served versions from `current_release_scopes`.
     - **So production is not running `20260910120000`.** The released rows of those versions are immutable (`guard_released_scope_row_immutable`). Activation required each version to have navigation rows, and a non-empty scope's navigation always has a root. So `20260910120000` would return at least 167 more roots across those pairs. Production's output equals the served-only count that #666 defines.
     - **Not verified:** I could not read the function body, because anon cannot read the catalog. The first RPC call returned a transient HTTP 500 and was retried.
   - **#666 is superseded by this PR.**
5. **Prerequisite outside this repo.** Before the first layered activation, axiom.org must read its navigation tree from `current_navigation_nodes`. A direct `navigation_nodes` read hides shadowed rows but returns the stored per-scope tree fields. On axiom.org `master` (`src/lib/axiom/navigation-index/read.ts`, `section-page.ts`, `coverage-page.ts`) the tree reads `navigation_nodes` directly. There, a primary section that leaves its title to the base would show as a top-level document and be missing from its title's children.

## Deviations from the plan and the brief, and why

- **The previous lane's serving design was replaced.** Its views tested every base row against served primary rows with a correlated probe inside one EXISTS, and kept a separate summaries table for child counts. That made the planner sort every stored `us` navigation row for a page. It also left a primary root of its own scope as a root of the merged tree, although its title is in the base. The derived shadow and override tables restore indexed plans and place such nodes in the base tree.
- **Brief contract item 3 (parent resolution in validation sees both layers) is not done as written.** Parent closure stays per scope, as `169dbb46` ("Require parent closure within each immutable release scope") made it, because Supabase derives a row's `parent_id` from the parent's path and the row's own version, so a parent only the base carries cannot satisfy it. Cross-layer parenting happens in serving. This round adds the cross-layer view as warnings: validation now merges each layered pair's trees as serving does. `test_parent_closure_stays_per_scope_across_layers` pins the per-scope rule.
- **The previous lane's SQL check against base/primary overlaps across pairs was dropped.** Serving resolves precedence per pair, so such an overlap cannot make serving ambiguous. Release validation still rejects it.
- **The same-layer ambiguity check runs only for layered pairs.** Running it for every pair would cost a full GROUP BY over a large release. An unlayered pair keeps its previous behaviour; validation rejects duplicates in new releases.
- **The owner-level write guards apply to every release, not only layered ones** (Deployment, item 3). Membership and released rows were already treated as immutable by the existing code (`20260718193000`'s comment, the released-row trigger); the guards make that hold at statement level.
- **The `.github/workflows/ci.yml` postgres job's pytest line adds `tests/test_layered_serving_postgres.py`.** No action or toolchain pins changed.

## Not verified, known limits, follow-ups

- **Production state.** Nothing was run against production except the read-only anon GETs above (the root counts and the shape of `current_release_scopes`). Live function definitions were not inspected.
- **PostgreSQL 15.** Locally only PostgreSQL 14 was available. `test_merge_into_membership_meets_the_same_guards` (MERGE needs 15) is skipped locally and runs in CI's postgres job, which also runs every two-session test on 15.
- **Supabase and the no-op owner change.** How Supabase's own hooks react to `ALTER VIEW … OWNER TO <its owner>` was not checked; it changes no catalog row locally.
- **The July row guard under an old snapshot** stays as it is; see "Review round 2", flagged items.
- **Activation duration.** The time of a real layered activation through the activation workflow has to be measured in PR 5, as the plan already requires.
- **Placement of new eCFR sections.** Staged rows keep no declared parent path, only a versioned parent id. So a primary root that the base does not carry goes under its nearest served path prefix, even if it declares a non-prefix parent. A newly added eCFR section absent from the May base lands under its part rather than its subpart. No text is wrong.
- **Repealed base sections stay served.** Precedence is per path, so a primary re-encoding of a section cannot retire a base descendant it no longer has.
- **Activation gate.** `scripts/check_release_gate.py` compares scope triples only and does not compare layers. That is PR 4 work.

## Tests

Commands at `affd452a` (the head), with local PostgreSQL 14 for the database modules. The machine was heavily loaded (load average 15 to 90, from other sessions), so the database modules were run in parts:

```text
$ git ls-files -z -- '*.py' ':!data' | xargs -0 uv run --extra dev ruff check
All checks passed!
$ uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports
Success: no issues found in 98 source files
$ uv run --extra dev towncrier check --compare-with origin/main
Found:
1. …/changelog.d/layered-release-serving.added.md
$ AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev python -m pytest -q tests/test_query_supabase.py
32 passed in 17.12s
$ DATABASE_URL=… uv run --extra dev python -m pytest -q tests/test_layered_serving_postgres.py -k "not representative_scale"
152 passed, 3 skipped, 1 deselected in 209.22s
$ DATABASE_URL=… uv run --extra dev python -m pytest -q tests/test_atomic_release_postgres.py
92 passed in 214.04s
$ DATABASE_URL=… uv run --extra dev python -m pytest -q tests/test_layered_serving_postgres.py -k representative_scale
1 passed, 155 deselected in 300.08s
```

The three skips are the MERGE test (PostgreSQL 15) and the two write-in-progress cases on derived tables, which do not exist before a first application. `ruff format --check` flags `src/axiom_corpus/query/supabase.py` for a block that is the same on `origin/main`; CI does not run it.

**CI on the head `affd452a`: every check passes** (run 37331315035; `gh pr checks` exits 0, GitHub reports MERGEABLE). `test (3.14)`, the full suite on the full corpus: `5215 passed, 309 skipped, 208 deselected`. `postgres` (PostgreSQL 15): both modules `246 passed, 2 skipped` (the two derived-table cases of a first application; the MERGE test runs on 15), ops queue `24 passed`. Selector validation, citation-path grammar and workflow validation pass.

## Callers of modified functions

GitNexus was not used. Callers come from `git grep`:

- `_release_citation_paths`: `release_quality.py` (`validate_release`). `_LayeredScopeParents` is new and used only there.
- `navigation._resolve_parent_path` now delegates to the new `_resolve_parent`; its caller is `build_navigation_nodes_from_sources`. `scope_parent_paths` and `merge_layered_parent_paths` are new, called from `release_quality.py` and tests.
- `get_section_with_children`: `src/axiom_corpus/cli.py:1952`, `query/supabase.py` (`get_section_deep`, `get_by_citation`). The new helpers `_serves_base_layer`, `_navigation_children` and `_all_rows` are called only from `_direct_children`; round 2 changed `_serves_base_layer` (now calls `_all_rows`).
- SQL, round 2: `corpus.release_layers_pair` and `corpus.pair_has_derived_rows` (new) are called only by `sync_layered_serving`; `corpus.guard_truncate_reads_committed_state` (new) by the three `TRUNCATE` triggers; `refresh_layered_serving` by `sync_layered_serving`, `sync_layered_serving_membership`, `rederive_layered_serving` and owners.
- `selector_sha256`, `build_release_content`, `build_unsigned_release_object`, `sign_release_object`, `_validate_unsigned_release_object`, `_validate_scope_entries`, `_parse_scope`: unchanged this round (see the previous description).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

