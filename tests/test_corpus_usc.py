from datetime import date

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.usc import (
    build_usc_inventory_from_xml,
    extract_usc,
    extract_usc_directory,
    infer_uslm_title,
    iter_usc_title_provisions,
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


def test_extract_usc_limit_certifies_scoped_inventory(tmp_path):
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_usc(store, version="2026-04-29", source_xml=source_xml, limit=2)

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == ["us/statute/26", "us/statute/26/32"]
    assert records[0].source_as_of == "2025-12-03"


def test_extract_usc_allowed_citations_certifies_scoped_inventory(tmp_path):
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM)
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
    source_text = report.source_paths[0].read_text()
    assert 'identifier="/us/usc/t26/s32"' in source_text
    assert 'identifier="/us/usc/t26/s151"' not in source_text


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
    source_text = report.source_paths[0].read_text()
    assert 'identifier="/us/usc/t42/s1382"' in source_text
    assert 'identifier="/us/usc/t42/s1382/b"' in source_text
    assert 'identifier="/us/usc/t42/s1382/a"' not in source_text


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
    source_text = report.source_paths[0].read_text()
    assert 'identifier="/us/usc/t42/s1382"' in source_text
    assert 'identifier="/us/usc/t42/s1382/b"' in source_text
    assert 'identifier="/us/usc/t42/s1382/b/1"' in source_text
    assert 'identifier="/us/usc/t42/s1382/a"' not in source_text


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
