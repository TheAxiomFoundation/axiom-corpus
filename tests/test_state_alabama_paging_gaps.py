"""An Alabama section listing that ends early stays a visible coverage gap.

``extract_alabama_code`` pages through every section with the ALISON
``codesOfAlabama`` query and compares the distinct sections it holds with the
``count`` the listing reports. When the listing ends early, every section and
container the run did not fetch is an inventory gap, so coverage reads
incomplete and strict release validation refuses the run. The one exception is
a container the scaffold gives no section beneath it: it holds nothing to
fetch and stays a record, whatever its heading says.

The fixtures follow the live ALISON shapes: the scaffold gives every section a
parent, and some headings carry a status word whether or not the container
holds sections.
"""

import json
from pathlib import Path

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters import alabama
from axiom_corpus.corpus.state_adapters.alabama import (
    ALABAMA_GRAPHQL_SOURCE_FORMAT,
    extract_alabama_code,
)
from tests.test_state_extraction_gaps import _assert_visible_gaps

VERSION = "2026-11-02"
TITLES_SOURCE = f"{ALABAMA_GRAPHQL_SOURCE_FORMAT}/titles.json"

# (code id, parent code id, display id, title)
CONTAINERS = [
    ("T1", None, "1", "Title 1 General Provisions."),
    ("C1", "T1", "1", "Chapter 1 Construction of Code and Statutes."),
    ("C2", "T1", "2", "Chapter 2 Seals."),
    ("T2", None, "2", "Title 2 Agriculture."),
    ("C3", "T2", "1", "Chapter 1 General Provisions."),
    # A status word in the heading, but the container holds sections.
    (
        "R1",
        "T2",
        "2",
        "Chapter 2 Repealed. Regulation of Aeronautics, Aircraft and Airports Generally.",
    ),
    ("C4", "T2", "3", "Chapter 3 Dairy Products."),
    ("A1", "C4", "1", "Article 1 General Provisions."),
    # No section beneath it, under a parent that holds one.
    ("D2", "A1", "2", "Division 2 Hog Cholera."),
    # No section beneath it, with a status word.
    ("A2", "C4", "2", "Article 2 Alabama Dairy Commission. (Repealed)"),
    # Reserved section stubs beneath it.
    ("P2", "C4", "2", "Part 2 Reserved."),
]
# (code id, parent code id, display id)
SECTIONS = [
    ("S1", "C1", "1-1-1"),
    ("S2", "C1", "1-1-2"),
    ("S3", "C2", "1-2-1"),
    ("S4", "C3", "2-1-1"),
    ("S5", "R1", "2-2-1"),
    ("S6", "A1", "2-3-1"),
    ("S7", "P2", "2-3-221"),
]
COUNT = len(SECTIONS)

TITLE_1 = "us-al/statute/title-1"
CHAPTER_1_1 = "us-al/statute/title-1/chapter-1"
CHAPTER_1_2 = "us-al/statute/title-1/chapter-2"
TITLE_2 = "us-al/statute/title-2"
CHAPTER_2_1 = "us-al/statute/title-2/chapter-1"
REPEALED_WITH_SECTIONS = "us-al/statute/title-2/chapter-2"
CHAPTER_2_3 = "us-al/statute/title-2/chapter-3"
ARTICLE_2_3_1 = "us-al/statute/title-2/chapter-3/article-1"
EMPTY_DIVISION = "us-al/statute/title-2/chapter-3/article-1/division-2"
EMPTY_REPEALED_ARTICLE = "us-al/statute/title-2/chapter-3/article-2"
RESERVED_PART = "us-al/statute/title-2/chapter-3/part-2"
EMPTY_CONTAINERS = {EMPTY_DIVISION, EMPTY_REPEALED_ARTICLE}
CODE_ROOT = "us-al/statute"


def _section_path(code_id: str) -> str:
    return f"us-al/statute/{next(row[2] for row in SECTIONS if row[0] == code_id)}"


