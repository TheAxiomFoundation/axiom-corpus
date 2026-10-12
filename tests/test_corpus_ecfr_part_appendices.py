"""Part appendices beyond one letter or number ("Appendix II to Part 200", "Appendix to Part 720").

Invariants checked here:

- Identity: a part appendix's citation path is ``us/regulation/<title>/<part>/<segment>``
  with segment ``appendix-<d>`` (designator lowercased), ``appendix`` (unnumbered) or
  ``appendixes``/``appendices`` (the collective note). Its parent is the part, at
  level 1, wherever it sits in the part: directly, in a subject group, or in a subpart.
- Order: when a part's lettered designators are all roman numerals and one has more
  than one character, they sort by value; otherwise letters sort by ``ord`` and
  numbers by value. An unnumbered or collective appendix leads. Classification
  ignores input order and placement depth.
- Legacy: any set of numbers and single letters keeps the path, ordinal, legal
  identifier, identifiers and exact metadata the adapter gave it before roman and
  unnumbered part appendices were taken; such metadata has no ``appendix_numbering``.
  Intended exception: a live single letter (I, V, X, L, C, D, M) in a part that also
  lists a reserved multi-character numeral reads as a numeral. No eCFR part has that
  shape (all title structures as of 2026-10-08).
- Agreement: the structure inventory and the XML records name the same rows, and a
  structure-only placeholder carries the identity of the XML record it stands in for.
- Fail closed: an opted-in part appendix that names another part, has a designator
  with no unambiguous order, or still has an unsupported shape raises
  ``EcfrAppendixError``, and ``extract_ecfr`` writes nothing. An appendix placed in
  another part never changes the numbering of the part it names.
"""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.ecfr import (
    EcfrAppendixError,
    EcfrPartTarget,
    build_ecfr_inventory_from_structures,
    extract_ecfr,
    iter_ecfr_title_provisions,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id

PNG = b"\x89PNG\r\n\x1a\nunified-guidance-form"
PLACEMENTS = ("part", "group", "subpart", "subpart-group")


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


def _part_fixture(part, appendices, *, title=2, body=None):
    """One part's structure node and XML, with appendices at the given placements.

    ``appendices`` is a list of ``(identifier, placement, reserved)``. Both renderings
    use one layout, so source order agrees: a section, the part-level appendices, a
    part-level subject group, then subpart A with a section, its appendices and a
    subject group of its own.
    """
    body = body or (lambda identifier: f"<P>Text of {identifier}.</P>")

    def node(identifier, reserved):
        label = f"{identifier} [Reserved]" if reserved else f"{identifier}—Heading of {identifier}"
        return {"identifier": identifier, "label": label, "type": "appendix", "reserved": reserved}

    def div9(identifier, reserved):
        if reserved:
            return f'<DIV9 N="{identifier}" TYPE="APPENDIX"><HEAD>{identifier} [Reserved]</HEAD></DIV9>'
        return (
            f'<DIV9 N="{identifier}" TYPE="APPENDIX" NODE="{title}:{identifier}">'
            f"<HEAD>{identifier}—Heading of {identifier}</HEAD>{body(identifier)}"
            "<CITA>[89 FR 30136, Apr. 22, 2024]</CITA></DIV9>"
        )

    at = {placement: [a for a in appendices if a[1] == placement] for placement in PLACEMENTS}
    structure_part = {
        "identifier": part, "label": f"Part {part}-Synthetic Part", "type": "part",
        "children": [
            {"identifier": f"{part}.1", "label": f"§ {part}.1 Purpose.",
             "label_description": "Purpose.", "type": "section"},
            *(node(identifier, reserved) for identifier, _, reserved in at["part"]),
            {"identifier": f"ECFR{part}g", "type": "subject_group",
             "children": [node(identifier, reserved) for identifier, _, reserved in at["group"]]},
            {"identifier": "A", "label": "Subpart A-General", "type": "subpart", "children": [
                {"identifier": f"{part}.10", "label": f"§ {part}.10 Scope.",
                 "label_description": "Scope.", "type": "section"},
                *(node(identifier, reserved) for identifier, _, reserved in at["subpart"]),
                {"identifier": f"ECFR{part}s", "type": "subject_group",
                 "children": [node(i, r) for i, _, r in at["subpart-group"]]},
            ]},
        ],
    }
    xml_part = (
        f'<DIV5 N="{part}" TYPE="PART"><HEAD>PART {part}—SYNTHETIC PART</HEAD>'
        f'<DIV8 N="§ {part}.1" TYPE="SECTION"><HEAD>§ {part}.1 Purpose.</HEAD><P>Purpose text.</P></DIV8>'
        + "".join(div9(identifier, reserved) for identifier, _, reserved in at["part"])
        + '<DIV7 TYPE="SUBJGRP"><HEAD>Appendices</HEAD>'
        + "".join(div9(identifier, reserved) for identifier, _, reserved in at["group"])
        + "</DIV7>"
        + '<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A—General</HEAD>'
        + f'<DIV8 N="§ {part}.10" TYPE="SECTION"><HEAD>§ {part}.10 Scope.</HEAD><P>Scope text.</P></DIV8>'
        + "".join(div9(identifier, reserved) for identifier, _, reserved in at["subpart"])
        + '<DIV7 TYPE="SUBJGRP"><HEAD>Forms</HEAD>'
        + "".join(div9(identifier, reserved) for identifier, _, reserved in at["subpart-group"])
        + "</DIV7></DIV6></DIV5>"
    )
    return structure_part, xml_part


def _title(parts, *, title=2, chapter="II"):
    structure = {
        "identifier": str(title), "label": f"Title {title}", "type": "title",
        "children": [{"identifier": chapter, "label": f"Chapter {chapter}", "type": "chapter",
                      "children": [structure_part for structure_part, _ in parts]}],
    }
    xml = "<ECFR>" + "".join(xml_part for _, xml_part in parts) + "</ECFR>"
    return structure, xml


def _targets(structure, part):
    return tuple(t for t in ecfr.part_targets_from_structure(structure) if t.part == part)


def _inventory(structure, part, **kwargs):
    return build_ecfr_inventory_from_structures(
        (structure,), only_part=part, include_appendices=True, **kwargs
    ).items


def _records(xml, structure, part, **kwargs):
    return tuple(iter_ecfr_title_provisions(
        xml, _targets(structure, part), version="v", source_path="s.xml",
        source_as_of="2026-10-08", expression_date="2026-10-08", include_appendices=True,
        **kwargs,
    ))


def _identity(record):
    return (
        record.id, record.citation_path, record.citation_label, record.heading,
        record.parent_citation_path, record.parent_id, record.level, record.ordinal,
        record.kind, record.legal_identifier, record.identifiers, record.source_url,
    )


# The Uniform Guidance shape: roman numerals I-XII, one placed in a subpart and one
# reserved, beside an unnumbered appendix in another part and a lettered part.
UG_APPENDICES = [
    ("Appendix I to Part 200", "group", False),
    ("Appendix II to Part 200", "group", False),
    ("Appendix III to Part 200", "group", False),
    ("Appendix IV to Part 200", "subpart", False),
    ("Appendix V to Part 200", "group", False),
    ("Appendix VII to Part 200", "group", True),
    ("Appendix IX to Part 200", "group", False),
    ("Appendix XII to Part 200", "part", False),
]
STRUCTURE, XML = _title([
    _part_fixture("200", UG_APPENDICES, body=lambda identifier: (
        '<P>Contract provisions.</P><FP><img src="/graphics/EC01JA91.007.gif"/></FP>'
        if identifier == "Appendix II to Part 200" else f"<P>Text of {identifier}.</P>"
    )),
    _part_fixture("25", [("Appendix A to Part 25", "part", False), ("Appendix I to Part 25", "part", False)]),
    _part_fixture("720", [("Appendix to Part 720", "group", False)]),
])

# (citation path, ordinal, legal identifier, ecfr:appendix, appendix_numbering or absent)
ABSENT = object()
EXPECTED_200 = [
    ("us/regulation/2/200/appendix-i", 1_000_001, "2 CFR part 200, appendix I", "i", "roman"),
    ("us/regulation/2/200/appendix-ii", 1_000_002, "2 CFR part 200, appendix II", "ii", "roman"),
    ("us/regulation/2/200/appendix-iii", 1_000_003, "2 CFR part 200, appendix III", "iii", "roman"),
    ("us/regulation/2/200/appendix-v", 1_000_005, "2 CFR part 200, appendix V", "v", "roman"),
    ("us/regulation/2/200/appendix-ix", 1_000_009, "2 CFR part 200, appendix IX", "ix", "roman"),
    ("us/regulation/2/200/appendix-iv", 1_000_004, "2 CFR part 200, appendix IV", "iv", "roman"),
]
EXPECTED_200_PATHS = [
    "us/regulation/2/200",
    "us/regulation/2/200/1",
    "us/regulation/2/200/appendix-xii",
    "us/regulation/2/200/appendix-i",
    "us/regulation/2/200/appendix-ii",
    "us/regulation/2/200/appendix-iii",
    "us/regulation/2/200/appendix-v",
    "us/regulation/2/200/appendix-ix",
    "us/regulation/2/200/subpart-A",
    "us/regulation/2/200/10",
    "us/regulation/2/200/appendix-iv",
]


@pytest.mark.parametrize(
    "identifier,segment,legal_identifier,appendix",
    [
        ("Appendix II to Part 200", "appendix-ii", "2 CFR part 200, appendix II", "ii"),
        ("Appendix XIII to Part 266", "appendix-xiii", "2 CFR part 266, appendix XIII", "xiii"),
        ("Appendix I to Part 200", "appendix-i", "2 CFR part 200, appendix I", "i"),
        ("Appendix A to Part 604", "appendix-a", "2 CFR part 604, appendix A", "a"),
        ("appendix b to part 604", "appendix-b", "2 CFR part 604, appendix B", "b"),
        ("Appendix 12 to Part 604", "appendix-12", "2 CFR part 604, appendix 12", "12"),
        ("Appendix to Part 720", "appendix", "2 CFR part 720, appendix", None),
        ("  Appendix to Part 54a ", "appendix", "2 CFR part 54a, appendix", None),
        ("Appendixes to Part 50", "appendixes", "2 CFR part 50, appendixes", None),
        ("Appendices to Part 50", "appendices", "2 CFR part 50, appendices", None),
    ],
)
def test_part_appendix_identifier_parses(identifier, segment, legal_identifier, appendix):
    parsed = ecfr._part_appendix_from_identifier(identifier)

    assert parsed is not None
    assert parsed.identifier == identifier
    assert parsed.segment == segment
    assert parsed.appendix == appendix
    assert parsed.citation_path(2) == f"us/regulation/2/{parsed.part}/{segment}"
    assert parsed.part_citation_path(2) == f"us/regulation/2/{parsed.part}"
    assert parsed.legal_identifier(2) == legal_identifier
    # A part appendix is not a subpart appendix.
    assert ecfr._subpart_appendix_from_identifier(identifier) is None


@pytest.mark.parametrize(
    "identifier,loose_segment",
    [
        # Alphanumeric designators parse loosely (so a selected one fails closed)...
        ("Appendix M1 to Part 226", "appendix-m1"),
        ("Appendix AA to Part 604", "appendix-aa"),
        ("Appendix ii to Part 604", "appendix-ii"),
        ("Appendixes A to Part 50", "appendixes"),
        # ...the rest never parse.
        ("Appendix D-1 to Part 208", None),
        ("Appendix I(F) to Part 13", None),
        ("Appendix to Part 60-20", None),
        ("Appendixes L-M to Part 50", None),
        ("Appendix to 19 CFR Part 0", None),
        ("Appendix A to Subpart B of Part 604", None),
        ("Appendix to Subpart B of Part 404", None),
        ("Appendix A to Chapter I", None),
        ("", None),
    ],
)
def test_part_appendix_identifier_rejects_other_shapes(identifier, loose_segment):
    assert ecfr._part_appendix_from_identifier(identifier) is None
    loose = ecfr._part_appendix_from_identifier(identifier, require_supported=False)
    assert (loose.segment if loose else None) == loose_segment


def test_inventory_takes_roman_and_unnumbered_part_appendices():
    items = _inventory(STRUCTURE, "200", run_id="2026-10-12-title-2-part-200")

    assert [item.citation_path for item in items] == EXPECTED_200_PATHS
    by_path = {item.citation_path: item for item in items}
    assert by_path["us/regulation/2/200/appendix-ii"].metadata == {
        "kind": "appendix",
        "title": 2,
        "part": "200",
        "appendix": "ii",
        "appendix_identifier": "Appendix II to Part 200",
        "appendix_numbering": "roman",
        "chapter": "II",
        "subchapter": None,
        "parent_citation_path": "us/regulation/2/200",
        "label": "Appendix II to Part 200—Heading of Appendix II to Part 200",
        "label_description": None,
        "heading": "Heading of Appendix II to Part 200",
        "received_on": None,
    }
    assert by_path["us/regulation/2/200/appendix-ii"].source_url == (
        "https://www.ecfr.gov/current/title-2/chapter-II/part-200/"
        "appendix-Appendix%20II%20to%20Part%20200"
    )
    # Inside subpart A, Appendix IV still belongs to the part.
    assert by_path["us/regulation/2/200/appendix-iv"].metadata["parent_citation_path"] == (
        "us/regulation/2/200"
    )
    assert "subpart" not in by_path["us/regulation/2/200/appendix-iv"].metadata
    # The reserved Appendix VII is not inventoried.
    assert "us/regulation/2/200/appendix-vii" not in by_path

    unnumbered = _inventory(STRUCTURE, "720")
    assert [item.citation_path for item in unnumbered] == [
        "us/regulation/2/720", "us/regulation/2/720/1", "us/regulation/2/720/appendix",
        "us/regulation/2/720/subpart-A", "us/regulation/2/720/10",
    ]
    assert unnumbered[2].metadata["appendix"] is None
    assert unnumbered[2].metadata["appendix_numbering"] is None
    assert unnumbered[2].metadata["heading"] == "Heading of Appendix to Part 720"

    # Default inventories never see appendices.
    default = build_ecfr_inventory_from_structures((STRUCTURE,), only_part="200")
    assert [item.citation_path for item in default.items] == [
        path for path in EXPECTED_200_PATHS if "appendix" not in path
    ]


def test_lettered_part_keeps_its_metadata_shape_beside_roman_parts():
    # Part 25 lists "A" and "I": letters, as before, whatever part 200 does.
    items = {item.citation_path: item for item in _inventory(STRUCTURE, "25")}

    for designator in ("a", "i"):
        metadata = items[f"us/regulation/2/25/appendix-{designator}"].metadata
        assert set(metadata) == {
            "kind", "title", "part", "appendix", "appendix_identifier", "chapter", "subchapter",
            "parent_citation_path", "label", "label_description", "heading", "received_on",
        }
        placeholder = ecfr._structure_only_provision(
            items[f"us/regulation/2/25/appendix-{designator}"], "v", "2026-10-08", "2026-10-08"
        )
        assert placeholder.ordinal == 1_000_000 + ord(designator.upper())


def test_iterator_takes_part_appendices_with_identity_and_order():
    records = _records(XML, STRUCTURE, "200")

    by_path = {record.citation_path: record for record in records}
    for path, ordinal, legal_identifier, appendix, numbering in EXPECTED_200:
        record = by_path[path]
        assert record.kind == "appendix"
        assert record.level == 1
        assert record.parent_citation_path == "us/regulation/2/200"
        assert record.parent_id == by_path["us/regulation/2/200"].id
        assert record.id == deterministic_provision_id(path)
        assert record.ordinal == ordinal
        assert record.legal_identifier == record.citation_label == legal_identifier
        assert record.identifiers == {"ecfr:title": "2", "ecfr:part": "200", "ecfr:appendix": appendix}
        assert record.metadata["appendix_numbering"] == numbering
        assert record.source_as_of == record.expression_date == "2026-10-08"
    assert by_path["us/regulation/2/200/appendix-ii"].body.split("\n\n") == [
        "Contract provisions.",
        "[Official source image: ecfr/graphics/EC01JA91.007.png]",
    ]
    assert by_path["us/regulation/2/200/appendix-xii"].heading == "Heading of Appendix XII to Part 200"

    unnumbered = {record.citation_path: record for record in _records(XML, STRUCTURE, "720")}
    record = unnumbered["us/regulation/2/720/appendix"]
    assert (record.ordinal, record.level, record.parent_citation_path) == (1_000_000, 1, "us/regulation/2/720")
    assert record.legal_identifier == record.citation_label == "2 CFR part 720, appendix"
    assert record.identifiers == {"ecfr:title": "2", "ecfr:part": "720"}
    assert record.metadata == {
        "title": 2, "part": "720", "appendix": None, "appendix_identifier": "Appendix to Part 720",
        "appendix_numbering": None, "chapter": "II", "subchapter": None,
    }
    assert record.body == "Text of Appendix to Part 720."

    # Default iteration never converts appendices.
    assert all(
        record.kind != "appendix"
        for record in iter_ecfr_title_provisions(
            XML, _targets(STRUCTURE, "200"), version="v", source_path="s.xml"
        )
    )


def test_part_children_sort_by_numeral_after_sections_and_subparts():
    # Appendices sort after the part's sections and subparts, by numeral value.
    records = _records(XML, STRUCTURE, "200", allowed_citation_paths=set(EXPECTED_200_PATHS))
    children = sorted(
        (record for record in records if record.parent_citation_path == "us/regulation/2/200"),
        key=lambda record: (record.ordinal or 0, record.citation_path),
    )
    assert [record.citation_path.rsplit("/", 1)[1] for record in children] == [
        "1", "subpart-A", "appendix-i", "appendix-ii", "appendix-iii", "appendix-iv",
        "appendix-v", "appendix-ix", "appendix-xii",
    ]


@pytest.mark.parametrize(
    "allowed,expected",
    [
        ({"us/regulation/2/200/appendix-ii"}, ["us/regulation/2/200/appendix-ii"]),
        ({"us/regulation/2/200/appendix-iv"}, ["us/regulation/2/200/appendix-iv"]),
        ({"us/regulation/2/200/1"}, ["us/regulation/2/200/1"]),
        (set(), []),
    ],
)
def test_iterator_allowlist_selects_part_appendices(allowed, expected):
    assert [record.citation_path for record in _records(XML, STRUCTURE, "200", allowed_citation_paths=allowed)] == expected


def test_iterator_allowlist_selects_unnumbered_part_appendix():
    records = _records(XML, STRUCTURE, "720", allowed_citation_paths={"us/regulation/2/720/appendix"})
    assert [record.citation_path for record in records] == ["us/regulation/2/720/appendix"]


# Legacy oracle: what the adapter produced for numbers and single letters before this
# change, written out independently of the code under test.
def _legacy_ordinal(designator):
    return 1_000_000 + (int(designator) if designator.isdigit() else ord(designator.upper()))


def _legacy_inventory_metadata(identifier, designator, part="604", title=45, chapter="VI"):
    label = f"{identifier}—Heading of {identifier}"
    return {
        "kind": "appendix", "title": title, "part": part, "appendix": designator.lower(),
        "appendix_identifier": identifier, "chapter": chapter, "subchapter": None,
        "parent_citation_path": f"us/regulation/{title}/{part}", "label": label,
        "label_description": None, "heading": f"Heading of {identifier}", "received_on": None,
    }


_letters = st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_legacy_designators = st.lists(
    st.one_of(
        st.integers(min_value=0, max_value=60).map(str),
        st.tuples(_letters, st.booleans()).map(lambda pair: pair[0] if pair[1] else pair[0].lower()),
    ),
    min_size=1, max_size=10, unique_by=lambda designator: designator.upper().lstrip("0") or "0",
)


@settings(max_examples=150, deadline=None)
@given(
    _legacy_designators,
    st.lists(st.sampled_from(PLACEMENTS), min_size=10, max_size=10),
    st.lists(st.booleans(), min_size=10, max_size=10),
    st.randoms(),
)
def test_numbers_and_letters_keep_the_legacy_identity(designators, placements, reserved, rng):
    appendices = [
        (f"Appendix {designator} to Part 604", placements[index], reserved[index] and index > 0)
        for index, designator in enumerate(designators)
    ]
    rng.shuffle(appendices)
    structure, xml = _title([_part_fixture("604", appendices, title=45)], title=45, chapter="VI")

    items = _inventory(structure, "604")
    allowed = {item.citation_path for item in items}
    records = {record.citation_path: record for record in _records(xml, structure, "604", allowed_citation_paths=allowed)}

    live = [(identifier, identifier.split()[1]) for identifier, _, is_reserved in appendices if not is_reserved]
    appendix_items = {item.citation_path: item for item in items if item.metadata["kind"] == "appendix"}
    assert set(appendix_items) == {f"us/regulation/45/604/appendix-{d.lower()}" for _, d in live}
    for identifier, designator in live:
        path = f"us/regulation/45/604/appendix-{designator.lower()}"
        item = appendix_items[path]
        assert item.metadata == _legacy_inventory_metadata(identifier, designator)
        placeholder = ecfr._structure_only_provision(item, "v", "2026-10-08", "2026-10-08")
        record = records[path]
        for provision in (placeholder, record):
            assert provision.ordinal == _legacy_ordinal(designator)
            assert provision.level == 1
            assert provision.parent_citation_path == "us/regulation/45/604"
            assert provision.legal_identifier == f"45 CFR part 604, appendix {designator.upper()}"
            assert provision.identifiers == {
                "ecfr:title": "45", "ecfr:part": "604", "ecfr:appendix": designator.lower(),
            }
        assert record.metadata == {
            "title": 45, "part": "604", "appendix": designator.lower(),
            "appendix_identifier": identifier, "chapter": "VI", "subchapter": None,
        }
        assert record.body == f"Text of {identifier}."


@settings(max_examples=200, deadline=None)
@given(
    st.sets(st.integers(min_value=1, max_value=3999), min_size=1, max_size=12),
    st.sampled_from([None, "Appendix to Part 200", "Appendixes to Part 200"]),
    st.lists(st.sampled_from(PLACEMENTS), min_size=14, max_size=14),
    st.lists(st.booleans(), min_size=14, max_size=14),
    st.randoms(),
)
def test_roman_part_appendices_order_by_value_and_agree_with_placeholders(
    values, lead, placements, reserved, rng
):
    # A multi-character numeral among the part's appendices makes them all numerals.
    values = sorted(values | {2})
    identifiers = ([lead] if lead else []) + [f"Appendix {_to_roman(v)} to Part 200" for v in values]
    appendices = [
        (identifier, placements[index], reserved[index] and identifier != "Appendix II to Part 200")
        for index, identifier in enumerate(identifiers)
    ]
    rng.shuffle(appendices)
    structure, xml = _title([_part_fixture("200", appendices)])

    items = _inventory(structure, "200")
    records = {
        record.citation_path: record
        for record in _records(xml, structure, "200", allowed_citation_paths={item.citation_path for item in items})
    }
    assert [item.citation_path for item in items] == list(records)
    live = [identifier for identifier, _, is_reserved in sorted(appendices, key=lambda a: identifiers.index(a[0]))
            if not is_reserved]
    appendix_records = []
    for item in items:
        if item.metadata["kind"] != "appendix":
            continue
        placeholder = ecfr._structure_only_provision(item, "v", "2026-10-08", "2026-10-08")
        record = records[item.citation_path]
        assert _identity(placeholder) == _identity(record)
        assert record.parent_citation_path == "us/regulation/2/200"
        assert record.level == 1
        appendix_records.append(record)
    ordered = sorted(appendix_records, key=lambda record: (record.ordinal, record.citation_path))
    assert [record.metadata["appendix_identifier"] for record in ordered] == live
    for record in appendix_records:
        designator = record.metadata["appendix"]
        if designator:
            assert record.ordinal == 1_000_000 + ecfr._roman_numeral_value(designator.upper())
            assert record.metadata["appendix_numbering"] == "roman"
        else:
            assert record.ordinal == 1_000_000


@settings(max_examples=100, deadline=None)
@given(
    st.sets(st.integers(min_value=1, max_value=40), min_size=1, max_size=8),
    st.lists(st.sampled_from(PLACEMENTS), min_size=2, max_size=2),
    st.randoms(),
)
def test_numbering_ignores_order_and_placement_depth(values, placements, rng):
    identifiers = [f"Appendix {_to_roman(v)} to Part 200" for v in sorted(values | {3})]
    base = None
    for _ in range(3):
        rng.shuffle(identifiers)
        structure, _xml = _title([_part_fixture("200", [
            (identifier, placements[index % 2], False) for index, identifier in enumerate(identifiers)
        ])])
        numbering = ecfr._appendix_numbering_by_container(ecfr._structure_appendix_placements(structure))
        assert numbering[("200", None)] == dict.fromkeys((_to_roman(v) for v in values | {3}), "roman")
        base = base or numbering
        assert numbering == base


def test_extract_ecfr_takes_part_appendices_with_complete_coverage(tmp_path, monkeypatch):
    fetched = []

    def fetch_graphic(identifier):
        fetched.append(identifier)
        assert identifier == "EC01JA91.007"
        return PNG

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: XML)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch_graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store, version="2026-10-12", as_of="2026-10-08", only_title=2, only_part="200",
        include_appendices=True,
    )

    assert report.title_errors == ()
    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == EXPECTED_200_PATHS
    assert [item.citation_path for item in load_source_inventory(report.inventory_path)] == EXPECTED_200_PATHS
    assert not any(record.metadata.get("structure_only") for record in records)
    # Appendix II's source image is archived: its citation is resolved for graphics too.
    assert fetched == ["EC01JA91.007"]
    graphic = store.root / "sources/us/regulation/2026-10-12-title-2-part-200/ecfr/graphics/EC01JA91.007.png"
    assert graphic.read_bytes() == PNG


