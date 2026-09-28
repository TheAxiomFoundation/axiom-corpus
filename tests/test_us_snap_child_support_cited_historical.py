"""Historical state PDFs retain the dated child-support rules and every page.

Each scope is a historical vintage: its citation paths carry /vintage/<date>, and
source_as_of and expression_date are that printed date (docs/corpus-pipeline.md,
"Historical vintages of state documents").
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import fitz
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
# (manifest, version, PDF page count, vintage date, basis)
SCOPES = [
    (
        "us-co-10-ccr-2506-1-2009-07-01.yaml",
        "2026-09-28-co-10-ccr-2506-1-2009-07-01",
        236,
        "2009-07-01",
        "printed_effective_date",
    ),
    (
        "us-ri-218-820-snap-rules-2014-10-01.yaml",
        "2026-09-28-ri-218-820-snap-rules-2014-10-01",
        311,
        "2014-10-01",
        "official_filing_record_effective_date",
    ),
    (
        "us-ar-snap-manual-2020-02-01.yaml",
        "2026-09-28-ar-snap-manual-2020-02-01",
        1057,
        "2020-02-01",
        "latest_printed_revision_stamp",
    ),
    (
        "us-hi-har-17-676-2012-01-06.yaml",
        "2026-09-28-hi-har-17-676-2012-01-06",
        73,
        "2012-01-06",
        "latest_printed_amendment",
    ),
]


@cache
def _scope(index: int) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    manifest, version, *_ = SCOPES[index]
    document = yaml.safe_load((REPO_ROOT / "manifests" / manifest).read_text())["documents"][0]
    scope = f"{document['jurisdiction']}/{document['document_class']}/{version}"
    path = CORPUS_ROOT / "provisions" / f"{scope}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return document, {row["citation_path"]: row for row in rows}, scope


def _page(index: int, number: int) -> str:
    document, rows, _ = _scope(index)
    return rows[f"{document['citation_path']}/page-{number}"]["body"]


def test_colorado_child_support_is_subtracted_before_the_gross_income_test() -> None:
    body = _page(0, 127)
    assert "B-4223.6 DEDUCTION FOR LEGALLY OBLIGATED CHILD SUPPORT PAID TO NONHOUSEHOLD MEMBERS" in body
    assert (
        "The child support deduction will be made from the household's total countable gross "
        "income. The deduction will be made prior to any gross income test to determine eligibility."
    ) in body
    assert "Rule Sections SB&P, 4010.11, 4230 eff. 07/01/2009." in _page(0, 236)
    assert "See Section B- 4223.6" in _page(0, 110)  # the disclosed hyphen join


def test_rhode_island_preserves_the_2005_exclusion_and_older_conflicting_wording() -> None:
    body = _page(1, 136)
    assert body.startswith("120")  # printed page = PDF page - 16 from PDF page 17
    assert _page(1, 17).startswith("1\n")
    assert _page(1, 1).startswith("Rhode Island Department of Human Services")
    assert "1008.20.22 (7 CFR 273.9) Child Support Income Exclusion REV:05/2005" in body
    assert (
        "Legally obligated child support payments made by a household member to or for a "
        "nonhousehold member are an income exclusion."
    ) in body
    assert "also count toward this deduction" in body
    assert "The SNAP allows five (5) deductions from a household's gross income" in _page(1, 132)
    body = _page(1, 145)
    assert "1010.20 (7 CFR 273.10) DETERMINING DEDUCTIONS REV:05/2005" in body
    assert (
        "Education expenses, the cost of doing business for the self-employed, and legally "
        "obligated child support paid to a person not in the household are not deductions but "
        "are instead income exclusions, and are handled in accordance with Section 1014.20.15 "
        "(student households), Section 1016.15.20 (self- employed households), and Section "
        "1008.20.22 (child support payments)."
    ) in body
    assert "1038.19 (7 CFR 273.9) CHILD SUPPORT DEDUCTION REV:09/2000" in _page(1, 288)


def test_rhode_island_filing_record_backs_the_effective_dates() -> None:
    document, rows, _ = _scope(1)
    record = rows[f"{document['citation_path']}/filing-record/block-1"]
    body = f"{record['heading']} {record['body']}"
    for text in (
        "218-820",
        "EMERGENCY RULE",
        "Effective 10/01/2014 to 01/29/2015",
        "Amendment - effective from 12/15/2014 to 03/17/2015",
        "Repeal - effective from 10/09/2017",
        "Part 820",
    ):
        assert text in body, text
    assert record["source_as_of"] == record["expression_date"] == "2026-09-28"


def test_arkansas_keeps_child_support_deduction_and_gross_test_revision_stamps() -> None:
    body = _page(2, 642)
    assert "6550 Child Support Deductions SNAP Manual 06/01/98" in body
    assert (
        "A deduction will be allowed for legally obligated child support payments made by a "
        "household member to an individual who is not a household member."
    ) in body
    assert "6551 Determining Amount of Child Support Deduction SNAP Manual 06/01/98" in _page(2, 643)
    assert "7524 Determining Eligibility SNAP Manual 07/01/98" in _page(2, 687)
    assert (
        "Except for the farm loss deduction explained in SNAP 5670, no deductions will be "
        "allowed in the calculation of total gross income."
    ) in _page(2, 688)
    assert "6100 Deductions – Summary" in _page(2, 615)
    assert "Deductions are applied after the gross income has been calculated." in _page(2, 615)
    assert "7600 Calculation of A Budget SNAP Manual 07/01/98" in _page(2, 690)
    assert "7610 SNAP Budget Process SNAP Manual 06/01/05" in _page(2, 691)
    worksheet = _page(2, 692)
    assert "11. If there is a child support deduction, enter the amount here. (See SNAP 6550.)" in worksheet
    assert "12. Total deductions in lines 7-10. Enter result here." in worksheet
    assert "SNAP Manual 02/01/20" in _page(2, 358)
    assert "Issuance Number: SNAP 19-02" in _page(2, 175)


def test_arkansas_latest_printed_revision_stamp_is_the_vintage_date() -> None:
    document, rows, _ = _scope(2)
    with fitz.open(CORPUS_ROOT / rows[document["citation_path"]]["source_path"]) as pdf:
        stamps = set()
        for page in pdf:
            text = page.get_text()
            for token in text.split("SNAP Manual ")[1:]:
                month, day, year = token[:2], token[3:5], token[6:8]
                if token[2] == token[5] == "/" and (month + day + year).isdigit():
                    stamps.add((int(year) + (2000 if int(year) < 50 else 1900), int(month), int(day)))
    assert max(stamps) == (2020, 2, 1)


def test_hawaii_retains_net_income_deduction_and_its_printed_history() -> None:
    assert (
        "(f) Subtract the legally obligated child support payments that are paid by a household member."
    ) in _page(3, 38)
    assert "§17-676-55 REPEALED. [R 1/06/12]" in _page(3, 38)
    body = _page(3, 48)
    assert (
        "(6) Legally obligated child support payments, paid by a household member to or for a "
        "nonhousehold member, including payments made to a third party on behalf of the "
        "nonhousehold member."
    ) in body
    assert "The department shall allow a deduction for amounts paid toward arrearages." in body
    assert "am and comp 11/09/06; am 11/22/08]" in body
    assert (
        "the household\u2019s monthly income after all other applicable deductions"
    ) in _page(3, 46)
    assert (
        "Deductible expenses shall include only certain costs of dependent care, shelter, "
        "child support, and medical costs."
    ) in _page(3, 51)


def test_hawaii_2014_posting_text_matches_the_released_2019_posting() -> None:
    document, rows, _ = _scope(3)
    released_path = (
        CORPUS_ROOT
        / "provisions/us-hi/regulation/2026-05-27-hi-snap-rules-r2026-07-15-self-contained.jsonl"
    )
    released = {
        row["citation_path"]: row
        for row in map(json.loads, released_path.read_text().splitlines())
    }
    for number in range(1, 74):
        assert _page(3, number) == released[f"us-hi/regulation/har/17/676/page-{number}"]["body"]


@pytest.mark.parametrize("index", range(len(SCOPES)))
def test_historical_pdf_has_complete_coverage_and_embedded_text_on_every_page(index: int) -> None:
    document, rows, scope = _scope(index)
    _, _, page_count, vintage, basis = SCOPES[index]
    root = document["citation_path"]
    pdf_rows = {path: row for path, row in rows.items() if "/filing-record" not in path}
    assert set(pdf_rows) == {root} | {f"{root}/page-{number}" for number in range(1, page_count + 1)}
    coverage = json.loads((CORPUS_ROOT / "coverage" / f"{scope}.json").read_text())
    assert coverage["complete"] is True
    assert coverage["source_count"] == coverage["provision_count"] == len(rows)
    for key in (
        "missing_from_provisions",
        "extra_provisions",
        "duplicate_source_citations",
        "duplicate_provision_citations",
    ):
        assert coverage[key] == []
    with fitz.open(CORPUS_ROOT / rows[root]["source_path"]) as pdf:
        assert len(pdf) == page_count
        for number, page in enumerate(pdf, 1):
            assert page.get_text().strip(), (scope, number)
            assert rows[f"{root}/page-{number}"]["body"].strip(), (scope, number)
    assert root.endswith(f"/vintage/{vintage}")
    for row in pdf_rows.values():
        assert row["source_as_of"] == row["expression_date"] == vintage
        assert row["metadata"]["historical_vintage"] is True
        assert row["metadata"]["vintage_date_basis"] == basis
    # A file creation timestamp is recorded but never used as the vintage date.
    assert "effective_date" not in document["metadata"] or basis.endswith("effective_date")
