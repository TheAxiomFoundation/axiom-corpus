"""Mississippi income-tax statute recovery from official session-law sources."""

from __future__ import annotations

import re
import time
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

MISSISSIPPI_HB1_HTML_URL = (
    "https://billstatus.ls.state.ms.us/documents/2025/html/HB/0001-0099/HB0001SG.htm"
)
MISSISSIPPI_HB1_PDF_URL = (
    "https://billstatus.ls.state.ms.us/documents/2025/pdf/HB/0001-0099/HB0001SG.pdf"
)
MISSISSIPPI_HB1_SIGNING_URL = (
    "https://governorreeves.ms.gov/"
    "gov-reeves-signs-historic-legislation-eliminating-mississippis-individual-income-tax/"
)
MISSISSIPPI_DOR_RATES_URL = "https://www.dor.ms.gov/general-information"
MISSISSIPPI_SESSION_LAW_SOURCE_FORMAT = "mississippi-legislature-session-law-html"
MISSISSIPPI_SESSION_LAW_PDF_SOURCE_FORMAT = "mississippi-legislature-session-law-pdf"
MISSISSIPPI_SIGNING_SOURCE_FORMAT = "mississippi-governor-signing-html"
MISSISSIPPI_RATE_SOURCE_FORMAT = "mississippi-dor-rate-guidance-html"
MISSISSIPPI_USER_AGENT = "axiom-corpus/0.1 (contact@axiom-foundation.org)"

_SECTION_1_RE = re.compile(
    r"^SECTION\s+1\.\s+Section\s+27-7-5,\s+Mississippi Code of 1972,\s+is amended",
    re.I,
)
_SECTION_2_RE = re.compile(r"^SECTION\s+2\.", re.I)
_SECTION_30_RE = re.compile(r"^SECTION\s+30\s*\.", re.I)


@dataclass(frozen=True)
class _MississippiSource:
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


@dataclass(frozen=True)
class MississippiRateAuthority:
    """Operative annual rate confirmed by official Department of Revenue guidance."""

    tax_year: int
    zero_rate_threshold: int
    excess_rate_percent: str


