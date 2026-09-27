"""Idaho Statutes source-first corpus adapter."""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.citation_segment import variant_segment
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

IDAHO_STATUTES_BASE_URL = "https://legislature.idaho.gov/statutesrules/idstat/"
IDAHO_TITLE_INDEX_SOURCE_FORMAT = "idaho-statutes-title-index-html"
IDAHO_TITLE_SOURCE_FORMAT = "idaho-statutes-title-html"
IDAHO_CHAPTER_SOURCE_FORMAT = "idaho-statutes-chapter-html"
IDAHO_SECTION_SOURCE_FORMAT = "idaho-statutes-section-html"
IDAHO_USER_AGENT = "axiom-corpus/0.1 (contact@axiom-foundation.org)"

_TITLE_HREF_RE = re.compile(r"/statutesrules/idstat/Title(?P<title>\d+)/?$", re.I)
_TITLE_TEXT_RE = re.compile(r"^TITLE\s+(?P<title>\d+)\b\s*(?P<heading>.*)$", re.I)
_CHAPTER_TEXT_RE = re.compile(r"^CHAPTER\s+(?P<chapter>\d+[A-Z]?)\b\s*(?P<heading>.*)$", re.I)
_CHAPTER_HREF_RE = re.compile(
    r"/statutesrules/idstat/Title(?P<title>\d+)/T(?P=title)CH(?P<chapter>\d+[A-Z]?)/?$",
    re.I,
)
_SECTION_HREF_RE = re.compile(
    r"/statutesrules/idstat/Title(?P<title>\d+)/T(?P=title)CH(?P<chapter>\d+[A-Z]?)/SECT(?P<section>\d+-\d+[A-Z]?)/?$",
    re.I,
)
_SECTION_NUMBER_RE = re.compile(r"\b(?P<section>\d{1,2}-\d{2,5}[A-Z]?)\b", re.I)
_RENDITION_EFFECTIVE_RE = re.compile(
    r"\[(?P<note>effective(?P<until>\s+until)?\s+"
    r"(?P<date>[A-Z][a-z]+\s+\d{1,2},\s+\d{4}))\]",
    re.I,
)


@dataclass(frozen=True)
class IdahoTitle:
    """One Idaho Code title from the official statute title index."""

    number: str
    heading: str
    source_url: str
    source_path: str
    source_format: str
    sha256: str
    ordinal: int

    @property
    def source_id(self) -> str:
        return f"title-{self.number}"

    @property
    def citation_path(self) -> str:
        return f"us-id/statute/{self.source_id}"

    @property
    def legal_identifier(self) -> str:
        return f"Idaho Code title {self.number}"


@dataclass(frozen=True)
class IdahoChapter:
    """One chapter row from an official Idaho Code title page."""

    title_number: str
    title_heading: str
    chapter: str
    heading: str
    source_url: str
    source_path: str
    source_format: str
    sha256: str
    ordinal: int
    pdf_url: str | None = None
    active: bool = True
    status: str | None = None

    @property
    def source_id(self) -> str:
        return f"title-{self.title_number}-chapter-{self.chapter}"

    @property
    def citation_path(self) -> str:
        return f"us-id/statute/title-{self.title_number}/chapter-{self.chapter}"

    @property
    def parent_citation_path(self) -> str:
        return f"us-id/statute/title-{self.title_number}"

    @property
    def legal_identifier(self) -> str:
        return f"Idaho Code title {self.title_number}, ch. {self.chapter}"


@dataclass(frozen=True)
class IdahoSectionListing:
    """One section listing row from an official Idaho Code chapter page."""

    title_number: str
    chapter: str
    section: str
    heading: str
    source_url: str
    ordinal: int

    @property
    def source_id(self) -> str:
        return self.section

    @property
    def citation_path(self) -> str:
        return f"us-id/statute/{self.section}"

    @property
    def legal_identifier(self) -> str:
        return f"Idaho Code § {self.section}"


@dataclass(frozen=True)
class IdahoSection:
    """One Idaho Code section parsed from official section HTML.

    A page can print several dated renditions of one section ("[effective until
    January 1, 2027]" / "[effective January 1, 2027]"). The rendition in force
    on the expression date has no ``variant`` and keeps the plain citation
    path; every other rendition is a same-number variant at
    ``<section>--<variant>`` (the NM/VT/DE ``citation_segment.variant_segment``
    convention).
    """

    listing: IdahoSectionListing
    heading: str
    body: str | None
    source_history: tuple[str, ...]
    source_notes: tuple[str, ...]
    references_to: tuple[str, ...]
    source_url: str
    source_path: str
    source_format: str
    sha256: str
    status: str | None = None
    variant: str | None = None
    effective_note: str | None = None

    @property
    def citation_path(self) -> str:
        return f"us-id/statute/{self.source_id}"

    @property
    def canonical_citation_path(self) -> str:
        return self.listing.citation_path

    @property
    def source_id(self) -> str:
        return variant_segment(self.listing.source_id, self.variant)

    @property
    def legal_identifier(self) -> str:
        return self.listing.legal_identifier

    @property
    def parent_citation_path(self) -> str:
        return f"us-id/statute/title-{self.listing.title_number}/chapter-{self.listing.chapter}"


