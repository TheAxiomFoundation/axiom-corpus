"""Reading amendment markup back.

``_render_amendment_markup`` writes GNU wdiff delimiters around struck
(``[-...-]``) and underlined (``{+...+}``) runs. A run whose last character and
its closer make a token cannot be read by removing every occurrence of the four
tokens: a struck run ending in "[" is written ``[-[-]`` and an underlined run
ending in "{" is written ``{+{+}``, and the old ``str.replace`` strip took the
run's own "[" with the closer's "-", turning "[" into "]". A sweep of every
retained PDF found 22 such pages, which ``_pdf_page_layered_text`` stopped with
"amendment markup changed the text": Maryland session laws and a bill, which
strike the brackets of a stricken deletion, and CMS state plan approval
packages. ``_amendment_markup_runs`` reads the delimiters left to right instead.

Invariants (Hypothesis):

1. For any raw text and states whose normalized text holds none of the four
   tokens, reading the rendered markup back gives the normalized text, every
   visible character's state, and the run counts the renderer reports.
2. Removing every token occurrence gives the same text exactly when no struck
   run ends in "[" and no underlined run ends in "{". So the reader agrees with
   the old strip on every page the old strip passed.
3. ``_pdf_page_layered_text`` on a page with drawn strike and underline rules
   refuses with a ValueError naming the page exactly when the normalized page
   text holds a token, and otherwise returns markup that reads back to the
   default page text and to the drawn states.

Invariants 1 and 2 are also checked for every text of up to four characters.

The reader is checked against an independent character-by-character oracle
(``_oracle_runs``).
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
from hypothesis import HealthCheck, assume, example, given, settings
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
ZERO_WIDTH = ("​", "﻿")
FONT = "helv"
SIZE = 12.0
BASELINE = 100.0
LINE_PITCH = 30.0
CELL = 6.0
STRIKE_OFFSET = -0.25
UNDERLINE_OFFSET = 0.13

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


def _naive_strip(text: str) -> str:
    """The strip before this fix: remove every occurrence of each token in turn."""
    for token in TOKENS:
        text = text.replace(token, "")
    return text


def _ambiguous_run(runs: list[tuple[str, str | None]]) -> bool:
    return any(
        (state == D and run.endswith("[")) or (state == I and run.endswith("{"))
        for run, state in runs
    )


@st.composite
def _marked_text(draw: st.DrawFn) -> tuple[str, list[str | None]]:
    pairs = draw(
        st.lists(st.tuples(st.sampled_from(_ALPHABET), st.sampled_from(_STATES)), max_size=40)
    )
    return "".join(character for character, _state in pairs), [state for _c, state in pairs]


# 1. Render then read back --------------------------------------------------------


@_SETTINGS
@given(_marked_text())
@example(("the budget bill [shall] MAY specify", [None] * 16 + [D] + [None] * 5 + [D] * 5 + [None] * 8))
@example(("x{y", [I, I, None]))
@example(("[", [D]))
@example(("{", [I]))
@example(("[ [", [D, None, D]))
def test_property_markup_reads_back_to_the_normalized_text_and_states(
    case: tuple[str, list[str | None]],
) -> None:
    raw, states = case
    normalized = _normalize_text(raw)
    assume(not any(token in normalized for token in TOKENS))
    rendered = _render_amendment_markup(raw, states)

    runs = _amendment_markup_runs(rendered.text)
    assert runs == _oracle_runs(rendered.text)
    assert _strip_amendment_markup(rendered.text) == normalized
    assert _read_back(runs) == _expected_marks(raw, states)
    assert all(run for run, _state in runs)
    assert rendered.deleted_runs == sum(state == D for _run, state in runs)
    assert rendered.inserted_runs == sum(state == I for _run, state in runs)


@_SETTINGS
@given(_marked_text())
@example(("the budget bill [shall] MAY specify", [None] * 16 + [D] + [None] * 5 + [D] * 5 + [None] * 8))
@example(("a-]", [None, D, D]))
def test_property_the_old_strip_fails_exactly_on_a_run_ending_in_its_opening_bracket(
    case: tuple[str, list[str | None]],
) -> None:
    raw, states = case
    normalized = _normalize_text(raw)
    assume(not any(token in normalized for token in TOKENS))
    rendered = _render_amendment_markup(raw, states)

    old_strip_holds = _naive_strip(rendered.text) == normalized
    assert old_strip_holds is not _ambiguous_run(_oracle_runs(rendered.text)), rendered.text


_SHORT_ALPHABET = ("a", "[", "]", "-", "{", "}", "+", " ", "\u200b", "\n")


def test_every_short_text_reads_back() -> None:
    """Invariants 1 and 2 for every text of up to 4 characters and every state assignment.

    A delimiter and the characters it can make a token with are at most four
    characters apart, so this covers every local arrangement; Hypothesis covers
    longer texts.
    """
    cases = misread_by_the_old_strip = 0
    for size in range(5):
        for characters in itertools.product(_SHORT_ALPHABET, repeat=size):
            raw = "".join(characters)
            normalized = _normalize_text(raw)
            if any(token in normalized for token in TOKENS):
                continue
            for states in itertools.product(_STATES, repeat=size):
                rendered = _render_amendment_markup(raw, list(states))
                runs = _amendment_markup_runs(rendered.text)
                assert runs == _oracle_runs(rendered.text), (raw, states)
                assert _strip_amendment_markup(rendered.text) == normalized, (raw, states)
                assert _read_back(runs) == _expected_marks(raw, list(states)), (raw, states)
                ambiguous = _ambiguous_run(runs)
                assert (_naive_strip(rendered.text) == normalized) is not ambiguous, (raw, states)
                cases += 1
                misread_by_the_old_strip += ambiguous
    assert (cases, misread_by_the_old_strip) == (736537, 143454)


def test_a_struck_bracket_reads_as_struck_text() -> None:
    raw = "the budget bill [shall] MAY specify"
    states = [None] * 16 + [D] + [None] * 5 + [D] * 5 + [None] * 8

    rendered = _render_amendment_markup(raw, states)

    assert rendered.text == "the budget bill [-[-]shall[-] MAY-] specify"
    assert _naive_strip(rendered.text) == "the budget bill ]shall] MAY specify"
    assert _strip_amendment_markup(rendered.text) == raw
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

    def get_text(self, option: str, *, flags: int = 0, sort: bool = False) -> Any:
        if option == "text":
            out: list[str] = []
            for line in self.lines:
                out.extend(character for character, _state in line)
                if line and line[-1][0] not in ("\n", "\x00"):
                    out.append("\n")
            return "".join(out)
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


_LINE_ALPHABET = ("a", "[", "]", "-", "{", "}", "+", " ", "​", "\x1c")


@st.composite
def _ruled_lines(draw: st.DrawFn) -> list[list[tuple[str, str | None]]]:
    line = st.lists(
        st.tuples(st.sampled_from(_LINE_ALPHABET), st.sampled_from(_STATES)), max_size=12
    )
    return draw(st.lists(line, min_size=1, max_size=4))


@settings(max_examples=600, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_ruled_lines())
@example(_line_case("bill [shall] MAY", [None] * 5 + [D] + [None] * 5 + [D] * 5))
@example(_line_case("a[​-b", [None] * 5))
def test_property_layered_markup_refuses_tokens_or_reads_back_to_the_page(
    lines: list[list[tuple[str, str | None]]],
) -> None:
    page = _RuledPage(lines)
    default_text = _normalize_text(page.get_text("text"))
    present = [token for token in TOKENS if token in default_text]

    if present:
        with pytest.raises(
            ValueError,
            match="PDF page 7 text already contains amendment markup delimiters "
            + re.escape(str(present)),
        ):
            _layered(page)
        return
    text, metadata = _layered(page)

    assert metadata is not None
    assert _strip_amendment_markup(text) == default_text
    runs = _oracle_runs(text)
    assert _amendment_markup_runs(text) == runs
    drawn = [pair for line in lines for pair in line]
    assert _read_back(runs) == [
        (character, state)
        for character, state in drawn
        if not character.isspace() and character not in ZERO_WIDTH
    ]
    assert metadata["deleted_runs"] == sum(state == D for _run, state in runs)
    assert metadata["inserted_runs"] == sum(state == I for _run, state in runs)


def test_a_zero_width_character_inside_a_delimiter_is_refused_with_the_page_named() -> None:
    # Normalizing drops U+200B, so the page text reads "a[-b". Checking the raw
    # text missed it, and the old strip then removed the literal "[-".
    page = _RuledPage(_line_case("a[​-b", [None, D, None, None, None]))

    with pytest.raises(
        ValueError,
        match=r"PDF page 7 text already contains amendment markup delimiters \['\[-'\]",
    ):
        _layered(page)


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


# The 22 pages the corpus-wide sweep found. Maryland prints a deletion in brackets
# and strikes out what an amendment struck from the bill (legend on 2022 HB 456,
# page 1), so its bill and session laws strike the brackets of a deletion that an
# amendment struck; the marks on those 12 pages were checked against renderings.
# The CMS approval packages set their text in Type3 fonts whose character boxes
# are 135 to 240 pt tall, and rules 1.6 to 3 pt long fall at a strike or underline
# offset from them: the classifier's marks there are not amendments.
_SWEPT_PAGES = [
    (
        "us-az/policy/2026-09-13-chip-state-plan/official-documents/"
        "us-az-cms-chip-state-plan-spa-az-22-0007-approval-package.pdf",
        (94, 96),
    ),
    (
        "us-ca/policy/2026-09-13-medicaid-state-plan/official-documents/"
        "us-ca-cms-medicaid-state-plan-spa-ca-22-0036-approval-document.pdf",
        (11,),
    ),
    (
        "us-ca/policy/2026-09-13-medicaid-state-plan/official-documents/"
        "us-ca-cms-medicaid-state-plan-spa-ca-25-0037-approval-document.pdf",
        (26,),
    ),
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
    (
        "us-mi/policy/2026-09-13-medicaid-state-plan/official-documents/"
        "us-mi-cms-medicaid-state-plan-spa-mi-25-0101-approval-document.pdf",
        (5,),
    ),
    (
        "us-mo/policy/2026-09-13-medicaid-state-plan/official-documents/"
        "us-mo-cms-medicaid-state-plan-spa-mo-21-0032-approval-document.pdf",
        (17, 27),
    ),
    (
        "us-ms/policy/2026-09-13-medicaid-state-plan/official-documents/"
        "us-ms-cms-medicaid-state-plan-spa-ms-19-0018-approval-document.pdf",
        (37, 39),
    ),
    (
        "us-wi/policy/2026-09-13-medicaid-state-plan/official-documents/"
        "us-wi-cms-medicaid-state-plan-spa-wi-25-0006-a-approval-document.pdf",
        (2,),
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
