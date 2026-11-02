"""A section page the run cannot use stays a visible coverage gap.

Each case gives one section, named by its parent listing, a page the run
cannot use: the page cannot be fetched, is a maintenance or empty page, or has
the wrong shape. The section must then be an error, an inventory item with no
provision, and incomplete coverage under strict release validation. A section
whose page could not be fetched is sourced from the parent listing that names
it; one whose page was fetched but is unusable is sourced from its own page.
A section whose official page holds no text, or marks it repealed, is still
written, so a run of those stays complete.
"""

import json

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from axiom_corpus.corpus.state_adapters.massachusetts import (
    extract_massachusetts_general_laws,
)
from tests.test_corpus_maryland import SAMPLE_EMPTY_SECTION_HTML as MD_EMPTY_SECTION_HTML
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
    SAMPLE_REPEALED_SECTION_HTML as MA_REPEALED_SECTION_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_SECTION_HTML as MA_SECTION_TWO_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_SECTION_ONE_HTML as MA_SECTION_ONE_HTML,
)
from tests.test_state_extraction_gaps import MAINTENANCE, _assert_visible_gaps, _write_sources

EMPTY_PAGE = ""
WRONG_SHAPE_HTML = (
    "<html><body><main><h1>Search results</h1><p>No entries.</p></main></body></html>"
)
# "missing-file" stands in for a page that could not be fetched at all.
SECTION_FAILURES = ["missing-file", "maintenance", "empty", "wrong-shape"]


def _fail_page(pages: dict[str, str], relative: str, failure: str) -> None:
    if failure == "missing-file":
        pages.pop(relative, None)
        return
    pages[relative] = {
        "maintenance": MAINTENANCE,
        "empty": EMPTY_PAGE,
        "wrong-shape": WRONG_SHAPE_HTML,
    }[failure]


def _assert_complete(report, *, expected: set[str]) -> None:
    assert report.errors == ()
    assert report.coverage.complete is True
    provisions = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert provisions == expected


# --- Maryland: articles.json -> sections/<article>.json -> section pages ---

MD_ARTICLES = [{"DisplayText": "Agriculture - (gag)", "Value": "gag"}]
MD_SECTIONS = [{"DisplayText": "1-101", "Value": "100"}, {"DisplayText": "1-102", "Value": "200"}]
MD_SECTION_LIST = "maryland-code-json/sections/gag.json"
MD_GOOD_PAGES = {
    "maryland-code-json/articles.json": json.dumps(MD_ARTICLES),
    MD_SECTION_LIST: json.dumps(MD_SECTIONS),
    "maryland-code-html/gag/1-101.html": MD_SECTION_HTML,
    "maryland-code-html/gag/1-102.html": MD_SECTION_HTML.replace("1&ndash;101", "1&ndash;102"),
}
MD_EXTRACTED = {
    "us-md/statute/gag",
    "us-md/statute/gag/title-1",
    "us-md/statute/gag/1-101",
    "us-md/statute/gag/1-102",
}


def _extract_maryland(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_maryland_code(
        store, version="2026-05-09", source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", SECTION_FAILURES)
def test_maryland_failed_section_page_remains_inventory_gap(tmp_path, failure):
    # On main a section page that could not be fetched or read was logged as an
    # error with no inventory item, so coverage still read complete.
    failed = "maryland-code-html/gag/1-102.html"
    pages = dict(MD_GOOD_PAGES)
    _fail_page(pages, failed, failure)
    store, report = _extract_maryland(tmp_path, pages)
    assert report.section_count == 1
    assert "gag 1-102" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MD_EXTRACTED,
        missing={"us-md/statute/gag/1-102"},
        gap_source=MD_SECTION_LIST if failure == "missing-file" else failed,
    )


def test_maryland_section_page_without_text_stays_complete(tmp_path):
    pages = dict(MD_GOOD_PAGES)
    pages["maryland-code-html/gag/1-102.html"] = MD_EMPTY_SECTION_HTML.replace(
        "1&ndash;103", "1&ndash;102"
    )
    _, report = _extract_maryland(tmp_path, pages)
    assert report.section_count == 2
    _assert_complete(report, expected=MD_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-md/statute/gag/1-102"].body is None
    assert records["us-md/statute/gag/1-102"].metadata["status"] == "source-empty"


# --- Massachusetts: index -> part page -> title chapter fragment -> chapter -> sections ---

MA_CHAPTER_62 = "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62.html"
MA_SECTION_ONE = "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section1.html"
MA_SECTION_TWO = "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section2.html"
MA_GOOD_PAGES = {
    "pages/Laws/GeneralLaws/index.html": MA_INDEX_HTML,
    "pages/Laws/GeneralLaws/PartI.html": MA_PART_HTML,
    "ajax/GetChaptersForTitle/part-1-title-9-IX.html": MA_CHAPTERS_FRAGMENT,
    MA_CHAPTER_62: MA_CHAPTER_HTML,
    MA_SECTION_ONE: MA_SECTION_ONE_HTML,
    MA_SECTION_TWO: MA_SECTION_TWO_HTML,
}
MA_EXTRACTED = {
    "us-ma/statute/part-i",
    "us-ma/statute/part-i/title-ix",
    "us-ma/statute/part-i/title-ix/chapter-62",
    "us-ma/statute/62/1",
    "us-ma/statute/62/2",
}


def _extract_massachusetts(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_massachusetts_general_laws(
        store, version="2026-05-09", source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", SECTION_FAILURES)
def test_massachusetts_failed_section_page_remains_inventory_gap(tmp_path, failure):
    # On main a section page that could not be fetched or read was logged as an
    # error with no inventory item, so coverage still read complete.
    pages = dict(MA_GOOD_PAGES)
    _fail_page(pages, MA_SECTION_TWO, failure)
    store, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 1
    assert "62 2" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MA_EXTRACTED,
        missing={"us-ma/statute/62/2"},
        gap_source=MA_CHAPTER_62 if failure == "missing-file" else MA_SECTION_TWO,
    )


def test_massachusetts_repealed_section_page_stays_complete(tmp_path):
    pages = dict(MA_GOOD_PAGES)
    pages[MA_SECTION_TWO] = MA_REPEALED_SECTION_HTML
    _, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 2
    _assert_complete(report, expected=MA_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-ma/statute/62/2"].metadata["status"] == "repealed"
