"""North Dakota Century Code source-first corpus adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import fitz
import requests

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

NORTH_DAKOTA_CODE_INDEX_URL = "https://ndlegis.gov/cencode/t57c38.html"
NORTH_DAKOTA_CODE_PDF_URL = "https://ndlegis.gov/cencode/t57c38.pdf"
NORTH_DAKOTA_2026_INDIVIDUAL_SCHEDULE_URL = (
    "https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2025-iit/"
    "28709-form-nd-1es-2026.pdf"
)
NORTH_DAKOTA_2026_FIDUCIARY_SCHEDULE_URL = (
    "https://www.tax.nd.gov/sites/www/files/documents/forms/business/fiduciary/"
    "2025-fiduciary/28723-form-38-es-2026.pdf"
)
NORTH_DAKOTA_CODE_SOURCE_FORMAT = "north-dakota-century-code-pdf"
NORTH_DAKOTA_INDEX_SOURCE_FORMAT = "north-dakota-century-code-html"
NORTH_DAKOTA_SCHEDULE_SOURCE_FORMAT = "north-dakota-tax-commissioner-pdf"

_SECTION_HEADER_RE = re.compile(
    r"(?m)^(?P<section>57-38-\d+(?:\.\d+)*)\.\s+(?P<heading>[A-Z][^\n]+)$"
)
_INDEX_SECTION_RE = re.compile(r">\s*(?P<section>57-38-\d+(?:\.\d+)*)\s*</a>", re.I)
_REFERENCE_RE = re.compile(r"\b(?:section\s+)?(?P<section>57-38-\d+(?:\.\d+)*)\b", re.I)
_NUMBER_RE = re.compile(r"(?<![\d,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")


@dataclass(frozen=True)
class NorthDakotaSection:
    """One section parsed from the official chapter PDF."""

    section: str
    heading: str
    body: str
    ordinal: int
    references_to: tuple[str, ...] = ()
    status: str = "active"
    metadata: dict[str, Any] | None = None

    @property
    def citation_path(self) -> str:
        return f"us-nd/statute/57/{self.section}"

    @property
    def legal_identifier(self) -> str:
        return f"N.D.C.C. § {self.section}"


@dataclass(frozen=True)
class NorthDakotaRateBracket:
    """One row in a Tax Commissioner rate schedule."""

    over: str
    not_over: str | None
    base_tax: str
    rate: str
    amount_over: str


@dataclass(frozen=True)
class NorthDakotaRateSchedule:
    """One filing-status schedule prescribed under N.D.C.C. § 57-38-30.3(1)(g)."""

    subdivision: str
    heading: str
    brackets: tuple[NorthDakotaRateBracket, ...]


@dataclass(frozen=True)
class _SourceAsset:
    relative_path: str
    source_url: str
    data: bytes


class _NorthDakotaFetcher:
    def __init__(
        self,
        *,
        source_dir: Path | None,
        download_dir: Path | None,
        timeout_seconds: float,
        request_attempts: int,
    ) -> None:
        self.source_dir = source_dir
        self.download_dir = download_dir
        self.timeout_seconds = timeout_seconds
        self.request_attempts = max(1, request_attempts)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "axiom-corpus/0.1 (contact@axiom-foundation.org)"}
        )

    def fetch(self, relative_path: str, source_url: str) -> _SourceAsset:
        if self.source_dir is not None:
            path = self.source_dir / relative_path
            if not path.exists():
                raise ValueError(f"North Dakota source file does not exist: {path}")
            return _SourceAsset(relative_path, source_url, path.read_bytes())
        if self.download_dir is not None:
            path = self.download_dir / relative_path
            if path.exists():
                return _SourceAsset(relative_path, source_url, path.read_bytes())

        last_error: requests.RequestException | None = None
        for _attempt in range(self.request_attempts):
            try:
                response = self.session.get(source_url, timeout=self.timeout_seconds)
                response.raise_for_status()
                data = response.content
                break
            except requests.RequestException as exc:
                last_error = exc
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError(f"failed to fetch {source_url}")

        if self.download_dir is not None:
            path = self.download_dir / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return _SourceAsset(relative_path, source_url, data)


def extract_north_dakota_code(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | None = None,
    limit: int | None = None,
    download_dir: str | Path | None = None,
    code_index_url: str = NORTH_DAKOTA_CODE_INDEX_URL,
    code_pdf_url: str = NORTH_DAKOTA_CODE_PDF_URL,
    individual_schedule_url: str = NORTH_DAKOTA_2026_INDIVIDUAL_SCHEDULE_URL,
    fiduciary_schedule_url: str = NORTH_DAKOTA_2026_FIDUCIARY_SCHEDULE_URL,
    tax_year: int = 2026,
    timeout_seconds: float = 90.0,
    request_attempts: int = 3,
) -> StateStatuteExtractReport:
    """Snapshot chapter 57-38 and overlay the Commissioner's operative annual schedules."""
    scope = _scope_filter(only_title)
    run_id = f"{version}-us-nd-title-{scope}"
    if limit is not None:
        run_id = f"{run_id}-limit-{limit}"
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    fetcher = _NorthDakotaFetcher(
        source_dir=Path(source_dir) if source_dir is not None else None,
        download_dir=Path(download_dir) if download_dir is not None else None,
        timeout_seconds=timeout_seconds,
        request_attempts=request_attempts,
    )

    assets = (
        fetcher.fetch("north-dakota-century-code/chapter-57-38.html", code_index_url),
        fetcher.fetch("north-dakota-century-code/chapter-57-38.pdf", code_pdf_url),
        fetcher.fetch(
            f"north-dakota-tax-commissioner/{tax_year}-form-nd-1es.pdf",
            individual_schedule_url,
        ),
        fetcher.fetch(
            f"north-dakota-tax-commissioner/{tax_year}-form-38-es.pdf",
            fiduciary_schedule_url,
        ),
    )
    index_asset, code_asset, individual_asset, fiduciary_asset = assets
    persisted: dict[str, tuple[str, str]] = {}
    source_paths: list[Path] = []
    for asset in assets:
        path = store.source_path(
            "us-nd",
            DocumentClass.STATUTE,
            run_id,
            asset.relative_path,
        )
        sha256 = store.write_bytes(path, asset.data)
        source_paths.append(path)
        persisted[asset.relative_path] = (
            _state_source_key("us-nd", run_id, asset.relative_path),
            sha256,
        )

    indexed_sections = parse_north_dakota_index_html(index_asset.data)
    sections = parse_north_dakota_chapter_pdf(code_asset.data)
    parsed_sections = tuple(section.section for section in sections)
    if parsed_sections != indexed_sections:
        missing = sorted(set(indexed_sections) - set(parsed_sections))
        extra = sorted(set(parsed_sections) - set(indexed_sections))
        raise ValueError(
            "North Dakota chapter PDF does not match its official index: "
            f"missing={missing}, extra={extra}"
        )
    individual_schedules = parse_north_dakota_individual_rate_schedules(
        individual_asset.data
    )
    fiduciary_schedule = parse_north_dakota_fiduciary_rate_schedule(fiduciary_asset.data)
    schedules = (*individual_schedules, fiduciary_schedule)
    target_index = next(
        (index for index, section in enumerate(sections) if section.section == "57-38-30.3"),
        None,
    )
    if target_index is None:
        raise ValueError("North Dakota chapter source omits section 57-38-30.3")
    sections = list(sections)
    sections[target_index] = apply_north_dakota_rate_schedule_overlay(
        sections[target_index], schedules=schedules, tax_year=tax_year
    )
    if limit is not None:
        sections = sections[: max(0, limit)]

    index_source_path, index_sha = persisted[index_asset.relative_path]
    code_source_path, code_sha = persisted[code_asset.relative_path]
    individual_source_path, individual_sha = persisted[individual_asset.relative_path]
    fiduciary_source_path, fiduciary_sha = persisted[fiduciary_asset.relative_path]
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    _append_record(
        items,
        records,
        citation_path="us-nd/statute/57",
        version=run_id,
        source_url=index_asset.source_url,
        source_path=index_source_path,
        source_id="title-57",
        source_format=NORTH_DAKOTA_INDEX_SOURCE_FORMAT,
        sha256=index_sha,
        source_as_of=source_as_of_text,
        expression_date=expression_date_text,
        kind="title",
        body=None,
        heading="Taxation",
        legal_identifier="N.D.C.C. Title 57",
        parent_citation_path=None,
        level=0,
        ordinal=57,
        identifiers={"north_dakota:title": "57"},
        metadata={"kind": "title", "title": "57", "chapter_scope": "57-38"},
    )

    for section in sections:
        metadata: dict[str, Any] = {
            "kind": "section",
            "title": "57",
            "chapter": "57-38",
            "section": section.section,
            "status": section.status,
        }
        if section.references_to:
            metadata["references_to"] = list(section.references_to)
        if section.metadata:
            metadata.update(section.metadata)
        if section.section == "57-38-30.3":
            metadata["source_components"] = [
                {
                    "role": "codified_base",
                    "source_url": code_asset.source_url,
                    "source_path": code_source_path,
                    "sha256": code_sha,
                },
                {
                    "role": f"operative_{tax_year}_individual_rate_schedules",
                    "source_url": individual_asset.source_url,
                    "source_path": individual_source_path,
                    "sha256": individual_sha,
                },
                {
                    "role": f"operative_{tax_year}_fiduciary_rate_schedule",
                    "source_url": fiduciary_asset.source_url,
                    "source_path": fiduciary_source_path,
                    "sha256": fiduciary_sha,
                },
            ]
        _append_record(
            items,
            records,
            citation_path=section.citation_path,
            version=run_id,
            source_url=code_asset.source_url,
            source_path=code_source_path,
            source_id=f"section-{section.section}",
            source_format=NORTH_DAKOTA_CODE_SOURCE_FORMAT,
            sha256=code_sha,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            kind="section",
            body=section.body,
            heading=section.heading,
            legal_identifier=section.legal_identifier,
            parent_citation_path="us-nd/statute/57",
            level=1,
            ordinal=section.ordinal,
            identifiers={
                "north_dakota:title": "57",
                "north_dakota:chapter": "57-38",
                "north_dakota:section": section.section,
            },
            metadata=metadata,
        )

    inventory_path = store.inventory_path("us-nd", DocumentClass.STATUTE, run_id)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path("us-nd", DocumentClass.STATUTE, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction="us-nd",
        document_class=DocumentClass.STATUTE.value,
        version=run_id,
    )
    coverage_path = store.coverage_path("us-nd", DocumentClass.STATUTE, run_id)
    store.write_json(coverage_path, coverage.to_mapping())
    return StateStatuteExtractReport(
        jurisdiction="us-nd",
        title_count=1,
        container_count=1,
        section_count=len(sections),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        skipped_source_count=0,
        errors=(),
    )


