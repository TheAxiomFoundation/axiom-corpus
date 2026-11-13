"""A container whose table of contents yields nothing stays a coverage gap.

Follow-up to axiom-corpus#890 for Alaska through Louisiana. A title, chapter or
other container is written as a provision only once its own table of contents
lists children. When the page cannot be fetched, is a maintenance, empty or
wrong-shape page, or lists no children, the run records an error and an
inventory gap, so coverage and strict release validation read incomplete.

A gap is sourced from the page the run could not use, or from the parent
listing that names the container when its page could not be fetched at all.
"""

from pathlib import Path

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters import florida
from axiom_corpus.corpus.state_adapters.alaska import (
    ALASKA_CHAPTER_PRINT_SOURCE_FORMAT,
    ALASKA_TITLE_INDEX_SOURCE_FORMAT,
    ALASKA_TITLE_TOC_SOURCE_FORMAT,
    extract_alaska_statutes,
)
from axiom_corpus.corpus.state_adapters.arizona import (
    ARIZONA_SECTION_SOURCE_FORMAT,
    ARIZONA_TITLE_DETAIL_SOURCE_FORMAT,
    ARIZONA_TITLE_INDEX_SOURCE_FORMAT,
    extract_arizona_revised_statutes,
)
from axiom_corpus.corpus.state_adapters.connecticut import (
    CONNECTICUT_CURRENT_SOURCE_FORMAT,
    CONNECTICUT_SUPPLEMENT_SOURCE_FORMAT,
    extract_connecticut_statutes,
)
from axiom_corpus.corpus.state_adapters.delaware import extract_delaware_code
from axiom_corpus.corpus.state_adapters.florida import (
    FLORIDA_CHAPTER_SOURCE_FORMAT,
    FLORIDA_TITLE_INDEX_SOURCE_FORMAT,
    extract_florida_statutes,
)
from axiom_corpus.corpus.state_adapters.hawaii import (
    HAWAII_CHAPTER_DIRECTORY_SOURCE_FORMAT,
    HAWAII_CHAPTER_INDEX_SOURCE_FORMAT,
    HAWAII_ROOT_INDEX_SOURCE_FORMAT,
    HAWAII_SECTION_SOURCE_FORMAT,
    HAWAII_VOLUME_DIRECTORY_SOURCE_FORMAT,
    extract_hawaii_revised_statutes,
)
from axiom_corpus.corpus.state_adapters.iowa import (
    IOWA_CHAPTER_INDEX_SOURCE_FORMAT,
    IOWA_SECTION_INDEX_SOURCE_FORMAT,
    IOWA_SECTION_PDF_SOURCE_FORMAT,
    IOWA_TITLE_INDEX_SOURCE_FORMAT,
    extract_iowa_code,
)
from axiom_corpus.corpus.state_adapters.kansas import (
    KANSAS_CHAPTER_SOURCE_FORMAT,
    KANSAS_ROOT_SOURCE_FORMAT,
    KANSAS_SECTION_SOURCE_FORMAT,
    extract_kansas_statutes,
)
from axiom_corpus.corpus.state_adapters.louisiana import (
    LOUISIANA_LAWPRINT_SOURCE_FORMAT,
    LOUISIANA_ROOT_TOC_SOURCE_FORMAT,
    LOUISIANA_TITLE_TOC_SOURCE_FORMAT,
    extract_louisiana_revised_statutes,
)
from tests.test_corpus_alaska import (
    SAMPLE_CHAPTER_PRINT_HTML as AK_CHAPTER_PRINT,
)
from tests.test_corpus_alaska import (
    SAMPLE_TITLE_INDEX_HTML as AK_TITLE_INDEX,
)
from tests.test_corpus_alaska import (
    SAMPLE_TITLE_TOC_HTML as AK_TITLE_TOC,
)
from tests.test_corpus_arizona import (
    SAMPLE_SECTION_HTML as AZ_SECTION,
)
from tests.test_corpus_arizona import (
    SAMPLE_TITLE_DETAIL_HTML as AZ_TITLE_DETAIL,
)
from tests.test_corpus_arizona import (
    SAMPLE_TITLE_INDEX_HTML as AZ_TITLE_INDEX,
)
from tests.test_corpus_connecticut import SAMPLE_CHAPTER as CT_CHAPTER
from tests.test_corpus_connecticut import SAMPLE_TITLE as CT_TITLE
from tests.test_corpus_connecticut import SAMPLE_TITLES as CT_TITLES
from tests.test_corpus_delaware import (
    SAMPLE_CHAPTER_WITH_SUBCHAPTERS as DE_CHAPTER_11,
)
from tests.test_corpus_delaware import (
    SAMPLE_DELAWARE_INDEX as DE_INDEX_HTML,
)
from tests.test_corpus_delaware import (
    SAMPLE_DELAWARE_TITLE as DE_TITLE_30,
)
from tests.test_corpus_delaware import (
    SAMPLE_REPEALED_CHAPTER as DE_CHAPTER_14,
)
from tests.test_corpus_delaware import (
    SAMPLE_SUBCHAPTER as DE_SUBCHAPTER_I,
)
from tests.test_corpus_florida import SAMPLE_CHAPTER as FL_CHAPTER_409
from tests.test_corpus_florida import SAMPLE_TITLE_INDEX as FL_TITLE_XXX
from tests.test_corpus_hawaii import (
    SAMPLE_CHAPTER_DIRECTORY_HTML as HI_CHAPTER_DIRECTORY,
)
from tests.test_corpus_hawaii import (
    SAMPLE_CHAPTER_INDEX_HTML as HI_CHAPTER_INDEX,
)
from tests.test_corpus_hawaii import SAMPLE_ROOT_HTML as HI_ROOT
from tests.test_corpus_hawaii import SAMPLE_SECTION_HTML as HI_SECTION
from tests.test_corpus_hawaii import SAMPLE_VOLUME_HTML as HI_VOLUME
from tests.test_corpus_iowa import SAMPLE_CHAPTER_INDEX_HTML as IA_CHAPTER_INDEX
from tests.test_corpus_iowa import SAMPLE_SECTION_INDEX_HTML as IA_SECTION_INDEX
from tests.test_corpus_iowa import SAMPLE_TITLE_INDEX_HTML as IA_TITLE_INDEX
from tests.test_corpus_iowa import _sample_pdf as ia_sample_pdf
from tests.test_corpus_kansas import SAMPLE_CHAPTER_HTML as KS_CHAPTER_1
from tests.test_corpus_kansas import SAMPLE_REPEALED_RANGE_HTML as KS_REPEALED_RANGE
from tests.test_corpus_kansas import SAMPLE_ROOT_HTML as KS_ROOT
from tests.test_corpus_kansas import SAMPLE_SECTION_HTML as KS_SECTION_1_201
from tests.test_corpus_louisiana import SAMPLE_EMPTY_RESERVED_HTML as LA_EMPTY_RESERVED
from tests.test_corpus_louisiana import SAMPLE_ROOT_HTML as LA_ROOT
from tests.test_corpus_louisiana import SAMPLE_SECTION_1_HTML as LA_SECTION_14_1
from tests.test_corpus_louisiana import SAMPLE_SECTION_HTML as LA_SECTION_14_2
from tests.test_corpus_louisiana import SAMPLE_TITLE_HTML as LA_TITLE_14
from tests.test_state_extraction_gaps import MAINTENANCE, _assert_visible_gaps, _write_sources

