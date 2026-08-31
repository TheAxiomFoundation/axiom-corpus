from collections import Counter
from dataclasses import replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZipInfo

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.usc import (
    _source_artifact_bytes,
    build_usc_inventory_from_xml,
    decode_uslm_bytes,
    extract_usc,
    extract_usc_directory,
    infer_uslm_title,
    iter_usc_title_provisions,
    load_usc_source,
    parse_uslm_title,
    usc_run_id,
)

SAMPLE_USLM = """<?xml version="1.0" encoding="UTF-8"?>
<uslm:uscDoc xmlns:uslm="http://xml.house.gov/schemas/uslm/1.0" xmlns:dcterms="http://purl.org/dc/terms/" identifier="/us/usc/t26">
  <uslm:meta>
    <uslm:docNumber>26</uslm:docNumber>
    <dcterms:created>2025-12-03T10:14:52</dcterms:created>
    <uslm:docPublicationName>Online@119-46</uslm:docPublicationName>
  </uslm:meta>
  <uslm:title identifier="/us/usc/t26">
    <uslm:num>Title 26</uslm:num>
    <uslm:heading>Internal Revenue Code</uslm:heading>
    <uslm:chapter identifier="/us/usc/t26/ch1">
      <uslm:section identifier="/us/usc/t26/s32">
        <uslm:num>§ 32.</uslm:num>
        <uslm:heading>Earned income</uslm:heading>
        <uslm:content>
          <uslm:p>(a) Allowance of credit.</uslm:p>
          <uslm:p>See <uslm:ref href="/us/usc/t26/s151">section 151</uslm:ref>.</uslm:p>
        </uslm:content>
      </uslm:section>
      <uslm:section identifier="/us/usc/t26/s151">
        <uslm:num>§ 151.</uslm:num>
        <uslm:heading>Allowance of deductions for personal exemptions</uslm:heading>
        <uslm:content>
          <uslm:p>(a) In general.</uslm:p>
          <uslm:table>
            <uslm:tr><uslm:th>Year</uslm:th><uslm:th>Amount</uslm:th></uslm:tr>
            <uslm:tr><uslm:td>2026</uslm:td><uslm:td>$0</uslm:td></uslm:tr>
          </uslm:table>
        </uslm:content>
      </uslm:section>
    </uslm:chapter>
  </uslm:title>
</uslm:uscDoc>
"""

SAMPLE_USLM_42 = """
<uscDoc identifier="/us/usc/t42">
  <meta><docNumber>42</docNumber></meta>
  <title identifier="/us/usc/t42">
    <heading>The Public Health and Welfare</heading>
    <section identifier="/us/usc/t42/s1983">
      <num>§ 1983.</num>
      <heading>Civil action for deprivation of rights</heading>
      <content><p>Every person who deprives another of rights is liable.</p></content>
    </section>
  </title>
</uscDoc>
"""

SAMPLE_USLM_SUBSECTIONS = """
<uscDoc identifier="/us/usc/t42">
  <meta><docNumber>42</docNumber></meta>
  <title identifier="/us/usc/t42">
    <heading>The Public Health and Welfare</heading>
    <section identifier="/us/usc/t42/s1382">
      <num>§ 1382.</num>
      <heading>Eligibility for benefits</heading>
      <subsection identifier="/us/usc/t42/s1382/a">
        <num>(a)</num>
        <heading>Eligible individual defined</heading>
        <paragraph identifier="/us/usc/t42/s1382/a/1">
          <num>(1)</num>
          <content><p>Each aged, blind, or disabled individual is eligible if income and resources tests are met.</p></content>
        </paragraph>
      </subsection>
      <subsection identifier="/us/usc/t42/s1382/b">
        <num>(b)</num>
        <heading>Amount of benefits</heading>
        <paragraph identifier="/us/usc/t42/s1382/b/1">
          <num>(1)</num>
          <content><p>The benefit shall be payable at the rate of $1,752 or, if greater, the amount determined under <ref href="/us/usc/t42/s1382f">section 1382f</ref>.</p></content>
        </paragraph>
      </subsection>
    </section>
  </title>
</uscDoc>
"""

SAMPLE_USLM_NESTED = """
<uscDoc identifier="/us/usc/t26">
  <meta><docNumber>26</docNumber></meta>
  <title identifier="/us/usc/t26">
    <heading>Internal Revenue Code</heading>
    <section identifier="/us/usc/t26/s1401">
      <num>§ 1401.</num>
      <heading>Rate of tax</heading>
      <subsection identifier="/us/usc/t26/s1401/b">
        <num>(b)</num>
        <heading>Hospital insurance</heading>
        <paragraph identifier="/us/usc/t26/s1401/b/2">
          <num>(2)</num>
          <heading>Additional tax</heading>
          <subparagraph identifier="/us/usc/t26/s1401/b/2/A">
            <num>(A)</num>
            <heading>In general</heading>
            <chapeau>The tax is imposed on income in excess of—</chapeau>
            <clause identifier="/us/usc/t26/s1401/b/2/A/i">
              <num>(i)</num>
              <content>in the case of a joint return, $250,000,</content>
            </clause>
            <clause identifier="/us/usc/t26/s1401/b/2/A/ii">
              <num>(ii)</num>
              <content>in the case of a separate return, $125,000.</content>
            </clause>
          </subparagraph>
          <subparagraph identifier="/us/usc/t26/s1401/b/2/B">
            <num>(B)</num>
            <heading>Coordination with FICA</heading>
            <content><p>The amounts shall be reduced by wages taken into account under section 3121(b)(2).</p></content>
          </subparagraph>
        </paragraph>
      </subsection>
    </section>
  </title>
</uscDoc>
"""

