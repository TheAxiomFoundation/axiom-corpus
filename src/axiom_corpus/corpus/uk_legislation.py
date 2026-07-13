"""UK legislation extraction into source-first corpus artifacts."""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
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

# legislation.gov.uk CLML embeds editorial-annotation identifiers of the form
# ``key-<32 hex>`` (an MD5-shaped digest), optionally suffixed with a volatile
# ``-<epoch-ms>`` timestamp. They occur only inside XML tags -- as attribute
# values such as ``ChangeId``, ``CommentaryRef``/``Ref``, ``EffectId`` and
# Commentary ``id``, and as the final path segment of effect ``URI`` values in
# ``ukm:UnappliedEffects`` blocks -- never in element text. Archiving them
# verbatim is doubly harmful: the 32-hex shape is a false positive for GitHub's
# Mailgun API-key push-protection detector (which blocks every commit that adds
# such a file), and the epoch-ms suffix is regenerated on every fetch, so
# byte-identical legislation re-fetched later produces a spuriously different
# source capture.
#
# Sanitization is scoped to tag content (``_CLML_TAG_RE``) so that a matching
# literal in legislative text, a title, or other substantive content is never
# rewritten -- that would desync the archived capture from the provisions, which
# derive from the pre-sanitization bytes. The ``{32,}`` quantifier (rather than
# exactly ``{32}``) guarantees no ``key-<32 hex>`` substring can survive even for
# a longer future digest.
_CLML_TAG_RE = re.compile(r"<[^>]*>")
_CLML_EDITORIAL_ANCHOR_RE = re.compile(r"key-([0-9a-f]{32,})(?:-[0-9]+)?")


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
        records = _drop_missing_parent_links(_dedupe_records(grouped_records[document_class]))
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
    """Return the canonical corpus citation path for a UK provision."""
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
            if citation.paragraph:
                parts.extend(["paragraph", citation.paragraph])
        elif citation.provision_segment == "article":
            parts.extend([citation.provision_segment, citation.section])
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
    parent_path = _parent_citation_path(citation, citation_path)
    kind = _provision_kind(citation)
    ordinal = _provision_ordinal(citation.paragraph or citation.section)
    identifiers = {
        "legislation.gov.uk:type": citation.type,
        "legislation.gov.uk:year": str(citation.year),
        "legislation.gov.uk:number": str(citation.number),
        "legislation.gov.uk:provision": _legislation_provision_identifier(citation),
    }
    metadata = {
        "extent": section.extent,
        "references_to": section.references_to,
        "retrieved_at": (section.retrieved_at.isoformat() if section.retrieved_at else None),
    }
    if citation.provision_segment == "schedule" and citation.paragraph:
        metadata["schedule"] = citation.section
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
        level=2 if citation.paragraph else 1,
        ordinal=ordinal,
        kind=kind,
        legal_identifier=citation.short_cite,
        identifiers=identifiers,
        metadata=metadata,
    )


def _prepare_clml_source(source_name: str, source_bytes: bytes) -> _PreparedSource:
    normalized_source_bytes = _normalize_clml_source_bytes(source_bytes)
    # Provisions, coverage and inventory citations are derived from the
    # pre-sanitization bytes, so editorial-anchor sanitization cannot affect
    # them; only the archived source capture (``raw_bytes``) is sanitized.
    section = parse_section(normalized_source_bytes.decode("utf-8"))
    sanitized_source_bytes = _sanitize_clml_editorial_anchors(normalized_source_bytes)
    return _PreparedSource(
        section=section,
        raw_bytes=sanitized_source_bytes,
        source_format=UK_SOURCE_FORMAT,
        relative_name=_source_relative_name(section),
        source_name=source_name,
    )


def _normalize_clml_source_bytes(source_bytes: bytes) -> bytes:
    """Normalize CLML source bytes for stable storage without changing XML content."""
    text = source_bytes.decode("utf-8")
    normalized_text = "\n".join(line.rstrip() for line in text.splitlines())
    if text.endswith(("\n", "\r")):
        normalized_text += "\n"
    return normalized_text.encode("utf-8")


