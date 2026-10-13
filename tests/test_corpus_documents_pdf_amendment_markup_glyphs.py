"""A drawing that is a glyph is not an amendment rule.

MuPDF draws a Type 3 glyph that it cannot cache by running the glyph's
procedure on the page, and then reports the character as hidden text. PyMuPDF
lists such a glyph among the page's drawings, so ``amendment_markup`` took the
bar of a hyphen for a strike and an underscore for an underline. With PyMuPDF
1.26.7 that marked characters on ten pages of CMS state plan approval packages
set in Type 3 fonts. PyMuPDF 1.28.2 paints those fonts' glyphs as text and
marks none of them; it still draws the glyphs of the font built here.
``_pdf_drawing_is_glyph`` recognises the glyph drawings and
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
   page has no Type 3 font, in which case the page's text is not traced. A
   glyph drawing is one that directly precedes a one-character hidden span in
   a Type 3 font and is at most two of that span's font sizes wide and high.
"""

from __future__ import annotations

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


def _no_glyph_drawings(_page: Any) -> dict[int, float]:
    return {}


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
        sizes = documents_module._pdf_drawn_glyph_sizes(page)
        drawings = page.get_drawings()

    assert sizes == {0: SIZE, 2: SIZE, 4: SIZE, 7: SIZE}
    assert all(documents_module._pdf_drawing_is_glyph(path, sizes) for path in drawings)
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
    monkeypatch.setattr(documents_module, "_pdf_drawn_glyph_sizes", _no_glyph_drawings)
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
        assert len(documents_module._pdf_drawn_glyph_sizes(page)) == 8
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
    monkeypatch.setattr(documents_module, "_pdf_drawn_glyph_sizes", _no_glyph_drawings)
    with pytest.raises(ValueError, match="'-' is both struck through and underlined"):
        _marked(content)


def test_a_heavy_glyph_bar_draws_no_thick_rule_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    # At 30 pt the hyphen's bar is 2.1 pt thick: too thick to classify, and at a
    # strike position, which warns when the bar is taken for a rule.
    content = _type3_pdf("a-a", size=30.0)

    assert [block.body for block in _marked(content)] == ["a-a"]

    monkeypatch.setattr(documents_module, "_pdf_drawn_glyph_sizes", _no_glyph_drawings)
    with pytest.raises(PdfAmendmentMarkupWarning, match="thicker than 1.5 pt"):
        _marked(content)


def test_a_glyph_drawn_as_two_paths_is_recognised_only_by_its_last_one() -> None:
    # "=" fills its upper bar, then its lower one. Only the lower bar is the
    # drawing right before the hidden character, so the upper one, at a strike
    # offset, still marks it.
    with fitz.open(stream=_type3_pdf("a=a"), filetype="pdf") as document:
        page = document[0]
        assert [path["seqno"] for path in page.get_drawings()] == [0, 2, 3, 5]
        assert set(documents_module._pdf_drawn_glyph_sizes(page)) == {0, 3, 5}

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
        assert documents_module._pdf_drawn_glyph_sizes(reopened[0]) == {}
    assert [block.body for block in _marked(content)] == ["{+I+}"]


@pytest.mark.parametrize(
    ("rule_length", "expected"),
    [
        # 120 pt is ten font sizes: no glyph of a 12 pt font is that long.
        (120.0, "{+a+}"),
        # 7.2 pt, the width of the "a", could be a glyph: it is taken for one.
        (7.2, "a"),
    ],
)
def test_a_rule_before_hidden_type3_text_is_a_glyph_only_if_it_is_glyph_sized(
    rule_length: float, expected: str
) -> None:
    # Text rendering mode 3 hides the "a" in the PDF itself, so MuPDF does not
    # draw its glyph, and the underline drawn before it is the previous command.
    stream = _line(LEFT, LEFT + rule_length, REAL_OFFSETS[I], SIZE) + (
        f"BT /T1 {SIZE} Tf 3 Tr {LEFT} {PAGE_HEIGHT - BASELINE} Td (a) Tj ET\n"
    )
    content = _type3_document(stream)

    with fitz.open(stream=content, filetype="pdf") as document:
        page = document[0]
        assert [kind for kind, _bbox in page.get_bboxlog()] == ["stroke-path", "ignore-text"]
        assert documents_module._pdf_drawn_glyph_sizes(page) == {0: SIZE}
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


