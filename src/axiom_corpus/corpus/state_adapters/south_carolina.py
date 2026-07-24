"""South Carolina Code of Laws source-first corpus adapter."""

from __future__ import annotations

import html as html_module
import re
import time
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

SOUTH_CAROLINA_BASE_URL = "https://www.scstatehouse.gov"
SOUTH_CAROLINA_SOURCE_FORMAT = "south-carolina-code-html"
SOUTH_CAROLINA_USER_AGENT = "axiom-corpus/0.1 (contact@axiom-foundation.org)"
SOUTH_CAROLINA_REQUEST_DELAY_SECONDS = 0.15
SOUTH_CAROLINA_REQUEST_ATTEMPTS = 3
SOUTH_CAROLINA_TIMEOUT_SECONDS = 90.0

_TITLE_LINK_RE = re.compile(
    r'<a\s+href="(?P<href>/code/title(?P<title>\d+)\.php)">\s*Title\s+\d+\s*</a>'
    r"\s*-\s*(?P<heading>[^<]+)",
    re.I,
)
_CHAPTER_HREF_RE = re.compile(r"/code/t(?P<title>\d{1,2})c(?P<chapter>\d{3})\.php$", re.I)
_CHAPTER_ROW_RE = re.compile(
    r"\b(?:CHAPTER|ARTICLE)\s+(?P<chapter>\d+[A-Z]?)\s*-\s*(?P<heading>.+?)(?:\s+HTML\b|$)",
    re.I,
)
_SECTION_RE = re.compile(
    r"^SECTION\s+(?P<section>\d{1,2}-\d+[A-Z]?-\d+(?:\.\d+)?[A-Z]?)\.\s*(?P<heading>.*)$",
    re.I,
)
_ARTICLE_RE = re.compile(r"^ARTICLE\s+(?P<article>[0-9A-Z]+)$", re.I)
_REFERENCE_RE = re.compile(r"\b(?P<section>\d{1,2}-\d+[A-Z]?-\d+(?:\.\d+)?[A-Z]?)\b")
_SESSION_LAW_AMENDMENT_RE = re.compile(
    r"^SECTION\s+(?P<amendment_section>\d+)\.\s+Section\s+"
    r"(?P<section>\d{1,2}-\d+[A-Z]?-\d+(?:\.\d+)?[A-Z]?)"
    r"(?P<subsection_path>(?:\([A-Z0-9]+\))*)\s+of\s+the\s+S\.C\.\s+Code\s+is\s+amended\s+"
    r"(?P<action>to\s+read|by\s+adding):$",
    re.I,
)
_SESSION_LAW_ACT_RE = re.compile(
    r"^\(A(?P<act_number>\d+),\s*R\d+,\s*H(?P<bill_number>\d+)\)$",
    re.I,
)
_SESSION_LAW_NEXT_SECTION_RE = re.compile(r"^SECTION\s+\d+\.", re.I)
_SESSION_LAW_SUBSECTION_MARKER_RE = re.compile(r"\((?P<marker>[A-Z0-9]+)\)", re.I)
_SESSION_LAW_LEADING_SUBSECTION_MARKERS_RE = re.compile(
    r"^(?P<markers>(?:\([A-Z0-9]+\))+)",
    re.I,
)


@dataclass(frozen=True)
class SouthCarolinaTitle:
    """Title metadata from the official Code of Laws index."""

    number: int
    heading: str
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"us-sc/statute/title-{self.number}"

    @property
    def legal_identifier(self) -> str:
        return f"S.C. Code Title {self.number}"


@dataclass(frozen=True)
class SouthCarolinaChapter:
    """Chapter metadata from an official title page."""

    title: int
    number: str
    heading: str | None
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"us-sc/statute/title-{self.title}/chapter-{self.number}"

    @property
    def legal_identifier(self) -> str:
        return f"S.C. Code Title {self.title}, Chapter {self.number}"


@dataclass(frozen=True)
class SouthCarolinaSection:
    """Parsed section from an official chapter page."""

    section: str
    heading: str | None
    body: str | None
    title: int
    chapter: str
    ordinal: int
    article: str | None = None
    article_heading: str | None = None
    references_to: tuple[str, ...] = ()
    source_history: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    status: str | None = None

    @property
    def citation_path(self) -> str:
        return f"us-sc/statute/{self.section}"

    @property
    def parent_citation_path(self) -> str:
        return f"us-sc/statute/title-{self.title}/chapter-{self.chapter}"

    @property
    def legal_identifier(self) -> str:
        return f"S.C. Code Section {self.section}"


@dataclass(frozen=True)
class SouthCarolinaSessionLawOverlay:
    """Operative amendment text for a Code section from an enacted session law."""

    section: str
    subsection: str | None
    subsection_path: tuple[str, ...]
    operation: str
    replacement_lines: tuple[str, ...]
    amendment_section: str
    act_number: str
    bill_number: str
    effective_text: str | None = None
    approved_text: str | None = None

    @property
    def history_citation(self) -> str:
        year_match = re.search(r"\b(20\d{2})\b", self.approved_text or "")
        year = year_match.group(1) if year_match else "2026"
        return (
            f"{year} Act No. {self.act_number} (H.{self.bill_number}), "
            f"SECTION {self.amendment_section}"
        )


