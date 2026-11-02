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
import requests

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters import arizona, illinois, new_york
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
from axiom_corpus.corpus.state_adapters.idaho import (
    IDAHO_CHAPTER_SOURCE_FORMAT,
    IDAHO_SECTION_SOURCE_FORMAT,
    IDAHO_TITLE_INDEX_SOURCE_FORMAT,
    IDAHO_TITLE_SOURCE_FORMAT,
    extract_idaho_statutes,
)
from axiom_corpus.corpus.state_adapters.illinois import (
    ILLINOIS_ILCS_BASE_URL,
    ILLINOIS_ILCS_FULLTEXT_URL,
    extract_illinois_ilcs,
)
from axiom_corpus.corpus.state_adapters.iowa import (
    IOWA_CHAPTER_INDEX_SOURCE_FORMAT,
    IOWA_SECTION_INDEX_SOURCE_FORMAT,
    IOWA_SECTION_PDF_SOURCE_FORMAT,
    IOWA_TITLE_INDEX_SOURCE_FORMAT,
    extract_iowa_code,
)
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from axiom_corpus.corpus.state_adapters.massachusetts import (
    extract_massachusetts_general_laws,
)
from axiom_corpus.corpus.state_adapters.montana import extract_montana_code
from axiom_corpus.corpus.state_adapters.new_york import (
    extract_new_york_consolidated_laws,
    extract_new_york_openleg_sections,
)
from axiom_corpus.corpus.state_adapters.nyc_admin_code import extract_nyc_admin_code
from axiom_corpus.corpus.state_adapters.west_virginia import (
    WEST_VIRGINIA_ARTICLE_SOURCE_FORMAT,
    WEST_VIRGINIA_INDEX_SOURCE_FORMAT,
    WEST_VIRGINIA_SECTION_SOURCE_FORMAT,
    extract_west_virginia_code,
)
from tests.test_corpus_arizona import SAMPLE_EMPTY_SECTION_HTML as AZ_EMPTY_SECTION_HTML
from tests.test_corpus_arizona import SAMPLE_SECTION_HTML as AZ_SECTION_HTML
from tests.test_corpus_arizona import SAMPLE_TITLE_DETAIL_HTML as AZ_TITLE_DETAIL_HTML
from tests.test_corpus_arizona import SAMPLE_TITLE_INDEX_HTML as AZ_TITLE_INDEX_HTML
from tests.test_corpus_hawaii import SAMPLE_CHAPTER_DIRECTORY_HTML as HI_CHAPTER_DIRECTORY_HTML
from tests.test_corpus_hawaii import SAMPLE_CHAPTER_INDEX_HTML as HI_CHAPTER_INDEX_HTML
from tests.test_corpus_hawaii import SAMPLE_ROOT_HTML as HI_ROOT_HTML
from tests.test_corpus_hawaii import SAMPLE_SECTION_HTML as HI_SECTION_HTML
from tests.test_corpus_hawaii import SAMPLE_VOLUME_HTML as HI_VOLUME_HTML
from tests.test_corpus_idaho import SAMPLE_CHAPTER_HTML as ID_CHAPTER_HTML
from tests.test_corpus_idaho import SAMPLE_SECTION_HTML as ID_SECTION_HTML
from tests.test_corpus_idaho import SAMPLE_TITLE_HTML as ID_TITLE_HTML
from tests.test_corpus_idaho import SAMPLE_TITLE_INDEX_HTML as ID_TITLE_INDEX_HTML
from tests.test_corpus_illinois import SAMPLE_REPEALED_SECTION_2 as IL_REPEALED_SECTION_2
from tests.test_corpus_illinois import SAMPLE_SECTION_1 as IL_SECTION_1
from tests.test_corpus_illinois import SAMPLE_SECTION_2 as IL_SECTION_2
from tests.test_corpus_illinois import _FakeIllinoisResponse as IlFakeResponse
from tests.test_corpus_iowa import SAMPLE_CHAPTER_INDEX_HTML as IA_CHAPTER_INDEX_HTML
from tests.test_corpus_iowa import SAMPLE_SECTION_INDEX_HTML as IA_SECTION_INDEX_HTML
from tests.test_corpus_iowa import SAMPLE_TITLE_INDEX_HTML as IA_TITLE_INDEX_HTML
from tests.test_corpus_iowa import _sample_pdf as ia_sample_pdf
from tests.test_corpus_iowa import _status_pdf as ia_status_pdf
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
from tests.test_corpus_montana import _write_montana_fixture_tree as mt_write_fixture_tree
from tests.test_corpus_new_york import SAMPLE_ARTICLE as NY_ARTICLE_HTML
from tests.test_corpus_new_york import SAMPLE_EMPTY_SECTION_602 as NY_EMPTY_SECTION_602
from tests.test_corpus_new_york import _write_new_york_fixture_tree as ny_write_fixture_tree
from tests.test_corpus_new_york import (
    _write_new_york_openleg_section_fixture as ny_write_openleg_section_fixture,
)
from tests.test_corpus_nyc_admin_code import SECTION_HTML as NYC_SECTION_HTML
from tests.test_corpus_west_virginia import SAMPLE_ARTICLE_JSON as WV_ARTICLE_JSON
from tests.test_corpus_west_virginia import SAMPLE_INDEX_HTML as WV_INDEX_HTML
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


