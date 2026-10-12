"""Subpart-scoped eCFR appendices ("Appendix II to Subpart C of Part 404").

Invariants checked here:

- Identity: a subpart appendix's citation path is
  ``us/regulation/<title>/<part>/subpart-<S>/<segment>`` with segment ``appendix-<d>``
  (designator lowercased), ``appendix`` (unnumbered) or ``appendixes`` (the collective
  note); its parent is the subpart row, at level 2.
- Order: within one subpart, roman-numbered appendices sort by numeral value, lettered
  ones alphabetically (the part-appendix ordinal), numbered ones numerically, and
  unnumbered or collective ones first. Classification ignores input order.
- Agreement: the structure inventory and the XML records name the same rows, and a
  structure-only placeholder carries the same identity, parent, level, ordinal and
  labels as the XML record it stands in for.
- Fail closed: an opted-in subpart appendix that sits outside the subpart or part it
  names, or whose designator has no unambiguous order, raises before any write.
- Part appendices and section rendering are unchanged.
"""

import json
import random
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.ecfr import (
    EcfrPartTarget,
    build_ecfr_inventory_from_structures,
    extract_ecfr,
    iter_ecfr_title_provisions,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id

TARGET = EcfrPartTarget(title=20, part="404", chapter="III")
PNG = b"\x89PNG\r\n\x1a\nlisting-figure"


def _appendix_node(identifier, description):
    return {
        "identifier": identifier,
        "label": f"{identifier}—{description}\n",
        "label_description": f"{description}\n",
        "type": "appendix",
        "reserved": False,
    }


def _section_node(identifier, description):
    return {
        "identifier": identifier,
        "label": f"§ {identifier} {description}",
        "label_description": description,
        "type": "section",
    }


STRUCTURE = {
    "identifier": "20",
    "label": "Title 20-Employees' Benefits",
    "type": "title",
    "children": [{
        "identifier": "III",
        "label": "Chapter III-Social Security Administration",
        "type": "chapter",
        "children": [{
            "identifier": "404",
            "label": "Part 404-Federal Old-Age, Survivors and Disability Insurance",
            "type": "part",
            "children": [
                {
                    "identifier": "B", "label": "Subpart B-Insured Status", "type": "subpart",
                    "children": [
                        _section_node("404.101", "Introduction."),
                        {"identifier": "ECFR1", "type": "subject_group", "children": [
                            _appendix_node(
                                "Appendix to Subpart B of Part 404",
                                "Quarter of Coverage Amounts for Calendar Years After 1978",
                            ),
                        ]},
                    ],
                },
                {
                    "identifier": "C", "label": "Subpart C-Computing Primary Insurance Amounts",
                    "type": "subpart",
                    "children": [
                        _section_node("404.201", "What is included in this subpart?"),
                        {"identifier": "ECFR2", "type": "subject_group", "children": [
                            _appendix_node("Appendixes to Subpart C of Part 404", "Note"),
                            _appendix_node(
                                "Appendix I to Subpart C of Part 404",
                                "Average of the Total Wages for Years After 1950",
                            ),
                            _appendix_node(
                                "Appendix II to Subpart C of Part 404",
                                "Benefit Formulas Used With Average Indexed Monthly Earnings",
                            ),
                            _appendix_node(
                                "Appendix IV to Subpart C of Part 404",
                                "Earnings Needed for a Year of Coverage After 1950",
                            ),
                            _appendix_node(
                                "Appendix V to Subpart C of Part 404",
                                "Computing the Special Minimum Primary Insurance Amount",
                            ),
                        ]},
                    ],
                },
                {
                    "identifier": "P", "label": "Subpart P-Determining Disability and Blindness",
                    "type": "subpart",
                    "children": [
                        _section_node("404.1501", "Scope of subpart."),
                        _appendix_node("Appendix 1 to Subpart P of Part 404", "Listing of Impairments"),
                        _appendix_node("Appendix 2 to Subpart P of Part 404", "Medical-Vocational Guidelines"),
                        # A part appendix inside a subpart keeps its part parent.
                        _appendix_node("Appendix A to Part 404", "Synthetic Part Appendix"),
                    ],
                },
            ],
        }],
    }],
}


def _div9(identifier, description, body):
    return (
        f'<DIV9 N="{identifier}" TYPE="APPENDIX">'
        f"<HEAD>{identifier}—{description}\n</HEAD>{body}"
        "<CITA>[45 FR 25060, Apr. 14, 1980]</CITA></DIV9>"
    )


XML = f"""<ECFR><DIV5 N="404" TYPE="PART">
<HEAD>PART 404—FEDERAL OLD-AGE, SURVIVORS AND DISABILITY INSURANCE</HEAD>
<DIV6 N="B" TYPE="SUBPART"><HEAD>Subpart B—Insured Status</HEAD>
  <DIV8 N="§ 404.101" TYPE="SECTION"><HEAD>§ 404.101 Introduction.</HEAD><P>(a) Insured status.</P></DIV8>
  <DIV7 TYPE="SUBJGRP"><HEAD>Quarters of Coverage</HEAD>
  {_div9("Appendix to Subpart B of Part 404", "Quarter of Coverage Amounts for Calendar Years After 1978",
         "<TABLE><THEAD><TR><TH>Year</TH><TH>Amount</TH></TR></THEAD>"
         "<TBODY><TR><TD>1978</TD><TD>$250</TD></TR></TBODY></TABLE>")}
  </DIV7>
</DIV6>
<DIV6 N="C" TYPE="SUBPART"><HEAD>Subpart C—Computing Primary Insurance Amounts</HEAD>
  <DIV8 N="§ 404.201" TYPE="SECTION"><HEAD>§ 404.201 What is included in this subpart?</HEAD>
    <P>A section paragraph.</P>
    <TABLE><CAPTION><P>Section Caption</P></CAPTION><TR><TH>means<br/>less</TH></TR></TABLE>
  </DIV8>
  <DIV7 TYPE="SUBJGRP"><HEAD>Appendixes</HEAD>
  {_div9("Appendixes to Subpart C of Part 404", "Note", "<P>The appendixes show figures.</P>")}
  {_div9("Appendix I to Subpart C of Part 404", "Average of the Total Wages for Years After 1950",
         "<P>The average wage index series.</P>")}
  {_div9("Appendix II to Subpart C of Part 404", "Benefit Formulas Used With Average Indexed Monthly Earnings",
         '<DIV width="100%"><TABLE><CAPTION><P class="title">Benefit Formulas</P></CAPTION>'
         "<THEAD><TR><TH>Year you reach age 62 <sup>1</sup></TH><TH>90 percent of the<br/>first—</TH></TR></THEAD>"
         "<TBODY><TR><TD>1979</TD><TD>$180</TD></TR></TBODY>"
         "<TFOOT><TR><TD><sup>1</sup> Or become disabled.</TD></TR></TFOOT></TABLE></DIV>")}
  {_div9("Appendix IV to Subpart C of Part 404", "Earnings Needed for a Year of Coverage After 1950",
         "<P>Year-of-coverage amounts.</P>")}
  {_div9("Appendix V to Subpart C of Part 404", "Computing the Special Minimum Primary Insurance Amount",
         "<P>Special minimum amounts.</P>")}
  </DIV7>
</DIV6>
<DIV6 N="P" TYPE="SUBPART"><HEAD>Subpart P—Determining Disability and Blindness</HEAD>
  <DIV8 N="§ 404.1501" TYPE="SECTION"><HEAD>§ 404.1501 Scope of subpart.</HEAD><P>(a) Disability.</P></DIV8>
  {_div9("Appendix 1 to Subpart P of Part 404", "Listing of Impairments",
         '<XREF ID="20260702">Link to an amendment published at 91 FR 40836, July 2, 2026.</XREF>'
         "<HD1>Part A</HD1><P>1.00 Musculoskeletal Disorders</P>"
         '<FP><img src="/graphics/er28mr13.002.gif"/></FP>')}
  {_div9("Appendix 2 to Subpart P of Part 404", "Medical-Vocational Guidelines",
         "<P>200.00 Introduction.</P>")}
  {_div9("Appendix A to Part 404", "Synthetic Part Appendix", "<P>Part-scoped text.</P>")}
</DIV6>
</DIV5></ECFR>"""

EXPECTED_PATHS = [
    "us/regulation/20/404",
    "us/regulation/20/404/subpart-B",
    "us/regulation/20/404/101",
    "us/regulation/20/404/subpart-B/appendix",
    "us/regulation/20/404/subpart-C",
    "us/regulation/20/404/201",
    "us/regulation/20/404/subpart-C/appendixes",
    "us/regulation/20/404/subpart-C/appendix-i",
    "us/regulation/20/404/subpart-C/appendix-ii",
    "us/regulation/20/404/subpart-C/appendix-iv",
    "us/regulation/20/404/subpart-C/appendix-v",
    "us/regulation/20/404/subpart-P",
    "us/regulation/20/404/1501",
    "us/regulation/20/404/subpart-P/appendix-1",
    "us/regulation/20/404/subpart-P/appendix-2",
    "us/regulation/20/404/appendix-a",
]

# (citation path, ordinal, legal identifier, identifiers["ecfr:appendix"])
EXPECTED_APPENDICES = [
    ("us/regulation/20/404/subpart-B/appendix", 1_000_000, "20 CFR part 404, subpart B, appendix", None),
    ("us/regulation/20/404/subpart-C/appendixes", 1_000_000, "20 CFR part 404, subpart C, appendixes", None),
    ("us/regulation/20/404/subpart-C/appendix-i", 1_000_001, "20 CFR part 404, subpart C, appendix I", "i"),
    ("us/regulation/20/404/subpart-C/appendix-ii", 1_000_002, "20 CFR part 404, subpart C, appendix II", "ii"),
    ("us/regulation/20/404/subpart-C/appendix-iv", 1_000_004, "20 CFR part 404, subpart C, appendix IV", "iv"),
    ("us/regulation/20/404/subpart-C/appendix-v", 1_000_005, "20 CFR part 404, subpart C, appendix V", "v"),
    ("us/regulation/20/404/subpart-P/appendix-1", 1_000_001, "20 CFR part 404, subpart P, appendix 1", "1"),
    ("us/regulation/20/404/subpart-P/appendix-2", 1_000_002, "20 CFR part 404, subpart P, appendix 2", "2"),
]


def _to_roman(value):
    numerals = []
    for amount, numeral in (
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
        (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ):
        while value >= amount:
            numerals.append(numeral)
            value -= amount
    return "".join(numerals)


def _records(xml=XML, **kwargs):
    return tuple(iter_ecfr_title_provisions(
        xml, (TARGET,), version="2026-10-12", source_path="ecfr/title-20-part-404.xml",
        source_as_of="2026-10-08", expression_date="2026-10-08", **kwargs,
    ))


def _identity(record):
    return (
        record.id, record.citation_path, record.citation_label, record.heading,
        record.parent_citation_path, record.parent_id, record.level, record.ordinal,
        record.kind, record.legal_identifier, record.identifiers, record.source_url,
    )


@pytest.mark.parametrize(
    "identifier,segment,legal_identifier",
    [
        ("Appendix II to Subpart C of Part 404", "appendix-ii", "20 CFR part 404, subpart C, appendix II"),
        ("Appendix VII to Subpart C of Part 404", "appendix-vii", "20 CFR part 404, subpart C, appendix VII"),
        ("Appendix 1 to Subpart P of Part 404", "appendix-1", "20 CFR part 404, subpart P, appendix 1"),
        ("Appendix A to Subpart C of Part 910", "appendix-a", "20 CFR part 910, subpart C, appendix A"),
        ("Appendix to Subpart B of Part 404", "appendix", "20 CFR part 404, subpart B, appendix"),
        ("Appendixes to Subpart C of Part 404", "appendixes", "20 CFR part 404, subpart C, appendixes"),
        ("Appendices to Subpart L of Part 1910", "appendices", "20 CFR part 1910, subpart L, appendices"),
        ("Appendix to Subpart K of Part 416", "appendix", "20 CFR part 416, subpart K, appendix"),
    ],
)
def test_subpart_appendix_identifier_parses(identifier, segment, legal_identifier):
    appendix = ecfr._subpart_appendix_from_identifier(identifier)

    assert appendix is not None
    assert appendix.segment == segment
    assert appendix.citation_path(20) == (
        f"us/regulation/20/{appendix.part}/subpart-{appendix.subpart}/{segment}"
    )
    assert appendix.legal_identifier(20) == legal_identifier
    # A part appendix identifier is not a subpart appendix, and vice versa.
    assert ecfr._appendix_citation_from_identifier(20, identifier, require_supported=False) is None


@pytest.mark.parametrize(
    "identifier",
    [
        "Appendix A to Part 604",
        "Appendix A-1 to Subpart I of Part 550",
        "Appendix C1 to Subpart B of Part 430",
        "Appendix AA to Subpart B of Part 430",
        "Appendixes A to Subpart C of Part 404",
        "Appendix A to Subpart D",
        "Appendix B to Subpart A of 10 CFR Part 51",
        "Appendix A to Subpart B to Part 830",
        "Table 1 to Subpart A of Part 1211",
        "Appendix ii to Subpart C of Part 404",
        "",
    ],
)
def test_subpart_appendix_identifier_rejects_other_shapes(identifier):
    assert ecfr._subpart_appendix_from_identifier(identifier) is None


def test_roman_numeral_values_round_trip_exhaustively():
    for value in range(1, 4000):
        numeral = _to_roman(value)
        assert ecfr._is_roman_numeral(numeral)
        assert ecfr._roman_numeral_value(numeral) == value
    for not_numeral in ("", "IIII", "VV", "IC", "XM", "A", "ii"):
        assert not ecfr._is_roman_numeral(not_numeral)


@settings(max_examples=200, deadline=None)
@given(st.sets(st.integers(min_value=1, max_value=3999), min_size=1, max_size=40), st.randoms())
def test_roman_numbered_appendices_sort_by_numeral_value(values, rng):
    # A set with a multi-character numeral is read as numerals, whatever its order.
    values.add(2)
    designators = [_to_roman(value) for value in sorted(values)]
    shuffled = list(designators)
    rng.shuffle(shuffled)

    numbering = ecfr._subpart_appendix_numbering(shuffled)

    assert numbering == ecfr._subpart_appendix_numbering(designators)
    assert set(numbering.values()) == {"roman"}
    ordinals = [ecfr._subpart_appendix_ordinal(d, numbering[d]) for d in designators]
    assert ordinals == [1_000_000 + value for value in sorted(values)]


@settings(max_examples=200, deadline=None)
@given(st.sets(st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), min_size=1))
def test_lettered_appendices_keep_the_part_appendix_ordinal(letters):
    numbering = ecfr._subpart_appendix_numbering(letters)

    # Single letters (I, V, C... included) are letters unless a sibling is a
    # multi-character numeral, and order like the part appendices do.
    assert set(numbering.values()) == {"letter"}
    for letter in letters:
        assert ecfr._subpart_appendix_ordinal(letter, numbering[letter]) == (
            ecfr._appendix_ordinal(letter.lower())
        )


@settings(max_examples=100, deadline=None)
@given(st.sets(st.integers(min_value=0, max_value=999), min_size=1), st.sets(st.sampled_from("ABC")))
def test_numbered_appendices_order_numerically_beside_letters(numbers, letters):
    designators = [str(number) for number in numbers] + sorted(letters)
    numbering = ecfr._subpart_appendix_numbering(designators)

    for number in numbers:
        assert numbering[str(number)] == "digit"
        assert ecfr._subpart_appendix_ordinal(str(number), "digit") == 1_000_000 + number


@pytest.mark.parametrize(
    "designators,ambiguous",
    [(["A", "CC"], "CC"), (["A", "II"], "II"), (["B", "IV", "V"], "IV")],
)
def test_multi_character_designator_among_letters_has_no_order(designators, ambiguous):
    numbering = ecfr._subpart_appendix_numbering(designators)

    assert numbering[ambiguous] is None
    assert ecfr._subpart_appendix_ordinal(ambiguous, None) is None


def test_unnumbered_and_collective_appendices_lead_their_subpart():
    assert ecfr._subpart_appendix_ordinal(None, None) == 1_000_000
    assert ecfr._subpart_appendix_ordinal("", "roman") == 1_000_000


def test_inventory_takes_subpart_appendices_beside_part_appendices():
    inventory = build_ecfr_inventory_from_structures(
        (STRUCTURE,), only_part="404", include_appendices=True,
        run_id="2026-10-12-title-20-part-404",
    )

    assert [item.citation_path for item in inventory.items] == EXPECTED_PATHS
    by_path = {item.citation_path: item for item in inventory.items}
    appendix_ii = by_path["us/regulation/20/404/subpart-C/appendix-ii"].metadata
    assert appendix_ii == {
        "kind": "appendix",
        "title": 20,
        "part": "404",
        "subpart": "C",
        "appendix": "ii",
        "appendix_identifier": "Appendix II to Subpart C of Part 404",
        "appendix_numbering": "roman",
        "chapter": "III",
        "subchapter": None,
        "parent_citation_path": "us/regulation/20/404/subpart-C",
        "label": "Appendix II to Subpart C of Part 404—Benefit Formulas Used With Average Indexed Monthly Earnings\n",
        "label_description": "Benefit Formulas Used With Average Indexed Monthly Earnings\n",
        "heading": "Benefit Formulas Used With Average Indexed Monthly Earnings",
        "received_on": None,
    }
    assert by_path["us/regulation/20/404/subpart-C/appendix-ii"].source_url == (
        "https://www.ecfr.gov/current/title-20/chapter-III/part-404/"
        "appendix-Appendix%20II%20to%20Subpart%20C%20of%20Part%20404"
    )
    assert by_path["us/regulation/20/404/subpart-C/appendixes"].metadata["appendix"] is None
    assert by_path["us/regulation/20/404/subpart-C/appendixes"].metadata["heading"] == "Note"
    # The part appendix keeps the part-appendix metadata shape exactly.
    assert set(by_path["us/regulation/20/404/appendix-a"].metadata) == {
        "kind", "title", "part", "appendix", "appendix_identifier", "chapter", "subchapter",
        "parent_citation_path", "label", "label_description", "heading", "received_on",
    }
    assert by_path["us/regulation/20/404/appendix-a"].metadata["parent_citation_path"] == (
        "us/regulation/20/404"
    )
    # Default inventories never see appendices.
    default = build_ecfr_inventory_from_structures((STRUCTURE,), only_part="404")
    assert [item.citation_path for item in default.items] == [
        path for path in EXPECTED_PATHS if "appendix" not in path
    ]


def test_iterator_takes_subpart_appendices_with_identity_and_order():
    records = _records(include_appendices=True)

    assert [record.citation_path for record in records] == EXPECTED_PATHS
    by_path = {record.citation_path: record for record in records}
    for path, ordinal, legal_identifier, designator in EXPECTED_APPENDICES:
        record = by_path[path]
        parent = path.rsplit("/", 1)[0]
        assert record.kind == "appendix"
        assert record.level == 2
        assert record.parent_citation_path == parent
        assert record.parent_id == by_path[parent].id == deterministic_provision_id(parent)
        assert record.id == deterministic_provision_id(path)
        assert record.ordinal == ordinal
        assert record.legal_identifier == record.citation_label == legal_identifier
        expected_identifiers = {"ecfr:title": "20", "ecfr:part": "404", "ecfr:subpart": path.split("/")[4][8:]}
        if designator:
            expected_identifiers["ecfr:appendix"] = designator
        assert record.identifiers == expected_identifiers
        assert record.metadata["appendix"] == designator
        assert record.source_as_of == record.expression_date == "2026-10-08"
    # Navigation order within subpart C follows the numerals, after its sections.
    subpart_c = sorted(
        (record for record in records if record.parent_citation_path == "us/regulation/20/404/subpart-C"),
        key=lambda record: (record.ordinal, record.citation_path),
    )
    assert [record.citation_path.rsplit("/", 1)[1] for record in subpart_c] == [
        "201", "appendixes", "appendix-i", "appendix-ii", "appendix-iv", "appendix-v",
    ]
    part_appendix = by_path["us/regulation/20/404/appendix-a"]
    assert (part_appendix.parent_citation_path, part_appendix.level, part_appendix.ordinal) == (
        "us/regulation/20/404", 1, 1_000_065,
    )
    assert "subpart" not in part_appendix.metadata
    assert by_path["us/regulation/20/404/subpart-C/appendixes"].heading == "Note"
    assert by_path["us/regulation/20/404/subpart-P/appendix-1"].heading == "Listing of Impairments"
    # Default iteration never converts appendices.
    assert [record.citation_path for record in _records()] == [
        path for path in EXPECTED_PATHS if "appendix" not in path
    ]


def test_appendix_rendering_keeps_captions_and_word_breaks_but_sections_do_not_change():
    by_path = {record.citation_path: record for record in _records(include_appendices=True)}

    assert by_path["us/regulation/20/404/subpart-C/appendix-ii"].body.split("\n\n") == [
        "Benefit Formulas",
        "Year you reach age 62 1 | 90 percent of the first—\n1979 | $180\n1 Or become disabled.",
    ]
    listing = by_path["us/regulation/20/404/subpart-P/appendix-1"].body
    assert listing.split("\n\n") == [
        "Part A",
        "1.00 Musculoskeletal Disorders",
        "[Official source image: ecfr/graphics/ER28MR13.002.png]",
    ]
    # eCFR's editorial "Link to an amendment" cross-reference is not regulation text.
    assert "Link to an amendment" not in listing
    assert "45 FR 25060" not in by_path["us/regulation/20/404/subpart-B/appendix"].body
    # Section rendering keeps its established output (caption dropped, <br/> joined).
    assert by_path["us/regulation/20/404/201"].body == "A section paragraph.\n\nmeansless"


@pytest.mark.parametrize(
    "allowed,expected",
    [
        ({"us/regulation/20/404/subpart-C/appendix-ii"}, ["us/regulation/20/404/subpart-C/appendix-ii"]),
        ({"us/regulation/20/404/subpart-B/appendix", "us/regulation/20/404/appendix-a"},
         ["us/regulation/20/404/subpart-B/appendix", "us/regulation/20/404/appendix-a"]),
        ({"us/regulation/20/404/201"}, ["us/regulation/20/404/201"]),
        (set(), []),
    ],
)
def test_iterator_allowlist_selects_subpart_appendices(allowed, expected):
    records = _records(include_appendices=True, allowed_citation_paths=allowed)

    assert [record.citation_path for record in records] == expected


def _with_appendix(xml, subpart, identifier):
    """Put one more DIV9 at the end of ``subpart`` (or of the part when None)."""
    div9 = _div9(identifier, "Moved", "<P>Moved appendix.</P>")
    if subpart is None:
        return xml.replace("</DIV5>", div9 + "</DIV5>")
    marker = f'<DIV6 N="{subpart}" TYPE="SUBPART">'
    start = xml.index(marker)
    end = xml.index("</DIV6>", start)
    return xml[:end] + div9 + xml[end:]


@pytest.mark.parametrize(
    "subpart,identifier,error",
    [
        ("B", "Appendix VI to Subpart C of Part 404", "subpart 'C' conflicts with enclosing subpart 'B'"),
        (None, "Appendix VI to Subpart C of Part 404", "subpart 'C' conflicts with enclosing subpart None"),
        ("C", "Appendix VI to Subpart C of Part 405", "part '405' conflicts with enclosing part '404'"),
    ],
)
@pytest.mark.parametrize("selection", ["all", "parsed-path", "enclosing-path", "excluded"])
def test_iterator_fails_closed_for_misplaced_subpart_appendix(subpart, identifier, error, selection):
    xml = _with_appendix(XML, subpart, identifier)
    appendix = ecfr._subpart_appendix_from_identifier(identifier)
    allowed = {
        "all": None,
        "parsed-path": {appendix.citation_path(20)},
        "enclosing-path": {f"us/regulation/20/404/subpart-{subpart or 'C'}/{appendix.segment}"},
        "excluded": {"us/regulation/20/404/201"},
    }[selection]

    if selection == "excluded":
        records = _records(xml, include_appendices=True, allowed_citation_paths=allowed)
        assert [record.citation_path for record in records] == ["us/regulation/20/404/201"]
    else:
        with pytest.raises(ValueError, match=error):
            _records(xml, include_appendices=True, allowed_citation_paths=allowed)
    # Without the opt-in the misplaced appendix is never read.
    assert len(_records(xml)) == len([path for path in EXPECTED_PATHS if "appendix" not in path])


@pytest.mark.parametrize(
    "subpart,identifier,error",
    [
        ("B", "Appendix VI to Subpart C of Part 404", "subpart 'C' conflicts with enclosing subpart 'B'"),
        ("C", "Appendix VI to Subpart C of Part 405", "part '405' conflicts with enclosing part '404'"),
    ],
)
def test_inventory_fails_closed_for_misplaced_subpart_appendix(subpart, identifier, error):
    structure = json.loads(json.dumps(STRUCTURE))
    part = structure["children"][0]["children"][0]
    host = next(child for child in part["children"] if child["identifier"] == subpart)
    host["children"].append(_appendix_node(identifier, "Moved"))

    with pytest.raises(ValueError, match=error):
        build_ecfr_inventory_from_structures((structure,), only_part="404", include_appendices=True)
    # Section selectors and the default scope exclude it before validation.
    assert build_ecfr_inventory_from_structures(
        (structure,), only_part="404", only_sections=("404.201",), include_appendices=True,
    ).items
    assert build_ecfr_inventory_from_structures((structure,), only_part="404").items


def test_ambiguous_designators_fail_closed_in_inventory_and_iterator():
    structure = json.loads(json.dumps(STRUCTURE))
    subpart_p = structure["children"][0]["children"][0]["children"][2]
    subpart_p["children"].append(_appendix_node("Appendix A to Subpart P of Part 404", "Lettered"))
    subpart_p["children"].append(_appendix_node("Appendix CC to Subpart P of Part 404", "Ambiguous"))
    xml = _with_appendix(_with_appendix(XML, "P", "Appendix A to Subpart P of Part 404"), "P",
                         "Appendix CC to Subpart P of Part 404")

    with pytest.raises(ValueError, match="designator order is ambiguous"):
        build_ecfr_inventory_from_structures((structure,), only_part="404", include_appendices=True)
    with pytest.raises(ValueError, match="designator order is ambiguous"):
        _records(xml, include_appendices=True)
    # "1" and "2" stay numbered, and "A" stays a letter, beside the ambiguous "CC".
    numbering = ecfr._subpart_appendix_numbering(["1", "2", "A", "CC"])
    assert numbering == {"1": "digit", "2": "digit", "A": "letter", "CC": None}


@pytest.fixture
def live_fetchers(monkeypatch):
    fetched = []

    def fetch_graphic(identifier):
        fetched.append(identifier)
        assert identifier == "ER28MR13.002"
        return PNG

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: XML)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch_graphic)
    return fetched


