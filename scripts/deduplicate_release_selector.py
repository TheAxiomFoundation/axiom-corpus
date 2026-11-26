#!/usr/bin/env python3
"""Remove cross-scope citation duplicates from unreleased release additions.

The canonical selector identifies the scopes that retain citation ownership. The
target selector must contain every canonical scope, each in the same layer, and
may add unreleased scopes. When a citation occurs once in a canonical primary
scope and once in an added primary scope, this command removes the added
provision and its matching inventory item, then refreshes that scope's coverage
report. Any ambiguous collision is rejected.

Base scopes the target declares are never opened and never cut. A target
that selects, as a primary scope, a scope that a tracked selector it reads
marks as a base is refused before any artifact is opened. For a citation path
that both layers carry, serving picks the primary row, so a primary row over a
base row is layering, not a duplicate: only primary scopes compete for a
citation. The report lists the base scopes the run left untouched.

Dedup reads the selectors committed at HEAD of ``releases_dir`` (on the
command line, the checkout ``resolver.cli_repo`` finds from ``--corpus``), of
the checkouts that physically hold a target scope's artifacts or either
selector file, of each checkout the resolver recognises that holds a link on
those paths as dedup spells them, and on the command line of the working
directory's checkout. Before it opens any artifact it refuses a link at a
checkout's guarded place that leads into no checkout, a path through a
symlinked file at or below a guarded place, a checkout whose ``manifests`` or
``manifests/releases`` is a symlink or holds a ``.git`` entry, an artifact
path that does not resolve to a path ending in its own artifact kind,
jurisdiction, document class and version, an added primary's file with
another hard link, and an added primary's file that a base it knows reaches
through a link (``successors.guard_scope_artifacts`` and
``refuse_links_into_bases``). A checkout it does not read is one of the
threat model's stated limits (2, 11 and 15).

Released scopes are immutable. Re-version them before using this command.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.releases import ReleaseScope, parse_release_scope
from axiom_corpus.corpus.resolver import cli_repo
from axiom_corpus.corpus.successors import (
    guard_scope_artifacts,
    refuse_links_into_bases,
    refuse_tracked_bases_as_primary,
    tracked_base_scopes,
)

# The tracked selectors are the only record of which scopes are bases.
DEFAULT_RELEASES_DIR = Path(__file__).resolve().parents[1] / "manifests" / "releases"
# The three files of a scope that ``_refresh_scope`` reads and rewrites.
_ARTIFACTS = (("provisions", ".jsonl"), ("inventory", ".json"), ("coverage", ".json"))


def _read_selector(path: Path) -> tuple[ReleaseScope, ...]:
    payload = json.loads(path.read_text())
    raw_scopes = payload.get("scopes")
    if not isinstance(raw_scopes, list):
        raise ValueError(f"{path}: selector must contain a scopes list")
    scopes = tuple(parse_release_scope(scope, manifest_path=path) for scope in raw_scopes)
    if len(scopes) != len({scope.key for scope in scopes}):
        raise ValueError(f"{path}: selector contains duplicate scopes")
    return scopes


def _scope_order(scope: ReleaseScope) -> tuple[str, str, str, str]:
    return (*scope.key, scope.layer)


def _render(scope: ReleaseScope) -> str:
    rendered = f"{scope.jurisdiction}/{scope.document_class}/{scope.version}"
    return f"{rendered} (base)" if scope.is_base else rendered


def _artifact_path(corpus: Path, artifact: str, scope: ReleaseScope, suffix: str) -> Path:
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
    scope: ReleaseScope,
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
        **scope.to_selector_mapping(),
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
    releases_dir: Path | None = None,
    holders_of: Iterable[Path] = (),
) -> dict[str, Any]:
    """Remove from the target's added primary scopes each citation a canonical scope carries.

    ``releases_dir`` names the ``manifests/releases`` directory whose tracked
    selectors say which scopes are bases; ``None`` means
    ``DEFAULT_RELEASES_DIR``, that directory in this script's checkout. A
    target that selects one of those bases as a primary scope raises
    ``ValueError`` before any artifact is opened.

    It also reads the selectors committed at HEAD of the checkouts that
    physically hold a target scope's provisions, inventory or coverage or
    either selector file, of each checkout the resolver recognises that holds
    a link on those paths as spelled here, and of the checkouts holding each
    path in ``holders_of`` (``main()`` passes the working directory), and
    refuses a base of theirs that the target selects as a primary scope.
    Before any artifact is opened it raises ``ValueError`` for a link at a
    checkout's guarded place that leads into no checkout, an artifact path
    that does not resolve to a path ending in its own artifact kind,
    jurisdiction, document class and version, an added primary's file with
    another hard link, and an added primary's file that a base it knows
    reaches through a link. A checkout it does not read is one of the threat
    model's stated limits (2, 11 and 15).
    """
    canonical_scopes = set(_read_selector(canonical_selector))
    target_scopes = _read_selector(target_selector)
    # Whole-scope comparison: a canonical scope carried in the other layer is
    # omitted, not kept.
    missing = sorted(canonical_scopes - set(target_scopes), key=_scope_order)
    if missing:
        raise ValueError(
            "target selector omits canonical scopes: " + ", ".join(_render(s) for s in missing)
        )
    # The canonical scopes are among the target's, so this checks them too.
    directory = DEFAULT_RELEASES_DIR if releases_dir is None else releases_dir
    known = set(tracked_base_scopes(directory))
    refuse_tracked_bases_as_primary(
        target_scopes, known, selector=f"target selector {target_selector}"
    )
    # Only added primary scopes can be cut, so only their files are rewritten.
    # Base scopes' paths are guarded too, since a base path that links to a
    # primary file is an alias; the guard and the link check only resolve
    # paths, so no base scope is opened.
    rewritten = [
        _artifact_path(corpus, kind, scope, suffix)
        for scope in target_scopes
        if not scope.is_base and scope not in canonical_scopes
        for kind, suffix in _ARTIFACTS
    ]
    paths = [
        _artifact_path(corpus, kind, scope, suffix)
        for scope in target_scopes
        for kind, suffix in _ARTIFACTS
    ]
    for inventory in guard_scope_artifacts(
        paths,
        releases_dir=directory,
        rewritten=rewritten,
        holders_of=(canonical_selector, target_selector, *holders_of),
    ):
        extra = tracked_base_scopes(inventory)
        refuse_tracked_bases_as_primary(
            target_scopes, extra, selector=f"target selector {target_selector}"
        )
        known |= extra
    refuse_links_into_bases(corpus=corpus, bases=known, rewritten=rewritten)

    base_scopes = sorted((scope for scope in target_scopes if scope.is_base), key=_scope_order)
    carriers: dict[str, list[tuple[ReleaseScope, bool]]] = defaultdict(list)
    for scope in target_scopes:
        if scope.is_base:
            continue
        path = _artifact_path(corpus, "provisions", scope, ".jsonl")
        seen_in_scope: set[str] = set()
        for _, row in _read_provision_lines(path):
            citation_path = row["citation_path"]
            if citation_path in seen_in_scope:
                raise ValueError(f"{path}: duplicate citation_path {citation_path}")
            seen_in_scope.add(citation_path)
            carriers[citation_path].append((scope, scope in canonical_scopes))

    removals: dict[ReleaseScope, set[str]] = defaultdict(set)
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
                f"{_render(scope)} ({'canonical' if canonical else 'added'})"
                for scope, canonical in matches
            )
            raise ValueError(f"ambiguous citation carrier for {citation_path}: {rendered}")
        removals[added_matches[0]].add(citation_path)

    ordered_removals = sorted(removals.items(), key=lambda item: _scope_order(item[0]))
    preflight = [
        _refresh_scope(corpus, scope, removed_paths, apply=False)
        for scope, removed_paths in ordered_removals
    ]
    scopes = (
        [
            _refresh_scope(corpus, scope, removed_paths, apply=True)
            for scope, removed_paths in ordered_removals
        ]
        if apply
        else preflight
    )
    return {
        "applied": apply,
        "collision_count": sum(scope["removed_count"] for scope in scopes),
        "inherited_collision_count": len(inherited_collision_paths),
        "inherited_collision_paths": inherited_collision_paths,
        "scope_count": len(scopes),
        "scopes": scopes,
        "untouched_base_scopes": [scope.to_selector_mapping() for scope in base_scopes],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    parser.add_argument("--canonical-selector", type=Path, required=True)
    parser.add_argument("--target-selector", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    # The checkout resolver.cli_repo finds from --corpus decides which scopes are
    # bases, as --base does for compose_scope_versions.py and
    # consolidate_release_scopes.py; the working directory's checkout, such as a
    # sparse worktree whose branch commits a new base, is read too.
    repo = cli_repo(argparse.Namespace(base=args.corpus))
    if repo is None:
        parser.error(
            "neither --corpus nor the working directory is in an axiom-corpus checkout, so no "
            "tracked selectors say which scopes are bases"
        )
    report = deduplicate(
        args.corpus,
        args.canonical_selector,
        args.target_selector,
        apply=args.apply,
        releases_dir=repo / "manifests" / "releases",
        holders_of=(Path.cwd(),),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
