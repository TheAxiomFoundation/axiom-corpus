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


def test_publication_registers_signed_object_before_retaining_activation_artifact() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")

    migrate = workflow.index("python scripts/apply_release_object_staging_migration.py")
    publish = workflow.index("python scripts/publish_corpus.py")
    stage = workflow.index("python scripts/stage_release_object.py")
    retain = workflow.index("- name: Retain the signed release object for activation")
    assert migrate < publish < stage < retain
    assert "--expected-project-ref swocpijqqahhuwtuahwc" in workflow


def test_activation_gate_pipelines_fail_when_the_gate_command_fails() -> None:
    workflow = Path(".github/workflows/activate-release.yml").read_text(encoding="utf-8")

    assert workflow.count("set -o pipefail") == 1
    assert workflow.count("| tee \"$RUNNER_TEMP/release-gate.txt\"") == 1


def test_existing_signed_release_registration_is_identity_bound_and_inert() -> None:
    workflow = Path(".github/workflows/register-release-object.yml").read_text(
        encoding="utf-8"
    )

    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "environment: release-preview" in workflow
    assert "run-id: ${{ inputs.publish_run_id }}" in workflow
    assert '.path == ".github/workflows/publish.yml"' in workflow
    assert '.head_branch == "main"' in workflow
    assert '.conclusion == "success"' in workflow
    assert "AXIOM_CORPUS_RELEASE_PUBLIC_KEY" in workflow
    assert "python scripts/apply_release_activation_upload_migration.py" in workflow
    assert "python scripts/apply_release_object_staging_migration.py" in workflow
    assert "python scripts/stage_release_object.py" in workflow
    assert '--release "$RELEASE_NAME"' in workflow
    assert '--content-sha "$CONTENT_SHA"' in workflow
    assert "--expected-project-ref swocpijqqahhuwtuahwc" in workflow
    assert "activate_corpus_release" not in workflow
    assert "scripts/activate_release.py" not in workflow
    assert "actions/checkout@v" not in workflow
    assert "actions/setup-python@v" not in workflow
    assert "actions/download-artifact@v" not in workflow


def test_release_object_staging_preserves_signed_publication_time() -> None:
    migration = Path(
        "supabase/migrations/20260803175000_stage_signed_release_object.sql"
    ).read_text(encoding="utf-8")

    assert "p_release_object #>> '{content,created_at}'" in migration
    assert (
        "VALUES (v_release_name, v_content_sha, p_release_object, v_published_at)"
        in migration
    )
    assert "SET created_at = v_published_at" in migration
    assert "NEW.created_at := signed_published_at" in migration
