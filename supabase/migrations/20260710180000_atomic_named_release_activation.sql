-- Replace mutable per-scope activation with one immutable named-release pointer.
--
-- Publication stages versioned rows and content-addressed R2 objects first.
-- The controller then readbacks/hashes every object, checks exact database row
-- counts, deep-validates the corpus, and signs an Ed25519 release object.  This
-- RPC repeats the count check and moves the production pointer in the same
-- transaction as the derived-count refresh. Any error rolls the pointer back.

-- Different immutable releases may contain the same citation path at different
-- versions. Public reads remain unambiguous because current_provisions joins the
-- one active release's exact version scopes.
ALTER TABLE corpus.provisions
  DROP CONSTRAINT IF EXISTS provisions_citation_path_unique;
ALTER TABLE corpus.provisions
  DROP CONSTRAINT IF EXISTS rules_citation_path_unique;
ALTER TABLE corpus.provisions
  DROP CONSTRAINT IF EXISTS provisions_citation_path_key;
DROP INDEX IF EXISTS corpus.provisions_citation_path_unique;
DROP INDEX IF EXISTS corpus.rules_citation_path_unique;
DROP INDEX IF EXISTS corpus.provisions_citation_path_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_provisions_citation_path_version
  ON corpus.provisions (citation_path, version)
  WHERE version IS NOT NULL;

-- Navigation is also historical release state. The old global path key forced
-- the writer to delete the same path from older versions, making rollback and
-- immutable release retention impossible.
DROP INDEX IF EXISTS corpus.idx_navigation_nodes_path;
CREATE INDEX idx_navigation_nodes_path
  ON corpus.navigation_nodes (path);
CREATE UNIQUE INDEX IF NOT EXISTS idx_navigation_nodes_path_version
  ON corpus.navigation_nodes (path, version)
  WHERE version IS NOT NULL;

CREATE TABLE IF NOT EXISTS corpus.release_objects (
  release_name text PRIMARY KEY,
  content_sha256 text NOT NULL UNIQUE
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  release_object jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    release_name <> 'current'
    AND char_length(release_name) <= 128
    AND release_name ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
  ),
  UNIQUE (release_name, content_sha256)
);

CREATE TABLE IF NOT EXISTS corpus.active_release_pointer (
  pointer_name text PRIMARY KEY CHECK (pointer_name = 'production'),
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  activated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (release_name, content_sha256)
    REFERENCES corpus.release_objects(release_name, content_sha256)
);

ALTER TABLE corpus.release_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE corpus.active_release_pointer ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS release_objects_active_read ON corpus.release_objects;
DROP POLICY IF EXISTS release_objects_public_read ON corpus.release_objects;
CREATE POLICY release_objects_public_read
  ON corpus.release_objects
  FOR SELECT TO anon, authenticated
  USING (true);

DROP POLICY IF EXISTS active_release_pointer_read ON corpus.active_release_pointer;
CREATE POLICY active_release_pointer_read
  ON corpus.active_release_pointer
  FOR SELECT TO anon, authenticated
  USING (pointer_name = 'production');

GRANT SELECT ON corpus.release_objects TO anon, authenticated;
GRANT SELECT ON corpus.active_release_pointer TO anon, authenticated;
GRANT SELECT ON corpus.release_objects, corpus.active_release_pointer TO service_role;
REVOKE INSERT, UPDATE, DELETE ON corpus.release_objects FROM service_role;
REVOKE INSERT, UPDATE, DELETE ON corpus.active_release_pointer FROM service_role;

-- This is an approved pre-launch hard cut. No legacy scope membership is a
-- signed v2 release, so retaining any of it would either violate the new
-- release-object foreign key or falsely make mutable rows look immutable.
DELETE FROM corpus.release_scopes;
DROP INDEX IF EXISTS corpus.idx_release_scopes_current_active;

DROP POLICY IF EXISTS release_scopes_anon_read ON corpus.release_scopes;
DROP POLICY IF EXISTS release_scopes_authenticated_read ON corpus.release_scopes;

