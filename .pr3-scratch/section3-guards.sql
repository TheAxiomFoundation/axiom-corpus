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
