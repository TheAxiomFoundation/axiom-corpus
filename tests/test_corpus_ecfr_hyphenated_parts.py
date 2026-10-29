"""eCFR parts whose identifier is hyphenated (title 41: part 60-20, sections 60-20.1, ...).

The fixtures copy the shapes of the eCFR title 41 and title 14 structures and XML as of
2026-10-08. Section and part-appendix identifiers under a hyphenated part used to be
dropped by the inventory (and misread by the XML pass: "60-20.1" became part 20); they
now resolve to us/regulation/41/60-20/1. Every other identifier must parse exactly as
before, which the properties below check against a frozen copy of the earlier grammar.
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

# The grammar on origin/main before hyphenated parts (89dc519fa), kept as the reference
# for everything outside a hyphenated part.
OLD_SECTION_IDENTIFIER = r"([0-9A-Za-z]+)\.([0-9A-Za-z][0-9A-Za-z.()-]*)"
OLD_APPENDIX_IDENTIFIER = r"Appendix\s+([0-9A-Za-z]+)\s+to\s+Part\s+([0-9A-Za-z]+)"


def _section(identifier, label, *, reserved=False):
    node = {"identifier": identifier, "label": label, "type": "section"}
    if reserved:
        node["reserved"] = True
    return node


TITLE_41_STRUCTURE = {
    "identifier": "41",
    "label": "Title 41—Public Contracts and Property Management",
    "type": "title",
    "children": [
        {
            "identifier": "B",
            "label": "Subtitle B—Other Provisions Relating to Public Contracts",
            "type": "subtitle",
            "children": [
                {
                    "identifier": "60",
                    "label": "Chapter 60—Office of Federal Contract Compliance Programs",
                    "type": "chapter",
                    "children": [
                        {
                            "identifier": "60-20",
                            "label": "Part 60-20—Discrimination on the Basis of Sex",
                            "type": "part",
                            "children": [
                                _section("60-20.1", "§ 60-20.1 Purpose."),
                                _section("60-20.2", "§ 60-20.2 General prohibitions."),
                            ],
                        },
                        {
                            "identifier": "60-300",
                            "label": "Part 60-300—Affirmative Action Obligations",
                            "type": "part",
                            "children": [
                                {
                                    "identifier": "A",
                                    "label": "Subpart A—Preliminary Matters, Equal Opportunity Clause",
                                    "type": "subpart",
                                    "children": [
                                        _section("60-300.1", "§ 60-300.1 Purpose, applicability."),
                                        _section("60-300.2", "§ 60-300.2 Definitions."),
                                        _section("60-300.3", "§ 60-300.3 [Reserved]", reserved=True),
                                    ],
                                },
                                {
                                    "identifier": "Appendix A to Part 60-300",
                                    "label": "Appendix A to Part 60-300—Guidelines on Reasonable Accommodation",
                                    "type": "appendix",
                                },
                            ],
                        },
                    ],
                }
            ],
        },
        {
            "identifier": "C",
            "label": "Subtitle C—Federal Property Management Regulations System",
            "type": "subtitle",
            "children": [
                {
                    "identifier": "101",
                    "label": "Chapter 101—Federal Property Management Regulations",
                    "type": "chapter",
                    "children": [
                        {
                            "identifier": "101-30",
                            "label": "Part 101-30—Federal Catalog System",
                            "type": "part",
                            "children": [
                                _section("101-30.101-1a", "§ 101-30.101-1a Item of production."),
                                _section(
                                    "101-30.603-3 - 101-30.603-4",
                                    "§§ 101-30.603-3-101-30.603-4 [Reserved]",
                                    reserved=True,
                                ),
                            ],
                        }
                    ],
                },
                {
                    "identifier": "109",
                    "label": "Chapter 109—Department of Energy Property Management Regulations",
                    "type": "chapter",
                    "children": [
                        {
                            "identifier": "109-38",
                            "label": "Part 109-38—Motor Equipment Management",
                            "type": "part",
                            "children": [
                                _section(
                                    "109-38.301-1.50",
                                    "§ 109-38.301-1.50 Authorization for transportation.",
                                ),
                            ],
                        }
                    ],
                },
            ],
        },
    ],
}

TITLE_41_XML = """<?xml version="1.0"?>
<ECFR>
  <DIV5 N="60-20" TYPE="PART" NODE="41:1.2.3.4.5">
    <HEAD>PART 60-20—DISCRIMINATION ON THE BASIS OF SEX</HEAD>
    <DIV8 N="60-20.1" TYPE="SECTION" NODE="41:1.2.3.4.5.0.1.1">
      <HEAD>§ 60-20.1 Purpose.</HEAD>
      <P>The purpose of this part is to set forth specific requirements.</P>
    </DIV8>
    <DIV8 N="60-20.2" TYPE="SECTION" NODE="41:1.2.3.4.5.0.1.2">
      <HEAD>§ 60-20.2 General prohibitions.</HEAD>
      <P>(a) It is unlawful for a contractor to discriminate.</P>
    </DIV8>
  </DIV5>
  <DIV5 N="60-300" TYPE="PART" NODE="41:1.2.3.4.6">
    <HEAD>PART 60-300—AFFIRMATIVE ACTION OBLIGATIONS</HEAD>
    <DIV6 N="A" TYPE="SUBPART" NODE="41:1.2.3.4.6.1">
      <HEAD>Subpart A—Preliminary Matters, Equal Opportunity Clause</HEAD>
      <DIV8 N="60-300.1" TYPE="SECTION" NODE="41:1.2.3.4.6.1.1.1">
        <HEAD>§ 60-300.1 Purpose, applicability.</HEAD>
        <P>(a) Purpose. The purpose of the regulations in this part.</P>
      </DIV8>
      <DIV8 N="60-300.2" TYPE="SECTION" NODE="41:1.2.3.4.6.1.1.2">
        <HEAD>§ 60-300.2 Definitions.</HEAD>
        <P>For the purpose of this part:</P>
        <MATH><img src="/graphics/ec05no91.089.gif"/></MATH>
      </DIV8>
      <DIV8 N="60-300.3" TYPE="SECTION" NODE="41:1.2.3.4.6.1.1.3">
        <HEAD>§ 60-300.3 [Reserved]</HEAD>
      </DIV8>
    </DIV6>
    <DIV9 N="Appendix A to Part 60-300" TYPE="APPENDIX" NODE="41:1.2.3.4.6.2">
      <HEAD>Appendix A to Part 60-300—Guidelines on Reasonable Accommodation</HEAD>
      <P>1. A contractor must make reasonable accommodation.</P>
    </DIV9>
  </DIV5>
  <DIV5 N="101-30" TYPE="PART" NODE="41:2.1.1.30">
    <HEAD>PART 101-30—FEDERAL CATALOG SYSTEM</HEAD>
    <DIV8 N="101-30.101-1a" TYPE="SECTION" NODE="41:2.1.1.30.0.1.1">
      <HEAD>§ 101-30.101-1a Item of production.</HEAD>
      <P>Item of production means an item of supply.</P>
    </DIV8>
    <DIV8 N="101-30.603-3 - 101-30.603-4" TYPE="SECTION" NODE="41:2.1.1.30.0.1.2">
      <HEAD>§§ 101-30.603-3-101-30.603-4 [Reserved]</HEAD>
    </DIV8>
  </DIV5>
  <DIV5 N="109-38" TYPE="PART" NODE="41:2.2.1.38">
    <HEAD>PART 109-38—MOTOR EQUIPMENT MANAGEMENT</HEAD>
    <DIV8 N="109-38.301-1.50" TYPE="SECTION" NODE="41:2.2.1.38.0.1.1">
      <HEAD>§ 109-38.301-1.50 Authorization for transportation.</HEAD>
      <P>(a) The formula follows.</P>
      <MATH><img src="/graphics/ec05no91.088.gif"/></MATH>
    </DIV8>
  </DIV5>
