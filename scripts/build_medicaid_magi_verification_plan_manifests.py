"""Build one official-document manifest per state for the MAGI-based eligibility verification plans that
CMS posts on medicaid.gov, and add a `family: magi_verification_plan` row per state to the Medicaid agent queue.

Wave-5 closure (2026-09-15, docs/ingest-runs/2026-09-15-medicaid-chip.md). 42 CFR 435.945(j) requires every state
to submit its MAGI-based verification plan to CMS, and CMS posts the approved plans on one index page:
https://www.medicaid.gov/medicaid/eligibility-policy/medicaid/chip-eligibility-verification-plans. The plan is the
document family the closure schema names for 42 CFR 435.920, 435.945, 435.948, 435.949 and 435.952
(`plan_family: MAGI-based verification plan (state-submitted, posted by CMS on medicaid.gov)`): it records, per
eligibility factor, whether the state accepts self-attestation, which electronic data sources (the federal data
services hub, SSA, IEVS, state wage data) it uses, and its reasonable-compatibility standard.

The index lists, per state, an "Eligibility Verification Plan" PDF and, for some states, a COVID-era "Disaster
Addendum" and an unwinding "Mitigation Plan". Only the verification plan is taken; the addenda and mitigation plans
are inventoried in the queue row's `index_families` and not taken (temporary flexibilities, not the standing plan).
Every link is read from the live index at build time; nothing is hand-written. medicaid.gov answered the plain
extractor client HTTP 200 on 2026-09-14 (index and PDFs), so no browser impersonation is requested.

    uv run python scripts/build_medicaid_magi_verification_plan_manifests.py            # every state on the index
    uv run python scripts/build_medicaid_magi_verification_plan_manifests.py --only us-wy --only us-ia
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "manifests" / "medicaid-agent-queue.yaml"
INDEX = "https://www.medicaid.gov/medicaid/eligibility-policy/medicaid/chip-eligibility-verification-plans"
VERSION = "2026-09-15-medicaid-magi-verification-plan"
SOURCE_AS_OF = "2026-09-15"
FAMILY = "magi_verification_plan"
UA = "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) https://github.com/TheAxiomFoundation/axiom-corpus"

STATES = {
    "us-al": "Alabama", "us-ak": "Alaska", "us-az": "Arizona", "us-ar": "Arkansas", "us-ca": "California",
    "us-co": "Colorado", "us-ct": "Connecticut", "us-de": "Delaware", "us-dc": "District of Columbia",
    "us-fl": "Florida", "us-ga": "Georgia", "us-hi": "Hawaii", "us-id": "Idaho", "us-il": "Illinois",
    "us-in": "Indiana", "us-ia": "Iowa", "us-ks": "Kansas", "us-ky": "Kentucky", "us-la": "Louisiana",
    "us-me": "Maine", "us-md": "Maryland", "us-ma": "Massachusetts", "us-mi": "Michigan", "us-mn": "Minnesota",
    "us-ms": "Mississippi", "us-mo": "Missouri", "us-mt": "Montana", "us-ne": "Nebraska", "us-nv": "Nevada",
    "us-nh": "New Hampshire", "us-nj": "New Jersey", "us-nm": "New Mexico", "us-ny": "New York",
    "us-nc": "North Carolina", "us-nd": "North Dakota", "us-oh": "Ohio", "us-ok": "Oklahoma", "us-or": "Oregon",
    "us-pa": "Pennsylvania", "us-ri": "Rhode Island", "us-sc": "South Carolina", "us-sd": "South Dakota",
    "us-tn": "Tennessee", "us-tx": "Texas", "us-ut": "Utah", "us-vt": "Vermont", "us-va": "Virginia",
    "us-wa": "Washington", "us-wv": "West Virginia", "us-wi": "Wisconsin", "us-wy": "Wyoming",
}
_BY_NAME = {name: jur for jur, name in STATES.items()}
_LINK_RE = re.compile(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', re.S | re.I)
SUBTYPES = {
    "Eligibility Verification Plan": "magi_verification_plan_pdf",
    "Disaster Addendum": "disaster_addendum_pdf",
    "Mitigation Plan": "mitigation_plan_pdf",
}


def fetch(url: str) -> tuple[str, float]:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    resp.raise_for_status()
    return resp.text, resp.elapsed.total_seconds()


def slug(value: str, limit: int = 80) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:limit].strip("-")


def parse_index(page: str) -> dict[str, list[dict[str, str]]]:
    """Return {jurisdiction: [{title, url, kind}, ...]} in index order."""
    out: dict[str, list[dict[str, str]]] = {}
    for href, text in _LINK_RE.findall(page):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
        for name, jur in _BY_NAME.items():
            if text.startswith(name + " "):
                kind = text[len(name) + 1:].strip()
                if kind.startswith("Mitigation Plan"):
                    kind_key = "Mitigation Plan"
                elif kind.startswith("Disaster Addendum"):
                    kind_key = "Disaster Addendum"
                elif kind.startswith("Eligibility Verification Plan"):
                    kind_key = "Eligibility Verification Plan"
                else:
                    kind_key = kind
                out.setdefault(jur, []).append({"title": text, "url": urljoin(INDEX, html.unescape(href)), "kind": kind_key})
                break
    return out


def build(jur: str, links: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    name = STATES[jur]
    families: dict[str, dict[str, int]] = {}
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in links:
        fam = families.setdefault(SUBTYPES.get(link["kind"], slug(link["kind"], 40) + "_pdf"), {"found": 0, "taken": 0})
        fam["found"] += 1
        if link["kind"] != "Eligibility Verification Plan" or link["url"] in seen:
            continue
        seen.add(link["url"])
        fam["taken"] += 1
        stem = slug(link["url"].rsplit("/", 1)[-1].rsplit(".", 1)[0], 100)
        docs.append({
            "source_id": f"{jur}-cms-magi-verification-plan-{stem}",
            "jurisdiction": jur,
            "document_class": "policy",
            "title": f"{name} MAGI-based eligibility verification plan (42 CFR 435.945(j)) as posted by CMS",
            "source_url": link["url"],
            "source_format": "pdf",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": SOURCE_AS_OF,
            "citation_path": f"{jur}/policy/cms/magi-verification-plan/{stem}",
            "extraction": {"ocr": True},
            "metadata": {
                "primary_source": True,
                "source_authority": "Centers for Medicare & Medicaid Services (medicaid.gov)",
                "program": "MEDICAID",
                "state": name,
                "document_subtype": "magi_verification_plan_pdf",
                "index_link_text": link["title"],
                "source_discovery_group": f"{jur}/policy/cms-magi-verification-plan",
                "discovered_via": f"manual-review:medicaid-agent-queue wave-5 closure (2026-09-15); CMS verification-plan index {INDEX}",
                "publisher_note": "medicaid.gov answered the plain extractor client HTTP 200 (index and PDF) on 2026-09-14; TLS verified, no mirror",
                "carries_elements": "M-435-920 M-435-945 M-435-948 M-435-949 M-435-952 (closure schema plan_family)",
            },
        })
    return docs, {"index_url": INDEX, "families": families}


def queue_row(jur: str, docs: list[dict[str, Any]], info: dict[str, Any], seconds: float) -> dict[str, Any]:
    found = sum(f["found"] for f in info["families"].values())
    taken = sum(f["taken"] for f in info["families"].values())
    stem = f"{jur}-medicaid-magi-verification-plan"
    return {
        "jurisdiction": jur, "name": STATES[jur], "family": FAMILY, "lead_counts": {}, "candidate_sources": [],
        "target_manifest": f"manifests/{stem}.yaml",
        "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": VERSION},
        "queue_status": "agent_ready", "source_kind": "cms_posted_magi_verification_plan",
        "primary_source_url": docs[0]["source_url"], "index_url": INDEX,
        "index_document_count": found, "taken_count": taken, "index_families": info["families"],
        "notes": (f"MAGI verification plan row (2026-09-15, wave-5 closure): CMS posts the state's 42 CFR 435.945(j) MAGI-based "
                  f"eligibility verification plan on the medicaid.gov verification-plans index ({found} document(s) listed for the "
                  f"state; the verification plan taken, disaster addenda and mitigation plans inventoried and not taken). The plan is the "
                  f"closure schema's carrying family for 435.920/.945/.948/.949/.952 (SSN verification, verification plan, electronic "
                  f"data sources, hub verification, reasonable compatibility). Index fetched in {seconds:.1f} s with the plain extractor "
                  f"client (HTTP 200; no impersonation). Generator: scripts/build_medicaid_magi_verification_plan_manifests.py."),
    }


def update_queue(new_rows: dict[str, dict[str, Any]], missing: list[str]) -> dict[str, int]:
    """Insert or replace each jurisdiction's verification-plan row right after its last existing row."""
    queue = yaml.safe_load(QUEUE.read_text())
    states: list[dict[str, Any]] = [r for r in queue["states"] if not (r.get("family") == FAMILY and r["jurisdiction"] in new_rows)]
    for jur, row in new_rows.items():
        idx = max((i for i, r in enumerate(states) if r["jurisdiction"] == jur), default=None)
        states.insert(len(states) if idx is None else idx + 1, row)
    queue["states"] = states
    queue["status_counts"] = {}
    for row in states:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    note = (f"MAGI verification plan family (2026-09-15, wave-5 closure): one `family: {FAMILY}` row per state for the CMS-posted "
            f"MAGI-based eligibility verification plan ({INDEX}), version {VERSION}, document_class policy, citation root "
            f"us-xx/policy/cms/magi-verification-plan"
            + (f"; no plan is listed for {', '.join(missing)}" if missing else "")
            + ". Generator: scripts/build_medicaid_magi_verification_plan_manifests.py.")
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    queue["queue_status"] = "in_progress"
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append", default=[], metavar="JURISDICTION")
    args = parser.parse_args()
    page, seconds = fetch(INDEX)
    index = parse_index(page)
    missing = sorted(j for j in STATES if j not in index or not any(link["kind"] == "Eligibility Verification Plan" for link in index[j]))
    rows: dict[str, dict[str, Any]] = {}
    for jur in sorted(index):
        if args.only and jur not in args.only:
            continue
        docs, info = build(jur, index[jur])
        if not docs:
            print(f"{jur}: no verification plan listed ({[link["title"] for link in index[jur]]})", file=sys.stderr)
            continue
        (ROOT / "manifests" / f"{jur}-medicaid-magi-verification-plan.yaml").write_text(
            yaml.safe_dump({"version": VERSION, "documents": docs}, sort_keys=False, allow_unicode=True, width=120))
        rows[jur] = queue_row(jur, docs, info, seconds)
        print(f"{jur}: {len(docs)} document(s); families {info['families']}")
    counts = update_queue(rows, missing)
    print(f"states with a plan: {len(index)}; manifests written: {len(rows)}; no plan listed for: {missing}")
    print(f"queue {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
