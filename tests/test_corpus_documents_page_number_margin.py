"""A page-number drop pattern removes a bare number only from the page's margin.

``drop_line_patterns`` entries such as ``^\\d{1,3}$`` exist to remove page
numbers, but a pattern sees only a line's text, so it also removed every table
cell, list number and citation title that is a bare number. The fixtures below
rebuild regions of the official PDFs behind released rows that lost data that
way, line by line at the coordinates the official page prints them, and run
them through the manifests' own extraction settings.

``_content_only_lines`` is the line filter as it ran before: it drops every
line a filter matches. The tests use it twice: to show that each fixture
reproduces the damage seen in the released row, and as the second
implementation in the differential test, which checks that a page without a
table loses exactly the lines it lost before.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module

REPO_ROOT = Path(__file__).resolve().parents[1]

# (text, x, baseline y, font size, style) with style "", "b" (bold) or "bi".
Line = tuple[str, float, float, float, str]

_FONTS = {"": "helv", "b": "hebo", "bi": "hebi"}


def _pdf(pages: list[list[Line]]) -> bytes:
    """A letter-size PDF whose content stream holds each page's lines in order."""
    document = fitz.open()
    for lines in pages:
        page = document.new_page(width=612, height=792)
        for text, x, y, size, style in lines:
            page.insert_text((x, y), text, fontsize=size, fontname=_FONTS[style])
    content: bytes = document.tobytes()
    document.close()
    return content


def _manifest_extraction(manifest: str, source_id: str) -> dict[str, Any]:
    documents = yaml.safe_load((REPO_ROOT / "manifests" / manifest).read_text())["documents"]
    extraction: dict[str, Any] = next(
        document["extraction"] for document in documents if document["source_id"] == source_id
    )
    return extraction


def _content_only_lines(content: bytes, extraction: dict[str, Any]) -> list[str]:
    """Every page line the filters do not match: the filter before this change."""
    drop_lines = {str(line).strip() for line in extraction.get("drop_lines", ())}
    patterns = tuple(re.compile(str(p)) for p in extraction.get("drop_line_patterns", ()))
    header_patterns = documents_module._page_header_patterns(extraction)
    kept: list[str] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        for page in document:
            for entry in documents_module._without_page_header(
                documents_module._pdf_page_styled_lines(page, extraction=extraction),
                header_patterns,
            ):
                if not documents_module._drop_pdf_line(entry[0], drop_lines, patterns):
                    kept.append(entry[0])
    return kept


def _filtered_lines(content: bytes, extraction: dict[str, Any]) -> list[str]:
    return [
        line for line, _page in documents_module._filtered_pdf_lines(content, extraction=extraction)
    ]


def _section_body(content: bytes, extraction: dict[str, Any], label: str) -> str:
    blocks = documents_module._extract_pdf_blocks(content, extraction=extraction)
    return next(block.body for block in blocks if block.metadata.get("section_label") == label)


def _tokens(text: str) -> list[str]:
    return text.split()


# --- 9 CCR 2503-6 (Colorado Works), PDF pages 50-51 -------------------------
# us-co/regulation/9-ccr-2503-6/3.606.1 lost every "Number of Children" label
# and every chart amount under 1,000 to ``^\d{1,3}$``.

_CO_WORKS_HEADER: list[Line] = [
    ("CODE OF COLORADO REGULATIONS", 72.0, 42.0, 9.0, "bi"),
    ("9 CCR 2503-6", 482.6, 42.0, 9.0, "bi"),
    ("Income Maintenance (Volume 3)", 72.0, 52.3, 9.0, "bi"),
]

