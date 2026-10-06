"""State-published child-support election letters, law and rulemaking sources."""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

import fitz
import pytest
import yaml

from axiom_corpus.corpus import documents

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
SCOPES = (
    ("mo-dss-im-39-2003", "us-mo", "guidance", 2),
    ("mo-dss-im-34-2013", "us-mo", "guidance", 9),
    ("nj-pl-2013-c45", "us-nj", "statute", 2),
    ("nj-prn-2016-017", "us-nj", "rulemaking", 21),
    ("nc-dss-es-al-6-2005", "us-nc", "guidance", 3),
    ("wa-wsr-09-15-085", "us-wa", "rulemaking", 2),
    ("wa-wsr-09-16-095", "us-wa", "rulemaking", 2),
)


@cache
def _rows(stem: str) -> dict[str, dict]:
    _, jurisdiction, document_class, _ = next(scope for scope in SCOPES if scope[0] == stem)
    path = CORPUS / "provisions" / jurisdiction / document_class / f"2026-09-28-{stem}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == len({row["citation_path"] for row in rows})
    return {row["citation_path"]: row for row in rows}


def _body(stem: str, suffix: str) -> str:
    (source,) = yaml.safe_load((ROOT / "manifests" / f"us-{stem}.yaml").read_text())["documents"]
    return _rows(stem)[f"{source['citation_path']}/{suffix}"]["body"]


@pytest.mark.parametrize(
    ("stem", "suffix", "sentence"),
    [
        (
            "mo-dss-im-39-2003",
            "block-1",
            "Effective for any budget completed March 10, 2003, and after, exclude (deduct) "
            "the child support expense from the gross income prior to the gross eligibility "
            "(130% of Federal Poverty Level - FPL) test.",
        ),
        (
            "mo-dss-im-34-2013",
            "block-4",
            "When prorating ineligible or disqualified members' income, all obligated child "
            "support paid by eligible and/or ineligible EU members is excluded from the "
            "household's gross income.",
        ),
        (
            "nj-pl-2013-c45",
            "block-1",
            "Notwithstanding the provisions of any other law or regulation to the contrary, "
            "the department and the county welfare agencies shall exclude from a household’s "
            "income all legally-obligated or court-ordered child support payments paid by a "
            "household member to, or on behalf of, a non-household member, including payments "
            "to a third party on behalf of the non-household member and amounts paid toward "
            "arrearages, for the purpose of determining whether a household meets applicable "
            "gross and net SNAP income eligibility standards.",
        ),
        (
            "nj-prn-2016-017",
            "page-3",
            "As required by the New Jersey SNAP Employment and Training Provider "
            "Demonstration Project Act (P.L. 2013, c. 45), legally obligated child support paid "
            "by a household member will now be considered as an income exclusion, which will "
            "result in this income being eliminated from consideration prior to the "
            "household’s gross income test.",
        ),
        (
            "nc-dss-es-al-6-2005",
            "page-1",
            "Treatment of Legally Obligated Child Support (LSO) paid by members of the Food "
            "Stamp Unit was changed to an income exclusion rather than an income deduction "
            "beginning January 1, 2005.",
        ),
        (
            "wa-wsr-09-15-085",
            "block-1",
            "The department is exercising an option from the 2002 farm bill to treat child "
            "support payments made to someone outside of the home as an income exclusion "
            "prior to administering the gross income test.",
        ),
        (
            "wa-wsr-09-16-095",
            "block-1",
            "Due to the time required to complete the rule change process for proposed "
            "changes to WAC 388-450-0185 , the department wishes to change the effective date "
            "for WSR 09-15-085 to November 15, 2009.",
        ),
    ],
)
def test_key_child_support_sentence_is_in_expected_row(
    stem: str, suffix: str, sentence: str
) -> None:
    assert sentence in _body(stem, suffix)


def test_missouri_memos_keep_their_headers_and_drop_site_navigation() -> None:
    im39 = _body("mo-dss-im-39-2003", "block-1")
    assert im39.endswith("Implement this policy March 10, 2003. JKW/REM Distribution #6")
    assert "2003 Memorandums" not in im39
    header = _body("mo-dss-im-34-2013", "block-1")
    assert "FAMILY SUPPORT DIVISION" in header
    assert "DISQUALIFIED OR INELIGIBLE MEMBERS EARNED INCOME AND EXPENSE BUDGETING" in header
    assert "MANUAL REVISION #19 1115.035.20.05 1115.070.00 1115.071.00" in header
    body = _body("mo-dss-im-34-2013", "block-4")
    assert "Deduct the total from the disqualified or ineligible EU member's gross income." in body
    assert "Deduct any remaining child support from the eligible EU members' income." in body
    assert "This change will be in effect March 18, 2013." in _body("mo-dss-im-34-2013", "block-5")


def test_missouri_and_north_carolina_preserve_separate_net_calculation() -> None:
    missouri = _body("mo-dss-im-39-2003", "block-1")
    start = missouri.index("for what amount based on the net income test")
    net = missouri[start:]
    assert net.index("subtract the 20% earned income deduction") < net.index(
        "subtract court ordered child support paid"
    )
    assert (
        "FSIS also uses Field 80N to calculate the LSO amount paid as an income deduction "
        "once the gross income test has been performed."
    ) in _body("nc-dss-es-al-6-2005", "page-1")