</ECFR>
"""

# 14 CFR part 241 numbers its own sections 19-8.1 to 19-8.10. They must not be read as
# sections of a part 19-8.
TITLE_14_STRUCTURE = {
    "identifier": "14",
    "label": "Title 14—Aeronautics and Space",
    "type": "title",
    "children": [
        {
            "identifier": "241",
            "label": "Part 241—Uniform System of Accounts and Reports",
            "type": "part",
            "children": [
                _section("241.1", "§ 241.1 Applicability."),
                _section("19-8", "Sec. 19-8 Passenger Origin—Destination"),
                _section("19-8.1", "19-8.1 Purpose."),
            ],
        }
    ],
}

TITLE_14_XML = """<ECFR>
  <DIV5 N="241" TYPE="PART">
    <HEAD>PART 241—UNIFORM SYSTEM OF ACCOUNTS AND REPORTS</HEAD>
    <DIV8 N="241.1" TYPE="SECTION"><HEAD>§ 241.1 Applicability.</HEAD><P>Text.</P></DIV8>
    <DIV8 N="19-8" TYPE="SECTION"><HEAD>Sec. 19-8 Passenger Origin—Destination</HEAD></DIV8>
    <DIV8 N="19-8.1" TYPE="SECTION"><HEAD>19-8.1 Purpose.</HEAD><P>Text.</P></DIV8>
  </DIV5>
