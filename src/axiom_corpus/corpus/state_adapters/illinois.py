"""Illinois ILCS source-first corpus adapter."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urljoin

import requests
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

ILLINOIS_ILCS_BASE_URL = "https://www.ilga.gov/ftp/ILCS/"
ILLINOIS_ILCS_FULLTEXT_URL = "https://www.ilga.gov/legislation/ilcs/fulltext.asp"
ILLINOIS_ILCS_SOURCE_FORMAT = "illinois-ilcs-html"
ILLINOIS_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
ILLINOIS_REQUEST_HEADERS = {
    "User-Agent": ILLINOIS_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_DOC_NAME_RE = re.compile(
    r"^(?P<chapter>\d{4})(?P<act>\d{5})(?P<doc_type>[AFHK])(?P<identifier>.*?)(?:\.html?)?$",
    re.IGNORECASE,
)
_DOC_TOKEN_RE = re.compile(r"\b\d{9}[AFHK][A-Za-z0-9.\-]*\b(?!\.\s)")
_HREF_RE = re.compile(r"""href\s*=\s*["'](?P<href>[^"']+)["']""", re.IGNORECASE)
_ILCS_CITATION_RE = re.compile(
    r"\((?P<chapter>\d+)\s+ILCS\s+(?P<act>\d+)\s*/\s*(?P<section>[^)]+)\)"
)
_SECTION_HEADING_RE = re.compile(r"^(?:Sec\.|Section)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class IllinoisIlcsDocumentName:
    """Parsed ILCS FTP document file name."""

    stem: str
    chapter: str
    act: str
    doc_type: str
    identifier: str

    @property
    def chapter_int(self) -> int:
        return int(self.chapter)

    @property
    def act_int(self) -> int:
        value = int(self.act)
        if self.act.endswith("0"):
            return value // 10
        return value

    @property
    def section(self) -> str | None:
        if self.doc_type != "K":
            return None
        return self.identifier or None

    @property
    def citation(self) -> str | None:
        if self.section is None:
            return None
        return f"{self.chapter_int} ILCS {self.act_int}/{self.section}"

    @property
    def citation_path(self) -> str:
        base = f"us-il/statute/{self.chapter_int}/{self.act_int}"
        if self.section is None:
            return base
        return f"{base}/{self.section}"

    @property
    def act_citation_path(self) -> str:
        return f"us-il/statute/{self.chapter_int}/{self.act_int}"

    @property
    def chapter_citation_path(self) -> str:
        return f"us-il/statute/{self.chapter_int}"


@dataclass(frozen=True)
class IllinoisIlcsSection:
    document: IllinoisIlcsDocumentName
    citation: str
    section: str
    heading: str | None
    body: str
    references_to: tuple[str, ...]

    @property
    def citation_path(self) -> str:
        return f"us-il/statute/{self.document.chapter_int}/{self.document.act_int}/{self.section}"


@dataclass(frozen=True)
class _IllinoisListing:
    """A remote page that names ILCS documents: the Section Sequence file,
    the ILCS index, or an act directory."""

    relative_name: str
    source_url: str
    data: bytes


@dataclass(frozen=True)
class _IllinoisRemoteFailure:
    """A listed ILCS document the remote run could not fetch."""

    document: IllinoisIlcsDocumentName
    relative_name: str
    source_url: str
    listing: _IllinoisListing | None


def parse_illinois_ilcs_doc_name(value: str) -> IllinoisIlcsDocumentName:
    """Parse an official ILCS FTP document token or HTML file name."""
    name = Path(unquote(value)).name
    stem = name.rsplit(".", 1)[0]
    match = _DOC_NAME_RE.match(name)
    if not match:
        raise ValueError(f"not an ILCS document name: {value!r}")
    return IllinoisIlcsDocumentName(
        stem=stem,
        chapter=match.group("chapter"),
        act=match.group("act"),
        doc_type=match.group("doc_type").upper(),
        identifier=match.group("identifier"),
    )


def parse_illinois_ilcs_links(text: str) -> tuple[str, ...]:
    """Extract ILCS document links or document tokens from FTP index/readme text."""
    links: list[str] = []
    seen: set[str] = set()
    seen_stems: set[str] = set()
    for href in _HREF_RE.findall(text):
        decoded = unquote(href)
        if (
            decoded.lower().endswith((".html", ".htm"))
            and _looks_like_ilcs_path(decoded)
            and decoded not in seen
        ):
            seen.add(decoded)
            seen_stems.add(parse_illinois_ilcs_doc_name(decoded).stem)
            links.append(decoded)
    token_source = re.sub(r"<a\b[^>]*>.*?</a>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    for token in _DOC_TOKEN_RE.findall(token_source):
        stem = token.rsplit(".", 1)[0] if token.lower().endswith(".html") else token
        decoded = f"{stem}.html"
        if decoded not in seen and stem not in seen_stems:
            seen.add(decoded)
            seen_stems.add(stem)
            links.append(decoded)
    return tuple(links)


def parse_illinois_section_sequence(text: str) -> dict[str, int]:
    """Return official Section Sequence ordering by document stem."""
    sequence: dict[str, int] = {}
    for token in _DOC_TOKEN_RE.findall(text):
        stem = token.rsplit(".", 1)[0] if token.lower().endswith(".html") else token
        if stem not in sequence:
            sequence[stem] = len(sequence)
    return sequence


def parse_illinois_ilcs_section(
    html: str | bytes,
    *,
    document: IllinoisIlcsDocumentName,
) -> IllinoisIlcsSection:
    """Extract the canonical citation, heading, body, and references from an ILCS section page.

    A page without an ILCS citation is read under the document's own citation
    only when a line opens with that section's heading (``Sec. 3.``). A page
    with neither holds no section (a maintenance, empty or wrong-shape page),
    so it raises ``ValueError`` instead of becoming the section's text.
    """
    text = _html_text(html)
    citation_match = _ILCS_CITATION_RE.search(text)
    if citation_match:
        chapter = citation_match.group("chapter")
        act = citation_match.group("act")
        section = citation_match.group("section").strip()
        citation = f"{chapter} ILCS {act}/{section}"
    elif not document.citation:
        raise ValueError(f"ILCS section page has no citation: {document.stem}")
    elif _names_section(text, document.section or ""):
        section = document.section or ""
        citation = document.citation
    else:
        raise ValueError(f"ILCS section page names no section: {document.stem}")

    heading = _section_heading(text, section)
    references = tuple(
        f"{match.group('chapter')} ILCS {match.group('act')}/{match.group('section').strip()}"
        for match in _ILCS_CITATION_RE.finditer(text)
    )
    return IllinoisIlcsSection(
        document=document,
        citation=citation,
        section=section,
        heading=heading,
        body=text,
        references_to=tuple(dict.fromkeys(ref for ref in references if ref != citation)),
    )


def extract_illinois_ilcs(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_chapter: str | int | None = None,
    only_act: str | int | None = None,
    limit: int | None = None,
    workers: int = 8,
    base_url: str = ILLINOIS_ILCS_BASE_URL,
) -> StateStatuteExtractReport:
    """Snapshot official Illinois ILCS HTML and extract normalized provisions."""
    jurisdiction = "us-il"
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    chapter_filter = int(only_chapter) if only_chapter is not None else None
    act_filter = int(only_act) if only_act is not None else None
    run_id = _illinois_run_id(
        version,
        jurisdiction=jurisdiction,
        chapter_filter=chapter_filter,
        act_filter=act_filter,
        limit=limit,
    )

    source_root = Path(source_dir) if source_dir is not None else None
    sequence_listing: _IllinoisListing | None = None
    if source_root is not None:
        sequence = _load_local_section_sequence(source_root)
    else:
        sequence, sequence_listing = _fetch_remote_section_sequence(base_url)
    remote_errors: list[str] = []
    remote_failures: list[_IllinoisRemoteFailure] = []
    if source_root is not None:
        source_entries: Iterable[tuple[IllinoisIlcsDocumentName, str, str | None, bytes]] = tuple(
            sorted(
                _discover_local_sources(source_root),
                key=lambda entry: _source_sort_key(entry[0], entry[1], sequence),
            )
        )
    else:
        source_entries = _iter_remote_sources(
            base_url,
            limit=limit,
            chapter_filter=chapter_filter,
            act_filter=act_filter,
            sequence=sequence,
            workers=workers,
            errors=remote_errors,
            failures=remote_failures,
            sequence_listing=sequence_listing,
        )

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    source_paths: list[Path] = []
    seen: set[str] = set()
    title_count = 0
    container_count = 0
    section_count = 0
    skipped_source_count = 0
    errors: list[str] = []
    remaining = limit
    unread_sections: list[SourceInventoryItem] = []

    for document, relative_name, source_url, data in source_entries:
        if remaining is not None and remaining <= 0:
            break
        if chapter_filter is not None and document.chapter_int != chapter_filter:
            continue
        if act_filter is not None and document.act_int != act_filter:
            continue

        artifact_relative = f"illinois-ilcs/{relative_name}"
        artifact_path = store.source_path(
            jurisdiction,
            DocumentClass.STATUTE,
            run_id,
            artifact_relative,
        )
        sha256 = store.write_bytes(artifact_path, data)
        source_paths.append(artifact_path)
        source_key = _state_source_key(jurisdiction, run_id, artifact_relative)

        chapter_path = document.chapter_citation_path
        if chapter_path not in seen:
            seen.add(chapter_path)
            title_count += 1
            container_count += 1
            items.append(
                _inventory_item(
                    citation_path=chapter_path,
                    source_url=source_url,
                    source_path=source_key,
                    sha256=sha256,
                    metadata={"kind": "chapter", "chapter": str(document.chapter_int)},
                )
            )
            records.append(
                _provision_record(
                    jurisdiction=jurisdiction,
                    citation_path=chapter_path,
                    version=run_id,
                    source_url=source_url,
                    source_path=source_key,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    kind="chapter",
                    heading=f"{document.chapter_int} ILCS",
                    legal_identifier=f"{document.chapter_int} ILCS",
                    level=1,
                    ordinal=document.chapter_int,
                    identifiers={"ilcs:chapter": str(document.chapter_int)},
                )
            )

        act_path = document.act_citation_path
        if act_path not in seen:
            seen.add(act_path)
            container_count += 1
            act_title = _act_title(data) or f"{document.chapter_int} ILCS {document.act_int}"
            items.append(
                _inventory_item(
                    citation_path=act_path,
                    source_url=source_url,
                    source_path=source_key,
                    sha256=sha256,
                    metadata={
                        "kind": "act",
                        "chapter": str(document.chapter_int),
                        "act": str(document.act_int),
                        "parent_citation_path": chapter_path,
                    },
                )
            )
            records.append(
                _provision_record(
                    jurisdiction=jurisdiction,
                    citation_path=act_path,
                    version=run_id,
                    source_url=source_url,
                    source_path=source_key,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    kind="act",
                    heading=act_title,
                    legal_identifier=f"{document.chapter_int} ILCS {document.act_int}",
                    parent_citation_path=chapter_path,
                    level=2,
                    ordinal=document.act_int,
                    identifiers={
                        "ilcs:chapter": str(document.chapter_int),
                        "ilcs:act": str(document.act_int),
                    },
                )
            )

        if document.doc_type != "K":
            skipped_source_count += 1
            continue
        try:
            section = parse_illinois_ilcs_section(data, document=document)
        except ValueError as exc:
            skipped_source_count += 1
            errors.append(f"{relative_name}: {exc}")
            if document.section is not None:
                unread_sections.append(
                    _inventory_item(
                        citation_path=document.citation_path,
                        source_url=source_url,
                        source_path=source_key,
                        sha256=sha256,
                        metadata={
                            "kind": "section",
                            "chapter": str(document.chapter_int),
                            "act": str(document.act_int),
                            "section": document.section,
                            "parent_citation_path": act_path,
                            "source_id": document.stem,
                        },
                    )
                )
            continue
        if section.citation_path in seen:
            continue
        seen.add(section.citation_path)
        section_count += 1
        ordinal = sequence.get(document.stem)
        items.append(
            _inventory_item(
                citation_path=section.citation_path,
                source_url=source_url,
                source_path=source_key,
                sha256=sha256,
                metadata={
                    "kind": "section",
                    "chapter": str(document.chapter_int),
                    "act": str(document.act_int),
                    "section": section.section,
                    "heading": section.heading,
                    "parent_citation_path": act_path,
                    "references_to": list(section.references_to),
                    "source_id": document.stem,
                },
            )
        )
        records.append(
            _provision_record(
                jurisdiction=jurisdiction,
                citation_path=section.citation_path,
                version=run_id,
                source_url=source_url,
                source_path=source_key,
                source_id=document.stem,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                kind="section",
                heading=section.heading,
                body=section.body,
                legal_identifier=section.citation,
                parent_citation_path=act_path,
                level=3,
                ordinal=ordinal,
                identifiers={
                    "ilcs:chapter": str(document.chapter_int),
                    "ilcs:act": str(document.act_int),
                    "ilcs:section": section.section,
                },
                metadata={"references_to": list(section.references_to)},
            )
        )
        if remaining is not None:
            remaining -= 1

    # A section document that was fetched but holds no section (a maintenance,
    # empty or wrong-shape page) stays in the inventory, sourced from that
    # page, so coverage reports it as missing, unless another document
    # supplied the section.
    for gap in unread_sections:
        if gap.citation_path in seen:
            continue
        seen.add(gap.citation_path)
        items.append(gap)

    # A section document the remote run could not fetch stays in the
    # inventory, sourced from the listing that named it, so coverage reports
    # it as missing instead of dropping it.
    recorded_listings: dict[str, tuple[str, str]] = {}
    for failure in remote_failures:
        document = failure.document
        if document.section is None or document.citation_path in seen:
            continue
        listing = failure.listing
        if listing is None:
            raise ValueError(f"no recorded listing names {failure.relative_name}")
        recorded = recorded_listings.get(listing.relative_name)
        if recorded is None:
            artifact_relative = f"illinois-ilcs/{listing.relative_name}"
            artifact_path = store.source_path(
                jurisdiction,
                DocumentClass.STATUTE,
                run_id,
                artifact_relative,
            )
            recorded = (
                _state_source_key(jurisdiction, run_id, artifact_relative),
                store.write_bytes(artifact_path, listing.data),
            )
            recorded_listings[listing.relative_name] = recorded
            source_paths.append(artifact_path)
        seen.add(document.citation_path)
        items.append(
            _inventory_item(
                citation_path=document.citation_path,
                source_url=listing.source_url,
                source_path=recorded[0],
                sha256=recorded[1],
                metadata={
                    "kind": "section",
                    "chapter": str(document.chapter_int),
                    "act": str(document.act_int),
                    "section": document.section,
                    "parent_citation_path": document.act_citation_path,
                    "source_id": document.stem,
                    "target_source_url": failure.source_url,
                },
            )
        )

    if not records:
        raise ValueError("no Illinois ILCS provisions extracted")

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
        skipped_source_count=skipped_source_count + len(remote_errors),
        errors=tuple(remote_errors + errors),
    )


def _discover_local_sources(
    source_root: Path | None,
) -> tuple[tuple[IllinoisIlcsDocumentName, str, str | None, bytes], ...]:
    if source_root is None:
        return ()
    entries: list[tuple[IllinoisIlcsDocumentName, str, str | None, bytes]] = []
    for html_path in sorted(path for path in source_root.rglob("*.html") if path.is_file()):
        try:
            document = parse_illinois_ilcs_doc_name(html_path.name)
        except ValueError:
            continue
        relative_name = html_path.relative_to(source_root).as_posix()
        entries.append((document, relative_name, f"file://{html_path}", html_path.read_bytes()))
    return tuple(entries)


def _source_sort_key(
    document: IllinoisIlcsDocumentName,
    relative_name: str,
    sequence: dict[str, int],
) -> tuple[int, int, int, str, str, str]:
    return (
        sequence.get(document.stem, 10_000_000),
        document.chapter_int,
        document.act_int,
        document.doc_type,
        document.identifier,
        relative_name,
    )


def _discover_remote_sources(
    base_url: str,
    *,
    limit: int | None,
    chapter_filter: int | None,
    act_filter: int | None,
    workers: int = 1,
    errors: list[str] | None = None,
) -> tuple[tuple[IllinoisIlcsDocumentName, str, str | None, bytes], ...]:
    return tuple(
        _iter_remote_sources(
            base_url,
            limit=limit,
            chapter_filter=chapter_filter,
            act_filter=act_filter,
            sequence={},
            workers=workers,
            errors=errors,
        )
    )


def _iter_remote_sources(
    base_url: str,
    *,
    limit: int | None,
    chapter_filter: int | None,
    act_filter: int | None,
    sequence: dict[str, int],
    workers: int,
    errors: list[str] | None = None,
    failures: list[_IllinoisRemoteFailure] | None = None,
    sequence_listing: _IllinoisListing | None = None,
) -> Iterator[tuple[IllinoisIlcsDocumentName, str, str | None, bytes]]:
    session = requests.Session()
    session.headers.update(ILLINOIS_REQUEST_HEADERS)
    listed = _remote_document_listings(
        session,
        base_url,
        limit=limit,
        chapter_filter=chapter_filter,
        act_filter=act_filter,
        sequence=sequence,
        sequence_listing=sequence_listing,
    )
    listing_by_name = dict(listed)
    source_refs: list[tuple[IllinoisIlcsDocumentName, str, str]] = []
    for relative_name, _listing in listed:
        try:
            document = parse_illinois_ilcs_doc_name(relative_name)
        except ValueError:
            continue
        url = _remote_source_url(base_url, document, relative_name)
        source_refs.append((document, relative_name, url))

    def record_failure(
        document: IllinoisIlcsDocumentName,
        relative_name: str,
        url: str,
        error: object,
    ) -> None:
        if errors is not None:
            errors.append(f"{relative_name}: {error}")
        if failures is not None:
            failures.append(
                _IllinoisRemoteFailure(
                    document=document,
                    relative_name=relative_name,
                    source_url=url,
                    listing=listing_by_name.get(relative_name),
                )
            )
    sorted_refs = tuple(
        sorted(
            source_refs,
            key=lambda entry: _source_sort_key(entry[0], entry[1], sequence),
        )
    )
    worker_count = max(1, workers)
    if worker_count == 1:
        for document, relative_name, url in sorted_refs:
            try:
                response = session.get(url, timeout=20)
                response.raise_for_status()
            except requests.RequestException as exc:
                record_failure(document, relative_name, url, exc)
                continue
            yield document, relative_name, url, response.content
        return

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for document, relative_name, url, data, error in executor.map(
            _fetch_remote_source,
            sorted_refs,
        ):
            if error is not None:
                record_failure(document, relative_name, url, error)
                continue
            yield document, relative_name, url, data


def _fetch_remote_source(
    source_ref: tuple[IllinoisIlcsDocumentName, str, str],
) -> tuple[IllinoisIlcsDocumentName, str, str, bytes, str | None]:
    document, relative_name, url = source_ref
    try:
        response = requests.get(url, headers=ILLINOIS_REQUEST_HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return document, relative_name, url, b"", str(exc)
    return document, relative_name, url, response.content, None


def _remote_source_url(
    base_url: str,
    document: IllinoisIlcsDocumentName,
    relative_name: str,
) -> str:
    """Return the current official source URL for a discovered ILCS document."""
    if document.doc_type == "K":
        return f"{ILLINOIS_ILCS_FULLTEXT_URL}?DocName={quote(document.stem, safe='')}"
    return urljoin(base_url, quote(relative_name, safe="/%"))


def _remote_document_paths(
    session: requests.Session,
    base_url: str,
    *,
    limit: int | None,
    chapter_filter: int | None = None,
    act_filter: int | None = None,
    sequence: dict[str, int] | None = None,
) -> tuple[str, ...]:
    return tuple(
        relative_name
        for relative_name, _listing in _remote_document_listings(
            session,
            base_url,
            limit=limit,
            chapter_filter=chapter_filter,
            act_filter=act_filter,
            sequence=sequence,
        )
    )


def _remote_document_listings(
    session: requests.Session,
    base_url: str,
    *,
    limit: int | None,
    chapter_filter: int | None = None,
    act_filter: int | None = None,
    sequence: dict[str, int] | None = None,
    sequence_listing: _IllinoisListing | None = None,
) -> tuple[tuple[str, _IllinoisListing | None], ...]:
    """Return each selected document path with the listing page that names it."""
    if sequence:
        return tuple(
            (relative_name, sequence_listing)
            for relative_name in _remote_document_paths_from_sequence(
                sequence,
                limit=limit,
                chapter_filter=chapter_filter,
                act_filter=act_filter,
            )
        )
    index_page = _remote_page(session, base_url)
    index = index_page.text
    index_listing = _IllinoisListing(
        relative_name="index.html",
        source_url=base_url,
        data=index_page.content,
    )
    direct_links = [
        normalized_link
        for normalized_link in (
            _ilcs_relative_href(link) for link in parse_illinois_ilcs_links(index)
        )
        if "/" in normalized_link
        and _document_path_matches(normalized_link, chapter_filter, act_filter)
    ]
    if direct_links:
        return tuple(
            (relative_name, index_listing)
            for relative_name in _limit_section_paths(direct_links, limit)
        )

    paths: list[str] = []
    listings: list[tuple[str, _IllinoisListing | None]] = []
    for chapter_href in _directory_hrefs(index, prefix="Ch"):
        if not _directory_matches(chapter_href, "Ch", chapter_filter):
            continue
        chapter_url = urljoin(base_url, quote(chapter_href, safe="/%"))
        chapter_text = _remote_text(session, chapter_url)
        for act_href in _directory_hrefs(chapter_text, prefix="Act"):
            if not _directory_matches(act_href, "Act", act_filter):
                continue
            act_relative = f"{chapter_href.rstrip('/')}/{act_href.rstrip('/')}"
            act_url = urljoin(base_url, quote(f"{act_relative}/", safe="/%"))
            act_page = _remote_page(session, act_url)
            act_listing = _IllinoisListing(
                relative_name=f"{act_relative}/index.html",
                source_url=act_url,
                data=act_page.content,
            )
            for doc_href in parse_illinois_ilcs_links(act_page.text):
                relative_name = f"{act_relative}/{Path(doc_href).name}"
                paths.append(relative_name)
                listings.append((relative_name, act_listing))
                if limit is not None and _section_path_count(paths) >= limit:
                    return tuple(listings)
    return tuple(listings)


def _remote_document_paths_from_sequence(
    sequence: dict[str, int],
    *,
    limit: int | None,
    chapter_filter: int | None,
    act_filter: int | None,
) -> tuple[str, ...]:
    paths: list[str] = []
    for stem in sequence:
        try:
            document = parse_illinois_ilcs_doc_name(f"{stem}.html")
        except ValueError:
            continue
        if chapter_filter is not None and document.chapter_int != chapter_filter:
            continue
        if act_filter is not None and document.act_int != act_filter:
            continue
        paths.append(
            f"Ch {document.chapter_int:04d}/Act {document.act_int:04d}/{document.stem}.html"
        )
        if limit is not None and _section_path_count(paths) >= limit:
            break
    return tuple(paths)


def _document_path_matches(
    path: str,
    chapter_filter: int | None,
    act_filter: int | None,
) -> bool:
    try:
        document = parse_illinois_ilcs_doc_name(path)
    except ValueError:
        return False
    if chapter_filter is not None and document.chapter_int != chapter_filter:
        return False
    return act_filter is None or document.act_int == act_filter


def _limit_section_paths(paths: list[str], limit: int | None) -> tuple[str, ...]:
    if limit is None:
        return tuple(paths)
    out: list[str] = []
    section_count = 0
    for path in paths:
        out.append(path)
        try:
            document = parse_illinois_ilcs_doc_name(path)
        except ValueError:
            continue
        if document.doc_type == "K":
            section_count += 1
        if section_count >= limit:
            break
    return tuple(out)


def _section_path_count(paths: list[str]) -> int:
    count = 0
    for path in paths:
        try:
            document = parse_illinois_ilcs_doc_name(path)
        except ValueError:
            continue
        if document.doc_type == "K":
            count += 1
    return count


def _directory_matches(
    href: str,
    prefix: str,
    expected: int | None,
) -> bool:
    if expected is None:
        return True
    match = re.search(rf"\b{re.escape(prefix)}\s+(\d+)\b", href)
    return bool(match and int(match.group(1)) == expected)


def _remote_text(session: requests.Session, url: str) -> str:
    return _remote_page(session, url).text


def _remote_page(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return response


def _directory_hrefs(text: str, *, prefix: str) -> tuple[str, ...]:
    hrefs: list[str] = []
    for href in _HREF_RE.findall(text):
        decoded = _ilcs_relative_href(href)
        segment = decoded.strip("/").split("/")[-1] if decoded else ""
        if segment.startswith(f"{prefix} "):
            hrefs.append(f"{segment}/")
    return tuple(dict.fromkeys(hrefs))


def _ilcs_relative_href(href: str) -> str:
    decoded = unquote(href).strip()
    if "/ftp/ILCS/" in decoded:
        return decoded.split("/ftp/ILCS/", 1)[1]
    return decoded.lstrip("/")


def _load_local_section_sequence(source_root: Path | None) -> dict[str, int]:
    if source_root is None:
        return {}
    candidates = (
        source_root / "aReadMe" / "Section Sequence.txt",
        source_root / "Section Sequence.txt",
    )
    for candidate in candidates:
        if candidate.exists():
            return parse_illinois_section_sequence(candidate.read_text(encoding="utf-8"))
    return {}


def _load_remote_section_sequence(base_url: str) -> dict[str, int]:
    return _fetch_remote_section_sequence(base_url)[0]


def _fetch_remote_section_sequence(
    base_url: str,
) -> tuple[dict[str, int], _IllinoisListing | None]:
    """Return the official Section Sequence ordering and the file it came from."""
    url = urljoin(base_url, "aReadMe/Section%20Sequence.txt")
    try:
        response = requests.get(url, headers=ILLINOIS_REQUEST_HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return {}, None
    sequence = parse_illinois_section_sequence(response.text)
    if not sequence:
        return {}, None
    return sequence, _IllinoisListing(
        relative_name="aReadMe/Section Sequence.txt",
        source_url=url,
        data=response.content,
    )


def _html_text(html: str | bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    lines = [
        re.sub(r"\s+", " ", unescape(line)).strip() for line in soup.get_text("\n").splitlines()
    ]
    return "\n".join(line for line in lines if line)


def _section_heading(text: str, section: str) -> str | None:
    for line in text.splitlines():
        if not _SECTION_HEADING_RE.match(line):
            continue
        match = re.match(
            rf"^(?:Sec\.|Section)\s+{re.escape(section)}\.?\s*(?P<heading>.*)$",
            line,
            re.IGNORECASE,
        )
        if match:
            heading = match.group("heading").strip()
            return heading.rstrip(".") or None
    return None


def _names_section(text: str, section: str) -> bool:
    """Whether a line opens with this section's heading (``Sec. 1.``, not ``Sec. 10.``)."""
    heading = re.compile(
        rf"^(?:Sec\.|Section)\s+{re.escape(section)}\.?(?:\s|$)",
        re.IGNORECASE,
    )
    return any(heading.match(line) for line in text.splitlines())


