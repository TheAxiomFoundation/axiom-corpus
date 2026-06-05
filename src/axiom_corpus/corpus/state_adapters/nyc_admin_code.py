"""NYC Administrative Code targeted source-first corpus adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.supabase import deterministic_provision_id

NYC_ADMIN_CODE_SOURCE_FORMAT = "nyc-admin-code-amlegal-html"
NYC_ADMIN_CODE_USER_AGENT = (
    "axiom-corpus/0.1 (NYC Administrative Code ingestion; contact@axiom-foundation.org)"
)

DEFAULT_NYC_ADMIN_CODE_SECTIONS = {
    "11-1701": "https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13463",
    "11-1704.1": "https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13565",
    "11-1706": "https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13608",
}

_SECTION_HEADING_RE = re.compile(r"^§\s*(?P<section>\d{1,2}-\d+(?:\.\d+)?)\s+(?P<title>.+)$")


@dataclass(frozen=True)
class NycAdminCodePage:
    section: str
    source_url: str
    relative_path: str
    data: bytes


def extract_nyc_admin_code(
    store: CorpusArtifactStore,
    *,
    version: str,
    sections: tuple[str, ...] | None = None,
    urls: tuple[str, ...] | None = None,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    timeout_seconds: float = 20.0,
    session: requests.Session | None = None,
) -> StateStatuteExtractReport:
    """Extract selected NYC Administrative Code sections from CodeLibrary pages."""
    jurisdiction = "us-ny"
    run_id = f"{version}-nyc-admin-code"
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)
    selected = _selected_sections(sections, urls)
    if not selected:
        raise ValueError("no NYC Administrative Code sections selected")

    source_root = Path(source_dir) if source_dir is not None else None
    download_root = Path(download_dir) if download_dir is not None else None
    http = session or requests.Session()
    http.headers.update({"User-Agent": NYC_ADMIN_CODE_USER_AGENT})

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    source_paths: list[Path] = []
    errors: list[str] = []
    skipped_source_count = 0

    for ordinal, (section, source_url) in enumerate(selected):
        try:
            page = _fetch_page(
                section,
                source_url,
                source_dir=source_root,
                download_dir=download_root,
                timeout_seconds=timeout_seconds,
                session=http,
            )
            artifact_path = store.source_path(
                jurisdiction,
                DocumentClass.STATUTE,
                run_id,
                page.relative_path,
            )
            sha256 = store.write_bytes(artifact_path, page.data)
            source_paths.append(artifact_path)
            source_key = _state_source_key(jurisdiction, run_id, page.relative_path)
            parsed = parse_nyc_admin_code_section(
                page.data,
                section_hint=section,
                source_url=page.source_url,
            )
            citation_path = f"us-ny/statute/NYC/{parsed.section}"
            metadata = {
                "kind": "section",
                "law_id": "NYC",
                "location_id": parsed.section,
                "display_number": parsed.section,
                "publisher": "American Legal Publishing Code Library",
                "source_caveat": "CodeLibrary publishes the NYC Administrative Code online; verify against official legislative history for evidentiary use.",
            }
            items.append(
                SourceInventoryItem(
                    citation_path=citation_path,
                    source_url=page.source_url,
                    source_path=source_key,
                    source_format=NYC_ADMIN_CODE_SOURCE_FORMAT,
                    sha256=sha256,
                    metadata=metadata,
                )
            )
            records.append(
                ProvisionRecord(
                    jurisdiction=jurisdiction,
                    document_class=DocumentClass.STATUTE.value,
                    citation_path=citation_path,
                    id=deterministic_provision_id(citation_path, run_id),
                    body=parsed.body,
                    heading=parsed.heading,
                    citation_label=f"NYC Administrative Code § {parsed.section}",
                    version=run_id,
                    source_url=page.source_url,
                    source_path=source_key,
                    source_id=parsed.section,
                    source_format=NYC_ADMIN_CODE_SOURCE_FORMAT,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    parent_citation_path="us-ny/statute/NYC",
                    level=1,
                    ordinal=ordinal,
                    kind="section",
                    legal_identifier=f"NYC Administrative Code § {parsed.section}",
                    identifiers={
                        "law_id": "NYC",
                        "location_id": parsed.section,
                        "display_number": parsed.section,
                    },
                    metadata=metadata,
                )
            )
        except Exception as exc:
            skipped_source_count += 1
            errors.append(f"{section}: {exc}")

    if not items:
        raise ValueError("no NYC Administrative Code provisions extracted")

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
        title_count=0,
        container_count=0,
        section_count=len(records),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        skipped_source_count=skipped_source_count,
        errors=tuple(errors),
    )


@dataclass(frozen=True)
class ParsedNycAdminCodeSection:
    section: str
    heading: str
    body: str


def parse_nyc_admin_code_section(
    html: bytes | str,
    *,
    section_hint: str | None = None,
    source_url: str | None = None,
) -> ParsedNycAdminCodeSection:
    soup = BeautifulSoup(html, "html.parser")
    for selector in ("script", "style", "nav", "header", "footer"):
        for node in soup.select(selector):
            node.decompose()
    content = (
        soup.select_one(".codenav__section-body")
        or soup.select_one("div.Section.toc-destination.rbox")
        or soup.select_one("#codecontent")
        or soup
    )
    text = _clean_text(content.get_text("\n"))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    start_index = _find_heading_index(lines, section_hint)
    heading = lines[start_index]
    match = _SECTION_HEADING_RE.match(heading)
    if match is None:
        if section_hint is None:
            raise ValueError(f"could not identify NYC section heading in {source_url or 'HTML'}")
        section = section_hint
    else:
        section = match.group("section")
    if section_hint and section != section_hint:
        raise ValueError(f"expected section {section_hint}, found {section}")
    if heading.strip() == f"§ {section}" and start_index + 1 < len(lines):
        heading = f"{heading} {lines[start_index + 1]}"
    body_lines = _body_lines(lines[start_index:])
    body = "\n".join(body_lines).strip()
    if not body:
        raise ValueError(f"empty body for NYC Administrative Code § {section}")
    return ParsedNycAdminCodeSection(section=section, heading=heading, body=body)


def _selected_sections(
    sections: tuple[str, ...] | None,
    urls: tuple[str, ...] | None,
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    default_sections = (
        tuple(DEFAULT_NYC_ADMIN_CODE_SECTIONS)
        if sections is None and urls is None
        else ()
    )
    for section in (sections if sections is not None else default_sections):
        normalized = section.strip()
        if not normalized:
            continue
        source_url = DEFAULT_NYC_ADMIN_CODE_SECTIONS.get(normalized)
        if source_url is None:
            raise ValueError(f"no default NYC Administrative Code URL for section {normalized!r}")
        rows.append((normalized, source_url))
    for raw in urls or ():
        if "=" not in raw:
            raise ValueError("--url values must be SECTION=URL")
        section, source_url = raw.split("=", 1)
        rows.append((section.strip(), source_url.strip()))
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for section, source_url in rows:
        if section in seen:
            continue
        seen.add(section)
        deduped.append((section, source_url))
    return tuple(deduped)


def _fetch_page(
    section: str,
    source_url: str,
    *,
    source_dir: Path | None,
    download_dir: Path | None,
    timeout_seconds: float,
    session: requests.Session,
) -> NycAdminCodePage:
    relative_path = _relative_path(section, source_url)
    if source_dir is not None:
        path = source_dir / relative_path
        if not path.exists():
            raise FileNotFoundError(relative_path)
        return NycAdminCodePage(
            section=section,
            source_url=source_url,
            relative_path=relative_path,
            data=path.read_bytes(),
        )
    if download_dir is not None:
        cached_path = download_dir / relative_path
        if cached_path.exists():
            return NycAdminCodePage(
                section=section,
                source_url=source_url,
                relative_path=relative_path,
                data=cached_path.read_bytes(),
            )
    response = session.get(source_url, timeout=timeout_seconds)
    response.raise_for_status()
    data = response.content
    if download_dir is not None:
        cached_path = download_dir / relative_path
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        cached_path.write_bytes(data)
    return NycAdminCodePage(
        section=section,
        source_url=response.url,
        relative_path=relative_path,
        data=data,
    )


def _relative_path(section: str, source_url: str) -> str:
    parsed = urlparse(source_url)
    page_id = Path(parsed.path).name or section
    return f"{NYC_ADMIN_CODE_SOURCE_FORMAT}/{section}/{page_id}.html"


def _find_heading_index(lines: list[str], section_hint: str | None) -> int:
    expected = f"§ {section_hint}" if section_hint else "§ "
    for index, line in enumerate(lines):
        if line.startswith(expected):
            return index
    for index, line in enumerate(lines):
        if _SECTION_HEADING_RE.match(line):
            return index
    raise ValueError("could not find NYC Administrative Code section heading")


def _body_lines(lines: list[str]) -> list[str]:
    stops = {
        "Disclaimer:",
        "View Full Site",
        "Hosted by:",
        "Back to Top",
        "Keyboard:",
    }
    body: list[str] = []
    for line in lines:
        if any(line.startswith(stop) for stop in stops):
            break
        if line in {
            "New York City Administrative Code",
            "Title 11: Taxation and Finance",
            "Share",
            "Download",
            "Bookmark",
            "Print",
        }:
            continue
        body.append(line)
    return body


def _clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _state_source_key(jurisdiction: str, run_id: str, relative_path: str) -> str:
    return f"sources/{jurisdiction}/{DocumentClass.STATUTE.value}/{run_id}/{relative_path}"
