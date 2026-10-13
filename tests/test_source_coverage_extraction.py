"""Source coverage as the official-document extractor records it.

Example tests for the HTML, PDF and DOCX paths, properties of the figures the
extractor records (they are bounded, 1.0 when nothing in the region is lost, never
raised by removing a row, and recording them never changes the rows), and a
differential test: the figures written to a coverage report equal a recomputation
from the written rows and the source bytes that shares no code with the extractor.
"""

from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import fitz
import lxml.html
import pytest
import yaml
from bs4 import BeautifulSoup
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.source_coverage import (
    SourceCoverage,
    SourceCoverageReport,
    SourceRegion,
    row_texts,
    words,
)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _measure(
    content: bytes, source_format: str, extraction: dict[str, Any] | None = None
) -> tuple[tuple[Any, ...], SourceRegion, SourceCoverage]:
    region = SourceRegion()
    blocks = documents._extract_blocks(
        content,
        source_format,
        source_url="https://example.test/source",
        title="Manifest title",
        extraction=extraction,
        region=region,
    )
    return blocks, region, region.measure(row_texts(blocks))


def _count(text: str) -> int:
    return len(words(text))


def _pdf(pages: list[str]) -> bytes:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def _paragraph(*runs: str, style: str | None = None) -> str:
    properties = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    body = "".join(f'<w:r><w:t xml:space="preserve">{run}</w:t></w:r>' for run in runs)
    return f"<w:p>{properties}{body}</w:p>"


def _table(*rows: list[str]) -> str:
    """A table; each cell is one paragraph, written as it is (already paragraph XML)."""
    return (
        "<w:tbl>"
        + "".join(
            "<w:tr>" + "".join(f"<w:tc>{cell}</w:tc>" for cell in row) + "</w:tr>" for row in rows
        )
        + "</w:tbl>"
    )


def _docx(*body: str) -> bytes:
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{_W}"><w:body>'
        + "".join(body)
        + "<w:sectPr/></w:body></w:document>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


# --------------------------------------------------------------------------- HTML

PAGE = b"""<html><head><title>Chapter 5</title><script>var hidden = "script words";</script>
<style>p { color: red }</style></head><body>
<header>Department of Example banner</header>
<nav>Home About Contact</nav>
<main>
  <h1>Chapter 5 Eligibility</h1>
  <p>First paragraph kept.</p>
  <div>Bare summary text that the default text tags skip.</div>
  <aside>Related links inside main</aside>
  <button>Print</button>
  <ul><li>Item kept</li></ul>
  <!-- a comment is not text -->
</main>
<footer>Contact the webmaster</footer></body></html>"""


def test_html_region_is_the_content_root_and_bare_text_is_missing() -> None:
    blocks, region, figures = _measure(PAGE, "html")

    assert [(block.heading, block.body) for block in blocks] == [
        ("Chapter 5 Eligibility", "First paragraph kept.\n\nItem kept")
    ]
    assert region.kind == "html_main_content"
    assert region.texts == (
        "Chapter 5 Eligibility First paragraph kept. "
        "Bare summary text that the default text tags skip. Item kept",
    )
    assert figures.region_words == 17
    assert figures.kept_words == 8
    assert [
        (run.offset, run.words, run.text, run.before) for run in figures.longest_missing_runs
    ] == [
        (
            6,
            9,
            "Bare summary text that the default text tags skip.",
            # The 40 characters before the run, from a word start.
            "5 Eligibility First paragraph kept.",
        )
    ]
    # The aside and the button sat inside the content root; the banner, the menu and
    # the footer were never in the region, and a script holds no words.
    assert figures.deliberately_dropped_words == _count("Related links inside main Print") == 5


def test_html_content_selector_names_the_region() -> None:
    page = b"""<html><body><div id="chrome"><p>Search the site</p></div>
    <div id="law"><p>Section text.</p><span>Loose history note.</span><input value="x">
    <div class="breadcrumb">Title 36 Part 8</div></div></body></html>"""
    blocks, region, figures = _measure(page, "html", {"html_content_selector": "#law"})

    assert [block.body for block in blocks] == ["Section text."]
    assert region.kind == "html_content_selector"
    assert (figures.region_words, figures.kept_words) == (5, 2)
    assert [run.text for run in figures.longest_missing_runs] == ["Loose history note."]
    assert figures.deliberately_dropped_words == _count("Title 36 Part 8")


def test_html_text_selector_nodes_are_the_region() -> None:
    page = b"""<html><body><main><form>Search and filter the list</form>
    <div class="card"><div class="summary">The state extends coverage.</div>
    <button>Approval Package</button><div>Effective Date: July 1, 2024</div></div>
    <div class="card"><div class="summary">A second amendment.</div></div></main></body></html>"""
    blocks, region, figures = _measure(page, "html", {"html_text_selector": "div.card"})

    assert region.kind == "html_text_selector"
    assert region.texts == (
        "The state extends coverage. Effective Date: July 1, 2024",
        "A second amendment.",
    )
    assert figures.coverage == 1.0
    assert figures.region_words == 12
    # The form outside the cards is not in the region; the button inside one was dropped.
    assert figures.deliberately_dropped_words == 2
    assert "Search and filter" not in " ".join(block.body for block in blocks)


