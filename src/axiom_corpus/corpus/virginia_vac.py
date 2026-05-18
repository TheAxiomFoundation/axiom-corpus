"""Virginia Administrative Code source-first adapter."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

VIRGINIA_VAC_BASE_URL = "https://law.lis.virginia.gov"
VIRGINIA_VAC_API_BASE_URL = f"{VIRGINIA_VAC_BASE_URL}/api"
VIRGINIA_VAC_SOURCE_FORMAT = "virginia-vac-json"
VIRGINIA_VAC_USER_AGENT = "axiom-corpus/0.1 (max@axiom-foundation.org)"


@dataclass(frozen=True)
class VirginiaVacExtractReport:
    """Result from a Virginia Administrative Code extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    title_count: int
    agency_count: int
    chapter_count: int
    section_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class _SourceSnapshot:
    payload: Any
    source_key: str
    source_path: Path
    sha256: str


@dataclass(frozen=True)
class _VacTitle:
    number: str
    name: str
    ordinal: int
    source_key: str
    sha256: str

    @property
    def citation_path(self) -> str:
        return f"us-va/regulation/title-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        return f"{VIRGINIA_VAC_BASE_URL}/admincode/title{quote(self.number, safe='')}/"

    @property
    def heading(self) -> str:
        return f"Title {self.number}. {self.name}"


@dataclass(frozen=True)
class _VacAgency:
    title: _VacTitle
    number: str
    name: str
    ordinal: int
    source_key: str
    sha256: str
    body: str | None

    @property
    def citation_path(self) -> str:
        return f"{self.title.citation_path}/agency-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        title = quote(self.title.number, safe="")
        agency = quote(self.number, safe="")
        return f"{VIRGINIA_VAC_BASE_URL}/admincode/title{title}/agency{agency}/"

    @property
    def heading(self) -> str:
        return f"Agency {self.number}. {self.name}"


@dataclass(frozen=True)
class _VacChapter:
    agency: _VacAgency
    number: str
    name: str
    ordinal: int
    source_key: str
    sha256: str

    @property
    def citation_path(self) -> str:
        return f"{self.agency.citation_path}/chapter-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        title = quote(self.agency.title.number, safe="")
        agency = quote(self.agency.number, safe="")
        chapter = quote(self.number, safe="")
        return (
            f"{VIRGINIA_VAC_BASE_URL}/admincode/title{title}/"
            f"agency{agency}/chapter{chapter}/"
        )

    @property
    def heading(self) -> str:
        return f"Chapter {self.number}. {self.name}"


@dataclass(frozen=True)
class _VacSectionStub:
    chapter: _VacChapter
    number: str
    title: str
    part_number: str | None
    part_name: str | None
    article_number: str | None
    article_name: str | None
    body: str | None
    authority: str | None
    historical_note: str | None
    source_key: str
    source_path: Path
    sha256: str
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"{self.chapter.citation_path}/section-{_path_token(self.number)}"

    @property
    def source_url(self) -> str:
        title = quote(self.chapter.agency.title.number, safe="")
        agency = quote(self.chapter.agency.number, safe="")
        chapter = quote(self.chapter.number, safe="")
        section = quote(self.number, safe="")
        return (
            f"{VIRGINIA_VAC_BASE_URL}/admincode/title{title}/agency{agency}/"
            f"chapter{chapter}/section{section}/"
        )

    @property
    def legal_identifier(self) -> str:
        return (
            f"{self.chapter.agency.title.number}VAC"
            f"{self.chapter.agency.number}-{self.chapter.number}-{self.number}"
        )

    @property
    def heading(self) -> str:
        return f"{self.legal_identifier}. {self.title}".strip()


@dataclass(frozen=True)
class _VacSectionDetail:
    stub: _VacSectionStub
    body: str | None
    authority: str | None
    historical_note: str | None
    source_key: str
    source_path: Path
    sha256: str