_CO_WORKS_PAGE_50: list[Line] = [
    *_CO_WORKS_HEADER,
    ("50", 529.0, 768.4, 10.0, "b"),
    ("3.606.1 Basic Cash Assistance", 72.0, 536.3, 10.0, "b"),
    ("A.", 72.0, 559.9, 10.0, ""),
    ("Payment of Basic Cash Assistance (BCA) Grants", 108.0, 559.9, 10.0, ""),
    (
        "Counties or groups of county departments shall not reduce the BCA grant, restrict "
        "eligibility, or",
        108.0,
        583.4,
        10.0,
        "",
    ),
]

_CHART_COLUMNS = (188.9, 213.8, 238.6, 263.6, 289.9, 317.4, 344.6, 373.9, 405.1, 434.4, 463.5)
_NEED_NONE = ("0", "117", "245", "368", "490", "587", "678", "755", "830", "904", "977")
_GRANT_NONE = ("0", "173", "362", "543", "724", "869", "1003", "1117", "1226", "1337", "1460")
_NEED_ONE = ("253", "331", "421", "510", "605", "697", "770", "844", "920", "992", "1065")
_GRANT_ONE = ("374", "488", "620", "754", "894", "1031", "1138", "1248", "1359", "1467", "1574")
_NEED_TWO = ("357", "439", "533", "628", "716", "787", "861", "937", "1009", "1082", "1155")
_GRANT_TWO = ("527", "649", "788", "927", "1057", "1163", "1273", "1387", "1492", "1598", "1707")


def _amount_row(values: tuple[str, ...], additional: str, baseline: float) -> list[Line]:
    """One chart row: eleven columns for 0 to 10 children, then each additional child."""
    cells = [(value, x, baseline, 8.0, "") for value, x in zip(values, _CHART_COLUMNS, strict=True)]
    return [*cells, (additional, 510.8, baseline, 8.0, "")]


_CO_WORKS_PAGE_51: list[Line] = [
    *_CO_WORKS_HEADER,
    ("51", 529.0, 768.4, 10.0, "b"),
    ("F.", 72.0, 360.9, 10.0, ""),
    (
        "Determining Eligibility for Basic Cash Assistance Grant Based on the Need Standard",
        108.0,
        360.9,
        10.0,
        "",
    ),
    ("upon those included in the assistance unit:", 108.0, 442.4, 10.0, ""),
    ("COLORADO WORKS STANDARDS OF ASSISTANCE CHART", 164.9, 465.9, 10.0, ""),
    ("Number of", 135.7, 478.0, 8.0, ""),
    ("Children", 139.7, 487.5, 8.0, ""),
    *[
        (str(children), x, 496.9, 8.0, "")
        for children, x in enumerate(
            (193.4, 218.2, 243.1, 268.0, 294.3, 321.8, 349.0, 378.3, 409.5, 438.8, 465.8)
        )
    ],
    ("Each", 506.2, 478.0, 8.0, ""),
    ("Additional", 497.8, 487.5, 8.0, ""),
    ("Child", 506.3, 496.9, 8.0, ""),
    ("No Caretaker", 68.3, 510.9, 8.0, ""),
    ("Need", 145.0, 510.9, 8.0, ""),
    ("Standard", 138.3, 520.3, 8.0, ""),
    *_amount_row(_NEED_NONE, "67", 520.3),
    ("Grant", 144.5, 534.2, 8.0, ""),
    ("Standard", 138.3, 543.7, 8.0, ""),
    *_amount_row(_GRANT_NONE, "90", 543.7),
    ("One Caretaker", 65.9, 557.6, 8.0, ""),
    ("Need", 145.0, 557.6, 8.0, ""),
    ("Standard", 138.3, 567.1, 8.0, ""),
    *_amount_row(_NEED_ONE, "67", 567.1),
    ("Grant", 144.5, 581.0, 8.0, ""),
    ("Standard", 138.3, 590.4, 8.0, ""),
    *_amount_row(_GRANT_ONE, "90", 590.4),
    ("Two Caretakers", 63.9, 604.3, 8.0, ""),
    ("Need", 145.0, 604.3, 8.0, ""),
    ("Standard", 138.3, 613.8, 8.0, ""),
    *_amount_row(_NEED_TWO, "67", 615.8),
    ("Grant", 144.5, 629.7, 8.0, ""),
    ("Standard", 138.3, 639.2, 8.0, ""),
    *_amount_row(_GRANT_TWO, "90", 639.2),
]


