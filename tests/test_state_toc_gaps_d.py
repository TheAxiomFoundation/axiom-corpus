"""A failed table of contents stays a visible coverage gap (axiom-corpus#890).

Batch D: Minnesota, Nebraska, Washington, the District of Columbia, Rhode
Island, South Dakota, Utah and Wisconsin.

Each case gives one container a listing the run cannot use: the page cannot be
fetched, is a maintenance or empty page, has the wrong shape, or lists no
children. Its children are never seen, so the container itself must be the
gap: an error, an inventory item with no provision, and incomplete coverage
under strict release validation. A container that could not be fetched is
sourced from the parent listing that names it; one that was fetched but is
unusable is sourced from its own page.

Containers that list nothing by law (repealed, reserved, or whose only children
are not yet in force) stay complete, and an interrupt during a fetch still stops
the run.
"""

import pytest
import requests

from axiom_corpus.corpus import states
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.states import (
    extract_minnesota_statutes,
    extract_nebraska_revised_statutes,
)
from tests.test_corpus_states import (
    SAMPLE_MINNESOTA_CHAPTER,
    SAMPLE_MINNESOTA_INDEX,
    SAMPLE_MINNESOTA_PART,
    SAMPLE_NEBRASKA_CHAPTER,
    SAMPLE_NEBRASKA_INDEX,
)
from tests.test_state_extraction_gaps import MAINTENANCE, _assert_visible_gaps, _write_sources

EMPTY_PAGE = ""
WRONG_SHAPE_HTML = (
    "<html><body><main><h1>Search results</h1><p>No entries.</p></main></body></html>"
)
# "missing-file" is a --source-dir page that is not there; "request-error" is a
# live fetch that fails. Both stand in for a page that could not be fetched.
PAGE_FAILURES = ["maintenance", "empty", "wrong-shape", "no-children"]
FETCH_FAILURES = ["missing-file", "request-error"]
TOC_FAILURES = FETCH_FAILURES + PAGE_FAILURES


def _page_for(failure: str, bodies: dict[str, str]) -> str:
    return {
        "maintenance": MAINTENANCE,
        "empty": EMPTY_PAGE,
        "wrong-shape": WRONG_SHAPE_HTML,
        **bodies,
    }[failure]


def _fail_page(pages: dict[str, str], relative: str, failure: str, bodies: dict[str, str]) -> None:
    """Make ``relative`` unusable; a fetch failure removes it from the pages."""
    if failure in FETCH_FAILURES:
        pages.pop(relative, None)
        return
    pages[relative] = _page_for(failure, bodies)


def _report_paths(report) -> tuple[set[str], set[str]]:
    inventory = {item.citation_path for item in load_source_inventory(report.inventory_path)}
    provisions = {record.citation_path for record in load_provisions(report.provisions_path)}
    return inventory, provisions


# --- Minnesota: index -> part pages -> full chapter pages ---

MN_TAX_PART = "minnesota-statutes-html/parts/taxation.html"
MN_INDEX = SAMPLE_MINNESOTA_INDEX.replace(
    "  </table>",
    '    <tr>\n      <td><a href="/statutes/part/TAXATION">270 - 297I</a></td>\n'
    "      <td>TAXATION</td>\n    </tr>\n  </table>",
)
MN_GOOD_PAGES = {
    "minnesota-statutes-html/index.html": MN_INDEX,
    "minnesota-statutes-html/parts/public-welfare-and-related-activities.html": SAMPLE_MINNESOTA_PART,
    "minnesota-statutes-html/chapters/chapter-256B.html": SAMPLE_MINNESOTA_CHAPTER,
    MN_TAX_PART: SAMPLE_MINNESOTA_PART.replace("256B", "290").replace(
        "Medical Assistance", "Income Tax"
    ),
    "minnesota-statutes-html/chapters/chapter-290.html": SAMPLE_MINNESOTA_CHAPTER.replace(
        "256B", "290"
    ).replace("MEDICAL ASSISTANCE", "INCOME TAX"),
}
MN_WELFARE = {
    "us-mn/statute/part-public-welfare-and-related-activities",
    "us-mn/statute/256B",
    "us-mn/statute/256B.01",
    "us-mn/statute/256B.02",
}
MN_EMPTY_PART = "<html><body><table><tr><td>No chapters</td></tr></table></body></html>"
MN_EMPTY_CHAPTER = (
    '<html><body><div id="xtend" class="statute">'
    '<h2 class="chapter_title">CHAPTER 290. INCOME TAX</h2></div></body></html>'
)


