from __future__ import annotations

import json
from pathlib import Path

from axiom_corpus.corpus.documents import OfficialDocumentManifest
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.supabase import deterministic_provision_id

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "manifests/releases/ca-rulespec-2026-07-21-oracle-complete.json"
V2_RELEASE_PATH = (
    ROOT / "manifests/releases/ca-rulespec-2026-07-21-oracle-complete-v2.json"
)
CONTRACT_PATH = (
    ROOT / "tests/fixtures/releases/ca-rulespec-2026-07-21-complete-citations.json"
)
DEPENDENCIES_PATH = (
    ROOT / "manifests/ca-rulespec-2026-07-21-oracle-dependencies.yaml"
)
DEPENDENCIES_VERSION = "2026-07-21-ca-rulespec-oracle-dependencies"
GST_HST_CITATION = "ca/policy/cra/gst-hst-2026/rate-calculator"
TD1_CITATION = "ca/policy/cra/td1-2026/provincial-territorial-personal-credits"


def test_oracle_complete_release_adds_official_gst_hst_program_root() -> None:
    release = ReleaseManifest.load(RELEASE_PATH)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    required = {*contract["citation_paths"], GST_HST_CITATION}
    dependencies = OfficialDocumentManifest.load(DEPENDENCIES_PATH)
    assert len(release.scopes) == 1
    assert len(dependencies.documents) == 1
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

    assert len(required) == 104
    assert len(provisions) == 465
    assert required <= by_path.keys()
    assert all(by_path[path].body is None for path in required)
    document = dependencies.documents[0]
    expected_source_path = (
        f"sources/ca/policy/{version}/{DEPENDENCIES_VERSION}/"
        f"official-documents/{document.source_id}.{document.source_format}"
    )
    records = [
        record
        for record in provisions
        if record.citation_path.startswith(f"{GST_HST_CITATION}/")
    ]
    assert len(records) == 3
    assert any("Ontario 13%" in (record.body or "") for record in records)
    assert any("Nova Scotia 14%" in (record.body or "") for record in records)
    for record in records:
        assert record.source_path == expected_source_path
        assert inventory_by_path[record.citation_path].source_path == expected_source_path
        assert record.id == deterministic_provision_id(record.citation_path, version)
        assert record.parent_citation_path in by_path
        assert record.parent_id == by_path[record.parent_citation_path].id


def test_oracle_complete_v2_release_has_no_empty_primary_documents() -> None:
    release = ReleaseManifest.load(V2_RELEASE_PATH)
    assert len(release.scopes) == 1
    scope = release.scopes[0]
    provisions = load_provisions(
        ROOT
        / "data/corpus/provisions"
        / scope.jurisdiction
        / scope.document_class
        / f"{scope.version}.jsonl"
    )
    inventory = load_source_inventory(
        ROOT
        / "data/corpus/inventory"
        / scope.jurisdiction
        / scope.document_class
        / f"{scope.version}.json"
    )

    assert len(provisions) == len(inventory) == 464
    assert all(record.body is None or record.body.strip() for record in provisions)
    assert all(
        item.citation_path != f"{TD1_CITATION}/primary-document"
        for item in inventory
    )
