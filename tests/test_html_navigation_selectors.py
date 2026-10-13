"""A manifest can name a publisher's page navigation, and the extractor drops it whole.

``html_navigation_selectors`` match navigation elements (tab or jump links) and
``html_navigation_heading_selectors`` match headings that start a link list
(``documents._DeclaredNavigation``). Invariants, for every page:

- The kept blocks are the blocks of an extraction without the keys minus the
  blocks they declare, in order, with unchanged ordinals, headings and bodies:
  a declared block is dropped whole and its ordinal is used up, so no other
  block changes path or text.
- A block is declared exactly when the heading that starts it is matched, or
  every string of its body lies inside a matched element; a block with any
  other text keeps its whole body.
- ``html_keep_navigation_blocks: true`` keeps every block.

``html_drop_selectors`` cannot do this: they remove elements before the blocks
are numbered, so every block after one they empty is renumbered.

The retained-page tests pin each selector the Washington EA-Z and Texas HHS
manifests name on pages the locked scopes hold.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.documents import (
    OfficialDocumentManifest,
    _extract_html_blocks,
    _extract_json_html_blocks,
)
from scripts.build_medicaid_state_eligibility_manual_manifests import (
    TX_RELATED_POLICY_HEADING as MEDICAID_RELATED_POLICY,
)
from scripts.build_snap_state_manual_completion_manifests import (
    TX_RELATED_POLICY_HEADING as SNAP_RELATED_POLICY,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "data" / "corpus"
URL = "https://example.gov/rules"
KEEP = {"html_keep_navigation_blocks": True}
CHROME = {"html_navigation_selectors": [".chrome"]}
CHROME_HEADING = {"html_navigation_heading_selectors": ["h2.list-heading"]}
_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def _page(body: str, title: str = "Rules") -> bytes:
    return f"<!doctype html><html><head><title>{title}</title></head><body>{body}</body></html>".encode()


def _blocks(content: bytes, extraction: dict | None = None) -> list[tuple[int, str | None, str]]:
    blocks = _extract_html_blocks(
        content, source_url=URL, fallback_title="Rules", extraction=extraction
    )
    return [(block.ordinal, block.heading, block.body) for block in blocks]


TAB_PAGE = _page(
    "<p>Revised April 29, 2013</p>"
    "<h3>WAC 388-404-0005 How does age affect eligibility?</h3>"
    "<ul><li><h4><a href='#ci'>Clarifying Information</a></h4></li></ul>"
    "<h3 id='ci'>Clarifying Information - WAC 388-404-0005</h3>"
    "<p>When a child turns 18 they are an adult.</p>"
    "<h3>Worker Responsibilities - WAC 388-404-0005</h3>"
    "<p>Verify the child's age.</p>"
)


def test_a_declared_tab_link_block_is_dropped_and_later_blocks_keep_their_paths() -> None:
    every = _blocks(TAB_PAGE)
    kept = _blocks(TAB_PAGE, {"html_navigation_selectors": ["ul > li a[href^='#']"]})

    assert [ordinal for ordinal, _, _ in every] == [1, 2, 3, 4]
    assert every[1][2] == "Clarifying Information"
    assert kept == [every[0], every[2], every[3]]


def test_a_drop_selector_would_renumber_the_blocks_after_it() -> None:
    # Why the declared keys exist: html_drop_selectors empty the block before the
    # walk numbers it, so the blocks after it move up one ordinal.
    dropped = _blocks(TAB_PAGE, {"html_drop_selectors": ["ul > li a[href^='#']"]})

    assert [(ordinal, body) for ordinal, _, body in dropped] == [
        (1, "Revised April 29, 2013"),
        (2, "When a child turns 18 they are an adult."),
        (3, "Verify the child's age."),
    ]


def test_text_outside_the_matched_elements_keeps_the_whole_block() -> None:
    page = _page(
        "<h3>WAC 388-437-0005</h3>"
        "<ul><li><a href='#ci'>Clarifying Information</a> and "
        "<a href='#wr'>Worker Responsibilities</a></li></ul>"
        "<h3>Lottery winnings</h3>"
        "<ul><li>Barcode generated a tickle. See <a href='#wr'>Worker Responsibilities</a>"
        " for what to do.</li></ul>"
    )
    links_only = _blocks(page, {"html_navigation_selectors": ["a[href^='#']"]})
    with_joiner = _blocks(
        page,
        {
            "html_navigation_selectors": [
                "a[href^='#']",
                "li:has(> a[href='#ci']):has(> a[href='#wr'])",
            ]
        },
    )

    # The bare "and" between the links is text no link holds.
    assert links_only == _blocks(page)
    assert with_joiner == [
        (
            2,
            "Lottery winnings",
            "Barcode generated a tickle. See Worker Responsibilities for what to do.",
        )
    ]


def test_a_declared_heading_drops_the_list_it_starts_and_nothing_after() -> None:
    page = _page(
        "<h2>A-121 Receipt of Application</h2><p>Applications must be signed.</p>"
        "<h3>Related Policy</h3>"
        "<p>Application Requests, <a href='/a113'>A-113</a><br>What to Report, B-621</p>"
        "<p>Failure to Comply, <a href='/a420'>A-420</a></p>"
        "<h2>A-122 Filing the Application</h2><p>Staff file the application.</p>"
    )
    selectors = {
        "html_navigation_heading_selectors": [
            ":is(h2, h3, h4, h5, h6):-soup-contains('Related'):-soup-contains('Polic')"
        ]
    }
    every = _blocks(page)

    assert every[1][1:] == (
        "Related Policy",
        "Application Requests, A-113 What to Report, B-621\n\nFailure to Comply, A-420",
    )
    assert _blocks(page, selectors) == [every[0], every[2]]


def test_matched_elements_stay_in_the_tree_so_headings_inside_them_still_split_blocks() -> None:
    page = _page(
        "<div class='chrome'><h2>Clarifying Information</h2><p>A child is under 18.</p></div>"
        "<h2>Worker Responsibilities</h2><p>Verify age.</p>"
    )

    # The heading walk sees the matched heading; the block under it is all chrome.
    assert _blocks(page) == [
        (1, "Clarifying Information", "A child is under 18."),
        (2, "Worker Responsibilities", "Verify age."),
    ]
    assert _blocks(page, CHROME) == [(2, "Worker Responsibilities", "Verify age.")]


def test_keep_navigation_blocks_keeps_declared_blocks_too() -> None:
    extraction = {"html_navigation_selectors": ["ul > li a[href^='#']"], **KEEP}

    assert _blocks(TAB_PAGE, extraction) == _blocks(TAB_PAGE)


@pytest.mark.parametrize(
    "segmentation",
    [
        {
            "segmentation": "labeled_sections",
            "section_heading_pattern": r"^(?P<label>Sec\. \d+)\.\s+(?P<heading>.+)$",
        },
        {"segmentation": "anchor_range", "anchor_ids": ["a"]},
    ],
)
def test_declared_navigation_on_a_page_with_declared_sections_is_an_error(
    segmentation: dict,
) -> None:
    for key in ("html_navigation_selectors", "html_navigation_heading_selectors"):
        with pytest.raises(ValueError, match="positional blocks"):
            _extract_html_blocks(
                TAB_PAGE,
                source_url=URL,
                fallback_title="Rules",
                extraction={**segmentation, key: ["a"]},
            )


def test_a_webworks_page_drops_declared_blocks_with_their_ordinals() -> None:
    page = _page(
        "<div id='page_content'>"
        "<p class='Heading_1'>608 Hearings</p><p class='Body_Text'>A household may ask.</p>"
        "<p class='Heading_2'>Related Policy</p><p class='Body_Text'>Notices, B-621</p>"
        "<p class='Heading_2'>608-1 Requests</p>"
        "<p class='Body_Text'><span class='chrome'>Back to top</span></p>"
        "<p class='Heading_2'>608-2 Timing</p><p class='Body_Text'>Within 90 days.</p></div>"
    )
    extraction = {
        "html_navigation_selectors": [".chrome"],
        "html_navigation_heading_selectors": [".Heading_2:-soup-contains('Related Policy')"],
    }

    assert [ordinal for ordinal, _, _ in _blocks(page)] == [1, 2, 3, 4]
    assert _blocks(page, extraction) == [
        (1, "608 Hearings", "A household may ask."),
        (4, "608-2 Timing", "Within 90 days."),
    ]


def test_a_declared_fallback_block_is_dropped() -> None:
    page = _page("<div class='chrome'>Clarifying Information</div>")

    assert _blocks(page) == [(1, "Rules", "Clarifying Information")]
    assert _blocks(page, CHROME) == []


def test_html_inside_json_drops_declared_blocks() -> None:
    # The general filter is off for JSON (the check cannot see the HTML); a
    # declaration names elements of the HTML itself, so it applies.
    content = json.dumps({"html": TAB_PAGE.decode()}).encode()
    blocks = _extract_json_html_blocks(
        content,
        source_url=URL,
        fallback_title="Rules",
        extraction={"json_html_field": "html", "html_navigation_selectors": ["ul > li a"]},
    )

    assert [block.ordinal for block in blocks] == [1, 3, 4]


# Property: random pages of headings and paragraphs, some text wrapped in .chrome,
# some headings marked chrome.

_TEXT = st.text(alphabet="abcdefgh", min_size=1, max_size=6)
_SEGMENTS = st.lists(st.tuples(_TEXT, st.booleans()), min_size=1, max_size=3)
_ITEMS = st.lists(st.tuples(_SEGMENTS, st.booleans()), max_size=3)
_SECTIONS = st.lists(st.tuples(_TEXT, st.booleans(), _ITEMS), max_size=5)


def _render(opening: list, sections: list) -> bytes:
    def item(segments: list, as_list: bool) -> str:
        words = " ".join(
            f"<span class='chrome'>{html.escape(text)}</span>" if chrome else html.escape(text)
            for text, chrome in segments
        )
        return f"<ul><li>{words}</li></ul>" if as_list else f"<p>{words}</p>"

    parts = [item(*entry) for entry in opening]
    for heading, chrome, items in sections:
        parts.append(
            f"<h2 class='list-heading'>{heading}</h2>" if chrome else f"<h2>{heading}</h2>"
        )
        parts.extend(item(*entry) for entry in items)
    return _page("".join(parts))


def _declared(items: list, heading_chrome: bool) -> bool:
    return heading_chrome or all(chrome for segments, _ in items for _, chrome in segments)


@_SETTINGS
@given(opening=_ITEMS, sections=_SECTIONS)
def test_kept_blocks_are_every_block_minus_the_declared_ones(opening, sections) -> None:  # type: ignore[no-untyped-def]
    content = _render(opening, sections)
    every = _blocks(content)
    model = [(False, opening)] + [(chrome, items) for _, chrome, items in sections]
    model = [(chrome, items) for chrome, items in model if items]
    if not model:
        # No paragraphs: at most the whole-root fallback block of heading text,
        # which no .chrome element holds and no heading starts.
        assert len(every) == (1 if sections else 0)
        for extraction in (CHROME, CHROME_HEADING, {**CHROME, **CHROME_HEADING}):
            assert _blocks(content, extraction) == every
        return

    assert [ordinal for ordinal, _, _ in every] == list(range(1, len(model) + 1))
    expected = [
        block
        for block, (chrome, items) in zip(every, model, strict=True)
        if not _declared(items, chrome)
    ]
    assert _blocks(content, {**CHROME, **CHROME_HEADING}) == expected
    assert _blocks(content, {**CHROME, **CHROME_HEADING, **KEEP}) == every
    # Each key alone drops only what it declares.
    assert _blocks(content, CHROME) == [
        block for block, (_, items) in zip(every, model, strict=True) if not _declared(items, False)
    ]
    assert _blocks(content, CHROME_HEADING) == [
        block for block, (chrome, _) in zip(every, model, strict=True) if not chrome
    ]


# Retained pages: each selector the manifests name, on bytes the locked scopes hold.

WA_SCOPE = "us-wa/manual/2026-07-21-wa-eaz-manual"
TX_SNAP_SCOPE = "us-tx/manual/2026-09-10-snap-state-manual-completion"
TX_MEPD_SCOPE = "us-tx/manual/2026-09-10-medicaid-state-eligibility-manual"
TX_C120_SCOPE = "us-tx/manual/2026-07-13-tx-twh-c120"
MANIFESTS = {
    WA_SCOPE: "us-wa-eaz-manual.yaml",
    TX_SNAP_SCOPE: "us-tx-snap-manual-completion.yaml",
    TX_MEPD_SCOPE: "us-tx-medicaid-eligibility-manual.yaml",
    TX_C120_SCOPE: "us-tx-twh-c120-snap-deduction-amounts.yaml",
}


WA_TAB_LINKS = [
    'ul > li a[href*="#"]:-soup-contains("Clarifying Information", "Worker Responsibilities")',
    'ul > li:has(> a[href*="#"]:-soup-contains("Clarifying Information"))'
    ':has(> a[href*="#"]:-soup-contains("Worker Responsibilities"))',
    'ul > li :has(> a[href*="#"]:-soup-contains("Clarifying Information"))'
    ':has(> a[href*="#"]:-soup-contains("Worker Responsibilities"))',
]


def test_manifests_and_builders_name_the_same_selectors() -> None:
    assert MEDICAID_RELATED_POLICY == SNAP_RELATED_POLICY
    for scope, manifest in MANIFESTS.items():
        sources = OfficialDocumentManifest.load(REPO_ROOT / "manifests" / manifest).documents
        declared = {
            (
                tuple((source.extraction or {}).get("html_navigation_selectors") or ()),
                tuple((source.extraction or {}).get("html_navigation_heading_selectors") or ()),
            )
            for source in sources
        }
        expected = (tuple(WA_TAB_LINKS), ()) if scope == WA_SCOPE else ((), (SNAP_RELATED_POLICY,))
        assert declared == {expected}, manifest


def _retained(scope: str, source_id: str) -> tuple[list, list]:
    """Blocks of a retained page without and with its manifest's declared navigation."""
    manifest = OfficialDocumentManifest.load(REPO_ROOT / "manifests" / MANIFESTS[scope])
    source = next(source for source in manifest.documents if source.source_id == source_id)
    content = (CORPUS / "sources" / scope / "official-documents" / f"{source_id}.html").read_bytes()
    extraction = dict(source.extraction or {})
    plain = {
        key: value
        for key, value in extraction.items()
        if key not in {"html_navigation_selectors", "html_navigation_heading_selectors"}
    }

    def blocks(config: dict) -> list:
        return list(
            _extract_html_blocks(
                content,
                source_url=source.source_url,
                fallback_title=source.title,
                extraction=config or None,
            )
        )

    assert blocks({**extraction, **KEEP}) == blocks({**plain, **KEEP})
    return blocks(plain), blocks(extraction)


