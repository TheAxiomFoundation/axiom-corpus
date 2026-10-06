-- Layered release serving: a base scope served underneath primary scopes.
--
-- A release scope may be signed as a base scope ("layer": "base" in a
-- release-object/v4 scope; primary scopes carry no layer key). Within the one
-- release that serves a (jurisdiction, document_class) pair, a base row is
-- served only when no primary row of the same pair carries its citation path:
-- for a path both layers carry, serving picks the primary row regardless of
-- version dates or scope order. The base scope is published once, immutable,
-- and reused byte for byte by successors; a newly encoded primary section wins
-- over the base text the moment its release is activated.
--
-- Precedence is resolved per (jurisdiction, document_class) pair, the unit
-- serving is keyed by (active_scope_pointer), so activating one pair never
-- changes what another pair serves. Release validation keeps citation paths
-- unique within each layer and confines base/primary overlaps to one pair.
--
-- With no base scope active every view, policy, and count here returns exactly
-- the rows it returned before this migration (tests/test_layered_serving_postgres.py
-- compares each against the previous definitions). Every existing release_scopes
-- row becomes primary through the column default, so historical releases keep
-- their meaning and remain replayable.
--
-- NOT applied by any workflow. publish.yml, register-release-object.yml and
-- activate-release.yml re-apply only 20260722021000 and the registration RPC
-- (20260927100000). Apply this file deliberately, as postgres, before the first
-- layered release is activated. Every statement is re-runnable.

-- ---------------------------------------------------------------------------
-- 1. Signed layer on release membership. Historical rows default to primary.
-- ---------------------------------------------------------------------------
ALTER TABLE corpus.release_scopes
  ADD COLUMN IF NOT EXISTS layer text NOT NULL DEFAULT 'primary';
ALTER TABLE corpus.release_scopes
  DROP CONSTRAINT IF EXISTS release_scopes_layer_check;
ALTER TABLE corpus.release_scopes
  ADD CONSTRAINT release_scopes_layer_check CHECK (layer IN ('base', 'primary'));
CREATE UNIQUE INDEX IF NOT EXISTS release_scopes_one_base_per_pair
  ON corpus.release_scopes (release_name, jurisdiction, document_class)
  WHERE layer = 'base';

-- The active map names one release per pair; every version that release carries
-- for the pair is served, now with its layer (appended, column order kept).
CREATE OR REPLACE VIEW corpus.current_release_scopes AS
SELECT
  scopes.release_name,
  scopes.jurisdiction,
  scopes.document_class,
  scopes.version,
  scopes.synced_at,
  scopes.layer
FROM corpus.release_scopes scopes
JOIN corpus.active_scope_pointer active
  ON active.jurisdiction = scopes.jurisdiction
 AND active.document_class = scopes.document_class
 AND active.release_name = scopes.release_name;

-- ---------------------------------------------------------------------------
-- 2. Indexes for the winner test.
--
-- The single-path lookup and the primary-collision probe both use the existing
-- partial unique index idx_provisions_citation_path_version (citation_path,
-- version) WHERE version IS NOT NULL (20260710180000); navigation probes use
-- idx_navigation_nodes_path. The index below is keyed exactly like the
-- navigation scope test, so a per-jurisdiction page reads only served scopes
-- instead of every stored version (the same definition as open PR #699; either
-- migration makes the other a no-op).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_release_scope_version
  ON corpus.navigation_nodes (
    jurisdiction,
    (COALESCE(NULLIF(doc_type, ''), 'unknown')),
    version
  )
  INCLUDE (citation_path, has_children, child_count, has_rulespec);

