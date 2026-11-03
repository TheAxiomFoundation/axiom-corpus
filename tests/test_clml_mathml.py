"""MathML in CLML provisions renders its structure, or says what it could not render.

``_mathml_text`` used to join a formula's presentation tokens with spaces, so
``<mfrac><mi>M</mi><mi>W</mi></mfrac>`` read ``M W`` and
``<msub><mi>x</mi><mn>1</mn></msub>`` read ``x 1`` (#930). The flat products
in the UK child-definition scopes (``M x W`` and ``M × W`` in the Tax-Free
Childcare Regulations 2015, reg 9) must still render exactly as they did, and
``alttext`` still wins.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.uk_legislation import extract_uk_legislation_sections
from axiom_corpus.parsers import clml
from axiom_corpus.parsers.clml import parse_section

_LEG_NS = "http://www.legislation.gov.uk/namespaces/legislation"
_MATH_NS = "http://www.w3.org/1998/Math/MathML"


def _math(inner: str, **attributes: str) -> ET.Element:
    attrs = "".join(f' {name}="{value}"' for name, value in attributes.items())
    return ET.fromstring(f'<math xmlns="{_MATH_NS}"{attrs}>{inner}</math>')


def _rendered(inner: str, **attributes: str) -> str:
    return str(clml._mathml_text(_math(inner, **attributes)))


def _flat_rendering(element: ET.Element) -> str:
    """The rendering before this change: every presentation token, space-separated."""
    return " ".join(token for text in element.itertext() for token in text.split())


def _provision_xml(content: str, *, uri: str) -> str:
    return f"""<Legislation xmlns="{_LEG_NS}" xmlns:math="{_MATH_NS}"
        DocumentURI="{uri}" RestrictExtent="E+W+S+N.I.">
      <Secondary><Body><P1 DocumentURI="{uri}"><Pnumber>1</Pnumber>
        <P1para>{content}</P1para>
      </P1></Body></Secondary>
    </Legislation>"""


# --- Each presentation form ---------------------------------------------------


@pytest.mark.parametrize(
    ("inner", "expected"),
    [
        # The review probes from #930.
        ("<mfrac><mi>M</mi><mi>W</mi></mfrac>", "M/W"),
        ("<msub><mi>x</mi><mn>1</mn></msub>", "x_1"),
        ("<msup><mi>x</mi><mn>2</mn></msup>", "x^2"),
        ("<msubsup><mi>x</mi><mi>i</mi><mn>2</mn></msubsup>", "x_i^2"),
        ("<msqrt><mi>a</mi><mo>+</mo><mi>b</mi></msqrt>", "√(a + b)"),
        ("<mroot><mi>x</mi><mn>3</mn></mroot>", "root(x, 3)"),
        ("<mfenced><mi>a</mi><mi>b</mi></mfenced>", "(a, b)"),
        (
            '<mfenced open="[" close="]" separators=";"><mi>a</mi><mi>b</mi><mi>c</mi></mfenced>',
            "[a; b; c]",
        ),
        # An operand longer than one name or number takes parentheses.
        (
            "<mfrac><mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow>"
            "<mrow><mi>c</mi><mo>−</mo><mi>d</mi></mrow></mfrac>",
            "(a + b)/(c − d)",
        ),
        ("<mfrac><mi>a</mi><mfrac><mi>b</mi><mi>c</mi></mfrac></mfrac>", "a/(b/c)"),
        ("<msup><mi>e</mi><mrow><mo>−</mo><mi>x</mi></mrow></msup>", "e^(− x)"),
        (
            "<mrow><mi>P</mi><mo>=</mo><msub><mi>p</mi><mn>1</mn></msub><mo>+</mo>"
            "<msub><mi>p</mi><mn>2</mn></msub></mrow>",
            "P = p_1 + p_2",
        ),
    ],
)
def test_presentation_forms_render_their_structure(inner: str, expected: str) -> None:
    assert _rendered(inner) == expected


def test_universal_credit_regulation_73_2a_keeps_its_fraction() -> None:
    """legislation.gov.uk's markup for UC Regs 2013 reg 73(2A), as served on 2026-11-02."""
    inner = (
        '<semantics definitionURL="" encoding=""> <mrow> <mi> N</mi> <mo> ×</mo> <mrow> '
        "<mo> (</mo> <mrow> <mfrac> <mrow> <mi> M</mi> <mo> ×</mo> <mn> 12</mn> </mrow> "
        "<mrow> <mn> 365</mn> </mrow> </mfrac> </mrow> <mo> )</mo> </mrow> </mrow> "
        '<annotation encoding=""/> </semantics>'
    )
    element = _math(inner, overflow="scroll")

    assert _flat_rendering(element) == "N × ( M × 12 365 )"
    assert clml._mathml_text(element) == "N × ( (M × 12)/365 )"


