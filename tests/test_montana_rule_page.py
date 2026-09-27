"""Tests for reading an ARM rule from a rules.mt.gov react-pdf text layer.

The property tests draw rule documents from a seeded generator, lay them out
the way the rules.mt.gov PDF text layer does (absolutely positioned spans,
wrapped lines, page breaks, two-column tables with wrapped cells) and require
the parser to give back exactly the lines the document was made of. They use
``random.Random`` with fixed seeds rather than Hypothesis, which is not a
dependency of this repository.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass, field
from html import escape

import pytest

from axiom_corpus.corpus.montana_rule_page import (
    MontanaRulePageError,
    join_wrapped,
    parse_montana_rule_document,
    text_layer_lines,
)

PITCH = 1.85
ROW_GAP = 2.42
PAGE_TOP = 4.78
PAGE_BOTTOM = 93.0


# --- join_wrapped -----------------------------------------------------------


@pytest.mark.parametrize(
    ("parts", "numeral_wrap", "expected"),
    [
        (
            ["TANF cash assistance Post-", "Employment Program"],
            False,
            "TANF cash assistance Post-Employment Program",
        ),
        (["POST-", "EMPLOYMENT"], False, "POST-EMPLOYMENT"),
        (["income -", "joint"], False, "income - joint"),
        (["53-4-", "212, MCA"], False, "53-4-212, MCA"),
        (["pages 2424-", "2626"], False, "pages 2424-2626"),
        (["TANF-", "(a)"], False, "TANF- (a)"),
        (["AMD, 2002 MAR p.", "1771, Eff. 6/28/02"], False, "AMD, 2002 MAR p. 1771, Eff. 6/28/02"),
        (["$ 37", "5"], True, "$ 375"),
        (["$ 37", "5"], False, "$ 37 5"),
        (["1,", "178"], True, "1,178"),
        (["1st", "Month"], True, "1st Month"),
        (["$", "375"], True, "$ 375"),
        (["  ", "a\xa0 b ", ""], False, "a b"),
    ],
)
def test_join_wrapped(parts: list[str], numeral_wrap: bool, expected: str) -> None:
    assert join_wrapped(parts, numeral_wrap=numeral_wrap) == expected


def _non_space(text: str) -> str:
    return re.sub(r"\s+", "", text)


@pytest.mark.parametrize("seed", range(300))
def test_join_wrapped_keeps_every_character_in_order(seed: int) -> None:
    rng = random.Random(seed)
    alphabet = "ab-1,. $\xa0"
    parts = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6))) for _ in range(5)]
    joined = join_wrapped(parts, numeral_wrap=rng.random() < 0.5)
    assert _non_space(joined) == _non_space("".join(parts).replace("\xa0", " "))
    assert joined == joined.strip()
    assert "  " not in joined


# --- a synthetic rules.mt.gov page ------------------------------------------


@dataclass
class _Page:
    lines: list[list[tuple[float, float, str]]] = field(default_factory=list)


@dataclass
class _Layout:
    """Places spans on pages the way the rule PDF's text layer does."""

    pages: list[_Page] = field(default_factory=lambda: [_Page()])
    top: float = PAGE_TOP
    started: bool = False

    def advance(self, gap: float, *, need: float = 0.0) -> None:
        if not self.started:
            self.started = True
            return
        if self.top + gap + need > PAGE_BOTTOM:
            self.pages.append(_Page())
            self.top = PAGE_TOP
            return
        self.top += gap

    def line(self, segments: list[tuple[float, str]]) -> None:
        self.pages[-1].lines.append([(left, self.top, text) for left, text in segments])

    def html(self) -> bytes:
        pages = []
        for number, page in enumerate(self.pages, 1):
            spans = []
            for line in page.lines:
                for left, top, text in line:
                    spans.append(
                        f'<span dir="ltr" role="presentation" style="left: {left:.2f}%; '
                        f"top: {top:.2f}%; font-size: calc(var(--scale-factor)*12.00px); "
                        f'font-family: sans-serif;">{escape(text)}</span>'
                    )
                spans.append('<br role="presentation">')
            pages.append(
                f'<div class="react-pdf__Page" data-page-number="{number}">'
                '<canvas class="react-pdf__Page__canvas"></canvas>'
                '<div class="react-pdf__Page__textContent textLayer">'
                f'{"".join(spans)}<div class="endOfContent"></div></div></div>'
            )
        return (
            "<html><body><nav>Skip to main content</nav>"
            f'<div class="react-pdf__Document">{"".join(pages)}</div>'
            "<footer>Contact Us</footer></body></html>"
        ).encode()


_SYLLABLES = ("an", "ce", "di", "for", "in", "ma", "ne", "or", "pro", "sta", "te", "un")


