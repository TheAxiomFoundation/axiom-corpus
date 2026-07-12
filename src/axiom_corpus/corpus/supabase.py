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
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TextIO
from uuid import NAMESPACE_URL, UUID, uuid5

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.projection_digest import (
    ProjectionDigestError,
    encode_identifiers_projection,
)
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope, validate_release_name
from axiom_corpus.release.manifest import verify_release_object

DEFAULT_AXIOM_SUPABASE_URL = "https://swocpijqqahhuwtuahwc.supabase.co"
DEFAULT_SERVICE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
DEFAULT_ACCESS_TOKEN_ENV = "SUPABASE_ACCESS_TOKEN"
USER_AGENT = "axiom-corpus/0.1"
POSTGRES_INT32_MIN = -(2**31)
POSTGRES_INT32_MAX = 2**31 - 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

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


# Staged provision identity is derived state: both ids are deterministic
# functions of (citation_path, version) unless an ingest carried explicit ids.
# Every other projected column is release content. The split decides what an
# idempotent reload may converge (identity) versus what it must never touch
# silently (content).
PROVISION_IDENTITY_COLUMNS = ("id", "parent_id")
PROVISION_CONTENT_COLUMNS = tuple(
    column for column in SUPABASE_PROVISIONS_COLUMNS if column not in PROVISION_IDENTITY_COLUMNS
)

_STAGING_CONFLICT_PREVIEW_LIMIT = 20


class ProvisionStagingConflictError(RuntimeError):
    """Staged `corpus.provisions` state conflicts with the rows being loaded.

    Raised before any write. A conflict means the database already holds
    different content under an immutable ``(citation_path, version)`` key,
    holds staged rows the incoming load does not describe, or holds rows whose
    replacement would cascade-delete state outside the loaded rows. None of
    these may be resolved implicitly: overwriting could launder drifted source
    text into a later signed release, and skipping could sign content that is
    not what the local artifacts say. Inspect ``conflicts``, then either fix
    the corpus artifacts or explicitly clear the stale staged scope
    (``axiom-corpus-ingest load-supabase --replace-scope``).
    """

    def __init__(self, conflicts: Sequence[Mapping[str, object]]) -> None:
        self.conflicts = tuple(dict(conflict) for conflict in conflicts)
        preview = json.dumps(list(self.conflicts[:_STAGING_CONFLICT_PREVIEW_LIMIT]), sort_keys=True)
        overflow = len(self.conflicts) - _STAGING_CONFLICT_PREVIEW_LIMIT
        suffix = f" (+{overflow} more)" if overflow > 0 else ""
        super().__init__(
            f"{len(self.conflicts)} provision staging conflict(s); "
            f"no rows were written: {preview}{suffix}"
        )


@dataclass(frozen=True)
class SupabaseLoadReport:
    rows_total: int
    rows_loaded: int
    chunk_count: int
    dry_run: bool = False
    rows_inserted: int = 0
    rows_replaced: int = 0
    rows_already_staged: int = 0

    def to_mapping(self) -> dict[str, object]:
        return {
            "rows_total": self.rows_total,
            "rows_loaded": self.rows_loaded,
            "chunk_count": self.chunk_count,
            "dry_run": self.dry_run,
            "rows_inserted": self.rows_inserted,
            "rows_replaced": self.rows_replaced,
            "rows_already_staged": self.rows_already_staged,
        }


@dataclass(frozen=True)
class StagedScopeEvidence:
    provision_rows: int
    navigation_rows: int
    provision_projection_sha256: str
    navigation_projection_sha256: str


@dataclass(frozen=True)
class ReleasedScopeObject:
    scope_key: tuple[str, str, str]
    release_name: str
    content_sha256: str
    release_object: Mapping[str, object]


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

    ``corpus.current_provisions`` follows the singleton production pointer to
    one immutable named release and joins that release's exact version scopes.
    A navigation scope without matching provision rows produces
    ``current_provision_count == 0`` here.
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
            "missing_current_provisions": [f.to_mapping() for f in self.missing_current_provisions],
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
    current_keys = {(row["jurisdiction"], row["document_class"]) for row in current_counts}

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
        missing_current_provisions=tuple(
            sorted(missing, key=lambda f: (f.jurisdiction, f.document_class))
        ),
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
        out.append(
            {
                "jurisdiction": str(row.get("jurisdiction") or ""),
                "document_class": str(row.get("document_class") or "unknown"),
                "count": int(row.get("node_count") or 0),
            }
        )
    return tuple(out)