@pytest.mark.parametrize("failure", ["maintenance", "empty", "wrong-shape"])
def test_arizona_section_page_naming_no_section_remains_inventory_gap(tmp_path, failure):
    # On main the section parser read any page, so a maintenance, empty or
    # wrong-shape page was written as the section with no text and coverage
    # still read complete.
    pages = dict(AZ_GOOD_PAGES)
    _fail_page(pages, AZ_SECTION_202, failure)
    store, report = _extract_arizona(tmp_path, pages)
    assert report.section_count == 1
    assert report.errors == (
        "section 1-202: no section number in the page title or first paragraph",
    )
    _assert_visible_gaps(
        store,
        report,
        expected=AZ_EXTRACTED,
        missing={"us-az/statute/1-202"},
        gap_source=AZ_SECTION_202,
    )


def test_arizona_section_page_without_text_stays_complete(tmp_path):
    pages = dict(AZ_GOOD_PAGES)
    pages[AZ_SECTION_202] = AZ_EMPTY_SECTION_HTML.replace("1-201", "1-202")
    _, report = _extract_arizona(tmp_path, pages)
    assert report.section_count == 2
    _assert_complete(report, expected=AZ_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-az/statute/1-202"].body is None


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


# --- Iowa: title index -> chapter index -> section index -> section PDFs ---

IA_SECTION_INDEX = f"{IOWA_SECTION_INDEX_SOURCE_FORMAT}/chapter-422.html"
IA_PDF_DIR = f"{IOWA_SECTION_PDF_SOURCE_FORMAT}/chapter-422"
IA_SECTION_422_2 = f"{IA_PDF_DIR}/422.2.pdf"
IA_SECTION_422_2_ROW = """    <tr>
      <td>&#167;422.2 - Definitions.</td>
      <td><a href="/docs/code/2026/422.2.pdf">PDF</a></td>
    </tr>
  </tbody></table>"""
IA_GOOD_PAGES = {
    f"{IOWA_TITLE_INDEX_SOURCE_FORMAT}/2026.html": IA_TITLE_INDEX_HTML,
    f"{IOWA_CHAPTER_INDEX_SOURCE_FORMAT}/title-X.html": IA_CHAPTER_INDEX_HTML,
    IA_SECTION_INDEX: IA_SECTION_INDEX_HTML.replace("  </tbody></table>", IA_SECTION_422_2_ROW, 1),
}
IA_EXTRACTED = {
    "us-ia/statute/title-x",
    "us-ia/statute/chapter-422",
    "us-ia/statute/422.1",
    "us-ia/statute/422.2",
}


def _extract_iowa(tmp_path, pages: dict[str, str], pdfs: dict[str, bytes]):
    _write_sources(tmp_path / "source", pages)
    for relative, data in pdfs.items():
        path = tmp_path / "source" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_iowa_code(
        store, version="2026-05-09", source_dir=tmp_path / "source", only_title="X", workers=1
    )
    return store, report


def _iowa_pdfs() -> dict[str, bytes]:
    return {
        f"{IA_PDF_DIR}/422.1.pdf": ia_sample_pdf(),
        IA_SECTION_422_2: ia_status_pdf(
            section="422.2",
            heading="Definitions.",
            body=["For the purposes of this chapter, terms have these meanings."],
            notes=[],
        ),
    }


def test_iowa_fixture_lists_both_sections(tmp_path):
    _, report = _extract_iowa(tmp_path, dict(IA_GOOD_PAGES), _iowa_pdfs())
    assert report.section_count == 2
    _assert_complete(report, expected=IA_EXTRACTED)


@pytest.mark.parametrize("failure", SECTION_FAILURES)
def test_iowa_failed_section_pdf_remains_inventory_gap(tmp_path, failure):
    # On main a section PDF that could not be fetched or read was logged as an
    # error with no inventory item, so coverage still read complete; a
    # maintenance page served in place of the PDF was read as section text.
    pdfs = _iowa_pdfs()
    if failure == "missing-file":
        del pdfs[IA_SECTION_422_2]
    else:
        pdfs[IA_SECTION_422_2] = {
            "maintenance": MAINTENANCE,
            "empty": EMPTY_PAGE,
            "wrong-shape": WRONG_SHAPE_HTML,
        }[failure].encode()
    store, report = _extract_iowa(tmp_path, dict(IA_GOOD_PAGES), pdfs)
    assert report.section_count == 1
    assert "section 422.2" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=IA_EXTRACTED,
        missing={"us-ia/statute/422.2"},
        gap_source=IA_SECTION_INDEX if failure == "missing-file" else IA_SECTION_422_2,
    )


