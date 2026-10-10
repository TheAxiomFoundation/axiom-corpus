import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-mt-snap-manual.yaml"
VERSION = "2026-07-17-mt-snap-policy-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-mt" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-mt" / "manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-mt" / "manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-mt" / "manual" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 83
EXPECTED_PAGE_COUNT = 352
EXPECTED_ROW_COUNT = EXPECTED_DOCUMENT_COUNT + EXPECTED_PAGE_COUNT
EXPECTED_SOURCE_SET_SHA256 = "b4049b33a509d1bd80fd0fc5e2da14bbc7296f4830923e338d9776372ddeb875"


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def test_montana_manifest_pins_complete_current_official_manual() -> None:
    documents = _documents()
    source_ids = {document["source_id"] for document in documents}
    section_numbers = {document["metadata"]["official_section_number"] for document in documents}
    source_set = "".join(
        "\t".join(
            (
                document["metadata"]["official_section_number"],
                document["source_id"],
                document["source_url"],
                document["expression_date"],
                document["metadata"]["source_sha256"],
            )
        )
        + "\n"
        for document in documents
    ).encode()

    assert len(documents) == len(source_ids) == len(section_numbers) == EXPECTED_DOCUMENT_COUNT
    assert hashlib.sha256(source_set).hexdigest() == EXPECTED_SOURCE_SET_SHA256
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(
        date.fromisoformat(document["expression_date"]) <= date(2026, 7, 17)
        for document in documents
    )
    assert all(
        document["source_url"].startswith("https://dphhs.mt.gov/assets/hcsd/snapmanual/")
        for document in documents
    )
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(document["metadata"]["program"] == "SNAP" for document in documents)
    assert all(document["metadata"]["federal_program"] == "SNAP" for document in documents)
    assert Counter(document["metadata"]["discovered_via"] for document in documents) == Counter(
        {
            "official-manual-index:montana-dphhs-snap": 82,
            "official-manual-toc:montana-dphhs-snap": 1,
        }
    )

    by_section = {
        document["metadata"]["official_section_number"]: document for document in documents
    }
    assert by_section["0-1"]["source_url"].endswith("/SNAPTOC7.2026.pdf")
    assert by_section["104-1"]["source_url"].endswith("/SNAP104.1.pdf")
    assert by_section["105-1"]["source_url"].endswith("/SNAP105.1.pdf")
    assert by_section["1502-1"]["source_url"].endswith("/SNAP1501.2.pdf")
    assert by_section["1704-1"]["source_url"].endswith("/SNAP1704.1.pdf")


def test_montana_current_toc_covers_every_manifest_section() -> None:
    documents = _documents()
    toc_source = next(
        document
        for document in documents
        if document["metadata"]["official_section_number"] == "0-1"
    )
    toc_path = SOURCE_ROOT / "official-documents" / f"{toc_source['source_id']}.pdf"
    with fitz.open(toc_path) as pdf:
        text = "\n".join(page.get_text() for page in pdf)

    toc_sections = {
        line.strip().replace(".", "-")
        for line in text.splitlines()
        if re.fullmatch(r"(?:0-\d|\d{3,4}(?:[-.]\d{1,2})?)", line.strip())
    } - {"100", "200", "300", "600", "1700"}
    manifest_sections = {document["metadata"]["official_section_number"] for document in documents}

    assert toc_sections == manifest_sections
    assert "1704-1" in toc_sections


def test_montana_scope_retains_every_pdf_page_with_complete_coverage() -> None:
    documents = {document["source_id"]: document for document in _documents()}
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    provisions = [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted((SOURCE_ROOT / "official-documents").glob("*.pdf"))
    rows_by_source = Counter(row["source_id"] for row in provisions)
    total_pages = 0

    assert len(retained_files) == len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len(inventory) == len(provisions) == EXPECTED_ROW_COUNT
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT

    for source_file in retained_files:
        source_id = source_file.stem
        document = documents[source_id]
        source_hash = sha256_file(source_file)
        source_items = [item for item in inventory if Path(item["source_path"]).stem == source_id]
        source_rows = [row for row in provisions if row["source_id"] == source_id]
        with fitz.open(source_file) as pdf:
            page_text = [page.get_text() for page in pdf]
            total_pages += pdf.page_count
            expected_rows = pdf.page_count + 1

        assert source_hash == document["metadata"]["source_sha256"]
        assert all(text.strip() for text in page_text)
        assert "The request is blocked." not in "\n".join(page_text)
        assert len(source_items) == len(source_rows) == rows_by_source[source_id] == expected_rows
        assert all(item["sha256"] == source_hash for item in source_items)
        assert all(row["source_url"] == document["source_url"] for row in source_rows)
        assert all(row["expression_date"] == document["expression_date"] for row in source_rows)

    assert total_pages == EXPECTED_PAGE_COUNT
    assert not any(
        "Source URL:" in (row.get("body") or "") or "Retrieved At:" in (row.get("body") or "")
        for row in provisions
    )
