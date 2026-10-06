"""Build the wave-6 official-document manifests for group tanf-ccdf-nh-wy.

Wave 6 (2026-10-06) closes the program-bundle gaps: documents the TANF and CCDF program bundles
name (axiom-corpus#780) that the served corpus does not hold. This script carries the documents of
New Hampshire to Wyoming that ``extract-official-documents`` takes, one manifest per
(jurisdiction, document class)::

    manifests/us-<st>-tanf-ccdf-w6-<class>.yaml      version 2026-10-06-w6-tanf-ccdf-<class>-<st>

Every entry was read on the publisher's site on 2026-10-06 (one plain GET with the corpus user agent;
``request.browser_impersonation`` only for dhhs.nh.gov and nysenate.gov, whose run notes document
the need). ``source_url`` is the bundle's own address whenever that is the address fetched, so the
bundle generator joins the document to its manifest by URL; the decisions file
``docs/ingest-runs/2026-10-06-w6-tanf-ccdf-nh-wy-decisions.csv`` records the join for the others.
Statute chapters (WI 49 and 990, WV 9-9, RI 40-5.2) run through ``extract-state-statutes`` with
``manifests/state-statutes-tanf-ccdf-w6-nh-wy.yaml``; WAC 110-15 through ``extract-washington-wac``.

Usage::

    uv run python scripts/build_w6_tanf_ccdf_nh_wy_manifests.py [--only us-nj,us-vt]
"""

from __future__ import annotations

import argparse
import copy
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE_AS_OF = "2026-10-06"
GROUP = "tanf-ccdf-nh-wy"
DISCOVERED_VIA = (
    "wave6 program-bundle gaps 2026-10-06 (docs/coverage/program-bundle-gaps-2026-10-06, "
    "group tanf-ccdf-nh-wy); publisher page read 2026-10-06"
)
CHROME = {"browser_impersonation": "chrome120"}

AUTHORITY = {
    "us-nh": "New Hampshire Department of Health and Human Services",
    "us-nj": "New Jersey Department of Human Services, Division of Family Development",
    "us-nm": "New Mexico Health Care Authority / Early Childhood Education and Care Department",
    "us-nv": "Nevada Department of Human Services, Division of Social Services (formerly DWSS)",
    "us-ny": "New York State",
    "us-oh": "Ohio Department of Job and Family Services / Department of Children and Youth",
    "us-ok": "Oklahoma Human Services",
    "us-or": "Oregon Department of Early Learning and Care",
    "us-pa": "Pennsylvania Department of Human Services",
    "us-ri": "Rhode Island Department of Human Services",
    "us-sc": "South Carolina Department of Social Services, Division of Early Care and Education",
    "us-sd": "South Dakota Department of Social Services",
    "us-tn": "Tennessee Department of Human Services",
    "us-tx": "Texas Workforce Commission / Texas Health and Human Services Commission",
    "us-ut": "Utah Department of Workforce Services",
    "us-va": "Virginia Department of Social Services / Department of Education",
    "us-vt": "Vermont Department for Children and Families",
    "us-wa": "Washington State Department of Children, Youth, and Families / Legislature",
    "us-wi": "Wisconsin Department of Children and Families / Legislature",
    "us-wv": "West Virginia Department of Human Services, Bureau for Family Assistance",
    "us-wy": "Wyoming Department of Family Services",
}

# Labeled-section patterns for the New Jersey Administrative Code chapter PDFs that DHS posts
# (the OAL/Lexis export layout of the 2026-07-03 N.J.A.C. 10:90 manifest).
NJ_DROP = [
    r"^This file includes all Regulations adopted and published through the New Jersey Register",
    r"^NJ - New Jersey Administrative Code\s+>\s+TITLE 10\. HUMAN SERVICES",
    r"^SUBCHAPTER\s+\d+\.",
    r"^NEW JERSEY ADMINISTRATIVE CODE",
    r"^Copyright © 20\d\d by the New Jersey Office of Administrative\s+Law",
    r"^End of Document$",
    r"^Page \d+ of \d+$",
]


def njac(chapter: str, chapter_title: str) -> dict[str, Any]:
    return {
        "segmentation": "labeled_sections",
        "section_heading_pattern": (
            r"^§\s*(?P<label>" + chapter.replace(":", r"\:") + r"-[0-9A-Za-z.]+)\s+(?P<heading>.+)$"
        ),
        "drop_line_patterns": [
            *NJ_DROP,
            rf"^CHAPTER {chapter.split(':')[1]}\. {chapter_title}",
            rf"^N\.J\.A\.C\. {chapter}-",
        ],
    }


def d(
    rows: list[str],
    jur: str,
    cls: str,
    path: str,
    title: str,
    url: str,
    fmt: str,
    expr: str,
    program: str,
    subtype: str,
    *,
    extraction: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    note: str | None = None,
    authority: str | None = None,
    download_url: str | None = None,
) -> dict[str, Any]:
    return {
        "rows": rows,
        "jurisdiction": jur,
        "document_class": cls,
        "citation_path": path,
        "title": title,
        "source_url": url,
        "download_url": download_url,
        "source_format": fmt,
        "expression_date": expr,
        "program": program,
        "subtype": subtype,
        "extraction": extraction,
        "request": request,
        "note": note,
        "authority": authority,
    }


H = "html"
P = "pdf"
HTML_MAIN = {"html_content_selector": "main"}

