import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-sd-snap-manual.yaml"
VERSION = "2026-07-21-sd-snap-manual"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-sd/manual"
    / VERSION
    / "official-documents/sd-dss-snap-policy-procedure-manual.pdf"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-sd/manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-sd/manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-sd/manual" / f"{VERSION}.json"

EXPECTED_SOURCE_SHA256 = "a52d596aa2232519464526cb70fd5dbd24a3f02ad87476c6df60ab7641316b5f"
EXPECTED_PAGE_COUNT = 339
EXPECTED_ROW_COUNT = EXPECTED_PAGE_COUNT + 1


def _document() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"][0]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_south_dakota_manifest_pins_current_official_manual() -> None:
    document = _document()

    assert document["source_url"] == (
        "https://dss.sd.gov/docs/economicassistance/snap/snapmanual.pdf"
    )
    assert document["source_as_of"] == "2026-07-21"
    assert document["expression_date"] == "2026-07-07"
    assert document["metadata"]["primary_source"] is True
    assert document["metadata"]["program"] == "SNAP"
    assert document["metadata"]["source_document_updated"] == "July 2026"


def test_south_dakota_source_and_generated_scope_are_complete() -> None:
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    with fitz.open(SOURCE_PATH) as pdf:
        assert pdf.page_count == EXPECTED_PAGE_COUNT
        assert "Updated" in pdf[0].get_text()
        assert "July" in pdf[0].get_text()
        assert "2026" in pdf[0].get_text()

    assert sha256_file(SOURCE_PATH) == EXPECTED_SOURCE_SHA256
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert rows[0]["kind"] == "document"
    assert [row["metadata"]["page_number"] for row in rows[1:]] == list(
        range(1, EXPECTED_PAGE_COUNT + 1)
    )
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT
