"""Build the tax-year-2025 individual income tax form/instruction manifests (federal
IRS core plus the batch-1, batch-2 and batch-3 retry states), the state guidance manifests for
jurisdictions that publish no TY2025 resident return (NH, WA), and the 2026 IRS
inflation-adjustment guidance manifest, then update ``manifests/tax-agent-queue.yaml``.

Every URL below was confirmed by the agent on 2026-09-10 from the publisher's own
forms index (recorded per jurisdiction as ``index_url``); the PolicyEngine lead
list in the queue was discovery only and is never a source. The tables are static
on purpose: state forms indexes differ in shape (JS data tables, node pages,
media downloads) and a reviewer should be able to read the exact confirmed set.

    uv run python scripts/build_tax_forms_manifests.py [--verify]

``--verify`` issues a HEAD/GET probe for every download URL with the corpus
user agent and reports non-PDF/HTML responses without changing any file.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CORPUS_BASE = Path(os.environ.get("AXIOM_CORPUS_BASE", str(ROOT / "data" / "corpus")))
SOURCE_AS_OF = "2026-09-10"
TAX_YEAR = "2025"
TY_EXPRESSION_DATE = "2025-01-01"  # tax-year-2025 returns cover calendar year 2025
USER_AGENT = (
    "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) "
    "https://github.com/TheAxiomFoundation/axiom-corpus"
)

FEDERAL_FORMS_VERSION = "2026-09-10-tax-irs-forms-ty2025"
FEDERAL_GUIDANCE_VERSION = "2026-09-10-tax-irs-guidance"
STATE_FORMS_VERSION = "2026-09-10-tax-state-forms-ty2025"
STATE_GUIDANCE_VERSION = "2026-09-10-tax-state-guidance-ty2025"
# Territories pass (2026-09-11): PR, GU and MP publish their own TY2025 returns; VI's index links the
# IRS Form 1040 (done by pointer); AS posts Form 390 only as an Excel workbook (needs_review).
TERRITORY_FORMS_VERSION = "2026-09-11-tax-territory-forms-ty2025"
TERRITORY_SOURCE_AS_OF = "2026-09-11"
# Batch-3 retry of the publisher-blocked CO/IN/UT hosts from a US network exit.
US_NETWORK_RETRY = "2026-09-10T21:35:30Z"

IRS_FORMS_INDEX = "https://www.irs.gov/forms-instructions"
IRS_1040_INDEX = "https://www.irs.gov/forms-pubs/about-form-1040"
IRS_SCHEDULES_INDEX = "https://www.irs.gov/forms-pubs/schedules-for-form-1040"
IRS_IRB_INDEX = "https://www.irs.gov/internal-revenue-bulletins"

SINGLE_BLOCK = {"segmentation": "single_block"}
# Publisher edges that reject non-browser TLS fingerprints (plain requests and a
# browser user agent both get HTTP 403). The extractor's curl_cffi path in
# documents.py honours these keys and still verifies TLS.
BROWSER_IMPERSONATION = {
    "browser_user_agent": True,
    "browser_impersonation": True,
    "browser_impersonation_direct": True,
}
# dor.wa.gov Drupal pages: the page body is the one `.field--name-body` under <main>.
WA_DOR_HTML = {"html_content_selector": "main .field--name-body"}
NM_PIT_FORMS_INDEX = "https://www.tax.newmexico.gov/individuals/online-services-overview/personal-income-tax-forms/"
NM_REALFILE = "https://klvg4oyd4j.execute-api.us-west-2.amazonaws.com/prod/PublicFiles/34821a9573ca43e7b06dfad20f5183fd"
# irs.gov instruction/publication HTML: the `.book` container holds the headed
# body; the default HTML extractor emits one block per heading.
IRS_HTML = {"html_content_selector": ".book"}


def _irs_pdf(form_id: str, title: str, about_url: str, subtype: str) -> dict[str, Any]:
    return {
        "source_id": f"irs-{form_id}-ty{TAX_YEAR}",
        "jurisdiction": "us",
        "document_class": "form",
        "title": title,
        "source_url": about_url,
        "download_url": f"https://www.irs.gov/pub/irs-pdf/{form_id}.pdf",
        "source_format": "pdf",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": TY_EXPRESSION_DATE,
        "citation_path": f"us/form/irs/ty{TAX_YEAR}/{form_id}",
        "extraction": SINGLE_BLOCK,
        "metadata": {
            "primary_source": True,
            "source_authority": "Internal Revenue Service",
            "document_subtype": subtype,
            "irs_product_id": form_id,
            "tax_year": TAX_YEAR,
            "source_discovery_group": "us/form/irs-individual-income-tax-forms",
            "source_family": "irs-individual-income-tax-forms-ty2025",
            "index_url": IRS_FORMS_INDEX,
            "discovered_via": "manual-review:tax-agent-queue; index https://www.irs.gov/forms-instructions and https://www.irs.gov/forms-pubs/schedules-for-form-1040",
        },
    }


def _irs_html(product_id: str, title: str, html_url: str, subtype: str) -> dict[str, Any]:
    return {
        "source_id": f"irs-{product_id}-ty{TAX_YEAR}",
        "jurisdiction": "us",
        "document_class": "form",
        "title": title,
        "source_url": html_url,
        "source_format": "html",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": TY_EXPRESSION_DATE,
        "citation_path": f"us/form/irs/ty{TAX_YEAR}/{product_id}",
        "extraction": IRS_HTML,
        "metadata": {
            "primary_source": True,
            "source_authority": "Internal Revenue Service",
            "document_subtype": subtype,
            "irs_product_id": product_id,
            "tax_year": TAX_YEAR,
            "print_version_pdf": f"https://www.irs.gov/pub/irs-pdf/{product_id}.pdf",
            "source_discovery_group": "us/form/irs-individual-income-tax-forms",
            "source_family": "irs-individual-income-tax-forms-ty2025",
            "index_url": IRS_FORMS_INDEX,
            "discovered_via": "manual-review:tax-agent-queue; index https://www.irs.gov/forms-instructions and https://www.irs.gov/forms-pubs/schedules-for-form-1040",
        },
    }


FEDERAL_FORMS = [
    _irs_pdf("f1040", "Form 1040, U.S. Individual Income Tax Return (2025)", IRS_1040_INDEX, "form"),
    _irs_html("i1040gi", "Instructions for Form 1040 and Form 1040-SR (2025)", "https://www.irs.gov/instructions/i1040gi", "instructions"),
    _irs_pdf("f1040s1", "Schedule 1 (Form 1040), Additional Income and Adjustments to Income (2025)", IRS_SCHEDULES_INDEX, "schedule"),
    _irs_pdf("f1040s2", "Schedule 2 (Form 1040), Additional Taxes (2025)", IRS_SCHEDULES_INDEX, "schedule"),
    _irs_pdf("f1040s3", "Schedule 3 (Form 1040), Additional Credits and Payments (2025)", IRS_SCHEDULES_INDEX, "schedule"),
    _irs_pdf("f1040sa", "Schedule A (Form 1040), Itemized Deductions (2025)", "https://www.irs.gov/forms-pubs/about-schedule-a-form-1040", "schedule"),
    _irs_html("i1040sca", "Instructions for Schedule A (Form 1040), Itemized Deductions (2025)", "https://www.irs.gov/instructions/i1040sca", "instructions"),
    _irs_pdf("f1040sb", "Schedule B (Form 1040), Interest and Ordinary Dividends (2025)", "https://www.irs.gov/forms-pubs/about-schedule-b-form-1040", "schedule"),
    _irs_html("i1040sb", "Instructions for Schedule B (Form 1040), Interest and Ordinary Dividends (2025)", "https://www.irs.gov/instructions/i1040sb", "instructions"),
    _irs_pdf("f1040sd", "Schedule D (Form 1040), Capital Gains and Losses (2025)", "https://www.irs.gov/forms-pubs/about-schedule-d-form-1040", "schedule"),
    _irs_html("i1040sd", "Instructions for Schedule D (Form 1040), Capital Gains and Losses (2025)", "https://www.irs.gov/instructions/i1040sd", "instructions"),
    _irs_pdf("f1040sei", "Schedule EIC (Form 1040), Earned Income Credit (2025)", "https://www.irs.gov/forms-pubs/about-schedule-eic-form-1040", "schedule"),
    _irs_pdf("f1040s8", "Schedule 8812 (Form 1040), Credits for Qualifying Children and Other Dependents (2025)", "https://www.irs.gov/forms-pubs/about-schedule-8812-form-1040", "schedule"),
    _irs_html("i1040s8", "Instructions for Schedule 8812 (Form 1040), Credits for Qualifying Children and Other Dependents (2025)", "https://www.irs.gov/instructions/i1040s8", "instructions"),
    _irs_pdf("f8962", "Form 8962, Premium Tax Credit (PTC) (2025)", "https://www.irs.gov/forms-pubs/about-form-8962", "form"),
    _irs_html("i8962", "Instructions for Form 8962, Premium Tax Credit (PTC) (2025)", "https://www.irs.gov/instructions/i8962", "instructions"),
    _irs_pdf("f1040sse", "Schedule SE (Form 1040), Self-Employment Tax (2025)", "https://www.irs.gov/forms-pubs/about-schedule-se-form-1040", "schedule"),
    _irs_html("i1040sse", "Instructions for Schedule SE (Form 1040), Self-Employment Tax (2025)", "https://www.irs.gov/instructions/i1040sse", "instructions"),
    _irs_html("p17", "Publication 17 (2025), Your Federal Income Tax (For Individuals)", "https://www.irs.gov/publications/p17", "publication"),
]


def _irs_guidance(
    doc_id: str,
    number: str,
    title: str,
    irb: str,
    issue_date: str,
    pdf: str,
    subtype: str,
    expression_date: str,
    year: str,
) -> dict[str, Any]:
    return {
        "source_id": f"irs-{doc_id}",
        "jurisdiction": "us",
        "document_class": "guidance",
        "citation_path": f"us/guidance/irs/{doc_id}",
        "title": title,
        "source_url": f"https://www.irs.gov/irb/{irb}_IRB",
        "download_url": f"https://www.irs.gov/pub/irs-drop/{pdf}.pdf",
        "source_format": "pdf",
        "source_as_of": issue_date,
        "expression_date": expression_date,
        "metadata": {
            "primary_source": True,
            "source_authority": "Internal Revenue Service",
            "document_subtype": subtype,
            "document_number": number,
            "irb_citation": f"{irb.replace('_', ' ')} IRB",
            "irb_issue_date": issue_date,
            "tax_year": year,
            "source_discovery_group": "us/guidance/irs",
            "index_url": IRS_IRB_INDEX,
            "discovered_via": "manual-review:tax-agent-queue; index https://www.irs.gov/internal-revenue-bulletins (2026 issues scanned for inflation-adjustment items)",
        },
    }


FEDERAL_GUIDANCE = [
    _irs_guidance("notice-2026-10", "Notice 2026-10", "Notice 2026-10, 2026 Standard Mileage Rates", "2026-04", "2026-01-20", "n-26-10", "notice", "2026-01-01", "2026"),
    _irs_guidance("rev-proc-2026-24", "Rev. Proc. 2026-24", "Rev. Proc. 2026-24, 2027 inflation adjusted amounts for Health Savings Accounts", "2026-25", "2026-06-15", "rp-26-24", "revenue_procedure", "2027-01-01", "2027"),
    _irs_guidance("rev-proc-2026-26", "Rev. Proc. 2026-26", "Rev. Proc. 2026-26, Section 36B applicable percentage table and required contribution percentage for 2027", "2026-31", "2026-07-27", "rp-26-26", "revenue_procedure", "2027-01-01", "2027"),
]

# Already in manifests/us-irs-guidance.yaml; listed so the run note can say what
# the IRB scan skipped.
EXISTING_IRS_GUIDANCE = ("rev-proc-2025-25", "rev-proc-2025-32", "notice-2025-67")


# ---------------------------------------------------------------------------
# States, batch 1
# ---------------------------------------------------------------------------
# Each state: agency slug used in the citation path, publisher name, forms index
# URL, index inventory (families seen with counts, agent-recorded), and the
# confirmed documents. ``blocked`` records the exact publisher failure instead.

STATES: dict[str, dict[str, Any]] = {
    "us-al": {
        "name": "Alabama",
        "agency": "ador",
        "authority": "Alabama Department of Revenue",
        "index_url": "https://www.revenue.alabama.gov/forms/?jsf=jet-data-table:form-table&tax=individual-income-tax",
        "index_document_count": 26,
        "inventory": (
            "JetEngine data table filtered to Individual Income Tax; server renders 25 rows per view, "
            "all years, no server-side pagination. Search '40' view: 26 rows = 15 TY2025 + 10 TY2024 "
            "(Form 40 print form + instructions booklet, Form 40 tax table, 40A/40NR tax tables, 40V, "
            "Schedule OC + instructions, Schedules A/B/DC, D/E, ATP, standard deduction charts 40/40A/40NR, "
            "qualified vehicle loan interest worksheets). Nonresident (40NR) and 40A families not taken."
        ),
        "documents": [
            ("form-40", "Form 40, Alabama Individual Income Tax Return (2025)", "https://www.revenue.alabama.gov/wp-content/uploads/2026/01/25f40blk.pdf", "form"),
            ("form-40-instructions", "Form 40 Booklet, Alabama Individual Income Tax Return Instructions (2025)", "https://www.revenue.alabama.gov/wp-content/uploads/2026/01/25f40bk.pdf", "instructions"),
            ("form-40-tax-table", "Form 40 Tax Table (2025)", "https://www.revenue.alabama.gov/wp-content/uploads/2026/01/25f40taxtable.pdf", "tax_table"),
            ("form-40-standard-deduction-chart", "Standard Deduction Chart, Form 40 (2025)", "https://www.revenue.alabama.gov/wp-content/uploads/2026/01/25stddeduction40.pdf", "worksheet"),
        ],
    },
    "us-ar": {
        "name": "Arkansas",
        "agency": "dfa",
        "authority": "Arkansas Department of Finance and Administration",
        "index_url": "https://www.dfa.arkansas.gov/office/taxes/income-tax-administration/individual-income-tax/forms/2025-tax-forms/",
        "index_document_count": 49,
        "inventory": (
            "2025 Tax Forms page: 49 PDF links (AR1000F resident return, AR1000NR nonresident return, "
            "joint AR1000F/NR instructions, AR1000ES vouchers, schedules AR3/AR4/AR1000ADJ/AR1000D/AR1000TC/"
            "AR1000NOL/AR1000-CO/AR1000TD/AR-OI with instructions, credit forms AR1000CE/DC/DD/AR1075/AR1113/"
            "AR2441, AR2106/AR2210/AR2210A/AR3903/AR4684, AR1000V, AR1055-IT, AR-MS, AR-NRMILITARY, "
            "additional tax credit worksheet, penalty waiver form, Tax Brackets 2025, Tax Tables). "
            "Taken: resident return, instructions, tax brackets."
        ),
        "documents": [
            ("ar1000f", "Form AR1000F, Arkansas Full Year Resident Individual Income Tax Return (2025)", "https://www.dfa.arkansas.gov/wp-content/uploads/2025_AR1000F_FullYearResidentIndividualIncomeTaxReturn_1.pdf", "form"),
            ("ar1000f-instructions", "AR1000F and AR1000NR Instructions, Arkansas Individual Income Tax (2025)", "https://www.dfa.arkansas.gov/wp-content/uploads/2025_AR1000F_and_AR1000NR_Instructions.pdf", "instructions"),
            ("tax-brackets", "Arkansas Individual Income Tax Brackets (2025)", "https://www.dfa.arkansas.gov/wp-content/uploads/2025_TaxBrackets.pdf", "rate_schedule"),
        ],
    },
    "us-co": {
        "name": "Colorado",
        "agency": "cdor",
        "authority": "Colorado Department of Revenue",
        "batch": 1,
        "retry_batch": 3,
        "request": BROWSER_IMPERSONATION,
        "index_url": "https://tax.colorado.gov/2025-individual-income-tax-forms",
        "index_document_count": 45,
        "index_families": [
            "main returns (5): DR 0104 Book, DR 0104, DR 0104EZ, DR 0104X, DR 8454",
            "tax and voluntary schedules (5): DR 0104AMT, DR 0104CH, DR 0104EE, DR 0104PN, DR 0104US",
            "payment forms (8): DR 0900, DR 0900F, DR 0204, DR 0104EP, DR 0104BEP, DR 0105EP, DR 0158-I, DR 0158-F",
            "credit, subtraction and deduction forms (27): DR 0104AD, DR 0104CR; parents and workers DR 0104CN, DR 0104TN, DR 0347; child care contribution DR 1317, DR 1318; contaminated land DR 0348P/T, DR 0349; enterprise and CHIPS zones DR 0078, DR 1366, DR 1370; conservation easement DR 1305/E/F/G; innovative motor vehicle DR 0617, DR 0618; other DR 0113, DR 0289, DR 0366, DR 1307, DR 1316, DR 1322, DR 1330, DR 1703",
            "individual-income-tax-forms landing page: 2025 tab (10 quick links), Helpful Forms (13), tax-year tabs 2022-2024 and the prior-year archive",
        ],
        "inventory": (
            "Individual Income Tax Forms landing page (tax-year tabs 2022-2025, Helpful Forms) links the 2025 Income "
            "Tax Forms page, which lists 45 DR-form landing pages under Main Returns (5), Tax & Voluntary Schedules (5), "
            "Payment Forms (8) and Credit, Subtraction & Deduction Forms (27); each landing page carries the 2025 and "
            "2024 PDF links. Taken: DR 0104 Book (2025 Colorado Individual Income Tax Filing Guide, Book104_2025.pdf, "
            "88 pages, rev. 10/29/25: instructions, DR 0104 and related forms) and DR 0104 (2025 Colorado Individual "
            "Income Tax Return, form only, 8 pages, rev. 10/03/25). Colorado lists no separate TY2025 rate schedule "
            "(flat rate stated in the booklet); DR 0104EP (2025 estimated tax payment form with worksheet) is a "
            "payment form and was not taken, as with the NJ/NM/VT estimated vouchers. Access: tax.colorado.gov answers "
            "HTTP 403 (CloudFront) to plain requests with the corpus user agent and serves to a chrome120 TLS "
            "fingerprint; the batch-1 and batch-2 attempts (403 in every mode from a European network) were retried "
            f"{US_NETWORK_RETRY} from a US network, where the index, landing pages and PDFs serve to the impersonated request."
        ),
        "documents": [
            ("dr-0104", "DR 0104, Colorado Individual Income Tax Return (2025)", "https://tax.colorado.gov/sites/tax/files/documents/DR0104_2025.pdf", "form", "https://tax.colorado.gov/DR0104"),
            ("dr-0104-book", "DR 0104 Book, Colorado Individual Income Tax Filing Guide (2025)", "https://tax.colorado.gov/sites/tax/files/documents/Book104_2025.pdf", "instructions", "https://tax.colorado.gov/DR0104Booklet"),
        ],
    },
    "us-dc": {
        "name": "District of Columbia",
        "agency": "otr",
        "authority": "District of Columbia Office of Tax and Revenue",
        "index_url": "https://otr.cfo.dc.gov/page/individual-income-tax-forms-0",
        "index_document_count": 230,
        "inventory": (
            "Individual Income Tax Forms page: 230 node links across tax years 2018-2025; per year the "
            "families are D-40 Booklet, D-40 form (fill-in), D-40P payment voucher, D-40B nonresident "
            "request for refund, D-40ES estimated tax booklet, and LIHTC allocation instructions. TY2025 "
            "row: 6 documents. Taken: 2025 D-40 Booklet and 2025 D-40 form. The 2026 D-40ES booklet "
            "(estimated tax) is a TY2026 product and was left for the TY2026 cut. Note: the page and PDFs "
            "serve to the corpus user agent; a Chrome user agent / chrome120 impersonation is answered "
            "with a Cloudflare 'Access denied' page, so no browser_impersonation is configured."
        ),
        "documents": [
            ("d-40-booklet", "2025 D-40 Booklet, District of Columbia Individual Income Tax Forms and Instructions", "https://otr.cfo.dc.gov/sites/default/files/dc/sites/otr/publication/attachments/2025_D40_Book_082026_v1.pdf", "instructions", "https://otr.cfo.dc.gov/node/1817386"),
            ("d-40", "2025 D-40, District of Columbia Individual Income Tax Return", "https://otr.cfo.dc.gov/sites/default/files/dc/sites/otr/publication/attachments/2025_D40_Form_030526.pdf", "form", "https://otr.cfo.dc.gov/node/1817391"),
        ],
    },
    "us-de": {
        "name": "Delaware",
        "agency": "dor",
        "authority": "Delaware Division of Revenue",
        "index_url": "https://revenue.delaware.gov/personal-income-tax-forms/",
        "index_document_count": 63,
        "inventory": (
            "Personal Income Tax Forms Current Year (2025-2026) page: 63 PDF links. Families: resident "
            "PIT-RES form/schedule/Schedule A/worksheet/instructions, non-resident PIT-NON family, 2025 "
            "income tax table, PIT-VCH/PIT-EXT/PIT-EST 2026/PIT-REQ/PIT-UND/PIT-STC/PIT-SCW/PIT-CRS/"
            "PIT-BIN/PIT-CFR, fiduciary FID-*, composite CMP-*, partnership PRT-*, real estate REW-*, "
            "PUT-EXM and RTT-* business forms. Taken: PIT-RES form, PIT-RES instructions, 2025 tax table."
        ),
        "documents": [
            ("pit-res", "Form PIT-RES, Delaware Individual Resident and Amended Income Tax Return (2025)", "https://revenuefiles.delaware.gov/2025/PITForms_Instructions/PIT-RES_2025-01_PaperInteractiveIPM.pdf", "form"),
            ("pit-res-instructions", "Form PIT-RES Instructions, Delaware Individual Resident Income Tax Return (2025)", "https://revenuefiles.delaware.gov/2025/PITForms_Instructions/Instructions/PIT-RES_Instructions_2025-01.pdf", "instructions"),
            ("income-tax-table", "Delaware 2025 Income Tax Table", "https://revenuefiles.delaware.gov/2025/TY25_taxtable.pdf", "tax_table"),
        ],
    },
    "us-ia": {
        "name": "Iowa",
        "agency": "idr",
        "authority": "Iowa Department of Revenue",
        "index_url": "https://revenue.iowa.gov/forms/common-forms/individual-income-tax",
        "index_document_count": 15,
        "inventory": (
            "Forms - Individual Income Tax page: 15 media links (2025 IA 1040 return, IA 1040ES 2026 "
            "voucher instructions, IA 148, IA 100/100A-G capital gain deduction forms, IA 4136, IA 176, "
            "alternate tax worksheet, composite agreement) plus a link to the online 2025 IA 1040 Expanded "
            "Instructions (47 line/intro HTML pages at .../1040-expanded-instructions and a printable PDF "
            "on its past-instructions page). Iowa publishes no separate rate schedule for TY2025 (flat "
            "rate stated in the instructions). Taken: 2025 IA 1040 return and the 2025 Expanded "
            "Instructions PDF (the department's own printable compilation of the HTML instructions)."
        ),
        "documents": [
            ("ia-1040", "2025 IA 1040 Iowa Individual Income Tax Return (41-001)", "https://revenue.iowa.gov/media/4402/download?inline", "form"),
            ("ia-1040-expanded-instructions", "2025 IA 1040 Expanded Instructions (printable)", "https://revenue.iowa.gov/media/4435/download?inline", "instructions", "https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax/1040-expanded-instructions/past-instructions"),
        ],
    },
    "us-id": {
        "name": "Idaho",
        "agency": "istc",
        "authority": "Idaho State Tax Commission",
        "index_url": "https://tax.idaho.gov/forms/",
        "index_document_count": 200,
        "inventory": (
            "Forms page: 589 links, 200 PDF form links across sales/use, property, tobacco, fuels, "
            "business income, individual income (Form 40 return 2025, Form 43 part-year/nonresident, "
            "Form 39R resident supplemental schedule, Form 39NR, individual income tax instructions "
            "EIN00046 rev. 2026-03-02, Form 51 estimated payment, food tax credit Form 24, capital "
            "gains deduction, itemized deduction worksheet), fiduciary, withholding and beer/wine "
            "families. Taken: Form 40, EIN00046 instructions, Form 39R. manifests/us-id-tax-forms.yaml "
            "(source-discovery seed, older EIN00046 revisions, never extracted) is left untouched."
        ),
        "documents": [
            ("form-40", "Form 40, Idaho Individual Income Tax Return (2025)", "https://tax.idaho.gov/wp-content/uploads/forms/EFO00089/EFO00089_03-02-2026.pdf", "form"),
            ("individual-income-tax-instructions", "Idaho Individual Income Tax Instructions, Forms 40, 43, 39R, 39NR (2025, EIN00046 rev. 2026-03-02)", "https://tax.idaho.gov/wp-content/uploads/forms/EIN00046/EIN00046_03-02-2026.pdf", "instructions"),
            ("form-39r", "Form 39R, Idaho Resident Supplemental Schedule (2025)", "https://tax.idaho.gov/wp-content/uploads/forms/EFO00088/EFO00088_03-02-2026.pdf", "schedule"),
        ],
    },
    "us-in": {
        "name": "Indiana",
        "agency": "dor",
        "authority": "Indiana Department of Revenue",
        "batch": 1,
        "retry_batch": 3,
        "index_url": "https://www.in.gov/dor/tax-forms/individual/current/",
        "index_document_count": 54,
        "index_families": [
            "Indiana full-year residents (14 rows): IT-40 Booklet (SP 265), IT-40 Form (154), Schedules 1-7, Schedule 5/IN-DONATE, IN-DEP, IN-DEP-A, IN-W, CT-40, IT-40 Booklet Spanish (SP 270)",
            "Indiana part-year residents and full-year nonresidents (15 rows): IT-40PNR Booklet (SP 258), IT-40PNR Form (472), Schedules A-H, IN-DEP, IN-DEP-A, IN-PRO, IN-DONATE, IN-W, CT-40PNR, IT-40RNR",
            "other individual tax forms/schedules (31 rows): CC-40, ES-40, FCD-A, IN-ABLE, IN-CR, IN-EDGE, IN-EDGE R, IN-EIC, IN-H, IN-OCC, IN-OPT, IN-PAT, IN-529, IN-2058SP, IT-2210, IT-2210A, IT-2440, IT-40NOL, IT-40PNRA, IT-9, SC-40, IT-40QEC, NOL-MOD, IH-5, GA-110L, IN-40PA, POA-1, POA-R",
        ],
        "inventory": (
            "DOR Current Year Individual Tax Forms index: 58 forms.in.gov/Download.aspx links, 54 unique (IN-DEP, IN-DEP-A, "
            "IN-W and ES-40 are listed twice), in three tables (full-year residents 14, part-year/nonresidents 15, other "
            "31) plus the ES-40 heading. Taken: 2025 IT-40 Form (State Form 154, R24 / 9-25, 2 pages) and the 2025 "
            "IT-40 Full-Year Resident Individual Income Tax Booklet (SP 265, 12-25, 56 pages; instructions, county tax "
            "rates, no form or schedules). Indiana lists no separate TY2025 rate schedule (flat rate and county rates "
            "are in the booklet); ES-40 (estimated tax payment form with worksheet) is a payment voucher and was not "
            "taken, as with the NJ/NM/VT estimated vouchers; Schedules 3, 7 and CT-40, which the IT-40 requires, are "
            "schedules and were not taken (DC/MS/MT precedent). Access: the index serves to the corpus user agent; "
            "forms.in.gov (Cloudflare), which answered HTTP 403 'Sorry, you have been blocked' in every mode from a "
            f"European network in batches 1 and 2, serves the PDFs plainly (200, application/pdf) on the {US_NETWORK_RETRY} "
            "retry from a US network. The file host names files by content-disposition (IT-40 (9-25) Fillable.pdf, "
            "IT-40 Instructions (12-25).pdf); the index page is recorded as source_url."
        ),
        "documents": [
            ("it-40", "Form IT-40, Indiana Full-Year Resident Individual Income Tax Return (2025)", "https://forms.in.gov/Download.aspx?id=16914", "form", "https://www.in.gov/dor/tax-forms/individual/current/"),
            ("it-40-booklet", "IT-40 Booklet, Indiana Full-Year Resident Individual Income Tax Booklet (2025)", "https://forms.in.gov/Download.aspx?id=16915", "instructions", "https://www.in.gov/dor/tax-forms/individual/current/"),
        ],
    },
    "us-ms": {
        "name": "Mississippi",
        "agency": "dor",
        "authority": "Mississippi Department of Revenue",
        "index_url": "https://www.dor.ms.gov/forms-resources/form-search?division=individual_forms",
        "index_document_count": 26,
        "inventory": (
            "Form Search, Individual division: 26 PDF links (Form 80-100 individual income tax "
            "instructions, 80-105 resident return, 80-205 non-resident/part-year return, 80-106 voucher, "
            "80-107 withholding schedule, 80-108 itemized deductions, 80-115 e-file declaration, 80-155 "
            "NOL, 80-160 credit for tax paid to another state, 80-161 PTE credit, 80-315 reforestation "
            "credit + instructions, 80-320 interest/penalty worksheet, 80-340 reservation exclusion, 80-401 "
            "credit summary, 80-491 additional dependents, fiduciary 81-* forms, 70-698, 71-661, transcript "
            "request). Taken: 80-105 and 80-100. Mississippi publishes no separate TY2025 rate schedule."
        ),
        "documents": [
            ("form-80-105", "Form 80-105, Mississippi Resident Individual Income Tax Return (2025)", "https://www.dor.ms.gov/sites/default/files/tax-forms/individual/80105258%201.pdf", "form"),
            ("form-80-100-instructions", "Form 80-100, Mississippi Individual Income Tax Instructions (2025)", "https://www.dor.ms.gov/sites/default/files/tax-forms/individual/80100251%202.pdf", "instructions"),
        ],
    },
    "us-mt": {
        "name": "Montana",
        "agency": "mtdor",
        "authority": "Montana Department of Revenue",
        "index_url": "https://revenue.mt.gov/forms/",
        "index_document_count": 20,
        "inventory": (
            "Forms repository index links the Individual Income Tax publication pages. Form 2 publication "
            "page: 20 PDF links (Form 2 returns 2021-2025, 2024 instructions, 2024/2025 Schedules I-V, "
            "2EC and transition schedule, 2025 instructions); Form 2 instruction booklet page: 7 links "
            "(instructions 2020-2025, SALT-cap instructions). Taken: 2025 Form 2 and 2025 Form 2 "
            "instructions. Montana's rate schedule is inside the instructions."
        ),
        "documents": [
            ("form-2", "Montana Individual Income Tax Return, Form 2 (2025)", "https://revenue.mt.gov/files/Forms/Montana-Individual-Income-Tax-Return-Form-2/2025_Montana_Individual_Income_Tax_Return_Form_2.pdf", "form", "https://revenue.mt.gov/publications/montana-individual-income-tax-return-form-2"),
            ("form-2-instructions", "Montana Individual Income Tax Return, Form 2 Instructions (2025)", "https://revenuefiles.mt.gov/files/Forms/Montana-Individual-Income-Tax-Return-Form-2-Instructions/2025_Montana_Individual_Income_Tax_Return_Form_2_Instructions.pdf", "instructions", "https://revenue.mt.gov/publications/montana-form-2-individual-income-tax-return-forms-and-instructions-includes-form-2ec"),
        ],
    },
    # -----------------------------------------------------------------------
    # States, batch 2 (the seven states left in the queue, NH onward) and batch 3
    # (CO, IN, UT: blocked in batches 1/2, retried from a US network). Rows may
    # carry ``batch``, ``document_class`` (guidance scopes for publishers with no
    # TY2025 resident return), ``request`` (applied to every document),
    # ``index_families`` (queue row field), and dict rows for HTML documents.
    # -----------------------------------------------------------------------
    "us-nh": {
        "name": "New Hampshire",
        "agency": "dra",
        "authority": "New Hampshire Department of Revenue Administration",
        "batch": 2,
        "document_class": "guidance",
        "request": BROWSER_IMPERSONATION,
        "index_url": "https://www.revenue.nh.gov/resource-center/current-year-forms-and-instructions",
        "index_document_count": 232,
        "index_families": [
            "business profits tax / business enterprise tax: NH-1040, NH-1041, NH-1065, NH-1120, NH-1120-WE, BET, BET-80, BET-80-WE, BT-EXT, BT-SUMMARY, Schedules II-IV, DP-80, DP-120/120-P, DP-121, DP-131-A, DP-132/132-WE, DP-160, DP-2210/2220, ADDL INFO, AFFL SCHD (forms + instructions)",
            "meals and rentals, communications services, tobacco, real estate transfer, utility property, medicaid enhancement, nursing facility, education tax credit, low and moderate income homeowners property tax relief (DP-8), DP-9, DP-100, CD-*, PA-*, AU-*, ED-*, MS-*, CU-*, GPA-01",
            "TY2025 substitute forms letter of intent and general instructions",
            "interest and dividends tax: none for TY2025 (only a Search Prior Year Forms link; DP-10 2024 was the final return)",
        ],
        "inventory": (
            "Current Year Forms and Instructions index (Drupal; served only to a browser TLS fingerprint, HTTP 403 "
            "to plain requests with the corpus or a Chrome user agent): 238 PDF links, 232 unique, grouped by tax "
            "type (business profits/business enterprise NH-1040/1041/1065/1120/1120-WE, BET, BT-*, DP-80..DP-2210, "
            "schedules; meals and rentals, communications, tobacco, real estate transfer, utility, medicaid "
            "enhancement, nursing facility, education tax credit, DP-8 property tax relief; TY2025 substitute forms). "
            "No Interest and Dividends Tax (DP-10) family is listed for TY2025: RSA 77 was repealed for taxable "
            "periods beginning on or after 2025-01-01, so New Hampshire publishes no TY2025 resident individual "
            "income tax return or instructions. Taken instead, document_class guidance: TIR 2025-001 (2025-01-21), "
            "the DRA release stating the repeal and that 2025 I&D forms will not be issued."
        ),
        "documents": [
            ("tir-2025-001", "TIR 2025-001, Interest and Dividends Tax Repealed Effective January 1, 2025", "https://www.revenue.nh.gov/sites/g/files/ehbemt736/files/documents/2025-001-technical-information-release-repeal.pdf", "technical_information_release"),
        ],
    },
    "us-nj": {
        "name": "New Jersey",
        "agency": "taxation",
        "authority": "New Jersey Division of Taxation",
        "batch": 2,
        "index_url": "https://www.nj.gov/treasury/taxation/prntgit.shtml",
        "index_document_count": 63,
        "index_families": [
            "resident: NJ-1040 + instructions, Schedule NJ-HCC, NJ-EZ Enroll, NJ-1040X + instructions, NJ-630, NJ-1040-ES 2025/2026 + instructions, NJ-1040-V, NJ-2210, GIT-311/317/327/330/337, GIT-DEP, NJ-1040-O, NJ-2440, NJ-2450, Schedule COJ, Schedule DOP/NJ-WCC, Schedule NJ-BUS-1/2, Worksheet G, NJ-1040-HW + instructions, PA REV-419",
            "nonresident: NJ-1040NR + instructions, NJ-1040NR-V, NJ-2210NR, NJ-NR-A, NJ-165, business schedules, GIT credit forms",
            "fiduciary: NJ-1041 + instructions, NJ-1041SB, NJ-1041-V, business schedules",
            "composite: NJ-1080C + instructions, NJ-1080E, eligibility, record layouts",
            "other: C-4267, DCC-1, NJ-W4, NJ-W-4P, change of address, A-3128, GIT/REP-1 to 4A",
        ],
        "inventory": (
            "2025 Income Tax Forms page (Printable Gross Income Tax forms): 89 table rows, 63 unique PDF links "
            "(62 on nj.gov, one PA REV-419 on revenue.pa.gov) across resident, nonresident, fiduciary, composite "
            "and other families. Taken: NJ-1040 resident return (4 pages, 2025) and the NJ-1040 Resident Return "
            "instruction booklet (70 pages, 2025). New Jersey publishes no separate TY2025 rate schedule or tax "
            "table; both are inside the instruction booklet."
        ),
        "documents": [
            ("nj-1040", "Form NJ-1040, New Jersey Resident Income Tax Return (2025)", "https://www.nj.gov/treasury/taxation/pdf/current/1040.pdf", "form"),
            ("nj-1040-instructions", "Form NJ-1040, New Jersey Resident Return Instructions (2025)", "https://www.nj.gov/treasury/taxation/pdf/current/1040i.pdf", "instructions"),
        ],
    },
    "us-nm": {
        "name": "New Mexico",
        "agency": "trd",
        "authority": "New Mexico Taxation and Revenue Department",
        "batch": 2,
        "index_url": NM_PIT_FORMS_INDEX,
        "index_document_count": 32,
        "index_families": [
            "return and instructions: Personal Income Tax Packet 2025, PIT-1 return, PIT-1 instructions, PIT-1 quick reference instructions, 2025 Tax Look Up Table",
            "schedules with instructions: PIT-S, PIT-ADJ, PIT-B, PIT-110, PIT-RC, PIT-CG, PIT-Childcare, PIT-CR, PIT-D",
            "amended, payment and filing: PIT-X + instructions, PIT-EXT, PIT-PV, PIT-8453, RPD-41338",
            "estimated: PIT-ES voucher + instructions (subfolder RPD-41272 underpayment penalty)",
            "other RPD forms: RPD-41369 NOL carryforward, RPD-41348 military spouse (2), RPD-41359 pass-through withholding statement, RPD-41260 change of address; subfolder Prior Years",
        ],
        "inventory": (
            "Personal Income Tax Forms page hosts a RealFile widget (rf-tables.js, account 34821a9573ca43e7b06dfad20f5183fd, "
            "folder 288c2306-33d5-4471-b79b-73d07aaea840 'Personal Income Tax (PIT)'); its GetWidgetFiles listing "
            "returns 32 files and 2 subfolders (Prior Years; RPD-41272). Downloads are the department's RealFile "
            "file host (execute-api.us-west-2.amazonaws.com/prod/PublicFiles/<account>/<fileId>/<name>), the only "
            "URLs the publisher's index emits. Taken: 2025 PIT-1 return, 2025 PIT-1 instructions, 2025 Tax Look Up "
            "Table (the separately listed computation document). The combined 2025 PIT Packet duplicates them and "
            "was not taken."
        ),
        "documents": [
            ("pit-1", "Form PIT-1, New Mexico Personal Income Tax Return (2025)", f"{NM_REALFILE}/1acb11d0-7e9e-4ff9-8c45-a28d9bfc9150/2025pit-1.pdf", "form", NM_PIT_FORMS_INDEX),
            ("pit-1-instructions", "Form PIT-1, New Mexico Personal Income Tax Return Instructions (2025)", f"{NM_REALFILE}/2d774fd0-be97-4b57-8dae-68aed999da0f/2025pit-1-ins.pdf", "instructions", NM_PIT_FORMS_INDEX),
            ("tax-look-up-table", "New Mexico Personal Income Tax Look Up Table (2025)", f"{NM_REALFILE}/3138d8e6-3d90-4fc8-a0af-ee15d3b395f5/2025trt.pdf", "tax_table", NM_PIT_FORMS_INDEX),
        ],
    },
    "us-ok": {
        "name": "Oklahoma",
        "agency": "otc",
        "authority": "Oklahoma Tax Commission",
        "batch": 2,
        "index_url": "https://oklahoma.gov/tax/forms.html",
        "index_document_count": 26,
        "index_families": [
            "Income Tax / Individuals / Current (26): 511 resident packet, 511-NR packet, 504-I, 505, 507, 511-EF, 511-EIC, 511-NOL, 511-NR-NOL, 511-TX, 511-V, 528, 538-H, 538-S, 542, 561, 561-P, 561-NR, 561-S, 573, 574, 582-I, 588, OW-8-ES, OW-8-ES-SUP, OW-8-P-SUP-I",
            "other current income tax subcategories on the same index: Corporate (3), Corporate/Fiduciary/Pass-Through (2), Corporate/Pass-Through (1), Credits (22), Fiduciary (5), Information (4), Miscellaneous (4), Pass-Through (9), Withholding (1); past-year income tax 1997-2024; non-income tax types",
        ],
        "inventory": (
            "Forms page is driven by the commission's own metadata CSV "
            "(/content/dam/ok/en/tax/documents/forms/New-MetaData-CSV-8-1-26.csv, 1,649 rows). Category Income Tax, "
            "subcategory Individuals, year Current: 26 rows. Taken: the 2025 Form 511 Oklahoma Resident Individual "
            "Income Tax Forms Packet and Instructions (52 pages; Form 511, instructions, Form 538-S and the tax "
            "table are one publication). Oklahoma lists no separate TY2025 resident form or rate schedule."
        ),
        "documents": [
            ("form-511-packet", "2025 Form 511, Oklahoma Resident Individual Income Tax Forms Packet and Instructions", "https://oklahoma.gov/content/dam/ok/en/tax/documents/forms/individuals/current/511-Pkt.pdf", "forms_and_instructions_packet"),
        ],
    },
    "us-ut": {
        "name": "Utah",
        "agency": "ustc",
        "authority": "Utah State Tax Commission",
        "batch": 2,
        "retry_batch": 3,
        "index_url": "https://tax.utah.gov/forms-pubs/",
        "index_document_count": 517,
        "index_families": [
            "Individual Income, current (21 rows): TC-40 Forms (tc-40full), TC-40 Basic (tc-40), TC-40 Instructions, TC-40 Mini Packet, TC-40 Full Packet, TC-40A, TC-40AC, TC-40B, TC-40R, TC-40S, TC-40T, TC-40TS, TC-40W, TC-131, TC-546, TC-547, TC-804, TC-831, TC-8857, Pub 33, Pub 57",
            "Individual Income, prior years (82 rows): TC-40, TC-40 Instructions, TC-40A/B/C/D/LI/LIC/LIS/S/V/W 2015-2024",
            "other tax types, all years (515 rows): Corporate Income 108, Sales 83, DMV and MVED 74, Fiduciary 49, Other Taxes 43, Partnership/LLP/LLC 38, Fuel 24, Tobacco 23, Withholding 22, Insurance 16, Oil/Gas/Severance 14, Property 11, Beer 7, Cannabinoid Tobacco 3",
        ],
        "inventory": (
            "Current Forms & Publications index (tax.utah.gov/forms redirects 301 to /forms-pubs/): one table of 618 rows "
            "with 517 unique PDF links on the commission's file host files.tax.utah.gov/tax/forms/<year or current>/; "
            "231 links are 'current', 103 rows are tax type Individual Income (21 current). Taken: TC-40 Basic (Utah "
            "Individual Income Tax Return 2025, tc-40.pdf, 3 pages) and TC-40 Instructions (Utah 2025 TC-40 Forms and "
            "Instructions booklet, tc-40inst.pdf, 34 pages). Utah lists no separate TY2025 rate schedule (single rate "
            "stated in the instructions); TC-40 Forms (tc-40full: TC-40 with schedules), the Mini and Full Packets "
            "(compilations without instructions) and the TC-546 prepayment coupon were not taken. Access: the index and "
            "the file host serve to the corpus user agent (index via Cloudflare 200; PDFs from S3); chrome120 "
            "impersonation of tax.utah.gov gets the Cloudflare 403 challenge, so no browser_impersonation is configured "
            "(DC precedent). Batch 2 probed files.tax.utah.gov/forms/current/ (404): the host's real path is "
            f"/tax/forms/current/, as the index links it; tax.utah.gov/forms/current/tc-40.pdf 301s there. Retried {US_NETWORK_RETRY} "
            "from a US network."
        ),
        "documents": [
            ("tc-40", "Form TC-40, Utah Individual Income Tax Return (2025)", "https://files.tax.utah.gov/tax/forms/current/tc-40.pdf", "form", "https://tax.utah.gov/forms-pubs/"),
            ("tc-40-instructions", "TC-40 Forms and Instructions, Utah Individual Income Tax Return Instructions (2025)", "https://files.tax.utah.gov/tax/forms/current/tc-40inst.pdf", "instructions", "https://tax.utah.gov/forms-pubs/"),
        ],
    },
    "us-vt": {
        "name": "Vermont",
        "agency": "vdt",
        "authority": "Vermont Department of Taxes",
        "batch": 2,
        "index_url": "https://tax.vermont.gov/personal-income-tax",
        "index_document_count": 35,
        "index_families": [
            "return and instructions: 2025 Income Tax Return Booklet, IN-111 + instructions, Tax Year 2025 Vermont Tax Rate Schedules, Vermont Tax Tables (file VermontTaxTables-2025.pdf, index label 'Tax Year 2024')",
            "schedules with instructions: IN-112, IN-113, IN-117, IN-119, IN-153",
            "payments, estimated, extension, amended: IN-114 2026 + instructions, IN-116, IN-151, IN-152, IN-152A, IN-110",
            "homestead and credits: HS-122/HI-144 + instructions, HS-122W, HSD-315, HSD-316, RCC-146 + instructions",
            "other: W-4VT, domicile statement, B-2, PA-1, GB-1098, RP-1231",
        ],
        "inventory": (
            "Personal Income Tax page (the /individuals/personal-income-tax URL redirects here; the /forms-and-"
            "instructions URL is 404): 35 unique PDF links for tax year 2025. Taken: Form IN-111 (2 pages, rev. "
            "10/25), Form IN-111 Instructions (20 pages) and the Tax Year 2025 Vermont Tax Rate Schedules (1 page), "
            "the separately published computation document. Not taken: the 2025 Income Tax Return Booklet (52 pages, "
            "a compilation of IN-111/112/113/116, HS-122, RCC-146 and instructions) and the tax tables (lookup), "
            "following the batch-1 AR precedent."
        ),
        "documents": [
            ("in-111", "Form IN-111, Vermont Income Tax Return (2025)", "https://tax.vermont.gov/sites/tax/files/documents/IN-111-2025.pdf", "form"),
            ("in-111-instructions", "Form IN-111 Instructions, Vermont Income Tax Return (2025)", "https://tax.vermont.gov/sites/tax/files/documents/IN-111-Instr-2025.pdf", "instructions"),
            ("tax-rate-schedules", "Tax Year 2025 Vermont Tax Rate Schedules", "https://tax.vermont.gov/sites/tax/files/documents/TaxRateSched-2025.pdf", "rate_schedule"),
        ],
    },
    "us-wa": {
        "name": "Washington",
        "agency": "dor",
        "authority": "Washington State Department of Revenue",
        "batch": 2,
        "document_class": "guidance",
        "index_url": "https://dor.wa.gov/taxes-rates/other-taxes/capital-gains-tax",
        "index_document_count": 8,
        "index_families": [
            "income tax: DOR 'Income tax' page (no individual income tax currently; 9.9% tax on AGI over $1 million from 2028 under SB 6346, first returns 2029); no forms",
            "capital gains tax page documents: 4 interim guidance statements, 2 special notices (tiered rates TY2025, prepayment), Capital Gains Tax Return Instructions PDF (2023-01, electronic-only return), Capital Gains Tax info sheet PDF (2023-02)",
        ],
        "inventory": (
            "Washington has no individual income tax and therefore no resident return in its forms index "
            "(dor.wa.gov/forms-publications/forms-name). The DOR 'Income tax' page states this and announces the "
            "2028 high-earner income tax; the capital gains tax page (an excise tax on individuals' long-term capital "
            "gains, filed only through My DOR) links 8 documents: 4 interim guidance statements, 2 special notices, "
            "the 2023 return instructions PDF and a 2023 info sheet. Taken, document_class guidance, as irs.gov-style "
            "HTML (one provision per heading): the Income tax page, the Capital gains tax page, and the special "
            "notice 'New tiered rates for Washington's capital gains tax' (issued 2025-06-30; 7% to $1,000,000 and "
            "9.9% above, beginning tax year 2025). The 2023 return instructions predate the tiered rates and were "
            "not taken."
        ),
        "documents": [
            {"id": "income-tax", "title": "Income tax (Washington Department of Revenue): no individual income tax; 9.9% tax on adjusted gross income over $1 million from 2028", "url": "https://dor.wa.gov/taxes-rates/income-tax", "subtype": "agency_web_page", "format": "html", "extraction": WA_DOR_HTML},
            {"id": "capital-gains-tax", "title": "Capital gains tax (Washington Department of Revenue)", "url": "https://dor.wa.gov/taxes-rates/other-taxes/capital-gains-tax", "subtype": "agency_web_page", "format": "html", "extraction": WA_DOR_HTML},
            {"id": "special-notice-capital-gains-tiered-rates", "title": "Special Notice: New tiered rates for Washington's capital gains tax (tax year 2025)", "url": "https://dor.wa.gov/forms-publications/publications-subject/special-notices/new-tiered-rates-washingtons-capital-gains-tax", "subtype": "special_notice", "format": "html", "extraction": WA_DOR_HTML},
        ],
    },
    # Territories pass (2026-09-11; every URL confirmed on the publisher's own forms index that day).
    "us-pr": {
        "name": "Puerto Rico",
        "agency": "hacienda",
        "authority": "Puerto Rico Department of the Treasury (Departamento de Hacienda)",
        "batch": 4,
        "version": TERRITORY_FORMS_VERSION,
        "source_as_of": TERRITORY_SOURCE_AS_OF,
        "source_family": "territory-resident-individual-income-tax-forms-ty2025",
        "index_url": "https://hacienda.pr.gov/documentos/2025-planilla-de-contribucion-sobre-ingresos-de-individuos-para-propositos-informativos-no-utilice-para-rendir-individual-income-tax-return-information-purposes",
        "index_document_count": 6,
        "index_families": [
            "2025 individual return, informative print (2): Formulario 482 (Spanish, rev. 20 jun 25) and Form 482.0 (English, rev. Jul 18 25); the return itself must be e-filed",
            "2025 instructions booklets (2): Spanish (rev. 1 abr 26; the 'Instrucciones para Radicar la Planilla' page separately links the 27 feb 26 revision) and English",
            "2025 Anejo CT / Schedule CT, informative print (2): Spanish and English; not taken",
        ],
        "inventory": (
            "Hacienda's '2025 Planilla de Contribucion sobre Ingresos de Individuos (para propositos informativos)' document "
            "page links six PDFs: the Spanish and English informative prints of the individual return (Formulario 482 / "
            "Form 482.0), the Spanish and English instructions booklets and the Spanish and English Schedule CT. "
            "Taken: both returns and both instructions booklets."
        ),
        "documents": [
            ("formulario-482", "Formulario 482, Planilla de Contribucion sobre Ingresos de Individuos 2025 (para propositos informativos)", "https://hacienda.pr.gov/sites/default/files/individuos_2025_rev._20_jun_25_informativo.pdf", "form"),
            ("formulario-482-instrucciones", "Folleto de Instrucciones, Planilla de Contribucion sobre Ingresos de Individuos 2025 (rev. 1 abr 26)", "https://hacienda.pr.gov/sites/default/files/inst_individuos_2025_1_abr_26.pdf", "instructions"),
            ("form-482-0", "Form 482.0, Individual Income Tax Return 2025 (for information purposes)", "https://hacienda.pr.gov/sites/default/files/individuals_2025_rev._jul_18_25_informative.pdf", "form"),
            ("form-482-0-instructions", "Instructions Booklet, Individual Income Tax Return 2025", "https://hacienda.pr.gov/sites/default/files/inst_individuals_2025.pdf", "instructions"),
        ],
    },
    "us-gu": {
        "name": "Guam",
        "agency": "drt",
        "authority": "Guam Department of Revenue and Taxation",
        "batch": 4,
        "version": TERRITORY_FORMS_VERSION,
        "source_as_of": TERRITORY_SOURCE_AS_OF,
        "source_family": "territory-resident-individual-income-tax-forms-ty2025",
        "index_url": "https://www.guamtax.com/forms/",
        "index_document_count": 59,
        "index_families": [
            "Guam individual income tax returns 2019-2025 (12): Form 1040 Guam and Form 1040-SR Guam per year",
            "business privilege tax, gross receipts tax and other DRT forms and instructions (47); not taken",
        ],
        "inventory": (
            "The DRT Forms & Publications page lists 59 PDFs; the Income Tax section carries the Guam prints of Form 1040 "
            "and Form 1040-SR for 2019-2025. Guam applies the Internal Revenue Code as the Guam Territorial Income Tax "
            "(48 U.S.C. 1421i) and DRT publishes no Guam instructions booklet: its filing-season notices refer taxpayers "
            "to the IRS instructions, which are in the corpus as us/form/irs/ty2025/i1040gi. Taken: the 2025 Form 1040 "
            "Guam and 2025 Form 1040-SR Guam."
        ),
        "documents": [
            ("form-1040-guam", "Form 1040 Guam, Guam Individual Income Tax Return (2025)", "https://www.guamtax.com/forms/2025GUAM1040TaxForm.pdf", "form"),
            ("form-1040-sr-guam", "Form 1040-SR Guam, Guam Income Tax Return for Seniors (2025)", "https://www.guamtax.com/forms/2025GUAM1040SRTaxForm.pdf", "form"),
        ],
    },
    "us-mp": {
        "name": "Northern Mariana Islands",
        "agency": "drt",
        "authority": "CNMI Department of Finance, Division of Revenue and Taxation",
        "batch": 4,
        "version": TERRITORY_FORMS_VERSION,
        "source_as_of": TERRITORY_SOURCE_AS_OF,
        "source_family": "territory-resident-individual-income-tax-forms-ty2025",
        "index_url": "https://www.finance.gov.mp/forms.php",
        "index_document_count": 170,
        "index_families": [
            "2025 Revenue and Taxation forms (14): 1040CM, 1040NMI, 1040NR-CM, 1040-CM-X, Schedule 1CM, Schedule ETC, Schedule WSD, OS-3710, W-2CM, W-2GCM, 1120CM, 1120F-CM, 1120S, 1065-CM",
            "2025 Revenue and Taxation instructions and publications (7): Publication IOC (W-2CM code reference), OS-3710/W-2 supplemental instructions, electronic filing specifications and templates, withholding guidelines; no 2025 Form 1040CM instructions (the last posted i1040-CM is tax year 2020 under prior-year forms)",
            "prior-year (2019-2024) income tax forms and IRS links on the same page and the prior-year page (149); not taken",
        ],
        "inventory": (
            "The Department of Finance Forms page lists 170 file links across its divisions; the Revenue and Taxation "
            "2025 block carries the Northern Marianas Territorial Income Tax return (Form 1040CM), the wage and salary "
            "tax return (Form 1040NMI), the nonresident and amended returns and the 1040CM schedules 1CM, ETC and WSD, "
            "and links IRS Schedules 8812 and EIC, the IRS Form 1040 instructions and tax tables for the mirrored "
            "code. Taken: Form 1040CM, Form 1040NMI, Schedule 1CM, Schedule ETC and Schedule WSD for 2025."
        ),
        "documents": [
            ("form-1040cm", "Form 1040CM, Northern Marianas Territorial Income Tax Return (2025)", "https://www.finance.gov.mp/division-forms/revenue-taxation/2025/f1040cm--2025.pdf", "form"),
            ("form-1040nmi", "Form 1040NMI, Employee's Annual Wage and Salary and Earnings Tax Return (2025)", "https://www.finance.gov.mp/division-forms/revenue-taxation/2025/f1040nmi--2025.pdf", "form"),
            ("schedule-1cm", "Schedule 1CM (Form 1040CM), Additional Income and Adjustments to Income (2025)", "https://www.finance.gov.mp/division-forms/revenue-taxation/2025/s1cm--2025.pdf", "schedule"),
            ("schedule-etc", "Schedule ETC (Form 1040CM), Education Tax Credit (2025)", "https://www.finance.gov.mp/division-forms/revenue-taxation/2025/setc--2025.pdf", "schedule"),
            ("schedule-wsd", "Schedule WSD (Form 1040CM), Wage and Salary Deduction (2025)", "https://www.finance.gov.mp/division-forms/revenue-taxation/2025/swsd--2025.pdf", "schedule"),
        ],
    },
}

BATCH_1 = tuple(j for j, s in STATES.items() if s.get("batch", 1) == 1)  # AL .. MT in queue order
BATCH_2 = tuple(j for j, s in STATES.items() if s.get("batch") == 2)  # NH, NJ, NM, OK, UT, VT, WA
# Batch 3 re-ran the batch-1/2 states whose publishers blocked the European exit;
# ``batch`` keeps their original membership so batch-1/2 rows stay byte-identical.
BATCH_3 = tuple(j for j, s in STATES.items() if s.get("retry_batch") == 3)  # CO, IN, UT
BATCH_4 = tuple(j for j, s in STATES.items() if s.get("batch") == 4)  # PR, GU, MP (territories)
TERRITORY_NAMES = {"us-pr": "Puerto Rico", "us-gu": "Guam", "us-vi": "Virgin Islands", "us-as": "American Samoa",
                   "us-mp": "Northern Mariana Islands"}
BATCH_NOTES = {
    1: "Batch 1 (2026-09-10) = the first ten queue-order states without a current-year resident return ingest: " + ", ".join(BATCH_1) + ".",
    2: "Batch 2 (2026-09-10) = the remaining queue-order states without a current-year resident return ingest, starting at NH: " + ", ".join(BATCH_2) + " (seven; the queue held no further states).",
    3: "Batch 3 (2026-09-10) = retry of the publisher-blocked batch-1/2 states from a US network: " + ", ".join(BATCH_3) + ".",
    4: "Territories pass (2026-09-11) = the five inhabited territories: " + ", ".join(BATCH_4) + " built here; us-vi done by pointer (its publisher's index links the IRS Form 1040); us-as needs_review (Form 390 posted only as an Excel workbook).",
}

# Territory rows without a manifest (territories pass). VI: the Bureau of Internal Revenue's own forms
# index links the IRS Form 1040 for tax year 2025 (mirror code, 48 U.S.C. 1397), already in the corpus.
# AS: the Tax Office posts the 2025 Form 390 only as an Excel workbook of fillable form sheets, which the
# official-documents xlsx path (tabular header/row extraction) cannot represent.
TERRITORY_POINTER_ROWS: dict[str, dict[str, Any]] = {
    "us-vi": {
        "queue_status": "done",
        "source_kind": "official_index_points_to_irs_form",
        "primary_source_url": "https://bir.vi.gov/Form",
        "target_manifest": "manifests/us-irs-individual-income-tax-forms-ty2025.yaml",
        "target_scope": {"jurisdiction": "us", "document_class": "form", "version": FEDERAL_FORMS_VERSION},
        "index_url": "https://bir.vi.gov/Form",
        "index_document_count": 131,
        "taken_count": 0,
        "index_families": [
            "individual income tax returns, tax years 2011-2025 (14): every '1040 U.S. Individual Income Tax Return' entry links the IRS PDF (2025: https://www.irs.gov/pub/irs-prior/f1040--2025.pdf)",
            "Form 1040 INFO, Non-Virgin Islands Source Income of Virgin Islands Residents, tax years 2016-2025 (10): BIR's own attachment form (2025 revision 2025-01-08); not taken",
            "Form 8689 Allocation of Individual Income Tax to the U.S. Virgin Islands (13, IRS PDFs), gross receipts, withholding, excise and other BIR forms (94); not taken",
        ],
        "notes": (
            "Territories pass (2026-09-11): done by pointer. Bona fide Virgin Islands residents file the federal Form 1040 "
            "with the Bureau of Internal Revenue under the mirror code (48 U.S.C. 1397); the Bureau's Forms page "
            "(https://bir.vi.gov/Form, an application whose listing is served by the publisher's own /api/form/find "
            "endpoint, 131 entries) links the tax year 2025 Form 1040 entry to the IRS PDF and posts no Virgin Islands "
            "return or instructions booklet of its own. The IRS TY2025 Form 1040 and instructions are in the corpus as "
            "us/form/irs/ty2025/f1040 and i1040gi (version 2026-09-10-tax-irs-forms-ty2025). BIR's own TY2025 product is "
            "Form 1040 INFO (a residents' attachment, not the return), recorded and not taken. 0 taken."
        ),
    },
    "us-as": {
        "queue_status": "needs_review",
        "source_kind": "official_xlsx_forms_workbook",
        "primary_source_url": "https://www.americansamoa.gov/_files/ugd/4bfff9_a3bcba04ed65461ba9c6e20f503a8725.xlsx?dn=2025%20Tax%20Forms%20Updated-V3-%204.11.2026.xlsx",
        "target_manifest": "manifests/us-as-individual-income-tax-forms-ty2025.yaml",
        "target_scope": {"jurisdiction": "us-as", "document_class": "form", "version": None},
        "index_url": "https://www.americansamoa.gov/tax-office",
        "index_document_count": 15,
        "taken_count": 0,
        "index_families": [
            "Form 390 American Samoa Individual Income Tax Return workbooks, tax years 2020-2025 (7 xlsx): the 2025 workbook (updated V3, 4.11.2026) holds sheets 390, Sch. T8812, 8812(2001), Sch. TEITC, Sch A & B, Sch. C, 390X, 390A, Direct Deposit",
            "'IRS 2000 Tax Table and Instructions' PDFs (2): the IRS 2000 booklet reposted because American Samoa applies the Internal Revenue Code as of 2000-12-31; an IRS publication, not taken",
            "other Tax Office files (6): ARPA child tax credit FAQ, Form T15323, stimulus FAQ, REAL ID policy, driver licence guide, workmen's compensation travel allowance; not taken",
        ],
        "notes": (
            "Territories pass (2026-09-11): needs_review. The American Samoa Government Tax Office page (HTTP 200) "
            "publishes the 2025 Form 390 A.S. Individual Income Tax Return only as an Excel workbook of fillable form "
            "sheets (no PDF, no American Samoa instructions; the page reposts the IRS 2000 tax table and instructions "
            "because the territory applies the Internal Revenue Code as of 2000-12-31, 48 U.S.C. 1661 and A.S.C.A. "
            "11.0403). The official-documents extractor's xlsx path is a header-row table reader and would not "
            "represent a form layout, so nothing was extracted; reviewer to decide on a form-workbook extraction or a "
            "PDF print. 0 taken."
        ),
    },
}

# States whose current-year resident individual income tax return material was
# already ingested (work-order list). target_manifest is the prior manifest; the
# scope version is the prior run's version when a local coverage artifact or a
# release selector names it, otherwise None.
DONE: dict[str, tuple[str, str | None]] = {
    "us-ak": ("manifests/us-ak-title-43-individual-income-tax-2026.yaml", "2026-07-24-ak-individual-income-tax"),
    "us-az": ("manifests/us-az-2026-140es-booklet.yaml", "2026-07-21-az-140es-2026"),
    "us-ca": ("manifests/us-ca-2026-form-540-es-instructions.yaml", "2026-07-23-ca-2026-form-540-es"),
    "us-ct": ("manifests/us-ct-2026-supplement-section-12-704e.yaml", "2026-07-24-ct-income-tax-supplement"),
    "us-fl": ("manifests/us-fl-individual-income-tax-zero-liability.yaml", "2026-07-24-fl-individual-income-tax-zero-liability"),
    "us-ga": ("manifests/us-ga-it-511-2025-official-document.yaml", "2026-07-21-ga-it-511-2025"),
    "us-hi": ("manifests/us-hi-2025-n11-capital-gain-worksheet.yaml", "2026-07-22-hi-2025-n11-capital-gain-worksheet"),
    "us-il": ("manifests/us-il-2026-resident-income-tax-core.yaml", "2026-07-24-il-individual-income-tax-resident-core"),
    "us-ks": ("manifests/us-ks-2026-k40es.yaml", "2026-07-21-ks-k40es-2026"),
    "us-ky": ("manifests/us-ky-2026-740-es.yaml", "2026-740-es"),
    "us-la": ("manifests/us-la-2026-it-540es-instructions.yaml", "2026-07-23-la-2026-it-540es-instructions"),
    "us-ma": ("manifests/us-ma-2026-form-1-es.yaml", "2026-07-22-ma-2026-form-1-es"),
    "us-md": ("manifests/us-md-tax-forms.yaml", None),
    "us-me": ("manifests/us-me-individual-income-tax-rates-2026.yaml", "2026-07-23-me-individual-income-tax-rates-2026"),
    "us-mi": ("manifests/us-mi-2026-income-tax-rate-notice.yaml", "2026-07-21-mi-2026-income-tax-rate-notice"),
    "us-mn": ("manifests/us-mn-income-tax-inflation-adjusted-amounts-2026.yaml", "2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026"),
    "us-mo": ("manifests/us-mo-individual-income-tax-forms.yaml", None),
    "us-nc": ("manifests/us-nc-ty2026-income-tax-core.yaml", "2026-07-26-nc-ty2026-income-tax-core"),
    "us-nd": ("manifests/us-nd-individual-income-tax-forms.yaml", None),
    "us-ne": ("manifests/us-ne-2026-1040n-es.yaml", "2026-07-22-ne-1040n-es-2026"),
    "us-nv": ("manifests/us-nv-individual-income-tax-zero-liability.yaml", "2026-07-24-nv-individual-income-tax-zero-liability"),
    "us-ny": ("manifests/us-ny-tax-current-forms.yaml", "2026-06-05-ny-tax-current-forms"),
    "us-oh": ("manifests/us-oh-individual-income-tax-forms.yaml", None),
    "us-or": ("manifests/us-or-2026-or-estimate.yaml", "2026-07-22-or-estimate-2026"),
    "us-pa": ("manifests/us-pa-personal-income-tax-rates.yaml", "2026-07-21-pa-personal-income-tax-rates"),
    "us-ri": ("manifests/us-ri-pit-adv-2025-22-official-documents.yaml", "2026-07-23-ri-pit-adv-2025-22"),
    "us-sc": ("manifests/us-sc-individual-income-tax-forms.yaml", None),
    "us-sd": ("manifests/us-sd-2026-personal-income-tax-zero-liability.yaml", "2026-07-24-sd-personal-income-tax-zero-liability"),
    "us-tn": ("manifests/us-tn-2026-individual-income-tax-zero-liability-guidance.yaml", "2026-07-24-tn-individual-income-tax-zero-liability-guidance"),
    "us-tx": ("manifests/us-tx-2026-individual-income-tax-prohibition.yaml", "2026-07-24-tx-individual-income-tax-prohibition"),
    "us-va": ("manifests/us-va-tax-forms.yaml", None),
    "us-wi": ("manifests/us-wi-2026-form1-es-instructions.yaml", "2026-07-22-wi-form1-es-2026"),
    "us-wv": ("manifests/us-wv-individual-income-tax-forms.yaml", None),
    "us-wy": ("manifests/us-wy-2026-individual-income-tax-absence.yaml", "2026-07-24-wy-individual-income-tax-absence"),
}


def _coverage_class(jurisdiction: str, version: str | None) -> str | None:
    """Return the document_class whose local coverage artifact carries ``version``."""
    if version is None:
        return None
    base = CORPUS_BASE / "coverage" / jurisdiction
    if not base.is_dir():
        return None
    for class_dir in sorted(base.iterdir()):
        if (class_dir / f"{version}.json").is_file():
            return class_dir.name
    return None


def _state_class(state: dict[str, Any]) -> str:
    return str(state.get("document_class", "form"))


def _state_version(state: dict[str, Any]) -> str:
    if state.get("version"):
        return str(state["version"])
    return STATE_FORMS_VERSION if _state_class(state) == "form" else STATE_GUIDANCE_VERSION


def _state_document(
    jurisdiction: str, state: dict[str, Any], row: tuple[Any, ...] | dict[str, Any]
) -> dict[str, Any]:
    """Build one manifest document.

    ``row`` is either the batch-1 tuple ``(id, title, url, subtype[, landing])`` for a
    single-block PDF or a dict with ``id``, ``title``, ``url``, ``subtype`` and optional
    ``landing``, ``format`` (default ``pdf``) and ``extraction`` (default single block).
    Form-class citation paths keep the batch-1 shape ``us-xx/form/<agency>/ty2025/<id>``;
    guidance scopes use ``us-xx/guidance/<agency>/<id>`` like ``us/guidance/irs/<id>``.
    """
    spec = dict(row) if isinstance(row, dict) else dict(zip(("id", "title", "url", "subtype", "landing"), row, strict=False))
    document_class = _state_class(state)
    landing = spec.get("landing")
    if document_class == "form":
        citation_path = f"{jurisdiction}/form/{state['agency']}/ty{TAX_YEAR}/{spec['id']}"
        source_family = state.get("source_family", "state-resident-individual-income-tax-forms-ty2025")
    else:
        citation_path = f"{jurisdiction}/{document_class}/{state['agency']}/{spec['id']}"
        source_family = f"state-individual-income-tax-{document_class}-ty2025"
    doc = {
        "source_id": f"{jurisdiction}-{state['agency']}-{spec['id']}-ty{TAX_YEAR}",
        "jurisdiction": jurisdiction,
        "document_class": document_class,
        "title": spec["title"],
        "source_url": landing or spec["url"],
        "source_format": spec.get("format", "pdf"),
        "source_as_of": state.get("source_as_of", SOURCE_AS_OF),
        "expression_date": TY_EXPRESSION_DATE,
        "citation_path": citation_path,
        "extraction": spec.get("extraction", SINGLE_BLOCK),
        "metadata": {
            "primary_source": True,
            "source_authority": state["authority"],
            "document_subtype": spec["subtype"],
            "program": "individual_income_tax",
            "tax_year": TAX_YEAR,
            "source_discovery_group": f"{jurisdiction}/{document_class}/individual-income-tax",
            "source_family": source_family,
            "index_url": state["index_url"],
            "discovered_via": f"manual-review:tax-agent-queue; index {state['index_url']}",
        },
    }
    if landing:
        doc["download_url"] = spec["url"]
    if state.get("request"):
        doc["request"] = dict(state["request"])
    return doc


def _write_manifest(path: Path, documents: list[dict[str, Any]], version: str = SOURCE_AS_OF) -> None:
    path.write_text(
        yaml.safe_dump({"version": version, "documents": documents}, sort_keys=False, allow_unicode=True, width=120)
    )


def _probe(session: requests.Session, doc: dict[str, Any]) -> tuple[int, str]:
    """Return (status, content-type) for a document's download URL.

    Documents whose ``request`` asks for direct browser impersonation are probed the
    way the extractor fetches them (curl_cffi, TLS verified); everything else uses a
    plain HEAD with a GET fallback.
    """
    url = doc.get("download_url") or doc["source_url"]
    if (doc.get("request") or {}).get("browser_impersonation_direct"):
        from curl_cffi import requests as curl_requests

        response = curl_requests.get(url, impersonate="chrome120", timeout=60, allow_redirects=True, stream=True)
        try:
            return response.status_code, response.headers.get("content-type", "")
        finally:
            response.close()
    response = session.head(url, allow_redirects=True, timeout=60)
    if response.status_code >= 400 or response.status_code == 405:
        response = session.get(url, allow_redirects=True, timeout=120, stream=True)
    try:
        return response.status_code, response.headers.get("content-type", "")
    finally:
        response.close()


def _verify(documents: list[dict[str, Any]]) -> int:
    failures = 0
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    for doc in documents:
        try:
            status, content_type = _probe(session, doc)
            ok = status == 200 and (
                ("pdf" in content_type) if doc["source_format"] == "pdf" else ("html" in content_type)
            )
            print(f"{'ok ' if ok else 'BAD'} {status} {content_type[:30]:30} {doc['source_id']}")
            failures += 0 if ok else 1
        except Exception as exc:  # noqa: BLE001 - a probe failure is a verification failure
            print(f"BAD --- {exc!r} {doc['source_id']}")
            failures += 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--verify", action="store_true", help="probe every download URL; write nothing")
    parser.add_argument("--only", help="comma-separated territory jurisdictions whose queue rows are added or "
                        "refreshed (state rows are always rewritten from the static tables)")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None

    manifests_dir = ROOT / "manifests"
    federal_forms_path = manifests_dir / "us-irs-individual-income-tax-forms-ty2025.yaml"
    federal_guidance_path = manifests_dir / "us-irs-guidance-2026-inflation-adjustments.yaml"
    state_docs: dict[str, list[dict[str, Any]]] = {
        jur: [_state_document(jur, state, row) for row in state["documents"]]
        for jur, state in STATES.items()
        if "documents" in state
    }

    if args.verify:
        all_docs = FEDERAL_FORMS + FEDERAL_GUIDANCE + [d for docs in state_docs.values() for d in docs]
        failures = _verify(all_docs)
        print(f"verified {len(all_docs)} documents, {failures} failures")
        return 1 if failures else 0

    _write_manifest(federal_forms_path, FEDERAL_FORMS)
    _write_manifest(federal_guidance_path, FEDERAL_GUIDANCE)
    written = [federal_forms_path.name, federal_guidance_path.name]
    state_manifest_paths: dict[str, Path] = {}
    for jur, docs in state_docs.items():
        document_class = _state_class(STATES[jur])
        kind = "forms" if document_class == "form" else document_class
        path = manifests_dir / f"{jur}-individual-income-tax-{kind}-ty2025.yaml"
        _write_manifest(path, docs, str(STATES[jur].get("source_as_of", SOURCE_AS_OF)))
        state_manifest_paths[jur] = path
        written.append(path.name)

    queue_path = manifests_dir / "tax-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    for jur, name in TERRITORY_NAMES.items():
        if only and jur not in only:
            continue
        rows.setdefault(jur, {"jurisdiction": jur, "name": name, "lead_counts": {}, "candidate_sources": []})

    federal = rows["us"]
    federal.update(
        {
            "queue_status": "agent_ready",
            "source_kind": "official_pdf_and_html_forms_instructions",
            "primary_source_url": IRS_1040_INDEX,
            "target_manifest": f"manifests/{federal_forms_path.name}",
            "target_scope": {"jurisdiction": "us", "document_class": "form", "version": FEDERAL_FORMS_VERSION},
            "index_url": IRS_FORMS_INDEX,
            "index_document_count": 35,
            "taken_count": len(FEDERAL_FORMS),
            "notes": (
                "IRS individual income tax core, tax year 2025 (family irs-individual-income-tax-forms-ty2025): "
                "forms/schedules as single-block PDFs, instructions and Publication 17 from the irs.gov HTML "
                "editions (one provision per heading). Forms & Instructions index lists 35 products (popular "
                "forms/instructions/tax table; 1040 family, W-4, 1040-ES, W-9, 4506/4506-T, 2848, 941, W-2/W-3, "
                "9465, SS-4, W-7, 4547) and links the Schedules for Form 1040 page (14 schedules: 1, 1-A, 2, 3, "
                "A-F, H, J, R, SE, EIC, 8812). Taken: 19. Separate manifest "
                f"manifests/{federal_guidance_path.name} (document_class guidance, version "
                f"{FEDERAL_GUIDANCE_VERSION}) adds the 2026 IRB inflation-adjustment items not already in "
                "manifests/us-irs-guidance.yaml: Notice 2026-10, Rev. Proc. 2026-24, Rev. Proc. 2026-26. "
                "Extraction proven 2026-09-10."
            ),
        }
    )

    for jur, row in rows.items():
        if jur == "us":
            continue
        if jur in TERRITORY_POINTER_ROWS:
            row.update(TERRITORY_POINTER_ROWS[jur])
            continue
        if jur in STATES:
            state = STATES[jur]
            batch_note = BATCH_NOTES[state.get("retry_batch", state.get("batch", 1))]
            if "blocked" in state:
                retries = "".join(f" retried {stamp}, same failure" for stamp in state.get("retries", ()))
                row.update(
                    {
                        "queue_status": "blocked_primary_source",
                        "source_kind": "official_pdf_forms_instructions",
                        "primary_source_url": state["index_url"],
                        "target_manifest": None,
                        "target_scope": {"jurisdiction": jur, "document_class": "form", "version": None},
                        "index_url": state["index_url"],
                        "index_document_count": state.get("index_document_count"),
                        "taken_count": 0,
                        "notes": f"{batch_note} Blocked by the publisher: {state['blocked']}{retries}",
                    }
                )
            else:
                docs = state_docs[jur]
                document_class = _state_class(state)
                if document_class == "form":
                    source_kind = "official_pdf_forms_instructions"
                    confirmed = "TY2025 resident individual income tax return material confirmed from the"
                else:
                    source_kind = f"official_{document_class}_no_ty2025_resident_return"
                    confirmed = "No TY2025 resident individual income tax return exists; official guidance confirmed from the"
                row.update(
                    {
                        "queue_status": "agent_ready",
                        "source_kind": source_kind,
                        "primary_source_url": docs[0]["source_url"],
                        "target_manifest": f"manifests/{state_manifest_paths[jur].name}",
                        "target_scope": {"jurisdiction": jur, "document_class": document_class, "version": _state_version(state)},
                        "index_url": state["index_url"],
                        "index_document_count": state["index_document_count"],
                        "taken_count": len(docs),
                        "notes": (
                            f"{batch_note} {confirmed} {state['authority']} index. {state['inventory']} "
                            "Extraction proven 2026-09-10."
                        ),
                    }
                )
                if "index_families" in state:
                    row["index_families"] = list(state["index_families"])
        elif jur in DONE:
            manifest, version = DONE[jur]
            if not (ROOT / manifest).is_file():
                print(f"warning: {jur} done manifest missing: {manifest}", file=sys.stderr)
            document_class = _coverage_class(jur, version)
            row.update(
                {
                    "queue_status": "done",
                    "source_kind": "official_documents_prior_ingest",
                    "primary_source_url": row.get("primary_source_url"),
                    "target_manifest": manifest,
                    "target_scope": {"jurisdiction": jur, "document_class": document_class, "version": version},
                    "taken_count": 0,
                    "notes": (
                        "Current-year individual income tax material already ingested (2026-07 state income tax "
                        "runs / zero-liability states); not re-ingested and not counted toward batch 1. "
                        + (
                            "The prior manifest exists but no local coverage artifact or release selector names its "
                            "version in this checkout; reviewer to confirm the scope."
                            if version is None
                            else "Scope taken from the prior run note / local coverage artifact."
                        )
                    ),
                }
            )
        else:
            row["queue_status"] = "needs_review"
            row["notes"] = f"Not in batch 1 or 2; waits for a later batch. {BATCH_NOTES[2]}"

    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    counts: dict[str, int] = {}
    for row in queue["states"]:
        counts[row["queue_status"]] = counts.get(row["queue_status"], 0) + 1
    queue["status_counts"] = counts
    queue["queue_status"] = "in_progress"
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"wrote {len(written)} manifests: {', '.join(written)}")
    print(f"queue {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
