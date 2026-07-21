import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-wi-foodshare-manual.yaml"
VERSION = "2026-07-21-wi-foodshare-manual"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-wi/manual"
    / VERSION
    / "official-documents/wi-dhs-foodshare-handbook-26-01.pdf"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-wi/manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-wi/manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-wi/manual" / f"{VERSION}.json"

EXPECTED_SOURCE_SHA256 = "6e76d7710eee559264bf019adadd5b9faa15ed79cf7a74311e245e54ab2850d7"
EXPECTED_PAGE_COUNT = 372
EXPECTED_ROW_COUNT = EXPECTED_PAGE_COUNT + 1


def _document() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"][0]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_wisconsin_manifest_pins_current_official_handbook() -> None:
    document = _document()

    assert document["source_url"] == (
        "https://www.emhandbooks.wisconsin.gov/fsh/home.htm"
    )
    assert document["download_url"].endswith("p16001-26-01.pdf")
    assert document["source_as_of"] == "2026-07-21"
    assert document["expression_date"] == "2026-04-15"
    assert document["metadata"]["primary_source"] is True
    assert document["metadata"]["program"] == "FoodShare"
    assert document["metadata"]["release"] == "26-01"
    assert document["metadata"]["source_document_release_date"] == "2026-04-15"


def test_wisconsin_source_and_generated_scope_are_complete() -> None:
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    with fitz.open(SOURCE_PATH) as pdf:
        assert pdf.page_count == EXPECTED_PAGE_COUNT
        assert "FoodShare Handbook" in pdf[0].get_text()
        assert "Release 26-01" in pdf[0].get_text()
        assert all(page.get_text().strip() for page in pdf)

    assert sha256_file(SOURCE_PATH) == EXPECTED_SOURCE_SHA256
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert rows[0]["kind"] == "document"
    assert [row["metadata"]["page_number"] for row in rows[1:]] == list(
        range(1, EXPECTED_PAGE_COUNT + 1)
    )
    assert any("Release Date: 04/15/2026" in row["body"] for row in rows[1:])
    assert any("Effective Date: 04/15/2026" in row["body"] for row in rows[1:])
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT
