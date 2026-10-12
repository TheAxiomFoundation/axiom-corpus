"""Live eCFR section identifiers that break the PART.SECTION form.

The fixtures copy the shapes of the eCFR structures and XML as of 2026-10-08:

- 14 CFR part 241 numbers its sections without the part ("03", "1-1", "19-8.1"; the
  eCFR reader path is section-241.19-8.1), in subject groups.
- 41 CFR 105-60.001 is published as "105.60.001".
- "52. 36" (36 CFR 52.36), "1222. 27" and "3141. 5" (43 CFR part 3140, subpart 3141)
  carry a stray space after the dot.
- "956.1 (Rule 1)" (39 CFR 956.1) carries its rule number.

Each used to be dropped by the inventory (and "19-8.1" misread by the XML pass as part 8,
"105.60.001" as part 105). Each is now read only where the enclosing part confirms it;
the properties check every other identifier against frozen copies of the earlier grammar.
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.ecfr import (
    EcfrGraphicTranscription,
    build_ecfr_inventory_from_structures,
    extract_ecfr,
    iter_ecfr_title_provisions,
    part_targets_from_structure,
)
from axiom_corpus.corpus.io import load_provisions

SCHEMA = json.loads(
    (Path(__file__).parents[1] / "schema/citation-path.v1.json").read_text()
)
CITATION_PATH = re.compile(SCHEMA["$defs"]["citation_path"]["pattern"])
WELL_FORMED_SEGMENT = re.compile(SCHEMA["$defs"]["hierarchy_segment"]["well_formed_pattern"])

# The grammar before this change (#840, d097dcda7), kept as the reference for every
# identifier the confirmed readings leave alone.
EARLIER_PART = r"[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*"
EARLIER_SECTION = r"[0-9A-Za-z][0-9A-Za-z.()-]*"
EARLIER_IDENTIFIER = rf"([0-9A-Za-z]+)\.({EARLIER_SECTION})"


def _section(identifier, label, *, reserved=False, label_description=None):
    node = {"identifier": identifier, "label": label, "type": "section"}
    if label_description is not None:
        node["label_description"] = label_description
    if reserved:
        node["reserved"] = True
    return node


def _part(identifier, label, children):
    return {"identifier": identifier, "label": label, "type": "part", "children": children}


def _title(identifier, children):
    return {"identifier": str(identifier), "label": f"Title {identifier}", "type": "title",
            "children": children}


TITLE_14_STRUCTURE = _title(14, [{
    "identifier": "II",
    "label": "Chapter II—Office of the Secretary, Department of Transportation",
    "type": "chapter",
    "children": [_part("241", "Part 241—Uniform System of Accounts and Reports", [
        _section("01", "Section 01 [Reserved]", reserved=True),
        _section(
            "03",
            "Section 03 Definitions for Purposes of This System of Accounts and Reports",
            label_description="Definitions for Purposes of This System of Accounts and Reports",
        ),
        {
            "identifier": "ECFRa1e3d3d65a1a610",
            "label": "General Accounting Provisions",
            "type": "subject_group",
            "generated_id": True,
            "children": [
                _section("1", "Section 1 Introduction to System of Accounts and Reports"),
                _section(
                    "1-1",
                    "Sec. 1-1 Applicability of system of accounts and reports.",
                    label_description="Applicability of system of accounts and reports.",
                ),
            ],
        },
        {
            "identifier": "ECFRb6240d0cae7da08",
            "label": "Operating Statistics Classifications",
            "type": "subject_group",
            "generated_id": True,
            "children": [
                _section("19-8", "Sec. 19-8 Passenger Origin—Destination"),
                _section("19-8.1", "19-8.1 Purpose.", label_description="Purpose."),
                _section("19-8.3", "§ 19-8.3 Applicability.", label_description="Applicability."),
                _section("19-8.10", "§ 19-8.10 Staff review.", label_description="Staff review."),
            ],
        },
    ])],
}])

# The formula in 19-8.10 is not in the eCFR; it exercises graphic capture.
TITLE_14_XML = """<ECFR>
  <DIV5 N="241" TYPE="PART" NODE="14:4.0.1.1.14">
    <HEAD>PART 241—UNIFORM SYSTEM OF ACCOUNTS AND REPORTS</HEAD>
    <DIV8 N="01" TYPE="SECTION"><HEAD>Section 01 [Reserved]</HEAD></DIV8>
    <DIV8 N="03" TYPE="SECTION" NODE="14:4.0.1.1.14.0.1.3">
      <HEAD>Section 03 Definitions for Purposes of This System of Accounts and Reports</HEAD>
      <P>Account, clearing. An account used as a medium for accumulating costs.</P>
    </DIV8>
    <DIV7 N="ECFRa1e3d3d65a1a610" TYPE="SUBJGRP">
      <HEAD>General Accounting Provisions</HEAD>
      <DIV8 N="1" TYPE="SECTION"><HEAD>Section 1 Introduction to System of Accounts and Reports</HEAD></DIV8>
      <DIV8 N="1-1" TYPE="SECTION">
        <HEAD>Sec. 1-1 Applicability of system of accounts and reports.</HEAD>
        <P>Each large certificated air carrier shall keep its accounts.</P>
      </DIV8>
    </DIV7>
    <DIV7 N="ECFRb6240d0cae7da08" TYPE="SUBJGRP">
      <HEAD>Operating Statistics Classifications</HEAD>
      <DIV8 N="19-8" TYPE="SECTION"><HEAD>Sec. 19-8 Passenger Origin—Destination</HEAD></DIV8>
      <DIV8 N="19-8.1" TYPE="SECTION">
        <HEAD>19-8.1 Purpose.</HEAD>
        <P>The purpose of this part is to set forth required procedures.</P>
      </DIV8>
      <DIV8 N="19-8.3" TYPE="SECTION">
        <HEAD>§ 19-8.3 Applicability.</HEAD>
        <P>(a) All U.S. certificated and commuter air carriers.</P>
      </DIV8>
      <DIV8 N="19-8.10" TYPE="SECTION">
        <HEAD>§ 19-8.10 Staff review.</HEAD>
        <P>The OAI staff will review the carrier procedures.</P>
        <MATH><img src="/graphics/ec01ja26.001.gif"/></MATH>
      </DIV8>
    </DIV7>
  </DIV5>
