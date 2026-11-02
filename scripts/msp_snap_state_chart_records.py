"""Per-jurisdiction document records for scripts/build_msp_snap_state_charts_manifests.py.

Every URL below was located on the publisher's own site and verified from this machine on
2026-09-14 (HTTP status, content type, PDF text layer, figures read); see
docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md for the per-state evidence. States whose
current document is already held in a selected scope are recorded as pointers (no manifest);
blocked and image-only publishers are recorded without a manifest.
"""
from __future__ import annotations

from build_msp_snap_state_charts_manifests import IMPERSONATE, Doc, State

# ------------------------------------------------------------------------------------ MSP
# One scope per state, version 2026-09-14-msp-income-standards (medicare.md MED-ST-7; the
# resource and methodology elements MED-ST-2/3/4 where the chart carries them).

MSP_STATES: list[State] = [
    State(
        "us-az", "Arizona Health Care Cost Containment System (AHCCCS)",
        "https://www.azahcccs.gov/Members/GetCovered/", 1, "official_pdf_eligibility_chart",
        "AHCCCS 'Who Can Apply?' page links one FPL and income eligibility chart (PDF, RTF twin); the 2-page "
        "chart revised February 1, 2026 prints QMB/SLMB/QI-1 monthly limits ($1,330/$1,596/$1,796 single; "
        "$1,804/$2,164/$2,435 couple, without the $20 disregard) under 'Coverage for Medicare Beneficiaries' "
        "with resource limit N/A (no MSP asset test). azahcccs.gov answers the plain client (HTTP 200); the "
        "des.az.gov block was not involved. The AHCCCS eligibility policy manual chapter 600 (MA0615, held in "
        "the selected 2026-09-10 scope) states the same figures in prose; the chart is the standards document.",
        documents=[Doc(
            "us-az-ahcccs-eligibility-requirements-2026-02",
            "AHCCCS Eligibility Requirements, February 1, 2026 (FPL and Income Eligibility Chart)",
            "https://www.azahcccs.gov/Members/GetCovered/",
            "us-az/guidance/ahcccs/eligibility-requirements-chart/2026-02", "2026-02-01",
            download_url="https://www.azahcccs.gov/Members/Downloads/EligibilityRequirements.pdf",
            metadata={"document_subtype": "eligibility_standards_chart", "effective_date": "2026-02-01",
                      "msp_groups": "QMB, SLMB, QI-1 (page 2); resource test: none",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-co", "Colorado Department of Health Care Policy and Financing (HCPF)",
        "https://hcpf.colorado.gov/2026-memo-series-communication", 86, "official_pdf_operational_memo",
        "HCPF publishes the MSP standards as operational memos: OM 26-025 (issued 2026-04-08, effective "
        "2026-04-01; QMB $1,350/$1,824, SLMB $1,616/$2,184, QI-1 $1,816/$2,455, QDWI $2,680/$3,628 including "
        "the $20 disregard; supersedes OM 25-013) on the 2026 memo series page (86 PDF links, the only MSP memo "
        "of 2026) and OM 25-078 (issued 2025-12-29, effective 2026-01-01; MSP resource limits $11,450/$17,910 "
        "including the $1,500/$3,000 burial allowance) on the 2025 page. hcpf.colorado.gov (CloudFront) answers "
        "HTTP 403 to the plain client and HTTP 200 to the browser-impersonated client; both memos taken with "
        "browser impersonation.",
        documents=[
            Doc("us-co-hcpf-om-26-025",
                "HCPF OM 26-025: 2026 Increase to Income Limits, Medicare Savings Programs and Low-Income Subsidy",
                "https://hcpf.colorado.gov/sites/hcpf/files/HCPF%20OM%2026-025%202026%20Increase%20to%20Income%20"
                "Limits-Medicare%20Savings%20Programs%20and%20Low-Income%20Subsidy_Accessible.pdf",
                "us-co/guidance/hcpf/operational-memo/om-26-025", "2026-04-01", request=IMPERSONATE,
                metadata={"document_subtype": "operational_memo", "document_number": "HCPF OM 26-025",
                          "issue_date": "2026-04-08", "effective_date": "2026-04-01",
                          "closure_elements_extra": ["MED-ST-2", "MED-ST-4"]}),
            Doc("us-co-hcpf-om-25-078",
                "HCPF OM 25-078: 2026 Increase to Resource Limits, Medicare Savings Programs and Low-Income Subsidy",
                "https://hcpf.colorado.gov/sites/hcpf/files/HCPF%20OM%2025-078%202026%20Increase%20to%20Resource%20"
                "Limits%20-%20Medicare%20Savings%20Programs%20and%20Low-Income%20Subsidy.pdf",
                "us-co/guidance/hcpf/operational-memo/om-25-078", "2026-01-01", request=IMPERSONATE,
                metadata={"document_subtype": "operational_memo", "document_number": "HCPF OM 25-078",
                          "issue_date": "2025-12-29", "effective_date": "2026-01-01",
                          "index_url": "https://hcpf.colorado.gov/2025-memo-series-communication",
                          "closure_elements_extra": ["MED-ST-3"]}),
        ],
    ),
    State(
        "us-ct", "Connecticut Department of Social Services (DSS)",
        "https://portal.ct.gov/dss/knowledge-base/articles/fact-sheets-and-brochures-articles/income-tables-articles/"
        "dss-program-standards-chart", 2, "official_pdf_program_standards_chart",
        "The DSS Program Standards Chart knowledge-base article links two charts: the current 'As of 7/1/2026' "
        "chart (MSP block 'eff. 3/1/2026': QMB $2,807/$3,806, SLMB $3,073/$4,166, ALMB $3,272/$4,436) and the "
        "10/1/2026 chart that becomes current on 2026-10-01 (same MSP block, FY 2027 SNAP standards; not taken). "
        "The 1/1/2026 chart held in the selected us-ct/policy/2026-07-02-ct-ssp-upm-and-standards scope prints "
        "the 3/1/2025 MSP figures, so a dated sibling path is taken under the same document class (policy, the "
        "state's precedent for this chart). The MSP eligibility page prints the three tiers in prose.",
        document_class="policy",
        documents=[
            Doc("us-ct-dss-program-standards-chart-2026-07-01",
                "DSS Program Standards Chart: Income Limits and Standards for DSS Benefit Programs (As of 7/1/2026)",
                "https://portal.ct.gov/dss/knowledge-base/articles/fact-sheets-and-brochures-articles/"
                "income-tables-articles/dss-program-standards-chart",
                "us-ct/policy/dss/program-standards/2026-07-01", "2026-07-01",
                download_url="https://portal.ct.gov/dss/-/media/departments-and-agencies/dss/fact-sheets-and-issue-briefs/"
                             "fact-sheets/dss-program-standards-chart-effective-070126.pdf"
                             "?rev=d3d0a3b7ffa7403ab0e9b371e6a193b1&hash=CBB327624CDA9609DE31CD9DACE3CE39",
                metadata={"document_subtype": "program_standards_chart", "msp_effective_date": "2026-03-01",
                          "layout_note": "single dense landscape page; column order is scrambled in the text layer",
                          "closure_elements_extra": ["MED-ST-2"]}),
            Doc("us-ct-dss-msp-eligibility-2026-03-01",
                "Medicare Savings Program: Eligibility (monthly income limits effective March 1, 2026)",
                "https://portal.ct.gov/dss/health-and-home-care/medicare-savings-program/medicare-savings-program/eligibility",
                "us-ct/policy/dss/medicare-savings-program-eligibility/2026-03-01", "2026-03-01", source_format="html",
                metadata={"document_subtype": "agency_program_page", "effective_date": "2026-03-01",
                          "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]}),
        ],
    ),
    State(
        "us-dc", "District of Columbia Department of Health Care Finance (DHCF)",
        "https://dhcf.dc.gov/service/qualified-Medicare-beneficiary-qmb", 1, "official_html_program_page",
        "DHCF publishes no PDF standards chart or transmittal; the QMB service page (updated 2026-01-16) prints the "
        "2026 QMB monthly limits (300% FPL plus the $20 disregard: $4,010 one person, $5,430 two) and states no "
        "asset test. The District operates only the QMB tier (its ceiling exceeds 135% FPL, so no SLMB/QI dollar "
        "standards exist). The 'Eligibility Changes to the Medicaid Program Effective January 1, 2026' resource "
        "document describes the transition without dollar limits and is not taken.",
        documents=[Doc(
            "us-dc-dhcf-qmb-income-limits-2026",
            "Full Duals and Qualified Medicare Beneficiary (QMB) Only: 2026 income limits (DHCF service page)",
            "https://dhcf.dc.gov/service/qualified-Medicare-beneficiary-qmb",
            "us-dc/guidance/dhcf/qmb-income-limits/2026", "2026-01-16", source_format="html",
            metadata={"document_subtype": "agency_program_page", "page_updated": "2026-01-16",
                      "msp_groups": "QMB only (300% FPL); resource test: none",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-3", "MED-ST-4"]},
        )],
    ),
    State(
        "us-de", "Delaware Health and Social Services, Division of Medicaid and Medical Assistance (DMMA)",
        "https://dhss.delaware.gov/dmma/home/income-limits/", 1, "official_pdf_administrative_notice",
        "DMMA Administrative Notice A-03-2026 (signed 2026-02-04) prints the 2026 QMB/SLMB/QI-1/QDWI monthly "
        "limits for family sizes 1 and 2 ($1,330/$1,596/$1,796/$2,660; $1,804/$2,164/$2,435/$3,607), effective "
        "2026-04-01 for MSP; Delaware applies no MSP resource test. The DMMA Medicaid Income Limits page reproduces "
        "the MSP table (taken as the HTML secondary). Both answer the plain client.",
        documents=[
            Doc("us-de-dmma-administrative-notice-a-03-2026",
                "DMMA Administrative Notice A-03-2026: 2026 Federal Poverty and Medicaid Assistance Levels",
                "https://dhss.delaware.gov/wp-content/uploads/sites/11/2026/06/2026-Federal-Poverty-and-Medicaid-Assistance-Levels.pdf",
                "us-de/guidance/dmma/administrative-notice/a-03-2026", "2026-04-01",
                metadata={"document_subtype": "administrative_notice", "document_number": "A-03-2026",
                          "signed_date": "2026-02-04", "effective_date": "2026-04-01",
                          "closure_elements_extra": ["MED-ST-2"]}),
            Doc("us-de-dmma-medicaid-income-limits-2026",
                "Medicaid Income Limits: 2026 Monthly Countable Income for Medicare Savings Programs (DMMA page)",
                "https://dhss.delaware.gov/dmma/home/income-limits/",
                "us-de/guidance/dmma/medicaid-income-limits/2026", "2026-04-01", source_format="html",
                metadata={"document_subtype": "agency_program_page", "closure_elements_extra": ["MED-ST-2"]}),
        ],
    ),
    State(
        "us-fl", "Florida Department of Children and Families, ESS Program Policy Manual",
        "https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual/",
        27, "manual_appendix_pointer",
        "Done by pointer: the ESS Program Policy Manual index links Appendix A-9.1 'Medicare Savings Programs and "
        "Low-Income Subsidy Coverage Groups Financial Standards' (ffic.myflfamilies.com/manual/essfiles/59106.pdf, "
        "HTTP 200), headed 'Interim Effective January 2026 / Financial Standards April 2025' (QMB $1,342, SLMB "
        "$1,609, QI1 $1,811, assets $9,950/$14,910). The selected scope us-fl/manual/"
        "2026-05-27-fl-ess-manual-r2026-07-15-self-contained already holds this edition at us-fl/manual/dcf/"
        "ess-program-policy-manual/appendix-a-9-1-medicare-savings-programs-and-low-income-subsidy-coverage-groups-"
        "financial-standards (the closure regex missed it because the figures sit in a table without a 2026 date "
        "next to the group term). Nothing new to take; DCF has not posted an April 2026 revision.",
        status="done",
        pointer_scope={"jurisdiction": "us-fl", "document_class": "manual", "version": "2026-05-27-fl-ess-manual-r2026-07-15-self-contained"},
    ),
    State(
        "us-ga", "Georgia Department of Community Health, Georgia Medicaid",
        "https://medicaid.georgia.gov/how-apply/basic-eligibility", 2, "official_pdf_financial_limits_chart",
        "medicaid.georgia.gov answered the plain client (HTTP 200; the dch/dfcs.georgia.gov block was not "
        "involved). The Basic Eligibility page links two limits documents: the one-page '2026 Financial Limits, All "
        "Programs' chart (income limits effective 3/1/2026, revised 3/5/2026: QMB/SLMB/QI-1/QDWI as FPL% + $20, "
        "resources $9,950/$14,910) and the three-page '2026 Income and Resource Limits' narrative (QMB only). The "
        "chart's text layer is column-scrambled (dense landscape table).",
        documents=[
            Doc("us-ga-medicaid-financial-limits-2026",
                "2026 Financial Limits, All Programs (Income Limits Effective 3/1/2026, Revised 3/5/2026)",
                "https://medicaid.georgia.gov/how-apply/basic-eligibility",
                "us-ga/guidance/dch/medicaid/financial-limits-all-programs/2026", "2026-03-01",
                download_url="https://medicaid.georgia.gov/document/document/2026-financial-limits-revised-3526/download",
                metadata={"document_subtype": "financial_limits_chart", "revised": "2026-03-05",
                          "closure_elements_extra": ["MED-ST-2", "MED-ST-3", "MED-ST-4"]}),
            Doc("us-ga-medicaid-abd-fm-income-resource-limits-2026",
                "2026 Income and Resource Limits (ABD and Family Medicaid)",
                "https://medicaid.georgia.gov/how-apply/basic-eligibility",
                "us-ga/guidance/dch/medicaid/abd-fm-income-resource-limits/2026", "2026-03-01",
                download_url="https://medicaid.georgia.gov/document/document/2026-abd-fm-income-resource-limits/download",
                metadata={"document_subtype": "income_resource_limits_narrative"}),
        ],
    ),
    State(
        "us-hi", "Hawaii Department of Human Services, Med-QUEST Division",
        "https://medquest.hawaii.gov/en/resources/rules-and-policy.html", 7, "official_pdf_income_standards_chart",
        "The Med-QUEST Rules and Policies page lists seven annual MAGI and MAGI-Excepted income standards charts "
        "(2020-2026); the 2026 chart (effective 01/13/2026) prints QMB 100%, SLMB 120%, QI-1 135% and QDWI 200% "
        "monthly standards for household sizes 1-10 on the Hawaii poverty guideline (100% = $1,530) keyed to HAR "
        "17-1722 sections, plus the MAGI-Excepted asset limits $9,950/$14,910. Plain client HTTP 200.",
        documents=[Doc(
            "us-hi-medquest-income-standards-chart-2026",
            "2026 MAGI and MAGI-Excepted Income Standards Chart, Effective 01/13/2026",
            "https://medquest.hawaii.gov/en/resources/rules-and-policy.html",
            "us-hi/guidance/med-quest/magi-and-magi-excepted-income-standards-chart/2026", "2026-01-13",
            download_url="https://medquest.hawaii.gov/content/dam/formsanddocuments/resources/"
                         "magi-and-magi-excepted-income-standard-charts/2026%20PPDO%20MAGI%20and%20MAGI-Excepted%20"
                         "Income%20Standards%20CHART.pdf",
            metadata={"document_subtype": "income_standards_chart", "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-id", "Idaho Department of Health and Welfare (DHW)",
        "https://healthandwelfare.idaho.gov/medicaid-program-income-limits", 1, "official_html_program_page",
        "DHW publishes no PDF chart or transmittal; the Medicaid Program Income Limits page (last updated "
        "2026-04-20) carries a 'Medicare Savings Program, Effective January 2026' section with individual and "
        "couple tables (QMB $1,350/$1,824, SLMB $1,616/$2,184, QI $1,816/$2,455, resources $9,950/$14,910; FPL% "
        "plus the $20 disregard). The whole page is taken (it also holds the other program limits).",
        documents=[Doc(
            "us-id-dhw-medicaid-program-income-limits-2026",
            "Medicaid Program Income Limits: Medicare Savings Program (Effective January 2026)",
            "https://healthandwelfare.idaho.gov/medicaid-program-income-limits",
            "us-id/guidance/dhw/medicaid-program-income-limits/2026", "2026-01-01", source_format="html",
            metadata={"document_subtype": "agency_program_page", "page_updated": "2026-04-20",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-in", "Indiana Family and Social Services Administration, Office of Medicaid Policy and Planning",
        "https://www.in.gov/fssa/ompp/forms-documents-and-tools/medicaid-eligibility-policy-manual/", 22,
        "manual_chapter_pointer",
        "Done by pointer: IHCPPM Chapter 3000 Eligibility Standards (www.in.gov/fssa/ompp/files/Medicaid_PM_3000.pdf, "
        "HTTP 200, modified 2026-09-10) prints the QMB 150% / SLMB 170% / QDW 200% / QI 185% standards effective "
        "March 1, 2026 (3010.35.05-.20: $1,995 / $2,261 / $2,660 / $2,461 for one) and the 1/1/2026 resource "
        "limits. The selected scope us-in/manual/2026-09-10-chip-state-eligibility-manual already holds this "
        "chapter section by section (us-in/manual/fssa/chip/ihcppm-chapter-3000/3010.35.05 carries 'effective "
        "March 1, 2026' and $1995.00). Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-in", "document_class": "manual", "version": "2026-09-10-chip-state-eligibility-manual"},
    ),
    State(
        "us-ks", "Kansas Department of Health and Environment, Division of Health Care Finance (KanCare)",
        "https://www.kancare.ks.gov/providers/presumptive-eligibility", 1, "official_pdf_standards_appendix",
        "Kansas Medical Assistance Standards F-8 (07-26 edition, 9 pages) prints the MSP table 'Updated 4/1/2026' "
        "(QMB 100%, LMB 120%, ELMB 135%, QWD 200%: Kansas's names for QMB/SLMB/QI/QDWI) on page 3 and the "
        "$9,950/$14,910 resource limits on page 8. kancare.ks.gov (Akamai) answers HTTP 403 to the plain client "
        "and HTTP 200 to the browser-impersonated client. The CivicPlus URL carries a version stamp that changes "
        "on re-upload; the Presumptive Eligibility page is the only public page found linking F-8.",
        documents=[Doc(
            "us-ks-kdhe-medical-assistance-standards-f-8-2026-07",
            "Kansas Medical Assistance Standards F-8 (07-26): income and resource standards incl. QMB, LMB, ELMB, QWD",
            "https://www.kancare.ks.gov/providers/presumptive-eligibility",
            "us-ks/guidance/kdhe/medical-assistance-standards-f-8/2026-07", "2026-04-01",
            download_url="https://www.kancare.ks.gov/home/showpublisheddocument/4880/639165970250700000",
            request=IMPERSONATE,
            metadata={"document_subtype": "standards_appendix", "document_number": "F-8 (07-26)",
                      "msp_table_updated": "2026-04-01", "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-ky", "Kentucky Cabinet for Health and Family Services, DCBS Division of Family Support",
        "https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx", 12, "manual_volume_pointer",
        "Done by pointer: Operation Manual Volume IVA (Non-MAGI Medicaid, one 356-page PDF, HTTP 200) carries MS "
        "4455 'Income Limits for Medicare Savings Program' (R. 4/13/26, OMTL-693: QMB $1,350, SLMB $1,616, QI1 "
        "$1,816 for one, including the $20 exclusion) on PDF page 334 and MS 4450 resource limits. The selected "
        "scope us-ky/manual/2026-09-10-medicaid-state-eligibility-manual holds the same edition page by page "
        "(us-ky/manual/dcbs/medicaid/volume-iva; the 4/13/26 figures match). Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-ky", "document_class": "manual", "version": "2026-09-10-medicaid-state-eligibility-manual"},
    ),
    State(
        "us-la", "Louisiana Department of Health, Medicaid Eligibility Manual",
        "https://ldh.la.gov/medicaid/medicaid-eligibility-manual", 17, "manual_chart_pointer",
        "Done by pointer: chart Z-200 'Federal Poverty Income Guidelines, for programs changing effective March 1, "
        "2026' (issued 2026-01-30; 100/120/135/200% monthly figures $1,330/$1,596/$1,796/$2,660) and Z-2200 "
        "'Medicare Savings Program Resource Limits' are both held in the selected scope us-la/manual/"
        "2026-09-10-medicaid-state-eligibility-manual (us-la/manual/ldh/medicaid/z-200/page-1 prints 'Issued "
        "January 30, 2026 ... Effective March 1, 2026'; z-2200). Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-la", "document_class": "manual", "version": "2026-09-10-medicaid-state-eligibility-manual"},
    ),
    State(
        "us-ma", "Massachusetts Executive Office of Health and Human Services, MassHealth",
        "https://www.mass.gov/info-details/program-financial-guidelines-for-certain-masshealth-applicants-and-members",
        2, "official_pdf_eligibility_operations_memo_and_fpl_chart",
        "MassHealth publishes no single chart naming QMB/SLMB/QI with per-tier dollars. The tiers (QMB up to 190% "
        "FPL, SLMB over 190 to 210%, QI over 210 to 225%, no asset test since 2024-03-01) are set by Eligibility "
        "Operations Memo 24-03 (March 2024; the 2026 EOM list 26-01 to 26-09 has no MSP standards memo) and the "
        "2026 dollars by the program financial guidelines chart DG-FPL_2026-03 (effective 2026-03-01; 190% "
        "$2,527/$3,427, 225% $2,993/$4,058; no 210% column). Both taken; mass.gov answers HTTP 403 to the plain "
        "client and 200 to the browser-impersonated client. The MSP application form is not taken.",
        documents=[
            Doc("us-ma-masshealth-eom-24-03",
                "MassHealth Eligibility Operations Memo 24-03: Medicare Savings Programs (formerly MassHealth Senior "
                "Buy-In and MassHealth Buy-In)",
                "https://www.mass.gov/doc/eom-24-03-medicare-savings-programs-formerly-known-as-masshealth-senior-buy-in-"
                "and-masshealth-buy-in-programs-0/download",
                "us-ma/guidance/masshealth/eom/24-03", "2024-03-01", request=IMPERSONATE,
                metadata={"document_subtype": "eligibility_operations_memo", "document_number": "EOM 24-03",
                          "closure_elements_extra": ["MED-ST-1", "MED-ST-2", "MED-ST-3", "MED-ST-4"]}),
            Doc("us-ma-masshealth-income-standards-fpl-2026-03",
                "2026 MassHealth Income Standards and Federal Poverty Guidelines, Effective March 1, 2026 (DG-FPL_2026-03)",
                "https://www.mass.gov/doc/2026-masshealth-income-standards-and-federal-poverty-guidelines-0/download",
                "us-ma/guidance/masshealth/income-standards-and-fpl/2026-03", "2026-03-01", request=IMPERSONATE,
                metadata={"document_subtype": "income_standards_chart", "document_number": "DG-FPL_2026-03",
                          "closure_elements_extra": ["MED-ST-2"]}),
        ],
    ),
    State(
        "us-me", "Maine Department of Health and Human Services, Office for Family Independence",
        "https://www.maine.gov/dhhs/ofi/programs-services/health-care-assistance", 2, "official_pdf_eligibility_guidelines_chart",
        "The OFI health care assistance page links the 2026 MaineCare Eligibility Guidelines chart (file dated "
        "6.23.26; 2026 FPL, 100% = $1,330). Its Medicare Savings Programs (Buy-in) block prints QMB at 185% FPL "
        "($2,461/$3,337) and QI at 250% ($3,325/$4,509) with no asset test; Maine has no SLMB tier (22 MRS "
        "3174-LLL), so two tiers are the complete program. Plain client HTTP 200.",
        documents=[Doc(
            "us-me-ofi-mainecare-eligibility-guidelines-2026",
            "2026 MaineCare Eligibility Guidelines (OFI chart, incl. Medicare Savings Programs / Buy-in)",
            "https://www.maine.gov/dhhs/ofi/programs-services/health-care-assistance",
            "us-me/guidance/ofi/mainecare-eligibility-guidelines/2026", "2026-03-01",
            download_url="https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/"
                         "2026%20MaineCare%20Eligibility%20Guidelines%206.23..26_1.pdf",
            metadata={"document_subtype": "eligibility_guidelines_chart", "file_date": "2026-06-23",
                      "msp_groups": "QMB 185% FPL, QI 250% FPL; no SLMB tier; resource test: none",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-mi", "Michigan Department of Health and Human Services, Bridges Reference Tables Manual",
        "https://mdhhs-pres-prod.michigan.gov/olmweb/ex/RF/Public/RFT/000.pdf", 22, "official_pdf_reference_table",
        "RFT 242 'AD-Care and Medicare Savings Program Income Limits' (RFB 2026-004, 4-1-2026) prints the "
        "full-coverage QMB, limited-coverage QMB (SLMB) and ALMB (QI) monthly limits effective 4/1/2026 (QMB "
        "$1,350/$1,824, SLM to $1,616/$2,184, ALMB to $1,816/$2,455, +$20 disregard). Path-case gotcha: the "
        "uppercase /olmweb/EX/... path (and the dhhs.michigan.gov/OLMWEB redirect) serves the stale RFB 2025-004 "
        "edition; the lowercase /olmweb/ex/... path serves the current one and is the URL taken. The RFT 000 table "
        "of contents (RFB 2026-006) lists 22 tables. MSP resource limits are in BEM 165 (selected Bridges scope). "
        "Class manual: the reference tables are part of the Bridges manual family held as manual.",
        document_class="manual",
        documents=[Doc(
            "us-mi-mdhhs-rft-242-2026-04",
            "RFT 242: AD-Care and Medicare Savings Program Income Limits (RFB 2026-004, 4-1-2026)",
            "https://mdhhs-pres-prod.michigan.gov/olmweb/ex/RF/Public/RFT/242.pdf",
            "us-mi/manual/mdhhs/bridges-reference-tables/rft-242", "2026-04-01",
            metadata={"document_subtype": "reference_table", "document_number": "RFT 242 (RFB 2026-004)",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-4"]},
        )],
    ),
    State(
        "us-mn", "Minnesota Department of Human Services (eDocs)",
        "https://edocs.dhs.state.mn.us/lfserver/Public/DHS-3461A-ENG", 1, "official_pdf_income_and_asset_guidelines",
        "DHS-3461A 'Insurance Affordability Programs (IAPs) Income and Asset Guidelines' (6-26 edition, effective "
        "7/1/26 to 6/30/27) is the agency's MSP dollar chart: QMB/SLMB/QI/QWD monthly and annual limits with the $20 "
        "disregard ($1,350/$1,616/$1,816/$2,680 for one) and asset limits ($10,000/$18,000). The unversioned eDocs "
        "URL stacks the current edition (pages 1-2) over the prior 10-25 edition (pages 3-4), so pages 1-2 are "
        "taken as one block. The EPM Appendix F host hcopub.dhs.state.mn.us resets connections and fails TLS "
        "verification from this machine (both clients); eDocs answers the plain client.",
        documents=[Doc(
            "us-mn-dhs-3461a-2026-06",
            "DHS-3461A-ENG: Insurance Affordability Programs (IAPs) Income and Asset Guidelines (6-26), "
            "Effective 7/1/26 to 6/30/27",
            "https://edocs.dhs.state.mn.us/lfserver/Public/DHS-3461A-ENG",
            "us-mn/guidance/dhs/dhs-3461a/2026-06", "2026-07-01",
            extraction={"segmentation": "single_block", "start_page": 1, "end_page": 2},
            metadata={"document_subtype": "income_and_asset_guidelines_chart", "document_number": "DHS-3461A-ENG (6-26)",
                      "page_note": "pages 3-4 of the file are the superseded 10-25 edition and are not extracted",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-3", "MED-ST-4"]},
        )],
    ),
    State(
        "us-mo", "Missouri Department of Social Services, Family Support Division (DSS Manuals)",
        "https://dssmanuals.mo.gov/mo-healthnet-for-the-aged-blind-and-disabled/", 1, "manual_appendix_pointer",
        "Done by pointer: MHABD Manual Appendix J 'Eligibility Standards for Non-MAGI Programs (07/2026)' "
        "(dssmanuals.mo.gov, HTTP 200 to the plain client; the upload path is dated 2022/07 but the file is "
        "overwritten in place) prints QMB $1,330, SLMB1 $1,596, SLMB2 (QI-1) $1,796 effective 04-01-26 and "
        "resource maximums $9,950/$14,910 effective 01-01-26. The selected scope us-mo/manual/"
        "2026-09-10-medicaid-state-eligibility-manual holds this same 07/2026 edition (us-mo/manual/dss/medicaid/"
        "mhabd/appendix-j/page-1). fsdimresources.mo.gov is Incapsula-blocked to both clients. Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-mo", "document_class": "manual", "version": "2026-09-10-medicaid-state-eligibility-manual"},
    ),
    State(
        "us-ms", "Mississippi Division of Medicaid",
        "https://medicaid.ms.gov/medicaid-coverage/who-qualifies-for-coverage/medicare-cost-sharing/", 1,
        "official_pdf_eligibility_guide",
        "The Medicare Cost-Sharing page links the 'Medicaid Eligibility Guide for Medicare Cost-Sharing Coverage' "
        "(revised 3/1/2026, 2 pages): QMB $1,380/$1,854, SLMB $1,646/$2,214, QI $1,846/$2,485 (2026 FPL plus the "
        "$50 Mississippi disregard), no resource test. The Eligibility Manual Appendix A-1 (rev. 3/1/2026) lists "
        "the same percentages but its multi-column table separates labels from figures; the guide is the closing "
        "document. Plain client HTTP 200.",
        documents=[Doc(
            "us-ms-dom-medicare-cost-sharing-eligibility-guide-2026-03",
            "Medicaid Eligibility Guide for Medicare Cost-Sharing Coverage (revised 3/1/2026)",
            "https://medicaid.ms.gov/wp-content/uploads/2026/03/Medicare-Cost-Sharing-2026.pdf",
            "us-ms/guidance/dom/medicare-cost-sharing-eligibility-guide/2026-03", "2026-03-01",
            metadata={"document_subtype": "eligibility_guide", "closure_elements_extra": ["MED-ST-2", "MED-ST-3", "MED-ST-4"]},
        )],
    ),
    State(
        "us-nc", "North Carolina Department of Health and Human Services, Division of Health Benefits (NC Medicaid)",
        "https://policies.ncdhhs.gov/divisional-a-m/health-benefits-nc-medicaid/adult-medicaid/", 2,
        "official_pdf_change_notice",
        "MA-2252 'Non-MAGI Medicaid Income/Reserve Limits (2026)' (effective 4/1/2026; MQB-Q/MQB-B/MQB-E are NC's "
        "names for QMB/SLMB/QI) is already held in the selected scope us-nc/manual/"
        "2026-09-10-medicaid-state-eligibility-manual (us-nc/manual/dhb/medicaid/ma-2252 carries 'April 1, 2026'), "
        "so it is not re-taken. Change Notice 03-26 (2026-02-03), the transmittal that issues the 2026 FPL income "
        "changes and COLA disregard, was not held and is taken under the manual class of the NC Medicaid family.",
        document_class="manual",
        documents=[Doc(
            "us-nc-dhb-change-notice-03-26",
            "Change Notice for Manual No. 03-26: 2026 Federal Poverty Level Changes (FPL) Income Changes and "
            "Cost of Living Adjustment (COLA) Disregard",
            "https://policies.ncdhhs.gov/document/change-notice-for-manual-no-03-26-2026-federal-poverty-level-changes-"
            "fpl-income-changes-and-cost-of-living-adjustment-cola-disregard/",
            "us-nc/manual/dhb/medicaid/change-notice/cn-03-26", "2026-04-01",
            download_url="https://policies.ncdhhs.gov/wp-content/uploads/CN-03-26-abd.pdf",
            metadata={"document_subtype": "manual_change_notice", "document_number": "CN 03-26", "issue_date": "2026-02-03",
                      "pointer": "us-nc/manual/dhb/medicaid/ma-2252 (selected scope) carries the 2026 dollar chart",
                      "closure_elements_extra": ["MED-ST-4"]},
        )],
    ),
    State(
        "us-nh", "New Hampshire Department of Health and Human Services, Bureau of Family Assistance",
        "https://www.dhhs.nh.gov/mam_htm/html/601_table_a_income_limits_mam.htm", 6, "official_html_service_release",
        "Service Release SR 26-03 (dated 03/26, effective 2026-03-01) is the FPL mass-change release that updates "
        "the QMB and SLMB/SLMB135 (NH's name for QI) income limits and restates the resource limits. MAM 601 Tables "
        "C (QMB) and D (SLMB/SLMB135), stamped 'SR 26-03', are already held in the selected scope us-nh/manual/"
        "2026-09-10-medicaid-state-eligibility-manual (us-nh/manual/dhhs/mam/601-table-c-..., 601-table-d-...) and "
        "are not re-taken. dhhs.nh.gov (Akamai) answers HTTP 403 to the plain client and 200 to the "
        "browser-impersonated client; the SR is taken with browser impersonation under the manual class of the MAM.",
        document_class="manual",
        documents=[Doc(
            "us-nh-dhhs-sr-26-03",
            "SR 26-03 Dated 03/26: Updated Income Limits for QMB, SLMB/SLMB135, GA, EMA, CM, PW (Service Release)",
            "https://www.dhhs.nh.gov/sr_htm/html/sr_26-03_dated_03_26.htm",
            "us-nh/manual/dhhs/sr/26-03", "2026-03-01", source_format="html", request=IMPERSONATE,
            metadata={"document_subtype": "service_release", "document_number": "SR 26-03",
                      "pointer": "us-nh/manual/dhhs/mam/601-table-c-qualified-medicare-beneficiary-qmb-mam and "
                                 "601-table-d-... (selected scope) carry the twelve-size tables",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-nj", "New Jersey Department of Human Services, Division of Medical Assistance and Health Services (DMAHS)",
        "https://www.nj.gov/humanservices/dmahs/providers-stakeholders/provider-resources/medicaid-communications/", 6,
        "official_pdf_medicaid_communication",
        "Medicaid Communication No. 26-03 (2026-02-26) 'Income Eligibility Standards Effective January 1, 2026' "
        "is the annual FPL communication; its page-3 chart labels QMB Only 100% FPL, SLMB 120% FPL and SLMB QI-1 "
        "135% FPL with annual and monthly columns for household sizes 1-8 (columns extract out of order in the text "
        "layer). The Division of Aging Services MSP page (nj.gov/humanservices/doas/services/l-p/msp/, HTTP 200) "
        "prints the 2026 annual income and the $9,950/$14,910 asset limits that 26-03 omits, but its markup nests "
        "the whole <main> inside an unclosed <nav>, which the HTML extractor drops, so it is recorded here and not "
        "taken. The 2026 communications folder lists 26-01 to 26-06 (26-01 is SSI/Medicaid Only, no MSP figures).",
        documents=[
            Doc("us-nj-dmahs-medicaid-communication-26-03",
                "Medicaid Communication No. 26-03: Income Eligibility Standards Effective January 1, 2026",
                "https://www.nj.gov/humanservices/dmahs/documents/providers-stakeholders/resources/medicaid/2026/"
                "26-03_Income_Eligibility_Standards_Effective_January-1-2026.pdf",
                "us-nj/guidance/dmahs/medicaid-communication/26-03", "2026-01-01",
                metadata={"document_subtype": "medicaid_communication", "document_number": "Medicaid Communication 26-03",
                          "issue_date": "2026-02-26", "closure_elements_extra": ["MED-ST-2"]}),
        ],
    ),
    State(
        "us-nm", "New Mexico Health Care Authority, Medical Assistance Division",
        "https://www.hca.nm.gov/lookingforinformation/income-eligibility-federal-poverty-level-guidelines/", 14,
        "official_pdf_standards_form",
        "MAD 029 'Aged, Blind and Disabled Medicaid Programs' revised 04/01/2026 (one dense page: FPL grid, SSI/LTC "
        "standards and the MSP boxes QMB $1,330/$1,804, SLIMB $1,596/$2,164, QI1 $1,796/$2,435; footnote: resource "
        "guidelines no longer apply to MSP). The FPL page lists 14 MAD 029 editions; the second 2026-2027 link "
        "(MAD-029-1.1.2026-Final.pdf) is the January revision still carrying 2025 FPL figures and is not taken. "
        "Plain client HTTP 200.",
        documents=[Doc(
            "us-nm-hca-mad-029-2026-04-01",
            "MAD 029: Aged, Blind and Disabled Medicaid Programs (Revised 04/01/2026; 2026-2027)",
            "https://www.hca.nm.gov/lookingforinformation/income-eligibility-federal-poverty-level-guidelines/",
            "us-nm/guidance/hca/mad-029/2026-04-01", "2026-04-01",
            download_url="https://www.hca.nm.gov/wp-content/uploads/MAD-029-Final-2026-1.pdf",
            metadata={"document_subtype": "eligibility_standards_form", "document_number": "MAD 029",
                      "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-nv", "Nevada Department of Health and Human Services, Division of Social Services",
        "https://www.dss.nv.gov/access-nv/eligibility-payments-manual/income-limit-charts/", 1, "official_html_income_limit_chart",
        "The Income Limit Charts page prints the MAABD '2026 Medicare Beneficiary Income Limits by Aid Category' "
        "(QMB $0-$1,330/$1,804, SLMB $1,330.01-$1,596/$2,164, QI-1 to $1,796/$2,435; the year only, no day) in a "
        "collapsed accordion beside the SNAP/TANF/MAGI charts; the whole page is taken. The formal Medical Assistance "
        "Manual Appendix C is stale (MTL 08/24, 'Effective 04/24'). Effective date recorded as 2026-04-01 from "
        "Nevada's April FPL cadence (metadata flags it as inferred). Plain client HTTP 200.",
        documents=[Doc(
            "us-nv-dss-income-limit-charts-maabd-2026",
            "Income Limit Charts: Medical Assistance to the Aged, Blind and Disabled (MAABD), 2026 Medicare "
            "Beneficiary Income Limits by Aid Category",
            "https://www.dss.nv.gov/access-nv/eligibility-payments-manual/income-limit-charts/",
            "us-nv/guidance/dss/income-limit-charts-maabd/2026", "2026-04-01", source_format="html",
            metadata={"document_subtype": "income_limit_chart_page", "expression_date_source": "inferred (page prints 2026 only)",
                      "closure_elements_extra": ["MED-ST-2"]},
        )],
    ),
    State(
        "us-ny", "New York State Department of Health, Office of Health Insurance Programs",
        "https://www.health.ny.gov/health_care/medicaid/publications/pub2026gis.htm", 13, "official_pdf_gis_message",
        "GIS 26 MA/05 '2026 Federal Poverty Levels' (2026-02-13) and its Attachment 1 'New York State Income and "
        "Resource Standards for Non-MAGI Population, Effective January 1, 2026' carry the MSP standards: New York "
        "has QMB (to 138% FPL, $1,836/$2,489) and QI (over 138% to 186%, $2,474/$3,355) only since the 2023 "
        "expansion, no SLMB tier and no resource test. The NYSDOH Medicare Savings Programs page (revised May "
        "2026) prints the same limits with the +$20 columns. health.ny.gov (CloudFront) answers HTTP 403 to the "
        "plain client and 200 to the browser-impersonated client (otda.ny.gov was not needed). The 2026 GIS index "
        "lists 13 messages.",
        documents=[
            Doc("us-ny-doh-gis-26-ma-05",
                "GIS 26 MA/05: 2026 Federal Poverty Levels",
                "https://www.health.ny.gov/health_care/medicaid/publications/docs/gis/26ma05.pdf",
                "us-ny/guidance/doh/gis/26-ma-05", "2026-01-01", request=IMPERSONATE,
                metadata={"document_subtype": "general_information_system_message", "document_number": "GIS 26 MA/05",
                          "issue_date": "2026-02-13", "closure_elements_extra": ["MED-ST-2"]}),
            Doc("us-ny-doh-gis-26-ma-05-attachment-1",
                "GIS 26 MA/05 Attachment 1: New York State Income and Resource Standards for Non-MAGI Population, "
                "Effective January 1, 2026",
                "https://www.health.ny.gov/health_care/medicaid/publications/docs/gis/26ma05_att1.pdf",
                "us-ny/guidance/doh/gis/26-ma-05/attachment-1", "2026-01-01", request=IMPERSONATE,
                metadata={"document_subtype": "standards_chart", "document_number": "GIS 26 MA/05 Att. 1",
                          "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]}),
            Doc("us-ny-doh-medicare-savings-programs-2026",
                "Medicare Savings Programs 2026 (NYSDOH page, revised May 2026)",
                "https://www.health.ny.gov/health_care/medicaid/program/update/savingsprogram/medicaresavingsprogram.htm",
                "us-ny/guidance/doh/medicare-savings-programs/2026", "2026-05-01", source_format="html", request=IMPERSONATE,
                metadata={"document_subtype": "agency_program_page", "closure_elements_extra": ["MED-ST-2", "MED-ST-4"]}),
        ],
    ),
    State(
        "us-oh", "Ohio Department of Medicaid",
        "https://medicaid.ohio.gov/resources-for-providers/policies-guidelines/medicaid-eligibility-procedure-letters/",
        None, "official_pdf_eligibility_procedure_letter",
        "Medicaid Eligibility Procedure Letter No. 194 (issued 2026-01-21, effective 2026-03-01) sets the 2026 "
        "QMB/SLMB/QI-1/QDWI standards under OAC 5160:1-3-02.1 for family sizes 1-8 and obsoletes MEPL 186; the "
        "one-page '2026 Monthly Financial Eligibility, Aged, Blind or Disabled / Medicare Premium Assistance "
        "Programs' chart prints sizes 1-12. Both PDFs answer the plain client on dam.assets.ohio.gov; the MEPL "
        "index page on medicaid.ohio.gov could not be fetched from this machine (HTTP/2 error / 404), so the index "
        "count is not recorded. Ohio applies no MSP resource test.",
        documents=[
            Doc("us-oh-odm-mepl-194",
                "Medicaid Eligibility Procedure Letter (MEPL) No. 194: 2026 Federal Poverty Level Income Guidelines",
                "https://dam.assets.ohio.gov/image/upload/medicaid.ohio.gov/About%20Us/PoliciesGuidelines/MEPL/"
                "MEPL_194_-_2026_Federal_Poverty_Level_Income_Guidelines.pdf",
                "us-oh/guidance/odm/mepl/194", "2026-03-01",
                metadata={"document_subtype": "eligibility_procedure_letter", "document_number": "MEPL 194",
                          "issue_date": "2026-01-21", "closure_elements_extra": ["MED-ST-2"]}),
            Doc("us-oh-odm-abd-monthly-financial-eligibility-2026",
                "Ohio Medicaid 2026 Monthly Financial Eligibility: Aged, Blind or Disabled Individuals / Medicare "
                "Premium Assistance Programs",
                "https://dam.assets.ohio.gov/image/upload/medicaid.ohio.gov/Families,%20Individuals/Programs/whoQualifies/"
                "2026_Aged_Blind_Disabled_Individuals.pdf",
                "us-oh/guidance/odm/abd-monthly-financial-eligibility-chart/2026", "2026-03-01",
                metadata={"document_subtype": "financial_eligibility_chart",
                          "expression_date_source": "MEPL 194 effective date (the chart is undated on its face)",
                          "closure_elements_extra": ["MED-ST-2"]}),
        ],
    ),
    State(
        "us-ok", "Oklahoma Human Services (OKDHS) / Oklahoma Health Care Authority",
        "https://oklahoma.gov/okdhs/searchcenter/okdhsformresults/c-1.html", 1, "policy_appendix_pointer",
        "Done by pointer: OKDHS Appendix C-1 'Maximum Income, Resource, and Payment Standards' (7/1/2026 revision, "
        "8 pages) carries the MSP schedules VI (QMBP), VII (SLMB) and VII.A (QI-1): FPL% + $20 ($1,350/$1,616/"
        "$1,816 for one) and the $9,950/$14,910 resource standard. The selected scope us-ok/policy/"
        "2026-07-21-ok-snap-policy holds this same revision (us-ok/policy/okdhs/snap/appendix-c-1 prints "
        "'7/1/2026' and $1,350), as does the superseding 2026-09-11 scope. The HTML rendering c-1.html is the "
        "older 1/1/2026 revision with 2025 figures. Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-ok", "document_class": "policy", "version": "2026-07-21-ok-snap-policy"},
    ),
    State(
        "us-or", "Oregon Department of Human Services, Aging and People with Disabilities",
        "https://www.oregon.gov/odhs/aging-disability-services/pages/medicare-savings-programs.aspx", 4,
        "official_html_program_page",
        "The MSP income standards are OAR 461-155-0290 (QMB), 461-155-0295 (SLMB, QI) and 461-155-0291 (QDWI), "
        "amended by SSP 17-2026 effective 2026-03-01 with the 2026 FPL dollar tables; all three rules are already "
        "held in the selected scope us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461 "
        "(rule-461-155-0290/-0291/-0295; the 0295 row carries $1,596/$1,796) and are not re-taken. The ODHS 'Help "
        "Paying Medicare Costs' page prints the four 2026 tiers for one- and two-person groups and states Oregon has "
        "no MSP asset test; taken as the standards page. The brochure host sharedsystems.dhsoha.state.or.us "
        "serves an incomplete TLS chain (not needed). Plain client HTTP 200.",
        documents=[Doc(
            "us-or-odhs-medicare-savings-programs-2026",
            "ODHS Aging and Disability Services: Help Paying Medicare Costs (Medicare Savings Programs), 2026 income limits",
            "https://www.oregon.gov/odhs/aging-disability-services/pages/medicare-savings-programs.aspx",
            "us-or/guidance/odhs/medicare-savings-programs/2026", "2026-03-01", source_format="html",
            metadata={"document_subtype": "agency_program_page",
                      "pointer": "OAR 461-155-0290, -0291, -0295 in us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461",
                      "closure_elements_extra": ["MED-ST-1", "MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-ri", "Rhode Island Executive Office of Health and Human Services (EOHHS)",
        "https://eohhs.ri.gov/Consumer/ProgramsServices/MedicarePremiumPaymentProgram.aspx", 1, "official_html_program_page",
        "EOHHS publishes no PDF chart; the Medicare Premium Payment Program page (last updated 2026-09-02) prints "
        "the 2026 limits: QMB $1,683/$2,275 (125% FPL, SLMB folded into QMB as of 2026-02-01 under SPA RI-26-0003), "
        "QI $2,255/$3,050 (168% FPL), resources $9,950/$14,910. Effective date recorded from the 2026-02-01 QMB "
        "change statement. Plain client HTTP 200.",
        documents=[Doc(
            "us-ri-eohhs-medicare-premium-payment-program-2026",
            "Medicare Premium Payment Program (MPP): 2026 monthly income and resource limits (EOHHS page)",
            "https://eohhs.ri.gov/Consumer/ProgramsServices/MedicarePremiumPaymentProgram.aspx",
            "us-ri/guidance/eohhs/medicare-premium-payment-program/2026", "2026-02-01", source_format="html",
            metadata={"document_subtype": "agency_program_page", "page_updated": "2026-09-02",
                      "closure_elements_extra": ["MED-ST-1", "MED-ST-2", "MED-ST-3", "MED-ST-4"]},
        )],
    ),
    State(
        "us-sc", "South Carolina Department of Health and Human Services (Healthy Connections Medicaid)",
        "https://www.scdhhs.gov/members/program-eligibility-and-income-limits", 2, "official_html_program_page",
        "The Program Eligibility and Income Limits page prints the QMB and the SLMB/QI sections with 'Eff. "
        "03/01/2026' monthly limits ($1,330/$1,596/$1,796; couple $1,804/$2,164/$2,435) and resource limits "
        "$9,950/$14,910 in accordions (the SLMB/QI resources cell is labelled 'Eff. 01/01/2025', an agency typo). "
        "The three-page 'Medicaid Eligibility Programs Effective March 1, 2026' PDF (URL still named 'Effective "
        "1.1') carries SLMB, QI and QDWI rows; both taken. Plain client HTTP 200.",
        documents=[
            Doc("us-sc-scdhhs-program-eligibility-and-income-limits-2026",
                "Program Eligibility and Income Limits: Qualified Medicare Beneficiaries; Specified Low Income Medicare "
                "Beneficiaries and Qualifying Individuals (2026)",
                "https://www.scdhhs.gov/members/program-eligibility-and-income-limits",
                "us-sc/guidance/scdhhs/program-eligibility-and-income-limits/2026", "2026-03-01", source_format="html",
                metadata={"document_subtype": "agency_program_page", "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]}),
            Doc("us-sc-scdhhs-medicaid-eligibility-programs-2026-03-01",
                "Medicaid Eligibility Programs Effective March 1, 2026",
                "https://www.scdhhs.gov/sites/dhhs/files/pdf/links/Medicaid%20Eligibility%20Groups%20Effective%201.1.pdf",
                "us-sc/guidance/scdhhs/medicaid-eligibility-programs/2026-03-01", "2026-03-01",
                metadata={"document_subtype": "eligibility_groups_chart", "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]}),
        ],
    ),
    State(
        "us-sd", "South Dakota Department of Social Services (DSS)",
        "https://dss.sd.gov/economicassistance/medical_programs.aspx", 2, "official_pdf_brochure",
        "Partial: no South Dakota document prints separate QMB/SLMB/QI dollar tiers. The Medicare Savings Program "
        "brochure EA05 (May 2026) prints the single 2026 MSP income ceiling ($1,816/$2,455 = 135% FPL + $20) and "
        "the resource limits; the Medicaid Coverage Groups page names QMB, SLMB and QI-1 with the $9,950/$14,910 "
        "resource limits. Both taken as the state's current official publications; the application DSS-EA-270, the "
        "Guide to Assistance and the billing manual were checked and print no figures. Plain client HTTP 200.",
        status="needs_review",
        documents=[
            Doc("us-sd-dss-medicare-savings-program-brochure-2026-05",
                "Medicare Savings Program Application Assistance (brochure EA05, May 2026)",
                "https://dss.sd.gov/formsandpubs/docs/MEDELGBLTY/MedicareSavingsProgramBrochureEntire.pdf",
                "us-sd/guidance/dss/medicare-savings-program-brochure/2026-05", "2026-05-01",
                metadata={"document_subtype": "agency_brochure", "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]}),
            Doc("us-sd-dss-medicaid-coverage-groups-2026",
                "South Dakota Medicaid Coverage Groups: Medicare Savings Program (DSS page)",
                "https://dss.sd.gov/economicassistance/medical_programs.aspx",
                "us-sd/guidance/dss/medicaid-coverage-groups/2026", "2026-01-01", source_format="html",
                metadata={"document_subtype": "agency_program_page", "closure_elements_extra": ["MED-ST-1", "MED-ST-3"]}),
        ],
    ),
    State(
        "us-ut", "Utah Department of Health and Human Services, Office of Eligibility Policy (Medicaid Policy Manual)",
        "https://oepmanuals.dhhs.utah.gov/", None, "manual_table_pointer",
        "Needs review: the Medicaid Policy Manual TABLE II 'Aged, Blind and Disabled Income Limits and Other "
        "Important Figures' (effective 2026-03-01) prints the 100% FPL figure ($1,330/$1,804) and the QMB/SLMB/QI "
        "asset limits, but not the 120% and 135% dollar tiers (sections 320-2/320-3/320-4 define the tiers as "
        "percentages). TABLE II is already held in the selected scope us-ut/manual/"
        "2026-09-10-medicaid-state-eligibility-manual (us-ut/manual/dhhs/medicaid/tables-table-ii-...). No Utah "
        "publication with all three dollar tiers was found; nothing new to take.",
        status="needs_review",
        pointer_scope={"jurisdiction": "us-ut", "document_class": "manual", "version": "2026-09-10-medicaid-state-eligibility-manual"},
    ),
    State(
        "us-vt", "Department of Vermont Health Access (DVHA)",
        "https://dvha.vermont.gov/members/medicaid/medicaid-aged-blind-or-disabled-mabd", 4, "official_pdf_standards_chart",
        "The MABD page lists four standards documents (the Q1 1/1/2026 chart and standards-change notice, and their "
        "republished 4/1/2026 versions). The 2026 MABD PIL/FPL Income Chart effective 4/1/2026 and the 2026 "
        "Standards Change for Healthcare (version 4, 07/13/2026) print Vermont's tiers: QMB 150% FPL "
        "($1,995/$2,707), QI-1 202% ($2,687/$3,645), QDWI 200%, no resource test; SLMB sunset 1/1/2026. The DVHA "
        "MSP member page repeats them with a couple-range typo and is not taken. Plain client HTTP 200.",
        documents=[
            Doc("us-vt-dvha-mabd-pil-fpl-income-chart-2026",
                "2026 MABD PIL FPL Income Chart, Effective 4/1/2026 (Protected Income Level and Percentage of FPL)",
                "https://dvha.vermont.gov/sites/dvha/files/documents/MABD_PIL_Income_Chart_2026.pdf",
                "us-vt/guidance/dvha/mabd-pil-fpl-income-chart/2026", "2026-04-01",
                metadata={"document_subtype": "income_standards_chart", "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]}),
            Doc("us-vt-dvha-standards-change-for-healthcare-2026",
                "2026 Standards Change for Healthcare (Version 4, updated 07/13/2026)",
                "https://dvha.vermont.gov/sites/dvha/files/documents/Standards_Change_for_Healthcare_2026.pdf",
                "us-vt/guidance/dvha/standards-change-for-healthcare/2026", "2026-04-01",
                metadata={"document_subtype": "standards_change_notice", "version_date": "2026-07-13",
                          "closure_elements_extra": ["MED-ST-1", "MED-ST-2", "MED-ST-3"]}),
        ],
    ),
    State(
        "us-wa", "Washington State Health Care Authority (HCA)",
        "https://www.hca.wa.gov/free-or-low-cost-health-care/i-help-others-apply-and-access-apple-health/"
        "program-standard-income-and-resources", 64, "official_pdf_income_and_resource_standards_chart",
        "The Program standard for income and resources page (held as HTML in the selected 2026-09-10 Medicaid "
        "scope) lists 64 quarterly charts; the current chart 'Washington Apple Health Income and Resource "
        "Standards, July 1, 2026' (HCA 19-0096 (07/26), 3 pages) carries the MSP block 'Alternate financial "
        "eligibility standards 4/1/2026' with Washington's tiers (QMB 110% $1,483, SLMB 120% $1,616, QI-1 138% "
        "$1,855, QDWI 200% $2,680 for one; eleven household columns; no MSP resource row, no asset test). The "
        "unsuffixed URL is overwritten each quarter; earlier charts carry a YYYYMMDD suffix. Plain client HTTP 200.",
        documents=[Doc(
            "us-wa-hca-income-and-resource-standards-2026-07-01",
            "Washington Apple Health Income and Resource Standards, July 1, 2026 (HCA 19-0096 (07/26))",
            "https://www.hca.wa.gov/free-or-low-cost-health-care/i-help-others-apply-and-access-apple-health/"
            "program-standard-income-and-resources",
            "us-wa/guidance/hca/income-and-resource-standards/2026-07-01", "2026-07-01",
            download_url="https://www.hca.wa.gov/assets/free-or-low-cost/income-standards.pdf",
            metadata={"document_subtype": "income_and_resource_standards_chart", "document_number": "HCA 19-0096 (07/26)",
                      "msp_block_effective_date": "2026-04-01", "closure_elements_extra": ["MED-ST-2", "MED-ST-3"]},
        )],
    ),
    State(
        "us-wv", "West Virginia Department of Human Services, Bureau for Family Assistance (Income Maintenance Manual)",
        "https://bfa.wv.gov/income-maintenance-manual", 1, "manual_appendix_pointer",
        "Done by pointer: the BFA site publishes the whole Income Maintenance Manual as one 2,273-page PDF "
        "(bfa.wv.gov/media/40005/download, created 2026-08-25). The 2026 MSP figures are in Chapter 4 Income, "
        "Appendix A 'Income Limits' (QMB 1,330/1,804; SLIMB 1,331-1,596 / 1,805-2,164; QI-1 1,597-1,796 / "
        "2,165-2,435), not in Chapter 10. The selected scope us-wv/manual/2026-07-21-wv-income-maintenance-manual "
        "already holds this appendix with the 2026 FPL figures (us-wv/manual/bfa/income-maintenance-manual/"
        "page-407: 'Chapter 4 Income APPENDIX A: INCOME LIMITS ... SLIMB ... 1,596'). Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-wv", "document_class": "manual", "version": "2026-07-21-wv-income-maintenance-manual"},
    ),
    State(
        "us-wy", "Wyoming Department of Health, Division of Healthcare Financing (Medicaid Eligibility Online Manual)",
        "https://ecom.wyo.gov/", 2, "google_sites_image_tables",
        "Needs review: the EOM (Google Sites, HTTP 200 to the plain client) carries Table 1 'Federal Poverty Level "
        "Standard, Effective Date: April 1, 2026' (columns C/D/F = QMB 100%, SLMB 120%, QI 135%) and Table 7 "
        "'Maximum Resource Standards, Effective Date: January 1, 2026', but the dollar tables are JPEG images "
        "served from lh3.googleusercontent.com (1280 px, signed URLs); the page text holds only the titles, "
        "effective dates and column key. The official-documents extractor has no image adapter, and OCR of the "
        "1280 px rendering leaves the one- and two-person rows illegible, so no manifest is written. A "
        "browser-rendered or higher-resolution fetch is needed.",
        status="needs_review",
        blocked_evidence="ecom.wyo.gov/tables/table1 and /tables/table7: HTTP 200 HTML whose tables are "
                         "lh3.googleusercontent.com JPEGs (image/jpeg, ~235 KB, 1280x1416); =s0/=w4000 variants "
                         "return HTML; tesseract at 1280 px reads the 3+ person rows only.",
    ),
]


# ----------------------------------------------------------------------------------- SNAP
# One scope per state, version 2026-09-14-snap-fy2026-state-transmittal (snap.md snap_s20).

SNAP_STATES: list[State] = [
    State(
        "us-al", "Alabama Department of Human Resources, Food Assistance Division",
        "https://dhr.alabama.gov/food-assistance/", 2, "official_pdf_eligibility_summary_form",
        "DHR publishes no separate FY 2026 COLA transmittal; the Food Assistance page links Form DHR-FAP-1942 "
        "'Summarized Eligibility Requirements' (Rev. 10-25, 4 pages), which prints the FY 2026 gross/net income "
        "limits, standard deductions ($209/$223/$261/$299) and maximum allotments effective 10/01/25. The same table "
        "is page 8 of the combined application Form 2116/1942 Rev. 10-2025 (not taken). Page 1 is a graphic cover; "
        "pages 2-4 carry the text. Plain client HTTP 200.",
        documents=[Doc(
            "us-al-dhr-form-1942-summarized-eligibility-requirements-2025-10",
            "Food Assistance Program Summarized Eligibility Requirements (Form DHR-FAP-1942, Rev. 10-25)",
            "https://dhr.alabama.gov/wp-content/uploads/2025/10/Form-1942-Summarized-Eligibility-Requirements-Rev.-10-25.pdf",
            "us-al/guidance/dhr/food-assistance/form-1942-summarized-eligibility-requirements/2025-10", "2025-10-01",
            metadata={"document_subtype": "eligibility_summary_form", "document_number": "DHR-FAP-1942 Rev. 10-25",
                      "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-dc", "District of Columbia Department of Human Services, Economic Security Administration",
        "https://dhs.dc.gov/service/snap-eligibility-requirements", 2, "official_html_program_page",
        "DHS publishes no FY 2026 transmittal; the FY 2026 figures live on two service pages: 'SNAP Eligibility "
        "Requirements' (income limits October 1, 2025 to September 30, 2026) and 'SNAP Monthly Benefit' (maximum "
        "allotments, $24 minimum). The eligibility page's deduction paragraph still prints FY 2025 values (standard "
        "deduction $204, shelter cap $712, SUA $374), recorded in metadata. Plain client HTTP 200.",
        documents=[
            Doc("us-dc-dhs-snap-eligibility-requirements-fy2026",
                "SNAP Eligibility Requirements: income limits effective October 1, 2025 to September 30, 2026 (DHS page)",
                "https://dhs.dc.gov/service/snap-eligibility-requirements",
                "us-dc/guidance/dhs/snap-eligibility-requirements/fy2026", "2025-10-01", source_format="html",
                metadata={"document_subtype": "agency_program_page", "fiscal_year": "2026",
                          "caveat": "the deduction paragraph still prints FY 2025 standard deduction, shelter cap and SUA"}),
            Doc("us-dc-dhs-snap-monthly-benefit-fy2026",
                "SNAP Monthly Benefit: maximum monthly allotment levels October 1, 2025 to September 30, 2026 (DHS page)",
                "https://dhs.dc.gov/service/snap-monthly-benefit",
                "us-dc/guidance/dhs/snap-monthly-benefit/fy2026", "2025-10-01", source_format="html",
                metadata={"document_subtype": "agency_program_page", "fiscal_year": "2026"}),
        ],
    ),
    State(
        "us-de", "Delaware Health and Social Services, Division of Social Services",
        "https://dhss.delaware.gov/dss/division-of-social-services/snap/", 1, "official_html_program_page",
        "DSS publishes no separate transmittal; the SNAP program page prints the FY 2026 table 'Food Benefit Income "
        "Eligibility Limits and Maximum Benefit Amounts, October 1, 2025 to September 30, 2026' (200/165/130/100% "
        "limits and maximum benefits by household size) inside an accordion; deductions are not on the page. DSSM "
        "9060 on regulations.delaware.gov is a JavaScript shell to the plain client. Plain client HTTP 200.",
        documents=[Doc(
            "us-de-dss-snap-income-limits-and-maximum-benefits-fy2026",
            "SNAP: Food Benefit Income Eligibility Limits and Maximum Benefit Amounts, October 1, 2025 to September 30, 2026",
            "https://dhss.delaware.gov/dss/division-of-social-services/snap/",
            "us-de/guidance/dss/snap-income-limits-and-maximum-benefits/fy2026", "2025-10-01", source_format="html",
            metadata={"document_subtype": "agency_program_page", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-hi", "Hawaii Department of Human Services, Benefit, Employment and Support Services Division (BESSD)",
        "https://humanservices.hawaii.gov/bessd/snap/", 1, "official_html_program_page",
        "BESSD publishes no transmittal; the SNAP page prints the Hawaii-specific FY 2026 gross (130%/200%) and net "
        "(100%) monthly income eligibility standards effective 10/1/2025 (three tables; the 130% row for seven "
        "persons is misprinted '$6.064'). Maximum allotments are not published on the state site (the 2025-09-23 "
        "press release states only the reductions). Plain client HTTP 200.",
        documents=[Doc(
            "us-hi-bessd-snap-income-eligibility-standards-fy2026",
            "SNAP Gross and Net Monthly Income Eligibility Standards, Effective 10/1/2025 (BESSD SNAP page)",
            "https://humanservices.hawaii.gov/bessd/snap/",
            "us-hi/guidance/bessd/snap-income-eligibility-standards/fy2026", "2025-10-01", source_format="html",
            metadata={"document_subtype": "agency_program_page", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-ia", "Iowa Department of Health and Human Services, Bureau of Financial, Food, and Work Supports",
        "https://hhs.iowa.gov/about/policy-manuals/income-maintenance/income-maintenance-general-letters", 30,
        "official_pdf_general_letter",
        "Iowa transmits the FY 2026 standards through Employees' Manual general letters: GL 7-F-104 (2026-02-13, "
        "Title 7 Chapter F SNAP Budgeting: 'update the gross and net income limits effective 10/1/25 ... maximum "
        "benefit allotment effective 10/1/25') and companion GL 7-E-126 (2026-02-13, Chapter E SNAP Income incl. "
        "standard utility allowances). The general-letters index lists the 30 most recent letters; the standalone "
        "chapter links still served the September 2024 revisions. Plain client HTTP 200.",
        documents=[
            Doc("us-ia-hhs-general-letter-7-f-104",
                "General Letter No. 7-F-104: Employees' Manual Title 7, Chapter F, SNAP Budgeting (revised pages; "
                "FY 2026 income limits and maximum allotments)",
                "https://hhs.iowa.gov/about/policy-manuals/income-maintenance/income-maintenance-general-letters",
                "us-ia/guidance/hhs/general-letter/7-f-104", "2025-10-01",
                download_url="https://hhs.iowa.gov/media/18803/download?inline",
                metadata={"document_subtype": "general_letter", "document_number": "GL 7-F-104", "issue_date": "2026-02-13",
                          "fiscal_year": "2026"}),
            Doc("us-ia-hhs-general-letter-7-e-126",
                "General Letter No. 7-E-126: Employees' Manual Title 7, Chapter E, SNAP Income (revised pages; "
                "FY 2026 standard utility allowances)",
                "https://hhs.iowa.gov/about/policy-manuals/income-maintenance/income-maintenance-general-letters",
                "us-ia/guidance/hhs/general-letter/7-e-126", "2025-10-01",
                download_url="https://hhs.iowa.gov/media/18790/download?inline",
                metadata={"document_subtype": "general_letter", "document_number": "GL 7-E-126", "issue_date": "2026-02-13",
                          "fiscal_year": "2026"}),
        ],
    ),
    State(
        "us-id", "Idaho Department of Health and Welfare",
        "https://healthandwelfare.idaho.gov/services-programs/food-assistance", 1, "official_html_program_page",
        "Partial: DHW publishes no transmittal, chart or manual with FY 2026 figures; the only state-published FY "
        "2026 numbers are the gross (130% FPL) monthly income limits 'Effective October 2025' on the Apply for SNAP "
        "page. Net limits, deductions, SUAs and allotments are not on the state site. Plain client HTTP 200.",
        status="needs_review",
        documents=[Doc(
            "us-id-dhw-apply-snap-income-limits-fy2026",
            "Apply for SNAP: Monthly income limits for SNAP, Effective October 2025 (DHW page)",
            "https://healthandwelfare.idaho.gov/services-programs/food-assistance/apply-snap",
            "us-id/guidance/dhw/apply-snap-income-limits/fy2026", "2025-10-01", source_format="html",
            metadata={"document_subtype": "agency_program_page", "fiscal_year": "2026",
                      "caveat": "gross income limits only"},
        )],
    ),
    State(
        "us-ks", "Kansas Department for Children and Families, Economic and Employment Services (KEESM)",
        "https://content.dcf.ks.gov/ees/keesm/appendix/appendix.html", 2, "official_pdf_manual_appendix",
        "KEESM Appendix F-2 'Food Assistance Program Standards Effective October 1, 2025 to September 30, 2026' "
        "(one page: allotments, limits, standard deduction, $744 shelter cap, SUA $469 / LUA $345 / phone $44 / "
        "medical $175). The unversioned 'F-2 FA Program Standards.pdf' link already serves the FY 2027 chart, so "
        "the archived FY 2026 file name is taken. Taken under the manual class of the KEESM (selected "
        "us-ks/manual scope). Plain client HTTP 200.",
        document_class="manual",
        documents=[Doc(
            "us-ks-dcf-keesm-appendix-f-2-fy2026",
            "KEESM Appendix F-2: Food Assistance Program Standards Effective October 1, 2025 to September 30, 2026",
            "https://content.dcf.ks.gov/ees/keesm/appendix/appendix.html",
            "us-ks/manual/dcf/keesm/appendix/f-2/fy2026", "2025-10-01",
            download_url="https://content.dcf.ks.gov/ees/keesm/appendix/F-2%20FA%20Program%20Standards%2010-25%20to%2009.26.pdf",
            metadata={"document_subtype": "manual_appendix_standards_chart", "document_number": "KEESM Appendix F-2 (10-25)",
                      "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-ma", "Massachusetts Department of Transitional Assistance (DTA)",
        "https://www.mass.gov/lists/department-of-transitional-assistance-program-eligibility-charts-and-tables", 3,
        "official_pdf_issuance_tables",
        "The DTA Policy Online 'SNAP Annual Cost-of-Living Adjustment (COLA)' scheduled mailing (FY 2026 shelter "
        "cap, standard deductions, SUAs, minimum benefit, effective 10/1/2025) is already held in the selected scope "
        "us-ma/guidance/2026-08-03-ma-dta-snap-cola-official-source-recovery (us-ma/guidance/dta/policy-online/"
        "snap-cola/2025-10-01) and is not re-taken. The maximum allotments it omits are in the 'SNAP program "
        "issuance tables, 1 to 10 persons (106 CMR 364.980)' PDF republished by DTA (FNS basis-of-issuance table "
        "dated 12/16/2025 for October 1, 2025; 51 pages), taken with browser impersonation (mass.gov answers HTTP "
        "403 to the plain client). The 11-20 person table (101 pages) and the stale mass.gov COLA info page are not taken.",
        documents=[Doc(
            "us-ma-dta-snap-issuance-tables-1-10-fy2026",
            "SNAP program issuance tables: number of persons in household 1 to 10, as referenced at 106 CMR 364.980 "
            "(October 1, 2025)",
            "https://www.mass.gov/lists/department-of-transitional-assistance-program-eligibility-charts-and-tables",
            "us-ma/guidance/dta/snap-issuance-tables/fy2026/households-1-10", "2025-10-01",
            download_url="https://www.mass.gov/doc/snap-program-issuance-tables-number-of-persons-in-household-1-to-10-"
                         "as-referenced-at-106-cmr-364980/download",
            request=IMPERSONATE,
            metadata={"document_subtype": "benefit_issuance_table", "table_date": "2025-12-16", "fiscal_year": "2026",
                      "pointer": "us-ma/guidance/dta/policy-online/snap-cola/2025-10-01 (selected scope) carries the COLA notice"},
        )],
    ),
    State(
        "us-mn", "Minnesota Department of Human Services (Combined Manual)",
        "https://www.dhs.state.mn.us/main/idcplg?IdcService=GET_DYNAMIC_CONVERSION&dDocName=cm_002012"
        "&RevisionSelectionMethod=LatestReleased", None, "official_pdf_manual_change_attachment",
        "No FY 2026 COLA bulletin was found on DHS or DCYF; the Combined Manual 'Description of Changes Attachment, "
        "Revised Sections, Issued 10/2025' (19 pages) carries every FY 2026 figure in the revised sections "
        "(0018.15 homeless shelter $198.99, 0018.15.09 SUAs, 0018.21 standard deduction, 0019.06/0019.09 income "
        "limits, 0020.12 net standards, 0022.12.01 TFP and $24 minimum). Page 1 is watermarked DRAFT although the "
        "sections print 'ISSUE DATE 10/2025'. dhs.state.mn.us is Radware-gated: the PDF answers the "
        "browser-impersonated client (HTTP 200) and the plain client intermittently; taken with impersonation.",
        documents=[Doc(
            "us-mn-dhs-combined-manual-description-of-changes-2025-10",
            "Combined Manual Description of Changes Attachment: Revised Sections, Issued 10/2025 (MNDHS-072723)",
            "https://www.dhs.state.mn.us/main/groups/county_access/documents/pub/mndhs-072723.pdf",
            "us-mn/guidance/dhs/combined-manual-description-of-changes/2025-10", "2025-10-01", request=IMPERSONATE,
            metadata={"document_subtype": "manual_change_attachment", "document_number": "MNDHS-072723", "fiscal_year": "2026",
                      "caveat": "page 1 carries a DRAFT / PROPOSED CHANGES watermark; the revised sections are the issued text"},
        )],
    ),
    State(
        "us-mo", "Missouri Department of Social Services, Family Support Division (DSS Manuals)",
        "https://dssmanuals.mo.gov/memorandums/2025-im-memos/", 24, "official_pdf_flyer",
        "The FSD flyer '10/2025 SNAP Changes Effective October 1, 2025' (one page, created 2025-09-15) prints the "
        "FY 2026 gross/net limits, maximum allotments, standard deductions, $744 shelter cap and $198.99 homeless "
        "deduction (no SUAs or minimum). The 2025 IM memo series on dssmanuals.mo.gov is password-protected and "
        "dss.mo.gov/fsd/fstamp answers 404; the flyer URL is stable and overwritten yearly. Plain client HTTP 200.",
        documents=[Doc(
            "us-mo-fsd-snap-changes-flyer-2025-10",
            "Supplemental Nutrition Assistance Program (SNAP) Changes Effective October 1, 2025 (FSD flyer, 10/2025)",
            "https://dssmanuals.mo.gov/wp-content/uploads/2021/10/snap-changes-flyer.pdf",
            "us-mo/guidance/fsd/snap-changes-flyer/2025-10", "2025-10-01",
            metadata={"document_subtype": "agency_flyer", "file_created": "2025-09-15", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-ms", "Mississippi Department of Human Services, Division of Economic Assistance",
        "https://www.mdhs.ms.gov/help/snap/", 1, "official_html_program_page",
        "No MDHS transmittal for FY 2026 was found; the SNAP page prints 'SNAP Income Limits and Max Benefit "
        "Amounts' (gross 130%, net 100%, maximum allotments; 'All numbers are effective October 1, 2025'). The SNAP "
        "Policy Manual (Title 18 Part 14, hosted by the Secretary of State) carries no dollar standards. Plain "
        "client HTTP 200.",
        documents=[Doc(
            "us-ms-mdhs-snap-income-limits-and-max-benefits-fy2026",
            "SNAP Income Limits and Max Benefit Amounts, effective October 1, 2025 (MDHS SNAP page)",
            "https://www.mdhs.ms.gov/help/snap/",
            "us-ms/guidance/mdhs/snap-income-limits-and-max-benefits/fy2026", "2025-10-01", source_format="html",
            metadata={"document_subtype": "agency_program_page", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-mt", "Montana Department of Public Health and Human Services (SNAP Policy Manual)",
        "https://dphhs.mt.gov/hcsd/Manuals/snapmanual", 82, "manual_section_pointer",
        "Done by pointer: Montana publishes no separate COLA manual letter; SNAP 001 'Table of Standards: GMI and "
        "NMI, Thrifty Food Plan' (Effective Date October 1, 2025: 130/165/200% and net limits, allotments, $24 "
        "minimum, $744 cap), SNAP 602-2 (standard deduction) and SNAP 602-4 ($799 SUA) print the FY 2026 figures. "
        "The selected scope us-mt/manual/2026-07-17-mt-snap-policy-manual already holds SNAP 001 in this edition "
        "(us-mt/manual/dphhs/snap-policy-manual/snap001-table-of-standards-gmi-nmi-thrifty-food-plan prints "
        "'October 1, 2025' and $1,696) with 602-2 and 602-4. Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-mt", "document_class": "manual", "version": "2026-07-17-mt-snap-policy-manual"},
    ),
    State(
        "us-ne", "Nebraska Department of Health and Human Services",
        "https://dhhs.ne.gov/Pages/Guidance-Documents.aspx", 3, "official_pdf_guidance_document",
        "DHHS publishes the FY 2026 standards as guidance document DOC00428 'SNAP Program Standards, Effective "
        "October 1, 2025' (2 pages: 100/130/165% limits, maximum allotments, $24 minimum, resource limits; no "
        "deductions). The Regulation and Guidance Documents Index lists three SNAP guidance documents (DOC00428, "
        "DOC00429 deductions, DOC00431); DOC00429 was not located. Plain client HTTP 200.",
        documents=[Doc(
            "us-ne-dhhs-snap-program-standards-fy2026",
            "SNAP Program Standards, Effective October 1, 2025 (Nebraska DHHS guidance document DOC00428)",
            "https://dhhs.ne.gov/Guidance%20Docs/SNAP%20Program%20Standards.pdf",
            "us-ne/guidance/dhhs/snap-program-standards/fy2026", "2025-10-01",
            metadata={"document_subtype": "guidance_document", "document_number": "DOC00428", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-nh", "New Hampshire Department of Health and Human Services, Bureau of Family Assistance",
        "https://www.dhhs.nh.gov/fsm_htm/newfsm.htm", None, "official_html_service_release",
        "Service Release SR 25-32 (dated 10/25, signed 2025-09-18, effective 2025-10-01) is the FY 2026 SNAP mass "
        "change: 165/130/100/200% income limits, maximum allotments, $24 minimum, resource limits, SUAs "
        "($1,018/$373/$217/$39), standard deductions, $744 shelter cap, homeless and medical deductions. dhhs.nh.gov "
        "(Akamai) answers HTTP 403 to the plain client and 200 to the browser-impersonated client; the Food Stamp "
        "Manual index is a JavaScript frameset, so the SR count is not enumerated. Taken under the manual class of "
        "the FSM (the service releases are the transmittal family of the selected us-nh manual scopes).",
        document_class="manual",
        documents=[Doc(
            "us-nh-dhhs-sr-25-32",
            "SR 25-32 Dated 10/25: October 2025 SNAP Mass Change, Annual Update of the Minimum and Maximum SNAP "
            "Allotments, Maximum Income Limits, Standard Utility Allowances, Resource Limit and Certain Income Deductions",
            "https://www.dhhs.nh.gov/sr_htm/html/sr_25-32_dated_10_25.htm",
            "us-nh/manual/dhhs/sr/25-32", "2025-10-01", source_format="html", request=IMPERSONATE,
            metadata={"document_subtype": "service_release", "document_number": "SR 25-32", "signed_date": "2025-09-18",
                      "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-nj", "New Jersey Department of Human Services, Division of Family Development (NJ SNAP)",
        "https://www.nj.gov/humanservices/njsnap/apply/eligibility/", 1, "official_html_program_page",
        "Partial: no DFD Instruction announcing the FY 2026 COLA was found on nj.gov (DFD home, food stamps, "
        "reports and materials pages checked; the instructions paths answer 404) and the N.J.A.C. 10:87 manual "
        "(October 2025) prints no FY 2026 dollars. The NJ SNAP eligibility page carries the state's applied 185% "
        "FPL gross standard (figures valid October 2025 to September 2026) and the $95 state minimum benefit only. "
        "Plain client HTTP 200.",
        status="needs_review",
        documents=[Doc(
            "us-nj-dfd-njsnap-eligibility-fy2026",
            "NJ SNAP: Who is Eligible for SNAP? Gross monthly income eligibility standard (185% FPL), figures valid "
            "October 2025 to September 2026",
            "https://www.nj.gov/humanservices/njsnap/apply/eligibility/",
            "us-nj/guidance/dfd/njsnap-eligibility/fy2026", "2025-10-01", source_format="html",
            metadata={"document_subtype": "agency_program_page", "fiscal_year": "2026",
                      "caveat": "gross income standard and state minimum benefit only"},
        )],
    ),
    State(
        "us-nm", "New Mexico Health Care Authority, Income Support Division",
        "https://www.hca.nm.gov/lookingforinformation/income-eligibility-federal-poverty-level-guidelines/", 12,
        "official_pdf_standards_card",
        "ISD 017 'Income Eligibility Guidelines for SNAP and Financial Assistance and LIHEAP, October 1, 2025 to "
        "September 30, 2026' (the index-linked '-final-1' revision, created 2026-02-27, printed revision date "
        "'2-30-2026' sic): 100/130/200% limits, maximum allotments, $24 minimum, standard deductions, $744 shelter "
        "cap, HCSUA $419, LUA $289, telephone $51, homeless $198.99, asset limits. The earlier 9-30-2025 revision "
        "is still live but unlinked (same SNAP figures; not taken). The FPL page lists 12 English cards. Plain "
        "client HTTP 200.",
        documents=[Doc(
            "us-nm-hca-isd-017-fy2026",
            "ISD 017: Income Eligibility Guidelines for SNAP and Financial Assistance and LIHEAP, "
            "October 1, 2025 to September 30, 2026",
            "https://www.hca.nm.gov/lookingforinformation/income-eligibility-federal-poverty-level-guidelines/",
            "us-nm/guidance/hca/isd-017/fy2026", "2025-10-01",
            download_url="https://www.hca.nm.gov/wp-content/uploads/ISD-017-FPG-Cards-FY-2026-10.01.25-to-09.30.2026-final-1.pdf",
            metadata={"document_subtype": "income_guidelines_card", "document_number": "ISD 017", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-ny", "New York State Office of Temporary and Disability Assistance (OTDA)",
        "https://otda.ny.gov/policy/gis/2025/", None, "blocked_publisher",
        "Blocked: the FY 2026 SNAP standards are GIS 25 TA/DC059 '2025-2026 SNAP Standards' with Attachment 1 on "
        "otda.ny.gov, which resets the plain client's connection and answers the browser-impersonated client with "
        "an HTTP 200 JavaScript challenge page ('Please enable JavaScript', support ID), as in every earlier probe "
        "(batches 1-3, 2026-09-11 re-probe). Probed once each way and not fought; no mirror or archived copy used.",
        status="blocked_primary_source",
        blocked_evidence="https://www.otda.ny.gov/policy/gis/2025/25DC059.pdf: plain client connection reset; "
                         "curl_cffi chrome120 HTTP 200 text/html JavaScript challenge (support ID), not the PDF.",
    ),
    State(
        "us-nd", "North Dakota Health and Human Services (SNAP Policy Manual)",
        "https://www.nd.gov/dhs/policymanuals/SNAP/Content/Home%202.htm", 15, "official_pdf_manual_release",
        "SNAP Release 25.6 'Effective October 1, 2025' (6 pages, redline of the income levels, Thrifty Food Plan, "
        "SUA and standard deduction sections; the 130% one-person figure is misprinted $1,692) is the FY 2026 "
        "release on the manual's release log (15 PDFs). The live Appendix B has already rolled to FY 2027 (Release "
        "26.7) and releases 26-5/26-6 are held in the superseding 2026-09-11 scope; 25.6 was never taken. Taken "
        "under the manual class of the ND SNAP manual (us-nd/manual/hhs/snap/updates/...). Plain client HTTP 200.",
        document_class="manual",
        documents=[Doc(
            "us-nd-hhs-snap-release-25-6",
            "SNAP Release 25.6, Effective October 1, 2025 (income levels, Thrifty Food Plan, SUA, standard deduction)",
            "https://www.nd.gov/dhs/policymanuals/SNAP/Content/Home%202.htm",
            "us-nd/manual/hhs/snap/updates/release-25-6", "2025-10-01",
            download_url="https://www.nd.gov/dhs/policymanuals/SNAP/Content/Policy%20Update%20Documentation/2025/"
                         "SNAP%20Release%2025.6%20Effective%20October.1.2025.pdf",
            metadata={"document_subtype": "manual_release", "document_number": "Release 25.6", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-oh", "Ohio Department of Job and Family Services, Office of Family Assistance",
        "https://emanuals.jfs.ohio.gov/FoodAssistance/FACT/", None, "official_pdf_change_transmittal",
        "Food Assistance Change Transmittal No. 105 'October 1, 2025 Mass Change' (dated 2025-08-29, 4 pages, the "
        "full FY 2026 figure set) answers the plain client on dam.assets.ohio.gov. The eManuals FACT index host "
        "still does not answer (as on 2026-09-11) and the jfs.ohio.gov help-center pages answer 404, so the index "
        "count is not recorded.",
        documents=[Doc(
            "us-oh-odjfs-fact-105",
            "Food Assistance Change Transmittal No. 105: October 1, 2025 Mass Change",
            "https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/EBS/Programs%20Rules%20and%20Resources/Food%20Assistance/"
            "Food%20Assistance%20Change%20Letters/2025/FACT_105_-_October_1_2025_Mass_Change.pdf",
            "us-oh/guidance/odjfs/fact/105", "2025-10-01",
            metadata={"document_subtype": "change_transmittal", "document_number": "FACT 105", "issue_date": "2025-08-29",
                      "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-or", "Oregon Department of Human Services, Oregon Eligibility Partnership",
        "https://www.oregon.gov/odhs/transmittals/pages/oep-transmittals.aspx", None, "official_pdf_policy_transmittal",
        "OEP policy transmittal OEP-PT-25-034 'FFY2026 COLA Standards for SNAP' (issued 2025-09-09, 5 pages: "
        "income limits, deductions, FUA/LUA/TUA/IUA, maximum and minimum allotments). The transmittal index page "
        "is JavaScript-rendered, so the count is not recorded (the file was found by sweeping the pt25NNN series). "
        "Plain client HTTP 200.",
        documents=[Doc(
            "us-or-odhs-oep-pt-25-034",
            "OEP-PT-25-034: FFY2026 COLA Standards for SNAP (Oregon Eligibility Partnership policy transmittal)",
            "https://www.oregon.gov/odhs/transmittals/oeptransmittals/pt25034.pdf",
            "us-or/guidance/odhs/oep-transmittal/pt-25-034", "2025-10-01",
            metadata={"document_subtype": "policy_transmittal", "document_number": "OEP-PT-25-034", "issue_date": "2025-09-09",
                      "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-ri", "Rhode Island Department of Human Services",
        "https://dhs.ri.gov/programs-and-services/supplemental-nutrition-assistance-program-snap/supplemental-nutrition-0",
        2, "official_pdf_cola_notice",
        "'SNAP Annual Cost of Living Adjustment Effective October 1, 2025' (2 pages: 185%/200% limits, standard "
        "deduction, SUA $844, $744 cap, minimum and maximum) and 'SNAP Monthly Income Guidelines October 1, 2025 "
        "through September 30, 2026' (1 page). Neither prints an issue date. The COLA sheet is no longer linked "
        "from the SNAP page (the FY 2027 sheet replaced it) but is still served. Plain client HTTP 200.",
        documents=[
            Doc("us-ri-dhs-snap-cola-fy2026",
                "SNAP Annual Cost of Living Adjustment Effective October 1, 2025 (Fall 2025 SNAP eligibility and benefit changes)",
                "https://dhs.ri.gov/media/9561/download?language=en",
                "us-ri/guidance/dhs/snap-cola/fy2026", "2025-10-01",
                metadata={"document_subtype": "cola_notice", "fiscal_year": "2026"}),
            Doc("us-ri-dhs-snap-monthly-income-guidelines-fy2026",
                "SNAP Monthly Income Guidelines, October 1, 2025 through September 30, 2026",
                "https://dhs.ri.gov/media/9551/download?language=en",
                "us-ri/guidance/dhs/snap-monthly-income-guidelines/fy2026", "2025-10-01",
                metadata={"document_subtype": "income_guidelines_chart", "fiscal_year": "2026"}),
        ],
    ),
    State(
        "us-tn", "Tennessee Department of Human Services",
        "https://www.tn.gov/humanservices/for-families/supplemental-nutrition-assistance-program-snap/"
        "eligibility-information.html", 1, "official_pdf_income_chart",
        "'TN.gov Income Update 2026' (one page, the only document on the SNAP eligibility page) prints the FY 2026 "
        "130/165/200/100% income standards and maximum allotments for households of 1-24; no title, date or "
        "deductions are printed (effective date recorded from the FY 2026 figures). Plain client HTTP 200.",
        documents=[Doc(
            "us-tn-dhs-income-update-2026",
            "TN.gov Income Update 2026: SNAP gross and net income standards and maximum allotments (FY 2026)",
            "https://www.tn.gov/humanservices/for-families/supplemental-nutrition-assistance-program-snap/"
            "eligibility-information.html",
            "us-tn/guidance/dhs/snap-income-update/2026", "2025-10-01",
            download_url="https://www.tn.gov/content/dam/tn/human-services/documents/TN.gov_Income_Update%202026.pdf",
            metadata={"document_subtype": "income_chart", "fiscal_year": "2026",
                      "expression_date_source": "FY 2026 figures (the chart prints no date)"},
        )],
    ),
    State(
        "us-ut", "Utah Department of Workforce Services (Eligibility Manual)",
        "https://jobs.utah.gov/infosource/eligibilitymanual/", None, "official_html_manual_table",
        "Eligibility Manual Table 2 'SNAP Monthly Income Limits and Maximum Assistance Amounts (Table Effective: "
        "October 1, 2025)' (RoboHelp topic page; the manual root answers 403/404 so the count is not recorded). "
        "Deduction tables were not located. Taken under the manual class of the selected us-ut manuals scope. "
        "Plain client HTTP 200.",
        document_class="manual",
        documents=[Doc(
            "us-ut-dws-eligibility-manual-table-2-fy2026",
            "Eligibility Manual Table 2: SNAP Monthly Income Limits and Maximum Assistance Amounts "
            "(Table Effective October 1, 2025)",
            "https://jobs.utah.gov/infosource/eligibilitymanual/Tables,_Appendicies,_and_Charts/"
            "Tables,_Appendicies,_and_Charts/Table_2_-_SNAP_Monthly_Income_Limits_and_Maximum_Assistance_Amounts.htm",
            "us-ut/manual/dws/eligibility-manual/tables/table-2-snap-monthly-income-limits/fy2026", "2025-10-01",
            source_format="html",
            metadata={"document_subtype": "manual_table", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-vt", "Vermont Department for Children and Families, Economic Services Division (3SquaresVT Program Manual)",
        "https://dcf.vermont.gov/esd/laws-rules/procedures", 1, "official_html_manual_tables",
        "DCF publishes no standalone COLA transmittal; the 3SquaresVT Program Manual '3100 Tables' topic (RoboHelp "
        "page on the AHS host; income limits and maximum benefit, standard deduction, shelter deduction maximum, "
        "utility allowances $1,096, minimum benefit, each stamped 'Last Update Release # 25-4, Effective Date "
        "10/01/2025') carries the FY 2026 figures. The selected scope us-vt/manual/2026-07-21-vt-3squaresvt-manual "
        "does not hold this topic (the released 2026-05-27 scope holds an earlier edition at "
        "us-vt/manual/dcf/3squaresvt/3000-tables, so a release-keyed path is used). Plain client HTTP 200.",
        document_class="manual",
        documents=[Doc(
            "us-vt-dcf-3squaresvt-3100-tables-release-25-4",
            "3SquaresVT Program Manual, 3100 Tables (Release # 25-4, effective 10/01/2025)",
            "https://www.ahsnet.ahs.state.vt.us/Public/3sVT/assets/BRM/3000_Tables.htm",
            "us-vt/manual/dcf/3squaresvt/3100-tables-release-25-4", "2025-10-01", source_format="html",
            metadata={"document_subtype": "manual_tables", "document_number": "Release 25-4", "fiscal_year": "2026"},
        )],
    ),
    State(
        "us-va", "Virginia Department of Social Services (SNAP Manual Volume V)",
        "https://www.dss.virginia.gov/benefit/snap/", 12, "manual_transmittal_pointer",
        "Done by pointer: SNAP Manual Volume V Transmittal #36 (dated 2025-09-18) is a full reissue of the manual "
        "(200 pages) carrying the FY 2026 figures at the income limits, deductions and allotment tables. The "
        "selected scope us-va/manual/2026-07-21-va-snap-manual holds the full manual with the same FY 2026 figures "
        "(us-va/manual/dss/snap/full-manual prints 'October 1, 2025', $1,696, $1,305, $2,608). The transmittals "
        "page lists #25-#36. Nothing new to take.",
        status="done",
        pointer_scope={"jurisdiction": "us-va", "document_class": "manual", "version": "2026-07-21-va-snap-manual"},
    ),
]


# ----------------------------------------------------------------------------- SNAP charts
# Wave 5 (2026-09-15, docs/ingest-runs/2026-09-15-snap-wic.md): the publisher's standing
# per-standard eligibility charts, one scope per state, version
# 2026-09-15-snap-eligibility-charts. Massachusetts only in this pass: the DTA "Program
# eligibility charts and tables" list (21 PDFs, 14 of them SNAP; the other seven are TAFDC,
# EAEDC and SSP standards, not taken) is the family the 2026-09-14 transmittal run took the
# issuance tables from. Every PDF below was downloaded with browser impersonation (mass.gov
# answers HTTP 403 to the plain client) and its text layer read on 2026-09-15; the effective
# date printed on the chart is the expression date (two charts print none: the homeless
# deduction, whose $199 is the FY 2026 figure, and the undated Bay State CAP shelter
# standards, dated by the file's HTTP Last-Modified header).
_MA_CHARTS_INDEX = "https://www.mass.gov/lists/department-of-transitional-assistance-program-eligibility-charts-and-tables"


def _ma_chart(slug: str, title: str, doc_slug: str, expression_date: str, element: str, **metadata) -> Doc:
    return Doc(
        f"us-ma-dta-eligibility-chart-{slug}",
        title,
        _MA_CHARTS_INDEX,
        f"us-ma/guidance/dta/eligibility-charts/fy2026/{slug}",
        expression_date,
        download_url=f"https://www.mass.gov/doc/{doc_slug}/download",
        request=IMPERSONATE,
        metadata={"document_subtype": "eligibility_chart", "fiscal_year": "2026", "closure_element": element, **metadata},
    )


SNAP_CHARTS_STATES: list[State] = [
    State(
        "us-ma", "Massachusetts Department of Transitional Assistance (DTA)",
        _MA_CHARTS_INDEX, 21, "official_pdf_eligibility_charts",
        "The DTA 'Program eligibility charts and tables' list posts the SNAP standards 106 CMR 364-366 reference by "
        "cross-reference as one PDF per standard (income standards at 130%/165%/200%/100% FPL, maximum benefit "
        "levels, standard deduction, SUAs, maximum shelter and homeless deductions, minimum benefit, asset limit, "
        "Disaster SNAP standards, Bay State CAP shelter and SUA standards). The 2026-09-14 transmittal run took only "
        "the 1-10 person issuance tables from this list; the 14 SNAP charts are taken here (the 11-20 person issuance "
        "table, 101 pages, and the seven TAFDC/EAEDC/SSP charts are not). Every chart but the Bay State CAP shelter "
        "standards prints its effective date (10/01/2025; the 200% categorical-eligibility standards 02/01/2026).",
        document_class="guidance",
        documents=[
            _ma_chart("gross-income-standard-130",
                      "Maximum Gross Monthly Income Standard (130% of Poverty) as referenced at 106 CMR 364.950, "
                      "non-categorically eligible households (effective 10/1/2025)",
                      "maximum-gross-monthly-income-standard-130-of-poverty-as-referenced-at-106-cmr-364950-non-"
                      "categorically-eligible-households", "2025-10-01", "snap_s17", cmr_reference="106 CMR 364.950"),
            _ma_chart("categorical-eligibility-income-standards-200",
                      "Gross Monthly Categorical Eligibility Income Standards (200% of Poverty) as referenced at "
                      "106 CMR 364.976 (effective 02/01/2026)",
                      "gross-monthly-categorical-eligibility-income-standards-as-referenced-at-106-cmr-364976",
                      "2026-02-01", "snap_s02", cmr_reference="106 CMR 364.976"),
            _ma_chart("net-income-standards",
                      "Maximum Allowable Monthly Net Income Standards (100% of Poverty) as referenced at 106 CMR 364.970 "
                      "(effective 10/01/2025)",
                      "maximum-allowable-monthly-net-income-standards-as-referenced-at-106-cmr-364970-1", "2025-10-01",
                      "snap_s17", cmr_reference="106 CMR 364.970"),
            _ma_chart("elderly-disabled-special-circumstances-165",
                      "Standards for Special Circumstances Involving an Elderly and Disabled Individual (165% of Poverty) "
                      "as referenced at 106 CMR 364.975 (effective 10/01/2025)",
                      "standards-for-special-circumstances-involving-an-elderly-and-disabled-individual-as-referenced-at-"
                      "106-cmr-364975", "2025-10-01", "snap_s17", cmr_reference="106 CMR 364.975"),
            _ma_chart("maximum-benefit-levels",
                      "Maximum Benefit Levels as referenced at 106 CMR 364.600 (effective 10/01/2025)",
                      "maximum-benefit-levels-as-referenced-at-106-cmr-364600", "2025-10-01", "snap_s18",
                      cmr_reference="106 CMR 364.600"),
            _ma_chart("standard-deduction",
                      "Standard Deduction as referenced at 106 CMR 364.400 (effective 10/1/2025)",
                      "standard-deduction-as-referenced-at-106-cmr-364400-1", "2025-10-01", "snap_s15",
                      cmr_reference="106 CMR 364.400"),
            _ma_chart("standard-utility-allowances",
                      "Standard Utility Allowances (SUA) as referenced at 106 CMR 364.945 (effective 10/01/2025)",
                      "standard-utility-allowance-sua-as-referenced-at-106-cmr-364945", "2025-10-01", "snap_s04",
                      cmr_reference="106 CMR 364.945", also_closes="snap_s05, snap_s06"),
            _ma_chart("maximum-shelter-deduction",
                      "Maximum Shelter Deduction as referenced at 106 CMR 364.550 (effective 10/01/2025)",
                      "maximum-shelter-deduction-as-referenced-at-106-cmr-364550-1", "2025-10-01", "snap_s16",
                      cmr_reference="106 CMR 364.550"),
            _ma_chart("homeless-deduction",
                      "Homeless Deduction as referenced at 106 CMR 365.520(B)(3)(b)(2)",
                      "homeless-deduction-as-referenced-at-365520b3b2", "2025-10-01", "snap_s16",
                      cmr_reference="106 CMR 365.520(B)(3)(b)(2)",
                      expression_date_note="the chart prints no effective date; its $199 is the FY 2026 homeless "
                                           "shelter deduction (HTTP Last-Modified 2025-12-09)"),
            _ma_chart("minimum-benefit-level",
                      "Minimum Benefit Level for certain categorically-eligible one- and two-person households as "
                      "referenced at 106 CMR 365.180 (effective 10/01/2025)",
                      "minimum-benefit-level-for-certain-categorically-eligible-one-and-two-person-households-as-"
                      "referenced-at-106-cmr-365180-0", "2025-10-01", "snap_s19", cmr_reference="106 CMR 365.180"),
            _ma_chart("maximum-asset-limit",
                      "Maximum Asset Limit as referenced at 106 CMR 363.110 (effective 10/1/2025)",
                      "maximum-asset-limit-as-referenced-at-106-cmr-363110", "2025-10-01", "snap_s21",
                      cmr_reference="106 CMR 363.110"),
            _ma_chart("disaster-snap-income-and-asset-standard",
                      "Disaster SNAP Program Maximum Gross Monthly Income and Asset Standard as referenced at "
                      "106 CMR 364.946 (effective 10/01/2025)",
                      "disaster-snap-program-maximum-gross-monthly-income-and-asset-standard-as-referenced-at-106-cmr-"
                      "364946", "2025-10-01", "snap_s17", cmr_reference="106 CMR 364.946"),
            _ma_chart("bay-state-cap-shelter-standards",
                      "Bay State CAP High and Low Shelter Standards as referenced at 106 CMR 366.910(F)",
                      "bay-state-cap-high-and-low-shelter-as-referenced-at-106-cmr-366910f", "2024-09-27", "snap_s39",
                      cmr_reference="106 CMR 366.910(F)",
                      expression_date_note="the chart prints no effective date; dated by the file's HTTP "
                                           "Last-Modified header (2024-09-27)"),
            _ma_chart("bay-state-cap-standard-utility-allowance",
                      "Bay State CAP Standard Utility Allowance as referenced at 106 CMR 366.910 (effective 10/01/2025)",
                      "bay-state-cap-standard-utility-allowance-as-referenced-at-106-cmr-366910-2", "2025-10-01",
                      "snap_s39", cmr_reference="106 CMR 366.910"),
        ],
        index_families={
            "eligibility_charts_pdf": {"found": 21, "taken": 14},
            "snap_issuance_tables_pdf": {"found": 2, "taken": 1},
        },
    ),
]