VERSION = "2026-05-09"
EMPTY_PAGE = ""
WRONG_SHAPE = (
    "<html><body><nav><a href='/'>Home</a><a href='/search'>Search</a></nav>"
    "<main><h1>Statutes</h1><p>No entries.</p></main></body></html>"
)
# "missing-file" is a page the run cannot fetch; "no-children" is a page of the
# right shape whose table of contents lists nothing.
FAILURES = ["missing-file", "maintenance", "empty", "wrong-shape", "no-children"]
_FAILED_BODY = {"maintenance": MAINTENANCE, "empty": EMPTY_PAGE, "wrong-shape": WRONG_SHAPE}


def _fail_page(pages: dict[str, str], relative: str, failure: str, no_children: str) -> None:
    if failure == "missing-file":
        pages.pop(relative, None)
    elif failure == "no-children":
        pages[relative] = no_children
    else:
        pages[relative] = _FAILED_BODY[failure]


def _store(tmp_path: Path) -> CorpusArtifactStore:
    return CorpusArtifactStore(tmp_path / "corpus")


# --- Alaska -----------------------------------------------------------------

AK_INDEX = f"{ALASKA_TITLE_INDEX_SOURCE_FORMAT}/index.html"
AK_TOC_01 = f"{ALASKA_TITLE_TOC_SOURCE_FORMAT}/title-01.html"
AK_TOC_02 = f"{ALASKA_TITLE_TOC_SOURCE_FORMAT}/title-02.html"
AK_PRINT_0105 = f"{ALASKA_CHAPTER_PRINT_SOURCE_FORMAT}/title-01/chapter-01.05.html"
AK_PRINT_0110 = f"{ALASKA_CHAPTER_PRINT_SOURCE_FORMAT}/title-01/chapter-01.10.html"
AK_GOOD = {
    "us-ak/statute/title-01",
    "us-ak/statute/01.05",
    "us-ak/statute/01.05/article-1",
    "us-ak/statute/01.05.006",
    "us-ak/statute/01.05.011",
}
AK_TITLE_02_LINK = (
    '<li><a onclick="loadTOC( 2);" href="javascript:void(0);">'
    "Title 2. Aeronautics. <BR></a></li>\n  </ul>"
)
AK_CHAPTER_10_LINK = (
    '<li><a onclick=loadTOC("01.10"); href=javascript:void(0)>'
    "<b>Chapter 10. General Definitions.<BR></h6></b></a></li>"
)


def _alaska_pages() -> dict[str, str]:
    return {
        AK_INDEX: AK_TITLE_INDEX.replace("</ul>", AK_TITLE_02_LINK, 1),
        AK_TOC_01: AK_TITLE_TOC,
        AK_PRINT_0105: AK_CHAPTER_PRINT,
    }


@pytest.mark.parametrize("failure", FAILURES)
def test_alaska_failed_title_toc_remains_inventory_gap(tmp_path, failure):
    pages = _alaska_pages()
    pages[AK_TOC_02] = ""
    _fail_page(
        pages,
        AK_TOC_02,
        failure,
        '<a onclick=loadTOC("02"); href=javascript:void(0)>Title 2. Aeronautics.</a>',
    )
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_alaska_statutes(store, version=VERSION, source_dir=tmp_path / "source")
    assert report.section_count == 2
    assert "title 02" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=AK_GOOD | {"us-ak/statute/title-02"},
        missing={"us-ak/statute/title-02"},
        gap_source=AK_INDEX if failure == "missing-file" else AK_TOC_02,
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_alaska_failed_chapter_print_remains_inventory_gap(tmp_path, failure):
    pages = _alaska_pages()
    pages[AK_TOC_01] = AK_TITLE_TOC + AK_CHAPTER_10_LINK
    pages[AK_PRINT_0110] = ""
    _fail_page(
        pages,
        AK_PRINT_0110,
        failure,
        '<div class="statute"><b><a name="01.10"> </a>'
        "<h6>Chapter 10. General Definitions.<BR></h6></b></div>",
    )
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_alaska_statutes(
        store, version=VERSION, source_dir=tmp_path / "source", only_title="1"
    )
    assert report.section_count == 2
    assert "chapter 01.10" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=AK_GOOD | {"us-ak/statute/01.10"},
        missing={"us-ak/statute/01.10"},
        gap_source=AK_TOC_01 if failure == "missing-file" else AK_PRINT_0110,
    )


# --- Arizona ----------------------------------------------------------------

AZ_INDEX = f"{ARIZONA_TITLE_INDEX_SOURCE_FORMAT}/index.html"
AZ_DETAIL_1 = f"{ARIZONA_TITLE_DETAIL_SOURCE_FORMAT}/title-1.html"
AZ_DETAIL_3 = f"{ARIZONA_TITLE_DETAIL_SOURCE_FORMAT}/title-3.html"
# Title 2 is listed without a link and headed "THIS TITLE HAS BEEN REPEALED";
# the adapter writes it without fetching anything.
AZ_GOOD = {
    "us-az/statute/title-1",
    "us-az/statute/title-1/chapter-2",
    "us-az/statute/title-1/chapter-2/article-1",
    "us-az/statute/1-201",
    "us-az/statute/title-2",
}
AZ_TITLE_3_ROW = """  <tr>
    <td><input value="3"></td>
    <td><a href="https://www.azleg.gov/arsDetail?title=3">Title 3</a></td>
    <td>Agriculture</td>
  </tr>
</table>"""
AZ_EMPTY_CHAPTER = """
<div id="chapter3" class="accordion">
  <h5>
    <a class="one-sixth first" href="">Chapter 3</a>
    <div class="two-thirds">SUPPLEMENTARY PROVISIONS</div>
    <div class="one-sixth">Sec: 1-301-1-309</div>
  </h5>
  <div></div>
</div>
"""
AZ_EMPTY_ARTICLE = """
    <div class="article">
      <a class="one-sixth first" href="">Article 2</a>
      <span class="five-sixths">Statutes</span>
      <div></div>
    </div>
  </div>
</div>
"""


def _arizona_pages() -> dict[str, str]:
    return {
        AZ_INDEX: AZ_TITLE_INDEX.replace("</table>", AZ_TITLE_3_ROW, 1),
        AZ_DETAIL_1: AZ_TITLE_DETAIL,
        f"{ARIZONA_SECTION_SOURCE_FORMAT}/title-1/1-201.html": AZ_SECTION,
    }