@dataclass(frozen=True)
class _SouthCarolinaSourcePage:
    relative_path: str
    source_url: str
    data: bytes


class _SouthCarolinaFetcher:
    def __init__(
        self,
        *,
        base_url: str,
        source_dir: Path | None,
        download_dir: Path | None,
        request_delay_seconds: float,
        request_attempts: int,
        timeout_seconds: float,
    ) -> None:
        self.base_url = _base_url(base_url)
        self.source_dir = source_dir
        self.download_dir = download_dir
        self.request_delay_seconds = request_delay_seconds
        self.request_attempts = request_attempts
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": SOUTH_CAROLINA_USER_AGENT})

    def fetch_master(self) -> _SouthCarolinaSourcePage:
        return self.fetch(
            f"{SOUTH_CAROLINA_SOURCE_FORMAT}/statmast.html",
            urljoin(self.base_url, "/code/statmast.php"),
        )

    def fetch_title(self, title: int) -> _SouthCarolinaSourcePage:
        return self.fetch(
            f"{SOUTH_CAROLINA_SOURCE_FORMAT}/title-{title}.html",
            urljoin(self.base_url, f"/code/title{title}.php"),
        )

    def fetch_chapter(self, title: int, chapter: str | int) -> _SouthCarolinaSourcePage:
        chapter_number = int(str(chapter))
        return self.fetch(
            f"{SOUTH_CAROLINA_SOURCE_FORMAT}/title-{title}/chapter-{chapter_number}.html",
            urljoin(self.base_url, f"/code/t{title:02d}c{chapter_number:03d}.php"),
        )

    def fetch(self, relative_path: str, source_url: str) -> _SouthCarolinaSourcePage:
        normalized = _normalize_relative_path(relative_path)
        if self.source_dir is not None:
            source_path = _source_dir_file(self.source_dir, normalized)
            if source_path is None:
                raise ValueError(f"South Carolina source file does not exist: {self.source_dir / normalized}")
            return _SouthCarolinaSourcePage(
                relative_path=normalized,
                source_url=source_url,
                data=source_path.read_bytes(),
            )
        if self.download_dir is not None:
            cached_path = self.download_dir / normalized
            if cached_path.exists():
                return _SouthCarolinaSourcePage(
                    relative_path=normalized,
                    source_url=source_url,
                    data=cached_path.read_bytes(),
                )

        data = self._download(source_url)
        if self.download_dir is not None:
            cached_path = self.download_dir / normalized
            cached_path.parent.mkdir(parents=True, exist_ok=True)
            cached_path.write_bytes(data)
        return _SouthCarolinaSourcePage(relative_path=normalized, source_url=source_url, data=data)

    def _download(self, source_url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, max(1, self.request_attempts) + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.request_delay_seconds:
                time.sleep(self.request_delay_seconds - elapsed)
            try:
                response = self._session.get(source_url, timeout=self.timeout_seconds)
                self._last_request_at = time.monotonic()
                response.raise_for_status()
                return response.content
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.request_attempts:
                    break
                time.sleep(min(2.0 * attempt, 8.0))
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"failed to fetch {source_url}")


