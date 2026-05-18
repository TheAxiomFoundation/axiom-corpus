from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.maryland_comar import extract_maryland_comar


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_comar_sources(source_dir: Path) -> None:
    ns = 'xmlns="https://open.law/schemas/library" xmlns:xi="http://www.w3.org/2001/XInclude"'
    _write(
        source_dir / "index.xml",
        f"""<?xml version="1.0" encoding="utf-8"?>
<library {ns}>
  <heading>Library of Maryland Regulations</heading>
  <meta>
    <build><build-date>2026-05-14</build-date></build>
  </meta>
  <xi:include href="./us/md/exec/comar/index.xml"/>
</library>
""",
    )
    _write(source_dir / "license.md", "CC-BY-SA 4.0\n")
    _write(
        source_dir / "us/md/exec/comar/index.xml",
        f"""<?xml version="1.0" encoding="utf-8"?>
<document {ns} id="Code of Maryland Regulations">
  <heading>Code of Maryland Regulations</heading>
  <xi:include href="./01/index.xml"/>
</document>
""",
    )
    _write(
        source_dir / "us/md/exec/comar/01/index.xml",
        f"""<?xml version="1.0" encoding="utf-8"?>
<container {ns}>
  <prefix>Title</prefix>
  <num>01</num>
  <heading>EXECUTIVE DEPARTMENT</heading>
  <xi:include href="./02/index.xml"/>
</container>
""",
    )
    _write(
        source_dir / "us/md/exec/comar/01/02/index.xml",
        f"""<?xml version="1.0" encoding="utf-8"?>
<container {ns}>
  <prefix>Subtitle</prefix>
  <num>02</num>
  <heading>SECRETARY OF STATE</heading>
  <xi:include href="./03.xml"/>
</container>
""",
    )
    _write(
        source_dir / "us/md/exec/comar/01/02/03.xml",
        f"""<?xml version="1.0" encoding="utf-8"?>
<container {ns}>
  <prefix>Chapter</prefix>
  <num>03</num>
  <heading>Charitable Organizations: Procedural Regulations</heading>
  <section>
    <prefix>Regulation</prefix>
    <num>.01</num>
    <heading>Scope.</heading>
    <text>These regulations apply to hearings under <cite doc="Md. Code" path="gbr|6-205">Business Regulation Article, Section 6-205</cite>.</text>
    <para>
      <num>A.</num>
      <text>Who May File. Any interested person may file a petition.</text>
      <para>
        <num>(1)</num>
        <text>The petition shall be in writing.</text>
      </para>
    </para>
    <text>
      <table>
        <tbody>
          <tr><th>Term</th><th>Meaning</th></tr>
          <tr><td>COMAR</td><td>Code of Maryland Regulations</td></tr>
        </tbody>
      </table>
    </text>
    <annotations>
      <annotation type="History" effective="2020-01-01">Effective date: January 1, 2020.</annotation>
    </annotations>
  </section>
  <section>
    <prefix>Regulation</prefix>
    <num>.02</num>
    <heading>Definitions.</heading>
    <text>See <cite path="|01|02|03|.01">Regulation .01</cite>.</text>
    <annotations/>
  </section>
</container>
""",
    )


def test_extract_maryland_comar_local_sources_writes_records(tmp_path):
    source_dir = tmp_path / "comar-source"
    _write_comar_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_maryland_comar(
        store,
        version="2026-05-18",
        source_dir=source_dir,
        only_title="01",
        only_subtitle="02",
        only_chapter="03",
        limit=1,
    )

    assert report.coverage.complete
    assert report.title_count == 1
    assert report.subtitle_count == 1
    assert report.chapter_count == 1
    assert report.regulation_count == 1
    assert report.provisions_written == 5

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-md/regulation",
        "us-md/regulation/title-01",
        "us-md/regulation/title-01/subtitle-02",
        "us-md/regulation/title-01/subtitle-02/chapter-03",
        "us-md/regulation/title-01/subtitle-02/chapter-03/regulation-01",
    ]
    section = records[-1]
    assert section.heading == "COMAR 01.02.03.01. Scope."
    assert section.citation_label == "COMAR 01.02.03.01"
    assert section.body is not None
    assert "A. Who May File." in section.body
    assert "(1) The petition shall be in writing." in section.body
    assert "Term | Meaning" in section.body
    assert section.source_as_of == "2026-05-14"
    assert section.expression_date == "2026-05-14"
    assert section.metadata is not None
    assert section.metadata["references_to"] == ["us-md/statute/gbr/6-205"]
    assert section.metadata["annotations"][0]["type"] == "History"

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    assert inventory[-1].source_format == "maryland-comar-openlaw-xml"


def test_extract_maryland_comar_cli_local_sources(tmp_path, capsys):
    source_dir = tmp_path / "comar-source"
    _write_comar_sources(source_dir)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-maryland-comar",
            "--base",
            str(base),
            "--version",
            "2026-05-18",
            "--source-dir",
            str(source_dir),
            "--only-title",
            "01",
            "--only-subtitle",
            "02",
            "--only-chapter",
            "03",
            "--limit",
            "1",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"jurisdiction": "us-md"' in out
    assert '"regulation_count": 1' in out
    assert '"coverage_complete": true' in out
