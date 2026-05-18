-- Precompute counts at the exact release-scope grain.
--
-- Counting a whole release directly from corpus.provisions can exceed
-- PostgREST's gateway timeout even when the database statement timeout is
-- disabled. This materialized view makes release validation read a small
-- version-keyed count surface instead of rescanning the corpus each time.

CREATE MATERIALIZED VIEW IF NOT EXISTS corpus.provision_scope_counts AS
SELECT
  jurisdiction,
  COALESCE(NULLIF(doc_type, ''), 'unknown') AS document_class,
  version,
  COUNT(id)::bigint AS provision_count,
  COUNT(id) FILTER (
    WHERE body IS NOT NULL
      AND BTRIM(body) <> ''
  )::bigint AS body_count,
  COUNT(id) FILTER (
    WHERE parent_id IS NULL
  )::bigint AS top_level_count,
  COUNT(id) FILTER (
    WHERE has_rulespec IS TRUE
  )::bigint AS rulespec_count,
  now() AS refreshed_at
FROM corpus.provisions
WHERE jurisdiction IS NOT NULL
  AND version IS NOT NULL
GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown'), version
WITH NO DATA;

SET statement_timeout = 0;
REFRESH MATERIALIZED VIEW corpus.provision_scope_counts;
RESET statement_timeout;

CREATE UNIQUE INDEX IF NOT EXISTS idx_provision_scope_counts_scope
  ON corpus.provision_scope_counts (jurisdiction, document_class, version);

GRANT SELECT ON corpus.provision_scope_counts TO postgres, service_role;
REVOKE SELECT ON corpus.provision_scope_counts FROM anon, authenticated, PUBLIC;

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
SET statement_timeout = 0
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
    COALESCE(SUM(provision_scope_counts.provision_count), 0)::bigint
      AS provision_count,
    COALESCE(SUM(provision_scope_counts.body_count), 0)::bigint AS body_count,
    COALESCE(SUM(provision_scope_counts.top_level_count), 0)::bigint
      AS top_level_count,
    COALESCE(SUM(provision_scope_counts.rulespec_count), 0)::bigint
      AS rulespec_count,
    COALESCE(MAX(provision_scope_counts.refreshed_at), now()) AS refreshed_at
  FROM requested_groups
  JOIN requested_scopes
    ON requested_scopes.jurisdiction = requested_groups.jurisdiction
   AND requested_scopes.document_class = requested_groups.document_class
  LEFT JOIN corpus.provision_scope_counts
    ON provision_scope_counts.jurisdiction = requested_scopes.jurisdiction
   AND provision_scope_counts.document_class = requested_scopes.document_class
   AND provision_scope_counts.version = requested_scopes.version
  GROUP BY requested_groups.jurisdiction, requested_groups.document_class
  ORDER BY requested_groups.jurisdiction, requested_groups.document_class
$$;

CREATE OR REPLACE FUNCTION corpus.refresh_corpus_analytics()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
SET statement_timeout = 0
SET lock_timeout = 0
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY corpus.provision_counts;
  REFRESH MATERIALIZED VIEW CONCURRENTLY corpus.current_provision_counts;
  REFRESH MATERIALIZED VIEW CONCURRENTLY corpus.provision_scope_counts;
END;
$$;

GRANT EXECUTE ON FUNCTION corpus.refresh_corpus_analytics() TO postgres, service_role;
REVOKE EXECUTE ON FUNCTION corpus.refresh_corpus_analytics()
  FROM anon, authenticated, PUBLIC;

NOTIFY pgrst, 'reload schema';
