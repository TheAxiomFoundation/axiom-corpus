"""A drawing that is a glyph is not an amendment rule.

MuPDF draws a Type 3 glyph that it cannot cache by running the glyph's
procedure on the page, and then reports the character as hidden text. PyMuPDF
lists such a glyph among the page's drawings, so ``amendment_markup`` took the
bar of a hyphen for a strike and an underscore for an underline. With PyMuPDF
1.26.7 that marked characters on ten pages of CMS state plan approval packages
set in Type 3 fonts. PyMuPDF 1.28.2 paints those fonts' glyphs as text and
marks none of them; it still draws the glyphs of the font built here.
``_pdf_glyph_drawings`` recognises the glyph drawings and
``_pdf_horizontal_rules`` leaves them out.

Invariants (Hypothesis):

1. Text does not mark itself. A page whose only drawings are its own glyphs
   extracts, with ``amendment_markup``, to its default text with no runs.
2. Real rules mark as before. On a page of drawn Type 3 text with real strike
   and underline rules, each character's state is the one the real rules give
   it, and extraction stops only where a real strike and a real underline meet.
3. Leaving glyph drawings out only removes rules. A page's rules are the rules
   of the same page without its glyph drawings, they are among the rules found
   when no drawing is taken for a glyph, and they are all of those when the
   page has no Type 3 font, in which case the page's text is neither traced nor
   bounded. A page without a rule reads no fonts and no text. A glyph drawing
   is one whose next command, paths without segments aside, is hidden text of
   one span of one character in a font only the page's Type 3 fonts are named,
   and that lies inside that character's bound and is at most two of its font
   sizes wide and high. The drawings and the bbox log are matched by command
   number as PyMuPDF 1.26.7 numbers them, which a model page reproduces.
4. Only a PDF has Type 3 fonts. A page of a file MuPDF opens as something else
   (a Word file saved under a ``.pdf`` name) has no glyph drawings, its fonts
   are never read, and it extracts with ``amendment_markup`` as before.
5. A path without segments changes nothing. Adding such paths anywhere in a
   page's content, or inside a glyph's procedure, leaves its extraction as it
   was, though ``get_drawings`` neither lists nor counts them.
6. Only a Type 3 font's hidden character makes a glyph. A hidden character in
   another font never makes the drawing before it a glyph, however the page's
   Type 3 and other fonts are named (a subset prefix, a name MuPDF cuts short,
   a Type0 font named after its descendant) and wherever the other font sits:
   the page's resources (referenced, inline, under a resource name with a "/" in
   it, or inherited from the page tree), an annotation's appearance stream, a
   tiling pattern, a soft mask's group, or a Type 3 font's glyph procedure. A page
   whose other fonts can't all be read has no glyph drawings.
7. The drawings taken for glyphs are the ones the glyph procedures paint. On a
   page of drawn Type 3 text and real rules, they are exactly the drawings that
   go away when every glyph procedure paints nothing, an oracle that reads no
   bbox log, text trace or font name.

The Type 3 fonts are the ones ``_pdf_type3_font_names`` (the OCR overlay's
helper) names.
"""

from __future__ import annotations

