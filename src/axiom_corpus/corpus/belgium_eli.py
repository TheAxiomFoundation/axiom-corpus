"""Belgian ELI/Moniteur/Justel extraction into source-first corpus artifacts."""

from __future__ import annotations

import re
import time
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

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

BELGIAN_ELI_SOURCE_FORMAT = "ejustice.just.fgov.be-eli-html"
EJUSTICE_BASE_URL = "https://www.ejustice.just.fgov.be"
BELGIAN_MONITEUR_DEFAULT_LANGUAGE = "fr"
BELGIAN_MONITEUR_MAX_EDITIONS = 5
BELGIAN_MONITEUR_POLICY_SECTION_TITLES = (
    "lois, decrets, ordonnances et reglements",
    "autres arretes",
)
BELGIAN_MONITEUR_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; axiom-corpus/0.1; "
        "+https://axiom-foundation.org; max@axiom-foundation.org)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-BE,fr;q=0.9,nl-BE;q=0.8,en;q=0.7",
}

_ELI_LINK_RE = re.compile(
    r"https?://(?:www\.)?ejustice\.just\.fgov\.be/eli/"
    r"(?P<document_type>[^/\"'<>\s]+)/"
    r"(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/"
    r"(?P<numac>[A-Za-z0-9]+)/(?P<version>moniteur|staatsblad|justel)",
    re.IGNORECASE,
)
_ELI_PATH_RE = re.compile(
    r"(?:^|/)eli/"
    r"(?P<document_type>[^/\"'<>\s]+)/"
    r"(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})"
    r"(?:/(?P<numac>[A-Za-z0-9]+)(?:/(?P<version>moniteur|staatsblad|justel))?)?",
    re.IGNORECASE,
)
_ARTICLE_ANCHOR_RE = re.compile(
    r"<a\b(?=[^>]*\bname=['\"]Art\.(?P<label>[^'\"]+)['\"])[^>]*>",
    re.IGNORECASE,
)
_MONITEUR_ARTICLE_HEADING_RE = re.compile(
    r"(?im)(?:^|\n)(?P<heading>(?:Article|Art\.)\s+"
    r"(?P<label>\d+(?:/\d+)?(?:er|bis|ter|quater|quinquies)?))\.",
)
_DATE_TITLE_RE = re.compile(r"^\d{1,2}\s+[A-ZÉÈA-Z]+(?:\s+\d{4})?\.?\s*[-.]?\s+.+")
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
_NUMAC_QUERY_RE = re.compile(r"\bnumac_search=(?P<numac>[A-Za-z0-9]+)")

_STATUTE_DOCUMENT_TYPES = {
    "constitution",
    "grondwet",
    "loi",
    "wet",
    "ordonnance",
    "ordonnantie",
    "decret",
    "decreet",
}
_REGULATION_DOCUMENT_TYPES = {"arrete", "arrêté", "besluit", "reglement", "règlement"}
_BRUSSELS_DOCUMENT_TYPES = {"ordonnance", "ordonnantie"}
_OFFICIAL_VERSIONS = {"moniteur", "staatsblad"}
_FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}
_FRENCH_TITLE_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})(?:er)?\s+"
    r"(?P<month>janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)\s+"
    r"(?P<year>\d{4})",
    re.IGNORECASE,
)
_DOCUMENT_TYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bloi\b|\bloi-", re.IGNORECASE), "loi"),
    (re.compile(r"\bd[eé]cret\b", re.IGNORECASE), "decret"),
    (re.compile(r"\bordonnance\b", re.IGNORECASE), "ordonnance"),
    (re.compile(r"\barr[êe]t[ée]\b", re.IGNORECASE), "arrete"),
    (re.compile(r"\br[èe]glement\b", re.IGNORECASE), "reglement"),
    (re.compile(r"\bwet\b", re.IGNORECASE), "wet"),
    (re.compile(r"\bdecreet\b", re.IGNORECASE), "decreet"),
    (re.compile(r"\bordonnantie\b", re.IGNORECASE), "ordonnantie"),
    (re.compile(r"\bbesluit\b", re.IGNORECASE), "besluit"),
)


@dataclass(frozen=True)
class BelgianELIDocument:
    """One Belgian ELI document locator."""

    document_type: str
    year: str
    month: str
    day: str
    numac: str
    title: str
    moniteur_url: str | None = None
    justel_url: str | None = None
    source_name: str | None = None
    jurisdiction_code: str | None = None

    @property
    def jurisdiction(self) -> str:
        if self.jurisdiction_code is not None:
            return self.jurisdiction_code
        if self.document_type in _BRUSSELS_DOCUMENT_TYPES:
            return "be-bru"
        return "be"

    @property
    def document_class(self) -> str:
        if self.document_type in _REGULATION_DOCUMENT_TYPES:
            return DocumentClass.REGULATION.value
        if self.document_type in _STATUTE_DOCUMENT_TYPES:
            return DocumentClass.STATUTE.value
        return DocumentClass.OTHER.value

    @property
    def document_id(self) -> str:
        return f"eli/{self.document_type}/{self.year}/{self.month}/{self.day}/{self.numac}"

    @property
    def preferred_source_url(self) -> str:
        return self.moniteur_url or self.justel_url or _eli_document_url(self)


@dataclass(frozen=True)
class BelgianELIProvision:
    """A normalized document- or article-level Belgian ELI provision."""

    document: BelgianELIDocument
    kind: str
    label: str
    body: str
    heading: str | None
    source_url: str
    source_authority: str


