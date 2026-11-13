#!/usr/bin/env python3
"""Verify an explicit JSON list of {oid, size} records in local SHA-1 Git.

No cache, remote source or lazy fetch can satisfy this check. Identical records
are deduplicated. The reported OID-set SHA256 hashes sorted unique ASCII OIDs,
each followed by a newline (the empty set hashes empty bytes).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

OID = re.compile(r"[0-9a-f]{40}\Z")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_inventory(path: Path) -> dict[str, int]:
    """Require explicit canonical OIDs/sizes; conflicting duplicates are errors."""
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    if not isinstance(payload, list):
        raise ValueError("inventory must be a JSON list of {oid, size} records")
    objects: dict[str, int] = {}
    for index, record in enumerate(payload):
        if not isinstance(record, dict) or set(record) != {"oid", "size"}:
            raise ValueError(f"inventory record {index} must contain exactly oid and size")
        oid, size = record["oid"], record["size"]
        if not isinstance(oid, str) or not OID.fullmatch(oid):
            raise ValueError(f"inventory record {index} requires a lowercase 40-hex OID")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"inventory record {index} requires a non-negative integer size")
        if oid in objects and objects[oid] != size:
            raise ValueError(f"conflicting expected sizes for OID {oid}")
        objects[oid] = size
    return objects


def _git(repo: Path, *args: str, input: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input,
        capture_output=True,
        text=True,
        encoding="ascii",
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1"},
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"local Git check failed: {result.stderr.strip()}")
    return result


def verify_inventory(repo: Path, objects: dict[str, int]) -> dict[str, int | str]:
    """Verify every normalized inventory object, including empty inventories."""
    object_format = _git(repo, "rev-parse", "--show-object-format").stdout.strip()
    if object_format != "sha1":
        raise ValueError(f"unsupported Git object format: {object_format!r}; expected sha1")
    ordered = sorted(objects)
    request = "".join(f"{oid}\n" for oid in ordered)
    lines = _git(repo, "cat-file", "--batch-check", input=request).stdout.splitlines()
    if len(lines) != len(ordered):
        raise ValueError("local Git reply count differs from the inventory")
    for oid, line in zip(ordered, lines, strict=True):
        fields = line.split()
        if len(fields) != 3 or fields[0] != oid:
            raise ValueError(f"missing or unexpected local Git reply for {oid}: {line!r}")
        if fields[1] != "blob":
            raise ValueError(f"expected blob for {oid}, got {fields[1]!r}")
        if fields[2] != str(objects[oid]):
            raise ValueError(
                f"wrong blob size for {oid}: expected {objects[oid]}, got {fields[2]!r}"
            )
    return {
        "object_count": len(ordered),
        "total_expected_bytes": sum(objects.values()),
        "oid_set_sha256": hashlib.sha256(request.encode("ascii")).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_inventory(args.repo, load_inventory(args.inventory))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"verify-git-blobs: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