def test_iowa_repealed_section_pdf_stays_complete(tmp_path):
    pdfs = _iowa_pdfs()
    pdfs[IA_SECTION_422_2] = ia_status_pdf(
        section="422.2",
        heading="Definitions.",
        body=["Repealed by 2023 Acts, ch 1, §1."],
        notes=[],
    )
    _, report = _extract_iowa(tmp_path, dict(IA_GOOD_PAGES), pdfs)
    assert report.section_count == 2
    _assert_complete(report, expected=IA_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-ia/statute/422.2"].metadata["status"] == "repealed"


# --- Idaho: title index -> title page -> chapter page -> section pages ---

ID_CHAPTER = f"{IDAHO_CHAPTER_SOURCE_FORMAT}/title-63/chapter-30.html"
ID_SECTION_DIR = f"{IDAHO_SECTION_SOURCE_FORMAT}/title-63/chapter-30"
ID_SECTION_3003 = f"{ID_SECTION_DIR}/63-3003.html"
ID_SECTION_3003_ROW = """    <tr>
      <td><a href="/statutesrules/idstat/Title63/T63CH30/SECT63-3003">63-3003</a></td>
      <td>&#160;&#160;</td>
      <td> IDENTITY OF FEDERAL AND STATE TERMS. </td>
    </tr>
  </table>"""
ID_GOOD_PAGES = {
    f"{IDAHO_TITLE_INDEX_SOURCE_FORMAT}/index.html": ID_TITLE_INDEX_HTML,
    f"{IDAHO_TITLE_SOURCE_FORMAT}/title-63.html": ID_TITLE_HTML,
    ID_CHAPTER: ID_CHAPTER_HTML.replace("  </table>", ID_SECTION_3003_ROW, 1),
    f"{ID_SECTION_DIR}/63-3002.html": ID_SECTION_HTML,
    ID_SECTION_3003: ID_SECTION_HTML.replace("63-3002", "63-3003"),
}
ID_EXTRACTED = {
    "us-id/statute/title-63",
    "us-id/statute/title-63/chapter-30",
    "us-id/statute/title-63/chapter-31",
    "us-id/statute/63-3002",
    "us-id/statute/63-3003",
}


def _extract_idaho(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_idaho_statutes(
        store,
        version="2026-05-09",
        source_dir=tmp_path / "source",
        expression_date="2025-07-01",
        only_title="63",
        workers=1,
    )
    return store, report


@pytest.mark.parametrize("failure", SECTION_FAILURES)
def test_idaho_failed_section_page_remains_inventory_gap(tmp_path, failure):
    # On main a section page that could not be fetched or read was logged as an
    # error with no inventory item, so coverage still read complete.
    pages = dict(ID_GOOD_PAGES)
    _fail_page(pages, ID_SECTION_3003, failure)
    store, report = _extract_idaho(tmp_path, pages)
    assert report.section_count == 1
    assert "section 63-3003" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=ID_EXTRACTED,
        missing={"us-id/statute/63-3003"},
        gap_source=ID_CHAPTER if failure == "missing-file" else ID_SECTION_3003,
    )


def test_idaho_repealed_section_page_stays_complete(tmp_path):
    pages = dict(ID_GOOD_PAGES)
    pages[ID_SECTION_3003] = ID_SECTION_HTML.replace("63-3002", "63-3003").replace(
        "Declaration of intent.</span> The income tax act applies with section 63-3003.",
        "Repealed.</span> [63-3003, repealed 2020, ch. 1, sec. 1.]",
    )
    _, report = _extract_idaho(tmp_path, pages)
    assert report.section_count == 2
    _assert_complete(report, expected=ID_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-id/statute/63-3003"].metadata["status"] == "repealed"


# --- Montana: index -> title -> chapter -> part -> section pages ---

MT_SECTION_2101 = "title_0150/chapter_0300/part_0210/section_0010/0150-0300-0210-0010.html"
MT_EXTRACTED = {
    "us-mt/statute/15",
    "us-mt/statute/15-30",
    "us-mt/statute/15-30-21",
    "us-mt/statute/15-30-2101",
    "us-mt/statute/15-30-2110",
}


def _extract_montana(tmp_path, failure: str | None):
    source = tmp_path / "source"
    source.mkdir()
    mt_write_fixture_tree(source)
    if failure == "missing-file":
        (source / MT_SECTION_2101).unlink()
    elif failure is not None:
        (source / MT_SECTION_2101).write_text(
            {"maintenance": MAINTENANCE, "empty": EMPTY_PAGE, "wrong-shape": WRONG_SHAPE_HTML}[
                failure
            ],
            encoding="utf-8",
        )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_montana_code(
        store, version="2026-05-05", source_dir=source, only_title="15", workers=1
    )
    return store, report


def test_montana_fixture_extracts_complete(tmp_path):
    _, report = _extract_montana(tmp_path, None)
    assert report.section_count == 2
    _assert_complete(report, expected=MT_EXTRACTED)


@pytest.mark.parametrize("failure", ["maintenance", "empty", "wrong-shape"])
def test_montana_unreadable_section_page_remains_inventory_gap(tmp_path, failure):
    # On main a section page with no section content was logged as an error with
    # no inventory item, so coverage still read complete.
    store, report = _extract_montana(tmp_path, failure)
    assert report.section_count == 1
    assert "section 15-30-2101" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MT_EXTRACTED,
        missing={"us-mt/statute/15-30-2101"},
        gap_source=MT_SECTION_2101,
    )


def test_montana_unfetchable_section_page_still_stops_the_run(tmp_path):
    # Montana fetches every page of a level before parsing it, and a page it
    # cannot fetch stops the run: a loud failure, not a silent loss.
    with pytest.raises(ValueError, match="does not exist"):
        _extract_montana(tmp_path, "missing-file")


# --- New York (Senate pages): law index -> law -> article -> part -> sections ---

NY_LAW_TREE = {
    "us-ny/statute/TAX",
    "us-ny/statute/TAX/A22",
    "us-ny/statute/TAX/A22P1",
    "us-ny/statute/TAX/601",
    "us-ny/statute/TAX/602",
}


def _extract_new_york(
    tmp_path,
    *,
    missing: str | None = None,
    pages: dict[str, str] | None = None,
    only_title: str | None = "TAX",
    workers=1,
):
    source = ny_write_fixture_tree(tmp_path)
    if missing is not None:
        (source / "new-york-senate-html" / missing).unlink(missing_ok=True)
    _write_sources(source / "new-york-senate-html", pages or {})
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_new_york_consolidated_laws(
        store,
        version="2026-test",
        source_dir=source,
        only_title=only_title,
        workers=workers,
        source_as_of="2026-01-30",
        expression_date="2026-01-30",
    )
    return store, report


@pytest.mark.parametrize("workers", [1, 4])
def test_new_york_unfetched_section_page_remains_inventory_gap(tmp_path, workers):
    # On main a page the crawl could not fetch was logged as an error with no
    # inventory item, so coverage still read complete. Four workers fetch the
    # part's sibling sections in parallel.
    store, report = _extract_new_york(tmp_path, missing="TAX/602.html", workers=workers)
    assert report.section_count == 1
    assert "TAX/602" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=NY_LAW_TREE,
        missing={"us-ny/statute/TAX/602"},
        gap_source="new-york-senate-html/TAX/A22P1.html",
    )