</ECFR>
"""

PART_241_SECTIONS = ["03", "1", "1-1", "19-8", "19-8.1", "19-8.3", "19-8.10"]

TITLE_41_STRUCTURE = _title(41, [{
    "identifier": "105",
    "label": "Chapter 105—General Services Administration",
    "type": "chapter",
    "children": [_part("105-60", "Part 105-60—Public Availability of Agency Records", [
        {
            "identifier": "A",
            "label": "Subpart A—General Policy",
            "type": "subpart",
            "children": [
                _section("105-60.000", "§ 105-60.000 Purpose of part.",
                         label_description="Purpose of part."),
                _section("105.60.001", "§ 105.60.001 General policy.",
                         label_description="General policy."),
            ],
        },
        {
            "identifier": "B",
            "label": "Subpart B—Proactive Disclosures",
            "type": "subpart",
            "children": [_section("105-60.100", "§ 105-60.100 General.")],
        },
    ])],
}])

TITLE_41_XML = """<ECFR>
  <DIV5 N="105-60" TYPE="PART">
    <HEAD>PART 105-60—PUBLIC AVAILABILITY OF AGENCY RECORDS</HEAD>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A—General Policy</HEAD>
      <DIV8 N="105-60.000" TYPE="SECTION"><HEAD>§ 105-60.000 Purpose of part.</HEAD><P>Purpose.</P></DIV8>
      <DIV8 N="105.60.001" TYPE="SECTION">
        <HEAD>§ 105.60.001 General policy.</HEAD>
        <P>(a) In compliance with the Freedom of Information Act.</P>
      </DIV8>
    </DIV6>
    <DIV6 N="B" TYPE="SUBPART">
      <HEAD>Subpart B—Proactive Disclosures</HEAD>
      <DIV8 N="105-60.100" TYPE="SECTION"><HEAD>§ 105-60.100 General.</HEAD><P>Records.</P></DIV8>
    </DIV6>
  </DIV5>
</ECFR>
"""

TITLE_36_STRUCTURE = _title(36, [_part("52", "Part 52—Concession Contracts", [{
    "identifier": "D",
    "label": "Subpart D—Information and Access to Information",
    "type": "subpart",
    "children": [
        _section("52.35", "§ 52.35 What records must an operator keep?",
                 label_description="What records must an operator keep?"),
        # The eCFR splits label_description at the first space, inside "52. 36".
        _section(
            "52. 36",
            "§ 52. 36 What access does the Comptroller General have to records?",
            label_description="36 What access does the Comptroller General have to records?",
        ),
    ],
}])])

TITLE_36_XML = """<ECFR>
  <DIV5 N="52" TYPE="PART">
    <HEAD>PART 52—CONCESSION CONTRACTS</HEAD>
    <DIV6 N="D" TYPE="SUBPART">
      <HEAD>Subpart D—Information and Access to Information</HEAD>
      <DIV8 N="52.35" TYPE="SECTION">
        <HEAD>§ 52.35 What records must an operator keep?</HEAD><P>Records.</P>
      </DIV8>
      <DIV8 N="52. 36" TYPE="SECTION">
        <HEAD>§ 52. 36 What access does the Comptroller General have to records?</HEAD>
        <P>The Comptroller General of the United States has access.</P>
      </DIV8>
    </DIV6>
  </DIV5>
</ECFR>
"""

TITLE_39_STRUCTURE = _title(39, [_part("956", "Part 956—Rules of Practice", [
    _section("956.1 (Rule 1)", "§ 956.1 (Rule 1) Authority for this part.",
             label_description="(Rule 1) Authority for this part."),
    _section("956.4", "§ 956.4 Filing of petition.", label_description="Filing of petition."),
])])

TITLE_39_XML = """<ECFR>
  <DIV5 N="956" TYPE="PART">
    <HEAD>PART 956—RULES OF PRACTICE</HEAD>
    <DIV8 N="956.1 (Rule 1)" TYPE="SECTION">
      <HEAD>§ 956.1 (Rule 1) Authority for this part.</HEAD>
      <P>This part is issued by the Judicial Officer.</P>
    </DIV8>
    <DIV8 N="956.4" TYPE="SECTION"><HEAD>§ 956.4 Filing of petition.</HEAD><P>File.</P></DIV8>
  </DIV5>
