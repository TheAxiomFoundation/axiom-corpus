import json
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ok-snap-rules.yaml"
VERSION = "2026-07-21-ok-snap-rules"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-ok/regulation"
    / VERSION
    / "official-documents/ok-oac-340-50-snap-rules.json"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-ok/regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-ok/regulation" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-ok/regulation" / f"{VERSION}.json"

EXPECTED_SOURCE_SHA256 = "8b780c6e3ff25042d379680561271bf204cb5b8aa4dae3d17f756a93fbd944b2"
EXPECTED_API_RECORD_COUNT = 205
EXPECTED_RULE_COUNT = 77
EXPECTED_ROW_COUNT = EXPECTED_RULE_COUNT + 1


def _document() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"][0]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_oklahoma_manifest_pins_current_official_rules_api() -> None:
    document = _document()

    assert document["source_url"] == "https://rules.ok.gov/home"
    assert document["download_url"] == (
        "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum"
        "?titleNum=340&chapterNum=50"
    )
    assert document["source_as_of"] == "2026-07-21"
    assert document["expression_date"] == "2026-07-21"
    assert document["metadata"]["primary_source"] is True
    assert document["metadata"]["program"] == "SNAP"


def test_oklahoma_source_and_generated_scope_are_complete() -> None:
    source_records = json.loads(SOURCE_PATH.read_text())
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    assert sha256_file(SOURCE_PATH) == EXPECTED_SOURCE_SHA256
    assert len(source_records) == EXPECTED_API_RECORD_COUNT
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert rows[0]["kind"] == "document"
    assert all(row["body"] for row in rows[1:])
    assert all(
        row["source_path"] == str(SOURCE_PATH.relative_to(CORPUS_ROOT)) for row in rows
    )
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT
