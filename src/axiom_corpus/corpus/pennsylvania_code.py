"""Pennsylvania Code source-first adapter."""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TextIO
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup, Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment, sha256_bytes
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

PENNSYLVANIA_CODE_BASE_URL = "https://www.pacodeandbulletin.gov"
PENNSYLVANIA_CODE_HOME_URL = f"{PENNSYLVANIA_CODE_BASE_URL}/"
PENNSYLVANIA_CODE_SOURCE_FORMAT = "pennsylvania-code-html"
PENNSYLVANIA_CODE_USER_AGENT = "axiom-corpus/0.1 (max@axiom-foundation.org)"

_SOURCE_PREFIX = "pennsylvania-code"
_TITLE_OPTION_RE = re.compile(r"^(?P<number>\d+)\s+(?P<name>.+)$")
_CHAPTER_LINK_RE = re.compile(
    r"Chapter\s+(?P<number>[A-Za-z0-9.-]+)\.\s*"
    r"<a\s+[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>"
    r"(?P<name>.*?)(?:</FONT>)?</a>",
    re.I | re.S,
)
_SECTION_BREAK_RE = re.compile(r"<!--\s*sectbreak;(?P<meta>.*?)-->", re.I | re.S)
_SECTION_REF_RE = re.compile(
    r"\b(?P<title>\d+)\s+Pa\.\s*Code\s+§+\s*(?P<section>[A-Za-z0-9.-]+)",
    re.I,
)


