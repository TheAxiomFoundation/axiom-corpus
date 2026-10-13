"""Subchapter appendices ("Appendix to Subchapter D", 41 CFR chapter 101).

The eCFR places an appendix to a subchapter in that subchapter's last part: 41 CFR
chapter 101's "Appendix to Subchapter D" is in part 101-21, at reader path
.../subchapter-D/part-101-21/appendix-Appendix%20to%20Subchapter%20D. On 2026-10-08 it
is the only live one in all 49 titles; three more in title 41 are reserved.

Invariants checked here:

- Identity: its citation path is ``us/regulation/<title>/<part>/appendix-to-subchapter-<s>``
  (subchapter lowercased), under the part that holds it, at level 1, with legal
  identifier "<title> CFR chapter <c>, subchapter <S>, appendix". Its segment never
  equals a part appendix's (``appendix``, ``appendix-<d>``, ``appendixes``).
- Confirmation: it is read only inside the subchapter it names; one that names
  another subchapter fails closed (``EcfrAppendixError``) in the inventory and, when
  selected, in the XML pass, and ``extract_ecfr`` writes nothing.
- Agreement: inventory and XML records name the same rows, and a structure-only
  placeholder carries the identity of the XML record it stands in for.
- Scope: it is read only with ``include_appendices``; a section selector, the default
  scope, or an allowlist without it never reads it.
"""