def virginia_vac_run_id(
    version: str,
    *,
    only_title: str | None = None,
    only_agency: str | None = None,
    only_chapter: str | None = None,
    limit: int | None = None,
) -> str:
    """Return a scoped Virginia Administrative Code run id."""

    parts = [version]
    if only_title:
        parts.append(f"title-{_path_token(only_title)}")
    if only_agency:
        parts.append(f"agency-{_path_token(only_agency)}")
    if only_chapter:
        parts.append(f"chapter-{_path_token(only_chapter)}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def extract_virginia_vac(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | None = None,
    only_agency: str | None = None,
    only_chapter: str | None = None,
    limit: int | None = None,
    workers: int = 8,
    progress_stream: TextIO | None = None,
) -> VirginiaVacExtractReport:
    """Snapshot the official Virginia Administrative Code API and extract provisions."""

    jurisdiction = "us-va"
    document_class = DocumentClass.REGULATION.value
    run_id = virginia_vac_run_id(
        version,
        only_title=only_title,
        only_agency=only_agency,
        only_chapter=only_chapter,
        limit=limit,
    )
    source_root = Path(source_dir) if source_dir is not None else None
    download_root = Path(download_dir) if download_dir is not None else None
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)

    source_paths: list[Path] = []
    inventory: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    section_stubs: list[_VacSectionStub] = []

    titles_snapshot = _snapshot_json_source(
        store,
        run_id=run_id,
        relative_name="virginia-vac-json/titles.json",
        url=_api_url("AdministrativeCodeGetTitleListOfXml"),
        source_root=source_root,
        download_root=download_root,
    )
    source_paths.append(titles_snapshot.source_path)
    raw_titles = _require_list(titles_snapshot.payload, "title list")
    titles = tuple(
        _VacTitle(
            number=str(row.get("TitleNumber") or ""),
            name=str(row.get("TitleName") or ""),
            ordinal=ordinal,
            source_key=titles_snapshot.source_key,
            sha256=titles_snapshot.sha256,
        )
        for ordinal, row in enumerate(raw_titles, start=1)
        if isinstance(row, Mapping) and row.get("TitleNumber")
    )
    selected_titles = tuple(
        title
        for title in titles
        if only_title is None or _same_token(title.number, only_title)
    )
    if not selected_titles:
        raise ValueError(f"no Virginia Administrative Code titles selected: {only_title!r}")

    root_path = "us-va/regulation"
    inventory.append(
        SourceInventoryItem(
            citation_path=root_path,
            source_url=f"{VIRGINIA_VAC_BASE_URL}/admincode/",
            source_path=titles_snapshot.source_key,
            source_format=VIRGINIA_VAC_SOURCE_FORMAT,
            sha256=titles_snapshot.sha256,
            metadata={
                "kind": "collection",
                "source_as_of": source_as_of_text,
                "selected_title_count": len(selected_titles),
                "total_title_count": len(titles),
            },
        )
    )
    records.append(
        _record(
            citation_path=root_path,
            heading="Virginia Administrative Code",
            body=None,
            version=run_id,
            source_url=f"{VIRGINIA_VAC_BASE_URL}/admincode/",
            source_path=titles_snapshot.source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            level=0,
            ordinal=0,
            kind="collection",
            metadata={
                "selected_title_count": len(selected_titles),
                "total_title_count": len(titles),
            },
        )
    )

    selected_section_count = 0
    agency_count = 0
    chapter_count = 0
    for title in selected_titles:
        _progress(progress_stream, f"virginia-vac title {title.number}")
        _append_title(
            title,
            inventory=inventory,
            records=records,
            version=run_id,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )
        agencies_snapshot = _snapshot_json_source(
            store,
            run_id=run_id,
            relative_name=f"virginia-vac-json/title-{_path_token(title.number)}/agencies.json",
            url=_api_url("AdministrativeCodeGetAgencyListOfXml", title.number),
            source_root=source_root,
            download_root=download_root,
        )
        source_paths.append(agencies_snapshot.source_path)
        agencies_payload = _single_title_payload(
            agencies_snapshot.payload,
            title_number=title.number,
        )
        raw_agencies = _require_list(agencies_payload.get("AgencyList"), "agency list")
        for agency_ordinal, agency_row in enumerate(raw_agencies, start=1):
            if not isinstance(agency_row, Mapping) or not agency_row.get("AgencyNumber"):
                continue
            agency_number = str(agency_row.get("AgencyNumber") or "")
            if only_agency is not None and not _same_token(agency_number, only_agency):
                continue
            preface_snapshot = _snapshot_json_source(
                store,
                run_id=run_id,
                relative_name=(
                    f"virginia-vac-json/title-{_path_token(title.number)}/"
                    f"agency-{_path_token(agency_number)}/preface.json"
                ),
                url=_api_url("AdministrativeCodePrefaceXml", title.number, agency_number),
                source_root=source_root,
                download_root=download_root,
            )
            source_paths.append(preface_snapshot.source_path)
            preface_payload = (
                preface_snapshot.payload if isinstance(preface_snapshot.payload, Mapping) else {}
            )
            agency = _VacAgency(
                title=title,
                number=agency_number,
                name=str(agency_row.get("AgencyName") or ""),
                ordinal=agency_ordinal,
                source_key=preface_snapshot.source_key,
                sha256=preface_snapshot.sha256,
                body=_html_fragment_to_text(preface_payload.get("PrefaceSummary")),
            )
            agency_count += 1
            _append_agency(
                agency,
                inventory=inventory,
                records=records,
                version=run_id,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
            )
            chapters_snapshot = _snapshot_json_source(
                store,
                run_id=run_id,
                relative_name=(
                    f"virginia-vac-json/title-{_path_token(title.number)}/"
                    f"agency-{_path_token(agency.number)}/chapters.json"
                ),
                url=_api_url("AdministrativeCodeChapterListOfXml", title.number, agency.number),
                source_root=source_root,
                download_root=download_root,
            )
            source_paths.append(chapters_snapshot.source_path)
            chapters_payload = _single_agency_payload(
                chapters_snapshot.payload,
                title_number=title.number,
                agency_number=agency.number,
            )
            raw_chapters = _require_list(chapters_payload.get("ChapterList"), "chapter list")
            for chapter_ordinal, chapter_row in enumerate(raw_chapters, start=1):
                if not isinstance(chapter_row, Mapping) or not chapter_row.get("ChapterNumber"):
                    continue
                chapter_number = str(chapter_row.get("ChapterNumber") or "")
                if chapter_number.lower() == "preface":
                    continue
                if only_chapter is not None and not _same_token(chapter_number, only_chapter):
                    continue
                sections_snapshot = _snapshot_json_source(
                    store,
                    run_id=run_id,
                    relative_name=(
                        f"virginia-vac-json/title-{_path_token(title.number)}/"
                        f"agency-{_path_token(agency.number)}/"
                        f"chapter-{_path_token(chapter_number)}/sections.json"
                    ),
                    url=_api_url(
                        "AdministrativeCodeGetSectionListOfXml",
                        title.number,
                        agency.number,
                        chapter_number,
                    ),
                    source_root=source_root,
                    download_root=download_root,
                )
                source_paths.append(sections_snapshot.source_path)
                chapter = _VacChapter(
                    agency=agency,
                    number=chapter_number,
                    name=str(chapter_row.get("ChapterName") or ""),
                    ordinal=chapter_ordinal,
                    source_key=sections_snapshot.source_key,
                    sha256=sections_snapshot.sha256,
                )
                chapter_count += 1
                _append_chapter(
                    chapter,
                    inventory=inventory,
                    records=records,
                    version=run_id,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                )
                sections_payload = _single_chapter_payload(
                    sections_snapshot.payload,
                    title_number=title.number,
                    agency_number=agency.number,
                    chapter_number=chapter.number,
                )
                raw_sections = sections_payload.get("Sections") or ()
                if not isinstance(raw_sections, list):
                    continue
                seen_chapter_sections: set[str] = set()
                for section_ordinal, section_row in enumerate(raw_sections, start=1):
                    if not isinstance(section_row, Mapping) or not section_row.get(
                        "SectionNumber"
                    ):
                        continue
                    section_number = str(section_row.get("SectionNumber") or "")
                    section_key = _path_token(section_number)
                    if section_key in seen_chapter_sections:
                        continue
                    seen_chapter_sections.add(section_key)
                    if limit is not None and selected_section_count >= limit:
                        continue
                    section_stubs.append(
                        _VacSectionStub(
                            chapter=chapter,
                            number=section_number,
                            title=str(section_row.get("SectionTitle") or ""),
                            part_number=_clean_optional(section_row.get("PartNumber")),
                            part_name=_clean_optional(section_row.get("PartName")),
                            article_number=_clean_optional(section_row.get("ArticleNumber")),
                            article_name=_clean_optional(section_row.get("ArticleName")),
                            body=_html_fragment_to_text(section_row.get("Body")),
                            authority=_html_fragment_to_text(section_row.get("Authority")),
                            historical_note=_html_fragment_to_text(
                                section_row.get("HistoricalNote")
                            ),
                            source_key=sections_snapshot.source_key,
                            source_path=sections_snapshot.source_path,
                            sha256=sections_snapshot.sha256,
                            ordinal=section_ordinal,
                        )
                    )
                    selected_section_count += 1

    details = _load_section_details(
        section_stubs,
        store=store,
        run_id=run_id,
        source_root=source_root,
        download_root=download_root,
        workers=workers,
        progress_stream=progress_stream,
    )
    for detail in details:
        source_paths.append(detail.source_path)
        _append_section(
            detail,
            inventory=inventory,
            records=records,
            version=run_id,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )

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

    return VirginiaVacExtractReport(
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
        title_count=len(selected_titles),
        agency_count=agency_count,
        chapter_count=chapter_count,
        section_count=len(section_stubs),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


def _append_title(
    title: _VacTitle,
    *,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> None:
    inventory.append(
        SourceInventoryItem(
            citation_path=title.citation_path,
            source_url=title.source_url,
            source_path=title.source_key,
            source_format=VIRGINIA_VAC_SOURCE_FORMAT,
            sha256=title.sha256,
            metadata={
                "kind": "title",
                "title_number": title.number,
                "title_name": title.name,
            },
        )
    )
    records.append(
        _record(
            citation_path=title.citation_path,
            parent_citation_path="us-va/regulation",
            heading=title.heading,
            body=None,
            version=version,
            source_url=title.source_url,
            source_path=title.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=1,
            ordinal=title.ordinal,
            kind="title",
            legal_identifier=f"Title {title.number}",
            metadata={"title_number": title.number, "title_name": title.name},
        )
    )


def _append_agency(
    agency: _VacAgency,
    *,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> None:
    inventory.append(
        SourceInventoryItem(
            citation_path=agency.citation_path,
            source_url=agency.source_url,
            source_path=agency.source_key,
            source_format=VIRGINIA_VAC_SOURCE_FORMAT,
            sha256=agency.sha256,
            metadata={
                "kind": "agency",
                "title_number": agency.title.number,
                "agency_number": agency.number,
                "agency_name": agency.name,
            },
        )
    )
    records.append(
        _record(
            citation_path=agency.citation_path,
            parent_citation_path=agency.title.citation_path,
            heading=agency.heading,
            body=agency.body,
            version=version,
            source_url=agency.source_url,
            source_path=agency.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=2,
            ordinal=agency.ordinal,
            kind="agency",
            legal_identifier=f"{agency.title.number}VAC{agency.number}",
            metadata={
                "title_number": agency.title.number,
                "agency_number": agency.number,
                "agency_name": agency.name,
            },
        )
    )


def _append_chapter(
    chapter: _VacChapter,
    *,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> None:
    metadata = {
        "kind": "chapter",
        "title_number": chapter.agency.title.number,
        "agency_number": chapter.agency.number,
        "chapter_number": chapter.number,
        "chapter_name": chapter.name,
    }
    inventory.append(
        SourceInventoryItem(
            citation_path=chapter.citation_path,
            source_url=chapter.source_url,
            source_path=chapter.source_key,
            source_format=VIRGINIA_VAC_SOURCE_FORMAT,
            sha256=chapter.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=chapter.citation_path,
            parent_citation_path=chapter.agency.citation_path,
            heading=chapter.heading,
            body=None,
            version=version,
            source_url=chapter.source_url,
            source_path=chapter.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=3,
            ordinal=chapter.ordinal,
            kind="chapter",
            legal_identifier=(
                f"{chapter.agency.title.number}VAC"
                f"{chapter.agency.number}-{chapter.number}"
            ),
            metadata=metadata,
        )
    )


def _append_section(
    detail: _VacSectionDetail,
    *,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> None:
    stub = detail.stub
    metadata = {
        "kind": "section",
        "title_number": stub.chapter.agency.title.number,
        "agency_number": stub.chapter.agency.number,
        "chapter_number": stub.chapter.number,
        "section_number": stub.number,
        "part_number": stub.part_number,
        "part_name": stub.part_name,
        "article_number": stub.article_number,
        "article_name": stub.article_name,
        "authority": detail.authority,
        "historical_note": detail.historical_note,
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "")}
    inventory.append(
        SourceInventoryItem(
            citation_path=stub.citation_path,
            source_url=stub.source_url,
            source_path=detail.source_key,
            source_format=VIRGINIA_VAC_SOURCE_FORMAT,
            sha256=detail.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=stub.citation_path,
            parent_citation_path=stub.chapter.citation_path,
            heading=stub.heading,
            body=detail.body,
            version=version,
            source_url=stub.source_url,
            source_path=detail.source_key,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=4,
            ordinal=stub.ordinal,
            kind="section",
            legal_identifier=stub.legal_identifier,
            citation_label=stub.legal_identifier,
            identifiers={"vac": stub.legal_identifier},
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
        jurisdiction="us-va",
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
        source_format=VIRGINIA_VAC_SOURCE_FORMAT,
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


def _load_section_details(
    stubs: list[_VacSectionStub],
    *,
    store: CorpusArtifactStore,
    run_id: str,
    source_root: Path | None,
    download_root: Path | None,
    workers: int,
    progress_stream: TextIO | None,
) -> tuple[_VacSectionDetail, ...]:
    if not stubs:
        return ()
    workers = max(1, workers)
    if workers == 1:
        details = [
            _load_section_detail(
                stub,
                store=store,
                run_id=run_id,
                source_root=source_root,
                download_root=download_root,
            )
            for stub in stubs
        ]
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            details = list(
                executor.map(
                    lambda stub: _load_section_detail(
                        stub,
                        store=store,
                        run_id=run_id,
                        source_root=source_root,
                        download_root=download_root,
                    ),
                    stubs,
                )
            )
    _progress(progress_stream, f"virginia-vac section details {len(details)}")
    return tuple(details)


def _load_section_detail(
    stub: _VacSectionStub,
    *,
    store: CorpusArtifactStore,
    run_id: str,
    source_root: Path | None,
    download_root: Path | None,
) -> _VacSectionDetail:
    if not _has_section_detail_endpoint(stub.number):
        return _section_detail_from_stub(stub)
    section_number, point, colon = _section_detail_parts(stub.number)
    try:
        snapshot = _snapshot_json_source(
            store,
            run_id=run_id,
            relative_name=(
                f"virginia-vac-json/title-{_path_token(stub.chapter.agency.title.number)}/"
                f"agency-{_path_token(stub.chapter.agency.number)}/"
                f"chapter-{_path_token(stub.chapter.number)}/"
                f"section-{_path_token(stub.number)}.json"
            ),
            url=_api_url(
                "AdministrativeCodeGetSectionDetailsXml",
                stub.chapter.agency.title.number,
                stub.chapter.agency.number,
                stub.chapter.number,
                section_number,
                point,
                colon,
            ),
            source_root=source_root,
            download_root=download_root,
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 400:
            return _section_detail_from_stub(stub)
        raise
    payload = _single_section_payload(
        snapshot.payload,
        title_number=stub.chapter.agency.title.number,
        agency_number=stub.chapter.agency.number,
        chapter_number=stub.chapter.number,
        section_number=stub.number,
    )
    return _VacSectionDetail(
        stub=stub,
        body=_html_fragment_to_text(payload.get("Body")),
        authority=_html_fragment_to_text(payload.get("Authority")),
        historical_note=_html_fragment_to_text(payload.get("HistoricalNote")),
        source_key=snapshot.source_key,
        source_path=snapshot.source_path,
        sha256=snapshot.sha256,
    )


def _section_detail_from_stub(stub: _VacSectionStub) -> _VacSectionDetail:
    return _VacSectionDetail(
        stub=stub,
        body=stub.body,
        authority=stub.authority,
        historical_note=stub.historical_note,
        source_key=stub.source_key,
        source_path=stub.source_path,
        sha256=stub.sha256,
    )


def _snapshot_json_source(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    relative_name: str,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
) -> _SourceSnapshot:
    data = _load_source_bytes(
        relative_name,
        url=url,
        source_root=source_root,
        download_root=download_root,
    )
    artifact_path = store.source_path("us-va", DocumentClass.REGULATION, run_id, relative_name)
    sha = store.write_bytes(artifact_path, data)
    source_key = f"sources/us-va/regulation/{run_id}/{relative_name}"
    return _SourceSnapshot(
        payload=json.loads(data.decode("utf-8-sig")),
        source_key=source_key,
        source_path=artifact_path,
        sha256=sha,
    )


def _load_source_bytes(
    relative_name: str,
    *,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
) -> bytes:
    if source_root is not None:
        path = source_root / relative_name
        if not path.exists():
            raise FileNotFoundError(path)
        return path.read_bytes()
    if download_root is not None:
        cached = download_root / relative_name
        if cached.exists():
            return cached.read_bytes()
    response = requests.get(
        url,
        headers={
            "User-Agent": VIRGINIA_VAC_USER_AGENT,
            "Accept": "application/json,text/json,*/*;q=0.8",
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.content
    if download_root is not None:
        path = download_root / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def _single_title_payload(payload: Any, *, title_number: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("expected title payload mapping")
    if str(payload.get("TitleNumber") or "") != str(title_number):
        raise ValueError(f"unexpected title payload for title {title_number}")
    return payload


def _single_agency_payload(
    payload: Any,
    *,
    title_number: str,
    agency_number: str,
) -> Mapping[str, Any]:
    title_payload = _single_title_payload(payload, title_number=title_number)
    agencies = _require_list(title_payload.get("AgencyList"), "agency payload")
    for agency in agencies:
        if isinstance(agency, Mapping) and str(agency.get("AgencyNumber") or "") == str(
            agency_number
        ):
            return agency
    raise ValueError(f"missing Virginia agency {title_number}VAC{agency_number}")


def _single_chapter_payload(
    payload: Any,
    *,
    title_number: str,
    agency_number: str,
    chapter_number: str,
) -> Mapping[str, Any]:
    agency_payload = _single_agency_payload(
        payload,
        title_number=title_number,
        agency_number=agency_number,
    )
    chapters = _require_list(agency_payload.get("ChapterList"), "chapter payload")
    for chapter in chapters:
        if isinstance(chapter, Mapping) and str(chapter.get("ChapterNumber") or "") == str(
            chapter_number
        ):
            return chapter
    raise ValueError(f"missing Virginia chapter {title_number}VAC{agency_number}-{chapter_number}")


def _single_section_payload(
    payload: Any,
    *,
    title_number: str,
    agency_number: str,
    chapter_number: str,
    section_number: str,
) -> Mapping[str, Any]:
    chapter_payload = _single_chapter_payload(
        payload,
        title_number=title_number,
        agency_number=agency_number,
        chapter_number=chapter_number,
    )
    sections = _require_list(chapter_payload.get("Sections"), "section payload")
    for section in sections:
        if isinstance(section, Mapping) and str(section.get("SectionNumber") or "") == str(
            section_number
        ):
            return section
    raise ValueError(
        f"missing Virginia section {title_number}VAC{agency_number}-{chapter_number}-{section_number}"
    )


def _require_list(value: Any, label: str) -> list[Any]:
    if isinstance(value, list):
        return value
    raise ValueError(f"expected {label} to be a list")


def _api_url(operation: str, *parts: str) -> str:
    suffix = "/".join(quote(str(part), safe="") for part in parts)
    if suffix:
        return f"{VIRGINIA_VAC_API_BASE_URL}/{operation}/{suffix}"
    return f"{VIRGINIA_VAC_API_BASE_URL}/{operation}"


def _section_detail_parts(section_number: str) -> tuple[str, str, str]:
    base = section_number.strip()
    colon = "0"
    point = "0"
    if ":" in base:
        base, colon = base.split(":", 1)
    if "." in base:
        base, point = base.split(".", 1)
    return base or "0", point or "0", colon or "0"


def _has_section_detail_endpoint(section_number: str) -> bool:
    return bool(re.match(r"^\d", section_number.strip()))


def _html_fragment_to_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    soup = BeautifulSoup(value, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for table in soup.find_all("table"):
        if isinstance(table, Tag):
            table.replace_with("\n" + _table_text(table) + "\n")
    text = soup.get_text(" ", strip=True)
    return _clean_multiline_text(text) or None


def _table_text(table: Tag) -> str:
    rows: list[str] = []
    for tr in table.find_all("tr"):
        cells = [
            _clean_text(cell.get_text(" ", strip=True))
            for cell in tr.find_all(["th", "td"])
            if _clean_text(cell.get_text(" ", strip=True))
        ]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _clean_multiline_text(value: str) -> str:
    lines = [_clean_text(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clean_optional(value: object) -> str | None:
    text = _clean_text(str(value)) if value is not None else ""
    return text or None


def _path_token(value: str) -> str:
    token = _clean_text(str(value)).lower()
    token = token.replace("/", "-").replace("\\", "-").replace(":", "-").replace(" ", "-")
    return safe_segment(token)


def _same_token(left: str, right: str) -> bool:
    return _path_token(left) == _path_token(right)


def _date_text(value: date | str | None, fallback: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value or fallback


def _progress(stream: TextIO | None, message: str) -> None:
    if stream is None:
        return
    print(message, file=stream, flush=True)


if __name__ == "__main__":  # pragma: no cover
    extract_virginia_vac(
        CorpusArtifactStore(Path("data/corpus")),
        version=date.today().isoformat(),
        progress_stream=sys.stderr,
    )
