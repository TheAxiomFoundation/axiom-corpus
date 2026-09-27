#!/usr/bin/env python3
"""Resolve rulespec-us citations against the release lines, with and without each audited scope.

Companion to ``scripts/audit_recovery_sibling_scopes.py``. For every scope that
audit covers, and every key release line that selects it, this resolves each
corpus path rulespec-us cites under the scope's jurisdiction and document class
twice with axiom-encode's own resolver
(``axiom_encode.corpus_resolver.resolve_local_corpus_source``): once over the
line's scopes as selected, once with the swap the run note proposes (the scope
dropped, its replacement added). It records every citation whose resolution
touches the scope or changes under the swap.

axiom-encode is not a dependency of this repository, so this is run by hand and
its output committed; CI only checks the committed file's consistency. The
release object's signature is not checked: the release is built from the local
provisions files (their real sha256 and byte counts), so lookup, composition and
slicing are the resolver's own code.

Run it with a Python that has axiom-encode's dependencies (its own venv), from
the repository root:

    <axiom-encode>/.venv/bin/python scripts/resolve_recovery_sibling_citations.py \\
        --encode-src <axiom-encode>/src --encode-rev <commit> \\
        --rulespec-index <rulespec-us>/.axiom/index/provisions_to_rules.json \\
        --rulespec-rev <commit>
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = Path("docs/ingest-runs/2026-09-27-recovery-sibling-scopes-downstream.json")
KEY_SELECTORS = (
    "us-rulespec-2026-08-08-obbb-alien-snap",
    "us-rulespec-2026-09-24-snap-fy2027-cola",
    "us-rulespec-2026-08-23-canada-338-suspension-union",
    "us-rulespec-2026-09-14-wave4-union",
    "us-rulespec-2026-09-14-wave4-r2-union",
)
NY_CORE = (
    "us-ny/statute/2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-"
    "tax-615-tax-616"
)
# The swap the run note proposes for each scope: scopes that leave with it (they
# collide with the replacement) and the replacement. A scope with no
# replacement is simply dropped, to show what depends on it.
SWAPS: dict[str, dict[str, list[str]]] = {
    "us-ny/statute/2026-07-13-recovery": {
        "drop_with": [NY_CORE],
        "add": ["us-ny/statute/2026-09-14-income-tax-chapter"],
    },
    "us-id/statute/2026-07-13-recovery": {},
    "us-me/statute/2026-07-13-recovery": {
        "add": ["us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36"]
    },
    "us-mn/statute/2026-07-13-recovery": {
        "add": [
            "us-mn/statute/2026-09-14-income-tax-chapter-us-mn-title-290",
            "us-mn/statute/2026-09-14-income-tax-chapter-us-mn-title-142g",
            "us-mn/statute/2026-09-14-income-tax-chapter-us-mn-title-256p",
        ]
    },
    "us-ut/statute/2026-07-13-recovery": {
        "add": ["us-ut/statute/2026-09-14-income-tax-chapter-title-59"]
    },
    "us-sc/statute/2026-07-13-recovery": {},
    "us-mi/statute/2026-07-13-recovery": {
        "add": ["us-mi/statute/2026-09-14-income-tax-chapter-us-mi-chapter-206"]
    },
    "us-mt/regulation/2026-07-13-recovery": {},
    "us-co/regulation/2026-07-13-recovery": {
        "add": ["us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated"]
    },
    "us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated": {},
    "us-fl/regulation/2026-07-13-recovery": {},
    "us-sc/regulation/2026-07-13-recovery": {},
    "us-tn/regulation/2026-07-13-recovery": {},
    "us-il/manual/2026-07-13-recovery-r2026-07-17-dedup": {},
    "us-in/manual/2026-07-13-recovery": {},
    "us-sc/manual/2026-07-13-recovery": {},
    "us-ut/manual/2026-07-13-recovery": {},
    "us/guidance/2026-07-13-recovery": {},
}

Scope = tuple[str, str, str]


def _scope(text: str) -> Scope:
    jurisdiction, document_class, version = text.split("/", 2)
    return jurisdiction, document_class, version


def _release(resolver: Any, artifact_type: Any, root: Path, name: str, scopes: list[Scope]) -> Any:
    release = object.__new__(resolver.LocalCorpusRelease)
    artifacts = []
    for jurisdiction, document_class, version in scopes:
        relative = f"data/corpus/provisions/{jurisdiction}/{document_class}/{version}.jsonl"
        raw = (root / relative).read_bytes()
        artifacts.append(
            artifact_type(
                artifact_class="provisions",
                path=relative,
                sha256=hashlib.sha256(raw).hexdigest(),
                byte_count=len(raw),
                row_count=raw.count(b"\n"),
            )
        )
    for attribute, value in (
        ("root", root),
        ("name", name),
        ("content_sha256", "0" * 64),
        ("public_key", ""),
        ("provisions_root", root / "data" / "corpus" / "provisions"),
        ("selector_sha256", "0" * 64),
        ("scopes", tuple(resolver.ReleaseScope(*scope) for scope in scopes)),
        ("artifacts", tuple(artifacts)),
        ("release_object_path", root / "releases" / name),
    ):
        object.__setattr__(release, attribute, value)
    return release


def _resolve(resolver: Any, release: Any, path: str) -> dict[str, Any]:
    try:
        source = resolver.resolve_local_corpus_source(path, release)
    except Exception as exc:  # noqa: BLE001 - the resolver's own failure classes
        return {"error": type(exc).__name__, "message": str(exc)[:300]}
    return {
        "resolved_path": source.citation_path,
        "resolved_version": source.row.version,
        "slice_required": source.slice_required,
        "composed_from": [row.citation_path for row in source.component_rows],
        "body_chars": len(source.body),
        "body_sha256": hashlib.sha256(source.body.encode("utf-8")).hexdigest(),
    }


def downstream(root: Path, encode_src: Path, index_path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(encode_src))
    resolver = importlib.import_module("axiom_encode.corpus_resolver")
    artifact_type = importlib.import_module("axiom_encode.corpus_release").VerifiedReleaseArtifact

    index = json.loads(index_path.read_text(encoding="utf-8"))["provisions"]
    selectors = {
        path.stem: [
            (entry["jurisdiction"], entry["document_class"], entry["version"])
            for entry in json.loads(path.read_text(encoding="utf-8"))["scopes"]
        ]
        for path in sorted((root / "manifests" / "releases").glob("*.json"))
    }
    report: dict[str, Any] = {}
    for key, swap in SWAPS.items():
        scope = _scope(key)
        prefix = f"{scope[0]}/{scope[1]}/"
        cited = sorted(path for path in index if path.startswith(prefix))
        lines: dict[str, Any] = {}
        for name in KEY_SELECTORS:
            selected = selectors[name]
            if scope not in selected:
                continue
            dropped = {scope, *(_scope(item) for item in swap.get("drop_with", []))}
            added = [_scope(item) for item in swap.get("add", [])]
            swapped = [s for s in selected if s not in dropped] + [
                s for s in added if s not in selected
            ]
            now = _release(resolver, artifact_type, root, name, selected)
            after = _release(resolver, artifact_type, root, name + "+swap", swapped)
            affected = []
            for path in cited:
                today = _resolve(resolver, now, path)
                swapped_result = _resolve(resolver, after, path)
                if (
                    today.get("resolved_version") == scope[2]
                    or today != swapped_result
                    or "cross active release scopes" in today.get("message", "")
                ):
                    affected.append(
                        {
                            "cited_path": path,
                            "modules": sorted(entry["module"] for entry in index[path]),
                            "today": today,
                            "after_swap": swapped_result,
                        }
                    )
            lines[name] = {
                "dropped": sorted("/".join(item) for item in dropped),
                "added": ["/".join(item) for item in added],
                "cited_under_pair": len(cited),
                "affected": affected,
            }
        report[key] = lines
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--corpus-root", type=Path, default=Path("."))
    parser.add_argument("--encode-src", type=Path, required=True)
    parser.add_argument("--encode-rev", required=True, help="axiom-encode commit of --encode-src")
    parser.add_argument("--rulespec-index", type=Path, required=True)
    parser.add_argument("--rulespec-rev", required=True, help="rulespec-us commit of the index")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = {
        "generated_by": "scripts/resolve_recovery_sibling_citations.py",
        "axiom_encode_rev": args.encode_rev,
        "rulespec_us_rev": args.rulespec_rev,
        "scopes": downstream(args.corpus_root.resolve(), args.encode_src, args.rulespec_index),
    }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