TITLE_1_HELD = {TITLE_1, CHAPTER_1_1, _section_path("S1"), _section_path("S2")}
TITLE_1_PATHS = TITLE_1_HELD | {CHAPTER_1_2, _section_path("S3")}
TITLE_2_MISSING = {
    TITLE_2,
    CHAPTER_2_1,
    REPEALED_WITH_SECTIONS,
    CHAPTER_2_3,
    ARTICLE_2_3_1,
    RESERVED_PART,
} | {_section_path(code_id) for code_id in ("S4", "S5", "S6", "S7")}
TITLE_2_PATHS = TITLE_2_MISSING | EMPTY_CONTAINERS
ALL_PATHS = TITLE_1_PATHS | TITLE_2_PATHS
# After S1 and S2: everything else except the two empty containers.
MISSING_AFTER_S2 = {CHAPTER_1_2, _section_path("S3")} | TITLE_2_MISSING


def _deflated(headers: list[str], rows: list[tuple[str | None, ...]]) -> str:
    lines = ["†".join(headers)]
    lines.extend("†".join(value or "" for value in row) for row in rows)
    return "†∫" + "∫".join(lines)


def _section_title(display: str) -> str:
    return f"Section {display} Heading {display}."


def _section_row(code_id: str) -> dict:
    _, parent, display = next(row for row in SECTIONS if row[0] == code_id)
    return {
        "id": f"g-{code_id}",
        "codeId": code_id,
        "displayId": display,
        "title": _section_title(display),
        "content": f"<p>Text of section {display}.</p>",
        "history": "(Acts 2026, No. 1.)",
        "parentId": parent,
        "type": "Section",
        "isContentNode": True,
        "sectionRange": None,
        "effectiveDate": None,
        "supersessionDate": None,
    }


def _page(code_ids: list[str], *, count: int | None = COUNT) -> dict:
    return {
        "data": {
            "codesOfAlabama": {
                "count": count,
                "data": [_section_row(code_id) for code_id in code_ids],
            }
        }
    }


def _page_name(offset: int, limit: int) -> str:
    return f"{ALABAMA_GRAPHQL_SOURCE_FORMAT}/sections-current-offset-{offset}-limit-{limit}.json"


def _write_source(
    root: Path,
    pages: dict[str, dict | bytes],
    *,
    scaffold_sections: bool = True,
    extra_containers: tuple[tuple[str, str, str, str], ...] = (),
) -> Path:
    source = root / "source"
    (source / ALABAMA_GRAPHQL_SOURCE_FORMAT).mkdir(parents=True)
    containers = [*CONTAINERS, *extra_containers]
    scaffold_rows = [(code_id, parent, display) for code_id, parent, display, _ in containers]
    title_rows = [(code_id, title) for code_id, _, _, title in containers]
    if scaffold_sections:
        scaffold_rows.extend(SECTIONS)
        title_rows.extend((code_id, _section_title(display)) for code_id, _, display in SECTIONS)
    scaffold = _deflated(["codeId", "parentId", "displayId"], scaffold_rows)
    titles = _deflated(
        ["codeId", "title", "sectionRange", "effectiveDate"],
        [(code_id, title, None, None) for code_id, title in title_rows],
    )
    (source / ALABAMA_GRAPHQL_SOURCE_FORMAT / "scaffold.json").write_text(
        json.dumps({"data": {"scaffold": scaffold}})
    )
    (source / TITLES_SOURCE).write_text(json.dumps({"data": {"titles": titles}}))
    for name, payload in pages.items():
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        (source / name).write_bytes(data)
    return source


def _extract(tmp_path: Path, source: Path, **kwargs):
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_alabama_code(
        store,
        version=VERSION,
        source_dir=source,
        source_as_of=VERSION,
        expression_date=VERSION,
        **kwargs,
    )
    return store, report


def _paths(report) -> tuple[list[str], list[str]]:
    inventory = [item.citation_path for item in load_source_inventory(report.inventory_path)]
    records = [record.citation_path for record in load_provisions(report.provisions_path)]
    return inventory, records


EMPTY_PAGE_AFTER_S2 = {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page([])}


# Controls: a complete listing reads complete, as on main.


@pytest.mark.parametrize(
    ("page_size", "pages"),
    [
        (7, {_page_name(0, 7): _page([row[0] for row in SECTIONS])}),
        # The last page is short because it is the last one.
        (
            3,
            {
                _page_name(0, 3): _page(["S1", "S2", "S3"]),
                _page_name(3, 3): _page(["S4", "S5", "S6"]),
                _page_name(6, 3): _page(["S7"]),
            },
        ),
    ],
    ids=["full-pages", "short-last-page"],
)
def test_complete_listing_reads_complete(tmp_path, page_size, pages):
    source = _write_source(tmp_path, pages)
    _, report = _extract(tmp_path, source, page_size=page_size)

    inventory, records = _paths(report)
    assert report.errors == ()
    assert report.coverage.complete is True
    assert set(inventory) == set(records) == ALL_PATHS
    assert len(inventory) == len(records) == len(ALL_PATHS)
    assert report.section_count == COUNT
    assert report.title_count == 2


