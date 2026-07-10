"""Release validation gates for source-first corpus artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.document_sections import split_document_body
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.r2 import ArtifactReport, _sha256_file
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.supabase import deterministic_provision_id


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
        _validate_scope(store, scope, collector)
    return ReleaseValidationReport(
        release_name=release.name,
        scope_count=len(release.scopes),
        error_count=collector.error_count,
        warning_count=collector.warning_count,
        issues=tuple(collector.issues),
        max_issues=max_issues,
        strict_warnings=strict_warnings,
    )


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
) -> tuple[SourceInventoryItem, ...] | None:
    if not path.exists():
        collector.add(
            "error", "missing_inventory", "inventory artifact is missing", scope=scope, path=path
        )
        return None
    try:
        return load_source_inventory(path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        collector.add("error", "invalid_inventory", str(exc), scope=scope, path=path)
        return None


def _load_provisions_for_validation(
    path: Path,
    scope: ReleaseScope,
    collector: _IssueCollector,
) -> tuple[ProvisionRecord, ...] | None:
    if not path.exists():
        collector.add(
            "error", "missing_provisions", "provisions artifact is missing", scope=scope, path=path
        )
        return None
    try:
        return load_provisions(path)
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
    inventory: tuple[SourceInventoryItem, ...],
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
    provisions: tuple[ProvisionRecord, ...],
    inventory_source_paths: set[str],
    scope: ReleaseScope,
    collector: _IssueCollector,
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
        _validate_provision_record(record, by_path, scope, collector)


def _warn_unsectioned_document(
    record: ProvisionRecord,
    by_path: dict[str, ProvisionRecord],
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


def _validate_provision_record(
    record: ProvisionRecord,
    by_path: dict[str, ProvisionRecord],
    scope: ReleaseScope,
    collector: _IssueCollector,
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
    _warn_unsectioned_document(record, by_path, scope, collector)
    if record.parent_citation_path:
        parent = by_path.get(record.parent_citation_path)
        if parent is None:
            collector.add(
                "error",
                "missing_parent_citation",
                f"{record.citation_path} parent not found: {record.parent_citation_path}",
                scope=scope,
            )
        elif record.parent_id and parent.id and record.parent_id != parent.id:
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
    _validate_date(record.expression_date, "expression_date", record, scope, collector)


def _validate_date(
    value: str | None,
    field: str,
    record: ProvisionRecord,
    scope: ReleaseScope,
    collector: _IssueCollector,
) -> None:
    if not value:
        collector.add(
            "warning",
            f"missing_{field}",
            f"{record.citation_path} missing {field}",
            scope=scope,
        )
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        collector.add(
            "warning",
            f"invalid_{field}",
            f"{record.citation_path} has non-ISO {field}: {value}",
            scope=scope,
        )