def test_colorado_works_standards_of_assistance_chart_keeps_every_cell() -> None:
    extraction = _manifest_extraction(
        "us-co-tanf-state-policy-manual.yaml", "us-co-ccr-9-2503-6-colorado-works"
    )
    content = _pdf([_CO_WORKS_PAGE_50, _CO_WORKS_PAGE_51])

    # The fixture reproduces the released row: the content-only filter loses
    # the children counts and every amount under 1,000.
    assert (
        "Number of Children Each Additional Child No Caretaker Need Standard Grant Standard "
        "1003 1117 1226"
    ) in " ".join(_content_only_lines(content, extraction))

    body = _section_body(content, extraction, "3.606.1")
    assert body.endswith(
        "COLORADO WORKS STANDARDS OF ASSISTANCE CHART "
        "Number of Children 0 1 2 3 4 5 6 7 8 9 10 Each Additional Child "
        "No Caretaker Need Standard " + " ".join(_NEED_NONE) + " 67 "
        "Grant Standard " + " ".join(_GRANT_NONE) + " 90 "
        "One Caretaker Need Standard " + " ".join(_NEED_ONE) + " 67 "
        "Grant Standard " + " ".join(_GRANT_ONE) + " 90 "
        "Two Caretakers Need Standard " + " ".join(_NEED_TWO) + " 67 "
        "Grant Standard " + " ".join(_GRANT_TWO) + " 90"
    )
    # The page numbers at the foot of both pages still go.
    assert not {"50", "51"} & set(_tokens(body))


# --- 9 CCR 2503-6 (Colorado Works), PDF page 79 -----------------------------
# us-co/regulation/9-ccr-2503-6/3.609.2 lost the thirty "Days" values of the
# partial-month table.

_DAYS_COLUMNS = ((163.7, 212.0), (295.9, 360.4), (444.5, 500.5))
_PARTIAL_MONTH = (
    (".03288", ".36164", ".69041"),
    (".06575", ".39452", ".72329"),
    (".09863", ".42739", ".75617"),
    (".13151", ".46027", ".78904"),
    (".16439", ".49315", ".82192"),
    (".19726", ".52603", ".85480"),
    (".23014", ".55890", ".88768"),
    (".26302", ".59178", ".92054"),
    (".29590", ".62466", ".95342"),
    (".32876", ".65754", ".9863"),
)


def _partial_month_rows() -> list[Line]:
    lines: list[Line] = []
    for row, standards in enumerate(_PARTIAL_MONTH):
        baseline = 186.4 + 12.0 * row
        for column, ((days_x, standard_x), standard) in enumerate(
            zip(_DAYS_COLUMNS, standards, strict=True)
        ):
            days = row + 1 + 10 * column
            lines.append(
                (
                    str(days),
                    days_x - (2.8 if days >= 10 and column == 0 else 0.0),
                    baseline,
                    10.0,
                    "",
                )
            )
            lines.append((standard, standard_x, baseline, 10.0, ""))
    return lines


_CO_WORKS_PAGE_78: list[Line] = [
    *_CO_WORKS_HEADER,
    ("78", 529.0, 768.4, 10.0, "b"),
    ("3.609.2 Payments", 72.0, 620.0, 10.0, "b"),
    ("A.", 72.0, 643.5, 10.0, ""),
    ("Partial month payments", 108.0, 643.5, 10.0, ""),
]