@dataclass(frozen=True)
class BelgianMoniteurSource:
    """One source discovered from a Belgian Official Gazette summary page."""

    source_id: str
    source_url: str
    jurisdiction: str
    document_class: str
    document_type: str
    numac: str
    title: str
    publication_date: str
    edition: int
    section_title: str
    moniteur_url: str | None = None
    justel_url: str | None = None
    authority: str | None = None


@dataclass(frozen=True)
class BelgianMoniteurDiscoveryReport:
    """Result of discovering Belgian Official Gazette article sources."""

    start_date: str
    end_date: str
    language: str
    summary_pages_fetched: int
    sources: tuple[BelgianMoniteurSource, ...]


@dataclass(frozen=True)
class _PreparedBelgianELISource:
    """Prepared source snapshot and extracted provisions."""

    raw_bytes: bytes
    relative_name: str
    source_name: str
    provisions: tuple[BelgianELIProvision, ...]


@dataclass(frozen=True)
class BelgianELIClassExtractReport:
    """Artifact report for one Belgium/Brussels document class."""

    jurisdiction: str
    document_class: str
    source_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class BelgianELIExtractReport:
    """Combined Belgian ELI extraction report."""

    version: str
    source_count: int
    provisions_written: int
    class_reports: tuple[BelgianELIClassExtractReport, ...]


def discover_belgian_moniteur_sources(
    *,
    start_date: date | str,
    end_date: date | str,
    language: str = BELGIAN_MONITEUR_DEFAULT_LANGUAGE,
    included_section_titles: Sequence[str] = BELGIAN_MONITEUR_POLICY_SECTION_TITLES,
    request_timeout: float = 30.0,
    limit: int | None = None,
    max_editions: int = BELGIAN_MONITEUR_MAX_EDITIONS,
) -> BelgianMoniteurDiscoveryReport:
    """Discover official Moniteur belge statute/regulation article sources.

    The official data.gov.be entry for the Moniteur points to eJustice HTML
    rather than a bulk package. This crawler uses the daily summary endpoint,
    follows only the policy-law sections, and returns article.pl source URLs
    that the ELI extractor can snapshot and normalize.
    """
    start = _coerce_date(start_date)
    end = _coerce_date(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")

    included_sections = {_normalize_heading(title) for title in included_section_titles}
    session = requests.Session()
    session.headers.update(BELGIAN_MONITEUR_REQUEST_HEADERS)
    current = start
    summary_pages_fetched = 0
    sources_by_id: dict[str, BelgianMoniteurSource] = {}

    while current <= end:
        first_url = _moniteur_summary_url(
            summary_date=current,
            edition=1,
            language=language,
        )
        first_response = _get_ejustice(session, first_url, timeout=request_timeout)
        summary_pages_fetched += 1
        first_html = first_response.text
        for source in _parse_moniteur_summary_sources(
            first_html,
            summary_url=first_response.url,
            publication_date=current.isoformat(),
            edition=1,
            included_section_titles=included_sections,
        ):
            sources_by_id.setdefault(source.source_id, source)
            if limit is not None and len(sources_by_id) >= limit:
                return BelgianMoniteurDiscoveryReport(
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    language=language,
                    summary_pages_fetched=summary_pages_fetched,
                    sources=tuple(sources_by_id.values()),
                )

        editions = _discover_summary_editions(first_html, max_editions=max_editions)
        for edition in editions:
            if edition == 1:
                continue
            summary_url = _moniteur_summary_url(
                summary_date=current,
                edition=edition,
                language=language,
            )
            response = _get_ejustice(session, summary_url, timeout=request_timeout)
            summary_pages_fetched += 1
            for source in _parse_moniteur_summary_sources(
                response.text,
                summary_url=response.url,
                publication_date=current.isoformat(),
                edition=edition,
                included_section_titles=included_sections,
            ):
                sources_by_id.setdefault(source.source_id, source)
                if limit is not None and len(sources_by_id) >= limit:
                    return BelgianMoniteurDiscoveryReport(
                        start_date=start.isoformat(),
                        end_date=end.isoformat(),
                        language=language,
                        summary_pages_fetched=summary_pages_fetched,
                        sources=tuple(sources_by_id.values()),
                    )
        current += timedelta(days=1)

    return BelgianMoniteurDiscoveryReport(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        language=language,
        summary_pages_fetched=summary_pages_fetched,
        sources=tuple(sources_by_id.values()),
    )


def extract_belgian_eli(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_htmls: Sequence[str | Path] = (),
    source_dir: str | Path | None = None,
    source_pattern: str = "*.html",
    source_urls: Sequence[str] = (),
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    request_timeout: float = 30.0,
    limit: int | None = None,
    source_jurisdiction_overrides: Mapping[str, str] | None = None,
) -> BelgianELIExtractReport:
    """Extract Belgian ELI HTML into normalized corpus artifacts.

    This adapter is intentionally source-first. It snapshots ELI/Moniteur/Justel
    HTML and emits durable corpus records before RuleSpec encodes anything from
    the source. Justel article records are marked as non-authentic consolidated
    locators; Moniteur/Belgisch Staatsblad remains the preferred legal source.
    """
    if not source_htmls and source_dir is None and not source_urls:
        raise ValueError("at least one source HTML path, source directory, or URL is required")

    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    prepared = _prepare_sources(
        source_htmls=source_htmls,
        source_dir=source_dir,
        source_pattern=source_pattern,
        source_urls=source_urls,
        request_timeout=request_timeout,
        limit=limit,
        source_jurisdiction_overrides=source_jurisdiction_overrides or {},
    )

    grouped_records: dict[tuple[str, str], list[ProvisionRecord]] = defaultdict(list)
    grouped_inventory: dict[tuple[str, str], list[SourceInventoryItem]] = defaultdict(list)
    grouped_sources: dict[tuple[str, str], dict[str, Path]] = defaultdict(dict)

    for item in prepared:
        source_sha_by_scope: dict[tuple[str, str], str] = {}
        for provision in item.provisions:
            document = provision.document
            scope = (document.jurisdiction, document.document_class)
            if scope not in source_sha_by_scope:
                source_artifact_path = store.source_path(
                    document.jurisdiction,
                    document.document_class,
                    version,
                    item.relative_name,
                )
                source_sha_by_scope[scope] = store.write_bytes(
                    source_artifact_path,
                    item.raw_bytes,
                )
                grouped_sources[scope][item.relative_name] = source_artifact_path

            citation_path = belgian_eli_citation_path(provision)
            record = _provision_record(
                provision,
                citation_path=citation_path,
                version=version,
                source_path=_source_key(
                    document.jurisdiction,
                    document.document_class,
                    version,
                    item.relative_name,
                ),
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
            )
            grouped_records[scope].append(record)
            grouped_inventory[scope].append(
                SourceInventoryItem(
                    citation_path=citation_path,
                    source_url=record.source_url,
                    source_path=record.source_path,
                    source_format=BELGIAN_ELI_SOURCE_FORMAT,
                    sha256=source_sha_by_scope[scope],
                    metadata={
                        "source_name": item.source_name,
                        "source_authority": provision.source_authority,
                        "title": document.title,
                        "document_type": document.document_type,
                        "numac": document.numac,
                        "kind": provision.kind,
                        "label": provision.label,
                        "moniteur_url": document.moniteur_url,
                        "justel_url": document.justel_url,
                        "legal_authority_url": document.moniteur_url,
                    },
                )
            )

    class_reports: list[BelgianELIClassExtractReport] = []
    for jurisdiction, document_class in sorted(grouped_records):
        records = _dedupe_records(grouped_records[(jurisdiction, document_class)])
        inventory = _dedupe_inventory(grouped_inventory[(jurisdiction, document_class)])
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
            grouped_sources[(jurisdiction, document_class)][name]
            for name in sorted(grouped_sources[(jurisdiction, document_class)])
        )
        class_reports.append(
            BelgianELIClassExtractReport(
                jurisdiction=jurisdiction,
                document_class=document_class,
                source_count=len(inventory),
                provisions_written=len(records),
                inventory_path=inventory_path,
                provisions_path=provisions_path,
                coverage_path=coverage_path,
                coverage=coverage,
                source_paths=source_paths,
            )
        )

    return BelgianELIExtractReport(
        version=version,
        source_count=sum(report.source_count for report in class_reports),
        provisions_written=sum(report.provisions_written for report in class_reports),
        class_reports=tuple(class_reports),
    )


