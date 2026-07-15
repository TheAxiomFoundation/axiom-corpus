import json
from datetime import date
from urllib.error import HTTPError

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.ecfr import (
    EcfrGraphicTranscription,
    EcfrPartTarget,
    build_ecfr_inventory,
    build_ecfr_inventory_from_structures,
    extract_ecfr,
    iter_ecfr_title_provisions,
    load_ecfr_graphic_transcriptions,
    part_targets_from_structure,
)
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import ProvisionRecord

SAMPLE_STRUCTURE = {
    "identifier": "7",
    "label": "Title 7-Agriculture",
    "type": "title",
    "children": [
        {
            "identifier": "II",
            "label": "Chapter II-Food and Nutrition Service",
            "type": "chapter",
            "children": [
                {
                    "identifier": "C",
                    "label": "Subchapter C-Food Stamp Program",
                    "type": "subchapter",
                    "children": [
                        {
                            "identifier": "273",
                            "label": "Part 273-Certification of Eligible Households",
                            "type": "part",
                            "children": [
                                {
                                    "identifier": "273.1",
                                    "label": "§ 273.1 Household concept.",
                                    "label_description": "Household concept.",
                                    "type": "section",
                                },
                                {
                                    "identifier": "273.2",
                                    "label": "§ 273.2 Application processing.",
                                    "label_description": "Application processing.",
                                    "type": "section",
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ],
}

SAMPLE_SUBPART_STRUCTURE = {
    "identifier": "7",
    "label": "Title 7-Agriculture",
    "type": "title",
    "children": [
        {
            "identifier": "273",
            "label": "Part 273-Certification of Eligible Households",
            "type": "part",
            "children": [
                {
                    "identifier": "A",
                    "label": "Subpart A-General",
                    "type": "subpart",
                    "children": [
                        {
                            "identifier": "273.1",
                            "label": "§ 273.1 Household concept.",
                            "label_description": "Household concept.",
                            "type": "section",
                        }
                    ],
                }
            ],
        }
    ],
}

SAMPLE_TITLE_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.1">
      <HEAD>§ 273.1 Household concept.</HEAD>
      <P>(a) General household definition.</P>
      <P>(b) Special households.</P>
    </DIV8>
    <DIV8 N="§ 273.2" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.2">
      <HEAD>§ 273.2 Application processing.</HEAD>
      <P>(a) Application filing.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_TITLE_WITH_TABLE_XML = """
<ECFR>
  <DIV5 N="275" TYPE="PART">
    <HEAD>PART 275-PERFORMANCE REPORTING SYSTEM</HEAD>
    <DIV8 N="§ 275.3" TYPE="SECTION" NODE="7:4.1.1.2.3.1.1.3">
      <HEAD>§ 275.3 Federal monitoring.</HEAD>
      <P>(A) The Federal review sample is determined as follows:</P>
      <DIV width="100%">
        <DIV class="gpotbl_div">
          <TABLE class="gpo_table">
            <THEAD>
              <TR>
                <TH>Average monthly reviewable caseload (N)</TH>
                <TH>Federal subsample target (n′)</TH>
              </TR>
            </THEAD>
            <TBODY>
              <TR>
                <TD>31,489 and over</TD>
                <TD>n′ = 400</TD>
              </TR>
              <TR>
                <TD>10,001 to 31,488</TD>
                <TD>n′ = .011634 N + 33.66</TD>
              </TR>
            </TBODY>
          </TABLE>
        </DIV>
      </DIV>
      <P>(B) The next paragraph remains after the table.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_TITLE_WITH_GRAPHICS_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.1">
      <HEAD>§ 273.1 Household concept.</HEAD>
      <P>(a) The formula follows.</P>
      <MATH><img src="/graphics/ER07OC94.022.gif"/></MATH>
      <FP>This flush paragraph remains operative.</FP>
      <FP-1>This numbered flush paragraph also remains operative.</FP-1>
    </DIV8>
    <DIV8 N="§ 273.2" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.2">
      <HEAD>§ 273.2 Application processing.</HEAD>
      <P>(a) Application filing.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_SUBPART_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A-General</HEAD>
      <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.1">
        <HEAD>§ 273.1 Household concept.</HEAD>
        <P>(a) General household definition.</P>
      </DIV8>
    </DIV6>
  </DIV5>
</ECFR>
"""


def test_part_targets_from_structure_preserve_ancestry():
    targets = part_targets_from_structure(SAMPLE_STRUCTURE)

    assert targets == (
        EcfrPartTarget(
            title=7,
            part="273",
            chapter="II",
            subchapter="C",
            label="Part 273-Certification of Eligible Households",
        ),
    )


def test_build_ecfr_inventory_from_structure_sections():
    inventory = build_ecfr_inventory_from_structures((SAMPLE_STRUCTURE,))

    assert inventory.title_count == 1
    assert inventory.part_count == 1
    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    ]
    assert inventory.items[0].source_format == "ecfr-xml"
    assert inventory.items[0].metadata["kind"] == "part"


def test_build_ecfr_inventory_from_structure_includes_subparts():
    inventory = build_ecfr_inventory_from_structures(
        (SAMPLE_SUBPART_STRUCTURE,),
        run_id="2026-04-29-title-7-part-273",
        only_part="273",
        source_sha256_by_title={7: "abc123"},
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/7/273",
        "us/regulation/7/273/subpart-A",
        "us/regulation/7/273/1",
    ]
    assert inventory.items[0].source_path == (
        "sources/us/regulation/2026-04-29-title-7-part-273/ecfr/title-7-part-273.xml"
    )
    assert inventory.items[0].sha256 == "abc123"


def test_iter_ecfr_title_provisions_builds_normalized_records():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_TITLE_XML,
            (EcfrPartTarget(title=7, part="273", chapter="II", subchapter="C"),),
            version="2026-04-29",
            source_path="ecfr/title-7.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    ]
    assert records[0].kind == "part"
    assert records[0].body is None
    assert records[1].document_class == "regulation"
    assert records[1].heading == "Household concept"
    assert records[1].parent_citation_path == "us/regulation/7/273"
    assert records[1].level == 1
    assert "General household" in records[1].body


def test_iter_ecfr_title_provisions_preserves_table_rows():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_TITLE_WITH_TABLE_XML,
            (EcfrPartTarget(title=7, part="275", chapter="II", subchapter="C"),),
            version="2026-06-15-title-7-part-275",
            source_path="sources/us/regulation/2026-06-15-title-7-part-275/ecfr/title-7-part-275.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/7/275",
        "us/regulation/7/275/3",
    ]
    body = records[1].body
    assert body is not None
    assert "(A) The Federal review sample is determined as follows:" in body
    assert "Average monthly reviewable caseload (N) | Federal subsample target (n′)" in body
    assert "10,001 to 31,488 | n′ = .011634 N + 33.66" in body
    assert body.index("(A) The Federal review sample") < body.index(
        "Average monthly reviewable caseload"
    )
    assert body.index("10,001 to 31,488") < body.index(
        "(B) The next paragraph remains after the table."
    )


def test_iter_ecfr_title_provisions_preserves_flush_paragraphs_and_formulas():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_TITLE_WITH_GRAPHICS_XML,
            (EcfrPartTarget(title=7, part="273"),),
            version="2026-07-15-title-7-part-273",
            source_path="sources/us/regulation/v/ecfr/title-7-part-273.xml",
            graphic_transcriptions={"ER07OC94.022": "X = (a * b) / c"},
        )
    )

    body = records[1].body
    assert body is not None
    assert "Formula (ER07OC94.022, verified official image): X = (a * b) / c" in body
    assert "This flush paragraph remains operative." in body
    assert "This numbered flush paragraph also remains operative." in body
    assert body.index("The formula follows") < body.index("Formula (ER07OC94.022")
    assert body.index("Formula (ER07OC94.022") < body.index("This flush paragraph")


def test_load_ecfr_graphic_transcriptions_validates_digest_bound_entries(tmp_path):
    manifest = tmp_path / "graphics.json"
    manifest.write_text(
        '{"graphics":{"ER07OC94.022":{"sha256":"'
        + "a" * 64
        + '","text":" X = (a * b) / c "}}}'
    )

    assert load_ecfr_graphic_transcriptions(manifest) == {
        "ER07OC94.022": EcfrGraphicTranscription(
            sha256="a" * 64,
            text="X = (a * b) / c",
        )
    }


def test_iter_ecfr_title_provisions_builds_subpart_hierarchy():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_SUBPART_XML,
            (EcfrPartTarget(title=7, part="273"),),
            version="2026-04-29",
            source_path="sources/us/regulation/2026-04-29/ecfr/title-7.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/subpart-A",
        "us/regulation/7/273/1",
    ]
    assert records[2].parent_citation_path == "us/regulation/7/273/subpart-A"
    assert records[2].level == 2


def test_extract_ecfr_writes_source_inventory_provisions_and_coverage(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_title_xml",
        lambda title, as_of: pytest.fail("part-scoped extract fetched a full title"),
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: SAMPLE_TITLE_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")
    run_id = "2026-04-29-title-7-part-273"
    store.write_provisions(
        store.provisions_path("us", "regulation", run_id),
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/999",
                body="stale",
            )
        ],
    )

    report = extract_ecfr(
        store,
        version="2026-04-29",
        as_of="2024-04-16",
        expression_date=date(2024, 4, 16),
        only_title=7,
        only_part="273",
    )

    assert report.coverage.complete
    assert report.provisions_written == 3
    assert (store.root / f"sources/us/regulation/{run_id}/ecfr/title-7-part-273.xml").exists()
    assert (store.root / f"inventory/us/regulation/{run_id}.json").exists()
    assert (store.root / f"provisions/us/regulation/{run_id}.jsonl").exists()
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    ]
    assert records[1].source_path == (
        "sources/us/regulation/2026-04-29-title-7-part-273/ecfr/title-7-part-273.xml"
    )
    assert records[1].source_as_of == "2024-04-16"
    assert records[1].expression_date == "2024-04-16"


