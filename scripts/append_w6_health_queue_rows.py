#!/usr/bin/env python3
# ruff: noqa: E501
"""Append the wave-6 health rows to the Medicaid, CHIP and Medicare agent queues.

One `family: w6_bundle_gap` row per new scope (queue_status agent_ready: extracted, unsigned,
awaiting the controller) and one per blocked publisher (blocked_primary_source), built from
docs/ingest-runs/2026-10-06-w6-health-decisions.csv. The rows are appended as a text block after
the existing `states:` list (the last top-level key of each queue), so existing rows keep their
formatting; a rerun replaces the block. `status_counts` is recomputed from every row.

Usage:
    uv run python scripts/append_w6_health_queue_rows.py
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs" / "ingest-runs" / "2026-10-06-w6-health-decisions.csv"
RUN_NOTE = "docs/ingest-runs/2026-10-06-w6-health.md"
WORK_ORDER = "docs/coverage/program-bundle-gaps-2026-10-06/wave6/health.csv (branch analysis/program-bundle-gaps-2026-10-06)"
BEGIN = "# --- wave 6 health rows (scripts/append_w6_health_queue_rows.py) ---"
QUEUES = {
    "medicaid": ROOT / "manifests" / "medicaid-agent-queue.yaml",
    "chip": ROOT / "manifests" / "chip-agent-queue.yaml",
    "medicare": ROOT / "manifests" / "medicare-agent-queue.yaml",
}
# Scopes whose documents are all Medicare Savings Program or CHIP materials go to that queue;
# everything else goes to the Medicaid queue.
MEDICARE_SCOPES = {"us-ct/guidance/2026-10-06-w6-health-guidance-ct", "us-me/statute/2026-10-06-w6-health-statute-me"}
CHIP_SCOPES = {
    "us-fl/guidance/2026-10-06-w6-health-guidance-fl", "us-ia/guidance/2026-10-06-w6-health-guidance-ia",
    "us-ks/guidance/2026-10-06-w6-health-guidance-ks", "us-mo/statute/2026-10-06-w6-health-statute-mo",
    "us-tx/manual/2026-10-06-w6-health-manual-tx", "us-wi/manual/2026-10-06-w6-health-manual-wi",
    "us-ca/manual/2026-10-06-w6-health-manual-ca",
}


def _queue_for(scope: str) -> str:
    if scope in MEDICARE_SCOPES:
        return "medicare"
    if scope in CHIP_SCOPES:
        return "chip"
    return "medicaid"


def _manifest_for(scope: str) -> str | None:
    jur, cls, version = scope.split("/")
    candidates = [ROOT / "manifests" / f"{jur}-health-w6-{cls}.yaml"]
    for path in candidates:
        if path.exists() and f"version: {version}" in path.read_text() or (
            path.exists() and f'version: "{version}"' in path.read_text()
        ):
            return str(path.relative_to(ROOT))
    if scope.startswith("us-co/statute/"):
        return "manifests/us-co-health-w6-statute.yaml"
    return None


def _names() -> dict[str, str]:
    names: dict[str, str] = {}
    data = yaml.safe_load(QUEUES["medicaid"].read_text())
    for row in data.get("states", []):
        if row.get("name"):
            names.setdefault(row["jurisdiction"], row["name"])
    return names


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def main() -> int:
    with DECISIONS.open(newline="") as handle:
        decisions = list(csv.DictReader(handle))
    names = _names()
    by_scope: dict[str, list[dict]] = defaultdict(list)
    blocked: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for d in decisions:
        if d["new_status"] == "PRESENT":
            by_scope[d["scope_version"]].append(d)
        elif d["new_status"] == "OUTREACH":
            host = re.sub(r"^https?://", "", d["official_url"]).split("/")[0]
            blocked[(d["jurisdiction"], host)].append(d)
    blocks: dict[str, list[str]] = defaultdict(list)
    for scope, rows in sorted(by_scope.items()):
        jur, cls, version = scope.split("/")
        paths = sorted({r["citation_path"] for r in rows})
        lines = [
            f"- jurisdiction: {jur}",
            f"  name: {names.get(jur, jur)}",
            "  family: w6_bundle_gap",
            "  queue_status: agent_ready",
            "  source_kind: official_documents_program_bundle_gap",
        ]
        manifest = _manifest_for(scope)
        if manifest:
            lines.append(f"  target_manifest: {manifest}")
        lines += [
            "  target_scope:",
            f"    jurisdiction: {jur}",
            f"    document_class: {cls}",
            f"    version: {version}",
            f"  taken_count: {len(rows)}",
            f"  work_order: {WORK_ORDER}",
            f"  run_note: {RUN_NOTE}",
            "  citation_paths:",
            *[f"  - {p}" for p in paths],
            "  notes: " + _q(
                f"2026-10-06 wave 6 health (program-bundle gaps): {len(rows)} work-order row(s) extracted from the official "
                f"publisher into {scope} (unsigned, uncommitted; controller signs and selects). See {RUN_NOTE}."
            ),
        ]
        blocks[_queue_for(scope)].append("\n".join(lines))
    for (jur, host), rows in sorted(blocked.items()):
        lines = [
            f"- jurisdiction: {jur}",
            f"  name: {names.get(jur, jur)}",
            "  family: w6_bundle_gap",
            "  queue_status: blocked_primary_source",
            "  source_kind: official_documents_program_bundle_gap",
            f"  primary_source_url: {rows[0]['official_url']}",
            f"  blocked_count: {len(rows)}",
            f"  work_order: {WORK_ORDER}",
            f"  run_note: {RUN_NOTE}",
            "  notes: " + _q(f"2026-10-06 wave 6 health: {host} blocks the corpus client ({rows[0]['note']}). OUTREACH; not worked around."),
        ]
        blocks["medicaid"].append("\n".join(lines))
    for key, path in QUEUES.items():
        text = path.read_text()
        if BEGIN in text:
            text = text[: text.index(BEGIN)].rstrip("\n") + "\n"
        if blocks.get(key):
            text = text.rstrip("\n") + "\n" + BEGIN + "\n" + "\n".join(blocks[key]) + "\n"
        data = yaml.safe_load(text)
        counts = Counter(row.get("queue_status") for row in data.get("states", []))
        status_block = "status_counts:\n" + "".join(f"  {k}: {v}\n" for k, v in counts.items())
        text = re.sub(r"^status_counts:\n(?:  .*\n)+", status_block, text, count=1, flags=re.M)
        path.write_text(text)
        yaml.safe_load(text)  # still valid YAML
        print(f"{path.relative_to(ROOT)}: {len(blocks.get(key, []))} wave-6 rows; status_counts {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