</ECFR>
"""

# 43 CFR numbers a part's subparts like parts: part 3140, subpart 3141, sections 3141.x.
TITLE_43_STRUCTURE = _title(43, [_part("3140", "Part 3140—Leasing in Special Tar Sand Areas", [{
    "identifier": "3141",
    "label": "Subpart 3141—Leasing in Special Tar Sand Areas",
    "type": "subpart",
    "children": [
        _section("3141.3", "§ 3141.3 Authority.", label_description="Authority."),
        _section("3141. 5", "§ 3141. 5 Definitions.", label_description="5 Definitions."),
    ],
}])])

TITLE_43_XML = """<ECFR>
  <DIV5 N="3140" TYPE="PART">
    <HEAD>PART 3140—LEASING IN SPECIAL TAR SAND AREAS</HEAD>
    <DIV6 N="3141" TYPE="SUBPART">
      <HEAD>Subpart 3141—Leasing in Special Tar Sand Areas</HEAD>
      <DIV8 N="3141.3" TYPE="SECTION"><HEAD>§ 3141.3 Authority.</HEAD><P>Authority.</P></DIV8>
      <DIV8 N="3141. 5" TYPE="SECTION">
        <HEAD>§ 3141. 5 Definitions.</HEAD><P>As used in this subpart, the term:</P>
      </DIV8>
    </DIV6>
  </DIV5>
</ECFR>
"""


def _paths(items):
    return [item.citation_path for item in items]


def _valid_citation_path(path):
    return bool(CITATION_PATH.fullmatch(path)) and all(
        WELL_FORMED_SEGMENT.fullmatch(segment) for segment in path.split("/")[2:]
    )


def _records(xml, structure, *, allowed=None, include_appendices=False):
    return tuple(
        iter_ecfr_title_provisions(
            xml,
            part_targets_from_structure(structure),
            version="2026-10-12",
            source_path=f"ecfr/title-{structure['identifier']}.xml",
            source_as_of="2026-10-08",
            expression_date="2026-10-08",
            allowed_citation_paths=allowed,
            include_appendices=include_appendices,
        )
    )


def _placeholder(item):
    return ecfr._structure_only_provision(item, "v", "2026-10-08", "2026-10-08")


def _agreeing_records(xml, structure):
    """The allowlisted XML records, which must name exactly the inventory's rows."""
    inventory = build_ecfr_inventory_from_structures((structure,))
    records = _records(xml, structure, allowed=set(_paths(inventory.items)))
    assert [record.citation_path for record in records] == _paths(inventory.items)
    return inventory, {record.citation_path: record for record in records}


# --- 14 CFR part 241 ----------------------------------------------------------------


def test_part_241_numbers_its_sections_without_the_part():
    whole = build_ecfr_inventory_from_structures((TITLE_14_STRUCTURE,))
    scoped = build_ecfr_inventory_from_structures((TITLE_14_STRUCTURE,), only_part="241")

    expected = ["us/regulation/14/241"] + [
        f"us/regulation/14/241/{section}" for section in PART_241_SECTIONS
    ]
    assert _paths(whole.items) == expected
    assert _paths(scoped.items) == expected
    assert all(_valid_citation_path(path) for path in expected)

    by_path = {item.citation_path: item for item in whole.items}
    item = by_path["us/regulation/14/241/19-8.1"]
    assert item.source_url == (
        "https://www.ecfr.gov/current/title-14/chapter-II/part-241#p-241.19-8.1"
    )
    assert item.metadata["part"] == "241"
    assert item.metadata["section"] == "19-8.1"
    assert item.metadata["parent_citation_path"] == "us/regulation/14/241"
    placeholder = _placeholder(item)
    assert placeholder.legal_identifier == "14 CFR 241.19-8.1"
    assert placeholder.heading == "Purpose"
    assert placeholder.level == 1
    assert placeholder.identifiers == {
        "ecfr:title": "14",
        "ecfr:part": "241",
        "ecfr:section": "19-8.1",
    }
    # Headings drop the published designation, whatever its form.
    assert {path: _placeholder(by_path[path]).heading for path in expected[1:]} == {
        "us/regulation/14/241/03": "Definitions for Purposes of This System of Accounts and Reports",
        "us/regulation/14/241/1": "Introduction to System of Accounts and Reports",
        "us/regulation/14/241/1-1": "Applicability of system of accounts and reports",
        "us/regulation/14/241/19-8": "Passenger Origin—Destination",
        "us/regulation/14/241/19-8.1": "Purpose",
        "us/regulation/14/241/19-8.3": "Applicability",
        "us/regulation/14/241/19-8.10": "Staff review",
    }


