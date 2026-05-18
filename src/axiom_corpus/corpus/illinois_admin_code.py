"""Illinois Administrative Code source-first adapter."""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, TextIO, overload
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

ILLINOIS_ADMIN_CODE_BASE_URL = "https://www.ilga.gov/ftp/JCAR/AdminCode/"
ILLINOIS_ADMIN_CODE_INDEX_URL = urljoin(ILLINOIS_ADMIN_CODE_BASE_URL, "titles.html")
ILLINOIS_ADMIN_CODE_SOURCE_FORMAT = "illinois-admin-code-html"
ILLINOIS_ADMIN_CODE_USER_AGENT = "axiom-corpus/0.1 (max@axiom-foundation.org)"
ILLINOIS_ADMIN_CODE_SOURCE_NOTE = (
    "Illinois General Assembly site maintained and updated weekly, but it is not the "
    "certified official text; certified copies are available from the Secretary of "
    "State's Index Department."
)

_SOURCE_PREFIX = "illinois-admin-code-html"
_TITLE_RE = re.compile(r"TITLE\s*:?\s*(?P<number>\d+)\s*:\s*(?P<heading>.+)", re.I | re.S)
_SUBTITLE_RE = re.compile(
    r"SUBTITLE\s+(?P<number>[A-Z0-9IVXLCDM.-]+)\s*:\s*(?P<heading>.+)",
    re.I | re.S,
)
_CHAPTER_RE = re.compile(r"CHAPTER\s+(?P<number>[A-Z0-9IVXLCDM.-]+)\s*:\s*(?P<heading>.+)", re.I | re.S)
_SUBCHAPTER_RE = re.compile(
    r"SUBCHAPTER\s+(?P<number>[A-Z0-9IVXLCDM.-]+)\s*:\s*(?P<heading>.+)",
    re.I | re.S,
)
_PART_RE = re.compile(r"PART\s+(?P<number>[A-Z0-9.-]+)\s*(?P<heading>.*)", re.I | re.S)
_SECTION_NUMBER_PATTERN = (
    r"[A-Z0-9]+(?:\.(?:\d+[A-Z]?|[A-Z]+(?:\s+[A-Z0-9]+)?))?"
)
_BARE_SECTION_NUMBER_PATTERN = r"[A-Z0-9]+\.(?:\d+[A-Z]?|[A-Z]+(?:\s+[A-Z0-9]+)?)"
_SECTION_RE = re.compile(
    rf"SECTIONS?\s+(?P<number>{_SECTION_NUMBER_PATTERN})\s*(?P<heading>.*)",
    re.I | re.S,
)
_SECTION_META_RE = re.compile(
    rf"Sections?\s+(?P<number>{_SECTION_NUMBER_PATTERN})\s*(?P<heading>.*)",
    re.I | re.S,
)
_BARE_SECTION_RE = re.compile(
    rf"(?P<number>{_BARE_SECTION_NUMBER_PATTERN})\s*(?P<heading>.*)",
    re.I | re.S,
)
_LISTING_ENTRY_RE = re.compile(
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2}\s+[AP]M)\s+"
    r"(?P<size>\d+|&lt;dir&gt;|<dir>)\s+"
    r'<A\s+HREF="(?P<href>[^"]+)">(?P<name>[^<]+)</A>',
    re.I,
)
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


