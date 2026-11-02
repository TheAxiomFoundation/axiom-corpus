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
from axiom_corpus.corpus.io import load_source_inventory
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
    extract_connecticut_statutes,
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