def test_extract_ecfr_placeholder_keeps_roman_part_appendix_identity(tmp_path, monkeypatch):
    # The structure lists I, II and III; this XML snapshot has only Appendix I. Its
    # ordinal must still be the numeral's (1), as the structure's numbering says,
    # not the letter I's (73).
    structure, _ = _title([_part_fixture("200", [
        ("Appendix I to Part 200", "group", False),
        ("Appendix II to Part 200", "group", False),
        ("Appendix III to Part 200", "subpart", False),
    ])])
    _, xml = _title([_part_fixture("200", [("Appendix I to Part 200", "group", False)])])
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    kwargs = {"version": "2026-10-12", "as_of": "2026-10-08", "only_title": 2,
              "only_part": "200", "include_appendices": True}

    report = extract_ecfr(CorpusArtifactStore(tmp_path / "missing"), **kwargs)

    assert report.coverage.complete
    by_path = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert by_path["us/regulation/2/200/appendix-i"].ordinal == 1_000_001
    assert by_path["us/regulation/2/200/appendix-i"].body == "Text of Appendix I to Part 200."
    for numeral, value in (("ii", 2), ("iii", 3)):
        placeholder = by_path[f"us/regulation/2/200/appendix-{numeral}"]
        assert placeholder.body is None
        assert placeholder.metadata["structure_only"] is True
        assert (placeholder.parent_citation_path, placeholder.level, placeholder.ordinal) == (
            "us/regulation/2/200", 1, 1_000_000 + value,
        )
        assert placeholder.legal_identifier == f"2 CFR part 200, appendix {numeral.upper()}"

    # A later snapshot that carries every appendix gives the same identities.
    _, full_xml = _title([_part_fixture("200", [
        ("Appendix I to Part 200", "group", False),
        ("Appendix II to Part 200", "group", False),
        ("Appendix III to Part 200", "subpart", False),
    ])])
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: full_xml)
    present = {
        record.citation_path: record
        for record in load_provisions(extract_ecfr(CorpusArtifactStore(tmp_path / "present"), **kwargs).provisions_path)
    }
    for numeral in ("i", "ii", "iii"):
        path = f"us/regulation/2/200/appendix-{numeral}"
        assert _identity(present[path])[:-1] == _identity(by_path[path])[:-1]


