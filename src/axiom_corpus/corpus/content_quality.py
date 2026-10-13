"""Content checks for release scopes: rows that carry a web page's furniture, not its text.

The July 2026 US source recovery merged scopes whose rows passed every structural
release check yet held no legal text: LegInfo menus at statute section paths, a
LegInfo version picker in place of WIC 11450, and empty ``document`` roots whose
only descendants were navigation (docs/ingest-runs/2026-09-25-us-ca-statute-
recovery-audit.md and 2026-09-27-recovery-sibling-scopes-audit.md). This module
finds those shapes in any scope from its provisions and its retained HTML
sources. Each finding names one row or one source file:

``navigation_body``
    The row's body is made of its source page's navigation text. A page's
    navigation text is the text of every ``a``, ``option`` and ``button``
    element, of ``nav``, ``header`` and ``footer``, and of elements with a
    navigation, banner or contentinfo role, keeping only strings that are
    mostly letters, so citation links ("1990 c 604 art 2 s 21", "17041") are
    not navigation. A body is navigation when those strings cover at least
    ``NAVIGATION_COVERAGE`` of its characters, matched as whole word runs, and
    at most ``NAVIGATION_RESIDUAL_WORDS`` words are left over. A body that only
    repeats the row's own heading is a heading row, not navigation, even when
    the page's table of contents links that heading.
``navigation_prefixed_body``
    The row holds text, but it opens with page chrome: a skip link or a
    JavaScript notice within its first ``PREFIX_TOKENS`` words, or an opening
    run of at least ``PREFIX_RUN_TOKENS`` navigation words in a first
    ``PREFIX_TOKENS`` words that are at least ``PREFIX_COVERAGE`` navigation.
    The rest of the body must not itself be mostly navigation.
``hollow_document_root``
    A ``document`` row with no body whose descendants in the scope (rows whose
    citation path extends it) carry no text: each is empty, has no word with a
    letter in it, is a ``navigation_body``, or comes from a version picker. A bodyless root with text below
    it is the shared document extractor's normal shape (the wave4 chapter
    scopes keep each section's text in one child block), so emptiness alone is
    not a finding, and neither is a short text: "Reserved." is a section's
    text.
``version_picker_source``
    A retained HTML source is a LegInfo "select from multiples" page: it has
    the ``form#selectFromMultiples`` the California adapter resolves
    (``states._resolve_california_multiple_section_html``) and no
    ``#single_law_section``, so it holds a list of versions, not a section.

The checks read only the bytes a scope's lock pins, so a scope's findings never
change unless this module does. ``CONTENT_CHECK_VERSION`` names the rules; the
release content baseline records it with every scope's findings.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import lxml.html
from lxml import etree

from axiom_corpus.corpus.models import ProvisionRecord

CONTENT_CHECK_VERSION = "content-check-v1"

NAVIGATION_BODY = "navigation_body"
NAVIGATION_PREFIXED_BODY = "navigation_prefixed_body"
HOLLOW_DOCUMENT_ROOT = "hollow_document_root"
VERSION_PICKER_SOURCE = "version_picker_source"
FINDING_CODES = (
    NAVIGATION_BODY,
    NAVIGATION_PREFIXED_BODY,
    HOLLOW_DOCUMENT_ROOT,
    VERSION_PICKER_SOURCE,
)

# Share of a body's characters that navigation strings must cover, and the
# words they may leave over, for the body to count as navigation.
NAVIGATION_COVERAGE = 0.7
NAVIGATION_RESIDUAL_WORDS = 25
# Words a body is read to, so a very long row costs no more than this.
MAX_BODY_TOKENS = 1200
# The opening of a body that the prefix check reads, the share of it that
# navigation strings must cover, and the run of navigation words it must open
# with. Glossary and cross-reference links in manual prose reach the share but
# not the opening run. A prefixed body must hold at least PREFIXED_MIN_TOKENS
# words, and the rest of it must not itself be navigation.
PREFIX_TOKENS = 60
PREFIX_COVERAGE = 0.4
PREFIX_RUN_TOKENS = 8
PREFIXED_MIN_TOKENS = 80
REST_MAX_COVERAGE = 0.5
# A navigation string must be at least this share letters (spaces aside).
NAVIGATION_STRING_LETTER_SHARE = 0.75
# Bytes read to decide whether a source is HTML.
HTML_SNIFF_BYTES = 4096

_NAVIGATION_XPATH = (
    "//a|//option|//button|//nav|//header|//footer"
    "|//*[@role='navigation']|//*[@role='banner']|//*[@role='contentinfo']"
)
_INVISIBLE_XPATH = "//script|//style|//noscript|//template"
_SKIP_LINK = re.compile(
    r"\bskip\s+(?:to\s+(?:the\s+)?(?:main\s+)?content|navigation|to\s+main)\b"
    r"|\benable\s+javascript\b",
    re.IGNORECASE,
)
_HTML_MARKERS = (b"<html", b"<!doctype html", b"<body")


@dataclass(frozen=True, order=True)
class ContentFinding:
    """One row or source file a content check flags.

    ``path`` is the row's ``citation_path``, or for ``version_picker_source``
    the source's ``source_path`` relative to the corpus root.
    """

    code: str
    path: str
    detail: str = field(default="", compare=False)

    def key(self) -> tuple[str, str]:
        return (self.code, self.path)


def _tokens(text: str) -> list[str]:
    return text.split()


def _has_letters(token: str) -> bool:
    return any(char.isalpha() for char in token)


def is_navigation_string(text: str) -> bool:
    """Whether a link or nav element's text can count as page navigation.

    Mostly-letter strings only: a link whose text is a citation ("17041",
    "1990 c 604 art 2 s 21") is part of the law's own text.
    """
    compact = "".join(text.split())
    if len(compact) < 2:
        return False
    letters = sum(1 for char in compact if char.isalpha())
    return letters >= 2 and letters / len(compact) >= NAVIGATION_STRING_LETTER_SHARE


def looks_like_html(head: bytes) -> bool:
    lowered = head[:HTML_SNIFF_BYTES].lower()
    return any(marker in lowered for marker in _HTML_MARKERS)


@dataclass(frozen=True)
class Coverage:
    """How much of a text its page's navigation strings cover."""

    share: float
    residual_words: int
    tokens: int


