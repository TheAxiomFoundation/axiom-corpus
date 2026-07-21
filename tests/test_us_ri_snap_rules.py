import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ri-snap-rules.yaml"
VERSION = "2026-07-21-ri-snap-rules"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-ri/regulation"
    / VERSION
    / "official-documents/ri-dhs-snap-218-20-00-1.pdf"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-ri/regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-ri/regulation" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-ri/regulation" / f"{VERSION}.json"

EXPECTED_SOURCE_SHA256 = "875e5a2a0f5d0ef62d2566f46323be71164bd7a14fa1c2e825985eddb6224983"
EXPECTED_PAGE_COUNT = 272
EXPECTED_ROW_COUNT = EXPECTED_PAGE_COUNT + 1


def _document() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"][0]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_rhode_island_manifest_pins_current_signed_regulation() -> None:
    document = _document()

    assert document["source_url"] == (
        "https://rules.sos.ri.gov/regulations/part/218-20-00-1"
    )
    assert document["download_url"].endswith("REG_13456_20260316083651496.pdf")
    assert document["source_as_of"] == "2026-07-21"
    assert document["expression_date"] == "2026-04-05"
    assert document["metadata"]["primary_source"] is True
    assert document["metadata"]["legal_identifier"] == "218-RICR-20-00-1"
    assert document["metadata"]["agency_signing_date"] == "2026-03-13"
    assert document["metadata"]["department_of_state_signing_date"] == "2026-03-16"
    assert document["metadata"]["regulation_effective_date"] == "2026-04-05"


def test_rhode_island_source_and_generated_scope_are_complete() -> None:
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    with fitz.open(SOURCE_PATH) as pdf:
        assert pdf.page_count == EXPECTED_PAGE_COUNT
        assert "218-RICR-20-00-1" in pdf[0].get_text()
        assert all(page.get_text().strip() for page in pdf)
        signature_page = pdf[-1].get_text()
        assert "Type of Filing: Amendment" in signature_page
        assert "04/05/2026" in signature_page
        assert "E-SIGNED by Department of State" in signature_page

    assert sha256_file(SOURCE_PATH) == EXPECTED_SOURCE_SHA256
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert rows[0]["kind"] == "document"
    assert [row["metadata"]["page_number"] for row in rows[1:]] == list(
        range(1, EXPECTED_PAGE_COUNT + 1)
    )
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT
