#!/usr/bin/env python3
"""Add or refresh the federal statute (U.S. Code, USLM) row in each program agent queue.

The 2026-09-13 federal statute layer (docs/ingest-runs/2026-09-13-federal-statute-layer.md)
closes the needs-closure statute gaps with one self-contained ``us/statute`` scope per program.
Program queues are generated YAML; this generator inserts one ``us`` row per queue after the
last existing federal row (the shape the 2026-09-11 eCFR follow-on rows use), keyed by
``source_kind: federal_statute_uscode_uslm`` so a re-run refreshes rather than duplicates.
Counts are read from the scope artifacts under ``--base`` (coverage report and provisions),
never typed by hand, and ``status_counts`` is recomputed the way the builder scripts do.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_KIND = "federal_statute_uscode_uslm"
RUN_NOTE = "docs/ingest-runs/2026-09-13-federal-statute-layer.md"
RELEASE_POINT = "Public Law 119-103 (09/02/2026), USLM XML created 2026-09-09"
ZIP_URL = "https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc{title}@119-103.zip"

# program -> (queue file, scope version, title, sections taken, closure element ids, note)
SCOPES: dict[str, dict[str, object]] = {
    "wic": {
        "queue": "manifests/wic-agent-queue.yaml",
        "version": "2026-09-13-wic-statute-1786-title-42",
        "title": "42",
        "sections": "42 U.S.C. 1786",
        "elements": "wic_usc_1786_a through wic_usc_1786_s (19)",
        "still_missing": "",
    },
    "tanf": {
        "queue": "manifests/tanf-agent-queue.yaml",
        "version": "2026-09-13-tanf-statute-part-a-title-42",
        "title": "42",
        "sections": (
            "42 U.S.C. 601-619, every section of chapter 7 subchapter IV part A "
            "(601, 602, 603, 603a [transferred], 604, 604a, 605, 606, 607, 608, 608a, 609, 610, "
            "611, 611a, 612, 613, 614 [repealed], 615, 616, 617, 618, 619)"
        ),
        "elements": "tanf-f-usc-601 through tanf-f-usc-619 including tanf-f-usc-611a (20)",
        "still_missing": "",
    },
    "ccdf": {
        "queue": "manifests/ccdf-agent-queue.yaml",
        "version": "2026-09-13-ccdf-statute-ccdbg-title-42",
        "title": "42",
        "sections": (
            "42 U.S.C. 9857, 9858, 9858a-9858r, every section of chapter 105 subchapter II-B "
            "(CCDBG Act sections 658A-658T; 9857a is not a distinct USLM section, the goals are 9857(b))"
        ),
        "elements": "ccdf-f-usc-1 through ccdf-f-usc-7 (7)",
        "still_missing": "",
    },
    "ssi": {
        "queue": "manifests/ssi-agent-queue.yaml",
        "version": "2026-09-13-ssi-statute-1381a-1383f-title-42",
        "title": "42",
        "sections": (
            "42 U.S.C. 1381a, 1383, 1383a, 1383b, 1383c, 1383d, 1383e, 1383f (the Title XVI sections the "
            "released 2026-06-20 scope stops short of; 1381 and 1382-1382j stay in the released scope)"
        ),
        "elements": "SSI-F-USC-1381a, SSI-F-USC-1383, SSI-F-USC-1383a through SSI-F-USC-1383f (8)",
        "still_missing": "",
    },
    "liheap": {
        "queue": "manifests/liheap-agent-queue.yaml",
        "version": "2026-09-13-liheap-statute-chapter-94-title-42",
        "title": "42",
        "sections": (
            "42 U.S.C. 8621-8630, every section of chapter 94 subchapter II "
            "(8621, 8622, 8623, 8624, 8625, 8626, 8626a, 8626b, 8627, 8628, 8628a, 8629, 8630)"
        ),
        "elements": "LIHEAP-F-USC-8621 through LIHEAP-F-USC-8630 (10)",
        "still_missing": "",
    },
    "medicare": {
        "queue": "manifests/medicare-agent-queue.yaml",
        "version": "2026-09-13-medicare-statute-eligibility-premiums-title-42",
        "title": "42",
        "sections": (
            "42 U.S.C. 426-1, 1395c, 1395d, 1395e, 1395i-2, 1395i-2a, 1395k, 1395l, 1395o, 1395p, 1395q, "
            "1395r, 1395s, 1395v, 1395w-21, 1395w-22, 1395w-101, 1395w-102, 1395w-113, 1395w-114, 1396u-3 "
            "(the household-facing eligibility, enrollment, premium and cost-sharing sections of subchapter XVIII "
            "plus the QI allotment section; 426 stays in the released 2026-06-23 scope)"
        ),
        "elements": (
            "MED-F-USC-426-1, MED-F-USC-1395c through MED-F-USC-1395w-114 (20), MED-F-USC-1396u-3 (21); "
            "MED-F-USC-1396a and MED-F-USC-1396d are carried by the Medicaid closure scope"
        ),
        "still_missing": "",
    },
    "medicaid": {
        "queue": "manifests/medicaid-agent-queue.yaml",
        "version": "2026-09-13-medicaid-statute-closure-title-42",
        "title": "42",
        "sections": (
            "42 U.S.C. 1315, 1320b-7, 1396o, 1396o-1, 1396r-1, 1396r-1a, 1396r-1b, 1396r-1c, 1396r-5, 1396r-6 "
            "(whole sections) and the subsections 1396a(a)(3), (a)(17), (a)(25), (a)(34), (a)(47), (k), (r); "
            "1396d(b), (y), (z); 1396p(b), (c), (d) (the released 2026-06-26 Medicaid scope keeps 1396a(a)(10), "
            "(e), (f), (l), (m); 1396b(f), (v); 1396d(a), (n), (p), (q); 1396p(f); 1396u-1, and the PL 119-21 "
            "scope keeps 1396a(xx); no citation path is carried twice)"
        ),
        "elements": (
            "M-ST-1396a-a17, M-ST-1396a-a34, M-ST-1396a-a47, M-ST-1396a-k, M-ST-1396d-b-y, M-ST-1396o, "
            "M-ST-1396p-b, M-ST-1396p-c, M-ST-1396p-d, M-ST-1396r-5, M-ST-1396r-6, M-ST-1320b-7, M-ST-1315, "
            "M-ST-1396a-a3, M-ST-1396a-a25 (15)"
        ),
        "still_missing": "",
    },
    "tax": {
        "queue": "manifests/tax-agent-queue.yaml",
        "version": "2026-09-13-tax-statute-closure-31-title-26",
        "title": "26",
        "sections": (
            "26 U.S.C. 3, 23, 25, 31, 35, 53, 66, 71 [repealed], 72, 101, 103, 108, 117, 121, 125, 129, 132, 135, "
            "137, 139, 162, 215 [repealed], 217, 401, 402, 403, 415, 457, 461, 469, 529, 529A, 530, 1001, 1012, "
            "1014, 1015, 1016, 1250, 6072, 6081, 6654 (42 sections for the 31 tax closure elements)"
        ),
        "elements": (
            "F007, F012, F024, F035, F036, F037, F052, F053, F056, F058, F060, F062, F063, F064, F065, F066, F067, "
            "F068, F069, F072, F083, F092, F094, F095, F096, F097, F098, F101, F102, F113, F114 (31)"
        ),
        "still_missing": "",
    },
}


def _scope_counts(base: Path, version: str) -> tuple[int, int]:
    coverage = json.loads((base / "coverage" / "us" / "statute" / f"{version}.json").read_text())
    if not coverage.get("complete"):
        raise SystemExit(f"{version}: coverage is not complete; refusing to record it")
    provisions_path = base / "provisions" / "us" / "statute" / f"{version}.jsonl"
    sections = 0
    for line in provisions_path.read_text().splitlines():
        if line.strip() and json.loads(line).get("kind") == "section":
            sections += 1
    return int(coverage["provision_count"]), sections


def _row(program: str, spec: dict[str, object], base: Path) -> dict[str, object]:
    version = str(spec["version"])
    title = str(spec["title"])
    provisions, sections = _scope_counts(base, version)
    note = (
        f"2026-09-13 federal statute layer ({RUN_NOTE}): {spec['sections']}. Extracted with extract-usc from the "
        f"official OLRC USLM release point {RELEASE_POINT} ({ZIP_URL.format(title=title)}; the zip and its usc{title}.xml "
        f"member are retained under sources/us/statute/{version}/). {sections} section rows, {provisions} provision rows, "
        f"coverage complete; citation paths us/statute/{title}/<section>[/<subsection>...]. Section rows are "
        f"self-contained (the title row us/statute/{title} stays in its released consolidated scope; detached parents "
        f"are recorded in metadata.detached_parent_citation_path). No selected scope carries any of these paths. "
        f"Closes needs-closure elements {spec['elements']}."
    )
    if spec.get("still_missing"):
        note += f" Still missing: {spec['still_missing']}."
    return {
        "jurisdiction": "us",
        "name": f"Federal statute ({title} U.S.C., uscode.house.gov USLM)",
        "queue_status": "agent_ready",
        "source_kind": SOURCE_KIND,
        "primary_source_url": ZIP_URL.format(title=title),
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us", "document_class": "statute", "version": version},
        "lead_counts": {},
        "candidate_sources": [],
        "notes": note,
        "index_url": "https://uscode.house.gov/download/download.shtml",
        "index_document_count": sections,
        "taken_count": provisions,
    }


def update_queue(program: str, spec: dict[str, object], base: Path) -> dict[str, int]:
    queue_path = ROOT / str(spec["queue"])
    queue = yaml.safe_load(queue_path.read_text())
    row = _row(program, spec, base)
    states: list[dict[str, object]] = queue["states"]
    existing = [i for i, s in enumerate(states) if s.get("source_kind") == SOURCE_KIND]
    if existing:
        states[existing[0]] = row
    else:
        federal = [i for i, s in enumerate(states) if s.get("jurisdiction") == "us"]
        insert_at = federal[-1] + 1 if federal else 0
        states.insert(insert_at, row)
    queue["status_counts"] = {}
    for s in states:
        queue["status_counts"][s["queue_status"]] = (
            queue["status_counts"].get(s["queue_status"], 0) + 1
        )
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return dict(queue["status_counts"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base", type=Path, required=True, help="corpus root holding the statute scopes"
    )
    parser.add_argument(
        "--program", action="append", choices=sorted(SCOPES), help="restrict to these programs"
    )
    args = parser.parse_args()
    for program in args.program or sorted(SCOPES):
        counts = update_queue(program, SCOPES[program], args.base)
        print(f"{program}: {SCOPES[program]['queue']} status_counts={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
