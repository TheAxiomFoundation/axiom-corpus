"""Verify immutable, Ed25519-signed corpus release objects."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    ReleaseManifestError,
    load_release_object,
    sha256_file,
)


def _verify_local_artifacts(payload: dict[str, object], repo_root: Path) -> list[str]:
    content = payload.get("content")
    if not isinstance(content, dict):
        return ["release object content is missing"]
    artifacts = content.get("artifacts")
    if not isinstance(artifacts, list):
        return ["release object artifacts are missing"]
    issues: list[str] = []
    root = repo_root.resolve()
    for raw in artifacts:
        if not isinstance(raw, dict):
            issues.append("release object contains a non-object artifact")
            continue
        relative = raw.get("path")
        if not isinstance(relative, str):
            issues.append("release artifact is missing its path")
            continue
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            issues.append(f"artifact escapes repository: {relative}")
            continue
        if not path.is_file():
            issues.append(f"artifact is missing: {relative}")
            continue
        actual = sha256_file(path)
        if actual != raw.get("sha256"):
            issues.append(f"artifact sha256 mismatch: {relative}")
        if path.stat().st_size != raw.get("bytes"):
            issues.append(f"artifact byte-count mismatch: {relative}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_object", type=Path)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args(argv)

    public_key = os.environ.get(RELEASE_OBJECT_PUBLIC_KEY_ENV, "")
    if not public_key:
        print(
            f"error: {RELEASE_OBJECT_PUBLIC_KEY_ENV} is required",
            file=sys.stderr,
        )
        return 2
    try:
        payload = load_release_object(args.release_object, public_key=public_key)
    except ReleaseManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    issues = _verify_local_artifacts(payload, args.repo_root) if args.repo_root is not None else []
    report = {
        "release": payload["release"],
        "content_sha256": payload["content_sha256"],
        "signature_verified": True,
        "local_content_checked": args.repo_root is not None,
        "ok": not issues,
        "issues": issues,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
