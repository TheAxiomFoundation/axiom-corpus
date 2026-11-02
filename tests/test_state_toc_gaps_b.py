"""A failed table of contents stays a visible coverage gap (axiom-corpus#890).

Each case gives one container a listing the run cannot use: the page cannot be
fetched, is a maintenance or empty page, has the wrong shape, or lists no
children. Its children are never seen, so the container itself must be the
gap: an error, an inventory item with no provision, and incomplete coverage
under strict release validation. A container that could not be fetched is
sourced from the parent listing that names it; one that was fetched but is
unusable is sourced from its own page.
"""

import json

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from axiom_corpus.corpus.state_adapters.massachusetts import (
    extract_massachusetts_general_laws,
)
from tests.test_corpus_maryland import SAMPLE_SECTION_HTML as MD_SECTION_HTML
from tests.test_corpus_massachusetts import (
    SAMPLE_CHAPTER_HTML as MA_CHAPTER_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_CHAPTERS_FRAGMENT as MA_CHAPTERS_FRAGMENT,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_INDEX_HTML as MA_INDEX_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_PART_HTML as MA_PART_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_SECTION_HTML as MA_SECTION_TWO_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_SECTION_ONE_HTML as MA_SECTION_ONE_HTML,
)
from tests.test_state_extraction_gaps import MAINTENANCE, _assert_visible_gaps, _write_sources

EMPTY_PAGE = ""
WRONG_SHAPE_HTML = "<html><body><main><h1>Search results</h1><p>No entries.</p></main></body></html>"
# "missing-file" stands in for a page that could not be fetched at all.
TOC_FAILURES = ["missing-file", "maintenance", "empty", "wrong-shape", "no-children"]


def _fail_page(pages: dict[str, str], relative: str, failure: str, bodies: dict[str, str]) -> None:
    if failure == "missing-file":
        pages.pop(relative, None)
        return
    pages[relative] = {
        "maintenance": MAINTENANCE,
        "empty": EMPTY_PAGE,
        "wrong-shape": WRONG_SHAPE_HTML,
        **bodies,
    }[failure]


# --- Maryland: articles.json -> sections/<article>.json -> section pages ---

MD_ARTICLES = [
    {"DisplayText": "Agriculture - (gag)", "Value": "gag"},
    {"DisplayText": "Business Regulation - (gbr)", "Value": "gbr"},
]
MD_SECTIONS = [{"DisplayText": "1-101", "Value": "100"}, {"DisplayText": "1-102", "Value": "200"}]
MD_GOOD_PAGES = {
    "maryland-code-json/articles.json": json.dumps(MD_ARTICLES),
    "maryland-code-json/sections/gag.json": json.dumps(MD_SECTIONS),
    "maryland-code-html/gag/1-101.html": MD_SECTION_HTML,
    "maryland-code-html/gag/1-102.html": MD_SECTION_HTML.replace("1&ndash;101", "1&ndash;102"),
}
MD_EXTRACTED = {
    "us-md/statute/gag",
    "us-md/statute/gag/title-1",
    "us-md/statute/gag/1-101",
    "us-md/statute/gag/1-102",
}


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_maryland_failed_article_section_list_remains_inventory_gap(tmp_path, failure):
    failed = "maryland-code-json/sections/gbr.json"
    pages = dict(MD_GOOD_PAGES)
    pages[failed] = json.dumps(MD_SECTIONS)
    _fail_page(
        pages,
        failed,
        failure,
        {"wrong-shape": json.dumps({"Message": "An error has occurred."}), "no-children": "[]"},
    )
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_maryland_code(store, version="2026-05-09", source_dir=tmp_path / "source")
    assert report.section_count == 2
    assert "gbr" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MD_EXTRACTED | {"us-md/statute/gbr"},
        missing={"us-md/statute/gbr"},
        gap_source=(
            "maryland-code-json/articles.json" if failure == "missing-file" else "sections/gbr.json"
        ),
    )


# --- Massachusetts: index -> part page -> title chapter fragment -> chapter page ---