def test_complete_listing_for_one_title_reads_complete(tmp_path):
    pages = {_page_name(0, 7): _page([row[0] for row in SECTIONS])}
    source = _write_source(tmp_path, pages)
    _, report = _extract(tmp_path, source, page_size=7, only_title="1")

    inventory, records = _paths(report)
    assert report.errors == ()
    assert report.coverage.complete is True
    assert set(inventory) == set(records) == TITLE_1_PATHS


def test_run_capped_by_limit_reads_complete_without_gaps(tmp_path):
    # A --limit run keeps only what it fetched, by design, even though the
    # listing reports more sections than the run holds.
    pages = {_page_name(0, 2): _page(["S1", "S2"])}
    source = _write_source(tmp_path, pages)
    _, report = _extract(tmp_path, source, page_size=7, limit=2)

    inventory, records = _paths(report)
    assert report.errors == ()
    assert report.coverage.complete is True
    assert set(inventory) == set(records) == TITLE_1_HELD


# Lead 1 and lead 2: the listing stops early on an empty or short page, and
# the containers and sections it never fetched must stay in the inventory.


def test_empty_page_before_count_keeps_unfetched_nodes_as_gaps(tmp_path):
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2)
    store, report = _extract(tmp_path, source, page_size=2)

    assert all("2 of 7 sections" in error for error in report.errors)
    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing=MISSING_AFTER_S2,
        gap_source=_page_name(2, 2),
    )


def test_short_page_before_count_keeps_unfetched_nodes_as_gaps(tmp_path):
    pages = {_page_name(0, 3): _page(["S1", "S2"])}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=3)

    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing=MISSING_AFTER_S2,
        gap_source=_page_name(0, 3),
    )


def test_early_end_for_one_title_keeps_that_title_as_gaps(tmp_path):
    # Main raised "no Alabama provisions extracted" here: nothing of title 2
    # was fetched, so the run held no record and wrote nothing.
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2)
    store, report = _extract(tmp_path, source, page_size=2, only_title="2")

    _assert_visible_gaps(
        store,
        report,
        expected=TITLE_2_PATHS,
        missing=TITLE_2_MISSING,
        gap_source=_page_name(2, 2),
    )


# The scaffold's tree, not the heading, decides what holds nothing to fetch.


def test_container_with_no_section_beneath_it_stays_a_record(tmp_path):
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2)
    _, report = _extract(tmp_path, source, page_size=2)

    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    missing = set(report.coverage.missing_from_provisions)
    # With and without a status word in the heading.
    assert set(records) >= EMPTY_CONTAINERS
    assert not EMPTY_CONTAINERS & missing
    # The division's parent holds a section past the end of the listing, so
    # the parent is a gap while the empty division under it stays a record.
    assert ARTICLE_2_3_1 in missing
    assert records[EMPTY_DIVISION].parent_citation_path == ARTICLE_2_3_1
    assert not any(path in error for path in EMPTY_CONTAINERS for error in report.errors)


# Live shapes: childless scaffold nodes with a section number for a
# ``displayId`` whose titles text reads as a container.
SECTION_NUMBERED_NODES = (
    ("A3", "C4", "3", "Article 3 Sex Offenders."),
    (
        "V1",
        "A3",
        "32-6-49.24",
        "Division 32-6-49.24 Disqualification of Person Convicted of Crime Requiring Regi...",
    ),
    ("A4", "C4", "45-46A-60", "Article 45-46A-60 Reserved."),
)
SECTION_NUMBERED_HOLDER = "us-al/statute/title-2/chapter-3/article-3"
SECTION_NUMBERED_GAPS = {
    f"{SECTION_NUMBERED_HOLDER}/division-32-6-49-24",
    "us-al/statute/title-2/chapter-3/article-45-46a-60",
}


