"""New Zealand district plan (council instrument) extraction into corpus artifacts.

A district plan is a binding regulatory instrument made by a territorial authority
under Schedule 1 of the Resource Management Act 1991. It is neither central-government
statute nor central-government regulation, so it carries its own ``district-plan``
document class (see ``schema/citation-path.v1.json``) with an issuer-scoped citation
shape::

    <jurisdiction>/district-plan/<territorial-authority>/<plan-version>/<chapter>/<provision>
    e.g. nz/district-plan/wellington-city/2024/muz/r13

Most New Zealand councils publish their district plans on the IsoPlan ePlan platform
(Wellington: ``eplan.wellington.govt.nz``), which exposes revision-pinned JSON chapter
endpoints behind the viewer. One IsoPlan adapter therefore covers many of the 67
territorial authorities. This module is manifest-driven and fetcher-injectable
(mirroring ``eli.py``) so full-council ingestion runs from the live endpoints while the
offline test path drives checked-in payload fixtures.

The corpus repo owns source text and provenance only. Executable activity-status
encodings live in ``rulespec-nz`` and cite these provisions through their
``source_verification.corpus_citation_path`` field.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, TextIO

import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

# ---------------------------------------------------------------------------
# Citation-path shape + document class — the one canonical definition. Any
# consumer (rulespec-nz, axiom-encode grounding per axiom-encode#1144) must
# accept the same shape before grounding resolves end to end.
# ---------------------------------------------------------------------------
DISTRICT_PLAN_DOCUMENT_CLASS = DocumentClass.DISTRICT_PLAN.value
DISTRICT_PLAN_DEFINITIONS_CHAPTER = "definitions"
ISOPLAN_SOURCE_FORMAT = "isoplan-eplan-json"
ISOPLAN_REVISION_SOURCE_FORMAT = "isoplan-eplan-revision-json"

# IsoPlan viewer endpoints sit behind a WAF that rejects non-browser clients; a
# browser-shaped request with an XHR marker and same-origin referer is accepted.
ISOPLAN_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# IsoPlan ``ruleTextSize`` is a heading-level marker: 7 is a provision (rule /
# standard) heading, 5 is body / self-contained policy-objective content, and
# every other value is a structural section divider (zone title, "Objectives",
# "Policies", "Standards", precinct headers). Only content sizes carry law.
_PROVISION_HEADING_SIZE = 7
_CONTENT_SIZE = 5
_CONTENT_SIZES = frozenset({_CONTENT_SIZE, _PROVISION_HEADING_SIZE})

# A plan rule identifier: a chapter/zone code, then one or more hyphen segments
# with at least one digit-bearing segment (MUZ-R13, MUZ-P3, GIZ-R5, MUZ-R13.1,
# MUZ-PREC01-R1, MUZ-R10a). Anchored to the start of a heading cell.
_IDENTIFIER_RE = re.compile(r"^([A-Z]{2,6}(?:-[A-Za-z0-9]+)+)(?:\s|$)")

# Rule-type letter (after the chapter code) -> corpus provision kind.
_KIND_BY_TYPE_LETTER: dict[str, str] = {
    "O": "objective",
    "P": "policy",
    "R": "rule",
    "S": "standard",
}

# HTML block-level tags whose boundaries become line breaks. Inline tags (a,
# span, b, sup, ...) contribute no separator, so glossary-term links keep the
# source's own spacing ("trade supply retail, a wholesaler", not " , a ").
_BLOCK_TAGS = frozenset(
    {
        "p", "div", "li", "ol", "ul", "table", "thead", "tbody", "tr", "td",
        "th", "br", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
    }
)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DistrictPlanChapter:
    """One IsoPlan chapter/zone payload declared by an extraction manifest."""

    code: str
    name: str
    url: str
    section_id: str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> DistrictPlanChapter:
        code = str(row["code"]).strip()
        if not code:
            raise ValueError("district plan chapter requires a non-empty code")
        section_raw = row.get("section_id")
        return cls(
            code=code,
            name=str(row.get("name", code)).strip(),
            url=str(row["url"]).strip(),
            section_id=str(section_raw).strip() if section_raw is not None else None,
        )


@dataclass(frozen=True)
class DistrictPlanManifest:
    """Declares one operative district plan revision and its chapter endpoints."""

    jurisdiction: str
    territorial_authority: str
    territorial_authority_name: str
    plan_version: str
    plan_title: str
    plan_status: str
    revision: str
    as_at: str
    base_url: str
    chapters: tuple[DistrictPlanChapter, ...]
    revision_index_url: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> DistrictPlanManifest:
        chapters = tuple(
            DistrictPlanChapter.from_mapping(row)
            for row in data.get("chapters", [])
            if isinstance(row, Mapping)
        )
        if not chapters:
            raise ValueError("district plan manifest requires at least one chapter")
        revision_index = data.get("revision_index")
        revision_index_url = None
        if isinstance(revision_index, Mapping):
            revision_index_url = _optional_str(revision_index.get("url"))
        elif isinstance(revision_index, str):
            revision_index_url = _optional_str(revision_index)
        return cls(
            jurisdiction=str(data.get("jurisdiction", "nz")).strip(),
            territorial_authority=str(data["territorial_authority"]).strip(),
            territorial_authority_name=str(
                data.get("territorial_authority_name", data["territorial_authority"])
            ).strip(),
            plan_version=str(data["plan_version"]).strip(),
            plan_title=str(data.get("plan_title", "")).strip(),
            plan_status=str(data.get("plan_status", "operative")).strip(),
            revision=str(data.get("revision", "")).strip(),
            as_at=str(data.get("as_at", "")).strip(),
            base_url=str(data.get("base_url", "")).strip(),
            chapters=chapters,
            revision_index_url=revision_index_url,
        )

    @classmethod
    def load(cls, path: str | Path) -> DistrictPlanManifest:
        data = yaml.safe_load(Path(path).read_text())
        if not isinstance(data, Mapping):
            raise ValueError("district plan manifest must be a YAML mapping")
        return cls.from_mapping(data)


# ---------------------------------------------------------------------------
# Parsed structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ParsedProvision:
    """One identifier-anchored provision parsed from an IsoPlan chapter payload."""

    identifier: str
    chapter_token: str
    provision_token: str
    kind: str
    heading: str | None
    body: str
    plan_section: str | None
    precinct: str | None
    ordinal: int | None
    source_rule_ids: tuple[str, ...]


@dataclass(frozen=True)
class ParsedDefinition:
    """One glossary definition parsed from the IsoPlan revision index."""

    term: str
    slug: str
    body: str
    group: str | None
    source_definition_id: str | None


@dataclass(frozen=True)
class _ChapterPayload:
    """A fetched chapter payload plus its provenance."""

    chapter: DistrictPlanChapter
    raw_bytes: bytes
    sha256: str
    provisions: tuple[ParsedProvision, ...]


@dataclass(frozen=True)
class DistrictPlanExtractReport:
    """Report for one district-plan extraction run."""

    jurisdiction: str
    territorial_authority: str
    document_class: str
    plan_version: str
    revision: str
    as_at: str
    chapter_count: int
    definition_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


DistrictPlanFetcher = Callable[[str], bytes]


# ---------------------------------------------------------------------------
# Citation-path shape
# ---------------------------------------------------------------------------
def district_plan_citation_path(
    *,
    jurisdiction: str,
    territorial_authority: str,
    plan_version: str,
    chapter: str | None = None,
    provision: str | None = None,
    document_class: str = DISTRICT_PLAN_DOCUMENT_CLASS,
) -> str:
    """Return the canonical council-instrument citation path.

    Shape: ``<jurisdiction>/<document_class>/<ta>/<plan-version>[/<chapter>[/<provision>]]``
    e.g. ``nz/district-plan/wellington-city/2024/muz/r13``. ``chapter``/``provision``
    are appended only when given, so the plan root and chapter-root paths share the
    same builder.
    """
    segments = [
        jurisdiction,
        document_class,
        territorial_authority,
        plan_version,
    ]
    if chapter:
        segments.append(chapter)
        if provision:
            segments.append(provision)
    elif provision:
        raise ValueError("provision requires a chapter")
    return "/".join(_path_segment(segment) for segment in segments)


def _path_segment(value: str) -> str:
    cleaned = value.strip().strip("/").lower()
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"[^0-9a-z.\-]+", "-", cleaned).strip("-")
    if not cleaned:
        raise ValueError(f"empty district-plan path segment from {value!r}")
    return cleaned


# ---------------------------------------------------------------------------
# Identifier helpers
# ---------------------------------------------------------------------------
def parse_rule_identifier(cell_text: str) -> str | None:
    """Return the leading plan rule identifier of a heading cell, if any.

    The source occasionally splits an identifier with a stray space ("M UZ-S11");
    a whitespace-stripped retry recovers it.
    """
    match = _IDENTIFIER_RE.match(cell_text)
    if match:
        return match.group(1)
    match = _IDENTIFIER_RE.match(cell_text.replace(" ", ""))
    return match.group(1) if match else None


def chapter_token_for_identifier(identifier: str) -> str:
    """Return the chapter/zone token of an identifier (segment before first '-')."""
    return identifier.split("-", 1)[0].lower()


def provision_token_for_identifier(identifier: str) -> str:
    """Return the provision token of an identifier (everything after the chapter)."""
    _, _, rest = identifier.partition("-")
    return rest.lower()


def classify_provision_kind(identifier: str) -> str:
    """Classify a provision by its rule-type letter (R rule, P policy, ...).

    The type token is a single letter followed by a number (R13, P3, O1, S1); a
    multi-letter precinct code (PREC01) is not a type and is skipped so
    ``MUZ-PREC01-R1`` classifies on its ``R1`` leaf.
    """
    for segment in identifier.split("-")[1:]:
        letter_match = re.match(r"([A-Za-z])\d", segment)
        if letter_match:
            letter = letter_match.group(1).upper()
            if letter in _KIND_BY_TYPE_LETTER:
                return _KIND_BY_TYPE_LETTER[letter]
    return "provision"


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------
class _IsoPlanTextExtractor(HTMLParser):
    """Collect text, breaking only on block boundaries so inline spacing holds."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def render_isoplan_text(html: str | None) -> str:
    """Render IsoPlan ``ruleText``/``glossaryText`` HTML to normalized plan text.

    Block boundaries become line breaks; inline element boundaries add nothing, so
    glossary-term links keep the source's punctuation spacing. Whitespace is
    collapsed per line and spaces before ``, . ; :`` are dropped (an inline-link
    artifact), yielding text that matches the operative provision verbatim.
    """
    parser = _IsoPlanTextExtractor()
    parser.feed(html or "")
    parser.close()
    raw = parser.text().replace("\xa0", " ")
    lines: list[str] = []
    for line in raw.split("\n"):
        collapsed = re.sub(r"[ \t]+", " ", line).strip()
        collapsed = re.sub(r"\s+([,.;:])", r"\1", collapsed)
        if collapsed:
            lines.append(collapsed)
    return "\n".join(lines)