def test_part_241_xml_records_agree_with_the_inventory():
    inventory, records = _agreeing_records(TITLE_14_XML, TITLE_14_STRUCTURE)

    purpose = records["us/regulation/14/241/19-8.1"]
    assert purpose.citation_label == "14 CFR 241.19-8.1"
    assert purpose.legal_identifier == "14 CFR 241.19-8.1"
    assert purpose.body == "The purpose of this part is to set forth required procedures."
    assert purpose.parent_citation_path == "us/regulation/14/241"
    assert purpose.metadata["part"] == "241"
    assert records["us/regulation/14/241/03"].source_id == "14:4.0.1.1.14.0.1.3"
    for item in inventory.items[1:]:
        assert records[item.citation_path].heading == _placeholder(item).heading

    # The earlier search grammar read "19-8.1" as part 8, section 1.
    unfiltered = [record.citation_path for record in _records(TITLE_14_XML, TITLE_14_STRUCTURE)]
    assert not any(path.startswith("us/regulation/14/8/") for path in unfiltered)
    # A reserved section reads too, as everywhere; the inventory leaves it out.
    assert "us/regulation/14/241/01" in unfiltered


def test_part_less_sections_need_a_part_whose_sections_name_no_part():
    # A section that names part 241 shows the part numbers its sections the usual way.
    mixed = json.loads(json.dumps(TITLE_14_STRUCTURE))
    mixed["children"][0]["children"][0]["children"].append(
        _section("241.30", "§ 241.30 Named.")
    )
    paths = _paths(build_ecfr_inventory_from_structures((mixed,)).items)
    assert paths == ["us/regulation/14/241", "us/regulation/14/241/30"]

    xml = TITLE_14_XML.replace(
        "</DIV5>", '<DIV8 N="241.30" TYPE="SECTION"><HEAD>§ 241.30 Named.</HEAD></DIV8></DIV5>'
    )
    records = {record.citation_path for record in _records(xml, mixed)}
    assert "us/regulation/14/8/1" in records  # the earlier search reading, unchanged
    assert "us/regulation/14/241/19-8.1" not in records

    # A dropped dot in an ordinary part stays dropped, not "273/2739".
    typo = _title(7, [_part("273", "Part 273—Certification", [
        _section("273.1", "§ 273.1 Household concept."),
        _section("2739", "§ 2739 Income and deductions."),
    ])])
    assert _paths(build_ecfr_inventory_from_structures((typo,)).items) == [
        "us/regulation/7/273", "us/regulation/7/273/1",
    ]
    elem = ET.Element("DIV8", {"N": "2739", "TYPE": "SECTION"})
    assert ecfr._section_citation_from_element(
        7, elem, "273", named_parts=frozenset({"273"})
    ) is None


def test_part_241_selectors_and_local_source_xml(tmp_path):
    inventory = build_ecfr_inventory_from_structures(
        (TITLE_14_STRUCTURE,), only_part="241", only_sections=("241.19-8.1", "241.03")
    )
    assert _paths(inventory.items) == [
        "us/regulation/14/241",
        "us/regulation/14/241/03",
        "us/regulation/14/241/19-8.1",
    ]

    source_xml = tmp_path / "official-title-14-part-241.xml"
    source_xml.write_text(TITLE_14_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ecfr(
        store,
        version="2026-10-12",
        as_of="2026-10-08",
        expression_date=date(2026, 10, 8),
        source_xml=source_xml,
        only_title=14,
        only_part="241",
        only_sections=("241.1-1",),
        workers=1,
    )
    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/14/241",
        "us/regulation/14/241/1-1",
    ]
    assert records[1].heading == "Applicability of system of accounts and reports"
    assert records[1].body == "Each large certificated air carrier shall keep its accounts."


def test_extract_ecfr_part_241_with_formula_graphic(tmp_path, monkeypatch):
    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: TITLE_14_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: TITLE_14_XML)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-10-12",
        as_of="2026-10-08",
        expression_date=date(2026, 10, 8),
        only_title=14,
        only_part="241",
        workers=1,
        graphic_transcriptions={
            "EC01JA26.001": EcfrGraphicTranscription(sha256=sha256_bytes(graphic), text="A = B")
        },
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == ["us/regulation/14/241"] + [
        f"us/regulation/14/241/{section}" for section in PART_241_SECTIONS
    ]
    assert not any((record.metadata or {}).get("structure_only") for record in records)
    assert records[-1].body == (
        "The OAI staff will review the carrier procedures.\n\n"
        "Formula (EC01JA26.001, verified official image): A = B"
    )
    run_root = store.root / "sources/us/regulation/2026-10-12-title-14-part-241/ecfr"
    assert (run_root / "graphics/EC01JA26.001.png").read_bytes() == graphic


# --- 41 CFR 105-60.001 --------------------------------------------------------------


def test_dotted_hyphenated_part_reads_inside_that_part():
    inventory, records = _agreeing_records(TITLE_41_XML, TITLE_41_STRUCTURE)

    assert _paths(inventory.items) == [
        "us/regulation/41/105-60",
        "us/regulation/41/105-60/subpart-A",
        "us/regulation/41/105-60/000",
        "us/regulation/41/105-60/001",
        "us/regulation/41/105-60/subpart-B",
        "us/regulation/41/105-60/100",
    ]
    item = inventory.items[3]
    assert item.metadata["part"] == "105-60"
    assert item.metadata["section"] == "001"
    assert item.metadata["parent_citation_path"] == "us/regulation/41/105-60/subpart-A"
    assert _placeholder(item).legal_identifier == "41 CFR 105-60.001"
    assert _placeholder(item).heading == "General policy"
    record = records["us/regulation/41/105-60/001"]
    assert record.citation_label == "41 CFR 105-60.001"
    assert record.heading == "General policy"
    assert record.body == "(a) In compliance with the Freedom of Information Act."
    assert record.parent_citation_path == "us/regulation/41/105-60/subpart-A"
    assert record.metadata["part"] == "105-60"

    scoped = build_ecfr_inventory_from_structures((TITLE_41_STRUCTURE,), only_part="105-60")
    assert _paths(scoped.items) == _paths(inventory.items)
    selected = build_ecfr_inventory_from_structures(
        (TITLE_41_STRUCTURE,), only_part="105-60", only_sections=("105-60.001",)
    )
    assert _paths(selected.items)[-1] == "us/regulation/41/105-60/001"
    # The earlier grammar read it as part 105, section 60.001.
    unfiltered = [record.citation_path for record in _records(TITLE_41_XML, TITLE_41_STRUCTURE)]
    assert "us/regulation/41/105/60.001" not in unfiltered