_CO_WORKS_PAGE_79: list[Line] = [
    *_CO_WORKS_HEADER,
    ("79", 529.0, 768.4, 10.0, "b"),
    (
        "To calculate the partial month payments, the following table shall be used:",
        180.1,
        150.9,
        10.0,
        "",
    ),
    ("Days", 154.6, 174.4, 10.0, "b"),
    ("Standard", 205.6, 174.4, 10.0, "b"),
    ("Days", 289.5, 174.4, 10.0, "b"),
    ("Standard", 354.1, 174.4, 10.0, "b"),
    ("Days", 438.1, 174.4, 10.0, "b"),
    ("Standard", 494.2, 174.4, 10.0, "b"),
    *_partial_month_rows(),
    ("2.", 108.0, 318.4, 10.0, ""),
    ("Payment determination", 144.0, 318.4, 10.0, ""),
]


def test_colorado_works_partial_month_table_keeps_its_days() -> None:
    extraction = _manifest_extraction(
        "us-co-tanf-state-policy-manual.yaml", "us-co-ccr-9-2503-6-colorado-works"
    )
    content = _pdf([_CO_WORKS_PAGE_78, _CO_WORKS_PAGE_79])

    assert "Days Standard Days Standard Days Standard .03288 .36164 .69041" in " ".join(
        _content_only_lines(content, extraction)
    )

    body = _section_body(content, extraction, "3.609.2")
    rows = " ".join(
        f"{row + 1} {standards[0]} {row + 11} {standards[1]} {row + 21} {standards[2]}"
        for row, standards in enumerate(_PARTIAL_MONTH)
    )
    assert f"Days Standard Days Standard Days Standard {rows} 2. Payment determination" in body
    assert not {"78", "79"} & set(_tokens(body))


# --- 1 CCR 201-2 (Colorado income tax), PDF pages 296-297 -------------------
# us-co/regulation/1-ccr-201-2/39-22-2003 lost the final zero of each income
# band the PDF wraps onto a line of its own.

_CO_TAX_HEADER: list[Line] = [
    ("CODE OF COLORADO REGULATIONS", 72.0, 32.9, 12.0, "bi"),
    ("1 CCR 201-2", 469.9, 32.9, 12.0, "bi"),
    ("Taxation Division", 72.0, 46.7, 12.0, "bi"),
]

_CO_TAX_PAGE_296: list[Line] = [
    *_CO_TAX_HEADER,
    ("296", 520.0, 767.9, 12.0, "b"),
    ("Rule 39-22-2003.", 72.0, 553.7, 12.0, "b"),
    ("State Sales Tax Refund.", 180.0, 553.7, 12.0, "b"),
    (
        "Basis and Purpose. The bases for this rule are sections 39-21-112(1), 39-22-2001, 39-",
        72.0,
        579.5,
        12.0,
        "b",
    ),
    (
        "22-2002, and 39-22-2003, C.R.S. The purpose of this rule is to publish the amount of",
        72.0,
        593.3,
        12.0,
        "",
    ),
    ("(a)", 108.0, 700.1, 12.0, ""),
    ("2016 - 2020: No refund available.", 144.0, 700.1, 12.0, ""),
]

