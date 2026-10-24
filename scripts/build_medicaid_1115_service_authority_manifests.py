"""Build one official-document manifest per state for the current CMS approval documents of the state's approved
section 1115 *service-authority* demonstration, and add a `family: cms_1115_service_authority` row per state to the
Medicaid agent queue.

Wave 8 (2026-10-20, docs/ingest-runs/2026-10-20-w8-medicaid-1115-behavioral-health.md). This is a sibling family of
`cms_1115_stc`, not a widening of it. `cms_1115_stc` takes the special terms and conditions of demonstrations that set
state-specific *eligibility* terms; its selection rule (see the generator docstring of
scripts/build_medicaid_1115_stc_manifests.py and the family note in manifests/medicaid-agent-queue.yaml) excludes
SUD/SMI, reentry, CCBHC, dental and payment demonstrations as service authority. Its version
`2026-09-15-medicaid-1115-stc` sits in two signed releases and is immutable. The two live behavioural-health
demonstrations therefore get their own family, their own version `2026-10-20-w8-medicaid-1115-service-authority` and
their own citation root `us-xx/policy/cms/1115-service-authority`, so a consumer can tell the two kinds apart by
citation path alone and the wave-5 rule stays exactly as written.

Selection, per demonstration, is what the publisher's own demonstration page posts as current: the approval letter, the
special terms and conditions, and the waiver and expenditure authority lists, excluding every superseded, expired or
pending posting. Every selected link is re-read from the live demonstration page at build time; a link that is no
longer listed, or that has moved out of the page section it was selected from, fails the build. The fetch helper
enforces the body rule in code: a 200 whose body carries a bot-challenge marker, or which lacks the publisher's own
page furniture, fails the build, so a silent challenge cannot pass as a page that no longer lists a document.

    uv run python scripts/build_medicaid_1115_service_authority_manifests.py
    uv run python scripts/build_medicaid_1115_service_authority_manifests.py --only us-ak
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "manifests" / "medicaid-agent-queue.yaml"
LIST = "https://www.medicaid.gov/medicaid/section-1115-demo/demonstration-and-waiver-list"
VERSION = "2026-10-20-w8-medicaid-1115-service-authority"
SOURCE_AS_OF = "2026-10-20"
FAMILY = "cms_1115_service_authority"
UA = "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) https://github.com/TheAxiomFoundation/axiom-corpus"
NAMES = {"us-ak": "Alaska", "us-id": "Idaho"}
# medicaid.gov state filter ids (from the list page's <select>), used for the primary_source_url of every row.
STATE_FILTER = {"us-ak": 896, "us-id": 986}
# The demonstration page each state's service-authority selection is read from, with its printed status line.
DEMONSTRATION = {
    "us-ak": (80966, "Alaska Behavioral Health Reform", "11-W-00411/7", "Approved",
              "approval 2018-11-21, effective 2019-01-01, expiration 2028-12-31"),
    "us-id": (81511, "Idaho Behavioral Health Transformation", "11-W-00339/10", "Pending",
              "approval 2020-04-17, effective 2020-04-17, expiration 2027-03-31"),
}
# Bot-challenge markers. "challenge-platform" is deliberately absent: Cloudflare injects that passive telemetry
# into genuine pages, so matching on it would reject real content.
CHALLENGE_MARKERS = ("attention required! | cloudflare", "just a moment...", "bobcmn", "cf_chl_opt", "chk_jschl",
                     "checking your browser", "incapsula", "incap_ses", "radware", "tspd", "captcha")
# Furniture the publisher's own demonstration page always carries.
FURNITURE = ("| Medicaid</title>", "Waiver Authority", "Supporting Documents")

# (page section the document is listed under, file name, slug, posted date, whether the PDF needs OCR, what it carries)
SELECTION: dict[str, list[tuple[str, str, str, str, bool, str]]] = {
    "us-ak": [
        ("Approved Application(s) and Related Documents", "ak-bhr-tech-correct-appvl-03272026.pdf",
         "behavioral-health-reform", "2026-03-27", False,
         "the current approved terms of the behavioural-health service-authority demonstration: the CMS approval letter, "
         "the waiver authority list, the expenditure authority list and the full special terms and conditions for the "
         "2024-03-26 to 2028-12-31 approval period, re-issued with corrected per member per month expenditure limits for "
         "the Medicaid Expenditure Groups that the original extension STCs mislabelled. SUD and SMI service authority; it "
         "sets no state-specific eligibility group"),
    ],
    "us-id": [
        ("Administrative Record", "id-behavioral-health-transformation-dmntsn-aprvl-ca-03292024.pdf",
         "behavioral-health-transformation", "2024-03-29", True,
         "the special terms and conditions, waiver authority list and expenditure authority list of the demonstration as "
         "approved 2020-04-17 and amended and restated 2024-03-29; the 2026-08-28 temporary extension approval states that "
         "these STCs and expenditure authorities continue to apply. SUD and SMI service authority; it sets no "
         "state-specific eligibility group"),
        ("Administrative Record", "id-behavioral-health-transformation-dmntsn-aprvl-amndmnt-ca-05152025.pdf",
         "behavioral-health-transformation-2025-amendment", "2025-05-15", True,
         "Attachment G, appended to the STCs effective 2025-05-15: it removes the expenditure authority that let legally "
         "responsible individuals provide 1905(a) personal care services, 60 calendar days after the effective date. Read "
         "with the 2024-03-29 amended and restated STCs; the letter records that the amendment does not affect Medicaid "
         "eligibility"),
        ("Approved Application(s) and Related Documents", "ID-BHT-ext-apprvl-letter-08282026.pdf",
         "behavioral-health-transformation-temporary-extension", "2026-08-28", False,
         "the approval in force: it extends the demonstration to 2027-03-31 while CMS and the state negotiate the "
         "2025-03-12 extension application, and states that the current STCs, expenditure authority and budget neutrality "
         "agreement continue to apply during the temporary extension"),
    ],
}
# Titles, per slug, and the document_subtype each selected posting is recorded under.
TITLES: dict[str, tuple[str, str]] = {
    "behavioral-health-reform": (
        "CMS technical correction approval, waiver and expenditure authorities and special terms and conditions, approval "
        "period 2024-03-26 to 2028-12-31", "cms_1115_approval_and_stc_pdf"),
    "behavioral-health-transformation": (
        "CMS amended and restated approval, waiver and expenditure authorities and special terms and conditions",
        "cms_1115_approval_and_stc_pdf"),
    "behavioral-health-transformation-2025-amendment": (
        "CMS amendment approval and Attachment G amendments to the expenditure authorities and special terms and conditions",
        "cms_1115_amendment_approval_pdf"),
    "behavioral-health-transformation-temporary-extension": (
        "CMS temporary extension approval through 2027-03-31", "cms_1115_temporary_extension_approval_pdf"),
}
# Postings the publisher's own page serves that are deliberately not taken, per state.
NOT_TAKEN: dict[str, str] = {
    "us-ak": "the 2024-03-26 Behavioral Health Reform Approval and the 2023-11-03 SUD-BHP Demonstration Approval sit in the "
             "page's Administrative Record; the 2026-03-27 technical correction restates the same approval period in full "
             "and is the only posting under Approved Application(s), so the earlier two are superseded and not taken",
    "us-id": "the earlier CMS Temporary Extension Approvals (2025-09-25 under Approved Application(s), 2025-03-31 in the "
             "Administrative Record) cover expired extension periods, the 2025-03-12 Pending Application - Extension is "
             "pending, and the pre-2024 Demonstration Approvals are superseded by the 2024-03-29 amended and restated "
             "approval; none of them is taken",
}
_LINK_RE = re.compile(r'<a[^>]+href="([^"]+\.(?:pdf|docx?|xlsx?|xlsm|zip))"[^>]*>(.*?)</a>', re.S | re.I)
_SECTION_RE = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S)


def _text(markup: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", markup))).strip()


def fetch(url: str) -> tuple[str, float]:
    """Fetch ``url`` with the corpus client, judging the response by its body and never by its status line."""
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    resp.raise_for_status()
    body = resp.text
    hits = [m for m in CHALLENGE_MARKERS if m in body.lower()]
    if hits:
        raise RuntimeError(f"{url} answered a bot-challenge body ({len(body)} chars, markers {hits})")
    missing = [f for f in FURNITURE if f not in body]
    if missing:
        raise RuntimeError(f"{url} body lacks the publisher's own page furniture {missing} ({len(body)} chars)")
    return body, resp.elapsed.total_seconds()


def demonstration_page(node: int) -> str:
    return f"{LIST}/{node}"


def list_url(jur: str) -> str:
    return f"{LIST}?filter%5Bfield_state%5D%5Bin%5D%5B%5D={STATE_FILTER[jur]}&filter%5Bfield_status%5D%5Bin%5D%5B%5D=1561&limit=100"


def page_sections(page: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split a demonstration page into (section heading, [(href, link text), ...]) in document order."""
    main = re.search(r"<main[^>]*>(.*?)</main>", page, re.S)
    body = main.group(1) if main else page
    parts = _SECTION_RE.split(body)
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    heading = "(top)"
    for index, part in enumerate(parts):
        if index % 2:
            heading = _text(part)
            continue
        links = [(html.unescape(href), _text(label)) for href, label in _LINK_RE.findall(part)]
        if links:
            sections.append((heading, links))
    return sections