def test_extract_ecfr_archives_sha_bound_formula_graphics(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: SAMPLE_TITLE_WITH_GRAPHICS_XML,
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-07-15",
        as_of="2026-07-09",
        expression_date=date(2026, 7, 9),
        only_title=7,
        only_part="273",
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text="X = (a * b) / c",
            )
        },
    )

    assert report.coverage.complete
    graphic_path = (
        store.root
        / "sources/us/regulation/2026-07-15-title-7-part-273/ecfr/graphics/ER07OC94.022.png"
    )
    evidence_path = graphic_path.with_name("transcriptions.json")
    assert graphic_path.read_bytes() == graphic
    assert '"sha256"' in evidence_path.read_text()
    records = load_provisions(report.provisions_path)
    assert "verified official image" in (records[1].body or "")


def test_extract_ecfr_reprocesses_complete_scope_for_graphic_transcriptions(
    tmp_path, monkeypatch
):
    import axiom_corpus.corpus.ecfr as ecfr

    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: SAMPLE_TITLE_WITH_GRAPHICS_XML,
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")
    kwargs = {
        "version": "2026-07-15",
        "as_of": "2026-07-09",
        "expression_date": date(2026, 7, 9),
        "only_title": 7,
        "only_part": "273",
    }

    first_report = extract_ecfr(store, **kwargs)
    first_records = load_provisions(first_report.provisions_path)
    assert "verified official image" not in (first_records[1].body or "")

    second_report = extract_ecfr(
        store,
        **kwargs,
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text="X = (a * b) / c",
            )
        },
    )

    second_records = load_provisions(second_report.provisions_path)
    assert "verified official image" in (second_records[1].body or "")
    assert any(path.name == "transcriptions.json" for path in second_report.source_paths)


