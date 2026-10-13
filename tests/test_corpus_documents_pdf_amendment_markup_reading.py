"""Reading amendment markup back.

``_render_amendment_markup`` writes GNU wdiff delimiters around struck
(``[-...-]``) and underlined (``{+...+}``) runs. A run whose last character and
its closer make a token cannot be read by removing every occurrence of the four
tokens: a struck run ending in "[" is written ``[-[-]`` and an underlined run
ending in "{" is written ``{+{+}``, and the old ``str.replace`` strip took the
run's own "[" with the closer's "-", turning "[" into "]". A sweep of every
retained PDF found 22 such pages, which ``_pdf_page_layered_text`` stopped with
"amendment markup changed the text": 12 pages of Maryland session laws and a
bill, which strike the brackets of a deletion that an amendment struck, and 10
pages of CMS state plan approval packages, whose Type 3 glyphs marked
themselves and no longer do
(``test_corpus_documents_pdf_amendment_markup_glyphs``).
``_amendment_markup_runs`` reads the delimiters left to right instead.

Invariants, for any raw text and any states (Hypothesis, and every text of up to
four characters):

1. ``delimiters_in_text`` lists exactly the tokens spelled by two adjacent
   visible characters that have the same state, so that no delimiter is written
   between them.
2. When it is empty, reading the rendered markup back gives the normalized text,
   every visible character's state, and the run counts the renderer reports.
3. Whatever main accepts, this accepts with the same output: if the raw text
   holds no token and the old strip gives back the normalized text, then
   ``delimiters_in_text`` is empty and the reader gives back the same text.
4. Where the normalized text holds no token, the old strip fails exactly when a
   struck run ends in "[" or an underlined run ends in "{".
5. ``_pdf_page_layered_text`` on a page with drawn strike and underline rules
   refuses with a ValueError naming the page when the raw text holds a token, or
   when ``delimiters_in_text`` is not empty; otherwise it returns markup that
   reads back to the default page text and to the drawn states. It accepts every
   page main accepts.

The reader is checked against an independent character-by-character oracle
(``_oracle_runs``), and ``delimiters_in_text`` against one computed from the
input alone (``_tokens_spelled_in_one_stretch``).
"""

from __future__ import annotations

import dataclasses
import itertools
import re
import warnings
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import (
    PdfAmendmentMarkupWarning,
    _amendment_markup_runs,
    _normalize_text,
    _render_amendment_markup,
    _strip_amendment_markup,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = REPO_ROOT / "data" / "corpus" / "sources"
MD_STATUTE = SOURCES / "us-md/statute"
MD_2025_CH_604 = (
    MD_STATUTE
    / "2026-10-06-w6-income-tax-statute-md/official-documents"
    / "us-md-statute-session-laws-2025-chapter-604.pdf"
)

D = "deleted"
I = "inserted"  # noqa: E741
TOKENS = ("[-", "-]", "{+", "+}")
ZWSP = "\u200b"
ZERO_WIDTH = (ZWSP, "\ufeff")
FONT = "helv"
SIZE = 12.0
BASELINE = 100.0
LINE_PITCH = 30.0
CELL = 6.0
STRIKE_OFFSET = -0.25
UNDERLINE_OFFSET = 0.13
MD_LINE = "the budget bill [shall] MAY specify"
MD_STATES: list[str | None] = [None] * 16 + [D] + [None] * 5 + [D] * 5 + [None] * 8

_SETTINGS = settings(
    max_examples=1500,
    deadline=None,
    suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow],
)
# Delimiter characters next to runs, zero-width characters that normalizing
# drops, and characters that str.splitlines and str.split treat as breaks.
_ALPHABET = ("a", "b", "[", "]", "-", "{", "}", "+", " ", "\n", "\r", *ZERO_WIDTH, "\x1c", "\x85")
_STATES: tuple[str | None, ...] = (None, D, I)


