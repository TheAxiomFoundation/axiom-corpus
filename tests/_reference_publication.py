"""Pre-streaming publication code, kept as test oracles.

Every function, class and constant below is the implementation that
``origin/main`` shipped at cf46a725b, copied verbatim from that commit's
source with only its name prefixed (``_reference_`` for functions,
``_Reference`` for classes, ``_REFERENCE_`` for constants) and references to
the other copied names renamed with it. They hold whole artifacts in memory;
the streaming replacements must agree with them exactly, result for result
and exception for exception, and the differential tests assert that.
Low-level primitives whose bodies this change did not touch (record models,
row projection, network calls, path checks) are imported from the package.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import mimetypes
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any, TextIO
from uuid import UUID

from botocore.exceptions import ClientError

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.document_sections import split_document_body
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.navigation import NavigationNode, deterministic_navigation_id
from axiom_corpus.corpus.projection_digest import (
    NAVIGATION_PROJECTION_COLUMNS,
    PROVISION_PROJECTION_COLUMNS,
    ProjectionDigestError,
    encode_identifiers_projection,
)
from axiom_corpus.corpus.r2 import ArtifactReport, _sha256_file
from axiom_corpus.corpus.release_quality import ReleaseValidationIssue, ReleaseValidationReport
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.supabase import (
    _STAGED_SCOPE_FETCH_BASE_BACKOFF_SECONDS,
    _STAGED_SCOPE_FETCH_MAX_ATTEMPTS,
    DEFAULT_AXIOM_SUPABASE_URL,
    POSTGRES_INT32_MAX,
    POSTGRES_INT32_MIN,
    PROVISION_CONTENT_COLUMNS,
    SUPABASE_PROVISIONS_COLUMNS,
    USER_AGENT,
    ProvisionStagingConflictError,
    SupabaseLoadReport,
    _normalize_version,
    _rest_url,
    delete_supabase_provision_ids,
    deterministic_provision_id,
    fetch_provision_rows_with_parents,
    insert_supabase_rows,
    provision_to_supabase_row,
    update_supabase_provision_parent,
)
from axiom_corpus.release.manifest import (
    _ARTIFACT_CLASSES,
    ReleaseManifestError,
    _canonical_signed_source_reference,
    canonical_corpus_artifact_file,
    selector_sha256,
)
from axiom_corpus.release.publication import (
    _MAX_CONDITIONAL_WRITE_ATTEMPTS,
    _ArtifactEntry,
    _is_conditional_write_conflict,
    _snapshot_file,
    _StagedArtifact,
)

# --- src/axiom_corpus/corpus/io.py at cf46a725b ---


def _reference_load_source_inventory(path: str | Path) -> tuple[SourceInventoryItem, ...]:
    data = json.loads(Path(path).read_text())
    rows = data.get("items", data if isinstance(data, list) else [])
    return tuple(SourceInventoryItem.from_mapping(row) for row in rows)


def _reference_load_provisions(path: str | Path) -> tuple[ProvisionRecord, ...]:
    records: list[ProvisionRecord] = []
    p = Path(path)
    if not p.exists():
        return ()
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        records.append(ProvisionRecord.from_mapping(data))
    return tuple(records)


# --- src/axiom_corpus/corpus/projection_digest.py at cf46a725b ---


def _reference_provision_projection_sha256(rows: Iterable[Mapping[str, object]]) -> str:
    """Hash exact provision projection rows in citation-path identity order."""
    return _reference_projection_sha256(
        rows,
        columns=PROVISION_PROJECTION_COLUMNS,
        order_by=("citation_path", "id"),
        mapping_columns={"identifiers"},
    )


def _reference_navigation_projection_sha256(rows: Iterable[Mapping[str, object]]) -> str:
    """Hash exact navigation projection rows in path identity order."""
    return _reference_projection_sha256(
        rows,
        columns=NAVIGATION_PROJECTION_COLUMNS,
        order_by=("path", "id"),
    )


def _reference_projection_sha256(
    rows: Iterable[Mapping[str, object]],
    *,
    columns: Sequence[str],
    order_by: Sequence[str],
    mapping_columns: set[str] | None = None,
) -> str:
    """Return the canonical digest for one complete scope projection."""
    materialized = tuple(rows)
    required = set(columns)
    for row in materialized:
        if set(row) != required:
            missing = sorted(required - set(row))
            extra = sorted(set(row) - required)
            raise ProjectionDigestError(
                f"projection row fields differ; missing={missing!r}, extra={extra!r}"
            )
    try:
        ordered = sorted(
            materialized,
            key=lambda row: tuple(_reference_required_identity(row.get(field), field) for field in order_by),
        )
    except TypeError as exc:
        raise ProjectionDigestError("projection identity fields are not comparable") from exc

    scope = hashlib.sha256()
    mapping_fields = mapping_columns or set()
    for row in ordered:
        payload = "".join(
            _reference_encode_identifiers(row[column])
            if column in mapping_fields
            else _reference_encode_scalar(row[column])
            for column in columns
        )
        scope.update(hashlib.sha256(payload.encode("utf-8")).hexdigest().encode("ascii"))
    return scope.hexdigest()


def _reference_required_identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectionDigestError(f"projection identity field {field!r} must be a string")
    return value


def _reference_encode_scalar(value: object) -> str:
    if value is None:
        return "N"
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value
    else:
        raise ProjectionDigestError(f"unsupported projection scalar type: {type(value).__name__}")
    return f"V{len(text.encode('utf-8'))}:{text}"


def _reference_encode_identifiers(value: object) -> str:
    if value is None:
        return "N"
    if not isinstance(value, Mapping):
        raise ProjectionDigestError("projection identifiers must be a string mapping")
    if any(not isinstance(key, str) for key in value):
        raise ProjectionDigestError("projection identifier keys must be strings")
    parts: list[str] = []
    for key in sorted(value):
        item = value[key]
        parts.append(_reference_encode_scalar(key))
        parts.append(_reference_encode_scalar(item))
    return _reference_encode_scalar("".join(parts))


# --- src/axiom_corpus/corpus/navigation.py at cf46a725b ---


def _reference_build_navigation_nodes(
    records: Iterable[ProvisionRecord],
    *,
    jurisdiction: str | None = None,
    document_class: str | None = None,
    encoded_paths: Iterable[str] | None = None,
) -> tuple[NavigationNode, ...]:
    """Project provision records into `corpus.navigation_nodes` rows.

    The returned tuple is sorted by `(parent_path, sort_key, path)` so repeated
    runs on identical input produce byte-identical output, regardless of the
    order in which the source provisions were emitted.

    Optional `jurisdiction` / `document_class` filters mirror the scope flags
    on the CLI: callers that want the full corpus pass them as ``None``.

    ``encoded_paths`` augments ``record.has_rulespec`` from an external source
    (typically the jurisdiction's `rulespec-*` repo, see
    ``axiom_corpus.corpus.rulespec_paths``). A node whose path is in the set
    is treated as encoded even when the corresponding provision row has
    ``has_rulespec=False``. Ancestor ``encoded_descendant_count`` then
    propagates from those augmented values, so encoded-only browsing is
    discoverable from the top of the tree.
    """
    filtered: list[ProvisionRecord] = []
    seen_paths: set[str] = set()
    for record in records:
        if jurisdiction is not None and record.jurisdiction != jurisdiction:
            continue
        if document_class is not None and record.document_class != document_class:
            continue
        if record.citation_path in seen_paths:
            # Provisions JSONL should be unique per citation_path, but be
            # defensive: collapse duplicates rather than emitting two nodes.
            continue
        seen_paths.add(record.citation_path)
        filtered.append(record)

    encoded_set: set[str] = set(encoded_paths) if encoded_paths is not None else set()

    by_path: dict[str, ProvisionRecord] = {r.citation_path: r for r in filtered}

    parent_paths: dict[str, str | None] = {}
    for record in filtered:
        parent_paths[record.citation_path] = _reference_resolve_parent_path(record, by_path)

    _reference_break_parent_cycles(parent_paths)

    depths = _reference_resolve_depths(parent_paths)

    nodes: dict[str, NavigationNode] = {}
    for record in filtered:
        path = record.citation_path
        parent_path = parent_paths[path]
        segment = _reference_segment(path, parent_path)
        nodes[path] = NavigationNode(
            id=deterministic_navigation_id(path, record.version),
            jurisdiction=record.jurisdiction,
            doc_type=record.document_class,
            path=path,
            parent_path=parent_path,
            segment=segment,
            label=_reference_label_for(record, segment),
            sort_key=_reference_sort_key(record, segment),
            depth=depths[path],
            provision_id=_reference_provision_id_for_navigation(record),
            citation_path=path,
            version=record.version,
            has_rulespec=bool(record.has_rulespec) or path in encoded_set,
            status=_reference_status_for(record),
        )

    children_by_parent: dict[str, list[NavigationNode]] = defaultdict(list)
    for node in nodes.values():
        if node.parent_path is not None and node.parent_path in nodes:
            children_by_parent[node.parent_path].append(node)

    encoded_descendants: dict[str, int] = defaultdict(int)
    for node in sorted(nodes.values(), key=lambda n: -n.depth):
        own = (1 if node.has_rulespec else 0) + encoded_descendants[node.path]
        if node.parent_path is not None and node.parent_path in nodes:
            encoded_descendants[node.parent_path] += own

    finalized = [
        replace(
            node,
            has_children=bool(children_by_parent.get(node.path)),
            child_count=len(children_by_parent.get(node.path, ())),
            encoded_descendant_count=encoded_descendants[node.path],
        )
        for node in nodes.values()
    ]
    return tuple(
        sorted(
            finalized,
            key=lambda n: (n.parent_path or "", n.sort_key, n.path),
        )
    )


def _reference_provision_id_for_navigation(record: ProvisionRecord) -> str:
    legacy_id = deterministic_provision_id(record.citation_path)
    try:
        explicit_id = str(UUID(record.id)) if record.id is not None else None
    except ValueError as exc:
        raise ValueError(f"provision id must be a UUID: {record.id!r}") from exc
    if record.version and (explicit_id is None or explicit_id == legacy_id):
        return deterministic_provision_id(record.citation_path, record.version)
    return explicit_id or legacy_id


def _reference_resolve_parent_path(
    record: ProvisionRecord,
    by_path: dict[str, ProvisionRecord],
) -> str | None:
    explicit = record.parent_citation_path
    if explicit and explicit != record.citation_path and explicit in by_path:
        return explicit
    parts = record.citation_path.split("/")
    for size in range(len(parts) - 1, 0, -1):
        candidate = "/".join(parts[:size])
        if candidate in by_path and candidate != record.citation_path:
            return candidate
    return None


def _reference_break_parent_cycles(parent_paths: dict[str, str | None]) -> None:
    """Promote any node that participates in a parent cycle to a root.

    `_reference_resolve_parent_path` rejects self-edges, but a record A whose parent is B
    while B's parent is A would still produce a two-cycle. Walking the chain
    here catches that and any longer cycle. One stable member of each actual
    cycle has its `parent_path` cleared so descendants outside the cycle remain
    attached and repeated builds produce the same rows regardless of input
    order.
    """
    for start in sorted(parent_paths):
        chain: list[str] = []
        seen_at: dict[str, int] = {}
        cursor: str | None = start
        while cursor is not None and cursor in parent_paths:
            if cursor in seen_at:
                cycle_nodes = chain[seen_at[cursor] :]
                parent_paths[min(cycle_nodes)] = None
                break
            seen_at[cursor] = len(chain)
            chain.append(cursor)
            cursor = parent_paths.get(cursor)


def _reference_resolve_depths(parent_paths: dict[str, str | None]) -> dict[str, int]:
    depths: dict[str, int] = {}

    def depth_of(path: str, stack: tuple[str, ...] = ()) -> int:
        if path in depths:
            return depths[path]
        if path in stack:
            # Defensive: parent cycles in the dataset would otherwise recurse
            # forever. Treat the cycle entry as a root.
            depths[path] = 0
            return 0
        parent = parent_paths.get(path)
        if parent is None or parent not in parent_paths:
            depths[path] = 0
            return 0
        value = depth_of(parent, stack + (path,)) + 1
        depths[path] = value
        return value

    for path in parent_paths:
        depth_of(path)
    return depths


def _reference_segment(path: str, parent_path: str | None) -> str:
    if parent_path and path.startswith(parent_path + "/"):
        return path[len(parent_path) + 1 :]
    if "/" in path:
        return path.rsplit("/", 1)[-1]
    return path


def _reference_label_for(record: ProvisionRecord, segment: str) -> str:
    for candidate in (record.heading, record.citation_label):
        if candidate:
            text = candidate.strip()
            if text:
                return text
    return segment


def _reference_status_for(record: ProvisionRecord) -> str | None:
    if record.metadata:
        status = record.metadata.get("status")
        if isinstance(status, str) and status.strip():
            return status.strip()
    return None


_REFERENCE_SORT_NUMERIC_RUN = re.compile(r"(\d+)")


_REFERENCE_SORT_PAD_WIDTH = 12


def _reference_sort_key(record: ProvisionRecord, segment: str) -> str:
    """Return a natural-order sort key.

    Falling back to a derivation that already exists in `corpus.provisions`:
    `level` orders peer groups, and within a group the segment's numeric runs
    are zero-padded so 2 < 10 even when compared lexicographically. The
    leading ordinal slot keeps explicit `ordinal` values authoritative when
    set.
    """
    ordinal_slot = (
        f"{record.ordinal:08d}"
        if isinstance(record.ordinal, int) and record.ordinal >= 0
        else "z" * 8
    )
    normalized = _reference_normalize_sort_segment(segment)
    return f"{ordinal_slot}|{normalized}"


def _reference_normalize_sort_segment(segment: str) -> str:
    lowered = segment.lower()
    return _REFERENCE_SORT_NUMERIC_RUN.sub(_reference_pad_match, lowered)


def _reference_pad_match(match: re.Match[str]) -> str:
    digits = match.group(1)
    return digits.rjust(_REFERENCE_SORT_PAD_WIDTH, "0")


# --- src/axiom_corpus/corpus/supabase.py at cf46a725b ---


def _reference_iter_supabase_rows(
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


def _reference_load_provisions_to_supabase(
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

    rows = list(_reference_iter_supabase_rows(_require_release_versions(records), versioned_ids=True))

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
            chunk_count=sum(1 for _ in _reference_chunked(iter(rows), chunk_size)),
            dry_run=True,
        )

    rest_url = _rest_url(supabase_url)
    plan = _reference_plan_provision_staging(
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
    for delete_chunk in _reference_chunked_values(
        [row_id for row_id, _ in sorted(plan.replaced_ids, key=lambda item: (-item[1], item[0]))],
        100,
    ):
        delete_supabase_provision_ids(delete_chunk, service_key=service_key, rest_url=rest_url)

    rows_loaded = plan.rows_already_staged
    chunk_count = 0
    for chunk in _reference_chunked(iter(plan.pending_inserts), chunk_size):
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


@dataclass(frozen=True)
class _ReferenceProvisionStagingPlan:
    pending_inserts: tuple[dict[str, object], ...]
    # (incoming row, parent_id the plan verified on the staged row)
    in_place_updates: tuple[tuple[dict[str, object], object], ...]
    replaced_ids: tuple[tuple[str, int], ...]
    rows_already_staged: int
    conflicts: tuple[dict[str, object], ...]



def _reference_row_level(row: Mapping[str, object]) -> int:
    level = row.get("level")
    if isinstance(level, int) and not isinstance(level, bool):
        return level
    return 0


def _reference_provision_column_equal(column: str, mine: object, theirs: object) -> bool:
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


def _reference_dependency_ordered_inserts(
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
    # A heap makes the otherwise under-specified order between independent
    # trees deterministic.  This matters operationally: every retry produces
    # the same chunk boundaries while still guaranteeing parents-first order.
    ready = [row_id for row_id, degree in in_degree.items() if degree == 0]
    heapq.heapify(ready)
    ordered_ids: list[str] = []
    while ready:
        row_id = heapq.heappop(ready)
        ordered_ids.append(row_id)
        for child in sorted(children_by_parent.get(row_id, ())):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                heapq.heappush(ready, child)
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


def _reference_plan_provision_staging(
    rows: Sequence[dict[str, object]],
    *,
    rows_by_key: Mapping[tuple[str, str], dict[str, object]],
    service_key: str,
    rest_url: str,
) -> _ReferenceProvisionStagingPlan:
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
        for existing in _reference_fetch_staged_scope_rows(
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
            if not _reference_provision_column_equal(column, row.get(column), staged.get(column))
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
        replaced[str(staged["id"])] = _reference_row_level(staged)
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
            replaced[dependent_id] = _reference_row_level(dependent)
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

    ordered_inserts = _reference_dependency_ordered_inserts(pending_inserts, conflicts)
    conflicts.sort(key=lambda item: (str(item["kind"]), str(item["citation_path"])))
    return _ReferenceProvisionStagingPlan(
        pending_inserts=tuple(ordered_inserts),
        in_place_updates=tuple(in_place.values()),
        replaced_ids=tuple(replaced.items()),
        rows_already_staged=rows_already_staged,
        conflicts=tuple(conflicts),
    )


def _reference_fetch_staged_scope_rows(
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
        for attempt in range(_STAGED_SCOPE_FETCH_MAX_ATTEMPTS):
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    page = json.loads(resp.read())
                break
            except urllib.error.HTTPError as exc:
                if 400 <= exc.code < 500:
                    raise
                if attempt + 1 == _STAGED_SCOPE_FETCH_MAX_ATTEMPTS:
                    raise
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if attempt + 1 == _STAGED_SCOPE_FETCH_MAX_ATTEMPTS:
                    raise
            time.sleep(_STAGED_SCOPE_FETCH_BASE_BACKOFF_SECONDS * (2**attempt))
        else:
            raise AssertionError("staged-scope retry loop exhausted unexpectedly")
        if not isinstance(page, list):
            raise RuntimeError("unexpected Supabase staged-scope response")
        page_rows = [row for row in page if isinstance(row, dict) and row.get("id") is not None]
        fetched.extend(page_rows)
        if len(page_rows) < page_size:
            break
        last_id = str(page_rows[-1]["id"])
    return tuple(fetched)


def _reference_chunked(
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


def _reference_chunked_values(values: Iterable[str], size: int) -> Iterator[list[str]]:
    chunk: list[str] = []
    for value in values:
        chunk.append(value)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


# --- src/axiom_corpus/corpus/release_quality.py at cf46a725b ---


_REFERENCE_PROFILED_CITATION_UNIQUENESS_GRANDFATHER = {
    "us-rulespec-2026-07-19": "79c091b4501eecb2996936ba51c87955f89460d9e3690b0fde88c30742547e9d"
}


class _ReferenceIssueCollector:
    def __init__(self, max_issues: int):
        self.max_issues = max_issues
        self.error_count = 0
        self.warning_count = 0
        self.issues: list[ReleaseValidationIssue] = []

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        scope: ReleaseScope | None = None,
        path: str | Path | None = None,
    ) -> None:
        if severity == "error":
            self.error_count += 1
        elif severity == "warning":
            self.warning_count += 1
        else:
            raise ValueError(f"invalid validation severity: {severity}")
        if len(self.issues) >= self.max_issues:
            return
        self.issues.append(
            ReleaseValidationIssue(
                severity=severity,
                code=code,
                message=message,
                jurisdiction=scope.jurisdiction if scope else None,
                document_class=scope.document_class if scope else None,
                version=scope.version if scope else None,
                path=str(path) if path is not None else None,
            )
        )


def _reference_validate_release(
    root: str | Path,
    release: ReleaseManifest,
    *,
    artifact_report: ArtifactReport | None = None,
    max_issues: int = 200,
    strict_warnings: bool = False,
    ignore_r2_missing: bool = False,
) -> ReleaseValidationReport:
    """Validate release-scoped artifacts before promotion or publication."""
    if max_issues <= 0:
        raise ValueError("max_issues must be positive")
    store = CorpusArtifactStore(root)
    collector = _ReferenceIssueCollector(max_issues=max_issues)
    artifact_rows = {}
    if artifact_report is not None:
        _reference_validate_artifact_report(
            artifact_report,
            collector,
            ignore_r2_missing=ignore_r2_missing,
        )
        artifact_rows = {
            (row.jurisdiction, row.document_class, row.version): row for row in artifact_report.rows
        }
    uniqueness_grandfathered = _reference_citation_uniqueness_grandfathered(release)
    require_unique_citations = (
        release.requires_complete_expression_dates and not uniqueness_grandfathered
    )
    if release.requires_complete_expression_dates and uniqueness_grandfathered:
        collector.add(
            "warning",
            "legacy_release_citation_uniqueness_grandfathered",
            "known historical release predates release-wide citation uniqueness enforcement",
        )
    release_citation_paths = _reference_release_citation_paths(
        store,
        release,
        artifact_rows,
        collector,
        require_unique=require_unique_citations,
    )
    for scope in release.scopes:
        if _reference_scope_has_remote_artifacts(scope, artifact_rows):
            collector.add(
                "warning",
                "remote_only_scope_not_deep_validated",
                (
                    "release scope is complete in R2 but local cache artifacts are absent, "
                    "so deep record validation was skipped"
                ),
                scope=scope,
            )
            continue
        _reference_validate_scope(
            store,
            scope,
            collector,
            release_citation_paths,
            require_expression_dates=release.requires_complete_expression_dates,
        )
    return ReleaseValidationReport(
        release_name=release.name,
        scope_count=len(release.scopes),
        error_count=collector.error_count,
        warning_count=collector.warning_count,
        issues=tuple(collector.issues),
        max_issues=max_issues,
        strict_warnings=strict_warnings,
    )


def _reference_citation_uniqueness_grandfathered(release: ReleaseManifest) -> bool:
    expected = _REFERENCE_PROFILED_CITATION_UNIQUENESS_GRANDFATHER.get(release.name)
    return expected is not None and selector_sha256(release) == expected


def _reference_release_citation_paths(
    store: CorpusArtifactStore,
    release: ReleaseManifest,
    artifact_rows: Mapping[tuple[str, str, str], Any],
    collector: _ReferenceIssueCollector,
    *,
    require_unique: bool,
) -> set[str]:
    """Collect parents available anywhere in the local release cut.

    A release may deliberately split a legal hierarchy across source snapshots.
    Parent integrity is therefore a release-wide invariant, not a scope-local one.
    Parsing errors remain owned by ``_reference_validate_scope`` so they are reported once.
    """
    paths: set[str] = set()
    owners: dict[str, ReleaseScope] = {}
    for scope in release.scopes:
        if _reference_scope_has_remote_artifacts(scope, artifact_rows):
            if require_unique:
                collector.add(
                    "error",
                    "release_citation_uniqueness_unverified",
                    (
                        "profiled release citation uniqueness cannot be verified because "
                        "the scope provisions are available only in remote artifacts"
                    ),
                    scope=scope,
                )
            continue
        path = store.provisions_path(scope.jurisdiction, scope.document_class, scope.version)
        try:
            provisions = _reference_load_provisions(path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        for record in provisions:
            owner = owners.get(record.citation_path)
            if require_unique and owner is not None and owner != scope:
                collector.add(
                    "error",
                    "duplicate_release_citation",
                    (
                        f"citation_path {record.citation_path} is also present in "
                        f"{owner.jurisdiction}/{owner.document_class}/{owner.version}"
                    ),
                    scope=scope,
                    path=path,
                )
            else:
                owners[record.citation_path] = scope
            paths.add(record.citation_path)
    return paths


def _reference_validate_artifact_report(
    artifact_report: ArtifactReport,
    collector: _ReferenceIssueCollector,
    *,
    ignore_r2_missing: bool = False,
) -> None:
    for row in artifact_report.rows:
        reasons = row.mismatch_reasons()
        if ignore_r2_missing:
            reasons = tuple(reason for reason in reasons if not reason.startswith("missing_r2_"))
        if not reasons:
            continue
        collector.add(
            "error",
            "artifact_report_mismatch",
            f"artifact report has mismatch reasons: {', '.join(reasons)}",
            scope=ReleaseScope(
                jurisdiction=row.jurisdiction,
                document_class=row.document_class,
                version=row.version,
            ),
        )
    for group in artifact_report.supabase_groups:
        reasons = group.mismatch_reasons()
        if not reasons:
            continue
        collector.add(
            "error",
            "supabase_count_mismatch",
            (
                f"Supabase count {group.supabase_count} does not match "
                f"release provision count {group.provision_count}"
            ),
            scope=ReleaseScope(
                jurisdiction=group.jurisdiction,
                document_class=group.document_class,
                version=",".join(group.versions),
            ),
        )


def _reference_scope_has_remote_artifacts(
    scope: ReleaseScope,
    rows: Mapping[tuple[str, str, str], Any],
) -> bool:
    row = rows.get(scope.key)
    if row is None:
        return False
    local_complete = row.local_inventory and row.local_provisions and row.local_coverage
    if local_complete:
        return False
    return (
        row.remote_inventory is True
        and row.remote_provisions is True
        and row.remote_coverage is True
        and row.coverage_complete is True
        and row.provision_count is not None
    )


def _reference_validate_scope(
    store: CorpusArtifactStore,
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
    release_citation_paths: set[str],
    *,
    require_expression_dates: bool,
) -> None:
    inventory_path = store.inventory_path(scope.jurisdiction, scope.document_class, scope.version)
    provisions_path = store.provisions_path(scope.jurisdiction, scope.document_class, scope.version)
    coverage_path = store.coverage_path(scope.jurisdiction, scope.document_class, scope.version)
    inventory = _reference_load_inventory_for_validation(inventory_path, scope, collector)
    provisions = _reference_load_provisions_for_validation(provisions_path, scope, collector)
    coverage = _reference_load_coverage_for_validation(coverage_path, scope, collector)
    if inventory is None or provisions is None:
        return
    inventory_source_paths = _reference_validate_inventory(store.root, inventory, scope, collector)
    _reference_validate_provisions(
        store.root,
        provisions,
        inventory_source_paths,
        scope,
        collector,
        release_citation_paths,
        require_expression_dates=require_expression_dates,
    )
    recomputed = compare_provision_coverage(
        inventory,
        provisions,
        jurisdiction=scope.jurisdiction,
        document_class=scope.document_class,
        version=scope.version,
    )
    if not recomputed.complete:
        collector.add(
            "error",
            "coverage_incomplete",
            "recomputed citation coverage is incomplete",
            scope=scope,
            path=coverage_path,
        )
    if coverage is not None:
        if not coverage.get("complete"):
            collector.add(
                "error",
                "persisted_coverage_incomplete",
                "persisted coverage report is incomplete",
                scope=scope,
                path=coverage_path,
            )
        expected_counts = {
            "source_count": recomputed.source_count,
            "provision_count": recomputed.provision_count,
            "matched_count": recomputed.matched_count,
        }
        for key, expected in expected_counts.items():
            if int(coverage.get(key, -1)) != expected:
                collector.add(
                    "error",
                    "coverage_count_mismatch",
                    f"persisted {key}={coverage.get(key)} but recomputed {expected}",
                    scope=scope,
                    path=coverage_path,
                )


def _reference_load_inventory_for_validation(
    path: Path,
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
) -> tuple[SourceInventoryItem, ...] | None:
    if not path.exists():
        collector.add(
            "error", "missing_inventory", "inventory artifact is missing", scope=scope, path=path
        )
        return None
    try:
        return _reference_load_source_inventory(path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        collector.add("error", "invalid_inventory", str(exc), scope=scope, path=path)
        return None


def _reference_load_provisions_for_validation(
    path: Path,
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
) -> tuple[ProvisionRecord, ...] | None:
    if not path.exists():
        collector.add(
            "error", "missing_provisions", "provisions artifact is missing", scope=scope, path=path
        )
        return None
    try:
        return _reference_load_provisions(path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        collector.add("error", "invalid_provisions", str(exc), scope=scope, path=path)
        return None


def _reference_load_coverage_for_validation(
    path: Path,
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
) -> dict[str, Any] | None:
    if not path.exists():
        collector.add(
            "error", "missing_coverage", "coverage artifact is missing", scope=scope, path=path
        )
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        collector.add("error", "invalid_coverage", str(exc), scope=scope, path=path)
        return None
    if not isinstance(data, dict):
        collector.add(
            "error",
            "invalid_coverage",
            "coverage artifact must be a JSON object",
            scope=scope,
            path=path,
        )
        return None
    return data


def _reference_validate_inventory(
    root: Path,
    inventory: tuple[SourceInventoryItem, ...],
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
) -> set[str]:
    source_hashes: dict[str, str] = {}
    inventory_source_paths: set[str] = set()
    for item in inventory:
        if not item.citation_path:
            collector.add(
                "error",
                "empty_inventory_citation",
                "inventory item has no citation_path",
                scope=scope,
            )
        validated = _reference_validate_source_file(
            root,
            item.source_path,
            scope,
            collector,
            reference_kind="inventory",
            citation_path=item.citation_path,
        )
        if validated is not None:
            source_identity, source_path = validated
            inventory_source_paths.add(source_identity)
        else:
            source_identity = None
            source_path = None

        if not isinstance(item.sha256, str) or not item.sha256:
            collector.add(
                "error",
                "missing_inventory_source_sha256",
                f"inventory item {item.citation_path} has no source sha256",
                scope=scope,
            )
        elif source_identity is not None and source_path is not None:
            digest = source_hashes.get(source_identity)
            if digest is None:
                try:
                    digest = _sha256_file(source_path)
                except OSError as exc:
                    collector.add(
                        "error",
                        "unreadable_inventory_source_file",
                        f"cannot read source file {source_identity}: {exc}",
                        scope=scope,
                        path=source_path,
                    )
                    continue
                source_hashes[source_identity] = digest
            if digest != item.sha256:
                collector.add(
                    "error",
                    "source_sha256_mismatch",
                    f"source sha256 mismatch for {source_identity}",
                    scope=scope,
                    path=source_path,
                )
    return inventory_source_paths


def _reference_validate_source_file(
    root: Path,
    source_path: object,
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
    *,
    reference_kind: str,
    citation_path: str,
) -> tuple[str, Path | None] | None:
    if not isinstance(source_path, str) or not source_path:
        collector.add(
            "error",
            f"missing_{reference_kind}_source_path",
            f"{reference_kind} item {citation_path} has no source_path",
            scope=scope,
        )
        return None

    parts = source_path.split("/")
    expected_prefix = [
        "sources",
        scope.jurisdiction,
        scope.document_class,
        scope.version,
    ]
    if (
        source_path.startswith("/")
        or "\\" in source_path
        or len(parts) <= len(expected_prefix)
        or parts[: len(expected_prefix)] != expected_prefix
        or any(part in {"", ".", ".."} for part in parts)
    ):
        collector.add(
            "error",
            f"noncanonical_{reference_kind}_source_path",
            (
                f"{reference_kind} item {citation_path} source_path must be under "
                f"{'/'.join(expected_prefix)}/: {source_path}"
            ),
            scope=scope,
            path=source_path,
        )
        return None

    try:
        corpus_root = root.resolve(strict=True)
    except OSError as exc:
        collector.add(
            "error",
            f"missing_{reference_kind}_source_file",
            f"corpus root is unavailable while validating {source_path}: {exc}",
            scope=scope,
            path=source_path,
        )
        return source_path, None

    lexical = corpus_root
    for part in parts:
        lexical = lexical / part
        if lexical.is_symlink():
            collector.add(
                "error",
                f"symlinked_{reference_kind}_source_path",
                f"{reference_kind} source_path contains a symlink: {source_path}",
                scope=scope,
                path=lexical,
            )
            return source_path, None

    try:
        resolved = lexical.resolve(strict=True)
    except (OSError, RuntimeError):
        collector.add(
            "error",
            f"missing_{reference_kind}_source_file",
            f"{reference_kind} source file is missing: {source_path}",
            scope=scope,
            path=lexical,
        )
        return source_path, None

    try:
        resolved.relative_to(corpus_root)
    except ValueError:
        collector.add(
            "error",
            f"noncanonical_{reference_kind}_source_path",
            f"{reference_kind} source file escapes the corpus root: {source_path}",
            scope=scope,
            path=resolved,
        )
        return source_path, None
    if resolved != lexical:
        collector.add(
            "error",
            f"noncanonical_{reference_kind}_source_path",
            f"{reference_kind} source_path is not canonical: {source_path}",
            scope=scope,
            path=resolved,
        )
        return source_path, None
    if not resolved.is_file():
        collector.add(
            "error",
            f"nonregular_{reference_kind}_source_file",
            f"{reference_kind} source_path is not a regular file: {source_path}",
            scope=scope,
            path=resolved,
        )
        return source_path, None
    return source_path, resolved


def _reference_validate_provisions(
    root: Path,
    provisions: tuple[ProvisionRecord, ...],
    inventory_source_paths: set[str],
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
    release_citation_paths: set[str] | None = None,
    *,
    require_expression_dates: bool = False,
) -> None:
    try:
        DocumentClass(scope.document_class)
    except ValueError:
        collector.add(
            "error",
            "invalid_document_class",
            f"invalid document_class {scope.document_class}",
            scope=scope,
        )
    by_path: dict[str, ProvisionRecord] = {}
    by_id: dict[str, ProvisionRecord] = {}
    checked_source_paths: set[str] = set()
    for record in provisions:
        if record.citation_path in by_path:
            collector.add(
                "error",
                "duplicate_provision_citation",
                f"duplicate citation_path {record.citation_path}",
                scope=scope,
            )
        by_path[record.citation_path] = record
        record_id = record.id or deterministic_provision_id(record.citation_path)
        if record_id in by_id:
            collector.add(
                "error",
                "duplicate_provision_id",
                f"duplicate provision id {record_id}",
                scope=scope,
            )
        by_id[record_id] = record
        if not isinstance(record.source_path, str) or not record.source_path:
            _reference_validate_source_file(
                root,
                record.source_path,
                scope,
                collector,
                reference_kind="provision",
                citation_path=record.citation_path,
            )
        elif record.source_path not in checked_source_paths:
            checked_source_paths.add(record.source_path)
            validated = _reference_validate_source_file(
                root,
                record.source_path,
                scope,
                collector,
                reference_kind="provision",
                citation_path=record.citation_path,
            )
            if validated is not None and validated[0] not in inventory_source_paths:
                collector.add(
                    "error",
                    "provision_source_not_in_inventory",
                    (
                        f"provision {record.citation_path} source_path is not present "
                        f"in the scope inventory: {record.source_path}"
                    ),
                    scope=scope,
                    path=record.source_path,
                )
    for record in provisions:
        _reference_validate_provision_record(
            record,
            by_path,
            scope,
            collector,
            release_citation_paths or set(by_path),
            require_expression_dates=require_expression_dates,
        )


def _reference_warn_unsectioned_document(
    record: ProvisionRecord,
    by_path: dict[str, ProvisionRecord],
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
) -> None:
    """Warn when a document-level body carries printed section markers
    (Part/Step/Schedule) but the document has no child provisions at
    all — the app then has no child nodes to navigate into. Fix with
    ``section-provisions``. Any existing children (marker sections,
    per-capture form variants, /values supplements) already make the
    document navigable, so they silence the warning.
    """
    if record.kind != "document" or not record.body:
        return
    prefix = record.citation_path + "/"
    if any(path.startswith(prefix) for path in by_path):
        return
    if split_document_body(record.body) is None:
        return
    collector.add(
        "warning",
        "unsectioned_document_body",
        (
            f"{record.citation_path} has top-level section markers but no "
            "section children; run axiom-corpus-ingest section-provisions"
        ),
        scope=scope,
    )


def _reference_validate_provision_record(
    record: ProvisionRecord,
    by_path: dict[str, ProvisionRecord],
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
    release_citation_paths: set[str],
    *,
    require_expression_dates: bool,
) -> None:
    if record.jurisdiction != scope.jurisdiction:
        collector.add(
            "error",
            "provision_jurisdiction_mismatch",
            f"{record.citation_path} has jurisdiction {record.jurisdiction}",
            scope=scope,
        )
    if record.document_class != scope.document_class:
        collector.add(
            "error",
            "provision_document_class_mismatch",
            f"{record.citation_path} has document_class {record.document_class}",
            scope=scope,
        )
    if record.version != scope.version:
        collector.add(
            "error",
            "provision_version_mismatch",
            f"{record.citation_path} has version {record.version}",
            scope=scope,
        )
    if not ((record.body and record.body.strip()) or (record.heading and record.heading.strip())):
        collector.add(
            "warning",
            "empty_provision_text",
            f"{record.citation_path} has neither body nor heading",
            scope=scope,
        )
    _reference_warn_unsectioned_document(record, by_path, scope, collector)
    if record.parent_citation_path:
        parent = by_path.get(record.parent_citation_path)
        # Supabase derives versioned parent UUIDs, so a citation found only in
        # another release scope cannot satisfy this scope's FK.
        if parent is None:
            collector.add(
                "error",
                "missing_parent_citation",
                f"{record.citation_path} parent not found: {record.parent_citation_path}",
                scope=scope,
            )
        elif (
            parent is not None and record.parent_id and parent.id and record.parent_id != parent.id
        ):
            collector.add(
                "error",
                "parent_id_mismatch",
                f"{record.citation_path} parent_id does not match parent record id",
                scope=scope,
            )
    if record.parent_citation_path and not record.parent_id:
        expected_parent_id = deterministic_provision_id(record.parent_citation_path)
        collector.add(
            "warning",
            "missing_parent_id",
            f"{record.citation_path} missing parent_id; deterministic value would be {expected_parent_id}",
            scope=scope,
        )
    _reference_validate_date(record.source_as_of, "source_as_of", record, scope, collector)
    _reference_validate_date(
        record.expression_date,
        "expression_date",
        record,
        scope,
        collector,
        required=require_expression_dates,
    )


def _reference_validate_date(
    value: str | None,
    field: str,
    record: ProvisionRecord,
    scope: ReleaseScope,
    collector: _ReferenceIssueCollector,
    *,
    required: bool = False,
) -> None:
    severity = "error" if required else "warning"
    if not value:
        collector.add(
            severity,
            f"missing_{field}",
            f"{record.citation_path} missing {field}",
            scope=scope,
        )
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        collector.add(
            severity,
            f"invalid_{field}",
            f"{record.citation_path} has non-ISO {field}: {value}",
            scope=scope,
        )


# --- src/axiom_corpus/release/manifest.py at cf46a725b ---


def _reference_load_provision_snapshot(
    path: Path,
    *,
    expected_sha256: str,
    expected_bytes: int,
    expected_rows: int,
) -> tuple[ProvisionRecord, ...]:
    """Parse the exact provision bytes already named by the artifact entry."""
    raw = path.read_bytes()
    if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ReleaseManifestError(
            f"provisions artifact changed while building release content: {path}"
        )
    records: list[ProvisionRecord] = []
    try:
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ReleaseManifestError(f"provisions artifact contains a non-object row: {path}")
            records.append(ProvisionRecord.from_mapping(value))
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ReleaseManifestError(f"cannot parse provisions artifact {path}: {exc}") from exc
    if len(records) != expected_rows:
        raise ReleaseManifestError(
            f"provisions artifact row count changed while building release content: {path}"
        )
    return tuple(records)


def _reference_validate_signed_source_references(
    repo_root: Path,
    *,
    base: str,
    scope_key: tuple[str, str, str],
    entries: Sequence[Mapping[str, Any]],
) -> None:
    """Require every record source to be an exact signed scope artifact."""
    jurisdiction, document_class, version = scope_key
    by_class: dict[str, list[Mapping[str, Any]]] = {
        artifact_class: [
            entry for entry in entries if entry.get("artifact_class") == artifact_class
        ]
        for artifact_class in _ARTIFACT_CLASSES
    }
    if len(by_class["inventory"]) != 1 or len(by_class["provisions"]) != 1:
        raise ReleaseManifestError(
            "release scope source-reference validation requires exact inventory and "
            f"provisions artifacts: {jurisdiction}/{document_class}/{version}"
        )

    inventory_path = canonical_corpus_artifact_file(
        repo_root,
        str(by_class["inventory"][0]["path"]),
    )
    provisions_path = canonical_corpus_artifact_file(
        repo_root,
        str(by_class["provisions"][0]["path"]),
    )
    try:
        inventory = _reference_load_source_inventory(inventory_path)
        provisions = _reference_load_provisions(provisions_path)
    except (
        AttributeError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise ReleaseManifestError(
            "cannot parse scope source references for "
            f"{jurisdiction}/{document_class}/{version}: {exc}"
        ) from exc

    source_entries = {
        str(entry["path"]): entry
        for entry in by_class["sources"]
        if isinstance(entry.get("path"), str)
    }
    inventory_source_paths: set[str] = set()
    for item in inventory:
        relative = _canonical_signed_source_reference(
            repo_root,
            base=base,
            scope_key=scope_key,
            source_path=item.source_path,
            owner=f"inventory item {item.citation_path}",
        )
        signed_entry = source_entries.get(relative)
        if signed_entry is None:
            raise ReleaseManifestError(
                f"inventory source reference is absent from signed artifacts: {relative}"
            )
        if not isinstance(item.sha256, str) or item.sha256 != signed_entry.get("sha256"):
            raise ReleaseManifestError(
                f"inventory source sha256 does not match signed artifact: {relative}"
            )
        inventory_source_paths.add(relative)

    for record in provisions:
        relative = _canonical_signed_source_reference(
            repo_root,
            base=base,
            scope_key=scope_key,
            source_path=record.source_path,
            owner=f"provision {record.citation_path}",
        )
        if relative not in source_entries:
            raise ReleaseManifestError(
                f"provision source reference is absent from signed artifacts: {relative}"
            )
        if relative not in inventory_source_paths:
            raise ReleaseManifestError(
                f"provision source reference is absent from scope inventory: {relative}"
            )


# --- src/axiom_corpus/release/publication.py at cf46a725b ---


def _reference_stage_one_artifact(client: Any, *, bucket: str, entry: _ArtifactEntry) -> _StagedArtifact:
    """Stage one artifact: snapshot, hash, conditional write, exact readback."""
    with _snapshot_file(entry.path) as (snapshot, actual_digest, actual_bytes):
        # Hash, size, and upload all refer to this one immutable snapshot.
        # In particular, the repository path is never reopened after the
        # digest has been computed.
        if actual_bytes != entry.size:
            raise ReleaseManifestError(
                f"local artifact byte count mismatch for {entry.path_value}: "
                f"expected {entry.size}, got {actual_bytes}"
            )
        if actual_digest != entry.sha256:
            raise ReleaseManifestError(
                f"local artifact sha256 mismatch for {entry.path_value}: "
                f"expected {entry.sha256}, got {actual_digest}"
            )

        remote = _reference_read_object_or_none(client, bucket=bucket, key=entry.key)
        if remote is None:
            was_uploaded = _reference_put_snapshot_if_absent(
                client,
                bucket=bucket,
                key=entry.key,
                snapshot=snapshot,
                filename=entry.path.name,
                sha256=entry.sha256,
                size=entry.size,
            )
        else:
            _reference_verify_bytes(remote, sha256=entry.sha256, size=entry.size, label=entry.key)
            was_uploaded = False

    # Always read after the upload decision. Metadata, ETags, and upload
    # return values are not evidence that R2 persisted the expected bytes.
    readback = _reference_read_object_or_none(client, bucket=bucket, key=entry.key)
    if readback is None:
        raise ReleaseManifestError(f"R2 readback is missing after staging: {entry.key}")
    _reference_verify_bytes(readback, sha256=entry.sha256, size=entry.size, label=entry.key)
    return _StagedArtifact(index=entry.index, key=entry.key, size=entry.size, uploaded=was_uploaded)


def _reference_put_snapshot_if_absent(
    client: Any,
    *,
    bucket: str,
    key: str,
    snapshot: SpooledTemporaryFile[bytes],
    filename: str,
    sha256: str,
    size: int,
) -> bool:
    request: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": snapshot,
        "ContentLength": size,
        "IfNoneMatch": "*",
        "Metadata": {"sha256": sha256},
    }
    content_type = mimetypes.guess_type(filename)[0]
    if content_type:
        request["ContentType"] = content_type

    for attempt in range(_MAX_CONDITIONAL_WRITE_ATTEMPTS):
        snapshot.seek(0)
        try:
            client.put_object(**request)
        except ClientError as exc:
            if not _is_conditional_write_conflict(exc):
                raise
            remote = _reference_read_object_or_none(client, bucket=bucket, key=key)
            if remote is not None:
                _reference_verify_bytes(remote, sha256=sha256, size=size, label=key)
                return False
            if attempt + 1 == _MAX_CONDITIONAL_WRITE_ATTEMPTS:
                raise ReleaseManifestError(
                    f"R2 conditional write conflict did not converge: {key}"
                ) from exc
            continue
        return True
    raise AssertionError("conditional write loop must return or raise")


def _reference_read_object_or_none(client: Any, *, bucket: str, key: str) -> bytes | None:
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    except KeyError:
        # Small in-memory clients used by unit tests model absence as KeyError.
        return None
    body = response.get("Body")
    if body is None:
        raise ReleaseManifestError(f"R2 returned no body for {key}")
    with closing(body):
        raw = body.read()
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if not isinstance(raw, bytes):
        raise ReleaseManifestError(f"R2 returned a non-byte body for {key}")
    return raw


def _reference_verify_bytes(payload: bytes, *, sha256: str, size: int, label: str) -> None:
    if len(payload) != size:
        raise ReleaseManifestError(
            f"R2 readback byte count mismatch for {label}: expected {size}, got {len(payload)}"
        )
    actual = hashlib.sha256(payload).hexdigest()
    if actual != sha256:
        raise ReleaseManifestError(
            f"R2 readback sha256 mismatch for {label}: expected {sha256}, got {actual}"
        )
