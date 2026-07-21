#!/usr/bin/env python3
"""Bind release inventory entries to their committed source snapshot bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from axiom_corpus.corpus.releases import ReleaseManifest


def _source_file(
    base: Path,
    *,
    jurisdiction: str,
    document_class: str,
    version: str,
    source_path: object,
) -> Path:
    if not isinstance(source_path, str) or not source_path:
        raise ValueError(f"{jurisdiction}/{document_class}/{version} has no source_path")
    relative = PurePosixPath(source_path)
    expected = PurePosixPath("sources", jurisdiction, document_class, version)
    if relative.is_absolute() or relative.parts[:4] != expected.parts or ".." in relative.parts:
        raise ValueError(f"source_path is outside its release scope: {source_path}")

    candidate = base.joinpath(*relative.parts)
    cursor = base
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"source_path contains a symlink: {source_path}")
    if not candidate.is_file():
        raise ValueError(f"source snapshot is missing: {source_path}")
    return candidate


def bind_inventory_source_hashes(
    repo_root: Path,
    release_path: Path,
    *,
    write: bool = False,
) -> dict[str, Any]:
    """Return the exact missing-hash repair plan and optionally apply it."""

    repo_root = repo_root.resolve(strict=True)
    base = repo_root / "data" / "corpus"
    release = ReleaseManifest.load(release_path)
    changed_files: list[str] = []
    changed_scopes: list[str] = []
    bound_items = 0

    for scope in release.scopes:
        inventory_path = (
            base / "inventory" / scope.jurisdiction / scope.document_class / f"{scope.version}.json"
        )
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise ValueError(f"inventory has no items list: {inventory_path}")

        changed = False
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"inventory contains a non-object item: {inventory_path}")
            source = _source_file(
                base,
                jurisdiction=scope.jurisdiction,
                document_class=scope.document_class,
                version=scope.version,
                source_path=item.get("source_path"),
            )
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            existing = item.get("sha256")
            if existing is not None and existing != digest:
                raise ValueError(
                    f"source sha256 mismatch for {item.get('citation_path')}: "
                    f"{existing} != {digest}"
                )
            if existing is None:
                item["sha256"] = digest
                changed = True
                bound_items += 1

        if not changed:
            continue
        relative_inventory = inventory_path.relative_to(repo_root).as_posix()
        changed_files.append(relative_inventory)
        changed_scopes.append("/".join(scope.key))
        if write:
            inventory_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    return {
        "bound_items": bound_items,
        "changed_files": changed_files,
        "changed_scopes": changed_scopes,
        "release": release.name,
        "write": write,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = bind_inventory_source_hashes(
        args.repo_root,
        args.release,
        write=args.write,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