def parse_north_dakota_chapter_pdf(pdf: bytes) -> tuple[NorthDakotaSection, ...]:
    """Split the official chapter PDF into body-bearing section provisions."""
    text = _pdf_text(pdf)
    text = re.sub(r"(?m)^Page No\.\s*\d+\s*$", "", text)
    matches = []
    seen_sections: set[str] = set()
    for match in _SECTION_HEADER_RE.finditer(text):
        section = match.group("section")
        if section in seen_sections:
            continue
        seen_sections.add(section)
        matches.append(match)
    if not matches:
        raise ValueError("no North Dakota Century Code sections parsed")
    sections: list[NorthDakotaSection] = []
    for ordinal, match in enumerate(matches, start=1):
        end = matches[ordinal].start() if ordinal < len(matches) else len(text)
        section_number = match.group("section")
        body = _clean_pdf_body(text[match.end() : end])
        if not body:
            raise ValueError(f"North Dakota section has no body: {section_number}")
        status = _section_status(body)
        sections.append(
            NorthDakotaSection(
                section=section_number,
                heading=_clean_line(match.group("heading")).rstrip("."),
                body=body,
                ordinal=ordinal,
                references_to=_references_to(body, self_section=section_number),
                status=status,
            )
        )
    return tuple(sections)


def parse_north_dakota_index_html(html: bytes | str) -> tuple[str, ...]:
    """Read the ordered section inventory from the official chapter index."""
    text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    sections = tuple(dict.fromkeys(match.group("section") for match in _INDEX_SECTION_RE.finditer(text)))
    if not sections:
        raise ValueError("North Dakota chapter index contains no sections")
    return sections


