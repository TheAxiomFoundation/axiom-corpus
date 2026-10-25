"""Regression tests for the CA ACL 06-31 and 13 DE Reg. 1550 scopes.

Each test pins a defect an adversarial review found in the first extraction
(axiom-corpus PR #736): the California page-1 paragraph hidden by an empty
/ActualText, strike-through deletions read as ordinary text in both PDFs, and
the Delaware boxed exceptions placed after the next heading. The committed
provisions must also reproduce from the retained PDFs under the manifests'
extraction settings.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from axiom_corpus.corpus import documents as documents_module

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"

CA_VERSION = "2026-09-23-ca-cdss-acl-06-31"
CA_MANIFEST = REPO_ROOT / "manifests" / "us-ca-cdss-acl-06-31.yaml"
CA_PROVISIONS = CORPUS_ROOT / "provisions" / "us-ca" / "guidance" / f"{CA_VERSION}.jsonl"
CA_PDF = (
    CORPUS_ROOT
    / "sources/us-ca/guidance"
    / CA_VERSION
    / "official-documents/ca-cdss-acl-2006-06-31.pdf"
)
CA_ROOT = "us-ca/guidance/cdss/acl-2006-06-31"

DE_VERSION = "2026-09-23-de-register-13-de-reg-1550"
DE_MANIFEST = REPO_ROOT / "manifests" / "us-de-register-13-de-reg-1550.yaml"
DE_PROVISIONS = CORPUS_ROOT / "provisions" / "us-de" / "rulemaking" / f"{DE_VERSION}.jsonl"
DE_PDF = (
    CORPUS_ROOT
    / "sources/us-de/rulemaking"
    / DE_VERSION
    / "official-documents/de-register-13-de-reg-1550.pdf"
)
DE_ROOT = "us-de/rulemaking/delaware-register/2010-06-01/13-de-reg-1550"


@cache
def _rows(path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return {row["citation_path"]: row for row in rows}


def _body(path: Path, citation_path: str) -> str:
    body = _rows(path)[citation_path]["body"]
    assert isinstance(body, str)
    return body


def _extraction(manifest: Path) -> dict[str, Any]:
    (document,) = yaml.safe_load(manifest.read_text())["documents"]
    extraction = document["extraction"]
    assert isinstance(extraction, dict)
    return extraction


def test_california_page_1_keeps_the_changes_include_paragraph() -> None:
    body = _body(CA_PROVISIONS, f"{CA_ROOT}/page-1")

    assert (
        "(CalWORKs) program. Changes include: (1) treatment of legally obligated child "
        "support payments to non-household members as an income exclusion rather than as "
        "an income deduction; (2) exclusion of certain restricted accounts as a resource;"
    ) in body
    assert (
        "(6) allowance of a Telephone Utility Allowance (TUA) for households not qualified "
        "to receive a SUA or LUA. Proposed regulations are attached showing the above "
        "changes in FSP policy (enclosed as Attachment A). IMPLEMENTATION SCHEDULE"
    ) in body
    # The letter itself carries no amendment markup.
    assert "amendment_markup" not in _rows(CA_PROVISIONS)[f"{CA_ROOT}/page-1"]["metadata"]


def test_california_page_12_marks_the_repealed_child_support_deduction_deleted() -> None:
    body = _body(CA_PROVISIONS, f"{CA_ROOT}/page-12")

    assert ".38 [-Child Support Deduction-]" in body
    for clause in (
        "(a) [-The child support deduction is the monthly amount of child support payments "
        "that a household member, with a legal obligation to pay child support payments to "
        "or for an individual living outside of the household, actually makes.-]",
        "(b) [-The payments shall be verified as specified in Section 63-300.51(j).-]",
        "(c) [-Households that fail or refuse to cooperate",
        "(d) [-Payments are deductible only to the extent",
        "(e) [-Child support payments made to a third party",
        "(f) [-Amounts paid toward arrearages shall be deductible.-]",
    ):
        assert clause in body
    # The new telephone-allowance paragraphs above it are insertions.
    assert "(e) {+A household that is not eligible for either the SUA or LUA" in body


def test_california_page_8_marks_the_new_child_support_exclusion_inserted() -> None:
    body = _body(CA_PROVISIONS, f"{CA_ROOT}/page-8")

    assert (
        "{+(p) Child Support payments that a household member pays to or for an individual "
        "living outside of the household.+}"
    ) in body
    assert "{+(6) Amounts paid toward arrearages shall be excluded.+}" in body
    assert "who have not attained their [-18th-] {+19th+} birthday" in body


def test_california_page_15_recovers_and_marks_the_struck_subtraction_step() -> None:
    body = _body(CA_PROVISIONS, f"{CA_ROOT}/page-15")

    assert (
        "[-(g) Subtract allowable monthly child support payments as specified in "
        "Section 63-502.37.-]"
    ) in body
    assert "([-h-]{+g+}) (Continued)" in body


def test_california_case_names_are_not_marked_as_insertions() -> None:
    for page in ("page-13", "page-16"):
        body = _body(CA_PROVISIONS, f"{CA_ROOT}/{page}")
        assert "Jones v. Yeutter" in body
        assert "{+Jones" not in body
    assert "Hamilton v. Lyng; and Section 4103" in _body(CA_PROVISIONS, f"{CA_ROOT}/page-13")


def test_california_marks_only_attachment_a() -> None:
    rows = _rows(CA_PROVISIONS)
    for page in range(1, 32):
        row = rows[f"{CA_ROOT}/page-{page}"]
        marked = "amendment_markup" in row["metadata"]
        assert marked is (7 <= page <= 23), page
        if not marked:
            assert not any(token in row["body"] for token in ("[-", "-]", "{+", "+}"))


def test_delaware_page_3_marks_the_deleted_retirement_income_example() -> None:
    body = _body(DE_PROVISIONS, f"{DE_ROOT}/page-3")

    # The whole page is the old DSSM 9059 text, struck through.
    assert body.startswith("[-person or organization outside of the household")
    assert body.endswith("-]")
    assert body.count("[-") == 1
    assert "{+" not in body
    assert (
        "b) A civil service retiree is entitled to a retirement payment of $800 a month. "
        "However, $400 is diverted to his ex-wife by court order for child support."
    ) in body


def test_delaware_page_16_separates_deleted_and_replacement_text() -> None:
    body = _body(DE_PROVISIONS, f"{DE_ROOT}/page-16")

    assert body.startswith("[-R. In HUD's Family Self-Sufficiency (FSS) Program")
    assert (
        "unless extended by Food and Nutrition Service. 13 DE Reg. 937 (01/01/10)-] "
        "{+This section lists the types of income excluded for the Food Supplement Program."
    ) in body
    assert body.endswith("+}")


def test_delaware_page_22_keeps_the_child_support_exception_with_item_26() -> None:
    body = _body(DE_PROVISIONS, f"{DE_ROOT}/page-22")

    item_26 = body.index("26. Child Support Payments, Food and Nutrition Act of 2008")
    exception = body.index(
        "Exception: Legally obligated child support payments made to an individual or "
        "agency outside of the household may be allowed as an exclusion even if the child "
        "for whom the support was paid is a household member."
    )
    heading_v = body.index("V. American Indian or Alaska Native Payments")
    assert item_26 < exception < heading_v
    assert ("legally enforceable separation agreement, etc. Exception: Legally obligated") in body
    assert "like DCSE. V. American Indian or Alaska Native Payments" in body


def test_delaware_page_17_keeps_the_educational_income_exceptions_with_item_e() -> None:
    body = _body(DE_PROVISIONS, f"{DE_ROOT}/page-17")

    assert (
        "regardless of earmarking or use. Exceptions: The portion of Veterans Educational "
        "Assistance"
    ) in body
    assert "it is considered earned income. F. Loans - All loans" in body


def test_delaware_marks_the_regulation_text_from_page_2() -> None:
    rows = _rows(DE_PROVISIONS)
    assert "amendment_markup" not in rows[f"{DE_ROOT}/page-1"]["metadata"]
    page_2 = rows[f"{DE_ROOT}/page-2"]
    assert page_2["metadata"]["amendment_markup"]["deleted_runs"] == 1
    assert "9059 Income Exclusions [-[7 CFR 273.9(c)] Only the following items" in page_2["body"]
    for page in range(17, 23):
        body = rows[f"{DE_ROOT}/page-{page}"]["body"]
        assert body.startswith("{+") and body.endswith("+}") and body.count("{+") == 1
    # The register's closing citation line is not part of the amended text.
    assert rows[f"{DE_ROOT}/page-23"]["body"].endswith(
        "Grand Coulee Dam Settlement Act, P.L. 103-436+} 13 DE Reg. 1550 (06-01-10) (Final)"
    )


@pytest.mark.parametrize(
    ("pdf_path", "manifest", "provisions", "root", "page_count"),
    [
        (CA_PDF, CA_MANIFEST, CA_PROVISIONS, CA_ROOT, 31),
        (DE_PDF, DE_MANIFEST, DE_PROVISIONS, DE_ROOT, 23),
    ],
)
def test_committed_pages_reproduce_from_the_retained_pdf(
    pdf_path: Path, manifest: Path, provisions: Path, root: str, page_count: int
) -> None:
    content = pdf_path.read_bytes()
    extraction = _extraction(manifest)
    marked = documents_module._extract_pdf_blocks(content, extraction=extraction)
    rows = _rows(provisions)

    assert len(marked) == page_count
    for block in marked:
        row = rows[f"{root}/page-{block.metadata['page_number']}"]
        assert row["body"] == block.body
        assert row["metadata"].get("amendment_markup") == block.metadata.get("amendment_markup")


@pytest.mark.parametrize(
    ("pdf_path", "manifest", "reordered_pages"),
    [(CA_PDF, CA_MANIFEST, set()), (DE_PDF, DE_MANIFEST, {17, 22})],
)
def test_markup_adds_delimiters_and_no_other_text(
    pdf_path: Path, manifest: Path, reordered_pages: set[int]
) -> None:
    content = pdf_path.read_bytes()
    extraction = _extraction(manifest)
    without_markup = {
        key: value
        for key, value in extraction.items()
        if key not in {"amendment_markup", "sort_blocks"}
    }
    marked = documents_module._extract_pdf_blocks(content, extraction=extraction)
    plain = documents_module._extract_pdf_blocks(content, extraction=without_markup)

    assert [block.metadata["page_number"] for block in marked] == [
        block.metadata["page_number"] for block in plain
    ]
    for marked_block, plain_block in zip(marked, plain, strict=True):
        stripped = documents_module._strip_amendment_markup(marked_block.body)
        if marked_block.metadata["page_number"] in reordered_pages:
            assert stripped != plain_block.body
            assert sorted(stripped.split()) == sorted(plain_block.body.split())
        else:
            assert stripped == plain_block.body
