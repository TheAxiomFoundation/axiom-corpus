"""Committed-artifact checks for the 2025 FTB 3514 (California EITC) booklet scope."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import fitz
import pytest
import yaml

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-09-23-ca-2025-ftb-3514"
MANIFEST_PATH = REPO_ROOT / "manifests/us-ca-2025-ftb-3514-booklet.yaml"
SOURCE_URL = "https://www.ftb.ca.gov/forms/2025/2025-3514-booklet.pdf"
SOURCE_SHA256 = "9096ff0ec8a240717753f3f0345f2fa85a7bfaba4a8bcb194f316394a4e15538"
ROOT = "us-ca/form/individual-income-tax/2025"
SLICES = {
    "us-ca-ftb-2025-3514-instructions": f"{ROOT}/3514-instructions",
    "us-ca-ftb-2025-3514-eitc-worksheet": f"{ROOT}/3514-eitc-worksheet",
    "us-ca-ftb-2025-3514-form": f"{ROOT}/3514",
    "us-ca-ftb-2025-3514-eitc-table": f"{ROOT}/3514-eitc-table",
}
RTC_SCOPE_VERSION = "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7"
SB_1435_SCOPE_VERSION = "2026-09-23-ca-rtc-sb-1435-us-ca-sections-rtc-17024.5-rtc-17052"
# The bodies were extracted with this PyMuPDF release (the uv.lock pin). The
# booklet's tagged ActualText reads differently in other releases: PyMuPDF
# 1.28.2 returns different tokens for the instructions, form and table pages.
PYMUPDF_VERSION = "1.26.7"
_TABLE_VALUE = r"\$?\d{1,3}(?:,\d{3})*"
_TABLE_ROW_RE = re.compile(rf"^{_TABLE_VALUE}(?: {_TABLE_VALUE}){{5}}$")
_TABLE_DOUBLE_ROW_RE = re.compile(rf"^{_TABLE_VALUE}(?: {_TABLE_VALUE}){{11}}$")


def _provisions() -> dict[str, dict[str, object]]:
    path = REPO_ROOT / f"data/corpus/provisions/us-ca/form/{VERSION}.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    return {str(record["citation_path"]): record for record in records}


def _body(citation_path: str) -> str:
    body = _provisions()[citation_path]["body"]
    assert isinstance(body, str)
    return body


def _metadata(citation_path: str) -> dict[str, object]:
    metadata = _provisions()[citation_path]["metadata"]
    assert isinstance(metadata, dict)
    return metadata


def _amount(value: str) -> int:
    return int(value.replace("$", "").replace(",", ""))


def _eitc_table_rows() -> list[tuple[int, ...]]:
    """Rebuild lookup rows: each page's left column block, then its right block."""
    body = _body(f"{SLICES['us-ca-ftb-2025-3514-eitc-table']}/document-1")
    rows: list[tuple[int, ...]] = []
    for page in body.split("\n\n"):
        left: list[tuple[int, ...]] = []
        right: list[tuple[int, ...]] = []
        for line in page.splitlines():
            if _TABLE_DOUBLE_ROW_RE.match(line) or _TABLE_ROW_RE.match(line):
                values = [_amount(value) for value in line.split()]
                left.append(tuple(values[:6]))
                if len(values) == 12:
                    right.append(tuple(values[6:]))
        rows.extend(left)
        rows.extend(right)
    return rows


def test_ftb_3514_sources_share_the_official_pdf_bytes() -> None:
    source_dir = REPO_ROOT / f"data/corpus/sources/us-ca/form/{VERSION}/official-documents"
    for source_id in SLICES:
        source = source_dir / f"{source_id}.pdf"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256

    inventory = json.loads(
        (REPO_ROOT / f"data/corpus/inventory/us-ca/form/{VERSION}.json").read_text()
    )
    items = inventory["items"]
    assert len(items) == 8
    for item in items:
        assert item["source_url"] == SOURCE_URL
        assert item["sha256"] == SOURCE_SHA256
        assert item["metadata"]["source_sha256"] == SOURCE_SHA256
        assert item["metadata"]["primary_source"] is True