def test_html_headings_with_no_text_below_them_are_missing() -> None:
    page = b"<html><body><main><h2>Part A General</h2><h3>Section 1</h3><p>Text one.</p></main></body></html>"
    blocks, _region, figures = _measure(page, "html")

    assert [(block.heading, block.body) for block in blocks] == [("Section 1", "Text one.")]
    assert (figures.region_words, figures.kept_words) == (7, 4)
    assert [run.text for run in figures.longest_missing_runs] == ["Part A General"]


def test_html_nested_dropped_nodes_are_counted_once() -> None:
    page = b"""<html><body><main><p>Kept text.</p>
    <aside>Outer aside <aside>inner aside</aside> <button>Print</button> tail</aside>
    <nav>Menu <nav>Submenu</nav></nav></main></body></html>"""
    _blocks, _region, figures = _measure(page, "html")

    assert (figures.region_words, figures.kept_words) == (2, 2)
    assert figures.deliberately_dropped_words == _count(
        "Outer aside inner aside Print tail Menu Submenu"
    )


def test_html_text_selector_that_matches_nothing_reads_the_whole_root() -> None:
    page = b"<html><body><main><p>First paragraph.</p><div>Bare text.</div></main></body></html>"
    blocks, region, figures = _measure(page, "html", {"html_text_selector": "div.absent"})

    # The walk found no text node, so the extractor fell back to the whole content root.
    assert [block.body for block in blocks] == ["First paragraph. Bare text."]
    assert region.kind == "html_main_content"
    assert region.texts == ("First paragraph. Bare text.",)
    assert (figures.region_words, figures.kept_words, figures.coverage) == (4, 4, 1.0)


def test_html_page_with_no_text_tags_is_read_whole() -> None:
    page = b"<html><body><div>Only bare text here.</div></body></html>"
    blocks, region, figures = _measure(page, "html")

    assert [block.body for block in blocks] == ["Only bare text here."]
    assert region.kind == "html_main_content"
    assert (figures.region_words, figures.kept_words, figures.coverage) == (4, 4, 1.0)


LABELED_PAGE = b"""<html><body><main>
<p>Preamble printed before any section.</p>
<p>101 Purpose. This part sets the rules.</p>
<p>More purpose text.</p>
<div>An unlabeled note in a div.</div>
<p>102 Scope. Applies statewide.</p>
<p>History: adopted in 2020.</p>
<p>Text after the stop line.</p>
</main></body></html>"""
LABELED_EXTRACTION = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>\d{3}) (?P<heading>[A-Z][a-z]+)\.\s*(?P<body>.*)$",
    "stop_text_pattern": r"^History:",
}


def test_html_labeled_sections_region_ends_at_the_stop_and_holds_the_preamble() -> None:
    blocks, region, figures = _measure(LABELED_PAGE, "html", LABELED_EXTRACTION)

    assert [(block.heading, block.body) for block in blocks] == [
        ("Purpose", "This part sets the rules.\n\nMore purpose text."),
        ("Scope", "Applies statewide."),
    ]
    assert region.kind == "html_main_content"
    assert region.texts == (
        "Preamble printed before any section. 101 Purpose. This part sets the rules. "
        "More purpose text. An unlabeled note in a div. 102 Scope. Applies statewide.",
    )
    # 5 + 2 + 5 + 3 + 6 + 2 + 2 words before the stop; the rows hold 1 + 8 + 1 + 2.
    assert figures.region_words == 25
    assert figures.kept_words == 12
    # The section numbers live in the rows' citation paths, not their headings or
    # bodies, so they count as missing with the text beside them.
    assert sorted(run.text for run in figures.longest_missing_runs) == [
        "An unlabeled note in a div. 102",
        "Preamble printed before any section. 101",
    ]


def test_html_labeled_sections_without_a_stop_read_the_whole_root() -> None:
    extraction = {
        key: value for key, value in LABELED_EXTRACTION.items() if key != "stop_text_pattern"
    }
    _blocks, region, figures = _measure(LABELED_PAGE, "html", extraction)

    assert region.texts[0].endswith("History: adopted in 2020. Text after the stop line.")
    assert figures.region_words == 25 + 9
    assert figures.kept_words == 12 + 9


def test_html_anchor_ranges_are_read_whole() -> None:
    page = b"""<html><body><main><p>Lead-in outside the range.</p>
    <h2 id="s1">Section 1</h2><p>Range text one.</p><div>Bare range text.</div>
    <h2 id="s2">Section 2</h2><p>Outside again.</p></main></body></html>"""
    blocks, region, figures = _measure(
        page,
        "html",
        {"segmentation": "anchor_range", "html_start_selector": "#s1", "html_stop_selector": "#s2"},
    )

    assert [block.body for block in blocks] == ["Section 1 Range text one. Bare range text."]
    assert region.kind == "html_anchor_range"
    assert (figures.region_words, figures.kept_words, figures.coverage) == (8, 8, 1.0)


