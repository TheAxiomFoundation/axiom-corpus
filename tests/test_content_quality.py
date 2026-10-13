"""The release content checks (``axiom_corpus.corpus.content_quality``).

Invariants, for every input:

- Coverage is a share in [0, 1], and the residual word count never exceeds the
  number of tokens.
- A body that is exactly one of its page's navigation strings is navigation,
  unless it repeats the row's own heading.
- A page with no navigation strings never makes a body navigation; such a body
  is prefixed only through a skip link or JavaScript notice.
- A body is text exactly when it is not navigation and has a word with a
  letter or is a table of figures (at least ``FIGURE_TEXT_MIN_TOKENS`` figures,
  at least ``FIGURE_TEXT_MIN_SHARE`` of its tokens). The figure rule decides
  substance only, never the navigation or prefix verdicts.
- A table of figures stays one when a figure is added; fewer than
  ``FIGURE_TEXT_MIN_TOKENS`` tokens never are one.
- A scope's findings do not depend on the order of its records, are sorted and
  unique, and its hollow roots are bodyless ``document`` rows with no text-
  bearing row below them; ``text_paths`` never contains a hollow root.
- Adding a text-bearing row can only remove hollow roots.
- A reviewed-empty list removes exactly the hollow roots it names from the
  findings, reports them in ``reviewed_empty_roots``, and changes nothing else
  (other findings and ``text_paths`` alike).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import content_quality
from axiom_corpus.corpus.content_quality import (
    _SKIP_LINK,
    FIGURE_TEXT_MIN_SHARE,
    FIGURE_TEXT_MIN_TOKENS,
    HOLLOW_DOCUMENT_ROOT,
    HTML_SNIFF_BYTES,
    NAVIGATION_BODY,
    NAVIGATION_PREFIXED_BODY,
    PREFIX_TOKENS,
    PREFIXED_MIN_TOKENS,
    VERSION_PICKER_SOURCE,
    PageNavigation,
    ScopeContentScanner,
    classify_body,
    is_figure,
    is_figure_table,
    is_navigation_string,
    is_version_picker,
    looks_like_html,
    page_navigation,
    scan_provisions,
)
from axiom_corpus.corpus.models import ProvisionRecord

_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

MENU = ("Home", "About Us", "Contact Us", "Help", "Advanced Search", "Sign In")
PAGE = (
    "<!doctype html><html><head><title>Code Section</title></head><body>"
    "<header><a href='/'>Skip to main content</a></header>"
    "<nav><ul>" + "".join(f"<li><a href='#'>{item}</a></li>" for item in MENU) + "</ul></nav>"
    "<div id='law'><p>(a) Every individual who is in this state for other than a temporary "
    "or transitory purpose is a resident, as defined in <a href='#'>section 17014</a>.</p>"
    "<p>[Repealed, <a href='#'>1990 c 604 art 2 s 21</a>]</p></div>"
    "<footer><a href='#'>Privacy Policy</a> <a href='#'>Accessibility Statement</a></footer>"
    "</body></html>"
)
LAW = (
    "(a) Every individual who is in this state for other than a temporary or transitory "
    "purpose is a resident, as defined in section 17014."
)
PICKER = (
    "<html><body><form id='selectFromMultiples' action='/faces/selectFromMultiples.xhtml'>"
    "<a onclick=\"x({'op_statues':'2024'})\">(Amended by Stats. 2024, Ch. 798, Sec. 1.)</a>"
    "</form></body></html>"
)


def _record(path: str, body: str | None, **fields: object) -> ProvisionRecord:
    return ProvisionRecord(
        jurisdiction="us-xx",
        document_class="statute",
        citation_path=path,
        body=body,
        version="v1",
        **fields,  # type: ignore[arg-type]
    )


def _page() -> PageNavigation:
    return page_navigation(PAGE.encode())


def test_navigation_strings_exclude_citation_links() -> None:
    assert is_navigation_string("Contact Us")
    assert is_navigation_string("中文 (Simplified Chinese)")
    assert not is_navigation_string("17014")
    assert not is_navigation_string("1990 c 604 art 2 s 21")
    assert not is_navigation_string("x")


def test_page_navigation_reads_links_nav_header_and_footer_but_not_the_law() -> None:
    page = _page()
    menu = " ".join(MENU).split()
    assert all(page.cover(menu))
    law = LAW.split()
    covered = page.cover(law)
    # Only the link "section 17014" is a navigation string, and it is not one
    # (it is a citation); nothing in the law is covered.
    assert not any(covered)


def test_matching_is_by_whole_words() -> None:
    page = PageNavigation(["Home"])
    assert page.cover(["Homestead", "exemption"]) == [False, False]
    assert page.cover(["Home"]) == [True]


def test_a_menu_body_is_navigation_and_law_is_text() -> None:
    page = _page()
    menu = classify_body("\n\n".join(MENU), page)
    assert (menu.navigation, menu.substantive) == (True, False)
    law = classify_body(LAW, page)
    assert (law.navigation, law.prefixed, law.substantive) == (False, False, True)
    repealed = classify_body("[Repealed, 1990 c 604 art 2 s 21 ]", page)
    assert (repealed.navigation, repealed.substantive) == (False, True)


def test_a_body_that_repeats_its_heading_is_not_navigation() -> None:
    page = PageNavigation(["Chapter 1: General provisions"])
    body = "Chapter 1: General provisions"
    assert classify_body(body, page).navigation
    assert not classify_body(body, page, heading=body).navigation


def test_chrome_before_the_text_is_a_prefixed_body() -> None:
    page = _page()
    body = "Skip to main content " + " ".join(MENU) + " " + " ".join([LAW] * 6)
    verdict = classify_body(body, page)
    assert (verdict.navigation, verdict.prefixed, verdict.substantive) == (False, True, True)
    # The same text with no chrome in front of it is not.
    assert not classify_body(" ".join([LAW] * 7), page).prefixed


def test_linked_terms_inside_prose_do_not_make_a_prefix() -> None:
    glossary = PageNavigation(["Household", "Overview", "Rights and Responsibilities"])
    body = (
        "Household People who buy and prepare food together are usually counted as the "
        "same household. " + " ".join([LAW] * 6)
    )
    assert not classify_body(body, glossary).prefixed


def test_version_picker_detection_follows_the_adapter() -> None:
    assert is_version_picker(PICKER.encode())
    with_section = PICKER.replace("</form>", "</form><div id='single_law_section'>text</div>")
    assert not is_version_picker(with_section.encode())
    assert not is_version_picker(PAGE.encode())
    assert not is_version_picker(b"%PDF-1.7 selectFromMultiples")


# The body of IL CSMM item 67224, WAG 25-06-05-a (1), the minimum monthly SNAP
# benefit for one or two persons: dates and amounts only.
IL_MINIMUM_BENEFIT = (
    "04/09 - 10/13 11/13 - 09/14 10/14 - 09/17 10/17 - 09/19 10/19-- 12/20 01/21- 09/21 "
    "10/21- 09/22 10/22- 09/25 10/25- 09/26 $16 $15 $16 $15 $16 $19 $20 $23 $24"
)
# Letterless bodies seen in the locked scopes that are not text: date stamps on
# scanned CMS pages, a page number, a stamp with its SPA numbers, and a page
# whose font maps glyphs to control characters, with a stray digit or two.
NOT_TEXT = (
    "9/4/13",
    "178",
    "11/22/2019 04/01/2016",
    "5 30 14",
    "10/1/11 1/12/12 11-009 01-004",
    "\x00\x01\x02\x03\x05 \x07 1 \x03\x08 2 \x07\x10 \x10\x05 3 \x12\x13 4 \x14 5 "
    "\x15\x16 \x17\x15 \x19\x17 \x1a\x1b \x12\x13 \x14\x15 \x16\x15 \x13\x14 \x15\x13",
    "§ — ;",
)


def test_figures_are_numbers_dates_amounts_and_rates() -> None:
    for token in (
        "16",
        "$1,014.00",
        ".9666",
        "10/19--",
        "($450,000)",
        "2.5%",
        "8411.11.40",
        "23/24",
    ):
        assert is_figure(token), token
    for token in ("§", "-", "—", "1a", "Ch.", "\x05\x061", "$", "%"):
        assert not is_figure(token), token


def test_a_table_of_figures_is_text_and_a_stamp_is_not() -> None:
    verdict = classify_body(IL_MINIMUM_BENEFIT, None)
    assert (verdict.navigation, verdict.prefixed, verdict.substantive) == (False, False, True)
    projections = "23/24 24/25 25/26 26/27 27/28 ($450,000) ($800,000) ($900,000)"
    assert classify_body(projections, None).substantive
    for body in NOT_TEXT:
        assert not classify_body(body, None).substantive, body


def test_a_root_over_a_figure_table_has_text_and_one_over_date_stamps_does_not(
    tmp_path: Path,
) -> None:
    records = [
        # IL item 67224: the table is the item's text.
        _record("us-xx/manual/67224", None, kind="document"),
        _record("us-xx/manual/67224/block-1", IL_MINIMUM_BENEFIT, kind="block"),
        # A scanned attachment whose text layer is each page's date stamp
        # (OH-12-004): no text, so the root is hollow.
        _record("us-xx/manual/oh-12-004", None, kind="document"),
        *(
            _record(f"us-xx/manual/oh-12-004/page-{page}", "9/4/13", kind="page")
            for page in (1, 2, 3)
        ),
    ]
    findings = scan_provisions(tmp_path, records)
    assert [(finding.code, finding.path) for finding in findings] == [
        (HOLLOW_DOCUMENT_ROOT, "us-xx/manual/oh-12-004")
    ]


def test_bodies_just_under_the_navigation_bar_keep_their_text() -> None:
    """Why ``NAVIGATION_COVERAGE`` stays 0.7 (docs/release-gate-policy.md).

    Between 0.65 and 0.7 the locked scopes hold page chrome and law alike: a
    repeal notice beside its "Return to Table of Contents" link (0.66), and
    manual prose whose terms are links (0.656). The Maine menu that lost
    §5219-SS's text sits at 0.692 among them.
    """
    toc = PageNavigation(["Return to Table of Contents"])
    repealed = classify_body("Repealed February 10, 2004. Return to Table of Contents", toc)
    assert (repealed.navigation, repealed.substantive) == (False, True)
    linked_terms = PageNavigation(
        [
            "Medicare Savings Programs",
            "Medical Assistance for People Who Are Age 65 or Older and People Who Are Blind "
            "or Have a Disability",
            "Household Composition",
        ]
    )
    prose = classify_body(
        "The Medicare Savings Programs (MSP) generally follow the standard Medical "
        "Assistance for People Who Are Age 65 or Older and People Who Are Blind or Have a "
        "Disability (MA-ABD) Household Composition and Family Size policy.",
        linked_terms,
    )
    assert (prose.navigation, prose.substantive) == (False, True)


def _write(root: Path, relative: str, payload: str) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return relative


def test_scanner_reports_each_kind_of_finding(tmp_path: Path) -> None:
    page = _write(tmp_path, "sources/us-xx/statute/v1/page.html", PAGE)
    picker = _write(tmp_path, "sources/us-xx/statute/v1/picker.html", PICKER)
    records = [
        # A section root whose only child is the site menu: hollow.
        _record("us-xx/statute/1", None, kind="document", heading="1", source_path=page),
        _record("us-xx/statute/1/block-1", "\n\n".join(MENU), kind="block", source_path=page),
        # A section root with the law below it: the extractor's normal shape.
        _record("us-xx/statute/2", None, kind="document", heading="2", source_path=page),
        _record("us-xx/statute/2/block-1", "\n\n".join(MENU), kind="block", source_path=page),
        _record("us-xx/statute/2/block-2", LAW, kind="block", source_path=page),
        # A root whose text comes from a version picker carries none.
        _record("us-xx/statute/3", None, kind="document", heading="3", source_path=picker),
        _record(
            "us-xx/statute/3/block-1",
            "(Amended by Stats. 2024, Ch. 798, Sec. 1.)",
            kind="block",
            source_path=picker,
        ),
        _record(
            "us-xx/statute/4",
            "Skip to main content " + " ".join(MENU) + " " + " ".join([LAW] * 6),
            kind="section",
            source_path=page,
        ),
    ]
    scanner = ScopeContentScanner(tmp_path)
    for record in records:
        scanner.add(record)
    found = {(finding.code, finding.path) for finding in scanner.findings()}
    assert found == {
        (HOLLOW_DOCUMENT_ROOT, "us-xx/statute/1"),
        (NAVIGATION_BODY, "us-xx/statute/1/block-1"),
        (NAVIGATION_BODY, "us-xx/statute/2/block-1"),
        (HOLLOW_DOCUMENT_ROOT, "us-xx/statute/3"),
        (NAVIGATION_PREFIXED_BODY, "us-xx/statute/4"),
        (VERSION_PICKER_SOURCE, picker),
    }
    assert scanner.text_paths() == {
        "us-xx/statute/2",
        "us-xx/statute/2/block-2",
        "us-xx/statute/4",
    }


def test_rows_without_html_sources_are_never_navigation(tmp_path: Path) -> None:
    pdf = _write(tmp_path, "sources/us-xx/statute/v1/doc.pdf", "%PDF-1.7 Home Contact Us")
    findings = scan_provisions(
        tmp_path,
        [
            _record("us-xx/statute/d", None, kind="document", source_path=pdf),
            _record("us-xx/statute/d/page-1", "Home Contact Us", kind="page", source_path=pdf),
        ],
    )
    assert findings == ()


_WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGH", min_size=2, max_size=8)
_PHRASE = st.lists(_WORD, min_size=1, max_size=4).map(" ".join)
_TOKEN = st.one_of(_WORD, st.sampled_from(["17014", "(a)", "§", "—", "2,500", ";"]))


@_SETTINGS
@given(strings=st.lists(_PHRASE, max_size=12), tokens=st.lists(_TOKEN, max_size=80))
def test_coverage_is_a_share_and_residual_is_bounded(strings: list[str], tokens: list[str]) -> None:
    coverage = PageNavigation(strings).coverage(tokens)
    assert 0.0 <= coverage.share <= 1.0
    assert 0 <= coverage.residual_words <= len(tokens)
    assert coverage.tokens == len(tokens)


@_SETTINGS
@given(strings=st.lists(_PHRASE, min_size=1, max_size=12), data=st.data())
def test_a_body_that_is_one_navigation_string_is_navigation(
    strings: list[str], data: st.DataObject
) -> None:
    body = data.draw(st.sampled_from(strings))
    page = PageNavigation(strings)
    assert classify_body(body, page).navigation
    assert not classify_body(body, page, heading=body).navigation


@_SETTINGS
@given(tokens=st.lists(_TOKEN, max_size=200))
def test_without_navigation_strings_only_a_skip_link_can_flag_a_body(tokens: list[str]) -> None:
    body = " ".join(tokens)
    verdict = classify_body(body, PageNavigation([]))
    assert not verdict.navigation
    skip_link = bool(_SKIP_LINK.search(" ".join(tokens[:PREFIX_TOKENS])))
    assert verdict.prefixed == (len(tokens) >= PREFIXED_MIN_TOKENS and skip_link)
    assert verdict.substantive == (any(char.isalpha() for char in body) or is_figure_table(tokens))


_FIGURE_TOKEN = st.sampled_from(["16", "$15", "04/09", "10/19--", "(450,000)", ".9666", "2.5%"])
_ANY_TOKEN = st.one_of(_TOKEN, _FIGURE_TOKEN, st.sampled_from(["-", "§", "\x05\x06", "\x071"]))


@_SETTINGS
@given(strings=st.lists(_PHRASE, max_size=8), tokens=st.lists(_ANY_TOKEN, max_size=120))
def test_text_means_letters_or_figures_and_not_navigation(
    strings: list[str], tokens: list[str]
) -> None:
    page = PageNavigation(strings)
    verdict = classify_body(" ".join(tokens), page)
    has_letters = any(char.isalpha() for token in tokens for char in token)
    assert verdict.substantive == (
        (has_letters or is_figure_table(tokens)) and not verdict.navigation
    )
    assert not (verdict.navigation and verdict.prefixed)
    # The figure rule decides substance only: forcing it either way leaves the
    # navigation and prefix verdicts as they were.
    for forced in (True, False):
        with mock.patch.object(content_quality, "is_figure_table", return_value=forced):
            other = classify_body(" ".join(tokens), page)
        assert (other.navigation, other.prefixed) == (verdict.navigation, verdict.prefixed)


@_SETTINGS
@given(tokens=st.lists(_ANY_TOKEN, max_size=60), extra=_FIGURE_TOKEN)
def test_a_figure_table_grows_by_figures_and_needs_enough_of_them(
    tokens: list[str], extra: str
) -> None:
    if is_figure_table(tokens):
        assert is_figure_table([*tokens, extra])
    if len(tokens) < FIGURE_TEXT_MIN_TOKENS:
        assert not is_figure_table(tokens)
    figures = sum(1 for token in tokens if is_figure(token))
    assert is_figure_table(tokens) == (
        figures >= FIGURE_TEXT_MIN_TOKENS and figures >= FIGURE_TEXT_MIN_SHARE * len(tokens)
    )


_ROW_BODIES = st.sampled_from(
    [None, "", "   ", "\n\n".join(MENU), LAW, "Reserved.", "17014", "Home Contact Us"]
)
_KINDS = st.sampled_from(["document", "block", "section"])
_PATHS = st.sampled_from(["a", "a/b", "a/b/c", "a/d", "e", "e/f"])


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    rows=st.lists(
        st.tuples(_PATHS, _KINDS, _ROW_BODIES), max_size=12, unique_by=lambda row: row[0]
    ),
    order=st.randoms(use_true_random=False),
)
def test_scope_findings_are_order_free_and_hollow_roots_are_well_formed(rows, order) -> None:  # type: ignore[no-untyped-def]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = _write(root, "sources/us-xx/statute/v1/page.html", PAGE)
        records = [
            _record(f"us-xx/statute/{path}", body, kind=kind, source_path=source)
            for path, kind, body in rows
        ]
        shuffled = list(records)
        order.shuffle(shuffled)
        first = ScopeContentScanner(root)
        second = ScopeContentScanner(root)
        for record in records:
            first.add(record)
        for record in shuffled:
            second.add(record)
        findings = first.findings()
        assert findings == second.findings()
        assert list(findings) == sorted(set(findings))
        hollow = {f.path for f in findings if f.code == HOLLOW_DOCUMENT_ROOT}
        empty_roots = {
            r.citation_path for r in records if r.kind == "document" and not (r.body or "").strip()
        }
        assert hollow <= empty_roots
        text = first.text_paths()
        assert not hollow & text
        for root_path in empty_roots - hollow:
            assert any(path.startswith(root_path + "/") for path in text)
        # Adding a row with text below a hollow root clears it and adds no other.
        if hollow:
            target = sorted(hollow)[0]
            first.add(_record(target + "/z", LAW, kind="block", source_path=source))
            after = {f.path for f in first.findings() if f.code == HOLLOW_DOCUMENT_ROOT}
            assert after <= hollow and target not in after


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    rows=st.lists(
        st.tuples(_PATHS, _KINDS, _ROW_BODIES), max_size=12, unique_by=lambda row: row[0]
    ),
    reviewed=st.sets(_PATHS.map(lambda path: f"us-xx/statute/{path}"), max_size=4),
)
def test_reviewed_empty_rows_leave_the_findings_and_nothing_else(rows, reviewed) -> None:  # type: ignore[no-untyped-def]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = _write(root, "sources/us-xx/statute/v1/page.html", PAGE)
        records = [
            _record(f"us-xx/statute/{path}", body, kind=kind, source_path=source)
            for path, kind, body in rows
        ]
        plain = ScopeContentScanner(root)
        exempting = ScopeContentScanner(root, reviewed_empty=reviewed)
        for record in records:
            plain.add(record)
            exempting.add(record)
        hollow = {f.path for f in plain.findings() if f.code == HOLLOW_DOCUMENT_ROOT}
        assert exempting.reviewed_empty_roots() == tuple(sorted(hollow & reviewed))
        assert set(exempting.findings()) == {
            finding
            for finding in plain.findings()
            if not (finding.code == HOLLOW_DOCUMENT_ROOT and finding.path in reviewed)
        }
        assert exempting.text_paths() == plain.text_paths()
        assert plain.reviewed_empty_roots() == ()


def test_a_reviewed_empty_row_is_exempt_only_while_it_is_hollow(tmp_path: Path) -> None:
    page = _write(tmp_path, "sources/us-xx/statute/v1/page.html", PAGE)
    toc = _record("us-xx/statute/toc", None, kind="document", heading="Contents", source_path=page)
    menu = _record("us-xx/statute/toc/block-1", "\n\n".join(MENU), kind="block", source_path=page)
    reviewed = {"us-xx/statute/toc", "us-xx/statute/absent"}
    findings = scan_provisions(tmp_path, [toc, menu], reviewed_empty=reviewed)
    # The menu block is still navigation; only the root's hollowness is exempt.
    assert [(f.code, f.path) for f in findings] == [(NAVIGATION_BODY, "us-xx/statute/toc/block-1")]
    scanner = ScopeContentScanner(tmp_path, reviewed_empty=reviewed)
    for record in (toc, menu, _record("us-xx/statute/toc/block-2", LAW, kind="block")):
        scanner.add(record)
    # With text below it the row is not hollow, so the list exempts nothing.
    assert scanner.reviewed_empty_roots() == ()


def test_findings_serialize_by_code_and_path() -> None:
    finding = scan_provisions(Path("."), [_record("us-xx/statute/x", None, kind="document")])[0]
    assert (finding.code, finding.path) == (HOLLOW_DOCUMENT_ROOT, "us-xx/statute/x")
    assert json.dumps([finding.code, finding.path])


def test_named_anchors_and_in_content_headers_are_not_navigation() -> None:
    page = page_navigation(
        b"<html><body><nav><a href='/'>Home</a></nav><article>"
        b"<header><h1>Section 5 Earned income credit</h1></header>"
        b"<p><a name='s5'>The credit equals 30 percent of the federal credit.</a></p>"
        b"</article></body></html>"
    )
    assert classify_body("Home", page).navigation
    assert not classify_body("Section 5 Earned income credit", page).navigation
    assert not classify_body("The credit equals 30 percent of the federal credit.", page).navigation


def test_a_body_that_is_its_label_and_heading_is_not_navigation() -> None:
    page = PageNavigation(["Subpart A—General Provisions"])
    body = "Subpart A—General Provisions"
    assert classify_body(body, page).navigation
    assert not classify_body(body, page, heading="General provisions", label="Subpart A").navigation
    assert not classify_body(body, page, heading="SUBPART A - GENERAL PROVISIONS").navigation


def test_xml_with_a_body_element_is_not_html() -> None:
    from axiom_corpus.corpus.content_quality import looks_like_html

    assert not looks_like_html(b"<?xml version='1.0'?><akomaNtoso><act><body>x</body></act>")
    assert looks_like_html(b"<?xml version='1.0'?><!DOCTYPE html><html><body>x</body></html>")
    assert looks_like_html(b"<body><p>fragment</p></body>")


_JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=20),
    lambda children: st.lists(children, max_size=3)
    | st.dictionaries(st.text(max_size=5), children, max_size=3),
    max_leaves=6,
)


@settings(max_examples=200, deadline=None)
@given(
    rows=st.lists(
        st.fixed_dictionaries(
            {"citation_path": st.text(min_size=1, max_size=30)},
            optional={
                "body": _JSON | st.just("\n\n".join(MENU)),
                "heading": _JSON,
                "citation_label": _JSON,
                "source_path": _JSON
                | st.sampled_from(
                    ["page.html", "nul\x00.html", "../page.html", "/etc/passwd", "absent.html"]
                ),
                "kind": _JSON | st.just("document"),
            },
        ),
        max_size=6,
    )
)
def test_the_scanner_accepts_any_row_the_loader_yields(rows: list[dict]) -> None:
    """``validate_release`` feeds the scanner every record it loads; no field may make it raise."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "page.html").write_text(PAGE, encoding="utf-8")
        scanner = ScopeContentScanner(root)
        for row in rows:
            scanner.add(
                ProvisionRecord.from_mapping(
                    {"jurisdiction": "us-xx", "document_class": "statute", **row}
                )
            )
        scanner.findings()
        scanner.text_paths()


@settings(max_examples=300, deadline=None)
@given(
    prefix=st.sampled_from(
        [
            b"<html>",
            b"<!doctype html><html>",
            b"<?xml version='1.0' encoding='latin-1'?><html>",
            b"<html><head><meta charset='x-unknown'>",
        ]
    ),
    rest=st.binary(max_size=400) | st.text(max_size=200).map(lambda text: text.encode()),
)
def test_reading_a_page_never_raises(prefix: bytes, rest: bytes) -> None:
    """Any bytes behind an HTML start read as a page or as no page, never as an error."""
    raw = prefix + rest
    assert looks_like_html(raw[:HTML_SNIFF_BYTES])
    page_navigation(raw)
    is_version_picker(raw)


def test_source_paths_outside_the_corpus_are_never_read(tmp_path: Path) -> None:
    outside = tmp_path / "outside.html"
    outside.write_text(PAGE, encoding="utf-8")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    findings = scan_provisions(
        corpus,
        [
            _record(
                "us-xx/statute/a", "\n\n".join(MENU), kind="block", source_path="../outside.html"
            ),
            _record("us-xx/statute/b", "\n\n".join(MENU), kind="block", source_path=str(outside)),
        ],
    )
    assert findings == ()