@dataclass(frozen=True)
class _IdahoSource:
    relative_path: str
    source_url: str
    source_format: str
    data: bytes


@dataclass(frozen=True)
class _RecordedSource:
    source_url: str
    source_path: str
    source_format: str
    sha256: str


@dataclass(frozen=True)
class _IdahoRendition:
    """One dated rendition of a section on a page that prints several."""

    position: int
    start: int
    end: int
    effective_date: date | None
    until: bool
    note: str | None


@dataclass(frozen=True)
class _IdahoSectionFetchResult:
    listing: IdahoSectionListing
    source: _IdahoSource | None = None
    sections: tuple[IdahoSection, ...] = ()
    error: BaseException | None = None


class _IdahoFetcher:
    def __init__(
        self,
        *,
        source_dir: Path | None,
        download_dir: Path | None,
        base_url: str,
        request_delay_seconds: float,
        timeout_seconds: float,
        request_attempts: int,
    ) -> None:
        self.source_dir = source_dir
        self.download_dir = download_dir
        self.base_url = base_url.rstrip("/") + "/"
        self.request_delay_seconds = max(0.0, request_delay_seconds)
        self.timeout_seconds = timeout_seconds
        self.request_attempts = max(1, request_attempts)
        self._last_request_at = 0.0
        self._request_lock = Lock()

    def fetch_title_index(self) -> _IdahoSource:
        relative_path = f"{IDAHO_TITLE_INDEX_SOURCE_FORMAT}/index.html"
        data = self._fetch(relative_path, self.base_url)
        return _IdahoSource(
            relative_path=relative_path,
            source_url=self.base_url,
            source_format=IDAHO_TITLE_INDEX_SOURCE_FORMAT,
            data=data,
        )

    def fetch_title(self, title: IdahoTitle) -> _IdahoSource:
        relative_path = f"{IDAHO_TITLE_SOURCE_FORMAT}/title-{title.number}.html"
        source_url = urljoin(self.base_url, f"Title{title.number}/")
        data = self._fetch(relative_path, source_url)
        return _IdahoSource(
            relative_path=relative_path,
            source_url=source_url,
            source_format=IDAHO_TITLE_SOURCE_FORMAT,
            data=data,
        )

    def fetch_chapter(self, chapter: IdahoChapter) -> _IdahoSource:
        relative_path = (
            f"{IDAHO_CHAPTER_SOURCE_FORMAT}/title-{chapter.title_number}/"
            f"chapter-{chapter.chapter}.html"
        )
        data = self._fetch(relative_path, chapter.source_url)
        return _IdahoSource(
            relative_path=relative_path,
            source_url=chapter.source_url,
            source_format=IDAHO_CHAPTER_SOURCE_FORMAT,
            data=data,
        )

    def fetch_section(self, listing: IdahoSectionListing) -> _IdahoSource:
        relative_path = (
            f"{IDAHO_SECTION_SOURCE_FORMAT}/title-{listing.title_number}/"
            f"chapter-{listing.chapter}/{listing.section}.html"
        )
        data = self._fetch(relative_path, listing.source_url)
        return _IdahoSource(
            relative_path=relative_path,
            source_url=listing.source_url,
            source_format=IDAHO_SECTION_SOURCE_FORMAT,
            data=data,
        )

    def _fetch(self, relative_path: str, source_url: str) -> bytes:
        if self.source_dir is not None:
            return (self.source_dir / relative_path).read_bytes()
        if self.download_dir is not None:
            cached_path = self.download_dir / relative_path
            if cached_path.exists():
                return cached_path.read_bytes()
        data = _download_idaho_source(
            source_url,
            fetcher=self,
            request_delay_seconds=self.request_delay_seconds,
            timeout_seconds=self.timeout_seconds,
            request_attempts=self.request_attempts,
        )
        if self.download_dir is not None:
            cached_path = self.download_dir / relative_path
            cached_path.parent.mkdir(parents=True, exist_ok=True)
            _write_cache_bytes(cached_path, data)
        return data

    def wait_for_request_slot(self) -> None:  # pragma: no cover
        if self.request_delay_seconds <= 0:
            return
        with self._request_lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.request_delay_seconds:
                time.sleep(self.request_delay_seconds - elapsed)
            self._last_request_at = time.monotonic()