_CO_TAX_PAGE_297: list[Line] = [
    *_CO_TAX_HEADER,
    ("297", 520.0, 767.9, 12.0, "b"),
    ("(b)", 108.0, 83.3, 12.0, ""),
    ("2021:", 144.0, 83.3, 12.0, ""),
    ("Modified", 135.8, 109.6, 12.0, ""),
    ("Adjuste", 135.8, 123.4, 12.0, ""),
    ("d Gross", 135.8, 137.2, 12.0, ""),
    ("Income", 135.8, 151.0, 12.0, ""),
    ("$44,00", 193.0, 135.4, 12.0, ""),
    ("0 or", 193.0, 149.2, 12.0, ""),
    ("less", 193.0, 163.0, 12.0, ""),
    ("$44,00", 246.8, 135.4, 12.0, ""),
    ("1 -", 246.8, 149.2, 12.0, ""),
    ("$88,00", 246.8, 163.0, 12.0, ""),
    ("0", 246.8, 176.8, 12.0, ""),
    ("$88,001", 300.8, 135.4, 12.0, ""),
    ("-", 300.8, 149.2, 12.0, ""),
    ("$139,00", 300.8, 163.0, 12.0, ""),
    ("0", 300.8, 176.8, 12.0, ""),
    ("$139,001", 361.3, 135.4, 12.0, ""),
    ("-", 361.3, 149.2, 12.0, ""),
    ("$193,000", 361.3, 163.0, 12.0, ""),
    ("Single", 135.8, 203.0, 12.0, ""),
    ("Filer", 135.8, 216.8, 12.0, ""),
    ("Refund", 135.8, 230.6, 12.0, ""),
    ("$37", 193.0, 228.8, 12.0, ""),
    ("$49", 246.8, 228.8, 12.0, ""),
    ("$56", 300.8, 228.8, 12.0, ""),
    ("$68", 361.3, 228.8, 12.0, ""),
]


def test_colorado_sales_tax_refund_bands_keep_their_final_zero() -> None:
    extraction = _manifest_extraction(
        "us-co-income-tax-regulations.yaml", "co-sos-1-ccr-201-2-income-tax"
    )
    content = _pdf([_CO_TAX_PAGE_296, _CO_TAX_PAGE_297])

    assert "$44,00 1 - $88,00 $88,001 - $139,00 $139,001" in " ".join(
        _content_only_lines(content, extraction)
    )

    body = _section_body(content, extraction, "39-22-2003")
    assert "$44,00 1 - $88,00 0 $88,001 - $139,00 0 $139,001 - $193,000" in body
    assert not {"296", "297"} & set(_tokens(body))


# --- 16 Del. Admin. Code 3000, PDF pages 13-14 ------------------------------
# Delaware prints its page numbers at the head of the page. The work-hours
# table ends page 13, so its last row is the lowest line on the page; page
# 14's text stream emits the rest of the table after 3006.4's opening lines,
# so us-de/regulation/16/3000/3006.2 lost "20 20" and 3006.4 lost the rest.

_DE_HEADER: list[Line] = [
    ("TITLE 16 HEALTH AND SAFETY", 207.7, 38.4, 16.0, "b"),
    ("DELAWARE ADMINISTRATIVE CODE", 186.1, 57.4, 16.0, "b"),
]

_DE_PAGE_13: list[Line] = [
    *_DE_HEADER,
    ("13", 557.6, 45.4, 12.0, "b"),
    (
        "3006.2 TANF Employment and Training Participation and Participation Rates",
        36.0,
        100.0,
        10.0,
        "b",
    ),
    ("REQUIRED EMPLOYMENT AND TRAINING HOURS", 36.0, 640.7, 10.0, ""),
    ("Family Composition", 168.0, 687.5, 10.0, ""),
    ("Required", 352.0, 674.3, 10.0, ""),
    ("Hours", 352.0, 687.5, 10.0, ""),
    ("Per", 352.0, 700.7, 10.0, ""),
    ("Week", 352.0, 713.8, 10.0, ""),
    ("Minimum", 403.4, 674.3, 10.0, ""),
    ("Required", 403.4, 687.5, 10.0, ""),
    ("Core", 403.4, 700.6, 10.0, ""),
    ("Hours", 403.4, 713.8, 10.0, ""),
    ("Single Parent Family", 168.0, 727.8, 10.0, ""),
    ("A. With a child under 6 years old", 168.0, 753.3, 10.0, ""),
    ("20", 352.0, 753.3, 10.0, ""),
    ("20", 403.4, 753.3, 10.0, ""),
]