class PageNavigation:
    """The navigation strings of one HTML page, matched as whole word runs."""

    def __init__(self, strings: Iterable[str]):
        sequences: dict[str, list[tuple[str, ...]]] = {}
        for string in set(strings):
            if not is_navigation_string(string):
                continue
            words = tuple(_tokens(string))
            if words:
                sequences.setdefault(words[0], []).append(words)
        for candidates in sequences.values():
            candidates.sort(key=len, reverse=True)
        self._by_first = sequences

    def __bool__(self) -> bool:
        return bool(self._by_first)

    def cover(self, tokens: list[str]) -> list[bool]:
        """Mark each token that lies in a longest-first match of a navigation string."""
        covered = [False] * len(tokens)
        index = 0
        while index < len(tokens):
            matched = 0
            for sequence in self._by_first.get(tokens[index], ()):
                end = index + len(sequence)
                if end <= len(tokens) and tuple(tokens[index:end]) == sequence:
                    matched = len(sequence)
                    break
            if matched:
                for position in range(index, index + matched):
                    covered[position] = True
                index += matched
            else:
                index += 1
        return covered

    def coverage(self, tokens: list[str]) -> Coverage:
        return _coverage(tokens, self.cover(tokens))


def _coverage(tokens: list[str], covered: list[bool]) -> Coverage:
    total = sum(len(token) for token in tokens)
    if not total:
        return Coverage(0.0, 0, 0)
    hit = sum(len(token) for token, flag in zip(tokens, covered, strict=True) if flag)
    residual = sum(
        1 for token, flag in zip(tokens, covered, strict=True) if not flag and _has_letters(token)
    )
    return Coverage(hit / total, residual, len(tokens))


def _parse_html(raw: bytes) -> etree._Element | None:
    try:
        return lxml.html.document_fromstring(raw)
    except (etree.ParserError, ValueError):
        return None


def page_navigation(raw: bytes) -> PageNavigation:
    """Collect the navigation strings of an HTML page (empty for any other bytes)."""
    if not looks_like_html(raw):
        return PageNavigation(())
    document = _parse_html(raw)
    if document is None:
        return PageNavigation(())
    for element in document.xpath(_INVISIBLE_XPATH):
        element.drop_tree()
    strings = []
    for element in document.xpath(_NAVIGATION_XPATH):
        text = " ".join(_tokens(element.text_content()))
        if text:
            strings.append(text)
    return PageNavigation(strings)


def is_version_picker(raw: bytes) -> bool:
    """Whether a page is a LegInfo version picker with no section on it."""
    if b"selectFromMultiples" not in raw or not looks_like_html(raw):
        return False
    document = _parse_html(raw)
    if document is None:
        return False
    if document.xpath("//*[@id='single_law_section']"):
        return False
    return bool(document.xpath("//form[@id='selectFromMultiples']"))


@dataclass(frozen=True)
class RowVerdict:
    """What the row checks conclude about one body."""

    navigation: bool
    prefixed: bool
    substantive: bool


def _opening_run(tokens: list[str], covered: list[bool]) -> int:
    """Navigation words a body opens with, passing over tokens with no letters."""
    run = 0
    for token, flag in zip(tokens, covered, strict=True):
        if not flag and _has_letters(token):
            break
        run += flag
    return run


