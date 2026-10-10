"""Pennsylvania unconsolidated-statute source-first corpus adapter."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

PENNSYLVANIA_UNCONSOLIDATED_VIEW_URL = (
    "https://www.palegis.us/statutes/unconsolidated/law-information/view-statute"
)
PENNSYLVANIA_UNCONSOLIDATED_SOURCE_FORMAT = (
    "pennsylvania-unconsolidated-statutes-html"
)
PENNSYLVANIA_UNCONSOLIDATED_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
)
PENNSYLVANIA_UNCONSOLIDATED_TIMEOUT_SECONDS = 120.0
PENNSYLVANIA_UNCONSOLIDATED_REQUEST_ATTEMPTS = 3

_SECTION_HEADING_RE_TEMPLATE = r"^Section\s+{section}\.\s*(?P<rest>.+)$"


@dataclass(frozen=True)
class PennsylvaniaUnconsolidatedProvision:
    """One act, article, or section in an official unconsolidated act."""

    kind: str
    act_year: int
    act_number: int
    article: int
    display_number: str
    heading: str | None
    body: str | None
    parent_citation_path: str | None
    level: int
    ordinal: int | None
    source_history: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    status: str | None = None

    @property
    def citation_path(self) -> str:
        act_path = f"us-pa/statute/act-{self.act_year}-{self.act_number}"
        if self.kind == "act":
            return act_path
        article_path = f"{act_path}/article-{self.article}"
        if self.kind == "article":
            return article_path
        return f"{article_path}/section-{self.display_number}"

    @property
    def source_id(self) -> str:
        if self.kind == "act":
            return f"{self.act_year}-{self.act_number}"
        if self.kind == "article":
            return f"{self.act_year}-{self.act_number}-article-{self.article}"
        return f"{self.act_year}-{self.act_number}-{self.display_number}"

    @property
    def legal_identifier(self) -> str:
        act_name = "Tax Reform Code of 1971"
        if self.kind == "act":
            return f"{act_name} (Act {self.act_number} of {self.act_year})"
        if self.kind == "article":
            return f"{act_name}, Article {_roman(self.article)}"
        purdons = _purdons_identifier(self.article, self.display_number)
        suffix = f" ({purdons})" if purdons else ""
        return f"{act_name} \u00a7 {self.display_number}{suffix}"


def extract_pennsylvania_unconsolidated_statutes(
    store: CorpusArtifactStore,
    *,
    version: str,
    act_year: int,
    act_number: int,
    article: int,
    source_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    limit: int | None = None,
    download_dir: str | Path | None = None,
    view_url: str = PENNSYLVANIA_UNCONSOLIDATED_VIEW_URL,
    request_attempts: int = PENNSYLVANIA_UNCONSOLIDATED_REQUEST_ATTEMPTS,
    timeout_seconds: float = PENNSYLVANIA_UNCONSOLIDATED_TIMEOUT_SECONDS,
) -> StateStatuteExtractReport:
    """Snapshot and extract one complete article of an unconsolidated act."""
    jurisdiction = "us-pa"
    run_id = _run_id(
        version,
        act_year=act_year,
        act_number=act_number,
        article=article,
        limit=limit,
    )
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    source_url = _article_url(
        view_url,
        act_year=act_year,
        act_number=act_number,
        article=article,
    )
    relative_path = _article_relative_path(act_year, act_number, article)
    data = _load_article(
        source_dir=Path(source_dir) if source_dir is not None else None,
        download_dir=Path(download_dir) if download_dir is not None else None,
        relative_path=relative_path,
        source_url=source_url,
        request_attempts=request_attempts,
        timeout_seconds=timeout_seconds,
    )

    artifact_path = store.source_path(
        jurisdiction,
        DocumentClass.STATUTE,
        run_id,
        relative_path,
    )
    sha256 = store.write_bytes(artifact_path, data)
    source_key = _state_source_key(jurisdiction, run_id, relative_path)
    provisions = parse_pennsylvania_unconsolidated_article_html(
        data,
        act_year=act_year,
        act_number=act_number,
        article=article,
    )
    if limit is not None:
        provisions = provisions[:limit]
    if not provisions:
        raise ValueError("no Pennsylvania unconsolidated provisions extracted")

    items = tuple(
        _inventory_item(
            provision,
            source_url=source_url,
            source_path=source_key,
            sha256=sha256,
        )
        for provision in provisions
    )
    records = tuple(
        _provision_record(
            provision,
            version=run_id,
            source_url=source_url,
            source_path=source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
        )
        for provision in provisions
    )
    inventory_path = store.inventory_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_inventory(inventory_path, items)
    provisions_path = store.provisions_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        items,
        records,
        jurisdiction=jurisdiction,
        document_class=DocumentClass.STATUTE.value,
        version=run_id,
    )
    coverage_path = store.coverage_path(jurisdiction, DocumentClass.STATUTE, run_id)
    store.write_json(coverage_path, coverage.to_mapping())
    return StateStatuteExtractReport(
        jurisdiction=jurisdiction,
        title_count=sum(provision.kind == "act" for provision in provisions),
        container_count=sum(provision.kind == "article" for provision in provisions),
        section_count=sum(provision.kind == "section" for provision in provisions),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=(artifact_path,),
        errors=(),
    )


def parse_pennsylvania_unconsolidated_article_html(
    html: str | bytes,
    *,
    act_year: int,
    act_number: int,
    article: int,
) -> tuple[PennsylvaniaUnconsolidatedProvision, ...]:
    """Parse one official Pennsylvania unconsolidated-act article page."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.select_one(".BodyContainer") or soup.body or soup
    text = _clean_text(body.get_text(" ", strip=True))
    if "403 - Forbidden" in text or "Request blocked" in text:
        raise ValueError("source page is blocked")

    article_heading = _article_heading(body, article)
    provisions: list[PennsylvaniaUnconsolidatedProvision] = [
        PennsylvaniaUnconsolidatedProvision(
            kind="act",
            act_year=act_year,
            act_number=act_number,
            article=article,
            display_number=str(act_number),
            heading="Tax Reform Code of 1971",
            body=None,
            parent_citation_path=None,
            level=0,
            ordinal=0,
        )
    ]
    act_path = provisions[0].citation_path
    provisions.append(
        PennsylvaniaUnconsolidatedProvision(
            kind="article",
            act_year=act_year,
            act_number=act_number,
            article=article,
            display_number=str(article),
            heading=article_heading,
            body=None,
            parent_citation_path=act_path,
            level=1,
            ordinal=article,
        )
    )
    article_path = provisions[1].citation_path
    marker_re = _section_marker_re(act_year, act_number)
    markers = tuple(
        tag
        for tag in body.find_all("div", class_="Comment")
        if isinstance(tag, Tag) and marker_re.fullmatch(_clean_text(tag.get_text()))
    )
    for ordinal, marker in enumerate(markers, start=1):
        marker_match = marker_re.fullmatch(_clean_text(marker.get_text()))
        if marker_match is None:
            continue
        section = marker_match.group("section")
        heading, body_lines = _section_heading_and_body(marker, section)
        body_text = "\n".join(body_lines).strip() or None
        notes = tuple(line for line in body_lines if _is_note(line))
        history = tuple(line for line in body_lines if _is_source_history(line, section))
        provisions.append(
            PennsylvaniaUnconsolidatedProvision(
                kind="section",
                act_year=act_year,
                act_number=act_number,
                article=article,
                display_number=section,
                heading=heading,
                body=body_text,
                parent_citation_path=article_path,
                level=2,
                ordinal=ordinal,
                source_history=history,
                notes=notes,
                status=_section_status(heading, body_text),
            )
        )
    if len(provisions) == 2:
        raise ValueError(
            f"no sections parsed for Pennsylvania Act {act_number} of {act_year}, "
            f"Article {article}"
        )
    return tuple(provisions)


