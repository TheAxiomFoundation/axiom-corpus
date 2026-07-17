import json
import re
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-de-snap-rules.yaml"
VERSION = "2026-07-17-de-snap-rules"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-de" / "regulation" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-de" / "regulation" / f"{VERSION}.json"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-de" / "regulation" / f"{VERSION}.json"


def test_delaware_snap_manifest_pins_current_official_consolidation() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]

    assert len(documents) == 1
    document = documents[0]
    assert document["source_url"] == "https://regulations.delaware.gov/AdminCode/title16/9000"
    assert document["download_url"].endswith("/35bc7e34-2cc2-40d0-a90a-cb238e3b496c")
    assert document["source_as_of"] == "2026-07-17"
    assert document["expression_date"] == "2025-12-01"
    assert document["metadata"]["latest_register_citation"] == "29 DE Reg. 531"
    assert document["metadata"]["latest_register_effective_date"] == "2025-12-01"
    assert document["metadata"]["pdf_document_modified"] == "2026-02-09"
    assert document["metadata"]["landing_page_last_modified"] == "2026-06-09"
    assert document["metadata"]["discovered_via"]
    assert document["metadata"]["discovered_via"].startswith("official-api:")


def test_delaware_snap_scope_retains_complete_official_pdf() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(path for path in SOURCE_ROOT.rglob("*") if path.is_file())

    assert len(retained_files) == 1
    assert retained_files[0].suffix == ".pdf"
    assert len(inventory) == 265
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 265
    assert coverage["provision_count"] == 265
    assert all(CORPUS_ROOT / item["source_path"] == retained_files[0] for item in inventory)
    assert all(item["sha256"] == sha256_file(retained_files[0]) for item in inventory)

    with fitz.open(retained_files[0]) as pdf:
        text = "\n".join(page.get_text() for page in pdf)
        assert pdf.page_count == 114
    source_labels = {
        match.group(1)
        for line in text.splitlines()
        if (match := re.match(r"^(9\d{3}(?:\.\d+)*)(?:\s|$)", line.strip()))
    }
    generated_labels = {
        item["citation_path"].rsplit("/", 1)[-1]
        for item in inventory
        if item["metadata"]["kind"] != "document"
    }
    assert len(source_labels) == 264
    assert generated_labels == source_labels
    assert {"9068.1", "9068.2", "9085.2", "9092", "9093.7"} <= generated_labels
    assert "9000 Food Stamp Program" in text
    assert "29 DE Reg. 531 (12/01/25)" in text
    assert "9095.18 Treasury Offset Program (TOP)" in text
