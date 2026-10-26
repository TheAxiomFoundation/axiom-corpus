"""Armenian ARLIS legal-act extraction.

ARLIS publishes Armenian statutes and regulations as legacy Word-export HTML.  This
adapter is deliberately local-file first: a manifest binds every input to an
official ARLIS URL, immutable SHA-256, explicit expression dates, and the
expected number of article and appendix headers before any corpus artifact is
written.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Self, cast
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup
from bs4.element import NavigableString, PageElement, Tag

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

ARMENIA_ARLIS_SOURCE_FORMAT = "arlis.am-consolidated-html"
ARMENIA_ARLIS_JURISDICTION = "am"
ARMENIA_ARLIS_DOCUMENT_CLASS = DocumentClass.STATUTE.value
ARMENIA_ARLIS_LANGUAGE = "hy"
_DOCUMENT_CLASS_ACT_TYPES = {
    DocumentClass.STATUTE.value: frozenset({"Օրենք", "Օրենսգիրք"}),
    DocumentClass.REGULATION.value: frozenset({"Որոշում"}),
}
ARMENIA_ARLIS_DOCUMENT_CLASSES = frozenset(_DOCUMENT_CLASS_ACT_TYPES)
_REGULATION_ENACTMENT_BODY = "ՀՀ կառավարություն"

_ASCII_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
_ARTICLE_MARKER_RE = re.compile(
    r"^\s*(?:⚖\s*)?Հոդված\s*(?P<label>\d+(?:[.․]\d+)?)\s*[.․]?\s*$",
)
_ARTICLE_WORD_RE = re.compile(r"Հոդված(?:\s|$)")
_STRUCTURE_PREFIX_RE = re.compile(
    r"^\s*(?P<kind>Մ\s*Ա\s*Ս|Բ\s*Ա\s*Ժ\s*Ի\s*Ն|"
    r"Ե\s*Ն\s*Թ\s*Ա\s*Բ\s*Ա\s*Ժ\s*Ի\s*Ն|Գ\s*Լ\s*Ո\s*Ւ\s*Խ)"
    r"\s*(?P<label>\d+(?:[.․]\d+)?)(?P<suffix>.*)$",
    re.IGNORECASE,
)
_NUMBERED_APPENDIX_RE = re.compile(
    r"^\s*Հավելված(?:\s+(?:N\s*)?(?P<label>\d+(?:[.․]\d+)?))?\s*$",
    re.IGNORECASE,
)
_AUTHORITY_APPENDIX_RE = re.compile(
    r"^\s*Հավելված(?:\s+N\s*(?P<label>\d+(?:[.․]\d+)?))?\s+(?:"
    r"ՀՀ\s+կառավարության\b.*\s+որոշման|"
    r"«[^»]+»\s+Հայաստանի\s+Հանրապետության\s+օրենքի"
    r")\s*$",
    re.IGNORECASE,
)
_APPENDIX_WORD_RE = re.compile(r"^\s*Հավելված(?:\s|$)", re.IGNORECASE)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VALIDITY_PERIOD_PATTERN = (
    r"\((?P<start_day>\d{2})\.(?P<start_month>\d{2})\."
    r"(?P<start_year>\d{4})\s*-\s*(?:մինչ օրս|"
    r"(?P<end_day>\d{2})\.(?P<end_month>\d{2})\.(?P<end_year>\d{4}))\)"
)
_VALIDITY_PERIOD_RES = {
    "incorporation": re.compile(rf"^(?:Պաշտոնական\s+)?Ինկորպորացիա\s*{_VALIDITY_PERIOD_PATTERN}$"),
    "main_act": re.compile(rf"^Հիմնական ակտ\s*{_VALIDITY_PERIOD_PATTERN}$"),
}
_DOTTED_DATE_RE = re.compile(r"^(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})$")
_SIGNATURE_ROLES = frozenset(
    role.casefold()
    for role in (
        "ՀայաստանիՀանրապետությանՆախագահ",
        "Հանրապետությաննախագահ",
        "ՀայաստանիՀանրապետությանվարչապետ",
        "ՀՀվարչապետ",
        "ՀայաստանիՀանրապետությանփոխվարչապետ",
        "ՀՀփոխվարչապետ",
        "ՀայաստանիՀանրապետությանվարչապետիաշխատակազմիղեկավար",
        "ՀայաստանիՀանրապետությանկառավարությանաշխատակազմիղեկավար",
    )
)
_SIGNATURE_NAME_RE = re.compile(r"^[Ա-Ֆ]\.\s*[Ա-Ֆ][Ա-Ֆա-ֆ]+(?:[- ][Ա-Ֆ][Ա-Ֆա-ֆ]+)*$")
_STRUCTURE_KIND = {
    "մաս": "part",
    "բաժին": "section",
    "ենթաբաժին": "subsection",
    "գլուխ": "chapter",
}
_STRUCTURE_LEVEL = {
    "part": 1,
    "section": 2,
    "subsection": 3,
    "chapter": 4,
}


@dataclass(frozen=True)
class ArmeniaARLISSource:
    """One hash-pinned official ARLIS legal act."""

    source_id: str
    document_class: str
    act_id: str
    base_act_id: str | None
    official_number: str
    adopted: str
    title: str
    source_url: str
    source_file: str
    sha256: str
    source_as_of: str
    expression_date: str
    expression_end_date: str | None
    language: str
    expected_article_count: int
    expected_appendix_count: int | None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Self:
        """Validate and construct one manifest source."""
        jurisdiction = str(data.get("jurisdiction", ARMENIA_ARLIS_JURISDICTION))
        document_class = str(data.get("document_class", ARMENIA_ARLIS_DOCUMENT_CLASS))
        if jurisdiction != ARMENIA_ARLIS_JURISDICTION:
            raise ValueError(f"ARLIS source jurisdiction must be am, got {jurisdiction!r}")
        if document_class not in ARMENIA_ARLIS_DOCUMENT_CLASSES:
            raise ValueError(
                f"ARLIS source document_class must be statute or regulation, got {document_class!r}"
            )

        source_id = _required_text(data, "source_id")
        if not _SOURCE_ID_RE.fullmatch(source_id):
            raise ValueError(f"invalid ARLIS source_id: {source_id!r}")
        act_id = _required_text(data, "act_id")
        if not act_id.isdigit():
            raise ValueError(f"ARLIS act_id must contain only digits: {act_id!r}")
        base_act_id = _required_text(data, "base_act_id") if "base_act_id" in data else None
        if base_act_id is not None and not base_act_id.isdigit():
            raise ValueError(f"ARLIS base_act_id must contain only digits: {base_act_id!r}")

        language_value = data.get("language")
        if isinstance(language_value, bool):
            raise ValueError("ARLIS language must be the string 'hy', not a YAML boolean")
        language = _required_text(data, "language")
        if language != ARMENIA_ARLIS_LANGUAGE:
            raise ValueError(f"ARLIS source language must be hy, got {language!r}")

        source_file = _required_text(data, "source_file")
        if Path(source_file).name != source_file or Path(source_file).is_absolute():
            raise ValueError(f"ARLIS source_file must be a plain file name: {source_file!r}")
        if not source_file.lower().endswith((".html", ".htm")):
            raise ValueError(f"ARLIS source_file must be HTML: {source_file!r}")

        source_url = _required_text(data, "source_url")
        parsed_url = urlparse(source_url)
        allowed_paths = {
            f"/hy/acts/{act_id}",
            f"/hy/acts/{act_id}/latest",
        }
        if (
            parsed_url.scheme != "https"
            or parsed_url.netloc != "www.arlis.am"
            or parsed_url.path not in allowed_paths
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError(
                "ARLIS source_url must be an official Armenian act URL "
                f"for act {act_id}: {source_url!r}"
            )

        sha256 = _required_text(data, "sha256")
        if not _SHA256_RE.fullmatch(sha256):
            raise ValueError(f"invalid lowercase SHA-256 for {source_id}: {sha256!r}")

        expected_article_count = data.get("expected_article_count")
        if (
            isinstance(expected_article_count, bool)
            or not isinstance(expected_article_count, int)
            or expected_article_count < 0
        ):
            raise ValueError(
                f"ARLIS source {source_id} requires a non-negative expected_article_count"
            )
        expected_appendix_count = data.get("expected_appendix_count")
        if expected_appendix_count is None and document_class == DocumentClass.REGULATION.value:
            raise ValueError(
                f"ARLIS regulation {source_id} requires a non-negative expected_appendix_count"
            )
        if expected_appendix_count is not None and (
            isinstance(expected_appendix_count, bool)
            or not isinstance(expected_appendix_count, int)
            or expected_appendix_count < 0
        ):
            raise ValueError(
                f"ARLIS source {source_id} requires a non-negative expected_appendix_count"
            )

        expression_date = _required_iso_date(data, "expression_date")
        expression_end_date = _optional_iso_date(data, "expression_end_date")
        if expression_end_date is not None and expression_end_date <= expression_date:
            raise ValueError(
                f"ARLIS expression_end_date must follow expression_date for {source_id}"
            )
        if expression_end_date is not None and parsed_url.path.endswith("/latest"):
            raise ValueError(
                "finite ARLIS historical expressions must use the exact act URL, "
                f"not /latest: {source_url!r}"
            )

        return cls(
            source_id=source_id,
            document_class=document_class,
            act_id=act_id,
            base_act_id=base_act_id,
            official_number=_required_text(data, "official_number"),
            adopted=_required_iso_date(data, "adopted"),
            title=_required_text(data, "title"),
            source_url=source_url,
            source_file=source_file,
            sha256=sha256,
            source_as_of=_required_iso_date(data, "source_as_of"),
            expression_date=expression_date,
            expression_end_date=expression_end_date,
            language=language,
            expected_article_count=expected_article_count,
            expected_appendix_count=expected_appendix_count,
        )

    @property
    def document_citation_path(self) -> str:
        return f"am/{self.document_class}/act-{self.act_id}"


@dataclass(frozen=True)
class ArmeniaARLISManifest:
    """Manifest binding local snapshots to official ARLIS identities."""

    documents: tuple[ArmeniaARLISSource, ...]

    @classmethod
    def load(cls, path: str | Path) -> Self:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("ARLIS manifest must be a YAML mapping")
        rows = data.get("documents")
        if not isinstance(rows, list) or not rows:
            raise ValueError("ARLIS manifest must contain a non-empty documents list")
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("every ARLIS manifest document must be a mapping")
        manifest = cls(
            documents=tuple(
                ArmeniaARLISSource.from_mapping(cast(dict[str, Any], row)) for row in rows
            )
        )
        manifest.require_unique_sources()
        manifest.require_single_document_class()
        return manifest

    def require_unique_sources(self) -> None:
        for field_name in ("source_id", "act_id", "source_file"):
            values = [str(getattr(source, field_name)) for source in self.documents]
            duplicates = sorted(value for value in set(values) if values.count(value) > 1)
            if duplicates:
                raise ValueError(f"duplicate ARLIS {field_name}: {', '.join(duplicates)}")

    def require_single_document_class(self) -> None:
        """Require one output scope per extraction manifest."""
        document_classes = sorted({source.document_class for source in self.documents})
        if len(document_classes) != 1:
            raise ValueError(
                f"ARLIS manifest must contain exactly one document_class, got {document_classes}"
            )

    @property
    def document_class(self) -> str:
        self.require_single_document_class()
        return self.documents[0].document_class


@dataclass(frozen=True)
class ArmeniaARLISProvision:
    """One document, hierarchy, appendix, or article parsed from ARLIS."""

    citation_path: str
    parent_citation_path: str | None
    kind: str
    label: str
    heading: str | None
    body: str | None
    level: int
    ordinal: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ArmeniaARLISDocumentExtractReport:
    """Extraction result for one ARLIS act."""

    source_id: str
    act_id: str
    article_count: int
    structural_count: int
    provisions_written: int
    source_path: Path
    sha256: str


@dataclass(frozen=True)
class ArmeniaARLISExtractReport:
    """Artifact report for one Armenian ARLIS extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    document_count: int
    article_count: int
    structural_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]
    document_reports: tuple[ArmeniaARLISDocumentExtractReport, ...]


