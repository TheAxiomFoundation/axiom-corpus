"""Section text from eCFR XML: table captions and word breaks.

Invariants checked here, for any generated section:

- Word breaks: ``<br/>`` and block children (``<P>``, ``<FP>``, ...) separate the
  words on either side; inline markup (``<E>``, ``<sub>``, ``<SU>``) joins them.
  The tokens of the rendered text equal those of a reference model.
- Only whitespace is added: with whitespace removed, the break-aware text equals
  the plain ``itertext()`` join, so no character is lost, added or reordered.
- Captions: a table's caption is its own block, just before the table's rows.
- Conservation: with whitespace and the ``|`` cell separators removed, a section
  body is the section's text in document order, less its ``HEAD`` and ``CITA``.
- Agreement: sections and appendices render the same body for content that has
  no appendix-only element (HD1-HD3 headings, non-formula images).
"""

import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions

_words = st.text(alphabet="abcxyzABC0189§$%().,—–'é", min_size=1, max_size=6)
_inline_tags = st.sampled_from(["E", "SU", "sub", "sup", "I"])
_block_tags = st.sampled_from(["P", "FP", "FP-1", "PSPACE", "HED", "HD1", "LI", "DIV"])

# A run of content inside one rendered element: (kind, tag, word, space_before).
_segment = st.one_of(
    st.tuples(st.just("text"), st.none(), _words, st.booleans()),
    st.tuples(st.just("inline"), _inline_tags, _words, st.booleans()),
    st.tuples(st.just("br"), st.none(), st.none(), st.booleans()),
    st.tuples(st.just("block"), _block_tags, _words, st.booleans()),
)
_segments = st.lists(_segment, max_size=8)


def _xml(segments):
    parts = []
    for kind, tag, word, space in segments:
        parts.append(" " if space else "")
        if kind == "text":
            parts.append(escape(word))
        elif kind == "inline":
            parts.append(f"<{tag}>{escape(word)}</{tag}>")
        elif kind == "br":
            parts.append("<br/>")
        else:
            parts.append(f"<{tag}>{escape(word)}</{tag}>")
    return "".join(parts)


def _reference_text(segments):
    """Rendered text by hand: a break or block boundary is a space, inline joins."""
    parts = []
    for kind, _tag, word, space in segments:
        parts.append(" " if space else "")
        if kind in ("text", "inline"):
            parts.append(word)
        elif kind == "br":
            parts.append(" ")
        else:
            parts.append(f" {word} ")
    return " ".join("".join(parts).split())


def _no_ws(text):
    return re.sub(r"\s+", "", text)


@settings(max_examples=300, deadline=None)
@given(_segments, st.sampled_from(["TD", "TH", "P", "CAPTION", "HED"]))
def test_breaks_separate_words_and_inline_markup_joins(segments, container):
    elem = ET.fromstring(f"<{container}>{_xml(segments)}</{container}>")

    text = ecfr._element_text_with_breaks(elem)

    assert text == _reference_text(segments)
    # Only whitespace differs from the plain join: nothing lost, added or moved.
    assert _no_ws(text) == _no_ws(ecfr._element_text(elem))


_cells = st.lists(_segments, min_size=1, max_size=3)
_rows = st.lists(_cells, max_size=3)
_captions = st.lists(_words, max_size=2)
_paragraph = st.tuples(st.just("P"), _segments)
_heading = st.tuples(st.just("HED"), _segments)
_table = st.tuples(st.just("TABLE"), st.tuples(_captions, _rows, st.booleans()))
_children = st.lists(st.one_of(_paragraph, _heading, _table), max_size=5)


