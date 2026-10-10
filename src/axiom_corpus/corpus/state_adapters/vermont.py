"""Vermont Statutes Online source-first corpus adapter."""

from __future__ import annotations

import json
import re
import time
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urljoin

import fitz
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib3.exceptions import InsecureRequestWarning

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

VERMONT_STATUTES_BASE_URL = "https://legislature.vermont.gov/"
VERMONT_CHAPTER_151_INDEX_URL = "https://legislature.vermont.gov/statutes/chapter/32/151"
VERMONT_CHAPTER_151_FULL_URL = "https://legislature.vermont.gov/statutes/fullchapter/32/151"
VERMONT_2026_ACTS_REGISTRY_URL = (
    "https://legislature.vermont.gov/bill/loadBillActsAffectingStatutes/2026"
)
VERMONT_ACT_152_URL = (
    "https://legislature.vermont.gov/Documents/2026/Docs/ACTS/ACT152/ACT152%20As%20Enacted.pdf"
)
VERMONT_ACT_164_URL = (
    "https://legislature.vermont.gov/Documents/2026/Docs/ACTS/ACT164/ACT164%20As%20Enacted.pdf"
)
VERMONT_STATUTES_SOURCE_FORMAT = "vermont-statutes-online-html"
VERMONT_ACTS_REGISTRY_SOURCE_FORMAT = "vermont-acts-affecting-statutes-json"
VERMONT_SESSION_LAW_SOURCE_FORMAT = "vermont-session-law-pdf"
VERMONT_USER_AGENT = "axiom-corpus/0.1 (contact@axiom-foundation.org)"

_SECTION_HREF_RE = re.compile(r"/statutes/section/32/151/(?P<section>[0-9a-z]+)$", re.I)
_SECTION_HEADING_RE = re.compile(
    r"^§{1,2}\s*(?P<section>\d+[a-z]*)(?P<tail>.*)$",
    re.I | re.S,
)
_ACT_SECTION_RE = re.compile(
    r"^\s*Sec\.\s+(?P<act_section>\d+[a-z]?)\.\s+"
    r"32\s+V\.S\.A\.\s+§\s*(?P<section>\d+[a-z]*)\b",
    re.I | re.M,
)
_NEXT_ACT_SECTION_RE = re.compile(r"^\s*Sec\.\s+\d+[a-z]?\.", re.I | re.M)
_EXPECTED_2026_ACT_ENTRIES = {
    ("152", "5930bb"),
    ("164", "5811"),
    ("164", "5822"),
    ("164", "5823"),
    ("164", "5824"),
    ("164", "5916"),
    ("164", "5930ee"),
    ("164", "5930ii"),
    ("164", "5930u"),
}
_ACT_EFFECTS: dict[tuple[str, str], dict[str, Any]] = {
    ("164", "1"): {
        "status": "operative",
        "effective_date": "2025-01-01",
        "applies_to": "taxable years beginning on and after 2025-01-01",
        "legal_effect": "section repealed",
    },
    ("164", "17"): {
        "status": "operative",
        "effective_date": "2026-06-18",
        "legal_effect": "affordable-housing credit allocation amended",
    },
    ("164", "55"): {
        "status": "operative",
        "effective_date": "2026-01-01",
        "applies_to": "taxable years beginning on and after 2025-01-01",
        "legal_effect": "federal income-tax decoupling amendments",
    },
    ("164", "55a"): {
        "status": "operative",
        "effective_date": "2026-01-01",
        "applies_to": "taxable years beginning on and after 2026-01-01",
        "legal_effect": "IRC section 1202(a) decoupling amendment",
    },
    ("164", "56"): {
        "status": "operative",
        "effective_date": "2026-01-01",
        "applies_to": "taxable years beginning on and after 2025-01-01",
        "legal_effect": "adjusted-gross-income apportionment definition amended",
    },
    ("164", "57"): {
        "status": "operative",
        "effective_date": "2026-01-01",
        "applies_to": "taxable years beginning on and after 2025-01-01",
        "legal_effect": "nonresident Vermont-income computation amended",
    },
    ("164", "58"): {
        "status": "future",
        "effective_date": "2027-01-01",
        "applies_to": "taxable years beginning on and after 2027-01-01",
        "legal_effect": "research-and-development credit percentage amendment",
    },
    ("164", "59"): {
        "status": "operative",
        "effective_date": "2026-06-18",
        "legal_effect": "annual downtown-credit award limitation amended",
    },
    ("164", "60"): {
        "status": "operative",
        "effective_date": "2026-01-01",
        "applies_to": "taxable years beginning on and after 2025-01-01",
        "legal_effect": "federal income-tax link-up advanced through 2025-12-31",
    },
    ("152", "19"): {
        "status": "operative",
        "effective_date": "2026-07-01",
        "legal_effect": "downtown-credit eligibility and administration amended",
    },
}