def test_extract_ecfr_placeholder_keeps_unnumbered_part_appendix_identity(tmp_path, monkeypatch):
    structure, _ = _title([_part_fixture("720", [("Appendix to Part 720", "group", False)])])
    _, xml = _title([_part_fixture("720", [])])
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)

    report = extract_ecfr(
        CorpusArtifactStore(tmp_path / "corpus"), version="2026-10-12", as_of="2026-10-08",
        only_title=2, only_part="720", include_appendices=True,
    )

    placeholder = {record.citation_path: record for record in load_provisions(report.provisions_path)}[
        "us/regulation/2/720/appendix"
    ]
    assert placeholder.body is None
    assert (placeholder.ordinal, placeholder.level, placeholder.parent_citation_path) == (
        1_000_000, 1, "us/regulation/2/720",
    )
    assert placeholder.legal_identifier == placeholder.citation_label == "2 CFR part 720, appendix"
    assert placeholder.identifiers == {"ecfr:title": "2", "ecfr:part": "720"}
    assert placeholder.heading == "Heading of Appendix to Part 720"


AMBIGUOUS = "designator order is ambiguous among its part's appendices"
CONFLICT = "appendix part '605' conflicts with enclosing part '604'"
UNSUPPORTED = "unsupported nonreserved eCFR appendix identifier"
UNSUPPORTED_XML = "unsupported nonreserved eCFR appendix XML identifier"