def test_childless_section_numbered_node_is_a_gap_and_its_container_holds_it(tmp_path):
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2, extra_containers=SECTION_NUMBERED_NODES)
    store, report = _extract(tmp_path, source, page_size=2)

    missing = MISSING_AFTER_S2 | SECTION_NUMBERED_GAPS | {SECTION_NUMBERED_HOLDER}
    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS | SECTION_NUMBERED_GAPS | {SECTION_NUMBERED_HOLDER},
        missing=missing,
        gap_source=_page_name(2, 2),
    )
    # A childless real container ("Division 2 Hog Cholera.") is still kept.
    records = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert EMPTY_DIVISION in records


def test_section_numbered_nodes_keep_their_records_in_a_complete_listing(tmp_path):
    # The gap rule doesn't change any node's kind or record.
    pages = {_page_name(0, 7): _page([row[0] for row in SECTIONS])}
    source = _write_source(tmp_path, pages, extra_containers=SECTION_NUMBERED_NODES)
    _, report = _extract(tmp_path, source, page_size=7)

    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert report.coverage.complete is True
    assert set(records) == ALL_PATHS | SECTION_NUMBERED_GAPS | {SECTION_NUMBERED_HOLDER}
    assert {records[path].kind for path in SECTION_NUMBERED_GAPS} == {"division", "article"}


def test_status_heading_over_unfetched_sections_is_a_gap(tmp_path):
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2)
    _, report = _extract(tmp_path, source, page_size=2)

    missing = set(report.coverage.missing_from_provisions)
    # "Chapter 2 Repealed. Regulation of ..." and "Part 2 Reserved." hold
    # sections past the end of the listing: they and their sections are gaps.
    assert {REPEALED_WITH_SECTIONS, _section_path("S5")} <= missing
    assert {RESERVED_PART, _section_path("S7")} <= missing


# The run can't place the shortfall: something still marks it.


def test_early_end_with_every_node_held_marks_last_container(tmp_path):
    # The listing reports eight sections; the run holds all seven the titles
    # data names. The container of the last section held marks the shortfall.
    pages = {
        _page_name(0, 7): _page([row[0] for row in SECTIONS], count=8),
        _page_name(7, 7): _page([], count=8),
    }
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=7)

    assert len(report.errors) == 1
    assert report.errors[0].endswith(
        ": sections listing ended with 7 of 8 sections; "
        f"the run can't place the missing ones; marked at {RESERVED_PART}"
    )
    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing={RESERVED_PART},
        gap_source=_page_name(7, 7),
    )


def test_early_end_with_nothing_held_in_title_marks_the_title(tmp_path):
    # A scaffold that names no sections gives every container no section, so
    # nothing in title 2 is a gap and no section of it was fetched.
    pages = {_page_name(0, 2): _page([], count=0)}
    source = _write_source(tmp_path, pages, scaffold_sections=False)
    store, report = _extract(tmp_path, source, page_size=2, only_title="2")

    containers = {TITLE_2, CHAPTER_2_1, REPEALED_WITH_SECTIONS, CHAPTER_2_3, ARTICLE_2_3_1}
    containers |= {RESERVED_PART} | EMPTY_CONTAINERS
    assert "marked at us-al/statute/title-2" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=containers,
        missing={TITLE_2},
        gap_source=_page_name(0, 2),
    )


def test_early_end_with_nothing_held_marks_the_code(tmp_path):
    pages = {_page_name(0, 2): _page([], count=0)}
    source = _write_source(tmp_path, pages, scaffold_sections=False)
    store, report = _extract(tmp_path, source, page_size=2)

    containers = {path for path in ALL_PATHS if "/title-" in path}
    assert f"marked at {CODE_ROOT}" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=containers | {CODE_ROOT},
        missing={CODE_ROOT},
        gap_source=_page_name(0, 2),
    )


# Lead 3: the first page reports no sections while the scaffold has titles.


@pytest.mark.parametrize("count", [0, None], ids=["count-zero", "count-missing"])
def test_listing_with_no_sections_keeps_scaffold_nodes_as_gaps(tmp_path, count):
    pages = {_page_name(0, 2): _page([], count=count)}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing=ALL_PATHS - EMPTY_CONTAINERS,
        gap_source=_page_name(0, 2),
    )


# Lead 4: a server that ignores ``offset`` returns the same rows every page.


def test_listing_that_repeats_rows_keeps_unfetched_nodes_as_gaps(tmp_path):
    pages = {
        _page_name(0, 3): _page(["S1", "S2"] + ["S1"]),
        _page_name(3, 3): _page(["S1", "S2", "S1"]),
        _page_name(6, 3): _page(["S1"]),
    }
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=3)

    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing=MISSING_AFTER_S2,
        gap_source=_page_name(6, 3),
    )