def classify(label: str) -> str:
    """Group one posted document by what it is, for the queue row's `index_families` inventory."""
    lowered = label.lower()
    if any(k in lowered for k in ("monitoring report", "quarterly", "annual monitoring", "retrospective monitoring",
                                 "availability assessment", "metrics report")):
        return "monitoring_report"
    if any(k in lowered for k in ("evaluation", "mid-point assessment")):
        return "evaluation_document"
    if "approval" in lowered:
        return "approval_document"
    if any(k in lowered for k in ("acceptance letter", "letter from state", "overlay letter", "completeness letter")):
        return "correspondence"
    if "application" in lowered:
        return "application"
    return "other"


def find_link(sections: list[tuple[str, list[tuple[str, str]]]], base: str, section: str,
              file_name: str) -> tuple[str, str]:
    """Return (absolute url, link text) of the listed file, requiring it to still sit in ``section``."""
    for heading, links in sections:
        for href, label in links:
            if href.rsplit("/", 1)[-1] != file_name:
                continue
            if heading != section:
                raise RuntimeError(f"{file_name} moved from '{section}' to '{heading}' on {base}")
            return urljoin(base, href), label
    raise RuntimeError(f"{file_name} is not listed on {base}")


def build(jur: str) -> tuple[list[dict[str, Any]], dict[str, Any], float]:
    node, demo_title, demo_number, printed_status, printed_dates = DEMONSTRATION[jur]
    page_url = demonstration_page(node)
    page, seconds = fetch(page_url)
    sections = page_sections(page)
    families: dict[str, dict[str, int]] = {}
    for heading, links in sections:
        for _, label in links:
            bucket = families.setdefault(f"{heading}: {classify(label)}", {"found": 0, "taken": 0})
            bucket["found"] += 1
    docs: list[dict[str, Any]] = []
    for section, file_name, slug, approval_date, needs_ocr, carries in SELECTION[jur]:
        url, link_text = find_link(sections, page_url, section, file_name)
        families[f"{section}: {classify(link_text)}"]["taken"] += 1
        summary, subtype = TITLES[slug]
        doc: dict[str, Any] = {
            "source_id": f"{jur}-cms-1115-service-authority-{slug}",
            "jurisdiction": jur,
            "document_class": "policy",
            "title": f'{NAMES[jur]} section 1115 demonstration "{demo_title}": {summary} ({approval_date})',
            "source_url": url,
            "source_format": "pdf",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": approval_date,
            "citation_path": f"{jur}/policy/cms/1115-service-authority/{slug}",
        }
        if needs_ocr:
            doc["extraction"] = {"ocr": True}
        doc["metadata"] = {
            "primary_source": True,
            "source_authority": "Centers for Medicare & Medicaid Services (medicaid.gov)",
            "program": "MEDICAID",
            "state": NAMES[jur],
            "document_subtype": subtype,
            "demonstration_title": demo_title,
            "demonstration_number": demo_number,
            "demonstration_page": page_url,
            "demonstration_authority_kind": "service_authority",
            "index_link_text": link_text,
            "index_section": section,
            "printed_status": printed_status,
            "printed_waiver_dates": printed_dates,
            "approval_date": approval_date,
            "carries": carries,
            "source_discovery_group": f"{jur}/policy/cms-1115-service-authority",
            "discovered_via": f"manual-review:medicaid-agent-queue wave-8 (2026-10-20); CMS 1115 demonstration list {list_url(jur)}",
            "publisher_note": "medicaid.gov answered the plain extractor client HTTP 200 (list, demonstration page and PDF) "
                              "on 2026-10-20 at 9 to 12 second pacing; bodies carry the publisher's own page furniture and "
                              "no bot-challenge marker; TLS verified, no mirror",
            "supersedes_note": NOT_TAKEN[jur],
            "carries_elements": "M-ST-1315 adjacent (service authority, not an eligibility demonstration): CMS-approved 1115 "
                                "demonstration special terms and conditions",
        }
        docs.append(doc)
    index_count = sum(bucket["found"] for bucket in families.values())
    return docs, {"families": dict(sorted(families.items())), "index_url": page_url,
                  "index_document_count": index_count, "printed_status": printed_status}, seconds