def extract_idaho_statutes(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | int | None = None,
    only_chapter: str | int | None = None,
    limit: int | None = None,
    download_dir: str | Path | None = None,
    base_url: str = IDAHO_STATUTES_BASE_URL,
    request_delay_seconds: float = 0.05,
    timeout_seconds: float = 60.0,
    request_attempts: int = 3,
    workers: int = 1,
) -> StateStatuteExtractReport:
    """Snapshot official Idaho Statutes HTML and extract provisions."""
    jurisdiction = "us-id"
    title_filter = _title_filter(only_title)
    chapter_filter = _chapter_filter(only_chapter)
    run_id = _idaho_run_id(
        version,
        title_filter=title_filter,
        chapter_filter=chapter_filter,
        limit=limit,
    )
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    fetcher = _IdahoFetcher(
        source_dir=Path(source_dir) if source_dir is not None else None,
        download_dir=Path(download_dir) if download_dir is not None else None,
        base_url=base_url,
        request_delay_seconds=request_delay_seconds,
        timeout_seconds=timeout_seconds,
        request_attempts=request_attempts,
    )

    source_paths: list[Path] = []
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    title_count = 0
    container_count = 0
    section_count = 0
    remaining_sections = limit

    title_index_source = fetcher.fetch_title_index()
    title_index_recorded = _record_source(
        store,
        jurisdiction=jurisdiction,
        run_id=run_id,
        source=title_index_source,
    )
    source_paths.append(
        store.source_path(
            jurisdiction,
            DocumentClass.STATUTE,
            run_id,
            title_index_source.relative_path,
        )
    )
    titles = parse_idaho_title_index(
        title_index_source.data,
        source=title_index_recorded,
        base_url=base_url,
    )
    if title_filter is not None:
        titles = tuple(title for title in titles if title.number == title_filter)
    if not titles:
        raise ValueError(f"no Idaho titles selected for filter: {only_title!r}")

    for title in titles:
        if remaining_sections is not None and remaining_sections <= 0:
            break
        if _append_unique(
            seen,
            items,
            records,
            _title_inventory_item(title),
            _title_record(
                title,
                version=run_id,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
            ),
        ):
            title_count += 1
            container_count += 1

        title_source = fetcher.fetch_title(title)
        title_recorded = _record_source(
            store,
            jurisdiction=jurisdiction,
            run_id=run_id,
            source=title_source,
        )
        source_paths.append(
            store.source_path(
                jurisdiction,
                DocumentClass.STATUTE,
                run_id,
                title_source.relative_path,
            )
        )
        chapters = parse_idaho_title_page(
            title_source.data,
            title=title,
            source=title_recorded,
            base_url=base_url,
        )
        if chapter_filter is not None:
            chapters = tuple(chapter for chapter in chapters if chapter.chapter == chapter_filter)

        for chapter in chapters:
            if remaining_sections is not None and remaining_sections <= 0:
                break
            if _append_unique(
                seen,
                items,
                records,
                _chapter_inventory_item(chapter),
                _chapter_record(
                    chapter,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                ),
            ):
                container_count += 1
            if not chapter.active:
                continue

            chapter_source = fetcher.fetch_chapter(chapter)
            chapter_recorded = _record_source(
                store,
                jurisdiction=jurisdiction,
                run_id=run_id,
                source=chapter_source,
            )
            source_paths.append(
                store.source_path(
                    jurisdiction,
                    DocumentClass.STATUTE,
                    run_id,
                    chapter_source.relative_path,
                )
            )
            listings = parse_idaho_chapter_page(
                chapter_source.data,
                chapter=chapter,
                base_url=base_url,
            )
            selected_listings: list[IdahoSectionListing] = []
            for listing in listings:
                if remaining_sections is not None and len(selected_listings) >= remaining_sections:
                    break
                if listing.citation_path in seen:
                    errors.append(f"duplicate citation path: {listing.citation_path}")
                    continue
                selected_listings.append(listing)
            for result in _fetch_idaho_section_results(
                fetcher,
                selected_listings,
                source=chapter_recorded,
                expression_date=expression_date_text,
                workers=workers,
            ):
                if result.error is not None:
                    errors.append(f"section {result.listing.section}: {result.error}")
                    continue
                assert result.source is not None
                assert result.sections
                section_recorded = _record_source(
                    store,
                    jurisdiction=jurisdiction,
                    run_id=run_id,
                    source=result.source,
                )
                source_paths.append(
                    store.source_path(
                        jurisdiction,
                        DocumentClass.STATUTE,
                        run_id,
                        result.source.relative_path,
                    )
                )
                # The rendition in force first, then its same-number variants.
                for parsed in result.sections:
                    section = _replace_section_source(parsed, section_recorded)
                    if _append_unique(
                        seen,
                        items,
                        records,
                        _section_inventory_item(section),
                        _section_record(
                            section,
                            version=run_id,
                            source_as_of=source_as_of_text,
                            expression_date=expression_date_text,
                        ),
                    ):
                        section_count += 1
                        if section.variant is None and remaining_sections is not None:
                            remaining_sections -= 1

    if not records:
        raise ValueError("no Idaho Statutes provisions extracted")

    inventory_path = store.inventory_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction=jurisdiction,
        document_class=DocumentClass.STATUTE.value,
        version=run_id,
    )
    coverage_path = store.coverage_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_json(coverage_path, coverage.to_mapping())
    return StateStatuteExtractReport(
        jurisdiction=jurisdiction,
        title_count=title_count,
        container_count=container_count,
        section_count=section_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        errors=tuple(errors),
    )