CREATE OR REPLACE VIEW corpus.current_release_scopes AS
SELECT
  scopes.release_name,
  scopes.jurisdiction,
  scopes.document_class,
  scopes.version,
  scopes.synced_at
FROM corpus.release_scopes scopes
JOIN corpus.active_release_pointer pointer
  ON pointer.pointer_name = 'production'
 AND pointer.release_name = scopes.release_name;

ALTER TABLE corpus.release_scopes DROP COLUMN IF EXISTS active;
ALTER TABLE corpus.release_scopes
  DROP CONSTRAINT IF EXISTS release_scopes_named_release_only;
ALTER TABLE corpus.release_scopes
  ADD CONSTRAINT release_scopes_named_release_only CHECK (
    release_name <> 'current'
    AND char_length(release_name) <= 128
    AND release_name ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
  );
ALTER TABLE corpus.release_scopes
  DROP CONSTRAINT IF EXISTS release_scopes_release_object_fkey;
ALTER TABLE corpus.release_scopes
  ADD CONSTRAINT release_scopes_release_object_fkey
  FOREIGN KEY (release_name) REFERENCES corpus.release_objects(release_name);

CREATE POLICY release_scopes_anon_read
  ON corpus.release_scopes
  FOR SELECT TO anon
  USING (
    EXISTS (
      SELECT 1
      FROM corpus.active_release_pointer pointer
      WHERE pointer.pointer_name = 'production'
        AND pointer.release_name = release_scopes.release_name
    )
  );

CREATE POLICY release_scopes_authenticated_read
  ON corpus.release_scopes
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM corpus.active_release_pointer pointer
      WHERE pointer.pointer_name = 'production'
        AND pointer.release_name = release_scopes.release_name
    )
  );

REVOKE ALL ON corpus.release_scopes FROM service_role;
GRANT SELECT ON corpus.release_scopes TO service_role;

-- Once a scope belongs to a signed release object, its database projection is
-- immutable even while another release is active. A later activation can
-- safely point back to it, and retries cannot mutate historical signed state.
CREATE OR REPLACE FUNCTION corpus.guard_released_scope_row_immutable()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
BEGIN
  -- Reject mutation from a released scope, including an UPDATE that tries to
  -- move an immutable row elsewhere.
  IF TG_OP <> 'INSERT' THEN
    IF EXISTS (
      SELECT 1
      FROM corpus.release_scopes scopes
      JOIN corpus.release_objects objects
        ON objects.release_name = scopes.release_name
      WHERE scopes.jurisdiction = OLD.jurisdiction
        AND scopes.document_class = COALESCE(NULLIF(OLD.doc_type, ''), 'unknown')
        AND scopes.version = OLD.version
    ) THEN
      RAISE EXCEPTION
        'rows belonging to an immutable corpus release cannot be mutated: %/%/%',
        OLD.jurisdiction,
        COALESCE(NULLIF(OLD.doc_type, ''), 'unknown'),
        OLD.version;
    END IF;
  END IF;

  -- Also reject INSERT and UPDATE into a released scope. Without this half of
  -- the guard a new citation path could appear in the active public views
  -- after the release object had been signed, despite exact activation counts.
  IF TG_OP <> 'DELETE' THEN
    IF EXISTS (
      SELECT 1
      FROM corpus.release_scopes scopes
      JOIN corpus.release_objects objects
        ON objects.release_name = scopes.release_name
      WHERE scopes.jurisdiction = NEW.jurisdiction
        AND scopes.document_class = COALESCE(NULLIF(NEW.doc_type, ''), 'unknown')
        AND scopes.version = NEW.version
    ) THEN
      RAISE EXCEPTION
        'rows belonging to an immutable corpus release cannot be mutated: %/%/%',
        NEW.jurisdiction,
        COALESCE(NULLIF(NEW.doc_type, ''), 'unknown'),
        NEW.version;
    END IF;
  END IF;

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_released_provision_immutable ON corpus.provisions;
CREATE TRIGGER guard_released_provision_immutable
BEFORE INSERT OR UPDATE OR DELETE ON corpus.provisions
FOR EACH ROW EXECUTE FUNCTION corpus.guard_released_scope_row_immutable();