def _fetch_current_provision_counts(
    rest_url: str, headers: dict[str, str]
) -> tuple[dict[str, object], ...]:
    query = urllib.parse.urlencode(
        {
            "select": "jurisdiction,document_class,provision_count",
        }
    )
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

    Bare ISO dates are already canonical. Valid ISO timestamps and values whose
    leading ``YYYY-MM-DD`` is a real calendar date are reduced to that exact
    date before the REST upsert. This makes the signed Python projection match
    the stored PostgreSQL DATE text instead of relying on an implicit server
    cast. Anything else non-empty becomes ``None``. The second tuple element is
    the original string when a coercion happened (for provenance), else
    ``None``.
    """
    if value is None or not isinstance(value, str):
        return value, None
    raw = value.strip()
    if not raw:
        return None, None
    # Already a value Postgres accepts for a date column (bare date or a full
    # ISO timestamp it will cast down to the date) — leave untouched.
    try:
        canonical_date = date.fromisoformat(raw).isoformat()
        return canonical_date, None
    except ValueError:
        pass
    try:
        canonical_date = datetime.fromisoformat(raw).date().isoformat()
        return canonical_date, raw
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


def _required_uuid(value: object, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"provision {field} must be a UUID: {value!r}") from exc


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
    explicit_provision_id = _required_uuid(record.id, field="id") if record.id is not None else None
    if (
        versioned_ids
        and version is not None
        and (explicit_provision_id is None or explicit_provision_id == legacy_provision_id)
    ):
        provision_id = deterministic_provision_id(record.citation_path, version)
    else:
        provision_id = explicit_provision_id or legacy_provision_id
    parent_id = (
        _required_uuid(record.parent_id, field="parent_id")
        if record.parent_id is not None
        else None
    )
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
    # The int4 ordinal shim indexes within each release scope, not across the
    # whole iterable, so a multi-scope load projects the exact same rows as
    # the per-scope signed evidence digests in release content.
    scope_positions: dict[tuple[str, str, str], int] = {}
    for record in records:
        row = provision_to_supabase_row(record, versioned_ids=versioned_ids)
        scope_key = (
            str(row.get("jurisdiction") or ""),
            str(row.get("doc_type") or ""),
            str(row.get("version") or ""),
        )
        index = scope_positions.get(scope_key, 0)
        scope_positions[scope_key] = index + 1
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
    present behind the active named-release pointer.
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


def fetch_staged_release_scope_evidence(
    release: ReleaseManifest,
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
) -> dict[tuple[str, str, str], StagedScopeEvidence]:
    """Fetch exact counts and projection digests for every staged scope.

    There is intentionally no materialized-view or paged-client fallback. The
    publication boundary requires the dedicated evidence RPC; absence or
    failure is fatal before signing.
    """
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
        f"{_rest_url(supabase_url)}/rpc/get_staged_release_scope_evidence",
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
    with urllib.request.urlopen(req, timeout=600) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list):
        raise RuntimeError("unexpected staged release-evidence response")
    evidence: dict[tuple[str, str, str], StagedScopeEvidence] = {}
    expected_fields = {
        "jurisdiction",
        "document_class",
        "version",
        "provision_count",
        "navigation_count",
        "provision_projection_sha256",
        "navigation_projection_sha256",
    }
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise RuntimeError("staged release-evidence response contains a malformed row")
        key = (
            str(row.get("jurisdiction") or ""),
            str(row.get("document_class") or ""),
            str(row.get("version") or ""),
        )
        if not all(key) or key in evidence:
            raise RuntimeError(f"invalid staged release-evidence identity: {key!r}")
        raw_provision_count = row.get("provision_count")
        raw_navigation_count = row.get("navigation_count")
        if (
            isinstance(raw_provision_count, bool)
            or isinstance(raw_navigation_count, bool)
            or not isinstance(raw_provision_count, int | str)
            or not isinstance(raw_navigation_count, int | str)
        ):
            raise RuntimeError(f"invalid staged release row count for {key!r}")
        provision_digest = row.get("provision_projection_sha256")
        navigation_digest = row.get("navigation_projection_sha256")
        if (
            not isinstance(provision_digest, str)
            or _SHA256_RE.fullmatch(provision_digest) is None
            or not isinstance(navigation_digest, str)
            or _SHA256_RE.fullmatch(navigation_digest) is None
        ):
            raise RuntimeError(f"invalid staged release projection digest for {key!r}")
        evidence[key] = StagedScopeEvidence(
            provision_rows=int(raw_provision_count),
            navigation_rows=int(raw_navigation_count),
            provision_projection_sha256=provision_digest,
            navigation_projection_sha256=navigation_digest,
        )
    expected_keys = set(release.scope_keys)
    if set(evidence) != expected_keys:
        missing = sorted(expected_keys - set(evidence))
        extra = sorted(set(evidence) - expected_keys)
        raise RuntimeError(
            f"staged release-evidence scope mismatch; missing={missing!r}, extra={extra!r}"
        )
    return evidence


def fetch_released_scope_objects(
    release: ReleaseManifest,
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
) -> dict[tuple[str, str, str], tuple[ReleasedScopeObject, ...]]:
    """Return prior signed objects that make requested scopes immutable."""

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
        f"{_rest_url(supabase_url)}/rpc/get_released_scope_objects",
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
    with urllib.request.urlopen(req, timeout=600) as resp:
        rows = json.loads(resp.read())
    if not isinstance(rows, list):
        raise RuntimeError("unexpected released-scope response")

    expected_keys = set(release.scope_keys)
    grouped: dict[tuple[str, str, str], list[ReleasedScopeObject]] = {
        key: [] for key in release.scope_keys
    }
    seen: set[tuple[tuple[str, str, str], str]] = set()
    expected_fields = {
        "jurisdiction",
        "document_class",
        "version",
        "release_name",
        "content_sha256",
        "release_object",
    }
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise RuntimeError("released-scope response contains a malformed row")
        key = (
            str(row.get("jurisdiction") or ""),
            str(row.get("document_class") or ""),
            str(row.get("version") or ""),
        )
        if key not in expected_keys:
            raise RuntimeError(f"released-scope response contains an unknown scope: {key!r}")
        raw_name = row.get("release_name")
        try:
            release_name = validate_release_name(raw_name) if isinstance(raw_name, str) else ""
        except ValueError as exc:
            raise RuntimeError("released-scope response has an invalid release name") from exc
        if not release_name:
            raise RuntimeError("released-scope response has an invalid release name")
        content_sha256 = row.get("content_sha256")
        release_object = row.get("release_object")
        if (
            not isinstance(content_sha256, str)
            or _SHA256_RE.fullmatch(content_sha256) is None
            or not isinstance(release_object, dict)
            or release_object.get("release") != release_name
            or release_object.get("content_sha256") != content_sha256
        ):
            raise RuntimeError("released-scope response has inconsistent object identity")
        identity = (key, release_name)
        if identity in seen:
            raise RuntimeError(f"released-scope response contains a duplicate: {identity!r}")
        seen.add(identity)
        grouped[key].append(
            ReleasedScopeObject(
                scope_key=key,
                release_name=release_name,
                content_sha256=content_sha256,
                release_object=release_object,
            )
        )
    return {
        key: tuple(sorted(objects, key=lambda item: item.release_name))
        for key, objects in grouped.items()
    }


def activate_corpus_release(
    release_object: Mapping[str, object],
    *,
    access_token: str,
    public_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
) -> dict[str, object]:
    """Verify, install, and activate through the trusted management plane.

    The staging service role is deliberately unable to invoke the activation
    RPC. This wrapper verifies Ed25519 before using a separate Supabase
    Management API credential to execute the count-and-pointer transaction.
    """
    verify_release_object(release_object, public_key=public_key)
    project_ref = _project_ref_from_url(supabase_url)
    query = "SELECT corpus.activate_corpus_release($1::jsonb) AS result"
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{project_ref}/database/query",
        data=json.dumps(
            {
                "query": query,
                "parameters": [json.dumps(release_object, sort_keys=True)],
                "read_only": False,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        rows = json.loads(resp.read())
    if (
        not isinstance(rows, list)
        or len(rows) != 1
        or not isinstance(rows[0], dict)
        or set(rows[0]) != {"result"}
    ):
        raise RuntimeError(f"unexpected corpus activation query response: {rows!r}")
    result = rows[0]["result"]
    if not isinstance(result, dict) or result.get("active") is not True:
        raise RuntimeError(f"unexpected corpus activation response: {result!r}")
    if result.get("release") != release_object.get("release"):
        raise RuntimeError("activated release name does not match the requested object")
    if result.get("content_sha256") != release_object.get("content_sha256"):
        raise RuntimeError("activated release digest does not match the requested object")
    return result


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
        (str(row["jurisdiction"]), str(row["document_class"])): row for row in fallback_rows
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
    dry_run: bool = False,
    progress_stream: TextIO | None = None,
) -> SupabaseLoadReport:
    """Stage normalized, versioned provision records in ``corpus.provisions``.

    Loading never changes release membership or public visibility. Only the
    signed named-release activation RPC can move the production pointer.
    Missing parents remain hard foreign-key/data defects; publication never
    manufactures legal-corpus rows to make an invalid scope loadable.

    Staging is idempotent against verified pre-staged state. Every loaded
    scope's existing rows are fetched and compared before any write:

    - a row that is byte-identical across every projected column is left
      untouched;
    - a row whose release content matches but whose derived identity
      (``id``/``parent_id``) reflects a superseded id scheme is converged to
      the canonical identity, in place when the id survives, otherwise by
      replacing the stale row;
    - a row whose content differs under the same immutable
      ``(citation_path, version)`` key, or a staged row the load does not
      describe, raises :class:`ProvisionStagingConflictError` before anything
      is written — silent overwrites and silent skips are both integrity
      defects at this boundary.

    Replacements are planned against the ``parent_id`` ON DELETE CASCADE
    closure, so converging a stale identity can never silently delete a row
    that survives the load; any dependent row outside the loaded rows is
    reported as a conflict instead, and the dependent set is re-checked
    immediately before the deletes execute.

    Verification and writes are separate REST requests, not one transaction:
    the contract assumes one staging writer at a time. The residual races are
    narrowed (conditional single-column parent updates, the pre-delete
    dependent re-check, plain inserts that surface any constraint violation)
    and the publisher's evidence gate re-derives every in-release scope
    server-side after staging; a truly transactional staging boundary needs a
    server-side RPC.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    def _require_release_versions(
        source: Iterable[ProvisionRecord],
    ) -> Iterator[ProvisionRecord]:
        for record in source:
            version = _normalize_version(record.version)
            if version is None:
                raise ValueError(
                    "ProvisionRecord.version is required for immutable release staging"
                )
            yield record

    rows = list(iter_supabase_rows(_require_release_versions(records), versioned_ids=True))

    rows_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["citation_path"]), str(row["version"]))
        if key in rows_by_key:
            raise ValueError(
                f"load payload repeats an immutable provision key: {key[0]} @ {key[1]}"
            )
        rows_by_key[key] = row

    if dry_run:
        return SupabaseLoadReport(
            rows_total=len(rows),
            rows_loaded=0,
            chunk_count=sum(1 for _ in _chunked(iter(rows), chunk_size)),
            dry_run=True,
        )

    rest_url = _rest_url(supabase_url)
    plan = _plan_provision_staging(
        rows,
        rows_by_key=rows_by_key,
        service_key=service_key,
        rest_url=rest_url,
    )
    if plan.conflicts:
        raise ProvisionStagingConflictError(plan.conflicts)

    if progress_stream is not None and (
        plan.rows_already_staged or plan.replaced_ids or plan.in_place_updates
    ):
        print(
            f"verified staged state: {plan.rows_already_staged} rows identical, "
            f"{len(plan.replaced_ids)} stale identities replaced, "
            f"{len(plan.in_place_updates)} converged in place, "
            f"{len(plan.pending_inserts)} to insert",
            file=progress_stream,
            flush=True,
        )

    # Planning read the database without a transaction. Re-fetch the cascade
    # dependents of every id scheduled for deletion immediately before the
    # deletes: a dependent staged by a concurrent writer after planning would
    # otherwise be cascade-deleted without a trace. This narrows the race
    # window to the write phase itself; the staging boundary assumes a single
    # staging writer at a time, and the publish evidence gate re-derives
    # every in-release scope server-side after staging.
    if plan.replaced_ids:
        replaced_id_set = {row_id for row_id, _ in plan.replaced_ids}
        late_dependents = [
            dependent
            for dependent in fetch_provision_rows_with_parents(
                sorted(replaced_id_set), service_key=service_key, rest_url=rest_url
            )
            if str(dependent.get("id")) not in replaced_id_set
        ]
        if late_dependents:
            raise ProvisionStagingConflictError(
                [
                    {
                        "kind": "cascade-outside-load",
                        "citation_path": str(dependent.get("citation_path")),
                        "version": str(dependent.get("version")),
                        "staged_id": str(dependent.get("id")),
                        "staged_parent_id": str(dependent.get("parent_id")),
                    }
                    for dependent in late_dependents
                ]
            )

    # Deletes run deepest-first so an in-set parent is never removed while an
    # in-set child still exists; the closure guarantees no out-of-set child.
    for delete_chunk in _chunked_values(
        [row_id for row_id, _ in sorted(plan.replaced_ids, key=lambda item: (-item[1], item[0]))],
        100,
    ):
        delete_supabase_provision_ids(delete_chunk, service_key=service_key, rest_url=rest_url)

    rows_loaded = plan.rows_already_staged
    chunk_count = 0
    for chunk in _chunked(iter(plan.pending_inserts), chunk_size):
        chunk_count += 1
        insert_supabase_rows(chunk, service_key=service_key, rest_url=rest_url)
        rows_loaded += len(chunk)
        if progress_stream is not None and (chunk_count == 1 or chunk_count % 10 == 0):
            print(
                f"processed Supabase chunk {chunk_count} ({rows_loaded} rows)",
                file=progress_stream,
                flush=True,
            )

    # In-place converges run after inserts so a canonical parent row already
    # exists when a surviving child re-points at it.
    for row, verified_parent_id in plan.in_place_updates:
        update_supabase_provision_parent(
            row_id=str(row["id"]),
            new_parent_id=row.get("parent_id"),
            verified_parent_id=verified_parent_id,
            service_key=service_key,
            rest_url=rest_url,
        )
        rows_loaded += 1

    return SupabaseLoadReport(
        rows_total=len(rows),
        rows_loaded=rows_loaded,
        chunk_count=chunk_count,
        dry_run=False,
        rows_inserted=len(plan.pending_inserts) - len(plan.replaced_ids),
        rows_replaced=len(plan.replaced_ids) + len(plan.in_place_updates),
        rows_already_staged=plan.rows_already_staged,
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


@dataclass(frozen=True)
class _ProvisionStagingPlan:
    pending_inserts: tuple[dict[str, object], ...]
    # (incoming row, parent_id the plan verified on the staged row)
    in_place_updates: tuple[tuple[dict[str, object], object], ...]
    replaced_ids: tuple[tuple[str, int], ...]
    rows_already_staged: int
    conflicts: tuple[dict[str, object], ...]


def _row_level(row: Mapping[str, object]) -> int:
    level = row.get("level")
    if isinstance(level, int) and not isinstance(level, bool):
        return level
    return 0


def _provision_column_equal(column: str, mine: object, theirs: object) -> bool:
    """Column-faithful equality between a projected value and PostgREST JSON.

    ``identifiers`` compares by the signed projection-digest encoding, so
    classification agrees exactly with what release evidence will hash: bool
    and int stay distinct (Python's ``True == 1`` cannot mask a value-type
    change) and text is exact. Values outside the digest contract (floats,
    nested structures — which publication rejects at digest time regardless)
    fall back to canonical JSON, keeping any ambiguity in the loud-conflict
    direction. Every other projected column is a scalar SQL type where plain
    equality over the JSON decoding is faithful.
    """
    if column == "identifiers":
        try:
            return encode_identifiers_projection(mine) == encode_identifiers_projection(theirs)
        except ProjectionDigestError:
            return json.dumps(mine, sort_keys=True) == json.dumps(theirs, sort_keys=True)
    return mine == theirs


def _dependency_ordered_inserts(
    pending_inserts: Sequence[dict[str, object]],
    conflicts: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Order pending inserts so every in-load parent precedes its children.

    A topological sort over the actual parent links is a guarantee the
    foreign key can hold across chunk boundaries; sorting by ``level`` would
    only restate an unchecked corpus invariant. Rows that share an id or form
    a parent cycle cannot be inserted coherently at all, so they become
    conflicts instead of runtime constraint errors.
    """
    pending_by_id: dict[str, dict[str, object]] = {}
    for row in pending_inserts:
        row_id = str(row.get("id"))
        if row_id in pending_by_id:
            conflicts.append(
                {
                    "kind": "duplicate-pending-id",
                    "citation_path": str(row.get("citation_path")),
                    "version": str(row.get("version")),
                    "staged_id": row_id,
                }
            )
            continue
        pending_by_id[row_id] = row
    children_by_parent: dict[str, list[str]] = {}
    in_degree: dict[str, int] = dict.fromkeys(pending_by_id, 0)
    for row_id, row in pending_by_id.items():
        parent = row.get("parent_id")
        parent_key = str(parent) if parent is not None else None
        if parent_key is not None and parent_key != row_id and parent_key in pending_by_id:
            children_by_parent.setdefault(parent_key, []).append(row_id)
            in_degree[row_id] += 1
    ordered_ids = [row_id for row_id, degree in in_degree.items() if degree == 0]
    cursor = 0
    while cursor < len(ordered_ids):
        for child in children_by_parent.get(ordered_ids[cursor], ()):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                ordered_ids.append(child)
        cursor += 1
    if len(ordered_ids) != len(pending_by_id):
        for row_id, degree in in_degree.items():
            if degree > 0:
                row = pending_by_id[row_id]
                conflicts.append(
                    {
                        "kind": "cyclic-parent-linkage",
                        "citation_path": str(row.get("citation_path")),
                        "version": str(row.get("version")),
                        "staged_id": row_id,
                    }
                )
        return list(pending_inserts)
    return [pending_by_id[row_id] for row_id in ordered_ids]


def _plan_provision_staging(
    rows: Sequence[dict[str, object]],
    *,
    rows_by_key: Mapping[tuple[str, str], dict[str, object]],
    service_key: str,
    rest_url: str,
) -> _ProvisionStagingPlan:
    """Classify a load against verified staged state before any write.

    Each incoming row lands in exactly one bucket: already staged
    byte-identically, insert (no staged row), in-place converge (content and
    id match, derived ``parent_id`` is stale), or replace (content matches, id
    is stale). Anything else — divergent content under an immutable key,
    staged rows the load does not describe, or a replacement whose ON DELETE
    CASCADE would reach a row that survives the load — is a conflict, and the
    caller writes nothing.
    """
    scope_keys: dict[tuple[str, str, str], None] = {}
    for row in rows:
        scope_keys.setdefault(
            (str(row["jurisdiction"]), str(row["doc_type"]), str(row["version"])), None
        )

    existing_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for jurisdiction, doc_type, version in scope_keys:
        for existing in fetch_staged_scope_rows(
            jurisdiction=jurisdiction,
            doc_type=doc_type,
            version=version,
            service_key=service_key,
            rest_url=rest_url,
        ):
            existing_by_key[(str(existing["citation_path"]), str(existing["version"]))] = existing

    conflicts: list[dict[str, object]] = []
    pending_inserts: list[dict[str, object]] = []
    in_place: dict[tuple[str, str], tuple[dict[str, object], object]] = {}
    replaced: dict[str, int] = {}
    matched_existing: dict[tuple[str, str], dict[str, object]] = {}
    rows_already_staged = 0

    leftover = dict(existing_by_key)
    for key, row in rows_by_key.items():
        staged = leftover.get(key)
        if staged is None:
            pending_inserts.append(row)
            continue
        del leftover[key]
        matched_existing[key] = staged
        divergent_content = sorted(
            column
            for column in PROVISION_CONTENT_COLUMNS
            if not _provision_column_equal(column, row.get(column), staged.get(column))
        )
        if divergent_content:
            conflicts.append(
                {
                    "kind": "content-mismatch",
                    "citation_path": key[0],
                    "version": key[1],
                    "fields": divergent_content,
                    "staged_id": str(staged.get("id")),
                }
            )
            continue
        if row.get("id") == staged.get("id"):
            if row.get("parent_id") == staged.get("parent_id"):
                rows_already_staged += 1
            else:
                in_place[key] = (row, staged.get("parent_id"))
            continue
        replaced[str(staged["id"])] = _row_level(staged)
        pending_inserts.append(row)

    for key, staged_leftover in leftover.items():
        conflicts.append(
            {
                "kind": "unexpected-staged-row",
                "citation_path": key[0],
                "version": key[1],
                "staged_id": str(staged_leftover.get("id")),
            }
        )

    # Replacing a stale id fires ``parent_id`` ON DELETE CASCADE. Chase the
    # closure: a dependent the load re-creates is escalated to a replacement
    # of its own (its cascade deletion is compensated by a canonical
    # re-insert); a dependent outside the load is a conflict — converging one
    # scope must never silently delete another scope's rows.
    frontier = set(replaced)
    while frontier:
        next_frontier: set[str] = set()
        for dependent in fetch_provision_rows_with_parents(
            sorted(frontier), service_key=service_key, rest_url=rest_url
        ):
            dependent_id = str(dependent.get("id"))
            if dependent_id in replaced:
                continue
            dependent_key = (
                str(dependent.get("citation_path")),
                str(dependent.get("version")),
            )
            incoming = rows_by_key.get(dependent_key)
            if incoming is None or matched_existing.get(dependent_key) is None:
                conflicts.append(
                    {
                        "kind": "cascade-outside-load",
                        "citation_path": dependent_key[0],
                        "version": dependent_key[1],
                        "staged_id": dependent_id,
                        "staged_parent_id": str(dependent.get("parent_id")),
                    }
                )
                continue
            if dependent_key in in_place:
                del in_place[dependent_key]
            elif str(incoming.get("id")) == dependent_id and incoming.get(
                "parent_id"
            ) == dependent.get("parent_id"):
                # Previously counted as already staged; the cascade will
                # delete it, so it must be re-created canonically instead.
                rows_already_staged -= 1
            else:
                continue
            replaced[dependent_id] = _row_level(dependent)
            pending_inserts.append(incoming)
            next_frontier.add(dependent_id)
        frontier = next_frontier

    # A load whose own projection references an id scheduled for deletion is
    # internally inconsistent: the insert phase would either FK-fail or, worse,
    # silently attach rows to a resurrected id with cascade-deleted children.
    for key, row in rows_by_key.items():
        parent_id = row.get("parent_id")
        if parent_id is not None and str(parent_id) in replaced:
            if str(row.get("id")) in replaced or any(
                str(pending.get("id")) == str(parent_id) for pending in pending_inserts
            ):
                continue
            conflicts.append(
                {
                    "kind": "replaced-id-still-referenced",
                    "citation_path": key[0],
                    "version": key[1],
                    "parent_id": str(parent_id),
                }
            )

    ordered_inserts = _dependency_ordered_inserts(pending_inserts, conflicts)
    conflicts.sort(key=lambda item: (str(item["kind"]), str(item["citation_path"])))
    return _ProvisionStagingPlan(
        pending_inserts=tuple(ordered_inserts),
        in_place_updates=tuple(in_place.values()),
        replaced_ids=tuple(replaced.items()),
        rows_already_staged=rows_already_staged,
        conflicts=tuple(conflicts),
    )


def fetch_staged_scope_rows(
    *,
    jurisdiction: str,
    doc_type: str,
    version: str,
    service_key: str,
    rest_url: str,
    page_size: int = 1_000,
) -> tuple[dict[str, object], ...]:
    """Fetch every staged projection row for one exact provision scope."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    fetched: list[dict[str, object]] = []
    last_id: str | None = None
    while True:
        query_params = {
            "select": ",".join(SUPABASE_PROVISIONS_COLUMNS),
            "jurisdiction": f"eq.{jurisdiction}",
            "doc_type": f"eq.{doc_type}",
            "version": f"eq.{version}",
            "order": "id.asc",
            "limit": str(page_size),
        }
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
            page = json.loads(resp.read())
        if not isinstance(page, list):
            raise RuntimeError("unexpected Supabase staged-scope response")
        page_rows = [row for row in page if isinstance(row, dict) and row.get("id") is not None]
        fetched.extend(page_rows)
        if len(page_rows) < page_size:
            break
        last_id = str(page_rows[-1]["id"])
    return tuple(fetched)


def fetch_provision_rows_with_parents(
    parent_ids: Sequence[str],
    *,
    service_key: str,
    rest_url: str,
    page_size: int = 1_000,
) -> tuple[dict[str, object], ...]:
    """Fetch the direct ON DELETE CASCADE set of ``parent_ids``.

    Returns the identity columns of every provision row whose ``parent_id``
    is one of the given ids, across all scopes, so replacement planning can
    prove a delete never reaches a row that should survive.
    """
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    dependents: list[dict[str, object]] = []
    for chunk in _chunked_values(list(parent_ids), 100):
        parent_filter = "in.(" + ",".join(_postgrest_in_value(value) for value in chunk) + ")"
        last_id: str | None = None
        while True:
            query_params = {
                "select": "id,citation_path,version,parent_id,level",
                "parent_id": parent_filter,
                "order": "id.asc",
                "limit": str(page_size),
            }
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
                page = json.loads(resp.read())
            if not isinstance(page, list):
                raise RuntimeError("unexpected Supabase cascade-dependent response")
            page_rows = [row for row in page if isinstance(row, dict) and row.get("id") is not None]
            dependents.extend(page_rows)
            if len(page_rows) < page_size:
                break
            last_id = str(page_rows[-1]["id"])
    return tuple(dependents)


def insert_supabase_rows(
    rows: list[dict[str, object]],
    *,
    service_key: str,
    rest_url: str,
) -> None:
    """Insert staged provision rows; any constraint violation is a loud error.

    Staging deliberately sends a plain insert with no PostgREST conflict
    resolution: the caller has already verified the staged state, so a
    conflict here means a concurrent writer or a verification gap, and both
    must fail instead of silently merging or skipping.
    """
    if not rows:
        return
    req = urllib.request.Request(
        f"{rest_url}/provisions",
        data=json.dumps(rows).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
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
        raise RuntimeError(f"insert failed {exc.code}: {body}") from exc


def update_supabase_provision_parent(
    *,
    row_id: str,
    new_parent_id: object,
    verified_parent_id: object,
    service_key: str,
    rest_url: str,
) -> None:
    """Re-point one verified staged row at its canonical parent.

    An in-place converge only ever changes ``parent_id`` — every other column
    was verified byte-identical during planning — so the update writes that
    single column and is conditioned on both the id and the parent value the
    plan verified. A row that vanished or changed between verification and
    write matches zero rows and fails loudly instead of being silently
    overwritten.
    """
    if not row_id:
        raise ValueError("provision parent update requires an id")
    params = {"id": f"eq.{row_id}"}
    if verified_parent_id is None:
        params["parent_id"] = "is.null"
    else:
        params["parent_id"] = f"eq.{verified_parent_id}"
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{rest_url}/provisions?{query}",
        data=json.dumps({"parent_id": new_parent_id}).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
            "Accept-Profile": "corpus",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"in-place converge failed {exc.code}: {body}") from exc
    affected = len(payload) if isinstance(payload, list) else None
    if affected != 1:
        raise RuntimeError(
            f"in-place converge for provision {row_id} affected "
            f"{affected if affected is not None else 'an unknown number of'} rows; "
            "expected exactly 1 (the row changed or vanished after verification)"
        )


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
        raise ValueError(
            f"table_name must be 'provisions' or 'navigation_nodes', got {table_name!r}"
        )
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
                    f"    transient HTTP {exc.code} on attempt {attempt + 1}/"
                    f"{max_retries + 1}: {body}",
                    file=progress_stream,
                    flush=True,
                )
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if progress_stream is not None:
                print(
                    f"    transient {type(exc).__name__} on attempt {attempt + 1}/"
                    f"{max_retries + 1}: {exc}",
                    file=progress_stream,
                    flush=True,
                )

        if attempt < max_retries:
            sleep_for = base_backoff_seconds * (2**attempt)
            time.sleep(sleep_for)

    raise RuntimeError(
        f"backfill_version_chunk failed after {max_retries + 1} attempts: {last_error}"
    )


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
