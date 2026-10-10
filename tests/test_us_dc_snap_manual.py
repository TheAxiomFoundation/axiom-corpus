import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-dc-snap-manual.yaml"
VERSION = "2026-07-17-dc-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-dc" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-dc" / "manual" / f"{VERSION}.json"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-dc" / "manual" / f"{VERSION}.json"


def test_dc_snap_manifest_pins_official_fy2025_manual() -> None:
    document = yaml.safe_load(MANIFEST_PATH.read_text())["documents"][0]

    assert document["source_url"].endswith("Final%20ESA%20SNAP%20Policy%20Manual%201.24.25.pdf")
    assert document["source_as_of"] == "2026-07-17"
    assert document["expression_date"] == "2025-01-01"
    assert document["metadata"]["manual_version"] == "FY2025"
    assert document["metadata"]["manual_effective_date"] == "2025-01-01"
    assert document["metadata"]["source_last_modified"] == "2025-02-28"
    assert document["metadata"]["pdf_document_created"] == "2025-01-23"
    assert document["metadata"]["pdf_document_modified"] == "2025-01-30"
    assert document["metadata"]["discovered_via"].startswith("official-landing-page:")


def test_dc_snap_scope_retains_every_official_pdf_page() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(path for path in SOURCE_ROOT.rglob("*") if path.is_file())

    assert len(retained_files) == 1
    assert len(inventory) == 350
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 350
    assert coverage["provision_count"] == 350
    assert all(CORPUS_ROOT / item["source_path"] == retained_files[0] for item in inventory)
    assert all(item["sha256"] == sha256_file(retained_files[0]) for item in inventory)
    assert {item["citation_path"] for item in inventory[1:]} == {
        f"us-dc/manual/dhs/esa/snap-policy-manual/page-{page}" for page in range(1, 350)
    }

    with fitz.open(retained_files[0]) as pdf:
        text = "\n".join(page.get_text() for page in pdf)
        assert pdf.page_count == 349
    assert "Version FY2025" in text
    assert "January 1, 2025" in text
    assert "Chapter 26. Appendix 2" in text
