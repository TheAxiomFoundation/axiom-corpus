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
<P><SPAN STYLE="font-family: Public Sans">Gift Tax</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans"><STRONG>ARTICLE 25</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">Gift Tax</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">Editor's note: This article was approved by voters.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">The vote count was 100 FOR and 50 AGAINST.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">39-25-101 to 39-25-120. (Repealed)</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">Source: L. 2003: Entire article repealed, p. 2003, \u00a7 69, effective May 22.</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">CHIPS Zone Act</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans"><STRONG>ARTICLE 36</STRONG></SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">CHIPS Zone Act</SPAN></P>
<P><SPAN STYLE="font-family: Public Sans">\t<STRONG>39-36-101.  Definitions. </STRONG>As used in this article 36, "zone" means a designated area.</SPAN></P>
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


def test_parse_colorado_crs_title_captures_repealed_range_articles() -> None:
    sections, _ = parse_colorado_crs_title(_fixture_bytes(), title="39", only_article="25")
    assert len(sections) == 1
    record = sections[0]
    assert record.section == "39-25-101"
    assert record.heading == "39-25-101 to 39-25-120. (Repealed)"
    assert record.article == "25"
    assert record.body_paragraphs == []
    assert record.is_repealed_range
    assert any("Entire article repealed" in h for h in record.source_history)
    # Pre-range editor's note (printed before the ranged heading) belongs to
    # the ranged record, including its unlabeled continuation paragraph.
    assert any("approved by voters" in n for n in record.source_notes)
    assert any("100 FOR and 50 AGAINST" in n for n in record.source_notes)
    # The next article's caption never becomes the ranged record's body.
    assert not any("CHIPS" in b for b in record.body_paragraphs)


def test_parse_colorado_crs_title_section_after_repealed_range_article() -> None:
    sections, _ = parse_colorado_crs_title(_fixture_bytes(), title="39", only_article="36")
    assert [s.section for s in sections] == ["39-36-101"]
    assert sections[0].body.startswith('As used in this article 36')


def test_parse_colorado_crs_title_keeps_pre_article_caption_out_of_annex() -> None:
    sections, _ = parse_colorado_crs_title(_fixture_bytes(), title="39")
    by_number = {section.section: section for section in sections}
    last_before_caption = by_number[max(
        s for s in by_number if not s.startswith("39-25")
    )]
    assert not any("Gift Tax" in h for h in last_before_caption.source_history)
    assert not any("Gift Tax" in n for n in last_before_caption.source_notes)


def test_parse_colorado_crs_title_scopes_to_comma_separated_articles() -> None:
    single, _ = parse_colorado_crs_title(_fixture_bytes(), title="39", only_article="21")
    assert {section.article for section in single} == {"21"}

    combined, _ = parse_colorado_crs_title(
        _fixture_bytes(), title="39", only_article=" 21, ,22,, "
    )
    articles = {section.article for section in combined}
    assert articles == {"21", "22"}
    assert len(combined) > len(single)


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
