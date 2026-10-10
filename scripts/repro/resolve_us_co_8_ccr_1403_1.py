#!/usr/bin/env python3
"""Resolve rulespec-us's us-co/regulation citations with and without the 8 CCR 1403-1 successor.

Companion to ``scripts/repro/us_co_8_ccr_1403_1_sections.py``. For each release
line below, this resolves every ``us-co/regulation`` path in rulespec-us's
``provisions_to_rules.json`` twice with axiom-encode's own resolver
(``axiom_encode.corpus_resolver.resolve_local_corpus_source``): over the line's
``us-co/regulation`` scopes as selected, and with the line's Colorado recovery
scope swapped for the successor. The resolver reads only the scopes of a cited
path's jurisdiction and document class, so the other scopes of a line do not
change these results. It also resolves a few structural paths of the new rows.

The release is built in memory exactly as
``scripts/resolve_recovery_sibling_citations.py`` builds it (no release object is
loaded or validated). Run it by hand from the repository root with axiom-encode's
venv, after ``uv run axiom-corpus-ingest corpus fetch`` of the scopes it names:

    <axiom-encode>/.venv/bin/python scripts/repro/resolve_us_co_8_ccr_1403_1.py \\
        --encode-src <axiom-encode>/src --encode-rev <commit> \\
        --rulespec-index <rulespec-us>/.axiom/index/provisions_to_rules.json \\
        --rulespec-rev <commit>
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.resolve_recovery_sibling_citations import (  # noqa: E402
    Scope,
    _release,
    _resolve,
    require_provisions,
)

PAIR = ("us-co", "regulation")
RECOVERY = "2026-07-13-recovery"
CONSOLIDATED = f"{RECOVERY}-r2026-09-11-tanf-consolidated"
SUCCESSOR = f"{CONSOLIDATED}-r2026-09-27-ccap-sections"
# Each line and the Colorado scope it selects today.
LINES = {
    "us-rulespec-2026-08-08-obbb-alien-snap": RECOVERY,
    "us-rulespec-2026-09-24-irs-sales-tax-tables-union": CONSOLIDATED,
    "us-rulespec-2026-09-14-wave4-r2-union": CONSOLIDATED,
    "us-rulespec-2026-10-07-w6-bundle-gaps-union": CONSOLIDATED,
}
PROBES = (
    "us-co/regulation/8-ccr-1403-1",
    "us-co/regulation/8-ccr-1403-1/3.104",
    "us-co/regulation/8-ccr-1403-1/3.105.1",
    "us-co/regulation/8-ccr-1403-1/3.111",
    "us-co/regulation/8-ccr-1403-1/3.111/h",
)
DEFAULT_OUTPUT = Path("docs/ingest-runs/2026-09-27-co-8-ccr-1403-1-sections-downstream.json")


def downstream(root: Path, encode_src: Path, index_path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(encode_src))
    resolver = importlib.import_module("axiom_encode.corpus_resolver")
    artifact_type = importlib.import_module("axiom_encode.corpus_release").VerifiedReleaseArtifact

    index = json.loads(index_path.read_text(encoding="utf-8"))["provisions"]
    prefix = "/".join(PAIR) + "/"
    cited = sorted(path for path in index if path.startswith(prefix))
    selected: dict[str, list[Scope]] = {}
    for name in LINES:
        scopes = json.loads((root / "manifests/releases" / f"{name}.json").read_text())["scopes"]
        selected[name] = [
            (entry["jurisdiction"], entry["document_class"], entry["version"])
            for entry in scopes
            if (entry["jurisdiction"], entry["document_class"]) == PAIR
        ]
    successor: Scope = (*PAIR, SUCCESSOR)
    require_provisions(root, {s for scopes in selected.values() for s in scopes} | {successor})

    report: dict[str, Any] = {}
    for name, old_version in LINES.items():
        old: Scope = (*PAIR, old_version)
        if old not in selected[name]:
            raise SystemExit(f"{name} does not select {'/'.join(old)}")
        swapped = [successor if scope == old else scope for scope in selected[name]]
        now = _release(resolver, artifact_type, root, name, selected[name])
        after = _release(resolver, artifact_type, root, name + "+swap", swapped)
        changed = []
        same_text_from_successor = []
        resolved = {"as_selected": 0, "with_swap": 0}
        for path in cited:
            today = _resolve(resolver, now, path)
            swapped_result = _resolve(resolver, after, path)
            resolved["as_selected"] += "error" not in today
            resolved["with_swap"] += "error" not in swapped_result
            text = ("error", "body_sha256", "composed_from", "slice_required")
            if any(today.get(key) != swapped_result.get(key) for key in text):
                changed.append(
                    {
                        "cited_path": path,
                        "modules": sorted(entry["module"] for entry in index[path]),
                        "as_selected": today,
                        "with_swap": swapped_result,
                    }
                )
            elif today != swapped_result:
                # Same text, now read from the successor (only the version moves).
                same_text_from_successor.append(path)
        report[name] = {
            "swap": {"drop": "/".join(old), "add": "/".join(successor)},
            "us_co_regulation_scopes": len(selected[name]),
            "cited_paths": len(cited),
            "resolved": resolved,
            "changed": changed,
            "same_text_from_successor": same_text_from_successor,
            "probes_with_swap": {path: _resolve(resolver, after, path) for path in PROBES},
        }
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
        "generated_by": "scripts/repro/resolve_us_co_8_ccr_1403_1.py",
        "axiom_encode_rev": args.encode_rev,
        "rulespec_us_rev": args.rulespec_rev,
        "lines": downstream(args.corpus_root.resolve(), args.encode_src, args.rulespec_index),
    }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
