import json
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
    missing_published_artifacts = []
    invalid_published_artifacts = []
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
            continue

        jurisdiction = target_scope["jurisdiction"]
        document_class = target_scope["document_class"]
        version = str(target_scope["version"])
        artifact_paths = {
            "coverage": REPO_ROOT
            / "data"
            / "corpus"
            / "coverage"
            / jurisdiction
            / document_class
            / f"{version}.json",
            "provisions": REPO_ROOT
            / "data"
            / "corpus"
            / "provisions"
            / jurisdiction
            / document_class
            / f"{version}.jsonl",
            "ingest_manifest": REPO_ROOT
            / ".axiom"
            / "ingest-manifests"
            / jurisdiction
            / document_class
            / f"{version}.json",
        }
        absent = sorted(name for name, path in artifact_paths.items() if not path.is_file())
        if absent:
            missing_published_artifacts.append((state["jurisdiction"], absent))
            continue

        coverage = json.loads(artifact_paths["coverage"].read_text())
        ingest_manifest = json.loads(artifact_paths["ingest_manifest"].read_text())
        applied_paths = {
            item.get("path")
            for item in ingest_manifest.get("applied_files", [])
            if isinstance(item, dict)
        }
        expected_paths = {
            path.relative_to(REPO_ROOT).as_posix()
            for name, path in artifact_paths.items()
            if name != "ingest_manifest"
        }
        signature = ingest_manifest.get("signature")
        if (
            coverage.get("complete") is not True
            or coverage.get("jurisdiction") != jurisdiction
            or coverage.get("document_class") != document_class
            or str(coverage.get("version")) != version
            or ingest_manifest.get("jurisdiction") != jurisdiction
            or ingest_manifest.get("document_class") != document_class
            or str(ingest_manifest.get("version")) != version
            or not isinstance(signature, dict)
            or signature.get("algorithm") != "ed25519"
            or not isinstance(signature.get("value"), str)
            or not signature["value"]
            or not expected_paths <= applied_paths
        ):
            invalid_published_artifacts.append(state["jurisdiction"])

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
    assert missing_published_artifacts == []
    assert invalid_published_artifacts == []
