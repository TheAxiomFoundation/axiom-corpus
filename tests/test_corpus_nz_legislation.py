import json

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.nz_legislation import extract_nz_legislation

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

    assert report.source_count == 3
    assert report.provisions_written == 3
    class_report = report.class_reports[0]
    assert class_report.document_class == "statute"
    assert class_report.coverage.complete
    assert len(class_report.source_paths) == 1
    assert class_report.source_paths[0].exists()

    provisions_path = base / "provisions/nz/statute/2026-06-16-nz-income-tax.jsonl"
    rows = [json.loads(line) for line in provisions_path.read_text().splitlines()]
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
    assert section_1["ordinal"] == 1
    assert section_1["expression_date"] == "2026-04-01"
    assert "(1) This Act is the Income Tax Act 2007." in section_1["body"]
    assert "(2) This Act comes into force on 1 April 2008." in section_1["body"]
    assert section_1["metadata"]["administering_ministry"] == "Inland Revenue"

    inventory = json.loads(
        (base / "inventory/nz/statute/2026-06-16-nz-income-tax.json").read_text()
    )
    assert len(inventory["items"]) == 3
    assert inventory["items"][0]["source_format"] == "legislation.govt.nz-pco-xml"


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

    assert report.provisions_written == 2
    class_report = report.class_reports[0]
    assert class_report.document_class == "regulation"
    assert len(class_report.source_paths) == 2

    rows = [
        json.loads(line)
        for line in (
            base / "provisions/nz/regulation/2026-06-16-nz-legislation.jsonl"
        ).read_text().splitlines()
    ]
    assert {row["citation_path"] for row in rows} == {
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
    } == {row["source_path"] for row in rows}
    assert any(
        row["source_url"]
        == "https://www.legislation.govt.nz/secondary-legislation/pco-drafted/2013/135/latest/SR135P1.html"
        for row in rows
    )


def test_extract_nz_legislation_preserves_alphanumeric_api_number_tokens(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_dir = tmp_path / "pco"
    source_xml = (
        source_dir
        / "bill/government/2013/150-B"
        / "bill_government_2013_150-B_en_2014-06-17.xml"
    )
    source_xml.parent.mkdir(parents=True)
    source_xml.write_text(SAMPLE_NZ_SPLIT_BILL_XML)

    report = extract_nz_legislation(
        CorpusArtifactStore(base),
        version="2026-06-16-nz-legislation",
        source_dir=source_dir,
    )

    assert report.provisions_written == 1
    row = json.loads(
        (base / "provisions/nz/rulemaking/2026-06-16-nz-legislation.jsonl")
        .read_text()
        .strip()
    )
    assert row["citation_path"] == "nz/rulemaking/bill/government/2013/150-B/clause/1"
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

    assert report.provisions_written == 3
    rows = [
        json.loads(line)
        for line in (base / "provisions/nz/statute/2026-06-16-nz-nested.jsonl")
        .read_text()
        .splitlines()
    ]
    assert {row["citation_path"] for row in rows} == {
        "nz/statute/act/public/2026/0001/section/1-BODY1",
        "nz/statute/act/public/2026/0001/section/3",
        "nz/statute/act/public/2026/0001/section/1-SCHED1CLAUSE1",
    }
    assert {row["metadata"]["provision_path_token"] for row in rows} == {
        "1-BODY1",
        "3",
        "1-SCHED1CLAUSE1",
    }


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
