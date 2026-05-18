"""Ohio Administrative Code source-first adapter."""

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
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment, sha256_bytes
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

OHIO_ADMIN_CODE_BASE_URL = "https://codes.ohio.gov"
OHIO_ADMIN_CODE_INDEX_URL = f"{OHIO_ADMIN_CODE_BASE_URL}/ohio-administrative-code"
OHIO_ADMIN_CODE_SOURCE_FORMAT = "ohio-administrative-code-html"
OHIO_ADMIN_CODE_USER_AGENT = "axiom-corpus/0.1 (max@axiom-foundation.org)"

_SOURCE_PREFIX = "ohio-administrative-code"
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


@dataclass(frozen=True)
class OhioAdminCodeExtractReport:
    """Result from an Ohio Administrative Code extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    agency_count: int
    chapter_count: int
    rule_count: int
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
class _Agency:
    number: str
    name: str
    href: str
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"us-oh/regulation/agency-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return urljoin(OHIO_ADMIN_CODE_INDEX_URL, self.href)

    @property
    def heading(self) -> str:
        return f"{self.number}. {self.name}".strip()


@dataclass(frozen=True)
class _AgencySnapshot:
    agency: _Agency
    snapshot: _SourceSnapshot
    chapters: tuple[_Chapter, ...]


@dataclass(frozen=True)
class _Chapter:
    agency: _Agency
    number: str
    heading: str
    href: str
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"{self.agency.citation_path}/chapter-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return urljoin(OHIO_ADMIN_CODE_INDEX_URL, self.href)

    @property
    def legal_identifier(self) -> str:
        return f"Ohio Admin. Code Chapter {self.number}"


@dataclass(frozen=True)
class _Rule:
    chapter: _Chapter
    number: str
    heading: str
    body: str | None
    source_url: str
    source_id: str
    effective_date: str | None
    promulgated_under: str | None
    pdf_url: str | None
    authorized_by: str | None
    amplifies: str | None
    five_year_review_date: str | None
    prior_effective_dates: str | None
    last_updated: str | None
    references_to: tuple[str, ...]
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"{self.chapter.citation_path}/rule-{_path_token(self.number)}"

    @property
    def legal_identifier(self) -> str:
        return f"Ohio Admin. Code {self.number}"


@dataclass(frozen=True)
class _ChapterSnapshot:
    chapter: _Chapter
    snapshot: _SourceSnapshot | None
    rules: tuple[_Rule, ...]
    error: str | None = None


def ohio_admin_code_run_id(
    version: str,
    *,
    only_agency: str | None = None,
    only_chapter: str | None = None,
    limit: int | None = None,
) -> str:
    """Return a scoped Ohio Administrative Code run id."""

    parts = [version]
    if only_agency:
        parts.append(f"agency-{_path_token(only_agency)}")
    if only_chapter:
        parts.append(f"chapter-{_path_token(only_chapter)}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def extract_ohio_admin_code(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_agency: str | None = None,
    only_chapter: str | None = None,
    limit: int | None = None,
    workers: int = 8,
    progress_stream: TextIO | None = None,
) -> OhioAdminCodeExtractReport:
    """Snapshot official Ohio Administrative Code HTML and extract provisions."""

    jurisdiction = "us-oh"
    document_class = DocumentClass.REGULATION.value
    if only_chapter and only_agency is None:
        only_agency = _agency_number_from_chapter(only_chapter)
    run_id = ohio_admin_code_run_id(
        version,
        only_agency=only_agency,
        only_chapter=only_chapter,
        limit=limit,
    )
    source_root = Path(source_dir) if source_dir is not None else None
    download_root = Path(download_dir) if download_dir is not None and source_root is None else None
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)

    session = _session()
    index_snapshot = _snapshot_html(
        store,
        session,
        run_id=run_id,
        relative_name=f"{_SOURCE_PREFIX}/index.html",
        url=OHIO_ADMIN_CODE_INDEX_URL,
        source_root=source_root,
        download_root=download_root,
    )
    source_paths: list[Path] = [index_snapshot.source_path]
    all_agencies = _parse_agencies(index_snapshot.content)
    agencies = tuple(
        agency
        for agency in all_agencies
        if only_agency is None or _same_token(agency.number, only_agency)
    )
    if not agencies:
        raise ValueError(f"no Ohio Administrative Code agencies selected: {only_agency!r}")

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    errors: list[str] = []
    skipped_source_count = 0

    root_path = "us-oh/regulation"
    items.append(
        SourceInventoryItem(
            citation_path=root_path,
            source_url=OHIO_ADMIN_CODE_INDEX_URL,
            source_path=index_snapshot.source_key,
            source_format=OHIO_ADMIN_CODE_SOURCE_FORMAT,
            sha256=index_snapshot.sha256,
            metadata={
                "kind": "collection",
                "source_as_of": source_as_of_text,
                "selected_agency_count": len(agencies),
                "total_agency_count": len(all_agencies),
            },
        )
    )
    records.append(
        _root_record(
            version=run_id,
            source_path=index_snapshot.source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            selected_agency_count=len(agencies),
            total_agency_count=len(all_agencies),
        )
    )

    agency_snapshots: list[_AgencySnapshot] = []
    selected_chapters: list[_Chapter] = []
    for agency in agencies:
        _progress(progress_stream, f"ohio-admin-code agency {agency.number}")
        relative_name = f"{_SOURCE_PREFIX}/agencies/{_path_token(agency.number)}.html"
        try:
            snapshot = _snapshot_html(
                store,
                session,
                run_id=run_id,
                relative_name=relative_name,
                url=agency.source_url,
                source_root=source_root,
                download_root=download_root,
            )
        except (OSError, requests.RequestException) as exc:
            errors.append(f"agency {agency.number}: {exc}")
            skipped_source_count += 1
            continue
        source_paths.append(snapshot.source_path)
        chapters = _parse_chapters(snapshot.content, agency=agency)
        if only_chapter is not None:
            chapters = tuple(
                chapter for chapter in chapters if _same_token(chapter.number, only_chapter)
            )
        agency_snapshots.append(
            _AgencySnapshot(agency=agency, snapshot=snapshot, chapters=chapters)
        )
        selected_chapters.extend(chapters)
        if limit is not None and len(selected_chapters) >= limit:
            selected_chapters = selected_chapters[:limit]
            break

    if only_chapter is not None and not selected_chapters:
        raise ValueError(f"no Ohio Administrative Code chapter selected: {only_chapter!r}")

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
    agency_count = 0
    chapter_count = 0
    rule_count = 0
    remaining_rules = limit

    for agency_snapshot in agency_snapshots:
        agency_chapters = tuple(
            chapter
            for chapter in agency_snapshot.chapters
            if chapter.citation_path in chapter_result_by_path
        )
        if not agency_chapters and only_chapter is not None:
            continue
        agency = agency_snapshot.agency
        if agency.citation_path not in seen_paths:
            seen_paths.add(agency.citation_path)
            _append_agency(
                agency,
                snapshot=agency_snapshot.snapshot,
                inventory=items,
                records=records,
                version=run_id,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                chapter_count=len(agency_chapters),
            )
            agency_count += 1

        for chapter in agency_chapters:
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
                    inventory=items,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    rule_count=len(result.rules),
                )
                chapter_count += 1
            for rule in result.rules:
                if remaining_rules is not None and remaining_rules <= 0:
                    break
                if rule.citation_path in seen_paths:
                    continue
                seen_paths.add(rule.citation_path)
                _append_rule(
                    rule,
                    snapshot=result.snapshot,
                    inventory=items,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                )
                rule_count += 1
                if remaining_rules is not None:
                    remaining_rules -= 1

    if len(records) <= 1:
        raise ValueError("no Ohio Administrative Code provisions extracted")

    inventory_path = store.inventory_path(jurisdiction, document_class, run_id)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path(jurisdiction, document_class, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
    )
    coverage_path = store.coverage_path(jurisdiction, document_class, run_id)
    store.write_json(coverage_path, coverage.to_mapping())

    return OhioAdminCodeExtractReport(
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
        agency_count=agency_count,
        chapter_count=chapter_count,
        rule_count=rule_count,
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
    _progress(progress_stream, f"ohio-admin-code chapter {chapter.number}")
    relative_name = f"{_SOURCE_PREFIX}/chapters/chapter-{_path_token(chapter.number)}.html"
    try:
        snapshot = _snapshot_html(
            store,
            _session(),
            run_id=run_id,
            relative_name=relative_name,
            url=chapter.source_url,
            source_root=source_root,
            download_root=download_root,
        )
        return _ChapterSnapshot(
            chapter=chapter,
            snapshot=snapshot,
            rules=_parse_rules(snapshot.content, chapter=chapter),
        )
    except (OSError, requests.RequestException) as exc:
        return _ChapterSnapshot(
            chapter=chapter,
            snapshot=None,
            rules=(),
            error=f"chapter {chapter.number}: {exc}",
        )


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": OHIO_ADMIN_CODE_USER_AGENT})
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
    source_path = store.source_path("us-oh", DocumentClass.REGULATION, run_id, relative_name)
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
    return _SourceSnapshot(
        source_key=source_key,
        source_path=source_path,
        sha256=sha256,
        content=content,
    )


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
    response: requests.Response | None = None
    for attempt in range(6):
        response = session.get(url, timeout=60)
        if response.status_code not in {429, 500, 502, 503, 504}:
            response.raise_for_status()
            content = response.content
            if download_root is not None:
                path = download_root / relative_name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            time.sleep(0.1)
            return content
        retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
        time.sleep(retry_after if retry_after is not None else min(2**attempt, 30))
    assert response is not None
    response.raise_for_status()
    return response.content


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(float(value), 0)
    except ValueError:
        return None


def _parse_agencies(html_bytes: bytes) -> tuple[_Agency, ...]:
    soup = BeautifulSoup(html_bytes.decode("utf-8", errors="replace"), "html.parser")
    agencies: dict[str, _Agency] = {}
    for ordinal, link in enumerate(soup.select("td.name-cell a[href]"), start=1):
        if not isinstance(link, Tag):
            continue
        href = _path_from_href(str(link.get("href") or ""), OHIO_ADMIN_CODE_INDEX_URL)
        match = re.fullmatch(r"/ohio-administrative-code/(?P<number>[0-9][0-9A-Za-z:.-]*)", href)
        if not match:
            continue
        number = match.group("number")
        parsed_number, name = _split_number_heading(link.get_text(" ", strip=True), number)
        agencies.setdefault(
            number,
            _Agency(
                number=parsed_number or number,
                name=name,
                href=href,
                ordinal=ordinal,
            ),
        )
    return tuple(sorted(agencies.values(), key=lambda agency: agency.ordinal))


def _parse_chapters(html_bytes: bytes, *, agency: _Agency) -> tuple[_Chapter, ...]:
    soup = BeautifulSoup(html_bytes.decode("utf-8", errors="replace"), "html.parser")
    chapters: dict[str, _Chapter] = {}
    for ordinal, link in enumerate(soup.select('td.name-cell a[href*="chapter-"]'), start=1):
        if not isinstance(link, Tag):
            continue
        href = _path_from_href(str(link.get("href") or ""), agency.source_url)
        match = re.fullmatch(
            r"/ohio-administrative-code/chapter-(?P<number>[0-9A-Za-z:.-]+)",
            href,
        )
        if not match:
            continue
        number = match.group("number")
        parsed_number, heading = _parse_chapter_heading(link.get_text(" ", strip=True), number)
        chapters.setdefault(
            number,
            _Chapter(
                agency=agency,
                number=parsed_number or number,
                heading=heading,
                href=href,
                ordinal=ordinal,
            ),
        )
    return tuple(sorted(chapters.values(), key=lambda chapter: chapter.ordinal))


def _parse_rules(html_bytes: bytes, *, chapter: _Chapter) -> tuple[_Rule, ...]:
    soup = BeautifulSoup(html_bytes.decode("utf-8", errors="replace"), "html.parser")
    rules: list[_Rule] = []
    for ordinal, content in enumerate(soup.select("div.list-content"), start=1):
        if not isinstance(content, Tag):
            continue
        head = content.select_one(".content-head-text a")
        if not isinstance(head, Tag):
            continue
        href = _path_from_href(str(head.get("href") or ""), chapter.source_url)
        match = re.fullmatch(
            r"/ohio-administrative-code/rule-(?P<number>[0-9A-Za-z:.-]+)",
            href,
        )
        if not match:
            continue
        number = match.group("number")
        parsed_number, heading = _parse_rule_heading(head.get_text(" ", strip=True), number)
        body_tag = content.select_one("section.laws-body")
        info = _rule_info(content)
        supplemental = _supplemental_info(content)
        rules.append(
            _Rule(
                chapter=chapter,
                number=parsed_number or number,
                heading=heading,
                body=_body_text(body_tag) if isinstance(body_tag, Tag) else None,
                source_url=urljoin(chapter.source_url, href),
                source_id=f"rule-{number}",
                effective_date=info.get("effective"),
                promulgated_under=info.get("promulgated_under"),
                pdf_url=info.get("pdf_url"),
                authorized_by=supplemental.get("authorized_by"),
                amplifies=supplemental.get("amplifies"),
                five_year_review_date=supplemental.get("five_year_review_date"),
                prior_effective_dates=supplemental.get("prior_effective_dates"),
                last_updated=_last_updated(body_tag) if isinstance(body_tag, Tag) else None,
                references_to=_references(content),
                ordinal=ordinal,
            )
        )
    return tuple(rules)


def _rule_info(content: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for module in content.select(".laws-section-info-module"):
        if not isinstance(module, Tag):
            continue
        label_tag = module.select_one(".label")
        value_tag = module.select_one(".value")
        if not isinstance(label_tag, Tag) or not isinstance(value_tag, Tag):
            continue
        label = _metadata_key(label_tag.get_text(" ", strip=True))
        if label == "pdf":
            link = value_tag.find("a")
            if isinstance(link, Tag):
                href = str(link.get("href") or "")
                if href:
                    values["pdf_url"] = urljoin(OHIO_ADMIN_CODE_BASE_URL, href)
            continue
        value = _clean_text(value_tag.get_text(" ", strip=True))
        if value:
            values[label] = value
    return values


def _supplemental_info(content: Tag) -> dict[str, str]:
    addl = content.select_one("section.laws-history .laws-additional-information")
    if not isinstance(addl, Tag):
        return {}
    values: dict[str, str] = {}
    for label_tag in addl.find_all("strong"):
        if not isinstance(label_tag, Tag):
            continue
        label = _metadata_key(label_tag.get_text(" ", strip=True))
        value_tag = label_tag.find_next_sibling("span")
        if not isinstance(value_tag, Tag):
            continue
        value = _clean_text(value_tag.get_text(" ", strip=True))
        if value:
            values[label] = value
    return values


def _metadata_key(value: str) -> str:
    text = _clean_text(value).rstrip(":").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _body_text(body_tag: Tag | None) -> str | None:
    if body_tag is None:
        return None
    lines = _block_lines(body_tag)
    return "\n".join(line for line in lines if line) or None


def _block_lines(tag: Tag) -> list[str]:
    lines: list[str] = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            text = _clean_text(str(child))
            if text:
                lines.append(text)
            continue
        if not isinstance(child, Tag):
            continue
        classes = set(child.get("class") or [])
        if "laws-notice" in classes:
            continue
        if child.name == "p":
            text = _clean_text(child.get_text(" ", strip=True))
            if text:
                lines.append(text)
        elif child.name == "table":
            table = _table_text(child)
            if table:
                lines.append(table)
        elif child.name in {"ul", "ol"}:
            for item in child.find_all("li", recursive=False):
                if isinstance(item, Tag):
                    text = _clean_text(item.get_text(" ", strip=True))
                    if text:
                        lines.append(text)
        elif child.name not in {"script", "style"}:
            lines.extend(_block_lines(child))
    return lines


def _table_text(table: Tag) -> str | None:
    rows: list[str] = []
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [
            _clean_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"], recursive=False)
            if isinstance(cell, Tag)
        ]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows) if rows else None


def _last_updated(body_tag: Tag) -> str | None:
    notice = body_tag.select_one(".laws-notice p")
    if not isinstance(notice, Tag):
        return None
    return _clean_text(notice.get_text(" ", strip=True)) or None


def _references(content: Tag) -> tuple[str, ...]:
    refs: set[str] = set()
    for link in content.select("a.rule-link, a.section-link"):
        if not isinstance(link, Tag):
            continue
        href = str(link.get("href") or "")
        rule_match = re.search(r"/ohio-administrative-code/rule-(?P<rule>[0-9A-Za-z:.-]+)$", href)
        if rule_match:
            rule = rule_match.group("rule")
            refs.add(f"us-oh/regulation/rule-{_path_token(rule)}")
            continue
        section_match = re.search(r"/ohio-revised-code/section-(?P<section>[0-9A-Za-z.]+)$", href)
        if section_match:
            refs.add(f"us-oh/statute/{section_match.group('section')}")
    return tuple(sorted(refs))


def _append_agency(
    agency: _Agency,
    *,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    chapter_count: int,
) -> None:
    metadata = {
        "kind": "agency",
        "agency_number": agency.number,
        "agency_name": agency.name,
        "chapter_count": chapter_count,
    }
    inventory.append(
        SourceInventoryItem(
            citation_path=agency.citation_path,
            source_url=agency.source_url,
            source_path=snapshot.source_key,
            source_format=OHIO_ADMIN_CODE_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=agency.citation_path,
            parent_citation_path="us-oh/regulation",
            citation_label=f"Ohio Admin. Code Agency {agency.number}",
            heading=agency.heading,
            body=None,
            version=version,
            source_url=agency.source_url,
            source_path=snapshot.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=1,
            ordinal=agency.ordinal,
            kind="agency",
            legal_identifier=f"Ohio Admin. Code Agency {agency.number}",
            identifiers={"ohio:oac_agency": agency.number},
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
    rule_count: int,
) -> None:
    metadata = {
        "kind": "chapter",
        "agency_number": chapter.agency.number,
        "chapter_number": chapter.number,
        "rule_count": rule_count,
    }
    inventory.append(
        SourceInventoryItem(
            citation_path=chapter.citation_path,
            source_url=chapter.source_url,
            source_path=snapshot.source_key,
            source_format=OHIO_ADMIN_CODE_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=chapter.citation_path,
            parent_citation_path=chapter.agency.citation_path,
            citation_label=chapter.legal_identifier,
            heading=chapter.heading,
            body=None,
            version=version,
            source_url=chapter.source_url,
            source_path=snapshot.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=2,
            ordinal=chapter.ordinal,
            kind="chapter",
            legal_identifier=chapter.legal_identifier,
            identifiers={
                "ohio:oac_agency": chapter.agency.number,
                "ohio:oac_chapter": chapter.number,
            },
            metadata=metadata,
        )
    )


def _append_rule(
    rule: _Rule,
    *,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> None:
    metadata: dict[str, object] = {
        "kind": "rule",
        "agency_number": rule.chapter.agency.number,
        "chapter_number": rule.chapter.number,
        "rule_number": rule.number,
        "effective_date": rule.effective_date,
        "promulgated_under": rule.promulgated_under,
        "pdf_url": rule.pdf_url,
        "authorized_by": rule.authorized_by,
        "amplifies": rule.amplifies,
        "five_year_review_date": rule.five_year_review_date,
        "prior_effective_dates": rule.prior_effective_dates,
        "last_updated": rule.last_updated,
        "references_to": list(rule.references_to),
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    inventory.append(
        SourceInventoryItem(
            citation_path=rule.citation_path,
            source_url=rule.source_url,
            source_path=snapshot.source_key,
            source_format=OHIO_ADMIN_CODE_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=rule.citation_path,
            parent_citation_path=rule.chapter.citation_path,
            citation_label=rule.legal_identifier,
            heading=rule.heading,
            body=rule.body,
            version=version,
            source_url=rule.source_url,
            source_path=snapshot.source_key,
            source_id=rule.source_id,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=3,
            ordinal=rule.ordinal,
            kind="rule",
            legal_identifier=rule.legal_identifier,
            identifiers={
                "ohio:oac_agency": rule.chapter.agency.number,
                "ohio:oac_chapter": rule.chapter.number,
                "ohio:oac_rule": rule.number,
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
    selected_agency_count: int,
    total_agency_count: int,
) -> ProvisionRecord:
    return _record(
        citation_path="us-oh/regulation",
        citation_label="Ohio Administrative Code",
        heading="Ohio Administrative Code",
        body=None,
        version=version,
        source_url=OHIO_ADMIN_CODE_INDEX_URL,
        source_path=source_path,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=0,
        ordinal=0,
        kind="collection",
        legal_identifier="Ohio Administrative Code",
        identifiers={"state:code": "OAC"},
        metadata={
            "selected_agency_count": selected_agency_count,
            "total_agency_count": total_agency_count,
        },
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
        jurisdiction="us-oh",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        citation_label=citation_label,
        heading=heading,
        body=body,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=source_id,
        source_format=OHIO_ADMIN_CODE_SOURCE_FORMAT,
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


def _split_number_heading(text: str, expected_number: str) -> tuple[str | None, str]:
    cleaned = _clean_text(text)
    match = re.match(
        rf"^(?P<number>{re.escape(expected_number)})\s*\|\s*(?P<heading>.+)$",
        cleaned,
    )
    if match:
        return match.group("number"), _clean_text(match.group("heading"))
    parts = [part.strip() for part in cleaned.split("|", 1)]
    if len(parts) == 2 and parts[0]:
        return parts[0], _clean_text(parts[1])
    return None, cleaned


def _parse_rule_heading(text: str, expected_number: str) -> tuple[str | None, str]:
    cleaned = _clean_text(text)
    match = re.match(
        rf"^Rule\s+(?P<number>{re.escape(expected_number)})\s*\|\s*(?P<heading>.+)$",
        cleaned,
    )
    if match:
        return match.group("number"), _clean_text(match.group("heading")).rstrip(".")
    parsed_number, heading = _split_number_heading(cleaned.removeprefix("Rule "), expected_number)
    return parsed_number, heading.rstrip(".")


def _parse_chapter_heading(text: str, expected_number: str) -> tuple[str | None, str]:
    cleaned = _clean_text(text)
    match = re.match(
        rf"^Chapter\s+(?P<number>{re.escape(expected_number)})\s*\|\s*(?P<heading>.+)$",
        cleaned,
    )
    if match:
        return match.group("number"), _clean_text(match.group("heading")).rstrip(".")
    parsed_number, heading = _split_number_heading(
        cleaned.removeprefix("Chapter "),
        expected_number,
    )
    return parsed_number, heading.rstrip(".")


def _path_from_href(href: str, base_url: str) -> str:
    return urlparse(urljoin(base_url, href)).path


def _source_key(run_id: str, relative_name: str) -> str:
    return f"sources/us-oh/regulation/{run_id}/{relative_name}"


def _agency_number_from_chapter(chapter: str) -> str:
    text = chapter.removeprefix("chapter-").strip("/")
    if "-" not in text:
        return text
    return text.rsplit("-", 1)[0]


def _path_token(value: str) -> str:
    token = _clean_text(value).lower()
    token = token.replace(".", "-")
    token = re.sub(r"[^a-z0-9]+", "-", token).strip("-")
    return safe_segment(token or "unknown")


def _same_token(left: str, right: str) -> bool:
    return _path_token(left) == _path_token(right)


def _clean_text(value: str) -> str:
    text = value.replace("\xa0", " ").replace("\ufffd", " ")
    text = text.replace("Â", "").replace("�", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


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