def test_extract_ecfr_rolls_back_failed_transcription_rebuild(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: SAMPLE_TITLE_WITH_GRAPHICS_XML,
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")
    kwargs = {
        "version": "2026-07-15",
        "as_of": "2026-07-09",
        "expression_date": date(2026, 7, 9),
        "only_title": 7,
        "only_part": "273",
    }
    successful = extract_ecfr(
        store,
        **kwargs,
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text="original transcription",
            )
        },
    )
    records_before = successful.provisions_path.read_bytes()
    evidence_path = next(
        path for path in successful.source_paths if path.name == "transcriptions.json"
    )
    evidence_before = evidence_path.read_bytes()

    failed = extract_ecfr(
        store,
        **kwargs,
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256="0" * 64,
                text="rejected transcription",
            )
        },
    )

    assert failed.title_error_count == 1
    assert failed.provisions_path.read_bytes() == records_before
    assert evidence_path.read_bytes() == evidence_before


def test_extract_ecfr_aggregates_graphic_evidence_across_titles(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    identifiers = {1: "ER07OC94.022", 2: "ER25SE06.014"}
    graphics = {
        identifier: b"\x89PNG\r\n\x1a\n" + identifier.encode()
        for identifier in identifiers.values()
    }

    def structure(title, as_of):
        return {**SAMPLE_STRUCTURE, "identifier": str(title)}

    def title_xml(title, as_of):
        return SAMPLE_TITLE_WITH_GRAPHICS_XML.replace(
            "ER07OC94.022", identifiers[title]
        )

    monkeypatch.setattr(ecfr, "DEFAULT_CFR_TITLES", (1, 2))
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_title_xml", title_xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphics[identifier])
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-07-15",
        as_of="2026-07-09",
        expression_date=date(2026, 7, 9),
        workers=2,
        graphic_transcriptions={
            identifier: EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text=f"formula for {identifier}",
            )
            for identifier, graphic in graphics.items()
        },
    )

    evidence_path = next(
        path for path in report.source_paths if path.name == "transcriptions.json"
    )
    assert set(json.loads(evidence_path.read_text())["graphics"]) == set(graphics)

    failed_store = CorpusArtifactStore(tmp_path / "failed-corpus")
    failed = extract_ecfr(
        failed_store,
        version="2026-07-15",
        as_of="2026-07-09",
        expression_date=date(2026, 7, 9),
        workers=2,
        graphic_transcriptions={
            identifiers[1]: EcfrGraphicTranscription(
                sha256=sha256_bytes(graphics[identifiers[1]]),
                text="valid transcription",
            ),
            identifiers[2]: EcfrGraphicTranscription(
                sha256="0" * 64,
                text="rejected transcription",
            ),
        },
    )

    assert failed.title_error_count == 1
    assert load_provisions(failed.provisions_path) == ()


