"""Supabase row projection for normalized provision JSONL."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TextIO
from uuid import NAMESPACE_URL, UUID, uuid5

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope

DEFAULT_AXIOM_SUPABASE_URL = "https://swocpijqqahhuwtuahwc.supabase.co"
DEFAULT_SERVICE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
DEFAULT_ACCESS_TOKEN_ENV = "SUPABASE_ACCESS_TOKEN"
USER_AGENT = "axiom-corpus/0.1"
POSTGRES_INT32_MIN = -(2**31)
POSTGRES_INT32_MAX = 2**31 - 1

SUPABASE_PROVISIONS_COLUMNS = (
    "id",
    "jurisdiction",
    "doc_type",
    "parent_id",
    "level",
    "ordinal",
    "heading",
    "body",
    "source_url",
    "source_path",
    "citation_path",
    "version",
    "rulespec_path",
    "has_rulespec",
    "source_document_id",
    "source_as_of",
    "expression_date",
    "language",
    "legal_identifier",
    "identifiers",
)


@dataclass(frozen=True)
class SupabaseLoadReport:
    rows_total: int
    rows_loaded: int
    chunk_count: int
    dry_run: bool = False
    existing_id_count: int = 0
    refreshed: bool = False
    refresh_error: str | None = None
    auto_registered_scopes: tuple[dict[str, object], ...] = ()
    synthesized_parents: int = 0
    superseded_skipped: int = 0

    def to_mapping(self) -> dict[str, object]:
        return {
            "rows_total": self.rows_total,
            "rows_loaded": self.rows_loaded,
            "chunk_count": self.chunk_count,
            "dry_run": self.dry_run,
            "existing_id_count": self.existing_id_count,
            "refreshed": self.refreshed,
            "refresh_error": self.refresh_error,
            "auto_registered_scopes": [dict(s) for s in self.auto_registered_scopes],
            "synthesized_parents": self.synthesized_parents,
            "superseded_skipped": self.superseded_skipped,
        }


@dataclass(frozen=True)
class SupabaseDeleteReport:
    intended_rows_deleted: int
    delete_chunk_count: int
    dry_run: bool = False

    def to_mapping(self) -> dict[str, object]:
        return {
            "intended_rows_deleted": self.intended_rows_deleted,
            "delete_chunk_count": self.delete_chunk_count,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class SupabaseReleaseScopeSyncReport:
    release_name: str
    rows_total: int
    rows_loaded: int
    chunk_count: int
    dry_run: bool = False
    refreshed: bool = False
    refresh_error: str | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "release_name": self.release_name,
            "rows_total": self.rows_total,
            "rows_loaded": self.rows_loaded,
            "chunk_count": self.chunk_count,
            "dry_run": self.dry_run,
            "refreshed": self.refreshed,
            "refresh_error": self.refresh_error,
        }


@dataclass(frozen=True)
class ReleaseCoverageFinding:
    """A jurisdiction × document_class with navigation rows but no current provisions."""

    jurisdiction: str
    document_class: str
    navigation_node_count: int
    current_provision_count: int

    def to_mapping(self) -> dict[str, object]:
        return {
            "jurisdiction": self.jurisdiction,
            "document_class": self.document_class,
            "navigation_node_count": self.navigation_node_count,
            "current_provision_count": self.current_provision_count,
        }


@dataclass(frozen=True)
class ReleaseCoverageReport:
    """Result of verifying the navigation → current_provisions join.

    The view ``corpus.current_provisions`` exists if and only if there is a
    matching row in ``corpus.release_scopes`` (release_name='current',
    active=true). A jurisdiction with navigation rows but no matching release
    scope row produces ``current_provision_count == 0`` here — the historical
    UK failure mode that left rows unreachable to consumers.
    """

    checked_at: str
    missing_current_provisions: tuple[ReleaseCoverageFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.missing_current_provisions

    def to_mapping(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checked_at": self.checked_at,
            "missing_current_provisions": [
                f.to_mapping() for f in self.missing_current_provisions
            ],
        }


def verify_release_coverage(
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
) -> ReleaseCoverageReport:
    """Check the invariant: any jurisdiction with navigation rows must also
    have rows in ``corpus.current_provisions``.

    Reads two PostgREST views:
      * ``navigation_node_counts`` — per (jurisdiction, doc_type) row counts
        derived from active-release navigation rows
      * ``current_provision_counts`` — per (jurisdiction, document_class)
        row counts from corpus.current_provisions

    Reports any (jurisdiction, doc_type) pair where navigation has rows and
    current_provisions has zero. The historical UK regression (4,705 nav rows,
    0 current_provisions) is exactly this shape.
    """
    rest_url = _rest_url(supabase_url)
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept": "application/json",
        "Accept-Profile": "corpus",
        "User-Agent": USER_AGENT,
    }

    nav_counts = _fetch_navigation_node_counts(rest_url, headers)
    current_counts = _fetch_current_provision_counts(rest_url, headers)
    current_keys = {
        (row["jurisdiction"], row["document_class"]) for row in current_counts
    }

    missing: list[ReleaseCoverageFinding] = []
    for nav in nav_counts:
        jurisdiction = str(nav["jurisdiction"])
        document_class = str(nav["document_class"])
        count_value = nav["count"]
        count = int(count_value) if isinstance(count_value, int | str) else 0
        if count > 0 and (jurisdiction, document_class) not in current_keys:
            missing.append(
                ReleaseCoverageFinding(
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    navigation_node_count=count,
                    current_provision_count=0,
                )
            )

    return ReleaseCoverageReport(
        checked_at=datetime.now(UTC).isoformat(),
        missing_current_provisions=tuple(sorted(
            missing, key=lambda f: (f.jurisdiction, f.document_class)
        )),
    )


def _fetch_navigation_node_counts(
    rest_url: str, headers: dict[str, str]
) -> tuple[dict[str, object], ...]:
    """Get GROUP BY (jurisdiction, doc_type) counts via the corpus RPC.

    We do this server-side because corpus.navigation_nodes is ~2.4M rows
    and PostgREST caps responses at 1000 — paginating the whole table
    would take thousands of round trips. The RPC
    ``corpus.get_navigation_node_counts`` returns ~70 current-release rows
    in one call. See migrations 20260512170000_navigation_node_counts_rpc.sql
    and 20260513101000_version_aware_navigation_nodes.sql.
    """
    # POST RPC resolves the schema from Content-Profile, not Accept-Profile.
    # Without it PostgREST defaults to `public` and returns 404 for the
    # corpus.* function.
    req = urllib.request.Request(
        f"{rest_url}/rpc/get_navigation_node_counts",
        data=b"{}",
        method="POST",
        headers={
            **headers,
            "Content-Type": "application/json",
            "Content-Profile": "corpus",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list):
        return ()
    out: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            "jurisdiction": str(row.get("jurisdiction") or ""),
            "document_class": str(row.get("document_class") or "unknown"),
            "count": int(row.get("node_count") or 0),
        })
    return tuple(out)


def _fetch_current_provision_counts(
    rest_url: str, headers: dict[str, str]
) -> tuple[dict[str, object], ...]:
    query = urllib.parse.urlencode({
        "select": "jurisdiction,document_class,provision_count",
    })
    req = urllib.request.Request(
        f"{rest_url}/current_provision_counts?{query}",
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list):
        return ()
    return tuple(
        {
            "jurisdiction": str(row.get("jurisdiction") or ""),
            "document_class": str(row.get("document_class") or "unknown"),
            "count": int(row.get("provision_count") or 0),
        }
        for row in rows
        if isinstance(row, dict)
    )


def deterministic_provision_id(citation_path: str, version: str | None = None) -> str:
    """Return the stable UUID used by `corpus.provisions` ingests.

    Historical callers passed only a citation path, so that form intentionally
    keeps the old UUID. Supabase loads now pass a release version as well so
    the same citation can exist in multiple staged/published versions.
    """
    normalized_version = _normalize_version(version)
    if normalized_version is None:
        return str(uuid5(NAMESPACE_URL, f"axiom:{citation_path}"))
    identity = json.dumps(
        ["axiom", normalized_version, citation_path],
        separators=(",", ":"),
    )
    return str(uuid5(NAMESPACE_URL, identity))


def _normalize_version(version: str | None) -> str | None:
    if version is None:
        return None
    normalized = str(version).strip()
    return normalized or None


# `corpus.provisions` columns whose SQL type is `date`. A malformed value here
# (e.g. an ingest that wrote the whole version slug `2026-07-01-be-...` instead
# of a date) makes Postgres parse the trailing text as a time zone and reject
# the entire upsert chunk with 22023 "time zone ... not recognized". Coerce
# defensively so one bad metadata field can never fail a whole scope's publish.
DATE_COLUMNS = ("expression_date", "source_as_of")

_ISO_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _coerce_date_column_value(value: object) -> tuple[object, str | None]:
    """Return (postgres-safe date value, original-if-coerced).

    Valid ISO dates/timestamps pass through unchanged. A value whose leading
    ``YYYY-MM-DD`` is a real calendar date but which carries trailing non-date
    text (the version-slug ingest bug) is truncated to that date prefix.
    Anything else non-empty becomes ``None``. The second tuple element is the
    original string when a coercion happened (for provenance), else ``None``.
    """
    if value is None or not isinstance(value, str):
        return value, None
    raw = value.strip()
    if not raw:
        return None, None
    # Already a value Postgres accepts for a date column (bare date or a full
    # ISO timestamp it will cast down to the date) — leave untouched.
    try:
        date.fromisoformat(raw)
        return raw, None
    except ValueError:
        pass
    try:
        datetime.fromisoformat(raw)
        return raw, None
    except ValueError:
        pass
    match = _ISO_DATE_PREFIX_RE.match(raw)
    if match:
        prefix = match.group(1)
        try:
            date.fromisoformat(prefix)
        except ValueError:
            return None, raw
        return prefix, raw
    return None, raw


def _version_date_prefix(version: str | None) -> str | None:
    """The leading ``YYYY-MM-DD`` of a version string, if it is a real date.

    Version strings are ``<iso-date>-<slug>`` (e.g. ``2026-07-06-ny-tax-...``);
    the date prefix orders versions chronologically and sorts correctly as a
    plain string. Returns ``None`` when there is no parseable date prefix, so
    callers treat "cannot compare" as "not superseded" (never skip on doubt).
    """
    if not version:
        return None
    match = _ISO_DATE_PREFIX_RE.match(str(version).strip())
    if not match:
        return None
    prefix = match.group(1)
    try:
        date.fromisoformat(prefix)
    except ValueError:
        return None
    return prefix


def _release_document_class(document_class: str | None) -> str:
    normalized = str(document_class or "").strip()
    return normalized or "unknown"


def _uuid_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


def _sanitize_supabase_value(value: object) -> object:
    """Remove characters Postgres cannot store from text/jsonb values."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {
            str(_sanitize_supabase_value(key)): _sanitize_supabase_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_supabase_value(item) for item in value]
    return value