@dataclass(frozen=True)
class _ArticleHeader:
    label: str
    raw_marker: str
    heading: str | None
    inline_body: str | None
    court_decision_urls: tuple[str, ...]


@dataclass
class _PendingProvision:
    citation_path: str
    parent_citation_path: str
    kind: str
    label: str
    raw_marker: str
    level: int
    ordinal: int
    blocks: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _PreparedSource:
    source: ArmeniaARLISSource
    content: bytes
    provisions: tuple[ArmeniaARLISProvision, ...]
    article_count: int
    structural_count: int


def extract_armenia_arlis(
    store: CorpusArtifactStore,
    *,
    version: str,
    manifest_path: str | Path,
    source_dir: str | Path,
) -> ArmeniaARLISExtractReport:
    """Verify and extract hash-pinned Armenian ARLIS legal acts.

    All manifest rows and all input hashes are validated, and every source is
    parsed to its expected article count, before the first artifact is written.
    This avoids leaving a plausible-looking partial scope when a later source
    has drifted or exposes unrecognized markup.
    """
    if not str(version).strip():
        raise ValueError("ARLIS extraction version must not be empty")
    manifest = ArmeniaARLISManifest.load(manifest_path)
    document_class = manifest.document_class
    source_root = Path(source_dir).resolve()
    if not source_root.is_dir():
        raise ValueError(f"ARLIS source directory does not exist: {source_root}")

    prepared: list[_PreparedSource] = []
    for source in manifest.documents:
        source_path = (source_root / source.source_file).resolve()
        try:
            source_path.relative_to(source_root)
        except ValueError as exc:
            raise ValueError(
                f"ARLIS source path escapes source directory: {source.source_file!r}"
            ) from exc
        if not source_path.is_file():
            raise ValueError(f"ARLIS source file does not exist: {source_path}")
        content = source_path.read_bytes()
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != source.sha256:
            raise ValueError(
                f"ARLIS SHA-256 mismatch for {source.source_id}: "
                f"expected {source.sha256}, got {actual_sha256}"
            )
        provisions = parse_armenia_arlis_html(content, source=source)
        article_count = sum(item.kind == "article" for item in provisions)
        structural_count = sum(item.kind not in {"document", "article"} for item in provisions)
        if article_count != source.expected_article_count:
            raise ValueError(
                f"ARLIS article count mismatch for {source.source_id}: "
                f"expected {source.expected_article_count}, got {article_count}"
            )
        appendix_count = sum(item.kind == "appendix" for item in provisions)
        if (
            source.expected_appendix_count is not None
            and appendix_count != source.expected_appendix_count
        ):
            raise ValueError(
                f"ARLIS appendix count mismatch for {source.source_id}: "
                f"expected {source.expected_appendix_count}, got {appendix_count}"
            )
        prepared.append(
            _PreparedSource(
                source=source,
                content=content,
                provisions=provisions,
                article_count=article_count,
                structural_count=structural_count,
            )
        )

    records: list[ProvisionRecord] = []
    inventory: list[SourceInventoryItem] = []
    source_paths: list[Path] = []
    document_reports: list[ArmeniaARLISDocumentExtractReport] = []
    for item in prepared:
        source = item.source
        relative_name = f"arlis/{source.source_file}"
        artifact_path = store.source_path(
            ARMENIA_ARLIS_JURISDICTION,
            document_class,
            version,
            relative_name,
        )
        written_sha256 = store.write_bytes(artifact_path, item.content)
        if written_sha256 != source.sha256:
            raise RuntimeError(
                f"written ARLIS source hash changed for {source.source_id}: {written_sha256}"
            )
        source_paths.append(artifact_path)
        source_key = f"sources/am/{document_class}/{version}/{relative_name}"
        document_id = deterministic_provision_id(source.document_citation_path, version)
        for provision in item.provisions:
            metadata = {
                **_source_metadata(source),
                **provision.metadata,
            }
            inventory.append(
                SourceInventoryItem(
                    citation_path=provision.citation_path,
                    source_url=source.source_url,
                    source_path=source_key,
                    source_format=ARMENIA_ARLIS_SOURCE_FORMAT,
                    sha256=source.sha256,
                    metadata=metadata,
                )
            )
            records.append(
                ProvisionRecord(
                    id=deterministic_provision_id(provision.citation_path, version),
                    jurisdiction=ARMENIA_ARLIS_JURISDICTION,
                    document_class=document_class,
                    citation_path=provision.citation_path,
                    body=provision.body,
                    heading=provision.heading,
                    citation_label=_citation_label(source, provision),
                    version=version,
                    source_url=source.source_url,
                    source_path=source_key,
                    source_id=f"arlis.am:act:{source.act_id}",
                    source_format=ARMENIA_ARLIS_SOURCE_FORMAT,
                    source_document_id=document_id,
                    source_as_of=source.source_as_of,
                    expression_date=source.expression_date,
                    parent_citation_path=provision.parent_citation_path,
                    parent_id=(
                        deterministic_provision_id(
                            provision.parent_citation_path,
                            version,
                        )
                        if provision.parent_citation_path
                        else None
                    ),
                    level=provision.level,
                    ordinal=provision.ordinal,
                    kind=provision.kind,
                    language=source.language,
                    legal_identifier=_citation_label(source, provision),
                    identifiers={
                        "arlis.am:act_id": source.act_id,
                        "arlis.am:official_number": source.official_number,
                        "arlis.am:source_id": source.source_id,
                        "arlis.am:expression_start": source.expression_date,
                        f"arlis.am:{provision.kind}": provision.label,
                        **(
                            {"arlis.am:base_act_id": source.base_act_id}
                            if source.base_act_id is not None
                            else {}
                        ),
                        **(
                            {"arlis.am:expression_end_exclusive": source.expression_end_date}
                            if source.expression_end_date is not None
                            else {}
                        ),
                    },
                    metadata=metadata,
                )
            )
        document_reports.append(
            ArmeniaARLISDocumentExtractReport(
                source_id=source.source_id,
                act_id=source.act_id,
                article_count=item.article_count,
                structural_count=item.structural_count,
                provisions_written=len(item.provisions),
                source_path=artifact_path,
                sha256=written_sha256,
            )
        )

    _require_unique_citations(records)
    inventory_path = store.inventory_path(
        ARMENIA_ARLIS_JURISDICTION,
        document_class,
        version,
    )
    provisions_path = store.provisions_path(
        ARMENIA_ARLIS_JURISDICTION,
        document_class,
        version,
    )
    coverage_path = store.coverage_path(
        ARMENIA_ARLIS_JURISDICTION,
        document_class,
        version,
    )
    store.write_inventory(inventory_path, inventory)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction=ARMENIA_ARLIS_JURISDICTION,
        document_class=document_class,
        version=version,
    )
    if not coverage.complete:
        raise RuntimeError("ARLIS extraction produced incomplete provision coverage")
    store.write_json(coverage_path, coverage.to_mapping())

    return ArmeniaARLISExtractReport(
        jurisdiction=ARMENIA_ARLIS_JURISDICTION,
        document_class=document_class,
        version=version,
        document_count=len(document_reports),
        article_count=sum(report.article_count for report in document_reports),
        structural_count=sum(report.structural_count for report in document_reports),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        document_reports=tuple(document_reports),
    )


