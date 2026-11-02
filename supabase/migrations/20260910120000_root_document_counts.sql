-- Root-document counts per jurisdiction and document type, for the public
-- coverage census.
--
-- The coverage page on axiom.org counts "source documents" as the roots of
-- `corpus.navigation_nodes` (parent_path IS NULL). It fetched them one
-- jurisdiction at a time, paging 1,000 rows per request and ordering by
-- path; the two largest jurisdictions (us, us-il) take several seconds per
-- page through PostgREST and time out under the page's fan-out, and the page
-- counts a failed jurisdiction as zero. The published figure fell from
-- 9,913 to 4,569 on 2026-09-10 while the corpus was unchanged.
--
-- A partial index makes the root lookup cheap, and one grouped RPC replaces
-- ~200 paged queries with a single call. `get_navigation_node_counts()`
-- already exists but groups the whole table and times out.
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_roots_by_jurisdiction
  ON corpus.navigation_nodes (jurisdiction, doc_type)
  WHERE parent_path IS NULL;

CREATE OR REPLACE FUNCTION corpus.get_root_document_counts()
RETURNS TABLE (
  jurisdiction text,
  doc_type text,
  document_count bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = corpus, public
AS $$
  SELECT
    jurisdiction,
    COALESCE(NULLIF(doc_type, ''), 'unknown') AS doc_type,
    COUNT(*)::bigint AS document_count
  FROM corpus.navigation_nodes
  WHERE parent_path IS NULL
    AND jurisdiction IS NOT NULL
  GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown')
  ORDER BY jurisdiction, doc_type
$$;
GRANT EXECUTE ON FUNCTION corpus.get_root_document_counts() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION corpus.get_root_document_counts() TO postgres, service_role;
NOTIFY pgrst, 'reload schema';