def _extract_minnesota(tmp_path, monkeypatch, pages, *, failed=None, failure=None, raise_=None):
    """Run Minnesota from ``pages``; a request error or an interrupt hits ``failed``.

    A fetch failure that is not a missing --source-dir file runs the live path,
    which reads the same pages through a stubbed loader.
    """
    if failure != "request-error" and raise_ is None:
        _write_sources(tmp_path / "source", pages)
        source_dir = tmp_path / "source"
    else:
        source_dir = None

        def load(session, source_root, download_root, *, relative_name, url):
            if relative_name == failed:
                if raise_ is not None:
                    raise raise_
                raise requests.ConnectionError("source unavailable")
            return pages[relative_name].encode()

        monkeypatch.setattr(states, "_load_minnesota_html", load)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_minnesota_statutes(
        store, version="2026-05-01", source_dir=source_dir, workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_minnesota_failed_part_toc_remains_inventory_gap(tmp_path, monkeypatch, failure):
    pages = dict(MN_GOOD_PAGES)
    _fail_page(pages, MN_TAX_PART, failure, {"no-children": MN_EMPTY_PART})
    store, report = _extract_minnesota(
        tmp_path, monkeypatch, pages, failed=MN_TAX_PART, failure=failure
    )
    assert report.section_count == 2
    assert "TAXATION" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MN_WELFARE | {"us-mn/statute/part-taxation"},
        missing={"us-mn/statute/part-taxation"},
        gap_source=(
            "minnesota-statutes-html/index.html" if failure in FETCH_FAILURES else MN_TAX_PART
        ),
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_minnesota_failed_chapter_toc_remains_inventory_gap(tmp_path, monkeypatch, failure):
    failed = "minnesota-statutes-html/chapters/chapter-290.html"
    pages = dict(MN_GOOD_PAGES)
    _fail_page(pages, failed, failure, {"no-children": MN_EMPTY_CHAPTER})
    store, report = _extract_minnesota(tmp_path, monkeypatch, pages, failed=failed, failure=failure)
    assert report.section_count == 2
    assert "290" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MN_WELFARE | {"us-mn/statute/part-taxation", "us-mn/statute/290"},
        missing={"us-mn/statute/290"},
        gap_source=MN_TAX_PART if failure in FETCH_FAILURES else failed,
    )


@pytest.mark.parametrize(
    "failed",
    [MN_TAX_PART, "minnesota-statutes-html/chapters/chapter-290.html"],
    ids=["part", "chapter"],
)
def test_minnesota_interrupt_during_fetch_stops_the_run(tmp_path, monkeypatch, failed):
    # Only an ordinary fetch error becomes a gap; an interrupt still stops the
    # run, including from the chapter pool with one worker.
    with pytest.raises(KeyboardInterrupt):
        _extract_minnesota(
            tmp_path, monkeypatch, dict(MN_GOOD_PAGES), failed=failed, raise_=KeyboardInterrupt()
        )


def test_minnesota_run_of_only_gaps_still_fails(tmp_path, monkeypatch):
    # The only part page is missing. Main raised FileNotFoundError; the part is
    # now a gap, and a run with no provisions still raises.
    pages = {"minnesota-statutes-html/index.html": SAMPLE_MINNESOTA_INDEX}
    with pytest.raises((OSError, ValueError)):
        _extract_minnesota(tmp_path, monkeypatch, pages)


# --- Nebraska: index -> one full-chapter page per chapter ---

NE_CHAPTER_2 = "nebraska-revised-statutes-html/chapters/chapter-2-full.html"
NE_GOOD_PAGES = {
    "nebraska-revised-statutes-html/index.html": SAMPLE_NEBRASKA_INDEX.replace(
        "</main>",
        '<a href="/laws/browse-chapters.php?chapter=02">Chapter 2 AGRICULTURE</a></main>',
    ),
    "nebraska-revised-statutes-html/chapters/chapter-1-full.html": SAMPLE_NEBRASKA_CHAPTER,
    NE_CHAPTER_2: SAMPLE_NEBRASKA_CHAPTER.replace("1-10", "2-10"),
}
NE_CHAPTER_1 = {"us-ne/statute/1", "us-ne/statute/1/1-101", "us-ne/statute/1/1-105"}
NE_EMPTY_CHAPTER = (
    '<html><body><div class="printwidth"><p>No statutes in this chapter.</p></div></body></html>'
)


def _extract_nebraska(tmp_path, monkeypatch, pages, *, failed=None, failure=None, raise_=None):
    if failure != "request-error" and raise_ is None:
        _write_sources(tmp_path / "source", pages)
        source_dir = tmp_path / "source"
    else:
        source_dir = None

        def load(session, source_root, download_root, *, relative_name, url):
            if relative_name == failed:
                if raise_ is not None:
                    raise raise_
                raise requests.ConnectionError("source unavailable")
            return pages[relative_name].encode()

        monkeypatch.setattr(states, "_load_nebraska_html", load)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_nebraska_revised_statutes(store, version="2026-05-04", source_dir=source_dir)
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_nebraska_failed_chapter_remains_inventory_gap(tmp_path, monkeypatch, failure):
    pages = dict(NE_GOOD_PAGES)
    _fail_page(pages, NE_CHAPTER_2, failure, {"no-children": NE_EMPTY_CHAPTER})
    store, report = _extract_nebraska(
        tmp_path, monkeypatch, pages, failed=NE_CHAPTER_2, failure=failure
    )
    assert report.section_count == 2
    assert report.errors[0].startswith("chapter 2:")
    _assert_visible_gaps(
        store,
        report,
        expected=NE_CHAPTER_1 | {"us-ne/statute/2"},
        missing={"us-ne/statute/2"},
        gap_source=(
            "nebraska-revised-statutes-html/index.html"
            if failure in FETCH_FAILURES
            else NE_CHAPTER_2
        ),
    )


def test_nebraska_interrupt_during_chapter_fetch_stops_the_run(tmp_path, monkeypatch):
    with pytest.raises(KeyboardInterrupt):
        _extract_nebraska(
            tmp_path,
            monkeypatch,
            dict(NE_GOOD_PAGES),
            failed=NE_CHAPTER_2,
            raise_=KeyboardInterrupt(),
        )


def test_nebraska_run_of_only_gaps_still_fails(tmp_path, monkeypatch):
    pages = {"nebraska-revised-statutes-html/index.html": SAMPLE_NEBRASKA_INDEX}
    with pytest.raises(ValueError, match="no Nebraska Revised Statutes provisions extracted"):
        _extract_nebraska(tmp_path, monkeypatch, pages)
