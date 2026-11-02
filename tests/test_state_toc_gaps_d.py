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
    extract_dc_code,
    extract_minnesota_statutes,
    extract_nebraska_revised_statutes,
    extract_washington_rcw,
)
from tests.test_corpus_states import (
    SAMPLE_DC_INDEX,
    SAMPLE_DC_SECTION,
    SAMPLE_MINNESOTA_CHAPTER,
    SAMPLE_MINNESOTA_INDEX,
    SAMPLE_MINNESOTA_PART,
    SAMPLE_NEBRASKA_CHAPTER,
    SAMPLE_NEBRASKA_INDEX,
    SAMPLE_WASHINGTON_CHAPTER,
    SAMPLE_WASHINGTON_INDEX,
    SAMPLE_WASHINGTON_TITLE,
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


# --- Washington: index -> title pages -> full chapter pages ---

WA_TITLE_43 = "washington-rcw-html/titles/title-43.html"
WA_CHAPTER_42_17 = "washington-rcw-html/chapters/chapter-42.17-full.html"
WA_GOOD_PAGES = {
    "washington-rcw-html/index.html": SAMPLE_WASHINGTON_INDEX.replace(
        "    </table>",
        '      <tr><td><a href="default.aspx?Cite=43">Title 43</a></td>'
        "<td>STATE GOVERNMENT--EXECUTIVE</td></tr>\n    </table>",
    ),
    "washington-rcw-html/titles/title-42.html": SAMPLE_WASHINGTON_TITLE.replace(
        "    </table>",
        '      <tr><td><a href="http://app.leg.wa.gov/RCW/default.aspx?cite=42.17">42.17</a></td>'
        "<td>Campaign disclosure.</td></tr>\n    </table>",
    ),
    "washington-rcw-html/chapters/chapter-42.56-full.html": SAMPLE_WASHINGTON_CHAPTER,
    WA_CHAPTER_42_17: SAMPLE_WASHINGTON_CHAPTER.replace("42.56", "42.17").replace(
        "PUBLIC RECORDS ACT", "CAMPAIGN DISCLOSURE"
    ),
    WA_TITLE_43: SAMPLE_WASHINGTON_TITLE.replace("42.56", "43.01")
    .replace("Title 42", "Title 43")
    .replace("Public records act.", "General provisions."),
    "washington-rcw-html/chapters/chapter-43.01-full.html": SAMPLE_WASHINGTON_CHAPTER.replace(
        "42.56", "43.01"
    ),
}
WA_42_56 = {
    "us-wa/statute/42",
    "us-wa/statute/42/42.56",
    "us-wa/statute/42/42.56/42.56.010",
    "us-wa/statute/42/42.56/42.56.020",
}
WA_42_17 = {
    "us-wa/statute/42/42.17",
    "us-wa/statute/42/42.17/42.17.010",
    "us-wa/statute/42/42.17/42.17.020",
}
WA_43 = {
    "us-wa/statute/43",
    "us-wa/statute/43/43.01",
    "us-wa/statute/43/43.01/43.01.010",
    "us-wa/statute/43/43.01/43.01.020",
}
WA_EMPTY_TITLE = (
    '<html><body><h1>Title 43 RCW</h1><div id="contentWrapper" class="title-page">'
    '<h3 class="list-heading">Chapters</h3><table></table></div></body></html>'
)
# A chapter page that names its chapter and carries no section anchors: the
# shape the existing ``_washington_chapter_without_sections`` exemption keeps.
WA_SECTIONLESS_CHAPTER = (
    "<html><body><h1>Chapter 42.17 RCW</h1><h2>CAMPAIGN DISCLOSURE</h2>"
    '<div id="ContentPlaceHolder1_pnlExpanded"><p>Recodified as chapter 42.17A RCW.</p></div>'
    "</body></html>"
)
# Section anchors that do not belong to the chapter parse to no sections.
WA_FOREIGN_ANCHORS = SAMPLE_WASHINGTON_CHAPTER.replace("42.56", "42.99")


def _extract_washington(tmp_path, monkeypatch, pages, *, failed=None, failure=None, raise_=None):
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

        monkeypatch.setattr(states, "_load_washington_html", load)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_washington_rcw(store, version="2026-05-04", source_dir=source_dir, workers=1)
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_washington_failed_title_toc_remains_inventory_gap(tmp_path, monkeypatch, failure):
    pages = dict(WA_GOOD_PAGES)
    _fail_page(pages, WA_TITLE_43, failure, {"no-children": WA_EMPTY_TITLE})
    store, report = _extract_washington(
        tmp_path, monkeypatch, pages, failed=WA_TITLE_43, failure=failure
    )
    assert report.section_count == 4
    assert report.errors[0].startswith("title 43:")
    _assert_visible_gaps(
        store,
        report,
        expected=WA_42_56 | WA_42_17 | {"us-wa/statute/43"},
        missing={"us-wa/statute/43"},
        gap_source="washington-rcw-html/index.html" if failure in FETCH_FAILURES else WA_TITLE_43,
    )


@pytest.mark.parametrize(
    "failure", [*FETCH_FAILURES, "maintenance", "empty", "wrong-shape", "foreign-anchors"]
)
def test_washington_failed_chapter_remains_inventory_gap(tmp_path, monkeypatch, failure):
    pages = dict(WA_GOOD_PAGES)
    _fail_page(pages, WA_CHAPTER_42_17, failure, {"foreign-anchors": WA_FOREIGN_ANCHORS})
    store, report = _extract_washington(
        tmp_path, monkeypatch, pages, failed=WA_CHAPTER_42_17, failure=failure
    )
    assert report.section_count == 4
    assert report.errors[0].startswith("chapter 42.17:")
    _assert_visible_gaps(
        store,
        report,
        expected=WA_42_56 | WA_43 | {"us-wa/statute/42/42.17"},
        missing={"us-wa/statute/42/42.17"},
        gap_source=(
            "washington-rcw-html/titles/title-42.html"
            if failure in FETCH_FAILURES
            else WA_CHAPTER_42_17
        ),
    )


def test_washington_chapter_page_without_sections_stays_complete(tmp_path, monkeypatch):
    # Pins the existing exemption: a chapter page that names its chapter and
    # carries no section anchors (a recodified or wholly repealed chapter) is
    # written as a complete container and counted as a skipped source.
    pages = dict(WA_GOOD_PAGES)
    pages[WA_CHAPTER_42_17] = WA_SECTIONLESS_CHAPTER
    store, report = _extract_washington(tmp_path, monkeypatch, pages)
    assert report.errors == ()
    assert report.skipped_source_count == 1
    assert report.coverage.complete is True
    inventory, provisions = _report_paths(report)
    assert inventory == provisions == WA_42_56 | WA_43 | {"us-wa/statute/42/42.17"}


@pytest.mark.parametrize("failed", [WA_TITLE_43, WA_CHAPTER_42_17], ids=["title", "chapter"])
def test_washington_interrupt_during_fetch_stops_the_run(tmp_path, monkeypatch, failed):
    with pytest.raises(KeyboardInterrupt):
        _extract_washington(
            tmp_path, monkeypatch, dict(WA_GOOD_PAGES), failed=failed, raise_=KeyboardInterrupt()
        )


def test_washington_run_of_only_gaps_still_fails(tmp_path, monkeypatch):
    pages = {"washington-rcw-html/index.html": SAMPLE_WASHINGTON_INDEX}
    with pytest.raises(ValueError, match="no Revised Code of Washington"):
        _extract_washington(tmp_path, monkeypatch, pages)


# --- District of Columbia: per-title index.xml -> section XML files ---

DC_TITLE_2_INDEX = "2/index.xml"
DC_INDEX_TWO_SECTIONS = SAMPLE_DC_INDEX.replace(
    '<xi:include href="./sections/1-101.xml"/>',
    '<xi:include href="./sections/1-101.xml"/>\n    <xi:include href="./sections/1-102.xml"/>',
)
DC_GOOD_PAGES = {
    "1/index.xml": DC_INDEX_TWO_SECTIONS,
    "1/sections/1-101.xml": SAMPLE_DC_SECTION,
    "1/sections/1-102.xml": SAMPLE_DC_SECTION.replace("1-101", "1-102"),
}
DC_TITLE_1 = {
    "us-dc/statute/1",
    "us-dc/statute/1/chapter-1",
    "us-dc/statute/1/1-101",
    "us-dc/statute/1/1-102",
}
DC_EMPTY_TITLE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<container xmlns="https://code.dccouncil.us/schemas/dc-library">'
    "<prefix>Title</prefix><num>2</num><heading>Government Administration.</heading>"
    "</container>"
)