@dataclass(frozen=True)
class PennsylvaniaCodeExtractReport:
    """Result from a Pennsylvania Code extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    title_count: int
    chapter_count: int
    reserved_chapter_count: int
    section_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]
    skipped_source_count: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SourceSnapshot:
    source_key: str
    source_path: Path
    sha256: str
    content: bytes


@dataclass(frozen=True)
class _Title:
    number: str
    name: str
    relative_file: str
    ordinal: int

    @property
    def padded_number(self) -> str:
        return self.relative_file.strip("/").split("/", 1)[0]

    @property
    def citation_path(self) -> str:
        return f"us-pa/regulation/title-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return _secure_url(self.relative_file)

    @property
    def heading(self) -> str:
        return f"Title {self.number}. {self.name}"


@dataclass(frozen=True)
class _TitleSnapshot:
    title: _Title
    snapshot: _SourceSnapshot
    chapters: tuple[_Chapter, ...]


@dataclass(frozen=True)
class _Chapter:
    title: _Title
    number: str
    name: str
    relative_file: str
    ordinal: int
    reserved: bool = False

    @property
    def citation_path(self) -> str:
        return f"{self.title.citation_path}/chapter-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return _secure_url(self.relative_file)

    @property
    def heading(self) -> str:
        return f"Chapter {self.number}. {self.name}"


@dataclass(frozen=True)
class _ChapterSnapshot:
    chapter: _Chapter
    snapshot: _SourceSnapshot | None
    sections: tuple[_Section, ...]
    authority: str | None = None
    source_note: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class _Section:
    chapter: _Chapter
    number: str
    heading: str
    body: str | None
    references_to: tuple[str, ...]
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"{self.chapter.citation_path}/section-{_path_token(self.number)}"

    @property
    def legal_identifier(self) -> str:
        return f"{self.chapter.title.number} Pa. Code § {self.number}"

    @property
    def source_url(self) -> str:
        return _display_url(self.chapter.title.padded_number, self.chapter.relative_file)


def pennsylvania_code_run_id(
    version: str,
    *,
    only_title: str | None = None,
    only_chapter: str | None = None,
    limit_titles: int | None = None,
    limit_chapters: int | None = None,
) -> str:
    """Return a scoped Pennsylvania Code run id."""

    parts = [version]
    if only_title:
        parts.append(f"title-{_path_token(only_title)}")
    if only_chapter:
        parts.append(f"chapter-{_path_token(only_chapter)}")
    if limit_titles is not None:
        parts.append(f"limit-titles-{limit_titles}")
    if limit_chapters is not None:
        parts.append(f"limit-chapters-{limit_chapters}")
    return "-".join(parts)


def extract_pennsylvania_code(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | None = None,
    only_chapter: str | None = None,
    limit_titles: int | None = None,
    limit_chapters: int | None = None,
    workers: int = 8,
    progress_stream: TextIO | None = None,
) -> PennsylvaniaCodeExtractReport:
    """Snapshot official Pennsylvania Code HTML and extract provisions."""

    jurisdiction = "us-pa"
    document_class = DocumentClass.REGULATION.value
    run_id = pennsylvania_code_run_id(
        version,
        only_title=only_title,
        only_chapter=only_chapter,
        limit_titles=limit_titles,
        limit_chapters=limit_chapters,
    )
    source_root = Path(source_dir) if source_dir is not None else None
    download_root = Path(download_dir) if download_dir is not None and source_root is None else None
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    session = _session()

    home_snapshot = _snapshot_html(
        store,
        session,
        run_id=run_id,
        relative_name=f"{_SOURCE_PREFIX}/index.html",
        url=PENNSYLVANIA_CODE_HOME_URL,
        source_root=source_root,
        download_root=download_root,
    )
    source_paths: list[Path] = [home_snapshot.source_path]
    all_titles = _parse_titles(home_snapshot.content)
    titles = tuple(
        title for title in all_titles if only_title is None or _same_token(title.number, only_title)
    )
    if limit_titles is not None:
        titles = titles[:limit_titles]
    if not titles:
        raise ValueError(f"no Pennsylvania Code titles selected: {only_title!r}")

    root_path = "us-pa/regulation"
    inventory: list[SourceInventoryItem] = [
        SourceInventoryItem(
            citation_path=root_path,
            source_url=PENNSYLVANIA_CODE_HOME_URL,
            source_path=home_snapshot.source_key,
            source_format=PENNSYLVANIA_CODE_SOURCE_FORMAT,
            sha256=home_snapshot.sha256,
            metadata={
                "kind": "collection",
                "source_as_of": source_as_of_text,
                "selected_title_count": len(titles),
                "total_title_count": len(all_titles),
                "effective_through": _effective_through(home_snapshot.content),
            },
        )
    ]
    records: list[ProvisionRecord] = [
        _root_record(
            version=run_id,
            source_path=home_snapshot.source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            selected_title_count=len(titles),
            total_title_count=len(all_titles),
            effective_through=_effective_through(home_snapshot.content),
        )
    ]

    errors: list[str] = []
    skipped_source_count = 0
    title_snapshots: list[_TitleSnapshot] = []
    selected_chapters: list[_Chapter] = []
    reserved_chapter_count = 0
    for title in titles:
        _progress(progress_stream, f"pennsylvania-code title {title.number}")
        try:
            snapshot = _snapshot_html(
                store,
                session,
                run_id=run_id,
                relative_name=f"{_SOURCE_PREFIX}{title.relative_file}",
                url=title.source_url,
                source_root=source_root,
                download_root=download_root,
            )
        except (OSError, requests.RequestException) as exc:
            errors.append(f"title {title.number}: {exc}")
            skipped_source_count += 1
            continue
        source_paths.append(snapshot.source_path)
        chapters = _parse_chapters(snapshot.content, title=title)
        if only_chapter is not None:
            chapters = tuple(
                chapter for chapter in chapters if _same_token(chapter.number, only_chapter)
            )
        if limit_chapters is not None:
            chapters = chapters[:limit_chapters]
        title_snapshots.append(_TitleSnapshot(title=title, snapshot=snapshot, chapters=chapters))
        active_chapters = tuple(chapter for chapter in chapters if not chapter.reserved)
        reserved_chapter_count += len(chapters) - len(active_chapters)
        selected_chapters.extend(active_chapters)

    if only_chapter is not None and not selected_chapters:
        raise ValueError(f"no Pennsylvania Code chapter selected: {only_chapter!r}")

    chapter_results = _snapshot_chapters(
        store,
        run_id=run_id,
        chapters=tuple(selected_chapters),
        source_root=source_root,
        download_root=download_root,
        workers=workers,
        progress_stream=progress_stream,
    )
    chapter_result_by_path = {
        result.chapter.citation_path: result for result in chapter_results
    }
    seen_paths = {root_path}
    title_count = 0
    chapter_count = 0
    section_count = 0

    for title_snapshot in title_snapshots:
        title_chapters = tuple(
            chapter
            for chapter in title_snapshot.chapters
            if chapter.citation_path in chapter_result_by_path
        )
        if not title_chapters and only_chapter is not None:
            continue
        title = title_snapshot.title
        if title.citation_path not in seen_paths:
            seen_paths.add(title.citation_path)
            title_reserved_chapters = tuple(
                chapter for chapter in title_snapshot.chapters if chapter.reserved
            )
            _append_title(
                title,
                snapshot=title_snapshot.snapshot,
                inventory=inventory,
                records=records,
                version=run_id,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                chapter_count=len(title_chapters),
                reserved_chapters=title_reserved_chapters,
            )
            title_count += 1
        for chapter in title_chapters:
            result = chapter_result_by_path[chapter.citation_path]
            if result.error:
                errors.append(result.error)
                skipped_source_count += 1
                continue
            if result.snapshot is None:
                continue
            source_paths.append(result.snapshot.source_path)
            if chapter.citation_path not in seen_paths:
                seen_paths.add(chapter.citation_path)
                _append_chapter(
                    chapter,
                    snapshot=result.snapshot,
                    inventory=inventory,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    section_count=len(result.sections),
                    authority=result.authority,
                    source_note=result.source_note,
                )
                chapter_count += 1
            for section in result.sections:
                if section.citation_path in seen_paths:
                    continue
                seen_paths.add(section.citation_path)
                _append_section(
                    section,
                    snapshot=result.snapshot,
                    inventory=inventory,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                )
                section_count += 1

    if len(records) <= 1:
        raise ValueError("no Pennsylvania Code provisions extracted")

    inventory_path = store.inventory_path(jurisdiction, document_class, run_id)
    store.write_inventory(inventory_path, inventory)
    provisions_path = store.provisions_path(jurisdiction, document_class, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
    )
    coverage_path = store.coverage_path(jurisdiction, document_class, run_id)
    store.write_json(coverage_path, coverage.to_mapping())

    return PennsylvaniaCodeExtractReport(
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
        title_count=title_count,
        chapter_count=chapter_count,
        reserved_chapter_count=reserved_chapter_count,
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


def _snapshot_chapters(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    chapters: tuple[_Chapter, ...],
    source_root: Path | None,
    download_root: Path | None,
    workers: int,
    progress_stream: TextIO | None,
) -> tuple[_ChapterSnapshot, ...]:
    if workers <= 1:
        return tuple(
            _snapshot_chapter(
                store,
                run_id=run_id,
                chapter=chapter,
                source_root=source_root,
                download_root=download_root,
                progress_stream=progress_stream,
            )
            for chapter in chapters
        )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return tuple(
            executor.map(
                lambda chapter: _snapshot_chapter(
                    store,
                    run_id=run_id,
                    chapter=chapter,
                    source_root=source_root,
                    download_root=download_root,
                    progress_stream=progress_stream,
                ),
                chapters,
            )
        )


def _snapshot_chapter(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    chapter: _Chapter,
    source_root: Path | None,
    download_root: Path | None,
    progress_stream: TextIO | None,
) -> _ChapterSnapshot:
    _progress(
        progress_stream,
        f"pennsylvania-code chapter {chapter.title.number}-{chapter.number}",
    )
    try:
        snapshot = _snapshot_html(
            store,
            _session(),
            run_id=run_id,
            relative_name=f"{_SOURCE_PREFIX}{chapter.relative_file}",
            url=chapter.source_url,
            source_root=source_root,
            download_root=download_root,
        )
        sections, authority, source_note = _parse_sections(snapshot.content, chapter=chapter)
        return _ChapterSnapshot(
            chapter=chapter,
            snapshot=snapshot,
            sections=sections,
            authority=authority,
            source_note=source_note,
        )
    except (OSError, requests.RequestException) as exc:
        return _ChapterSnapshot(
            chapter=chapter,
            snapshot=None,
            sections=(),
            error=f"chapter {chapter.title.number}-{chapter.number}: {exc}",
        )


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": PENNSYLVANIA_CODE_USER_AGENT})
    return session


def _snapshot_html(
    store: CorpusArtifactStore,
    session: requests.Session,
    *,
    run_id: str,
    relative_name: str,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
) -> _SourceSnapshot:
    source_path = store.source_path("us-pa", DocumentClass.REGULATION, run_id, relative_name)
    source_key = _source_key(run_id, relative_name)
    if source_root is None and source_path.exists():
        content = source_path.read_bytes()
        return _SourceSnapshot(
            source_key=source_key,
            source_path=source_path,
            sha256=sha256_bytes(content),
            content=content,
        )
    content = _load_html(
        session,
        source_root,
        download_root,
        relative_name=relative_name,
        url=url,
    )
    sha256 = store.write_bytes(source_path, content)
    return _SourceSnapshot(source_key=source_key, source_path=source_path, sha256=sha256, content=content)


def _load_html(
    session: requests.Session,
    source_root: Path | None,
    download_root: Path | None,
    *,
    relative_name: str,
    url: str,
) -> bytes:
    if source_root is not None:
        return (source_root / relative_name).read_bytes()
    if download_root is not None:
        cached = download_root / relative_name
        if cached.exists():
            return cached.read_bytes()
    response = _get_with_retries(session, url)
    content = response.content
    if download_root is not None:
        cached = download_root / relative_name
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(content)
    return content


def _get_with_retries(
    session: requests.Session,
    url: str,
    *,
    attempts: int = 5,
) -> requests.Response:
    delay = 1.0
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if attempt == attempts or status not in {429, 500, 502, 503, 504}:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 20)
    assert last_error is not None
    raise last_error


def _parse_titles(content: bytes) -> tuple[_Title, ...]:
    soup = BeautifulSoup(content, "html.parser")
    titles: list[_Title] = []
    for ordinal, option in enumerate(soup.select("select#codeTitleSelected option"), start=1):
        relative_file = option.get("value")
        if not isinstance(relative_file, str) or not relative_file.startswith("/"):
            continue
        text = _clean_text(option.get_text(" ", strip=True))
        match = _TITLE_OPTION_RE.match(text)
        if not match:
            continue
        titles.append(
            _Title(
                number=match.group("number"),
                name=_clean_text(match.group("name")),
                relative_file=relative_file,
                ordinal=ordinal,
            )
        )
    return tuple(titles)


def _parse_chapters(content: bytes, *, title: _Title) -> tuple[_Chapter, ...]:
    text = _decode(content)
    chapters: list[_Chapter] = []
    seen_files: set[str] = set()
    for match in _CHAPTER_LINK_RE.finditer(text):
        href = match.group("href")
        if "chap" not in href.lower() or href in seen_files:
            continue
        seen_files.add(href)
        relative_file = _join_title_relative(title, href)
        name = _html_fragment_text(match.group("name"))
        chapters.append(
            _Chapter(
                title=title,
                number=_clean_text(match.group("number")),
                name=name,
                relative_file=relative_file,
                ordinal=len(chapters) + 1,
                reserved=_is_reserved_chapter_name(name),
            )
        )
    return tuple(chapters)


def _parse_sections(
    content: bytes,
    *,
    chapter: _Chapter,
) -> tuple[tuple[_Section, ...], str | None, str | None]:
    text = _decode(content)
    matches = list(_SECTION_BREAK_RE.finditer(text))
    authority, source_note = _chapter_notes(text[: matches[0].start()] if matches else text)
    sections: list[_Section] = []
    for index, match in enumerate(matches):
        section_number = _section_number_from_meta(match.group("meta"))
        if not section_number:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        fragment = text[match.end() : end]
        section = _parse_section_fragment(
            fragment,
            chapter=chapter,
            number=section_number,
            ordinal=len(sections) + 1,
        )
        if section is not None:
            sections.append(section)
    return tuple(sections), authority, source_note


def _parse_section_fragment(
    fragment: str,
    *,
    chapter: _Chapter,
    number: str,
    ordinal: int,
) -> _Section | None:
    soup = BeautifulSoup(fragment, "html.parser")
    heading_tag = soup.find(["h4", "H4"])
    if not isinstance(heading_tag, Tag):
        return None
    heading_text = _clean_text(heading_tag.get_text(" ", strip=True))
    heading = _section_heading(heading_text, number)
    heading_tag.decompose()
    body = _clean_body(soup.get_text("\n", strip=True))
    return _Section(
        chapter=chapter,
        number=number,
        heading=heading,
        body=body,
        references_to=_references_to(body or ""),
        ordinal=ordinal,
    )


def _chapter_notes(text: str) -> tuple[str | None, str | None]:
    soup = BeautifulSoup(text, "html.parser")
    paragraphs = [_clean_text(paragraph.get_text(" ", strip=True)) for paragraph in soup.find_all("p")]
    paragraphs = [
        paragraph
        for paragraph in paragraphs
        if paragraph and paragraph.lower() not in {"authority", "source"}
    ]
    authority: str | None = None
    source_note: str | None = None
    labels = [
        _clean_text(node.get_text(" ", strip=True)).lower()
        for node in soup.find_all(["b", "strong", "center"])
    ]
    if any(label == "authority" for label in labels) and paragraphs:
        authority = paragraphs[0]
    if any(label == "source" for label in labels):
        source_note = paragraphs[1] if authority and len(paragraphs) > 1 else paragraphs[0] if paragraphs else None
    return authority, source_note


def _section_heading(heading_text: str, number: str) -> str:
    cleaned = re.sub(r"^§\s*", "", heading_text)
    cleaned = re.sub(rf"^{re.escape(number)}\.?\s*", "", cleaned)
    return _clean_text(cleaned) or heading_text


def _append_title(
    title: _Title,
    *,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    chapter_count: int,
    reserved_chapters: tuple[_Chapter, ...] = (),
) -> None:
    metadata: dict[str, object] = {
        "kind": "title",
        "title_number": title.number,
        "source_as_of": source_as_of,
        "chapter_count": chapter_count,
        "reserved_chapter_count": len(reserved_chapters),
        "reserved_chapters": [chapter.number for chapter in reserved_chapters],
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    inventory.append(
        SourceInventoryItem(
            citation_path=title.citation_path,
            source_url=title.source_url,
            source_path=snapshot.source_key,
            source_format=PENNSYLVANIA_CODE_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=title.citation_path,
            parent_citation_path="us-pa/regulation",
            citation_label=f"{title.number} Pa. Code",
            heading=title.heading,
            body=None,
            version=version,
            source_url=title.source_url,
            source_path=snapshot.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=1,
            ordinal=title.ordinal,
            kind="title",
            legal_identifier=f"{title.number} Pa. Code",
            identifiers={"pennsylvania:code_title": title.number},
            metadata=metadata,
        )
    )


def _append_chapter(
    chapter: _Chapter,
    *,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    section_count: int,
    authority: str | None,
    source_note: str | None,
) -> None:
    metadata: dict[str, object] = {
        "kind": "chapter",
        "title_number": chapter.title.number,
        "chapter_number": chapter.number,
        "source_as_of": source_as_of,
        "section_count": section_count,
        "authority": authority,
        "source_note": source_note,
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    body = _chapter_body(authority, source_note)
    inventory.append(
        SourceInventoryItem(
            citation_path=chapter.citation_path,
            source_url=chapter.source_url,
            source_path=snapshot.source_key,
            source_format=PENNSYLVANIA_CODE_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=chapter.citation_path,
            parent_citation_path=chapter.title.citation_path,
            citation_label=f"{chapter.title.number} Pa. Code Chapter {chapter.number}",
            heading=chapter.heading,
            body=body,
            version=version,
            source_url=chapter.source_url,
            source_path=snapshot.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=2,
            ordinal=chapter.ordinal,
            kind="chapter",
            legal_identifier=f"{chapter.title.number} Pa. Code Chapter {chapter.number}",
            identifiers={
                "pennsylvania:code_title": chapter.title.number,
                "pennsylvania:code_chapter": chapter.number,
            },
            metadata=metadata,
        )
    )


def _append_section(
    section: _Section,
    *,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> None:
    metadata: dict[str, object] = {
        "kind": "section",
        "title_number": section.chapter.title.number,
        "chapter_number": section.chapter.number,
        "section_number": section.number,
        "references_to": list(section.references_to),
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    inventory.append(
        SourceInventoryItem(
            citation_path=section.citation_path,
            source_url=section.source_url,
            source_path=snapshot.source_key,
            source_format=PENNSYLVANIA_CODE_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=section.citation_path,
            parent_citation_path=section.chapter.citation_path,
            citation_label=section.legal_identifier,
            heading=section.heading,
            body=section.body,
            version=version,
            source_url=section.source_url,
            source_path=snapshot.source_key,
            source_id=section.number,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=3,
            ordinal=section.ordinal,
            kind="section",
            legal_identifier=section.legal_identifier,
            identifiers={
                "pennsylvania:code_title": section.chapter.title.number,
                "pennsylvania:code_chapter": section.chapter.number,
                "pennsylvania:code_section": section.number,
            },
            metadata=metadata,
        )
    )


def _root_record(
    *,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    selected_title_count: int,
    total_title_count: int,
    effective_through: str | None,
) -> ProvisionRecord:
    metadata: dict[str, object] = {
        "selected_title_count": selected_title_count,
        "total_title_count": total_title_count,
        "effective_through": effective_through,
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    return _record(
        citation_path="us-pa/regulation",
        citation_label="Pennsylvania Code",
        heading="Pennsylvania Code",
        body=None,
        version=version,
        source_url=PENNSYLVANIA_CODE_HOME_URL,
        source_path=source_path,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=0,
        ordinal=0,
        kind="collection",
        legal_identifier="Pennsylvania Code",
        identifiers={"state:code": "Pa. Code"},
        metadata=metadata,
    )


def _record(
    *,
    citation_path: str,
    heading: str | None,
    body: str | None,
    version: str,
    source_url: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    level: int,
    ordinal: int | None,
    kind: str,
    parent_citation_path: str | None = None,
    citation_label: str | None = None,
    source_id: str | None = None,
    legal_identifier: str | None = None,
    identifiers: dict[str, str] | None = None,
    metadata: dict[str, object] | None = None,
) -> ProvisionRecord:
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction="us-pa",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        citation_label=citation_label,
        heading=heading,
        body=body,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=source_id,
        source_format=PENNSYLVANIA_CODE_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_citation_path,
        parent_id=(
            deterministic_provision_id(parent_citation_path) if parent_citation_path else None
        ),
        level=level,
        ordinal=ordinal,
        kind=kind,
        legal_identifier=legal_identifier,
        identifiers=identifiers,
        metadata=metadata,
    )


def _chapter_body(authority: str | None, source_note: str | None) -> str | None:
    parts: list[str] = []
    if authority:
        parts.append(f"Authority: {authority}")
    if source_note:
        parts.append(f"Source: {source_note}")
    return "\n\n".join(parts) or None


def _references_to(text: str) -> tuple[str, ...]:
    refs: list[str] = []
    for match in _SECTION_REF_RE.finditer(text):
        refs.append(
            f"us-pa/regulation/title-{_path_token(match.group('title'))}/"
            f"section-{_path_token(match.group('section'))}"
        )
    return _unique(refs)


def _is_reserved_chapter_name(name: str) -> bool:
    normalized = _clean_text(name).strip("[]() ").lower()
    return normalized == "reserved"


def _section_number_from_meta(meta: str) -> str | None:
    for part in meta.split(";"):
        if part.startswith("s") and len(part) > 1:
            return _clean_text(part[1:])
    return None


def _join_title_relative(title: _Title, href: str) -> str:
    cleaned = href.split("?", 1)[0]
    if cleaned.startswith("/"):
        if cleaned.startswith("/secure/pacode/data/"):
            return "/" + cleaned.removeprefix("/secure/pacode/data/").lstrip("/")
        return cleaned
    title_dir = title.relative_file.rsplit("/", 1)[0]
    return f"{title_dir}/{cleaned}"


def _secure_url(relative_file: str) -> str:
    return urljoin(
        PENNSYLVANIA_CODE_BASE_URL,
        f"/secure/pacode/data/{relative_file.lstrip('/')}",
    )


def _display_url(title_number: str, relative_file: str) -> str:
    quoted_file = quote(f"/secure/pacode/data/{relative_file.lstrip('/')}", safe="/")
    return (
        f"{PENNSYLVANIA_CODE_BASE_URL}/Display/pacode?"
        f"titleNumber={quote(title_number)}&file={quoted_file}&searchunitkeywords=&operator=OR&title=null"
    )


def _source_key(run_id: str, relative_name: str) -> str:
    return f"sources/us-pa/regulation/{run_id}/{relative_name}"


def _path_token(value: str) -> str:
    token = _clean_text(value).lower().replace(".", "-")
    token = re.sub(r"[^a-z0-9]+", "-", token).strip("-")
    return safe_segment(token or "unknown")


def _same_token(left: str, right: str) -> bool:
    return _path_token(left) == _path_token(right)


def _effective_through(content: bytes) -> str | None:
    text = _clean_text(BeautifulSoup(content, "html.parser").get_text(" ", strip=True))
    match = re.search(r"changes effective through\s+(?P<value>.+?\([^)]+\)\.)", text, re.I)
    return _clean_text(match.group("value")) if match else None


def _html_fragment_text(value: str) -> str:
    return _clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def _clean_body(value: str) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_text(value: str) -> str:
    text = value.replace("\xa0", " ").replace("\ufffd", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    return text.strip()


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _date_text(value: date | str | None, fallback: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value or fallback


def _progress(stream: TextIO | None, message: str) -> None:
    if stream is not None:
        print(message, file=stream, flush=True)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


if __name__ == "__main__":  # pragma: no cover
    from axiom_corpus.corpus.cli import main

    raise SystemExit(main(sys.argv[1:]))