def _extract_arizona(tmp_path: Path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_arizona_revised_statutes(
        store, version=VERSION, source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", FAILURES)
def test_arizona_failed_title_detail_remains_inventory_gap(tmp_path, failure):
    pages = _arizona_pages()
    _fail_page(
        pages,
        AZ_DETAIL_3,
        failure,
        '<html><body><div class="accordion"><h5>Title 3 Agriculture</h5></div></body></html>',
    )
    store, report = _extract_arizona(tmp_path, pages)
    assert report.section_count == 1
    assert "title 3" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=AZ_GOOD | {"us-az/statute/title-3"},
        missing={"us-az/statute/title-3"},
        gap_source=AZ_INDEX if failure == "missing-file" else AZ_DETAIL_3,
    )


def test_arizona_chapter_listing_no_sections_remains_inventory_gap(tmp_path):
    pages = _arizona_pages()
    pages[AZ_INDEX] = AZ_TITLE_INDEX
    pages[AZ_DETAIL_1] = AZ_TITLE_DETAIL + AZ_EMPTY_CHAPTER
    store, report = _extract_arizona(tmp_path, pages)
    chapter = "us-az/statute/title-1/chapter-3"
    assert "chapter 3" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=AZ_GOOD | {chapter},
        missing={chapter},
        gap_source=AZ_DETAIL_1,
    )


def test_arizona_article_listing_no_sections_remains_inventory_gap(tmp_path):
    pages = _arizona_pages()
    pages[AZ_INDEX] = AZ_TITLE_INDEX
    pages[AZ_DETAIL_1] = AZ_TITLE_DETAIL.replace(
        "    </div>\n  </div>\n</div>\n", "    </div>" + AZ_EMPTY_ARTICLE, 1
    )
    assert "Article 2" in pages[AZ_DETAIL_1]
    store, report = _extract_arizona(tmp_path, pages)
    article = "us-az/statute/title-1/chapter-2/article-2"
    assert "article 2" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=AZ_GOOD | {article},
        missing={article},
        gap_source=AZ_DETAIL_1,
    )


def test_arizona_repealed_title_without_link_stays_complete(tmp_path):
    # Pins existing behaviour: the index lists a repealed title with no link
    # to a detail page, and the adapter writes it as a complete container.
    pages = _arizona_pages()
    pages[AZ_INDEX] = AZ_TITLE_INDEX
    store, report = _extract_arizona(tmp_path, pages)
    assert report.errors == ()
    assert report.coverage.complete is True
    assert {item.citation_path for item in load_source_inventory(report.inventory_path)} == AZ_GOOD


# --- Connecticut ------------------------------------------------------------
# Only the current source set: a supplement page may legitimately list only
# what changed, so the supplement keeps its behaviour.

CT_INDEX = f"{CONNECTICUT_CURRENT_SOURCE_FORMAT}/titles.html"
CT_TITLE_12 = f"{CONNECTICUT_CURRENT_SOURCE_FORMAT}/title-12.html"
CT_TITLE_13 = f"{CONNECTICUT_CURRENT_SOURCE_FORMAT}/title-13.html"
CT_CHAPTER_203 = f"{CONNECTICUT_CURRENT_SOURCE_FORMAT}/chapter-203.html"
CT_CHAPTER_204 = f"{CONNECTICUT_CURRENT_SOURCE_FORMAT}/chapter-204.html"
CT_GOOD = {"us-ct/statute/title-12", "us-ct/statute/chapter-203", "us-ct/statute/12-41"}


def _ct_title_row(number: str, heading: str, *, linked: bool = True) -> str:
    designator = f'<span class="toc_ttl_desig">Title {number}</span>'
    name = f'<span class="toc_ttl_name">{heading}</span>'
    if linked:
        designator = f'<a href="title_{number}.htm">{designator}</a>'
        name = f'<a href="title_{number}.htm">{name}</a>'
    return f"<tr><td>{designator}</td><td>{name}</td></tr>\n  </table>"


def _ct_chapter_row(chapter: str, heading: str) -> str:
    return (
        f'<tr><td class="left_40pct"><a class="toc_ch_link" href="chap_{chapter}.htm">'
        f'Chapter {chapter}</a></td><td><a class="toc_ch_link" href="chap_{chapter}.htm">'
        f"{heading}</a></td></tr>\n  </table>"
    )


CT_EMPTY_CHAPTER = """<html><body><div id="chap_204.htm">
  <h2 class="chap-no">CHAPTER 204</h2>
  <h2 class="chap-name">LOCAL LEVY</h2>
</div></body></html>"""


def _connecticut_pages() -> dict[str, str]:
    return {CT_INDEX: CT_TITLES, CT_TITLE_12: CT_TITLE, CT_CHAPTER_203: CT_CHAPTER}


def _extract_connecticut(tmp_path: Path, pages: dict[str, str], **kwargs):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_connecticut_statutes(
        store, version=VERSION, source_dir=tmp_path / "source", include_supplement=False, **kwargs
    )
    return store, report


@pytest.mark.parametrize("failure", FAILURES)
def test_connecticut_failed_title_page_remains_inventory_gap(tmp_path, failure):
    pages = _connecticut_pages()
    pages[CT_INDEX] = CT_TITLES.replace("</table>", _ct_title_row("13", "Highways"), 1)
    _fail_page(
        pages,
        CT_TITLE_13,
        failure,
        '<html><body><h1 class="title-name">HIGHWAYS</h1><table></table></body></html>',
    )
    store, report = _extract_connecticut(tmp_path, pages)
    assert report.section_count == 1
    assert "title 13" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=CT_GOOD | {"us-ct/statute/title-13"},
        missing={"us-ct/statute/title-13"},
        gap_source=CT_INDEX if failure == "missing-file" else CT_TITLE_13,
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_connecticut_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    pages = _connecticut_pages()
    pages[CT_TITLE_12] = CT_TITLE.replace("</table>", _ct_chapter_row("204", "Local Levy"), 1)
    _fail_page(pages, CT_CHAPTER_204, failure, CT_EMPTY_CHAPTER)
    store, report = _extract_connecticut(tmp_path, pages, only_title="12")
    assert report.section_count == 1
    assert "chapter 204" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=CT_GOOD | {"us-ct/statute/chapter-204"},
        missing={"us-ct/statute/chapter-204"},
        gap_source=CT_TITLE_12 if failure == "missing-file" else CT_CHAPTER_204,
    )


def test_connecticut_unlinked_title_stays_complete(tmp_path):
    # Pins existing behaviour: a title the index lists without a link is
    # written as an inactive container without fetching anything.
    pages = _connecticut_pages()
    pages[CT_INDEX] = CT_TITLES.replace(
        "</table>", _ct_title_row("11", "Libraries [Repealed]", linked=False), 1
    )
    store, report = _extract_connecticut(tmp_path, pages)
    assert report.errors == ()
    assert report.coverage.complete is True
    inventory = {item.citation_path for item in load_source_inventory(report.inventory_path)}
    assert inventory == CT_GOOD | {"us-ct/statute/title-11"}


