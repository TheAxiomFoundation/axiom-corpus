from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260722021000_chunked_release_activation_upload.sql"
)


def test_chunked_activation_transport_is_private_and_hash_verified() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS corpus.release_activation_upload_chunks" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert (
        "REVOKE ALL ON corpus.release_activation_upload_chunks\n"
        "  FROM anon, authenticated, service_role, PUBLIC"
    ) in sql
    assert "CREATE OR REPLACE FUNCTION corpus.load_release_activation_upload" in sql
    assert "sha256(convert_to(v_raw, 'UTF8'))" in sql
    assert "release activation upload is incomplete" in sql
    assert "release activation upload object digest mismatch" in sql
    assert "release activation upload identity mismatch" in sql
    assert (
        "REVOKE EXECUTE ON FUNCTION "
        "corpus.load_release_activation_upload(text, text, text, text)\n"
        "  FROM anon, authenticated, service_role, PUBLIC"
    ) in sql


def test_protected_activation_installs_transport_after_preview() -> None:
    workflow = Path(".github/workflows/activate-release.yml").read_text(encoding="utf-8")

    revalidate = workflow.index("- name: Revalidate takeover preview")
    migrate = workflow.index("- name: Ensure bounded release upload transport")
    activate = workflow.index("- name: Activate signed release")
    assert revalidate < migrate < activate
    assert "python scripts/apply_release_activation_upload_migration.py" in workflow
    assert workflow.count("SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}") == 4
