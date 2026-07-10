from pathlib import Path

MIGRATION = Path("supabase/migrations/20260710180000_atomic_named_release_activation.sql")


def test_migration_installs_immutable_release_object_and_single_pointer() -> None:
    sql = MIGRATION.read_text()

    assert "CREATE TABLE IF NOT EXISTS corpus.release_objects" in sql
    assert "content_sha256 text NOT NULL UNIQUE" in sql
    assert "CREATE TABLE IF NOT EXISTS corpus.active_release_pointer" in sql
    assert "pointer_name text PRIMARY KEY CHECK (pointer_name = 'production')" in sql
    assert "CHECK (release_name <> 'current')" in sql
    assert "CREATE POLICY release_objects_public_read" in sql
    assert "FOR SELECT TO anon, authenticated\n  USING (true)" in sql


def test_current_views_follow_named_pointer_not_mutable_active_flags() -> None:
    sql = MIGRATION.read_text()

    assert "JOIN corpus.active_release_pointer pointer" in sql
    assert "pointer.release_name = scopes.release_name" in sql
    assert "ALTER TABLE corpus.release_scopes DROP COLUMN IF EXISTS active" in sql
    assert "DELETE FROM corpus.release_scopes WHERE release_name = 'current'" in sql


def test_activation_rechecks_counts_before_pointer_and_refreshes_transactionally() -> None:
    sql = MIGRATION.read_text()

    function = sql[sql.index("CREATE OR REPLACE FUNCTION corpus.activate_corpus_release") :]
    count_index = function.index("SELECT COUNT(*)::bigint INTO actual_rows")
    navigation_count_index = function.index("SELECT COUNT(*)::bigint INTO actual_navigation_rows")
    object_index = function.index("INSERT INTO corpus.release_objects")
    pointer_index = function.index("INSERT INTO corpus.active_release_pointer")
    refresh_index = function.index("REFRESH MATERIALIZED VIEW corpus.current_provision_counts")
    return_index = function.index("RETURN jsonb_build_object")

    assert (
        count_index
        < navigation_count_index
        < object_index
        < pointer_index
        < refresh_index
        < return_index
    )
    assert "actual_rows <> expected_rows" in function
    assert "actual_navigation_rows <> expected_navigation_rows" in function
    assert "RAISE EXCEPTION" in function


def test_versioned_citations_can_coexist_for_named_releases() -> None:
    sql = MIGRATION.read_text()

    assert "DROP CONSTRAINT IF EXISTS provisions_citation_path_unique" in sql
    assert "DROP CONSTRAINT IF EXISTS rules_citation_path_unique" in sql
    assert "idx_provisions_citation_path_version" in sql
    assert "ON corpus.provisions (citation_path, version)" in sql
    assert "DROP INDEX IF EXISTS corpus.idx_navigation_nodes_path" in sql
    assert "idx_navigation_nodes_path_version" in sql
    assert "ON corpus.navigation_nodes (path, version)" in sql


def test_service_role_can_only_activate_through_rpc() -> None:
    sql = MIGRATION.read_text()

    assert "REVOKE INSERT, UPDATE, DELETE ON corpus.release_objects FROM service_role" in sql
    assert "REVOKE INSERT, UPDATE, DELETE ON corpus.active_release_pointer FROM service_role" in sql
    assert "REVOKE INSERT, UPDATE, DELETE ON corpus.release_scopes FROM service_role" in sql
    assert "GRANT EXECUTE ON FUNCTION corpus.activate_corpus_release(jsonb)" in sql


def test_rows_bound_to_any_signed_release_are_immutable() -> None:
    sql = MIGRATION.read_text()

    assert "guard_released_scope_row_immutable" in sql
    assert "JOIN corpus.release_objects objects" in sql
    assert "TG_OP <> 'INSERT'" in sql
    assert "TG_OP <> 'DELETE'" in sql
    assert "OLD.jurisdiction" in sql
    assert "NEW.jurisdiction" in sql
    assert "BEFORE INSERT OR UPDATE OR DELETE ON corpus.provisions" in sql
    assert "BEFORE INSERT OR UPDATE OR DELETE ON corpus.navigation_nodes" in sql


def test_activation_stores_memberships_under_the_validated_release_name() -> None:
    sql = MIGRATION.read_text()

    assert (
        """INSERT INTO corpus.release_scopes (
    release_name,
    jurisdiction,"""
        in sql
    )
    assert (
        """SELECT
    v_release_name,
    value ->> 'jurisdiction',"""
        in sql
    )
    assert "INSERT INTO corpus.release_scopes (\n    v_release_name," not in sql
