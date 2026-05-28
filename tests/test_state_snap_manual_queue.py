import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TARGET_MANIFEST_PATHS = {
    "us-co": "us-co/regulation/10-ccr-2506-1",
    "us-oh": "us-oh/regulation/agency-5101-4",
}


def test_published_state_snap_queue_entries_are_release_backed():
    queue_path = REPO_ROOT / "manifests" / "state-snap-manual-agent-queue.yaml"
    release_path = REPO_ROOT / "manifests" / "releases" / "current.json"

    queue = yaml.safe_load(queue_path.read_text())["states"]
    release_scopes = json.loads(release_path.read_text())["scopes"]
    release_keys = {
        (scope["jurisdiction"], scope["document_class"], str(scope["version"]))
        for scope in release_scopes
    }

    missing_manifests = []
    missing_release_scopes = []
    missing_manifest_paths = []
    for state in queue:
        if state.get("queue_status") != "published_current":
            continue

        manifest = state.get("target_manifest")
        if not manifest or not (REPO_ROOT / manifest).exists():
            missing_manifests.append(state["jurisdiction"])

        target_scope = state.get("target_scope")
        if not target_scope:
            missing_release_scopes.append((state["jurisdiction"], "missing target_scope"))
            continue
        key = (
            target_scope["jurisdiction"],
            target_scope["document_class"],
            str(target_scope["version"]),
        )
        if key not in release_keys:
            missing_release_scopes.append(key)

        expected_path = EXPECTED_TARGET_MANIFEST_PATHS.get(state["jurisdiction"])
        if manifest and expected_path:
            manifest_payload = yaml.safe_load((REPO_ROOT / manifest).read_text())
            documents = manifest_payload.get("documents", [])
            citation_paths = {document.get("citation_path") for document in documents}
            if expected_path not in citation_paths:
                missing_manifest_paths.append((state["jurisdiction"], expected_path))

    assert missing_manifests == []
    assert missing_release_scopes == []
    assert missing_manifest_paths == []