class _MississippiFetcher:
    def __init__(
        self,
        *,
        source_dir: Path | None,
        download_dir: Path | None,
        request_delay_seconds: float,
        timeout_seconds: float,
        request_attempts: int,
    ) -> None:
        self.source_dir = source_dir
        self.download_dir = download_dir
        self.request_delay_seconds = max(0.0, request_delay_seconds)
        self.timeout_seconds = timeout_seconds
        self.request_attempts = max(1, request_attempts)
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": MISSISSIPPI_USER_AGENT})

    def fetch(
        self,
        relative_path: str,
        source_url: str,
        source_format: str,
        *,
        verify_ssl: bool = True,
    ) -> _MississippiSource:
        relative_path = "/".join(safe_segment(part) for part in relative_path.split("/"))
        if self.source_dir is not None:
            data = (self.source_dir / relative_path).read_bytes()
        elif self.download_dir is not None and (self.download_dir / relative_path).exists():
            data = (self.download_dir / relative_path).read_bytes()
        else:
            data = self._download(source_url, verify_ssl=verify_ssl)
            if self.download_dir is not None:
                _write_cache_bytes(self.download_dir / relative_path, data)
        return _MississippiSource(relative_path, source_url, source_format, data)

    def _download(self, source_url: str, *, verify_ssl: bool) -> bytes:
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.request_attempts + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.request_delay_seconds:
                time.sleep(self.request_delay_seconds - elapsed)
            try:
                with warnings.catch_warnings():
                    if not verify_ssl:
                        warnings.simplefilter("ignore", InsecureRequestWarning)
                    response = self._session.get(
                        source_url,
                        timeout=self.timeout_seconds,
                        verify=verify_ssl,
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


def extract_mississippi_income_tax_statute(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | int | None = None,
    limit: int | None = None,
    download_dir: str | Path | None = None,
    bill_html_url: str = MISSISSIPPI_HB1_HTML_URL,
    bill_pdf_url: str = MISSISSIPPI_HB1_PDF_URL,
    signing_url: str = MISSISSIPPI_HB1_SIGNING_URL,
    rate_guidance_url: str = MISSISSIPPI_DOR_RATES_URL,
    tax_year: int = 2026,
    request_delay_seconds: float = 0.05,
    timeout_seconds: float = 90.0,
    request_attempts: int = 3,
    legislature_verify_ssl: bool = True,
    dor_verify_ssl: bool = True,
) -> StateStatuteExtractReport:
    """Recover current section 27-7-5 from enacted HB 1 and official guidance.

    Mississippi's public Code section route is robot-blocked. This deliberately
    bounded adapter snapshots the Legislature's complete enacted replacement of
    section 27-7-5, together with official signing and annual-rate confirmation.
    """
    _validate_scope(only_title, limit)
    jurisdiction = "us-ms"
    run_id = f"{safe_segment(version)}-us-ms-section-27-7-5"
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    fetcher = _MississippiFetcher(
        source_dir=Path(source_dir) if source_dir is not None else None,
        download_dir=Path(download_dir) if download_dir is not None else None,
        request_delay_seconds=request_delay_seconds,
        timeout_seconds=timeout_seconds,
        request_attempts=request_attempts,
    )
    sources = (
        fetcher.fetch(
            "mississippi-legislature/2025-hb-1-sg.html",
            bill_html_url,
            MISSISSIPPI_SESSION_LAW_SOURCE_FORMAT,
            verify_ssl=legislature_verify_ssl,
        ),
        fetcher.fetch(
            "mississippi-legislature/2025-hb-1-sg.pdf",
            bill_pdf_url,
            MISSISSIPPI_SESSION_LAW_PDF_SOURCE_FORMAT,
            verify_ssl=legislature_verify_ssl,
        ),
        fetcher.fetch(
            "mississippi-governor/2025-hb-1-signing.html",
            signing_url,
            MISSISSIPPI_SIGNING_SOURCE_FORMAT,
        ),
        fetcher.fetch(
            "mississippi-department-of-revenue/2026-individual-income-tax-rates.html",
            rate_guidance_url,
            MISSISSIPPI_RATE_SOURCE_FORMAT,
            verify_ssl=dor_verify_ssl,
        ),
    )
    if not sources[1].data.startswith(b"%PDF"):
        raise ValueError("official Mississippi HB 1 PDF snapshot is not a PDF")

    body, effective_date = parse_mississippi_hb1_section_27_7_5(sources[0].data)
    signing_date = parse_mississippi_hb1_signing(sources[2].data)
    rate_authority = parse_mississippi_dor_rate_guidance(sources[3].data, tax_year=tax_year)
    if rate_authority.excess_rate_percent != "4":
        raise ValueError(f"unexpected Mississippi {tax_year} excess rate")

    recorded = tuple(
        _record_source(store, jurisdiction=jurisdiction, run_id=run_id, source=source)
        for source in sources
    )
    primary = recorded[0]
    components = [
        {
            "role": role,
            "source_url": source.source_url,
            "source_path": source.source_path,
            "source_format": source.source_format,
            "sha256": source.sha256,
        }
        for role, source in zip(
            ("enacted_section_text", "official_bill_pdf", "enactment_confirmation", "operative_rate"),
            recorded,
            strict=True,
        )
    ]
    law_vintage = {
        "legislature": "2025 Regular Session",
        "bill": "House Bill 1",
        "bill_text_version": "As Sent to Governor",
        "signed_date": signing_date,
        "effective_date": effective_date,
        "source_as_of": source_as_of_text,
    }
    shared_metadata: dict[str, Any] = {
        "scope": "Mississippi Code section 27-7-5 only",
        "scope_basis": "complete enacted replacement text in 2025 House Bill 1, Section 1",
        "public_code_access": "Lexis section text robot-blocked",
        "law_vintage": law_vintage,
        "operative_rate": {
            "tax_year": rate_authority.tax_year,
            "zero_rate_percent": "0",
            "zero_rate_threshold": rate_authority.zero_rate_threshold,
            "excess_rate_percent": rate_authority.excess_rate_percent,
        },
        "source_components": components,
    }
    title_path = "us-ms/statute/title-27"
    chapter_path = f"{title_path}/chapter-7"
    section_path = "us-ms/statute/27-7-5"
    rows = (
        (title_path, None, "Taxation and Finance", "title", 0, None, "title-27"),
        (chapter_path, None, "Income Tax and Withholding", "chapter", 1, title_path, "chapter-7"),
        (section_path, body, "Rate of tax", "section", 2, chapter_path, "27-7-5"),
    )
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for ordinal, (path, row_body, heading, kind, level, parent, source_id) in enumerate(rows, 1):
        metadata = dict(shared_metadata)
        metadata.update({"kind": kind, "title": "27"})
        if level >= 1:
            metadata["chapter"] = "7"
        if level == 2:
            metadata["section"] = "27-7-5"
        items.append(
            SourceInventoryItem(
                citation_path=path,
                source_url=primary.source_url,
                source_path=primary.source_path,
                source_format=primary.source_format,
                sha256=primary.sha256,
                metadata=metadata,
            )
        )
        legal_identifier = {
            "title": "Miss. Code Title 27",
            "chapter": "Miss. Code Title 27, Chapter 7",
            "section": "Miss. Code § 27-7-5",
        }[kind]
        records.append(
            ProvisionRecord(
                id=deterministic_provision_id(path),
                jurisdiction=jurisdiction,
                document_class=DocumentClass.STATUTE.value,
                citation_path=path,
                body=row_body,
                heading=heading,
                citation_label=legal_identifier,
                version=run_id,
                source_url=primary.source_url,
                source_path=primary.source_path,
                source_id=source_id,
                source_format=primary.source_format,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                parent_citation_path=parent,
                parent_id=deterministic_provision_id(parent) if parent else None,
                level=level,
                ordinal=ordinal,
                kind=kind,
                legal_identifier=legal_identifier,
                identifiers={
                    "mississippi:title": "27",
                    **({"mississippi:chapter": "7"} if level >= 1 else {}),
                    **({"mississippi:section": "27-7-5"} if level == 2 else {}),
                },
                metadata=metadata,
            )
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
        container_count=2,
        section_count=1,
        provisions_written=3,
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(
            store.source_path(jurisdiction, DocumentClass.STATUTE, run_id, source.relative_path)
            for source in sources
        ),
    )


def parse_mississippi_hb1_section_27_7_5(html: str | bytes) -> tuple[str, str]:
    """Return enacted section 27-7-5 text and its effective date from HB 1."""
    soup = BeautifulSoup(html, "lxml")
    for deletion in soup.find_all("s"):
        deletion.decompose()
    for bold in soup.find_all("b"):
        if re.fullmatch(r"(?:\s|\xa0|\*)+", bold.get_text()):
            bold.decompose()
    paragraphs = [_clean_text(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
    section_1 = next((i for i, text in enumerate(paragraphs) if _SECTION_1_RE.match(text)), None)
    if section_1 is None:
        raise ValueError("official Mississippi HB 1 Section 1 marker not found")
    start = next(
        (i for i in range(section_1 + 1, len(paragraphs)) if paragraphs[i].startswith("27-7-5.")),
        None,
    )
    if start is None:
        raise ValueError("Mississippi Code section 27-7-5 text not found in HB 1")
    end = next((i for i in range(start + 1, len(paragraphs)) if _SECTION_2_RE.match(paragraphs[i])), None)
    if end is None:
        raise ValueError("official Mississippi HB 1 Section 2 boundary not found")
    body_parts = paragraphs[start:end]
    body_parts[0] = re.sub(r"^27-7-5\.\s*", "", body_parts[0])
    body = "\n\n".join(part for part in body_parts if part)
    required = (
        "For calendar year 2026",
        "four percent (4%)",
        "For calendar year 2027",
        "three and three-quarters percent (3.75%)",
        "For calendar year 2030 and all calendar years thereafter",
    )
    if any(value not in body for value in required):
        raise ValueError("official Mississippi HB 1 section 27-7-5 text is incomplete")
    if "For calendar year 2026 and all calendar years thereafter" in body:
        raise ValueError("deleted Mississippi HB 1 text remained in enacted section")
    effective = next((text for text in paragraphs if _SECTION_30_RE.match(text)), "")
    if "Sections 1 through 13" not in effective or "July 1, 2025" not in effective:
        raise ValueError("official Mississippi HB 1 effective-date authority not found")
    return body, "2025-07-01"


def parse_mississippi_hb1_signing(html: str | bytes) -> str:
    """Validate the Governor's official HB 1 signing announcement."""
    text = _clean_text(BeautifulSoup(html, "lxml").get_text(" ", strip=True))
    if not re.search(r"Governor Tate Reeves today signed", text, re.I):
        raise ValueError("official Mississippi HB 1 signing confirmation not found")
    if not re.search(r"House Bill 1", text, re.I):
        raise ValueError("House Bill 1 not found in official signing confirmation")
    if not re.search(r"March 27, 2025", text, re.I):
        raise ValueError("Mississippi HB 1 signing date not found")
    return "2025-03-27"


def parse_mississippi_dor_rate_guidance(
    html: str | bytes,
    *,
    tax_year: int = 2026,
) -> MississippiRateAuthority:
    """Parse the official DOR annual rate table for the requested tax year."""
    text = _clean_text(BeautifulSoup(html, "lxml").get_text(" ", strip=True))
    match = re.search(
        rf"Tax Year\s+{tax_year}\s+Excess of \$10,000\s+of Taxable Income is taxed @\s*([0-9.]+)%",
        text,
        re.I,
    )
    if match is None:
        raise ValueError(f"Mississippi DOR tax-year {tax_year} rate row not found")
    if not re.search(r"0%\s+on the first \$10,000 of taxable income", text, re.I):
        raise ValueError("Mississippi DOR zero-rate threshold not found")
    return MississippiRateAuthority(
        tax_year=tax_year,
        zero_rate_threshold=10_000,
        excess_rate_percent=match.group(1).rstrip("0").rstrip("."),
    )


def _record_source(
    store: CorpusArtifactStore,
    *,
    jurisdiction: str,
    run_id: str,
    source: _MississippiSource,
) -> _RecordedSource:
    path = store.source_path(
        jurisdiction,
        DocumentClass.STATUTE,
        run_id,
        source.relative_path,
    )
    sha256 = store.write_bytes(path, source.data)
    source_path = (
        f"sources/{jurisdiction}/statute/{run_id}/{source.relative_path}"
    )
    return _RecordedSource(source.source_url, source_path, source.source_format, sha256)


def _validate_scope(only_title: str | int | None, limit: int | None) -> None:
    if only_title is not None and str(only_title).strip().lower() not in {
        "27-7-5",
        "section 27-7-5",
    }:
        raise ValueError("Mississippi session-law adapter only supports section 27-7-5")
    if limit is not None and limit < 1:
        raise ValueError("Mississippi section 27-7-5 scope requires limit >= 1")


def _clean_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\u200b", "").replace("\u00ad", "")
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+([,.;:])", r"\1", value)


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    return value.isoformat() if isinstance(value, date) else str(value)


def _write_cache_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