import ast
import re
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import (
    PdfAmendmentMarkupWarning,
    _amendment_markup_runs,
    _normalize_text,
    _strip_amendment_markup,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = REPO_ROOT / "data" / "corpus" / "sources"
D = "deleted"
I = "inserted"  # noqa: E741
SIZE = 12.0
BASELINE = 100.0
LEFT = 72.0
PAGE_HEIGHT = 842.0
# Real rules, in font sizes from the baseline. The glyph bars below sit at
# -0.225 (hyphen) and +0.125 (underscore), inside the same ranges.
REAL_OFFSETS = {D: -0.30, I: 0.17}
# name, advance and procedure of each glyph, in a 1000-unit em: a block for
# "a"; a bar 0.19 to 0.26 em above the baseline for "-" and one 0.10 to 0.15 em
# below it for "_"; nothing for the space; two separately filled bars for "=",
# the lower one filled last.
_GLYPHS = {
    "a": ("a", 600, "100 0 400 500 re f"),
    "-": ("hyphen", 350, "50 190 250 70 re f"),
    "_": ("underscore", 500, "0 -150 500 50 re f"),
    " ": ("space", 300, ""),
    "=": ("equal", 600, "50 330 500 70 re f 50 190 500 70 re f"),
}


def _advance(character: str, size: float) -> float:
    return _GLYPHS[character][1] * size / 1000


def _type3_document(stream: str, *, font_name: str = "/Name /T1 ") -> bytes:
    """A one-page PDF with the content ``stream`` and the Type 3 font ``/T1``.

    Each glyph procedure fills its shape in the page's current colour (``d0``).
    ``font_name`` is the font dictionary's /Name entry; empty leaves it out.
    """
    document = fitz.open()
    page = document.new_page(width=595.0, height=PAGE_HEIGHT)
    procedures = {}
    for name, advance, body in _GLYPHS.values():
        xref = document.get_new_xref()
        document.update_object(xref, "<<>>")
        document.update_stream(xref, f"{advance} 0 d0 {body}".encode(), compress=False)
        procedures[name] = xref
    first_code, last_code = 32, 97
    widths = [0] * (last_code - first_code + 1)
    differences = []
    for character, (name, advance, _body) in sorted(_GLYPHS.items()):
        widths[ord(character) - first_code] = advance
        differences.append(f"{ord(character)} /{name}")
    font = document.get_new_xref()
    document.update_object(
        font,
        f"<< /Type /Font /Subtype /Type3 {font_name}/FontBBox [0 -200 1000 800] "
        "/FontMatrix [0.001 0 0 0.001 0 0] /Resources << >> "
        "/CharProcs << "
        + " ".join(f"/{name} {xref} 0 R" for name, xref in procedures.items())
        + " >> /Encoding << /Type /Encoding /Differences ["
        + " ".join(differences)
        + f"] >> /FirstChar {first_code} /LastChar {last_code} /Widths ["
        + " ".join(map(str, widths))
        + "] >>",
    )
    document.xref_set_key(page.xref, "Resources", f"<< /Font << /T1 {font} 0 R >> >>")
    contents = document.get_new_xref()
    document.update_object(contents, "<<>>")
    document.update_stream(contents, stream.encode(), compress=False)
    document.xref_set_key(page.xref, "Contents", f"{contents} 0 R")
    content = document.tobytes()
    document.close()
    return content


def _line(x0: float, x1: float, offset: float, size: float) -> str:
    """A 0.6 pt line ``offset`` font sizes below the baseline."""
    y = PAGE_HEIGHT - (BASELINE + offset * size)
    return f"0.6 w {x0} {y} m {x1} {y} l S\n"


def _type3_pdf(
    text: str,
    *,
    rules: list[tuple[str, int, int]] | None = None,
    size: float = SIZE,
) -> bytes:
    """One line of ``text`` set in a Type 3 font that MuPDF draws glyph by glyph.

    ``rules`` adds real lines: a strike or an underline from the left edge of
    character ``first`` to the right edge of character ``last``.
    """
    stream = f"BT /T1 {size} Tf {LEFT} {PAGE_HEIGHT - BASELINE} Td ({text}) Tj ET\n"
    lefts = [LEFT]
    for character in text:
        lefts.append(lefts[-1] + _advance(character, size))
    for state, first, last in rules or ():
        stream += _line(lefts[first], lefts[last + 1], REAL_OFFSETS[state], size)
    return _type3_document(stream)


def _marked(content: bytes) -> list[Any]:
    """Extract with ``amendment_markup``; any markup warning is an error."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", PdfAmendmentMarkupWarning)
        return list(
            documents_module._extract_pdf_blocks(content, extraction={"amendment_markup": True})
        )


def _plain(content: bytes) -> list[str]:
    return [block.body for block in documents_module._extract_pdf_blocks(content, extraction={})]


def _states(body: str) -> list[tuple[str, str | None]]:
    return [
        (character, state)
        for run, state in _amendment_markup_runs(body)
        for character in run
        if not character.isspace()
    ]


def _no_glyph_drawings(_page: Any, _paths: list[dict[str, Any]]) -> frozenset[int]:
    return frozenset()


def _glyph_seqnos(page: Any) -> set[int]:
    """The command numbers of the page's drawings that are glyphs."""
    drawings = page.get_drawings()
    return {
        drawings[position]["seqno"]
        for position in documents_module._pdf_glyph_drawings(page, drawings)
    }


# 1. What PyMuPDF reports for drawn Type 3 text ------------------------------------


def test_pymupdf_draws_each_glyph_and_then_reports_its_character_as_hidden_text() -> None:
    # The rule rests on this. If a PyMuPDF release stops drawing this font's
    # glyphs as paths, the tests below no longer exercise the glyph rule.
    with fitz.open(stream=_type3_pdf("a-_ a"), filetype="pdf") as document:
        page = document[0]
        commands = [kind for kind, _bbox in page.get_bboxlog()]
        drawings = page.get_drawings()
        trace = page.get_texttrace()

    # "a", "-", "_": a filled path, then one hidden character. The empty space
    # glyph is painted as text. Then the last "a".
    assert commands == [
        "fill-path",
        "ignore-text",
        "fill-path",
        "ignore-text",
        "fill-path",
        "ignore-text",
        "fill-text",
        "fill-path",
        "ignore-text",
    ]
    assert [path["seqno"] for path in drawings] == [0, 2, 4, 7]
    assert [(span["seqno"], span["type"], span["font"], len(span["chars"])) for span in trace] == [
        (1, 3, "T1", 1),
        (3, 3, "T1", 1),
        (5, 3, "T1", 1),
        (6, 0, "T1", 1),
        (8, 3, "T1", 1),
    ]


def test_the_glyph_drawings_are_found_by_the_hidden_character_that_follows_each() -> None:
    with fitz.open(stream=_type3_pdf("a-_ a"), filetype="pdf") as document:
        page = document[0]
        log = page.get_bboxlog()
        drawings = page.get_drawings()
        glyphs = documents_module._pdf_glyph_drawings(page, drawings)

    assert glyphs == {0, 1, 2, 3}
    # Without empty paths the drawings' numbers are their bbox-log positions.
    assert documents_module._pdf_drawing_commands(log) == {n: n for n in range(len(log))}
    for path in drawings:
        # Each glyph lies inside the bound of the hidden character after it,
        # which MuPDF gives one point more on each side.
        (left, top, right, bottom) = log[path["seqno"] + 1][1]
        rect = path["rect"]
        assert (rect.x0 - left, rect.y0 - top, right - rect.x1, bottom - rect.y1) == pytest.approx(
            (1.0, 1.0, 1.0, 1.0), abs=1e-4
        )
    # The largest, the block of "a", is half a font size high.
    assert max(max(path["rect"].width, path["rect"].height) for path in drawings) == 6.0


# 2. Text does not mark itself ------------------------------------------------------


def test_a_hyphen_and_an_underscore_do_not_mark_themselves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _type3_pdf("aa-aa_a a")

    marked = _marked(content)

    assert [block.body for block in marked] == ["aa-aa_a a"] == _plain(content)
    metadata = marked[0].metadata["amendment_markup"]
    assert (metadata["deleted_runs"], metadata["inserted_runs"]) == (0, 0)

    # Taking the glyph drawings for rules strikes the hyphen with its own bar
    # and underlines the underscore with itself.
    monkeypatch.setattr(documents_module, "_pdf_glyph_drawings", _no_glyph_drawings)
    assert [block.body for block in _marked(content)] == ["aa[---]aa{+_+}a a"]


def test_the_glyphs_of_a_type3_font_without_a_name_do_not_mark_its_text() -> None:
    # MuPDF makes up a name for such a font: "Unnamed-T3" (1.26) or one from
    # its object number (1.28). get_fonts reports an empty base name.
    stream = f"BT /T1 {SIZE} Tf {LEFT} {PAGE_HEIGHT - BASELINE} Td (aa-aa_a a) Tj ET\n"
    content = _type3_document(stream, font_name="")

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        (font,) = page.get_fonts(full=True)
        assert (font[2], font[3]) == ("Type3", "")
        (name,) = {span["font"] for span in page.get_texttrace()}
        assert name in ("Unnamed-T3", f"Type3 ({font[0]} 0 R)")
        # One drawn glyph for each character but the space.
        assert len(_glyph_seqnos(page)) == 8
    assert [block.body for block in _marked(content)] == ["aa-aa_a a"]


def test_a_real_underline_still_marks_drawn_type3_text() -> None:
    content = _type3_pdf("aa-aa_a a", rules=[(I, 0, 4)])

    assert [block.body for block in _marked(content)] == ["{+aa-aa+}_a a"]


def test_a_real_strike_still_marks_drawn_type3_text() -> None:
    content = _type3_pdf("aa-aa_a a", rules=[(D, 5, 8)])

    assert [block.body for block in _marked(content)] == ["aa-aa[-_a a-]"]


def test_an_underlined_hyphen_is_inserted_text(monkeypatch: pytest.MonkeyPatch) -> None:
    content = _type3_pdf("a-a", rules=[(I, 0, 2)])

    assert [block.body for block in _marked(content)] == ["{+a-a+}"]

    # Its own bar made the hyphen struck as well, which stopped the page.
    monkeypatch.setattr(documents_module, "_pdf_glyph_drawings", _no_glyph_drawings)
    with pytest.raises(ValueError, match="'-' is both struck through and underlined"):
        _marked(content)


def test_a_heavy_glyph_bar_draws_no_thick_rule_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    # At 30 pt the hyphen's bar is 2.1 pt thick: too thick to classify, and at a
    # strike position, which warns when the bar is taken for a rule.
    content = _type3_pdf("a-a", size=30.0)

    assert [block.body for block in _marked(content)] == ["a-a"]

    monkeypatch.setattr(documents_module, "_pdf_glyph_drawings", _no_glyph_drawings)
    with pytest.raises(PdfAmendmentMarkupWarning, match="thicker than 1.5 pt"):
        _marked(content)


def test_a_glyph_drawn_as_two_paths_is_recognised_only_by_its_last_one() -> None:
    # "=" fills its upper bar, then its lower one. Only the lower bar is the
    # drawing right before the hidden character, so the upper one, at a strike
    # offset, still marks it.
    with fitz.open(stream=_type3_pdf("a=a"), filetype="pdf") as document:
        page = document[0]
        assert [path["seqno"] for path in page.get_drawings()] == [0, 2, 3, 5]
        assert _glyph_seqnos(page) == {0, 3, 5}

    assert [block.body for block in _marked(_type3_pdf("a=a"))] == ["a[-=-]a"]


def test_hidden_text_in_an_ordinary_font_keeps_the_rule_drawn_before_it() -> None:
    # A rule followed by one hidden character is a glyph only in a Type 3 font.
    # An OCR layer's hidden text over a table rule is classified as before.
    document = fitz.open()
    page = document.new_page()
    page.draw_line((70, BASELINE + 2), (90, BASELINE + 2), width=0.6)
    page.insert_text((72, BASELINE), "I", fontname="helv", fontsize=SIZE, render_mode=3)
    content = document.tobytes()
    document.close()

    with fitz.open(stream=content, filetype="pdf") as reopened:
        assert [kind for kind, _bbox in reopened[0].get_bboxlog()] == ["stroke-path", "ignore-text"]
        assert _glyph_seqnos(reopened[0]) == set()
    assert [block.body for block in _marked(content)] == ["{+I+}"]


@pytest.mark.parametrize(
    ("state", "x0", "x1", "expected"),
    [
        # Underlines 120 pt and 7.2 pt long (the width of the "a") lie below the
        # character's bound, so neither is taken for its glyph.
        (I, LEFT, LEFT + 120.0, "{+a+}"),
        (I, LEFT, LEFT + 7.2, "{+a+}"),
        # A strike 5 pt long lies inside the bound and is glyph-sized: it is taken
        # for a glyph. One 18 pt long runs out of the bound and marks.
        (D, LEFT + 1.0, LEFT + 6.0, "a"),
        (D, LEFT, LEFT + 18.0, "[-a-]"),
    ],
)
def test_a_rule_before_hidden_type3_text_is_a_glyph_only_inside_its_bound(
    state: str, x0: float, x1: float, expected: str
) -> None:
    # Text rendering mode 3 hides the "a" in the PDF itself, so MuPDF does not
    # draw its glyph, and the rule drawn before it is the previous command.
    stream = _line(x0, x1, REAL_OFFSETS[state], SIZE) + (
        f"BT /T1 {SIZE} Tf 3 Tr {LEFT} {PAGE_HEIGHT - BASELINE} Td (a) Tj ET\n"
    )
    content = _type3_document(stream)

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        log = page.get_bboxlog()
        assert [kind for kind, _bbox in log] == ["stroke-path", "ignore-text"]
        # The character's bound is its glyph's box and a point more each way.
        assert log[1][1] == pytest.approx((LEFT + 0.2, 93.0, LEFT + 7.0, 101.0), abs=1e-4)
        assert _glyph_seqnos(page) == ({0} if expected == "a" else set())
    assert [block.body for block in _marked(content)] == [expected]


_WORDS = st.lists(st.text(alphabet="a-_", min_size=1, max_size=5), min_size=1, max_size=4)
_SIZES = st.sampled_from([8.0, 12.0, 18.0])


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(words=_WORDS, size=_SIZES)
def test_property_drawn_type3_text_does_not_mark_itself(words: list[str], size: float) -> None:
    text = " ".join(words)
    content = _type3_pdf(text, size=size)

    marked = _marked(content)

    assert [block.body for block in marked] == [text] == _plain(content)
    metadata = marked[0].metadata["amendment_markup"]
    assert (metadata["deleted_runs"], metadata["inserted_runs"]) == (0, 0)


@st.composite
def _text_and_real_rules(draw: st.DrawFn) -> tuple[str, list[tuple[str, int, int]]]:
    text = " ".join(draw(_WORDS))
    visible = [index for index, character in enumerate(text) if character != " "]
    rules = []
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        first, last = sorted(
            (draw(st.sampled_from(visible)), draw(st.sampled_from(visible))),
        )
        rules.append((draw(st.sampled_from([D, I])), first, last))
    return text, rules


@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_text_and_real_rules(), size=_SIZES)
def test_property_only_real_rules_mark_drawn_type3_text(
    case: tuple[str, list[tuple[str, int, int]]], size: float
) -> None:
    text, rules = case
    content = _type3_pdf(text, rules=rules, size=size)
    # A rule runs from the left edge of its first character to the right edge
    # of its last, so it covers the centre of exactly the characters between.
    expected = [
        (character, {state for state, first, last in rules if first <= index <= last})
        for index, character in enumerate(text)
        if character != " "
    ]

    if any(len(states) == 2 for _character, states in expected):
        with pytest.raises(ValueError, match="is both struck through and underlined"):
            _marked(content)
        return
    marked = _marked(content)

    assert [_strip_amendment_markup(block.body) for block in marked] == [text] == _plain(content)
    assert _states(marked[0].body) == [
        (character, next(iter(states), None)) for character, states in expected
    ]


def _drawing_key(path: dict[str, Any]) -> tuple[Any, ...]:
    return (path["type"], *(round(value, 2) for value in path["rect"]))


def _empty_glyph_procedures(document: Any) -> None:
    """Make every glyph procedure of the document's Type 3 fonts paint nothing."""
    for xref in range(1, document.xref_length()):
        if document.xref_get_key(xref, "Subtype") == ("name", "/Type3"):
            _kind, procedures = document.xref_get_key(xref, "CharProcs")
            for number in re.findall(r"(\d+) 0 R", procedures):
                document.update_stream(int(number), b"0 0 d0")


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_text_and_real_rules(), size=_SIZES)
def test_property_the_glyph_drawings_are_the_ones_the_glyph_procedures_paint(
    case: tuple[str, list[tuple[str, int, int]]], size: float
) -> None:
    text, rules = case
    content = _type3_pdf(text, rules=rules, size=size)

    with (
        fitz.open(stream=content, filetype="pdf") as document,
        fitz.open(stream=content, filetype="pdf") as emptied,
    ):
        _empty_glyph_procedures(emptied)
        drawings = document[0].get_drawings()
        left = Counter(_drawing_key(path) for path in emptied[0].get_drawings())
        glyphs = documents_module._pdf_glyph_drawings(document[0], drawings)

    assert Counter(_drawing_key(drawings[position]) for position in glyphs) == (
        Counter(_drawing_key(path) for path in drawings) - left
    )
    # The emptied copy still has every real rule.
    assert sum(left.values()) == len(rules)


# 3. Leaving glyph drawings out only removes rules ----------------------------------

# Object number, get_fonts base name, font type, and the name MuPDF gives the
# font's spans in a text trace. A Type 3 font without a /Name has an empty base
# name and is "Unnamed-T3" to MuPDF 1.26, "Type3 (N 0 R)" to MuPDF 1.28. A Type0
# font's spans carry its descendant's name (``_DESCENDANTS``). MuPDF keeps 31
# bytes of a name and PyMuPDF leaves out a subset prefix (six characters and "+").
_LONG_NAME = "ABCDEF+AVeryLongFontNameThatMuPDFCutsShort"
_FONTS = [
    (11, "T1", "Type3", "T1"),
    (12, "", "Type3", "Unnamed-T3"),
    (13, "", "Type3", "Type3 (13 0 R)"),
    (14, "Helvetica", "Type1", "Helvetica"),
    (15, "ABCDEF+HiddenHorzOCR-Identity-H", "Type0", "HiddenHorzOCR"),
    # Named as the Type 3 font T1.
    (16, "T1", "TrueType", "T1"),
    # Its descendant is named as the Type 3 fonts without a name.
    (17, "GHIJKL+Other-Identity-H", "Type0", "Unnamed-T3"),
    # Its spans' name, cut short and without the prefix, is the next font's name.
    (18, _LONG_NAME, "Type1", _LONG_NAME[7:31]),
    (19, _LONG_NAME[7:31], "Type3", _LONG_NAME[7:31]),
]
# A Type0 font's descendant: its object number and /BaseFont.
_DESCENDANTS = {15: (25, "ABCDEF+HiddenHorzOCR"), 17: (27, "GHIJKL+Unnamed-T3")}
_TRACE_NAMES = sorted({font[3] for font in _FONTS}) + [
    "Type3 (12 0 R)",
    "Type3 (14 0 R)",
    "NotOnThePage",
]
# MuPDF's bound of a path with no segments, as PyMuPDF prints it.
_EMPTY_BOUND = (2147483520.0, 2147483520.0, -2147483648.0, -2147483648.0)
_STROKE = 0.2
_TEXT_KINDS = {0: "fill-text", 1: "stroke-text", 3: "ignore-text"}


class _CommandDocument:
    """The PDF a ``_CommandPage`` belongs to: its objects are the page's fonts.

    It answers what the glyph rule reads: the page's resources, which list its
    fonts, each font's /Subtype and a Type 3 font's /Name (``xref_get_key``), and
    any other font's dictionary (``xref_object``), with a Type0 font's descendant.
    Every other key is null, so the page has no annotations and no forms.
    """

    is_pdf = True

    def __init__(self, fonts: list[tuple[int, str, str, str]]) -> None:
        self.fonts = {font[0]: font for font in fonts}

    def xref_length(self) -> int:
        return 100

    def xref_get_key(self, xref: int, key: str) -> tuple[str, str]:
        if xref == _CommandPage.xref and key == "Resources":
            fonts = " ".join(f"/F{number} {number} 0 R" for number in self.fonts)
            return "dict", f"<< /Font << {fonts} >> >>"
        font = self.fonts.get(xref)
        if font is not None and key == "Subtype":
            return "name", f"/{font[2]}"
        if font is not None and font[2] == "Type3" and key == "Name" and font[1]:
            return "name", f"/{font[1]}"
        return "null", "null"

    def xref_object(self, xref: int) -> str:
        for number, (descendant, name) in _DESCENDANTS.items():
            if xref == descendant and number in self.fonts:
                return f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{name} >>"
        if xref not in self.fonts:
            return "null"
        _number, base, kind, _trace_name = self.fonts[xref]
        entries = f"/Type /Font /Subtype /{kind}" + (f" /BaseFont /{base}" if base else "")
        if xref in _DESCENDANTS:
            entries += f" /DescendantFonts [{_DESCENDANTS[xref][0]} 0 R]"
        return f"<< {entries} >>"


def _rule_rect(command: tuple[Any, ...]) -> fitz.Rect:
    _kind, x0, x1, y, thickness, _paint = command
    return fitz.Rect(x0, y - thickness / 2, x1, y + thickness / 2)


class _CommandPage:
    """A page given as its sequence of commands: rules, empty paths and text.

    ``commands`` holds ``("rule", x0, x1, y, thickness, paint)``, a rectangle
    filled (``f``), stroked (``s``) or both (``fs``); ``("empty", kind)``, a path
    with no segments; and ``("text", trace font name, span type, characters,
    font size, bound, spans)``. It numbers them as PyMuPDF 1.26.7 does: the bbox
    log has an entry for each command, two for a filled and stroked rectangle,
    and a text's spans carry its entry's position; ``get_drawings`` lists the
    rectangles, numbered by the entries before them less the empty paths, which
    it neither lists nor counts. ``fonts`` holds entries of ``_FONTS``.
    """

    xref = 1

    def __init__(
        self, commands: list[tuple[Any, ...]], fonts: list[tuple[int, str, str, str]]
    ) -> None:
        self.commands = commands
        self.fonts = fonts
        self.reads: Counter[str] = Counter()
        self.parent = _CommandDocument(fonts)

    def _starts(self) -> tuple[list[int], list[int]]:
        """Each command's first bbox-log position and ``get_drawings`` number."""
        positions, numbers = [], []
        position = number = 0
        for command in self.commands:
            positions.append(position)
            numbers.append(number)
            entries = 2 if command[0] == "rule" and command[5] == "fs" else 1
            position += entries
            number += 0 if command[0] == "empty" else entries
        return positions, numbers

    def get_fonts(self, full: bool = False) -> list[tuple[Any, ...]]:
        assert full
        self.reads["fonts"] += 1
        return [
            (xref, "n/a", kind, base, f"F{xref}", "", 0)
            for xref, base, kind, _trace_name in self.fonts
        ]

    def get_bboxlog(self) -> list[tuple[str, tuple[float, ...]]]:
        self.reads["bboxlog"] += 1
        log: list[tuple[str, tuple[float, ...]]] = []
        for command in self.commands:
            if command[0] == "rule":
                rect = _rule_rect(command)
                half = _STROKE / 2
                if "f" in command[5]:
                    log.append(("fill-path", tuple(rect)))
                if "s" in command[5]:
                    log.append(
                        (
                            "stroke-path",
                            (rect.x0 - half, rect.y0 - half, rect.x1 + half, rect.y1 + half),
                        )
                    )
            elif command[0] == "empty":
                log.append((command[1], _EMPTY_BOUND))
            else:
                log.append((_TEXT_KINDS[command[2]], command[5]))
        return log

    def get_texttrace(self) -> list[dict[str, Any]]:
        self.reads["texttrace"] += 1
        positions, _numbers = self._starts()
        return [
            {
                "seqno": positions[index],
                "type": command[2],
                "font": command[1],
                "chars": ((),) * command[3],
                "size": command[4],
            }
            for index, command in enumerate(self.commands)
            if command[0] == "text"
            for _span in range(command[6])
        ]

    def get_drawings(self) -> list[dict[str, Any]]:
        _positions, numbers = self._starts()
        drawings = []
        for index, command in enumerate(self.commands):
            if command[0] != "rule":
                continue
            rect = _rule_rect(command)
            paint = command[5]
            drawing: dict[str, Any] = {
                "seqno": numbers[index],
                "type": paint,
                "rect": rect,
                "items": [("re", rect, 1)],
                "command": index,
            }
            if "f" in paint:
                drawing |= {"fill": (0.0, 0.0, 0.0), "fill_opacity": 1.0}
            if "s" in paint:
                drawing |= {"color": (0.0, 0.0, 0.0), "stroke_opacity": 1.0, "width": _STROKE}
            drawings.append(drawing)
        return drawings


class _WithoutCommands(_CommandPage):
    """The same page with some rules left out and no fonts; numbers are kept."""

    def __init__(self, page: _CommandPage, dropped: set[int]) -> None:
        super().__init__(page.commands, [])
        self.dropped = dropped

    def get_drawings(self) -> list[dict[str, Any]]:
        return [path for path in super().get_drawings() if path["command"] not in self.dropped]


# Rules 3 to 228 pt long and text of 4 to 40 pt: some rules are glyph-sized
# for some of the text, some for none. The text bounds hold all, some or none of
# the rules.
_TEXT_BOUNDS = [(70.0, 90.0, 310.0, 130.0), (71.0, 99.0, 112.0, 104.0), (0.0, 0.0, 10.0, 10.0)]
_RULE_COMMAND = st.tuples(
    st.just("rule"),
    st.sampled_from([72.0, 80.0, 100.0]),
    st.sampled_from([103.0, 110.0, 150.0, 300.0]),
    st.sampled_from([97.0, 101.5, 120.0]),
    st.sampled_from([0.4, 0.8, 2.0, 5.0]),
    st.sampled_from(["f", "s", "fs"]),
)
_EMPTY_COMMAND = st.tuples(st.just("empty"), st.sampled_from(["fill-path", "stroke-path"]))
_TEXT_COMMAND = st.tuples(
    st.just("text"),
    st.sampled_from(_TRACE_NAMES),
    st.sampled_from([0, 1, 3]),
    st.integers(min_value=1, max_value=3),
    st.sampled_from([4.0, 12.0, 40.0]),
    st.sampled_from(_TEXT_BOUNDS),
    st.sampled_from([1, 1, 1, 2]),
)
_COMMAND_PAGES = st.builds(
    _CommandPage,
    st.lists(st.one_of(_RULE_COMMAND, _EMPTY_COMMAND, _TEXT_COMMAND), max_size=14),
    st.lists(st.sampled_from(_FONTS), unique=True, max_size=len(_FONTS)),
)


def _oracle_glyph_commands(page: _CommandPage) -> set[int]:
    """Walk the commands: a glyph-sized rule inside the bound of the one hidden
    character after it, empty paths aside, in a font only Type 3 fonts are named."""
    type3: set[str] = set()
    others: set[str] = set()
    for xref, base, kind, trace_name in page.fonts:
        if kind == "Type3":
            type3 |= {base} if base else {"Unnamed-T3", f"Type3 ({xref} 0 R)"}
        else:
            others.add(trace_name)
    glyphs = set()
    for index, command in enumerate(page.commands):
        following = next(
            (later for later in page.commands[index + 1 :] if later[0] != "empty"), None
        )
        if command[0] != "rule" or following is None or following[0] != "text":
            continue
        rect = _rule_rect(command)
        _kind, font, span_type, characters, size, (left, top, right, bottom), spans = following
        if (
            font in type3 - others
            and (span_type, characters, spans) == (3, 1, 1)
            and max(rect.width, rect.height) <= 2 * size
            and left <= rect.x0 <= rect.x1 <= right
            and top <= rect.y0 <= rect.y1 <= bottom
        ):
            glyphs.add(index)
    return glyphs


@settings(max_examples=2000, deadline=None)
@given(_COMMAND_PAGES)
def test_property_leaving_glyph_drawings_out_only_removes_rules(page: _CommandPage) -> None:
    rules = documents_module._pdf_horizontal_rules(page)
    every_rule = documents_module._pdf_horizontal_rules(_WithoutCommands(page, set()))
    glyphs = _oracle_glyph_commands(page)

    assert rules == documents_module._pdf_horizontal_rules(_WithoutCommands(page, glyphs))
    for kept, all_of_them in zip(rules, every_rule, strict=True):
        assert not Counter(kept) - Counter(all_of_them)
    if not any(kind == "Type3" for _xref, _base, kind, _trace_name in page.fonts):
        assert rules == every_rule
        assert page.reads["texttrace"] == page.reads["bboxlog"] == 0
    if every_rule == ((), ()):
        assert not page.reads
    # The drawings taken for glyphs are the oracle's, among those that would make rules.
    candidates = [
        path for path in page.get_drawings() if any(documents_module._pdf_path_rules(path))
    ]
    found = documents_module._pdf_glyph_drawings(page, candidates)
    assert {candidates[position]["command"] for position in found} == glyphs & {
        path["command"] for path in candidates
    }


def test_a_page_without_a_type3_font_is_not_traced() -> None:
    page = _CommandPage(
        [
            ("rule", 72.0, 110.0, 101.5, 0.6, "f"),
            ("text", "Helvetica", 3, 1, 40.0, _TEXT_BOUNDS[0], 1),
        ],
        [_FONTS[3], _FONTS[4]],
    )

    thin, thick = documents_module._pdf_horizontal_rules(page)

    assert (len(thin), len(thick), page.reads["texttrace"], page.reads["bboxlog"]) == (1, 0, 0, 0)


def test_a_page_without_a_rule_reads_no_fonts_and_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    # Drawn Type 3 text and no rule: its glyphs are not looked for.
    monkeypatch.setattr(documents_module, "_pdf_type3_font_names", _refuse_type3_lookup)
    with fitz.open(stream=_type3_pdf("a a"), filetype="pdf") as document:
        page = document[0]
        assert page.get_drawings()  # the glyphs of "a", a block 3.6 by 6 pt

        assert documents_module._pdf_horizontal_rules(page) == ((), ())


def _refuse_type3_lookup(page: Any) -> frozenset[str]:
    raise AssertionError("read the Type 3 fonts of a page")


