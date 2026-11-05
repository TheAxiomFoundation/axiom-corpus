-- Register signed release-object/v4 (layered) objects before activation.
--
-- v4 is v3 plus signed scope layers: a scope may carry "layer": "base", and a
-- primary scope carries no layer key. The publisher emits v4 only for a release
-- with at least one base scope, so every other release keeps registering as v3.
-- v2 and v3 objects are accepted exactly as by 20260803175000; v4 objects get
-- the v3 quality-profile checks plus the layer rules below.
--
-- This file holds only the registration function, so the publish and
-- register-release-object workflows (scripts/apply_release_object_staging_migration.py)
-- can re-apply it on every run without touching serving. The trigger
-- guard_corpus_release_object_insert is unchanged and stays in 20260803175000.
-- Registering a v4 object never serves it: activation of a layered release
-- needs 20260927110000_layered_release_serving.sql.

CREATE OR REPLACE FUNCTION corpus.stage_corpus_release_object(p_release_object jsonb)
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
  v_published_at timestamptz;
  v_scope_count integer;
  existing_sha text;
  existing_object jsonb;
  inserted_count integer;
BEGIN
  IF COALESCE(p_release_object ->> 'schema_version', '') NOT IN (
    'axiom-corpus/release-object/v2',
    'axiom-corpus/release-object/v3',
    'axiom-corpus/release-object/v4'
  ) THEN
    RAISE EXCEPTION 'unsupported corpus release object schema';
  END IF;
  IF p_release_object ->> 'schema_version' IN (
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
  BEGIN
    v_published_at := NULLIF(
      p_release_object #>> '{content,created_at}',
      ''
    )::timestamptz;
  EXCEPTION
    WHEN invalid_datetime_format OR datetime_field_overflow THEN
      RAISE EXCEPTION 'invalid signed corpus release publication timestamp';
  END;
  IF v_published_at IS NULL THEN
    RAISE EXCEPTION 'signed corpus release publication timestamp is required';
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

  -- A v4 scope is primary without a layer key and base with the exact string
  -- "base"; a v4 object carries at least one base scope and at most one per
  -- (jurisdiction, document_class) pair.
  IF p_release_object ->> 'schema_version' = 'axiom-corpus/release-object/v4' THEN
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
  END IF;

  -- Serialize first publication of an immutable name so two concurrent callers
  -- cannot both observe absence and let the loser silently accept a different
  -- object through ON CONFLICT DO NOTHING.
  PERFORM pg_advisory_xact_lock(hashtextextended(v_release_name, 0));
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

  INSERT INTO corpus.release_objects (
    release_name,
    content_sha256,
    release_object,
    created_at
  )
  VALUES (v_release_name, v_content_sha, p_release_object, v_published_at)
  ON CONFLICT (release_name) DO NOTHING;
  GET DIAGNOSTICS inserted_count = ROW_COUNT;
  IF inserted_count = 0 THEN
    UPDATE corpus.release_objects
    SET created_at = v_published_at
    WHERE release_name = v_release_name
      AND content_sha256 = v_content_sha
      AND release_object = p_release_object
      AND created_at IS DISTINCT FROM v_published_at;
  END IF;

  RETURN jsonb_build_object(
    'staged', true,
    'inserted', inserted_count = 1,
    'release', v_release_name,
    'content_sha256', v_content_sha,
    'scope_count', v_scope_count
  );
END;
$$;

REVOKE EXECUTE ON FUNCTION corpus.stage_corpus_release_object(jsonb)
  FROM anon, authenticated, service_role, PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.stage_corpus_release_object(jsonb)
  TO postgres;