def _cell_texts(html: str | None) -> list[str]:
    """Render each top-level ``<td>`` cell of an IsoPlan row to text."""
    return [
        render_isoplan_text(f"<x>{cell}</x>")
        for cell in re.findall(r"<td[^>]*>(.*?)</td>", html or "", re.S)
    ]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_isoplan_chapter(
    payload: Mapping[str, Any] | bytes | str,
    *,
    chapter_code: str,
) -> tuple[ParsedProvision, ...]:
    """Parse an IsoPlan chapter payload into identifier-anchored provisions.

    Walks the ``rules`` array in order. A row whose first cell carries a rule
    identifier opens a provision; following identifier-less content rows extend its
    body; a structural section divider (any non-content ``ruleTextSize``) closes the
    open provision and updates the section/precinct context. Content before the
    first provision is chapter narrative and is not emitted (it has no citable
    identifier).
    """
    data = _as_mapping(payload)
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ValueError("IsoPlan chapter payload must carry a 'rules' list")

    chapter_token = chapter_code.strip().lower()
    provisions: list[ParsedProvision] = []
    seen_tokens: set[str] = set()
    plan_section: str | None = None
    open_identifier: str | None = None
    heading: str | None = None
    body_lines: list[str] = []
    source_rule_ids: list[str] = []
    ordinal = 0

    def flush() -> None:
        nonlocal open_identifier, heading, body_lines, source_rule_ids
        if open_identifier is None:
            return
        provision_token = provision_token_for_identifier(open_identifier)
        if provision_token and provision_token not in seen_tokens:
            seen_tokens.add(provision_token)
            provisions.append(
                ParsedProvision(
                    identifier=open_identifier,
                    chapter_token=chapter_token,
                    provision_token=provision_token,
                    kind=classify_provision_kind(open_identifier),
                    heading=heading,
                    body="\n".join(body_lines).strip(),
                    plan_section=plan_section,
                    precinct=_precinct_of(open_identifier),
                    ordinal=ordinal,
                    source_rule_ids=tuple(source_rule_ids),
                )
            )
        open_identifier = None
        heading = None
        body_lines = []
        source_rule_ids = []

    for row in rules:
        if not isinstance(row, Mapping):
            continue
        rule_text = row.get("ruleText")
        size = row.get("ruleTextSize")
        cells = _cell_texts(rule_text if isinstance(rule_text, str) else None)
        first_cell = cells[0] if cells else render_isoplan_text(
            rule_text if isinstance(rule_text, str) else None
        )
        identifier = parse_rule_identifier(first_cell)
        rule_id = row.get("ruleId")
        rule_id_text = str(rule_id) if rule_id is not None else None

        if identifier is not None:
            flush()
            ordinal += 1
            open_identifier = identifier
            own = cells[1:] if len(cells) >= 2 else _identifier_stripped(first_cell, identifier)
            heading = _first_line(own)
            body_lines = [line for line in own if line]
            source_rule_ids = [rule_id_text] if rule_id_text else []
        elif size not in _CONTENT_SIZES:
            flush()
            section = render_isoplan_text(rule_text if isinstance(rule_text, str) else None)
            plan_section = section or plan_section
        elif open_identifier is not None:
            body_text = render_isoplan_text(rule_text if isinstance(rule_text, str) else None)
            if body_text:
                body_lines.extend(body_text.split("\n"))
            if rule_id_text:
                source_rule_ids.append(rule_id_text)

    flush()
    return tuple(provisions)