def test_dotted_form_of_another_part_keeps_the_earlier_reading():
    named_parts = frozenset({"105-60"})
    assert ecfr._section_citation_from_identifier(
        41, "105.61.001", "105-60", named_parts=named_parts
    ) == ("us/regulation/41/105/61.001", "61.001")
    # In an alphanumeric part the dotted form is the part's own grammar.
    assert ecfr._section_citation_from_identifier(41, "105.60.001", "105") == (
        "us/regulation/41/105/60.001",
        "60.001",
    )


# --- stray space after the dot ------------------------------------------------------


@pytest.mark.parametrize(
    ("structure", "xml", "path", "label", "heading", "parent"),
    [
        (
            TITLE_36_STRUCTURE,
            TITLE_36_XML,
            "us/regulation/36/52/36",
            "36 CFR 52.36",
            "What access does the Comptroller General have to records?",
            "us/regulation/36/52/subpart-D",
        ),
        (
            TITLE_43_STRUCTURE,
            TITLE_43_XML,
            "us/regulation/43/3141/5",
            "43 CFR 3141.5",
            "Definitions",
            "us/regulation/43/3140/subpart-3141",
        ),
    ],
)
def test_stray_space_after_the_dot(structure, xml, path, label, heading, parent):
    inventory, records = _agreeing_records(xml, structure)
    by_path = {item.citation_path: item for item in inventory.items}

    item = by_path[path]
    sibling = inventory.items[-2]
    # Read like its sibling ("3141.3" in part 3140 is us/regulation/43/3141/3).
    assert item.metadata["part"] == sibling.metadata["part"]
    assert item.metadata["parent_citation_path"] == sibling.metadata["parent_citation_path"]
    assert item.metadata["heading"] == heading
    assert _placeholder(item).heading == heading
    record = records[path]
    assert record.citation_label == label
    assert record.heading == heading
    assert record.parent_citation_path == parent
    assert record.parent_citation_path == records[sibling.citation_path].parent_citation_path


def test_stray_space_needs_a_part_another_section_names():
    structure = json.loads(json.dumps(TITLE_36_STRUCTURE))
    structure["children"][0]["children"][0]["children"][1]["identifier"] = "53. 36"
    assert _paths(build_ecfr_inventory_from_structures((structure,)).items) == [
        "us/regulation/36/52",
        "us/regulation/36/52/subpart-D",
        "us/regulation/36/52/35",
    ]
    elem = ET.Element("DIV8", {"N": "53. 36", "TYPE": "SECTION"})
    assert ecfr._section_citation_from_element(
        36, elem, "52", named_parts=frozenset({"52"})
    ) is None


# --- rule number --------------------------------------------------------------------


def test_rule_number_reads_as_the_section_and_stays_in_the_heading():
    inventory, records = _agreeing_records(TITLE_39_XML, TITLE_39_STRUCTURE)

    assert _paths(inventory.items) == [
        "us/regulation/39/956",
        "us/regulation/39/956/1",
        "us/regulation/39/956/4",
    ]
    item = inventory.items[1]
    assert item.metadata["section"] == "1"
    assert "heading" not in item.metadata
    assert _placeholder(item).heading == "(Rule 1) Authority for this part"
    assert _placeholder(item).legal_identifier == "39 CFR 956.1"
    record = records["us/regulation/39/956/1"]
    assert record.heading == "(Rule 1) Authority for this part"
    assert record.citation_label == "39 CFR 956.1"
    assert build_ecfr_inventory_from_structures(
        (TITLE_39_STRUCTURE,), only_sections=("956.1",)
    ).items[-1].citation_path == "us/regulation/39/956/1"


def test_rule_number_must_match_the_section():
    structure = json.loads(json.dumps(TITLE_39_STRUCTURE))
    structure["children"][0]["children"][0]["identifier"] = "956.1 (Rule 2)"
    assert _paths(build_ecfr_inventory_from_structures((structure,)).items) == [
        "us/regulation/39/956",
        "us/regulation/39/956/4",
    ]