OFFICIAL_TITLE_26_USLM = (
    Path(__file__).parents[1]
    / "data/corpus/sources/us/statute/"
    "2026-07-24-1401-coordination-repair-title-26/uslm/usc26.xml"
)
OFFICIAL_TITLE_26_USLM_SHA256 = (
    "d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621"
)


def _write_uslm_archive(path: Path, members: dict[str, str]) -> Path:
    with ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def test_usc_run_id_scopes_title_and_limit():
    assert usc_run_id("2026-04-29", "26", 2) == "2026-04-29-title-26-limit-2"


def test_build_usc_inventory_from_xml():
    inventory = build_usc_inventory_from_xml(
        SAMPLE_USLM,
        run_id="2026-04-29-title-26",
        source_sha256="abc123",
        source_download_url="https://uscode.house.gov/download/releasepoints/example.zip",
    )

    assert infer_uslm_title(SAMPLE_USLM) == "26"
    assert inventory.title_count == 1
    assert inventory.section_count == 2
    assert [item.citation_path for item in inventory.items] == [
        "us/statute/26",
        "us/statute/26/32",
        "us/statute/26/151",
    ]
    assert inventory.items[0].source_path == "sources/us/statute/2026-04-29-title-26/uslm/usc26.xml"
    assert inventory.items[0].metadata["created_date"] == "2025-12-03"
    assert inventory.items[0].metadata["publication_name"] == "Online@119-46"
    assert inventory.items[1].source_format == "uslm-xml"
    assert inventory.items[1].sha256 == "abc123"
    assert inventory.items[1].metadata["parent_citation_path"] == "us/statute/26"
    assert inventory.items[1].metadata["references_to"] == ["us/statute/26/151"]


def test_build_usc_inventory_ignores_unidentified_amendatory_sections():
    xml = SAMPLE_USLM.replace(
        "</uslm:section>",
        "<uslm:content><uslm:section><uslm:num>Sec. “(a)</uslm:num>"
        "<uslm:content><uslm:p>Quoted amendment.</uslm:p></uslm:content>"
        "</uslm:section></uslm:content></uslm:section>",
        1,
    )

    inventory = build_usc_inventory_from_xml(xml)

    assert all(item.citation_path != "us/statute/26/Sec" for item in inventory.items)


def test_build_usc_inventory_from_xml_respects_allowed_citations():
    inventory = build_usc_inventory_from_xml(
        SAMPLE_USLM,
        run_id="2026-04-29-title-26",
        allowed_citation_paths={"us/statute/26/151"},
    )

    assert inventory.section_count == 2
    assert [item.citation_path for item in inventory.items] == ["us/statute/26/151"]


def test_build_usc_inventory_from_xml_includes_subsections():
    inventory = build_usc_inventory_from_xml(
        SAMPLE_USLM_SUBSECTIONS,
        run_id="2026-04-29-title-42",
    )

    assert inventory.section_count == 1
    assert [item.citation_path for item in inventory.items] == [
        "us/statute/42",
        "us/statute/42/1382",
        "us/statute/42/1382/a",
        "us/statute/42/1382/a/1",
        "us/statute/42/1382/b",
        "us/statute/42/1382/b/1",
    ]
    assert inventory.items[2].metadata["kind"] == "subsection"
    assert inventory.items[2].metadata["parent_citation_path"] == "us/statute/42/1382"
    assert inventory.items[3].metadata["kind"] == "paragraph"
    assert inventory.items[3].metadata["parent_citation_path"] == "us/statute/42/1382/a"


def test_build_usc_inventory_from_xml_includes_subsections_for_allowed_section():
    inventory = build_usc_inventory_from_xml(
        SAMPLE_USLM_SUBSECTIONS,
        run_id="2026-04-29-title-42",
        allowed_citation_paths={"us/statute/42/1382"},
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/statute/42/1382",
        "us/statute/42/1382/a",
        "us/statute/42/1382/a/1",
        "us/statute/42/1382/b",
        "us/statute/42/1382/b/1",
    ]


def test_build_usc_inventory_from_xml_respects_allowed_subsection():
    inventory = build_usc_inventory_from_xml(
        SAMPLE_USLM_SUBSECTIONS,
        run_id="2026-04-29-title-42",
        allowed_citation_paths={"us/statute/42/1382/b"},
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/statute/42/1382/b",
        "us/statute/42/1382/b/1",
    ]


def test_build_usc_inventory_from_xml_respects_allowed_paragraph():
    inventory = build_usc_inventory_from_xml(
        SAMPLE_USLM_SUBSECTIONS,
        run_id="2026-04-29-title-42",
        allowed_citation_paths={"us/statute/42/1382/b/1"},
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/statute/42/1382/b/1"
    ]