def _section_heading_and_body(marker: Tag, section: str) -> tuple[str | None, list[str]]:
    body_lines: list[str] = []
    heading: str | None = None
    heading_seen = False
    stop_marker_re = re.compile(r"^\d{8}u[0-9A-Z.-]+[hs]$", re.I)
    for sibling in marker.next_siblings:
        if isinstance(sibling, NavigableString):
            text = _clean_text(str(sibling))
        elif isinstance(sibling, Tag):
            marker_text = _marker_text(sibling)
            if marker_text and stop_marker_re.fullmatch(marker_text):
                break
            if sibling.name in {"script", "style"} or marker_text:
                continue
            text = _clean_text(sibling.get_text(" ", strip=True))
        else:
            continue
        if not text:
            continue
        if not heading_seen:
            heading_seen = True
            heading, trailing_body = _parse_section_heading(text, section)
            if trailing_body:
                body_lines.append(trailing_body)
            continue
        body_lines.append(text)
    return heading, body_lines


def _parse_section_heading(text: str, section: str) -> tuple[str | None, str | None]:
    pattern = re.compile(
        _SECTION_HEADING_RE_TEMPLATE.format(section=re.escape(section)),
        re.I,
    )
    match = pattern.match(text)
    if match is None:
        return text or None, None
    heading_text, separator, trailing = match.group("rest").partition("--")
    if not separator:
        return heading_text.removesuffix(".") or None, None
    heading = heading_text.removesuffix(".").strip() or None
    return heading, trailing.strip() or None


