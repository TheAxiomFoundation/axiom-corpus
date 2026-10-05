"""Release validation gates for source-first corpus artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.document_sections import split_document_body
from axiom_corpus.corpus.io import (
    SourceInventoryReference,
    iter_provisions,
    load_source_inventory_references,
)
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord
from axiom_corpus.corpus.r2 import ArtifactReport, _sha256_file
from axiom_corpus.corpus.releases import (
    LAYER_BASE,
    LAYER_PRIMARY,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id
from axiom_corpus.release.manifest import selector_sha256

_PROFILED_CITATION_UNIQUENESS_GRANDFATHER = {
    "us-rulespec-2026-07-19": "79c091b4501eecb2996936ba51c87955f89460d9e3690b0fde88c30742547e9d"
}


@dataclass(frozen=True)
class ReleaseValidationIssue:
    severity: str
    code: str
    message: str
    jurisdiction: str | None = None
    document_class: str | None = None
    version: str | None = None
    path: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.jurisdiction is not None:
            payload["jurisdiction"] = self.jurisdiction
        if self.document_class is not None:
            payload["document_class"] = self.document_class
        if self.version is not None:
            payload["version"] = self.version
        if self.path is not None:
            payload["path"] = self.path
        return payload


@dataclass(frozen=True)
class ReleaseValidationReport:
    release_name: str
    scope_count: int
    error_count: int
    warning_count: int
    issues: tuple[ReleaseValidationIssue, ...]
    max_issues: int
    strict_warnings: bool = False

    @property
    def ok(self) -> bool:
        return self.error_count == 0 and (not self.strict_warnings or self.warning_count == 0)

    @property
    def truncated(self) -> bool:
        return self.error_count + self.warning_count > len(self.issues)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "release": self.release_name,
            "scope_count": self.scope_count,
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "strict_warnings": self.strict_warnings,
            "issue_count": self.error_count + self.warning_count,
            "issues_returned": len(self.issues),
            "issues_truncated": self.truncated,
            "issues": [issue.to_mapping() for issue in self.issues],
        }


class _IssueCollector:
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


def validate_release(
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
    collector = _IssueCollector(max_issues=max_issues)
    artifact_rows = {}
    if artifact_report is not None:
        _validate_artifact_report(
            artifact_report,
            collector,
            ignore_r2_missing=ignore_r2_missing,
        )
        artifact_rows = {
            (row.jurisdiction, row.document_class, row.version): row for row in artifact_report.rows
        }
    uniqueness_grandfathered = _citation_uniqueness_grandfathered(release)
    require_unique_citations = (
        release.requires_complete_expression_dates and not uniqueness_grandfathered
    )
    if release.requires_complete_expression_dates and uniqueness_grandfathered:
        collector.add(
            "warning",
            "legacy_release_citation_uniqueness_grandfathered",
            "known historical release predates release-wide citation uniqueness enforcement",
        )
    release_citation_paths = _release_citation_paths(
        store,
        release,
        artifact_rows,
        collector,
        require_unique=require_unique_citations,
    )
    for scope in release.scopes:
        if _scope_has_remote_artifacts(scope, artifact_rows):
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
        _validate_scope(
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


def _citation_uniqueness_grandfathered(release: ReleaseManifest) -> bool:
    expected = _PROFILED_CITATION_UNIQUENESS_GRANDFATHER.get(release.name)
    return expected is not None and selector_sha256(release) == expected


def _release_citation_paths(
    store: CorpusArtifactStore,
    release: ReleaseManifest,
    artifact_rows: Mapping[tuple[str, str, str], Any],
    collector: _IssueCollector,
    *,
    require_unique: bool,
) -> set[str]:
    """Collect parents available anywhere in the local release cut.

    A release may deliberately split a legal hierarchy across source snapshots.
    Parent integrity is therefore a release-wide invariant, not a scope-local one.
    Parsing errors remain owned by ``_validate_scope`` so they are reported once.

    Citation uniqueness is per layer: a base scope may carry a path a primary
    scope also carries (serving picks the primary row), but two scopes of the
    same layer may not, and the overlap must stay inside one
    (jurisdiction, document_class) pair because serving resolves precedence
    per pair. The returned path set is the union of both layers.
    """
    paths: set[str] = set()
    owners = _LayeredCitationOwners()
    for scope in release.scopes:
        if _scope_has_remote_artifacts(scope, artifact_rows):
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
            citation_paths = [record.citation_path for record in iter_provisions(path)]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        for citation_path in citation_paths:
            conflict = owners.claim(citation_path, scope)
            if require_unique and conflict is not None:
                code, message = conflict
                collector.add("error", code, message, scope=scope, path=path)
            paths.add(citation_path)
    return paths


class _LayeredCitationOwners:
    """Track which release scope owns each citation path in each layer."""

    def __init__(self) -> None:
        # One map per layer, keyed by the path itself: a release's citation
        # set is held once per layer, without a tuple per path.
        self._owners: dict[str, dict[str, ReleaseScope]] = {
            LAYER_BASE: {},
            LAYER_PRIMARY: {},
        }

    def claim(self, citation_path: str, scope: ReleaseScope) -> tuple[str, str] | None:
        """Record ``scope`` as an owner of ``citation_path``; return any conflict.

        Duplicates inside one scope are reported by ``_validate_provisions``.
        """
        owners = self._owners[scope.layer]
        owner = owners.get(citation_path)
        if owner is not None and owner != scope:
            return (
                "duplicate_release_citation",
                (
                    f"citation_path {citation_path} is also present in "
                    f"{owner.jurisdiction}/{owner.document_class}/{owner.version}"
                ),
            )
        owners.setdefault(citation_path, scope)
        other_layer = LAYER_PRIMARY if scope.is_base else LAYER_BASE
        other = self._owners[other_layer].get(citation_path)
        if other is not None and other.pair != scope.pair:
            return (
                "layered_citation_outside_pair",
                (
                    f"citation_path {citation_path} is carried by {scope.layer} scope "
                    f"{scope.jurisdiction}/{scope.document_class}/{scope.version} and "
                    f"{other.layer} scope "
                    f"{other.jurisdiction}/{other.document_class}/{other.version}; "
                    "a base row can only be shadowed by a primary row of its own "
                    "jurisdiction and document class"
                ),
            )
        return None


class _ProvisionFacts(NamedTuple):
    """What the scope checks read from one provision record.

    Each field holds the record's value unchanged, except that the body, which
    is most of a record's bytes, is kept only as the two facts the checks read
    from it, and the heading only where the body has no text (the one place a
    check reads it). Validation therefore holds compact per-row metadata
    rather than every provision body, and reports exactly what it did with the
    full records.
    """

    citation_path: str
    id: str | None
    jurisdiction: str
    document_class: str
    version: str | None
    source_path: str | None
    parent_citation_path: str | None
    parent_id: str | None
    source_as_of: str | None
    expression_date: str | None
    has_body_text: bool
    heading: str | None
    # A "document" record whose body splits on its own top-level section
    # markers; the unsectioned-document warning applies only to these.
    sectioned_document: bool


def _provision_facts(record: ProvisionRecord, shared: dict[object, object]) -> _ProvisionFacts:
    body = record.body
    has_body_text = bool(body and body.strip())
    return _ProvisionFacts(
        citation_path=record.citation_path,
        id=record.id,
        jurisdiction=_shared(record.jurisdiction, shared),
        document_class=_shared(record.document_class, shared),
        version=_shared(record.version, shared),
        source_path=_shared(record.source_path, shared),
        parent_citation_path=record.parent_citation_path,
        parent_id=record.parent_id,
        source_as_of=_shared(record.source_as_of, shared),
        expression_date=_shared(record.expression_date, shared),
        has_body_text=has_body_text,
        heading=None if has_body_text else record.heading,
        sectioned_document=_sectioned_document(record),
    )


def _sectioned_document(record: ProvisionRecord | _ProvisionFacts) -> bool:
    """Whether a document record's body splits on its own section markers."""
    if isinstance(record, _ProvisionFacts):
        return record.sectioned_document
    body = record.body
    return record.kind == "document" and bool(body) and split_document_body(body or "") is not None