@pytest.mark.parametrize("workers", [1, 4])
@pytest.mark.parametrize("failure", ["maintenance", "empty", "wrong-shape"])
def test_new_york_section_page_without_section_remains_inventory_gap(tmp_path, failure, workers):
    # On main a page with no section headline parsed as a container, so a
    # maintenance, empty or wrong-shape page behind a "SECTION 602" link was
    # written as a container with no text and coverage still read complete.
    pages: dict[str, str] = {}
    _fail_page(pages, "TAX/602.html", failure)
    store, report = _extract_new_york(tmp_path, pages=pages, workers=workers)
    assert report.section_count == 1
    assert report.errors == (
        "https://www.nysenate.gov/legislation/laws/TAX/602: "
        "expected a section, page has no headline",
    )
    _assert_visible_gaps(
        store,
        report,
        expected=NY_LAW_TREE,
        missing={"us-ny/statute/TAX/602"},
        gap_source="new-york-senate-html/TAX/602.html",
    )


@pytest.mark.parametrize("workers", [1, 4])
def test_new_york_section_link_to_another_node_remains_inventory_gap(tmp_path, workers):
    # The article page links on to its part; the crawl does not follow links
    # from a page that stands in for a section.
    store, report = _extract_new_york(
        tmp_path, pages={"TAX/602.html": NY_ARTICLE_HTML}, workers=workers
    )
    assert report.errors == (
        "https://www.nysenate.gov/legislation/laws/TAX/602: "
        "expected a section, page has headline ARTICLE 22",
    )
    _assert_visible_gaps(
        store,
        report,
        expected=NY_LAW_TREE,
        missing={"us-ny/statute/TAX/602"},
        gap_source="new-york-senate-html/TAX/602.html",
    )