import json
import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.ecfr import (
    EcfrAppendixError,
    build_ecfr_inventory_from_structures,
    extract_ecfr,
    iter_ecfr_title_provisions,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory

SCHEMA = json.loads((Path(__file__).parents[1] / "schema/citation-path.v1.json").read_text())
CITATION_PATH = re.compile(SCHEMA["$defs"]["citation_path"]["pattern"])
WELL_FORMED_SEGMENT = re.compile(SCHEMA["$defs"]["hierarchy_segment"]["well_formed_pattern"])
PNG = b"\x89PNG\r\n\x1a\nsubchapter-appendix"


def _appendix_node(identifier, *, reserved=False):
    label = f"{identifier} [Reserved]" if reserved else f"{identifier}—Temporary Regulations"
    return {"identifier": identifier, "label": label, "type": "appendix", "reserved": reserved}


def _div9(identifier, *, image=False):
    img = '<P><img src="/graphics/ec01ja26.002.gif"/></P>' if image else ""
    return (
        f'<DIV9 N="{identifier}" TYPE="APPENDIX" NODE="5:{identifier}">'
        f"<HEAD>{identifier}—Temporary Regulations</HEAD>"
        f"<P>Text of {identifier}.</P>{img}<CITA>[67 FR 76883, Dec. 13, 2002]</CITA></DIV9>"
    )


def _fixture(subchapters, *, title=5, chapter="XIV", group=False, image=False):
    """A title with one chapter and ``subchapters`` = [(subchapter, [(part, appendices)])].

    Each part has one section; ``appendices`` are identifiers placed after it (inside a
    subject group when ``group``), in structure and XML alike.
    """
    structure_subchapters, xml_parts = [], []
    for subchapter, parts in subchapters:
        structure_parts = []
        for part, appendices in parts:
            nodes = [_appendix_node(identifier) for identifier in appendices]
            divs = "".join(_div9(identifier, image=image) for identifier in appendices)
            if group:
                nodes = [{"identifier": f"ECFR{part}g", "type": "subject_group", "children": nodes}]
                divs = f'<DIV7 TYPE="SUBJGRP"><HEAD>Appendix</HEAD>{divs}</DIV7>'
            structure_parts.append({
                "identifier": part, "label": f"Part {part}—Heading", "type": "part",
                "children": [
                    {"identifier": f"{part}.1", "label": f"§ {part}.1 Scope.",
                     "label_description": "Scope.", "type": "section"},
                    *nodes,
                ],
            })
            xml_parts.append(
                f'<DIV5 N="{part}" TYPE="PART"><HEAD>PART {part}—HEADING</HEAD>'
                f'<DIV8 N="{part}.1" TYPE="SECTION"><HEAD>§ {part}.1 Scope.</HEAD><P>Scope.</P></DIV8>'
                f"{divs}</DIV5>"
            )
        structure_subchapters.append({
            "identifier": subchapter, "label": f"Subchapter {subchapter}—Heading",
            "type": "subchapter", "children": structure_parts,
        })
    structure = {
        "identifier": str(title), "label": f"Title {title}", "type": "title",
        "children": [{"identifier": chapter, "label": f"Chapter {chapter}", "type": "chapter",
                      "children": structure_subchapters}],
    }
    return structure, "<ECFR>" + "".join(xml_parts) + "</ECFR>"


STRUCTURE, XML = _fixture([
    ("A", [("2410", [])]),
    ("D", [("2470", []), ("2471", ["Appendix to Subchapter D"])]),
])
APPENDIX = "us/regulation/5/2471/appendix-to-subchapter-d"


def _records(xml, structure, *, allowed=None, include_appendices=True):
    return tuple(iter_ecfr_title_provisions(
        xml, ecfr.part_targets_from_structure(structure), version="v", source_path="s.xml",
        source_as_of="2026-10-08", expression_date="2026-10-08",
        allowed_citation_paths=allowed, include_appendices=include_appendices,
    ))


def _identity(record):
    return (
        record.id, record.citation_path, record.citation_label, record.heading,
        record.parent_citation_path, record.parent_id, record.level, record.ordinal,
        record.kind, record.legal_identifier, record.identifiers, record.source_url,
    )


@pytest.mark.parametrize(
    ("identifier", "part", "segment", "subchapter"),
    [
        ("Appendix to Subchapter D", "101-21", "appendix-to-subchapter-d", "D"),
        ("appendix  to  subchapter  B", "2471", "appendix-to-subchapter-b", "B"),
        (" Appendix to Subchapter XIV ", "1", "appendix-to-subchapter-xiv", "XIV"),
    ],
)
def test_subchapter_appendix_identifier_parses(identifier, part, segment, subchapter):
    appendix = ecfr._subchapter_appendix_from_identifier(identifier, part=part)
    assert appendix.segment == segment
    assert appendix.subchapter == subchapter
    assert appendix.citation_path(41) == f"us/regulation/41/{part}/{segment}"
    assert appendix.legal_identifier(41, "101") == f"41 CFR chapter 101, subchapter {subchapter}, appendix"


@pytest.mark.parametrize(
    "identifier",
    [
        "Appendix A to Subchapter D",  # designated: none live, stays unsupported
        "Appendix to Subchapter G - Temporary Regulations",  # reserved shape
        "Appendixes to Subchapter D",
        "Appendix to Subchapter",
        "Appendix to Subchapter D of Part 101-21",
        "Appendix to Subchapter K",  # Kelvin sign: ASCII-only
        "Appendix to Part 101-21",
    ],
)
def test_subchapter_appendix_identifier_rejects_other_shapes(identifier):
    assert ecfr._subchapter_appendix_from_identifier(identifier, part="101-21") is None


def test_subchapter_appendix_needs_a_part():
    assert ecfr._subchapter_appendix_from_identifier("Appendix to Subchapter D", part=None) is None


def test_inventory_takes_a_subchapter_appendix_under_the_part_that_holds_it():
    items = build_ecfr_inventory_from_structures(
        (STRUCTURE,), only_part="2471", include_appendices=True
    ).items
    assert [item.citation_path for item in items] == [
        "us/regulation/5/2471", "us/regulation/5/2471/1", APPENDIX,
    ]
    appendix = items[-1]
    assert appendix.source_url == (
        "https://www.ecfr.gov/current/title-5/chapter-XIV/subchapter-D/part-2471/"
        "appendix-Appendix%20to%20Subchapter%20D"
    )
    assert appendix.metadata == {
        "kind": "appendix",
        "title": 5,
        "part": "2471",
        "appendix": None,
        "appendix_identifier": "Appendix to Subchapter D",
        "appendix_numbering": None,
        "appendix_subchapter": "D",
        "chapter": "XIV",
        "subchapter": "D",
        "parent_citation_path": "us/regulation/5/2471",
        "label": "Appendix to Subchapter D—Temporary Regulations",
        "label_description": None,
        "heading": "Temporary Regulations",
        "received_on": None,
    }
    placeholder = ecfr._structure_only_provision(appendix, "v", "2026-10-08", "2026-10-08")
    assert placeholder.legal_identifier == "5 CFR chapter XIV, subchapter D, appendix"
    assert placeholder.heading == "Temporary Regulations"
    assert placeholder.level == 1
    assert placeholder.ordinal == 1_000_000
    assert placeholder.parent_citation_path == "us/regulation/5/2471"
    assert placeholder.identifiers == {
        "ecfr:title": "5", "ecfr:part": "2471", "ecfr:subchapter": "D",
    }
    whole = build_ecfr_inventory_from_structures((STRUCTURE,), include_appendices=True).items
    assert [item.citation_path for item in whole].count(APPENDIX) == 1


@pytest.mark.parametrize("group", [False, True])
def test_xml_records_agree_with_inventory_and_placeholders(group):
    structure, xml = _fixture([("D", [("2471", ["Appendix to Subchapter D"])])], group=group)
    items = build_ecfr_inventory_from_structures((structure,), include_appendices=True).items
    records = _records(xml, structure, allowed={item.citation_path for item in items})
    assert [record.citation_path for record in records] == [item.citation_path for item in items]
    appendix = records[-1]
    assert appendix.citation_label == "5 CFR chapter XIV, subchapter D, appendix"
    assert appendix.body == "Text of Appendix to Subchapter D."
    assert appendix.source_id == "5:Appendix to Subchapter D"
    placeholder = ecfr._structure_only_provision(items[-1], "v", "2026-10-08", "2026-10-08")
    assert _identity(placeholder) == _identity(appendix)
    # Free iteration (no allowlist) reads it the same way.
    assert _identity(_records(xml, structure)[-1]) == _identity(appendix)


def test_subchapter_appendix_beside_a_part_appendix_keeps_its_own_path():
    structure, xml = _fixture(
        [("D", [("2471", ["Appendix to Part 2471", "Appendix A to Part 2471", "Appendix to Subchapter D"])])]
    )
    items = build_ecfr_inventory_from_structures((structure,), include_appendices=True).items
    paths = [item.citation_path for item in items]
    assert paths == [
        "us/regulation/5/2471",
        "us/regulation/5/2471/1",
        "us/regulation/5/2471/appendix",
        "us/regulation/5/2471/appendix-a",
        "us/regulation/5/2471/appendix-to-subchapter-d",
    ]
    records = _records(xml, structure, allowed=set(paths))
    assert [record.citation_path for record in records] == paths


def test_subchapter_appendix_naming_another_subchapter_fails_closed(tmp_path, monkeypatch):
    structure, xml = _fixture([("E", [("2471", ["Appendix to Subchapter D"])])])
    with pytest.raises(EcfrAppendixError, match="subchapter 'D' conflicts with enclosing subchapter 'E'"):
        build_ecfr_inventory_from_structures((structure,), include_appendices=True)
    for allowed in (None, {"us/regulation/5/2471/appendix-to-subchapter-d"}):
        with pytest.raises(EcfrAppendixError, match="conflicts with enclosing subchapter 'E'"):
            _records(xml, structure, allowed=allowed)
    # Outside the scope, it is never read.
    assert [record.citation_path for record in _records(xml, structure, allowed={"us/regulation/5/2471/1"})] == [
        "us/regulation/5/2471/1"
    ]
    assert build_ecfr_inventory_from_structures(
        (structure,), only_sections=("2471.1",), include_appendices=True
    ).items
    assert build_ecfr_inventory_from_structures((structure,)).items

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: pytest.fail("invalid inventory fetched XML"))
    store = CorpusArtifactStore(tmp_path / "corpus")
    with pytest.raises(EcfrAppendixError, match="conflicts with enclosing subchapter"):
        extract_ecfr(store, version="2026-10-12", as_of="2026-10-08", only_title=5,
                     only_part="2471", include_appendices=True)
    assert not store.root.exists()