def _shared[T](value: T, shared: dict[object, object]) -> T:
    # Every row of a scope repeats a few jurisdiction, class, version, source
    # and date strings; one object per value keeps the facts compact.
    if type(value) is str:
        return shared.setdefault(value, value)  # type: ignore[return-value]
    return value


def _validate_artifact_report(
    artifact_report: ArtifactReport,
    collector: _IssueCollector,
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


def _scope_has_remote_artifacts(
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


def _validate_scope(
    store: CorpusArtifactStore,
    scope: ReleaseScope,
    collector: _IssueCollector,
    release_citation_paths: set[str],
    *,
    require_expression_dates: bool,
) -> None:
    inventory_path = store.inventory_path(scope.jurisdiction, scope.document_class, scope.version)
    provisions_path = store.provisions_path(scope.jurisdiction, scope.document_class, scope.version)
    coverage_path = store.coverage_path(scope.jurisdiction, scope.document_class, scope.version)
    inventory = _load_inventory_for_validation(inventory_path, scope, collector)
    provisions = _load_provisions_for_validation(provisions_path, scope, collector)
    coverage = _load_coverage_for_validation(coverage_path, scope, collector)
    if inventory is None or provisions is None:
        return
    inventory_source_paths = _validate_inventory(store.root, inventory, scope, collector)
    _validate_provisions(
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


def _load_inventory_for_validation(
    path: Path,
    scope: ReleaseScope,
    collector: _IssueCollector,
) -> tuple[SourceInventoryReference, ...] | None:
    if not path.exists():
        collector.add(
            "error", "missing_inventory", "inventory artifact is missing", scope=scope, path=path
        )
        return None
    try:
        return load_source_inventory_references(path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        collector.add("error", "invalid_inventory", str(exc), scope=scope, path=path)
        return None


def _load_provisions_for_validation(
    path: Path,
    scope: ReleaseScope,
    collector: _IssueCollector,
) -> tuple[_ProvisionFacts, ...] | None:
    if not path.exists():
        collector.add(
            "error", "missing_provisions", "provisions artifact is missing", scope=scope, path=path
        )
        return None
    try:
        shared: dict[object, object] = {}
        return tuple(_provision_facts(record, shared) for record in iter_provisions(path))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        collector.add("error", "invalid_provisions", str(exc), scope=scope, path=path)
        return None


def _load_coverage_for_validation(
    path: Path,
    scope: ReleaseScope,
    collector: _IssueCollector,
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


def _validate_inventory(
    root: Path,
    inventory: tuple[SourceInventoryReference, ...],
    scope: ReleaseScope,
    collector: _IssueCollector,
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
        validated = _validate_source_file(
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


def _validate_source_file(
    root: Path,
    source_path: object,
    scope: ReleaseScope,
    collector: _IssueCollector,
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


def _validate_provisions(
    root: Path,
    provisions: tuple[_ProvisionFacts, ...],
    inventory_source_paths: set[str],
    scope: ReleaseScope,
    collector: _IssueCollector,
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
    by_path: dict[str, _ProvisionFacts] = {}
    by_id: dict[str, _ProvisionFacts] = {}
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
            _validate_source_file(
                root,
                record.source_path,
                scope,
                collector,
                reference_kind="provision",
                citation_path=record.citation_path,
            )
        elif record.source_path not in checked_source_paths:
            checked_source_paths.add(record.source_path)
            validated = _validate_source_file(
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
        _validate_provision_record(
            record,
            by_path,
            scope,
            collector,
            release_citation_paths or set(by_path),
            require_expression_dates=require_expression_dates,
        )


def _warn_unsectioned_document(
    record: ProvisionRecord | _ProvisionFacts,
    by_path: Mapping[str, object],
    scope: ReleaseScope,
    collector: _IssueCollector,
) -> None:
    """Warn when a document-level body carries printed section markers
    (Part/Step/Schedule) but the document has no child provisions at
    all — the app then has no child nodes to navigate into. Fix with
    ``section-provisions``. Any existing children (marker sections,
    per-capture form variants, /values supplements) already make the
    document navigable, so they silence the warning.
    """
    if not _sectioned_document(record):
        return
    prefix = record.citation_path + "/"
    if any(path.startswith(prefix) for path in by_path):
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


def _validate_provision_record(
    record: _ProvisionFacts,
    by_path: dict[str, _ProvisionFacts],
    scope: ReleaseScope,
    collector: _IssueCollector,
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
    if not (record.has_body_text or (record.heading and record.heading.strip())):
        collector.add(
            "warning",
            "empty_provision_text",
            f"{record.citation_path} has neither body nor heading",
            scope=scope,
        )
    _warn_unsectioned_document(record, by_path, scope, collector)
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
    _validate_date(record.source_as_of, "source_as_of", record, scope, collector)
    _validate_date(
        record.expression_date,
        "expression_date",
        record,
        scope,
        collector,
        required=require_expression_dates,
    )


def _validate_date(
    value: str | None,
    field: str,
    record: _ProvisionFacts,
    scope: ReleaseScope,
    collector: _IssueCollector,
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