_DE_PAGE_14: list[Line] = [
    ("TITLE 16 HEALTH AND SAFETY", 207.7, 39.4, 16.0, "b"),
    ("DELAWARE ADMINISTRATIVE CODE", 186.1, 58.4, 16.0, "b"),
    ("14", 39.6, 43.8, 12.0, "b"),
    (
        "Numerator: # of TANF families with a work-eligible-individual who meet the "
        "participation requirement for the month",
        36.0,
        148.4,
        10.0,
        "",
    ),
    (
        "3006.4 TANF Employment and Training Activities Which Constitute Participation Under TANF",
        36.0,
        699.9,
        10.0,
        "b",
    ),
    (
        "The following are employment-related activities that count as participation:",
        54.0,
        713.9,
        10.0,
        "",
    ),
    ("B. No children under 6 years old", 168.0, 82.6, 10.0, ""),
    ("30", 352.0, 82.6, 10.0, ""),
    ("20", 403.4, 82.6, 10.0, ""),
    ("Two Parent Family", 168.0, 95.4, 10.0, ""),
    ("A. Not receiving subsidized child care", 168.0, 108.1, 10.0, ""),
    ("35", 352.0, 108.1, 10.0, ""),
    ("30", 403.4, 108.1, 10.0, ""),
    ("B. Receiving subsidized child care", 168.0, 120.9, 10.0, ""),
    ("55", 352.0, 120.9, 10.0, ""),
    ("50", 403.4, 120.9, 10.0, ""),
]


def test_delaware_work_hours_table_at_the_foot_of_a_page_keeps_its_hours() -> None:
    extraction = _manifest_extraction(
        "us-de-tanf-state-policy-manual.yaml",
        "de-dhss-dss-3000-technical-eligibility-for-cash-assistance",
    )
    content = _pdf([_DE_PAGE_13, _DE_PAGE_14])

    before = " ".join(_content_only_lines(content, extraction))
    assert "A. With a child under 6 years old Numerator:" in before
    assert before.endswith(
        "B. No children under 6 years old Two Parent Family "
        "A. Not receiving subsidized child care B. Receiving subsidized child care"
    )

    body = _section_body(content, extraction, "3006.2")
    assert "Single Parent Family A. With a child under 6 years old 20 20 Numerator:" in body
    assert not {"13", "14"} & set(_tokens(body))
    assert _section_body(content, extraction, "3006.4").endswith(
        "B. No children under 6 years old 30 20 Two Parent Family "
        "A. Not receiving subsidized child care 35 30 "
        "B. Receiving subsidized child care 55 50"
    )


# --- 16 Del. Admin. Code 9000 (Delaware SNAP), PDF page 12 ------------------
# Each section's statutory authority line prints the CFR title as a text run
# of its own, so "7 CFR 273.1" lost its "7".

_DE_SNAP_PAGE_12: list[Line] = [
    ("12", 41.9, 65.5, 12.0, "b"),
    ("TITLE 16 HEALTH AND SAFETY", 199.8, 55.6, 14.0, "b"),
    ("DELAWARE ADMINISTRATIVE CODE", 181.9, 76.7, 14.0, "b"),
    ("9013.1 Household Definition", 54.0, 107.1, 10.0, "b"),
    ("7", 54.0, 118.6, 10.0, ""),
    ("CFR 273.1", 90.0, 118.6, 10.0, ""),
    (
        "A) General Definition - a household is composed of one of the following individuals",
        54.0,
        130.1,
        10.0,
        "",
    ),
    ("1. An individual living alone", 54.0, 164.6, 10.0, ""),
]


def test_delaware_snap_authority_line_keeps_its_cfr_title() -> None:
    extraction = _manifest_extraction(
        "us-de-snap-rules.yaml", "de-dhss-dss-9000-food-stamp-program"
    )
    content = _pdf([_DE_SNAP_PAGE_12])

    assert "9013.1 Household Definition CFR 273.1 A) General" in " ".join(
        _content_only_lines(content, extraction)
    )

    blocks = documents_module._extract_pdf_blocks(content, extraction=extraction)
    section = next(block for block in blocks if block.metadata.get("section_label") == "9013.1")
    # Without its "7", "CFR 273.1" read as a continuation of the heading.
    assert section.heading == "9013.1 Household Definition"
    assert section.body.startswith("7 CFR 273.1 A) General Definition")
    assert "12" not in _tokens(section.body)