def test_new_jersey_law_keeps_effective_date_rule_and_approval() -> None:
    body = _body("nj-pl-2013-c45", "block-1")
    assert "C.44:10-104 Certain income excluded in determining eligibility." in body
    assert (
        "11. This act shall take effect on the first day of the seventh month next "
        "following the date of enactment"
    ) in body
    assert "Approved April 15, 2013." in body


def test_new_jersey_proposal_marks_bold_insertions_and_bracketed_deletions() -> None:
    assert (
        "{+20. All legally obligated or court-ordered child support payments paid by a "
        "household member to, or on behalf of, a non-household member, including payments "
        "to a+}"
    ) in _body("nj-prn-2016-017", "page-10")
    assert (
        "{+third party on behalf of the non-household member and amounts paid toward "
        "arrearages. Alimony payments made to or for a non-household member shall not be "
        "excluded as income.+}"
    ) in _body("nj-prn-2016-017", "page-11")
    # The deletion of 10:87-5.10(a)4v and (a)5 opens on page 11 and closes on page 12.
    page_11 = _body("nj-prn-2016-017", "page-11")
    page_12 = _body("nj-prn-2016-017", "page-12")
    assert "[-v. Legally obligated or court-ordered child support payments" in page_11
    assert page_11.endswith("-]")
    assert page_12.startswith("- 12 -")  # the running page number stays unmarked
    assert "shall not be included in the child support deduction; and-]" in page_12
    rows = {
        int(key.rsplit("-", 1)[1]): row
        for key, row in _rows("nj-prn-2016-017").items()
        if "/page-" in key
    }
    assert rows[11]["metadata"]["amendment_markup"]["deletion_continues_to_next_page"] is True
    assert rows[12]["metadata"]["amendment_markup"]["deletion_continues_from_previous_page"] is True
    for page, row in rows.items():
        markup = row["metadata"].get("amendment_markup")
        assert (markup is not None) is (page >= 9)
        if markup:
            assert markup["deleted_source_markup"] == "brackets"
            assert markup["inserted_source_markup"] == "bold"
            assert "[" not in documents._strip_amendment_markup(row["body"]).replace("[-", "")
    assert sum(row["metadata"]["amendment_markup"]["deleted_runs"] for page, row in rows.items() if page >= 9) == 23


def test_washington_markup_survives_unclosed_html_paragraphs() -> None:
    body = _body("wa-wsr-09-15-085", "block-1")
    assert "(([-and-]))" in body  # the register's ((struck)) wrapper, spaced as printed
    assert "{+AMENDATORY SECTION+}" not in body
    assert "09-09-103, § 388-450-0015" in body
    lead = body.index("Some examples of income we do not count are:")
    operative = body.index(
        "(n) {+For Basic Food Only: The total monthly amount of all legally obligated current "
        "or back child support payments paid by the assistance unit to someone outside of the "
        "assistance unit for:+}"
    )
    assert lead < operative
    assert "{+(i) A person who is not in the assistance unit; or+}" in body
    assert body.count("\n\n") > 30  # the order's paragraphs survive html.parser
    assert "(( [-" not in body


@pytest.mark.parametrize(("stem", "jurisdiction", "document_class", "row_count"), SCOPES)
def test_retained_source_coverage_dates_and_reproduction(
    stem: str, jurisdiction: str, document_class: str, row_count: int
) -> None:
    version = f"2026-09-28-{stem}"
    (source,) = yaml.safe_load((ROOT / "manifests" / f"us-{stem}.yaml").read_text())["documents"]
    rows = _rows(stem)
    coverage = json.loads(
        (CORPUS / "coverage" / jurisdiction / document_class / f"{version}.json").read_text()
    )
    inventory = json.loads(
        (CORPUS / "inventory" / jurisdiction / document_class / f"{version}.json").read_text()
    )
    assert coverage["complete"] is True
    assert (
        coverage["matched_count"]
        == coverage["source_count"]
        == coverage["provision_count"]
        == row_count
    )
    assert not any(
        coverage[key]
        for key in (
            "duplicate_provision_citations",
            "duplicate_source_citations",
            "extra_provisions",
            "missing_from_provisions",
        )
    )
    assert {item["citation_path"] for item in inventory["items"]} == set(rows)
    root = rows[source["citation_path"]]
    retained = CORPUS / root["source_path"]
    content = retained.read_bytes()
    assert {item["sha256"] for item in inventory["items"]} == {
        hashlib.sha256(content).hexdigest()
    }
    assert {row["expression_date"] for row in rows.values()} == {source["expression_date"]}
    assert {row["source_as_of"] for row in rows.values()} == {source["source_as_of"]}
    blocks = documents._extract_blocks(
        content,
        source["source_format"],
        source_url=source["source_url"],
        title=source["title"],
        extraction=source.get("extraction"),
    )
    assert len(blocks) + 1 == row_count
    for block in blocks:
        suffix = (
            f"page-{block.metadata['page_number']}"
            if source["source_format"] == "pdf"
            else f"block-{block.ordinal}"
        )
        row = rows[f"{source['citation_path']}/{suffix}"]
        assert row["body"] == block.body
        assert row["metadata"].get("amendment_markup") == block.metadata.get("amendment_markup")
    if source["source_format"] == "pdf":
        with fitz.open(stream=content, filetype="pdf") as pdf:
            assert len(pdf) == row_count - 1
            assert all(page.get_text().strip() for page in pdf)