def row(jur: str, docs: list[dict[str, Any]], info: dict[str, Any], seconds: float) -> dict[str, Any]:
    node, demo_title, _, printed_status, printed_dates = DEMONSTRATION[jur]
    return {
        "jurisdiction": jur, "name": NAMES[jur], "family": FAMILY, "lead_counts": {}, "candidate_sources": [],
        "target_manifest": f"manifests/{jur}-medicaid-1115-service-authority.yaml",
        "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": VERSION},
        "primary_source_url": list_url(jur),
        "index_url": info["index_url"],
        "queue_status": "agent_ready",
        "source_kind": "cms_posted_1115_approval_and_stc",
        "index_document_count": info["index_document_count"],
        "taken_count": len(docs),
        "index_families": info["families"],
        "notes": (f"CMS 1115 service-authority row (2026-10-20, wave 8): sibling family of `cms_1115_stc`, which stays as "
                  f"written. \"{demo_title}\" prints Status {printed_status} ({printed_dates}) on its own medicaid.gov page, "
                  f"which answered the plain extractor client HTTP 200 in {seconds:.1f} s. "
                  f"{info['index_document_count']} posted documents inventoried by page section, {len(docs)} taken under "
                  f"version {VERSION}, citation root {jur}/policy/cms/1115-service-authority. Not taken: {NOT_TAKEN[jur]}. The "
                  f"demonstration is service authority, so M-ST-1315 stays ABSENT for the state and the `cms_1115_stc` row "
                  f"is unchanged. Generator: scripts/build_medicaid_1115_service_authority_manifests.py."),
        "run_note": "docs/ingest-runs/2026-10-20-w8-medicaid-1115-behavioral-health.md",
    }