def belgian_eli_citation_path(provision: BelgianELIProvision) -> str:
    """Return the canonical corpus citation path for a Belgian ELI provision."""
    document = provision.document
    parts = [
        document.jurisdiction,
        document.document_class,
        document.document_type,
        document.year,
        document.month,
        document.day,
        document.numac,
    ]
    if provision.kind == "document":
        parts.append("document")
    else:
        parts.extend([provision.kind, _label_token(provision.label)])
    return "/".join(parts)


def parse_belgian_eli_source(
    html_text: str,
    *,
    source_name: str,
) -> tuple[BelgianELIProvision, ...]:
    """Parse one ELI HTML source into document- or article-level provisions."""
    source_document = _document_from_source_name(source_name, html_text)
    if source_document is None:
        source_document = _document_from_moniteur_article_page(source_name, html_text)
    if source_document is not None:
        article_provisions = _parse_article_provisions(
            source_document,
            html_text,
        ) or _parse_moniteur_article_provisions(source_document, html_text)
        if article_provisions:
            return article_provisions
        return (_document_provision(source_document),)

    listing_documents = _parse_listing_documents(html_text, source_name=source_name)
    return tuple(_document_provision(document) for document in listing_documents)


def _prepare_sources(
    *,
    source_htmls: Sequence[str | Path],
    source_dir: str | Path | None,
    source_pattern: str,
    source_urls: Sequence[str],
    request_timeout: float,
    limit: int | None,
    source_jurisdiction_overrides: Mapping[str, str],
) -> list[_PreparedBelgianELISource]:
    prepared: list[_PreparedBelgianELISource] = []
    for source_name, source_bytes in _iter_sources(
        source_htmls=source_htmls,
        source_dir=source_dir,
        source_pattern=source_pattern,
        source_urls=source_urls,
        request_timeout=request_timeout,
        limit=limit,
    ):
        normalized = _normalize_source_bytes(source_bytes)
        html_text = normalized.decode("utf-8")
        provisions = parse_belgian_eli_source(html_text, source_name=source_name)
        jurisdiction_override = source_jurisdiction_overrides.get(
            source_name,
        ) or source_jurisdiction_overrides.get(_normalize_ejustice_url(source_name))
        if jurisdiction_override is not None:
            provisions = tuple(
                replace(
                    provision,
                    document=replace(
                        provision.document,
                        jurisdiction_code=jurisdiction_override,
                    ),
                )
                for provision in provisions
            )
        if not provisions:
            raise ValueError(f"no Belgian ELI documents found in {source_name}")
        prepared.append(
            _PreparedBelgianELISource(
                raw_bytes=normalized,
                relative_name=_source_relative_name(source_name),
                source_name=source_name,
                provisions=provisions,
            )
        )
    return prepared