</ECFR>
"""


def _paths(items):
    return [item.citation_path for item in items]


def _valid_citation_path(path):
    return bool(CITATION_PATH.fullmatch(path)) and all(
        WELL_FORMED_SEGMENT.fullmatch(segment) for segment in path.split("/")[2:]
    )


def _records(xml, structure, *, include_appendices=False, allowed=None):
    return tuple(
        iter_ecfr_title_provisions(
            xml,
            part_targets_from_structure(structure),
            version="2026-10-12",
            source_path="ecfr/title-41.xml",
            source_as_of="2026-10-08",
            expression_date="2026-10-08",
            allowed_citation_paths=allowed,
            include_appendices=include_appendices,
        )
    )


def test_inventory_reads_sections_of_a_hyphenated_part():
    inventory = build_ecfr_inventory_from_structures((TITLE_41_STRUCTURE,), only_part="60-20")

    assert inventory.part_count == 1
    assert _paths(inventory.items) == [
        "us/regulation/41/60-20",
        "us/regulation/41/60-20/1",
        "us/regulation/41/60-20/2",
    ]
    section = inventory.items[1]
    assert section.source_url == (
        "https://www.ecfr.gov/current/title-41/chapter-60/part-60-20#p-60-20.1"
    )
    assert section.metadata["part"] == "60-20"
    assert section.metadata["section"] == "1"
    assert section.metadata["parent_citation_path"] == "us/regulation/41/60-20"

    placeholder = ecfr._structure_only_provision(section, "v", "2026-10-08", "2026-10-08")
    assert placeholder.legal_identifier == "41 CFR 60-20.1"
    assert placeholder.heading == "Purpose"
    assert placeholder.level == 1
    assert placeholder.ordinal == 10
    assert placeholder.identifiers == {
        "ecfr:title": "41",
        "ecfr:part": "60-20",
        "ecfr:section": "1",
    }


def test_whole_title_inventory_reads_every_hyphenated_part():
    inventory = build_ecfr_inventory_from_structures((TITLE_41_STRUCTURE,))

    assert inventory.part_count == 4
    assert _paths(inventory.items) == [
        "us/regulation/41/60-20",
        "us/regulation/41/60-20/1",
        "us/regulation/41/60-20/2",
        "us/regulation/41/60-300",
        "us/regulation/41/60-300/subpart-A",
        "us/regulation/41/60-300/1",
        "us/regulation/41/60-300/2",
        "us/regulation/41/101-30",
        "us/regulation/41/101-30/101-1a",
        "us/regulation/41/109-38",
        "us/regulation/41/109-38/301-1.50",
    ]
    by_path = {item.citation_path: item for item in inventory.items}
    subpart_section = by_path["us/regulation/41/60-300/2"]
    assert subpart_section.metadata["subpart"] == "A"
    assert subpart_section.metadata["parent_citation_path"] == (
        "us/regulation/41/60-300/subpart-A"
    )
    assert by_path["us/regulation/41/109-38/301-1.50"].metadata["section"] == "301-1.50"
    assert all(_valid_citation_path(path) for path in by_path)


def test_hyphenated_prefix_is_a_part_only_inside_that_part():
    whole = build_ecfr_inventory_from_structures((TITLE_14_STRUCTURE,))
    scoped = build_ecfr_inventory_from_structures((TITLE_14_STRUCTURE,), only_part="241")

    expected = ["us/regulation/14/241", "us/regulation/14/241/1"]
    assert _paths(whole.items) == expected
    assert _paths(scoped.items) == expected
    assert not any("/19-8" in path for path in _paths(whole.items))

    # The same identifier under another part does not borrow that part's number.
    misplaced = json.loads(json.dumps(TITLE_41_STRUCTURE))
    misplaced["children"][0]["children"][0]["children"][1]["children"][0]["children"].append(
        _section("60-20.9", "§ 60-20.9 Misplaced.")
    )
    paths = _paths(build_ecfr_inventory_from_structures((misplaced,)).items)
    assert "us/regulation/41/60-20/9" not in paths


def test_xml_reads_hyphenated_part_sections_as_the_inventory_does():
    inventory = build_ecfr_inventory_from_structures((TITLE_41_STRUCTURE,))
    allowed = set(_paths(inventory.items))

    records = _records(TITLE_41_XML, TITLE_41_STRUCTURE, allowed=allowed)

    assert [record.citation_path for record in records] == _paths(inventory.items)
    by_path = {record.citation_path: record for record in records}
    purpose = by_path["us/regulation/41/60-20/1"]
    assert purpose.citation_label == "41 CFR 60-20.1"
    assert purpose.legal_identifier == "41 CFR 60-20.1"
    assert purpose.heading == "Purpose"
    assert purpose.body == "The purpose of this part is to set forth specific requirements."
    assert purpose.parent_citation_path == "us/regulation/41/60-20"
    assert purpose.source_id == "41:1.2.3.4.5.0.1.1"
    definitions = by_path["us/regulation/41/60-300/2"]
    assert definitions.parent_citation_path == "us/regulation/41/60-300/subpart-A"
    assert definitions.level == 2
    assert definitions.identifiers["ecfr:subpart"] == "A"


def test_xml_no_longer_reads_a_hyphenated_part_as_its_last_number():
    records = _records(TITLE_41_XML, TITLE_41_STRUCTURE)
    paths = [record.citation_path for record in records]

    assert "us/regulation/41/60-20/1" in paths
    # The earlier search grammar read "60-20.1" as part 20, section 1.
    assert "us/regulation/41/20/1" not in paths
    assert all(path.startswith("us/regulation/41/") for path in paths)
    sections = [record for record in records if record.kind == "section"]
    assert all(
        record.metadata["part"] == record.citation_path.split("/")[3] for record in sections
    )


def test_section_selector_accepts_a_hyphenated_part():
    inventory = build_ecfr_inventory_from_structures(
        (TITLE_41_STRUCTURE,), only_part="60-300", only_sections=("60-300.2",)
    )

    assert inventory.part_count == 1
    assert _paths(inventory.items) == [
        "us/regulation/41/60-300",
        "us/regulation/41/60-300/subpart-A",
        "us/regulation/41/60-300/2",
    ]


@pytest.mark.parametrize("selector", ["60-20", "60-20.", "-60.1", "60--20.1", "60-.1", "60-20 .1"])
def test_section_selector_still_rejects_malformed_hyphenated_parts(selector):
    with pytest.raises(ValueError, match="invalid eCFR section selector"):
        build_ecfr_inventory_from_structures((TITLE_41_STRUCTURE,), only_sections=(selector,))


def test_hyphenated_selector_selects_only_a_section_under_that_part():
    # eCFR files 41 CFR 105-60.001 under part 105-60 with the identifier "105.60.001",
    # which the alphanumeric grammar reads as part 105, as it did before this change.
    structure = {"identifier": "41", "type": "title", "children": [{
        "identifier": "105-60", "label": "Part 105-60—Public Availability", "type": "part",
        "children": [{"identifier": "A", "label": "Subpart A—General", "type": "subpart",
                      "children": [_section("105-60.000", "§ 105-60.000 Scope."),
                                   _section("105.60.001", "§ 105.60.001 General policy.")]}],
    }]}
    whole = _paths(build_ecfr_inventory_from_structures((structure,)).items)
    assert whole == [
        "us/regulation/41/105-60",
        "us/regulation/41/105-60/subpart-A",
        "us/regulation/41/105-60/000",
        "us/regulation/41/105/60.001",
    ]

    selected = build_ecfr_inventory_from_structures(
        (structure,), only_sections=("105-60.000",)
    )
    assert selected.part_count == 1
    assert _paths(selected.items) == whole[:3]
    # Its path is not under 105-60, so no selector naming part 105-60 reaches it.
    with pytest.raises(ValueError, match="not found: 105-60.60.001"):
        build_ecfr_inventory_from_structures((structure,), only_sections=("105-60.60.001",))
    # The fixture's citation (41 CFR 105.60.001) selects it, under the part that holds it.
    assert _paths(
        build_ecfr_inventory_from_structures((structure,), only_sections=("105.60.001",)).items
    ) == [*whole[:2], "us/regulation/41/105/60.001"]


def test_selector_main_accepts_still_matches_a_dotted_part():
    # Main selected the section that the structure files as "1.4" under a part identified
    # "1.2-3" with "1.2-3.4": its metadata named the enclosing part, so part and section
    # spelled that (and main reads it as part 1, section 2-3.4). A section's metadata now
    # names the part its identifier names, with the part that holds it in enclosing_part
    # (#841), so its own citation selects it, under that part. This fixture's section
    # is selected by "1.4"; the former spelling "1.2-3.4" no longer selects it.
    structure = {"identifier": "41", "type": "title", "children": [
        {"identifier": "1", "label": "Part 1", "type": "part", "children": []},
        {"identifier": "1.2-3", "label": "Part 1.2-3", "type": "part",
         "children": [_section("1.4", "§ 1.4 x.")]},
    ]}

    selected = build_ecfr_inventory_from_structures((structure,), only_sections=("1.4",))

    assert _paths(selected.items) == ["us/regulation/41/1.2-3", "us/regulation/41/1/4"]
    with pytest.raises(ValueError, match="not found: 1.2-3.4"):
        build_ecfr_inventory_from_structures((structure,), only_sections=("1.2-3.4",))


def test_lettered_appendix_of_a_hyphenated_part():
    inventory = build_ecfr_inventory_from_structures(
        (TITLE_41_STRUCTURE,), only_part="60-300", include_appendices=True
    )
    appendix = inventory.items[-1]

    assert appendix.citation_path == "us/regulation/41/60-300/appendix-a"
    assert appendix.metadata["part"] == "60-300"
    assert appendix.metadata["appendix"] == "a"
    assert appendix.metadata["parent_citation_path"] == "us/regulation/41/60-300"
    assert appendix.source_url == (
        "https://www.ecfr.gov/current/title-41/chapter-60/part-60-300/"
        "appendix-Appendix%20A%20to%20Part%2060-300"
    )

    records = _records(
        TITLE_41_XML,
        TITLE_41_STRUCTURE,
        include_appendices=True,
        allowed=set(_paths(inventory.items)),
    )
    assert [record.citation_path for record in records] == _paths(inventory.items)
    assert records[-1].legal_identifier == "41 CFR part 60-300, appendix A"
    assert records[-1].body == "1. A contractor must make reasonable accommodation."


@pytest.mark.parametrize(
    "identifier",
    [
        "Appendix \u0131 to Part 60-300",  # dotless i
        "Appendix \u212a to Part 60-300",  # Kelvin sign
        "Appendix A to Part 60-\u017f00",  # long s
    ],
)
def test_hyphenated_part_appendix_rejects_unicode_lookalikes(identifier):
    assert ecfr._appendix_citation_from_identifier(41, identifier) is None
    assert ecfr._appendix_citation_from_identifier(41, identifier, require_supported=False) is None


def test_hyphenated_part_appendix_naming_another_part_fails_closed():
    conflicting = json.loads(json.dumps(TITLE_41_STRUCTURE))
    part_60_20 = conflicting["children"][0]["children"][0]["children"][0]
    part_60_20["children"].append(
        {"identifier": "Appendix A to Part 60-300", "label": "Appendix A", "type": "appendix"}
    )

    with pytest.raises(ValueError, match="'60-300' conflicts with enclosing part '60-20'"):
        build_ecfr_inventory_from_structures(
            (conflicting,), only_part="60-20", include_appendices=True
        )

    xml = TITLE_41_XML.replace(
        '<DIV8 N="60-20.2"',
        '<DIV9 N="Appendix A to Part 60-300" TYPE="APPENDIX"><P>x</P></DIV9><DIV8 N="60-20.2"',
    )
    with pytest.raises(ValueError, match="conflicts with enclosing part '60-20'"):
        _records(xml, TITLE_41_STRUCTURE, include_appendices=True)


@pytest.mark.parametrize(
    ("part", "paths", "graphic_id", "text"),
    [
        (
            "109-38",
            ["us/regulation/41/109-38", "us/regulation/41/109-38/301-1.50"],
            "EC05NO91.088",
            "(a) The formula follows.",
        ),
        # A section inside a subpart, as 41 CFR 101-1.109 is.
        (
            "60-300",
            [
                "us/regulation/41/60-300",
                "us/regulation/41/60-300/subpart-A",
                "us/regulation/41/60-300/1",
                "us/regulation/41/60-300/2",
            ],
            "EC05NO91.089",
            "For the purpose of this part:",
        ),
    ],
)
def test_extract_ecfr_hyphenated_part_with_formula_graphic(
    tmp_path, monkeypatch, part, paths, graphic_id, text
):
    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: TITLE_41_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: TITLE_41_XML)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_title_xml",
        lambda title, as_of: pytest.fail("part-scoped extract fetched a full title"),
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-10-12",
        as_of="2026-10-08",
        expression_date=date(2026, 10, 8),
        only_title=41,
        only_part=part,
        workers=1,
        graphic_transcriptions={
            graphic_id: EcfrGraphicTranscription(sha256=sha256_bytes(graphic), text="A = B")
        },
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == paths
    assert records[-1].body == (
        f"{text}\n\nFormula ({graphic_id}, verified official image): A = B"
    )
    run_root = store.root / f"sources/us/regulation/2026-10-12-title-41-part-{part}/ecfr"
    assert (run_root / f"graphics/{graphic_id}.png").read_bytes() == graphic
    assert (run_root / f"title-41-part-{part}.xml").exists()


def test_extract_ecfr_local_source_xml_selects_a_hyphenated_section(tmp_path):
    source_xml = tmp_path / "official-title-41-part-60-300.xml"
    source_xml.write_text(TITLE_41_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-10-12",
        as_of="2026-10-08",
        expression_date=date(2026, 10, 8),
        source_xml=source_xml,
        only_title=41,
        only_part="60-300",
        only_sections=("60-300.1",),
        workers=1,
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/41/60-300",
        "us/regulation/41/60-300/subpart-A",
        "us/regulation/41/60-300/1",
    ]
    assert records[2].body == "(a) Purpose. The purpose of the regulations in this part."



def test_ecfr_cli_takes_a_hyphenated_part_and_section(tmp_path, monkeypatch, capsys):
    from axiom_corpus.corpus.cli import main

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: TITLE_41_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: TITLE_41_XML)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: b"\x89PNG\r\n\x1a\n")
    base = tmp_path / "corpus"
    common = ["--base", str(base), "--version", "2026-10-12", "--as-of", "2026-10-08",
              "--only-title", "41", "--only-part", "60-300"]

    assert main(["inventory-ecfr", *common, "--section", "60-300.2"]) == 0
    assert json.loads(capsys.readouterr().out)["items_written"] == 3
    assert main(["extract-ecfr", *common, "--include-appendices"]) == 0
    output = json.loads(capsys.readouterr().out)

    records = load_provisions(Path(output["provisions_path"]))
    assert [record.citation_path for record in records] == [
        "us/regulation/41/60-300",
        "us/regulation/41/60-300/subpart-A",
        "us/regulation/41/60-300/1",
        "us/regulation/41/60-300/2",
        "us/regulation/41/60-300/appendix-a",
    ]
    assert Path(output["provisions_path"]).parent.name == "regulation"
    assert Path(output["provisions_path"]).name == "2026-10-12-title-41-part-60-300.jsonl"

# --- Properties --------------------------------------------------------------------



def _chars(alphabet, **kwargs):
    # Strings drawn character by character: Hypothesis 6.168's text() shrinker can raise
    # an internal "32 is not in list" while shrinking a failure on these alphabets.
    return st.lists(st.sampled_from(alphabet), **kwargs).map("".join)


_ALNUM = _chars("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=4)
_PART = st.lists(_ALNUM, min_size=1, max_size=3).map("-".join)
_SECTION = st.builds(
    lambda head, tail: head + tail,
    st.sampled_from("0123456789abcAZ"),
    _chars("0123456789aZ.()-", max_size=8),
)
# Broad identifiers: anything the eCFR could put in an N attribute or structure node.
_IDENTIFIER = _chars("0123456789aZ.-() §", max_size=14)
_ENCLOSING = st.one_of(
    st.none(), _PART, st.sampled_from(["S 660", "1150-1159", "60-20", "241", "", "-", "1-"])
)


def _old_identifier(title, identifier):
    match = re.fullmatch(OLD_SECTION_IDENTIFIER, identifier)
    if not match:
        return None
    part, section = match.groups()
    return ecfr._section_citation_path(title, part, section), section


def _old_element(title, n_attr):
    match = re.search(OLD_SECTION_IDENTIFIER, n_attr)
    if not match:
        return None
    part, section = match.groups()
    return ecfr._section_citation_path(title, part, section), part, section


def _names_hyphenated_part(part, identifier):
    return (
        part is not None
        and "-" in part
        and re.fullmatch(ecfr._PART_IDENTIFIER_PATTERN, part) is not None
        and re.fullmatch(rf"{re.escape(part)}\.{ecfr._SECTION_NUMBER_PATTERN}", identifier)
        is not None
    )


@settings(max_examples=400, deadline=None)
@given(title=st.integers(1, 50), part=_PART, section=_SECTION)
def test_property_part_section_round_trips_through_structure_and_xml(title, part, section):
    identifier = f"{part}.{section}"
    path = f"us/regulation/{title}/{part}/{ecfr._section_path_segment(section)}"

    assert ecfr._section_citation_from_identifier(title, identifier, part) == (path, section)
    for n_attr in (identifier, f"§ {identifier}", f" {identifier} "):
        elem = ET.Element("DIV8", {"N": n_attr, "TYPE": "SECTION"})
        assert ecfr._section_citation_from_element(title, elem, part) == (path, part, section)
    assert re.fullmatch(ecfr._SECTION_SELECTOR_PATTERN, identifier)
    if ecfr._section_path_segment(section):
        assert CITATION_PATH.fullmatch(path)


@st.composite
def _part_and_identifier(draw, prefix=""):
    """An enclosing part and an identifier that often starts with that part."""
    part = draw(_ENCLOSING)
    tail = draw(_IDENTIFIER)
    if part is not None and draw(st.booleans()):
        return part, f"{prefix}{part}.{tail}"
    return part, tail


@settings(max_examples=800, deadline=None)
@given(title=st.integers(1, 50), drawn=_part_and_identifier())
def test_property_structure_parse_matches_earlier_grammar_outside_hyphenated_parts(
    title, drawn
):
    part, identifier = drawn
    new = ecfr._section_citation_from_identifier(title, identifier, part)
    if _names_hyphenated_part(part, identifier):
        assert new is not None and new[0].split("/")[3] == part
    else:
        assert new == _old_identifier(title, identifier)


@settings(max_examples=800, deadline=None)
@given(
    title=st.integers(1, 50),
    drawn=st.one_of(_part_and_identifier(), _part_and_identifier("§ "), _part_and_identifier(" ")),
)
def test_property_xml_parse_matches_earlier_grammar_outside_hyphenated_parts(title, drawn):
    part, n_attr = drawn
    elem = ET.Element("DIV8", {"N": n_attr, "TYPE": "SECTION"})
    new = ecfr._section_citation_from_element(title, elem, part)
    bare = re.sub(r"^§\s*", "", n_attr.strip())
    if _names_hyphenated_part(part, bare):
        assert new is not None and new[1] == part
    else:
        assert new == _old_element(title, n_attr)


# Case-insensitive lookalikes of ASCII letters: dotless i, dotted capital I, Kelvin sign, long s.
_LOOKALIKES = ["\u0131", "\u0130", "\u212a", "\u017f"]


def _old_appendix(title, identifier, supported):
    match = re.fullmatch(OLD_APPENDIX_IDENTIFIER, identifier.strip(), flags=re.I)
    if not match:
        return None
    appendix, part = match.groups()
    appendix = appendix.lower()
    if supported and not (appendix.isdigit() or (len(appendix) == 1 and appendix.isalpha())):
        return None
    return f"us/regulation/{title}/{part}/appendix-{appendix}", part, appendix


@settings(max_examples=400, deadline=None)
@given(
    title=st.integers(1, 50),
    designator=st.one_of(_ALNUM, st.sampled_from(["A", "1", "II", "b", *_LOOKALIKES])),
    part=st.one_of(
        _PART,
        st.sampled_from(["S 660", "60--20", "60-", "6\u212a", "60-\u0131", "\u017f-1"]),
    ),
    supported=st.booleans(),
)
def test_property_appendix_part_grammar(title, designator, part, supported):
    identifier = f"Appendix {designator} to Part {part}"
    new = ecfr._appendix_citation_from_identifier(title, identifier, require_supported=supported)
    if "-" not in part:
        # The alphanumeric form parses exactly as before, lookalikes included.
        assert new == _old_appendix(title, identifier, supported)
        return
    # A hyphenated part is new: ASCII only, and every path it yields is schema-valid.
    grammatical = (
        re.fullmatch(ecfr._PART_IDENTIFIER_PATTERN, part) is not None
        and re.fullmatch("[0-9A-Za-z]+", designator) is not None
    )
    designator_ok = not supported or designator.isdigit() or (
        len(designator) == 1 and designator.isalpha()
    )
    if grammatical and designator_ok:
        appendix = designator.lower()
        assert new == (f"us/regulation/{title}/{part}/appendix-{appendix}", part, appendix)
        assert _valid_citation_path(new[0])
    else:
        assert new is None


def _old_filter(items, only_sections):
    """origin/main's _filter_ecfr_inventory_sections (89dc519fa), with its grammar."""
    requested = tuple(dict.fromkeys(only_sections))
    for selector in requested:
        if not re.fullmatch(OLD_SECTION_IDENTIFIER, selector):
            raise ValueError(
                f"invalid eCFR section selector {selector!r}; expected PART.SECTION"
            )
    by_path = {item.citation_path: item for item in items}
    matches = {}
    for item in items:
        metadata = item.metadata or {}
        if metadata.get("kind") != "section":
            continue
        selector = f"{metadata.get('part')}.{metadata.get('section')}"
        if selector in requested:
            matches[selector] = item
    missing = [selector for selector in requested if selector not in matches]
    if missing:
        raise ValueError(f"eCFR section selector(s) not found: {', '.join(missing)}")
    retained_paths = set()
    for item in matches.values():
        retained_paths.add(item.citation_path)
        parent_path = str((item.metadata or {}).get("parent_citation_path") or "")
        while parent_path:
            retained_paths.add(parent_path)
            parent = by_path.get(parent_path)
            parent_path = str(
                ((parent.metadata if parent else None) or {}).get("parent_citation_path") or ""
            )
    return [item for item in items if item.citation_path in retained_paths]