DOCS: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- New Hampshire
    d(["https://gc.nh.gov/rules/state_agencies/he-c6900.html",
       "https://www.law.cornell.edu/regulations/new-hampshire/N-H-Admin-Code-SS-He-C-6910.06",
       "https://www.law.cornell.edu/regulations/new-hampshire/N-H-Admin-Code-SS-He-C-6910.07",
       "https://www.law.cornell.edu/regulations/new-hampshire/N-H-Admin-Code-SS-He-C-6910.09",
       "https://www.law.cornell.edu/regulations/new-hampshire/N-H-Admin-Code-SS-He-C-6910.17",
       "https://www.law.cornell.edu/regulations/new-hampshire/N-H-Admin-Code-SS-He-C-6910.18",
       "https://www.law.cornell.edu/regulations/new-hampshire/N-H-Code-Admin-R-He-C-6910-17"],
      "us-nh", "regulation", "us-nh/regulation/he-c-6900",
      "New Hampshire Code of Administrative Rules Chapter He-C 6900 Child Care Program "
      "(Part He-C 6910 Employment Related NH Child Care Scholarship Program Eligibility)",
      "https://gc.nh.gov/rules/state_agencies/he-c6900.html", H, "2026-08-20", "CCDF",
      "administrative_code_chapter",
      authority="New Hampshire General Court, Office of Legislative Services (Administrative Rules)",
      extraction={
          "html_content_selector": ".WordSection1",
          "segmentation": "labeled_sections",
          "section_heading_pattern": (
              r"^(?P<prefix>He-C)\s+(?P<part>69\d\d)\s*\.\s*(?P<section>\d+)\s*(?:[-\u2013]\s*)?"
              r"(?P<heading>(?:[A-Z].*?)?)(?:\s+\.\s+(?P<body>.+))?\.?$"
          ),
          "section_label_template": "{prefix} {part}.{section}",
          "stop_text_pattern": "^APPENDIX$",
      },
      note="the publisher's current chapter page (HTTP Last-Modified 2026-08-20), split on its section "
      "labels the way the He-W 700 SNAP rules scope is (the heading must start with a capital, so "
      "in-text cross-references such as 'He-C 6917.03(k) shall be' do not open a section); the "
      "rule-to-statute appendix table is not taken"),
    d(["https://www.dhhs.nh.gov/sites/g/files/ehbemt476/files/documents2/bcdhsc-form-2533.pdf"],
      "us-nh", "policy", "us-nh/policy/ccdf/rate-schedules/bcdhsc-form-2533-2024-08",
      "BCDHSC Form 2533 (August 2024, SR 24-23): Child Care Scholarship Program - Employment Related "
      "Maximum Weekly Rates",
      "https://www.dhhs.nh.gov/sites/g/files/ehbemt476/files/documents2/bcdhsc-form-2533.pdf", P,
      "2024-08-01", "CCDF", "rate_or_copay_schedule", request=CHROME),
    d(["https://www.dhhs.nh.gov/sr_htm/html/sr_24-08_dated_01_24.htm"],
      "us-nh", "guidance", "us-nh/guidance/dhhs/sr/sr-24-08",
      "NH DHHS Bureau of Family Assistance Supervisory Release SR 24-08 (dated 01/24)",
      "https://www.dhhs.nh.gov/sr_htm/html/sr_24-08_dated_01_24.htm", H, "2024-01-01", "TANF",
      "supervisory_release", request=CHROME),
    # ---------------------------------------------------------------- New Jersey
    d(["us-nj/regulation/njac-10-90",
       "https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-10-90-3-1",
       "https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-10-90-3-2",
       "https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-10-90-3-20",
       "https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-10-90-3-3",
       "https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-10-90-3-8"],
      "us-nj", "regulation", "us-nj/regulation/njac-10-90",
      "N.J.A.C. 10:90 Work First New Jersey Program",
      "https://www.nj.gov/humanservices/notices/documents/rules-and-regulations/WFNJ_Manual_12.17.24.pdf",
      P, "2024-12-16", "TANF", "administrative_code_chapter",
      extraction="FROM_MAIN_MANIFEST",
      authority="New Jersey Department of Human Services, Division of Family Development",
      note="entry copied from manifests/us-nj-wfnj-rules.yaml (EXTRACT-MANIFEST); compiled through "
      "N.J.R. Vol. 56 No. 24, December 16, 2024"),
    d(["https://www.nj.gov/humanservices/notices/documents/rules-and-regulations/NJAC%2010_15%20CHILD%20CARE%20SERVICES.PDF",
       "https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-10-15-5-2"],
      "us-nj", "regulation", "us-nj/regulation/njac-10-15", "N.J.A.C. 10:15 Child Care Services",
      "https://www.nj.gov/humanservices/notices/documents/rules-and-regulations/NJAC%2010_15%20CHILD%20CARE%20SERVICES.PDF",
      P, "2025-06-16", "CCDF", "administrative_code_chapter",
      extraction=njac("10:15", "CHILD CARE SERVICES"),
      note="compiled through N.J.R. Vol. 57 No. 12, June 16, 2025 (printed on page 1)"),
    d(["https://www.childcarenj.gov/ChildCareNJ/media/media_library/Copayment_Schedule.pdf"],
      "us-nj", "policy", "us-nj/policy/ccdf/rate-schedules/copayment-schedule-2026",
      "New Jersey Child Care Assistance Program Copayment Schedule (2026-2027)",
      "https://www.childcarenj.gov/ChildCareNJ/media/media_library/Copayment_Schedule.pdf", P,
      "2026-03-01", "CCDF", "rate_or_copay_schedule"),
    d(["https://www.childcarenj.gov/ChildCareNJ/media/media_library/Income_Eligibility_Schedule.pdf"],
      "us-nj", "policy", "us-nj/policy/ccdf/rate-schedules/income-eligibility-schedules-2026-03-01",
      "New Jersey DHS 2026-2027 Income Eligibility Schedules for Publicly Subsidized Child Care "
      "Assistance or Services (effective 3/1/26)",
      "https://www.childcarenj.gov/ChildCareNJ/media/media_library/Income_Eligibility_Schedule.pdf", P,
      "2026-03-01", "CCDF", "rate_or_copay_schedule"),
    d(["https://www.childcarenj.gov/ChildCareNJ/media/media_library/Max_CC_Payment_Rates.pdf",
       "http://www.bccap.org/wp-content/uploads/2024/03/Maximum-Child-Care-Payment-Rates-March-2024.pdf"],
      "us-nj", "policy", "us-nj/policy/ccdf/rate-schedules/maximum-child-care-payment-rates-2026-04-01",
      "New Jersey Maximum Child Care Payment Rates (effective April 1, 2026)",
      "https://www.childcarenj.gov/ChildCareNJ/media/media_library/Max_CC_Payment_Rates.pdf", P,
      "2026-04-01", "CCDF", "rate_or_copay_schedule"),
    d(["https://bergencountynj.gov/wp-content/uploads/2025/03/CC-230-March-2025-Rate-Chart.pdf"],
      "us-nj", "policy", "us-nj/policy/ccdf/rate-schedules/cc-230-rate-chart-2025-03-01-bergen-county",
      "CC-230 Child Care Rate Chart effective March 1, 2025 (as posted by the County of Bergen)",
      "https://bergencountynj.gov/wp-content/uploads/2025/03/CC-230-March-2025-Rate-Chart.pdf", P,
      "2025-03-01", "CCDF", "rate_or_copay_schedule",
      authority="County of Bergen, New Jersey (posting the DHS/DFD CC-230 rate chart)"),
    d(["https://www.childcarenj.gov/Parents/CCAP/ImportantInfo"],
      "us-nj", "guidance", "us-nj/guidance/dhs/childcarenj/ccap-important-information",
      "Child Care Assistance Program: Important Information (policy summaries for parents)",
      "https://www.childcarenj.gov/Parents/CCAP/ImportantInfo", H, SOURCE_AS_OF, "CCDF",
      "agency_web_page"),
    # ---------------------------------------------------------------- New Mexico
    d(["https://www.hca.nm.gov/2023/01/10/human-services-department-to-pass-through-more-money-to-low-income-families/"],
      "us-nm", "guidance", "us-nm/guidance/hca/news/2023-01-10-pass-through-more-money-to-low-income-families",
      "Human Services Department to pass through more money to low-income families (2023-01-10)",
      "https://www.hca.nm.gov/2023/01/10/human-services-department-to-pass-through-more-money-to-low-income-families/",
      H, "2023-01-10", "TANF", "press_release"),
    d(["PREFIX:https://www.hca.nm.gov/2023/09/01/state-announces-a-23-percent-increase"],
      "us-nm", "guidance", "us-nm/guidance/hca/news/2023-09-01-23-percent-increase-in-cash-assistance",
      "State announces a 23 percent increase in cash assistance for low-income New Mexico families (2023-09-01)",
      "PREFIX:https://www.hca.nm.gov/2023/09/01/state-announces-a-23-percent-increase",
      H, "2023-09-01", "TANF", "press_release"),
    d(["https://www.hca.nm.gov/lookingforassistance/temporary_assistance_for_needy_families/"],
      "us-nm", "guidance", "us-nm/guidance/hca/temporary-assistance-for-needy-families",
      "New Mexico Health Care Authority: Temporary Assistance for Needy Families",
      "https://www.hca.nm.gov/lookingforassistance/temporary_assistance_for_needy_families/", H,
      SOURCE_AS_OF, "TANF", "agency_web_page"),
    d(["PREFIX:https://www.hsd.state.nm.us/wp-content/uploads/FileLinks/f13cd6ab72d244089c5bf80111f07524/"],
      "us-nm", "guidance", "us-nm/guidance/hsd/tanf-new-mexico-works-fact-sheet-2017-01-20",
      "TANF / New Mexico Works Fact Sheet (updated 1.20.17)",
      "PREFIX:https://www.hsd.state.nm.us/wp-content/uploads/FileLinks/f13cd6ab72d244089c5bf80111f07524/",
      P, "2017-01-20", "TANF", "fact_sheet"),
    d(["https://www.nmlegis.gov/Publications/Session_Dates.pdf"],
      "us-nm", "guidance", "us-nm/guidance/legislature/session-dates",
      "New Mexico Legislature: Session Dates (current 2027 session and prior sessions)",
      "https://www.nmlegis.gov/Publications/Session_Dates.pdf", P, "2026-07-27", "CCDF",
      "legislative_reference", authority="New Mexico Legislature"),
    d(["https://www.nmlegis.gov/handouts/ALFC%20120825%20Item%208%20Policy%20Brief%20Child%20Care%20Update.pdf"],
      "us-nm", "guidance", "us-nm/guidance/lfc/2025-12-09-childcare-assistance-policy-brief",
      "Legislative Finance Committee policy brief: Health and Human Services: Childcare Assistance (December 9, 2025)",
      "https://www.nmlegis.gov/handouts/ALFC%20120825%20Item%208%20Policy%20Brief%20Child%20Care%20Update.pdf",
      P, "2025-12-09", "CCDF", "legislative_analysis", authority="New Mexico Legislative Finance Committee"),
    d(["https://www.nmececd.org/universal/"],
      "us-nm", "guidance", "us-nm/guidance/ececd/universal-child-care",
      "ECECD: Universal Child Care", "https://www.nmececd.org/universal/", H, SOURCE_AS_OF, "CCDF",
      "agency_web_page", authority="New Mexico Early Childhood Education and Care Department"),
    d(["https://www.nmececd.org/wp-content/uploads/2024/12/Parents-Guide-to-Child-Care_English.pdf"],
      "us-nm", "guidance", "us-nm/guidance/ececd/parents-guide-to-selecting-quality-child-care-2024-12",
      "ECECD Parents' Guide to Selecting Quality Child Care (December 2024)",
      "https://www.nmececd.org/wp-content/uploads/2024/12/Parents-Guide-to-Child-Care_English.pdf", P,
      "2024-12-12", "CCDF", "agency_guide", authority="New Mexico Early Childhood Education and Care Department"),
    d(["PREFIX:https://www.nmececd.org/wp-content/uploads/2024/05/Cost-Model-Reimbursement-Rate-Flyer"],
      "us-nm", "policy", "us-nm/policy/ccdf/rate-schedules/cost-model-reimbursement-rates-2024-05",
      "ECECD Child Care Assistance cost-model reimbursement rates flyer (May 2024)",
      "PREFIX:https://www.nmececd.org/wp-content/uploads/2024/05/Cost-Model-Reimbursement-Rate-Flyer",
      P, "2024-05-22", "CCDF", "rate_or_copay_schedule",
      authority="New Mexico Early Childhood Education and Care Department"),
    d(["https://www.nmececd.org/wp-content/uploads/2024/09/CCA-Co-payments-waived_rev1l.pdf"],
      "us-nm", "policy", "us-nm/policy/ccdf/rate-schedules/cca-copayments-waived",
      "ECECD Child Care Assistance Co-payments Waived (income table; updated April 2022, posted September 2024)",
      "https://www.nmececd.org/wp-content/uploads/2024/09/CCA-Co-payments-waived_rev1l.pdf", P,
      "2024-09-20", "CCDF", "rate_or_copay_schedule",
      authority="New Mexico Early Childhood Education and Care Department"),
    d(["https://www.hca.nm.gov/wp-content/uploads/HSR-Vol-41-No-17-with-proposed-rule.pdf"],
      "us-nm", "rulemaking", "us-nm/rulemaking/hca/hsr-vol-41-no-17",
      "New Mexico Human Services Register Vol. 41 No. 17, with proposed rule",
      "https://www.hca.nm.gov/wp-content/uploads/HSR-Vol-41-No-17-with-proposed-rule.pdf", P,
      "2021-02-01", "TANF", "register_notice", extraction={"ocr": True},
      note="image-only scan (no text layer); Tesseract page OCR"),
    d(["https://www.nmlegis.gov/Sessions/26%20Regular/final/SB0241.pdf"],
      "us-nm", "statute", "us-nm/statute/session-laws/2026/sb241",
      "New Mexico 2026 Regular Session SB 241 (final): Child Care Assistance Program Act",
      "https://www.nmlegis.gov/Sessions/26%20Regular/final/SB0241.pdf", P, "2026-03-10", "CCDF",
      "session_law", authority="New Mexico Legislature"),
    d(["https://www.srca.nm.gov/parts/title08/08.015.0002.html"],
      "us-nm", "regulation", "us-nm/regulation/nmac/8/15/2",
      "8.15.2 NMAC Requirements for Child Care Assistance Programs for Clients and Child Care Providers",
      "https://www.srca.nm.gov/parts/title08/08.015.0002.html", H, "2025-04-21", "CCDF",
      "administrative_code_part", authority="New Mexico Commission of Public Records, State Records Center and Archives",
      note="the part the bundle cites; 8.9.3 NMAC (ECECD) is the current child care assistance part "
      "(us-nm/regulation/2026-09-15-ccdf-subsidy-rules)"),
    d(["https://www.nmececd.org/wp-content/uploads/2025/11/8.9.3_integrated_FULL-TEXT.pdf"],
      "us-nm", "regulation", "us-nm/regulation/nmac/8/9/3--ececd-integrated-text-2025-11",
      "8.9.3 NMAC Child Care Assistance; Requirements for Child Care Assistance Programs (ECECD integrated full text, November 2025)",
      "https://www.nmececd.org/wp-content/uploads/2025/11/8.9.3_integrated_FULL-TEXT.pdf", P,
      "2025-11-12", "CCDF", "administrative_code_part",
      authority="New Mexico Early Childhood Education and Care Department",
      note="the issuing agency's integrated text; the SRCA part file is held as us-nm/regulation/nmac/8/9/3"),
    # ---------------------------------------------------------------- Nevada
    *[d([u], "us-nv", "guidance", f"us-nv/guidance/dss/tanf-faq/{slug}", f"Nevada TANF FAQ: {t}", u, H,
        SOURCE_AS_OF, "TANF", "agency_web_page")
      for u, slug, t in [
          ("https://dss.nv.gov/TANF/TANF_FAQ/", "facts-and-faqs", "Facts & FAQs"),
          ("https://dss.nv.gov/TANF/TANF_FAQ-Eligibility_Criteria-F/I/", "eligibility-criteria-f-i", "Eligibility - Criteria F/I"),
          ("https://dss.nv.gov/TANF/TANF_FAQ-Eligibility_Criteria-Income-Consid-1/", "earned-income-disregards", "Eligibility - Earned Income Disregards"),
          ("https://dss.nv.gov/TANF/TANF_FAQ-Eligibility_Criteria-Income-Consid-2/", "need-and-payment-standards", "Eligibility - Need / Payment Standards"),
          ("https://dss.nv.gov/TANF/TANF_FAQ-Eligibility_Criteria-R/S/", "eligibility-criteria-r-s", "Eligibility - Criteria R/S"),
      ]],
    d(["https://dss.nv.gov/uploadedFiles/dwssnvgov/content/Home/Features/Chapter%20A_1000%2012-15-15.pdf"],
      "us-nv", "manual", "us-nv/manual/dwss/eligibility-payments/a-1000-2015-12-15",
      "DWSS Eligibility and Payments Manual Chapter A-1000 Introduction of TANF Cash Programs (12-15-15)",
      "https://dss.nv.gov/uploadedFiles/dwssnvgov/content/Home/Features/Chapter%20A_1000%2012-15-15.pdf", P,
      "2015-12-15", "TANF", "agency_manual_chapter"),
    d(["https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/eligibility/chapter-c_140.pdf",
       "https://drive.google.com/file/d/1v1jiPfl1pzrKPcJGg0gRjNOLErIjbHA3/view?usp=sharing",
       "https://drive.google.com/file/d/1xX0U05I3wfeiGY0wfjIB6rxcauE_kFLX/view?usp=sharing"],
      "us-nv", "manual", "us-nv/manual/dwss/eligibility-payments/c-140",
      "Eligibility and Payments Manual Chapter C-140 TANF Need Standards",
      "https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/eligibility/chapter-c_140.pdf", P,
      "2026-02-23", "TANF", "agency_manual_chapter",
      note="the publisher's current chapter (HTTP Last-Modified 2026-02-23); the bundle's two Google "
      "Drive copies (EP_Man_C-0140.pdf, 'Chapter C_140 2018.pdf') are third-party reposts"),
    d(["https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/care/Child_Care_Manual_July_2024.pdf"],
      "us-nv", "manual", "us-nv/manual/dwss/child-care-policy-manual-2024-07",
      "DWSS Child Care Policy Manual (July 2024)",
      "https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/care/Child_Care_Manual_July_2024.pdf", P,
      "2024-07-11", "CCDF", "agency_manual"),
    d(["https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/care/CC_PT_06-25_ANNUAL_INCOME_CHANGES_10.02.2025.pdf"],
      "us-nv", "policy", "us-nv/policy/ccdf/policy-transmittals/cc-pt-06-25-annual-income-changes",
      "Child Care and Development Program Policy Transmittal CC PT 06-25: Annual Income Changes (10.02.2025)",
      "https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/care/CC_PT_06-25_ANNUAL_INCOME_CHANGES_10.02.2025.pdf",
      P, "2025-10-02", "CCDF", "policy_transmittal"),
    d(["https://dss.nv.gov/uploadedFiles/dwssnvgov/content/TANF/TANF_State_Plan_FINAL%20_Effective_12.31.20.pdf"],
      "us-nv", "policy", "us-nv/policy/acf/tanf-plan/effective-2020-12-31",
      "State of Nevada TANF State Plan (effective 12.31.20)",
      "https://dss.nv.gov/uploadedFiles/dwssnvgov/content/TANF/TANF_State_Plan_FINAL%20_Effective_12.31.20.pdf",
      P, "2020-12-31", "TANF", "tanf_state_plan",
      note="the plan the bundle cites; the current FFY24 plan is us-nv/policy/acf/tanf-plan/fy2024"),
    # ---------------------------------------------------------------- New York
    d(["https://dos.ny.gov/system/files/documents/2024/05/050124.pdf"],
      "us-ny", "rulemaking", "us-ny/rulemaking/dos/state-register-2024-05-01",
      "New York State Register, Vol. XLVI Issue 18 (May 1, 2024)",
      "https://dos.ny.gov/system/files/documents/2024/05/050124.pdf", P, "2024-05-01", "CCDF",
      "state_register_issue", authority="New York Department of State, Division of Administrative Rules",
      note="carries OCFS's Expansion of Eligibility for Child Care Assistance Program notice"),
    d(["https://www.nysenate.gov/legislation/laws/SOS/410-U"],
      "us-ny", "statute", "us-ny/statute/SOS/410-U",
      "N.Y. Social Services Law § 410-u Establishment of block grant for child care",
      "https://www.nysenate.gov/legislation/laws/SOS/410-U", H, SOURCE_AS_OF, "CCDF", "statute_section",
      extraction={"html_content_selector": "div.nys-openleg-result-text"}, request=CHROME,
      authority="New York State Senate (Open Legislation)"),
    d(["https://www.nysenate.gov/legislation/laws/SOS/410-W"],
      "us-ny", "statute", "us-ny/statute/SOS/410-W",
      "N.Y. Social Services Law § 410-w Eligibility",
      "https://www.nysenate.gov/legislation/laws/SOS/410-W", H, SOURCE_AS_OF, "CCDF", "statute_section",
      extraction={"html_content_selector": "div.nys-openleg-result-text"}, request=CHROME,
      authority="New York State Senate (Open Legislation)"),
    # ---------------------------------------------------------------- Ohio
    *[d([u], "us-oh", "regulation", f"us-oh/regulation/agency-5180-2/chapter-5180-2-16/{slug}", t, u, P, e,
        "CCDF", "administrative_rule_version", authority="Ohio Legislative Service Commission (codes.ohio.gov)",
        note="authenticated rule version the bundle cites; the publicly funded child care rules are now "
        "OAC 5180:6-1 (us-oh/regulation/2026-09-15-ccdf-subsidy-rules-agency-5180-6-chapter-5180-6-1)")
      for u, slug, t, e in [
          ("https://codes.ohio.gov/assets/laws/administrative-code/authenticated/5180/2/16/5180$2-16-01_20221211.pdf",
           "rule-5180-2-16-01--effective-2022-12-11",
           "OAC 5180:2-16-01 Definitions for eligibility for publicly funded child care benefits (effective December 11, 2022)",
           "2022-12-11"),
          ("https://codes.ohio.gov/assets/laws/administrative-code/authenticated/5180/2/16/5180$2-16-03_20220227.pdf",
           "rule-5180-2-16-03--effective-2022-02-27",
           "OAC 5180:2-16-03 Income eligibility requirements for publicly funded child care benefits (effective February 27, 2022)",
           "2022-02-27"),
          ("https://codes.ohio.gov/assets/laws/administrative-code/authenticated/5180/2/16/5180$2-16-05_20221211.pdf",
           "rule-5180-2-16-05--effective-2022-12-11",
           "OAC 5180:2-16-05 Copayment for publicly funded child care benefits (effective December 11, 2022)",
           "2022-12-11"),
          ("https://codes.ohio.gov/assets/laws/administrative-code/authenticated/5180/2/16/5180$2-16-09_20231007.pdf",
           "rule-5180-2-16-09--effective-2023-10-07",
           "OAC 5180:2-16-09 Provider responsibilities for publicly funded child care (effective October 7, 2023)",
           "2023-10-07"),
          ("PREFIX:https://codes.ohio.gov/assets/laws/administrative-code/pdfs/5180/2/16/5180$2-16-05_PH_FF_A_APP5",
           "rule-5180-2-16-05-appendix-5--2022-12-01",
           "OAC 5180:2-16-05 Appendix: copayment multiplier by percent of FPL (filed 2022-12-01)",
           "2022-12-01"),
      ]],
    d(["PREFIX:https://codes.ohio.gov/assets/laws/administrative-code/pdfs/5180/6/1/5180$6-1-10_PH_FF_N_APP1"],
      "us-oh", "regulation", "us-oh/regulation/agency-5180-6/chapter-5180-6-1/rule-5180-6-1-10-appendix-1--2025-10-20",
      "OAC 5180:6-1-10 Appendix 1: publicly funded child care payment rates (filed 2025-10-20)",
      "PREFIX:https://codes.ohio.gov/assets/laws/administrative-code/pdfs/5180/6/1/5180$6-1-10_PH_FF_N_APP1",
      P, "2025-10-20", "CCDF", "administrative_rule_appendix",
      authority="Ohio Legislative Service Commission (codes.ohio.gov)"),
    *[d([u], "us-oh", "statute", f"us-oh/statute/{sec}", f"Ohio Revised Code Section {sec}", u, H, SOURCE_AS_OF,
        "TANF", "statute_section", extraction={"html_content_selector": "section.laws-body"},
        authority="Ohio Legislative Service Commission (codes.ohio.gov)")
      for u, sec in [("https://codes.ohio.gov/ohio-revised-code/section-5107.04", "5107.04"),
                     ("https://codes.ohio.gov/ohio-revised-code/section-5107.10", "5107.10")]],
    d(["PLACEHOLDER_OH_PL21"],
      "us-oh", "guidance", "us-oh/guidance/dcy/procedure-letter-21-2025-08-29",
      "Ohio Department of Children and Youth Procedure Letter 21 (August 29, 2025; revised September 11, 2025)",
      "PLACEHOLDER_OH_PL21", P, "2025-08-29", "CCDF", "procedure_letter",
      authority="Ohio Department of Children and Youth"),
    d(["PLACEHOLDER_OH_ACTL297"],
      "us-oh", "guidance", "us-oh/guidance/odjfs/cash-assistance-manual-actl-297",
      "ODJFS Cash Assistance Manual Action Change Transmittal Letter No. 297: January 1, 2026 Ohio Works First "
      "and Refugee Cash Assistance Cost-of-Living Increase (November 25, 2025)",
      "PLACEHOLDER_OH_ACTL297", P, "2025-11-25", "TANF", "manual_transmittal",
      authority="Ohio Department of Job and Family Services"),
    # ---------------------------------------------------------------- Oklahoma
    d(["https://oklahoma.gov/content/dam/ok/en/okdhs/documents/searchcenter/okdhsformresults/c-4-b.pdf"],
      "us-ok", "policy", "us-ok/policy/ccdf/rate-schedules/appendix-c-4-b-child-care-provider-rate-schedule",
      "OKDHS Appendix C-4-B Child Care Provider Rate Schedule",
      "https://oklahoma.gov/content/dam/ok/en/okdhs/documents/searchcenter/okdhsformresults/c-4-b.pdf", P,
      "2026-05-08", "CCDF", "rate_or_copay_schedule"),
    d(["https://oklahoma.gov/content/dam/ok/en/okdhs/documents/searchcenter/okdhsformresults/c-4.pdf"],
      "us-ok", "policy", "us-ok/policy/ccdf/rate-schedules/appendix-c-4-eligibility-copayment-chart-2026-10-01",
      "OKDHS Appendix C-4 Child Care Eligibility/Copayment Chart (10/1/2026)",
      "https://oklahoma.gov/content/dam/ok/en/okdhs/documents/searchcenter/okdhsformresults/c-4.pdf", P,
      "2026-10-01", "CCDF", "rate_or_copay_schedule"),
    d(["https://www.okdhslive.org/popups/IncomeStandardsPopup.aspx"],
      "us-ok", "policy", "us-ok/policy/okdhs/maximum-income-resource-and-payment-standards",
      "OKDHS Live: Maximum Income, Resource, and Payment Standards",
      "https://www.okdhslive.org/popups/IncomeStandardsPopup.aspx", H, SOURCE_AS_OF, "TANF",
      "standards_table", authority="Oklahoma Human Services (OKDHS Live online services)"),
    # ---------------------------------------------------------------- Oregon
    d(["https://www.oregon.gov/delc/programs/pages/erdc.aspx"],
      "us-or", "guidance", "us-or/guidance/delc/erdc-program",
      "DELC Child Care Assistance: Employment Related Day Care (ERDC) program",
      "https://www.oregon.gov/delc/programs/pages/erdc.aspx", H, SOURCE_AS_OF, "CCDF", "agency_web_page"),
    d(["https://www.oregon.gov/delc/programs/pages/rates.aspx"],
      "us-or", "guidance", "us-or/guidance/delc/erdc-child-care-maximum-rates",
      "DELC ERDC Child Care Maximum Rates", "https://www.oregon.gov/delc/programs/pages/rates.aspx", H,
      SOURCE_AS_OF, "CCDF", "agency_web_page"),
    d(["https://www.oregon.gov/delc/providers/Documents/Provider%20Rate%20Increase%20For%20Jan%202026_Phase%202_ENG.pdf",
       "https://www.oregon.gov/delc/programs/ERDC%20Fliers/Provider%20Guide%20Insert%20Final%20EN.pdf"],
      "us-or", "policy", "us-or/policy/ccdf/rate-schedules/erdc-provider-guide-insert-delc-7492i-2026-02-27",
      "ERDC Provider Guide Insert (DELC 7492i, 2/27/2026): provider rate increase for January 2026, Phase 2",
      "https://www.oregon.gov/delc/providers/Documents/Provider%20Rate%20Increase%20For%20Jan%202026_Phase%202_ENG.pdf",
      P, "2026-02-27", "CCDF", "rate_or_copay_schedule"),
    # ---------------------------------------------------------------- Pennsylvania
    d(["https://www.pa.gov/agencies/dhs/resources/cash-assistance/tanf"],
      "us-pa", "guidance", "us-pa/guidance/dhs/cash-assistance-tanf",
      "PA DHS: Temporary Assistance for Needy Families (TANF)",
      "https://www.pa.gov/agencies/dhs/resources/cash-assistance/tanf", H, SOURCE_AS_OF, "TANF",
      "agency_web_page"),
    d(["https://www.pa.gov/agencies/dhs/resources/early-learning-child-care/elrc/"],
      "us-pa", "guidance", "us-pa/guidance/dhs/early-learning-resource-centers",
      "PA DHS: Early Learning Resource Centers (ELRC)",
      "https://www.pa.gov/agencies/dhs/resources/early-learning-child-care/elrc/", H, SOURCE_AS_OF, "CCDF",
      "agency_web_page"),
    d(["PLACEHOLDER_PA_MCCA"],
      "us-pa", "policy", "us-pa/policy/ccdf/rate-schedules/mcca-rates-by-region",
      "Pennsylvania Maximum Child Care Allowance (MCCA) rates by region", "PLACEHOLDER_PA_MCCA", P,
      "2024-01-24", "CCDF", "rate_or_copay_schedule"),
    d(["https://www.pacodeandbulletin.gov/secure/pacode/data/055/chapter3042/055_3042.pdf"],
      "us-pa", "regulation", "us-pa/regulation/title-55/chapter-3042-pdf",
      "55 Pa. Code Chapter 3042 Subsidized Child Care Eligibility",
      "https://www.pacodeandbulletin.gov/secure/pacode/data/055/chapter3042/055_3042.pdf", P, "2026-09-03",
      "CCDF", "administrative_code_chapter", authority="Pennsylvania Legislative Reference Bureau (Pennsylvania Code)"),
    d(["https://www.law.cornell.edu/regulations/pennsylvania/55-Pa-Code-SS-183-94"],
      "us-pa", "regulation", "us-pa/regulation/title-55/chapter-183-pdf",
      "55 Pa. Code Chapter 183 Standards for Need and Amount of Assistance (incl. § 183.94)",
      "https://www.pacodeandbulletin.gov/secure/pacode/data/055/chapter183/055_0183.pdf", P, SOURCE_AS_OF,
      "TANF", "administrative_code_chapter", authority="Pennsylvania Legislative Reference Bureau (Pennsylvania Code)",
      note="linked as the chapter PDF from the Pennsylvania Code chapter 183 table of contents"),
    # ---------------------------------------------------------------- Rhode Island
    *[d([u], "us-ri", "policy", f"us-ri/policy/ccdf/rate-schedules/{slug}", t, u, P, e, "CCDF",
        "rate_or_copay_schedule")
      for u, slug, t, e in [
          ("https://dhs.ri.gov/media/10606/download?language=en", "ccap-family-co-share-levels-2026-02-15",
           "RI DHS CCAP Family Co-Share Levels - 2026 (effective 02/15/26)", "2026-02-15"),
          ("https://dhs.ri.gov/media/3556/download?language=en", "ccap-licensed-exempt-weekly-rates-2022-01-01",
           "RI DHS CCAP Licensed Exempt Child Care Weekly Rates (effective January 1, 2022)", "2022-01-01"),
          ("https://dhs.ri.gov/media/5006/download?language=en", "ccap-licensed-family-child-care-weekly-rates-2023-01-01",
           "RI DHS CCAP Licensed Family Child Care Weekly Rates (effective January 1, 2023)", "2023-01-01"),
          ("https://dhs.ri.gov/media/7481/download?language=en", "ccap-weekly-rates-2024-07-01",
           "RI DHS CCAP weekly rates (effective July 1, 2024)", "2024-07-01"),
          ("https://dhs.ri.gov/media/9356/download?language=en", "ccap-weekly-rates-2025-07-01",
           "RI DHS CCAP weekly rates (effective July 1, 2025)", "2025-07-01"),
      ]],
    *[d([u], "us-ri", "guidance", f"us-ri/guidance/dhs/{slug}", t, u, H, e, "TANF", k)
      for u, slug, t, e, k in [
          ("https://dhs.ri.gov/press-releases/ri-works-benefit-increase-almost-here", "ri-works-benefit-increase-almost-here",
           "RI DHS press release: RI Works Benefit Increase is Almost Here!", SOURCE_AS_OF, "press_release"),
          ("https://dhs.ri.gov/programs-and-services/ri-works-program", "ri-works-program",
           "RI DHS: Rhode Island Works", SOURCE_AS_OF, "agency_web_page"),
          ("https://dhs.ri.gov/programs-and-services/ri-works-program/eligibility-how-apply",
           "ri-works-eligibility-how-to-apply", "RI DHS: Rhode Island Works - Eligibility & How to Apply",
           SOURCE_AS_OF, "agency_web_page"),
      ]],
    d(["https://www.rilegislature.gov/sfiscal/Other%20Documents/Rhode%20Island%20Works.pdf"],
      "us-ri", "guidance", "us-ri/guidance/senate-fiscal-office/rhode-island-works-2011-02-15",
      "Senate Fiscal Office Issue Brief: Rhode Island Works (February 15, 2011)",
      "https://www.rilegislature.gov/sfiscal/Other%20Documents/Rhode%20Island%20Works.pdf", P, "2011-02-15",
      "TANF", "legislative_analysis", authority="Rhode Island Senate Fiscal Office"),
    d(["https://webserver.rilegislature.gov/PublicLaws/law25/law25278-10.htm"],
      "us-ri", "statute", "us-ri/statute/session-laws/2025/278-article-10",
      "Rhode Island Public Laws 2025, chapter 278, Article 10 (Relating to Health and Human Services)",
      "https://webserver.rilegislature.gov/PublicLaws/law25/law25278-10.htm", H, "2025-10-17", "CCDF",
      "session_law", authority="Rhode Island General Assembly"),
    # ---------------------------------------------------------------- South Carolina
    d(["https://www.scchildcare.org/media/n3qmcb5u/sc-child-care-scholarship-program-fee-scale-2023-2024.pdf"],
      "us-sc", "policy", "us-sc/policy/ccdf/rate-schedules/scholarship-fee-scale-2023-2024",
      "SC Child Care Scholarship Program Child Development Fee Scale (October 1, 2023 - September 30, 2024)",
      "https://www.scchildcare.org/media/n3qmcb5u/sc-child-care-scholarship-program-fee-scale-2023-2024.pdf", P,
      "2023-10-01", "CCDF", "rate_or_copay_schedule",
      note="the edition the bundle cites; the 2025-2026 fee scale is us-sc/policy/ccdf/rate-schedules/scholarship-fee-scale-2025-2026"),
    d(["https://www.law.cornell.edu/regulations/south-carolina/R-114-1140",
       "https://www.law.cornell.edu/regulations/south-carolina/S.C.-Code-Regs.-114-1140"],
      "us-sc", "regulation", "us-sc/regulation/chapter-114-pdf",
      "South Carolina Code of Regulations Chapter 114 (Department of Social Services), incl. R. 114-1140",
      "https://www.scstatehouse.gov/coderegs/Chapter%20114.pdf", P, SOURCE_AS_OF, "TANF",
      "administrative_code_chapter", authority="South Carolina Legislative Council (Code of Regulations)",
      note="linked from the Legislative Council's Code of Regulations index (coderegs/statmast.php)"),
    # ---------------------------------------------------------------- South Dakota
    d(["https://dss.sd.gov/docs/childcare/assistance/BEES_CCA_Policy_Manual.pdf",
       "https://dss.sd.gov/docs/childcare/assistance/Subsidy_Manual.pdf"],
      "us-sd", "manual", "us-sd/manual/dss/child-care-assistance-policy-manual-2026-08",
      "SD DSS Division of Economic Assistance Child Care Assistance Policy Manual (August 2026)",
      "https://dss.sd.gov/docs/childcare/assistance/BEES_CCA_Policy_Manual.pdf", P, "2026-08-01", "CCDF",
      "agency_manual"),
    *[d([u], "us-sd", "policy", f"us-sd/policy/ccdf/rate-schedules/{slug}", t, u, P, e, "CCDF",
        "rate_or_copay_schedule")
      for u, slug, t, e in [
          ("https://dss.sd.gov/docs/childcare/assistance/CCA_Weekly_Reimbursement_Rates.pdf",
           "cca-weekly-reimbursement-rates", "SD Child Care Assistance Weekly Reimbursement Rates", "2026-09-21"),
          ("https://dss.sd.gov/docs/childcare/assistance/Provider_Rate_Regions.pdf",
           "provider-rate-regions", "SD Child Care Assistance Provider Rate Regions", "2026-05-29"),
          ("https://dss.sd.gov/docs/childcare/assistance/Sliding_Fee_Scale.pdf",
           "sliding-fee-scale", "SD Child Care Assistance Sliding Fee Scale", "2026-03-02"),
      ]],
    *[d([f"https://sdlegislature.gov/api/Rules/Archived/{n}.pdf"], "us-sd", "regulation",
        f"us-sd/regulation/arsd/67/10/05/03--archived-{n}",
        f"ARSD 67:10:05:03 Payment standard (archived rule version {n})",
        f"https://sdlegislature.gov/api/Rules/Archived/{n}.pdf", P, SOURCE_AS_OF, "TANF",
        "archived_rule_version", authority="South Dakota Legislative Research Council",
        note="archived version of 67:10:05:03; the current rule is us-sd/regulation/arsd/67/10/05/03 "
        "(us-sd/regulation/2026-09-10-tanf-state-policy-manual)")
      for n in ("10994", "11393", "12036", "14008")],
    # ---------------------------------------------------------------- Tennessee
    d(["https://www.tn.gov/content/dam/tn/human-services/documents/Income%20Eligibility%20and%20Co-Pay%20Chart_June_1_2024.pdf"],
      "us-tn", "policy", "us-tn/policy/ccdf/rate-schedules/income-eligibility-and-copay-chart-2024-06-01",
      "Tennessee Child Care Certificate Program Income Eligibility Limits and Parent Co-Pay Fees (effective June 1, 2024)",
      "https://www.tn.gov/content/dam/tn/human-services/documents/Income%20Eligibility%20and%20Co-Pay%20Chart_June_1_2024.pdf",
      P, "2024-06-01", "CCDF", "rate_or_copay_schedule"),
    d(["https://www.tn.gov/humanservices/for-families/child-care-services/update-on-child-care-funding.html"],
      "us-tn", "guidance", "us-tn/guidance/dhs/update-on-child-care-funding",
      "TDHS: Update on Child Care Funding - Frequently Asked Questions",
      "https://www.tn.gov/humanservices/for-families/child-care-services/update-on-child-care-funding.html", H,
      SOURCE_AS_OF, "CCDF", "agency_web_page"),
    # ---------------------------------------------------------------- Texas
    d(["https://fhb.hhs.texas.gov/sites/default/files/documents/mepd-and-twh-Bulletin-24-12.pdf"],
      "us-tx", "guidance", "us-tx/guidance/hhsc/mepd-and-tw-bulletin-24-12",
      "HHSC MEPD and Texas Works Bulletin 24-12 (October 1, 2024)",
      "https://fhb.hhs.texas.gov/sites/default/files/documents/mepd-and-twh-Bulletin-24-12.pdf", P,
      "2024-10-01", "TANF", "handbook_bulletin"),
    *[d([u], "us-tx", "policy", f"us-tx/policy/ccdf/rate-schedules/{slug}", t, u, P, e, "CCDF",
        "rate_or_copay_schedule")
      for u, slug, t, e in [
          ("https://www.twc.texas.gov/sites/default/files/ccel/docs/bcy-26-psoc-chart-twc.pdf",
           "psoc-sliding-fee-scale-bcy2026", "TWC Parent Share of Cost (PSoC) Sliding Fee Scale (BCY2026)", "2025-10-01"),
          ("https://www.twc.texas.gov/sites/default/files/ccel/docs/bcy2025-psoc-chart-twc.pdf",
           "psoc-sliding-fee-scale-bcy2025", "TWC Parent Share of Cost (PSOC) Sliding Fee Scale (BCY2025)", "2024-10-01"),
          ("https://www.twc.texas.gov/sites/default/files/ccel/docs/bcy25-board-max-provider-payment-rates-4-age-groups-twc.pdf",
           "board-max-provider-payment-rates-bcy2025",
           "TWC Board Contract Year 2025 Child Care Provider Payment Rates (effective October 1, 2024; WD Letter 19-24, Attachment 1)",
           "2024-10-01"),
          ("https://www.twc.texas.gov/sites/default/files/ccel/docs/bcy26-board-max-provider-payment-rates-twc.pdf",
           "board-max-provider-payment-rates-bcy2026",
           "TWC Board Contract Year 2026 Child Care Provider Payment Rates (effective October 1, 2025; WD Letter 08-25)",
           "2025-10-01"),
      ]],
    d(["https://www.twc.texas.gov/sites/default/files/wf/docs/workforce-board-directory-twc.pdf"],
      "us-tx", "guidance", "us-tx/guidance/twc/workforce-development-board-directory",
      "TWC Workforce Development Board Directory (as of July 16, 2026)",
      "https://www.twc.texas.gov/sites/default/files/wf/docs/workforce-board-directory-twc.pdf", P,
      "2026-07-16", "CCDF", "directory"),
    d(["https://wspanhandle.com/child-care/for-parents/"],
      "us-tx", "guidance", "us-tx/guidance/workforce-solutions-panhandle/child-care-for-parents",
      "Workforce Solutions Panhandle: Child Care Assistance Information for Parents",
      "https://wspanhandle.com/child-care/for-parents/", H, SOURCE_AS_OF, "CCDF", "local_board_web_page",
      authority="Workforce Solutions Panhandle (Panhandle Workforce Development Board, Panhandle Regional Planning Commission)"),
    # ---------------------------------------------------------------- Utah
    d(["https://jobs.utah.gov/customereducation/services/childcare/occsubsidyfact.pdf"],
      "us-ut", "guidance", "us-ut/guidance/dws/child-care-subsidy-fact-sheet",
      "DWS Child Care Assistance fact sheet",
      "https://jobs.utah.gov/customereducation/services/childcare/occsubsidyfact.pdf", P, "2026-08-31",
      "CCDF", "fact_sheet"),
    d(["PLACEHOLDER_UT_T1_2008"],
      "us-ut", "manual", "us-ut/manual/dws/eligibility-manual/obsolete-table-1-2008-to-2012-04-30",
      "DWS Eligibility Manual: Obsolete Table 1 (2008 to 04/30/12)", "PLACEHOLDER_UT_T1_2008", H,
      "2012-04-30", "TANF", "obsolete_manual_table"),
    d(["PLACEHOLDER_UT_T1_2012"],
      "us-ut", "manual", "us-ut/manual/dws/eligibility-manual/obsolete-table-1-2012-05-01-to-2022-09-30",
      "DWS Eligibility Manual: Obsolete Table 1 (05/01/12 to 09/30/22)", "PLACEHOLDER_UT_T1_2012", H,
      "2022-09-30", "TANF", "obsolete_manual_table"),
    d(["https://jobs.utah.gov/occ/provider/r986700.pdf",
       "https://www.law.cornell.edu/regulations/utah/Utah-Admin-Code-R986-700-702",
       "https://www.law.cornell.edu/regulations/utah/Utah-Admin-Code-R986-700-707",
       "https://www.law.cornell.edu/regulations/utah/Utah-Admin-Code-R986-700-709",
       "https://www.law.cornell.edu/regulations/utah/Utah-Admin-Code-R986-700-710",
       "https://www.law.cornell.edu/regulations/utah/Utah-Admin-Code-R986-700-713"],
      "us-ut", "regulation", "us-ut/regulation/admin-rules/r986/700",
      "Utah Administrative Code R986-700: Child Care Assistance",
      "https://jobs.utah.gov/occ/provider/r986700.pdf", P, "2025-02-12", "CCDF", "administrative_code_rule",
      note="the agency's posting of R986-700 (the rule text as filed with the Office of Administrative Rules)"),
    # ---------------------------------------------------------------- Virginia
    *[d([u], "us-va", "guidance", f"us-va/guidance/budget/{slug}", t, u, H, e, p, "budget_amendment",
        authority="Virginia General Assembly, Division of Legislative Automated Systems (State Budget)")
      for u, slug, t, e, p in [
          ("https://budget.lis.virginia.gov/amendment/2015/1/HB1400/Introduced/CR/335/1c/", "2015-hb1400-item-335-1c",
           "2015 HB1400 Conference Report amendment 335#1c (DSS) Increase TANF Payments 2.5 percent", "2015-02-01", "TANF"),
          ("https://budget.lis.virginia.gov/amendment/2019/1/SB1100/Introduced/CA/340/1s/", "2019-sb1100-item-340-1s",
           "2019 SB1100 Committee Approved amendment 340#1s (DSS) Increase TANF Benefits by Five Percent", "2019-02-01", "TANF"),
          ("https://budget.lis.virginia.gov/amendment/2020/1/hb30/introduced/cr/350/1c/", "2020-hb30-item-350-1c",
           "2020 HB30 Conference Report amendment 350#1c (DSS) Increase TANF Payment and Income Eligibility", "2020-03-01", "TANF"),
          ("https://budget.lis.virginia.gov/amendment/2021/2/HB1800/introduced/CR/350/2c/", "2021-hb1800-item-350-2c",
           "2021 HB1800 Conference Report amendment 350#2c (DSS) Increase TANF Benefits 10 Percent", "2021-02-01", "TANF"),
          ("https://budget.lis.virginia.gov/amendment/2022/2/HB30/Introduced/CR/341/2c/", "2022-hb30-item-341-2c",
           "2022 HB30 Conference Report amendment 341#2c (DSS) Increase TANF Standards of Assistance", "2022-06-01", "TANF"),
          ("https://budget.lis.virginia.gov/item/2025/1/HB1600/Chapter/1/125.10/", "2025-hb1600-chapter-725-item-125.10",
           "2025 HB1600 Chapter 725 Item 125.10 (DOE) Early Childhood Care and Education Programs", "2025-07-01", "CCDF"),
      ]],
    *[d([u], "us-va", "regulation", path, t, u, H, SOURCE_AS_OF, p, "administrative_code_section",
        extraction={"html_content_selector": "article"},
        authority="Virginia General Assembly, Division of Legislative Automated Systems (Virginia Administrative Code)")
      for u, path, t, p in [
          ("https://law.lis.virginia.gov/admincode/title22/agency40/chapter295/section50/",
           "us-va/regulation/title-22/agency-40/chapter-295/section-50", "22VAC40-295-50. Income eligibility.", "TANF"),
          ("https://law.lis.virginia.gov/admincode/title8/agency20/chapter790/section20/",
           "us-va/regulation/title-8/agency-20/chapter-790/section-20", "8VAC20-790-20. Families and children to be served.", "CCDF"),
          ("https://law.lis.virginia.gov/admincode/title8/agency20/chapter790/section40/",
           "us-va/regulation/title-8/agency-20/chapter-790/section-40", "8VAC20-790-40. Case management.", "CCDF"),
      ]],
    d(["https://rga.lis.virginia.gov/Published/2023/RD81/PDF"],
      "us-va", "guidance", "us-va/guidance/rga/2023-rd81",
      "VDSS report to the Governor and General Assembly, RD81 (2023), memorandum dated January 26, 2023",
      "https://rga.lis.virginia.gov/Published/2023/RD81/PDF", P, "2023-01-26", "TANF", "agency_report",
      authority="Virginia Department of Social Services (Reports to the General Assembly)"),
    d(["PLACEHOLDER_VA_TOWNHALL"],
      "us-va", "guidance", "us-va/guidance/townhall/doe-gdoc-8298-ccsp-guidance-manual-proposed-2025",
      "Child Care Subsidy Program Guidance Manual, proposed revised guidance (Virginia Regulatory Town Hall GDoc DOE 8298, 2025-08-05)",
      "PLACEHOLDER_VA_TOWNHALL", P, "2025-08-05", "CCDF", "proposed_guidance_document",
      authority="Virginia Department of Education (Virginia Regulatory Town Hall)"),
    d(["https://www.childcare.virginia.gov/home/showpublisheddocument/65775/638937831784030000"],
      "us-va", "policy", "us-va/policy/ccdf/rate-schedules/ccsp-per-child-copayment-amounts-2026-10-01",
      "Child Care Subsidy Program (CCSP) Per-Child Copayment Amounts by Family Income (updated September 2, 2026; effective October 1, 2026)",
      "https://www.childcare.virginia.gov/home/showpublisheddocument/65775/638937831784030000", P, "2026-10-01",
      "CCDF", "rate_or_copay_schedule", authority="Virginia Department of Education"),
    d(["https://www.childcare.virginia.gov/home/showpublisheddocument/66667/638981099706730000"],
      "us-va", "manual", "us-va/manual/doe/child-care-subsidy-program-guidance-manual-2025-10-09",
      "Child Care Subsidy Program Guidance Manual (revised guidance effective October 9, 2025)",
      "https://www.childcare.virginia.gov/home/showpublisheddocument/66667/638981099706730000", P, "2025-10-09",
      "CCDF", "agency_manual", authority="Virginia Department of Education"),
    # ---------------------------------------------------------------- Vermont
    d(["https://legislature.vermont.gov/statutes/fullchapter/33/011"],
      "us-vt", "statute", "us-vt/statute/33/chapter-11",
      "33 V.S.A. Chapter 11: Reach Up (full chapter)",
      "https://legislature.vermont.gov/statutes/fullchapter/33/011", H, SOURCE_AS_OF, "TANF", "statute_chapter",
      authority="Vermont General Assembly (Vermont Statutes Online)"),
    d(["https://legislature.vermont.gov/statutes/section/33/011/01103",
       "https://law.justia.com/codes/vermont/2016/title-33/chapter-11/section-1103/",
       "https://law.justia.com/codes/vermont/title-33/chapter-11/section-1103/"],
      "us-vt", "statute", "us-vt/statute/33-1103", "33 V.S.A. § 1103. Eligibility and benefit levels",
      "https://legislature.vermont.gov/statutes/section/33/011/01103", H, SOURCE_AS_OF, "TANF",
      "statute_section", authority="Vermont General Assembly (Vermont Statutes Online)"),
    d(["https://legislature.vermont.gov/statutes/section/33/035/03512"],
      "us-vt", "statute", "us-vt/statute/33-3512",
      "33 V.S.A. § 3512. Child Care Financial Assistance Program; eligibility",
      "https://legislature.vermont.gov/statutes/section/33/035/03512", H, SOURCE_AS_OF, "CCDF",
      "statute_section", authority="Vermont General Assembly (Vermont Statutes Online)"),
    d(["https://legislature.vermont.gov/Documents/2022/Docs/ACTS/ACT133/ACT133%20As%20Enacted.pdf"],
      "us-vt", "statute", "us-vt/statute/session-laws/2022/act-133",
      "Act No. 133 of 2022 (H.464): miscellaneous changes to the Reach Up Program (as enacted)",
      "https://legislature.vermont.gov/Documents/2022/Docs/ACTS/ACT133/ACT133%20As%20Enacted.pdf", P,
      "2022-05-27", "TANF", "session_law", authority="Vermont General Assembly"),
    d(["https://legislature.vermont.gov/Documents/2024/Docs/ACTS/ACT076/ACT076%20As%20Enacted.pdf"],
      "us-vt", "statute", "us-vt/statute/session-laws/2023/act-76",
      "Act No. 76 of 2023 (H.217): child care, early education, workers' compensation, and unemployment insurance (as enacted)",
      "https://legislature.vermont.gov/Documents/2024/Docs/ACTS/ACT076/ACT076%20As%20Enacted.pdf", P,
      "2023-06-28", "CCDF", "session_law", authority="Vermont General Assembly"),
    d(["https://dcf.vermont.gov/cdd-blog/act-76-and-ccfap-updates-june-2024"],
      "us-vt", "guidance", "us-vt/guidance/dcf/cdd-blog/act-76-and-ccfap-updates-june-2024",
      "DCF CDD Blog: Act 76 and CCFAP Updates: June 2024",
      "https://dcf.vermont.gov/cdd-blog/act-76-and-ccfap-updates-june-2024", H, "2024-06-19", "CCDF",
      "agency_blog_post"),
    d(["https://dcf.vermont.gov/dcf-news/more-vermont-families-qualify-child-care-financial-assistance"],
      "us-vt", "guidance", "us-vt/guidance/dcf/news/more-vermont-families-qualify-child-care-financial-assistance",
      "DCF News: More Vermont Families Qualify for Child Care Financial Assistance",
      "https://dcf.vermont.gov/dcf-news/more-vermont-families-qualify-child-care-financial-assistance", H,
      SOURCE_AS_OF, "CCDF", "press_release"),
    d(["https://legislature.vermont.gov/assets/Legislative-Reports/Act-76-CCFAP-Rates-Jan-2024.pdf"],
      "us-vt", "guidance", "us-vt/guidance/legislative-reports/act-76-ccfap-rates-2024-01",
      "Report to the Vermont Legislature on Adjustment of CCFAP Rates in Accordance with Act 76 of 2023 (January 2024)",
      "https://legislature.vermont.gov/assets/Legislative-Reports/Act-76-CCFAP-Rates-Jan-2024.pdf", P,
      "2024-01-19", "CCDF", "agency_report_to_legislature"),
    d(["https://legislature.vermont.gov/assets/Legislative-Reports/Reach-Up-Annual-Report-2018.01.31.pdf"],
      "us-vt", "guidance", "us-vt/guidance/legislative-reports/reach-up-annual-report-2018-01-31",
      "Report to the Vermont Legislature: Evaluation of Reach Up (33 V.S.A. § 1134), January 31, 2018",
      "https://legislature.vermont.gov/assets/Legislative-Reports/Reach-Up-Annual-Report-2018.01.31.pdf", P,
      "2018-01-31", "TANF", "agency_report_to_legislature"),
    d(["https://ljfo.vermont.gov/assets/Uploads/9bc271c390/Reach-Up-Annual-Report_FINAL_2020.01.15.pdf"],
      "us-vt", "guidance", "us-vt/guidance/legislative-reports/reach-up-annual-report-2020-01-15",
      "Report to the Vermont Legislature: Evaluation of Reach Up (33 V.S.A. § 1134), January 15, 2020",
      "https://ljfo.vermont.gov/assets/Uploads/9bc271c390/Reach-Up-Annual-Report_FINAL_2020.01.15.pdf", P,
      "2020-01-15", "TANF", "agency_report_to_legislature",
      authority="Vermont Department for Children and Families (posted by the Joint Fiscal Office)",
      note="ljfo.vermont.gov omits its GlobalSign RSA OV SSL CA 2018 intermediate; extraction runs with "
      "REQUESTS_CA_BUNDLE = certifi + data/certs/globalsign-rsa-ov-ssl-ca-2018.pem"),
    d(["https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2230A.pdf"],
      "us-vt", "manual", "us-vt/manual/dcf/esd-procedures/p-2230a",
      "DCF ESD Procedures P-2230A Calculating Net Income and Benefits (24-16)",
      "https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2230A.pdf", P,
      "2024-08-14", "TANF", "agency_procedure"),
    d(["https://outside.vermont.gov/dept/DCF/Shared%20Documents/Benefits/CCFAP-Income-Guidelines.pdf"],
      "us-vt", "policy", "us-vt/policy/ccdf/rate-schedules/ccfap-income-guidelines-2024-10-06",
      "Child Care Financial Assistance Income Guidelines (effective October 6, 2024)",
      "https://outside.vermont.gov/dept/DCF/Shared%20Documents/Benefits/CCFAP-Income-Guidelines.pdf", P,
      "2024-10-06", "CCDF", "rate_or_copay_schedule"),
    d(["https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Act76/ACT-76-FAQs.pdf"],
      "us-vt", "guidance", "us-vt/guidance/dcf/cdd/act-76-faqs",
      "Act 76 (H.217) Frequently Asked Questions (Child Development Division)",
      "https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Act76/ACT-76-FAQs.pdf", P, "2024-06-10",
      "CCDF", "faq"),
    d(["https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Act76/CCFAP-Rate-Increase-Per-Act-76.pdf"],
      "us-vt", "policy", "us-vt/policy/ccdf/rate-schedules/ccfap-rates-per-act-76",
      "Child Care Financial Assistance Program (CCFAP) Rates Per Act 76 (7/2/2023, 1/1/2024, 7/1/2024 schedules)",
      "https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Act76/CCFAP-Rate-Increase-Per-Act-76.pdf", P,
      "2023-07-28", "CCDF", "rate_or_copay_schedule"),
    d(["https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Act76/Memo-Act-76-CCFAP-Rule-Revision.pdf"],
      "us-vt", "guidance", "us-vt/guidance/dcf/cdd/memo-act-76-ccfap-rule-revision-2024-06-28",
      "CDD memorandum: CCFAP Regulation changes under Act 76 (issue date 06/28/24)",
      "https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Act76/Memo-Act-76-CCFAP-Rule-Revision.pdf", P,
      "2024-06-28", "CCDF", "agency_memorandum"),
    d(["https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/CCFAP/CCFAP-State-Rates.pdf"],
      "us-vt", "policy", "us-vt/policy/ccdf/rate-schedules/ccfap-state-rates-2024-06-30",
      "Child Care Financial Assistance State Rates (effective June 30, 2024)",
      "https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/CCFAP/CCFAP-State-Rates.pdf", P,
      "2024-06-30", "CCDF", "rate_or_copay_schedule"),
    # ---------------------------------------------------------------- Washington
    *[d([u], "us-wa", "statute", f"us-wa/statute/{sec.split('.')[0]}/{sec.rsplit('.', 1)[0]}/{sec}",
        f"RCW {sec}", u, H, SOURCE_AS_OF, p, "statute_section",
        extraction={"html_content_selector": "#contentWrapper"}, authority="Washington State Legislature")
      for u, sec, p in [
          ("https://app.leg.wa.gov/RCW/default.aspx?cite=43.216.135", "43.216.135", "CCDF"),
          ("https://app.leg.wa.gov/RCW/default.aspx?cite=43.216.802", "43.216.802", "CCDF"),
          ("https://app.leg.wa.gov/RCW/default.aspx?cite=43.216.814", "43.216.814", "CCDF"),
          ("https://app.leg.wa.gov/rcw/default.aspx?cite=74.04.005", "74.04.005", "TANF"),
          ("https://app.leg.wa.gov/rcw/default.aspx?cite=74.08A.230", "74.08A.230", "TANF"),
      ]],
    d(["https://lawfilesext.leg.wa.gov/biennium/2017-18/Pdf/Bills/Session%20Laws/House/1831-S2.SL.pdf"],
      "us-wa", "statute", "us-wa/statute/session-laws/2018/chapter-40",
      "Laws of 2018, chapter 40 (E2SHB 1831): Public assistance - resource limits",
      "https://lawfilesext.leg.wa.gov/biennium/2017-18/Pdf/Bills/Session%20Laws/House/1831-S2.SL.pdf", P,
      "2019-02-01", "TANF", "session_law", authority="Washington State Legislature"),
    d(["https://lawfilesext.leg.wa.gov/biennium/2023-24/Pdf/Bills/Session%20Laws/House/1447-S2.SL.pdf"],
      "us-wa", "statute", "us-wa/statute/session-laws/2023/chapter-418",
      "Laws of 2023, chapter 418 (2SHB 1447): Assistance programs - eligibility",
      "https://lawfilesext.leg.wa.gov/biennium/2023-24/Pdf/Bills/Session%20Laws/House/1447-S2.SL.pdf", P,
      "2023-07-23", "TANF", "session_law", authority="Washington State Legislature"),
    *[d([f"https://lawfilesext.leg.wa.gov/law/wsr/{y}/{m}/{w}.htm"], "us-wa", "rulemaking",
        f"us-wa/rulemaking/wsr/{w}", f"WSR {w} Permanent Rules, DSHS Economic Services Administration ({t})",
        f"https://lawfilesext.leg.wa.gov/law/wsr/{y}/{m}/{w}.htm", H, e, "TANF", "register_filing",
        authority="Washington State Code Reviser (Washington State Register)")
      for y, m, w, t, e in [
          ("2016", "01", "16-01-093", "filed December 15, 2015, effective January 15, 2016", "2016-01-15"),
          ("2018", "09", "18-09-088", "filed April 17, 2018, effective July 1, 2018", "2018-07-01"),
          ("2021", "21", "21-21-054", "filed October 15, 2021, effective November 15, 2021", "2021-11-15"),
          ("2023", "23", "23-23-054", "filed November 8, 2023, effective January 1, 2024", "2024-01-01"),
          ("2024", "11", "24-11-019", "filed May 7, 2024, effective August 1, 2024", "2024-08-01"),
      ]],
    d(["https://dcyf.wa.gov/news/subsidy-rate-increase-child-care-centers"],
      "us-wa", "guidance", "us-wa/guidance/dcyf/news/subsidy-rate-increase-child-care-centers",
      "DCYF news: Subsidy Rate Increase for Child Care Centers",
      "https://dcyf.wa.gov/news/subsidy-rate-increase-child-care-centers", H, SOURCE_AS_OF, "CCDF",
      "press_release"),
    d(["https://content.govdelivery.com/accounts/WADEL/bulletins/3e5526b"],
      "us-wa", "guidance", "us-wa/guidance/dcyf/bulletins/ffn-providers-changes-to-child-care-subsidy-program",
      "DCYF bulletin: FFN Child Care Providers - Changes to the Child Care Subsidy Program",
      "https://content.govdelivery.com/accounts/WADEL/bulletins/3e5526b", H, SOURCE_AS_OF, "CCDF",
      "agency_email_bulletin",
      authority="Washington State Department of Children, Youth, and Families (GovDelivery account WADEL)"),
    *[d([u], "us-wa", "policy", f"us-wa/policy/ccdf/rate-schedules/{slug}", t, u, P, e, "CCDF",
        "rate_or_copay_schedule")
      for u, slug, t, e in [
          ("https://www.dcyf.wa.gov/sites/default/files/pdf/LFH-Base-Rates-July-2025.pdf",
           "licensed-family-home-base-rates-2025-07-01", "DCYF Licensed Family Home Base Rate (effective July 1, 2025)", "2025-07-01"),
          ("https://www.dcyf.wa.gov/sites/default/files/pdf/copay_calculation_table.pdf",
           "income-eligibility-and-copay-calculation-table-2026-10-01",
           "DCYF Family Copayment for Subsidized Child Care: Income Eligibility and Copay Calculation Table (effective October 1, 2026)",
           "2026-10-01"),
          ("https://www.dcyf.wa.gov/sites/default/files/pdf/subsidy-LC-2026.pdf",
           "licensed-center-base-rates-2026-07-01", "DCYF Licensed Center Base Rate (effective 7/1/2026)", "2026-07-01"),
          ("https://www.dcyf.wa.gov/sites/default/files/pubs/EPS_0004.pdf",
           "child-care-subsidy-rates-regional-map-eps-0004", "DCYF Child Care Subsidy Rates Regional Map (EPS_0004)", "2026-05-21"),
      ]],
    # ---------------------------------------------------------------- Wisconsin
    d(["https://docs.legis.wisconsin.gov/code/admin_code/dcf/101_199/101/09",
       "https://docs.legis.wisconsin.gov/code/admin_code/dcf/101_199/101/18/2"],
      "us-wi", "regulation", "us-wi/regulation/dcf/101",
      "Wisconsin Administrative Code Chapter DCF 101: Wisconsin Works",
      "https://docs.legis.wisconsin.gov/document/administrativecode/ch.%20DCF%20101.pdf", P, SOURCE_AS_OF,
      "TANF", "administrative_code_chapter", authority="Wisconsin Legislative Reference Bureau",
      note="the chapter PDF the DCF 101.09 page links; the bundle's section pages load only a window of the "
      "chapter"),
    d(["https://docs.legis.wisconsin.gov/code/register/2021/790b/insert/dcf101.pdf"],
      "us-wi", "regulation", "us-wi/regulation/dcf/101--register-2021-10-no-790",
      "Chapter DCF 101 Wisconsin Works, as inserted into the Administrative Code 11-1-2021 (Register October 2021 No. 790)",
      "https://docs.legis.wisconsin.gov/code/register/2021/790b/insert/dcf101.pdf", P, "2021-11-01", "TANF",
      "administrative_code_register_insert", authority="Wisconsin Legislative Reference Bureau"),
    d(["https://dcf.wisconsin.gov/files/cs/guidance-documents/pdf/dcf-201-child-care-subsidy-payments-provider-fees.pdf"],
      "us-wi", "rulemaking", "us-wi/rulemaking/dcf/dcf-201-child-care-subsidy-copayments-and-provider-fees",
      "DCF 201 Child Care Subsidy Copayments and Provider Fees (rule document, statement of scope SS 002-23)",
      "https://dcf.wisconsin.gov/files/cs/guidance-documents/pdf/dcf-201-child-care-subsidy-payments-provider-fees.pdf",
      P, "2023-03-16", "CCDF", "rule_order"),
    d(["https://dcf.wisconsin.gov/wisconsin-shares/wisconsin-shares-handbook-july-2026"],
      "us-wi", "manual", "us-wi/manual/dcf/wisconsin-shares-handbook-2026-07",
      "Wisconsin Shares Handbook (July 2026)",
      "https://dcf.wisconsin.gov/wisconsin-shares/wisconsin-shares-handbook-july-2026", P, "2026-07-01", "CCDF",
      "agency_manual"),
    d(["https://docs.legis.wisconsin.gov/misc/lfb/budget/2025_27_biennial_budget/302_budget_papers/211_children_and_families_tanf_and_economic_support_wisconsin_shares_child_care_subsidy_program.pdf"],
      "us-wi", "guidance", "us-wi/guidance/lfb/2025-27-budget-paper-211",
      "Legislative Fiscal Bureau 2025-27 budget paper #211: Children and Families - TANF and Economic Support "
      "(Wisconsin Shares child care subsidy program)",
      "https://docs.legis.wisconsin.gov/misc/lfb/budget/2025_27_biennial_budget/302_budget_papers/211_children_and_families_tanf_and_economic_support_wisconsin_shares_child_care_subsidy_program.pdf",
      P, "2025-05-01", "CCDF", "legislative_analysis", authority="Wisconsin Legislative Fiscal Bureau"),
    # ---------------------------------------------------------------- West Virginia
    d(["https://bfa.wv.gov/media/6766/download?inline"],
      "us-wv", "manual", "us-wv/manual/bfa/child-care-subsidy-policy-manual-2024-10-01",
      "WV Child Care Subsidy Policies and Procedures Manual (October 1, 2024)",
      "https://bfa.wv.gov/media/6766/download?inline", P, "2024-10-01", "CCDF", "agency_manual"),
    d(["https://bfa.wv.gov/media/6826/download?inline"],
      "us-wv", "policy", "us-wv/policy/ccdf/rate-schedules/sliding-fee-scale-fy2024-appendix-a",
      "Child Care Policy Appendix A: Sliding Fee Scale for Child Day Care Services (FY 2024)",
      "https://bfa.wv.gov/media/6826/download?inline", P, "2024-10-01", "CCDF", "rate_or_copay_schedule"),
    d(["https://bfa.wv.gov/media/6831/download?inline"],
      "us-wv", "policy", "us-wv/policy/ccdf/rate-schedules/child-care-rates-2024-10-01",
      "Child Care Policy: provider rates (effective October 1, 2024)",
      "https://bfa.wv.gov/media/6831/download?inline", P, "2024-10-01", "CCDF", "rate_or_copay_schedule"),
    # ---------------------------------------------------------------- Wyoming
    d(["https://dfs.wyo.gov/about/policy-manuals/child-care-subsidy-policy-manual/"],
      "us-wy", "guidance", "us-wy/guidance/dfs/child-care-subsidy-policy-manual-page",
      "Wyoming DFS: Child Care Subsidy Policy Manual (policy manual page)",
      "https://dfs.wyo.gov/about/policy-manuals/child-care-subsidy-policy-manual/", H, SOURCE_AS_OF, "CCDF",
      "agency_web_page"),
    d(["PLACEHOLDER_WY_RULE"],
      "us-wy", "regulation", "us-wy/regulation/049-0008/chapter-1",
      "Wyoming Administrative Rules, Family Services: Child Care - Purchase of Service, Chapter 1 (049.0008.1.05072025, effective 05/07/2025)",
      "PLACEHOLDER_WY_RULE", P, "2025-05-07", "CCDF", "administrative_rule_chapter",
      authority="Wyoming Secretary of State, Administrative Rules"),
    d(["https://wyoleg.gov/statutes/compress/title42.pdf"],
      "us-wy", "statute", "us-wy/statute/title-42-pdf", "Wyoming Statutes Title 42 - Welfare",
      "https://wyoleg.gov/statutes/compress/title42.pdf", P, "2026-05-08", "TANF", "statute_title",
      authority="Wyoming Legislature"),
    *[d([u], "us-wy", "policy", f"us-wy/policy/ccdf/rate-schedules/{slug}", t, u, P, e, "CCDF",
        "rate_or_copay_schedule",
        note="linked from the DFS Child Care page (dfs.wyo.gov/services/family-services/child-care/); the Lead "
        "Agency hosts its child care documents on Google Drive")
      for u, slug, t, e in [
          ("https://drive.google.com/file/d/1-zjev4TxHdyq7vC8tlh9SCNSNZzZz4Kq/view", "child-care-sliding-fee-scale-tblicc-2026-04-01",
           "Child Care Sliding Fee Scale TBLICC 04-01-26 (with 85%)", "2026-04-01"),
          ("https://drive.google.com/file/d/1T7NWbz6hOlRyAcqwROXExos5JB57NstB/view", "child-care-sliding-fee-scale-tblicc-2025-04-01",
           "Child Care Sliding Fee Scale TBLICC 04-01-25 (with 85%)", "2025-04-01"),
          ("https://drive.google.com/file/d/1rG1a7x4V5KKLiipNUwMVmemHBLWZS5MZ/view", "child-care-sliding-fee-scale-tblicc-2024-04-01",
           "Child Care Sliding Fee Scale TBLICC 04-01-24", "2024-04-01"),
      ]],
]


