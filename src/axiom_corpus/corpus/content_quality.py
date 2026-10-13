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
    navigation text is the text of every link (``a`` with an ``href``),
    ``option`` and ``button``, of ``nav``, of a ``header`` or ``footer`` that
    is not inside an ``article``, ``main`` or ``section`` (where it holds a
    section's own heading), and of elements with a navigation, banner or
    contentinfo role. Only strings that are mostly letters count, so citation
    links ("1990 c 604 art 2 s 21", "17041") are not navigation. A body is navigation when those strings cover at least
    ``NAVIGATION_COVERAGE`` of its characters, matched as whole word runs, and
    at most ``NAVIGATION_RESIDUAL_WORDS`` words are left over. A body that only
    repeats the row's own heading, alone or after its citation label (compared
    without case or punctuation), is a heading row, not navigation, even when
    the page's table of contents links that heading.
``navigation_prefixed_body``
    The row holds text, but it opens with page chrome: a skip link or a
    JavaScript notice within its first ``PREFIX_TOKENS`` words, or an opening
    run of at least ``PREFIX_RUN_TOKENS`` navigation words in a first
    ``PREFIX_TOKENS`` words that are at least ``PREFIX_COVERAGE`` navigation.
    The rest of the body must not itself be mostly navigation.
``hollow_document_root``
    A ``document`` row with no body whose descendants in the scope (rows whose
    citation path extends it) carry no text: each is empty, has neither a word
    with a letter in it nor a table of figures, is a ``navigation_body``, or
    comes from a version picker. A body with no word with a letter is a table
    of figures when at least ``FIGURE_TEXT_MIN_TOKENS`` of its tokens are
    figures (numbers, dates, amounts, rates) and they are at least
    ``FIGURE_TEXT_MIN_SHARE`` of its tokens: a benefit table of dates and
    amounts is text, while a page number, a date stamp on a scanned page or a
    font's garbled glyph codes are not. A bodyless document with no rows below
    it at all is hollow too: it carries a heading and nothing else. A bodyless
    root with text below it is the shared document extractor's normal shape
    (the wave4 chapter scopes keep each section's text in one child block), so
    emptiness alone is not a finding, and neither is a short text: "Reserved."
    is a section's text. A root that review found correctly empty (a table of
    contents, an index of separate documents, a reserved or repealed item) is
    listed in ``manifests/reviewed-empty-nodes.yaml`` and is not a finding
    (``ScopeContentScanner``'s ``reviewed_empty``).
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
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import lxml.html
from lxml import etree

from axiom_corpus.corpus.models import ProvisionRecord

CONTENT_CHECK_VERSION = "content-check-v2"

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
# A body with no word with a letter is text when at least this many of its
# tokens are figures and they are at least this share of its tokens. Date
# stamps and page numbers on scanned pages hold one to four figures; garbled
# glyph codes hold under 15% figures (docs/release-gate-policy.md).
FIGURE_TEXT_MIN_TOKENS = 5
FIGURE_TEXT_MIN_SHARE = 0.5
# Bytes read to decide whether a source is HTML.
HTML_SNIFF_BYTES = 4096

_OUTSIDE_CONTENT = "not(ancestor::article or ancestor::main or ancestor::section)"
_NAVIGATION_XPATH = (
    "//a[@href]|//option|//button|//nav"
    f"|//header[{_OUTSIDE_CONTENT}]|//footer[{_OUTSIDE_CONTENT}]"
    "|//*[@role='navigation']|//*[@role='banner']|//*[@role='contentinfo']"
)
_INVISIBLE_XPATH = "//script|//style|//noscript|//template"
_SKIP_LINK = re.compile(
    r"\bskip\s+(?:to\s+(?:the\s+)?(?:main\s+)?content|navigation|to\s+main)\b"
    r"|\benable\s+javascript\b",
    re.IGNORECASE,
)
_HTML_MARKERS = (b"<html", b"<!doctype html", b"<body")
# A figure: a number, date, amount, rate or range, with an optional sign,
# currency symbol, percent sign, enclosing parentheses or trailing punctuation
# ("16", "$1,014.00", ".9666", "10/19--", "(450,000)", "2.5%").
_FIGURE = re.compile(r"[(\[]?[-+\u2212]?[$\u00a3\u20ac\u00a5]?\.?\d[\d.,/:\u2013-]*%?[)\]]?[.,;:]?")
# A list marker, not a figure: up to three digits in brackets, or before a
# period or a closing bracket ("(1)", "[12]", "3.", "4)").
_ENUMERATOR = re.compile(r"[(\[]\d{1,3}[)\]]|\d{1,3}[.)\]]")
# Rows arrive grouped by source, so a scope needs only its recent pages.
PAGE_CACHE_SIZE = 256


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


def is_figure(token: str) -> bool:
    """Whether a token is a number, date, amount, rate or range.

    A list marker ("(1)", "2.") is not one: a body that kept only its
    paragraph numbers has lost its text.
    """
    return _FIGURE.fullmatch(token) is not None and _ENUMERATOR.fullmatch(token) is None


def is_figure_table(tokens: list[str]) -> bool:
    """Whether tokens with no letter in them still read as text: a table of figures.

    At least ``FIGURE_TEXT_MIN_TOKENS`` figures, making up at least
    ``FIGURE_TEXT_MIN_SHARE`` of the tokens. A date stamp ("9/4/13"), a page
    number or a pair of dates is too few; a scanned page's garbled glyph codes,
    which hold a stray digit here and there, are too thin; list markers are not
    figures at all.
    """
    figures = sum(1 for token in tokens if is_figure(token))
    return figures >= FIGURE_TEXT_MIN_TOKENS and figures >= FIGURE_TEXT_MIN_SHARE * len(tokens)


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
    """Whether a file's first bytes are an HTML page (XHTML included, other XML not)."""
    lowered = head[:HTML_SNIFF_BYTES].lower()
    if (
        lowered.removeprefix(b"\xef\xbb\xbf").lstrip().startswith(b"<?xml")
        and b"<html" not in lowered
    ):
        return False  # an XML format with a <body> element, such as Akoma Ntoso
    return any(marker in lowered for marker in _HTML_MARKERS)


def _normalized_words(text: str | None) -> list[str]:
    """Words of a text without case or punctuation, for comparing a body to its heading."""
    return re.sub(r"[^\w]+", " ", (text or "").casefold()).split()


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
                if (
                    end <= len(tokens)
                    and tokens[end - 1] == sequence[-1]
                    and tuple(tokens[index:end]) == sequence
                ):
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
    except (etree.LxmlError, ValueError):
        # LxmlError is the base of every lxml error (ParserError, XMLSyntaxError, ...).
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
    label: str | None = None,
) -> RowVerdict:
    """Apply the navigation, prefix and substance rules to one body.

    A body is text (``substantive``) when it is not navigation and has a word
    with a letter in it, or, having none, is a table of figures
    (``is_figure_table``). That rule decides substance only: the navigation
    and prefix verdicts are what they were without it. A figure is a token like
    any other in the coverage share, and the residual and the opening run count
    words with letters only.
    """
    tokens = _tokens(body or "")[:MAX_BODY_TOKENS]
    words = sum(1 for token in tokens if _has_letters(token))
    if not tokens:
        return RowVerdict(navigation=False, prefixed=False, substantive=False)
    covered = navigation.cover(tokens) if navigation else [False] * len(tokens)
    whole = _coverage(tokens, covered)
    words_of_body = _normalized_words(body)
    heading_words = _normalized_words(heading)
    repeats_heading = bool(heading_words) and words_of_body in (
        heading_words,
        _normalized_words(label) + heading_words,
    )
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
    substantive = not is_navigation and (words > 0 or is_figure_table(tokens))
    return RowVerdict(navigation=is_navigation, prefixed=prefixed, substantive=substantive)


