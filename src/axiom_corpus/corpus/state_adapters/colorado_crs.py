"""Colorado Revised Statutes source-first corpus adapter.

Snapshots one official OLLS uncertified-printout title HTM file from
https://olls.info/crs/ (the "Download C.R.S. Titles" portal published by the
Office of Legislative Legal Services) and extracts section-level provisions.

The OLLS HTM files are WordPerfect exports: flat sequences of
``<P><SPAN STYLE="font-family: Public Sans">`` paragraphs with no charset
declaration (windows-1252 bytes in practice). Section headings render as
``<STRONG>39-22-104.  Heading text. </STRONG>`` prefixes inside a paragraph;
``ARTICLE N`` and ``PART N`` container headings render as standalone
``<STRONG>`` paragraphs; amendment history renders as ``Source:`` paragraphs
after each section; case annotations render under ``ANNOTATION`` headings and
are excluded from provision bodies (they are annotations, not statute).

Citation paths follow the shape the existing ``us-co`` statute encodings
already cite (``us-co/statute/39/39-22-104``): sections sit directly under the
title node so the encoder's ``corpus_citation_path`` grounding matches without
migration.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

COLORADO_CRS_BASE_URL = "https://olls.info/crs/"
COLORADO_CRS_TITLE_SOURCE_FORMAT = "colorado-crs-olls-title-htm"
COLORADO_CRS_USER_AGENT = "axiom-corpus/0.1 (contact@axiom-foundation.org)"

_SECTION_HEADING_RE = re.compile(
    r"^(?P<section>\d+(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?)\.\s+(?P<heading>.+?)\s*$",
    re.S,
)
_ARTICLE_HEADING_RE = re.compile(r"^ARTICLE\s+(?P<article>\d+(?:\.\d+)?)$")
_REPEALED_RANGE_HEADING_RE = re.compile(
    r"^(?P<start>\d+(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?)\s+to\s+"
    r"(?P<end>\d+(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?)\.\s*\(\s*Repealed\s*\)\s*$"
)
_PART_HEADING_RE = re.compile(r"^PART\s+(?P<part>\d+)$")
_REPEALED_HEADING_RE = re.compile(r"\(\s*Repealed\s*\)", re.I)
_SOURCE_PARAGRAPH_RE = re.compile(r"^Source:\s*(?P<history>.*)$", re.S)
_NOTE_PARAGRAPH_RE = re.compile(
    r"^(?P<label>Editor's note|Cross references|Law reviews)\s*:?\s*(?P<note>.*)$",
    re.I | re.S,
)
_ANNOTATION_HEADING_RE = re.compile(r"^ANNOTATIONS?$")


@dataclass(frozen=True)
class _RecordedSource:
    source_url: str
    source_path: str
    source_format: str
    sha256: str


@dataclass
class _ColoradoSection:
    """One parsed C.R.S. section within the selected title."""

    section: str
    heading: str
    article: str
    part_heading: str | None
    body_paragraphs: list[str] = field(default_factory=list)
    source_history: list[str] = field(default_factory=list)
    source_notes: list[str] = field(default_factory=list)
    annotation_paragraphs: int = 0
    ordinal: int = 0
    is_repealed_range: bool = False

    @property
    def repealed(self) -> bool:
        return bool(_REPEALED_HEADING_RE.search(self.heading)) or any(
            _REPEALED_HEADING_RE.search(paragraph) for paragraph in self.body_paragraphs[:1]
        )

    @property
    def body(self) -> str:
        return "\n".join(self.body_paragraphs).strip()


def _store_relative_path(store: CorpusArtifactStore, path: Path) -> str:
    try:
        return path.relative_to(store.root).as_posix()
    except ValueError:
        return path.as_posix()


def _decode_olls_html(data: bytes) -> str:
    """Decode an OLLS WordPerfect HTM export (windows-1252 in practice)."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _normalize_text(value: str) -> str:
    value = value.replace(" ", " ")
    value = re.sub(r"[ \t]*\n[ \t]*", "\n", value)
    value = re.sub(r"\n{2,}", "\n", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def _paragraph_text(tag: Any) -> str:
    text = tag.get_text()
    text = text.replace(" ", " ")
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _paragraph_body_text(tag: Any) -> str:
    """Paragraph text with the original line shape kept for subsections."""
    text = tag.get_text()
    text = text.replace(" ", " ")
    return _normalize_text(text)


def parse_colorado_crs_title(
    html: str | bytes,
    *,
    title: str,
    only_article: str | None = None,
) -> tuple[tuple[_ColoradoSection, ...], str]:
    """Parse one OLLS C.R.S. title HTM export into sections.

    Returns the parsed sections (optionally scoped to one article) and the
    document heading text used for the title container provision.
    """
    decoded = _decode_olls_html(html) if isinstance(html, bytes) else html
    soup = BeautifulSoup(decoded, "lxml")
    heading_tag = soup.find("h1")
    document_heading = _paragraph_text(heading_tag) if heading_tag else f"C.R.S. Title {title}"

    sections: list[_ColoradoSection] = []
    current: _ColoradoSection | None = None
    current_part_heading: str | None = None
    pending_part_number: str | None = None
    in_annotation = False
    # Once a section's post-statute annex starts (Source:, Editor's note:,
    # Cross references:, Law reviews:), statutory text never resumes before
    # the next section/article/part boundary in the OLLS layout. Unlabeled
    # continuation paragraphs belong to the active annex bucket, NOT the body
    # (multi-paragraph editor's-note and cross-reference blocks are common).
    annex_bucket: str | None = None
    ordinal = 0
    # Annex paragraphs printed after an article/part boundary but before a
    # ranged repealed heading belong to that upcoming ranged record.
    pending_prefix_history: list[str] = []
    pending_prefix_notes: list[str] = []
    pending_prefix_bucket: str | None = None

    paragraphs = soup.find_all("p")

    def _next_nonempty_text(start_index: int) -> str:
        for later in paragraphs[start_index + 1 :]:
            later_text = _paragraph_text(later)
            if later_text:
                return later_text
        return ""

    for index, paragraph in enumerate(paragraphs):
        text = _paragraph_text(paragraph)
        if not text:
            continue

        article_match = _ARTICLE_HEADING_RE.match(text)
        if article_match is not None:
            current_part_heading = None
            pending_part_number = None
            in_annotation = False
            annex_bucket = None
            current = None
            pending_prefix_history = []
            pending_prefix_notes = []
            pending_prefix_bucket = None
            continue

        part_match = _PART_HEADING_RE.match(text)
        if part_match is not None:
            pending_part_number = part_match.group("part")
            current_part_heading = f"PART {pending_part_number}"
            in_annotation = False
            annex_bucket = None
            current = None
            continue

        if pending_part_number is not None:
            # The paragraph after "PART N" is its caption line.
            current_part_heading = f"PART {pending_part_number} - {text}"
            pending_part_number = None
            continue

        if _ANNOTATION_HEADING_RE.match(text):
            in_annotation = True
            annex_bucket = None
            if current is not None:
                current.annotation_paragraphs += 1
            continue

        range_match = _REPEALED_RANGE_HEADING_RE.match(text)
        if range_match is not None:
            # Fully repealed articles appear only as a ranged pseudo-section
            # ("39-25-101 to 39-25-120. (Repealed)"). Record one empty repealed
            # section under the range start so the article is represented and
            # the following Source:/Editor's note annex has an owner.
            range_start = range_match.group("start")
            if range_start.split("-", 1)[0] == title:
                in_annotation = False
                annex_bucket = None
                ordinal += 1
                current = _ColoradoSection(
                    section=range_start,
                    heading=f"{range_start} to {range_match.group('end')}. (Repealed)",
                    article=range_start.split("-")[1],
                    part_heading=current_part_heading,
                    ordinal=ordinal,
                    is_repealed_range=True,
                )
                current.source_history.extend(pending_prefix_history)
                current.source_notes.extend(pending_prefix_notes)
                pending_prefix_history = []
                pending_prefix_notes = []
                pending_prefix_bucket = None
                sections.append(current)
                continue

        section_match = _SECTION_HEADING_RE.match(text)
        strong = paragraph.find("strong")
        strong_text = _paragraph_text(strong) if strong is not None else ""
        if section_match is not None and strong_text.startswith(section_match.group("section")):
            section_number = section_match.group("section")
            section_title_part = section_number.split("-", 1)[0]
            if section_title_part != title:
                # Cross-title stray (should not happen inside one title file).
                continue
            in_annotation = False
            annex_bucket = None
            ordinal += 1
            heading_and_body = section_match.group("heading")
            heading_text = strong_text[len(section_number) :].lstrip(". ").strip()
            body_remainder = heading_and_body[len(heading_text) :].strip()
            pending_prefix_history = []
            pending_prefix_notes = []
            pending_prefix_bucket = None
            current = _ColoradoSection(
                section=section_number,
                heading=heading_text.rstrip("."),
                article=section_number.split("-")[1],
                part_heading=current_part_heading,
                ordinal=ordinal,
            )
            if body_remainder:
                current.body_paragraphs.append(body_remainder)
            sections.append(current)
            continue

        if current is None or in_annotation:
            if current is not None and in_annotation:
                current.annotation_paragraphs += 1
            elif current is None and not in_annotation:
                # Source:/Editor's-note material after a boundary and before a
                # ranged repealed heading — buffer it for that ranged record.
                prefix_source = _SOURCE_PARAGRAPH_RE.match(text)
                prefix_note = _NOTE_PARAGRAPH_RE.match(text)
                if prefix_source is not None:
                    history = prefix_source.group("history").strip()
                    if history:
                        pending_prefix_history.append(history)
                    pending_prefix_bucket = "history"
                elif prefix_note is not None:
                    note = f"{prefix_note.group('label')}: {prefix_note.group('note').strip()}"
                    pending_prefix_notes.append(note.strip().rstrip(":"))
                    pending_prefix_bucket = "notes"
                elif pending_prefix_bucket == "history":
                    pending_prefix_history.append(_paragraph_body_text(paragraph))
                elif pending_prefix_bucket == "notes":
                    pending_prefix_notes.append(_paragraph_body_text(paragraph))
            continue

        source_match = _SOURCE_PARAGRAPH_RE.match(text)
        if source_match is not None:
            history = source_match.group("history").strip()
            if history:
                current.source_history.append(history)
            annex_bucket = "history"
            continue

        note_match = _NOTE_PARAGRAPH_RE.match(text)
        if note_match is not None:
            note = f"{note_match.group('label')}: {note_match.group('note').strip()}"
            current.source_notes.append(note.strip().rstrip(":"))
            annex_bucket = "notes"
            continue

        if annex_bucket in ("history", "notes") and _ARTICLE_HEADING_RE.match(
            _next_nonempty_text(index)
        ):
            # TOC-style topical caption printed immediately before the next
            # ARTICLE heading (e.g. "Gift Tax" above "ARTICLE 25") — it belongs
            # to the upcoming article, not to the active section's annex.
            continue

        if annex_bucket == "history":
            current.source_history.append(_paragraph_body_text(paragraph))
            continue
        if annex_bucket == "notes":
            current.source_notes.append(_paragraph_body_text(paragraph))
            continue

        if current.is_repealed_range:
            # Ranged repealed records carry no statutory text; stray captions
            # or TOC lines before the next heading are not their body.
            continue

        current.body_paragraphs.append(_paragraph_body_text(paragraph))

    if only_article is None:
        selected = tuple(sections)
    else:
        # Accept a single article ("22") or a comma-separated list
        # ("1,1.5,26") so one manifest source can scope one bundle to many
        # articles without one-bundle-per-article collection-root growth.
        allowed = {part.strip() for part in str(only_article).split(",") if part.strip()}
        selected = tuple(section for section in sections if section.article in allowed)
    return selected, document_heading


def _download_colorado_title(
    *,
    source_url: str,
    timeout_seconds: float,
    request_attempts: int,
    request_delay_seconds: float,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(request_attempts):
        try:
            response = requests.get(
                source_url,
                timeout=timeout_seconds,
                headers={"User-Agent": COLORADO_CRS_USER_AGENT},
            )
            response.raise_for_status()
            return response.content
        except Exception as exc:  # noqa: BLE001 - retried, re-raised after attempts
            last_error = exc
            time.sleep(request_delay_seconds * (attempt + 1))
    raise ValueError(f"failed to download {source_url}: {last_error}")


def extract_colorado_revised_statutes(
    store: CorpusArtifactStore,
    *,
    version: str,
    title: str,
    edition: str,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_article: str | None = None,
    limit: int | None = None,
    download_dir: str | Path | None = None,
    base_url: str = COLORADO_CRS_BASE_URL,
    timeout_seconds: float = 120.0,
    request_attempts: int = 3,
    request_delay_seconds: float = 1.0,
) -> StateStatuteExtractReport:
    """Snapshot one official OLLS C.R.S. title HTM export and extract provisions."""
    jurisdiction = "us-co"
    run_id = version
    source_as_of_text = source_as_of or version
    if isinstance(expression_date, date):
        expression_date_text = expression_date.isoformat()
    else:
        expression_date_text = expression_date or source_as_of_text

    filename = f"crs{edition}-title-{title}.htm"
    source_url = f"{base_url}{filename}"

    data: bytes | None = None
    if download_dir is not None:
        cached = Path(download_dir) / filename
        if cached.exists():
            data = cached.read_bytes()
    if data is None:
        data = _download_colorado_title(
            source_url=source_url,
            timeout_seconds=timeout_seconds,
            request_attempts=request_attempts,
            request_delay_seconds=request_delay_seconds,
        )
        if download_dir is not None:
            cached = Path(download_dir) / filename
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)

    source_store_path = store.source_path(jurisdiction, DocumentClass.STATUTE, run_id, filename)
    sha256 = store.write_bytes(source_store_path, data)
    recorded = _RecordedSource(
        source_url=source_url,
        source_path=_store_relative_path(store, source_store_path),
        source_format=COLORADO_CRS_TITLE_SOURCE_FORMAT,
        sha256=sha256,
    )

    sections, document_heading = parse_colorado_crs_title(
        data,
        title=title,
        only_article=only_article,
    )
    if limit is not None:
        sections = sections[:limit]
    if not sections:
        raise ValueError(
            f"no C.R.S. sections extracted for title {title!r} article {only_article!r}"
        )

    title_citation_path = f"us-co/statute/{title}"
    root_citation_path = "us-co/statute"

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []

    def _container(
        citation_path: str,
        *,
        heading: str,
        parent: str | None,
        level: int,
        kind: str,
        ordinal_value: int,
        legal_identifier: str,
    ) -> None:
        items.append(
            SourceInventoryItem(
                citation_path=citation_path,
                source_url=recorded.source_url,
                source_path=recorded.source_path,
                source_format=recorded.source_format,
                sha256=recorded.sha256,
                metadata={"kind": kind, "heading": heading},
            )
        )
        records.append(
            ProvisionRecord(
                id=deterministic_provision_id(citation_path),
                jurisdiction=jurisdiction,
                document_class=DocumentClass.STATUTE.value,
                citation_path=citation_path,
                body="",
                heading=heading,
                citation_label=legal_identifier,
                version=run_id,
                source_url=recorded.source_url,
                source_path=recorded.source_path,
                source_id=filename,
                source_format=recorded.source_format,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                parent_citation_path=parent,
                parent_id=deterministic_provision_id(parent) if parent else None,
                level=level,
                ordinal=ordinal_value,
                kind=kind,
                legal_identifier=legal_identifier,
                identifiers={"co:crs_edition": edition, "co:title": title},
                metadata={
                    "kind": kind,
                    "crs_edition": edition,
                    "title": title,
                    "source_filename": filename,
                },
            )
        )

    _container(
        root_citation_path,
        heading="Colorado Revised Statutes",
        parent=None,
        level=0,
        kind="root",
        ordinal_value=0,
        legal_identifier="C.R.S.",
    )
    _container(
        title_citation_path,
        heading=document_heading,
        parent=root_citation_path,
        level=1,
        kind="title",
        ordinal_value=int(float(title)),
        legal_identifier=f"C.R.S. Title {title}",
    )

    for section in sections:
        citation_path = f"{title_citation_path}/{section.section}"
        legal_identifier = f"C.R.S. § {section.section}"
        metadata: dict[str, Any] = {
            "kind": "section",
            "crs_edition": edition,
            "title": title,
            "article": section.article,
            "section": section.section,
            "source_filename": filename,
        }
        if section.part_heading:
            metadata["part_heading"] = section.part_heading
        if section.source_history:
            metadata["source_history"] = list(section.source_history)
        if section.source_notes:
            metadata["source_notes"] = list(section.source_notes)
        if section.annotation_paragraphs:
            metadata["annotation_paragraphs_excluded"] = section.annotation_paragraphs
        if section.repealed:
            metadata["status"] = "repealed"

        items.append(
            SourceInventoryItem(
                citation_path=citation_path,
                source_url=recorded.source_url,
                source_path=recorded.source_path,
                source_format=recorded.source_format,
                sha256=recorded.sha256,
                metadata=dict(metadata),
            )
        )
        records.append(
            ProvisionRecord(
                id=deterministic_provision_id(citation_path),
                jurisdiction=jurisdiction,
                document_class=DocumentClass.STATUTE.value,
                citation_path=citation_path,
                body=section.body,
                heading=section.heading,
                citation_label=legal_identifier,
                version=run_id,
                source_url=recorded.source_url,
                source_path=recorded.source_path,
                source_id=filename,
                source_format=recorded.source_format,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                parent_citation_path=title_citation_path,
                parent_id=deterministic_provision_id(title_citation_path),
                level=2,
                ordinal=section.ordinal,
                kind="section",
                legal_identifier=legal_identifier,
                identifiers={
                    "co:crs_edition": edition,
                    "co:title": title,
                    "co:article": section.article,
                    "co:section": section.section,
                },
                metadata=metadata,
            )
        )

    inventory_path = store.inventory_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction=jurisdiction,
        document_class=DocumentClass.STATUTE.value,
        version=run_id,
    )
    coverage_path = store.coverage_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_json(coverage_path, coverage.to_mapping())

    return StateStatuteExtractReport(
        jurisdiction=jurisdiction,
        title_count=1,
        container_count=2,
        section_count=len(sections),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=(source_store_path,),
        errors=(),
    )
