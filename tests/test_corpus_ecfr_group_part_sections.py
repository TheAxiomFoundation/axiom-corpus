"""eCFR sections whose identifier names a part other than the part that holds them.

Title 43 groups BLM rules in parts such as 3800 ("Mining Claims Under the General Mining
Laws"), whose subparts carry their own numbers: subpart 3809 of part 3800 holds
43 CFR 3809.1, and eCFR has no part 3809 (its ancestry API resolves section 3809.1 to
part 3800, subpart 3809, and answers nothing for part 3809). A few typeset errors do the
same: § 1735.9 sits in 7 CFR part 1739. The fixtures copy the shapes of the eCFR title
structures and XML as of 2026-10-08.

Such a section keeps the path of its citation (us/regulation/43/3809/1), which is how
the app and the encoder resolve "43 CFR 3809.1". It belongs to the part that holds it:
its parent is that part's subpart or the part itself, a run scoped to that part includes
it, and metadata["enclosing_part"] names that part. Before this, a run scoped to part
3800 dropped it, and a whole-title run gave it the parent us/regulation/43/3809/subpart-3809,
which is not in the inventory.
"""

import json
import re
import tempfile
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.ecfr import (
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


def _section(identifier, label, *, reserved=False):
    node = {"identifier": identifier, "label": label, "type": "section"}
    if reserved:
        node["reserved"] = True
    return node


def _subpart(identifier, label, children):
    return {"identifier": identifier, "label": label, "type": "subpart", "children": children}


TITLE_43_STRUCTURE = {
    "identifier": "43",
    "label": "Title 43—Public Lands: Interior",
    "type": "title",
    "children": [
        {
            "identifier": "B",
            "label": "Subtitle B—Regulations Relating to Public Lands",
            "type": "subtitle",
            "children": [
                {
                    "identifier": "II",
                    "label": "Chapter II—Bureau of Land Management, Department of the Interior",
                    "type": "chapter",
                    "children": [
                        {
                            "identifier": "C",
                            "label": "Subchapter C—Minerals Management (3000)",
                            "type": "subchapter",
                            "children": [
                                {
                                    "identifier": "3800",
                                    "label": "Part 3800—Mining Claims Under the General Mining Laws",
                                    "type": "part",
                                    "children": [
                                        _subpart("3800", "Subpart 3800—General", [
                                            _section("3800.5", "§ 3800.5 Fees."),
                                        ]),
                                        _subpart(
                                            "3802",
                                            "Subpart 3802—Exploration and Mining, Wilderness Review Program",
                                            [
                                                _section("3802.0-1", "§ 3802.0-1 Purpose."),
                                                _section(
                                                    "3802.0-4",
                                                    "§ 3802.0-4 [Reserved]",
                                                    reserved=True,
                                                ),
                                            ],
                                        ),
                                        _subpart("3809", "Subpart 3809—Surface Management", [
                                            {
                                                "identifier": "ECFR756fd0a32677e93",
                                                "label": "General Information",
                                                "type": "subject_group",
                                                "children": [
                                                    _section(
                                                        "3809.1",
                                                        "§ 3809.1 What are the purposes of this subpart?",
                                                    ),
                                                    _section(
                                                        "3809.2",
                                                        "§ 3809.2 What is the scope of this subpart?",
                                                    ),
                                                ],
                                            },
                                        ]),
                                    ],
                                },
                                {
                                    "identifier": "3830",
                                    "label": (
                                        "Part 3830—Administration of Mining Claims and Sites; "
                                        "General Provisions"
                                    ),
                                    "type": "part",
                                    "children": [
                                        _subpart("A", "Subpart A—Introduction", [
                                            _section(
                                                "3830.1",
                                                "§ 3830.1 What is the purpose of parts 3830-3839?",
                                            ),
                                        ]),
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ],
}

TITLE_43_XML = """<?xml version="1.0"?>
<ECFR>
  <DIV5 N="3800" TYPE="PART" NODE="43:2.1.1.3.38">
    <HEAD>PART 3800—MINING CLAIMS UNDER THE GENERAL MINING LAWS</HEAD>
    <DIV6 N="3800" TYPE="SUBPART" NODE="43:2.1.1.3.38.1">
      <HEAD>Subpart 3800—General</HEAD>
      <DIV8 N="3800.5" TYPE="SECTION" NODE="43:2.1.1.3.38.1.1.1">
        <HEAD>§ 3800.5 Fees.</HEAD>
        <P>(a) An applicant for a plan of operations under this part must pay a processing fee.</P>
      </DIV8>
    </DIV6>
    <DIV6 N="3802" TYPE="SUBPART" NODE="43:2.1.1.3.38.2">
      <HEAD>Subpart 3802—Exploration and Mining, Wilderness Review Program</HEAD>
      <DIV8 N="3802.0-1" TYPE="SECTION" NODE="43:2.1.1.3.38.2.1.1">
        <HEAD>§ 3802.0-1 Purpose.</HEAD>
        <P>The purpose of this subpart is to establish procedures.</P>
      </DIV8>
      <DIV8 N="3802.0-4" TYPE="SECTION" NODE="43:2.1.1.3.38.2.1.2">
        <HEAD>§ 3802.0-4 [Reserved]</HEAD>
      </DIV8>
    </DIV6>
    <DIV6 N="3809" TYPE="SUBPART" NODE="43:2.1.1.3.38.3">
      <HEAD>Subpart 3809—Surface Management</HEAD>
      <DIV7 N="ECFR756fd0a32677e93" TYPE="SUBJGRP" NODE="43:2.1.1.3.38.3.1">
        <HEAD>General Information</HEAD>
        <DIV8 N="3809.1" TYPE="SECTION" NODE="43:2.1.1.3.38.3.1.1">
          <HEAD>§ 3809.1 What are the purposes of this subpart?</HEAD>
          <P>The purposes of this subpart are to:</P>
          <P>(a) Prevent unnecessary or undue degradation of public lands.</P>
        </DIV8>
        <DIV8 N="3809.2" TYPE="SECTION" NODE="43:2.1.1.3.38.3.1.2">
          <HEAD>§ 3809.2 What is the scope of this subpart?</HEAD>
          <P>(a) Mining claims and millsites.</P>
        </DIV8>
      </DIV7>
    </DIV6>
  </DIV5>
  <DIV5 N="3830" TYPE="PART" NODE="43:2.1.1.3.40">
    <HEAD>PART 3830—ADMINISTRATION OF MINING CLAIMS AND SITES; GENERAL PROVISIONS</HEAD>
    <DIV6 N="A" TYPE="SUBPART" NODE="43:2.1.1.3.40.1">
      <HEAD>Subpart A—Introduction</HEAD>
      <DIV8 N="3830.1" TYPE="SECTION" NODE="43:2.1.1.3.40.1.1.1">
        <HEAD>§ 3830.1 What is the purpose of parts 3830-3839?</HEAD>
        <P>The regulations in parts 3830 through 3839 provide procedures.</P>
      </DIV8>
    </DIV6>
  </DIV5>
</ECFR>
"""

PART_3800_URL = "https://www.ecfr.gov/current/title-43/chapter-II/subchapter-C/part-3800"


def _paths(items):
    return [item.citation_path for item in items]


def _valid_citation_path(path):
    return bool(CITATION_PATH.fullmatch(path)) and all(
        WELL_FORMED_SEGMENT.fullmatch(segment) for segment in path.split("/")[2:]
    )


def _records(xml, structure, *, allowed=None):
    return tuple(
        iter_ecfr_title_provisions(
            xml,
            part_targets_from_structure(structure),
            version="2026-10-12",
            source_path="ecfr/title-43.xml",
            source_as_of="2026-10-08",
            expression_date="2026-10-08",
            allowed_citation_paths=allowed,
        )
    )


def _enclosing_part(item):
    metadata = item.metadata or {}
    return metadata.get("enclosing_part") or metadata["part"]


def _without_source_path(item):
    # A part-scoped run names its own source file (ecfr/title-43-part-3800.xml).
    return {key: value for key, value in item.to_mapping().items() if key != "source_path"}


WHOLE_TITLE_43_PATHS = [
    "us/regulation/43/3800",
    "us/regulation/43/3800/subpart-3800",
    "us/regulation/43/3800/5",
    "us/regulation/43/3800/subpart-3802",
    "us/regulation/43/3802/0-1",
    "us/regulation/43/3800/subpart-3809",
    "us/regulation/43/3809/1",
    "us/regulation/43/3809/2",
    "us/regulation/43/3830",
    "us/regulation/43/3830/subpart-A",
    "us/regulation/43/3830/1",
]


def test_section_keeps_its_citation_path_and_takes_the_part_that_holds_it_as_parent():
    inventory = build_ecfr_inventory_from_structures((TITLE_43_STRUCTURE,))

    assert _paths(inventory.items) == WHOLE_TITLE_43_PATHS
    by_path = {item.citation_path: item for item in inventory.items}
    section = by_path["us/regulation/43/3809/1"]
    assert section.metadata["parent_citation_path"] == "us/regulation/43/3800/subpart-3809"
    assert section.metadata["part"] == "3809"
    assert section.metadata["section"] == "1"
    assert section.metadata["subpart"] == "3809"
    assert section.metadata["enclosing_part"] == "3800"
    # eCFR serves no part 3809 page: the section is on part 3800's.
    assert section.source_url == f"{PART_3800_URL}#p-3809.1"

    placeholder = ecfr._structure_only_provision(section, "v", "2026-10-08", "2026-10-08")
    assert placeholder.citation_label == "43 CFR 3809.1"
    assert placeholder.legal_identifier == "43 CFR 3809.1"
    assert placeholder.heading == "What are the purposes of this subpart?"
    assert placeholder.parent_citation_path == "us/regulation/43/3800/subpart-3809"
    assert placeholder.level == 2
    assert placeholder.ordinal == 10
    assert placeholder.identifiers == {
        "ecfr:title": "43",
        "ecfr:part": "3809",
        "ecfr:subpart": "3809",
        "ecfr:section": "1",
    }

    # Every parent is in the inventory and comes before its child.
    seen = set()
    for item in inventory.items:
        parent = item.metadata.get("parent_citation_path")
        assert parent is None or parent in seen
        seen.add(item.citation_path)
        assert _valid_citation_path(item.citation_path)


def test_section_that_names_its_part_is_unchanged():
    inventory = build_ecfr_inventory_from_structures((TITLE_43_STRUCTURE,))
    section = {item.citation_path: item for item in inventory.items}["us/regulation/43/3800/5"]

    assert "enclosing_part" not in section.metadata
    assert section.metadata["part"] == "3800"
    assert section.metadata["parent_citation_path"] == "us/regulation/43/3800/subpart-3800"
    assert section.source_url == f"{PART_3800_URL}#p-3800.5"


def test_part_scoped_inventory_is_the_whole_inventory_restricted_to_that_part():
    whole = build_ecfr_inventory_from_structures((TITLE_43_STRUCTURE,))

    for part in ("3800", "3830"):
        scoped = build_ecfr_inventory_from_structures((TITLE_43_STRUCTURE,), only_part=part)
        restricted = [item for item in whole.items if _enclosing_part(item) == part]
        assert scoped.part_count == 1
        assert [_without_source_path(item) for item in scoped.items] == [
            _without_source_path(item) for item in restricted
        ]
    scoped_3800 = build_ecfr_inventory_from_structures((TITLE_43_STRUCTURE,), only_part="3800")
    assert "us/regulation/43/3809/1" in _paths(scoped_3800.items)
    assert scoped_3800.items[0].source_path == "ecfr/title-43-part-3800.xml"


def test_a_part_named_only_by_section_identifiers_is_not_a_scope():
    # eCFR has no part 3809, so a run scoped to it finds nothing rather than borrowing
    # part 3800's sections.
    inventory = build_ecfr_inventory_from_structures((TITLE_43_STRUCTURE,), only_part="3809")

    assert inventory.items == ()
    assert inventory.part_count == 0


def test_xml_records_agree_with_the_inventory():
    inventory = build_ecfr_inventory_from_structures((TITLE_43_STRUCTURE,))
    records = _records(TITLE_43_XML, TITLE_43_STRUCTURE, allowed=set(_paths(inventory.items)))

    assert [record.citation_path for record in records] == WHOLE_TITLE_43_PATHS
    items = {item.citation_path: item for item in inventory.items}
    for record in records:
        if record.kind != "section":
            continue
        item = items[record.citation_path]
        assert record.parent_citation_path == item.metadata["parent_citation_path"]
        assert record.source_url == item.source_url
        for key in ("part", "section", "subpart", "enclosing_part"):
            assert record.metadata.get(key) == item.metadata.get(key)

    purposes = {record.citation_path: record for record in records}["us/regulation/43/3809/1"]
    assert purposes.citation_label == "43 CFR 3809.1"
    assert purposes.legal_identifier == "43 CFR 3809.1"
    assert purposes.heading == "What are the purposes of this subpart?"
    assert purposes.body == (
        "The purposes of this subpart are to:\n\n"
        "(a) Prevent unnecessary or undue degradation of public lands."
    )
    assert purposes.parent_citation_path == "us/regulation/43/3800/subpart-3809"
    assert purposes.level == 2
    assert purposes.source_id == "43:2.1.1.3.38.3.1.1"
    assert purposes.source_url == f"{PART_3800_URL}#p-3809.1"
    assert purposes.metadata["enclosing_part"] == "3800"
    assert purposes.identifiers == {
        "ecfr:title": "43",
        "ecfr:part": "3809",
        "ecfr:subpart": "3809",
        "ecfr:section": "1",
    }


@pytest.mark.parametrize("only_part", ["3800", None])
def test_section_selector_takes_the_official_citation(only_part):
    inventory = build_ecfr_inventory_from_structures(
        (TITLE_43_STRUCTURE,), only_part=only_part, only_sections=("3809.2",)
    )

    assert inventory.part_count == 1
    assert _paths(inventory.items) == [
        "us/regulation/43/3800",
        "us/regulation/43/3800/subpart-3809",
        "us/regulation/43/3809/2",
    ]


def test_section_selector_does_not_reach_another_part():
    with pytest.raises(ValueError, match="selector\\(s\\) not found: 3809.1"):
        build_ecfr_inventory_from_structures(
            (TITLE_43_STRUCTURE,), only_part="3830", only_sections=("3809.1",)
        )


# The other live sections of 2026-10-08 that name a part other than the one holding them:
# typeset errors that eCFR publishes, with eCFR's own citation (hierarchy_metadata).
@pytest.mark.parametrize(
    ("title", "part", "subpart", "identifier", "path", "label"),
    [
        (7, "1739", "A", "1735.9", "us/regulation/7/1735/9", "7 CFR 1735.9"),
        (30, "1206", "F", "206.253", "us/regulation/30/206/253", "30 CFR 206.253"),
        (32, "865", "A", "856.7", "us/regulation/32/856/7", "32 CFR 856.7"),
        (48, "1415", "1415.2", "1414.209-70", "us/regulation/48/1414/209-70", "48 CFR 1414.209-70"),
        (41, "105-60", "A", "105.60.001", "us/regulation/41/105/60.001", "41 CFR 105.60.001"),
    ],
)
def test_misnumbered_section_belongs_to_the_part_that_holds_it(
    title, part, subpart, identifier, path, label
):
    structure = {
        "identifier": str(title),
        "label": f"Title {title}",
        "type": "title",
        "children": [
            {
                "identifier": part,
                "label": f"Part {part}—Heading",
                "type": "part",
                "children": [
                    _subpart(subpart, f"Subpart {subpart}—Heading", [
                        _section(f"{part}.1", f"§ {part}.1 First."),
                        _section(identifier, f"§ {identifier} Misnumbered."),
                    ]),
                ],
            }
        ],
    }
    xml = (
        f'<ECFR><DIV5 N="{part}" TYPE="PART"><HEAD>PART {part}</HEAD>'
        f'<DIV6 N="{subpart}" TYPE="SUBPART"><HEAD>Subpart {subpart}</HEAD>'
        f'<DIV8 N="{part}.1" TYPE="SECTION"><HEAD>§ {part}.1 First.</HEAD><P>One.</P></DIV8>'
        f'<DIV8 N="{identifier}" TYPE="SECTION"><HEAD>§ {identifier} Misnumbered.</HEAD>'
        "<P>Two.</P></DIV8></DIV6></DIV5></ECFR>"
    )
    subpart_path = f"us/regulation/{title}/{part}/subpart-{subpart}"

    scoped = build_ecfr_inventory_from_structures((structure,), only_part=part)
    whole = build_ecfr_inventory_from_structures((structure,))
    assert [_without_source_path(item) for item in scoped.items] == [
        _without_source_path(item) for item in whole.items
    ]
    assert _paths(scoped.items)[-1] == path
    assert _valid_citation_path(path)
    item = scoped.items[-1]
    assert item.metadata["parent_citation_path"] == subpart_path
    assert item.metadata["enclosing_part"] == part
    assert item.source_url == f"https://www.ecfr.gov/current/title-{title}/part-{part}#p-{identifier}"

    records = _records(xml, structure, allowed=set(_paths(scoped.items)))
    assert [record.citation_path for record in records] == _paths(scoped.items)
    assert records[-1].legal_identifier == label
    assert records[-1].parent_citation_path == subpart_path
    assert records[-1].body == "Two."


def test_two_sections_claiming_one_citation_path_fail_closed():
    # If part 1735 had a live § 1735.9 beside part 1739's misnumbered one, both would be
    # us/regulation/7/1735/9.
    structure = {
        "identifier": "7",
        "label": "Title 7",
        "type": "title",
        "children": [
            {
                "identifier": "1735",
                "label": "Part 1735—Telecommunications Program",
                "type": "part",
                "children": [_section("1735.9", "§ 1735.9 Live.")],
            },
            {
                "identifier": "1739",
                "label": "Part 1739—Broadband Grant Program",
                "type": "part",
                "children": [
                    _subpart("A", "Subpart A—Community Connect", [
                        _section("1735.9", "§ 1735.9 USDA Rural Development State Director notification."),
                    ]),
                ],
            },
        ],
    }

    with pytest.raises(ValueError, match="'us/regulation/7/1735/9' is claimed twice"):
        build_ecfr_inventory_from_structures((structure,))
    # Each part alone holds one claim.
    for part in ("1735", "1739"):
        assert "us/regulation/7/1735/9" in _paths(
            build_ecfr_inventory_from_structures((structure,), only_part=part).items
        )


def _patch_fetchers(monkeypatch):
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: TITLE_43_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: TITLE_43_XML)
    monkeypatch.setattr(ecfr, "fetch_ecfr_title_xml", lambda title, as_of: TITLE_43_XML)


@pytest.mark.parametrize("only_part", ["3800", None])
def test_extract_ecfr_writes_group_part_sections_under_the_part_that_holds_them(
    tmp_path, monkeypatch, only_part
):
    _patch_fetchers(monkeypatch)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-10-12",
        as_of="2026-10-08",
        expression_date=date(2026, 10, 8),
        only_title=43,
        only_part=only_part,
        workers=1,
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    expected = [
        path for path in WHOLE_TITLE_43_PATHS if only_part is None or "/3830" not in path
    ]
    assert [record.citation_path for record in records] == expected
    by_path = {record.citation_path: record for record in records}
    for record in records:
        # Every parent is a record of the run, and no record is a structure-only stand-in.
        assert record.parent_citation_path is None or record.parent_citation_path in by_path
        assert not (record.metadata or {}).get("structure_only")
    assert by_path["us/regulation/43/3809/2"].body == "(a) Mining claims and millsites."
    assert by_path["us/regulation/43/3809/2"].parent_citation_path == (
        "us/regulation/43/3800/subpart-3809"
    )


def test_extract_ecfr_local_source_xml_selects_a_group_part_section(tmp_path):
    source_xml = tmp_path / "official-title-43-part-3800.xml"
    source_xml.write_text(TITLE_43_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-10-12",
        as_of="2026-10-08",
        expression_date=date(2026, 10, 8),
        source_xml=source_xml,
        only_title=43,
        only_part="3800",
        only_sections=("3809.1",),
        workers=1,
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/43/3800",
        "us/regulation/43/3800/subpart-3809",
        "us/regulation/43/3809/1",
    ]
    assert records[2].parent_citation_path == "us/regulation/43/3800/subpart-3809"
    assert records[2].legal_identifier == "43 CFR 3809.1"


def test_ecfr_cli_takes_a_group_part_and_its_section(tmp_path, monkeypatch, capsys):
    from axiom_corpus.corpus.cli import main

    _patch_fetchers(monkeypatch)
    base = tmp_path / "corpus"
    common = ["--base", str(base), "--version", "2026-10-12", "--as-of", "2026-10-08",
              "--only-title", "43", "--only-part", "3800"]

    assert main(["inventory-ecfr", *common, "--section", "3809.1"]) == 0
    assert json.loads(capsys.readouterr().out)["items_written"] == 3
    assert main(["extract-ecfr", *common]) == 0
    output = json.loads(capsys.readouterr().out)

    records = load_provisions(Path(output["provisions_path"]))
    assert [record.citation_path for record in records] == WHOLE_TITLE_43_PATHS[:8]


# 14 CFR part 241 numbers its own sections 19-8.1 to 19-8.10. The XML search finds
# PART.SECTION anywhere in N, so it reads "19-8.1" as 8.1.
TITLE_14_PART_241_XML = """<ECFR>
  <DIV5 N="241" TYPE="PART">
    <HEAD>PART 241—UNIFORM SYSTEM OF ACCOUNTS AND REPORTS</HEAD>
    <DIV8 N="241.1" TYPE="SECTION"><HEAD>§ 241.1 Applicability.</HEAD><P>Text.</P></DIV8>
    <DIV8 N="19-8.1" TYPE="SECTION"><HEAD>§ 19-8.1 Definitions.</HEAD><P>Body of 19-8.1.</P></DIV8>
    <DIV8 N="§ 3809.1" TYPE="SECTION"><HEAD>§ 3809.1 Numbered for another part.</HEAD><P>Body.</P></DIV8>
  </DIV5>
</ECFR>
"""


def test_retained_xml_does_not_take_a_partial_match_as_another_parts_section(tmp_path):
    source_xml = tmp_path / "official-title-14-part-241.xml"
    source_xml.write_text(TITLE_14_PART_241_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")
    common = {"version": "2026-10-12", "as_of": "2026-10-08", "source_xml": source_xml,
              "only_title": 14, "only_part": "241", "workers": 1}

    # "19-8.1" is not § 8.1 of part 241: the selector finds nothing, and nothing is
    # written.
    with pytest.raises(ValueError, match=r"not found in retained XML: 8\.1"):
        extract_ecfr(store, only_sections=("8.1",), **common)
    assert not store.root.exists() or not any(path.is_file() for path in store.root.rglob("*"))

    # A section that is numbered for another part, and published so, is read as such.
    report = extract_ecfr(store, only_sections=("3809.1",), **common)
    records = load_provisions(report.provisions_path)
    assert [(record.citation_path, record.legal_identifier) for record in records] == [
        ("us/regulation/14/241", "14 CFR part 241"),
        ("us/regulation/14/3809/1", "14 CFR 3809.1"),
    ]
    assert records[1].parent_citation_path == "us/regulation/14/241"
    assert records[1].metadata["enclosing_part"] == "241"


# A sibling the XML search misreads: "19-3809.401-k-1" holds "3809.401-k-1", which folds
# to the path of § 3809.401(k)-1.
PART_3800_SIBLING_XML = """<ECFR>
  <DIV5 N="3800" TYPE="PART">
    <HEAD>PART 3800—MINING CLAIMS UNDER THE GENERAL MINING LAWS</HEAD>
    <DIV8 N="3809.401(k)-1" TYPE="SECTION" NODE="selected">
      <HEAD>§ 3809.401(k)-1 Selected.</HEAD><P>Selected body.</P>
    </DIV8>
    <DIV8 N="19-3809.401-k-1" TYPE="SECTION" NODE="sibling">
      <HEAD>19-3809.401-k-1 Another published section.</HEAD><P>Sibling body.</P>
      <MATH><img src="/graphics/ec05no91.090.gif"/></MATH>
    </DIV8>
  </DIV5>
</ECFR>
"""


def test_misread_sibling_cannot_take_a_selected_sections_path(tmp_path, monkeypatch):
    # Retained XML: the selected section is written with its own body; the sibling is
    # neither written nor captured for graphics.
    monkeypatch.setattr(
        ecfr, "fetch_ecfr_graphic", lambda identifier: pytest.fail(f"captured {identifier}")
    )
    source_xml = tmp_path / "official-title-43-part-3800.xml"
    source_xml.write_text(PART_3800_SIBLING_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store, version="2026-10-12", as_of="2026-10-08", source_xml=source_xml,
        only_title=43, only_part="3800", only_sections=("3809.401(k)-1",), workers=1,
    )

    assert report.coverage.complete and not report.title_errors
    section = load_provisions(report.provisions_path)[-1]
    assert section.citation_path == "us/regulation/43/3809/401-k-1"
    assert section.legal_identifier == "43 CFR 3809.401(k)-1"
    assert section.body == "Selected body."
    assert section.source_id == "selected"

    # The same holds for the XML pass under an inventory from the eCFR structure.
    structure = {"identifier": "43", "label": "Title 43", "type": "title", "children": [
        {"identifier": "3800", "label": "Part 3800", "type": "part",
         "children": [_section("3809.401(k)-1", "§ 3809.401(k)-1 Selected.")]},
    ]}
    inventory = build_ecfr_inventory_from_structures((structure,))
    records = _records(PART_3800_SIBLING_XML, structure, allowed=set(_paths(inventory.items)))
    assert [(record.citation_path, record.source_id) for record in records] == [
        ("us/regulation/43/3800", None),
        ("us/regulation/43/3809/401-k-1", "selected"),
    ]

    # And for sections inside a subpart.
    structure["children"][0]["children"] = [
        _subpart("3809", "Subpart 3809", structure["children"][0]["children"])
    ]
    xml = PART_3800_SIBLING_XML.replace(
        '<DIV8 N="3809.401(k)-1"', '<DIV6 N="3809" TYPE="SUBPART"><DIV8 N="3809.401(k)-1"'
    ).replace("</DIV8>\n  </DIV5>", "</DIV8></DIV6>\n  </DIV5>")
    inventory = build_ecfr_inventory_from_structures((structure,))
    records = _records(xml, structure, allowed=set(_paths(inventory.items)))
    assert [(record.citation_path, record.source_id) for record in records] == [
        ("us/regulation/43/3800", None),
        ("us/regulation/43/3800/subpart-3809", None),
        ("us/regulation/43/3809/401-k-1", "selected"),
    ]


@pytest.mark.parametrize("part", ["3800", "3809"])
def test_retained_selector_naming_two_sections_fails_before_any_write(tmp_path, part):
    # The same N in two subparts, in the part that holds § 3809.1 or the part it names.
    xml = (
        f'<ECFR><DIV5 N="{part}" TYPE="PART"><HEAD>PART {part}</HEAD>'
        '<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A</HEAD>'
        '<DIV8 N="3809.1" TYPE="SECTION"><HEAD>§ 3809.1 A</HEAD><P>First body</P></DIV8></DIV6>'
        '<DIV6 N="B" TYPE="SUBPART"><HEAD>Subpart B</HEAD>'
        '<DIV8 N="3809.1" TYPE="SECTION"><HEAD>§ 3809.1 B</HEAD><P>Second body</P></DIV8></DIV6>'
        "</DIV5></ECFR>"
    )
    source_xml = tmp_path / "official.xml"
    source_xml.write_text(xml)
    store = CorpusArtifactStore(tmp_path / "corpus")

    with pytest.raises(ValueError, match="3809.1 names more than one section in retained XML"):
        extract_ecfr(
            store, version="2026-10-12", as_of="2026-10-08", source_xml=source_xml,
            only_title=43, only_part=part, only_sections=("3809.1",), workers=1,
        )
    assert not store.root.exists() or not any(path.is_file() for path in store.root.rglob("*"))


def test_two_xml_elements_under_one_citation_path_are_a_title_error(tmp_path, monkeypatch):
    # The XML search reads "19-3800.5" as 3800.5, the path of the section before it. The
    # later record would replace the earlier, so the title fails before writing artifacts.
    xml = TITLE_43_XML.replace(
        '<DIV8 N="3802.0-1"',
        '<DIV8 N="19-3800.5" TYPE="SECTION" NODE="misread"><HEAD>19-3800.5 Other.</HEAD>'
        '<P>Other body.</P></DIV8>\n      <DIV8 N="3802.0-1"',
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: TITLE_43_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    store = CorpusArtifactStore(tmp_path / "corpus")

    with pytest.raises(ValueError, match="'us/regulation/43/3800/5' twice") as exc:
        extract_ecfr(
            store, version="2026-10-12", as_of="2026-10-08", only_title=43, only_part="3800",
            workers=1,
        )

    assert "'43:2.1.1.3.38.1.1.1' and 'misread'" in str(exc.value)
    assert not any(path.is_file() for path in store.root.rglob("*"))


@pytest.mark.parametrize("resumed", [False, True])
@pytest.mark.parametrize("allow_incomplete", [False, True])
def test_retained_duplicate_rebuild_is_fatal_and_preserves_run(
    tmp_path, monkeypatch, capsys, resumed, allow_incomplete
):
    # Review #841: only one selector is requested, so the scoped inventory misses
    # the other element whose distinct N folds to the selected citation path.
    monkeypatch.chdir(tmp_path)
    _assert_collision_rebuild_preserves_run(
        tmp_path, "3800", "3809.401(k)-1", "3809.401-k-1",
        resumed=resumed, allow_incomplete=allow_incomplete,
    )
    assert "twice" in capsys.readouterr().err


def _assert_collision_rebuild_preserves_run(
    root, part, selected, conflicting, *, resumed, allow_incomplete, reverse=False
):
    from axiom_corpus.corpus.cli import main

    source = root / "official.xml"
    store = CorpusArtifactStore(root / "corpus")
    section = (
        f'<DIV8 N="{selected}" TYPE="SECTION" NODE="good"><HEAD>Selected</HEAD>'
        '<P>Saved body.</P></DIV8>'
    )
    prefix = f'<ECFR><DIV5 N="{part}" TYPE="PART"><HEAD>Part {part}</HEAD>'
    suffix = "</DIV5></ECFR>"
    source.write_text(prefix + section + suffix)
    args = [
        "extract-ecfr", "--base", str(store.root), "--version", "review",
        "--as-of", "2026-10-08", "--source-xml", str(source),
        "--only-title", "43", "--only-part", part, "--section", selected,
        "--workers", "1",
    ]
    if resumed:
        assert main(args) == 0
    before = {p.relative_to(store.root): p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    replacement = section.replace("Saved body.", "Changed selected body.")
    other = (
        f'<DIV8 N="{conflicting}" TYPE="SECTION" NODE="bad"><HEAD>Sibling</HEAD>'
        '<P>Conflicting body.</P></DIV8>'
    )
    elements = other + replacement if reverse else replacement + other
    source.write_text(prefix + elements + suffix)

    assert main([*args, *(["--allow-incomplete"] if allow_incomplete else [])]) == 2
    after = {p.relative_to(store.root): p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    # Invariant: rejecting an ambiguous identity leaves all four artifact families
    # byte-for-byte intact (or absent on a fresh run), including the source snapshot.
    assert after == before


@settings(
    max_examples=40, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    part=st.sampled_from(["3800", "3809"]),
    number=st.integers(min_value=1, max_value=999),
    letter=st.sampled_from(list("akz")),
    tail=st.integers(min_value=1, max_value=9),
    resumed=st.booleans(), allow_incomplete=st.booleans(), reverse=st.booleans(),
)
def test_property_duplicate_rebuild_is_fatal_and_preserves_run(
    tmp_path, monkeypatch, part, number, letter, tail, resumed, allow_incomplete, reverse
):
    monkeypatch.chdir(tmp_path)
    with tempfile.TemporaryDirectory(dir=tmp_path) as tmp:
        _assert_collision_rebuild_preserves_run(
            Path(tmp), part, f"3809.{number}({letter})-{tail}",
            f"3809.{number}-{letter}-{tail}", resumed=resumed,
            allow_incomplete=allow_incomplete, reverse=reverse,
        )


@pytest.mark.parametrize("allow_incomplete", [False, True])
def test_remote_duplicate_xml_is_fatal_before_writing(tmp_path, monkeypatch, capsys, allow_incomplete):
    from axiom_corpus.corpus.cli import main

    monkeypatch.chdir(tmp_path)
    structure = {"type": "title", "identifier": "43", "children": [
        {"type": "part", "identifier": "3800", "children": [
            {"type": "section", "identifier": "3809.401(k)-1"},
        ]},
    ]}
    xml = (
        '<ECFR><DIV5 N="3800" TYPE="PART"><HEAD>Part 3800</HEAD>'
        '<DIV8 N="3809.401(k)-1" TYPE="SECTION" NODE="good"><P>Selected.</P></DIV8>'
        '<DIV8 N="3809.401-k-1" TYPE="SECTION" NODE="bad"><P>Conflicting.</P></DIV8>'
        '</DIV5></ECFR>'
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    store = CorpusArtifactStore(tmp_path / "corpus")
    args = [
        "extract-ecfr", "--base", str(store.root), "--version", "review",
        "--as-of", "2026-10-08", "--only-title", "43", "--only-part", "3800",
        "--workers", "1", *(["--allow-incomplete"] if allow_incomplete else []),
    ]

    assert main(args) == 2
    assert "twice" in capsys.readouterr().err
    assert not any(p.is_file() for p in store.root.rglob("*"))


def _assert_remote_collision_precedes_graphics(
    root, monkeypatch, capsys, *, failure, selected="3809.401(k)-1",
    conflicting="3809.401-k-1", allow_incomplete=False, reverse=False,
):
    from axiom_corpus.corpus.cli import main

    capsys.readouterr()
    structure = {"type": "title", "identifier": "43", "children": [
        {"type": "part", "identifier": "3800", "children": [
            {"type": "section", "identifier": selected},
        ]},
    ]}
    prefix = '<ECFR><DIV5 N="3800" TYPE="PART"><HEAD>Part 3800</HEAD>'
    suffix = '</DIV5></ECFR>'
    section = (
        f'<DIV8 N="{selected}" TYPE="SECTION" NODE="good"><HEAD>Selected</HEAD>'
        '<P>Saved body.</P></DIV8>'
    )
    xml = prefix + section + suffix
    fetched_graphics = []

    def fetch_graphic(identifier):
        fetched_graphics.append(identifier)
        if failure == "invalid_png":
            return b"not a PNG"
        if failure == "failed_download":
            raise urllib.error.HTTPError("https://example.gov/graphic", 404, "missing", {}, None)
        if failure == "timeout":
            raise TimeoutError("graphic timed out")
        raise urllib.error.URLError("graphic unavailable")

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda *args: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch_graphic)
    monkeypatch.setattr(ecfr.time, "sleep", lambda _: None)
    store = CorpusArtifactStore(root / "corpus")
    args = [
        "extract-ecfr", "--base", str(store.root), "--version", "review",
        "--as-of", "2026-10-08", "--only-title", "43", "--only-part", "3800",
        "--section", selected, "--workers", "1",
    ]
    assert main(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["coverage_complete"]
    assert [r.body for r in load_provisions(Path(output["provisions_path"])) if r.kind == "section"] == [
        "Saved body."
    ]
    # Resume with complete cached rows but no source: re-fetch must validate the
    # new identities before any graphic failure can bind those rows to new bytes.
    next((store.root / "sources").rglob("*.xml")).unlink()
    before = {p.relative_to(store.root): p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    replacement = section.replace("Saved body.", "Changed body.").replace(
        "</DIV8>", '<MATH><IMG src="/graphics/ec05no91.090.gif"/></MATH></DIV8>'
    )
    other = (
        f'<DIV8 N="{conflicting}" TYPE="SECTION" NODE="bad"><HEAD>Sibling</HEAD>'
        '<P>Conflicting body.</P></DIV8>'
    )
    xml = prefix + (other + replacement if reverse else replacement + other) + suffix
    if failure == "malformed_xml":
        xml = xml.removesuffix("</ECFR>")
    assert "Saved body." not in xml

    assert main([*args, *(["--allow-incomplete"] if allow_incomplete else [])]) == 2
    expected_error = "cannot validate replacement XML" if failure == "malformed_xml" else "twice"
    assert expected_error in capsys.readouterr().err
    assert fetched_graphics == []
    assert {p.relative_to(store.root): p.read_bytes() for p in store.root.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("failure", ["invalid_png", "failed_download"])
@pytest.mark.parametrize("allow_incomplete", [False, True])
def test_remote_duplicate_rebuild_precedes_graphics_errors(
    tmp_path, monkeypatch, capsys, failure, allow_incomplete
):
    monkeypatch.chdir(tmp_path)
    _assert_remote_collision_precedes_graphics(
        tmp_path, monkeypatch, capsys, failure=failure, allow_incomplete=allow_incomplete,
    )


@pytest.mark.parametrize("allow_incomplete", [False, True])
def test_remote_malformed_rebuild_is_fatal_and_preserves_run(
    tmp_path, monkeypatch, capsys, allow_incomplete,
):
    monkeypatch.chdir(tmp_path)
    _assert_remote_collision_precedes_graphics(
        tmp_path, monkeypatch, capsys, failure="malformed_xml", allow_incomplete=allow_incomplete,
    )


@settings(
    max_examples=30, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    number=st.integers(min_value=1, max_value=999),
    failure=st.sampled_from(["invalid_png", "failed_download", "timeout", "url_error", "malformed_xml"]),
    allow_incomplete=st.booleans(), reverse=st.booleans(),
)
def test_property_remote_collision_precedes_recoverable_graphics_errors(
    tmp_path, monkeypatch, capsys, number, failure, allow_incomplete, reverse
):
    monkeypatch.chdir(tmp_path)
    with tempfile.TemporaryDirectory(dir=tmp_path) as tmp, monkeypatch.context() as patch:
        _assert_remote_collision_precedes_graphics(
            Path(tmp), patch, capsys, failure=failure,
            selected=f"3809.{number}(a)", conflicting=f"3809.{number}-a",
            allow_incomplete=allow_incomplete, reverse=reverse,
        )


@pytest.mark.parametrize("appendix_first", [False, True])
def test_remote_partial_provision_validation_fails_before_writing(
    tmp_path, monkeypatch, appendix_first,
):
    # A renderer error before or after colliding sections must also fail closed.
    # The structure selects appendix A, but the XML claims a contradictory part.
    sections = (
        '<DIV8 N="3809.1(a)" TYPE="SECTION"><P>Selected.</P></DIV8>'
        '<DIV8 N="3809.1-a" TYPE="SECTION"><P>Conflicting.</P></DIV8>'
    )
    appendix = '<DIV9 N="Appendix A to Part 3801" TYPE="APPENDIX"><P>Appendix.</P></DIV9>'
    xml = ('<ECFR><DIV5 N="3800" TYPE="PART"><HEAD>Part 3800</HEAD>'
           + (appendix + sections if appendix_first else sections + appendix)
           + '</DIV5></ECFR>')
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: xml)
    monkeypatch.setattr(
        ecfr, "fetch_ecfr_graphic", lambda _: pytest.fail("captured graphics before validation")
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    with pytest.raises(ValueError, match="conflicts with enclosing part|twice"):
        ecfr._extract_one_title(
            store, 43, (ecfr.EcfrPartTarget(title=43, part="3800"),), "review", "review",
            "2026-10-08", "2026-10-08",
            {"us/regulation/43/3800", "us/regulation/43/3809/1-a",
             "us/regulation/43/3800/appendix-a"},
            "3800", None, True,
        )
    assert not any(p.is_file() for p in store.root.rglob("*"))


@pytest.mark.parametrize("failure", ["http_error", "url_error", "timeout"])
def test_remote_xml_download_error_has_no_unvalidated_source(tmp_path, monkeypatch, failure):
    def fetch(*args):
        if failure == "http_error":
            raise urllib.error.HTTPError("https://example.gov/xml", 404, "missing", {}, None)
        if failure == "timeout":
            raise TimeoutError("XML timed out")
        raise urllib.error.URLError("XML unavailable")

    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", fetch)
    monkeypatch.setattr(ecfr.time, "sleep", lambda _: None)
    store = CorpusArtifactStore(tmp_path / "corpus")

    result = ecfr._extract_one_title(
        store, 43, (ecfr.EcfrPartTarget(title=43, part="3800"),), "review", "review",
        "2026-10-08", "2026-10-08", {"us/regulation/43/3809/1"}, "3800", None, False,
    )

    assert result.error is not None
    assert result.provisions == ()
    assert not any(p.is_file() for p in store.root.rglob("*"))


def test_recoverable_xml_error_retains_snapshot_for_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: TITLE_43_STRUCTURE)
    calls = []

    def fetch(title, part, as_of):
        calls.append((title, part, as_of))
        assert len(calls) == 1, "resume must reuse the saved snapshot"
        return "<ECFR>"

    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", fetch)
    store = CorpusArtifactStore(tmp_path / "corpus")
    for _ in range(2):
        report = extract_ecfr(
            store, version="review", as_of="2026-10-08", only_title=43,
            only_part="3800", only_sections=("3809.1",), workers=1,
        )
        assert report.title_error_count == 1
        assert not report.coverage.complete
    assert len(calls) == 1
    assert [p.read_text() for p in (store.root / "sources").rglob("*.xml")] == ["<ECFR>"]


@pytest.mark.parametrize(
    ("second", "path"),
    [
        ({"identifier": "3800", "label": "Part 3800 again", "type": "part", "children": []},
         "us/regulation/43/3800"),
        ({"identifier": "3801", "label": "Part 3801", "type": "part", "children": [
            _subpart("A", "Subpart A", []), _subpart("A", "Subpart A again", [])]},
         "us/regulation/43/3801/subpart-A"),
    ],
)
def test_duplicate_guard_covers_parts_and_subparts(second, path):
    structure = {"identifier": "43", "label": "Title 43", "type": "title", "children": [
        {"identifier": "3800", "label": "Part 3800", "type": "part", "children": []}, second,
    ]}

    with pytest.raises(ValueError, match=f"'{path}' is claimed twice"):
        build_ecfr_inventory_from_structures((structure,))


def test_duplicate_guard_spans_every_structure_of_a_call():
    def title_7(part, holder_subpart=None):
        section = _section("1735.9", "§ 1735.9 Heading.")
        children = [_subpart(holder_subpart, "Subpart A", [section])] if holder_subpart else [section]
        return {"identifier": "7", "label": "Title 7", "type": "title", "children": [
            {"identifier": part, "label": f"Part {part}", "type": "part", "children": children}
        ]}

    with pytest.raises(ValueError, match="'us/regulation/7/1735/9' is claimed twice"):
        build_ecfr_inventory_from_structures((title_7("1735"), title_7("1739", "A")))
    # The same numbers in another title are another path.
    other = title_7("1739", "A")
    other["identifier"] = "8"
    assert "us/regulation/8/1735/9" in _paths(
        build_ecfr_inventory_from_structures((title_7("1735"), other)).items
    )


# --- Properties --------------------------------------------------------------------
#
# Generated titles mix parts whose sections name them with BLM-style group parts, whose
# subparts number their own sections, and sections that name another part outright.
# A section identifier is PREFIX.NUMBER, where PREFIX is the enclosing part, a number from
# a small pool that other parts of the title may also use, or a hyphenated number that no
# grammar reads in an alphanumeric part ("19-8.1" in 14 CFR part 241). Parts and subparts
# are sometimes reserved, with live sections inside, and some numbers carry parenthesised
# groups that fold into the path segment ("401(k)-1" is 401-k-1), so two identifiers can
# claim one path. Each structure is one title; limit and selectors are outside the
# partition property (the selector property and the example tests cover selectors).


def _chars(alphabet, **kwargs):
    # Strings drawn character by character: Hypothesis 6.168's text() shrinker can raise
    # an internal "32 is not in list" while shrinking a failure on these alphabets.
    return st.lists(st.sampled_from(alphabet), **kwargs).map("".join)


_POOL = ["3800", "3809", "3830", "1735", "1739", "206"]
_PARTS = st.one_of(st.sampled_from(_POOL), st.sampled_from(["60-20", "105-60"]))
# (section number, its path segment), the segment written out rather than computed.
_NUMBERS = st.one_of(
    st.integers(0, 600).map(lambda n: (str(n), str(n))),
    st.builds(lambda a, b: (f"{a}-{b}", f"{a}-{b}"), st.integers(0, 9), st.integers(1, 9)),
    st.sampled_from([
        ("1(a)", "1-a"), ("1-a", "1-a"), ("401(k)-1", "401-k-1"), ("3121(a)(1)-1", "3121-a-1-1"),
    ]),
)


def _rarely(draw):
    return draw(st.booleans()) and draw(st.booleans())


@st.composite
def _sections(draw, part):
    """Live and reserved sections of one container."""
    nodes = []
    for _ in range(draw(st.integers(0, 4))):
        prefix = draw(st.one_of(st.just(part), st.sampled_from(_POOL), st.just("19-8")))
        number, segment = draw(_NUMBERS)
        identifier = f"{prefix}.{number}"
        node = _section(identifier, f"§ {identifier} Heading.", reserved=_rarely(draw))
        node["_segment"] = segment  # for the reference model; the adapter ignores it
        nodes.append(node)
    return nodes


@st.composite
def _group_titles(draw):
    parts = draw(st.lists(_PARTS, min_size=1, max_size=4, unique=True))
    children = []
    for part in parts:
        part_children = draw(_sections(part))
        subparts = draw(st.lists(
            st.one_of(st.just(part), st.sampled_from(_POOL), st.sampled_from(["A", "B"])),
            max_size=3,
            unique=True,
        ))
        for subpart in subparts:
            sections = draw(_sections(subpart if subpart not in ("A", "B") else part))
            if sections and draw(st.booleans()):
                sections = [{"identifier": f"ECFR{subpart}", "label": "Group", "type": "subject_group",
                             "children": sections}]
            node = _subpart(subpart, f"Subpart {subpart}—Heading", sections)
            if _rarely(draw):
                node["reserved"] = True
            part_children.append(node)
        node = {"identifier": part, "label": f"Part {part}—Heading", "type": "part",
                "children": part_children}
        if _rarely(draw):
            node["reserved"] = True
        children.append(node)
    return {"identifier": "43", "label": "Title 43", "type": "title", "children": children}


def _expected_sections(structure, *, reserved=False):
    """Reference model: each live section the inventory should hold, in structure order.

    Tuples of (citation path, cited part, enclosing part, parent path, identifier). A
    reserved part or subpart holds no live section. With ``reserved``, every section
    node is included, reserved or under a reserved container: the XML pass cannot tell
    them apart, so it emits one under any path the inventory allows.
    """
    title = structure["identifier"]
    rows = []

    def walk(node, part=None, subpart=None):
        kind = node["type"]
        if node.get("reserved") and not reserved:
            return
        if kind == "part":
            part = node["identifier"]
        if kind == "subpart":
            subpart = node["identifier"]
        if kind == "section":
            prefix = node["identifier"].split(".", 1)[0]
            if "-" in prefix and prefix != part:
                return  # no grammar reads a foreign hyphenated part
            part_path = f"us/regulation/{title}/{part}"
            parent = f"{part_path}/subpart-{subpart}" if subpart else part_path
            rows.append((f"us/regulation/{title}/{prefix}/{node['_segment']}", prefix, part,
                         parent, node["identifier"]))
            return
        for child in node.get("children", []):
            walk(child, part, subpart)

    walk(structure)
    return rows


def _render_xml(structure):
    def node_xml(node):
        kind = node["type"]
        inner = "".join(node_xml(child) for child in node.get("children", []))
        if kind == "section":
            return (f'<DIV8 N="{node["identifier"]}" TYPE="SECTION"><HEAD>{node["label"]}</HEAD>'
                    f'<P>Body of {node["identifier"]}.</P></DIV8>')
        if kind == "subject_group":
            return f'<DIV7 N="{node["identifier"]}" TYPE="SUBJGRP"><HEAD>Group</HEAD>{inner}</DIV7>'
        if kind == "subpart":
            return f'<DIV6 N="{node["identifier"]}" TYPE="SUBPART"><HEAD>{node["label"]}</HEAD>{inner}</DIV6>'
        return f'<DIV5 N="{node["identifier"]}" TYPE="PART"><HEAD>{node["label"]}</HEAD>{inner}</DIV5>'

    return "<ECFR>" + "".join(node_xml(part) for part in structure["children"]) + "</ECFR>"


def _duplicated(paths):
    return len(set(paths)) != len(paths)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(structure=_group_titles())
def test_property_inventory_raises_exactly_when_two_sections_claim_one_path(structure):
    expected = _expected_sections(structure)
    parts = [node["identifier"] for node in structure["children"]]

    scopes = [None, *parts]
    for only_part in scopes:
        rows = [row for row in expected if only_part is None or row[2] == only_part]
        if _duplicated([row[0] for row in rows]):
            with pytest.raises(ValueError, match="is claimed twice"):
                build_ecfr_inventory_from_structures((structure,), only_part=only_part)
        else:
            build_ecfr_inventory_from_structures((structure,), only_part=only_part)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(structure=_group_titles())
def test_property_part_scoped_inventories_partition_the_whole_inventory(structure):
    expected = _expected_sections(structure)
    assume(not _duplicated([row[0] for row in _expected_sections(structure, reserved=True)]))
    whole = build_ecfr_inventory_from_structures((structure,))
    paths = _paths(whole.items)

    # Sections: the reference model's, in structure order, each read as its citation and
    # parented by the part that holds it.
    sections = [item for item in whole.items if item.metadata["kind"] == "section"]
    assert [item.citation_path for item in sections] == [row[0] for row in expected]
    for item, (_path, cited, enclosing, parent, identifier) in zip(sections, expected, strict=True):
        metadata = item.metadata
        assert f"{metadata['part']}.{metadata['section']}" == identifier
        assert metadata["part"] == cited
        assert metadata["parent_citation_path"] == parent
        assert metadata.get("enclosing_part") == (enclosing if cited != enclosing else None)
        assert item.source_url.endswith(f"/part-{enclosing}#p-{identifier}")

    # Identity: unique, schema-valid paths, each parent present and earlier.
    assert not _duplicated(paths)
    seen = set()
    for item in whole.items:
        parent = item.metadata.get("parent_citation_path")
        assert parent is None or parent in seen
        seen.add(item.citation_path)
        assert _valid_citation_path(item.citation_path)

    # Partition: each part-scoped inventory is the whole inventory restricted to the items
    # that part holds, and the scopes together are the whole inventory, in order.
    union = []
    for part in [node["identifier"] for node in structure["children"]]:
        scoped = build_ecfr_inventory_from_structures((structure,), only_part=part)
        restricted = [item for item in whole.items if _enclosing_part(item) == part]
        assert [_without_source_path(item) for item in scoped.items] == [
            _without_source_path(item) for item in restricted
        ]
        reserved_part = next(n for n in structure["children"] if n["identifier"] == part).get("reserved")
        assert scoped.part_count == (0 if reserved_part else 1)
        union.extend(scoped.items)
    assert [_without_source_path(item) for item in union] == [
        _without_source_path(item) for item in whole.items
    ]

    # Agreement: the XML pass, allowlisted by the inventory, yields every inventory path
    # with the inventory's parent, part, section, enclosing part and URL.
    records = _records(_render_xml(structure), structure, allowed=set(paths))
    assert [record.citation_path for record in records] == paths
    items = {item.citation_path: item for item in whole.items}
    for record in records:
        if record.kind != "section":
            continue
        item = items[record.citation_path]
        assert record.parent_citation_path == item.metadata["parent_citation_path"]
        assert record.source_url == item.source_url
        for key in ("part", "section", "subpart", "enclosing_part"):
            assert record.metadata.get(key) == item.metadata.get(key)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(structure=_group_titles(), data=st.data())
def test_property_section_selector_returns_the_section_and_its_ancestors(structure, data):
    expected = _expected_sections(structure)
    assume(expected and not _duplicated([row[0] for row in _expected_sections(structure, reserved=True)]))
    path, _cited, enclosing, parent, identifier = data.draw(st.sampled_from(expected))
    # A selector names one section; an identifier repeated in a scope is ambiguous.
    assume([row[4] for row in expected if row[2] == enclosing].count(identifier) == 1)

    inventory = build_ecfr_inventory_from_structures(
        (structure,), only_part=enclosing, only_sections=(identifier,)
    )

    part_path = f"us/regulation/43/{enclosing}"
    assert _paths(inventory.items) == list(dict.fromkeys([part_path, parent, path]))
    assert inventory.part_count == 1


# The alphanumeric PART.SECTION grammar of main (89dc519fa), kept as the reference.
ALNUM_SECTION_IDENTIFIER = r"([0-9A-Za-z]+)\.([0-9A-Za-z][0-9A-Za-z.()-]*)"


@settings(max_examples=500, deadline=None)
@given(
    title=st.integers(1, 50),
    part=st.one_of(st.sampled_from(["241", "3800", "60-20", "105-60"]), _chars("0123456789", min_size=1, max_size=4)),
    n_attr=st.one_of(
        _chars("0123456789aZ.-() §", max_size=14),
        st.builds(lambda a, b: f"{a}.{b}", st.sampled_from(["3809", "19-8", "241", "60-20", "8"]),
                  _chars("0123456789a()-", min_size=1, max_size=6)),
    ),
)
def test_property_retained_xml_reads_another_parts_section_only_as_its_identifier_reads(
    title, part, n_attr
):
    """A retained part XML admits a section numbered for another part only when the
    structure grammar reads its published identifier to the XML's reading; a section
    that names its own part is admitted as before."""
    xml = (f'<ECFR><DIV5 N="{part}" TYPE="PART"><HEAD>PART {part}</HEAD>'
           f'<DIV8 N="{n_attr}" TYPE="SECTION"><HEAD>Heading</HEAD><P>Body.</P></DIV8></DIV5></ECFR>')
    reading = ecfr._section_citation_from_element(
        title, ET.fromstring(xml).find("DIV5/DIV8"), part
    )
    assume(reading is not None)
    path, cited, section = reading
    selector = f"{cited}.{section}"
    assume(re.fullmatch(ecfr._SECTION_SELECTOR_PATTERN, selector))
    bare = re.sub(r"^§\s*", "", n_attr.strip())

    def select():
        structure = ecfr._scoped_structure_from_part_xml(
            xml, title=title, part=part, only_sections=(selector,)
        )
        return build_ecfr_inventory_from_structures(
            (structure,), only_part=part, only_sections=(selector,)
        ).items

    if cited == part or re.fullmatch(ALNUM_SECTION_IDENTIFIER, bare):
        items = select()
        assert items[-1].citation_path == path
        assert items[-1].metadata.get("enclosing_part") == (part if cited != part else None)
    else:
        with pytest.raises(ValueError, match="not found"):
            select()


# N values of one retained part: sections of parts 3800 and 3809 as published, with a
# leading section sign or spaces, forms that fold to one path, and identifiers that only
# the XML search reads ("19-3809.1" holds "3809.1").
_RETAINED_N = [
    "3809.1", "§ 3809.1", " 3809.1 ", "3809.1(a)", "3809.1-a", "19-3809.1", "19-3809.1-a",
    "3800.5", "19-3800.5", "3809. 1", "241.1",
]


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    part=st.sampled_from(["3800", "3809"]),
    n_attrs=st.lists(st.sampled_from(_RETAINED_N), min_size=1, max_size=5),
    data=st.data(),
)
def test_property_retained_extraction_writes_the_one_element_that_claims_the_path(
    part, n_attrs, data
):
    """extract_ecfr on a retained part XML completes exactly when one element claims the
    selected section's path, and then writes that element's body; a section numbered for
    another part is claimed only by the element that publishes the selector.

    The production selection helper supplies selectors and expected claimants here;
    this property checks extraction, duplicate rejection, and writes against that
    selection, rather than independently verifying the helper's parsing grammar.
    """
    import tempfile

    xml = (f'<ECFR><DIV5 N="{part}" TYPE="PART"><HEAD>PART {part}</HEAD>' + "".join(
        f'<DIV8 N="{n_attr}" TYPE="SECTION" NODE="n{index}"><HEAD>Heading</HEAD>'
        f"<P>Body {index}.</P></DIV8>"
        for index, n_attr in enumerate(n_attrs)
    ) + "</DIV5></ECFR>")
    readings = [
        ecfr._selectable_section_from_element(43, elem, part)
        for elem in ET.fromstring(xml).iter("DIV8")
    ]
    selectors = sorted({f"{reading[1]}.{reading[2]}" for reading in readings if reading})
    assume(selectors)
    selector = data.draw(st.sampled_from(selectors))
    path = next(r[0] for r in readings if r and f"{r[1]}.{r[2]}" == selector)
    claimants = [index for index, reading in enumerate(readings) if reading and reading[0] == path]
    if not selector.startswith(f"{part}."):
        # Numbered for another part: only elements that publish the selector's path
        # whole claim it, never one the XML search alone reads.
        assert all(
            re.fullmatch(ALNUM_SECTION_IDENTIFIER, re.sub(r"^§\s*", "", n_attrs[index].strip()))
            for index in claimants
        )

    with tempfile.TemporaryDirectory() as tmp:
        source_xml = Path(tmp) / "official.xml"
        source_xml.write_text(xml)
        store = CorpusArtifactStore(Path(tmp) / "corpus")
        try:
            report = extract_ecfr(
                store, version="2026-10-12", as_of="2026-10-08", source_xml=source_xml,
                only_title=43, only_part=part, only_sections=(selector,), workers=1,
            )
        except ValueError as exc:
            assert len(claimants) > 1
            assert (
                "names more than one section in retained XML" in str(exc)
                or "twice" in str(exc)
            )
            assert not store.root.exists() or not any(p.is_file() for p in store.root.rglob("*"))
            return
        sections = [r for r in load_provisions(report.provisions_path) if r.kind == "section"]

    assert len(claimants) == 1
    assert report.coverage.complete and not report.title_errors
    assert [(r.citation_path, r.body, r.source_id) for r in sections] == [
        (path, f"Body {claimants[0]}.", f"n{claimants[0]}")
    ]
