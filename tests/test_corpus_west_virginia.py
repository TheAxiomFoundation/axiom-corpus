import json

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.west_virginia import (
    WEST_VIRGINIA_ARTICLE_SOURCE_FORMAT,
    WEST_VIRGINIA_INDEX_SOURCE_FORMAT,
    extract_west_virginia_code,
    parse_west_virginia_article_sections_json,
    parse_west_virginia_code_index,
)

SAMPLE_INDEX_HTML = """<!doctype html>
<html><body><div id="wrapper">
  <h1><a href="https://code.wvlegislature.gov/2/">CHAPTER 2. COMMON LAW, STATUTES, LEGAL HOLIDAYS, DEFINITIONS AND LEGAL CAPACITY.</a></h1>
  <h2><a href="https://code.wvlegislature.gov/2-2/">CHAPTER 2, ARTICLE 2. LEGAL HOLIDAYS; SPECIAL MEMORIAL DAYS; CONSTRUCTION OF STATUTES; DEFINITIONS.</a></h2>
  <h3><a href="https://code.wvlegislature.gov/2-2-1/">§2-2-1. Legal holidays; official acts or court proceedings.</a></h3>
  <h3><a href="https://code.wvlegislature.gov/2-2-1A/">§2-2-1a. Special memorial days.</a></h3>
  <h3><a href="https://code.wvlegislature.gov/2-2-1B/">§2-2-1b. Repealed. Acts, 1982 Reg. Sess., Ch. 76.</a></h3>
</div></body></html>
"""

SAMPLE_ARTICLE_JSON = {
    "html": """
<h4>§2-2-1. Legal holidays; official acts or court proceedings.</h4>
<p>(a) The following days are legal holidays.</p>
<p>(b) See §2-2-1a for special memorial days.</p>
<h4>§2-2-1a. Special memorial days.</h4>
<p>June 20 is West Virginia Day.</p>
<h4>§2-2-1b. Repealed. Acts, 1982 Reg. Sess., Ch. 76.</h4>
"""
}

SAMPLE_2026_RATE_AUTHORITY_JSON = {
    "html": """
<h4>§11-21-4h. Future personal income tax reductions.</h4>
<p>(b) Beginning on August 15, 2026, and every August 15 thereafter, the Secretary
of Revenue will determine whether adjusted collections exceed inflation-adjusted
base-year revenues. Any reduction begins the second taxable year following the
determination.</p>
<p>(e) This section applies for taxable years beginning on and after January 1, 2027,
in lieu of the rates specified in §11-21-4j.</p>
<h4>§11-21-4j. Rate of tax — Taxable years beginning on and after January 1, 2026.</h4>
<p>(a) For taxable years beginning on and after January 1, 2026:</p>
<p>Not over $10,000 2.11% of the taxable income</p>
<p>Over $10,000 but not over $25,000 $211 plus 2.81% of excess over $10,000</p>
<p>Over $25,000 but not over $40,000 $632.50 plus 3.16% of excess over $25,000</p>
<p>Over $40,000 but not over $60,000 $1,106.50 plus 4.22% of excess over $40,000</p>
<p>Over $60,000 $1,950.50 plus 4.58% of excess over $60,000</p>
<p>(b) Married individuals filing separate returns:</p>
<p>Not over $5,000 2.11% of the taxable income</p>
<p>Over $5,000 but not over $12,500 $105.50 plus 2.81% of excess over $5,000</p>
<p>Over $12,500 but not over $20,000 $316.25 plus 3.16% of excess over $12,500</p>
<p>Over $20,000 but not over $30,000 $553.25 plus 4.22% of excess over $20,000</p>
<p>Over $30,000 $975.25 plus 4.58% of excess over $30,000</p>
"""
}


def test_parse_west_virginia_code_index_extracts_hierarchy():
    index = parse_west_virginia_code_index(SAMPLE_INDEX_HTML)

    assert [chapter.chapter for chapter in index.chapters] == ["2"]
    assert index.chapters[0].citation_path == "us-wv/statute/chapter-2"
    assert [article.article for article in index.articles] == ["2"]
    assert index.articles[0].citation_path == "us-wv/statute/chapter-2/article-2"
    assert [section.section for section in index.sections] == ["2-2-1", "2-2-1A", "2-2-1B"]
    assert index.sections[1].heading == "Special memorial days"