def _act_title(data: bytes) -> str | None:
    text = _html_text(data)
    for line in text.splitlines():
        if line.endswith("Act.") or line.endswith("Act"):
            return line
    return None


def _inventory_item(
    *,
    citation_path: str,
    source_url: str | None,
    source_path: str,
    sha256: str,
    metadata: dict[str, Any],
) -> SourceInventoryItem:
    return SourceInventoryItem(
        citation_path=citation_path,
        source_url=_non_file_url(source_url),
        source_path=source_path,
        source_format=ILLINOIS_ILCS_SOURCE_FORMAT,
        sha256=sha256,
        metadata=metadata,
    )


def _provision_record(
    *,
    jurisdiction: str,
    citation_path: str,
    version: str,
    source_url: str | None,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    kind: str,
    heading: str | None,
    legal_identifier: str,
    level: int,
    ordinal: int | None,
    body: str | None = None,
    source_id: str | None = None,
    parent_citation_path: str | None = None,
    identifiers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProvisionRecord:
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=jurisdiction,
        document_class=DocumentClass.STATUTE.value,
        citation_path=citation_path,
        body=body,
        heading=heading,
        citation_label=legal_identifier,
        version=version,
        source_url=_non_file_url(source_url),
        source_path=source_path,
        source_id=source_id,
        source_format=ILLINOIS_ILCS_SOURCE_FORMAT,
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


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _state_source_key(jurisdiction: str, run_id: str, relative_name: str) -> str:
    return f"sources/{jurisdiction}/{DocumentClass.STATUTE.value}/{run_id}/{relative_name}"


def _illinois_run_id(
    version: str,
    *,
    jurisdiction: str,
    chapter_filter: int | None,
    act_filter: int | None,
    limit: int | None,
) -> str:
    if chapter_filter is None and act_filter is None and limit is None:
        return version
    parts = [version, jurisdiction]
    if chapter_filter is not None:
        parts.append(f"chapter-{chapter_filter}")
    if act_filter is not None:
        parts.append(f"act-{act_filter}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def _non_file_url(value: str | None) -> str | None:
    if value and not value.startswith("file://"):
        return value
    return None


def _looks_like_ilcs_path(value: str) -> bool:
    try:
        parse_illinois_ilcs_doc_name(value)
    except ValueError:
        return False
    return True
