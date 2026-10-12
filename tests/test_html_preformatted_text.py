"""``pre`` elements in the official-document HTML extractor.

Before 2026-10-12 the extractor read heading, ``p``, ``li``, ``table`` and
``blockquote`` nodes only, so text printed in a ``pre`` element reached a row only
when it sat inside one of those or when the page had no other text node (the root
fallback). SSA POMS RS 02510.026 lost 57 ``pre`` screen exhibits that way. A ``pre``
is now a text node of its own and keeps its line breaks.
"""

from __future__ import annotations

import html
import string

import pytest
from bs4 import BeautifulSoup
from hypothesis import given
from hypothesis import strategies as st

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.documents import (
    _extract_html_blocks,
    _html_node_text,
    _join_html_text_parts,
    _normalize_preformatted_text,
    _normalize_text,
)
from scripts.audit_recovery_sibling_scopes import _matching_run, read_page

# Shaped like SSA POMS RS 02510.026 (2026-10-12): a DEQY earnings-query printout in
# ``pre`` elements under ``div.poms``, between ordinary paragraphs.
POMS_PAGE = b"""<!doctype html><html><head><title>POMS RS 02510.026</title></head><body>
<header>Social Security banner</header>
<div class="poms">
<h1 class="sectitle">RS 02510.026 Annual Report Exhibits</h1>
<p class="tninfo">TN 12 (06-24)</p>
<h2>A. DEQY printout</h2>
<p class="poms-para">The query shows the reported earnings.</p>
<pre class="poms-pre-normal">
 RPYR  REO  EIN-SEI    LOAC  NAME        EARNINGS
 0017  AA   xxxxxxxxx  C     J DOE       32750.00

 WAGE TOTAL                              32750.00
</pre>
<p class="poms-para">Compare the total with the annual report.</p>
</div>
</body></html>"""
POMS_EXTRACTION = {"html_content_selector": "div.poms", "html_drop_selectors": ["p.tninfo"]}
PRE_TAGS_BEFORE = frozenset(documents._TEXT_TAGS - {"pre"})


def _blocks(page: bytes, extraction: dict | None = None):
    return _extract_html_blocks(
        page,
        source_url="https://example.gov/page",
        fallback_title="Fallback",
        extraction=extraction,
    )


def test_pre_text_reaches_the_block_with_its_line_breaks() -> None:
    [block] = _blocks(POMS_PAGE, POMS_EXTRACTION)

    assert block.heading == "A. DEQY printout"
    assert block.body == (
        "The query shows the reported earnings.\n\n"
        "RPYR REO EIN-SEI LOAC NAME EARNINGS\n"
        "0017 AA xxxxxxxxx C J DOE 32750.00\n\n"
        "WAGE TOTAL 32750.00\n\n"
        "Compare the total with the annual report."
    )


