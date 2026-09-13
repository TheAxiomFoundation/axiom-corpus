#!/usr/bin/env python3
"""Independent check of the three matrices: every PRESENT row must name a scope that is
selected (draft union selector or one of the three 2026-09-11 federal scopes the brief adds),
and a citation_path that exists in that scope with a non-empty body (or, for a container/document
row, a descendant with a non-empty body). Prints failures and, with --dump, the heading and the
opening of the body of every state-level PRESENT row so a reader can judge the evidence."""
import argparse, csv, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXTRA = {("us", "regulation", "2026-09-11-title-20-part-416"), ("us", "manual", "2026-09-11-medicare-cms-iom-100-02"),
         ("us", "manual", "2026-09-11-medicare-cms-iom-100-04")}
ap = argparse.ArgumentParser(); ap.add_argument("--base", default="/Users/pavelmakarchuk/axiom-corpus/data/corpus")
ap.add_argument("--selector", default="/Users/pavelmakarchuk/axiom-corpus/docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json")
ap.add_argument("--dump", action="store_true"); ap.add_argument("--programs", default="ssi,liheap,medicare")
a = ap.parse_args()
sel = {(s["jurisdiction"], s["document_class"], s["version"]) for s in json.load(open(a.selector))["scopes"]} | EXTRA
cache = {}
def load(jur, cls, ver):
    k = (jur, cls, ver)
    if k not in cache:
        p = Path(a.base) / "provisions" / jur / cls / f"{ver}.jsonl"
        cache[k] = {json.loads(l)["citation_path"]: json.loads(l) for l in p.open()} if p.exists() else None
    return cache[k]
bad = 0
for prog in a.programs.split(","):
    rows = list(csv.DictReader((HERE / f"{prog}-matrix.csv").open()))
    seen = set(); n_present = 0
    for r in rows:
        key = (r["jurisdiction"], r["element"])
        assert key not in seen, ("duplicate cell", prog, key); seen.add(key)
        if r["status"] != "PRESENT":
            continue
        n_present += 1
        cp = r["citation_path"]; parts = cp.split("/")
        jur, cls = parts[0], parts[1]
        if (jur, cls, r["scope_version"]) not in sel:
            print(f"NOT SELECTED {prog} {r['jurisdiction']} {r['element']} {jur}/{cls}/{r['scope_version']}"); bad += 1; continue
        rows_ = load(jur, cls, r["scope_version"])
        if rows_ is None:
            print(f"NO FILE {prog} {r['jurisdiction']} {r['element']} {jur}/{cls}/{r['scope_version']}"); bad += 1; continue
        d = rows_.get(cp)
        if d is None:
            print(f"NO PATH {prog} {r['jurisdiction']} {r['element']} {r['scope_version']} {cp}"); bad += 1; continue
        body = (d.get("body") or "").strip()
        if not body:
            kids = {}
            for x in rows_.values():
                kids.setdefault(x.get("parent_citation_path"), []).append(x)
            desc, todo = [], list(kids.get(cp, [])) + [x for p_, x in rows_.items() if p_.startswith(cp + "/")]
            seen_ = set()
            while todo:
                x = todo.pop()
                if x["citation_path"] in seen_:
                    continue
                seen_.add(x["citation_path"])
                if (x.get("body") or "").strip():
                    desc.append(x)
                todo.extend(kids.get(x["citation_path"], []))
            if not desc:
                print(f"EMPTY {prog} {r['jurisdiction']} {r['element']} {r['scope_version']} {cp}"); bad += 1; continue
            body = f"[container; {len(desc)} descendants with text; first: {desc[0]['citation_path']}] " + (desc[0].get("body") or "")
        if a.dump and r["level"] == "state" and r["jurisdiction"] != "us":
            print(f"--- {prog} {r['jurisdiction']} {r['element']} {r['scope_version']} {cp}\n    H: {(d.get('heading') or '')[:100]}\n    B: {' '.join(body.split())[:260]}")
    print(f"== {prog}: {len(rows)} cells, {n_present} PRESENT checked")
print("FAILURES:", bad); sys.exit(1 if bad else 0)
