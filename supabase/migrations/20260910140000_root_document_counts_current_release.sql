-- Count root documents from the current release only.
--
-- get_root_document_counts() (20260910120000) counted every stored version
-- of each root row, while anon readers see only the current release through
-- the navigation_nodes RLS policy. The coverage page switched to the function
-- and read 98,406 source documents against 9,913 visible ones. Count from
-- corpus.current_navigation_nodes, the same visibility get_navigation_node_counts()
-- uses, so the function agrees with what the page's per-jurisdiction reads see.
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
  FROM corpus.current_navigation_nodes
  WHERE parent_path IS NULL
    AND jurisdiction IS NOT NULL
  GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown')
  ORDER BY jurisdiction, doc_type
$$;
GRANT EXECUTE ON FUNCTION corpus.get_root_document_counts() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION corpus.get_root_document_counts() TO postgres, service_role;
NOTIFY pgrst, 'reload schema';