def extract_south_carolina_code(
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
    base_url: str = SOUTH_CAROLINA_BASE_URL,
    request_delay_seconds: float = SOUTH_CAROLINA_REQUEST_DELAY_SECONDS,
    request_attempts: int = SOUTH_CAROLINA_REQUEST_ATTEMPTS,
    timeout_seconds: float = SOUTH_CAROLINA_TIMEOUT_SECONDS,
    session_law_url: str | None = None,
    session_law_section: str | None = None,
    session_law_sections: tuple[str, ...] = (),
    session_law_source_id: str | None = None,
    excluded_sections: tuple[str, ...] = (),
) -> StateStatuteExtractReport:
    """Snapshot official South Carolina Code HTML and extract provisions."""
    jurisdiction = "us-sc"
    title_filter = _title_filter(only_title)
    chapter_filter = _chapter_filter(only_chapter)
    excluded_section_keys = {
        section.strip().lower() for section in excluded_sections if section.strip()
    }
    run_id = _south_carolina_run_id(
        version,
        title_filter=title_filter,
        chapter_filter=chapter_filter,
        limit=limit,
    )
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    fetcher = _SouthCarolinaFetcher(
        base_url=base_url,
        source_dir=Path(source_dir) if source_dir is not None else None,
        download_dir=Path(download_dir) if download_dir is not None else None,
        request_delay_seconds=request_delay_seconds,
        request_attempts=request_attempts,
        timeout_seconds=timeout_seconds,
    )

    source_paths: list[Path] = []
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    title_count = 0
    container_count = 0
    section_count = 0
    skipped_source_count = 0
    remaining_sections = limit

    session_law_page: _SouthCarolinaSourcePage | None = None
    session_law_path: Path | None = None
    session_law_source_key: str | None = None
    session_law_sha: str | None = None
    session_law_overlays: tuple[SouthCarolinaSessionLawOverlay, ...] = ()
    session_law_applied: set[str] = set()
    if session_law_url is not None:
        requested_sections = tuple(
            dict.fromkeys(
                section.strip()
                for section in (
                    *session_law_sections,
                    *((session_law_section,) if session_law_section else ()),
                )
                if section.strip()
            )
        )
        if not requested_sections:
            raise ValueError(
                "session_law_section or session_law_sections is required with "
                "session_law_url"
            )
        source_id = safe_segment(session_law_source_id or "session-law")
        session_law_page = fetcher.fetch(
            f"{SOUTH_CAROLINA_SOURCE_FORMAT}/session-laws/{source_id}.html",
            session_law_url,
        )
        session_law_overlays = tuple(
            parse_south_carolina_session_law_overlay(
                session_law_page.data,
                section=section,
            )
            for section in requested_sections
        )
        session_law_path = store.source_path(
            jurisdiction,
            DocumentClass.STATUTE,
            run_id,
            session_law_page.relative_path,
        )
        session_law_sha = store.write_bytes(session_law_path, session_law_page.data)
        source_paths.append(session_law_path)
        session_law_source_key = _state_source_key(
            jurisdiction,
            run_id,
            session_law_page.relative_path,
        )

    master_page = fetcher.fetch_master()
    master_path = store.source_path(
        jurisdiction,
        DocumentClass.STATUTE,
        run_id,
        master_page.relative_path,
    )
    master_sha = store.write_bytes(master_path, master_page.data)
    source_paths.append(master_path)
    master_source_key = _state_source_key(jurisdiction, run_id, master_page.relative_path)
    titles = tuple(
        title
        for title in parse_south_carolina_master_index_html(master_page.data)
        if title_filter is None or title.number == title_filter
    )
    if not titles:
        raise ValueError(f"no South Carolina titles selected for filter: {only_title!r}")

    for title in titles:
        if remaining_sections is not None and remaining_sections <= 0:
            break
        try:
            title_page = fetcher.fetch_title(title.number)
        except ValueError as exc:
            skipped_source_count += 1
            errors.append(f"title {title.number}: {exc}")
            continue

        title_path = store.source_path(
            jurisdiction,
            DocumentClass.STATUTE,
            run_id,
            title_page.relative_path,
        )
        title_sha = store.write_bytes(title_path, title_page.data)
        source_paths.append(title_path)
        title_source_key = _state_source_key(jurisdiction, run_id, title_page.relative_path)
        chapters = tuple(
            chapter
            for chapter in parse_south_carolina_title_html(title_page.data, title=title.number)
            if chapter_filter is None or chapter.number == chapter_filter
        )
        if not chapters:
            skipped_source_count += 1
            errors.append(f"title {title.number}: no chapters selected")
            continue

        if title.citation_path not in seen:
            seen.add(title.citation_path)
            title_count += 1
            _append_record(
                items,
                records,
                citation_path=title.citation_path,
                version=run_id,
                source_url=title_page.source_url,
                source_path=title_source_key,
                source_id=f"title-{title.number}",
                sha256=title_sha,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                kind="title",
                body=None,
                heading=title.heading,
                legal_identifier=title.legal_identifier,
                parent_citation_path=None,
                level=0,
                ordinal=title.ordinal,
                identifiers={"south_carolina:title": str(title.number)},
                metadata={
                    "kind": "title",
                    "title": str(title.number),
                    "index_source_path": master_source_key,
                    "index_sha256": master_sha,
                },
            )

        for chapter in chapters:
            if remaining_sections is not None and remaining_sections <= 0:
                break
            try:
                chapter_page = fetcher.fetch_chapter(title.number, chapter.number)
            except (requests.RequestException, ValueError) as exc:
                skipped_source_count += 1
                errors.append(f"title {title.number} chapter {chapter.number}: {exc}")
                continue

            chapter_path = store.source_path(
                jurisdiction,
                DocumentClass.STATUTE,
                run_id,
                chapter_page.relative_path,
            )
            chapter_sha = store.write_bytes(chapter_path, chapter_page.data)
            source_paths.append(chapter_path)
            chapter_source_key = _state_source_key(jurisdiction, run_id, chapter_page.relative_path)
            sections = tuple(
                section
                for section in parse_south_carolina_chapter_html(
                    chapter_page.data,
                    title=title.number,
                    chapter=chapter.number,
                )
                if section.section.lower() not in excluded_section_keys
            )
            chapter_body_lines = _chapter_note_lines(chapter_page.data) if not sections else []
            chapter_body = "\n".join(chapter_body_lines).strip() or None
            chapter_status = _status(chapter.heading, chapter_body_lines)

            if chapter.citation_path not in seen:
                seen.add(chapter.citation_path)
                container_count += 1
                _append_record(
                    items,
                    records,
                    citation_path=chapter.citation_path,
                    version=run_id,
                    source_url=chapter_page.source_url,
                    source_path=chapter_source_key,
                    source_id=f"title-{title.number}-chapter-{chapter.number}",
                    sha256=chapter_sha,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    kind="chapter",
                    body=chapter_body,
                    heading=chapter.heading,
                    legal_identifier=chapter.legal_identifier,
                    parent_citation_path=title.citation_path,
                    level=1,
                    ordinal=chapter.ordinal,
                    identifiers={
                        "south_carolina:title": str(title.number),
                        "south_carolina:chapter": chapter.number,
                    },
                    metadata={
                        "kind": "chapter",
                        "title": str(title.number),
                        "chapter": chapter.number,
                        **({"status": chapter_status} if chapter_status else {}),
                    },
                )

            if not sections:
                if not chapter_body:
                    errors.append(f"title {title.number} chapter {chapter.number}: no sections parsed")
                continue
            for section in sections:
                if remaining_sections is not None and remaining_sections <= 0:
                    break
                if section.citation_path in seen:
                    continue
                section_source_url = chapter_page.source_url
                section_source_path = chapter_source_key
                section_sha = chapter_sha
                metadata_updates: dict[str, Any] | None = None
                session_law_overlay = next(
                    (
                        overlay
                        for overlay in session_law_overlays
                        if section.section == overlay.section
                    ),
                    None,
                )
                if session_law_overlay is not None:
                    if (
                        session_law_page is None
                        or session_law_source_key is None
                        or session_law_sha is None
                    ):
                        raise RuntimeError("South Carolina session-law source was not persisted")
                    section = apply_south_carolina_session_law_overlay(
                        section,
                        session_law_overlay,
                    )
                    session_law_applied.add(session_law_overlay.section)
                    section_source_url = session_law_page.source_url
                    section_source_path = session_law_source_key
                    section_sha = session_law_sha
                    metadata_updates = {
                        "source_components": [
                            {
                                "role": "codified_base",
                                "source_url": chapter_page.source_url,
                                "source_path": chapter_source_key,
                                "sha256": chapter_sha,
                            },
                            {
                                "role": "operative_session_law_overlay",
                                "source_url": session_law_page.source_url,
                                "source_path": session_law_source_key,
                                "sha256": session_law_sha,
                            },
                        ],
                        "session_law_overlay": {
                            "act_number": session_law_overlay.act_number,
                            "bill_number": session_law_overlay.bill_number,
                            "amendment_section": session_law_overlay.amendment_section,
                            "operation": session_law_overlay.operation,
                            "subsection_path": _format_subsection_path(
                                session_law_overlay.subsection_path
                            ),
                            "effective_text": session_law_overlay.effective_text,
                            "approved_text": session_law_overlay.approved_text,
                        },
                    }
                seen.add(section.citation_path)
                section_count += 1
                _append_section_record(
                    items,
                    records,
                    section,
                    version=run_id,
                    source_url=section_source_url,
                    source_path=section_source_path,
                    sha256=section_sha,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    metadata_updates=metadata_updates,
                )
                if remaining_sections is not None:
                    remaining_sections -= 1

    unapplied_session_law_sections = {
        overlay.section for overlay in session_law_overlays
    } - session_law_applied
    if unapplied_session_law_sections:
        raise ValueError(
            "South Carolina session-law overlay targets were not extracted: "
            f"{', '.join(sorted(unapplied_session_law_sections))}"
        )
    if not records:
        raise ValueError("no South Carolina provisions extracted")

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
        skipped_source_count=skipped_source_count,
        errors=tuple(errors),
    )