def test_subchapter_appendix_without_a_subchapter_fails_closed():
    structure, _xml = _fixture([("D", [("2471", ["Appendix to Subchapter D"])])])
    chapter = structure["children"][0]
    chapter["children"] = chapter["children"][0]["children"]  # parts directly under the chapter
    with pytest.raises(EcfrAppendixError, match="enclosing subchapter None"):
        build_ecfr_inventory_from_structures((structure,), include_appendices=True)


def test_reserved_and_unopted_subchapter_appendices_are_not_read():
    structure, xml = _fixture([("D", [("2471", [])])])
    part = structure["children"][0]["children"][0]["children"][0]
    part["children"].append(_appendix_node("Appendix to Subchapter D - Temporary Regulations", reserved=True))
    assert [item.citation_path for item in build_ecfr_inventory_from_structures(
        (structure,), include_appendices=True
    ).items] == ["us/regulation/5/2471", "us/regulation/5/2471/1"]
    assert [item.citation_path for item in build_ecfr_inventory_from_structures(
        (STRUCTURE,), only_part="2471"
    ).items] == ["us/regulation/5/2471", "us/regulation/5/2471/1"]
    assert APPENDIX not in {record.citation_path for record in _records(XML, STRUCTURE, include_appendices=False)}


def test_extract_ecfr_takes_a_subchapter_appendix_with_its_image(tmp_path, monkeypatch):
    structure, xml = _fixture([("D", [("2471", ["Appendix to Subchapter D"])])], image=True)
    fetched = []

    def fetch_graphic(identifier):
        fetched.append(identifier)
        return PNG

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch_graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ecfr(store, version="2026-10-12", as_of="2026-10-08", only_title=5,
                          only_part="2471", include_appendices=True)

    assert report.title_errors == ()
    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    paths = ["us/regulation/5/2471", "us/regulation/5/2471/1", APPENDIX]
    assert [record.citation_path for record in records] == paths
    assert [item.citation_path for item in load_source_inventory(report.inventory_path)] == paths
    assert not any(record.metadata.get("structure_only") for record in records)
    assert records[-1].body == (
        "Text of Appendix to Subchapter D.\n\n"
        "[Official source image: ecfr/graphics/EC01JA26.002.png]"
    )
    # The image's appendix resolves to its citation through the part that holds it.
    assert fetched == ["EC01JA26.002"]


