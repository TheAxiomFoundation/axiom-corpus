"""Client and downloader for the New Zealand Legislation API."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

NZ_LEGISLATION_API_BASE_URL = "https://api.legislation.govt.nz"
NZ_LEGISLATION_API_KEY_ENV = "NZ_LEGISLATION_API_KEY"
NZ_LEGISLATION_DEFAULT_TYPES = (
    "act",
    "secondary_legislation",
    "bill",
    "amendment_paper",
)


class NZLegislationAPIError(RuntimeError):
    """Raised when the NZ Legislation API or XML format fetch fails."""


@dataclass(frozen=True)
class NZLegislationAPISource:
    """One API-discovered source XML format URL."""

    work_id: str
    version_id: str
    title: str
    legislation_type: str
    legislation_status: str | None
    xml_url: str
    relative_path: str
    metadata: dict[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "version_id": self.version_id,
            "title": self.title,
            "legislation_type": self.legislation_type,
            "legislation_status": self.legislation_status,
            "xml_url": self.xml_url,
            "relative_path": self.relative_path,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class NZLegislationAPIDownloadReport:
    """Report for API XML discovery/download."""

    output_dir: Path
    discovered_count: int
    downloaded_count: int
    skipped_count: int
    failed_count: int
    sources: tuple[NZLegislationAPISource, ...]
    downloaded_paths: tuple[Path, ...]
    skipped_paths: tuple[Path, ...]
    failures: tuple[dict[str, str], ...]
    manifest_path: Path | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "discovered_count": self.discovered_count,
            "downloaded_count": self.downloaded_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "sources": [source.to_mapping() for source in self.sources],
            "downloaded_paths": [str(path) for path in self.downloaded_paths],
            "skipped_paths": [str(path) for path in self.skipped_paths],
            "failures": list(self.failures),
        }


class NZLegislationAPIClient:
    """Minimal synchronous client for api.legislation.govt.nz."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = NZ_LEGISLATION_API_BASE_URL,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("NZ Legislation API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
        self._client = None

    def __enter__(self) -> NZLegislationAPIClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_json(self, path: str, params: Mapping[str, str] | None = None) -> dict[str, Any]:
        """GET an API JSON endpoint with the configured API key."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self.client.get(
            url,
            headers={"Accept": "application/json", "X-Api-Key": self.api_key},
            params=dict(params or {}),
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise NZLegislationAPIError(f"unexpected JSON payload from {url}")
        return data

    def search_works(
        self,
        *,
        page: int,
        per_page: int,
        legislation_type: str | None = None,
        publisher: str | None = "Parliamentary Counsel Office",
        search_term: str | None = None,
        sort_by: str = "year_asc",
    ) -> dict[str, Any]:
        """Search works through the official v0 works endpoint."""
        params = {
            "page": str(page),
            "per_page": str(per_page),
            "sort_by": sort_by,
        }
        if legislation_type:
            params["legislation_type"] = legislation_type
        if publisher:
            params["publisher"] = publisher
        if search_term:
            params["search_term"] = search_term
            params["search_field"] = "title"
        return self.get_json("/v0/works/", params=params)

    def iter_work_rows(
        self,
        *,
        legislation_types: Sequence[str] = NZ_LEGISLATION_DEFAULT_TYPES,
        publisher: str | None = "Parliamentary Counsel Office",
        search_term: str | None = None,
        per_page: int = 100,
        max_pages: int | None = None,
        limit: int | None = None,
    ) -> Iterable[dict[str, Any]]:
        """Yield work rows across one or more legislation types."""
        yielded = 0
        for legislation_type in legislation_types:
            page = 1
            while True:
                payload = self.search_works(
                    page=page,
                    per_page=per_page,
                    legislation_type=legislation_type,
                    publisher=publisher,
                    search_term=search_term,
                )
                raw_results = payload.get("results") or []
                if not isinstance(raw_results, list):
                    raise NZLegislationAPIError("works response results must be a list")
                for row in raw_results:
                    if not isinstance(row, dict):
                        continue
                    yield row
                    yielded += 1
                    if limit is not None and yielded >= limit:
                        return
                if len(raw_results) < per_page:
                    break
                if max_pages is not None and page >= max_pages:
                    break
                page += 1

    def discover_latest_xml_sources(
        self,
        *,
        legislation_types: Sequence[str] = NZ_LEGISLATION_DEFAULT_TYPES,
        publisher: str | None = "Parliamentary Counsel Office",
        search_term: str | None = None,
        per_page: int = 100,
        max_pages: int | None = None,
        limit: int | None = None,
    ) -> tuple[NZLegislationAPISource, ...]:
        """Discover latest XML format URLs for API search results."""
        sources: list[NZLegislationAPISource] = []
        seen_versions: set[str] = set()
        rows = self.iter_work_rows(
            legislation_types=legislation_types,
            publisher=publisher,
            search_term=search_term,
            per_page=per_page,
            max_pages=max_pages,
            limit=limit,
        )
        for row in rows:
            source = _source_from_work_row(row)
            if source is None or source.version_id in seen_versions:
                continue
            seen_versions.add(source.version_id)
            sources.append(source)
        return tuple(sources)

    def download_xml(self, url: str) -> bytes:
        """Download a single XML format URL returned by the API."""
        response = self.client.get(
            url,
            headers={
                "Accept": "application/xml,text/xml,*/*",
                "X-Api-Key": self.api_key,
                "User-Agent": "Axiom/1.0 (max@axiom-foundation.org)",
            },
        )
        if response.status_code == 202 and response.headers.get("x-amzn-waf-action"):
            raise NZLegislationAPIError(f"XML URL returned WAF challenge: {url}")
        response.raise_for_status()
        content = response.content
        if not content.lstrip().startswith(b"<"):
            raise NZLegislationAPIError(f"XML URL did not return XML content: {url}")
        return content


def download_nz_legislation_api_sources(
    output_dir: str | Path,
    *,
    api_key: str,
    legislation_types: Sequence[str] = NZ_LEGISLATION_DEFAULT_TYPES,
    publisher: str | None = "Parliamentary Counsel Office",
    search_term: str | None = None,
    per_page: int = 100,
    max_pages: int | None = None,
    limit: int | None = None,
    resume: bool = True,
    allow_failures: bool = False,
    workers: int = 1,
    manifest_path: str | Path | None = None,
    client: NZLegislationAPIClient | None = None,
) -> NZLegislationAPIDownloadReport:
    """Discover and download XML source files from the official API."""
    if workers < 1:
        raise ValueError("workers must be at least 1")
    output_root = Path(output_dir)
    api_client = client or NZLegislationAPIClient(api_key)
    owns_client = client is None
    try:
        sources = api_client.discover_latest_xml_sources(
            legislation_types=legislation_types,
            publisher=publisher,
            search_term=search_term,
            per_page=per_page,
            max_pages=max_pages,
            limit=limit,
        )
        downloaded_paths: list[Path] = []
        skipped_paths: list[Path] = []
        failures: list[dict[str, str]] = []

        def download_source(source: NZLegislationAPISource) -> tuple[NZLegislationAPISource, Path]:
            target = output_root / source.relative_path
            content = api_client.download_xml(source.xml_url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return source, target

        pending_sources: list[NZLegislationAPISource] = []
        for source in sources:
            target = output_root / source.relative_path
            if resume and target.exists():
                skipped_paths.append(target)
            else:
                pending_sources.append(source)

        if workers == 1:
            for source in pending_sources:
                try:
                    _, target = download_source(source)
                except Exception as exc:
                    failures.append(
                        {
                            "work_id": source.work_id,
                            "version_id": source.version_id,
                            "xml_url": source.xml_url,
                            "error": str(exc),
                        }
                    )
                    if not allow_failures:
                        raise
                    continue
                downloaded_paths.append(target)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_source = {
                    executor.submit(download_source, source): source
                    for source in pending_sources
                }
                for future in as_completed(future_to_source):
                    source = future_to_source[future]
                    try:
                        _, target = future.result()
                    except Exception as exc:
                        failures.append(
                            {
                                "work_id": source.work_id,
                                "version_id": source.version_id,
                                "xml_url": source.xml_url,
                                "error": str(exc),
                            }
                        )
                        if not allow_failures:
                            raise
                        continue
                    downloaded_paths.append(target)
        resolved_manifest_path = Path(manifest_path) if manifest_path is not None else None
        report = NZLegislationAPIDownloadReport(
            output_dir=output_root,
            discovered_count=len(sources),
            downloaded_count=len(downloaded_paths),
            skipped_count=len(skipped_paths),
            failed_count=len(failures),
            sources=sources,
            downloaded_paths=tuple(downloaded_paths),
            skipped_paths=tuple(skipped_paths),
            failures=tuple(failures),
            manifest_path=resolved_manifest_path,
        )
        if resolved_manifest_path is not None:
            resolved_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_manifest_path.write_text(
                json.dumps(report.to_mapping(), indent=2, sort_keys=True) + "\n"
            )
        return report
    finally:
        if owns_client:
            api_client.close()


def _source_from_work_row(row: Mapping[str, Any]) -> NZLegislationAPISource | None:
    latest = row.get("latest_matching_version")
    if not isinstance(latest, dict):
        return None
    xml_url = _format_url(latest.get("formats"), "xml")
    if not xml_url:
        return None
    work_id = str(row.get("work_id") or "")
    version_id = str(latest.get("version_id") or "")
    if not work_id or not version_id:
        return None
    title = str(latest.get("title") or row.get("title") or "")
    legislation_type = str(row.get("legislation_type") or "")
    return NZLegislationAPISource(
        work_id=work_id,
        version_id=version_id,
        title=title,
        legislation_type=legislation_type,
        legislation_status=(
            str(row["legislation_status"]) if row.get("legislation_status") is not None else None
        ),
        xml_url=xml_url,
        relative_path=_relative_xml_path(work_id, version_id),
        metadata={
            "latest_matching_version_is_latest": latest.get("is_latest_version"),
            "formats": latest.get("formats"),
            "administering_agencies": row.get("administering_agencies"),
            "publisher": row.get("publisher"),
        },
    )


def _format_url(formats: object, format_type: str) -> str | None:
    if not isinstance(formats, list):
        return None
    for item in formats:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").lower()
        url = str(item.get("url") or "")
        if item_type == format_type or url.rstrip("/").lower().endswith(f".{format_type}"):
            return url
    return None


def _relative_xml_path(work_id: str, version_id: str) -> str:
    parts = work_id.split("_")
    if len(parts) >= 4:
        leg_type, subtype, year, number = parts[:4]
        return "/".join(
            [
                _safe_segment(leg_type),
                _safe_segment(subtype),
                _safe_segment(year),
                _safe_segment(number),
                f"{_safe_segment(version_id)}.xml",
            ]
        )
    return f"{_safe_segment(version_id)}.xml"


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._~-]+", "-", value.strip()).strip("-")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError(f"unsafe NZ legislation source segment: {value!r}")
    return cleaned
