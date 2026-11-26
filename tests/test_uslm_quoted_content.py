"""Line rendering of USLM quoted amendments (axiom_corpus.corpus.uslm_quoted_content)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from axiom_corpus.corpus.uslm_quoted_content import (
    StatutesPage,
    UslmRenderError,
    last_text_slot,
    local_name,
    page_in_effect,
    render_structural_element,
    structural_label_paths,
)

NS = "http://schemas.gpo.gov/xml/uslm"

# A quoted subsection shaped like Pub. L. 119-21 sec. 71119(a): every quoted
# paragraph's number carries the amendatory open quote, a run-in subclause has
# none, a page marker falls mid-sentence, margin notes sit between a number and
# its heading and inside a chapeau, and the closing quote ends the last text.
QUOTED = f"""<main xmlns="{NS}"><page identifier="/us/stat/139/306">139 STAT. 306</page>
<section><content>Section 1902 is amended by adding at the end the following:
<quotedContent><subsection><num value="zz">“(zz) </num><heading>Test rule<inline>.—</inline></heading>
<paragraph><num value="1">“(1) </num><sidenote><p>Deadline.</p></sidenote><heading>In general<inline>.—</inline></heading><chapeau>Except as provided in paragraph <sidenote><p>Determination.</p><p>Criteria.</p></sidenote>(2), a State shall, <page identifier="/us/stat/139/307">139 STAT. 307</page>
for the term ‘<term>applicable individual</term>’, provide—</chapeau>
<subparagraph><num value="A">“(A) </num><content>one thing; and</content></subparagraph>
<subparagraph><num value="B">“(B) </num><chapeau>another—</chapeau>
<clause><num value="i">“(i)</num><subclause class="inline"><num value="I">(I) </num><content>run in “quoted” text;</content></subclause>
<subclause><num value="II">“(II) </num><content>second;<page identifier="/us/stat/139/308">139 STAT. 308</page></content></subclause></clause>
<clause><num value="ii">“(ii) </num><content>the State’s last clause.”</content></clause></subparagraph>
</paragraph></subsection></quotedContent>.</content></section></main>"""


def _parse() -> tuple[ET.Element, ET.Element, ET.Element]:
    document = ET.fromstring(QUOTED)
    quoted = next(node for node in document.iter() if local_name(node.tag) == "quotedContent")
    subsection = next(node for node in quoted if local_name(node.tag) == "subsection")
    return document, quoted, subsection


def test_renders_one_line_per_descendant_without_markers_or_amendatory_quotes() -> None:
    _document, quoted, subsection = _parse()
    rendered = render_structural_element(
        subsection, label_path=("zz",), closing_slot=last_text_slot(quoted)
    )
    assert rendered.body.split("\n") == [
        "(1) In general.— Except as provided in paragraph (2), a State shall, for the term "
        "‘applicable individual’, provide—",
        "(A) one thing; and",
        "(B) another—",
        "(i)",
        "(I) run in “quoted” text;",
        "(II) second;",
        "(ii) the State’s last clause.",
    ]
    assert rendered.label_paths == (
        ("zz", "1"),
        ("zz", "1", "A"),
        ("zz", "1", "B"),
        ("zz", "1", "B", "i"),
        ("zz", "1", "B", "i", "I"),
        ("zz", "1", "B", "i", "II"),
        ("zz", "1", "B", "ii"),
    )
    assert rendered.stripped_open_quotes == 6
    assert rendered.stripped_closing_quote


def test_page_breaks_and_margin_notes_carry_body_offsets() -> None:
    _document, quoted, subsection = _parse()
    rendered = render_structural_element(
        subsection, label_path=("zz",), closing_slot=last_text_slot(quoted)
    )
    body = rendered.body
    pages = [(item.page.page, item.printed) for item in rendered.page_breaks]
    assert pages == [(307, "139 STAT. 307"), (308, "139 STAT. 308")]
    assert body[rendered.page_breaks[0].offset :].startswith("for the term")
    assert body[rendered.page_breaks[1].offset :].startswith("(ii) the State")
    notes = [(note.notes, note.label_path) for note in rendered.margin_notes]
    assert notes == [
        (("Deadline.",), ("zz", "1")),
        (("Determination.", "Criteria."), ("zz", "1")),
    ]
    assert body[rendered.margin_notes[0].offset :].startswith("In general.—")
    assert body[rendered.margin_notes[1].offset :].startswith("(2), a State")


def test_a_row_body_leaves_out_its_own_number_heading_and_margin_note() -> None:
    _document, quoted, subsection = _parse()
    paragraph = next(node for node in subsection if local_name(node.tag) == "paragraph")
    rendered = render_structural_element(
        paragraph, label_path=("zz", "1"), closing_slot=last_text_slot(quoted)
    )
    assert rendered.body.startswith("Except as provided in paragraph (2), a State shall,")
    assert rendered.margin_notes[0].notes == ("Deadline.",)
    assert rendered.margin_notes[0].offset == 0
    assert rendered.stripped_open_quotes == 5


def test_closing_quote_is_kept_without_a_closing_slot_and_required_with_one() -> None:
    _document, _quoted, subsection = _parse()
    kept = render_structural_element(subsection, label_path=("zz",))
    assert kept.body.endswith("last clause.\u201d")
    assert not kept.stripped_closing_quote
    chapeau = next(node for node in subsection.iter() if local_name(node.tag) == "chapeau")
    with pytest.raises(UslmRenderError, match="closing quote"):
        render_structural_element(
            subsection, label_path=("zz",), closing_slot=last_text_slot(chapeau)
        )


def test_last_text_slot_skips_marker_text() -> None:
    element = ET.fromstring(
        f'<content xmlns="{NS}">end.”<sidenote><p>Note.</p></sidenote>'
        '<page identifier="/us/stat/1/2">1 STAT. 2</page></content>'
    )
    node, slot = last_text_slot(element)
    assert (node is element, slot) == (True, "text")


def test_page_in_effect_and_label_paths() -> None:
    document, _quoted, subsection = _parse()
    assert page_in_effect(document, subsection) == StatutesPage("/us/stat/139/306", 139, 306)
    paragraph = next(node for node in subsection if local_name(node.tag) == "paragraph")
    clause = next(node for node in paragraph.iter() if local_name(node.tag) == "clause")
    assert page_in_effect(document, clause).page == 307  # type: ignore[union-attr]
    assert structural_label_paths(subsection, ("zz",))[-1] == ("zz", "1", "B", "ii")


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        ('<paragraph><num value="1">(1)</num><table/></paragraph>', "unexpected <table>"),
        (
            '<paragraph><num value="1">(1)</num>stray<content>x</content></paragraph>',
            "text after <num>",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>x</content>stray</paragraph>',
            "text after <content>",
        ),
        (
            '<paragraph>stray<num value="1">(1)</num><content>x</content></paragraph>',
            "text outside a text block",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>wo<page identifier="/us/stat/1/2">'
            "1 STAT. 2</page>rd</content></paragraph>",
            "splits a word",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>shall<page identifier="/us/stat/1/2">'
            "1 STAT. 2</page><ref>pay</ref></content></paragraph>",
            "splits a word",
        ),
        (
            '<paragraph><num value="1">(1)</num><content><inline>shall'
            '<page identifier="/us/stat/1/2"/></inline>pay</content></paragraph>',
            "splits a word",
        ),
        (
            '<paragraph><num value="1">(1)</num><subparagraph><num value="A">(A)</num>'
            "<content>First.</content></subparagraph><continuation>Flush.</continuation></paragraph>",
            "cannot place <continuation>",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>a <page identifier="x">x</page> b'
            "</content></paragraph>",
            "page identifier",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>a <sidenote>loose</sidenote> b'
            "</content></paragraph>",
            "margin note",
        ),
        (
            '<paragraph><num value="1">(1)</num><clause><content>x</content></clause></paragraph>',
            "no num value",
        ),
    ],
)
def test_rejects_what_it_cannot_place(fragment: str, message: str) -> None:
    element = ET.fromstring(
        f'<subsection xmlns="{NS}"><num value="zz">(zz)</num>{fragment}</subsection>'
    )
    with pytest.raises(UslmRenderError, match=message):
        render_structural_element(element, label_path=("zz",))


def test_page_break_keeps_a_separator_in_the_next_inline_element() -> None:
    element = ET.fromstring(
        f'<paragraph xmlns="{NS}"><content>shall<page identifier="/us/stat/1/2"/>'
        "<ref> pay</ref></content></paragraph>"
    )
    rendered = render_structural_element(element, label_path=("1",))
    assert rendered.body == "shall pay"
    assert rendered.page_breaks[0].offset == rendered.body.index("pay")


def test_a_skipped_heading_keeps_its_margin_note_at_the_start_of_the_body() -> None:
    element = ET.fromstring(
        f'<subsection xmlns="{NS}"><num value="kk">(kk)</num><heading>Condition<inline>.</inline>'
        "<sidenote><p>Effective date.</p></sidenote><inline>—</inline></heading>"
        "<content>This subsection applies.</content></subsection>"
    )
    rendered = render_structural_element(element, label_path=("kk",))
    assert rendered.body == "This subsection applies."
    assert len(rendered.margin_notes) == 1
    note = rendered.margin_notes[0]
    assert (note.notes, note.label_path, note.offset) == (("Effective date.",), ("kk",), 0)


def test_space_before_punctuation_is_kept_unless_asked_to_drop_it() -> None:
    element = ET.fromstring(
        f'<paragraph xmlns="{NS}"><num value="1">(1)</num><chapeau>text—</chapeau>'
        '<subparagraph><num value="A">(A)</num><content>of 1986 .</content></subparagraph>'
        "</paragraph>"
    )
    kept = render_structural_element(element, label_path=("1",))
    dropped = render_structural_element(
        element, label_path=("1",), drop_space_before_punctuation=True
    )
    assert kept.body == "text—\n(A) of 1986 ."
    assert dropped.body == "text—\n(A) of 1986."