@dataclass(frozen=True)
class VermontSubchapter:
    number: str
    heading: str
    ordinal: int

    @property
    def citation_path(self) -> str:
        return f"us-vt/statute/chapter-151-subchapter-{self.number.lower()}"


@dataclass(frozen=True)
class VermontSection:
    section: str
    heading: str
    body: str | None
    subchapter: str
    ordinal: int
    citation_path: str
    source_url: str
    status: str | None = None


@dataclass(frozen=True)
class VermontActOverlay:
    act_number: str
    act_section: str
    statute_section: str
    text: str


@dataclass(frozen=True)
class _SourceAsset:
    relative_path: str
    source_url: str
    source_format: str
    data: bytes


@dataclass(frozen=True)
class _RecordedSource:
    source_url: str
    source_path: str
    source_format: str
    sha256: str


class _VermontFetcher:
    def __init__(
        self,
        *,
        source_dir: Path | None,
        download_dir: Path | None,
        request_delay_seconds: float,
        timeout_seconds: float,
        request_attempts: int,
        verify_ssl: bool,
    ) -> None:
        self.source_dir = source_dir
        self.download_dir = download_dir
        self.request_delay_seconds = max(0.0, request_delay_seconds)
        self.timeout_seconds = timeout_seconds
        self.request_attempts = max(1, request_attempts)
        self.verify_ssl = verify_ssl
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": VERMONT_USER_AGENT})

    def fetch(
        self,
        relative_path: str,
        source_url: str,
        source_format: str,
    ) -> _SourceAsset:
        normalized = "/".join(safe_segment(part) for part in relative_path.split("/"))
        if self.source_dir is not None:
            data = (self.source_dir / normalized).read_bytes()
        elif self.download_dir is not None and (self.download_dir / normalized).exists():
            data = (self.download_dir / normalized).read_bytes()
        else:
            data = self._download(source_url)
            if self.download_dir is not None:
                _write_cache_bytes(self.download_dir / normalized, data)
        return _SourceAsset(normalized, source_url, source_format, data)

    def _download(self, source_url: str) -> bytes:
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.request_attempts + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.request_delay_seconds:
                time.sleep(self.request_delay_seconds - elapsed)
            try:
                with warnings.catch_warnings():
                    if not self.verify_ssl:
                        warnings.simplefilter("ignore", InsecureRequestWarning)
                    response = self._session.get(
                        source_url,
                        timeout=self.timeout_seconds,
                        verify=self.verify_ssl,
                    )
                self._last_request_at = time.monotonic()
                response.raise_for_status()
                return response.content
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.request_attempts:
                    time.sleep(min(2.0 * attempt, 8.0))
        assert last_error is not None
        raise last_error


def extract_vermont_statutes(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | int | None = None,
    only_chapter: str | int | None = None,
    limit: int | None = None,
    download_dir: str | Path | None = None,
    chapter_index_url: str = VERMONT_CHAPTER_151_INDEX_URL,
    full_chapter_url: str = VERMONT_CHAPTER_151_FULL_URL,
    acts_registry_url: str = VERMONT_2026_ACTS_REGISTRY_URL,
    act_152_url: str = VERMONT_ACT_152_URL,
    act_164_url: str = VERMONT_ACT_164_URL,
    request_delay_seconds: float = 0.1,
    timeout_seconds: float = 90.0,
    request_attempts: int = 3,
    verify_ssl: bool = True,
) -> StateStatuteExtractReport:
    """Snapshot Chapter 151 and overlay all 2026 acts affecting that chapter."""
    _validate_scope(only_title, only_chapter, limit)
    jurisdiction = "us-vt"
    run_id = f"{safe_segment(version)}-us-vt-title-32-chapter-151"
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    fetcher = _VermontFetcher(
        source_dir=Path(source_dir) if source_dir is not None else None,
        download_dir=Path(download_dir) if download_dir is not None else None,
        request_delay_seconds=request_delay_seconds,
        timeout_seconds=timeout_seconds,
        request_attempts=request_attempts,
        verify_ssl=verify_ssl,
    )
    assets = (
        fetcher.fetch(
            "vermont-legislature/title-32-chapter-151-index.html",
            chapter_index_url,
            VERMONT_STATUTES_SOURCE_FORMAT,
        ),
        fetcher.fetch(
            "vermont-legislature/title-32-chapter-151-full.html",
            full_chapter_url,
            VERMONT_STATUTES_SOURCE_FORMAT,
        ),
        fetcher.fetch(
            "vermont-legislature/2026-acts-affecting-statutes.json",
            acts_registry_url,
            VERMONT_ACTS_REGISTRY_SOURCE_FORMAT,
        ),
        fetcher.fetch(
            "vermont-legislature/2026-act-152-s325.pdf",
            act_152_url,
            VERMONT_SESSION_LAW_SOURCE_FORMAT,
        ),
        fetcher.fetch(
            "vermont-legislature/2026-act-164-h933.pdf",
            act_164_url,
            VERMONT_SESSION_LAW_SOURCE_FORMAT,
        ),
    )
    index_asset, full_asset, registry_asset, act_152_asset, act_164_asset = assets
    if not act_152_asset.data.startswith(b"%PDF") or not act_164_asset.data.startswith(b"%PDF"):
        raise ValueError("Vermont enacted-act snapshots must be PDFs")

    recorded = tuple(
        _record_source(store, jurisdiction=jurisdiction, run_id=run_id, source=source)
        for source in assets
    )
    index_source, full_source, registry_source, act_152_source, act_164_source = recorded
    subchapters, indexed_sections = parse_vermont_chapter_index(index_asset.data)
    full_subchapters, sections = parse_vermont_full_chapter(full_asset.data)
    if subchapters != full_subchapters:
        raise ValueError("Vermont Chapter 151 index/full-text subchapter closure mismatch")
    if tuple(section.section for section in indexed_sections) != tuple(
        section.section for section in sections
    ):
        raise ValueError("Vermont Chapter 151 index/full-text section closure mismatch")
    registry_entries = parse_vermont_2026_chapter_151_act_registry(registry_asset.data)
    if set(registry_entries) != _EXPECTED_2026_ACT_ENTRIES:
        raise ValueError(
            f"unexpected 2026 Vermont acts affecting Chapter 151: {sorted(set(registry_entries))}"
        )
    act_152_overlays = parse_vermont_act_pdf(act_152_asset.data, act_number="152")
    act_164_overlays = parse_vermont_act_pdf(act_164_asset.data, act_number="164")
    overlays = (*act_152_overlays, *act_164_overlays)
    overlay_entries = {(overlay.act_number, overlay.statute_section) for overlay in overlays}
    if overlay_entries != _EXPECTED_2026_ACT_ENTRIES:
        raise ValueError(f"Vermont enacted-act overlay closure mismatch: {sorted(overlay_entries)}")

    overlays_by_section: dict[str, list[VermontActOverlay]] = {}
    for overlay in overlays:
        overlays_by_section.setdefault(overlay.statute_section, []).append(overlay)

    source_components = [
        _component("chapter_index_closure", index_source),
        _component("complete_2025_session_codification", full_source),
        _component("complete_2026_chapter_151_act_registry", registry_source),
        _component("2026_act_152", act_152_source),
        _component("2026_act_164", act_164_source),
    ]
    shared_metadata: dict[str, Any] = {
        "scope": "complete 32 V.S.A. chapter 151",
        "scope_basis": (
            "official chapter index and complete chapter text through the 2025 session, "
            "closed through 2026 by the official acts-affecting-statutes registry and "
            "all identified enacted acts"
        ),
        "codification_vintage": "includes actions of the 2025 General Assembly session",
        "overlay_vintage": "2026 Acts and Resolves Nos. 152 and 164",
        "source_as_of": source_as_of_text,
        "source_components": source_components,
        "rate_authority": {
            "section": "32 V.S.A. § 5822",
            "rates_percent": ["3.35", "6.60", "7.60", "8.75"],
            "inflation_adjustment": (
                "taxable-income table amounts adjusted annually under § 5822(b)(2)"
            ),
            "minimum_tax_rule": (
                "for federal adjusted gross income above $150,000, greater of table tax "
                "or 3 percent of federal adjusted gross income"
            ),
        },
    }
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    ordinal = 0

    ordinal = _append_record(
        items,
        records,
        ordinal=ordinal,
        citation_path="us-vt/statute/title-32",
        body=None,
        heading="Taxation and Finance",
        kind="title",
        level=0,
        parent=None,
        source_id="title-32",
        legal_identifier="32 V.S.A.",
        source=index_source,
        version=run_id,
        source_as_of=source_as_of_text,
        expression_date=expression_date_text,
        metadata={**shared_metadata, "title": "32", "kind": "title"},
    )
    ordinal = _append_record(
        items,
        records,
        ordinal=ordinal,
        citation_path="us-vt/statute/chapter-151",
        body=None,
        heading="Income Taxes",
        kind="chapter",
        level=1,
        parent="us-vt/statute/title-32",
        source_id="chapter-151",
        legal_identifier="32 V.S.A. chapter 151",
        source=index_source,
        version=run_id,
        source_as_of=source_as_of_text,
        expression_date=expression_date_text,
        metadata={
            **shared_metadata,
            "title": "32",
            "chapter": "151",
            "kind": "chapter",
            "indexed_section_units": len(indexed_sections),
            "unique_section_urls": len({section.source_url for section in indexed_sections}),
            "subchapter_count": len(subchapters),
            "2026_affected_section_entries": len(registry_entries),
        },
    )
    for subchapter in subchapters:
        ordinal = _append_record(
            items,
            records,
            ordinal=ordinal,
            citation_path=subchapter.citation_path,
            body=None,
            heading=subchapter.heading,
            kind="subchapter",
            level=2,
            parent="us-vt/statute/chapter-151",
            source_id=f"subchapter-{subchapter.number.lower()}",
            legal_identifier=f"32 V.S.A. chapter 151, subchapter {subchapter.number}",
            source=index_source,
            version=run_id,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            metadata={
                **shared_metadata,
                "title": "32",
                "chapter": "151",
                "subchapter": subchapter.number,
                "kind": "subchapter",
            },
        )
        for section in (row for row in sections if row.subchapter == subchapter.number):
            section_overlays = overlays_by_section.get(section.section, [])
            metadata = {
                **shared_metadata,
                "title": "32",
                "chapter": "151",
                "subchapter": section.subchapter,
                "section": section.section,
                "kind": "section",
                **({"status": section.status} if section.status else {}),
            }
            if section.section == "5930ll":
                metadata["future_repeal_effective_date"] = "2030-07-01"
                if section.citation_path.endswith("--effective-2030-07-01"):
                    metadata["effective_date"] = "2030-07-01"
            body = section.body
            heading = section.heading
            if section_overlays:
                overlay_metadata = [
                    {
                        "act": f"2026 Act No. {overlay.act_number}",
                        "act_section": overlay.act_section,
                        **_ACT_EFFECTS[(overlay.act_number, overlay.act_section)],
                    }
                    for overlay in section_overlays
                ]
                metadata["2026_enacted_overlays"] = overlay_metadata
                metadata["body_basis"] = (
                    "2025-session codified text followed by verbatim PDF text-extraction "
                    "of each 2026 enacted amendment; strike/underline typography remains "
                    "authoritative in the persisted PDFs"
                )
                body = _overlay_body(section, section_overlays)
                if section.section == "5916":
                    heading = "Repealed—denial of tax credits for S corporations"
                    metadata["status"] = "repealed"
            ordinal = _append_record(
                items,
                records,
                ordinal=ordinal,
                citation_path=section.citation_path,
                body=body,
                heading=heading,
                kind="section",
                level=3,
                parent=subchapter.citation_path,
                source_id=section.citation_path.rsplit("/", 1)[-1],
                legal_identifier=f"32 V.S.A. § {section.section}",
                source=full_source,
                version=run_id,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                metadata=metadata,
            )

    inventory_path = store.inventory_path(jurisdiction, DocumentClass.STATUTE, run_id)
    provisions_path = store.provisions_path(jurisdiction, DocumentClass.STATUTE, run_id)
    coverage_path = store.coverage_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_inventory(inventory_path, items)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction=jurisdiction,
        document_class=DocumentClass.STATUTE.value,
        version=run_id,
    )
    store.write_json(coverage_path, coverage.to_mapping())
    return StateStatuteExtractReport(
        jurisdiction=jurisdiction,
        title_count=1,
        container_count=2 + len(subchapters),
        section_count=len(sections),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(
            store.source_path(jurisdiction, DocumentClass.STATUTE, run_id, asset.relative_path)
            for asset in assets
        ),
    )