def test_a_page_of_a_file_that_is_not_a_pdf_has_no_glyph_drawings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The glyph a Type 3 font draws is the only drawing taken for text, and only a
    # PDF has Type 3 fonts, so the fonts of another document are never read.
    page = _CommandPage(
        [("rule", 72.0, 110.0, 101.5, 0.6, "f"), ("text", "T1", 3, 1, 40.0, _TEXT_BOUNDS[0], 1)],
        [_FONTS[0]],
    )
    page.parent.is_pdf = False
    monkeypatch.setattr(documents_module, "_pdf_type3_font_names", _refuse_type3_lookup)

    thin, thick = documents_module._pdf_horizontal_rules(page)

    assert (len(thin), len(thick), page.reads["texttrace"], page.reads["bboxlog"]) == (1, 0, 0, 0)
    with fitz.open(stream=b"<p>Some <u>underlined</u> text</p>", filetype="html") as document:
        assert not document.is_pdf
        drawing = {"seqno": 0, "type": "f", "rect": fitz.Rect(72, 100, 110, 101), "items": []}
        assert documents_module._pdf_glyph_drawings(document[0], [drawing]) == frozenset()


# A Word 2007+ file saved under a .pdf name; MuPDF opens it as an Office document.
# Reading Page.xref of its pages crashed PyMuPDF 1.26.7 with a segmentation fault,
# so it is extracted in a child process.
VA_WORD_FILE = (
    SOURCES
    / "us-va/manual/2026-09-10-ssi-state-supplement/official-documents"
    / "va-dars-auxiliary-grant-manual-chapter-a.pdf"
)
_EXTRACT_BOTH_WAYS = """
import sys, warnings
from axiom_corpus.corpus import documents
content = open(sys.argv[1], "rb").read()
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    plain = documents._extract_pdf_blocks(content, extraction={})
    marked = documents._extract_pdf_blocks(content, extraction={"amendment_markup": True})
assert [documents._strip_amendment_markup(b.body) for b in marked] == [b.body for b in plain]
print(len(marked))
"""


def test_a_word_file_given_as_a_pdf_still_extracts_with_amendment_markup() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", _EXTRACT_BOTH_WAYS, str(VA_WORD_FILE)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, (result.returncode, result.stderr[-2000:])
    assert int(result.stdout.split()[-1]) > 0


_RULE = ("rule", 72.0, 110.0, 101.5, 0.6, "f")
_AROUND = _TEXT_BOUNDS[0]


@pytest.mark.parametrize(
    ("commands", "fonts", "glyph"),
    [
        # The rule is 38 pt long: 0.95 and 2 font sizes of the text after it.
        ([_RULE, ("text", "T1", 3, 1, 40.0, _AROUND, 1)], [0], True),
        ([_RULE, ("text", "Unnamed-T3", 3, 1, 19.0, _AROUND, 1)], [1], True),
        ([_RULE, ("text", "Type3 (13 0 R)", 3, 1, 40.0, _AROUND, 1)], [2], True),
        # Stroked, or filled and stroked; or with empty paths before or after it.
        ([(*_RULE[:5], "s"), ("text", "T1", 3, 1, 40.0, _AROUND, 1)], [0], True),
        ([(*_RULE[:5], "fs"), ("text", "T1", 3, 1, 40.0, _AROUND, 1)], [0], True),
        (
            [("empty", "fill-path"), ("empty", "stroke-path"), _RULE, ("empty", "fill-path")]
            + [("text", "T1", 3, 1, 40.0, _AROUND, 1)],
            [0],
            True,
        ),
        # The object number of a font that is not Type 3.
        ([_RULE, ("text", "Type3 (14 0 R)", 3, 1, 40.0, _AROUND, 1)], [0, 3], False),
        # Longer than two font sizes, or not inside the character's bound.
        ([_RULE, ("text", "T1", 3, 1, 18.0, _AROUND, 1)], [0], False),
        ([_RULE, ("text", "T1", 3, 1, 40.0, (0.0, 0.0, 10.0, 10.0), 1)], [0], False),
        # Painted text, several hidden characters or spans, or hidden text in another font.
        ([_RULE, ("text", "T1", 0, 1, 40.0, _AROUND, 1)], [0], False),
        ([_RULE, ("text", "T1", 3, 2, 40.0, _AROUND, 1)], [0], False),
        ([_RULE, ("text", "T1", 3, 1, 40.0, _AROUND, 2)], [0], False),
        ([_RULE, ("text", "HiddenHorzOCR", 3, 1, 40.0, _AROUND, 1)], [0, 4], False),
        # A Type 3 font named as another font on the page: as a TrueType font,
        # as a Type0 font's descendant, or as a long name cut short.
        ([_RULE, ("text", "T1", 3, 1, 40.0, _AROUND, 1)], [0, 5], False),
        ([_RULE, ("text", "Unnamed-T3", 3, 1, 40.0, _AROUND, 1)], [1, 6], False),
        ([_RULE, ("text", "Type3 (12 0 R)", 3, 1, 40.0, _AROUND, 1)], [1, 6], True),
        ([_RULE, ("text", _LONG_NAME[7:31], 3, 1, 40.0, _AROUND, 1)], [8], True),
        ([_RULE, ("text", _LONG_NAME[7:31], 3, 1, 40.0, _AROUND, 1)], [7, 8], False),
        # Another drawing in between.
        (
            [_RULE, (*_RULE[:3], 300.0, 0.6, "f"), ("text", "T1", 3, 1, 40.0, _AROUND, 1)],
            [0],
            False,
        ),
    ],
)
def test_a_drawing_is_a_glyph_only_right_before_one_hidden_type3_character(
    commands: list[tuple[Any, ...]], fonts: list[int], glyph: bool
) -> None:
    page = _CommandPage(commands, [_FONTS[index] for index in fonts])
    index = commands.index(next(command for command in commands if command[0] == "rule"))

    thin, _thick = documents_module._pdf_horizontal_rules(page)

    assert (index in _oracle_glyph_commands(page)) is glyph
    assert all(rule.y != 101.5 for rule in thin) is glyph


@pytest.mark.parametrize(
    ("width", "height", "glyph"),
    [
        # Before a 12 pt hidden Type 3 character, up to 24 pt each way.
        (3.0, 0.8, True),
        (24.0, 0.8, True),
        (24.01, 0.8, False),
        # Several short rules stacked in one tall path.
        (3.0, 24.0, True),
        (3.0, 24.01, False),
    ],
)
def test_a_glyph_drawing_is_at_most_two_font_sizes_wide_and_high(
    width: float, height: float, glyph: bool
) -> None:
    rect = fitz.Rect(72.0, 90.0, 72.0 + width, 90.0 + height)
    drawing = {"seqno": 0, "type": "f", "rect": rect, "items": [("re", rect, 1)]}
    page = _CommandPage([("text", "T1", 3, 1, 12.0, _AROUND, 1)], [_FONTS[0]])
    page.get_bboxlog = lambda: [("fill-path", tuple(rect)), ("ignore-text", _AROUND)]  # type: ignore[method-assign]
    page.get_texttrace = lambda: [  # type: ignore[method-assign]
        {"seqno": 1, "type": 3, "font": "T1", "chars": ((),), "size": 12.0}
    ]

    assert (documents_module._pdf_glyph_drawings(page, [drawing]) == {0}) is glyph


_R = (72.0, 100.0, 110.0, 101.0)
_WIDE = (71.9, 99.9, 110.1, 101.1)


@pytest.mark.parametrize(
    ("path_type", "log", "end"),
    [
        ("f", [("fill-path", _R)], 1),
        ("f", [("fill-path", _WIDE)], None),
        ("f", [("stroke-path", _WIDE)], None),
        ("s", [("stroke-path", _WIDE)], 1),
        ("s", [("stroke-path", (72.0, 100.0, 109.0, 101.0))], None),
        ("s", [("fill-path", _R)], None),
        ("fs", [("fill-path", _R), ("stroke-path", _WIDE)], 2),
        ("fs", [("fill-path", _R)], None),
        # PyMuPDF merges a stroke into the fill before it across text; the
        # drawing then does not agree with the entries after its fill.
        ("fs", [("fill-path", _R), ("ignore-text", _WIDE), ("stroke-path", _WIDE)], None),
    ],
)
def test_a_drawing_agrees_with_its_bbox_log_entries(
    path_type: str, log: list[tuple[str, tuple[float, ...]]], end: int | None
) -> None:
    path = {"type": path_type, "rect": fitz.Rect(_R)}

    assert documents_module._pdf_drawing_end(path, log, 0) == end


_LOG_ENTRY = st.one_of(
    st.tuples(
        st.sampled_from(["fill-path", "stroke-path"]), st.sampled_from([_R, _WIDE, _EMPTY_BOUND])
    ),
    st.tuples(
        st.sampled_from(["fill-text", "ignore-text", "fill-shade", "fill-image"]), st.just(_R)
    ),
)


@settings(max_examples=300, deadline=None)
@given(st.lists(_LOG_ENTRY, max_size=20))
def test_property_drawing_numbers_skip_exactly_the_empty_paths(
    log: list[tuple[str, tuple[float, ...]]],
) -> None:
    commands = documents_module._pdf_drawing_commands(log)

    kept = [
        position
        for position, (kind, bound) in enumerate(log)
        if not (kind.endswith("-path") and bound == _EMPTY_BOUND)
    ]
    assert list(commands) == list(range(len(kept)))
    assert list(commands.values()) == kept