def test_whole_titles_with_every_family_keep_unique_valid_paths():
    for structure, xml in (
        (TITLE_14_STRUCTURE, TITLE_14_XML),
        (TITLE_41_STRUCTURE, TITLE_41_XML),
        (TITLE_36_STRUCTURE, TITLE_36_XML),
        (TITLE_39_STRUCTURE, TITLE_39_XML),
        (TITLE_43_STRUCTURE, TITLE_43_XML),
    ):
        inventory, records = _agreeing_records(xml, structure)
        paths = _paths(inventory.items)
        assert len(set(paths)) == len(paths)
        assert all(_valid_citation_path(path) for path in paths)
        assert all(record.body is not None for record in records.values() if record.kind == "section")


# --- Evidence and headings ---------------------------------------------------------


@pytest.mark.parametrize(
    ("part", "identifiers", "named"),
    [
        ("241", PART_241_SECTIONS, frozenset()),
        # The dotted spelling names the hyphenated part itself, not part 105.
        ("105-60", ["105-60.000", "105.60.001", "105-60.100"], frozenset({"105-60"})),
        # XML N values are read bare, as the reading reads them; a stray space is not evidence.
        ("52", ["§ 52.35", " 52.34 ", "52. 36"], frozenset({"52"})),
        ("3140", ["3140.1", "3141.3", "3141. 5"], frozenset({"3140", "3141"})),
        ("956", ["956.1 (Rule 1)", "956.4"], frozenset({"956"})),
    ],
)
def test_section_named_parts(part, identifiers, named):
    assert ecfr._section_named_parts(part, identifiers) == named


def _part_nodes(node):
    if node["type"] == "part":
        yield node
    for child in node.get("children", []):
        yield from _part_nodes(child)


def test_evidence_is_the_same_from_structure_and_xml():
    for structure, xml in (
        (TITLE_14_STRUCTURE, TITLE_14_XML),
        (TITLE_41_STRUCTURE, TITLE_41_XML),
        (TITLE_36_STRUCTURE, TITLE_36_XML),
        (TITLE_39_STRUCTURE, TITLE_39_XML),
        (TITLE_43_STRUCTURE, TITLE_43_XML),
    ):
        div5 = {elem.get("N"): elem for elem in ET.fromstring(xml).iter("DIV5")}
        for node in _part_nodes(structure):
            assert ecfr._structure_named_parts(node) == ecfr._element_named_parts(
                div5[node["identifier"]]
            )


def test_stray_space_naming_the_first_number_of_a_hyphenated_part_stays_unread():
    # "105. 5" beside "105.60.001": part 105-60 names no part 105.
    named = ecfr._section_named_parts("105-60", ["105-60.000", "105.60.001"])
    assert ecfr._section_citation_from_identifier(
        41, "105. 5", "105-60", named_parts=named
    ) is None


def test_stray_space_confirmed_by_a_sibling_whose_n_carries_a_section_sign():
    xml = TITLE_36_XML.replace('<DIV8 N="52.35"', '<DIV8 N="§ 52.35"')
    records = [record.citation_path for record in _records(xml, TITLE_36_STRUCTURE)]
    assert records[-2:] == ["us/regulation/36/52/35", "us/regulation/36/52/36"]


@pytest.mark.parametrize(
    ("heading", "designation", "expected"),
    [
        ("Sec. 1-1 Applicability.", "1-1", "Applicability."),
        ("Section 03 Definitions", "03", "Definitions"),
        ("§ 52. 36 What access?", "52. 36", "What access?"),
        ("§ 52.  36 What access?", "52. 36", "What access?"),
        ("19-8.1 Purpose.", "19-8.1", "Purpose."),
        # Only the whole designation goes, not the start of a longer number.
        ("10 Things", "1", "10 Things"),
        ("19-8.1 Purpose.", "19-8", "19-8.1 Purpose."),
        ("Applicability.", "1-1", "Applicability."),
        ("Sec. 1-1 Applicability.", None, "Sec. 1-1 Applicability."),
    ],
)
def test_without_designation(heading, designation, expected):
    assert ecfr._without_designation(heading, designation) == expected


def test_local_source_xml_structure_carries_the_designated_heading():
    structure = ecfr._scoped_structure_from_part_xml(
        TITLE_14_XML, title=14, part="241", only_sections=("241.1-1", "241.03")
    )
    sections = structure["children"][0]["children"]
    assert [(node["identifier"], node["label_description"]) for node in sections] == [
        ("241.1-1", "Applicability of system of accounts and reports"),
        ("241.03", "Definitions for Purposes of This System of Accounts and Reports"),
    ]


# --- Properties ---------------------------------------------------------------------


def _chars(alphabet, **kwargs):
    # Strings drawn character by character: Hypothesis 6.168's text() shrinker can raise
    # an internal "32 is not in list" while shrinking a failure on these alphabets.
    return st.lists(st.sampled_from(alphabet), **kwargs).map("".join)


_ALNUM = _chars("0123456789abcAZ", min_size=1, max_size=4)
_PART = st.one_of(
    _ALNUM,
    st.lists(_ALNUM, min_size=2, max_size=3).map("-".join),
    st.sampled_from(["241", "105-60", "52", "3140", "956", "S 660", "", "1-"]),
)
_SECTION = st.builds(
    lambda head, tail: head + tail,
    st.sampled_from("0123456789abcAZ"),
    _chars("0123456789aZ.()-", max_size=6),
)
_NOISE = _chars("0123456789aZ.-() §R", max_size=12)