def test_ftb_3514_coverage_is_complete() -> None:
    coverage = json.loads(
        (REPO_ROOT / f"data/corpus/coverage/us-ca/form/{VERSION}.json").read_text()
    )
    assert coverage == {
        "complete": True,
        "document_class": "form",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us-ca",
        "matched_count": 8,
        "missing_from_provisions": [],
        "provision_count": 8,
        "source_count": 8,
        "version": VERSION,
    }
    expected = []
    for citation_path in SLICES.values():
        expected.extend([citation_path, f"{citation_path}/document-1"])
    assert list(_provisions()) == expected


def test_ftb_3514_manifest_slices_do_not_overlap() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    assert [document["source_id"] for document in documents] == list(SLICES)
    pages: list[int] = []
    for document in documents:
        assert document["source_url"] == SOURCE_URL
        assert document["citation_path"] == SLICES[document["source_id"]]
        assert document["extraction"]["segmentation"] == "single_block"
        for window in document["extraction"]["page_windows"]:
            pages.extend(range(window["start_page"], window["end_page"] + 1))
    assert len(pages) == len(set(pages))
    assert sorted(set(range(1, 33)) - set(pages)) == [11, 12, 17, 18, 19, 20, 21]


def test_ftb_3514_eitc_worksheet_preserves_line_guards() -> None:
    lines = _body(f"{SLICES['us-ca-ftb-2025-3514-eitc-worksheet']}/document-1").splitlines()
    for expected in (
        "Enter your California earned income from form FTB 3514, line 19. "
        "If the amount is zero or less, stop here",
        "If the amount on line 2 is zero, stop here. You cannot take the credit.",
        "Enter the amount from federal Form 1040 or 1040-SR, line 11b (federal AGI)",
        "Are the amounts on line 1 and line 3 the same?",
        "Yes Skip line 5; and enter the amount from line 2 on line 6.",
        "Bullet No qualifying children, is the amount on line 3 less than $4,661?",
        "Bullet 1 qualifying child, is the amount on line 3 less than $6,998?",
        "Bullet 2 or more qualifying children, is the amount on line 3 less than $9,823?",
        "Yes Leave line 5 blank; enter the amount from line 2 on line 6.",
        "Compare the amounts on line 5 and line 2, enter the smaller amount on line 6.",
        "Enter this amount on form FTB 3514, line 20.",
    ):
        assert any(line.startswith(expected) for line in lines), expected

    metadata = _metadata(SLICES["us-ca-ftb-2025-3514-eitc-worksheet"])
    assert metadata["worksheet_line_5_threshold_no_qualifying_children"] == "4661"
    assert metadata["worksheet_line_5_threshold_one_qualifying_child"] == "6998"
    assert metadata["worksheet_line_5_threshold_two_or_more_qualifying_children"] == "9823"
    assert metadata["worksheet_table_citation"] == SLICES["us-ca-ftb-2025-3514-eitc-table"]


def test_ftb_3514_instructions_and_form_keep_eligibility_amounts() -> None:
    instructions = _body(f"{SLICES['us-ca-ftb-2025-3514-instructions']}/document-1")
    for expected in (
        "line 11b (federal AGI) less than $32,901?",
        "Is the amount on line 12 more than $4,814?",
        "Is the amount on line 5 more than $4,814?",
        "Subtract the $27,425 threshold amount from your California earned",
        "$21.71.",
        "$43.42 if both taxpayer and spouse/RDP are claiming the FYTC.",
    ):
        assert expected in instructions, expected
    assert "California Earned Income Tax Credit Worksheet\nPart I All Filers" not in instructions

    form = _body(f"{SLICES['us-ca-ftb-2025-3514-form']}/document-1")
    assert (
        "20 California EITC. Enter amount from California Earned Income Tax Credit "
        "Worksheet, Part III, line 6."
    ) in form
    assert "If your total net loss exceeds $35,640 or your federal AGI exceeds $32,900," in form
    assert form.count("FTB 3514 2025 Side 1") == 1