def test_extract_ecfr_takes_subpart_appendices_with_complete_coverage(tmp_path, live_fetchers):
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ecfr(
        store, version="2026-10-12", as_of="2026-10-08", only_title=20, only_part="404",
        include_appendices=True,
    )

    assert report.title_errors == ()
    assert report.coverage.complete
    assert report.provisions_written == len(EXPECTED_PATHS)
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == EXPECTED_PATHS
    assert [item.citation_path for item in load_source_inventory(report.inventory_path)] == EXPECTED_PATHS
    assert live_fetchers == ["ER28MR13.002"]
    graphic = store.root / "sources/us/regulation/2026-10-12-title-20-part-404/ecfr/graphics/ER28MR13.002.png"
    assert graphic.read_bytes() == PNG
    assert graphic in report.source_paths


def test_extract_ecfr_section_scope_skips_subpart_appendices_and_graphics(tmp_path, live_fetchers):
    report = extract_ecfr(
        CorpusArtifactStore(tmp_path / "corpus"), version="2026-10-12", as_of="2026-10-08",
        only_title=20, only_part="404", only_sections=("404.201",), include_appendices=True,
    )

    assert report.coverage.complete
    assert [record.citation_path for record in load_provisions(report.provisions_path)] == [
        "us/regulation/20/404", "us/regulation/20/404/subpart-C", "us/regulation/20/404/201",
    ]
    assert live_fetchers == []