-- ---------------------------------------------------------------------------
-- 3. Winner views over provisions.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW corpus.current_provisions AS
SELECT p.*
FROM corpus.provisions p
WHERE p.version IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM corpus.current_release_scopes s
    WHERE s.jurisdiction = p.jurisdiction
      AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
      AND s.version = p.version
      AND (
        s.layer = 'primary'
        OR NOT EXISTS (
          SELECT 1
          FROM corpus.provisions q
          JOIN corpus.current_release_scopes ps
            ON ps.jurisdiction = q.jurisdiction
           AND ps.document_class = COALESCE(NULLIF(q.doc_type, ''), 'unknown')
           AND ps.version = q.version
          WHERE q.citation_path = p.citation_path
            AND q.version IS NOT NULL
            AND q.jurisdiction = s.jurisdiction
            AND ps.document_class = s.document_class
            AND ps.layer = 'primary'
        )
      )
  );

-- Everything the winner view does not serve, including base rows shadowed by
-- a primary row. Service-only, as before.
CREATE OR REPLACE VIEW corpus.legacy_provisions AS
SELECT p.*
FROM corpus.provisions p
WHERE NOT EXISTS (
  SELECT 1
  FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version
    AND (
      s.layer = 'primary'
      OR NOT EXISTS (
        SELECT 1
        FROM corpus.provisions q
        JOIN corpus.current_release_scopes ps
          ON ps.jurisdiction = q.jurisdiction
         AND ps.document_class = COALESCE(NULLIF(q.doc_type, ''), 'unknown')
         AND ps.version = q.version
        WHERE q.citation_path = p.citation_path
          AND q.version IS NOT NULL
          AND q.jurisdiction = s.jurisdiction
          AND ps.document_class = s.document_class
          AND ps.layer = 'primary'
      )
    )
);

GRANT SELECT ON corpus.current_release_scopes TO anon, authenticated;
GRANT SELECT ON corpus.current_provisions TO anon, authenticated;
GRANT SELECT ON corpus.legacy_provisions TO postgres, service_role;

-- ---------------------------------------------------------------------------
-- 4. Merged navigation summaries.
--
-- Stored has_children, child_count and encoded_descendant_count are computed
-- per scope (build_navigation_nodes) and signed in the navigation projection,
-- so they cannot change. When a primary title overlays a base title, the
-- served title also has the base-only sections as children. Activation derives
-- the merged values for each layered pair from the signed staged rows and
-- stores only the nodes whose merged values differ from their stored ones,
-- keyed by release (the inputs are immutable, so the rows are too).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS corpus.navigation_layer_summaries (
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  jurisdiction text NOT NULL,
  document_class text NOT NULL,
  navigation_id text NOT NULL,
  has_children boolean NOT NULL,
  child_count integer NOT NULL CHECK (child_count >= 0),
  encoded_descendant_count integer NOT NULL CHECK (encoded_descendant_count >= 0),
  PRIMARY KEY (release_name, navigation_id),
  FOREIGN KEY (release_name, content_sha256)
    REFERENCES corpus.release_objects (release_name, content_sha256),
  CHECK (has_children = (child_count > 0))
);

ALTER TABLE corpus.navigation_layer_summaries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON corpus.navigation_layer_summaries FROM anon, authenticated, service_role, PUBLIC;
GRANT SELECT ON corpus.navigation_layer_summaries TO service_role;

