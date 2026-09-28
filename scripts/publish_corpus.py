#!/usr/bin/env python
"""Publish one explicit immutable named corpus release.

The only production publication sequence is:

1. Deep-validate the local named selector as a preflight.
2. Upload each artifact to its SHA-256 R2 key and hash the downloaded bytes.
3. Stage versioned Supabase provision and navigation rows without visibility.
   Staging verifies any pre-staged rows first: byte-identical rows are
   no-ops, stale derived identities converge to the canonical projection,
   and divergent content under an immutable key aborts before any write.
4. Read exact per-scope database counts and rerun deep validation.
5. Build, Ed25519-sign, upload, read back, and public-key-verify the release object.
6. Invoke one database RPC that rechecks counts, moves the production pointer,
   and refreshes derived current counts in a single transaction.

There is no mutable ``current`` selector, git-diff auto-publication, per-scope
activation, missing-parent synthesis, best-effort count check, or refresh
failure suppression.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.navigation import build_navigation_nodes
from axiom_corpus.corpus.navigation_supabase import write_navigation_nodes_to_supabase
from axiom_corpus.corpus.r2 import DEFAULT_R2_BUCKET, R2Config, load_r2_config
from axiom_corpus.corpus.release_quality import ReleaseValidationReport, validate_release
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    resolve_release_manifest_path,
)
from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    DEFAULT_SERVICE_KEY_ENV,
    ReleasedScopeObject,
    StagedScopeEvidence,
    activate_corpus_release,
    fetch_released_scope_objects,
    fetch_staged_release_scope_evidence,
    load_provisions_to_supabase,
    resolve_service_key,
)
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_PRIVATE_KEY_ENV,
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    ReleaseManifestError,
    ReleaseSignatureMismatchError,
    build_release_content,
    build_unsigned_release_object,
    canonical_json_bytes,
    canonical_release_public_key,
    serialize_release_object,
    sign_release_object,
    verify_release_object,
)
from axiom_corpus.release.publication import (
    DEFAULT_R2_STAGING_WORKERS,
    R2ReadbackReport,
    emit_progress,
    stage_release_artifacts,
    stage_signed_release_object,
)

RELEASE_OBJECT_LEGACY_PUBLIC_KEYS_ENV = "AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS"


@dataclass(frozen=True)
class PublicationReport:
    release: str
    content_sha256: str
    scope_count: int
    provision_rows: int
    r2_release_object_key: str
    activation: Mapping[str, object] | None
    release_object: Mapping[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "release": self.release,
            "content_sha256": self.content_sha256,
            "scope_count": self.scope_count,
            "provision_rows": self.provision_rows,
            "r2_release_object_key": self.r2_release_object_key,
            "activation": dict(self.activation) if self.activation is not None else None,
            "release_object": dict(self.release_object),
        }


@contextmanager
def _phase(
    stream: TextIO | None,
    name: str,
    **counts: object,
) -> Iterator[dict[str, object]]:
    """Emit flushed, timestamped start/end lines around one publication phase.

    The yielded dict collects end-of-phase counts. A failure inside the phase
    is logged with the phase name and elapsed time, then re-raised unchanged,
    so a killed or failed CI run shows exactly which phase it was in.
    """
    started = time.monotonic()
    emit_progress(stream, f"phase {name} start{_format_counts(counts)}")
    result: dict[str, object] = {}
    try:
        yield result
    except BaseException as exc:
        emit_progress(
            stream,
            f"phase {name} failed elapsed={time.monotonic() - started:.1f}s "
            f"error={type(exc).__name__}",
        )
        raise
    emit_progress(
        stream,
        f"phase {name} end elapsed={time.monotonic() - started:.1f}s{_format_counts(result)}",
    )


def _format_counts(counts: Mapping[str, object]) -> str:
    if not counts:
        return ""
    return "".join(f" {key}={value}" for key, value in counts.items())


def publish_named_release(
    *,
    repo_root: Path,
    base: Path,
    selector_path: Path,
    supabase_url: str,
    service_key: str,
    access_token: str,
    r2_config: R2Config,
    private_key: str,
    public_key: str,
    legacy_public_keys: Sequence[str] = (),
    chunk_size: int = 500,
    activate: bool = False,
    r2_client: Any | None = None,
    r2_workers: int = DEFAULT_R2_STAGING_WORKERS,
    progress_stream: TextIO | None = None,
) -> PublicationReport:
    """Execute the sole production publication boundary for one release.

    Publication stages content-addressed R2 artifacts and versioned Supabase
    rows, then signs and uploads the release object. It does NOT move serving by
    default: activation repoints the per-scope serving map and can displace
    another jurisdiction's release, so it is an explicit, separate decision (set
    ``activate=True`` here, or run ``scripts/activate_release.py`` — with
    ``--dry-run`` to preview the takeover — after publishing).

    ``r2_workers`` bounds the thread pool that stages and reads back R2
    objects; every object is still verified individually. ``progress_stream``
    receives one flushed, timestamped line at the start and end of every
    publication phase so a CI log shows where wall time goes.
    """
    if r2_workers < 1:
        raise ValueError("r2_workers must be positive")
    root = repo_root.resolve()
    corpus_root = base.resolve()
    public_key, legacy_public_keys = _trusted_release_public_keys(
        public_key,
        legacy_public_keys,
    )
    try:
        base_rel = corpus_root.relative_to(root).as_posix()
    except ValueError as exc:
        raise ReleaseManifestError("corpus base must be inside the repository") from exc
    release = ReleaseManifest.load(selector_path)
    _require_canonical_selector(root, selector_path, release)
    quality_profile = _require_publishable_quality_profile(release)
    publication_started = time.monotonic()
    emit_progress(
        progress_stream,
        f"publication start: release={release.name} scopes={len(release.scopes)} "
        f"r2_workers={r2_workers} chunk_size={chunk_size}",
    )

    # A cheap local gate runs before any external writes. The authoritative
    # validation attestation is generated again after remote readback/counting.
    with _phase(progress_stream, "preflight-deep-validation", scopes=len(release.scopes)) as done:
        preflight = validate_release(corpus_root, release, max_issues=200)
        _require_deep_validation(preflight, phase="preflight")
        done.update(errors=preflight.error_count, warnings=preflight.warning_count)

    with _phase(progress_stream, "release-content", scopes=len(release.scopes)) as done:
        provisional_content = build_release_content(
            root,
            release=release,
            validation={"passed": True, "phase": "preflight"},
            base=base_rel,
            bucket=r2_config.bucket,
        )
        expected_evidence = _expected_scope_evidence(provisional_content)
        done.update(
            artifacts=len(provisional_content["artifacts"]),
            bytes=sum(int(entry["bytes"]) for entry in provisional_content["artifacts"]),
            provision_rows=sum(item.provision_rows for item in expected_evidence.values()),
        )

    with _phase(
        progress_stream,
        "r2-staging",
        artifacts=len(provisional_content["artifacts"]),
        workers=r2_workers,
    ) as done:
        r2_report = stage_release_artifacts(
            root,
            release_content=provisional_content,
            config=r2_config,
            client=r2_client,
            workers=r2_workers,
            progress_stream=progress_stream,
        )
        done.update(
            verified=r2_report.artifact_count,
            bytes=r2_report.artifact_bytes,
            uploaded=r2_report.uploaded_count,
            reused=r2_report.reused_count,
        )

    with _phase(progress_stream, "released-scope-lookup", scopes=len(release.scopes)) as done:
        released_scopes = fetch_released_scope_objects(
            release,
            service_key=service_key,
            supabase_url=supabase_url,
        )
        _require_safe_released_scope_reuse(
            provisional_content,
            released_scopes,
            public_keys=(public_key, *legacy_public_keys),
        )
        done.update(
            released_scopes=sum(1 for objects in released_scopes.values() if objects),
            unreleased_scopes=sum(1 for objects in released_scopes.values() if not objects),
            prior_objects=len(
                {obj.release_name for objects in released_scopes.values() for obj in objects}
            ),
        )

    staged_rows = 0
    scopes_to_stage: list[tuple[Any, list[Any]]] = []
    release_records: list[Any] = []
    with _phase(progress_stream, "local-provision-load") as done:
        for scope in release.scopes:
            expected = expected_evidence[scope.key]
            if released_scopes[scope.key]:
                staged_rows += expected.provision_rows
                continue
            provisions_path = (
                corpus_root
                / "provisions"
                / scope.jurisdiction
                / scope.document_class
                / f"{scope.version}.jsonl"
            )
            records = load_provisions(provisions_path)
            if len(records) != expected.provision_rows:
                raise ReleaseManifestError(
                    f"local row count changed after hashing for {'/'.join(scope.key)}: "
                    f"expected {expected.provision_rows}, got {len(records)}"
                )
            scopes_to_stage.append((scope, records))
            release_records.extend(records)
        done.update(
            unreleased_scopes=len(scopes_to_stage),
            rows=len(release_records),
            reused_released_rows=staged_rows,
        )

    # One staging call covers every unreleased scope, so pre-staged rows whose
    # stale parent links cross scope boundaries within this release converge
    # together instead of tripping the cascade guard scope by scope.
    if scopes_to_stage:
        expected_release_rows = sum(
            expected_evidence[scope.key].provision_rows for scope, _ in scopes_to_stage
        )
        with _phase(
            progress_stream,
            "provision-staging",
            scopes=len(scopes_to_stage),
            rows=expected_release_rows,
            chunk_size=chunk_size,
        ) as done:
            load_report = load_provisions_to_supabase(
                release_records,
                service_key=service_key,
                supabase_url=supabase_url,
                chunk_size=chunk_size,
                progress_stream=progress_stream,
            )
            if load_report.rows_loaded != expected_release_rows:
                raise ReleaseManifestError(
                    f"Supabase staging wrote {load_report.rows_loaded} rows for "
                    f"{release.name}; expected {expected_release_rows}"
                )
            staged_rows += load_report.rows_loaded
            done.update(
                rows_loaded=load_report.rows_loaded,
                chunks=load_report.chunk_count,
                inserted=load_report.rows_inserted,
                replaced=load_report.rows_replaced,
                already_staged=load_report.rows_already_staged,
            )

    if scopes_to_stage:
        with _phase(
            progress_stream,
            "navigation-staging",
            scopes=len(scopes_to_stage),
            rows=sum(len(records) for _, records in scopes_to_stage),
        ) as done:
            navigation_rows_loaded = 0
            for scope, records in scopes_to_stage:
                expected = expected_evidence[scope.key]
                navigation = build_navigation_nodes(records)
                if len(navigation) != expected.navigation_rows:
                    raise ReleaseManifestError(
                        f"local navigation projection has {len(navigation)} rows for "
                        f"{'/'.join(scope.key)}; expected {expected.navigation_rows}"
                    )
                navigation_report = write_navigation_nodes_to_supabase(
                    navigation,
                    service_key=service_key,
                    supabase_url=supabase_url,
                    chunk_size=chunk_size,
                    replace_scope=True,
                    replace_scopes=(scope.key,),
                    progress_stream=progress_stream,
                )
                if navigation_report.rows_loaded != len(navigation):
                    raise ReleaseManifestError(
                        f"navigation staging was incomplete for {'/'.join(scope.key)}"
                    )
                navigation_rows_loaded += navigation_report.rows_loaded
            done.update(rows_loaded=navigation_rows_loaded)

    with _phase(progress_stream, "staged-evidence", scopes=len(release.scopes)) as done:
        actual_evidence = fetch_staged_release_scope_evidence(
            release,
            service_key=service_key,
            supabase_url=supabase_url,
        )
        _require_exact_evidence(expected_evidence, actual_evidence)
        done.update(
            scopes=len(actual_evidence),
            provision_rows=sum(item.provision_rows for item in actual_evidence.values()),
            navigation_rows=sum(item.navigation_rows for item in actual_evidence.values()),
        )

    with _phase(
        progress_stream, "post-readback-deep-validation", scopes=len(release.scopes)
    ) as done:
        deep_report = validate_release(corpus_root, release, max_issues=200)
        _require_deep_validation(deep_report, phase="post-readback")
        done.update(errors=deep_report.error_count, warnings=deep_report.warning_count)

    with _phase(progress_stream, "sign-release-object") as done:
        validation = _validation_attestation(
            deep_report,
            quality_profile=quality_profile,
            r2_report=r2_report,
            expected_evidence=expected_evidence,
            actual_evidence=actual_evidence,
        )
        content = build_release_content(
            root,
            release=release,
            validation=validation,
            base=base_rel,
            bucket=r2_config.bucket,
        )
        if _publication_identity(content) != _publication_identity(provisional_content):
            raise ReleaseManifestError("release artifacts changed between readback and signing")

        unsigned = build_unsigned_release_object(content)
        signed = sign_release_object(unsigned, private_key=private_key)
        # Requiring the independently configured public key catches a wrong or
        # rotated private key before the object is uploaded or the pointer moves.
        verify_release_object(signed, public_key=public_key)
        done.update(content_sha256=str(signed["content_sha256"]))

    with _phase(progress_stream, "release-object-upload") as done:
        release_key = stage_signed_release_object(
            signed,
            public_key=public_key,
            config=r2_config,
            client=r2_client,
        )
        done.update(key=release_key)
    emit_progress(
        progress_stream,
        f"publication end: release={release.name} content_sha256={signed['content_sha256']} "
        f"elapsed={time.monotonic() - publication_started:.1f}s",
    )

    activation: Mapping[str, object] | None = None
    if activate:
        activation = activate_corpus_release(
            signed,
            access_token=access_token,
            public_key=public_key,
            supabase_url=supabase_url,
        )
    return PublicationReport(
        release=release.name,
        content_sha256=str(signed["content_sha256"]),
        scope_count=len(release.scopes),
        provision_rows=staged_rows,
        r2_release_object_key=release_key,
        activation=activation,
        release_object=signed,
    )


def plan_named_release(
    *,
    repo_root: Path,
    base: Path,
    selector_path: Path,
    r2_bucket: str,
) -> dict[str, Any]:
    """Validate and print a no-write publication plan."""
    release = ReleaseManifest.load(selector_path)
    _require_canonical_selector(repo_root.resolve(), selector_path, release)
    _require_publishable_quality_profile(release)
    report = validate_release(base, release, max_issues=200)
    _require_deep_validation(report, phase="dry-run")
    base_rel = base.resolve().relative_to(repo_root.resolve()).as_posix()
    content = build_release_content(
        repo_root,
        release=release,
        validation={"passed": True, "phase": "dry-run"},
        base=base_rel,
        bucket=r2_bucket,
    )
    return {
        "dry_run": True,
        "release": release.name,
        "selector": str(selector_path),
        "scope_count": len(release.scopes),
        "artifact_count": len(content["artifacts"]),
        "provision_rows": sum(
            evidence.provision_rows for evidence in _expected_scope_evidence(content).values()
        ),
    }


def _expected_scope_evidence(
    content: Mapping[str, Any],
) -> dict[tuple[str, str, str], StagedScopeEvidence]:
    raw_scopes = content.get("scopes")
    if not isinstance(raw_scopes, list):
        raise ReleaseManifestError("release content is missing scopes")
    evidence: dict[tuple[str, str, str], StagedScopeEvidence] = {}
    for raw in raw_scopes:
        if not isinstance(raw, dict):
            raise ReleaseManifestError("release content contains a non-object scope")
        key = (
            str(raw.get("jurisdiction") or ""),
            str(raw.get("document_class") or ""),
            str(raw.get("version") or ""),
        )
        rows = raw.get("provision_rows")
        navigation_rows = raw.get("navigation_rows")
        provision_digest = raw.get("provision_projection_sha256")
        navigation_digest = raw.get("navigation_projection_sha256")
        if (
            not all(key)
            or key in evidence
            or not isinstance(rows, int)
            or isinstance(rows, bool)
            or not isinstance(navigation_rows, int)
            or isinstance(navigation_rows, bool)
            or not isinstance(provision_digest, str)
            or not isinstance(navigation_digest, str)
        ):
            raise ReleaseManifestError(f"invalid release scope evidence entry: {raw!r}")
        evidence[key] = StagedScopeEvidence(
            provision_rows=rows,
            navigation_rows=navigation_rows,
            provision_projection_sha256=provision_digest,
            navigation_projection_sha256=navigation_digest,
        )
    return evidence


def _require_exact_evidence(
    expected: Mapping[tuple[str, str, str], StagedScopeEvidence],
    actual: Mapping[tuple[str, str, str], StagedScopeEvidence],
) -> None:
    if set(expected) == set(actual) and all(
        actual[key] == value for key, value in expected.items()
    ):
        return
    differences = {
        "/".join(key): {
            "expected": (expected[key].__dict__ if key in expected else None),
            "actual_provisions": (actual[key].provision_rows if key in actual else None),
            "actual_navigation": (actual[key].navigation_rows if key in actual else None),
            "actual_provision_projection_sha256": (
                actual[key].provision_projection_sha256 if key in actual else None
            ),
            "actual_navigation_projection_sha256": (
                actual[key].navigation_projection_sha256 if key in actual else None
            ),
        }
        for key in sorted(set(expected) | set(actual))
        if key not in expected or key not in actual or actual[key] != expected[key]
    }
    raise ReleaseManifestError(
        "exact staged provision/navigation projection evidence does not match: "
        + json.dumps(differences, sort_keys=True)
    )


def _require_deep_validation(report: ReleaseValidationReport, *, phase: str) -> None:
    if report.ok:
        return
    raise ReleaseManifestError(
        f"deep release validation failed during {phase}: "
        + json.dumps(report.to_mapping(), sort_keys=True)
    )


def _validation_attestation(
    report: ReleaseValidationReport,
    *,
    quality_profile: str,
    r2_report: R2ReadbackReport,
    expected_evidence: Mapping[tuple[str, str, str], StagedScopeEvidence],
    actual_evidence: Mapping[tuple[str, str, str], StagedScopeEvidence],
) -> dict[str, Any]:
    return {
        "passed": True,
        "quality_profile": quality_profile,
        "deep_validation": {
            "error_count": report.error_count,
            "warning_count": report.warning_count,
            "scope_count": report.scope_count,
        },
        # Upload-vs-reuse is an operational detail that changes on a retry.
        # Only the deterministic readback evidence belongs in signed content.
        "r2_readback": {
            "bucket": r2_report.bucket,
            "artifact_count": r2_report.artifact_count,
            "artifact_bytes": r2_report.artifact_bytes,
            "verified_keys": list(r2_report.verified_keys),
        },
        "supabase_projection_evidence": [
            {
                "jurisdiction": key[0],
                "document_class": key[1],
                "version": key[2],
                "expected": expected_evidence[key].provision_rows,
                "actual": actual_evidence[key].provision_rows,
                "expected_navigation": expected_evidence[key].navigation_rows,
                "actual_navigation": actual_evidence[key].navigation_rows,
                "expected_provision_projection_sha256": (
                    expected_evidence[key].provision_projection_sha256
                ),
                "actual_provision_projection_sha256": (
                    actual_evidence[key].provision_projection_sha256
                ),
                "expected_navigation_projection_sha256": (
                    expected_evidence[key].navigation_projection_sha256
                ),
                "actual_navigation_projection_sha256": (
                    actual_evidence[key].navigation_projection_sha256
                ),
            }
            for key in sorted(expected_evidence)
        ],
    }


def _publication_identity(content: Mapping[str, Any]) -> bytes:
    artifacts = content.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReleaseManifestError("release content has no artifact list")
    scopes = content.get("scopes")
    if not isinstance(scopes, list):
        raise ReleaseManifestError("release content has no scope evidence")
    identity: list[dict[str, object]] = []
    for raw in artifacts:
        if not isinstance(raw, dict):
            raise ReleaseManifestError("release content contains a non-object artifact")
        identity.append(dict(raw))
    return canonical_json_bytes(
        {
            "quality_profile": content.get("quality_profile"),
            "scopes": scopes,
            "artifacts": identity,
        }
    )


def _require_safe_released_scope_reuse(
    content: Mapping[str, Any],
    released: Mapping[tuple[str, str, str], tuple[ReleasedScopeObject, ...]],
    *,
    public_keys: Sequence[str],
) -> None:
    trusted_keys = tuple(dict.fromkeys(public_keys))
    if not trusted_keys or any(not key for key in trusted_keys):
        raise ReleaseManifestError("prior release verification requires non-empty public keys")
    expected_keys = set(_expected_scope_evidence(content))
    if set(released) != expected_keys:
        raise ReleaseManifestError("released-scope lookup did not cover the requested scopes")
    for key, objects in released.items():
        expected_identity = _scope_publication_identity(content, key)
        for released_object in objects:
            if not _verifies_with_any_key(released_object.release_object, trusted_keys):
                raise ReleaseManifestError(
                    "database returned an untrusted prior release object for "
                    f"{'/'.join(key)}: {released_object.release_name}"
                )
            prior_content = released_object.release_object.get("content")
            if not isinstance(prior_content, dict):
                raise ReleaseManifestError("verified prior release object lacks content")
            if _scope_publication_identity(prior_content, key) != expected_identity:
                raise ReleaseManifestError(
                    "immutable released scope differs from the requested artifacts or "
                    f"database projection: {'/'.join(key)} "
                    f"({released_object.release_name})"
                )


def _verifies_with_any_key(
    release_object: Mapping[str, Any],
    public_keys: Sequence[str],
) -> bool:
    for public_key in public_keys:
        try:
            verify_release_object(release_object, public_key=public_key)
        except ReleaseSignatureMismatchError:
            continue
        return True
    return False


def _scope_publication_identity(
    content: Mapping[str, Any],
    key: tuple[str, str, str],
) -> bytes:
    raw_scopes = content.get("scopes")
    raw_artifacts = content.get("artifacts")
    if not isinstance(raw_scopes, list) or not isinstance(raw_artifacts, list):
        raise ReleaseManifestError("release content lacks scope or artifact inventory")
    matches = [
        raw
        for raw in raw_scopes
        if isinstance(raw, dict)
        and tuple(
            str(raw.get(field) or "") for field in ("jurisdiction", "document_class", "version")
        )
        == key
    ]
    if len(matches) != 1:
        raise ReleaseManifestError(f"release content does not contain scope {'/'.join(key)}")
    jurisdiction, document_class, version = key
    exact_paths = {
        f"data/corpus/inventory/{jurisdiction}/{document_class}/{version}.json",
        f"data/corpus/provisions/{jurisdiction}/{document_class}/{version}.jsonl",
        f"data/corpus/coverage/{jurisdiction}/{document_class}/{version}.json",
    }
    source_prefix = f"data/corpus/sources/{jurisdiction}/{document_class}/{version}/"
    artifacts = [
        dict(raw)
        for raw in raw_artifacts
        if isinstance(raw, dict)
        and (
            str(raw.get("path") or "") in exact_paths
            or str(raw.get("path") or "").startswith(source_prefix)
        )
    ]
    if len(artifacts) < 4 or exact_paths - {str(raw.get("path")) for raw in artifacts}:
        raise ReleaseManifestError(f"release content lacks artifacts for scope {'/'.join(key)}")
    return canonical_json_bytes(
        {
            "scope": matches[0],
            "artifacts": sorted(artifacts, key=lambda raw: str(raw["path"])),
        }
    )


def _require_canonical_selector(
    repo_root: Path,
    selector_path: Path,
    release: ReleaseManifest,
) -> None:
    expected = repo_root / "manifests" / "releases" / f"{release.name}.json"
    try:
        supplied = selector_path.resolve(strict=True)
        canonical = expected.resolve(strict=True)
    except OSError as exc:
        raise ReleaseManifestError("release selector must be a tracked canonical file") from exc
    if supplied != canonical or canonical != expected:
        raise ReleaseManifestError(
            "release selector must be the exact non-symlink path "
            f"manifests/releases/{release.name}.json"
        )


def _require_publishable_quality_profile(release: ReleaseManifest) -> str:
    if release.quality_profile != COMPLETE_EXPRESSION_DATES_PROFILE:
        raise ReleaseManifestError(
            f"release publication requires quality_profile {COMPLETE_EXPRESSION_DATES_PROFILE!r}"
        )
    return release.quality_profile


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ReleaseManifestError(f"required environment variable is not set: {name}")
    return value


def _legacy_public_keys_from_env() -> tuple[str, ...]:
    raw = os.environ.get(RELEASE_OBJECT_LEGACY_PUBLIC_KEYS_ENV, "")
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReleaseManifestError(
            f"{RELEASE_OBJECT_LEGACY_PUBLIC_KEYS_ENV} must be a JSON array of public keys"
        ) from exc
    if (
        not isinstance(payload, list)
        or any(not isinstance(key, str) or not key for key in payload)
        or len(set(payload)) != len(payload)
    ):
        raise ReleaseManifestError(
            f"{RELEASE_OBJECT_LEGACY_PUBLIC_KEYS_ENV} must be a unique JSON array "
            "of non-empty public keys"
        )
    return tuple(payload)


def _trusted_release_public_keys(
    current_public_key: str,
    legacy_public_keys: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    current = canonical_release_public_key(current_public_key)
    legacy = tuple(canonical_release_public_key(key) for key in legacy_public_keys)
    if current in legacy:
        raise ReleaseManifestError("current release public key must not be a legacy key")
    if len(set(legacy)) != len(legacy):
        raise ReleaseManifestError("legacy release public keys must be canonically unique")
    return current, legacy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release",
        required=True,
        help="Immutable named release selector name or explicit JSON path.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--supabase-url", default=DEFAULT_AXIOM_SUPABASE_URL)
    parser.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    parser.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--r2-bucket")
    parser.add_argument("--r2-endpoint")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument(
        "--r2-workers",
        type=int,
        default=DEFAULT_R2_STAGING_WORKERS,
        help=(
            "Bounded thread-pool size for content-addressed R2 upload and exact "
            "readback. Every object is still hashed and verified individually; "
            "this only changes how many are in flight."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--activate",
        action="store_true",
        help=(
            "Also move serving to this release after publishing. Off by default: "
            "activation repoints the per-scope serving map and can displace another "
            "jurisdiction's release, so it is a separate explicit step. Prefer "
            "scripts/activate_release.py (with --dry-run to preview the takeover)."
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.r2_workers < 1:
        parser.error("--r2-workers must be at least 1")
    repo_root = args.repo_root.resolve()
    base = (repo_root / args.base).resolve() if not args.base.is_absolute() else args.base.resolve()
    selector = resolve_release_manifest_path(args.release)
    if not selector.is_absolute():
        selector = repo_root / selector
    if args.dry_run:
        payload = plan_named_release(
            repo_root=repo_root,
            base=base,
            selector_path=selector,
            r2_bucket=args.r2_bucket or os.environ.get("R2_BUCKET") or DEFAULT_R2_BUCKET,
        )
    else:
        r2_config = load_r2_config(
            credential_path=args.credentials_file,
            bucket=args.r2_bucket,
            endpoint_url=args.r2_endpoint,
        )
        service_key = resolve_service_key(
            args.supabase_url,
            service_key_env=args.service_key_env,
            access_token_env=args.access_token_env,
        )
        access_token = _required_env(args.access_token_env)
        report = publish_named_release(
            repo_root=repo_root,
            base=base,
            selector_path=selector,
            supabase_url=args.supabase_url,
            service_key=service_key,
            access_token=access_token,
            r2_config=r2_config,
            private_key=_required_env(RELEASE_OBJECT_PRIVATE_KEY_ENV),
            public_key=_required_env(RELEASE_OBJECT_PUBLIC_KEY_ENV),
            legacy_public_keys=_legacy_public_keys_from_env(),
            chunk_size=args.chunk_size,
            activate=args.activate,
            r2_workers=args.r2_workers,
            progress_stream=sys.stderr,
        )
        payload = report.to_mapping()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(
            serialize_release_object(payload["release_object"])
            if "release_object" in payload
            else (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
