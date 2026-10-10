import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

import fitz
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-md-fsp-manual.yaml"
VERSION = "2026-07-17-md-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-md" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-md" / "manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-md" / "manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-md" / "manual" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 51
EXPECTED_ROW_COUNT = 379
EXPECTED_PDF_PAGE_COUNT = 157
EXPECTED_SOURCE_INDEX_SHA256 = (
    "09414c4152f2c49aaab4586e2db8916a555204b6e6754697ca8b796c4c3f1c3a"
)
CURRENT_URL_SUFFIXES = {
    "md-dhs-snap-100-household-composition": "100-Household-Composition-MAY-2026.docx.pdf",
    "md-dhs-snap-102-students": "102-Students-JAN-2026.docx.pdf",
    "md-dhs-snap-115-categorical-eligibility": "115-Categorical-Eligibility-SEPT-2025-1.pdf",
    "md-dhs-snap-200-resources": "200-Resources-JUNE-2026.pdf",
    "md-dhs-snap-211-excluded-income": "211-Excluded-Income-APRIL-2026.pdf",
    "md-dhs-snap-404-head-of-household-or-authorized-representative": (
        "404-Head-of-Household-rev-JULY-2020-1.pdf"
    ),
}


def test_maryland_snap_manifest_pins_complete_current_official_index() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    by_source = {document["source_id"]: document for document in documents}

    assert len(documents) == len(by_source) == EXPECTED_DOCUMENT_COUNT
    assert len({document["source_url"] for document in documents}) == len(documents)
    assert Counter(document["source_format"] for document in documents) == Counter(
        {"docx": 35, "pdf": 16}
    )
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(document["metadata"]["program"] == "SNAP" for document in documents)
    assert all(document["metadata"]["federal_program"] == "SNAP" for document in documents)
    assert all(
        document["metadata"]["discovered_via"]
        == "official-manual-index:maryland-dhs-snap"
        for document in documents
    )
    assert all(
        document["metadata"]["expression_date_precision"] == "month"
        and document["metadata"]["expression_date_normalization"]
        == "first_day_of_month"
        for document in documents
    )
    for source_id, suffix in CURRENT_URL_SUFFIXES.items():
        assert by_source[source_id]["source_url"].endswith(suffix)

    assert by_source["md-dhs-snap-102-students"]["expression_date"] == "2026-04-01"
    assert by_source["md-dhs-snap-403-customer-rights-and-responsibilities"][
        "expression_date"
    ] == "2024-10-01"
    assert by_source["md-dhs-snap-600-standards"]["expression_date"] == "2025-08-01"


def test_maryland_snap_scope_retains_every_source_and_complete_generated_row() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    by_source = {document["source_id"]: document for document in documents}
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    provisions = [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted((SOURCE_ROOT / "official-documents").iterdir())
    row_counts = Counter(record["source_id"] for record in provisions)
    source_index = []
    pdf_page_count = 0

    assert len(retained_files) == len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len(inventory) == len(provisions) == EXPECTED_ROW_COUNT
    assert set(row_counts) == set(by_source)
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT

    for source_id, document in by_source.items():
        source_file = SOURCE_ROOT / "official-documents" / f"{source_id}.{document['source_format']}"
        relative_source_path = source_file.relative_to(CORPUS_ROOT).as_posix()
        source_hash = sha256_file(source_file)
        source_items = [item for item in inventory if item["source_path"] == relative_source_path]
        source_rows = [row for row in provisions if row["source_id"] == source_id]

        if document["source_format"] == "pdf":
            assert source_file.read_bytes().startswith(b"%PDF-")
            with fitz.open(source_file) as pdf:
                unit_count = pdf.page_count
                page_text = [page.get_text() for page in pdf]
            assert all(text.strip() for text in page_text)
            assert "The request is blocked." not in "\n".join(page_text)
            pdf_page_count += unit_count
        else:
            assert source_file.read_bytes().startswith(b"PK")
            assert zipfile.is_zipfile(source_file)
            unit_count = row_counts[source_id] - 1

        assert len(source_items) == len(source_rows) == row_counts[source_id]
        assert all(item["sha256"] == source_hash for item in source_items)
        assert all(row["source_path"] == relative_source_path for row in source_rows)
        assert all(row["source_url"] == document["source_url"] for row in source_rows)
        assert all(row["source_as_of"] == "2026-07-17" for row in source_rows)
        assert all(
            row["expression_date"] == document["expression_date"] for row in source_rows
        )
        assert all(row["metadata"]["program"] == "SNAP" for row in source_rows)
        assert all(row["body"] for row in source_rows if row["kind"] != "document")
        source_index.append(
            (source_id, document["source_format"], unit_count, row_counts[source_id], source_hash)
        )

    index_payload = "".join(
        "\t".join(map(str, item)) + "\n" for item in sorted(source_index)
    )
    assert pdf_page_count == EXPECTED_PDF_PAGE_COUNT
    assert hashlib.sha256(index_payload.encode()).hexdigest() == EXPECTED_SOURCE_INDEX_SHA256
