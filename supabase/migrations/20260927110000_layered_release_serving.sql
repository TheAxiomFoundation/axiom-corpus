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
-- The derived state is a function of the pointers, release membership and the
-- staged rows of released scopes, and stays one, whoever writes (short of
-- turning triggers off): the pointers' trigger re-derives a pair whenever its
-- serving release changes; membership of a signed release cannot be updated,
-- deleted or truncated, only its signed scopes can be inserted, and one that
-- joins a served pair re-derives it; a signed release object cannot change or,
-- while it has membership, go; released rows refuse TRUNCATE as they already
-- refuse row writes; only the derivation writes the derived tables, and only
-- under READ COMMITTED.
--
-- NOT applied by any workflow. publish.yml and register-release-object.yml
-- re-apply only 20260722021000 and the registration RPC (20260927100000), and
-- activate-release.yml only 20260722021000. Apply this file deliberately, as
-- postgres, before the first layered release is activated: until it is
-- applied, the activation RPC of 20260719043000 rejects every
-- release-object/v4 object. Every statement is re-runnable. The file never
-- derives a served base layer: its statements lock tables serving reads go
-- through until it commits, so when a base scope is served (re-applying it
-- after a layered activation) run SELECT corpus.rederive_layered_serving() as
-- its own transaction afterwards (section 3). Deployment is in
-- docs/named-release-publication.md.

-- Give up rather than queue serving reads behind a lock this file waits for:
-- while a statement here waits, reads that need a conflicting lock queue
-- behind it. On a timeout, retry at a quieter moment.
SET lock_timeout = '2s';

-- ---------------------------------------------------------------------------
-- 1. Navigation indexes.
--
-- current_navigation_nodes (section 5) tests served scopes with a hashed
-- filter, so a per-jurisdiction page ordered by citation_path is an ordered
-- index scan that stops after the page, whatever the share of stored versions
-- the jurisdiction serves; this index makes that scan possible. The scope
-- index is the definition of open PR #699 (either migration makes the other a
-- no-op); it keeps scope-driven reads of one served scope cheap. On a live
-- database build both with CREATE INDEX CONCURRENTLY before applying this file
-- (it then skips them), so staging writes are not blocked for the build. They
-- come first, before any statement locks a table serving reads.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  v_invalid text;
BEGIN
  -- A failed CREATE INDEX CONCURRENTLY leaves an INVALID index under the name,
  -- and CREATE INDEX IF NOT EXISTS would then silently keep it.
  SELECT string_agg(indexrelid::regclass::text, ', ')
  INTO v_invalid
  FROM pg_index
  WHERE NOT indisvalid
    AND indexrelid IN (
      to_regclass('corpus.idx_navigation_nodes_jurisdiction_citation_path'),
      to_regclass('corpus.idx_navigation_nodes_release_scope_version')
    );
  IF v_invalid IS NOT NULL THEN
    RAISE EXCEPTION 'drop and rebuild invalid index before applying: %', v_invalid;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_navigation_nodes_jurisdiction_citation_path
  ON corpus.navigation_nodes (jurisdiction, citation_path);
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_release_scope_version
  ON corpus.navigation_nodes (
    jurisdiction,
    (COALESCE(NULLIF(doc_type, ''), 'unknown')),
    version
  )
  INCLUDE (citation_path, has_children, child_count, has_rulespec);

-- ---------------------------------------------------------------------------
-- 2. Signed layer on release membership. Historical rows default to primary.
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
--     was the segment fallback (the provision has no heading).
--
-- Where every provision declares its immediate path prefix as its parent and
-- a primary scope never skips a level the base carries, this is exactly
-- build_navigation_nodes run over the served records (tested). Staged rows do
-- not keep a provision's declared parent path, only its versioned parent id,
-- so a primary root the base does not carry goes under its nearest served
-- path prefix even if it declares a parent that is not a prefix (an eCFR
-- section declares its subpart): it lands under the part instead.
CREATE TABLE IF NOT EXISTS corpus.layered_navigation_overrides (
  LIKE corpus.navigation_nodes INCLUDING DEFAULTS,
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  document_class text NOT NULL,
  layer text NOT NULL CHECK (layer IN ('base', 'primary')),
  PRIMARY KEY (id)
);
-- The same lookups current_navigation_nodes serves from navigation_nodes.
CREATE INDEX IF NOT EXISTS idx_layered_navigation_overrides_pair
  ON corpus.layered_navigation_overrides (jurisdiction, document_class);
