"""The official-document HTML extractor drops blocks that are page navigation.

``documents._extract_html_blocks`` asks ``content_quality.is_navigation_block`` of
every positional block. Invariants, for every page:

- The filtered blocks are the unfiltered blocks minus the ones the helper calls
  navigation, in order, with unchanged ordinals, headings and bodies, so a
  dropped block never renumbers the blocks after it.
- A page with no navigation strings loses no block, and
  ``html_keep_navigation_blocks: true`` keeps every block.
- Every block the helper calls navigation is a ``navigation_body`` by the release
  content check, with no word of its own and at least two navigation strings.
- Differential against the release content check on the written rows: every
  dropped row is one the check flags on the unfiltered rows, and the check flags
  exactly the other flagged rows on the filtered rows.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.content_quality import (
    MAX_BODY_TOKENS,
    NAVIGATION_BLOCK_MAX_STRING_WORDS,
    NAVIGATION_BODY,
    PageNavigation,
    classify_body,
    is_navigation_block,
    page_navigation,
    scan_provisions,
)
from axiom_corpus.corpus.documents import (
    OfficialDocumentSource,
    _extract_html_blocks,
    _extract_json_html_blocks,
    _provision_records,
    extract_official_documents,
)
from axiom_corpus.corpus.io import load_provisions

_SETTINGS = settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
KEEP = {"html_keep_navigation_blocks": True}
URL = "https://example.gov/rules"


def _page(body: str, title: str = "Rules") -> bytes:
    return f"<!doctype html><html><head><title>{title}</title></head><body>{body}</body></html>".encode()


def _links(*labels: str) -> str:
    return (
        "<ul>"
        + "".join(f"<li><a href='/{i}'>{label}</a></li>" for i, label in enumerate(labels))
        + "</ul>"
    )


def _blocks(content: bytes, extraction: dict | None = None) -> list[tuple[int, str | None, str]]:
    blocks = _extract_html_blocks(
        content, source_url=URL, fallback_title="Rules", extraction=extraction
    )
    return [(block.ordinal, block.heading, block.body) for block in blocks]


MENU_PAGE = _page(
    _links("Home", "About Us", "Contact Us")
    + "<h2>Earned income</h2><p>Earned income includes wages, salaries and tips.</p>"
    + "<h2>Related pages</h2>"
    + _links("Unearned income", "Resources", "Apply online")
    + "<h2>Unearned income</h2><p>Unearned income includes pensions and annuities.</p>"
)


def test_a_menu_block_is_dropped_and_later_blocks_keep_their_ordinals() -> None:
    every = _blocks(MENU_PAGE, KEEP)
    kept = _blocks(MENU_PAGE)

    assert [ordinal for ordinal, _, _ in every] == [1, 2, 3, 4]
    assert kept == [every[1], every[3]]
    assert [ordinal for ordinal, _, _ in kept] == [2, 4]
    assert "Home" not in " ".join(body for _, _, body in kept)


def test_a_lone_link_is_kept_because_it_can_be_the_section_text() -> None:
    page = _page(
        _links("Home", "Forms")
        + "<h2>Illinois residents</h2><p><a href='/ra'>See reciprocal agreement</a></p>"
        + "<h2>Exhibit</h2><p><a href='/x.pdf'>Exhibit Overpayment Requiring RO Concurrence</a></p>"
    )
    kept = _blocks(page)

    assert [body for _, _, body in kept] == [
        "See reciprocal agreement",
        "Exhibit Overpayment Requiring RO Concurrence",
    ]
    # The release check still flags the lone link, for review; the extractor keeps it.
    assert classify_body("See reciprocal agreement", page_navigation(page)).navigation


def test_a_status_line_beside_a_link_is_kept() -> None:
    # Connecticut's eRegulations: "Repealed" is also a table-of-contents link.
    page = _page(
        _links("Repealed", "Return to Table of Contents", "Sec. 12-701")
        + "<h2>Sec. 12-719-1. (Repealed)</h2>"
        + "<p>Repealed April 6, 2000.</p><p><a href='#toc'>Return to Table of Contents</a></p>"
    )
    body = "Repealed April 6, 2000.\n\nReturn to Table of Contents"

    assert classify_body(body, page_navigation(page)).navigation
    assert body in [text for _, _, text in _blocks(page)]


def test_a_definition_inside_a_glossary_link_is_kept() -> None:
    definition = (
        "Work Registration The act of signing the application or recertification form "
        "attesting to work registration requirements."
    )
    page = _page(
        f"<h2>301 Overview</h2><p><a href='#g1'>{definition}</a></p>"
        f"<p><a href='#g2'>{definition.replace('Work Registration', 'Work Rules')}</a></p>"
    )
    body = _blocks(page, KEEP)[0][2]

    assert classify_body(body, page_navigation(page)).navigation
    assert [text for _, _, text in _blocks(page)] == [body]


def test_a_table_of_contents_with_long_entries_is_kept() -> None:
    entries = [
        "HOOFDSTUK 2/1. Bepaling van de premiebedragen en de loongrenzen "
        "(ing. BVR 2 juni 2023, art. 2, I: 1 januari 2023)",
        "HOOFDSTUK 3. Voorwaarden voor de aanpassing van de premiebedragen en de loongrenzen",
    ]
    page = _page("<h2>Inhoudstafel</h2>" + _links(*entries))
    tokens = entries[0].split()
    body = "\n\n".join(entries)

    assert sum(any(c.isalpha() for c in t) for t in tokens) > NAVIGATION_BLOCK_MAX_STRING_WORDS
    assert classify_body(body, page_navigation(page)).navigation
    assert [text for _, _, text in _blocks(page)] == [body]


def test_a_body_that_repeats_its_heading_is_kept() -> None:
    navigation = PageNavigation(["Forms", "Publications"])

    assert is_navigation_block("Forms Publications", navigation)
    assert is_navigation_block("Forms Publications", navigation, heading="Forms and Publications")
    assert not is_navigation_block("Forms Publications", navigation, heading="Forms Publications")
    assert not is_navigation_block(
        "Rules 3 Forms Publications",
        PageNavigation(["Rules 3", "Forms", "Publications"]),
        heading="Forms Publications",
        label="Rules 3",
    )


def test_a_body_longer_than_the_check_reads_is_kept() -> None:
    navigation = PageNavigation(["Home", "About"])
    body = " ".join(["Home", "About"] * (MAX_BODY_TOKENS // 2 + 1))

    assert classify_body(body, navigation).navigation
    assert not is_navigation_block(body, navigation)


def test_keep_navigation_blocks_keeps_every_block() -> None:
    kept = _blocks(MENU_PAGE, KEEP)

    assert len(kept) == 4
    assert kept[0][2] == "Home\n\nAbout Us\n\nContact Us"


def test_labeled_sections_are_never_dropped() -> None:
    page = _page(
        _links("Household", "Income limits")
        + "<p>Sec. 1. Definitions</p><ul><li><a href='/h'>Household</a></li>"
        + "<li><a href='/i'>Income limits</a></li></ul>"
        + "<p>Sec. 2. Rates</p><p>The rate is 3 percent.</p>"
    )
    blocks = _extract_html_blocks(
        page,
        source_url=URL,
        fallback_title="Rules",
        extraction={
            "segmentation": "labeled_sections",
            "section_heading_pattern": r"^(?P<label>Sec\. \d+)\.\s+(?P<heading>.+)$",
        },
    )

    assert [block.body for block in blocks] == [
        "Household\n\nIncome limits",
        "The rate is 3 percent.",
    ]
    assert is_navigation_block("Household\n\nIncome limits", page_navigation(page))


def test_a_webworks_page_with_declared_sections_is_never_filtered() -> None:
    # WebWorks reading takes precedence over labeled_sections, as before the filter;
    # the declared segmentation still turns the filter off.
    page = _page(
        _links("Household", "Income limits")
        + "<div id='page_content'><p class='Heading_1'>Sec. 1. Definitions</p>"
        + "<p class='Body_Text'><a href='/h'>Household</a></p>"
        + "<p class='Body_Text'><a href='/i'>Income limits</a></p></div>"
    )
    extraction = {
        "segmentation": "labeled_sections",
        "section_heading_pattern": r"^(?P<label>Sec\. \d+)\.\s+(?P<heading>.+)$",
    }

    assert _blocks(page) == []
    assert _blocks(page, extraction) == [(1, "Sec. 1. Definitions", "Household\n\nIncome limits")]


def test_figures_beside_linked_labels_are_kept() -> None:
    page = _page(
        "<h2>Income limits</h2><table><tr>"
        "<th><a href='/gross'>Gross monthly income limit</a></th>"
        "<th><a href='/net'>Net monthly income limit</a></th></tr>"
        "<tr><td>$2,000</td><td>$1,500</td></tr></table>"
        "<h2>Status</h2><p><a href='/r'>Repealed by the General Assembly</a> 2000-04-06</p>"
        "<p><a href='/e'>Effective date of repeal</a> 2001-01-01</p>"
    )
    navigation = page_navigation(page)
    bodies = [body for _, _, body in _blocks(page)]

    assert len(bodies) == 2
    for body in bodies:
        assert classify_body(body, navigation).navigation
        assert not is_navigation_block(body, navigation)


def test_table_marks_beside_linked_labels_are_kept() -> None:
    page = _page(
        "<h2>Who counts this income</h2><table>"
        "<tr><th><a href='/snap'>SNAP</a></th><th><a href='/tanf'>TANF</a></th></tr>"
        "<tr><td>✓</td><td>✗</td></tr></table>"
        "<h2>Programs</h2><p><a href='/snap'>SNAP</a> | <a href='/tanf'>TANF</a></p>"
    )
    navigation = page_navigation(page)

    assert classify_body("SNAP TANF ✓ ✗", navigation).navigation
    assert [body for _, _, body in _blocks(page)] == ["SNAP TANF ✓ ✗"]
    assert is_navigation_block("SNAP | TANF", navigation)


def test_short_definitions_inside_links_are_kept() -> None:
    page = _page(
        "<h2>Definitions</h2><p><a href='/income'>Income means money received.</a></p>"
        "<p><a href='/resource'>Resource means property owned.</a></p>"
    )
    body = "Income means money received.\n\nResource means property owned."

    assert classify_body(body, page_navigation(page)).navigation
    assert [text for _, _, text in _blocks(page)] == [body]
    # A label ending in an ellipsis or a question mark is still a label.
    assert is_navigation_block(
        "Continue reading... How current is this law?",
        PageNavigation(["Continue reading...", "How current is this law?"]),
    )


def test_html_inside_json_is_never_filtered() -> None:
    # The release check reads the retained JSON, which has no HTML navigation, so
    # the extractor drops nothing it reads out of a JSON field.
    content = json.dumps({"html": MENU_PAGE.decode()}).encode()
    blocks = _extract_json_html_blocks(
        content, source_url=URL, fallback_title="Rules", extraction={"json_html_field": "html"}
    )

    assert [block.ordinal for block in blocks] == [1, 2, 3, 4]


def test_a_webworks_page_drops_its_navigation_and_never_falls_back() -> None:
    menu = "".join(
        f"<p class='Body_Text'><a href='/{i}'>{label}</a></p>"
        for i, label in enumerate(("Previous Section", "Next Section", "Print"))
    )
    page = _page(
        "<div id='page_content'>"
        "<p class='Heading_1'>608 Hearings</p>" + menu + "<p class='Heading_2'>608-1 Requests</p>"
        "<p class='Body_Text'>A household may request a hearing at any time.</p></div>"
    )
    only_menu = _page(
        "<div id='page_content'><p class='Heading_1'>608 Hearings</p>"
        + menu
        + "</div>"
        + "<p>Text outside the WebWorks content that the default walk would read.</p>"
    )

    assert [(ordinal, body) for ordinal, _, body in _blocks(page)] == [
        (2, "A household may request a hearing at any time.")
    ]
    assert _blocks(only_menu) == []
    assert len(_blocks(only_menu, KEEP)) == 1


def test_a_navigation_fallback_block_is_dropped_not_replaced() -> None:
    page = _page("<div><a href='/'>Home</a> <a href='/forms'>Forms</a></div>")

    assert _blocks(page, KEEP) == [(1, "Rules", "Home Forms")]
    assert _blocks(page) == []


def test_extract_official_documents_writes_the_gap_and_the_check_agrees(tmp_path: Path) -> None:
    page_path = tmp_path / "page.html"
    page_path.write_bytes(
        _page(
            _links("Home", "About Us", "Contact Us")
            + "<h2>Earned income</h2><p>Earned income includes wages, salaries and tips.</p>"
            + "<h2>Illinois residents</h2><p><a href='/ra'>See reciprocal agreement</a></p>"
        )
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: income-rules
    jurisdiction: us-test
    document_class: manual
    title: Income Rules
    source_url: {URL}
    source_format: html
    local_path: {json.dumps(str(page_path))}
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store, manifest_path=manifest_path, version="2026-10-13-test"
    )

    records = load_provisions(report.provisions_path)
    assert report.coverage.complete
    assert [record.citation_path.rsplit("/", 1)[-1] for record in records] == [
        "income-rules",
        "block-2",
        "block-3",
    ]
    assert records[0].metadata["block_count"] == 2
    findings = scan_provisions(store.root, records)
    assert [(finding.code, finding.path) for finding in findings] == [
        (NAVIGATION_BODY, "us-test/manual/income-rules/block-3")
    ]


# Property-based: pages made of headed sections of links and sentences.

_LABELS = st.sampled_from(
    [
        "Home",
        "About Us",
        "Contact",
        "Forms",
        "Income",
        "Apply Now",
        "Eligibility rules",
        "Previous Section",
        "Next Section",
        "Section 5",
        "1990 c 604",
        "Household income limits for the program year",
        "Apply now.",
        "Report changes on time!",
    ]
)
_WORDS = st.sampled_from(
    ["The", "rate", "is", "3", "percent", "Income", "Forms", "Home", "of", "wages", "|", "✓", "—"]
)
_ITEM = st.one_of(
    st.tuples(st.just("link"), _LABELS),
    st.tuples(st.just("text"), st.lists(_WORDS, min_size=1, max_size=8).map(" ".join)),
)
_SECTION = st.tuples(
    st.sampled_from(["Overview", "Income", "Related pages", "Forms", "Home"]),
    st.lists(_ITEM, min_size=0, max_size=5),
)
_PAGES = st.tuples(st.lists(_ITEM, max_size=4), st.lists(_SECTION, min_size=0, max_size=5))


def _render(
    opening: list[tuple[str, str]], sections: list[tuple[str, list[tuple[str, str]]]]
) -> bytes:
    def item(kind: str, text: str) -> str:
        escaped = html.escape(text)
        return (
            f"<p><a href='/{len(text)}'>{escaped}</a></p>"
            if kind == "link"
            else f"<p>{escaped}</p>"
        )

    parts = [item(*entry) for entry in opening]
    for heading, items in sections:
        parts.append(f"<h2>{html.escape(heading)}</h2>")
        parts.extend(item(*entry) for entry in items)
    return _page("".join(parts))


@_SETTINGS
@given(page=_PAGES)
def test_filtered_blocks_are_the_unfiltered_blocks_minus_navigation(page) -> None:  # type: ignore[no-untyped-def]
    content = _render(*page)
    navigation = page_navigation(content)
    every = _extract_html_blocks(content, source_url=URL, fallback_title="Rules", extraction=KEEP)
    kept = _extract_html_blocks(content, source_url=URL, fallback_title="Rules", extraction=None)

    assert [block.ordinal for block in every] == list(range(1, len(every) + 1))
    assert list(kept) == [
        block
        for block in every
        if not is_navigation_block(
            block.body, navigation, heading=block.heading, label=f"Rules {block.ordinal}"
        )
    ]
    if not navigation:
        assert kept == every


@_SETTINGS
@given(
    strings=st.lists(_LABELS, max_size=6),
    tokens=st.lists(st.one_of(_LABELS, _WORDS), min_size=1, max_size=12),
)
def test_a_navigation_block_is_a_flagged_body_of_links_only(strings, tokens) -> None:  # type: ignore[no-untyped-def]
    navigation = PageNavigation(strings)
    body = " ".join(tokens)
    if is_navigation_block(body, navigation):
        words = body.split()
        spans = navigation.matches(words)
        covered = {position for start, end in spans for position in range(start, end)}
        assert classify_body(body, navigation).navigation
        assert all(
            set(word) <= set("|/\\<>«»‹›•·-–")
            for position, word in enumerate(words)
            if position not in covered
        )
        assert len(spans) >= 2
        for start, end in spans:
            assert sum(any(char.isalpha() for char in word) for word in words[start:end]) <= 12
            assert not words[end - 1].endswith((".", "!"))


@_SETTINGS
@given(page=_PAGES)
def test_the_extractor_drops_only_rows_the_release_check_flags(page, tmp_path_factory) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path_factory.mktemp("corpus")
    content = _render(*page)
    source_key = "sources/us-test/manual/v1/official-documents/rules.html"
    (root / source_key).parent.mkdir(parents=True, exist_ok=True)
    (root / source_key).write_bytes(content)
    source = OfficialDocumentSource(
        source_id="rules",
        jurisdiction="us-test",
        document_class="manual",
        title="Rules",
        source_url=URL,
    )

    def rows(extraction: dict | None) -> list:
        blocks = _extract_html_blocks(
            content, source_url=URL, fallback_title="Rules", extraction=extraction
        )
        return list(
            _provision_records(
                source,
                blocks=blocks,
                version="v1",
                source_key=source_key,
                source_format="html",
                source_as_of="2026-10-13",
                expression_date="2026-10-13",
                content_type="text/html",
                final_url=URL,
            )
        )

    def flagged(records: list) -> set[str]:
        return {f.path for f in scan_provisions(root, records) if f.code == NAVIGATION_BODY}

    every, kept = rows(KEEP), rows(None)
    dropped = {r.citation_path for r in every} - {r.citation_path for r in kept}

    assert dropped <= flagged(every)
    assert flagged(kept) == flagged(every) - dropped


def test_recovery_keeps_every_block_of_a_page_it_re_encodes() -> None:
    # recover_ingest_batch decodes HTML as UTF-8 and re-encodes it before
    # extracting, so on a Windows-1252 page the extractor would read other link
    # text than the release check reads in the retained bytes.
    from scripts.recover_ingest_batch import _generic

    law = (
        "Every landlord shall return the deposit within thirty days of the end of the tenancy. " * 4
    )
    data = (
        b"<html><head><meta charset='windows-1252'><title>Deposits</title></head><body>"
        b"<ul><li><a href='/o'>Owner\x92s Guide</a></li><li><a href='/t'>Tenant\x92s Guide</a></li></ul>"
        b"<h2>Deposits</h2><p>" + law.encode() + b"</p></body></html>"
    )
    entry = {
        "document_id": "deposits",
        "jurisdiction": "us-test",
        "document_class": "manual",
        "parser": "documents:html",
        "proposed_version": "v1",
        "covers_citation_paths": [],
    }
    provenance = {"url": URL, "fetched_at": "2026-10-13T00:00:00Z", "sha256": "0" * 64}

    _, records = _generic(
        entry, Path("deposits"), data, provenance, "sources/us-test/manual/v1/deposits.html"
    )

    assert [record.ordinal for record in records[1:]] == [1, 2]
    assert "Guide" in (records[1].body or "")