@dataclass(frozen=True)
class IllinoisAdminCodeExtractReport:
    """Result from an Illinois Administrative Code extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    title_count: int
    subtitle_count: int
    chapter_count: int
    subchapter_count: int
    part_count: int
    section_count: int
    appendix_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]
    skipped_source_count: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RecordedSource:
    source_url: str
    source_path: str
    artifact_path: Path
    sha256: str


@dataclass(frozen=True)
class _TitleEntry:
    number: str
    heading: str
    ordinal: int

    @property
    def display_number(self) -> str:
        return str(int(self.number))

    @property
    def citation_path(self) -> str:
        return f"us-il/regulation/title-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return urljoin(ILLINOIS_ADMIN_CODE_BASE_URL, f"{self.number}/")


@dataclass(frozen=True)
class _DirectoryEntry:
    title: str
    name: str
    href: str
    last_modified: str | None
    size: int | None
    ordinal: int
    is_dir: bool = False

    @property
    def relative_name(self) -> str:
        return f"{_SOURCE_PREFIX}/{self.title}/{self.name}"

    @property
    def source_url(self) -> str:
        return urljoin(ILLINOIS_ADMIN_CODE_BASE_URL, f"{self.title}/{quote(self.name)}")


@dataclass(frozen=True)
class _Hierarchy:
    title_number: str
    title_heading: str
    subtitle_number: str | None
    subtitle_heading: str | None
    chapter_number: str | None
    chapter_heading: str | None
    subchapter_number: str | None
    subchapter_heading: str | None
    part_number: str
    part_heading: str
    section_number: str
    section_heading: str
    heading_lines: tuple[str, ...]

    @property
    def title_path(self) -> str:
        return f"us-il/regulation/title-{_path_token(self.title_number)}"

    @property
    def subtitle_path(self) -> str | None:
        if not self.subtitle_number:
            return None
        return f"{self.title_path}/subtitle-{_path_token(self.subtitle_number)}"

    @property
    def chapter_path(self) -> str | None:
        if not self.chapter_number:
            return None
        return f"{self.subtitle_path or self.title_path}/chapter-{_path_token(self.chapter_number)}"

    @property
    def subchapter_path(self) -> str | None:
        if not self.subchapter_number or not self.chapter_path:
            return None
        return f"{self.chapter_path}/subchapter-{_path_token(self.subchapter_number)}"

    @property
    def part_parent_path(self) -> str:
        return self.subchapter_path or self.chapter_path or self.subtitle_path or self.title_path

    @property
    def part_path(self) -> str:
        return f"{self.part_parent_path}/part-{_path_token(self.part_number)}"

    @property
    def section_path(self) -> str:
        return f"{self.part_path}/{_section_path_segment(self.section_number)}"

    @property
    def legal_identifier(self) -> str:
        return f"{int(self.title_number)} Ill. Adm. Code {self.section_number}"


@dataclass(frozen=True)
class _PageProvision:
    entry: _DirectoryEntry
    source: _RecordedSource
    hierarchy: _Hierarchy
    body: str | None
    kind: str
    source_notes: tuple[str, ...]
    references_to_labels: tuple[str, ...]
    source_entries: tuple[_DirectoryEntry, ...] = ()


@dataclass(frozen=True)
class _PageSnapshotResult:
    page: _PageProvision | None
    source_paths: tuple[Path, ...]
    error: str | None = None


@dataclass(frozen=True)
class _ContainerSource:
    source: _RecordedSource
    source_as_of: str | None
    title: _TitleEntry | None = None
    hierarchy: _Hierarchy | None = None
    entry: _DirectoryEntry | None = None


def illinois_admin_code_run_id(
    version: str,
    *,
    only_title: str | None = None,
    limit: int | None = None,
) -> str:
    """Return a scoped Illinois Administrative Code run id."""

    parts = [version]
    if only_title:
        parts.append(f"title-{_path_token(_normal_title_number(only_title))}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def extract_illinois_admin_code(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | None = None,
    limit: int | None = None,
    workers: int = 8,
    progress_stream: TextIO | None = None,
) -> IllinoisAdminCodeExtractReport:
    """Snapshot Illinois Administrative Code HTML and extract provisions."""

    jurisdiction = "us-il"
    document_class = DocumentClass.REGULATION.value
    only_title_number = _normal_title_number(only_title) if only_title else None
    run_id = illinois_admin_code_run_id(version, only_title=only_title_number, limit=limit)
    source_root = Path(source_dir) if source_dir is not None else None
    download_root = Path(download_dir) if download_dir is not None and source_root is None else None

    index_source = _snapshot_source(
        store,
        run_id=run_id,
        relative_name=f"{_SOURCE_PREFIX}/titles.html",
        url=ILLINOIS_ADMIN_CODE_INDEX_URL,
        source_root=source_root,
        download_root=download_root,
    )
    source_paths: list[Path] = [index_source.artifact_path]
    titles = _parse_titles(index_source.artifact_path.read_bytes())
    if only_title_number is not None:
        titles = tuple(title for title in titles if title.number == only_title_number)
    if not titles:
        raise ValueError(f"no Illinois Administrative Code titles selected: {only_title!r}")

    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    inventory: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    errors: list[str] = []
    skipped_source_count = 0
    title_sources: dict[str, _ContainerSource] = {}
    title_heading_by_number = {title.number: title.heading for title in titles}
    page_entries: list[_DirectoryEntry] = []

    root_path = "us-il/regulation"
    root_metadata: dict[str, Any] = {
        "kind": "collection",
        "source_note": ILLINOIS_ADMIN_CODE_SOURCE_NOTE,
        "source_as_of": source_as_of_text,
        "title_count": len(titles),
    }
    inventory.append(
        SourceInventoryItem(
            citation_path=root_path,
            source_url=ILLINOIS_ADMIN_CODE_INDEX_URL,
            source_path=index_source.source_path,
            source_format=ILLINOIS_ADMIN_CODE_SOURCE_FORMAT,
            sha256=index_source.sha256,
            metadata=root_metadata,
        )
    )
    records.append(
        _record(
            citation_path=root_path,
            heading="Illinois Administrative Code",
            body=None,
            version=run_id,
            source=index_source,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            level=0,
            ordinal=0,
            kind="collection",
            metadata=root_metadata,
        )
    )

    for title in titles:
        _progress(progress_stream, f"illinois-admin-code title {title.number}")
        listing_relative = f"{_SOURCE_PREFIX}/{title.number}/index.html"
        listing_source = _snapshot_source(
            store,
            run_id=run_id,
            relative_name=listing_relative,
            url=title.source_url,
            source_root=source_root,
            download_root=download_root,
        )
        source_paths.append(listing_source.artifact_path)
        title_sources[title.number] = _ContainerSource(
            source=listing_source,
            source_as_of=source_as_of_text,
            title=title,
        )
        entries = _parse_title_listing(listing_source.artifact_path.read_bytes(), title=title.number)
        html_entries = tuple(entry for entry in entries if not entry.is_dir and entry.name.endswith(".html"))
        page_entries.extend(html_entries)

    if limit is not None:
        page_entries = page_entries[:limit]

    page_provisions: list[_PageProvision] = []
    if workers <= 1:
        for entry in page_entries:
            result = _snapshot_and_parse_page_result(
                store,
                run_id=run_id,
                entry=entry,
                source_root=source_root,
                download_root=download_root,
                title_heading_by_number=title_heading_by_number,
            )
            source_paths.extend(result.source_paths)
            if result.page is not None:
                page_provisions.append(result.page)
            elif result.error:
                skipped_source_count += 1
                errors.append(result.error)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for result in executor.map(
                lambda selected: _snapshot_and_parse_page_result(
                    store,
                    run_id=run_id,
                    entry=selected,
                    source_root=source_root,
                    download_root=download_root,
                    title_heading_by_number=title_heading_by_number,
                ),
                page_entries,
            ):
                source_paths.extend(result.source_paths)
                if result.page is not None:
                    page_provisions.append(result.page)
                elif result.error:
                    skipped_source_count += 1
                    errors.append(result.error)

    page_provisions = list(_aggregate_page_provisions(page_provisions))
    container_sources: dict[str, _ContainerSource] = dict(title_sources)
    section_count = 0
    appendix_count = 0
    for page in page_provisions:
        hierarchy = page.hierarchy
        _set_container_source(
            container_sources,
            hierarchy.subtitle_path,
            _ContainerSource(
                source=page.source,
                source_as_of=page.entry.last_modified,
                hierarchy=hierarchy,
                entry=page.entry,
            ),
        )
        _set_container_source(
            container_sources,
            hierarchy.chapter_path,
            _ContainerSource(
                source=page.source,
                source_as_of=page.entry.last_modified,
                hierarchy=hierarchy,
                entry=page.entry,
            ),
        )
        _set_container_source(
            container_sources,
            hierarchy.subchapter_path,
            _ContainerSource(
                source=page.source,
                source_as_of=page.entry.last_modified,
                hierarchy=hierarchy,
                entry=page.entry,
            ),
        )
        _set_container_source(
            container_sources,
            hierarchy.part_path,
            _ContainerSource(
                source=page.source,
                source_as_of=page.entry.last_modified,
                hierarchy=hierarchy,
                entry=page.entry,
            ),
        )
        if page.kind == "section":
            section_count += 1
        else:
            appendix_count += 1

    for title in titles:
        source = title_sources[title.number]
        title_metadata: dict[str, Any] = {
            "kind": "title",
            "title_number": title.display_number,
            "title_number_padded": title.number,
            "source_note": ILLINOIS_ADMIN_CODE_SOURCE_NOTE,
        }
        _append_inventory_and_record(
            inventory=inventory,
            records=records,
            citation_path=title.citation_path,
            parent_citation_path=root_path,
            heading=f"Title {title.display_number}. {title.heading}",
            body=None,
            version=run_id,
            source=source.source,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            level=1,
            ordinal=title.ordinal,
            kind="title",
            legal_identifier=f"{title.display_number} Ill. Adm. Code",
            identifiers={"illinois_admin_code": f"{title.display_number} Ill. Adm. Code"},
            metadata=title_metadata,
        )

    chapter_paths = sorted(
        path
        for path in container_sources
        if "/chapter-" in path and "/subchapter-" not in path and "/part-" not in path
    )
    subtitle_paths = sorted(
        path
        for path in container_sources
        if "/subtitle-" in path and "/chapter-" not in path and "/part-" not in path
    )
    subchapter_paths = sorted(
        path for path in container_sources if "/subchapter-" in path and "/part-" not in path
    )
    part_paths = sorted(path for path in container_sources if "/part-" in path)
    for ordinal, path in enumerate(subtitle_paths, 1):
        source = container_sources[path]
        if not source.hierarchy:
            continue
        hierarchy = source.hierarchy
        if not hierarchy.subtitle_number:
            continue
        subtitle_metadata = _container_metadata("subtitle", hierarchy, source.entry)
        _append_inventory_and_record(
            inventory=inventory,
            records=records,
            citation_path=path,
            parent_citation_path=hierarchy.title_path,
            heading=_container_heading(
                "Subtitle",
                hierarchy.subtitle_number,
                hierarchy.subtitle_heading,
            ),
            body=None,
            version=run_id,
            source=source.source,
            source_as_of=source.source_as_of or source_as_of_text,
            expression_date=expression_date_text,
            level=2,
            ordinal=ordinal,
            kind="subtitle",
            legal_identifier=(
                f"{int(hierarchy.title_number)} Ill. Adm. Code Subtitle "
                f"{hierarchy.subtitle_number}"
            ),
            identifiers=None,
            metadata=subtitle_metadata,
        )
    for ordinal, path in enumerate(chapter_paths, 1):
        source = container_sources[path]
        if not source.hierarchy:
            continue
        hierarchy = source.hierarchy
        if not hierarchy.chapter_number:
            continue
        chapter_metadata = _container_metadata("chapter", hierarchy, source.entry)
        _append_inventory_and_record(
            inventory=inventory,
            records=records,
            citation_path=path,
            parent_citation_path=hierarchy.title_path,
            heading=_container_heading("Chapter", hierarchy.chapter_number, hierarchy.chapter_heading),
            body=None,
            version=run_id,
            source=source.source,
            source_as_of=source.source_as_of or source_as_of_text,
            expression_date=expression_date_text,
            level=3,
            ordinal=ordinal,
            kind="chapter",
            legal_identifier=(
                f"{int(hierarchy.title_number)} Ill. Adm. Code Chapter {hierarchy.chapter_number}"
            ),
            identifiers=None,
            metadata=chapter_metadata,
        )
    for ordinal, path in enumerate(subchapter_paths, 1):
        source = container_sources[path]
        if not source.hierarchy:
            continue
        hierarchy = source.hierarchy
        if not hierarchy.subchapter_number:
            continue
        subchapter_metadata = _container_metadata("subchapter", hierarchy, source.entry)
        _append_inventory_and_record(
            inventory=inventory,
            records=records,
            citation_path=path,
            parent_citation_path=hierarchy.chapter_path,
            heading=_container_heading(
                "Subchapter",
                hierarchy.subchapter_number,
                hierarchy.subchapter_heading,
            ),
            body=None,
            version=run_id,
            source=source.source,
            source_as_of=source.source_as_of or source_as_of_text,
            expression_date=expression_date_text,
            level=4,
            ordinal=ordinal,
            kind="subchapter",
            legal_identifier=(
                f"{int(hierarchy.title_number)} Ill. Adm. Code Subchapter "
                f"{hierarchy.subchapter_number}"
            ),
            identifiers=None,
            metadata=subchapter_metadata,
        )
    for ordinal, path in enumerate(part_paths, 1):
        source = container_sources[path]
        if not source.hierarchy:
            continue
        hierarchy = source.hierarchy
        part_metadata = _container_metadata("part", hierarchy, source.entry)
        _append_inventory_and_record(
            inventory=inventory,
            records=records,
            citation_path=path,
            parent_citation_path=hierarchy.part_parent_path,
            heading=_container_heading("Part", hierarchy.part_number, hierarchy.part_heading),
            body=None,
            version=run_id,
            source=source.source,
            source_as_of=source.source_as_of or source_as_of_text,
            expression_date=expression_date_text,
            level=5,
            ordinal=ordinal,
            kind="part",
            legal_identifier=f"{int(hierarchy.title_number)} Ill. Adm. Code Part {hierarchy.part_number}",
            identifiers={"illinois_admin_code": f"{int(hierarchy.title_number)} Ill. Adm. Code {hierarchy.part_number}"},
            metadata=part_metadata,
        )
    for ordinal, page in enumerate(page_provisions, 1):
        hierarchy = page.hierarchy
        page_source_entries = page.source_entries or (page.entry,)
        page_metadata: dict[str, Any] = {
            "kind": page.kind,
            "title_number": str(int(hierarchy.title_number)),
            "title_number_padded": hierarchy.title_number,
            "title_heading": hierarchy.title_heading,
            "part_number": hierarchy.part_number,
            "part_heading": hierarchy.part_heading,
            "section_number": hierarchy.section_number,
            "source_file": page_source_entries[0].name,
            "source_note": ILLINOIS_ADMIN_CODE_SOURCE_NOTE,
            "heading_lines": list(hierarchy.heading_lines),
        }
        if len(page_source_entries) > 1:
            page_metadata["source_files"] = [entry.name for entry in page_source_entries]
            page_metadata["source_file_count"] = len(page_source_entries)
        if hierarchy.chapter_number:
            page_metadata["chapter_number"] = hierarchy.chapter_number
        if hierarchy.chapter_heading is not None:
            page_metadata["chapter_heading"] = hierarchy.chapter_heading
        if hierarchy.subtitle_number:
            page_metadata["subtitle_number"] = hierarchy.subtitle_number
        if hierarchy.subtitle_heading is not None:
            page_metadata["subtitle_heading"] = hierarchy.subtitle_heading
        if hierarchy.subchapter_number:
            page_metadata["subchapter_number"] = hierarchy.subchapter_number
        if hierarchy.subchapter_heading is not None:
            page_metadata["subchapter_heading"] = hierarchy.subchapter_heading
        source_sizes = [entry.size for entry in page_source_entries if entry.size is not None]
        if source_sizes:
            page_metadata["source_size_bytes"] = sum(source_sizes)
        source_dates = [
            entry.last_modified for entry in page_source_entries if entry.last_modified is not None
        ]
        if source_dates:
            page_metadata["source_last_modified"] = max(source_dates)
        if page.source_notes:
            page_metadata["source_notes"] = list(page.source_notes)
        if page.references_to_labels:
            page_metadata["references_to_labels"] = list(page.references_to_labels)
        _append_inventory_and_record(
            inventory=inventory,
            records=records,
            citation_path=hierarchy.section_path,
            parent_citation_path=hierarchy.part_path,
            heading=f"{hierarchy.legal_identifier}. {hierarchy.section_heading}".strip(),
            body=page.body,
            version=run_id,
            source=page.source,
            source_as_of=page.entry.last_modified or source_as_of_text,
            expression_date=expression_date_text,
            level=6,
            ordinal=ordinal,
            kind=page.kind,
            legal_identifier=hierarchy.legal_identifier,
            identifiers={"illinois_admin_code": hierarchy.legal_identifier},
            metadata=page_metadata,
        )

    inventory_path = store.inventory_path(jurisdiction, DocumentClass.REGULATION, run_id)
    provisions_path = store.provisions_path(jurisdiction, DocumentClass.REGULATION, run_id)
    coverage_path = store.coverage_path(jurisdiction, DocumentClass.REGULATION, run_id)
    store.write_inventory(inventory_path, inventory)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
    )
    store.write_json(coverage_path, coverage.to_mapping())

    return IllinoisAdminCodeExtractReport(
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
        title_count=len(titles),
        subtitle_count=len(subtitle_paths),
        chapter_count=len(chapter_paths),
        subchapter_count=len(subchapter_paths),
        part_count=len(part_paths),
        section_count=section_count,
        appendix_count=appendix_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        skipped_source_count=skipped_source_count,
        errors=tuple(errors),
    )


def _snapshot_and_parse_page_result(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    entry: _DirectoryEntry,
    source_root: Path | None,
    download_root: Path | None,
    title_heading_by_number: dict[str, str],
) -> _PageSnapshotResult:
    try:
        page, source_paths = _snapshot_and_parse_page(
            store,
            run_id=run_id,
            entry=entry,
            source_root=source_root,
            download_root=download_root,
            title_heading_by_number=title_heading_by_number,
        )
    except (OSError, ValueError, requests.RequestException) as exc:
        return _PageSnapshotResult(page=None, source_paths=(), error=f"{entry.name}: {exc}")
    return _PageSnapshotResult(page=page, source_paths=source_paths)


def _snapshot_and_parse_page(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    entry: _DirectoryEntry,
    source_root: Path | None,
    download_root: Path | None,
    title_heading_by_number: dict[str, str],
) -> tuple[_PageProvision, tuple[Path, ...]]:
    source_paths: list[Path] = []
    source = _snapshot_source(
        store,
        run_id=run_id,
        relative_name=entry.relative_name,
        url=entry.source_url,
        source_root=source_root,
        download_root=download_root,
    )
    source_paths.append(source.artifact_path)
    data = source.artifact_path.read_bytes()
    for asset_relative, asset_url in _linked_asset_sources(data, entry=entry):
        if source_root is not None:
            asset_source = _snapshot_source(
                store,
                run_id=run_id,
                relative_name=asset_relative,
                url=asset_url,
                source_root=source_root,
                download_root=download_root,
                missing_ok=True,
            )
        else:
            asset_source = _snapshot_source(
                store,
                run_id=run_id,
                relative_name=asset_relative,
                url=asset_url,
                source_root=source_root,
                download_root=download_root,
            )
        if asset_source is not None:
            source_paths.append(asset_source.artifact_path)
    return (
        _parse_page(
            data,
            entry=entry,
            source=source,
            title_heading_by_number=title_heading_by_number,
        ),
        tuple(source_paths),
    )


@overload
def _snapshot_source(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    relative_name: str,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
    missing_ok: Literal[False] = False,
) -> _RecordedSource: ...


@overload
def _snapshot_source(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    relative_name: str,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
    missing_ok: Literal[True],
) -> _RecordedSource | None: ...


def _snapshot_source(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    relative_name: str,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
    missing_ok: bool = False,
) -> _RecordedSource | None:
    data: bytes
    if source_root is not None:
        path = _source_file_path(source_root, relative_name)
        if not path.exists():
            if missing_ok:
                return None
            raise FileNotFoundError(path)
        data = path.read_bytes()
    elif download_root is not None:
        path = download_root / relative_name
        if path.exists():
            data = path.read_bytes()
        else:
            data = _get_bytes(url)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    else:
        data = _get_bytes(url)
    artifact_path = store.source_path("us-il", DocumentClass.REGULATION, run_id, relative_name)
    sha = store.write_bytes(artifact_path, data)
    return _RecordedSource(
        source_url=url,
        source_path=f"sources/us-il/regulation/{run_id}/{relative_name}",
        artifact_path=artifact_path,
        sha256=sha,
    )


def _source_file_path(source_root: Path, relative_name: str) -> Path:
    path = source_root / relative_name
    if path.exists():
        return path
    if relative_name.startswith(f"{_SOURCE_PREFIX}/"):
        return source_root / relative_name.removeprefix(f"{_SOURCE_PREFIX}/")
    return path


def _get_bytes(url: str, *, attempts: int = 4) -> bytes:
    last_exc: requests.RequestException | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": ILLINOIS_ADMIN_CODE_USER_AGENT},
                timeout=(15, 90),
            )
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == attempts - 1:
                break
            time.sleep(0.5 * (2**attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"failed to fetch {url}")


def _parse_titles(data: bytes) -> tuple[_TitleEntry, ...]:
    soup = BeautifulSoup(data, "html.parser")
    titles: list[_TitleEntry] = []
    for link in soup.find_all("a"):
        if not isinstance(link, Tag):
            continue
        href = str(link.get("href") or "")
        match = re.match(r"(?P<number>\d{3})/\d{3}parts\.html$", href)
        if not match:
            continue
        title_text = _clean_text(link.get_text(" "))
        title_match = _TITLE_RE.search(title_text)
        if not title_match:
            continue
        titles.append(
            _TitleEntry(
                number=match.group("number"),
                heading=_clean_text(title_match.group("heading")),
                ordinal=len(titles) + 1,
            )
        )
    return tuple(titles)


def _parse_title_listing(data: bytes, *, title: str) -> tuple[_DirectoryEntry, ...]:
    text = data.decode("utf-8", errors="replace")
    entries: list[_DirectoryEntry] = []
    for match in _LISTING_ENTRY_RE.finditer(text):
        name = match.group("name")
        if name == "[To Parent Directory]":
            continue
        size_text = match.group("size")
        is_dir = "<dir>" in size_text.lower() or "&lt;dir&gt;" in size_text.lower()
        entries.append(
            _DirectoryEntry(
                title=title,
                name=name,
                href=match.group("href"),
                last_modified=_listing_date(match.group("date"), match.group("time")),
                size=None if is_dir else int(size_text),
                ordinal=len(entries) + 1,
                is_dir=is_dir,
            )
        )
    return tuple(entries)


def _parse_page(
    data: bytes,
    *,
    entry: _DirectoryEntry,
    source: _RecordedSource,
    title_heading_by_number: dict[str, str],
) -> _PageProvision:
    soup = BeautifulSoup(data, "html.parser")
    hierarchy = _parse_hierarchy(
        soup,
        fallback_title=entry.title,
        fallback_title_heading=title_heading_by_number.get(entry.title, ""),
    )
    body = _body_text(soup)
    source_notes = _source_notes(soup)
    references_to_labels = _references_to_labels(body or "")
    return _PageProvision(
        entry=entry,
        source=source,
        hierarchy=hierarchy,
        body=body,
        kind=_page_kind(hierarchy.section_number),
        source_notes=source_notes,
        references_to_labels=references_to_labels,
    )


def _aggregate_page_provisions(
    pages: Iterable[_PageProvision],
) -> tuple[_PageProvision, ...]:
    grouped: dict[str, list[_PageProvision]] = {}
    for page in pages:
        grouped.setdefault(page.hierarchy.section_path, []).append(page)
    aggregated: list[_PageProvision] = []
    for group in grouped.values():
        if len(group) == 1:
            aggregated.append(group[0])
            continue
        first = group[0]
        body = _join_lines(page.body or "" for page in group)
        aggregated.append(
            _PageProvision(
                entry=first.entry,
                source=first.source,
                hierarchy=first.hierarchy,
                body=body,
                kind=first.kind,
                source_notes=_unique(
                    note for page in group for note in page.source_notes
                ),
                references_to_labels=_unique(
                    reference
                    for page in group
                    for reference in page.references_to_labels
                ),
                source_entries=tuple(page.entry for page in group),
            )
        )
    return tuple(aggregated)


def _parse_hierarchy(
    soup: BeautifulSoup,
    *,
    fallback_title: str,
    fallback_title_heading: str,
) -> _Hierarchy:
    heading_lines = _heading_lines(soup)
    fields = _heading_fields(heading_lines)
    meta_section = _meta_section(soup)
    section_text = fields.get("section") or meta_section
    title_text = fields.get("title")
    part_text = fields.get("part")
    if not section_text:
        raise ValueError(f"missing Illinois Administrative Code heading: {heading_lines!r}")
    section_match = (
        _SECTION_RE.search(section_text)
        or _SECTION_META_RE.search(section_text)
        or _BARE_SECTION_RE.search(section_text)
    )
    if not section_match:
        raise ValueError(f"unparseable Illinois Administrative Code heading: {heading_lines!r}")
    title_number = _normal_title_number(fallback_title)
    title_heading = fallback_title_heading
    if title_text:
        title_match = _TITLE_RE.search(title_text)
        if not title_match:
            raise ValueError(f"unparseable Illinois Administrative Code title: {heading_lines!r}")
        title_number = _normal_title_number(title_match.group("number") or fallback_title)
        title_heading = _clean_text(title_match.group("heading"))
    section_number = _clean_text(section_match.group("number"))
    part_number = section_number.split(".", 1)[0]
    part_heading = ""
    if part_text:
        part_match = _PART_RE.search(part_text)
        if not part_match:
            raise ValueError(f"unparseable Illinois Administrative Code part: {heading_lines!r}")
        part_number = _clean_text(part_match.group("number"))
        part_heading = _clean_text(part_match.group("heading"))
    subtitle_number: str | None = None
    subtitle_heading: str | None = None
    subtitle_text = fields.get("subtitle")
    if subtitle_text:
        subtitle_match = _SUBTITLE_RE.search(subtitle_text)
        if subtitle_match:
            subtitle_number = _clean_text(subtitle_match.group("number")).upper()
            subtitle_heading = _clean_text(subtitle_match.group("heading"))
    chapter_number: str | None = None
    chapter_heading: str | None = None
    chapter_text = fields.get("chapter")
    if chapter_text:
        chapter_match = _CHAPTER_RE.search(chapter_text)
        if chapter_match:
            chapter_number = _clean_text(chapter_match.group("number")).upper()
            chapter_heading = _clean_text(chapter_match.group("heading"))
    subchapter_number: str | None = None
    subchapter_heading: str | None = None
    subchapter_text = fields.get("subchapter")
    if subchapter_text:
        subchapter_match = _SUBCHAPTER_RE.search(subchapter_text)
        if subchapter_match:
            subchapter_number = _clean_text(subchapter_match.group("number")).lower()
            subchapter_heading = _clean_text(subchapter_match.group("heading"))
    return _Hierarchy(
        title_number=title_number,
        title_heading=title_heading,
        subtitle_number=subtitle_number,
        subtitle_heading=subtitle_heading,
        chapter_number=chapter_number,
        chapter_heading=chapter_heading,
        subchapter_number=subchapter_number,
        subchapter_heading=subchapter_heading,
        part_number=part_number,
        part_heading=part_heading,
        section_number=section_number,
        section_heading=_clean_text(section_match.group("heading")),
        heading_lines=heading_lines,
    )


def _heading_lines(soup: BeautifulSoup) -> tuple[str, ...]:
    lines = []
    for heading in soup.find_all("div", class_="heading"):
        if not isinstance(heading, Tag):
            continue
        for raw_line in heading.get_text("\n").splitlines():
            line = _clean_text(raw_line)
            if line and line.upper() != "ADMINISTRATIVE CODE":
                lines.append(line)
    return tuple(lines)


def _heading_fields(lines: tuple[str, ...]) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    prefix_by_key = {
        "title": "TITLE ",
        "subtitle": "SUBTITLE ",
        "chapter": "CHAPTER ",
        "subchapter": "SUBCHAPTER ",
        "part": "PART ",
        "section": "SECTION ",
    }
    for line in lines:
        key = _heading_key(line)
        if key is not None:
            fields[key] = line
            current_key = key
        elif current_key is not None:
            prefix = prefix_by_key[current_key]
            fields[current_key] = f"{fields[current_key]} {line}"
            if current_key == "part" and not fields[current_key].upper().startswith(prefix):
                fields[current_key] = f"PART {fields[current_key]}"
    return fields


def _heading_key(line: str) -> str | None:
    if _SUBCHAPTER_RE.search(line):
        return "subchapter"
    if _SUBTITLE_RE.search(line):
        return "subtitle"
    if _CHAPTER_RE.search(line):
        return "chapter"
    if _TITLE_RE.search(line):
        return "title"
    if _PART_RE.search(line):
        return "part"
    if _SECTION_RE.search(line) or _BARE_SECTION_RE.search(line):
        return "section"
    return None


def _meta_section(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": re.compile("^sectionname$", re.I)})
    if not isinstance(meta, Tag):
        return None
    content = meta.get("content")
    if content is None:
        return None
    return _clean_text(str(content))


def _body_text(soup: BeautifulSoup) -> str | None:
    content = _content_container(soup)
    if content is None:
        return None
    lines = _block_lines(content)
    return _join_lines(lines)


def _content_container(soup: BeautifulSoup) -> Tag | None:
    hr = soup.find("hr")
    if not isinstance(hr, Tag):
        body = soup.find("body")
        return body if isinstance(body, Tag) else None
    for sibling in hr.next_siblings:
        if isinstance(sibling, Tag):
            return sibling
    return None


def _block_lines(node: Tag) -> list[str]:
    lines: list[str] = []
    for child in node.children:
        if not isinstance(child, Tag):
            continue
        name = child.name.lower() if child.name else ""
        if name == "p":
            text = _clean_text(child.get_text(" "))
            if text:
                lines.append(text)
        elif name == "table":
            table_text = _table_text(child)
            if table_text:
                lines.append(table_text)
        elif name in {"style", "script"}:
            continue
        else:
            lines.extend(_block_lines(child))
    return lines


def _table_text(table: Tag) -> str | None:
    rows: list[str] = []
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells: list[str] = []
        for cell in row.find_all(["th", "td"], recursive=False):
            if not isinstance(cell, Tag):
                continue
            text = _clean_text(cell.get_text(" "))
            if text:
                cells.append(text)
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows) if rows else None


def _source_notes(soup: BeautifulSoup) -> tuple[str, ...]:
    notes: list[str] = []
    for paragraph in soup.find_all("p"):
        if not isinstance(paragraph, Tag):
            continue
        text = _clean_text(paragraph.get_text(" "))
        raw_classes = paragraph.get("class")
        classes = (
            {str(value) for value in raw_classes}
            if isinstance(raw_classes, list)
            else ({str(raw_classes)} if raw_classes is not None else set())
        )
        if text.startswith("(Source:") or "JCARSourceNote" in classes:
            notes.append(text)
    return tuple(notes)


def _references_to_labels(text: str) -> tuple[str, ...]:
    patterns = (
        re.compile(r"\b\d+\s+Ill\.\s+Adm\.\s+Code\s+[A-Za-z0-9. -]+"),
        re.compile(r"\b\d+\s+ILCS\s+\d+(?:/[A-Za-z0-9.-]+)?"),
    )
    refs: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            refs.add(_clean_text(match.group(0)).rstrip(".,;:)"))
    return tuple(sorted(refs))


def _linked_asset_sources(data: bytes, *, entry: _DirectoryEntry) -> tuple[tuple[str, str], ...]:
    soup = BeautifulSoup(data, "html.parser")
    assets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        for attr in ("src", "href"):
            value = tag.get(attr)
            if value is None:
                continue
            raw = str(value)
            if not raw or raw.startswith(("#", "mailto:", "javascript:")):
                continue
            url = urljoin(entry.source_url, raw)
            parsed = urlparse(url)
            if parsed.netloc != "www.ilga.gov" or "/ftp/JCAR/AdminCode/" not in parsed.path:
                continue
            asset_name = parsed.path.split(f"/AdminCode/{entry.title}/", 1)[-1]
            if not asset_name or asset_name.endswith(".html") or asset_name == entry.name:
                continue
            relative_name = f"{_SOURCE_PREFIX}/{entry.title}/{asset_name}"
            if relative_name not in seen:
                seen.add(relative_name)
                assets.append((relative_name, url))
    return tuple(assets)


def _append_inventory_and_record(
    *,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    citation_path: str,
    parent_citation_path: str | None,
    heading: str,
    body: str | None,
    version: str,
    source: _RecordedSource,
    source_as_of: str,
    expression_date: str,
    level: int,
    ordinal: int,
    kind: str,
    legal_identifier: str | None,
    identifiers: dict[str, str] | None,
    metadata: dict[str, Any],
) -> None:
    inventory.append(
        SourceInventoryItem(
            citation_path=citation_path,
            source_url=source.source_url,
            source_path=source.source_path,
            source_format=ILLINOIS_ADMIN_CODE_SOURCE_FORMAT,
            sha256=source.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=citation_path,
            parent_citation_path=parent_citation_path,
            heading=heading,
            body=body,
            version=version,
            source=source,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=level,
            ordinal=ordinal,
            kind=kind,
            legal_identifier=legal_identifier,
            identifiers=identifiers,
            metadata=metadata,
        )
    )


def _record(
    *,
    citation_path: str,
    heading: str,
    body: str | None,
    version: str,
    source: _RecordedSource,
    source_as_of: str,
    expression_date: str,
    level: int,
    ordinal: int,
    kind: str,
    parent_citation_path: str | None = None,
    legal_identifier: str | None = None,
    identifiers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProvisionRecord:
    return ProvisionRecord(
        jurisdiction="us-il",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        id=deterministic_provision_id(citation_path),
        parent_citation_path=parent_citation_path,
        parent_id=(
            deterministic_provision_id(parent_citation_path)
            if parent_citation_path is not None
            else None
        ),
        heading=heading,
        citation_label=legal_identifier,
        body=body,
        version=version,
        source_url=source.source_url,
        source_path=source.source_path,
        source_format=ILLINOIS_ADMIN_CODE_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=level,
        ordinal=ordinal,
        kind=kind,
        legal_identifier=legal_identifier,
        identifiers=identifiers,
        has_rulespec=False,
        metadata=metadata,
    )


def _container_metadata(
    kind: str,
    hierarchy: _Hierarchy,
    entry: _DirectoryEntry | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": kind,
        "title_number": str(int(hierarchy.title_number)),
        "title_number_padded": hierarchy.title_number,
        "title_heading": hierarchy.title_heading,
        "source_note": ILLINOIS_ADMIN_CODE_SOURCE_NOTE,
    }
    if hierarchy.subtitle_number:
        metadata["subtitle_number"] = hierarchy.subtitle_number
    if hierarchy.subtitle_heading is not None:
        metadata["subtitle_heading"] = hierarchy.subtitle_heading
    if hierarchy.chapter_number:
        metadata["chapter_number"] = hierarchy.chapter_number
        metadata["chapter_heading"] = hierarchy.chapter_heading
    if hierarchy.subchapter_number:
        metadata["subchapter_number"] = hierarchy.subchapter_number
        metadata["subchapter_heading"] = hierarchy.subchapter_heading
    if kind == "part":
        metadata["part_number"] = hierarchy.part_number
        metadata["part_heading"] = hierarchy.part_heading
    if entry is not None:
        metadata["source_file"] = entry.name
        if entry.last_modified:
            metadata["source_last_modified"] = entry.last_modified
    return metadata


def _container_heading(label: str, number: str, heading: str | None) -> str:
    text = f"{label} {number}"
    if heading:
        text = f"{text}. {heading}"
    return text


def _set_container_source(
    container_sources: dict[str, _ContainerSource],
    citation_path: str | None,
    source: _ContainerSource,
) -> None:
    if citation_path is not None and citation_path not in container_sources:
        container_sources[citation_path] = source


def _listing_date(date_text: str, time_text: str) -> str | None:
    try:
        parsed = datetime.strptime(f"{date_text} {time_text}", "%m/%d/%Y %I:%M %p")
    except ValueError:
        return None
    return parsed.date().isoformat()


def _normal_title_number(value: str) -> str:
    text = value.strip()
    if not text.isdigit():
        raise ValueError(f"Illinois title must be numeric: {value!r}")
    return f"{int(text):03d}"


def _section_path_segment(section_number: str) -> str:
    label = _supplemental_label(section_number)
    if label:
        section_without_label = re.sub(label, "", section_number, flags=re.I)
        return f"{label.lower()}-{_path_token(section_without_label)}"
    return f"section-{_path_token(section_number)}"


def _page_kind(section_number: str) -> str:
    return (_supplemental_label(section_number) or "section").lower()


def _supplemental_label(section_number: str) -> str | None:
    upper = section_number.upper()
    for label in ("APPENDIX", "ILLUSTRATION", "EXHIBIT", "TABLE", "FORM", "SCHEDULE"):
        if label in upper:
            return label
    return None


def _path_token(value: str) -> str:
    token = _clean_text(value).lower()
    token = token.replace(".", "-")
    token = re.sub(r"[^a-z0-9]+", "-", token).strip("-")
    return token or "unknown"


def _clean_text(value: str) -> str:
    text = value.replace("\xa0", " ").replace("\ufffd", " ")
    text = text.replace("Â", "").replace("�", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _join_lines(lines: Iterable[str]) -> str | None:
    cleaned = [_clean_text(line) for line in lines if _clean_text(line)]
    return "\n\n".join(cleaned) if cleaned else None


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return tuple(out)


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _progress(stream: TextIO | None, message: str) -> None:
    if stream is not None:
        print(message, file=stream)
        stream.flush()


def main(argv: list[str] | None = None) -> int:
    """Debug helper for manual module execution."""

    del argv
    print("Use axiom-corpus-ingest extract-illinois-admin-code", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
