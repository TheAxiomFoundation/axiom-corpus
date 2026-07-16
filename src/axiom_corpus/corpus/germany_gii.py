"""gesetze-im-internet.de (juris XML) extraction into source-first corpus artifacts.

This adapter ingests consolidated German federal statutes and ordinances from the
official Bundesministerium der Justiz portal ``gesetze-im-internet.de``. Each law
is published as a ``juris`` XML document inside a per-law ZIP archive::

    https://www.gesetze-im-internet.de/<gesetz-slug>/xml.zip

The archive holds one ``BJNR*.xml`` document whose root ``<dokumente>`` element
carries a flat list of ``<norm>`` elements: the first ``<norm>`` is the law-level
frame (Rahmennorm) with the act metadata (``jurabk``, ``langue`` title,
``ausfertigung-datum``, ``fundstelle``, ``standangabe``); every following
``<norm>`` is either a section (``<enbez>`` = ``§ N``), an appendix
(``<enbez>`` = ``Anlage N``), a table-of-contents norm (``Inhaltsübersicht``), a
repealed-range placeholder (``<enbez>`` = ``(XXXX) §§ N bis M`` with
``<titel>`` = ``(weggefallen)``), or a structural division heading
(``<gliederungseinheit>`` with no ``<enbez>``).

Citation-path scheme
--------------------
The corpus citation path is the stable public identity of every provision
(``provision_id = uuid5(NAMESPACE_URL, "axiom:" + citation_path)``), so it must
conform to ``schema/citation-path.v1.json`` (segment 0 = jurisdiction, segment 1 =
``document_class``, all segments lowercase, no spaces/underscores/en-dashes, no
``block-N``/``page-N``, no two-segment collection roots). The scheme is::

    de/statute/<gesetz-slug>                     # law-level parent (kind=document)
    de/statute/<gesetz-slug>/<norm>              # per-norm child

where ``<gesetz-slug>`` is the site slug transliterated and slugified
(``solzg_1995`` → ``solzg-1995``; the exact site slug is retained in
``identifiers["gesetze-im-internet.de:slug"]``) and ``<norm>`` is derived from the
norm's ``<enbez>`` (or division key). Examples::

    de/statute/estg                              # Einkommensteuergesetz (parent)
    de/statute/estg/1                            # § 1
    de/statute/estg/32a                          # § 32a
    de/statute/estg/66                           # § 66
    de/statute/estg/anlage-1                     # Anlage 1
    de/statute/estg/anlage-1a                    # Anlage 1a
    de/statute/estg/inhaltsuebersicht            # Inhaltsübersicht
    de/statute/estg/xxxx-7c-bis-7d               # (XXXX) §§ 7c bis 7d (weggefallen)
    de/statute/estg/gl-010                       # division "I. Steuerpflicht"

The section slug is ``§``-stripped and slugified: ``§ 32a`` → ``32a``,
``§ 4d`` → ``4d``. Umlauts are transliterated (ä→ae, ö→oe, ü→ue, ß→ss) because the
grammar charset excludes them. Division headings that carry no ``<enbez>`` are
keyed by their ``<gliederungskennzahl>`` under a ``gl-`` prefix so they can never
collide with a numeric section slug. Because juris occasionally reuses a
``gliederungskennzahl`` (observed twice in SGB V), any residual slug collision is
resolved deterministically by appending the norm's unique ``doknr`` tail, so every
provision within a law has a distinct, stable citation path and coverage is always
complete (source citation set == provision citation set).

Every ``<norm>`` becomes exactly one provision, so the emitted provision set is a
faithful, byte-grounded reconstruction of the consolidated document. The parsed
source XML is retained under the store's ``sources/`` tree with its sha256 before
any provision is emitted (provenance: never encode from unretained text).
"""

from __future__ import annotations

import io
import re
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, cast

import requests
import yaml
from lxml import etree

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

