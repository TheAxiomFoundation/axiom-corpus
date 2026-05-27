"""Generic official-document ingestion for policy sources."""

from __future__ import annotations

import re
import sys
import time
import warnings
import zipfile
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from json import loads as json_loads
from pathlib import Path
from typing import Any, Self, TextIO
from xml.etree import ElementTree

import fitz
import requests
import yaml
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib3.exceptions import InsecureRequestWarning

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

OFFICIAL_DOCUMENT_USER_AGENT = (
    "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) "
    "https://github.com/TheAxiomFoundation/axiom-corpus"
)
OFFICIAL_DOCUMENT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_BROWSER_FALLBACK_STATUSES = {403, 404, 406}
_REQUEST_RETRY_STATUSES = {429, 500, 502, 503, 504}
_REQUEST_RETRY_ATTEMPTS = 4
_REQUEST_RETRY_BASE_DELAY_SECONDS = 0.5
_GOOGLE_DRIVE_FILE_RE = re.compile(r"https?://drive\.google\.com/file/d/([^/]+)/")
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_TEXT_TAGS = _HEADING_TAGS | {"p", "li", "table", "blockquote"}
_NON_HEADING_UPPERCASE_LINES = {
    "HANDBOOK BEGINS HERE",
    "HANDBOOK CONTINUES",
    "HANDBOOK CONTINUE",
    "HANDBOOK ENDS HERE",
}
_WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass(frozen=True)
class OfficialDocumentSource:
    """One primary official document to snapshot and normalize."""

    source_id: str
    jurisdiction: str
    document_class: str
    title: str
    source_url: str
    citation_path: str | None = None
    download_url: str | None = None
    source_format: str | None = None
    source_as_of: str | None = None
    expression_date: str | None = None
    local_path: str | None = None
    request: dict[str, Any] | None = None
    extraction: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Self:
        request = data.get("request")
        if request is not None and not isinstance(request, dict):
            raise ValueError("official document request config must be a mapping")
        extraction = data.get("extraction")
        if extraction is not None and not isinstance(extraction, dict):
            raise ValueError("official document extraction config must be a mapping")
        return cls(
            source_id=str(data["source_id"]),
            jurisdiction=str(data["jurisdiction"]),
            document_class=str(data.get("document_class", DocumentClass.POLICY.value)),
            title=str(data["title"]),
            source_url=str(data["source_url"]),
            citation_path=data.get("citation_path"),
            download_url=data.get("download_url"),
            source_format=data.get("source_format"),
            source_as_of=data.get("source_as_of"),
            expression_date=data.get("expression_date"),
            local_path=data.get("local_path"),
            request=request,
            extraction=extraction,
            metadata=data.get("metadata"),
        )