MA_PART_II_LINK = """
  <li><a href="/Laws/GeneralLaws/PartII">
    <span class="part">Part II</span>
    <span class="partTitle">REAL AND PERSONAL PROPERTY AND DOMESTIC RELATIONS</span>
    <span class="chapters">Chapters 183-210</span>
  </a></li>
</ul>"""
MA_TITLE_X_PANEL = """
  <div id="Xtitle" class="panel panel-default">
    <div class="panel-heading">
      <h4 class="glTitle panel-title">
        <a href="#titleX" onclick="accordionAjaxLoad('1', '10', 'X')">Title X</a>
      </h4>
      <h4 class="panel-title">
        <a href="#titleX" onclick="accordionAjaxLoad('1', '10', 'X')">PUBLIC RECORDS</a>
      </h4>
    </div>
  </div>
</div>
</body>"""
MA_CHAPTER_63_LINK = """
    <li><a href="/Laws/GeneralLaws/PartI/TitleIX/Chapter63">
      <span class="chapter">Chapter 63</span>
      <span class="chapterTitle">TAXATION OF CORPORATIONS</span>
    </a></li>
  </ul>"""
MA_INDEX = "pages/Laws/GeneralLaws/index.html"
MA_PART_I = "pages/Laws/GeneralLaws/PartI.html"
MA_TITLE_IX = "ajax/GetChaptersForTitle/part-1-title-9-IX.html"
MA_CHAPTER_62 = "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62.html"
MA_GOOD_PAGES = {
    MA_INDEX: MA_INDEX_HTML,
    MA_PART_I: MA_PART_HTML,
    MA_TITLE_IX: MA_CHAPTERS_FRAGMENT,
    MA_CHAPTER_62: MA_CHAPTER_HTML,
    "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section1.html": MA_SECTION_ONE_HTML,
    "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section2.html": MA_SECTION_TWO_HTML,
}
MA_EXTRACTED = {
    "us-ma/statute/part-i",
    "us-ma/statute/part-i/title-ix",
    "us-ma/statute/part-i/title-ix/chapter-62",
    "us-ma/statute/62/1",
    "us-ma/statute/62/2",
}
# A page of the right kind that lists nothing, at each level.
MA_EMPTY_PART = MA_PART_HTML.split('<div id="Ititle"')[0] + "</div></body></html>"
MA_EMPTY_FRAGMENT = '<div class="panel-collapse"><ul class="generalLawsList"></ul></div>'
MA_EMPTY_CHAPTER = MA_CHAPTER_HTML.split("<li>")[0] + "</ul></body></html>"


def _extract_massachusetts(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_massachusetts_general_laws(
        store, version="2026-05-09", source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_massachusetts_failed_part_page_remains_inventory_gap(tmp_path, failure):
    failed = "pages/Laws/GeneralLaws/PartII.html"
    pages = dict(MA_GOOD_PAGES)
    pages[MA_INDEX] = MA_INDEX_HTML.replace("</ul>", MA_PART_II_LINK, 1)
    pages[failed] = MA_PART_HTML
    _fail_page(pages, failed, failure, {"no-children": MA_EMPTY_PART})
    store, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 2
    assert "PartII" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MA_EXTRACTED | {"us-ma/statute/part-ii"},
        missing={"us-ma/statute/part-ii"},
        gap_source=MA_INDEX if failure == "missing-file" else failed,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_massachusetts_failed_title_chapter_list_remains_inventory_gap(tmp_path, failure):
    failed = "ajax/GetChaptersForTitle/part-1-title-10-X.html"
    pages = dict(MA_GOOD_PAGES)
    pages[MA_PART_I] = MA_PART_HTML.replace("</div>\n</body>", MA_TITLE_X_PANEL, 1)
    pages[failed] = MA_CHAPTERS_FRAGMENT
    _fail_page(pages, failed, failure, {"no-children": MA_EMPTY_FRAGMENT})
    store, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 2
    assert "title-10-X" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MA_EXTRACTED | {"us-ma/statute/part-i/title-x"},
        missing={"us-ma/statute/part-i/title-x"},
        gap_source=MA_PART_I if failure == "missing-file" else failed,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_massachusetts_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    # On main a chapter page that could not be fetched was logged as an error
    # with no inventory item, so coverage still read complete.
    failed = "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter63.html"
    pages = dict(MA_GOOD_PAGES)
    pages[MA_TITLE_IX] = MA_CHAPTERS_FRAGMENT.replace("  </ul>", MA_CHAPTER_63_LINK, 1)
    pages[failed] = MA_CHAPTER_HTML
    _fail_page(pages, failed, failure, {"no-children": MA_EMPTY_CHAPTER})
    store, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 2
    assert "chapter 63" in report.errors[0]
    chapter = "us-ma/statute/part-i/title-ix/chapter-63"
    _assert_visible_gaps(
        store,
        report,
        expected=MA_EXTRACTED | {chapter},
        missing={chapter},
        gap_source=MA_TITLE_IX if failure == "missing-file" else failed,
    )
