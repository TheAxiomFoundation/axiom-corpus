import hashlib
import json
from pathlib import Path

import fitz
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-la-snap-manual.yaml"
VERSION = "2026-07-17-la-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-la" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-la" / "manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-la" / "manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-la" / "manual" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 346
EXPECTED_PAGE_COUNT = 1137
EXPECTED_ROW_COUNT = 1483
EXPECTED_SOURCE_INDEX_SHA256 = (
    "52da2f004f73fed27bfb2df22867dac8cfd1da83ebb5b078d83e5b541e0e4e0a"
)


def test_louisiana_snap_manifest_pins_complete_powerdms_policy_tree() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]

    assert len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len({document["source_id"] for document in documents}) == len(documents)
    assert [document["metadata"]["discovery_ordinal"] for document in documents] == list(
        range(1, EXPECTED_DOCUMENT_COUNT + 1)
    )
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(
        document["metadata"]["discovered_via"]
        == "official-powerdms-api:ladcfs-economic-independence-policy-tree"
        for document in documents
    )
    assert all(
        document["source_url"]
        == (
            "https://public.powerdms.com/LADCFS/documents/"
            f"{document['metadata']['powerdms_document_id']}"
        )
        for document in documents
    )
    assert all(
        "Y. FORMS AND FORMS  INSTRUCTIONS"
        not in document["metadata"]["powerdms_breadcrumbs"]
        for document in documents
    )
    assert any(
        document["metadata"]["powerdms_document_id"] == "394424"
        and document["title"] == "S-0810-SNAP Forms and Notices"
        for document in documents
    )


def test_louisiana_snap_scope_retains_every_official_pdf_page() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    provisions = [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(path for path in SOURCE_ROOT.rglob("*.pdf") if path.is_file())
    expressions = {document["source_id"]: document["expression_date"] for document in documents}
    source_index = []

    assert len(retained_files) == len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len(inventory) == len(provisions) == EXPECTED_ROW_COUNT
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT

    for source_file in retained_files:
        source_id = source_file.stem
        source_hash = sha256_file(source_file)
        relative_source_path = source_file.relative_to(CORPUS_ROOT).as_posix()
        source_items = [
            item for item in inventory if item["source_path"] == relative_source_path
        ]

        assert source_file.read_bytes().startswith(b"%PDF-")
        with fitz.open(source_file) as pdf:
            page_count = pdf.page_count
            page_text = [page.get_text() for page in pdf]
        assert all(text.strip() for text in page_text)
        assert "The request is blocked." not in "\n".join(page_text)
        assert len(source_items) == page_count + 1
        assert all(item["sha256"] == source_hash for item in source_items)
        source_index.append((source_id, page_count, source_hash))

    assert sum(page_count for _, page_count, _ in source_index) == EXPECTED_PAGE_COUNT
    index_payload = "".join(
        f"{source_id}\t{page_count}\t{source_hash}\n"
        for source_id, page_count, source_hash in sorted(source_index)
    )
    assert hashlib.sha256(index_payload.encode()).hexdigest() == EXPECTED_SOURCE_INDEX_SHA256
    assert all(
        provision["expression_date"] == expressions[provision["source_id"]]
        for provision in provisions
    )
