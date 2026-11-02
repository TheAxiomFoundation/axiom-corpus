from html import escape

import pytest
from bs4 import BeautifulSoup, Doctype, NavigableString
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.maine import (
    MAINE_REVISED_STATUTES_INDEX,
    MAINE_REVISED_STATUTES_SOURCE_FORMAT,
    MaineTitle,
    _maine_section_body_lines,
    extract_maine_revised_statutes,
    parse_maine_chapter_page,
    parse_maine_section,
    parse_maine_title_index,
    parse_maine_title_page,
)

SAMPLE_TITLE_INDEX_HTML = """
<html>
<body>
<ul class="title_list">
  <li class="right_nav"><a href="1/title1ch0sec0.html">TITLE 1: GENERAL PROVISIONS</a></li>
  <li class="right_nav"><a href="36/title36ch0sec0.html">TITLE 36: TAXATION</a></li>
</ul>
</body>
</html>
"""

SAMPLE_TITLE_HTML = """
<html>
<body>
<div class="title_toc MRSTitle_toclist col-sm-10">
  <div class="title_heading"><div>Title 36: TAXATION</div></div>
  <div class="MRSPart_toclist">
    <h2 class="heading_part">Part 8: INCOME TAXES</h2>
    <div class="MRSChapter_toclist">
      <a href="./title36ch822sec0.html">Chapter 822: TAX CREDITS</a> \u00a75213 - \u00a75219-BBB
    </div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_CHAPTER_HTML = """
<html>
<body>
<div class="chapter_toclist col-sm-10">
  <div class="ch_heading"><div>Title 36, Chapter 822: TAX CREDITS</div></div>
  <div class="MRSSection_toclist">
    <a href="./title36sec5219-S.html">36 \u00a75219-S. Earned income credit</a>
  </div>
  <div class="MRSSection_toclist right_nav_repealed">
    <a href="./title36sec5219-T.html">36 \u00a75219-T. Old credit (REPEALED)</a>
  </div>