def test_html_webworks_page_is_the_region_and_its_mini_toc_is_dropped() -> None:
    page = b"""<html><body><div id="page_content">
    <div class="WebWorks_MiniTOC">On this page Purpose Scope</div>
    <div class="Heading_1">100 Purpose</div>
    <div class="Body_Text">Body text kept.</div>
    <div class="Caption">A caption the walk skips.</div>
    </div><div id="tabs">General Details</div></body></html>"""
    blocks, region, figures = _measure(page, "html")

    assert [(block.heading, block.body) for block in blocks] == [("100 Purpose", "Body text kept.")]
    assert region.kind == "html_webworks_page"
    assert (figures.region_words, figures.kept_words) == (10, 5)
    assert [run.text for run in figures.longest_missing_runs] == ["A caption the walk skips."]
    assert figures.deliberately_dropped_words == _count("On this page Purpose Scope")


def test_html_br_breaks_page_keeps_all_of_its_selected_text() -> None:
    page = (
        b'<html><body><div id="menu"><a href="/">Statutes</a></div><div id="StatuteText">'
        b"&sect;5-312.<br><br>(a) This section is not intended to create an incentive.<br>"
        b"(b) The Department shall adopt regulations.<br><br>(c) Funds are subject to budget."
        b"</div></body></html>"
    )
    blocks, region, figures = _measure(
        page, "html", {"html_text_selector": "#StatuteText", "html_br_breaks": True}
    )

    assert len(blocks) == 1 and blocks[0].body.count("\n\n") == 2
    assert region.kind == "html_text_selector"
    assert figures.coverage == 1.0 and figures.region_words == 2 + 10 + 6 + 6
    # Without the selector the same page keeps only its menu: the Maryland loss.
    old_blocks, _old_region, old = _measure(page, "html", {"html_content_selector": "body"})
    assert (old.region_words, old.kept_words) == (25, 25)
    assert [block.body for block in old_blocks] == [
        "Statutes \u00a75-312. (a) This section is not intended to create an incentive. "
        "(b) The Department shall adopt regulations. (c) Funds are subject to budget."
    ]


def test_html_default_tags_beside_bare_statute_text_lose_the_statute() -> None:
    page = (
        b'<html><body><ul><li><a href="/">Statutes</a></li><li><a href="/x">Counties</a></li></ul>'
        b'<div id="StatuteText">&sect;5-312. (a) This section is not intended to create an '
        b"incentive.</div></body></html>"
    )
    blocks, _region, figures = _measure(page, "html", {"html_content_selector": "body"})

    assert [block.body for block in blocks] == ["Statutes\n\nCounties"]
    assert (figures.region_words, figures.kept_words) == (14, 2)
    assert figures.longest_missing_runs[0].words == 12
    assert figures.longest_missing_runs[0].text.endswith("not intended to create an incentive.")


def test_html_text_before_matches_get_text_until_the_stop() -> None:
    soup = BeautifulSoup(
        "<div id='r'>lead <b>bold</b><script>var s;</script><!-- c --><p id='a'>first</p>"
        "<template><i>t</i></template><p id='b'>second <span id='inner'>deep</span> tail</p>"
        "<p id='c'>third</p></div>",
        "lxml",
    )
    root = soup.select_one("#r")
    assert root is not None

    def before(selector: str) -> tuple[str, bool]:
        stop = soup.select_one(selector)
        assert stop is not None
        return documents._html_text_before(root, stop)

    assert documents._html_text_before(root, None) == (
        "lead bold first second deep tail third",
        False,
    )
    assert before("#c") == ("lead bold first second deep tail", True)
    assert before("#inner") == ("lead bold first second", True)
    assert before("#a") == ("lead bold", True)
    assert before("#r") == ("", True)
    outside = BeautifulSoup("<p>elsewhere</p>", "lxml").p
    assert documents._html_text_before(root, outside) == (root.get_text(" ", strip=True), False)


def test_html_json_field_is_measured_and_json_records_are_not() -> None:
    payload = json.dumps(
        {"content": "<main><p>Kept paragraph.</p><div>Lost div text.</div></main>"}
    ).encode()
    blocks, region, figures = _measure(payload, "json", {"json_html_field": "content"})

    assert [block.body for block in blocks] == ["Kept paragraph."]
    assert region.kind == "html_main_content"
    assert (figures.region_words, figures.kept_words) == (5, 2)

    records = json.dumps({"rows": [{"id": "1", "text": "Record text."}]}).encode()
    unmeasured = SourceRegion()
    documents._extract_blocks(
        records,
        "json",
        source_url="u",
        title="T",
        extraction={
            "segmentation": "records",
            "json_records_path": "rows",
            "json_record_label_field": "id",
            "json_record_text_field": "text",
        },
        region=unmeasured,
    )
    assert not unmeasured.measured


def test_html_source_region_reads_what_an_extraction_would() -> None:
    region = documents.html_source_region(PAGE, extraction=None)
    assert region.kind == "html_main_content"
    assert region.texts == _measure(PAGE, "html")[1].texts
    with pytest.raises(ValueError, match="html content selector did not match"):
        documents.html_source_region(PAGE, extraction={"html_content_selector": "#absent"})


# --------------------------------------------------------------------------- PDF


