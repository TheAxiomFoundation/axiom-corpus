import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-pa-snap-handbook.yaml"
QUEUE_PATH = REPO_ROOT / "manifests" / "state-snap-manual-agent-queue.yaml"
VERSION = "2026-07-21-pa-snap-handbook"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-pa" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-pa" / "manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-pa" / "manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-pa" / "manual" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 297
EXPECTED_BLOCK_COUNT = 758
EXPECTED_ROW_COUNT = EXPECTED_DOCUMENT_COUNT + EXPECTED_BLOCK_COUNT
EXPECTED_FAMILY_COUNT = 33
EXPECTED_SOURCE_BYTES = 5_095_767
EXPECTED_SOURCE_AGGREGATE = (
    "98aadcd8f4cd9e3da755eb7efb59851984e615d0d8996425a5d6f41b88f7fc02"
)


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _inventory() -> list[dict]:
    return json.loads(INVENTORY_PATH.read_text())["items"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_pennsylvania_manifest_pins_complete_current_handbook_boundary() -> None:
    documents = _documents()
    families = {
        urlparse(document["source_url"]).path.split("/")[-2] for document in documents
    }

    assert len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len(families) == EXPECTED_FAMILY_COUNT
    assert [document["metadata"]["toc_order"] for document in documents] == list(
        range(1, EXPECTED_DOCUMENT_COUNT + 1)
    )
    assert len({document["source_id"] for document in documents}) == EXPECTED_DOCUMENT_COUNT
    assert len({document["source_url"] for document in documents}) == EXPECTED_DOCUMENT_COUNT
    assert all(document["source_as_of"] == "2026-07-21" for document in documents)
    assert all(document["expression_date"] == "2026-07-21" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(document["metadata"]["program"] == "SNAP" for document in documents)


def test_pennsylvania_retained_sources_match_inventory_and_aggregate() -> None:
    inventory = _inventory()
    document_items = [item for item in inventory if item["metadata"]["kind"] == "document"]
    source_files = sorted(path for path in SOURCE_ROOT.rglob("*") if path.is_file())

    assert len(document_items) == len(source_files) == EXPECTED_DOCUMENT_COUNT
    assert sum(path.stat().st_size for path in source_files) == EXPECTED_SOURCE_BYTES
    for item in document_items:
        source_path = CORPUS_ROOT / item["source_path"]
        assert source_path.is_file()
        assert item["sha256"] == sha256_file(source_path)

    ordered_hashes = "".join(item["sha256"] for item in document_items)
    assert hashlib.sha256(ordered_hashes.encode()).hexdigest() == EXPECTED_SOURCE_AGGREGATE


def test_pennsylvania_generated_scope_has_complete_coverage() -> None:
    inventory = _inventory()
    rows = _provisions()
    coverage = json.loads(COVERAGE_PATH.read_text())

    assert len(inventory) == len(rows) == EXPECTED_ROW_COUNT
    assert sum(row["kind"] == "document" for row in rows) == EXPECTED_DOCUMENT_COUNT
    assert sum(row["kind"] == "block" for row in rows) == EXPECTED_BLOCK_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT


def test_pennsylvania_queue_limits_current_status_to_handbook_snapshot() -> None:
    states = yaml.safe_load(QUEUE_PATH.read_text())["states"]
    state = next(item for item in states if item["jurisdiction"] == "us-pa")

    assert state["queue_status"] == "published_current"
    assert state["target_scope"] == {
        "jurisdiction": "us-pa",
        "document_class": "manual",
        "version": VERSION,
    }
    assert "Complete current 297-topic Pennsylvania SNAP Handbook HTML snapshot" in state[
        "notes"
    ]
    assert "does not claim complete Pennsylvania SNAP legal authority" in state["notes"]
    assert "Chapter 501" in state["notes"]
    assert "operations-memorandum" in state["notes"]
    assert "cross-manual dependencies" in state["notes"]
