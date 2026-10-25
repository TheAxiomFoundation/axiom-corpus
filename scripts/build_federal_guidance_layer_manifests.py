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

Two 2026-09-15 wave-5 families (docs/coverage/needs-closure-2026-09-14, run note
docs/ingest-runs/2026-09-15-ssi-liheap-medicare.md) share the helpers:

* ``liheap-model-plan`` (``2026-09-15-liheap-model-plan``, guidance,
  LIHEAP-F-GUID-MODELPLAN): the FY 2027 (LIHEAP-AT-2026-4) and FY 2026
  (LIHEAP-AT-2025-04) Model Plan Application action transmittals from the ACF OCS
  action-transmittal index, each with its attachments (the OLDC cloning instructions,
  the Model Plan Reference Guide and the OMB 0970-0075 Model Plan template). acf.gov
  answered the plain client with an AWS WAF challenge (HTTP 202, empty body,
  ``x-amzn-waf-action: challenge``) on 2026-09-15 and served a chrome120 TLS
  fingerprint, so the documents are fetched with browser impersonation.
* ``ssi-cfr-416-appendix-k`` (``2026-09-15-title-20-part-416-appendix-k``, regulation,
  SSI-F-CFR416-APPK): the Appendix to Subpart K of 20 CFR part 416 (income excluded
  under other federal laws), a subpart-scoped appendix the eCFR adapter's
  ``--include-appendices`` rejects; taken as an official document from the eCFR
  renderer API (the same publisher API the adapter reads), the canonical eCFR page
  being the citation.

    uv run python scripts/build_federal_guidance_layer_manifests.py [--only snap,wic,medicare,liheap] [--skip-queue]
    uv run python scripts/build_federal_guidance_layer_manifests.py --only liheap-model-plan,ssi-cfr-416-appendix-k
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
    document_class: str = "guidance",
    source_as_of: str = SOURCE_AS_OF,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": "us",
        "document_class": document_class,
        "title": title,
        "source_url": source_url,
    }
    if download_url:
        out["download_url"] = download_url
    out.update(
        {
            "source_format": source_format,
            "source_as_of": source_as_of,
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


# ------------------------------------------------------------------- wave 5 (2026-09-15)
WAVE5_AS_OF = "2026-09-15"
WAVE5_RUN_NOTE = "docs/ingest-runs/2026-09-15-ssi-liheap-medicare.md"
MODEL_PLAN_VERSION = "2026-09-15-liheap-model-plan"
AT_INDEX = "https://acf.gov/ocs/resource/liheap-action-transmittals"
ACF_ACCESS_NOTE = (
    "acf.gov answered the plain corpus client with an AWS WAF challenge (HTTP 202, empty body, "
    "x-amzn-waf-action: challenge) on 2026-09-15, one probe each way; a chrome120 TLS fingerprint was served "
    "(fingerprint-only wall, no CAPTCHA or JavaScript challenge solved, TLS verification on), so the family is "
    "fetched with browser impersonation; the same host served the plain client on 2026-09-13"
)
# (at number, page slug, AT pdf, date, fiscal year, attachments [(slug, file, title, format, pages)])
MODEL_PLAN_TRANSMITTALS = [
    {
        "at": "2026-4", "fiscal_year": "2027", "date": "2026-06-10",
        "page": "https://acf.gov/ocs/policy-guidance/model-plan-application-liheap-funding-federal-fiscal-year-2027-fy27",
        "page_title": "Model Plan Application for LIHEAP Funding for Federal Fiscal Year 2027 (FY27)",
        "transmittal": ("COMM_AT_LIHEAP_Model-Plan_FY27_Final.pdf", 7),
        "attachments": [
            ("attachment-1-oldc-cloning-instructions", "Att-1_LIHEAP_AT_Model-Plan_FY27_CloningInstructions.pdf",
             "Attachment 1: OLDC instructions for cloning the FY26 Model Plan into the FY27 Model Plan", "pdf", 4),
            ("attachment-2-model-plan-reference-guide", "Att-2_LIHEAP_AT_Model-Plan_FY27_Att-2_ReferenceGuide.pdf",
             "Attachment 2: LIHEAP Model Plan Reference Guide (FY 2027)", "pdf", 41),
            ("attachment-3-model-plan-template", "Att-3_LIHEAP-Model-Plan-Template_508_5.8.26.pdf",
             "Attachment 3: LIHEAP Model Plan template (OMB Clearance No. 0970-0075, FY 2027)", "pdf", 44),
        ],
    },
    {
        "at": "2025-04", "fiscal_year": "2026", "date": "2025-04-02",
        "page": "https://acf.gov/ocs/policy-guidance/liheap-2025-04-model-plan-application-liheap-funding-federal-fiscal-year-2026",
        "page_title": "LIHEAP-AT-2025-04 Model Plan Application for LIHEAP Funding for Federal Fiscal Year 2026 (FY26)",
        "transmittal": ("COMM_LIHEAP_Model-Plan-AT_FY26_040225.pdf", 6),
        "attachments": [
            ("attachment-1-oldc-cloning-instructions", "COMM_LIHEAP_AT_Att-1_Cloning-Instructions_FY2026.docx",
             "Attachment 1: OLDC instructions for cloning the FY25 Model Plan into the FY26 Model Plan", "docx", None),
            ("attachment-model-plan-reference-guide", "COMM_LIHEAP-Model-Plan-Reference-Guide_FY26-Final.pdf",
             "LIHEAP Model Plan Reference Guide (FY 2026)", "pdf", 41),
            ("attachment-model-plan-template", "COMM_LIHEAP_Model-Plan-Template-draft_032025.docx",
             "LIHEAP Model Plan template (OMB Clearance No. 0970-0075, FY 2026, Word)", "docx", None),
        ],
    },
]


def build_liheap_model_plan() -> list[dict[str, Any]]:
    """The FY 2027 and FY 2026 Model Plan Application action transmittals and their attachments."""
    docs: list[dict[str, Any]] = []
    for at in MODEL_PLAN_TRANSMITTALS:
        group = f"us/guidance/acf/ocs/liheap-at/{at['at']}"
        common = {
            "source_authority": ACF,
            "program": "LIHEAP",
            "fiscal_year": at["fiscal_year"],
            "action_transmittal": f"LIHEAP-AT-{at['at']}",
            "action_transmittal_date": at["date"],
            "action_transmittal_page": at["page"],
            "index_url": AT_INDEX,
            "source_discovery_group": "us/guidance/acf/ocs",
            "closure_elements": ["LIHEAP-F-GUID-MODELPLAN"],
            "discovered_via": (
                "manual-review:liheap-agent-queue; needs-closure-2026-09-14 LIHEAP-F-GUID-MODELPLAN; ACF OCS LIHEAP "
                f"action transmittals index {AT_INDEX}"
            ),
            "access_note": ACF_ACCESS_NOTE,
        }
        docs.append(doc(
            f"us-acf-ocs-liheap-at-{at['at']}", f"LIHEAP-AT-{at['at']}: {at['page_title']} (page)",
            at["page"], group, at["date"], request=IMPERSONATE, source_as_of=WAVE5_AS_OF,
            metadata={**common, "document_subtype": "action_transmittal_page"},
        ))
        file_name, pages = at["transmittal"]
        docs.append(doc(
            f"us-acf-ocs-liheap-at-{at['at']}-transmittal",
            f"LIHEAP-AT-{at['at']}: Model Plan Application for LIHEAP Funding for Federal Fiscal Year {at['fiscal_year']} (transmittal)",
            at["page"], f"{group}/transmittal", at["date"], source_format="pdf",
            download_url=f"https://acf.gov/sites/default/files/documents/ocs/{file_name}",
            request=IMPERSONATE, source_as_of=WAVE5_AS_OF,
            metadata={**common, "document_subtype": "action_transmittal", "pdf_page_count": pages,
                      "expression_date_note": f"the transmittal's printed DATE line, {at['date']}"},
        ))
        for slug, file_name, title, fmt, pages in at["attachments"]:
            meta = {**common, "document_subtype": "action_transmittal_attachment",
                    "expression_date_note": f"the attachments carry the transmittal's date, {at['date']}"}
            if pages:
                meta["pdf_page_count"] = pages
            if "template" in slug:
                meta["omb_control_number"] = "0970-0075"
            docs.append(doc(
                f"us-acf-ocs-liheap-at-{at['at']}-{slug}", f"LIHEAP-AT-{at['at']} {title}",
                at["page"], f"{group}/{slug}", at["date"], source_format=fmt,
                download_url=f"https://acf.gov/sites/default/files/documents/ocs/{file_name}",
                request=IMPERSONATE, source_as_of=WAVE5_AS_OF, metadata=meta,
            ))
    return docs


APPENDIX_K_VERSION = "2026-09-15-title-20-part-416-appendix-k"
ECFR_APPENDIX_PAGE = (
    "https://www.ecfr.gov/current/title-20/chapter-III/part-416/appendix-Appendix%20to%20Subpart%20K%20of%20Part%20416"
)
ECFR_APPENDIX_RENDERER = (
    "https://www.ecfr.gov/api/renderer/v1/content/enhanced/2026-09-11/title-20"
    "?part=416&appendix=Appendix%20to%20Subpart%20K%20of%20Part%20416"
)


def build_ssi_cfr_416_appendix_k() -> list[dict[str, Any]]:
    """20 CFR part 416, Appendix to Subpart K (list of types of income excluded under the SSI
    program as provided by federal laws other than the Social Security Act)."""
    return [doc(
        "us-ecfr-title-20-part-416-appendix-subpart-k",
        "20 CFR Part 416, Appendix to Subpart K - List of Types of Income Excluded Under the SSI Program as Provided "
        "by Federal Laws Other Than the Social Security Act",
        ECFR_APPENDIX_PAGE, "us/regulation/20/416/subpart-K/appendix", "2026-09-09",
        download_url=ECFR_APPENDIX_RENDERER, document_class="regulation", source_as_of=WAVE5_AS_OF,
        extraction={"html_content_selector": "div.appendix"},
        metadata={
            "source_authority": "Office of the Federal Register, Electronic Code of Federal Regulations (eCFR)",
            "document_subtype": "cfr_appendix",
            "program": "SSI",
            "title": 20, "part": "416", "subpart": "K",
            "appendix_identifier": "Appendix to Subpart K of Part 416",
            "parent_citation_path": "us/regulation/20/416/subpart-K",
            "ecfr_point_in_time": "2026-09-11",
            "expression_date_note": (
                "title 20 latest_issue_date / latest_amended_on 2026-09-09 (eCFR titles.json read 2026-09-15), the "
                "expression date the sibling scope us/regulation/2026-09-11-title-20-part-416 carries; the appendix's "
                "own citation line is '45 FR 65547, Oct. 3, 1980, as amended at ... 75 FR 1273, Jan. 11, 2010' (last amendment 2010-01-11)"
            ),
            "download_note": (
                "the canonical eCFR page (source_url) redirects the corpus client to unblock.federalregister.gov; the "
                "eCFR renderer API (download_url, the publisher's own rendering of the 2026-09-11 point-in-time "
                "text) serves the appendix HTML; the div.appendix node is the document body"
            ),
            "adapter_note": (
                "extract-ecfr --include-appendices accepts part-scoped 'Appendix X to Part N' identifiers only and "
                "raises on this subpart-scoped one (run note 2026-09-11-federal-cfr-followon-parts); taken as an "
                "official document instead"
            ),
            "source_discovery_group": "us/regulation/ecfr",
            "closure_elements": ["SSI-F-CFR416-APPK"],
            "discovered_via": (
                "manual-review:ssi-agent-queue; needs-closure-2026-09-14 SSI-F-CFR416-APPK; eCFR structure "
                "title-20 2026-09-11 (part 416 > subpart K > appendix)"
            ),
        },
    )]


# ----------------------------------------------------------------------------------- queues
def write_manifest(name: str, version: str, docs: list[dict[str, Any]]) -> Path:
    path = ROOT / "manifests" / name
    path.write_text(yaml.safe_dump({"version": version, "documents": docs}, sort_keys=False, allow_unicode=True, width=120))
    return path


RUN_NOTES = {MODEL_PLAN_VERSION: WAVE5_RUN_NOTE, APPENDIX_K_VERSION: WAVE5_RUN_NOTE}


def scope_record(version: str, manifest: Path, docs: list[dict[str, Any]], elements: list[str], note: str) -> dict[str, Any]:
    return {
        "jurisdiction": "us", "document_class": docs[0]["document_class"], "version": version,
        "target_manifest": str(manifest.relative_to(ROOT)),
        "document_count": len(docs),
        "citation_paths": [d["citation_path"] for d in docs],
        "closure_elements": elements,
        "run_note": RUN_NOTES.get(version, RUN_NOTE),
        "notes": note,
    }


def update_queue(queue_name: str, key: str, record: dict[str, Any], note: str, *, row_name: str | None = None) -> dict[str, int]:
    """Attach the scope record to the queue's federal row: the row named ``row_name`` when
    given (the SSI queue keeps an eCFR row beside its POMS row), else the first ``us`` row.
    Every other row, including the later federal rows, is carried through untouched."""
    path = ROOT / "manifests" / queue_name
    queue = yaml.safe_load(path.read_text())
    federal_rows = [row for row in queue["states"] if row["jurisdiction"] == "us"]
    if row_name is not None:
        federal = next((row for row in federal_rows if row.get("name") == row_name), None)
        if federal is None:
            raise SystemExit(f"{queue_name}: no federal row named {row_name!r}")
    else:
        federal = federal_rows[0] if federal_rows else None
    if federal is None:
        federal = {"jurisdiction": "us", "name": "Federal", "queue_status": "agent_ready"}
        queue["states"].insert(0, federal)
    federal[key] = record
    if note not in str(federal.get("notes") or ""):
        federal["notes"] = f"{federal.get('notes') or ''} {note}".strip()
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
    "liheap-model-plan": ("us-liheap-model-plan-2026-09-15.yaml", MODEL_PLAN_VERSION, build_liheap_model_plan,
                          "liheap-agent-queue.yaml", "model_plan_scope", ["LIHEAP-F-GUID-MODELPLAN"],
                          "2026-09-15 wave-5 closure run (needs-closure-2026-09-14 LIHEAP-F-GUID-MODELPLAN): the FY 2027 "
                          "(LIHEAP-AT-2026-4, 2026-06-10) and FY 2026 (LIHEAP-AT-2025-04, 2025-04-02) Model Plan Application "
                          "action transmittals from the ACF OCS action-transmittal index, each with its OLDC cloning "
                          "instructions, Model Plan Reference Guide and OMB 0970-0075 Model Plan template (10 documents). "
                          "acf.gov fronted an AWS WAF challenge to the plain client on 2026-09-15 (HTTP 202, empty body) and "
                          "served a chrome120 TLS fingerprint; fetched with browser impersonation, TLS verification on."),
    "ssi-cfr-416-appendix-k": ("us-ecfr-title-20-part-416-appendix-k-2026-09-15.yaml", APPENDIX_K_VERSION,
                               build_ssi_cfr_416_appendix_k, "ssi-agent-queue.yaml", "appendix_subpart_k_scope",
                               ["SSI-F-CFR416-APPK"],
                               "2026-09-15 wave-5 closure run (needs-closure-2026-09-14 SSI-F-CFR416-APPK): the Appendix to "
                               "Subpart K of 20 CFR part 416 (types of income excluded under other federal laws), the one "
                               "part-416 node the 2026-09-11 eCFR scope skipped (extract-ecfr --include-appendices rejects "
                               "subpart-scoped appendix identifiers), taken as an official document from the eCFR renderer "
                               "API under us/regulation/20/416/subpart-K/appendix; the canonical eCFR page is walled to the "
                               "corpus client (unblock.federalregister.gov) and is the citation."),
}
QUEUE_ROW_NAMES = {"ssi-cfr-416-appendix-k": "Federal (20 CFR part 416, eCFR)"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated families (snap, wic, medicare, liheap, liheap-model-plan, ssi-cfr-416-appendix-k)")
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
            counts = update_queue(queue_name, key, scope_record(version, manifest, docs, elements, note), note,
                                  row_name=QUEUE_ROW_NAMES.get(family))
            print(f"  queue {queue_name}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
