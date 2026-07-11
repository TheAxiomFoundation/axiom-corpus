import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from axiom_corpus.converters.nz_pco import NZPCOConverter
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.nz_legislation import (
    _apply_source_name_metadata,
    _assign_schedule_provision_paths,
    _current_law_source_bytes,
    _dedupe_inventory,
    _dedupe_records,
    _parent_citation_path,
    _schedule_hierarchy,
    _structural_own_body,
    extract_nz_legislation,
    nz_citation_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
NZ_RELEASE_VERSION = "2026-06-16-rulespec-nz-pco"

SAMPLE_NZ_ACT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM407935" year="2007" act.no="97" act.type="public"
     date.assent="2007-11-15" stage="in-force" date.as.at="2024-06-01">
  <cover>
    <title>Income Tax Act 2007</title>
    <assent>2007-11-15</assent>
  </cover>
  <ministry>Inland Revenue</ministry>
  <long-title>An Act to consolidate and reform the law relating to income tax</long-title>
  <body>
    <prov id="DLM407936">
      <label>1</label>
      <heading>Title</heading>
      <prov.body>
        <subprov id="DLM407937">
          <label>(1)</label>
          <para><text>This Act is the Income Tax Act 2007.</text></para>
        </subprov>
        <subprov id="DLM407938">
          <label>(2)</label>
          <para><text>This Act comes into force on 1 April 2008.</text></para>
        </subprov>
      </prov.body>
    </prov>
    <prov id="DLM407939">
      <label>2</label>
      <heading>Interpretation</heading>
      <prov.body>
        <para>
          <text>In this Act, the following terms have the meanings given.</text>
          <label-para>
            <label>(a)</label>
            <text>amount means any amount of money</text>
          </label-para>
          <label-para>
            <label>(b)</label>
            <text>tax means income tax</text>
          </label-para>
        </para>
      </prov.body>
    </prov>
    <prov id="DLM407940">
      <label>3</label>
      <heading>Empty section</heading>
    </prov>
  </body>
</act>
"""

SAMPLE_NZ_REGULATION_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<regulation id="DLM200000" year="2020" regulation.no="10" regulation.type="public">
  <cover><title>Income Tax Regulations 2020</title></cover>
  <body>
    <prov id="DLM200001">
      <label>2</label>
      <heading>Rate</heading>
      <prov.body>
        <para><text>The prescribed rate is 10 percent.</text></para>
      </prov.body>
    </prov>
  </body>
</regulation>
"""

SAMPLE_NZ_SECONDARY_135_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<regulation id="DLM5178334" year="2013" sr.no="135" sr.type="regulation">
  <cover><title>Road User Charges (Rates) Regulations 2013</title></cover>
  <body>
    <prov id="SR135P1">
      <label>1</label>
      <heading>Title</heading>
      <prov.body><para><text>These regulations are the rates regulations.</text></para></prov.body>
    </prov>
  </body>
</regulation>
"""

SAMPLE_NZ_SECONDARY_307_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<regulation id="DLM5179000" year="2013" sr.no="307" sr.type="order">
  <cover><title>Road User Charges Order 2013</title></cover>
  <body>
    <prov id="SR307P1">
      <label>1</label>
      <heading>Title</heading>
      <prov.body><para><text>This order is the rates order.</text></para></prov.body>
    </prov>
  </body>
</regulation>
"""

SAMPLE_NZ_SPLIT_BILL_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<bill id="DLM6110593" year="2013" bill.no="150" bill.type="government" split.letter="B">
  <cover><title>KiwiSaver (Vulnerable Children) Amendment Bill</title></cover>
  <body>
    <prov id="BILL150BP1">
      <label>1</label>
      <heading>Title</heading>
      <prov.body><para><text>This Act is the KiwiSaver Amendment Act.</text></para></prov.body>
    </prov>
  </body>
</bill>
"""

SAMPLE_NZ_NESTED_PROVISIONS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM900000" year="2026" act.no="1" act.type="public">
  <cover><title>Nested Provisions Act 2026</title></cover>
  <body>
    <prov id="BODY1">
      <label>1</label>
      <heading>Title</heading>
      <prov.body><para><text>This Act has a direct section.</text></para></prov.body>
    </prov>
    <part>
      <label>1</label>
      <heading>Main rules</heading>
      <prov id="PART3">
        <label>3</label>
        <heading>Nested body rule</heading>
        <prov.body><para><text>This nested section must be extracted.</text></para></prov.body>
      </prov>
    </part>
  </body>
  <schedule.group>
    <schedule id="SCHED1">
      <label>1</label>
      <heading>Rates</heading>
      <prov id="SCHED1CLAUSE1">
        <label>1</label>
        <heading>Schedule clause</heading>
        <prov.body><para><text>This schedule clause must not collide.</text></para></prov.body>
      </prov>
    </schedule>
  </schedule.group>
</act>
"""

SAMPLE_NZ_TABLE_PROVISION_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM900100" year="2026" act.no="2" act.type="public">
  <cover><title>Rates Table Act 2026</title></cover>
  <body>
    <prov id="RATE1">
      <label>1</label>
      <heading>Rates</heading>
      <prov.body>
        <subprov id="RATE1SUB1">
          <label>(1)</label>
          <para>
            <legtable>
              <table>
                <tgroup cols="3">
                  <thead>
                    <row>
                      <entry>Row</entry>
                      <entry>Range</entry>
                      <entry>Tax rate</entry>
                    </row>
                  </thead>
                  <tbody>
                    <row>
                      <entry>1</entry>
                      <entry>$0 to $15,600</entry>
                      <entry>0.105</entry>
                    </row>
                    <row>
                      <entry>2</entry>
                      <entry>$15,601 to $53,500</entry>
                      <entry>0.175</entry>
                    </row>
                  </tbody>
                </tgroup>
              </table>
            </legtable>
          </para>
        </subprov>
      </prov.body>
    </prov>
  </body>
</act>
"""

SAMPLE_NZ_SCHEDULE_STRUCTURES_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM900200" year="2026" act.no="3" act.type="public">
  <cover><title>Schedule Rates Act 2026</title></cover>
  <schedule.group>
    <schedule id="SCHED2">
      <label>2</label>
      <heading>Income tests and rates</heading>
      <schedule.misc>
        <def-para id="INCOME1">
          <para>
            <text><def-term>Income Test 1</def-term> means income over $160.</text>
          </para>
        </def-para>
        <head1 id="PART1">
          <label>Part 1</label>
          <heading>Main rates</heading>
          <legtable>
            <table>
              <tgroup cols="2">
                <tbody><row><entry>Single</entry><entry>$100</entry></row></tbody>
              </tgroup>
            </table>
          </legtable>
        </head1>
        <part id="PARTA">
          <label>A</label>
          <para><label-para>1</label-para><text>A listed PIE.</text></para>
          <para><label-para>2</label-para><text>A listed life insurer.</text></para>
        </part>
      </schedule.misc>
    </schedule>
  </schedule.group>
</act>
"""

SAMPLE_NZ_SCHEDULE_HIERARCHY_COLLISIONS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM900300" year="2026" act.no="6" act.type="public">
  <cover><title>Schedule Hierarchy Act 2026</title></cover>
  <schedule.group>
    <schedule id="SCHEDH1">
      <label>1</label>
      <schedule.provisions>
        <part id="PARTA1">
          <label>Part A</label>
          <para><text>first part own sentinel.</text></para>
          <subpart id="SUBPART1">
            <label>Subpart 1</label>
            <para><text>subpart own sentinel.</text></para>
            <prov id="CLAUSE1A">
              <label>1</label>
              <heading>First clause</heading>
              <prov.body>
                <para>
                  <text>first hierarchy clause.</text>
                  <def-para id="NESTEDDEF1">
                    <para><text><def-term>nested term</def-term> means clause-only text.</text></para>
                  </def-para>
                  <legtable><table><tgroup cols="2"><tbody>
                    <row><entry>clause table sentinel</entry><entry>$300</entry></row>
                  </tbody></tgroup></table></legtable>
                </para>
              </prov.body>
            </prov>
          </subpart>
        </part>
        <part id="PARTA2">
          <label>Part A</label>
          <prov id="CLAUSE1B">
            <label>1</label>
            <heading>Second clause</heading>
            <prov.body><para><text>second hierarchy clause.</text></para></prov.body>
          </prov>
        </part>
      </schedule.provisions>
    </schedule>
  </schedule.group>
</act>
"""

SAMPLE_NZ_SCHEDULE_OWN_BODY_AND_HEADING_ONLY_HIERARCHY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM900400" year="2026" act.no="7" act.type="public">
  <cover><title>Schedule Own Body Act 2026</title></cover>
  <schedule.group>
    <schedule id="SCHEDOWN1">
      <label>4</label>
      <heading>Boards</heading>
      <schedule.misc>
        <para><text>schedule own sentinel.</text></para>
        <table>
          <summary>Accessibility metadata says this table has 2 rows and 2 columns.</summary>
          <tgroup>
            <tbody>
              <row><entry>Band</entry><entry>Amount</entry></row>
              <row><entry>A</entry><entry>$10</entry></row>
            </tbody>
          </tgroup>
        </table>
        <def-para id="SCHEDULEDEF1">
          <para><text><def-term>own term</def-term> means definition descendant sentinel.</text></para>
        </def-para>
        <head1 id="PART2">
          <label>Part 2</label>
          <heading>Descriptions of areas</heading>
          <head2 id="BOARDHEADING1">
            <heading>Te Taumata Hauora o Te Kahu o Taonui</heading>
            <prov id="HEADINGCLAUSE2">
              <label>2</label>
              <heading>Description of area</heading>
              <prov.body><para><text>heading descendant sentinel.</text></para></prov.body>
            </prov>
          </head2>
        </head1>
      </schedule.misc>
      <notes><history><history-note>history descendant sentinel.</history-note></history></notes>
    </schedule>
  </schedule.group>
</act>
"""

SAMPLE_NZ_INACTIVE_CONTENT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<act id="CURRENTLAW1" year="2026" act.no="4" act.type="public" stage="in-force">
  <cover><title>Current Law Act 2026</title></cover>
  <body>
    <prov id="ACTIVE1">
      <label>1</label>
      <heading>Current rule</heading>
      <prov.body>
        <subprov id="ACTIVE1SUB1">
          <label>(1)</label>
          <para><text>Current provision text.</text></para>
        </subprov>
        <subprov id="REPEALEDSUB" deletion-status="repealed">
          <label>(2)</label>
          <para><text>Repealed subprovision text.</text></para>
        </subprov>
      </prov.body>
    </prov>
    <part id="EXPIREDPART" deletion-status="expired">
      <label>2</label>
      <prov id="INHERITEDEXPIRED">
        <label>2</label>
        <heading>Expired through ancestor</heading>
        <prov.body><para><text>Inherited expired text.</text></para></prov.body>
      </prov>
    </part>
    <prov id="DIRECTREVOKED" deletion-status="revoked">
      <label>3</label>
      <heading>Directly revoked</heading>
      <prov.body><para><text>Directly revoked text.</text></para></prov.body>
    </prov>
    <part id="NOTINFORCEPART" stage="not-in-force">
      <label>4</label>
      <prov id="INHERITEDNOTINFORCE">
        <label>4</label>
        <heading>Not in force through ancestor</heading>
        <prov.body><para><text>Inherited not-in-force text.</text></para></prov.body>
      </prov>
    </part>
    <part id="UNKNOWNSTAGEPART" stage="unknown">
      <label>5</label>
      <prov id="INHERITEDUNKNOWNSTAGE">
        <label>5</label>
        <heading>Unknown stage through ancestor</heading>
        <prov.body><para><text>Inherited unknown-stage text.</text></para></prov.body>
      </prov>
    </part>
  </body>
  <schedule.group>
    <schedule id="LMS199577">
      <label>21</label>
      <heading>Current schedule 21</heading>
    </schedule>
    <schedule id="DLM1695100" deletion-status="repealed">
      <label>21</label>
      <heading>Repealed schedule 21</heading>
    </schedule>
    <schedule id="LMS960776">
      <label>39</label>
      <heading>Current schedule 39</heading>
    </schedule>
    <schedule id="DLM3683728" deletion-status="repealed">
      <label>39</label>
      <heading>Repealed schedule 39</heading>
    </schedule>
  </schedule.group>
</act>
"""


def test_extract_nz_legislation_requires_source_or_directory(tmp_path):
    with pytest.raises(ValueError, match="at least one source XML path or source directory"):
        extract_nz_legislation(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-06-16-nz",
        )


def test_extract_nz_legislation_writes_statute_artifacts(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "income-tax-act-2007.xml"
    source_xml.write_text(SAMPLE_NZ_ACT_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-income-tax",
        source_xmls=(source_xml,),
        source_as_of="2026-06-16",
        expression_date="2026-04-01",
    )

    assert report.source_count == 4
    assert report.provisions_written == 4
    class_report = report.class_reports[0]
    assert class_report.document_class == "statute"
    assert class_report.coverage.complete
    assert len(class_report.source_paths) == 1
    assert class_report.source_paths[0].exists()

    provisions_path = base / "provisions/nz/statute/2026-06-16-nz-income-tax.jsonl"
    rows = [json.loads(line) for line in provisions_path.read_text().splitlines()]
    document = next(
        row for row in rows if row["citation_path"] == "nz/statute/act/public/2007/0097"
    )
    assert document["body"] is None
    assert document["kind"] == "document"
    assert document["level"] == 1
    assert document["source_url"] == (
        "https://www.legislation.govt.nz/act/public/2007/0097/latest/contents.html"
    )
    assert document["source_path"] == (
        "sources/nz/statute/2026-06-16-nz-income-tax/act/public/2007/0097/wholeof.xml"
    )
    assert document["source_as_of"] == "2026-06-16"
    assert document["expression_date"] == "2026-04-01"
    assert "parent_citation_path" not in document
    assert "parent_id" not in document
    section_1 = next(row for row in rows if row["citation_path"].endswith("/section/1"))
    assert section_1["citation_path"] == "nz/statute/act/public/2007/0097/section/1"
    assert section_1["citation_label"] == "Income Tax Act 2007 s 1"
    assert section_1["source_url"] == (
        "https://www.legislation.govt.nz/act/public/2007/0097/latest/DLM407936.html"
    )
    assert section_1["source_path"] == (
        "sources/nz/statute/2026-06-16-nz-income-tax/act/public/2007/0097/wholeof.xml"
    )
    assert section_1["kind"] == "section"
    assert section_1["level"] == 2
    assert section_1["parent_citation_path"] == document["citation_path"]
    assert section_1["parent_id"] == document["id"]
    assert section_1["ordinal"] == 1
    assert section_1["expression_date"] == "2026-04-01"
    assert "(1) This Act is the Income Tax Act 2007." in section_1["body"]
    assert "(2) This Act comes into force on 1 April 2008." in section_1["body"]
    assert section_1["metadata"]["administering_ministry"] == "Inland Revenue"

    inventory = json.loads(
        (base / "inventory/nz/statute/2026-06-16-nz-income-tax.json").read_text()
    )
    assert len(inventory["items"]) == 4
    assert inventory["items"][0]["citation_path"] == document["citation_path"]
    assert inventory["items"][0]["source_format"] == "legislation.govt.nz-pco-xml"
    assert inventory["items"][0]["metadata"]["source_name"] == ("act/public/2007/0097/wholeof.xml")


def test_extract_nz_legislation_groups_statutes_and_regulations_from_directory(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_dir = tmp_path / "pco"
    source_dir.mkdir()
    (source_dir / "income-tax-act-2007.xml").write_text(SAMPLE_NZ_ACT_XML)
    (source_dir / "income-tax-regulations-2020.xml").write_text(SAMPLE_NZ_REGULATION_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-legislation",
        source_dir=source_dir,
    )

    assert [class_report.document_class for class_report in report.class_reports] == [
        "regulation",
        "statute",
    ]
    assert (base / "provisions/nz/regulation/2026-06-16-nz-legislation.jsonl").exists()
    assert (base / "provisions/nz/statute/2026-06-16-nz-legislation.jsonl").exists()


def test_extract_nz_legislation_preserves_nested_api_source_paths(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_dir = tmp_path / "pco"
    path_135 = (
        source_dir
        / "secondary-legislation/pco-drafted/2013/135"
        / "secondary-legislation_pco-drafted_2013_135_en_2014-07-01.xml"
    )
    path_307 = (
        source_dir
        / "secondary-legislation/pco-drafted/2013/307"
        / "secondary-legislation_pco-drafted_2013_307_en_2013-07-29.xml"
    )
    path_135.parent.mkdir(parents=True)
    path_307.parent.mkdir(parents=True)
    path_135.write_text(SAMPLE_NZ_SECONDARY_135_XML)
    path_307.write_text(SAMPLE_NZ_SECONDARY_307_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-legislation",
        source_dir=source_dir,
    )

    assert report.provisions_written == 4
    class_report = report.class_reports[0]
    assert class_report.document_class == "regulation"
    assert len(class_report.source_paths) == 2

    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/regulation/2026-06-16-nz-legislation.jsonl")
        .read_text()
        .splitlines()
    ]
    provision_rows = [row for row in rows if row["kind"] == "regulation"]
    assert {row["citation_path"] for row in provision_rows} == {
        "nz/regulation/regulation/public/2013/0135/regulation/1",
        "nz/regulation/regulation/public/2013/0307/regulation/1",
    }
    assert {
        "sources/nz/regulation/2026-06-16-nz-legislation/"
        "secondary-legislation/pco-drafted/2013/135/"
        "secondary-legislation_pco-drafted_2013_135_en_2014-07-01.xml",
        "sources/nz/regulation/2026-06-16-nz-legislation/"
        "secondary-legislation/pco-drafted/2013/307/"
        "secondary-legislation_pco-drafted_2013_307_en_2013-07-29.xml",
    } == {row["source_path"] for row in provision_rows}
    assert any(
        row["source_url"]
        == "https://www.legislation.govt.nz/secondary-legislation/pco-drafted/2013/135/latest/SR135P1.html"
        for row in provision_rows
    )


def test_extract_nz_legislation_preserves_alphanumeric_api_number_tokens(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_dir = tmp_path / "pco"
    source_xml = (
        source_dir / "bill/government/2013/150-B" / "bill_government_2013_150-B_en_2014-06-17.xml"
    )
    source_xml.parent.mkdir(parents=True)
    source_xml.write_text(SAMPLE_NZ_SPLIT_BILL_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-legislation",
        source_dir=source_dir,
    )

    assert report.provisions_written == 2
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/rulemaking/2026-06-16-nz-legislation.jsonl")
        .read_text()
        .splitlines()
    ]
    row = next(row for row in rows if row["kind"] == "clause")
    assert row["citation_path"] == "nz/rulemaking/bill/government/2013/150-b/clause/1"
    assert row["source_url"] == (
        "https://www.legislation.govt.nz/bill/government/2013/150-B/latest/BILL150BP1.html"
    )


def test_extract_nz_legislation_writes_nested_provisions_without_label_collisions(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "nested-provisions-act-2026.xml"
    source_xml.write_text(SAMPLE_NZ_NESTED_PROVISIONS_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-nested",
        source_xmls=(source_xml,),
    )

    assert report.provisions_written == 5
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/statute/2026-06-16-nz-nested.jsonl")
        .read_text()
        .splitlines()
    ]
    provision_rows = [row for row in rows if row["kind"] in {"clause", "section"}]
    assert {row["citation_path"] for row in provision_rows} == {
        "nz/statute/act/public/2026/0001/section/1",
        "nz/statute/act/public/2026/0001/section/3",
        "nz/statute/act/public/2026/0001/schedule/1/clause/1",
    }
    assert {row["metadata"]["provision_path_token"] for row in provision_rows} == {
        "1",
        "3",
    }


def test_extract_nz_legislation_preserves_schedule_hierarchy_and_collisions(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "schedule-hierarchy-act-2026.xml"
    source_xml.write_text(SAMPLE_NZ_SCHEDULE_HIERARCHY_COLLISIONS_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-schedule-hierarchy",
        source_xmls=(source_xml,),
    )

    assert report.provisions_written == 7
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/statute/2026-06-16-nz-schedule-hierarchy.jsonl")
        .read_text()
        .splitlines()
    ]
    by_source_id = {
        row.get("identifiers", {}).get("legislation.govt.nz:provision")
        or row.get("identifiers", {}).get("legislation.govt.nz:element"): row
        for row in rows
    }
    first_part = by_source_id["PARTA1"]
    second_part = by_source_id["PARTA2"]
    subpart = by_source_id["SUBPART1"]
    first_clause = by_source_id["CLAUSE1A"]
    second_clause = by_source_id["CLAUSE1B"]

    assert first_part["citation_path"].endswith("/schedule/1/part/a")
    assert second_part["citation_path"].endswith("/schedule/1/part/a-parta2")
    assert subpart["citation_path"].endswith("/schedule/1/part/a/subpart/1")
    assert first_clause["citation_path"].endswith("/schedule/1/part/a/subpart/1/clause/1")
    assert second_clause["citation_path"].endswith("/schedule/1/part/a-parta2/clause/1")
    assert first_clause["parent_citation_path"] == subpart["citation_path"]
    assert second_clause["parent_citation_path"] == second_part["citation_path"]
    assert first_clause["level"] == 5
    assert second_clause["level"] == 4
    assert first_part["body"] == "first part own sentinel."
    assert subpart["body"] == "subpart own sentinel."
    assert "first hierarchy clause" not in first_part["body"]
    assert "first hierarchy clause" not in subpart["body"]
    assert "clause table sentinel" not in first_part["body"]
    assert "clause table sentinel" not in subpart["body"]
    assert first_clause["body"].count("nested term means clause-only text") == 1
    assert first_clause["body"].count("clause table sentinel | $300") == 1
    assert "NESTEDDEF1" not in by_source_id


def test_extract_nz_legislation_preserves_schedule_own_body_and_heading_only_hierarchy(
    tmp_path,
):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "schedule-own-body-act-2026.xml"
    source_xml.write_text(SAMPLE_NZ_SCHEDULE_OWN_BODY_AND_HEADING_ONLY_HIERARCHY_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-schedule-own-body",
        source_xmls=(source_xml,),
    )

    assert report.provisions_written == 6
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/statute/2026-06-16-nz-schedule-own-body.jsonl")
        .read_text()
        .splitlines()
    ]
    by_source_id = {
        row.get("identifiers", {}).get("legislation.govt.nz:provision")
        or row.get("identifiers", {}).get("legislation.govt.nz:element"): row
        for row in rows
    }
    schedule = by_source_id["SCHEDOWN1"]
    part = by_source_id["PART2"]
    heading_only_subpart = by_source_id["BOARDHEADING1"]
    clause = by_source_id["HEADINGCLAUSE2"]
    definition = by_source_id["SCHEDULEDEF1"]

    assert schedule["body"] == "schedule own sentinel.\nBand | Amount\nA | $10"
    assert "Accessibility metadata" not in schedule["body"]
    assert "heading descendant sentinel" not in schedule["body"]
    assert "definition descendant sentinel" not in schedule["body"]
    assert "history descendant sentinel" not in schedule["body"]
    assert definition["body"] == "own term means definition descendant sentinel."
    assert part["citation_path"].endswith("/schedule/4/part/2")
    assert heading_only_subpart["citation_path"].endswith(
        "/schedule/4/part/2/subpart/te-taumata-hauora-o-te-kahu-o-taonui"
    )
    assert heading_only_subpart["parent_citation_path"] == part["citation_path"]
    assert heading_only_subpart["heading"] == "Te Taumata Hauora o Te Kahu o Taonui"
    assert heading_only_subpart["level"] == 4
    assert "ordinal" not in heading_only_subpart
    assert clause["parent_citation_path"] == heading_only_subpart["citation_path"]
    assert clause["citation_path"].endswith(
        "/schedule/4/part/2/subpart/te-taumata-hauora-o-te-kahu-o-taonui/clause/2"
    )
    assert clause["level"] == 5


def test_extract_nz_legislation_writes_schedule_parts_and_definitions(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "schedule-rates-act-2026.xml"
    source_xml.write_text(SAMPLE_NZ_SCHEDULE_STRUCTURES_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-schedules",
        source_xmls=(source_xml,),
        source_as_of="2026-06-16",
        expression_date="2026-06-16",
    )

    assert report.provisions_written == 5
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/statute/2026-06-16-nz-schedules.jsonl")
        .read_text()
        .splitlines()
    ]
    by_path = {row["citation_path"]: row for row in rows}
    document_path = "nz/statute/act/public/2026/0003"
    schedule_path = f"{document_path}/schedule/2"
    part = by_path[f"{schedule_path}/part/1"]
    paragraph_part = by_path[f"{schedule_path}/part/a"]
    definition = by_path[f"{schedule_path}/definition/income-test-1"]

    assert by_path[schedule_path]["body"] is None
    assert by_path[schedule_path]["parent_citation_path"] == document_path
    assert part["parent_citation_path"] == schedule_path
    assert part["level"] == 3
    assert "$100" in part["body"]
    assert "heading" not in paragraph_part
    assert paragraph_part["body"] == "1\nA listed PIE.\n2\nA listed life insurer."
    assert definition["parent_citation_path"] == schedule_path
    assert definition["level"] == 3
    assert "income over $160" in definition["body"]
    assert definition["source_url"].endswith("/latest/INCOME1.html")


def test_extract_nz_legislation_excludes_inactive_elements_and_descendants(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "current-law-act-2026.xml"
    source_xml.write_text(SAMPLE_NZ_INACTIVE_CONTENT_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-current-law",
        source_xmls=(source_xml,),
    )

    assert report.provisions_written == 4
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/statute/2026-06-16-nz-current-law.jsonl")
        .read_text()
        .splitlines()
    ]
    by_path = {row["citation_path"]: row for row in rows}
    document_path = "nz/statute/act/public/2026/0004"
    section = by_path[f"{document_path}/section/1"]
    schedule_21 = by_path[f"{document_path}/schedule/21"]
    schedule_39 = by_path[f"{document_path}/schedule/39"]

    assert section["body"] == "(1) Current provision text."
    assert section["metadata"]["stage"] == "in-force"
    assert schedule_21["identifiers"]["legislation.govt.nz:element"] == "LMS199577"
    assert schedule_39["identifiers"]["legislation.govt.nz:element"] == "LMS960776"
    assert {
        row.get("identifiers", {}).get("legislation.govt.nz:provision")
        or row.get("identifiers", {}).get("legislation.govt.nz:element")
        for row in rows
    }.isdisjoint(
        {
            "REPEALEDSUB",
            "INHERITEDEXPIRED",
            "DIRECTREVOKED",
            "INHERITEDNOTINFORCE",
            "INHERITEDUNKNOWNSTAGE",
            "DLM1695100",
            "DLM3683728",
        }
    )


@pytest.mark.parametrize(
    "stage",
    (
        "not-in-force",
        "repealed",
        "draft",
        "revoked",
        "expired",
        "unknown",
    ),
)
def test_extract_nz_legislation_rejects_every_non_current_document_stage(tmp_path, stage):
    source_xml = tmp_path / "inactive-act-2026.xml"
    source_xml.write_text(
        SAMPLE_NZ_INACTIVE_CONTENT_XML.replace('stage="in-force"', f'stage="{stage}"')
    )

    with pytest.raises(ValueError, match="inactive NZ source document is not current law"):
        extract_nz_legislation(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-06-16-nz-current-law",
            source_xmls=(source_xml,),
        )


def test_extract_nz_legislation_rejects_document_deletion_status(tmp_path):
    source_xml = tmp_path / "inactive-act-2026.xml"
    source_xml.write_text(
        SAMPLE_NZ_INACTIVE_CONTENT_XML.replace(
            'stage="in-force"',
            'stage="in-force" deletion-status="expired"',
        )
    )

    with pytest.raises(ValueError, match="inactive NZ source document is not current law"):
        extract_nz_legislation(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-06-16-nz-current-law",
            source_xmls=(source_xml,),
        )


def test_nz_citation_deduplication_rejects_every_duplicate_path():
    records = (
        ProvisionRecord("nz", "statute", "nz/statute/example/1"),
        ProvisionRecord("nz", "statute", "nz/statute/example/2"),
        ProvisionRecord("nz", "statute", "nz/statute/example/1"),
        ProvisionRecord("nz", "statute", "nz/statute/example/2"),
    )
    inventory = (
        SourceInventoryItem("nz/statute/example/1"),
        SourceInventoryItem("nz/statute/example/2"),
        SourceInventoryItem("nz/statute/example/1"),
        SourceInventoryItem("nz/statute/example/2"),
    )

    with pytest.raises(
        ValueError,
        match=r"duplicate provision citation paths: nz/statute/example/1, nz/statute/example/2",
    ):
        _dedupe_records(records)
    with pytest.raises(
        ValueError,
        match=r"duplicate inventory citation paths: nz/statute/example/1, nz/statute/example/2",
    ):
        _dedupe_inventory(inventory)


def test_extract_nz_legislation_preserves_table_text_in_provision_body(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "rates-table-act-2026.xml"
    source_xml.write_text(SAMPLE_NZ_TABLE_PROVISION_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-table",
        source_xmls=(source_xml,),
    )

    assert report.provisions_written == 2
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/statute/2026-06-16-nz-table.jsonl")
        .read_text()
        .splitlines()
    ]
    row = next(row for row in rows if row["kind"] == "section")
    assert "Row | Range | Tax rate" in row["body"]
    assert "1 | $0 to $15,600 | 0.105" in row["body"]
    assert "2 | $15,601 to $53,500 | 0.175" in row["body"]


def test_extract_nz_legislation_directory_limit(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_dir = tmp_path / "pco"
    source_dir.mkdir()
    (source_dir / "a-act.xml").write_text(SAMPLE_NZ_ACT_XML)
    (source_dir / "b-regulation.xml").write_text(SAMPLE_NZ_REGULATION_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-limited",
        source_dir=source_dir,
        limit=1,
    )

    assert len(report.class_reports) == 1
    assert report.class_reports[0].document_class == "statute"


def test_nz_release_has_one_exact_row_for_every_current_pco_provision():
    converter = NZPCOConverter()
    expected: dict[str, tuple[str, str]] = {}
    expected_structural: dict[
        str,
        tuple[str, str, str | None, str | None, str, int],
    ] = {}
    nested_schedule_definition_ids: set[str] = set()
    heading_only_hierarchy_ids: set[str] = set()
    schedule_clause_count = 0
    schedule_own_body_count = 0
    duplicated_source_descendant_bodies: list[tuple[str, str]] = []

    for document_class in ("regulation", "statute"):
        source_root = REPO_ROOT / "data/corpus/sources/nz" / document_class / NZ_RELEASE_VERSION
        for source_path in sorted(source_root.rglob("*.xml")):
            current_bytes = _current_law_source_bytes(source_path.read_bytes())
            root = ET.fromstring(current_bytes)
            parents = {child: parent for parent in root.iter() for child in parent}
            fragments, schedule_paths = _schedule_hierarchy(current_bytes)
            fragments_by_id = {fragment.source_element_id: fragment for fragment in fragments}
            fragments_by_suffix = {fragment.path_suffix: fragment for fragment in fragments}
            assert len(fragments_by_id) == len(fragments)
            assert len(fragments_by_suffix) == len(fragments)
            for schedule in root.iter("schedule"):
                schedule_id = (schedule.get("id") or "").strip()
                schedule_label = " ".join((schedule.findtext("label") or "").split())
                if schedule_id and schedule_label:
                    schedule_fragment = fragments_by_id[schedule_id]
                    schedule_own_body = _structural_own_body(schedule)
                    assert schedule_fragment.body == schedule_own_body
                    schedule_own_body_count += schedule_own_body is not None
                else:
                    continue

                hierarchy_tags = {"head1", "head2", "part", "subpart"}
                for hierarchy in (
                    element for element in schedule.iter() if element.tag in hierarchy_tags
                ):
                    hierarchy_id = (hierarchy.get("id") or "").strip()
                    label = " ".join((hierarchy.findtext("label") or "").split())
                    heading = " ".join((hierarchy.findtext("heading") or "").split())
                    if hierarchy_id and not label and heading:
                        heading_only_hierarchy_ids.add(hierarchy_id)
                        fragment = fragments_by_id[hierarchy_id]
                        assert fragment.heading == heading
                        assert fragment.label == heading

                for provision in schedule.iter("prov"):
                    provision_id = (provision.get("id") or "").strip()
                    assert provision_id
                    schedule_path = schedule_paths[provision_id]
                    current = parents.get(provision)
                    expected_parent = schedule_fragment
                    while current is not None and current is not schedule:
                        current_id = (current.get("id") or "").strip()
                        if current.tag in hierarchy_tags and current_id in fragments_by_id:
                            expected_parent = fragments_by_id[current_id]
                            break
                        current = parents.get(current)
                    assert schedule_path.parent_suffix == expected_parent.path_suffix
                    assert schedule_path.level == expected_parent.level + 1

                for definition in schedule.iter("def-para"):
                    current = parents.get(definition)
                    while current is not None and current is not schedule:
                        if current.tag == "prov":
                            definition_id = definition.get("id")
                            assert definition_id
                            nested_schedule_definition_ids.add(definition_id)
                            break
                        current = parents.get(current)
            legislation = converter.parse_xml(current_bytes.decode())
            source_name = source_path.relative_to(source_root).as_posix()
            _apply_source_name_metadata(legislation, source_name)
            _assign_schedule_provision_paths(legislation, current_bytes)
            document_path = _parent_citation_path(legislation)
            for fragment in fragments:
                assert fragment.source_element_id not in expected_structural
                parent_path = (
                    f"{document_path}/{fragment.parent_suffix}"
                    if fragment.parent_suffix
                    else document_path
                )
                expected_structural[fragment.source_element_id] = (
                    f"{document_path}/{fragment.path_suffix}",
                    parent_path,
                    fragment.body,
                    fragment.heading,
                    fragment.kind,
                    fragment.level,
                )
                if fragment.kind == "definition" or not fragment.body or not fragment.parent_suffix:
                    continue
                ancestor_suffix: str | None = fragment.parent_suffix
                while ancestor_suffix:
                    ancestor = fragments_by_suffix[ancestor_suffix]
                    if ancestor.body and fragment.body in ancestor.body:
                        duplicated_source_descendant_bodies.append(
                            (ancestor.path_suffix, fragment.path_suffix)
                        )
                    ancestor_suffix = ancestor.parent_suffix
            for provision in legislation.provisions:
                assert provision.id not in expected
                expected[provision.id] = (
                    nz_citation_path(legislation, provision),
                    provision.text,
                )
                schedule_clause_count += provision.corpus_kind == "clause"
                schedule_path = schedule_paths.get(provision.id)
                if schedule_path is None or not provision.text:
                    continue
                ancestor_suffix: str | None = schedule_path.parent_suffix
                while ancestor_suffix:
                    ancestor = fragments_by_suffix[ancestor_suffix]
                    if ancestor.body and provision.text in ancestor.body:
                        duplicated_source_descendant_bodies.append(
                            (ancestor.path_suffix, schedule_path.path_suffix)
                        )
                    ancestor_suffix = ancestor.parent_suffix

    actual: dict[str, dict] = {}
    actual_structural: dict[str, dict] = {}
    all_rows: dict[str, dict] = {}
    emitted_definition_ids: set[str] = set()
    for document_class in ("regulation", "statute"):
        artifact = (
            REPO_ROOT / "data/corpus/provisions/nz" / document_class / f"{NZ_RELEASE_VERSION}.jsonl"
        )
        for line in artifact.read_text().splitlines():
            row = json.loads(line)
            assert row["citation_path"] not in all_rows
            all_rows[row["citation_path"]] = row
            provision_id = row.get("identifiers", {}).get("legislation.govt.nz:provision")
            if provision_id:
                assert provision_id not in actual
                actual[provision_id] = row
            element_id = row.get("identifiers", {}).get("legislation.govt.nz:element")
            if element_id:
                assert element_id not in actual_structural
                actual_structural[element_id] = row
            if row["kind"] == "definition":
                emitted_definition_ids.add(row["identifiers"]["legislation.govt.nz:element"])

    assert schedule_clause_count == 1_283
    assert schedule_own_body_count == 71
    assert len(heading_only_hierarchy_ids) == 16
    assert len(expected_structural) == 907
    assert duplicated_source_descendant_bodies == []
    assert len(nested_schedule_definition_ids) == 344
    assert len(emitted_definition_ids) == 413
    assert emitted_definition_ids.isdisjoint(nested_schedule_definition_ids)
    assert set(actual) == set(expected)
    assert set(actual_structural) == set(expected_structural)
    assert len({row["citation_path"] for row in actual.values()}) == len(actual)
    for provision_id, (citation_path, rendered_body) in expected.items():
        row = actual[provision_id]
        assert row["citation_path"] == citation_path
        assert row.get("body", "") == rendered_body
    for element_id, (
        citation_path,
        parent_path,
        body,
        heading,
        kind,
        level,
    ) in expected_structural.items():
        row = actual_structural[element_id]
        assert row["citation_path"] == citation_path
        assert row["parent_citation_path"] == parent_path
        assert row.get("body") == body
        assert row.get("heading") == heading
        assert row["kind"] == kind
        assert row["level"] == level

    duplicated_parent_child_bodies: list[tuple[str, str]] = []
    duplicated_descendant_ancestor_bodies: list[tuple[str, str]] = []
    for child_path, child in all_rows.items():
        parent_path = child.get("parent_citation_path")
        parent = all_rows.get(parent_path)
        if parent is None or parent["kind"] not in {"part", "schedule", "subpart"}:
            continue
        child_body = child.get("body")
        parent_body = parent.get("body")
        if (
            child["kind"] != "definition"
            and child_body
            and parent_body
            and child_body in parent_body
        ):
            duplicated_parent_child_bodies.append((parent_path, child_path))
        if child["kind"] != "clause" or not child_body:
            continue
        ancestor_path = parent_path
        while ancestor_path:
            ancestor = all_rows.get(ancestor_path)
            if ancestor is None:
                break
            ancestor_body = ancestor.get("body")
            if ancestor_body and child_body in ancestor_body:
                duplicated_descendant_ancestor_bodies.append(
                    (ancestor["citation_path"], child_path)
                )
            ancestor_path = ancestor.get("parent_citation_path")
    assert duplicated_parent_child_bodies == []
    assert duplicated_descendant_ancestor_bodies == []

    assert {
        provision_id: actual[provision_id]["citation_path"]
        for provision_id in {
            "DLM104829",
            "DLM104891",
            "DLM1523194",
            "DLM6784845",
            "LMS813367",
            "LMS1588497",
        }
    } == {
        "DLM104829": ("nz/statute/act/public/2001/0049/schedule/1/part/2/clause/32"),
        "DLM104891": ("nz/statute/act/public/2001/0049/schedule/1/part/2/clause/47"),
        "DLM1523194": ("nz/statute/act/public/2007/0097/schedule/1/part/a/clause/1"),
        "DLM6784845": ("nz/statute/act/public/2018/0032/schedule/3/part/5/clause/19"),
        "LMS813367": (
            "nz/statute/act/public/2022/0030/schedule/4/part/2/"
            "subpart/te-taumata-hauora-o-te-kahu-o-taonui/clause/2"
        ),
        "LMS1588497": ("nz/regulation/regulation/public/1998/0277/schedule/2/part/2/clause/4"),
    }
