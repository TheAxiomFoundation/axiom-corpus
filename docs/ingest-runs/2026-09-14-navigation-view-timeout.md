# `corpus.current_navigation_nodes` per-jurisdiction page: statement timeout

Date: 2026-09-13 (measured), migration dated 2026-09-14
Branch: `fix/navigation-view-timeout`
Migration: `supabase/migrations/20260914000000_navigation_release_scope_index.sql`
Consumer: `axiom-encode-economics` branch `fix/nav-paging` (snapshot paging)

GitNexus impact analysis was not run: the GitNexus MCP tools were not available in this
session. No function was modified in either repository's Python; the corpus change is
one index, the economics change is confined to `Rest.rows`, `snapshot_corpus_nav`,
`take_snapshot` (meta) and the CLI header.

## Symptom

The economics snapshot reads what is ingested from the public view
`corpus.current_navigation_nodes`, one jurisdiction per request, 1,000 rows a page,
ordered by `citation_path`. The `us` page hit Supabase's statement timeout once in the
2026-09-11 snapshot and on every request on 2026-09-13. Until the view answers nothing
downstream can read what the day's release (`us-rulespec-2026-09-11-program-ingestion-
union`, 536 scopes, 54 of them `us`) published.

## Live measurements, anon role, 2026-09-13 (before the fix)

Read through the economics repo's own anon-key configuration; nothing but the anon role
was used and no key was written anywhere. Visible rows: 132,563 over 221 jurisdictions;
`us` 14,369 rows over 48 active scopes; `us-il` 14,150; `nz` 11,774; `us-ar` 1,033.

| Request (`select=` the consumer's seven columns) | Status | Latency |
|---|---|---|
| `jurisdiction=eq.us&order=citation_path.asc&limit=1000&offset=0` (consumer's exact page 1) | 500 `57014` | 3.08 s (cancelled) |
| same, `offset=20000` (past the end; 0 rows) | 200 | 1.61 s |
| same, `limit=100` | 200 | 1.38 s |
| `jurisdiction=eq.us&limit=1000` (no order) | 200 | 1.98 s |
| `jurisdiction=eq.us&order=path.asc&limit=1000` (`path` is indexed) | 500 `57014` | 3.09 s (cancelled) |
| `jurisdiction=eq.us-ar&order=citation_path.asc&limit=1000` | 200 | 0.25 s |
| `rpc/get_root_document_counts` (roots through the same view) | 200 | 2.11 s |
| `rpc/get_navigation_node_counts` (whole base table) | 500 `57014` | 3.19 s (cancelled) |

The anon statement timeout is 3 s. The cost does not depend on the rows returned (a page
past the end costs 1.6 s), nor on the order (unordered is 2 s), but on the jurisdiction:
`us-ar` is 12x faster than `us` for a similar page.

## Cause

`corpus.navigation_nodes` keeps every version a release ever carried (immutable releases,
`20260710180000`), so `us` holds many superseded rows for each visible one (on 2026-09-10,
#666: 8,912 `us` roots stored against 410 visible). The view keeps a row when

```sql
EXISTS (SELECT 1 FROM corpus.current_release_scopes s
        WHERE s.jurisdiction = n.jurisdiction
          AND s.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
          AND s.version = n.version)
```

`current_release_scopes` itself is cheap: a join of `release_scopes` (hundreds of rows)
with `active_scope_pointer` (one row per served pair), 48 rows for `us`. The planner does
want to drive the query from those 48 scopes and probe the navigation table per scope,
but the only index leading with `(jurisdiction, doc_type, version)` is on the bare
`doc_type` column, which does not match the `COALESCE(NULLIF(doc_type, ''), 'unknown')`
expression in the scope test. It therefore probes `idx_navigation_nodes_scope_version_
parent_sort` on `(jurisdiction, version)` alone, fetches every `us` row of that version
from the heap, and filters `doc_type` afterwards; the sort by `citation_path` and the
`LIMIT` come last. The cost is the jurisdiction's total row count across versions, paid
again on every page, and it grows with every release even though the visible set does
not. Exactly the same expression is why `idx_provisions_release_scope_version` on
`corpus.provisions` was built on the expression (`20260513140000`); the navigation table
never got the matching index.

Two things checked and ruled out. The RLS policy on `navigation_nodes` repeats the scope
test, but the view is not `security_invoker`, so a read through the view runs as the view
owner and the policy is not evaluated a second time (the local plan shows one scope join).
And `path`, the one indexed sort column, does not help either: ordering by it still needs
every `us` row filtered first (3.09 s live).

## Fix

One index keyed exactly like the scope test, covering the columns paging consumers select:

```sql
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_release_scope_version
  ON corpus.navigation_nodes (jurisdiction, (COALESCE(NULLIF(doc_type, ''), 'unknown')), version)
  INCLUDE (citation_path, has_children, child_count, has_rulespec);