def test_annotations_are_not_read_as_presentation() -> None:
    inner = (
        "<semantics><mfrac><mi>a</mi><mi>b</mi></mfrac>"
        '<annotation encoding="application/x-tex">\\frac{a}{b}</annotation></semantics>'
    )
    assert _rendered(inner) == "a/b"


# --- Pins: the flat products of the child-definition scopes ------------------
# Tax-Free Childcare Regulations 2015 reg 9, verbatim from legislation.gov.uk.

_TFC_ANNUAL = (
    '<math:math xmlns:math="http://www.w3.org/1998/Math/MathML" display="block">'
    "<math:mrow><math:mi>M</math:mi><math:mi>x</math:mi><math:mi>W</math:mi></math:mrow>"
    "</math:math>"
)
_TFC_WEEKLY = (
    '<math:math xmlns:math="http://www.w3.org/1998/Math/MathML" overflow="scroll">'
    "<math:mrow><math:mi> M</math:mi><math:mo> ×</math:mo><math:mi> W</math:mi></math:mrow>"
    "</math:math>"
)


@pytest.mark.parametrize(("markup", "expected"), [(_TFC_ANNUAL, "M x W"), (_TFC_WEEKLY, "M × W")])
def test_child_definition_flat_products_render_exactly_as_before(
    markup: str, expected: str
) -> None:
    element = ET.fromstring(markup)

    assert clml._mathml_text(element) == expected == _flat_rendering(element)
    assert clml.unrendered_mathml_elements(element) == []


def test_child_definition_formulas_leave_the_provision_text_as_before() -> None:
    xml = _provision_xml(
        f"""<P2><Pnumber>5A</Pnumber><P2para>
          <Text>The annual threshold is the product of the calculation—</Text>
          <Formula>{_TFC_ANNUAL}<Where><Para><Text>where M is annual income.</Text></Para></Where>
          </Formula></P2para></P2>
        <P2><Pnumber>6</Pnumber><P2para>
          <Text>The weekly threshold is the product of the calculation—</Text>
          <Formula>{_TFC_WEEKLY}<Where><Para><Text>where M is weekly income.</Text></Para></Where>
          </Formula></P2para></P2>""",
        uri="http://www.legislation.gov.uk/uksi/2015/448/regulation/9",
    )
    section = parse_section(xml)

    assert section.text.split("\n") == [
        "The annual threshold is the product of the calculation—",
        "M x W",
        "where M is annual income.",
        "The weekly threshold is the product of the calculation—",
        "M × W",
        "where M is weekly income.",
    ]
    assert section.unrendered_mathml == []


# --- alttext, and what stays unrendered --------------------------------------


def test_alttext_still_wins_over_the_structure() -> None:
    element = _math("<mfrac><mi>M</mi><mi>W</mi></mfrac>", alttext="M divided by W")

    assert clml._mathml_text(element) == "M divided by W"
    assert clml.unrendered_mathml_elements(element) == []


