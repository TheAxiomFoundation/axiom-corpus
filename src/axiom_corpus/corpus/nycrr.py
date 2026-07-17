"""New York Codes, Rules and Regulations source-first adapter."""

from __future__ import annotations

import re
import sys
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol, TextIO
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

NYCRR_BASE_URL = "https://govt.westlaw.com"
NYCRR_ROOT_URL = f"{NYCRR_BASE_URL}/nycrr/Browse/Index"
NYCRR_SOURCE_FORMAT = "nycrr-westlaw-html"
NYCRR_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_NYCRR_BROWSE_PATH = "/nycrr/Browse/Home/NewYork/UnofficialNewYorkCodesRulesandRegulations"
_BH_PARAMS = {
    "bhcp": "1",
    "bhab": "0",
    "bhav": "-1",
    "bhov": "-3",
    "bhqs": "1",
}
_MONTH_DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4}\b"
)


class _Response(Protocol):
    content: bytes
    text: str
    url: str

    def raise_for_status(self) -> None: ...


class _Session(Protocol):
    def get(self, url: str, *, timeout: int = 30) -> _Response: ...


@dataclass(frozen=True)
class NycrrExtractReport:
    """Result from a NYCRR extraction run."""

    jurisdiction: str
    document_class: str
    page_count: int
    browse_page_count: int
    document_page_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class NycrrPartSource:
    """One explicitly scoped NYCRR part browse page."""

    part: str
    citation_path: str
    source_url: str
    title: str | None = None
    expected_document_count: int | None = None
    expected_section_count: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _QueuedPage:
    url: str
    parent_citation_path: str | None
    link_text: str | None
    ordinal: int | None


@dataclass(frozen=True)
class _FetchedPage:
    url: str
    html: str
    sha256: str
    source_path: Path
    source_key: str


def nycrr_run_id(
    version: str,
    *,
    only_title: int | None = None,
    limit: int | None = None,
) -> str:
    """Return a scoped NYCRR run id."""
    parts = [version]
    if only_title is not None:
        parts.append(f"title-{only_title}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def extract_nycrr(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: int | None = None,
    limit: int | None = None,
    delay_seconds: float = 0.25,
    retry_attempts: int = 4,
    refresh: bool = False,
    session: _Session | None = None,
    progress_stream: TextIO | None = None,
) -> NycrrExtractReport:
    """Snapshot the public NYCRR browse tree and extract normalized provisions."""
    run_id = nycrr_run_id(version, only_title=only_title, limit=limit)
    client = _nycrr_session(session)
    expression_date_text = _date_text(expression_date, version)
    source_as_of_text = source_as_of or version

    root_url = _normalize_url(
        NYCRR_ROOT_URL,
        include_browserhawk=True,
        extra_query={"transitionType": "Default", "contextData": "(sc.Default)"},
    )
    queue: deque[_QueuedPage] = deque(
        [_QueuedPage(root_url, None, "Unofficial New York Codes, Rules and Regulations", 0)]
    )
    queued: set[str] = {root_url}
    seen: set[str] = set()
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    source_paths: list[Path] = []
    browse_page_count = 0
    document_page_count = 0

    while queue:
        if limit is not None and len(records) >= limit:
            break
        page = queue.popleft()
        if page.url in seen:
            continue
        seen.add(page.url)
        fetched = _read_or_fetch_page(
            store,
            client,
            run_id,
            page.url,
            refresh=refresh,
            delay_seconds=delay_seconds,
            retry_attempts=retry_attempts,
        )
        source_paths.append(fetched.source_path)
        soup = BeautifulSoup(fetched.html, "lxml")
        _raise_if_browserhawk_blocked(soup, page.url)
        page_type = "document" if soup.select_one("#co_document") else "browse"
        if page_type == "document":
            document_page_count += 1
        else:
            browse_page_count += 1
        citation_path = _citation_path_for_page(soup, page, page_type)
        if citation_path in {record.citation_path for record in records}:
            citation_path = f"{citation_path}@{_page_guid(page.url) or len(records) + 1}"
        metadata = _page_metadata(soup, page, page_type, fetched.url)
        items.append(
            SourceInventoryItem(
                citation_path=citation_path,
                source_url=_display_url(fetched.url),
                source_path=fetched.source_key,
                source_format=NYCRR_SOURCE_FORMAT,
                sha256=fetched.sha256,
                metadata=metadata,
            )
        )
        records.append(
            _provision_record(
                soup,
                citation_path=citation_path,
                parent_citation_path=page.parent_citation_path,
                version=run_id,
                source_url=_display_url(fetched.url),
                source_path=fetched.source_key,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                page_type=page_type,
                metadata=metadata,
                ordinal=page.ordinal,
            )
        )

        if progress_stream is not None and len(records) % 100 == 0:
            print(
                f"nycrr extracted {len(records)} pages "
                f"({browse_page_count} browse, {document_page_count} documents)",
                file=progress_stream,
                flush=True,
            )

        if limit is not None and len(records) >= limit:
            break
        if page_type != "document":
            child_links = _child_links(
                soup,
                only_title=only_title if citation_path == _root_path() else None,
            )
            for ordinal, (href, text) in enumerate(child_links, start=1):
                child_url = _normalize_url(href, include_browserhawk=True)
                if child_url is None or child_url in seen or child_url in queued:
                    continue
                queued.add(child_url)
                queue.append(_QueuedPage(child_url, citation_path, text, ordinal))

    inventory_path = store.inventory_path("us-ny", DocumentClass.REGULATION, run_id)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path("us-ny", DocumentClass.REGULATION, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction="us-ny",
        document_class=DocumentClass.REGULATION.value,
        version=run_id,
    )
    coverage_path = store.coverage_path("us-ny", DocumentClass.REGULATION, run_id)
    store.write_json(coverage_path, coverage.to_mapping())
    return NycrrExtractReport(
        jurisdiction="us-ny",
        document_class=DocumentClass.REGULATION.value,
        page_count=len(records),
        browse_page_count=browse_page_count,
        document_page_count=document_page_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


def extract_nycrr_parts(
    store: CorpusArtifactStore,
    *,
    version: str,
    part_sources: Sequence[NycrrPartSource],
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    delay_seconds: float = 0.25,
    retry_attempts: int = 4,
    refresh: bool = False,
    session: _Session | None = None,
    progress_stream: TextIO | None = None,
) -> NycrrExtractReport:
    """Extract explicit NYCRR parts and their complete nested provision trees."""
    if not part_sources:
        raise ValueError("at least one NYCRR part source is required")

    client = _nycrr_session(session)
    expression_date_text = _date_text(expression_date, version)
    source_as_of_text = source_as_of or version
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    source_paths: list[Path] = []
    seen_paths: set[str] = set()
    browse_page_count = 0
    document_page_count = 0

    for source in part_sources:
        part_url = _normalize_url(source.source_url, include_browserhawk=True)
        if part_url is None:
            raise ValueError(f"unsupported NYCRR part URL: {source.source_url}")
        part_page = _QueuedPage(
            part_url,
            None,
            source.title or f"Part {source.part}",
            _outline_ordinal(source.part, 0),
        )
        fetched_part = _read_or_fetch_page(
            store,
            client,
            version,
            part_url,
            refresh=refresh,
            delay_seconds=delay_seconds,
            retry_attempts=retry_attempts,
        )
        source_paths.append(fetched_part.source_path)
        part_soup = BeautifulSoup(fetched_part.html, "lxml")
        _raise_if_browserhawk_blocked(part_soup, part_url)
        part_heading = _page_heading(part_soup, source.title)
        if not part_heading or not re.match(
            rf"^Part\s+{re.escape(source.part)}(?:\D|$)", part_heading
        ):
            raise RuntimeError(
                f"NYCRR source did not resolve to Part {source.part}: {part_heading!r}"
            )
        part_metadata = _scoped_part_metadata(
            _page_metadata(part_soup, part_page, "browse", fetched_part.url),
            source,
            source_as_of_text,
        )
        part_record = _provision_record(
            part_soup,
            citation_path=source.citation_path,
            parent_citation_path=None,
            version=version,
            source_url=_display_url(fetched_part.url),
            source_path=fetched_part.source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            page_type="browse",
            metadata=part_metadata,
            ordinal=_outline_ordinal(source.part, 0),
        )
        _append_scoped_record(
            items,
            records,
            seen_paths,
            part_record,
            fetched_part,
        )
        browse_page_count += 1

        child_links = _part_child_links(part_soup)
        section_count = sum(
            link_text.lower().startswith(f"s {source.part}.")
            for _, link_text in child_links
        )
        if (
            source.expected_document_count is not None
            and len(child_links) != source.expected_document_count
        ):
            raise RuntimeError(
                f"Part {source.part} exposed {len(child_links)} documents; "
                f"expected {source.expected_document_count}"
            )
        if (
            source.expected_section_count is not None
            and section_count != source.expected_section_count
        ):
            raise RuntimeError(
                f"Part {source.part} exposed {section_count} rule sections; "
                f"expected {source.expected_section_count}"
            )

        for child_ordinal, (href, link_text) in enumerate(child_links, start=1):
            child_url = _normalize_url(href, include_browserhawk=True)
            if child_url is None:
                raise RuntimeError(f"unsupported NYCRR child URL: {href}")
            child_page = _QueuedPage(
                child_url,
                source.citation_path,
                link_text,
                child_ordinal,
            )
            fetched_child = _read_or_fetch_page(
                store,
                client,
                version,
                child_url,
                refresh=refresh,
                delay_seconds=delay_seconds,
                retry_attempts=retry_attempts,
            )
            source_paths.append(fetched_child.source_path)
            child_soup = BeautifulSoup(fetched_child.html, "lxml")
            _raise_if_browserhawk_blocked(child_soup, child_url)
            if child_soup.select_one("#co_document") is None:
                raise RuntimeError(f"NYCRR part child was not a document: {child_url}")
            child_metadata = _scoped_part_metadata(
                _page_metadata(child_soup, child_page, "document", fetched_child.url),
                source,
                source_as_of_text,
            )
            child_path = _part_child_citation_path(
                child_soup,
                part=source.part,
                part_citation_path=source.citation_path,
                link_text=link_text,
            )
            child_record = _provision_record(
                child_soup,
                citation_path=child_path,
                parent_citation_path=source.citation_path,
                version=version,
                source_url=_display_url(fetched_child.url),
                source_path=fetched_child.source_key,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                page_type="document",
                metadata=child_metadata,
                ordinal=child_ordinal,
            )
            _append_scoped_record(
                items,
                records,
                seen_paths,
                child_record,
                fetched_child,
            )
            for nested_record in _nested_nycrr_provisions(child_soup, child_record):
                _append_scoped_record(
                    items,
                    records,
                    seen_paths,
                    nested_record,
                    fetched_child,
                )
            document_page_count += 1

            if progress_stream is not None:
                print(
                    f"nycrr parts extracted {source.part} child {child_ordinal} "
                    f"({len(records)} provisions)",
                    file=progress_stream,
                    flush=True,
                )

    inventory_path = store.inventory_path("us-ny", DocumentClass.REGULATION, version)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path("us-ny", DocumentClass.REGULATION, version)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction="us-ny",
        document_class=DocumentClass.REGULATION.value,
        version=version,
    )
    coverage_path = store.coverage_path("us-ny", DocumentClass.REGULATION, version)
    store.write_json(coverage_path, coverage.to_mapping())
    return NycrrExtractReport(
        jurisdiction="us-ny",
        document_class=DocumentClass.REGULATION.value,
        page_count=len(records),
        browse_page_count=browse_page_count,
        document_page_count=document_page_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


def _scoped_part_metadata(
    page_metadata: Mapping[str, Any],
    source: NycrrPartSource,
    verified_current_on: str,
) -> dict[str, Any]:
    return {
        **page_metadata,
        **source.metadata,
        "primary_source": True,
        "source_authority": "New York State Department of State",
        "administering_agency": (
            "New York State Office of Temporary and Disability Assistance"
        ),
        "program": "SNAP",
        "federal_program": "SNAP",
        "part_number": source.part,
        "part_citation_path": source.citation_path,
        "verified_current_on": verified_current_on,
    }


def _append_scoped_record(
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    seen_paths: set[str],
    record: ProvisionRecord,
    fetched: _FetchedPage,
) -> None:
    if record.citation_path in seen_paths:
        raise RuntimeError(f"duplicate NYCRR citation path: {record.citation_path}")
    seen_paths.add(record.citation_path)
    records.append(record)
    items.append(
        SourceInventoryItem(
            citation_path=record.citation_path,
            source_url=record.source_url,
            source_path=fetched.source_key,
            source_format=NYCRR_SOURCE_FORMAT,
            sha256=fetched.sha256,
            metadata=record.metadata,
        )
    )


def _part_child_links(soup: BeautifulSoup) -> tuple[tuple[str, str], ...]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("section.co_innertube a[href^='/nycrr/Document/']"):
        href = anchor.get("href") or ""
        text = _clean_text(anchor.get_text(" ", strip=True))
        if not text or href in seen:
            continue
        seen.add(href)
        links.append((href, text))
    return tuple(links)


def _part_child_citation_path(
    soup: BeautifulSoup,
    *,
    part: str,
    part_citation_path: str,
    link_text: str,
) -> str:
    citation = _citation_label(soup)
    if citation:
        match = re.match(
            rf"^\s*\d+\s+CRR-NY\s+{re.escape(part)}\.(?P<section>[A-Za-z0-9.-]+)\s*$",
            citation,
        )
        if match:
            return f"{part_citation_path}/{_slug(match.group('section'))}"
    lowered = link_text.lower()
    if lowered.endswith(" notes"):
        return f"{part_citation_path}/notes"
    if lowered.endswith(" refs"):
        return f"{part_citation_path}/refs"
    raise RuntimeError(
        f"unable to derive Part {part} citation from {citation!r} / {link_text!r}"
    )


def _nested_nycrr_provisions(
    soup: BeautifulSoup,
    section_record: ProvisionRecord,
) -> tuple[ProvisionRecord, ...]:
    body = soup.select_one("#co_document .co_contentBlock.co_body")
    if body is None or section_record.citation_label is None:
        return ()

    blocks: list[tuple[int, str | None, str]] = []
    for text_block in body.select(
        ".co_subsection > .co_headtext, .co_paragraphText"
    ):
        text = _direct_paragraph_text(text_block)
        if not text:
            continue
        depth = _paragraph_depth(text_block.get("class", ()))
        marker = re.match(r"^\(\s*(?P<label>[A-Za-z0-9-]+)\s*\)", text)
        blocks.append((depth, marker.group("label").lower() if marker else None, text))

    output: list[ProvisionRecord] = []
    labels: list[str] = []
    for index, (raw_depth, label, text) in enumerate(blocks):
        if label is None:
            continue
        depth = min(raw_depth, len(labels) + 1)
        labels = [*labels[: depth - 1], label]
        path_labels = tuple(labels)
        end = len(blocks)
        for next_index in range(index + 1, len(blocks)):
            next_depth, next_label, _ = blocks[next_index]
            if next_label is not None and next_depth <= depth:
                end = next_index
                break
        provision_body = "\n".join(block[2] for block in blocks[index:end])
        citation_path = f"{section_record.citation_path}/{'/'.join(path_labels)}"
        citation_label = section_record.citation_label + "".join(
            f"({path_label})" for path_label in path_labels
        )
        parent_path = (
            section_record.citation_path
            if depth == 1
            else f"{section_record.citation_path}/{'/'.join(path_labels[:-1])}"
        )
        metadata = {
            **section_record.metadata,
            "outline_depth": depth,
            "outline_label": label,
            "outline_path": list(path_labels),
            "source_section_citation_path": section_record.citation_path,
        }
        output.append(
            ProvisionRecord(
                jurisdiction=section_record.jurisdiction,
                document_class=section_record.document_class,
                citation_path=citation_path,
                id=deterministic_provision_id(citation_path),
                body=provision_body,
                heading=_nested_heading(text, label),
                citation_label=citation_label,
                version=section_record.version,
                source_url=section_record.source_url,
                source_path=section_record.source_path,
                source_id=section_record.source_id,
                source_format=section_record.source_format,
                source_document_id=section_record.id,
                source_as_of=section_record.source_as_of,
                expression_date=section_record.expression_date,
                parent_citation_path=parent_path,
                parent_id=deterministic_provision_id(parent_path),
                level=_level(citation_path),
                ordinal=_outline_ordinal(label, depth),
                kind=_outline_kind(depth),
                legal_identifier=citation_label,
                identifiers={
                    **section_record.identifiers,
                    "nycrr:outline": "/".join(path_labels),
                },
                metadata=metadata,
            )
        )
    return tuple(output)


def _direct_paragraph_text(text_block: Any) -> str:
    strings = []
    is_paragraph_text = "co_paragraphText" in (text_block.get("class") or ())
    for value in text_block.find_all(string=True):
        nearest_paragraph = value.find_parent(class_="co_paragraphText")
        if not is_paragraph_text or nearest_paragraph is text_block:
            strings.append(str(value))
    return _clean_text(" ".join(strings))


def _paragraph_depth(classes: Sequence[str]) -> int:
    for class_name in classes:
        if match := re.fullmatch(r"co_indentLeft(?P<indent>\d+)", class_name):
            return int(match.group("indent")) // 2 + 1
    return 1


def _nested_heading(text: str, label: str) -> str:
    without_marker = re.sub(
        rf"^\(\s*{re.escape(label)}\s*\)\s*", "", text, count=1
    )
    first_line = without_marker.split("\n", 1)[0]
    sentence = re.split(r"(?<=[.!?])\s+", first_line, maxsplit=1)[0]
    return sentence[:240].rstrip()


def _outline_kind(depth: int) -> str:
    return {
        1: "subdivision",
        2: "paragraph",
        3: "subparagraph",
        4: "clause",
        5: "subclause",
    }.get(depth, "item")


def _outline_ordinal(label: str, depth: int) -> int | None:
    if label.isdigit():
        return int(label)
    if depth in {3, 6} and re.fullmatch(r"[ivxlcdm]+", label):
        values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
        total = 0
        previous = 0
        for character in reversed(label.lower()):
            value = values[character]
            total += -value if value < previous else value
            previous = max(previous, value)
        return total
    if len(label) == 1 and label.isalpha():
        return ord(label.lower()) - ord("a") + 1
    return None


def _nycrr_session(session: _Session | None = None) -> _Session:
    if session is not None:
        return session
    real_session = requests.Session()
    real_session.headers.update({"User-Agent": NYCRR_USER_AGENT})
    real_session.cookies.set("bhCookieSess", "1", domain=".govt.westlaw.com", path="/")
    real_session.cookies.set("bhCookiePerm", "1", domain=".govt.westlaw.com", path="/")
    return real_session


def _read_or_fetch_page(
    store: CorpusArtifactStore,
    session: _Session,
    run_id: str,
    url: str,
    *,
    refresh: bool,
    delay_seconds: float,
    retry_attempts: int,
) -> _FetchedPage:
    relative_name = _source_relative_name(url)
    source_path = store.source_path("us-ny", DocumentClass.REGULATION, run_id, relative_name)
    source_key = f"sources/us-ny/{DocumentClass.REGULATION.value}/{run_id}/{relative_name}"
    if source_path.exists() and not refresh:
        html_bytes = source_path.read_bytes()
        return _FetchedPage(url, html_bytes.decode("utf-8", errors="replace"), sha256_bytes(html_bytes), source_path, source_key)
    response = _get_with_retries(
        session,
        url,
        delay_seconds=delay_seconds,
        retry_attempts=retry_attempts,
    )
    html_bytes = response.content
    sha256 = store.write_bytes(source_path, html_bytes)
    return _FetchedPage(response.url or url, response.text, sha256, source_path, source_key)


def _get_with_retries(
    session: _Session,
    url: str,
    *,
    delay_seconds: float,
    retry_attempts: int,
) -> _Response:
    attempts = max(1, retry_attempts)
    for attempt in range(attempts):
        if delay_seconds > 0:
            time.sleep(delay_seconds if attempt == 0 else delay_seconds * (2 ** attempt))
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt + 1 >= attempts:
                raise
    raise RuntimeError("unreachable NYCRR retry loop")


def _normalize_url(
    href: str,
    *,
    include_browserhawk: bool,
    extra_query: Mapping[str, str] | None = None,
) -> str | None:
    url = urljoin(NYCRR_BASE_URL, href.replace("&amp;", "&"))
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if extra_query:
        query.update(extra_query)
    path = parsed.path
    if path == _NYCRR_BROWSE_PATH and "guid" not in query:
        return None
    if not (
        path == "/nycrr/Browse/Index"
        or path == _NYCRR_BROWSE_PATH
        or path.startswith("/nycrr/Document/")
    ):
        return None
    keep_keys = ["guid", "viewType", "originationContext", "transitionType", "contextData"]
    kept = {key: query[key] for key in keep_keys if key in query}
    if include_browserhawk:
        kept.update(_BH_PARAMS)
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(kept), ""))