def _dropped(every: list, kept: list) -> list[tuple[int, str]]:
    assert kept == [block for block in every if block in kept]
    return [(block.ordinal, block.body) for block in every if block not in kept]


def test_wa_jump_links_inside_list_items() -> None:
    # Selector 1: ``ul > li a[href*="#"]`` with a tab label, here under an h4.
    every, kept = _retained(
        WA_SCOPE, "wa-dshs-eaz-015-esa-eligibility-z-manual-ea-z-age-requirements"
    )

    assert _dropped(every, kept) == [
        (3, "Clarifying Information and Worker Responsibilities"),
        (4, "Clarifying Information"),
    ]
    assert len(kept) == 6


def test_wa_two_links_joined_by_and_in_a_list_item() -> None:
    # Selector 2: the list item holding both links directly, so its "and" is
    # inside a matched element. The page also holds an unlinked "Clarifying
    # Information" label and a prose item with a Worker Responsibilities link;
    # both stay.
    every, kept = _retained(
        WA_SCOPE, "wa-dshs-eaz-100-esa-eligibility-z-manual-ea-z-emergency-food-supplements"
    )
    bodies = [block.body for block in kept]

    assert _dropped(every, kept) == [
        (2, "Clarifying Information and Worker Responsibilities"),
        (3, "Clarifying Information and Worker Responsibilities"),
    ]
    assert "Clarifying Information" in bodies
    assert any("Barcode generated a tickle" in body for body in bodies)