@pytest.mark.parametrize("status", ["Repealed", "Reserved", "Transferred"])
def test_connecticut_chapter_marked_empty_by_law_stays_complete(tmp_path, status):
    # Pins existing behaviour: a chapter the title page marks repealed,
    # reserved or transferred may list no sections and still reads complete.
    pages = _connecticut_pages()
    pages[CT_TITLE_12] = CT_TITLE.replace(
        "</table>", _ct_chapter_row("204", f"Local Levy [{status}]"), 1
    )
    pages[CT_CHAPTER_204] = CT_EMPTY_CHAPTER
    store, report = _extract_connecticut(tmp_path, pages, only_title="12")
    assert report.errors == ()
    assert report.coverage.complete is True
    inventory = {item.citation_path for item in load_source_inventory(report.inventory_path)}
    assert inventory == CT_GOOD | {"us-ct/statute/chapter-204"}


@pytest.mark.parametrize("status", ["Obsolete", "Expired", "Omitted", "Conditionally Repealed"])
def test_connecticut_chapter_marked_other_status_listing_nothing_remains_gap(tmp_path, status):
    # Only repealed, reserved and transferred mean a chapter lists nothing by
    # law. A chapter marked with any other status the adapter reads, whose
    # page lists no sections, is still a gap.
    pages = _connecticut_pages()
    pages[CT_TITLE_12] = CT_TITLE.replace(
        "</table>", _ct_chapter_row("204", f"Local Levy [{status}]"), 1
    )
    pages[CT_CHAPTER_204] = CT_EMPTY_CHAPTER
    store, report = _extract_connecticut(tmp_path, pages, only_title="12")
    assert "chapter 204" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=CT_GOOD | {"us-ct/statute/chapter-204"},
        missing={"us-ct/statute/chapter-204"},
        gap_source=CT_CHAPTER_204,
    )


CT_SUPPLEMENT_CHAPTER_204 = """<html><body><div id="chap_204.htm">
  <h2 class="chap-no">CHAPTER 204</h2>
  <h2 class="chap-name">LOCAL LEVY</h2>
  <p><span class="catchln" id="sec_12-50">Sec. 12-50. Levy of tax.</span> Supplement text.</p>
</div></body></html>"""


def test_connecticut_supplement_does_not_fill_a_current_set_gap(tmp_path):
    # The current chapter 204 page cannot be fetched, so chapter 204 is a gap.
    # The supplement lists chapter 204 and holds its page, but a supplement
    # row must not fill the gap or duplicate the container.
    title_12 = CT_TITLE.replace("</table>", _ct_chapter_row("204", "Local Levy"), 1)
    supplement = CONNECTICUT_SUPPLEMENT_SOURCE_FORMAT
    pages = {
        CT_INDEX: CT_TITLES,
        CT_TITLE_12: title_12,
        CT_CHAPTER_203: CT_CHAPTER,
        f"{supplement}/titles.html": CT_TITLES,
        f"{supplement}/title-12.html": title_12,
        f"{supplement}/chapter-203.html": CT_CHAPTER,
        f"{supplement}/chapter-204.html": CT_SUPPLEMENT_CHAPTER_204,
    }
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_connecticut_statutes(
        store,
        version=VERSION,
        source_dir=tmp_path / "source",
        only_title="12",
        include_supplement=True,
    )
    chapter = "us-ct/statute/chapter-204"
    assert len(report.errors) == 1
    assert "chapter 204" in report.errors[0]
    assert report.coverage.complete is False
    assert report.coverage.missing_from_provisions == (chapter,)
    assert chapter not in report.coverage.duplicate_provision_citations
    assert chapter not in report.coverage.duplicate_source_citations
    inventory = load_source_inventory(report.inventory_path)
    gap = [item for item in inventory if item.citation_path == chapter]
    assert len(gap) == 1
    assert gap[0].source_path is not None
    assert gap[0].source_path.endswith(CT_TITLE_12)
    provisions = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert chapter not in provisions
    assert "us-ct/statute/12-50" in provisions


# --- Delaware ---------------------------------------------------------------
# The fixture's repealed chapter 14 still lists its repealed section stubs, so
# nothing shows a Delaware container that lists nothing by law.

DE_GOOD = {
    "us-de/statute/30",
    "us-de/statute/30/part-ii",
    "us-de/statute/30/11",
    "us-de/statute/30/11/subchapter-i",
    "us-de/statute/30/1101",
    "us-de/statute/30/1102",
    "us-de/statute/30/14",
    "us-de/statute/30/1401-1409",
}
DE_CHAPTER_20A_LINK = (
    '<div class="title-links"><a href="../title30/c020a/index.html">'
    "Chapter 20A. Veterans’ Opportunity Credit</a></div>"
)
DE_SUBCHAPTER_II_LINK = (
    '<div class="title-links"><a href="../../title30/c011/sc02/index.html">'
    "Subchapter II. Resident Individuals</a></div>"
)


def _delaware_pages() -> dict[str, str]:
    return {
        "index.html": DE_INDEX_HTML,
        "title30/index.html": DE_TITLE_30.replace(DE_CHAPTER_20A_LINK, ""),
        "title30/c011/index.html": DE_CHAPTER_11,
        "title30/c011/sc01/index.html": DE_SUBCHAPTER_I,
        "title30/c014/index.html": DE_CHAPTER_14,
    }


def _extract_delaware(tmp_path: Path, pages: dict[str, str], **kwargs):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_delaware_code(store, version=VERSION, source_dir=tmp_path / "source", **kwargs)
    return store, report


