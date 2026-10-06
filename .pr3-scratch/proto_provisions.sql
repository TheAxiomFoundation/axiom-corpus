CREATE OR REPLACE VIEW corpus.current_provisions AS
SELECT p.*
FROM corpus.provisions p
WHERE EXISTS (
  SELECT 1 FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version
    AND s.layer = 'primary')
UNION ALL
SELECT p.*
FROM corpus.provisions p
WHERE EXISTS (
  SELECT 1 FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version
    AND s.layer = 'base')
  AND NOT EXISTS (
    SELECT 1
    FROM corpus.provisions q
    JOIN corpus.current_release_scopes ps
      ON ps.jurisdiction = q.jurisdiction
     AND ps.document_class = COALESCE(NULLIF(q.doc_type, ''), 'unknown')
     AND ps.version = q.version
    WHERE q.citation_path = p.citation_path
      AND q.version IS NOT NULL
      AND q.jurisdiction = p.jurisdiction
      AND ps.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
      AND ps.layer = 'primary');