@pytest.mark.parametrize(
    "body",
    [
        b"5 5 m 5 5 l f 10 10 m 20 10 l 0.5 w S",
        b"5 5 m 5 5 l S 10 10 m 20 10 l 0.5 w S",
        b"0 0 m f 10 10 m 20 10 l 0.5 w S",
        b"5 5 m h f 10 10 m 20 10 l 0.5 w S",
    ],
)
def test_a_path_of_one_point_keeps_its_drawing_number(body: bytes) -> None:
    # MuPDF bounds a path without segments by a rectangle that ends before it
    # starts, and PyMuPDF makes no drawing of it; a path of one point has a bound of
    # no width and is a drawing.
    document = fitz.open()
    page = document.new_page(width=100, height=100)
    page.insert_text((1, 99), " ")
    document.update_stream(page.get_contents()[0], body)
    page = document[0]
    log = page.get_bboxlog()
    commands = documents_module._pdf_drawing_commands(log)
    drawings = page.get_drawings()

    assert len(drawings) == (2 if b"5 5 l" in body else 1)
    for drawing in drawings:
        index = commands[drawing["seqno"]]
        assert documents_module._pdf_drawing_end(drawing, log, index) == index + 1


def test_no_function_of_the_documents_module_replaces_another() -> None:
    # A second ``def`` of a name replaces the first for every caller, and ruff does
    # not report it when a function body uses the first. The OCR overlay's helper
    # takes a box of no width for empty; the drawing numbers must not.
    tree = ast.parse(Path(documents_module.__file__).read_text(encoding="utf-8"))
    names = Counter(
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.ClassDef)
    )

    assert [name for name, count in names.items() if count > 1] == []
    assert documents_module._pdf_rect_is_empty((5.0, 5.0, 5.0, 9.0))
    assert not documents_module._pdf_bound_is_inverted((5.0, 5.0, 5.0, 9.0))
    assert documents_module._pdf_bound_is_inverted(_EMPTY_BOUND)


# 4. A path without segments changes nothing --------------------------------------


def _type3_stream_with_empty_paths(
    text: str, rules: list[tuple[str, int, int]], places: list[int], size: float
) -> str:
    """``_type3_pdf``'s content, one text object a character, with an empty path
    (a move, filled, stroked or closed) before each part whose index is in ``places``."""
    empties = ["0 0 m f\n", "10 10 m S\n", "5 5 m h f\n", "1 2 m 3 4 m B\n"]
    lefts = [LEFT]
    for character in text:
        lefts.append(lefts[-1] + _advance(character, size))
    parts = [
        f"BT /T1 {size} Tf {lefts[index]} {PAGE_HEIGHT - BASELINE} Td ({character}) Tj ET\n"
        for index, character in enumerate(text)
    ]
    parts += [
        _line(lefts[first], lefts[last + 1], REAL_OFFSETS[state], size)
        for state, first, last in rules
    ]
    return "".join(
        (empties[index % len(empties)] if index in places else "") + part
        for index, part in enumerate(parts + [""])
    )


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    case=_text_and_real_rules(),
    places=st.sets(st.integers(min_value=0, max_value=30), max_size=6),
    in_glyphs=st.booleans(),
)
def test_property_paths_without_segments_change_nothing(
    case: tuple[str, list[tuple[str, int, int]]], places: set[int], in_glyphs: bool
) -> None:
    text, rules = case
    plain = _type3_document(_type3_stream_with_empty_paths(text, rules, [], SIZE))
    saved = dict(_GLYPHS)
    try:
        if in_glyphs:
            # Each glyph's procedure begins and ends with an empty path (the
            # space's stays empty, so MuPDF still paints it as text).
            for character, (name, advance, body) in saved.items():
                if body:
                    _GLYPHS[character] = (name, advance, f"0 0 m f {body} 0 0 m S")
        content = _type3_document(_type3_stream_with_empty_paths(text, rules, sorted(places), SIZE))
    finally:
        _GLYPHS.clear()
        _GLYPHS.update(saved)

    with fitz.open(stream=content, filetype="pdf") as document:
        log = document[0].get_bboxlog()
    assert sum(bound == _EMPTY_BOUND for _kind, bound in log) >= len(
        places & set(range(len(text) + len(rules) + 1))
    )
    try:
        expected = [block.body for block in _marked(plain)]
    except ValueError as error:
        with pytest.raises(ValueError) as raised:
            _marked(content)
        assert str(raised.value) == str(error)
        return
    assert [block.body for block in _marked(content)] == expected


def test_empty_paths_before_a_drawn_glyph_do_not_hide_a_real_underline() -> None:
    # Two empty fills put get_drawings' numbers two behind the bbox log's. The
    # underline is then the command before the hidden "a" by get_drawings'
    # count, but not on the page: it stays a rule and marks the "a".
    stream = (
        "0 0 m f 1 1 m f\n"
        f"BT /T1 {SIZE} Tf {LEFT} {PAGE_HEIGHT - BASELINE} Td (a) Tj ET\n"
        + _line(LEFT, LEFT + 7.2, REAL_OFFSETS[I], SIZE)
    )
    content = _type3_document(stream)

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        assert [kind for kind, _bbox in page.get_bboxlog()] == [
            "fill-path",
            "fill-path",
            "fill-path",
            "ignore-text",
            "stroke-path",
        ]
        assert [(path["seqno"], path["type"]) for path in page.get_drawings()] == [
            (0, "f"),
            (2, "s"),
        ]
        assert _glyph_seqnos(page) == {0}
    assert [block.body for block in _marked(content)] == ["{+a+}"]


def test_a_glyph_filled_and_stroked_is_one_drawing_and_still_a_glyph() -> None:
    # B fills and strokes the hyphen's bar: PyMuPDF reports one drawing (fs)
    # numbered as the fill, and the stroke's number goes unused.
    saved = dict(_GLYPHS)
    try:
        _GLYPHS["-"] = ("hyphen", 350, "50 190 250 70 re B")
        content = _type3_document(
            f"0.2 w BT /T1 {SIZE} Tf {LEFT} {PAGE_HEIGHT - BASELINE} Td (a-a) Tj ET\n"
        )
    finally:
        _GLYPHS.clear()
        _GLYPHS.update(saved)

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        assert [(path["seqno"], path["type"]) for path in page.get_drawings()] == [
            (0, "f"),
            (2, "fs"),
            (5, "f"),
        ]
        assert _glyph_seqnos(page) == {0, 2, 5}
    assert [block.body for block in _marked(content)] == ["a-a"]


# 5. Only a Type 3 font's hidden character makes a glyph --------------------------


_WHERE = [
    "page",
    "page-inline",
    "page-inline-escaped",
    "page-inherited",
    "page-inherited-inline",
    "form",
    "form-inline",
    "appearance",
    "appearance-inline",
    "appearance-states",
    "pattern",
    "soft-mask",
    "type3-glyph",
    "type3-glyph-inline",
]
# The second Type 3 font of the "type3-glyph" pages, whose glyph shows the "a".
_GLYPH_FONT = "Outline"