@pytest.mark.parametrize(
    ("inner", "expected_text", "unrendered"),
    [
        (
            "<munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>n</mi>"
            "</munderover><msub><mi>x</mi><mi>i</mi></msub>",
            "∑ i = 1 n x_i",
            ["munderover"],
        ),
        # A fraction without a rule is a binomial coefficient or a stack, not a/b.
        ('<mfrac linethickness="0"><mi>n</mi><mi>k</mi></mfrac>', "n k", ["mfrac"]),
        (
            "<mtable><mtr><mtd><mi>a</mi></mtd><mtd><mi>b</mi></mtd></mtr></mtable>",
            "a b",
            ["mtable", "mtd", "mtr"],
        ),
        # A form with the wrong number of children cannot be read as its structure.
        ("<mfrac><mi>a</mi></mfrac>", "a", ["mfrac"]),
    ],
)
def test_forms_without_a_notation_keep_their_tokens_and_are_named(
    inner: str, expected_text: str, unrendered: list[str]
) -> None:
    element = _math(inner)

    assert clml._mathml_text(element) == expected_text
    assert clml.unrendered_mathml_elements(element) == unrendered


def test_unrendered_mathml_is_recorded_on_the_provision_row() -> None:
    uri = "http://www.legislation.gov.uk/uksi/2015/448/regulation/10"
    unrendered = _provision_xml(
        "<Text>The total is <math:math><math:munder><math:mo>∑</math:mo><math:mi>i</math:mi>"
        "</math:munder><math:msub><math:mi>x</math:mi><math:mi>i</math:mi></math:msub>"
        "</math:math>.</Text>",
        uri=uri,
    )
    rendered = _provision_xml(
        "<Text>The rate is <math:math><math:mfrac><math:mi>M</math:mi><math:mi>W</math:mi>"
        "</math:mfrac></math:math>.</Text>",
        uri=uri.replace("/10", "/11"),
    )
    with TemporaryDirectory() as directory:
        base = Path(directory)
        paths = []
        for name, xml in (("reg-10.xml", unrendered), ("reg-11.xml", rendered)):
            path = base / name
            path.write_text(xml, encoding="utf-8")
            paths.append(path)
        report = extract_uk_legislation_sections(
            CorpusArtifactStore(base / "corpus"),
            version="2026-11-02-mathml-test",
            source_xmls=paths,
            source_as_of="2026-11-02",
            expression_date="2026-04-06",
        )
        rows = {
            row["citation_path"]: row
            for class_report in report.class_reports
            for row in map(json.loads, class_report.provisions_path.read_text().splitlines())
        }

    by_label = {path.rsplit("/", 1)[-1]: row for path, row in rows.items()}
    assert by_label["10"]["body"] == "The total is ∑ i x_i."
    assert by_label["10"]["metadata"]["unrendered_mathml"] == ["munder"]
    assert by_label["11"]["body"] == "The rate is M/W."
    assert "unrendered_mathml" not in by_label["11"]["metadata"]


# --- Properties ---------------------------------------------------------------
# A generated tree is plain data: ("token", name, text) or (name, attributes,
# children). Annotations hold text that is not presentation.

_TOKEN_NAMES = ("mi", "mn", "mo", "mtext")
_UNSUPPORTED = ("munder", "mover", "munderover", "menclose", "mphantom", "mtable")
_TOKEN_TEXT = st.text(alphabet="abMNWx0123456789+−×=()∑.,", min_size=1, max_size=4)
_PADDING = st.sampled_from(("", " ", "  "))

Tree = Any


def _tokens_leaf() -> st.SearchStrategy[Tree]:
    return st.tuples(
        st.just("token"), st.sampled_from(_TOKEN_NAMES), _PADDING, _TOKEN_TEXT, _PADDING
    ).map(lambda leaf: ("token", leaf[1], f"{leaf[2]}{leaf[3]}{leaf[4]}"))


def _node(name: str, children: Any, **attributes: str) -> Tree:
    return (name, attributes, tuple(children))