def _section_xml(children):
    parts = ['<DIV8 N="§ 404.201" TYPE="SECTION"><HEAD>§ 404.201 HEADWORD heading.</HEAD>']
    for tag, content in children:
        if tag == "TABLE":
            captions, rows, wrapped = content
            caption = (
                "<CAPTION>" + "".join(f"<P>{escape(word)}</P>" for word in captions) + "</CAPTION>"
                if captions
                else ""
            )
            body = "".join(
                "<TR>"
                + "".join(
                    f"<{'TH' if index == 0 else 'TD'}>{_xml(cell)}</{'TH' if index == 0 else 'TD'}>"
                    for index, cell in enumerate(row)
                )
                + "</TR>"
                for row in rows
            )
            table = f"<TABLE>{caption}<TBODY>{body}</TBODY></TABLE>"
            parts.append(f'<DIV width="100%">{table}</DIV>' if wrapped else table)
        else:
            parts.append(f"<{tag}>{_xml(content)}</{tag}>")
    parts.append("<CITA>[CITAWORD 45 FR 25060]</CITA></DIV8>")
    return "".join(parts)


def _expected_blocks(children):
    blocks = []
    for tag, content in children:
        if tag == "TABLE":
            captions, rows, _wrapped = content
            caption = " ".join(captions)
            if caption:
                blocks.append(caption)
            lines = [
                " | ".join(text for cell in row for text in [_reference_text(cell)] if text)
                for row in rows
            ]
            table = "\n".join(line for line in lines if line)
            if table:
                blocks.append(table)
        else:
            text = _reference_text(content)
            if text:
                blocks.append(text)
    return blocks


def _source_text(elem):
    """The section's text in document order, less HEAD and CITA."""
    parts = []

    def visit(node):
        if node.text:
            parts.append(node.text)
        for child in node:
            if child.tag not in ("HEAD", "CITA"):
                visit(child)
            if child.tail:
                parts.append(child.tail)

    visit(elem)
    return "".join(parts)


@settings(max_examples=300, deadline=None)
@given(_children)
def test_section_body_keeps_captions_and_word_breaks(children):
    elem = ET.fromstring(_section_xml(children))

    body = ecfr._section_body(elem)

    assert (body.split("\n\n") if body else []) == _expected_blocks(children)
    assert "HEADWORD" not in body and "CITAWORD" not in body
    assert _no_ws(body).replace("|", "") == _no_ws(_source_text(elem))
    # Sections and appendices share the text rules.
    assert ecfr._section_body(elem, appendix=True) == body


@pytest.mark.parametrize(
    "table,expected",
    [
        # 20 CFR 404.1592: a caption paragraph, no <br/>.
        (
            '<TABLE><CAPTION><P class="title">Table 1—For Employees</P></CAPTION>'
            "<TR><TH>For months</TH><TH>Amount</TH></TR></TABLE>",
            ["Table 1—For Employees", "For months | Amount"],
        ),
        # 20 CFR 404.313: a heading cell broken with <br/>.
        (
            "<TABLE><TR><TH>If your date of birth is:</TH>"
            "<TH>The credit for each month you delay<br />retirement is:</TH></TR></TABLE>",
            ["If your date of birth is: | The credit for each month you delay retirement is:"],
        ),
        # Appendix 1 to subpart P of part 404: adjacent caption paragraphs.
        (
            '<TABLE><CAPTION><P class="title">Table IV-A</P><P class="headnote">'
            "[Applicable at test sites less than 3,000 feet above sea level]</P></CAPTION>"
            "<TR><TD>65</TD></TR></TABLE>",
            ["Table IV-A [Applicable at test sites less than 3,000 feet above sea level]", "65"],
        ),
        # A table with no caption renders as before.
        ("<TABLE><TR><TD>a</TD><TD>b</TD></TR></TABLE>", ["a | b"]),
    ],
)
def test_section_records_keep_ecfr_captions_and_breaks(table, expected):
    xml = (
        '<ECFR><DIV5 N="404" TYPE="PART"><HEAD>PART 404</HEAD>'
        '<DIV8 N="§ 404.313" TYPE="SECTION"><HEAD>§ 404.313 Delayed retirement.</HEAD>'
        f"<P>(a) Text.</P>{table}</DIV8></DIV5></ECFR>"
    )

    records = tuple(
        iter_ecfr_title_provisions(
            xml, (EcfrPartTarget(title=20, part="404"),), version="v", source_path="s.xml"
        )
    )

    assert records[-1].citation_path == "us/regulation/20/404/313"
    assert records[-1].body.split("\n\n") == ["(a) Text.", *expected]
