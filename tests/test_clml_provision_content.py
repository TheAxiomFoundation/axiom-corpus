"""Provision text and territorial extent must follow the captured CLML structure."""

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.uk_legislation import extract_uk_legislation_sections
from axiom_corpus.parsers.clml import parse_section

_TERRITORIES = ("E", "W", "S", "N.I.")
_LEG_NS = "http://www.legislation.gov.uk/namespaces/legislation"
_MATH_NS = "http://www.w3.org/1998/Math/MathML"


def _restriction(extent: str | None) -> str:
    return f' RestrictExtent="{extent}"' if extent is not None else ""


def _extent_xml(
    restrictions: tuple[str | None, ...],
    *,
    root_extent: str = "E+W+S+N.I.",
    number: int = 137,
    child_extent: str | None = None,
    sibling_extent: str | None = None,
) -> str:
    part, block, group, provision = restrictions
    uri = f"http://www.legislation.gov.uk/ukpga/1992/4/section/{number}"
    return f"""<Legislation xmlns="{_LEG_NS}" DocumentURI="{uri}"
        RestrictExtent="{root_extent}">
      <Primary><Body><Part{_restriction(part)}><Pblock{_restriction(block)}>
        <P1group{_restriction(group)}>
          <P1 DocumentURI="{uri}"{_restriction(provision)}>
            <Pnumber>{number}</Pnumber><P1para><Text>A definition.</Text>
              <P2{_restriction(child_extent)}><Pnumber>1</Pnumber>
                <P2para><Text>A narrower subsection.</Text></P2para>
              </P2>
            </P1para>
          </P1>
        </P1group>
        <P1group{_restriction(sibling_extent)}><Title>Another group</Title></P1group>
      </Pblock></Part></Body></Primary>
    </Legislation>"""


@pytest.mark.parametrize(
    ("restrictions", "expected"),
    [
        (("E+W+S", None, None, None), ["E", "W", "S"]),
        ((None, "E+W", None, None), ["E", "W"]),
        ((None, None, "S", None), ["S"]),
        ((None, None, None, "W"), ["W"]),
        (("E+W+S", "E+W", "W", None), ["W"]),
        (("E+W+S", "E+W", "E+W", "E"), ["E"]),
        ((None, None, None, None), list(_TERRITORIES)),
    ],
    ids=["part", "pblock", "p1group", "p1", "nearest-group", "nearest-p1", "root"],
)
def test_extent_uses_nearest_restriction(restrictions, expected):
    assert parse_section(_extent_xml(restrictions)).extent == expected


def test_extent_ignores_restrictions_on_children_and_siblings():
    xml = _extent_xml(
        (None, None, "E+W+S", None), child_extent="E", sibling_extent="N.I."
    )
    assert parse_section(xml).extent == ["E", "W", "S"]


def _ancestor_extent_oracle(xml: str) -> list[str]:
    """Carry each ancestor's restriction down to the requested provision only."""
    root = ET.fromstring(xml)
    target_uri = root.attrib["DocumentURI"]

    def visit(element: ET.Element, inherited: list[str]) -> list[str] | None:
        extent = (
            element.attrib["RestrictExtent"].split("+")
            if "RestrictExtent" in element.attrib
            else inherited
        )
        if element.tag == f"{{{_LEG_NS}}}P1" and element.get("DocumentURI") == target_uri:
            return extent
        for child in element:
            result = visit(child, extent)
            if result is not None:
                return result
        return None

    result = visit(root, [])
    assert result is not None
    return result


@st.composite
def _nested_restrictions(draw):
    root = draw(st.sets(st.sampled_from(_TERRITORIES), min_size=1))
    root_ordered = tuple(territory for territory in _TERRITORIES if territory in root)
    captures = []
    for _ in range(draw(st.integers(min_value=1, max_value=4))):
        inherited = root_ordered
        restrictions = []
        for _ in range(4):
            if draw(st.booleans()):
                chosen = draw(st.sets(st.sampled_from(inherited), min_size=1))
                inherited = tuple(territory for territory in inherited if territory in chosen)
                restrictions.append("+".join(inherited))
            else:
                restrictions.append(None)
        captures.append(tuple(restrictions))
    return "+".join(root_ordered), tuple(captures)


