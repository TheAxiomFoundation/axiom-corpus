#!/usr/bin/env python3
"""Add the 2026-09-13 federal CFR layer rows to the program agent queues.

The needs-driven closure check (docs/coverage/needs-closure-2026-09-11/) found the federal
regulation layer of six programs never taken. docs/ingest-runs/2026-09-13-federal-cfr-layer.md
takes it from the eCFR Versioner API (as-of 2026-09-10). This generator records one
``federal_regulation_ecfr`` row per taken scope in each program's queue, inserted after that
queue's existing ``us`` rows (the program generators carry later ``us`` rows through untouched),
appends a one-sentence pointer to the pre-existing federal row, and recomputes
``status_counts`` the way the program generators do. Re-running it is idempotent: a row whose
``target_scope.version`` already exists is updated in place.

    uv run python scripts/build_federal_cfr_layer_queue_rows.py [--base data/corpus]

With ``--base`` the unit and row counts below are checked against the coverage files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUN_NOTE = "docs/ingest-runs/2026-09-13-federal-cfr-layer.md"
AS_OF = "2026-09-10"
ECFR = "https://www.ecfr.gov/current"
STRUCTURE = "https://www.ecfr.gov/api/versioner/v1/structure/{as_of}/title-{title}.json"
SOURCE_KIND = "federal_regulation_ecfr"

# (queue file, pointer sentence appended to the queue's first federal row) per program.
QUEUES: dict[str, tuple[str, str]] = {
    "snap": ("manifests/snap-completion-agent-queue.yaml", ""),
    "tanf": (
        "manifests/tanf-agent-queue.yaml",
        " 2026-09-13: 45 CFR parts 260-265 taken as us/regulation 2026-09-13-title-45-part-260 to -265 "
        f"(see the six federal_regulation_ecfr rows below and {RUN_NOTE}).",
    ),
    "liheap": (
        "manifests/liheap-agent-queue.yaml",
        " 2026-09-13: 45 CFR part 96 (subpart H, LIHEAP, 96.80-96.89, inside the whole part) taken as "
        f"us/regulation 2026-09-13-title-45-part-96 (see the federal_regulation_ecfr row below and {RUN_NOTE}).",
    ),
    "medicare": (
        "manifests/medicare-agent-queue.yaml",
        " 2026-09-13: 42 CFR parts 406, 407, 408 and 423 taken as us/regulation 2026-09-13-title-42-part-<p> "
        f"(see the four federal_regulation_ecfr rows below and {RUN_NOTE}).",
    ),
    "medicaid": (
        "manifests/medicaid-agent-queue.yaml",
        " 2026-09-13: 42 CFR part 447 (subpart A cost sharing, inside the whole part) taken as us/regulation "
        f"2026-09-13-title-42-part-447 (see the federal_regulation_ecfr row below and {RUN_NOTE}).",
    ),
    "tax": (
        "manifests/tax-agent-queue.yaml",
        " 2026-09-13: the closure check's 26 CFR part 1 sections (344, folded into the released 1401 scope's "
        "successor) and the whole of 26 CFR part 31 taken as us/regulation (see the two "
        f"federal_regulation_ecfr rows below and {RUN_NOTE}).",
    ),
}


def _reader_url(title: int, chapter: str, part: str, subchapter: str | None = None) -> str:
    sub = f"/subchapter-{subchapter}" if subchapter else ""
    return f"{ECFR}/title-{title}/chapter-{chapter}{sub}/part-{part}"


# program, title, part, scope version, eCFR units (= rows, coverage complete), shape, closure elements, extra note
ROWS: list[dict[str, Any]] = []


def _row(program: str, title: int, part: str, version: str, units: int, shape: str, elements: str,
         reader_url: str, extra: str = "") -> None:
    ROWS.append({
        "program": program, "title": title, "part": part, "version": version, "units": units,
        "shape": shape, "elements": elements, "reader_url": reader_url, "extra": extra,
    })


SNAP_PARTS = {
    "271": (10, "1 part + 9 sections", "snap_cfr_271_1-9"),
    "272": (19, "1 part + 18 sections", "snap_cfr_272_1-18"),
    "274": (9, "1 part + 8 sections", "snap_cfr_274_1-8"),
    "276": (8, "1 part + 7 sections", "snap_cfr_276_1-7"),
    "277": (19, "1 part + 17 sections + Appendix A (cost principles; 277.15 reserved skipped)", "snap_cfr_277_1-14,16-18"),
    "278": (9, "1 part + 8 sections (278.8, 278.10 reserved skipped)", "snap_cfr_278_1-7,9"),
    "279": (11, "1 part + 2 subparts + 8 sections", "snap_cfr_279_1-8"),
    "280": (2, "1 part + 1 section", "snap_cfr_280_1"),
    "281": (11, "1 part + 10 sections", "snap_cfr_281_1-10"),
    "282": (3, "1 part + 2 sections", "snap_cfr_282_1-2"),
    "283": (36, "1 part + 3 subparts + 32 sections", "snap_cfr_283_1-32"),
    "284": (2, "1 part + 1 section (284.2 reserved skipped)", "snap_cfr_284_1"),
    "285": (6, "1 part + 5 sections", "snap_cfr_285_1-5"),
}
for _part, (_units, _shape, _elements) in SNAP_PARTS.items():
    _row("snap", 7, _part, f"2026-09-13-title-7-part-{_part}", _units, _shape, _elements,
         _reader_url(7, "II", _part, "C"))

TANF_PARTS = {
    "260": (27, "1 part + 3 subparts + 23 sections", "tanf-f-cfr-260.* (23)"),
    "261": (52, "1 part + 8 subparts + 43 sections", "tanf-f-cfr-261.* (43)"),
    "262": (9, "1 part + 8 sections", "tanf-f-cfr-262.* (8)"),
    "263": (22, "1 part + 3 subparts + 18 sections", "tanf-f-cfr-263.* (18)"),
    "264": (30, "1 part + 3 subparts + 26 sections", "tanf-f-cfr-264.* (26)"),
    "265": (11, "1 part + 10 sections", "tanf-f-cfr-265.* (10)"),
}
for _part, (_units, _shape, _elements) in TANF_PARTS.items():
    _row("tanf", 45, _part, f"2026-09-13-title-45-part-{_part}", _units, _shape, _elements,
         _reader_url(45, "II", _part))

_row("liheap", 45, "96", "2026-09-13-title-45-part-96", 87,
     "1 part + 12 subparts + 73 sections + Appendix A (6 reserved sections and Appendix B skipped)",
     "LIHEAP-F-CFR96-96-81 to -86, -88, -89 (subpart H's eight live sections; 96.80 and 96.87 are reserved at the "
     "publisher, so LIHEAP-F-CFR96-96-80 and -87 have no text to take)",
     _reader_url(45, "I", "96"),
     "The adapter has no subpart selector, so the whole part (block grants: SSBG, LIHEAP, CSBG, PCBG, SABG) is taken; "
     "subpart H is us/regulation/45/96/subpart-H with its sections under us/regulation/45/96/<section>.")

MEDICARE_PARTS = {
    "406": (30, "1 part + 4 subparts + 25 sections", "MED-F-CFR-406"),
    "407": (33, "1 part + 4 subparts + 28 sections", "MED-F-CFR-407"),
    "408": (58, "1 part + 8 subparts + 49 sections (408.4 reserved skipped)", "MED-F-CFR-408"),
    "423": (360, "1 part + 25 subparts + 334 sections (2 reserved subparts, 3 reserved sections skipped)",
            "MED-F-CFR-423-B, -D, -P"),
}
for _part, (_units, _shape, _elements) in MEDICARE_PARTS.items():
    _row("medicare", 42, _part, f"2026-09-13-title-42-part-{_part}", _units, _shape, _elements,
         _reader_url(42, "IV", _part, "B"))

_row("medicaid", 42, "447", "2026-09-13-title-42-part-447", 79,
     "1 part + 7 subparts + 71 sections (subparts D and H and 447.58 reserved skipped)",
     "M-447-1 to M-447-90 (22 subpart A sections)", _reader_url(42, "IV", "447", "C"),
     "The adapter has no subpart selector, so the whole part (payments for services) is taken; subpart A is "
     "us/regulation/42/447/subpart-A.")

_row("tax", 26, "1", "2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated", 346,
     "1 part + 345 sections: the released 2026-07-24 scope's 1.1401-1 plus the 344 sections the closure check lists, "
     "taken section-scoped (extract-ecfr --section, 2026-09-13-title-26-part-1, 345 rows) and consolidated with "
     "scripts/consolidate_release_scopes.py because both scopes carry the us/regulation/26/1 container",
     "F116-F127, F129, F130, F132 (1.7703-1 only) and the 1.1402(a)-1 to 1.1402(h)-1 half of F128",
     _reader_url(26, "I", "1", "A"),
     "Section identifiers with parenthesised groups (1.401(k)-1) fold into hyphenated path segments "
     "(us/regulation/26/1/401-k-1); labels keep the official form. 1.163-16 is the publisher's placeholder for the "
     "91 FR 57235 amendment (heading 'xxx', empty body). 6 formula images archived without transcriptions "
     "(1.162-28, 1.163-10T, 1.408-11). F132's 301.7701-18 (part 301) is not taken.")
_row("tax", 26, "31", "2026-09-13-title-26-part-31", 359,
     "1 part + 7 subparts + 351 sections (31.3121(a)(12)-1 reserved skipped)", "F131",
     _reader_url(26, "I", "31", "C"))


def _note(row: dict[str, Any]) -> str:
    text = (
        f"2026-09-13 federal CFR layer ({RUN_NOTE}): {row['title']} CFR part {row['part']} extracted with "
        f"extract-ecfr --only-title {row['title']} --only-part {row['part']} from the eCFR Versioner API at as-of "
        f"{AS_OF} (the titles' up_to_date_as_of on 2026-09-13; expression date {AS_OF}). {row['units']} rows = "
        f"{row['shape']}; coverage complete; every section body non-empty unless noted; citation paths "
        f"us/regulation/{row['title']}/{row['part']}/<section>. Closure elements addressed: {row['elements']}."
    )
    if row["extra"]:
        text += " " + row["extra"]
    return text


def _queue_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "jurisdiction": "us",
        "name": "Federal",
        "queue_status": "agent_ready",
        "source_kind": SOURCE_KIND,
        "primary_source_url": row["reader_url"],
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us", "document_class": "regulation", "version": row["version"]},
        "lead_counts": {},
        "candidate_sources": [],
        "notes": _note(row),
        "index_url": STRUCTURE.format(as_of=AS_OF, title=row["title"]),
        "index_document_count": row["units"],
        "taken_count": row["units"],
    }


def _check_against_corpus(base: Path) -> None:
    for row in ROWS:
        coverage = json.loads((base / "coverage" / "us" / "regulation" / f"{row['version']}.json").read_text())
        if not coverage["complete"] or coverage["provision_count"] != row["units"]:
            raise SystemExit(f"{row['version']}: coverage {coverage['provision_count']} rows, complete={coverage['complete']}; "
                             f"generator says {row['units']}")


def apply(program: str, queue_path: Path, pointer: str) -> dict[str, int]:
    queue = yaml.safe_load(queue_path.read_text())
    states: list[dict[str, Any]] = queue["states"]
    new_rows = [_queue_row(r) for r in ROWS if r["program"] == program]
    by_version = {r["target_scope"]["version"]: r for r in new_rows}
    federal_indexes = [i for i, s in enumerate(states) if s["jurisdiction"] == "us"]
    if pointer and federal_indexes:
        first = states[federal_indexes[0]]
        if first.get("source_kind") != SOURCE_KIND and pointer not in (first.get("notes") or ""):
            first["notes"] = (first.get("notes") or "") + pointer
    # Update rows already present (idempotent re-run), then insert the rest after the last us row.
    for s in states:
        version = ((s.get("target_scope") or {}).get("version")) if s["jurisdiction"] == "us" else None
        if version in by_version:
            s.clear()
            s.update(by_version.pop(version))
    insert_at = (federal_indexes[-1] + 1) if federal_indexes else 0
    for r in list(by_version.values()):
        states.insert(insert_at, r)
        insert_at += 1
    queue["status_counts"] = {}
    for s in states:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, help="corpus root; check the row counts against coverage files")
    args = parser.parse_args()
    if args.base is not None:
        _check_against_corpus(args.base)
    for program, (rel, pointer) in QUEUES.items():
        counts = apply(program, ROOT / rel, pointer)
        print(f"{rel}: {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
