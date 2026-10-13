"""Zero-width glyphs in the layered PDF path (follow-up to axiom-corpus#741).

PyMuPDF's rawdict leaves out glyphs its plain-text printer prints: the last span
of a line when that span's box has no area (a zero-advance period in its own
font size) and a line whose box has no area (a line holding only such a
period). ``_pdf_page_character_blocks`` reads the text page with the printer's
test and adds them back. The generated pages below draw Helvetica with chosen
characters given zero advance in the font's ``/Widths``, which makes both kinds.

Invariants, as property tests over generated pages (Hypothesis):

1. Printer parity: the blocks' characters, line by line with the printer's
   newline rule, are exactly ``page.get_text("text")``.
2. rawdict identity: where nothing is added, the blocks are rawdict's blocks,
   sorted or not (a differential test against ``get_text("rawdict")``).
3. Additions only: rawdict's characters appear in the blocks in rawdict's order
   with rawdict's values; every added character has a box with no area.
4. ``sort_blocks`` and ``amendment_markup`` extract every generated page, the
   first holding the default page characters and the second its text.
5. The rectangle helpers agree with MuPDF's own functions on every input
   (a differential test against ``fitz.mupdf``).
"""

from __future__ import annotations

import math
import warnings
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import (
    _PDF_EMPTY_RECT,
    _PDF_INFINITE_RECT,
    PdfAmendmentMarkupWarning,
    _pdf_intersect_rect,
    _pdf_page_character_blocks,
    _pdf_rect_is_empty,
    _pdf_rect_is_valid,
    _pdf_rects_overlap,
    _pdf_union_rect,
    _strip_amendment_markup,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = REPO_ROOT / "data" / "corpus" / "sources"
MO_1040ES_PDF = (
    SOURCES
    / "us-mo/statute/2026-07-16-pit-central-us-mo-143/missouri-department-of-revenue"
    / "2026-form-mo-1040es.pdf"
)

PAGE_HEIGHT = 792.0
HELVETICA = fitz.Font("helv")
FLAGS = fitz.TEXTFLAGS_TEXT

Run = tuple[str, float]
Line = tuple[float, float, list[Run]]


def _zero_width_pdf(
    lines: list[Line],
    *,
    zero_width: str = ".",
    rules: tuple[tuple[float, float, float, float], ...] = (),
) -> bytes:
    """A one-page PDF in Helvetica whose ``zero_width`` characters advance by 0.

    Each line is ``(x, baseline, runs)`` in page coordinates (y down) and each
    run ``(text, font size)``, drawn one after another from ``x``. Each rule is a
    filled bar ``(x0, x1, y, thickness)``.
    """
    widths = " ".join(
        "0" if chr(code) in zero_width else str(round(HELVETICA.glyph_advance(code) * 1000))
        for code in range(32, 127)
    )
    document = fitz.open()
    page = document.new_page(width=612, height=PAGE_HEIGHT)
    font = document.get_new_xref()
    document.update_object(
        font,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding "
        f"/FirstChar 32 /LastChar 126 /Widths [{widths}] >>",
    )
    operators = []
    for x, baseline, runs in lines:
        operators.append(f"BT 1 0 0 1 {x} {PAGE_HEIGHT - baseline} Tm")
        for text, size in runs:
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            operators.append(f"/F1 {size} Tf ({escaped}) Tj")
        operators.append("ET")
    for x0, x1, y, thickness in rules:
        operators.append(
            f"0 0 0 rg {x0} {PAGE_HEIGHT - y - thickness / 2} {x1 - x0} {thickness} re f"
        )
    contents = document.get_new_xref()
    document.update_object(contents, "<< >>")
    document.update_stream(contents, "\n".join(operators).encode())
    document.xref_set_key(page.xref, "Resources", f"<< /Font << /F1 {font} 0 R >> >>")
    document.xref_set_key(page.xref, "Contents", f"{contents} 0 R")
    content = document.tobytes()
    document.close()
    return content


def _characters(
    blocks: list[dict[str, Any]],
) -> list[tuple[str, tuple[float, ...], tuple[float, ...]]]:
    return [
        (char["c"], tuple(char["origin"]), tuple(char["bbox"]))
        for block in blocks
        for line in block["lines"]
        for span in line["spans"]
        for char in span["chars"]
    ]


def _printed_text(blocks: list[dict[str, Any]]) -> str:
    """The blocks' characters with the plain-text printer's newline rule."""
    out: list[str] = []
    for block in blocks:
        for line in block["lines"]:
            last = ""
            for span in line["spans"]:
                for char in span["chars"]:
                    out.append(char["c"])
                    last = char["c"]
            if last not in ("", "\n", "\x00"):
                out.append("\n")
    return "".join(out)


def _is_subsequence(part: list[Any], whole: list[Any]) -> bool:
    items = iter(whole)
    return all(any(item == wanted for item in items) for wanted in part)


def _read(content: bytes, *, sort: bool) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        blocks = _pdf_page_character_blocks(page, flags=FLAGS, sort=sort, page_number=1)
        raw = page.get_text("rawdict", flags=FLAGS, sort=sort)
        text = page.get_text("text", flags=FLAGS)
    return blocks, raw, text


def _pages(content: bytes, extraction: dict[str, Any]) -> list[Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PdfAmendmentMarkupWarning)
        return list(documents_module._extract_pdf_blocks(content, extraction=extraction))


# 1. The glyphs rawdict leaves out -------------------------------------------------


def test_rawdict_leaves_out_a_zero_width_last_span_and_line_that_the_printer_prints() -> None:
    content = _zero_width_pdf(
        [
            (72, 100, [("Total $", 12), (".", 8)]),
            (72, 200, [(".", 12)]),
            (72, 300, [("a.b", 12)]),
        ]
    )
    blocks, raw, text = _read(content, sort=False)

    assert text == "Total $.\n.\na.b\n"
    assert _printed_text(raw["blocks"]) == "Total $\na.b\n"
    assert _printed_text(blocks) == text
    # The period inside "a.b" is zero-width too, but rawdict keeps it.
    added = [char for char in _characters(blocks) if char not in _characters(raw["blocks"])]
    assert [char[0] for char in added] == [".", "."]
    assert all(_pdf_rect_is_empty(char[2]) for char in added)


def test_a_left_out_last_span_keeps_its_font_size() -> None:
    content = _zero_width_pdf([(72, 100, [("Total $", 12), (".", 8)])])
    blocks, _raw, _text = _read(content, sort=False)

    (line,) = blocks[0]["lines"]
    assert [
        (span["size"], "".join(char["c"] for char in span["chars"])) for span in line["spans"]
    ] == [
        (12.0, "Total $"),
        (8.0, "."),
    ]


def test_a_left_out_line_takes_its_place_among_the_block_lines() -> None:
    # Lines 14 points apart form one block; the middle line is a lone period.
    content = _zero_width_pdf(
        [(72, 100, [("first", 12)]), (72, 114, [(".", 12)]), (72, 128, [("third", 12)])]
    )
    blocks, raw, text = _read(content, sort=False)

    assert len(blocks) == len(raw["blocks"]) == 1
    assert [len(line["spans"]) for line in blocks[0]["lines"]] == [1, 1, 1]
    assert _printed_text(blocks) == text == "first\n.\nthird\n"


def test_the_layered_keys_extract_the_missouri_1040es_with_its_zero_width_periods() -> None:
    content = MO_1040ES_PDF.read_bytes()
    plain = _pages(content, {})

    marked = _pages(content, {"amendment_markup": True})
    sorted_pages = _pages(content, {"sort_blocks": True})

    assert [_strip_amendment_markup(block.body) for block in marked] == [
        block.body for block in plain
    ]
    assert "$." in _strip_amendment_markup(marked[0].body)
    for sorted_block, plain_block in zip(sorted_pages, plain, strict=True):
        assert Counter(sorted_block.body.replace(" ", "").replace("\n", "")) == Counter(
            plain_block.body.replace(" ", "").replace("\n", "")
        )


def test_a_struck_zero_width_period_is_marked_with_its_line() -> None:
    width = fitz.get_text_length("Old rule", fontname="helv", fontsize=12)
    content = _zero_width_pdf(
        [(72, 100, [("Old rule", 12), (".", 8)])],
        rules=((72, 72 + width, 100 - 0.23 * 12, 0.6),),
    )

    (page,) = _pages(content, {"amendment_markup": True})

    assert page.body == "[-Old rule.-]"


# 2. Mismatches stop extraction ---------------------------------------------------


class _AlteredTextPage:
    def __init__(self, textpage: Any, alter: Callable[[dict[str, Any]], None]) -> None:
        self._textpage = textpage
        self.this = textpage.this
        self._alter = alter

    def extractRAWDICT(self) -> dict[str, Any]:  # noqa: N802 - PyMuPDF's name
        raw = self._textpage.extractRAWDICT()
        self._alter(raw)
        return raw


class _AlteredPage:
    def __init__(self, page: Any, alter: Callable[[dict[str, Any]], None]) -> None:
        self._page = page
        self._alter = alter

    def get_textpage(self, *, flags: int) -> _AlteredTextPage:
        return _AlteredTextPage(self._page.get_textpage(flags=flags), self._alter)


def _first_chars(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw["blocks"][0]["lines"][0]["spans"][0]["chars"]


@pytest.mark.parametrize(
    ("alter", "message"),
    [
        (
            lambda raw: _first_chars(raw)[0].update(c="X"),
            "rawdict holds a character the plain-text printer does not print",
        ),
        (
            lambda raw: _first_chars(raw)[0].update(bbox=(0.0, 0.0, 1.0, 1.0)),
            "rawdict holds a character the plain-text printer does not print",
        ),
        (
            lambda raw: _first_chars(raw).pop(1),
            "rawdict holds a character the plain-text printer does not print",
        ),
        (
            lambda raw: _first_chars(raw).pop(),
            "rawdict leaves out characters that are not a last empty span",
        ),
        (
            lambda raw: raw["blocks"].pop(0),
            "rawdict holds a character the plain-text printer does not print",
        ),
        (lambda raw: raw["blocks"].pop(), "a text block is missing from rawdict"),
        (
            lambda raw: raw["blocks"].append(dict(raw["blocks"][0])),
            "rawdict holds a block the text page does not",
        ),
        (
            lambda raw: raw["blocks"][0]["lines"].append(raw["blocks"][0]["lines"][0]),
            "rawdict holds a line the text page does not",
        ),
        (lambda raw: raw["blocks"][0]["lines"].pop(0), "a line is missing from rawdict"),
    ],
)
def test_a_rawdict_that_does_not_line_up_with_the_text_page_stops_extraction(
    alter: Callable[[dict[str, Any]], None], message: str
) -> None:
    content = _zero_width_pdf([(72, 100, [("first", 12)]), (72, 300, [("second", 12)])])
    with fitz.open(stream=content, filetype="pdf") as document:
        page = _AlteredPage(document[0], alter)
        with pytest.raises(RuntimeError, match=rf"PDF page 7: .*\({message}\)"):
            _pdf_page_character_blocks(page, flags=FLAGS, sort=False, page_number=7)


# 3. Properties over generated pages --------------------------------------------

# Baselines near and past the top and bottom edges, x near and past the left and
# right edges, and line spacings that join lines into one block or not.
_runs = st.lists(
    st.tuples(st.text(alphabet="ab. ", min_size=1, max_size=4), st.sampled_from([8.0, 12.0])),
    min_size=1,
    max_size=4,
)
_lines = st.lists(
    st.tuples(
        st.sampled_from([-30.0, 72.0, 300.0, 590.0]),
        st.sampled_from([4.0, 100.0, 114.0, 128.0, 400.0, 790.0, 797.0]),
        _runs,
    ),
    min_size=1,
    max_size=6,
)
_zero_width = st.sampled_from([".", ". ", ".a", ""])


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(lines=_lines, zero_width=_zero_width)
def test_property_blocks_hold_exactly_what_the_printer_prints(
    lines: list[Line], zero_width: str
) -> None:
    """Invariants 1-3 on generated pages, sorted and unsorted."""
    content = _zero_width_pdf(lines, zero_width=zero_width)
    for sort in (False, True):
        blocks, raw, text = _read(content, sort=sort)
        characters, raw_characters = _characters(blocks), _characters(raw["blocks"])
        if not sort:
            assert _printed_text(blocks) == text
            assert _is_subsequence(raw_characters, characters)
            added = Counter(characters) - Counter(raw_characters)
            assert all(_pdf_rect_is_empty(bbox) for _c, _origin, bbox in added)
        else:
            assert Counter(_printed_text(blocks)) == Counter(text)
        if len(characters) == len(raw_characters):
            assert blocks == raw["blocks"]
        if not sort:
            event("rawdict left glyphs out" if added else "rawdict read every glyph")


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(lines=_lines, zero_width=_zero_width)
def test_property_the_layered_keys_extract_every_generated_page(
    lines: list[Line], zero_width: str
) -> None:
    """Invariant 4: no generated page stops the layered keys."""
    content = _zero_width_pdf(lines, zero_width=zero_width)
    plain = [block.body for block in _pages(content, {})]

    assert [block.body for block in _pages(content, {"amendment_markup": True})] == plain
    sorted_bodies = [block.body for block in _pages(content, {"sort_blocks": True})]
    assert [Counter(body.replace(" ", "").replace("\n", "")) for body in sorted_bodies] == [
        Counter(body.replace(" ", "").replace("\n", "")) for body in plain
    ]


def test_every_cited_page_without_left_out_glyphs_gets_rawdicts_blocks() -> None:
    """Invariant 2 on retained PDFs: a page rawdict reads whole is unchanged."""
    paths = [
        MO_1040ES_PDF,
        SOURCES
        / "us-az/manual/2026-06-25-az-ccap/official-documents/az-des-ccap-reimbursement-rates.pdf",
        SOURCES
        / "us-wa/guidance/2026-09-14-msp-income-standards/official-documents"
        / "us-wa-hca-income-and-resource-standards-2026-07-01.pdf",
    ]
    unchanged = 0
    for path in paths:
        with fitz.open(path) as document:
            for page in document:
                for sort in (False, True):
                    blocks = _pdf_page_character_blocks(
                        page, flags=FLAGS, sort=sort, page_number=page.number + 1
                    )
                    raw = page.get_text("rawdict", flags=FLAGS, sort=sort)
                    if not sort:
                        assert _printed_text(blocks) == page.get_text("text", flags=FLAGS)
                    if len(_characters(blocks)) == len(_characters(raw["blocks"])):
                        assert blocks == raw["blocks"]
                        unchanged += 1
    assert unchanged


# 4. The rectangle helpers against MuPDF ------------------------------------------

_coordinates = st.one_of(
    st.floats(width=32),
    st.sampled_from(
        [0.0, 1.0, float(fitz.FZ_MIN_INF_RECT), float(fitz.FZ_MAX_INF_RECT), math.inf, -math.inf]
    ),
)
_rects = st.one_of(
    st.tuples(_coordinates, _coordinates, _coordinates, _coordinates),
    st.sampled_from([_PDF_EMPTY_RECT, _PDF_INFINITE_RECT, (1.0, 1.0, 1.0, 2.0)]),
)


def _mupdf(rect: tuple[float, float, float, float]) -> Any:
    return fitz.mupdf.FzRect(*rect)


def _same(a: Any, b: tuple[float, float, float, float]) -> bool:
    values = (a.x0, a.y0, a.x1, a.y1)
    return all(x == y or (math.isnan(x) and math.isnan(y)) for x, y in zip(values, b, strict=True))


@settings(max_examples=2000, deadline=None)
@given(a=_rects, b=_rects)
def test_property_rect_helpers_agree_with_mupdf(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> None:
    """Invariant 5: each helper is the MuPDF function it names."""
    assert _same(fitz.mupdf.fz_union_rect(_mupdf(a), _mupdf(b)), _pdf_union_rect(a, b))
    assert _same(fitz.mupdf.fz_intersect_rect(_mupdf(a), _mupdf(b)), _pdf_intersect_rect(a, b))
    assert bool(fitz.mupdf.fz_is_empty_rect(_mupdf(a))) == _pdf_rect_is_empty(a)
    assert bool(fitz.mupdf.fz_is_valid_rect(_mupdf(a))) == _pdf_rect_is_valid(a)
    assert bool(fitz.JM_rects_overlap(_mupdf(a), _mupdf(b))) == _pdf_rects_overlap(a, b)