# A page that cannot be fetched or read ends the listing the same way.


def test_unfetchable_page_keeps_unfetched_nodes_as_gaps_from_titles(tmp_path):
    pages = {_page_name(0, 2): _page(["S1", "S2"])}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    assert all("sections page at offset 2" in error for error in report.errors)
    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing=MISSING_AFTER_S2,
        gap_source=TITLES_SOURCE,
    )


def test_unfetchable_first_page_keeps_every_node_as_gap_from_titles(tmp_path):
    source = _write_source(tmp_path, {})
    store, report = _extract(tmp_path, source, page_size=2)

    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing=ALL_PATHS - EMPTY_CONTAINERS,
        gap_source=TITLES_SOURCE,
    )


def test_unreadable_page_keeps_unfetched_nodes_as_gaps_from_that_page(tmp_path):
    pages = {
        _page_name(0, 2): _page(["S1", "S2"]),
        _page_name(2, 2): {"data": {"somethingElse": None}},
    }
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    assert all("missing data.codesOfAlabama" in error for error in report.errors)
    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing=MISSING_AFTER_S2,
        gap_source=_page_name(2, 2),
    )


def test_early_end_with_no_record_still_writes_its_gaps(tmp_path):
    # Every node in title 1 is a gap, so the run holds no record at all. Main
    # raised before writing anything; the gaps must still be written.
    source = _write_source(tmp_path, {})
    store, report = _extract(tmp_path, source, page_size=2, only_title="1")

    assert report.provisions_written == 0
    _assert_visible_gaps(
        store,
        report,
        expected=TITLE_1_PATHS,
        missing=TITLE_1_PATHS,
        gap_source=TITLES_SOURCE,
    )


# What stops the run.


def test_interrupt_during_page_fetch_propagates(tmp_path, monkeypatch):
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2)
    original = alabama._AlabamaFetcher.fetch_sections_page

    def interrupted(self, *, offset, limit):
        if offset > 0:
            raise KeyboardInterrupt
        return original(self, offset=offset, limit=limit)

    monkeypatch.setattr(alabama._AlabamaFetcher, "fetch_sections_page", interrupted)
    with pytest.raises(KeyboardInterrupt):
        _extract(tmp_path, source, page_size=2)


def test_store_write_failure_for_a_page_propagates(tmp_path, monkeypatch):
    # A full disk is not a coverage gap.
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2)
    original = CorpusArtifactStore.write_bytes

    def failing(self, path, data):
        if "sections-current-offset-2" in str(path):
            raise OSError("No space left on device")
        return original(self, path, data)

    monkeypatch.setattr(CorpusArtifactStore, "write_bytes", failing)
    with pytest.raises(OSError, match="No space left"):
        _extract(tmp_path, source, page_size=2)


def test_listing_does_not_page_past_count(tmp_path, monkeypatch):
    pages = {
        _page_name(0, 3): _page(["S1", "S2", "S1"]),
        _page_name(3, 3): _page(["S1", "S2", "S1"]),
        _page_name(6, 3): _page(["S1"]),
    }
    source = _write_source(tmp_path, pages)
    offsets: list[int] = []
    original = alabama._AlabamaFetcher.fetch_sections_page

    def recording(self, *, offset, limit):
        offsets.append(offset)
        return original(self, offset=offset, limit=limit)

    monkeypatch.setattr(alabama._AlabamaFetcher, "fetch_sections_page", recording)
    _extract(tmp_path, source, page_size=3)
    assert offsets == [0, 3, 6]


def test_section_numbered_node_with_a_child_reads_as_a_container(tmp_path):
    # Only a childless node counts as a section by its number. This one has an
    # empty child, so both are containers the scaffold gives no section.
    extra = (
        ("A5", "C4", "2-3-500", "Article 2-3-500 Grouping."),
        ("D5", "A5", "5", "Division 5 Empty."),
    )
    source = _write_source(tmp_path, EMPTY_PAGE_AFTER_S2, extra_containers=extra)
    _, report = _extract(tmp_path, source, page_size=2)

    article = "us-al/statute/title-2/chapter-3/article-2-3-500"
    records = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert {article, f"{article}/division-5"} <= records
    assert article not in report.coverage.missing_from_provisions
