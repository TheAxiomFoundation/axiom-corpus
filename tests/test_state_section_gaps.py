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
from axiom_corpus.corpus.state_adapters import arizona
from axiom_corpus.corpus.state_adapters.arizona import (
    ARIZONA_SECTION_SOURCE_FORMAT,
    ARIZONA_TITLE_DETAIL_SOURCE_FORMAT,
    ARIZONA_TITLE_INDEX_SOURCE_FORMAT,
    extract_arizona_revised_statutes,
)
from axiom_corpus.corpus.state_adapters.hawaii import (
    HAWAII_CHAPTER_DIRECTORY_SOURCE_FORMAT,
    HAWAII_CHAPTER_INDEX_SOURCE_FORMAT,
    HAWAII_ROOT_INDEX_SOURCE_FORMAT,
    HAWAII_SECTION_SOURCE_FORMAT,
    HAWAII_VOLUME_DIRECTORY_SOURCE_FORMAT,
    extract_hawaii_revised_statutes,
)
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from axiom_corpus.corpus.state_adapters.massachusetts import (
    extract_massachusetts_general_laws,
)
from tests.test_corpus_arizona import SAMPLE_SECTION_HTML as AZ_SECTION_HTML
from tests.test_corpus_arizona import SAMPLE_TITLE_DETAIL_HTML as AZ_TITLE_DETAIL_HTML
from tests.test_corpus_arizona import SAMPLE_TITLE_INDEX_HTML as AZ_TITLE_INDEX_HTML
from tests.test_corpus_hawaii import SAMPLE_CHAPTER_DIRECTORY_HTML as HI_CHAPTER_DIRECTORY_HTML
from tests.test_corpus_hawaii import SAMPLE_CHAPTER_INDEX_HTML as HI_CHAPTER_INDEX_HTML
from tests.test_corpus_hawaii import SAMPLE_ROOT_HTML as HI_ROOT_HTML
from tests.test_corpus_hawaii import SAMPLE_SECTION_HTML as HI_SECTION_HTML
from tests.test_corpus_hawaii import SAMPLE_VOLUME_HTML as HI_VOLUME_HTML
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


# --- Arizona: title index -> title detail page -> section pages ---

AZ_INDEX = f"{ARIZONA_TITLE_INDEX_SOURCE_FORMAT}/index.html"
AZ_DETAIL = f"{ARIZONA_TITLE_DETAIL_SOURCE_FORMAT}/title-1.html"
AZ_SECTION_201 = f"{ARIZONA_SECTION_SOURCE_FORMAT}/title-1/1-201.html"
AZ_SECTION_202 = f"{ARIZONA_SECTION_SOURCE_FORMAT}/title-1/1-202.html"
AZ_SECTION_202_ROW = """        <ul>
          <li class="colleft">
            <a class="stat" href="/viewdocument/?docName=https://www.azleg.gov/ars/1/00202.htm">1-202</a>
          </li>
          <li class="colright">Statutes; construction</li>
        </ul>
      </div>
    </div>"""
AZ_GOOD_PAGES = {
    AZ_INDEX: AZ_TITLE_INDEX_HTML,
    AZ_DETAIL: AZ_TITLE_DETAIL_HTML.replace("      </div>\n    </div>", AZ_SECTION_202_ROW, 1),
    AZ_SECTION_201: AZ_SECTION_HTML,
    AZ_SECTION_202: AZ_SECTION_HTML.replace("1-201", "1-202"),
}
AZ_EXTRACTED = {
    "us-az/statute/title-1",
    "us-az/statute/title-1/chapter-2",
    "us-az/statute/title-1/chapter-2/article-1",
    "us-az/statute/1-201",
    "us-az/statute/1-202",
}