def test_title_41_part_101_21_shape():
    # 41 CFR chapter 101, subchapter D, part 101-21 (2026-10-08), with its one section.
    structure = {
        "identifier": "41", "label": "Title 41", "type": "title",
        "children": [{"identifier": "101", "label": "Chapter 101", "type": "chapter", "children": [{
            "identifier": "D", "label": "Subchapter D—Public Buildings and Space", "type": "subchapter",
            "children": [{
                "identifier": "101-21", "label": "Part 101-21—Federal Buildings Fund", "type": "part",
                "children": [
                    {"identifier": "101-21.000", "label": "§ 101-21.000 Cross-reference.",
                     "type": "section"},
                    {"identifier": "Appendix to Subchapter D",
                     "label": "Appendix to Subchapter D—Temporary Regulations Federal Property "
                              "Management Regulations; Interim Rule D-1\n",
                     "type": "appendix"},
                ],
            }],
        }]}],
    }
    xml = (
        '<ECFR><DIV5 N="101-21" TYPE="PART"><HEAD>PART 101-21—FEDERAL BUILDINGS FUND</HEAD>'
        '<DIV8 N="101-21.000" TYPE="SECTION"><HEAD>§ 101-21.000 Cross-reference.</HEAD><P>See.</P></DIV8>'
        '<DIV9 N="Appendix to Subchapter D" TYPE="APPENDIX">'
        "<HEAD>Appendix to Subchapter D—Temporary Regulations Federal Property Management "
        "Regulations; Interim Rule D-1\n</HEAD>"
        "<HD3><B>PART 101-17—ASSIGNMENT AND UTILIZATION OF SPACE</B></HD3>"
        "<P>For information on location of space, <I>see</I> FMR part 102-83.</P>"
        "</DIV9></DIV5></ECFR>"
    )
    items = build_ecfr_inventory_from_structures(
        (structure,), only_part="101-21", include_appendices=True
    ).items
    appendix = next(item for item in items if item.metadata["kind"] == "appendix")
    assert appendix.citation_path == "us/regulation/41/101-21/appendix-to-subchapter-d"
    records = {r.citation_path: r for r in _records(xml, structure, allowed={i.citation_path for i in items})}
    record = records[appendix.citation_path]
    assert record.legal_identifier == "41 CFR chapter 101, subchapter D, appendix"
    assert record.heading == (
        "Temporary Regulations Federal Property Management Regulations; Interim Rule D-1"
    )
    assert record.body.startswith("PART 101-17—ASSIGNMENT AND UTILIZATION OF SPACE")
    placeholder = ecfr._structure_only_provision(appendix, "v", "2026-10-08", "2026-10-08")
    assert _identity(placeholder) == _identity(record)


_LETTERS = st.lists(st.sampled_from("ABCDEFGHIJKLMNXVabd0123456789"), min_size=1, max_size=4).map("".join)


@settings(max_examples=150, deadline=None)
@given(
    subchapter=_LETTERS,
    others=st.lists(st.sampled_from(["Appendix to Part {p}", "Appendix A to Part {p}", "Appendix 1 to Part {p}"]),
                    max_size=3, unique=True),
    group=st.booleans(),
    last=st.booleans(),
)
def test_property_subchapter_appendix_identity_and_agreement(subchapter, others, group, last):
    part = "2471"
    appendices = [other.format(p=part) for other in others]
    appendices.insert(len(appendices) if last else 0, f"Appendix to Subchapter {subchapter}")
    structure, xml = _fixture([(subchapter, [("2470", []), (part, appendices)])], group=group)

    items = build_ecfr_inventory_from_structures((structure,), include_appendices=True).items
    paths = [item.citation_path for item in items]
    path = f"us/regulation/5/{part}/appendix-to-subchapter-{subchapter.lower()}"
    assert paths.count(path) == 1
    assert len(set(paths)) == len(paths)
    assert CITATION_PATH.fullmatch(path)
    assert all(WELL_FORMED_SEGMENT.fullmatch(segment) for segment in path.split("/")[2:])

    records = _records(xml, structure, allowed=set(paths))
    assert [record.citation_path for record in records] == paths
    by_path = {record.citation_path: record for record in records}
    for item in items:
        if item.metadata["kind"] == "appendix":
            placeholder = ecfr._structure_only_provision(item, "v", "2026-10-08", "2026-10-08")
            assert _identity(placeholder) == _identity(by_path[item.citation_path])
    assert by_path[path].parent_citation_path == f"us/regulation/5/{part}"
    assert by_path[path].legal_identifier == f"5 CFR chapter XIV, subchapter {subchapter}, appendix"