def _extract_dc(tmp_path, pages):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_dc_code(store, version="2026-04-29", source_dir=tmp_path / "source")
    return store, report


@pytest.mark.parametrize("failure", ["missing-file", "maintenance", "empty", "wrong-shape"])
def test_dc_failed_section_file_remains_inventory_gap(tmp_path, failure):
    failed = "1/sections/1-102.xml"
    pages = dict(DC_GOOD_PAGES)
    _fail_page(pages, failed, failure, {})
    store, report = _extract_dc(tmp_path, pages)
    assert report.section_count == 1
    assert "1-102" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=DC_TITLE_1,
        missing={"us-dc/statute/1/1-102"},
        # The title index lists the section; a file that was read but is
        # unusable is its own evidence.
        gap_source=(
            "dc-law-xml/titles/1/index.xml"
            if failure == "missing-file"
            else f"dc-law-xml/titles/{failed}"
        ),
    )


@pytest.mark.parametrize("failure", ["maintenance", "empty", "wrong-shape", "no-children"])
def test_dc_failed_title_index_remains_inventory_gap(tmp_path, failure):
    pages = dict(DC_GOOD_PAGES)
    pages[DC_TITLE_2_INDEX] = _page_for(failure, {"no-children": DC_EMPTY_TITLE})
    store, report = _extract_dc(tmp_path, pages)
    assert report.section_count == 2
    assert report.errors[0].startswith("title 2:")
    _assert_visible_gaps(
        store,
        report,
        expected=DC_TITLE_1 | {"us-dc/statute/2"},
        missing={"us-dc/statute/2"},
        gap_source="dc-law-xml/titles/2/index.xml",
    )


