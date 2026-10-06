DROP VIEW IF EXISTS corpus.current_navigation_nodes;
CREATE VIEW corpus.current_navigation_nodes AS
SELECT
  served.id, served.jurisdiction, served.doc_type, served.path, served.parent_path,
  served.segment, served.label, served.sort_key, served.depth, served.provision_id,
  served.citation_path, served.has_children, served.child_count, served.has_rulespec,
  served.encoded_descendant_count, served.status, served.created_at, served.updated_at,
  served.version
FROM (
  SELECT n.id, n.jurisdiction, n.doc_type, n.path, n.parent_path, n.segment, n.label,
         n.sort_key, n.depth, n.provision_id, n.citation_path, n.has_children,
         n.child_count, n.has_rulespec, n.encoded_descendant_count, n.status,
         n.created_at, n.updated_at, n.version, false AS merged
  FROM corpus.navigation_nodes n
  UNION ALL
  SELECT o.id, o.jurisdiction, o.doc_type, o.path, o.parent_path, o.segment, o.label,
         o.sort_key, o.depth, o.provision_id, o.citation_path, o.has_children,
         o.child_count, o.has_rulespec, o.encoded_descendant_count, o.status,
         o.created_at, o.updated_at, o.version, true AS merged
  FROM corpus.layered_navigation_overrides o
) served
WHERE EXISTS (
    SELECT 1 FROM corpus.current_release_scopes s
    WHERE s.jurisdiction = served.jurisdiction
      AND s.document_class = COALESCE(NULLIF(served.doc_type, ''), 'unknown')
      AND s.version = served.version)
  AND (
    served.merged
    OR (
      served.id NOT IN (
        SELECT shadowed.navigation_id FROM corpus.layered_shadowed_rows shadowed
        WHERE shadowed.navigation_id IS NOT NULL)
      AND (
        (served.jurisdiction, COALESCE(NULLIF(served.doc_type, ''), 'unknown'))
          NOT IN (SELECT shadowed.jurisdiction, shadowed.document_class FROM corpus.layered_shadowed_rows shadowed)
        OR NOT EXISTS (SELECT 1 FROM corpus.layered_navigation_overrides o WHERE o.id = served.id)
      )
    )
  );
GRANT SELECT ON corpus.current_navigation_nodes TO anon, authenticated;
CREATE INDEX IF NOT EXISTS idx_layered_navigation_overrides_release_scope_version ON corpus.layered_navigation_overrides (jurisdiction, (COALESCE(NULLIF(doc_type, ''), 'unknown')), version) INCLUDE (citation_path, has_children, child_count, has_rulespec);
ANALYZE corpus.layered_navigation_overrides;