# 3. Leaving glyph drawings out only removes rules ----------------------------------

# Object number, get_fonts base name, font type, and the name MuPDF gives the
# font in a text trace. A Type 3 font without a /Name has an empty base name and
# is "Unnamed-T3" to MuPDF 1.26, "Type3 (N 0 R)" to MuPDF 1.28.
_FONTS = [
    (11, "T1", "Type3", "T1"),
    (12, "", "Type3", "Unnamed-T3"),
    (13, "", "Type3", "Type3 (13 0 R)"),
    (14, "Helvetica", "Type1", "Helvetica"),
    (15, "HiddenHorzOCR", "Type0", "HiddenHorzOCR"),
]
_TRACE_NAMES = [*(font[3] for font in _FONTS), "Type3 (12 0 R)", "Type3 (14 0 R)", "NotOnThePage"]


class _CommandPage:
    """A page given as its sequence of commands: rule drawings and text spans.

    ``commands`` holds ``("rule", x0, x1, y, thickness)`` and ``("text", trace
    font name, span type, characters, font size)``; a command's index is its
    ``seqno``. ``fonts`` holds entries of ``_FONTS``.
    """

    def __init__(
        self, commands: list[tuple[Any, ...]], fonts: list[tuple[int, str, str, str]]
    ) -> None:
        self.commands = commands
        self.fonts = fonts
        self.traces = 0

    def get_fonts(self, full: bool = False) -> list[tuple[Any, ...]]:
        assert full
        return [
            (xref, "n/a", kind, base, f"F{xref}", "", 0)
            for xref, base, kind, _trace_name in self.fonts
        ]

    def get_texttrace(self) -> list[dict[str, Any]]:
        self.traces += 1
        return [
            {
                "seqno": seqno,
                "type": command[2],
                "font": command[1],
                "chars": ((),) * command[3],
                "size": command[4],
            }
            for seqno, command in enumerate(self.commands)
            if command[0] == "text"
        ]

    def get_drawings(self) -> list[dict[str, Any]]:
        drawings = []
        for seqno, command in enumerate(self.commands):
            if command[0] != "rule":
                continue
            _kind, x0, x1, y, thickness = command
            rect = fitz.Rect(x0, y - thickness / 2, x1, y + thickness / 2)
            drawings.append(
                {
                    "seqno": seqno,
                    "type": "f",
                    "fill": (0.0, 0.0, 0.0),
                    "fill_opacity": 1.0,
                    "rect": rect,
                    "items": [("re", rect, 1)],
                }
            )
        return drawings


class _WithoutCommands(_CommandPage):
    """The same page with some drawings left out and no fonts; seqnos are kept."""

    def __init__(self, page: _CommandPage, dropped: set[int]) -> None:
        super().__init__(page.commands, [])
        self.dropped = dropped

    def get_drawings(self) -> list[dict[str, Any]]:
        return [path for path in super().get_drawings() if path["seqno"] not in self.dropped]


# Rules 3 to 228 pt long and text of 4 to 40 pt: some rules are glyph-sized
# for some of the text, some for none.
_RULE_COMMAND = st.tuples(
    st.just("rule"),
    st.sampled_from([72.0, 80.0, 100.0]),
    st.sampled_from([103.0, 110.0, 150.0, 300.0]),
    st.sampled_from([97.0, 101.5, 120.0]),
    st.sampled_from([0.4, 0.8, 2.0, 5.0]),
)
_TEXT_COMMAND = st.tuples(
    st.just("text"),
    st.sampled_from(_TRACE_NAMES),
    st.sampled_from([0, 1, 3]),
    st.integers(min_value=1, max_value=3),
    st.sampled_from([4.0, 12.0, 40.0]),
)
_COMMAND_PAGES = st.builds(
    _CommandPage,
    st.lists(st.one_of(_RULE_COMMAND, _TEXT_COMMAND), max_size=12),
    st.lists(st.sampled_from(_FONTS), unique=True, max_size=len(_FONTS)),
)