def parse_south_carolina_master_index_html(html: str | bytes) -> tuple[SouthCarolinaTitle, ...]:
    """Parse the official Code of Laws master title index."""
    text = _decode(html)
    titles: list[SouthCarolinaTitle] = []
    seen: set[int] = set()
    for match in _TITLE_LINK_RE.finditer(text):
        number = int(match.group("title"))
        if number in seen:
            continue
        seen.add(number)
        titles.append(
            SouthCarolinaTitle(
                number=number,
                heading=_title_case(_clean_text(html_module.unescape(match.group("heading")))),
                ordinal=len(titles) + 1,
            )
        )
    return tuple(titles)


def parse_south_carolina_title_html(
    html: str | bytes,
    *,
    title: int,
) -> tuple[SouthCarolinaChapter, ...]:
    """Parse one official title table of contents page."""
    soup = BeautifulSoup(html, "lxml")
    chapters: list[SouthCarolinaChapter] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        match = _CHAPTER_HREF_RE.search(href)
        if not match or int(match.group("title")) != int(title):
            continue
        chapter = str(int(match.group("chapter")))
        if chapter in seen:
            continue
        seen.add(chapter)
        row = anchor.find_parent("tr")
        text = _clean_text(row.get_text(" ", strip=True) if row is not None else anchor.parent.get_text(" ", strip=True))
        row_match = _CHAPTER_ROW_RE.search(text)
        heading = _title_case(row_match.group("heading")) if row_match else None
        chapters.append(
            SouthCarolinaChapter(
                title=int(title),
                number=chapter,
                heading=heading,
                ordinal=len(chapters) + 1,
            )
        )
    return tuple(chapters)