def test_pdf_pages_are_read_whole() -> None:
    pages = [
        "Page one text about eligibility.\nA second line.",
        "",
        "Page three closes the notice.",
    ]
    blocks, region, figures = _measure(_pdf(pages), "pdf")

    assert [block.metadata["page_number"] for block in blocks] == [1, 3]
    assert region.kind == "pdf_pages"
    assert region.texts == (
        "Page one text about eligibility. A second line.",
        "Page three closes the notice.",
    )
    assert figures.region_words == _count(" ".join(pages)) == 13
    assert figures.coverage == 1.0 and figures.deliberately_dropped_words == 0


def test_pdf_single_block_reads_every_page() -> None:
    blocks, region, figures = _measure(
        _pdf(["An Act about benefit amounts.", "Section 1. Amounts rise."]),
        "pdf",
        {"segmentation": "single_block"},
    )
    assert len(blocks) == 1
    assert region.kind == "pdf_pages"
    assert (figures.region_words, figures.coverage) == (9, 1.0)


LABELED_PDF_PAGES = [
    "STATE MANUAL\nTable of contents\n100 Purpose\n200 Scope\nCHAPTER ONE",
    "Manual page 2\nFront matter that follows the start marker.\n100 PURPOSE\nPurpose body line one.\n"
    "Purpose body line two.",
    "Manual page 3\n100 PURPOSE\nPurpose body continues here.\nRev. 2024\n200 SCOPE\nScope body line.",
]
LABELED_PDF_EXTRACTION = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>\d{3}) (?P<heading>[A-Z]+)$",
    "start_after_pattern": r"^CHAPTER ONE$",
    "page_header_patterns": [r"Manual page \d+"],
    "drop_line_patterns": [r"^Rev\. \d{4}$"],
}


def test_pdf_labeled_sections_region_starts_after_the_marker() -> None:
    blocks, region, figures = _measure(_pdf(LABELED_PDF_PAGES), "pdf", LABELED_PDF_EXTRACTION)

    assert [(block.heading, block.body) for block in blocks] == [
        (
            "100 PURPOSE",
            "Purpose body line one. Purpose body line two. Purpose body continues here.",
        ),
        ("200 SCOPE", "Scope body line."),
    ]
    assert region.kind == "pdf_page_range"
    assert region.texts == (
        "Front matter that follows the start marker.",
        "100 PURPOSE",
        "Purpose body line one.",
        "Purpose body line two.",
        "100 PURPOSE",
        "Purpose body continues here.",
        "200 SCOPE",
        "Scope body line.",
    )
    # Dropped on purpose: two running headers after the marker (3 words each), the
    # revision line (2) and the heading restated at the top of page 3 (2, read then
    # dropped). Page 1, before the marker, is outside the region.
    assert figures.deliberately_dropped_words == 3 + 3 + 2 + 2
    assert figures.region_words == 7 + 2 + 4 + 4 + 4 + 2 + 3
    assert figures.kept_words == figures.region_words - 7
    assert [(run.offset, run.text) for run in figures.longest_missing_runs] == [
        (0, "Front matter that follows the start marker.")
    ]


def test_pdf_labeled_sections_keep_repeated_headings_in_the_region_when_told_to() -> None:
    extraction = {**LABELED_PDF_EXTRACTION, "drop_repeated_section_headings": False}
    blocks, _region, figures = _measure(_pdf(LABELED_PDF_PAGES), "pdf", extraction)

    assert [block.heading for block in blocks] == ["100 PURPOSE", "100 PURPOSE", "200 SCOPE"]
    assert figures.deliberately_dropped_words == 3 + 3 + 2
    assert figures.region_words == 7 + 2 + 4 + 4 + 2 + 4 + 2 + 3
    assert figures.missing_words == 7


def test_pdf_page_windows_bound_the_region() -> None:
    pages = [
        "Masthead text to exclude.\nLAW 5 Benefits\nFirst law line.",
        "Middle page outside every window.",
        "Second window opens.\nLAW 9 Taxes\nSecond law line.\nEND OF LAW\nTrailing text.",
    ]
    blocks, region, figures = _measure(
        _pdf(pages),
        "pdf",
        {
            "segmentation": "single_block",
            "page_windows": [
                {"start_page": 1, "end_page": 1, "start_at_pattern": r"^LAW 5"},
                {
                    "start_page": 3,
                    "end_page": 3,
                    "start_at_pattern": r"^LAW 9",
                    "stop_at_pattern": r"^END OF LAW$",
                },
            ],
        },
    )

    assert region.kind == "pdf_page_windows"
    assert region.texts == ("LAW 5 Benefits", "First law line.", "LAW 9 Taxes", "Second law line.")
    assert blocks[0].body == "LAW 5 Benefits\nFirst law line.\n\nLAW 9 Taxes\nSecond law line."
    assert (figures.region_words, figures.coverage) == (12, 1.0)


def test_pdf_numbered_sections_leave_the_text_before_the_first_section_missing() -> None:
    pages = [
        "Short title and preamble text.\n100. DEFINITIONS\nIn this Act, income means wages."
        "\n200. RATES\nThe rate is 5 percent."
    ]
    blocks, region, figures = _measure(_pdf(pages), "pdf", {"segmentation": "numbered_sections"})

    assert [block.heading for block in blocks] == ["100. DEFINITIONS", "200. RATES"]
    assert region.kind == "pdf_page_range"
    assert figures.missing_words == 5
    assert [run.text for run in figures.longest_missing_runs] == ["Short title and preamble text."]


