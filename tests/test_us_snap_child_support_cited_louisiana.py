"""Pin Louisiana's gross-income exclusion, net deduction, and 2003 rule."""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import fitz
import pytest
import yaml

from axiom_corpus.corpus import documents

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
LAC_VERSION = "2026-09-27-la-lac-title-67-part-iii-compilation-2026-08"
REGISTER_VERSION = "2026-09-27-la-register-2003-04-20-vol-29-no-4"
LAC_ROOT = "us-la/regulation/lac/67/iii"
REGISTER_ROOT = "us-la/rulemaking/louisiana-register/2003-04-20/vol-29-no-4"
LAC_SOURCE = (
    CORPUS / "sources/us-la/regulation" / LAC_VERSION / "official-documents/la-osr-lac-67-iii.docx"
)
REGISTER_SOURCE = (
    CORPUS / "sources/us-la/rulemaking" / REGISTER_VERSION
    / "official-documents/la-register-2003-04-20-vol-29-no-4.pdf"
)
SCOPES = (("regulation", LAC_VERSION, 312), ("rulemaking", REGISTER_VERSION, 146))


@cache
def _rows(document_class: str, version: str) -> dict[str, dict]:
    path = CORPUS / "provisions/us-la" / document_class / f"{version}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == len({row["citation_path"] for row in rows})
    return {row["citation_path"]: row for row in rows}


def test_louisiana_exclusion_and_deduction_remain_distinct_sections_with_history() -> None:
    rows = _rows("regulation", LAC_VERSION)
    exclusion = rows[f"{LAC_ROOT}/1980"]["body"]
    deduction = rows[f"{LAC_ROOT}/1981"]["body"]
    assert (
        "legally obligated child support payments to non-household members are excluded "
        "when determining eligibility based on gross income standards;"
    ) in exclusion
    assert (
        "Legally obligated child support payments to, or for, an individual living outside "
        "of the household must be included in the deductions from the total monthly income "
        "when a budget for SNAP eligibility is determined."
    ) in deduction
    for body in (exclusion, deduction):
        assert "AUTHORITY NOTE:" in body
        assert "HISTORICAL NOTE:" in body
    assert "LR 29:607 (April 2003)" in exclusion
    assert "LR 42:1652 (October 2016)" in exclusion
    assert "LR 21:958 (September 1995)" in deduction
    assert "LR 36:2530 (November 2010)" in deduction


def test_louisiana_whole_part_iii_matches_independent_word_section_inventory() -> None:
    with ZipFile(LAC_SOURCE) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
        footer = ElementTree.fromstring(archive.read("word/footer4.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = [
        "".join(p.itertext()) for p in document.findall("w:body/w:p", ns)
    ]
    start = paragraphs.index("Chapter 1.Confidentiality")
    end = next(
        i for i in range(start, len(paragraphs)) if paragraphs[i].startswith("Part V.")
    )
    labels = [
        match.group(1)
        for text in paragraphs[start:end]
        if (match := re.match(r"^§(\d+)\.", text))
    ]
    assert len(labels) == len(set(labels)) == 311
    rows = _rows("regulation", LAC_VERSION)
    assert set(rows) == {LAC_ROOT} | {f"{LAC_ROOT}/{label}" for label in labels}
    assert "August 2026" in "".join(footer.itertext())
    assert rows[LAC_ROOT]["expression_date"] == "2026-08-01"
    assert rows[LAC_ROOT]["metadata"]["compilation_date_precision"] == "month"


def test_louisiana_sections_reproduce_from_retained_docx() -> None:
    manifest = yaml.safe_load((ROOT / "manifests/us-la-lac-title-67-part-iii.yaml").read_text())
    blocks = documents._extract_docx_blocks(
        LAC_SOURCE.read_bytes(), extraction=manifest["documents"][0]["extraction"]
    )
    rows = _rows("regulation", LAC_VERSION)
    assert len(blocks) == 311
    for block in blocks:
        path = f"{LAC_ROOT}/{block.metadata['section_label']}"
        assert rows[path]["body"] == block.body


def test_louisiana_register_pins_the_2003_gross_income_exclusion() -> None:
    rows = _rows("rulemaking", REGISTER_VERSION)
    page = rows[f"{REGISTER_ROOT}/page-96"]
    assert (
        "Legally obligated child support payments to non- household members are excluded "
        "when determining eligibility based on gross income standards."
    ) in page["body"]
    assert "LR 29:607 (April 2003)" in page["body"]
    assert "April 20, 2003" in page["body"]
    assert page["expression_date"] == "2003-04-20"
    assert page["metadata"]["page_number"] == 96
    assert "amendment_markup" not in page["metadata"]


def test_louisiana_register_retains_every_page_with_embedded_text() -> None:
    rows = _rows("rulemaking", REGISTER_VERSION)
    with fitz.open(REGISTER_SOURCE) as pdf:
        assert len(pdf) == 145
        assert all(page.get_text().strip() for page in pdf)
    blocks = documents._extract_pdf_blocks(REGISTER_SOURCE.read_bytes(), extraction=None)
    assert len(blocks) == 145
    assert set(rows) == {REGISTER_ROOT} | {
        f"{REGISTER_ROOT}/page-{number}" for number in range(1, 146)
    }
    for block in blocks:
        assert rows[f"{REGISTER_ROOT}/page-{block.metadata['page_number']}"]["body"] == block.body


@pytest.mark.parametrize(("document_class", "version", "count"), SCOPES)
def test_louisiana_scopes_have_complete_coverage_and_no_existing_path_collisions(
    document_class: str, version: str, count: int,
) -> None:
    rows = _rows(document_class, version)
    assert len(rows) == count
    coverage = json.loads(
        (CORPUS / "coverage/us-la" / document_class / f"{version}.json").read_text()
    )
    assert coverage["complete"] is True
    new_versions = {scope[1] for scope in SCOPES}
    for path in (CORPUS / "provisions/us-la").glob("*/*.jsonl"):
        if path.stem in new_versions:
            continue
        old_paths = {json.loads(line)["citation_path"] for line in path.read_text().splitlines()}
        assert not set(rows) & old_paths, path
