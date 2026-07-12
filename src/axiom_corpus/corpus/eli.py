"""Generic European Legislation Identifier (ELI) document ingestion."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlparse, urlsplit
from xml.etree import ElementTree

import requests
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import (
    OFFICIAL_DOCUMENT_USER_AGENT,
    OfficialDocumentExtractReport,
    OfficialDocumentSource,
    _DocumentBlock,
    _inventory_items,
    _provision_records,
)
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem

ELI_ONTOLOGY = "http://data.europa.eu/eli/ontology#"


class EliInForce(StrEnum):
    """Normalized ELI currency state."""

    IN_FORCE = "in-force"
    NOT_IN_FORCE = "not-in-force"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EliManifestation:
    """One XML, HTML, or PDF manifestation in an ELI graph."""

    format: str
    url: str
    legal_value: str | None = None


@dataclass(frozen=True)
class EliActMetadata:
    """The phase-1 metadata extracted from an ELI JSON-LD graph."""

    eli_uri: str
    in_force: EliInForce
    consolidated_by: tuple[str, ...]
    changed_by: tuple[str, ...]
    consolidates: tuple[str, ...]
    titles: tuple[str, ...]
    title_short: tuple[str, ...]
    title_alternative: tuple[str, ...]
    date_document: str | None
    responsibility_of: tuple[str, ...]
    manifestations: tuple[EliManifestation, ...]

    def manifestation(self, format: str) -> EliManifestation | None:
        return next((item for item in self.manifestations if item.format == format), None)


@dataclass(frozen=True)
class LexDaniaSection:
    """One paragraph-level block extracted from LexDania XML."""

    label: str
    heading: str
    body: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _ValidatedEliDocument:
    """Fetched document inputs that passed every phase-A validation."""

    source: EliDocumentSource
    graph_url: str
    graph_bytes: bytes
    metadata: EliActMetadata
    xml_url: str
    xml_bytes: bytes
    sections: tuple[LexDaniaSection, ...]


@dataclass(frozen=True)
class EliDocumentSource:
    """One ELI act declared by an extraction manifest."""

    source_id: str
    eli_uri: str | None
    graph_url: str | None
    xml_url: str | None
    jurisdiction: str
    document_class: str
    citation_path: str
    title: str
    language: str
    source_format: str = "xml"
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> EliDocumentSource:
        eli_uri = _optional_string(row.get("eli_uri"))
        graph_url = _optional_string(row.get("graph_url"))
        xml_url = _optional_string(row.get("xml_url"))
        if not eli_uri and not graph_url:
            raise ValueError("ELI manifest entry requires eli_uri or graph_url")
        source_format = str(row.get("format", row.get("source_format", "xml"))).lower()
        return cls(
            source_id=str(row.get("source_id") or _source_id(eli_uri or graph_url or "eli")),
            eli_uri=eli_uri,
            graph_url=graph_url,
            xml_url=xml_url,
            jurisdiction=str(row["jurisdiction"]),
            document_class=str(row["document_class"]),
            citation_path=str(row["citation_path"]).strip("/"),
            title=str(row["title"]),
            language=str(row["language"]),
            source_format=source_format,
            metadata=dict(row["metadata"]) if isinstance(row.get("metadata"), dict) else None,
        )


EliFetcher = Callable[[str], bytes]


def parse_eli_graph(
    payload: Any,
    *,
    language: str | None = None,
    expected_uri: str | None = None,
) -> EliActMetadata:
    """Parse the relevant resource, expression, and manifestation graph nodes."""
    nodes = _graph_nodes(payload)
    resources = tuple(node for node in nodes if _has_type(node, "LegalResource"))
    resource = next(
        (
            node
            for node in resources
            if expected_uri is None
            or _eli_uris_match(str(node.get("@id", "")).strip(), expected_uri)
        ),
        None,
    )
    if resource is None:
        if expected_uri is not None and resources:
            found_uris = ", ".join(
                repr(str(node.get("@id", "")).strip()) for node in resources
            )
            raise ValueError(
                f"ELI graph has no LegalResource matching requested URI {expected_uri!r}; "
                f"found LegalResource URI(s): {found_uris}"
            )
        raise ValueError("ELI graph has no LegalResource node")
    eli_uri = str(resource.get("@id", "")).strip()
    if not eli_uri:
        raise ValueError("ELI LegalResource has no @id URI")

    expression_ids = set(_values(resource, "is_realized_by"))
    expressions = tuple(
        node
        for node in nodes
        if str(node.get("@id", "")) in expression_ids and _has_type(node, "LegalExpression")
    )
    expression = _select_expression(expressions, language=language)
    embodied_urls = set(_values(expression, "is_embodied_by"))
    manifestations: list[EliManifestation] = []
    for node in nodes:
        url = str(node.get("@id", ""))
        if not url or url not in embodied_urls or not _has_type(node, "Format"):
            continue
        format_name = _manifestation_format(node, url)
        if format_name not in {"xml", "html", "pdf"}:
            continue
        legal_values = _values(node, "legal_value")
        manifestations.append(
            EliManifestation(
                format=format_name,
                url=url,
                legal_value=_fragment(legal_values[0], "LegalValue-") if legal_values else None,
            )
        )

    raw_force = _values(resource, "in_force")
    force_token = _fragment(raw_force[0], "InForce-").lower() if raw_force else ""
    in_force = {
        "inforce": EliInForce.IN_FORCE,
        "notinforce": EliInForce.NOT_IN_FORCE,
    }.get(force_token, EliInForce.UNKNOWN)
    return EliActMetadata(
        eli_uri=eli_uri,
        in_force=in_force,
        consolidated_by=_unique(_values(resource, "consolidated_by")),
        changed_by=_unique(_values(resource, "changed_by")),
        consolidates=_unique(_values(resource, "consolidates")),
        titles=_unique(_values(expression, "title")),
        title_short=_unique(_values(expression, "title_short")),
        title_alternative=_unique(_values(expression, "title_alternative")),
        date_document=_first(_values(resource, "date_document")),
        responsibility_of=_unique(_values(resource, "responsibility_of")),
        manifestations=tuple(sorted(manifestations, key=lambda item: item.format)),
    )


def require_current_eli_act(metadata: EliActMetadata, *, allow_superseded: bool = False) -> None:
    """Refuse a mechanically superseded ELI act unless explicitly allowed."""
    superseded = bool(metadata.consolidated_by) or metadata.in_force is EliInForce.NOT_IN_FORCE
    if not superseded or allow_superseded:
        return
    successor = metadata.consolidated_by[0] if metadata.consolidated_by else "an unspecified act"
    raise ValueError(
        f"ELI act {metadata.eli_uri} is superseded by {successor}; "
        "pass --allow-superseded to ingest it"
    )


def extract_lexdania_sections(xml_bytes: bytes) -> tuple[LexDaniaSection, ...]:
    """Extract one section per LexDania ``Paragraf`` element."""
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid LexDania XML") from exc
    if _local_name(root.tag) != "Dokument" or not any(
        _local_name(node.tag) == "DokumentIndhold" for node in root.iter()
    ):
        raise ValueError("XML is not a LexDania Dokument/DokumentIndhold document")
    parents = {child: parent for parent in root.iter() for child in parent}
    sections: list[LexDaniaSection] = []
    for paragraph in (node for node in root.iter() if _local_name(node.tag) == "Paragraf"):
        number = paragraph.attrib.get("localId", "").strip()
        if not number:
            raise ValueError("LexDania Paragraf is missing its localId number")
        label = "paragraf-" + "-".join(re.findall(r"[0-9]+|[A-Za-zÆØÅæøå]+", number.lower()))
        heading_node = next(
            (child for child in paragraph if _local_name(child.tag) == "Explicatus"), None
        )
        heading = _element_text(heading_node) or f"§ {number}."
        parts = [heading]
        for child in paragraph:
            if _local_name(child.tag) == "Stk":
                text = _element_text(child)
                if text:
                    parts.append(text)
        metadata: dict[str, Any] = {
            "citation_suffix": label,
            "section_label": heading,
            "paragraph_number": number,
            "lexdania_local_id": number,
        }
        ancestor = parents.get(paragraph)
        while ancestor is not None:
            kind = _local_name(ancestor.tag)
            if kind in {"Kapitel", "Afsnit"}:
                prefix = kind.lower()
                local_id = ancestor.attrib.get("localId")
                ancestor_heading = _direct_explicatus(ancestor)
                if local_id:
                    metadata[f"{prefix}_number"] = local_id
                if ancestor_heading:
                    metadata[f"{prefix}_heading"] = ancestor_heading
            ancestor = parents.get(ancestor)
        sections.append(
            LexDaniaSection(
                label=label,
                heading=heading,
                body="\n\n".join(parts),
                metadata=metadata,
            )
        )
    if not sections:
        raise ValueError("LexDania document contains no Paragraf elements")
    return tuple(sections)


def extract_eli_documents(
    store: CorpusArtifactStore,
    *,
    manifest_path: str | Path,
    version: str,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_source_id: str | None = None,
    limit: int | None = None,
    allow_superseded: bool = False,
    fetcher: EliFetcher | None = None,
    progress_stream: TextIO | None = None,
) -> OfficialDocumentExtractReport:
    """Fetch ELI graphs and LexDania XML, then write standard corpus artifacts."""
    rows = yaml.safe_load(Path(manifest_path).read_text())
    if not isinstance(rows, dict) or not isinstance(rows.get("documents"), list):
        raise ValueError("ELI manifest must be a mapping with a documents list")
    sources = tuple(
        EliDocumentSource.from_mapping(row) for row in rows["documents"] if isinstance(row, dict)
    )
    selected = tuple(item for item in sources if only_source_id in {None, item.source_id})
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ValueError("no ELI documents selected")
    scopes = {(item.jurisdiction, item.document_class) for item in selected}
    if len(scopes) != 1:
        raise ValueError("ELI extraction requires one jurisdiction/document_class")
    jurisdiction, document_class = next(iter(scopes))
    run_id = version
    if only_source_id:
        run_id += f"-{safe_segment(only_source_id)}"
    if limit is not None:
        run_id += f"-limit-{limit}"
    get = fetcher or _requests_fetcher
    # Phase A: fetch and validate the complete selection without touching the store.
    validated: list[_ValidatedEliDocument] = []
    for item in selected:
        if progress_stream:
            print(f"extracting {item.source_id}", file=progress_stream)
        if item.source_format != "xml":
            raise ValueError(
                "ELI phase 1 extracts XML only; use extract-official-documents for PDF fallback"
            )
        graph_url = item.graph_url or f"{item.eli_uri}.json"
        graph_bytes = get(graph_url)
        metadata = parse_eli_graph(
            json.loads(graph_bytes),
            language=item.language,
            expected_uri=item.eli_uri,
        )
        if item.eli_uri is not None and not _eli_uris_match(metadata.eli_uri, item.eli_uri):
            raise ValueError(
                f"ELI graph selected URI {metadata.eli_uri!r}, "
                f"not requested URI {item.eli_uri!r}"
            )
        require_current_eli_act(metadata, allow_superseded=allow_superseded)
        xml_manifestation = metadata.manifestation("xml")
        xml_url = item.xml_url or (xml_manifestation.url if xml_manifestation else None)
        if not xml_url:
            raise ValueError(
                f"ELI graph for {metadata.eli_uri} has no XML manifestation; "
                "use extract-official-documents for PDF fallback"
            )
        xml_bytes = get(xml_url)
        sections = extract_lexdania_sections(xml_bytes)
        validated.append(
            _ValidatedEliDocument(
                source=item,
                graph_url=graph_url,
                graph_bytes=graph_bytes,
                metadata=metadata,
                xml_url=xml_url,
                xml_bytes=xml_bytes,
                sections=sections,
            )
        )

    # Phase B: every document passed the currency and LexDania gates, so writes may begin.
    inventory: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    source_paths: list[Path] = []
    block_count = 0
    for document in validated:
        item = document.source
        metadata = document.metadata
        relative_base = f"eli/{safe_segment(item.source_id)}"
        graph_path = store.source_path(
            jurisdiction, document_class, run_id, f"{relative_base}.jsonld"
        )
        xml_path = store.source_path(jurisdiction, document_class, run_id, f"{relative_base}.xml")
        store.write_bytes(graph_path, document.graph_bytes)
        xml_sha = store.write_bytes(xml_path, document.xml_bytes)
        source_paths.extend((graph_path, xml_path))
        source_key = f"sources/{jurisdiction}/{document_class}/{run_id}/{relative_base}.xml"
        blocks = tuple(
            _DocumentBlock(
                kind="section",
                ordinal=index,
                heading=section.heading,
                body=section.body,
                metadata=section.metadata,
            )
            for index, section in enumerate(document.sections, 1)
        )
        block_count += len(blocks)
        diligence = {
            "eli_uri": metadata.eli_uri,
            "eli_in_force": metadata.in_force.value,
            "eli_changed_by": list(metadata.changed_by),
            "eli_consolidated_by": list(metadata.consolidated_by),
            "eli_consolidates": list(metadata.consolidates),
            "eli_titles": list(metadata.titles),
            "eli_title_short": list(metadata.title_short),
            "eli_title_alternative": list(metadata.title_alternative),
            "eli_date_document": metadata.date_document,
            "eli_responsibility_of": list(metadata.responsibility_of),
            "eli_graph_url": document.graph_url,
        }
        source = OfficialDocumentSource(
            source_id=item.source_id,
            jurisdiction=item.jurisdiction,
            document_class=item.document_class,
            title=item.title,
            source_url=metadata.eli_uri,
            citation_path=item.citation_path,
            source_format="xml",
            language=item.language,
            metadata={**(item.metadata or {}), **diligence},
        )
        source_as_of_text = source_as_of or version
        expression_date_text = _date_text(
            expression_date, metadata.date_document, source_as_of_text
        )
        inventory.extend(
            _inventory_items(
                source,
                blocks=blocks,
                source_key=source_key,
                source_format="xml",
                source_sha=xml_sha,
                content_type="application/xml",
                final_url=document.xml_url,
            )
        )
        records.extend(
            _provision_records(
                source,
                blocks=blocks,
                version=run_id,
                source_key=source_key,
                source_format="xml",
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                content_type="application/xml",
                final_url=document.xml_url,
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
        document_count=len(selected),
        block_count=block_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


def _requests_fetcher(url: str) -> bytes:
    response = requests.get(url, headers={"User-Agent": OFFICIAL_DOCUMENT_USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.content


def _select_expression(
    expressions: Sequence[Mapping[str, Any]], *, language: str | None
) -> Mapping[str, Any]:
    if not expressions:
        raise ValueError("ELI LegalResource has no referenced LegalExpression node")
    if language:
        language_tokens = {language.lower(), {"da": "dan"}.get(language.lower(), language.lower())}
        matches = [
            expression
            for expression in expressions
            if language_tokens
            & {
                value.rstrip("/").rsplit("/", 1)[-1].lower()
                for value in (
                    *(_values(expression, "language")),
                    str(expression.get("@id", "")),
                )
            }
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"ELI graph has multiple LegalExpression nodes for language {language}"
            )
        available_languages = sorted(
            {
                value.rstrip("/").rsplit("/", 1)[-1]
                for expression in expressions
                for value in _values(expression, "language")
            }
        )
        available = ", ".join(available_languages) if available_languages else "none"
        raise ValueError(
            f"ELI graph has no LegalExpression for requested language {language!r}; "
            f"available languages: {available}"
        )
    if len(expressions) == 1:
        return expressions[0]
    raise ValueError("ELI graph has no unique LegalExpression")


def _graph_nodes(payload: Any) -> tuple[Mapping[str, Any], ...]:
    value = payload.get("@graph", payload) if isinstance(payload, dict) else payload
    if not isinstance(value, list):
        raise ValueError("ELI JSON-LD must be a node list or an @graph object")
    return tuple(node for node in value if isinstance(node, dict))


def _values(node: Mapping[str, Any], key: str) -> list[str]:
    raw = node.get(ELI_ONTOLOGY + key, node.get(f"eli:{key}", []))
    raw_items = raw if isinstance(raw, list) else [raw]
    values: list[str] = []
    for item in raw_items:
        value = item.get("@id", item.get("@value")) if isinstance(item, dict) else item
        if value is not None and str(value).strip():
            values.append(str(value).strip())
    return values


def _has_type(node: Mapping[str, Any], suffix: str) -> bool:
    raw = node.get("@type", [])
    return any(
        str(value).endswith("#" + suffix) for value in (raw if isinstance(raw, list) else [raw])
    )


def _eli_uris_match(actual: str, expected: str) -> bool:
    """Compare ELI URIs allowing only HTTP(S) and trailing-slash differences."""

    def normalized(uri: str) -> tuple[str, str, str, str, str]:
        parsed = urlsplit(uri.strip())
        scheme = "http(s)" if parsed.scheme.lower() in {"http", "https"} else parsed.scheme
        return scheme, parsed.netloc, parsed.path.rstrip("/"), parsed.query, parsed.fragment

    return normalized(actual) == normalized(expected)


def _manifestation_format(node: Mapping[str, Any], url: str) -> str:
    formats = _values(node, "format") + _values(node, "media_type")
    for candidate in formats:
        lowered = candidate.lower()
        if "xml" in lowered:
            return "xml"
        if "html" in lowered:
            return "html"
        if "pdf" in lowered:
            return "pdf"
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].lower()


def _fragment(value: str, prefix: str) -> str:
    token = value.rsplit("#", 1)[-1]
    return token.removeprefix(prefix)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _first(values: Sequence[str]) -> str | None:
    return values[0] if values else None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _direct_explicatus(element: ElementTree.Element) -> str:
    return next(
        (_element_text(child) for child in element if _local_name(child.tag) == "Explicatus"),
        "",
    )


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None and str(value).strip() else None


def _source_id(uri: str) -> str:
    return "-".join(part for part in urlparse(uri).path.split("/") if part)[-80:]


def _date_text(value: date | str | None, graph_date: str | None, fallback: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if value:
        return str(value)
    if graph_date:
        match = re.match(r"(\d{2})-(\d{2})-(\d{4})", graph_date)
        if match:
            return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return fallback