CREATE OR REPLACE FUNCTION corpus.build_navigation_layer_summaries(
  p_release_name text,
  p_content_sha256 text,
  p_jurisdiction text,
  p_document_class text
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
SET statement_timeout = 0
AS $$
DECLARE
  v_rows integer;
BEGIN
  DELETE FROM corpus.navigation_layer_summaries summaries
  WHERE summaries.release_name = p_release_name
    AND summaries.jurisdiction = p_jurisdiction
    AND summaries.document_class = p_document_class;

  WITH RECURSIVE members AS (
    SELECT scopes.version, scopes.layer
    FROM corpus.release_scopes scopes
    WHERE scopes.release_name = p_release_name
      AND scopes.jurisdiction = p_jurisdiction
      AND scopes.document_class = p_document_class
  ),
  staged AS (
    SELECT
      navigation.id,
      navigation.path,
      navigation.parent_path,
      navigation.has_rulespec,
      navigation.has_children,
      navigation.child_count,
      navigation.encoded_descendant_count,
      members.layer
    FROM corpus.navigation_nodes navigation
    JOIN members ON members.version = navigation.version
    WHERE navigation.jurisdiction = p_jurisdiction
      AND COALESCE(NULLIF(navigation.doc_type, ''), 'unknown') = p_document_class
  ),
  winners AS (
    SELECT staged.*
    FROM staged
    WHERE staged.layer = 'primary'
       OR NOT EXISTS (
         SELECT 1
         FROM staged primary_node
         WHERE primary_node.layer = 'primary'
           AND primary_node.path = staged.path
       )
  ),
  children AS (
    SELECT winners.parent_path AS path, COUNT(*)::integer AS child_count
    FROM winners
    WHERE winners.parent_path IS NOT NULL
    GROUP BY winners.parent_path
  ),
  -- Each encoded served node counts once toward every strict ancestor, the
  -- same bottom-up sum build_navigation_nodes computes for one scope.
  ancestry AS (
    SELECT winners.parent_path AS path, 1 AS hops
    FROM winners
    WHERE winners.has_rulespec AND winners.parent_path IS NOT NULL
    UNION ALL
    SELECT winners.parent_path, ancestry.hops + 1
    FROM ancestry
    JOIN winners ON winners.path = ancestry.path
    WHERE winners.parent_path IS NOT NULL
      AND ancestry.hops < 10000
  ),
  encoded AS (
    SELECT ancestry.path, COUNT(*)::integer AS encoded_descendant_count
    FROM ancestry
    GROUP BY ancestry.path
  ),
  merged AS (
    SELECT
      winners.id,
      COALESCE(children.child_count, 0) AS child_count,
      COALESCE(encoded.encoded_descendant_count, 0) AS encoded_descendant_count,
      winners.has_children AS stored_has_children,
      winners.child_count AS stored_child_count,
      winners.encoded_descendant_count AS stored_encoded_descendant_count
    FROM winners
    LEFT JOIN children ON children.path = winners.path
    LEFT JOIN encoded ON encoded.path = winners.path
  )
  INSERT INTO corpus.navigation_layer_summaries (
    release_name,
    content_sha256,
    jurisdiction,
    document_class,
    navigation_id,
    has_children,
    child_count,
    encoded_descendant_count
  )
  SELECT
    p_release_name,
    p_content_sha256,
    p_jurisdiction,
    p_document_class,
    merged.id,
    merged.child_count > 0,
    merged.child_count,
    merged.encoded_descendant_count
  FROM merged
  WHERE (merged.child_count > 0, merged.child_count, merged.encoded_descendant_count)
        IS DISTINCT FROM (
          merged.stored_has_children,
          merged.stored_child_count,
          merged.stored_encoded_descendant_count
        );
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  RETURN v_rows;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.build_navigation_layer_summaries(text, text, text, text)
  FROM anon, authenticated, service_role, PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.build_navigation_layer_summaries(text, text, text, text)
  TO postgres;

-- ---------------------------------------------------------------------------
-- 5. Winner view over navigation. Same columns in the same order; the three
-- summary columns take the merged value where one was derived.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW corpus.current_navigation_nodes AS
SELECT
  n.id,
  n.jurisdiction,
  n.doc_type,
  n.path,
  n.parent_path,
  n.segment,
  n.label,
  n.sort_key,
  n.depth,
  n.provision_id,
  n.citation_path,
  COALESCE(summary.has_children, n.has_children) AS has_children,
  COALESCE(summary.child_count, n.child_count) AS child_count,
  n.has_rulespec,
  COALESCE(summary.encoded_descendant_count, n.encoded_descendant_count)
    AS encoded_descendant_count,
  n.status,
  n.created_at,
  n.updated_at,
  n.version
FROM corpus.navigation_nodes n
LEFT JOIN corpus.active_scope_pointer active
  ON active.jurisdiction = n.jurisdiction
 AND active.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
LEFT JOIN corpus.navigation_layer_summaries summary
  ON summary.release_name = active.release_name
 AND summary.navigation_id = n.id
WHERE n.version IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM corpus.current_release_scopes s
    WHERE s.jurisdiction = n.jurisdiction
      AND s.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
      AND s.version = n.version
      AND (
        s.layer = 'primary'
        OR NOT EXISTS (
          SELECT 1
          FROM corpus.navigation_nodes m
          JOIN corpus.current_release_scopes ps
            ON ps.jurisdiction = m.jurisdiction
           AND ps.document_class = COALESCE(NULLIF(m.doc_type, ''), 'unknown')
           AND ps.version = m.version
          WHERE m.path = n.path
            AND m.version IS NOT NULL
            AND m.jurisdiction = s.jurisdiction
            AND ps.document_class = s.document_class
            AND ps.layer = 'primary'
        )
      )
  );

