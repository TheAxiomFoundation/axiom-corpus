"""UK legislation extraction into source-first corpus artifacts."""

from __future__ import annotations

import asyncio
import json
import re
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
from axiom_corpus.fetchers.lex import LexClient, LexSection
from axiom_corpus.models_uk import UK_REGULATION_TYPES, UKCitation, UKSection
from axiom_corpus.parsers.clml import parse_section

UK_SOURCE_FORMAT = "legislation.gov.uk-clml"
LEX_SOURCE_FORMAT = "lex.lab.i.ai.gov.uk"

# Default ceiling when an act's provision count is unknown.
_LEX_DEFAULT_LIMIT = 2000

_PROVISION_URI_RE = re.compile(r"/(section|regulation|schedule)/([0-9A-Za-z]+)")


@dataclass(frozen=True)
class _PreparedSource:
    """A normalized provision ready to be written, plus its raw source bytes."""

    section: UKSection
    raw_bytes: bytes
    source_format: str
    relative_name: str
    source_name: str


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
    source: str = "clml",
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    lex_limit: int | None = None,
) -> UKLegislationExtractReport:
    """Extract UK section/regulation text into normalized corpus artifacts.

    Local ``source_xmls`` are always parsed as legislation.gov.uk CLML. Remote
    ``citations`` are fetched from CLML by default, or from the Lex API when
    ``source="lex"``. Lex citations may be act-level (e.g. ``ukpga/2007/3``) to
    ingest every section of an instrument, or section-level to ingest one.
    """
    if not source_xmls and not citations:
        raise ValueError("at least one source XML path or citation is required")
    if source not in ("clml", "lex"):
        raise ValueError(f"unknown source backend: {source}")

    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)

    prepared: list[_PreparedSource] = [
        _prepare_clml_source(name, source_bytes)
        for name, source_bytes in _iter_source_xmls(source_xmls)
    ]
    if citations:
        if source == "lex":
            prepared.extend(_fetch_lex_sources(citations, limit=lex_limit))
        else:
            prepared.extend(
                _prepare_clml_source(name, source_bytes)
                for name, source_bytes in asyncio.run(_fetch_citation_xmls(citations))
            )

    grouped_records: dict[str, list[ProvisionRecord]] = defaultdict(list)
    grouped_inventory: dict[str, list[SourceInventoryItem]] = defaultdict(list)
    grouped_sources: dict[str, list[tuple[str, bytes]]] = defaultdict(list)

    for item in prepared:
        section = item.section
        document_class = uk_document_class(section.citation)
        citation_path = uk_citation_path(section)
        source_artifact_path = store.source_path(
            "uk",
            document_class,
            version,
            item.relative_name,
        )
        source_key = _source_key(version, document_class, item.relative_name)
        source_sha256 = store.write_bytes(source_artifact_path, item.raw_bytes)
        record = _section_record(
            section,
            citation_path=citation_path,
            document_class=document_class,
            version=version,
            source_path=source_key,
            source_format=item.source_format,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )
        grouped_records[document_class].append(record)
        grouped_inventory[document_class].append(
            SourceInventoryItem(
                citation_path=citation_path,
                source_url=section.source_url or section.citation.legislation_url,
                source_path=source_key,
                source_format=item.source_format,
                sha256=source_sha256,
                metadata={
                    "source_name": item.source_name,
                    "legislation_type": section.citation.type,
                    "provision_segment": section.citation.provision_segment,
                    "heading": section.title,
                },
            )
        )
        grouped_sources[document_class].append((item.relative_name, item.raw_bytes))

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
        if citation.provision_segment == "schedule":
            parts.extend(["schedule", citation.section])
        else:
            parts.append(citation.section)
    return "/".join(parts)


def _section_record(
    section: UKSection,
    *,
    citation_path: str,
    document_class: str,
    version: str,
    source_path: str,
    source_format: str,
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
        source_format=source_format,
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


def _prepare_clml_source(source_name: str, source_bytes: bytes) -> _PreparedSource:
    section = parse_section(source_bytes.decode("utf-8"))
    return _PreparedSource(
        section=section,
        raw_bytes=source_bytes,
        source_format=UK_SOURCE_FORMAT,
        relative_name=_source_relative_name(section),
        source_name=source_name,
    )


def _fetch_lex_sources(
    citations: Sequence[str],
    *,
    limit: int | None,
    client: LexClient | None = None,
) -> list[_PreparedSource]:
    """Fetch normalized provision text from the Lex API.

    Each citation's act is fetched once and cached; section-level citations
    filter the act's provisions to the requested number. Schedules are skipped
    because the citation model does not yet represent them.
    """
    client = client or LexClient()
    prepared: list[_PreparedSource] = []
    act_cache: dict[str, tuple[date, list[dict[str, object]]]] = {}

    for raw_citation in citations:
        citation = UKCitation.from_string(raw_citation)
        act_id = f"{citation.type}/{citation.year}/{citation.number}"
        if act_id not in act_cache:
            legislation = client.lookup_legislation(citation.type, citation.year, citation.number)
            reference_date = legislation.reference_date
            if reference_date is None:
                raise ValueError(f"Lex returned no usable date for {act_id}")
            fetch_limit = limit or legislation.number_of_provisions or _LEX_DEFAULT_LIMIT
            act_cache[act_id] = (
                reference_date,
                client.lookup_sections_raw(act_id, fetch_limit),
            )
        enacted_date, raw_sections = act_cache[act_id]

        matched = 0
        for raw_section in raw_sections:
            lex_section = LexSection.model_validate(raw_section)
            if lex_section.provision_type != "section":
                continue
            token = _provision_token(lex_section.uri or lex_section.id)
            if token is None:
                continue
            provision = token[1]
            if citation.section is not None and provision.lower() != citation.section.lower():
                continue
            section_citation = UKCitation(
                type=citation.type,
                year=citation.year,
                number=citation.number,
                section=provision,
                subsection=None,
            )
            prepared.append(
                _PreparedSource(
                    section=_lex_section_to_uksection(section_citation, lex_section, enacted_date),
                    raw_bytes=json.dumps(raw_section, ensure_ascii=False, sort_keys=True).encode(
                        "utf-8"
                    ),
                    source_format=LEX_SOURCE_FORMAT,
                    relative_name=_lex_relative_name(section_citation),
                    source_name=lex_section.id,
                )
            )
            matched += 1

        if citation.section is not None and matched == 0:
            raise ValueError(f"Lex returned no section matching {raw_citation}")

    return prepared


def _lex_section_to_uksection(
    citation: UKCitation,
    lex_section: LexSection,
    enacted_date: date,
) -> UKSection:
    return UKSection(
        citation=citation,
        title=lex_section.title or citation.short_cite,
        text=lex_section.text,
        enacted_date=enacted_date,
        commencement_date=None,
        source_url=lex_section.uri or citation.legislation_url,
        retrieved_at=date.today(),
    )


def _lex_relative_name(citation: UKCitation) -> str:
    provision = citation.section or "document"
    return (
        f"{citation.type}/{citation.year}/{citation.number}/"
        f"{citation.provision_segment}-{provision}.json"
    )


def _provision_token(uri: str) -> tuple[str, str] | None:
    match = _PROVISION_URI_RE.search(uri)
    if not match:
        return None
    return match.group(1), match.group(2)


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
            raise ValueError(f"section, regulation, or schedule required: {raw_citation}")
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
