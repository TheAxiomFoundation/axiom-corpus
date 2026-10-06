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
-- How: whenever a pair's serving release changes, a trigger on
-- active_scope_pointer records, in the same transaction, the base rows of that
-- release that a primary row shadows (layered_shadowed_rows) and the
-- navigation nodes whose tree fields differ once the two layers are merged
-- (layered_navigation_overrides). Both are derived from staged rows that are
-- immutable once released, and both are empty for every pair served without
-- a base scope. The serving views are the previous rules minus the shadowed
-- rows, plus the navigation overrides, so with no base scope active every
-- view, policy and function here returns exactly the rows it returned before
-- this migration (tests/test_layered_serving_postgres.py compares each against
-- the previous definitions). Every existing release_scopes row becomes primary
-- through the column default, so historical releases keep their meaning.
--
-- NOT applied by any workflow. publish.yml and register-release-object.yml
-- re-apply only 20260722021000 and the registration RPC (20260927100000), and
-- activate-release.yml only 20260722021000. Apply this file deliberately, as
-- postgres, before the first layered release is activated: until it is
-- applied, the activation RPC of 20260719043000 rejects every
-- release-object/v4 object. Every statement is re-runnable.

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

GRANT SELECT ON corpus.current_release_scopes TO anon, authenticated;

-- ---------------------------------------------------------------------------
-- 2. Navigation scope index.
--
-- Keyed exactly like the scope test of current_navigation_nodes and the
-- navigation_nodes policies, so a per-jurisdiction page reads only served
-- scopes instead of every stored version. The same definition as open PR #699;
-- either migration makes the other a no-op. Restoring a base scope multiplies
-- the rows a us page serves, so serving needs it.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_release_scope_version
  ON corpus.navigation_nodes (
    jurisdiction,
    (COALESCE(NULLIF(doc_type, ''), 'unknown')),
    version
  )
  INCLUDE (citation_path, has_children, child_count, has_rulespec);

-- ---------------------------------------------------------------------------
-- 3. Derived serving state for layered pairs.
-- ---------------------------------------------------------------------------