def parse_armenia_arlis_html(
    html: str | bytes,
    *,
    source: ArmeniaARLISSource,
) -> tuple[ArmeniaARLISProvision, ...]:
    """Parse one official ARLIS consolidation without dropping legal blocks."""
    soup = BeautifulSoup(html, "lxml")
    roots = soup.select("#act_body .act-block__section")
    if len(roots) != 1:
        raise ValueError(
            f"ARLIS source {source.source_id} must contain exactly one "
            f"#act_body .act-block__section, got {len(roots)}"
        )
    root = roots[0]
    validity_kind = _require_expression_date(soup, source)
    _require_source_identity(soup, source, validity_kind=validity_kind)
    candidate_headers: dict[int, _ArticleHeader] = {}
    for table in root.find_all("table"):
        header = _article_header(table, source_url=source.source_url)
        if header is not None:
            candidate_headers[id(table)] = header
    for block in root.find_all(recursive=False):
        if block.name == "table" or block.find("table") is not None:
            continue
        header = _inline_article_header(block, source_url=source.source_url)
        if header is not None:
            candidate_headers[id(block)] = header
    if not candidate_headers and source.expected_article_count > 0:
        raise ValueError(f"ARLIS source {source.source_id} contains no article headers")
    _reject_unbound_article_markers(root, candidate_headers, source.source_id)
    _reject_unbound_appendix_markers(root, source.source_id)

    document_path = source.document_citation_path
    parsed: list[ArmeniaARLISProvision] = []
    document_blocks: list[str] = []
    contexts: dict[str, tuple[str, int]] = {}
    pending: _PendingProvision | None = None
    active_article: _PendingProvision | None = None
    article_ordinal = 0
    structural_ordinal = 0
    appendix_ordinal = 0
    encountered_headers: set[int] = set()

    def flush_pending() -> None:
        nonlocal pending
        if pending is None:
            return
        heading = _structural_heading(pending.blocks)
        body = _joined_body(pending.blocks)
        parsed.append(
            ArmeniaARLISProvision(
                citation_path=pending.citation_path,
                parent_citation_path=pending.parent_citation_path,
                kind=pending.kind,
                label=pending.label,
                heading=heading,
                body=body,
                level=pending.level,
                ordinal=pending.ordinal,
                metadata={
                    **pending.metadata,
                    "raw_marker": pending.raw_marker,
                },
            )
        )
        pending = None

    def flush_article() -> None:
        nonlocal active_article
        if active_article is None:
            return
        parsed.append(
            ArmeniaARLISProvision(
                citation_path=active_article.citation_path,
                parent_citation_path=active_article.parent_citation_path,
                kind="article",
                label=active_article.label,
                heading=cast(str, active_article.metadata["article_heading"]),
                body=_joined_body(active_article.blocks),
                level=active_article.level,
                ordinal=active_article.ordinal,
                metadata={
                    key: value
                    for key, value in active_article.metadata.items()
                    if key != "article_heading"
                },
            )
        )
        active_article = None

    nodes: list[Tag | NavigableString] = []
    for node in root.children:
        if isinstance(node, Tag) or (isinstance(node, NavigableString) and str(node).strip()):
            nodes.append(node)

    for node in nodes:
        if isinstance(node, NavigableString):
            text = _render_text(str(node))
            if active_article is not None:
                active_article.blocks.append(text)
            elif pending is not None:
                pending.blocks.append(text)
            else:
                document_blocks.append(text)
            continue

        headers = _headers_in_block(node, candidate_headers)
        if len(headers) > 1:
            raise ValueError(
                f"ARLIS source {source.source_id} has multiple article headers "
                "inside one top-level block"
            )
        if headers:
            header_node, header = headers[0]
            _require_empty_header_wrapper(node, header_node, source.source_id)
            encountered_headers.add(id(header_node))
            flush_article()
            flush_pending()
            article_ordinal += 1
            parent_path, parent_level = _deepest_context(contexts, document_path)
            citation_path = f"{document_path}/article-{header.label}"
            active_article = _PendingProvision(
                citation_path=citation_path,
                parent_citation_path=parent_path,
                kind="article",
                label=header.label,
                raw_marker=header.raw_marker,
                level=parent_level + 1,
                ordinal=article_ordinal,
                blocks=[header.inline_body] if header.inline_body else [],
                metadata={
                    "article_heading": header.heading,
                    "raw_article_marker": header.raw_marker,
                    "court_decision_urls": list(header.court_decision_urls),
                    "hierarchy": _hierarchy_metadata(contexts),
                },
            )
            continue

        structure = _structure_marker(node)
        if structure is not None:
            flush_article()
            flush_pending()
            kind, label, raw_marker, inline_body = structure
            structural_ordinal += 1
            parent_path, parent_level = _structure_parent(
                kind,
                contexts,
                document_path,
            )
            citation_path = f"{parent_path}/{kind}-{label}"
            contexts[kind] = (citation_path, parent_level + 1)
            _clear_deeper_contexts(kind, contexts)
            pending = _PendingProvision(
                citation_path=citation_path,
                parent_citation_path=parent_path,
                kind=kind,
                label=label,
                raw_marker=raw_marker,
                level=parent_level + 1,
                ordinal=structural_ordinal,
                blocks=[inline_body] if inline_body else [],
                metadata={"hierarchy": _hierarchy_metadata(contexts)},
            )
            continue

        appendix_marker = _appendix_marker(node)
        if appendix_marker is not None:
            flush_article()
            flush_pending()
            appendix_ordinal += 1
            structural_ordinal += 1
            appendix_label, raw_marker = appendix_marker
            appendix_label = appendix_label or str(appendix_ordinal)
            pending = _PendingProvision(
                citation_path=f"{document_path}/appendix-{appendix_label}",
                parent_citation_path=document_path,
                kind="appendix",
                label=appendix_label,
                raw_marker=raw_marker,
                level=1,
                ordinal=structural_ordinal,
                blocks=[],
                metadata={"hierarchy": []},
            )
            continue

        rendered = _render_block(node)
        if _is_signature_block(node):
            flush_article()
            flush_pending()
            if rendered:
                document_blocks.append(rendered)
            continue
        if active_article is not None:
            active_article.blocks.append(rendered)
        elif pending is not None:
            pending.blocks.append(rendered)
        else:
            document_blocks.append(rendered)

    flush_article()
    flush_pending()
    if encountered_headers != set(candidate_headers):
        missing = len(set(candidate_headers) - encountered_headers)
        raise ValueError(
            f"ARLIS source {source.source_id} left {missing} article header(s) unbound"
        )

    article_count = sum(item.kind == "article" for item in parsed)
    document_body = _joined_body(document_blocks)
    if document_body is None and not any(item.heading or item.body for item in parsed):
        raise ValueError(f"ARLIS source {source.source_id} contains no extractable legal content")
    document = ArmeniaARLISProvision(
        citation_path=document_path,
        parent_citation_path=None,
        kind="document",
        label=source.official_number,
        heading=source.title,
        body=document_body,
        level=0,
        ordinal=0,
        metadata={
            "article_count": article_count,
            "structural_count": sum(item.kind != "article" for item in parsed),
        },
    )
    provisions = (document, *parsed)
    _require_unique_parsed_citations(provisions, source.source_id)
    return provisions


