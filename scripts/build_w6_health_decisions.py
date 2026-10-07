#!/usr/bin/env python3
# ruff: noqa: C408, E501
"""Write docs/ingest-runs/2026-10-06-w6-health-decisions.csv: one row per work-order row.

Work order: docs/coverage/program-bundle-gaps-2026-10-06/wave6/health.csv (branch
analysis/program-bundle-gaps-2026-10-06; pass its path with --work-order). Rows extracted with
the official-documents manifests come from scripts/build_w6_health_manifests.py; rows extracted
with a dedicated adapter, rows already held, and rows not extracted are listed below.

Usage:
    uv run python scripts/build_w6_health_decisions.py --work-order <path to health.csv>
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ingest-runs" / "2026-10-06-w6-health-decisions.csv"
COLUMNS = ["id", "jurisdiction", "programs", "action", "new_status", "scope_version", "citation_path", "official_url", "note"]


def _load_manifest_docs() -> list[dict]:
    spec = importlib.util.spec_from_file_location("w6m", ROOT / "scripts" / "build_w6_health_manifests.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    out = []
    for doc in module.DOCS:
        out.append(dict(row=doc["row"], status="PRESENT",
                        scope=f"{doc['jur']}/{doc['cls']}/{module.version_for(doc['jur'], doc['cls'])}",
                        path=doc["path"], url=doc["url"],
                        note=doc.get("note") or (doc.get("access") or f"Official publisher answered; {doc['fmt'].upper()} extracted")))
    return out


IL_ILCS = "us-il/statute/2026-10-06-w6-health-statute-il-us-il-chapter-305-act-5"
IL_IAC = "us-il/regulation/2026-10-06-w6-health-regulation-il-title-089-part-00120"
WAC_505 = "us-wa/regulation/2026-10-06-w6-health-regulation-wa-182-505"
WAC_512 = "us-wa/regulation/2026-10-06-w6-health-regulation-wa-182-512"
IAC_PATH = "us-il/regulation/title-089/chapter-i/subchapter-b/part-120/section-120-{}"
IAC_URL = {
    "330": "089001200H03300R", "360": "089001200H03600R", "362": "089001200H03620R", "370": "089001200H03700R",
    "381": "089001200H03810R", "510": "089001200I05100R", "66": "089001200C00660R",
}
ILCS_NOTE = ("www.ilga.gov answers HTTP 403 'Access Denied' to the corpus client for every path (also its /ftp/ILCS/ tree); 305 ILCS 5 "
             "was extracted with the unchanged illinois-ilcs adapter from the same ILGA file repository at ftp.ilga.gov/ILCS/ "
             "(snapshot dated 11/24/2025) by scripts/extract_w6_health_illinois_ilcs.py")
IAC_NOTE = ("Official JCAR Illinois Administrative Code (ftp.ilga.gov, illinois-admin-code adapter, title 89 part 120) in place of "
            "the Cornell LII mirror the bundle names")

CA_WIC = "us-ca/statute/2026-10-06-w6-tanf-ccdf-statutes-ca-us-ca-title-WIC"
CA_NOTE = ("leginfo.legislature.ca.gov answers HTTP 403 (Cloudflare challenge) to the corpus client and to the section adapter; the "
           "Legislative Counsel bulk download (pubinfo_2025.zip, Last-Modified 2026-10-05) answered, and the wave-6 tanf-ccdf group's "
           "california-codes-bulk WIC scope (7,987 rows, coverage complete) holds this provision; not re-extracted (same citation paths)")

OTHER: list[dict] = [
    # --- extracted with a dedicated adapter (PRESENT) ---
    dict(row=28, status="PRESENT", scope="us-co/statute/2026-10-06-w6-health-statute-co-crs2025", path="us-co/statute/10/10-16-1203",
         url="https://olls.info/crs/crs2025-title-10.htm",
         note="Official OLLS C.R.S. 2025 title 10 download (colorado-revised-statutes adapter, article 16) in place of the law.justia.com mirror; manifests/us-co-health-w6-statute.yaml"),
    *[dict(row=r, status="PRESENT", scope=IL_IAC, path=IAC_PATH.format(s),
           url=f"https://ftp.ilga.gov/JCAR/AdminCode/089/{IAC_URL[s]}.html", note=IAC_NOTE)
      for r, s in [(61, "330"), (62, "360"), (63, "362"), (64, "370"), (65, "381"), (66, "510"), (67, "66")]],
    *[dict(row=r, status="PRESENT", scope=IL_ILCS, path="us-il/statute/305/5/5-2",
           url="https://ftp.ilga.gov/ILCS/Ch%200305/Act%200005/030500050K5-2.html", note=ILCS_NOTE)
      for r in (68, 69, 70)],
    dict(row=108, status="PRESENT", scope="us-or/statute/2026-10-06-w6-health-statute-or-ors-us-or-chapter-414", path="us-or/statute/414.231",
         url="https://www.oregonlegislature.gov/bills_laws/ors/ors414.html",
         note="Official Oregon Legislature ORS chapter 414 (oregon-ors adapter) in place of the oregon.public.law mirror"),
    dict(row=116, status="PRESENT", scope=WAC_505, path="us-wa/regulation/182/182-505/182-505-0100",
         url="https://app.leg.wa.gov/WAC/default.aspx?cite=182-505&full=true", note="washington-wac adapter, chapter 182-505 (full-chapter page)"),
    dict(row=117, status="PRESENT", scope=WAC_505, path="us-wa/regulation/182/182-505/182-505-0210",
         url="https://app.leg.wa.gov/WAC/default.aspx?cite=182-505&full=true",
         note="washington-wac adapter, chapter 182-505; the same section text is also held as HCA manual text at us-wa/manual/hca/chip/apple-health-for-kids/wac-182-505-0210 (us-wa/manual/2026-09-10-chip-state-eligibility-manual)"),
    dict(row=118, status="PRESENT", scope=WAC_505, path="us-wa/regulation/182/182-505/182-505-0225",
         url="https://app.leg.wa.gov/WAC/default.aspx?cite=182-505&full=true",
         note="washington-wac adapter, chapter 182-505; the same section text is also held as HCA manual text at us-wa/manual/hca/chip/apple-health-for-kids/wac-182-505-0225 (us-wa/manual/2026-09-10-chip-state-eligibility-manual)"),
    dict(row=119, status="PRESENT", scope=WAC_512, path="us-wa/regulation/182/182-512/182-512-0010",
         url="https://app.leg.wa.gov/WAC/default.aspx?cite=182-512&full=true", note="washington-wac adapter, chapter 182-512 (full-chapter page)"),
    dict(row=120, status="PRESENT", scope=WAC_512, path="us-wa/regulation/182/182-512/182-512-0100",
         url="https://app.leg.wa.gov/WAC/default.aspx?cite=182-512&full=true", note="washington-wac adapter, chapter 182-512 (full-chapter page)"),
    # --- already held ---
    dict(row=3, status="ALREADY-HELD", scope="us-ar/manual/2026-09-10-medicaid-state-eligibility-manual", path="us-ar/manual/dco/medicaid/policy-manual",
         url="https://humanservices.arkansas.gov/wp-content/uploads/MS-Policy-9.26-New.pdf",
         note="The Cornell item (016.20.18 Ark. Code R. 003, 'AR Works Program Updates') republishes DHS Medical Services Policy Manual sections A-100 ff.; the current manual (09/2026) holding A-100 ff. is held"),
    dict(row=14, status="ALREADY-HELD", scope="us-ca/policy/2026-09-13-chip-state-plan", path="us-ca/policy/cms/chip-state-plan/spa/ca-24-0012/approval-package",
         url="https://www.medicaid.gov/CHIP/Downloads/CA-24-0012.pdf",
         note="Same CHIP SPA CA-24-0012 approval package as posted by CMS; the DHCS copy at the bundle address also answers"),
    dict(row=29, status="ALREADY-HELD", scope="us-co/manual/2026-09-10-medicaid-state-eligibility-manual", path="us-co/manual/hcpf/medicaid/10-ccr-2505-10-8-100",
         url="https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2918&deptID=7&agencyID=69&deptName=Department of Health Care Policy and Financing&agencyName=Medical Services Board (Volume 8; Medical Assistance, Children's Health Plan)&seriesNum=10 CCR 2505-10 8.100",
         note="10 CCR 2505-10 section 8.100 from the Secretary of State CCR (official) is held; the bundle names the Cornell LII mirror"),
    dict(row=39, status="ALREADY-HELD", scope="us-de/regulation/2026-07-03-de-dssm-13000", path="us-de/regulation/admin-code/title16/dssm/13000",
         url="https://regulations.delaware.gov/api/AdminCode/title16/13000/2b2fba94-223c-4eb2-8f14-cad95de1c9fd",
         note="EXTRACT-MANIFEST row: manifests/us-de-dssm-13000.yaml was extracted on 2026-07-03 (same URL, coverage complete); scope not yet in a served release"),
    dict(row=42, status="ALREADY-HELD", scope="us-fl/policy/2026-09-13-medicaid-state-plan", path="us-fl/policy/cms/medicaid-state-plan/spa/fl-13-0015-mm1/approval-document",
         url="https://www.medicaid.gov/State-resource-center/Medicaid-State-Plan-Amendments/Downloads/FL/FL-13-0015-MM1.pdf",
         note="ahca.myflorida.com is the official AHCA host (CHECK-PUBLISHER -> official); the same CMS approval of SPA FL-13-0015-MM1 is held from medicaid.gov"),
    dict(row=75, status="ALREADY-HELD", scope="us-ks/manual/2026-09-10-medicaid-state-eligibility-manual", path="us-ks/manual/kdhe/medicaid/kfmam-02000",
         url="https://khap2.kdhe.state.ks.us/kfmam/main.asp?tier1=02000",
         note="KFMAM chapter 02000 page held (its block-1 carries section 2100 Child in Family, the bundle's tier2=02100 view)"),
    dict(row=79, status="ALREADY-HELD", scope="us-ma/regulation/2026-09-10-chip-state-eligibility-manual", path="us-ma/regulation/130-cmr/505/002",
         url="https://www.mass.gov/doc/130-cmr-505000-masshealth-coverage-types-5/download",
         note="130 CMR 505.002 from the official mass.gov 130 CMR 505.000 PDF is held; the bundle names the Cornell LII mirror"),
    dict(row=80, status="ALREADY-HELD", scope="us-ma/regulation/2026-09-10-chip-state-eligibility-manual", path="us-ma/regulation/130-cmr/506/011",
         url="https://www.mass.gov/doc/130-cmr-506000-masshealth-financial-requirements-4/download",
         note="130 CMR 506.011 from the official mass.gov 130 CMR 506.000 PDF is held; the bundle names the Cornell LII mirror"),
    dict(row=82, status="ALREADY-HELD", scope="us-mi/manual/2026-09-11-mi-snap-manual-supersede", path="us-mi/manual/mdhhs/bridges/bem/toc",
         url="https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/000.pdf",
         note="BEM Mobile.pdf (17 MB, redirects to mdhhs-pres-prod) compiles the Bridges Eligibility Manual items, which are held one document per BEM item (us-mi/manual/mdhhs/bridges/bem/<item>)"),
    dict(row=90, status="ALREADY-HELD", scope="us-mo/manual/2026-09-10-medicaid-state-eligibility-manual", path="us-mo/manual/dss/medicaid/mhabd/0865-000-00/0865-010-00/0865-010-15",
         url="https://dssmanuals.mo.gov/mo-healthnet-for-the-aged-blind-and-disabled/0865-000-00/0865-010-00/0865-010-15/",
         note="DEAD-LINK row: the old dss.mo.gov/fsd/iman page is 404; the same MHABD manual section 0865.010.15 Resources (QMB) is held from dssmanuals.mo.gov"),
    dict(row=105, status="ALREADY-HELD", scope="us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461", path="us-or/regulation/chapter-461/division-155/rule-461-155-0250",
         url="https://secure.sos.state.or.us/oard/viewSingleRule.action?ruleVrsnRsn=329862",
         note="Current OAR 461-155-0250 held (also in the r2026-09-14 consolidated chapter-461 scope); the ODHS PDF at the bundle address also answers"),
    # Concurrent wave-6 scopes of other groups hold these; extracting them again would duplicate the
    # same citation paths, so they are recorded here instead (see the run note).
    *[dict(row=r, status="ALREADY-HELD", scope=CA_WIC, path=p, url="https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip", note=CA_NOTE)
      for r, p in [(16, "us-ca/statute/wic/14007.8"), (19, "us-ca/statute/wic/15833"), (20, "us-ca/statute/wic/15834"),
                   (21, "us-ca/statute/wic/15850.1"), (22, "us-ca/statute/wic/15850.5"),
                   (23, "us-ca/statute/wic/node-16.7.2"), (24, "us-ca/statute/wic/node-16.7.3")]],
    dict(row=125, status="ALREADY-HELD", scope="us-wi/statute/2026-10-06-w6-tanf-ccdf-statute-wi-chapter-49", path="us-wi/statute/49.471",
         url="https://docs.legis.wisconsin.gov/statutes/statutes/49?view=section",
         note=("Wis. Stat. 49.471 (BadgerCare Plus, 242 rows) is held in the wave-6 tanf-ccdf group's chapter 49 scope at the same citation path; "
               "this group's single-section extraction of the bundle address (2026-10-06-w6-health-statute-wi) was removed to avoid the duplicate path")),
    # --- OUTREACH ---
    *[dict(row=r, status="OUTREACH", scope="", path="", url=u,
           note="dhcs.ca.gov answers the corpus client HTTP 200 with a 212-byte Incapsula challenge (2026-10-06; same block as 2026-09-10 and 2026-09-13); no wp-content copy of this document was found")
      for r, u in [
          (7, "https://www.dhcs.ca.gov/services/medi-cal-resources/medi-cal-eligibility-division/all-county-welfare-directors-medi-cal-eligibility-division-information-letters/program-descriptions-by-fpl-enclosure-3/"),
          (8, "https://www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/Asset-Limit-Changes-for-Non-MAGI-Medi-Cal.aspx"),
          (9, "https://www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/FFY_Bene.aspx"),
          (10, "https://www.dhcs.ca.gov/services/medi-cal/eligibility/letters/Documents/23-03.pdf"),
          (12, "https://www.dhcs.ca.gov/services/medi-cal/eligibility/letters/Documents/25-14.pdf"),
          (13, "https://www.dhcs.ca.gov/services/working-disabled-program/"),
      ]],
    dict(row=18, status="OUTREACH", scope="", path="", url="https://govt.westlaw.com/calregs/Search/Results?t_querytext=2699.200&t_Method=tnc",
         note="Official CCR publisher (OAL's govt.westlaw.com/calregs) answers HTTP 403 Cloudflare 'Just a moment' challenge; 10 CCR 2699.200 (MCAP basis of eligibility) not otherwise published officially; the bundle names the Cornell LII mirror"),
    dict(row=78, status="OUTREACH", scope="", path="", url="https://ldh.la.gov/faq/category/19",
         note="ldh.la.gov HTML pages answer HTTP 403 (479 bytes) to the corpus client; the Cloudflare block on ldh.la.gov HTML is recorded since 2026-09-10"),
    dict(row=103, status="OUTREACH", scope="", path="", url="https://info.nystateofhealth.ny.gov/sites/default/files/2026%20Income%20Levels_for%20Medicaid,%20CHPlus%20&%20EP.pdf",
         note="info.nystateofhealth.ny.gov answers HTTP 403 CloudFront 'The request could not be satisfied'; no run note documents an impersonation fallback for this host"),
    # --- OUT-OF-SCOPE ---
    dict(row=25, status="OUT-OF-SCOPE", scope="", path="", url="https://coloradoimmigrant.org/wp-content/uploads/2024/03/Eng.-OmniSalud-Guide-2024.pdf",
         note="Advocacy guide by the Colorado Immigrant Rights Coalition (third party); the official OmniSalud texts are Connect for Health Colorado's page (row 26, PRESENT) and C.R.S. 10-16-1203 (row 28, PRESENT)"),
    dict(row=41, status="OUT-OF-SCOPE", scope="", path="", url="https://nashp.org/delaware-chip-fact-sheet/",
         note="Third-party fact sheet (National Academy for State Health Policy); the official CHIP rule DSSM 18000 is held in us-de/regulation/2026-09-10-chip-state-eligibility-manual"),
    dict(row=74, status="OUT-OF-SCOPE", scope="", path="", url="https://www.indianapca.org/cost-sharing-for-hip-program-to-remain-paused-at-this-time/",
         note="News post by the Indiana Primary Health Care Association (third party); the official HIP POWER account page is row 72 (PRESENT)"),
    *[dict(row=r, status="OUT-OF-SCOPE", scope="", path="", url=u,
           note="Third-party host (mmcor.phpcoalition.org) that redirects to a Microsoft sign-in page; an actuarial CHPlus rate-setting presentation, not a source of eligibility rules")
      for r, u in [
          (101, "https://mmcor.phpcoalition.org/docs/Rate%20Setting%20Documents/CY25/NY%20CY25%20CHPlus%20Rate%20Presentation%20-%202024.11.08.pdf"),
          (102, "https://mmcor.phpcoalition.org/docs/Rate%20Setting%20Documents/CY26/NY%20CY26%20CHPlus%20Rate%20Presentation%20-%202025.11.10_FINAL.pdf"),
      ]],
    dict(row=109, status="OUT-OF-SCOPE", scope="", path="", url="https://www.opb.org/article/2023/07/10/oregon-expands-health-coverage-low-income-residents-immigrants/",
         note="News article (Oregon Public Broadcasting); the official texts are OHA's Healthier Oregon page (row 107) and HB 3352 (row 106), both PRESENT"),
    # --- ABSENT ---
    dict(row=1, status="ABSENT", scope="", path="", url="https://www.alabamapublichealth.gov/allbabies/assets/allbabies-map.pdf",
         note="The map PDF redirects to ADPH's 404 page; the ALL Babies index (https://www.alabamapublichealth.gov/allbabies/index.html, HTTP 200) links no county map and no longer limits eligibility by county"),
    dict(row=40, status="ABSENT", scope="", path="", url="https://dhss.delaware.gov/dmma/dhcpflyer/",
         note="The address is now an empty WordPress attachment page (no flyer text or file link); the DHCP program page is https://dhss.delaware.gov/dmma/home/services/dhcp/ and the CHIP rule DSSM 18000 is held"),
    dict(row=121, status="ABSENT", scope="", path="", url="https://app.leg.wa.gov/wac/default.aspx?cite=182-525-0300",
         note="The cite redirects to the Title 182 disposition page; chapter 182-525 is not in the current Title 182 chapter list (182-524 is followed by 182-526)"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-order", required=True)
    parser.add_argument("--extra", help="JSON file with extra decision rows (row, status, scope, path, url, note)")
    args = parser.parse_args()
    with open(args.work_order, newline="") as handle:
        rows = list(csv.DictReader(handle))
    decisions = _load_manifest_docs() + OTHER
    if args.extra:
        import json

        with open(args.extra) as handle:
            decisions += json.load(handle)
    by_row: dict[int, dict] = {}
    for d in decisions:
        assert d["row"] not in by_row, f"duplicate decision for row {d['row']}"
        by_row[d["row"]] = d
    missing = [i for i in range(len(rows)) if i not in by_row]
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for i, r in enumerate(rows):
            d = by_row.get(i) or dict(status="SKIPPED", scope="", path="", url=r["bundle_url"], note="Not reached in the time box")
            writer.writerow({
                "id": r["id"], "jurisdiction": r["jurisdiction"], "programs": r["programs"], "action": r["action"],
                "new_status": d["status"], "scope_version": d["scope"], "citation_path": d["path"],
                "official_url": d["url"], "note": d["note"],
            })
    counts: dict[str, int] = {}
    for i in range(len(rows)):
        status = by_row[i]["status"] if i in by_row else "SKIPPED"
        counts[status] = counts.get(status, 0) + 1
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows {counts}; rows without a decision: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
