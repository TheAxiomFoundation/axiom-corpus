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
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-mi-bridges-manual.yaml"
VERSION = "2026-07-17-mi-bridges-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-mi" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-mi" / "manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-mi" / "manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-mi" / "manual" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 196
EXPECTED_SNAP_DOCUMENT_COUNT = 95
EXPECTED_SOURCE_SET_SHA256 = (
    "7f556800e839027ee6bc227e730df9ddc7208034c577f1ee7e91a4e81261f43a"
)
REQUIRED_SNAP_SUPPORT_SOURCES = {
    "mi-mdhhs-bridges-glossary",
    "mi-mdhhs-rfs-305",
    "mi-mdhhs-rft-250",
    "mi-mdhhs-rft-255",
    "mi-mdhhs-rft-260",
    "mi-mdhhs-rft-262",
    "mi-mdhhs-rft-295",
}


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _manual_ids_from_toc(source_id: str, manual_code: str) -> set[str]:
    toc_path = SOURCE_ROOT / "official-documents" / f"{source_id}.pdf"
    with fitz.open(toc_path) as pdf:
        text = "\n".join(page.get_text() for page in pdf)
    return set(re.findall(rf"\b{manual_code}\s+(\d+[A-Z]?)\b", text)) - {"000"}


def test_michigan_manifest_pins_current_complete_bridges_manual() -> None:
    documents = _documents()
    source_ids = {document["source_id"] for document in documents}
    source_set = "".join(
        f"{document['source_id']}:{document['metadata']['source_sha256']}\n"
        for document in documents
    ).encode()

    assert len(documents) == len(source_ids) == EXPECTED_DOCUMENT_COUNT
    assert hashlib.sha256(source_set).hexdigest() == EXPECTED_SOURCE_SET_SHA256
    assert sum(
        document["metadata"]["contains_snap_policy"] for document in documents
    ) == EXPECTED_SNAP_DOCUMENT_COUNT
    assert source_ids >= REQUIRED_SNAP_SUPPORT_SOURCES
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(
        date.fromisoformat(document["expression_date"]) <= date(2026, 7, 17)
        for document in documents
    )
    assert all(
        document["source_url"].startswith(
            "https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/"
        )
        for document in documents
    )
    assert all("/OLMWeb/exF/" not in document["source_url"] for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(
        document["metadata"]["current_effective_tree"] is True
        for document in documents
    )
    assert all(
        document["metadata"].get("federal_program") == "SNAP"
        for document in documents
        if document["metadata"]["contains_snap_policy"]
    )
    documents_by_id = {document["source_id"]: document for document in documents}
    for source_id in {"mi-mdhhs-bridges-bem-240", "mi-mdhhs-bridges-bem-630"}:
        assert documents_by_id[source_id]["metadata"]["contains_snap_policy"] is False
        assert "federal_program" not in documents_by_id[source_id]["metadata"]
    assert (
        documents_by_id["mi-mdhhs-bridges-bem-205"]["metadata"]["source_revision"]
        == "BPB 2024-025"
    )


def test_michigan_manifest_matches_retained_official_manual_tocs() -> None:
    source_ids = {document["source_id"] for document in _documents()}
    manifest_bam_ids = {
        source_id.rsplit("-", 1)[-1].upper()
        for source_id in source_ids
        if source_id.startswith("mi-mdhhs-bridges-bam-")
        and source_id != "mi-mdhhs-bridges-bam-toc"
    }
    manifest_bem_ids = {
        source_id.rsplit("-", 1)[-1].upper()
        for source_id in source_ids
        if source_id.startswith("mi-mdhhs-bridges-bem-")
        and source_id != "mi-mdhhs-bridges-bem-toc"
    }

    assert manifest_bam_ids == _manual_ids_from_toc(
        "mi-mdhhs-bridges-bam-toc", "BAM"
    )
    assert manifest_bem_ids == _manual_ids_from_toc(
        "mi-mdhhs-bridges-bem-toc", "BEM"
    )


def test_michigan_scope_retains_every_pdf_page_with_complete_coverage() -> None:
    documents = {document["source_id"]: document for document in _documents()}
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    provisions = [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(SOURCE_ROOT.glob("official-documents/*.pdf"))
    rows_by_source = Counter(row["source_id"] for row in provisions)

    assert len(retained_files) == len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len(inventory) == len(provisions) == 2310
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == 2310
    assert coverage["provision_count"] == 2310

    for source_file in retained_files:
        source_id = source_file.stem
        document = documents[source_id]
        source_hash = sha256_file(source_file)
        source_items = [
            item
            for item in inventory
            if Path(item["source_path"]).stem == source_id
        ]
        with fitz.open(source_file) as pdf:
            expected_rows = pdf.page_count + 1

        assert source_hash == document["metadata"]["source_sha256"]
        assert len(source_items) == rows_by_source[source_id] == expected_rows
        assert all(item["sha256"] == source_hash for item in source_items)
        assert all(item["source_url"] == document["source_url"] for item in source_items)

    assert not any(
        "Source URL:" in (row.get("body") or "")
        or "Retrieved At:" in (row.get("body") or "")
        for row in provisions
    )