def parse_vermont_chapter_index(
    html: str | bytes,
) -> tuple[tuple[VermontSubchapter, ...], tuple[VermontSection, ...]]:
    """Parse Chapter 151's subchapter and section closure index."""
    soup = BeautifulSoup(html, "lxml")
    subchapters: list[VermontSubchapter] = []
    sections: list[VermontSection] = []
    current_subchapter: str | None = None
    duplicate_counts: dict[str, int] = {}
    for ul in soup.select("ul.statutes-list"):
        marker = ul.find("strong")
        if marker is None or "Subchapter" not in marker.get_text(" ", strip=True):
            continue
        number_tag = marker.select_one("span.dirty")
        heading_tag = marker.select_one("span.caps")
        if number_tag is None or heading_tag is None:
            raise ValueError("malformed Vermont subchapter marker")
        current_subchapter = _clean_text(number_tag.get_text()).upper()
        subchapters.append(
            VermontSubchapter(
                current_subchapter,
                _clean_text(heading_tag.get_text(" ", strip=True)),
                len(subchapters) + 1,
            )
        )
        for anchor in ul.select('a[href*="/statutes/section/32/151/"]'):
            href = str(anchor.get("href") or "")
            match = _SECTION_HREF_RE.search(href)
            if match is None:
                continue
            section = match.group("section").lstrip("0").lower()
            display = _clean_text(anchor.get_text(" ", strip=True))
            heading_match = _SECTION_HEADING_RE.match(display)
            if heading_match is None:
                raise ValueError(f"unrecognized Vermont section index label: {display!r}")
            duplicate_counts[section] = duplicate_counts.get(section, 0) + 1
            suffix = ""
            if duplicate_counts[section] > 1:
                suffix = "--effective-2030-07-01"
            heading = heading_match.group("tail").lstrip(" .–—-")
            sections.append(
                VermontSection(
                    section=section,
                    heading=heading,
                    body=None,
                    subchapter=current_subchapter,
                    ordinal=len(sections) + 1,
                    citation_path=f"us-vt/statute/32-{section}{suffix}",
                    source_url=urljoin(VERMONT_STATUTES_BASE_URL, href),
                    status=_section_status(
                        section,
                        display,
                        duplicate_ordinal=duplicate_counts[section],
                    ),
                )
            )
    if not subchapters or not sections:
        raise ValueError("official Vermont Chapter 151 index has no provisions")
    return tuple(subchapters), tuple(sections)