def _iter_sources(
    *,
    source_htmls: Sequence[str | Path],
    source_dir: str | Path | None,
    source_pattern: str,
    source_urls: Sequence[str],
    request_timeout: float,
    limit: int | None,
) -> Iterable[tuple[str, bytes]]:
    named_sources: list[tuple[str, Path | str]] = [
        (Path(path).name, Path(path)) for path in source_htmls
    ]
    if source_dir is not None:
        source_root = Path(source_dir)
        named_sources.extend(
            (path.relative_to(source_root).as_posix(), path)
            for path in sorted(source_root.rglob(source_pattern))
        )
    named_sources.extend((url, url) for url in source_urls)
    if limit is not None:
        named_sources = named_sources[:limit]

    for source_name, source in named_sources:
        if isinstance(source, Path):
            yield source_name, source.read_bytes()
        else:
            response = _get_ejustice(
                requests.Session(),
                source,
                timeout=request_timeout,
            )
            yield source_name, response.content


def _get_ejustice(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
) -> requests.Response:
    session.headers.update(BELGIAN_MONITEUR_REQUEST_HEADERS)
    last_error: requests.RequestException | None = None
    for attempt in range(1, 5):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 4:
                break
            time.sleep(min(2**attempt, 10))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"failed to fetch {url}")


def _moniteur_summary_url(
    *,
    summary_date: date,
    edition: int,
    language: str,
) -> str:
    return f"{EJUSTICE_BASE_URL}/cgi/summary.pl?" + urlencode(
        {
            "language": language,
            "sum_date": summary_date.isoformat(),
            "s_editie": str(edition),
            "view_numac": "",
        }
    )


def _parse_moniteur_summary_sources(
    html_text: str,
    *,
    summary_url: str,
    publication_date: str,
    edition: int,
    included_section_titles: set[str],
) -> tuple[BelgianMoniteurSource, ...]:
    soup = BeautifulSoup(html_text, "html.parser")
    sources: list[BelgianMoniteurSource] = []
    for section in soup.find_all(id=lambda value: value and value.startswith("list-title-")):
        heading = section.find("h2")
        section_title = _clean_text(heading.get_text(" ", strip=True)) if heading else ""
        if _normalize_heading(section_title) not in included_section_titles:
            continue
        for link in section.find_all("a", class_="list-item--title", href=True):
            title = _clean_text(link.get_text(" ", strip=True))
            document_type = _infer_document_type(title)
            if document_type is None:
                continue
            href = str(link.get("href") or "")
            numac = _numac_from_href(href)
            if not numac:
                continue
            source_url = _normalize_ejustice_url(urljoin(summary_url, href))
            document_date = _extract_french_title_date(title)
            if document_date is None:
                document_date = _coerce_date(publication_date)
            document_url = _eli_document_url_from_parts(
                document_type=document_type,
                year=f"{document_date.year:04d}",
                month=f"{document_date.month:02d}",
                day=f"{document_date.day:02d}",
                numac=numac,
            )
            authority = _summary_item_authority(link)
            jurisdiction = _infer_jurisdiction(document_type, title, authority)
            document_class = (
                DocumentClass.REGULATION.value
                if document_type in _REGULATION_DOCUMENT_TYPES
                else DocumentClass.STATUTE.value
            )
            source_id = _slug_source_id(
                f"{jurisdiction}-{document_class}-{document_type}-{document_date:%Y%m%d}-{numac}"
            )
            sources.append(
                BelgianMoniteurSource(
                    source_id=source_id,
                    source_url=source_url,
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    document_type=document_type,
                    numac=numac,
                    title=title,
                    publication_date=publication_date,
                    edition=edition,
                    section_title=section_title,
                    moniteur_url=f"{document_url}/moniteur",
                    justel_url=f"{document_url}/justel",
                    authority=authority,
                )
            )
    return tuple(sources)


def _discover_summary_editions(html_text: str, *, max_editions: int) -> tuple[int, ...]:
    soup = BeautifulSoup(html_text, "html.parser")
    editions: set[int] = {1}
    edition_container = soup.find(class_=lambda value: _has_class(value, "editions"))
    if edition_container is not None:
        for text in edition_container.stripped_strings:
            if text.isdigit():
                editions.add(int(text))
        for link in edition_container.find_all("a", href=True):
            query = parse_qs(urlparse(str(link.get("href") or "")).query)
            value = _first_query_value(query, "s_editie")
            if value and value.isdigit():
                editions.add(int(value))
    return tuple(sorted(edition for edition in editions if 1 <= edition <= max_editions))


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _normalize_heading(value: str) -> str:
    return _strip_accents(_clean_text(value)).lower()


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _infer_document_type(title: str) -> str | None:
    normalized = _strip_accents(title).lower()
    for pattern, document_type in _DOCUMENT_TYPE_PATTERNS:
        if pattern.search(normalized):
            return document_type
    return None