DROP TRIGGER IF EXISTS guard_released_navigation_immutable ON corpus.navigation_nodes;
CREATE TRIGGER guard_released_navigation_immutable
BEFORE INSERT OR UPDATE OR DELETE ON corpus.navigation_nodes
FOR EACH ROW EXECUTE FUNCTION corpus.guard_released_scope_row_immutable();

-- Historical migrations granted ALL to service_role. TRUNCATE bypasses row
-- triggers entirely, so narrow the staging role to the exact row operations it
-- needs. Released-scope triggers still reject those operations after signing.
REVOKE ALL ON corpus.provisions, corpus.navigation_nodes FROM service_role;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON corpus.provisions, corpus.navigation_nodes TO service_role;

-- Cross-language canonical serialization for signed database projections.
-- Python uses the same N / V<byte-count>:<utf8-value> field encoding. Each row
-- is SHA-256 hashed independently, then the ordered ASCII row digests are
-- hashed into one scope digest. This avoids JSON formatting and delimiter
-- ambiguity while binding every publisher-controlled serving column.
CREATE OR REPLACE FUNCTION corpus.canonical_projection_field(p_value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN p_value IS NULL THEN 'N'
    ELSE 'V' || octet_length(convert_to(p_value, 'UTF8'))::text || ':' || p_value
  END
$$;

CREATE OR REPLACE FUNCTION corpus.canonical_projection_identifiers(p_value jsonb)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN p_value IS NULL THEN 'N'
    ELSE corpus.canonical_projection_field(
      COALESCE(
        (
          SELECT string_agg(
            corpus.canonical_projection_field(entry.key)
              || corpus.canonical_projection_field(entry.value),
            '' ORDER BY entry.key COLLATE "C"
          )
          FROM jsonb_each_text(p_value) AS entry(key, value)
        ),
        ''
      )
    )
  END
$$;

CREATE OR REPLACE FUNCTION corpus.provision_projection_sha256(
  p_jurisdiction text,
  p_document_class text,
  p_version text
)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = corpus, public
AS $$
  WITH projected AS (
    SELECT
      provisions.citation_path,
      provisions.id::text AS row_id,
      encode(
        sha256(
          convert_to(
            concat(
              corpus.canonical_projection_field(provisions.id::text),
              corpus.canonical_projection_field(provisions.jurisdiction),
              corpus.canonical_projection_field(provisions.doc_type),
              corpus.canonical_projection_field(provisions.parent_id::text),
              corpus.canonical_projection_field(provisions.level::text),
              corpus.canonical_projection_field(provisions.ordinal::text),
              corpus.canonical_projection_field(provisions.heading),
              corpus.canonical_projection_field(provisions.body),
              corpus.canonical_projection_field(provisions.source_url),
              corpus.canonical_projection_field(provisions.source_path),
              corpus.canonical_projection_field(provisions.citation_path),
              corpus.canonical_projection_field(provisions.version),
              corpus.canonical_projection_field(provisions.rulespec_path),
              corpus.canonical_projection_field(provisions.has_rulespec::text),
              corpus.canonical_projection_field(provisions.source_document_id::text),
              corpus.canonical_projection_field(provisions.source_as_of::text),
              corpus.canonical_projection_field(provisions.expression_date::text),
              corpus.canonical_projection_field(provisions.language),
              corpus.canonical_projection_field(provisions.legal_identifier),
              corpus.canonical_projection_identifiers(provisions.identifiers)
            ),
            'UTF8'
          )
        ),
        'hex'
      ) AS row_sha256
    FROM corpus.provisions provisions
    WHERE provisions.jurisdiction = p_jurisdiction
      AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown') = p_document_class
      AND provisions.version = p_version
  )
  SELECT encode(
    sha256(
      convert_to(
        COALESCE(
          string_agg(
            row_sha256,
            '' ORDER BY citation_path COLLATE "C", row_id COLLATE "C"
          ),
          ''
        ),
        'UTF8'
      )
    ),
    'hex'
  )
  FROM projected
$$;

CREATE OR REPLACE FUNCTION corpus.navigation_projection_sha256(
  p_jurisdiction text,
  p_document_class text,
  p_version text
)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = corpus, public
AS $$
  WITH projected AS (
    SELECT
      navigation.path,
      navigation.id::text AS row_id,
      encode(
        sha256(
          convert_to(
            concat(
              corpus.canonical_projection_field(navigation.id::text),
              corpus.canonical_projection_field(navigation.jurisdiction),
              corpus.canonical_projection_field(navigation.doc_type),
              corpus.canonical_projection_field(navigation.path),
              corpus.canonical_projection_field(navigation.parent_path),
              corpus.canonical_projection_field(navigation.segment),
              corpus.canonical_projection_field(navigation.label),
              corpus.canonical_projection_field(navigation.sort_key),
              corpus.canonical_projection_field(navigation.depth::text),
              corpus.canonical_projection_field(navigation.provision_id::text),
              corpus.canonical_projection_field(navigation.citation_path),
              corpus.canonical_projection_field(navigation.version),
              corpus.canonical_projection_field(navigation.has_children::text),
              corpus.canonical_projection_field(navigation.child_count::text),
              corpus.canonical_projection_field(navigation.has_rulespec::text),
              corpus.canonical_projection_field(
                navigation.encoded_descendant_count::text
              ),
              corpus.canonical_projection_field(navigation.status)
            ),
            'UTF8'
          )
        ),
        'hex'
      ) AS row_sha256
    FROM corpus.navigation_nodes navigation
    WHERE navigation.jurisdiction = p_jurisdiction
      AND COALESCE(NULLIF(navigation.doc_type, ''), 'unknown') = p_document_class
      AND navigation.version = p_version
  )
  SELECT encode(
    sha256(
      convert_to(
        COALESCE(
          string_agg(
            row_sha256,
            '' ORDER BY path COLLATE "C", row_id COLLATE "C"
          ),
          ''
        ),
        'UTF8'
      )
    ),
    'hex'
  )
  FROM projected
$$;

REVOKE ALL ON FUNCTION corpus.canonical_projection_field(text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION corpus.canonical_projection_identifiers(jsonb)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION corpus.provision_projection_sha256(text, text, text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION corpus.navigation_projection_sha256(text, text, text)
  FROM PUBLIC, anon, authenticated, service_role;

-- Direct, exact evidence over staged base rows. This deliberately does not
-- read a materialized view: the pre-sign attestation must never be stale.
CREATE OR REPLACE FUNCTION corpus.get_staged_release_scope_evidence(p_scopes jsonb)
RETURNS TABLE (
  jurisdiction text,
  document_class text,
  version text,
  provision_count bigint,
  navigation_count bigint,
  provision_projection_sha256 text,
  navigation_projection_sha256 text
)
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
  )
  SELECT
    requested.jurisdiction,
    requested.document_class,
    requested.version,
    (
      SELECT COUNT(*)::bigint
      FROM corpus.provisions provisions
      WHERE provisions.jurisdiction = requested.jurisdiction
        AND COALESCE(NULLIF(provisions.doc_type, ''), 'unknown')
            = requested.document_class
        AND provisions.version = requested.version
    ) AS provision_count,
    (
      SELECT COUNT(*)::bigint
      FROM corpus.navigation_nodes navigation
      WHERE navigation.jurisdiction = requested.jurisdiction
        AND COALESCE(NULLIF(navigation.doc_type, ''), 'unknown')
            = requested.document_class
        AND navigation.version = requested.version
    ) AS navigation_count,
    corpus.provision_projection_sha256(
      requested.jurisdiction,
      requested.document_class,
      requested.version
    ),
    corpus.navigation_projection_sha256(
      requested.jurisdiction,
      requested.document_class,
      requested.version
    )
  FROM requested
  ORDER BY requested.jurisdiction, requested.document_class, requested.version
$$;

GRANT EXECUTE ON FUNCTION corpus.get_staged_release_scope_evidence(jsonb)
  TO postgres, service_role;
REVOKE EXECUTE ON FUNCTION corpus.get_staged_release_scope_evidence(jsonb)
  FROM anon, authenticated, PUBLIC;

-- Return every prior signed object that makes a requested scope immutable.
-- The publisher verifies each object with the configured Ed25519 public key
-- and compares its signed artifact inventory before deciding to skip DML.
CREATE OR REPLACE FUNCTION corpus.get_released_scope_objects(p_scopes jsonb)
RETURNS TABLE (
  jurisdiction text,
  document_class text,
  version text,
  release_name text,
  content_sha256 text,
  release_object jsonb
)
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
  )
  SELECT
    scopes.jurisdiction,
    scopes.document_class,
    scopes.version,
    objects.release_name,
    objects.content_sha256,
    objects.release_object
  FROM requested
  JOIN corpus.release_scopes scopes
    ON scopes.jurisdiction = requested.jurisdiction
   AND scopes.document_class = requested.document_class
   AND scopes.version = requested.version
  JOIN corpus.release_objects objects
    ON objects.release_name = scopes.release_name
  ORDER BY
    scopes.jurisdiction,
    scopes.document_class,
    scopes.version,
    objects.release_name
$$;

GRANT EXECUTE ON FUNCTION corpus.get_released_scope_objects(jsonb)
  TO postgres, service_role;
REVOKE EXECUTE ON FUNCTION corpus.get_released_scope_objects(jsonb)
  FROM anon, authenticated, PUBLIC;

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
  active_release_name text;
  active_content_sha256 text;
  v_scope_count integer;
BEGIN
  IF p_release_object ->> 'schema_version'
     IS DISTINCT FROM 'axiom-corpus/release-object/v2' THEN
    RAISE EXCEPTION 'unsupported corpus release object schema';
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
  -- membership insertion and pointer movement. Concurrent writers wait; once
  -- this transaction commits, the immutable-scope triggers reject their rows.
  -- Without these locks, a writer could commit after the counts but before it
  -- could observe the new signed membership.
  LOCK TABLE corpus.provisions IN SHARE MODE;
  LOCK TABLE corpus.navigation_nodes IN SHARE MODE;

  -- Recheck exact staged counts inside the activation transaction. A mismatch
  -- prevents both release-object insertion and pointer movement.
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

  SELECT pointer.release_name, pointer.content_sha256
  INTO active_release_name, active_content_sha256
  FROM corpus.active_release_pointer pointer
  WHERE pointer.pointer_name = 'production';
  IF active_release_name IS NOT DISTINCT FROM v_release_name
     AND active_content_sha256 IS NOT DISTINCT FROM v_content_sha THEN
    RETURN jsonb_build_object(
      'release', v_release_name,
      'content_sha256', v_content_sha,
      'scope_count', v_scope_count,
      'active', true
    );
  END IF;

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
  -- so a count-refresh failure rolls the active pointer back.
  REFRESH MATERIALIZED VIEW corpus.current_provision_counts;

  RETURN jsonb_build_object(
    'release', v_release_name,
    'content_sha256', v_content_sha,
    'scope_count', v_scope_count,
    'active', true
  );
END;
$$;

GRANT EXECUTE ON FUNCTION corpus.activate_corpus_release(jsonb)
  TO postgres;
REVOKE EXECUTE ON FUNCTION corpus.activate_corpus_release(jsonb)
  FROM anon, authenticated, service_role, PUBLIC;

NOTIFY pgrst, 'reload schema';
