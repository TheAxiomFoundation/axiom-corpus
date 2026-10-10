#!/usr/bin/env python3
# ruff: noqa: C408, E501
"""Write the wave-6 `health` official-document manifests (state Medicaid, CHIP, Medicare docs).

Work order: docs/coverage/program-bundle-gaps-2026-10-06/wave6/health.csv (128 rows), branch
analysis/program-bundle-gaps-2026-10-06. Every entry below was fetched once from the official
publisher on 2026-10-06 with the corpus client (or, where a run note documents it, browser
impersonation) and read before it was listed. `source_url` is the bundle's address exactly
(the bundle generator joins documents to manifests by URL); a redirect target, when there is
one, is recorded in `metadata.final_url`.

One manifest per (jurisdiction, document class): manifests/<jur>-health-w6-<class>.yaml with
version 2026-10-06-w6-health-<class>-<state>. The script is static (no network) and idempotent.

Usage:
    uv run python scripts/build_w6_health_manifests.py            # write manifests
    uv run python scripts/build_w6_health_manifests.py --list     # print row -> scope/path
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-10-06"
WORK_ORDER = (
    "docs/coverage/program-bundle-gaps-2026-10-06/wave6/health.csv "
    "(branch analysis/program-bundle-gaps-2026-10-06)"
)
DISCOVERED_VIA = "program-bundle-gaps-2026-10-06 wave 6 health; bundle address fetched from the official publisher"

IMPERSONATE = {"browser_impersonation": True, "browser_impersonation_direct": True}
MAIN = {"html_content_selector": "main"}

AUTH = {
    "adph": "Alabama Department of Public Health (Children's Cabinet report)",
    "al-lsa": "Alabama Legislative Services Agency, Alabama Administrative Code (Alabama Medicaid Agency rules)",
    "dhcs": "California Department of Health Care Services (DHCS)",
    "scc": "County of Santa Clara Social Services Agency, Department of Employment and Benefit Services",
    "c4hco": "Connect for Health Colorado (Colorado's state-based health insurance marketplace, C.R.S. 10-22-104)",
    "hcpf": "Colorado Department of Health Care Policy and Financing (HCPF)",
    "ct-dss": "Connecticut Department of Social Services (DSS)",
    "ct-ads": "Connecticut Department of Aging and Disability Services (ADS), CHOICES program",
    "dc-hbx": "District of Columbia Health Benefit Exchange Authority (DC HBX)",
    "fhkc": "Florida Healthy Kids Corporation (Florida KidCare, s. 624.91 F.S.)",
    "ga-dch": "Georgia Department of Community Health (DCH)",
    "ga-dfcs": "Georgia Division of Family and Children Services (DFCS), PAMMS",
    "macpac": "Medicaid and CHIP Payment and Access Commission (MACPAC), a federal legislative-branch agency",
    "ia-hhs": "Iowa Department of Health and Human Services",
    "ia-lsa": "Iowa Legislative Services Agency, Fiscal Services Division",
    "ia-legis": "Iowa Legislature, Iowa Administrative Code (Iowa HHS rules)",
    "il-hfs": "Illinois Department of Healthcare and Family Services (HFS)",
    "in-fssa": "Indiana Family and Social Services Administration (FSSA)",
    "klrd": "Kansas Legislative Research Department (KLRD)",
    "la-osr": "Louisiana Department of Health rules, published by the Louisiana Division of Administration, Office of the State Register",
    "me-leg": "Maine Legislature, Office of the Revisor of Statutes",
    "mi-mdhhs": "Michigan Department of Health and Human Services (MDHHS)",
    "mo-dss": "Missouri Department of Social Services (DSS)",
    "mo-revisor": "Missouri Revisor of Statutes (Committee on Legislative Research)",
    "ms-dom": "Mississippi Division of Medicaid (DOM)",
    "nd-leg": "North Dakota Legislative Assembly (testimony of the Department of Health and Human Services)",
    "nv-dhcfp": "Nevada Division of Health Care Financing and Policy (Nevada Medicaid)",
    "or-odhs": "Oregon Department of Human Services (ODHS), chapter 461 rules",
    "or-leg": "Oregon Legislative Assembly (OLIS)",
    "or-oha": "Oregon Health Authority (OHA)",
    "or-odhs-oha": "Oregon Department of Human Services and Oregon Health Authority",
    "scdhhs": "South Carolina Department of Health and Human Services (SCDHHS)",
    "tenncare": "TennCare, Tennessee Division of TennCare",
    "tx-hhsc": "Texas Health and Human Services Commission (HHSC)",
    "dmas": "Virginia Department of Medical Assistance Services (DMAS)",
    "wa-leg": "Washington State Legislature",
    "wa-hca": "Washington State Health Care Authority (HCA)",
    "wi-leg": "Wisconsin Legislature, Legislative Reference Bureau",
    "wi-dhs": "Wisconsin Department of Health Services",
    "wdh": "Wyoming Department of Health",
}

# row = 0-based row index of the work-order CSV (data row number).
DOCS: list[dict] = [
    # --- Alabama ---
    dict(row=0, jur="us-al", cls="regulation", auth="al-lsa", program="MEDICAID",
         url="https://admincode.legislature.state.al.us/api/chapter/560-X-25",
         path="us-al/regulation/alabama-administrative-code/560/x/25",
         title="Alabama Administrative Code Chapter 560-X-25: Medicaid Eligibility (Alabama Medicaid Agency)",
         fmt="pdf", subtype="administrative_code_chapter_pdf"),
    dict(row=2, jur="us-al", cls="guidance", auth="adph", program="CHIP",
         url="https://www.alabamapublichealth.gov/perinatal/assets/al-im-reduction-plan.pdf",
         path="us-al/guidance/adph/infant-mortality-reduction-plan-2018",
         title="State of Alabama Infant Mortality Reduction Plan: Children's Cabinet Recommendations and Report (June 2018)",
         fmt="pdf", expr="2018-06-01", subtype="state_plan_report_pdf"),
    # --- California ---
    dict(row=5, jur="us-ca", cls="guidance", auth="dhcs", program="MEDICAID",
         url="https://www.dhcs.ca.gov/hy/wp-content/uploads/2025/10/MAGIHouseholdSizeFlowChartADA.pdf",
         path="us-ca/guidance/dhcs/magi-household-size-flowchart",
         title="DHCS Guide for Calculating MAGI Medi-Cal Individual Household Size (household size flow chart, 42 CFR 435.603(f))",
         fmt="pdf", subtype="eligibility_job_aid_pdf"),
    dict(row=4, jur="us-ca", cls="form", auth="dhcs", program="MEDICAID",
         url="https://www.dhcs.ca.gov/wp-content/uploads/2025/10/MC250A_Eng.pdf",
         path="us-ca/form/official-forms/dhcs.ca.gov/formsandpubs/forms/forms/mced/mc-forms/mc250a-eng",
         title="MC 250A: Application for Medi-Cal for Former Foster Care Youth (English)",
         fmt="pdf", subtype="eligibility_application_form_pdf",
         bundle_url="https://dhcs.ca.gov/formsandpubs/forms/Forms/MCED/MC_Forms/MC250A_Eng.pdf",
         note=("EXTRACT-MANIFEST row: manifests/us-ca-official-forms.yaml names the old address, which now redirects to "
               "/file/mc250a_eng-pdf/ behind an Incapsula challenge; the same form is served from DHCS's wp-content "
               "uploads (address found by web search, fetched from dhcs.ca.gov); the manifest's citation_path us-ca/form/official_forms/.../mc_forms/mc250a_eng fails the citation-path grammar (underscores), so its segments are folded to hyphens (citation_segment rule)")),
    dict(row=6, jur="us-ca", cls="guidance", auth="dhcs", program="CHIP",
         url="https://www.dhcs.ca.gov/wp-content/uploads/2025/10/HACCP-FPL-Chart.pdf",
         path="us-ca/guidance/dhcs/haccp/income-eligibility-comparison-chart-2025",
         title="DHCS Income Eligibility Comparison Chart: Medi-Cal, HACCP and CCS eligibility by household size (2025 FPL)",
         fmt="pdf", subtype="income_standards_chart_pdf",
         bundle_url="https://www.dhcs.ca.gov/services/HACCP/Documents/Program-Income-Eligibility-Comparison2025.pdf",
         note=("The bundle's /services/HACCP/Documents/ address answers an Incapsula challenge; this is DHCS's wp-content "
               "copy of the 2025-FPL HACCP comparison chart (138% FPL single = $20,783), address found by web search")),
    dict(row=11, jur="us-ca", cls="guidance", auth="dhcs", program="CHIP",
         url="https://www.dhcs.ca.gov/wp-content/uploads/2025/10/25-01.pdf",
         path="us-ca/guidance/dhcs/acwdl/25-01",
         title="DHCS All County Welfare Directors Letter 25-01: 2025 Federal Poverty Levels (January 21, 2025)",
         fmt="pdf", expr="2025-01-21", subtype="all_county_welfare_directors_letter_pdf",
         bundle_url="https://www.dhcs.ca.gov/services/medi-cal/eligibility/letters/Documents/25-01.pdf",
         note=("The bundle's /letters/Documents/ address redirects to /file/25-01-pdf/ behind an Incapsula challenge; "
               "the same letter is served from DHCS's wp-content uploads (address found by web search)")),
    dict(row=15, jur="us-ca", cls="guidance", auth="dhcs", program="MEDICAID",
         url="https://www.dhcs.ca.gov/wp-content/uploads/2025/10/c20-10.pdf",
         path="us-ca/guidance/dhcs/acwdl/20-10",
         title="DHCS All County Welfare Directors Letter 20-10: Guidance on MAGI Medi-Cal Household Compositions (April 30, 2020)",
         fmt="pdf", expr="2020-04-30", subtype="all_county_welfare_directors_letter_pdf"),
    dict(row=17, jur="us-ca", cls="manual", auth="scc", program="CHIP",
         url="https://stgenssa.sccgov.org/debs/program_handbooks/medi-cal/assets/35StCtyAdminHealthIns/CCHIP.htm",
         path="us-ca/manual/scc-ssa/medi-cal/cchip",
         title="Santa Clara County Medi-Cal Program Handbook: County Children's Health Initiative Program (CCHIP)",
         fmt="html", expr="2022-07-01", extraction=dict(MAIN), subtype="county_program_handbook_topic",
         note="County agency handbook (the county administers CCHIP locally); effective July 1, 2022 as printed"),
    # --- Colorado ---
    dict(row=26, jur="us-co", cls="guidance", auth="c4hco", program="MEDICAID",
         url="https://connectforhealthco.com/get-started/omnisalud/",
         final="https://connectforhealthco.com/new-customers/omnisalud/",
         path="us-co/guidance/connect-for-health-colorado/omnisalud",
         title="Connect for Health Colorado: OmniSalud", fmt="html",
         extraction={"html_content_selector": "article"}, subtype="agency_program_page"),
    dict(row=27, jur="us-co", cls="guidance", auth="hcpf", program="MEDICAID",
         url="https://www.healthfirstcolorado.com/health-coverage-for-immigrants/",
         final="https://www.healthfirstcolorado.gov/health-coverage-for-immigrants/",
         path="us-co/guidance/hcpf/health-first-colorado/health-coverage-for-immigrants",
         title="Health First Colorado: Health Coverage for Immigrants", fmt="html",
         extraction={"html_content_selector": "article"}, subtype="agency_program_page"),
    dict(row=30, jur="us-co", cls="guidance", auth="hcpf", program="CHIP",
         url="https://hcpf.colorado.gov/child-health-plan-plus",
         path="us-co/guidance/hcpf/child-health-plan-plus",
         title="HCPF: Child Health Plan Plus (CHP+)", fmt="html", extraction=dict(MAIN),
         request=IMPERSONATE, subtype="agency_program_page",
         access="hcpf.colorado.gov answers CloudFront 403 to the corpus client; browser impersonation as documented in docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md"),
    dict(row=31, jur="us-co", cls="guidance", auth="hcpf", program="CHIP",
         url="https://hcpf.colorado.gov/sites/hcpf/files/April%202022%20CHP%2B%20Income%20Chart.pdf",
         path="us-co/guidance/hcpf/chp-plus-income-chart/2022-04",
         title="HCPF Child Health Plan Plus Monthly Maximum Income Guidelines (April 2022)",
         fmt="pdf", expr="2022-04-01", request=IMPERSONATE, subtype="income_standards_chart_pdf",
         access="hcpf.colorado.gov answers CloudFront 403 to the corpus client; browser impersonation as documented in docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md"),
    dict(row=32, jur="us-co", cls="guidance", auth="hcpf", program="CHIP",
         url="https://hcpf.colorado.gov/sites/hcpf/files/April%202023%20CHP%2B%20Income%20Chart%20_.pdf",
         path="us-co/guidance/hcpf/chp-plus-income-chart/2023-04",
         title="HCPF Child Health Plan Plus Monthly Maximum Income Guidelines (April 2023)",
         fmt="pdf", expr="2023-04-01", request=IMPERSONATE, subtype="income_standards_chart_pdf",
         access="hcpf.colorado.gov answers CloudFront 403 to the corpus client; browser impersonation as documented in docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md"),
    # --- Connecticut ---
    dict(row=33, jur="us-ct", cls="guidance", auth="ct-dss", program="MEDICAID",
         url="https://portal.ct.gov/-/media/Departments-and-Agencies/DSS/HIT/MedCoverageGroupsOLD.pdf",
         path="us-ct/guidance/dss/medical-coverage-groups-upm-2540",
         title="DSS Medical Coverage Groups (UPM 2540) chart", fmt="pdf", subtype="coverage_groups_chart_pdf"),
    dict(row=34, jur="us-ct", cls="guidance", auth="ct-ads", program="MEDICARE_SAVINGS_PROGRAMS",
         url="https://portal.ct.gov/-/media/aginganddisability/agingservices/choices/benefitsquickguide.pdf",
         path="us-ct/guidance/ads/choices-benefits-quick-guide/2024-03-01",
         title="CHOICES Benefits Quick Guide (MSP effective 3/1/24-2/29/25)", fmt="pdf", expr="2024-03-01",
         subtype="benefits_quick_guide_pdf"),
    dict(row=35, jur="us-ct", cls="guidance", auth="ct-ads", program="MEDICARE_SAVINGS_PROGRAMS",
         url="https://portal.ct.gov/-/media/aginganddisability/agingservices/choices/quick-guide---accessible-version-21523.pdf",
         path="us-ct/guidance/ads/choices-benefits-quick-guide/2023-03-01",
         title="CHOICES Benefits Quick Guide, accessible version (MSP effective 3/1/23-2/29/24)", fmt="pdf",
         expr="2023-03-01", subtype="benefits_quick_guide_pdf"),
    dict(row=36, jur="us-ct", cls="guidance", auth="ct-dss", program="CHIP",
         url="https://portal.ct.gov/-/media/hh/pdf/husky-health-monthly-income-chart-march-1-2025.pdf",
         path="us-ct/guidance/dss/husky-health-monthly-income-chart/2025-03-01",
         title="Connecticut HUSKY Health Program Monthly Income Guidelines, effective March 1, 2025", fmt="pdf",
         expr="2025-03-01", subtype="income_standards_chart_pdf",
         note="The March 1, 2026 edition is held in us-ct/manual/2026-09-10-chip-state-eligibility-manual"),
    dict(row=37, jur="us-ct", cls="guidance", auth="ct-ads", program="MEDICARE_SAVINGS_PROGRAMS",
         url="https://portal.ct.gov/ads/-/media/ads-beta/choices/choices-benefits-quick-guide.pdf?rev=3b8c59ca12224218bc4c4438649e7ac7",
         path="us-ct/guidance/ads/choices-benefits-quick-guide/2026-03-01",
         title="CHOICES Benefits Quick Guide (MSP effective 3/1/26-2/28/27)", fmt="pdf", expr="2026-03-01",
         subtype="benefits_quick_guide_pdf"),
    # --- District of Columbia ---
    dict(row=38, jur="us-dc", cls="guidance", auth="dc-hbx", program="MEDICAID",
         url="https://hbx.dc.gov/sites/default/files/dc/sites/hbx/event_content/attachments/PROPOSED%20EXTENSION%20OF%20LOSS%20OF%20MEDICAID%20SEP%20Nov%202025_0.pdf",
         path="us-dc/guidance/hbx/proposed-extension-loss-of-medicaid-sep-2025-11",
         title="DC HBX: Proposed Extension of Existing Loss of Medicaid SEP (November 24, 2025)", fmt="pdf",
         expr="2025-11-24", subtype="board_proposal_pdf"),
    # --- Florida ---
    dict(row=43, jur="us-fl", cls="guidance", auth="fhkc", program="CHIP",
         url="https://floridakidcare.org/docs/cost/florida_kidcare_income_guidelines.pdf",
         path="us-fl/guidance/florida-healthy-kids/kidcare-income-guidelines/2025",
         title="Florida KidCare 2025 General Annual Income Guidelines", fmt="pdf", expr="2025-04-01",
         subtype="income_standards_chart_pdf"),
    # --- Georgia ---
    dict(row=44, jur="us-ga", cls="guidance", auth="ga-dch", program="CHIP",
         url="https://dch.georgia.gov/announcement/2024-08-13/peachcare-kidsr-co-payments-and-premiums-resume-oct-1-2024",
         path="us-ga/guidance/dch/peachcare-copayments-premiums-resume-2024-10-01",
         title="DCH announcement: PeachCare for Kids Co-Payments and Premiums Resume Oct. 1, 2024 (2024-08-13)",
         fmt="html", expr="2024-08-13", extraction={"html_content_selector": "#main-content"},
         subtype="agency_announcement_page"),
    dict(row=46, jur="us-ga", cls="guidance", auth="macpac", program="MEDICAID",
         url="https://www.macpac.gov/wp-content/uploads/2024/12/EXHIBIT-36.-Medicaid-Income-Eligibility-Levels-as-a-Percentage-of-the-FPL-for-Non-Aged-Non-Disabled-Non-Pregnant-Adults-July-2024.pdf",
         path="us-ga/guidance/macpac/exhibit-36/2024-07",
         title="MACStats Exhibit 36: Medicaid Income Eligibility Levels as a Percentage of the FPL for Non-Aged, Non-Disabled, Non-Pregnant Adults by State, July 2024",
         fmt="pdf", expr="2024-07-01", subtype="federal_statistical_exhibit_pdf",
         note="Federal (MACPAC) multi-state exhibit; held under us-ga because the Georgia bundle layer names it"),
    dict(row=47, jur="us-ga", cls="guidance", auth="macpac", program="MEDICAID",
         url="https://www.macpac.gov/wp-content/uploads/2026/01/EXHIBIT-36.-Medicaid-Income-Eligibility-Levels-as-a-Percentage-of-the-Federal-Poverty-Level-for-Non-Aged-Non-Disabled-Non-Pregnant-Adults-by-State-2025.pdf",
         path="us-ga/guidance/macpac/exhibit-36/2025-07",
         title="MACStats Exhibit 36: Medicaid Income Eligibility Levels as a Percentage of the FPL for Non-Aged, Non-Disabled, Non-Pregnant Adults by State, July 2025",
         fmt="pdf", expr="2025-07-01", subtype="federal_statistical_exhibit_pdf",
         note="Federal (MACPAC) multi-state exhibit; held under us-ga because the Georgia bundle layer names it"),
    dict(row=48, jur="us-ga", cls="guidance", auth="ga-dch", program="MEDICAID",
         url="https://www.mmis.georgia.gov/portal/Portals/0/StaticContent/Public/ALL/NOTICES/Covid-19-%20Spring%20Medicaid%20Fair%202021%2020210325165058.pdf",
         path="us-ga/guidance/dch/mmis/medicaid-fair-spring-2021-nemt",
         title="DCH Medicaid Fair, Spring 2021: Non-Emergency Medical Transportation (NEMT) COVID-19 Operations (GAMMIS notice)",
         fmt="pdf", expr="2021-03-25", subtype="provider_notice_presentation_pdf"),
    dict(row=45, jur="us-ga", cls="manual", auth="ga-dfcs", program="MEDICAID",
         url="https://pamms.dhs.ga.gov/dfcs/medicaid/appendix-a2/2026-family-limits/",
         path="us-ga/manual/dfcs/medicaid/appendix-a2-2026-family-limits",
         title="Georgia Medicaid Policy Manual Appendix A2: Family Medicaid Financial Limits 2026 (effective 03/01/2026)",
         fmt="html", expr="2026-03-01", extraction={"html_content_selector": "article"},
         subtype="eligibility_manual_appendix"),
    # --- Iowa ---
    dict(row=49, jur="us-ia", cls="guidance", auth="ia-hhs", program="CHIP",
         url="https://hhs.iowa.gov/media/10189/download?inline=",
         path="us-ia/guidance/hhs/hawki-income-guidelines/2026",
         title="Iowa HHS 2026 Hawki Income Guidelines", fmt="pdf", subtype="income_standards_chart_pdf"),
    dict(row=50, jur="us-ia", cls="guidance", auth="ia-lsa", program="MEDICAID",
         url="https://www.legis.iowa.gov/docs/publications/FN/1449063.pdf",
         path="us-ia/guidance/lsa/fiscal-note/sf-2251-postpartum-coverage",
         title="Iowa LSA Fiscal Note: SF 2251 - Postpartum Coverage, Medicaid (LSB5156SV.3), final action",
         fmt="pdf", subtype="legislative_fiscal_note_pdf"),
    dict(row=51, jur="us-ia", cls="regulation", auth="ia-legis", program="MEDICAID",
         url="https://www.legis.iowa.gov/docs/iac/rule/441.75.1.pdf",
         path="us-ia/regulation/iac/441/75/75.1",
         title="441 IAC 75.1(249A) Definitions (Iowa HHS medical assistance eligibility)", fmt="pdf",
         subtype="administrative_code_rule_pdf", bundle_url="https://www.law.cornell.edu/regulations/iowa/Iowa-Admin-Code-r-441-75-1",
         note="Official Iowa Legislature rule PDF in place of the Cornell LII mirror the bundle names"),
    # --- Illinois (HFS pages) ---
    *[
        dict(row=r, jur="us-il", cls="guidance", auth="il-hfs", program=prog, url=u,
             path=f"us-il/guidance/hfs/{slug}", title=f"Illinois HFS: {t}", fmt="html", extraction=dict(MAIN),
             subtype="agency_program_page")
        for r, prog, u, slug, t in [
            (52, "MEDICAID", "https://hfs.illinois.gov/medicalclients/healthbenefitsforimmigrants.html",
             "health-benefits-for-immigrants", "Health Benefits for Immigrants"),
            (53, "MEDICAID", "https://hfs.illinois.gov/medicalclients/healthbenefitsforimmigrants/hbiafaq.html",
             "health-benefits-for-immigrants/hbia-faq", "Health Benefits for Immigrant Adults FAQ"),
            (54, "MEDICAID", "https://hfs.illinois.gov/medicalclients/healthbenefitsforimmigrants/healthbenefitsforimmigrantadults.html",
             "health-benefits-for-immigrants/immigrant-adults", "Health Benefits for Immigrant Adults"),
            (55, "CHIP", "https://hfs.illinois.gov/medicalprograms/allkids/about.html", "all-kids/about", "About All Kids"),
            (56, "CHIP", "https://hfs.illinois.gov/medicalprograms/allkids/income.html", "all-kids/income",
             "All Kids: How Much Does It Cost?"),
            (57, "MEDICAID", "https://hfs.illinois.gov/medicalprograms/hbwd.html", "hbwd",
             "Health Benefits for Workers with Disabilities (HBWD)"),
            (58, "MEDICAID", "https://hfs.illinois.gov/medicalprograms/hbwd/about.html", "hbwd/about", "About HBWD"),
            (59, "MEDICAID", "https://hfs.illinois.gov/medicalprograms/hbwd/eligibility.html", "hbwd/eligibility",
             "HBWD Eligibility"),
            (60, "MEDICAID", "https://hfs.illinois.gov/medicalprograms/hbwd/premiums.html", "hbwd/premiums",
             "HBWD Premium Costs & Co-Pays"),
        ]
    ],
    # --- Indiana ---
    dict(row=71, jur="us-in", cls="guidance", auth="in-fssa", program="MEDICAID",
         url="https://www.in.gov/fssa/ddars/bba/provider-resources/residential-care-assistance-program/",
         path="us-in/guidance/fssa/residential-care-assistance-program",
         title="Indiana FSSA DDRS/BBA: Residential Care Assistance Program", fmt="html",
         extraction={"html_content_selector": "article"}, subtype="agency_program_page"),
    dict(row=72, jur="us-in", cls="guidance", auth="in-fssa", program="MEDICAID",
         url="https://www.in.gov/fssa/hip/about-hip/power-accounts/",
         path="us-in/guidance/fssa/hip/power-accounts",
         title="Healthy Indiana Plan (HIP): POWER accounts", fmt="html",
         extraction={"html_content_selector": "article"}, subtype="agency_program_page"),
    dict(row=73, jur="us-in", cls="guidance", auth="in-fssa", program="CHIP",
         url="https://www.in.gov/medicaid/members/member-programs/hhw-package-c-medworks-premium/",
         path="us-in/guidance/fssa/hhw-package-c-medworks-premium",
         title="Indiana Medicaid for Members: HHW Package C / MEDWorks Premium", fmt="html",
         extraction={"html_content_selector": "article"}, subtype="agency_program_page"),
    # --- Kansas ---
    dict(row=76, jur="us-ks", cls="guidance", auth="klrd", program="CHIP",
         url="https://klrd.gov/2026/03/02/briefing-book-2026-childrens-eligibility-for-chip-mchip-medicaid-and-hcbs-including-information-on-premium-requirements-for-chip/",
         path="us-ks/guidance/klrd/briefing-book-2026/childrens-eligibility-chip-mchip-medicaid-hcbs",
         title="KLRD Briefing Book 2026: Children's Eligibility for CHIP, MCHIP, Medicaid, and HCBS, including information on premium requirements for CHIP",
         fmt="html", expr="2026-03-02", extraction={"html_content_selector": "article"},
         subtype="legislative_research_briefing"),
    # --- Louisiana ---
    dict(row=77, jur="us-la", cls="regulation", auth="la-osr", program="MEDICAID",
         url="https://www.doa.la.gov/media/ogee2gb4/50.docx",
         path="us-la/regulation/lac/50/iii",
         title="Louisiana Administrative Code Title 50 (Public Health - Medical Assistance), Part III: Eligibility",
         fmt="docx", subtype="administrative_code_part",
         bundle_url="https://www.law.cornell.edu/regulations/louisiana/La-Admin-Code-tit-50-SS-III-2305",
         extraction={
             "segmentation": "labeled_sections",
             # The title DOCX opens with a table of contents whose Part lines repeat the body
             # headings verbatim, so the start is the unique historical note that closes Part II.
             "start_after_pattern": r"LR 42:63 \(January 2016\), amended by the Department of Health, Bureau of Health Services Financing, LR 43:529 \(March 2017\), LR 47:476 \(April 2021\), LR 51:1613 \(October 2025\)\.$",
             "stop_text_pattern": r"^Part V\.\s+Hospital Services\s*$",
             "section_heading_pattern": r"^§(?P<label>\d{3,5})\.\s*(?P<heading>\S.*)$",
             "drop_line_patterns": [r"^Title\s+50$", r"^PUBLIC HEALTH.{0,3}MEDICAL ASSISTANCE$",
                                    r"^Subpart \d+\.\s", r"^Chapter \d+\.\s*[A-Z]"],
         },
         note=("Official Office of the State Register title DOCX (Title 50 file last modified 2026-09-25) in place of the "
               "Cornell LII mirror of LAC 50:III.2305 the bundle names; Part III only (45 sections, 2305 = Provisional "
               "Medicaid Program)")),
    # --- Maine ---
    dict(row=81, jur="us-me", cls="statute", auth="me-leg", program="MEDICARE_SAVINGS_PROGRAMS",
         url="https://legislature.maine.gov/statutes/22/title22sec3174-LLL.html",
         path="us-me/statute/22/3174-lll", title="Maine Revised Statutes Title 22, section 3174-LLL: Medicare savings program",
         fmt="html", extraction={"html_content_selector": "div.MRSSection", "segmentation": "single_block"},
         subtype="statute_section_html"),
    # --- Michigan (michigan.gov, browser impersonation documented in the WIC run note) ---
    *[
        dict(row=r, jur="us-mi", cls="guidance", auth="mi-mdhhs", program=prog, url=u, path=p, title=t,
             fmt=f, extraction=ex, request=IMPERSONATE, subtype=st,
             access="michigan.gov answers 403 to non-browser clients; browser impersonation as documented in docs/ingest-runs/2026-09-10-wic-fns-guidance-and-state-manuals.md")
        for r, prog, u, p, t, f, ex, st in [
            (83, "MEDICAID", "https://www.michigan.gov/healthymiplan", "us-mi/guidance/mdhhs/healthy-michigan-plan",
             "MDHHS: Healthy Michigan Plan", "html", dict(MAIN), "agency_program_page"),
            (84, "MEDICAID", "https://www.michigan.gov/healthymiplan/-/media/Project/Websites/healthymiplan/B-23-07-HMP-Final.pdf",
             "us-mi/guidance/mdhhs/healthy-michigan-plan/b-23-07-hmp-final", "MDHHS Healthy Michigan Plan document B-23-07-HMP-Final",
             "pdf", {}, "agency_bulletin_pdf"),
            (85, "MEDICAID", "https://www.michigan.gov/mdhhs/-/media/Project/Websites/mdhhs/Assistance-Programs/Medicaid-BPHASA/2023-Bulletins/Final-Bulletin-MMP-24-20-Eligibility.pdf?rev=dbb27d49587c40f6bb87c2669287edf6&hash=8F47918C2161E23831CC56F0BF4A3AD0",
             "us-mi/guidance/mdhhs/medicaid-bulletin/mmp-24-20", "MDHHS Medical Services Administration Bulletin MMP 24-20 (Eligibility)",
             "pdf", {}, "medicaid_policy_bulletin_pdf"),
            (86, "CHIP", "https://www.michigan.gov/mdhhs/assistance-programs/healthcare/childrenteens/michild/qanda/michild-program-general-information",
             "us-mi/guidance/mdhhs/michild/program-general-information", "MDHHS: MIChild Program General Information",
             "html", dict(MAIN), "agency_program_page"),
        ]
    ],
    # --- Missouri ---
    dict(row=87, jur="us-mo", cls="guidance", auth="mo-dss", program="MEDICAID",
         url="https://mydss.mo.gov/benefit-program-income-limits", final="https://dss.mo.gov/benefit-program-income-limits",
         path="us-mo/guidance/dss/benefit-program-income-limits", title="Missouri DSS: Benefit Program Income Limits",
         fmt="html", extraction={"html_content_selector": "div.region-content"}, subtype="income_standards_page"),
    dict(row=88, jur="us-mo", cls="guidance", auth="mo-dss", program="CHIP",
         url="https://mydss.mo.gov/childrens-health-insurance-program-chip-premium-chart",
         final="https://dss.mo.gov/childrens-health-insurance-program-chip-premium-chart",
         path="us-mo/guidance/dss/chip-premium-chart", title="Missouri DSS: Children's Health Insurance Program (CHIP) Premium Chart",
         fmt="html", extraction={"html_content_selector": "div.region-content"}, subtype="premium_chart_page"),
    dict(row=89, jur="us-mo", cls="statute", auth="mo-revisor", program="CHIP",
         url="https://revisor.mo.gov/main/OneSection.aspx?section=208.640",
         path="us-mo/statute/208.640", title="RSMo 208.640: Co-payments required, when, amount, limitations",
         fmt="html", extraction={"html_content_selector": "div.norm", "segmentation": "single_block"},
         subtype="statute_section_html"),
    # --- Mississippi ---
    dict(row=91, jur="us-ms", cls="guidance", auth="ms-dom", program="MEDICAID",
         url="https://medicaid.ms.gov/medicaid-coverage/who-qualifies-for-coverage/income-limits-for-medicaid-and-chip-programs/",
         path="us-ms/guidance/dom/income-limits-for-medicaid-and-chip-programs",
         title="Mississippi Division of Medicaid: Income Limits for Medicaid and CHIP Programs (effective March 1, 2026)",
         fmt="html", expr="2026-03-01", extraction={"html_content_selector": ".page-content"}, subtype="income_standards_page"),
    dict(row=92, jur="us-ms", cls="guidance", auth="ms-dom", program="MEDICAID",
         url="https://medicaid.ms.gov/medicaid-coverage/who-qualifies-for-coverage/working-disabled/",
         path="us-ms/guidance/dom/working-disabled", title="Mississippi Division of Medicaid: Working Disabled",
         fmt="html", extraction={"html_content_selector": ".page-content"}, subtype="agency_program_page"),
    dict(row=94, jur="us-ms", cls="guidance", auth="ms-dom", program="MEDICAID",
         url="https://medicaid.ms.gov/wp-content/uploads/2022/07/Healthier-Mississippi-Waiver-Full-Public-Notice-Website.pdf",
         path="us-ms/guidance/dom/healthier-mississippi-waiver/public-notice-2022-07-19",
         title="Healthier Mississippi Waiver Demonstration Extension Request: Full Public Notice and Comment Period (posted July 19, 2022)",
         fmt="pdf", expr="2022-07-19", subtype="waiver_public_notice_pdf"),
    dict(row=95, jur="us-ms", cls="guidance", auth="ms-dom", program="MEDICAID",
         url="https://medicaid.ms.gov/wp-content/uploads/2024/04/20240403_MES_Gainwell_PRP-101_Member-Coverage-Description-Job_Aid_v0.1.pdf",
         path="us-ms/guidance/dom/member-coverage-descriptions-job-aid",
         title="Mississippi Division of Medicaid Job Aid: Member Coverage Descriptions (PRP-101, v0.1, 2024-04-03)",
         fmt="pdf", expr="2024-04-03", subtype="job_aid_pdf"),
    dict(row=97, jur="us-ms", cls="guidance", auth="ms-dom", program="MEDICAID",
         url="https://medicaid.ms.gov/wp-content/uploads/2026/02/HMW-Fact-Sheet-2026.pdf",
         path="us-ms/guidance/dom/healthier-mississippi-waiver/fact-sheet-2026",
         title="Healthier Mississippi Waiver Medicaid Fact Sheet (2026)", fmt="pdf", subtype="program_fact_sheet_pdf"),
    dict(row=96, jur="us-ms", cls="policy", auth="ms-dom", program="MEDICAID",
         url="https://medicaid.ms.gov/wp-content/uploads/2024/09/Healthier-Mississippi-Extension.pdf",
         path="us-ms/policy/dom/healthier-mississippi-1115-extension-2024",
         title="CMS approval of the Healthier Mississippi Section 1115 Demonstration extension (11-W-00185/4): expenditure authority and special terms and conditions",
         fmt="pdf", subtype="cms_1115_approval_pdf"),
    dict(row=93, jur="us-ms", cls="manual", auth="ms-dom", program="MEDICAID",
         url="https://medicaid.ms.gov/wp-content/uploads/2017/10/Chapter-101.pdf",
         path="us-ms/manual/dom/medicaid/chapter-101-2017-10",
         title="Mississippi Division of Medicaid Eligibility Policy and Procedures Manual, Chapter 101: Coverage Groups and Processing Applications and Reviews (October 2017 file)",
         fmt="pdf", subtype="eligibility_manual_chapter_pdf",
         note="Superseded edition; the September 2025 revision is held at us-ms/manual/dom/medicaid/chapter-101 (us-ms/manual/2026-09-10-medicaid-state-eligibility-manual)"),
    dict(row=98, jur="us-ms", cls="regulation", auth="ms-dom", program="MEDICAID",
         url="https://www.medicaid.ms.gov/wp-content/uploads/2014/01/Admin-Code-Part-104.pdf",
         path="us-ms/regulation/title-23/part-104",
         title="Mississippi Administrative Code Title 23: Medicaid, Part 104: Income (Division of Medicaid file, 2014)",
         fmt="pdf", subtype="administrative_code_part_pdf"),
    # --- North Dakota, Nevada ---
    dict(row=99, jur="us-nd", cls="guidance", auth="nd-leg", program="MEDICAID",
         url="https://ndlegis.gov/assembly/69-2025/testimony/HHUMSER-1067-20250114-28935-F-FREMMING_KRISTA.pdf",
         path="us-nd/guidance/legislature/testimony/hb-1067-2025-01-14-dhhs",
         title="Testimony on House Bill No. 1067, House Human Services Committee, January 14, 2025 (Krista Fremming, ND HHS Medical Services)",
         fmt="pdf", expr="2025-01-14", subtype="agency_legislative_testimony_pdf"),
    dict(row=100, jur="us-nv", cls="guidance", auth="nv-dhcfp", program="MEDICAID",
         url="https://medicaid.nv.gov/Downloads/provider/web_announcement_3748_20251020.pdf",
         path="us-nv/guidance/dhcfp/web-announcement-3748",
         title="Nevada Medicaid Web Announcement 3748: Recipient Eligibility Expanded for Postpartum Care Services (October 20, 2025)",
         fmt="pdf", expr="2025-10-20", subtype="provider_web_announcement_pdf"),
    # --- Oregon ---
    dict(row=104, jur="us-or", cls="regulation", auth="or-odhs", program="MEDICAID",
         url="https://ch461rules.odhs.oregon.gov/historical/461-155-0250_history.pdf",
         path="us-or/regulation/chapter-461/division-155/rule-461-155-0250-history",
         title="OAR 461-155-0250 Income and Payment Standard; OSIPM: historical versions (ODHS chapter 461 rule history)",
         fmt="pdf", expr="2025-01-01", subtype="administrative_rule_history_pdf",
         note="Prior versions (effective 1-01-25 and earlier); the current rule is held at us-or/regulation/chapter-461/division-155/rule-461-155-0250"),
    dict(row=106, jur="us-or", cls="statute", auth="or-leg", program="MEDICAID",
         url="https://olis.oregonlegislature.gov/liz/2021R1/Downloads/MeasureDocument/HB3352/Enrolled",
         path="us-or/statute/session-laws/2021/hb3352", title="Oregon Enrolled House Bill 3352 (2021 Regular Session)",
         fmt="pdf", expr="2021-07-01", subtype="enrolled_bill_pdf"),
    dict(row=107, jur="us-or", cls="guidance", auth="or-oha", program="MEDICAID",
         url="https://www.oregon.gov/oha/hsd/ohp/pages/healthier-oregon.aspx",
         path="us-or/guidance/oha/healthier-oregon", title="Oregon Health Authority: Healthier Oregon",
         fmt="html", extraction=dict(MAIN), subtype="agency_program_page"),
    dict(row=110, jur="us-or", cls="guidance", auth="or-odhs-oha", program="MEDICAID",
         url="https://sharedsystems.dhsoha.state.or.us/DHSForms/Served/de5530.pdf",
         path="us-or/guidance/odhs-oha/combined-standards-de5530",
         title="ODHS/OHA Combined Standards (DE 5530)", fmt="pdf", subtype="standards_chart_pdf"),
    # --- South Carolina, Tennessee, Texas, Virginia ---
    dict(row=111, jur="us-sc", cls="policy", auth="scdhhs", program="MEDICAID",
         url="https://www.scdhhs.gov/sites/dhhs/files/waivers/2025-06-23%20Palmetto%20Pathways%20to%20Independence%20Submission%20(1).pdf",
         path="us-sc/policy/scdhhs/1115/palmetto-pathways-to-independence-2025-06-23",
         title="South Carolina Palmetto Pathways to Independence: Community Engagement Section 1115 Demonstration Waiver Application (June 23, 2025)",
         fmt="pdf", expr="2025-06-23", subtype="section_1115_application_pdf"),
    dict(row=112, jur="us-tn", cls="policy", auth="tenncare", program="MEDICAID",
         url="https://www.tn.gov/content/dam/tn/tenncare/documents2/SSPPParentsAndOtherCaretakerRelatives.pdf",
         path="us-tn/policy/tenncare/state-plan/parents-and-other-caretaker-relatives",
         title="TennCare Medicaid State Plan: Eligibility Groups - Mandatory Coverage - Parents and Other Caretaker Relatives (TN-21-0010, approved 3/23/2022, effective 10/1/2021)",
         fmt="pdf", expr="2021-10-01", subtype="medicaid_state_plan_page_pdf"),
    dict(row=113, jur="us-tx", cls="manual", auth="tx-hhsc", program="CHIP",
         url="https://www.hhs.texas.gov/sites/default/files/documents/laws-regulations/handbooks/umcm/6-3.pdf",
         path="us-tx/manual/hhsc/umcm/6-3", title="Texas HHSC Uniform Managed Care Manual 6.3: CHIP Cost Sharing",
         fmt="pdf", subtype="managed_care_manual_chapter_pdf"),
    dict(row=114, jur="us-va", cls="manual", auth="dmas", program="MEDICAID",
         url="https://www.dmas.virginia.gov/media/ifujac10/m03-7-1-24.pdf",
         path="us-va/manual/dmas/medicaid/m03-2024-07-01",
         title="Virginia Medical Assistance Eligibility Manual Chapter M03: Covered Groups Requirements (7-1-24 file)",
         fmt="pdf", expr="2024-07-01", subtype="eligibility_manual_chapter_pdf",
         note="Superseded edition; the 4-1-26 file is held at us-va/manual/dmas/medicaid/m03 (us-va/manual/2026-09-10-medicaid-state-eligibility-manual)"),
    # --- Washington ---
    dict(row=115, jur="us-wa", cls="statute", auth="wa-leg", program="CHIP",
         url="https://app.leg.wa.gov/rcw/default.aspx?cite=74.09.470",
         path="us-wa/statute/74/74.09/74.09.470", title="RCW 74.09.470: Children's health care coverage",
         fmt="html", extraction={"html_content_selector": "#mainContent", "segmentation": "single_block"},
         subtype="statute_section_html"),
    dict(row=122, jur="us-wa", cls="statute", auth="wa-leg", program="MEDICAID",
         url="https://lawfilesext.leg.wa.gov/biennium/2023-24/Pdf/Bills/Session%20Laws/Senate/5187-S.SL.pdf",
         path="us-wa/statute/session-laws/2023/chapter-475-essb-5187",
         title="Laws of 2023, chapter 475 (Engrossed Substitute Senate Bill 5187, 2023-25 operating budget, partial veto)",
         fmt="pdf", expr="2023-05-16", subtype="session_law_pdf"),
    dict(row=123, jur="us-wa", cls="guidance", auth="wa-hca", program="MEDICAID",
         url="https://www.hca.wa.gov/about-hca/programs-and-initiatives/apple-health-medicaid/apple-health-expansion",
         path="us-wa/guidance/hca/apple-health-expansion", title="Washington HCA: Apple Health Expansion",
         fmt="html", extraction={"html_content_selector": "div.region-content"}, subtype="agency_program_page"),
    dict(row=124, jur="us-wa", cls="guidance", auth="wa-hca", program="CHIP",
         url="https://www.hca.wa.gov/free-or-low-cost-health-care/i-need-medical-dental-or-vision-care/children",
         path="us-wa/guidance/hca/children", title="Washington HCA: Apple Health for Children",
         fmt="html", extraction={"html_content_selector": "div.region-content"}, subtype="agency_program_page"),
    # --- Wisconsin, Wyoming ---
    dict(row=126, jur="us-wi", cls="manual", auth="wi-dhs", program="CHIP",
         url="https://www.emhandbooks.wisconsin.gov/bcplus/policyfiles/6/48.1.htm",
         path="us-wi/manual/dhs/badgercare-plus/48-1",
         title="BadgerCare Plus Handbook 48.1: BadgerCare Plus Children's Premium Tables (Release 26-03, August 12, 2026)",
         fmt="html", expr="2026-08-12",
         extraction={"html_drop_selectors": [".topic-header", ".topic-header-shadow", ".breadcrumbs", ".minitoc", ".expanding-content"]},
         subtype="policy_handbook_topic"),
    dict(row=127, jur="us-wy", cls="guidance", auth="wdh", program="MEDICAID",
         url="https://health.wyo.gov/healthcarefin/medicaid/programs-and-eligibility/medicaid-income-requirements/",
         path="us-wy/guidance/wdh/medicaid-income-requirements", title="Wyoming Department of Health: Medicaid Income Requirements",
         fmt="html", extraction=dict(MAIN), subtype="income_standards_page"),
]


def state_code(jur: str) -> str:
    return jur.split("-", 1)[1]


def version_for(jur: str, cls: str) -> str:
    return f"2026-10-06-w6-health-{cls}-{state_code(jur)}"


def manifest_path(jur: str, cls: str) -> Path:
    return ROOT / "manifests" / f"{jur}-health-w6-{cls}.yaml"


def source_id(doc: dict) -> str:
    tail = doc["path"].split("/", 2)[2].replace("/", "-").replace(".", "-")
    return f"{doc['jur']}-w6-health-{tail}"[:120]


def entry(doc: dict) -> dict:
    meta = {
        "primary_source": True,
        "source_authority": AUTH[doc["auth"]],
        "program": doc["program"],
        "document_subtype": doc["subtype"],
        "source_discovery_group": f"{doc['jur']}/{doc['cls']}/w6-health",
        "discovered_via": DISCOVERED_VIA,
        "work_order": WORK_ORDER,
        "work_order_row": doc["row"],
        "bundle_url": doc.get("bundle_url", doc["url"]),
    }
    if doc.get("final"):
        meta["final_url"] = doc["final"]
    if doc.get("access"):
        meta["access_note"] = doc["access"]
    if doc.get("note"):
        meta["note"] = doc["note"]
    out = {
        "source_id": source_id(doc),
        "jurisdiction": doc["jur"],
        "document_class": doc["cls"],
        "title": doc["title"],
        "source_url": doc["url"],
        "source_format": doc["fmt"],
        "source_as_of": SOURCE_AS_OF,
        "expression_date": doc.get("expr", SOURCE_AS_OF),
        "citation_path": doc["path"],
    }
    extraction = dict(doc.get("extraction") or {})
    if doc["fmt"] == "pdf":
        extraction.setdefault("ocr", True)
    if extraction:
        out["extraction"] = extraction
    if doc.get("request"):
        out["request"] = dict(doc["request"])
    out["metadata"] = meta
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    rows = [d["row"] for d in DOCS]
    assert len(rows) == len(set(rows)), "duplicate work-order row"
    paths = [d["path"] for d in DOCS]
    assert len(paths) == len(set(paths)), "duplicate citation path"
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for doc in DOCS:
        groups[(doc["jur"], doc["cls"])].append(doc)
    if args.list:
        for doc in sorted(DOCS, key=lambda d: d["row"]):
            print(json.dumps({"row": doc["row"], "scope": f"{doc['jur']}/{doc['cls']}/{version_for(doc['jur'], doc['cls'])}",
                              "citation_path": doc["path"], "official_url": doc["url"],
                              "manifest": str(manifest_path(doc["jur"], doc["cls"]).relative_to(ROOT))}))
        return 0
    for (jur, cls), docs in sorted(groups.items()):
        body = {"version": version_for(jur, cls), "documents": [entry(d) for d in sorted(docs, key=lambda d: d["row"])]}
        path = manifest_path(jur, cls)
        path.write_text(yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=120))
        print(f"wrote {path.relative_to(ROOT)} ({len(docs)} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
