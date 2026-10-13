"""Hardening of the opt-in PDF amendment-markup keys (axiom-corpus#741).

Example tests pin each fix: the layered path's newlines, the check against the
default page text, invisible and near-threshold rules, typographic underlines,
and the configuration checks. Property tests state the invariants the layered
path keeps for every input. They run exhaustively over short inputs and over a
seeded sample of longer ones; the repository has no Hypothesis.

1. Faithful markup: reading the delimiters back gives each visible character's
   state, and removing them gives ``_normalize_text`` of the raw text.
2. The layered text equals PyMuPDF's plain-text printer, modelled line by line.
3. ``typographic_underlines`` only removes insertion marks, only inside an
   occurrence that is exactly an underlined stretch, and does not depend on the
   order of the phrases.
"""

from __future__ import annotations

import itertools
import random
import warnings
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import (
    PdfAmendmentMarkupWarning,
    _normalize_text,
    _render_amendment_markup,
    _strip_amendment_markup,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = REPO_ROOT / "data" / "corpus" / "sources"
AZ_CCAP_PDF = (
    SOURCES
    / "us-az/manual/2026-06-25-az-ccap/official-documents/az-des-ccap-reimbursement-rates.pdf"
)
WA_HCA_PDF = (
    SOURCES
    / "us-wa/guidance/2026-09-14-msp-income-standards/official-documents"
    / "us-wa-hca-income-and-resource-standards-2026-07-01.pdf"
)
MO_1040ES_PDF = (
    SOURCES
    / "us-mo/statute/2026-07-16-pit-central-us-mo-143/missouri-department-of-revenue"
    / "2026-form-mo-1040es.pdf"
)

D = "deleted"
I = "inserted"  # noqa: E741
FONT = "helv"
SIZE = 12.0
BASELINE = 100.0


def _pages(content: bytes, extraction: dict[str, Any]) -> list[Any]:
    return list(documents_module._extract_pdf_blocks(content, extraction=extraction))


def _pdf_with_rule(
    text: str,
    *,
    offset: float | None = None,
    thickness: float = 0.6,
    stroke_opacity: float = 1.0,
    fill_opacity: float = 1.0,
    filled: bool = False,
) -> bytes:
    """One line of text with a horizontal rule ``offset`` font sizes below its baseline."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, BASELINE), text, fontname=FONT, fontsize=SIZE)
    width = fitz.get_text_length(text, fontname=FONT, fontsize=SIZE)
    if offset is not None:
        y = BASELINE + offset * SIZE
        if filled:
            page.draw_rect(
                fitz.Rect(72, y - thickness / 2, 72 + width, y + thickness / 2),
                color=None,
                fill=(0, 0, 0),
                fill_opacity=fill_opacity,
            )
        else:
            page.draw_line((72, y), (72 + width, y), width=thickness, stroke_opacity=stroke_opacity)
    content = document.tobytes()
    document.close()
    return content


def _no_warnings(content: bytes, extraction: dict[str, Any]) -> list[Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("error", PdfAmendmentMarkupWarning)
        return _pages(content, extraction)


# 1. The layered path's newlines ------------------------------------------------


class _FakePage:
    """A page whose character layer and plain text are given directly.

    ``blocks`` is a list of text blocks, each a list of lines, each a string of
    characters. The plain text is PyMuPDF's printer applied to the same
    characters (``_printer_text``), unless ``text`` overrides it.
    """

    def __init__(self, blocks: list[list[str]], *, text: str | None = None) -> None:
        self.blocks = blocks
        self.text = _printer_text(blocks) if text is None else text

    def get_text(self, option: str, *, flags: int = 0, sort: bool = False) -> Any:
        if option == "text":
            return self.text
        assert option == "rawdict"
        raw_blocks = []
        for block in self.blocks:
            lines = []
            for line in block:
                chars = [
                    {
                        "c": character,
                        "bbox": (72 + 6 * index, 90.0, 78 + 6 * index, 102.0),
                        "origin": (72 + 6 * index, BASELINE),
                    }
                    for index, character in enumerate(line)
                ]
                spans = [{"size": SIZE, "origin": (72, BASELINE), "chars": chars}] if chars else []
                lines.append({"spans": spans})
            raw_blocks.append({"type": 0, "lines": lines})
        return {"blocks": raw_blocks}

    def get_drawings(self) -> list[Any]:
        return []


def _printer_text(blocks: list[list[str]]) -> str:
    """PyMuPDF's plain-text printer (``JM_print_stext_page_as_text``) on given lines.

    After each line it appends a newline when the line printed a character whose
    code point is neither 10 (newline) nor 0.
    """
    out: list[str] = []
    for block in blocks:
        for line in block:
            last_char = 0
            for character in line:
                out.append(character)
                last_char = ord(character)
            if last_char != 10 and last_char > 0:
                out.append("\n")
    return "".join(out)


def _layered(page: _FakePage, *, sort_blocks: bool = False) -> str:
    extraction: dict[str, Any] = {"amendment_markup": True}
    if sort_blocks:
        extraction["sort_blocks"] = True
    text, _metadata = documents_module._pdf_page_layered_text(
        page,
        extraction=extraction,
        markup=documents_module._pdf_amendment_markup_config(extraction),
        page_number=1,
    )
    return text


def test_a_line_that_ends_in_a_newline_gets_no_second_one() -> None:
    # "Summer Daily Rate/" ends in its own newline in the AZ CCAP rate table; a
    # second newline would split the cell into two paragraphs.
    page = _FakePage([["Summer Daily Rate/\n", "School-Year Daily Rate*"]])

    assert _layered(page) == "Summer Daily Rate/ School-Year Daily Rate*"


def test_empty_lines_add_no_newline() -> None:
    page = _FakePage([["first", "", "second"], ["", "third"]])

    assert _layered(page) == "first second third"


def test_the_layered_text_must_equal_the_default_page_text() -> None:
    # A glyph the plain-text printer keeps but the character layer leaves out
    # (PyMuPDF drops zero-width glyphs from rawdict).
    page = _FakePage([["$", "Your Name"]], text="$.\nYour Name\n")

    with pytest.raises(
        ValueError, match=r"differs from the page's default text \(missing U\+002E\)"
    ):
        _layered(page)


def test_sort_blocks_must_keep_the_default_page_characters() -> None:
    page = _FakePage([["second"], ["first"]], text="second\nfirst\nextra\n")

    with pytest.raises(
        ValueError, match="missing U\\+0061, U\\+0065, U\\+0072, U\\+0074, U\\+0078"
    ):
        _layered(page, sort_blocks=True)


_LINE_ALPHABET = ("a", "b", " ", "\n", "\x00")


def _random_blocks(rng: random.Random) -> list[list[str]]:
    return [
        [
            "".join(rng.choice(_LINE_ALPHABET) for _ in range(rng.randrange(0, 6)))
            for _ in range(rng.randrange(0, 5))
        ]
        for _ in range(rng.randrange(1, 4))
    ]


def _all_single_block_pages() -> list[list[list[str]]]:
    lines = [
        "".join(chars) for size in range(3) for chars in itertools.product("a\n ", repeat=size)
    ]
    return [
        [list(block)] for size in range(1, 4) for block in itertools.product(lines, repeat=size)
    ]


def test_property_layered_text_matches_the_plain_text_printer() -> None:
    """Invariant 2: for every line structure, layered text == normalized printer text."""
    rng = random.Random(741)
    cases = _all_single_block_pages() + [_random_blocks(rng) for _ in range(2000)]
    for blocks in cases:
        page = _FakePage(blocks)
        assert _layered(page) == _normalize_text(page.text), blocks
        assert _layered(page, sort_blocks=True) == _normalize_text(page.text), blocks


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (AZ_CCAP_PDF, {1: "Summer Daily Rate/ School-Year Daily Rate*"}),
        (WA_HCA_PDF, {1: "215% FPL - Children (N11/N31)", 2: "except in 11+) Alternate"}),
    ],
)
def test_marked_pages_strip_back_to_the_default_text_in_the_cited_pdfs(
    path: Path, expected: dict[int, str]
) -> None:
    content = path.read_bytes()
    plain = _pages(content, {})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PdfAmendmentMarkupWarning)
        marked = _pages(content, {"amendment_markup": True})

    assert [block.metadata["page_number"] for block in marked] == [
        block.metadata["page_number"] for block in plain
    ]
    for marked_block, plain_block in zip(marked, plain, strict=True):
        assert _strip_amendment_markup(marked_block.body) == plain_block.body
    for page_number, phrase in expected.items():
        assert phrase in _strip_amendment_markup(marked[page_number - 1].body)


def test_a_zero_width_glyph_stops_marked_extraction_with_the_page_named() -> None:
    content = MO_1040ES_PDF.read_bytes()

    with pytest.raises(ValueError, match=r"PDF page 1: the character layer .* \(missing U\+002E\)"):
        _pages(content, {"amendment_markup": True})
    # The default extraction keeps the zero-width period.
    assert "$." in _pages(content, {})[0].body


def test_pages_outside_the_marked_range_use_the_default_text() -> None:
    content = MO_1040ES_PDF.read_bytes()
    plain = _pages(content, {})

    # Pages 1 and 3 hold zero-width glyphs; marking only page 2 keeps them.
    marked = _pages(content, {"amendment_markup": {"start_page": 2, "end_page": 2}})

    assert [_strip_amendment_markup(block.body) for block in marked] == [
        block.body for block in plain
    ]
    assert [
        block.body == plain_block.body for block, plain_block in zip(marked, plain, strict=True)
    ] == [
        True,
        False,
        True,
    ]
    assert ["amendment_markup" in block.metadata for block in marked] == [False, True, False]


# 2. Configuration ----------------------------------------------------------------


def test_amendment_markup_false_is_the_default_extraction() -> None:
    content = _pdf_with_rule("underlined", offset=0.12)

    assert _pages(content, {"amendment_markup": False}) == _pages(content, {})


@pytest.mark.parametrize("key", ["sort_blocks", "ignore_actual_text"])
@pytest.mark.parametrize("value", ["true", 1, {}])
def test_boolean_keys_reject_other_values(key: str, value: Any) -> None:
    content = _pdf_with_rule("text")

    with pytest.raises(ValueError, match=f"{key} must be true or false"):
        _pages(content, {key: value})


@pytest.mark.parametrize("segmentation", ["single_block", "numbered_sections", "labeled_sections"])
def test_ignore_actual_text_is_checked_with_every_segmentation(segmentation: str) -> None:
    content = _pdf_with_rule("text")

    with pytest.raises(ValueError, match="ignore_actual_text must be true or false"):
        _pages(content, {"ignore_actual_text": "yes", "segmentation": segmentation})


# 3. Classifier hardening -------------------------------------------------------


def test_a_rule_with_zero_stroke_opacity_is_not_a_strike() -> None:
    content = _pdf_with_rule("plain", offset=-0.25, stroke_opacity=0.0)

    (page,) = _no_warnings(content, {"amendment_markup": True})

    assert page.body == "plain"
    assert page.metadata["amendment_markup"]["deleted_runs"] == 0


def test_a_rule_with_zero_fill_opacity_is_not_an_underline() -> None:
    content = _pdf_with_rule("plain", offset=0.12, filled=True, fill_opacity=0.0)

    (page,) = _no_warnings(content, {"amendment_markup": True})

    assert page.body == "plain"


def test_visible_rules_still_mark_text_without_warnings() -> None:
    struck = _pdf_with_rule("old", offset=-0.25)
    underlined = _pdf_with_rule("new", offset=0.12, filled=True)

    assert _no_warnings(struck, {"amendment_markup": True})[0].body == "[-old-]"
    assert _no_warnings(underlined, {"amendment_markup": True})[0].body == "{+new+}"


@pytest.mark.parametrize(
    ("offset", "body"),
    [
        (0.21, "{+edge+}"),  # just inside the underline range
        (0.24, "edge"),  # just outside it
        (-0.11, "[-edge-]"),
        (-0.42, "edge"),
    ],
)
def test_near_threshold_rules_warn_and_keep_their_classification(offset: float, body: str) -> None:
    content = _pdf_with_rule("edge", offset=offset, thickness=0.3)

    with pytest.warns(
        PdfAmendmentMarkupWarning, match="PDF page 1: 4 characters have a rule within"
    ):
        (page,) = _pages(content, {"amendment_markup": True})

    assert page.body == body


def test_a_thick_rule_at_an_underline_position_warns_and_is_ignored() -> None:
    content = _pdf_with_rule("heavy", offset=0.12, thickness=2.0, filled=True)

    with pytest.warns(PdfAmendmentMarkupWarning, match=r"rule thicker than 1.5 pt \(2.00 pt\)"):
        (page,) = _pages(content, {"amendment_markup": True})

    assert page.body == "heavy"


def test_a_stroked_rectangle_counts_its_stroke_in_its_thickness() -> None:
    # 1 pt high and stroked 1 pt wide: 2 pt of paint, though each number alone
    # is under the 1.5 pt limit.
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, BASELINE), "boxed", fontname=FONT, fontsize=SIZE)
    width = fitz.get_text_length("boxed", fontname=FONT, fontsize=SIZE)
    page.draw_rect(
        fitz.Rect(72, BASELINE + 0.9, 72 + width, BASELINE + 1.9), color=(0, 0, 0), width=1.0
    )

    with pytest.warns(PdfAmendmentMarkupWarning, match=r"thicker than 1.5 pt \(2.00 pt\)"):
        (block,) = _pages(document.tobytes(), {"amendment_markup": True})

    assert block.body == "boxed"


def test_rules_thicker_than_the_warning_limit_are_ignored_quietly() -> None:
    content = _pdf_with_rule("boxed", offset=0.12, thickness=4.0, filled=True)

    assert _no_warnings(content, {"amendment_markup": True})[0].body == "boxed"


def test_unmarked_extraction_never_warns() -> None:
    content = _pdf_with_rule("edge", offset=0.21, thickness=0.3)

    assert _no_warnings(content, {})[0].body == "edge"
    assert _no_warnings(content, {"sort_blocks": True})[0].body == "edge"


# 4. Typographic underlines -------------------------------------------------------


def _states(words: list[tuple[str, str | None]]) -> tuple[str, list[str | None]]:
    """Raw text and per-character states for space-separated (word, state) pairs."""
    text: list[str] = []
    states: list[str | None] = []
    for index, (word, state) in enumerate(words):
        if index:
            text.append(" ")
            states.append(None)
        text.extend(word)
        states.extend([state] * len(word))
    return "".join(text), states


def test_a_typographic_phrase_counts_only_where_it_is_underlined() -> None:
    raw, states = _states([("Jones", None), ("v.", None), ("Yeutter", None), ("again", I)])

    rendered = _render_amendment_markup(raw, states, typographic_underlines=("Jones v. Yeutter",))

    assert rendered.text == "Jones v. Yeutter {+again+}"
    assert rendered.typographic_underlines == {"Jones v. Yeutter": 0}
    assert rendered.typographic_underlines_kept == {"Jones v. Yeutter": 0}


def test_a_typographic_phrase_inside_an_inserted_paragraph_stays_inserted() -> None:
    raw, states = _states(
        [("order", I), ("in", I), ("Jones", I), ("v.", I), ("Yeutter", I), ("applies", I)]
    )

    rendered = _render_amendment_markup(raw, states, typographic_underlines=("Jones v. Yeutter",))

    assert rendered.text == "{+order in Jones v. Yeutter applies+}"
    assert rendered.typographic_underlines == {"Jones v. Yeutter": 0}
    assert rendered.typographic_underlines_kept == {"Jones v. Yeutter": 1}


def test_a_partly_underlined_phrase_keeps_its_marks() -> None:
    raw, states = _states([("in", None), ("Jones", I), ("v.", None), ("Yeutter", None)])

    rendered = _render_amendment_markup(raw, states, typographic_underlines=("Jones v. Yeutter",))

    assert rendered.text == "in {+Jones+} v. Yeutter"
    assert rendered.typographic_underlines_kept == {"Jones v. Yeutter": 1}


def test_an_exact_underlined_stretch_with_plain_inner_words_is_typographic() -> None:
    raw, states = _states(
        [("in", None), ("Hamilton", I), ("v.", None), ("Lyng;", I), ("and", None), ("new", I)]
    )

    rendered = _render_amendment_markup(raw, states, typographic_underlines=("Hamilton v. Lyng;",))

    assert rendered.text == "in Hamilton v. Lyng; and {+new+}"
    assert rendered.typographic_underlines == {"Hamilton v. Lyng;": 1}
    assert rendered.inserted_runs == 1


def test_the_phrase_must_reach_the_end_of_the_underlined_stretch() -> None:
    # "Lyng;" is underlined through its semicolon, so "Hamilton v. Lyng" stops
    # short of the stretch.
    raw, states = _states([("in", None), ("Hamilton", I), ("v.", None), ("Lyng;", I)])

    rendered = _render_amendment_markup(raw, states, typographic_underlines=("Hamilton v. Lyng",))

    assert rendered.typographic_underlines == {"Hamilton v. Lyng": 0}
    assert "{+Hamilton+}" in rendered.text


def test_overlapping_occurrences_of_a_phrase_are_each_judged() -> None:
    raw, states = _states(
        [("Jones", I), ("v.", None), ("Jones", I), ("v.", None), ("Jones", I), ("ends", None)]
    )

    rendered = _render_amendment_markup(raw, states, typographic_underlines=("Jones v. Jones",))

    assert rendered.text == "Jones v. Jones v. Jones ends"
    assert rendered.typographic_underlines == {"Jones v. Jones": 2}


def test_a_phrase_found_only_inside_an_insertion_fails_extraction() -> None:
    document = fitz.open()
    page = document.new_page()
    text = "new rule citing Jones v. Yeutter"
    page.insert_text((72, BASELINE), text, fontname=FONT, fontsize=SIZE)
    width = fitz.get_text_length(text, fontname=FONT, fontsize=SIZE)
    page.draw_rect(
        fitz.Rect(72, BASELINE + 1.2, 72 + width, BASELINE + 1.8), color=None, fill=(0, 0, 0)
    )

    with (
        pytest.warns(PdfAmendmentMarkupWarning, match="inside a longer underlined stretch"),
        pytest.raises(ValueError, match="not found as an underlined stretch"),
    ):
        _pages(
            document.tobytes(),
            {"amendment_markup": {"typographic_underlines": ["Jones v. Yeutter"]}},
        )


# Property tests ------------------------------------------------------------------


def _read_marked(text: str) -> list[tuple[str, str | None]]:
    """Return (character, state) for every non-space character of wdiff-marked text.

    Asserts that delimiters are balanced, never nested, never empty and never
    have whitespace just inside them.
    """
    out: list[tuple[str, str | None]] = []
    state: str | None = None
    opened_at = -1
    index = 0
    while index < len(text):
        token = text[index : index + 2]
        if token in ("[-", "{+"):
            assert state is None, text
            state = D if token == "[-" else I
            opened_at = len(out)
            assert not text[index + 2 : index + 3].isspace(), text
            index += 2
            continue
        if token in ("-]", "+}"):
            assert state == (D if token == "-]" else I), text
            assert len(out) > opened_at, text
            assert not text[index - 1 : index].isspace(), text
            state = None
            index += 2
            continue
        if not text[index].isspace():
            out.append((text[index], state))
        index += 1
    assert state is None, text
    return out


_RENDER_ALPHABET = ("a", "b", " ", "\n", "\r", "​")
_STATES: tuple[str | None, ...] = (None, D, I)


def _expected_marks(raw: str, states: list[str | None]) -> list[tuple[str, str | None]]:
    return [
        (character, state)
        for character, state in zip(raw, states, strict=True)
        if not character.isspace() and character not in {"​", "﻿"}
    ]


def _render_cases(rng: random.Random) -> list[tuple[str, list[str | None]]]:
    cases: list[tuple[str, list[str | None]]] = []
    for size in range(5):
        for chars in itertools.product(_RENDER_ALPHABET, repeat=size):
            for states in itertools.product(_STATES, repeat=size):
                cases.append(("".join(chars), list(states)))
    for _ in range(3000):
        size = rng.randrange(5, 60)
        cases.append(
            (
                "".join(rng.choice(_RENDER_ALPHABET) for _ in range(size)),
                [rng.choice(_STATES) for _ in range(size)],
            )
        )
    return cases


def test_property_markup_is_faithful_and_strips_to_the_normalized_text() -> None:
    """Invariant 1, exhaustive to length 4 and on 3,000 seeded longer inputs."""
    for raw, states in _render_cases(random.Random(1741)):
        rendered = _render_amendment_markup(raw, states)
        assert _strip_amendment_markup(rendered.text) == _normalize_text(raw), (raw, states)
        assert _read_marked(rendered.text) == _expected_marks(raw, states), (raw, states)
        assert rendered.deleted_runs == rendered.text.count("[-")
        assert rendered.inserted_runs == rendered.text.count("{+")


_WORDS = ("Jones", "v.", "Yeutter", "x", "y")
_PHRASES = ("Jones v. Yeutter", "Jones", "v.", "x y", "Yeutter x", "Jones v. Jones", "x x")


def _is_exact_underlined_stretch(raw: str, states: list[str | None], start: int, end: int) -> bool:
    """Oracle: raw[start:end] begins and ends underlined, and its visible neighbours are not."""
    visible = [index for index, character in enumerate(raw) if character != " "]
    inside = [index for index in visible if start <= index < end]
    before = [index for index in visible if index < start]
    after = [index for index in visible if index >= end]
    return (
        bool(inside)
        and states[inside[0]] == I
        and states[inside[-1]] == I
        and (not before or states[before[-1]] != I)
        and (not after or states[after[0]] != I)
    )


def _qualifying_starts(raw: str, states: list[str | None], phrase: str) -> list[int]:
    return [
        start
        for start in range(len(raw) - len(phrase) + 1)
        if raw.startswith(phrase, start)
        and _is_exact_underlined_stretch(raw, states, start, start + len(phrase))
    ]


def test_property_typographic_underlines_only_clear_exact_underlined_stretches() -> None:
    """Invariant 3 on 4,000 seeded paragraphs of case-name-like words."""
    rng = random.Random(2741)
    for _ in range(4000):
        words = [
            (
                rng.choice(_WORDS),
                rng.choice((None, None, I, I, D)),
            )
            for _ in range(rng.randrange(1, 9))
        ]
        raw, states = _states(words)
        if rng.random() < 0.3:  # mixed states inside a word
            states = [rng.choice(_STATES) if char != " " else None for char in raw]
        phrases = tuple(rng.sample(_PHRASES, rng.randrange(1, 4)))
        plain = _render_amendment_markup(raw, states)
        typographic = _render_amendment_markup(raw, states, typographic_underlines=phrases)
        reordered = _render_amendment_markup(raw, states, typographic_underlines=phrases[::-1])

        assert reordered.text == typographic.text
        assert _strip_amendment_markup(typographic.text) == _strip_amendment_markup(plain.text)
        before = _read_marked(plain.text)
        after = _read_marked(typographic.text)
        covered = {
            position
            for phrase in phrases
            for start in _qualifying_starts(raw, states, phrase)
            for position in range(start, start + len(phrase))
        }
        visible = [position for position, character in enumerate(raw) if character != " "]
        for position, (old, new) in zip(visible, zip(before, after, strict=True), strict=True):
            # Exactly the inserted characters inside a qualifying occurrence turn plain.
            expected = None if old[1] == I and position in covered else old[1]
            assert new == (old[0], expected), (raw, states, phrases, position)
        for phrase in phrases:
            starts = [
                start
                for start in range(len(raw) - len(phrase) + 1)
                if raw.startswith(phrase, start)
            ]
            qualifying = _qualifying_starts(raw, states, phrase)
            kept = [
                start
                for start in starts
                if start not in qualifying and I in states[start : start + len(phrase)]
            ]
            assert typographic.typographic_underlines[phrase] == len(qualifying), (raw, phrase)
            assert typographic.typographic_underlines_kept[phrase] == len(kept), (raw, phrase)
