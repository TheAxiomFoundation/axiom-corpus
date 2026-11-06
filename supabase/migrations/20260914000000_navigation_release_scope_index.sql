-- Let a per-jurisdiction page of corpus.current_navigation_nodes answer within
-- the anon statement timeout.
--
-- The view keeps every navigation row whose (jurisdiction, document_class,
-- version) has an active scope in corpus.current_release_scopes (the
-- per-(jurisdiction, document_class) serving map, 20260718193000). Consumers
-- page it one jurisdiction at a time, ordered by citation_path. On 2026-09-13
-- the `us` page (14,369 visible rows over 48 active scopes) took 3.1 s and was
-- cancelled by the 3 s anon statement timeout on every page; a 100-row page
-- took 1.4 s and `get_root_document_counts()` 2.1 s. Smaller jurisdictions
-- answer in 0.25 s.
--
-- Cause: navigation_nodes keeps every version a release ever carried (immutable
-- releases, 20260710180000), so `us` holds many superseded rows for each
-- visible one. The only indexes that lead with (jurisdiction, doc_type,
-- version) cannot serve the view's scope test, because the view and the RLS
-- policy compare `s.document_class = COALESCE(NULLIF(n.doc_type, ''),
-- 'unknown')`, and an index on the bare `doc_type` column does not match that
-- expression. The planner therefore reads every `us` row of every version from
-- the heap, hash-joins the 48 scopes, sorts the survivors by citation_path and
-- takes the page; the cost is the total row count of the jurisdiction, not its
-- visible count, and it is paid again on every page.
--
-- Fix: an index keyed exactly like the scope test, mirroring
-- idx_provisions_release_scope_version on corpus.provisions (20260513140000).
-- With it the planner drives from the active scopes of the jurisdiction and
-- range-scans only the visible rows of each scope; INCLUDE carries the columns
-- the paging consumers select so the scan never touches the heap. On a
-- production-shaped local load (1.5M rows, `us` 400k rows / 14.4k visible /
-- 48 scopes) the consumer's `us` page went from 937 ms to 21 ms, a deep page
-- from 997 ms to 31 ms, and an unfiltered global page from 1,534 ms to 302 ms;
-- see docs/ingest-runs/2026-09-14-navigation-view-timeout.md.
--
-- The view, policy and serving map are unchanged: visibility still follows
-- corpus.active_scope_pointer exactly, and activation needs no refresh step.
--
-- Apply to the live database with CONCURRENTLY (outside a transaction, so not
-- through `supabase db push`) to avoid blocking staging writes while the
-- ~3M-row index builds; the same name makes this file a no-op afterwards.
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_release_scope_version
  ON corpus.navigation_nodes (
    jurisdiction,
    (COALESCE(NULLIF(doc_type, ''), 'unknown')),
    version
  )
  INCLUDE (citation_path, has_children, child_count, has_rulespec);

COMMENT ON INDEX corpus.idx_navigation_nodes_release_scope_version IS
  'Scope test of current_navigation_nodes and the navigation_nodes RLS '
  'policies: (jurisdiction, document_class expression, version), covering '
  'the columns per-jurisdiction paging consumers select.';

ANALYZE corpus.navigation_nodes;