def parse_south_carolina_chapter_html(
    html: str | bytes,
    *,
    title: int,
    chapter: str | int,
) -> tuple[SouthCarolinaSection, ...]:
    """Parse sections from one official chapter page."""
    chapter_number = str(int(str(chapter)))
    soup = BeautifulSoup(html, "lxml")
    _replace_tables_with_text(soup)
    lines = [_clean_text(line) for line in soup.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]

    sections: list[SouthCarolinaSection] = []
    current_section: str | None = None
    current_heading: str | None = None
    current_body: list[str] = []
    current_article: str | None = None
    current_article_heading: str | None = None
    pending_article: str | None = None
    pending_article_heading: str | None = None

    def finish_current() -> None:
        nonlocal current_section, current_heading, current_body, current_article, current_article_heading
        if current_section is None:
            return
        body_lines = [line for line in current_body if line]
        body = "\n".join(body_lines).strip() or None
        source_history = tuple(
            dict.fromkeys(line for line in body_lines if line.upper().startswith("HISTORY:"))
        )
        notes = tuple(
            dict.fromkeys(
                line
                for line in body_lines
                if line.upper().startswith(("EDITOR'S NOTE", "CODE COMMISSIONER", "EFFECT OF AMENDMENT"))
            )
        )
        references = _references_to(body_lines, self_section=current_section)
        sections.append(
            SouthCarolinaSection(
                section=current_section,
                heading=current_heading,
                body=body,
                title=int(title),
                chapter=chapter_number,
                ordinal=len(sections) + 1,
                article=current_article,
                article_heading=current_article_heading,
                references_to=references,
                source_history=source_history,
                notes=notes,
                status=_status(current_heading, body_lines),
            )
        )
        current_section = None
        current_heading = None
        current_body = []
        current_article = None
        current_article_heading = None

    i = 0
    while i < len(lines):
        line = lines[i]
        article_match = _ARTICLE_RE.match(line)
        if article_match:
            pending_article = article_match.group("article").upper()
            pending_article_heading = None
            if i + 1 < len(lines) and not _SECTION_RE.match(lines[i + 1]):
                pending_article_heading = _title_case(lines[i + 1])
                i += 2
            else:
                i += 1
            continue

        section_match = _SECTION_RE.match(line)
        if section_match:
            finish_current()
            current_section = section_match.group("section")
            inline_heading = _clean_heading(section_match.group("heading"))
            if inline_heading:
                current_heading = inline_heading
                i += 1
            else:
                current_heading = None
                j = i + 1
                while j < len(lines):
                    candidate = lines[j]
                    if candidate and not _SECTION_RE.match(candidate) and not _ARTICLE_RE.match(candidate):
                        current_heading = _clean_heading(candidate)
                        break
                    j += 1
                i = j + 1
            current_article = pending_article
            current_article_heading = pending_article_heading
            pending_article = None
            pending_article_heading = None
            continue

        if current_section is not None and not _chapter_noise(line):
            current_body.append(line)
        i += 1

    finish_current()
    return tuple(sections)


def _leading_subsection_markers(line: str) -> tuple[str, ...]:
    match = _SESSION_LAW_LEADING_SUBSECTION_MARKERS_RE.match(line)
    if match is None:
        return ()
    return tuple(
        marker.group("marker")
        for marker in _SESSION_LAW_SUBSECTION_MARKER_RE.finditer(match.group("markers"))
    )


def _format_subsection_path(path: tuple[str, ...]) -> str:
    return "".join(f"({component})" for component in path)


def _retain_co_located_ancestor_markers(
    *,
    codified_line: str,
    replacement_lines: tuple[str, ...],
    target: str,
) -> tuple[str, ...]:
    """Keep ancestor markers that share the codified target's first line."""
    if not replacement_lines:
        return replacement_lines
    codified_markers = _leading_subsection_markers(codified_line)
    target_index = next(
        (
            index
            for index in range(len(codified_markers) - 1, -1, -1)
            if codified_markers[index].casefold() == target.casefold()
        ),
        None,
    )
    if target_index is None or target_index == 0:
        return replacement_lines

    ancestor_markers = codified_markers[:target_index]
    replacement_markers = _leading_subsection_markers(replacement_lines[0])
    expected_prefix = (*ancestor_markers, target)
    if tuple(
        marker.casefold() for marker in replacement_markers[: len(expected_prefix)]
    ) == tuple(marker.casefold() for marker in expected_prefix):
        return replacement_lines
    if not replacement_markers or replacement_markers[0].casefold() != target.casefold():
        return replacement_lines

    ancestor_prefix = _format_subsection_path(ancestor_markers)
    return (
        f"{ancestor_prefix}{replacement_lines[0]}",
        *replacement_lines[1:],
    )


def _subsection_marker_kind(marker: str) -> str:
    if marker.isdigit():
        return "number"
    if marker.isupper():
        return "upper-alpha"
    if re.fullmatch(r"[ivxlcdm]+", marker):
        return "lower-roman"
    return "lower-alpha"


