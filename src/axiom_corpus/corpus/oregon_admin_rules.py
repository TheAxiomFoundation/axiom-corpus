"""Oregon Administrative Rules source-first adapter."""

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
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment, sha256_bytes
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

OREGON_OARD_BASE_URL = "https://secure.sos.state.or.us"
OREGON_OARD_APP_URL = f"{OREGON_OARD_BASE_URL}/oard/"
OREGON_ADMIN_RULES_SEARCH_URL = urljoin(OREGON_OARD_APP_URL, "ruleSearch.action")
OREGON_ADMIN_RULES_SOURCE_FORMAT = "oregon-administrative-rules-html"
OREGON_ADMIN_RULES_USER_AGENT = "axiom-corpus/0.1 (max@axiom-foundation.org)"

_SOURCE_PREFIX = "oregon-administrative-rules"
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
_CHAPTER_OPTION_RE = re.compile(r"^(?P<number>\d+)\s+-\s+(?P<name>.+)$")
_DIVISION_LABEL_RE = re.compile(
    r"^Division\s+(?P<number>[A-Za-z0-9.-]+)\s*-\s*(?P<name>.+)$",
    re.I,
)
_OAR_REF_RE = re.compile(r"\bOAR\s+(\d{3}-\d{3}-\d{4})\b")
_ORS_REF_RE = re.compile(r"\bORS\s+(\d+(?:\.\d+)?(?:\([^)]+\))*)\b")


