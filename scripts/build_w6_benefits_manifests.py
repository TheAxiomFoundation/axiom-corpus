"""Build the wave-6 `benefits` group manifests (state SNAP, WIC, SSI state supplement, LIHEAP and
unemployment insurance documents named by the program bundles and missing from the served corpus)
and the per-row decisions file.

Work order: docs/coverage/program-bundle-gaps-2026-10-06/wave6/benefits.csv (265 rows, on the
bundle-gaps branch). Run note: docs/ingest-runs/2026-10-06-w6-benefits.md.

Every document below was fetched from its official publisher on 2026-10-06 with the extractor's
own client (plain corpus user agent first, the extractor's built-in browser user agent retry on
403/404/406) and read before it was listed: the printed title, date or edition is recorded in
the entry. No mirror, archive, proxy or CAPTCHA path is used anywhere; TLS is always verified.

One manifest per (jurisdiction, document_class): manifests/<jur>-benefits-w6-<class>.yaml,
version 2026-10-06-w6-benefits-<class>-<st> (the `w6-benefits` infix keeps every version unique
to this agent). Rows the corpus already holds, rows blocked at the publisher, and rows that are
not rule documents are listed in DECISIONS with their evidence.

    uv run python scripts/build_w6_benefits_manifests.py            # manifests + decisions CSV
    uv run python scripts/build_w6_benefits_manifests.py --work-order <csv> --decisions-only
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-10-06"
RUN_NOTE = "docs/ingest-runs/2026-10-06-w6-benefits.md"
DECISIONS_CSV = ROOT / "docs/ingest-runs/2026-10-06-w6-benefits-decisions.csv"
DEFAULT_WORK_ORDER = Path(
    "/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/"
    "program-bundle-gaps-2026-10-06/wave6/benefits.csv"
)
DISCOVERED_VIA = "axiom.org program-bundle gap list 2026-10-06 (wave 6, group benefits, row {rows})"


def version_for(jurisdiction: str, document_class: str) -> str:
    return f"2026-10-06-w6-benefits-{document_class}-{jurisdiction.removeprefix('us-')}"


def manifest_path_for(jurisdiction: str, document_class: str) -> Path:
    return ROOT / "manifests" / f"{jurisdiction}-benefits-w6-{document_class}.yaml"


DOCS: list[dict[str, Any]] = []


def doc(
    rows: list[int],
    jurisdiction: str,
    document_class: str,
    citation_path: str,
    title: str,
    url: str,
    fmt: str,
    *,
    program: str,
    authority: str,
    subtype: str,
    expression_date: str = SOURCE_AS_OF,
    expression_note: str | None = None,
    download_url: str | None = None,
    extraction: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    alias_rows: dict[int, str] | None = None,
    **metadata: Any,
) -> None:
    DOCS.append(
        {
            "rows": rows,
            "alias_rows": alias_rows or {},
            "jurisdiction": jurisdiction,
            "document_class": document_class,
            "citation_path": citation_path,
            "title": title,
            "source_url": url,
            "source_format": fmt,
            "download_url": download_url,
            "extraction": extraction,
            "request": request,
            "expression_date": expression_date,
            "metadata": {
                "primary_source": True,
                "source_authority": authority,
                "document_subtype": subtype,
                "program": program,
                "expression_date_note": expression_note
                or (
                    "fetch date; the publisher serves the current text"
                    if expression_date == SOURCE_AS_OF
                    else "the date the document prints"
                ),
                "discovered_via": DISCOVERED_VIA.format(rows=", ".join(map(str, rows))),
                **metadata,
            },
        }
    )


# --------------------------------------------------------------------------------------------
# us-ak
AK_DOH = "Alaska Department of Health"
doc([0], "us-ak", "guidance", "us-ak/guidance/doh/hr-1-ak-impacts",
    "Alaska Department of Health, H.R. 1 - AK Impacts",
    "https://health.alaska.gov/en/education/hr-1-ak-impacts/", "html",
    program="SNAP", authority=AK_DOH, subtype="agency_web_page")
doc([1], "us-ak", "guidance", "us-ak/guidance/doh/adult-public-assistance-apa",
    "Alaska Department of Health, Adult Public Assistance (APA)",
    "https://health.alaska.gov/en/services/adult-public-assistance-apa/", "html",
    program="SSI state supplement (Adult Public Assistance)", authority=AK_DOH, subtype="agency_web_page")
doc([2], "us-ak", "guidance", "us-ak/guidance/doh/assisted-living-licensing-and-renewals",
    "Alaska Department of Health, Assisted Living Licensing and Renewals",
    "https://health.alaska.gov/en/services/assisted-living-licensing-and-renewals/", "html",
    program="SSI state supplement (Adult Public Assistance)", authority=AK_DOH, subtype="agency_web_page")
doc([3], "us-ak", "guidance", "us-ak/guidance/doh/snap-nutrition-assistance",
    "Alaska Department of Health, Supplemental Nutrition Assistance Program (SNAP)",
    "https://health.alaska.gov/en/services/division-of-public-assistance-dpa-services/snap-nutrition-assistance/",
    "html", program="SNAP", authority=AK_DOH, subtype="agency_web_page")
doc([4], "us-ak", "guidance", "us-ak/guidance/dpa/apa/standards/2017-2020",
    "Adult Public Assistance (APA) Need and Maximum Payment Standards, 1/1/2017 to 1/1/2020",
    "https://www.akleg.gov/basis/get_documents.asp?session=31&docid=60171", "pdf",
    program="SSI state supplement (Adult Public Assistance)",
    authority="Alaska Department of Health and Social Services, Division of Public Assistance; "
    "filed in the Alaska Legislature's BASIS document system (31st Legislature)",
    subtype="payment_standards_table", expression_date="2020-01-01",
    expression_note="the latest effective date the table prints (1/1/2020)")
doc([6], "us-ak", "statute", "us-ak/statute/title-47-pdf",
    "Alaska Statutes Title 47. Welfare, Social Services, and Institutions (Legislature PDF)",
    "https://www.akleg.gov/statutesPDF/Title-47.pdf", "pdf",
    program="SSI state supplement (APA); TANF; CCDF", authority="Alaska State Legislature",
    subtype="statute_title_pdf", pages=368,
    path_note="whole-title PDF at page granularity; a later section-level adapter scope would use us-ak/statute/47/...")
doc([7], "us-ak", "regulation", "us-ak/regulation/aac/title-7-pdf",
    "Alaska Administrative Code Title 7. Health and Social Services (Legislature PDF)",
    "https://www.akleg.gov/statutesPDF/aac%20Title%207.pdf", "pdf",
    program="SSI state supplement (APA); CCDF", authority="Alaska State Legislature (Alaska Administrative Code)",
    subtype="administrative_code_title_pdf", pages=3054,
    path_note="whole-title PDF at page granularity; the ATAP scope's chapter rows sit under us-ak/regulation/aac/title-7/chapter-45")

# us-al
doc([10], "us-al", "guidance", "us-al/guidance/adol/uc-benefit-rights-and-responsibilities",
    "Alabama Unemployment Compensation Benefit Rights and Responsibilities (claimant handbook)",
    "https://labor.alabama.gov/docs/guides/uc_brr.pdf", "pdf",
    program="Unemployment insurance", authority="Alabama Department of Workforce (formerly Department of Labor)",
    subtype="claimant_handbook")

doc([8], "us-al", "regulation", "us-al/regulation/alabama-administrative-code/480/4/3",
    "Alabama Administrative Code Chapter 480-4-3: Benefits (Department of Workforce)",
    "https://admincode.legislature.state.al.us/administrative-code/480-4-3", "pdf",
    download_url="https://admincode.legislature.state.al.us/api/chapter/480-4-3",
    program="Unemployment insurance", authority="Alabama Legislative Services Agency (Alabama Administrative Code)",
    subtype="administrative_code_chapter_pdf",
    source_url_note="source_url is the chapter page the bundle cites (a JavaScript application); download_url is the "
    "publisher's chapter PDF route, the same /api route as the held 660-2-4 chapter")

# us-ca
CDSS = "California Department of Social Services"
for num, date in (("25-79", "2025-11-07"), ("25-92", "2025-12-31"), ("25-93", "2025-12-31"), ("26-15", "2026-02-26")):
    year = "20" + num[:2]
    doc([{"25-79": 55, "25-92": 56, "25-93": 57, "26-15": 58}[num]], "us-ca", "guidance",
        f"us-ca/guidance/cdss/acl-{year}-{num}", f"CDSS All County Letter No. {num}",
        f"https://www.cdss.ca.gov/Portals/9/Additional-Resources/Letters-and-Notices/ACLs/{year}/{num}.pdf",
        "pdf", program="SNAP (CalFresh)", authority=CDSS, subtype="all_county_letter",
        expression_date=date, document_number=f"ACL {num}")

# us-ct
doc([66], "us-ct", "guidance", "us-ct/guidance/dss/program-standards-chart",
    "DSS Program Standards Chart: Income Limits & Standards for DSS Benefit Programs (as of 10/1/2025)",
    "https://portal.ct.gov/dss/-/media/departments-and-agencies/dss/fact-sheets-and-issue-briefs/fact-sheets/dss-program-standards-chart.pdf",
    "pdf", program="SSI state supplement (AABD); TANF", authority="Connecticut Department of Social Services",
    subtype="standards_chart", expression_date="2025-10-01",
    alias_rows={65: "the bundle's 7-1-2022 xlsx edition now redirects to the portal's 404 page; this is the "
                "publisher's current edition of the same chart"})

# us-dc
doc([69], "us-dc", "guidance", "us-dc/guidance/dhs/give-snap-a-raise",
    "Give SNAP A Raise: Here's What to Expect (DC DHS)",
    "https://dhs.dc.gov/page/give-snap-raise-heres-what-expect", "html",
    program="SNAP", authority="District of Columbia Department of Human Services", subtype="agency_web_page")
doc([70], "us-dc", "guidance", "us-dc/guidance/doee/liheap",
    "Receive Assistance With Your Utility Bills (LIHEAP), DC DOEE",
    "https://doee.dc.gov/liheap", "html",
    program="LIHEAP", authority="District of Columbia Department of Energy and Environment", subtype="agency_web_page")

# us-de
doc([71], "us-de", "rulemaking", "us-de/rulemaking/register/2010-06/13-de-reg-1550",
    "13 DE Reg. 1550 (06/01/10), Final: DSSM 9059 Income Exclusions (Food Supplement Program)",
    "https://archive.regulations.delaware.gov/register/june2010/final/13%20DE%20Reg%201550%2006-01-10.htm",
    "html", program="SNAP", authority="Delaware Register of Regulations (Registrar of Regulations)",
    subtype="register_final_order", expression_date="2010-06-01",
    hosting_note="archive.regulations.delaware.gov is the Registrar's own host for back issues, not a third-party archive")
doc([72], "us-de", "rulemaking", "us-de/rulemaking/register/2005-08/9-de-reg-168",
    "9 DE Reg. 168 (08/01/05), Proposed: Self-Employment Income (Division of Social Services)",
    "https://regulations.delaware.gov/register/august2005/proposed/9%20DE%20Reg%20168%2008-01-05.htm",
    "html", program="SNAP", authority="Delaware Register of Regulations (Registrar of Regulations)",
    subtype="register_proposed_regulation", expression_date="2005-08-01",
    download_url="https://archive.regulations.delaware.gov/register/august2005/proposed/9%20DE%20Reg%20168%2008-01-05.htm",
    source_url_note="regulations.delaware.gov now serves an Angular application shell for register pages (no text in the "
    "HTML); the Registrar serves the same back-issue page as static HTML on its archive host, taken as download_url")

# us-fl
doc([74], "us-fl", "statute", "us-fl/statute/session-laws/2024/hb5001",
    "Florida HB 5001 (2024), General Appropriations Act, enrolled text",
    "https://www.flsenate.gov/Session/Bill/2024/5001", "pdf",
    download_url="https://www.flsenate.gov/Session/Bill/2024/5001/BillText/er/PDF",
    program="SSI state supplement (Optional State Supplementation rates)", authority="The Florida Senate",
    subtype="enrolled_bill", expression_date="2024-07-01",
    expression_note="the General Appropriations Act for FY 2024-25 takes effect July 1, 2024",
    source_url_note="source_url is the bill page the bundle cites; the document is its enrolled (ER) text")

# us-hi
doc([77], "us-hi", "guidance", "us-hi/guidance/dhs/changes-to-abawd-work-requirements-for-snap-faqs",
    "Changes to Able-Bodied Adult Work Requirements for SNAP: FAQs (Hawaii DHS)",
    "https://humanservices.hawaii.gov/changes-to-able-bodied-adult-work-requirements-for-snap-faqs/", "html",
    program="SNAP", authority="Hawaii Department of Human Services", subtype="agency_web_page")
doc([78], "us-hi", "guidance", "us-hi/guidance/dhs/federal-snap-work-requirement-changes-to-begin",
    "Federal SNAP Work Requirement Changes to Begin (Hawaii DHS)",
    "https://humanservices.hawaii.gov/federal-snap-work-requirement-changes-to-begin-department-of-human-services-offers-guidance-and-resources/",
    "html", program="SNAP", authority="Hawaii Department of Human Services", subtype="agency_news_release")

# us-il
doc([84], "us-il", "guidance", "us-il/guidance/dceo/utility-bill-assistance",
    "Utility Bill Assistance (Illinois DCEO, LIHEAP)",
    "https://dceo.illinois.gov/communityservices/utilitybillassistance.html", "html",
    program="LIHEAP", authority="Illinois Department of Commerce and Economic Opportunity", subtype="agency_web_page")
doc([85], "us-il", "guidance", "us-il/guidance/dceo/utility-bill-assistance-faqs",
    "Utility Bill Assistance: Frequently Asked Questions (Illinois DCEO, LIHEAP)",
    "https://dceo.illinois.gov/communityservices/utilitybillassistance/faqs.html", "html",
    program="LIHEAP", authority="Illinois Department of Commerce and Economic Opportunity", subtype="agency_faq")

# us-in
doc([102], "us-in", "guidance", "us-in/guidance/fssa/rcap-provider-guide",
    "Residential Care Assistance Program (RCAP) Provider Guide (September 7, 2017)",
    "https://www.in.gov/fssa/ddars/files/RCAP-Provider-Guide.pdf", "pdf",
    program="SSI state supplement (RCAP)", authority="Indiana Family and Social Services Administration",
    subtype="provider_guide", expression_date="2017-09-07")
doc([103], "us-in", "manual", "us-in/manual/ihcda/liheap-intake-and-operations-manual",
    "Indiana Energy Assistance Program Intake and Operations Program Manual 2025-2026 (PY2026)",
    "https://www.in.gov/ihcda/files/Indiana-LIHEAP-Intake-and-Operations-Program-Manual-PY2026.pdf", "pdf",
    program="LIHEAP", authority="Indiana Housing and Community Development Authority",
    subtype="program_manual", expression_date="2025-10-01",
    expression_note="program year 2026 (2025-2026 heating season) edition",
    supersedes="us-in/manual/2026-09-14-liheap-benefit-matrix (PY2024 version 1.0, same citation path)")

# us-ky
doc([108], "us-ky", "regulation", "us-ky/regulation/kar/921/004/116",
    '921 KAR 4:116. Low Income Home Energy Assistance Program or "LIHEAP"',
    "https://apps.legislature.ky.gov/law/kar/titles/921/004/116/", "html",
    program="LIHEAP", authority="Kentucky Legislative Research Commission (Kentucky Administrative Regulations)",
    subtype="administrative_regulation_html", extraction={"html_content_selector": "div.regulation-content"})
doc([109], "us-ky", "manual", "us-ky/manual/dcbs/dfs/volume-v-state-supplementation",
    "Division of Family Support Operation Manual Volume V, State Supplementation (OMTL 714, R. 10/1/26)",
    "https://www.chfs.ky.gov/agencies/dcbs/dfs/Documents/OMVOLV.pdf", "pdf",
    program="SSI state supplement", authority="Kentucky Cabinet for Health and Family Services, DCBS Division of Family Support",
    subtype="operations_manual_volume", expression_date="2026-10-01", latest_omtl="OMTL-714")

# us-la
doc([110], "us-la", "guidance", "us-la/guidance/dcfs/news/as-extra-snap-benefits-end",
    "As Extra SNAP Benefits End, Recipients Encouraged to Update Info, Assess Options (Louisiana DCFS)",
    "https://www.dcfs.louisiana.gov/news/as-extra-snap-benefits-end-recipients-encouraged-to-update-info-assess-options",
    "html", program="SNAP", authority="Louisiana Department of Children and Family Services", subtype="agency_news_release")
doc([111], "us-la", "rulemaking", "us-la/rulemaking/register/2003-04",
    "Louisiana Register, April 2003 (Vol. 29, No. 04)",
    "https://www.doa.louisiana.gov/media/m23b1mhf/0304.pdf", "pdf",
    program="SNAP", authority="Louisiana Division of Administration, Office of the State Register",
    subtype="state_register_issue", expression_date="2003-04-20",
    expression_note="the April 2003 issue (published on the 20th of the month)")
for row, slug, title in (
    (112, "cms-approval", "Louisiana SPA 25-0013: CMS approval package (approval letter, CMS-179, approved pages)"),
    (113, "supplement-12-to-attachment-2-6-a-redlined",
     "Louisiana SPA 25-0013: Supplement 12 to Attachment 2.6-A, variations from the basic personal needs allowance (redlined)"),
):
    doc([row], "us-la", "policy", f"us-la/policy/cms/medicaid-state-plan/spa/la-25-0013/{slug}", title,
        f"https://ldh.la.gov/assets/medicaid/StatePlan/Amend2025/25-0013/{'25-0013-CMS-Approval' if row == 112 else 'Supplement-12-to-Attachment-2.6-A-Redlined'}.pdf",
        "pdf", program="SSI state supplement (personal needs allowance)", authority="Louisiana Department of Health",
        subtype="medicaid_state_plan_amendment", expression_date="2025-07-01",
        expression_note="TN 25-0013 effective date July 1, 2025",
        access_note="ldh.la.gov answers 403 to the plain corpus agent and 200 to the extractor's built-in browser user-agent retry")

# us-ma
DTA = "Massachusetts Department of Transitional Assistance"
doc([117], "us-ma", "guidance", "us-ma/guidance/dta/policy-online/helpful-charts-and-figures",
    "Helpful Charts and Figures (DTA Policy Online, SNAP and cash standards)",
    "https://eohhs.ehs.state.ma.us/DTA/PolicyOnline/olg%20docs/guides/Helpful%20Charts%20and%20Figures.pdf", "pdf",
    program="SNAP; TAFDC", authority=DTA, subtype="standards_chart")
doc([118], "us-ma", "guidance", "us-ma/guidance/dta/online-guide-transmittal/2025-31",
    "DTA Online Guide Transmittal 2025-31 (July 25, 2025)",
    "https://eohhs.ehs.state.ma.us/DTA/PolicyOnline/olg%20docs/olgtm/2025/31.pdf", "pdf",
    program="SNAP", authority=DTA, subtype="online_guide_transmittal", expression_date="2025-07-25")
for row, cy, lm in ((123, "2022", "2021-10-27"), (124, "2025", "2024-11-01")):
    doc([row], "us-ma", "guidance", f"us-ma/guidance/dta/ssp-payment-levels/cy{cy}",
        f"Federal and State Payment Levels for Calendar Year (CY) {cy}",
        f"https://www.mass.gov/doc/federal-and-state-payment-levels-for-calendar-year-cy-{cy}/download", "pdf",
        program="SSI state supplement (SSP)", authority=DTA, subtype="payment_levels_chart",
        expression_date=f"{cy}-01-01", expression_note=f"calendar year {cy} chart (Last-Modified {lm})")
doc([125], "us-ma", "guidance", "us-ma/guidance/eohlc/learn-about-home-energy-assistance-heap",
    "Learn about Home Energy Assistance - HEAP (Mass.gov, EOHLC)",
    "https://www.mass.gov/info-details/learn-about-home-energy-assistance-heap", "html",
    program="LIHEAP", authority="Massachusetts Executive Office of Housing and Livable Communities", subtype="agency_web_page")

# us-md
doc([126], "us-md", "guidance", "us-md/guidance/dhs/fia/at-26-08",
    "FIA Action Transmittal AT 26-08: H.R. 1 (2025) - Treatment of Energy Assistance Payments (October 16, 2025)",
    "https://dhs.maryland.gov/documents/FIA/Action%20Transmittals-AT%20-%20Information%20Memo-IM/AT-IM2026/26-08%20AT%20H.R.%201%202025%20Treatment%20of%20Energy%20Assistance%20Payments%20combined.pdf",
    "pdf", program="SNAP", authority="Maryland Department of Human Services, Family Investment Administration",
    subtype="action_transmittal", expression_date="2025-10-16", document_number="AT 26-08")
doc([127], "us-md", "statute", "us-md/statute/session-laws/2016/hb0445",
    "Maryland HB 445 (2016 Regular Session), enrolled bill",
    "https://mgaleg.maryland.gov/2016RS/bills/hb/hb0445E.pdf", "pdf",
    program="SNAP", authority="Maryland General Assembly", subtype="enrolled_bill", expression_date="2016-04-12",
    expression_note="publisher Last-Modified of the enrolled file (2016-04-12); the bill prints its own effective-date section")
doc([128], "us-md", "statute", "us-md/statute/bills/2022/hb0456",
    "Maryland HB 456 (2022 Regular Session), third reader",
    "https://mgaleg.maryland.gov/2022RS/bills/hb/hb0456T.pdf", "pdf",
    program="SNAP", authority="Maryland General Assembly", subtype="bill_third_reader", expression_date="2022-03-08",
    expression_note="publisher Last-Modified of the third-reader file (2022-03-08)")

doc([129], "us-md", "statute", "us-md/statute/human-services/5-501",
    "Maryland Code, Human Services § 5-501 (Supplemental Nutrition Assistance Program)",
    "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=ghu&enactments=false&section=5-501", "html",
    program="SNAP", authority="Maryland General Assembly", subtype="statute_section_html",
    extraction={"html_content_selector": "#StatuteText"},
    alias_note="the bundle cites a casetext copy; this is the General Assembly's statute text (the route of "
    "us-md/statute/2026-07-03-md-tca-statutes)")

# us-me
doc([134], "us-me", "statute", "us-me/statute/title-22/3271",
    "22 M.R.S. §3271. Program (Title 22, Subtitle 3: Income Supplementation)",
    "https://legislature.maine.gov/statutes/22/title22sec3271.html", "html",
    program="SSI state supplement", authority="Maine Legislature, Office of the Revisor of Statutes", subtype="statute_section_html",
    extraction={"html_content_selector": "div.MRSSection"})
doc([135], "us-me", "rulemaking", "us-me/rulemaking/dhhs/ofi/chapter-301/rule-2026-02-244p",
    "10-144 C.M.R. Chapter 301 SNAP Rules, Rule #244P rule pages (track changes), amended December 14, 2025",
    "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/rule-2026-02/SNAP%20244P%20Rule%20Pages%20%28TC%29.pdf",
    "pdf", program="SNAP; TANF", authority="Maine Department of Health and Human Services, Office for Family Independence",
    subtype="rulemaking_rule_pages", expression_date="2025-12-14")
doc([136], "us-me", "regulation", "us-me/regulation/dhhs/ofi/chapter-332/appendices-charts",
    "10-144 C.M.R. Chapter 332 MaineCare Eligibility Manual, appendices and charts",
    "https://www.maine.gov/sos/sites/maine.gov.sos/files/content/assets/144c332-appendices-charts.docx", "docx",
    program="SSI state supplement; Medicaid", authority="Maine Secretary of State (agency rules, 10-144 Chapter 332)",
    subtype="administrative_rule_appendix", expression_date="2025-02-28",
    expression_note="publisher Last-Modified of the served file (2025-02-28)")

# us-mi
doc([145], "us-mi", "guidance", "us-mi/guidance/mdhhs/bridges/bpb/2017-016",
    "Bridges Policy Bulletin BPB 2017-016 (FAP LIHEAP payments; heat and utility standard), effective 8-1-2017",
    "https://mdhhs-pres-prod.michigan.gov/olmweb/EX/BP/Public/BPB/2017-016.pdf", "pdf",
    program="SNAP (FAP); LIHEAP", authority="Michigan Department of Health and Human Services",
    subtype="policy_bulletin", expression_date="2017-08-01", document_number="BPB 2017-016")

# us-mo
doc([147], "us-mo", "manual", "us-mo/manual/dss/december-1973-eligibility-requirements/1035-005-00",
    "DSS Manuals, December 1973 Eligibility Requirements, 1035.005.00 Real or Personal Property Limit",
    "https://dssmanuals.mo.gov/december-1973-eligibility-requirements/1035-000-00/1035-005-00/", "html",
    program="SSI state supplement", authority="Missouri Department of Social Services, Family Support Division",
    subtype="manual_section_html")
doc([148], "us-mo", "form", "us-mo/form/dss/fsd/im-72",
    "IM-72 FNIS Facility Notification Information Sheet (7/2026)",
    "https://dssmanuals.mo.gov/wp-content/uploads/2020/10/im-72.pdf", "pdf",
    program="SSI state supplement", authority="Missouri Department of Social Services, Family Support Division",
    subtype="agency_form", expression_date="2026-07-01", expression_note="the form's revision line IM-72FNIS (7/2026)")
for row, sec in ((149, "208.010"), (150, "208.030"), (151, "209.030"), (152, "209.040"), (153, "209.240")):
    doc([row], "us-mo", "statute", f"us-mo/statute/{sec}", f"RSMo {sec}",
        f"https://revisor.mo.gov/main/OneSection.aspx?section={sec}", "html",
        program="SSI state supplement", authority="Missouri Revisor of Statutes", subtype="statute_section_html",
        extraction={"html_content_selector": "div.norm"})
doc([154], "us-mo", "regulation", "us-mo/regulation/csr/13/40-2",
    "13 CSR 40-2, Department of Social Services, Family Support Division, Income Maintenance",
    "https://www.sos.mo.gov/cmsimages/adrules/csr/current/13csr/13c40-2.pdf", "pdf",
    program="SSI state supplement", authority="Missouri Secretary of State, Code of State Regulations",
    subtype="administrative_code_chapter_pdf", expression_date="2022-03-31",
    expression_note="the chapter's printed currency date (JOHN R. ASHCROFT (3/31/22))",
    alias_rows={155: "13 CSR 40-2.050 is a rule of this chapter", 156: "13 CSR 40-2.120 is a rule of this chapter",
                157: "13 CSR 40-2.130 is a rule of this chapter"})

# us-nc
NCDHHS = "North Carolina Department of Health and Human Services, Division of Social Services"
doc([160], "us-nc", "manual", "us-nc/manual/dss/energy-programs/ep-cn-03-2026",
    "Energy Programs Manual Change Notice 03-2026 (Policy Updates, effective October 1, 2026)",
    "https://policies.ncdhhs.gov/wp-content/uploads/EP-CN-03-2026.pdf", "pdf",
    program="LIHEAP", authority=NCDHHS, subtype="manual_change_notice", expression_date="2026-10-01")
doc([161], "us-nc", "manual", "us-nc/manual/dss/energy-programs/ep-150",
    "Energy Programs Manual EP-150 Household Composition (Change #2-2023)",
    "https://policies.ncdhhs.gov/wp-content/uploads/eps150.pdf", "pdf",
    program="LIHEAP", authority=NCDHHS, subtype="manual_section", expression_date="2023-06-02")
doc([162], "us-nc", "manual", "us-nc/manual/dss/energy-programs/ep-175",
    "Energy Programs Manual EP-175 United States Citizenship (Change #1-2011)",
    "https://policies.ncdhhs.gov/wp-content/uploads/eps175.pdf", "pdf",
    program="LIHEAP", authority=NCDHHS, subtype="manual_section", expression_date="2011-12-01")

# us-ne
NEDHHS = "Nebraska Department of Health and Human Services"
doc([163], "us-ne", "guidance", "us-ne/guidance/dhhs/liheap-guidance-document-2026",
    "Low Income Home Energy Assistance Program Guidance Document 10/1/2025 (DHHS Documents copy)",
    "https://dhhs.ne.gov/Documents/Low%20Income%20Home%20Energy%20Assistance%20Program%20%28LIHEAP%29%20Guidance%20Document%202026.pdf",
    "pdf", program="LIHEAP", authority=NEDHHS, subtype="guidance_document", expression_date="2025-10-01",
    related_scope="us-ne/guidance/2026-09-14-liheap-benefit-matrix holds the 'Guidance Docs' copy at a different URL")
doc([164], "us-ne", "guidance", "us-ne/guidance/dhhs/obbb-snap-changes-faq",
    "OBBBA SNAP Changes Frequently Asked Questions (updated August 17, 2026)",
    "https://dhhs.ne.gov/Documents/OBBB-SNAP-Changes-FAQ.pdf", "pdf",
    program="SNAP", authority=NEDHHS, subtype="agency_faq", expression_date="2026-08-17")
for row, ch, date, fid in ((166, 1, "2020-12-26", 1746), (167, 2, "2022-06-26", 1747), (168, 3, "2020-12-26", 1748)):
    mm, dd, yyyy = date[5:7], date[8:10], date[:4]
    doc([row], "us-ne", "regulation", f"us-ne/regulation/title-476/chapter-{ch}",
        f"476 NAC {ch} (Low Income Home Energy Assistance Program), filing of {mm}-{dd}-{yyyy}",
        f"https://rules.nebraska.gov/api/fileStorage/GetAsByteArray/chapter-pdfs/476%20NAC%20{ch}%20({mm}-{dd}-{yyyy}).pdf/{fid}",
        "pdf", program="LIHEAP", authority="Nebraska Secretary of State, Rules and Regulations",
        subtype="administrative_code_chapter_pdf", expression_date=date,
        expression_note="the effective date in the chapter file name")

# us-nj
NJLWD = "New Jersey Department of Labor and Workforce Development"
doc([169], "us-nj", "guidance", "us-nj/guidance/dhs/njsnap/covid19",
    "NJ SNAP: COVID-19 (what you need to know about SNAP during the public health crisis)",
    "https://www.nj.gov/humanservices/njsnap/emergency/covid19/", "html",
    program="SNAP", authority="New Jersey Department of Human Services", subtype="agency_web_page")
for row, slug, title, url, sub, date in (
    (170, "employer-handbook-unemployment-insurance", "Employer Handbook: Unemployment Insurance",
     "https://www.nj.gov/labor/ea/help/employer_handbook/ui.shtml", "agency_web_page", SOURCE_AS_OF),
    (171, "press/2023-12-27-minimum-wage", "New Jersey's Minimum Wage to Exceed Governor Murphy's $15/Hour Goal on January 1 (December 27, 2023)",
     "https://www.nj.gov/labor/lwdhome/press/2023/20231227_minimumwage.shtml", "agency_news_release", "2023-12-27"),
    (172, "press/2024-12-17-new-benefit-rates-2025", "NJ Department of Labor and Workforce Development Announces New Benefit Rates for 2025 (December 17, 2024)",
     "https://www.nj.gov/labor/lwdhome/press/2024/20241217_new_benefit_rates.shtml", "agency_news_release", "2024-12-17"),
    (173, "press/2025-12-29-new-benefit-rates-2026", "NJ Department of Labor and Workforce Development Announces New Benefit Rates for 2026 (December 29, 2025)",
     "https://www.nj.gov/labor/lwdhome/press/2025/20251229_newbenefitrates2026.shtml", "agency_news_release", "2025-12-29"),
    (175, "myunemployment/how-we-calculate-benefits", "How we calculate benefits (Division of Unemployment Insurance)",
     "https://www.nj.gov/labor/myunemployment/before/about/calculator/", "agency_web_page", SOURCE_AS_OF),
    (176, "myunemployment/dependency-benefits", "How to claim dependency benefits, if you're eligible",
     "https://www.nj.gov/labor/myunemployment/before/about/howtoapply/dependencybenefits.shtml", "agency_web_page", SOURCE_AS_OF),
    (177, "myunemployment/who-is-eligible", "Who is eligible for benefits? (Division of Unemployment Insurance)",
     "https://www.nj.gov/labor/myunemployment/before/about/who/", "agency_web_page", SOURCE_AS_OF),
    (178, "myunemployment/faq-factors-that-affect-your-weekly-benefit-rate", "FAQ: Factors that affect your weekly benefit rate",
     "https://www.nj.gov/labor/myunemployment/help/faqs/reducebenefits.shtml", "agency_faq", SOURCE_AS_OF),
):
    doc([row], "us-nj", "guidance", f"us-nj/guidance/lwd/{slug}", title, url, "html",
        program="Unemployment insurance", authority=NJLWD, subtype=sub, expression_date=date)
doc([174], "us-nj", "guidance", "us-nj/guidance/lwd/unemployment-compensation-law-compilation",
    "New Jersey Unemployment Compensation Law, Extended Benefits Law, Workforce Development Partnership Act, supplementary legislation (LWD compilation)",
    "https://www.nj.gov/labor/myunemployment/assets/pdfs/UI_statute.pdf", "pdf",
    program="Unemployment insurance", authority=NJLWD, subtype="agency_statute_compilation",
    expression_date="2024-12-19", expression_note="publisher Last-Modified of the compilation (2024-12-19)",
    class_note="the agency's reprint of N.J.S.A. 43:21; kept as guidance so a later legislature statute scope is not shadowed")

# us-ny
NYDOL = "New York State Department of Labor"
doc([179], "us-ny", "statute", "us-ny/statute/bills/2021/s7148",
    "New York Senate Bill S7148 (2021-2022 Regular Sessions), bill text",
    "https://assembly.state.ny.us/leg/?default_fld=&leg_video=&bn=S7148&term=2021&Text=Y", "html",
    program="Unemployment insurance", authority="New York State Assembly (legislative information system)",
    subtype="bill_text", expression_date="2021-06-02", expression_note="introduced June 2, 2021",
    extraction={"html_content_selector": "#legcontent", "html_text_selector": "pre"},
    alias_rows={191: "nysenate.gov answers a Cloudflare challenge to the corpus client; the Assembly's own "
                "legislative information system serves the same bill text"})
for row, slug, title, url, date in (
    (180, "p832s-how-your-weekly-ui-benefits-are-calculated-1-25-es", "P832S (1/25, Spanish): How your weekly UI benefit payment is calculated",
     "https://dol.ny.gov/system/files/documents/2025/02/p832s-how-your-weekly-ui-benefits-are-calculated-1-25es-us.pdf", "2025-01-01"),
    (181, "p803-partial-ui-faqs-10-3-25", "P803 Partial Unemployment FAQs (10/3/25)",
     "https://dol.ny.gov/system/files/documents/2025/10/p803-partial-ui-faqs-10-3-25.pdf", "2025-10-03"),
    (182, "p832-how-your-weekly-ui-benefits-are-calculated-2-26", "P832 (2/26): How your weekly unemployment insurance benefit payment is calculated",
     "https://dol.ny.gov/system/files/documents/2026/03/p832-how-your-weekly-ui-benefits-are-calculated-2-26.pdf", "2026-02-01"),
):
    doc([row], "us-ny", "guidance", f"us-ny/guidance/dol/{slug}", title, url, "pdf",
        program="Unemployment insurance", authority=NYDOL, subtype="claimant_publication", expression_date=date,
        expression_note="the edition date the publication number carries")
doc([187], "us-ny", "guidance", "us-ny/guidance/governor/news/2025-10-08-maximum-weekly-benefit-increase",
    "Governor Hochul and Labor Leaders Announce Maximum Weekly Benefit Increase for Unemployed Workers (October 8, 2025)",
    "https://www.governor.ny.gov/news/governor-hochul-and-labor-leaders-announce-maximum-weekly-benefit-increase-unemployed-workers",
    "html", program="Unemployment insurance", authority="Office of the Governor of New York",
    subtype="news_release", expression_date="2025-10-08")
doc([188], "us-ny", "guidance", "us-ny/guidance/dtf/nys-50/2024-12",
    "2024 Form NYS-50, Employer's Guide to Unemployment Insurance, Wage Reporting, and Withholding Tax (12/24)",
    "https://www.tax.ny.gov/forms/publications/2024/wt/nys50-1224.htm", "html",
    program="Unemployment insurance", authority="New York State Department of Taxation and Finance",
    subtype="employer_guide", expression_date="2024-12-01")
doc([189], "us-ny", "guidance", "us-ny/guidance/dtf/nys-50/current",
    "Form NYS-50, Employer's Guide to Unemployment Insurance, Wage Reporting, and Withholding Tax (current edition)",
    "https://www.tax.ny.gov/forms/publications/wt/nys50.htm", "html",
    program="Unemployment insurance", authority="New York State Department of Taxation and Finance",
    subtype="employer_guide")

# us-ok
OESC = "Oklahoma Employment Security Commission"
doc([195], "us-ok", "guidance", "us-ok/guidance/oesc/oes-339-claimant-handbook",
    "OES-339 Claimant Handbook: A Guide to Unemployment Benefits (Rev. 06-3-2026)",
    "https://oklahoma.gov/content/dam/ok/en/oesc/documents/forms/OES-339.pdf", "pdf",
    program="Unemployment insurance", authority=OESC, subtype="claimant_handbook", expression_date="2026-06-03")
for row, year, fname in ((196, "2023", "Employer-Important-Numbers-2023"), (197, "2024", "Employer-Important-Numbers-2024"),
                         (198, "2025", "Employer-Important-Numbers-2025"), (199, "2026", "Employer-Improtant-Numbers-2026")):
    doc([row], "us-ok", "guidance", f"us-ok/guidance/oesc/employer-important-numbers/{year}",
        f"OESC Important Numbers for {year} (rates, taxable wage base, maximum weekly benefit)",
        f"https://oklahoma.gov/content/dam/ok/en/oesc/images/misc/{fname}.pdf", "pdf",
        program="Unemployment insurance", authority=OESC, subtype="annual_parameters_sheet",
        expression_date=f"{year}-01-01", expression_note=f"calendar year {year} figures")
doc([201], "us-ok", "statute", "us-ok/statute/title-40-pdf",
    "Oklahoma Statutes Title 40. Labor (complete title PDF)",
    "https://www.oklegislature.gov/OK_Statutes/CompleteTitles/os40.pdf", "pdf",
    program="Unemployment insurance", authority="Oklahoma Legislature", subtype="statute_title_pdf",
    expression_date="2025-12-31", expression_note="publisher Last-Modified of the compiled title (2025-12-31)",
    pages=340)
doc([202], "us-ok", "statute", "us-ok/statute/session-laws/2021/hb1933",
    "Oklahoma Enrolled House Bill No. 1933 (2021), relating to labor (unemployment)",
    "https://www.oklegislature.gov/cf_pdf/2021-22%20ENR/hB/HB1933%20ENR.PDF", "pdf",
    program="Unemployment insurance", authority="Oklahoma Legislature", subtype="enrolled_bill",
    expression_date="2021-05-17", expression_note="publisher Last-Modified of the enrolled file (2021-05-17)")
# OSCN rows 203-205 are taken as pages of the Title 40 PDF (the Legislature's own compilation):
# oscn.net served a Turnstile challenge page to the extractor run (see DECISIONS).

# us-pa
PALI = "Pennsylvania Department of Labor & Industry"
doc([212], "us-pa", "guidance", "us-pa/guidance/dli/uc-law",
    "Pennsylvania Unemployment Compensation Law (Department of Labor & Industry compilation)",
    "https://www.pa.gov/content/dam/copapwp-pagov/en/dli/documents/uc/uc_law.pdf", "pdf",
    program="Unemployment insurance", authority=PALI, subtype="agency_statute_compilation",
    expression_date="2024-08-15", expression_note="publisher Last-Modified of the compilation (2024-08-15)")
doc([213], "us-pa", "guidance", "us-pa/guidance/dli/ucp-1-claimant-handbook",
    "UCP-1 Unemployment Compensation Handbook (claimant handbook)",
    "https://www.pa.gov/content/dam/copapwp-pagov/en/dli/documents/uc/ucp-forms/ucp-1.pdf", "pdf",
    program="Unemployment insurance", authority=PALI, subtype="claimant_handbook",
    expression_date="2024-08-15", expression_note="publisher Last-Modified of the handbook (2024-08-15)")
doc([214], "us-pa", "rulemaking", "us-pa/rulemaking/pa-bulletin/54/24-1863",
    "54 Pa.B. 8560 (Doc. No. 24-1863), Unemployment Compensation; Table Specified for Determination of Rate and Amount of Benefits (December 28, 2024)",
    "https://www.pacodeandbulletin.gov/Display/pabull?file=/secure/pabulletin/data/vol54/54-52/1863.html", "html",
    program="Unemployment insurance", authority="Pennsylvania Bulletin (Legislative Reference Bureau)",
    subtype="register_notice", expression_date="2024-12-28")

# us-sc
for row, slug, title in (
    (218, "optional-state-supplementation-oss-rate-increases", "Optional State Supplementation (OSS) Rate Increases"),
    (219, "optional-state-supplementation-oss-rate-increases-0", "Optional State Supplementation (OSS) Rate Increases (second notice)"),
    (220, "social-security-and-supplemental-security-income-cost-living-adjustment-increases",
     "Social Security and Supplemental Security Income Cost-of-living Adjustment Increases"),
    (221, "social-security-and-supplemental-security-income-cost-living-adjustment-increases-0",
     "Social Security and Supplemental Security Income Cost-of-living Adjustment Increases (second notice)"),
    (222, "social-security-and-supplemental-security-income-ssi-cost-living-adjustment-cola",
     "Social Security and Supplemental Security Income (SSI) Cost-of-living Adjustment (COLA)"),
):
    doc([row], "us-sc", "guidance", f"us-sc/guidance/scdhhs/communications/{slug}", f"SCDHHS communication: {title}",
        f"https://www.scdhhs.gov/communications/{slug}", "html",
        program="SSI state supplement (Optional State Supplementation)",
        authority="South Carolina Department of Health and Human Services", subtype="agency_communication")

doc([223, 224], "us-sc", "regulation", "us-sc/regulation/chapter-126-pdf",
    "S.C. Code of Regulations Chapter 126, Department of Health and Human Services (Legislature PDF)",
    "https://www.scstatehouse.gov/coderegs/Chapter%20126.pdf", "pdf",
    program="SSI state supplement (Optional State Supplementation)",
    authority="South Carolina Legislature, Code of Regulations", subtype="administrative_code_chapter_pdf",
    path_note="whole-chapter PDF at page granularity; R. 126-910 and 126-920 (OSS) are in Article 9 of the chapter")

# us-tx
doc([226], "us-tx", "statute", "us-tx/statute/session-laws/88r/hb1287",
    "Texas H.B. No. 1287 (88th Legislature, Regular Session), enrolled version",
    "https://capitol.texas.gov/tlodocs/88R/billtext/html/HB01287F.htm", "html",
    program="SNAP; TANF", authority="Texas Legislature Online", subtype="enrolled_bill", expression_date="2023-05-28",
    expression_note="publisher Last-Modified of the enrolled text (2023-05-28)")

# us-ut
DWS = "Utah Department of Workforce Services"
doc([230], "us-ut", "guidance", "us-ut/guidance/dws/ui/benefit-calculation",
    "Unemployment Insurance Benefit Calculation (Utah DWS)",
    "https://jobs.utah.gov/ui/UIShared/PDFs/BenefitCalculation.pdf", "pdf",
    program="Unemployment insurance", authority=DWS, subtype="benefit_calculation_sheet",
    expression_date="2026-09-25", expression_note="publisher Last-Modified of the served file (2026-09-25)")
doc([231], "us-ut", "guidance", "us-ut/guidance/dws/ui/claimant-guide",
    "Unemployment Insurance Claimant Guide (Utah DWS)",
    "https://jobs.utah.gov/ui/jobseeker/claimantguide.pdf", "pdf",
    program="Unemployment insurance", authority=DWS, subtype="claimant_handbook",
    expression_date="2025-03-13", expression_note="publisher Last-Modified of the served file (2025-03-13)")
for row, sec, ver in ((234, "201", "C35A-4-S201_1800010118000101"), (235, "207", "C35A-4-S207_2025050720250507"),
                      (236, "401", "C35A-4-S401_1800010118000101"), (237, "403", "C35A-4-S403_2014040320140513")):
    doc([row], "us-ut", "statute", f"us-ut/statute/35a-4-{sec}", f"Utah Code Section 35A-4-{sec}",
        f"https://le.utah.gov/xcode/Title35A/Chapter4/35A-4-S{sec}.html", "html",
        download_url=f"https://le.utah.gov/xcode/Title35A/Chapter4/{ver}.html",
        program="Unemployment insurance", authority="Utah State Legislature, Office of Legislative Research and General Counsel",
        subtype="statute_section_html", utah_code_version=ver,
        source_url_note="source_url is the section page the bundle cites, which loads the current version file named by its versionDefault; download_url is that file")

doc([232, 233], "us-ut", "regulation", "us-ut/regulation/admin-rules/r994/401",
    "Utah Administrative Code R994-401: Payment of Benefits (Workforce Services, Unemployment Insurance)",
    "https://adminrules.utah.gov/public/rule/R994-401/Current%20Rules", "html",
    download_url="https://adminrules.utah.gov/api/public/getfile/uac-html/ffc52bcf-88e1-4d58-a0c3-a18af6a6e3b6.html/R994-401.html",
    request={"browser_user_agent": True, "range_fetch": True, "range_backend": "curl", "range_chunk_size": 4194304},
    extraction={"html_content_selector": "body"},
    program="Unemployment insurance", authority="Utah Office of Administrative Rules", subtype="administrative_code_rule",
    expression_date="2022-04-21", expression_note="the rule's effective date in the eRules record (4/21/2022)",
    rule_id=2241, reference_number="R994-401",
    source_url_note="source_url is the eRules rule route; download_url is the current rule HTML named by the public "
    "API record (searchRuleDataTotal/R994-401), fetched with Accept */* as the FEP R986-200 manifest does")

# us-wa
doc([247], "us-wa", "regulation", "us-wa/regulation/388/388-414/388-414-0001",
    "WAC 388-414-0001 Broad-based categorical eligibility (BBCE)",
    "https://app.leg.wa.gov/WAC/default.aspx?cite=388-414-0001", "html",
    program="SNAP; TANF", authority="Washington State Legislature, Office of the Code Reviser",
    subtype="administrative_code_section_html", extraction={"html_content_selector": "#contentWrapper"},
    path_note="the citation path follows the washington-wac adapter (us-wa/regulation/388/<chapter>/<section>)")
for row, issue, filing, fmt in (
    (251, "2006/16", "06-16-071", "html"), (252, "2007/22", "07-22-022", "html"), (253, "2008/16", "08-16-067", "html"),
    (254, "2013/22", "13-22-037", "html"), (255, "2018/24", "18-24-032", "html"), (256, "2020/23", "20-23-053", "html"),
    (257, "2023/14", "23-14-065", "html"), (258, "2023/24", "23-24-009", "html"), (259, "2024/02", "24-02EMER", "pdf"),
    (260, "2024/06", "24-06-025", "html"),
):
    ext = "pdf" if fmt == "pdf" else "htm"
    doc([row], "us-wa", "rulemaking", f"us-wa/rulemaking/wsr/{filing.lower()}", f"Washington State Register WSR {filing}",
        f"https://lawfilesext.leg.wa.gov/law/wsr/{issue}/{filing}.{ext}", fmt,
        program="SSI state supplement", authority="Washington State Register, Office of the Code Reviser",
        subtype="state_register_filing")
for row, date in ((261, "2024-01-01"), (262, "2025-01-01"), (263, "2026-01-01")):
    doc([row], "us-wa", "guidance", f"us-wa/guidance/hca/income-standards/{date}",
        f"Washington Apple Health income and resource standards, effective {date}",
        f"https://www.hca.wa.gov/assets/free-or-low-cost/income-standards-{date.replace('-', '')}.pdf", "pdf",
        program="SSI state supplement; Medicaid", authority="Washington State Health Care Authority",
        subtype="standards_chart", expression_date=date)

# us-wi
doc([264], "us-wi", "guidance", "us-wi/guidance/dhs/dms/ops-memo/2026-30",
    "DMS Operations Memo 2026-30 (Wisconsin DHS)",
    "https://www.dhs.wisconsin.gov/dms/memos/ops/dms-ops-2026-30.pdf", "pdf",
    program="SNAP (FoodShare)", authority="Wisconsin Department of Health Services, Division of Medicaid Services",
    subtype="operations_memo", expression_date="2026-08-20",
    expression_note="publisher Last-Modified of the memo (2026-08-20)")


# --------------------------------------------------------------------------------------------
# EXTRACT-MANIFEST rows: copy the entry from the manifest on main into a wave-6 manifest.
COPIED: list[tuple[str, str, list[int], dict[int, str]]] = [
    ("manifests/us-ca-cdss-acl-guidance.yaml", "ca-cdss-acl-2024-24-59", [53], {}),
    ("manifests/us-ca-cdss-acl-06-31.yaml", "*", [54], {59: "the same 31-page file (412,441 bytes, byte-identical) under the publisher's older path"}),
    ("manifests/us-il-dhs-mr-23-22.yaml", "il-dhs-csmm-149614", [83], {}),
    ("manifests/us-ma-dta-policy-online-snap-child-support.yaml", "ma-dta-policy-online-snap-child-support-expenses-deduction",
     [114], {116: "the same page; the bundle spells the !SSL! path segment unescaped"}),
    ("manifests/us-va-22vac40-601-snap-regulation.yaml", "*", [238, 239, 240, 241, 242, 243, 244], {}),
]


def copied_documents() -> list[dict[str, Any]]:
    out = []
    for manifest, source_id, rows, aliases in COPIED:
        data = yaml.safe_load((ROOT / manifest).read_text())
        entries = [d for d in data["documents"] if source_id == "*" or d["source_id"] == source_id]
        if not entries:
            raise SystemExit(f"{manifest}: {source_id} not found")
        for entry in entries:
            entry = dict(entry)
            entry["source_as_of"] = SOURCE_AS_OF
            metadata = dict(entry.get("metadata") or {})
            metadata["copied_from_manifest"] = manifest
            metadata["wave6_rows"] = rows
            entry["metadata"] = metadata
            out.append({"entry": entry, "rows": rows, "alias_rows": aliases})
    return out


# --------------------------------------------------------------------------------------------
# Rows decided without a new document: (status, scope, citation_path, official_url, note)
HELD = "ALREADY-HELD"
DECISIONS: dict[int, tuple[str, str, str, str, str]] = {}


def decide(rows: list[int] | int, status: str, scope: str, path: str, url: str, note: str) -> None:
    for row in [rows] if isinstance(rows, int) else rows:
        DECISIONS[row] = (status, scope, path, url, note)


decide(5, "OUT-OF-SCOPE", "", "", "https://www.akleg.gov/basis/statutes.asp",
       "statute browse landing page ('This page is no longer used'), a list of the 47 titles with no rule text; "
       "the title it is cited for is taken as the Title 47 PDF (row 6)")
decide(8, "SKIPPED", "", "", "https://admincode.legislature.state.al.us/administrative-code/480-4-3",
       "the page is a JavaScript application shell (1,855 bytes); the rule text sits behind the publisher's "
       "/api/rule/<rule-number> PDF route (row 9 answers 200), but chapter 480-4-3 has several rules whose "
       "numbers were not enumerated in the time box")
decide(9, HELD, "us-al/regulation/2026-06-30-al-admin-code-660-2-4", "us-al/regulation/alabama-administrative-code/660/2/4",
       "https://admincode.legislature.state.al.us/api/rule/660-2-4-.26",
       "660-2-4-.26 Non-SSI Supplementation (SUP) Recipients is on page 13 of the held chapter 660-2-4 PDF "
       "(.../660/2/4/page-13)")
for r in (11, 183, 184, 185, 186):
    decide(r, "OUT-OF-SCOPE", "", "", "",
           "US DOL ETA Office of Unemployment Insurance compilation of state UI laws (Comparison of State UI Laws / "
           "Significant Provisions of State UI Laws): a federal secondary summary of state law, kept out under the "
           "queues' forbidden-sources policy like the SNAP State Options Report; the state statute is the rule source")
decide(12, "OUT-OF-SCOPE", "", "", "https://www.bls.gov/lau/",
       "BLS Local Area Unemployment Statistics: a statistical dataset, not a rule document (also HTTP 403 to the corpus client)")
decide(13, "SKIPPED", "", "", "",
       "alabamaretail.org is a trade association (third party); the law behind the article is Ala. Code 25-4-72/-73 "
       "(weekly benefit amount and duration), whose official text is on ALISON (alison.legislature.state.al.us); "
       "the Title 25 chapter 4 statute extraction was not reached in the time box")
for r, sec in ((14, "chapter 4"), (15, "25-4-72"), (16, "25-4-73"), (17, "25-4-74"), (18, "25-4-77")):
    decide(r, "SKIPPED", "", "", "",
           f"Justia mirror of Ala. Code Title 25 {sec}; official text is ALISON (alison.legislature.state.al.us, the "
           "`alabama` statute adapter); the Title 25 chapter 4 extraction was not reached in the time box")
decide(19, HELD, "us-ar/manual/2026-09-11-ar-snap-manual-supersede", "us-ar/manual/dhs/snap-policy-manual",
       "https://humanservices.arkansas.gov/wp-content/uploads/Recent-Rules-Filing-SNAP-6000-Deductions.pdf",
       "the bundle's file is the 01/01/2021 rules filing of SNAP manual section 6000 Deductions; the current section 6100 "
       "(SNAP Manual 07/01/2026) is page 282 of the held whole-manual scope (also 2026-07-16-ar-snap-manual, 04/02/2026)")
decide([20, 21], HELD, "us-ar/manual/2026-09-11-ar-snap-manual-supersede", "us-ar/manual/dhs/snap-policy-manual",
       "https://humanservices.arkansas.gov/",
       "arkansas.gov/dhs/webpolicy redirects to humanservices.arkansas.gov/webpolicy (HTTP 403/404); FSC 6100 (Deductions) "
       "and FSC 7100 (Determining Eligibility/Prospective Budgeting) are pages 282 and 314 of the held current SNAP manual")
AZ_FAA = ("dbmefaapolicy.azdes.gov answered HTTP 403 with a Cloudflare 'Just a moment...' challenge (5,804 bytes, "
          "cf-mitigated) to the plain and browser-UA corpus client on 2026-10-06 (FAA5 index probe); the same wall "
          "was recorded on 2026-09-13 and 2026-09-14 (chrome120 also challenged); durable bot challenge, not worked around")
decide(list(range(22, 40)) + list(range(42, 53)), "OUTREACH", "", "", "", AZ_FAA)
decide(40, "OUTREACH", "", "", "https://apps.azsos.gov/public_services/Title_06/6-14.pdf",
       "apps.azsos.gov (Arizona Secretary of State, A.A.C. publisher) answered HTTP 403 with a Cloudflare 'Just a moment...' "
       "challenge (5,823 bytes) to the plain and browser-UA corpus client; not worked around")
decide(41, "SKIPPED", "", "", "https://www.azleg.gov/arsDetail/?title=46",
       "azleg.gov answers 200: the page is the Title 46 (Welfare) table of sections; taking the title means fetching its "
       "several hundred section pages, not reached in the time box")
decide(60, "SKIPPED", "", "", "",
       "Justia mirror of Cal. Welf. & Inst. Code Div. 9, Part 3, Ch. 3, Art. 4; official text is leginfo.legislature.ca.gov "
       "through the `extract-california-code-sections` adapter (WIC 12200 is already held, row 61); the rest of the "
       "article was not reached in the time box")
decide(61, HELD, "us-ca/statute/2026-06-27-ca-ssi-ssp-wic-12200-us-ca-sections-wic-12200", "us-ca/statute/wic/12200",
       "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=12200",
       "held through the California LegInfo adapter (the plain client gets 403 from leginfo)")
for r, path in ((62, "us-co/policy/co-fns-food-restriction-waiver-modification-2026-01-23"),
                (63, "us-co/policy/co-fns-food-restriction-waiver-modification-2026-05-11"),
                (64, "us-co/policy/co-fns-food-restriction-waiver-approval-2025")):
    decide(r, HELD, "us-co/policy/2026-07-21-co-snap-policy", path, "",
           "the manifest's document is in the held scope (inventory source_url matches; scope selected in "
           "us-rulespec-snap-2026-07-21)")
decide(67, HELD, "us-ct/policy/2026-09-14-tanf-manual-whole", "us-ct/policy/dss/upm",
       "https://portal.ct.gov/dss/-/media/departments-and-agencies/dss/upms/upm0---table-of-contents/0100.doc",
       "ctdssmap.com is the CT Medical Assistance Program provider portal (DSS fiscal agent); its UPM page links no manual "
       "text. The DSS Uniform Policy Manual itself is held whole (3,129 rows) from DSS's own portal.ct.gov files")
decide(68, HELD, "us-ct/statute/2026-09-14-income-tax-chapter-title-17b", "us-ct/statute/17b-100",
       "https://www.cga.ct.gov/current/pub/chap_319s.htm",
       "the held Title 17b scope was built from this chapter page (inventory source_url matches; sections 17b-100 ff.)")
decide(73, HELD, "us-de/regulation/2026-07-17-de-snap-rules", "us-de/regulation/title-16/9000-food-stamp-program",
       "https://regulations.delaware.gov/AdminCode/title16/",
       "Cornell LII mirror of 16 Del. Admin. Code 9000-9059; the official DSSM 9000 Food Benefit Program rules are held")
decide([75, 76], HELD, "us-fl/manual/2026-05-27-fl-ess-manual-r2026-07-15-self-contained",
       "us-fl/manual/dcf/ess-program-policy-manual/appendix-a-12-state-funded-programs-eligibility-standards",
       "https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual",
       "the dated upload paths answer 404; Appendix A-12 State Funded Programs Eligibility Standards is held in the ESS manual scope")
decide(79, HELD, "us-hi/regulation/2026-07-03-hi-tanf-admin-rules", "us-hi/regulation/har/17/676",
       "", "hawaii.gov/dhs/main/har read-timed out; HAR chapter 17-676 Income is held (also in the HI SNAP rules scopes)")
decide(80, HELD, "us-ia/manual/2026-07-17-ia-snap-manual", "us-ia/manual/hhs/em/7-f", "",
       "the dhs.state.ia.us path answers 404 (esp.dhs.state.ia.us); Employees' Manual Title 7 Chapter F is held from Iowa HHS")
decide(81, HELD, "us-id/regulation/2026-07-04-id-aabd-rules", "us-id/regulation/idapa/16/03/05",
       "https://adminrules.idaho.gov/rules/current/16/160305.pdf",
       "the bundle's file is the 2022 archive edition of IDAPA 16.03.05; the current edition is held section by section")
decide(82, HELD, "us-id/regulation/2026-07-04-id-aabd-rules", "us-id/regulation/idapa/16/03/05/514",
       "https://adminrules.idaho.gov/rules/current/16/160305.pdf", "Cornell LII mirror; IDAPA 16.03.05.514 is held from the official rules PDF")
decide(86, "OUT-OF-SCOPE", "", "", "",
       "Rockford Housing Authority 'Public Benefits Quick Reference Guide' (2020): a local third-party summary of several "
       "programs, not a rule document")
for r in range(87, 102):
    decide(r, "SKIPPED", "", "", "",
           "Cornell LII mirror of 89 Ill. Adm. Code Part 113 (AABD); official text is the JCAR Illinois Administrative Code "
           "(`extract-illinois-admin-code --only-title 89 --only-part 113`), not reached in the time box")
decide(104, "OUT-OF-SCOPE", "", "", "",
       "FindLaw copy of an Indiana Court of Appeals opinion: case law, not a rule document of the corpus families")
decide(105, "SKIPPED", "", "", "",
       "Justia mirror of IC 12-10-6-2.1; official text is iga.in.gov (`extract-indiana-code`), not reached in the time box")
decide(106, "SKIPPED", "", "", "",
       "Cornell LII mirror of 455 IAC 1-3-3; official text is the Indiana Register / IAC (iar.iga.in.gov), not reached in the time box")
decide(107, HELD, "us-ks/statute/2026-07-04-ks-sspp-statute", "us-ks/statute/39/972/supplemental-income",
       "https://ksrevisor.gov/statutes/chapters/ch39/039_009_0072.html",
       "K.S.A. 39-972 is held (inventory source_url matches); the scope is on disk but not yet selected (2026-09-14 note)")
decide(115, "ABSENT", "", "", "https://www.mass.gov/lists/department-of-transitional-assistance-regulations",
       "106 CMR 364.360 is a Cornell LII entry for a section number the official DTA chapter 364 does not carry: the held "
       "official chapter has 364.300-364.350 and 364.370 (2026-09-10 SNAP completion note, judgment 3)")
decide([119], HELD, "us-ma/regulation/2026-09-10-ssi-state-supplement", "us-ma/regulation/106-cmr/327/327.220",
       "https://www.mass.gov/regulations/106-CMR-32700-eligibility-requirements-for-state-supplement-program-ssp",
       "Cornell LII mirror; 106 CMR 327.220 is held from the official DTA PDF")
decide([120], HELD, "us-ma/regulation/2026-09-10-ssi-state-supplement", "us-ma/regulation/106-cmr/327/327.330",
       "https://www.mass.gov/regulations/106-CMR-32700-eligibility-requirements-for-state-supplement-program-ssp",
       "Cornell LII mirror; 106 CMR 327.330 is held from the official DTA PDF")
decide(121, HELD, "us-ma/regulation/2026-07-21-ma-dta-regulations-consolidated", "us-ma/regulation/106-cmr/363/230",
       "https://www.mass.gov/lists/department-of-transitional-assistance-regulations",
       "Cornell LII mirror; 106 CMR 363.230 is held from the official DTA chapter 363")
decide(122, HELD, "us-ma/regulation/2026-07-21-ma-dta-regulations-consolidated", "us-ma/regulation/106-cmr/363",
       "https://www.mass.gov/lists/department-of-transitional-assistance-regulations",
       "the 2000s Eeohhs2 PDF path answers 404 ('Not allowed'); the current official 106 CMR 363 is held")
decide(129, "SKIPPED", "", "", "",
       "casetext copy of Md. Code, Human Services § 5-501; official text is mgaleg.maryland.gov Laws - Statute Text "
       "(the route of us-md/statute/2026-07-03-md-tca-statutes), not reached in the time box")
decide(130, HELD, "us-md/manual/2026-07-17-md-snap-manual", "us-md/manual/dhs/snap/212-deductions", "",
       "the dhr.maryland.gov path answers 404; FSP Manual section 212 Deductions is held from dhs.maryland.gov")
decide(131, HELD, "us-md/manual/2026-07-17-md-snap-manual", "us-md/manual/dhs/snap/210-income", "",
       "dhr.state.md.us no longer answers (connect timeout); the old FSP manual's income section is the current "
       "FSP Manual section 210 Income, held")
decide([132, 133], "SKIPPED", "", "", "",
       "dsd.state.md.us redirects to dsd.maryland.gov (404); COMAR 07.03.17 is published as the Division of State "
       "Documents' official XML (`extract-maryland-comar --only-title 07 --only-subtitle 03 --only-chapter 17`), not "
       "reached in the time box")
decide(137, HELD, "us-me/regulation/2026-09-10-ssi-state-supplement", "us-me/regulation/dhhs/ofi/chapter-332",
       "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c332-2025-101%20NSC.docx",
       "the (AMD) docx is the amendment copy of filing 2025-101; the held scopes carry the same filing's NSC docx")
decide(138, HELD, "us-me/regulation/2026-07-17-me-snap-rules", "us-me/regulation/dhhs/ofi/chapter-301",
       "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c301-2026-133-NSC.docx",
       "Cornell LII mirror of 10-144 C.M.R. ch. 301 §555-5 (Deductions); held in the official chapter 301 rule text")
decide(139, HELD, "us-me/regulation/2026-09-10-ssi-state-supplement", "us-me/regulation/dhhs/ofi/chapter-332/part-11/section-5",
       "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c332-2025-101%20NSC.docx",
       "Cornell LII mirror; ch. 332 Part 11 §5 is held from the official rule")
for r, s in ((140, "3"), (141, "4")):
    decide(r, HELD, "us-me/regulation/2026-09-10-medicaid-state-eligibility-manual",
           f"us-me/regulation/dhhs/ofi/chapter-332/part-7/section-{s}",
           "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c332-2025-101%20NSC.docx",
           f"Cornell LII mirror; ch. 332 Part 7 §{s} is held from the official rule")
decide(142, HELD, "us-mi/statute/2026-07-16-mi-fip-statutory-authority", "us-mi/statute/400.10d",
       "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-400-10d",
       "the manifest's document is held (inventory source_url matches); the scope is on disk and not in any release selector")
decide(143, HELD, "us-mi/manual/2026-06-27-mi-mdhhs-rft-248", "us-mi/manual/mdhhs/rft/248",
       "https://dhhs.michigan.gov/OLMWEB/EX/RF/Public/RFT/248.pdf", "inventory source_url matches")
decide(144, HELD, "us-mi/manual/2026-09-11-mi-snap-manual-supersede", "us-mi/manual/mdhhs/bridges/bem/554",
       "https://dhhs.michigan.gov/olmweb/ex/BP/Public/BEM/554.pdf",
       "inventory source_url matches (released in 2026-07-17-mi-bridges-manual; 8-1-2026 edition in the supersede scope)")
decide(146, "OUTREACH", "", "", "https://dssmanuals.mo.gov/december-1973-eligibility-requirements/1010-000-00/",
       "the publisher serves the page as 'This content is password-protected'; no public text")
decide([158, 159], "SKIPPED", "", "", "",
       "dssmanuals.mo.gov dated memo posts (IM-143 of 2022-12-05, IM-57 of 2023-06-08) answer 404; the current address "
       "of the two memoranda was not searched in the time box")
decide(165, HELD, "us-ne/regulation/2026-09-10-ssi-state-supplement", "us-ne/regulation/title-469",
       "https://rules.nebraska.gov/api/fileStorage/GetAsByteArray/chapter-pdfs/469%20NAC%201%20%2806-06-2022%29.pdf",
       "the bundle's Title-469-Complete.pdf is the DHHS compiled 2014 edition (AABD Manual Letter #62-2014); the current "
       "469 NAC chapters (06-06-2022) are held from the Secretary of State")
decide(190, "OUTREACH", "", "", "https://otda.ny.gov/policy/directives/2016/ADM/16-ADM-06.pdf",
       "otda.ny.gov resets the connection (ConnectionResetError 54) for the corpus client; F5/TSPD challenge recorded "
       "2026-09-10/13; durable")
decide(192, "OUTREACH", "", "", "https://www.nysenate.gov/legislation/bills/2025/S3006",
       "nysenate.gov answers HTTP 403 with a Cloudflare 'Just a moment...' challenge to the corpus client; not worked around")
for r, sec in ((193, "527"), (194, "590")):
    decide(r, "OUTREACH", "", "", f"https://www.nysenate.gov/legislation/laws/LAB/{sec}",
           f"nysenate.gov answers HTTP 403 with a Cloudflare challenge; NY Labor Law § {sec} has no other probed official "
           "host in this pass (the corpus's New York laws adapters were not run)")
decide(200, "OUT-OF-SCOPE", "", "", "",
       "OESC 'Oklahoma UI Tax Rates by Industry, Establishment Size and County, 1st quarter 2016 to 2021': a "
       "statistical report, not a rule document")
decide([206, 207], "OUTREACH", "", "", "",
       "oscn.net answered the first three section requests (1.5 s apart) and then HTTP 201 'OSCN Turnstile' (a Cloudflare "
       "Turnstile challenge page) for CiteID 77166 and 77177; not solved or worked around. The sections are in the Title 40 "
       "PDF taken from oklegislature.gov (row 201) but their section numbers were not identified behind the challenge")
for r, path in ((208, "us-or/regulation/chapter-461/division-140/rule-461-140-0266"),
                (209, "us-or/regulation/chapter-461/division-155/rule-461-155-0180"),
                (210, "us-or/regulation/chapter-461/division-160/rule-461-160-0430")):
    decide(r, HELD, "us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated",
           path, "", "OAR chapter 461 is held whole (2026-09-14 consolidated successor of the TANF chapter-461 scope)")
decide(211, HELD, "us-pa/manual/2026-07-21-pa-snap-handbook", "us-pa/manual/dhs/snap/560-income-deductions-560-appendix-a",
       "http://services.dpw.state.pa.us/oimpolicymanuals/snap/560_Income_Deductions/560_Appendix_A.htm",
       "inventory source_url matches")
decide([215, 217], HELD, "us-pa/manual/2026-07-21-pa-snap-handbook", "us-pa/manual/dhs/snap/560-income-deductions-snap-560-title",
       "http://services.dpw.state.pa.us/oimpolicymanuals/snap/", "the old bop/fs/560 paths answer 404 or no longer resolve; "
       "SNAP Handbook chapter 560 Income Deductions is held section by section (560.1-560.8 and Appendix A)")
decide(216, HELD, "us-pa/manual/2026-07-21-pa-snap-handbook", "us-pa/manual/dhs/snap/560-income-deductions-560-appendix-a",
       "http://services.dpw.state.pa.us/oimpolicymanuals/snap/560_Income_Deductions/560_Appendix_A.htm",
       "the old 560_A path answers 404; chapter 560 Appendix A is held")
for r, s in ((223, "126-910"), (224, "126-920")):
    decide(r, "SKIPPED", "", "", "",
           f"Cornell LII mirror of S.C. Code Regs. R. {s}; the official Code of Regulations chapter 126 PDF on "
           "scstatehouse.gov was not reached in the time box")
decide(225, HELD, "us-tx/manual/2026-07-13-tx-twh-c120",
       "us-tx/manual/hhs/texas-works-handbook/c-120-supplemental-nutrition-assistance-program",
       "https://www.hhs.texas.gov/handbooks/texas-works-handbook/c-120-supplemental-nutrition-assistance-program",
       "the manifest's document is held (inventory source_url matches)")
decide(227, "SKIPPED", "", "", "https://statutes.capitol.texas.gov/Docs/HR/htm/HR.32.htm",
       "statutes.capitol.texas.gov now serves a JavaScript application shell (no chapter text in the HTML); Human "
       "Resources Code chapter 32 needs the `extract-texas-tcas` route, not reached in the time box")
decide(228, HELD, "us-tx/manual/2026-09-10-medicaid-state-eligibility-manual", "us-tx/manual/hhsc/medicaid/mepd-h-1500",
       "https://www.hhs.texas.gov/handbooks/medicaid-elderly-people-disabilities-handbook/h-1500-personal-needs-allowance",
       "inventory source_url matches")
decide(229, HELD, "us-tx/manual/2026-09-10-medicaid-state-eligibility-manual", "us-tx/manual/hhsc/medicaid/mepd-h-6000",
       "https://www.hhs.texas.gov/handbooks/medicaid-elderly-people-disabilities-handbook/h-6000-co-payment-ssi-cases",
       "inventory source_url matches")
for r, s in ((232, "R994-401-201"), (233, "R994-401-301")):
    decide(r, "SKIPPED", "", "", "",
           f"Cornell LII mirror of Utah Admin. Code {s}; official text is the eRules public API (the route of "
           "us-ut/regulation/2026-09-15-ssi-state-supplement-rules), not reached in the time box")
decide([245, 246], HELD, "us-vt/manual/2026-07-21-vt-3squaresvt-manual", "us-vt/manual/dcf/3squaresvt/3100-tables",
       "https://dcf.vermont.gov/benefits/3SquaresVT",
       "the humanservices.vermont.gov on-line-rules paths answer 404; the ESD food stamp rules and procedure tables were "
       "replaced by the 3SquaresVT Rules (manual) held whole, with the standards in 3100 Tables")
for r, path in ((248, "us-wa/regulation/388/388-474/388-474-0012"), (249, "us-wa/regulation/388/388-478/388-478-0055"),
                (250, "us-wa/regulation/388/388-478/388-478-0057")):
    decide(r, HELD, "us-wa/regulation/" + ("2026-07-01-388-474-r2026-07-15-self-contained-r2026-07-17-dedup" if "474" in path
                                           else "2026-06-25-388-478-r2026-07-15-self-contained-r2026-07-17-dedup"),
           path, "", "held through the washington-wac adapter (inventory source_url matches)")


# --------------------------------------------------------------------------------------------
# Adapter scopes (existing extractors, not official-documents manifests). These override the
# SKIPPED placeholders above once the scope is on disk; commands are in the run note.

# extract-illinois-admin-code --only-title 89 --only-part 113 (JCAR, ftp.ilga.gov)
IL_SCOPE = "us-il/regulation/2026-10-06-w6-benefits-ssi-aabd-il-title-089-part-00113"
IL_PART = "us-il/regulation/title-089/chapter-iv/subchapter-b/part-113"
for r, s, code in (
    (87, "10", "B00100"), (88, "100", "C01000"), (89, "112", "C01120"), (90, "113", "C01130"),
    (91, "120", "C01200"), (92, "125", "C01250"), (93, "140", "C01400"), (94, "141", "C01410"),
    (95, "142", "C01420"), (96, "247", "D02470"), (97, "248", "D02480"), (98, "253", "D02530"),
    (99, "259", "D02590"), (100, "70", "B00700"),
):
    decide(r, "PRESENT", IL_SCOPE, f"{IL_PART}/section-113-{s}",
           f"https://ftp.ilga.gov/JCAR/AdminCode/089/089001130{code}R.html",
           f"Cornell LII mirror; 89 Ill. Adm. Code 113.{s} taken from the JCAR Illinois Administrative Code "
           "(Part 113 whole, 92 sections)")
decide(101, "PRESENT", IL_SCOPE, IL_PART, "https://ftp.ilga.gov/JCAR/AdminCode/089/089001130A00010R.html",
       "Cornell LII mirror of Part 113 Subpart B; JCAR publishes no separate subpart page, so the subpart's sections "
       "are rows of the Part 113 scope")

# OSCN rows: oscn.net challenged the extractor run with an 'OSCN Turnstile' page (the 2026-10-06 probe had
# answered 200 for these three); the Oklahoma Legislature's compiled Title 40 PDF carries the same sections.
OK_PDF = "us-ok/statute/2026-10-06-w6-benefits-statute-ok"
for r, sec, page in ((203, "1-231", 48), (204, "2-104", 49), (205, "2-105", 50)):
    decide(r, "PRESENT", OK_PDF, f"us-ok/statute/title-40-pdf/page-{page}",
           "https://www.oklegislature.gov/OK_Statutes/CompleteTitles/os40.pdf",
           f"oscn.net (official, Oklahoma Supreme Court) answered the extractor with a Cloudflare 'OSCN Turnstile' "
           f"challenge page; 40 O.S. § {sec} is on page {page} of the Legislature's compiled Title 40 PDF (row 201)")

# extract-state-statutes --manifest manifests/us-al-benefits-w6-ui-statute.yaml (alabama-code adapter, ALISON)
AL_SCOPE = "us-al/statute/2026-10-06-w6-benefits-ui-statute-us-al-title-25"
decide(13, "PRESENT", AL_SCOPE, "us-al/statute/25-4-72",
       "https://alison.legislature.state.al.us/code-of-alabama?section=25-4-72",
       "alabamaretail.org is a trade association (third party); the law its article reports (weekly benefit amount and "
       "weeks of benefits) is Ala. Code 25-4-72 and 25-4-73, taken from the Legislature's ALISON code service")
decide(14, "PRESENT", AL_SCOPE, "us-al/statute/title-25/chapter-4", "https://alison.legislature.state.al.us/code-of-alabama",
       "Justia mirror of Ala. Code Title 25 Chapter 4; the official chapter is taken whole within Title 25 from ALISON")
for r, sec in ((15, "25-4-72"), (16, "25-4-73"), (17, "25-4-74"), (18, "25-4-77")):
    decide(r, "PRESENT", AL_SCOPE, f"us-al/statute/{sec}",
           f"https://alison.legislature.state.al.us/code-of-alabama?section={sec}",
           f"Justia mirror; Ala. Code {sec} taken from the Legislature's ALISON code service")

# extract-texas-tcas --only-title HR (Texas Legislative Council TCAS JSON, statutes.capitol.texas.gov)
decide(227, "PRESENT", "us-tx/statute/2026-10-06-w6-benefits-ssi-statute-us-tx-title-HR",
       "us-tx/statute/hr/title-2/subtitle-c/chapter-32", "https://statutes.capitol.texas.gov/Docs/HR/htm/HR.32.htm",
       "the chapter page is now a JavaScript application shell; Human Resources Code chapter 32 (Medical Assistance "
       "Program) taken through the `texas-tcas` adapter from the same publisher's statute JSON (whole HR code, 1,806 rows)")
# extract-indiana-code --only-title 12 --source-year 2026 (Indiana General Assembly, iga.in.gov)
decide(105, "PRESENT", "us-in/statute/2026-10-06-w6-benefits-ssi-statute-us-in-title-12", "us-in/statute/12-10-6-2.1",
       "https://iga.in.gov/ic/2026/Title_12.html",
       "Justia mirror; IC 12-10-6-2.1 (residential care assistance eligibility) taken from the General Assembly's 2026 "
       "Indiana Code Title 12 (whole title, 4,070 rows)")
decide(106, "SKIPPED", "", "", "https://iar.iga.in.gov/code/2026/455/1",
       "Cornell LII mirror of 455 IAC 1-3-3; the official Indiana Register IAC host serves a 735-byte JavaScript "
       "application shell and the corpus has no IAR adapter; not built in the time box")
decide(60, "OUTREACH", "", "",
       "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=WIC&division=9.&title=&part=3.&chapter=3.&article=4.",
       "Justia mirror of Cal. Welf. & Inst. Code Div. 9, Part 3, Ch. 3, Art. 4; the official leginfo.legislature.ca.gov "
       "article page answered HTTP 403 with a Cloudflare 'Just a moment...' challenge to the plain and browser-UA corpus "
       "client on 2026-10-06 (WIC 12200 of the article is held, row 61); not worked around")
decide(41, "SKIPPED", "", "", "https://www.azleg.gov/arsDetail/?title=46",
       "azleg.gov answers 200 (the Title 46 table of sections); the `arizona-revised-statutes` adapter can take the whole "
       "title, but a parallel wave-6 agent (tanf-ccdf) holds ARS 46-207 and 46-207.01 in "
       "us-az/statute/2026-10-06-w6-tanf-ccdf-statutes-az, so a whole-title scope would collide; left to the controller")
for r, memo in ((158, "IM-143 (2022-12-05)"), (159, "IM-57 (2023-06-08)")):
    decide(r, "ABSENT", "", "", "https://dssmanuals.mo.gov/memorandums/",
           f"the dated post of memo {memo} answers 404; the site search for the memo number lists only manual sections "
           "that cite it, the Memorandums index lists only CD and OEC memo years and practice points (no FSD IM memo "
           "archive), and the WordPress API answers 403; no current official copy found")

# extract-maryland-comar --only-title 07 --only-subtitle 03 --only-chapter 17 (DSD official XML)
MD_SCOPE = ("us-md/regulation/2026-10-06-w6-benefits-snap-comar-md-publication-2026-10-05-title-07-subtitle-03-"
            "chapter-17")
for r, reg in ((132, "35"), (133, "43")):
    decide(r, "PRESENT", MD_SCOPE, f"us-md/regulation/title-07/subtitle-03/chapter-17/regulation-{reg}",
           "https://github.com/maryland-dsd/law-xml-codified/blob/publication%2F2026-10-02.2026-10-05/us/md/exec/comar/07/03/17.xml",
           f"dsd.state.md.us redirects to dsd.maryland.gov (404); COMAR 07.03.17.{reg} taken from the Division of State "
           "Documents' official COMAR XML (chapter 17 whole)")


# --------------------------------------------------------------------------------------------
def manifest_entry(d: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source_id": d["citation_path"].replace("/", "-"),
        "jurisdiction": d["jurisdiction"],
        "document_class": d["document_class"],
        "title": d["title"],
        "source_url": d["source_url"],
        "source_format": d["source_format"],
        "source_as_of": SOURCE_AS_OF,
        "expression_date": d["expression_date"],
        "citation_path": d["citation_path"],
    }
    if d["download_url"]:
        entry["download_url"] = d["download_url"]
    if d["request"]:
        entry["request"] = d["request"]
    if d["extraction"]:
        entry["extraction"] = d["extraction"]
    entry["metadata"] = {**d["metadata"], "wave6_rows": d["rows"], "run_note": RUN_NOTE}
    return entry


def build_manifests() -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for d in DOCS:
        groups[(d["jurisdiction"], d["document_class"])].append(manifest_entry(d))
    for c in copied_documents():
        e = c["entry"]
        groups[(e["jurisdiction"], e["document_class"])].append(e)
    for (jur, cls), entries in sorted(groups.items()):
        path = manifest_path_for(jur, cls)
        data = {"version": version_for(jur, cls), "documents": entries}
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120))
    return groups


def write_decisions(work_order: Path, statuses: dict[str, str] | None = None) -> None:
    rows = list(csv.DictReader(work_order.open()))
    by_row: dict[int, tuple[str, str, str, str, str]] = dict(DECISIONS)
    for d in DOCS:
        scope = f"{d['jurisdiction']}/{d['document_class']}/{version_for(d['jurisdiction'], d['document_class'])}"
        for r in d["rows"]:
            by_row[r] = ("PRESENT", scope, d["citation_path"], d["source_url"], d["title"])
        for r, note in d["alias_rows"].items():
            by_row[r] = ("PRESENT", scope, d["citation_path"], d["source_url"], note)
    for c in copied_documents():
        e = c["entry"]
        scope = f"{e['jurisdiction']}/{e['document_class']}/{version_for(e['jurisdiction'], e['document_class'])}"
        for r in c["rows"]:
            if rows[r]["bundle_path"] and rows[r]["bundle_path"] != e["citation_path"]:
                continue
            by_row[r] = ("PRESENT", scope, e["citation_path"], e["source_url"],
                         f"manifest entry copied from {e['metadata']['copied_from_manifest']}")
        for r, note in c["alias_rows"].items():
            by_row[r] = ("PRESENT", scope, e["citation_path"], e["source_url"], note)
    overrides = statuses or {}
    with DECISIONS_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "jurisdiction", "programs", "action", "new_status", "scope_version", "citation_path",
                    "official_url", "note"])
        for i, row in enumerate(rows):
            status, scope, path, url, note = by_row.get(i, ("SKIPPED", "", "", "", "not reached in the time box"))
            if str(i) in overrides:
                status, note = overrides[str(i)], f"{note}; extraction failed, see run note"
                scope = path = ""
            w.writerow([row["id"], row["jurisdiction"], row["programs"], row["action"], status, scope, path, url, note])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-order", type=Path, default=DEFAULT_WORK_ORDER)
    parser.add_argument("--decisions-only", action="store_true")
    args = parser.parse_args()
    if not args.decisions_only:
        groups = build_manifests()
        for (jur, cls), entries in sorted(groups.items()):
            print(f"{manifest_path_for(jur, cls).relative_to(ROOT)}\t{version_for(jur, cls)}\t{len(entries)}")
    write_decisions(args.work_order)


if __name__ == "__main__":
    main()