def parse_idaho_title_index(
    html: str | bytes,
    *,
    source: _RecordedSource,
    base_url: str = IDAHO_STATUTES_BASE_URL,
) -> tuple[IdahoTitle, ...]:
    """Parse the official Idaho Statutes title index."""
    soup = BeautifulSoup(_decode(html), "lxml")
    titles: list[IdahoTitle] = []
    seen: set[str] = set()
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        link = cells[0].find("a", href=True)
        text = _clean_text(cells[0])
        href = str(link["href"]) if isinstance(link, Tag) else ""
        href_match = _TITLE_HREF_RE.search(href)
        text_match = _TITLE_TEXT_RE.match(text)
        if href_match is None and text_match is None:
            continue
        number = (href_match or text_match).group("title")  # type: ignore[union-attr]
        if number in seen:
            continue
        seen.add(number)
        titles.append(
            IdahoTitle(
                number=number,
                heading=_clean_heading(cells[2]) or f"Title {number}",
                source_url=urljoin(base_url, href) if href else source.source_url,
                source_path=source.source_path,
                source_format=source.source_format,
                sha256=source.sha256,
                ordinal=len(titles) + 1,
            )
        )
    return tuple(titles)


def parse_idaho_title_page(
    html: str | bytes,
    *,
    title: IdahoTitle,
    source: _RecordedSource,
    base_url: str = IDAHO_STATUTES_BASE_URL,
) -> tuple[IdahoChapter, ...]:
    """Parse one official Idaho Statutes title page."""
    soup = BeautifulSoup(_decode(html), "lxml")
    title_heading = _title_page_heading(soup, title)
    chapters: list[IdahoChapter] = []
    seen: set[str] = set()
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        chapter_cell = cells[0]
        text = _clean_text(chapter_cell)
        match = re.match(r"^CHAPTER\s+(?P<chapter>\d+[A-Z]?)$", text, re.I)
        if match is None:
            continue
        chapter = match.group("chapter").upper()
        if chapter in seen:
            continue
        seen.add(chapter)
        link = chapter_cell.find("a", href=True)
        href = str(link["href"]) if isinstance(link, Tag) else ""
        href_match = _CHAPTER_HREF_RE.search(href)
        pdf_url: str | None = None
        for row_link in row.find_all("a", href=True):
            row_href = str(row_link["href"])
            if row_href.lower().endswith(".pdf"):
                pdf_url = urljoin(base_url, row_href)
                break
        heading = _clean_heading(cells[2]) or f"Chapter {chapter}"
        status = _status_from_heading(heading)
        chapters.append(
            IdahoChapter(
                title_number=title.number,
                title_heading=title_heading,
                chapter=chapter,
                heading=heading,
                source_url=urljoin(base_url, href) if href_match is not None else source.source_url,
                source_path=source.source_path,
                source_format=source.source_format,
                sha256=source.sha256,
                ordinal=len(chapters) + 1,
                pdf_url=pdf_url,
                active=href_match is not None,
                status=status,
            )
        )
    return tuple(chapters)


def parse_idaho_chapter_page(
    html: str | bytes,
    *,
    chapter: IdahoChapter,
    base_url: str = IDAHO_STATUTES_BASE_URL,
) -> tuple[IdahoSectionListing, ...]:
    """Parse section listings from one official Idaho Statutes chapter page."""
    soup = BeautifulSoup(_decode(html), "lxml")
    listings: list[IdahoSectionListing] = []
    seen: set[str] = set()
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        link = cells[0].find("a", href=True)
        if not isinstance(link, Tag):
            continue
        href = str(link["href"])
        match = _SECTION_HREF_RE.search(href)
        if match is None:
            continue
        section = match.group("section").upper()
        if section in seen:
            continue
        seen.add(section)
        listings.append(
            IdahoSectionListing(
                title_number=chapter.title_number,
                chapter=chapter.chapter,
                section=section,
                heading=_clean_heading(cells[2]) or f"Section {section}",
                source_url=urljoin(base_url, href),
                ordinal=len(listings) + 1,
            )
        )
    return tuple(listings)


def parse_idaho_section_page(
    html: str | bytes,
    *,
    listing: IdahoSectionListing,
    source: _RecordedSource,
    expression_date: date | str | None = None,
) -> IdahoSection:
    """Parse one official Idaho Statutes section HTML page.

    When the page prints several renditions this is the one in force on
    ``expression_date``; :func:`parse_idaho_section_versions` returns them all.
    """
    return parse_idaho_section_versions(
        html,
        listing=listing,
        source=source,
        expression_date=expression_date,
    )[0]