def test_parse_west_virginia_article_sections_json_extracts_bodies_refs_and_status():
    sections = parse_west_virginia_article_sections_json(json.dumps(SAMPLE_ARTICLE_JSON))

    assert [section.section for section in sections] == ["2-2-1", "2-2-1A", "2-2-1B"]
    assert sections[0].body is not None
    assert "legal holidays" in sections[0].body
    assert sections[0].references_to == ("us-wv/statute/2-2-1A",)
    assert sections[2].status == "repealed"


def test_parse_west_virginia_article_sections_json_handles_repealed_paragraphs_and_ranges():
    payload = {
        "html": """
<p>§4-4-1 to 4-4-3.</p><p>Repealed.</p><p>Acts, 1991 Reg. Sess., Ch. 71.</p>
<p>§5-1C-1.</p><p>Repealed.</p><p>Acts, 2003 Reg. Sess., Ch. 197.</p>
"""
    }

    sections = parse_west_virginia_article_sections_json(json.dumps(payload))

    assert [section.section for section in sections] == [
        "4-4-1",
        "4-4-2",
        "4-4-3",
        "5-1C-1",
    ]
    assert sections[0].body == "Repealed.\nActs, 1991 Reg. Sess., Ch. 71."
    assert sections[0].status == "repealed"
    assert sections[3].body == "Repealed.\nActs, 2003 Reg. Sess., Ch. 197."


def test_parse_west_virginia_article_preserves_2026_rates_and_future_trigger():
    sections = parse_west_virginia_article_sections_json(
        json.dumps(SAMPLE_2026_RATE_AUTHORITY_JSON)
    )

    assert [section.section for section in sections] == ["11-21-4H", "11-21-4J"]
    trigger, rates = sections
    assert trigger.body is not None
    assert "Beginning on August 15, 2026" in trigger.body
    assert "second taxable year following the determination" in trigger.body
    assert "beginning on and after January 1, 2027" in trigger.body
    assert rates.body is not None
    assert "Not over $10,000 2.11% of the taxable income" in rates.body
    assert "$211 plus 2.81% of excess over $10,000" in rates.body
    assert "$632.50 plus 3.16% of excess over $25,000" in rates.body
    assert "$1,106.50 plus 4.22% of excess over $40,000" in rates.body
    assert "$1,950.50 plus 4.58% of excess over $60,000" in rates.body
    assert "$105.50 plus 2.81% of excess over $5,000" in rates.body
    assert "$316.25 plus 3.16% of excess over $12,500" in rates.body
    assert "$553.25 plus 4.22% of excess over $20,000" in rates.body
    assert "$975.25 plus 4.58% of excess over $30,000" in rates.body


def test_extract_west_virginia_code_from_source_dir_writes_complete_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / WEST_VIRGINIA_INDEX_SOURCE_FORMAT).mkdir(parents=True)
    (source_dir / WEST_VIRGINIA_ARTICLE_SOURCE_FORMAT / "chapter-2").mkdir(parents=True)
    (source_dir / WEST_VIRGINIA_INDEX_SOURCE_FORMAT / "wvcodeentire.html").write_text(
        SAMPLE_INDEX_HTML,
        encoding="utf-8",
    )
    (source_dir / WEST_VIRGINIA_ARTICLE_SOURCE_FORMAT / "chapter-2" / "article-2.json").write_text(
        json.dumps(SAMPLE_ARTICLE_JSON),
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_west_virginia_code(
        store,
        version="2026-05-08",
        source_dir=source_dir,
        source_as_of="2026-05-08",
        expression_date="2026-05-08",
        only_chapter=2,
        only_article=2,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 1
    assert report.section_count == 3
    assert report.provisions_written == 5
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert inventory[0].source_format == WEST_VIRGINIA_INDEX_SOURCE_FORMAT
    assert records[0].citation_path == "us-wv/statute/chapter-2"
    assert records[1].citation_path == "us-wv/statute/chapter-2/article-2"
    assert records[2].citation_path == "us-wv/statute/2-2-1"
    assert records[2].source_path is not None
    assert records[2].source_path.endswith(
        "/west-virginia-code-article-json/chapter-2/article-2.json"
    )
    assert records[2].metadata is not None
    assert records[2].metadata["references_to"] == ["us-wv/statute/2-2-1A"]