def _display_url(url: str) -> str:
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key in _BH_PARAMS:
        query.pop(key, None)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


def _source_relative_name(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.path.startswith("/nycrr/Document/"):
        return f"nycrr/document/{parsed.path.rsplit('/', 1)[-1]}.html"
    if parsed.path == "/nycrr/Browse/Index":
        return "nycrr/browse/index.html"
    guid = _page_guid(url)
    if guid:
        return f"nycrr/browse/{guid}.html"
    return "nycrr/browse/unknown.html"


def _page_guid(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.path.startswith("/nycrr/Document/"):
        return parsed.path.rsplit("/", 1)[-1]
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return query.get("guid")


def _child_links(
    soup: BeautifulSoup,
    *,
    only_title: int | None = None,
) -> tuple[tuple[str, str], ...]:
    links: list[tuple[str, str]] = []
    for anchor in soup.select("section.co_innertube a[href]"):
        href = anchor.get("href") or ""
        text = _clean_text(anchor.get_text(" ", strip=True))
        if not text:
            continue
        if not (
            href.startswith("/nycrr/Browse/Home/NewYork/UnofficialNewYorkCodesRulesandRegulations")
            or href.startswith("/nycrr/Document/")
        ):
            continue
        if only_title is not None and not text.startswith(f"Title {only_title} "):
            continue
        links.append((href, text))
    return tuple(links)


def _citation_path_for_page(
    soup: BeautifulSoup,
    page: _QueuedPage,
    page_type: str,
) -> str:
    if page.parent_citation_path is None:
        return _root_path()
    if page_type == "document":
        return _document_citation_path(soup, page.parent_citation_path, page.link_text)
    heading = _page_heading(soup, page.link_text)
    return f"{page.parent_citation_path}/{_heading_token(heading)}"


def _root_path() -> str:
    return "us-ny/regulation"


def _document_citation_path(
    soup: BeautifulSoup,
    parent_citation_path: str,
    link_text: str | None,
) -> str:
    citation = _citation_label(soup)
    token = None
    if citation:
        match = re.match(r"^\s*(?P<title>\d+)\s+CRR-NY\s+(?P<section>.+?)\s*$", citation)
        if match:
            token = _slug(match.group("section").split(",", 1)[0])
    if not token and link_text:
        section_match = re.match(r"^s\s+([A-Za-z0-9.:-]+)", link_text.strip())
        token = _slug(section_match.group(1) if section_match else link_text)
    return f"{parent_citation_path}/{token or 'document'}"


def _heading_token(heading: str | None) -> str:
    text = heading or "node"
    match = re.match(
        r"^(Title|Chapter|Subchapter|Article|Part)\s+([A-Za-z0-9.IVXLCivxlc-]+)",
        text.strip(),
    )
    if match:
        return f"{match.group(1).lower()}-{_slug(match.group(2).rstrip('.'))}"
    return _slug(text)


def _page_heading(soup: BeautifulSoup, fallback: str | None = None) -> str | None:
    if soup.select_one("#co_document"):
        title = soup.select_one("#co_document .co_title .co_headtext")
        if title:
            return _clean_text(title.get_text(" ", strip=True))
    h1 = soup.find("h1")
    if h1:
        return _clean_text(h1.get_text(" ", strip=True))
    return fallback


def _citation_label(soup: BeautifulSoup) -> str | None:
    citation = soup.select_one("#citation")
    if citation:
        return _clean_text(citation.get_text(" ", strip=True))
    return None


def _provision_record(
    soup: BeautifulSoup,
    *,
    citation_path: str,
    parent_citation_path: str | None,
    version: str,
    source_url: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    page_type: str,
    metadata: dict[str, Any],
    ordinal: int | None,
) -> ProvisionRecord:
    current_through = metadata.get("current_through")
    heading = _page_heading(soup, metadata.get("link_text"))
    citation_label = _citation_label(soup)
    return ProvisionRecord(
        jurisdiction="us-ny",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        id=deterministic_provision_id(citation_path),
        body=_document_body(soup) if page_type == "document" else None,
        heading=heading,
        citation_label=citation_label,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id="nycrr-westlaw",
        source_format=NYCRR_SOURCE_FORMAT,
        source_document_id=None,
        source_as_of=str(current_through or source_as_of),
        expression_date=expression_date,
        parent_citation_path=parent_citation_path,
        parent_id=deterministic_provision_id(parent_citation_path) if parent_citation_path else None,
        level=_level(citation_path),
        ordinal=ordinal,
        kind=_record_kind(page_type, heading, citation_label, citation_path),
        legal_identifier=citation_label or heading,
        identifiers=_identifiers(metadata, citation_label, heading),
        metadata=metadata,
    )


def _page_metadata(
    soup: BeautifulSoup,
    page: _QueuedPage,
    page_type: str,
    fetched_url: str,
) -> dict[str, Any]:
    heading = _page_heading(soup, page.link_text)
    metadata: dict[str, Any] = {
        "source": "New York Department of State NYCRR, published via Thomson Reuters Westlaw",
        "source_caveat": "Online NYCRR is unofficial and not for evidentiary use.",
        "page_type": page_type,
        "guid": _page_guid(fetched_url),
        "link_text": page.link_text,
        "heading": heading,
        "fetched_url": fetched_url,
    }
    current_through = _current_through(soup)
    if current_through:
        metadata["current_through"] = current_through
    citation = _citation_label(soup)
    if citation:
        metadata["citation"] = citation
    return {key: value for key, value in metadata.items() if value is not None}


def _document_body(soup: BeautifulSoup) -> str | None:
    body = soup.select_one("#co_document .co_contentBlock.co_body")
    if body is None:
        return None
    text = _clean_multiline_text(body.get_text("\n", strip=True))
    return text or None


def _current_through(soup: BeautifulSoup) -> str | None:
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"Current through\s+(.+?)(?:\s+End of Document|\s+IMPORTANT NOTE|$)", text)
    if not match:
        return None
    date_match = _MONTH_DATE_PATTERN.search(match.group(1))
    if not date_match:
        return None
    return datetime.strptime(date_match.group(0), "%B %d, %Y").date().isoformat()


def _record_kind(
    page_type: str,
    heading: str | None,
    citation_label: str | None,
    citation_path: str,
) -> str:
    if citation_path == _root_path():
        return "collection"
    if page_type == "document":
        if citation_label and re.search(r"\d+\s+CRR-NY\s+\d", citation_label):
            return "section"
        return "document"
    token = _heading_token(heading)
    return token.split("-", 1)[0] if "-" in token else "collection"


def _identifiers(
    metadata: Mapping[str, Any],
    citation_label: str | None,
    heading: str | None,
) -> dict[str, str]:
    identifiers: dict[str, str] = {}
    guid = metadata.get("guid")
    if guid:
        identifiers["nycrr:guid"] = str(guid)
    if citation_label:
        identifiers["nycrr:citation"] = citation_label
        match = re.match(r"^\s*(?P<title>\d+)\s+CRR-NY\s+(?P<section>.+?)\s*$", citation_label)
        if match:
            identifiers["nycrr:title"] = match.group("title")
            identifiers["nycrr:section"] = match.group("section")
    if heading:
        heading_match = re.match(r"^(Title|Chapter|Subchapter|Article|Part)\s+(.+)$", heading)
        if heading_match:
            identifiers[f"nycrr:{heading_match.group(1).lower()}"] = heading_match.group(2)
    return identifiers


def _level(citation_path: str) -> int:
    return max(0, len(citation_path.split("/")) - 2)


def _raise_if_browserhawk_blocked(soup: BeautifulSoup, url: str) -> None:
    h1 = soup.find("h1")
    heading = h1.get_text(" ", strip=True) if h1 else ""
    if "not optimized for Weblinks" in heading:
        raise RuntimeError(f"NYCRR BrowserHawk validation did not complete for {url}")


def _date_text(value: date | str | None, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, date):
        return value.isoformat()
    return value


def _slug(value: str) -> str:
    lowered = value.strip().lower().replace("§", "s")
    lowered = lowered.replace("—", "-").replace("–", "-")
    slug = re.sub(r"[^a-z0-9.]+", "-", lowered).strip("-")
    return slug or "node"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_multiline_text(value: str) -> str:
    lines = [_clean_text(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


if __name__ == "__main__":  # pragma: no cover
    report = extract_nycrr(
        CorpusArtifactStore(Path("data/corpus")),
        version=date.today().isoformat(),
        progress_stream=sys.stderr,
    )
    print(report)