def parse_vermont_full_chapter(
    html: str | bytes,
) -> tuple[tuple[VermontSubchapter, ...], tuple[VermontSection, ...]]:
    """Parse the complete Chapter 151 HTML in official display order."""
    soup = BeautifulSoup(html, "lxml")
    subchapters: list[VermontSubchapter] = []
    sections: list[VermontSection] = []
    duplicate_counts: dict[str, int] = {}
    for ul in soup.select("ul.statutes-list"):
        marker = ul.find("strong", recursive=False) or ul.find("strong")
        if marker is None or "Subchapter" not in marker.get_text(" ", strip=True):
            continue
        number_tag = marker.select_one("span.dirty")
        heading_tag = marker.select_one("span.caps")
        if number_tag is None or heading_tag is None:
            raise ValueError("malformed Vermont full-chapter subchapter marker")
        subchapter = _clean_text(number_tag.get_text()).upper()
        subchapters.append(
            VermontSubchapter(
                subchapter,
                _clean_text(heading_tag.get_text(" ", strip=True)),
                len(subchapters) + 1,
            )
        )
        for item in ul.find_all("li", recursive=False):
            bold = item.find("b")
            if bold is None:
                continue
            display = _clean_text(bold.get_text(" ", strip=True))
            match = _SECTION_HEADING_RE.match(display)
            if match is None:
                continue
            section = match.group("section").lower()
            duplicate_counts[section] = duplicate_counts.get(section, 0) + 1
            suffix = "--effective-2030-07-01" if duplicate_counts[section] > 1 else ""
            heading = match.group("tail").lstrip(" .–—-")
            body = _section_body(item, bold)
            sections.append(
                VermontSection(
                    section=section,
                    heading=heading,
                    body=body,
                    subchapter=subchapter,
                    ordinal=len(sections) + 1,
                    citation_path=f"us-vt/statute/32-{section}{suffix}",
                    source_url=(
                        f"https://legislature.vermont.gov/statutes/section/32/151/"
                        f"{section.zfill(5)}"
                    ),
                    status=_section_status(
                        section,
                        display,
                        duplicate_ordinal=duplicate_counts[section],
                    ),
                )
            )
    if not subchapters or not sections:
        raise ValueError("official Vermont full Chapter 151 has no provisions")
    return tuple(subchapters), tuple(sections)