def parse_north_dakota_individual_rate_schedules(
    pdf: bytes,
) -> tuple[NorthDakotaRateSchedule, ...]:
    """Parse the four individual schedules from the official annual ND-1ES form."""
    document = fitz.open(stream=pdf, filetype="pdf")
    page = next(
        (
            page
            for page in document
            if "Tax Rate Schedules" in page.get_text("text")
            and "Married filing separately" in page.get_text("text")
        ),
        None,
    )
    if page is None:
        raise ValueError("ND-1ES source omits individual tax rate schedules")
    split = page.rect.width / 2
    left_lines = _column_lines(page, 0, split)
    right_lines = _column_lines(page, split, page.rect.width)
    return (
        NorthDakotaRateSchedule(
            "a",
            "Single, other than head of household or surviving spouse.",
            _parse_rate_brackets(_lines_between(left_lines, "Single", "Married filing separately")),
        ),
        NorthDakotaRateSchedule(
            "b",
            "Married filing jointly and surviving spouse.",
            _parse_rate_brackets(
                _lines_between(
                    right_lines,
                    "Married filing jointly and Qualifying surviving spouse",
                    "Head of household",
                )
            ),
        ),
        NorthDakotaRateSchedule(
            "c",
            "Married filing separately.",
            _parse_rate_brackets(_lines_between(left_lines, "Married filing separately", None)),
        ),
        NorthDakotaRateSchedule(
            "d",
            "Head of household.",
            _parse_rate_brackets(_lines_between(right_lines, "Head of household", None)),
        ),
    )