# --------------------------------------------------------------------------- DOCX


def test_docx_region_reads_words_whole_where_table_runs_split_them() -> None:
    content = _docx(
        _paragraph("Chapter 701", style="Heading1"),
        _paragraph("Intro", " para", "graph."),
        _table(
            [_paragraph("Page | 702", ".000"), _paragraph("Eligi", "bility")],
            [_paragraph("Income limit"), _paragraph("$1,", "200")],
        ),
        f'<w:sdt xmlns:w="{_W}"><w:sdtContent>{_paragraph("Control text the body walk skips.")}</w:sdtContent></w:sdt>',
    )
    blocks, region, figures = _measure(content, "docx")

    assert [(block.heading, block.body) for block in blocks] == [
        ("Chapter 701", "Intro paragraph.\n\nPage | 702 .000 | Eligi bility Income limit | $1, 200")
    ]
    assert region.kind == "docx_body"
    assert region.texts == (
        "Chapter 701",
        "Intro paragraph.",
        "Page | 702.000 | Eligibility",
        "Income limit | $1,200",
        "Control text the body walk skips.",
    )
    # "Eligibility" is one word in Word and two in the row; the content control is unread.
    # 2 + 2 + 4 + 4 + 6 words; the row lacks "eligibility" and the control's six.
    assert figures.region_words == 18
    assert figures.kept_words == 11
    assert sorted(run.text for run in figures.longest_missing_runs) == [
        "Control text the body walk skips.",
        "Eligibility",
    ]


DOCX_LABELED = _docx(
    _paragraph("Cover page text."),
    _paragraph("PART ONE"),
    _paragraph("Unlabeled lead-in."),
    _paragraph("701.100: Purpose"),
    _paragraph("Purpose body."),
    _paragraph("Page 12"),
    _table([_paragraph("Standard"), _paragraph("Amount")]),
    _paragraph("701.200: Scope"),
    _paragraph("Scope body."),
    _paragraph("REGULATORY AUTHORITY"),
    _paragraph("After the stop."),
)
DOCX_LABELED_EXTRACTION = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>\d{3}\.\d{3}): (?P<heading>.+)$",
    "start_after_pattern": r"^PART ONE$",
    "stop_text_pattern": r"^REGULATORY AUTHORITY$",
}


def test_docx_labeled_sections_region_lies_between_the_markers() -> None:
    blocks, region, figures = _measure(DOCX_LABELED, "docx", DOCX_LABELED_EXTRACTION)

    assert [(block.heading, block.body) for block in blocks] == [
        ("701.100 Purpose", "Purpose body.\n\nStandard | Amount"),
        ("701.200 Scope", "Scope body."),
    ]
    assert region.kind == "docx_body"
    assert region.texts == (
        "Unlabeled lead-in.",
        "701.100: Purpose",
        "Purpose body.",
        "Standard | Amount",
        "701.200: Scope",
        "Scope body.",
    )
    assert figures.deliberately_dropped_words == _count("Page 12")
    assert (figures.region_words, figures.kept_words) == (15, 12)
    assert [run.text for run in figures.longest_missing_runs] == ["Unlabeled lead-in."]


def test_docx_styled_sections_merge_restated_headings_on_purpose() -> None:
    content = _docx(
        _paragraph("Lead-in before any heading."),
        _table([_paragraph("Table before a heading")]),
        _paragraph("44-207 INCOME ELIGIBILITY", style="Heading2"),
        _paragraph("Body one."),
        _paragraph("Page 3"),
        _paragraph("44-207 INCOME ELIGIBILITY (Continued)", style="Heading2"),
        _table([_paragraph("Family", " size"), _paragraph("Lim", "it")]),
        _paragraph("44-211 RESOURCES", style="Heading2"),
        _paragraph("Body two."),
    )
    blocks, region, figures = _measure(
        content,
        "docx",
        {
            "segmentation": "styled_labeled_sections",
            "section_heading_pattern": r"^(?P<label>\d{2}-\d{3}) (?P<heading>[A-Z ]+)$",
        },
    )

    assert [
        (block.heading, block.body, block.metadata["heading_occurrences"]) for block in blocks
    ] == [
        ("44-207 INCOME ELIGIBILITY", "Body one.\n\nFamily size | Lim it", 2),
        ("44-211 RESOURCES", "Body two.", 1),
    ]
    assert region.kind == "docx_body"
    # Dropped on purpose: the page line (2 words) and the restated heading (5).
    assert figures.deliberately_dropped_words == 2 + 5
    assert sorted(run.text for run in figures.longest_missing_runs) == [
        "Lead-in before any heading. Table before a heading",
        "Limit",
    ]
    assert figures.missing_words == 9 + 1


# --------------------------------------------------------------------------- the report