# --- Differential: a page with no table -------------------------------------

_WORDS = st.text(alphabet="abcdefghij", min_size=1, max_size=8)
_SENTENCES = st.lists(_WORDS, min_size=1, max_size=6).map(" ".join)
_PAGE_FILTERS: dict[str, Any] = {
    "drop_lines": ["RUNNING HEAD", "RUNNING FOOT"],
    "drop_line_patterns": [r"^\d{1,3}$"],
}


@st.composite
def _pages_without_tables(draw: st.DrawFn) -> list[Line]:
    """Body text, running header and footer, and a page number in either margin.

    The page number is a bare number above or below all the body text, alone
    on its line or sharing the running head's row; the content stream may
    emit it first, last or anywhere between, as real PDFs do.
    """
    sentences = draw(st.lists(_SENTENCES, min_size=1, max_size=12))
    body: list[Line] = [
        (sentence, 72.0, 120.0 + 14.0 * index, 10.0, "") for index, sentence in enumerate(sentences)
    ]
    furniture: list[Line] = []
    if draw(st.booleans()):
        furniture.append(("RUNNING HEAD", 72.0, 60.0, 9.0, "b"))
    if draw(st.booleans()):
        furniture.append(("RUNNING FOOT", 72.0, 752.0, 9.0, ""))
    number = str(draw(st.integers(min_value=1, max_value=999)))
    at_top = draw(st.booleans())
    beside_furniture = draw(st.booleans())
    if at_top:
        page_number: Line = (number, 520.0, 60.0 if beside_furniture else 40.0, 10.0, "b")
    else:
        page_number = (number, 300.0, 752.0 if beside_furniture else 770.0, 10.0, "b")
    lines = body + furniture
    position = draw(st.integers(min_value=0, max_value=len(lines)))
    return [*lines[:position], page_number, *lines[position:]]


@settings(max_examples=60, deadline=None)
@given(pages=st.lists(_pages_without_tables(), min_size=1, max_size=3))
def test_page_without_a_table_loses_the_same_lines_as_before(pages: list[list[Line]]) -> None:
    content = _pdf(pages)

    assert _filtered_lines(content, _PAGE_FILTERS) == _content_only_lines(content, _PAGE_FILTERS)


# --- Properties on any page -------------------------------------------------


_ROW_KINDS = ("text", "labelled cells", "bare cells", "blank")


@st.composite
def _pages_with_tables(draw: st.DrawFn) -> tuple[list[Line], list[str]]:
    """A page of rows, and the lines the margin rule must keep, in stream order.

    A row holds body text, numeric cells beside a text label, bare numeric
    cells alone, or nothing; a running head and a page number may frame it.
    Every number on the page is distinct, so each line can be told apart.
    The expected lines follow from the layout alone: a bare number survives
    when body text shares its row or lies both above and below it.
    """
    kinds = draw(st.lists(st.sampled_from(_ROW_KINDS), min_size=1, max_size=14))
    widths = [draw(st.integers(min_value=1, max_value=3)) for _kind in kinds]
    has_page_number = draw(st.booleans())
    has_running_head = draw(st.booleans())
    count = sum(
        width for kind, width in zip(kinds, widths, strict=True) if kind.endswith("cells")
    ) + int(has_page_number)
    numbers = iter(
        str(number)
        for number in draw(
            st.lists(
                st.integers(min_value=0, max_value=1200),
                min_size=count,
                max_size=count,
                unique=True,
            )
        )
    )
    text_rows = [row for row, kind in enumerate(kinds) if kind in ("text", "labelled cells")]
    lines: list[Line] = []
    expected: list[str] = []
    if has_running_head:
        lines.append(("RUNNING HEAD", 72.0, 60.0, 9.0, "b"))
    if has_page_number:
        lines.append((next(numbers), 300.0, 770.0, 10.0, ""))
    for row, (kind, width) in enumerate(zip(kinds, widths, strict=True)):
        baseline = 120.0 + 16.0 * row
        if kind in ("text", "labelled cells"):
            sentence = draw(_SENTENCES)
            lines.append((sentence, 72.0, baseline, 10.0, ""))
            expected.append(sentence)
        if kind.endswith("cells"):
            inside = kind == "labelled cells" or (
                any(other < row for other in text_rows) and any(other > row for other in text_rows)
            )
            for column in range(width):
                cell = next(numbers)
                lines.append((cell, 300.0 + 60.0 * column, baseline, 10.0, ""))
                if inside:
                    expected.append(cell)
    return lines, expected