def classify_body(
    body: str | None,
    navigation: PageNavigation | None,
    *,
    heading: str | None = None,
) -> RowVerdict:
    """Apply the navigation, prefix and substance rules to one body."""
    tokens = _tokens(body or "")[:MAX_BODY_TOKENS]
    words = sum(1 for token in tokens if _has_letters(token))
    if not tokens:
        return RowVerdict(navigation=False, prefixed=False, substantive=False)
    covered = navigation.cover(tokens) if navigation else [False] * len(tokens)
    whole = _coverage(tokens, covered)
    repeats_heading = heading is not None and tokens == _tokens(heading)
    is_navigation = (
        not repeats_heading
        and whole.share >= NAVIGATION_COVERAGE
        and whole.residual_words <= NAVIGATION_RESIDUAL_WORDS
    )
    prefixed = False
    if not is_navigation and len(tokens) >= PREFIXED_MIN_TOKENS:
        head = tokens[:PREFIX_TOKENS]
        head_covered = covered[:PREFIX_TOKENS]
        rest_coverage = _coverage(tokens[PREFIX_TOKENS:], covered[PREFIX_TOKENS:])
        chrome_opening = bool(_SKIP_LINK.search(" ".join(head))) or (
            _coverage(head, head_covered).share >= PREFIX_COVERAGE
            and _opening_run(head, head_covered) >= PREFIX_RUN_TOKENS
        )
        prefixed = chrome_opening and rest_coverage.share < REST_MAX_COVERAGE
    substantive = not is_navigation and words > 0
    return RowVerdict(navigation=is_navigation, prefixed=prefixed, substantive=substantive)


class ScopeContentScanner:
    """Stream one scope's provisions and report its content findings.

    ``add`` reads one record at a time, so a scope is checked in the same pass
    that validates it, holding only each row's path, source and verdict. Each
    source file is read once, however many rows cite it.
    """

    def __init__(self, corpus_root: str | Path):
        self.root = Path(corpus_root)
        self._pages: dict[str, PageNavigation | None] = {}
        self._pickers: set[str] = set()
        self._findings: list[ContentFinding] = []
        self._empty_roots: list[str] = []
        # (citation_path, source_path) of every row whose body is text.
        self._text_rows: list[tuple[str, str | None]] = []

    def _page(self, source_path: str | None) -> PageNavigation | None:
        if not source_path:
            return None
        if source_path in self._pages:
            return self._pages[source_path]
        page: PageNavigation | None = None
        path = self.root / source_path
        try:
            if path.is_file():
                with path.open("rb") as handle:
                    head = handle.read(HTML_SNIFF_BYTES)
                if looks_like_html(head):
                    raw = path.read_bytes()
                    page = page_navigation(raw)
                    if is_version_picker(raw):
                        self._pickers.add(source_path)
        except OSError:
            page = None
        self._pages[source_path] = page
        return page

    def add(self, record: ProvisionRecord) -> None:
        page = self._page(record.source_path)
        verdict = classify_body(record.body, page, heading=record.heading)
        if verdict.navigation:
            self._findings.append(
                ContentFinding(NAVIGATION_BODY, record.citation_path, "body is page navigation")
            )
        elif verdict.prefixed:
            self._findings.append(
                ContentFinding(
                    NAVIGATION_PREFIXED_BODY,
                    record.citation_path,
                    "body opens with page navigation before its text",
                )
            )
        if verdict.substantive:
            self._text_rows.append((record.citation_path, record.source_path))
        if record.kind == "document" and not (record.body and record.body.strip()):
            self._empty_roots.append(record.citation_path)

    def _text_row_paths(self) -> list[str]:
        """Sorted paths of rows that carry text. A version picker's rows never do."""
        return sorted(path for path, source in self._text_rows if source not in self._pickers)

    def _hollow_roots(self, text_rows: list[str]) -> list[str]:
        hollow = []
        for root in self._empty_roots:
            prefix = root + "/"
            index = bisect.bisect_left(text_rows, prefix)
            if index < len(text_rows) and text_rows[index].startswith(prefix):
                continue
            hollow.append(root)
        return hollow

    def text_paths(self) -> frozenset[str]:
        """Citation paths whose rows carry text: text bodies, and roots with text below them."""
        text_rows = self._text_row_paths()
        hollow = set(self._hollow_roots(text_rows))
        return frozenset(text_rows) | frozenset(
            root for root in self._empty_roots if root not in hollow
        )

    def findings(self) -> tuple[ContentFinding, ...]:
        found = list(self._findings)
        for root in self._hollow_roots(self._text_row_paths()):
            found.append(
                ContentFinding(
                    HOLLOW_DOCUMENT_ROOT,
                    root,
                    "document root has no body and no descendant carries text",
                )
            )
        for source_path in self._pickers:
            found.append(
                ContentFinding(
                    VERSION_PICKER_SOURCE,
                    source_path,
                    "source is a LegInfo version picker, not a section",
                )
            )
        return tuple(sorted(set(found)))


def scan_provisions(
    corpus_root: str | Path, records: Iterable[ProvisionRecord]
) -> tuple[ContentFinding, ...]:
    """Content findings for one scope's records (see ``ScopeContentScanner``)."""
    scanner = ScopeContentScanner(corpus_root)
    for record in records:
        scanner.add(record)
    return scanner.findings()


def findings_by_code(findings: Iterable[ContentFinding]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return dict(sorted(counts.items()))
