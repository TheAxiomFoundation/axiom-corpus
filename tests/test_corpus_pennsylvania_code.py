from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.pennsylvania_code import extract_pennsylvania_code


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_pennsylvania_code_sources(source_dir: Path) -> None:
    _write(
        source_dir / "pennsylvania-code" / "index.html",
        """<html><body>
<select id="codeTitleSelected">
<option value="Select a Title">Select a Title</option>
<option value="/001/001toc.html">1&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;GENERAL PROVISIONS</option>
</select>
<p>The <em><strong>Pennsylvania Code</strong></em> website reflects the
<em>Pennsylvania Code</em> changes effective through 56 Pa.B. 1270 (February 28, 2026).</p>
</body></html>
""",
    )
    _write(
        source_dir / "pennsylvania-code" / "001" / "001toc.html",
        """<html><body><blockquote>
<br/>&nbsp;<FONT SIZE=+1>PART I. <a href="partItoc.html">Joint Committee on Documents</FONT></a>
<br/>&nbsp;&nbsp;&nbsp;&nbsp;<FONT SIZE=+1>Chapter 0. <a href="chapter0/chap0toc.html">[Reserved]</FONT></a>
<br/>&nbsp;&nbsp;&nbsp;&nbsp;<FONT SIZE=+1>Chapter 1. <a href="chapter1/chap1toc.html">Preliminary Provisions</FONT></a>
</blockquote></body></html>
""",
    )
    _write(
        source_dir / "pennsylvania-code" / "001" / "chapter1" / "chap1toc.html",
        """<html><head>
<meta name="title" content="001">
<meta name="chapter" content="0001">
</head><body><blockquote>
<BR><H1><CENTER>CHAPTER 1.&nbsp;PRELIMINARY PROVISIONS</CENTER></H1>
<P><CENTER><B>Authority</B></CENTER></P>
<P>&nbsp;&nbsp;&nbsp;The provisions of this Chapter 1 issued under 45 Pa.C.S. § 701.</P>
<P><CENTER><B>Source</B></CENTER></P>
<P>&nbsp;&nbsp;&nbsp;The provisions of this Chapter 1 adopted by JCD Order No. 4.</P>
<!--sectbreak;t001;c0001;s1.1-->
<A NAME="1.1."><H4><FONT SIZE=+1>&#167;&nbsp;1.1.&nbsp;</FONT>Title of official legal codification.</H4>
<P>&nbsp;The official legal codification shall be known as the <I>Pennsylvania Code</I>.</P>
<!--sectbreak;t001;c0001;s1.2-->
<A NAME="1.2."><H4><FONT SIZE=+1>&#167;&nbsp;1.2.&nbsp;</FONT>Citation of <B><I>Code</B></I><B>.</B></H4>
<P>&nbsp;The approved short form is "Pa. Code." This section cited in 1 Pa. Code § 1.1.</P>
</blockquote></body></html>
""",
    )


def test_extract_pennsylvania_code_local_sources_writes_records(tmp_path):
    source_dir = tmp_path / "pa-source"
    _write_pennsylvania_code_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_pennsylvania_code(
        store,
        version="2026-05-18",
        source_dir=source_dir,
        only_title="1",
        workers=1,
    )

    assert report.coverage.complete
    assert report.title_count == 1
    assert report.chapter_count == 1
    assert report.reserved_chapter_count == 1
    assert report.section_count == 2
    assert report.provisions_written == 5
    assert report.skipped_source_count == 0
    assert report.errors == ()

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-pa/regulation",
        "us-pa/regulation/title-1",
        "us-pa/regulation/title-1/chapter-1",
        "us-pa/regulation/title-1/chapter-1/section-1-1",
        "us-pa/regulation/title-1/chapter-1/section-1-2",
    ]
    root = records[0]
    assert root.metadata is not None
    assert root.metadata["effective_through"] == "56 Pa.B. 1270 (February 28, 2026)."
    title = records[1]
    assert title.metadata is not None
    assert title.metadata["reserved_chapter_count"] == 1
    assert title.metadata["reserved_chapters"] == ["0"]
    chapter = records[2]
    assert chapter.body is not None
    assert "Authority: The provisions of this Chapter 1 issued" in chapter.body
    section = records[-1]
    assert section.heading == "Citation of Code ."
    assert section.citation_label == "1 Pa. Code § 1.2"
    assert section.metadata is not None
    assert section.metadata["references_to"] == [
        "us-pa/regulation/title-1/section-1-1"
    ]

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    assert inventory[-1].source_format == "pennsylvania-code-html"


def test_extract_pennsylvania_code_cli_local_sources(tmp_path, capsys):
    source_dir = tmp_path / "pa-source"
    _write_pennsylvania_code_sources(source_dir)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-pennsylvania-code",
            "--base",
            str(base),
            "--version",
            "2026-05-18",
            "--source-dir",
            str(source_dir),
            "--only-title",
            "1",
            "--workers",
            "1",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"jurisdiction": "us-pa"' in out
    assert '"title_count": 1' in out
    assert '"chapter_count": 1' in out
    assert '"reserved_chapter_count": 1' in out
    assert '"section_count": 2' in out
    assert '"coverage_complete": true' in out
