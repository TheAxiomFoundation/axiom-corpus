#!/usr/bin/env python3
"""List locked scopes whose rows record a file: URL in a URL field.

A ``file:`` URL in ``source_url`` or a metadata ``*_url`` field (above all
``metadata.download_url``) names a path on the machine that extracted the scope,
such as ``file:///Users/<name>/...``. ``guard-ingested`` rejects new ones; this
audit finds the ones already locked. It reads each locked inventory and
provisions object from the worktree, the shared cache, git, or R2 (the same
reader the guard uses), so nothing needs fetching first. Body text is not read:
a scanned document may print a ``file:`` link itself.

    uv run python scripts/audit_local_file_urls.py
    uv run python scripts/audit_local_file_urls.py --release manifests/releases/<name>.json
    uv run python scripts/audit_local_file_urls.py --scope de/guidance --json report.json

Exit status is 1 when any selected scope carries such a URL, and 2 when an
artifact cannot be read or parsed, so cannot be cleared.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.corpus_locks import LockEntry, LockSet, ScopeKey, load_locks
from axiom_corpus.corpus.ingest_manifests import (
    LocalFileUrlScanError,
    default_content_reader,
    local_file_url_fields,
    redact_file_urls,
)

REPO = Path(__file__).resolve().parents[1]
ROW_PREFIXES = ("data/corpus/inventory/", "data/corpus/provisions/")


def _scope_label(scope: ScopeKey) -> str:
    return "/".join(scope)


def _selector_scopes(paths: Iterable[Path]) -> set[ScopeKey]:
    scopes: set[ScopeKey] = set()
    for path in paths:
        data = json.loads(path.read_text())
        for raw in data.get("scopes") or []:
            scopes.add((str(raw["jurisdiction"]), str(raw["document_class"]), str(raw["version"])))
    return scopes


def _selectors_by_scope(repo: Path) -> dict[ScopeKey, list[str]]:
    by_scope: dict[ScopeKey, list[str]] = {}
    for path in sorted((repo / "manifests" / "releases").glob("*.json")):
        for scope in _selector_scopes([path]):
            by_scope.setdefault(scope, []).append(path.stem)
    return by_scope


def _selected(
    locks: LockSet, *, scope_prefixes: list[str], release_scopes: set[ScopeKey] | None
) -> list[tuple[ScopeKey, LockEntry]]:
    selected = []
    for scope, lock in sorted(locks.locks.items()):
        label = _scope_label(scope)
        if scope_prefixes and not any(
            label == prefix or label.startswith(prefix.rstrip("/") + "/")
            for prefix in scope_prefixes
        ):
            continue
        if release_scopes is not None and scope not in release_scopes:
            continue
        selected.extend(
            (scope, entry) for entry in lock.files if entry.path.startswith(ROW_PREFIXES)
        )
    return selected


def audit(
    repo: Path,
    *,
    scope_prefixes: list[str] | None = None,
    release_paths: list[Path] | None = None,
    reader: Callable[[LockEntry], bytes | None] | None = None,
    workers: int = 4,
) -> dict[str, Any]:
    """Return ``{"scanned", "unreadable", "unscannable", "scopes"}`` for locked row artifacts.

    ``unreadable`` lists artifacts whose bytes no source holds; ``unscannable``
    those that are not UTF-8 JSON where a ``file:`` URL could sit, which the
    scan cannot clear.
    """
    locks = load_locks(repo)
    if locks.errors:
        raise SystemExit("corpus lock files are invalid: " + "; ".join(locks.errors[:5]))
    release_scopes = _selector_scopes(release_paths) if release_paths else None
    entries = _selected(locks, scope_prefixes=scope_prefixes or [], release_scopes=release_scopes)
    read = reader or default_content_reader(repo)

    def scan(item: tuple[ScopeKey, LockEntry]) -> tuple[ScopeKey, LockEntry, Any]:
        scope, entry = item
        payload = read(entry)
        if payload is None:
            return scope, entry, None
        try:
            return scope, entry, local_file_url_fields(entry.path, payload)
        except LocalFileUrlScanError as exc:
            return scope, entry, exc

    selectors = _selectors_by_scope(repo)
    by_scope: dict[ScopeKey, dict[str, Any]] = {}
    unreadable: list[str] = []
    unscannable: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for scope, entry, found in pool.map(scan, entries):
            if found is None:
                unreadable.append(entry.path)
                continue
            if isinstance(found, LocalFileUrlScanError):
                unscannable.append(str(found))
                continue
            if not found:
                continue
            record = by_scope.setdefault(
                scope,
                {
                    "scope": _scope_label(scope),
                    "artifacts": {},
                    "selectors": selectors.get(scope, []),
                },
            )
            fields: dict[str, int] = {}
            for _citation, field in found:
                shown = redact_file_urls(field)  # a crafted key could itself name a path
                fields[shown] = fields.get(shown, 0) + 1
            record["artifacts"][entry.path] = {"rows": len(found), "fields": fields}
    return {
        "scanned": len(entries),
        "unreadable": unreadable,
        "unscannable": unscannable,
        "scopes": [by_scope[scope] for scope in sorted(by_scope)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Limit to <jurisdiction>[/<document_class>[/<version>]]; repeatable.",
    )
    parser.add_argument(
        "--release",
        type=Path,
        action="append",
        default=[],
        help="Limit to the scopes a release selector names; repeatable.",
    )
    parser.add_argument("--json", type=Path, help="Write the full report here.")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    report = audit(
        args.repo.resolve(),
        scope_prefixes=args.scope,
        release_paths=args.release or None,
        workers=args.workers,
    )
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for record in report["scopes"]:
        rows = {path.split("/")[2]: detail["rows"] for path, detail in record["artifacts"].items()}
        print(
            f"{record['scope']}\t"
            + "\t".join(f"{kind}={count}" for kind, count in sorted(rows.items()))
            + f"\tselectors={len(record['selectors'])}"
        )
    print(
        f"{len(report['scopes'])} scope(s) record a file: URL; "
        f"{report['scanned']} row artifact(s) scanned, {len(report['unreadable'])} unreadable, "
        f"{len(report['unscannable'])} unscannable.",
        file=sys.stderr,
    )
    if report["unreadable"] or report["unscannable"]:
        for problem in (report["unreadable"] + report["unscannable"])[:5]:
            print(f"not cleared: {problem}", file=sys.stderr)
        return 2
    return 1 if report["scopes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