def _write_scope(
    tmp_path: Path,
) -> tuple[CorpusArtifactStore, documents.OfficialDocumentExtractReport]:
    sources = tmp_path / "retained"
    sources.mkdir(parents=True)
    (sources / "page.html").write_bytes(PAGE)
    (sources / "labeled.html").write_bytes(LABELED_PAGE)
    (sources / "manual.pdf").write_bytes(_pdf(LABELED_PDF_PAGES))
    (sources / "pages.pdf").write_bytes(_pdf(["Page one text.", "Page two text."]))
    (sources / "chapter.docx").write_bytes(DOCX_LABELED)
    (sources / "rates.csv").write_bytes(b"year,rate\n2025,4.5\n2026,4.7\n")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_id": name,
                        "jurisdiction": "us-xx",
                        "document_class": "policy",
                        "title": title,
                        "source_url": f"https://example.test/{name}",
                        "local_path": str(sources / filename),
                        "source_format": filename.rsplit(".", 1)[1],
                        **({"extraction": extraction} if extraction else {}),
                    }
                    for name, title, filename, extraction in (
                        ("page", "Eligibility chapter summary", "page.html", None),
                        ("labeled", "Labeled part", "labeled.html", LABELED_EXTRACTION),
                        ("manual", "State manual", "manual.pdf", LABELED_PDF_EXTRACTION),
                        ("pages", "Notice", "pages.pdf", None),
                        ("chapter", "Chapter 701", "chapter.docx", DOCX_LABELED_EXTRACTION),
                        ("rates", "Rate table", "rates.csv", None),
                    )
                ]
            }
        )
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = documents.extract_official_documents(
        store, manifest_path=manifest, version="2026-10-13"
    )
    return store, report


def test_the_coverage_report_gains_one_optional_field(tmp_path: Path) -> None:
    store, report = _write_scope(tmp_path)
    written = json.loads(report.coverage_path.read_text())
    recomputed = compare_provision_coverage(
        load_source_inventory(report.inventory_path),
        load_provisions(report.provisions_path),
        jurisdiction="us-xx",
        document_class="policy",
        version="2026-10-13",
    )

    source_coverage = written.pop("source_coverage")
    # Every field that was there before is unchanged: without the new key the file
    # holds exactly what the store writes for the coverage report alone.
    assert written == recomputed.to_mapping()
    alone = store.coverage_path("us-xx", "policy", "alone")
    store.write_json(alone, recomputed.to_mapping())
    assert json.loads(alone.read_text()) == written
    assert report.coverage == recomputed and report.coverage.complete
    assert report.source_coverage == SourceCoverageReport.from_mapping(source_coverage)

    prefix = "sources/us-xx/policy/2026-10-13/official-documents/"
    assert [
        (row["source_path"], row["source_format"], row["region"])
        for row in source_coverage["sources"]
    ] == [
        (prefix + "page.html", "html", "html_main_content"),
        (prefix + "labeled.html", "html", "html_main_content"),
        (prefix + "manual.pdf", "pdf", "pdf_page_range"),
        (prefix + "pages.pdf", "pdf", "pdf_pages"),
        (prefix + "chapter.docx", "docx", "docx_body"),
    ]
    assert source_coverage["unmeasured"] == [
        {"source_path": prefix + "rates.csv", "source_format": "csv"}
    ]
    assert source_coverage["measure"] == "source-coverage-v1"
    cited = {record.source_path for record in load_provisions(report.provisions_path)}
    assert {row["source_path"] for row in source_coverage["sources"]} | {
        prefix + "rates.csv"
    } == cited


def test_the_document_rows_heading_counts_as_extracted_text(tmp_path: Path) -> None:
    # Each source's document row carries the manifest title. "Eligibility chapter
    # summary" repeats two words the blocks already keep and adds "summary", which the
    # page prints only in its lost div: one more word is kept, inside the same run.
    _store, report = _write_scope(tmp_path)
    assert report.source_coverage is not None
    page = report.source_coverage.sources[0].figures
    blocks_only = _measure(PAGE, "html")[2]

    assert page.region_words == blocks_only.region_words == 17
    assert (blocks_only.kept_words, page.kept_words) == (8, 9)
    (run,) = page.longest_missing_runs
    assert (run.offset, run.words) == (6, 8)
    assert run.text == "Bare summary text that the default text tags skip."


def test_a_scope_with_source_coverage_passes_release_validation(tmp_path: Path) -> None:
    store, _report = _write_scope(tmp_path)
    release = ReleaseManifest(
        name="test-release",
        scopes=(ReleaseScope(jurisdiction="us-xx", document_class="policy", version="2026-10-13"),),
    )
    validation = validate_release(store.root, release)

    assert [issue for issue in validation.issues if "coverage" in issue.code] == []
    assert validation.error_count == 0, [issue.to_mapping() for issue in validation.issues]


def test_extraction_is_deterministic(tmp_path: Path) -> None:
    _store, first = _write_scope(tmp_path / "a")
    _store, second = _write_scope(tmp_path / "b")
    assert first.coverage_path.read_bytes() == second.coverage_path.read_bytes()


# --------------------------------------------------------------------------- differential


def _plain_words(text: str) -> list[str]:
    """Words by a character loop that shares nothing with ``source_coverage.words``."""
    text = unicodedata.normalize("NFKC", text)
    for invisible in (0x00AD, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF):
        text = text.replace(chr(invisible), "")
    text = re.sub(r"(?<=[^\W\d_])[-\u2010\u2011]\s+(?=[^\W\d_])", "", text)
    found: list[str] = []
    current = ""
    for char in text:
        if char.isalnum():
            current += char
        elif current:
            found.append(current.casefold())
            current = ""
    if current:
        found.append(current.casefold())
    return found


