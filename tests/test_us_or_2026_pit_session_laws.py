from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-07-24-or-pit-session-laws"
MANIFEST_PATH = (
    REPO_ROOT / "manifests/us-or-2026-pit-session-laws-official-documents.yaml"
)
SOURCE_ROOT = (
    REPO_ROOT / f"data/corpus/sources/us-or/statute/{VERSION}/official-documents"
)
INVENTORY_PATH = REPO_ROOT / f"data/corpus/inventory/us-or/statute/{VERSION}.json"
PROVISIONS_PATH = REPO_ROOT / f"data/corpus/provisions/us-or/statute/{VERSION}.jsonl"
COVERAGE_PATH = REPO_ROOT / f"data/corpus/coverage/us-or/statute/{VERSION}.json"

SB1507_CITATION = "us-or/statute/session-laws/2026/sb1507"
HB4084_CITATION = "us-or/statute/session-laws/2026/hb4084"
SB1510_CITATION = "us-or/statute/session-laws/2026/sb1510"
SB1507_SHA256 = "db9c1057f6a67d5cb5416825614192f040e70a6b424c96723d7f2769d21c40cb"
HB4084_SHA256 = "f3e11dedf65f2d079f3f30865675d0da5f495ea864dcc52c686e9a99f72c83a3"
SB1510_SHA256 = "0e323352cafe8a27bb75194f2185ff7b58dcb1603ff6986e9acebfb18a20f419"


def _provisions() -> list[dict[str, object]]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def _normalized_body(record: dict[str, object]) -> str:
    body = record["body"]
    assert isinstance(body, str)
    dehyphenated = re.sub(r"(?<=\w)-\s+(?=\w)", "", body)
    return " ".join(dehyphenated.split())


def test_oregon_2026_session_law_sources_and_coverage_are_complete() -> None:
    source_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(SOURCE_ROOT.glob("*.pdf"))
    }
    assert source_hashes == {
        "us-or-2026-sb1507-chapter-142.pdf": SB1507_SHA256,
        "us-or-2026-hb4084-chapter-50.pdf": HB4084_SHA256,
        "us-or-2026-sb1510-chapter-75.pdf": SB1510_SHA256,
    }

    coverage = json.loads(COVERAGE_PATH.read_text())
    assert coverage == {
        "complete": True,
        "document_class": "statute",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us-or",
        "matched_count": 6,
        "missing_from_provisions": [],
        "provision_count": 6,
        "source_count": 6,
        "version": VERSION,
    }
    assert [record["citation_path"] for record in _provisions()] == [
        SB1507_CITATION,
        f"{SB1507_CITATION}/document-1",
        HB4084_CITATION,
        f"{HB4084_CITATION}/document-1",
        SB1510_CITATION,
        f"{SB1510_CITATION}/document-1",
    ]


def test_oregon_2026_session_law_manifest_uses_chaptered_primary_sources() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    by_source_id = {document["source_id"]: document for document in documents}
    assert set(by_source_id) == {
        "us-or-2026-sb1507-chapter-142",
        "us-or-2026-hb4084-chapter-50",
        "us-or-2026-sb1510-chapter-75",
    }

    sb1507 = by_source_id["us-or-2026-sb1507-chapter-142"]
    assert sb1507["source_url"].endswith("/2026orLaw0142.pdf")
    assert sb1507["expression_date"] == "2026-04-09"
    assert sb1507["citation_path"] == SB1507_CITATION
    assert sb1507["metadata"]["primary_source"] is True
    assert sb1507["metadata"]["chapter_number"] == "142"

    hb4084 = by_source_id["us-or-2026-hb4084-chapter-50"]
    assert hb4084["source_url"].endswith("/2026orLaw0050.pdf")
    assert hb4084["expression_date"] == "2026-03-31"
    assert hb4084["citation_path"] == HB4084_CITATION
    assert hb4084["metadata"]["primary_source"] is True
    assert hb4084["metadata"]["chapter_number"] == "50"
    assert hb4084["metadata"]["legal_authority_url"].endswith(
        "/Measures/Overview/HB4084"
    )

    sb1510 = by_source_id["us-or-2026-sb1510-chapter-75"]
    assert sb1510["source_url"].endswith("/2026orLaw0075.pdf")
    assert sb1510["expression_date"] == "2026-03-31"
    assert sb1510["citation_path"] == SB1510_CITATION
    assert sb1510["metadata"]["primary_source"] is True
    assert sb1510["metadata"]["chapter_number"] == "75"
    assert sb1510["metadata"]["legal_authority_url"].endswith(
        "/Downloads/MeasureDocument/SB1510"
    )