@settings(max_examples=80, deadline=None)
@given(case=_pages_with_tables())
def test_margin_rule_keeps_exactly_the_bare_numbers_inside_the_body(
    case: tuple[list[Line], list[str]],
) -> None:
    page, expected = case
    content = _pdf([page])
    filters: dict[str, Any] = {"drop_lines": ["RUNNING HEAD"], "drop_line_patterns": [r"^\d+$"]}
    before = _content_only_lines(content, filters)
    after = _filtered_lines(content, filters)

    assert after == expected
    # Never more is dropped than before: the old output is a subsequence of
    # the new one, and only bare numbers come back.
    remaining = iter(after)
    assert all(any(line == candidate for candidate in remaining) for line in before)
    assert all(re.fullmatch(r"\d+", line) for line in after if line not in before)


def test_a_bare_number_above_all_body_text_is_still_a_page_number() -> None:
    """Position decides: a cell with no body text above it, on its row or beside it, goes."""
    content = _pdf(
        [
            [
                ("RUNNING HEAD", 72.0, 60.0, 9.0, "b"),
                ("7", 300.0, 60.0, 9.0, "b"),
                ("3", 300.0, 120.0, 10.0, ""),
                ("Body text below the number.", 72.0, 140.0, 10.0, ""),
                ("4", 300.0, 160.0, 10.0, ""),
                ("More body text.", 72.0, 180.0, 10.0, ""),
            ]
        ]
    )
    filters: dict[str, Any] = {"drop_lines": ["RUNNING HEAD"], "drop_line_patterns": [r"^\d+$"]}

    assert _filtered_lines(content, filters) == [
        "Body text below the number.",
        "4",
        "More body text.",
    ]


def test_a_line_the_page_cannot_place_keeps_the_content_only_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OCR text has no position on the page, so a bare number there goes as before."""
    content = _pdf(
        [[("Body text above.", 72.0, 120.0, 10.0, ""), ("Body text below.", 72.0, 160.0, 10.0, "")]]
    )
    real_page_text = documents_module._pdf_page_text

    def page_text_with_unplaced_number(page: Any, *, extraction: dict[str, Any]) -> str:
        above, below = real_page_text(page, extraction=extraction).strip().split("\n")
        return f"{above}\n12\n{below}\n"

    monkeypatch.setattr(documents_module, "_pdf_page_text", page_text_with_unplaced_number)

    assert _filtered_lines(content, {"drop_line_patterns": [r"^\d+$"]}) == [
        "Body text above.",
        "Body text below.",
    ]


def test_rotated_text_keeps_the_content_only_rule() -> None:
    """Rows mean nothing for text that does not run left to right."""
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 120), "Body text above.", fontsize=10)
    page.insert_text((300, 140), "12", fontsize=10, rotate=90)
    page.insert_text((72, 160), "Body text below.", fontsize=10)
    content = document.tobytes()
    document.close()

    assert _filtered_lines(content, {"drop_line_patterns": [r"^\d+$"]}) == [
        "Body text above.",
        "Body text below.",
    ]
