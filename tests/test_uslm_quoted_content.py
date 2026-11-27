"""Line rendering of USLM quoted amendments (axiom_corpus.corpus.uslm_quoted_content)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

import pytest

from axiom_corpus.corpus.uslm_quoted_content import (
    VERIFIED_QUOTATIONS,
    StatutesPage,
    UslmRenderError,
    _checked_render,
    _quotation_fingerprint,
    _render_structural_element,
    _structural_nodes,
    last_text_slot,
    local_name,
    num_value,
    page_in_effect,
    render_structural_element,
    structural_label_paths,
)
from scripts.repro.us_pl_119_21_1396a_xx_line_structure import (
    CITATION_PATHS,
    SOURCE_LEAF,
    SOURCE_VERSION,
    _quoted_subsection,
    render_rows,
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
    rendered = _render_structural_element(
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
    rendered = _render_structural_element(
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
    rendered = _render_structural_element(
        paragraph, label_path=("zz", "1"), closing_slot=last_text_slot(quoted)
    )
    assert rendered.body.startswith("Except as provided in paragraph (2), a State shall,")
    assert rendered.margin_notes[0].notes == ("Deadline.",)
    assert rendered.margin_notes[0].offset == 0
    assert rendered.stripped_open_quotes == 5


def test_closing_quote_is_kept_without_a_closing_slot_and_required_with_one() -> None:
    _document, _quoted, subsection = _parse()
    kept = _render_structural_element(subsection, label_path=("zz",))
    assert kept.body.endswith("last clause.\u201d")
    assert not kept.stripped_closing_quote
    chapeau = next(node for node in subsection.iter() if local_name(node.tag) == "chapeau")
    with pytest.raises(UslmRenderError, match="closing quote"):
        _render_structural_element(
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
            "would join text without whitespace",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>shall<page identifier="/us/stat/1/2">'
            "1 STAT. 2</page><ref>pay</ref></content></paragraph>",
            "would join text without whitespace",
        ),
        (
            '<paragraph><num value="1">(1)</num><content><inline>shall'
            '<page identifier="/us/stat/1/2"/></inline>pay</content></paragraph>',
            "would join text without whitespace",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>under paragraph'
            '<page identifier="/us/stat/139/307">139 STAT. 307</page>(2).</content></paragraph>',
            "would join text without whitespace",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>42'
            '<page identifier="/us/stat/139/307"/>§ 1396a</content></paragraph>',
            "would join text without whitespace",
        ),
        (
            '<paragraph><num value="1">(1)</num><content>‘<term>State</term>’'
            "<sidenote><p>Definition.</p></sidenote>means</content></paragraph>",
            "would join text without whitespace",
        ),
        pytest.param(
            '<paragraph><num value="1">(1)</num><content>under paragraph (2<inline>)</inline>'
            '<span><page identifier="/us/stat/139/307"/></span>'
            "<ref>(as in effect in 2026)</ref>.</content></paragraph>",
            "would join text without whitespace",
            id="page-between-parentheses",
        ),
        pytest.param(
            '<paragraph><num value="1">(1)</num><content>text,'
            "<sidenote><p>Note.</p></sidenote>—next</content></paragraph>",
            "would join text without whitespace",
            id="margin-note-between-comma-and-em-dash",
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
        _render_structural_element(element, label_path=("zz",))


def test_page_break_keeps_a_separator_in_the_next_inline_element() -> None:
    element = ET.fromstring(
        f'<paragraph xmlns="{NS}"><content>shall<page identifier="/us/stat/1/2"/>'
        "<ref> pay</ref></content></paragraph>"
    )
    rendered = _render_structural_element(element, label_path=("1",))
    assert rendered.body == "shall pay"
    assert rendered.page_breaks[0].offset == rendered.body.index("pay")


@pytest.mark.parametrize(
    ("block", "markers", "rejected_tag"),
    [
        pytest.param("content", ("page",), "page", id="page-in-content"),
        pytest.param("content", ("page", "sidenote"), "page", id="page-then-sidenote"),
        pytest.param("content", ("sidenote",), "sidenote", id="sidenote-in-content"),
        pytest.param("heading", ("page",), "page", id="page-in-heading"),
        pytest.param("heading", ("sidenote", "page"), "page", id="sidenote-then-page-in-heading"),
    ],
)
def test_period_dash_join_requires_only_sidenotes_within_a_heading(
    block: str, markers: tuple[str, ...], rejected_tag: str
) -> None:
    xml = {
        "page": '<page identifier="/us/stat/139/307"/>',
        "sidenote": "<sidenote><p>Note.</p></sidenote>",
    }
    marker_xml = "".join(xml[tag] for tag in markers)
    element = ET.fromstring(
        f"<paragraph><{block}>The deadline is 5 p.m.{marker_xml}— midnight if extended."
        f"</{block}></paragraph>"
    )
    with pytest.raises(
        UslmRenderError, match=f"<{rejected_tag}> would join text without whitespace"
    ):
        _render_structural_element(element, label_path=("1",))


def test_margin_note_between_heading_punctuation_joins_the_punctuation() -> None:
    # Pub. L. 119-21 sec. 70304(a)(3)(B)(ii) places the note within the heading.
    element = ET.fromstring(
        f'<subparagraph xmlns="{NS}"><clause><num value="ii">“(ii) </num>'
        "<heading>Substantial and legitimate business reason<inline>.</inline>"
        "<sidenote><p>Definition.</p></sidenote><inline>—</inline></heading>"
        "<content>For purposes of clause (i), the term ‘<term>substantial and legitimate business "
        "reason</term>’ shall not include the operation of a separate line of business, the rate "
        "of wages or category of jobs for employees (or any similar basis), or the application of "
        "State or local laws relating to family and medical leave, but may include the grouping of "
        "employees of a common law employer.</content></clause></subparagraph>"
    )
    rendered = _render_structural_element(element, label_path=("B",))
    assert rendered.body.startswith(
        "(ii) Substantial and legitimate business reason.— For purposes of clause (i),"
    )
    (note,) = rendered.margin_notes
    assert (note.notes, note.label_path, note.offset) == (
        ("Definition.",),
        ("B", "ii"),
        rendered.body.index("—"),
    )


def test_a_skipped_heading_keeps_its_margin_note_at_the_start_of_the_body() -> None:
    element = ET.fromstring(
        f'<subsection xmlns="{NS}"><num value="kk">(kk)</num><heading>Condition<inline>.</inline>'
        "<sidenote><p>Effective date.</p></sidenote><inline>—</inline></heading>"
        "<content>This subsection applies.</content></subsection>"
    )
    rendered = _render_structural_element(element, label_path=("kk",))
    assert rendered.body == "This subsection applies."
    assert len(rendered.margin_notes) == 1
    note = rendered.margin_notes[0]
    assert (note.notes, note.label_path, note.offset) == (("Effective date.",), ("kk",), 0)


def test_a_skipped_heading_keeps_its_page_break_at_the_start_of_the_body() -> None:
    parent = ET.fromstring(
        '<subsection><paragraph><num value="1">“(1) </num><heading>Coverage '
        '<inline><page identifier="/us/stat/139/307">139 STAT. 307</page>rules</inline>.—'
        "</heading><content>The State shall pay.</content></paragraph></subsection>"
    )
    rendered = _render_structural_element(parent[0], label_path=("xx", "1"))
    assert rendered.body == "The State shall pay."
    (page,) = rendered.page_breaks
    assert (page.page, page.printed, page.offset) == (
        StatutesPage("/us/stat/139/307", 139, 307),
        "139 STAT. 307",
        0,
    )

    ancestor = _render_structural_element(parent, label_path=("xx",))
    (ancestor_page,) = ancestor.page_breaks
    assert ancestor_page.page == page.page
    assert ancestor.body[ancestor_page.offset :].startswith("rules.—")


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ("<num>(1) <inline>Additional text</inline></num>", "<num> with child elements"),
        (
            "<heading>Coverage <span><table>Additional text</table></span></heading>",
            "unexpected <table> in <span>",
        ),
        ("<num>(1)</num><num>(2)</num>", "multiple own <num>"),
        (
            "<heading>Coverage.</heading><heading>Additional rules.</heading>",
            "multiple own <heading>",
        ),
    ],
)
def test_validates_the_rows_own_fields_before_omitting_them(fields: str, message: str) -> None:
    element = ET.fromstring(
        f"<paragraph>{fields}<content>The State shall pay.</content></paragraph>"
    )
    with pytest.raises(UslmRenderError, match=message):
        _render_structural_element(element, label_path=("1",))


def test_margin_note_rejects_text_in_a_paragraph_tail() -> None:
    element = ET.fromstring(
        "<paragraph><content>The State <sidenote><p>Deadline.</p>Notification."
        "</sidenote>shall pay.</content></paragraph>"
    )
    with pytest.raises(UslmRenderError, match="margin note text outside <p>"):
        _render_structural_element(element, label_path=("1",))


def test_margin_note_preserves_inline_tails_and_all_paragraphs() -> None:
    element = ET.fromstring(
        "<paragraph><content>The State <sidenote><p>See <ref>section 1</ref> for details.</p>\n"
        "<p>Deadline.</p>\n</sidenote>shall pay.</content></paragraph>"
    )
    rendered = _render_structural_element(element, label_path=("1",))
    assert rendered.body == "The State shall pay."
    (note,) = rendered.margin_notes
    assert note.notes == ("See section 1 for details.", "Deadline.")
    assert rendered.body[note.offset :] == "shall pay."


@pytest.mark.parametrize(
    ("marker", "tag"),
    [
        ('<page identifier="/us/stat/139/307"><sidenote><p>Note.</p></sidenote></page>', "page"),
        ('<sidenote><p>Note.<page identifier="/us/stat/139/307"/></p></sidenote>', "sidenote"),
    ],
)
def test_rejects_markers_nested_inside_marker_metadata(marker: str, tag: str) -> None:
    element = ET.fromstring(
        f"<paragraph><content>The State {marker}shall pay.</content></paragraph>"
    )
    with pytest.raises(UslmRenderError, match=f"nested marker in <{tag}>"):
        _render_structural_element(element, label_path=("1",))


@pytest.mark.parametrize("field", ["num", "heading"])
def test_omitted_own_fields_still_validate_the_closing_slot(field: str) -> None:
    element = ET.fromstring(f"<paragraph><{field}>Last text.</{field}></paragraph>")
    with pytest.raises(UslmRenderError, match="closing quote"):
        _render_structural_element(element, label_path=("1",), closing_slot=last_text_slot(element))


def test_selected_closing_quote_on_a_number_is_stripped() -> None:
    element = ET.fromstring(
        '<subsection><paragraph><num value="1">“(1)”</num></paragraph></subsection>'
    )
    slot = last_text_slot(element)
    parent = _render_structural_element(element, label_path=("xx",), closing_slot=slot)
    assert parent.body == "(1)"
    assert parent.stripped_open_quotes == 1
    assert parent.stripped_closing_quote
    row = _render_structural_element(element[0], label_path=("xx", "1"), closing_slot=slot)
    assert row.body == ""
    assert row.stripped_open_quotes == 0
    assert row.stripped_closing_quote


def test_space_before_punctuation_is_kept_unless_asked_to_drop_it() -> None:
    element = ET.fromstring(
        f'<paragraph xmlns="{NS}"><num value="1">(1)</num><chapeau>text—</chapeau>'
        '<subparagraph><num value="A">(A)</num><content>of 1986 .</content></subparagraph>'
        "</paragraph>"
    )
    kept = _render_structural_element(element, label_path=("1",))
    dropped = _render_structural_element(
        element, label_path=("1",), drop_space_before_punctuation=True
    )
    assert kept.body == "text—\n(A) of 1986 ."
    assert dropped.body == "text—\n(A) of 1986."


@pytest.mark.parametrize("normalize_punctuation", [False, True])
@pytest.mark.parametrize(
    ("content", "tag"),
    [
        ("1<sup>3</sup>⁄<sub>32</sub>-inch cotton", "sup"),
        ("H<sub>2</sub>O", "sub"),
    ],
)
def test_refuses_superscripts_and_subscripts(
    content: str, tag: str, normalize_punctuation: bool
) -> None:
    element = ET.fromstring(f'<paragraph xmlns="{NS}"><content>{content}</content></paragraph>')
    with pytest.raises(UslmRenderError, match=f"unexpected <{tag}> in <content>"):
        _render_structural_element(
            element, label_path=("1",), drop_space_before_punctuation=normalize_punctuation
        )


def _checked_arguments(quotation: ET.Element, label_path: tuple[str, ...]) -> dict[str, object]:
    """The arguments every checked render passes, for the given row."""
    return {
        "quotation": quotation,
        "label_path": label_path,
        "closing_slot": last_text_slot(quotation),
        "drop_space_before_punctuation": True,
    }


@pytest.fixture(scope="module")
def retained_uslm() -> bytes:
    root = Path(__file__).resolve().parents[1]
    return (root / "data/corpus/sources/us/statute" / SOURCE_VERSION / SOURCE_LEAF).read_bytes()


def test_verified_quotation_fingerprint_is_stable_and_all_twelve_rows_render(
    retained_uslm: bytes,
) -> None:
    quotation, _ = _quoted_subsection(ET.fromstring(retained_uslm))
    reparsed, _ = _quoted_subsection(ET.fromstring(retained_uslm))
    fingerprint = _quotation_fingerprint(quotation)
    assert tuple(VERIFIED_QUOTATIONS) == (fingerprint,)
    assert _quotation_fingerprint(reparsed) == fingerprint
    reparsed.tail = "Different surrounding amendment text."
    assert _quotation_fingerprint(reparsed) == fingerprint

    _, rows = render_rows(retained_uslm)
    assert len(rows) == 12
    assert tuple(row.citation_path for row in rows) == CITATION_PATHS


def test_synthetic_quotation_scope_error_names_the_five_known_patterns() -> None:
    _document, quotation, subsection = _parse()
    with pytest.raises(UslmRenderError, match="verified only for the listed quotation") as error:
        render_structural_element(subsection, quotation=quotation, label_path=("zz",))
    message = str(error.value)
    for phrase in (
        "drop_space_before_punctuation",
        "(A).25",
        "5 p.m.— filing",
        "foreign-namespace <page> or <sidenote>",
        "<br/>",
        "page_in_effect",
    ):
        assert phrase in message


def test_scope_guard_refuses_the_retained_section_10310_quotation(retained_uslm: bytes) -> None:
    document = ET.fromstring(retained_uslm)
    amending_element = next(
        node
        for node in document.iter()
        if node.get("identifier") == "/us/pl/119/21/tI/stC/s10310/3/D"
    )
    quotation = next(amending_element.iter(f"{{{NS}}}quotedContent"))
    with pytest.raises(UslmRenderError, match="fingerprint is not listed"):
        render_structural_element(quotation[0], **_checked_arguments(quotation, ("2",)))


def test_scope_guard_refuses_a_one_character_change_inside_the_quotation(
    retained_uslm: bytes,
) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    chapeau = next(node for node in subsection.iter(f"{{{NS}}}chapeau") if node.text)
    assert chapeau.text is not None and "Except" in chapeau.text
    chapeau.text = chapeau.text.replace("Except", "except", 1)
    with pytest.raises(UslmRenderError, match="fingerprint is not listed"):
        render_structural_element(subsection, **_checked_arguments(quotation, ("xx",)))


def test_scope_guard_refuses_an_element_outside_the_verified_quotation(
    retained_uslm: bytes,
) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    outside = deepcopy(subsection)
    with pytest.raises(UslmRenderError, match="not a structural element of the quotation"):
        render_structural_element(outside, **_checked_arguments(quotation, ("xx",)))


def test_scope_guard_requires_the_quotation_to_be_quoted_content(retained_uslm: bytes) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    arguments = {**_checked_arguments(quotation, ("xx",)), "quotation": subsection}
    with pytest.raises(UslmRenderError, match="not a <quotedContent>"):
        render_structural_element(subsection, **arguments)


def test_scope_guard_renders_exactly_the_twelve_checked_rows(retained_uslm: bytes) -> None:
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    nodes = list(_structural_nodes(quotation))
    assert len(nodes) == 112
    accepted = []
    for node, path in nodes:
        try:
            rendered = render_structural_element(node, **_checked_arguments(quotation, path))
        except UslmRenderError as error:
            assert "is not a checked row" in str(error)
        else:
            accepted.append((path, rendered))
    _, rows = render_rows(retained_uslm)
    assert [path for path, _rendered in accepted] == [
        ("xx",),
        *(("xx", str(number)) for number in range(1, 12)),
    ]
    assert [rendered for _path, rendered in accepted] == [row.rendered for row in rows]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("label_path", "is not the row's own"),
        ("closing_slot_none", "closing_slot must be"),
        ("closing_slot_other", "closing_slot must be"),
        ("drop_space_false", "drop_space_before_punctuation must be True"),
        ("drop_space_one", "drop_space_before_punctuation must be True"),
    ],
)
def test_scope_guard_refuses_a_checked_row_with_other_arguments(
    retained_uslm: bytes, change: str, reason: str
) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    paragraphs = {
        num_value(child): child for child in subsection if local_name(child.tag) == "paragraph"
    }
    arguments = _checked_arguments(quotation, ("xx", "11"))
    assert render_structural_element(paragraphs["11"], **arguments).stripped_closing_quote
    changed: dict[str, object] = {
        "label_path": {"label_path": ("xx", "10")},
        "closing_slot_none": {"closing_slot": None},
        "closing_slot_other": {"closing_slot": last_text_slot(paragraphs["1"])},
        "drop_space_false": {"drop_space_before_punctuation": False},
        "drop_space_one": {"drop_space_before_punctuation": 1},
    }[change]
    with pytest.raises(UslmRenderError, match=reason):
        render_structural_element(paragraphs["11"], **{**arguments, **changed})


@pytest.mark.parametrize("which", ["quotation_none", "quotation_tree", "element_none"])
def test_scope_guard_raises_its_own_error_for_non_elements(
    retained_uslm: bytes, which: str
) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    arguments = _checked_arguments(quotation, ("xx",))
    element: object = subsection
    if which == "quotation_none":
        arguments["quotation"] = None
    elif which == "quotation_tree":
        arguments["quotation"] = ET.ElementTree(quotation)
    else:
        element = None
    with pytest.raises(UslmRenderError, match="must be ElementTree elements"):
        render_structural_element(element, **arguments)  # type: ignore[arg-type]


def test_scope_guard_raises_its_own_error_for_a_quotation_without_canonical_xml(
    retained_uslm: bytes,
) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    arguments = _checked_arguments(quotation, ("xx",))
    chapeau = next(node for node in subsection.iter(f"{{{NS}}}chapeau") if node.text)
    assert chapeau.text is not None
    chapeau.text = "\x0c" + chapeau.text
    with pytest.raises(UslmRenderError, match="has no canonical XML"):
        render_structural_element(subsection, **arguments)


def test_scope_guard_refuses_a_comment_kept_in_the_quotation(retained_uslm: bytes) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    arguments = _checked_arguments(quotation, ("xx",))
    subsection.insert(2, ET.Comment("note"))
    with pytest.raises(UslmRenderError, match="fingerprint is not listed"):
        render_structural_element(subsection, **arguments)
    with pytest.raises(UslmRenderError, match="non-string tag"):
        last_text_slot(quotation)


def test_scope_guard_renders_from_a_copy_of_the_fingerprinted_quotation(
    retained_uslm: bytes,
) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    arguments = _checked_arguments(quotation, ("xx",))
    element, own_path, slot, verified = _checked_render(subsection, **arguments)
    assert verified is VERIFIED_QUOTATIONS[_quotation_fingerprint(quotation)]
    assert own_path == ("xx",) and type(own_path) is tuple
    assert element is not subsection
    assert not any(node is element for node in quotation.iter())
    assert slot[0] is not last_text_slot(quotation)[0]
    assert slot[1] == last_text_slot(quotation)[1]


def _paragraph(quotation: ET.Element, number: str) -> ET.Element:
    return next(node for node, path in _structural_nodes(quotation) if path == ("xx", number))


def test_scope_guard_compares_label_path_as_a_plain_tuple(retained_uslm: bytes) -> None:
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))

    class AlwaysEqual(tuple):  # type: ignore[type-arg]
        def __ne__(self, other: object) -> bool:
            return False

        def __eq__(self, other: object) -> bool:
            return True

    class AlwaysEqualText(str):
        def __ne__(self, other: object) -> bool:
            return False

    paragraph = _paragraph(quotation, "11")
    for label_path in (
        AlwaysEqual(("xx", "10")),
        ("xx", AlwaysEqualText("10")),
        ["xx", "11"],
    ):
        arguments = _checked_arguments(quotation, ("xx", "11"))
        arguments["label_path"] = label_path
        with pytest.raises(UslmRenderError, match="is not the row's own"):
            render_structural_element(paragraph, **arguments)


def test_scope_guard_renders_plain_text_whatever_the_callers_text_objects(
    retained_uslm: bytes,
) -> None:
    _, rows = render_rows(retained_uslm)
    expected = rows[11].rendered
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    paragraph = _paragraph(quotation, "11")
    number = next(child for child in paragraph.iter() if local_name(child.tag) == "num")
    first = next(child for child in number.iter() if child.text)

    class WrongText(str):
        def split(self, *args: object, **kwargs: object) -> list[str]:  # type: ignore[override]
            return ["\u201c(Z)"]

        def strip(self, *args: object, **kwargs: object) -> str:  # type: ignore[override]
            return ""

    first.text = WrongText(first.text or "")
    rendered = render_structural_element(paragraph, **_checked_arguments(quotation, ("xx", "11")))
    assert rendered == expected


def test_scope_guard_refuses_subclassed_elements(retained_uslm: bytes) -> None:
    quotation, subsection = _quoted_subsection(ET.fromstring(retained_uslm))

    class Element(ET.Element):
        pass

    arguments = _checked_arguments(quotation, ("xx",))
    with pytest.raises(UslmRenderError, match="must be ElementTree elements"):
        render_structural_element(Element("x"), **arguments)


def test_scope_guard_renders_plain_strings_for_qname_attribute_values(
    retained_uslm: bytes,
) -> None:
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    page = next(
        node
        for node in quotation.iter()
        if local_name(node.tag) == "page" and node.get("identifier")
    )
    page.set("identifier", ET.QName(page.get("identifier") or ""))
    # The QName serializes to the same canonical XML, so the parsed copy holds
    # a plain string and the render is the checked one.
    _, rows = render_rows(retained_uslm)
    paragraph = _paragraph(quotation, "11")
    assert (
        render_structural_element(paragraph, **_checked_arguments(quotation, ("xx", "11")))
        == rows[11].rendered
    )


def test_scope_guard_renders_the_checked_text_for_parser_equivalent_line_endings(
    retained_uslm: bytes,
) -> None:
    _, rows = render_rows(retained_uslm)
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    tail_node = next(
        node for node in _paragraph(quotation, "1").iter() if node.tail and "\n" in node.tail
    )
    tail_node.tail = (tail_node.tail or "").replace("\n", "\r", 1)
    assert (
        render_structural_element(
            _paragraph(quotation, "1"), **_checked_arguments(quotation, ("xx", "1"))
        )
        == rows[1].rendered
    )


class _RaisingRepr(str):
    def __repr__(self) -> str:
        raise RuntimeError("repr")


class _RaisingRsplit(str):
    def rsplit(self, *args: object, **kwargs: object) -> list[str]:  # type: ignore[override]
        raise RuntimeError("rsplit")


class _RaisingReprError(Exception):
    def __repr__(self) -> str:
        raise RuntimeError("error repr")

    def __str__(self) -> str:
        raise RuntimeError("error str")


class _RaisingContains(str):
    def __contains__(self, item: object) -> bool:  # type: ignore[override]
        raise _RaisingReprError()


def test_scope_guard_refuses_unformattable_label_paths(retained_uslm: bytes) -> None:
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    paragraph = _paragraph(quotation, "11")
    for label_path in (("xx", 10**5000), ("xx", _RaisingRepr("11")), (_RaisingRepr("xx"),)):
        arguments = _checked_arguments(quotation, ("xx", "11"))
        arguments["label_path"] = label_path
        with pytest.raises(UslmRenderError, match="is not the row's own"):
            render_structural_element(paragraph, **arguments)


def test_scope_guard_refuses_a_subclassed_quotation_tag(retained_uslm: bytes) -> None:
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    arguments = _checked_arguments(quotation, ("xx", "11"))
    quotation.tag = _RaisingRsplit(quotation.tag)
    with pytest.raises(UslmRenderError, match="not a <quotedContent>"):
        render_structural_element(_paragraph(quotation, "11"), **arguments)


def test_scope_guard_refuses_an_attribute_that_raises_while_serializing(
    retained_uslm: bytes,
) -> None:
    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    arguments = _checked_arguments(quotation, ("xx", "11"))
    quotation.set("extra", _RaisingContains("value"))
    with pytest.raises(UslmRenderError, match="has no canonical XML"):
        render_structural_element(_paragraph(quotation, "11"), **arguments)


def test_scope_guard_converts_any_exception_raised_while_checking(
    retained_uslm: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    from axiom_corpus.corpus import uslm_quoted_content

    def raising(*args: object, **kwargs: object) -> object:
        raise _RaisingReprError()

    quotation, _subsection = _quoted_subsection(ET.fromstring(retained_uslm))
    paragraph = _paragraph(quotation, "11")
    monkeypatch.setattr(uslm_quoted_content, "_structural_nodes", raising)
    with pytest.raises(UslmRenderError, match="raised an exception while it was checked"):
        render_structural_element(paragraph, **_checked_arguments(quotation, ("xx", "11")))