def _de_empty_chapter_page(head: str) -> str:
    return (
        '<html><body><div id="content"><div id="TitleHead"><h1>TITLE 30</h1>'
        f'<h3>{head}</h3></div><div id="CodeBody"></div></div></body></html>'
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_delaware_failed_title_page_remains_inventory_gap(tmp_path, failure):
    pages = _delaware_pages()
    _fail_page(
        pages,
        "title1/index.html",
        failure,
        '<html><body><div id="content"><div class="row"><h2>General Provisions</h2>'
        "</div></div></body></html>",
    )
    store, report = _extract_delaware(tmp_path, pages)
    assert report.section_count == 3
    assert "title1/index.html" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=DE_GOOD | {"us-de/statute/1"},
        missing={"us-de/statute/1"},
        gap_source=(
            "delaware-code-html/index.html" if failure == "missing-file" else "title1/index.html"
        ),
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_delaware_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    pages = _delaware_pages()
    pages["title30/index.html"] = DE_TITLE_30
    _fail_page(
        pages,
        "title30/c020a/index.html",
        failure,
        _de_empty_chapter_page("CHAPTER 20A. Veterans’ Opportunity Credit"),
    )
    store, report = _extract_delaware(tmp_path, pages, only_title="30")
    assert report.section_count == 3
    assert "c020a" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=DE_GOOD | {"us-de/statute/30/20A"},
        missing={"us-de/statute/30/20A"},
        gap_source=(
            "title30/index.html" if failure == "missing-file" else "title30/c020a/index.html"
        ),
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_delaware_failed_subchapter_page_remains_inventory_gap(tmp_path, failure):
    pages = _delaware_pages()
    pages["title30/c011/index.html"] = DE_CHAPTER_11.replace(
        "</div>\n</div>\n</body>", DE_SUBCHAPTER_II_LINK + "\n</div>\n</body>", 1
    )
    assert "sc02" in pages["title30/c011/index.html"]
    _fail_page(
        pages,
        "title30/c011/sc02/index.html",
        failure,
        _de_empty_chapter_page("CHAPTER 11. Personal Income Tax").replace(
            "</h3>", "</h3><h4>Subchapter II. Resident Individuals</h4>"
        ),
    )
    store, report = _extract_delaware(tmp_path, pages, only_title="30")
    assert report.section_count == 3
    assert "sc02" in report.errors[0]
    subchapter = "us-de/statute/30/11/subchapter-ii"
    _assert_visible_gaps(
        store,
        report,
        expected=DE_GOOD | {subchapter},
        missing={subchapter},
        gap_source=(
            "title30/c011/index.html"
            if failure == "missing-file"
            else "title30/c011/sc02/index.html"
        ),
    )


# --- Florida ----------------------------------------------------------------
# Florida's titles come from a fixed list in the adapter, not from a fetched
# index page, so a title page that cannot be fetched has no listing to source
# a gap from; that run still stops.

FL_TITLE_XXIX = f"{FLORIDA_TITLE_INDEX_SOURCE_FORMAT}/title-XXIX.html"
FL_TITLE_XXX_PATH = f"{FLORIDA_TITLE_INDEX_SOURCE_FORMAT}/title-XXX.html"
FL_CHAPTER_409_PATH = f"{FLORIDA_CHAPTER_SOURCE_FORMAT}/0400-0499/0409/0409.html"
FL_CHAPTER_410_PATH = f"{FLORIDA_CHAPTER_SOURCE_FORMAT}/0400-0499/0410/0410.html"
FL_GOOD = {
    "us-fl/statute/title-xxx",
    "us-fl/statute/chapter-409",
    "us-fl/statute/chapter-409/part-i",
    "us-fl/statute/409.016",
    "us-fl/statute/409.145",
}
FL_CHAPTER_410_ROW = """<tr valign="top">
  <td nowrap align="Right"><font>
    <a href="index.cfm?App_mode=Display_Statute&URL=0400-0499/0410/0410ContentsIndex.html&StatuteYear=2025">Chapter 410</a>
  </font></td>
  <td class="ChapterTOC"><font>AGING AND ADULT SERVICES</font></td>
</tr>
</table>"""
FL_EMPTY_PART = """  <div class="Part">
    <div class="PartTitle"><div class="PartNumber">PART II</div><span class="PartTitle">OTHER</span></div>
  </div>
</div>
</div>"""


def _florida_pages() -> dict[str, str]:
    return {FL_TITLE_XXX_PATH: FL_TITLE_XXX, FL_CHAPTER_409_PATH: FL_CHAPTER_409}


def _extract_florida(tmp_path: Path, monkeypatch, pages: dict[str, str]):
    monkeypatch.setattr(florida, "FLORIDA_TITLE_ROMANS", ("XXIX", "XXX"))
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_florida_statutes(store, version=VERSION, source_dir=tmp_path / "source")
    return store, report


@pytest.mark.parametrize("failure", [f for f in FAILURES if f != "missing-file"])
def test_florida_failed_title_index_remains_inventory_gap(tmp_path, monkeypatch, failure):
    pages = _florida_pages()
    _fail_page(
        pages,
        FL_TITLE_XXIX,
        failure,
        '<html><body><table><tr><td><a name="TitleXXIX"></a>TITLE XXIX</td>'
        "<td>PUBLIC HEALTH</td></tr></table></body></html>",
    )
    store, report = _extract_florida(tmp_path, monkeypatch, pages)
    assert report.section_count == 2
    assert "title XXIX" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=FL_GOOD | {"us-fl/statute/title-xxix"},
        missing={"us-fl/statute/title-xxix"},
        gap_source=FL_TITLE_XXIX,
    )


def test_florida_unfetchable_title_index_still_stops_the_run(tmp_path, monkeypatch):
    # Pins existing behaviour: with no fetched listing to source a gap from,
    # a title index page that cannot be fetched stops the run.
    with pytest.raises(FileNotFoundError):
        _extract_florida(tmp_path, monkeypatch, _florida_pages())


@pytest.mark.parametrize("failure", FAILURES)
def test_florida_failed_chapter_page_remains_inventory_gap(tmp_path, monkeypatch, failure):
    pages = _florida_pages()
    pages[FL_TITLE_XXIX] = FL_TITLE_XXX.replace("XXX", "XXIX").replace("0409", "0408")
    pages[f"{FLORIDA_CHAPTER_SOURCE_FORMAT}/0400-0499/0408/0408.html"] = FL_CHAPTER_409.replace(
        "409", "408"
    ).replace("TITLE XXX", "TITLE XXIX")
    pages[FL_TITLE_XXX_PATH] = FL_TITLE_XXX.replace("</table>", FL_CHAPTER_410_ROW, 1)
    _fail_page(
        pages,
        FL_CHAPTER_410_PATH,
        failure,
        '<html><body><div class="Chapters"><div class="Chapter"><div class="Title">'
        '<div class="TitleNumber">TITLE XXX</div></div><div class="ChapterTitle">'
        '<div class="ChapterNumber">CHAPTER 410</div></div></div></div></body></html>',
    )
    store, report = _extract_florida(tmp_path, monkeypatch, pages)
    assert report.section_count == 4
    assert "chapter 410" in report.errors[0]
    title_xxix = {
        "us-fl/statute/title-xxix",
        "us-fl/statute/chapter-408",
        "us-fl/statute/chapter-408/part-i",
        "us-fl/statute/408.016",
        "us-fl/statute/408.145",
    }
    _assert_visible_gaps(
        store,
        report,
        expected=FL_GOOD | title_xxix | {"us-fl/statute/chapter-410"},
        missing={"us-fl/statute/chapter-410"},
        gap_source=FL_TITLE_XXX_PATH if failure == "missing-file" else FL_CHAPTER_410_PATH,
    )


def test_florida_part_listing_no_sections_remains_inventory_gap(tmp_path, monkeypatch):
    pages = _florida_pages()
    pages[FL_TITLE_XXIX] = FL_TITLE_XXX.replace("XXX", "XXIX").replace("0409", "0408")
    pages[f"{FLORIDA_CHAPTER_SOURCE_FORMAT}/0400-0499/0408/0408.html"] = FL_CHAPTER_409.replace(
        "409", "408"
    ).replace("TITLE XXX", "TITLE XXIX")
    pages[FL_CHAPTER_409_PATH] = FL_CHAPTER_409.replace(
        "</div>\n</div>\n</body>", FL_EMPTY_PART + "\n</body>", 1
    )
    assert "PART II" in pages[FL_CHAPTER_409_PATH]
    store, report = _extract_florida(tmp_path, monkeypatch, pages)
    part = "us-fl/statute/chapter-409/part-ii"
    assert "part II" in report.errors[0]
    title_xxix = {
        "us-fl/statute/title-xxix",
        "us-fl/statute/chapter-408",
        "us-fl/statute/chapter-408/part-i",
        "us-fl/statute/408.016",
        "us-fl/statute/408.145",
    }
    _assert_visible_gaps(
        store,
        report,
        expected=FL_GOOD | title_xxix | {part},
        missing={part},
        gap_source=FL_CHAPTER_409_PATH,
    )


