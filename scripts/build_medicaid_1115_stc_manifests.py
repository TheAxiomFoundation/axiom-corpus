"""Build one official-document manifest per state for the current CMS approval document (special terms and
conditions) of the state's approved section 1115 demonstration(s) that set state-specific eligibility terms, and add a
`family: cms_1115_stc` row per target state to the Medicaid agent queue.

Wave-5 closure (2026-09-15, docs/ingest-runs/2026-09-15-medicaid-chip.md), M-ST-1315 for the thirteen states the
09-14 recount marked EXTRACTABLE (AK ID KY MT ND NE NV PA SC SD VA WI WY). medicaid.gov lists every demonstration in
the "Section 1115 Demonstration and Waiver List" (`/medicaid/section-1115-demo/demonstration-and-waiver-list`,
filterable by state and status); each demonstration page lists its documents with a posting date. The current
approval document (approval letter + special terms and conditions + waiver and expenditure-authority lists) is the
document that carries the eligibility terms. The list was read live on 2026-09-14 for the thirteen states with the
"Approved" status filter; the selection below is the eligibility-bearing approved demonstration(s) per state with the
newest "Demonstration Approval" (or "Amendment Approval" that re-issues the STCs) posted. Demonstrations that only
waive service or payment rules (SUD/SMI, HCBS 1915(c) waivers listed alongside, air ambulance, uncompensated care)
are not eligibility terms and are not taken. States whose eligibility demonstrations are pending, withdrawn,
terminated or expired have no STCs to take and get a queue row that says so (`ABSENT` in the decisions file).

Every selected link is re-read from the live demonstration page at build time; a link that is no longer listed
fails the build.

    uv run python scripts/build_medicaid_1115_stc_manifests.py
    uv run python scripts/build_medicaid_1115_stc_manifests.py --only us-wy
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
LIST = "https://www.medicaid.gov/medicaid/section-1115-demo/demonstration-and-waiver-list"
VERSION = "2026-09-15-medicaid-1115-stc"
SOURCE_AS_OF = "2026-09-15"
FAMILY = "cms_1115_stc"
UA = "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) https://github.com/TheAxiomFoundation/axiom-corpus"
NAMES = {"us-ak": "Alaska", "us-id": "Idaho", "us-ky": "Kentucky", "us-mt": "Montana", "us-nd": "North Dakota",
         "us-ne": "Nebraska", "us-nv": "Nevada", "us-pa": "Pennsylvania", "us-sc": "South Carolina",
         "us-sd": "South Dakota", "us-va": "Virginia", "us-wi": "Wisconsin", "us-wy": "Wyoming"}
# medicaid.gov state filter ids (from the list page's <select>), used for the primary_source_url of every row.
STATE_FILTER = {"us-ak": 896, "us-id": 986, "us-ky": 861, "us-mt": 911, "us-nd": 811, "us-ne": 851, "us-nv": 716,
                "us-pa": 961, "us-sc": 831, "us-sd": 846, "us-va": 866, "us-wi": 941, "us-wy": 981}

# (demonstration node id, demonstration title as listed, slug, approval-document file name, approval date, what it carries)
SELECTION: dict[str, list[tuple[int, str, str, str, str, str]]] = {
    "us-ky": [(81806, "TEAMKY (formerly KY HEALTH)", "teamky", "ky-teamky-appvl-03202025.pdf", "2025-03-20",
               "current STCs (technical corrections to the 2024-12-12 extension approval): SUD/SMI, reentry, former foster "
               "care youth from other states and the demonstration's eligibility and enrollment terms")],
    "us-mt": [(82401, "Montana Plan First", "plan-first", "mt-plan-first-ext-appvl-03292019.pdf", "2019-03-29",
               "the 2019 extension approval with the full STCs of the family-planning eligibility demonstration (women "
               "with income up to 211% FPL)"),
              (82401, "Montana Plan First", "plan-first-2025-amendment", "mt-plan-first-sti-std-adjtmnt-amndmnt-04302025.pdf",
               "2025-04-30", "the 2025 STI/STD adjustment amendment approval (letter and amended STC pages only; read with the "
               "2019 STCs)")],
    "us-pa": [(83081, "Pennsylvania Medicaid Coverage Former Foster Care Youth From a Different State & SUD Demonstration",
               "former-foster-care-youth-sud", "pa-former-foster-care-youth-diff-state-sud-dmnstrtn-appvl-11142024.pdf",
               "2024-11-14", "current STCs re-issued with the continuous-eligibility amendment: former foster care youth "
               "from another state eligibility group, SUD, continuous eligibility"),
              (159451, "Pennsylvania Keystones of Health", "keystones-of-health", "pa-keystones-of-health-ca-12262024.pdf",
               "2024-12-26", "STCs of the 2025-2029 demonstration: reentry pre-release coverage, HRSN, continuous "
               "eligibility for children up to age 6 and the demonstration populations")],
    "us-sd": [(83191, "South Dakota Former Foster Care Youth Demonstration", "former-foster-care-youth",
               "sd-ffcy-ext-appvl-10302023.pdf", "2023-10-30", "current STCs: former foster care youth from another state")],
    "us-va": [(83451, "Building and Transforming Coverage, Services, and Supports for a Healthier Virginia", "btcsshv",
               "va-btcsshv-1115-demo-rnwl-2026-apprvl-07312026.pdf", "2026-07-31",
               "2026 renewal STCs: ARTS, former foster care youth, GAP legacy populations, SMI, the demonstration's eligibility groups"),
              (83426, "Virginia FAMIS MOMS and FAMIS Select", "famis-moms-famis-select",
               "va-famis-moms-famis-select-11182021-ca.pdf", "2021-11-18",
               "current STCs: CHIP-funded pregnant women (FAMIS MOMS) and premium assistance (FAMIS Select) eligibility")],
    "us-wi": [(83631, "Wisconsin BadgerCare Reform", "badgercare-reform", "wi-badgercare-reform-demo-approval-05152025.pdf",
               "2025-05-12", "current STCs (2025-05-12 approval): childless adults up to 100% FPL, premiums, the "
               "demonstration's eligibility and enrollment terms; a 2024-12-23 expansion amendment is pending"),
              (83576, "Wisconsin SeniorCare", "seniorcare", "wi-senior-care-ca2.pdf", "2022-06-07",
               "current STCs (COVID-19 amendment approval, re-issued 2022-06-07 after the 2022-06-06 demonstration approval): "
               "prescription-drug coverage eligibility for residents 65+ by income band")],
    "us-wy": [(83646, "Wyoming Pregnant By Choice (Family Planning) Demonstration", "pregnant-by-choice",
               "wy-pregnant-by-choice-sti-std-adjtmnt-amndmnt-04302025.pdf", "2025-04-30",
               "current STCs of the family-planning eligibility demonstration (postpartum women losing Medicaid; STI/STD amendment)")],
}
# States whose listed 1115 demonstrations carry no approved eligibility terms (read on the live list 2026-09-14).
NO_STC: dict[str, str] = {
    "us-ak": "the only approved 1115 is Alaska Behavioral Health Reform (SUD/SMI service authority, approved 2024-03-26); the other "
             "listed items are 1915(c) waivers; no eligibility demonstration",
    "us-id": "Idaho Medicaid Reform Waiver is pending (no approval document); Idaho Childless Adults and Children's Access Card are "
             "legacy listings without a current approval; Idaho Medicaid Plus (ID-04) is a 1915(b) waiver; Idaho Behavioral Health "
             "Transformation is SUD/SMI",
    "us-nd": "no 1115 eligibility demonstration; the listed items are 1915(c) waivers, the ND-04 1915(b) managed-care waiver for the "
             "new adult group and the COVID-19 managed-care risk-mitigation demonstration",
    "us-ne": "Nebraska Heritage Health Adult 1115 (the expansion premium/wellness demonstration) was terminated at the state's request "
             "(CMS approval to terminate 2021-09-02); the SUD demonstration is service authority only",
    "us-nv": "Nevada Healthy Futures is pending; the Nevada Comprehensive Care Waiver approvals are 2014-2015 STC amendments of an "
             "expired demonstration; SUD/OUD, reentry and CCBHC demonstrations are service authority",
    "us-sc": "Healthy Connections Works and Palmetto Pathways to Independence (community engagement, 2019 approvals) are withdrawn; "
             "the 2025 Palmetto Pathways and Transitioning to Preconception Care applications are pending",
}


def fetch(url: str) -> tuple[str, float]:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    resp.raise_for_status()
    return resp.text, resp.elapsed.total_seconds()


def demonstration_page(node: int) -> str:
    return f"{LIST}/{node}"


def list_url(jur: str) -> str:
    return f"{LIST}?filter%5Bfield_state%5D%5Bin%5D%5B%5D={STATE_FILTER[jur]}&filter%5Bfield_status%5D%5Bin%5D%5B%5D=1561&limit=100"


_LINK_RE = re.compile(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', re.S | re.I)


def find_link(page: str, base: str, file_name: str) -> tuple[str, str]:
    """Return (absolute url, link text) of the listed PDF whose file name matches."""
    for href, text in _LINK_RE.findall(page):
        href = html.unescape(href)
        if href.rsplit("/", 1)[-1] == file_name:
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
            return urljoin(base, href), text
    raise RuntimeError(f"{file_name} is not listed on {base}")


def build(jur: str) -> tuple[list[dict[str, Any]], dict[str, Any], float]:
    docs: list[dict[str, Any]] = []
    families: dict[str, dict[str, int]] = {"approved_eligibility_demonstration_stc_pdf": {"found": 0, "taken": 0}}
    total = 0.0
    for node, title, dslug, file_name, approval_date, carries in SELECTION[jur]:
        page_url = demonstration_page(node)
        page, seconds = fetch(page_url)
        total += seconds
        url, link_text = find_link(page, page_url, file_name)
        families["approved_eligibility_demonstration_stc_pdf"]["found"] += 1
        families["approved_eligibility_demonstration_stc_pdf"]["taken"] += 1
        docs.append({
            "source_id": f"{jur}-cms-1115-stc-{dslug}",
            "jurisdiction": jur,
            "document_class": "policy",
            "title": f"{NAMES[jur]} section 1115 demonstration \"{title}\": CMS approval document and special terms and conditions ({approval_date})",
            "source_url": url,
            "source_format": "pdf",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": approval_date,
            "citation_path": f"{jur}/policy/cms/1115-stc/{dslug}",
            "extraction": {"ocr": True},
            "metadata": {
                "primary_source": True,
                "source_authority": "Centers for Medicare & Medicaid Services (medicaid.gov)",
                "program": "MEDICAID",
                "state": NAMES[jur],
                "document_subtype": "cms_1115_approval_and_stc_pdf",
                "demonstration_title": title,
                "demonstration_page": page_url,
                "index_link_text": link_text,
                "approval_date": approval_date,
                "carries": carries,
                "source_discovery_group": f"{jur}/policy/cms-1115-stc",
                "discovered_via": f"manual-review:medicaid-agent-queue wave-5 closure (2026-09-15); CMS 1115 demonstration list {list_url(jur)}",
                "publisher_note": "medicaid.gov answered the plain extractor client HTTP 200 (list, demonstration page and PDF) on 2026-09-14; TLS verified, no mirror",
                "carries_elements": "M-ST-1315 (closure schema: CMS-approved 1115 demonstration special terms and conditions)",
            },
        })
    return docs, {"index_url": list_url(jur), "families": families}, total


def row_base(jur: str) -> dict[str, Any]:
    return {"jurisdiction": jur, "name": NAMES[jur], "family": FAMILY, "lead_counts": {}, "candidate_sources": [],
            "target_manifest": f"manifests/{jur}-medicaid-1115-stc.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": VERSION},
            "primary_source_url": list_url(jur), "index_url": list_url(jur)}


def update_queue(new_rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    queue = yaml.safe_load(QUEUE.read_text())
    states: list[dict[str, Any]] = [r for r in queue["states"] if not (r.get("family") == FAMILY and r["jurisdiction"] in new_rows)]
    for jur, row in new_rows.items():
        idx = max((i for i, r in enumerate(states) if r["jurisdiction"] == jur), default=None)
        states.insert(len(states) if idx is None else idx + 1, row)
    queue["states"] = states
    queue["status_counts"] = {}
    for row in states:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    note = (f"CMS 1115 STC family (2026-09-15, wave-5 closure): one `family: {FAMILY}` row per M-ST-1315 target state (AK ID KY MT "
            f"ND NE NV PA SC SD VA WI WY) for the current CMS approval document and special terms and conditions of the state's "
            f"approved eligibility demonstration(s) on {LIST}, version {VERSION}, document_class policy, citation root "
            f"us-xx/policy/cms/1115-stc; states with no approved eligibility demonstration keep a row with the reason. "
            f"Generator: scripts/build_medicaid_1115_stc_manifests.py.")
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
    rows: dict[str, dict[str, Any]] = {}
    for jur in sorted(NAMES):
        if args.only and jur not in args.only:
            continue
        row = row_base(jur)
        if jur in SELECTION:
            docs, info, seconds = build(jur)
            (ROOT / "manifests" / f"{jur}-medicaid-1115-stc.yaml").write_text(
                yaml.safe_dump({"version": VERSION, "documents": docs}, sort_keys=False, allow_unicode=True, width=120))
            row.update({
                "queue_status": "agent_ready", "source_kind": "cms_posted_1115_approval_and_stc",
                "index_document_count": len(docs), "taken_count": len(docs), "index_families": info["families"],
                "notes": (f"CMS 1115 STC row (2026-09-15, wave-5 closure): {len(docs)} approved eligibility demonstration(s) with "
                          f"the current approval document (STCs) taken from the demonstration page(s) "
                          f"{', '.join(demonstration_page(s[0]) for s in SELECTION[jur])} (plain extractor client, HTTP 200, "
                          f"{seconds:.1f} s). Service-only demonstrations (SUD/SMI, reentry, CCBHC) and the 1915(b)/(c) waivers "
                          f"listed alongside are not taken. Generator: scripts/build_medicaid_1115_stc_manifests.py."),
            })
            print(f"{jur}: {len(docs)} document(s)")
        else:
            row.update({
                "target_manifest": None, "queue_status": "needs_review", "source_kind": "cms_posted_1115_approval_and_stc",
                "index_document_count": 0, "taken_count": 0, "index_families": {},
                "notes": (f"CMS 1115 STC row (2026-09-15, wave-5 closure): nothing taken; {NO_STC[jur]} (read on the live list with "
                          f"the Approved filter, 2026-09-14). M-ST-1315 is ABSENT for the state until an eligibility demonstration is "
                          f"approved. Generator: scripts/build_medicaid_1115_stc_manifests.py."),
            })
            print(f"{jur}: no approved eligibility demonstration ({NO_STC[jur][:60]}...)", file=sys.stderr)
        rows[jur] = row
    counts = update_queue(rows)
    print(f"queue {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
