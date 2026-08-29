"""Focused integrity checks for the Proclamation 11021 Annex IV witness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-08-29-tariff-232-proclamation-11021-annex-iv-page-43"
CITATION_PATH = "us/rulemaking/federal-register/2026-04-09/2026-06960/annex-iv/page-43"
SOURCE_SHA256 = "9657a6c4589e1013ecebbc9eaf04db0ab865efde25ddfe81c463b29e5f0180f7"
BODY_SHA256 = "8bb8ff988becea34d3e4331b35350f023e68750419a62c724b36311870218d57"


def test_proclamation_11021_annex_iv_page_43_is_source_pinned() -> None:
    source_path = (
        REPO_ROOT
        / "data/corpus/sources/us/rulemaking"
        / VERSION
        / "official-documents/Metals-ANNEXES-I-A-I-B-II-III-IV.pdf"
    )
    source = source_path.read_bytes()
    assert len(source) == 633_053
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256

    provisions_path = REPO_ROOT / "data/corpus/provisions/us/rulemaking" / f"{VERSION}.jsonl"
    records = [json.loads(line) for line in provisions_path.read_text().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["citation_path"] == CITATION_PATH
    assert record["expression_date"] == "2026-04-09"
    assert record["kind"] == "page"
    assert record["level"] == 4
    assert "parent_citation_path" not in record
    assert hashlib.sha256(record["body"].encode()).hexdigest() == BODY_SHA256
    assert "on April 6, 2026" in record["body"]
    assert "at least 15 percent of the weight of the imported article" in record["body"]
    assert "(ii) Derivative aluminum articles:" in record["body"]
    assert "7612.10.00" in record["body"]
    assert "7612.10.10" not in record["body"]
    assert record["metadata"]["effective_date"] == "2026-04-06"
    assert record["metadata"]["source_pdf_sha256"] == SOURCE_SHA256
    assert record["metadata"]["selected_pdf_pages"] == [43]
    assert record["metadata"]["selection_scope"] == (
        "single complete PDF page containing the Annex IV effective date, "
        "U.S. note 16(c) 15-percent proviso, and the page-43 portion of "
        "subdivision (c)(ii), including HTS 7612.10.00"
    )

    inventory_path = REPO_ROOT / "data/corpus/inventory/us/rulemaking" / f"{VERSION}.json"
    inventory = json.loads(inventory_path.read_text())["items"]
    assert len(inventory) == 1
    assert inventory[0]["citation_path"] == CITATION_PATH
    assert inventory[0]["sha256"] == SOURCE_SHA256

    coverage_path = REPO_ROOT / "data/corpus/coverage/us/rulemaking" / f"{VERSION}.json"
    coverage = json.loads(coverage_path.read_text())
    assert coverage == {
        "complete": True,
        "document_class": "rulemaking",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us",
        "matched_count": 1,
        "missing_from_provisions": [],
        "provision_count": 1,
        "source_count": 1,
        "version": VERSION,
    }