```

The view, the policy, `current_release_scopes` and `active_scope_pointer` are untouched,
so visibility still follows the per-`(jurisdiction, document_class)` map exactly and
activation needs no refresh step (`tests/test_navigation_view_page_postgres.py` repoints a
pair and checks the page follows). No RPC was added: the view itself is fast with the
index, and a `SECURITY DEFINER` pager would have to re-implement the scope test.

## Local verification (PostgreSQL 15.14, the CI recipe's image, Docker)

Schema: the production definitions of `navigation_nodes` with all eight current indexes,
`release_scopes`, `release_objects`, `active_scope_pointer`, `current_release_scopes`,
`current_navigation_nodes` and the `anon_read` policy. Load shaped like production:
1,526,956 rows, 154,496 visible over 219 jurisdictions; `us` = 400,100 rows of which
14,400 are visible over 48 active scopes (5 document classes, 380 superseded version
scopes). Heap 442 MB, existing indexes 650 MB.

Consumer query as `anon`, `EXPLAIN (ANALYZE, BUFFERS)`, warm cache:

| Query | Before | Expression index (this migration) | `(jurisdiction, citation_path) INCLUDE (...)` for comparison |
|---|---|---|---|
| `us` page 1 | 937 ms | **21 ms** | 913 ms |
| `us` deep page (offset 13,000) | 997 ms | **31 ms** | 887 ms |
| `us` past the end (offset 20,000) | 991 ms | **30 ms** | 880 ms |
| `j-001` (small) page 1 | 4.9 ms | 0.9 ms | 1.8 ms |
| `us` no order | 81 ms | 0.5 ms | 85 ms |
| `us` order by `path` | 941 ms | 17 ms | 865 ms |
| global, no jurisdiction filter, page 1 | 1,534 ms | 302 ms | 2,542 ms |
| direct base-table read as anon (RLS policy) | 652 ms | 517 ms | 12 ms |

Before (top of the plan): 310,181 buffers hit; `Bitmap Index Scan on
idx_navigation_nodes_scope_version_parent_sort, Index Cond: (jurisdiction = 'us' AND
version = scopes.version)` then `Filter: (scopes.document_class = COALESCE(NULLIF(doc_type,
''), 'unknown'))` on the heap, 48 loops, 14,400 rows out of the join, sort, limit.

After: 922 buffers hit; `Bitmap Index Scan on idx_navigation_nodes_release_scope_version,
Index Cond: (jurisdiction = 'us' AND COALESCE(NULLIF(doc_type, ''), 'unknown') =
scopes.document_class AND version = scopes.version)`, 48 loops of 300 rows, sort, limit.
The scan touches only visible rows, so the page costs the visible count of the jurisdiction
(14k rows, 21 ms) instead of its total (400k rows, 937 ms), and it no longer grows as
superseded versions accumulate.

The ordered-scan alternative `(jurisdiction, citation_path) INCLUDE (doc_type, version,
...)` was measured and rejected: the planner does not use it for the view (913 ms) because
the semi-join still has to test every `us` row; it only speeds up the direct base-table
read, which is not the consumer's path. The RLS policy on a direct `navigation_nodes` read
is a hashed sub-plan filter, not a join, so the new index does not change that path
(652 -> 517 ms); consumers should keep reading the view.

Index build on the 1.53M-row local table: 4.4 s, 135 MB (the largest existing index, `idx_navigation_nodes_scope_version_parent_sort`, is 214 MB there); expect a minute or so on production's larger table over the pooler. Applying the migration
twice is a no-op (`IF NOT EXISTS`).

## Apply to production (maintainer)

CI does not apply migrations to the live database. Following #666, apply the SQL first,
then merge this PR so the repository records it. In the Supabase SQL editor (runs as
`postgres`, outside a transaction), one statement at a time:

```sql
SET statement_timeout = 0;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_navigation_nodes_release_scope_version
  ON corpus.navigation_nodes (jurisdiction, (COALESCE(NULLIF(doc_type, ''), 'unknown')), version)
  INCLUDE (citation_path, has_children, child_count, has_rulespec);