# --- Hawaii -----------------------------------------------------------------
# A chapter's section files are listed by its directory; its heading comes
# from its chapter index page. The adapter marks a chapter "repealed" from
# that heading, and a repealed chapter may list no section files.

HI_ROOT_PATH = f"{HAWAII_ROOT_INDEX_SOURCE_FORMAT}/index.html"
HI_VOLUME_04 = f"{HAWAII_VOLUME_DIRECTORY_SOURCE_FORMAT}/volume-04.html"
HI_VOLUME_05 = f"{HAWAII_VOLUME_DIRECTORY_SOURCE_FORMAT}/volume-05.html"
HI_DIRECTORY_235 = f"{HAWAII_CHAPTER_DIRECTORY_SOURCE_FORMAT}/volume-04/HRS0235.html"
HI_DIRECTORY_236 = f"{HAWAII_CHAPTER_DIRECTORY_SOURCE_FORMAT}/volume-04/HRS0236.html"
HI_INDEX_235 = f"{HAWAII_CHAPTER_INDEX_SOURCE_FORMAT}/volume-04/HRS0235.html"
HI_INDEX_236 = f"{HAWAII_CHAPTER_INDEX_SOURCE_FORMAT}/volume-04/HRS0236.html"
HI_GOOD = {"us-hi/statute/volume-04", "us-hi/statute/chapter-235", "us-hi/statute/235-55.75"}
HI_VOLUME_05_LINK = '<a href="/hrscurrent/Vol05_Ch0261-0319/">Vol05_Ch0261-0319</a>\n</pre>'
HI_CHAPTER_236_LINK = '<a href="/hrscurrent/Vol04_Ch0201-0257/HRS0236/">HRS0236</a>\n</pre>'
HI_DIRECTORY_236_INDEX_ONLY = (
    "<html><body><pre>"
    '<a href="/hrscurrent/Vol04_Ch0201-0257/HRS0236/HRS_0236-.htm">HRS_0236-.htm</a>'
    "</pre></body></html>"
)


def _chapter_index(chapter: str, heading: str) -> str:
    return (
        '<html><body><div class="WordSection1">'
        f'<p class="RegularParagraphs" align="center"><b>CHAPTER {chapter}</b></p>'
        f'<p class="RegularParagraphs" align="center"><b>{heading}</b></p>'
        "</div></body></html>"
    )


def _hawaii_pages() -> dict[str, str]:
    return {
        HI_ROOT_PATH: HI_ROOT,
        HI_VOLUME_04: HI_VOLUME,
        HI_DIRECTORY_235: HI_CHAPTER_DIRECTORY,
        HI_INDEX_235: HI_CHAPTER_INDEX,
        f"{HAWAII_SECTION_SOURCE_FORMAT}/volume-04/HRS0235/HRS_0235-0055_0007_0005.htm": (
            HI_SECTION
        ),
    }


def _extract_hawaii(tmp_path: Path, pages: dict[str, str], **kwargs):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_hawaii_revised_statutes(
        store, version=VERSION, source_dir=tmp_path / "source", workers=1, **kwargs
    )
    return store, report


@pytest.mark.parametrize("failure", FAILURES)
def test_hawaii_failed_volume_directory_remains_inventory_gap(tmp_path, failure):
    pages = _hawaii_pages()
    pages[HI_ROOT_PATH] = HI_ROOT.replace("</pre>", HI_VOLUME_05_LINK, 1)
    _fail_page(
        pages, HI_VOLUME_05, failure, "<html><body><pre>1/6/2026 3:46 PM</pre></body></html>"
    )
    store, report = _extract_hawaii(tmp_path, pages)
    assert report.section_count == 1
    assert "volume 05" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=HI_GOOD | {"us-hi/statute/volume-05"},
        missing={"us-hi/statute/volume-05"},
        gap_source=HI_ROOT_PATH if failure == "missing-file" else HI_VOLUME_05,
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_hawaii_failed_chapter_directory_remains_inventory_gap(tmp_path, failure):
    pages = _hawaii_pages()
    pages[HI_VOLUME_04] = HI_VOLUME.replace("</pre>", HI_CHAPTER_236_LINK, 1)
    pages[HI_INDEX_236] = _chapter_index("236", "ESTATE AND TRANSFER TAX")
    _fail_page(pages, HI_DIRECTORY_236, failure, HI_DIRECTORY_236_INDEX_ONLY)
    store, report = _extract_hawaii(tmp_path, pages, only_title="04")
    assert report.section_count == 1
    assert "chapter 236" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=HI_GOOD | {"us-hi/statute/chapter-236"},
        missing={"us-hi/statute/chapter-236"},
        gap_source=HI_VOLUME_04 if failure == "missing-file" else HI_DIRECTORY_236,
    )


def test_hawaii_unfetchable_chapter_index_remains_inventory_gap(tmp_path):
    pages = _hawaii_pages()
    pages.pop(HI_INDEX_235)
    pages[HI_VOLUME_04] = HI_VOLUME.replace("</pre>", HI_CHAPTER_236_LINK, 1)
    pages[HI_DIRECTORY_236] = HI_DIRECTORY_236_INDEX_ONLY
    pages[HI_INDEX_236] = _chapter_index("236", "[REPEALED]")
    store, report = _extract_hawaii(tmp_path, pages, only_title="04")
    assert "chapter 235" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected={
            "us-hi/statute/volume-04",
            "us-hi/statute/chapter-235",
            "us-hi/statute/chapter-236",
        },
        missing={"us-hi/statute/chapter-235"},
        gap_source=HI_DIRECTORY_235,
    )


def test_hawaii_repealed_chapter_listing_no_sections_stays_complete(tmp_path):
    # A chapter whose index heading the adapter marks repealed lists nothing
    # by law: its directory holds only the chapter index file.
    pages = _hawaii_pages()
    pages[HI_VOLUME_04] = HI_VOLUME.replace("</pre>", HI_CHAPTER_236_LINK, 1)
    pages[HI_DIRECTORY_236] = HI_DIRECTORY_236_INDEX_ONLY
    pages[HI_INDEX_236] = _chapter_index("236", "[REPEALED]")
    store, report = _extract_hawaii(tmp_path, pages, only_title="04")
    assert report.errors == ()
    assert report.coverage.complete is True
    inventory = {item.citation_path for item in load_source_inventory(report.inventory_path)}
    assert inventory == HI_GOOD | {"us-hi/statute/chapter-236"}


# --- Iowa -------------------------------------------------------------------
# The adapter skips a chapter its title index heads "RESERVED"; the fixture's
# chapter 423 is one.