def _required_text(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if isinstance(value, bool) or value is None:
        raise ValueError(f"ARLIS manifest field {field!r} must be a string")
    text = str(value).strip()
    if not text:
        raise ValueError(f"ARLIS manifest field {field!r} must not be empty")
    return text


def _required_iso_date(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise ValueError(f"ARLIS manifest field {field!r} must be an explicitly quoted ISO date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid ARLIS {field}: {value!r}") from exc


def _optional_iso_date(data: Mapping[str, Any], field: str) -> str | None:
    if field not in data:
        return None
    return _required_iso_date(data, field)


def _require_source_identity(
    soup: BeautifulSoup,
    source: ArmeniaARLISSource,
    *,
    validity_kind: str,
) -> None:
    base_links = soup.select("a.act-changes-primary[href]")
    if validity_kind == "main_act":
        if source.base_act_id is not None:
            raise ValueError(f"ARLIS main act {source.source_id} must not declare base_act_id")
        if len(base_links) != 1:
            raise ValueError(
                f"ARLIS main act {source.source_id} must contain exactly one primary-act "
                f"link, got {len(base_links)}"
            )
        embedded_base_href = base_links[0].get("href")
        expected_base_href = f"/hy/acts/{source.act_id}"
        if embedded_base_href != expected_base_href:
            raise ValueError(
                f"ARLIS act_id mismatch for main act {source.source_id}: manifest has "
                f"{source.act_id!r}, source metadata has primary link "
                f"{embedded_base_href!r}"
            )
    elif validity_kind == "incorporation":
        if source.document_class == DocumentClass.REGULATION.value and source.base_act_id is None:
            raise ValueError(
                f"ARLIS regulation incorporation {source.source_id} requires base_act_id"
            )
        if source.base_act_id is not None:
            if len(base_links) != 1:
                raise ValueError(
                    f"ARLIS source {source.source_id} must contain exactly one primary-act "
                    f"link, got {len(base_links)}"
                )
            embedded_base_href = base_links[0].get("href")
            expected_base_href = f"/hy/acts/{source.base_act_id}"
            if embedded_base_href != expected_base_href:
                raise ValueError(
                    f"ARLIS base_act_id mismatch for {source.source_id}: manifest has "
                    f"{source.base_act_id!r}, source metadata has primary link "
                    f"{embedded_base_href!r}"
                )

    current_rows = soup.select(".act-changes-history__couple.current-act")
    if validity_kind == "main_act":
        if current_rows:
            raise ValueError(
                f"ARLIS main act {source.source_id} must not contain a current-act "
                f"history row, got {len(current_rows)}"
            )
    elif validity_kind == "incorporation":
        _require_incorporation_self_identity(current_rows, source)
    else:  # pragma: no cover - internal guard
        raise ValueError(f"unsupported ARLIS validity kind: {validity_kind!r}")

    titles = soup.find_all("title")
    if len(titles) != 1:
        raise ValueError(
            f"ARLIS source {source.source_id} must contain exactly one HTML title, "
            f"got {len(titles)}"
        )
    embedded_title = _inline_text(titles[0])
    if embedded_title != source.title:
        raise ValueError(
            f"ARLIS title mismatch for {source.source_id}: manifest has "
            f"{source.title!r}, source metadata has {embedded_title!r}"
        )

    act_info = _act_info_values(soup, source.source_id)
    embedded_act_type = _required_act_info_value(act_info, "Տիպ", source.source_id)
    allowed_act_types = _DOCUMENT_CLASS_ACT_TYPES[source.document_class]
    if embedded_act_type not in allowed_act_types:
        raise ValueError(
            f"ARLIS document_class mismatch for {source.source_id}: manifest class "
            f"{source.document_class!r} permits {sorted(allowed_act_types)!r}, "
            f"source metadata has type {embedded_act_type!r}"
        )
    if source.document_class == DocumentClass.REGULATION.value:
        embedded_enactment_body = _required_act_info_value(
            act_info,
            "Ընդունող մարմին",
            source.source_id,
        )
        if embedded_enactment_body != _REGULATION_ENACTMENT_BODY:
            raise ValueError(
                f"ARLIS regulation enactment-body mismatch for {source.source_id}: "
                f"expected {_REGULATION_ENACTMENT_BODY!r}, got {embedded_enactment_body!r}"
            )
    embedded_number = _required_act_info_value(act_info, "Համար", source.source_id)
    if embedded_number != source.official_number:
        raise ValueError(
            f"ARLIS official_number mismatch for {source.source_id}: manifest has "
            f"{source.official_number!r}, source metadata has {embedded_number!r}"
        )

    adopted_value = _required_act_info_value(
        act_info,
        "Ընդունման ամսաթիվ",
        source.source_id,
    )
    adopted_match = _DOTTED_DATE_RE.fullmatch(adopted_value)
    if adopted_match is None:
        raise ValueError(
            f"ARLIS source {source.source_id} has an unrecognized adoption date: {adopted_value!r}"
        )
    try:
        embedded_adopted = date(
            int(adopted_match.group("year")),
            int(adopted_match.group("month")),
            int(adopted_match.group("day")),
        ).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"ARLIS source {source.source_id} has an invalid adoption date: {adopted_value!r}"
        ) from exc
    if embedded_adopted != source.adopted:
        raise ValueError(
            f"ARLIS adopted mismatch for {source.source_id}: manifest has "
            f"{source.adopted}, source metadata has {embedded_adopted}"
        )


def _require_incorporation_self_identity(
    current_rows: Sequence[Tag],
    source: ArmeniaARLISSource,
) -> None:
    if len(current_rows) != 1:
        raise ValueError(
            f"ARLIS source {source.source_id} must contain exactly one current-act "
            f"history row, got {len(current_rows)}"
        )
    current_row = current_rows[0]
    history_items = current_row.find_all(
        "div",
        class_="act-changes-history__item",
        recursive=False,
    )
    if len(history_items) != 2:
        raise ValueError(
            f"ARLIS source {source.source_id} current-act row must contain exactly "
            f"two direct history items, got {len(history_items)}"
        )
    self_links = history_items[1].find_all(
        "a",
        class_="act-link",
        href=True,
        recursive=False,
    )
    compare_controls = current_row.find_all(
        "div",
        class_="act-changes-history__couple-compare",
        recursive=False,
    )
    if len(self_links) != 1 or len(compare_controls) != 1:
        raise ValueError(
            f"ARLIS source {source.source_id} current-act row must expose exactly "
            "one direct self link and compare control"
        )
    embedded_self_href = self_links[0].get("href")
    embedded_compare_url = compare_controls[0].get("data-request-url")
    expected_self_href = f"/hy/acts/{source.act_id}"
    expected_compare_url = f"{expected_self_href}/compare/{source.act_id}"
    if embedded_self_href != expected_self_href or embedded_compare_url != expected_compare_url:
        raise ValueError(
            f"ARLIS act_id mismatch for {source.source_id}: manifest has "
            f"{source.act_id!r}, current-act metadata has self link "
            f"{embedded_self_href!r} and compare URL {embedded_compare_url!r}"
        )


def _act_info_values(soup: BeautifulSoup, source_id: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in soup.select(".act-info__item"):
        label_tag = item.select_one(".act-info__label")
        value_tag = item.select_one(".act-info__value")
        if label_tag is None or value_tag is None:
            raise ValueError(f"ARLIS source {source_id} has an incomplete act-info item")
        label = _inline_text(label_tag)
        value = _inline_text(value_tag)
        if not label or not value:
            raise ValueError(f"ARLIS source {source_id} has an empty act-info item")
        if label in values:
            raise ValueError(f"ARLIS source {source_id} has duplicate act-info label {label!r}")
        values[label] = value
    if not values:
        raise ValueError(f"ARLIS source {source_id} contains no act-info metadata")
    return values


def _required_act_info_value(
    act_info: Mapping[str, str],
    label: str,
    source_id: str,
) -> str:
    value = act_info.get(label)
    if value is None:
        raise ValueError(f"ARLIS source {source_id} is missing act-info field {label!r}")
    return value


def _require_expression_date(soup: BeautifulSoup, source: ArmeniaARLISSource) -> str:
    act_info = _act_info_values(soup, source.source_id)
    value = _required_act_info_value(act_info, "Փաստաթղթի տեսակ", source.source_id)
    matches = [
        (validity_kind, match)
        for validity_kind, pattern in _VALIDITY_PERIOD_RES.items()
        if (match := pattern.fullmatch(value)) is not None
    ]
    if len(matches) != 1:
        raise ValueError(
            f"ARLIS source {source.source_id} has an unrecognized validity value: {value!r}"
        )
    [(validity_kind, match)] = matches
    try:
        expression_date = date(
            int(match.group("start_year")),
            int(match.group("start_month")),
            int(match.group("start_day")),
        ).isoformat()
        expression_end_date = (
            date(
                int(match.group("end_year")),
                int(match.group("end_month")),
                int(match.group("end_day")),
            ).isoformat()
            if match.group("end_year") is not None
            else None
        )
    except ValueError as exc:
        raise ValueError(
            f"ARLIS source {source.source_id} has an invalid validity period: {value!r}"
        ) from exc
    if expression_end_date is not None and expression_end_date <= expression_date:
        raise ValueError(
            f"ARLIS source {source.source_id} has a non-increasing validity period: {value!r}"
        )
    if (
        expression_date != source.expression_date
        or expression_end_date != source.expression_end_date
    ):
        raise ValueError(
            f"ARLIS expression period mismatch for {source.source_id}: manifest has "
            f"{(source.expression_date, source.expression_end_date)}, source metadata has "
            f"{(expression_date, expression_end_date)}"
        )
    return validity_kind


def _article_header(table: Tag, *, source_url: str) -> _ArticleHeader | None:
    row = table.find("tr")
    if not isinstance(row, Tag):
        return None
    cells = row.find_all(["td", "th"], recursive=False)
    if not cells:
        return None
    marker = _inline_text(cells[0])
    match = _ARTICLE_MARKER_RE.fullmatch(marker)
    if match is None:
        return None
    if len(cells) != 2:
        raise ValueError(
            f"recognized ARLIS article header must have exactly two cells, got {len(cells)}"
        )
    heading = _inline_text(cells[1])
    if not heading:
        raise ValueError(f"ARLIS article {match.group('label')} has no heading")
    court_urls = tuple(
        dict.fromkeys(
            urljoin(source_url, str(anchor.get("href")))
            for anchor in cells[0].find_all("a", href=True)
            if "⚖" in _inline_text(anchor)
        )
    )
    return _ArticleHeader(
        label=_normalized_numeric_label(match.group("label")),
        raw_marker=marker,
        heading=heading,
        inline_body=None,
        court_decision_urls=court_urls,
    )


def _inline_article_header(block: Tag, *, source_url: str) -> _ArticleHeader | None:
    strong_tags = [block] if block.name == "strong" else []
    strong_tags.extend(block.find_all("strong"))
    marker_tags = [
        strong
        for strong in strong_tags
        if _ARTICLE_MARKER_RE.fullmatch(_inline_text(strong)) is not None
    ]
    if not marker_tags:
        return None
    if len(marker_tags) != 1:
        raise ValueError(
            f"recognized inline ARLIS article header must have one marker, got {len(marker_tags)}"
        )
    marker_tag = marker_tags[0]
    marker = _inline_text(marker_tag)
    match = _ARTICLE_MARKER_RE.fullmatch(marker)
    if match is None:  # pragma: no cover - guarded by marker_tags
        return None
    rendered = _render_block(block)
    if not rendered.startswith(marker):
        raise ValueError(
            f"recognized inline ARLIS article header has text before its marker: {rendered[:120]!r}"
        )
    inline_body = rendered[len(marker) :].strip() or None
    court_urls = tuple(
        dict.fromkeys(
            urljoin(source_url, str(anchor.get("href")))
            for anchor in marker_tag.find_all("a", href=True)
            if "⚖" in _inline_text(anchor)
        )
    )
    return _ArticleHeader(
        label=_normalized_numeric_label(match.group("label")),
        raw_marker=marker,
        heading=None,
        inline_body=inline_body,
        court_decision_urls=court_urls,
    )


def _headers_in_block(
    block: Tag,
    candidate_headers: Mapping[int, _ArticleHeader],
) -> list[tuple[Tag, _ArticleHeader]]:
    candidates = [block, *block.find_all(True)]
    return [
        (candidate, candidate_headers[id(candidate)])
        for candidate in candidates
        if id(candidate) in candidate_headers
    ]


def _reject_unbound_article_markers(
    root: Tag,
    candidate_headers: Mapping[int, _ArticleHeader],
    source_id: str,
) -> None:
    for text_node in root.find_all(string=_ARTICLE_WORD_RE):
        bound = any(
            id(parent) in candidate_headers
            for parent in text_node.parents
            if isinstance(parent, Tag) and parent is not root
        )
        if not bound:
            context = _inline_text(text_node.parent) if text_node.parent else str(text_node)
            raise ValueError(
                f"ARLIS source {source_id} contains an unrecognized article marker: "
                f"{context[:120]!r}"
            )


def _reject_unbound_appendix_markers(root: Tag, source_id: str) -> None:
    for block in root.find_all(recursive=False):
        marker = _inline_text(block)
        if _APPENDIX_WORD_RE.match(marker) is None:
            continue
        if _appendix_marker(block) is not None:
            continue
        if block.name != "table" and marker.endswith(("։", ".", "!", "?")):
            continue
        raise ValueError(
            f"ARLIS source {source_id} contains an unrecognized appendix marker: {marker!r}"
        )


def _require_empty_header_wrapper(block: Tag, table: Tag, source_id: str) -> None:
    if block is table:
        return
    outside_text: list[str] = []
    for text_node in block.find_all(string=True):
        if text_node.find_parent("table") is table:
            continue
        if str(text_node).strip():
            outside_text.append(str(text_node).strip())
    if outside_text:
        raise ValueError(
            f"ARLIS source {source_id} has unparsed text beside an article header: "
            f"{' '.join(outside_text)[:120]!r}"
        )


def _structure_marker(block: Tag) -> tuple[str, str, str, str | None] | None:
    raw_marker = _inline_text(block)
    match = _STRUCTURE_PREFIX_RE.fullmatch(raw_marker)
    if match is None:
        return None
    armenian_kind = re.sub(r"\s+", "", match.group("kind")).casefold()
    kind = _STRUCTURE_KIND.get(armenian_kind)
    if kind is None:
        raise ValueError(f"unsupported ARLIS hierarchy marker: {raw_marker!r}")
    suffix = match.group("suffix").strip()
    marker_end = match.start("suffix")
    return (
        kind,
        _normalized_numeric_label(match.group("label")),
        raw_marker[:marker_end].strip(),
        suffix or None,
    )


def _appendix_marker(block: Tag) -> tuple[str | None, str] | None:
    raw_marker = _inline_text(block)
    numbered_match = _NUMBERED_APPENDIX_RE.fullmatch(raw_marker)
    if numbered_match is not None:
        label = numbered_match.group("label")
        return (_normalized_numeric_label(label) if label else None), raw_marker
    authority_match = _AUTHORITY_APPENDIX_RE.fullmatch(raw_marker)
    if authority_match is None:
        return None
    label = authority_match.group("label")
    return (_normalized_numeric_label(label) if label else None), raw_marker


def _structure_parent(
    kind: str,
    contexts: Mapping[str, tuple[str, int]],
    document_path: str,
) -> tuple[str, int]:
    parent_candidates = {
        "part": (),
        "section": ("part",),
        "subsection": ("section", "part"),
        "chapter": ("subsection", "section", "part"),
    }[kind]
    for candidate in parent_candidates:
        if candidate in contexts:
            return contexts[candidate]
    return document_path, 0


def _clear_deeper_contexts(
    kind: str,
    contexts: dict[str, tuple[str, int]],
) -> None:
    current_level = _STRUCTURE_LEVEL[kind]
    for candidate in tuple(contexts):
        if _STRUCTURE_LEVEL[candidate] > current_level:
            contexts.pop(candidate)


def _deepest_context(
    contexts: Mapping[str, tuple[str, int]],
    document_path: str,
) -> tuple[str, int]:
    if not contexts:
        return document_path, 0
    return max(contexts.values(), key=lambda item: item[1])


def _hierarchy_metadata(
    contexts: Mapping[str, tuple[str, int]],
) -> list[dict[str, str]]:
    ordered = sorted(
        contexts.items(),
        key=lambda item: item[1][1],
    )
    return [{"kind": kind, "citation_path": path} for kind, (path, _level) in ordered]


def _structural_heading(blocks: Sequence[str]) -> str | None:
    values = [value.strip() for value in blocks if value.strip()]
    for value in values:
        if not value.startswith("("):
            return value.splitlines()[0]
    return values[0].splitlines()[0] if values else None


def _inline_text(tag: Tag) -> str:
    raw = (
        tag.get_text("", strip=False).replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    )
    return _ASCII_WHITESPACE_RE.sub(" ", raw.replace("\n", " ")).strip(" \t\r\f\v")


def _render_block(block: Tag) -> str:
    if block.name == "table":
        return _render_table(block)
    raw = "".join(_render_element(child) for child in block.children)
    return _render_text(raw)


def _render_element(node: PageElement) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"
    if node.name == "table":
        return _render_table(node)
    return "".join(_render_element(child) for child in node.children)


def _render_table(table: Tag) -> str:
    rendered_rows: list[str] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        rendered_cells = [
            _render_text("".join(_render_element(child) for child in cell.children))
            for cell in cells
        ]
        rendered_rows.append(" | ".join(cell for cell in rendered_cells if cell))
    return _joined_body(rendered_rows) or ""


def _render_text(raw: str) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = [_ASCII_WHITESPACE_RE.sub(" ", line).strip(" \t\r\f\v") for line in raw.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    compacted: list[str] = []
    for line in lines:
        if line or not compacted or compacted[-1]:
            compacted.append(line)
    return "\n".join(compacted)


def _joined_body(blocks: Sequence[str]) -> str | None:
    values = [value for value in blocks if value.strip()]
    return "\n".join(values) if values else None


def _is_signature_block(block: Tag) -> bool:
    if block.name != "table":
        return False
    cells = [_inline_text(cell) for cell in block.find_all(["td", "th"])]
    non_empty_cells = [cell for cell in cells if cell]
    if not 2 <= len(cells) <= 4 or len(non_empty_cells) < 2:
        return False
    role = re.sub(r"\s+", "", non_empty_cells[0]).casefold()
    return role in _SIGNATURE_ROLES and _SIGNATURE_NAME_RE.fullmatch(non_empty_cells[1]) is not None


def _normalized_numeric_label(value: str) -> str:
    return value.replace("․", ".")


def _citation_label(
    source: ArmeniaARLISSource,
    provision: ArmeniaARLISProvision,
) -> str:
    if provision.kind == "document":
        return f"{source.official_number} — {source.title}"
    if provision.kind == "article":
        return f"{source.official_number}, Հոդված {provision.label}"
    return f"{source.official_number}, {provision.kind} {provision.label}"


def _source_metadata(source: ArmeniaARLISSource) -> dict[str, Any]:
    metadata = {
        "source_id": source.source_id,
        "act_id": source.act_id,
        "official_number": source.official_number,
        "adopted": source.adopted,
        "title": source.title,
        "source_authority": "ARLIS (Armenian Legal Information System)",
        "source_language": source.language,
        "consolidated_expression": True,
        "expected_article_count": source.expected_article_count,
        "verified_source_sha256": source.sha256,
    }
    if source.expression_end_date is not None:
        metadata["expression_end_date"] = source.expression_end_date
    if source.expected_appendix_count is not None:
        metadata["expected_appendix_count"] = source.expected_appendix_count
    return metadata


def _require_unique_parsed_citations(
    provisions: Sequence[ArmeniaARLISProvision],
    source_id: str,
) -> None:
    article_labels = [provision.label for provision in provisions if provision.kind == "article"]
    duplicate_article_labels = sorted(
        label for label in set(article_labels) if article_labels.count(label) > 1
    )
    if duplicate_article_labels:
        raise ValueError(
            f"ARLIS source {source_id} produced duplicate article labels: "
            f"{', '.join(duplicate_article_labels[:5])}"
        )

    paths = [provision.citation_path for provision in provisions]
    duplicates = sorted(path for path in set(paths) if paths.count(path) > 1)
    if duplicates:
        raise ValueError(
            f"ARLIS source {source_id} produced duplicate citation paths: "
            f"{', '.join(duplicates[:5])}"
        )


def _require_unique_citations(records: Sequence[ProvisionRecord]) -> None:
    paths = [record.citation_path for record in records]
    duplicates = sorted(path for path in set(paths) if paths.count(path) > 1)
    if duplicates:
        raise ValueError(
            f"ARLIS extraction produced duplicate citation paths: {', '.join(duplicates[:5])}"
        )