@pytest.mark.parametrize(
    "appendices,identifier,error,xml_error",
    [
        # "II" or "CC" beside a letter has no unambiguous order.
        ([("Appendix A to Part 604", "part", False), ("Appendix II to Part 604", "group", False)],
         "Appendix II to Part 604", AMBIGUOUS, AMBIGUOUS),
        ([("Appendix B to Part 604", "subpart", False), ("Appendix CC to Part 604", "part", False)],
         "Appendix CC to Part 604", AMBIGUOUS, AMBIGUOUS),
        # A roman or unnumbered part appendix that names another part.
        ([("Appendix II to Part 605", "subpart", False)], "Appendix II to Part 605", CONFLICT, CONFLICT),
        ([("Appendix to Part 605", "group", False)], "Appendix to Part 605", CONFLICT, CONFLICT),
        # Shapes that stay unsupported.
        ([("Appendix M1 to Part 604", "part", False)], "Appendix M1 to Part 604", UNSUPPORTED, UNSUPPORTED_XML),
        ([("Appendix ii to Part 604", "part", False)], "Appendix ii to Part 604", UNSUPPORTED, UNSUPPORTED_XML),
        ([("Appendixes A to Part 604", "part", False)], "Appendixes A to Part 604", UNSUPPORTED, UNSUPPORTED_XML),
        ([("Appendix D-1 to Part 604", "subpart", False)], "Appendix D-1 to Part 604", UNSUPPORTED, UNSUPPORTED_XML),
    ],
)
def test_part_appendix_fails_closed_in_inventory_iterator_and_extract(
    tmp_path, monkeypatch, appendices, identifier, error, xml_error
):
    structure, xml = _title([_part_fixture("604", appendices, title=45)], title=45, chapter="VI")

    with pytest.raises(EcfrAppendixError, match=error):
        _inventory(structure, "604")
    # The iterator fails closed when the appendix is in scope: everything, its parsed
    # citation, or the citation it would take in its enclosing part.
    loose = ecfr._part_appendix_from_identifier(identifier, require_supported=False)
    selections = [None]
    if loose is not None:
        selections += [{loose.citation_path(45)}, {f"us/regulation/45/604/{loose.segment}"}]
    for allowed in selections:
        with pytest.raises(EcfrAppendixError, match=xml_error):
            _records(xml, structure, "604", allowed_citation_paths=allowed)
    # Excluded by an allowlist, a section selector, or the default scope, it is never read.
    assert [
        record.citation_path
        for record in _records(xml, structure, "604", allowed_citation_paths={"us/regulation/45/604/1"})
    ] == ["us/regulation/45/604/1"]
    assert build_ecfr_inventory_from_structures(
        (structure,), only_part="604", only_sections=("604.1",), include_appendices=True
    ).items
    assert build_ecfr_inventory_from_structures((structure,), only_part="604").items

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: pytest.fail("invalid inventory fetched XML"))
    store = CorpusArtifactStore(tmp_path / "corpus")
    with pytest.raises(EcfrAppendixError, match=error):
        extract_ecfr(store, version="2026-10-12", as_of="2026-10-08", only_title=45,
                     only_part="604", include_appendices=True)
    assert not store.root.exists()