def provision_to_supabase_row(
    record: ProvisionRecord,
    *,
    versioned_ids: bool = True,
) -> dict[str, object]:
    """Project a normalized provision record into the `corpus.provisions` shape."""
    version = _normalize_version(record.version)
    legacy_provision_id = deterministic_provision_id(record.citation_path)
    if versioned_ids and version is not None and (
        record.id is None or record.id == legacy_provision_id
    ):
        provision_id = deterministic_provision_id(record.citation_path, version)
    else:
        provision_id = record.id or legacy_provision_id
    parent_id = record.parent_id
    if parent_id is None and record.parent_citation_path:
        parent_id = deterministic_provision_id(
            record.parent_citation_path,
            version if versioned_ids else None,
        )
    elif versioned_ids and version is not None and record.parent_citation_path:
        legacy_parent_id = deterministic_provision_id(record.parent_citation_path)
        if parent_id == legacy_parent_id:
            parent_id = deterministic_provision_id(record.parent_citation_path, version)
    source_document_id = _uuid_or_none(record.source_document_id)
    identifiers = dict(record.identifiers or {})
    if record.source_document_id is not None and source_document_id is None:
        identifiers.setdefault("source:document_id", record.source_document_id)

    # Coerce date columns so a malformed metadata value (the version-slug ingest
    # bug) can never fail the upsert; keep the original in identifiers so the
    # coercion is provenance-visible rather than silent.
    source_as_of, raw_source_as_of = _coerce_date_column_value(record.source_as_of)
    expression_date, raw_expression_date = _coerce_date_column_value(record.expression_date)
    if raw_source_as_of is not None:
        identifiers.setdefault("corpus:raw_source_as_of", raw_source_as_of)
    if raw_expression_date is not None:
        identifiers.setdefault("corpus:raw_expression_date", raw_expression_date)

    row: dict[str, object] = {
        "id": provision_id,
        "jurisdiction": record.jurisdiction,
        "doc_type": record.document_class,
        "parent_id": parent_id,
        "level": record.level,
        "ordinal": record.ordinal,
        "heading": record.heading,
        "body": record.body,
        "source_url": record.source_url,
        "source_path": record.source_path,
        "citation_path": record.citation_path,
        "version": version,
        "rulespec_path": record.rulespec_path,
        "has_rulespec": bool(record.has_rulespec) if record.has_rulespec is not None else False,
        "source_document_id": source_document_id,
        "source_as_of": source_as_of,
        "expression_date": expression_date,
        "language": record.language,
        "legal_identifier": record.legal_identifier,
        "identifiers": identifiers,
    }
    return {key: _sanitize_supabase_value(value) for key, value in row.items()}


def iter_supabase_rows(
    records: Iterable[ProvisionRecord],
    *,
    versioned_ids: bool = True,
) -> Iterator[dict[str, object]]:
    for index, record in enumerate(records):
        row = provision_to_supabase_row(record, versioned_ids=versioned_ids)
        ordinal = row.get("ordinal")
        if (
            isinstance(ordinal, int)
            and not isinstance(ordinal, bool)
            and not POSTGRES_INT32_MIN <= ordinal <= POSTGRES_INT32_MAX
        ):
            raw_identifiers = row.get("identifiers")
            identifiers: dict[str, object] = (
                dict(raw_identifiers) if isinstance(raw_identifiers, Mapping) else {}
            )
            identifiers.setdefault("corpus:ordinal", ordinal)
            row["identifiers"] = identifiers
            # Production `corpus.provisions.ordinal` is still int4. Preserve
            # sibling order for Supabase queries without mutating corpus JSON.
            row["ordinal"] = index
        yield row