def _structure_paths(structure):
    """Every part, subpart and readable live section path of a title, with repeats."""
    title = int(structure["identifier"])
    paths = []

    def walk(node, part=None):
        kind = node.get("type")
        if kind == "part":
            part = node["identifier"]
            paths.append(f"us/regulation/{title}/{part}")
        elif kind == "subpart":
            paths.append(f"us/regulation/{title}/{part}/subpart-{node['identifier']}")
        elif kind == "section" and not node.get("reserved"):
            parsed = ecfr._section_citation_from_identifier(title, node["identifier"], part)
            if parsed is not None:
                paths.append(parsed[0])
            return
        for child in node.get("children", []):
            walk(child, part)

    walk(structure)
    return paths


def _filter_outcome(fn, items, selectors):
    try:
        return ("ok", [item.citation_path for item in fn(items, selectors)])
    except ValueError as exc:
        return ("raise", str(exc))


@st.composite
def _odd_titles(draw):
    """Titles whose parts may be dotted or hyphenated and whose section identifiers may
    or may not name their part."""
    part = st.one_of(_PART, st.builds(lambda a, b: f"{a}.{b}", _ALNUM, _PART))
    parts = draw(st.lists(part, min_size=1, max_size=4, unique=True))
    children = []
    for part_id in parts:
        identifiers = draw(st.lists(
            st.one_of(
                st.integers(1, 9).map(lambda n, p=part_id: f"{p}.{n}"),
                _chars("0123456789aZ.-", min_size=1, max_size=9),
            ),
            max_size=5, unique=True,
        ))
        sections = [_section(identifier, f"§ {identifier} x.") for identifier in identifiers]
        if sections and draw(st.booleans()):
            sections = [{"identifier": "A", "label": "Subpart A", "type": "subpart",
                         "children": sections}]
        children.append({"identifier": part_id, "label": f"Part {part_id}", "type": "part",
                         "children": sections})
    return {"identifier": "41", "label": "Title 41", "type": "title", "children": children}


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(structure=_odd_titles(), extra=st.lists(_chars("0123456789aZ.-", max_size=10), max_size=4))
def test_property_selectors_main_accepts_filter_as_on_main(structure, extra):
    try:
        items = list(build_ecfr_inventory_from_structures((structure,)).items)
    except ValueError as exc:
        # Two items under one citation path fail closed (#841); main wrote both. Check
        # that two items of the structure do claim the path the error names.
        claimed = re.search(r"'([^']+)' is claimed twice", str(exc))
        assert claimed is not None, exc
        assert _structure_paths(structure).count(claimed.group(1)) >= 2
        return
    candidates = {
        f"{item.metadata['part']}.{item.metadata['section']}"
        for item in items
        if item.metadata["kind"] == "section"
    } | set(extra)
    for selector in sorted(candidates):
        if re.fullmatch(OLD_SECTION_IDENTIFIER, selector) is None:
            continue
        assert _filter_outcome(ecfr._filter_ecfr_inventory_sections, items, (selector,)) == (
            _filter_outcome(_old_filter, items, (selector,))
        )