def _find_subsection_range(
    lines: list[str],
    path: tuple[str, ...],
    *,
    section: str,
) -> tuple[int, int]:
    if not path:
        raise ValueError("South Carolina subsection path cannot be empty")

    search_start = 0
    search_end = len(lines)
    path_index = 0
    target_start: int | None = None
    while path_index < len(path):
        target = path[path_index]
        found_index: int | None = None
        consumed = 0
        for line_index in range(search_start, search_end):
            markers = _leading_subsection_markers(lines[line_index])
            if not markers or markers[0].casefold() != target.casefold():
                continue
            consumed = 1
            while (
                consumed < len(markers)
                and path_index + consumed < len(path)
                and markers[consumed].casefold()
                == path[path_index + consumed].casefold()
            ):
                consumed += 1
            found_index = line_index
            break
        if found_index is None:
            raise ValueError(
                f"codified section {section} omits subsection "
                f"{_format_subsection_path(path)}"
            )

        target_start = found_index
        consumed_kinds = {
            _subsection_marker_kind(component)
            for component in path[path_index : path_index + consumed]
        }
        sibling_index = next(
            (
                line_index
                for line_index in range(found_index + 1, search_end)
                if (
                    (markers := _leading_subsection_markers(lines[line_index]))
                    and _subsection_marker_kind(markers[0]) in consumed_kinds
                )
            ),
            search_end,
        )
        search_start = found_index
        search_end = sibling_index
        path_index += consumed

    if target_start is None:
        raise ValueError(
            f"codified section {section} omits subsection "
            f"{_format_subsection_path(path)}"
        )
    return target_start, search_end