def test_extract_ecfr_writes_structure_only_placeholders(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    structure = {
        **SAMPLE_STRUCTURE,
        "children": [
            {
                **SAMPLE_STRUCTURE["children"][0],
                "children": [
                    {
                        **SAMPLE_STRUCTURE["children"][0]["children"][0],
                        "children": [
                            {
                                **SAMPLE_STRUCTURE["children"][0]["children"][0]["children"][0],
                                "children": [
                                    *SAMPLE_STRUCTURE["children"][0]["children"][0]["children"][0][
                                        "children"
                                    ],
                                    {
                                        "identifier": "273.3",
                                        "label": "§ 273.3 Missing from XML.",
                                        "label_description": "Missing from XML.",
                                        "type": "section",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: SAMPLE_TITLE_XML)

    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ecfr(
        store,
        version="2026-04-29",
        as_of="2024-04-16",
        expression_date=date(2024, 4, 16),
        only_title=7,
        only_part="273",
    )

    records = load_provisions(report.provisions_path)
    assert report.coverage.complete
    assert report.provisions_written == 4
    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
        "us/regulation/7/273/3",
    ]
    placeholder = records[-1]
    assert placeholder.body is None
    assert placeholder.heading == "Missing from XML"
    assert placeholder.parent_citation_path == "us/regulation/7/273"
    assert placeholder.legal_identifier == "7 CFR 273.3"
    assert placeholder.identifiers == {
        "ecfr:title": "7",
        "ecfr:part": "273",
        "ecfr:section": "3",
    }
    assert placeholder.metadata is not None
    assert placeholder.metadata["structure_only"] is True
    assert placeholder.metadata["body_status"] == "not_in_ecfr_full_xml"


def test_extract_ecfr_keeps_failed_titles_missing_from_coverage(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    def fail_part_xml(title, part, as_of):
        raise HTTPError("https://example.test", 404, "Not Found", {}, None)

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", fail_part_xml)

    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ecfr(
        store,
        version="2026-04-29",
        as_of="2024-04-16",
        expression_date=date(2024, 4, 16),
        only_title=7,
        only_part="273",
    )

    assert not report.coverage.complete
    assert report.title_error_count == 1
    assert report.provisions_written == 0
    assert report.coverage.missing_from_provisions == (
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    )


def test_build_ecfr_inventory_skips_missing_titles_in_full_mode(monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    def fake_fetch(title, as_of):
        if title == 2:
            raise HTTPError("https://example.test", 404, "Not Found", {}, None)
        return {**SAMPLE_STRUCTURE, "identifier": str(title)}

    monkeypatch.setattr(ecfr, "DEFAULT_CFR_TITLES", (1, 2))
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", fake_fetch)

    inventory = build_ecfr_inventory(as_of="2024-04-16")

    assert inventory.title_count == 1
    assert len(inventory.items) == 3