def _word(rng: random.Random, *, upper: bool = False) -> str:
    roll = rng.random()
    if roll < 0.08:
        word = f"{rng.randint(1, 9)},{rng.randint(0, 999):03d}"
    elif roll < 0.16:
        word = "-".join(
            "".join(rng.choice(_SYLLABLES) for _ in range(rng.randint(1, 3))) for _ in range(2)
        )
    else:
        word = "".join(rng.choice(_SYLLABLES) for _ in range(rng.randint(1, 4)))
        if rng.random() < 0.1:
            word += rng.choice(".,;:")
    return word.upper() if upper else word


def _words(rng: random.Random, low: int, high: int, *, upper: bool = False) -> list[str]:
    return [_word(rng, upper=upper) for _ in range(rng.randint(low, high))]


def _wrap(words: list[str], width: int, rng: random.Random) -> list[str]:
    """Greedy wrap; a hyphenated word that does not fit may break after a hyphen."""

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= width or not current:
            current = candidate
            continue
        if "-" in word and rng.random() < 0.6:
            head, tail = word.split("-", 1)
            if len(f"{current} {head}-") <= width:
                lines.append(f"{current} {head}-")
                current = tail
                continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def _render_paragraph(layout: _Layout, rng: random.Random, marker: str, level: int) -> str:
    marker_left, text_left = ((10.59, 15.29), (15.29, 20.0))[level]
    words = _words(rng, 3, 60)
    text = " ".join(words)
    wrapped = _wrap(words, rng.randint(40, 95), rng)
    for index, line in enumerate(wrapped):
        layout.advance(ROW_GAP if index == 0 else PITCH)
        if index == 0:
            layout.line([(marker_left, marker), (marker_left + 2.2, " "), (text_left, line)])
        else:
            layout.line([(text_left, line)])
    return f"{marker} {text}"


def _render_table(layout: _Layout, rng: random.Random) -> list[str]:
    rows: list[str] = []
    title_words = _words(rng, 1, 6, upper=True)
    title_lines = _wrap(title_words, rng.randint(8, 30), rng)
    has_header = rng.random() < 0.5
    left_words, right_words = _words(rng, 1, 5), _words(rng, 1, 5)
    header_left = _wrap(left_words, rng.randint(6, 14), rng) if has_header else []
    header_right = _wrap(right_words, rng.randint(6, 14), rng) if has_header else []
    header_height = max(len(header_left), len(header_right)) * PITCH + ROW_GAP
    layout.advance(ROW_GAP * 2, need=len(title_lines) * PITCH + header_height + ROW_GAP)
    title_left = rng.uniform(5.9, 9.5)
    for index, line in enumerate(title_lines):
        if index:
            layout.advance(PITCH)
        layout.line([(title_left, line)])
    rows.append(" ".join(title_words))
    if has_header:
        layout.advance(ROW_GAP)
        for index in range(max(len(header_left), len(header_right))):
            if index:
                layout.advance(PITCH)
            segments = []
            if index < len(header_left):
                segments.append((rng.uniform(6.0, 10.0), header_left[index]))
            if index < len(header_right):
                segments.append((rng.uniform(15.0, 20.0), header_right[index]))
            layout.line(segments)
        rows.append(f"{' '.join(left_words)} | {' '.join(right_words)}")
    ordinal = rng.random() < 0.3
    row_gap = rng.choice((PITCH, ROW_GAP))
    for number in range(1, rng.randint(2, 21)):
        label = (
            f"{number}{('st', 'nd', 'rd')[number - 1]}" if ordinal and number <= 3 else str(number)
        )
        amount = (
            f"{rng.randint(1, 4)},{rng.randint(0, 999):03d}"
            if rng.random() < 0.5
            else str(rng.randint(10, 999))
        )
        value = f"$ {amount}" if number == 1 else amount
        label_lines = [label, "Month"] if ordinal else [label]
        value_lines = [value]
        if rng.random() < 0.3 and len(amount) >= 2:
            split = rng.randint(1, len(amount) - 1)
            if amount[split].isdigit():
                prefix = value[: len(value) - len(amount) + split]
                value_lines = [prefix, amount[split:]]
        layout.advance(row_gap if number > 1 else ROW_GAP, need=PITCH * 2)
        label_left, value_left = rng.uniform(5.9, 10.0), rng.uniform(14.0, 30.0)
        for index in range(max(len(label_lines), len(value_lines))):
            if index:
                layout.advance(PITCH)
            segments = []
            if index < len(label_lines):
                segments.append((label_left, label_lines[index]))
                if index == 0:
                    segments.append((label_left + 1.0, " "))
            if index < len(value_lines):
                segments.append((value_left + (2.4 if index else 0.0), value_lines[index]))
            layout.line(segments)
        rows.append(f"{' '.join(label_lines)} | {value}")
    return rows


