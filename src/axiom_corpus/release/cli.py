"""CLI for emitting and verifying corpus release manifests.

Commands
--------
``emit-release-manifest``
    Build (and, when a signing key is present, sign) a release manifest for the
    current corpus state and write it to ``--out``.

``verify-release-manifest``
    Recompute artifact hashes/row counts for ``--manifest`` against the tree at
    ``--repo-root`` and verify the HMAC signature.

Both are exposed as the ``axiom-corpus-release`` console script and via the
``scripts/release_manifest.py`` wrapper. This module is intentionally separate
from ``axiom_corpus.corpus.cli`` so the release surface stays additive.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .manifest import (
    DEFAULT_R2_BUCKET,
    RELEASE_MANIFEST_SIGNING_KEY_ENV,
    ReleaseManifestError,
    build_release_manifest,
    jsonl_row_count,
    manifest_signature_issue,
    serialize_manifest,
    sha256_file,
    sign_manifest,
)


def _signing_key() -> str | None:
    key = os.environ.get(RELEASE_MANIFEST_SIGNING_KEY_ENV, "")
    return key or None


def _default_repo_root() -> Path:
    # ``src/axiom_corpus/release/cli.py`` -> repo root is three parents up from
    # the package directory.
    return Path(__file__).resolve().parents[3]


def cmd_emit(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    try:
        manifest = build_release_manifest(
            repo_root,
            release=args.release,
            base=args.base,
            bucket=args.bucket,
            created_at=args.created_at,
        )
    except ReleaseManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    signing_key = _signing_key()
    signed = False
    if signing_key:
        manifest = sign_manifest(manifest, signing_key)
        signed = True

    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(serialize_manifest(manifest))

    totals = manifest["summary"]["totals"]
    report = {
        "manifest": str(out_path),
        "release": args.release,
        "signed": signed,
        "signing_key_env": RELEASE_MANIFEST_SIGNING_KEY_ENV,
        "files": totals["files"],
        "bytes": totals["bytes"],
        "provision_rows": manifest["summary"]
        .get("provisions", {})
        .get("rows", 0),
        "created_at": manifest["created_at"],
        "git_commit": manifest.get("git", {}).get("commit"),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not signed:
        print(
            f"note: {RELEASE_MANIFEST_SIGNING_KEY_ENV} not set; wrote unsigned "
            "manifest (hashes are still authoritative).",
            file=sys.stderr,
        )
    return 0


def _rehash_issues(
    manifest: dict[str, Any],
    repo_root: Path,
) -> list[str]:
    """Recompute recorded hashes/rows against disk and return mismatches."""
    issues: list[str] = []

    def _check_entry(entry: dict[str, Any]) -> None:
        rel = entry.get("path")
        if not isinstance(rel, str):
            issues.append(f"artifact entry missing path: {entry!r}")
            return
        path = repo_root / rel
        if not path.is_file():
            issues.append(f"missing on disk: {rel}")
            return
        actual_sha = sha256_file(path)
        if actual_sha != entry.get("sha256"):
            issues.append(
                f"sha256 mismatch: {rel} "
                f"(manifest={entry.get('sha256')}, disk={actual_sha})"
            )
        expected_bytes = entry.get("bytes")
        actual_bytes = path.stat().st_size
        if expected_bytes is not None and actual_bytes != expected_bytes:
            issues.append(
                f"byte-length mismatch: {rel} "
                f"(manifest={expected_bytes}, disk={actual_bytes})"
            )
        if "rows" in entry:
            actual_rows = jsonl_row_count(path)
            if actual_rows != entry.get("rows"):
                issues.append(
                    f"row-count mismatch: {rel} "
                    f"(manifest={entry.get('rows')}, disk={actual_rows})"
                )

    for entries in manifest.get("artifacts", {}).values():
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    _check_entry(entry)

    for rel, meta in manifest.get("documents", {}).items():
        if isinstance(meta, dict):
            _check_entry({"path": rel, **meta})

    return issues


def cmd_verify(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read manifest {manifest_path}: {exc}", file=sys.stderr)
        return 2

    problems: list[str] = []

    signing_key = _signing_key()
    if signing_key:
        signature_issue = manifest_signature_issue(manifest, signing_key)
        if signature_issue:
            problems.append(f"signature {signature_issue}")
    elif args.require_signature:
        problems.append(
            f"{RELEASE_MANIFEST_SIGNING_KEY_ENV} is required to verify the "
            "signature but is not set"
        )

    if not args.signature_only:
        problems.extend(_rehash_issues(manifest, args.repo_root.resolve()))

    report = {
        "manifest": str(manifest_path),
        "release": manifest.get("release"),
        "signature_checked": bool(signing_key),
        "content_checked": not args.signature_only,
        "ok": not problems,
        "problems": problems,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not problems else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="axiom-corpus-release",
        description="Emit and verify signed corpus release manifests.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    default_root = _default_repo_root()

    emit = sub.add_parser(
        "emit-release-manifest",
        help="Emit a release manifest for the current corpus state.",
    )
    emit.add_argument("--release", default="r0", help="Release id (default: r0).")
    emit.add_argument(
        "--base",
        default="data/corpus",
        help="Corpus base directory, repo-relative (default: data/corpus).",
    )
    emit.add_argument(
        "--out",
        type=Path,
        default=Path("releases/r0/release_manifest.json"),
        help="Output manifest path (default: releases/r0/release_manifest.json).",
    )
    emit.add_argument(
        "--repo-root",
        type=Path,
        default=default_root,
        help="Repository root containing data/corpus (default: inferred).",
    )
    emit.add_argument(
        "--bucket",
        default=DEFAULT_R2_BUCKET,
        help=f"R2 bucket for declared keys (default: {DEFAULT_R2_BUCKET}).",
    )
    emit.add_argument(
        "--created-at",
        default=None,
        help="Override created_at (default: HEAD committer time, UTC).",
    )
    emit.set_defaults(func=cmd_emit)

    verify = sub.add_parser(
        "verify-release-manifest",
        help="Verify a release manifest against the tree and its signature.",
    )
    verify.add_argument(
        "--manifest",
        type=Path,
        default=Path("releases/r0/release_manifest.json"),
        help="Manifest to verify (default: releases/r0/release_manifest.json).",
    )
    verify.add_argument(
        "--repo-root",
        type=Path,
        default=default_root,
        help="Repository root to rehash artifacts against (default: inferred).",
    )
    verify.add_argument(
        "--signature-only",
        action="store_true",
        help="Only verify the signature; skip rehashing artifacts.",
    )
    verify.add_argument(
        "--require-signature",
        action="store_true",
        help=(
            "Fail if the signing key is absent instead of skipping the "
            "signature check."
        ),
    )
    verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
