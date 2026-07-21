-- Return prior signed release objects once per release, with compact scope
-- memberships. The earlier RPC repeated the complete release object for every
-- requested scope, making publication payloads grow multiplicatively.
CREATE OR REPLACE FUNCTION corpus.get_released_scope_object_sets(p_scopes jsonb)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = corpus, public
SET statement_timeout = 0
AS $$
  WITH requested AS (
    SELECT DISTINCT
      scope.value ->> 'jurisdiction' AS jurisdiction,
      scope.value ->> 'document_class' AS document_class,
      scope.value ->> 'version' AS version
    FROM jsonb_array_elements(COALESCE(p_scopes, '[]'::jsonb)) scope(value)
  ),
  matched AS (
    SELECT
      scopes.release_name,
      jsonb_agg(
        jsonb_build_object(
          'jurisdiction', scopes.jurisdiction,
          'document_class', scopes.document_class,
          'version', scopes.version
        )
        ORDER BY scopes.jurisdiction, scopes.document_class, scopes.version
      ) AS scopes
    FROM requested
    JOIN corpus.release_scopes scopes
      ON scopes.jurisdiction = requested.jurisdiction
     AND scopes.document_class = requested.document_class
     AND scopes.version = requested.version
    GROUP BY scopes.release_name
  )
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'release_name', objects.release_name,
        'content_sha256', objects.content_sha256,
        'release_object', objects.release_object,
        'scopes', matched.scopes
      )
      ORDER BY objects.release_name
    ),
    '[]'::jsonb
  )
  FROM matched
  JOIN corpus.release_objects objects
    ON objects.release_name = matched.release_name
$$;

GRANT EXECUTE ON FUNCTION corpus.get_released_scope_object_sets(jsonb)
  TO postgres, service_role;
REVOKE EXECUTE ON FUNCTION corpus.get_released_scope_object_sets(jsonb)
  FROM anon, authenticated, PUBLIC;

NOTIFY pgrst, 'reload schema';
