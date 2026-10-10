from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.new_hampshire import (
    NEW_HAMPSHIRE_2021_HB2_URL,
    NEW_HAMPSHIRE_2023_HB2_URL,
    NEW_HAMPSHIRE_CHAPTER_SOURCE_FORMAT,
    NEW_HAMPSHIRE_MERGED_CHAPTER_SOURCE_FORMAT,
    NEW_HAMPSHIRE_ROOT_SOURCE_FORMAT,
    NEW_HAMPSHIRE_TITLE_SOURCE_FORMAT,
    _RecordedSource,
    extract_new_hampshire_rsa,
    parse_new_hampshire_chapter_77_repeal,
    parse_new_hampshire_chapter_toc,
    parse_new_hampshire_merged_chapter,
    parse_new_hampshire_root,
    parse_new_hampshire_title_page,
)

SAMPLE_ROOT_HTML = """
<html><body>
<ul>
  <li><a href="NHTOC/NHTOC-V.htm">TITLE V: TAXATION</a></li>
  <p class="chapter_list">Chapters 71 - 84</p>
</ul>
</body></html>
"""

SAMPLE_TITLE_HTML = """
<html><body>
<ul>
  <li><a href="NHTOC-V-77-A.htm">CHAPTER 77-A: BUSINESS PROFITS TAX</a></li>
</ul>
</body></html>
"""

SAMPLE_CHAPTER_TOC_HTML = """
<html><body>
<h2><a href="../V/77-A/77-A-mrg.htm">Entire Chapter</a></h2>
<ul>
  <li><a href="../V/77-A/77-A-1.htm">Section: 77-A:1 Definitions.</a></li>
  <li><a href="../V/77-A/77-A-2.htm">Section: 77-A:2 Tax Imposed.</a></li>
</ul>
</body></html>
"""

SAMPLE_MERGED_CHAPTER_HTML = """
<html><body>
<center><h3>Section 77-A:1</h3></center>
<codesect>
  <b>77-A:1 Definitions. &#150;</b>
  For purposes of RSA 77-A:2, "gross business profits" means gross income.
</codesect>
<sourcenote>Source. 1970, 5:1.</sourcenote>
<center><h3>Section 77-A:2</h3></center>
<codesect>
  <b>77-A:2 Tax Imposed. &#150;</b>
  A tax is imposed on taxable business profits.
</codesect>
<sourcenote>Source. 1970, 5:2.</sourcenote>
</body></html>
"""

SAMPLE_REPEALED_TITLE_HTML = """
<html><body><ul>
  <li><a href="NHTOC-V-77.htm">CHAPTER 77: TAXATION OF INCOMES</a></li>
</ul></body></html>
"""

SAMPLE_REPEALED_CHAPTER_TOC_HTML = """
<html><body>
<h2><a href="../V/77/77-mrg.htm">CHAPTER 77: TAXATION OF INCOMES</a></h2>
<ul><li>Chapter is repealed</li></ul>
</body></html>
"""

SAMPLE_REPEALED_CHAPTER_HTML = """
<html><head><title>Chapter 77 Repealed</title></head><body>
<h1>TITLE V TAXATION</h1><h2>Chapter 77 TAXATION OF INCOMES</h2>
<p><b>Chapter 77 Repealed -</b> Entire Chapter was repealed</p>
<br>[Repealed by 2021, 91:189, II, eff. Jan. 1, 2025.]
</body></html>
"""

SAMPLE_2021_REPEAL_HTML = """
<html><body>
<p>CHAPTER 91</p>
<p>91:99 Repeals; Interest and Dividends Taxation; 2027.</p>
<p>II. RSA 77, relative to taxation of incomes.</p>
<p>91:101 Application; Repeal of RSA 77. Paragraph II of section 99 shall apply to
taxable periods beginning after December 31, 2026.</p>
<p>Approved: June 25, 2021</p>
</body></html>
"""

SAMPLE_2023_ACCELERATION_HTML = """
<html><head><style>.deleted{text-decoration: line-through;}</style></head><body>
<p>CHAPTER 79</p>
<p>79:85 Taxation of Incomes; Rate. Amend RSA 77:1 to read as follows:</p>
<p>IV. The annual tax shall be <span class="deleted">2 percent for all taxable periods
ending on or after December 31, 2025</span>.</p>
<p>V. The annual tax shall be <span class="deleted">1 percent for all taxable periods
ending on or after December 31, 2026</span>.</p>
<p>79:87 Application; Repeal of RSA 77.</p>
<p>Paragraph II of section 99 shall apply to taxable periods beginning after December 31,
<span class="deleted">2026</span> 2024.</p>
<p>79:88 Amend Effective Date; Amend Repeal of Interest and Dividends Tax from 2027 to 2025.</p>
<p>Sections 90-100 of this act shall take effect January 1,
<span class="deleted">2027</span> 2025.</p>
<p>Approved: June 20, 2023</p>
</body></html>
"""

