import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-va-snap-manual.yaml"
VERSION = "2026-07-21-va-snap-manual"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-va/manual"
    / VERSION
    / "official-documents/va-dss-snap-full-manual-2025-10-01.pdf"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-va/manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-va/manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-va/manual" / f"{VERSION}.json"

EXPECTED_SOURCE_SHA256 = "9868c25c0d17685234301783bc1833b4dab494d2380b050ab0dffb73dc4e8d8a"
EXPECTED_PAGE_COUNT = 714
EXPECTED_PAGE_ROW_COUNT = 677
EXPECTED_ROW_COUNT = EXPECTED_PAGE_ROW_COUNT + 1


def _document() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"][0]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_virginia_manifest_pins_current_official_manual() -> None:
    document = _document()

    assert document["source_url"].endswith("Entire-Manual-eff-10012025.pdf")
    assert document["source_as_of"] == "2026-07-21"
    assert document["expression_date"] == "2025-10-01"
    assert document["extraction"] == {"ocr": True, "ocr_dpi": 300}
    assert document["metadata"]["primary_source"] is True
    assert document["metadata"]["program"] == "SNAP"
    assert document["metadata"]["source_document_date"] == "2025-09-18"
    assert document["metadata"]["source_document_effective_date"] == "2025-10-01"
    assert "November 1, 2025" in document["metadata"][
        "source_document_effective_date_note"
    ]


def test_virginia_source_and_generated_scope_are_complete() -> None:
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    with fitz.open(SOURCE_PATH) as pdf:
        assert pdf.page_count == EXPECTED_PAGE_COUNT
        represented_pages = {
            page.number + 1
            for page in pdf
            if page.get_text().strip() or page.get_images(full=True)
        }

    page_rows = rows[1:]
    assert sha256_file(SOURCE_PATH) == EXPECTED_SOURCE_SHA256
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert rows[0]["kind"] == "document"
    assert len(represented_pages) == EXPECTED_PAGE_ROW_COUNT
    assert {row["metadata"]["page_number"] for row in page_rows} == represented_pages
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT


def test_virginia_image_only_appendix_pages_are_ocr_extracted() -> None:
    rows_by_pdf_page = {
        row["metadata"]["page_number"]: row for row in _provisions()[1:]
    }

    assert "First Report of Injury" in rows_by_pdf_page[709]["body"]
    assert "SEE INSTRUCTIONS ON REVERSE SIDE" in rows_by_pdf_page[709]["body"]
    assert "First Report of Injury Filing Instructions" in rows_by_pdf_page[710]["body"]
    assert "Virginia Workers" in rows_by_pdf_page[710]["body"]
    assert "requires that ALL injuries" in rows_by_pdf_page[710]["body"]
