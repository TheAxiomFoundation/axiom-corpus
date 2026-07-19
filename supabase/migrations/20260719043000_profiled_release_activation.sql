-- Accept the profiled release-object/v3 format at the atomic activation
-- boundary. Historical v2 objects remain replayable, while every v3 object
-- must carry the quality profile in both signed content and validation evidence.

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
  activated_scopes jsonb := '[]'::jsonb;
  reaffirmed_scopes jsonb := '[]'::jsonb;
BEGIN
  IF COALESCE(p_release_object ->> 'schema_version', '') NOT IN (
    'axiom-corpus/release-object/v2',
    'axiom-corpus/release-object/v3'
  ) THEN
    RAISE EXCEPTION 'unsupported corpus release object schema';
  END IF;
  IF p_release_object ->> 'schema_version' = 'axiom-corpus/release-object/v3' THEN
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
    synced_at
  )
  SELECT
    v_release_name,
    value ->> 'jurisdiction',
    value ->> 'document_class',
    value ->> 'version',
    now()
  FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
  ON CONFLICT (release_name, jurisdiction, document_class, version) DO NOTHING;

  IF EXISTS (
    (
      SELECT
        scopes.jurisdiction,
        scopes.document_class,
        scopes.version
      FROM corpus.release_scopes scopes
      WHERE scopes.release_name = v_release_name
      EXCEPT
      SELECT
        value ->> 'jurisdiction',
        value ->> 'document_class',
        value ->> 'version'
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
    )
    UNION ALL
    (
      SELECT
        value ->> 'jurisdiction',
        value ->> 'document_class',
        value ->> 'version'
      FROM jsonb_array_elements(p_release_object #> '{content,scopes}')
      EXCEPT
      SELECT
        scopes.jurisdiction,
        scopes.document_class,
        scopes.version
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
