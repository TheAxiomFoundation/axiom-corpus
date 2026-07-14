"""Tests for CLML Superior/Inferior vulgar-fraction rendering (issue #321).

The UK CLML normalizer used to flatten ``2<Superior>6</Superior>/<Inferior>7
</Inferior> per cent`` (the mixed number "2 6/7 per cent") into ``26/7 per
cent`` -- reading the value 2.857 as the improper fraction 3.714. Because the
encoder grounds numeric literals against the provision body, that is a
silent-wrong-value class of failure. These tests pin the corrected rendering and
guard the exponent / footnote uses of <Superior> that must stay untouched.

The fixtures reproduce the exact markup observed at
``wsi/2013/3029/regulation/25`` (Welsh CTR working-age taper, the per-day form of
the 20% weekly taper) and its plain-text sibling ``regulation/23``.
"""

from xml.etree import ElementTree as ET

from axiom_corpus.parsers.clml import (
    _get_text_content,
    parse_section,
)

_LEG = "http://www.legislation.gov.uk/namespaces/legislation"


def _text_element(inner: str) -> ET.Element:
    """Parse a bare CLML ``<Text>`` fragment (default legislation namespace)."""
    return ET.fromstring(f'<Text xmlns="{_LEG}">{inner}</Text>')


def _itertext(inner: str) -> str:
    return "".join(_text_element(inner).itertext())


def _rendered(inner: str) -> str:
    return _get_text_content(_text_element(inner))


# --- The core bug ----------------------------------------------------------


def test_mixed_number_fraction_keeps_separating_space():
    """``2 6/7`` must survive as a mixed number, not collapse to ``26/7``.

    This is the exact wsi/2013/3029/regulation/25 markup.
    """
    inner = "amount B is 2<Superior>6</Superior>/<Inferior>7</Inferior> per cent"
    assert _rendered(inner) == "amount B is 2 6/7 per cent"
    # The pre-fix flattening, pinned so a regression is loud.
    assert _itertext(inner) == "amount B is 26/7 per cent"
    assert "26/7" not in _rendered(inner)


def test_plain_text_mixed_number_is_unchanged():
    """regulation/23 carries plain-text ``2 6/7`` and must stay identical."""
    inner = "amount B is 2 6/7 per cent"
    assert _rendered(inner) == "amount B is 2 6/7 per cent"


def test_pure_fraction_without_leading_integer():
    """A fraction not preceded by an integer gains no spurious space."""
    inner = "a <Superior>1</Superior>/<Inferior>2</Inferior> share"
    assert _rendered(inner) == "a 1/2 share"


def test_fraction_at_very_start_with_no_preceding_text():
    """A fraction that is the first content (no leading element text) renders
    without a leading space -- exercises the empty-accumulator path."""
    inner = "<Superior>1</Superior>/<Inferior>2</Inferior> of the amount"
    assert _rendered(inner) == "1/2 of the amount"


def test_fraction_without_literal_slash_gets_one():
    """When the source omits the solidus, the numerator/denominator still join
    with a single ``/`` rather than concatenating to ``12``."""
    inner = "a <Superior>1</Superior><Inferior>2</Inferior> share"
    assert _itertext(inner) == "a 12 share"
    assert _rendered(inner) == "a 1/2 share"


def test_mixed_number_without_literal_slash():
    inner = "rate of 3<Superior>4</Superior><Inferior>5</Inferior> times"
    assert _rendered(inner) == "rate of 3 4/5 times"


def test_fraction_slash_character_between_elements():
    """A U+2044 FRACTION SLASH between the elements is treated as a separator."""
    inner = "is 2<Superior>6</Superior>⁄<Inferior>7</Inferior> per cent"
    assert _rendered(inner) == "is 2 6/7 per cent"


# --- The audited non-fraction uses of <Superior> ---------------------------


def test_exponent_superior_is_not_spaced():
    """``m<Superior>2</Superior>`` (m^2) has no <Inferior> and must be left as-is."""
    assert _rendered("an area of 5m<Superior>2</Superior> per plot") == (
        "an area of 5m2 per plot"
    )
    assert _rendered("up to 10<Superior>2</Superior> units") == "up to 102 units"


def test_footnote_marker_superior_is_not_spaced():
    inner = "the word<Superior>3</Superior> is defined"
    assert _rendered(inner) == "the word3 is defined"


def test_superior_and_distant_inferior_are_not_joined():
    """A footnote <Superior> and a later unrelated <Inferior> (separated by real
    words) must not be mistaken for a fraction."""
    inner = "note<Superior>2</Superior> and later <Inferior>x</Inferior> end"
    assert _rendered(inner) == "note2 and later x end"


# --- itertext parity for everything without a fraction ---------------------


def test_matches_itertext_when_no_fraction_present():
    samples = [
        "plain text only",
        "nested <Term>defined term</Term> and tail",
        "an area of 5m<Superior>2</Superior> per plot",
        "the word<Superior>3</Superior> is defined",
        "note<Superior>2</Superior> and later <Inferior>x</Inferior> end",
        "<Emphasis>lead</Emphasis>trailing",
    ]
    for inner in samples:
        assert _rendered(inner) == _itertext(inner), inner


def test_comment_node_parity_with_itertext():
    """``parse_section`` builds trees with ``ET.fromstring``, which discards
    comments, so this node type never reaches production; the walker nonetheless
    stays byte-for-byte identical to ``itertext`` for it."""
    element = ET.Element(f"{{{_LEG}}}Text")
    element.text = "before"
    comment = ET.Comment("editorial note")
    comment.tail = "after"
    element.append(comment)
    assert _get_text_content(element) == "".join(element.itertext())


def test_rendering_is_idempotent():
    """Rendering is a pure function of the tree: a second pass is identical, and
    the corrected text contains no residual improper-fraction artifact."""
    inner = "amount B is 2<Superior>6</Superior>/<Inferior>7</Inferior> per cent"
    element = _text_element(inner)
    first = _get_text_content(element)
    second = _get_text_content(element)
    assert first == second == "amount B is 2 6/7 per cent"


# --- Full parse_section integration ----------------------------------------


_REG25_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/wsi/2013/3029/regulation/25"
             RestrictExtent="E+W">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/wsi/2013/3029/regulation/25</dc:identifier>
    <dc:title>The Council Tax Reduction Schemes (Prescribed Requirements) (Wales) Regulations 2013</dc:title>
    <ukm:SecondaryMetadata>
        <ukm:Year Value="2013"/>
        <ukm:Number Value="3029"/>
    </ukm:SecondaryMetadata>
    <ukm:EnactmentDate Date="2013-11-27"/>
</ukm:Metadata>
<Primary>
    <Body>
        <P1 id="regulation-25" DocumentURI="http://www.legislation.gov.uk/wsi/2013/3029/regulation/25">
            <Pnumber>25</Pnumber>
            <P1para>
                <Text>amount B is 2<Superior>6</Superior>/<Inferior>7</Inferior> per cent of the difference between that person's income for the relevant week and that person's applicable amount; and</Text>
            </P1para>
        </P1>
    </Body>
</Primary>
</Legislation>
"""


def test_parse_section_renders_welsh_taper_fraction():
    section = parse_section(_REG25_FIXTURE)
    assert "2 6/7 per cent" in section.text
    assert "26/7" not in section.text
    assert section.citation.type == "wsi"
    assert section.citation.section == "25"