def _infer_jurisdiction(
    document_type: str,
    title: str | None,
    authority: str | None = None,
) -> str:
    haystack = _strip_accents(" ".join(value or "" for value in (title, authority))).lower()
    if document_type in _BRUSSELS_DOCUMENT_TYPES or any(
        marker in haystack
        for marker in (
            "bruxelles-capitale",
            "brussels hoofdstedelijk",
            "commission communautaire commune",
            "commission communautaire francaise",
            "cocom",
            "cocof",
        )
    ):
        return "be-bru"
    if any(marker in haystack for marker in ("wallonie", "wallonne", "service public de wallonie")):
        return "be-wal"
    if any(marker in haystack for marker in ("flamande", "vlaamse", "vlaanderen")):
        return "be-vlg"
    if any(
        marker in haystack for marker in ("communaute francaise", "federation wallonie-bruxelles")
    ):
        return "be-fwb"
    if any(marker in haystack for marker in ("germanophone", "deutschsprachigen")):
        return "be-deu"
    return "be"


def _extract_french_title_date(title: str) -> date | None:
    match = _FRENCH_TITLE_DATE_RE.search(title)
    if match is None:
        return None
    month = _FRENCH_MONTHS[_strip_accents(match.group("month")).lower()]
    return date(int(match.group("year")), month, int(match.group("day")))


def _numac_from_href(href: str) -> str | None:
    query_numac = _first_query_value(parse_qs(urlparse(href).query), "numac_search")
    if query_numac:
        return query_numac
    match = _NUMAC_QUERY_RE.search(href)
    return match.group("numac") if match else None


def _summary_item_authority(link: object) -> str | None:
    find_parent = getattr(link, "find_parent", None)
    if not callable(find_parent):
        return None
    item = find_parent(class_=lambda value: _has_class(value, "list-item"))
    if item is None:
        return None
    subtitle = item.find(class_=lambda value: _has_class(value, "list-item--subtitle"))
    if subtitle is None:
        return None
    authority = _clean_text(subtitle.get_text(" ", strip=True))
    return authority or None


def _first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0] or None


def _summary_publication_date(source_name: str) -> str:
    value = _first_query_value(parse_qs(urlparse(source_name).query), "sum_date")
    return value or date.today().isoformat()


def _summary_edition(source_name: str) -> int:
    value = _first_query_value(parse_qs(urlparse(source_name).query), "s_editie")
    if value and value.isdigit():
        return int(value)
    return 1


def _moniteur_intro_title(soup: BeautifulSoup) -> str | None:
    intro = soup.find("p", class_=lambda value: _has_class(value, "intro-text"))
    if intro is None:
        return None
    title = _clean_text(intro.get_text(" ", strip=True))
    return title or None


def _moniteur_authority(soup: BeautifulSoup) -> str | None:
    title = soup.find("h1", class_=lambda value: _has_class(value, "page__title"))
    if title is None:
        return None
    authority = _clean_text(title.get_text(" ", strip=True))
    return authority or None


def _moniteur_eli_document_from_links(
    html_text: str,
    *,
    preferred_numac: str | None,
) -> BelgianELIDocument | None:
    fallback: BelgianELIDocument | None = None
    for match in _ELI_LINK_RE.finditer(html_text):
        version = match.group("version").lower()
        if version not in _OFFICIAL_VERSIONS:
            continue
        document = BelgianELIDocument(
            document_type=match.group("document_type").lower(),
            year=match.group("year"),
            month=match.group("month"),
            day=match.group("day"),
            numac=match.group("numac"),
            title=_fallback_title(match),
            moniteur_url=_normalize_ejustice_url(match.group(0)),
            justel_url=(
                _eli_document_url_from_parts(
                    document_type=match.group("document_type").lower(),
                    year=match.group("year"),
                    month=match.group("month"),
                    day=match.group("day"),
                    numac=match.group("numac"),
                )
                + "/justel"
            ),
        )
        if preferred_numac is not None and document.numac == preferred_numac:
            return document
        if fallback is None:
            fallback = document
    return fallback


def _numac_from_article_page(html_text: str) -> str | None:
    soup = BeautifulSoup(html_text, "html.parser")
    tag = soup.find(class_=lambda value: _has_class(value, "tag"))
    if tag is None:
        return None
    numac = _clean_text(tag.get_text(" ", strip=True))
    return numac or None


def _document_date_parts_from_url(url: str | None) -> tuple[str, str, str] | None:
    if url is None:
        return None
    match = _ELI_PATH_RE.search(url)
    if match is None:
        return None
    return match.group("year"), match.group("month"), match.group("day")


def _has_class(value: object, class_name: str) -> bool:
    if isinstance(value, str):
        return class_name in value.split()
    if isinstance(value, Sequence):
        return class_name in value
    return False