def _oracle_runs(text: str) -> list[tuple[str, str | None]]:
    """Read wdiff markup one character at a time.

    Outside a run "[-" and "{+" open one; inside, only the run's own closer
    ends it, so a struck run's "[" just before "-]" is text.
    """
    runs: list[tuple[str, str | None]] = []
    state: str | None = None
    current: list[str] = []
    index = 0
    while index < len(text):
        pair = text[index : index + 2]
        if state is None and pair in ("[-", "{+"):
            if current:
                runs.append(("".join(current), None))
            current, state = [], (D if pair == "[-" else I)
            index += 2
            continue
        if state is not None and pair == ("-]" if state == D else "+}"):
            assert current, text
            runs.append(("".join(current), state))
            current, state = [], None
            index += 2
            continue
        current.append(text[index])
        index += 1
    assert state is None, text
    if current:
        runs.append(("".join(current), None))
    return runs


def _read_back(runs: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    return [
        (character, state) for run, state in runs for character in run if not character.isspace()
    ]


def _expected_marks(raw: str, states: list[str | None]) -> list[tuple[str, str | None]]:
    return [
        (character, state)
        for character, state in zip(raw, states, strict=True)
        if not character.isspace() and character not in ZERO_WIDTH
    ]


def _tokens_spelled_in_one_stretch(raw: str, states: list[str | None]) -> tuple[str, ...]:
    """Oracle for ``delimiters_in_text``, from the input alone.

    Two visible characters end up next to each other, with no delimiter between
    them, when nothing but zero-width characters separates them and they have
    the same state.
    """
    visible = [
        (character, state)
        for character, state in zip(raw, states, strict=True)
        if character not in ZERO_WIDTH
    ]
    spelled = {
        first + second
        for (first, first_state), (second, second_state) in itertools.pairwise(visible)
        if first_state == second_state and not first.isspace() and not second.isspace()
    }
    return tuple(token for token in TOKENS if token in spelled)


def _naive_strip(text: str) -> str:
    """The strip on main: remove every occurrence of each token in turn."""
    for token in TOKENS:
        text = text.replace(token, "")
    return text


def _main_accepts(raw: str, rendered_text: str) -> bool:
    """Main's two checks: no token in the raw text, and its strip gives the text back."""
    return not any(token in raw for token in TOKENS) and _naive_strip(
        rendered_text
    ) == _normalize_text(raw)


def _ambiguous_run(runs: list[tuple[str, str | None]]) -> bool:
    return any(
        (state == D and run.endswith("[")) or (state == I and run.endswith("{"))
        for run, state in runs
    )


def _check_rendering(raw: str, states: list[str | None]) -> tuple[bool, bool]:
    """Assert invariants 1 to 4 for one input; return (readable, misread by the old strip)."""
    normalized = _normalize_text(raw)
    rendered = _render_amendment_markup(raw, states)
    case = (raw, states, rendered.text)

    assert rendered.delimiters_in_text == _tokens_spelled_in_one_stretch(raw, states), case
    readable = not rendered.delimiters_in_text
    if _main_accepts(raw, rendered.text):
        assert readable, case
    if not readable:
        return False, False
    runs = _amendment_markup_runs(rendered.text)
    assert runs == _oracle_runs(rendered.text), case
    assert _strip_amendment_markup(rendered.text) == normalized, case
    assert _read_back(runs) == _expected_marks(raw, states), case
    assert rendered.deleted_runs == sum(state == D for _run, state in runs), case
    assert rendered.inserted_runs == sum(state == I for _run, state in runs), case
    old_strip_holds = _naive_strip(rendered.text) == normalized
    if not any(token in normalized for token in TOKENS):
        assert old_strip_holds is not _ambiguous_run(runs), case
    return True, not old_strip_holds


@st.composite
def _marked_text(draw: st.DrawFn) -> tuple[str, list[str | None]]:
    pairs = draw(
        st.lists(st.tuples(st.sampled_from(_ALPHABET), st.sampled_from(_STATES)), max_size=40)
    )
    return "".join(character for character, _state in pairs), [state for _c, state in pairs]


# 1. Render then read back --------------------------------------------------------


@_SETTINGS
@given(_marked_text())
@example((MD_LINE, MD_STATES))
@example(("x{y", [I, I, None]))
@example(("[", [D]))
@example(("{", [I]))
@example(("[ [", [D, None, D]))
@example(("-[", [None, D]))
@example(("[" + ZWSP + "-", [I, None, None]))
@example(("[-", [I, None]))
@example(("-" + ZWSP + "]", [None, None, D]))
@example(("a[" + ZWSP + "-b", [None] * 5))
def test_property_rendered_markup_is_readable_and_main_compatible(
    case: tuple[str, list[str | None]],
) -> None:
    """Invariants 1 to 4."""
    _check_rendering(*case)


_SHORT_ALPHABET = ("a", "[", "]", "-", "{", "}", "+", " ", ZWSP, "\n")


def test_every_short_text_reads_back() -> None:
    """Invariants 1 to 4 for every text of up to 4 characters and every state assignment.

    A delimiter and the characters it can make a token with are at most four
    characters apart, so this covers every local arrangement; Hypothesis covers
    longer texts.
    """
    cases = unreadable = misread_by_the_old_strip = 0
    for size in range(5):
        for characters in itertools.product(_SHORT_ALPHABET, repeat=size):
            raw = "".join(characters)
            for states in itertools.product(_STATES, repeat=size):
                readable, misread = _check_rendering(raw, list(states))
                cases += 1
                unreadable += not readable
                misread_by_the_old_strip += misread
    assert (cases, unreadable, misread_by_the_old_strip) == (837931, 34890, 177612)


def test_a_struck_bracket_reads_as_struck_text() -> None:
    rendered = _render_amendment_markup(MD_LINE, MD_STATES)

    assert rendered.text == "the budget bill [-[-]shall[-] MAY-] specify"
    assert rendered.delimiters_in_text == ()
    assert _naive_strip(rendered.text) == "the budget bill ]shall] MAY specify"
    assert _strip_amendment_markup(rendered.text) == MD_LINE
    assert _amendment_markup_runs(rendered.text) == [
        ("the budget bill ", None),
        ("[", D),
        ("shall", None),
        ("] MAY", D),
        (" specify", None),
    ]


def test_an_underlined_brace_reads_as_underlined_text() -> None:
    rendered = _render_amendment_markup("x{y", [I, I, None])

    assert rendered.text == "{+x{+}y"
    assert _strip_amendment_markup(rendered.text) == "x{y"
    assert _amendment_markup_runs(rendered.text) == [("x{", I), ("y", None)]


@pytest.mark.parametrize(
    ("raw", "states", "text", "in_text"),
    [
        # A delimiter is written between the two characters: readable.
        ("[" + ZWSP + "-", [I, None, None], "{+[+}-", ()),
        ("[" + ZWSP + "-", [D, None, None], "[-[-]-", ()),
        ("-" + ZWSP + "]", [None, None, D], "-[-]-]", ()),
        ("[-", [I, None], "{+[+}-", ()),
        # The two characters are in one run or one plain stretch: not readable.
        ("a[" + ZWSP + "-b", [None] * 5, "a[-b", ("[-",)),
        ("a-" + ZWSP + "]b", [None] * 5, "a-]b", ("-]",)),
        ("x-" + ZWSP + "]y", [D] * 5, "[-x-]y-]", ("-]",)),
        ("{" + ZWSP + "+ +" + ZWSP + "}", [I] * 7, "{+{+ +}+}", ("{+", "+}")),
    ],
)
def test_delimiters_in_text_are_those_no_written_delimiter_splits(
    raw: str, states: list[str | None], text: str, in_text: tuple[str, ...]
) -> None:
    rendered = _render_amendment_markup(raw, states)

    assert rendered.text == text
    assert rendered.delimiters_in_text == in_text
    if not in_text:
        assert _strip_amendment_markup(rendered.text) == _normalize_text(raw)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("a [-b", r"opened at offset 2 is never closed"),
        ("a [--] b", r"run at offset 2 is empty"),
        ("a -] b", r"\['-\]'\] outside a run \(offsets 0 to 6\)"),
        ("a {+b+} c+}", r"\['\+\}'\] outside a run"),
        ("[-a [-b-]", r"\['\[-'\] inside a deleted run \(offsets 2 to 7\)"),
        ("{+a [-b+}", r"\['\[-'\] inside a inserted run"),
    ],
)
def test_text_the_renderer_did_not_write_is_refused(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _strip_amendment_markup(text)


def test_a_page_whose_markup_cannot_be_read_back_is_a_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = dataclasses.replace(_render_amendment_markup("ab", [D, None]), text="[-a")
    monkeypatch.setattr(documents_module, "_render_amendment_markup", lambda *_a, **_k: broken)

    with pytest.raises(RuntimeError, match=r"PDF page 7 cannot be read back: .* never closed"):
        _layered(_RuledPage([[("a", D), ("b", None)]]))


# 2. The layered path on a page with drawn rules ----------------------------------


class _RuledPage:
    """One text block whose characters carry the strike and underline rules drawn for them.

    ``lines`` holds each line's (character, state) pairs. Line ``k`` sits on
    baseline ``BASELINE + k * LINE_PITCH``; character ``i`` fills the cell from
    ``72 + i * CELL``. A struck character gets a short rule through its own cell
    at ``STRIKE_OFFSET`` font sizes from the baseline and an underlined one a
    rule at ``UNDERLINE_OFFSET``; whitespace gets none, as the classifier skips
    it. The plain text is PyMuPDF's printer on the same characters.
    """

    def __init__(self, lines: list[list[tuple[str, str | None]]]) -> None:
        self.lines = lines

    def raw(self) -> tuple[str, list[str | None]]:
        """The raw text and states the layered path reads off this page."""
        characters: list[str] = []
        states: list[str | None] = []
        for line in self.lines:
            for character, state in line:
                characters.append(character)
                states.append(None if character.isspace() else state)
            if line and line[-1][0] not in ("\n", "\x00"):
                characters.append("\n")
                states.append(None)
        return "".join(characters), states

    def get_text(self, option: str, *, flags: int = 0, sort: bool = False) -> Any:
        if option == "text":
            return self.raw()[0]
        assert option == "rawdict"
        lines = []
        for number, line in enumerate(self.lines):
            baseline = BASELINE + number * LINE_PITCH
            chars = [
                {
                    "c": character,
                    "bbox": (72 + CELL * index, baseline - 10, 72 + CELL * (index + 1), baseline + 2),
                    "origin": (72 + CELL * index, baseline),
                }
                for index, (character, _state) in enumerate(line)
            ]
            spans = [{"size": SIZE, "origin": (72, baseline), "chars": chars}] if chars else []
            lines.append({"spans": spans})
        return {"blocks": [{"type": 0, "lines": lines}]}

    def get_fonts(self, full: bool = False) -> list[Any]:
        return []

    def get_drawings(self) -> list[dict[str, Any]]:
        drawings = []
        for number, line in enumerate(self.lines):
            baseline = BASELINE + number * LINE_PITCH
            for index, (character, state) in enumerate(line):
                if state is None or character.isspace():
                    continue
                offset = STRIKE_OFFSET if state == D else UNDERLINE_OFFSET
                y = baseline + offset * SIZE
                x = 72 + CELL * index
                drawings.append(
                    {
                        "type": "s",
                        "color": (0.0, 0.0, 0.0),
                        "width": 0.6,
                        "stroke_opacity": 1.0,
                        "items": [("l", fitz.Point(x + 1, y), fitz.Point(x + CELL - 1, y))],
                    }
                )
        return drawings


def _layered(page: _RuledPage) -> tuple[str, dict[str, Any] | None]:
    extraction: dict[str, Any] = {"amendment_markup": True}
    with warnings.catch_warnings():
        warnings.simplefilter("error", PdfAmendmentMarkupWarning)
        return documents_module._pdf_page_layered_text(
            page,
            extraction=extraction,
            markup=documents_module._pdf_amendment_markup_config(extraction),
            page_number=7,
        )


def _line_case(text: str, states: list[str | None]) -> list[list[tuple[str, str | None]]]:
    return [list(zip(text, states, strict=True))]


_LINE_ALPHABET = ("a", "[", "]", "-", "{", "}", "+", " ", ZWSP, "\x1c")


@st.composite
def _ruled_lines(draw: st.DrawFn) -> list[list[tuple[str, str | None]]]:
    line = st.lists(
        st.tuples(st.sampled_from(_LINE_ALPHABET), st.sampled_from(_STATES)), max_size=12
    )
    return draw(st.lists(line, min_size=1, max_size=4))


@settings(max_examples=600, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_ruled_lines())
@example(_line_case("bill [shall] MAY", [None] * 5 + [D] + [None] * 5 + [D] * 5))
@example(_line_case("a[" + ZWSP + "-b", [None] * 5))
@example(_line_case("[" + ZWSP + "-", [I, None, None]))
@example(_line_case("a[-b", [None, I, None, None]))
def test_property_layered_markup_refuses_or_reads_back_and_accepts_what_main_accepts(
    lines: list[list[tuple[str, str | None]]],
) -> None:
    """Invariant 5."""
    page = _RuledPage(lines)
    raw, states = page.raw()
    default_text = _normalize_text(raw)
    rendered = _render_amendment_markup(raw, states)
    in_raw = [token for token in TOKENS if token in raw]
    in_text = _tokens_spelled_in_one_stretch(raw, states)

    if in_raw or in_text:
        assert not _main_accepts(raw, rendered.text)
        message = (
            f"PDF page 7 text already contains amendment markup delimiters {in_raw}"
            if in_raw
            else f"PDF page 7 text contains amendment markup delimiters {list(in_text)} "
            "once its zero-width characters are dropped"
        )
        with pytest.raises(ValueError, match=re.escape(message)):
            _layered(page)
        return
    text, metadata = _layered(page)

    assert text == rendered.text
    assert metadata is not None
    assert _strip_amendment_markup(text) == default_text
    runs = _oracle_runs(text)
    assert _amendment_markup_runs(text) == runs
    assert _read_back(runs) == _expected_marks(raw, states)
    assert metadata["deleted_runs"] == sum(state == D for _run, state in runs)
    assert metadata["inserted_runs"] == sum(state == I for _run, state in runs)


def test_a_delimiter_spelled_across_a_zero_width_character_is_refused_with_the_page_named() -> None:
    # Normalizing drops U+200B, so the page text reads "a[-b" and the markup
    # would hold a literal "[-". The raw text holds no token, so main rendered
    # it, removed the "[-" and failed with "amendment markup changed the text".
    page = _RuledPage(_line_case("a[" + ZWSP + "-b", [None] * 5))

    with pytest.raises(
        ValueError,
        match=r"PDF page 7 text contains amendment markup delimiters \['\[-'\] once its "
        r"zero-width characters are dropped; amendment_markup output would be ambiguous",
    ):
        _layered(page)


def test_a_delimiter_split_by_a_run_boundary_extracts_as_on_main() -> None:
    # The underlined "[" and the plain "-" spell "[-" once U+200B is dropped, but
    # the closer is written between them. Main accepts this page.
    page = _RuledPage(_line_case("[" + ZWSP + "-", [I, None, None]))
    raw, _states = page.raw()

    text, metadata = _layered(page)

    assert text == "{+[+}-"
    assert _main_accepts(raw, text)
    assert _strip_amendment_markup(text) == "[-"
    assert metadata is not None and metadata["inserted_runs"] == 1


def test_a_struck_bracket_before_a_zero_width_character_extracts() -> None:
    # Main read "[-[-]-" as "]-" and stopped; the run boundary keeps it readable.
    page = _RuledPage(_line_case("a[" + ZWSP + "-b", [None, D, None, None, None]))
    raw, _states = page.raw()

    text, _metadata = _layered(page)

    assert text == "a[-[-]-b"
    assert not _main_accepts(raw, text)
    assert _strip_amendment_markup(text) == "a[-b"


def test_a_typographic_underline_that_joins_a_spelled_delimiter_is_refused() -> None:
    # "A[" is underlined and the "-" after U+200B is plain, so the closer splits
    # "[-". Listing "A[" as a typographic underline removes its delimiters, and
    # the text then spells "[-" in one plain stretch.
    raw = "A[" + ZWSP + "-x"
    states: list[str | None] = [I, I, None, None, None]
    page = _RuledPage(_line_case(raw, states))

    assert _layered(page)[0] == "{+A[+}-x"
    rendered = _render_amendment_markup(raw + "\n", [*states, None], typographic_underlines=("A[",))
    assert rendered.text == "A[-x"
    assert rendered.typographic_underlines == {"A[": 1}
    assert rendered.delimiters_in_text == ("[-",)
    extraction: dict[str, Any] = {"amendment_markup": {"typographic_underlines": ["A["]}}
    with pytest.raises(
        ValueError,
        match=r"PDF page 7 text contains amendment markup delimiters \['\[-'\] once",
    ):
        documents_module._pdf_page_layered_text(
            page,
            extraction=extraction,
            markup=documents_module._pdf_amendment_markup_config(extraction),
            page_number=7,
        )


def test_a_delimiter_in_the_raw_text_is_refused_as_on_main() -> None:
    # Main refuses any token in the raw text, split by a run boundary or not.
    for states in ([None, None, None, None], [None, I, None, None]):
        with pytest.raises(
            ValueError,
            match=r"PDF page 7 text already contains amendment markup delimiters \['\[-'\]",
        ):
            _layered(_RuledPage(_line_case("a[-b", states)))


# 3. Real PDFs ---------------------------------------------------------------------


def _pdf_with_marked_parts(parts: list[tuple[str, str | None]]) -> bytes:
    """One line of text set part by part, each struck or underlined part with its own rule."""
    document = fitz.open()
    page = document.new_page()
    x = 72.0
    for text, state in parts:
        page.insert_text((x, BASELINE), text, fontname=FONT, fontsize=SIZE)
        width = fitz.get_text_length(text, fontname=FONT, fontsize=SIZE)
        if state is not None:
            y = BASELINE + (STRIKE_OFFSET if state == D else UNDERLINE_OFFSET) * SIZE
            page.draw_line((x, y), (x + width, y), width=0.6)
        x += width
    content = document.tobytes()
    document.close()
    return content


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (
            [("the budget bill ", None), ("[", D), ("shall", None), ("] MAY", D), (" specify", None)],
            "the budget bill [-[-]shall[-] MAY-] specify",
        ),
        ([("keep ", None), ("{", I), ("x", None)], "keep {+{+}x"),
        ([("keep ", None), ("new{", I), (" end", None)], "keep {+new{+} end"),
    ],
)
def test_a_pdf_with_a_run_ending_in_its_opening_bracket_marks_and_strips_back(
    parts: list[tuple[str, str | None]], expected: str
) -> None:
    content = _pdf_with_marked_parts(parts)

    plain = list(documents_module._extract_pdf_blocks(content, extraction={}))
    with warnings.catch_warnings():
        warnings.simplefilter("error", PdfAmendmentMarkupWarning)
        marked = list(
            documents_module._extract_pdf_blocks(content, extraction={"amendment_markup": True})
        )

    assert [block.body for block in marked] == [expected]
    assert [_strip_amendment_markup(block.body) for block in marked] == [
        block.body for block in plain
    ]