def _oracle_glyph_drawings(page: _CommandPage) -> set[int]:
    """Walk the commands: a glyph-sized rule right before one hidden Type 3 character."""
    type3 = set()
    for xref, base, kind, _trace_name in page.fonts:
        if kind == "Type3":
            type3 |= {base} if base else {"Unnamed-T3", f"Type3 ({xref} 0 R)"}
    glyphs = set()
    for seqno, command in enumerate(page.commands[:-1]):
        following = page.commands[seqno + 1]
        if (
            command[0] == "rule"
            and following[0] == "text"
            and following[1] in type3
            and following[2] == 3
            and following[3] == 1
            and max(command[2] - command[1], command[4]) <= 2 * following[4]
        ):
            glyphs.add(seqno)
    return glyphs


@settings(max_examples=1500, deadline=None)
@given(_COMMAND_PAGES)
def test_property_leaving_glyph_drawings_out_only_removes_rules(page: _CommandPage) -> None:
    rules = documents_module._pdf_horizontal_rules(page)
    every_rule = documents_module._pdf_horizontal_rules(_WithoutCommands(page, set()))
    glyphs = _oracle_glyph_drawings(page)

    assert rules == documents_module._pdf_horizontal_rules(_WithoutCommands(page, glyphs))
    for kept, all_of_them in zip(rules, every_rule, strict=True):
        assert not Counter(kept) - Counter(all_of_them)
    if not any(kind == "Type3" for _xref, _base, kind, _trace_name in page.fonts):
        assert rules == every_rule
        assert page.traces == 0


def test_a_page_without_a_type3_font_is_not_traced() -> None:
    page = _CommandPage(
        [("rule", 72.0, 110.0, 101.5, 0.6), ("text", "Helvetica", 3, 1, 40.0)],
        [_FONTS[3], _FONTS[4]],
    )

    thin, thick = documents_module._pdf_horizontal_rules(page)

    assert (len(thin), len(thick), page.traces) == (1, 0, 0)


@pytest.mark.parametrize(
    ("following", "glyph"),
    [
        # The rule is 38 pt long: 0.95 and 2 font sizes of the text after it.
        (("text", "T1", 3, 1, 40.0), True),
        (("text", "Unnamed-T3", 3, 1, 19.0), True),
        (("text", "Type3 (13 0 R)", 3, 1, 40.0), True),
        # The object number of a font that is not Type 3.
        (("text", "Type3 (14 0 R)", 3, 1, 40.0), False),
        # Longer than two font sizes.
        (("text", "T1", 3, 1, 18.0), False),
        # Painted text, several hidden characters, or hidden text in another font.
        (("text", "T1", 0, 1, 40.0), False),
        (("text", "T1", 3, 2, 40.0), False),
        (("text", "HiddenHorzOCR", 3, 1, 40.0), False),
        (("rule", 72.0, 110.0, 300.0, 0.6), False),
    ],
)
def test_a_drawing_is_a_glyph_only_right_before_one_hidden_type3_character(
    following: tuple[Any, ...], glyph: bool
) -> None:
    page = _CommandPage([("rule", 72.0, 110.0, 101.5, 0.6), following], list(_FONTS))

    thin, _thick = documents_module._pdf_horizontal_rules(page)

    assert (0 in _oracle_glyph_drawings(page)) is glyph
    assert all(rule.y != 101.5 for rule in thin) is glyph


@pytest.mark.parametrize(
    ("seqno", "width", "height", "glyph"),
    [
        # The command before a 12 pt hidden Type 3 character, up to 24 pt each way.
        (4, 3.0, 0.8, True),
        (4, 24.0, 24.0, True),
        (4, 24.1, 0.8, False),
        # Several short rules stacked in one tall path.
        (4, 3.0, 24.1, False),
        # Not before such a character, no command number, or no font size.
        (5, 3.0, 0.8, False),
        (None, 3.0, 0.8, False),
        (6, 3.0, 0.8, False),
    ],
)
def test_a_glyph_drawing_is_at_most_two_font_sizes_wide_and_high(
    seqno: int | None, width: float, height: float, glyph: bool
) -> None:
    path = {"seqno": seqno, "rect": fitz.Rect(72.0, 100.0, 72.0 + width, 100.0 + height)}

    assert documents_module._pdf_drawing_is_glyph(path, {4: 12.0, 6: 0.0}) is glyph


# 4. The CMS approval package pages -------------------------------------------------

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
