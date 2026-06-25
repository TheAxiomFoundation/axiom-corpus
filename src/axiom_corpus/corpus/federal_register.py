"""Federal Register regulatory activity source adapter."""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol, TextIO, cast
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

FEDERAL_REGISTER_API_URL = "https://www.federalregister.gov/api/v1/documents.json"
FEDERAL_REGISTER_API_DOCS_URL = "https://www.federalregister.gov/developers/documentation/api/v1"
FEDERAL_REGISTER_SOURCE_ID = "federal-register"
FEDERAL_REGISTER_API_SOURCE_FORMAT = "federal-register-api-json"
FEDERAL_REGISTER_TEXT_SOURCE_FORMAT = "federal-register-raw-text"
FEDERAL_REGISTER_TEXT_SLICE_SOURCE_FORMAT = "federal-register-raw-text-slice"
DEFAULT_DOCUMENT_TYPES = ("RULE", "PRORULE", "NOTICE")
FEDERAL_REGISTER_FIELDS = (
    "abstract",
    "action",
    "agencies",
    "agency_names",
    "body_html_url",
    "cfr_references",
    "citation",
    "comments_close_on",
    "dates",
    "docket_id",
    "docket_ids",
    "document_number",
    "effective_on",
    "end_page",
    "excerpts",
    "full_text_xml_url",
    "html_url",
    "json_url",
    "mods_url",
    "page_length",
    "pdf_url",
    "public_inspection_pdf_url",
    "publication_date",
    "raw_text_url",
    "regulation_id_number_info",
    "regulation_id_numbers",
    "regulations_dot_gov_info",
    "regulations_dot_gov_url",
    "significant",
    "start_page",
    "subtype",
    "title",
    "toc_doc",
    "toc_subject",
    "topics",
    "type",
    "volume",
)


class _Response(Protocol):
    content: bytes
    text: str
    url: str

    def raise_for_status(self) -> None: ...


class _Session(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Iterable[tuple[str, str]] | None = None,
        timeout: float = 30,
    ) -> _Response: ...