def _synthetic_rule(seed: int) -> tuple[bytes, tuple[str, ...]]:
    rng = random.Random(seed)
    layout = _Layout()
    expected: list[str] = []
    citation = f"{rng.randint(1, 50)}.{rng.randint(1, 200)}.{rng.randint(100, 999)}"
    heading_words = [citation, *_words(rng, 3, 20, upper=True)]
    for line in _wrap(heading_words, rng.randint(40, 90), rng):
        layout.advance(PITCH)
        layout.line([(5.88, line)])
    expected.append(" ".join(heading_words))
    for number in range(1, rng.randint(2, 6)):
        expected.append(_render_paragraph(layout, rng, f"({number})", 0))
        for letter in "abcde"[: rng.randint(0, 4)]:
            expected.append(_render_paragraph(layout, rng, f"({letter})", 1))
            if rng.random() < 0.3:
                expected.extend(_render_table(layout, rng))
    notes = {
        "Authorizing statute(s):": f"{rng.randint(1, 90)}-{rng.randint(1, 9)}-{rng.randint(100, 999)}, MCA",
        "Implementing statute(s):": ", ".join(
            f"{rng.randint(1, 90)}-{rng.randint(1, 9)}-{rng.randint(100, 999)}" for _ in range(3)
        )
        + ", MCA",
        "History:": "; ".join(
            f"AMD, {rng.randint(1990, 2025)} MAR p. {rng.randint(1, 3000)}, Eff. 1/1/{rng.randint(10, 99)}"
            for _ in range(rng.randint(1, 12))
        )
        + ".",
    }
    for label, value in notes.items():
        wrapped = _wrap(value.split(" "), rng.randint(40, 100), rng)
        layout.advance(ROW_GAP * 2, need=PITCH)
        layout.line([(5.88, label), (5.88 + len(label) * 0.9, " "), (24.6, wrapped[0])])
        for line in wrapped[1:]:
            layout.advance(PITCH)
            layout.line([(5.88, line)])
        expected.append(f"{label} {value}")
    return layout.html(), tuple(expected)


@pytest.mark.parametrize("seed", range(400))
def test_parser_reads_back_every_synthetic_rule(seed: int) -> None:
    html, expected = _synthetic_rule(seed)
    document = parse_montana_rule_document(html)
    assert document.document_lines() == expected


@pytest.mark.parametrize("seed", range(0, 400, 7))
def test_parser_keeps_every_character_of_the_text_layer(seed: int) -> None:
    html, _ = _synthetic_rule(seed)
    layer = "".join(segment.text for line in text_layer_lines(html) for segment in line.segments)
    rendered = "".join(parse_montana_rule_document(html).document_lines()).replace("|", "")
    assert Counter(_non_space(rendered)) == Counter(_non_space(layer))


# --- failure modes ----------------------------------------------------------


def _page(*lines: list[tuple[float, float, str]]) -> bytes:
    layout = _Layout()
    layout.pages[0].lines = [list(line) for line in lines]
    return layout.html()


def test_parser_rejects_a_page_without_a_text_layer() -> None:
    with pytest.raises(MontanaRulePageError, match="react-pdf"):
        parse_montana_rule_document(b"<html><body><p>37.78.420 RULE</p></body></html>")


def test_parser_rejects_a_heading_without_an_arm_number() -> None:
    html = _page(
        [(5.9, 5.0, "ASSISTANCE STANDARDS")],
        [(10.6, 8.0, "(1)"), (12.8, 8.0, " "), (15.3, 8.0, "Text.")],
        [(15.3, 9.85, "More text.")],
    )
    with pytest.raises(MontanaRulePageError, match="ARM number"):
        parse_montana_rule_document(html)


def test_parser_rejects_a_table_without_labelled_rows() -> None:
    html = _page(
        [(5.9, 5.0, "37.78.420 RULE")],
        [(10.6, 8.0, "(1)"), (12.8, 8.0, " "), (15.3, 8.0, "Text.")],
        [(15.3, 9.85, "More text.")],
        [(6.0, 14.0, "TITLE")],
        [(6.0, 16.42, "Month"), (20.0, 16.42, "amount")],
    )
    with pytest.raises(MontanaRulePageError, match="labelled rows"):
        parse_montana_rule_document(html)


def test_parser_rejects_overlapping_table_columns() -> None:
    html = _page(
        [(5.9, 5.0, "37.78.420 RULE")],
        [(10.6, 8.0, "(1)"), (12.8, 8.0, " "), (15.3, 8.0, "Text.")],
        [(15.3, 9.85, "More text.")],
        [(6.0, 14.0, "1"), (20.0, 14.0, "$ 10")],
        [(25.0, 16.42, "2"), (21.0, 16.42, "20")],
    )
    with pytest.raises(MontanaRulePageError, match="overlap"):
        parse_montana_rule_document(html)


def test_parser_rejects_a_span_without_a_position() -> None:
    html = (
        b'<div class="react-pdf__Page" data-page-number="1">'
        b'<div class="react-pdf__Page__textContent"><span>37.78.420</span></div></div>'
    )
    with pytest.raises(MontanaRulePageError, match="without a position"):
        parse_montana_rule_document(html)
