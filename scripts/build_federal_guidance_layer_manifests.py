"""Build the 2026-09-13 federal guidance-layer manifests and record them on the
program agent queues (needs-driven closure check, docs/coverage/needs-closure-2026-09-11).

Four scopes, all jurisdiction ``us``, document_class ``guidance``:

* ``2026-09-13-snap-fns-guidance`` (snap.md snap_g09 to snap_g12, snap_g15): the FY 2026
  COLA memorandum (minimum benefit), the FY 2026 state standard utility allowance table,
  the FY 2026 quarterly ABAWD time-limit waiver status lists, the June 2026 BBCE state
  chart and the OBBB (P.L. 119-21) implementation memoranda and Q&As not yet in the corpus
  (the ABAWD-exceptions and alien-eligibility memoranda are already released scopes).
* ``2026-09-13-wic-fns-guidance-documents`` (wic.md wic_g04, wic_g07, wic_g08): the WIC
  nutrition risk criteria memorandum, the infant formula rebate and vendor cost-containment
  guidance, and the state-plan guidance memorandum.
* ``2026-09-13-medicare-annual-notices-2026`` (medicare.md MED-F-ANN-AB, MED-F-ANN-D,
  MED-F-ANN-LIS, and the Part D enrollment guidance that replaced Pub 100-18 chapter 3):
  the three CY 2026 Part A / Part B Federal Register notices, the CMS premiums fact sheet,
  the Part D bid information fact sheet and national average bid announcement, the CY 2026
  Rate Announcement (Part D defined standard benefit parameters), the CY 2026 LIS resource
  limits memorandum and the CY 2026 Medicare Advantage and Part D enrollment guidance.
* ``2026-09-13-liheap-annual-figures-2026`` (liheap.md LIHEAP-F-ANN-POVERTY, LIHEAP-F-ANN-SMI;
  medicare.md MED-F-ANN-POVERTY): the 2026 HHS poverty guidelines notice (91 FR 1797) and
  ASPE page, and ACF LIHEAP IM 2026-01 with its FPG and state median income tables.

Publishers: www.fna.usda.gov (the FNS site since the 2026-06-01 rename; memo pages embed
their PDF from the USDA guidance portal, which serves only browser-impersonated clients),
www.govinfo.gov for Federal Register notices, www.cms.gov, acf.gov and aspe.hhs.gov.
No mirror or archived copy is used.

    uv run python scripts/build_federal_guidance_layer_manifests.py [--only snap,wic,medicare,liheap] [--skip-queue]
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-09-13"
RUN_NOTE = "docs/ingest-runs/2026-09-13-federal-guidance-layer.md"
FNA = "https://www.fna.usda.gov"
PORTAL = "https://www.usda.gov/sites/default/files/guidance-documents/"
FNA_AUTHORITY = "USDA Food and Nutrition Service (Food and Nutrition Administration since 2026-06-01)"
GOVINFO_SUFFIX = " via U.S. Government Publishing Office"
IMPERSONATE = {"browser_impersonation": True, "browser_impersonation_direct": True}
PORTAL_NOTE = (
    "The FNA page carries only an embedded PDF from the USDA guidance portal "
    "(www.usda.gov/sites/default/files/guidance-documents/), which answers HTTP 403 to plain clients and "
    "serves the file to a browser-impersonated client; downloaded with browser impersonation."
)


def doc(
    source_id: str,
    title: str,
    source_url: str,
    citation_path: str,
    expression_date: str,
    *,
    source_format: str = "html",
    download_url: str | None = None,
    request: dict[str, Any] | None = None,
    extraction: dict[str, Any] | None = None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": "us",
        "document_class": "guidance",
        "title": title,
        "source_url": source_url,
    }
    if download_url:
        out["download_url"] = download_url
    out.update(
        {
            "source_format": source_format,
            "source_as_of": SOURCE_AS_OF,
            "expression_date": expression_date,
            "citation_path": citation_path,
        }
    )
    if request:
        out["request"] = dict(request)
    if extraction:
        out["extraction"] = dict(extraction)
    out["metadata"] = {"primary_source": True, **metadata}
    return out


def fr_notice(source_id: str, title: str, number: str, published: str, citation: str, path: str,
              authority: str, **meta: Any) -> dict[str, Any]:
    date = published
    return doc(
        source_id, title,
        f"https://www.govinfo.gov/content/pkg/FR-{date}/html/{number}.htm", path, published,
        metadata={
            "source_authority": authority + GOVINFO_SUFFIX,
            "document_subtype": "federal_register_notice",
            "federal_register_citation": citation,
            "federal_register_document_number": number,
            "federal_register_publication_date": published,
            "federal_register_pdf_url": f"https://www.govinfo.gov/content/pkg/FR-{date}/pdf/{number}.pdf",
            **meta,
        },
    )


# ------------------------------------------------------------------------------------ SNAP
SNAP_VERSION = "2026-09-13-snap-fns-guidance"
SNAP_GROUP = "us/guidance/usda/fns"
SNAP_INDEX = f"{FNA}/obbb"
SNAP_META = {
    "source_authority": FNA_AUTHORITY, "program": "SNAP", "source_discovery_group": SNAP_GROUP,
    "discovered_via": "manual-review:snap-completion-agent-queue; needs-closure-2026-09-11 snap_g09-snap_g15",
}
# (source_id suffix, FNA page path, portal file, memo date, title, subtype, closure elements, extra metadata)
SNAP_PORTAL_MEMOS = [
    ("snap-fy2026-cola-memo", "/snap/allotment/cola/fy26", "fns.snap-cola-fy26memo.pdf", "2025-10-01",
     "SNAP - Fiscal Year 2026 Cost-of-Living Adjustments (memorandum)", "cola_guidance", ["snap_g09"],
     {"fiscal_year": "2026", "effective_start": "2025-10-01", "effective_end": "2026-09-30",
      "expression_date_note": "the memorandum prints no date line; its COLAs are effective October 1, 2025, the "
                              "same convention as the released FY 2026 tables scope",
      "related_released_scope": "us/guidance/2026-05-01-snap-fy2026-cola-r2026-07-15-self-contained (the two-page "
                                "allotment and deduction tables; this document is the full memorandum with the "
                                "minimum benefit)"}),
    ("snap-obbb-implementation-memo", "/snap/obbb-implementation", "fns.snap-obbb-implementation.pdf", "2025-09-04",
     "SNAP Provisions of the One Big Beautiful Bill Act of 2025 - Information Memorandum",
     "information_memorandum", ["snap_g15"], {"public_law": "119-21"}),
    ("snap-obbb-abawd-waivers-implementation-memo", "/snap/obbb-abawd-waivers-implementation",
     "fns.snap-obbb-abawd-waivers-implementation.pdf", "2025-10-03",
     "SNAP Provisions of the One Big Beautiful Bill Act of 2025: ABAWD Waivers - Implementation Memorandum",
     "implementation_memorandum", ["snap_g11", "snap_g15"], {"public_law": "119-21", "statute_reference": "7 USC 2015(o)(4)"}),
    ("snap-obbb-qc-variance-exclusion-qas", "/snap/obbb-qas-variance-exclusion", "fns.snap-obbb-qas-variance-exclusion.pdf",
     "2025-11-14", "SNAP Questions and Answers on Quality Control Variance Exclusion (OBBB sections 10102 and 10103)",
     "questions_and_answers", ["snap_g15"], {"public_law": "119-21"}),
    ("snap-obbb-time-limit-changes-qas-1", "/obbb/snap/time-limit-changes-qas1", "fns.snap-obbbTimeLimitQAs1.pdf",
     "2026-06-11", "SNAP Provisions of the One Big Beautiful Bill Act of 2025: Time Limit Changes - Questions and Answers #1",
     "questions_and_answers", ["snap_g15"], {"public_law": "119-21", "statute_reference": "7 USC 2015(o)"}),
    ("snap-fy2026-sua-simplified-process-memo", "/snap/admin/sua-fy26", "fns.snap-simplifiedProcess-fy26sua-values.pdf",
     "2025-08-15", "SNAP - Simplified Process for Fiscal Year 2026 Standard Utility Allowance (SUA) Values",
     "implementation_memorandum", ["snap_g10", "snap_g15"], {"public_law": "119-21", "fiscal_year": "2026"}),
    ("snap-obbb-energy-assistance-payments-memo", "/snap/admin/energy-assistance-payments",
     "fns.SNAP-admin-energy-assistance-payments.pdf", "2025-08-29",
     "SNAP Implementation of the One Big Beautiful Bill Act of 2025 - Treatment of Energy Assistance Payments",
     "implementation_memorandum", ["snap_g15"], {"public_law": "119-21", "statute_reference": "7 USC 2014(e)(6)(C)"}),
    ("snap-obbb-internet-energy-assistance-qas-1", "/obbb/snap/restrictions-internet-expenses-energy-assist-payments-qas1",
     "fns.snap-obbb-restrictionsInternetExpEnergyAssistPayments-QAs1.pdf", "2026-05-08",
     "SNAP Provisions of the One Big Beautiful Bill Act of 2025 - Restrictions on Internet Expenses and Treatment of "
     "Energy Assistance Payments - Questions and Answers #1", "questions_and_answers", ["snap_g15"],
     {"public_law": "119-21", "statute_reference": "7 USC 2014(e)(6)"}),
    ("snap-obbb-admin-cost-sharing-qas", "/obbb/snap/admin-cost-sharing-qas",
     "fns.snap-obbb-section10106-adminCostSharing-qas.pdf", "2026-05-21",
     "SNAP Provisions of the One Big Beautiful Bill Act of 2025, Section 10106 Administrative Cost Sharing: Questions and Answers",
     "questions_and_answers", ["snap_g15"], {"public_law": "119-21", "statute_reference": "7 USC 2025(a)"}),
    ("snap-obbb-alien-eligibility-qas-1", "/snap/obbb-alien-eligibility-qas1", "fns.snap-obbb-alien-eligibility-qas1.pdf",
     "2025-12-09", "SNAP Provisions of the One Big Beautiful Bill Act of 2025 - Alien SNAP Eligibility - Questions and Answers #1",
     "questions_and_answers", ["snap_g14", "snap_g15"], {"public_law": "119-21", "statute_reference": "7 USC 2015(f)"}),
]
SNAP_FNA_FILES = [
    # (source_id, page path, file path on www.fna.usda.gov, format, expression, title, subtype, elements, metadata)
    ("snap-fy2026-standard-utility-allowances", "/snap/eligibility/deduction/standard-utility-allowances",
     "/sites/default/files/resource-files/2026-05-21-SUA-Table-FY26.xlsx", "xlsx", "2025-10-01",
     "SNAP FY 2026 Standard Utility Allowances (SUA) by State (table updated August 2026)", "sua_state_table",
     ["snap_g10"], {"fiscal_year": "2026", "effective_start": "2025-10-01", "effective_end": "2026-09-30",
                    "table_updated": "2026-08 (page label 'FY 2026 SUAs - Updated August 2026'; page updated 2026-08-18)",
                    "expression_date_note": "the table's own header prints the effective period October 1, 2025 to "
                                            "September 30, 2026; the FNA page prints no release date for the update"}),
    ("snap-abawd-waiver-status-fy2026-q1", "/snap/waivers/timelimit",
     "/sites/default/files/resource-files/FY26-Quarter-1-ABAWD-Waiver-Status.pdf", "pdf", "2025-10-01",
     "SNAP: Status of State ABAWD Time Limit Waivers, Fiscal Year 2026 - 1st Quarter", "abawd_waiver_status",
     ["snap_g11"], {"fiscal_year": "2026", "quarter": "1", "effective_start": "2025-10-01"}),
    ("snap-abawd-waiver-status-fy2026-q2", "/snap/waivers/timelimit",
     "/sites/default/files/resource-files/FY26-Quarter-2-ABAWD-Waiver-Status.pdf", "pdf", "2026-01-01",
     "SNAP: Status of State ABAWD Time Limit Waivers, Fiscal Year 2026 - 2nd Quarter", "abawd_waiver_status",
     ["snap_g11"], {"fiscal_year": "2026", "quarter": "2", "effective_start": "2026-01-01"}),
    ("snap-abawd-waiver-status-fy2026-q3", "/snap/waivers/timelimit",
     "/sites/default/files/resource-files/FY26-Quarter-3-ABAWD-Waiver-Status.pdf", "pdf", "2026-03-01",
     "SNAP: Status of State ABAWD Time Limit Waivers, Fiscal Year 2026 - 3rd Quarter", "abawd_waiver_status",
     ["snap_g11"], {"fiscal_year": "2026", "quarter": "3", "effective_start": "2026-04-01",
                    "expression_date_note": "the list prints March 1, 2026 as its date"}),
    ("snap-bbce-state-chart-2026-06", "/snap/broad-based-categorical-eligibility",
     "/sites/default/files/resource-files/BBCE-States-Chart-June2026.pdf", "pdf", "2026-06-01",
     "SNAP Broad-Based Categorical Eligibility (BBCE) States Chart, June 2026", "bbce_state_chart",
     ["snap_g12"], {"chart_edition": "June 2026", "expression_date_note": "the chart carries its month only"}),
]


def build_snap() -> list[dict[str, Any]]:
    docs = []
    for sid, page, fn, date, title, subtype, elements, meta in SNAP_PORTAL_MEMOS:
        docs.append(doc(
            sid, title, FNA + page, f"{SNAP_GROUP}/{sid}", date, source_format="pdf",
            download_url=PORTAL + fn, request=IMPERSONATE,
            metadata={**SNAP_META, "document_subtype": subtype, "memo_date": date, "closure_elements": elements,
                      "index_url": SNAP_INDEX, "access_note": PORTAL_NOTE, **meta},
        ))
    for sid, page, path, fmt, date, title, subtype, elements, meta in SNAP_FNA_FILES:
        docs.append(doc(
            sid, title, FNA + page, f"{SNAP_GROUP}/{sid}", date, source_format=fmt, download_url=FNA + path,
            # www.fna.usda.gov served the files to a plain client on 2026-09-13; the option only
            # enables the extractor's browser fallback if the Akamai front door starts rejecting it.
            request={"browser_impersonation": True},
            metadata={**SNAP_META, "document_subtype": subtype, "closure_elements": elements, "index_url": FNA + page, **meta},
        ))
    return docs


# ------------------------------------------------------------------------------------- WIC
WIC_VERSION = "2026-09-13-wic-fns-guidance-documents"
WIC_GROUP = "us/guidance/fns/wic"
WIC_INDEX = f"{FNA}/resources?f[0]=program:32&f[1]=resource_type:401"
WIC_META = {
    "source_authority": FNA_AUTHORITY, "program": "WIC", "source_discovery_group": WIC_GROUP,
    "index_url": WIC_INDEX,
    "discovered_via": "manual-review:wic-agent-queue; needs-closure-2026-09-11 wic_g04/wic_g07/wic_g08; FNA resource browser WIC/Guidance Documents",
    "access_note": PORTAL_NOTE,
}
WIC_DOCS = [
    # (slug, page path, portal file, date, title, subtype, memo number, elements, extraction)
    ("nutrition-risk-criteria", "/wic/nutrition-risk-criteria", "fns.wic-pm2011-5-nutritionriskCriteria.pdf", "2011-05-20",
     "WIC Policy Memorandum #2011-5: WIC Nutrition Risk Criteria", "policy_memorandum", "2011-5", ["wic_g04"], None),
    ("infant-formula-rebate-solicitations-bidding", "/wic/infant-formula-rebate-solicitations-bidding",
     "fns.wic-infantFormRebSolic-Bidding.pdf", "2019-10-07",
     "WIC Infant Formula Rebate Solicitations - Bidding on Single Milk- and Soy-Based Infant Formula (informational memorandum)",
     "informational_memorandum", None, ["wic_g07"], None),
    ("evaluation-criteria-infant-formula-rebate-contracts", "/wic/evaluation-criteria-infant-formula-rebate-contracts",
     "fns.wic-pm99-3-EvaluationCriteria-InfantFormulaRebateContracts.pdf", "1998-10-14",
     "WIC Policy Memorandum #1999-3: Evaluation Criteria for Infant Formula Rebate Contracts", "policy_memorandum",
     "1999-3", ["wic_g07"], {"ocr": True, "force_ocr": True, "ocr_dpi": 300}),
    ("interim-guidance-vendor-cost-containment", "/wic/interim-guidance-vendor-cost-containment",
     "fns.wic-interimGuidanceVendorCostContainment.pdf", "2006-06-08",
     "Interim Guidance on WIC Vendor Cost Containment (June 2006)", "guidance_document", None, ["wic_g07"], None),
    ("vendor-cost-containment-interim-rule-clarification", "/wic/vendor-cost-containment-interim-rule-clarification",
     "fns.wic-pm2006-6-vendorCostContInterimRuleClarif.pdf", "2006-03-15",
     "WIC Policy Memorandum #2006-6: Vendor Cost Containment Interim Rule Clarification", "policy_memorandum",
     "2006-6", ["wic_g07"], None),
    ("wpm-2024-3-implementing-abfa-requirements-state-plans", "/wic/wpm-2024-3-implementing-abfa-requirements",
     "fns.WPM2024-3-ImplementingABFAStatePlans.pdf", "2024-02-16",
     "WIC Policy Memorandum #2024-3: Implementing ABFA Requirements in WIC State Plans", "policy_memorandum",
     "2024-3", ["wic_g08"], None),
]


def build_wic() -> list[dict[str, Any]]:
    docs = []
    for slug, page, fn, date, title, subtype, memo, elements, extraction in WIC_DOCS:
        meta = {**WIC_META, "document_subtype": subtype, "memo_date": date, "closure_elements": elements}
        if memo:
            meta["memo_number"] = memo
        if extraction and extraction.get("force_ocr"):
            meta["ocr_note"] = ("scanned memorandum whose embedded text layer is garbled (the 1998 header reads "
                                "'GCl \\4 1918'); every page is re-read with OCR")
        docs.append(doc(
            f"us-fns-wic-guidance-{slug}", title, FNA + page, f"{WIC_GROUP}/guidance/{slug}", date,
            source_format="pdf", download_url=PORTAL + fn, request=IMPERSONATE, extraction=extraction, metadata=meta,
        ))
    return docs


# -------------------------------------------------------------------------------- Medicare
MED_VERSION = "2026-09-13-medicare-annual-notices-2026"
MED_GROUP = "us/guidance/cms"
CMS = "Centers for Medicare & Medicaid Services"
MED_META = {
    "program": "MEDICARE", "source_discovery_group": MED_GROUP, "calendar_year": "2026",
    "discovered_via": "manual-review:medicare-agent-queue; needs-closure-2026-09-11 MED-F-ANN-AB/MED-F-ANN-D/MED-F-ANN-LIS/MED-F-IOM-100-18",
}


def build_medicare() -> list[dict[str, Any]]:
    docs = [
        fr_notice("us-cms-cy2026-part-a-premiums-notice",
                  "Medicare Program; CY 2026 Part A Premiums for the Uninsured Aged and for Certain Disabled Individuals "
                  "Who Have Exhausted Other Entitlement (90 FR 52060)",
                  "2025-20250", "2025-11-19", "90 FR 52060", f"{MED_GROUP}/part-a-premiums/2026/federal-register", CMS,
                  **MED_META, closure_elements=["MED-F-ANN-AB"], determination="part_a_premiums"),
        fr_notice("us-cms-cy2026-part-a-deductible-coinsurance-notice",
                  "Medicare Program; CY 2026 Inpatient Hospital Deductible and Hospital and Extended Care Services "
                  "Coinsurance Amounts (90 FR 52075)",
                  "2025-20249", "2025-11-19", "90 FR 52075", f"{MED_GROUP}/part-a-deductible-coinsurance/2026/federal-register",
                  CMS, **MED_META, closure_elements=["MED-F-ANN-AB"], determination="part_a_deductible_coinsurance"),
        fr_notice("us-cms-cy2026-part-b-premium-deductible-notice",
                  "Medicare Program; Medicare Part B Monthly Actuarial Rates, Premium Rates, and Annual Deductible "
                  "Beginning January 1, 2026 (90 FR 52063)",
                  "2025-20251", "2025-11-19", "90 FR 52063", f"{MED_GROUP}/part-b-premium-deductible/2026/federal-register",
                  CMS, **MED_META, closure_elements=["MED-F-ANN-AB"], determination="part_b_premium_deductible_irmaa"),
        doc("us-cms-2026-parts-a-b-premiums-deductibles-fact-sheet",
            "2026 Medicare Parts A & B Premiums and Deductibles (CMS fact sheet, November 14, 2025)",
            "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-deductibles",
            f"{MED_GROUP}/parts-a-b-premiums-deductibles/2026/fact-sheet", "2025-11-14",
            metadata={"source_authority": CMS, "document_subtype": "fact_sheet", **MED_META,
                      "closure_elements": ["MED-F-ANN-AB"], "determination": "part_a_b_premiums_deductibles_irmaa"}),
        doc("us-cms-2026-part-d-bid-information-fact-sheet",
            "2026 Medicare Part D Bid Information and Part D Premium Stabilization Demonstration Parameters "
            "(CMS fact sheet, July 28, 2025)",
            "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-part-d-bid-information-and-part-d-premium-stabilization-demonstration-parameters",
            f"{MED_GROUP}/part-d-bid-information/2026/fact-sheet", "2025-07-28",
            metadata={"source_authority": CMS, "document_subtype": "fact_sheet", **MED_META,
                      "closure_elements": ["MED-F-ANN-D"], "determination": "part_d_base_beneficiary_premium"}),
        doc("us-cms-2026-part-d-national-average-bid-announcement",
            "Annual Release of Part D National Average Bid Amount and Other Part C & D Bid Information for CY 2026 "
            "(CMS memorandum, July 28, 2025)",
            "https://www.cms.gov/files/document/july-28-2025-parts-c-d-announcement.pdf",
            f"{MED_GROUP}/part-d-national-average-bid-amount/2026", "2025-07-28", source_format="pdf",
            metadata={"source_authority": CMS, "document_subtype": "annual_announcement", **MED_META,
                      "closure_elements": ["MED-F-ANN-D"],
                      "determination": "part_d_national_average_bid_base_premium_irmaa",
                      "index_url": "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-part-d-bid-information-and-part-d-premium-stabilization-demonstration-parameters"}),
        doc("us-cms-2026-ma-part-d-rate-announcement",
            "Announcement of Calendar Year (CY) 2026 Medicare Advantage (MA) Capitation Rates and Part C and Part D "
            "Payment Policies (April 7, 2025)",
            "https://www.cms.gov/files/document/2026-announcement.pdf",
            f"{MED_GROUP}/ma-part-d-rate-announcement/2026", "2025-04-07", source_format="pdf",
            metadata={"source_authority": CMS, "document_subtype": "annual_announcement", **MED_META,
                      "closure_elements": ["MED-F-ANN-D"],
                      "determination": "part_d_defined_standard_benefit_parameters (Attachment V) and Part C rates",
                      "index_url": "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-advantage-part-d-rate-announcement"}),
        doc("us-cms-cy2026-lis-resource-limits-memo",
            "Calendar Year (CY) 2026 Resource and Cost-Sharing Limits for Low-Income Subsidy (LIS) (CMS memorandum, "
            "October 31, 2025)",
            "https://www.cms.gov/files/document/cy2026-lis-resource-limits-memo.pdf",
            f"{MED_GROUP}/part-d-lis-resource-limits/2026", "2025-10-31", source_format="pdf",
            metadata={"source_authority": CMS, "document_subtype": "annual_memorandum", **MED_META,
                      "closure_elements": ["MED-F-ANN-LIS"], "determination": "part_d_lis_resource_limits_cost_sharing"}),
        doc("us-cms-cy2026-c-d-enrollment-disenrollment-guidance",
            "Medicare Advantage and Part D Enrollment and Disenrollment Guidance (CY 2026; updated August 8, 2024 and "
            "August 1, 2025)",
            "https://www.cms.gov/medicare/enrollment-renewal/part-d-enrollment-eligibility",
            f"{MED_GROUP}/part-c-d-enrollment-disenrollment-guidance/2026", "2025-08-01", source_format="pdf",
            download_url="https://www.cms.gov/files/document/cy-2026-cd-enrollment-and-disenrollment-guidance.pdf",
            metadata={"source_authority": CMS, "document_subtype": "enrollment_guidance", **MED_META,
                      "closure_elements": ["MED-F-IOM-100-18"],
                      "provenance_note": "Pub 100-18 chapter 3 (Eligibility, Enrollment and Disenrollment) is no longer "
                                         "posted as a manual chapter; the CMS Prescription Drug Benefit Manual page points "
                                         "to this standalone guidance, which CMS reissues each contract year."}),
    ]
    return docs


# ---------------------------------------------------------------------------------- LIHEAP
LIHEAP_VERSION = "2026-09-13-liheap-annual-figures-2026"
ACF = "HHS Administration for Children and Families, Office of Community Services"
ASPE = "HHS Office of the Assistant Secretary for Planning and Evaluation"
IM_PAGE = "https://acf.gov/ocs/policy-guidance/liheap-im2026-01-federal-poverty-guidelines-fpg-and-state-median-income-smi"
IM_INDEX = "https://acf.gov/ocs/policy-guidance/liheap-information-memoranda"
LIHEAP_META = {
    "program": "LIHEAP", "fiscal_year": "2026",
    "discovered_via": "manual-review:liheap-agent-queue; needs-closure-2026-09-11 LIHEAP-F-ANN-POVERTY/LIHEAP-F-ANN-SMI",
}


def build_liheap() -> list[dict[str, Any]]:
    pg_group = "us/guidance/hhs/aspe"
    im_group = "us/guidance/acf/ocs"
    docs = [
        fr_notice("us-hhs-2026-poverty-guidelines-notice",
                  "Annual Update of the HHS Poverty Guidelines (91 FR 1797, January 15, 2026)",
                  "2026-00755", "2026-01-15", "91 FR 1797", f"{pg_group}/poverty-guidelines/2026/federal-register",
                  "U.S. Department of Health and Human Services", program="federal_poverty_guidelines", calendar_year="2026",
                  source_discovery_group=pg_group, closure_elements=["LIHEAP-F-ANN-POVERTY", "MED-F-ANN-POVERTY"],
                  discovered_via=LIHEAP_META["discovered_via"]),
        doc("us-hhs-aspe-poverty-guidelines-2026",
            "HHS Poverty Guidelines for 2026 (ASPE poverty guidelines page)",
            "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
            f"{pg_group}/poverty-guidelines/2026", "2026-01-15",
            metadata={"source_authority": ASPE, "document_subtype": "poverty_guidelines", "program": "federal_poverty_guidelines",
                      "calendar_year": "2026", "source_discovery_group": pg_group,
                      "closure_elements": ["LIHEAP-F-ANN-POVERTY", "MED-F-ANN-POVERTY"],
                      "discovered_via": LIHEAP_META["discovered_via"],
                      "expression_date_note": "the page carries the 2026 guidelines published in the Federal Register on "
                                              "2026-01-15; the undated path us/guidance/hhs/aspe/poverty-guidelines in "
                                              "manifests/us-hhs-poverty-guidelines.yaml was never extracted"}),
        doc("us-acf-ocs-liheap-im-2026-01",
            "LIHEAP IM 2026-01: Federal Poverty Guidelines (FPG) and State Median Income (SMI) Estimates for LIHEAP Income "
            "Eligibility, Optional Use in FY 2026 and Mandatory Use in FY 2027 (page)",
            IM_PAGE, f"{im_group}/liheap-im/2026-01", "2026-04-24",
            metadata={"source_authority": ACF, "document_subtype": "information_memorandum_page", **LIHEAP_META,
                      "source_discovery_group": im_group, "index_url": IM_INDEX,
                      "closure_elements": ["LIHEAP-F-ANN-SMI", "LIHEAP-F-ANN-POVERTY"]}),
        doc("us-acf-ocs-liheap-im-2026-01-memorandum",
            "LIHEAP IM 2026-01 (ACF-OCS-LIHEAP-IM-2026-01): Federal Poverty Guidelines and State Median Income Estimates "
            "for LIHEAP Income Eligibility (memorandum)",
            IM_PAGE, f"{im_group}/liheap-im/2026-01/memorandum", "2026-04-24", source_format="pdf",
            download_url="https://acf.gov/sites/default/files/documents/ocs/ACF-OCS-LIHEAP-IM-2026-01.pdf",
            metadata={"source_authority": ACF, "document_subtype": "information_memorandum", **LIHEAP_META,
                      "source_discovery_group": im_group, "index_url": IM_INDEX,
                      "closure_elements": ["LIHEAP-F-ANN-SMI", "LIHEAP-F-ANN-POVERTY"]}),
        doc("us-acf-ocs-liheap-im-2026-01-att4-smi-table",
            "LIHEAP IM 2026-01 Attachment 4: State Median Income (SMI) by Household Size for Mandatory Use in FY 2027 "
            "(optional use in FY 2026)",
            IM_PAGE, f"{im_group}/liheap-im/2026-01/attachment-4-smi-table", "2026-04-24", source_format="pdf",
            download_url="https://acf.gov/sites/default/files/documents/ocs/COMM_LIHEAP_Att4SMITable_States_FY2027.pdf",
            metadata={"source_authority": ACF, "document_subtype": "state_median_income_table", **LIHEAP_META,
                      "source_discovery_group": im_group, "index_url": IM_INDEX, "closure_elements": ["LIHEAP-F-ANN-SMI"]}),
        doc("us-acf-ocs-liheap-im-2026-01-att2-fpg-tables",
            "LIHEAP IM 2026-01 Attachment 2: 100, 110 and 150 percent of the 2026 Federal Poverty Guidelines for the 50 "
            "States and the District of Columbia",
            IM_PAGE, f"{im_group}/liheap-im/2026-01/attachment-2-fpg-tables", "2026-04-24", source_format="pdf",
            download_url="https://acf.gov/sites/default/files/documents/ocs/COMM_LIHEAP_Att2FPGTables_States_FY2027.pdf",
            metadata={"source_authority": ACF, "document_subtype": "poverty_guideline_tables", **LIHEAP_META,
                      "source_discovery_group": im_group, "index_url": IM_INDEX, "closure_elements": ["LIHEAP-F-ANN-POVERTY"]}),
    ]
    return docs


# ----------------------------------------------------------------------------------- queues
def write_manifest(name: str, version: str, docs: list[dict[str, Any]]) -> Path:
    path = ROOT / "manifests" / name
    path.write_text(yaml.safe_dump({"version": version, "documents": docs}, sort_keys=False, allow_unicode=True, width=120))
    return path


def scope_record(version: str, manifest: Path, docs: list[dict[str, Any]], elements: list[str], note: str) -> dict[str, Any]:
    return {
        "jurisdiction": "us", "document_class": "guidance", "version": version,
        "target_manifest": str(manifest.relative_to(ROOT)),
        "document_count": len(docs),
        "citation_paths": [d["citation_path"] for d in docs],
        "closure_elements": elements,
        "run_note": RUN_NOTE,
        "notes": note,
    }


def update_queue(queue_name: str, key: str, record: dict[str, Any], note: str) -> dict[str, int]:
    path = ROOT / "manifests" / queue_name
    queue = yaml.safe_load(path.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    federal = rows.get("us")
    if federal is None:
        federal = {"jurisdiction": "us", "name": "Federal", "queue_status": "agent_ready"}
        rows["us"] = federal
    federal[key] = record
    if note not in str(federal.get("notes") or ""):
        federal["notes"] = f"{federal.get('notes') or ''} {note}".strip()
    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for row in queue["states"]:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


FAMILIES = {
    "snap": ("us-snap-fns-guidance-2026-09-13.yaml", SNAP_VERSION, build_snap, "snap-completion-agent-queue.yaml",
             "federal_guidance_scope", ["snap_g09", "snap_g10", "snap_g11", "snap_g12", "snap_g15"],
             "2026-09-13 closure run (needs-closure-2026-09-11 snap_g09-g12, g15): the FY 2026 COLA memorandum, the FY 2026 "
             "state SUA table, the FY 2026 quarterly ABAWD waiver status lists, the June 2026 BBCE chart and the OBBB "
             "implementation memoranda and Q&As not yet held, all from www.fna.usda.gov (the publisher's front door answered "
             "HTTP 200 on 2026-09-13; memo PDFs from the USDA guidance portal with browser impersonation). The State Options "
             "Report (snap_g16) stays out under the forbidden-sources policy."),
    "wic": ("us-wic-fns-guidance-documents-2026-09-13.yaml", WIC_VERSION, build_wic, "wic-agent-queue.yaml",
            "guidance_documents_scope", ["wic_g04", "wic_g07", "wic_g08"],
            "2026-09-13 closure run (needs-closure-2026-09-11 wic_g04/g07/g08): nutrition risk criteria (WPM 2011-5), infant "
            "formula rebate and vendor cost-containment guidance, and the ABFA state-plan memorandum from the FNA resource "
            "browser's WIC Guidance Documents family (195 documents). The pre-FY 2025 policy memoranda (wic_g05) and the "
            "Federal Register notices family (wic_g06) remain not taken."),
    "medicare": ("us-cms-annual-notices-2026.yaml", MED_VERSION, build_medicare, "medicare-agent-queue.yaml",
                 "annual_notices_2026", ["MED-F-ANN-AB", "MED-F-ANN-D", "MED-F-ANN-LIS", "MED-F-IOM-100-18"],
                 "2026-09-13 closure run (needs-closure-2026-09-11 MED-F-ANN-*): the CY 2026 Part A premium, Part A deductible "
                 "and Part B premium Federal Register notices (govinfo), the CMS premiums fact sheet, the Part D bid "
                 "information fact sheet and national average bid announcement, the CY 2026 Rate Announcement (Part D "
                 "defined standard benefit parameters), the CY 2026 LIS resource limits memorandum and the CY 2026 MA/Part D "
                 "enrollment and disenrollment guidance (the successor of Pub 100-18 chapter 3)."),
    "liheap": ("us-liheap-annual-figures-2026.yaml", LIHEAP_VERSION, build_liheap, "liheap-agent-queue.yaml",
               "annual_figures_scope", ["LIHEAP-F-ANN-POVERTY", "LIHEAP-F-ANN-SMI", "MED-F-ANN-POVERTY"],
               "2026-09-13 closure run (needs-closure-2026-09-11 LIHEAP-F-ANN-POVERTY/SMI): the 2026 HHS poverty guidelines "
               "notice (91 FR 1797) and ASPE page, and ACF LIHEAP IM 2026-01 with its FPG and SMI tables (acf.gov). The "
               "statute, 45 CFR 96 subpart H and the model plan (LIHEAP-F-GUID-MODELPLAN) are not part of this scope."),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated families (snap, wic, medicare, liheap)")
    parser.add_argument("--skip-queue", action="store_true")
    args = parser.parse_args()
    selected = set(args.only.split(",")) if args.only else set(FAMILIES)
    for family, (manifest_name, version, builder, queue_name, key, elements, note) in FAMILIES.items():
        if family not in selected:
            continue
        docs = builder()
        paths = [d["citation_path"] for d in docs]
        assert len(paths) == len(set(paths)), f"{family}: duplicate citation paths"
        manifest = write_manifest(manifest_name, version, docs)
        print(f"{family}: wrote {manifest.relative_to(ROOT)} ({len(docs)} documents, version {version})")
        if not args.skip_queue:
            counts = update_queue(queue_name, key, scope_record(version, manifest, docs, elements, note), note)
            print(f"  queue {queue_name}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
