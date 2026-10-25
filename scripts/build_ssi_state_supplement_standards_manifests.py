"""Build the SSI state-supplement payment-standards closure manifests (needs-closure-2026-09-11
SSI-ST-4, with SSI-ST-2 where the same publisher carries the authority) and record the scopes on
the SSI agent queue.

Ten REVIEW jurisdictions (KS, MA, MN, NE, NH, OH, OK, SC, SD, VA). Every document is the copy the
official publisher serves (the state agency, the state's statute/rules publisher). Facts per state
were verified by hand on 2026-09-13/14 and are the STATES table below; the run note is
docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md.

    uv run python scripts/build_ssi_state_supplement_standards_manifests.py [--only us-ma] [--no-queue]
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-09-14-ssi-state-supplement-standards"
SOURCE_AS_OF = "2026-09-14"
RUN_NOTE = "docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md"
CHROME = {"browser_impersonation": "chrome120"}
CHROME_DIRECT = {"browser_impersonation": "chrome120", "browser_impersonation_direct": True}


@dataclass
class Doc:
    citation_path: str
    title: str
    url: str
    document_class: str
    expression_date: str
    expression_note: str
    subtype: str
    closure_elements: list[str]
    fmt: str = "pdf"
    pages: int | None = None
    request: dict[str, Any] | None = None
    extraction: dict[str, Any] | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class State:
    name: str
    publisher: str
    index_url: str
    index_document_count: int | None
    status: str  # taken | absent | present_regraded
    access_note: str
    queue_note: str
    docs: list[Doc]
    hosting: str | None = None


VA_SECTIONS = ["10", "15", "20", "30", "35", "40", "45", "50", "60", "70", "80", "9998"]
VA_TITLES = {
    "10": "Definitions", "15": "Eligibility for an auxiliary grant", "20": "Assessment", "30": "Income",
    "35": "Resources", "40": "Living arrangements", "45": "Personal needs allowance", "50": "Establishment of rate",
    "60": "Payments", "70": "Redetermination", "80": "Appeals", "9998": "Forms",
}

STATES: dict[str, State] = {
    "us-ks": State(
        name="Kansas",
        publisher="Kansas Department of Health and Environment (State Supplemental Payment Program)",
        index_url="https://khap.kdhe.ks.gov/kfmam/policydocs/state%20supplemental%20payment%20program%20policy%20memo.pdf",
        index_document_count=None,
        status="absent",
        access_note="khap.kdhe.ks.gov HTTP 200 to the plain client for the 2007 memo; the policydocs directory answers 403.14; ksrevisor.gov HTTP 200",
        queue_note="Absent for the current year: the SSPP pays one flat $20 monthly amount to institutionalized eligibles (KHPA policy memo of 2007-05-02, retroactive to 2006-07-01, already in us-ks/guidance/2026-07-04-ks-sspp-guidance) and KDHE has published no later amount; the April 2026 Kansas Medical Assistance manual (khap.kdhe.ks.gov/KEESM/Apr_2026_Output, 121 topics) has no SSPP topic; K.S.A. 39-972 (floor 'not less than $30') is on disk as us-ks/statute/2026-07-04-ks-sspp-statute and unselected (controller: select it for SSI-ST-2). Nothing new to take.",
        docs=[],
    ),
    "us-ma": State(
        name="Massachusetts",
        publisher="Massachusetts Department of Transitional Assistance",
        index_url="https://www.mass.gov/info-details/learn-about-massachusetts-state-supplement-program-eligibility-and-payments",
        index_document_count=11,
        status="taken",
        access_note="mass.gov HTTP 403 to plain and Chrome-UA clients and HTTP 200 to a chrome120 TLS fingerprint on 2026-09-14; fetched with the extractor's browser_impersonation option, TLS verification on",
        queue_note="Federal and State Payment Levels for Calendar Year 2026 (1 page: the SSP amounts by SSI category and state living arrangement A, B, C, E, F, G) from the DTA SSP information page, which lists the CY 2016-2026 charts (11 documents; the 2026 chart taken). Closes SSI-ST-4; 106 CMR 327 (SSI-ST-2) is in the 2026-09-10 scope.",
        docs=[Doc(citation_path="us-ma/guidance/dta/ssp-payment-levels/cy2026",
                  title="Massachusetts State Supplement Program: Federal and State Payment Levels for Calendar Year 2026",
                  url="https://www.mass.gov/doc/federal-and-state-payment-levels-for-calendar-year-cy-2026/download",
                  document_class="guidance", expression_date="2026-01-01", expression_note="Calendar Year 2026 payment levels",
                  subtype="annual_payment_standards_chart_pdf", closure_elements=["SSI-ST-4"], pages=1, request=CHROME)],
    ),
    "us-mn": State(
        name="Minnesota",
        publisher="Minnesota Department of Human Services (Combined Manual); Office of the Revisor of Statutes (Minnesota Statutes)",
        index_url="https://www.dhs.state.mn.us/main/idcplg?IdcService=GET_DYNAMIC_CONVERSION&RevisionSelectionMethod=LatestReleased&dDocName=CM_MANUAL",
        index_document_count=None,
        status="taken",
        access_note="dhs.state.mn.us answers HTTP 200 with a 15 KB Radware challenge page to plain and Chrome-UA clients and the manual page to a chrome120 TLS fingerprint on 2026-09-14 (fetched with browser_impersonation_direct, TLS verification on); revisor.mn.gov HTTP 200 to the plain client",
        queue_note="Combined Manual 0020.21 MSA Assistance Standards, issue date 03/2026, with the 2026 MSA monthly assistance standards by living arrangement (person living alone $1,055.00, living with others $755.33, couples $1,582.00 / $1,058.00 and the pre-1994 couple standards), the current web page of the section whose 09/2020 print is the stale page in the selected Combined Manual PDF scope; and Minn. Stat. 256D.44 (2025 Minnesota Statutes) for the state authority (SSI-ST-2). The sibling Word file cm_002021~24.doc is a 2021 revision and was not taken.",
        docs=[
            Doc(citation_path="us-mn/manual/dhs/combined-manual/0020-21",
                title="Minnesota DHS Combined Manual 0020.21: MSA Assistance Standards (issue date 03/2026)",
                url="https://www.dhs.state.mn.us/main/idcplg?IdcService=GET_DYNAMIC_CONVERSION&RevisionSelectionMethod=LatestReleased&dDocName=cm_002021",
                document_class="manual", expression_date="2026-03-01", expression_note="printed 'ISSUE DATE: 03/2026'; the 2026 standards correspond with the 01/26 COLA",
                subtype="policy_manual_section_html", closure_elements=["SSI-ST-4"], fmt="html", request=CHROME_DIRECT,
                extra_metadata={"related_selected_scopes": ["us-mn/manual/2026-05-27-mn-combined-manual-r2026-07-15-self-contained (page 914-915, 09/2020 print)", "us-mn/manual/2026-06-27-mn-dhs-msa-revised-sections-2026-01 (on disk, unselected)"]}),
            Doc(citation_path="us-mn/statute/256d/44",
                title="Minnesota Statutes 256D.44: Minnesota Supplemental Aid, standard of assistance (2025 Minnesota Statutes)",
                url="https://www.revisor.mn.gov/statutes/cite/256D.44",
                document_class="statute", expression_date="2025-08-01", expression_note="2025 Minnesota Statutes edition as served by the Revisor on 2026-09-14",
                subtype="statute_section_html", closure_elements=["SSI-ST-2"], fmt="html"),
        ],
    ),
    "us-ne": State(
        name="Nebraska",
        publisher="Nebraska Department of Health and Human Services",
        index_url="https://dhhs.ne.gov/Pages/Title-469-Appendix.aspx",
        index_document_count=None,
        status="taken",
        access_note="dhhs.ne.gov HTTP 200 to the plain client",
        queue_note="Title 469 appendix 469-000-211 AABD or SDP Standard of Need (rev. 2021-01-01, the latest posted: unit standards, board and room, adult family home, assisted living, shelter allowance) and the Medicaid Title 477 appendix 477-000-044 ABD Standard of Need (rev. 2025-12-17, the 2026 figures effective 2026-01-01 in the same living-arrangement structure); 469 NAC chapter 3 (SSI-ST-2) is in the 2026-09-10 scope.",
        docs=[
            Doc(citation_path="us-ne/manual/dhhs/469-000-211",
                title="Nebraska DHHS 469-000-211: AABD or SDP Standard of Need (rev. January 1, 2021)",
                url="https://dhhs.ne.gov/Documents/469-000-211.pdf",
                document_class="manual", expression_date="2021-01-01", expression_note="printed 'REV. JANUARY 1, 2021' / 'Effective 01-01-2021'",
                subtype="manual_appendix_table_pdf", closure_elements=["SSI-ST-4"], pages=1),
            Doc(citation_path="us-ne/manual/dhhs/477-000-044",
                title="Nebraska DHHS 477-000-044: ABD Standard of Need (rev. December 17, 2025; 2026 standards)",
                url="https://dhhs.ne.gov/Documents/477-000-044.pdf",
                document_class="manual", expression_date="2026-01-01", expression_note="printed 'REV. DECEMBER 17, 2025'; 2026 standards effective 01/01/2026",
                subtype="manual_appendix_table_pdf", closure_elements=["SSI-ST-4"], pages=2,
                extra_metadata={"index_url": "https://dhhs.ne.gov/Pages/Title-477-Appendix.aspx"}),
        ],
    ),
    "us-nh": State(
        name="New Hampshire",
        publisher="New Hampshire Department of Health and Human Services",
        index_url="https://www.dhhs.nh.gov/aam_htm/html/601_income_limits_aam.htm",
        index_document_count=None,
        status="taken",
        access_note="dhhs.nh.gov HTTP 403 to plain and Chrome-UA clients and HTTP 200 to a chrome120 TLS fingerprint on 2026-09-14; fetched with the extractor's browser_impersonation option, TLS verification on",
        queue_note="Re-graded: AAM 601 Table A in the selected 2026-09-10 scope carries the 2026 standards of need in its block-2 row (independent living $1,008 / $1,492 / $1,976, residential care $1,188, community residence $1,070 / $1,130 / $1,188), so SSI-ST-4 was already PRESENT (the closure check read the 60-character block-1 stub). Taken in addition: Supervisory Release SR 26-01 dated 01/26 (the transmittal announcing the 2026 COLA-driven standards) and the Bureau of Developmental Services memo '2026 Standard of Need and Income Changes' of 2026-01-01.",
        docs=[
            Doc(citation_path="us-nh/guidance/dhhs/sr/26-01",
                title="New Hampshire DHHS Supervisory Release SR 26-01 (dated 01/26): COLA for 2026 and the OAA, APTD and ANB standards of need",
                url="https://www.dhhs.nh.gov/sr_htm/html/sr_26-01_dated_01_26.htm",
                document_class="guidance", expression_date="2026-01-01", expression_note="SR 26-01 dated 01/26, effective with the 2026 COLA",
                subtype="supervisory_release_html", closure_elements=["SSI-ST-4"], fmt="html", request=CHROME),
            Doc(citation_path="us-nh/guidance/dhhs/bds/2026-standard-of-need-and-income-changes",
                title="New Hampshire DHHS Bureau of Developmental Services: 2026 Standard of Need and Income Changes (January 1, 2026)",
                url="https://www.dhhs.nh.gov/sites/g/files/ehbemt476/files/documents2/bdsstandardofneed.pdf",
                document_class="guidance", expression_date="2026-01-01", expression_note="printed 'January 1, 2026'",
                subtype="agency_memo_pdf", closure_elements=["SSI-ST-4"], pages=2, request=CHROME),
        ],
    ),
    "us-oh": State(
        name="Ohio",
        publisher="Ohio Department of Behavioral Health (formerly OhioMHAS)",
        index_url="https://dbh.ohio.gov/get-help/recovery-supports/residential-state-supplement",
        index_document_count=None,
        status="taken",
        access_note="dam.assets.ohio.gov HTTP 200 to the plain client; dbh.ohio.gov HTTP 404 to the plain client and 200 to a Chrome UA; codes.ohio.gov HTTP 200",
        queue_note="Re-graded: OAC 5122-36-05(B)-(C) in the selected scopes prints the RSS payment level ('one thousand six hundred dollars per month' plus a personal needs allowance of at least two hundred dollars, effective 2023-07-01), so SSI-ST-4 was already PRESENT; no later rate notice exists on the DBH domains. Taken in addition: the DBH Residential State Supplement brochure (2 pages, '$1,600 per month effective July 1, 2023').",
        docs=[Doc(citation_path="us-oh/guidance/dbh/residential-state-supplement-brochure",
                  title="Ohio Department of Behavioral Health: Residential State Supplement (RSS) brochure",
                  url="https://dam.assets.ohio.gov/image/upload/mha.ohio.gov/learnandfindhelp/RecoverySupports/RSS/RSS-Brochure.pdf",
                  document_class="guidance", expression_date="2023-07-01", expression_note="footnote '$1,600 per month effective July 1, 2023'; PDF dated 2024-02-08",
                  subtype="program_brochure_pdf", closure_elements=["SSI-ST-4"], pages=2)],
        hosting="Ohio digital asset management service (dam.assets.ohio.gov)",
    ),
    "us-ok": State(
        name="Oklahoma",
        publisher="Oklahoma Human Services",
        index_url="https://oklahoma.gov/content/dam/ok/en/okdhs/documents/searchcenter/okdhsformresults/c-1.pdf",
        index_document_count=None,
        status="taken",
        access_note="oklahoma.gov HTTP 200 to the plain client (the former policy-library appendix page redirects to rules.ok.gov/home, Cloudflare HTTP 403 to plain clients)",
        queue_note="OKDHS Appendix C-1 Maximum Income, Resource, and Payment Standards, 7/1/2026 (8 pages; Schedule VIII.A on page 3: SSP categorically needy standard, eligible individual $1,034, individual with spouse $1,532, eligible couple $1,571, SSP amount capped at $40), the appendix OAC 340:15-1-5 cites; reached through the OKDHS forms search center.",
        docs=[Doc(citation_path="us-ok/manual/okdhs/oac-340-appendix/c-1",
                  title="Oklahoma Human Services Appendix C-1: Maximum Income, Resource, and Payment Standards (7/1/2026)",
                  url="https://oklahoma.gov/content/dam/ok/en/okdhs/documents/searchcenter/okdhsformresults/c-1.pdf",
                  document_class="manual", expression_date="2026-07-01", expression_note="footer 'Appendix C-1 7/1/2026'",
                  subtype="policy_appendix_pdf", closure_elements=["SSI-ST-4"], pages=8)],
    ),
    "us-sc": State(
        name="South Carolina",
        publisher="South Carolina Department of Health and Human Services",
        index_url="https://www.scdhhs.gov/members/program-eligibility-and-income-limits",
        index_document_count=None,
        status="taken",
        access_note="www.scdhhs.gov HTTP 200 to the plain client; img1.scdhhs.gov (the MPPM index) omits its Go Daddy G2 intermediate (data/certs) and lists Chapter 103 with no link (Chapter_103.docx answers 404)",
        queue_note="SCDHHS 'Program Eligibility and Income Limits' page (Optional State Supplementation section: monthly net income limit $1,804, resources $2,000, dated January 1, 2026), the publisher's current statement of the OSS net income limit; the current MPPM 103 file is not published on the img1.scdhhs.gov index (the only fetchable Chapter 103 is a 2014 Word 97 file on www1.scdhhs.gov, not taken). S.C. Code Title 43 chapter 5 carries no OSS rate (set by appropriations proviso).",
        docs=[Doc(citation_path="us-sc/guidance/scdhhs/program-eligibility-and-income-limits",
                  title="South Carolina Healthy Connections Medicaid: Program Eligibility and Income Limits (Optional State Supplementation net income limit, January 1, 2026)",
                  url="https://www.scdhhs.gov/members/program-eligibility-and-income-limits",
                  document_class="guidance", expression_date="2026-01-01", expression_note="the OSS section prints 'January 1, 2026'; other sections print 03/01/2026 income limits",
                  subtype="agency_web_page_html", closure_elements=["SSI-ST-4"], fmt="html")],
    ),
    "us-sd": State(
        name="South Dakota",
        publisher="South Dakota Department of Social Services",
        index_url="https://dss.sd.gov/economicassistance/",
        index_document_count=None,
        status="absent",
        access_note="dss.sd.gov HTTP 200 to the plain client; sdlegislature.gov HTTP 200",
        queue_note="Absent: ARSD 67:12:14:04 (in the 2026-09-10 scope) pays 'at a rate approved by the department based on the annual appropriation' and DSS publishes no rate (the DSS home, economic assistance, medical programs and forms pages and the DSS Handbook carry no state supplement content; guessed programme URLs answer a redirect stub); SSA's State Assistance Programs for SSI Recipients series ends with the January 2011 edition. Publisher posts no figure.",
        docs=[],
    ),
    "us-va": State(
        name="Virginia",
        publisher="Virginia Department for Aging and Rehabilitative Services (rate letter, hosted by VDSS); Virginia Law Portal, Legislative Information System (22VAC30-80)",
        index_url="https://www.dss.virginia.gov/licensed-care/assisted-living-facilities-alf/",
        index_document_count=None,
        status="taken",
        access_note="dss.virginia.gov and law.lis.virginia.gov HTTP 200 to the plain client",
        queue_note="DARS Auxiliary Grant rate letter of 2025-11-10 (rate $2,130 statewide and $2,450 in Planning District 8 effective 2026-01-01, personal needs allowance $87), linked from the VDSS assisted-living-facilities page; and 22VAC30-80 Auxiliary Grants Program, all 12 sections from Virginia LIS (SSI-ST-2), the alternative family the 2026-09-10 row inventoried and did not take.",
        docs=[
            Doc(citation_path="us-va/guidance/dars/auxiliary-grant-rate-letter/2026",
                title="Virginia DARS Auxiliary Grant rate letter: rate increase effective January 1, 2026",
                url="https://www.dss.virginia.gov/media/vdss/licensing/documents/assisted-living-facilities/additional-resources/ARC2026_ag_rate_letter.pdf",
                document_class="guidance", expression_date="2026-01-01", expression_note="letter dated November 10, 2025; rate effective January 1, 2026",
                subtype="rate_letter_pdf", closure_elements=["SSI-ST-4"], pages=1,
                extra_metadata={"hosting_authority": "Virginia Department of Social Services (dss.virginia.gov)"}),
            *[Doc(citation_path=f"us-va/regulation/22vac30-80/{section}",
                  title=f"22VAC30-80-{section}. {VA_TITLES[section]} (Auxiliary Grants Program)",
                  url=f"https://law.lis.virginia.gov/admincode/title22/agency30/chapter80/section{section}/",
                  document_class="regulation", expression_date="2026-09-14", expression_note="fetch date; Virginia LIS serves the current text and prints each section's historical notes",
                  subtype="administrative_code_section_html", closure_elements=["SSI-ST-2"], fmt="html",
                  extra_metadata={"index_url": "https://law.lis.virginia.gov/admincode/title22/agency30/chapter80/", "index_document_count": 12})
              for section in VA_SECTIONS],
        ],
    ),
}


def build_document(jur: str, state: State, doc: Doc) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source_id": re.sub(r"[^a-z0-9]+", "-", doc.citation_path).strip("-"),
        "jurisdiction": jur,
        "document_class": doc.document_class,
        "title": doc.title,
        "source_url": doc.url,
        "source_format": doc.fmt,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": doc.expression_date,
        "citation_path": doc.citation_path,
    }
    if doc.request:
        record["request"] = dict(doc.request)
    if doc.extraction:
        record["extraction"] = dict(doc.extraction)
    metadata: dict[str, Any] = {"primary_source": True, "source_authority": state.publisher}
    if state.hosting:
        metadata["hosting_authority"] = state.hosting
    metadata.update({
        "document_subtype": doc.subtype,
        "program": "ssi_state_supplement",
        "federal_program": "SSI",
        "state": jur.split("-")[1].upper(),
        "closure_elements": doc.closure_elements,
        "index_url": state.index_url,
        "source_discovery_group": f"{jur}/{doc.document_class}/ssi-state-supplement-standards",
        "discovered_via": f"manual-review:ssi-agent-queue (needs-closure-2026-09-11 SSI-ST-4 review); publisher index {state.index_url}",
        "extraction_granularity": "pdf_page" if doc.fmt == "pdf" else "html_blocks",
        "expression_date_note": doc.expression_note,
        "access_note": state.access_note,
    })
    if doc.pages is not None:
        metadata["page_count"] = doc.pages
    metadata.update(doc.extra_metadata)
    record["metadata"] = metadata
    return record


def write_manifests(only: set[str] | None) -> dict[str, list[dict[str, Any]]]:
    written: dict[str, list[dict[str, Any]]] = {}
    for jur, state in sorted(STATES.items()):
        if only and jur not in only:
            continue
        if not state.docs:
            written[jur] = []
            continue
        by_class: dict[str, list[dict[str, Any]]] = {}
        for doc in state.docs:
            by_class.setdefault(doc.document_class, []).append(build_document(jur, state, doc))
        scopes = []
        for document_class, documents in by_class.items():
            stem = f"{jur}-ssi-state-supplement-standards-{document_class}"
            (ROOT / "manifests" / f"{stem}.yaml").write_text(
                yaml.safe_dump({"version": VERSION, "documents": documents}, sort_keys=False, allow_unicode=True, width=120)
            )
            scopes.append({"jurisdiction": jur, "document_class": document_class, "version": VERSION,
                           "manifest": f"manifests/{stem}.yaml", "document_count": len(documents)})
        written[jur] = scopes
    return written


def update_queue(written: dict[str, list[dict[str, Any]]]) -> None:
    queue_path = ROOT / "manifests" / "ssi-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    done: set[str] = set()
    for row in queue["states"]:
        jur = row["jurisdiction"]
        if jur not in written or jur in done:
            continue
        done.add(jur)
        state = STATES[jur]
        scopes = written[jur]
        row["standards_scope"] = {
            "status": "taken" if scopes else state.status,
            "scopes": scopes,
            "index_url": state.index_url,
            "index_document_count": state.index_document_count,
            "taken_count": sum(s["document_count"] for s in scopes),
            "closure_elements": sorted({e for d in state.docs for e in d.closure_elements}) or ["SSI-ST-4"],
            "run_note": RUN_NOTE,
            "notes": f"2026-09-14 closure run: {state.queue_note} Access: {state.access_note}.",
        }
        if scopes:
            sentence = (" 2026-09-14: current payment standards (SSI-ST-4) taken as "
                        + ", ".join(f"{s['jurisdiction']}/{s['document_class']}/{s['version']}" for s in scopes)
                        + " (see standards_scope).")
        else:
            sentence = f" 2026-09-14: current payment standards (SSI-ST-4) {state.status} (see standards_scope)."
        if sentence.strip() not in (row.get("notes") or ""):
            row["notes"] = (row.get("notes") or "").rstrip() + sentence
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated jurisdictions (default: every state in STATES)")
    parser.add_argument("--no-queue", action="store_true", help="write manifests only")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None
    written = write_manifests(only)
    for jur, scopes in written.items():
        for scope in scopes:
            print(f"{jur} {scope['document_class']} {scope['manifest']} documents={scope['document_count']}")
        if not scopes:
            print(f"{jur} {STATES[jur].status}: no manifest")
    if not args.no_queue:
        update_queue(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