def test_sb1507_preserves_2026_modifications_eitc_and_jobs_credit() -> None:
    body = _normalized_body(_provisions()[1])
    assert "qualified passenger vehicle loan interest" in body
    assert "qualified small business stock" in body
    assert "section 168(k) of the Internal Revenue Code" in body
    assert "[nine] 14 percent of the earned income credit" in body
    assert "[12] 17 percent of the earned income credit" in body
    assert "Sections 2 and 5 of this 2026 Act" in body
    assert "apply to tax years beginning on or after January 1, 2026" in body
    assert "$1,000 for each net new job" in body
    assert "may not receive a credit for more than 10 new jobs" in body
    assert "may not exceed the tax liability of the taxpayer" in body
    assert "$12.5 million for any tax year" in body
    assert "before January 1, 2032" in body
    assert "subject of a referendum petition" in body
    assert "Approved by the Governor April 9, 2026" in body
    assert "Effective date June 5, 2026" in body


def test_hb4084_preserves_final_qualified_industry_jobs_credit() -> None:
    body = _normalized_body(_provisions()[3])
    assert "If Senate Bill 1507 becomes law" in body
    assert "“Qualified industry” means" in body
    assert "engaged in a qualified industry as a primary business" in body
    assert "each new job in Oregon created by the taxpayer" in body
    assert "during the tax year in a qualified industry" in body
    assert "Is engaged as the taxpayer’s primary business in a qualified industry" in body
    assert "Further define the term “qualified industry”" in body
    assert "Approved by the Governor March 31, 2026" in body
    assert "Effective date June 5, 2026" in body


def test_sb1510_preserves_pte_election_credit_extension_and_overpayment() -> None:
    body = _normalized_body(_provisions()[5])
    assert "A pass-through entity may elect to be liable for and pay" in body
    assert "pass-through business alternative income tax" in body
    assert "eligible for the credit allowed under section 8" in body
    assert "overpayment credited against an installment of estimated tax" in body
    assert "before January 1, [2026] 2028" in body
    assert "apply to overpayments made before January 31, 2028" in body
    assert "Approved by the Governor March 31, 2026" in body
    assert "Effective date June 5, 2026" in body


def test_inventory_pins_exact_source_hashes_and_expression_dates() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    by_citation = {item["citation_path"]: item for item in inventory}
    assert len(inventory) == len(by_citation) == 6

    for citation in (SB1507_CITATION, f"{SB1507_CITATION}/document-1"):
        assert by_citation[citation]["sha256"] == SB1507_SHA256
        assert by_citation[citation]["metadata"]["approval_date"] == "2026-04-09"
    for citation in (HB4084_CITATION, f"{HB4084_CITATION}/document-1"):
        assert by_citation[citation]["sha256"] == HB4084_SHA256
        assert by_citation[citation]["metadata"]["approval_date"] == "2026-03-31"
    for citation in (SB1510_CITATION, f"{SB1510_CITATION}/document-1"):
        assert by_citation[citation]["sha256"] == SB1510_SHA256
        assert by_citation[citation]["metadata"]["approval_date"] == "2026-03-31"

    provisions = {record["citation_path"]: record for record in _provisions()}
    assert provisions[SB1507_CITATION]["expression_date"] == "2026-04-09"
    assert provisions[SB1510_CITATION]["expression_date"] == "2026-03-31"
