"""Maryland COMAR source-first adapter."""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, TextIO, cast
from urllib.parse import quote

import requests
from lxml import etree

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

MARYLAND_COMAR_REPO_URL = "https://github.com/maryland-dsd/law-xml-codified"
MARYLAND_COMAR_BRANCHES_API_URL = (
    "https://api.github.com/repos/maryland-dsd/law-xml-codified/branches"
)
MARYLAND_COMAR_HTML_BASE_URL = "https://regs.maryland.gov"
MARYLAND_COMAR_SOURCE_FORMAT = "maryland-comar-openlaw-xml"
MARYLAND_COMAR_USER_AGENT = "axiom-corpus/0.1 (max@axiom-foundation.org)"

_COMAR_ROOT_RELATIVE = PurePosixPath("us/md/exec/comar/index.xml")
_SOURCE_PREFIX = "maryland-comar-xml"
_LIB_NS = "https://open.law/schemas/library"
_XI_NS = "http://www.w3.org/2001/XInclude"
_BRANCH_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class MarylandComarExtractReport:
    """Result from a Maryland COMAR extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    publication_branch: str | None
    title_count: int
    subtitle_count: int
    chapter_count: int
    regulation_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class _RecordedSource:
    source_url: str
    source_path: str
    artifact_path: Path
    sha256: str


@dataclass(frozen=True)
class _ComarContext:
    title: str
    title_heading: str
    subtitle: str | None = None
    subtitle_heading: str | None = None
    chapter: str | None = None
    chapter_heading: str | None = None


@dataclass(frozen=True)
class _SectionParts:
    number: str
    heading: str
    body: str | None
    annotations: tuple[dict[str, str], ...]
    attachments: tuple[dict[str, str], ...]
    references_to: tuple[str, ...]


def maryland_comar_run_id(
    version: str,
    *,
    publication_branch: str | None = None,
    only_title: str | None = None,
    only_subtitle: str | None = None,
    only_chapter: str | None = None,
    limit: int | None = None,
) -> str:
    """Return a scoped Maryland COMAR run id."""

    parts = [version]
    if publication_branch:
        branch_dates = _BRANCH_DATE_RE.findall(publication_branch)
        if branch_dates:
            parts.append(f"publication-{branch_dates[-1]}")
    if only_title:
        parts.append(f"title-{_path_token(only_title)}")
    if only_subtitle:
        parts.append(f"subtitle-{_path_token(only_subtitle)}")
    if only_chapter:
        parts.append(f"chapter-{_path_token(only_chapter)}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def latest_maryland_comar_publication_branch() -> str:
    """Return the newest public Maryland COMAR publication branch."""

    response = requests.get(
        MARYLAND_COMAR_BRANCHES_API_URL,
        params={"per_page": "100"},
        headers={"User-Agent": MARYLAND_COMAR_USER_AGENT},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("unexpected Maryland COMAR branches payload")
    branches = [
        str(row.get("name"))
        for row in payload
        if isinstance(row, dict) and str(row.get("name", "")).startswith("publication/")
    ]
    if not branches:
        raise ValueError("no Maryland COMAR publication branches found")
    return max(branches, key=_publication_branch_key)


def extract_maryland_comar(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    publication_branch: str | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | None = None,
    only_subtitle: str | None = None,
    only_chapter: str | None = None,
    limit: int | None = None,
    progress_stream: TextIO | None = None,
) -> MarylandComarExtractReport:
    """Snapshot the official Maryland COMAR bulk XML and extract provisions."""

    jurisdiction = "us-md"
    document_class = DocumentClass.REGULATION.value
    temp_root: TemporaryDirectory[str] | None = None
    if source_dir is None and publication_branch is None:
        publication_branch = latest_maryland_comar_publication_branch()
    run_id = maryland_comar_run_id(
        version,
        publication_branch=publication_branch,
        only_title=only_title,
        only_subtitle=only_subtitle,
        only_chapter=only_chapter,
        limit=limit,
    )
    try:
        source_root, temp_root = _resolve_source_root(
            source_dir=source_dir,
            download_dir=download_dir,
            publication_branch=publication_branch,
        )

        root_snapshot = _snapshot_source(
            store,
            run_id=run_id,
            source_root=source_root,
            relative_path=_COMAR_ROOT_RELATIVE,
            publication_branch=publication_branch,
        )
        source_paths: list[Path] = [root_snapshot.artifact_path]
        top_index = source_root / "index.xml"
        if top_index.exists():
            top_snapshot = _snapshot_source(
                store,
                run_id=run_id,
                source_root=source_root,
                relative_path=PurePosixPath("index.xml"),
                publication_branch=publication_branch,
            )
            source_paths.append(top_snapshot.artifact_path)
        license_path = source_root / "license.md"
        if license_path.exists():
            license_snapshot = _snapshot_source(
                store,
                run_id=run_id,
                source_root=source_root,
                relative_path=PurePosixPath("license.md"),
                publication_branch=publication_branch,
            )
            source_paths.append(license_snapshot.artifact_path)

        root = _parse_xml((source_root / _COMAR_ROOT_RELATIVE).read_bytes())
        detected_source_as_of = _detect_source_as_of(source_root, publication_branch)
        source_as_of_text = source_as_of or detected_source_as_of or version
        expression_date_text = _date_text(expression_date, source_as_of_text)
        root_heading = _child_text(root, "heading") or "Code of Maryland Regulations"
        root_metadata: dict[str, Any] = {
            "kind": "collection",
            "source_repo": MARYLAND_COMAR_REPO_URL,
            "source_as_of": source_as_of_text,
        }
        if publication_branch:
            root_metadata["publication_branch"] = publication_branch

        inventory: list[SourceInventoryItem] = []
        records: list[ProvisionRecord] = []
        root_path = "us-md/regulation"
        inventory.append(
            SourceInventoryItem(
                citation_path=root_path,
                source_url=MARYLAND_COMAR_HTML_BASE_URL,
                source_path=root_snapshot.source_path,
                source_format=MARYLAND_COMAR_SOURCE_FORMAT,
                sha256=root_snapshot.sha256,
                metadata=root_metadata,
            )
        )
        records.append(
            _record(
                citation_path=root_path,
                heading=root_heading,
                body=None,
                version=run_id,
                source_url=MARYLAND_COMAR_HTML_BASE_URL,
                source_path=root_snapshot.source_path,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                level=0,
                ordinal=0,
                kind="collection",
                metadata=root_metadata,
            )
        )

        selected_title = _normal_token(only_title) if only_title else None
        selected_subtitle = _normal_token(only_subtitle) if only_subtitle else None
        selected_chapter = _normal_token(only_chapter) if only_chapter else None
        remaining = limit
        title_count = 0
        subtitle_count = 0
        chapter_count = 0
        regulation_count = 0

        for title_ordinal, title_rel in enumerate(_include_paths(root, _COMAR_ROOT_RELATIVE), 1):
            title_parts = _comar_parts(title_rel)
            if len(title_parts) != 1:
                continue
            title_number = title_parts[0]
            if selected_title is not None and _normal_token(title_number) != selected_title:
                continue
            if remaining is not None and remaining <= 0:
                break
            _progress(progress_stream, f"maryland-comar title {title_number}")
            title_snapshot = _snapshot_source(
                store,
                run_id=run_id,
                source_root=source_root,
                relative_path=title_rel,
                publication_branch=publication_branch,
            )
            source_paths.append(title_snapshot.artifact_path)
            title_root = _parse_xml((source_root / title_rel).read_bytes())
            title_info = _container_info(title_root)
            title_heading = title_info["heading"] or ""
            title_context = _ComarContext(
                title=title_number,
                title_heading=title_heading,
            )
            _append_container(
                context=title_context,
                kind="title",
                number=title_number,
                heading=title_heading,
                ordinal=title_ordinal,
                source=title_snapshot,
                inventory=inventory,
                records=records,
                version=run_id,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
            )
            title_count += 1

            for subtitle_ordinal, subtitle_rel in enumerate(
                _include_paths(title_root, title_rel),
                1,
            ):
                subtitle_parts = _comar_parts(subtitle_rel)
                if len(subtitle_parts) != 2:
                    continue
                subtitle_number = subtitle_parts[1]
                if (
                    selected_subtitle is not None
                    and _normal_token(subtitle_number) != selected_subtitle
                ):
                    continue
                if remaining is not None and remaining <= 0:
                    break
                subtitle_snapshot = _snapshot_source(
                    store,
                    run_id=run_id,
                    source_root=source_root,
                    relative_path=subtitle_rel,
                    publication_branch=publication_branch,
                )
                source_paths.append(subtitle_snapshot.artifact_path)
                subtitle_root = _parse_xml((source_root / subtitle_rel).read_bytes())
                subtitle_info = _container_info(subtitle_root)
                subtitle_heading = subtitle_info["heading"] or ""
                subtitle_context = _ComarContext(
                    title=title_number,
                    title_heading=title_heading,
                    subtitle=subtitle_number,
                    subtitle_heading=subtitle_heading,
                )
                _append_container(
                    context=subtitle_context,
                    kind="subtitle",
                    number=subtitle_number,
                    heading=subtitle_heading,
                    ordinal=subtitle_ordinal,
                    source=subtitle_snapshot,
                    inventory=inventory,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                )
                subtitle_count += 1

                for chapter_ordinal, chapter_rel in enumerate(
                    _include_paths(subtitle_root, subtitle_rel),
                    1,
                ):
                    chapter_parts = _comar_parts(chapter_rel)
                    if len(chapter_parts) != 3:
                        continue
                    chapter_number = chapter_parts[2]
                    if (
                        selected_chapter is not None
                        and _normal_token(chapter_number) != selected_chapter
                    ):
                        continue
                    if remaining is not None and remaining <= 0:
                        break
                    chapter_snapshot = _snapshot_source(
                        store,
                        run_id=run_id,
                        source_root=source_root,
                        relative_path=chapter_rel,
                        publication_branch=publication_branch,
                    )
                    source_paths.append(chapter_snapshot.artifact_path)
                    chapter_root = _parse_xml((source_root / chapter_rel).read_bytes())
                    chapter_info = _container_info(chapter_root)
                    chapter_heading = chapter_info["heading"] or ""
                    chapter_context = _ComarContext(
                        title=title_number,
                        title_heading=title_heading,
                        subtitle=subtitle_number,
                        subtitle_heading=subtitle_heading,
                        chapter=chapter_number,
                        chapter_heading=chapter_heading,
                    )
                    sections = _section_children(chapter_root)
                    chapter_body = None if sections else _container_body(chapter_root)
                    _append_container(
                        context=chapter_context,
                        kind="chapter",
                        number=chapter_number,
                        heading=chapter_heading,
                        ordinal=chapter_ordinal,
                        source=chapter_snapshot,
                        inventory=inventory,
                        records=records,
                        version=run_id,
                        source_as_of=source_as_of_text,
                        expression_date=expression_date_text,
                        body=chapter_body,
                        reason=chapter_info["reason"],
                        annotations=_annotations(chapter_root),
                    )
                    chapter_count += 1

                    for section_ordinal, section in enumerate(sections, 1):
                        if remaining is not None and remaining <= 0:
                            break
                        section_parts = _section_parts(section, context=chapter_context)
                        _append_section(
                            context=chapter_context,
                            section=section_parts,
                            ordinal=section_ordinal,
                            source=chapter_snapshot,
                            inventory=inventory,
                            records=records,
                            version=run_id,
                            source_as_of=source_as_of_text,
                            expression_date=expression_date_text,
                        )
                        regulation_count += 1
                        if remaining is not None:
                            remaining -= 1

        inventory_path = store.inventory_path(jurisdiction, DocumentClass.REGULATION, run_id)
        provisions_path = store.provisions_path(jurisdiction, DocumentClass.REGULATION, run_id)
        coverage_path = store.coverage_path(jurisdiction, DocumentClass.REGULATION, run_id)
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

        return MarylandComarExtractReport(
            jurisdiction=jurisdiction,
            document_class=document_class,
            version=run_id,
            publication_branch=publication_branch,
            title_count=title_count,
            subtitle_count=subtitle_count,
            chapter_count=chapter_count,
            regulation_count=regulation_count,
            provisions_written=len(records),
            inventory_path=inventory_path,
            provisions_path=provisions_path,
            coverage_path=coverage_path,
            coverage=coverage,
            source_paths=tuple(source_paths),
        )
    finally:
        if temp_root is not None:
            temp_root.cleanup()


def _append_container(
    *,
    context: _ComarContext,
    kind: str,
    number: str,
    heading: str,
    ordinal: int,
    source: _RecordedSource,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    body: str | None = None,
    reason: str | None = None,
    annotations: tuple[dict[str, str], ...] = (),
) -> None:
    citation_path = _container_citation_path(context, kind)
    metadata: dict[str, Any] = {
        "kind": kind,
        "number": number,
        "title_number": context.title,
        "title_heading": context.title_heading,
    }
    if context.subtitle:
        metadata["subtitle_number"] = context.subtitle
        metadata["subtitle_heading"] = context.subtitle_heading
    if context.chapter:
        metadata["chapter_number"] = context.chapter
        metadata["chapter_heading"] = context.chapter_heading
    if reason:
        metadata["status"] = reason.lower()
        metadata["reason"] = reason
    if annotations:
        metadata["annotations"] = list(annotations)
    legal_identifier = _legal_identifier(context, kind=kind)
    parent_citation_path = _container_parent_citation_path(context, kind)
    inventory.append(
        SourceInventoryItem(
            citation_path=citation_path,
            source_url=source.source_url,
            source_path=source.source_path,
            source_format=MARYLAND_COMAR_SOURCE_FORMAT,
            sha256=source.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=citation_path,
            parent_citation_path=parent_citation_path,
            heading=_container_heading(kind=kind, number=number, heading=heading),
            body=body,
            version=version,
            source_url=source.source_url,
            source_path=source.source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level={"title": 1, "subtitle": 2, "chapter": 3}[kind],
            ordinal=ordinal,
            kind=kind,
            legal_identifier=legal_identifier,
            citation_label=legal_identifier,
            identifiers={"comar": legal_identifier},
            metadata=metadata,
        )
    )


def _append_section(
    *,
    context: _ComarContext,
    section: _SectionParts,
    ordinal: int,
    source: _RecordedSource,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> None:
    citation_path = _section_citation_path(context, section.number)
    legal_identifier = _section_legal_identifier(context, section.number)
    metadata: dict[str, Any] = {
        "kind": "regulation",
        "title_number": context.title,
        "subtitle_number": context.subtitle,
        "chapter_number": context.chapter,
        "regulation_number": section.number,
    }
    if section.references_to:
        metadata["references_to"] = list(section.references_to)
    if section.annotations:
        metadata["annotations"] = list(section.annotations)
    if section.attachments:
        metadata["attachments"] = list(section.attachments)
    inventory.append(
        SourceInventoryItem(
            citation_path=citation_path,
            source_url=source.source_url,
            source_path=source.source_path,
            source_format=MARYLAND_COMAR_SOURCE_FORMAT,
            sha256=source.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=citation_path,
            parent_citation_path=_container_citation_path(context, "chapter"),
            heading=f"{legal_identifier}. {section.heading}".strip(),
            citation_label=legal_identifier,
            body=section.body,
            version=version,
            source_url=source.source_url,
            source_path=source.source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=4,
            ordinal=ordinal,
            kind="regulation",
            legal_identifier=legal_identifier,
            identifiers={"comar": legal_identifier},
            metadata=metadata,
        )
    )


def _record(
    *,
    citation_path: str,
    heading: str,
    body: str | None,
    version: str,
    source_url: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    level: int,
    ordinal: int,
    kind: str,
    parent_citation_path: str | None = None,
    legal_identifier: str | None = None,
    citation_label: str | None = None,
    identifiers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProvisionRecord:
    return ProvisionRecord(
        jurisdiction="us-md",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        id=deterministic_provision_id(citation_path),
        parent_citation_path=parent_citation_path,
        parent_id=(
            deterministic_provision_id(parent_citation_path)
            if parent_citation_path is not None
            else None
        ),
        heading=heading,
        citation_label=citation_label,
        body=body,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_format=MARYLAND_COMAR_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=level,
        ordinal=ordinal,
        kind=kind,
        legal_identifier=legal_identifier,
        identifiers=identifiers,
        has_rulespec=False,
        metadata=metadata,
    )


def _resolve_source_root(
    *,
    source_dir: str | Path | None,
    download_dir: str | Path | None,
    publication_branch: str | None,
) -> tuple[Path, TemporaryDirectory[str] | None]:
    if source_dir is not None:
        source_root = Path(source_dir)
        if not (source_root / _COMAR_ROOT_RELATIVE).exists():
            raise FileNotFoundError(source_root / _COMAR_ROOT_RELATIVE)
        return source_root, None
    if publication_branch is None:
        raise ValueError("publication_branch is required when source_dir is not provided")
    if download_dir is not None:
        source_root = Path(download_dir) / _branch_cache_name(publication_branch)
        if (source_root / _COMAR_ROOT_RELATIVE).exists():
            return source_root, None
        source_root.parent.mkdir(parents=True, exist_ok=True)
        _download_archive(publication_branch, source_root)
        return source_root, None
    temp_root = TemporaryDirectory()
    source_root = Path(temp_root.name) / _branch_cache_name(publication_branch)
    _download_archive(publication_branch, source_root)
    return source_root, temp_root


def _download_archive(publication_branch: str, target: Path) -> None:
    archive_url = (
        f"{MARYLAND_COMAR_REPO_URL}/archive/refs/heads/"
        f"{quote(publication_branch, safe='/')}.zip"
    )
    response = requests.get(
        archive_url,
        headers={"User-Agent": MARYLAND_COMAR_USER_AGENT},
        timeout=300,
    )
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    archive_path = target.parent / f"{_branch_cache_name(publication_branch)}.zip"
    archive_path.write_bytes(response.content)
    staging = target.parent / f"{target.name}.extracting"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(staging)
    roots = [path for path in staging.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise ValueError(f"unexpected Maryland COMAR archive root count: {len(roots)}")
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(roots[0]), target)
    shutil.rmtree(staging)


def _snapshot_source(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    source_root: Path,
    relative_path: PurePosixPath,
    publication_branch: str | None,
) -> _RecordedSource:
    data = (source_root / relative_path).read_bytes()
    artifact_relative = PurePosixPath(_SOURCE_PREFIX) / relative_path
    artifact_path = store.source_path(
        "us-md",
        DocumentClass.REGULATION,
        run_id,
        artifact_relative.as_posix(),
    )
    sha = store.write_bytes(artifact_path, data)
    source_path = f"sources/us-md/regulation/{run_id}/{artifact_relative.as_posix()}"
    return _RecordedSource(
        source_url=_source_url(relative_path, publication_branch),
        source_path=source_path,
        artifact_path=artifact_path,
        sha256=sha,
    )


def _parse_xml(data: bytes) -> Any:
    return etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False))


def _detect_source_as_of(source_root: Path, publication_branch: str | None) -> str | None:
    index_path = source_root / "index.xml"
    if index_path.exists():
        root = _parse_xml(index_path.read_bytes())
        build_date = root.findtext(f".//{{{_LIB_NS}}}build-date")
        if build_date:
            return _clean_text(build_date)
    if publication_branch:
        dates = _BRANCH_DATE_RE.findall(publication_branch)
        if dates:
            return cast(str, dates[-1])
    return None


def _container_info(root: Any) -> dict[str, str | None]:
    return {
        "prefix": _child_text(root, "prefix"),
        "num": _child_text(root, "num"),
        "heading": _child_text(root, "heading"),
        "reason": _child_text(root, "reason"),
    }


def _section_parts(section: Any, *, context: _ComarContext) -> _SectionParts:
    number = _child_text(section, "num") or ""
    heading = _child_text(section, "heading") or ""
    return _SectionParts(
        number=number,
        heading=heading,
        body=_section_body(section),
        annotations=_annotations(section),
        attachments=_attachments(section),
        references_to=_references_to(section, context=context),
    )


def _section_body(section: Any) -> str | None:
    lines: list[str] = []
    for child in section:
        tag = _tag(child)
        if tag in {"prefix", "num", "heading", "annotations"}:
            continue
        lines.extend(_block_lines(child))
    return _join_lines(lines)


def _container_body(root: Any) -> str | None:
    lines: list[str] = []
    for child in root:
        tag = _tag(child)
        if tag in {"prefix", "num", "heading", "annotations"}:
            continue
        lines.extend(_block_lines(child))
    return _join_lines(lines)


def _block_lines(element: Any) -> list[str]:
    tag = _tag(element)
    if tag == "para":
        return _para_lines(element)
    if tag == "table":
        return _table_lines(element)
    if tag == "attachments":
        return [
            f"Attachment: {item['name']} {item['url']}".strip()
            for item in _attachments_container(element)
        ]
    if tag == "page":
        return []
    if tag == "annotations":
        return []
    text = _inline_text(element)
    return [text] if text else []


def _para_lines(element: Any) -> list[str]:
    number = _child_text(element, "num")
    current_parts: list[str] = []
    if number:
        current_parts.append(number)
    nested: list[str] = []
    for child in element:
        tag = _tag(child)
        if tag == "num":
            continue
        if tag == "para":
            nested.extend(_para_lines(child))
            continue
        if tag == "table":
            nested.extend(_table_lines(child))
            continue
        child_text = _inline_text(child)
        if child_text:
            current_parts.append(child_text)
    lines = [_clean_text(" ".join(current_parts))] if current_parts else []
    lines.extend(nested)
    return [line for line in lines if line]


def _inline_text(element: Any) -> str:
    tag = _tag(element)
    if tag == "br":
        return "\n"
    if tag == "img":
        return _clean_text(str(element.get("alt") or ""))
    if tag == "table":
        return "\n".join(_table_lines(element))
    pieces: list[str] = []
    if element.text:
        pieces.append(str(element.text))
    for child in element:
        child_text = _inline_text(child)
        if child_text:
            pieces.append(child_text)
        if child.tail:
            pieces.append(str(child.tail))
    return _clean_text("".join(pieces))


def _table_lines(table: Any) -> list[str]:
    rows: list[str] = []
    for row in table.iter():
        if _tag(row) != "tr":
            continue
        cells = [
            _inline_text(cell)
            for cell in row
            if _tag(cell) in {"td", "th"} and _inline_text(cell)
        ]
        if cells:
            rows.append(" | ".join(cells))
    return rows


def _annotations(element: Any) -> tuple[dict[str, str], ...]:
    annotations = []
    for container in element:
        if _tag(container) != "annotations":
            continue
        for annotation in container:
            if _tag(annotation) != "annotation":
                continue
            item = {
                str(key): str(value)
                for key, value in annotation.attrib.items()
                if value is not None and str(value)
            }
            text = _inline_text(annotation)
            if text:
                item["text"] = text
            if item:
                annotations.append(item)
    return tuple(annotations)


def _attachments(element: Any) -> tuple[dict[str, str], ...]:
    attachments: list[dict[str, str]] = []
    for container in element:
        if _tag(container) == "attachments":
            attachments.extend(_attachments_container(container))
    return tuple(attachments)


def _attachments_container(container: Any) -> tuple[dict[str, str], ...]:
    attachments: list[dict[str, str]] = []
    for attachment in container:
        if _tag(attachment) != "attachment":
            continue
        item = {
            str(key): str(value)
            for key, value in attachment.attrib.items()
            if value is not None and str(value)
        }
        if item:
            attachments.append(item)
    return tuple(attachments)


def _references_to(element: Any, *, context: _ComarContext) -> tuple[str, ...]:
    references: list[str] = []
    for child in element.iter():
        if _tag(child) != "cite":
            continue
        path = child.get("path")
        doc = child.get("doc")
        normalized = _normalize_reference(path, doc=doc, context=context)
        if normalized:
            references.append(normalized)
    return tuple(dict.fromkeys(references))


def _normalize_reference(
    path: str | None,
    *,
    doc: str | None,
    context: _ComarContext,
) -> str | None:
    if not path:
        return None
    if doc == "Md. Code" and path:
        raw_parts = [part for part in str(path).split("|") if part]
        article = _path_token(raw_parts[0])
        if len(raw_parts) >= 2:
            return f"us-md/statute/{article}/{_path_token(raw_parts[1])}"
        return f"us-md/statute/{article}"
    parts = [part for part in str(path).split("|") if part]
    if parts and parts[0].count(".") >= 2:
        dotted = [part for part in parts[0].split(".") if part]
        parts = dotted + parts[1:]
    if (
        len(parts) < 4
        and context.subtitle
        and context.chapter
        and parts
        and parts[0].startswith(".")
    ):
        parts = [context.title, context.subtitle, context.chapter, *parts]
    if len(parts) >= 4 and parts[3].startswith("."):
        ref_context = _ComarContext(
            title=parts[0],
            title_heading="",
            subtitle=parts[1],
            chapter=parts[2],
        )
        return _section_citation_path(ref_context, parts[3])
    return None


def _include_paths(root: Any, current_relative: PurePosixPath) -> tuple[PurePosixPath, ...]:
    parent = current_relative.parent
    out: list[PurePosixPath] = []
    for child in root:
        if _tag(child) != "include" or child.nsmap.get(child.prefix) != _XI_NS:
            continue
        href = child.get("href")
        if not href:
            continue
        resolved = (parent / str(href)).as_posix()
        normalized = PurePosixPath(resolved)
        parts = [part for part in normalized.parts if part not in {"."}]
        out.append(PurePosixPath(*parts))
    return tuple(out)


def _section_children(root: Any) -> tuple[Any, ...]:
    return tuple(child for child in root if _tag(child) == "section")


def _comar_parts(relative_path: PurePosixPath) -> tuple[str, ...]:
    parts = relative_path.parts
    try:
        start = parts.index("comar") + 1
    except ValueError:
        return ()
    comar_parts = list(parts[start:])
    if not comar_parts:
        return ()
    if comar_parts[-1] == "index.xml":
        comar_parts.pop()
    elif comar_parts[-1].endswith(".xml"):
        comar_parts[-1] = comar_parts[-1][:-4]
    return tuple(comar_parts)


def _source_url(relative_path: PurePosixPath, publication_branch: str | None) -> str:
    if publication_branch:
        return f"{MARYLAND_COMAR_REPO_URL}/blob/{quote(publication_branch, safe='')}/{relative_path.as_posix()}"
    return f"{MARYLAND_COMAR_REPO_URL}/blob/main/{relative_path.as_posix()}"


def _container_citation_path(context: _ComarContext, kind: str) -> str:
    title_path = f"us-md/regulation/title-{_path_token(context.title)}"
    if kind == "title":
        return title_path
    subtitle_path = f"{title_path}/subtitle-{_path_token(context.subtitle or '')}"
    if kind == "subtitle":
        return subtitle_path
    return f"{subtitle_path}/chapter-{_path_token(context.chapter or '')}"


def _container_parent_citation_path(context: _ComarContext, kind: str) -> str:
    if kind == "title":
        return "us-md/regulation"
    if kind == "subtitle":
        return _container_citation_path(context, "title")
    return _container_citation_path(context, "subtitle")


def _section_citation_path(context: _ComarContext, number: str) -> str:
    return f"{_container_citation_path(context, 'chapter')}/regulation-{_path_token(number)}"


def _container_heading(*, kind: str, number: str, heading: str) -> str:
    label = {"title": "Title", "subtitle": "Subtitle", "chapter": "Chapter"}[kind]
    return f"{label} {number}. {heading}".strip()


def _legal_identifier(context: _ComarContext, *, kind: str) -> str:
    if kind == "title":
        return f"COMAR {context.title}"
    if kind == "subtitle":
        return f"COMAR {context.title}.{context.subtitle}"
    return f"COMAR {context.title}.{context.subtitle}.{context.chapter}"


def _section_legal_identifier(context: _ComarContext, number: str) -> str:
    return f"COMAR {context.title}.{context.subtitle}.{context.chapter}{number}"


def _child_text(element: Any, tag_name: str) -> str | None:
    for child in element:
        if _tag(child) == tag_name:
            return _inline_text(child)
    return None


def _join_lines(lines: Iterable[str]) -> str | None:
    cleaned = [_clean_text(line) for line in lines]
    cleaned = [line for line in cleaned if line]
    return "\n".join(cleaned) if cleaned else None


def _clean_text(value: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _date_text(value: date | str | None, fallback: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        return value
    return fallback


def _path_token(value: str) -> str:
    token = value.strip().strip(".").lower()
    token = re.sub(r"[^a-z0-9]+", "-", token)
    return token.strip("-") or "unnumbered"


def _normal_token(value: str) -> str:
    return _path_token(value)


def _tag(element: Any) -> str:
    return cast(str, etree.QName(element).localname)


def _publication_branch_key(branch: str) -> tuple[tuple[str, ...], str]:
    return (tuple(_BRANCH_DATE_RE.findall(branch)), branch)


def _branch_cache_name(branch: str) -> str:
    return _path_token(branch.replace("/", "-"))


def _progress(stream: TextIO | None, message: str) -> None:
    if stream is None:
        return
    print(message, file=stream)
    stream.flush()


if __name__ == "__main__":  # pragma: no cover
    from axiom_corpus.corpus.cli import main

    raise SystemExit(main(sys.argv[1:]))