def _structures(children: st.SearchStrategy[Tree]) -> st.SearchStrategy[Tree]:
    two = st.tuples(children, children)
    return st.one_of(
        st.lists(children, max_size=4).map(lambda kids: _node("mrow", kids)),
        two.map(lambda kids: _node("mfrac", kids)),
        two.map(lambda kids: _node("mfrac", kids, linethickness="0")),
        two.map(lambda kids: _node("msub", kids)),
        two.map(lambda kids: _node("msup", kids)),
        st.tuples(children, children, children).map(lambda kids: _node("msubsup", kids)),
        st.lists(children, max_size=3).map(lambda kids: _node("msqrt", kids)),
        two.map(lambda kids: _node("mroot", kids)),
        st.lists(children, max_size=3).map(lambda kids: _node("mfenced", kids)),
        st.tuples(children, _TOKEN_TEXT).map(
            lambda pair: _node("semantics", [pair[0], ("annotation", {}, (("text", pair[1]),))])
        ),
        st.tuples(st.sampled_from(_UNSUPPORTED), st.lists(children, min_size=1, max_size=3)).map(
            lambda pair: _node(pair[0], pair[1])
        ),
    )


_TREES = st.recursive(_tokens_leaf(), _structures, max_leaves=12)
_FLAT_TREES = st.recursive(
    _tokens_leaf(),
    lambda children: st.lists(children, max_size=4).map(lambda kids: _node("mrow", kids)),
    max_leaves=12,
)


def _element(tree: Tree) -> ET.Element:
    if tree[0] == "token":
        element = ET.Element(f"{{{_MATH_NS}}}{tree[1]}")
        element.text = tree[2]
        return element
    name, attributes, children = tree
    element = ET.Element(f"{{{_MATH_NS}}}{name}", attributes)
    for child in children:
        if child[0] == "text":
            element.text = child[1]
        else:
            element.append(_element(child))
    return element


def _presentation_tokens(tree: Tree) -> list[str]:
    if tree[0] == "token":
        return tree[2].split()
    name, _attributes, children = tree
    if name == "annotation":
        return []
    return [token for child in children for token in _presentation_tokens(child)]


def _unsupported_names(tree: Tree) -> set[str]:
    if tree[0] in ("token", "text"):
        return set()
    name, attributes, children = tree
    names = {name} if name in _UNSUPPORTED or attributes.get("linethickness") == "0" else set()
    for child in children:
        names |= _unsupported_names(child)
    return names


def _in_order(tokens: list[str], text: str) -> bool:
    position = 0
    for token in tokens:
        found = text.find(token, position)
        if found < 0:
            return False
        position = found + len(token)
    return True


@settings(max_examples=300, deadline=None)
@given(tree=_TREES)
def test_rendering_keeps_every_presentation_token_in_order(tree: Tree) -> None:
    math = ET.Element(f"{{{_MATH_NS}}}math")
    math.append(_element(tree))

    text = clml._mathml_text(math)

    assert _in_order(_presentation_tokens(tree), text), text
    assert text == text.strip() and "  " not in text
    assert set(clml.unrendered_mathml_elements(math)) == _unsupported_names(tree)


@settings(max_examples=200, deadline=None)
@given(tree=_FLAT_TREES)
def test_a_flat_row_renders_as_the_flat_rendering_did(tree: Tree) -> None:
    math = ET.Element(f"{{{_MATH_NS}}}math")
    math.append(_element(tree))

    assert clml._mathml_text(math) == _flat_rendering(math)
    assert clml.unrendered_mathml_elements(math) == []


def test_rendering_reads_tokens_split_by_markup_inside_them() -> None:
    """Character data either side of a nested element stays two tokens, as before."""
    element = _math("<mrow><mtext>per<mspace/>week</mtext></mrow>")
    assert clml._mathml_text(element) == "per week" == _flat_rendering(element)
    assert re.fullmatch(r"per week", clml._mathml_text(element))