@settings(max_examples=40, deadline=None)
@example(case=("E+W+S+N.I.", (("E+W+S", "E+W", "W", None),)))
@given(case=_nested_restrictions())
def test_every_extracted_extent_matches_ancestor_and_is_subset_of_root(case):
    root_extent, captures = case
    with TemporaryDirectory(prefix="hub-axiom-corpus-765-clml-", dir="/private/tmp") as temp:
        base = Path(temp)
        source_paths = []
        expected = {}
        for number, restrictions in enumerate(captures, start=1):
            xml = _extent_xml(restrictions, root_extent=root_extent, number=number)
            source_path = base / f"section-{number}.xml"
            source_path.write_text(xml, encoding="utf-8")
            source_paths.append(source_path)
            expected[f"uk/statute/ukpga/1992/4/{number}"] = _ancestor_extent_oracle(xml)
        report = extract_uk_legislation_sections(
            CorpusArtifactStore(base / "corpus"),
            version="2026-09-28-extent-test",
            source_xmls=source_paths,
            source_as_of="2026-09-28",
            expression_date="2026-04-06",
        )
        assert report.provisions_written == len(captures)
        for class_report in report.class_reports:
            rows = [
                json.loads(line) for line in class_report.provisions_path.read_text().splitlines()
            ]
            for row in rows:
                extent = row["metadata"]["extent"]
                assert extent == expected[row["citation_path"]]
                assert set(extent) <= set(root_extent.split("+"))


def _formula_xml(content: str) -> str:
    uri = "http://www.legislation.gov.uk/uksi/2015/448/regulation/9"
    return f"""<Legislation xmlns="{_LEG_NS}" xmlns:math="{_MATH_NS}"
        DocumentURI="{uri}" RestrictExtent="E+W+S+N.I.">
      <Secondary><Body><P1 DocumentURI="{uri}"><Pnumber>9</Pnumber>
        <P1para>{content}</P1para>
      </P1></Body></Secondary>
    </Legislation>"""


def test_block_mathml_keeps_both_operative_formulas_in_prose_order():
    xml = _formula_xml("""
      <P2><Pnumber>5A</Pnumber><P2para>
        <Text>The annual threshold is the product of the calculation—</Text>
        <Formula><math:math display="block"><math:mrow>
          <math:mi>M</math:mi><math:mi>x</math:mi><math:mi>W</math:mi>
        </math:mrow></math:math>
          <Where><Para><Text>where M is annual income and W is weeks.</Text></Para></Where>
        </Formula>
      </P2para></P2>
      <P2><Pnumber>6</Pnumber><P2para>
        <Text>The weekly threshold is the product of the calculation—</Text>
        <Formula><math:math><math:mrow><math:mi>
          M</math:mi><math:mo>
          ×</math:mo><math:mi>
          W</math:mi></math:mrow></math:math>
          <Where><Para><Text>where M is weekly income and W is weeks.</Text></Para></Where>
        </Formula>
      </P2para></P2>
    """)
    section = parse_section(xml)
    body = re.sub(r"\s+", "", section.text)
    assert body.index("annualthreshold") < body.index("MxW") < body.index("whereMisannual")
    assert body.index("weeklythreshold") < body.index("M×W") < body.index("whereMisweekly")
    assert body.count("MxW") == body.count("M×W") == 1
    assert len(section.subsections) == 2
    assert "MxW" in re.sub(r"\s+", "", section.subsections[0].text)
    assert "M×W" in re.sub(r"\s+", "", section.subsections[1].text)


def test_inline_mathml_is_emitted_once():
    xml = _formula_xml("""<Text>The threshold is <math:math><math:mrow>
      <math:mi>M</math:mi><math:mo>×</math:mo><math:mi>W</math:mi>
    </math:mrow></math:math> for the period.</Text>""")
    assert re.sub(r"\s+", "", parse_section(xml).text) == "ThethresholdisM×Wfortheperiod."


def test_mathml_uses_supplied_alttext():
    xml = _formula_xml("""<Text>The threshold is—</Text>
      <Formula><math:math alttext="M times W"><math:mrow>
        <math:mi>M</math:mi><math:mo>×</math:mo><math:mi>W</math:mi>
      </math:mrow></math:math></Formula><Text>where W is weeks.</Text>""")
    text = parse_section(xml).text
    assert "M times W" in text
    assert text.index("The threshold") < text.index("M times W") < text.index("where W")
    assert "×" not in text


def test_mathml_preserves_existing_mixed_fraction_rendering():
    xml = _formula_xml("""<Text>The rate is 2<Superior>6</Superior>/<Inferior>7</Inferior>
      per cent, applied to <math:math><math:mi>M</math:mi><math:mo>×</math:mo>
      <math:mi>W</math:mi></math:math>.</Text>""")
    text = parse_section(xml).text
    assert "2 6/7" in text
    assert "26/7" not in text
    assert "M×W" in re.sub(r"\s+", "", text)


def test_mathml_inside_xhtml_table_is_emitted_once():
    xml = _formula_xml("""<Text>The threshold is given in the table.</Text>
      <Tabular><xhtml:table xmlns:xhtml="http://www.w3.org/1999/xhtml">
        <xhtml:tr><xhtml:td><math:math><math:mrow>
          <math:mi>M</math:mi><math:mo>×</math:mo><math:mi>W</math:mi>
        </math:mrow></math:math></xhtml:td></xhtml:tr>
      </xhtml:table></Tabular>""")
    text = re.sub(r"\s+", "", parse_section(xml).text)
    assert text.count("M×W") == 1
    assert "|M×W|" in text
