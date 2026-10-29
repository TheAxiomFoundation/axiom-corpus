"""Section text from eCFR XML: table captions and word breaks.

Invariants checked here, for any generated section:

- Word breaks: ``<br/>`` and block children (``<P>``, ``<FP>``, ...) separate the
  words on either side; a ``<br/>`` directly after a hyphen preserves the join.
  Inline markup (``<E>``, ``<sub>``, ``<SU>``) joins its surrounding text.
  The tokens of the rendered text equal those of a reference model.
- Only whitespace is added: with whitespace removed, the break-aware text equals
  the plain ``itertext()`` join, so no character is lost, added or reordered.
- Captions: a table's caption is its own block, just before the table's rows.
- Conservation: remove the caption marker, whitespace and ``|`` cell
  separators, and a body equals the source text less ``HEAD`` and ``CITA``.
- Caption isolation: captions never change paragraph paths, labels or spans after
  mapping offsets through removal of their caption blocks.
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
from axiom_corpus.corpus.anchors import generate_anchors_for_provision
from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions
from axiom_corpus.corpus.models import ProvisionRecord

_words = st.text(alphabet="abcxyzABC0189§$%().,—–'é-", min_size=1, max_size=6)
_inline_tags = st.sampled_from(["E", "SU", "sub", "sup", "I"])
_block_tags = st.sampled_from(["P", "FP", "FP-1", "PSPACE", "HED", "HD1", "LI", "DIV"])

# A segment holds (kind, tag, content, space_before). Inline content recursively
# contains text, breaks and inline elements, including breaks nested several deep.
_segment = st.recursive(
    st.one_of(
        st.tuples(st.just("text"), st.none(), _words, st.booleans()),
        st.tuples(st.just("br"), st.none(), st.none(), st.booleans()),
        st.tuples(st.just("block"), _block_tags, _words, st.booleans()),
    ),
    lambda child: st.tuples(
        st.just("inline"), _inline_tags, st.lists(child, max_size=4), st.booleans()
    ),
    max_leaves=16,
)
_segments = st.lists(_segment, max_size=8)


def _xml(segments):
    parts = []
    for kind, tag, content, space in segments:
        parts.append(" " if space else "")
        if kind == "text":
            parts.append(escape(content))
        elif kind == "inline":
            parts.append(f"<{tag}>{_xml(content)}</{tag}>")
        elif kind == "br":
            parts.append("<br/>")
        else:
            parts.append(f"<{tag}>{escape(content)}</{tag}>")
    return "".join(parts)


def _reference_text(segments):
    """Model boundaries recursively, preserving source hyphens across breaks."""
    parts = []

    def visit(items):
        for kind, _tag, content, space in items:
            parts.append(" " if space else "")
            if kind == "text":
                parts.append(content)
            elif kind == "inline":
                visit(content)
            elif kind == "br":
                if not "".join(parts).endswith("-"):
                    parts.append(" ")
            else:
                parts.append(f" {content} ")

    visit(segments)
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
                blocks.append(f"[Table caption: {caption}]")
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


def _unmark_caption_blocks(body):
    return re.sub(r"(?m)^\[Table caption: (.*)\]$", r"\1", body)


def _without_caption_blocks(body):
    return "\n\n".join(
        block for block in body.split("\n\n") if not block.startswith("[Table caption: ")
    )


def _anchor_signature(elem, *, appendix=False, remove_captions=False):
    body = ecfr._section_body(elem, appendix=appendix)
    provision = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        id="section-fixture",
        citation_path=(
            "us/regulation/26/1/appendix-a" if appendix
            else "us/regulation/26/1/412-c-1-2"
        ),
        body=body,
    )
    return [
        (
            anchor.citation_path,
            anchor.label,
            len(_without_caption_blocks(body[:anchor.char_start]))
            if remove_captions else anchor.char_start,
            len(_without_caption_blocks(body[:anchor.char_end]))
            if remove_captions else anchor.char_end,
            _without_caption_blocks(anchor.text) if remove_captions else anchor.text,
        )
        for anchor in generate_anchors_for_provision(provision)
    ]


def _remove_captions(elem):
    for table in elem.iter("TABLE"):
        for caption in table.findall("CAPTION"):
            table.remove(caption)


@pytest.mark.parametrize("appendix", [False, True])
def test_repeated_labeled_captions_do_not_create_paragraph_anchors(appendix):
    # 26 CFR 1.412(c)(1)-2 repeats (A) captions after its (a) paragraph text.
    elem = ET.fromstring(
        '<DIV8 N="§ 1.412(c)(1)-2" TYPE="SECTION">'
        '<P>(a) Computation of the charge.</P>'
        '<TABLE><CAPTION><P>(A) Computation of Net Shortfall Charge</P></CAPTION>'
        '<TR><TD>First computation</TD></TR></TABLE>'
        '<TABLE><CAPTION><P>(A) Computation of Net Shortfall Charge</P></CAPTION>'
        '<TR><TD>Second computation</TD></TR></TABLE>'
        '<P>(b) Next paragraph.</P></DIV8>'
    )
    actual = _anchor_signature(elem, appendix=appendix, remove_captions=True)
    _remove_captions(elem)

    assert actual == _anchor_signature(elem, appendix=appendix)
    assert [path.rsplit("/", 1)[-1] for path, *_ in actual] == ["a", "b"]


_caption_label = st.sampled_from(["a", "A", "B", "C", "1", "2", "i", "ii"])
_labeled_caption = st.tuples(
    _caption_label,
    st.sampled_from([
        " Computation", " FIRST CATEGORY", " Text—(A) charge", " Text–(1) charge",
        " Text. (1) charge", " Text: (A) charge",
    ]),
).map(lambda pair: f"({pair[0]}){pair[1]}")


@pytest.mark.parametrize("appendix", [False, True])
@settings(max_examples=100, deadline=None)
@given(captions=st.lists(_labeled_caption, min_size=1, max_size=5))
def test_labeled_captions_preserve_paragraph_anchors(captions, appendix):
    tables = "".join(
        f"<TABLE><CAPTION><P>{escape(caption)}</P></CAPTION>"
        f"<TR><TD>Value {index}</TD></TR></TABLE>"
        for index, caption in enumerate(captions)
    )
    elem = ET.fromstring(
        '<DIV8><P>(a) Computation—(1) First paragraph.</P>'
        f'{tables}<P>(2) Second paragraph.</P><P>(b) Next paragraph.</P></DIV8>'
    )
    actual = _anchor_signature(elem, appendix=appendix, remove_captions=True)
    _remove_captions(elem)

    assert actual == _anchor_signature(elem, appendix=appendix)


@pytest.mark.parametrize("appendix", [False, True])
@pytest.mark.parametrize(
    "content,expected",
    [
        ("<TABLE><TR><TH>Occupa-<br/>tion</TH></TR></TABLE>", "Occupa-tion"),
        (
            "<TABLE><TR><TH>Dec. 31, 1954-<br/>Apr. 1, 1957</TH></TR></TABLE>",
            "Dec. 31, 1954-Apr. 1, 1957",
        ),
    ],
)
def test_hyphen_before_break_keeps_source_join(content, expected, appendix):
    elem = ET.fromstring(f"<DIV8>{content}</DIV8>")

    assert ecfr._section_body(elem, appendix=appendix) == expected


def test_nested_inline_break_separates_words():
    elem = ET.fromstring("<DIV8><P><E>a<sub><I>b<br/>c</I></sub>d</E></P></DIV8>")

    assert ecfr._section_body(elem) == "ab cd"


@pytest.mark.parametrize("appendix", [False, True])
@settings(max_examples=300, deadline=None)
@given(children=_children)
def test_section_body_keeps_captions_and_word_breaks(children, appendix):
    elem = ET.fromstring(_section_xml(children))

    body = ecfr._section_body(elem, appendix=appendix)

    assert (body.split("\n\n") if body else []) == _expected_blocks(children)
    assert "HEADWORD" not in body and "CITAWORD" not in body
    assert _no_ws(_unmark_caption_blocks(body)).replace("|", "") == _no_ws(_source_text(elem))
    # Sections and appendices share caption markers and source text.
    assert ecfr._section_body(elem, appendix=not appendix) == body


@pytest.mark.parametrize(
    "table,expected",
    [
        # 20 CFR 404.1592: a caption paragraph, no <br/>.
        (
            '<TABLE><CAPTION><P class="title">Table 1—For Employees</P></CAPTION>'
            "<TR><TH>For months</TH><TH>Amount</TH></TR></TABLE>",
            ["[Table caption: Table 1—For Employees]", "For months | Amount"],
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
            [
                "[Table caption: Table IV-A "
                "[Applicable at test sites less than 3,000 feet above sea level]]",
                "65",
            ],
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