def write_supabase_rows_jsonl(path: str | Path, records: Iterable[ProvisionRecord]) -> int:
    """Write rows ready for a Supabase REST upsert payload as JSONL."""
    rows = tuple(iter_supabase_rows(records))
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else "")
    )
    return len(rows)


def fetch_provision_counts(
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
    include_legacy: bool = False,
) -> tuple[dict[str, object], ...]:
    """Fetch production provision-count rows.

    By default this reads the current release boundary. Set
    ``include_legacy=True`` for a full table snapshot that includes scopes not
    present in the current release manifest.
    """
    table_name = "provision_counts" if include_legacy else "current_provision_counts"
    query = urllib.parse.urlencode(
        {
            "select": (
                "jurisdiction,document_class,provision_count,body_count,"
                "top_level_count,rulespec_count,refreshed_at"
            ),
            "order": "jurisdiction.asc,document_class.asc",
        }
    )
    req = urllib.request.Request(
        f"{_rest_url(supabase_url)}/{table_name}?{query}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Accept-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list):
        raise RuntimeError("unexpected Supabase provision-count response")
    return tuple(_normalize_count_row(row) for row in rows if isinstance(row, dict))


def fetch_release_provision_counts(
    release: ReleaseManifest,
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
) -> tuple[dict[str, object], ...]:
    """Count provisions directly for a release manifest.

    Prefer the server-side manifest-count RPC so a full release count is a
    single database aggregate instead of hundreds of HTTP count requests.
    Falling back keeps older databases usable before the RPC migration lands.
    """
    rest_url = _rest_url(supabase_url)
    try:
        rows = _fetch_release_provision_counts_rpc(
            release,
            service_key=service_key,
            rest_url=rest_url,
        )
        return _fill_zero_release_counts_from_provisions(
            rows,
            release,
            service_key=service_key,
            rest_url=rest_url,
        )
    except urllib.error.HTTPError as exc:
        if not _is_missing_release_counts_rpc(exc):
            raise
    return _fetch_release_provision_counts_direct(
        release,
        service_key=service_key,
        rest_url=rest_url,
    )


def _fill_zero_release_counts_from_provisions(
    rows: tuple[dict[str, object], ...],
    release: ReleaseManifest,
    *,
    service_key: str,
    rest_url: str,
) -> tuple[dict[str, object], ...]:
    """Correct stale zero rows from materialized scope-count snapshots."""

    zero_keys = {
        (str(row.get("jurisdiction") or ""), str(row.get("document_class") or ""))
        for row in rows
        if _row_int(row.get("provision_count")) == 0
    }
    if not zero_keys:
        return rows
    fallback_scopes = tuple(
        scope for scope in release.scopes if (scope.jurisdiction, scope.document_class) in zero_keys
    )
    if not fallback_scopes:
        return rows
    fallback_rows = _fetch_release_provision_counts_direct(
        ReleaseManifest(name=f"{release.name}-zero-count-fallback", scopes=fallback_scopes),
        service_key=service_key,
        rest_url=rest_url,
    )
    fallback_by_key = {
        (str(row["jurisdiction"]), str(row["document_class"])): row
        for row in fallback_rows
    }
    corrected: list[dict[str, object]] = []
    for row in rows:
        key = (str(row.get("jurisdiction") or ""), str(row.get("document_class") or ""))
        fallback = fallback_by_key.get(key)
        if fallback is not None:
            corrected.append(fallback)
        else:
            corrected.append(row)
    return tuple(corrected)


def _row_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0


def _fetch_release_provision_counts_rpc(
    release: ReleaseManifest,
    *,
    service_key: str,
    rest_url: str,
) -> tuple[dict[str, object], ...]:
    payload = {
        "p_scopes": [
            {
                "jurisdiction": scope.jurisdiction,
                "document_class": scope.document_class,
                "version": scope.version,
            }
            for scope in release.scopes
        ]
    }
    req = urllib.request.Request(
        f"{rest_url}/rpc/get_release_provision_counts",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Accept-Profile": "corpus",
            "Content-Type": "application/json",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    if not isinstance(data, list):
        raise RuntimeError("unexpected Supabase release-count response")
    return tuple(_normalize_count_row(row) for row in data if isinstance(row, dict))


def _is_missing_release_counts_rpc(exc: urllib.error.HTTPError) -> bool:
    if exc.code == 404:
        return True
    if exc.code != 400:
        return False
    body = exc.read().decode("utf-8", errors="replace")
    return "PGRST202" in body or "get_release_provision_counts" in body


def _fetch_release_provision_counts_direct(
    release: ReleaseManifest,
    *,
    service_key: str,
    rest_url: str,
) -> tuple[dict[str, object], ...]:
    refreshed_at = datetime.now(UTC).isoformat()
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for scope in release.scopes:
        key = (scope.jurisdiction, scope.document_class)
        row = grouped.setdefault(
            key,
            {
                "jurisdiction": scope.jurisdiction,
                "document_class": scope.document_class,
                "provision_count": 0,
                "body_count": 0,
                "top_level_count": 0,
                "rulespec_count": 0,
                "refreshed_at": refreshed_at,
            },
        )
        _add_count(
            row,
            "provision_count",
            _count_provisions_scope(
                scope,
                service_key=service_key,
                rest_url=rest_url,
            ),
        )
        _add_count(
            row,
            "body_count",
            _count_provisions_scope(
                scope,
                service_key=service_key,
                rest_url=rest_url,
                extra_filters={"body": "not.is.null"},
            ),
        )
        _add_count(
            row,
            "top_level_count",
            _count_provisions_scope(
                scope,
                service_key=service_key,
                rest_url=rest_url,
                extra_filters={"parent_id": "is.null"},
            ),
        )
        _add_count(
            row,
            "rulespec_count",
            _count_provisions_scope(
                scope,
                service_key=service_key,
                rest_url=rest_url,
                extra_filters={"has_rulespec": "eq.true"},
            ),
        )
    return tuple(grouped[key] for key in sorted(grouped))


def _add_count(row: dict[str, object], key: str, increment: int) -> None:
    current = row.get(key)
    if not isinstance(current, int):
        raise RuntimeError(f"release count field is not an integer: {key}")
    row[key] = current + increment


def _count_provisions_scope(
    scope: ReleaseScope,
    *,
    service_key: str,
    rest_url: str,
    extra_filters: Mapping[str, str] | None = None,
) -> int:
    params = {
        "select": "id",
        "jurisdiction": f"eq.{scope.jurisdiction}",
        "doc_type": f"eq.{scope.document_class}",
        "version": f"eq.{scope.version}",
    }
    if extra_filters:
        params.update(extra_filters)
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{rest_url}/provisions?{query}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Accept-Profile": "corpus",
            "Prefer": "count=exact",
            "Range": "0-0",
            "User-Agent": USER_AGENT,
        },
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return _count_from_content_range(resp.headers.get("Content-Range"))
    except urllib.error.HTTPError as exc:
        if exc.code < 500:
            raise
        return _count_provisions_scope_by_pages(
            scope,
            service_key=service_key,
            rest_url=rest_url,
            extra_filters=extra_filters,
        )


def _count_from_content_range(value: str | None) -> int:
    if not value or "/" not in value:
        raise RuntimeError("Supabase count response missing Content-Range")
    total = value.rsplit("/", 1)[1]
    if total == "*":
        raise RuntimeError("Supabase count response did not include an exact total")
    return int(total)


def _count_provisions_scope_by_pages(
    scope: ReleaseScope,
    *,
    service_key: str,
    rest_url: str,
    extra_filters: Mapping[str, str] | None = None,
    page_size: int = 1_000,
) -> int:
    count = 0
    last_id: str | None = None
    while True:
        params = {
            "select": "id",
            "jurisdiction": f"eq.{scope.jurisdiction}",
            "doc_type": f"eq.{scope.document_class}",
            "version": f"eq.{scope.version}",
            "order": "id.asc",
            "limit": str(page_size),
        }
        if extra_filters:
            params.update(extra_filters)
        if last_id is not None:
            params["id"] = f"gt.{last_id}"
        query = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{rest_url}/provisions?{query}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Accept": "application/json",
                "Accept-Profile": "corpus",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            rows = json.loads(resp.read())
        if not isinstance(rows, list):
            raise RuntimeError("unexpected Supabase provisions response")
        count += len(rows)
        if len(rows) < page_size:
            return count
        last_row = rows[-1]
        if not isinstance(last_row, dict) or not last_row.get("id"):
            return count
        last_id = str(last_row["id"])


def sync_release_scopes_to_supabase(
    release: ReleaseManifest,
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
    chunk_size: int = 500,
    refresh: bool = True,
    dry_run: bool = False,
    allow_refresh_failure: bool = False,
    exclusive: bool = False,
) -> SupabaseReleaseScopeSyncReport:
    """Sync the Supabase release-scope set from a release manifest.

    Default behavior (``exclusive=False``) is **upsert-incremental**: each
    scope in the manifest is upserted (insert-or-update) into
    ``corpus.release_scopes`` with ``active=true``. Scopes already in the
    table but NOT in the manifest are left untouched. Safe to run from a
    feature branch whose manifest is a subset of production state.

    ``exclusive=True`` opts into the older "deactivate all then reinsert"
    semantics: every existing active row for ``release.name`` is marked
    inactive first, then the manifest's rows are inserted active. Use only
    when you specifically want to enforce that the manifest is the complete
    set of active scopes for the release — typically not what you want from
    a branch that does not have full coverage of production.

    The historical default was ``exclusive=True``. That behavior caused a
    silent unpromotion of ``us-wa/regulation`` on 2026-05-12 when a feature
    branch's manifest was used to sync (the WAC scope existed on a
    different branch). The new default eliminates this class of regression.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    rest_url = _rest_url(supabase_url)
    synced_at = datetime.now(UTC).isoformat()
    rows = [
        release_scope_to_supabase_row(
            scope,
            release_name=release.name,
            synced_at=synced_at,
        )
        for scope in release.scopes
    ]
    chunk_count = 0
    if rows:
        chunk_count = (len(rows) + chunk_size - 1) // chunk_size

    if not dry_run:
        if exclusive:
            deactivate_release_scope_rows(
                release_name=release.name,
                service_key=service_key,
                rest_url=rest_url,
            )
        for chunk in _chunked(iter(rows), chunk_size):
            upsert_release_scope_rows(chunk, service_key=service_key, rest_url=rest_url)

    refreshed = False
    refresh_error = None
    if refresh and not dry_run:
        try:
            refresh_corpus_analytics(service_key=service_key, rest_url=rest_url)
            refreshed = True
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            refresh_error = str(exc)
            if not allow_refresh_failure:
                raise RuntimeError(f"corpus analytics refresh failed: {exc}") from exc

    return SupabaseReleaseScopeSyncReport(
        release_name=release.name,
        rows_total=len(rows),
        rows_loaded=0 if dry_run else len(rows),
        chunk_count=chunk_count,
        dry_run=dry_run,
        refreshed=refreshed,
        refresh_error=refresh_error,
    )


def release_scope_to_supabase_row(
    scope: ReleaseScope,
    *,
    release_name: str,
    synced_at: str,
) -> dict[str, object]:
    return {
        "release_name": release_name,
        "jurisdiction": scope.jurisdiction,
        "document_class": scope.document_class,
        "version": scope.version,
        "active": True,
        "synced_at": synced_at,
    }

def _normalize_count_row(row: Mapping[str, object]) -> dict[str, object]:
    jurisdiction = row.get("jurisdiction")
    document_class = row.get("document_class")
    provision_count = row.get("provision_count")
    if jurisdiction is None or document_class is None or provision_count is None:
        raise RuntimeError("Supabase provision-count row is missing required fields")
    normalized: dict[str, object] = {
        "jurisdiction": str(jurisdiction),
        "document_class": str(document_class),
        "provision_count": _count_value(provision_count),
    }
    for key in ("body_count", "top_level_count", "rulespec_count"):
        value = row.get(key)
        if value is not None:
            normalized[key] = _count_value(value)
    if row.get("refreshed_at") is not None:
        normalized["refreshed_at"] = str(row["refreshed_at"])
    return normalized


def _count_value(value: object) -> int:
    if isinstance(value, bool):
        raise RuntimeError("Supabase count value must be numeric")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise RuntimeError("Supabase count value must be numeric")


def resolve_service_key(
    supabase_url: str,
    *,
    service_key: str | None = None,
    environ: Mapping[str, str] = os.environ,
    service_key_env: str = DEFAULT_SERVICE_KEY_ENV,
    access_token_env: str = DEFAULT_ACCESS_TOKEN_ENV,
) -> str:
    """Resolve the Supabase service role key without persisting credentials."""
    if service_key:
        return service_key
    env_service_key = environ.get(service_key_env)
    if env_service_key:
        return env_service_key
    access_token = environ.get(access_token_env)
    if not access_token:
        raise RuntimeError(
            f"{service_key_env} or {access_token_env} env var required for Supabase load"
        )

    project_ref = _project_ref_from_url(supabase_url)
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{project_ref}/api-keys",
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        keys = json.loads(resp.read())
    for entry in keys:
        if entry.get("name") == "service_role" and entry.get("api_key"):
            return str(entry["api_key"])
    raise RuntimeError("service_role key not found")


def load_provisions_to_supabase(
    records: Iterable[ProvisionRecord],
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
    chunk_size: int = 500,
    refresh: bool = True,
    dry_run: bool = False,
    allow_refresh_failure: bool = False,
    preserve_existing_ids: bool = False,
    synthesize_missing_parents: bool = False,
    skip_superseded: bool = False,
    progress_stream: TextIO | None = None,
    auto_register_scopes: bool = True,
    auto_publish: bool = True,
    release_name: str = "current",
) -> SupabaseLoadReport:
    """Upsert normalized provision records into `corpus.provisions`.

    By default, also ensures a row in ``corpus.release_scopes`` exists for
    each distinct ``(jurisdiction, document_class, version)`` triple in the
    loaded records, with ``active=True`` so the data is immediately visible
    via ``corpus.current_provisions``. This eliminates the silent-invisibility
    bug class where data was loaded but invisible because nobody added a
    matching release row.

    Pass ``auto_publish=False`` to stage the load (rows created but
    invisible — flip later via ``axiom-corpus-ingest publish``). Pass
    ``auto_register_scopes=False`` to skip release_scopes management
    entirely (legacy behavior; not recommended).
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    existing_id_count = 0
    synthesized_parents = 0
    superseded_skipped = 0
    superseded_scope_keys: set[tuple[str, str, str]] = set()
    records_iter: Iterable[ProvisionRecord] = records
    total_records: int | None = None
    # Any of these needs the current DB state (id + version) for the records'
    # citation paths *and* the parents they reference, so the load can upsert in
    # place (idempotent against UNIQUE(citation_path)), synthesize absent
    # containers, and never downgrade an already-newer row.
    heal = preserve_existing_ids or synthesize_missing_parents or skip_superseded
    if heal and not dry_run:
        materialized_records = tuple(records)
        total_records = len(materialized_records)
        lookup_paths: set[str] = set()
        for record in materialized_records:
            lookup_paths.add(record.citation_path)
            if record.parent_citation_path:
                lookup_paths.add(record.parent_citation_path)
        existing_rows = fetch_existing_provision_rows(
            lookup_paths,
            service_key=service_key,
            rest_url=_rest_url(supabase_url),
            chunk_size=100,
        )
        existing_ids = {
            path: str(entry["id"])
            for path, entry in existing_rows.items()
            if entry.get("id")
        }
        existing_id_count = len(existing_ids)

        kept: list[ProvisionRecord] = []
        for record in materialized_records:
            if skip_superseded:
                live = existing_rows.get(record.citation_path)
                if live is not None:
                    live_prefix = _version_date_prefix(live.get("version"))
                    this_prefix = _version_date_prefix(record.version)
                    if (
                        live_prefix is not None
                        and this_prefix is not None
                        and live_prefix > this_prefix
                    ):
                        superseded_skipped += 1
                        continue
            kept.append(record)

        # A version whose every row is superseded loads nothing. Record it as an
        # inactive release scope (a tombstone) so it reads as a deliberately
        # not-active predecessor (drift) rather than never-published — otherwise
        # the staleness guard would flag a version we are correctly refusing to
        # downgrade, forever.
        if skip_superseded and auto_register_scopes:
            def _scope_key(rec: ProvisionRecord) -> tuple[str, str, str] | None:
                v = _normalize_version(rec.version)
                return (
                    (rec.jurisdiction, _release_document_class(rec.document_class), v)
                    if v is not None
                    else None
                )

            all_scopes = {k for r in materialized_records if (k := _scope_key(r))}
            kept_scopes = {k for r in kept if (k := _scope_key(r))}
            superseded_scope_keys = all_scopes - kept_scopes

        prepared: list[ProvisionRecord] = []
        if synthesize_missing_parents:
            ancestors = synthesize_missing_ancestor_records(
                kept, known_paths=set(existing_ids)
            )
            synthesized_parents = len(ancestors)
            prepared.extend(ancestors)
            if progress_stream is not None:
                for anc in ancestors:
                    print(
                        f"synthesized missing container: {anc.citation_path}",
                        file=progress_stream,
                        flush=True,
                    )
        for record in kept:
            prepared.append(
                _record_with_existing_ids(record, existing_ids)
                if preserve_existing_ids
                else record
            )

        if progress_stream is not None:
            extra = ""
            if synthesized_parents:
                extra += f"; synthesized {synthesized_parents} missing container(s)"
            if superseded_skipped:
                extra += f"; skipped {superseded_skipped} superseded row(s)"
            print(
                f"resolved {existing_id_count} existing Supabase IDs "
                f"for {total_records} provisions{extra}",
                file=progress_stream,
                flush=True,
            )
        records_iter = prepared

    release_scope_keys: set[tuple[str, str, str]] = set()

    def _capture_release_scope_keys(
        source: Iterable[ProvisionRecord],
    ) -> Iterator[ProvisionRecord]:
        for record in source:
            version = _normalize_version(record.version)
            if auto_register_scopes and version is None:
                raise ValueError(
                    "ProvisionRecord.version is required when auto-registering "
                    "Supabase release scopes; pass --no-auto-register only for "
                    "explicit legacy/migration loads."
                )
            if version is not None:
                release_scope_keys.add(
                    (
                        record.jurisdiction,
                        _release_document_class(record.document_class),
                        version,
                    )
                )
            yield record

    records_iter = _capture_release_scope_keys(records_iter)

    rows_loaded = 0
    chunk_count = 0
    rest_url = _rest_url(supabase_url)
    row_iter = iter_supabase_rows(records_iter, versioned_ids=not preserve_existing_ids)
    for chunk in _chunked(row_iter, chunk_size):
        chunk_count += 1
        if not dry_run:
            upsert_supabase_rows(chunk, service_key=service_key, rest_url=rest_url)
        rows_loaded += len(chunk)
        if progress_stream is not None and (chunk_count == 1 or chunk_count % 10 == 0):
            total_text = f"/{total_records}" if total_records is not None else ""
            print(
                f"processed Supabase chunk {chunk_count} ({rows_loaded}{total_text} rows)",
                file=progress_stream,
                flush=True,
            )

    # Auto-register release_scopes rows after the provisions upsert succeeds.
    auto_registered: tuple[dict[str, object], ...] = ()
    if auto_register_scopes and not dry_run and release_scope_keys:
        auto_registered = ensure_release_scopes_for_loaded_data(
            release_scope_keys,
            release_name=release_name,
            active=auto_publish,
            service_key=service_key,
            rest_url=rest_url,
        )
        if progress_stream is not None:
            for row in auto_registered:
                state = "published" if row.get("active") is True else "staged (unpublished)"
                print(
                    f"release scope ready: {row['jurisdiction']}/"
                    f"{row['document_class']} v{row['version']} → {state}",
                    file=progress_stream,
                    flush=True,
                )

    # Tombstone wholly-superseded versions as inactive scopes (never active, so
    # never in current_provisions). Only versions with no active row of their
    # own — a version can legitimately have both superseded and surviving rows.
    if auto_register_scopes and not dry_run and superseded_scope_keys:
        tombstone_keys = superseded_scope_keys - release_scope_keys
        if tombstone_keys:
            ensure_release_scopes_for_loaded_data(
                tombstone_keys,
                release_name=release_name,
                active=False,
                service_key=service_key,
                rest_url=rest_url,
            )
            if progress_stream is not None:
                for jur, dc, ver in sorted(tombstone_keys):
                    print(
                        f"release scope tombstoned (superseded, inactive): "
                        f"{jur}/{dc} v{ver}",
                        file=progress_stream,
                        flush=True,
                    )

    refreshed = False
    refresh_error = None
    if refresh and not dry_run:
        try:
            refresh_corpus_analytics(service_key=service_key, rest_url=rest_url)
            refreshed = True
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            refresh_error = str(exc)
            if not allow_refresh_failure:
                raise RuntimeError(f"corpus analytics refresh failed: {exc}") from exc

    return SupabaseLoadReport(
        rows_total=rows_loaded,
        rows_loaded=0 if dry_run else rows_loaded,
        chunk_count=chunk_count,
        dry_run=dry_run,
        existing_id_count=existing_id_count,
        refreshed=refreshed,
        refresh_error=refresh_error,
        auto_registered_scopes=auto_registered,
        synthesized_parents=synthesized_parents,
        superseded_skipped=superseded_skipped,
    )


def delete_supabase_provisions_scope(
    *,
    jurisdiction: str,
    document_class: str,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
    delete_chunk_size: int = 100,
    fetch_page_size: int = 1_000,
    dry_run: bool = False,
    progress_stream: TextIO | None = None,
    versions: Sequence[str] | None = None,
) -> SupabaseDeleteReport:
    """Delete `corpus.provisions` rows for one jurisdiction/document class.

    When ``versions`` is given, deletion is limited to rows carrying one
    of those versions — the release-scope sense of "scope". Without it
    every row in the jurisdiction/document class goes, which once wiped
    20 sibling scopes when a per-scope reload loop passed
    ``--replace-scope``.
    """
    if delete_chunk_size <= 0:
        raise ValueError("delete_chunk_size must be positive")
    if fetch_page_size <= 0:
        raise ValueError("fetch_page_size must be positive")
    if dry_run:
        return SupabaseDeleteReport(
            intended_rows_deleted=0,
            delete_chunk_count=0,
            dry_run=True,
        )

    rest_url = _rest_url(supabase_url)
    provision_ids = fetch_provision_ids_for_scope(
        jurisdiction=jurisdiction,
        versions=versions,
        document_class=document_class,
        service_key=service_key,
        rest_url=rest_url,
        page_size=fetch_page_size,
    )
    intended_rows_deleted = 0
    delete_chunk_count = 0
    for chunk in _chunked_values(provision_ids, delete_chunk_size):
        delete_chunk_count += 1
        delete_supabase_provision_ids(chunk, service_key=service_key, rest_url=rest_url)
        intended_rows_deleted += len(chunk)
        if progress_stream is not None and (
            delete_chunk_count == 1 or delete_chunk_count % 10 == 0
        ):
            print(
                f"deleted Supabase chunk {delete_chunk_count} "
                f"({intended_rows_deleted}/{len(provision_ids)} scoped rows)",
                file=progress_stream,
                flush=True,
            )
    return SupabaseDeleteReport(
        intended_rows_deleted=intended_rows_deleted,
        delete_chunk_count=delete_chunk_count,
    )


def fetch_existing_provision_rows(
    citation_paths: Iterable[str],
    *,
    service_key: str,
    rest_url: str,
    chunk_size: int = 100,
) -> dict[str, dict[str, str | None]]:
    """Fetch current provision ``id`` and ``version`` keyed by citation path.

    Used to keep loads idempotent against the ``UNIQUE(citation_path)`` table
    constraint: a row's stable id lets a new release version upsert in place
    (rather than insert a colliding row), and its live version lets the loader
    skip a candidate that would downgrade an already-newer row.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    existing: dict[str, dict[str, str | None]] = {}
    unique_paths = sorted(set(citation_paths))
    for chunk in _chunked_values(unique_paths, chunk_size):
        if not chunk:
            continue
        filter_value = "in.(" + ",".join(_postgrest_in_value(value) for value in chunk) + ")"
        query = urllib.parse.urlencode(
            {
                "select": "id,citation_path,version",
                "citation_path": filter_value,
            }
        )
        req = urllib.request.Request(
            f"{rest_url}/provisions?{query}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Accept": "application/json",
                "Accept-Profile": "corpus",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            rows = json.loads(resp.read())
        if not isinstance(rows, list):
            raise RuntimeError("unexpected Supabase existing-id response")
        for row in rows:
            if not isinstance(row, dict):
                continue
            citation_path = row.get("citation_path")
            provision_id = row.get("id")
            if citation_path and provision_id:
                version = row.get("version")
                existing[str(citation_path)] = {
                    "id": str(provision_id),
                    "version": str(version) if version is not None else None,
                }
    return existing


def fetch_existing_provision_ids(
    citation_paths: Iterable[str],
    *,
    service_key: str,
    rest_url: str,
    chunk_size: int = 100,
) -> dict[str, str]:
    """Fetch current provision IDs keyed by citation path for in-place migrations."""
    rows = fetch_existing_provision_rows(
        citation_paths,
        service_key=service_key,
        rest_url=rest_url,
        chunk_size=chunk_size,
    )
    return {path: str(entry["id"]) for path, entry in rows.items() if entry.get("id")}


def fetch_provision_ids_for_scope(
    *,
    jurisdiction: str,
    document_class: str,
    service_key: str,
    rest_url: str,
    page_size: int = 1_000,
    versions: Sequence[str] | None = None,
) -> tuple[str, ...]:
    scoped_rows: list[tuple[str, int]] = []
    last_id: str | None = None
    while True:
        query_params = {
            "select": "id,level",
            "jurisdiction": f"eq.{jurisdiction}",
            "doc_type": f"eq.{document_class}",
            "order": "id.asc",
            "limit": str(page_size),
        }
        if versions:
            query_params["version"] = (
                "in.(" + ",".join(_postgrest_in_value(value) for value in versions) + ")"
            )
        if last_id is not None:
            query_params["id"] = f"gt.{last_id}"
        query = urllib.parse.urlencode(query_params)
        req = urllib.request.Request(
            f"{rest_url}/provisions?{query}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Accept": "application/json",
                "Accept-Profile": "corpus",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            rows = json.loads(resp.read())
        if not isinstance(rows, list):
            raise RuntimeError("unexpected Supabase scope-id response")
        page_rows = tuple(
            (
                str(row["id"]),
                int(row.get("level") or 0),
            )
            for row in rows
            if isinstance(row, dict) and row.get("id") is not None
        )
        scoped_rows.extend(page_rows)
        if len(page_rows) < page_size:
            break
        last_id = page_rows[-1][0]
    scoped_rows.sort(key=lambda row: (-row[1], row[0]))
    return tuple(row[0] for row in scoped_rows)


def delete_supabase_provision_ids(
    provision_ids: list[str],
    *,
    service_key: str,
    rest_url: str,
) -> None:
    if not provision_ids:
        return
    query = urllib.parse.urlencode(
        {"id": "in.(" + ",".join(_postgrest_in_value(value) for value in provision_ids) + ")"}
    )
    req = urllib.request.Request(
        f"{rest_url}/provisions?{query}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept-Profile": "corpus",
            "Content-Profile": "corpus",
            "Prefer": "return=minimal",
            "User-Agent": USER_AGENT,
        },
        method="DELETE",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        resp.read()


def _record_with_existing_ids(
    record: ProvisionRecord,
    existing_ids: Mapping[str, str],
) -> ProvisionRecord:
    provision_id = existing_ids.get(record.citation_path, record.id)
    parent_id = record.parent_id
    if record.parent_citation_path and record.parent_citation_path in existing_ids:
        parent_id = existing_ids[record.parent_citation_path]
    if provision_id == record.id and parent_id == record.parent_id:
        return record
    return replace(record, id=provision_id, parent_id=parent_id)


def synthesize_missing_ancestor_records(
    records: Sequence[ProvisionRecord],
    *,
    known_paths: set[str],
) -> list[ProvisionRecord]:
    """Synthesize container rows for parents referenced but defined nowhere.

    Some ingests emit article-level (leaf) provisions without the instrument
    container they hang off (e.g. every ``.../1978070303/article/N`` points at
    ``be/statute/loi/1978/07/03/1978070303`` but no record defines it), so the
    upsert fails the FK ``parent_id -> provisions(id)`` with 23503. For each
    referenced ``parent_citation_path`` that is neither among ``records`` nor in
    ``known_paths`` (already live in the DB), synthesize a minimal structural
    container: the citation identity only, no captured text, wired so its id
    equals the child's ``parent_id`` in both id modes (version-derived ids
    recompute identically from the shared path+version; preserved ids reuse the
    copied uuid). The container is a root — we only know the child's parent, not
    the parent's own ancestor — which matches how self-contained scopes root
    their top instrument node.
    """
    present = set(known_paths)
    for record in records:
        present.add(record.citation_path)
    synthesized: dict[str, ProvisionRecord] = {}
    for record in records:
        parent_path = record.parent_citation_path
        if not parent_path or parent_path in present or parent_path in synthesized:
            continue
        child_level = record.level
        container_level = max(child_level - 1, 1) if isinstance(child_level, int) else None
        synthesized[parent_path] = ProvisionRecord(
            jurisdiction=record.jurisdiction,
            document_class=record.document_class,
            citation_path=parent_path,
            id=record.parent_id,
            version=record.version,
            level=container_level,
            ordinal=0,
            parent_citation_path=None,
            parent_id=None,
            language=record.language,
            identifiers={"corpus:synthesized_container": "missing-parent-backfill"},
        )
    # Deterministic order (parents before their own would-be children) keeps the
    # prepended block stable and readable in progress output.
    return [synthesized[path] for path in sorted(synthesized)]


def upsert_supabase_rows(
    rows: list[dict[str, object]],
    *,
    service_key: str,
    rest_url: str,
) -> None:
    if not rows:
        return
    req = urllib.request.Request(
        f"{rest_url}/provisions?on_conflict=id",
        data=json.dumps(rows).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"upsert failed {exc.code}: {body}") from exc


def set_release_scope_active(
    *,
    jurisdiction: str,
    document_class: str,
    active: bool,
    release_name: str = "current",
    version: str | None = None,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
    refresh: bool = True,
) -> dict[str, object]:
    """Flip the ``active`` flag on a single release_scopes row.

    If ``version`` is None, picks the most recent row for (release_name,
    jurisdiction, document_class) by ``synced_at`` descending. Raises if no
    matching row exists.

    Returns the affected row's contents as a dict, plus the refresh result.
    """
    rest_url = _rest_url(supabase_url)
    auth = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept-Profile": "corpus",
        "User-Agent": USER_AGENT,
    }

    if version is None:
        # Find the most recent row for this (release_name, jurisdiction, doc_class).
        query = urllib.parse.urlencode({
            "release_name": f"eq.{release_name}",
            "jurisdiction": f"eq.{jurisdiction}",
            "document_class": f"eq.{document_class}",
            "select": "version,synced_at,active",
            "order": "synced_at.desc",
            "limit": 1,
        })
        req = urllib.request.Request(
            f"{rest_url}/release_scopes?{query}",
            headers=auth,
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read())
        if not rows:
            raise RuntimeError(
                f"no release_scopes row found for "
                f"({release_name}, {jurisdiction}, {document_class}); "
                f"load data first or pass --version to disambiguate"
            )
        version = rows[0]["version"]

    # PATCH the target row.
    query = urllib.parse.urlencode({
        "release_name": f"eq.{release_name}",
        "jurisdiction": f"eq.{jurisdiction}",
        "document_class": f"eq.{document_class}",
        "version": f"eq.{version}",
    })
    req = urllib.request.Request(
        f"{rest_url}/release_scopes?{query}",
        data=json.dumps({"active": active}).encode(),
        method="PATCH",
        headers={
            **auth,
            "Content-Type": "application/json",
            "Content-Profile": "corpus",
            "Prefer": "return=representation",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    if not result:
        raise RuntimeError(
            f"PATCH affected zero rows: ({release_name}, {jurisdiction}, "
            f"{document_class}, {version})"
        )

    refreshed = False
    refresh_error: str | None = None
    if refresh:
        try:
            refresh_corpus_analytics(service_key=service_key, rest_url=rest_url)
            refreshed = True
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            refresh_error = str(exc)

    return {
        "scope": result[0],
        "refreshed": refreshed,
        "refresh_error": refresh_error,
    }


def list_single_active_release_scopes(
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
) -> tuple[dict[str, str], ...]:
    """List (jurisdiction, document_class, version) for scopes with exactly one
    active version. These are the scopes that can be unambiguously backfilled.

    Multi-active scopes (e.g., federal guidance scopes where multiple
    versions are simultaneously active) are excluded — their existing
    NULL-version rows cannot be reverse-engineered to one specific
    version without external context.
    """
    rest_url = _rest_url(supabase_url)
    req = urllib.request.Request(
        f"{rest_url}/rpc/list_single_active_release_scopes",
        data=b"{}",
        method="POST",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list):
        return ()
    return tuple(
        {
            "jurisdiction": str(row.get("jurisdiction") or ""),
            "document_class": str(row.get("document_class") or ""),
            "version": str(row.get("version") or ""),
        }
        for row in rows
        if isinstance(row, dict)
    )


def backfill_version_chunk(
    *,
    jurisdiction: str,
    document_class: str,
    version: str,
    table_name: str,
    chunk_size: int = 50000,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
    max_retries: int = 6,
    base_backoff_seconds: float = 1.0,
    progress_stream: TextIO | None = None,
) -> int:
    """Call corpus.backfill_version_chunk RPC. Returns rows updated.

    Caller is expected to loop until this returns 0. The RPC updates at
    most ``chunk_size`` rows per call, each call within its own
    statement_timeout window.

    Transient server errors (HTTP 5xx and network timeouts) are retried
    with exponential backoff up to ``max_retries`` times. PostgREST's
    statement_timeout error (SQLSTATE 57014) surfaces as HTTP 500; if
    a chunk size consistently triggers that, lower ``chunk_size``
    rather than retrying — but a one-off transient 500 is common and
    recoverable.
    """
    if table_name not in {"provisions", "navigation_nodes"}:
        raise ValueError(f"table_name must be 'provisions' or 'navigation_nodes', got {table_name!r}")
    rest_url = _rest_url(supabase_url)
    payload = {
        "p_jurisdiction": jurisdiction,
        "p_document_class": document_class,
        "p_version": version,
        "p_table_name": table_name,
        "p_chunk_size": chunk_size,
    }

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            f"{rest_url}/rpc/backfill_version_chunk",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Content-Profile": "corpus",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read())
            if isinstance(result, int):
                return result
            if isinstance(result, str):
                return int(result)
            raise RuntimeError(f"unexpected backfill_version_chunk response: {result!r}")
        except urllib.error.HTTPError as exc:
            # 4xx is a real error (bad input, permissions); don't retry.
            if 400 <= exc.code < 500:
                raise
            last_error = exc
            body = exc.read()[:300].decode("utf-8", errors="replace")
            if progress_stream is not None:
                print(
                    f"    transient HTTP {exc.code} on attempt {attempt+1}/"
                    f"{max_retries+1}: {body}",
                    file=progress_stream,
                    flush=True,
                )
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if progress_stream is not None:
                print(
                    f"    transient {type(exc).__name__} on attempt {attempt+1}/"
                    f"{max_retries+1}: {exc}",
                    file=progress_stream,
                    flush=True,
                )

        if attempt < max_retries:
            sleep_for = base_backoff_seconds * (2 ** attempt)
            time.sleep(sleep_for)

    raise RuntimeError(
        f"backfill_version_chunk failed after {max_retries+1} attempts: {last_error}"
    )


def list_release_scopes(
    *,
    release_name: str = "current",
    active: bool | None = None,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
) -> tuple[dict[str, object], ...]:
    """List release_scopes rows, optionally filtered by active state."""
    rest_url = _rest_url(supabase_url)
    params: dict[str, str] = {
        "release_name": f"eq.{release_name}",
        "select": "release_name,jurisdiction,document_class,version,active,synced_at",
        "order": "jurisdiction.asc,document_class.asc,synced_at.desc",
    }
    if active is not None:
        params["active"] = f"is.{str(active).lower()}"

    req = urllib.request.Request(
        f"{rest_url}/release_scopes?{urllib.parse.urlencode(params)}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list):
        return ()
    return tuple(row for row in rows if isinstance(row, dict))


def ensure_release_scopes_for_loaded_data(
    release_scope_keys: Iterable[tuple[str, str, str]],
    *,
    release_name: str = "current",
    active: bool = True,
    service_key: str,
    rest_url: str,
) -> tuple[dict[str, object], ...]:
    """Idempotently ensure a release_scopes row exists for each loaded scope.

    Uses ``Prefer: resolution=ignore-duplicates``: if a row already exists
    for ``(release_name, jurisdiction, document_class, version)``, this
    function leaves it alone — including its ``active`` flag. State
    changes always require an explicit ``axiom-corpus-ingest publish`` /
    ``unpublish`` invocation, never a re-load.

    This protects against the surprise that a re-load with ``--stage``
    would silently demote a previously-published scope (or that a re-load
    without ``--stage`` would silently undo an explicit unpublish).
    Re-loads of existing scopes become no-ops at the release_scopes layer.

    Default ``active=True`` for newly-inserted rows matches the design
    choice that loading new data should publish it by default. Callers
    wanting to stage explicitly pass ``active=False``.
    """
    keys = tuple(sorted(set(release_scope_keys)))
    if not keys:
        return ()

    synced_at = datetime.now(UTC).isoformat()
    rows = [
        {
            "release_name": release_name,
            "jurisdiction": jurisdiction,
            "document_class": document_class,
            "version": version,
            "active": active,
            "synced_at": synced_at,
        }
        for jurisdiction, document_class, version in keys
    ]
    insert_release_scope_rows_ignore_duplicates(
        rows, service_key=service_key, rest_url=rest_url
    )
    return tuple(
        fetch_release_scope_row(
            release_name=release_name,
            jurisdiction=jurisdiction,
            document_class=document_class,
            version=version,
            service_key=service_key,
            rest_url=rest_url,
        )
        for jurisdiction, document_class, version in keys
    )


def fetch_release_scope_row(
    *,
    release_name: str,
    jurisdiction: str,
    document_class: str,
    version: str,
    service_key: str,
    rest_url: str,
) -> dict[str, object]:
    """Fetch the persisted release_scopes row after an ignore-duplicates insert."""
    query = urllib.parse.urlencode(
        {
            "release_name": f"eq.{release_name}",
            "jurisdiction": f"eq.{jurisdiction}",
            "document_class": f"eq.{document_class}",
            "version": f"eq.{version}",
            "select": "release_name,jurisdiction,document_class,version,active,synced_at",
            "limit": "1",
        }
    )
    req = urllib.request.Request(
        f"{rest_url}/release_scopes?{query}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Accept-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise RuntimeError(
            "release-scope insert/readback failed for "
            f"({release_name}, {jurisdiction}, {document_class}, {version})"
        )
    return dict(rows[0])


def insert_release_scope_rows_ignore_duplicates(
    rows: list[dict[str, object]],
    *,
    service_key: str,
    rest_url: str,
) -> None:
    """Insert release_scopes rows; skip any row that conflicts on the unique
    key (release_name, jurisdiction, document_class, version).

    Sister function to ``upsert_release_scope_rows`` which uses
    ``resolution=merge-duplicates``. The auto-register-on-load flow uses
    this ignore-duplicates variant so that re-loads don't silently flip
    the ``active`` flag on existing rows.
    """
    if not rows:
        return
    req = urllib.request.Request(
        (
            f"{rest_url}/release_scopes?"
            "on_conflict=release_name,jurisdiction,document_class,version"
        ),
        data=json.dumps(rows).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"release-scope ignore-duplicates insert failed {exc.code}: {body}"
        ) from exc


def deactivate_release_scope_rows(
    *,
    release_name: str,
    service_key: str,
    rest_url: str,
) -> None:
    query = urllib.parse.urlencode(
        {
            "release_name": f"eq.{release_name}",
            "active": "eq.true",
        }
    )
    req = urllib.request.Request(
        f"{rest_url}/release_scopes?{query}",
        data=json.dumps({"active": False}).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        resp.read()


def upsert_release_scope_rows(
    rows: list[dict[str, object]],
    *,
    service_key: str,
    rest_url: str,
) -> None:
    if not rows:
        return
    req = urllib.request.Request(
        (
            f"{rest_url}/release_scopes?"
            "on_conflict=release_name,jurisdiction,document_class,version"
        ),
        data=json.dumps(rows).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"release-scope upsert failed {exc.code}: {body}") from exc


def refresh_corpus_analytics(*, service_key: str, rest_url: str) -> None:
    """Refresh corpus analytics after loading provision rows."""
    _post_refresh_rpc(
        service_key=service_key, rest_url=rest_url, rpc_name="refresh_corpus_analytics"
    )


def _post_refresh_rpc(*, service_key: str, rest_url: str, rpc_name: str) -> None:
    req = urllib.request.Request(
        f"{rest_url}/rpc/{rpc_name}",
        data=b"{}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        resp.read()


def _chunked(
    rows: Iterable[dict[str, object]],
    size: int,
) -> Iterator[list[dict[str, object]]]:
    chunk: list[dict[str, object]] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _chunked_values(values: Iterable[str], size: int) -> Iterator[list[str]]:
    chunk: list[str] = []
    for value in values:
        chunk.append(value)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _postgrest_in_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _rest_url(supabase_url: str) -> str:
    return f"{supabase_url.rstrip('/')}/rest/v1"


def _project_ref_from_url(supabase_url: str) -> str:
    parsed = urllib.parse.urlparse(supabase_url)
    host = parsed.netloc or parsed.path
    if not host:
        raise ValueError(f"invalid Supabase URL: {supabase_url}")
    return host.split(".", 1)[0]