def parse_south_carolina_session_law_overlay(
    html: str | bytes,
    *,
    section: str,
) -> SouthCarolinaSessionLawOverlay:
    """Parse enacted replacement or addition text from an official session-law page."""
    soup = BeautifulSoup(html, "lxml")
    lines = [_clean_text(line) for line in soup.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    heading_lines = {
        _clean_text(tag.get_text(" ", strip=True))
        for tag in soup.find_all(("b", "strong"))
        if _clean_text(tag.get_text(" ", strip=True))
    }

    act_match = next(
        (match for line in lines if (match := _SESSION_LAW_ACT_RE.match(line))),
        None,
    )
    if act_match is None:
        raise ValueError("South Carolina session law does not identify an enacted act and bill")

    amendment_index: int | None = None
    amendment_match: re.Match[str] | None = None
    for index, line in enumerate(lines):
        candidate = _SESSION_LAW_AMENDMENT_RE.match(line)
        if candidate is not None and candidate.group("section").lower() == section.lower():
            amendment_index = index
            amendment_match = candidate
            break
    if amendment_index is None or amendment_match is None:
        raise ValueError(f"session law does not amend South Carolina section {section}")

    next_section_index = next(
        (
            index
            for index in range(amendment_index + 1, len(lines))
            if _SESSION_LAW_NEXT_SECTION_RE.match(lines[index])
        ),
        len(lines),
    )
    candidates = [
        line
        for line in lines[amendment_index + 1 : next_section_index]
        if line not in heading_lines
    ]
    raw_subsection_path = amendment_match.group("subsection_path") or ""
    subsection_path = tuple(
        match.group("marker")
        for match in _SESSION_LAW_SUBSECTION_MARKER_RE.finditer(raw_subsection_path)
    )
    subsection = subsection_path[0] if len(subsection_path) == 1 else None
    action = " ".join(amendment_match.group("action").lower().split())
    if subsection_path:
        operation = "replace_subsection"
        replacement_marker = subsection_path[-1]
        start_index = next(
            (
                index
                for index, line in enumerate(candidates)
                if (
                    (markers := _leading_subsection_markers(line))
                    and markers[0].casefold() == replacement_marker.casefold()
                )
            ),
            None,
        )
        if start_index is None:
            raise ValueError(
                "session law omits replacement subsection "
                f"{_format_subsection_path(subsection_path)} for {section}"
            )
        replacement_lines = tuple(candidates[start_index:])
    elif action == "by adding":
        operation = "add"
        replacement_lines = tuple(candidates)
    else:
        operation = "replace_section"
        replacement_lines = tuple(candidates)
        if replacement_lines:
            section_prefix = re.compile(
                rf"^Section\s+{re.escape(amendment_match.group('section'))}\.\s*",
                re.I,
            )
            replacement_lines = (
                section_prefix.sub("", replacement_lines[0]),
                *replacement_lines[1:],
            )
    if not replacement_lines:
        raise ValueError(f"session law has no amendment text for South Carolina section {section}")

    effective_text = next(
        (line for line in lines if "takes effect" in line.lower()),
        None,
    )
    approved_text = next(
        (line for line in lines if line.lower().startswith("approved the ")),
        None,
    )
    return SouthCarolinaSessionLawOverlay(
        section=amendment_match.group("section"),
        subsection=subsection,
        subsection_path=subsection_path,
        operation=operation,
        replacement_lines=replacement_lines,
        amendment_section=amendment_match.group("amendment_section"),
        act_number=act_match.group("act_number"),
        bill_number=act_match.group("bill_number"),
        effective_text=effective_text,
        approved_text=approved_text,
    )


def apply_south_carolina_session_law_overlay(
    section: SouthCarolinaSection,
    overlay: SouthCarolinaSessionLawOverlay,
) -> SouthCarolinaSection:
    """Apply later-enacted replacement or addition text to a codified section."""
    if section.section.lower() != overlay.section.lower():
        raise ValueError(
            f"session-law overlay for {overlay.section} cannot apply to {section.section}"
        )
    body_lines = (section.body or "").splitlines()
    history_index = next(
        (
            index
            for index, line in enumerate(body_lines)
            if line.upper().startswith("HISTORY:")
        ),
        None,
    )
    if history_index is None:
        raise ValueError(f"codified section {section.section} omits source history")

    if overlay.operation == "replace_subsection":
        if not overlay.subsection_path:
            raise ValueError("replacement-subsection overlay omits its subsection path")
        start_index, end_index = _find_subsection_range(
            body_lines[:history_index],
            overlay.subsection_path,
            section=section.section,
        )
        replacement_lines = _retain_co_located_ancestor_markers(
            codified_line=body_lines[start_index],
            replacement_lines=overlay.replacement_lines,
            target=overlay.subsection_path[-1],
        )
        target_kind = _subsection_marker_kind(overlay.subsection_path[-1])
        replacement_siblings = tuple(
            markers[0]
            for line in replacement_lines
            if (markers := _leading_subsection_markers(line))
            and _subsection_marker_kind(markers[0]) == target_kind
        )
        if replacement_siblings:
            final_path = (*overlay.subsection_path[:-1], replacement_siblings[-1])
            # The enacted replacement may add a sibling that did not exist in
            # the codified base. The target subtree remains the insertion
            # boundary in that case.
            with suppress(ValueError):
                _, end_index = _find_subsection_range(
                    body_lines[:history_index],
                    final_path,
                    section=section.section,
                )
        revised_lines = [
            *body_lines[:start_index],
            *replacement_lines,
            *body_lines[end_index:],
        ]
        history_line_index = revised_lines.index(body_lines[history_index])
    elif overlay.operation == "add":
        revised_lines = [
            *body_lines[:history_index],
            *overlay.replacement_lines,
            *body_lines[history_index:],
        ]
        history_line_index = history_index + len(overlay.replacement_lines)
    elif overlay.operation == "replace_section":
        revised_lines = [*overlay.replacement_lines, *body_lines[history_index:]]
        history_line_index = len(overlay.replacement_lines)
    else:
        raise ValueError(f"unsupported South Carolina session-law operation: {overlay.operation}")
    history_line = revised_lines[history_line_index].rstrip().removesuffix(".")
    if overlay.history_citation not in history_line:
        revised_lines[history_line_index] = f"{history_line}; {overlay.history_citation}."
    body = "\n".join(revised_lines).strip()
    source_history = tuple(
        dict.fromkeys(line for line in revised_lines if line.upper().startswith("HISTORY:"))
    )
    notes = tuple(
        dict.fromkeys(
            line
            for line in revised_lines
            if line.upper().startswith(
                ("EDITOR'S NOTE", "CODE COMMISSIONER", "EFFECT OF AMENDMENT")
            )
        )
    )
    return replace(
        section,
        body=body,
        references_to=_references_to(revised_lines, self_section=section.section),
        source_history=source_history,
        notes=notes,
    )


def _append_section_record(
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    section: SouthCarolinaSection,
    *,
    version: str,
    source_url: str,
    source_path: str,
    sha256: str,
    source_as_of: str,
    expression_date: str,
    metadata_updates: dict[str, Any] | None = None,
) -> None:
    metadata = _section_metadata(section)
    if metadata_updates:
        metadata.update(metadata_updates)
    _append_record(
        items,
        records,
        citation_path=section.citation_path,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=f"section-{section.section}",
        sha256=sha256,
        source_as_of=source_as_of,
        expression_date=expression_date,
        kind="section",
        body=section.body,
        heading=section.heading,
        legal_identifier=section.legal_identifier,
        parent_citation_path=section.parent_citation_path,
        level=2,
        ordinal=section.ordinal,
        identifiers={
            "south_carolina:title": str(section.title),
            "south_carolina:chapter": section.chapter,
            "south_carolina:section": section.section,
        },
        metadata=metadata,
    )


def _append_record(
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    *,
    citation_path: str,
    version: str,
    source_url: str,
    source_path: str,
    source_id: str,
    sha256: str,
    source_as_of: str,
    expression_date: str,
    kind: str,
    body: str | None,
    heading: str | None,
    legal_identifier: str,
    parent_citation_path: str | None,
    level: int,
    ordinal: int | None,
    identifiers: dict[str, str],
    metadata: dict[str, Any],
) -> None:
    items.append(
        SourceInventoryItem(
            citation_path=citation_path,
            source_url=source_url,
            source_path=source_path,
            source_format=SOUTH_CAROLINA_SOURCE_FORMAT,
            sha256=sha256,
            metadata=metadata,
        )
    )
    records.append(
        ProvisionRecord(
            id=deterministic_provision_id(citation_path, version),
            jurisdiction="us-sc",
            document_class=DocumentClass.STATUTE.value,
            citation_path=citation_path,
            body=body,
            heading=heading,
            citation_label=legal_identifier,
            version=version,
            source_url=source_url,
            source_path=source_path,
            source_id=source_id,
            source_format=SOUTH_CAROLINA_SOURCE_FORMAT,
            source_as_of=source_as_of,
            expression_date=expression_date,
            parent_citation_path=parent_citation_path,
            parent_id=(
                deterministic_provision_id(parent_citation_path, version)
                if parent_citation_path
                else None
            ),
            level=level,
            ordinal=ordinal,
            kind=kind,
            legal_identifier=legal_identifier,
            identifiers=identifiers,
            metadata=metadata,
        )
    )


def _section_metadata(section: SouthCarolinaSection) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": "section",
        "title": str(section.title),
        "chapter": section.chapter,
        "section": section.section,
    }
    if section.article:
        metadata["article"] = section.article
    if section.article_heading:
        metadata["article_heading"] = section.article_heading
    if section.references_to:
        metadata["references_to"] = list(section.references_to)
    if section.source_history:
        metadata["source_history"] = list(section.source_history)
    if section.notes:
        metadata["notes"] = list(section.notes)
    if section.status:
        metadata["status"] = section.status
    return metadata