def full_url(prefix: str, rows_csv: Path) -> str:
    """Resolve a bundle address that the table abbreviates (long URLs are kept whole in the CSV)."""
    import csv

    with rows_csv.open() as handle:
        hits = [row["bundle_url"] for row in csv.DictReader(handle) if row["bundle_url"].startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(f"prefix {prefix!r} matched {len(hits)} bundle rows")
    return hits[0]


def bundle_ids(rows_csv: Path) -> set[str]:
    import csv

    with rows_csv.open() as handle:
        return {row["id"] for row in csv.DictReader(handle)}


def manifest_entry(doc: dict[str, Any], main_manifest_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    jur = doc["jurisdiction"]
    source_id = jur + "-w6-" + doc["citation_path"].split("/", 2)[2].replace("/", "-").replace(".", "-").lower()
    entry: dict[str, Any] = {
        "source_id": source_id[:180],
        "jurisdiction": jur,
        "document_class": doc["document_class"],
        "title": doc["title"],
        "source_url": doc["source_url"],
    }
    if doc.get("download_url"):
        entry["download_url"] = doc["download_url"]
    entry.update(
        {
            "source_format": doc["source_format"],
            "source_as_of": SOURCE_AS_OF,
            "expression_date": doc["expression_date"],
            "citation_path": doc["citation_path"],
        }
    )
    extraction = doc.get("extraction")
    if extraction == "FROM_MAIN_MANIFEST":
        main = main_manifest_entries[doc["citation_path"]]
        extraction = copy.deepcopy(main.get("extraction"))
    if extraction:
        entry["extraction"] = extraction
    if doc.get("request"):
        entry["request"] = doc["request"]
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": doc.get("authority") or AUTHORITY[jur],
        "document_subtype": doc["subtype"],
        "program": doc["program"],
        "federal_program": doc["program"],
        "source_discovery_group": f"{jur}/{doc['document_class']}/w6-tanf-ccdf",
        "discovered_via": DISCOVERED_VIA,
        "program_bundle_ids": list(doc["rows"]),
    }
    if doc.get("note"):
        metadata["source_note"] = doc["note"]
    entry["metadata"] = metadata
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default="", help="comma-separated jurisdictions, e.g. us-nj,us-vt")
    parser.add_argument(
        "--rows-csv",
        type=Path,
        default=Path(
            "/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/"
            "program-bundle-gaps-2026-10-06/wave6/tanf-ccdf-nh-wy.csv"
        ),
    )
    args = parser.parse_args()
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    placeholders = {
        "PLACEHOLDER_OH_PL21": "https://dam.assets.ohio.gov/image/upload/childrenandyouth.ohio.gov/For%20Partners/Rules%20and%20Resources/2025",
        "PLACEHOLDER_OH_ACTL297": "https://dam.assets.ohio.gov/image/upload/v1764089750/jfs.ohio.gov/EBS/Programs%20Rules%20and%20Resources/Cash/",
        "PLACEHOLDER_PA_MCCA": "https://www.pa.gov/content/dam/copapwp-pagov/en/dhs/documents/services/children/documents/child-care-early-learning/MCCA-Rates-by-Region-eff",
        "PLACEHOLDER_UT_T1_2008": "https://jobs.utah.gov/infosource/eligibilitymanual/Obsolete_Policy/Obsolete_Tables%2c_Appendices%2c_and_Charts/Table_1/ObsoleteTable1_(2008_",
        "PLACEHOLDER_UT_T1_2012": "https://jobs.utah.gov/infosource/eligibilitymanual/Obsolete_Policy/Obsolete_Tables%2c_Appendices%2c_and_Charts/Table_1/Obsolete_Table_1_(05_",
        "PLACEHOLDER_VA_TOWNHALL": "https://townhall.virginia.gov/L/GetFile.cfm?File=C%3A%5CTownHall%5Cdocroot%5CGuidanceDocs_Proposed%5C201%5CGDoc_DOE_8298_20250805.pdf",
        "PLACEHOLDER_WY_RULE": "https://rules.wyo.gov/DownloadFile.aspx?source_id=24638",
    }
    resolved = {key: full_url(prefix, args.rows_csv) for key, prefix in placeholders.items()}
    csv_ids = bundle_ids(args.rows_csv)

    def resolve(value: str) -> str:
        if value in resolved:
            return resolved[value]
        if value.startswith("PREFIX:"):
            return full_url(value[len("PREFIX:"):], args.rows_csv)
        return value
    main_entries: dict[str, dict[str, Any]] = {}
    main_doc = yaml.safe_load((ROOT / "manifests" / "us-nj-wfnj-rules.yaml").read_text())
    for entry in main_doc["documents"]:
        main_entries[entry["citation_path"]] = entry

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    seen_paths: set[str] = set()
    for raw in DOCS:
        doc = dict(raw)
        doc["rows"] = [resolve(row) for row in doc["rows"]]
        doc["source_url"] = resolve(doc["source_url"])
        for row in doc["rows"]:
            if row not in csv_ids:
                raise SystemExit(f"row id not in the work order: {row}")
        if doc["citation_path"] in seen_paths:
            raise SystemExit(f"duplicate citation path {doc['citation_path']}")
        seen_paths.add(doc["citation_path"])
        if not doc["citation_path"].startswith(f"{doc['jurisdiction']}/{doc['document_class']}/"):
            raise SystemExit(f"path/class mismatch {doc['citation_path']}")
        if only and doc["jurisdiction"] not in only:
            continue
        groups[(doc["jurisdiction"], doc["document_class"])].append(doc)

    for (jur, cls), docs in sorted(groups.items()):
        st = jur.split("-", 1)[1]
        version = f"{SOURCE_AS_OF}-w6-tanf-ccdf-{cls}-{st}"
        manifest = {
            "version": version,
            "documents": [manifest_entry(doc, main_entries) for doc in docs],
        }
        path = ROOT / "manifests" / f"{jur}-tanf-ccdf-w6-{cls}.yaml"
        header = (
            f"# Wave 6 ({GROUP}): {jur} {cls} documents the TANF/CCDF program bundles name.\n"
            f"# Generated by scripts/build_w6_tanf_ccdf_nh_wy_manifests.py; edit the generator, not this file.\n"
        )
        path.write_text(header + yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=110))
        print(f"{path.relative_to(ROOT)}\t{version}\t{len(docs)} documents")


if __name__ == "__main__":
    main()