def test_wa_two_links_joined_by_and_inside_a_heading_in_a_list_item() -> None:
    # Selector 3: an element inside the list item (here ``h4 > span``) holding both links.
    every, kept = _retained(WA_SCOPE, "wa-dshs-eaz-194-esa-eligibility-z-manual-ea-z-verification")

    assert _dropped(every, kept) == [(3, "Clarifying Information and Worker Responsibilities")]


def test_tx_related_policy_headings_drop_their_lists() -> None:
    # h3, h4 and h5 "Related Policy" headings; titles and codes inside the links.
    every, kept = _retained(TX_SNAP_SCOPE, "tx-hhs-texas-works-a-120-office-procedures")
    dropped = _dropped(every, kept)
    related = [block for block in every if block.heading == "Related Policy"]

    assert [ordinal for ordinal, _ in dropped] == [block.ordinal for block in related]
    # 14 Related Policy headings; the navigation-block filter already drops three of their lists.
    assert len(dropped) == 11
    assert dropped[0] == (
        7,
        "Application Requests and Submissions, A-113 Filing the Application, A-122 "
        "Application Signature, A-122.1 Authorized Representatives (AR), A-170 "
        "Medical Programs, A-240 Children's Medicaid Redetermination Expectations, "
        "B-123.6 Denied EDGs, B-474.7 Additions to the Household, B-641",
    )


