#!/usr/bin/env python3
"""Remove cross-scope citation duplicates from unreleased release additions.

The canonical selector identifies the scopes that retain citation ownership. The
target selector must contain every canonical scope and may add unreleased scopes.
When a citation occurs once in a canonical scope and once in an added scope, this
command removes the added provision and its matching inventory item, then refreshes
that scope's coverage report. Any ambiguous collision is rejected.

Released scopes are immutable. Re-version them before using this command.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, order=True)
class Scope:
    jurisdiction: str
    document_class: str
    version: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Scope:
        return cls(
            jurisdiction=str(payload["jurisdiction"]),
            document_class=str(payload["document_class"]),
            version=str(payload["version"]),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "jurisdiction": self.jurisdiction,
            "document_class": self.document_class,
            "version": self.version,
        }


def _read_selector(path: Path) -> tuple[Scope, ...]:
    payload = json.loads(path.read_text())
    raw_scopes = payload.get("scopes")
    if not isinstance(raw_scopes, list):
        raise ValueError(f"{path}: selector must contain a scopes list")
    scopes = tuple(Scope.from_payload(scope) for scope in raw_scopes)
    if len(scopes) != len(set(scopes)):
        raise ValueError(f"{path}: selector contains duplicate scopes")
    return scopes


def _artifact_path(corpus: Path, artifact: str, scope: Scope, suffix: str) -> Path:
    return (
        corpus
        / artifact
        / scope.jurisdiction
        / scope.document_class
        / f"{scope.version}{suffix}"
    )


def _read_provision_lines(path: Path) -> list[tuple[str, dict[str, Any]]]:
    lines: list[tuple[str, dict[str, Any]]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line:
            continue
        row = json.loads(line)
        citation_path = row.get("citation_path")
        if not isinstance(citation_path, str) or not citation_path:
            raise ValueError(f"{path}:{line_number}: missing citation_path")
        lines.append((line, row))
    return lines


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _refresh_scope(
    corpus: Path,
    scope: Scope,
    removed_paths: set[str],
    *,
    apply: bool,
) -> dict[str, Any]:
    provisions_path = _artifact_path(corpus, "provisions", scope, ".jsonl")
    inventory_path = _artifact_path(corpus, "inventory", scope, ".json")
    coverage_path = _artifact_path(corpus, "coverage", scope, ".json")

    provision_lines = _read_provision_lines(provisions_path)
    inventory = json.loads(inventory_path.read_text())
    coverage = json.loads(coverage_path.read_text())
    items = inventory.get("items")
    if not isinstance(items, list):
        raise ValueError(f"{inventory_path}: inventory must contain an items list")

    provision_counts = Counter(row["citation_path"] for _, row in provision_lines)
    inventory_counts = Counter(item.get("citation_path") for item in items)
    for citation_path in sorted(removed_paths):
        if provision_counts[citation_path] != 1:
            raise ValueError(
                f"{provisions_path}: expected one provision for {citation_path}, "
                f"found {provision_counts[citation_path]}"
            )
        if inventory_counts[citation_path] != 1:
            raise ValueError(
                f"{inventory_path}: expected one inventory item for {citation_path}, "
                f"found {inventory_counts[citation_path]}"
            )

    retained_lines = [
        line for line, row in provision_lines if row["citation_path"] not in removed_paths
    ]
    retained_rows = [
        row for _, row in provision_lines if row["citation_path"] not in removed_paths
    ]
    retained_items = [item for item in items if item.get("citation_path") not in removed_paths]
    retained_paths = [row["citation_path"] for row in retained_rows]
    retained_inventory_paths = [str(item.get("citation_path")) for item in retained_items]
    retained_set = set(retained_paths)

    dangling = sorted(
        row["citation_path"]
        for row in retained_rows
        if row.get("parent_citation_path") in removed_paths
    )
    if dangling:
        raise ValueError(
            f"{provisions_path}: removing a parent would orphan: {', '.join(dangling)}"
        )

    inventory["items"] = retained_items
    if "source_count" in inventory:
        inventory["source_count"] = len(retained_items)
    coverage.update(
        {
            "complete": (
                bool(retained_paths)
                and not _duplicates(retained_paths)
                and not _duplicates(retained_inventory_paths)
                and set(retained_inventory_paths) == retained_set
            ),
            "duplicate_provision_citations": _duplicates(retained_paths),
            "duplicate_source_citations": _duplicates(retained_inventory_paths),
            "extra_provisions": sorted(retained_set - set(retained_inventory_paths)),
            "matched_count": len(retained_set & set(retained_inventory_paths)),
            "missing_from_provisions": sorted(set(retained_inventory_paths) - retained_set),
            "provision_count": len(retained_paths),
            "source_count": len(retained_inventory_paths),
        }
    )
    if not coverage["complete"]:
        raise ValueError(f"{coverage_path}: deduplicated scope would not be complete")

    if apply:
        provisions_path.write_text("\n".join(retained_lines) + "\n")
        _write_json(inventory_path, inventory)
        _write_json(coverage_path, coverage)

    return {
        **scope.as_dict(),
        "provision_count": len(retained_paths),
        "removed_count": len(removed_paths),
        "removed_paths": sorted(removed_paths),
    }


def deduplicate(
    corpus: Path,
    canonical_selector: Path,
    target_selector: Path,
    *,
    apply: bool,
) -> dict[str, Any]:
    canonical_scopes = set(_read_selector(canonical_selector))
    target_scopes = _read_selector(target_selector)
    missing = sorted(canonical_scopes - set(target_scopes))
    if missing:
        raise ValueError(
            "target selector omits canonical scopes: "
            + ", ".join(f"{s.jurisdiction}/{s.document_class}/{s.version}" for s in missing)
        )

    carriers: dict[str, list[tuple[Scope, bool]]] = defaultdict(list)
    for scope in target_scopes:
        path = _artifact_path(corpus, "provisions", scope, ".jsonl")
        seen_in_scope: set[str] = set()
        for _, row in _read_provision_lines(path):
            citation_path = row["citation_path"]
            if citation_path in seen_in_scope:
                raise ValueError(f"{path}: duplicate citation_path {citation_path}")
            seen_in_scope.add(citation_path)
            carriers[citation_path].append((scope, scope in canonical_scopes))

    removals: dict[Scope, set[str]] = defaultdict(set)
    inherited_collision_paths: list[str] = []
    for citation_path, matches in sorted(carriers.items()):
        if len(matches) == 1:
            continue
        canonical_matches = [scope for scope, canonical in matches if canonical]
        added_matches = [scope for scope, canonical in matches if not canonical]
        if not added_matches:
            inherited_collision_paths.append(citation_path)
            continue
        if len(canonical_matches) != 1 or len(added_matches) != 1:
            rendered = ", ".join(
                f"{scope.jurisdiction}/{scope.document_class}/{scope.version}"
                f" ({'canonical' if canonical else 'added'})"
                for scope, canonical in matches
            )
            raise ValueError(f"ambiguous citation carrier for {citation_path}: {rendered}")
        removals[added_matches[0]].add(citation_path)

    scopes = [
        _refresh_scope(corpus, scope, removed_paths, apply=apply)
        for scope, removed_paths in sorted(removals.items())
    ]
    return {
        "applied": apply,
        "collision_count": sum(scope["removed_count"] for scope in scopes),
        "inherited_collision_count": len(inherited_collision_paths),
        "inherited_collision_paths": inherited_collision_paths,
        "scope_count": len(scopes),
        "scopes": scopes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    parser.add_argument("--canonical-selector", type=Path, required=True)
    parser.add_argument("--target-selector", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = deduplicate(
        args.corpus,
        args.canonical_selector,
        args.target_selector,
        apply=args.apply,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
