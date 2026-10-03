"""Pin Maryland's COMAR chapter, Pennsylvania's existing text, and the Vermont repeal."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf

BASE = Path(__file__).resolve().parents[1]
CORPUS = BASE / "data/corpus"
MD_VERSION = "2026-09-28-md-snap-comar-publication-2026-09-27-title-07-subtitle-03-chapter-17"
MD_SCOPE = f"us-md/regulation/{MD_VERSION}"
MD_ROOT = "us-md/regulation/title-07/subtitle-03/chapter-17"
# The adapter's shared container rows, which the selected Maryland regulation scope
# also carries; a release consolidates them (docs/ingest-runs note, "Maryland").
MD_CONTAINERS = {
    "us-md/regulation",
    "us-md/regulation/title-07",
    "us-md/regulation/title-07/subtitle-03",
}
MD_SELECTED = (
    "us-md/regulation/2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-"
    "subtitle-03-chapters-06-07-r2026-09-14-chapter-03-title-03-subtitle-04-consolidated"
)
VT_VERSION = "2026-09-28-vt-dcf-b18-06f"


def _rows(scope: str) -> dict[str, dict]:
    return {
        row["citation_path"]: row
        for line in (CORPUS / "provisions" / f"{scope}.jsonl").read_text().splitlines()
        if (row := json.loads(line))
    }


def test_maryland_chapter_has_every_regulation_as_a_child_of_the_chapter() -> None:
    rows = _rows(MD_SCOPE)
    numbers = {f"{i:02}" for i in range(1, 62)} | {"09-1"}
    assert set(rows) == MD_CONTAINERS | {MD_ROOT} | {f"{MD_ROOT}/regulation-{n}" for n in numbers}
    for number in numbers:
        row = rows[f"{MD_ROOT}/regulation-{number}"]
        assert row["body"]
        assert row["parent_citation_path"] == MD_ROOT
        assert row["legal_identifier"] == f"COMAR 07.03.17.{number}"
        assert row["source_format"] == "maryland-comar-openlaw-xml"
        assert row["source_url"].startswith(
            "https://github.com/maryland-dsd/law-xml-codified/blob/publication%2F2026-09-27.2026-09-27/"
        )
    assert rows[MD_ROOT]["kind"] == "chapter"
    report = json.loads((CORPUS / "coverage" / f"{MD_SCOPE}.json").read_text())
    assert report["complete"] is True
    assert report["provision_count"] == len(rows) == 66


def test_maryland_deducts_child_support_in_the_net_calculation() -> None:
    rows = _rows(MD_SCOPE)
    assert (
        "A. A household member who has verification of having made legally obligated child "
        "support payments to or for an individual living outside the household is allowed a "
        "deduction."
    ) in rows[f"{MD_ROOT}/regulation-35"]["body"]
    assert (
        "G. Subtract payments for child support for an individual living outside the home as "
        "set forth in Regulation .35 of this chapter;"
    ) in rows[f"{MD_ROOT}/regulation-43"]["body"]
    assert (
        "B. A household that does not include an elderly or disabled member shall meet both "
        "the gross and net income eligibility standards for the Program in Schedules A and B "
        "of Regulation .45 of this chapter."
    ) in rows[f"{MD_ROOT}/regulation-42"]["body"]
    # The excluded-income list names child support received, not child support paid.
    excluded = [
        line for line in rows[f"{MD_ROOT}/regulation-30"]["body"].splitlines()
        if "child support" in line.lower()
    ]
    assert excluded == [
        "(2) Child support paid to a TCA recipient that is required to be transferred to the "
        "Department's Child Support Enforcement Administration;"
    ]
    # Tables keep their rows: the gross and net income standards of .45.
    assert "1 | $1,174 | $ 903 | $1,490 | $ 200" in rows[f"{MD_ROOT}/regulation-45"]["body"]


def test_maryland_shares_only_the_adapter_containers_with_the_selected_scope() -> None:
    new = set(_rows(MD_SCOPE))
    selected = set(_rows(MD_SELECTED))
    assert new & selected == MD_CONTAINERS


def test_pennsylvania_released_handbook_already_has_both_requested_passages() -> None:
    rows = _rows("us-pa/manual/2026-07-21-pa-snap-handbook")
    root = "us-pa/manual/dhs/snap/560-income-deductions"
    assert (
        "A household is eligible for a child support deduction from net income before "
        "calculation of the shelter deduction if all of the following conditions are met:"
    ) in rows[f"{root}-560-6-child-support-deduction/block-1"]["body"]
    appendix = [row for path, row in rows.items() if path.startswith(f"{root}-560-appendix-a/block-")]
    assert len(appendix) == 12
    assert all("Child Support 7 CFR § 273.9(d)(5)" in row["body"] for row in appendix)


def test_vermont_repeal_preserves_options_without_stating_an_election() -> None:
    rows = _rows(f"us-vt/rulemaking/{VT_VERSION}")
    root = "us-vt/rulemaking/dcf/2018-12-10/b18-06f"
    assert (
        "Current program options and waivers will be maintained (subject to approval "
        "by the federal Food and Nutrition Service)."
    ) in rows[f"{root}/page-1"]["body"]
    # The cover's text layer misreads the printed cover; the manifest's ocr_note says so.
    assert "CHANGES ADOPTED EFFECTNE January 1. 2019" in rows[f"{root}/page-1"]["body"]
    page_2 = rows[f"{root}/page-2"]["body"]
    assert "The anticipated effective date of the rule is January 1, 2019. This date is subject to change." in page_2
    assert "copies of the final proposed rule were filed with the Secretary of State" in page_2
    assert rows[root]["expression_date"] == "2018-12-10"
    assert rows[root]["metadata"]["effective_date"] == "2019-01-01"
    assert rows[root]["metadata"]["document_subtype"] == "final_proposed_rule_repeal_bulletin"
    pdf = CORPUS / "sources/us-vt/rulemaking" / VT_VERSION / "official-documents/vt-dcf-b18-06f.pdf"
    with pymupdf.open(pdf) as document:
        assert len(document) == 3
        assert all(page.get_text().strip() for page in document)
    report = json.loads((CORPUS / "coverage" / f"us-vt/rulemaking/{VT_VERSION}.json").read_text())
    assert report["complete"] is True
