-- Move corpus serving from one global release pointer to a per-scope active map.
--
-- Before this migration `corpus.active_release_pointer` was a singleton
-- (pointer_name = 'production'), and `current_release_scopes` -- the source of
-- `current_provisions`, `legacy_provisions`, and `current_provision_counts` --
-- served exactly one release's scopes. Activating any single-jurisdiction
-- release therefore un-served every other jurisdiction. On 2026-07-18 a routine
-- NZ publish auto-activated and narrowed production serving to three NZ scopes;
-- the underlying `provisions`/`navigation_nodes` rows were never touched (see
-- axiom-corpus#408 for the full incident write-up).
--
-- The fix keeps every publication guarantee -- exact staged count rechecks, the
-- per-scope projection digests, the immutable released-scope triggers, and the
-- release-object foreign keys -- and changes ONLY what activation repoints:
-- serving now follows `corpus.active_scope_pointer`, keyed by
-- (jurisdiction, document_class) -> active release. Activating a release repoints
-- only the (jurisdiction, document_class) pairs that release carries and leaves
-- every other jurisdiction on whatever release currently serves it. Overlap
-- between releases that claim the same (jurisdiction, document_class) -- e.g.
-- us-rulespec vs us-rulespec-ny-snap -- resolves last-activation-wins per pair.
--
-- Note the pointer is keyed by (jurisdiction, document_class), NOT by version: a
-- single release legitimately carries MANY versions of one pair (e.g.
-- us-rulespec-2026-07-17 has 165 scopes across 85 pairs; us/statute alone spans
-- 15 versions). The active pointer names the release, and
-- `current_release_scopes` joins `release_scopes` on that release so every
-- version the release carries for the pair is served -- exactly the set the old
-- singleton served for that pair. Every takeover is recorded append-only in
-- `corpus.scope_activation_history`.

-- ---------------------------------------------------------------------------
-- Serving authority: one active release per (jurisdiction, document_class).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS corpus.active_scope_pointer (
  jurisdiction text NOT NULL,
  document_class text NOT NULL,
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  activated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (jurisdiction, document_class),
  -- The pointed-at release must be a signed release object. That the release
  -- also COVERS this (jurisdiction, document_class) pair -- so serving never
  -- resolves to an empty join -- is enforced relationally by the membership
  -- trigger below, not merely by the activation RPC being the sole writer.
  FOREIGN KEY (release_name, content_sha256)
    REFERENCES corpus.release_objects (release_name, content_sha256)
);

-- The active pointer may only name a release that actually carries the pair.
-- Without this, a database-owner INSERT (a stray migration or management-plane
-- statement) could point a pair at a release lacking it, and current_release_scopes
-- would join zero rows -- a silent serving hole. release_scopes membership is
-- immutable once released, so an existence check at write time is sufficient.
CREATE OR REPLACE FUNCTION corpus.guard_active_scope_pointer_membership()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM corpus.release_scopes scopes
    WHERE scopes.release_name = NEW.release_name
      AND scopes.jurisdiction = NEW.jurisdiction
      AND scopes.document_class = NEW.document_class
  ) THEN
    RAISE EXCEPTION
      'active_scope_pointer %/% cannot name release % which does not cover the pair',
      NEW.jurisdiction, NEW.document_class, NEW.release_name;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_active_scope_pointer_membership ON corpus.active_scope_pointer;
CREATE TRIGGER guard_active_scope_pointer_membership
BEFORE INSERT OR UPDATE ON corpus.active_scope_pointer
FOR EACH ROW EXECUTE FUNCTION corpus.guard_active_scope_pointer_membership();

