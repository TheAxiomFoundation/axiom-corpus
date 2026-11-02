"""Draft agent-queue work orders for the committed programs from the sanctioned lead list.

Lead list: PolicyEngine-US citations, extracted offline with the citing parameter or
variable path preserved (docs/source-discovery-checklist.md). Classified by
axiom_corpus.corpus.source_discovery. Every row is a candidate for a human to confirm;
queue_status is needs_review throughout. Nothing here is a corpus source.
"""
import collections
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.expanduser("~/axiom-corpus/src"))
from axiom_corpus.corpus.source_discovery import build_source_discovery_report, canonicalize_url

PE = Path(os.path.expanduser("~/policyengine-us"))
CORPUS = Path(os.path.expanduser("~/axiom-corpus"))
OUT = Path(sys.argv[1])
sha = subprocess.run(["git", "-C", str(PE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
when = subprocess.run(["git", "-C", str(PE), "log", "-1", "--format=%cI"], capture_output=True, text=True).stdout.strip()
spec = yaml.safe_load((Path(os.path.expanduser("~/axiom-encode-economics/data/committed_programs.yaml"))).read_text())
PE_DIRS = {"tax": ["irs", "tax"], "snap": ["snap"], "medicaid": ["medicaid"], "chip": ["chip"], "tanf": ["tanf"], "wic": ["wic"],
           "ccdf": ["ccdf"], "medicare": ["medicare"], "liheap": ["liheap"], "ssi": ["ssi"]}
dirs = {d: k for k, ds in PE_DIRS.items() for d in ds}
href = re.compile(r"href:\s*(\S+)")
url_re = re.compile(r"https?://[^\s\"']+")
# 1. reference JSONL with citing path, program, jurisdiction
refs = []
root = PE / "policyengine_us"
for sub, ext in (("parameters", ".yaml"), ("variables", ".py")):
    for f in sorted((root / sub / "gov").rglob(f"*{ext}")):
        rel = f.relative_to(root / sub).as_posix()
        parts = rel.split("/")
        if parts[1] in ("contrib", "local"):
            continue
        prog = next((dirs[seg] for seg in parts[:-1] if seg in dirs), None)
        if not prog:
            continue
        jur = f"us-{parts[2]}" if parts[1] == "states" else "us"
        txt = f.read_text(errors="ignore")
        for u in sorted(set(href.findall(txt) if ext == ".yaml" else url_re.findall(txt))):
            refs.append({"reference_url": u, "project": "policyengine-us", "file_path": f"{sub}/{rel}", "symbol_path": None, "program": prog, "jurisdiction": jur})
jsonl = OUT / "policyengine-us-committed-program-references.jsonl"
OUT.mkdir(parents=True, exist_ok=True)
jsonl.write_text("".join(json.dumps(r) + "\n" for r in refs))
# 2. classify with the corpus module; covered = any source_url already in a corpus manifest
covered, manifest_of = set(), {}
for mf in (CORPUS / "manifests").glob("*.yaml"):
    try:
        d = yaml.safe_load(mf.read_text()) or {}
    except Exception:
        continue
    for doc in d.get("documents") or []:
        su = doc.get("source_url")
        if su:
            covered.add(su)
            c = canonicalize_url(su)
            if c:
                manifest_of[c.canonical_url] = mf.stem
report = build_source_discovery_report((), reference_input_paths=(jsonl,), covered_source_urls=covered, source_name="policyengine-us")
by_canon = {r.canonical_url: r for r in report.rows}
# 3. program × jurisdiction leads
leads = collections.defaultdict(lambda: collections.defaultdict(dict))
for r in refs:
    c = canonicalize_url(r["reference_url"])
    if not c or c.canonical_url not in by_canon:
        continue
    row = by_canon[c.canonical_url]
    e = leads[r["program"]][r["jurisdiction"]].setdefault(c.canonical_url, {
        "url": c.canonical_url, "source_status": str(row.source_status), "disposition": str(row.disposition),
        "document_class": row.document_class, "host": row.host, "jurisdiction_inferred": row.jurisdiction,
        "already_registered": manifest_of.get(c.canonical_url), "discovered_via": []})
    if len(e["discovered_via"]) < 3 and r["file_path"] not in e["discovered_via"]:
        e["discovered_via"].append(f"policyengine-us#{r['file_path']}")
names = {s["jurisdiction"]: s["name"] for s in yaml.safe_load((CORPUS / "manifests/state-snap-manual-agent-queue.yaml").read_text())["states"]}
names["us"] = "Federal"
snap_policy = yaml.safe_load((CORPUS / "manifests/state-snap-manual-agent-queue.yaml").read_text())["policy"]
today = datetime.date.today().isoformat()
summary = {}
for pr in spec["programs"]:
    k = pr["key"]
    if k == "snap":
        continue
    states = []
    for jur in sorted(leads[k], key=lambda j: (j != "us", j)):
        cands = sorted(leads[k][jur].values(), key=lambda c: ({"ready_for_manifest": 0, "needs_review": 1}.get(c["disposition"], 2), c["url"]))
        counts = collections.Counter(c["disposition"] for c in cands)
        states.append({
            "jurisdiction": jur, "name": names.get(jur, jur), "queue_status": "needs_review",
            "source_kind": None, "primary_source_url": None,
            "target_manifest": f"manifests/{jur}-{k}-sources.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": None, "version": None},
            "lead_counts": dict(counts),
            "candidate_sources": cands,
            "notes": "Drafted from the lead list; a reviewer must confirm the primary official source, add agency manuals the lead list does not cite, set source_kind and target_scope, then move queue_status to agent_ready.",
        })
    doc = {
        "version": today,
        "document_family": f"{k}_policy_sources",
        "program": k.upper(),
        "queue_status": "draft",
        "policy": {**snap_policy, "notes": [
            "Drafted 2026-09-10 for the ten board Year 1 programs (ballmer-proposal-2026 encoding-program-list.md).",
            "Lead list only: PolicyEngine-US citations extracted offline with the citing path preserved, classified by axiom_corpus.corpus.source_discovery. Not corpus sources; every selected document must be re-fetched from the official publisher.",
            "The lead list under-names agency manuals and state plans. Reviewers must add them from the official publisher before the queue is agent_ready.",
            f"policyengine-us {sha[:12]} ({when[:10]}); lead file: {jsonl.name}",
        ]},
        "lead_list": {"source": "policyengine-us", "commit": sha, "committed_at": when, "reference_file": jsonl.name,
                      "classifier": "axiom_corpus.corpus.source_discovery.build_source_discovery_report"},
        "status_counts": dict(collections.Counter(s["queue_status"] for s in states)),
        "states": states,
    }
    (CORPUS / "manifests" / f"{k}-agent-queue.yaml").write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
    summary[k] = {"jurisdictions": len(states), "leads": sum(len(s["candidate_sources"]) for s in states),
                  "ready": sum(s["lead_counts"].get("ready_for_manifest", 0) for s in states),
                  "already_registered": sum(1 for s in states for c in s["candidate_sources"] if c["already_registered"])}
print(json.dumps({"refs": len(refs), "rows": len(report.rows), "programs": summary}, indent=1))