def _hidden_other_font_page(
    type3_name: str, other: str, base: str, descendant: str, *, where: str = "page"
) -> bytes:
    """A strike inside the bound of one hidden "a", then that "a", in a font that is
    not Type 3: a Type 1 font named ``base``, or a Type0 font named ``base`` whose
    descendant is named ``descendant``. The page also has a Type 3 font named
    ``type3_name``. ``where`` (one of ``_WHERE``) says where the "a" and its font
    sit:

    - ``page``: in the page's content and resources, the font referenced;
      ``-inline`` writes it in the resources, ``-escaped`` also names it there
      ``/H#2F1`` (a "/" in its resource name), and ``-inherited`` moves the
      resources to the page-tree node the page inherits them from;
    - ``form``: in a form the page draws right after the strike, the font
      referenced or (``-inline``) written inline;
    - ``appearance``: in an annotation's appearance stream, the font referenced
      or (``-inline``) written inline; ``-states`` reaches the stream through a
      dictionary of appearance states;
    - ``pattern``, ``soft-mask``: in a tiling pattern the page fills with, or in
      the group of a soft mask the page paints through, right after the strike;
    - ``type3-glyph``: in the procedure of a glyph of a second Type 3 font
      (``_GLYPH_FONT``; with ``-inline`` both fonts are written inline). The
      procedure shows the "a" and then strokes a line in the width it inherits,
      so MuPDF draws the glyph on the page, and the glyph's own hidden character
      follows.

    The strike is always the page's first command and the "a" its second."""
    document = fitz.open(
        stream=_type3_document("", font_name=f"/Name /{type3_name} "), filetype="pdf"
    )
    page = document[0]
    if other == "Type1":
        font = f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} >>"
        code = "(a)"
    else:
        cid = document.get_new_xref()
        document.update_object(
            cid,
            f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{descendant} "
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
            f"/FontDescriptor << /Type /FontDescriptor /FontName /{descendant} /Flags 32 "
            "/FontBBox [0 -200 1000 800] /ItalicAngle 0 /Ascent 800 /Descent -200 "
            "/CapHeight 700 /StemV 80 >> >>",
        )
        font = (
            f"<< /Type /Font /Subtype /Type0 /BaseFont /{base} /Encoding /Identity-H "
            f"/DescendantFonts [{cid} 0 R] >>"
        )
        code = "<0041>"

    def placed(dictionary: str) -> str:
        """``dictionary`` as written in a resource dictionary: inline, or referenced."""
        if "inline" in where:
            return dictionary
        xref = document.get_new_xref()
        document.update_object(xref, dictionary)
        return f"{xref} 0 R"

    def stream_object(dictionary: str, stream: str) -> int:
        xref = document.get_new_xref()
        document.update_object(xref, dictionary)
        document.update_stream(xref, stream.encode(), compress=False)
        return xref

    name = "H#2F1" if where.endswith("escaped") else "H"
    own = f"<< /Font << /{name} {placed(font)} >> >>"  # the resources the "a" runs with
    y = PAGE_HEIGHT - (BASELINE + REAL_OFFSETS[D] * SIZE)
    strike = f"0.6 w {LEFT + 1} {y} m {LEFT + 6} {y} l S\n"
    text = f"BT 3 Tr /{name} {SIZE} Tf {LEFT} {PAGE_HEIGHT - BASELINE} Td {code} Tj ET\n"
    square = f"{LEFT} {PAGE_HEIGHT - BASELINE - 2} 20 20 re f"
    fonts = "/T1 " + document.xref_get_key(page.xref, "Resources/Font/T1")[1]
    others = ""
    stream = strike + text
    form = f"/Type /XObject /Subtype /Form /BBox [0 0 595 {PAGE_HEIGHT}]"
    if where.startswith("page"):
        fonts += f" /{name} {placed(font)}"
    elif where.startswith("form"):
        drawn = stream_object(f"<< {form} /Resources {own} >>", text)
        others = f" /XObject << /Fm1 {drawn} 0 R >>"
        stream = strike + "/Fm1 Do\n"
    elif where.startswith("appearance"):
        normal = f"{stream_object(f'<< {form} /Resources {own} >>', stream)} 0 R"
        if where.endswith("states"):
            states = document.get_new_xref()
            document.update_object(states, f"<< /On {normal} >>")
            normal = f"{states} 0 R"
        annotation = document.get_new_xref()
        document.update_object(
            annotation,
            f"<< /Type /Annot /Subtype /Square /Rect [0 0 595 {PAGE_HEIGHT}] /F 4 /AS /On "
            f"/AP << /N {normal} >> >>",
        )
        document.xref_set_key(page.xref, "Annots", f"[{annotation} 0 R]")
        stream = ""
    elif where == "pattern":
        pattern = stream_object(
            f"<< /PatternType 1 /PaintType 1 /TilingType 1 /BBox [0 0 595 {PAGE_HEIGHT}] "
            f"/XStep 595 /YStep {PAGE_HEIGHT} /Resources {own} >>",
            text,
        )
        others = f" /Pattern << /P1 {pattern} 0 R >>"
        stream = strike + f"/Pattern cs /P1 scn {square}\n"
    elif where == "soft-mask":
        group = stream_object(
            f"<< {form} /Group << /S /Transparency /CS /DeviceGray >> /Resources {own} >>",
            text + f"1 g 0 0 595 {PAGE_HEIGHT} re f\n",
        )
        others = f" /ExtGState << /G1 << /SMask << /S /Luminosity /G {group} 0 R >> >> >>"
        stream = strike + f"q /G1 gs 0 0 1 rg {square} Q\n"
    else:
        procedure = stream_object(
            "<<>>", f"600 0 d0 BT 3 Tr /{name} 1000 Tf 0 0 Td {code} Tj ET 0 0 m 0 500 l S"
        )
        glyphs = (
            f"<< /Type /Font /Subtype /Type3 /Name /{_GLYPH_FONT} /FontBBox [0 -200 1000 800] "
            f"/FontMatrix [0.001 0 0 0.001 0 0] /Resources {own} /CharProcs << /g {procedure} "
            "0 R >> /Encoding << /Type /Encoding /Differences [98 /g] >> /FirstChar 98 "
            "/LastChar 98 /Widths [600] >>"
        )
        fonts += f" /G {placed(glyphs)}"
        stream = strike + f"BT /G {SIZE} Tf {LEFT} {PAGE_HEIGHT - BASELINE} Td (b) Tj ET\n"
    resources = f"<< /Font << {fonts} >>{others} >>"
    holder = page.xref
    if "inherited" in where:
        holder = int(document.xref_get_key(document.pdf_catalog(), "Pages")[1].split()[0])
        document.xref_set_key(page.xref, "Resources", "null")
    document.xref_set_key(holder, "Resources", resources)
    contents = stream_object("<<>>", stream)
    document.xref_set_key(page.xref, "Contents", f"{contents} 0 R")
    content = document.tobytes()
    document.close()
    return content


def _hidden_a(page: Any) -> dict[str, Any]:
    """The span of the hidden "a" of a ``_hidden_other_font_page``: the page's second
    command."""
    (span,) = [span for span in page.get_texttrace() if span["seqno"] == 1]
    return span


_NAMES = st.sampled_from(
    ["Helvetica", "T1", "ABCDEF+T1", "AB+CDEF+T1", _LONG_NAME, _LONG_NAME[7:31]]
)


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    type3_name=_NAMES,
    other=st.sampled_from(["Type1", "Type0"]),
    base=_NAMES,
    descendant=_NAMES,
    where=st.sampled_from(_WHERE),
)
def test_property_hidden_text_in_another_font_never_makes_a_glyph(
    type3_name: str, other: str, base: str, descendant: str, where: str
) -> None:
    content = _hidden_other_font_page(type3_name, other, base, descendant, where=where)

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        span = _hidden_a(page)
        assert span["type"] == 3
        names = documents_module._pdf_type3_font_names(page)
        # The span carries the name of a font that is not Type 3; some cases
        # give it a Type 3 font's name.
        assert span["font"] not in documents_module._pdf_glyph_font_names(page)
        # Only the second Type 3 font's glyph, the line its procedure strokes, is one.
        assert _glyph_seqnos(page) == ({2} if where.startswith("type3-glyph") else set())
        thin, _thick = documents_module._pdf_horizontal_rules(page)
    assert len(thin) == 1
    if type3_name == base and other == "Type1" and len(base) <= 31:
        assert span["font"] in names  # the collision the rule guards against


