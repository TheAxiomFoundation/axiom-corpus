"""Build one corpus manifest per jurisdiction for the FY 2026 LIHEAP Detailed Model
Plans published by the ACF LIHEAP Clearinghouse, and update the LIHEAP agent queue.

Primary official source: https://liheapch.acf.gov/stateplans.htm (HHS/ACF Office of
Community Services). The server omits its TLS intermediate certificate
(Entrust DV TLS Issuing RSA CA 2, chained to Sectigo Public Server Authentication
Root R46); data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem is that public
intermediate, fetched from the certificate's own AIA URL. Run extraction with
REQUESTS_CA_BUNDLE pointing at certifi + that file. No verification is disabled.

    uv run python scripts/build_liheap_state_plan_manifests.py
"""
from __future__ import annotations

import datetime as dt
import html
import re
import sys
from pathlib import Path

import certifi
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
INDEX = "https://liheapch.acf.gov/stateplans.htm"
BASE = "https://liheapch.acf.gov"
INTERMEDIATE = ROOT / "data" / "certs" / "entrust-dv-tls-issuing-rsa-ca-2.pem"
SOURCE_AS_OF = dt.date.today().isoformat()
EXPRESSION_DATE = "2025-10-01"          # FY 2026 plans cover 10/01/2025 - 09/30/2026
FY = "2026"

FORM_DROP = [
    r"^Page \d+ of \d+$",
    r"^August 1987, revised .*$",
    r"^U\.S\. DEPARTMENT OF HEALTH AND HUMAN SERVICES$",
    r"^ADMINISTRATION FOR CHILDREN AND FAMILIES$",
    r"^OMB Clearance No\.?:.*$",
    r"^Expiration Date:.*$",
    r"^LOW INCOME HOME ENERGY ASSISTANCE PROGRAM ?\(LIHEAP\)$",
    r"^MODEL PLAN$",
    r"^DETAILED MODEL PLAN \(LIHEAP\)$",
]
EXTRACTION = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^Section (?P<label>\d{1,2})\s*[-:]\s*(?P<heading>\S.*)$",
    "drop_line_patterns": FORM_DROP,
    # page 1 is the OLDC table of contents, whose entries repeat every section heading
    "start_after_pattern": r"^(?:\d+\.\s*)?Plan Attachments$",
}


def ca_bundle() -> Path:
    out = ROOT / "data" / "certs" / "liheapch-ca-bundle.pem"
    out.write_text(Path(certifi.where()).read_text() + "\n" + INTERMEDIATE.read_text())
    return out


def main() -> int:
    bundle = ca_bundle()
    resp = requests.get(INDEX, headers={"User-Agent": "axiom-corpus/0.1 (source discovery)"}, timeout=60, verify=str(bundle))
    resp.raise_for_status()
    page = resp.text
    links = re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
    plans = []
    for href, text in links:
        m = re.search(rf"/docs/{FY}/state-plans/([A-Z]{{2}})_Plan_{FY}\.pdf$", href)
        if not m:
            continue
        code = m.group(1)
        name = re.sub(r"<[^>]+>", "", html.unescape(text)).strip()
        plans.append((code, name, href if href.startswith("http") else BASE + href))
    seen = set()
    plans = [p for p in plans if not (p[0] in seen or seen.add(p[0]))]
    if len(plans) < 50:
        print(f"only {len(plans)} plans found; index layout changed?", file=sys.stderr)
        return 1
    queue_path = ROOT / "manifests" / "liheap-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}
    written = []
    for code, name, url in sorted(plans):
        jur = f"us-{code.lower()}"
        stem = f"{jur}-liheap-state-plan-fy{FY}"
        doc = {
            "source_id": f"{jur}-acf-liheap-plan-fy{FY}",
            "jurisdiction": jur,
            "document_class": "policy",
            "title": f"{name} LIHEAP Detailed Model Plan, FY {FY}",
            "source_url": url,
            "source_format": "pdf",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": EXPRESSION_DATE,
            "citation_path": f"{jur}/policy/acf/liheap-plan/fy{FY}",
            "extraction": EXTRACTION,
            "metadata": {
                "primary_source": True,
                "source_authority": "HHS Administration for Children and Families, Office of Community Services (LIHEAP Clearinghouse)",
                "document_subtype": "state_plan_pdf",
                "program": "LIHEAP",
                "fiscal_year": FY,
                "report_period": f"2025-10-01 to {FY}-09-30",
                "source_discovery_group": f"{jur}/policy/liheap",
                "discovered_via": "manual-review:liheap-agent-queue; index https://liheapch.acf.gov/stateplans.htm",
                "tls_note": "server omits its intermediate certificate; extraction uses REQUESTS_CA_BUNDLE = certifi + data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem",
            },
        }
        manifest = {"version": SOURCE_AS_OF, "documents": [doc]}
        (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
        written.append(stem)
        row = rows.get(jur) or {"jurisdiction": jur, "name": name, "lead_counts": {}, "candidate_sources": []}
        row.update({
            "name": name, "queue_status": "agent_ready", "source_kind": "official_pdf_state_plan",
            "primary_source_url": url, "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": SOURCE_AS_OF},
            "notes": f"FY {FY} Detailed Model Plan from the ACF LIHEAP Clearinghouse index. Primary source confirmed by the agent from the publisher's index; agency policy manuals listed there are a separate, later document family.",
        })
        rows[jur] = row
    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue["queue_status"] = "in_progress"
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"wrote {len(written)} manifests; queue {queue['status_counts']}; ca bundle {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