def test_build_usc_inventory_from_xml_includes_source_asserted_descendants():
    inventory = build_usc_inventory_from_xml(SAMPLE_USLM_NESTED)

    assert [item.citation_path for item in inventory.items] == [
        "us/statute/26",
        "us/statute/26/1401",
        "us/statute/26/1401/b",
        "us/statute/26/1401/b/2",
        "us/statute/26/1401/b/2/A",
        "us/statute/26/1401/b/2/A/i",
        "us/statute/26/1401/b/2/A/ii",
        "us/statute/26/1401/b/2/B",
    ]
    assert inventory.items[-1].metadata["kind"] == "subparagraph"
    assert inventory.items[-1].metadata["identifier"] == "/us/usc/t26/s1401/b/2/B"


def test_official_uslm_section_status_is_preserved_as_metadata():
    source_text = SAMPLE_USLM.replace(
        '<uslm:section identifier="/us/usc/t26/s32">',
        '<uslm:section identifier="/us/usc/t26/s32" status="repealed">',
        1,
    )
    allowed_citation_paths = {"us/statute/26/32"}

    inventory = build_usc_inventory_from_xml(
        source_text,
        allowed_citation_paths=allowed_citation_paths,
    )
    records = tuple(
        iter_usc_title_provisions(
            source_text,
            version="2026-07-27-repeal-status-fixture",
            source_path="official-title-26/usc26.xml",
            allowed_citation_paths=allowed_citation_paths,
        )
    )

    assert inventory.items[0].metadata["status"] == "repealed"
    assert records[0].metadata["status"] == "repealed"


def test_official_title_26_node_count_and_semantic_label_fidelity():
    source_bytes = OFFICIAL_TITLE_26_USLM.read_bytes()
    assert sha256(source_bytes).hexdigest() == OFFICIAL_TITLE_26_USLM_SHA256

    source_root = ET.fromstring(source_bytes)
    structural_kinds = {
        "title",
        "section",
        "subsection",
        "paragraph",
        "subparagraph",
        "clause",
        "subclause",
        "item",
        "subitem",
    }
    source_kind_by_identifier: dict[str, str] = {}
    for element in source_root.iter():
        kind = element.tag.rsplit("}", 1)[-1]
        identifier = element.get("identifier")
        if (
            kind in structural_kinds
            and identifier is not None
            and identifier.startswith("/us/usc/t26")
        ):
            source_kind_by_identifier.setdefault(identifier, kind)
    source_kind_counts = Counter(source_kind_by_identifier.values())

    inventory = build_usc_inventory_from_xml(decode_uslm_bytes(source_bytes))
    kind_counts = Counter(item.metadata["kind"] for item in inventory.items)

    assert len(inventory.items) == len(
        {item.citation_path for item in inventory.items}
    )
    assert kind_counts == {
        "title": 1,
        "section": 2161,
        "subsection": 7469,
        "paragraph": 16594,
        "subparagraph": 17339,
        "clause": 10879,
        "subclause": 3694,
        "item": 181,
        "subitem": 33,
    }
    assert kind_counts == source_kind_counts
    assert sum(kind_counts.values()) == len(source_kind_by_identifier) == 58351

    items_by_path = {item.citation_path: item for item in inventory.items}
    label_keys = {
        "subsection",
        "paragraph",
        "subparagraph",
        "clause",
        "subclause",
        "item",
        "subitem",
    }
    expected = {
        "us/statute/26/12/1": (
            "paragraph",
            {"paragraph": "1"},
            "/us/usc/t26/s12/1",
            "us/statute/26/12",
        ),
        "us/statute/26/404/c/A": (
            "subparagraph",
            {"subsection": "c", "subparagraph": "A"},
            "/us/usc/t26/s404/c/A",
            "us/statute/26/404/c",
        ),
        "us/statute/26/1402/a/i": (
            "clause",
            {"subsection": "a", "clause": "i"},
            "/us/usc/t26/s1402/a/i",
            "us/statute/26/1402/a",
        ),
        "us/statute/26/62/e/18/i": (
            "clause",
            {"subsection": "e", "paragraph": "18", "clause": "i"},
            "/us/usc/t26/s62/e/18/i",
            "us/statute/26/62/e/18",
        ),
        "us/statute/26/143/f/5/B/I": (
            "subclause",
            {
                "subsection": "f",
                "paragraph": "5",
                "subparagraph": "B",
                "subclause": "I",
            },
            "/us/usc/t26/s143/f/5/B/I",
            "us/statute/26/143/f/5/B",
        ),
        "us/statute/26/432/e/4/II/aa": (
            "item",
            {
                "subsection": "e",
                "paragraph": "4",
                "subparagraph": "II",
                "item": "aa",
            },
            "/us/usc/t26/s432/e/4/II/aa",
            "us/statute/26/432/e/4/II",
        ),
    }
    for citation_path, (
        expected_kind,
        expected_labels,
        expected_identifier,
        expected_parent,
    ) in expected.items():
        metadata = items_by_path[citation_path].metadata
        assert metadata["kind"] == expected_kind
        assert {
            key: metadata[key] for key in label_keys if key in metadata
        } == expected_labels
        assert metadata["identifier"] == expected_identifier
        assert metadata["parent_citation_path"] == expected_parent

    records_by_path = {
        record.citation_path: record
        for record in iter_usc_title_provisions(
            decode_uslm_bytes(source_bytes),
            version="2026-07-24-official-fixture",
            source_path="official-title-26/usc26.xml",
            allowed_citation_paths=set(expected),
        )
    }
    assert set(records_by_path) == set(expected)
    for citation_path, (
        expected_kind,
        expected_labels,
        expected_identifier,
        expected_parent,
    ) in expected.items():
        record = records_by_path[citation_path]
        assert record.kind == expected_kind
        assert {
            key.removeprefix("usc:"): value
            for key, value in record.identifiers.items()
            if key.removeprefix("usc:") in label_keys
        } == expected_labels
        assert record.source_id == expected_identifier
        assert record.parent_citation_path == expected_parent