def parse_idaho_section_versions(
    html: str | bytes,
    *,
    listing: IdahoSectionListing,
    source: _RecordedSource,
    expression_date: date | str | None = None,
) -> tuple[IdahoSection, ...]:
    """Parse every rendition one official Idaho Statutes section page prints.

    The first section is the rendition in force on ``expression_date``, at the
    plain citation path. Each other rendition follows in printed order as a
    same-number variant named by its bracketed marker:
    ``effective-YYYY-MM-DD`` for "[effective <date>]",
    ``effective-until-YYYY-MM-DD`` for "[effective until <date>]", and
    ``variant-<n>`` (its 1-based printed position) when it has none. The shared
    page prefix and the History and notes after the last rendition belong to
    every rendition. Two renditions with the same name fail closed.
    """
    soup = BeautifulSoup(_decode(html), "lxml")
    content_divs = _section_content_divs(soup)
    if not content_divs:
        raise ValueError("Idaho section page has no statute content divs")
    renditions, history_start = _section_renditions(content_divs, section=listing.section)
    if len(renditions) <= 1:
        return (_parse_section_divs(content_divs, listing=listing, source=source),)
    if expression_date is None:
        raise ValueError(
            f"Idaho section {listing.section} publishes {len(renditions)} renditions; "
            "expression_date is required"
        )

    as_of = _coerce_expression_date(expression_date)
    primary = _primary_rendition(renditions, section=listing.section, as_of=as_of)
    sections = [
        _parse_section_divs(
            _rendition_divs(content_divs, renditions, primary, history_start=history_start),
            listing=listing,
            source=source,
        )
    ]
    variants: set[str] = set()
    for rendition in renditions:
        if rendition is primary:
            continue
        variant = _rendition_variant(rendition)
        if variant in variants:
            raise ValueError(
                f"Idaho section {listing.section} prints two renditions named {variant!r}"
            )
        variants.add(variant)
        parsed = _parse_section_divs(
            _rendition_divs(content_divs, renditions, rendition, history_start=history_start),
            listing=listing,
            source=source,
        )
        sections.append(
            replace(
                parsed,
                variant=variant,
                effective_note=rendition.note,
                status=parsed.status or _rendition_status(rendition),
            )
        )
    return tuple(sections)


def _parse_section_divs(
    content_divs: tuple[Tag, ...],
    *,
    listing: IdahoSectionListing,
    source: _RecordedSource,
) -> IdahoSection:
    heading = _clean_heading(listing.heading) or f"Section {listing.section}"
    body_parts: list[str] = []
    history_parts: list[str] = []
    note_parts: list[str] = []
    in_history = False
    in_notes = False
    found_section = False

    for div in content_divs:
        text = _clean_text(div)
        if not text:
            continue
        if _is_centered_header(div):
            continue
        if _is_history_marker(text):
            in_history = True
            in_notes = False
            continue
        if _is_note_marker(text):
            in_notes = True
            in_history = False
            note = _strip_note_marker(text)
            if note:
                note_parts.append(note)
            continue

        if in_history:
            history_parts.append(text)
            continue
        if in_notes:
            note_parts.append(text)
            continue

        if not found_section:
            section_text, parsed_heading = _strip_section_heading(text, listing.section)
            if parsed_heading:
                heading = parsed_heading
            if section_text:
                body_parts.append(section_text)
            found_section = True
            continue

        body_parts.append(text)

    body = _join_paragraphs(body_parts)
    history = tuple(part for part in (_join_paragraphs(history_parts),) if part)
    notes = tuple(part for part in (_join_paragraphs(note_parts),) if part)
    references_to = _extract_section_references(
        content_divs,
        "\n".join(part for part in [body or "", *notes] if part),
        current=listing.section,
    )
    status = _section_status(heading, body, history + notes)
    return IdahoSection(
        listing=listing,
        heading=heading,
        body=body,
        source_history=history,
        source_notes=notes,
        references_to=references_to,
        source_url=source.source_url,
        source_path=source.source_path,
        source_format=source.source_format,
        sha256=source.sha256,
        status=status,
    )


def _fetch_idaho_section_results(
    fetcher: _IdahoFetcher,
    listings: list[IdahoSectionListing],
    *,
    source: _RecordedSource,
    expression_date: date | str | None,
    workers: int,
) -> list[_IdahoSectionFetchResult]:
    if not listings:
        return []
    if workers <= 1 or len(listings) == 1:
        return [
            _fetch_one_idaho_section(
                fetcher,
                listing,
                source=source,
                expression_date=expression_date,
            )
            for listing in listings
        ]
    results: dict[int, _IdahoSectionFetchResult] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                _fetch_one_idaho_section,
                fetcher,
                listing,
                source=source,
                expression_date=expression_date,
            ): index
            for index, listing in enumerate(listings)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [results[index] for index in range(len(listings))]


def _fetch_one_idaho_section(
    fetcher: _IdahoFetcher,
    listing: IdahoSectionListing,
    *,
    source: _RecordedSource,
    expression_date: date | str | None,
) -> _IdahoSectionFetchResult:
    try:
        section_source = fetcher.fetch_section(listing)
        transient_source = _RecordedSource(
            source_url=section_source.source_url,
            source_path=source.source_path,
            source_format=section_source.source_format,
            sha256=source.sha256,
        )
        sections = parse_idaho_section_versions(
            section_source.data,
            listing=listing,
            source=transient_source,
            expression_date=expression_date,
        )
        return _IdahoSectionFetchResult(
            listing=listing,
            source=section_source,
            sections=sections,
        )
    except (requests.RequestException, OSError, ValueError) as exc:
        return _IdahoSectionFetchResult(listing=listing, error=exc)


def _replace_section_source(section: IdahoSection, source: _RecordedSource) -> IdahoSection:
    return replace(
        section,
        source_url=source.source_url,
        source_path=source.source_path,
        source_format=source.source_format,
        sha256=source.sha256,
    )


