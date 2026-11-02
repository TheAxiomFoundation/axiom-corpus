"""Build one official-document manifest per state for the annual Medicaid / CHIP income-level (and premium) table the
state agency posts, and add a `family: income_table` row to the Medicaid or CHIP agent queue.

Wave-5 closure (2026-09-15, docs/ingest-runs/2026-09-15-medicaid-chip.md), M-SS-INCOME-TABLE and
C-SS-INCOME-PREMIUM-TABLE. The 09-14 check accepts the CMS 2023-12-01 eligibility-levels compilation for the group
standards but not for a current-year table, so the state's own posted table is the carrying document. Each publisher
below was probed once on 2026-09-15 with the plain extractor client; the table is taken where the agency posts one as
text (an HTML page or a text-layer PDF) and every selected page is re-read live at build time (a page that stops
answering or loses its content selector fails the build).

    uv run python scripts/build_medicaid_income_table_manifests.py
    uv run python scripts/build_medicaid_income_table_manifests.py --only us-mn
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
QUEUES = {"MEDICAID": ROOT / "manifests" / "medicaid-agent-queue.yaml", "CHIP": ROOT / "manifests" / "chip-agent-queue.yaml"}
VERSIONS = {"MEDICAID": "2026-09-15-medicaid-income-table-2026", "CHIP": "2026-09-15-chip-income-premium-table-2026"}
SOURCE_AS_OF = "2026-09-15"
FAMILY = "income_table"
UA = "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) https://github.com/TheAxiomFoundation/axiom-corpus"

# jurisdiction -> (program, name, document class, citation path, source url, format, title, authority, index url,
#                  html content selector or None, expression date, what it carries)
SELECTION: dict[str, tuple[str, ...]] = {
    "us-mn": ("MEDICAID", "Minnesota", "manual", "us-mn/manual/dhs/medicaid/appendix-f",
              "https://hcopub.dhs.state.mn.us/epm/appendix_f.htm", "html",
              "Minnesota Health Care Programs Eligibility Policy Manual (EPM): Appendix F Standards and Guidelines",
              "Minnesota Department of Human Services", "https://hcopub.dhs.state.mn.us/epm/home.htm", "#rh-topic",
              SOURCE_AS_OF,
              "the EPM's standards appendix: federal poverty guidelines, MA income and asset standards, community spouse "
              "allowances, MinnesotaCare income limits and the pointer to the MinnesotaCare premium table (DHS-4139); the one "
              "EPM topic the 2026-09-10 scope left untaken; carries M-SS-INCOME-TABLE and, for MinnesotaCare, C-SS-INCOME-PREMIUM-TABLE"),
    "us-id": ("MEDICAID", "Idaho", "policy", "us-id/policy/dhw/medicaid/program-income-limits",
              "https://healthandwelfare.idaho.gov/medicaid-program-income-limits", "html",
              "Idaho Department of Health and Welfare: Medicaid Program Income Limits (2026)",
              "Idaho Department of Health and Welfare", "https://healthandwelfare.idaho.gov/services-programs/medicaid-health/apply-medicaid",
              "article", SOURCE_AS_OF,
              "the agency's per-program income-limit tables (13 tables, household size by dollar amount, 2026); carries M-SS-INCOME-TABLE"),
    "us-sc": ("CHIP", "South Carolina", "policy", "us-sc/policy/scdhhs/medicaid/program-eligibility-and-income-limits",
              "https://www.scdhhs.gov/members/program-eligibility-and-income-limits", "html",
              "South Carolina Healthy Connections Medicaid: Program Eligibility and Income Limits (effective 2026-03-01)",
              "South Carolina Department of Health and Human Services", "https://www.scdhhs.gov/members/program-eligibility-and-income-limits",
              "#content", SOURCE_AS_OF,
              "the agency's per-program income and resource limit tables (12 tables, monthly and annual by family size, effective "
              "03/01/2026), including Partners for Healthy Children (CHIP); carries C-SS-INCOME-PREMIUM-TABLE (no CHIP premiums in SC) "
              "and M-SS-INCOME-TABLE"),
    "us-me": ("CHIP", "Maine", "policy", "us-me/policy/dhhs/mainecare/eligibility-guidelines-2026",
              "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/2026%20MaineCare%20Eligibility%20Guidelines%206.23..26_1.pdf",
              "pdf", "Maine DHHS: 2026 MaineCare Eligibility Guidelines chart (6.23.26)",
              "Maine Department of Health and Human Services, Office for Family Independence",
              "https://www.maine.gov/dhhs/ofi/programs-services/health-care-assistance", None, "2026-06-23",
              "the annual eligibility-guidelines chart: monthly income limits by household size and FPL percentage for every "
              "MaineCare and CubCare coverage group; carries C-SS-INCOME-PREMIUM-TABLE and M-SS-INCOME-TABLE"),
}


def fetch(url: str) -> requests.Response:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    resp.raise_for_status()
    return resp


def confirm(jur: str, spec: tuple[str, ...]) -> tuple[int, float]:
    """Re-read the page: return (text length under the selector, seconds); fail if the selector is gone."""
    _prog, _name, _cls, _path, url, fmt, _title, _auth, _index, selector, _date, _carries = spec
    resp = fetch(url)
    if fmt == "pdf":
        if not resp.content.startswith(b"%PDF"):
            raise RuntimeError(f"{jur}: {url} is not a PDF")
        return len(resp.content), resp.elapsed.total_seconds()
    soup = BeautifulSoup(resp.text, "html.parser")
    node = soup.select_one(selector) if selector else soup.body
    if node is None:
        raise RuntimeError(f"{jur}: selector {selector!r} not found on {url}")
    text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
    if len(text) < 1000 or not re.search(r"\$\s?\d", text):
        raise RuntimeError(f"{jur}: content under {selector!r} is {len(text)} chars without dollar amounts")
    return len(text), resp.elapsed.total_seconds()


def document(jur: str, spec: tuple[str, ...]) -> dict[str, Any]:
    prog, name, cls, path, url, fmt, title, authority, index, selector, date, carries = spec
    doc: dict[str, Any] = {
        "source_id": f"{jur}-{FAMILY}-{path.rsplit('/', 1)[-1]}",
        "jurisdiction": jur, "document_class": cls, "title": title, "source_url": url, "source_format": fmt,
        "source_as_of": SOURCE_AS_OF, "expression_date": date, "citation_path": path,
    }
    if fmt == "pdf":
        doc["extraction"] = {"ocr": True}
    else:
        doc["extraction"] = {"html_content_selector": selector, "html_drop_selectors": ["nav", "header", "footer", "script", "style", "p.Footer"]}
    doc["metadata"] = {
        "primary_source": True, "source_authority": authority, "program": prog, "state": name,
        "document_subtype": "annual_income_table_" + fmt, "table_index_url": index, "carries": carries,
        "source_discovery_group": f"{jur}/{cls}/{FAMILY}",
        "discovered_via": f"manual-review:{prog.lower()}-agent-queue wave-5 closure (2026-09-15); publisher index {index}",
        "publisher_note": "publisher answered the plain extractor client HTTP 200 on 2026-09-15; TLS verified, no mirror",
        "carries_elements": "M-SS-INCOME-TABLE C-SS-INCOME-PREMIUM-TABLE",
    }
    return doc


def update_queue(prog: str, new_rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    queue_path = QUEUES[prog]
    queue = yaml.safe_load(queue_path.read_text())
    states = [r for r in queue["states"] if not (r.get("family") == FAMILY and r["jurisdiction"] in new_rows)]
    for jur, row in new_rows.items():
        idx = max((i for i, r in enumerate(states) if r["jurisdiction"] == jur), default=None)
        states.insert(len(states) if idx is None else idx + 1, row)
    queue["states"] = states
    queue["status_counts"] = {}
    for row in states:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    note = (f"Income table family (2026-09-15, wave-5 closure): `family: {FAMILY}` rows for the annual income-level / premium "
            f"table the agency posts as text, version {VERSIONS[prog]}, citation path per state. "
            f"Generator: scripts/build_medicaid_income_table_manifests.py.")
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    queue["queue_status"] = "in_progress"
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append", default=[], metavar="JURISDICTION")
    args = parser.parse_args()
    rows: dict[str, dict[str, dict[str, Any]]] = {"MEDICAID": {}, "CHIP": {}}
    for jur, spec in sorted(SELECTION.items()):
        if args.only and jur not in args.only:
            continue
        prog, name, cls, path, url, fmt, _title, _auth, index, _sel, _date, carries = spec
        size, seconds = confirm(jur, spec)
        doc = document(jur, spec)
        stem = f"{jur}-{prog.lower()}-income-table"
        (ROOT / "manifests" / f"{stem}.yaml").write_text(
            yaml.safe_dump({"version": VERSIONS[prog], "documents": [doc]}, sort_keys=False, allow_unicode=True, width=120))
        rows[prog][jur] = {
            "jurisdiction": jur, "name": name, "family": FAMILY, "lead_counts": {}, "candidate_sources": [],
            "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": cls, "version": VERSIONS[prog]},
            "queue_status": "agent_ready", "source_kind": "official_annual_income_table",
            "primary_source_url": url, "index_url": index, "index_document_count": 1, "taken_count": 1,
            "index_families": {"annual_income_table_" + fmt: {"found": 1, "taken": 1}},
            "notes": (f"Income table row (2026-09-15, wave-5 closure): {carries}. Fetched with the plain extractor client "
                      f"(HTTP 200, {size:,} {'bytes' if fmt == 'pdf' else 'characters under the content selector'}, "
                      f"{seconds:.1f} s). Generator: scripts/build_medicaid_income_table_manifests.py."),
        }
        print(f"{jur}: {prog} {path} ({size:,} {'bytes' if fmt == 'pdf' else 'chars'})")
    for prog, new_rows in rows.items():
        if new_rows:
            print(f"{prog}: queue {update_queue(prog, new_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