def test_pre_fixture_is_dropped_by_the_old_text_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuous: the fixture's printout reaches a row only through the ``pre`` node.

    With the tag set the extractor used before (no ``pre``), the same page loses the
    printout and keeps the paragraphs around it, so the test above checks the new
    node and not a path that already read it (an enclosing table or the fallback).
    """
    monkeypatch.setattr(documents, "_TEXT_TAGS", set(PRE_TAGS_BEFORE))

    [block] = _blocks(POMS_PAGE, POMS_EXTRACTION)

    assert "32750.00" not in block.body
    assert block.body == (
        "The query shows the reported earnings.\n\nCompare the total with the annual report."
    )


def test_pre_reads_br_as_a_line_break_and_adds_no_space_at_inline_tags() -> None:
    page = (
        b"<html><body><main><pre>Line one<br>Line   two [<a href='https://www.gpo.gov'>"
        b"www.gpo.gov</a>]\n\n\n   Para two   \n</pre></main></body></html>"
    )

    [block] = _blocks(page)

    assert block.body == "Line one\nLine two [www.gpo.gov]\n\nPara two"


def test_pre_inside_a_table_is_read_once_through_the_table() -> None:
    page = (
        b"<html><body><main><table><tr><td>Code</td><td><pre>A1\nB2</pre></td></tr>"
        b"</table></main></body></html>"
    )

    [block] = _blocks(page)

    assert block.body == "Code A1 B2"


def test_a_page_that_is_one_pre_reads_like_the_old_fallback_with_line_breaks() -> None:
    """A Federal Register text page is one ``pre``; it used to reach a row only by the
    root fallback, which joined its lines with spaces."""
    page = (
        b"<html><head><title>Federal Register Notice</title></head><body><pre>\n"
        b"[Federal Register Volume 90, Number 210]\n[Notices]\n\n"
        b"SUMMARY: The amounts\nare as follows.\n</pre></body></html>"
    )
    soup = BeautifulSoup(page, "lxml")
    old_fallback_body = _normalize_text(soup.body.get_text(" ", strip=True))

    [block] = _blocks(page)

    assert block.heading == "Federal Register Notice"
    assert block.body == (
        "[Federal Register Volume 90, Number 210]\n[Notices]\n\nSUMMARY: The amounts\nare as follows."
    )
    assert _normalize_text(block.body) == old_fallback_body


def test_selected_pre_nodes_keep_line_breaks() -> None:
    page = (
        b"<html><body><div id='legcontent'><pre>  1  Section 1. The tax law\n"
        b"  2  is amended.</pre></div></body></html>"
    )

    [block] = _blocks(page, {"html_content_selector": "#legcontent", "html_text_selector": "pre"})

    assert block.body == "1 Section 1. The tax law\n2 is amended."


def test_labeled_sections_keep_pre_line_breaks_in_the_section_body() -> None:
    page = (
        b"<html><body><main><p>Section 1. Rates</p><pre>Bracket   Rate\n0-10      1%\n</pre>"
        b"<p>Section 2. Credits</p><p>None.</p></main></body></html>"
    )

    sections = _blocks(
        page,
        {
            "segmentation": "labeled_sections",
            "section_heading_pattern": r"^Section (?P<label>\d+)\.\s*(?P<heading>.+)$",
        },
    )

    assert [(s.metadata["section_label"], s.heading, s.body) for s in sections] == [
        ("1", "Rates", "Bracket Rate\n0-10 1%"),
        ("2", "Credits", "None."),
    ]


def test_recovery_audit_walks_pre_nodes_as_the_extractor_does() -> None:
    """``audit_recovery_sibling_scopes.read_page`` mirrors the extractor's node text."""
    page = (
        b"<html><body><main><h2>Exhibit</h2><p>Lead.</p><pre>A   1\nB   2</pre></main>"
        b"</body></html>"
    )
    [block] = _blocks(page)

    walked = read_page(page, None)

    assert block.body == "Lead.\n\nA 1\nB 2"
    assert _matching_run(block.body, walked) is not None


_TEXT = st.text(
    alphabet=st.sampled_from(
        list("ab .,-$1\t\n\r") + ["\u00a0", "\u2028", "\x0c", "\u200b", "\ufeff", "\u3000"]
    ),
    max_size=80,
)


@given(_TEXT)
def test_preformatted_text_flattens_to_normalize_text(text: str) -> None:
    """Keeping line breaks is the only difference from ``_normalize_text``."""
    assert _normalize_text(_normalize_preformatted_text(text)) == _normalize_text(text)


@given(_TEXT)
def test_preformatted_text_is_normalized_once(text: str) -> None:
    normalized = _normalize_preformatted_text(text)

    assert _normalize_preformatted_text(normalized) == normalized
    assert normalized == normalized.strip()
    assert "\n\n\n" not in normalized
    assert " \n" not in normalized and "\n " not in normalized and "  " not in normalized
    assert all(line == " ".join(line.split()) for line in normalized.split("\n"))


@given(st.lists(_TEXT, max_size=6))
def test_joining_normalized_parts_is_the_normalized_join(raw_parts: list[str]) -> None:
    """Pages without ``pre`` get the bodies the extractor made before.

    The block body used to be ``_normalize_text`` of the joined parts; it is now the
    plain join. For parts ``_normalize_text`` made (every non-``pre`` node), the two
    are the same string.
    """
    parts = [part for part in map(_normalize_text, raw_parts) if part]

    assert _join_html_text_parts(parts) == _normalize_text("\n\n".join(parts))


@given(
    st.lists(
        st.text(alphabet=string.ascii_letters + string.digits + " \t$.,-", max_size=20),
        max_size=8,
    )
)
def test_extracted_pre_body_is_the_preformatted_text(lines: list[str]) -> None:
    printed = "\n".join(lines)
    page = f"<html><body><main><pre>{html.escape(printed)}</pre></main></body></html>".encode()
    expected = _normalize_preformatted_text(printed)

    blocks = _blocks(page)

    if expected:
        assert [block.body for block in blocks] == [expected]
    else:
        assert all(not block.body for block in blocks)


def test_html_node_text_reads_non_pre_nodes_as_before() -> None:
    soup = BeautifulSoup("<p>  One\n  <b>two</b>three </p>", "html.parser")
    node = soup.find("p")
    assert node is not None
    assert (
        _html_node_text(node) == _normalize_text(node.get_text(" ", strip=True)) == "One two three"
    )
