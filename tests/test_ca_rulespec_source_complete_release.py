from __future__ import annotations

import json
from pathlib import Path

from axiom_corpus.corpus.documents import OfficialDocumentManifest
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.supabase import deterministic_provision_id

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "manifests/releases/ca-rulespec-2026-07-21-source-complete.json"
CONTRACT_PATH = (
    ROOT / "tests/fixtures/releases/ca-rulespec-2026-07-21-complete-citations.json"
)
DEPENDENCIES_PATH = (
    ROOT / "manifests/ca-rulespec-2026-07-21-official-dependencies.yaml"
)
DEPENDENCIES_VERSION = "2026-07-21-ca-rulespec-official-dependencies"


def test_source_complete_release_has_composable_contracted_program_roots() -> None:
    release = ReleaseManifest.load(RELEASE_PATH)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    required = set(contract["citation_paths"])
    assert len(release.scopes) == 1
    scope = release.scopes[0]
    provisions = load_provisions(
        ROOT
        / "data/corpus/provisions"
        / scope.jurisdiction
        / scope.document_class
        / f"{scope.version}.jsonl"
    )
    by_path = {record.citation_path: record for record in provisions}

    assert len(required) == 103
    assert required <= by_path.keys()
    for citation_path in required:
        assert by_path[citation_path].body is None
        assert any(
            record.body is not None
            and record.citation_path.startswith(f"{citation_path}/")
            for record in provisions
        )


def test_source_complete_release_retains_official_dependency_closure() -> None:
    release = ReleaseManifest.load(RELEASE_PATH)
    dependencies = OfficialDocumentManifest.load(DEPENDENCIES_PATH)
    scope = release.scopes[0]
    version = scope.version
    provisions = load_provisions(
        ROOT
        / "data/corpus/provisions"
        / scope.jurisdiction
        / scope.document_class
        / f"{version}.jsonl"
    )
    inventory = load_source_inventory(
        ROOT
        / "data/corpus/inventory"
        / scope.jurisdiction
        / scope.document_class
        / f"{version}.json"
    )
    by_path = {record.citation_path: record for record in provisions}
    inventory_by_path = {item.citation_path: item for item in inventory}

    assert len(dependencies.documents) == 18
    assert len(provisions) == 461
    for document in dependencies.documents:
        citation_path = document.citation_path
        assert citation_path is not None
        expected_source_path = (
            f"sources/ca/policy/{version}/{DEPENDENCIES_VERSION}/"
            f"official-documents/{document.source_id}.{document.source_format}"
        )
        document_records = [
            record
            for record in provisions
            if record.citation_path == citation_path
            or record.citation_path.startswith(f"{citation_path}/")
        ]
        assert document_records
        assert by_path[citation_path].body is None
        for record in document_records:
            assert record.source_path == expected_source_path
            assert inventory_by_path[record.citation_path].source_path == expected_source_path
            assert record.id == deterministic_provision_id(record.citation_path, version)
            if record.parent_citation_path is not None:
                assert record.parent_citation_path in by_path
                assert record.parent_id == by_path[record.parent_citation_path].id