def test_extract_ecfr_placeholder_keeps_subpart_appendix_identity(tmp_path, monkeypatch, live_fetchers):
    # The structure lists Appendix III, which this XML snapshot lacks, and Appendix I
    # is the only single-character numeral: its ordinal must still be 1, as the
    # structure's numbering says, not the letter I's.
    structure = json.loads(json.dumps(STRUCTURE))
    appendices_c = structure["children"][0]["children"][0]["children"][1]["children"][1]["children"]
    appendices_c.insert(3, _appendix_node("Appendix III to Subpart C of Part 404", "Benefit Table"))
    xml = XML
    for numeral in ("II", "IV", "V"):
        start = xml.index(f'<DIV9 N="Appendix {numeral} to Subpart C')
        xml = xml[:start] + xml[xml.index("</DIV9>", start) + len("</DIV9>"):]
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    kwargs = {"version": "2026-10-12", "as_of": "2026-10-08", "only_title": 20,
              "only_part": "404", "include_appendices": True}

    report = extract_ecfr(CorpusArtifactStore(tmp_path / "missing"), **kwargs)

    assert report.coverage.complete
    by_path = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    placeholder = by_path["us/regulation/20/404/subpart-C/appendix-iii"]
    assert placeholder.body is None
    assert placeholder.metadata["structure_only"] is True
    assert placeholder.metadata["body_status"] == "not_in_ecfr_full_xml"
    assert (placeholder.parent_citation_path, placeholder.level, placeholder.ordinal) == (
        "us/regulation/20/404/subpart-C", 2, 1_000_003,
    )
    assert placeholder.legal_identifier == "20 CFR part 404, subpart C, appendix III"
    assert placeholder.heading == "Benefit Table"
    assert by_path["us/regulation/20/404/subpart-C/appendix-i"].ordinal == 1_000_001
    assert by_path["us/regulation/20/404/subpart-C/appendix-i"].body == "The average wage index series."

    # A later snapshot that carries the appendix keeps its identity.
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: _with_appendix(
        xml, "C", "Appendix III to Subpart C of Part 404"
    ).replace("Appendix III to Subpart C of Part 404—Moved", "Appendix III to Subpart C of Part 404—Benefit Table"))
    present = {
        record.citation_path: record
        for record in load_provisions(
            extract_ecfr(CorpusArtifactStore(tmp_path / "present"), **kwargs).provisions_path
        )
    }
    parsed = present["us/regulation/20/404/subpart-C/appendix-iii"]
    assert parsed.body == "Moved appendix."
    assert _identity(parsed)[:-1] == _identity(placeholder)[:-1]
    assert parsed.source_url == placeholder.source_url