def _title_inventory_item(title: IdahoTitle) -> SourceInventoryItem:
    return SourceInventoryItem(
        citation_path=title.citation_path,
        source_url=title.source_url,
        source_path=title.source_path,
        source_format=title.source_format,
        sha256=title.sha256,
        metadata={
            "kind": "title",
            "title": title.number,
            "heading": title.heading,
            "source_id": title.source_id,
        },
    )


def _chapter_inventory_item(chapter: IdahoChapter) -> SourceInventoryItem:
    metadata: dict[str, Any] = {
        "kind": "chapter",
        "title": chapter.title_number,
        "chapter": chapter.chapter,
        "heading": chapter.heading,
        "source_id": chapter.source_id,
        "parent_citation_path": chapter.parent_citation_path,
        "active": chapter.active,
    }
    if chapter.pdf_url:
        metadata["chapter_pdf_url"] = chapter.pdf_url
    if chapter.status:
        metadata["status"] = chapter.status
    return SourceInventoryItem(
        citation_path=chapter.citation_path,
        source_url=chapter.source_url,
        source_path=chapter.source_path,
        source_format=chapter.source_format,
        sha256=chapter.sha256,
        metadata=metadata,
    )


def _section_inventory_item(section: IdahoSection) -> SourceInventoryItem:
    metadata: dict[str, Any] = {
        "kind": "section",
        "title": section.listing.title_number,
        "chapter": section.listing.chapter,
        "section": section.listing.section,
        "heading": section.heading,
        "source_id": section.source_id,
        "parent_citation_path": section.parent_citation_path,
        "references_to": list(section.references_to),
    }
    if section.source_history:
        metadata["source_history"] = list(section.source_history)
    if section.source_notes:
        metadata["source_notes"] = list(section.source_notes)
    if section.status:
        metadata["status"] = section.status
    metadata.update(_section_variant_metadata(section))
    return SourceInventoryItem(
        citation_path=section.citation_path,
        source_url=section.source_url,
        source_path=section.source_path,
        source_format=section.source_format,
        sha256=section.sha256,
        metadata=metadata,
    )