def _extract_arizona(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_arizona_revised_statutes(
        store, version="2026-05-09", source_dir=tmp_path / "source", only_title="1", workers=1
    )
    return store, report


def test_arizona_fixture_lists_both_sections(tmp_path):
    _, report = _extract_arizona(tmp_path, dict(AZ_GOOD_PAGES))
    assert report.section_count == 2
    _assert_complete(report, expected=AZ_EXTRACTED)


# Arizona's section parser reads any page, so a maintenance, empty or
# wrong-shape page is written as a section with no text rather than an error;
# only a page that cannot be fetched or that raises while parsing reaches here.
@pytest.mark.parametrize("failure", ["missing-file", "parse-error"])
def test_arizona_failed_section_page_remains_inventory_gap(tmp_path, monkeypatch, failure):
    # On main a section page that could not be fetched was logged as an error
    # with no inventory item, so coverage still read complete.
    pages = dict(AZ_GOOD_PAGES)
    if failure == "missing-file":
        del pages[AZ_SECTION_202]
    else:
        parse = arizona.parse_arizona_section

        def reject_202(html, *, fallback_heading=None):
            if b"<TITLE>1-202" in (html if isinstance(html, bytes) else html.encode()):
                raise ValueError("unreadable section page")
            return parse(html, fallback_heading=fallback_heading)

        monkeypatch.setattr(arizona, "parse_arizona_section", reject_202)
    store, report = _extract_arizona(tmp_path, pages)
    assert report.section_count == 1
    assert "section 1-202" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=AZ_EXTRACTED,
        missing={"us-az/statute/1-202"},
        gap_source=AZ_DETAIL if failure == "missing-file" else AZ_SECTION_202,
    )


# --- Hawaii: root -> volume -> chapter directory (+ chapter index) -> section files ---

HI_DIRECTORY = f"{HAWAII_CHAPTER_DIRECTORY_SOURCE_FORMAT}/volume-04/HRS0235.html"
HI_SECTION_DIR = f"{HAWAII_SECTION_SOURCE_FORMAT}/volume-04/HRS0235"
HI_SECTION_5575 = f"{HI_SECTION_DIR}/HRS_0235-0055_0007_0005.htm"
HI_SECTION_5576 = f"{HI_SECTION_DIR}/HRS_0235-0055_0007_0006.htm"
HI_SECTION_5576_LINK = """  <a href="/hrscurrent/Vol04_Ch0201-0257/HRS0235/HRS_0235-0055_0007_0006.htm">
    HRS_0235-0055_0007_0006.htm
  </a>
</pre>"""
HI_GOOD_PAGES = {
    f"{HAWAII_ROOT_INDEX_SOURCE_FORMAT}/index.html": HI_ROOT_HTML,
    f"{HAWAII_VOLUME_DIRECTORY_SOURCE_FORMAT}/volume-04.html": HI_VOLUME_HTML,
    HI_DIRECTORY: HI_CHAPTER_DIRECTORY_HTML.replace("</pre>", HI_SECTION_5576_LINK, 1),
    f"{HAWAII_CHAPTER_INDEX_SOURCE_FORMAT}/volume-04/HRS0235.html": HI_CHAPTER_INDEX_HTML,
    HI_SECTION_5575: HI_SECTION_HTML,
    HI_SECTION_5576: HI_SECTION_HTML.replace("235-55.75", "235-55.76"),
}
HI_EXTRACTED = {
    "us-hi/statute/volume-04",
    "us-hi/statute/chapter-235",
    "us-hi/statute/235-55.75",
    "us-hi/statute/235-55.76",
}


def _extract_hawaii(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_hawaii_revised_statutes(
        store, version="2026-05-09", source_dir=tmp_path / "source", only_title="04", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", SECTION_FAILURES)
def test_hawaii_failed_section_page_remains_inventory_gap(tmp_path, failure):
    # On main a section page that could not be fetched or read was logged as an
    # error with no inventory item, so coverage still read complete.
    pages = dict(HI_GOOD_PAGES)
    _fail_page(pages, HI_SECTION_5576, failure)
    store, report = _extract_hawaii(tmp_path, pages)
    assert report.section_count == 1
    assert "section 235-55.76" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=HI_EXTRACTED,
        missing={"us-hi/statute/235-55.76"},
        gap_source=HI_DIRECTORY if failure == "missing-file" else HI_SECTION_5576,
    )


def test_hawaii_repealed_section_page_stays_complete(tmp_path):
    pages = dict(HI_GOOD_PAGES)
    pages[HI_SECTION_5576] = (
        "<html><body><div class='WordSection1'><p class='RegularParagraphs'>"
        "<b>&sect;235-55.76 REPEALED.</b> L 2020, c 1, &sect;2.</p></div></body></html>"
    )
    _, report = _extract_hawaii(tmp_path, pages)
    assert report.section_count == 2
    _assert_complete(report, expected=HI_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-hi/statute/235-55.76"].metadata["status"] == "repealed"