# The 12 Maryland pages the corpus-wide sweep found. Maryland prints a deletion
# in brackets and strikes out what an amendment struck from the bill (legend on
# 2022 HB 456, page 1), so its bill and session laws strike the brackets of a
# deletion that an amendment struck; the marks on these pages were checked
# against renderings.
_SWEPT_PAGES = [
    (
        "us-md/statute/2026-10-06-w6-benefits-statute-md/official-documents/"
        "us-md-statute-bills-2022-hb0456.pdf",
        (2,),
    ),
    (
        "us-md/statute/2026-10-06-w6-income-tax-statute-md/official-documents/"
        "us-md-statute-session-laws-2023-chapter-613.pdf",
        (2,),
    ),
    (
        "us-md/statute/2026-10-06-w6-tanf-ccdf-statutes-md/official-documents/"
        "us-md-w6-session-laws-2024-chapter-717.pdf",
        (37, 39, 44),
    ),
    (
        "us-md/statute/2026-10-06-w6-income-tax-statute-md/official-documents/"
        "us-md-statute-session-laws-2025-chapter-604.pdf",
        (87, 150, 162, 165, 166, 167, 168),
    ),
]
# Marked phrases read off renderings of the Maryland pages.
_MD_MARKED = {
    ("us-md-statute-bills-2022-hb0456.pdf", 2): "at least [-[-]62[-] 60-] years old",
    ("us-md-w6-session-laws-2024-chapter-717.pdf", 37): "from [-[-]2024[-] 2025-] through",
    ("us-md-statute-session-laws-2025-chapter-604.pdf", 87): (
        "the budget bill [-[-]shall[-] MAY-] specify"
    ),
    ("us-md-statute-session-laws-2025-chapter-604.pdf", 167): "(3) [-[-](i)[-]-] the standard",
}