@dataclass(frozen=True)
class FederalRegisterExtractReport:
    """Result from a Federal Register regulatory activity extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    start_date: str
    end_date: str
    document_types: tuple[str, ...]
    page_count: int
    document_count: int
    text_error_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class FederalRegisterCfrSectionRef:
    """A CFR section whose amendatory Federal Register text should be sliced."""

    title: int
    part: int
    section: str

    @property
    def section_number(self) -> str:
        return f"{self.part}.{self.section}"

    @property
    def citation_path(self) -> str:
        return f"us/regulation/{self.title}/{self.part}/{self.section}"

    @property
    def citation_label(self) -> str:
        return f"{self.title} CFR {self.section_number}"


@dataclass(frozen=True)
class FederalRegisterCfrSectionExtractReport:
    """Result from slicing CFR section text out of a Federal Register document."""

    jurisdiction: str
    document_class: str
    version: str
    source_text_path: Path
    requested_sections: tuple[str, ...]
    sections_written: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _FederalRegisterDocument:
    data: dict[str, Any]
    metadata_source_key: str
    metadata_sha256: str
    body_source_key: str
    body_source_format: str
    body_sha256: str
    body: str | None
    text_error: str | None = None


def federal_register_run_id(
    version: str,
    *,
    document_types: Sequence[str] = DEFAULT_DOCUMENT_TYPES,
    limit: int | None = None,
    term: str | None = None,
) -> str:
    """Return a scoped Federal Register run id."""
    run_id = version
    normalized_types = tuple(_normalize_document_type(kind) for kind in document_types)
    if normalized_types != DEFAULT_DOCUMENT_TYPES:
        run_id = f"{run_id}-types-{'-'.join(kind.lower() for kind in normalized_types)}"
    if term:
        run_id = f"{run_id}-term-{_slug(term)[:48]}"
    if limit is not None:
        run_id = f"{run_id}-limit-{limit}"
    return run_id


def extract_federal_register(
    store: CorpusArtifactStore,
    *,
    version: str,
    start_date: date | str,
    end_date: date | str | None = None,
    document_types: Sequence[str] = DEFAULT_DOCUMENT_TYPES,
    term: str | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    limit: int | None = None,
    per_page: int = 100,
    fetch_full_text: bool = True,
    timeout_seconds: float = 30,
    request_attempts: int = 3,
    request_delay_seconds: float = 0.1,
    session: _Session | None = None,
    progress_stream: TextIO | None = None,
) -> FederalRegisterExtractReport:
    """Snapshot Federal Register documents and normalize them as rulemaking activity."""
    start_date_text = _date_text(start_date)
    end_date_text = _date_text(end_date or start_date)
    normalized_types = tuple(_normalize_document_type(kind) for kind in document_types)
    run_id = federal_register_run_id(
        version,
        document_types=normalized_types,
        limit=limit,
        term=term,
    )
    client = cast(_Session, session or requests.Session())
    source_as_of_text = source_as_of or end_date_text
    root_path = "us/rulemaking/federal-register"
    expression_date_text = _date_text(expression_date or end_date_text)
    source_paths: list[Path] = []
    errors: list[str] = []
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []

    documents: list[dict[str, Any]] = []
    page = 1
    while True:
        params = _documents_query_params(
            start_date=start_date_text,
            end_date=end_date_text,
            document_types=normalized_types,
            term=term,
            per_page=per_page,
            page=page,
        )
        response = _get_with_retries(
            client,
            FEDERAL_REGISTER_API_URL,
            params=params,
            timeout=timeout_seconds,
            attempts=request_attempts,
            delay_seconds=request_delay_seconds,
        )
        payload = _decode_json(response)
        page_relative = f"federal-register/api/documents-page-{page}.json"
        page_path = store.source_path("us", DocumentClass.RULEMAKING, run_id, page_relative)
        page_sha = store.write_json(page_path, payload)
        source_paths.append(page_path)
        page_source_key = f"sources/us/{DocumentClass.RULEMAKING.value}/{run_id}/{page_relative}"

        if page == 1:
            items.append(
                SourceInventoryItem(
                    citation_path=root_path,
                    source_url=_query_url(params),
                    source_path=page_source_key,
                    source_format=FEDERAL_REGISTER_API_SOURCE_FORMAT,
                    sha256=page_sha,
                    metadata={
                        "kind": "collection",
                        "source": "FederalRegister.gov API",
                        "api_docs_url": FEDERAL_REGISTER_API_DOCS_URL,
                        "start_date": start_date_text,
                        "end_date": end_date_text,
                        "document_types": list(normalized_types),
                        "term": term,
                        "limit": limit,
                    },
                )
            )
            records.append(
                ProvisionRecord(
                    jurisdiction="us",
                    document_class=DocumentClass.RULEMAKING.value,
                    citation_path=root_path,
                    id=deterministic_provision_id(root_path),
                    heading="Federal Register Regulatory Activity",
                    version=run_id,
                    source_url=_query_url(params),
                    source_path=page_source_key,
                    source_id=FEDERAL_REGISTER_SOURCE_ID,
                    source_format=FEDERAL_REGISTER_API_SOURCE_FORMAT,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    kind="collection",
                    level=1,
                    metadata={
                        "source": "FederalRegister.gov API",
                        "api_docs_url": FEDERAL_REGISTER_API_DOCS_URL,
                        "start_date": start_date_text,
                        "end_date": end_date_text,
                        "document_types": list(normalized_types),
                        "term": term,
                        "limit": limit,
                    },
                )
            )

        results = list(payload.get("results") or [])
        if limit is not None:
            remaining = limit - len(documents)
            results = results[: max(0, remaining)]
        documents.extend(dict(result) for result in results if isinstance(result, dict))
        if progress_stream is not None:
            print(
                f"downloaded Federal Register page {page}: {len(results)} documents",
                file=progress_stream,
            )
        if limit is not None and len(documents) >= limit:
            break
        if not results or page >= int(payload.get("total_pages") or page):
            break
        page += 1

    fetched_documents = [
        _snapshot_document(
            store,
            run_id=run_id,
            client=client,
            document=document,
            fetch_full_text=fetch_full_text,
            timeout_seconds=timeout_seconds,
            request_attempts=request_attempts,
            request_delay_seconds=request_delay_seconds,
        )
        for document in documents
    ]
    for fetched in fetched_documents:
        metadata_path = store.root / fetched.metadata_source_key
        source_paths.append(metadata_path)
        if fetched.body_source_key != fetched.metadata_source_key:
            source_paths.append(store.root / fetched.body_source_key)
        if fetched.text_error:
            errors.append(fetched.text_error)

    by_date: dict[str, list[_FederalRegisterDocument]] = defaultdict(list)
    for fetched in fetched_documents:
        publication_date = str(fetched.data.get("publication_date") or "undated")
        by_date[publication_date].append(fetched)

    for date_ordinal, publication_date in enumerate(sorted(by_date), start=1):
        date_path = f"{root_path}/{publication_date}"
        date_docs = sorted(
            by_date[publication_date],
            key=lambda row: str(row.data.get("document_number") or ""),
        )
        first = date_docs[0]
        items.append(
            SourceInventoryItem(
                citation_path=date_path,
                source_url=FEDERAL_REGISTER_API_URL,
                source_path=first.metadata_source_key,
                source_format=FEDERAL_REGISTER_API_SOURCE_FORMAT,
                sha256=first.metadata_sha256,
                metadata={
                    "kind": "publication_date",
                    "source": "FederalRegister.gov API",
                    "publication_date": publication_date,
                    "document_count": len(date_docs),
                },
            )
        )
        records.append(
            ProvisionRecord(
                jurisdiction="us",
                document_class=DocumentClass.RULEMAKING.value,
                citation_path=date_path,
                id=deterministic_provision_id(date_path),
                heading=f"Federal Register documents published {publication_date}",
                version=run_id,
                source_url=FEDERAL_REGISTER_API_URL,
                source_path=first.metadata_source_key,
                source_id=FEDERAL_REGISTER_SOURCE_ID,
                source_format=FEDERAL_REGISTER_API_SOURCE_FORMAT,
                source_as_of=source_as_of_text,
                expression_date=publication_date,
                parent_citation_path=root_path,
                parent_id=deterministic_provision_id(root_path),
                kind="publication_date",
                level=2,
                ordinal=date_ordinal,
                metadata={
                    "source": "FederalRegister.gov API",
                    "publication_date": publication_date,
                    "document_count": len(date_docs),
                },
            )
        )
        for doc_ordinal, fetched in enumerate(date_docs, start=1):
            item, record = _document_item_and_record(
                fetched,
                root_path=date_path,
                run_id=run_id,
                source_as_of=source_as_of_text,
                ordinal=doc_ordinal,
            )
            items.append(item)
            records.append(record)

    inventory_path = store.inventory_path("us", DocumentClass.RULEMAKING, run_id)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path("us", DocumentClass.RULEMAKING, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction="us",
        document_class=DocumentClass.RULEMAKING.value,
        version=run_id,
    )
    coverage_path = store.coverage_path("us", DocumentClass.RULEMAKING, run_id)
    store.write_json(coverage_path, coverage.to_mapping())
    return FederalRegisterExtractReport(
        jurisdiction="us",
        document_class=DocumentClass.RULEMAKING.value,
        version=run_id,
        start_date=start_date_text,
        end_date=end_date_text,
        document_types=normalized_types,
        page_count=page,
        document_count=len(documents),
        text_error_count=len(errors),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        errors=tuple(errors),
    )


def extract_federal_register_cfr_sections(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_text_path: str | Path,
    sections: Sequence[FederalRegisterCfrSectionRef],
    document_number: str,
    document_citation: str,
    document_title: str,
    document_type: str,
    source_url: str,
    source_as_of: date | str,
    expression_date: date | str,
    source_document_citation_path: str | None = None,
) -> FederalRegisterCfrSectionExtractReport:
    """Write regulation-section records from a saved Federal Register raw text.

    This is for amendatory text that has not yet appeared as compiled eCFR XML,
    but is still the authoritative source for the affected CFR section.
    """
    section_refs = tuple(sections)
    if not section_refs:
        raise ValueError("at least one CFR section reference is required")

    source_path = Path(source_text_path)
    source_text = source_path.read_text()
    source_key = _source_key_for_path(store, source_path)
    source_sha = sha256_bytes(source_text.encode("utf-8"))
    source_as_of_text = _date_text(source_as_of)
    expression_date_text = _date_text(expression_date)
    source_document_path = source_document_citation_path or (
        f"us/rulemaking/federal-register/{source_as_of_text}/{document_number}"
    )

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    errors: list[str] = []
    part_refs = dict.fromkeys((ref.title, ref.part) for ref in section_refs)
    for title, part in part_refs:
        part_path = f"us/regulation/{title}/{part}"
        part_label = f"{title} CFR Part {part}"
        part_metadata = {
            "chapter": "IV",
            "part": str(part),
            "source_document_citation_path": source_document_path,
            "source_document_number": document_number,
            "source_document_title": document_title,
            "source_document_type": document_type,
        }
        part_identifiers = {
            "cfr:title": str(title),
            "cfr:part": str(part),
            "federal-register:document-number": document_number,
            "federal-register:citation": document_citation,
        }
        items.append(
            SourceInventoryItem(
                citation_path=part_path,
                source_url=source_url,
                source_path=source_key,
                source_format=FEDERAL_REGISTER_TEXT_SLICE_SOURCE_FORMAT,
                sha256=source_sha,
                metadata=part_metadata,
            )
        )
        records.append(
            ProvisionRecord(
                jurisdiction="us",
                document_class=DocumentClass.REGULATION.value,
                citation_path=part_path,
                id=deterministic_provision_id(part_path),
                heading=_federal_register_cfr_part_heading(source_text, title, part) or part_label,
                citation_label=part_label,
                version=version,
                source_url=source_url,
                source_path=source_key,
                source_id=FEDERAL_REGISTER_SOURCE_ID,
                source_format=FEDERAL_REGISTER_TEXT_SLICE_SOURCE_FORMAT,
                source_document_id=document_number,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                level=1,
                ordinal=part,
                kind="part",
                legal_identifier=part_label,
                identifiers=part_identifiers,
                metadata=part_metadata,
            )
        )

    section_count = 0
    for ref in section_refs:
        body = _federal_register_cfr_section_body(source_text, ref.section_number)
        if body is None:
            errors.append(f"missing CFR section block: {ref.citation_label}")
            continue
        section_count += 1
        heading = _federal_register_cfr_heading(body, ref.section_number)
        identifiers = {
            "cfr:title": str(ref.title),
            "cfr:part": str(ref.part),
            "cfr:section": ref.section_number,
            "federal-register:document-number": document_number,
            "federal-register:citation": document_citation,
        }
        metadata = {
            "chapter": "IV",
            "part": str(ref.part),
            "section": ref.section_number,
            "source_document_citation_path": source_document_path,
            "source_document_number": document_number,
            "source_document_title": document_title,
            "source_document_type": document_type,
        }
        items.append(
            SourceInventoryItem(
                citation_path=ref.citation_path,
                source_url=source_url,
                source_path=source_key,
                source_format=FEDERAL_REGISTER_TEXT_SLICE_SOURCE_FORMAT,
                sha256=source_sha,
                metadata=metadata,
            )
        )
        records.append(
            ProvisionRecord(
                jurisdiction="us",
                document_class=DocumentClass.REGULATION.value,
                citation_path=ref.citation_path,
                id=deterministic_provision_id(ref.citation_path),
                body=body,
                heading=heading,
                citation_label=ref.citation_label,
                version=version,
                source_url=source_url,
                source_path=source_key,
                source_id=FEDERAL_REGISTER_SOURCE_ID,
                source_format=FEDERAL_REGISTER_TEXT_SLICE_SOURCE_FORMAT,
                source_document_id=document_number,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                parent_citation_path=f"us/regulation/{ref.title}/{ref.part}",
                parent_id=deterministic_provision_id(f"us/regulation/{ref.title}/{ref.part}"),
                level=2,
                ordinal=_cfr_section_ordinal(ref.section),
                kind="section",
                legal_identifier=ref.citation_label,
                identifiers=identifiers,
                metadata=metadata,
            )
        )

    if errors:
        raise ValueError("; ".join(errors))

    inventory_path = store.inventory_path("us", DocumentClass.REGULATION, version)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path("us", DocumentClass.REGULATION, version)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction="us",
        document_class=DocumentClass.REGULATION.value,
        version=version,
    )
    coverage_path = store.coverage_path("us", DocumentClass.REGULATION, version)
    store.write_json(coverage_path, coverage.to_mapping())
    return FederalRegisterCfrSectionExtractReport(
        jurisdiction="us",
        document_class=DocumentClass.REGULATION.value,
        version=version,
        source_text_path=source_path,
        requested_sections=tuple(ref.citation_path for ref in section_refs),
        sections_written=section_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=(source_path,),
    )


def _snapshot_document(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    client: _Session,
    document: dict[str, Any],
    fetch_full_text: bool,
    timeout_seconds: float,
    request_attempts: int,
    request_delay_seconds: float,
) -> _FederalRegisterDocument:
    document_number = _document_number(document)
    metadata_relative = f"federal-register/documents/{document_number}.json"
    metadata_path = store.source_path("us", DocumentClass.RULEMAKING, run_id, metadata_relative)
    metadata_sha = store.write_json(metadata_path, document)
    metadata_source_key = (
        f"sources/us/{DocumentClass.RULEMAKING.value}/{run_id}/{metadata_relative}"
    )
    body = _body_fallback(document)
    body_source_key = metadata_source_key
    body_source_format = FEDERAL_REGISTER_API_SOURCE_FORMAT
    body_sha = metadata_sha
    text_error: str | None = None
    raw_text_url = document.get("raw_text_url")
    if fetch_full_text and raw_text_url:
        try:
            response = _get_with_retries(
                client,
                str(raw_text_url),
                timeout=timeout_seconds,
                attempts=request_attempts,
                delay_seconds=request_delay_seconds,
            )
        except requests.RequestException as exc:
            text_error = f"{document_number}: {exc}"
        else:
            raw_text = response.text.strip()
            body_text = _federal_register_text_body(raw_text)
            if raw_text:
                text_relative = f"federal-register/documents/{document_number}.txt"
                text_path = store.source_path("us", DocumentClass.RULEMAKING, run_id, text_relative)
                body_sha = store.write_text(text_path, raw_text + "\n")
                body_source_key = (
                    f"sources/us/{DocumentClass.RULEMAKING.value}/{run_id}/{text_relative}"
                )
                body_source_format = FEDERAL_REGISTER_TEXT_SOURCE_FORMAT
                body = body_text or body
    return _FederalRegisterDocument(
        data=document,
        metadata_source_key=metadata_source_key,
        metadata_sha256=metadata_sha,
        body_source_key=body_source_key,
        body_source_format=body_source_format,
        body_sha256=body_sha,
        body=body,
        text_error=text_error,
    )


def _document_item_and_record(
    fetched: _FederalRegisterDocument,
    *,
    root_path: str,
    run_id: str,
    source_as_of: str,
    ordinal: int,
) -> tuple[SourceInventoryItem, ProvisionRecord]:
    document = fetched.data
    document_number = _document_number(document)
    citation_path = f"{root_path}/{document_number}"
    metadata = _document_metadata(document, fetched)
    heading = _clean_text(str(document.get("title") or document_number))
    citation = _optional_text(document.get("citation"))
    item = SourceInventoryItem(
        citation_path=citation_path,
        source_url=_optional_text(document.get("html_url") or document.get("json_url")),
        source_path=fetched.body_source_key,
        source_format=fetched.body_source_format,
        sha256=fetched.body_sha256,
        metadata=metadata,
    )
    record = ProvisionRecord(
        jurisdiction="us",
        document_class=DocumentClass.RULEMAKING.value,
        citation_path=citation_path,
        id=deterministic_provision_id(citation_path),
        body=fetched.body,
        heading=heading,
        citation_label=citation or document_number,
        version=run_id,
        source_url=_optional_text(document.get("html_url") or document.get("json_url")),
        source_path=fetched.body_source_key,
        source_id=FEDERAL_REGISTER_SOURCE_ID,
        source_format=fetched.body_source_format,
        source_document_id=document_number,
        source_as_of=source_as_of,
        expression_date=str(document.get("publication_date") or source_as_of),
        parent_citation_path=root_path,
        parent_id=deterministic_provision_id(root_path),
        kind=_kind_for_type(_optional_text(document.get("type"))),
        level=3,
        ordinal=ordinal,
        legal_identifier=citation or document_number,
        identifiers=_document_identifiers(document),
        metadata=metadata,
    )
    return item, record


def _source_key_for_path(store: CorpusArtifactStore, source_path: Path) -> str:
    resolved_source = source_path.resolve()
    resolved_root = store.root.resolve()
    try:
        return resolved_source.relative_to(resolved_root).as_posix()
    except ValueError:
        return source_path.as_posix()


def _federal_register_cfr_section_body(text: str, section_number: str) -> str | None:
    start_pattern = re.compile(
        rf"(?m)^Sec\.\s+{re.escape(section_number)}(?:\s|$)",
    )
    start_match = start_pattern.search(text)
    if start_match is None:
        return None
    end_pattern = re.compile(
        r"(?m)^(?:(?P<instruction>0\n\d+\.\s+Section\s+"
        r"(?P<section>\d+\.\d+[A-Za-z]?)\b)|PART\s+\d+--|"
        r"Robert F\. Kennedy|\[FR Doc\.)|\n\n+Sec\.\s+\d+\.\d+[A-Za-z]?\b"
    )
    position = start_match.end()
    while True:
        end_match = end_pattern.search(text, position)
        if end_match is None:
            end_index = len(text)
            break
        if end_match.group("section") == section_number:
            position = end_match.end()
            continue
        end_index = end_match.start()
        break
    body = text[start_match.start() : end_index].strip()
    return _strip_federal_register_tail(body)


def _strip_federal_register_tail(body: str) -> str:
    return re.sub(r"\n</pre>.*\Z", "", body, flags=re.S).strip()


def _federal_register_cfr_part_heading(text: str, title: int, part: int) -> str | None:
    del title
    pattern = re.compile(rf"(?m)^PART\s+{part}--(?P<heading>.+)$")
    match = pattern.search(text)
    if match is None:
        return None
    return _clean_text(match.group("heading"))


def _federal_register_cfr_heading(body: str, section_number: str) -> str:
    heading_block = body.split("\n\n", 1)[0]
    heading = re.sub(
        rf"^Sec\.\s+{re.escape(section_number)}\s*",
        "",
        heading_block,
    )
    heading = _clean_text(heading)
    return heading.rstrip(".") or section_number


def _cfr_section_ordinal(section: str) -> int:
    match = re.match(r"(?P<digits>\d+)(?P<suffix>[a-z]*)\Z", section, flags=re.I)
    if match is None:
        raise ValueError(f"unsupported CFR section number: {section!r}")
    suffix = match.group("suffix").lower()
    suffix_offset = 0
    for char in suffix:
        suffix_offset = suffix_offset * 26 + (ord(char) - ord("a") + 1)
    return int(match.group("digits")) * 100 + suffix_offset


def _documents_query_params(
    *,
    start_date: str,
    end_date: str,
    document_types: Sequence[str],
    term: str | None,
    per_page: int,
    page: int,
) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [
        ("conditions[publication_date][gte]", start_date),
        ("conditions[publication_date][lte]", end_date),
        ("order", "newest"),
        ("per_page", str(per_page)),
        ("page", str(page)),
    ]
    if term:
        params.append(("conditions[term]", term))
    for document_type in document_types:
        params.append(("conditions[type][]", document_type))
    for field in FEDERAL_REGISTER_FIELDS:
        params.append(("fields[]", field))
    return params


def _get_with_retries(
    session: _Session,
    url: str,
    *,
    params: Iterable[tuple[str, str]] | None = None,
    timeout: float,
    attempts: int,
    delay_seconds: float,
) -> _Response:
    last_error: requests.RequestException | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max(1, attempts):
                break
            time.sleep(delay_seconds * attempt)
    assert last_error is not None
    raise last_error


def _decode_json(response: _Response) -> dict[str, Any]:
    data = json.loads(response.text)
    if not isinstance(data, dict):
        raise ValueError("Federal Register API response must be a JSON object")
    return data


def _document_metadata(
    document: dict[str, Any],
    fetched: _FederalRegisterDocument,
) -> dict[str, Any]:
    metadata = {
        "source": "FederalRegister.gov API",
        "kind": "federal_register_document",
        "document_number": _document_number(document),
        "type": document.get("type"),
        "subtype": document.get("subtype"),
        "publication_date": document.get("publication_date"),
        "agency_names": _agency_names(document),
        "agencies": document.get("agencies"),
        "action": document.get("action"),
        "abstract": document.get("abstract"),
        "citation": document.get("citation"),
        "cfr_references": document.get("cfr_references"),
        "docket_id": document.get("docket_id"),
        "docket_ids": document.get("docket_ids"),
        "regulation_id_numbers": document.get("regulation_id_numbers"),
        "comments_close_on": document.get("comments_close_on"),
        "effective_on": document.get("effective_on"),
        "significant": document.get("significant"),
        "start_page": document.get("start_page"),
        "end_page": document.get("end_page"),
        "page_length": document.get("page_length"),
        "html_url": document.get("html_url"),
        "pdf_url": document.get("pdf_url"),
        "raw_text_url": document.get("raw_text_url"),
        "json_url": document.get("json_url"),
        "regulations_dot_gov_url": document.get("regulations_dot_gov_url"),
        "metadata_source_path": fetched.metadata_source_key,
        "body_status": "raw_text"
        if fetched.body_source_format == FEDERAL_REGISTER_TEXT_SOURCE_FORMAT
        else "metadata_fallback",
    }
    if fetched.text_error:
        metadata["text_error"] = fetched.text_error
    return {key: value for key, value in metadata.items() if value not in (None, [], {})}


def _document_identifiers(document: dict[str, Any]) -> dict[str, str]:
    identifiers = {"federal-register:document-number": _document_number(document)}
    citation = _optional_text(document.get("citation"))
    if citation:
        identifiers["federal-register:citation"] = citation
    docket_ids = document.get("docket_ids")
    if isinstance(docket_ids, list) and docket_ids:
        identifiers["federal-register:docket-ids"] = ",".join(str(value) for value in docket_ids)
    regulation_id_numbers = document.get("regulation_id_numbers")
    if isinstance(regulation_id_numbers, list) and regulation_id_numbers:
        identifiers["federal-register:regulation-id-numbers"] = ",".join(
            str(value) for value in regulation_id_numbers
        )
    return identifiers


def _body_fallback(document: dict[str, Any]) -> str | None:
    parts = [
        _optional_text(document.get("title")),
        _optional_text(document.get("abstract")),
        _optional_text(document.get("action")),
        _optional_text(document.get("dates")),
    ]
    body = "\n\n".join(part for part in parts if part)
    return body or None


def _federal_register_text_body(raw_text: str) -> str | None:
    """Return readable Federal Register body text from a raw text response."""
    if not raw_text.strip():
        return None
    text = raw_text.replace("\x00", "")
    if "<" not in text:
        return text.strip() or None

    soup = BeautifulSoup(text, "html.parser")
    source = soup.find("pre") or soup.body or soup
    cleaned = source.get_text()
    return cleaned.strip() or None


def _agency_names(document: dict[str, Any]) -> list[str]:
    agency_names = document.get("agency_names")
    if isinstance(agency_names, list):
        return [str(name) for name in agency_names]
    agencies = document.get("agencies")
    if not isinstance(agencies, list):
        return []
    names: list[str] = []
    for agency in agencies:
        if isinstance(agency, dict) and agency.get("name"):
            names.append(str(agency["name"]))
    return names


def _document_number(document: dict[str, Any]) -> str:
    value = _optional_text(document.get("document_number"))
    if not value:
        raise ValueError(f"Federal Register document has no document_number: {document!r}")
    return value


def _kind_for_type(document_type: str | None) -> str:
    normalized = (document_type or "").strip().upper().replace("-", "_").replace(" ", "_")
    if normalized in {"RULE", "FINAL_RULE"}:
        return "final_rule"
    if normalized in {"PRORULE", "PROPOSED_RULE"}:
        return "proposed_rule"
    if normalized == "NOTICE":
        return "notice"
    if normalized in {"PRESDOCU", "PRESIDENTIAL_DOCUMENT"}:
        return "presidential_document"
    return "federal_register_document"


def _normalize_document_type(value: str) -> str:
    cleaned = value.strip().upper()
    aliases = {
        "FINAL_RULE": "RULE",
        "FINAL-RULE": "RULE",
        "PROPOSED_RULE": "PRORULE",
        "PROPOSED-RULE": "PRORULE",
        "PROPOSED": "PRORULE",
        "PRESIDENTIAL_DOCUMENT": "PRESDOCU",
        "PRESIDENTIAL-DOCUMENT": "PRESDOCU",
    }
    cleaned = aliases.get(cleaned, cleaned)
    if cleaned not in {"RULE", "PRORULE", "NOTICE", "PRESDOCU"}:
        raise ValueError(f"unsupported Federal Register document type: {value!r}")
    return cleaned


def _date_text(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _clean_text(str(value))
    return text or None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "federal-register"


def _query_url(params: Iterable[tuple[str, str]]) -> str:
    return f"{FEDERAL_REGISTER_API_URL}?{urlencode(list(params))}"