ANALYZE corpus.navigation_nodes;
COMMENT ON INDEX corpus.idx_navigation_nodes_release_scope_version IS
  'Scope test of current_navigation_nodes and the navigation_nodes RLS policies: (jurisdiction, document_class expression, version), covering the columns per-jurisdiction paging consumers select.';
```

`CONCURRENTLY` keeps staging loads (today's release publish) unblocked while the index
builds; it cannot run inside a transaction, so it is not what the migration file says.
The file uses the same index name with `IF NOT EXISTS`, so a later `supabase db push` is a
no-op. Check `SELECT indisvalid FROM pg_index WHERE indexrelid =
'corpus.idx_navigation_nodes_release_scope_version'::regclass;` is `true` (a cancelled
concurrent build leaves an invalid index that must be dropped and rebuilt).

Verify with the consumer's request as anon:
`/rest/v1/current_navigation_nodes?select=jurisdiction,doc_type,citation_path,has_children,child_count,has_rulespec,version&jurisdiction=eq.us&order=citation_path.asc&limit=1000`
should answer well under a second (21 ms local for 14k visible rows; the live `us-ar` page,
which never had the problem, takes 0.25 s end to end).

## Consumer change (axiom-encode-economics `fix/nav-paging`)

`Rest.rows` retries a page once on `57014`, then halves the page size at the same offset
down to 50 rows, and raises `PageTimeout(offset)` only when the smallest page still times
out. `snapshot_corpus_nav` orders by `citation_path.asc,version.asc` (unique per row, so
offset pages cannot overlap when ties are re-sorted) and starts jurisdictions with 10,000
or more visible rows at 500-row pages.

Shrinking the page is not enough for `us` today: run live on 2026-09-13 with the new
reader, `us-ar` answered in 0.4 s but every `us` attempt from 500 rows down to 50 rows was
cancelled at 3 s (31 s spent), because the cost is the jurisdiction's stored history, not
the rows returned. So on a persistent timeout the reader fetches the jurisdiction one
active scope at a time: it reads `current_release_scopes` for the jurisdiction (48 rows for
`us`, 0.13 s) and pages the view with `jurisdiction=eq.us&doc_type=eq.<class>&version=
eq.<version>`. Those three filters let the existing index
`idx_navigation_nodes_scope_version_parent_sort (jurisdiction, doc_type, version, ...)`
find one scope's rows without touching the superseded history (local plan without the new
index: `Index Cond: (jurisdiction = 'us' AND doc_type = 'statute' AND version = ...)`,
2.2 ms), and the union over the jurisdiction's active scopes is the view's row set by
definition. Live: **all 14,369 `us` rows in 5.3 s over 48 scope pages, worst scope
0.37 s** (`policy/2026-07-05-cms-chip-fcep-spa`, 2,347 rows, 0.36 s). A jurisdiction
that times out even per scope is left out of `corpus_nav.json`, recorded in
`meta.sources.corpus_nav_missing_jurisdictions`, and the rest of the snapshot is kept;
`meta.sources.corpus_nav_paged_by_scope` records which jurisdictions needed the fallback,
and the CLI header prints `CORPUS NAV INCOMPLETE: <jurisdictions>` when rows are absent.
Results are identical when the view answers normally (one request per 1,000 rows, same
rows, same order within a jurisdiction). No RPC is preferred because none was added.

The per-scope shape also explains why the index is the right database fix: it is the same
`(jurisdiction, document_class, version)` lookup, done inside the planner for all 48
scopes at once, with the `COALESCE` expression the view actually uses.

## Live measurements after the fix

Not yet taken: the index is applied by a maintainer, not by this branch. Re-run the
requests in the table above as anon after applying and record them here.