def _independent_html_region(raw: bytes, *, stop: str | None = None) -> tuple[list[str], list[str]]:
    """The default region of a page, read with lxml alone: (region words, dropped words).

    The region is ``main`` without the default drop selectors' elements, cut at the
    paragraph that starts with ``stop``; the dropped words are those elements' text
    where they sat inside ``main``.
    """
    document = lxml.html.document_fromstring(raw)
    for element in document.xpath("//script|//style|//noscript|//comment()"):
        element.drop_tree()
    main = document.xpath("//main")[0]
    dropped: list[str] = []
    for element in document.xpath(
        "//svg|//button|//input|//nav|//select|//header|//footer|//textarea|//aside"
        "|//*[contains(concat(' ', normalize-space(@class), ' '), ' breadcrumb ')]"
    ):
        if any(ancestor is main for ancestor in element.iterancestors()):
            dropped.extend(_plain_words(" ".join(element.itertext())))
        element.drop_tree()
    pieces: list[str] = []
    for element in main.iter():
        if stop and element.tag == "p" and (element.text or "").startswith(stop):
            break
        if element.text:
            pieces.append(element.text)
        if element.tail and element is not main:
            pieces.append(element.tail)
    return _plain_words(" ".join(pieces)), dropped


def _independent_pdf_lines(raw: bytes) -> list[str]:
    with fitz.open(stream=raw, filetype="pdf") as document:
        return [
            line.strip()
            for page in document
            for line in page.get_text().splitlines()
            if line.strip()
        ]


def _independent_docx_paragraphs(raw: bytes) -> list[str]:
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    return [
        "".join(node.text or "" for node in paragraph.iter(f"{{{_W}}}t"))
        for paragraph in root.iter(f"{{{_W}}}p")
    ]


def _kept(region: list[str], rows: list[str]) -> int:
    available = Counter()
    for text in rows:
        available.update(_plain_words(text))
    return sum(min(count, available[word]) for word, count in Counter(region).items())


def test_recorded_figures_equal_an_independent_recomputation(tmp_path: Path) -> None:
    """Re-extract the fixture scope, then recount every figure from the written rows
    and the retained bytes with lxml, PyMuPDF and ElementTree directly."""
    store, report = _write_scope(tmp_path)
    recorded = {
        Path(row["source_path"]).name: row
        for row in json.loads(report.coverage_path.read_text())["source_coverage"]["sources"]
    }
    rows: dict[str, list[str]] = {}
    for line in report.provisions_path.read_text().splitlines():
        record = json.loads(line)
        texts = rows.setdefault(Path(record["source_path"]).name, [])
        texts.extend(text for text in (record.get("heading"), record.get("body")) if text)
    retained = {path.name: path.read_bytes() for path in report.source_paths}

    expected: dict[str, tuple[list[str], int]] = {}
    region, dropped = _independent_html_region(retained["page.html"])
    expected["page.html"] = (region, len(dropped))
    region, dropped = _independent_html_region(retained["labeled.html"], stop="History:")
    expected["labeled.html"] = (region, len(dropped))

    # The manual: lines after "CHAPTER ONE", without the running headers and the
    # revision lines, and without a section heading restated at a page top.
    lines = _independent_pdf_lines(retained["manual.pdf"])
    lines = lines[lines.index("CHAPTER ONE") + 1 :]
    kept_lines: list[str] = []
    dropped_lines: list[str] = []
    seen_headings: set[str] = set()
    for line in lines:
        restated = re.fullmatch(r"\d{3} [A-Z]+", line) is not None and line in seen_headings
        if line.startswith("Manual page") or line.startswith("Rev.") or restated:
            dropped_lines.append(line)
            continue
        if re.fullmatch(r"\d{3} [A-Z]+", line):
            seen_headings.add(line)
        kept_lines.append(line)
    expected["manual.pdf"] = (
        _plain_words("\n".join(kept_lines)),
        len(_plain_words("\n".join(dropped_lines))),
    )
    expected["pages.pdf"] = (
        _plain_words("\n".join(_independent_pdf_lines(retained["pages.pdf"]))),
        0,
    )

    paragraphs = _independent_docx_paragraphs(retained["chapter.docx"])
    paragraphs = paragraphs[
        paragraphs.index("PART ONE") + 1 : paragraphs.index("REGULATORY AUTHORITY")
    ]
    expected["chapter.docx"] = (
        _plain_words("\n".join(text for text in paragraphs if text != "Page 12")),
        len(_plain_words("Page 12")),
    )

    assert set(recorded) == set(expected)
    for name, (region_words, dropped_words) in expected.items():
        row = recorded[name]
        assert row["region_words"] == len(region_words), name
        assert row["kept_words"] == _kept(region_words, rows[name]), name
        assert row["deliberately_dropped_words"] == dropped_words, name
        missing = len(region_words) - row["kept_words"]
        assert sum(run["words"] for run in row["longest_missing_runs"]) == missing, name


