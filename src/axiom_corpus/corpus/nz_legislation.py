"""New Zealand legislation extraction into source-first corpus artifacts."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from axiom_corpus.converters.nz_pco import (
    NZLabeledParagraph,
    NZLegislation,
    NZLegislationSubtype,
    NZPCOConverter,
    NZProvision,
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
    relative_name: str
    source_name: str


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
    return "/".join(
        [
            "nz",
            nz_document_class(legislation),
            legislation.legislation_type,
            legislation.subtype,
            str(legislation.year),
            _document_number_token(legislation),
            _provision_kind(legislation),
            provision.path_token or _provision_token(provision.label or provision.id),
        ]
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
    parent_path = _parent_citation_path(legislation)
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
        level=1,
        ordinal=_provision_ordinal(provision.label),
        kind=_provision_kind(legislation),
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
        },
    )


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
        legislation = converter.parse_xml(normalized.decode("utf-8"))
        _apply_source_name_metadata(legislation, source_name)
        prepared.append(
            _PreparedLegislation(
                legislation=legislation,
                raw_bytes=normalized,
                relative_name=_source_relative_name(legislation, source_name),
                source_name=source_name,
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
            _document_number_token(legislation),
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


def _document_number_token(legislation: NZLegislation) -> str:
    if legislation.document_number_token:
        token = re.sub(r"[^0-9A-Za-z]+", "-", legislation.document_number_token).strip("-")
        if token:
            return token
    return f"{legislation.number:04d}"


def _provision_body(provision: NZProvision) -> str:
    lines: list[str] = []
    if provision.text:
        lines.append(provision.text)
    lines.extend(_format_labeled_paragraph(paragraph) for paragraph in provision.paragraphs)
    for subprovision in provision.subprovisions:
        sub_body = _provision_body(subprovision)
        if sub_body:
            lines.append(f"{subprovision.label} {sub_body}".strip())
    return "\n".join(line for line in lines if line)


def _format_labeled_paragraph(paragraph: NZLabeledParagraph, prefix: str = "") -> str:
    label = f"{prefix}{paragraph.label}"
    lines = [f"{label} {paragraph.text}".strip()]
    for child in paragraph.children:
        lines.append(_format_labeled_paragraph(child, prefix=label))
    return "\n".join(line for line in lines if line)


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
