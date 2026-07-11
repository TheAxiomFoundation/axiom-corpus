"""New Zealand legislation extraction into source-first corpus artifacts."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import cast
from xml.etree import ElementTree as ET

from axiom_corpus.converters.nz_pco import (
    NZLegislation,
    NZLegislationSubtype,
    NZPCOConverter,
    NZProvision,
    render_nz_pco_legal_text,
)
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

NZ_SOURCE_FORMAT = "legislation.govt.nz-pco-xml"


@dataclass(frozen=True)
class _PreparedLegislation:
    """Parsed NZ legislation plus the raw source snapshot."""

    legislation: NZLegislation
    raw_bytes: bytes
    current_bytes: bytes
    relative_name: str
    source_name: str


@dataclass(frozen=True)
class _StructuralFragment:
    """One PCO-authored schedule hierarchy node or definition."""

    path_suffix: str
    parent_suffix: str | None
    source_element_id: str
    kind: str
    label: str
    heading: str | None
    body: str | None
    level: int
    ordinal: int | None


@dataclass(frozen=True)
class _ScheduleProvisionPath:
    """Canonical schedule ancestry for one PCO provision element."""

    path_suffix: str
    parent_suffix: str
    level: int


@dataclass(frozen=True)
class NZLegislationClassExtractReport:
    """Artifact report for one NZ document class."""

    document_class: str
    source_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class NZLegislationExtractReport:
    """Combined NZ legislation extraction report."""

    version: str
    source_count: int
    provisions_written: int
    class_reports: tuple[NZLegislationClassExtractReport, ...]


def extract_nz_legislation(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_xmls: Sequence[str | Path] = (),
    source_dir: str | Path | None = None,
    source_pattern: str = "*.xml",
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    limit: int | None = None,
) -> NZLegislationExtractReport:
    """Extract NZ PCO XML into normalized corpus artifacts.

    The live legislation.govt.nz XML endpoint is WAF-prone. This adapter is
    intentionally local-file first so full-country ingestion can run from the
    official data.govt.nz bulk XML release.
    """
    if not source_xmls and source_dir is None:
        raise ValueError("at least one source XML path or source directory is required")

    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    prepared = _prepare_sources(
        source_xmls=source_xmls,
        source_dir=source_dir,
        source_pattern=source_pattern,
        limit=limit,
    )

    grouped_records: dict[str, list[ProvisionRecord]] = defaultdict(list)
    grouped_inventory: dict[str, list[SourceInventoryItem]] = defaultdict(list)
    grouped_sources: dict[str, dict[str, Path]] = defaultdict(dict)

    for item in prepared:
        legislation = item.legislation
        document_class = nz_document_class(legislation)
        source_artifact_path = store.source_path(
            "nz",
            document_class,
            version,
            item.relative_name,
        )
        source_key = _source_key(version, document_class, item.relative_name)
        source_sha256 = store.write_bytes(source_artifact_path, item.raw_bytes)
        grouped_sources[document_class][item.relative_name] = source_artifact_path

        document_record = _document_record(
            legislation,
            document_class=document_class,
            version=version,
            source_path=source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )
        grouped_records[document_class].append(document_record)
        grouped_inventory[document_class].append(
            SourceInventoryItem(
                citation_path=document_record.citation_path,
                source_url=document_record.source_url,
                source_path=source_key,
                source_format=NZ_SOURCE_FORMAT,
                sha256=source_sha256,
                metadata={
                    "source_name": item.source_name,
                    "title": legislation.title,
                    "legislation_type": legislation.legislation_type,
                    "subtype": legislation.subtype,
                    "year": legislation.year,
                    "number": legislation.number,
                    "document_id": legislation.id,
                    "kind": "document",
                },
            )
        )

        for fragment in _structural_fragments(item.current_bytes):
            record = _structural_record(
                legislation,
                fragment,
                document_class=document_class,
                version=version,
                source_path=source_key,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
            )
            grouped_records[document_class].append(record)
            grouped_inventory[document_class].append(
                SourceInventoryItem(
                    citation_path=record.citation_path,
                    source_url=record.source_url,
                    source_path=source_key,
                    source_format=NZ_SOURCE_FORMAT,
                    sha256=source_sha256,
                    metadata={
                        "source_name": item.source_name,
                        "title": legislation.title,
                        "legislation_type": legislation.legislation_type,
                        "subtype": legislation.subtype,
                        "year": legislation.year,
                        "number": legislation.number,
                        "source_element_id": fragment.source_element_id,
                        "kind": fragment.kind,
                        "label": fragment.label,
                        "heading": fragment.heading,
                    },
                )
            )

        for provision in legislation.provisions:
            citation_path = nz_citation_path(legislation, provision)
            record = _provision_record(
                legislation,
                provision,
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
                    source_url=record.source_url,
                    source_path=source_key,
                    source_format=NZ_SOURCE_FORMAT,
                    sha256=source_sha256,
                    metadata={
                        "source_name": item.source_name,
                        "title": legislation.title,
                        "legislation_type": legislation.legislation_type,
                        "subtype": legislation.subtype,
                        "year": legislation.year,
                        "number": legislation.number,
                        "provision_id": provision.id,
                        "provision_label": provision.label,
                        "heading": provision.heading,
                    },
                )
            )

    class_reports: list[NZLegislationClassExtractReport] = []
    for document_class in sorted(grouped_records):
        records = _dedupe_records(grouped_records[document_class])
        inventory = _dedupe_inventory(grouped_inventory[document_class])
        inventory_path = store.inventory_path("nz", document_class, version)
        store.write_inventory(inventory_path, inventory)
        provisions_path = store.provisions_path("nz", document_class, version)
        store.write_provisions(provisions_path, records)
        coverage = compare_provision_coverage(
            inventory,
            records,
            jurisdiction="nz",
            document_class=document_class,
            version=version,
        )
        coverage_path = store.coverage_path("nz", document_class, version)
        store.write_json(coverage_path, coverage.to_mapping())
        source_paths = tuple(
            grouped_sources[document_class][name]
            for name in sorted(grouped_sources[document_class])
        )
        class_reports.append(
            NZLegislationClassExtractReport(
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

    return NZLegislationExtractReport(
        version=version,
        source_count=sum(report.source_count for report in class_reports),
        provisions_written=sum(report.provisions_written for report in class_reports),
        class_reports=tuple(class_reports),
    )


def nz_document_class(legislation: NZLegislation) -> str:
    """Return the corpus document class for NZ legislation."""
    if legislation.legislation_type == "act":
        return DocumentClass.STATUTE.value
    if legislation.legislation_type == "regulation":
        return DocumentClass.REGULATION.value
    if legislation.legislation_type in {"bill", "sop"}:
        return DocumentClass.RULEMAKING.value
    return DocumentClass.OTHER.value


def nz_citation_path(legislation: NZLegislation, provision: NZProvision) -> str:
    """Return the canonical corpus citation path for an NZ provision."""
    if provision.citation_path_suffix:
        return f"{_parent_citation_path(legislation)}/{provision.citation_path_suffix}"
    return "/".join(
        [
            "nz",
            nz_document_class(legislation),
            legislation.legislation_type,
            legislation.subtype,
            str(legislation.year),
            _document_number_token(legislation).lower(),
            _provision_kind(legislation),
            (provision.path_token or _provision_token(provision.label or provision.id)).lower(),
        ]
    )


def _document_record(
    legislation: NZLegislation,
    *,
    document_class: str,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    citation_path = _parent_citation_path(legislation)
    source_url = legislation.url
    legal_identifier = legislation.citation
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction="nz",
        document_class=document_class,
        citation_path=citation_path,
        citation_label=legislation.title,
        heading=legislation.title,
        body=None,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=source_url,
        source_format=NZ_SOURCE_FORMAT,
        source_document_id=_source_document_id(legislation),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=None,
        parent_id=None,
        level=1,
        ordinal=1,
        kind="document",
        legal_identifier=legal_identifier,
        identifiers={
            "legislation.govt.nz:document": _source_document_id(legislation),
            "legislation.govt.nz:id": legislation.id,
            "legislation.govt.nz:type": legislation.legislation_type,
            "legislation.govt.nz:subtype": legislation.subtype,
            "legislation.govt.nz:year": str(legislation.year),
            "legislation.govt.nz:number": str(legislation.number),
        },
        metadata={
            "title": legislation.title,
            "long_title": legislation.long_title,
            "stage": legislation.stage,
            "assent_date": _date_text(legislation.assent_date, ""),
            "version_date": _date_text(legislation.version_date, ""),
            "administering_ministry": legislation.administering_ministry,
            "document_id": legislation.id,
        },
    )


def _structural_record(
    legislation: NZLegislation,
    fragment: _StructuralFragment,
    *,
    document_class: str,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    document_path = _parent_citation_path(legislation)
    citation_path = f"{document_path}/{fragment.path_suffix}"
    parent_path = (
        f"{document_path}/{fragment.parent_suffix}" if fragment.parent_suffix else document_path
    )
    source_url = _source_element_url(legislation, fragment.source_element_id)
    legal_identifier = f"{legislation.title} {fragment.label}".strip()
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction="nz",
        document_class=document_class,
        citation_path=citation_path,
        citation_label=legal_identifier,
        heading=fragment.heading,
        body=fragment.body,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=source_url,
        source_format=NZ_SOURCE_FORMAT,
        source_document_id=_source_document_id(legislation),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=fragment.level,
        ordinal=fragment.ordinal,
        kind=fragment.kind,
        legal_identifier=legal_identifier,
        identifiers={
            "legislation.govt.nz:document": _source_document_id(legislation),
            "legislation.govt.nz:element": fragment.source_element_id,
            "legislation.govt.nz:type": legislation.legislation_type,
            "legislation.govt.nz:subtype": legislation.subtype,
            "legislation.govt.nz:year": str(legislation.year),
            "legislation.govt.nz:number": str(legislation.number),
        },
        metadata={
            "title": legislation.title,
            "long_title": legislation.long_title,
            "stage": legislation.stage,
            "assent_date": _date_text(legislation.assent_date, ""),
            "version_date": _date_text(legislation.version_date, ""),
            "administering_ministry": legislation.administering_ministry,
            "source_element_id": fragment.source_element_id,
            "structural_label": fragment.label,
        },
    )


def _provision_record(
    legislation: NZLegislation,
    provision: NZProvision,
    *,
    citation_path: str,
    document_class: str,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    document_path = _parent_citation_path(legislation)
    parent_path = (
        f"{document_path}/{provision.parent_citation_path_suffix}"
        if provision.parent_citation_path_suffix
        else document_path
    )
    legal_identifier = _citation_label(legislation, provision)
    identifiers = {
        "legislation.govt.nz:document": _source_document_id(legislation),
        "legislation.govt.nz:provision": provision.id,
        "legislation.govt.nz:type": legislation.legislation_type,
        "legislation.govt.nz:subtype": legislation.subtype,
        "legislation.govt.nz:year": str(legislation.year),
        "legislation.govt.nz:number": str(legislation.number),
        "legislation.govt.nz:label": provision.label,
    }
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction="nz",
        document_class=document_class,
        citation_path=citation_path,
        citation_label=legal_identifier,
        heading=provision.heading,
        body=_provision_body(provision),
        version=version,
        source_url=_provision_url(legislation, provision),
        source_path=source_path,
        source_id=_provision_url(legislation, provision),
        source_format=NZ_SOURCE_FORMAT,
        source_document_id=_source_document_id(legislation),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=provision.corpus_level,
        ordinal=_provision_ordinal(provision.label),
        kind=provision.corpus_kind or _provision_kind(legislation),
        legal_identifier=legal_identifier,
        identifiers=identifiers,
        metadata={
            "title": legislation.title,
            "long_title": legislation.long_title,
            "stage": legislation.stage,
            "assent_date": _date_text(legislation.assent_date, ""),
            "version_date": _date_text(legislation.version_date, ""),
            "administering_ministry": legislation.administering_ministry,
            "provision_id": provision.id,
            "provision_label": provision.label,
            "provision_path_token": provision.path_token,
            "schedule_path_suffix": provision.citation_path_suffix,
        },
    )


def _schedule_hierarchy(
    source_bytes: bytes,
) -> tuple[tuple[_StructuralFragment, ...], dict[str, _ScheduleProvisionPath]]:
    root = ET.fromstring(source_bytes)
    fragments: list[_StructuralFragment] = []
    provision_paths: dict[str, _ScheduleProvisionPath] = {}
    seen_paths: set[str] = set()

    for schedule in root.iter("schedule"):
        schedule_id = schedule.get("id", "").strip()
        schedule_label = _direct_child_text(schedule, "label")
        if not schedule_id or not schedule_label:
            continue
        schedule_token = _structural_token(schedule_label, prefix="schedule")
        schedule_suffix = _unique_structural_suffix(
            f"schedule/{schedule_token}",
            source_element_id=schedule_id,
            seen_paths=seen_paths,
        )
        parent_map = {child: parent for parent in schedule.iter() for child in list(parent)}
        hierarchy_tags = {"head1", "head2", "part", "subpart"}
        schedule_body = _structural_own_body(schedule)
        fragments.append(
            _StructuralFragment(
                path_suffix=schedule_suffix,
                parent_suffix=None,
                source_element_id=schedule_id,
                kind="schedule",
                label=f"Schedule {schedule_label}",
                heading=_direct_child_text(schedule, "heading") or None,
                body=schedule_body,
                level=2,
                ordinal=_provision_ordinal(schedule_label),
            )
        )
        hierarchy_suffixes: dict[ET.Element, str] = {schedule: schedule_suffix}
        hierarchy_levels: dict[ET.Element, int] = {schedule: 2}
        for element in (
            candidate for candidate in schedule.iter() if candidate.tag in hierarchy_tags
        ):
            element_id = element.get("id", "").strip()
            element_label = _direct_child_text(element, "label")
            element_heading = _direct_child_text(element, "heading")
            structural_name = element_label or element_heading
            if not element_id or not structural_name:
                continue
            parent_element = _nearest_mapped_ancestor(
                element,
                parent_map=parent_map,
                stop=schedule,
                mapped=hierarchy_suffixes,
            )
            if parent_element is None:
                parent_element = schedule
            parent_suffix = hierarchy_suffixes.get(parent_element, schedule_suffix)
            parent_level = hierarchy_levels.get(parent_element, 2)
            kind = "part" if element.tag in {"head1", "part"} else "subpart"
            token = _structural_token(structural_name, prefix=kind)
            suffix = _unique_structural_suffix(
                f"{parent_suffix}/{kind}/{token}",
                source_element_id=element_id,
                seen_paths=seen_paths,
            )
            hierarchy_suffixes[element] = suffix
            hierarchy_levels[element] = parent_level + 1
            body = _structural_own_body(element)
            fragments.append(
                _StructuralFragment(
                    path_suffix=suffix,
                    parent_suffix=parent_suffix,
                    source_element_id=element_id,
                    kind=kind,
                    label=structural_name,
                    heading=element_heading or None,
                    body=body,
                    level=parent_level + 1,
                    ordinal=(_provision_ordinal(token) if element_label else None),
                )
            )

        for definition in schedule.iter("def-para"):
            if _has_ancestor_tag(
                definition,
                parent_map=parent_map,
                stop=schedule,
                tags={"prov"},
            ):
                continue
            definition_id = definition.get("id", "").strip()
            definition_body = _source_element_text(definition)
            if not definition_id or not definition_body:
                continue
            definition_label = _definition_label(definition, definition_body)
            definition_token = _slug_token(definition_label)
            nearest_container = _nearest_mapped_ancestor(
                definition,
                parent_map=parent_map,
                stop=schedule,
                mapped=hierarchy_suffixes,
            )
            parent_suffix = (
                hierarchy_suffixes.get(nearest_container, schedule_suffix)
                if nearest_container is not None
                else schedule_suffix
            )
            parent_level = (
                hierarchy_levels.get(nearest_container, 2) if nearest_container is not None else 2
            )
            definition_suffix = f"{parent_suffix}/definition/{definition_token}"
            definition_suffix = _unique_structural_suffix(
                definition_suffix,
                source_element_id=definition_id,
                seen_paths=seen_paths,
            )
            fragments.append(
                _StructuralFragment(
                    path_suffix=definition_suffix,
                    parent_suffix=parent_suffix,
                    source_element_id=definition_id,
                    kind="definition",
                    label=definition_label,
                    heading=definition_label,
                    body=definition_body,
                    level=parent_level + 1,
                    ordinal=None,
                )
            )

        for provision in schedule.iter("prov"):
            provision_id = (provision.get("id") or "").strip()
            provision_label = _direct_child_text(provision, "label")
            if not provision_id:
                raise ValueError("Every current NZ schedule provision must have a PCO id.")
            nearest_container = _nearest_mapped_ancestor(
                provision,
                parent_map=parent_map,
                stop=schedule,
                mapped=hierarchy_suffixes,
            )
            parent_suffix = (
                hierarchy_suffixes.get(nearest_container, schedule_suffix)
                if nearest_container is not None
                else schedule_suffix
            )
            parent_level = (
                hierarchy_levels.get(nearest_container, 2) if nearest_container is not None else 2
            )
            clause_name = (
                provision_label or _direct_child_text(provision, "heading") or provision_id
            )
            clause_token = _slug_token(clause_name)
            path_suffix = _unique_structural_suffix(
                f"{parent_suffix}/clause/{clause_token}",
                source_element_id=provision_id,
                seen_paths=seen_paths,
            )
            if provision_id in provision_paths:
                raise ValueError(f"Duplicate current NZ PCO provision id: {provision_id}")
            provision_paths[provision_id] = _ScheduleProvisionPath(
                path_suffix=path_suffix,
                parent_suffix=parent_suffix,
                level=parent_level + 1,
            )

    return tuple(fragments), provision_paths


def _structural_fragments(source_bytes: bytes) -> tuple[_StructuralFragment, ...]:
    return _schedule_hierarchy(source_bytes)[0]


def _assign_schedule_provision_paths(
    legislation: NZLegislation,
    source_bytes: bytes,
) -> None:
    _, schedule_paths = _schedule_hierarchy(source_bytes)
    for provision in legislation.provisions:
        schedule_path = schedule_paths.get(provision.id)
        if schedule_path is None:
            continue
        provision.citation_path_suffix = schedule_path.path_suffix
        provision.parent_citation_path_suffix = schedule_path.parent_suffix
        provision.corpus_level = schedule_path.level
        provision.corpus_kind = "clause"
        provision.path_token = schedule_path.path_suffix.rsplit("/", 1)[-1]


def _direct_child_text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    if child is None:
        return ""
    return _normalized_element_text(child)


def _source_element_text(element: ET.Element) -> str:
    parts: list[str] = []

    def collect(node: ET.Element) -> None:
        if node.tag in {"notes", "history", "history-note"}:
            return
        if node.text and node.text.strip():
            parts.append(node.text.strip())
        for child in node:
            collect(child)
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())

    collect(element)
    return " ".join(" ".join(parts).split())


def _structural_own_body(element: ET.Element) -> str | None:
    """Render only text asserted directly by a schedule hierarchy node.

    Parts, subparts, and heads are containers. Their body may contain direct
    paragraphs or tables, but must never recursively absorb child hierarchy,
    provision, or definition bodies that receive their own corpus rows.
    """
    body_tags = {"para", "table"}
    excluded_subtrees = {
        "def-para",
        "head1",
        "head2",
        "history",
        "history-note",
        "notes",
        "part",
        "prov",
        "subpart",
    }

    owned_body_nodes: list[ET.Element] = []

    def collect(node: ET.Element) -> None:
        if node.tag in excluded_subtrees:
            return
        if node.tag in body_tags:
            owned_body_nodes.append(node)
            return
        for child in node:
            collect(child)

    for child in element:
        collect(child)
    body = "\n".join(
        rendered
        for node in owned_body_nodes
        if (
            rendered := render_nz_pco_legal_text(
                node,
                excluded={
                    descendant
                    for descendant in node.iter()
                    if descendant is not node and descendant.tag in excluded_subtrees
                },
            )
        )
    )
    return body or None


def _normalized_element_text(element: ET.Element) -> str:
    return " ".join(" ".join(element.itertext()).split())


def _definition_label(definition: ET.Element, body: str) -> str:
    term = definition.find(".//def-term")
    if term is not None:
        label = _normalized_element_text(term)
        if label:
            return label
    match = re.match(r"(.{1,160}?)\s+means\b", body, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return definition.get("id", "definition")


def _structural_token(label: str, *, prefix: str) -> str:
    without_prefix = re.sub(
        rf"^{re.escape(prefix)}\s+",
        "",
        label.strip(),
        flags=re.IGNORECASE,
    )
    return _slug_token(without_prefix)


def _slug_token(label: str) -> str:
    token = re.sub(r"[^0-9A-Za-z]+", "-", label.strip()).strip("-").lower()
    return token or "unnumbered"


def _unique_structural_suffix(
    suffix: str,
    *,
    source_element_id: str,
    seen_paths: set[str],
) -> str:
    if suffix not in seen_paths:
        seen_paths.add(suffix)
        return suffix
    unique = f"{suffix}-{_slug_token(source_element_id)}"
    seen_paths.add(unique)
    return unique


def _has_ancestor_tag(
    element: ET.Element,
    *,
    parent_map: dict[ET.Element, ET.Element],
    stop: ET.Element,
    tags: set[str],
) -> bool:
    current = parent_map.get(element)
    while current is not None and current is not stop:
        if current.tag in tags:
            return True
        current = parent_map.get(current)
    return False


def _nearest_mapped_ancestor(
    element: ET.Element,
    *,
    parent_map: dict[ET.Element, ET.Element],
    stop: ET.Element,
    mapped: Mapping[ET.Element, object],
) -> ET.Element | None:
    """Return the nearest ancestor that has an emitted structural row."""
    current = parent_map.get(element)
    while current is not None and current is not stop:
        if current in mapped:
            return current
        current = parent_map.get(current)
    return None


def _prepare_sources(
    *,
    source_xmls: Sequence[str | Path],
    source_dir: str | Path | None,
    source_pattern: str,
    limit: int | None,
) -> list[_PreparedLegislation]:
    converter = NZPCOConverter()
    prepared: list[_PreparedLegislation] = []
    for source_name, source_bytes in _iter_source_xmls(
        source_xmls=source_xmls,
        source_dir=source_dir,
        source_pattern=source_pattern,
        limit=limit,
    ):
        normalized = _normalize_source_bytes(source_bytes)
        current_bytes = _current_law_source_bytes(normalized)
        legislation = converter.parse_xml(current_bytes.decode("utf-8"))
        _apply_source_name_metadata(legislation, source_name)
        _assign_schedule_provision_paths(legislation, current_bytes)
        relative_name = _source_relative_name(legislation, source_name)
        prepared.append(
            _PreparedLegislation(
                legislation=legislation,
                raw_bytes=normalized,
                current_bytes=current_bytes,
                relative_name=relative_name,
                source_name=relative_name,
            )
        )
    return prepared


def _iter_source_xmls(
    *,
    source_xmls: Sequence[str | Path],
    source_dir: str | Path | None,
    source_pattern: str,
    limit: int | None,
) -> Iterable[tuple[str, bytes]]:
    named_paths = [(Path(path).name, Path(path)) for path in source_xmls]
    if source_dir is not None:
        source_root = Path(source_dir)
        named_paths.extend(
            (path.relative_to(source_root).as_posix(), path)
            for path in sorted(source_root.rglob(source_pattern))
        )
    if limit is not None:
        named_paths = named_paths[:limit]
    for source_name, path in named_paths:
        yield source_name, path.read_bytes()


def _normalize_source_bytes(source_bytes: bytes) -> bytes:
    text = source_bytes.decode("utf-8-sig")
    normalized_text = "\n".join(line.rstrip() for line in text.splitlines())
    if text.endswith(("\n", "\r")):
        normalized_text += "\n"
    return normalized_text.encode("utf-8")


def _current_law_source_bytes(source_bytes: bytes) -> bytes:
    """Return parser input with officially inactive content removed.

    The source snapshot remains byte-for-byte official XML. A document is
    eligible only when its PCO ``stage`` is absent or ``in-force`` and its
    ``deletion-status`` is absent. Within an eligible document, this filtered
    copy removes every subtree whose root has any other non-empty ``stage`` or
    any non-empty ``deletion-status``. This fail-closed rule prevents a new PCO
    status from silently entering the current-law corpus.
    """
    root = ET.fromstring(source_bytes)
    if _is_inactive_element(root):
        document_id = root.get("id") or "unknown"
        raise ValueError(f"inactive NZ source document is not current law: {document_id}")

    def remove_inactive(parent: ET.Element) -> None:
        for child in list(parent):
            if _is_inactive_element(child):
                parent.remove(child)
                continue
            remove_inactive(child)

    remove_inactive(root)
    return cast(bytes, ET.tostring(root, encoding="utf-8"))


def _is_inactive_element(element: ET.Element) -> bool:
    stage = (element.get("stage") or "").strip().lower()
    deletion_status = (element.get("deletion-status") or "").strip()
    return bool(deletion_status) or bool(stage and stage != "in-force")


def _apply_source_name_metadata(legislation: NZLegislation, source_name: str) -> None:
    parts = PurePosixPath(source_name).parts
    if len(parts) < 4:
        return

    source_type, source_subtype, year_text, number_token = parts[:4]
    if source_type not in {"act", "bill", "secondary-legislation", "amendment-paper"}:
        return

    legislation.source_document_path = "/".join(parts[:4])
    if source_type == "act":
        legislation.legislation_type = "act"
    elif source_type == "bill":
        legislation.legislation_type = "bill"
    elif source_type == "secondary-legislation":
        legislation.legislation_type = "regulation"
    elif source_type == "amendment-paper":
        legislation.legislation_type = "sop"

    subtype = _source_subtype(source_subtype)
    if subtype is not None:
        legislation.subtype = subtype
    if year_text.isdecimal():
        legislation.year = int(year_text)

    source_number = _source_number_value(number_token)
    if source_number is not None:
        legislation.number = source_number
    if not number_token.isdecimal():
        legislation.document_number_token = number_token


def _source_number_value(number_token: str) -> int | None:
    match = re.match(r"\d+", number_token)
    return int(match.group(0)) if match else None


def _source_subtype(source_subtype: str) -> NZLegislationSubtype | None:
    if source_subtype == "public":
        return "public"
    if source_subtype == "private":
        return "private"
    if source_subtype == "local":
        return "local"
    if source_subtype == "government":
        return "government"
    if source_subtype == "members":
        return "members"
    if source_subtype == "imperial":
        return "imperial"
    return None


def _source_relative_name(legislation: NZLegislation, source_name: str | None = None) -> str:
    if source_name and "/" in source_name:
        return source_name
    return (
        f"{legislation.legislation_type}/{legislation.subtype}/"
        f"{legislation.year}/{_document_number_token(legislation)}/wholeof.xml"
    )


def _source_key(version: str, document_class: str, relative_name: str) -> str:
    return f"sources/nz/{document_class}/{version}/{relative_name}"


def _source_document_id(legislation: NZLegislation) -> str:
    if legislation.source_document_path:
        return legislation.source_document_path
    return (
        f"{legislation.legislation_type}/{legislation.subtype}/"
        f"{legislation.year}/{_document_number_token(legislation)}"
    )


def _parent_citation_path(legislation: NZLegislation) -> str:
    return "/".join(
        [
            "nz",
            nz_document_class(legislation),
            legislation.legislation_type,
            legislation.subtype,
            str(legislation.year),
            _document_number_token(legislation).lower(),
        ]
    )


def _provision_kind(legislation: NZLegislation) -> str:
    if legislation.legislation_type == "act":
        return "section"
    if legislation.legislation_type == "regulation":
        return "regulation"
    return "clause"


def _provision_token(label: str) -> str:
    token = label.strip().strip("()")
    token = re.sub(r"[^0-9A-Za-z]+", "-", token).strip("-")
    return token or "unnumbered"


def _citation_label(legislation: NZLegislation, provision: NZProvision) -> str:
    if provision.corpus_kind == "clause":
        return f"{legislation.title} sch cl {provision.label}".strip()
    kind = _provision_kind(legislation)
    if kind == "section":
        prefix = "s"
    elif kind == "regulation":
        prefix = "reg"
    else:
        prefix = "cl"
    return f"{legislation.title} {prefix} {provision.label}".strip()


def _provision_url(legislation: NZLegislation, provision: NZProvision) -> str:
    if provision.id:
        return (
            f"https://www.legislation.govt.nz/{_source_document_id(legislation)}/"
            f"latest/{provision.id}.html"
        )
    return legislation.url


def _source_element_url(legislation: NZLegislation, source_element_id: str) -> str:
    return (
        f"https://www.legislation.govt.nz/{_source_document_id(legislation)}/"
        f"latest/{source_element_id}.html"
    )


def _document_number_token(legislation: NZLegislation) -> str:
    if legislation.document_number_token:
        token = re.sub(r"[^0-9A-Za-z]+", "-", legislation.document_number_token).strip("-")
        if token:
            return token
    return f"{legislation.number:04d}"


def _provision_body(provision: NZProvision) -> str:
    return provision.text


def _provision_ordinal(label: str) -> int | None:
    match = re.match(r"\d+", label.strip())
    return int(match.group(0)) if match else None


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _dedupe_records(records: Iterable[ProvisionRecord]) -> tuple[ProvisionRecord, ...]:
    by_path: dict[str, ProvisionRecord] = {}
    duplicate_paths: set[str] = set()
    for record in records:
        if record.citation_path in by_path:
            duplicate_paths.add(record.citation_path)
            continue
        by_path[record.citation_path] = record
    if duplicate_paths:
        joined = ", ".join(sorted(duplicate_paths))
        raise ValueError(f"duplicate provision citation paths: {joined}")
    return tuple(by_path[path] for path in sorted(by_path))


def _dedupe_inventory(
    items: Iterable[SourceInventoryItem],
) -> tuple[SourceInventoryItem, ...]:
    by_path: dict[str, SourceInventoryItem] = {}
    duplicate_paths: set[str] = set()
    for item in items:
        if item.citation_path in by_path:
            duplicate_paths.add(item.citation_path)
            continue
        by_path[item.citation_path] = item
    if duplicate_paths:
        joined = ", ".join(sorted(duplicate_paths))
        raise ValueError(f"duplicate inventory citation paths: {joined}")
    return tuple(by_path[path] for path in sorted(by_path))
