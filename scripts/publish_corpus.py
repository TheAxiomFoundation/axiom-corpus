#!/usr/bin/env python
"""Publish one explicit immutable named corpus release.

The only production publication sequence is:

1. Deep-validate the local named selector as a preflight.
2. Upload each artifact to its SHA-256 R2 key and hash the downloaded bytes.
3. Stage versioned Supabase provision and navigation rows without visibility.
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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.navigation import build_navigation_nodes
from axiom_corpus.corpus.navigation_supabase import write_navigation_nodes_to_supabase
from axiom_corpus.corpus.r2 import DEFAULT_R2_BUCKET, R2Config, load_r2_config
from axiom_corpus.corpus.release_quality import ReleaseValidationReport, validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, resolve_release_manifest_path
from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    DEFAULT_SERVICE_KEY_ENV,
    StagedScopeCounts,
    activate_corpus_release,
    fetch_staged_release_scope_counts,
    load_provisions_to_supabase,
    resolve_service_key,
)
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_PRIVATE_KEY_ENV,
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    ReleaseManifestError,
    build_release_content,
    build_unsigned_release_object,
    serialize_release_object,
    sign_release_object,
    verify_release_object,
)
from axiom_corpus.release.publication import (
    R2ReadbackReport,
    stage_release_artifacts,
    stage_signed_release_object,
)


@dataclass(frozen=True)
class PublicationReport:
    release: str
    content_sha256: str
    scope_count: int
    provision_rows: int
    r2_release_object_key: str
    activation: Mapping[str, object]
    release_object: Mapping[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "release": self.release,
            "content_sha256": self.content_sha256,
            "scope_count": self.scope_count,
            "provision_rows": self.provision_rows,
            "r2_release_object_key": self.r2_release_object_key,
            "activation": dict(self.activation),
            "release_object": dict(self.release_object),
        }


def publish_named_release(
    *,
    repo_root: Path,
    base: Path,
    selector_path: Path,
    supabase_url: str,
    service_key: str,
    r2_config: R2Config,
    private_key: str,
    public_key: str,
    chunk_size: int = 500,
    r2_client: Any | None = None,
) -> PublicationReport:
    """Execute the sole production publication boundary for one release."""
    root = repo_root.resolve()
    corpus_root = base.resolve()
    try:
        base_rel = corpus_root.relative_to(root).as_posix()
    except ValueError as exc:
        raise ReleaseManifestError("corpus base must be inside the repository") from exc
    release = ReleaseManifest.load(selector_path)

    # A cheap local gate runs before any external writes. The authoritative
    # validation attestation is generated again after remote readback/counting.
    preflight = validate_release(corpus_root, release, max_issues=200)
    _require_deep_validation(preflight, phase="preflight")

    provisional_content = build_release_content(
        root,
        release=release,
        validation={"passed": True, "phase": "preflight"},
        base=base_rel,
        bucket=r2_config.bucket,
    )
    expected_counts = _expected_scope_counts(provisional_content)

    r2_report = stage_release_artifacts(
        root,
        release_content=provisional_content,
        config=r2_config,
        client=r2_client,
    )

    staged_rows = 0
    for scope in release.scopes:
        provisions_path = (
            corpus_root
            / "provisions"
            / scope.jurisdiction
            / scope.document_class
            / f"{scope.version}.jsonl"
        )
        records = load_provisions(provisions_path)
        expected = expected_counts[scope.key]
        if len(records) != expected:
            raise ReleaseManifestError(
                f"local row count changed after hashing for {'/'.join(scope.key)}: "
                f"expected {expected}, got {len(records)}"
            )
        load_report = load_provisions_to_supabase(
            records,
            service_key=service_key,
            supabase_url=supabase_url,
            chunk_size=chunk_size,
            progress_stream=sys.stderr,
        )
        if load_report.rows_loaded != expected:
            raise ReleaseManifestError(
                f"Supabase staging wrote {load_report.rows_loaded} rows for "
                f"{'/'.join(scope.key)}; expected {expected}"
            )
        staged_rows += load_report.rows_loaded

        navigation = build_navigation_nodes(records)
        if len(navigation) != expected:
            raise ReleaseManifestError(
                f"local navigation projection has {len(navigation)} rows for "
                f"{'/'.join(scope.key)}; expected one per provision ({expected})"
            )
        navigation_report = write_navigation_nodes_to_supabase(
            navigation,
            service_key=service_key,
            supabase_url=supabase_url,
            chunk_size=chunk_size,
            replace_scope=True,
            replace_scopes=(scope.key,),
            progress_stream=sys.stderr,
        )
        if navigation_report.rows_loaded != len(navigation):
            raise ReleaseManifestError(
                f"navigation staging was incomplete for {'/'.join(scope.key)}"
            )

    actual_counts = fetch_staged_release_scope_counts(
        release,
        service_key=service_key,
        supabase_url=supabase_url,
    )
    _require_exact_counts(expected_counts, actual_counts)

    deep_report = validate_release(corpus_root, release, max_issues=200)
    _require_deep_validation(deep_report, phase="post-readback")
    validation = _validation_attestation(
        deep_report,
        r2_report=r2_report,
        expected_counts=expected_counts,
        actual_counts=actual_counts,
    )
    content = build_release_content(
        root,
        release=release,
        validation=validation,
        base=base_rel,
        bucket=r2_config.bucket,
    )
    if _artifact_identity(content) != _artifact_identity(provisional_content):
        raise ReleaseManifestError("release artifacts changed between readback and signing")

    unsigned = build_unsigned_release_object(content)
    signed = sign_release_object(unsigned, private_key=private_key)
    # Requiring the independently configured public key catches a wrong or
    # rotated private key before the object is uploaded or the pointer moves.
    verify_release_object(signed, public_key=public_key)
    release_key = stage_signed_release_object(
        signed,
        public_key=public_key,
        config=r2_config,
        client=r2_client,
    )

    activation = activate_corpus_release(
        signed,
        service_key=service_key,
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
        "provision_rows": sum(_expected_scope_counts(content).values()),
    }


def _expected_scope_counts(content: Mapping[str, Any]) -> dict[tuple[str, str, str], int]:
    raw_scopes = content.get("scopes")
    if not isinstance(raw_scopes, list):
        raise ReleaseManifestError("release content is missing scopes")
    counts: dict[tuple[str, str, str], int] = {}
    for raw in raw_scopes:
        if not isinstance(raw, dict):
            raise ReleaseManifestError("release content contains a non-object scope")
        key = (
            str(raw.get("jurisdiction") or ""),
            str(raw.get("document_class") or ""),
            str(raw.get("version") or ""),
        )
        rows = raw.get("provision_rows")
        if not all(key) or not isinstance(rows, int):
            raise ReleaseManifestError(f"invalid release scope count entry: {raw!r}")
        counts[key] = rows
    return counts


def _require_exact_counts(
    expected: Mapping[tuple[str, str, str], int],
    actual: Mapping[tuple[str, str, str], StagedScopeCounts],
) -> None:
    if set(expected) == set(actual) and all(
        actual[key].provision_rows == rows and actual[key].navigation_rows == rows
        for key, rows in expected.items()
    ):
        return
    differences = {
        "/".join(key): {
            "expected_provisions": expected.get(key),
            "actual_provisions": (actual[key].provision_rows if key in actual else None),
            "expected_navigation": expected.get(key),
            "actual_navigation": (actual[key].navigation_rows if key in actual else None),
        }
        for key in sorted(set(expected) | set(actual))
        if key not in expected
        or key not in actual
        or actual[key].provision_rows != expected[key]
        or actual[key].navigation_rows != expected[key]
    }
    raise ReleaseManifestError(
        "exact staged provision/navigation counts do not match: "
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
    r2_report: R2ReadbackReport,
    expected_counts: Mapping[tuple[str, str, str], int],
    actual_counts: Mapping[tuple[str, str, str], StagedScopeCounts],
) -> dict[str, Any]:
    return {
        "passed": True,
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
        "supabase_counts": [
            {
                "jurisdiction": key[0],
                "document_class": key[1],
                "version": key[2],
                "expected": expected_counts[key],
                "actual": actual_counts[key].provision_rows,
                "expected_navigation": expected_counts[key],
                "actual_navigation": actual_counts[key].navigation_rows,
            }
            for key in sorted(expected_counts)
        ],
    }


def _artifact_identity(content: Mapping[str, Any]) -> tuple[tuple[str, str, int], ...]:
    artifacts = content.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReleaseManifestError("release content has no artifact list")
    identity: list[tuple[str, str, int]] = []
    for raw in artifacts:
        if not isinstance(raw, dict):
            raise ReleaseManifestError("release content contains a non-object artifact")
        identity.append((str(raw["path"]), str(raw["sha256"]), int(raw["bytes"])))
    return tuple(identity)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ReleaseManifestError(f"required environment variable is not set: {name}")
    return value


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
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    base = (repo_root / args.base).resolve() if not args.base.is_absolute() else args.base.resolve()
    selector = resolve_release_manifest_path(args.release)
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
        report = publish_named_release(
            repo_root=repo_root,
            base=base,
            selector_path=selector,
            supabase_url=args.supabase_url,
            service_key=service_key,
            r2_config=r2_config,
            private_key=_required_env(RELEASE_OBJECT_PRIVATE_KEY_ENV),
            public_key=_required_env(RELEASE_OBJECT_PUBLIC_KEY_ENV),
            chunk_size=args.chunk_size,
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
