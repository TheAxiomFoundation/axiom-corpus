from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.illinois_admin_code import extract_illinois_admin_code
from axiom_corpus.corpus.io import load_provisions, load_source_inventory


def _write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def _write_illinois_sources(source_dir: Path) -> None:
    _write(
        source_dir / "titles.html",
        """<html><body>
<table><tr><td class="content"><b>Disclaimer:</b>This site provides access to the Illinois Administrative Code database that is maintained and updated weekly by the Illinois General Assembly. This database is NOT the "official" text of the Illinois Administrative Code.</td></tr></table>
<ul>
<li><a href='001/001parts.html' class='links'>TITLE 1: GENERAL PROVISIONS</a></li>
</ul>
</body></html>
""",
    )
    _write(
        source_dir / "001/index.html",
        """<html><body><pre><A HREF="/ftp/JCAR/AdminCode/">[To Parent Directory]</A><br><br>
 4/14/2023 11:00 PM         2450 <A HREF="/ftp/JCAR/AdminCode/001/001001000A01000R.html">001001000A01000R.html</A><br>
11/08/2025 12:00 AM         6400 <A HREF="/ftp/JCAR/AdminCode/001/00100100ZZ9996aaR.html">00100100ZZ9996aaR.html</A><br>
</pre></body></html>
""",
    )
    _write(
        source_dir / "001/001001000A01000R.html",
        """<html>
<head>
<meta name="sectionname" content="Section 100.100  Rulemaking Compliance">
</head>
<body><table><tr><td><div align="center" class="heading">TITLE 1: GENERAL PROVISIONS<br>CHAPTER I: SECRETARY OF STATE<br>PART 100<br>RULEMAKING IN ILLINOIS<br>SECTION 100.100 RULEMAKING COMPLIANCE</div><br>
<hr>
<div>
<p class=MsoNormal>&nbsp;</p>
<p class=MsoNormal><b>Section 100.100 Rulemaking Compliance</b></p>
<p class=MsoNormal>This Part describes rulemaking under 5 ILCS 100/1-1 and 1 Ill. Adm. Code 100.110.</p>
<table><tr><th>Term</th><th>Meaning</th></tr><tr><td>IAC</td><td>Illinois Administrative Code</td></tr></table>
<p class=JCARSourceNote>(Source: Amended at 18 Ill. Reg. 13067, effective August 11, 1994)</p>
<img src="001001000A01000R_files/image001.png">
</div>
</td></tr></table></body></html>
""",
    )
    _write(source_dir / "001/001001000A01000R_files/image001.png", b"png")
    _write(
        source_dir / "001/00100100ZZ9996aaR.html",
        """<html>
<head>
<meta name="sectionname" content="Section 100.APPENDIX A   Proposed Rules">
</head>
<body><table><tr><td><div align="center" class="heading">ADMINISTRATIVE CODE</div><div align="center" class="heading">TITLE 1: GENERAL PROVISIONS<br>CHAPTER I: SECRETARY OF STATE<br>PART 100 RULEMAKING IN ILLINOIS<br>SECTION 100.APPENDIX A PROPOSED RULES</div><br>
<hr>
<div>
<p class=MsoNormal><b>Section 100.APPENDIX A Proposed Rules</b></p>
<p class=MsoNormal>For detailed information on this notice, refer to Section 100.410.</p>
</div>
</td></tr></table></body></html>
""",
    )


def test_extract_illinois_admin_code_local_sources_writes_records(tmp_path):
    source_dir = tmp_path / "illinois-source"
    _write_illinois_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_illinois_admin_code(
        store,
        version="2026-05-18",
        source_dir=source_dir,
        only_title="1",
        workers=1,
    )

    assert report.coverage.complete
    assert report.title_count == 1
    assert report.subtitle_count == 0
    assert report.chapter_count == 1
    assert report.part_count == 1
    assert report.section_count == 1
    assert report.appendix_count == 1
    assert report.provisions_written == 6

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-il/regulation",
        "us-il/regulation/title-001",
        "us-il/regulation/title-001/chapter-i",
        "us-il/regulation/title-001/chapter-i/part-100",
        "us-il/regulation/title-001/chapter-i/part-100/section-100-100",
        "us-il/regulation/title-001/chapter-i/part-100/appendix-100-a",
    ]
    section = records[-2]
    assert section.heading == "1 Ill. Adm. Code 100.100. RULEMAKING COMPLIANCE"
    assert section.citation_label == "1 Ill. Adm. Code 100.100"
    assert section.body is not None
    assert "5 ILCS 100/1-1" in section.body
    assert "Term | Meaning" in section.body
    assert section.source_as_of == "2023-04-14"
    assert section.metadata is not None
    assert section.metadata["references_to_labels"] == [
        "1 Ill. Adm. Code 100.110",
        "5 ILCS 100/1-1",
    ]
    assert "not the certified official text" in section.metadata["source_note"]

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    assert inventory[-1].source_format == "illinois-admin-code-html"
    assert any("image001.png" in str(path) for path in report.source_paths)


def test_extract_illinois_admin_code_cli_local_sources(tmp_path, capsys):
    source_dir = tmp_path / "illinois-source"
    _write_illinois_sources(source_dir)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-illinois-admin-code",
            "--base",
            str(base),
            "--version",
            "2026-05-18",
            "--source-dir",
            str(source_dir),
            "--only-title",
            "001",
            "--workers",
            "1",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"jurisdiction": "us-il"' in out
    assert '"section_count": 1' in out
    assert '"appendix_count": 1' in out
    assert '"coverage_complete": true' in out
