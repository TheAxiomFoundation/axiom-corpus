"""Property tests for the hollow-root extractor fixes.

Invariants:

* ``start_after_pattern``: when the marker occurs, extraction equals extracting the lines
  after its first occurrence with no marker; when it never occurs, extraction raises.
* ``_pdf_page_needs_ocr``: an empty text layer always needs OCR; a layer with at least
  ``_OCR_OVERLAY_MAX_WORDS`` words with a letter never does; otherwise it needs OCR exactly
  when one image covers at least ``_OCR_PAGE_IMAGE_COVERAGE`` of the page, so the answer
  is monotone (more words never adds OCR, more coverage never removes it).
* ``nycrr._document_body``: a page with ``.co_body`` keeps exactly that text whatever its
  annotations say; a page without it reads ``.co_refsAnnos``; neither gives ``None``.
"""

from __future__ import annotations

import html
import io
import zipfile

import fitz
import pytest
from bs4 import BeautifulSoup
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.documents import (
    _OCR_OVERLAY_MAX_WORDS,
    _OCR_PAGE_IMAGE_COVERAGE,
    _extract_docx_blocks,
    _pdf_page_image_coverage,
    _pdf_page_needs_ocr,
)
from axiom_corpus.corpus.nycrr import _document_body

MARKER = "BEGIN RULE TEXT"
LINES = st.lists(
    st.sampled_from(
        [
            "701.010 Alpha section",
            "701.020 Beta section",
            "Body text one.",
            "Another body line.",
            MARKER,
        ]
    ),
    max_size=12,
)
LABELED = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>701\.\d{3}):?\s+(?P<heading>.+)$",
}


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{html.escape(text)}</w:t></w:r></w:p>" for text in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def _shape(blocks) -> list[tuple[str, str, str]]:
    return [(block.metadata["section_label"], block.heading, block.body) for block in blocks]


@settings(max_examples=150, deadline=None)
@given(LINES)
def test_start_marker_extracts_exactly_the_text_after_it_or_fails(lines):
    extraction = {**LABELED, "start_after_pattern": f"^{MARKER}$"}
    if MARKER not in lines:
        try:
            _extract_docx_blocks(_docx(lines), extraction=extraction)
        except ValueError as error:
            assert "start_after_pattern did not match" in str(error)
        else:
            raise AssertionError("an unmatched start marker must fail")
        return
    after = lines[lines.index(MARKER) + 1 :]
    with_marker = _extract_docx_blocks(_docx(lines), extraction=extraction)
    without_marker = _extract_docx_blocks(_docx(after), extraction=dict(LABELED))
    assert _shape(with_marker) == _shape(without_marker)


class _Page:
    """The slice of a PyMuPDF page that ``_pdf_page_needs_ocr`` reads."""

    def __init__(self, coverage: float | None):
        self.cropbox = fitz.Rect(0, 0, 600, 800)
        self._rects = []
        if coverage is not None:
            self._rects = [fitz.Rect(0, 0, 600, 800 * coverage)]

    def get_images(self, full: bool = False):
        del full
        # (xref, smask, width, height): a 600 x 800 pt page at 720 dpi.
        return [(1, 0, 6000, 8000)] if self._rects else []

    def get_image_rects(self, xref):
        del xref
        return self._rects


def _text(letter_words: int, numeric_tokens: int) -> str:
    return " ".join(["word"] * letter_words + ["9/4/13"] * numeric_tokens)


# Whole grid rows, so the fake page's coverage is exact under the coverage grid.
COVERAGE = st.one_of(st.none(), st.integers(1, 50).map(lambda rows: rows / 50))