-- Append-only audit of every scope takeover. Reconstructing the 2026-07-18
-- incident required reading release_objects.created_at; this makes the next one
-- answerable directly ("who last served us/statute, and what displaced it").
CREATE TABLE IF NOT EXISTS corpus.scope_activation_history (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  jurisdiction text NOT NULL,
  document_class text NOT NULL,
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  previous_release_name text,
  previous_content_sha256 text,
  activated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scope_activation_history_scope
  ON corpus.scope_activation_history (jurisdiction, document_class, activated_at DESC);

ALTER TABLE corpus.active_scope_pointer ENABLE ROW LEVEL SECURITY;
ALTER TABLE corpus.scope_activation_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS active_scope_pointer_read ON corpus.active_scope_pointer;
CREATE POLICY active_scope_pointer_read
  ON corpus.active_scope_pointer
  FOR SELECT TO anon, authenticated
  USING (true);

DROP POLICY IF EXISTS scope_activation_history_read ON corpus.scope_activation_history;
CREATE POLICY scope_activation_history_read
  ON corpus.scope_activation_history
  FOR SELECT TO anon, authenticated
  USING (true);

GRANT SELECT ON corpus.active_scope_pointer TO anon, authenticated, service_role;
GRANT SELECT ON corpus.scope_activation_history TO anon, authenticated, service_role;
-- Only the SECURITY DEFINER activation RPC (owned by postgres) writes serving
-- state. The staging service role must never move the pointer directly.
REVOKE INSERT, UPDATE, DELETE ON corpus.active_scope_pointer FROM service_role;
REVOKE INSERT, UPDATE, DELETE ON corpus.scope_activation_history FROM service_role;

-- ---------------------------------------------------------------------------
-- Seed the scope map from whatever the singleton serves at apply time, so
-- serving is byte-for-byte continuous across the migration. DISTINCT collapses
-- the released release's multi-version pairs to one pointer row per
-- (jurisdiction, document_class); the serving view rejoins every version. On the
-- production database this reinstates the release the pointer currently names
-- (e.g. us-rulespec-2026-07-17: 85 pointer rows serving all 165 scopes).
-- ---------------------------------------------------------------------------
INSERT INTO corpus.active_scope_pointer (
  jurisdiction, document_class, release_name, content_sha256, activated_at
)
SELECT DISTINCT
  scopes.jurisdiction,
  scopes.document_class,
  scopes.release_name,
  pointer.content_sha256,
  now()
FROM corpus.release_scopes scopes
JOIN corpus.active_release_pointer pointer
  ON pointer.pointer_name = 'production'
 AND pointer.release_name = scopes.release_name
ON CONFLICT (jurisdiction, document_class) DO NOTHING;

INSERT INTO corpus.scope_activation_history (
  jurisdiction, document_class, release_name, content_sha256, activated_at
)
SELECT
  jurisdiction, document_class, release_name, content_sha256, activated_at
FROM corpus.active_scope_pointer;

-- ---------------------------------------------------------------------------
-- Serving views + row-level security now follow the per-scope map. Column list
-- and shape are unchanged, so current_provisions / legacy_provisions /
-- current_provision_counts inherit correct per-scope semantics with no edits.
-- Every version the active release carries for a pair is served.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW corpus.current_release_scopes AS
SELECT
  scopes.release_name,
  scopes.jurisdiction,
  scopes.document_class,
  scopes.version,
  scopes.synced_at
FROM corpus.release_scopes scopes
JOIN corpus.active_scope_pointer active
  ON active.jurisdiction = scopes.jurisdiction
 AND active.document_class = scopes.document_class
 AND active.release_name = scopes.release_name;

DROP POLICY IF EXISTS release_scopes_anon_read ON corpus.release_scopes;
CREATE POLICY release_scopes_anon_read
  ON corpus.release_scopes
  FOR SELECT TO anon
  USING (
    EXISTS (
      SELECT 1
      FROM corpus.active_scope_pointer active
      WHERE active.jurisdiction = release_scopes.jurisdiction
        AND active.document_class = release_scopes.document_class
        AND active.release_name = release_scopes.release_name
    )
  );

DROP POLICY IF EXISTS release_scopes_authenticated_read ON corpus.release_scopes;
CREATE POLICY release_scopes_authenticated_read
  ON corpus.release_scopes
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM corpus.active_scope_pointer active
      WHERE active.jurisdiction = release_scopes.jurisdiction
        AND active.document_class = release_scopes.document_class
        AND active.release_name = release_scopes.release_name
    )
  );

-- ---------------------------------------------------------------------------
-- Dry-run preview: what a signed release would displace, without writing.
-- Signature verification stays in the caller (verify_release_object); this only
-- reports, per (jurisdiction, document_class) pair the release covers, the
-- current active release and whether activation would change it.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION corpus.preview_corpus_release_activation(p_release_object jsonb)
RETURNS TABLE (
  jurisdiction text,
  document_class text,
  current_release_name text,
  current_content_sha256 text,
  changes boolean
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = corpus, public
AS $$
  WITH pairs AS (
    SELECT DISTINCT
      scope.value ->> 'jurisdiction' AS jurisdiction,
      scope.value ->> 'document_class' AS document_class
    FROM jsonb_array_elements(COALESCE(p_release_object #> '{content,scopes}', '[]'::jsonb))
      AS scope(value)
  )
  SELECT
    pairs.jurisdiction,
    pairs.document_class,
    active.release_name,
    active.content_sha256,
    (active.release_name IS DISTINCT FROM (p_release_object ->> 'release')) AS changes
  FROM pairs
  LEFT JOIN corpus.active_scope_pointer active
    ON active.jurisdiction = pairs.jurisdiction
   AND active.document_class = pairs.document_class
  ORDER BY 1, 2
$$;

GRANT EXECUTE ON FUNCTION corpus.preview_corpus_release_activation(jsonb)
  TO postgres, service_role;
REVOKE EXECUTE ON FUNCTION corpus.preview_corpus_release_activation(jsonb)
  FROM anon, authenticated, PUBLIC;

-- ---------------------------------------------------------------------------
-- Activation RPC. Every validation from the singleton version is preserved
-- verbatim (schema, name, sha, signature, scope-array shape, duplicate scopes,
-- SHARE locks, per-scope staged count + projection-digest recheck, release
-- object + membership insertion and equality check). Only the pointer move
-- changes: it repoints the per-(jurisdiction, document_class) map for this
-- release's pairs and records each takeover, instead of overwriting one global
-- pointer.
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
  activated_scopes jsonb := '[]'::jsonb;
  reaffirmed_scopes jsonb := '[]'::jsonb;
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