def test_new_york_section_page_without_text_stays_complete(tmp_path):
    _, report = _extract_new_york(tmp_path, pages={"TAX/602.html": NY_EMPTY_SECTION_602})
    assert report.section_count == 2
    _assert_complete(report, expected=NY_LAW_TREE)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-ny/statute/TAX/602"].kind == "section"
    assert records["us-ny/statute/TAX/602"].body is None


def test_new_york_unfetched_container_page_remains_inventory_gap(tmp_path):
    store, report = _extract_new_york(tmp_path, missing="TAX/A22P1.html")
    _assert_visible_gaps(
        store,
        report,
        expected={"us-ny/statute/TAX", "us-ny/statute/TAX/A22", "us-ny/statute/TAX/A22P1"},
        missing={"us-ny/statute/TAX/A22P1"},
        gap_source="new-york-senate-html/TAX/A22.html",
    )


def test_new_york_unfetched_law_page_remains_inventory_gap(tmp_path):
    # The fixture index lists ABC and TAX but holds no ABC page, so a full run
    # cannot fetch ABC; its gap is sourced from the consolidated-laws index.
    store, report = _extract_new_york(tmp_path, missing="ABC/index.html", only_title=None)
    _assert_visible_gaps(
        store,
        report,
        expected=NY_LAW_TREE | {"us-ny/statute/ABC"},
        missing={"us-ny/statute/ABC"},
        gap_source="new-york-senate-html/CONSOLIDATED.html",
    )


def test_new_york_run_that_fetches_nothing_still_fails(tmp_path):
    with pytest.raises(ValueError, match="no New York provisions extracted"):
        _extract_new_york(tmp_path, missing="TAX/index.html")


# --- New York (OpenLegislation): targeted section documents ---

NY_OPENLEG_614 = "new-york-openleg-json/TAX/614.json"
NY_OPENLEG_SECTIONS = {"us-ny/statute/TAX/601", "us-ny/statute/TAX/614"}
NY_OPENLEG_UNREADABLE = {
    "maintenance": MAINTENANCE,
    "empty": EMPTY_PAGE,
    "no-result": json.dumps({"success": True}),
    "wrong-shape": json.dumps(
        {"success": True, "result": {"lawId": "TAX", "locationId": "614", "docType": "ARTICLE"}}
    ),
    "no-text": json.dumps(
        {"success": True, "result": {"lawId": "TAX", "locationId": "614", "docType": "SECTION"}}
    ),
}


def _extract_new_york_sections(tmp_path, source):
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_new_york_openleg_sections(
        store,
        version="2026-test",
        sections=("TAX:601", "TAX:614"),
        source_dir=source,
        source_as_of="2026-01-30",
        expression_date="2026-01-30",
    )
    return store, report


@pytest.mark.parametrize("failure", sorted(NY_OPENLEG_UNREADABLE))
def test_new_york_unreadable_openleg_section_remains_inventory_gap(tmp_path, failure):
    # On main an HTML or empty response stopped the run on a JSON error, and a
    # response with no section was logged as an error with no inventory item.
    source = ny_write_openleg_section_fixture(tmp_path)
    (source / NY_OPENLEG_614).write_text(NY_OPENLEG_UNREADABLE[failure], encoding="utf-8")
    store, report = _extract_new_york_sections(tmp_path, source)
    assert report.section_count == 1
    assert report.errors[0].startswith("TAX 614: ")
    _assert_visible_gaps(
        store,
        report,
        expected=NY_OPENLEG_SECTIONS,
        missing={"us-ny/statute/TAX/614"},
        gap_source=NY_OPENLEG_614,
    )


def test_new_york_unfetchable_openleg_section_stops_the_run(tmp_path, monkeypatch):
    # A targeted run has no listing to source a gap from, so a section it cannot
    # fetch fails the run. On main it was logged and coverage read complete.
    source = ny_write_openleg_section_fixture(tmp_path)
    fetch = new_york._NewYorkOpenLegFetcher.fetch_law_document

    def fail_614(self, law_id, location_id):
        if location_id == "614":
            raise requests.ConnectionError("connection reset")
        return fetch(self, law_id, location_id)

    monkeypatch.setattr(new_york._NewYorkOpenLegFetcher, "fetch_law_document", fail_614)
    with pytest.raises(ValueError, match="could not be fetched: TAX 614: connection reset"):
        _extract_new_york_sections(tmp_path, source)


# --- NYC Administrative Code: targeted CodeLibrary section pages ---

NYC_SECTION_1706 = NYC_SECTION_HTML.replace("11-1701", "11-1706")
NYC_URLS = (
    "11-1701=https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13463",
    "11-1706=https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13608",
)
NYC_1706_PAGE = "nyc-admin-code-amlegal-html/11-1706/0-0-0-13608.html"
NYC_SECTIONS = {"us-ny/statute/NYC/11-1701", "us-ny/statute/NYC/11-1706"}