def _sanitize_clml_editorial_anchors(source_bytes: bytes) -> bytes:
    """Rewrite volatile CLML editorial-annotation anchors to deterministic,
    document-local placeholders for the archived source capture.

    Each distinct ``key-<hex>`` anchor found **inside a tag** is replaced with
    ``key-a<N>``, where ``N`` counts distinct anchors in first-occurrence order
    (the first distinct anchor becomes ``key-a1``, the second ``key-a2`` ...),
    and the volatile ``-<epoch-ms>`` timestamp suffix is dropped. The mapping is
    keyed on the hex digest, so identical source anchors always map to the same
    placeholder and intra-document referential pairing is preserved: a
    ``CommentaryRef``/``Ref`` and the ``Commentary`` ``id`` it targets stay
    matched, an ``EffectId`` and its effect ``URI`` stay matched, and two
    ``Substitution`` elements that share one commentary but carry different
    ``ChangeId`` timestamps collapse onto the same placeholder.

    Replacement is scoped to tag content, so an identical literal appearing in
    element text (a body, a title) is left untouched -- the archived capture must
    not diverge from the substantive text that provisions are derived from.

    The transform is deterministic for a fixed input and idempotent: a
    placeholder ``key-a<N>`` is far shorter than the 32-hex-minimum input
    pattern, so a second pass matches nothing and returns the input unchanged.

    Only the archived source capture is sanitized. Provision, coverage and
    inventory-citation derivations are parsed from the pre-sanitization bytes in
    :func:`_prepare_clml_source`, so they are unaffected; the accompanying tests
    additionally prove provision bodies are byte-identical whether parsed from
    sanitized or unsanitized XML, because bodies strip editorial markup.
    """
    placeholders: dict[str, str] = {}

    def _placeholder(match: re.Match[str]) -> str:
        digest = match.group(1)
        placeholder = placeholders.get(digest)
        if placeholder is None:
            placeholder = f"key-a{len(placeholders) + 1}"
            placeholders[digest] = placeholder
        return placeholder

    def _sanitize_tag(tag_match: re.Match[str]) -> str:
        return _CLML_EDITORIAL_ANCHOR_RE.sub(_placeholder, tag_match.group(0))

    text = source_bytes.decode("utf-8")
    return _CLML_TAG_RE.sub(_sanitize_tag, text).encode("utf-8")


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
                provision_kind=citation.provision_kind,
                paragraph=None,
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
            raise ValueError(f"section, regulation, article, or schedule required: {raw_citation}")
        url = fetcher.build_url(citation)
        xml = await fetcher._fetch_xml(url)
        fetched.append((_source_relative_name_from_citation(citation), xml.encode()))
    return fetched


def _source_relative_name(section: UKSection) -> str:
    return _source_relative_name_from_citation(section.citation)


def _source_relative_name_from_citation(citation: UKCitation) -> str:
    provision = _source_provision_name(citation)
    return f"{citation.type}/{citation.year}/{citation.number}/{provision}.xml"


def _source_provision_name(citation: UKCitation) -> str:
    if citation.section is None:
        return f"{citation.provision_segment}-document"
    name = f"{citation.provision_segment}-{citation.section}"
    if citation.paragraph:
        name += f"-paragraph-{citation.paragraph}"
    return name


def _parent_citation_path(citation: UKCitation, citation_path: str) -> str:
    if citation.provision_segment == "schedule" and citation.paragraph:
        return "/".join(citation_path.split("/")[:-2])
    if citation.provision_segment == "article":
        return "/".join(citation_path.split("/")[:-2])
    return "/".join(citation_path.split("/")[:-1])


def _provision_kind(citation: UKCitation) -> str:
    if citation.provision_segment == "schedule" and citation.paragraph:
        return "paragraph"
    return citation.provision_segment


def _legislation_provision_identifier(citation: UKCitation) -> str:
    if not citation.section:
        return ""
    if citation.provision_segment == "schedule" and citation.paragraph:
        return f"schedule/{citation.section}/paragraph/{citation.paragraph}"
    if citation.provision_segment == "article":
        return f"{citation.provision_segment}/{citation.section}"
    return citation.section


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


def _drop_missing_parent_links(records: Iterable[ProvisionRecord]) -> tuple[ProvisionRecord, ...]:
    materialized = tuple(records)
    citation_paths = {record.citation_path for record in materialized}
    return tuple(
        replace(record, parent_citation_path=None, parent_id=None)
        if record.parent_citation_path and record.parent_citation_path not in citation_paths
        else record
        for record in materialized
    )


def _dedupe_inventory(
    items: Iterable[SourceInventoryItem],
) -> tuple[SourceInventoryItem, ...]:
    by_path: dict[str, SourceInventoryItem] = {}
    for item in items:
        by_path[item.citation_path] = item
    return tuple(by_path[path] for path in sorted(by_path))