def _title_record(
    title: IdahoTitle,
    *,
    version: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    return ProvisionRecord(
        id=deterministic_provision_id(title.citation_path),
        jurisdiction="us-id",
        document_class=DocumentClass.STATUTE.value,
        citation_path=title.citation_path,
        citation_label=title.legal_identifier,
        heading=title.heading,
        body=None,
        version=version,
        source_url=title.source_url,
        source_path=title.source_path,
        source_id=title.source_id,
        source_format=title.source_format,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=None,
        parent_id=None,
        level=0,
        ordinal=title.ordinal,
        kind="title",
        legal_identifier=title.legal_identifier,
        identifiers={"idaho:title": title.number},
        metadata={"title": title.number},
    )


def _chapter_record(
    chapter: IdahoChapter,
    *,
    version: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    metadata: dict[str, Any] = {
        "title": chapter.title_number,
        "chapter": chapter.chapter,
        "active": chapter.active,
    }
    if chapter.pdf_url:
        metadata["chapter_pdf_url"] = chapter.pdf_url
    if chapter.status:
        metadata["status"] = chapter.status
    return ProvisionRecord(
        id=deterministic_provision_id(chapter.citation_path),
        jurisdiction="us-id",
        document_class=DocumentClass.STATUTE.value,
        citation_path=chapter.citation_path,
        citation_label=chapter.legal_identifier,
        heading=chapter.heading,
        body=None,
        version=version,
        source_url=chapter.source_url,
        source_path=chapter.source_path,
        source_id=chapter.source_id,
        source_format=chapter.source_format,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=chapter.parent_citation_path,
        parent_id=deterministic_provision_id(chapter.parent_citation_path),
        level=1,
        ordinal=chapter.ordinal,
        kind="chapter",
        legal_identifier=chapter.legal_identifier,
        identifiers={"idaho:title": chapter.title_number, "idaho:chapter": chapter.chapter},
        metadata=metadata,
    )


def _section_record(
    section: IdahoSection,
    *,
    version: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    metadata: dict[str, Any] = {
        "title": section.listing.title_number,
        "chapter": section.listing.chapter,
        "section": section.listing.section,
        "references_to": list(section.references_to),
    }
    if section.source_history:
        metadata["source_history"] = list(section.source_history)
    if section.source_notes:
        metadata["source_notes"] = list(section.source_notes)
    if section.status:
        metadata["status"] = section.status
    metadata.update(_section_variant_metadata(section))
    return ProvisionRecord(
        id=deterministic_provision_id(section.citation_path),
        jurisdiction="us-id",
        document_class=DocumentClass.STATUTE.value,
        citation_path=section.citation_path,
        citation_label=section.legal_identifier,
        heading=section.heading,
        body=section.body,
        version=version,
        source_url=section.source_url,
        source_path=section.source_path,
        source_id=section.source_id,
        source_format=section.source_format,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=section.parent_citation_path,
        parent_id=deterministic_provision_id(section.parent_citation_path),
        level=2,
        ordinal=section.listing.ordinal,
        kind="section",
        legal_identifier=section.legal_identifier,
        identifiers={
            "idaho:title": section.listing.title_number,
            "idaho:chapter": section.listing.chapter,
            "idaho:section": section.listing.section,
        },
        metadata=metadata,
    )


def _section_variant_metadata(section: IdahoSection) -> dict[str, Any]:
    if section.variant is None:
        return {}
    metadata: dict[str, Any] = {
        "variant": section.variant,
        "canonical_citation_path": section.canonical_citation_path,
    }
    if section.effective_note:
        metadata["effective_note"] = section.effective_note
    return metadata


def _append_unique(
    seen: set[str],
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    item: SourceInventoryItem,
    record: ProvisionRecord,
) -> bool:
    if record.citation_path in seen:
        return False
    seen.add(record.citation_path)
    items.append(item)
    records.append(record)
    return True


def _record_source(
    store: CorpusArtifactStore,
    *,
    jurisdiction: str,
    run_id: str,
    source: _IdahoSource,
) -> _RecordedSource:
    artifact_path = store.source_path(
        jurisdiction,
        DocumentClass.STATUTE,
        run_id,
        source.relative_path,
    )
    sha256 = store.write_bytes(artifact_path, source.data)
    return _RecordedSource(
        source_url=source.source_url,
        source_path=_state_source_key(jurisdiction, run_id, source.relative_path),
        source_format=source.source_format,
        sha256=sha256,
    )


def _download_idaho_source(
    source_url: str,
    *,
    fetcher: _IdahoFetcher,
    request_delay_seconds: float,
    timeout_seconds: float,
    request_attempts: int,
) -> bytes:
    headers = {"User-Agent": IDAHO_USER_AGENT}
    last_error: requests.RequestException | None = None
    for attempt in range(1, request_attempts + 1):
        fetcher.wait_for_request_slot()
        try:
            response = requests.get(source_url, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= request_attempts:
                break
            time.sleep(max(request_delay_seconds, 0.25) * attempt)
    assert last_error is not None
    raise last_error


def _section_content_divs(soup: BeautifulSoup) -> tuple[Tag, ...]:
    divs: list[Tag] = []
    for div in soup.find_all("div"):
        if not isinstance(div, Tag):
            continue
        if div.find(
            "span",
            recursive=False,
            style=lambda value: value and "Courier New" in str(value),
        ):
            divs.append(div)
            continue
        style = str(div.get("style", ""))
        if "Courier New" in style:
            divs.append(div)
    return tuple(divs)


def _section_renditions(
    divs: tuple[Tag, ...],
    *,
    section: str,
) -> tuple[tuple[_IdahoRendition, ...], int]:
    """Split a page's content divs into the renditions of ``section`` it prints.

    A rendition starts at each div that opens with the section number and a
    heading, and runs to the next such div or to the History marker after the
    last one, whichever comes first. Returns the renditions in printed order
    and the index of that History marker (``len(divs)`` when there is none).
    """
    starts = [
        index
        for index, div in enumerate(divs)
        if _strip_section_heading(_clean_text(div), section)[1] is not None
    ]
    if not starts:
        return (), len(divs)
    history_start = next(
        (
            index
            for index in range(starts[-1] + 1, len(divs))
            if _is_history_marker(_clean_text(divs[index]))
        ),
        len(divs),
    )
    renditions: list[_IdahoRendition] = []
    for position, start in enumerate(starts, 1):
        next_start = starts[position] if position < len(starts) else history_start
        # A page with one rendition is read whole; its markers are never parsed.
        marker = _rendition_effective_marker(_clean_text(divs[start])) if len(starts) > 1 else None
        renditions.append(
            _IdahoRendition(
                position=position,
                start=start,
                end=min(next_start, history_start),
                effective_date=marker[0] if marker is not None else None,
                until=marker[1] if marker is not None else False,
                note=marker[2] if marker is not None else None,
            )
        )
    return tuple(renditions), history_start


def _primary_rendition(
    renditions: tuple[_IdahoRendition, ...],
    *,
    section: str,
    as_of: date,
) -> _IdahoRendition:
    """Return the one rendition in force on ``as_of``, or fail closed."""
    matching = [
        rendition
        for rendition in renditions
        if rendition.effective_date is not None and _rendition_in_force(rendition, as_of)
    ]
    unmarked = [rendition for rendition in renditions if rendition.effective_date is None]
    if len(matching) == 1:
        return matching[0]
    if not matching and len(unmarked) == 1:
        return unmarked[0]
    raise ValueError(f"Idaho section {section} has no unique rendition for {as_of.isoformat()}")


def _rendition_in_force(rendition: _IdahoRendition, as_of: date) -> bool:
    assert rendition.effective_date is not None
    if rendition.until:
        return as_of < rendition.effective_date
    return as_of >= rendition.effective_date


def _rendition_divs(
    divs: tuple[Tag, ...],
    renditions: tuple[_IdahoRendition, ...],
    rendition: _IdahoRendition,
    *,
    history_start: int,
) -> tuple[Tag, ...]:
    """The shared page prefix, one rendition, then the shared History and notes."""
    return (
        *divs[: renditions[0].start],
        *divs[rendition.start : rendition.end],
        *divs[history_start:],
    )


def _rendition_variant(rendition: _IdahoRendition) -> str:
    if rendition.effective_date is None:
        return f"variant-{rendition.position}"
    prefix = "effective-until" if rendition.until else "effective"
    return f"{prefix}-{rendition.effective_date.isoformat()}"


def _rendition_status(rendition: _IdahoRendition) -> str | None:
    # A variant is never the rendition in force, so a dated one either ended
    # ("until") or has not begun; the vocabulary is the NM/DE/NV/RI adapters'.
    if rendition.effective_date is None:
        return None
    return "effective_until" if rendition.until else "future_or_conditional"


def _rendition_effective_marker(text: str) -> tuple[date, bool, str] | None:
    match = _RENDITION_EFFECTIVE_RE.search(text)
    if match is None:
        return None
    effective_date = datetime.strptime(match.group("date"), "%B %d, %Y").date()
    return effective_date, match.group("until") is not None, _clean_text(match.group("note"))


def _coerce_expression_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid Idaho expression_date: {value!r}") from exc


def _strip_section_heading(text: str, section: str) -> tuple[str | None, str | None]:
    match = re.match(
        rf"^{re.escape(section)}\.\s*(?P<heading>.+?)\.\s*(?P<body>.*)$",
        text,
        re.S,
    )
    if match is None:
        match = re.match(rf"^{re.escape(section)}\.\s*(?P<heading>.+?)$", text, re.S)
    if match is None:
        return text, None
    heading = _clean_text(match.group("heading")).rstrip(".")
    body = _clean_text(match.groupdict().get("body") or "")
    return body or None, heading or None


def _extract_section_references(
    divs: tuple[Tag, ...],
    text: str,
    *,
    current: str,
) -> tuple[str, ...]:
    references: list[str] = []
    for div in divs:
        for link in div.find_all("a", href=True):
            match = _SECTION_HREF_RE.search(str(link["href"]))
            if match:
                _append_reference(references, match.group("section").upper(), current=current)
    for match in _SECTION_NUMBER_RE.finditer(text):
        _append_reference(references, match.group("section").upper(), current=current)
    return tuple(_dedupe_preserve_order(references))


def _append_reference(references: list[str], section: str, *, current: str) -> None:
    if section != current:
        references.append(f"us-id/statute/{section}")


def _title_page_heading(soup: BeautifulSoup, title: IdahoTitle) -> str:
    h1 = soup.find("h1", class_="lso-toc")
    text = _clean_text(h1) if h1 is not None else ""
    match = _TITLE_TEXT_RE.match(text)
    if match is not None and match.group("heading"):
        return _clean_heading(match.group("heading")) or title.heading
    return title.heading


def _is_centered_header(div: Tag) -> bool:
    style = str(div.get("style", "")).lower()
    return "text-align: center" in style


def _is_history_marker(text: str) -> bool:
    return text.strip().lower().rstrip(":") == "history"


def _is_note_marker(text: str) -> bool:
    return bool(re.match(r"^(compiler'?s notes?|cross references?|effective date):?", text, re.I))


def _strip_note_marker(text: str) -> str:
    return re.sub(
        r"^(compiler'?s notes?|cross references?|effective date):?\s*", "", text, flags=re.I
    )


def _status_from_heading(heading: str | None) -> str | None:
    if heading and re.search(
        r"\[(?:repealed|reserved|expired)\]|\b(repealed|reserved|expired)\b", heading, re.I
    ):
        if re.search(r"repealed", heading, re.I):
            return "repealed"
        if re.search(r"reserved", heading, re.I):
            return "reserved"
        if re.search(r"expired", heading, re.I):
            return "expired"
    return None


def _section_status(
    heading: str | None,
    body: str | None,
    notes: tuple[str, ...],
) -> str | None:
    return _status_from_heading(" ".join(part for part in [heading, body, *notes] if part))


def _write_cache_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _idaho_run_id(
    version: str,
    *,
    title_filter: str | None,
    chapter_filter: str | None,
    limit: int | None,
) -> str:
    if title_filter is None and chapter_filter is None and limit is None:
        return version
    parts = [version, "us-id"]
    if title_filter is not None:
        parts.append(f"title-{title_filter}")
    if chapter_filter is not None:
        parts.append(f"chapter-{chapter_filter}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def _title_filter(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r"^(?:title|Title)[-\s]*", "", text)
    text = text.lstrip("0")
    return text or None


def _chapter_filter(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r"^(?:chapter|Chapter)[-\s]*", "", text)
    text = text.lstrip("0")
    return text.upper() or None


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _decode(value: str | bytes) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _clean_heading(value: Any) -> str | None:
    text = _clean_text(value)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or None


def _clean_text(value: Any) -> str:
    text = value.get_text(" ", strip=True) if hasattr(value, "get_text") else str(value)
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _join_paragraphs(parts: list[str]) -> str | None:
    cleaned = [_clean_text(part) for part in parts if _clean_text(part)]
    return "\n".join(cleaned) or None


def _state_source_key(jurisdiction: str, run_id: str, relative_path: str) -> str:
    return f"sources/{jurisdiction}/{DocumentClass.STATUTE.value}/{run_id}/{relative_path}"


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
