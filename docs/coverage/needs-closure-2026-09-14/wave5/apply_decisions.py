#!/usr/bin/env python3
"""Fold wave-5 decisions CSVs back into the recount matrices and print the before/after roll-up.

    python3 wave5/apply_decisions.py --matrices docs/coverage/needs-closure-2026-09-14 \
        --decisions ~/axiom-corpus-worktrees/w5-*/docs/ingest-runs/2026-09-15-*-decisions.csv [--write]

Decision classes map to matrix statuses: PRESENT, ALREADY-HELD -> PRESENT (with the cited scope/path);
PATTERN-CONFIRMED -> PRESENT for the cells the row names; ABSENT, ABSENT-IN-CITED -> ABSENT; EXTRACTABLE,
OUTREACH, REVIEW keep their class; HELD-UNTIL-* -> unchanged. Federal rows (jurisdiction us) that become PRESENT
also flip the 51 inherited state rows of the same element when those rows carry the old federal status.
Without --write nothing is modified; the roll-up is printed either way.
"""
import argparse, csv, collections, glob, pathlib
ST = ["PRESENT", "EXTRACTABLE", "ABSENT", "OUTREACH", "REVIEW"]
MAP = {"PRESENT": "PRESENT", "ALREADY-HELD": "PRESENT", "PATTERN-CONFIRMED": "PRESENT",
       "ABSENT": "ABSENT", "ABSENT-IN-CITED": "ABSENT", "EXTRACTABLE": "EXTRACTABLE",
       "OUTREACH": "OUTREACH", "REVIEW": "REVIEW"}
ap = argparse.ArgumentParser(); ap.add_argument("--matrices", required=True); ap.add_argument("--decisions", nargs="+", required=True)
ap.add_argument("--write", action="store_true"); a = ap.parse_args()
mdir = pathlib.Path(a.matrices)
decisions = collections.defaultdict(dict)   # program -> (jur, element) -> row
for pat in a.decisions:
    for f in glob.glob(str(pathlib.Path(pat).expanduser())):
        for r in csv.DictReader(open(f)):
            ns = r["new_status"].strip().upper()
            if ns not in MAP: continue
            decisions[r["program"].strip().lower()][(r["jurisdiction"].strip(), r["element"].strip())] = r
def roll(rows):
    c = collections.Counter(r["status"].strip().upper() for r in rows if r["jurisdiction"] != "us"); n = sum(c[s] for s in ST)
    return n, {s: (f"{100*c[s]/n:.0f}%" if n else "-") for s in ST}
print("| Program | State cells | Present before | Present after | Extractable before | after | Review before | after | changed |")
print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
for prog in ["snap", "wic", "medicaid", "chip", "tanf", "ccdf", "ssi", "liheap", "medicare", "tax"]:
    p = mdir / f"{prog}-matrix.csv"
    rows = list(csv.DictReader(p.open())); fields = rows[0].keys() if rows else []
    before = roll(rows); changed = 0; dec = decisions.get(prog, {})
    fed_flip = {}
    for r in rows:
        d = dec.get((r["jurisdiction"], r["element"]))
        if not d: continue
        new = MAP[d["new_status"].strip().upper()]
        if new != r["status"].strip().upper() or (new == "PRESENT" and d.get("scope_version")):
            if r["jurisdiction"] == "us": fed_flip[r["element"]] = (r["status"].strip().upper(), new, d)
            r["status"] = new
            if d.get("scope_version"): r["scope_version"] = d["scope_version"]
            if d.get("citation_path"): r["citation_path"] = d["citation_path"]
            r["evidence_note"] = f"wave-5 {d['new_status']}: {d['note']}"[:600]; changed += 1
    for r in rows:   # inherited federal flips
        f = fed_flip.get(r["element"])
        if f and r["jurisdiction"] != "us" and r["status"].strip().upper() == f[0] and (r["level"].lower().startswith("federal") and "state" not in r["level"].lower()):
            r["status"] = f[1]; r["scope_version"] = f[2].get("scope_version", ""); r["citation_path"] = f[2].get("citation_path", ""); r["evidence_note"] = f"wave-5 inherited from us row: {f[2]['note']}"[:600]; changed += 1
    after = roll(rows)
    print(f"| {prog} | {after[0]:,} | {before[1]['PRESENT']} | {after[1]['PRESENT']} | {before[1]['EXTRACTABLE']} | {after[1]['EXTRACTABLE']} | {before[1]['REVIEW']} | {after[1]['REVIEW']} | {changed} |")
    if a.write and changed:
        with p.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(fields)); w.writeheader(); w.writerows(rows)
