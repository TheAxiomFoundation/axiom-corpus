-- Let get_root_document_counts() run as an index-only scan.
--
-- The function (20260910140000) counts roots through corpus.current_navigation_nodes,
-- whose visibility rule reads `version`. The partial index from 20260910120000
-- covers (jurisdiction, doc_type) only, so every root row is fetched from the heap
-- to read its version: 2 to 9 seconds per call on 2026-09-10, which trips the
-- statement timeout under the coverage page's render. Include `version` so the
-- scan never leaves the index.
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_roots_by_scope_version
  ON corpus.navigation_nodes (jurisdiction, doc_type, version)
  WHERE parent_path IS NULL;

DROP INDEX IF EXISTS corpus.idx_navigation_nodes_roots_by_jurisdiction;