def _slug_source_id(value: str) -> str:
    slug = _strip_accents(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "belgian-moniteur-source"


def _normalize_source_bytes(source_bytes: bytes) -> bytes:
    text = _decode_html(source_bytes)
    normalized_text = "\n".join(line.rstrip() for line in text.splitlines())
    if text.endswith(("\n", "\r")):
        normalized_text += "\n"
    return normalized_text.encode("utf-8")


def _decode_html(source_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "iso-8859-1", "cp1252"):
        try:
            return source_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return source_bytes.decode("utf-8", errors="replace")


def _document_from_source_name(
    source_name: str,
    html_text: str,
) -> BelgianELIDocument | None:
    match = _ELI_PATH_RE.search(source_name)
    if match is None:
        return None
    numac = match.group("numac")
    if numac is None:
        return None

    document_type = match.group("document_type").lower()
    version = (match.group("version") or "").lower()
    title = _page_title(html_text) or _fallback_title(match)
    source_url = (
        _normalize_ejustice_url(source_name)
        if source_name.startswith("http")
        else _versioned_eli_document_url(
            document_type=document_type,
            year=match.group("year"),
            month=match.group("month"),
            day=match.group("day"),
            numac=numac,
            version=version,
        )
    )
    document_url = _eli_document_url_from_parts(
        document_type=document_type,
        year=match.group("year"),
        month=match.group("month"),
        day=match.group("day"),
        numac=numac,
    )
    moniteur_url = source_url if version in _OFFICIAL_VERSIONS else f"{document_url}/moniteur"
    justel_url = source_url if version == "justel" else f"{document_url}/justel"
    return BelgianELIDocument(
        document_type=document_type,
        year=match.group("year"),
        month=match.group("month"),
        day=match.group("day"),
        numac=numac,
        title=title,
        moniteur_url=moniteur_url,
        justel_url=justel_url,
        source_name=source_name,
        jurisdiction_code=_infer_jurisdiction(document_type, title),
    )


def _document_from_moniteur_article_page(
    source_name: str,
    html_text: str,
) -> BelgianELIDocument | None:
    parsed = urlparse(source_name)
    if (
        parsed.scheme
        and parsed.netloc
        and not parsed.path.endswith(("/article.pl", "/article_body.pl"))
    ):
        return None

    query = parse_qs(parsed.query)
    query_numac = _first_query_value(query, "numac_search")
    soup = BeautifulSoup(html_text, "html.parser")
    title = _moniteur_intro_title(soup) or _page_title(html_text)
    if not title:
        return None

    authority = _moniteur_authority(soup)
    moniteur_eli_document = _moniteur_eli_document_from_links(
        html_text,
        preferred_numac=query_numac,
    )
    if moniteur_eli_document is not None:
        source_url = (
            _normalize_ejustice_url(source_name)
            if parsed.scheme and parsed.netloc
            else moniteur_eli_document.moniteur_url
        )
        return replace(
            moniteur_eli_document,
            title=title,
            moniteur_url=source_url,
            source_name=source_name,
            jurisdiction_code=_infer_jurisdiction(
                moniteur_eli_document.document_type,
                title,
                authority,
            ),
        )

    numac = query_numac or _numac_from_article_page(html_text)
    document_type = _infer_document_type(title)
    document_date = _extract_french_title_date(title)
    if not numac or document_type is None or document_date is None:
        return None

    document_url = _eli_document_url_from_parts(
        document_type=document_type,
        year=f"{document_date.year:04d}",
        month=f"{document_date.month:02d}",
        day=f"{document_date.day:02d}",
        numac=numac,
    )
    return BelgianELIDocument(
        document_type=document_type,
        year=f"{document_date.year:04d}",
        month=f"{document_date.month:02d}",
        day=f"{document_date.day:02d}",
        numac=numac,
        title=title,
        moniteur_url=(
            _normalize_ejustice_url(source_name)
            if parsed.scheme and parsed.netloc
            else f"{document_url}/moniteur"
        ),
        justel_url=f"{document_url}/justel",
        source_name=source_name,
        jurisdiction_code=_infer_jurisdiction(document_type, title, authority),
    )


def _parse_listing_documents(
    html_text: str,
    *,
    source_name: str,
) -> tuple[BelgianELIDocument, ...]:
    documents: dict[tuple[str, str, str, str, str], BelgianELIDocument] = {}
    for match in _ELI_LINK_RE.finditer(html_text):
        key = (
            match.group("document_type").lower(),
            match.group("year"),
            match.group("month"),
            match.group("day"),
            match.group("numac"),
        )
        title = _title_before_link(html_text, match.start()) or _fallback_title(match)
        url = _normalize_ejustice_url(match.group(0))
        version = match.group("version").lower()
        existing = documents.get(key)
        document = existing or BelgianELIDocument(
            document_type=key[0],
            year=key[1],
            month=key[2],
            day=key[3],
            numac=key[4],
            title=title,
            source_name=source_name,
        )
        if version in _OFFICIAL_VERSIONS:
            document = replace(document, moniteur_url=url)
        elif version == "justel":
            document = replace(document, justel_url=url)
        if not document.title and title:
            document = replace(document, title=title)
        documents[key] = document
    for source in _parse_moniteur_summary_sources(
        html_text,
        summary_url=source_name,
        publication_date=_summary_publication_date(source_name),
        edition=_summary_edition(source_name),
        included_section_titles={
            _normalize_heading(title) for title in BELGIAN_MONITEUR_POLICY_SECTION_TITLES
        },
    ):
        key = (
            source.document_type,
            *(_document_date_parts_from_url(source.moniteur_url) or ("", "", "")),
            source.numac,
        )
        if key in documents:
            continue
        document_date = _extract_french_title_date(source.title)
        if document_date is None:
            document_date = _coerce_date(source.publication_date)
        document_url = _eli_document_url_from_parts(
            document_type=source.document_type,
            year=f"{document_date.year:04d}",
            month=f"{document_date.month:02d}",
            day=f"{document_date.day:02d}",
            numac=source.numac,
        )
        documents[key] = BelgianELIDocument(
            document_type=source.document_type,
            year=f"{document_date.year:04d}",
            month=f"{document_date.month:02d}",
            day=f"{document_date.day:02d}",
            numac=source.numac,
            title=source.title,
            moniteur_url=source.moniteur_url or f"{document_url}/moniteur",
            justel_url=source.justel_url or f"{document_url}/justel",
            source_name=source_name,
            jurisdiction_code=source.jurisdiction,
        )
    return tuple(documents[key] for key in sorted(documents))


def _parse_article_provisions(
    document: BelgianELIDocument,
    html_text: str,
) -> tuple[BelgianELIProvision, ...]:
    text_html = _text_section_html(html_text)
    if text_html is None:
        return ()

    matches = list(_ARTICLE_ANCHOR_RE.finditer(text_html))
    provisions: list[BelgianELIProvision] = []
    for index, match in enumerate(matches):
        label = _clean_label(match.group("label"))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text_html)
        article_html = text_html[start:end]
        body = _html_text(article_html)
        if not body:
            continue
        source_url = _article_source_url(document, label)
        provisions.append(
            BelgianELIProvision(
                document=document,
                kind="article",
                label=label,
                body=body,
                heading=f"Article {label}",
                source_url=source_url,
                source_authority=_source_authority(source_url),
            )
        )
    return tuple(provisions)