# --------------------------------------------------------------------------- properties

_WORDS = st.sampled_from(
    ["income", "tax", "state", "the", "of", "shall", "rate", "5", "credit", "act"]
)
_SENTENCES = st.lists(_WORDS, min_size=1, max_size=8).map(" ".join)
# A page as a list of parts: a kind and its text. "p", "li" and "h2" are text tags the
# default walk reads; "div" text is bare, "aside" and "nav" are dropped on purpose.
_PARTS = st.lists(
    st.tuples(st.sampled_from(["p", "p", "li", "h2", "div", "aside", "nav"]), _SENTENCES),
    max_size=10,
)


def _page(parts: list[tuple[str, str]]) -> bytes:
    body = "".join(f"<{tag}>{text}</{tag}>" for tag, text in parts)
    return f"<html><body><main>{body}</main></body></html>".encode()


@given(_PARTS)
@settings(max_examples=150, deadline=None)
def test_html_figures_are_bounded_and_match_the_parts(parts: list[tuple[str, str]]) -> None:
    blocks, region, figures = _measure(_page(parts), "html")

    read = [text for tag, text in parts if tag not in {"aside", "nav"}]
    assert region.kind == "html_main_content"
    assert figures.region_words == sum(_count(text) for text in read)
    assert figures.deliberately_dropped_words == sum(
        _count(text) for tag, text in parts if tag in {"aside", "nav"}
    )
    assert 0 <= figures.kept_words <= figures.region_words
    assert 0.0 <= figures.coverage <= 1.0
    assert figures.kept_words <= sum(_count(text) for text in row_texts(blocks))


@given(st.lists(st.tuples(st.sampled_from(["p", "li", "aside", "nav"]), _SENTENCES), max_size=10))
@settings(max_examples=150, deadline=None)
def test_html_coverage_is_one_when_every_region_text_is_in_a_text_tag(
    parts: list[tuple[str, str]],
) -> None:
    _blocks, _region, figures = _measure(_page(parts), "html")
    assert figures.kept_words == figures.region_words
    assert figures.coverage == 1.0
    assert figures.longest_missing_runs == ()


@given(_PARTS, st.data())
@settings(max_examples=150, deadline=None)
def test_removing_a_row_never_raises_a_sources_coverage(
    parts: list[tuple[str, str]], data: st.DataObject
) -> None:
    blocks, region, figures = _measure(_page(parts), "html")
    keep = data.draw(st.lists(st.booleans(), min_size=len(blocks), max_size=len(blocks)))
    fewer = region.measure(
        row_texts(block for block, kept in zip(blocks, keep, strict=True) if kept)
    )

    assert fewer.region_words == figures.region_words
    assert fewer.kept_words <= figures.kept_words
    assert fewer.coverage <= figures.coverage


@given(_PARTS)
@settings(max_examples=100, deadline=None)
def test_recording_a_region_never_changes_the_blocks(parts: list[tuple[str, str]]) -> None:
    page = _page(parts)
    plain = documents._extract_blocks(page, "html", source_url="u", title="T", extraction=None)
    measured = documents._extract_blocks(
        page, "html", source_url="u", title="T", extraction=None, region=SourceRegion()
    )
    assert measured == plain
    assert _measure(page, "html")[2] == _measure(page, "html")[2]


@given(_PARTS)
@settings(max_examples=100, deadline=None)
def test_the_region_text_is_what_get_text_gives_the_content_root(
    parts: list[tuple[str, str]],
) -> None:
    page = _page(parts)
    _blocks, region, _figures = _measure(page, "html")
    soup = BeautifulSoup(page, "lxml")
    for node in soup.select("aside, nav"):
        node.decompose()
    assert soup.main is not None
    assert " ".join(region.texts) == soup.main.get_text(" ", strip=True)


@pytest.mark.parametrize(
    ("content", "source_format", "extraction"),
    [
        (PAGE, "html", None),
        (LABELED_PAGE, "html", LABELED_EXTRACTION),
        (_pdf(LABELED_PDF_PAGES), "pdf", LABELED_PDF_EXTRACTION),
        (_pdf(LABELED_PDF_PAGES), "pdf", None),
        (_pdf(LABELED_PDF_PAGES), "pdf", {"segmentation": "single_block"}),
        (DOCX_LABELED, "docx", DOCX_LABELED_EXTRACTION),
        (DOCX_LABELED, "docx", None),
    ],
)
def test_every_path_extracts_the_same_blocks_with_and_without_a_region(
    content: bytes, source_format: str, extraction: dict[str, Any] | None
) -> None:
    plain = documents._extract_blocks(
        content, source_format, source_url="u", title="T", extraction=extraction
    )
    blocks, region, figures = _measure(content, source_format, extraction)

    assert [(b.kind, b.ordinal, b.heading, b.body) for b in blocks] == [
        (b.kind, b.ordinal, b.heading, b.body) for b in plain
    ]
    assert region.measured
    assert 0 <= figures.kept_words <= figures.region_words
    # Words dropped after they were read left the region; nothing else did.
    read = len(words("\n".join(region.texts)))
    assert figures.region_words <= read
    assert read - figures.region_words <= figures.deliberately_dropped_words