CREATE INDEX IF NOT EXISTS idx_layered_navigation_overrides_citation_path
  ON corpus.layered_navigation_overrides (jurisdiction, citation_path);
CREATE INDEX IF NOT EXISTS idx_layered_navigation_overrides_scope_parent_sort
  ON corpus.layered_navigation_overrides (jurisdiction, doc_type, parent_path, sort_key);
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

-- Only the derivation below writes the two tables; it marks its own writes
-- with the transaction-local setting corpus.layered_serving_derivation. Any
-- other write, the owner's included, is rejected, so the tables cannot drift
-- from what is served. corpus.rederive_layered_serving() rebuilds them.
CREATE OR REPLACE FUNCTION corpus.guard_layered_serving_write()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = corpus, public
AS $$
BEGIN
  IF current_setting('corpus.layered_serving_derivation', true) IS DISTINCT FROM 'on' THEN
    RAISE EXCEPTION
      'corpus.% holds derived layered serving state and is written only by its derivation; run SELECT corpus.rederive_layered_serving() to rebuild it',
      TG_TABLE_NAME;
  END IF;
  RETURN NULL;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.guard_layered_serving_write() FROM PUBLIC;

CREATE OR REPLACE TRIGGER guard_layered_serving_write
BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON corpus.layered_shadowed_rows
FOR EACH STATEMENT EXECUTE FUNCTION corpus.guard_layered_serving_write();
CREATE OR REPLACE TRIGGER guard_layered_serving_write
BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON corpus.layered_navigation_overrides
FOR EACH STATEMENT EXECUTE FUNCTION corpus.guard_layered_serving_write();

-- The sort-key segment normalization of navigation._normalize_sort_segment:
-- lower-case, every run of digits left-padded with zeros to 12 characters
-- (longer runs unchanged). Citation path segments are ASCII letters, digits,
-- space, '.', ':', '-' and the en dash (schema/citation-path.v1.json), where
-- lower() and the digit test agree with Python's.
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

