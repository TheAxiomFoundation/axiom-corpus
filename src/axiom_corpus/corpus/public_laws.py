"""Selected enacted sections from official govinfo public-law USLM XML."""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import requests

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import (
    OFFICIAL_DOCUMENT_USER_AGENT,
    OfficialDocumentExtractReport,
    OfficialDocumentManifest,
    OfficialDocumentSource,
)
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

_USLM_NAMESPACE = "http://schemas.gpo.gov/xml/uslm"
_PROVISION_TAGS = {
    "section",
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "item",
    "subitem",
}
_BLOCK_TAGS = _PROVISION_TAGS | {"chapeau", "content", "continuation", "p", "quotedContent"}
_LAYOUT_TAGS = {"page", "sidenote", "centerRunningHead", "leftRunningHead", "rightRunningHead"}


def extract_public_laws(
    store: CorpusArtifactStore,
    *,
    manifest_path: str | Path,
    version: str,
    download_dir: str | Path | None = None,
) -> OfficialDocumentExtractReport:
    """Retain full source XML and normalize explicitly selected enacted sections.

    Each manifest document uses ``extraction.sections`` to select section numbers.
    Quoted replacement provisions stay in the amendment's body; they are not
    mistaken for independently enacted sections or codified USC provisions.
    ``download_dir`` optionally supplies exact package XML snapshots for replay.
    """
    manifest = OfficialDocumentManifest.load(manifest_path)
    manifest.require_unique_sources()
    if not manifest.documents:
        raise ValueError("no public laws selected")
    records: list[ProvisionRecord] = []
    inventory: list[SourceInventoryItem] = []
    source_paths: list[Path] = []
    with requests.Session() as session:
        session.headers["User-Agent"] = OFFICIAL_DOCUMENT_USER_AGENT
        for source in manifest.documents:
            if (source.jurisdiction, source.document_class) != ("us", "statute"):
                raise ValueError("public laws require the us/statute scope")
            sections = _selected_sections(source)
            content = _source_bytes(source, session=session, download_dir=download_dir)
            law_records = parse_public_law(
                content,
                source=source,
                version=version,
                sections=sections,
            )
            relative_source = f"public-laws/{safe_segment(source.source_id)}.xml"
            source_path = store.source_path("us", "statute", version, relative_source)
            source_sha = store.write_bytes(source_path, content)
            source_key = f"sources/us/statute/{version}/{relative_source}"
            source_paths.append(source_path)
            for record in law_records:
                # The parser has no storage dependency; add snapshot provenance here.
                record = ProvisionRecord.from_mapping(
                    {**record.to_mapping(), "source_path": source_key}
                )
                records.append(record)
                inventory.append(
                    SourceInventoryItem(
                        citation_path=record.citation_path,
                        source_url=source.source_url,
                        source_path=source_key,
                        source_format="uslm-xml",
                        sha256=source_sha,
                        metadata={"kind": record.kind, **(record.metadata or {})},
                    )
                )
    paths = [record.citation_path for record in records]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate public-law citation paths")
    inventory_path = store.inventory_path("us", "statute", version)
    provisions_path = store.provisions_path("us", "statute", version)
    coverage_path = store.coverage_path("us", "statute", version)
    store.write_inventory(inventory_path, inventory)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction="us",
        document_class="statute",
        version=version,
    )
    store.write_json(coverage_path, coverage.to_mapping())
    return OfficialDocumentExtractReport(
        jurisdiction="us",
        document_class="statute",
        document_count=len(manifest.documents),
        block_count=len(records) - len(manifest.documents),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


def parse_public_law(
    content: bytes,
    *,
    source: OfficialDocumentSource,
    version: str,
    sections: tuple[str, ...],
) -> tuple[ProvisionRecord, ...]:
    """Parse selected public-law sections without interpreting their amendments."""
    root = ET.fromstring(content)
    if root.tag != f"{{{_USLM_NAMESPACE}}}pLaw":
        raise ValueError("expected govinfo public-law USLM XML")
    meta = root.find(f"{{{_USLM_NAMESPACE}}}meta")
    if meta is None:
        raise ValueError("public law has no metadata")
    congress = _child_text(meta, "congress")
    number = _child_text(meta, "docNumber")
    approved = _child_text(meta, "approvedDate")
    if not congress.isdigit() or not number.isdigit():
        raise ValueError("public law has no numeric congress/law identity")
    date.fromisoformat(approved)
    if _child_text(meta, "publicPrivate") != "public":
        raise ValueError("expected a public law")
    package = f"PLAW-{congress}publ{number}"
    expected_url = f"https://www.govinfo.gov/content/pkg/{package}/uslm/{package}.xml"
    if (source.download_url or source.source_url) != expected_url:
        raise ValueError("public-law source URL does not match the XML law identity")
    root_path = f"us/statute/pl/{congress}/{number}"
    if source.citation_path not in (None, root_path):
        raise ValueError(f"public-law citation_path must be {root_path}")
    if source.expression_date not in (None, approved):
        raise ValueError("public-law expression_date must match its approvedDate")
    metadata: dict[str, Any] = {
        **(source.metadata or {}),
        "govinfo_package_id": package,
        "approved_date": approved,
        "selected_sections": list(sections),
        "source_scope": "selected enacted sections",
    }
    common: dict[str, Any] = {
        "jurisdiction": "us",
        "document_class": "statute",
        "version": version,
        "source_id": source.source_id,
        "source_document_id": package,
        "source_url": source.source_url,
        "source_format": "uslm-xml",
        "source_as_of": source.source_as_of or approved,
        "expression_date": approved,
        "language": source.language or "en",
        "metadata": metadata,
    }
    records = [
        ProvisionRecord(
            **common,
            id=deterministic_provision_id(root_path),
            citation_path=root_path,
            heading=source.title,
            citation_label=f"P.L. {congress}-{number}",
            kind="document",
            level=1,
            ordinal=1,
            legal_identifier=f"/us/pl/{congress}/{number}",
        )
    ]
    available: dict[str, ET.Element] = {}
    for section in _enacted_sections(root):
        label = _label(section)
        if label not in sections:
            continue
        if label in available:
            raise ValueError(f"ambiguous public-law section: {label}")
        available[label] = section
    missing = sorted(set(sections) - available.keys())
    if missing:
        raise ValueError(f"public-law sections not found: {', '.join(missing)}")
    for ordinal, section_number in enumerate(sections, 1):
        records.extend(
            _provision_records(
                available[section_number],
                parent_path=root_path,
                common=common,
                citation_label=f"P.L. {congress}-{number} § {section_number}",
                level=2,
                ordinal=ordinal,
            )
        )
    return tuple(records)


def _selected_sections(source: OfficialDocumentSource) -> tuple[str, ...]:
    values = (source.extraction or {}).get("sections")
    if not isinstance(values, list) or not values:
        raise ValueError("public-law extraction.sections must be a non-empty list")
    sections = tuple(str(value) for value in values)
    if any(not re.fullmatch(r"[0-9]+[A-Za-z]?", value) for value in sections):
        raise ValueError("public-law sections must be section numbers")
    if len(sections) != len(set(sections)):
        raise ValueError("duplicate selected public-law sections")
    return sections


def _source_bytes(
    source: OfficialDocumentSource,
    *,
    session: requests.Session,
    download_dir: str | Path | None,
) -> bytes:
    if source.local_path:
        return Path(source.local_path).read_bytes()
    if download_dir is not None:
        return (Path(download_dir) / f"{safe_segment(source.source_id)}.xml").read_bytes()
    response = session.get(source.download_url or source.source_url, timeout=120)
    response.raise_for_status()
    return response.content


def _enacted_sections(element: ET.Element) -> Iterator[ET.Element]:
    for child in element:
        tag = _local_name(child)
        if tag == "quotedContent":
            continue
        if tag == "section":
            yield child
        else:
            yield from _enacted_sections(child)


def _provision_records(
    element: ET.Element,
    *,
    parent_path: str,
    common: dict[str, Any],
    citation_label: str,
    level: int,
    ordinal: int,
) -> Iterator[ProvisionRecord]:
    label = _label(element)
    path = f"{parent_path}/{safe_segment(label)}"
    body = _normalize(
        "".join(
            _render(child) + (child.tail or "")
            for child in element
            if _local_name(child) not in {"num", "heading"}
        )
    )
    if not body:
        raise ValueError(f"empty public-law provision: {path}")
    yield ProvisionRecord(
        **common,
        id=deterministic_provision_id(path),
        citation_path=path,
        body=body,
        heading=_child_text(element, "heading") or None,
        citation_label=citation_label,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        kind=_local_name(element),
        level=level,
        ordinal=ordinal,
        legal_identifier=element.get("identifier"),
        identifiers={"uslm_id": element.get("id", "")},
    )
    child_ordinal = 0
    for child in element:
        if _local_name(child) not in _PROVISION_TAGS:
            continue
        child_ordinal += 1
        yield from _provision_records(
            child,
            parent_path=path,
            common=common,
            level=level + 1,
            ordinal=child_ordinal,
            citation_label=f"{citation_label}({_label(child)})",
        )


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str:
    child = element.find(f"{{{_USLM_NAMESPACE}}}{name}")
    return _normalize(_render(child)) if child is not None else ""


def _label(element: ET.Element) -> str:
    number = element.find(f"{{{_USLM_NAMESPACE}}}num")
    if number is None or not number.get("value"):
        raise ValueError("public-law provision has no num value")
    return str(number.get("value"))


def _render(element: ET.Element) -> str:
    tag = _local_name(element)
    if tag in _LAYOUT_TAGS:
        return ""
    content = (element.text or "") + "".join(
        _render(child) + (child.tail or "") for child in element
    )
    return f"\n\n{content}\n\n" if tag in _BLOCK_TAGS else content


def _normalize(text: str) -> str:
    return "\n\n".join(
        " ".join(part.split()) for part in re.split(r"\n\s*\n", text) if part.strip()
    )