def _parse_moniteur_article_provisions(
    document: BelgianELIDocument,
    html_text: str,
) -> tuple[BelgianELIProvision, ...]:
    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.find("main", class_=lambda value: _has_class(value, "article-text"))
    if main is None:
        return ()

    text = _normalize_moniteur_article_text(_html_text(str(main)))
    matches = list(_MONITEUR_ARTICLE_HEADING_RE.finditer(text))
    provisions: list[BelgianELIProvision] = []
    for index, match in enumerate(matches):
        label = _clean_label(match.group("label"))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        provisions.append(
            BelgianELIProvision(
                document=document,
                kind="article",
                label=label,
                body=body,
                heading=match.group("heading"),
                source_url=document.moniteur_url or f"{_eli_document_url(document)}/moniteur",
                source_authority="official_original_publication",
            )
        )
    return tuple(provisions)


def _normalize_moniteur_article_text(text: str) -> str:
    text = re.sub(
        r"\b(\d+)\s*\n\s*(er|bis|ter|quater|quinquies)\s*\n",
        r"\1\2",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(Article|Art\.)\s+(\d+)\s*\n\s*"
        r"(er|bis|ter|quater|quinquies)\s*\n\s*\.",
        r"\1 \2\3.",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"\b(Article|Art\.)\s+(\d+)\s*\n\s*\.",
        r"\1 \2.",
        text,
        flags=re.IGNORECASE,
    )


def _document_provision(document: BelgianELIDocument) -> BelgianELIProvision:
    source_url = document.preferred_source_url
    body_lines = [document.title]
    if document.moniteur_url:
        body_lines.append(f"Moniteur: {document.moniteur_url}")
    if document.justel_url:
        body_lines.append(f"Justel: {document.justel_url}")
    return BelgianELIProvision(
        document=document,
        kind="document",
        label="document",
        body="\n".join(body_lines),
        heading=document.title,
        source_url=source_url,
        source_authority=_source_authority(source_url),
    )


def _text_section_html(html_text: str) -> str | None:
    soup = BeautifulSoup(html_text, "html.parser")
    text_header = soup.find(id="text")
    if text_header is not None:
        container = text_header.find_parent("div")
        if container is not None:
            return str(container)
    container = soup.find(id="list-title-3")
    if container is not None:
        return str(container)
    return None


def _page_title(html_text: str) -> str | None:
    soup = BeautifulSoup(html_text, "html.parser")
    title_tag = soup.find(class_="list-item--title")
    if title_tag is not None:
        title = _clean_text(title_tag.get_text(" ", strip=True))
        if title:
            return title
    title_tag = soup.find("title")
    if title_tag is not None:
        title = _clean_text(title_tag.get_text(" ", strip=True))
        if title and not title.lower().startswith("justel"):
            return title
    return None


def _title_before_link(html_text: str, link_start: int) -> str | None:
    window = html_text[max(0, link_start - 2500) : link_start]
    parts = re.split(r"<tr><td\s+colspan=3><hr|<tr><A\s+name=", window, flags=re.I)
    fragment = parts[-1] if parts else window
    lines = [line for line in _html_text(fragment).splitlines() if line]
    for line in lines:
        if _DATE_TITLE_RE.match(line):
            return line
    return None


