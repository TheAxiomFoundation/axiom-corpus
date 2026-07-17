import json
import re
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-nj-snap-rules.yaml"
VERSION = "2026-07-17-nj-snap-rules"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-nj/regulation"
    / VERSION
    / "official-documents/nj-dhs-njac-10-87-snap-manual.pdf"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-nj/regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-nj/regulation" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-nj/regulation" / f"{VERSION}.json"

EXPECTED_SOURCE_SHA256 = "34c913b5be2c7e64b8d7b3d9ac89563f7beba474be88a544609ba9fcd3ac2d64"
EXPECTED_CODE_SECTION_COUNT = 261
EXPECTED_BLOCK_COUNT = 265
EXPECTED_ROW_COUNT = 266
SECTION_START_RE = re.compile(r"^\u00a7\s+(?P<label>10:87-\d+\.\d+[A-Z]?)\.?\s+")


def _document() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"][0]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_new_jersey_manifest_pins_current_complete_manual() -> None:
    document = _document()

    assert document["source_url"].endswith("/SNAPManual_10.14.25.pdf")
    assert document["source_as_of"] == "2026-07-17"
    assert document["expression_date"] == "2025-10-06"
    assert document["metadata"]["primary_source"] is True
    assert document["metadata"]["program"] == "SNAP"
    assert document["metadata"]["page_count"] == 570
    assert document["metadata"]["code_section_count"] == EXPECTED_CODE_SECTION_COUNT
    assert document["metadata"]["source_sha256"] == EXPECTED_SOURCE_SHA256
    assert "courtesy" in document["metadata"]["source_note"]
    assert "not the official" in document["metadata"]["source_note"]
    assert document["extraction"]["section_heading_requires_bold"] is True
    assert document["extraction"]["allow_unstyled_repeated_section_headings"] is True


def test_new_jersey_scope_retains_every_code_section_and_appendix() -> None:
    rows = _provisions()
    sections = [row for row in rows if row["kind"] == "section"]
    code_sections = [
        row
        for row in sections
        if row["metadata"]["section_label"].startswith("10:87-")
    ]
    generated_labels = {row["metadata"]["section_label"] for row in code_sections}
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    with fitz.open(SOURCE_PATH) as pdf:
        source_labels = {
            match.group("label")
            for page in pdf
            for line in page.get_text().splitlines()
            if (match := SECTION_START_RE.match(line.strip())) is not None
        }
        assert pdf.page_count == 570

    assert sha256_file(SOURCE_PATH) == EXPECTED_SOURCE_SHA256
    assert len(source_labels) == EXPECTED_CODE_SECTION_COUNT
    assert generated_labels == source_labels
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len(sections) == EXPECTED_BLOCK_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT
    assert {row["metadata"]["section_label"] for row in sections} - source_labels == {
        "chapter-notes",
        "subchapter-12-notes",
        "subchapter-13-notes",
        "appendix-a",
    }


def test_new_jersey_sections_preserve_multipage_text_and_current_policy() -> None:
    sections = {
        row["metadata"]["section_label"]: row
        for row in _provisions()
        if row["kind"] == "section"
    }

    chapter_notes = sections["chapter-notes"]["body"]
    assert "N.J.S.A. 30:1-12" in chapter_notes
    assert "Effective: November 16, 2022" in chapter_notes
    assert "CHAPTER HISTORICAL NOTE" in chapter_notes
    assert sections["10:87-1.1A"]["metadata"]["page_end"] == 6
    assert "Actively seeking" in sections["10:87-3.17"]["body"]
    assert "CSSA" in sections["10:87-3.17"]["body"]
    assert "pursuant to N.J.A.C. 10:88-4.2" in sections["10:87-9.11"]["body"]
    assert "10:87-5.9(a)11ii" in sections["10:87-5.4"]["body"]
    assert "family cap" not in sections["10:87-5.7"]["body"].lower()
    assert "State of New Jersey mileage reimbursement rate" in sections["10:87-5.10"]["body"]
    assert sections["10:87-5.10"]["metadata"]["page_end"] > sections["10:87-5.10"]["metadata"]["page_start"]
    assert "domestic partnership" in sections["10:87-2.2"]["body"]
    assert "State SNAP Minimum Benefit Program" in sections["10:87-13.4"]["body"]
    assert sections["appendix-a"]["body"]
    assert not any(
        marker in (row.get("body") or "")
        for row in sections.values()
        for marker in (
            "This file includes all Regulations",
            "End of Document",
            "Copyright " + chr(169) + " 2025",
        )
    )
