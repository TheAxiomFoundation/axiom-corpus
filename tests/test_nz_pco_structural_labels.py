"""NZ PCO structural labels render as legislation.govt.nz publishes them (#822).

PCO XML marks a subsection or paragraph label ``<label denominator="yes">1</label>``
and the publisher prints it ``(1)``, on the same line as its text. Extractions
wrote it bare, on a line of its own (``1\nA person is entitled…``). A label the
publisher prints as written (``denominator="no"``: ``A.``, ``(1)–(3)``) stays as
written, and an empty label prints nothing.

``_legacy_render_nz_pco_legal_text`` below is the renderer as it stood before
this change, verbatim. ``bare_structural_labels`` replays it, so a scope made
with it can be re-extracted byte for byte; the differential test checks that.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.converters import nz_pco
from axiom_corpus.converters.nz_pco import NZPCOConverter, render_nz_pco_legal_text
from axiom_corpus.corpus import nz_legislation

# Social Security Act 2018 s 72(1), verbatim from the retained source of
# nz/statute/2026-06-16-rulespec-nz-pco (act/public/2018/0032/wholeof.xml).
_SECTION_72_1 = (
    '<subprov><label denominator="yes">1</label><para><text>A person is entitled to a winter '
    "energy payment for 1 or more days during the winter period if, for those days,—</text>"
    '<label-para><label denominator="yes">a</label><para><text>the person is receiving a '
    "qualifying benefit (or a portion of it), either as the person granted that benefit or as "
    "the spouse or partner of that person; and</text></para></label-para><label-para>"
    '<label denominator="yes">b</label><para><text>the qualifying benefit (or a portion of it) '
    "is payable to the person; and</text></para></label-para><label-para>"
    '<label denominator="yes">c</label><para><text>the person is not disqualified under '
    "subsection (2).</text></para></label-para></para></subprov>"
)


def _act(body: str) -> str:
    return f"""<act id="DLM1" year="2018" act.no="32" act.type="public" date.assent="2018-04-26"
        stage="in-force" date.as.at="2026-06-16"><cover><title>Fixture Act 2018</title></cover>
      <body><prov id="P72"><label denominator="yes">72</label>
        <heading>Winter energy payment: requirements</heading>
        <prov.body>{body}</prov.body></prov></body></act>"""


def _body(body: str) -> str:
    return NZPCOConverter().parse_xml(_act(body)).provisions[0].text


def test_section_72_labels_render_as_published() -> None:
    assert _body(_SECTION_72_1) == (
        "(1) A person is entitled to a winter energy payment for 1 or more days during the "
        "winter period if, for those days,—\n"
        "(a) the person is receiving a qualifying benefit (or a portion of it), either as the "
        "person granted that benefit or as the spouse or partner of that person; and\n"
        "(b) the qualifying benefit (or a portion of it) is payable to the person; and\n"
        "(c) the person is not disqualified under subsection (2)."
    )


def test_bare_labels_replay_the_released_layout() -> None:
    with nz_pco.bare_structural_labels():
        body = _body(_SECTION_72_1)

    # The opening of the released row nz/statute/act/public/2018/0032/section/72.
    assert body.startswith(
        "1\nA person is entitled to a winter energy payment for 1 or more days during the "
        "winter period if, for those days,—\na\nthe person is receiving a qualifying benefit"
    )
    # The replay ends with its block and leaves published rendering on for the next caller.
    assert _body(_SECTION_72_1).startswith("(1) A person is entitled")


def test_each_subsection_and_paragraph_starts_its_own_line() -> None:
    body = _body(
        '<subprov><label denominator="yes">1</label><para><text>First.</text>'
        '<label-para><label denominator="yes">a</label><para><text>alpha:</text>'
        '<label-para><label denominator="yes">i</label><para><text>nested one;</text></para>'
        '</label-para><label-para><label denominator="yes">ii</label><para><text>nested two.'
        "</text></para></label-para></para></label-para></para></subprov>"
        '<subprov><label denominator="yes">2</label><para><text>Second.</text></para></subprov>'
    )
    assert body.split("\n") == [
        "(1) First.",
        "(a) alpha:",
        "(i) nested one;",
        "(ii) nested two.",
        "(2) Second.",
    ]


def test_labels_the_publisher_prints_as_written_stay_as_written() -> None:
    body = _body(
        # A range the publisher wraps: (2)–(14).
        '<subprov><label denominator="yes">2)–(14</label><para><text>[Repealed]</text></para>'
        "</subprov>"
        # Labels printed as written, and labels that print nothing.
        '<subprov><label denominator="no">(15)–(17)</label><para><text>[Repealed]</text>'
        "</para></subprov>"
        '<subprov><label denominator="no"/><para><text>Unlabelled subsection.</text>'
        '<label-para><label denominator="no">A.</label><para><text>lettered item.</text>'
        '</para></label-para><label-para><label denominator="yes"/><para><text>unlabelled '
        "item.</text></para></label-para></para></subprov>"
    )
    assert body.split("\n") == [
        "(2)–(14) [Repealed]",
        "(15)–(17) [Repealed]",
        "Unlabelled subsection.",
        "A. lettered item.",
        "unlabelled item.",
    ]


def test_schedule_definition_paragraphs_render_as_published() -> None:
    definition = ET.fromstring(
        '<def-para id="D1"><para><text><def-term id="T1">eligible person</def-term> means a '
        'person who—</text><label-para><label denominator="yes">a</label><para><text>is '
        'resident; and</text></para></label-para><label-para><label denominator="yes">b</label>'
        "<para><text>is aged 18 or over</text></para></label-para></para></def-para>"
    )

    assert nz_legislation._source_element_text(definition) == (
        "eligible person means a person who— (a) is resident; and (b) is aged 18 or over"
    )
    with nz_pco.bare_structural_labels():
        assert nz_legislation._source_element_text(definition) == (
            "eligible person means a person who— a is resident; and b is aged 18 or over"
        )


# --- Differential: the bare replay is the renderer as it stood --------------


def _legacy_render_nz_pco_legal_text(
    element: ET.Element,
    *,
    excluded: set[ET.Element] | None = None,
) -> str:
    """Render substantive PCO text once in document order.

    Labels, definitions, provisos, equations, examples, amendment text, and
    later text/tail siblings are retained. Tables use stable row/cell
    formatting. Editorial, accessibility, and amendment-history metadata are
    excluded from every caller, including schedule hierarchy bodies.
    """
    excluded_elements = excluded or set()
    skipped_tags = {
        "amends-note",
        "editorial-note",
        "history",
        "history-note",
        "ird.aids",
        "notes",
        "struckoutwords",
        "summary",
    }
    block_tags = {
        "amend",
        "def-para",
        "eqn",
        "eqn-line",
        "example",
        "heading",
        "item",
        "label-para",
        "label-para.crosshead",
        "legtable",
        "list",
        "para",
        "proviso",
        "quote",
        "row",
        "subheading",
        "subprov",
        "subprov.crosshead",
        "table",
        "tbody",
        "tgroup",
        "thead",
        "variable-def",
    }

    def clean(value: str | None) -> str:
        return " ".join((value or "").split())

    def join(parts: list[tuple[str, bool]]) -> str:
        output = ""
        prior_block = False
        for value, is_block in parts:
            value = value.strip()
            if not value:
                continue
            if output:
                separator = "\n" if prior_block or is_block else " "
                if output.rsplit("\n", 1)[-1].strip().startswith("(") and is_block:
                    separator = " "
                output += separator
            output += value
            prior_block = is_block
        return "\n".join(
            line for line in (" ".join(line.split()) for line in output.splitlines()) if line
        )

    def render(node: ET.Element) -> str:
        if node in excluded_elements or node.tag in skipped_tags:
            return ""
        if node.tag == "brk":
            return "\n"
        if node.tag == "row":
            cells = [child for child in node if child.tag == "entry"] or list(node)
            rendered_cells: list[str] = []
            for cell in cells:
                rendered_cell = " ".join(render(cell).split())
                if rendered_cell:
                    rendered_cells.append(rendered_cell)
            return " | ".join(rendered_cells)

        parts: list[tuple[str, bool]] = []
        if value := clean(node.text):
            parts.append((value, False))
        for child in node:
            child_text = render(child)
            if child_text.strip():
                parts.append((child_text, child.tag in block_tags))
            if tail := clean(child.tail):
                parts.append((tail, False))
        return join(parts)

    return render(element).strip()


_LABEL_TEXT = st.sampled_from(
    ("1", "2", "a", "b", "ca", "i", "ii", "A", "2)–(14", "(1)", "A.", "“(2)", "")
)
_TEXT = st.text(alphabet="abcdefgh (),.;—", min_size=0, max_size=12)
_DENOMINATOR = st.sampled_from(("yes", "no", None))


@st.composite
def _label(draw: st.DrawFn) -> ET.Element:
    label = ET.Element("label")
    denominator = draw(_DENOMINATOR)
    if denominator is not None:
        label.set("denominator", denominator)
    label.text = draw(_LABEL_TEXT)
    return label


def _text_element(value: str, tail: str = "") -> ET.Element:
    element = ET.Element("text")
    element.text = value
    element.tail = tail
    return element


_LEAVES = st.builds(_text_element, _TEXT, st.sampled_from(("", " ", " tail ")))


def _container(tag: str, children: list[ET.Element], label: ET.Element | None) -> ET.Element:
    element = ET.Element(tag)
    if label is not None:
        element.append(label)
    for child in children:
        element.append(child)
    return element


def _branches(children: st.SearchStrategy[ET.Element]) -> st.SearchStrategy[ET.Element]:
    kids = st.lists(children, max_size=3)
    return st.one_of(
        st.builds(_container, st.just("para"), kids, st.none()),
        st.builds(_container, st.just("subprov"), kids, st.one_of(st.none(), _label())),
        st.builds(_container, st.just("label-para"), kids, st.one_of(st.none(), _label())),
        st.builds(_container, st.just("item"), kids, st.one_of(st.none(), _label())),
        st.builds(_container, st.just("list"), kids, st.none()),
        st.builds(_container, st.just("proviso"), kids, st.none()),
    )


_TREES = st.recursive(_LEAVES, _branches, max_leaves=14).map(
    lambda tree: _container("prov.body", [tree], None)
)


@settings(max_examples=300, deadline=None)
@given(tree=_TREES)
def test_bare_replay_matches_the_legacy_renderer(tree: ET.Element) -> None:
    with nz_pco.bare_structural_labels():
        replayed = render_nz_pco_legal_text(tree)

    assert replayed == _legacy_render_nz_pco_legal_text(tree)


def _structural_labels(tree: ET.Element) -> list[tuple[str, str]]:
    """(bare, published) text of each structural label, in document order."""
    labels = []
    for parent in tree.iter():
        if parent.tag not in ("subprov", "label-para", "item"):
            continue
        for child in parent:
            if child.tag == "label":
                bare = " ".join("".join(child.itertext()).split())
                wrapped = child.get("denominator") == "yes" and not (
                    bare.startswith("(") and bare.endswith(")")
                )
                labels.append((bare, f"({bare})" if bare and wrapped else bare))
    return labels


@settings(max_examples=300, deadline=None)
@given(tree=_TREES)
def test_published_rendering_changes_only_how_labels_print(tree: ET.Element) -> None:
    published = render_nz_pco_legal_text(tree)
    bare = _legacy_render_nz_pco_legal_text(tree)

    # The same text in the same order: only the labels differ, and only in
    # their parentheses and the line break the bare layout put after them.
    removed = "".join(re.findall(r"[()]", bare))
    added = "".join(re.findall(r"[()]", published))
    assert re.sub(r"[()\s]", "", published) == re.sub(r"[()\s]", "", bare)
    expected_parentheses = sum(
        2 for bare_label, shown in _structural_labels(tree) if shown != bare_label
    )
    assert len(added) - len(removed) == expected_parentheses