def parse_vermont_2026_chapter_151_act_registry(
    data: str | bytes,
) -> tuple[tuple[str, str], ...]:
    """Return unique Act/section pairs affecting Chapter 151 in 2026."""
    payload = json.loads(data)
    entries: list[tuple[str, str]] = []
    for row in payload.get("data", []):
        if (
            str(row.get("TitleNumber")) != "32"
            or str(row.get("Chapter")) != "(Ch. 151)"
            or str(row.get("Year")) != "2026"
        ):
            continue
        citation = BeautifulSoup(str(row.get("Citation", "")), "lxml").get_text(" ")
        match = re.search(r"§\s*(\d+[a-z]*)", citation, re.I)
        if match is None:
            raise ValueError(f"unrecognized Vermont acts-registry citation: {citation!r}")
        entry = (str(row.get("ActNo")), match.group(1).lower())
        if entry not in entries:
            entries.append(entry)
    if not entries:
        raise ValueError("Vermont acts registry contains no 2026 Chapter 151 entries")
    return tuple(entries)


def parse_vermont_act_pdf(data: bytes, *, act_number: str) -> tuple[VermontActOverlay, ...]:
    """Extract Chapter 151 amendment blocks from an enacted Vermont act PDF."""
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # pragma: no cover - fitz error types vary by version
        raise ValueError(f"invalid Vermont Act {act_number} PDF") from exc
    text = "\n".join(page.get_text("text") for page in document)
    return parse_vermont_act_text(text, act_number=act_number)


def parse_vermont_act_text(text: str, *, act_number: str) -> tuple[VermontActOverlay, ...]:
    """Extract Chapter 151 amendment blocks from enacted-act plain text."""
    overlays: list[VermontActOverlay] = []
    if act_number == "164":
        repeal = re.search(
            r"Sec\.\s+1\.\s+REPEAL\s+32\s+V\.S\.A\.\s+§\s*5916"
            r"(?P<text>.*?)(?=^\s*Sec\.\s+2\.)",
            text,
            re.I | re.M | re.S,
        )
        if repeal is None:
            raise ValueError("Vermont Act 164 section 5916 repeal not found")
        overlays.append(
            VermontActOverlay(
                "164",
                "1",
                "5916",
                _clean_act_text("Sec. 1. REPEAL 32 V.S.A. § 5916" + repeal.group("text")),
            )
        )
    for match in _ACT_SECTION_RE.finditer(text):
        statute_section = match.group("section").lower()
        if statute_section not in {
            "5811",
            "5822",
            "5823",
            "5824",
            "5930bb",
            "5930ee",
            "5930ii",
            "5930u",
        }:
            continue
        next_match = _NEXT_ACT_SECTION_RE.search(text, match.end())
        end = next_match.start() if next_match is not None else len(text)
        overlays.append(
            VermontActOverlay(
                act_number,
                match.group("act_section"),
                statute_section,
                _clean_act_text(text[match.start() : end]),
            )
        )
    if not overlays:
        raise ValueError(f"Vermont Act {act_number} contains no Chapter 151 overlays")
    return tuple(overlays)


