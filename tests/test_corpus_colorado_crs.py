"""Tests for the Colorado Revised Statutes OLLS title adapter."""

from __future__ import annotations

import json
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.state_adapters.colorado_crs import (
    extract_colorado_revised_statutes,
    parse_colorado_crs_title,
)

_FIXTURE_HTML = """<HTML>
<HEAD>
<META NAME="Generator" CONTENT="WordPerfect">
<TITLE>Colorado Revised Statutes 2025 Title 39 Taxation</TITLE>
</HEAD>
<BODY>
<H1><SPAN STYLE="font-family: Public Sans">Colorado Revised Statutes 2025 Title 39 Taxation</SPAN></H1>
<P><SPAN STYLE="font-family: Public Sans"><STRONG>ARTICLE 21</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">Procedure and Administration</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>39-21-101.  Application. </STRONG>This article applies to taxes imposed under article 22.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans"><STRONG>Income Tax</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans"><STRONG>ARTICLE 22</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">Income Tax</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>Editor's note:</STRONG> This article was numbered as article 1 of chapter 138, C.R.S. 1963.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans"><STRONG>PART 1</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">GENERAL</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>39-22-101.  Short title. </STRONG>This article shall be known and may be cited as the Colorado Income Tax Act of 1987.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>Source:</STRONG> <STRONG>L. 87:</STRONG> Entire part R&amp;RE, p. 1426, \xa7 2, effective June 22.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>39-22-103.5.  Resident individual - definition. (Repealed)</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>Source:</STRONG> <STRONG>L. 92:</STRONG> Entire section repealed, p. 2262, \xa7 1, effective April 16.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>39-22-104.  Income tax imposed on individuals. </STRONG>(1) A tax is imposed per section 63 of the internal revenue code.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t(2)  The rate is set under subsection (1) of this section.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>Source:</STRONG> <STRONG>L. 87:</STRONG> Entire part R&amp;RE, p. 1427, \xa7 2, effective June 22.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>Editor's note:</STRONG> (1) This section is similar to former \xa7 39-22-104.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t(2) Subsection (2) provisions apply per session law.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>Cross references:</STRONG> (1) For the legislative declaration, see section 1 of chapter 42.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t(2) For the short title, see section 39-22-101.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t(3) For federal conformity, see 26 U.S.C. sec. 63.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans"><STRONG>ANNOTATION</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">Law reviews. For article, see 15 Colo. Law. 1.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">Annotator's case summary that must not enter the body.</SPAN></P>
</BODY>
</HTML>
"""


def _fixture_bytes() -> bytes:
    return _FIXTURE_HTML.encode("cp1252")


def test_parse_colorado_crs_title_sections_and_scoping() -> None:
    sections, document_heading = parse_colorado_crs_title(
        _fixture_bytes(), title="39", only_article="22"
    )
    assert document_heading == "Colorado Revised Statutes 2025 Title 39 Taxation"
    numbers = [section.section for section in sections]
    assert numbers == ["39-22-101", "39-22-103.5", "39-22-104"]

    by_number = {section.section: section for section in sections}
    short_title = by_number["39-22-101"]
    assert short_title.heading == "Short title"
    assert "Colorado Income Tax Act of 1987" in short_title.body
    assert short_title.part_heading == "PART 1 - GENERAL"
    assert short_title.source_history == [
        "L. 87: Entire part R&RE, p. 1426, § 2, effective June 22."
    ]

    repealed = by_number["39-22-103.5"]
    assert repealed.repealed
    assert repealed.body == ""

    imposed = by_number["39-22-104"]
    assert imposed.body.splitlines()[0].startswith("(1) A tax is imposed")
    assert "(2) The rate is set" in imposed.body
    assert "Annotator's case summary" not in imposed.body
    assert imposed.annotation_paragraphs >= 1
    assert any("similar to former" in note for note in imposed.source_notes)
    # Multi-paragraph annex blocks: unlabeled continuations of an editor's
    # note or cross-references block must land in metadata, never the body.
    assert imposed.body.rstrip().endswith("subsection (1) of this section.")
    assert "legislative declaration" not in imposed.body
    assert "For the short title" not in imposed.body
    assert "session law" not in imposed.body
    assert any("For the short title" in note for note in imposed.source_notes)
    assert any("federal conformity" in note for note in imposed.source_notes)
    assert any("session law" in note for note in imposed.source_notes)


def test_parse_colorado_crs_title_unscoped_includes_other_articles() -> None:
    sections, _ = parse_colorado_crs_title(_fixture_bytes(), title="39")
    numbers = {section.section for section in sections}
    assert "39-21-101" in numbers
    assert "39-22-104" in numbers


def test_extract_colorado_revised_statutes_writes_complete_artifacts(
    tmp_path: Path,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    (download_dir / "crs2025-title-39.htm").write_bytes(_fixture_bytes())
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_colorado_revised_statutes(
        store,
        version="2026-07-12-crs-2025-title-39-article-22",
        title="39",
        edition="2025",
        source_as_of="2026-07-12",
        expression_date="2025-08-31",
        only_article="22",
        download_dir=download_dir,
    )

    assert report.jurisdiction == "us-co"
    assert report.section_count == 3
    assert report.provisions_written == 5
    assert report.coverage.complete
    assert not report.errors

    rows = [json.loads(line) for line in Path(report.provisions_path).read_text().splitlines()]
    by_path = {row["citation_path"]: row for row in rows}
    assert set(by_path) == {
        "us-co/statute",
        "us-co/statute/39",
        "us-co/statute/39/39-22-101",
        "us-co/statute/39/39-22-103.5",
        "us-co/statute/39/39-22-104",
    }
    section = by_path["us-co/statute/39/39-22-104"]
    assert section["parent_citation_path"] == "us-co/statute/39"
    assert section["kind"] == "section"
    assert section["legal_identifier"] == "C.R.S. § 39-22-104"
    assert section["metadata"]["article"] == "22"
    assert by_path["us-co/statute/39/39-22-103.5"]["metadata"]["status"] == "repealed"
    assert by_path["us-co/statute/39"]["parent_citation_path"] == "us-co/statute"