def _references_to(body_lines: list[str], *, self_section: str) -> tuple[str, ...]:
    refs: list[str] = []
    for line in body_lines:
        for match in _REFERENCE_RE.finditer(line):
            section = match.group("section")
            if section == self_section:
                continue
            refs.append(f"us-sc/statute/{section}")
    return tuple(dict.fromkeys(refs))


def _replace_tables_with_text(soup: BeautifulSoup) -> None:
    for table in soup.find_all("table"):
        rows: list[str] = []
        for tr in table.find_all("tr"):
            cells = [
                _clean_text(cell.get_text(" ", strip=True))
                for cell in tr.find_all(["th", "td"])
                if _clean_text(cell.get_text(" ", strip=True))
            ]
            if cells:
                rows.append(" | ".join(cells))
        table.replace_with("\n" + "\n".join(rows) + "\n")


def _chapter_note_lines(html: str | bytes) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    _replace_tables_with_text(soup)
    lines = [_clean_text(line) for line in soup.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    body: list[str] = []
    started = False
    for line in lines:
        if not started:
            if line.startswith("CHAPTER "):
                started = True
            continue
        if _footer_noise(line):
            break
        if _chapter_noise(line):
            continue
        body.append(line)
    return body


def _chapter_noise(line: str) -> bool:
    return bool(
        line.startswith("South Carolina Law")
        or line == "South Carolina Code of Laws"
        or line == "Code of Laws"
        or line.startswith("Title ")
        or line.startswith("CHAPTER ")
    )


def _footer_noise(line: str) -> bool:
    return bool(
        line.startswith("South Carolina Legislative Services Agency")
        or line in {"Disclaimer", "Policies", "Photo Credits", "Contact Us"}
        or line.startswith("Legislative Services Agency")
        or line.startswith("h t t p")
    )


def _status(heading: str | None, body_lines: list[str]) -> str | None:
    joined = " ".join(part for part in [heading or "", *body_lines[:3]] if part).lower()
    if "repealed" in joined:
        return "repealed"
    if "reserved" in joined:
        return "reserved"
    return None


def _clean_heading(value: str | None) -> str | None:
    if value is None:
        return None
    text = _clean_text(value).rstrip(".")
    return text or None


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    text = html_module.unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _title_case(value: str | None) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if any(char.islower() for char in text):
        return text.removesuffix(".")
    small = {"A", "An", "And", "As", "At", "But", "By", "For", "In", "Nor", "Of", "On", "Or", "The", "To"}
    words = text.title().split()
    return " ".join(word.lower() if index and word in small else word for index, word in enumerate(words))


def _decode(html: str | bytes) -> str:
    if isinstance(html, bytes):
        return html.decode("utf-8-sig", errors="replace")
    return html


def _title_filter(value: str | int | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        raise ValueError(f"invalid South Carolina title filter: {value!r}")
    return int(match.group(0))


def _chapter_filter(value: str | int | None) -> str | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        raise ValueError(f"invalid South Carolina chapter filter: {value!r}")
    return str(int(match.group(0)))


def _south_carolina_run_id(
    version: str,
    *,
    title_filter: int | None,
    chapter_filter: str | None,
    limit: int | None,
) -> str:
    if title_filter is None and chapter_filter is None and limit is None:
        return version
    parts = [version, "us-sc"]
    if title_filter is not None:
        parts.append(f"title-{title_filter}")
    if chapter_filter is not None:
        parts.append(f"chapter-{chapter_filter}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _state_source_key(jurisdiction: str, run_id: str, relative_name: str) -> str:
    return f"sources/{jurisdiction}/{DocumentClass.STATUTE.value}/{run_id}/{relative_name}"


def _base_url(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def _normalize_relative_path(value: str) -> str:
    return "/".join(part for part in value.strip().split("/") if part)


def _source_dir_file(source_dir: Path, relative_path: str) -> Path | None:
    candidates = [source_dir / relative_path]
    if relative_path.startswith(f"{SOUTH_CAROLINA_SOURCE_FORMAT}/"):
        candidates.append(source_dir / relative_path.removeprefix(f"{SOUTH_CAROLINA_SOURCE_FORMAT}/"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
