from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.south_carolina import (
    SOUTH_CAROLINA_SOURCE_FORMAT,
    SouthCarolinaSection,
    apply_south_carolina_session_law_overlay,
    extract_south_carolina_code,
    parse_south_carolina_chapter_html,
    parse_south_carolina_master_index_html,
    parse_south_carolina_session_law_overlay,
    parse_south_carolina_title_html,
)

SAMPLE_MASTER_HTML = """<!doctype html>
<html>
<body>
<a href="/code/title11.php">Title 11</a> - Public Finance</span><br />
<a href="/code/title12.php">Title 12</a> - Taxation</span><br />
</body>
</html>
"""

SAMPLE_TITLE_HTML = """<!doctype html>
<html>
<body>
<table>
<tr>
  <td>CHAPTER 6 - SOUTH CAROLINA INCOME TAX ACT</td>
  <td><a href="/code/t12c006.php">HTML</a></td>
  <td><a href="/getfile.php?TYPE=CODEOFLAWS&amp;TITLE=12&amp;CHAPTER=6">Word</a></td>
</tr>
<tr>
  <td>CHAPTER 8 - INCOME TAX WITHHOLDING</td>
  <td><a href="/code/t12c008.php">HTML</a></td>
  <td><a href="/getfile.php?TYPE=CODEOFLAWS&amp;TITLE=12&amp;CHAPTER=8">Word</a></td>
</tr>
</table>
</body>
</html>
"""

SAMPLE_CHAPTER_HTML = """<!doctype html>
<html>
<body>
<div style="text-align: center;">CHAPTER 6</div>
<div style="text-align: center;">South Carolina Income Tax Act</div><br />
<div style="text-align: center;">ARTICLE 1</div>
<div style="text-align: center;">Adoption of Internal Revenue Code-Definitions</div><br />
<span style="font-weight: bold;"> SECTION 12-6-10.</span> Short title.<br /><br />
This chapter may be cited as the "South Carolina Income Tax Act".<br /><br />
HISTORY: 1995 Act No. 76, SECTION 1.<br /><br />
<span style="font-weight: bold;"> SECTION 12-6-20.</span> Administration and enforcement of chapter.<br /><br />
The department shall administer and enforce this chapter under Section 12-6-10.<br /><br />
HISTORY: 1995 Act No. 76, SECTION 1.<br /><br />
<div style="text-align: center;">ARTICLE 5</div>
<div style="text-align: center;">Tax Rates and Imposition</div><br />
<span style="font-weight: bold;"> SECTION 12-6-510.</span> Tax rates.<br /><br />
(A) A tax is imposed at these rates:<br /><br />
<table>
<tr><th>Bracket</th><th>Rate</th></tr>
<tr><td>Not over $2,220</td><td>2.5 percent</td></tr>
</table>
HISTORY: 1995 Act No. 76, SECTION 1.<br /><br />
</body>
</html>
"""

SAMPLE_REPEALED_CHAPTER_HTML = """<!doctype html>
<html>
<body>
<div style="text-align: center;">CHAPTER 23</div>
<div style="text-align: center;">Zoning and Planning [Repealed]</div><br />
Editor's Note<br /><br />
This Chapter, which included SECTIONS 5-23-10 to 5-23-190, was repealed.<br /><br />
South Carolina Legislative Services Agency * 223 Blatt Building
</body>
</html>
"""