@st.composite
def _title_structures(draw):
    """A title of distinct parts; each part's sections name it, optionally in subparts.

    Alphanumeric parts sometimes also carry a section numbered like a hyphenated part
    ("19-8.1" in part 241), which no part may claim. It is left out when the title has a
    part 8: the XML pass keeps the earlier reading of a section that does not name its part,
    which takes "19-8.1" as part 8, section 1, and would repeat 8.1's path. No eCFR title
    has that collision (all 49 titles, 2026-10-08).
    """
    parts = draw(st.lists(_PART, min_size=1, max_size=5, unique=True))
    children = []
    for part in parts:
        numbers = draw(st.lists(st.integers(1, 300), min_size=0, max_size=6, unique=True))
        sections = [
            _section(f"{part}.{number}", f"§ {part}.{number} Heading {number}.",
                     reserved=draw(st.booleans()) and draw(st.booleans()))
            for number in numbers
        ]
        if "-" not in part and "8" not in parts and draw(st.booleans()):
            sections.append(_section("19-8.1", "19-8.1 Purpose."))
        if sections and draw(st.booleans()):
            split = draw(st.integers(0, len(sections)))
            subpart = {"identifier": "A", "label": "Subpart A—General", "type": "subpart",
                       "children": sections[split:]}
            sections = [*sections[:split], subpart]
        children.append({"identifier": part, "label": f"Part {part}—Heading", "type": "part",
                         "children": sections})
    return {"identifier": "41", "label": "Title 41", "type": "title", "children": children}