GERMAN_GII_SOURCE_FORMAT = "gesetze-im-internet.de-juris-xml"
GII_BASE_URL = "https://www.gesetze-im-internet.de"
GII_SOURCE_AUTHORITY = "Bundesministerium der Justiz (juris GmbH)"
GII_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; axiom-corpus/0.1; "
        "+https://axiom-foundation.org; hello@axiom-foundation.org)"
    ),
    "Accept": "application/zip,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

_GERMAN_TRANSLITERATION = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "ae",
        "Ö": "oe",
        "Ü": "ue",
        "ß": "ss",
    }
)
_WEGGEFALLEN_RE = re.compile(r"weggefallen", re.IGNORECASE)
_LEADING_INT_RE = re.compile(r"\d+")


# ---------------------------------------------------------------------------
# Configuration and parsed structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GermanLaw:
    """One gesetze-im-internet.de law selected for ingestion."""

    slug: str
    jurisdiction: str = "de"
    document_class: str = DocumentClass.STATUTE.value
    title: str | None = None
    source_url: str | None = None
    source_id: str | None = None
    local_source: Path | None = None
    source_as_of: str | None = None
    expression_date: str | None = None
    metadata: Mapping[str, Any] | None = None

    @property
    def xml_zip_url(self) -> str:
        return self.source_url or f"{GII_BASE_URL}/{self.slug}/xml.zip"

    @property
    def html_url(self) -> str:
        return f"{GII_BASE_URL}/{self.slug}/"

    @property
    def citation_slug(self) -> str:
        return _slug(self.slug)

    @property
    def parent_citation_path(self) -> str:
        return f"{self.jurisdiction}/{self.document_class}/{self.citation_slug}"


@dataclass(frozen=True)
class GermanNorm:
    """A single ``<norm>`` parsed from a juris XML law document."""

    doknr: str
    doknr_tail: str
    kind: str
    norm_slug: str | None
    heading: str | None
    body: str
    jurabk: str | None = None
    enbez: str | None = None
    ordinal: int | None = None
    repealed: bool = False
    gliederungsbez: str | None = None
    gliederungskennzahl: str | None = None
    law_metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GermanGiiScopeReport:
    """Artifact report for one (jurisdiction, document_class) scope."""

    jurisdiction: str
    document_class: str
    law_count: int
    source_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class GermanGiiExtractReport:
    """Combined gesetze-im-internet.de extraction report."""

    version: str
    source_count: int
    provisions_written: int
    scope_reports: tuple[GermanGiiScopeReport, ...]


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------
def load_german_gii_laws(manifest_path: str | Path) -> tuple[GermanLaw, ...]:
    """Load the ``documents:`` list of a gesetze-im-internet manifest into laws.

    The manifest follows the official-documents shape (see
    ``manifests/de-*-official-documents.yaml``). Each document entry names a site
    ``slug`` and its expected law-level ``citation_path``; the derived parent path
    is cross-checked against that value so a slug typo fails fast.
    """
    data = yaml.safe_load(Path(manifest_path).read_text())
    if not isinstance(data, dict):
        raise ValueError("gesetze-im-internet manifest must be a YAML mapping")
    documents = data.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("gesetze-im-internet manifest must list at least one document")

    laws: list[GermanLaw] = []
    seen: set[str] = set()
    for entry in documents:
        if not isinstance(entry, dict):
            raise ValueError("each manifest document must be a mapping")
        slug = str(entry["slug"]).strip()
        if not slug:
            raise ValueError("manifest document slug must be non-empty")
        if slug in seen:
            raise ValueError(f"duplicate law slug in manifest: {slug}")
        seen.add(slug)
        law = GermanLaw(
            slug=slug,
            jurisdiction=str(entry.get("jurisdiction", "de")),
            document_class=str(entry.get("document_class", DocumentClass.STATUTE.value)),
            title=entry.get("title"),
            source_url=entry.get("source_url"),
            source_id=entry.get("source_id"),
            source_as_of=entry.get("source_as_of"),
            expression_date=entry.get("expression_date"),
            metadata=entry.get("metadata"),
        )
        expected = entry.get("citation_path")
        if expected is not None and str(expected) != law.parent_citation_path:
            raise ValueError(
                f"manifest citation_path {expected!r} does not match the derived "
                f"parent path {law.parent_citation_path!r} for slug {slug!r}"
            )
        laws.append(law)
    return tuple(laws)


