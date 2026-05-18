-- Fast manifest-scoped provision counts for release validation.
--
-- `current_provision_counts` is a materialized view over the active release
-- boundary. It is useful for public app reads, but refreshing it through
-- PostgREST can exceed gateway timeouts on the full corpus. Release validation
-- needs a narrower operation: count the exact manifest scopes being validated.
--
-- This RPC accepts those scopes as JSONB and returns one grouped row per
-- jurisdiction + document class, including zero-count groups. The CLI can then
-- snapshot Supabase state without relying on stale materialized views or
-- falling back to slow client-side paged counts.

CREATE OR REPLACE FUNCTION corpus.get_release_provision_counts(p_scopes jsonb)
RETURNS TABLE (
  jurisdiction text,
  document_class text,
  provision_count bigint,
  body_count bigint,
  top_level_count bigint,
  rulespec_count bigint,
  refreshed_at timestamptz
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = corpus, public
AS $$
  WITH requested_scopes AS (
    SELECT DISTINCT
      scope.value ->> 'jurisdiction' AS jurisdiction,
      scope.value ->> 'document_class' AS document_class,
      scope.value ->> 'version' AS version
    FROM jsonb_array_elements(COALESCE(p_scopes, '[]'::jsonb)) AS scope(value)
    WHERE jsonb_typeof(scope.value) = 'object'
      AND scope.value ? 'jurisdiction'
      AND scope.value ? 'document_class'
      AND scope.value ? 'version'
      AND NULLIF(scope.value ->> 'jurisdiction', '') IS NOT NULL
      AND NULLIF(scope.value ->> 'document_class', '') IS NOT NULL
      AND NULLIF(scope.value ->> 'version', '') IS NOT NULL
  ),
  requested_groups AS (
    SELECT
      requested_scopes.jurisdiction,
      requested_scopes.document_class
    FROM requested_scopes
    GROUP BY requested_scopes.jurisdiction, requested_scopes.document_class
  )
  SELECT
    requested_groups.jurisdiction,
    requested_groups.document_class,
    COUNT(provisions.id)::bigint AS provision_count,
    COUNT(provisions.id) FILTER (
      WHERE provisions.body IS NOT NULL
        AND BTRIM(provisions.body) <> ''
    )::bigint AS body_count,
    COUNT(provisions.id) FILTER (
      WHERE provisions.parent_id IS NULL
    )::bigint AS top_level_count,
    COUNT(provisions.id) FILTER (
      WHERE provisions.has_rulespec IS TRUE
    )::bigint AS rulespec_count,
    now() AS refreshed_at
  FROM requested_groups
  JOIN requested_scopes
    ON requested_scopes.jurisdiction = requested_groups.jurisdiction
   AND requested_scopes.document_class = requested_groups.document_class
  LEFT JOIN corpus.provisions
    ON provisions.jurisdiction = requested_scopes.jurisdiction
   AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown')
       = requested_scopes.document_class
   AND provisions.version = requested_scopes.version
  GROUP BY requested_groups.jurisdiction, requested_groups.document_class
  ORDER BY requested_groups.jurisdiction, requested_groups.document_class
$$;

GRANT EXECUTE ON FUNCTION corpus.get_release_provision_counts(jsonb)
  TO postgres, service_role;
REVOKE EXECUTE ON FUNCTION corpus.get_release_provision_counts(jsonb)
  FROM anon, authenticated, PUBLIC;

NOTIFY pgrst, 'reload schema';