def test_ftb_3514_eitc_table_rows_and_columns_are_complete() -> None:
    rows = _eitc_table_rows()
    table_metadata = _metadata(SLICES["us-ca-ftb-2025-3514-eitc-table"])
    assert len(rows) == int(str(table_metadata["table_row_count"])) == 658
    previous_ceiling = 0
    for at_least, but_not_over, *credits in rows:
        assert at_least == previous_ceiling + 1
        assert but_not_over - at_least == 49
        assert len(credits) == 4
        previous_ceiling = but_not_over
    assert rows[0] == (1, 50, 2, 7, 9, 10)
    assert rows[-1] == (32851, 32900, 1, 1, 1, 1)
    assert rows[40] == (2001, 2050, 132, 585, 689, 775)

    maxima = [max(row[column] for row in rows) for column in range(2, 6)]
    assert maxima == [302, 2016, 3339, 3756]
    assert maxima == [
        int(str(table_metadata[key]))
        for key in (
            "table_max_credit_no_qualifying_children",
            "table_max_credit_one_qualifying_child",
            "table_max_credit_two_qualifying_children",
            "table_max_credit_three_qualifying_children",
        )
    ]
    body = _body(f"{SLICES['us-ca-ftb-2025-3514-eitc-table']}/document-1")
    assert body.count("Caution: This is not a tax table.") == 9
    assert "At But Not 0 1 2 3" in body


def test_ftb_3514_slices_record_the_text_extractor() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    for document in documents:
        assert document["metadata"]["text_extractor"] == f"PyMuPDF {PYMUPDF_VERSION}"
        assert _metadata(document["citation_path"])["text_extractor"] == (
            f"PyMuPDF {PYMUPDF_VERSION}"
        )


@pytest.mark.skipif(
    fitz.VersionBind != PYMUPDF_VERSION,
    reason=(
        f"the bodies were extracted with PyMuPDF {PYMUPDF_VERSION}, and other PyMuPDF "
        "releases read this PDF's tagged ActualText differently"
    ),
)
def test_ftb_3514_slice_bodies_keep_every_pdf_token() -> None:
    """Each slice body carries exactly the words PyMuPDF 1.26.7 reads from its pages."""
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    source_dir = REPO_ROOT / f"data/corpus/sources/us-ca/form/{VERSION}/official-documents"
    for document in documents:
        extraction = document["extraction"]
        sort = bool(extraction.get("sort_text"))
        tokens: list[str] = []
        with fitz.open(source_dir / f"{document['source_id']}.pdf") as pdf:
            for window in extraction["page_windows"]:
                for page_number in range(window["start_page"], window["end_page"] + 1):
                    tokens.extend(pdf[page_number - 1].get_text("text", sort=sort).split())
        body = _body(f"{document['citation_path']}/document-1")
        assert body.split() == tokens, document["source_id"]


def test_ftb_3514_bodies_carry_the_text_layer_repeats_the_notes_disclose() -> None:
    """Pin the ActualText differences each extraction_note lists to the bodies."""
    instructions = _body(f"{SLICES['us-ca-ftb-2025-3514-instructions']}/document-1")
    worksheet = _body(f"{SLICES['us-ca-ftb-2025-3514-eitc-worksheet']}/document-1")
    form = _body(f"{SLICES['us-ca-ftb-2025-3514-form']}/document-1")
    table = _body(f"{SLICES['us-ca-ftb-2025-3514-eitc-table']}/document-1")
    assert [len(re.findall(r"\bBullet\b", body)) for body in (instructions, worksheet, form)] == [
        30,
        3,
        4,
    ]

    # Instructions pages in body order: PDF pages 1-7, 9-10 and 31-32.
    instruction_pages = instructions.split("\n\n")
    assert len(instruction_pages) == 11
    cover = "2025 California Earned Income Tax Credit Booklet. 3514"
    assert instruction_pages[0].count(cover) == 4
    assert f"Form FTB 3514, California Earned Income Tax Credit{cover}" in instruction_pages[0]
    page_5 = instruction_pages[4]
    assert page_5.count("Worksheet 1 – Investment Income Form 540 and Form 540NR Filers") == 3
    assert page_5.count("Worksheet 2 – Investment Income Form 540 2EZ Filers") == 2

    # Form pages in body order: PDF pages 13-16.
    form_pages = form.split("\n\n")
    assert len(form_pages) == 4
    title = "TAXABLE YEAR 2025 California Earned Income Tax CreditFORM 3514"
    assert form_pages[0].splitlines().count(title) == 5
    line_23 = "23. California earned income. Enter the amount from form FTB 3514, line 19."
    assert form_pages[2].count(line_23) == 2

    # Table pages in body order: PDF pages 22-30.
    table_pages = table.split("\n\n")
    assert len(table_pages) == 9
    assert table_pages[0].count("Your credit") == 1
    assert "looking up from" not in table_pages[0]
    assert "But Not" not in table_pages[0]
    for page in table_pages[1:-1]:
        assert page.count("At But Not 0 1 2 3") == 2
    assert table_pages[-1].count("At But Not 0 1 2 3") == 1