SAMPLE_SESSION_LAW_HTML = """<!doctype html>
<html><body>
<p>(A110, R117, H4216)</p>
<p>SECTION 1. Section 12-6-510(C) of the S.C. Code is amended to read:</p>
<p>(C)(1) For taxable years beginning after 2025, tax is imposed as follows:</p>
<p>$0 $30,000 1.99% times the amount</p>
<p>$30,000 or more 5.21% times the amount minus $966</p>
<p>(D) The department may prescribe tax tables consistent with this section.</p>
<p>SECTION 2. Section 12-6-50 of the S.C. Code is amended by adding:</p>
<p>(21) Section 63(b) through (g) relating to standard deductions and the itemized deduction are not adopted.</p>
<p>SECTION 3. Section 12-6-1140 of the S.C. Code is amended by adding:</p>
<p>(15)(a) A South Carolina Income Adjusted Deduction equal to twenty-two thousand five hundred dollars for head of household filers.</p>
<p>(b) The numerator is the amount federal adjusted gross income exceeds sixty thousand dollars and the denominator is eighty-two thousand five hundred.</p>
<p>SECTION 7. Section 12-6-3632 of the S.C. Code is amended to read:</p>
<p>Section 12-6-3632. A full-year resident is allowed one hundred twenty-five percent of the federal earned income tax credit, but not to exceed two hundred dollars.</p>
<p>SECTION 8. This act takes effect upon approval by the Governor and first applies to tax years beginning after 2025.</p>
<p>Approved the 30th day of March, 2026.</p>
</body></html>
"""

SAMPLE_MULTI_OVERLAY_CHAPTER_HTML = SAMPLE_CHAPTER_HTML.replace(
    "</body>",
    """<span style="font-weight: bold;"> SECTION 12-6-50.</span> Internal Revenue Code provisions not adopted.<br /><br />
Existing nonadoption.<br /><br />
HISTORY: 1995 Act No. 76, SECTION 1.<br /><br />
<span style="font-weight: bold;"> SECTION 12-6-1140.</span> Deductions from individual taxable income.<br /><br />
Existing deductions.<br /><br />
HISTORY: 1995 Act No. 76, SECTION 1.<br /><br />
<span style="font-weight: bold;"> SECTION 12-6-3632.</span> Earned income tax credit.<br /><br />
Old uncapped credit.<br /><br />
HISTORY: 2017 Act No. 40, SECTION 16.A.<br /><br />
</body>""",
)


def test_parse_south_carolina_master_index_html_extracts_titles():
    titles = parse_south_carolina_master_index_html(SAMPLE_MASTER_HTML)

    assert [title.number for title in titles] == [11, 12]
    assert titles[1].heading == "Taxation"
    assert titles[1].citation_path == "us-sc/statute/title-12"


def test_parse_south_carolina_title_html_extracts_chapters():
    chapters = parse_south_carolina_title_html(SAMPLE_TITLE_HTML, title=12)

    assert [chapter.number for chapter in chapters] == ["6", "8"]
    assert chapters[0].heading == "South Carolina Income Tax Act"
    assert chapters[0].citation_path == "us-sc/statute/title-12/chapter-6"


def test_parse_south_carolina_title_html_handles_probate_code_articles():
    title_html = """<!doctype html>
<html><body><table><tr>
  <td>ARTICLE 1 - GENERAL PROVISIONS, DEFINITIONS, AND PROBATE JURISDICTION OF COURT</td>
  <td><a href="/code/t62c001.php">HTML</a></td>
</tr></table></body></html>
"""

    chapters = parse_south_carolina_title_html(title_html, title=62)

    assert chapters[0].number == "1"
    assert chapters[0].heading == "General Provisions, Definitions, and Probate Jurisdiction of Court"


def test_parse_south_carolina_chapter_html_extracts_sections_articles_and_refs():
    sections = parse_south_carolina_chapter_html(SAMPLE_CHAPTER_HTML, title=12, chapter=6)

    assert [section.section for section in sections] == ["12-6-10", "12-6-20", "12-6-510"]
    assert sections[0].heading == "Short title"
    assert sections[0].article == "1"
    assert sections[1].references_to == ("us-sc/statute/12-6-10",)
    assert sections[2].article == "5"
    assert sections[2].article_heading == "Tax Rates and Imposition"
    assert sections[2].body is not None
    assert "Not over $2,220 | 2.5 percent" in sections[2].body