def parse_isoplan_definitions(
    payload: Mapping[str, Any] | bytes | str,
) -> tuple[ParsedDefinition, ...]:
    """Parse the ``definitions`` glossary from an IsoPlan revision index."""
    data = _as_mapping(payload)
    raw = data.get("definitions")
    if not isinstance(raw, list):
        return ()
    definitions: list[ParsedDefinition] = []
    seen_slugs: set[str] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        term = str(entry.get("glossaryHeading", "")).strip()
        body = render_isoplan_text(str(entry.get("glossaryText", "")) or None)
        if not term or not body:
            continue
        slug = _slug_token(term)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        definition_id = entry.get("id")
        group = entry.get("group")
        definitions.append(
            ParsedDefinition(
                term=term,
                slug=slug,
                body=body,
                group=str(group).strip() if group not in (None, "") else None,
                source_definition_id=(
                    str(definition_id) if definition_id not in (None, "") else None
                ),
            )
        )
    return tuple(definitions)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_nz_district_plan(
    store: CorpusArtifactStore,
    *,
    manifest_path: str | Path,
    version: str,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    retrieved_at: str | None = None,
    only_chapter: str | None = None,
    limit: int | None = None,
    fetcher: DistrictPlanFetcher | None = None,
    progress_stream: TextIO | None = None,
) -> DistrictPlanExtractReport:
    """Fetch IsoPlan district-plan payloads and write standard corpus artifacts.

    ``fetcher`` maps a URL to raw bytes; the offline test path injects a fixture
    fetcher, and the default fetches the live IsoPlan endpoints. All fetches and
    validation happen before any store write (phase A), mirroring ``eli.py``.
    """
    manifest = DistrictPlanManifest.load(manifest_path)
    get = fetcher or _default_fetcher(manifest.base_url)
    retrieval_stamp = retrieved_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    source_as_of_text = source_as_of or _date_of_retrieval(retrieval_stamp)
    expression_date_text = _expression_date_text(expression_date, manifest.as_at, source_as_of_text)

    selected_chapters = tuple(
        chapter
        for chapter in manifest.chapters
        if only_chapter in {None, chapter.code, chapter.code.lower()}
    )
    if limit is not None:
        selected_chapters = selected_chapters[:limit]
    if not selected_chapters:
        raise ValueError("no district-plan chapters selected")

    # Phase A: fetch, parse and validate everything before writing.
    chapter_payloads: list[_ChapterPayload] = []
    for chapter in selected_chapters:
        if progress_stream:
            print(f"extracting {manifest.territorial_authority}/{chapter.code}", file=progress_stream)
        raw_bytes = get(chapter.url)
        provisions = parse_isoplan_chapter(raw_bytes, chapter_code=chapter.code)
        if not provisions:
            raise ValueError(f"IsoPlan chapter {chapter.code} produced no provisions")
        chapter_payloads.append(
            _ChapterPayload(
                chapter=chapter,
                raw_bytes=raw_bytes,
                sha256=_sha256(raw_bytes),
                provisions=provisions,
            )
        )

    definitions: tuple[ParsedDefinition, ...] = ()
    revision_bytes: bytes | None = None
    revision_sha: str | None = None
    if manifest.revision_index_url and only_chapter is None:
        revision_bytes = get(manifest.revision_index_url)
        revision_sha = _sha256(revision_bytes)
        definitions = parse_isoplan_definitions(revision_bytes)

    # Phase B: writes.
    records: list[ProvisionRecord] = []
    inventory: list[SourceInventoryItem] = []
    source_paths: list[Path] = []
    document_class = DISTRICT_PLAN_DOCUMENT_CLASS
    jurisdiction = manifest.jurisdiction

    plan_root_path = district_plan_citation_path(
        jurisdiction=jurisdiction,
        territorial_authority=manifest.territorial_authority,
        plan_version=manifest.plan_version,
    )
    root_source_key = (
        _source_key(version, document_class, _revision_source_name(manifest))
        if revision_bytes is not None
        else None
    )
    plan_root = _plan_root_record(
        manifest,
        citation_path=plan_root_path,
        version=version,
        retrieved_at=retrieval_stamp,
        source_as_of=source_as_of_text,
        expression_date=expression_date_text,
        source_key=root_source_key,
    )
    records.append(plan_root)
    inventory.append(
        _inventory_for(
            plan_root,
            source_format=ISOPLAN_REVISION_SOURCE_FORMAT if revision_bytes is not None else ISOPLAN_SOURCE_FORMAT,
            sha256=revision_sha,
        )
    )

    for payload in chapter_payloads:
        chapter = payload.chapter
        relative_name = _chapter_source_name(manifest, chapter)
        source_key = _source_key(version, document_class, relative_name)
        store.write_bytes(
            store.source_path(jurisdiction, document_class, version, relative_name),
            payload.raw_bytes,
        )
        source_paths.append(store.source_path(jurisdiction, document_class, version, relative_name))

        chapter_path = district_plan_citation_path(
            jurisdiction=jurisdiction,
            territorial_authority=manifest.territorial_authority,
            plan_version=manifest.plan_version,
            chapter=payload.provisions[0].chapter_token,
        )
        chapter_record = _chapter_record(
            manifest,
            chapter,
            citation_path=chapter_path,
            parent_path=plan_root_path,
            version=version,
            source_key=source_key,
            sha256=payload.sha256,
            retrieved_at=retrieval_stamp,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )
        records.append(chapter_record)
        inventory.append(
            _inventory_for(chapter_record, source_format=ISOPLAN_SOURCE_FORMAT, sha256=payload.sha256)
        )

        for provision in payload.provisions:
            citation_path = district_plan_citation_path(
                jurisdiction=jurisdiction,
                territorial_authority=manifest.territorial_authority,
                plan_version=manifest.plan_version,
                chapter=provision.chapter_token,
                provision=provision.provision_token,
            )
            record = _provision_record(
                manifest,
                chapter,
                provision,
                citation_path=citation_path,
                parent_path=chapter_path,
                version=version,
                source_key=source_key,
                sha256=payload.sha256,
                retrieved_at=retrieval_stamp,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
            )
            records.append(record)
            inventory.append(
                _inventory_for(record, source_format=ISOPLAN_SOURCE_FORMAT, sha256=payload.sha256)
            )

    if definitions and revision_bytes is not None:
        relative_name = _revision_source_name(manifest)
        source_key = _source_key(version, document_class, relative_name)
        store.write_bytes(
            store.source_path(jurisdiction, document_class, version, relative_name),
            revision_bytes,
        )
        source_paths.append(store.source_path(jurisdiction, document_class, version, relative_name))
        definitions_path = district_plan_citation_path(
            jurisdiction=jurisdiction,
            territorial_authority=manifest.territorial_authority,
            plan_version=manifest.plan_version,
            chapter=DISTRICT_PLAN_DEFINITIONS_CHAPTER,
        )
        definitions_chapter = _definitions_chapter_record(
            manifest,
            citation_path=definitions_path,
            parent_path=plan_root_path,
            version=version,
            source_key=source_key,
            sha256=revision_sha,
            retrieved_at=retrieval_stamp,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )
        records.append(definitions_chapter)
        inventory.append(
            _inventory_for(
                definitions_chapter, source_format=ISOPLAN_REVISION_SOURCE_FORMAT, sha256=revision_sha
            )
        )
        for ordinal, definition in enumerate(definitions, 1):
            citation_path = district_plan_citation_path(
                jurisdiction=jurisdiction,
                territorial_authority=manifest.territorial_authority,
                plan_version=manifest.plan_version,
                chapter=DISTRICT_PLAN_DEFINITIONS_CHAPTER,
                provision=definition.slug,
            )
            record = _definition_record(
                manifest,
                definition,
                citation_path=citation_path,
                parent_path=definitions_path,
                version=version,
                source_key=source_key,
                sha256=revision_sha,
                retrieved_at=retrieval_stamp,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                ordinal=ordinal,
            )
            records.append(record)
            inventory.append(
                _inventory_for(
                    record, source_format=ISOPLAN_REVISION_SOURCE_FORMAT, sha256=revision_sha
                )
            )

    deduped_records = _dedupe_records(records)
    deduped_inventory = _dedupe_inventory(inventory)
    inventory_path = store.inventory_path(jurisdiction, document_class, version)
    provisions_path = store.provisions_path(jurisdiction, document_class, version)
    coverage_path = store.coverage_path(jurisdiction, document_class, version)
    store.write_inventory(inventory_path, deduped_inventory)
    store.write_provisions(provisions_path, deduped_records)
    coverage = compare_provision_coverage(
        deduped_inventory,
        deduped_records,
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=version,
    )
    store.write_json(coverage_path, coverage.to_mapping())

    return DistrictPlanExtractReport(
        jurisdiction=jurisdiction,
        territorial_authority=manifest.territorial_authority,
        document_class=document_class,
        plan_version=manifest.plan_version,
        revision=manifest.revision,
        as_at=manifest.as_at,
        chapter_count=len(chapter_payloads),
        definition_count=len(definitions),
        provisions_written=len(deduped_records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------
def _plan_root_record(
    manifest: DistrictPlanManifest,
    *,
    citation_path: str,
    version: str,
    retrieved_at: str,
    source_as_of: str,
    expression_date: str,
    source_key: str | None = None,
) -> ProvisionRecord:
    label = manifest.plan_title or f"{manifest.territorial_authority_name} District Plan"
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=manifest.jurisdiction,
        document_class=DISTRICT_PLAN_DOCUMENT_CLASS,
        citation_path=citation_path,
        citation_label=label,
        heading=label,
        body=None,
        version=version,
        source_url=manifest.base_url or None,
        source_path=source_key,
        source_id=manifest.base_url or None,
        source_format=ISOPLAN_SOURCE_FORMAT,
        source_document_id=_plan_document_id(manifest),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=None,
        parent_id=None,
        level=1,
        ordinal=1,
        kind="district-plan",
        legal_identifier=label,
        identifiers=_plan_identifiers(manifest),
        metadata=_plan_metadata(manifest, retrieved_at=retrieved_at),
    )


def _chapter_record(
    manifest: DistrictPlanManifest,
    chapter: DistrictPlanChapter,
    *,
    citation_path: str,
    parent_path: str,
    version: str,
    source_key: str,
    sha256: str,
    retrieved_at: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    label = f"{chapter.name} ({chapter.code})"
    metadata = _plan_metadata(manifest, retrieved_at=retrieved_at)
    metadata.update(
        {
            "chapter_code": chapter.code,
            "chapter_name": chapter.name,
            "source_sha256": sha256,
            "source_url": chapter.url,
        }
    )
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=manifest.jurisdiction,
        document_class=DISTRICT_PLAN_DOCUMENT_CLASS,
        citation_path=citation_path,
        citation_label=label,
        heading=chapter.name,
        body=None,
        version=version,
        source_url=chapter.url,
        source_path=source_key,
        source_id=chapter.url,
        source_format=ISOPLAN_SOURCE_FORMAT,
        source_document_id=_plan_document_id(manifest),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=2,
        ordinal=None,
        kind="chapter",
        legal_identifier=chapter.code,
        identifiers=_chapter_identifiers(manifest, chapter),
        metadata=metadata,
    )


def _provision_record(
    manifest: DistrictPlanManifest,
    chapter: DistrictPlanChapter,
    provision: ParsedProvision,
    *,
    citation_path: str,
    parent_path: str,
    version: str,
    source_key: str,
    sha256: str,
    retrieved_at: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    label = _provision_label(chapter, provision)
    metadata = _plan_metadata(manifest, retrieved_at=retrieved_at)
    metadata.update(
        {
            "chapter_code": chapter.code,
            "chapter_name": chapter.name,
            "plan_identifier": provision.identifier,
            "plan_section": provision.plan_section,
            "precinct": provision.precinct,
            "source_sha256": sha256,
            "source_url": chapter.url,
            "source_rule_ids": list(provision.source_rule_ids),
        }
    )
    identifiers = _chapter_identifiers(manifest, chapter)
    identifiers.update({"district-plan:identifier": provision.identifier})
    if provision.source_rule_ids:
        identifiers["eplan:rule-id"] = provision.source_rule_ids[0]
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=manifest.jurisdiction,
        document_class=DISTRICT_PLAN_DOCUMENT_CLASS,
        citation_path=citation_path,
        citation_label=label,
        heading=provision.heading,
        body=provision.body or None,
        version=version,
        source_url=_provision_source_url(chapter, provision),
        source_path=source_key,
        source_id=_provision_source_url(chapter, provision),
        source_format=ISOPLAN_SOURCE_FORMAT,
        source_document_id=_plan_document_id(manifest),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=3,
        ordinal=provision.ordinal,
        kind=provision.kind,
        legal_identifier=provision.identifier,
        identifiers=identifiers,
        metadata=metadata,
    )


def _definitions_chapter_record(
    manifest: DistrictPlanManifest,
    *,
    citation_path: str,
    parent_path: str,
    version: str,
    source_key: str,
    sha256: str | None,
    retrieved_at: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    metadata = _plan_metadata(manifest, retrieved_at=retrieved_at)
    metadata.update({"chapter_code": "definitions", "source_sha256": sha256})
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=manifest.jurisdiction,
        document_class=DISTRICT_PLAN_DOCUMENT_CLASS,
        citation_path=citation_path,
        citation_label=f"{manifest.plan_title} Definitions",
        heading="Definitions",
        body=None,
        version=version,
        source_url=manifest.revision_index_url,
        source_path=source_key,
        source_id=manifest.revision_index_url,
        source_format=ISOPLAN_REVISION_SOURCE_FORMAT,
        source_document_id=_plan_document_id(manifest),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=2,
        ordinal=None,
        kind="chapter",
        legal_identifier="Definitions",
        identifiers=_plan_identifiers(manifest),
        metadata=metadata,
    )


def _definition_record(
    manifest: DistrictPlanManifest,
    definition: ParsedDefinition,
    *,
    citation_path: str,
    parent_path: str,
    version: str,
    source_key: str,
    sha256: str | None,
    retrieved_at: str,
    source_as_of: str,
    expression_date: str,
    ordinal: int,
) -> ProvisionRecord:
    metadata = _plan_metadata(manifest, retrieved_at=retrieved_at)
    metadata.update(
        {
            "chapter_code": "definitions",
            "glossary_term": definition.term,
            "glossary_group": definition.group,
            "source_sha256": sha256,
            "source_url": manifest.revision_index_url,
        }
    )
    identifiers = _plan_identifiers(manifest)
    identifiers["district-plan:definition"] = definition.term
    if definition.source_definition_id:
        identifiers["eplan:definition-id"] = definition.source_definition_id
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=manifest.jurisdiction,
        document_class=DISTRICT_PLAN_DOCUMENT_CLASS,
        citation_path=citation_path,
        citation_label=definition.term,
        heading=definition.term,
        body=definition.body or None,
        version=version,
        source_url=manifest.revision_index_url,
        source_path=source_key,
        source_id=manifest.revision_index_url,
        source_format=ISOPLAN_REVISION_SOURCE_FORMAT,
        source_document_id=_plan_document_id(manifest),
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=3,
        ordinal=ordinal,
        kind="definition",
        legal_identifier=definition.term,
        identifiers=identifiers,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Metadata / identifier helpers
# ---------------------------------------------------------------------------
def _plan_identifiers(manifest: DistrictPlanManifest) -> dict[str, str]:
    identifiers = {
        "district-plan:territorial-authority": manifest.territorial_authority,
        "district-plan:plan-version": manifest.plan_version,
    }
    if manifest.revision:
        identifiers["eplan:revision"] = manifest.revision
    if manifest.as_at:
        identifiers["eplan:as-at"] = manifest.as_at
    return identifiers


def _chapter_identifiers(
    manifest: DistrictPlanManifest, chapter: DistrictPlanChapter
) -> dict[str, str]:
    identifiers = _plan_identifiers(manifest)
    identifiers["district-plan:chapter"] = chapter.code
    if chapter.section_id:
        identifiers["eplan:section-id"] = chapter.section_id
    return identifiers


def _plan_metadata(manifest: DistrictPlanManifest, *, retrieved_at: str) -> dict[str, Any]:
    return {
        "territorial_authority": manifest.territorial_authority,
        "territorial_authority_name": manifest.territorial_authority_name,
        "plan_title": manifest.plan_title,
        "plan_version": manifest.plan_version,
        "plan_status": manifest.plan_status,
        "revision": manifest.revision,
        "as_at": manifest.as_at,
        "retrieved_at": retrieved_at,
        "platform": "isoplan-eplan",
    }


def _inventory_for(
    record: ProvisionRecord, *, source_format: str, sha256: str | None
) -> SourceInventoryItem:
    metadata = {
        "kind": record.kind,
        "heading": record.heading,
        "legal_identifier": record.legal_identifier,
    }
    if record.metadata and record.metadata.get("retrieved_at"):
        metadata["retrieved_at"] = record.metadata["retrieved_at"]
    return SourceInventoryItem(
        citation_path=record.citation_path,
        source_url=record.source_url,
        source_path=record.source_path,
        source_format=source_format,
        sha256=sha256,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def _default_fetcher(base_url: str) -> DistrictPlanFetcher:
    """Build the live IsoPlan fetcher (lazy httpx import; browser-shaped headers)."""

    def fetch(url: str) -> bytes:
        import httpx

        headers = {
            "User-Agent": ISOPLAN_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
        if base_url:
            headers["Referer"] = base_url
        response = httpx.get(url, headers=headers, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
        return response.content

    return fetch


def _as_mapping(payload: Mapping[str, Any] | bytes | str) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, Mapping):
        raise ValueError("IsoPlan payload must decode to a JSON object")
    return data


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _slug_token(value: str) -> str:
    token = re.sub(r"[^0-9A-Za-z]+", "-", value.strip()).strip("-").lower()
    return token or "unnamed"


def _first_line(lines: Sequence[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _identifier_stripped(cell: str, identifier: str) -> list[str]:
    remainder = cell[len(identifier):] if cell.startswith(identifier) else cell
    return [line for line in remainder.split("\n") if line.strip()]


def _precinct_of(identifier: str) -> str | None:
    match = re.search(r"(PREC[0-9A-Za-z]*)", identifier)
    return match.group(1) if match else None


def _plan_document_id(manifest: DistrictPlanManifest) -> str:
    return f"{manifest.territorial_authority}/{manifest.plan_version}"


def _chapter_source_name(manifest: DistrictPlanManifest, chapter: DistrictPlanChapter) -> str:
    token = chapter.section_id or _slug_token(chapter.code)
    return (
        f"eplan/{safe_segment(manifest.territorial_authority)}/"
        f"{safe_segment(manifest.plan_version)}/{safe_segment(chapter.code.lower())}-{token}.json"
    )


def _revision_source_name(manifest: DistrictPlanManifest) -> str:
    revision = manifest.revision or "revision"
    return (
        f"eplan/{safe_segment(manifest.territorial_authority)}/"
        f"{safe_segment(manifest.plan_version)}/revision-{safe_segment(revision)}.json"
    )


def _source_key(version: str, document_class: str, relative_name: str) -> str:
    return f"sources/nz/{document_class}/{version}/{relative_name}"


def _provision_label(chapter: DistrictPlanChapter, provision: ParsedProvision) -> str:
    if provision.heading:
        return f"{provision.identifier} {provision.heading}"
    return provision.identifier


def _provision_source_url(chapter: DistrictPlanChapter, provision: ParsedProvision) -> str:
    return chapter.url


def _expression_date_text(
    value: date | str | None, as_at: str, fallback: str
) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if value:
        return str(value)
    iso = _isoplan_date_to_iso(as_at)
    return iso or fallback


def _isoplan_date_to_iso(as_at: str) -> str | None:
    token = as_at.strip()
    if not token:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(token, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _date_of_retrieval(retrieved_at: str) -> str:
    return retrieved_at.split("T", 1)[0]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe_records(records: Iterable[ProvisionRecord]) -> tuple[ProvisionRecord, ...]:
    by_path: dict[str, ProvisionRecord] = {}
    duplicates: set[str] = set()
    for record in records:
        if record.citation_path in by_path:
            duplicates.add(record.citation_path)
            continue
        by_path[record.citation_path] = record
    if duplicates:
        raise ValueError(f"duplicate provision citation paths: {', '.join(sorted(duplicates))}")
    return tuple(by_path[path] for path in sorted(by_path))


def _dedupe_inventory(items: Iterable[SourceInventoryItem]) -> tuple[SourceInventoryItem, ...]:
    by_path: dict[str, SourceInventoryItem] = {}
    duplicates: set[str] = set()
    for item in items:
        if item.citation_path in by_path:
            duplicates.add(item.citation_path)
            continue
        by_path[item.citation_path] = item
    if duplicates:
        raise ValueError(f"duplicate inventory citation paths: {', '.join(sorted(duplicates))}")
    return tuple(by_path[path] for path in sorted(by_path))