# Differential: the structure-derived placeholder and the XML-derived record are two
# implementations of one appendix identity. They must agree for any designator set.
_designator_sets = st.one_of(
    st.sets(st.integers(min_value=1, max_value=60), min_size=1, max_size=8).map(
        lambda values: [_to_roman(value) for value in sorted(values | {2})]
    ),
    st.sets(st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), min_size=1, max_size=8).map(sorted),
    st.sets(st.integers(min_value=1, max_value=20), min_size=1, max_size=8).map(
        lambda values: [str(value) for value in sorted(values)]
    ),
)


@settings(max_examples=150, deadline=None)
@given(
    _designator_sets,
    st.sampled_from([None, "Appendix to Subpart C of Part 404", "Appendixes to Subpart C of Part 404"]),
    st.randoms(),
)
def test_placeholder_and_xml_record_agree_for_any_designators(designators, lead, rng):
    identifiers = ([lead] if lead else []) + [
        f"Appendix {designator} to Subpart C of Part 404" for designator in designators
    ]
    order = list(identifiers)
    rng.shuffle(order)
    structure = {"identifier": "20", "type": "title", "children": [{
        "identifier": "404", "type": "part", "label": "Part 404-OASDI", "children": [{
            "identifier": "C", "type": "subpart", "label": "Subpart C-PIA",
            "children": [_appendix_node(identifier, "Table") for identifier in order],
        }],
    }]}
    xml = (
        '<ECFR><DIV5 N="404" TYPE="PART"><HEAD>PART 404</HEAD>'
        '<DIV6 N="C" TYPE="SUBPART"><HEAD>Subpart C—PIA</HEAD>'
        + "".join(_div9(identifier, "Table", "<P>Text.</P>") for identifier in order)
        + "</DIV6></DIV5></ECFR>"
    )

    inventory = build_ecfr_inventory_from_structures((structure,), only_part="404", include_appendices=True)
    records = tuple(iter_ecfr_title_provisions(
        xml, (EcfrPartTarget(title=20, part="404"),), version="v", source_path="s.xml",
        source_as_of="2026-10-08", expression_date="2026-10-08", include_appendices=True,
    ))

    assert [item.citation_path for item in inventory.items] == [record.citation_path for record in records]
    by_path = {record.citation_path: record for record in records}
    for item in inventory.items:
        if item.metadata["kind"] != "appendix":
            continue
        placeholder = ecfr._structure_only_provision(item, "v", "2026-10-08", "2026-10-08")
        record = by_path[item.citation_path]
        assert _identity(placeholder) == _identity(record)
    # Navigation order is the designators' own order, the lead note first.
    appendices = sorted(
        (record for record in records if record.kind == "appendix"),
        key=lambda record: (record.ordinal, record.citation_path),
    )
    assert [record.metadata["appendix_identifier"] for record in appendices] == identifiers