def test_extract_south_carolina_code_preserves_repealed_chapter_note(tmp_path):
    title_html = """<!doctype html>
<html><body><table><tr>
  <td>CHAPTER 23 - ZONING AND PLANNING [REPEALED]</td>
  <td><a href="/code/t05c023.php">HTML</a></td>
</tr></table></body></html>
"""
    source_dir = tmp_path / "source"
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "title-5").mkdir(parents=True)
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "statmast.html").write_text(
        '<a href="/code/title5.php">Title 5</a> - Municipal Corporations',
        encoding="utf-8",
    )
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "title-5.html").write_text(
        title_html,
        encoding="utf-8",
    )
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "title-5" / "chapter-23.html").write_text(
        SAMPLE_REPEALED_CHAPTER_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_south_carolina_code(
        store,
        version="2026-05-08",
        source_dir=source_dir,
        only_title=5,
        only_chapter=23,
    )

    records = load_provisions(report.provisions_path)
    assert report.errors == ()
    assert report.section_count == 0
    assert records[1].citation_path == "us-sc/statute/title-5/chapter-23"
    assert records[1].body is not None
    assert "This Chapter" in records[1].body
    assert records[1].metadata is not None
    assert records[1].metadata["status"] == "repealed"


def test_extract_south_carolina_code_from_source_dir_writes_complete_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "title-12").mkdir(parents=True)
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "statmast.html").write_text(
        SAMPLE_MASTER_HTML,
        encoding="utf-8",
    )
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "title-12.html").write_text(
        SAMPLE_TITLE_HTML,
        encoding="utf-8",
    )
    (source_dir / SOUTH_CAROLINA_SOURCE_FORMAT / "title-12" / "chapter-6.html").write_text(
        SAMPLE_CHAPTER_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_south_carolina_code(
        store,
        version="2026-05-08",
        source_dir=source_dir,
        source_as_of="2026-05-08",
        expression_date="2026-05-08",
        only_title=12,
        only_chapter=6,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 1
    assert report.section_count == 3
    assert report.provisions_written == 5
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert inventory[0].source_format == SOUTH_CAROLINA_SOURCE_FORMAT
    assert records[0].citation_path == "us-sc/statute/title-12"
    assert records[2].citation_path == "us-sc/statute/12-6-10"
    assert records[2].source_path is not None
    assert records[2].source_path.endswith(
        "/south-carolina-code-html/title-12/chapter-6.html"
    )
    assert records[3].metadata is not None
    assert records[3].metadata["references_to"] == ["us-sc/statute/12-6-10"]


def test_parse_and_apply_south_carolina_session_law_overlay():
    chapter_html = SAMPLE_CHAPTER_HTML.replace(
        "</table>\nHISTORY:",
        "</table>\n(C) The department may prescribe tax tables.<br /><br />\nHISTORY:",
    )
    section = parse_south_carolina_chapter_html(chapter_html, title=12, chapter=6)[2]

    overlay = parse_south_carolina_session_law_overlay(
        SAMPLE_SESSION_LAW_HTML,
        section="12-6-510",
    )
    current = apply_south_carolina_session_law_overlay(section, overlay)

    assert overlay.act_number == "110"
    assert overlay.bill_number == "4216"
    assert overlay.effective_text is not None
    assert current.body is not None
    assert "1.99% times the amount" in current.body
    assert "5.21% times the amount minus $966" in current.body
    assert "(C) The department may prescribe" not in current.body
    assert "2026 Act No. 110 (H.4216), SECTION 1" in current.body


def test_parse_and_apply_south_carolina_addition_and_whole_section_overlays():
    base = {
        "heading": None,
        "title": 12,
        "chapter": "6",
        "ordinal": 1,
    }
    section_50 = SouthCarolinaSection(
        section="12-6-50",
        body="Existing nonadoption.\nHISTORY: Prior law.",
        **base,
    )
    section_1140 = SouthCarolinaSection(
        section="12-6-1140",
        body="Existing deductions.\nHISTORY: Prior law.",
        **base,
    )
    section_3632 = SouthCarolinaSection(
        section="12-6-3632",
        body="Old uncapped credit.\nHISTORY: Prior law.",
        **base,
    )

    overlay_50 = parse_south_carolina_session_law_overlay(
        SAMPLE_SESSION_LAW_HTML,
        section="12-6-50",
    )
    overlay_1140 = parse_south_carolina_session_law_overlay(
        SAMPLE_SESSION_LAW_HTML,
        section="12-6-1140",
    )
    overlay_3632 = parse_south_carolina_session_law_overlay(
        SAMPLE_SESSION_LAW_HTML,
        section="12-6-3632",
    )

    current_50 = apply_south_carolina_session_law_overlay(section_50, overlay_50)
    current_1140 = apply_south_carolina_session_law_overlay(section_1140, overlay_1140)
    current_3632 = apply_south_carolina_session_law_overlay(section_3632, overlay_3632)

    assert overlay_50.operation == "add"
    assert "Section 63(b) through (g)" in (current_50.body or "")
    assert overlay_1140.operation == "add"
    assert "twenty-two thousand five hundred dollars" in (current_1140.body or "")
    assert overlay_3632.operation == "replace_section"
    assert "two hundred dollars" in (current_3632.body or "")
    assert "Old uncapped credit" not in (current_3632.body or "")
    assert "2026 Act No. 110 (H.4216), SECTION 7" in (current_3632.body or "")


def test_extract_south_carolina_code_applies_official_session_law(tmp_path):
    source_dir = tmp_path / "source"
    source_root = source_dir / SOUTH_CAROLINA_SOURCE_FORMAT
    (source_root / "title-12").mkdir(parents=True)
    (source_root / "session-laws").mkdir()
    (source_root / "statmast.html").write_text(SAMPLE_MASTER_HTML, encoding="utf-8")
    (source_root / "title-12.html").write_text(SAMPLE_TITLE_HTML, encoding="utf-8")
    (source_root / "title-12" / "chapter-6.html").write_text(
        SAMPLE_MULTI_OVERLAY_CHAPTER_HTML.replace(
            "</table>\nHISTORY:",
            "</table>\n(C) The department may prescribe tax tables.<br /><br />\nHISTORY:",
        ),
        encoding="utf-8",
    )
    (source_root / "session-laws" / "2026-act-110.html").write_text(
        SAMPLE_SESSION_LAW_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_south_carolina_code(
        store,
        version="2026-07-16",
        source_dir=source_dir,
        source_as_of="2026-07-16",
        expression_date="2026-07-16",
        only_title=12,
        only_chapter=6,
        session_law_url="https://example.gov/2026-act-110.html",
        session_law_sections=(
            "12-6-510",
            "12-6-50",
            "12-6-1140",
            "12-6-3632",
        ),
        session_law_source_id="2026-act-110",
    )

    records = load_provisions(report.provisions_path)
    records_by_citation = {record.citation_path: record for record in records}
    current = records_by_citation["us-sc/statute/12-6-510"]
    assert report.coverage.complete is True
    assert len(report.source_paths) == 4
    assert current.source_url == "https://example.gov/2026-act-110.html"
    assert current.body is not None
    assert "5.21% times the amount minus $966" in current.body
    assert current.metadata is not None
    assert current.metadata["session_law_overlay"]["act_number"] == "110"
    assert [component["role"] for component in current.metadata["source_components"]] == [
        "codified_base",
        "operative_session_law_overlay",
    ]
    assert "Section 63(b) through (g)" in (
        records_by_citation["us-sc/statute/12-6-50"].body or ""
    )
    assert "twenty-two thousand five hundred dollars" in (
        records_by_citation["us-sc/statute/12-6-1140"].body or ""
    )
    assert "not to exceed two hundred dollars" in (
        records_by_citation["us-sc/statute/12-6-3632"].body or ""
    )
    assert "Old uncapped credit" not in (
        records_by_citation["us-sc/statute/12-6-3632"].body or ""
    )