def test_ftb_3514_eitc_table_rows_match_the_pdf_word_positions() -> None:
    """Rebuild the table from word coordinates in the retained PDF, not the text stream."""
    source = (
        REPO_ROOT
        / f"data/corpus/sources/us-ca/form/{VERSION}/official-documents"
        / "us-ca-ftb-2025-3514-eitc-table.pdf"
    )
    value_re = re.compile(rf"^{_TABLE_VALUE}$")
    rows: list[tuple[int, ...]] = []
    with fitz.open(source) as document:
        for page_number in range(22, 31):
            page = document[page_number - 1]
            midline = page.rect.width / 2
            lines: dict[int, list[tuple[float, str]]] = {}
            for x0, y0, _x1, y1, word, *_rest in page.get_text("words"):
                if value_re.match(word):
                    lines.setdefault(round((y0 + y1) / 2), []).append((x0, word))
            left: list[tuple[int, ...]] = []
            right: list[tuple[int, ...]] = []
            for _y, words in sorted(lines.items()):
                ordered = sorted(words)
                left_values = [_amount(word) for x0, word in ordered if x0 < midline]
                right_values = [_amount(word) for x0, word in ordered if x0 >= midline]
                if len(left_values) == 6:
                    left.append(tuple(left_values))
                if len(right_values) == 6:
                    right.append(tuple(right_values))
            rows.extend(left)
            rows.extend(right)
    assert len(rows) == 658
    assert rows == _eitc_table_rows()


def _statute_histories(version: str) -> dict[str, str]:
    path = REPO_ROOT / f"data/corpus/provisions/us-ca/statute/{version}.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    return {
        str(record["citation_path"]): str(record["metadata"].get("history", ""))
        for record in records
    }


def test_ftb_3514_statutory_cross_reference_resolves() -> None:
    chapter = _statute_histories(RTC_SCOPE_VERSION)
    amended = _statute_histories(SB_1435_SCOPE_VERSION)
    for source_id in SLICES:
        metadata = _metadata(SLICES[source_id])
        citation = metadata["statutory_corpus_citation"]
        assert citation == "us-ca/statute/rtc/17052"
        assert metadata["statutory_corpus_version"] == RTC_SCOPE_VERSION
        assert metadata["statutory_superseding_corpus_version"] == SB_1435_SCOPE_VERSION
        note = metadata["statutory_note"]
        assert isinstance(note, str)
        assert note.startswith("SB 1435 (Stats. 2026, Ch. 236, Sec. 2), effective September 14")
        # The pointed-to record predates SB 1435; the superseding record carries it.
        assert "Stats. 2026, Ch. 236" not in chapter[citation]
        assert amended[citation].startswith("(Amended by Stats. 2026, Ch. 236, Sec. 2. (SB 1435)")
        assert "taxable years beginning on or after January 1, 2025" in amended[citation]
    for section in ("17024.5", "17041", "17052", "17073.5", "17076"):
        assert f"us-ca/statute/rtc/{section}" in chapter


def test_ftb_3514_scope_passes_release_validation() -> None:
    release = ReleaseManifest(
        name="us-ca-2026-09-23-ftb-3514-validation",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope("us-ca", "form", VERSION),),
    )
    report = validate_release(REPO_ROOT / "data/corpus", release, strict_warnings=True)
    assert report.to_mapping()["ok"] is True
    assert report.to_mapping()["issue_count"] == 0