def test_real_404_shape_from_retained_source_when_present():
    """Exercise the retained 2026-10-08 part 404 source when it is in the checkout."""
    source = (
        Path(__file__).parents[1] / "data/corpus/sources/us/regulation"
        / "2026-10-12-with-appendices-title-20-part-404/ecfr"
    )
    if not (source / "title-20-part-404.xml").exists():
        pytest.skip("retained part 404 appendix source not fetched")
    structure = json.loads((source / "title-20.structure.json").read_text())
    inventory = build_ecfr_inventory_from_structures((structure,), only_part="404", include_appendices=True)
    appendices = [item.citation_path for item in inventory.items if item.metadata["kind"] == "appendix"]
    assert appendices == [
        "us/regulation/20/404/subpart-B/appendix",
        *[f"us/regulation/20/404/subpart-C/{segment}" for segment in (
            "appendixes", "appendix-i", "appendix-ii", "appendix-iii", "appendix-iv",
            "appendix-v", "appendix-vi", "appendix-vii",
        )],
        "us/regulation/20/404/subpart-P/appendix-1",
        "us/regulation/20/404/subpart-P/appendix-2",
    ]
    targets = tuple(target for target in ecfr.part_targets_from_structure(structure) if target.part == "404")
    xml = (source / "title-20-part-404.xml").read_text()
    records = {
        record.citation_path: record
        for record in iter_ecfr_title_provisions(
            xml, targets, version="v", source_path="s.xml", include_appendices=True,
            allowed_citation_paths=set(appendices),
        )
    }
    assert set(records) == set(appendices)
    assert "Table No. 1—Residual Functional Capacity" in records[
        "us/regulation/20/404/subpart-P/appendix-2"
    ].body


def test_shuffled_designator_order_is_irrelevant():
    rng = random.Random(404)
    designators = ["I", "II", "III", "IV", "V", "VI", "VII"]
    for _ in range(20):
        shuffled = list(designators)
        rng.shuffle(shuffled)
        assert ecfr._subpart_appendix_numbering(shuffled) == dict.fromkeys(designators, "roman")