def test_dc_reserved_containers_stay_complete(tmp_path):
    # The title index is the table of contents for every container in it. A
    # container it marks "[Reserved]" lists nothing by law (Title 4, Part D of
    # the official index is one), and so does a whole title marked reserved.
    reserved_part = (
        "<container><prefix>Part</prefix><num>D</num><heading>[Reserved].</heading></container>"
    )
    pages = dict(DC_GOOD_PAGES)
    pages["1/index.xml"] = DC_INDEX_TWO_SECTIONS.replace(
        "  </container>\n</container>", f"  </container>\n  {reserved_part}\n</container>"
    )
    pages[DC_TITLE_2_INDEX] = DC_EMPTY_TITLE.replace("Government Administration.", "[Reserved].")
    store, report = _extract_dc(tmp_path, pages)
    assert report.errors == ()
    assert report.coverage.complete is True
    inventory, provisions = _report_paths(report)
    assert inventory == provisions == DC_TITLE_1 | {"us-dc/statute/1/part-d", "us-dc/statute/2"}


def test_dc_interrupt_while_reading_a_section_stops_the_run(tmp_path, monkeypatch):
    def interrupt(data):
        raise KeyboardInterrupt

    monkeypatch.setattr(states, "_parse_dc_section_xml", interrupt)
    with pytest.raises(KeyboardInterrupt):
        _extract_dc(tmp_path, dict(DC_GOOD_PAGES))


def test_dc_run_of_only_gaps_still_fails(tmp_path):
    # An unparseable title index raised ParseError (a SyntaxError) on main; it
    # is now a gap, and a run with no provisions still raises.
    with pytest.raises((SyntaxError, ValueError)):
        _extract_dc(tmp_path, {"1/index.xml": EMPTY_PAGE})
