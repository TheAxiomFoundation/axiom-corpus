import hashlib
import json
from pathlib import Path

import yaml

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-wa-eaz-manual.yaml"
QUEUE_PATH = REPO_ROOT / "manifests" / "state-snap-manual-agent-queue.yaml"
VERSION = "2026-07-21-wa-eaz-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-wa" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-wa" / "manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-wa" / "manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-wa" / "manual" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 200
EXPECTED_BLOCK_COUNT = 1_065
EXPECTED_ROW_COUNT = EXPECTED_DOCUMENT_COUNT + EXPECTED_BLOCK_COUNT
EXPECTED_SOURCE_BYTES = 20_353_997
EXPECTED_URL_AGGREGATE = "4b2eaaae9969afdca2d4aa2edb5984fca75f8bf26e9cf303a4f45aa3cc527a44"
EXPECTED_SOURCE_AGGREGATE = "91b5cbd4bd138f2a612379b6cbc0743dec0513830c6dbc94127bb8ac64c0966a"
COMPANION_URLS = {
    "https://www.dshs.wa.gov/esa/eligibility-z-manual-ea-z/eligibility-z-ea-z-manual-revisions",
    "https://www.dshs.wa.gov/esa/eligibility-z-ea-z-manual-revisions/notification-rule-changes",
    "https://www.dshs.wa.gov/esa/eligibility-z-manual-ea-z/eligibility-z-ea-z-wac-rules-index",
}


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _inventory() -> list[dict]:
    return json.loads(INVENTORY_PATH.read_text())["items"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_washington_manifest_pins_complete_current_eaz_boundary() -> None:
    documents = _documents()
    urls = [document["source_url"] for document in documents]

    assert len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len({document["source_id"] for document in documents}) == EXPECTED_DOCUMENT_COUNT
    assert len(set(urls)) == EXPECTED_DOCUMENT_COUNT
    assert len({document["citation_path"] for document in documents}) == EXPECTED_DOCUMENT_COUNT
    assert hashlib.sha256("\n".join(urls).encode()).hexdigest() == EXPECTED_URL_AGGREGATE
    assert COMPANION_URLS.isdisjoint(urls)
    assert all(document["source_as_of"] == "2026-07-21" for document in documents)
    assert all(document["expression_date"] == "2026-07-21" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(document["metadata"]["contains_snap_policy"] is True for document in documents)


def test_washington_retained_sources_match_inventory_and_aggregate() -> None:
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


def test_washington_html_extraction_is_deterministic_for_all_sources() -> None:
    manifest = documents_module.OfficialDocumentManifest.load(MANIFEST_PATH)
    inventory_by_citation = {item["citation_path"]: item for item in _inventory()}
    first_pass = []
    second_pass = []

    for source in manifest.documents:
        item = inventory_by_citation[source.citation_path]
        content = (CORPUS_ROOT / item["source_path"]).read_bytes()
        kwargs = {
            "source_url": source.source_url,
            "title": source.title,
            "extraction": source.extraction,
        }
        first_pass.append(documents_module._extract_blocks(content, "html", **kwargs))
        second_pass.append(documents_module._extract_blocks(content, "html", **kwargs))

    assert first_pass == second_pass
    assert sum(len(blocks) for blocks in first_pass) == EXPECTED_BLOCK_COUNT


def test_washington_generated_scope_has_complete_coverage() -> None:
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


def test_washington_queue_limits_current_status_to_eaz_snapshot() -> None:
    states = yaml.safe_load(QUEUE_PATH.read_text())["states"]
    state = next(item for item in states if item["jurisdiction"] == "us-wa")

    assert state["queue_status"] == "published_current"
    assert state["target_scope"] == {
        "jurisdiction": "us-wa",
        "document_class": "manual",
        "version": VERSION,
    }
    assert "Complete current 200-page Washington DSHS EA-Z HTML" in state["notes"]
    assert "does not claim complete Washington SNAP legal authority" in state["notes"]
    assert "rule-change notifications" in state["notes"]
    assert "WAC" in state["notes"]
    assert "federal SNAP authorities" in state["notes"]
    assert "forms and desk aids" in state["notes"]