@st.composite
def _identifier_in_part(draw):
    """An enclosing part, the parts its sections name, and an identifier shaped like
    one of the readings (or like none)."""
    part = draw(_PART)
    named = draw(
        st.one_of(
            st.none(),
            st.just(frozenset()),
            st.frozensets(st.one_of(st.just(part), _ALNUM), max_size=3),
        )
    )
    x = draw(st.one_of(st.just(part), _ALNUM, st.sampled_from(sorted(named or {"7"}))))
    section = draw(_SECTION)
    rule = draw(st.one_of(st.just(section), st.just(section.upper()), _ALNUM))
    space = draw(st.sampled_from([" ", "  ", "\t"]))
    identifier = draw(
        st.sampled_from(
            [
                f"{x}.{section}",
                f"{x}.{space}{section}",
                f"{x}.{section} (Rule {rule})",
                f"{part.replace('-', '.')}.{section}",
                section,
                draw(_NOISE),
            ]
        )
    )
    return part, named, identifier


def _earlier_structure(part, identifier):
    """#840's structure grammar: the enclosing part, then PART.SECTION."""
    if part is not None and re.fullmatch(EARLIER_PART, part) and identifier.startswith(
        f"{part}."
    ) and re.fullmatch(EARLIER_SECTION, identifier[len(part) + 1:]):
        return part, identifier[len(part) + 1:]
    match = re.fullmatch(EARLIER_IDENTIFIER, identifier)
    return match.groups() if match else None


def _dotted(part, identifier):
    if part is None or "-" not in part or not re.fullmatch(EARLIER_PART, part):
        return None
    prefix = part.replace("-", ".") + "."
    rest = identifier[len(prefix):]
    if identifier.startswith(prefix) and re.fullmatch(EARLIER_SECTION, rest):
        return part, rest
    return None


def _confirmed(part, identifier, named):
    """The confirmed readings, stated independently of the implementation."""
    if part is None or named is None:
        return None
    head, dot, rest = identifier.partition(".")
    if dot and head in named and re.fullmatch(EARLIER_PART, head):
        # A stray space after the dot.
        if rest[:1].isspace() and re.fullmatch(EARLIER_SECTION, rest.lstrip()):
            return head, rest.lstrip()
        # The section with its own rule number.
        tokens = rest.split()
        if (
            len(tokens) == 3
            and rest.startswith(tokens[0])
            and rest.endswith(")")
            and tokens[1] == "(Rule"
            and re.fullmatch(EARLIER_SECTION, tokens[0])
            and re.fullmatch(r"[0-9A-Za-z.-]+", tokens[2][:-1])
            and tokens[2][:-1].lower() == tokens[0].lower()
        ):
            return head, tokens[0]
    if not named and re.fullmatch(EARLIER_PART, part) and re.fullmatch(EARLIER_SECTION, identifier):
        return part, identifier
    return None


def _path(title, reading):
    return ecfr._section_citation_path(title, *reading) if reading else None


@settings(max_examples=1500, deadline=None)
@given(title=st.integers(1, 50), drawn=_identifier_in_part())
def test_property_structure_reading_is_conservative(title, drawn):
    part, named, identifier = drawn
    new = ecfr._section_citation_from_identifier(title, identifier, part, named_parts=named)
    earlier = _earlier_structure(part, identifier)
    if earlier is not None and earlier[0] == part:
        expected = earlier
    elif _dotted(part, identifier) is not None:
        expected = _dotted(part, identifier)
    elif earlier is not None:
        expected = earlier
    else:
        expected = _confirmed(part, identifier, named)
    assert new == ((_path(title, expected), expected[1]) if expected else None)
    # Without evidence about the part, only the dotted hyphenated part is new.
    bare = ecfr._section_citation_from_identifier(title, identifier, part)
    if _dotted(part, identifier) is None or (earlier is not None and earlier[0] == part):
        assert bare == ((_path(title, earlier), earlier[1]) if earlier else None)


@settings(max_examples=1500, deadline=None)
@given(
    title=st.integers(1, 50),
    drawn=_identifier_in_part(),
    prefix=st.sampled_from(["", "§ ", " ", "§"]),
)
def test_property_xml_reading_is_conservative(title, drawn, prefix):
    part, named, identifier = drawn
    n_attr = f"{prefix}{identifier}"
    elem = ET.Element("DIV8", {"N": n_attr, "TYPE": "SECTION"})
    new = ecfr._section_citation_from_element(title, elem, part, named_parts=named)

    bare = re.sub(r"^§\s*", "", n_attr.strip())
    search = re.search(EARLIER_IDENTIFIER, n_attr)
    earlier_search = search.groups() if search else None
    scoped = _earlier_structure(part, bare)
    if scoped is not None and scoped[0] == part:
        expected = scoped
    elif _dotted(part, bare) is not None:
        expected = _dotted(part, bare)
    elif re.fullmatch(EARLIER_IDENTIFIER, bare):
        expected = earlier_search
    else:
        expected = _confirmed(part, bare, named) or earlier_search
    assert new == ((_path(title, expected), *expected) if expected else None)