@given(st.integers(0, 80), st.integers(0, 5), COVERAGE)
def test_ocr_rule_matches_its_definition(letter_words, numeric_tokens, coverage):
    text = _text(letter_words, numeric_tokens)
    needs = _pdf_page_needs_ocr(_Page(coverage), text)
    if not text.strip():
        assert needs
    elif letter_words >= _OCR_OVERLAY_MAX_WORDS:
        assert not needs
    else:
        covered = coverage is not None and coverage >= _OCR_PAGE_IMAGE_COVERAGE - 1e-9
        assert needs == covered


@given(st.integers(1, 80), st.integers(0, 80), st.integers(1, 50), st.integers(1, 50))
def test_ocr_rule_is_monotone(words_a, extra_words, rows_a, rows_b):
    low, high = sorted((rows_a / 50, rows_b / 50))
    fewer, more = _text(words_a, 0), _text(words_a + extra_words, 0)
    # More words never turns OCR on; more coverage never turns it off.
    assert _pdf_page_needs_ocr(_Page(low), more) <= _pdf_page_needs_ocr(_Page(low), fewer)
    assert _pdf_page_needs_ocr(_Page(low), fewer) <= _pdf_page_needs_ocr(_Page(high), fewer)


def _scan_png() -> bytes:
    # Enough pixels that any rectangle the test places stays a scan (>= 100 dpi).
    pixmap = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 1275, 1650), False)
    pixmap.clear_with(200)
    return pixmap.tobytes("png")


SCAN_PNG = _scan_png()


@settings(max_examples=80, deadline=None)
@given(
    st.floats(-300, 550),
    st.floats(-300, 730),
    st.floats(20, 900),
    st.floats(20, 1100),
    st.one_of(st.none(), st.tuples(st.floats(0, 150), st.floats(0, 150))),
    st.sampled_from([0, 90, 180, 270]),
)
def test_image_coverage_matches_the_placed_rectangle(x0, y0, width, height, inset, rotation):
    # Differential: the coverage PyMuPDF's frames give must equal the share of the crop box
    # that the rectangle we placed covers, whatever the rotation.
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    placed = fitz.Rect(x0, y0, x0 + width, y0 + height)
    page.insert_image(placed, stream=SCAN_PNG, keep_proportion=False)
    crop = fitz.Rect(0, 0, 612, 792)
    if inset is not None:
        crop = fitz.Rect(inset[0], inset[1], 612 - inset[0], 792 - inset[1])
        page.set_cropbox(crop)
    if rotation:
        page.set_rotation(rotation)
    shown = placed & crop
    expected = 0.0 if shown.is_empty else shown.get_area() / crop.get_area()
    reopened = fitz.open("pdf", document.tobytes())

    assert _pdf_page_image_coverage(reopened[0]) == pytest.approx(expected, abs=1e-6)


SAFE_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" ()§.,"),
    max_size=40,
)


def _westlaw(body: str | None, annotations: str | None) -> str:
    parts = ['<div id="co_document">']
    if body is not None:
        parts.append(
            '<div class="co_contentBlock co_section"><div class="co_contentBlock co_body">'
            f'<div class="co_paragraphText">{html.escape(body)}</div></div></div>'
        )
    if annotations is not None:
        parts.append(
            '<div class="co_contentBlock co_refsAnnos">'
            f'<div class="co_paragraphText">{html.escape(annotations)}</div></div>'
        )
    parts.append("<div>Current through May 15, 2026</div></div>")
    return "<html><body>" + "".join(parts) + "</body></html>"


@given(st.one_of(st.none(), SAFE_TEXT), st.one_of(st.none(), SAFE_TEXT))
def test_document_body_prefers_section_text_then_annotations(body, annotations):
    result = _document_body(BeautifulSoup(_westlaw(body, annotations), "lxml"))

    def clean(value: str | None) -> str | None:
        text = " ".join((value or "").split())
        return text or None

    if body is not None:
        # A page with a .co_body is a section page, even when the body is empty (a repealed
        # section): its annotations are history notes, not the section's text.
        assert result == clean(body)
    elif annotations is not None:
        assert result == clean(annotations)
    else:
        assert result is None