</div>
</body>
</html>
"""

SAMPLE_SECTION_HTML = """
<html>
<body>
<div class="col-sm-12 MRSSection status_current">
  <h3 class="heading_section">\u00a75219-S. Earned income credit</h3>
  <div class="MRSSubSection">
    <div class="mrs-text indpara">
      <span class="headnote">1. Resident taxpayer.</span>
      A resident is allowed a credit under <a href="../36/title36sec5102.html">section 5102</a>.
    </div>
    <span class="bhistory">[PL 2021, c. 635, Pt. E, \u00a71 (AMD).]</span>
  </div>
  <div class="note"><span>Revisor's Note:</span> This is a note.</div>
  <div class="qhistory">
    SECTION HISTORY
    <div class="qhistory_list"><span class="hist_chapter">PL 1999, c. 731, \u00a7V1 (NEW).</span></div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_UNSUBDIVIDED_SECTION_HTML = """
<html>
<body>
<div class="col-sm-12 MRSSection status_current">
  <h3 class="heading_section">\u00a7115. Payment by credit card</h3>
  <div class="mrs-text indpara MRSIndentedPara status_current IP">
    The State Tax Assessor may establish procedures permitting payment of taxes by the use of credit cards.
    <span class="bhistory">[PL 2005, c. 622, \u00a73 (NEW).]</span>
  </div>
  <div class="qhistory">
    SECTION HISTORY
    <div class="qhistory_list"><span class="hist_chapter">PL 2005, c. 622, \u00a73 (NEW).</span></div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_TITLE = MaineTitle(
    number="36",
    heading="Taxation",
    relative_path="36/title36ch0sec0.html",
    ordinal=1,
)


def test_parse_maine_title_index_extracts_titles():
    titles = parse_maine_title_index(SAMPLE_TITLE_INDEX_HTML)

    assert [title.number for title in titles] == ["1", "36"]
    assert titles[1].heading == "TAXATION"
    assert titles[1].relative_path == "36/title36ch0sec0.html"
    assert titles[1].citation_path == "us-me/statute/title-36"


def test_parse_maine_title_chapter_and_section_pages():
    document = parse_maine_title_page(SAMPLE_TITLE_HTML, title=SAMPLE_TITLE)

    assert document.title_heading == "TAXATION"
    assert [part.part for part in document.parts] == ["8"]
    assert document.parts[0].citation_path == "us-me/statute/title-36/part-8"
    assert [chapter.display_chapter for chapter in document.chapters] == ["822"]
    assert document.chapters[0].section_range == "\u00a75213 - \u00a75219-BBB"

    targets = parse_maine_chapter_page(SAMPLE_CHAPTER_HTML, chapter=document.chapters[0])

    assert [target.section_id for target in targets] == ["5219-S", "5219-T"]
    assert targets[0].citation_path == "us-me/statute/36/5219-S"
    assert targets[1].status == "repealed"

    parsed = parse_maine_section(SAMPLE_SECTION_HTML, target=targets[0])

    assert parsed.heading == "Earned income credit"
    assert parsed.body is not None
    assert "resident is allowed a credit" in parsed.body
    assert parsed.references_to == ("us-me/statute/36/5102",)
    assert parsed.source_history == (
        "[PL 2021, c. 635, Pt. E, \u00a71 (AMD).]",
        "PL 1999, c. 731, \u00a7V1 (NEW).",
    )
    assert parsed.notes == ("Revisor's Note: This is a note.",)


def test_parse_maine_section_without_subsections_keeps_body():
    parsed = parse_maine_section(SAMPLE_UNSUBDIVIDED_SECTION_HTML)

    assert parsed.heading == "Payment by credit card"
    assert parsed.body is not None
    assert parsed.body.startswith("The State Tax Assessor may establish procedures")
    assert parsed.source_history == (
        "[PL 2005, c. 622, \u00a73 (NEW).]",
        "PL 2005, c. 622, \u00a73 (NEW).",
    )


@pytest.mark.parametrize("page_title", ["Maintenance", "Server error"])
def test_parse_maine_non_statute_page_rejects_real_target(page_title):
    document = parse_maine_title_page(SAMPLE_TITLE_HTML, title=SAMPLE_TITLE)
    target = parse_maine_chapter_page(SAMPLE_CHAPTER_HTML, chapter=document.chapters[0])[0]
    html = (
        f"<!DOCTYPE html><html><head><title>{page_title}</title></head><body>"
        "<h1>Scheduled maintenance</h1><p>The Maine Legislature website is temporarily "
        "unavailable. Please try again later.</p></body></html>"
    )

    assert target.citation_path == "us-me/statute/36/5219-S"
    with pytest.raises(ValueError, match="statute-content container"):
        parse_maine_section(html, target=target)


@settings(max_examples=50, deadline=None)
@given(payload=st.text(alphabet="abc XYZ019,.;:$%&<>é£\t\n\u00a0\u2011", max_size=100))
def test_generated_non_statute_page_never_becomes_cited_body(payload):
    document = parse_maine_title_page(SAMPLE_TITLE_HTML, title=SAMPLE_TITLE)
    target = parse_maine_chapter_page(SAMPLE_CHAPTER_HTML, chapter=document.chapters[0])[0]
    html = (
        "<!DOCTYPE html><html><body><main><h1>Maintenance</h1>"
        f"<div>{escape(payload)}</div></main></body></html>"
    )

    with pytest.raises(ValueError, match="statute-content container"):
        parse_maine_section(html, target=target)


def test_maine_body_walker_excludes_doctype_nodes():
    root = BeautifulSoup('<div class="MRSSection"></div>', "lxml").select_one(".MRSSection")
    assert root is not None
    root.append(Doctype("html"))
    root.append(NavigableString("Operative text."))

    assert _maine_section_body_lines(root) == ["Operative text."]


@pytest.mark.parametrize("container", ["MRSSection", "section-content"])
def test_maine_body_stays_inside_recognized_container(container):
    html = (
        '<!DOCTYPE html><html><body><p>Maintenance navigation.</p>'
        f'<div class="{container}">Opening text.<div class="mrs-text">'
        'Nested operative text.</div>Closing text.</div><p>Footer.</p></body></html>'
    )

    assert parse_maine_section(html).body == (
        "Opening text.\nNested operative text.\nClosing text."
    )


def test_maine_status_only_recognized_section_keeps_fallback():
    html = (
        '<div class="MRSSection"><h3 class="heading_section">§1. Former law</h3>'
        '<div class="headnote_blip">(REPEALED)</div></div>'
    )

    parsed = parse_maine_section(html)

    assert parsed.body == "(REPEALED)"
    assert parsed.status == "repealed"
    assert parsed.notes == ("(REPEALED)",)


def test_extract_maine_maintenance_response_fails_for_real_target(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / "36").mkdir(parents=True)
    for relative_path, html in {
        MAINE_REVISED_STATUTES_INDEX: SAMPLE_TITLE_INDEX_HTML,
        "36/title36ch0sec0.html": SAMPLE_TITLE_HTML,
        "36/title36ch822sec0.html": SAMPLE_CHAPTER_HTML,
        "36/title36sec5219-S.html": (
            "<!DOCTYPE html><html><body><h1>Scheduled maintenance</h1>"
            "<p>The Maine Legislature website is temporarily unavailable.</p></body></html>"
        ),
    }.items():
        (source_dir / relative_path).write_text(html, encoding="utf-8")
    store = CorpusArtifactStore(tmp_path / "corpus")

    with pytest.raises(ValueError, match="no Maine sections extracted.*statute-content container"):
        extract_maine_revised_statutes(
            store,
            version="2026-05-09",
            source_dir=source_dir,
            source_as_of="2025-10-01",
            expression_date="2025-10-01",
            only_title="36",
            limit=1,
        )
    assert not store.provisions_path(
        "us-me", "statute", "2026-05-09-us-me-title-36-limit-1"
    ).exists()


def test_extract_maine_revised_statutes_from_source_dir_writes_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / "36").mkdir(parents=True)
    (source_dir / MAINE_REVISED_STATUTES_INDEX).write_text(
        SAMPLE_TITLE_INDEX_HTML,
        encoding="utf-8",
    )
    (source_dir / "36" / "title36ch0sec0.html").write_text(
        SAMPLE_TITLE_HTML,
        encoding="utf-8",
    )
    (source_dir / "36" / "title36ch822sec0.html").write_text(
        SAMPLE_CHAPTER_HTML,
        encoding="utf-8",
    )
    (source_dir / "36" / "title36sec5219-S.html").write_text(
        SAMPLE_SECTION_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_maine_revised_statutes(
        store,
        version="2026-05-09",
        source_dir=source_dir,
        source_as_of="2025-10-01",
        expression_date="2025-10-01",
        only_title="36",
        limit=1,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 2
    assert report.section_count == 1
    assert report.provisions_written == 4
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert inventory[0].source_format == MAINE_REVISED_STATUTES_SOURCE_FORMAT
    assert [record.citation_path for record in records] == [
        "us-me/statute/title-36",
        "us-me/statute/title-36/part-8",
        "us-me/statute/title-36/chapter-822",
        "us-me/statute/36/5219-S",
    ]
    assert records[3].metadata is not None
    assert records[3].metadata["references_to"] == ["us-me/statute/36/5102"]