@st.composite
def _title_structures(draw):
    """A title of distinct parts mixing the shapes the eCFR uses: sections that name
    their part, a part-less part (14 CFR 241), and parts with a stray-space or
    rule-numbered section beside ordinary ones."""
    parts = draw(st.lists(st.one_of(_ALNUM, st.lists(_ALNUM, min_size=2, max_size=2).map("-".join)),
                          min_size=1, max_size=4, unique=True))
    children = []
    for part in parts:
        shape = draw(st.sampled_from(["named", "part-less", "stray", "rule", "dotted"]))
        # A stray-space or rule-numbered section is confirmed by an ordinary sibling.
        min_size = 2 if shape in ("stray", "rule") else 1
        numbers = draw(st.lists(st.integers(1, 60), min_size=min_size, max_size=5, unique=True))
        sections = []
        for index, number in enumerate(numbers):
            if shape == "part-less":
                identifier = draw(st.sampled_from([f"{number}", f"{number}-1", f"19-{number}.1", f"0{number}"]))
                label = f"Sec. {identifier} Heading {number}."
            elif shape == "stray" and index == 0:
                identifier, label = f"{part}. {number}", f"§ {part}. {number} Heading {number}."
            elif shape == "rule" and index == 0:
                identifier = f"{part}.{number} (Rule {number})"
                label = f"§ {identifier} Heading {number}."
            elif shape == "dotted" and index == 0 and "-" in part:
                identifier = f"{part.replace('-', '.')}.{number}"
                label = f"§ {identifier} Heading {number}."
            else:
                identifier, label = f"{part}.{number}", f"§ {part}.{number} Heading {number}."
            sections.append(_section(identifier, label))
        if shape == "part-less":
            # One node per identifier, none of which starts like a PART.SECTION of this
            # part ("19-5.1" in a part 19-5 would name it).
            unique = {}
            for node in sections:
                if not node["identifier"].startswith((f"{part}.", f"{part.replace('-', '.')}.")):
                    unique.setdefault(node["identifier"], node)
            sections = list(unique.values()) or [_section("1", "Sec. 1 Heading 1.")]
        sections = draw(st.permutations(sections))
        if draw(st.booleans()):
            split = draw(st.integers(0, len(sections)))
            subpart = {"identifier": "A", "label": "Subpart A—General", "type": "subpart",
                       "children": sections[split:]}
            sections = [*sections[:split], subpart]
        children.append(_part(part, f"Part {part}—Heading", sections))
    return _title(41, children)


def _render_xml(structure):
    def node_xml(node):
        kind = node["type"]
        if kind == "section":
            return (f'<DIV8 N="{node["identifier"]}" TYPE="SECTION"><HEAD>{node["label"]}</HEAD>'
                    f'<P>Body of {node["identifier"]}.</P></DIV8>')
        inner = "".join(node_xml(child) for child in node["children"])
        if kind == "subpart":
            return f'<DIV6 N="{node["identifier"]}" TYPE="SUBPART"><HEAD>{node["label"]}</HEAD>{inner}</DIV6>'
        return f'<DIV5 N="{node["identifier"]}" TYPE="PART"><HEAD>{node["label"]}</HEAD>{inner}</DIV5>'

    return "<ECFR>" + "".join(node_xml(part) for part in structure["children"]) + "</ECFR>"


def _section_nodes(node):
    for child in node.get("children", []):
        if child["type"] == "section":
            yield child
        else:
            yield from _section_nodes(child)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(structure=_title_structures())
def test_property_every_live_section_reads_once_and_agrees(structure):
    whole = build_ecfr_inventory_from_structures((structure,))
    paths = _paths(whole.items)

    # Identity: unique, schema-valid paths, each with its parent earlier in the inventory.
    assert len(set(paths)) == len(paths)
    seen = set()
    for item in whole.items:
        parent = (item.metadata or {}).get("parent_citation_path")
        assert parent is None or parent in seen
        seen.add(item.citation_path)
        assert _valid_citation_path(item.citation_path)

    # Coverage: every section of every generated shape is read, under its own part.
    sections = [item for item in whole.items if item.metadata["kind"] == "section"]
    assert len(sections) == sum(
        1 for part in structure["children"] for _node in _section_nodes(part)
    )
    assert all(item.citation_path.split("/")[3] == item.metadata["part"] for item in sections)

    # Partition: a part-scoped inventory is the whole inventory restricted to that part.
    for part in [node["identifier"] for node in structure["children"]]:
        part_path = f"us/regulation/41/{part}"
        scoped = _paths(build_ecfr_inventory_from_structures((structure,), only_part=part).items)
        assert scoped == [p for p in paths if p == part_path or p.startswith(part_path + "/")]

    # Agreement: the allowlisted XML pass yields every inventory row, and each section
    # record has the heading its structure-only placeholder would have.
    records = _records(_render_xml(structure), structure, allowed=set(paths))
    assert [record.citation_path for record in records] == paths
    by_path = {record.citation_path: record for record in records}
    for item in sections:
        assert by_path[item.citation_path].heading == _placeholder(item).heading
        assert by_path[item.citation_path].legal_identifier == _placeholder(item).legal_identifier

    # Selection: each section's official selector selects exactly it.
    for item in sections:
        selector = f"{item.metadata['part']}.{item.metadata['section']}"
        selected = build_ecfr_inventory_from_structures((structure,), only_sections=(selector,))
        assert [i.citation_path for i in selected.items if i.metadata["kind"] == "section"] == [
            item.citation_path
        ]
