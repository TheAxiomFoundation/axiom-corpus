#!/usr/bin/env python3
"""Validate every corpus citation_path against schema/citation-path.v1.json.

This is the enforcement half of the citation-path grammar (Phase-A item A6 of
`axiom-rebuild-plan-2026-07-02.md`). It reads the machine-readable grammar,
scans every record in ``data/corpus/provisions/**/*.jsonl``, and checks:

1. Every ``citation_path`` matches the grammar pattern.
2. Segment 0 equals the record's ``jurisdiction`` field (when both present).
3. Segment 1 equals the record's ``document_class`` field (and is in the enum).
4. Irregular-family counts do not exceed their ratcheted baselines
   (``known_irregulars_ratchet``): a *regression* (someone added more
   ``block-N`` / ``page-N`` / truncated / space / en-dash / uppercase /
   collection-root segments than existed at r0) fails. Counts dropping is fine.
5. The identity-drift set (paths whose stored ``id`` derives from neither the
   path-only nor the versioned uuid5 identity) does not grow beyond its
   baseline list in ``identity_drift_ratchet``.

Exit code 0 = clean; 1 = one or more checks failed. No network, no Supabase;
pure local file scan. Additive tooling — binds to nothing.

Usage::

    python scripts/validate_citation_paths.py
    python scripts/validate_citation_paths.py --provisions data/corpus/provisions --json
    python scripts/validate_citation_paths.py --update-baselines   # rewrite ratchets to live counts

``--update-baselines`` is the deliberate, reviewed way to move a ratchet: it
rewrites the baselines/identity-drift list in the schema to the current live
values and prints a diff summary. Run it only when the change is intended.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema" / "citation-path.v1.json"
DEFAULT_PROVISIONS = REPO_ROOT / "data" / "corpus" / "provisions"

# Irregular-family membership predicates, keyed to known_irregulars_ratchet.
IRREGULAR_PREDICATES: dict[str, Callable[[str], bool]] = {
    "block_n": lambda p: bool(re.search(r"/block-\d+", p)),
    "page_n": lambda p: bool(re.search(r"/page-\d+", p)),
    "space_segments": lambda p: " " in p,
    "endash_segments": lambda p: "–" in p,
    "uppercase_segments": lambda p: any(c.isupper() for c in p),
    "truncated_segments": lambda p: any(bool(re.search(r"[ \-–]$", s)) for s in p.split("/")),
    "collection_roots": lambda p: len(p.split("/")) == 2,
}


def path_only_id(citation_path: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"axiom:{citation_path}"))


def versioned_id(version: str | None, citation_path: str) -> str | None:
    if version is None:
        return None
    normalized = str(version).strip()
    if not normalized:
        return None
    identity = json.dumps(["axiom", normalized, citation_path], separators=(",", ":"))
    return str(uuid5(NAMESPACE_URL, identity))


def load_records(provisions_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    pattern = str(provisions_dir / "**" / "*.jsonl")
    for filename in sorted(glob.glob(pattern, recursive=True)):
        with open(filename, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    records.append({"_error": f"{filename}:{lineno} invalid JSON"})
                    continue
                if "citation_path" not in obj:
                    continue
                obj["_file"] = filename
                records.append(obj)
    return records


def validate(provisions_dir: Path, schema: dict[str, Any]) -> dict[str, Any]:
    """Run all checks, returning a structured result dict."""
    pattern = re.compile(schema["$defs"]["citation_path"]["pattern"])
    doc_classes = set(schema["$defs"]["document_class"]["enum"])

    records = load_records(provisions_dir)
    paths = [r["citation_path"] for r in records if "citation_path" in r]

    json_errors = [r["_error"] for r in records if "_error" in r]

    pattern_failures: list[str] = []
    jurisdiction_mismatches: list[str] = []
    docclass_mismatches: list[str] = []
    unknown_docclass: list[str] = []

    for rec in records:
        if "citation_path" not in rec:
            continue
        p = rec["citation_path"]
        segs = p.split("/")
        if not pattern.match(p):
            pattern_failures.append(p)
        # jurisdiction / document_class consistency (only when field present)
        jur = rec.get("jurisdiction")
        if jur is not None and segs and segs[0] != jur:
            jurisdiction_mismatches.append(f"{p}  (field jurisdiction={jur!r})")
        dc = rec.get("document_class")
        if len(segs) > 1:
            if dc is not None and segs[1] != dc:
                docclass_mismatches.append(f"{p}  (field document_class={dc!r})")
            if segs[1] not in doc_classes:
                unknown_docclass.append(p)

    # Irregular-family live counts vs ratcheted baselines.
    baselines = schema["known_irregulars_ratchet"]["baselines"]
    live_counts = {name: sum(1 for p in paths if pred(p)) for name, pred in IRREGULAR_PREDICATES.items()}
    ratchet_regressions = {
        name: (live_counts[name], baselines[name])
        for name in baselines
        if live_counts.get(name, 0) > baselines[name]
    }

    # Identity drift: stored id derives from neither path-only nor versioned id.
    drift_baseline = set(schema["identity_drift_ratchet"]["baseline_paths"])
    drift_live: list[str] = []
    for rec in records:
        if "citation_path" not in rec:
            continue
        stored = rec.get("id")
        if not stored:
            continue
        p = rec["citation_path"]
        if path_only_id(p) == stored:
            continue
        if versioned_id(rec.get("version"), p) == stored:
            continue
        drift_live.append(p)
    drift_live_set = set(drift_live)
    drift_new = sorted(drift_live_set - drift_baseline)  # regressions: NOT in baseline
    drift_resolved = sorted(drift_baseline - drift_live_set)  # baseline entries now clean

    ok = (
        not json_errors
        and not pattern_failures
        and not jurisdiction_mismatches
        and not docclass_mismatches
        and not unknown_docclass
        and not ratchet_regressions
        and not drift_new
    )

    return {
        "ok": ok,
        "provisions_dir": str(provisions_dir),
        "record_count": len(paths),
        "unique_path_count": len(set(paths)),
        "json_errors": json_errors,
        "pattern_failures": sorted(set(pattern_failures)),
        "jurisdiction_mismatches": sorted(set(jurisdiction_mismatches)),
        "docclass_mismatches": sorted(set(docclass_mismatches)),
        "unknown_docclass": sorted(set(unknown_docclass)),
        "irregular_live_counts": live_counts,
        "irregular_baselines": baselines,
        "ratchet_regressions": ratchet_regressions,
        "identity_drift_live": sorted(drift_live_set),
        "identity_drift_new": drift_new,
        "identity_drift_resolved": drift_resolved,
    }


def update_baselines(schema_path: Path, result: dict[str, Any]) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["known_irregulars_ratchet"]["baselines"] = {
        k: result["irregular_live_counts"][k]
        for k in schema["known_irregulars_ratchet"]["baselines"]
    }
    schema["identity_drift_ratchet"]["baseline_paths"] = result["identity_drift_live"]
    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def print_report(result: dict[str, Any]) -> None:
    print(f"citation-path grammar validation  ({result['provisions_dir']})")
    print(f"  records scanned : {result['record_count']}")
    print(f"  unique paths    : {result['unique_path_count']}")
    print()
    print("  irregular families (live / baseline):")
    for name, live in result["irregular_live_counts"].items():
        base = result["irregular_baselines"].get(name, "-")
        flag = "  <-- REGRESSION" if name in result["ratchet_regressions"] else ""
        print(f"    {name:20s} {live:6d} / {base}{flag}")
    print()

    def section(label: str, items: list[Any], limit: int = 20) -> None:
        if not items:
            return
        print(f"  {label}: {len(items)}")
        for item in items[:limit]:
            print(f"    - {item}")
        if len(items) > limit:
            print(f"    ... and {len(items) - limit} more")

    section("INVALID JSON lines", result["json_errors"])
    section("PATTERN failures", result["pattern_failures"])
    section("jurisdiction field mismatches", result["jurisdiction_mismatches"])
    section("document_class field mismatches", result["docclass_mismatches"])
    section("unknown document_class", result["unknown_docclass"])
    section("NEW identity drift (grows the ratchet)", result["identity_drift_new"])

    if result["identity_drift_resolved"]:
        print(f"  identity drift resolved since baseline: {len(result['identity_drift_resolved'])}")
        print("    (consider running --update-baselines to shrink the tracked set)")
    print()
    print("  RESULT:", "OK" if result["ok"] else "FAILED")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provisions", type=Path, default=DEFAULT_PROVISIONS,
                    help="Root directory of provision JSONL files.")
    ap.add_argument("--schema", type=Path, default=SCHEMA_PATH,
                    help="Path to citation-path.v1.json.")
    ap.add_argument("--json", action="store_true", help="Emit the result dict as JSON instead of a report.")
    ap.add_argument("--update-baselines", action="store_true",
                    help="Rewrite ratchet baselines and identity-drift list to current live values.")
    args = ap.parse_args(argv)

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    result = validate(args.provisions, schema)

    if args.update_baselines:
        update_baselines(args.schema, result)
        # Re-validate against the freshly written baselines so the exit code is clean.
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        result = validate(args.provisions, schema)
        print("Baselines updated to live counts.")

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