# ---------------------------------------------------------------------------
# Extraction orchestration
# ---------------------------------------------------------------------------
def extract_german_gii(
    store: CorpusArtifactStore,
    *,
    version: str,
    laws: Sequence[GermanLaw] = (),
    manifest: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    fetch_date: date | str | None = None,
    request_timeout: float = 60.0,
    limit: int | None = None,
) -> GermanGiiExtractReport:
    """Fetch, retain, and normalize gesetze-im-internet juris XML into artifacts.

    Every ``<norm>`` in each law becomes one provision. Source XML is retained
    under ``sources/`` with its sha256 before any provision is written. Records,
    inventory, and coverage are grouped and written per
    ``(jurisdiction, document_class)`` scope, mirroring ``belgium_eli``.
    """
    selected = list(laws)
    if manifest is not None:
        selected.extend(load_german_gii_laws(manifest))
    if not selected:
        raise ValueError("at least one law or a manifest is required")
    if limit is not None:
        selected = selected[:limit]

    expression_text = _date_text(expression_date)
    run_fetch_date = _date_text(fetch_date) or date.today().isoformat()

    grouped_records: dict[tuple[str, str], list[ProvisionRecord]] = defaultdict(list)
    grouped_inventory: dict[tuple[str, str], list[SourceInventoryItem]] = defaultdict(list)
    grouped_sources: dict[tuple[str, str], dict[str, Path]] = defaultdict(dict)
    law_counts: Counter[tuple[str, str]] = Counter()
    seen_parents: dict[str, str] = {}

    for law in selected:
        scope = (law.jurisdiction, law.document_class)
        # Two distinct site slugs can slugify to the same parent path
        # (e.g. ``sgb_2`` and ``sgb-2`` both map to ``de/statute/sgb-2``),
        # which would collide the two laws' provision paths. Fail loudly
        # rather than let coverage dedup silently drop one law.
        prior = seen_parents.get(law.parent_citation_path)
        if prior is not None and prior != law.slug:
            raise ValueError(
                f"laws {prior!r} and {law.slug!r} map to the same citation path "
                f"{law.parent_citation_path!r}"
            )
        seen_parents[law.parent_citation_path] = law.slug

        xml_bytes, inner_name = _load_law_bytes(law, request_timeout=request_timeout)
        norms = parse_gii_law(xml_bytes, law=law)
        if not norms:
            raise ValueError(f"no <norm> elements parsed from {law.slug}")

        law_counts[scope] += 1
        relative_name = f"{law.slug}/{inner_name}"
        source_artifact_path = store.source_path(
            law.jurisdiction, law.document_class, version, relative_name
        )
        source_sha = store.write_bytes(source_artifact_path, xml_bytes)
        grouped_sources[scope][relative_name] = source_artifact_path
        source_key = _source_key(law.jurisdiction, law.document_class, version, relative_name)

        # source_as_of semantics: a live fetch is stamped with the actual
        # fetch date — a manifest value cannot relabel it (mislabeling a
        # later re-fetch with a stale date is the org-wide date-field bug
        # class). Offline artifacts carry no inferable fetch date, so an
        # explicit per-law or run-level value is required. A version slug
        # is never an acceptable fallback.
        if law.local_source is None:
            if law.source_as_of and law.source_as_of != run_fetch_date:
                raise ValueError(
                    f"{law.slug}: manifest source_as_of {law.source_as_of!r} "
                    f"conflicts with the live fetch date {run_fetch_date}; drop "
                    "the manifest value (live fetches self-stamp) or ingest the "
                    "retained artifact offline with an explicit date"
                )
            law_as_of = run_fetch_date
        else:
            offline_as_of = law.source_as_of or source_as_of
            if not offline_as_of:
                raise ValueError(
                    f"{law.slug}: offline sources require source_as_of (per-law "
                    "manifest value or --source-as-of) recording when the "
                    "artifact was fetched from gesetze-im-internet.de"
                )
            law_as_of = offline_as_of
        _require_iso_date(law_as_of, field_name="source_as_of", slug=law.slug)
        law_expression = _date_text(law.expression_date) or expression_text or law_as_of
        _require_iso_date(law_expression, field_name="expression_date", slug=law.slug)

        for norm in norms:
            citation_path = _citation_path(law, norm)
            record = _provision_record(
                law,
                norm,
                citation_path=citation_path,
                version=version,
                source_key=source_key,
                source_as_of=law_as_of,
                expression_date=law_expression,
            )
            grouped_records[scope].append(record)
            grouped_inventory[scope].append(
                SourceInventoryItem(
                    citation_path=citation_path,
                    source_url=law.xml_zip_url,
                    source_path=source_key,
                    source_format=GERMAN_GII_SOURCE_FORMAT,
                    sha256=source_sha,
                    metadata={
                        "slug": law.slug,
                        "doknr": norm.doknr,
                        "kind": norm.kind,
                        "enbez": norm.enbez,
                        "heading": norm.heading,
                        "primary_source": _primary_source(law),
                    },
                )
            )

    scope_reports: list[GermanGiiScopeReport] = []
    for jurisdiction, document_class in sorted(grouped_records):
        scope = (jurisdiction, document_class)
        records = _dedupe_records(grouped_records[scope])
        inventory = _dedupe_inventory(grouped_inventory[scope])

        inventory_path = store.inventory_path(jurisdiction, document_class, version)
        store.write_inventory(inventory_path, inventory)
        provisions_path = store.provisions_path(jurisdiction, document_class, version)
        store.write_provisions(provisions_path, records)
        coverage = compare_provision_coverage(
            inventory,
            records,
            jurisdiction=jurisdiction,
            document_class=document_class,
            version=version,
        )
        coverage_path = store.coverage_path(jurisdiction, document_class, version)
        store.write_json(coverage_path, coverage.to_mapping())
        source_paths = tuple(
            grouped_sources[scope][name] for name in sorted(grouped_sources[scope])
        )
        scope_reports.append(
            GermanGiiScopeReport(
                jurisdiction=jurisdiction,
                document_class=document_class,
                law_count=law_counts[scope],
                source_count=len(inventory),
                provisions_written=len(records),
                inventory_path=inventory_path,
                provisions_path=provisions_path,
                coverage_path=coverage_path,
                coverage=coverage,
                source_paths=source_paths,
            )
        )

    return GermanGiiExtractReport(
        version=version,
        source_count=sum(report.source_count for report in scope_reports),
        provisions_written=sum(report.provisions_written for report in scope_reports),
        scope_reports=tuple(scope_reports),
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def parse_gii_law(xml_bytes: bytes, *, law: GermanLaw) -> tuple[GermanNorm, ...]:
    """Parse one juris XML law document into ordered, uniquely-slugged norms."""
    root = _parse_xml(xml_bytes)
    if _local(root) != "dokumente":
        raise ValueError(f"unexpected juris XML root <{_local(root)}> for {law.slug}")
    root_doknr = root.get("doknr") or ""
    norm_elements = root.findall("norm")
    parsed = [
        _parse_norm(element, index=index, root_doknr=root_doknr)
        for index, element in enumerate(norm_elements)
    ]
    return _disambiguate_slugs(parsed)


def _parse_norm(element: Any, *, index: int, root_doknr: str) -> GermanNorm:
    metadaten = element.find("metadaten")
    if metadaten is None:
        raise ValueError("juris <norm> is missing <metadaten>")
    doknr = element.get("doknr") or ""
    doknr_tail = doknr.removeprefix(root_doknr) or doknr

    jurabk = _clean(metadaten.findtext("jurabk"))
    enbez = _clean(metadaten.findtext("enbez"))
    titel = _element_text(metadaten.find("titel"))
    gliederung = metadaten.find("gliederungseinheit")
    kennzahl = _clean(metadaten.findtext("gliederungseinheit/gliederungskennzahl"))
    gliederungsbez = _clean(metadaten.findtext("gliederungseinheit/gliederungsbez"))
    gliederungstitel = _element_text(metadaten.find("gliederungseinheit/gliederungstitel"))

    textdaten = element.find("textdaten")
    text_content = None
    fussnoten_content = None
    if textdaten is not None:
        # ``text`` holds either a <Content> body or a <TOC> (the
        # Inhaltsübersicht table of contents); render whichever is present.
        text_content = textdaten.find("text/Content")
        if text_content is None:
            text_content = textdaten.find("text/TOC")
        fussnoten_content = textdaten.find("fussnoten/Content")

    if index == 0:
        return _parse_law_frame(
            metadaten,
            doknr=doknr,
            doknr_tail=doknr_tail,
            jurabk=jurabk,
            titel=titel,
            fussnoten_content=fussnoten_content,
        )

    body = _render_content(text_content)
    repealed = _is_repealed(titel, body)

    kind: str
    norm_slug: str
    heading: str | None
    ordinal: int | None
    if enbez is not None:
        kind = _enbez_kind(enbez)
        norm_slug = _slug(enbez)
        heading = titel or enbez
        ordinal = _leading_int(enbez)
    elif gliederung is not None:
        kind = "division"
        norm_slug = "gl-" + _slug(kennzahl or doknr_tail)
        heading = _join_heading(gliederungsbez, gliederungstitel)
        ordinal = None
        if not body:
            body = gliederungstitel or gliederungsbez or ""
    else:
        kind = "norm"
        norm_slug = "n-" + _slug(doknr_tail or str(index))
        heading = titel
        ordinal = None

    if repealed and not body:
        body = titel or "(weggefallen)"

    return GermanNorm(
        doknr=doknr,
        doknr_tail=doknr_tail,
        kind=kind,
        norm_slug=norm_slug or "n-" + _slug(doknr_tail or str(index)),
        heading=heading,
        body=body,
        jurabk=jurabk,
        enbez=enbez,
        ordinal=ordinal,
        repealed=repealed,
        gliederungsbez=gliederungsbez,
        gliederungskennzahl=kennzahl,
    )


def _parse_law_frame(
    metadaten: Any,
    *,
    doknr: str,
    doknr_tail: str,
    jurabk: str | None,
    titel: str | None,
    fussnoten_content: Any | None,
) -> GermanNorm:
    langue = _element_text(metadaten.find("langue"))
    amtabk = _clean(metadaten.findtext("amtabk"))
    ausfertigung = _clean(metadaten.findtext("ausfertigung-datum"))
    periodikum = _clean(metadaten.findtext("fundstelle/periodikum"))
    zitstelle = _clean(metadaten.findtext("fundstelle/zitstelle"))
    fundstelle = " ".join(part for part in (periodikum, zitstelle) if part) or None
    stand = _latest_stand(metadaten)

    law_metadata: dict[str, str] = {}
    for key, value in (
        ("jurabk", jurabk),
        ("amtabk", amtabk),
        ("langtitel", langue),
        ("ausfertigung_datum", ausfertigung),
        ("fundstelle", fundstelle),
        ("stand", stand),
    ):
        if value:
            law_metadata[key] = value

    body_lines: list[str] = []
    if langue:
        body_lines.append(langue)
    if ausfertigung:
        body_lines.append(f"Ausfertigungsdatum: {ausfertigung}")
    if fundstelle:
        body_lines.append(f"Fundstelle: {fundstelle}")
    if stand:
        body_lines.append(f"Stand: {stand}")
    footnote_text = _render_content(fussnoten_content)
    if footnote_text:
        body_lines.append(footnote_text)

    return GermanNorm(
        doknr=doknr,
        doknr_tail=doknr_tail,
        kind="document",
        norm_slug=None,
        heading=langue or titel or jurabk,
        body="\n".join(body_lines).strip(),
        jurabk=jurabk,
        enbez=None,
        ordinal=None,
        repealed=False,
        law_metadata=law_metadata,
    )


def _disambiguate_slugs(norms: Sequence[GermanNorm]) -> tuple[GermanNorm, ...]:
    """Guarantee unique per-law leaf slugs, keying collisions off the doknr tail.

    Section (``<enbez>``) slugs are unique in every observed law; division keys can
    repeat, so a residual collision is resolved by suffixing every member of the
    colliding group with its unique ``doknr`` tail. Applying the suffix to the whole
    group (not only the later members) keeps each provision's identity independent
    of iteration order.
    """
    counts = Counter(norm.norm_slug for norm in norms if norm.norm_slug is not None)
    collisions = {slug for slug, count in counts.items() if count > 1}
    if not collisions:
        return tuple(norms)
    resolved: list[GermanNorm] = []
    for norm in norms:
        if norm.norm_slug is not None and norm.norm_slug in collisions:
            suffix = _slug(norm.doknr_tail or norm.doknr)
            resolved.append(replace(norm, norm_slug=f"{norm.norm_slug}-{suffix}"))
        else:
            resolved.append(norm)
    return tuple(resolved)


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------
def _citation_path(law: GermanLaw, norm: GermanNorm) -> str:
    if norm.kind == "document" or norm.norm_slug is None:
        return law.parent_citation_path
    return f"{law.parent_citation_path}/{norm.norm_slug}"


def _provision_record(
    law: GermanLaw,
    norm: GermanNorm,
    *,
    citation_path: str,
    version: str,
    source_key: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    is_parent = norm.kind == "document"
    parent_path = None if is_parent else law.parent_citation_path
    parent_id = None if parent_path is None else deterministic_provision_id(parent_path)

    identifiers: dict[str, str] = {
        "gesetze-im-internet.de:slug": law.slug,
        "gesetze-im-internet.de:doknr": norm.doknr,
    }
    if norm.jurabk:
        identifiers["gesetze-im-internet.de:jurabk"] = norm.jurabk
    if norm.enbez:
        identifiers["gesetze-im-internet.de:enbez"] = norm.enbez
    if norm.gliederungskennzahl:
        identifiers["gesetze-im-internet.de:gliederungskennzahl"] = norm.gliederungskennzahl

    metadata: dict[str, Any] = {
        "law_slug": law.slug,
        "law_title": law.title or norm.law_metadata.get("langtitel"),
        "jurabk": norm.jurabk,
        "kind": norm.kind,
        "enbez": norm.enbez,
        "gliederungsbez": norm.gliederungsbez,
        "source_authority": GII_SOURCE_AUTHORITY,
        "legal_authority_url": law.html_url,
        "xml_source_url": law.xml_zip_url,
        "primary_source": _primary_source(law),
    }
    if norm.repealed:
        metadata["repealed"] = True
    if is_parent and norm.law_metadata:
        metadata["law_metadata"] = dict(norm.law_metadata)
    if law.metadata:
        for key, value in law.metadata.items():
            metadata.setdefault(str(key), value)

    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=law.jurisdiction,
        document_class=law.document_class,
        citation_path=citation_path,
        citation_label=_citation_label(law, norm),
        heading=norm.heading,
        body=norm.body or None,
        version=version,
        source_url=law.xml_zip_url,
        source_path=source_key,
        source_id=norm.doknr,
        source_format=GERMAN_GII_SOURCE_FORMAT,
        source_document_id=law.parent_citation_path,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=parent_id,
        level=0 if is_parent else 1,
        ordinal=norm.ordinal,
        kind=norm.kind,
        language="de",
        legal_identifier=norm.enbez or norm.gliederungsbez,
        identifiers=identifiers,
        metadata=_prune_none(metadata),
    )


def _citation_label(law: GermanLaw, norm: GermanNorm) -> str:
    abbreviation = norm.jurabk or law.title or law.slug
    if norm.kind == "document":
        return norm.law_metadata.get("langtitel") or abbreviation
    label = norm.enbez or norm.gliederungsbez or (norm.norm_slug or "")
    return f"{abbreviation} {label}".strip()


def _primary_source(law: GermanLaw) -> bool:
    if law.metadata is not None and "primary_source" in law.metadata:
        return bool(law.metadata["primary_source"])
    return True


# ---------------------------------------------------------------------------
# juris XML text rendering
# ---------------------------------------------------------------------------
def _parse_xml(data: bytes) -> Any:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=True,
    )
    return etree.fromstring(data, parser=parser)