def _extract_nyc(tmp_path, failure: str | None):
    pages = {
        "nyc-admin-code-amlegal-html/11-1701/0-0-0-13463.html": NYC_SECTION_HTML,
        NYC_1706_PAGE: NYC_SECTION_1706,
    }
    if failure is not None:
        _fail_page(pages, NYC_1706_PAGE, failure)
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_nyc_admin_code(
        store,
        version="2026-06-05",
        sections=(),
        urls=NYC_URLS,
        source_dir=tmp_path / "source",
    )
    return store, report


def test_nyc_fixture_extracts_complete(tmp_path):
    _, report = _extract_nyc(tmp_path, None)
    _assert_complete(report, expected=NYC_SECTIONS)


@pytest.mark.parametrize("failure", ["maintenance", "empty", "wrong-shape"])
def test_nyc_unreadable_section_page_remains_inventory_gap(tmp_path, failure):
    # On main a page with no section heading or body was logged as an error with
    # no inventory item, so coverage still read complete.
    store, report = _extract_nyc(tmp_path, failure)
    assert report.errors[0].startswith("11-1706: ")
    _assert_visible_gaps(
        store,
        report,
        expected=NYC_SECTIONS,
        missing={"us-ny/statute/NYC/11-1706"},
        gap_source=NYC_1706_PAGE,
    )


def test_nyc_unfetchable_section_page_stops_the_run(tmp_path):
    # A targeted run has no listing to source a gap from, so a section it cannot
    # fetch fails the run. On main it was logged and coverage read complete.
    with pytest.raises(ValueError, match="could not be fetched: 11-1706: "):
        _extract_nyc(tmp_path, "missing-file")


# --- West Virginia: code index -> article JSON -> section pages for sections the article lacks ---

WV_INDEX = f"{WEST_VIRGINIA_INDEX_SOURCE_FORMAT}/wvcodeentire.html"
WV_ARTICLE = f"{WEST_VIRGINIA_ARTICLE_SOURCE_FORMAT}/chapter-2/article-2.json"
WV_SECTION_1A = f"{WEST_VIRGINIA_SECTION_SOURCE_FORMAT}/2-2-1A.html"
WV_SECTION_1A_HTML = (
    '<html><body><div class="sectiontext">'
    "<h4>§2-2-1a. Special memorial days.</h4><p>June 20 is West Virginia Day.</p>"
    "</div></body></html>"
)
WV_EXTRACTED = {
    "us-wv/statute/chapter-2",
    "us-wv/statute/chapter-2/article-2",
    "us-wv/statute/2-2-1",
    "us-wv/statute/2-2-1A",
    "us-wv/statute/2-2-1B",
}


def _wv_article_without(*headings: str) -> str:
    html = WV_ARTICLE_JSON["html"]
    for heading in headings:
        start = html.index(heading)
        end = html.find("<h4>", start + 1)
        html = html[:start] + (html[end:] if end != -1 else "")
    return json.dumps({"html": html})


def _extract_west_virginia(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_west_virginia_code(
        store,
        version="2026-05-08",
        source_dir=tmp_path / "source",
        only_chapter=2,
        only_article=2,
    )
    return store, report


def _wv_pages_without_1a() -> dict[str, str]:
    return {
        WV_INDEX: WV_INDEX_HTML,
        WV_ARTICLE: _wv_article_without("<h4>§2-2-1a."),
        WV_SECTION_1A: WV_SECTION_1A_HTML,
    }


def test_west_virginia_section_page_fills_a_section_the_article_lacks(tmp_path):
    _, report = _extract_west_virginia(tmp_path, _wv_pages_without_1a())
    assert report.section_count == 3
    _assert_complete(report, expected=WV_EXTRACTED)


@pytest.mark.parametrize("failure", SECTION_FAILURES)
def test_west_virginia_failed_section_page_remains_inventory_gap(tmp_path, failure):
    # On main a section with no body in the article and no readable section page
    # was logged and still written as a provision with no text, so coverage
    # read complete.
    pages = _wv_pages_without_1a()
    _fail_page(pages, WV_SECTION_1A, failure)
    store, report = _extract_west_virginia(tmp_path, pages)
    assert report.section_count == 2
    assert "2-2-1A" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=WV_EXTRACTED,
        missing={"us-wv/statute/2-2-1A"},
        gap_source=WV_ARTICLE if failure == "missing-file" else WV_SECTION_1A,
    )