def _html_text(html_fragment: str) -> str:
    soup = BeautifulSoup(re.sub(r"<br\s*/?>", "\n", html_fragment, flags=re.I), "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [_clean_text(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _clean_text(value: str) -> str:
    text = value.replace("\xa0", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _clean_label(label: str) -> str:
    return _clean_text(label).strip(".")


def _label_token(label: str) -> str:
    token = label.strip().strip(".")
    token = re.sub(r"[^0-9A-Za-z]+", "-", token).strip("-")
    return token or "unnumbered"


def _provision_record(
    provision: BelgianELIProvision,
    *,
    citation_path: str,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
) -> ProvisionRecord:
    document = provision.document
    parent_path = _document_parent_citation_path(document)
    identifiers = {
        "ejustice.just.fgov.be:document_type": document.document_type,
        "ejustice.just.fgov.be:year": document.year,
        "ejustice.just.fgov.be:month": document.month,
        "ejustice.just.fgov.be:day": document.day,
        "ejustice.just.fgov.be:numac": document.numac,
        "ejustice.just.fgov.be:source_authority": provision.source_authority,
    }
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction=document.jurisdiction,
        document_class=document.document_class,
        citation_path=citation_path,
        citation_label=_citation_label(provision),
        heading=provision.heading,
        body=provision.body,
        version=version,
        source_url=provision.source_url,
        source_path=source_path,
        source_id=provision.source_url,
        source_format=BELGIAN_ELI_SOURCE_FORMAT,
        source_document_id=document.document_id,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_path,
        parent_id=deterministic_provision_id(parent_path),
        level=1 if provision.kind == "document" else 2,
        ordinal=_provision_ordinal(provision.label),
        kind=provision.kind,
        language=_language_for_document(document),
        legal_identifier=_citation_label(provision),
        identifiers=identifiers,
        metadata={
            "title": document.title,
            "document_type": document.document_type,
            "numac": document.numac,
            "moniteur_url": document.moniteur_url,
            "justel_url": document.justel_url,
            "legal_authority_url": document.moniteur_url,
            "source_authority": provision.source_authority,
        },
    )


def _citation_label(provision: BelgianELIProvision) -> str:
    if provision.kind == "document":
        return provision.document.title
    return f"{provision.document.title} art. {provision.label}".strip()


def _article_source_url(document: BelgianELIDocument, label: str) -> str:
    base_url = document.justel_url or document.moniteur_url or _eli_document_url(document)
    return f"{base_url}#Art.{label}"


def _source_authority(source_url: str) -> str:
    if source_url.rstrip("/").lower().endswith("/justel") or "/justel#" in source_url.lower():
        return "non_authentic_consolidated_locator"
    return "official_original_publication"


def _document_parent_citation_path(document: BelgianELIDocument) -> str:
    return "/".join(
        [
            document.jurisdiction,
            document.document_class,
            document.document_type,
            document.year,
            document.month,
            document.day,
            document.numac,
        ]
    )


def _source_relative_name(source_name: str) -> str:
    moniteur_article_name = _moniteur_article_relative_name(source_name)
    if moniteur_article_name is not None:
        return moniteur_article_name
    eli_match = _ELI_PATH_RE.search(source_name)
    if eli_match is not None:
        parts = [
            "eli",
            eli_match.group("document_type").lower(),
            eli_match.group("year"),
            eli_match.group("month"),
            eli_match.group("day"),
        ]
        numac = eli_match.group("numac")
        version = eli_match.group("version")
        if numac is not None:
            parts.append(numac)
            if version is not None:
                parts.append(f"{version.lower()}.html")
            else:
                parts.append("document.html")
        else:
            parts.append("index.html")
        return "/".join(parts)
    parsed = urlparse(source_name)
    if parsed.scheme and parsed.netloc:
        return parsed.path.strip("/") or "source.html"
    return source_name


def _moniteur_article_relative_name(source_name: str) -> str | None:
    parsed = urlparse(source_name)
    if not parsed.path.endswith("/article.pl"):
        return None
    query = parse_qs(parsed.query)
    numac = _first_query_value(query, "numac_search")
    publication_date = _first_query_value(query, "sum_date")
    edition = _first_query_value(query, "s_editie") or "1"
    if not numac:
        return None
    if not publication_date:
        publication_date = "unknown-date"
    return f"moniteur/{publication_date}/edition-{edition}/{numac}.html"


def _source_key(
    jurisdiction: str,
    document_class: str,
    version: str,
    relative_name: str,
) -> str:
    return f"sources/{jurisdiction}/{document_class}/{version}/{relative_name}"


def _eli_document_url(document: BelgianELIDocument) -> str:
    return _eli_document_url_from_parts(
        document_type=document.document_type,
        year=document.year,
        month=document.month,
        day=document.day,
        numac=document.numac,
    )


def _eli_document_url_from_parts(
    *,
    document_type: str,
    year: str,
    month: str,
    day: str,
    numac: str,
) -> str:
    return f"{EJUSTICE_BASE_URL}/eli/{document_type}/{year}/{month}/{day}/{numac}"


def _versioned_eli_document_url(
    *,
    document_type: str,
    year: str,
    month: str,
    day: str,
    numac: str,
    version: str,
) -> str | None:
    if not version:
        return None
    return f"{EJUSTICE_BASE_URL}/eli/{document_type}/{year}/{month}/{day}/{numac}/{version}"


def _normalize_ejustice_url(url: str) -> str:
    normalized = url.strip().strip("\"'")
    if normalized.startswith("http://"):
        normalized = "https://" + normalized.removeprefix("http://")
    return normalized.rstrip(" >")


def _fallback_title(match: re.Match[str]) -> str:
    document_type = match.group("document_type")
    year = match.group("year")
    month = match.group("month")
    day = match.group("day")
    numac = match.group("numac") or "unknown"
    return f"{document_type} {day}-{month}-{year} {numac}"


def _language_for_document(document: BelgianELIDocument) -> str:
    if document.document_type in {"wet", "ordonnantie", "decreet", "besluit", "grondwet"}:
        return "nl"
    return "fr"


def _provision_ordinal(label: str) -> int | None:
    match = re.match(r"\d+", label)
    return int(match.group(0)) if match else None


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


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