def _render_content(content: Any | None) -> str:
    """Render a ``<Content>`` element into faithful plain text.

    Paragraphs (``<P>`` = Absätze) become lines, ``<DL>`` enumerations keep their
    markers glued to the item text (``1. …``, ``a) …``), and CALS tables become
    pipe-delimited rows. Layout attributes are dropped; footnote-reference anchors
    are dropped; all numbering and body text is preserved.
    """
    if content is None:
        return ""
    blocks: list[str] = []
    for child in content:
        if not isinstance(child.tag, str):
            # XML comments / processing instructions are juris-internal markup
            # (e.g. "Start:"/"Ende:"/"SPLIT UMBAU") — never statutory content.
            # Text following a block-level comment is statutory, keep it.
            if child.tail and child.tail.strip():
                blocks.append(child.tail.strip())
            continue
        tag = _local(child)
        if tag == "table":
            blocks.append(_render_table(child))
        elif tag == "DL":
            blocks.append(_render_dl(child))
        elif tag == "BR":
            blocks.append("")
        else:
            blocks.append(_inline_text(child).strip())
    return _normalize_whitespace("\n".join(blocks))


def _inline_text(element: Any) -> str:
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if not isinstance(child.tag, str):
            # Skip juris-internal XML comments but keep the text that follows
            # them — dropping a comment must never drop statutory text.
            if child.tail:
                parts.append(child.tail)
            continue
        tag = _local(child)
        if tag == "BR":
            parts.append("\n")
        elif tag == "FnR":
            pass
        elif tag == "DL":
            parts.append("\n" + _render_dl(child))
        elif tag == "table":
            parts.append("\n" + _render_table(child))
        else:
            parts.append(_inline_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _render_dl(dl: Any) -> str:
    items: list[str] = []
    children = list(dl)
    index = 0
    while index < len(children):
        node = children[index]
        if _local(node) == "DT":
            term = _inline_text(node).strip()
            definition = ""
            if index + 1 < len(children) and _local(children[index + 1]) == "DD":
                definition = _inline_text(children[index + 1]).strip()
                index += 2
            else:
                index += 1
            item = f"{term} {definition}".strip()
        else:
            item = _inline_text(node).strip()
            index += 1
        if item:
            items.append(item)
    return "\n".join(items)


def _render_table(table: Any) -> str:
    rows: list[str] = []
    for child in table:
        # CALS table titles are statutory content (e.g. SGB VI Anlage 5's
        # "1. Freiwillige Beiträge zur Versicherungsanstalt Berlin").
        if isinstance(child.tag, str) and _local(child).lower() == "title":
            title = _inline_text(child).strip()
            if title:
                rows.append(title)
    for row in table.iter("row"):
        # Direct rows only: a nested table inside an <entry> is rendered by
        # _inline_text within its cell — letting the OUTER table's descendant
        # iteration also collect the inner rows duplicated every nested row
        # (WoGG Anlage 2's formula tables, round-2 gate finding).
        ancestor = row.getparent()
        while ancestor is not None and not (
            isinstance(ancestor.tag, str) and _local(ancestor) == "table"
        ):
            ancestor = ancestor.getparent()
        if ancestor is not table:
            continue
        cells = [_inline_text(entry).strip() for entry in row.findall("entry")]
        line = " | ".join(cell for cell in cells if cell)
        if line:
            rows.append(line)
    return "\n".join(rows)


def _element_text(element: Any | None) -> str | None:
    if element is None:
        return None
    text = _normalize_whitespace(_inline_text(element))
    return text or None


def _local(element: Any) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    return cast(str, etree.QName(element).localname)


def _latest_stand(metadaten: Any) -> str | None:
    stand: str | None = None
    for angabe in metadaten.findall("standangabe"):
        typ = _clean(angabe.findtext("standtyp"))
        kommentar = _element_text(angabe.find("standkommentar"))
        if typ and typ.lower().startswith("stand") and kommentar:
            stand = kommentar
    return stand


# ---------------------------------------------------------------------------
# Slugging and text helpers
# ---------------------------------------------------------------------------
def _slug(value: str) -> str:
    text = value.translate(_GERMAN_TRANSLITERATION).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _enbez_kind(enbez: str) -> str:
    lowered = enbez.lower()
    if lowered.startswith("anlage"):
        return "anlage"
    if "inhalt" in lowered:
        return "overview"
    if "§" in enbez:
        return "section"
    return "norm"


def _is_repealed(titel: str | None, body: str) -> bool:
    if titel and _WEGGEFALLEN_RE.search(titel):
        return True
    stripped = body.strip()
    return bool(stripped) and len(stripped) < 32 and bool(_WEGGEFALLEN_RE.search(stripped))


def _leading_int(text: str) -> int | None:
    match = _LEADING_INT_RE.search(text)
    return int(match.group(0)) if match else None


def _join_heading(*parts: str | None) -> str | None:
    joined = " ".join(part for part in parts if part)
    return joined or None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = _normalize_whitespace(value)
    return text or None


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _prune_none(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


def _date_text(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return value


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _require_iso_date(value: str, *, field_name: str, slug: str) -> str:
    """Reject any provision date that is not a real ISO date.

    Version slugs and other non-dates must never reach provision rows'
    ``source_as_of``/``expression_date`` (the date-field contamination class
    caught org-wide on 2026-07-16).
    """
    if not _ISO_DATE_RE.match(value):
        raise ValueError(f"{slug}: {field_name} must be an ISO date (YYYY-MM-DD), got {value!r}")
    return value


# ---------------------------------------------------------------------------
# Source acquisition
# ---------------------------------------------------------------------------
def _load_law_bytes(law: GermanLaw, *, request_timeout: float) -> tuple[bytes, str]:
    if law.local_source is not None:
        raw = Path(law.local_source).read_bytes()
        name = Path(law.local_source).name
    else:
        raw = _fetch_zip(law.xml_zip_url, timeout=request_timeout)
        name = None
    if _looks_like_zip(raw):
        return _extract_inner_xml(raw)
    return raw, name or f"{law.slug}.xml"


def _looks_like_zip(data: bytes) -> bool:
    return data[:2] == b"PK"


def _extract_inner_xml(zip_bytes: bytes) -> tuple[bytes, str]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if not xml_names:
            raise ValueError("gesetze-im-internet archive contains no .xml document")
        inner = sorted(xml_names)[0]
        return archive.read(inner), Path(inner).name


def _fetch_zip(url: str, *, timeout: float) -> bytes:
    session = requests.Session()
    session.headers.update(GII_REQUEST_HEADERS)
    last_error: requests.RequestException | None = None
    for attempt in range(1, 5):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:  # pragma: no cover - network path
            last_error = error
            if attempt == 4:
                break
            time.sleep(min(2**attempt, 10))
    if last_error is not None:  # pragma: no cover - network path
        raise last_error
    raise RuntimeError(f"failed to fetch {url}")  # pragma: no cover - unreachable


def _source_key(
    jurisdiction: str,
    document_class: str,
    version: str,
    relative_name: str,
) -> str:
    return f"sources/{jurisdiction}/{document_class}/{version}/{relative_name}"


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