GRANT SELECT ON corpus.current_navigation_nodes TO anon, authenticated;
GRANT SELECT ON corpus.current_navigation_nodes TO postgres, service_role;

-- ---------------------------------------------------------------------------
-- 6. Direct navigation_nodes reads follow the same winner rule. A policy on
-- navigation_nodes cannot select from navigation_nodes as the reader (that is
-- policy recursion), so the collision probe runs as the owner.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION corpus.navigation_path_has_served_primary(
  p_jurisdiction text,
  p_document_class text,
  p_path text
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = corpus, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM corpus.navigation_nodes m
    JOIN corpus.current_release_scopes ps
      ON ps.jurisdiction = m.jurisdiction
     AND ps.document_class = COALESCE(NULLIF(m.doc_type, ''), 'unknown')
     AND ps.version = m.version
    WHERE m.path = p_path
      AND m.version IS NOT NULL
      AND m.jurisdiction = p_jurisdiction
      AND ps.document_class = p_document_class
      AND ps.layer = 'primary'
  )
$$;

REVOKE EXECUTE ON FUNCTION corpus.navigation_path_has_served_primary(text, text, text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.navigation_path_has_served_primary(text, text, text)
  TO anon, authenticated, postgres, service_role;

DROP POLICY IF EXISTS anon_read ON corpus.navigation_nodes;
CREATE POLICY anon_read ON corpus.navigation_nodes
  FOR SELECT TO anon
  USING (
    EXISTS (
      SELECT 1
      FROM corpus.current_release_scopes s
      WHERE s.jurisdiction = navigation_nodes.jurisdiction
        AND s.document_class = COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown')
        AND s.version = navigation_nodes.version
        AND s.layer = 'primary'
    )
    OR (
      EXISTS (
        SELECT 1
        FROM corpus.current_release_scopes s
        WHERE s.jurisdiction = navigation_nodes.jurisdiction
          AND s.document_class = COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown')
          AND s.version = navigation_nodes.version
          AND s.layer = 'base'
      )
      AND NOT corpus.navigation_path_has_served_primary(
        navigation_nodes.jurisdiction,
        COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown'),
        navigation_nodes.path
      )
    )
  );

DROP POLICY IF EXISTS authenticated_read ON corpus.navigation_nodes;
CREATE POLICY authenticated_read ON corpus.navigation_nodes
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM corpus.current_release_scopes s
      WHERE s.jurisdiction = navigation_nodes.jurisdiction
        AND s.document_class = COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown')
        AND s.version = navigation_nodes.version
        AND s.layer = 'primary'
    )
    OR (
      EXISTS (
        SELECT 1
        FROM corpus.current_release_scopes s
        WHERE s.jurisdiction = navigation_nodes.jurisdiction
          AND s.document_class = COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown')
          AND s.version = navigation_nodes.version
          AND s.layer = 'base'
      )
      AND NOT corpus.navigation_path_has_served_primary(
        navigation_nodes.jurisdiction,
        COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown'),
        navigation_nodes.path
      )
    )
  );

-- ---------------------------------------------------------------------------
-- 7. Root-document counts from served winners.
--
-- Supersedes the definition proposed in open PR #666 (20260910140000, which
-- counts roots through current_navigation_nodes) and the table-wide count of
-- 20260910120000. With no base scope active it returns exactly what #666's
-- function returns.
-- ---------------------------------------------------------------------------
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
