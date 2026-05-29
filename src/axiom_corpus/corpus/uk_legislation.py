"""UK legislation extraction into source-first corpus artifacts."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import (
    ProvisionCoverageReport,
    compare_provision_coverage,
)
from axiom_corpus.corpus.models import (
    DocumentClass,
    ProvisionRecord,
    SourceInventoryItem,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id
from axiom_corpus.fetchers.legislation_uk import UKLegislationFetcher
from axiom_corpus.models_uk import UK_REGULATION_TYPES, UKCitation, UKSection
from axiom_corpus.parsers.clml import parse_section

UK_SOURCE_FORMAT = "legislation.gov.uk-clml"


@dataclass(frozen=True)
class UKLegislationClassExtractReport:
    """Artifact report for one UK document class."""

    document_class: str
    source_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class UKLegislationExtractReport:
    """Combined UK legislation extraction report."""

    version: str
    source_count: int
    provisions_written: int
    class_reports: tuple[UKLegislationClassExtractReport, ...]


def extract_uk_legislation_sections(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_xmls: Sequence[str | Path] = (),
    citations: Sequence[str] = (),
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
) -> UKLegislationExtractReport:
    """Extract UK section/regulation CLML into normalized corpus artifacts."""
    if not source_xmls and not citations:
        raise ValueError("at least one source XML path or citation is required")

    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    parsed_sources = list(_iter_source_xmls(source_xmls))
    parsed_sources.extend(asyncio.run(_fetch_citation_xmls(citations)) if citations else [])

    grouped_records: dict[str, list[ProvisionRecord]] = defaultdict(list)
    grouped_inventory: dict[str, list[SourceInventoryItem]] = defaultdict(list)
    grouped_sources: dict[str, list[tuple[str, bytes]]] = defaultdict(list)

    for source_name, source_bytes in parsed_sources:
        section = parse_section(source_bytes.decode("utf-8"))
        document_class = uk_document_class(section.citation)
        citation_path = uk_citation_path(section)
        source_relative_name = _source_relative_name(section)
        source_artifact_path = store.source_path(
            "uk",
            document_class,
            version,
            source_relative_name,
        )
        source_key = _source_key(version, document_class, source_relative_name)
        source_sha256 = store.write_bytes(source_artifact_path, source_bytes)
        record = _section_record(
            section,
            citation_path=citation_path,
            document_class=document_class,
            version=version,
            source_path=source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )
        grouped_records[document_class].append(record)
        grouped_inventory[document_class].append(
            SourceInventoryItem(
                citation_path=citation_path,
                source_url=section.source_url or section.citation.legislation_url,
                source_path=source_key,
                source_format=UK_SOURCE_FORMAT,
                sha256=source_sha256,
                metadata={
                    "source_name": source_name,
                    "legislation_type": section.citation.type,
                    "provision_segment": section.citation.provision_segment,
                    "heading": section.title,
                },
            )
        )
        grouped_sources[document_class].append((source_relative_name, source_bytes))

    class_reports: list[UKLegislationClassExtractReport] = []
    for document_class in sorted(grouped_records):
        records = _dedupe_records(grouped_records[document_class])
        inventory = _dedupe_inventory(grouped_inventory[document_class])
        inventory_path = store.inventory_path("uk", document_class, version)
        store.write_inventory(inventory_path, inventory)
        provisions_path = store.provisions_path("uk", document_class, version)
        store.write_provisions(provisions_path, records)
        coverage = compare_provision_coverage(
            inventory,
            records,
            jurisdiction="uk",
            document_class=document_class,
            version=version,
        )
        coverage_path = store.coverage_path("uk", document_class, version)
        store.write_json(coverage_path, coverage.to_mapping())
        source_paths = tuple(
            store.source_path("uk", document_class, version, name)
            for name, _source_bytes in grouped_sources[document_class]
        )
        class_reports.append(
            UKLegislationClassExtractReport(
                document_class=document_class,
                source_count=len(inventory),
                provisions_written=len(records),
                inventory_path=inventory_path,
                provisions_path=provisions_path,
                coverage_path=coverage_path,
                coverage=coverage,
                source_paths=source_paths,
            )
        )

    return UKLegislationExtractReport(
        version=version,
        source_count=sum(report.source_count for report in class_reports),
        provisions_written=sum(report.provisions_written for report in class_reports),
        class_reports=tuple(class_reports),
    )


def uk_document_class(citation: UKCitation) -> str:
    """Return the corpus document class for a UK citation."""
    if citation.type in UK_REGULATION_TYPES:
        return DocumentClass.REGULATION.value
    return DocumentClass.STATUTE.value


def uk_citation_path(section: UKSection) -> str:
    """Return the canonical corpus citation path for a UK section/regulation."""
    citation = section.citation
    document_class = uk_document_class(citation)
    parts = [
        "uk",
        document_class,
        citation.type,
        str(citation.year),
        str(citation.number),
    ]
    if citation.section:
        parts.append(citation.section)
    return "/".join(parts)


def _section_record(
    section: UKSection,
    *,
    citation_path: str,
    document_class: str,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    citation = section.citation
    parent_path = "/".join(citation_path.split("/")[:-1])
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction="uk",
        document_class=document_class,
        citation_path=citation_path,
        citation_label=citation.short_cite,
        heading=section.title,
        body=section.text,
        version=version,
        source_url=section.source_url or citation.legislation_url,
        source_path=source_path,
        source_id=section.source_url or citation.legislation_url,
        source_format=UK_SOURCE_FORMAT,
        source_document_id=f"{citation.type}/{citation.year}/{citation.number}",
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=1,
        ordinal=_provision_ordinal(citation.section),
        kind=citation.provision_segment,
        legal_identifier=citation.short_cite,
        identifiers={
            "legislation.gov.uk:type": citation.type,
            "legislation.gov.uk:year": str(citation.year),
            "legislation.gov.uk:number": str(citation.number),
            "legislation.gov.uk:provision": citation.section or "",
        },
        metadata={
            "extent": section.extent,
            "references_to": section.references_to,
            "retrieved_at": (section.retrieved_at.isoformat() if section.retrieved_at else None),
        },
    )


def _iter_source_xmls(source_xmls: Iterable[str | Path]) -> Iterable[tuple[str, bytes]]:
    for source_xml in source_xmls:
        path = Path(source_xml)
        yield path.name, path.read_bytes()


async def _fetch_citation_xmls(citations: Sequence[str]) -> list[tuple[str, bytes]]:
    fetcher = UKLegislationFetcher()
    fetched: list[tuple[str, bytes]] = []
    for raw_citation in citations:
        citation = UKCitation.from_string(raw_citation)
        if not citation.section:
            raise ValueError(f"section or regulation required: {raw_citation}")
        url = fetcher.build_url(citation)
        xml = await fetcher._fetch_xml(url)
        fetched.append((_source_relative_name_from_citation(citation), xml.encode()))
    return fetched


def _source_relative_name(section: UKSection) -> str:
    return _source_relative_name_from_citation(section.citation)


def _source_relative_name_from_citation(citation: UKCitation) -> str:
    provision = citation.section or "document"
    return (
        f"{citation.type}/{citation.year}/{citation.number}/"
        f"{citation.provision_segment}-{provision}.xml"
    )


def _source_key(version: str, document_class: str, relative_name: str) -> str:
    return f"sources/uk/{document_class}/{version}/{relative_name}"


def _provision_ordinal(provision: str | None) -> int | None:
    if provision is None:
        return None
    return int(provision) if provision.isdigit() else None


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _dedupe_records(records: Iterable[ProvisionRecord]) -> tuple[ProvisionRecord, ...]:
    by_path: dict[str, ProvisionRecord] = {}
    for record in records:
        by_path[record.citation_path] = record
    return tuple(by_path[path] for path in sorted(by_path))


def _dedupe_inventory(
    items: Iterable[SourceInventoryItem],
) -> tuple[SourceInventoryItem, ...]:
    by_path: dict[str, SourceInventoryItem] = {}
    for item in items:
        by_path[item.citation_path] = item
    return tuple(by_path[path] for path in sorted(by_path))
