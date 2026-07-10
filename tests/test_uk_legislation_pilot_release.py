import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPO_ROOT / "manifests" / "uk-legislation-gov-current-pilot.yaml"
PILOT_RELEASE_PATH = REPO_ROOT / "manifests" / "releases" / "uk-legislation-pilot.json"


def _release_keys(path: Path) -> set[tuple[str, str, str]]:
    payload = json.loads(path.read_text())
    return {
        (scope["jurisdiction"], scope["document_class"], str(scope["version"]))
        for scope in payload["scopes"]
    }


def test_uk_legislation_pilot_scopes_are_release_backed_and_signed():
    queue = yaml.safe_load(QUEUE_PATH.read_text())
    pilot_keys = _release_keys(PILOT_RELEASE_PATH)

    missing_pilot_release = []
    missing_signed_manifest = []
    for scope in queue["pilot_scopes"]:
        key = (scope["jurisdiction"], scope["document_class"], str(scope["version"]))
        if key not in pilot_keys:
            missing_pilot_release.append(key)
        signed_manifest = REPO_ROOT / scope["signed_manifest"]
        if not signed_manifest.exists():
            missing_signed_manifest.append(scope["signed_manifest"])

    assert missing_pilot_release == []
    assert missing_signed_manifest == []


def test_uk_legislation_pilot_artifacts_are_complete_clml():
    queue = yaml.safe_load(QUEUE_PATH.read_text())

    bad_source_formats = []
    bad_counts = []
    incomplete_coverage = []
    for scope in queue["pilot_scopes"]:
        jurisdiction = scope["jurisdiction"]
        document_class = scope["document_class"]
        version = str(scope["version"])
        inventory_path = (
            REPO_ROOT
            / "data"
            / "corpus"
            / "inventory"
            / jurisdiction
            / document_class
            / f"{version}.json"
        )
        provisions_path = (
            REPO_ROOT
            / "data"
            / "corpus"
            / "provisions"
            / jurisdiction
            / document_class
            / f"{version}.jsonl"
        )
        coverage_path = (
            REPO_ROOT
            / "data"
            / "corpus"
            / "coverage"
            / jurisdiction
            / document_class
            / f"{version}.json"
        )
        inventory = json.loads(inventory_path.read_text())["items"]
        coverage = json.loads(coverage_path.read_text())
        provision_count = sum(1 for line in provisions_path.read_text().splitlines() if line)

        formats = {item["source_format"] for item in inventory}
        if formats != {"legislation.gov.uk-clml"}:
            bad_source_formats.append((version, sorted(formats)))
        if provision_count != scope["provision_count"]:
            bad_counts.append((version, scope["provision_count"], provision_count))
        if (
            not coverage.get("complete")
            or coverage.get("source_count") != scope["provision_count"]
            or coverage.get("provision_count") != scope["provision_count"]
        ):
            incomplete_coverage.append((version, coverage))

    assert bad_source_formats == []
    assert bad_counts == []
    assert incomplete_coverage == []


def test_uk_legislation_pilot_has_unique_citation_paths():
    queue = yaml.safe_load(QUEUE_PATH.read_text())

    seen: dict[str, str] = {}
    duplicates = []
    for scope in queue["pilot_scopes"]:
        provisions_path = (
            REPO_ROOT
            / "data"
            / "corpus"
            / "provisions"
            / scope["jurisdiction"]
            / scope["document_class"]
            / f"{scope['version']}.jsonl"
        )
        for line in provisions_path.read_text().splitlines():
            if not line:
                continue
            row = json.loads(line)
            citation_path = row["citation_path"]
            version = str(scope["version"])
            prior_version = seen.setdefault(citation_path, version)
            if prior_version != version:
                duplicates.append((citation_path, prior_version, version))

    assert duplicates == []
