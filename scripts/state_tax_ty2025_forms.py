"""Static tables for the TY2025 state resident-return forms family of
``scripts/build_state_tax_statute_ty2026_manifests.py`` (``--family forms``; wave 5,
run note ``docs/ingest-runs/2026-09-15-tax.md``, closure elements F01-F05).

Every URL below was confirmed on 2026-09-14 from the revenue department's own forms index
(``index_url``) with the corpus user agent, downloaded and read (``pdfinfo``/``pdftotext``
first page); the printed title and tax year are what page 1 says. A state is listed under
``NOT_TAKEN`` with the evidence when the publisher blocks the corpus client or exposes no
product URL in served HTML, or when the corpus already holds the product (check-pattern
miss). Class is ``form`` for every document (``us-xx/form/<agency>/ty2025/<id>``), the
convention of the 2026-09-10 state forms run (``us-al/form/ador/ty2025/form-40``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
CORPUS_BASE = Path(os.environ.get("AXIOM_CORPUS_BASE", str(ROOT / "data" / "corpus")))
SOURCE_AS_OF = "2026-09-15"
RESEARCH_DATE = "2026-09-14"
FORMS_VERSION = "2026-09-15-income-tax-forms-ty2025"
TAX_YEAR = "2025"
EXPRESSION_DATE = "2025-01-01"  # tax-year-2025 returns cover calendar year 2025
RUN_NOTE = "docs/ingest-runs/2026-09-15-tax.md"
SINGLE_BLOCK = {"segmentation": "single_block"}
# tax.ohio.gov answers the corpus client with a 404 whose body is a "403 Error Page" and
# serves a Chrome user agent (documented in docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md);
# michigan.gov answers 403 to non-browser clients and is served to a chrome120 TLS fingerprint
# (documented in docs/ingest-runs/2026-09-10-wic-fns-guidance-and-state-manuals.md and
# docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md). The extractor tries the corpus
# client first and falls back to curl_cffi with the named fingerprint, TLS verified.
BROWSER_FALLBACK = {"browser_user_agent": True, "browser_impersonation": "chrome120"}


def _doc(
    jurisdiction: str,
    agency: str,
    doc_id: str,
    *,
    title: str,
    url: str,
    subtype: str,
    authority: str,
    index_url: str,
    pages: int,
    first_line: str,
    request: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "source_id": f"{jurisdiction}-{agency}-{doc_id}-ty{TAX_YEAR}",
        "jurisdiction": jurisdiction,
        "document_class": "form",
        "title": title,
        "source_url": url,
        "source_format": "pdf",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": EXPRESSION_DATE,
        "citation_path": f"{jurisdiction}/form/{agency}/ty{TAX_YEAR}/{doc_id}",
        "extraction": SINGLE_BLOCK,
        "metadata": {
            "primary_source": True,
            "source_authority": authority,
            "document_subtype": subtype,
            "program": "individual_income_tax",
            "tax_year": TAX_YEAR,
            "source_family": "state-income-tax-forms-ty2025-closure-2026-09-15",
            "index_url": index_url,
            "discovered_via": f"manual-review:needs-closure-2026-09-14 tax-extractable.csv; index {index_url} (read {RESEARCH_DATE})",
            "page_count_at_research": pages,
            "first_page_first_line": first_line,
        },
    }
    if request:
        doc["request"] = dict(request)
    if note:
        doc["metadata"]["source_note"] = note
    return doc


# jurisdiction -> {"publisher", "index_url", "index_document_count", "index_count_method",
#                  "elements", "documents", "notes"}
STATES: dict[str, dict[str, Any]] = {
    "us-az": {
        "publisher": "Arizona Department of Revenue",
        "index_url": "https://azdor.gov/forms/individual",
        "index_document_count": 23,
        "index_count_method": "product pages listed on the Individual forms index (each carries a per-year table)",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-az", "azdor", "form-140", title="Arizona Form 140 Resident Personal Income Tax Return (2025)",
                 url="https://azdor.gov/sites/default/files/document/FORMS_INDIVIDUAL_2025_140_f.pdf", subtype="return_form",
                 authority="Arizona Department of Revenue", index_url="https://azdor.gov/forms/individual/form-140-resident-personal-income-tax-form-fillable",
                 pages=6, first_line="DO NOT STAPLE ANY ITEMS TO THE RETURN."),
            _doc("us-az", "azdor", "form-140-instructions", title="Arizona Form 140 2025 Resident Personal Income Tax Return Instructions",
                 url="https://azdor.gov/sites/default/files/document/FORMS_INDIVIDUAL_2025_140i.pdf", subtype="instructions",
                 authority="Arizona Department of Revenue", index_url="https://azdor.gov/forms/individual/form-140-resident-personal-income-tax-form-fillable",
                 pages=33, first_line="Arizona Form 140 2025 Resident Personal Income Tax Return"),
            _doc("us-az", "azdor", "form-140-booklet", title="2025 Arizona Form 140 Resident Personal Income Tax Booklet (form, instructions and optional tax tables)",
                 url="https://azdor.gov/sites/default/files/document/FORMS_INDIVIDUAL_2025_140Booklet.pdf", subtype="booklet",
                 authority="Arizona Department of Revenue", index_url="https://azdor.gov/forms/individual/form-140-resident-personal-income-tax-form-fillable",
                 pages=62, first_line="2025 Arizona Form 140 Resident Personal Income Tax Booklet",
                 note="The Optional Tax Tables product page stops at form year 2022; the 2025 tables are inside this booklet."),
        ],
        "notes": "Served the corpus client. The Drupal product pages are inconsistent: the fillable Form 140 page carries 2023-2025 links, the non-fillable and Optional Tax Tables pages end at 2022.",
    },
    "us-ca": {
        "publisher": "California Franchise Tax Board",
        "index_url": "https://www.ftb.ca.gov/forms/index.html",
        "index_document_count": 17,
        "index_count_method": "distinct /forms/2025/ links on the forms index",
        "elements": ["F01", "F02", "F04", "F05"],
        "documents": [
            _doc("us-ca", "ftb", "form-540", title="2025 Form 540 California Resident Income Tax Return",
                 url="https://www.ftb.ca.gov/forms/2025/2025-540.pdf", subtype="return_form",
                 authority="California Franchise Tax Board", index_url="https://www.ftb.ca.gov/forms/index.html",
                 pages=6, first_line="TAXABLE YEAR 2025 FORM 540"),
            _doc("us-ca", "ftb", "form-540-booklet", title="2025 Personal Income Tax Booklet, California 540 Forms & Instructions",
                 url="https://www.ftb.ca.gov/forms/2025/2025-540-booklet.pdf", subtype="instructions",
                 authority="California Franchise Tax Board", index_url="https://www.ftb.ca.gov/forms/2025/2025-540-booklet.html",
                 pages=80, first_line="CALIFORNIA 540 Forms & Instructions 2025 Personal Income Tax Booklet",
                 note="The 2025 tax rate schedules are a section of this booklet; the separate 2025 tax table and rate schedules are already released as us-ca/form/2026-07-23-ca-2025-tax-materials-for-2026-estimates and are not re-taken."),
        ],
        "notes": "Served the corpus client; the booklet is HTML-first with a printable PDF (taken).",
    },
    "us-ct": {
        "publisher": "Connecticut Department of Revenue Services",
        "index_url": "https://portal.ct.gov/drs/drs-forms/current-year-forms/individual-income-tax-forms",
        "index_document_count": 26,
        "index_count_method": "distinct /-/media/drs/forms/2025/income/ PDFs on the individual income tax forms index",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-ct", "drs", "ct-1040", title="Form CT-1040 Connecticut Resident Income Tax Return (2025)",
                 url="https://portal.ct.gov/-/media/drs/forms/2025/income/ct-1040_1225.pdf?rev=7235bf71d64740faa8fdcfe378795c6e&hash=DBEA2EB4DE5D794AF83365C6F47CB4BD",
                 subtype="return_form", authority="Connecticut Department of Revenue Services",
                 index_url="https://portal.ct.gov/drs/drs-forms/current-year-forms/individual-income-tax-forms",
                 pages=4, first_line="Connecticut Resident Income Tax Return 2025"),
            _doc("us-ct", "drs", "ct-1040-instructions", title="2025 Form CT-1040 Connecticut Resident Income Tax Return Instructions (Rev. 12/25)",
                 url="https://portal.ct.gov/-/media/drs/forms/2025/income/2025-ct-1040-instructions_1225.pdf?rev=d898db2e610641b9b3e6efe6f89c6fc2&hash=06D5D5DF44FBF63ABF90A972C507F9FE",
                 subtype="instructions", authority="Connecticut Department of Revenue Services",
                 index_url="https://portal.ct.gov/drs/drs-forms/current-year-forms/individual-income-tax-forms",
                 pages=28, first_line="Department of Revenue Services State of Connecticut (Rev. 12/25)"),
            _doc("us-ct", "drs", "ct-1040-tcs", title="Form CT-1040 TCS 2025 Tax Calculation Schedule",
                 url="https://portal.ct.gov/-/media/drs/forms/2025/income/ct-1040-tcs_1225.pdf?rev=71831cc3f0ca480284b0aca2c0907f60&hash=286872E798AB942591726019D39BE336",
                 subtype="rate_schedule", authority="Connecticut Department of Revenue Services",
                 index_url="https://portal.ct.gov/drs/drs-forms/current-year-forms/calculators-and-tables",
                 pages=5, first_line="Form CT-1040 TCS",
                 note="The 2025 Income Tax Tables PDF on the same page (2025-income-tax-tables.pdf, Microsoft Print To PDF) has no text layer on any page and is not taken (no OCR)."),
        ],
        "notes": "Served the corpus client; Sitecore media URLs carry rev/hash query strings.",
    },
    "us-hi": {
        "publisher": "Hawaii Department of Taxation",
        "index_url": "https://tax.hawaii.gov/forms/a1_b1_1income/",
        "index_document_count": 49,
        "index_count_method": "distinct Rev. 2025 products on the Individual Income Tax (Resident and Nonresident) forms page",
        "elements": ["F01", "F03", "F04", "F05"],
        "documents": [
            _doc("us-hi", "dotax", "form-n-11", title="Form N-11 Hawaii Individual Income Tax Return, Resident (Rev. 2025)",
                 url="https://files.hawaii.gov/tax/forms/current/n11_i.pdf", subtype="return_form",
                 authority="Hawaii Department of Taxation", index_url="https://tax.hawaii.gov/forms/a1_b1_1income/",
                 pages=4, first_line="STATE OF HAWAII - DEPARTMENT OF TAXATION FORM N-11",
                 note="files.hawaii.gov/tax/forms/current/ is not year-stamped; the Rev. 2025 edition was taken on 2026-09-15."),
            _doc("us-hi", "dotax", "form-n-11-instructions", title="2025 N-11 Instructions, Hawaii Resident Income Tax (Rev. 2025)",
                 url="https://files.hawaii.gov/tax/forms/current/n11ins.pdf", subtype="instructions",
                 authority="Hawaii Department of Taxation", index_url="https://tax.hawaii.gov/forms/a1_b1_1income/",
                 pages=52, first_line="2025 N-11 STATE OF HAWAII - DEPARTMENT OF TAXATION"),
            _doc("us-hi", "dotax", "tax-tables", title="2025 Tax Tables, taxable income of less than $100,000 (from the N-11 booklet)",
                 url="https://files.hawaii.gov/tax/forms/2025/25table-on.pdf", subtype="tax_table",
                 authority="Hawaii Department of Taxation", index_url="https://tax.hawaii.gov/forms/d_25table-on/",
                 pages=14, first_line="2025 TAX TABLES"),
        ],
        "notes": "Served the corpus client.",
    },
    "us-il": {
        "publisher": "Illinois Department of Revenue",
        "index_url": "https://tax.illinois.gov/forms/incometax/currentyear/individual.html",
        "index_document_count": 29,
        "index_count_method": "distinct English current-year individual PDFs on the index",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-il", "idor", "form-il-1040", title="2025 Form IL-1040 Individual Income Tax Return",
                 url="https://tax.illinois.gov/content/dam/soi/en/web/tax/forms/incometax/documents/currentyear/individual/il-1040.pdf",
                 subtype="return_form", authority="Illinois Department of Revenue",
                 index_url="https://tax.illinois.gov/forms/incometax/currentyear/il-1040.html",
                 pages=2, first_line="Illinois Department of Revenue 2025 Form IL-1040 Individual Income Tax Return",
                 note="The currentyear path is not year-stamped; the 2025 edition was taken on 2026-09-15."),
            _doc("us-il", "idor", "form-il-1040-instructions", title="2025 Form IL-1040 Instructions",
                 url="https://tax.illinois.gov/content/dam/soi/en/web/tax/forms/incometax/documents/currentyear/individual/il-1040-instr.pdf",
                 subtype="instructions", authority="Illinois Department of Revenue",
                 index_url="https://tax.illinois.gov/forms/incometax/currentyear/il-1040.html",
                 pages=19, first_line="Illinois Department of Revenue 2025 Form IL-1040 Instructions",
                 note="Illinois has a flat 4.95% rate and publishes no tax table."),
        ],
        "notes": "Served the corpus client.",
    },
    "us-ks": {
        "publisher": "Kansas Department of Revenue",
        "index_url": "https://www.ksrevenue.gov/forms-ii.html",
        "index_document_count": 7,
        "index_count_method": "PDFs with the 25 year suffix on the Individual Income forms page (186 PDF links across all years)",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-ks", "kdor", "form-k-40", title="K-40 2025 Kansas Individual Income Tax",
                 url="https://www.ksrevenue.gov/pdf/k-4025.pdf", subtype="return_form",
                 authority="Kansas Department of Revenue", index_url="https://www.ksrevenue.gov/forms-ii.html",
                 pages=2, first_line="K-40 2025 KANSAS INDIVIDUAL INCOME TAX"),
            _doc("us-ks", "kdor", "individual-income-tax-instruction-booklet", title="2025 Individual Income Tax Instruction Booklet (K-40 instructions and tax tables)",
                 url="https://www.ksrevenue.gov/pdf/ip25.pdf", subtype="instructions",
                 authority="Kansas Department of Revenue", index_url="https://www.ksrevenue.gov/forms-ii.html",
                 pages=36, first_line="2025 Individual Income Tax"),
        ],
        "notes": "Served the corpus client; the tax tables are inside the booklet.",
    },
    "us-la": {
        "publisher": "Louisiana Department of Revenue",
        "index_url": "https://revenue.louisiana.gov/tax-forms/individuals/?tax_type=individual",
        "index_document_count": 5,
        "index_count_method": "links containing 2025 on the individuals tax-forms page (249 dam.ldr.la.gov links across all years)",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-la", "ldr", "form-it-540", title="2025 Louisiana Resident Income Tax Return, Form IT-540 (web, 2D barcode)",
                 url="https://dam.ldr.la.gov/taxforms/IT540WEB-BC-2025-F.pdf", subtype="return_form",
                 authority="Louisiana Department of Revenue", index_url="https://revenue.louisiana.gov/tax-forms/individuals/?tax_type=individual",
                 pages=17, first_line="FILE ONLINE ON LaTAP (cover page)"),
            _doc("us-la", "ldr", "form-it-540-instructions", title="2025 Louisiana Resident Income Tax Return Instructions, Form IT-540 (revised 7/26)",
                 url="https://dam.ldr.la.gov/taxforms/IT540i-WEB-2025-Revised-7-26.pdf", subtype="instructions",
                 authority="Louisiana Department of Revenue", index_url="https://revenue.louisiana.gov/tax-forms/individuals/?tax_type=individual",
                 pages=16, first_line="WHAT'S NEW FOR LOUISIANA 2025 INDIVIDUAL INCOME TAX?",
                 note="No TY2025 IT-540 tax table is listed (the latest listed is 2024); Louisiana's flat rate for 2025 is printed in the instructions."),
        ],
        "notes": "Served the corpus client; PDFs are on the department's dam.ldr.la.gov asset host.",
    },
    "us-ma": {
        "publisher": "Massachusetts Department of Revenue",
        "index_url": "https://www.mass.gov/lists/2025-massachusetts-personal-income-tax-forms-and-instructions",
        "index_document_count": 45,
        "index_count_method": "distinct mass.gov/doc/2025-.../download links on the 2025 personal income tax forms list",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-ma", "dor", "form-1", title="2025 Form 1 Massachusetts Resident Income Tax Return",
                 url="https://www.mass.gov/doc/2025-form-1-massachusetts-resident-income-tax-return/download", subtype="return_form",
                 authority="Massachusetts Department of Revenue", index_url="https://www.mass.gov/lists/2025-massachusetts-personal-income-tax-forms-and-instructions",
                 pages=4, first_line="2025 Form 1 Massachusetts Resident Income Tax Return"),
            _doc("us-ma", "dor", "form-1-instructions", title="2025 Form 1 Instructions, Massachusetts Resident Income Tax",
                 url="https://www.mass.gov/doc/2025-form-1-instructions/download", subtype="instructions",
                 authority="Massachusetts Department of Revenue", index_url="https://www.mass.gov/lists/2025-massachusetts-personal-income-tax-forms-and-instructions",
                 pages=40, first_line="Department of Revenue Commonwealth of Massachusetts Form 1 2025",
                 note="Massachusetts has flat Part B/Part A rates and publishes no tax table."),
        ],
        "notes": "Served the corpus client (no impersonation needed for the document downloads).",
    },
    "us-me": {
        "publisher": "Maine Revenue Services",
        "index_url": "https://www.maine.gov/revenue/tax-return-forms/individual-income-tax-2025",
        "index_document_count": 28,
        "index_count_method": "distinct PDF hrefs on the Individual Income Tax 2025 forms page",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-me", "mrs", "form-1040me", title="2025 Form 1040ME Maine Individual Income Tax",
                 url="https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/25_1040ME_fillable.pdf", subtype="return_form",
                 authority="Maine Revenue Services", index_url="https://www.maine.gov/revenue/tax-return-forms/individual-income-tax-2025",
                 pages=3, first_line="2025 MAINE INDIVIDUAL INCOME TAX"),
            _doc("us-me", "mrs", "form-1040me-general-instructions", title="2025 Form 1040ME General Instructions (with cover page)",
                 url="https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/25_1040me_gen_instr_w_cover_pg.pdf", subtype="instructions",
                 authority="Maine Revenue Services", index_url="https://www.maine.gov/revenue/tax-return-forms/individual-income-tax-2025",
                 pages=13, first_line="Maine Revenue Services"),
            _doc("us-me", "mrs", "tax-tables", title="2025 Maine Income Tax Table",
                 url="https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/25_tax_tables.pdf", subtype="tax_table",
                 authority="Maine Revenue Services", index_url="https://www.maine.gov/revenue/tax-return-forms/individual-income-tax-2025",
                 pages=5, first_line="2025 MAINE INCOME TAX TABLE"),
            _doc("us-me", "mrs", "tax-rate-schedules", title="2025 Maine Individual Income Tax Rate Schedules",
                 url="https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/ind_tax_rate_sched_2025.pdf", subtype="rate_schedule",
                 authority="Maine Revenue Services", index_url="https://www.maine.gov/revenue/tax-return-forms/individual-income-tax-2025",
                 pages=1, first_line="State of Maine - Individual Income Tax"),
        ],
        "notes": "Served the corpus client.",
    },
    "us-mi": {
        "publisher": "Michigan Department of Treasury",
        "index_url": "https://www.michigan.gov/taxes/iit-forms/2025-individual-income-tax-forms",
        "index_document_count": 57,
        "index_count_method": "distinct PDF hrefs on the 2025 Individual Income Tax Forms page (served to the Chrome fingerprint only)",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-mi", "treasury", "form-mi-1040", title="2025 MI-1040 Michigan Individual Income Tax Return",
                 url="https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2025/MI-1040.pdf?rev=c1d9fa606c614f799b4aa38843fa87f4&hash=CFBA1487FAEED3EF2D548B7E52D889BA",
                 subtype="return_form", authority="Michigan Department of Treasury",
                 index_url="https://www.michigan.gov/taxes/iit-forms/2025-individual-income-tax-forms",
                 pages=3, first_line="2025 MICHIGAN Individual Income Tax Return MI-1040", request=BROWSER_FALLBACK,
                 note="michigan.gov answers HTTP 403 to the corpus client on every page and PDF path and serves the chrome120 fingerprint (browser fallback documented for this host in the 2026-09-10 WIC and 2026-09-14 LIHEAP run notes)."),
            _doc("us-mi", "treasury", "mi-1040-book", title="2025 Michigan Individual Income Tax Forms and Instructions (MI-1040 Book)",
                 url="https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2025/MI-1040-Book.pdf?rev=5c0c79baa2d54570bd4a1f82749c0ecd&hash=FB9893FCE181585B595C00563B0FE271",
                 subtype="instructions", authority="Michigan Department of Treasury",
                 index_url="https://www.michigan.gov/taxes/iit-forms/2025-individual-income-tax-forms",
                 pages=40, first_line="Individual Income Tax FORMS AND INSTRUCTIONS MICHIGAN 2025", request=BROWSER_FALLBACK,
                 note="Michigan has a flat 4.25% rate and publishes no tax table; the exemption amounts are printed in the book."),
        ],
        "notes": "michigan.gov needs the documented chrome120 fallback (corpus client 403 site-wide).",
    },
    "us-mn": {
        "publisher": "Minnesota Department of Revenue",
        "index_url": "https://www.revenue.state.mn.us/form-search?search_text=income+tax&field_tax_type=106&field_tax_year=12606",
        "index_document_count": 13,
        "index_count_method": "results reported by the form search for income tax, tax year 2025 (10 distinct PDFs)",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-mn", "department-of-revenue", "form-m1", title="2025 Form M1, Minnesota Individual Income Tax",
                 url="https://www.revenue.state.mn.us/sites/default/files/2026-03/m1-25.pdf", subtype="return_form",
                 authority="Minnesota Department of Revenue", index_url="https://www.revenue.state.mn.us/form-search?search_text=income+tax&field_tax_type=106&field_tax_year=12606",
                 pages=2, first_line="2025 Form M1, Individual Income Tax"),
            _doc("us-mn", "department-of-revenue", "form-m1-instructions", title="2025 Minnesota Individual Income Tax Instructions (Form M1)",
                 url="https://www.revenue.state.mn.us/sites/default/files/2026-07/m1-inst-25.pdf", subtype="instructions",
                 authority="Minnesota Department of Revenue", index_url="https://www.revenue.state.mn.us/form-search?search_text=income+tax&field_tax_type=106&field_tax_year=12606",
                 pages=40, first_line="2025 Minnesota Individual Income Tax",
                 note="File dated 2026-07 (revised mid-season); the tax tables are inside the instructions."),
        ],
        "notes": "Served the corpus client (the form search is server-rendered).",
    },
    "us-mo": {
        "publisher": "Missouri Department of Revenue",
        "index_url": "https://dor.mo.gov/forms/?formName=&category=7&year=2025&searchForms=Search+Forms",
        "index_document_count": 35,
        "index_count_method": "distinct PDFs listed for Personal Tax - Individual Income Tax, year 2025",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-mo", "dor", "form-mo-1040", title="2025 Form MO-1040 Individual Income Tax Return, Long Form (fillable calculating)",
                 url="https://dor.mo.gov/forms/MO-1040%20Fillable%20Calculating_2025.pdf", subtype="return_form",
                 authority="Missouri Department of Revenue", index_url="https://dor.mo.gov/forms/?formName=&category=7&year=2025&searchForms=Search+Forms",
                 pages=32, first_line="2025 Individual Income Tax Return - Long Form"),
            _doc("us-mo", "dor", "form-mo-1040-instructions", title="2025 Form MO-1040 Individual Income Tax Long Form Instructions",
                 url="https://dor.mo.gov/forms/MO-1040%20Instructions_2025.pdf", subtype="instructions",
                 authority="Missouri Department of Revenue", index_url="https://dor.mo.gov/forms/?formName=&category=7&year=2025&searchForms=Search+Forms",
                 pages=53, first_line="2025 Form MO-1040 Individual Income Tax Long Form"),
            _doc("us-mo", "dor", "tax-chart", title="2025 Tax Chart (Missouri individual income tax)",
                 url="https://dor.mo.gov/forms/2025%20Tax%20Chart_2025.pdf", subtype="rate_schedule",
                 authority="Missouri Department of Revenue", index_url="https://dor.mo.gov/forms/?formName=&category=7&year=2025&searchForms=Search+Forms",
                 pages=1, first_line="2025 Tax Chart"),
        ],
        "notes": "Served the corpus client.",
    },
    "us-nc": {
        "publisher": "North Carolina Department of Revenue",
        "index_url": "https://www.ncdor.gov/taxes-forms/individual-income-tax/individual-income-tax-forms-instructions",
        "index_document_count": 11,
        "index_count_method": "2025 product landing pages linked from the individual income tax forms index",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-nc", "ncdor", "form-d-400", title="2025 Form D-400 North Carolina Individual Income Tax Return (web-fill version)",
                 url="https://www.ncdor.gov/2025-d-400-web-filled-version/open", subtype="return_form",
                 authority="North Carolina Department of Revenue", index_url="https://www.ncdor.gov/2025-d-400-individual-income-tax-return",
                 pages=3, first_line="Do Not Include This Page (web fill-in cover sheet)"),
            _doc("us-nc", "ncdor", "form-d-401-instructions", title="2025 Form D-401 North Carolina Individual Income Tax Instructions",
                 url="https://www.ncdor.gov/2025-d-401-individual-income-tax-instructions/open", subtype="instructions",
                 authority="North Carolina Department of Revenue", index_url="https://www.ncdor.gov/2025-d-401-individual-income-tax-instructions",
                 pages=28, first_line="Form D-401",
                 note="North Carolina has a flat rate (4.25% for 2025) and publishes no tax table."),
        ],
        "notes": "Served the corpus client.",
    },
    "us-nd": {
        "publisher": "North Dakota Office of State Tax Commissioner",
        "index_url": "https://www.tax.nd.gov/forms",
        "index_document_count": 22,
        "index_count_method": "distinct PDFs under /forms/individual/2025-iit/ on the forms index",
        "elements": ["F01", "F02", "F03"],
        "documents": [
            _doc("us-nd", "otc", "form-nd-1", title="2025 Form ND-1 Individual Income Tax Return",
                 url="https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2025-iit/28702-form-nd-1-2025.pdf", subtype="return_form",
                 authority="North Dakota Office of State Tax Commissioner", index_url="https://www.tax.nd.gov/forms",
                 pages=2, first_line="INDIVIDUAL INCOME TAX RETURN"),
            _doc("us-nd", "otc", "individual-income-tax-booklet", title="2025 North Dakota Individual Income Tax Booklet (Form ND-1 instructions and tables)",
                 url="https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2025-iit/2025-individual-income-tax-booklet.pdf", subtype="instructions",
                 authority="North Dakota Office of State Tax Commissioner", index_url="https://www.tax.nd.gov/forms",
                 pages=31, first_line="2025"),
        ],
        "notes": "Served the corpus client; the tax tables are inside the booklet.",
    },
    "us-ne": {
        "publisher": "Nebraska Department of Revenue",
        "index_url": "https://revenue.nebraska.gov/about/forms/individual-income-tax-forms",
        "index_document_count": 21,
        "index_count_method": "distinct PDFs under /doc/tax-forms/2025/ on the individual income tax forms index",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-ne", "dor", "form-1040n", title="Nebraska Individual Income Tax Return, Form 1040N (2025)",
                 url="https://revenue.nebraska.gov/sites/default/files/doc/tax-forms/2025/f_1040N.pdf", subtype="return_form",
                 authority="Nebraska Department of Revenue", index_url="https://revenue.nebraska.gov/about/forms/individual-income-tax-forms",
                 pages=3, first_line="Nebraska Individual Income Tax Return FORM 1040N 2025"),
            _doc("us-ne", "dor", "individual-income-tax-booklet", title="2025 Nebraska Individual Income Tax and Amended Return Booklet",
                 url="https://revenue.nebraska.gov/sites/default/files/doc/tax-forms/2025/f_Individual_Income_Tax_Booklet.pdf", subtype="instructions",
                 authority="Nebraska Department of Revenue", index_url="https://revenue.nebraska.gov/about/forms/individual-income-tax-forms",
                 pages=51, first_line="2025"),
            _doc("us-ne", "dor", "tax-table", title="2025 Nebraska Tax Table",
                 url="https://revenue.nebraska.gov/sites/default/files/doc/tax-forms/2025/2025_Tax_Tables.pdf", subtype="tax_table",
                 authority="Nebraska Department of Revenue", index_url="https://revenue.nebraska.gov/about/forms/individual-income-tax-forms",
                 pages=5, first_line="2025 Nebraska Tax Table"),
        ],
        "notes": "Served the corpus client.",
    },
    "us-ny": {
        "publisher": "New York State Department of Taxation and Finance",
        "index_url": "https://www.tax.ny.gov/forms/income_fullyear_forms.htm",
        "index_document_count": 25,
        "index_count_method": "form pages linked on the full-year resident forms index",
        "elements": ["F01"],
        "documents": [
            _doc("us-ny", "tax", "it-201", title="Form IT-201 Resident Income Tax Return, full year January 1, 2025, through December 31, 2025",
                 url="https://www.tax.ny.gov/pdf/current_forms/it/it201_fill_in.pdf", subtype="return_form",
                 authority="New York State Department of Taxation and Finance", index_url="https://www.tax.ny.gov/forms/income_fullyear_forms.htm",
                 pages=4, first_line="IT-201 Department of Taxation and Finance Resident Income Tax Return",
                 note="The IT-201-I instructions (with the tax tables and rate schedules) are already released in us-ny/form/2026-06-05-ny-tax-current-forms; only the form is taken. The current_forms path is not year-stamped."),
        ],
        "notes": "Served the corpus client; the IT-201 link passes through an e-file interstitial page before the PDF.",
    },
    "us-oh": {
        "publisher": "Ohio Department of Taxation",
        "index_url": "https://tax.ohio.gov/individual/get-a-form",
        "index_document_count": 5,
        "index_count_method": "2025 individual / SD 100 products linked on the Get a Form page",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-oh", "odt", "form-it-1040", title="2025 Ohio IT 1040 Individual Income Tax Return (original, fillable bundle with schedules)",
                 url="https://tax.ohio.gov/static/forms/ohio_individual/individual/2025/1040-bundle-original-fi.pdf", subtype="return_form",
                 authority="Ohio Department of Taxation", index_url="https://tax.ohio.gov/individual/get-a-form",
                 pages=13, first_line="2025 Ohio IT 1040 Individual Income Tax Return", request=BROWSER_FALLBACK,
                 note="tax.ohio.gov answers the corpus client with a 404 whose body is a 403 error page and serves a Chrome user agent (browser fallback documented for this host in the 2026-09-14 run note)."),
            _doc("us-oh", "odt", "it-1040-sd-100-instructions", title="Tax Year 2025 Instructions for Filing Original and Amended Individual Income Tax (IT 1040) and School District Income Tax (SD 100)",
                 url="https://dam.assets.ohio.gov/image/upload/v1767095693/tax.ohio.gov/forms/ohio_individual/individual/2025/it1040-booklet.pdf", subtype="instructions",
                 authority="Ohio Department of Taxation", index_url="https://tax.ohio.gov/individual/get-a-form",
                 pages=64, first_line="Tax Year 2025 Instructions for Filing Original and Amended: Individual Income Tax (IT 1040), School District Income Tax (SD 100)",
                 note="Hosted on the state's dam.assets.ohio.gov asset host, which serves the corpus client; the brackets are on page 18 (Ohio publishes brackets, no tax table)."),
        ],
        "notes": "tax.ohio.gov needs the documented Chrome fallback; dam.assets.ohio.gov served the corpus client.",
    },
    "us-or": {
        "publisher": "Oregon Department of Revenue",
        "index_url": "https://www.oregon.gov/dor/programs/individuals/Pages/default.aspx",
        "index_document_count": 3,
        "index_count_method": "PDF links on the individuals program page (the forms library at /dor/forms/Pages/default.aspx is a JavaScript SharePoint list with no links in the served HTML)",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-or", "dor", "form-or-40", title="2025 Form OR-40 Oregon Individual Income Tax Return for Full-year Residents",
                 url="https://www.oregon.gov/dor/forms/FormsPubs/form-or-40_101-040_2025.pdf", subtype="return_form",
                 authority="Oregon Department of Revenue", index_url="https://www.oregon.gov/dor/programs/individuals/Pages/default.aspx",
                 pages=8, first_line="2025 Form OR-40 Oregon Department of Revenue Oregon Individual Income Tax Return for Full-year Residents"),
            _doc("us-or", "dor", "form-or-40-instructions", title="2025 Form OR-40 Instructions, Oregon Individual Income Tax Full-year Resident (updated January 29, 2026)",
                 url="https://www.oregon.gov/dor/forms/FormsPubs/form-or-40-inst_101-040-1_2025.pdf", subtype="instructions",
                 authority="Oregon Department of Revenue", index_url="https://www.oregon.gov/dor/programs/individuals/Pages/default.aspx",
                 pages=32, first_line="These instructions were updated on January 29, 2026 to correct the Oregon Kids Credit instructions and worksheet",
                 note="The tax tables and rate charts are inside the instructions."),
        ],
        "notes": "Served the corpus client.",
    },
    "us-ri": {
        "publisher": "Rhode Island Division of Taxation",
        "index_url": "https://tax.ri.gov/forms/individual-tax-forms/personal-income-tax-forms",
        "index_document_count": 27,
        "index_count_method": "file-list items labelled (2025) on the personal income tax forms page",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-ri", "tax", "ri-1040", title="2025 Form RI-1040 Resident Individual Income Tax Return",
                 url="https://tax.ri.gov/sites/g/files/xkgbur541/files/2026-01/2025_1040WE_w.pdf", subtype="return_form",
                 authority="Rhode Island Division of Taxation", index_url="https://tax.ri.gov/forms/individual-tax-forms/personal-income-tax-forms",
                 pages=5, first_line="State of Rhode Island Division of Taxation 2025 Form RI-1040 Resident Individual Income Tax Return"),
            _doc("us-ri", "tax", "ri-1040-instructions", title="2025 Instructions for Filing RI-1040 (full year Rhode Island residents)",
                 url="https://tax.ri.gov/sites/g/files/xkgbur541/files/2025-12/2025%201040R%20Instructions%20122025.pdf", subtype="instructions",
                 authority="Rhode Island Division of Taxation", index_url="https://tax.ri.gov/forms/individual-tax-forms/personal-income-tax-forms",
                 pages=13, first_line="2025 INSTRUCTIONS FOR FILING RI-1040"),
            _doc("us-ri", "tax", "tax-tables", title="2025 Rhode Island Tax Tables (with the 2025 tax rate schedule)",
                 url="https://tax.ri.gov/sites/g/files/xkgbur541/files/2026-01/2025%20RI%20Tax%20Tables_Full.pdf", subtype="tax_table",
                 authority="Rhode Island Division of Taxation", index_url="https://tax.ri.gov/forms/individual-tax-forms/personal-income-tax-forms",
                 pages=7, first_line="RHODE ISLAND TAX RATE SCHEDULE 2025"),
            _doc("us-ri", "tax", "tax-rate-schedule-and-worksheets", title="2025 Rhode Island Tax Rate Schedule and Worksheets",
                 url="https://tax.ri.gov/sites/g/files/xkgbur541/files/2026-01/2025%20Tax%20Rate%20and%20Worksheets.pdf", subtype="rate_schedule",
                 authority="Rhode Island Division of Taxation", index_url="https://tax.ri.gov/forms/individual-tax-forms/personal-income-tax-forms",
                 pages=1, first_line="2025 RHODE ISLAND TAX RATE SCHEDULE AND WORKSHEETS"),
        ],
        "notes": "Served the corpus client.",
    },
    "us-sc": {
        "publisher": "South Carolina Department of Revenue",
        "index_url": "https://dor.sc.gov/find-a-form?search_api_fulltext=sc1040&field_category=individual_income&field_document_type=All&field_tax_year=All",
        "index_document_count": 7,
        "index_count_method": "PDFs with the _2025 suffix in the SC1040 search of the individual income category",
        "elements": ["F01", "F02", "F03", "F05"],
        "documents": [
            _doc("us-sc", "dor", "sc1040", title="2025 SC1040 South Carolina Individual Income Tax Return",
                 url="https://dor.sc.gov/sites/dor/files/forms/SC1040_2025.pdf", subtype="return_form",
                 authority="South Carolina Department of Revenue", index_url="https://dor.sc.gov/find-a-form?search_api_fulltext=sc1040&field_category=individual_income&field_document_type=All&field_tax_year=All",
                 pages=3, first_line="1350 SC1040 STATE OF SOUTH CAROLINA DEPARTMENT OF REVENUE 2025 INDIVIDUAL INCOME TAX RETURN"),
            _doc("us-sc", "dor", "sc1040-instructions", title="SC1040 Instructions 2025, Individual Income Tax Instructions (August 2025)",
                 url="https://dor.sc.gov/sites/dor/files/forms/SC1040Instr_2025.pdf", subtype="instructions",
                 authority="South Carolina Department of Revenue", index_url="https://dor.sc.gov/find-a-form?search_api_fulltext=sc1040&field_category=individual_income&field_document_type=All&field_tax_year=All",
                 pages=26, first_line="SC1040 Instructions 2025 Individual Income Tax Instructions"),
            _doc("us-sc", "dor", "sc1040tt", title="2025 South Carolina Individual Income Tax Tables (revised 6/17/25)",
                 url="https://dor.sc.gov/sites/dor/files/forms/SC1040TT_2025.pdf", subtype="tax_table",
                 authority="South Carolina Department of Revenue", index_url="https://dor.sc.gov/find-a-form?search_api_fulltext=sc1040&field_category=individual_income&field_document_type=All&field_tax_year=All",
                 pages=4, first_line="2025 South Carolina Individual Income Tax Tables (Revised 6/17/25)"),
        ],
        "notes": "Served the corpus client (server-rendered Drupal search).",
    },
    "us-va": {
        "publisher": "Virginia Department of Taxation",
        "index_url": "https://www.tax.virginia.gov/forms/search?category=1&year=657",
        "index_document_count": 40,
        "index_count_method": "PDF hrefs on the Individual Income Tax forms search for year 2025",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-va", "tax", "form-760", title="2025 Virginia Form 760 Resident Income Tax Return",
                 url="https://www.tax.virginia.gov/sites/default/files/taxforms/individual-income-tax/2025/760-2025.pdf", subtype="return_form",
                 authority="Virginia Department of Taxation", index_url="https://www.tax.virginia.gov/forms/search?category=1&year=657",
                 pages=2, first_line="WEB 2025 Virginia Form 760 Resident Income Tax Return File by May 1, 2026"),
            _doc("us-va", "tax", "form-760-instructions", title="2025 Form 760 Resident Individual Income Tax Instructions",
                 url="https://www.tax.virginia.gov/sites/default/files/vatax-pdf/2025-760-instructions.pdf", subtype="instructions",
                 authority="Virginia Department of Taxation", index_url="https://www.tax.virginia.gov/forms/search?category=1&year=657",
                 pages=43, first_line="VIRGINIA 2025 Form 760 Resident Individual Income Tax Instructions"),
            _doc("us-va", "tax", "tax-table", title="2025 Virginia Tax Table and Tax Rate Schedule",
                 url="https://www.tax.virginia.gov/sites/default/files/vatax-pdf/tax-table-2025.pdf", subtype="tax_table",
                 authority="Virginia Department of Taxation", index_url="https://www.tax.virginia.gov/forms/search?category=1&year=657",
                 pages=9, first_line="TAX RATE SCHEDULE IF YOUR VIRGINIA TAXABLE INCOME IS: Not over $3,000, your tax is 2% of your Virginia taxable income."),
        ],
        "notes": "Served the corpus client.",
    },
    "us-wi": {
        "publisher": "Wisconsin Department of Revenue",
        "index_url": "https://www.revenue.wi.gov/Pages/Form/2025Individual.aspx",
        "index_document_count": 173,
        "index_count_method": "distinct TaxForms2025/*.pdf links on the 2025 Individual forms page",
        "elements": ["F01", "F02", "F03", "F04", "F05"],
        "documents": [
            _doc("us-wi", "dor", "form-1", title="2025 Form 1 Wisconsin Income Tax",
                 url="https://www.revenue.wi.gov/TaxForms2025/2025-Form1.pdf", subtype="return_form",
                 authority="Wisconsin Department of Revenue", index_url="https://www.revenue.wi.gov/Pages/Form/2025Individual.aspx",
                 pages=5, first_line="1 Wisconsin income tax For the year Jan. 1-Dec. 31, 2025"),
            _doc("us-wi", "dor", "form-1-instructions", title="2025 Form 1 Instructions, Wisconsin Income Tax",
                 url="https://www.revenue.wi.gov/TaxForms2025/2025-Form1-Inst.pdf", subtype="instructions",
                 authority="Wisconsin Department of Revenue", index_url="https://www.revenue.wi.gov/Pages/Form/2025Individual.aspx",
                 pages=46, first_line="1 Wisconsin Income Tax 2025 Form 1 Instructions",
                 note="The tax table and standard deduction table are inside the instructions."),
        ],
        "notes": "Served the corpus client.",
    },
    "us-wv": {
        "publisher": "West Virginia Tax Division",
        "index_url": "https://tax.wv.gov/Individuals/Pages/Individuals.aspx",
        "index_document_count": 20,
        "index_count_method": "distinct /Documents/PIT/2025/*.pdf links on the Individuals page",
        "elements": ["F01", "F02", "F03", "F04"],
        "documents": [
            _doc("us-wv", "tax", "it-140-forms-and-instructions", title="2025 West Virginia Personal Income Tax Forms and Instructions (IT-140 booklet)",
                 url="https://tax.wv.gov/Documents/PIT/2025/it140.PersonalIncomeTaxFormsAndInstructions.2025.pdf", subtype="booklet",
                 authority="West Virginia Tax Division", index_url="https://tax.wv.gov/Individuals/Pages/Individuals.aspx",
                 pages=56, first_line="2025 West Virginia Personal Income Tax Forms & Instructions",
                 note="No standalone IT-140 form PDF is linked for 2025; the return form is inside this combined booklet."),
            _doc("us-wv", "tax", "it-140-tax-table", title="2025 West Virginia Tax Table",
                 url="https://tax.wv.gov/Documents/PIT/2025/it140.TaxTable.2025.pdf", subtype="tax_table",
                 authority="West Virginia Tax Division", index_url="https://tax.wv.gov/Individuals/Pages/Individuals.aspx",
                 pages=5, first_line="2025 WEST VIRGINIA TAX TABLE"),
            _doc("us-wv", "tax", "it-140-tax-rate-schedules", title="2025 West Virginia Tax Rate Schedules",
                 url="https://tax.wv.gov/Documents/PIT/2025/it140.TaxRateSchedules.2025.pdf", subtype="rate_schedule",
                 authority="West Virginia Tax Division", index_url="https://tax.wv.gov/Individuals/Pages/Individuals.aspx",
                 pages=1, first_line="2025 TAX RATE SCHEDULES RATE SCHEDULE I"),
        ],
        "notes": "Served the corpus client.",
    },
}

# Publisher blocks and check-pattern misses, with the evidence.
NOT_TAKEN: dict[str, dict[str, Any]] = {
    "us-ky": {
        "queue_status": "blocked_primary_source",
        "publisher": "Kentucky Department of Revenue",
        "index_url": "https://revenue.ky.gov/Get-Help/Pages/Forms.aspx",
        "reason": "The Find a Form page (HTTP 200, 86 KB) is a SharePoint document-search web part populated client-side (docsearch.js); the served HTML carries no form PDF links, and the former current-year forms pages (Forms/Pages/Current-Year-Individual-Income-Tax-Forms.aspx, Forms/Pages/default.aspx) answer 404. No 740 URL could be confirmed from an index; nothing guessed.",
    },
    "us-md": {
        "queue_status": "blocked_primary_source",
        "publisher": "Comptroller of Maryland",
        "index_url": "https://services.marylandcomptroller.gov/taxes/en/individual-income-tax-forms-and-instructions?id=kb_article_view&sysparm_article=KB0010191",
        "reason": "marylandtaxes.gov redirects to marylandcomptroller.gov whose 2025 forms paths answer 404; the forms link on the home page is a ServiceNow knowledge-base article (HTTP 200, 923 KB) whose served HTML holds one Angular template link and no PDF or attachment references; the legacy forms/current_forms/502.pdf path redirects to a 404 (same finding as the 2026-09-13 amounts probe). Not worked around.",
    },
    "us-pa": {
        "queue_status": "blocked_primary_source",
        "publisher": "Pennsylvania Department of Revenue",
        "index_url": "https://www.pa.gov/agencies/revenue/forms-and-publications/forms-for-individuals",
        "reason": "The Personal Income Tax Forms entry redirects to a Coveo-driven search listing (forms-and-publications.html#f-copapwptopic=Personal%20Income%20Tax) whose served HTML carries one unrelated PDF link and no PA-40 reference (plain and Chrome user agents alike); no PA-40 URL could be confirmed from an index; nothing guessed.",
    },
    "us-co": {
        "queue_status": "done",
        "publisher": "Colorado Department of Revenue",
        "index_url": "https://tax.colorado.gov/individual-income-tax-forms",
        "reason": "Check-pattern miss: the released us-co/form/2026-09-10-tax-state-forms-ty2025 scope already carries the 2025 DR 0104 Colorado Individual Income Tax Return and the DR 0104 Book (F01 ALREADY-HELD).",
    },
    "us-ia": {
        "queue_status": "done",
        "publisher": "Iowa Department of Revenue",
        "index_url": "https://revenue.iowa.gov/forms/common-forms/individual-income-tax",
        "reason": "Check-pattern miss: the released us-ia/form/2026-09-10-tax-state-forms-ty2025 scope already carries the 2025 IA 1040 Iowa Individual Income Tax Return (41-001) and the expanded instructions (F01 ALREADY-HELD).",
    },
}


def manifest_path(jurisdiction: str) -> Path:
    return MANIFESTS / f"{jurisdiction}-individual-income-tax-forms-ty2025-closure.yaml"


def build_forms(*, verify_only: bool = False) -> None:
    documents = [d for state in STATES.values() for d in state["documents"]]
    if verify_only:
        import requests

        session = requests.Session()
        session.headers["User-Agent"] = (
            "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) https://github.com/TheAxiomFoundation/axiom-corpus"
        )
        failures = 0
        for doc in documents:
            try:
                response = session.get(doc["source_url"], timeout=90, stream=True, headers={"Range": "bytes=0-1023"})
                ctype = response.headers.get("Content-Type", "")
                head = next(response.iter_content(1024), b"")
                ok = response.status_code in (200, 206) and (b"%PDF" in head or "pdf" in ctype)
                response.close()
            except Exception as exc:  # noqa: BLE001
                ok, response, ctype = False, None, repr(exc)
            expected_fallback = bool(doc.get("request"))
            status = response.status_code if response is not None else "---"
            print(f"{'ok ' if ok or expected_fallback else 'BAD'} {status} {ctype[:28]:28} {doc['source_id']}")
            failures += 0 if (ok or expected_fallback) else 1
        print(f"verified {len(documents)} documents, {failures} failures")
        return
    for jurisdiction, state in STATES.items():
        manifest_path(jurisdiction).write_text(
            yaml.safe_dump({"version": SOURCE_AS_OF, "documents": state["documents"]}, sort_keys=False, allow_unicode=True, width=120)
        )
    print(f"wrote {len(STATES)} forms manifests ({len(documents)} documents)")


def _coverage(jurisdiction: str, version: str) -> dict[str, Any] | None:
    import json

    path = CORPUS_BASE / "coverage" / jurisdiction / "form" / f"{version}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    return {
        "complete": payload.get("complete"),
        "provision_count": payload.get("provision_count"),
        "source_count": payload.get("source_count"),
        "missing": len(payload.get("missing_from_provisions") or []),
    }


def update_queue() -> None:
    queue_path = MANIFESTS / "tax-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"] if row["jurisdiction"] != "us"}
    for jurisdiction, state in STATES.items():
        rows[jurisdiction]["ty2025_forms_closure_scope"] = {
            "run_note": RUN_NOTE,
            "queue_status": "agent_ready",
            "publisher": state["publisher"],
            "index_url": state["index_url"],
            "index_document_count": state["index_document_count"],
            "index_count_method": state["index_count_method"],
            "closure_elements": state["elements"],
            "target_manifest": manifest_path(jurisdiction).as_posix().replace(str(ROOT) + "/", ""),
            "document_class": "form",
            "version": FORMS_VERSION,
            "coverage": _coverage(jurisdiction, FORMS_VERSION),
            "taken_count": len(state["documents"]),
            "documents": [d["citation_path"] for d in state["documents"]],
            "notes": state["notes"],
        }
    for jurisdiction, spec in NOT_TAKEN.items():
        rows[jurisdiction]["ty2025_forms_closure_scope"] = {
            "run_note": RUN_NOTE,
            "queue_status": spec["queue_status"],
            "publisher": spec["publisher"],
            "index_url": spec["index_url"],
            "taken_count": 0,
            "notes": spec["reason"],
        }
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"queue rows updated: forms {len(STATES)} taken, {len(NOT_TAKEN)} not taken")