@dataclass(frozen=True)
class OfficialDocumentManifest:
    """Manifest of primary official documents for one corpus scope."""

    documents: tuple[OfficialDocumentSource, ...]

    @classmethod
    def load(cls, path: str | Path) -> Self:
        data = yaml.safe_load(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError("official document manifest must be a YAML mapping")
        documents = data.get("documents")
        if not isinstance(documents, list):
            raise ValueError("official document manifest must contain a documents list")
        return cls(
            documents=tuple(
                OfficialDocumentSource.from_mapping(row)
                for row in documents
                if isinstance(row, dict)
            )
        )

    def require_unique_sources(self) -> None:
        seen: set[str] = set()
        for source in self.documents:
            if source.source_id in seen:
                raise ValueError(f"duplicate source_id: {source.source_id}")
            seen.add(source.source_id)


@dataclass(frozen=True)
class OfficialDocumentExtractReport:
    """Result from a generic official-document extraction run."""

    jurisdiction: str
    document_class: str
    document_count: int
    block_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class _DownloadedDocument:
    source: OfficialDocumentSource
    content: bytes
    content_type: str | None
    final_url: str


@dataclass(frozen=True)
class _DocumentBlock:
    kind: str
    ordinal: int
    heading: str | None
    body: str
    metadata: dict[str, Any]


def official_documents_run_id(
    version: str,
    *,
    only_source_id: str | None = None,
    limit: int | None = None,
) -> str:
    """Return a scoped run id for a manifest-driven official-document run."""
    parts = [version]
    if only_source_id:
        parts.append(safe_segment(only_source_id))
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def extract_official_documents(
    store: CorpusArtifactStore,
    *,
    manifest_path: str | Path,
    version: str,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_source_id: str | None = None,
    limit: int | None = None,
    progress_stream: TextIO | None = None,
) -> OfficialDocumentExtractReport:
    """Snapshot official HTML/PDF documents and extract normalized records."""
    manifest = OfficialDocumentManifest.load(manifest_path)
    manifest.require_unique_sources()
    documents = _select_documents(manifest.documents, only_source_id=only_source_id, limit=limit)
    if not documents:
        raise ValueError("no official documents selected")
    jurisdiction, document_class = _single_scope(documents)
    run_id = official_documents_run_id(version, only_source_id=only_source_id, limit=limit)
    default_source_as_of = source_as_of or version
    default_expression_date = _date_text(expression_date, default_source_as_of)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": OFFICIAL_DOCUMENT_USER_AGENT,
            "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    source_paths: list[Path] = []
    inventory: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    block_count = 0

    for source in documents:
        _progress(progress_stream, f"extracting {source.source_id}")
        downloaded = _download_document(source, session=session)
        source_format = _infer_source_format(source, downloaded)
        relative_source = (
            f"official-documents/{safe_segment(source.source_id)}{_extension(source_format)}"
        )
        artifact_path = store.source_path(jurisdiction, document_class, run_id, relative_source)
        source_sha = store.write_bytes(artifact_path, downloaded.content)
        source_paths.append(artifact_path)
        source_key = f"sources/{jurisdiction}/{document_class}/{run_id}/{relative_source}"
        source_as_of_text = source.source_as_of or default_source_as_of
        expression_date_text = source.expression_date or default_expression_date

        blocks = tuple(
            _extract_blocks(
                downloaded.content,
                source_format,
                source_url=source.source_url,
                title=source.title,
                extraction=source.extraction,
            )
        )
        block_count += len(blocks)
        inventory.extend(
            _inventory_items(
                source,
                blocks=blocks,
                source_key=source_key,
                source_format=source_format,
                source_sha=source_sha,
                content_type=downloaded.content_type,
                final_url=downloaded.final_url,
            )
        )
        records.extend(
            _provision_records(
                source,
                blocks=blocks,
                version=run_id,
                source_key=source_key,
                source_format=source_format,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                content_type=downloaded.content_type,
                final_url=downloaded.final_url,
            )
        )

    inventory_path = store.inventory_path(jurisdiction, document_class, run_id)
    provisions_path = store.provisions_path(jurisdiction, document_class, run_id)
    coverage_path = store.coverage_path(jurisdiction, document_class, run_id)
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

    return OfficialDocumentExtractReport(
        jurisdiction=jurisdiction,
        document_class=document_class,
        document_count=len(documents),
        block_count=block_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


def google_drive_download_url(url: str) -> str | None:
    """Return a direct download URL for a public Google Drive file URL."""
    match = _GOOGLE_DRIVE_FILE_RE.match(url)
    if not match:
        return None
    return f"https://drive.google.com/uc?export=download&id={match.group(1)}"


def _select_documents(
    documents: tuple[OfficialDocumentSource, ...],
    *,
    only_source_id: str | None,
    limit: int | None,
) -> tuple[OfficialDocumentSource, ...]:
    selected = [source for source in documents if only_source_id in {None, source.source_id}]
    if limit is not None:
        selected = selected[:limit]
    return tuple(selected)


def _single_scope(documents: tuple[OfficialDocumentSource, ...]) -> tuple[str, str]:
    jurisdictions = {source.jurisdiction for source in documents}
    document_classes = {source.document_class for source in documents}
    if len(jurisdictions) != 1 or len(document_classes) != 1:
        raise ValueError("official document extraction requires one jurisdiction/document_class")
    return next(iter(jurisdictions)), next(iter(document_classes))


def _download_document(
    source: OfficialDocumentSource,
    *,
    session: requests.Session,
) -> _DownloadedDocument:
    if source.local_path:
        path = Path(source.local_path)
        return _DownloadedDocument(
            source=source,
            content=path.read_bytes(),
            content_type=None,
            final_url=path.as_uri(),
        )
    download_url = (
        source.download_url or google_drive_download_url(source.source_url) or source.source_url
    )
    verify = bool((source.request or {}).get("verify_tls", True))
    response = _get_with_retries(session, download_url, verify=verify)
    if response.status_code in _BROWSER_FALLBACK_STATUSES:
        response.close()
        headers = dict(session.headers)
        headers["User-Agent"] = OFFICIAL_DOCUMENT_BROWSER_USER_AGENT
        response = _get_with_retries(session, download_url, headers=headers, verify=verify)
    response.raise_for_status()
    return _DownloadedDocument(
        source=source,
        content=response.content,
        content_type=response.headers.get("content-type"),
        final_url=response.url,
    )


def _get_with_retries(
    session: requests.Session,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    verify: bool = True,
) -> requests.Response:
    """Fetch a small official document, retrying transient server/network failures."""
    for attempt in range(1, _REQUEST_RETRY_ATTEMPTS + 1):
        try:
            with warnings.catch_warnings():
                if not verify:
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                response = session.get(
                    url,
                    headers=headers,
                    timeout=90,
                    allow_redirects=True,
                    verify=verify,
                )
            if (
                response.status_code in _REQUEST_RETRY_STATUSES
                and attempt < _REQUEST_RETRY_ATTEMPTS
            ):
                response.close()
                _sleep_before_retry(attempt)
                continue
            return response
        except requests.RequestException:
            if attempt >= _REQUEST_RETRY_ATTEMPTS:
                raise
            _sleep_before_retry(attempt)
    raise RuntimeError(f"failed to fetch official document: {url}")


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(_REQUEST_RETRY_BASE_DELAY_SECONDS * attempt)


def _infer_source_format(source: OfficialDocumentSource, downloaded: _DownloadedDocument) -> str:
    if source.source_format:
        return source.source_format.lower()
    content_type = (downloaded.content_type or "").lower()
    if downloaded.content.startswith(b"%PDF") or "pdf" in content_type:
        return "pdf"
    if "html" in content_type or downloaded.content.lstrip().startswith((b"<!doctype", b"<html")):
        return "html"
    if (
        "wordprocessingml" in content_type
        or downloaded.content.startswith(b"PK")
        and _zip_contains(downloaded.content, "word/document.xml")
    ):
        return "docx"
    raise ValueError(f"cannot infer source format for {source.source_id}")


def _extension(source_format: str) -> str:
    if source_format == "pdf":
        return ".pdf"
    if source_format == "html":
        return ".html"
    return f".{safe_segment(source_format)}"


def _extract_blocks(
    content: bytes,
    source_format: str,
    *,
    source_url: str,
    title: str | None,
    extraction: dict[str, Any] | None,
) -> tuple[_DocumentBlock, ...]:
    if source_format == "pdf":
        return _extract_pdf_blocks(content, extraction=extraction)
    if source_format == "html":
        return _extract_html_blocks(
            content, source_url=source_url, fallback_title=title, extraction=extraction
        )
    if source_format == "json":
        return _extract_json_html_blocks(
            content,
            source_url=source_url,
            fallback_title=title,
            extraction=extraction,
        )
    if source_format == "docx":
        return _extract_docx_blocks(content)
    raise ValueError(f"unsupported official document source_format: {source_format}")


def _extract_pdf_blocks(
    content: bytes, *, extraction: dict[str, Any] | None
) -> tuple[_DocumentBlock, ...]:
    segmentation = (extraction or {}).get("segmentation")
    if segmentation == "numbered_sections":
        return _extract_numbered_pdf_section_blocks(content, extraction=extraction or {})
    if segmentation == "labeled_sections":
        return _extract_labeled_pdf_section_blocks(content, extraction=extraction or {})
    blocks: list[_DocumentBlock] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        for index, page in enumerate(document, start=1):
            text = _normalize_text(page.get_text("text"))
            if not text:
                continue
            blocks.append(
                _DocumentBlock(
                    kind="page",
                    ordinal=len(blocks) + 1,
                    heading=f"Page {index}",
                    body=text,
                    metadata={"page_number": index},
                )
            )
    return tuple(blocks)


def _extract_numbered_pdf_section_blocks(
    content: bytes, *, extraction: dict[str, Any]
) -> tuple[_DocumentBlock, ...]:
    """Extract legal PDFs whose top-level sections begin with numbered headings."""
    lines = _filtered_pdf_lines(content, extraction=extraction)
    sections: list[_DocumentBlock] = []
    index = 0
    while index < len(lines):
        match = _NUMBERED_SECTION_START_RE.match(lines[index][0])
        if not match:
            index += 1
            continue

        section_label = match.group("label")
        end_label = match.group("end_label")
        index += 1
        heading_lines: list[str] = []
        while index < len(lines) and _looks_like_section_heading_line(lines[index][0]):
            heading_lines.append(lines[index][0])
            index += 1
        if not heading_lines:
            continue

        body_lines: list[str] = []
        first_page = lines[index - 1][1]
        while index < len(lines) and not _NUMBERED_SECTION_START_RE.match(lines[index][0]):
            body_lines.append(lines[index][0])
            index += 1

        label_text = section_label if end_label is None else f"{section_label} -- {end_label}"
        citation_suffix = section_label if end_label is None else f"{section_label}-{end_label}"
        heading = f"{label_text}. {' '.join(heading_lines)}"
        page_numbers = [page for _line, page in lines[max(0, index - len(body_lines)) : index]]
        pages = page_numbers or [first_page]
        metadata: dict[str, Any] = {
            "citation_suffix": citation_suffix,
            "section_label": section_label,
            "page_start": min(pages),
            "page_end": max(pages),
        }
        if end_label is not None:
            metadata["section_end_label"] = end_label
        sections.append(
            _DocumentBlock(
                kind="section",
                ordinal=len(sections) + 1,
                heading=heading,
                body=_normalize_text("\n".join(body_lines)),
                metadata=metadata,
            )
        )
    return tuple(sections)


def _extract_labeled_pdf_section_blocks(
    content: bytes, *, extraction: dict[str, Any]
) -> tuple[_DocumentBlock, ...]:
    """Extract PDFs whose top-level sections begin with stable labels."""
    heading_pattern = extraction.get("section_heading_pattern")
    label_pattern = extraction.get("section_label_pattern")
    if heading_pattern is None and label_pattern is None:
        raise ValueError(
            "labeled_sections extraction requires section_heading_pattern "
            "or section_label_pattern"
        )
    section_heading_re = (
        re.compile(str(heading_pattern)) if heading_pattern is not None else None
    )
    section_label_re = re.compile(str(label_pattern)) if label_pattern is not None else None
    label_heading_pattern = extraction.get("label_only_heading_pattern")
    label_heading_re = (
        re.compile(str(label_heading_pattern)) if label_heading_pattern is not None else None
    )
    label_requires_heading = bool(extraction.get("label_only_requires_heading", False))
    lines = _filtered_pdf_lines(content, extraction=extraction)
    drop_repeated = bool(extraction.get("drop_repeated_section_headings", True))

    sections: list[_DocumentBlock] = []
    current_label: str | None = None
    current_heading: str | None = None
    current_body: list[str] = []
    current_body_pages: list[int] = []
    current_start_page: int | None = None
    index = 0

    def flush() -> None:
        nonlocal current_label, current_heading, current_body, current_body_pages
        nonlocal current_start_page
        if current_label is None or current_heading is None or current_start_page is None:
            return
        pages = current_body_pages or [current_start_page]
        sections.append(
            _DocumentBlock(
                kind="section",
                ordinal=len(sections) + 1,
                heading=current_heading,
                body=_normalize_text("\n".join(current_body)),
                metadata={
                    "citation_suffix": current_label,
                    "section_label": current_label,
                    "page_start": min(pages),
                    "page_end": max(pages),
                },
            )
        )
        current_label = None
        current_heading = None
        current_body = []
        current_body_pages = []
        current_start_page = None

    while index < len(lines):
        line, page = lines[index]
        match = _match_labeled_pdf_section(line, section_heading_re, section_label_re)
        if match:
            label, heading_text = match
            consumed_label_heading = False
            if drop_repeated and label == current_label:
                index += 1
                while index < len(lines) and _looks_like_labeled_heading_continuation(
                    lines[index][0], section_heading_re, section_label_re
                ):
                    index += 1
                continue
            if not heading_text and label_heading_re is not None:
                if index + 1 < len(lines) and label_heading_re.match(lines[index + 1][0]):
                    heading_text = lines[index + 1][0]
                    consumed_label_heading = True
                elif label_requires_heading:
                    if current_label is not None:
                        current_body.append(line)
                        current_body_pages.append(page)
                    index += 1
                    continue
            flush()
            heading_lines = [heading_text] if heading_text else []
            index += 1
            if consumed_label_heading:
                index += 1
            while index < len(lines) and _looks_like_labeled_heading_continuation(
                lines[index][0], section_heading_re, section_label_re
            ):
                heading_lines.append(lines[index][0])
                index += 1
            heading = " ".join(part for part in heading_lines if part)
            current_label = label
            current_heading = f"{label} {heading}".strip()
            current_start_page = page
            continue
        if current_label is not None:
            current_body.append(line)
            current_body_pages.append(page)
        index += 1
    flush()
    return tuple(sections)


def _extract_docx_blocks(content: bytes) -> tuple[_DocumentBlock, ...]:
    with zipfile.ZipFile(BytesIO(content)) as document:
        xml = document.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    body = root.find("w:body", _WORD_NS)
    if body is None:
        return ()

    blocks: list[_DocumentBlock] = []
    heading: str | None = None
    parts: list[str] = []

    def flush() -> None:
        nonlocal parts
        body_text = _normalize_text("\n\n".join(parts))
        if body_text:
            blocks.append(
                _DocumentBlock(
                    kind="block",
                    ordinal=len(blocks) + 1,
                    heading=heading,
                    body=body_text,
                    metadata={},
                )
            )
        parts = []

    for child in body:
        if child.tag == _word_tag("p"):
            text = _docx_paragraph_text(child)
            if not text:
                continue
            if _docx_paragraph_is_heading(child):
                flush()
                heading = text
            else:
                parts.append(text)
        elif child.tag == _word_tag("tbl"):
            table_text = _docx_table_text(child)
            if table_text:
                parts.append(table_text)
    flush()
    return tuple(blocks)


def _zip_contains(content: bytes, name: str) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            return name in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _word_tag(local_name: str) -> str:
    return f"{{{_WORD_NS['w']}}}{local_name}"


def _docx_paragraph_is_heading(paragraph: ElementTree.Element) -> bool:
    style = paragraph.find("w:pPr/w:pStyle", _WORD_NS)
    value = style.get(_word_tag("val")) if style is not None else None
    if not value:
        return False
    normalized = value.lower().replace(" ", "")
    return normalized.startswith("heading") or normalized in {"title", "subtitle"}


def _docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    return _normalize_text("".join(_docx_text_chunks(paragraph)))


def _docx_table_text(table: ElementTree.Element) -> str:
    rows: list[str] = []
    for row in table.findall("w:tr", _WORD_NS):
        cells = [
            _normalize_text(" ".join(_docx_text_chunks(cell)))
            for cell in row.findall("w:tc", _WORD_NS)
        ]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _docx_text_chunks(node: ElementTree.Element) -> tuple[str, ...]:
    chunks: list[str] = []
    for descendant in node.iter():
        if descendant.tag == _word_tag("t") and descendant.text:
            chunks.append(descendant.text)
        elif descendant.tag == _word_tag("tab"):
            chunks.append("\t")
        elif descendant.tag == _word_tag("br"):
            chunks.append("\n")
    return tuple(chunks)


def _match_labeled_pdf_section(
    line: str,
    section_heading_re: re.Pattern[str] | None,
    section_label_re: re.Pattern[str] | None,
) -> tuple[str, str] | None:
    if section_heading_re is not None:
        match = section_heading_re.match(line)
        if match:
            return match.group("label"), match.groupdict().get("heading", "").strip()
    if section_label_re is not None:
        match = section_label_re.match(line)
        if match:
            return match.group("label"), ""
    return None


def _filtered_pdf_lines(
    content: bytes, *, extraction: dict[str, Any]
) -> tuple[tuple[str, int], ...]:
    start_page = _positive_int(extraction.get("start_page"), default=1)
    drop_lines = {str(line).strip() for line in extraction.get("drop_lines", ())}
    drop_line_patterns = tuple(
        re.compile(str(pattern)) for pattern in extraction.get("drop_line_patterns", ())
    )
    lines: list[tuple[str, int]] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        for page_index, page in enumerate(document, start=1):
            if page_index < start_page:
                continue
            for raw_line in page.get_text("text").splitlines():
                line = _normalize_text(raw_line)
                if not line or _drop_pdf_line(line, drop_lines, drop_line_patterns):
                    continue
                lines.append((line, page_index))
    return tuple(lines)


_NUMBERED_SECTION_START_RE = re.compile(
    r"^(?P<label>\d{3})\.(?:\s*--\s*(?P<end_label>\d{3})\.)?$"
)


def _positive_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    parsed = int(value)
    if parsed < 1:
        raise ValueError("page numbers must be positive")
    return parsed


def _drop_pdf_line(
    line: str, drop_lines: set[str], drop_line_patterns: tuple[re.Pattern[str], ...]
) -> bool:
    if line in drop_lines:
        return True
    if re.match(r"^Page \d+$", line):
        return True
    if re.match(r"^Section \d{3}$", line):
        return True
    return any(pattern.search(line) for pattern in drop_line_patterns)


def _looks_like_section_heading_line(line: str) -> bool:
    if line in {"(RESERVED)", "(RESERVED)."}:
        return True
    if line in _NON_HEADING_UPPERCASE_LINES:
        return False
    letters = [character for character in line if character.isalpha()]
    if not letters:
        return False
    uppercase_letters = [character for character in letters if character.isupper()]
    return len(uppercase_letters) / len(letters) >= 0.75


def _looks_like_labeled_heading_continuation(
    line: str,
    section_heading_re: re.Pattern[str] | None,
    section_label_re: re.Pattern[str] | None,
) -> bool:
    if _match_labeled_pdf_section(line, section_heading_re, section_label_re):
        return False
    return _looks_like_section_heading_line(line)


def _extract_html_blocks(
    content: bytes,
    *,
    source_url: str,
    fallback_title: str | None,
    extraction: dict[str, Any] | None,
) -> tuple[_DocumentBlock, ...]:
    soup = BeautifulSoup(content, "html.parser", from_encoding="utf-8")
    drop_selectors = [
        "script",
        "style",
        "noscript",
        "svg",
        "button",
        "input",
        "nav",
        "select",
        "header",
        "footer",
        "textarea",
        "aside",
        ".breadcrumb",
        ".breadcrumbs",
        "[aria-label='breadcrumb']",
        *_html_drop_selectors(extraction),
    ]
    for selector in drop_selectors:
        for node in soup.select(selector):
            node.decompose()
    root = _html_content_root(soup, extraction=extraction)
    title = _document_title(soup) or fallback_title
    webworks_blocks = _extract_webworks_html_blocks(root, title=title, source_url=source_url)
    if webworks_blocks:
        return webworks_blocks
    blocks: list[_DocumentBlock] = []
    heading = title
    parts: list[str] = []

    def flush() -> None:
        nonlocal parts
        body = _normalize_text("\n\n".join(parts))
        if body:
            blocks.append(
                _DocumentBlock(
                    kind="block",
                    ordinal=len(blocks) + 1,
                    heading=heading,
                    body=body,
                    metadata={"source_url": source_url},
                )
            )
        parts = []

    for node in root.find_all(_TEXT_TAGS):
        if not isinstance(node, Tag) or _inside_text_tag(node):
            continue
        text = _normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name in _HEADING_TAGS:
            flush()
            heading = text
            continue
        parts.append(text)
    flush()
    if blocks:
        return tuple(blocks)
    fallback = _normalize_text(root.get_text(" ", strip=True))
    if not fallback:
        return ()
    return (
        _DocumentBlock(
            kind="block",
            ordinal=1,
            heading=title,
            body=fallback,
            metadata={"source_url": source_url},
        ),
    )


def _extract_json_html_blocks(
    content: bytes,
    *,
    source_url: str,
    fallback_title: str | None,
    extraction: dict[str, Any] | None,
) -> tuple[_DocumentBlock, ...]:
    html_field = (extraction or {}).get("json_html_field")
    if not isinstance(html_field, str) or not html_field:
        raise ValueError("json official document extraction requires json_html_field")
    data = json_loads(content.decode("utf-8"))
    html_text = _json_path(data, html_field)
    if not isinstance(html_text, str) or not html_text.strip():
        raise ValueError(f"json_html_field did not resolve to HTML text: {html_field}")
    return _extract_html_blocks(
        html_text.encode("utf-8"),
        source_url=source_url,
        fallback_title=fallback_title,
        extraction=extraction,
    )


def _json_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise ValueError(f"json path did not resolve: {path}")
    return current


def _html_content_root(
    soup: BeautifulSoup, *, extraction: dict[str, Any] | None
) -> Tag:
    selector = (extraction or {}).get("html_content_selector") or (
        extraction or {}
    ).get("content_selector")
    if selector is not None:
        root = soup.select_one(str(selector))
        if isinstance(root, Tag):
            return root
        raise ValueError(f"html content selector did not match: {selector!r}")
    return _main_content(soup)


def _html_drop_selectors(extraction: dict[str, Any] | None) -> tuple[str, ...]:
    selectors = (extraction or {}).get("html_drop_selectors") or (
        extraction or {}
    ).get("drop_selectors")
    if selectors is None:
        return ()
    if isinstance(selectors, str):
        return (selectors,)
    return tuple(str(selector) for selector in selectors)


_WEBWORKS_TEXT_CLASS_PREFIXES = (
    "Body_Text",
    "List_",
    "Note_",
    "Numbered_",
    "Cell_",
    "Table_",
)


def _extract_webworks_html_blocks(
    root: Tag,
    *,
    title: str | None,
    source_url: str,
) -> tuple[_DocumentBlock, ...]:
    page = root.select_one("#page_content")
    if not isinstance(page, Tag):
        return ()
    for selector in (".WebWorks_MiniTOC", ".ww_skin_page_globalization"):
        for node in page.select(selector):
            node.decompose()

    blocks: list[_DocumentBlock] = []
    heading = title
    parts: list[str] = []

    def flush() -> None:
        nonlocal parts
        body = _normalize_text("\n\n".join(parts))
        if body:
            blocks.append(
                _DocumentBlock(
                    kind="block",
                    ordinal=len(blocks) + 1,
                    heading=heading,
                    body=body,
                    metadata={"source_url": source_url},
                )
            )
        parts = []

    for node in page.find_all(_is_webworks_content_node):
        text = _normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if _has_webworks_heading_class(node):
            flush()
            heading = text
            continue
        parts.append(text)
    flush()
    return tuple(blocks)


def _is_webworks_content_node(node: Tag) -> bool:
    return _has_webworks_heading_class(node) or any(
        _has_class_prefix(node, prefix) for prefix in _WEBWORKS_TEXT_CLASS_PREFIXES
    )


def _has_webworks_heading_class(node: Tag) -> bool:
    return _has_class_prefix(node, "Heading_")


def _has_class_prefix(node: Tag, prefix: str) -> bool:
    classes = node.get("class")
    if not isinstance(classes, list):
        return False
    return any(isinstance(item, str) and item.startswith(prefix) for item in classes)


def _main_content(soup: BeautifulSoup) -> Tag:
    for selector in ("main", "article", "[role='main']", "#main-content", ".main-content"):
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            return node
    if isinstance(soup.body, Tag):
        return soup.body
    return soup


def _document_title(soup: BeautifulSoup) -> str | None:
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = _normalize_text(h1.get_text(" ", strip=True))
        if text:
            return text
    if soup.title:
        text = _normalize_text(soup.title.get_text(" ", strip=True))
        if text:
            return text
    return None


def _inside_text_tag(node: Tag) -> bool:
    for parent in node.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in _TEXT_TAGS:
            return True
    return False


def _inventory_items(
    source: OfficialDocumentSource,
    *,
    blocks: tuple[_DocumentBlock, ...],
    source_key: str,
    source_format: str,
    source_sha: str,
    content_type: str | None,
    final_url: str,
) -> tuple[SourceInventoryItem, ...]:
    root_path = _root_citation_path(source)
    metadata = _source_metadata(
        source,
        content_type=content_type,
        final_url=final_url,
        block_count=len(blocks),
    )
    items = [
        SourceInventoryItem(
            citation_path=root_path,
            source_url=source.source_url,
            source_path=source_key,
            source_format=source_format,
            sha256=source_sha,
            metadata={"kind": "document", **metadata},
        )
    ]
    for block in blocks:
        items.append(
            SourceInventoryItem(
                citation_path=_block_citation_path(source, block),
                source_url=source.source_url,
                source_path=source_key,
                source_format=source_format,
                sha256=source_sha,
                metadata={"kind": block.kind, **metadata, **block.metadata},
            )
        )
    return tuple(items)


def _provision_records(
    source: OfficialDocumentSource,
    *,
    blocks: tuple[_DocumentBlock, ...],
    version: str,
    source_key: str,
    source_format: str,
    source_as_of: str,
    expression_date: str,
    content_type: str | None,
    final_url: str,
) -> tuple[ProvisionRecord, ...]:
    root_path = _root_citation_path(source)
    root_id = deterministic_provision_id(root_path)
    metadata = _source_metadata(
        source,
        content_type=content_type,
        final_url=final_url,
        block_count=len(blocks),
    )
    records = [
        ProvisionRecord(
            id=root_id,
            jurisdiction=source.jurisdiction,
            document_class=source.document_class,
            citation_path=root_path,
            heading=source.title,
            citation_label=source.title,
            version=version,
            source_url=source.source_url,
            source_path=source_key,
            source_id=source.source_id,
            source_format=source_format,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=1,
            ordinal=1,
            kind="document",
            metadata={"kind": "document", **metadata},
        )
    ]
    for block in blocks:
        citation_path = _block_citation_path(source, block)
        records.append(
            ProvisionRecord(
                id=deterministic_provision_id(citation_path),
                jurisdiction=source.jurisdiction,
                document_class=source.document_class,
                citation_path=citation_path,
                body=block.body,
                heading=block.heading,
                citation_label=f"{source.title} {block.ordinal}",
                version=version,
                source_url=source.source_url,
                source_path=source_key,
                source_id=source.source_id,
                source_format=source_format,
                source_as_of=source_as_of,
                expression_date=expression_date,
                parent_citation_path=root_path,
                parent_id=root_id,
                level=2,
                ordinal=block.ordinal,
                kind=block.kind,
                metadata={"kind": block.kind, **metadata, **block.metadata},
            )
        )
    return tuple(records)


def _source_metadata(
    source: OfficialDocumentSource,
    *,
    content_type: str | None,
    final_url: str,
    block_count: int,
) -> dict[str, Any]:
    metadata = dict(source.metadata or {})
    metadata.update(
        {
            "title": source.title,
            "content_type": content_type,
            "download_url": final_url,
            "block_count": block_count,
        }
    )
    return metadata


def _root_citation_path(source: OfficialDocumentSource) -> str:
    if source.citation_path:
        return _validate_citation_path(
            source.citation_path,
            jurisdiction=source.jurisdiction,
            document_class=source.document_class,
        )
    return f"{source.jurisdiction}/{source.document_class}/{safe_segment(source.source_id)}"


def _block_citation_path(source: OfficialDocumentSource, block: _DocumentBlock) -> str:
    citation_suffix = block.metadata.get("citation_suffix")
    if isinstance(citation_suffix, str) and citation_suffix:
        return f"{_root_citation_path(source)}/{safe_segment(citation_suffix)}"
    return f"{_root_citation_path(source)}/{block.kind}-{block.ordinal}"


def _validate_citation_path(
    citation_path: str,
    *,
    jurisdiction: str,
    document_class: str,
) -> str:
    """Return a manifest-supplied citation path after basic scope validation."""
    normalized = citation_path.strip().strip("/")
    expected_prefix = f"{jurisdiction}/{document_class}/"
    if not normalized.startswith(expected_prefix):
        raise ValueError(f"citation_path must start with {expected_prefix!r}: {citation_path!r}")
    for part in normalized.split("/"):
        safe_segment(part)
    return normalized


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_text(text: str) -> str:
    text = text.replace("\u200b", "").replace("\ufeff", "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _progress(stream: TextIO | None, message: str) -> None:
    if stream is None:
        return
    print(message, file=stream)
    stream.flush()


if __name__ == "__main__":
    print(
        "Use `axiom-corpus-ingest extract-official-documents` to run this adapter.",
        file=sys.stderr,
    )