-- Base rows a primary row shadows, for the release that serves each pair.
-- One row per shadowed citation path, with the base provision and navigation
-- row ids the serving views and policies exclude.
CREATE TABLE IF NOT EXISTS corpus.layered_shadowed_rows (
  jurisdiction text NOT NULL,
  document_class text NOT NULL,
  citation_path text NOT NULL,
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  base_version text NOT NULL,
  provision_id uuid,
  navigation_id text,
  PRIMARY KEY (jurisdiction, document_class, citation_path),
  CHECK (provision_id IS NOT NULL OR navigation_id IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_layered_shadowed_rows_provision_id
  ON corpus.layered_shadowed_rows (provision_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_layered_shadowed_rows_navigation_id
  ON corpus.layered_shadowed_rows (navigation_id);

-- navigation_nodes rows are built per scope (build_navigation_nodes) and are
-- signed through the navigation projection, so their tree fields cannot
-- change. Merging a primary scope onto a base scope changes the tree, and this
-- table holds the merged row of every served node whose tree fields differ
-- from its stored ones, for the release that serves each layered pair.
--
-- The merged tree of one pair:
--   * served nodes: every node of the pair's primary scopes, and every node of
--     its base scope whose path no primary node carries;
--   * a primary node keeps the parent its own scope gave it. A primary node
--     that is a root of its scope takes the parent its base twin (the base node
--     with the same path) has, or, when the base does not carry its path, the
--     nearest ancestor path the pair serves, the rule build_navigation_nodes
--     applies to a node whose parent is missing. A base node keeps its parent:
--     that path is always served, by the base node or the primary node that
--     shadows it;
--   * a parent cycle (possible only when the two layers disagree about which
--     of two paths is the ancestor) is broken as build_navigation_nodes breaks
--     one: its smallest path becomes a root;
--   * depth, has_children, child_count and encoded_descendant_count are
--     recomputed over the merged tree; segment and sort_key are recomputed for
--     a node whose parent changed, and so is its label when the stored label
--     was the segment (build_navigation_nodes' fallback for a node without a
--     heading or citation label).
CREATE TABLE IF NOT EXISTS corpus.layered_navigation_overrides (
  LIKE corpus.navigation_nodes INCLUDING DEFAULTS,
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  document_class text NOT NULL,
  layer text NOT NULL CHECK (layer IN ('base', 'primary')),
  PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS idx_layered_navigation_overrides_pair
  ON corpus.layered_navigation_overrides (jurisdiction, document_class);
CREATE INDEX IF NOT EXISTS idx_layered_navigation_overrides_parent_sort
  ON corpus.layered_navigation_overrides (parent_path, sort_key);
CREATE INDEX IF NOT EXISTS idx_layered_navigation_overrides_path
  ON corpus.layered_navigation_overrides (path);

ALTER TABLE corpus.layered_shadowed_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE corpus.layered_navigation_overrides ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON corpus.layered_shadowed_rows, corpus.layered_navigation_overrides
  FROM anon, authenticated, service_role, PUBLIC;
GRANT SELECT ON corpus.layered_shadowed_rows, corpus.layered_navigation_overrides
  TO service_role;

-- The sort-key segment normalization of navigation._normalize_sort_segment:
-- lower-case, every run of digits left-padded with zeros to 12 characters
-- (longer runs unchanged). Citation path segments are ASCII
-- (schema/citation-path.v1.json), where lower() agrees with Python's.
CREATE OR REPLACE FUNCTION corpus.navigation_sort_segment(p_segment text)
RETURNS text
LANGUAGE sql
IMMUTABLE
STRICT
SET search_path = corpus, public
AS $$
  SELECT COALESCE(
    string_agg(
      CASE
        WHEN token.part[1] ~ '^[0-9]+$' AND length(token.part[1]) < 12
          THEN lpad(token.part[1], 12, '0')
        ELSE token.part[1]
      END,
      ''
      ORDER BY token.position
    ),
    ''
  )
  FROM regexp_matches(lower(p_segment), '([0-9]+|[^0-9]+)', 'g')
    WITH ORDINALITY AS token(part, position)
$$;

-- navigation._segment: the path relative to its parent, else its last component.
CREATE OR REPLACE FUNCTION corpus.navigation_segment(p_path text, p_parent_path text)
RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = corpus, public
AS $$
  SELECT CASE
    WHEN p_parent_path IS NOT NULL
      AND p_parent_path <> ''
      AND left(p_path, length(p_parent_path) + 1) = p_parent_path || '/'
      THEN substr(p_path, length(p_parent_path) + 2)
    WHEN strpos(p_path, '/') > 0 THEN regexp_replace(p_path, '^.*/', '')
    ELSE p_path
  END
$$;

-- Recompute one pair's derived state from the release that now serves it.
CREATE OR REPLACE FUNCTION corpus.refresh_layered_serving(
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
  v_release_name text;
  v_content_sha256 text;
  v_base_version text;
  v_shadowed integer;
  v_served integer;
  v_reached integer;
  v_broken integer;
BEGIN
  DELETE FROM corpus.layered_shadowed_rows shadowed
  WHERE shadowed.jurisdiction = p_jurisdiction
    AND shadowed.document_class = p_document_class;
  DELETE FROM corpus.layered_navigation_overrides overrides
  WHERE overrides.jurisdiction = p_jurisdiction
    AND overrides.document_class = p_document_class;

  SELECT active.release_name, active.content_sha256
  INTO v_release_name, v_content_sha256
  FROM corpus.active_scope_pointer active
  WHERE active.jurisdiction = p_jurisdiction
    AND active.document_class = p_document_class;
  IF NOT FOUND THEN
    RETURN 0;
  END IF;
  SELECT scopes.version
  INTO v_base_version
  FROM corpus.release_scopes scopes
  WHERE scopes.release_name = v_release_name
    AND scopes.jurisdiction = p_jurisdiction
    AND scopes.document_class = p_document_class
    AND scopes.layer = 'base';
  IF NOT FOUND THEN
    RETURN 0;
  END IF;

  -- Base rows whose path a primary row of the pair carries.
  WITH primary_scopes AS (
    SELECT scopes.version
    FROM corpus.release_scopes scopes
    WHERE scopes.release_name = v_release_name
      AND scopes.jurisdiction = p_jurisdiction
      AND scopes.document_class = p_document_class
      AND scopes.layer = 'primary'
  ),
  primary_paths AS (
    SELECT provisions.citation_path
    FROM primary_scopes
    JOIN corpus.provisions provisions
      ON provisions.jurisdiction = p_jurisdiction
     AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown') = p_document_class
     AND provisions.version = primary_scopes.version
    UNION
    SELECT navigation.path
    FROM primary_scopes
    JOIN corpus.navigation_nodes navigation
      ON navigation.jurisdiction = p_jurisdiction
     AND COALESCE(NULLIF(navigation.doc_type, ''), 'unknown') = p_document_class
     AND navigation.version = primary_scopes.version
  )
  INSERT INTO corpus.layered_shadowed_rows (
    jurisdiction,
    document_class,
    citation_path,
    release_name,
    content_sha256,
    base_version,
    provision_id,
    navigation_id
  )
  SELECT
    p_jurisdiction,
    p_document_class,
    primary_paths.citation_path,
    v_release_name,
    v_content_sha256,
    v_base_version,
    base_provision.id,
    base_navigation.id
  FROM primary_paths
  LEFT JOIN corpus.provisions base_provision
    ON base_provision.citation_path = primary_paths.citation_path
   AND base_provision.version = v_base_version
   AND base_provision.jurisdiction = p_jurisdiction
   AND COALESCE(NULLIF(base_provision.doc_type, ''), 'unknown') = p_document_class
  LEFT JOIN corpus.navigation_nodes base_navigation
    ON base_navigation.path = primary_paths.citation_path
   AND base_navigation.version = v_base_version
   AND base_navigation.jurisdiction = p_jurisdiction
   AND COALESCE(NULLIF(base_navigation.doc_type, ''), 'unknown') = p_document_class
  WHERE base_provision.id IS NOT NULL
     OR base_navigation.id IS NOT NULL;
  GET DIAGNOSTICS v_shadowed = ROW_COUNT;

  -- The merged tree, over the pair's served navigation nodes.
  DROP TABLE IF EXISTS pg_temp.layered_navigation_merge;
  CREATE TEMP TABLE layered_navigation_merge ON COMMIT DROP AS
  SELECT
    navigation.*,
    scopes.layer AS node_layer,
    twin.path IS NOT NULL AS has_twin,
    CASE
      WHEN scopes.layer = 'primary'
       AND navigation.parent_path IS NULL
       AND twin.path IS NOT NULL
        THEN twin.parent_path
      ELSE navigation.parent_path
    END AS merged_parent_path
  FROM corpus.release_scopes scopes
  JOIN corpus.navigation_nodes navigation
    ON navigation.jurisdiction = scopes.jurisdiction
   AND COALESCE(NULLIF(navigation.doc_type, ''), 'unknown') = scopes.document_class
   AND navigation.version = scopes.version
  LEFT JOIN corpus.navigation_nodes twin
    ON scopes.layer = 'primary'
   AND twin.path = navigation.path
   AND twin.version = v_base_version
   AND twin.jurisdiction = p_jurisdiction
   AND COALESCE(NULLIF(twin.doc_type, ''), 'unknown') = p_document_class
  WHERE scopes.release_name = v_release_name
    AND scopes.jurisdiction = p_jurisdiction
    AND scopes.document_class = p_document_class
    AND NOT EXISTS (
      SELECT 1
      FROM corpus.layered_shadowed_rows shadowed
      WHERE shadowed.navigation_id = navigation.id
    );
  CREATE UNIQUE INDEX ON layered_navigation_merge (path);
  CREATE INDEX ON layered_navigation_merge (merged_parent_path);
  ANALYZE layered_navigation_merge;
  SELECT COUNT(*)::integer INTO v_served FROM layered_navigation_merge;

  -- A root of a primary scope the base does not carry goes under the nearest
  -- served ancestor path.
  WITH targets AS (
    SELECT node.path, string_to_array(node.path, '/') AS parts
    FROM layered_navigation_merge node
    WHERE node.node_layer = 'primary'
      AND node.parent_path IS NULL
      AND NOT node.has_twin
  ),
  nearest AS (
    SELECT DISTINCT ON (targets.path)
      targets.path,
      ancestor.path AS ancestor_path
    FROM targets
    CROSS JOIN LATERAL generate_series(array_length(targets.parts, 1) - 1, 1, -1)
      AS prefix(size)
    JOIN layered_navigation_merge ancestor
      ON ancestor.path = array_to_string(targets.parts[1:prefix.size], '/')
    ORDER BY targets.path, prefix.size DESC
  )
  UPDATE layered_navigation_merge node
  SET merged_parent_path = nearest.ancestor_path
  FROM nearest
  WHERE node.path = nearest.path;

  -- Every node must hang from a root. One that no root reaches sits on, or
  -- under, a parent cycle: make the smallest path of every cycle a root, as
  -- build_navigation_nodes does, and look again.
  LOOP
    WITH RECURSIVE tree AS (
      SELECT node.path
      FROM layered_navigation_merge node
      WHERE node.merged_parent_path IS NULL
      UNION ALL
      SELECT child.path
      FROM tree
      JOIN layered_navigation_merge child ON child.merged_parent_path = tree.path
    )
    SELECT COUNT(*)::integer INTO v_reached FROM tree;
    EXIT WHEN v_reached = v_served;

    WITH RECURSIVE tree AS (
      SELECT node.path
      FROM layered_navigation_merge node
      WHERE node.merged_parent_path IS NULL
      UNION ALL
      SELECT child.path
      FROM tree
      JOIN layered_navigation_merge child ON child.merged_parent_path = tree.path
    ),
    walk AS (
      SELECT node.merged_parent_path AS cursor, ARRAY[node.path] AS chain
      FROM layered_navigation_merge node
      WHERE NOT EXISTS (SELECT 1 FROM tree WHERE tree.path = node.path)
      UNION ALL
      SELECT parent.merged_parent_path, walk.chain || parent.path
      FROM walk
      JOIN layered_navigation_merge parent ON parent.path = walk.cursor
      WHERE NOT parent.path = ANY (walk.chain)
    ),
    -- A walk whose next step returns into its own chain closed a cycle: the
    -- cycle is the chain from that path on.
    cycles AS (
      SELECT DISTINCT (
        SELECT min(member)
        FROM unnest(walk.chain[array_position(walk.chain, walk.cursor):]) AS member
      ) AS smallest
      FROM walk
      WHERE walk.cursor = ANY (walk.chain)
    )
    UPDATE layered_navigation_merge node
    SET merged_parent_path = NULL
    FROM cycles
    WHERE node.path = cycles.smallest;
    GET DIAGNOSTICS v_broken = ROW_COUNT;
    IF v_broken = 0 THEN
      RAISE EXCEPTION 'layered navigation for %/% in % leaves % of % nodes unreachable',
        p_jurisdiction, p_document_class, v_release_name, v_served - v_reached, v_served;
    END IF;
  END LOOP;

  WITH RECURSIVE tree AS (
    SELECT node.path, 0 AS depth
    FROM layered_navigation_merge node
    WHERE node.merged_parent_path IS NULL
    UNION ALL
    SELECT child.path, tree.depth + 1
    FROM tree
    JOIN layered_navigation_merge child ON child.merged_parent_path = tree.path
  ),
  children AS (
    SELECT node.merged_parent_path AS path, COUNT(*)::integer AS child_count
    FROM layered_navigation_merge node
    WHERE node.merged_parent_path IS NOT NULL
    GROUP BY node.merged_parent_path
  ),
  -- Each encoded node counts once toward every strict ancestor, the
  -- bottom-up sum build_navigation_nodes computes for one scope.
  up AS (
    SELECT node.merged_parent_path AS path
    FROM layered_navigation_merge node
    WHERE node.has_rulespec AND node.merged_parent_path IS NOT NULL
    UNION ALL
    SELECT parent.merged_parent_path
    FROM up
    JOIN layered_navigation_merge parent ON parent.path = up.path
    WHERE parent.merged_parent_path IS NOT NULL
  ),
  encoded AS (
    SELECT up.path, COUNT(*)::integer AS encoded_descendant_count
    FROM up
    GROUP BY up.path
  ),
  derived AS (
    SELECT
      node.*,
      tree.depth AS merged_depth,
      CASE
        WHEN node.merged_parent_path IS DISTINCT FROM node.parent_path
          THEN corpus.navigation_segment(node.path, node.merged_parent_path)
        ELSE node.segment
      END AS merged_segment,
      COALESCE(children.child_count, 0) AS merged_child_count,
      COALESCE(encoded.encoded_descendant_count, 0) AS merged_encoded_descendant_count
    FROM layered_navigation_merge node
    JOIN tree ON tree.path = node.path
    LEFT JOIN children ON children.path = node.path
    LEFT JOIN encoded ON encoded.path = node.path
  ),
  merged AS (
    SELECT
      derived.*,
      CASE
        WHEN derived.merged_segment IS DISTINCT FROM derived.segment
         AND derived.label = derived.segment
          THEN derived.merged_segment
        ELSE derived.label
      END AS merged_label,
      CASE
        WHEN derived.merged_segment IS DISTINCT FROM derived.segment
          THEN split_part(derived.sort_key, '|', 1) || '|'
            || corpus.navigation_sort_segment(derived.merged_segment)
        ELSE derived.sort_key
      END AS merged_sort_key
    FROM derived
  )
  INSERT INTO corpus.layered_navigation_overrides (
    id,
    jurisdiction,
    doc_type,
    path,
    parent_path,
    segment,
    label,
    sort_key,
    depth,
    provision_id,
    citation_path,
    has_children,
    child_count,
    has_rulespec,
    encoded_descendant_count,
    status,
    created_at,
    updated_at,
    version,
    release_name,
    content_sha256,
    document_class,
    layer
  )
  SELECT
    merged.id,
    merged.jurisdiction,
    merged.doc_type,
    merged.path,
    merged.merged_parent_path,
    merged.merged_segment,
    merged.merged_label,
    merged.merged_sort_key,
    merged.merged_depth,
    merged.provision_id,
    merged.citation_path,
    merged.merged_child_count > 0,
    merged.merged_child_count,
    merged.has_rulespec,
    merged.merged_encoded_descendant_count,
    merged.status,
    merged.created_at,
    merged.updated_at,
    merged.version,
    v_release_name,
    v_content_sha256,
    p_document_class,
    merged.node_layer
  FROM merged
  WHERE (
    merged.merged_parent_path,
    merged.merged_segment,
    merged.merged_label,
    merged.merged_sort_key,
    merged.merged_depth,
    merged.merged_child_count > 0,
    merged.merged_child_count,
    merged.merged_encoded_descendant_count
  ) IS DISTINCT FROM (
    merged.parent_path,
    merged.segment,
    merged.label,
    merged.sort_key,
    merged.depth,
    merged.has_children,
    merged.child_count,
    merged.encoded_descendant_count
  );
  DROP TABLE layered_navigation_merge;
  RETURN v_shadowed;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.refresh_layered_serving(text, text)
  FROM anon, authenticated, service_role, PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.refresh_layered_serving(text, text) TO postgres;

-- Keep the derived state in step with active_scope_pointer in the same
-- transaction as every pointer move, whoever makes it: activation, a
-- maintenance repoint, or a removal.
CREATE OR REPLACE FUNCTION corpus.sync_layered_serving()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
BEGIN
  IF TG_OP = 'TRUNCATE' THEN
    DELETE FROM corpus.layered_shadowed_rows;
    DELETE FROM corpus.layered_navigation_overrides;
    RETURN NULL;
  END IF;
  IF TG_OP = 'DELETE'
     OR (
       TG_OP = 'UPDATE'
       AND (OLD.jurisdiction, OLD.document_class)
           IS DISTINCT FROM (NEW.jurisdiction, NEW.document_class)
     ) THEN
    PERFORM corpus.refresh_layered_serving(OLD.jurisdiction, OLD.document_class);
  END IF;
  IF TG_OP = 'INSERT'
     OR (
       TG_OP = 'UPDATE'
       AND (OLD.jurisdiction, OLD.document_class, OLD.release_name, OLD.content_sha256)
           IS DISTINCT FROM
           (NEW.jurisdiction, NEW.document_class, NEW.release_name, NEW.content_sha256)
     ) THEN
    PERFORM corpus.refresh_layered_serving(NEW.jurisdiction, NEW.document_class);
  END IF;
  RETURN NULL;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.sync_layered_serving() FROM PUBLIC;

DROP TRIGGER IF EXISTS sync_layered_serving ON corpus.active_scope_pointer;
CREATE TRIGGER sync_layered_serving
AFTER INSERT OR UPDATE OR DELETE ON corpus.active_scope_pointer
FOR EACH ROW EXECUTE FUNCTION corpus.sync_layered_serving();
DROP TRIGGER IF EXISTS sync_layered_serving_truncate ON corpus.active_scope_pointer;
CREATE TRIGGER sync_layered_serving_truncate
AFTER TRUNCATE ON corpus.active_scope_pointer
FOR EACH STATEMENT EXECUTE FUNCTION corpus.sync_layered_serving();

-- Derive the state of every pair served now (nothing for pairs without a base
-- scope), so re-applying this file leaves it exact.
DELETE FROM corpus.layered_shadowed_rows;
DELETE FROM corpus.layered_navigation_overrides;
SELECT corpus.refresh_layered_serving(active.jurisdiction, active.document_class)
FROM corpus.active_scope_pointer active
ORDER BY active.jurisdiction, active.document_class;

-- ---------------------------------------------------------------------------
-- 4. Winner views over provisions: the previous rules, less shadowed rows.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW corpus.current_provisions AS
SELECT p.*
FROM corpus.provisions p
WHERE EXISTS (
  SELECT 1
  FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version
)
  AND NOT EXISTS (
  SELECT 1
  FROM corpus.layered_shadowed_rows shadowed
  WHERE shadowed.provision_id = p.id
);

-- Everything current_provisions does not serve, now including base rows a
-- primary row shadows. Service-only, as before.
CREATE OR REPLACE VIEW corpus.legacy_provisions AS
SELECT p.*
FROM corpus.provisions p
WHERE NOT EXISTS (
  SELECT 1
  FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version
)
   OR EXISTS (
  SELECT 1
  FROM corpus.layered_shadowed_rows shadowed
  WHERE shadowed.provision_id = p.id
);

GRANT SELECT ON corpus.current_provisions TO anon, authenticated;
GRANT SELECT ON corpus.legacy_provisions TO postgres, service_role;

-- ---------------------------------------------------------------------------
-- 5. Winner view over navigation. Same columns in the same order: served
-- stored rows that are neither shadowed nor overridden, and the overrides.
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
  n.has_children,
  n.child_count,
  n.has_rulespec,
  n.encoded_descendant_count,
  n.status,
  n.created_at,
  n.updated_at,
  n.version
FROM corpus.navigation_nodes n
WHERE EXISTS (
  SELECT 1
  FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = n.jurisdiction
    AND s.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
    AND s.version = n.version
)
  AND NOT EXISTS (
  SELECT 1
  FROM corpus.layered_shadowed_rows shadowed
  WHERE shadowed.navigation_id = n.id
)
  AND NOT EXISTS (
  SELECT 1
  FROM corpus.layered_navigation_overrides overrides
  WHERE overrides.id = n.id
)
UNION ALL
SELECT
  o.id,
  o.jurisdiction,
  o.doc_type,
  o.path,
  o.parent_path,
  o.segment,
  o.label,
  o.sort_key,
  o.depth,
  o.provision_id,
  o.citation_path,
  o.has_children,
  o.child_count,
  o.has_rulespec,
  o.encoded_descendant_count,
  o.status,
  o.created_at,
  o.updated_at,
  o.version
FROM corpus.layered_navigation_overrides o;

GRANT SELECT ON corpus.current_navigation_nodes TO anon, authenticated;
GRANT SELECT ON corpus.current_navigation_nodes TO postgres, service_role;

-- ---------------------------------------------------------------------------
-- 6. Direct navigation_nodes reads: the previous policy, less shadowed rows. A
-- direct read returns the stored per-scope tree fields; the merged ones are in
-- current_navigation_nodes. The policy runs as the reader, who cannot read
-- layered_shadowed_rows, so the ids come from an owner-run function that the
-- planner evaluates once per query and hashes.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION corpus.layered_shadowed_navigation_ids()
RETURNS SETOF text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = corpus, public
ROWS 500
AS $$
  SELECT shadowed.navigation_id
  FROM corpus.layered_shadowed_rows shadowed
  WHERE shadowed.navigation_id IS NOT NULL
$$;

REVOKE EXECUTE ON FUNCTION corpus.layered_shadowed_navigation_ids() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.layered_shadowed_navigation_ids()
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
    )
    AND navigation_nodes.id NOT IN (SELECT corpus.layered_shadowed_navigation_ids())
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
    )
    AND navigation_nodes.id NOT IN (SELECT corpus.layered_shadowed_navigation_ids())
  );

-- ---------------------------------------------------------------------------
-- 7. Root-document counts from served winners.
--
-- Supersedes the definition proposed in open PR #666 (20260910140000, which
-- counts roots through current_navigation_nodes) and the table-wide count of
-- 20260910120000. With no base scope active it returns exactly what #666's
-- function returns; for a layered pair it counts the roots of the merged tree.
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

