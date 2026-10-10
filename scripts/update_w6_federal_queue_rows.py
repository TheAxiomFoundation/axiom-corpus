#!/usr/bin/env python3
"""Wave 6, group `federal`: record the new federal-layer scopes on each program queue's first `us` row.

    uv run python scripts/update_w6_federal_queue_rows.py --base /Users/pavelmakarchuk/axiom-corpus/data/corpus

Reads `docs/ingest-runs/2026-10-06-w6-federal-decisions.csv`, groups the PRESENT rows by program and
scope, and writes a `wave6_federal_scopes` record (scope, documents, provision rows, coverage) on the
first `jurisdiction: us` row of each program queue. The record is inserted as text so that the rest of
each queue file is byte-identical (other wave-6 agents edit the same queues' state rows); a second run
replaces the record instead of adding another. Row counts are read from the coverage reports.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DECISIONS = REPO / "docs/ingest-runs/2026-10-06-w6-federal-decisions.csv"
RUN_NOTE = "docs/ingest-runs/2026-10-06-w6-federal.md"
KEY = "wave6_federal_scopes"
QUEUES = {
    "income_tax": "tax", "eitc": "tax", "ctc": "tax", "medicaid": "medicaid", "chip": "chip",
    "snap": "snap-completion", "ssi": "ssi", "wic": "wic", "liheap": "liheap", "medicare": "medicare",
    "tanf": "tanf", "ccdf": "ccdf",
}


def scope_rows(base: Path, scope: str) -> tuple[int, bool]:
    jur, cls, version = scope.split("/", 2)
    coverage = json.loads((base / "coverage" / jur / cls / f"{version}.json").read_text())
    return int(coverage.get("provision_count") or coverage.get("source_count") or 0), bool(coverage.get("complete"))


def record_lines(records: list[dict]) -> list[str]:
    block = yaml.safe_dump({KEY: records}, sort_keys=False, allow_unicode=True, width=120)
    return ["  " + line if line else line for line in block.splitlines()]


def update_queue(path: Path, records: list[dict]) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index("states:")
    first = next(i for i in range(start + 1, len(lines)) if lines[i] == "- jurisdiction: us")
    end = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("- ") or not lines[i].startswith(" ")),
               len(lines))
    body = lines[first:end]
    # drop a previous record of this run (the key line and its deeper-indented lines)
    cleaned: list[str] = []
    skipping = False
    for line in body:
        if line == f"  {KEY}:":
            skipping = True
            continue
        if skipping and (line.startswith("  - ") or line.startswith("    ")):
            continue
        skipping = False
        cleaned.append(line)
    new_lines = lines[:first] + cleaned + record_lines(records) + lines[end:]
    text = "\n".join(new_lines) + "\n"
    before = yaml.safe_load(path.read_text(encoding="utf-8"))
    after = yaml.safe_load(text)
    before_row = dict(before["states"][next(i for i, r in enumerate(before["states"]) if r.get("jurisdiction") == "us")])
    before_row.pop(KEY, None)
    after_row = dict(after["states"][next(i for i, r in enumerate(after["states"]) if r.get("jurisdiction") == "us")])
    if after_row.pop(KEY) != records or after_row != before_row:
        raise SystemExit(f"{path}: inserted record did not round-trip")
    first_us = next(i for i, r in enumerate(before["states"]) if r.get("jurisdiction") == "us")
    others_before = [r for i, r in enumerate(before["states"]) if i != first_us]
    others_after = [r for i, r in enumerate(after["states"]) if i != first_us]
    if others_before != others_after or {k: v for k, v in before.items() if k != "states"} != {
        k: v for k, v in after.items() if k != "states"
    }:
        raise SystemExit(f"{path}: something other than the first us row changed")
    changed = text != path.read_text(encoding="utf-8")
    path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, type=Path)
    args = parser.parse_args()
    grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in csv.DictReader(DECISIONS.open(encoding="utf-8")):
        if row["new_status"] != "PRESENT":
            continue
        for program in row["programs"].split():
            queue = QUEUES.get(program)
            if queue:
                grouped[queue][row["scope_version"]].append(row["citation_path"])
    for queue, scopes in sorted(grouped.items()):
        records = []
        for scope in sorted(scopes):
            rows, complete = scope_rows(args.base, scope)
            records.append({
                "scope": scope,
                "work_order_documents": len(set(scopes[scope])),
                "scope_provision_rows": rows,
                "coverage_complete": complete,
                "citation_paths": sorted(set(scopes[scope])),
                "run_note": RUN_NOTE,
            })
        path = REPO / "manifests" / f"{queue}-agent-queue.yaml"
        changed = update_queue(path, records)
        print(f"{path.relative_to(REPO)}: {len(records)} scopes{' (changed)' if changed else ''}")


if __name__ == "__main__":
    main()