def update_queue(new_rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    queue = yaml.safe_load(QUEUE.read_text())
    states: list[dict[str, Any]] = [r for r in queue["states"]
                                    if not (r.get("family") == FAMILY and r["jurisdiction"] in new_rows)]
    for jur, new_row in new_rows.items():
        anchor = max((i for i, r in enumerate(states)
                      if r["jurisdiction"] == jur and r.get("family") == "cms_1115_stc"), default=None)
        if anchor is None:
            anchor = max((i for i, r in enumerate(states) if r["jurisdiction"] == jur), default=None)
        states.insert(len(states) if anchor is None else anchor + 1, new_row)
    queue["states"] = states
    counts: dict[str, int] = {}
    for state_row in states:
        counts[state_row["queue_status"]] = counts.get(state_row["queue_status"], 0) + 1
    queue["status_counts"] = counts
    note = (f"CMS 1115 service-authority family (2026-10-20, wave 8): one `family: {FAMILY}` row per state that holds a "
            f"current approved section 1115 demonstration whose authority is service rather than eligibility (AK ID), for "
            f"the approval letter, special terms and conditions and waiver and expenditure authority lists the state's own "
            f"demonstration page on {LIST} posts as current, version {VERSION}, document_class policy, citation root "
            f"us-xx/policy/cms/1115-service-authority. This is a sibling of `cms_1115_stc`, whose selection rule is "
            f"unchanged and still excludes service authority; the two families are separable by citation root. Superseded, "
            f"expired, withdrawn and pending postings are inventoried and not taken. Generator: "
            f"scripts/build_medicaid_1115_service_authority_manifests.py.")
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    queue["queue_status"] = "in_progress"
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append", default=[], metavar="JURISDICTION")
    args = parser.parse_args()
    rows: dict[str, dict[str, Any]] = {}
    for jur in sorted(NAMES):
        if args.only and jur not in args.only:
            continue
        docs, info, seconds = build(jur)
        (ROOT / "manifests" / f"{jur}-medicaid-1115-service-authority.yaml").write_text(
            yaml.safe_dump({"version": VERSION, "documents": docs}, sort_keys=False, allow_unicode=True, width=120))
        rows[jur] = row(jur, docs, info, seconds)
        print(f"{jur}: {info['index_document_count']} posted, {len(docs)} taken ({seconds:.1f} s)")
    counts = update_queue(rows)
    print(f"queue {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