def _section_marker_re(act_year: int, act_number: int) -> re.Pattern[str]:
    prefix = f"{act_year:04d}{act_number:04d}"
    return re.compile(rf"^{prefix}u(?P<section>[0-9]+(?:\.[0-9]+)?)s$", re.I)


def _article_heading(root: Tag, article: int) -> str:
    marker = f"ARTICLE {_roman(article)}"
    for paragraph in root.find_all("p"):
        if _clean_text(paragraph.get_text(" ", strip=True)).upper() != marker:
            continue
        for sibling in paragraph.next_siblings:
            if not isinstance(sibling, Tag) or sibling.name != "p":
                continue
            text = _clean_text(sibling.get_text(" ", strip=True))
            if text and not text.startswith("("):
                return _title_case(text)
    return f"Article {_roman(article)}"


def _load_article(
    *,
    source_dir: Path | None,
    download_dir: Path | None,
    relative_path: str,
    source_url: str,
    request_attempts: int,
    timeout_seconds: float,
) -> bytes:
    if source_dir is not None:
        candidates = (
            source_dir / relative_path,
            source_dir / Path(relative_path).name,
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate.read_bytes()
        raise ValueError(f"Pennsylvania article source does not exist: {candidates[0]}")
    if download_dir is not None:
        cached_path = download_dir / relative_path
        if cached_path.is_file():
            return cached_path.read_bytes()
    data = _download_article(
        source_url,
        request_attempts=request_attempts,
        timeout_seconds=timeout_seconds,
    )
    if download_dir is not None:
        cached_path = download_dir / relative_path
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=cached_path.parent, delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        tmp_path.replace(cached_path)
    return data


def _download_article(
    source_url: str,
    *,
    request_attempts: int,
    timeout_seconds: float,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, max(request_attempts, 1) + 1):
        try:
            response = requests.get(
                source_url,
                headers={"User-Agent": PENNSYLVANIA_UNCONSOLIDATED_USER_AGENT},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            data = response.content
            if b"403 - Forbidden" in data or b"Request blocked" in data:
                raise ValueError(f"Pennsylvania article source was blocked: {source_url}")
            return data
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < request_attempts:
                time.sleep(min(2**attempt, 8))
    raise ValueError(f"failed to download Pennsylvania source {source_url}: {last_error}")


def _inventory_item(
    provision: PennsylvaniaUnconsolidatedProvision,
    *,
    source_url: str,
    source_path: str,
    sha256: str,
) -> SourceInventoryItem:
    return SourceInventoryItem(
        citation_path=provision.citation_path,
        source_url=source_url,
        source_path=source_path,
        source_format=PENNSYLVANIA_UNCONSOLIDATED_SOURCE_FORMAT,
        sha256=sha256,
        metadata=_metadata(provision),
    )


def _provision_record(
    provision: PennsylvaniaUnconsolidatedProvision,
    *,
    version: str,
    source_url: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    identifiers = {
        "pennsylvania:act_year": str(provision.act_year),
        "pennsylvania:act_number": str(provision.act_number),
        "pennsylvania:article": str(provision.article),
        f"pennsylvania:{provision.kind}": provision.display_number,
        "pennsylvania:source_id": provision.source_id,
    }
    purdons = (
        _purdons_identifier(provision.article, provision.display_number)
        if provision.kind == "section"
        else None
    )
    if purdons:
        identifiers["pennsylvania:purdons"] = purdons
    return ProvisionRecord(
        id=deterministic_provision_id(provision.citation_path),
        jurisdiction="us-pa",
        document_class=DocumentClass.STATUTE.value,
        citation_path=provision.citation_path,
        body=provision.body,
        heading=provision.heading,
        citation_label=provision.legal_identifier,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=provision.source_id,
        source_format=PENNSYLVANIA_UNCONSOLIDATED_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=provision.parent_citation_path,
        parent_id=(
            deterministic_provision_id(provision.parent_citation_path)
            if provision.parent_citation_path
            else None
        ),
        level=provision.level,
        ordinal=provision.ordinal,
        kind=provision.kind,
        legal_identifier=provision.legal_identifier,
        identifiers=identifiers,
        metadata=_metadata(provision),
    )


def _metadata(provision: PennsylvaniaUnconsolidatedProvision) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": provision.kind,
        "act_year": str(provision.act_year),
        "act_number": str(provision.act_number),
        "article": str(provision.article),
        "display_number": provision.display_number,
    }
    if provision.parent_citation_path:
        metadata["parent_citation_path"] = provision.parent_citation_path
    if provision.notes:
        metadata["notes"] = list(provision.notes)
    if provision.source_history:
        metadata["source_history"] = list(provision.source_history)
    if provision.status:
        metadata["status"] = provision.status
    return metadata


def _article_url(
    view_url: str,
    *,
    act_year: int,
    act_number: int,
    article: int,
) -> str:
    query = urlencode(
        {
            "act": act_number,
            "chpt": article,
            "iFrame": "true",
            "sessInd": 0,
            "smthLwInd": 0,
            "txtType": "HTM",
            "yr": act_year,
        }
    )
    return f"{view_url}?{query}"


def _article_relative_path(act_year: int, act_number: int, article: int) -> str:
    return (
        f"{PENNSYLVANIA_UNCONSOLIDATED_SOURCE_FORMAT}/"
        f"act-{act_year}-{act_number}/article-{article}.html"
    )


def _run_id(
    version: str,
    *,
    act_year: int,
    act_number: int,
    article: int,
    limit: int | None,
) -> str:
    parts = [
        version,
        "us-pa",
        f"act-{act_year}-{act_number}",
        f"article-{article}",
    ]
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def _purdons_identifier(article: int, section: str) -> str | None:
    if article != 3:
        return None
    base, dot, suffix = section.partition(".")
    if not base.isdigit():
        return None
    number = str(7000 + int(base))
    if dot:
        number = f"{number}.{suffix}"
    return f"72 P.S. \u00a7 {number}"


def _section_status(heading: str | None, body: str | None) -> str | None:
    joined = f"{heading or ''} {body or ''}".lower()
    if "repealed" in joined[:300]:
        return "repealed"
    if "expired" in joined[:300]:
        return "expired"
    return None


def _is_note(text: str) -> bool:
    return bool(re.match(r"^(?:Compiler's Note|Cross References|References in Text)[.:]", text, re.I))


def _is_source_history(text: str, section: str) -> bool:
    return bool(re.match(rf"^\({re.escape(section)}\s+(?:added|amended|repealed)", text, re.I))


def _marker_text(tag: Tag) -> str | None:
    if tag.name == "div" and "Comment" in set(tag.get("class") or ()):
        return _clean_text(tag.get_text(" ", strip=True))
    return None


def _state_source_key(jurisdiction: str, run_id: str, relative_name: str) -> str:
    return f"sources/{jurisdiction}/{DocumentClass.STATUTE.value}/{run_id}/{relative_name}"


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.;:])", r"\1", text)


def _title_case(value: str) -> str:
    return value.title() if value.isupper() else value


def _roman(value: int) -> str:
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    result: list[str] = []
    remaining = value
    for amount, numeral in numerals:
        while remaining >= amount:
            result.append(numeral)
            remaining -= amount
    return "".join(result)