def parse_north_dakota_fiduciary_rate_schedule(pdf: bytes) -> NorthDakotaRateSchedule:
    """Parse the estate-and-trust schedule from the official annual Form 38-ES."""
    text = _pdf_text(pdf)
    match = re.search(
        r"Estates and Trusts(?P<table>.*?)(?:2026 Form 38-ES|SFN 28723)",
        text,
        re.S,
    )
    if match is None:
        raise ValueError("Form 38-ES source omits the fiduciary tax rate schedule")
    return NorthDakotaRateSchedule(
        "e",
        "Estates and trusts.",
        _parse_rate_brackets(match.group("table")),
    )


def apply_north_dakota_rate_schedule_overlay(
    section: NorthDakotaSection,
    *,
    schedules: tuple[NorthDakotaRateSchedule, ...],
    tax_year: int,
) -> NorthDakotaSection:
    """Replace statutory base schedules with annual schedules prescribed by the commissioner."""
    if section.section != "57-38-30.3":
        raise ValueError(f"rate schedules cannot apply to North Dakota section {section.section}")
    if [schedule.subdivision for schedule in schedules] != ["a", "b", "c", "d", "e"]:
        raise ValueError("North Dakota rate schedule overlay requires subdivisions a through e")
    replacement_text = "\n".join(_render_schedule(schedule) for schedule in schedules)
    body, count = re.subn(
        r"(?ms)^a\.\nSingle,.*?(?=^f\.\nFor an individual)",
        replacement_text + "\n",
        section.body,
        count=1,
    )
    if count != 1:
        raise ValueError("codified section 57-38-30.3 omits replaceable schedules a through e")
    metadata = dict(section.metadata or {})
    metadata["rate_schedule_overlay"] = {
        "tax_year": tax_year,
        "authority": "N.D.C.C. § 57-38-30.3(1)(g)",
        "subdivisions": ["a", "b", "c", "d", "e"],
    }
    return replace(
        section,
        body=body,
        references_to=_references_to(body, self_section=section.section),
        metadata=metadata,
    )


def _parse_rate_brackets(text: str) -> tuple[NorthDakotaRateBracket, ...]:
    tokens = _NUMBER_RE.findall(text)
    if len(tokens) < 13:
        raise ValueError(f"rate schedule has too few numeric values: {tokens}")
    tokens = tokens[:13]
    expected = ("0", "0.00", "0.00%", "0.00", "1.95%", "2.50%")
    actual = (tokens[0], tokens[2], tokens[3], tokens[6], tokens[7], tokens[11])
    if actual != expected or tokens[1] != tokens[4] or tokens[5] != tokens[9]:
        raise ValueError(f"unexpected North Dakota rate schedule layout: {tokens}")
    return (
        NorthDakotaRateBracket("0", tokens[1], tokens[2], tokens[3], "0"),
        NorthDakotaRateBracket(tokens[4], tokens[5], tokens[6], tokens[7], tokens[8]),
        NorthDakotaRateBracket(tokens[9], None, tokens[10], tokens[11], tokens[12]),
    )


