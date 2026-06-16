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