IA_INDEX = f"{IOWA_TITLE_INDEX_SOURCE_FORMAT}/2026.html"
IA_CHAPTERS_X = f"{IOWA_CHAPTER_INDEX_SOURCE_FORMAT}/title-X.html"
IA_CHAPTERS_XI = f"{IOWA_CHAPTER_INDEX_SOURCE_FORMAT}/title-XI.html"
IA_SECTIONS_422 = f"{IOWA_SECTION_INDEX_SOURCE_FORMAT}/chapter-422.html"
IA_SECTIONS_424 = f"{IOWA_SECTION_INDEX_SOURCE_FORMAT}/chapter-424.html"
IA_GOOD = {"us-ia/statute/title-x", "us-ia/statute/chapter-422", "us-ia/statute/422.1"}
IA_TITLE_XI_ROW = """<tr>
      <td>Title XI - NATURAL RESOURCES (Ch. 455 - 485)</td>
      <td><a href="/law/iowaCode/chapters?title=XI&amp;year=2026">Chapters</a></td>
    </tr>
  </tbody>"""
IA_CHAPTER_424_ROW = """<tr>
      <td>Chapter 424 - ENVIRONMENTAL PROTECTION CHARGE</td>
      <td><a href="/law/iowaCode/sections?codeChapter=424&amp;year=2026">Sections</a></td>
    </tr>
  </tbody>"""
IA_EMPTY_LISTING = '<html><body><table id="iacList"><tbody></tbody></table></body></html>'


def _extract_iowa(tmp_path: Path, pages: dict[str, str], **kwargs):
    source = tmp_path / "source"
    _write_sources(source, pages)
    pdf = source / IOWA_SECTION_PDF_SOURCE_FORMAT / "chapter-422" / "422.1.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(ia_sample_pdf())
    store = _store(tmp_path)
    report = extract_iowa_code(store, version=VERSION, source_dir=source, **kwargs)
    return store, report


def _iowa_pages() -> dict[str, str]:
    return {
        IA_INDEX: IA_TITLE_INDEX,
        IA_CHAPTERS_X: IA_CHAPTER_INDEX,
        IA_SECTIONS_422: IA_SECTION_INDEX,
    }


@pytest.mark.parametrize("failure", FAILURES)
def test_iowa_failed_title_chapter_index_remains_inventory_gap(tmp_path, failure):
    pages = _iowa_pages()
    pages[IA_INDEX] = IA_TITLE_INDEX.replace("</tbody>", IA_TITLE_XI_ROW, 1)
    _fail_page(pages, IA_CHAPTERS_XI, failure, IA_EMPTY_LISTING)
    store, report = _extract_iowa(tmp_path, pages)
    assert report.section_count == 1
    assert "title XI" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=IA_GOOD | {"us-ia/statute/title-xi"},
        missing={"us-ia/statute/title-xi"},
        gap_source=IA_INDEX if failure == "missing-file" else IA_CHAPTERS_XI,
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_iowa_failed_chapter_section_index_remains_inventory_gap(tmp_path, failure):
    pages = _iowa_pages()
    pages[IA_CHAPTERS_X] = IA_CHAPTER_INDEX.replace("</tbody>", IA_CHAPTER_424_ROW, 1)
    _fail_page(pages, IA_SECTIONS_424, failure, IA_EMPTY_LISTING)
    store, report = _extract_iowa(tmp_path, pages, only_title="X")
    assert report.section_count == 1
    assert "chapter 424" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=IA_GOOD | {"us-ia/statute/chapter-424"},
        missing={"us-ia/statute/chapter-424"},
        gap_source=IA_CHAPTERS_X if failure == "missing-file" else IA_SECTIONS_424,
    )


def test_iowa_reserved_chapter_stays_out_of_inventory(tmp_path):
    # Pins existing behaviour: the fixture's "Chapter 423 - RESERVED" row is
    # skipped, fetches nothing and leaves coverage complete.
    store, report = _extract_iowa(tmp_path, _iowa_pages(), only_title="X")
    assert report.errors == ()
    assert report.coverage.complete is True
    assert {item.citation_path for item in load_source_inventory(report.inventory_path)} == IA_GOOD


def test_iowa_title_listing_only_reserved_chapters_stays_complete(tmp_path):
    # A title whose chapter index lists only reserved chapters lists nothing
    # by law: it is written as a complete container with no gap.
    pages = _iowa_pages()
    pages[IA_INDEX] = IA_TITLE_INDEX.replace("</tbody>", IA_TITLE_XI_ROW, 1)
    pages[IA_CHAPTERS_XI] = (
        '<html><body><table id="iacList"><tbody><tr class="reservedChapterRow">'
        "<td>Chapter 455 - RESERVED</td>"
        '<td><a href="/law/iowaCode/sections?codeChapter=455&amp;year=2026">Sections</a></td>'
        "</tr></tbody></table></body></html>"
    )
    store, report = _extract_iowa(tmp_path, pages)
    assert report.errors == ()
    assert report.coverage.complete is True
    inventory = {item.citation_path for item in load_source_inventory(report.inventory_path)}
    assert inventory == IA_GOOD | {"us-ia/statute/title-xi"}


# --- Kansas -----------------------------------------------------------------
# The fixture's repealed article 1 still lists its repealed section range, so
# nothing shows a Kansas container that lists nothing by law. Kansas also
# logged fetch errors without a gap, so each level has a fetch-error case,
# section pages included.

KS_ROOT_PATH = f"{KANSAS_ROOT_SOURCE_FORMAT}/ksa.html"
KS_CHAPTER_1_PATH = f"{KANSAS_CHAPTER_SOURCE_FORMAT}/ksa_ch1.html"
KS_CHAPTER_2_PATH = f"{KANSAS_CHAPTER_SOURCE_FORMAT}/ksa_ch2.html"
KS_SECTION_1_202_PATH = f"{KANSAS_SECTION_SOURCE_FORMAT}/ch01/001_002_0002.html"
KS_GOOD = {
    "us-ks/statute/chapter-1",
    "us-ks/statute/chapter-1/article-1",
    "us-ks/statute/chapter-1/article-2",
    "us-ks/statute/1-101-through-1-109",
    "us-ks/statute/1-201",
}
KS_CHAPTER_2_LINK = (
    '<li><a href="/statutes/ksa_ch2.html">Chapter 2.&mdash;AGRICULTURE</a></li>\n</ul>'
)
KS_EMPTY_ARTICLE = """  <li>
    <a class="collapsed">Article 3.&mdash;PERMITS TO PRACTICE</a>
    <ul></ul>
  </li>
</ul>"""
KS_SECTION_1_202_ITEM = """      <li>
        1-202
        <a href="/statutes/chapters/ch01/001_002_0002.html">Compensation of members.</a>
      </li>
    </ul>
  </li>
</ul>"""


def _kansas_pages() -> dict[str, str]:
    return {
        KS_ROOT_PATH: KS_ROOT,
        KS_CHAPTER_1_PATH: KS_CHAPTER_1,
        f"{KANSAS_SECTION_SOURCE_FORMAT}/ch01/001_001_0001.html": KS_REPEALED_RANGE,
        f"{KANSAS_SECTION_SOURCE_FORMAT}/ch01/001_002_0001.html": KS_SECTION_1_201,
    }