def test_tx_related_policy_lists_with_codes_outside_the_links_and_several_paragraphs() -> None:
    every, kept = _retained(TX_SNAP_SCOPE, "tx-hhs-texas-works-a-410-general-policy")
    dropped = dict(_dropped(every, kept))
    lists = [body for body in dropped.values() if "\n\n" in body]

    assert all(block.heading == "Related Policy" for block in every if block.ordinal in dropped)
    assert lists and lists[0].startswith(
        "Social Security Numbers (SSNs), A-144.1\n\nPostponed Verification Procedures, A-145.1"
    )


def test_tx_related_policies_and_colon_headings() -> None:
    for source_id, heading in (
        ("us-tx-medicaid-twh-a-220", "Related Policies"),
        ("us-tx-medicaid-mepd-e-1300", "Related Policy:"),
    ):
        every, kept = _retained(TX_MEPD_SCOPE, source_id)
        dropped = {ordinal for ordinal, _ in _dropped(every, kept)}

        assert heading in {block.heading for block in every if block.ordinal in dropped}
        assert {block.heading for block in every if block.ordinal in dropped} <= {
            "Related Policy",
            "Related Policy:",
            "Related Policies",
        }


def test_tx_related_policy_headings_written_with_a_no_break_space() -> None:
    # "Related\xa0Policy" (MEPD's copy of A-1320) and "Related \xa0Policy" (B-540):
    # the selector matches the two words apart, so the space between them is free.
    for scope, source_id, raw in (
        (
            TX_MEPD_SCOPE,
            "us-tx-medicaid-twh-a-1320",
            "<h4><strong>Related&nbsp;Policy</strong></h4>",
        ),
        (
            TX_SNAP_SCOPE,
            "tx-hhs-texas-works-b-540-centralized-benefit-services",
            "<h4>Related &nbsp;Policy</h4>",
        ),
    ):
        path = CORPUS / "sources" / scope / "official-documents" / f"{source_id}.html"
        assert raw in path.read_text()
        every, kept = _retained(scope, source_id)
        related = [block for block in every if block.heading == "Related Policy"]

        assert related
        assert [block for block in every if block not in kept] == related


def test_a_numbered_section_heading_is_never_a_related_policy_heading() -> None:
    selector = SNAP_RELATED_POLICY
    page = _page(
        "<h2>A-1234 Policy Related to Disaster Payments</h2><p>Exclude disaster payments.</p>"
        "<h3>Related Policy</h3><p>Disaster Payments, A-1324.3</p>"
        "<h3>Related Policies</h3><p>Other Payments, A-1324.4</p>"
    )

    assert _blocks(page, {"html_navigation_heading_selectors": [selector]}) == [
        (1, "A-1234 Policy Related to Disaster Payments", "Exclude disaster payments.")
    ]


def test_tx_c120_wayback_page() -> None:
    every, kept = _retained(TX_C120_SCOPE, "tx-twh-c-120-snap-deduction-amounts")

    assert [block.heading for block in every if block not in kept] == ["Related Policy"] * 3
    # The deduction amounts encodings cite stay where they were.
    assert all(block in every for block in kept)