SAMPLE_ROOT_SOURCE = _RecordedSource(
    source_url="https://gc.nh.gov/rsa/html/nhtoc.htm",
    source_path="sources/us-nh/statute/test/nhtoc.htm",
    source_format=NEW_HAMPSHIRE_ROOT_SOURCE_FORMAT,
    sha256="abc",
)


def test_parse_new_hampshire_rsa_pages():
    titles = parse_new_hampshire_root(SAMPLE_ROOT_HTML, source=SAMPLE_ROOT_SOURCE)
    assert [title.title for title in titles] == ["V"]
    assert titles[0].heading == "Taxation"
    assert titles[0].chapter_range == "Chapters 71 - 84"

    chapters = parse_new_hampshire_title_page(SAMPLE_TITLE_HTML, title=titles[0])
    assert [chapter.chapter for chapter in chapters] == ["77-A"]
    assert chapters[0].heading == "Business Profits Tax"
    assert chapters[0].source_url.endswith("/NHTOC/NHTOC-V-77-A.htm")

    chapter_source = _RecordedSource(
        source_url="https://gc.nh.gov/rsa/html/NHTOC/NHTOC-V-77-A.htm",
        source_path="sources/us-nh/statute/test/NHTOC-V-77-A.htm",
        source_format=NEW_HAMPSHIRE_CHAPTER_SOURCE_FORMAT,
        sha256="def",
    )
    chapter, listings = parse_new_hampshire_chapter_toc(
        SAMPLE_CHAPTER_TOC_HTML,
        listing=chapters[0],
        source=chapter_source,
    )
    assert chapter.citation_path == "us-nh/statute/chapter-77-a"
    assert [listing.section_label for listing in listings] == ["77-A:1", "77-A:2"]
    assert listings[0].source_url == "https://gc.nh.gov/rsa/html/V/77-A/77-A-1.htm"

    merged_source = _RecordedSource(
        source_url="https://gc.nh.gov/rsa/html/V/77-A/77-A-mrg.htm",
        source_path="sources/us-nh/statute/test/77-A-mrg.htm",
        source_format=NEW_HAMPSHIRE_MERGED_CHAPTER_SOURCE_FORMAT,
        sha256="ghi",
    )
    sections = parse_new_hampshire_merged_chapter(
        SAMPLE_MERGED_CHAPTER_HTML,
        listings=listings,
        source=merged_source,
    )
    assert sections[0].citation_path == "us-nh/statute/77-a:1"
    assert "gross business profits" in (sections[0].body or "")
    assert sections[0].source_history == ("1970, 5:1.",)
    assert sections[0].references_to == ("us-nh/statute/77-a:2",)


def test_extract_new_hampshire_rsa_from_source_dir_writes_complete_artifacts(
    tmp_path,
):
    source_dir = tmp_path / "source"
    (source_dir / NEW_HAMPSHIRE_ROOT_SOURCE_FORMAT).mkdir(parents=True)
    (source_dir / NEW_HAMPSHIRE_TITLE_SOURCE_FORMAT).mkdir(parents=True)
    (source_dir / NEW_HAMPSHIRE_CHAPTER_SOURCE_FORMAT).mkdir(parents=True)
    (
        source_dir / NEW_HAMPSHIRE_MERGED_CHAPTER_SOURCE_FORMAT / "V" / "77-A"
    ).mkdir(parents=True)
    (source_dir / NEW_HAMPSHIRE_ROOT_SOURCE_FORMAT / "nhtoc.htm").write_text(
        SAMPLE_ROOT_HTML,
        encoding="utf-8",
    )
    (source_dir / NEW_HAMPSHIRE_TITLE_SOURCE_FORMAT / "NHTOC-V.htm").write_text(
        SAMPLE_TITLE_HTML,
        encoding="utf-8",
    )
    (source_dir / NEW_HAMPSHIRE_CHAPTER_SOURCE_FORMAT / "NHTOC-V-77-A.htm").write_text(
        SAMPLE_CHAPTER_TOC_HTML,
        encoding="utf-8",
    )
    (
        source_dir
        / NEW_HAMPSHIRE_MERGED_CHAPTER_SOURCE_FORMAT
        / "V"
        / "77-A"
        / "77-A-mrg.htm"
    ).write_text(SAMPLE_MERGED_CHAPTER_HTML, encoding="utf-8")
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_new_hampshire_rsa(
        store,
        version="2026-05-10",
        source_dir=source_dir,
        source_as_of="2026-05-10",
        expression_date="2026-05-10",
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 2
    assert report.section_count == 2
    assert report.provisions_written == 4
    assert len(load_source_inventory(report.inventory_path)) == 4
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-nh/statute/title-v",
        "us-nh/statute/chapter-77-a",
        "us-nh/statute/77-a:1",
        "us-nh/statute/77-a:2",
    ]
    assert records[-2].metadata is not None
    assert records[-2].metadata["references_to"] == ["us-nh/statute/77-a:2"]