def test_official_title_26_duplicate_number_siblings_survive_traversal():
    source_text = decode_uslm_bytes(OFFICIAL_TITLE_26_USLM.read_bytes())
    source_root = ET.fromstring(source_text)

    def local_name(element: ET.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    source_section = next(
        element
        for element in source_root.iter()
        if local_name(element) == "section"
        and element.get("identifier") == "/us/usc/t26/s45X"
    )
    source_subsection = next(
        element
        for element in source_section
        if local_name(element) == "subsection"
        and element.get("identifier") == "/us/usc/t26/s45X/d"
    )
    source_siblings = tuple(
        element
        for element in source_subsection
        if local_name(element) == "paragraph"
        and element.get("identifier") == "/us/usc/t26/s45X/d/4"
    )
    source_headings = tuple(
        " ".join(
            " ".join(
                child.itertext()
            ).split()
        )
        for element in source_siblings
        for child in element
        if local_name(child) == "heading"
    )
    nested_kinds = {
        "subparagraph",
        "clause",
        "subclause",
        "item",
        "subitem",
    }
    source_descendants = tuple(
        (local_name(descendant), descendant.get("identifier"))
        for sibling in source_siblings
        for descendant in sibling.iter()
        if local_name(descendant) in nested_kinds
    )

    assert len(source_siblings) == 2
    assert len({sibling.get("id") for sibling in source_siblings}) == 2
    assert len(source_descendants) == 4

    document = parse_uslm_title(source_text)
    section = next(section for section in document.sections if section.section == "45X")
    subsection = next(
        subsection for subsection in section.subsections if subsection.label == "d"
    )
    traversed_siblings = tuple(
        paragraph for paragraph in subsection.paragraphs if paragraph.label == "4"
    )

    def traversed_descendants(paragraph):
        for child in paragraph.children:
            yield child.kind, child.identifier
            yield from traversed_descendants(child)

    assert tuple(paragraph.heading for paragraph in traversed_siblings) == source_headings
    assert tuple(
        descendant
        for paragraph in traversed_siblings
        for descendant in traversed_descendants(paragraph)
    ) == source_descendants

    source_identifiers = tuple(
        identifier
        for identifier in (
            *(sibling.get("identifier") for sibling in source_siblings),
            *(identifier for _, identifier in source_descendants),
        )
        if identifier is not None
    )
    expected_paths = tuple(
        dict.fromkeys(
            f"us/statute/26/{identifier.removeprefix('/us/usc/t26/s')}"
            for identifier in source_identifiers
        )
    )
    allowed_citation_paths = set(expected_paths)
    inventory = build_usc_inventory_from_xml(
        source_text,
        allowed_citation_paths=allowed_citation_paths,
    )
    records = tuple(
        iter_usc_title_provisions(
            source_text,
            version="2026-07-24-duplicate-number-fixture",
            source_path="official-title-26/usc26.xml",
            allowed_citation_paths=allowed_citation_paths,
        )
    )

    assert len(source_identifiers) == 6
    assert len(expected_paths) == 5
    assert tuple(item.citation_path for item in inventory.items) == expected_paths
    assert tuple(record.citation_path for record in records) == expected_paths


def test_build_usc_inventory_from_xml_scopes_to_source_asserted_descendant():
    inventory = build_usc_inventory_from_xml(
        SAMPLE_USLM_NESTED,
        allowed_citation_paths={"us/statute/26/1401/b/2/B"},
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/statute/26/1401/b/2/B"
    ]


def test_build_usc_inventory_rejects_contradictory_nested_identifier():
    xml = SAMPLE_USLM_NESTED.replace(
        'identifier="/us/usc/t26/s1401/b/2/A"',
        'identifier="/us/usc/t26/s1401/WRONG/A"',
        1,
    )

    with pytest.raises(ValueError, match="contradicts parent b/2"):
        build_usc_inventory_from_xml(xml)


def test_iter_usc_title_provisions_builds_normalized_records():
    records = tuple(
        iter_usc_title_provisions(
            SAMPLE_USLM,
            version="2026-04-29-title-26",
            source_path="sources/us/statute/2026-04-29-title-26/uslm/usc26.xml",
            source_as_of="2026-04-01",
            expression_date="2026-04-01",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/statute/26",
        "us/statute/26/32",
        "us/statute/26/151",
    ]
    assert records[0].kind == "title"
    assert records[0].body is None
    assert records[1].document_class == "statute"
    assert records[1].heading == "Earned income"
    assert records[1].parent_citation_path == "us/statute/26"
    assert records[1].level == 1
    assert records[1].legal_identifier == "26 U.S.C. § 32"
    assert records[1].identifiers == {
        "usc:title": "26",
        "usc:section": "32",
        "uslm:identifier": "/us/usc/t26/s32",
    }
    assert records[1].metadata["references_to"] == ["us/statute/26/151"]
    assert "Allowance of credit" in records[1].body
    assert "| Year | Amount |" in records[2].body


def test_iter_usc_title_provisions_builds_subsection_records():
    records = tuple(
        iter_usc_title_provisions(
            SAMPLE_USLM_SUBSECTIONS,
            version="2026-04-29-title-42",
            source_path="sources/us/statute/2026-04-29-title-42/uslm/usc42.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/statute/42",
        "us/statute/42/1382",
        "us/statute/42/1382/a",
        "us/statute/42/1382/a/1",
        "us/statute/42/1382/b",
        "us/statute/42/1382/b/1",
    ]
    assert records[4].kind == "subsection"
    assert records[4].level == 2
    assert records[4].legal_identifier == "42 U.S.C. § 1382(b)"
    assert records[4].parent_citation_path == "us/statute/42/1382"
    assert records[4].identifiers == {
        "usc:title": "42",
        "usc:section": "1382",
        "usc:subsection": "b",
        "uslm:identifier": "/us/usc/t42/s1382/b",
    }
    assert records[4].metadata["references_to"] == ["us/statute/42/1382f"]
    assert "$1,752" in records[4].body
    assert records[5].kind == "paragraph"
    assert records[5].level == 3
    assert records[5].legal_identifier == "42 U.S.C. § 1382(b)(1)"
    assert records[5].parent_citation_path == "us/statute/42/1382/b"
    assert records[5].identifiers == {
        "usc:title": "42",
        "usc:section": "1382",
        "usc:subsection": "b",
        "usc:paragraph": "1",
        "uslm:identifier": "/us/usc/t42/s1382/b/1",
    }


def test_iter_usc_title_provisions_respects_allowed_citations():
    records = tuple(
        iter_usc_title_provisions(
            SAMPLE_USLM,
            version="2026-04-29-title-26",
            source_path="sources/us/statute/2026-04-29-title-26/uslm/usc26.xml",
            allowed_citation_paths={"us/statute/26/32"},
        )
    )

    assert [record.citation_path for record in records] == ["us/statute/26/32"]


def test_iter_usc_title_provisions_respects_allowed_subsection():
    records = tuple(
        iter_usc_title_provisions(
            SAMPLE_USLM_SUBSECTIONS,
            version="2026-04-29-title-42",
            source_path="sources/us/statute/2026-04-29-title-42/uslm/usc42.xml",
            allowed_citation_paths={"us/statute/42/1382/b"},
        )
    )

    assert [record.citation_path for record in records] == [
        "us/statute/42/1382/b",
        "us/statute/42/1382/b/1",
    ]


def test_iter_usc_title_provisions_respects_allowed_paragraph():
    records = tuple(
        iter_usc_title_provisions(
            SAMPLE_USLM_SUBSECTIONS,
            version="2026-04-29-title-42",
            source_path="sources/us/statute/2026-04-29-title-42/uslm/usc42.xml",
            allowed_citation_paths={"us/statute/42/1382/b/1"},
        )
    )

    assert [record.citation_path for record in records] == [
        "us/statute/42/1382/b/1"
    ]


def test_iter_usc_title_provisions_builds_source_asserted_descendants():
    records = tuple(
        iter_usc_title_provisions(
            SAMPLE_USLM_NESTED,
            version="2026-07-24-title-26",
            source_path="sources/us/statute/2026-07-24-title-26/uslm/usc26.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/statute/26",
        "us/statute/26/1401",
        "us/statute/26/1401/b",
        "us/statute/26/1401/b/2",
        "us/statute/26/1401/b/2/A",
        "us/statute/26/1401/b/2/A/i",
        "us/statute/26/1401/b/2/A/ii",
        "us/statute/26/1401/b/2/B",
    ]
    clause = records[5]
    assert clause.kind == "clause"
    assert clause.level == 5
    assert clause.legal_identifier == "26 U.S.C. § 1401(b)(2)(A)(i)"
    assert clause.parent_citation_path == "us/statute/26/1401/b/2/A"
    assert clause.identifiers == {
        "usc:title": "26",
        "usc:section": "1401",
        "usc:subsection": "b",
        "usc:paragraph": "2",
        "usc:subparagraph": "A",
        "usc:clause": "i",
        "uslm:identifier": "/us/usc/t26/s1401/b/2/A/i",
    }
    coordination = records[-1]
    assert coordination.kind == "subparagraph"
    assert "3121(b)(2)" in coordination.body
    assert "3101(b)(2)" not in coordination.body


def test_extract_usc_writes_source_inventory_provisions_and_coverage(tmp_path):
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(
        store,
        version="2026-04-29",
        source_xml=source_xml,
        source_as_of="2026-04-01",
        expression_date=date(2026, 4, 1),
    )

    assert report.coverage.complete
    assert report.title == "26"
    assert report.section_count == 2
    assert report.provisions_written == 3
    assert (store.root / "sources/us/statute/2026-04-29-title-26/uslm/usc26.xml").exists()
    assert (store.root / "inventory/us/statute/2026-04-29-title-26.json").exists()
    assert (store.root / "provisions/us/statute/2026-04-29-title-26.jsonl").exists()
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert [item.citation_path for item in inventory] == [
        "us/statute/26",
        "us/statute/26/32",
        "us/statute/26/151",
    ]
    assert [record.citation_path for record in records] == [
        "us/statute/26",
        "us/statute/26/32",
        "us/statute/26/151",
    ]
    assert records[1].source_path == "sources/us/statute/2026-04-29-title-26/uslm/usc26.xml"
    assert records[1].source_as_of == "2026-04-01"
    assert records[1].expression_date == "2026-04-01"


def test_extract_usc_archive_retains_zip_and_member_provenance(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "xml_usc26@119-102.zip",
        {"usc26.xml": SAMPLE_USLM},
    )
    archive_bytes = archive.read_bytes()
    member_bytes = SAMPLE_USLM.encode()
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(
        store,
        version="2026-04-29",
        source_archive=archive,
        source_as_of="2026-04-01",
    )

    expected_source_path = "sources/us/statute/2026-04-29-title-26/olrc/xml_usc26@119-102.zip"
    retained_archive = store.root / expected_source_path
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)

    assert report.coverage.complete
    assert report.source_paths == (retained_archive,)
    assert retained_archive.read_bytes() == archive_bytes
    assert not (store.root / "sources/us/statute/2026-04-29-title-26/uslm/usc26.xml").exists()
    assert {item.source_path for item in inventory} == {expected_source_path}
    assert {item.source_format for item in inventory} == {"uslm-xml+zip"}
    assert {item.sha256 for item in inventory} == {sha256(archive_bytes).hexdigest()}
    assert {record.source_path for record in records} == {expected_source_path}
    assert {record.source_format for record in records} == {"uslm-xml+zip"}
    expected_metadata = {
        "archive_sha256": sha256(archive_bytes).hexdigest(),
        "archive_member": "usc26.xml",
        "archive_member_sha256": sha256(member_bytes).hexdigest(),
    }
    for item in inventory:
        assert item.metadata is not None
        assert expected_metadata.items() <= item.metadata.items()
    for record in records:
        assert record.metadata is not None
        assert expected_metadata.items() <= record.metadata.items()


def test_extract_usc_archive_passes_release_quality(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "xml_usc26@119-102.zip",
        {"usc26.xml": SAMPLE_USLM},
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_usc(
        store,
        version="2026-04-29",
        source_archive=archive,
    )

    release_report = validate_release(
        store.root,
        ReleaseManifest(
            name="test-usc-archive",
            scopes=(ReleaseScope("us", "statute", "2026-04-29-title-26"),),
        ),
    )

    assert report.coverage.complete
    assert release_report.ok, [issue.to_mapping() for issue in release_report.issues]


def test_release_quality_rejects_corrupt_archive_member_provenance(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "xml_usc26@119-102.zip",
        {"usc26.xml": SAMPLE_USLM},
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_usc(
        store,
        version="2026-04-29",
        source_archive=archive,
    )
    release = ReleaseManifest(
        name="test-usc-archive",
        scopes=(ReleaseScope("us", "statute", "2026-04-29-title-26"),),
    )
    inventory = load_source_inventory(report.inventory_path)
    provisions = load_provisions(report.provisions_path)

    store.write_inventory(
        report.inventory_path,
        [
            replace(
                item,
                metadata={**(item.metadata or {}), "archive_member_sha256": "0" * 64},
            )
            for item in inventory
        ],
    )
    corrupt_inventory_report = validate_release(store.root, release)

    assert corrupt_inventory_report.ok is False
    assert "archive_member_sha256_mismatch" in {
        issue.code for issue in corrupt_inventory_report.issues
    }

    store.write_inventory(report.inventory_path, inventory)
    store.write_provisions(
        report.provisions_path,
        [
            replace(
                record,
                metadata={**(record.metadata or {}), "archive_member_sha256": "0" * 64},
            )
            for record in provisions
        ],
    )
    corrupt_provision_report = validate_release(store.root, release)

    assert corrupt_provision_report.ok is False
    assert "provision_source_provenance_mismatch" in {
        issue.code for issue in corrupt_provision_report.issues
    }


def test_release_quality_skips_member_read_after_archive_hash_mismatch(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "xml_usc26@119-102.zip",
        {"usc26.xml": SAMPLE_USLM},
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_usc(
        store,
        version="2026-04-29",
        source_archive=archive,
    )
    release = ReleaseManifest(
        name="test-usc-archive",
        scopes=(ReleaseScope("us", "statute", "2026-04-29-title-26"),),
    )
    inventory = load_source_inventory(report.inventory_path)
    invalid_archive_sha256 = "0" * 64
    store.write_inventory(
        report.inventory_path,
        [
            replace(
                item,
                sha256=invalid_archive_sha256,
                metadata={
                    **(item.metadata or {}),
                    "archive_sha256": invalid_archive_sha256,
                    "archive_member_sha256": invalid_archive_sha256,
                },
            )
            for item in inventory
        ],
    )

    release_report = validate_release(store.root, release)
    issue_codes = {issue.code for issue in release_report.issues}

    assert release_report.ok is False
    assert "source_sha256_mismatch" in issue_codes
    assert "archive_member_sha256_mismatch" not in issue_codes


def test_extract_usc_rejects_loaded_source_with_raw_source_arguments(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "xml_usc26@119-102.zip",
        {"usc26.xml": SAMPLE_USLM},
    )
    source = load_usc_source(source_archive=archive)

    with pytest.raises(ValueError, match="source_payload cannot be combined"):
        extract_usc(
            CorpusArtifactStore(tmp_path / "corpus"),
            version="2026-04-29",
            source_payload=source,
            source_archive=archive,
        )

    with pytest.raises(ValueError, match="declares title 26, not requested title 42"):
        extract_usc(
            CorpusArtifactStore(tmp_path / "other-corpus"),
            version="2026-04-29",
            source_payload=source,
            title="42",
        )


def test_load_usc_source_selects_unique_requested_title_member(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "title.zip",
        {
            "metadata.xml": "<metadata />",
            "nested/usc26.xml": SAMPLE_USLM,
        },
    )

    source = load_usc_source(source_archive=archive, title="26")

    assert source.archive_member == "nested/usc26.xml"
    assert source.xml_content == SAMPLE_USLM


def test_load_usc_source_uses_exact_explicit_member(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "title.zip",
        {
            "first.xml": "<metadata />",
            "nested/official.xml": SAMPLE_USLM,
        },
    )

    source = load_usc_source(
        source_archive=archive,
        archive_member="nested/official.xml",
    )

    assert source.archive_member == "nested/official.xml"


def test_load_usc_source_rejects_missing_or_conflicting_input(tmp_path):
    xml_path = tmp_path / "usc26.xml"
    xml_path.write_text(SAMPLE_USLM)
    archive = _write_uslm_archive(
        tmp_path / "title.zip",
        {"usc26.xml": SAMPLE_USLM},
    )

    with pytest.raises(ValueError, match="exactly one"):
        load_usc_source()
    with pytest.raises(ValueError, match="exactly one"):
        load_usc_source(source_xml=xml_path, source_archive=archive)
    with pytest.raises(ValueError, match="requires source_archive"):
        load_usc_source(source_xml=xml_path, archive_member="usc26.xml")


def test_load_usc_source_rejects_ambiguous_or_missing_member(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "title.zip",
        {"one.xml": SAMPLE_USLM, "two.xml": SAMPLE_USLM},
    )

    with pytest.raises(ValueError, match="ambiguous XML members"):
        load_usc_source(source_archive=archive)
    with pytest.raises(ValueError, match="member not found"):
        load_usc_source(source_archive=archive, archive_member="missing.xml")
    with pytest.raises(ValueError, match="unsafe USLM archive member request"):
        load_usc_source(source_archive=archive, archive_member="../one.xml")


def test_load_usc_source_rejects_duplicate_archive_member(tmp_path):
    archive_path = tmp_path / "duplicate.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("usc26.xml", SAMPLE_USLM)
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("usc26.xml", SAMPLE_USLM)

    with pytest.raises(ValueError, match="duplicate member"):
        load_usc_source(source_archive=archive_path)


def test_load_usc_source_rejects_unsafe_archive_member(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "unsafe.zip",
        {"../usc26.xml": SAMPLE_USLM},
    )

    with pytest.raises(ValueError, match="unsafe member"):
        load_usc_source(source_archive=archive)


def test_load_usc_source_rejects_symlink_archive_member(tmp_path):
    archive_path = tmp_path / "symlink.zip"
    link = ZipInfo("usc26.xml")
    link.create_system = 3
    link.external_attr = 0o120777 << 16
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(link, "target.xml")

    with pytest.raises(ValueError, match="symlink member"):
        load_usc_source(source_archive=archive_path)


def test_load_usc_source_rejects_bad_zip_and_non_uslm_xml(tmp_path):
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"not a zip")
    non_uslm = _write_uslm_archive(
        tmp_path / "non-uslm.zip",
        {"usc26.xml": '<uscDoc identifier="/us/usc/t26" />'},
    )

    with pytest.raises(ValueError, match="invalid USLM ZIP archive"):
        load_usc_source(source_archive=bad_zip)
    with pytest.raises(ValueError, match="not official OLRC USLM"):
        load_usc_source(source_archive=non_uslm)


def test_load_usc_source_rejects_archive_title_mismatch(tmp_path):
    archive = _write_uslm_archive(
        tmp_path / "title.zip",
        {"only.xml": SAMPLE_USLM},
    )

    with pytest.raises(ValueError, match="declares title 26, not requested title 42"):
        load_usc_source(source_archive=archive, title="42")


def test_extract_usc_limit_certifies_scoped_inventory(tmp_path):
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(store, version="2026-04-29", source_xml=source_xml, limit=2)

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == ["us/statute/26", "us/statute/26/32"]
    assert records[0].source_as_of == "2025-12-03"


def test_extract_usc_limit_does_not_leak_descendants(tmp_path):
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM_NESTED)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(
        store,
        version="2026-07-24",
        source_xml=source_xml,
        limit=2,
    )

    assert report.coverage.complete
    assert [record.citation_path for record in load_provisions(report.provisions_path)] == [
        "us/statute/26",
        "us/statute/26/1401",
    ]


def test_extract_usc_allowed_citations_certifies_scoped_inventory(tmp_path):
    source_bytes = SAMPLE_USLM.replace("\n", "\r\n").encode()
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_bytes(source_bytes)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(
        store,
        version="2026-04-29-eitc",
        source_xml=source_xml,
        allowed_citation_paths={"us/statute/26/32"},
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == ["us/statute/26/32"]
    assert [record.citation_path for record in records] == ["us/statute/26/32"]
    assert report.source_paths[0].read_bytes() == source_bytes
    assert inventory[0].sha256 == sha256(source_bytes).hexdigest()


def test_legacy_source_excerpt_round_trips_through_recovery_parser():
    allowed = {"us/statute/26", "us/statute/26/1401"}
    excerpt = _source_artifact_bytes(
        SAMPLE_USLM_NESTED,
        title="26",
        allowed_citation_paths=allowed,
    )
    decoded = decode_uslm_bytes(excerpt)
    inventory = build_usc_inventory_from_xml(
        decoded,
        title="26",
        allowed_citation_paths=allowed,
    )
    records = list(
        iter_usc_title_provisions(
            decoded,
            version="2026-07-13-recovery",
            source_path=(
                "sources/us/statute/2026-07-13-recovery/"
                "official-documents/usc26-section-1401.xml"
            ),
            title="26",
            allowed_citation_paths={
                item.citation_path for item in inventory.items
            },
        )
    )

    assert inventory.section_count == 1
    assert [record.citation_path for record in records] == [
        item.citation_path for item in inventory.items
    ]
    assert "us/statute/26/1401/b/2/B" in {
        record.citation_path for record in records
    }


def test_extract_usc_allowed_subsection_certifies_scoped_inventory(tmp_path):
    source_xml = tmp_path / "usc42.xml"
    source_xml.write_text(SAMPLE_USLM_SUBSECTIONS)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(
        store,
        version="2026-04-29-ssi",
        source_xml=source_xml,
        allowed_citation_paths={"us/statute/42/1382/b"},
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        "us/statute/42/1382/b",
        "us/statute/42/1382/b/1",
    ]
    assert [record.citation_path for record in records] == [
        "us/statute/42/1382/b",
        "us/statute/42/1382/b/1",
    ]
    assert report.source_paths[0].read_bytes() == source_xml.read_bytes()


def test_extract_usc_allowed_paragraph_certifies_scoped_inventory(tmp_path):
    source_xml = tmp_path / "usc42.xml"
    source_xml.write_text(SAMPLE_USLM_SUBSECTIONS)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(
        store,
        version="2026-04-29-ssi",
        source_xml=source_xml,
        allowed_citation_paths={"us/statute/42/1382/b/1"},
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == ["us/statute/42/1382/b/1"]
    assert [record.citation_path for record in records] == ["us/statute/42/1382/b/1"]
    assert report.source_paths[0].read_bytes() == source_xml.read_bytes()


def test_extract_usc_directory_writes_combined_us_code_artifacts(tmp_path):
    source_dir = tmp_path / "uscode"
    source_dir.mkdir()
    (source_dir / "usc42.xml").write_text(SAMPLE_USLM_42)
    (source_dir / "usc26.xml").write_text(SAMPLE_USLM)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc_directory(
        store,
        version="2026-04-29",
        source_dir=source_dir,
        source_as_of="2026-04-01",
        expression_date="2026-04-01",
    )

    assert report.coverage.complete
    assert report.title is None
    assert report.title_count == 2
    assert report.section_count == 3
    assert report.provisions_written == 5
    assert report.provisions_path == store.provisions_path("us", "statute", "2026-04-29")
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/statute/26",
        "us/statute/26/32",
        "us/statute/26/151",
        "us/statute/42",
        "us/statute/42/1983",
    ]
    assert records[-1].source_path == "sources/us/statute/2026-04-29/uslm/usc42.xml"


def test_extract_usc_directory_only_title_scopes_run_id(tmp_path):
    source_dir = tmp_path / "uscode"
    source_dir.mkdir()
    (source_dir / "usc42.xml").write_text(SAMPLE_USLM_42)
    (source_dir / "usc26.xml").write_text(SAMPLE_USLM)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc_directory(
        store,
        version="2026-04-29",
        source_dir=source_dir,
        only_title="42",
    )

    assert report.coverage.complete
    assert report.title == "42"
    assert report.title_count == 1
    assert report.provisions_path == store.provisions_path("us", "statute", "2026-04-29-title-42")
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == ["us/statute/42", "us/statute/42/1983"]
