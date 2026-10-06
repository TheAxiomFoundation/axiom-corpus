CREATE OR REPLACE FUNCTION corpus.materialize_layered_navigation(
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
  v_served integer;
  v_reached integer;
  v_broken integer;
BEGIN
  -- Only the release that now serves the pair keeps merged rows for it.
  DELETE FROM corpus.layered_navigation_nodes nodes
  WHERE nodes.jurisdiction = p_jurisdiction
    AND nodes.document_class = p_document_class;

  IF NOT EXISTS (
    SELECT 1
    FROM corpus.release_scopes scopes
    WHERE scopes.release_name = p_release_name
      AND scopes.jurisdiction = p_jurisdiction
      AND scopes.document_class = p_document_class
      AND scopes.layer = 'base'
  ) THEN
    RETURN 0;
  END IF;

  DROP TABLE IF EXISTS pg_temp.layered_navigation_staged;
  DROP TABLE IF EXISTS pg_temp.layered_navigation_merge;

  -- The pair's staged rows in this release, both layers.
  CREATE TEMP TABLE layered_navigation_staged ON COMMIT DROP AS
  SELECT navigation.*, scopes.layer AS node_layer
  FROM corpus.release_scopes scopes
  JOIN corpus.navigation_nodes navigation
    ON navigation.jurisdiction = scopes.jurisdiction
   AND COALESCE(NULLIF(navigation.doc_type, ''), 'unknown') = scopes.document_class
   AND navigation.version = scopes.version
  WHERE scopes.release_name = p_release_name
    AND scopes.jurisdiction = p_jurisdiction
    AND scopes.document_class = p_document_class;
  CREATE INDEX ON layered_navigation_staged (path);
  ANALYZE layered_navigation_staged;

  -- Served nodes, each with the parent it has in the merged tree: a root of a
  -- primary scope takes its base twin's parent.
  CREATE TEMP TABLE layered_navigation_merge ON COMMIT DROP AS
  SELECT
    winner.*,
    twin.path IS NOT NULL AS has_twin,
    CASE
      WHEN winner.node_layer = 'primary'
       AND winner.parent_path IS NULL
       AND twin.path IS NOT NULL
        THEN twin.parent_path
      ELSE winner.parent_path
    END AS merged_parent_path
  FROM layered_navigation_staged winner
  LEFT JOIN layered_navigation_staged twin
    ON winner.node_layer = 'primary'
   AND twin.node_layer = 'base'
   AND twin.path = winner.path
  WHERE winner.node_layer = 'primary'
     OR NOT EXISTS (
       SELECT 1
       FROM layered_navigation_staged shadow
       WHERE shadow.node_layer = 'primary'
         AND shadow.path = winner.path
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
        p_jurisdiction, p_document_class, p_release_name, v_served - v_reached, v_served;
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
  merged AS (
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
  )
  INSERT INTO corpus.layered_navigation_nodes (
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
    CASE
      WHEN merged.merged_segment IS DISTINCT FROM merged.segment
       AND merged.label = merged.segment
        THEN merged.merged_segment
      ELSE merged.label
    END,
    CASE
      WHEN merged.merged_segment IS DISTINCT FROM merged.segment
        THEN split_part(merged.sort_key, '|', 1) || '|'
          || corpus.navigation_sort_segment(merged.merged_segment)
      ELSE merged.sort_key
    END,
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
    p_release_name,
    p_content_sha256,
    p_document_class,
    merged.node_layer
  FROM merged;
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  DROP TABLE layered_navigation_staged;
  DROP TABLE layered_navigation_merge;
  RETURN v_rows;
END;
$$;