def test_west_virginia_repealed_section_stays_complete(tmp_path):
    # The code index marks 2-2-1b repealed, so the run writes it from the index
    # without a section page.
    pages = {WV_INDEX: WV_INDEX_HTML, WV_ARTICLE: _wv_article_without("<h4>§2-2-1b.")}
    _, report = _extract_west_virginia(tmp_path, pages)
    _assert_complete(report, expected=WV_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-wv/statute/2-2-1B"].metadata["status"] == "repealed"


# --- Illinois (remote): Section Sequence file, ILCS index or act directory -> documents ---

IL_SEQUENCE_URL = f"{ILLINOIS_ILCS_BASE_URL}aReadMe/Section%20Sequence.txt"
IL_ACT_URL = f"{ILLINOIS_ILCS_BASE_URL}Ch%200005/Act%200070/"
IL_ACT_DIR = "Ch 0005/Act 0070"
IL_DOC_LINKS = """
<a href="/ftp/ILCS/Ch%200005/Act%200070/000500700K1.html">Sec. 1</a>
<a href="/ftp/ILCS/Ch%200005/Act%200070/000500700K2.html">Sec. 2</a>
"""
IL_LISTINGS = {
    "sequence": (
        {IL_SEQUENCE_URL: "000500700K1\n000500700K2\n"},
        "illinois-ilcs/aReadMe/Section Sequence.txt",
    ),
    "index": ({ILLINOIS_ILCS_BASE_URL: IL_DOC_LINKS}, "illinois-ilcs/index.html"),
    "directory": (
        {
            ILLINOIS_ILCS_BASE_URL: '<a href="/ftp/ILCS/Ch%200005/">Ch 0005</a>',
            f"{ILLINOIS_ILCS_BASE_URL}Ch%200005/": (
                '<a href="/ftp/ILCS/Ch%200005/Act%200070/">Act 0070</a>'
            ),
            IL_ACT_URL: IL_DOC_LINKS,
        },
        "illinois-ilcs/Ch 0005/Act 0070/index.html",
    ),
}
IL_EXTRACTED = {
    "us-il/statute/5",
    "us-il/statute/5/70",
    "us-il/statute/5/70/1",
    "us-il/statute/5/70/2",
}


class _IllinoisRemote:
    """Serves both ``requests.Session().get`` and module-level ``requests.get``."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.headers: dict[str, str] = {}

    def get(self, url, timeout=None, headers=None):
        del timeout, headers
        if url not in self.pages:
            raise requests.HTTPError(f"404 Client Error: Not Found for url: {url}")
        return IlFakeResponse(self.pages[url])


def _extract_illinois_remote(tmp_path, monkeypatch, pages: dict[str, str], workers: int):
    remote = _IllinoisRemote(pages)
    monkeypatch.setattr(illinois.requests, "Session", lambda: remote)
    monkeypatch.setattr(illinois.requests, "get", remote.get)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_illinois_ilcs(
        store, version="2026-05-01", only_chapter=5, only_act=70, workers=workers
    )
    return store, report


@pytest.mark.parametrize("listing", sorted(IL_LISTINGS))
def test_illinois_complete_remote_run_records_no_listing(tmp_path, monkeypatch, listing):
    pages = {
        **IL_LISTINGS[listing][0],
        f"{ILLINOIS_ILCS_FULLTEXT_URL}?DocName=000500700K1": IL_SECTION_1,
        f"{ILLINOIS_ILCS_FULLTEXT_URL}?DocName=000500700K2": IL_SECTION_2,
    }
    _, report = _extract_illinois_remote(tmp_path, monkeypatch, pages, workers=1)
    _assert_complete(report, expected=IL_EXTRACTED)
    assert [path.name for path in report.source_paths] == ["000500700K1.html", "000500700K2.html"]


@pytest.mark.parametrize("workers", [1, 4])
@pytest.mark.parametrize("listing", sorted(IL_LISTINGS))
def test_illinois_unfetched_remote_section_remains_inventory_gap(
    tmp_path, monkeypatch, listing, workers
):
    # On main a listed section document the remote run could not fetch was
    # logged as an error with no inventory item, so coverage still read complete.
    listing_pages, gap_source = IL_LISTINGS[listing]
    pages = {
        **listing_pages,
        f"{ILLINOIS_ILCS_FULLTEXT_URL}?DocName=000500700K1": IL_SECTION_1,
    }
    store, report = _extract_illinois_remote(tmp_path, monkeypatch, pages, workers)
    assert report.section_count == 1
    assert "000500700K2.html" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=IL_EXTRACTED,
        missing={"us-il/statute/5/70/2"},
        gap_source=gap_source,
    )


def test_illinois_remote_run_that_fetches_no_section_still_fails(tmp_path, monkeypatch):
    # A run whose only inventory items would be gaps writes no provision, so it
    # still fails outright, as on main.
    with pytest.raises(ValueError, match="no Illinois ILCS provisions extracted"):
        _extract_illinois_remote(tmp_path, monkeypatch, dict(IL_LISTINGS["index"][0]), workers=1)


@pytest.mark.parametrize("workers", [1, 4])
@pytest.mark.parametrize("failure", ["maintenance", "empty", "wrong-shape"])
def test_illinois_remote_section_page_naming_no_section_remains_inventory_gap(
    tmp_path, monkeypatch, failure, workers
):
    # On main a fetched section page with no ILCS citation was read under its
    # document's own citation, so a maintenance, empty or wrong-shape page
    # became the section's text and coverage still read complete.
    pages = {
        **IL_LISTINGS["index"][0],
        f"{ILLINOIS_ILCS_FULLTEXT_URL}?DocName=000500700K1": IL_SECTION_1,
    }
    _fail_page(pages, f"{ILLINOIS_ILCS_FULLTEXT_URL}?DocName=000500700K2", failure)
    store, report = _extract_illinois_remote(tmp_path, monkeypatch, pages, workers)
    assert report.section_count == 1
    assert report.errors == (
        f"{IL_ACT_DIR}/000500700K2.html: ILCS section page names no section: 000500700K2",
    )
    _assert_visible_gaps(
        store,
        report,
        expected=IL_EXTRACTED,
        missing={"us-il/statute/5/70/2"},
        gap_source=f"illinois-ilcs/{IL_ACT_DIR}/000500700K2.html",
    )


# --- Illinois (local): ILCS act directory -> section documents ---

IL_GOOD_PAGES = {
    f"{IL_ACT_DIR}/000500700K1.html": IL_SECTION_1,
    f"{IL_ACT_DIR}/000500700K2.html": IL_SECTION_2,
}


def _extract_illinois(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_illinois_ilcs(
        store,
        version="2026-05-01",
        source_dir=tmp_path / "source",
        only_chapter=5,
        only_act=70,
    )
    return store, report


@pytest.mark.parametrize("failure", ["maintenance", "empty", "wrong-shape"])
@pytest.mark.parametrize("section", ["1", "2"])
def test_illinois_section_page_naming_no_section_remains_inventory_gap(tmp_path, section, failure):
    # The first document also supplies the chapter and act, so a failed first
    # page still leaves both containers written.
    relative = f"{IL_ACT_DIR}/000500700K{section}.html"
    pages = dict(IL_GOOD_PAGES)
    _fail_page(pages, relative, failure)
    store, report = _extract_illinois(tmp_path, pages)
    assert report.section_count == 1
    assert report.errors == (
        f"{relative}: ILCS section page names no section: 000500700K{section}",
    )
    _assert_visible_gaps(
        store,
        report,
        expected=IL_EXTRACTED,
        missing={f"us-il/statute/5/70/{section}"},
        gap_source=f"illinois-ilcs/{relative}",
    )


@pytest.mark.parametrize("copy", ["A/000500700K2.html", "Z/000500700K2.html"])
def test_illinois_unreadable_copy_of_a_written_section_stays_complete(tmp_path, copy):
    # Another document supplies section 2, before or after the unreadable copy,
    # so the section is written once and only the copy's error is logged.
    _, report = _extract_illinois(tmp_path, {**IL_GOOD_PAGES, copy: MAINTENANCE})
    assert report.errors == (f"{copy}: ILCS section page names no section: 000500700K2",)
    assert report.coverage.complete is True
    inventory = load_source_inventory(report.inventory_path)
    assert sorted(item.citation_path for item in inventory) == sorted(IL_EXTRACTED)
    section = next(item for item in inventory if item.citation_path == "us-il/statute/5/70/2")
    assert section.source_path is not None
    assert section.source_path.endswith(f"illinois-ilcs/{IL_ACT_DIR}/000500700K2.html")


def test_illinois_repealed_section_page_stays_complete(tmp_path):
    pages = {**IL_GOOD_PAGES, f"{IL_ACT_DIR}/000500700K2.html": IL_REPEALED_SECTION_2}
    _, report = _extract_illinois(tmp_path, pages)
    _assert_complete(report, expected=IL_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-il/statute/5/70/2"].body is not None
    assert "(Repealed)." in records["us-il/statute/5/70/2"].body


def test_illinois_uncited_page_that_names_its_section_stays_complete(tmp_path):
    # A page without an ILCS citation still reads under its document's
    # citation when a line opens with the section's heading.
    pages = {
        **IL_GOOD_PAGES,
        f"{IL_ACT_DIR}/000500700K2.html": "<html><body><p>Sec. 2.</p></body></html>",
    }
    _, report = _extract_illinois(tmp_path, pages)
    _assert_complete(report, expected=IL_EXTRACTED)
    records = {r.citation_path: r for r in load_provisions(report.provisions_path)}
    assert records["us-il/statute/5/70/2"].body == "Sec. 2."
