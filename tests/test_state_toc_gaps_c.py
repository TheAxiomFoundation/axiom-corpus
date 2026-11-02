"""Indiana, Oregon and South Carolina keep a container they cannot read as a coverage gap.

Follow-up to axiom-corpus#951 and #952 for container-level failures that
#953's survey found in no other fix: Indiana titles, Oregon chapters, and
South Carolina titles and chapters. (West Virginia articles follow #953, which
rewrites the same loop.) The run writes a container as a provision only once
its own page lists children. When the run cannot fetch the page, or the page
is a maintenance, empty or wrong-shape page, or lists no children, the run
records an error and an inventory gap, so coverage and release validation
read incomplete.

A gap takes its source from the page the run could not use, or from the parent
listing that names the container when the run could not fetch its page at all.
A container empty by law stays complete: a repealed Indiana title, an Oregon
chapter of former provisions, a repealed or reserved South Carolina chapter.
"""

from pathlib import Path

import pytest

from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters import oregon
from axiom_corpus.corpus.state_adapters.indiana import (
    INDIANA_CODE_SOURCE_FORMAT,
    extract_indiana_code,
)
from axiom_corpus.corpus.state_adapters.oregon import (
    OREGON_ORS_SOURCE_FORMAT,
    extract_oregon_ors,
)
from axiom_corpus.corpus.state_adapters.south_carolina import (
    SOUTH_CAROLINA_SOURCE_FORMAT,
    extract_south_carolina_code,
)
from tests.test_corpus_indiana import SAMPLE_INDIANA_TITLE_HTML as IN_TITLE_6
from tests.test_corpus_oregon import SAMPLE_OREGON_CHAPTER_90 as OR_CHAPTER_90
from tests.test_corpus_oregon import SAMPLE_OREGON_LANDING as OR_LANDING
from tests.test_corpus_oregon import (
    SAMPLE_OREGON_NO_SECTION_CHAPTER as OR_FORMER_CHAPTER_27,
)
from tests.test_corpus_south_carolina import SAMPLE_CHAPTER_HTML as SC_CHAPTER_6
from tests.test_corpus_south_carolina import SAMPLE_MASTER_HTML as SC_MASTER
from tests.test_corpus_south_carolina import SAMPLE_TITLE_HTML as SC_TITLE_12
from tests.test_state_extraction_gaps import MAINTENANCE, _assert_visible_gaps, _write_sources
from tests.test_state_toc_gaps_a import FAILURES, VERSION, _fail_page, _store

# --- Indiana ----------------------------------------------------------------

IN_GOOD = {
    "us-in/statute/6",
    "us-in/statute/6-1.1",
    "us-in/statute/6-1.1-1",
    "us-in/statute/6-1.1-1-1",
    "us-in/statute/6-1.1-1-2-b",
}
IN_TITLE_5 = "us-in/statute/5"
IN_TITLE_5_PAGE = f"{INDIANA_CODE_SOURCE_FORMAT}/2025_Indiana_Code_HTML/5.html"
IN_TITLE_5_HEADING_ONLY = (
    '<html><body><div class="title" id="5"><span id="ic_number">IC 5</span>'
    '<span id="shortdescription">TITLE 5. STATE AND LOCAL ADMINISTRATION</span></div>'
    "</body></html>"
)
# IC 17 as the 2025 Code ZIP ships it: the title heading and a repeal note.
IN_TITLE_17_REPEALED = (
    '<html><body><div class="title" id="17"><span id="ic_number">IC 17</span>'
    '<span id="shortdescription">TITLE 17. REPEALED</span>'
    '<div style="clear: both;"></div></div>'
    "<p><span><i>Repealed by Acts 1982, P.L.127, SEC.2(a).</i></span></p></body></html>"
)
# The Code ZIP and a source directory name a title only by its own file, so
# no listing shows a title whose file is absent: Indiana has no
# "missing-file" case.
IN_FAILURES = [failure for failure in FAILURES if failure != "missing-file"]


