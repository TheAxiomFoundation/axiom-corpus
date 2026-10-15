"""The release content checks (``axiom_corpus.corpus.content_quality``).

Invariants, for every input:

- Coverage is a share in [0, 1], and the residual word count never exceeds the
  number of tokens.
- A body that is exactly one of its page's navigation strings is navigation,
  unless it repeats the row's own heading.
- A page with no navigation strings never makes a body navigation; such a body
  is prefixed only through a skip link or JavaScript notice.
- A body is text exactly when it has a word with a letter and is not
  navigation.
- A scope's findings do not depend on the order of its records, are sorted and
  unique, and its hollow roots are bodyless ``document`` rows with no text-
  bearing row below them; ``text_paths`` never contains a hollow root.
- Adding a text-bearing row can only remove hollow roots.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.content_quality import (
    _SKIP_LINK,
    HOLLOW_DOCUMENT_ROOT,
    HTML_SNIFF_BYTES,
    MAX_BODY_TOKENS,
    NAVIGATION_BODY,
    NAVIGATION_PREFIXED_BODY,
    PREFIX_TOKENS,
    PREFIXED_MIN_TOKENS,
    VERSION_PICKER_SOURCE,
    PageNavigation,
    ScopeContentScanner,
    classify_body,
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


def test_text_after_the_navigation_sample_is_substantive() -> None:
    body = " ".join(str(number) for number in range(1, MAX_BODY_TOKENS + 1)) + " Tax liability."
    page = _page()
    with patch.object(page, "cover", wraps=page.cover) as cover:
        verdict = classify_body(body, page)
    assert (verdict.navigation, verdict.prefixed, verdict.substantive) == (False, False, True)
    cover.assert_called_once()
    assert len(cover.call_args.args[0]) == MAX_BODY_TOKENS


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


@_SETTINGS
@given(opening=st.integers(min_value=0, max_value=7))
def test_dense_glossary_links_need_an_opening_run_to_make_a_prefix(opening: int) -> None:
    """Dense glossary links need an opening run before they can count as chrome."""
    glossary = PageNavigation(["Household"])
    head = (
        ["Household"] * opening + ["resident"] + ["Household"] * (30 - opening) + ["resident"] * 29
    )
    assert len(head) == PREFIX_TOKENS
    assert glossary.coverage(head).share >= 0.4
    body = " ".join(head + ["resident"] * (PREFIXED_MIN_TOKENS - PREFIX_TOKENS))
    verdict = classify_body(body, glossary)
    assert (verdict.navigation, verdict.prefixed, verdict.substantive) == (False, False, True)


def test_version_picker_detection_follows_the_adapter() -> None:
    assert is_version_picker(PICKER.encode())
    with_section = PICKER.replace("</form>", "</form><div id='single_law_section'>text</div>")
    assert not is_version_picker(with_section.encode())
    assert not is_version_picker(PAGE.encode())
    assert not is_version_picker(b"%PDF-1.7 selectFromMultiples")


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


def test_a_root_with_text_after_the_navigation_sample_is_not_hollow(tmp_path: Path) -> None:
    body = " ".join(str(number) for number in range(1, MAX_BODY_TOKENS + 1)) + " Tax liability."
    source = _write(tmp_path, "sources/us-xx/statute/v1/page.html", f"<html><p>{body}</p></html>")
    root = "us-xx/statute/17014"
    child = root + "/block-1"
    scanner = ScopeContentScanner(tmp_path)
    scanner.add(_record(root, None, kind="document", source_path=source))
    scanner.add(_record(child, body, kind="block", source_path=source))
    assert scanner.findings() == ()
    assert scanner.text_paths() == {root, child}


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
    assert verdict.substantive == any(char.isalpha() for char in body)


@_SETTINGS
@given(strings=st.lists(_PHRASE, max_size=8), tokens=st.lists(_TOKEN, max_size=120))
def test_text_means_letters_and_not_navigation(strings: list[str], tokens: list[str]) -> None:
    verdict = classify_body(" ".join(tokens), PageNavigation(strings))
    has_letters = any(char.isalpha() for token in tokens for char in token)
    assert verdict.substantive == (has_letters and not verdict.navigation)
    assert not (verdict.navigation and verdict.prefixed)


@_SETTINGS
@given(
    before=st.integers(min_value=0, max_value=MAX_BODY_TOKENS * 2),
    after=st.integers(min_value=0, max_value=MAX_BODY_TOKENS * 2),
    word=st.text(alphabet=st.characters(categories=("L",)), min_size=1, max_size=16).filter(
        lambda word: word not in " ".join(MENU).split()
    ),
)
@example(before=MAX_BODY_TOKENS, after=0, word="Tax")
@example(before=0, after=MAX_BODY_TOKENS, word="Tax")
@example(before=MAX_BODY_TOKENS + 1, after=MAX_BODY_TOKENS, word="税")
def test_a_lettered_word_anywhere_makes_a_body_and_its_root_text(
    before: int, after: int, word: str
) -> None:
    body = " ".join(["17014"] * before + [word] + ["17014"] * after)
    verdict = classify_body(body, _page())
    assert (verdict.navigation, verdict.prefixed, verdict.substantive) == (False, False, True)
    root = "us-xx/statute/17014"
    child = root + "/block-1"
    scanner = ScopeContentScanner(Path("."))
    scanner.add(_record(root, None, kind="document"))
    scanner.add(_record(child, body, kind="block"))
    assert scanner.findings() == ()
    assert scanner.text_paths() == {root, child}


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
@example(prefix=b"<!doctype html>", rest=b"")
@example(prefix=b"<!doctype html>", rest=b"<!--selectFromMultiples-->")
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