def _render_schedule(schedule: NorthDakotaRateSchedule) -> str:
    lines = [
        f"{schedule.subdivision}.",
        schedule.heading,
        "If North Dakota taxable income is:",
        "Over | Not over | The tax is equal to | Of amount over",
    ]
    for bracket in schedule.brackets:
        not_over = f"${bracket.not_over}" if bracket.not_over else ""
        lines.append(
            f"${bracket.over} | {not_over} | ${bracket.base_tax} + {bracket.rate} | "
            f"${bracket.amount_over}"
        )
    return "\n".join(lines)


def _column_lines(page: fitz.Page, x_min: float, x_max: float) -> list[str]:
    rows: dict[float, list[tuple[float, str]]] = {}
    for word in page.get_text("words"):
        x0, y0, _x1, _y1, value = word[:5]
        if x_min <= x0 < x_max:
            key = round(float(y0), 1)
            rows.setdefault(key, []).append((float(x0), str(value)))
    return [
        " ".join(value for _x, value in sorted(rows[y]))
        for y in sorted(rows)
    ]


def _lines_between(lines: list[str], start: str, end: str | None) -> str:
    start_index = next(
        (index for index, line in enumerate(lines) if start.lower() in line.lower()),
        None,
    )
    if start_index is None:
        raise ValueError(f"rate schedule heading not found: {start}")
    end_index = len(lines)
    if end is not None:
        end_index = next(
            (
                index
                for index, line in enumerate(lines[start_index + 1 :], start=start_index + 1)
                if end.lower() in line.lower()
            ),
            None,
        )
        if end_index is None:
            raise ValueError(f"rate schedule heading not found: {end}")
    return "\n".join(lines[start_index:end_index])


def _pdf_text(data: bytes) -> str:
    document = fitz.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text("text") for page in document)


def _clean_pdf_body(text: str) -> str:
    lines = [_clean_line(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clean_line(value: str) -> str:
    return " ".join(value.replace("\u00ad", "").split())


def _section_status(body: str) -> str:
    lowered = body.lower()
    if lowered.startswith("repealed"):
        return "repealed"
    if lowered.startswith("expired"):
        return "expired"
    return "active"


def _references_to(body: str, *, self_section: str) -> tuple[str, ...]:
    refs = []
    for match in _REFERENCE_RE.finditer(body):
        section = match.group("section")
        if section != self_section:
            refs.append(f"us-nd/statute/57/{section}")
    return tuple(dict.fromkeys(refs))


def _scope_filter(value: str | None) -> str:
    normalized = (value or "57-38").strip().lower().removeprefix("chapter-")
    if normalized == "57":
        normalized = "57-38"
    if normalized != "57-38":
        raise ValueError(f"unsupported North Dakota Century Code scope: {value!r}")
    return normalized


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _state_source_key(jurisdiction: str, run_id: str, relative_name: str) -> str:
    return f"sources/{jurisdiction}/statute/{run_id}/{relative_name}"


def _append_record(
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    *,
    citation_path: str,
    version: str,
    source_url: str,
    source_path: str,
    source_id: str,
    source_format: str,
    sha256: str,
    source_as_of: str,
    expression_date: str,
    kind: str,
    body: str | None,
    heading: str | None,
    legal_identifier: str,
    parent_citation_path: str | None,
    level: int,
    ordinal: int,
    identifiers: dict[str, str],
    metadata: dict[str, Any],
) -> None:
    items.append(
        SourceInventoryItem(
            citation_path=citation_path,
            source_url=source_url,
            source_path=source_path,
            source_format=source_format,
            sha256=sha256,
            metadata=metadata,
        )
    )
    records.append(
        ProvisionRecord(
            id=deterministic_provision_id(citation_path),
            jurisdiction="us-nd",
            document_class=DocumentClass.STATUTE.value,
            citation_path=citation_path,
            body=body,
            heading=heading,
            citation_label=legal_identifier,
            version=version,
            source_url=source_url,
            source_path=source_path,
            source_id=source_id,
            source_format=source_format,
            source_as_of=source_as_of,
            expression_date=expression_date,
            parent_citation_path=parent_citation_path,
            parent_id=(
                deterministic_provision_id(parent_citation_path)
                if parent_citation_path
                else None
            ),
            level=level,
            ordinal=ordinal,
            kind=kind,
            legal_identifier=legal_identifier,
            identifiers=identifiers,
            metadata=metadata,
        )
    )
