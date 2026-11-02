"""An Alabama section listing that ends early stays a visible coverage gap.

``extract_alabama_code`` pages through every section with the ALISON
``codesOfAlabama`` query and compares the distinct sections it holds with the
``count`` the listing reports. When the listing ends early, every container
the scaffold names that has no fetched section beneath it is an inventory gap,
so coverage reads incomplete and strict release validation refuses the run.
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

# Two titles. Title 2 carries chapters the titles data marks as repealed,
# reserved and transferred; they have no sections by law. Article 1 sits
# under the repealed chapter.
SCAFFOLD_ROWS = [
    ("T1", None, "1"),
    ("C1", "T1", "1"),
    ("C2", "T1", "2"),
    ("T2", None, "2"),
    ("C3", "T2", "1"),
    ("R1", "T2", "2"),
    ("A1", "R1", "1"),
    ("R2", "T2", "3"),
    ("R3", "T2", "4"),
]
TITLE_ROWS = [
    ("T1", "Title 1 General Provisions."),
    ("C1", "Chapter 1 Construction of Code and Statutes."),
    ("C2", "Chapter 2 Seals."),
    ("T2", "Title 2 Agriculture."),
    ("C3", "Chapter 1 General Provisions."),
    ("R1", "Chapter 2 Repealed."),
    ("A1", "Article 1 Former Provisions."),
    ("R2", "Chapter 3 Reserved."),
    ("R3", "Chapter 4 Transferred."),
]
SECTIONS = [
    ("S1", "C1", "1-1-1"),
    ("S2", "C1", "1-1-2"),
    ("S3", "C2", "1-2-1"),
    ("S4", "C3", "2-1-1"),
]

TITLE_1 = "us-al/statute/title-1"
CHAPTER_1_1 = "us-al/statute/title-1/chapter-1"
CHAPTER_1_2 = "us-al/statute/title-1/chapter-2"
TITLE_2 = "us-al/statute/title-2"
CHAPTER_2_1 = "us-al/statute/title-2/chapter-1"
REPEALED = "us-al/statute/title-2/chapter-2"
REPEALED_ARTICLE = "us-al/statute/title-2/chapter-2/article-1"
RESERVED = "us-al/statute/title-2/chapter-3"
TRANSFERRED = "us-al/statute/title-2/chapter-4"
EMPTY_BY_LAW = {REPEALED, REPEALED_ARTICLE, RESERVED, TRANSFERRED}
SECTION_PATHS = {f"us-al/statute/{display}" for _, _, display in SECTIONS}
TITLE_1_PATHS = {TITLE_1, CHAPTER_1_1, CHAPTER_1_2} | {
    "us-al/statute/1-1-1",
    "us-al/statute/1-1-2",
    "us-al/statute/1-2-1",
}
TITLE_2_PATHS = {TITLE_2, CHAPTER_2_1, "us-al/statute/2-1-1"} | EMPTY_BY_LAW
ALL_PATHS = TITLE_1_PATHS | TITLE_2_PATHS


def _deflated(headers: list[str], rows: list[tuple[str | None, ...]]) -> str:
    lines = ["†".join(headers)]
    lines.extend("†".join(value or "" for value in row) for row in rows)
    return "†∫" + "∫".join(lines)


def _section_row(code_id: str) -> dict:
    _, parent, display = next(row for row in SECTIONS if row[0] == code_id)
    return {
        "id": f"g-{code_id}",
        "codeId": code_id,
        "displayId": display,
        "title": f"Section {display} Heading {display}.",
        "content": f"<p>Text of section {display}.</p>",
        "history": "(Acts 2026, No. 1.)",
        "parentId": parent,
        "type": "Section",
        "isContentNode": True,
        "sectionRange": None,
        "effectiveDate": None,
        "supersessionDate": None,
    }


def _page(code_ids: list[str], *, count: int | None = len(SECTIONS)) -> dict:
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
    scaffold_sections: bool = False,
) -> Path:
    source = root / "source"
    (source / ALABAMA_GRAPHQL_SOURCE_FORMAT).mkdir(parents=True)
    scaffold_rows = list(SCAFFOLD_ROWS)
    title_rows = list(TITLE_ROWS)
    if scaffold_sections:
        scaffold_rows.extend(SECTIONS)
        title_rows.extend(
            (code_id, f"Section {display} Heading {display}.") for code_id, _, display in SECTIONS
        )
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


# Controls: a complete listing reads complete, as on main.


@pytest.mark.parametrize(
    ("page_size", "pages"),
    [
        (2, {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page(["S3", "S4"])}),
        # The last page is short because it is the last one.
        (3, {_page_name(0, 3): _page(["S1", "S2", "S3"]), _page_name(3, 3): _page(["S4"])}),
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
    assert report.section_count == len(SECTIONS)
    assert report.title_count == 2


def test_complete_listing_for_one_title_reads_complete(tmp_path):
    pages = {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page(["S3", "S4"])}
    source = _write_source(tmp_path, pages)
    _, report = _extract(tmp_path, source, page_size=2, only_title="1")

    inventory, records = _paths(report)
    assert report.errors == ()
    assert report.coverage.complete is True
    assert set(inventory) == set(records) == TITLE_1_PATHS


# Lead 1 and lead 2: the listing stops early on an empty or short page, and
# the containers whose sections were never fetched must stay in the inventory.


@pytest.mark.parametrize("scaffold_sections", [False, True], ids=["containers", "with-sections"])
def test_empty_page_before_count_keeps_unfetched_containers_as_gaps(tmp_path, scaffold_sections):
    pages = {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page([])}
    source = _write_source(tmp_path, pages, scaffold_sections=scaffold_sections)
    store, report = _extract(tmp_path, source, page_size=2)

    missing = {CHAPTER_1_2, TITLE_2, CHAPTER_2_1}
    if scaffold_sections:
        # A scaffold that names the sections names the unfetched ones too.
        missing |= {"us-al/statute/1-2-1", "us-al/statute/2-1-1"}
    assert all("2 of 4 sections" in error for error in report.errors)
    _assert_visible_gaps(
        store,
        report,
        expected={TITLE_1, CHAPTER_1_1, "us-al/statute/1-1-1", "us-al/statute/1-1-2"}
        | missing
        | EMPTY_BY_LAW,
        missing=missing,
        gap_source=_page_name(2, 2),
    )


def test_short_page_before_count_keeps_unfetched_containers_as_gaps(tmp_path):
    pages = {_page_name(0, 3): _page(["S1", "S2"])}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=3)

    missing = {CHAPTER_1_2, TITLE_2, CHAPTER_2_1}
    _assert_visible_gaps(
        store,
        report,
        expected={TITLE_1, CHAPTER_1_1, "us-al/statute/1-1-1", "us-al/statute/1-1-2"}
        | missing
        | EMPTY_BY_LAW,
        missing=missing,
        gap_source=_page_name(0, 3),
    )


def test_early_end_for_one_title_keeps_that_title_as_a_gap(tmp_path):
    # Main raised "no Alabama provisions extracted" here: nothing of title 2
    # was fetched, so the run held no record and wrote nothing.
    pages = {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page([])}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2, only_title="2")

    missing = {TITLE_2, CHAPTER_2_1}
    _assert_visible_gaps(
        store,
        report,
        expected=missing | EMPTY_BY_LAW,
        missing=missing,
        gap_source=_page_name(2, 2),
    )


def test_early_end_with_every_container_fetched_keeps_last_container_as_gap(tmp_path):
    # The listing reports five sections and every container holds a fetched
    # one, so no container is empty. The listing ended inside the container of
    # the last section it held, which stays a gap.
    pages = {
        _page_name(0, 2): _page(["S1", "S2"], count=5),
        _page_name(2, 2): _page(["S3", "S4"], count=5),
        _page_name(4, 2): _page([], count=5),
    }
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    assert "4 of 5 sections" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=ALL_PATHS,
        missing={CHAPTER_2_1},
        gap_source=_page_name(4, 2),
    )


# Lead 3: the first page reports no sections while the scaffold has titles.


@pytest.mark.parametrize("count", [0, None], ids=["count-zero", "count-missing"])
def test_listing_with_no_sections_keeps_scaffold_containers_as_gaps(tmp_path, count):
    pages = {_page_name(0, 2): _page([], count=count)}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    missing = {TITLE_1, CHAPTER_1_1, CHAPTER_1_2, TITLE_2, CHAPTER_2_1}
    _assert_visible_gaps(
        store,
        report,
        expected=missing | EMPTY_BY_LAW,
        missing=missing,
        gap_source=_page_name(0, 2),
    )


def test_containers_empty_by_law_stay_complete_records(tmp_path):
    pages = {_page_name(0, 2): _page([], count=0)}
    source = _write_source(tmp_path, pages)
    _, report = _extract(tmp_path, source, page_size=2)

    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert set(records) == EMPTY_BY_LAW
    assert records[REPEALED].metadata["status"] == "repealed"
    assert not any(path in error for path in EMPTY_BY_LAW for error in report.errors)


@pytest.mark.parametrize(
    ("title", "empty"),
    [
        ("Chapter 2 Repealed.", True),
        ("Chapter 2 Reserved.", True),
        ("Chapter 2 Transferred.", True),
        ("Chapter 2 (Repealed)", True),
        ("Chapter 2 Repealed by Act 2019-1.", True),
        ("Chapter 2 Transferred to Title 40.", True),
        ("Chapter 2 Repealed, Acts 2019, No. 1.", True),
        ("Chapter 2 Transferred Property.", False),
        ("Chapter 2 Reserved Powers of Counties.", False),
        ("Chapter 2 Seals.", False),
    ],
)
def test_empty_by_law_reads_only_a_marker_heading(title, empty):
    node = alabama.AlabamaNode(code_id="X", title=title)
    assert alabama._alabama_empty_by_law(node, {"X": node}) is empty


def test_early_end_with_no_record_still_writes_its_gaps(tmp_path):
    # Every node in title 1 is a gap, so the run holds no record at all. Main
    # raised before writing anything; the gaps must still be written.
    source = _write_source(tmp_path, {})
    store, report = _extract(tmp_path, source, page_size=2, only_title="1")

    missing = {TITLE_1, CHAPTER_1_1, CHAPTER_1_2}
    assert report.provisions_written == 0
    _assert_visible_gaps(
        store,
        report,
        expected=missing,
        missing=missing,
        gap_source=TITLES_SOURCE,
    )


# Lead 4: a server that ignores ``offset`` returns the same rows every page.


def test_listing_that_repeats_rows_keeps_unfetched_containers_as_gaps(tmp_path):
    pages = {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page(["S1", "S2"])}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    missing = {CHAPTER_1_2, TITLE_2, CHAPTER_2_1}
    _assert_visible_gaps(
        store,
        report,
        expected={TITLE_1, CHAPTER_1_1, "us-al/statute/1-1-1", "us-al/statute/1-1-2"}
        | missing
        | EMPTY_BY_LAW,
        missing=missing,
        gap_source=_page_name(2, 2),
    )


# A page that cannot be fetched or read ends the listing the same way.


def test_unfetchable_page_keeps_unfetched_containers_as_gaps_from_titles(tmp_path):
    pages = {_page_name(0, 2): _page(["S1", "S2"])}
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    assert all("sections page at offset 2" in error for error in report.errors)
    missing = {CHAPTER_1_2, TITLE_2, CHAPTER_2_1}
    _assert_visible_gaps(
        store,
        report,
        expected={TITLE_1, CHAPTER_1_1, "us-al/statute/1-1-1", "us-al/statute/1-1-2"}
        | missing
        | EMPTY_BY_LAW,
        missing=missing,
        gap_source=TITLES_SOURCE,
    )


def test_unfetchable_first_page_keeps_every_container_as_gap_from_titles(tmp_path):
    source = _write_source(tmp_path, {})
    store, report = _extract(tmp_path, source, page_size=2)

    missing = {TITLE_1, CHAPTER_1_1, CHAPTER_1_2, TITLE_2, CHAPTER_2_1}
    _assert_visible_gaps(
        store,
        report,
        expected=missing | EMPTY_BY_LAW,
        missing=missing,
        gap_source=TITLES_SOURCE,
    )


def test_unreadable_page_keeps_unfetched_containers_as_gaps_from_that_page(tmp_path):
    pages = {
        _page_name(0, 2): _page(["S1", "S2"]),
        _page_name(2, 2): {"data": {"somethingElse": None}},
    }
    source = _write_source(tmp_path, pages)
    store, report = _extract(tmp_path, source, page_size=2)

    assert all("missing data.codesOfAlabama" in error for error in report.errors)
    missing = {CHAPTER_1_2, TITLE_2, CHAPTER_2_1}
    _assert_visible_gaps(
        store,
        report,
        expected={TITLE_1, CHAPTER_1_1, "us-al/statute/1-1-1", "us-al/statute/1-1-2"}
        | missing
        | EMPTY_BY_LAW,
        missing=missing,
        gap_source=_page_name(2, 2),
    )


def test_interrupt_during_page_fetch_propagates(tmp_path, monkeypatch):
    pages = {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page(["S3", "S4"])}
    source = _write_source(tmp_path, pages)
    original = alabama._AlabamaFetcher.fetch_sections_page

    def interrupted(self, *, offset, limit):
        if offset > 0:
            raise KeyboardInterrupt
        return original(self, offset=offset, limit=limit)

    monkeypatch.setattr(alabama._AlabamaFetcher, "fetch_sections_page", interrupted)
    with pytest.raises(KeyboardInterrupt):
        _extract(tmp_path, source, page_size=2)


def test_listing_does_not_page_past_count(tmp_path, monkeypatch):
    pages = {_page_name(0, 2): _page(["S1", "S2"]), _page_name(2, 2): _page(["S1", "S2"])}
    source = _write_source(tmp_path, pages)
    offsets: list[int] = []
    original = alabama._AlabamaFetcher.fetch_sections_page

    def recording(self, *, offset, limit):
        offsets.append(offset)
        return original(self, offset=offset, limit=limit)

    monkeypatch.setattr(alabama._AlabamaFetcher, "fetch_sections_page", recording)
    _extract(tmp_path, source, page_size=2)
    assert offsets == [0, 2]