def test_parse_new_hampshire_chapter_77_repeal_verifies_chaptered_laws():
    repeal = parse_new_hampshire_chapter_77_repeal(
        SAMPLE_REPEALED_CHAPTER_HTML,
        SAMPLE_2021_REPEAL_HTML,
        SAMPLE_2023_ACCELERATION_HTML,
    )

    assert "Entire Chapter was repealed" in repeal.body
    assert repeal.effective_date == "2025-01-01"
    assert repeal.original_law == "Laws 2021, chapter 91, section 99(II)"
    assert repeal.acceleration_law == "Laws 2023, chapter 79, sections 85-88"
    assert repeal.printed_source_note == "[Repealed by 2021, 91:189, II, eff. Jan. 1, 2025.]"


def test_extract_new_hampshire_repealed_chapter_77_writes_complete_scope(tmp_path):
    source_dir = tmp_path / "source"
    fixtures = {
        f"{NEW_HAMPSHIRE_ROOT_SOURCE_FORMAT}/nhtoc.htm": SAMPLE_ROOT_HTML,
        f"{NEW_HAMPSHIRE_TITLE_SOURCE_FORMAT}/NHTOC-V.htm": SAMPLE_REPEALED_TITLE_HTML,
        f"{NEW_HAMPSHIRE_CHAPTER_SOURCE_FORMAT}/NHTOC-V-77.htm": SAMPLE_REPEALED_CHAPTER_TOC_HTML,
        f"{NEW_HAMPSHIRE_MERGED_CHAPTER_SOURCE_FORMAT}/V/77/77-mrg.htm": SAMPLE_REPEALED_CHAPTER_HTML,
        "new-hampshire-general-court/2021-hb-2-chapter-91.html": SAMPLE_2021_REPEAL_HTML,
        "new-hampshire-general-court/2023-hb-2-chapter-79.html": SAMPLE_2023_ACCELERATION_HTML,
    }
    for relative_path, text in fixtures.items():
        path = source_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_new_hampshire_rsa(
        store,
        version="2026-07-16-pit-central",
        source_dir=source_dir,
        source_as_of="2026-07-16",
        expression_date="2026-07-16",
        only_title="V",
        only_chapter="77",
        repeal_authority_2021_url=NEW_HAMPSHIRE_2021_HB2_URL,
        repeal_acceleration_2023_url=NEW_HAMPSHIRE_2023_HB2_URL,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 2
    assert report.section_count == 0
    assert report.provisions_written == 2
    assert len(report.source_paths) == 6
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-nh/statute/title-v",
        "us-nh/statute/chapter-77",
    ]
    chapter = records[-1]
    assert chapter.body is not None and "Entire Chapter was repealed" in chapter.body
    assert chapter.metadata is not None
    assert chapter.metadata["status"] == "repealed"
    assert chapter.metadata["operative_2026"] == {
        "individual_interest_and_dividends_tax": "repealed",
        "rate_percent": 0,
        "taxable_periods_beginning_after": "2024-12-31",
        "legal_character": "no tax imposed because RSA chapter 77 is repealed",
    }
    assert chapter.metadata["law_vintage"]["repeal_effective_date"] == "2025-01-01"
    assert [row["role"] for row in chapter.metadata["source_components"]] == [
        "current_chapter_toc",
        "current_repeal_text",
        "original_repeal_authority",
        "accelerated_repeal_authority",
    ]