@pytest.mark.parametrize("where", _WHERE)
def test_a_type3_font_named_as_another_font_keeps_that_fonts_rule(
    where: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unused Type 3 font named Helvetica, then a strike inside the bound of one
    # hidden Type 1 Helvetica "a": the hidden character's span names a Type 3 font
    # too, and without the other fonts' names the strike is taken for its glyph.
    content = _hidden_other_font_page("Helvetica", "Type1", "Helvetica", "", where=where)
    second = {_GLYPH_FONT} if where.startswith("type3-glyph") else set()

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        assert documents_module._pdf_type3_font_names(page) == {"Helvetica"} | second
        assert "Helvetica" in (documents_module._pdf_other_font_names(page) or ())
        assert documents_module._pdf_glyph_font_names(page) == second
    kept = [block.body for block in _marked(content)]
    monkeypatch.setattr(documents_module, "_pdf_other_font_names", lambda _page: frozenset())
    lost = [block.body for block in _marked(content)]
    assert [_strip_amendment_markup(body) for body in kept] == [
        _strip_amendment_markup(body) for body in lost
    ]
    assert "[-a" in kept[0] and "[-" not in lost[0]


@pytest.mark.parametrize(
    "where",
    [
        "page-inline",
        "page-inline-escaped",
        "page-inherited-inline",
        "form-inline",
        "appearance-inline",
    ],
)
def test_an_inline_type0_font_is_known_by_its_descendant_name(where: str) -> None:
    # MuPDF names a Type0 font's spans after its descendant font, here "T1", the
    # name of the page's Type 3 font too.
    content = _hidden_other_font_page("T1", "Type0", "Outer-Identity-H", "T1", where=where)

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        assert _hidden_a(page)["font"] == "T1"
        assert "T1" in documents_module._pdf_type3_font_names(page)
        assert documents_module._pdf_glyph_font_names(page) == frozenset()


# When the page's other fonts can't all be read, nothing on it is a glyph, and its
# drawn glyphs mark it as they did before the classifier recognised glyphs.
_DRAWN = "aa-aa_a a"
_AS_BEFORE = "aa[---]aa{+_+}a a"


def _with_page_resources(content: bytes, resources: str) -> bytes:
    """``content`` with its page's resources set to ``resources``, in which ``{t1}``
    stands for the Type 3 font and ``{new}`` for a new object's number; the new
    object, when used, is a form that draws itself (``/XObject << /X0 {new} 0 R >>``
    in its own resources)."""
    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        new = document.get_new_xref()
        document.update_object(
            new,
            "<< /Type /XObject /Subtype /Form /BBox [0 0 10 10] "
            f"/Resources << /XObject << /X0 {new} 0 R >> >> >>",
        )
        document.update_stream(new, b"", compress=False)
        t1 = document.xref_get_key(page.xref, "Resources/Font/T1")[1]
        document.xref_set_key(page.xref, "Resources", resources.format(t1=t1, new=new))
        return document.tobytes()


def test_a_walk_past_its_bound_recognises_no_glyph(monkeypatch: pytest.MonkeyPatch) -> None:
    content = _type3_pdf(_DRAWN)
    assert [block.body for block in _marked(content)] == [_DRAWN]

    monkeypatch.setattr(documents_module, "_PDF_FONT_RESOURCES", 0)
    with fitz.open(stream=content, filetype="pdf") as document:
        assert documents_module._pdf_page_fonts(document[0]) is None
        assert documents_module._pdf_glyph_font_names(document[0]) == frozenset()
    assert [block.body for block in _marked(content)] == [_AS_BEFORE]


def test_a_read_that_raises_recognises_no_glyph(monkeypatch: pytest.MonkeyPatch) -> None:
    # The Type 1 Helvetica "a" sits in an appearance stream; the walk can't read
    # the annotation, so the strike stays a rule though a Type 3 font is named
    # Helvetica too.
    content = _hidden_other_font_page("Helvetica", "Type1", "Helvetica", "", where="appearance")

    def unreadable(_document: Any, _xref: int) -> bool:
        raise RuntimeError("an object that can't be read")

    monkeypatch.setattr(fitz.Document, "xref_is_stream", unreadable)
    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        assert documents_module._pdf_page_fonts(page) is None
        assert documents_module._pdf_other_font_names(page) is None
        assert documents_module._pdf_type3_font_names(page) == {"Helvetica"}
        assert documents_module._pdf_glyph_font_names(page) == frozenset()
    assert [block.body for block in _marked(content)] == ["[-a-]"]


def test_a_font_without_a_name_recognises_no_glyph() -> None:
    # MuPDF names the spans of a font without a /BaseFont after nothing in its
    # dictionary (an empty name, for one without a font program), so nothing tells
    # its hidden text from a Type 3 font's.
    content = _with_page_resources(
        _type3_pdf(_DRAWN), "<< /Font << /T1 {t1} /F2 << /Type /Font /Subtype /Type1 >> >> >>"
    )

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        assert documents_module._pdf_page_fonts(page) == ["<</Type/Font/Subtype/Type1>>"]
        assert documents_module._pdf_other_font_names(page) is None
    assert [block.body for block in _marked(content)] == [_AS_BEFORE]


def test_a_form_that_draws_itself_ends_no_walk() -> None:
    # The walk reads each object once, so a cycle through a form's resources
    # neither loops nor reaches the bound, and the glyphs stay glyphs.
    content = _with_page_resources(
        _type3_pdf(_DRAWN), "<< /Font << /T1 {t1} >> /XObject << /X0 {new} 0 R >> >>"
    )

    with fitz.open(stream=content, filetype="pdf") as document:
        assert documents_module._pdf_page_fonts(document[0]) == []
    assert [block.body for block in _marked(content)] == [_DRAWN]


# 6. The CMS approval package pages -------------------------------------------------

AZ_22_0007 = (
    "us-az/policy/2026-09-13-chip-state-plan/official-documents/"
    "us-az-cms-chip-state-plan-spa-az-22-0007-approval-package.pdf"
)
MO_21_0032 = (
    "us-mo/policy/2026-09-13-medicaid-state-plan/official-documents/"
    "us-mo-cms-medicaid-state-plan-spa-mo-21-0032-approval-document.pdf"
)
_MEDICAID = "us-{state}/policy/2026-09-13-medicaid-state-plan/official-documents/"
# The ten pages whose Type 3 text marked itself with PyMuPDF 1.26.7 (hyphen-like
# glyph bars 1.5 to 4.7 pt long), each with the runs it keeps. Renderings show no
# struck or underlined text on them. Missouri page 17 keeps five "I": Acrobat's
# OCR read the file icons of a table column as "I", hidden text in Times-Roman
# with the cell border under it. That is a table rule under text, which the
# classifier reads as an underline with every PyMuPDF version.
_CMS_PAGES: list[tuple[str, int, list[tuple[str, str]]]] = [
    (AZ_22_0007, 94, []),
    (AZ_22_0007, 96, []),
    (
        _MEDICAID.format(state="ca")
        + "us-ca-cms-medicaid-state-plan-spa-ca-22-0036-approval-document.pdf",
        11,
        [],
    ),
    (
        _MEDICAID.format(state="ca")
        + "us-ca-cms-medicaid-state-plan-spa-ca-25-0037-approval-document.pdf",
        26,
        [],
    ),
    (
        _MEDICAID.format(state="mi")
        + "us-mi-cms-medicaid-state-plan-spa-mi-25-0101-approval-document.pdf",
        5,
        [],
    ),
    (MO_21_0032, 17, [("I I I I", I), ("I", I)]),
    (MO_21_0032, 27, []),
    (
        _MEDICAID.format(state="ms")
        + "us-ms-cms-medicaid-state-plan-spa-ms-19-0018-approval-document.pdf",
        37,
        [],
    ),
    (
        _MEDICAID.format(state="ms")
        + "us-ms-cms-medicaid-state-plan-spa-ms-19-0018-approval-document.pdf",
        39,
        [],
    ),
    (
        _MEDICAID.format(state="wi")
        + "us-wi-cms-medicaid-state-plan-spa-wi-25-0006-a-approval-document.pdf",
        2,
        [],
    ),
]


def _page_markup(relative: str, page_number: int) -> tuple[str, dict[str, Any], str]:
    extraction: dict[str, Any] = {"amendment_markup": True}
    with fitz.open(SOURCES / relative) as document:
        page = document[page_number - 1]
        default_text = _normalize_text(documents_module._pdf_page_text(page, extraction={}))
        with warnings.catch_warnings():
            # Missouri's cell borders lie within 0.03 font sizes of a threshold.
            warnings.simplefilter("ignore", PdfAmendmentMarkupWarning)
            text, metadata = documents_module._pdf_page_layered_text(
                page,
                extraction=extraction,
                markup=documents_module._pdf_amendment_markup_config(extraction),
                page_number=page_number,
            )
    assert metadata is not None
    return text, metadata, default_text


@pytest.mark.parametrize(("relative", "page_number", "expected_runs"), _CMS_PAGES)
def test_the_type3_text_of_the_cms_pages_does_not_mark_itself(
    relative: str, page_number: int, expected_runs: list[tuple[str, str]]
) -> None:
    text, metadata, default_text = _page_markup(relative, page_number)

    assert _strip_amendment_markup(text) == default_text
    assert [run for run in _amendment_markup_runs(text) if run[1] is not None] == expected_runs
    assert metadata["deleted_runs"] == 0
    assert metadata["inserted_runs"] == len(expected_runs)


def test_the_real_underlines_of_a_type3_page_keep_their_marks() -> None:
    # Arizona page 110 underlines "The Office of Community Relations" and "The
    # Office of Legal Assistance" with real rules 150 and 174 pt long. With
    # PyMuPDF 1.26.7 three hyphen bars also struck a character each.
    text, metadata, default_text = _page_markup(AZ_22_0007, 110)

    assert _strip_amendment_markup(text) == default_text
    assert (metadata["deleted_runs"], metadata["inserted_runs"]) == (0, 2)
    inserted = [run for run, state in _amendment_markup_runs(text) if state == I]
    # The font's codes are not characters; both runs begin with those of "The".
    assert [run[:3] for run in inserted] == ["$\x1a\x02", "$\x1a\x02"]
