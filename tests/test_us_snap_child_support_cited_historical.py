"""Historical state PDFs retain the dated child-support rules and every page."""

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
SCOPES = [
    (
        "us-co-10-ccr-2506-1-2009-07-01.yaml",
        "2026-09-27-co-10-ccr-2506-1-2009-07-01",
        236,
    ),
    ("us-ri-snap-rules-2014-10.yaml", "2026-09-27-ri-snap-rules-2014-10", 311),
    (
        "us-ar-snap-manual-2020-compilation.yaml",
        "2026-09-27-ar-snap-manual-2020-compilation",
        1057,
    ),
    (
        "us-hi-har-17-676-2014-compilation.yaml",
        "2026-09-27-hi-har-17-676-2014-compilation",
        73,
    ),
]


@cache
def _scope(index: int) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    manifest, version, _ = SCOPES[index]
    (document,) = yaml.safe_load((REPO_ROOT / "manifests" / manifest).read_text())["documents"]
    scope = f"{document['jurisdiction']}/{document['document_class']}/{version}"
    path = CORPUS_ROOT / "provisions" / f"{scope}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return document, {row["citation_path"]: row for row in rows}, scope


def _page(index: int, number: int) -> dict[str, Any]:
    document, rows, _ = _scope(index)
    return rows[f"{document['citation_path']}/page-{number}"]


def test_colorado_child_support_is_subtracted_before_the_gross_income_test() -> None:
    body = _page(0, 127)["body"]
    assert "B-4223.6 DEDUCTION FOR LEGALLY OBLIGATED CHILD SUPPORT" in body
    assert (
        "The child support deduction will be made from the household's total countable gross "
        "income. The deduction will be made prior to any gross income test to determine eligibility."
    ) in body
    assert "Rule Sections SB&P, 4010.11, 4230 eff. 07/01/2009." in _page(0, 236)["body"]


def test_rhode_island_preserves_the_2005_exclusion_and_older_conflicting_wording() -> None:
    body = _page(1, 136)["body"]
    assert "1008.20.22 (7 CFR 273.9) Child Support Income Exclusion REV:05/2005" in body
    assert (
        "Legally obligated child support payments made by a household member to or for a "
        "nonhousehold member are an income exclusion."
    ) in body
    body = _page(1, 145)["body"]
    assert "1010.20 (7 CFR 273.10) DETERMINING DEDUCTIONS REV:05/2005" in body
    assert (
        "Education expenses, the cost of doing business for the self-employed, and legally "
        "obligated child support paid to a person not in the household are not deductions but "
        "are instead income exclusions, and are handled in accordance with Section 1014.20.15 "
        "(student households), Section 1016.15.20 (self- employed households), and Section "
        "1008.20.22 (child support payments)."
    ) in body
    assert "1038.19 (7 CFR 273.9) CHILD SUPPORT DEDUCTION REV:09/2000" in _page(1, 288)["body"]


def test_arkansas_keeps_child_support_deduction_and_gross_test_revision_stamps() -> None:
    body = _page(2, 642)["body"]
    assert "6550 Child Support Deductions SNAP Manual 06/01/98" in body
    assert (
        "A deduction will be allowed for legally obligated child support payments made by a "
        "household member to an individual who is not a household member."
    ) in body
    assert "7524 Determining Eligibility SNAP Manual 07/01/98" in _page(2, 687)["body"]
    assert (
        "Except for the farm loss deduction explained in SNAP 5670, no deductions will be "
        "allowed in the calculation of total gross income."
    ) in _page(2, 688)["body"]
    assert "7610 SNAP Budget Process SNAP Manual 06/01/05" in _page(2, 691)["body"]
    assert (
        "11. If there is a child support deduction, enter the amount here. (See SNAP 6550.)"
    ) in _page(2, 692)["body"]


def test_hawaii_retains_net_income_deduction_and_its_printed_history() -> None:
    assert (
        "(f) Subtract the legally obligated child support payments that are paid by a household member."
    ) in _page(3, 38)["body"]
    body = _page(3, 48)["body"]
    assert (
        "(6) Legally obligated child support payments, paid by a household member to or for a "
        "nonhousehold member, including payments made to a third party on behalf of the "
        "nonhousehold member."
    ) in body
    assert "The department shall allow a deduction for amounts paid toward arrearages." in body
    assert "am and comp 11/09/06; am 11/22/08]" in body


@pytest.mark.parametrize("index", range(len(SCOPES)))
def test_historical_pdf_has_complete_coverage_and_embedded_text_on_every_page(index: int) -> None:
    document, rows, scope = _scope(index)
    _, _, page_count = SCOPES[index]
    root = document["citation_path"]
    assert set(rows) == {root} | {f"{root}/page-{number}" for number in range(1, page_count + 1)}
    coverage = json.loads((CORPUS_ROOT / "coverage" / f"{scope}.json").read_text())
    assert coverage["complete"] is True
    assert coverage["source_count"] == coverage["provision_count"] == page_count + 1
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
    assert "/vintage/" in root
    for row in rows.values():
        assert row["source_as_of"] == document["source_as_of"]
        assert row["expression_date"] == document["expression_date"]
        assert row["metadata"]["historical_vintage"] is True
    if index in (2, 3):
        # A file creation timestamp identifies this compilation; it is not an effective date.
        assert document["metadata"]["date_basis"] == "file_creation_date"
        assert "effective_date" not in document["metadata"]