def _text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


class ScopeContentScanner:
    """Stream one scope's provisions and report its content findings.

    ``add`` reads one record at a time, so a scope is checked in the same pass
    that validates it, holding only each row's path, source and verdict. Rows
    arrive grouped by source, so each source file is read once for its run of
    rows; the last ``PAGE_CACHE_SIZE`` pages are kept.

    A row whose source file is absent is read as having no page, so it can be
    text but never navigation; ``validate_release`` reports the missing file
    itself, and callers outside validation fetch a scope's locked sources
    before scanning it.

    ``add`` never raises on a malformed row: ``validate_release`` feeds it each
    record while it loads them, and must report what it reported without the
    scan. A ``source_path``, ``heading`` or ``citation_label`` that is not a
    string is read as absent; validation reports the field itself.

    ``reviewed_empty`` names the citation paths of this scope's document rows
    that review found correctly empty (``manifests/reviewed-empty-nodes.yaml``).
    Such a row is not a ``hollow_document_root`` finding when it is hollow;
    ``reviewed_empty_roots`` lists the ones the exemption applied to. Nothing
    else depends on the list: a reviewed row is still hollow for
    ``text_paths``, and its descendants are checked as any other rows.
    """

    def __init__(self, corpus_root: str | Path, *, reviewed_empty: Iterable[str] = ()):
        self.root = Path(corpus_root)
        self._reviewed_empty = frozenset(reviewed_empty)
        self._pages: OrderedDict[str, PageNavigation | None] = OrderedDict()
        self._pickers: set[str] = set()
        self._findings: list[ContentFinding] = []
        self._empty_roots: list[str] = []
        # (citation_path, source_path) of every row whose body is text.
        self._text_rows: list[tuple[str, str | None]] = []

    def _page(self, source_path: str | None) -> PageNavigation | None:
        if not source_path:
            return None
        if source_path in self._pages:
            self._pages.move_to_end(source_path)
            return self._pages[source_path]
        relative = Path(source_path)
        if relative.is_absolute() or ".." in relative.parts:
            return None  # never read outside the corpus; validation rejects the path
        page: PageNavigation | None = None
        path = self.root / relative
        try:
            if path.is_file():
                with path.open("rb") as handle:
                    head = handle.read(HTML_SNIFF_BYTES)
                if looks_like_html(head):
                    raw = path.read_bytes()
                    page = page_navigation(raw)
                    if is_version_picker(raw):
                        self._pickers.add(source_path)
        except (OSError, ValueError, etree.LxmlError):
            # ValueError: a path the platform cannot name, e.g. one with a NUL;
            # LxmlError: a page lxml cannot read. Either way the row has no page.
            page = None
        self._pages[source_path] = page
        if len(self._pages) > PAGE_CACHE_SIZE:
            self._pages.popitem(last=False)
        return page

    def add(self, record: ProvisionRecord) -> None:
        source = _text_or_none(record.source_path)
        page = self._page(source)
        verdict = classify_body(
            _text_or_none(record.body),
            page,
            heading=_text_or_none(record.heading),
            label=_text_or_none(record.citation_label),
        )
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
            self._text_rows.append((record.citation_path, source))
        body = _text_or_none(record.body)
        if record.kind == "document" and not (body and body.strip()):
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

    def reviewed_empty_roots(self) -> tuple[str, ...]:
        """Hollow roots that ``reviewed_empty`` exempts from the findings, sorted."""
        return tuple(sorted(set(self._hollow_roots(self._text_row_paths())) & self._reviewed_empty))

    def findings(self) -> tuple[ContentFinding, ...]:
        found = list(self._findings)
        for root in self._hollow_roots(self._text_row_paths()):
            if root in self._reviewed_empty:
                continue
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
    corpus_root: str | Path,
    records: Iterable[ProvisionRecord],
    *,
    reviewed_empty: Iterable[str] = (),
) -> tuple[ContentFinding, ...]:
    """Content findings for one scope's records (see ``ScopeContentScanner``)."""
    scanner = ScopeContentScanner(corpus_root, reviewed_empty=reviewed_empty)
    for record in records:
        scanner.add(record)
    return scanner.findings()


def findings_by_code(findings: Iterable[ContentFinding]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return dict(sorted(counts.items()))
