import hashlib
import json
import re
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ms-snap-manual.yaml"
VERSION = "2026-07-17-ms-snap-policy-manual"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources"
    / "us-ms"
    / "manual"
    / VERSION
    / "official-documents"
    / "ms-mdhs-snap-policy-manual-part-14.pdf"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ms" / "manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-ms" / "manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-ms" / "manual" / f"{VERSION}.json"
SOURCE_SHA256 = "1093741e8c95d9b60ea5499242a43dcd07cb9433aaca1de88c82b719a6498764"
EXPECTED_RULE_COUNT = 384


def _document() -> dict:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    assert len(documents) == 1
    return documents[0]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_mississippi_manifest_pins_official_current_manual() -> None:
    document = _document()

    assert document["source_url"] == (
        "https://www.sos.ms.gov/adminsearch/ACCode/00000331c.pdf"
    )
    assert document["source_as_of"] == "2026-07-17"
    assert document["expression_date"] == "2025-12-20"
    assert document["metadata"]["source_sha256"] == SOURCE_SHA256
    assert document["metadata"]["primary_source"] is True
    assert document["metadata"]["federal_program"] == "SNAP"
    assert document["extraction"] == {
        "segmentation": "labeled_sections",
        "section_heading_pattern": r"^Rule (?P<label>\d+\.\d+) (?P<heading>.+)$",
        "section_heading_requires_bold": True,
        "drop_line_patterns": [r"^\d{1,3}$", r"^Part 14 Chapter \d+:.*$"],
    }


def test_mississippi_retains_complete_official_pdf() -> None:
    assert hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == SOURCE_SHA256
    with fitz.open(SOURCE_PATH) as pdf:
        text = "\n".join(page.get_text() for page in pdf)
        assert pdf.page_count == 168

    assert "Revised: December 20, 2025" in text
    assert "Part 14 Chapter 35: Disaster SNAP (D-SNAP)" in text


def test_mississippi_scope_extracts_every_numbered_rule_once() -> None:
    provisions = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    rules = [row for row in provisions if row["kind"] == "section"]
    labels = [row["metadata"]["section_label"] for row in rules]

    assert len(provisions) == len(inventory) == EXPECTED_RULE_COUNT + 1
    assert len(rules) == len(labels) == len(set(labels)) == EXPECTED_RULE_COUNT
    assert labels[0] == "1.1"
    assert labels[-1] == "35.10"
    assert {"13.1", "19.1", "29.1", "31.1", "34.1", "35.1"} <= set(labels)
    assert all(re.fullmatch(r"\d+\.\d+", label) for label in labels)
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == len(provisions)
    assert coverage["provision_count"] == len(provisions)
    assert not any(
        "Source URL:" in (row.get("body") or "")
        or "Retrieved At:" in (row.get("body") or "")
        for row in provisions
    )

    rules_by_label = {row["metadata"]["section_label"]: row for row in rules}
    assert rules_by_label["9.4"]["heading"].endswith("40 Qualifying Quarters of Work.")
    assert rules_by_label["14.11"]["heading"].endswith(
        "or an Unemployment Compensation Work Requirement."
    )
    assert rules_by_label["22.1"]["heading"].endswith(
        "Fleeing Felon Disqualifications and Work Requirement Sanctions."
    )
    assert rules_by_label["14.14"]["heading"] == "14.14 Provider Determination."
    assert rules_by_label["14.14"]["body"].startswith(
        "A. The agency must ensure that E&T providers understand their responsibility"
    )
    assert "Part 14 Chapter" not in rules_by_label["1.15"]["body"]
    assert "or 165 3. Damaged" not in rules_by_label["34.7"]["body"]
    assert "D-SNAP. 167 Source" not in rules_by_label["35.4"]["body"]
    assert "questionable. 168 Source" not in rules_by_label["35.8"]["body"]