-- navigation._label_text labels a node with its stripped heading and falls back
-- when the heading is None or str.strip() leaves nothing. str.strip() removes
-- every character str.isspace() accepts: these 29, not only ASCII whitespace.
CREATE OR REPLACE FUNCTION corpus.navigation_heading_is_blank(p_heading text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
SET search_path = corpus, public
AS $$
  SELECT p_heading IS NULL
    OR btrim(
      p_heading,
      E'\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f \u0085                 　'
    ) = ''
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

-- Planner statistics for the two derived tables. The views probe them by
-- unique index, and a layered activation changes them from empty to tens of
-- thousands of rows, so every derivation that changes them analyzes both in
-- its own transaction (ANALYZE counts the transaction's own rows). It takes
-- SHARE UPDATE EXCLUSIVE, which no read or row write conflicts with.
CREATE OR REPLACE FUNCTION corpus.analyze_layered_serving()
RETURNS void
LANGUAGE plpgsql
SET search_path = corpus, public
AS $$
BEGIN
  ANALYZE corpus.layered_shadowed_rows;
  ANALYZE corpus.layered_navigation_overrides;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.analyze_layered_serving()
  FROM anon, authenticated, service_role, PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.analyze_layered_serving() TO postgres;

-- Recompute one pair's derived state from the release that now serves it.
--
-- Only under READ COMMITTED: there each statement reads what was committed
-- when it started, and every caller holds a lock (EXCLUSIVE on
-- active_scope_pointer, or the row lock of a pointer write) that orders it
-- after any concurrent membership insert, which re-derives its own pair
-- (sync_layered_serving_membership). A REPEATABLE READ or SERIALIZABLE
-- snapshot taken before such an insert committed would miss its rows.
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
  v_changed integer;
  v_rows integer;
  v_shadowed integer;
  v_served integer;
  v_reached integer;
  v_broken integer;
  v_deriving text := current_setting('corpus.layered_serving_derivation', true);
BEGIN
  IF current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION
      'layered serving is derived only under READ COMMITTED isolation, not %',
      current_setting('transaction_isolation');
  END IF;
  PERFORM set_config('corpus.layered_serving_derivation', 'on', true);
  DELETE FROM corpus.layered_shadowed_rows shadowed
  WHERE shadowed.jurisdiction = p_jurisdiction
    AND shadowed.document_class = p_document_class;
  GET DIAGNOSTICS v_changed = ROW_COUNT;
  DELETE FROM corpus.layered_navigation_overrides overrides
  WHERE overrides.jurisdiction = p_jurisdiction
    AND overrides.document_class = p_document_class;
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  v_changed := v_changed + v_rows;

  SELECT active.release_name, active.content_sha256
  INTO v_release_name, v_content_sha256
  FROM corpus.active_scope_pointer active
  WHERE active.jurisdiction = p_jurisdiction
    AND active.document_class = p_document_class;
  IF FOUND THEN
    SELECT scopes.version
    INTO v_base_version
    FROM corpus.release_scopes scopes
    WHERE scopes.release_name = v_release_name
      AND scopes.jurisdiction = p_jurisdiction
      AND scopes.document_class = p_document_class
      AND scopes.layer = 'base';
  END IF;
  IF v_base_version IS NULL THEN
    -- Served without a base scope, or not served: nothing derived. A pair
    -- that was layered until now leaves its rows removed above.
    PERFORM set_config('corpus.layered_serving_derivation', COALESCE(v_deriving, ''), true);
    IF v_changed > 0 THEN
      PERFORM corpus.analyze_layered_serving();
    END IF;
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
    -- cycle is the chain from that path on. "Smallest" is code-point order,
    -- Python's.
    cycles AS (
      SELECT DISTINCT (
        SELECT min(member COLLATE "C")
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
      -- build_navigation_nodes labels a node with its heading (or citation
      -- label) and falls back to the segment; only a fallback label follows a
      -- changed segment.
      -- Staged rows do not keep the citation label, so a node with no heading
      -- whose citation label equals its old segment follows the new segment
      -- here, while build_navigation_nodes would keep the citation label.
      CASE
        WHEN derived.merged_segment IS DISTINCT FROM derived.segment
         AND derived.label = derived.segment
         AND NOT EXISTS (
           SELECT 1
           FROM corpus.provisions provision
           WHERE provision.id = derived.provision_id::uuid
             AND NOT corpus.navigation_heading_is_blank(provision.heading)
         )
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
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  DROP TABLE layered_navigation_merge;
  PERFORM set_config('corpus.layered_serving_derivation', COALESCE(v_deriving, ''), true);
  IF v_changed + v_shadowed + v_rows > 0 THEN
    PERFORM corpus.analyze_layered_serving();
  END IF;
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
DECLARE
  v_deriving text := current_setting('corpus.layered_serving_derivation', true);
BEGIN
  IF TG_OP = 'TRUNCATE' THEN
    -- Nothing is served: nothing is derived, whatever a snapshot shows.
    PERFORM set_config('corpus.layered_serving_derivation', 'on', true);
    DELETE FROM corpus.layered_shadowed_rows;
    DELETE FROM corpus.layered_navigation_overrides;
    PERFORM set_config('corpus.layered_serving_derivation', COALESCE(v_deriving, ''), true);
    PERFORM corpus.analyze_layered_serving();
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

-- CREATE OR REPLACE TRIGGER takes SHARE ROW EXCLUSIVE, which reads do not
-- wait for; DROP TRIGGER would take ACCESS EXCLUSIVE on the table.
CREATE OR REPLACE TRIGGER sync_layered_serving
AFTER INSERT OR UPDATE OR DELETE ON corpus.active_scope_pointer
FOR EACH ROW EXECUTE FUNCTION corpus.sync_layered_serving();
CREATE OR REPLACE TRIGGER sync_layered_serving_truncate
AFTER TRUNCATE ON corpus.active_scope_pointer
FOR EACH STATEMENT EXECUTE FUNCTION corpus.sync_layered_serving();

-- Release membership is what the derived state is derived from, so membership
-- of a signed release is immutable. Every row belongs to a signed release
-- (release_scopes_release_object_fkey), so an UPDATE or DELETE of any row is
-- rejected, and a TRUNCATE of any. Activation inserts membership; an inserted
-- row must be one of its release object's signed scopes with its signed layer
-- (guard_release_scope_membership_insert): a row can no longer be deleted, so
-- a stray one would stay.
CREATE OR REPLACE FUNCTION corpus.guard_release_scope_membership()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
BEGIN
  IF TG_OP = 'TRUNCATE' THEN
    IF EXISTS (SELECT 1 FROM corpus.release_scopes) THEN
      RAISE EXCEPTION
        'membership of a signed corpus release is immutable: cannot truncate corpus.release_scopes';
    END IF;
    RETURN NULL;
  END IF;
  RAISE EXCEPTION
    'membership of signed corpus release % is immutable: cannot % %/%/%',
    OLD.release_name,
    lower(TG_OP),
    OLD.jurisdiction,
    OLD.document_class,
    OLD.version;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.guard_release_scope_membership() FROM PUBLIC;

CREATE OR REPLACE TRIGGER guard_release_scope_membership
BEFORE UPDATE OR DELETE ON corpus.release_scopes
FOR EACH ROW EXECUTE FUNCTION corpus.guard_release_scope_membership();
CREATE OR REPLACE TRIGGER guard_release_scope_membership_truncate
BEFORE TRUNCATE ON corpus.release_scopes
FOR EACH STATEMENT EXECUTE FUNCTION corpus.guard_release_scope_membership();

-- One check per statement, over the rows it inserted (none for a re-activation,
-- whose rows all conflict), reading each release object once.
CREATE OR REPLACE FUNCTION corpus.guard_release_scope_membership_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
DECLARE
  v_stray record;
BEGIN
  WITH releases AS (
    SELECT DISTINCT inserted.release_name
    FROM inserted_scopes inserted
  ),
  signed AS MATERIALIZED (
    SELECT
      objects.release_name,
      scope.value ->> 'jurisdiction' AS jurisdiction,
      scope.value ->> 'document_class' AS document_class,
      scope.value ->> 'version' AS version,
      COALESCE(scope.value ->> 'layer', 'primary') AS layer
    FROM releases
    JOIN corpus.release_objects objects
      ON objects.release_name = releases.release_name
    CROSS JOIN LATERAL jsonb_array_elements(
      CASE
        WHEN jsonb_typeof(objects.release_object #> '{content,scopes}') = 'array'
          THEN objects.release_object #> '{content,scopes}'
        ELSE '[]'::jsonb
      END
    ) scope(value)
  )
  SELECT inserted.*
  INTO v_stray
  FROM inserted_scopes inserted
  WHERE NOT EXISTS (
    SELECT 1
    FROM signed
    WHERE signed.release_name = inserted.release_name
      AND signed.jurisdiction = inserted.jurisdiction
      AND signed.document_class = inserted.document_class
      AND signed.version = inserted.version
      AND signed.layer = inserted.layer
  )
  ORDER BY inserted.release_name, inserted.jurisdiction, inserted.document_class, inserted.version
  LIMIT 1;
  IF FOUND THEN
    RAISE EXCEPTION
      'membership of signed corpus release % is immutable: %/%/% (%) is not one of its signed scopes',
      v_stray.release_name,
      v_stray.jurisdiction,
      v_stray.document_class,
      v_stray.version,
      v_stray.layer;
  END IF;
  RETURN NULL;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.guard_release_scope_membership_insert() FROM PUBLIC;

-- AFTER triggers of one event fire in name order: this check, then the
-- re-derivation below.
CREATE OR REPLACE TRIGGER guard_release_scope_membership_insert
AFTER INSERT ON corpus.release_scopes
REFERENCING NEW TABLE AS inserted_scopes
FOR EACH STATEMENT EXECUTE FUNCTION corpus.guard_release_scope_membership_insert();

-- Activation inserts every signed scope before it moves a pointer, and checks
-- that membership then equals the signed scopes, so the membership of a
-- release that serves a pair is complete. A signed scope can still join a
-- pair its release already serves when membership was altered before the
-- guard above existed and is restored, by re-activating the release (whose
-- pointer then does not move) or by inserting the row: re-derive that pair in
-- the same statement. The pointers are locked before they are read, which
-- orders this after any activation or pointer write in progress, and that
-- write's derivation after this one.
CREATE OR REPLACE FUNCTION corpus.sync_layered_serving_membership()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
DECLARE
  pair record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM inserted_scopes) THEN
    RETURN NULL;
  END IF;
  IF current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION
      'release membership is inserted only under READ COMMITTED isolation, not %',
      current_setting('transaction_isolation');
  END IF;
  LOCK TABLE corpus.active_scope_pointer IN EXCLUSIVE MODE;
  FOR pair IN
    SELECT DISTINCT inserted.jurisdiction, inserted.document_class
    FROM inserted_scopes inserted
    JOIN corpus.active_scope_pointer active
      ON active.jurisdiction = inserted.jurisdiction
     AND active.document_class = inserted.document_class
     AND active.release_name = inserted.release_name
    ORDER BY 1, 2
  LOOP
    PERFORM corpus.refresh_layered_serving(pair.jurisdiction, pair.document_class);
  END LOOP;
  RETURN NULL;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.sync_layered_serving_membership() FROM PUBLIC;

CREATE OR REPLACE TRIGGER sync_layered_serving_membership
AFTER INSERT ON corpus.release_scopes
REFERENCING NEW TABLE AS inserted_scopes
FOR EACH STATEMENT EXECUTE FUNCTION corpus.sync_layered_serving_membership();

-- The signed release object is what membership is checked against, and what
-- the released-row guards (guard_released_scope_row_immutable, 20260710180000)
-- look up, so it is immutable too: only created_at may change
-- (stage_corpus_release_object repairs it to the signed publication time), and
-- an object with membership cannot be deleted. Checked row by row, so deleting
-- and re-inserting an object inside one statement cannot hide it from those
-- guards while the foreign keys wait for the end of the statement.
CREATE OR REPLACE FUNCTION corpus.guard_release_object_immutable()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.release_name, NEW.content_sha256, NEW.release_object)
       IS DISTINCT FROM (OLD.release_name, OLD.content_sha256, OLD.release_object) THEN
      RAISE EXCEPTION 'signed corpus release object % is immutable', OLD.release_name;
    END IF;
    RETURN NEW;
  END IF;
  IF EXISTS (
    SELECT 1
    FROM corpus.release_scopes scopes
    WHERE scopes.release_name = OLD.release_name
  ) THEN
    RAISE EXCEPTION
      'signed corpus release object % is immutable: its release has membership',
      OLD.release_name;
  END IF;
  RETURN OLD;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.guard_release_object_immutable() FROM PUBLIC;

CREATE OR REPLACE TRIGGER guard_release_object_immutable
BEFORE UPDATE OR DELETE ON corpus.release_objects
FOR EACH ROW EXECUTE FUNCTION corpus.guard_release_object_immutable();

-- TRUNCATE skips the row triggers that keep released rows immutable
-- (guard_released_scope_row_immutable, 20260710180000), and the derived state
-- copies released navigation rows. service_role has no TRUNCATE privilege;
-- for the owner, a TRUNCATE that would remove a row of a signed release's
-- scope is rejected, layered or not. A table holding only unreleased staged
-- rows can still be truncated.
CREATE OR REPLACE FUNCTION corpus.guard_released_scope_rows_truncate()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
DECLARE
  v_released text;
BEGIN
  EXECUTE format(
    $query$
      SELECT scopes.jurisdiction || '/' || scopes.document_class || '/' || scopes.version
      FROM corpus.release_scopes scopes
      JOIN corpus.release_objects objects
        ON objects.release_name = scopes.release_name
      WHERE EXISTS (
        SELECT 1
        FROM %I.%I staged
        WHERE staged.jurisdiction = scopes.jurisdiction
          AND COALESCE(NULLIF(staged.doc_type, ''), 'unknown') = scopes.document_class
          AND staged.version = scopes.version
      )
      ORDER BY 1
      LIMIT 1
    $query$,
    TG_TABLE_SCHEMA,
    TG_TABLE_NAME
  )
  INTO v_released;
  IF v_released IS NOT NULL THEN
    RAISE EXCEPTION
      'rows belonging to an immutable corpus release cannot be truncated: %.% holds %',
      TG_TABLE_SCHEMA,
      TG_TABLE_NAME,
      v_released;
  END IF;
  RETURN NULL;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.guard_released_scope_rows_truncate() FROM PUBLIC;

CREATE OR REPLACE TRIGGER guard_released_provision_truncate
BEFORE TRUNCATE ON corpus.provisions
FOR EACH STATEMENT EXECUTE FUNCTION corpus.guard_released_scope_rows_truncate();
CREATE OR REPLACE TRIGGER guard_released_navigation_truncate
BEFORE TRUNCATE ON corpus.navigation_nodes
FOR EACH STATEMENT EXECUTE FUNCTION corpus.guard_released_scope_rows_truncate();

-- Re-derive every served pair. This is its own deployment step, run as its
-- own transaction after this file whenever a base scope is served. It takes
-- the locks activation takes, and no other: EXCLUSIVE on active_scope_pointer
-- (conflicting with activations and pointer writes, never with a read), row
-- writes and ANALYZE on the two derived tables, and, only when the shadowed
-- provisions change, the refresh of current_provision_counts activation ends
-- with. Serving reads see the previous state until it commits. Returns the
-- number of shadowed citation paths.
CREATE OR REPLACE FUNCTION corpus.rederive_layered_serving()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
SET statement_timeout = 0
AS $$
DECLARE
  pair record;
  v_shadowed integer := 0;
  v_deriving text := current_setting('corpus.layered_serving_derivation', true);
  v_shadowed_provisions text;
BEGIN
  IF current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION
      'layered serving is derived only under READ COMMITTED isolation, not %',
      current_setting('transaction_isolation');
  END IF;
  LOCK TABLE corpus.active_scope_pointer IN EXCLUSIVE MODE;
  SELECT string_agg(shadowed.provision_id::text, ',' ORDER BY shadowed.provision_id)
  INTO v_shadowed_provisions
  FROM corpus.layered_shadowed_rows shadowed;
  PERFORM set_config('corpus.layered_serving_derivation', 'on', true);
  DELETE FROM corpus.layered_shadowed_rows;
  DELETE FROM corpus.layered_navigation_overrides;
  FOR pair IN
    SELECT active.jurisdiction, active.document_class
    FROM corpus.active_scope_pointer active
    ORDER BY 1, 2
  LOOP
    v_shadowed := v_shadowed
      + corpus.refresh_layered_serving(pair.jurisdiction, pair.document_class);
  END LOOP;
  PERFORM set_config('corpus.layered_serving_derivation', COALESCE(v_deriving, ''), true);
  PERFORM corpus.analyze_layered_serving();
  -- current_provision_counts counts current_provisions, which leaves out the
  -- shadowed provision rows.
  IF (
    SELECT string_agg(shadowed.provision_id::text, ',' ORDER BY shadowed.provision_id)
    FROM corpus.layered_shadowed_rows shadowed
  ) IS DISTINCT FROM v_shadowed_provisions THEN
    REFRESH MATERIALIZED VIEW corpus.current_provision_counts;
  END IF;
  RETURN v_shadowed;
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.rederive_layered_serving()
  FROM anon, authenticated, service_role, PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.rederive_layered_serving() TO postgres;

-- No base scope is served the first time this file is applied, so every
-- derived row would be removed: remove them here, which takes no lock a read
-- waits for. With a base scope served, deriving takes seconds for the whole
-- corpus, while this transaction holds locks serving reads wait for until it
-- commits (ALTER TABLE above, CREATE POLICY and CREATE OR REPLACE VIEW below).
-- So it is not done here: the triggers have kept the derived state, and the
-- deployment runs corpus.rederive_layered_serving() as its own step.
DO $$
DECLARE
  v_deriving text := current_setting('corpus.layered_serving_derivation', true);
BEGIN
  IF EXISTS (
    SELECT 1
    FROM corpus.current_release_scopes scopes
    WHERE scopes.layer = 'base'
  ) THEN
    RAISE NOTICE
      'a base scope is served: after this transaction commits, run SELECT corpus.rederive_layered_serving(); as its own transaction';
  ELSE
    PERFORM set_config('corpus.layered_serving_derivation', 'on', true);
    DELETE FROM corpus.layered_shadowed_rows;
    DELETE FROM corpus.layered_navigation_overrides;
    PERFORM set_config('corpus.layered_serving_derivation', COALESCE(v_deriving, ''), true);
  END IF;
END $$;

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
--
-- The two tables are combined first and filtered once, outside the UNION ALL:
-- PostgreSQL flattens a UNION ALL into one append relation only when its
-- branches carry no WHERE clause, and only then can an ordered page
-- (jurisdiction=eq.us&order=citation_path&limit=1000) merge two ordered index
-- scans and stop after the page instead of sorting every served row. The
-- served-scope and layer tests are uncorrelated, so the planner evaluates each
-- once per query and hashes it; the shadow and override probes run only for
-- rows of pairs served with a base scope. With no base scope active the
-- filter is exactly the previous scope test.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW corpus.current_navigation_nodes AS
SELECT
  served.id,
  served.jurisdiction,
  served.doc_type,
  served.path,
  served.parent_path,
  served.segment,
  served.label,
  served.sort_key,
  served.depth,
  served.provision_id,
  served.citation_path,
  served.has_children,
  served.child_count,
  served.has_rulespec,
  served.encoded_descendant_count,
  served.status,
  served.created_at,
  served.updated_at,
  served.version
FROM (
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
    n.version,
    false AS merged
  FROM corpus.navigation_nodes n
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
    o.version,
    true AS merged
  FROM corpus.layered_navigation_overrides o
) served
WHERE served.merged
   OR (
    (
      served.jurisdiction,
      COALESCE(NULLIF(served.doc_type, ''), 'unknown'),
      served.version
    ) IN (
      SELECT s.jurisdiction, s.document_class, s.version
      FROM corpus.current_release_scopes s
    )
    AND (
      (served.jurisdiction, COALESCE(NULLIF(served.doc_type, ''), 'unknown')) NOT IN (
        SELECT b.jurisdiction, b.document_class
        FROM corpus.current_release_scopes b
        WHERE b.layer = 'base'
      )
      OR (
        NOT EXISTS (
          SELECT 1
          FROM corpus.layered_shadowed_rows shadowed
          WHERE shadowed.navigation_id = served.id
        )
        AND NOT EXISTS (
          SELECT 1
          FROM corpus.layered_navigation_overrides overrides
          WHERE overrides.id = served.id
        )
      )
    )
  );

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
-- The intended count is served roots only. In this repository the function
-- was last defined by 20260910120000, which counts every stored root,
-- superseded and never-released versions included; against that definition
-- this one returns less wherever such roots are stored. Open PR #666
-- (20260910140000, never merged here, and the definition 20260910150000's
-- comment assumes) counts roots through current_navigation_nodes; this
-- supersedes it and, with no base scope active, returns exactly what it
-- returns. It counts exactly the roots current_navigation_nodes serves
-- (tests/test_layered_serving_postgres.py compares the two), reading the
-- stored roots of each served scope through
-- idx_navigation_nodes_roots_by_scope_version (20260910150000) instead of
-- every stored root; for a layered pair it counts the roots of the merged tree.
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
  WITH layered_pairs AS (
    SELECT base.jurisdiction, base.document_class
    FROM corpus.current_release_scopes base
    WHERE base.layer = 'base'
  ),
  roots AS (
    -- Pairs served without a base scope: the previous count, index-only.
    SELECT n.jurisdiction, n.doc_type
    FROM corpus.current_release_scopes s
    JOIN corpus.navigation_nodes n
      ON n.jurisdiction = s.jurisdiction
     AND COALESCE(NULLIF(n.doc_type, ''), 'unknown') = s.document_class
     AND n.version = s.version
    WHERE n.parent_path IS NULL
      AND NOT EXISTS (
        SELECT 1
        FROM layered_pairs
        WHERE layered_pairs.jurisdiction = s.jurisdiction
          AND layered_pairs.document_class = s.document_class
      )
    UNION ALL
    -- Layered pairs: stored roots neither shadowed nor overridden ...
    SELECT n.jurisdiction, n.doc_type
    FROM layered_pairs
    JOIN corpus.current_release_scopes s
      ON s.jurisdiction = layered_pairs.jurisdiction
     AND s.document_class = layered_pairs.document_class
    JOIN corpus.navigation_nodes n
      ON n.jurisdiction = s.jurisdiction
     AND COALESCE(NULLIF(n.doc_type, ''), 'unknown') = s.document_class
     AND n.version = s.version
    WHERE n.parent_path IS NULL
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
    -- ... and merged roots.
    SELECT o.jurisdiction, o.doc_type
    FROM corpus.layered_navigation_overrides o
    WHERE o.parent_path IS NULL
  )
  SELECT
    roots.jurisdiction,
    COALESCE(NULLIF(roots.doc_type, ''), 'unknown') AS doc_type,
    COUNT(*)::bigint AS document_count
  FROM roots
  WHERE roots.jurisdiction IS NOT NULL
  GROUP BY roots.jurisdiction, COALESCE(NULLIF(roots.doc_type, ''), 'unknown')
  ORDER BY 1, 2
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
-- refresh). New: v4 acceptance and layer rules, a v4-only check that each
-- layered pair keeps citation paths unique within each layer, the layer in
-- stored membership and in both membership comparisons. Each pointer move
-- fires sync_layered_serving, which derives the pair's shadowed rows and
-- merged navigation in this transaction. Any failure raises and rolls the
-- whole activation back.
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
  v_ambiguous record;
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

  -- Serving a layered pair is unambiguous only if each layer carries a
  -- citation path at most once: two primary rows of one path would both be
  -- served. The counts and digests above already pinned these staged rows to
  -- the signed projections.
  IF v_schema = 'axiom-corpus/release-object/v4' THEN
    WITH layered_pairs AS (
      SELECT
        scope.value ->> 'jurisdiction' AS jurisdiction,
        scope.value ->> 'document_class' AS document_class
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
      WHERE scope.value ? 'layer'
    ),
    layered_scopes AS (
      SELECT
        scope.value ->> 'jurisdiction' AS jurisdiction,
        scope.value ->> 'document_class' AS document_class,
        scope.value ->> 'version' AS version,
        COALESCE(scope.value ->> 'layer', 'primary') AS layer
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}') scope(value)
      JOIN layered_pairs
        ON layered_pairs.jurisdiction = scope.value ->> 'jurisdiction'
       AND layered_pairs.document_class = scope.value ->> 'document_class'
    )
    SELECT
      layered_scopes.jurisdiction,
      layered_scopes.document_class,
      layered_scopes.layer,
      provisions.citation_path
    INTO v_ambiguous
    FROM layered_scopes
    JOIN corpus.provisions provisions
      ON provisions.jurisdiction = layered_scopes.jurisdiction
     AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown') = layered_scopes.document_class
     AND provisions.version = layered_scopes.version
    GROUP BY 1, 2, 3, 4
    HAVING COUNT(*) > 1
    ORDER BY 1, 2, 4, 3
    LIMIT 1;
    IF FOUND THEN
      RAISE EXCEPTION
        'layered corpus release has ambiguous % citation ownership in %/%: %',
        v_ambiguous.layer,
        v_ambiguous.jurisdiction,
        v_ambiguous.document_class,
        v_ambiguous.citation_path;
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

RESET lock_timeout;
