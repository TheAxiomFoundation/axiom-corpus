"""Tests for reading an ARM rule from a rules.mt.gov react-pdf text layer.

The property tests draw rule documents from a seeded generator, lay them out
the way the rules.mt.gov PDF text layer does (absolutely positioned spans,
wrapped lines, page breaks, two-column tables with wrapped cells) and require
the parser to give back exactly the lines the document was made of. These are
synthetic supported layouts, not retained renditions of other rule versions.
Hypothesis also checks raw DOM text independently of the parser's span reader:
accepted paragraph layouts must preserve every non-whitespace character in order.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass, field
from html import escape

import pytest
from bs4 import BeautifulSoup
from hypothesis import example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.montana_rule_page import (
    MontanaRulePageError,
    join_wrapped,
    parse_montana_rule_document,
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
    soup = BeautifulSoup(html, "html.parser")
    layer = "".join(node.get_text() for node in soup.select(".react-pdf__Page__textContent"))
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


def _paragraph_page(content: str) -> bytes:
    return (
        '<div class="react-pdf__Page" data-page-number="1">'
        '<div class="react-pdf__Page__textContent">'
        '<span style="left:5%; top:5%;">37.78.420 RULE</span>'
        '<span style="left:10%; top:8%;">(1)</span>'
        f"{content}</div></div>"
    ).encode()


@pytest.mark.parametrize(
    "unpositioned",
    [
        "DO NOT ",
        '<div style="left:15%; top:8%;">DO NOT </div>',
        "<p>DO NOT </p>",
        "<em>DO NOT </em>",
    ],
    ids=["direct-layer-text", "positioned-div", "paragraph", "emphasis"],
)
def test_parser_rejects_text_outside_positioned_spans(unpositioned: str) -> None:
    html = _paragraph_page(unpositioned + '<span style="left:15%; top:8%;">pay.</span>')
    with pytest.raises(MontanaRulePageError, match="text outside.*positioned span"):
        parse_montana_rule_document(html)


def test_parser_rejects_text_outside_the_first_text_layer() -> None:
    html = _paragraph_page('<span style="left:15%; top:8%;">pay.</span>')
    html = html.replace(b"</div></div>", b"</div><p>DO NOT</p></div>")
    with pytest.raises(MontanaRulePageError, match="text outside.*positioned span"):
        parse_montana_rule_document(html)


@pytest.mark.parametrize("region", ["document", "wrapper"])
@pytest.mark.parametrize("injection", ["DO NOT ", "<p>DO NOT </p>"])
def test_parser_rejects_text_outside_pages_in_the_document(region: str, injection: str) -> None:
    page = _paragraph_page('<span style="left:15%; top:8%;">pay.</span>').decode()
    wrapper = f'<div class="page-wrapper">{injection if region == "wrapper" else ""}{page}</div>'
    html = (
        f'<div class="react-pdf__Document">'
        f"{injection if region == 'document' else ''}{wrapper}</div>"
    ).encode()
    with pytest.raises(MontanaRulePageError, match="text outside.*positioned span"):
        parse_montana_rule_document(html)


def test_parser_accepts_whitespace_wrappers_and_chrome_outside_the_document() -> None:
    html = (
        b"<nav>Montana SOS Skip to main content</nav>"
        b'<div class="react-pdf__Document">\n<div class="page-wrapper"> \n'
        + _paragraph_page('<span style="left:15%; top:8%;">DO NOT pay.</span>')
        + b"\n</div> \n</div>"
        b"<aside><h2>Rule Version</h2><p>Active Version 33678</p></aside>"
    )
    assert parse_montana_rule_document(html).document_lines() == (
        "37.78.420 RULE",
        "(1) DO NOT pay.",
    )


def test_parser_keeps_text_inside_nonspan_descendants_of_a_positioned_span() -> None:
    html = _paragraph_page('<span style="left:15%; top:8%;">DO <em>NOT</em> pay.</span>')
    assert parse_montana_rule_document(html).body_lines == ("(1) DO NOT pay.",)


def test_parser_ignores_browser_chrome_outside_pdf_pages() -> None:
    html = (
        b"<nav>Montana SOS Skip to main content</nav>"
        + _paragraph_page('<span style="left:15%; top:8%;">DO NOT pay.</span>')
        + b"<aside><h2>Rule Version</h2><p>Active Version 33678</p></aside>"
    )
    assert "Active Version" in BeautifulSoup(html, "html.parser").get_text()
    assert parse_montana_rule_document(html).document_lines() == (
        "37.78.420 RULE",
        "(1) DO NOT pay.",
    )


@pytest.mark.parametrize("direct_text_after_child", [False, True])
def test_parser_rejects_nested_positioned_spans_with_direct_text(
    direct_text_after_child: bool,
) -> None:
    child = '<span style="left:15%; top:8%;">pay.</span>'
    content = child + " DO NOT" if direct_text_after_child else "DO NOT " + child
    html = _paragraph_page(f'<span style="left:15%; top:8%;">{content}</span>')
    with pytest.raises(MontanaRulePageError, match="nested.*text"):
        parse_montana_rule_document(html)


def test_parser_keeps_nested_wrappers_without_direct_text() -> None:
    html = _paragraph_page('<span><span style="left:15%; top:8%;">DO NOT pay.</span></span>')
    assert parse_montana_rule_document(html).body_lines == ("(1) DO NOT pay.",)


@pytest.mark.parametrize(
    "continuation",
    [
        [(6.0, 16.0, "Month"), (20.0, 16.0, "amount"), (40.0, 16.0, "third column")],
        [(20.0, 16.0, "amount"), (40.0, 16.0, "third column")],
        [(6.0, 16.0, "Month"), (10.0, 16.0, "extra column")],
    ],
)
def test_parser_rejects_unexpected_continuation_columns(
    continuation: list[tuple[float, float, str]],
) -> None:
    html = _page(
        [(5.0, 5.0, "37.78.420 RULE")],
        [(10.0, 8.0, "(1)"), (15.0, 8.0, "Text.")],
        [(6.0, 14.0, "1"), (20.0, 14.0, "$ 10")],
        continuation,
    )
    with pytest.raises(MontanaRulePageError, match="column"):
        parse_montana_rule_document(html)


@settings(max_examples=100, deadline=None)
@given(
    before=st.text(alphabet="DO NOT ab12.,-&<>\u00a0", min_size=1, max_size=30),
    child=st.text(alphabet="pay ab12.,-&<>\u00a0", min_size=1, max_size=30),
    after=st.text(alphabet="ab12.,-&<>\u00a0", max_size=30),
    nested=st.booleans(),
    container=st.sampled_from(["span", "layer", "div", "p", "em"]),
    region=st.sampled_from(["layer", "document", "wrapper"]),
)
@example(before="DO NOT ", child="pay.", after="", nested=True, container="layer", region="layer")
@example(before="DO NOT ", child="pay.", after="", nested=True, container="div", region="layer")
@example(
    before="DO NOT ", child="pay.", after="", nested=False, container="layer", region="document"
)
@example(before="DO NOT ", child="pay.", after="", nested=False, container="p", region="document")
@example(
    before="DO NOT ", child="pay.", after="", nested=False, container="layer", region="wrapper"
)
@example(before="DO NOT ", child="pay.", after="", nested=False, container="p", region="wrapper")
def test_parser_preserves_raw_dom_text_in_order_or_rejects(
    before: str,
    child: str,
    after: str,
    nested: bool,
    container: str,
    region: str,
) -> None:
    inner = f'<span style="left:15%; top:8%;">{escape(child)}</span>' if nested else escape(child)
    content = f"{escape(before)}{inner}{escape(after)}"
    if container != "layer":
        content = f'<{container} style="left:15%; top:8%;">{content}</{container}>'
    page = _paragraph_page(
        content if region == "layer" else '<span style="left:15%; top:8%;">pay.</span>'
    ).decode()
    wrapper = f'<div class="page-wrapper">{content if region == "wrapper" else ""}{page}</div>'
    html = (
        f'<div class="react-pdf__Document">{content if region == "document" else ""}{wrapper}</div>'
    ).encode()
    # Read every visible PDF-Document DOM string directly: using text_layer_lines
    # here would share the parser's omissions of unsupported containers.
    soup = BeautifulSoup(html, "html.parser")
    pdf_document = soup.select_one("div.react-pdf__Document")
    assert pdf_document is not None
    raw_text = _non_space(pdf_document.get_text())
    try:
        document = parse_montana_rule_document(html)
    except MontanaRulePageError:
        # Every visible node participates in the oracle, including direct
        # layer text, Document/wrapper siblings and non-span containers.
        # Fully consumed text must work.
        if region != "layer":
            assert _non_space(before + child + after)
            return
        outside_span = before + after if nested else before + child + after
        assert ((nested or container != "span") and _non_space(outside_span)) or not _non_space(
            before + child + after
        )
        return
    assert _non_space("".join(document.document_lines())) == raw_text