def _files(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize(
    "xml_appendices,error",
    [
        # The structure lists part 200's Appendix III; the XML's names part 201.
        ([("Appendix II to Part 200", "group", False), ("Appendix III to Part 201", "subpart", False)],
         "part '201' conflicts with enclosing part '200'"),
        # The XML adds a letter beside the numerals: Appendix II loses its order.
        ([("Appendix A to Part 200", "part", False), ("Appendix II to Part 200", "group", False),
          ("Appendix III to Part 200", "subpart", False)], None),
    ],
    ids=["names-another-part", "letter-added"],
)
def test_extract_ecfr_xml_only_part_appendix_contradiction(tmp_path, monkeypatch, xml_appendices, error):
    structure, _ = _title([_part_fixture("200", [
        ("Appendix II to Part 200", "group", False), ("Appendix III to Part 200", "subpart", False),
    ])])
    _, xml = _title([_part_fixture("200", xml_appendices)])
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    store = CorpusArtifactStore(tmp_path / "corpus")
    kwargs = {"version": "2026-10-12", "as_of": "2026-10-08", "only_title": 2,
              "only_part": "200", "include_appendices": True}

    if error is not None:
        with pytest.raises(EcfrAppendixError, match=error):
            extract_ecfr(store, **kwargs)
        assert _files(store.root) == {}
        return
    # extract_ecfr orders the XML's records by the structure's numbering, so a letter
    # the structure does not list is outside the run and II and III keep their values.
    report = extract_ecfr(store, **kwargs)
    by_path = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert "us/regulation/2/200/appendix-a" not in by_path
    assert (by_path["us/regulation/2/200/appendix-ii"].ordinal,
            by_path["us/regulation/2/200/appendix-iii"].ordinal) == (1_000_002, 1_000_003)
    assert report.coverage.complete


def test_extract_ecfr_skips_xml_only_part_appendix_outside_the_inventory(tmp_path, monkeypatch):
    # An XML appendix misplaced in part 200 that the structure does not list takes
    # neither its parsed citation nor part 200's: it is outside the run.
    structure, _ = _title([_part_fixture("200", [("Appendix II to Part 200", "group", False)])])
    _, xml = _title([_part_fixture("200", [
        ("Appendix II to Part 200", "group", False), ("Appendix III to Part 201", "subpart", False),
    ])])
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)

    report = extract_ecfr(CorpusArtifactStore(tmp_path / "corpus"), version="2026-10-12",
                          as_of="2026-10-08", only_title=2, only_part="200", include_appendices=True)

    assert report.coverage.complete
    paths = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert "us/regulation/2/200/appendix-ii" in paths
    assert not {path for path in paths if path.endswith("appendix-iii")}


