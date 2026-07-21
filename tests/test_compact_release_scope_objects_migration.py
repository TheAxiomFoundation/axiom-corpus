from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260721102000_compact_released_scope_objects.sql"
)


def test_compact_rpc_returns_one_json_array_without_repeating_objects_per_scope() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "FUNCTION corpus.get_released_scope_object_sets(p_scopes jsonb)" in sql
    assert "RETURNS jsonb" in sql
    assert "GROUP BY scopes.release_name" in sql
    assert "'scopes', matched.scopes" in sql
    assert "'release_object', objects.release_object" in sql
    assert "ORDER BY objects.release_name" in sql
    assert "NOTIFY pgrst, 'reload schema'" in sql


def test_compact_rpc_is_service_role_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert (
        "GRANT EXECUTE ON FUNCTION corpus.get_released_scope_object_sets(jsonb)\n"
        "  TO postgres, service_role"
    ) in sql
    assert (
        "REVOKE EXECUTE ON FUNCTION corpus.get_released_scope_object_sets(jsonb)\n"
        "  FROM anon, authenticated, PUBLIC"
    ) in sql
