from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TARGET_MANIFEST_PATHS = {
    "us-co": "us-co/regulation/10-ccr-2506-1",
    "us-oh": "us-oh/regulation/agency-5101-4",
}


def test_reviewed_state_snap_queue_entries_have_source_manifests():
    queue_path = REPO_ROOT / "manifests" / "state-snap-manual-agent-queue.yaml"

    queue = yaml.safe_load(queue_path.read_text())["states"]

    missing_manifests = []
    missing_target_scopes = []
    missing_manifest_paths = []
    for state in queue:
        if state.get("queue_status") != "published_current":
            continue

        manifest = state.get("target_manifest")
        if not manifest or not (REPO_ROOT / manifest).exists():
            missing_manifests.append(state["jurisdiction"])

        target_scope = state.get("target_scope")
        if not target_scope:
            missing_target_scopes.append((state["jurisdiction"], "missing target_scope"))
            continue
        if not all(target_scope.get(key) for key in ("jurisdiction", "document_class", "version")):
            missing_target_scopes.append(state["jurisdiction"])

        expected_path = EXPECTED_TARGET_MANIFEST_PATHS.get(state["jurisdiction"])
        if manifest and expected_path:
            manifest_payload = yaml.safe_load((REPO_ROOT / manifest).read_text())
            documents = manifest_payload.get("documents", [])
            citation_paths = {document.get("citation_path") for document in documents}
            if expected_path not in citation_paths:
                missing_manifest_paths.append((state["jurisdiction"], expected_path))

    assert missing_manifests == []
    assert missing_target_scopes == []
    assert missing_manifest_paths == []