@dataclass(frozen=True)
class OregonAdminRulesExtractReport:
    """Result from an Oregon Administrative Rules extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    chapter_count: int
    division_count: int
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
class _Chapter:
    chapter_id: str
    number: str
    name: str
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"us-or/regulation/chapter-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return urljoin(
            OREGON_OARD_APP_URL,
            f"displayChapterRules.action?selectedChapter={self.chapter_id}",
        )

    @property
    def heading(self) -> str:
        return f"Chapter {self.number}. {self.name}"


@dataclass(frozen=True)
class _ChapterSnapshot:
    chapter: _Chapter
    snapshot: _SourceSnapshot
    divisions: tuple[_Division, ...]


@dataclass(frozen=True)
class _Division:
    chapter: _Chapter
    division_id: str
    number: str
    name: str
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"{self.chapter.citation_path}/division-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return urljoin(
            OREGON_OARD_APP_URL,
            f"displayDivisionRules.action?selectedDivision={self.division_id}",
        )

    @property
    def heading(self) -> str:
        return f"Division {self.number}. {self.name}"


@dataclass(frozen=True)
class _DivisionSnapshot:
    division: _Division
    snapshot: _SourceSnapshot | None
    rules: tuple[_Rule, ...]
    error: str | None = None


@dataclass(frozen=True)
class _Rule:
    division: _Division
    number: str
    heading: str
    body: str | None
    source_url: str
    source_id: str | None
    statutory_authority: str | None
    statutes_implemented: str | None
    history: str | None
    references_to: tuple[str, ...]
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"{self.division.citation_path}/rule-{_path_token(self.number)}"

    @property
    def legal_identifier(self) -> str:
        return f"OAR {self.number}"


def oregon_admin_rules_run_id(
    version: str,
    *,
    only_chapter: str | None = None,
    only_division: str | None = None,
    limit: int | None = None,
) -> str:
    """Return a scoped Oregon Administrative Rules run id."""

    parts = [version]
    if only_chapter:
        parts.append(f"chapter-{_path_token(only_chapter)}")
    if only_division:
        parts.append(f"division-{_path_token(only_division)}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def extract_oregon_admin_rules(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_chapter: str | None = None,
    only_division: str | None = None,
    limit: int | None = None,
    workers: int = 8,
    progress_stream: TextIO | None = None,
) -> OregonAdminRulesExtractReport:
    """Snapshot official OARD current-rule HTML and extract provisions."""

    jurisdiction = "us-or"
    document_class = DocumentClass.REGULATION.value
    run_id = oregon_admin_rules_run_id(
        version,
        only_chapter=only_chapter,
        only_division=only_division,
        limit=limit,
    )
    source_root = Path(source_dir) if source_dir is not None else None
    download_root = Path(download_dir) if download_dir is not None and source_root is None else None
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    session = _session()

    search_snapshot = _snapshot_html(
        store,
        session,
        run_id=run_id,
        relative_name=f"{_SOURCE_PREFIX}/rule-search.html",
        url=OREGON_ADMIN_RULES_SEARCH_URL,
        source_root=source_root,
        download_root=download_root,
    )
    source_paths: list[Path] = [search_snapshot.source_path]
    all_chapters = _parse_chapters(search_snapshot.content)
    chapters = tuple(
        chapter
        for chapter in all_chapters
        if only_chapter is None or _same_token(chapter.number, only_chapter)
    )
    if limit is not None:
        chapters = chapters[:limit]
    if not chapters:
        raise ValueError(f"no Oregon Administrative Rules chapters selected: {only_chapter!r}")

    root_path = "us-or/regulation"
    inventory: list[SourceInventoryItem] = [
        SourceInventoryItem(
            citation_path=root_path,
            source_url=OREGON_ADMIN_RULES_SEARCH_URL,
            source_path=search_snapshot.source_key,
            source_format=OREGON_ADMIN_RULES_SOURCE_FORMAT,
            sha256=search_snapshot.sha256,
            metadata={
                "kind": "collection",
                "source_as_of": source_as_of_text,
                "selected_chapter_count": len(chapters),
                "total_chapter_count": len(all_chapters),
            },
        )
    ]
    records: list[ProvisionRecord] = [
        _root_record(
            version=run_id,
            source_path=search_snapshot.source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            selected_chapter_count=len(chapters),
            total_chapter_count=len(all_chapters),
        )
    ]
    errors: list[str] = []
    skipped_source_count = 0

    chapter_snapshots: list[_ChapterSnapshot] = []
    selected_divisions: list[_Division] = []
    for chapter in chapters:
        _progress(progress_stream, f"oregon-admin-rules chapter {chapter.number}")
        try:
            snapshot = _snapshot_html(
                store,
                session,
                run_id=run_id,
                relative_name=f"{_SOURCE_PREFIX}/chapters/chapter-{_path_token(chapter.number)}.html",
                url=chapter.source_url,
                source_root=source_root,
                download_root=download_root,
            )
        except (OSError, requests.RequestException) as exc:
            errors.append(f"chapter {chapter.number}: {exc}")
            skipped_source_count += 1
            continue
        source_paths.append(snapshot.source_path)
        divisions = _parse_divisions(snapshot.content, chapter=chapter)
        if only_division is not None:
            divisions = tuple(
                division
                for division in divisions
                if _same_token(division.number, only_division)
            )
        chapter_snapshots.append(
            _ChapterSnapshot(chapter=chapter, snapshot=snapshot, divisions=divisions)
        )
        selected_divisions.extend(divisions)

    if only_division is not None and not selected_divisions:
        raise ValueError(f"no Oregon Administrative Rules division selected: {only_division!r}")

    division_results = _snapshot_divisions(
        store,
        run_id=run_id,
        divisions=tuple(selected_divisions),
        source_root=source_root,
        download_root=download_root,
        workers=workers,
        progress_stream=progress_stream,
    )
    division_result_by_path = {
        result.division.citation_path: result for result in division_results
    }
    seen_paths = {root_path}
    chapter_count = 0
    division_count = 0
    rule_count = 0

    for chapter_snapshot in chapter_snapshots:
        chapter_divisions = tuple(
            division
            for division in chapter_snapshot.divisions
            if division.citation_path in division_result_by_path
        )
        if not chapter_divisions and only_division is not None:
            continue
        chapter = chapter_snapshot.chapter
        if chapter.citation_path not in seen_paths:
            seen_paths.add(chapter.citation_path)
            _append_chapter(
                chapter,
                snapshot=chapter_snapshot.snapshot,
                inventory=inventory,
                records=records,
                version=run_id,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                division_count=len(chapter_divisions),
            )
            chapter_count += 1

        for division in chapter_divisions:
            result = division_result_by_path[division.citation_path]
            if result.error:
                errors.append(result.error)
                skipped_source_count += 1
                continue
            if result.snapshot is None:
                continue
            source_paths.append(result.snapshot.source_path)
            if division.citation_path not in seen_paths:
                seen_paths.add(division.citation_path)
                _append_division(
                    division,
                    snapshot=result.snapshot,
                    inventory=inventory,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    rule_count=len(result.rules),
                )
                division_count += 1
            for rule in result.rules:
                if rule.citation_path in seen_paths:
                    continue
                seen_paths.add(rule.citation_path)
                _append_rule(
                    rule,
                    snapshot=result.snapshot,
                    inventory=inventory,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                )
                rule_count += 1

    if len(records) <= 1:
        raise ValueError("no Oregon Administrative Rules provisions extracted")

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

    return OregonAdminRulesExtractReport(
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
        chapter_count=chapter_count,
        division_count=division_count,
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


def _snapshot_divisions(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    divisions: tuple[_Division, ...],
    source_root: Path | None,
    download_root: Path | None,
    workers: int,
    progress_stream: TextIO | None,
) -> tuple[_DivisionSnapshot, ...]:
    if workers <= 1:
        return tuple(
            _snapshot_division(
                store,
                run_id=run_id,
                division=division,
                source_root=source_root,
                download_root=download_root,
                progress_stream=progress_stream,
            )
            for division in divisions
        )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return tuple(
            executor.map(
                lambda division: _snapshot_division(
                    store,
                    run_id=run_id,
                    division=division,
                    source_root=source_root,
                    download_root=download_root,
                    progress_stream=progress_stream,
                ),
                divisions,
            )
        )


def _snapshot_division(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    division: _Division,
    source_root: Path | None,
    download_root: Path | None,
    progress_stream: TextIO | None,
) -> _DivisionSnapshot:
    _progress(progress_stream, f"oregon-admin-rules division {division.chapter.number}-{division.number}")
    try:
        snapshot = _snapshot_html(
            store,
            _session(),
            run_id=run_id,
            relative_name=(
                f"{_SOURCE_PREFIX}/divisions/"
                f"chapter-{_path_token(division.chapter.number)}-"
                f"division-{_path_token(division.number)}.html"
            ),
            url=division.source_url,
            source_root=source_root,
            download_root=download_root,
        )
        return _DivisionSnapshot(
            division=division,
            snapshot=snapshot,
            rules=_parse_rules(snapshot.content, division=division),
        )
    except (OSError, requests.RequestException) as exc:
        return _DivisionSnapshot(
            division=division,
            snapshot=None,
            rules=(),
            error=f"division {division.chapter.number}-{division.number}: {exc}",
        )


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": OREGON_ADMIN_RULES_USER_AGENT})
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
    source_path = store.source_path("us-or", DocumentClass.REGULATION, run_id, relative_name)
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


def _parse_chapters(content: bytes) -> tuple[_Chapter, ...]:
    soup = BeautifulSoup(content, "html.parser")
    chapters: list[_Chapter] = []
    for ordinal, option in enumerate(soup.select("select#selectedChapter option"), start=1):
        chapter_id = option.get("value")
        if not isinstance(chapter_id, str) or not chapter_id or chapter_id == "-1":
            continue
        text = _clean_text(option.get_text(" ", strip=True))
        match = _CHAPTER_OPTION_RE.match(text)
        if not match:
            continue
        chapters.append(
            _Chapter(
                chapter_id=chapter_id,
                number=match.group("number"),
                name=_clean_text(match.group("name")),
                ordinal=ordinal,
            )
        )
    return tuple(chapters)


def _parse_divisions(content: bytes, *, chapter: _Chapter) -> tuple[_Division, ...]:
    soup = BeautifulSoup(content, "html.parser")
    divisions: list[_Division] = []
    seen_ids: set[str] = set()
    for link in soup.select('a[href*="displayDivisionRules.action"]'):
        href = link.get("href")
        if not isinstance(href, str) or not href:
            continue
        division_id = _query_value(href, "selectedDivision")
        if not division_id or division_id in seen_ids:
            continue
        text = _clean_text(link.get_text(" ", strip=True))
        match = _DIVISION_LABEL_RE.match(text)
        if match:
            number = match.group("number")
            name = _clean_text(match.group("name"))
        else:
            number = _division_number_from_text(text)
            name = text.removeprefix(f"Division {number}").strip(" -") if number else text
        if not number:
            continue
        seen_ids.add(division_id)
        divisions.append(
            _Division(
                chapter=chapter,
                division_id=division_id,
                number=number,
                name=_clean_text(name),
                ordinal=len(divisions) + 1,
            )
        )
    return tuple(divisions)


def _parse_rules(content: bytes, *, division: _Division) -> tuple[_Rule, ...]:
    soup = BeautifulSoup(content, "html.parser")
    rules: list[_Rule] = []
    for block in soup.select("div.rule_div"):
        rule = _parse_rule_block(block, division=division, ordinal=len(rules) + 1)
        if rule is not None:
            rules.append(rule)
    return tuple(rules)


def _parse_rule_block(block: Tag, *, division: _Division, ordinal: int) -> _Rule | None:
    rule_link = block.select_one('a[href*="viewSingleRule.action"]')
    if rule_link is None:
        return None
    number = _clean_text(rule_link.get_text(" ", strip=True))
    if not number:
        return None
    header = rule_link.find_parent("p")
    heading = _rule_heading(header, fallback=number)
    body_parts: list[str] = []
    statutory_authority: str | None = None
    statutes_implemented: str | None = None
    history: str | None = None
    for paragraph in block.find_all("p", recursive=False):
        if paragraph is header:
            continue
        text = _clean_text(paragraph.get_text("\n", strip=True))
        if not text:
            continue
        if "Statutory/Other Authority:" in text or "History:" in text:
            statutory_authority = _metadata_value(text, "Statutory/Other Authority")
            statutes_implemented = _metadata_value(text, "Statutes/Other Implemented")
            history = _history_value(text)
            continue
        body_parts.append(text)
    body = _clean_body("\n\n".join(body_parts))
    references = _references_to("\n".join([body or "", statutory_authority or "", statutes_implemented or ""]))
    raw_href = rule_link.get("href")
    href = _canonical_oard_href(raw_href if isinstance(raw_href, str) else "")
    return _Rule(
        division=division,
        number=number,
        heading=heading,
        body=body,
        source_url=urljoin(OREGON_OARD_BASE_URL, href),
        source_id=_query_value(href, "ruleVrsnRsn"),
        statutory_authority=statutory_authority,
        statutes_implemented=statutes_implemented,
        history=history,
        references_to=references,
        ordinal=ordinal,
    )


def _rule_heading(header: Tag | None, *, fallback: str) -> str:
    if header is None:
        return fallback
    strongs = header.find_all("strong")
    for strong in strongs[1:]:
        text = _clean_text(strong.get_text(" ", strip=True))
        if text:
            return text
    text = _clean_text(header.get_text(" ", strip=True))
    return text.removeprefix(fallback).strip() or fallback


def _metadata_value(text: str, label: str) -> str | None:
    pattern = rf"{re.escape(label)}:\s*(?P<value>.*?)(?=\n?[A-Z][A-Za-z/ ]+?:|\n?History:|$)"
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return None
    return _clean_text(match.group("value"))


def _history_value(text: str) -> str | None:
    match = re.search(r"History:\s*(?P<value>.+)$", text, flags=re.S)
    if not match:
        return None
    return _clean_text(match.group("value"))


def _append_chapter(
    chapter: _Chapter,
    *,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    division_count: int,
) -> None:
    metadata: dict[str, object] = {
        "kind": "chapter",
        "chapter_id": chapter.chapter_id,
        "chapter_number": chapter.number,
        "source_as_of": source_as_of,
        "division_count": division_count,
    }
    inventory.append(
        SourceInventoryItem(
            citation_path=chapter.citation_path,
            source_url=chapter.source_url,
            source_path=snapshot.source_key,
            source_format=OREGON_ADMIN_RULES_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=chapter.citation_path,
            parent_citation_path="us-or/regulation",
            citation_label=f"OAR Chapter {chapter.number}",
            heading=chapter.heading,
            body=None,
            version=version,
            source_url=chapter.source_url,
            source_path=snapshot.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=1,
            ordinal=chapter.ordinal,
            kind="chapter",
            legal_identifier=f"OAR Chapter {chapter.number}",
            identifiers={"oregon:oar_chapter": chapter.number},
            metadata=metadata,
        )
    )


def _append_division(
    division: _Division,
    *,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    rule_count: int,
) -> None:
    metadata: dict[str, object] = {
        "kind": "division",
        "chapter_number": division.chapter.number,
        "division_id": division.division_id,
        "division_number": division.number,
        "source_as_of": source_as_of,
        "rule_count": rule_count,
    }
    inventory.append(
        SourceInventoryItem(
            citation_path=division.citation_path,
            source_url=division.source_url,
            source_path=snapshot.source_key,
            source_format=OREGON_ADMIN_RULES_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=division.citation_path,
            parent_citation_path=division.chapter.citation_path,
            citation_label=f"OAR Chapter {division.chapter.number}, Div. {division.number}",
            heading=division.heading,
            body=None,
            version=version,
            source_url=division.source_url,
            source_path=snapshot.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=2,
            ordinal=division.ordinal,
            kind="division",
            legal_identifier=f"OAR Chapter {division.chapter.number}, Division {division.number}",
            identifiers={
                "oregon:oar_chapter": division.chapter.number,
                "oregon:oar_division": division.number,
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
        "chapter_number": rule.division.chapter.number,
        "division_number": rule.division.number,
        "rule_number": rule.number,
        "statutory_authority": rule.statutory_authority,
        "statutes_implemented": rule.statutes_implemented,
        "history": rule.history,
        "references_to": list(rule.references_to),
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    inventory.append(
        SourceInventoryItem(
            citation_path=rule.citation_path,
            source_url=rule.source_url,
            source_path=snapshot.source_key,
            source_format=OREGON_ADMIN_RULES_SOURCE_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=rule.citation_path,
            parent_citation_path=rule.division.citation_path,
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
                "oregon:oar_chapter": rule.division.chapter.number,
                "oregon:oar_division": rule.division.number,
                "oregon:oar_rule": rule.number,
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
    selected_chapter_count: int,
    total_chapter_count: int,
) -> ProvisionRecord:
    return _record(
        citation_path="us-or/regulation",
        citation_label="Oregon Administrative Rules",
        heading="Oregon Administrative Rules",
        body=None,
        version=version,
        source_url=OREGON_ADMIN_RULES_SEARCH_URL,
        source_path=source_path,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=0,
        ordinal=0,
        kind="collection",
        legal_identifier="Oregon Administrative Rules",
        identifiers={"state:code": "OAR"},
        metadata={
            "selected_chapter_count": selected_chapter_count,
            "total_chapter_count": total_chapter_count,
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
        jurisdiction="us-or",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        citation_label=citation_label,
        heading=heading,
        body=body,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=source_id,
        source_format=OREGON_ADMIN_RULES_SOURCE_FORMAT,
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


def _references_to(text: str) -> tuple[str, ...]:
    refs: list[str] = []
    for match in _OAR_REF_RE.finditer(text):
        refs.append(f"us-or/regulation/rule-{_path_token(match.group(1))}")
    for match in _ORS_REF_RE.finditer(text):
        refs.append(f"us-or/statute/{match.group(1)}")
    return _unique(refs)


def _division_number_from_text(text: str) -> str | None:
    match = re.search(r"\bDivision\s+([A-Za-z0-9.-]+)\b", text, re.I)
    return match.group(1) if match else None


def _canonical_oard_href(href: str) -> str:
    cleaned = href
    if ";JSESSIONID_OARD=" in cleaned:
        before, after = cleaned.split(";JSESSIONID_OARD=", 1)
        query = after.split("?", 1)[1] if "?" in after else ""
        cleaned = f"{before}?{query}" if query else before
    return cleaned


def _query_value(href: str, name: str) -> str | None:
    parsed = urlparse(_canonical_oard_href(href))
    values = parse_qs(parsed.query).get(name)
    return values[0] if values else None


def _source_key(run_id: str, relative_name: str) -> str:
    return f"sources/us-or/regulation/{run_id}/{relative_name}"


def _path_token(value: str) -> str:
    token = _clean_text(value).lower()
    token = token.replace(".", "-")
    token = re.sub(r"[^a-z0-9]+", "-", token).strip("-")
    return safe_segment(token or "unknown")


def _same_token(left: str, right: str) -> bool:
    return _path_token(left) == _path_token(right)


def _clean_body(value: str) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_text(value: str) -> str:
    text = value.replace("\xa0", " ").replace("\ufffd", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
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