def _render_xml(structure):
    def node_xml(node):
        kind = node["type"]
        if kind == "section":
            return (f'<DIV8 N="{node["identifier"]}" TYPE="SECTION"><HEAD>{node["label"]}</HEAD>'
                    f'<P>Body of {node["identifier"]}.</P></DIV8>')
        if kind == "subpart":
            inner = "".join(node_xml(child) for child in node["children"])
            return f'<DIV6 N="{node["identifier"]}" TYPE="SUBPART"><HEAD>{node["label"]}</HEAD>{inner}</DIV6>'
        inner = "".join(node_xml(child) for child in node["children"])
        return f'<DIV5 N="{node["identifier"]}" TYPE="PART"><HEAD>{node["label"]}</HEAD>{inner}</DIV5>'

    return "<ECFR>" + "".join(node_xml(part) for part in structure["children"]) + "</ECFR>"


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(structure=_title_structures())
def test_property_inventory_partitions_by_part_and_matches_the_xml(structure):
    whole = build_ecfr_inventory_from_structures((structure,))
    paths = _paths(whole.items)

    # Identity: unique paths, each with its parent earlier in the inventory.
    assert len(set(paths)) == len(paths)
    seen = set()
    for item in whole.items:
        parent = (item.metadata or {}).get("parent_citation_path")
        assert parent is None or parent in seen
        seen.add(item.citation_path)
        assert _valid_citation_path(item.citation_path)
        # Every section sits under the part that encloses it (the foreign "19-8.1" drops).
        if item.metadata["kind"] == "section":
            assert item.citation_path.split("/")[3] == item.metadata["part"]
            # Selector round trip: its PART.SECTION selects it, with its ancestors.
            selector = f"{item.metadata['part']}.{item.metadata['section']}"
            selected = build_ecfr_inventory_from_structures((structure,), only_sections=(selector,))
            assert selected.items[-1] == item
            assert [i.citation_path for i in selected.items[:-1]] == [
                p for p in paths if p in {
                    f"us/regulation/41/{item.metadata['part']}",
                    item.metadata["parent_citation_path"],
                }
            ]

    # Partition: a part-scoped inventory is the whole inventory restricted to that part.
    for part in [node["identifier"] for node in structure["children"]]:
        part_path = f"us/regulation/41/{part}"
        scoped = _paths(build_ecfr_inventory_from_structures((structure,), only_part=part).items)
        assert scoped == [p for p in paths if p == part_path or p.startswith(part_path + "/")]

    # Structure order: live sections that name their part, in document order.
    expected_sections = []

    def walk(node, part=None):
        if node["type"] == "part":
            part = node["identifier"]
        if node["type"] == "section" and not node.get("reserved"):
            identifier = node["identifier"]
            if identifier.startswith(f"{part}."):
                expected_sections.append(f"us/regulation/41/{part}/{identifier[len(part) + 1:]}")
        for child in node.get("children", []):
            walk(child, part)

    walk(structure)
    assert [
        item.citation_path for item in whole.items if (item.metadata or {}).get("kind") == "section"
    ] == expected_sections

    # Agreement: the XML pass, allowlisted by the inventory, yields every inventory path.
    records = _records(_render_xml(structure), structure, allowed=set(paths))
    assert [record.citation_path for record in records] == paths
