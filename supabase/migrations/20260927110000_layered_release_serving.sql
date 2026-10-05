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

-- ---------------------------------------------------------------------------
-- 8. Activation accepts release-object/v4 and installs signed layers.
--
-- Every check of 20260719043000 is kept verbatim for v2 and v3 (schema,
-- profile, name, sha, signature, scope-array shape, duplicate scopes, SHARE
-- locks, per-scope staged count and projection-digest recheck, immutable
-- object, membership equality, per-pair pointer movement, history, count
-- refresh). New: v4 acceptance and layer rules, a v4-only ambiguity check,
-- the layer in stored membership and in both membership comparisons, and
-- merged navigation summaries for each newly activated layered pair. Any
-- failure raises and rolls the whole activation back.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION corpus.activate_corpus_release(p_release_object jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
SET statement_timeout = 0
SET lock_timeout = 0
AS $$
DECLARE
  v_release_name text;
  v_content_sha text;
  scope jsonb;
  pair record;
  expected_rows bigint;
  actual_rows bigint;
  expected_navigation_rows bigint;
  actual_navigation_rows bigint;
  expected_provision_projection_sha256 text;
  actual_provision_projection_sha256 text;
  expected_navigation_projection_sha256 text;
  actual_navigation_projection_sha256 text;
  existing_sha text;
  existing_object jsonb;
  prev_release_name text;
  prev_content_sha text;
  v_scope_count integer;
  v_schema text;
  v_ambiguous_path text;
  activated_scopes jsonb := '[]'::jsonb;
  reaffirmed_scopes jsonb := '[]'::jsonb;
BEGIN
  v_schema := COALESCE(p_release_object ->> 'schema_version', '');
  IF v_schema NOT IN (
    'axiom-corpus/release-object/v2',
    'axiom-corpus/release-object/v3',
    'axiom-corpus/release-object/v4'
  ) THEN
    RAISE EXCEPTION 'unsupported corpus release object schema';
  END IF;
  IF v_schema IN (
    'axiom-corpus/release-object/v3',
    'axiom-corpus/release-object/v4'
  ) THEN
    IF p_release_object #>> '{content,quality_profile}'
       IS DISTINCT FROM 'complete-expression-dates-v1' THEN
      RAISE EXCEPTION 'profiled corpus release has an unsupported quality profile';
    END IF;
    IF p_release_object #>> '{content,validation,quality_profile}'
       IS DISTINCT FROM p_release_object #>> '{content,quality_profile}' THEN
      RAISE EXCEPTION 'corpus release validation quality profile does not match signed content';
    END IF;
  END IF;
  v_release_name := p_release_object ->> 'release';
  v_content_sha := p_release_object ->> 'content_sha256';
  IF v_release_name IS NULL
     OR v_release_name = 'current'
     OR char_length(v_release_name) > 128
     OR v_release_name !~ '^[a-z0-9]+(-[a-z0-9]+)*$' THEN
    RAISE EXCEPTION 'invalid immutable corpus release name: %', v_release_name;
  END IF;
  IF v_content_sha IS NULL OR v_content_sha !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid corpus release content sha256';
  END IF;
  IF p_release_object #>> '{content,release}' IS DISTINCT FROM v_release_name THEN
    RAISE EXCEPTION 'corpus release name does not match signed content';
  END IF;
  IF COALESCE((p_release_object #>> '{content,validation,passed}')::boolean, false)
     IS NOT TRUE THEN
    RAISE EXCEPTION 'corpus release does not attest passed validation';
  END IF;
  IF p_release_object #>> '{signature,algorithm}' IS DISTINCT FROM 'ed25519'
     OR p_release_object #>> '{signature,key_id}'
        IS DISTINCT FROM 'axiom-corpus-release-v2'
     OR NULLIF(p_release_object #>> '{signature,value}', '') IS NULL THEN
    RAISE EXCEPTION 'corpus release object lacks an Ed25519 signature';
  END IF;

  IF jsonb_typeof(p_release_object #> '{content,scopes}') IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'corpus release scopes must be an array';
  END IF;
  v_scope_count := jsonb_array_length(p_release_object #> '{content,scopes}');
  IF v_scope_count IS NULL OR v_scope_count = 0 THEN
    RAISE EXCEPTION 'corpus release must contain at least one scope';
  END IF;
  IF (
    SELECT COUNT(*)
    FROM (
      SELECT
        value ->> 'jurisdiction',
        value ->> 'document_class',
        value ->> 'version'
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
      GROUP BY 1, 2, 3
    ) unique_scopes
  ) <> v_scope_count THEN
    RAISE EXCEPTION 'corpus release contains duplicate scopes';
  END IF;

  -- Layers are signed only in v4: a primary scope has no layer key and a base
  -- scope has exactly "base", at most one per (jurisdiction, document_class).
  -- A v2 or v3 object never carries a layer, so every historical release keeps
  -- its primary meaning.
  IF v_schema = 'axiom-corpus/release-object/v4' THEN
    IF EXISTS (
      SELECT 1
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
      WHERE scope.value ? 'layer'
        AND scope.value -> 'layer' IS DISTINCT FROM '"base"'::jsonb
    ) THEN
      RAISE EXCEPTION 'layered corpus release scope has an unsupported layer';
    END IF;
    IF NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
      WHERE scope.value ? 'layer'
    ) THEN
      RAISE EXCEPTION 'release-object/v4 is reserved for releases with a base scope';
    END IF;
    IF EXISTS (
      SELECT 1
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
      WHERE scope.value ? 'layer'
      GROUP BY scope.value ->> 'jurisdiction', scope.value ->> 'document_class'
      HAVING COUNT(*) > 1
    ) THEN
      RAISE EXCEPTION 'layered corpus release has more than one base scope for a pair';
    END IF;
  ELSIF EXISTS (
    SELECT 1
    FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
    WHERE scope.value ? 'layer'
  ) THEN
    RAISE EXCEPTION 'only release-object/v4 may sign scope layers';
  END IF;

  -- Freeze the staged base tables from the first exact count through release
  -- membership insertion, and serialize activations against each other so the
  -- per-pair read-then-repoint below cannot interleave (concurrent activations
  -- would otherwise record a wrong displaced occupant or mis-decide a reaffirm).
  -- EXCLUSIVE conflicts only with writers and other activations, never with the
  -- ACCESS SHARE that serving reads take, so serving is unaffected.
  LOCK TABLE corpus.provisions IN SHARE MODE;
  LOCK TABLE corpus.navigation_nodes IN SHARE MODE;
  LOCK TABLE corpus.active_scope_pointer IN EXCLUSIVE MODE;

  -- Recheck exact staged counts and projection digests inside the activation
  -- transaction. A mismatch prevents release-object insertion and any pointer
  -- movement.
  FOR scope IN
    SELECT value FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
  LOOP
    expected_rows := (scope ->> 'provision_rows')::bigint;
    expected_navigation_rows := (scope ->> 'navigation_rows')::bigint;
    expected_provision_projection_sha256 := scope ->> 'provision_projection_sha256';
    expected_navigation_projection_sha256 := scope ->> 'navigation_projection_sha256';
    IF expected_rows <= 0 OR expected_navigation_rows IS DISTINCT FROM expected_rows THEN
      RAISE EXCEPTION 'invalid expected row count for scope %', scope;
    END IF;
    IF expected_provision_projection_sha256 IS NULL
       OR expected_provision_projection_sha256 !~ '^[0-9a-f]{64}$'
       OR expected_navigation_projection_sha256 IS NULL
       OR expected_navigation_projection_sha256 !~ '^[0-9a-f]{64}$' THEN
      RAISE EXCEPTION 'invalid signed projection digest for scope %', scope;
    END IF;
    SELECT COUNT(*)::bigint INTO actual_rows
    FROM corpus.provisions provisions
    WHERE provisions.jurisdiction = scope ->> 'jurisdiction'
      AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown')
          = scope ->> 'document_class'
      AND provisions.version = scope ->> 'version';
    IF actual_rows <> expected_rows THEN
      RAISE EXCEPTION
        'staged row-count mismatch for %/%/%: expected %, got %',
        scope ->> 'jurisdiction',
        scope ->> 'document_class',
        scope ->> 'version',
        expected_rows,
        actual_rows;
    END IF;
    SELECT COUNT(*)::bigint INTO actual_navigation_rows
    FROM corpus.navigation_nodes navigation
    WHERE navigation.jurisdiction = scope ->> 'jurisdiction'
      AND COALESCE(NULLIF(navigation.doc_type, ''), 'unknown')
          = scope ->> 'document_class'
      AND navigation.version = scope ->> 'version';
    IF actual_navigation_rows <> expected_navigation_rows THEN
      RAISE EXCEPTION
        'staged navigation-count mismatch for %/%/%: expected %, got %',
        scope ->> 'jurisdiction',
        scope ->> 'document_class',
        scope ->> 'version',
        expected_navigation_rows,
        actual_navigation_rows;
    END IF;
    actual_provision_projection_sha256 := corpus.provision_projection_sha256(
      scope ->> 'jurisdiction',
      scope ->> 'document_class',
      scope ->> 'version'
    );
    IF actual_provision_projection_sha256
       IS DISTINCT FROM expected_provision_projection_sha256 THEN
      RAISE EXCEPTION
        'staged provision projection digest mismatch for %/%/%',
        scope ->> 'jurisdiction',
        scope ->> 'document_class',
        scope ->> 'version';
    END IF;
    actual_navigation_projection_sha256 := corpus.navigation_projection_sha256(
      scope ->> 'jurisdiction',
      scope ->> 'document_class',
      scope ->> 'version'
    );
    IF actual_navigation_projection_sha256
       IS DISTINCT FROM expected_navigation_projection_sha256 THEN
      RAISE EXCEPTION
        'staged navigation projection digest mismatch for %/%/%',
        scope ->> 'jurisdiction',
        scope ->> 'document_class',
        scope ->> 'version';
    END IF;
  END LOOP;

  -- A layered release must leave serving unambiguous: within each layer a
  -- citation path belongs to one scope of the release, and a base row can be
  -- shadowed only by a primary row of its own pair. The counts and digests
  -- above already pinned these staged rows to the signed projections.
  IF v_schema = 'axiom-corpus/release-object/v4' THEN
    SELECT duplicated.citation_path
    INTO v_ambiguous_path
    FROM (
      SELECT
        COALESCE(scope.value ->> 'layer', 'primary') AS layer,
        provisions.citation_path
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
      JOIN corpus.provisions provisions
        ON provisions.jurisdiction = scope.value ->> 'jurisdiction'
       AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown')
           = scope.value ->> 'document_class'
       AND provisions.version = scope.value ->> 'version'
      GROUP BY 1, 2
      HAVING COUNT(*) > 1
      ORDER BY 2, 1
      LIMIT 1
    ) duplicated;
    IF v_ambiguous_path IS NOT NULL THEN
      RAISE EXCEPTION
        'layered corpus release has ambiguous same-layer citation ownership: %',
        v_ambiguous_path;
    END IF;

    WITH release_rows AS (
      SELECT
        COALESCE(scope.value ->> 'layer', 'primary') AS layer,
        provisions.jurisdiction,
        scope.value ->> 'document_class' AS document_class,
        provisions.citation_path
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
      JOIN corpus.provisions provisions
        ON provisions.jurisdiction = scope.value ->> 'jurisdiction'
       AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown')
           = scope.value ->> 'document_class'
       AND provisions.version = scope.value ->> 'version'
    )
    SELECT base_rows.citation_path
    INTO v_ambiguous_path
    FROM release_rows base_rows
    JOIN release_rows primary_rows
      ON primary_rows.citation_path = base_rows.citation_path
     AND primary_rows.layer = 'primary'
    WHERE base_rows.layer = 'base'
      AND (primary_rows.jurisdiction, primary_rows.document_class)
          IS DISTINCT FROM (base_rows.jurisdiction, base_rows.document_class)
    ORDER BY 1
    LIMIT 1;
    IF v_ambiguous_path IS NOT NULL THEN
      RAISE EXCEPTION
        'layered corpus release shadows a base row from another pair: %',
        v_ambiguous_path;
    END IF;
  END IF;

  SELECT objects.content_sha256, objects.release_object
  INTO existing_sha, existing_object
  FROM corpus.release_objects objects
  WHERE objects.release_name = v_release_name;
  IF existing_sha IS NOT NULL AND existing_sha <> v_content_sha THEN
    RAISE EXCEPTION 'immutable corpus release name already exists with another digest';
  END IF;
  IF existing_object IS NOT NULL AND existing_object IS DISTINCT FROM p_release_object THEN
    RAISE EXCEPTION 'immutable corpus release name already exists with another object';
  END IF;

  INSERT INTO corpus.release_objects (release_name, content_sha256, release_object)
  VALUES (v_release_name, v_content_sha, p_release_object)
  ON CONFLICT (release_name) DO NOTHING;

  INSERT INTO corpus.release_scopes (
    release_name,
    jurisdiction,
    document_class,
    version,
    layer,
    synced_at
  )
  SELECT
    v_release_name,
    value ->> 'jurisdiction',
    value ->> 'document_class',
    value ->> 'version',
    COALESCE(value ->> 'layer', 'primary'),
    now()
  FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
  ON CONFLICT (release_name, jurisdiction, document_class, version) DO NOTHING;

  IF EXISTS (
    (
      SELECT
        scopes.jurisdiction,
        scopes.document_class,
        scopes.version,
        scopes.layer
      FROM corpus.release_scopes scopes
      WHERE scopes.release_name = v_release_name
      EXCEPT
      SELECT
        value ->> 'jurisdiction',
        value ->> 'document_class',
        value ->> 'version',
        COALESCE(value ->> 'layer', 'primary')
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
    )
    UNION ALL
    (
      SELECT
        value ->> 'jurisdiction',
        value ->> 'document_class',
        value ->> 'version',
        COALESCE(value ->> 'layer', 'primary')
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
      EXCEPT
      SELECT
        scopes.jurisdiction,
        scopes.document_class,
        scopes.version,
        scopes.layer
      FROM corpus.release_scopes scopes
      WHERE scopes.release_name = v_release_name
    )
  ) THEN
    RAISE EXCEPTION 'stored named-release membership differs from signed scopes';
  END IF;

  -- Per-pair activation. Repoint only the (jurisdiction, document_class) pairs
  -- this release carries (deduped across its versions), in deterministic order.
  -- Every other pair keeps its current release, so an activation is never a
  -- global cutover. Idempotent per pair: reaffirming a pair already served by
  -- this release writes nothing. The EXCLUSIVE lock above makes the
  -- read-then-upsert per pair race-free.
  FOR pair IN
    SELECT DISTINCT
      value ->> 'jurisdiction' AS jurisdiction,
      value ->> 'document_class' AS document_class
    FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
    ORDER BY 1, 2
  LOOP
    SELECT active.release_name, active.content_sha256
    INTO prev_release_name, prev_content_sha
    FROM corpus.active_scope_pointer active
    WHERE active.jurisdiction = pair.jurisdiction
      AND active.document_class = pair.document_class;

    IF prev_release_name IS NOT DISTINCT FROM v_release_name
       AND prev_content_sha IS NOT DISTINCT FROM v_content_sha THEN
      reaffirmed_scopes := reaffirmed_scopes || jsonb_build_object(
        'jurisdiction', pair.jurisdiction,
        'document_class', pair.document_class
      );
      CONTINUE;
    END IF;

    INSERT INTO corpus.active_scope_pointer (
      jurisdiction, document_class, release_name, content_sha256, activated_at
    ) VALUES (
      pair.jurisdiction,
      pair.document_class,
      v_release_name,
      v_content_sha,
      now()
    )
    ON CONFLICT (jurisdiction, document_class) DO UPDATE SET
      release_name = EXCLUDED.release_name,
      content_sha256 = EXCLUDED.content_sha256,
      activated_at = EXCLUDED.activated_at;

    INSERT INTO corpus.scope_activation_history (
      jurisdiction, document_class, release_name, content_sha256,
      previous_release_name, previous_content_sha256
    ) VALUES (
      pair.jurisdiction,
      pair.document_class,
      v_release_name,
      v_content_sha,
      prev_release_name,
      prev_content_sha
    );

    activated_scopes := activated_scopes || jsonb_build_object(
      'jurisdiction', pair.jurisdiction,
      'document_class', pair.document_class,
      'displaced_release', prev_release_name
    );

    -- A pair this release serves with a base scope needs merged navigation
    -- summaries before the pointer move commits.
    IF EXISTS (
      SELECT 1
      FROM corpus.release_scopes scopes
      WHERE scopes.release_name = v_release_name
        AND scopes.jurisdiction = pair.jurisdiction
        AND scopes.document_class = pair.document_class
        AND scopes.layer = 'base'
    ) THEN
      PERFORM corpus.build_navigation_layer_summaries(
        v_release_name,
        v_content_sha,
        pair.jurisdiction,
        pair.document_class
      );
    END IF;
  END LOOP;

  -- A pure reaffirm (re-activating the exact release already serving every one
  -- of its pairs) changes no serving state, so it must touch nothing: no
  -- breadcrumb bump, no count refresh. This keeps an identical retry fully
  -- idempotent.
  IF activated_scopes <> '[]'::jsonb THEN
    -- Informational breadcrumb only: the most recently activated release. No view
    -- or policy reads this for serving anymore; serving follows
    -- active_scope_pointer. Kept so diagnostics and the release-object foreign key
    -- remain valid. Guarded so an unchanged breadcrumb is not rewritten.
    INSERT INTO corpus.active_release_pointer (
      pointer_name,
      release_name,
      content_sha256,
      activated_at
    ) VALUES ('production', v_release_name, v_content_sha, now())
    ON CONFLICT (pointer_name) DO UPDATE SET
      release_name = EXCLUDED.release_name,
      content_sha256 = EXCLUDED.content_sha256,
      activated_at = EXCLUDED.activated_at
    WHERE active_release_pointer.release_name IS DISTINCT FROM EXCLUDED.release_name
       OR active_release_pointer.content_sha256 IS DISTINCT FROM EXCLUDED.content_sha256;

    -- Non-concurrent refresh is intentional: it runs in this same transaction,
    -- so a count-refresh failure rolls the activation back.
    REFRESH MATERIALIZED VIEW corpus.current_provision_counts;
  END IF;

  RETURN jsonb_build_object(
    'release', v_release_name,
    'content_sha256', v_content_sha,
    'scope_count', v_scope_count,
    'active', true,
    'scopes', jsonb_build_object(
      'activated', activated_scopes,
      'reaffirmed', reaffirmed_scopes
    )
  );
END;
$$;

GRANT EXECUTE ON FUNCTION corpus.activate_corpus_release(jsonb)
  TO postgres;
REVOKE EXECUTE ON FUNCTION corpus.activate_corpus_release(jsonb)
  FROM anon, authenticated, service_role, PUBLIC;

NOTIFY pgrst, 'reload schema';