def test_misplaced_appendix_does_not_change_the_numbering_of_the_part_it_names():
    # Part 604 lists the letters I and V. A roman "Appendix II to Part 604" misplaced in
    # part 605 must not turn them into numerals.
    structure, _ = _title([
        _part_fixture("604", [("Appendix I to Part 604", "part", False), ("Appendix V to Part 604", "group", False)]),
        _part_fixture("605", [("Appendix II to Part 604", "subpart", False)]),
    ])

    items = {item.citation_path: item for item in _inventory(structure, "604")}
    for designator in ("i", "v"):
        item = items[f"us/regulation/2/604/appendix-{designator}"]
        assert "appendix_numbering" not in item.metadata
        assert ecfr._structure_only_provision(item, "v", "d", "d").ordinal == _legacy_ordinal(designator)
    with pytest.raises(EcfrAppendixError, match="part '604' conflicts with enclosing part '605'"):
        _inventory(structure, "605")


def test_reserved_numeral_reads_a_lone_letter_as_a_numeral():
    # Intended: a reserved "Appendix II" shows the part's appendices are numbered with
    # roman numerals, so the live "Appendix I" sorts as 1, not as the letter I (73).
    # No eCFR part has this shape on 2026-10-08; see the module docstring.
    structure, xml = _title([_part_fixture("604", [
        ("Appendix I to Part 604", "part", False), ("Appendix II to Part 604", "part", True),
    ], title=45)], title=45, chapter="VI")

    (item,) = [item for item in _inventory(structure, "604") if item.metadata["kind"] == "appendix"]
    assert item.metadata["appendix_numbering"] == "roman"
    assert ecfr._structure_only_provision(item, "v", "d", "d").ordinal == 1_000_001
    (record,) = [
        record for record in _records(xml, structure, "604", allowed_citation_paths={item.citation_path})
    ]
    assert record.ordinal == 1_000_001


