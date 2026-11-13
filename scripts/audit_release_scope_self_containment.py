#!/usr/bin/env python3
"""Audit parent closure using the publisher's per-scope load boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.resolver import ensure_corpus_paths


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _provisions_path(corpus_root: Path, raw_scope: dict[str, Any]) -> Path:
    return (
        corpus_root
        / "provisions"
        / str(raw_scope["jurisdiction"])
        / str(raw_scope["document_class"])
        / f"{raw_scope['version']}.jsonl"
    )


def ensure_corpus_inputs(release: dict[str, Any], corpus_root: Path) -> None:
    """Fetch the provisions file of every release scope. Does nothing without locks.

    Paths are made absolute so that a relative ``--base`` resolves against the
    checkout that holds it, whatever the working directory.
    """
    ensure_corpus_paths(
        [_provisions_path(corpus_root, scope).absolute() for scope in release["scopes"]]
    )


def find_scope_residuals(
    release: dict[str, Any], corpus_root: Path
) -> list[dict[str, str]]:
    """Return child rows whose parent is absent from that exact scope.

    Citation paths in another in-plan scope deliberately do not satisfy the
    check.  The provision staging planner compensates cascades by exact
    ``(citation_path, version)`` keys, not by citation path across a release.
    """
    residuals: list[dict[str, str]] = []
    for raw_scope in release["scopes"]:
        jurisdiction = str(raw_scope["jurisdiction"])
        document_class = str(raw_scope["document_class"])
        version = str(raw_scope["version"])
        rows = _rows(_provisions_path(corpus_root, raw_scope))
        local_paths = {str(row["citation_path"]) for row in rows}
        for row in rows:
            parent = row.get("parent_citation_path")
            if parent and str(parent) not in local_paths:
                residuals.append(
                    {
                        "jurisdiction": jurisdiction,
                        "document_class": document_class,
                        "version": version,
                        "citation_path": str(row["citation_path"]),
                        "missing_parent_citation_path": str(parent),
                    }
                )
    return residuals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release", type=Path, default=Path("manifests/releases/us-rulespec-2026-07-13.json")
    )
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    release = json.loads(args.release.read_text())
    ensure_corpus_inputs(release, args.base)
    residuals = find_scope_residuals(release, args.base)
    report = {
        "scope_count": len(release["scopes"]),
        "residual_count": len(residuals),
        "residuals": residuals,
        "rule": "parent must be in the same exact scope load (citation_path + version)",
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(text)
    print(text, end="")
    return 1 if residuals else 0


if __name__ == "__main__":
    raise SystemExit(main())
