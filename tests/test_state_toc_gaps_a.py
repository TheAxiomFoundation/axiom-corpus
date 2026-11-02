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
from axiom_corpus.corpus.state_adapters.alaska import (
    ALASKA_CHAPTER_PRINT_SOURCE_FORMAT,
    ALASKA_TITLE_INDEX_SOURCE_FORMAT,
    ALASKA_TITLE_TOC_SOURCE_FORMAT,
    extract_alaska_statutes,
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