def test_ecfr_cli_reports_ambiguous_part_appendix_without_writes(tmp_path, monkeypatch, capsys):
    from axiom_corpus.corpus.cli import main

    structure, _ = _title([_part_fixture("604", [
        ("Appendix A to Part 604", "part", False), ("Appendix II to Part 604", "group", False),
    ], title=45)], title=45, chapter="VI")
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: pytest.fail("invalid inventory fetched XML"))
    output = tmp_path / "corpus"

    for command in ("inventory-ecfr", "extract-ecfr"):
        assert main([
            command, "--base", str(output), "--version", "2026-10-12", "--as-of", "2026-10-08",
            "--only-title", "45", "--only-part", "604", "--include-appendices",
        ]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Appendix II to Part 604" in captured.err
        assert "designator order is ambiguous" in captured.err
        assert "Traceback" not in captured.err
    assert not output.exists()


def test_real_2_cfr_200_appendices_from_retained_source_when_present():
    """Exercise the retained NSF-slice 2 CFR 200 XML (Appendices I-XII) when present."""
    source = (
        Path(__file__).parents[1] / "data/corpus/sources/us/regulation"
        / "2026-09-24-nsf-slice-title-2-part-200/ecfr/title-2-part-200.xml"
    )
    if not source.exists():
        pytest.skip("retained 2 CFR 200 source not fetched")
    xml = source.read_text()
    records = tuple(iter_ecfr_title_provisions(
        xml, (EcfrPartTarget(title=2, part="200", chapter="II"),), version="v",
        source_path="s.xml", include_appendices=True,
    ))
    appendices = [record for record in records if record.kind == "appendix"]
    numerals = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]

    assert [record.citation_path for record in appendices] == [
        f"us/regulation/2/200/appendix-{numeral}" for numeral in numerals
    ]
    assert [record.ordinal for record in appendices] == [1_000_000 + value for value in range(1, 13)]
    assert [record.legal_identifier for record in appendices] == [
        f"2 CFR part 200, appendix {numeral.upper()}" for numeral in numerals
    ]
    assert {record.parent_citation_path for record in appendices} == {"us/regulation/2/200"}
    assert {record.level for record in appendices} == {1}
    assert {record.metadata["appendix_numbering"] for record in appendices} == {"roman"}
    assert all(record.body for record in appendices)
    assert appendices[1].heading.startswith("Contract Provisions for Non-Federal Entity Contracts")
    # Sections are untouched by the opt-in.
    default = tuple(iter_ecfr_title_provisions(
        xml, (EcfrPartTarget(title=2, part="200", chapter="II"),), version="v", source_path="s.xml",
    ))
    assert [record for record in records if record.kind != "appendix"] == list(default)