def _extract_indiana(tmp_path: Path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    return store, extract_indiana_code(store, version=VERSION, source_dir=tmp_path / "source")


@pytest.mark.parametrize("failure", IN_FAILURES)
def test_indiana_failed_title_page_remains_inventory_gap(tmp_path, failure):
    pages = {"5.html": "", "6.html": IN_TITLE_6}
    _fail_page(pages, "5.html", failure, IN_TITLE_5_HEADING_ONLY)
    store, report = _extract_indiana(tmp_path, pages)
    assert report.section_count == 2
    assert report.errors[0].startswith("title 5: ")
    _assert_visible_gaps(
        store,
        report,
        expected=IN_GOOD | {IN_TITLE_5},
        missing={IN_TITLE_5},
        gap_source=IN_TITLE_5_PAGE,
    )


def test_indiana_repealed_title_listing_nothing_stays_complete(tmp_path):
    _store_, report = _extract_indiana(
        tmp_path, {"6.html": IN_TITLE_6, "17.html": IN_TITLE_17_REPEALED}
    )
    assert report.errors == ()
    assert report.coverage.complete is True
    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert set(records) == IN_GOOD | {"us-in/statute/17"}
    assert records["us-in/statute/17"].heading == "TITLE 17. REPEALED"


def test_indiana_run_that_reads_no_title_still_raises(tmp_path):
    # Intended: a run that writes no provision at all fails outright, as before.
    with pytest.raises(ValueError, match="no Indiana Code provisions extracted"):
        _extract_indiana(tmp_path, {"5.html": MAINTENANCE})


# --- Oregon -----------------------------------------------------------------

OR_LANDING_PAGE = f"{OREGON_ORS_SOURCE_FORMAT}/ORS.aspx"
OR_CHAPTER_91_PAGE = f"{OREGON_ORS_SOURCE_FORMAT}/ors091.html"
OR_GOOD = {
    "us-or/statute/title-10",
    "us-or/statute/chapter-090",
    "us-or/statute/chapter-090/series-general-provisions",
    "us-or/statute/90.100",
    "us-or/statute/90.105",
    "us-or/statute/90.110",
    "us-or/statute/chapter-090/series-landlord-rights-and-obligations",
    "us-or/statute/90.303",
    "us-or/statute/90.303-operative-2028-01-02",
    "us-or/statute/90.304",
}
OR_CHAPTER_91 = "us-or/statute/chapter-091"
OR_CHAPTER_91_NO_SECTIONS = (
    "<!doctype html><html><body><p>Chapter 91 — Tenancy</p><p>2025 EDITION</p>"
    "<p>TENANCY</p><p>PROPERTY RIGHTS AND TRANSACTIONS</p></body></html>"
)


def _extract_oregon(tmp_path: Path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    return store, extract_oregon_ors(store, version=VERSION, source_dir=tmp_path / "source")


# A source directory names a chapter only by its own file, so "missing-file"
# runs live below: discovery finds the chapter, then its page fails.
@pytest.mark.parametrize("failure", [failure for failure in FAILURES if failure != "missing-file"])
def test_oregon_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    pages = {"ORS.aspx": OR_LANDING, "ors090.html": OR_CHAPTER_90, "ors091.html": ""}
    _fail_page(pages, "ors091.html", failure, OR_CHAPTER_91_NO_SECTIONS)
    store, report = _extract_oregon(tmp_path, pages)
    assert report.section_count == 6
    assert report.errors[0].startswith("chapter 091: ")
    _assert_visible_gaps(
        store,
        report,
        expected=OR_GOOD | {OR_CHAPTER_91},
        missing={OR_CHAPTER_91},
        gap_source=OR_CHAPTER_91_PAGE,
    )


def test_oregon_unfetchable_chapter_page_remains_inventory_gap(tmp_path, monkeypatch):
    live_pages = {
        "ORS.aspx": OR_LANDING,
        "ors090.html": OR_CHAPTER_90,
        "ors091.html": OR_CHAPTER_91_NO_SECTIONS,
    }
    fetches: dict[str, int] = {}

    def fake_download(url: str) -> bytes:
        name = url.rsplit("/", 1)[1]
        fetches[name] = fetches.get(name, 0) + 1
        if name not in live_pages:
            raise ValueError(f"failed to fetch Oregon source page {url}: 404 Client Error")
        if name == "ors091.html" and fetches[name] > 1:
            # Discovery saw the chapter; the extraction fetch then fails.
            raise ValueError(f"failed to fetch Oregon source page {url}: 503 Server Error")
        return live_pages[name].encode()

    monkeypatch.setattr(oregon, "_download_oregon_page", fake_download)
    store = _store(tmp_path)
    report = extract_oregon_ors(store, version=VERSION, workers=2)
    assert fetches["ors091.html"] == 2
    assert report.skipped_source_count == 1
    assert report.errors[0].startswith("chapter 091: failed to fetch")
    _assert_visible_gaps(
        store,
        report,
        expected=OR_GOOD | {OR_CHAPTER_91},
        missing={OR_CHAPTER_91},
        gap_source=OR_LANDING_PAGE,
    )
    gap = next(
        item
        for item in load_source_inventory(report.inventory_path)
        if item.citation_path == OR_CHAPTER_91
    )
    assert gap.source_url == f"{oregon.OREGON_ORS_BASE_URL}ors/ors091.html"


def test_oregon_former_provisions_chapter_listing_no_sections_stays_complete(tmp_path):
    _store_, report = _extract_oregon(
        tmp_path,
        {"ORS.aspx": OR_LANDING, "ors090.html": OR_CHAPTER_90, "ors027.html": OR_FORMER_CHAPTER_27},
    )
    assert report.errors == ()
    assert report.coverage.complete is True
    paths = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert paths == OR_GOOD | {"us-or/statute/chapter-027"}


# --- South Carolina ---------------------------------------------------------

SC_MASTER_PAGE = f"{SOUTH_CAROLINA_SOURCE_FORMAT}/statmast.html"
SC_TITLE_11_PAGE = f"{SOUTH_CAROLINA_SOURCE_FORMAT}/title-11.html"
SC_TITLE_12_PAGE = f"{SOUTH_CAROLINA_SOURCE_FORMAT}/title-12.html"
SC_CHAPTER_8_PAGE = f"{SOUTH_CAROLINA_SOURCE_FORMAT}/title-12/chapter-8.html"
SC_TITLE_11 = "us-sc/statute/title-11"
SC_CHAPTER_8 = "us-sc/statute/title-12/chapter-8"
SC_TITLE_11_HTML = (
    "<!doctype html><html><body><table><tr>"
    "<td>CHAPTER 1 - STATE FINANCES GENERALLY</td>"
    '<td><a href="/code/t11c001.php">HTML</a></td>'
    "</tr></table></body></html>"
)
SC_TITLE_11_NO_CHAPTERS = (
    "<!doctype html><html><body>"
    '<div style="font-weight: bold; text-align: center;">Title 11 - Public Finance</div>'
    "<table></table></body></html>"
)
SC_TITLE_11_CHAPTER_1_HTML = (
    '<!doctype html><html><body><div style="text-align: center;">CHAPTER 1</div>'
    '<div style="text-align: center;">State Finances Generally</div><br />'
    '<span style="font-weight: bold;"> SECTION 11-1-10.</span> Fiscal year.<br /><br />'
    "The fiscal year of the State begins on the first day of July.<br /><br />"
    "HISTORY: 1962 Code Section 1-751.<br /><br /></body></html>"
)
SC_CHAPTER_8_HEAD = (
    '<!doctype html><html><body><div style="text-align: center;">CHAPTER 8</div>'
    '<div style="text-align: center;">Income Tax Withholding</div><br />'
)
SC_CHAPTER_8_HTML = (
    SC_CHAPTER_8_HEAD
    + '<span style="font-weight: bold;"> SECTION 12-8-10.</span> Definitions.<br /><br />'
    "As used in this chapter, a withholding agent is an employer.<br /><br />"
    "HISTORY: 1995 Act No. 76, SECTION 1.<br /><br /></body></html>"
)
# The right shape, the chapter's heading, and no section and no note under it.
SC_CHAPTER_8_NO_SECTIONS = SC_CHAPTER_8_HEAD + "</body></html>"
# A chapter empty by law, in the two shapes the live Code uses (chapters 37-8
# and 5-23): a reservation note, and a repeal note under a "[Repealed]" heading.
SC_CHAPTER_8_EMPTY_BY_LAW = {
    "reserved": SC_CHAPTER_8_HEAD + "(Reserved for Future Use)<br /><br /></body></html>",
    "repealed": SC_CHAPTER_8_HEAD.replace("Withholding</div>", "Withholding [Repealed]</div>")
    + "Editor's Note<br /><br />"
    "This Chapter, which included SECTIONS 12-8-10 to 12-8-590, was repealed.<br /><br />"
    "</body></html>",
}
SC_TITLE_11_GOOD = {SC_TITLE_11, "us-sc/statute/title-11/chapter-1", "us-sc/statute/11-1-10"}
SC_TITLE_12_GOOD = {
    "us-sc/statute/title-12",
    "us-sc/statute/title-12/chapter-6",
    "us-sc/statute/12-6-10",
    "us-sc/statute/12-6-20",
    "us-sc/statute/12-6-510",
    SC_CHAPTER_8,
    "us-sc/statute/12-8-10",
}


def _south_carolina_pages() -> dict[str, str]:
    return {
        SC_MASTER_PAGE: SC_MASTER,
        SC_TITLE_11_PAGE: SC_TITLE_11_HTML,
        f"{SOUTH_CAROLINA_SOURCE_FORMAT}/title-11/chapter-1.html": SC_TITLE_11_CHAPTER_1_HTML,
        SC_TITLE_12_PAGE: SC_TITLE_12,
        f"{SOUTH_CAROLINA_SOURCE_FORMAT}/title-12/chapter-6.html": SC_CHAPTER_6,
        SC_CHAPTER_8_PAGE: SC_CHAPTER_8_HTML,
    }


def _extract_south_carolina(tmp_path: Path, pages: dict[str, str], **kwargs):
    _write_sources(tmp_path / "source", pages)
    store = _store(tmp_path)
    report = extract_south_carolina_code(
        store, version=VERSION, source_dir=tmp_path / "source", **kwargs
    )
    return store, report


def test_south_carolina_sample_titles_extract_complete(tmp_path):
    _store_, report = _extract_south_carolina(tmp_path, _south_carolina_pages())
    assert report.errors == ()
    assert report.coverage.complete is True
    paths = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert paths == SC_TITLE_11_GOOD | SC_TITLE_12_GOOD


@pytest.mark.parametrize("failure", FAILURES)
def test_south_carolina_failed_title_page_remains_inventory_gap(tmp_path, failure):
    pages = _south_carolina_pages()
    _fail_page(pages, SC_TITLE_11_PAGE, failure, SC_TITLE_11_NO_CHAPTERS)
    store, report = _extract_south_carolina(tmp_path, pages)
    assert report.section_count == 4
    assert report.skipped_source_count == 1
    assert report.errors[0].startswith("title 11: ")
    _assert_visible_gaps(
        store,
        report,
        expected=SC_TITLE_12_GOOD | {SC_TITLE_11},
        missing={SC_TITLE_11},
        gap_source=SC_MASTER_PAGE if failure == "missing-file" else SC_TITLE_11_PAGE,
    )


@pytest.mark.parametrize("failure", FAILURES)
def test_south_carolina_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    pages = _south_carolina_pages()
    _fail_page(pages, SC_CHAPTER_8_PAGE, failure, SC_CHAPTER_8_NO_SECTIONS)
    store, report = _extract_south_carolina(tmp_path, pages, only_title=12)
    assert report.section_count == 3
    assert report.errors[0].startswith("title 12 chapter 8: ")
    _assert_visible_gaps(
        store,
        report,
        expected=SC_TITLE_12_GOOD - {"us-sc/statute/12-8-10"},
        missing={SC_CHAPTER_8},
        gap_source=SC_TITLE_12_PAGE if failure == "missing-file" else SC_CHAPTER_8_PAGE,
    )


@pytest.mark.parametrize("status", sorted(SC_CHAPTER_8_EMPTY_BY_LAW))
def test_south_carolina_chapter_empty_by_law_stays_complete(tmp_path, status):
    pages = _south_carolina_pages()
    pages[SC_CHAPTER_8_PAGE] = SC_CHAPTER_8_EMPTY_BY_LAW[status]
    _store_, report = _extract_south_carolina(tmp_path, pages, only_title=12)
    assert report.errors == ()
    assert report.coverage.complete is True
    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert set(records) == SC_TITLE_12_GOOD - {"us-sc/statute/12-8-10"}
    metadata = records[SC_CHAPTER_8].metadata
    assert metadata is not None
    assert metadata["status"] == status


def test_south_carolina_title_the_chapter_filter_leaves_out_is_not_a_gap(tmp_path):
    # Intended: a filter is not a failure. Title 11 lists chapters, none of
    # them chapter 6, so the run skips it with a note and coverage stays
    # complete for what the filter selected.
    _store_, report = _extract_south_carolina(tmp_path, _south_carolina_pages(), only_chapter=6)
    assert report.errors == ("title 11: no chapters selected",)
    assert report.coverage.complete is True
    paths = {item.citation_path for item in load_source_inventory(report.inventory_path)}
    assert SC_TITLE_11 not in paths


def test_south_carolina_run_that_reads_no_title_still_raises(tmp_path):
    # Intended: a run that writes no provision at all fails outright, as before.
    pages = _south_carolina_pages()
    pages.pop(SC_TITLE_12_PAGE)
    with pytest.raises(ValueError, match="no South Carolina provisions extracted"):
        _extract_south_carolina(tmp_path, pages, only_title=12)
