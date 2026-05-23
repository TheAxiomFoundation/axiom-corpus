"""Promote reviewed source-discovery groups into corpus manifests."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from axiom_corpus.corpus.documents import OfficialDocumentSource
from axiom_corpus.corpus.source_discovery import (
    DiscoveryDisposition,
    SourceDiscoveryRow,
    SourceStatus,
    infer_source_family,
)

_SAFE_CITATION_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SOURCE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SUPPORTED_OFFICIAL_DOCUMENT_FORMATS = {"html", "pdf"}


@dataclass(frozen=True)
class SourcePromotionReport:
    """Result from turning one source-discovery group into a manifest."""

    group_key: str
    output_path: Path
    document_count: int
    skipped_unsupported_count: int
    skipped_unsupported_urls: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "group_key": self.group_key,
            "output_path": str(self.output_path),
            "document_count": self.document_count,
            "skipped_unsupported_count": self.skipped_unsupported_count,
            "skipped_unsupported_urls": list(self.skipped_unsupported_urls),
        }


def promote_source_discovery_group(
    *,
    report_path: str | Path,
    group_key: str,
    output_path: str | Path,
    source_as_of: str | None = None,
    expression_date: str | None = None,
    limit: int | None = None,
    exclude_urls: tuple[str, ...] = (),
    url_rewrites: dict[str, str] | None = None,
    fail_on_unsupported: bool = True,
) -> SourcePromotionReport:
    """Write an official-document manifest for one ready source group."""

    rows = _ready_group_rows(_load_source_discovery_rows(report_path), group_key=group_key)
    excluded = set(exclude_urls)
    rewrites = url_rewrites or {}
    rows = tuple(row for row in rows if row.canonical_url not in excluded)
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise ValueError(f"no ready source-discovery rows found for group_key: {group_key}")

    documents: list[OfficialDocumentSource] = []
    unsupported_urls: list[str] = []
    for row in rows:
        source_url = rewrites.get(row.canonical_url, row.canonical_url)
        promoted_row = replace(row, canonical_url=source_url)
        source_format = _official_document_format(source_url)
        if source_format not in _SUPPORTED_OFFICIAL_DOCUMENT_FORMATS:
            unsupported_urls.append(source_url)
            continue
        documents.append(
            _official_document_source(
                promoted_row,
                group_key=group_key,
                source_family=infer_source_family(row),
                source_format=source_format,
                source_as_of=source_as_of,
                expression_date=expression_date,
                source_discovery_canonical_url=row.canonical_url,
            )
        )

    if unsupported_urls and fail_on_unsupported:
        raise ValueError(
            f"{len(unsupported_urls)} source-discovery URL(s) in {group_key} need a "
            f"non-HTML/PDF adapter: {unsupported_urls[:3]}"
        )
    if not documents:
        raise ValueError(f"no supported official-document URLs found for group_key: {group_key}")
    documents = list(_dedupe_document_citation_paths(tuple(documents)))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"documents": [_document_mapping(document) for document in documents]}
    output.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))

    return SourcePromotionReport(
        group_key=group_key,
        output_path=output,
        document_count=len(documents),
        skipped_unsupported_count=len(unsupported_urls),
        skipped_unsupported_urls=tuple(unsupported_urls),
    )


def _load_source_discovery_rows(report_path: str | Path) -> tuple[SourceDiscoveryRow, ...]:
    payload = json.loads(Path(report_path).read_text())
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("source-discovery report must contain a rows list")
    return tuple(_source_discovery_row(row) for row in raw_rows if isinstance(row, dict))


def _source_discovery_row(data: dict[str, Any]) -> SourceDiscoveryRow:
    return SourceDiscoveryRow(
        raw_url=str(data["raw_url"]),
        canonical_url=str(data["canonical_url"]),
        host=str(data["host"]),
        source_list=str(data["source_list"]),
        input_count=int(data["input_count"]),
        source_status=SourceStatus(str(data["source_status"])),
        disposition=DiscoveryDisposition(str(data["disposition"])),
        document_class=str(data["document_class"]),
        jurisdiction=data.get("jurisdiction"),
        release_scope_present=bool(data["release_scope_present"]),
        fragment=data.get("fragment"),
        reason=str(data["reason"]),
        reference_count=int(data.get("reference_count") or 0),
        sample_reference_paths=tuple(str(path) for path in data.get("sample_reference_paths", ())),
    )


def _ready_group_rows(
    rows: tuple[SourceDiscoveryRow, ...],
    *,
    group_key: str,
) -> tuple[SourceDiscoveryRow, ...]:
    selected = []
    for row in rows:
        if row.disposition is not DiscoveryDisposition.READY_FOR_MANIFEST:
            continue
        if row.release_scope_present or row.jurisdiction is None:
            continue
        row_group_key = f"{row.jurisdiction}/{row.document_class}/{infer_source_family(row)}"
        if row_group_key == group_key:
            selected.append(row)
    return tuple(sorted(selected, key=lambda row: (-row.input_count, row.canonical_url)))


def _official_document_source(
    row: SourceDiscoveryRow,
    *,
    group_key: str,
    source_family: str,
    source_format: str,
    source_as_of: str | None,
    expression_date: str | None,
    source_discovery_canonical_url: str,
) -> OfficialDocumentSource:
    citation_path = _citation_path(row, source_family=source_family)
    title = _title(row)
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": row.host,
        "source_discovery_group": group_key,
        "source_family": source_family,
        "source_status": row.source_status.value,
        "source_discovery_input_count": row.input_count,
        "source_discovery_source_list": row.source_list,
        "source_discovery_raw_url": row.raw_url,
    }
    if source_discovery_canonical_url != row.canonical_url:
        metadata["source_discovery_canonical_url"] = source_discovery_canonical_url
        metadata["source_url_rewritten"] = True
    if row.reference_count:
        metadata["source_discovery_reference_count"] = row.reference_count
    if row.sample_reference_paths:
        metadata["discovered_via"] = list(row.sample_reference_paths)
    else:
        metadata["discovered_via"] = f"source-discovery:{row.source_list}"

    return OfficialDocumentSource(
        source_id=_source_id(row),
        jurisdiction=str(row.jurisdiction),
        document_class=row.document_class,
        title=title,
        source_url=row.canonical_url,
        citation_path=citation_path,
        source_format=source_format,
        source_as_of=source_as_of,
        expression_date=expression_date,
        metadata=metadata,
    )


def _document_mapping(source: OfficialDocumentSource) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source_id": source.source_id,
        "jurisdiction": source.jurisdiction,
        "document_class": source.document_class,
        "citation_path": source.citation_path,
        "title": source.title,
        "source_url": source.source_url,
        "source_format": source.source_format,
    }
    if source.source_as_of:
        payload["source_as_of"] = source.source_as_of
    if source.expression_date:
        payload["expression_date"] = source.expression_date
    if source.metadata:
        payload["metadata"] = source.metadata
    return payload


def _dedupe_document_citation_paths(
    documents: tuple[OfficialDocumentSource, ...],
) -> tuple[OfficialDocumentSource, ...]:
    counts = Counter(document.citation_path for document in documents)
    if not any(count > 1 for count in counts.values()):
        return documents
    deduped: list[OfficialDocumentSource] = []
    for document in documents:
        if counts[document.citation_path] == 1:
            deduped.append(document)
            continue
        metadata = dict(document.metadata or {})
        metadata["source_discovery_base_citation_path"] = document.citation_path
        deduped.append(
            replace(
                document,
                citation_path=f"{document.citation_path}/{document.source_id}",
                metadata=metadata,
            )
        )
    return tuple(deduped)


def _official_document_format(url: str) -> str:
    path = urlsplit(url).path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith((".xlsx", ".xls", ".csv", ".zip", ".doc", ".docx")):
        return path.rsplit(".", 1)[1]
    return "html"


def _citation_path(row: SourceDiscoveryRow, *, source_family: str) -> str:
    parts = [
        str(row.jurisdiction),
        row.document_class,
        _citation_segment(row.host),
    ]
    if source_family != row.document_class:
        parts.insert(2, _citation_segment(source_family))
    split = urlsplit(row.canonical_url)
    path_parts = [
        _citation_segment(part.removesuffix(".pdf").removesuffix(".html").removesuffix(".htm"))
        for part in split.path.split("/")
        if part
    ]
    if path_parts:
        parts.extend(path_parts)
    else:
        parts.append(_short_hash(row.canonical_url))
    if split.query:
        parts.append(_short_hash(split.query))
    return "/".join(parts)


def _source_id(row: SourceDiscoveryRow) -> str:
    split = urlsplit(row.canonical_url)
    path_stem = "-".join(part for part in split.path.split("/") if part) or split.netloc
    stem = path_stem.rsplit(".", 1)[0]
    normalized = _SOURCE_ID_RE.sub("-", stem).strip("-").lower()
    if not normalized:
        normalized = "source"
    return f"{normalized[:72]}-{_short_hash(row.canonical_url)}"


def _title(row: SourceDiscoveryRow) -> str:
    split = urlsplit(row.canonical_url)
    path_parts = [part for part in split.path.split("/") if part]
    if path_parts:
        title_parts = path_parts
        if row.host == "legislation.gov.uk":
            title_parts = [part.rsplit(".", 1)[0] for part in path_parts]
            if title_parts and title_parts[-1] == "data":
                title_parts = title_parts[:-1]
            label = " ".join(title_parts)
        else:
            tail = path_parts[-1].rsplit(".", 1)[0]
            label = _SOURCE_ID_RE.sub(" ", tail).strip()
        if label:
            return " ".join(label.split())
    return row.host


def _citation_segment(value: str) -> str:
    segment = _SAFE_CITATION_SEGMENT_RE.sub("-", value.strip()).strip("-").lower()
    return segment or "source"


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:10]