@pytest.mark.parametrize(
    ("relative", "page_number"),
    [(relative, page) for relative, pages in _SWEPT_PAGES for page in pages],
)
def test_the_swept_pages_mark_and_strip_back_to_their_default_text(
    relative: str, page_number: int
) -> None:
    extraction: dict[str, Any] = {"amendment_markup": True}
    with fitz.open(SOURCES / relative) as document:
        page = document[page_number - 1]
        default_text = _normalize_text(documents_module._pdf_page_text(page, extraction={}))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PdfAmendmentMarkupWarning)
            text, metadata = documents_module._pdf_page_layered_text(
                page,
                extraction=extraction,
                markup=documents_module._pdf_amendment_markup_config(extraction),
                page_number=page_number,
            )

    runs = _amendment_markup_runs(text)
    assert runs == _oracle_runs(text)
    assert _strip_amendment_markup(text) == default_text
    # Each page has a run that the old strip misread.
    assert _naive_strip(text) != default_text
    assert _ambiguous_run(runs)
    assert metadata is not None
    assert metadata["deleted_runs"] == sum(state == D for _run, state in runs)
    assert metadata["inserted_runs"] == sum(state == I for _run, state in runs)
    phrase = _MD_MARKED.get((Path(relative).name, page_number))
    if phrase is not None:
        assert phrase in text


def test_a_marked_page_range_of_a_maryland_session_law_extracts() -> None:
    content = MD_2025_CH_604.read_bytes()
    plain = list(documents_module._extract_pdf_blocks(content, extraction={}))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PdfAmendmentMarkupWarning)
        marked = list(
            documents_module._extract_pdf_blocks(
                content, extraction={"amendment_markup": {"start_page": 87, "end_page": 87}}
            )
        )

    assert [_strip_amendment_markup(block.body) for block in marked] == [
        block.body for block in plain
    ]
    page_87 = next(block for block in marked if block.metadata["page_number"] == 87)
    assert "the budget bill [-[-]shall[-] MAY-] specify" in page_87.body
    assert page_87.metadata["amendment_markup"]["deleted_runs"] == 5