def _append_record(
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    *,
    ordinal: int,
    citation_path: str,
    body: str | None,
    heading: str,
    kind: str,
    level: int,
    parent: str | None,
    source_id: str,
    legal_identifier: str,
    source: _RecordedSource,
    version: str,
    source_as_of: str,
    expression_date: str,
    metadata: dict[str, Any],
) -> int:
    ordinal += 1
    items.append(
        SourceInventoryItem(
            citation_path=citation_path,
            source_url=source.source_url,
            source_path=source.source_path,
            source_format=source.source_format,
            sha256=source.sha256,
            metadata=metadata,
        )
    )
    identifiers = {"vermont:title": "32"}
    if level >= 1:
        identifiers["vermont:chapter"] = "151"
    if kind == "subchapter":
        identifiers["vermont:subchapter"] = str(metadata["subchapter"])
    if kind == "section":
        identifiers["vermont:section"] = str(metadata["section"])
    records.append(
        ProvisionRecord(
            id=deterministic_provision_id(citation_path),
            jurisdiction="us-vt",
            document_class=DocumentClass.STATUTE.value,
            citation_path=citation_path,
            body=body,
            heading=heading,
            citation_label=legal_identifier,
            version=version,
            source_url=source.source_url,
            source_path=source.source_path,
            source_id=source_id,
            source_format=source.source_format,
            source_as_of=source_as_of,
            expression_date=expression_date,
            parent_citation_path=parent,
            parent_id=deterministic_provision_id(parent) if parent else None,
            level=level,
            ordinal=ordinal,
            kind=kind,
            legal_identifier=legal_identifier,
            identifiers=identifiers,
            metadata=metadata,
        )
    )
    return ordinal


def _section_body(item: Tag, heading: Tag) -> str | None:
    parts: list[str] = []
    for child in item.find_all(["p", "table"], recursive=True):
        if child is heading or heading in child.descendants:
            continue
        if child.name == "p" and child.find_parent("table") is not None:
            continue
        text = _clean_text(child.get_text(" ", strip=True))
        if text and (not parts or text != parts[-1]):
            parts.append(text)
    return "\n\n".join(parts) or None


def _overlay_body(section: VermontSection, overlays: list[VermontActOverlay]) -> str:
    parts: list[str] = []
    if section.section == "5916":
        parts.append(
            "[Repealed by 2026 Act No. 164, Sec. 1, retroactive to January 1, 2025, "
            "for taxable years beginning on and after that date.]"
        )
        if section.body:
            parts.append(f"[Prior codified text through the 2025 session]\n{section.body}")
    elif section.body:
        parts.append(section.body)
    for overlay in overlays:
        effect = _ACT_EFFECTS[(overlay.act_number, overlay.act_section)]
        parts.append(
            f"[2026 enacted overlay — Act No. {overlay.act_number}, Sec. "
            f"{overlay.act_section}; {effect['status']}; effective "
            f"{effect['effective_date']}]\n{overlay.text}"
        )
    return "\n\n".join(parts)


def _component(role: str, source: _RecordedSource) -> dict[str, str]:
    return {
        "role": role,
        "source_url": source.source_url,
        "source_path": source.source_path,
        "source_format": source.source_format,
        "sha256": source.sha256,
    }


def _record_source(
    store: CorpusArtifactStore,
    *,
    jurisdiction: str,
    run_id: str,
    source: _SourceAsset,
) -> _RecordedSource:
    path = store.source_path(
        jurisdiction,
        DocumentClass.STATUTE,
        run_id,
        source.relative_path,
    )
    sha256 = store.write_bytes(path, source.data)
    return _RecordedSource(
        source_url=source.source_url,
        source_path=_state_source_key(jurisdiction, run_id, source.relative_path),
        source_format=source.source_format,
        sha256=sha256,
    )


def _state_source_key(jurisdiction: str, run_id: str, relative_path: str) -> str:
    return f"sources/{jurisdiction}/{DocumentClass.STATUTE.value}/{run_id}/{relative_path}"


def _validate_scope(
    only_title: str | int | None,
    only_chapter: str | int | None,
    limit: int | None,
) -> None:
    if str(only_title).lstrip("0") != "32":
        raise ValueError("Vermont adapter requires only_title=32")
    if str(only_chapter).lstrip("0") != "151":
        raise ValueError("Vermont adapter requires only_chapter=151")
    if limit is not None:
        raise ValueError("Vermont Chapter 151 closure extraction does not support limit")


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _section_status(section: str, display: str, *, duplicate_ordinal: int) -> str | None:
    if section == "5930ll":
        return "operative" if duplicate_ordinal == 1 else "future_repeal"
    return "repealed" if "repealed" in display.lower() else None


def _clean_act_text(value: str) -> str:
    value = re.sub(r"No\.\s+\d+\s+Page\s+\d+\s+of\s+\d+\s+2026", " ", value)
    value = re.sub(r"VT LEG #[^\n]+", " ", value)
    return _clean_text(value)


def _write_cache_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