def _extract_kansas(tmp_path: Path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_kansas_statutes(
        store, version=VERSION, source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", FAILURES)
def test_kansas_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    pages = _kansas_pages()
    pages[KS_ROOT_PATH] = KS_ROOT.replace("</ul>", KS_CHAPTER_2_LINK, 1)
    _fail_page(
        pages,
        KS_CHAPTER_2_PATH,
        failure,
        '<html><body><div class="ksa"><h2>Chapter 2.&mdash;AGRICULTURE</h2>'
        '<ul class="handle" id="tree"></ul></div></body></html>',
    )
    store, report = _extract_kansas(tmp_path, pages)
    assert report.section_count == 2
    assert "chapter 2" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=KS_GOOD | {"us-ks/statute/chapter-2"},
        missing={"us-ks/statute/chapter-2"},
        gap_source=KS_ROOT_PATH if failure == "missing-file" else KS_CHAPTER_2_PATH,
    )


def test_kansas_article_listing_no_sections_remains_inventory_gap(tmp_path):
    pages = _kansas_pages()
    pages[KS_CHAPTER_1_PATH] = KS_CHAPTER_1.replace("</ul>\n</div>", KS_EMPTY_ARTICLE + "\n</div>")
    assert "Article 3" in pages[KS_CHAPTER_1_PATH]
    store, report = _extract_kansas(tmp_path, pages)
    article = "us-ks/statute/chapter-1/article-3"
    assert "article 3" in report.errors[0]
    _assert_visible_gaps(
        store, report, expected=KS_GOOD | {article}, missing={article}, gap_source=KS_CHAPTER_1_PATH
    )


@pytest.mark.parametrize("failure", ["missing-file", "maintenance", "empty", "wrong-shape"])
def test_kansas_failed_section_page_remains_inventory_gap(tmp_path, failure):
    pages = _kansas_pages()
    pages[KS_CHAPTER_1_PATH] = KS_CHAPTER_1.replace(
        "    </ul>\n  </li>\n</ul>", KS_SECTION_1_202_ITEM, 1
    )
    assert "001_002_0002" in pages[KS_CHAPTER_1_PATH]
    _fail_page(pages, KS_SECTION_1_202_PATH, failure, "")
    store, report = _extract_kansas(tmp_path, pages)
    assert report.section_count == 2
    assert "1-202" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=KS_GOOD | {"us-ks/statute/1-202"},
        missing={"us-ks/statute/1-202"},
        gap_source=KS_CHAPTER_1_PATH if failure == "missing-file" else KS_SECTION_1_202_PATH,
    )


# --- Louisiana --------------------------------------------------------------
# Louisiana logged title and section fetch errors without a gap, so both
# levels have a fetch-error case. A section page whose printable document is
# empty is still written with a reserved or empty-page status.

LA_ROOT_PATH = f"{LOUISIANA_ROOT_TOC_SOURCE_FORMAT}/folder-75.html"
LA_TITLE_14_PATH = f"{LOUISIANA_TITLE_TOC_SOURCE_FORMAT}/title-14.html"
LA_TITLE_15_PATH = f"{LOUISIANA_TITLE_TOC_SOURCE_FORMAT}/title-15.html"
LA_SECTION_14_3_PATH = f"{LOUISIANA_LAWPRINT_SOURCE_FORMAT}/title-14/78400.html"
LA_GOOD = {"us-la/statute/title-14", "us-la/statute/14:1", "us-la/statute/14:2"}
LA_TITLE_15_ROW = """  <tr>
    <td><a href="Laws_Toc.aspx?folder=89&amp;level=Parent">TITLE 15</a></td>
    <td><a href="Laws_Toc.aspx?folder=89&amp;level=Parent">Criminal Procedure</a></td>
  </tr>
</table>"""
LA_SECTION_14_3_ROW = """  <tr>
    <td><a href="Law.aspx?d=78400">RS 14:3</a></td>
    <td><a href="Law.aspx?d=78400">Interpretation</a></td>
  </tr>
</table>"""


def _louisiana_pages() -> dict[str, str]:
    return {
        LA_ROOT_PATH: LA_ROOT,
        LA_TITLE_14_PATH: LA_TITLE_14,
        f"{LOUISIANA_LAWPRINT_SOURCE_FORMAT}/title-14/78224.html": LA_SECTION_14_1,
        f"{LOUISIANA_LAWPRINT_SOURCE_FORMAT}/title-14/78337.html": LA_SECTION_14_2,
    }


def _extract_louisiana(tmp_path: Path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_louisiana_revised_statutes(
        store, version=VERSION, source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", FAILURES)
def test_louisiana_failed_title_page_remains_inventory_gap(tmp_path, failure):
    pages = _louisiana_pages()
    pages[LA_ROOT_PATH] = LA_ROOT.replace("</table>", LA_TITLE_15_ROW, 1)
    _fail_page(
        pages,
        LA_TITLE_15_PATH,
        failure,
        "<html><body><table><tr>"
        '<td><a href="Law.aspx?d=79000">RS 15</a></td>'
        '<td><a href="Law.aspx?d=79000">TITLE 15. CRIMINAL PROCEDURE</a></td>'
        "</tr></table></body></html>",
    )
    store, report = _extract_louisiana(tmp_path, pages)
    assert report.section_count == 2
    assert "title 15" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=LA_GOOD | {"us-la/statute/title-15"},
        missing={"us-la/statute/title-15"},
        gap_source=LA_ROOT_PATH if failure == "missing-file" else LA_TITLE_15_PATH,
    )


@pytest.mark.parametrize("failure", ["missing-file", "maintenance", "empty", "wrong-shape"])
def test_louisiana_failed_section_page_remains_inventory_gap(tmp_path, failure):
    pages = _louisiana_pages()
    pages[LA_TITLE_14_PATH] = LA_TITLE_14.replace("</table>", LA_SECTION_14_3_ROW, 1)
    _fail_page(pages, LA_SECTION_14_3_PATH, failure, "")
    store, report = _extract_louisiana(tmp_path, pages)
    assert report.section_count == 2
    assert "14:3" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=LA_GOOD | {"us-la/statute/14:3"},
        missing={"us-la/statute/14:3"},
        gap_source=LA_TITLE_14_PATH if failure == "missing-file" else LA_SECTION_14_3_PATH,
    )


def test_louisiana_empty_official_section_page_stays_complete(tmp_path):
    # Pins existing behaviour: a printable page with an empty law document is
    # written as a status-only section, not a gap.
    pages = _louisiana_pages()
    pages[LA_TITLE_14_PATH] = LA_TITLE_14.replace("</table>", LA_SECTION_14_3_ROW, 1)
    pages[LA_SECTION_14_3_PATH] = LA_EMPTY_RESERVED.replace("46:2598", "14:3")
    store, report = _extract_louisiana(tmp_path, pages)
    assert report.errors == ()
    assert report.coverage.complete is True
    inventory = {item.citation_path for item in load_source_inventory(report.inventory_path)}
    assert inventory == LA_GOOD | {"us-la/statute/14:3"}
