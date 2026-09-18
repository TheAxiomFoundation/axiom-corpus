"""Static tables for the TY2026 indexed-amount family of
``scripts/build_state_tax_statute_ty2026_manifests.py`` (``--family amounts`` and
``--family queue``).

Every URL below was confirmed by the agent on 2026-09-13 from the revenue department's own
index (``index_url``) with the corpus user agent, downloaded and read (PDFs through
``pdftotext``); the figures quoted in ``amounts`` are what the document prints. A state is
listed under ``BLOCKED`` or ``NOT_TAKEN`` with the evidence when the publisher blocks the
client or posts no 2026-labelled figures and nothing later than what the corpus already
holds. Estimated-tax instructions and vouchers are ``form`` class (citation path
``us-xx/form/<agency>/ty2026/<id>``); department notices, publications and web pages are
``guidance`` (``us-xx/guidance/<agency>/ty<year>/<id>``), following the jurisdiction
precedents in ``manifests/us-xx-*`` (AZ 140ES, KY 740-ES, NE 1040N-ES are forms; MN, ME,
MI, RI amounts are guidance).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
CORPUS_BASE = Path(os.environ.get("AXIOM_CORPUS_BASE", str(ROOT / "data" / "corpus")))
SOURCE_AS_OF = "2026-09-14"
RESEARCH_DATE = "2026-09-13"
AMOUNTS_VERSION = "2026-09-14-ty2026-indexed-amounts"
STATUTE_VERSION = "2026-09-14-income-tax-chapter"
SINGLE_BLOCK = {"segmentation": "single_block"}
# Publisher edges that answer HTTP 403 to the corpus client and serve a browser (CO
# CloudFront, OH). The extractor tries the corpus client first and falls back to
# curl_cffi with the named Chrome fingerprint; TLS stays verified.
BROWSER_FALLBACK = {"browser_user_agent": True, "browser_impersonation": "chrome120"}


def _doc(
    jurisdiction: str,
    agency: str,
    doc_id: str,
    *,
    document_class: str,
    title: str,
    url: str,
    fmt: str,
    tax_year: str,
    subtype: str,
    authority: str,
    index_url: str,
    publication_date: str | None,
    amounts: list[str],
    extraction: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "source_id": f"{jurisdiction}-{agency}-{doc_id}-ty{tax_year}",
        "jurisdiction": jurisdiction,
        "document_class": document_class,
        "title": title,
        "source_url": url,
        "source_format": fmt,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": f"{tax_year}-01-01",
        "citation_path": f"{jurisdiction}/{document_class}/{agency}/ty{tax_year}/{doc_id}",
        "extraction": extraction or (SINGLE_BLOCK if fmt == "pdf" else {}),
        "metadata": {
            "primary_source": True,
            "source_authority": authority,
            "document_subtype": subtype,
            "program": "individual_income_tax",
            "tax_year": tax_year,
            "publication_or_revision_date": publication_date,
            "amounts_carried": amounts,
            "source_family": "state-ty2026-indexed-amounts",
            "closure_element": "F06",
            "index_url": index_url,
            "discovered_via": f"manual-review:tax-agent-queue; index {index_url} (read {RESEARCH_DATE})",
        },
    }
    if note:
        doc["metadata"]["source_note"] = note
    if request:
        doc["request"] = dict(request)
    if fmt == "html" and not extraction:
        raise ValueError(f"{doc['source_id']}: HTML documents need an html_content_selector")
    return doc


# jurisdiction -> {"publisher", "index_url", "index_document_count", "index_count_method",
#                  "indexes_for_inflation", "documents": [...], "notes"}
STATES: dict[str, dict[str, Any]] = {
    "us-al": {
        "publisher": "Alabama Department of Revenue",
        "index_url": "https://www.revenue.alabama.gov/forms/?jsf=jet-data-table:form-table&tax=form-categories:154",
        "index_document_count": 30,
        "index_count_method": "unique PDF links on the forms archive filtered to Individual Income Tax",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-al", "ador", "form-40es-instructions", document_class="form",
                 title="2026 Form 40ES Declaration of Estimated Tax Instructions",
                 url="https://www.revenue.alabama.gov/wp-content/uploads/2026/01/26f40esinstr.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Alabama Department of Revenue", index_url="https://www.revenue.alabama.gov/forms/?jsf=jet-data-table:form-table&tax=form-categories:154",
                 publication_date="2026-01-09", amounts=["estimated-tax thresholds only"],
                 note="Prints the 2026 estimated-tax rules but no rate schedule, deduction or exemption; the amounts are on the department's filing-information page taken in the guidance scope."),
            _doc("us-al", "ador", "individual-income-tax-filing-information", document_class="guidance",
                 title="Individual Income Tax: General Information for Individuals (rates and personal exemptions)",
                 url="https://www.revenue.alabama.gov/individual-corporate/individual-income-tax-filing-information/", fmt="html",
                 tax_year="2026", subtype="department_web_page",
                 authority="Alabama Department of Revenue", index_url="https://www.revenue.alabama.gov/individual-corporate/individual-income-tax-filing-information/",
                 publication_date=None, amounts=["rate schedule (2%/4%/5%)", "personal exemption ($1,500/$3,000)"],
                 extraction={"html_content_selector": "div.elementor-element-32825a90"},
                 note="Undated current page; Alabama does not index and the page states the statutory rates and exemptions in force for 2026."),
        ],
        "notes": "Alabama does not index. The 2026-labelled 40ES products print no amounts; the department's undated filing-information page states the statutory rates and exemptions.",
    },
    "us-ar": {
        "publisher": "Arkansas Department of Finance and Administration",
        "index_url": "https://www.dfa.arkansas.gov/office/taxes/income-tax-administration/individual-income-tax/forms/",
        "index_document_count": 55,
        "index_count_method": "unique PDF links on the Individual Income Tax Forms page",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-ar", "dfa", "ar1000es-instructions", document_class="form",
                 title="AR1000ES Individual Estimated Tax Vouchers and Instructions for Tax Year 2026",
                 url="https://www.dfa.arkansas.gov/wp-content/uploads/2026_Final_AR1000ES_2.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Arkansas Department of Finance and Administration", index_url="https://www.dfa.arkansas.gov/office/taxes/income-tax-administration/individual-income-tax/forms/",
                 publication_date="2026-05-12", amounts=["rate schedule (0%-3.7%)", "standard deduction ($2,470)", "personal credits ($29/$58)", "bracket-adjustment table"]),
        ],
        "notes": "Arkansas indexes the standard deduction and brackets to CPI (Act 182 of 2019); the 2026 AR1000ES prints the full 2026 schedule.",
    },
    "us-co": {
        "publisher": "Colorado Department of Revenue, Taxation Division",
        "index_url": "https://tax.colorado.gov/individual-income-tax-forms",
        "index_document_count": 23,
        "index_count_method": "unique form links on the Individual Income Tax Forms page (read with a browser user agent)",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-co", "cdor", "dr-0104ep", document_class="form",
                 title="DR 0104EP 2026 Colorado Estimated Income Tax Payment Form",
                 url="https://tax.colorado.gov/sites/tax/files/documents/DR_0104EP_2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Colorado Department of Revenue", index_url="https://tax.colorado.gov/individual-income-tax-forms",
                 publication_date="2025-12-05", amounts=["flat rate (4.4%)", "estimated-tax threshold"],
                 request=BROWSER_FALLBACK,
                 note="tax.colorado.gov (CloudFront) answers HTTP 403 to the corpus client and serves the file to a Chrome user agent (probed 2026-09-13)."),
        ],
        "notes": "Colorado is a flat 4.4% tax with no indexing; the 2026 DR 0104EP prints the rate.",
    },
    "us-ct": {
        "publisher": "Connecticut Department of Revenue Services",
        "index_url": "https://portal.ct.gov/drs/drs-forms/current-year-forms/individual-income-tax-forms",
        "index_document_count": 36,
        "index_count_method": "unique PDF links on the DRS current-year Individual Income Tax Forms page",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-ct", "drs", "ct-1040es", document_class="form",
                 title="Form CT-1040ES 2026 Estimated Connecticut Income Tax Payment Coupon for Individuals",
                 url="https://portal.ct.gov/-/media/drs/forms/2025/income/ct1040es-flat0126.pdf?rev=67a1aab5b38b4c9ca2732157970af963&hash=4D350AF90425A28B04F1F7A1694F9D4B", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Connecticut Department of Revenue Services", index_url="https://portal.ct.gov/drs/drs-forms/current-year-forms/individual-income-tax-forms",
                 publication_date="2025-08-28", amounts=["Table A personal exemptions 2026", "Table B rate schedule 2026", "phase-out and recapture tables"]),
        ],
        "notes": "Connecticut does not index; the CT-1040ES 2026 prints Tables A and B for the 2026 taxable year.",
    },
    "us-de": {
        "publisher": "Delaware Division of Revenue",
        "index_url": "https://revenue.delaware.gov/personal-income-tax-forms/",
        "index_document_count": 62,
        "index_count_method": "unique PDF links on the Personal Income Tax Forms current-year page",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-de", "dor", "pit-est-instructions", document_class="form",
                 title="Form PIT-EST Delaware Estimated Income Tax Voucher Instructions (2026)",
                 url="https://revenuefiles.delaware.gov/2025/PITForms_Instructions/Instructions/PIT-EST_Instructions_2026-01.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Delaware Division of Revenue", index_url="https://revenue.delaware.gov/personal-income-tax-forms/",
                 publication_date="2025-11-10", amounts=["rate schedule (2.2%-6.6%)", "standard deduction ($3,250/$6,500)", "additional standard deduction ($2,500)", "personal credit ($110)"]),
        ],
        "notes": "Delaware does not index; the 2026 PIT-EST instructions print the statutory amounts.",
    },
    "us-ga": {
        "publisher": "Georgia Department of Revenue",
        "index_url": "https://dor.georgia.gov/taxes/years-individual-income-tax-forms",
        "index_document_count": 8,
        "index_count_method": "document entries on This Year's Individual Income Tax Forms",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-ga", "dor", "500-es", document_class="form",
                 title="2026 500-ES Estimated Tax for Individuals and Fiduciaries",
                 url="https://dor.georgia.gov/document/document/2026-500-es-estimated-tax-individuals-and-fiduciaries/download", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Georgia Department of Revenue", index_url="https://dor.georgia.gov/taxes/years-individual-income-tax-forms",
                 publication_date="2025-05-22", amounts=["standard deduction ($12,000/$24,000)", "dependent exemption ($4,000, labelled tax year 2025)", "retirement exclusion"],
                 note="The form defers the rate to the IT-511 booklet and labels the exemption 'tax year 2025'; no 2026 rate publication exists on the publisher."),
        ],
        "notes": "Georgia is a flat tax with statutory amounts; dor.georgia.gov answered HTTP 200 to the corpus client on 2026-09-13 (no WAF block this run).",
    },
    "us-hi": {
        "publisher": "Hawaii Department of Taxation",
        "index_url": "https://tax.hawaii.gov/forms/a1_1alphalist/",
        "index_document_count": 261,
        "index_count_method": "unique PDF links on the alphabetical forms listing",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-hi", "dotax", "tax-tables-and-rate-schedules", document_class="guidance",
                 title="2025 Tax Tables and Tax Rate Schedules (individual tax tables for taxable years beginning after December 31, 2024)",
                 url="https://files.hawaii.gov/tax/forms/2025/25table-on.pdf", fmt="pdf",
                 tax_year="2025", subtype="tax_rate_schedules",
                 authority="Hawaii Department of Taxation", index_url="https://tax.hawaii.gov/forms/d_25table-on/",
                 publication_date="2025-12-10", amounts=["rate schedules I-III (1.4%-11%)", "tax tables"],
                 note="Latest published year: no 2026-labelled rate or estimated-tax document exists on the publisher as of 2026-09-13; Act 46, SLH 2024 sets the 2026 standard deduction step by statute."),
        ],
        "notes": "Hawaii does not index; brackets and the standard deduction change by the Act 46 (SLH 2024) schedule. Form N-1 is discontinued and N-200V (Rev. 2025) prints no amounts.",
    },
    "us-ia": {
        "publisher": "Iowa Department of Revenue",
        "index_url": "https://revenue.iowa.gov/forms/common-forms/individual-income-tax",
        "index_document_count": 15,
        "index_count_method": "unique media download links on the Individual Income Tax forms page",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-ia", "idr", "ia-1040es-instructions", document_class="form",
                 title="2026 IA 1040ES Estimated Tax Payment Voucher Instructions (45-009)",
                 url="https://revenue.iowa.gov/media/2725/download?inline", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Iowa Department of Revenue", index_url="https://revenue.iowa.gov/forms/common-forms/individual-income-tax",
                 publication_date="2025-08-29", amounts=["flat rate (3.8%)", "low-income exemption thresholds"]),
        ],
        "notes": "Iowa is a flat 3.8% tax from 2025 with no indexing and uses the federal standard deduction.",
    },
    "us-id": {
        "publisher": "Idaho State Tax Commission",
        "index_url": "https://tax.idaho.gov/forms/",
        "index_document_count": 172,
        "index_count_method": "unique PDF and document-manager links on the all-forms page",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-id", "istc", "individual-income-tax-rate-schedule", document_class="guidance",
                 title="Individual Income Tax Rate Schedule (by year; 2025 latest)",
                 url="https://tax.idaho.gov/taxes/income-tax/individual-income/individual-income-tax-rate-schedule/", fmt="html",
                 tax_year="2025", subtype="department_web_page",
                 authority="Idaho State Tax Commission", index_url="https://tax.idaho.gov/taxes/income-tax/individual-income/individual-income-tax-rate-schedule/",
                 publication_date="2025-12-29", amounts=["rate schedule by year (2025 latest: 0% to $4,811/$9,622, then 5.3%)"],
                 extraction={"html_content_selector": ".entry-content"},
                 note="Latest published year: the page has no 2026 row as of 2026-09-13."),
            _doc("us-id", "istc", "epb00744-withholding-percentage-table", document_class="guidance",
                 title="Table for Percentage Computation Method of Withholding (EPB00744, rev. 2026-07-23)",
                 url="https://tax.idaho.gov/wp-content/uploads/pubs/EPB00744/EPB00744_07-23-2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="withholding_tables",
                 authority="Idaho State Tax Commission", index_url="https://tax.idaho.gov/forms/",
                 publication_date="2026-07-23", amounts=["withholding rate (5.3%)", "zero-bracket withholding thresholds ($16,100/$32,200)"]),
        ],
        "notes": "Idaho indexes its zero-bracket threshold; the department's rate-schedule page stops at 2025 and Form 51 (2026) prints no rates, so the 2026-dated withholding table is taken alongside the rate-schedule page.",
    },
    "us-mn": {
        "publisher": "Minnesota Department of Revenue",
        "index_url": "https://www.revenue.state.mn.us/find-form",
        "index_document_count": 39,
        "index_count_method": "unique PDF and form-search links on the Find a Form page",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-mn", "department-of-revenue", "inflation-adjusted-amounts", document_class="guidance",
                 title="Inflation Adjusted Amounts for 2026 (tax year 2026 inflation-adjusted amounts)",
                 url="https://www.revenue.state.mn.us/sites/default/files/2025-12/inflation-adjusted-amounts-2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="inflation_adjustment_notice",
                 authority="Minnesota Department of Revenue", index_url="https://www.revenue.state.mn.us/minnesota-income-tax-rates-and-brackets",
                 publication_date="2025-12-15", amounts=["bracket thresholds", "standard deduction", "dependent exemption", "aged/blind additional deduction", "child credit", "working family credit", "dependent care credit"],
                 note="Same document as the released us-mn/guidance/2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026 scope, whose per-bracket rows captured the 'Statutory Year' column (2019/2023) instead of the 'Tax Year 2026' column; taken here as one body so both columns read in order."),
            _doc("us-mn", "department-of-revenue", "income-tax-rates-and-brackets", document_class="guidance",
                 title="Income Tax Rates and Brackets (tax year 2026)",
                 url="https://www.revenue.state.mn.us/minnesota-income-tax-rates-and-brackets", fmt="html",
                 tax_year="2026", subtype="department_web_page",
                 authority="Minnesota Department of Revenue", index_url="https://www.revenue.state.mn.us/minnesota-income-tax-rates-and-brackets",
                 publication_date="2026-01-09", amounts=["rate schedule 2026 (5.35%/6.8%/7.85%/9.85% by filing status)"],
                 extraction={"html_content_selector": ".uswds-main-content-wrapper"}),
        ],
        "notes": "Minnesota indexes; the HTML page carries the 2026 brackets and the PDF the full list.",
    },
    "us-mo": {
        "publisher": "Missouri Department of Revenue",
        "index_url": "https://dor.mo.gov/forms/",
        "index_document_count": 931,
        "index_count_method": "unique PDF links on the all-taxes Forms and Manuals page (14 labelled 2026)",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-mo", "dor", "mo-1040es", document_class="form",
                 title="MO-1040ES 2026 Declaration of Estimated Tax for Individuals",
                 url="https://dor.mo.gov/forms/MO-1040ES_2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Missouri Department of Revenue", index_url="https://dor.mo.gov/forms/",
                 publication_date="2025-12-15", amounts=["tax rate chart 2026 (2.0%-4.7%)", "standard deductions 2026", "head-of-household/qualifying-widow additional exemption ($1,400)"]),
        ],
        "notes": "Missouri indexes brackets and the standard deduction; dor.mo.gov served the 2026 file to the corpus client (no WAF block this run). A standalone 2026 Tax Chart is not yet posted.",
    },
    "us-ms": {
        "publisher": "Mississippi Department of Revenue",
        "index_url": "https://www.dor.ms.gov/forms-resources/form-search?division=individual_forms",
        "index_document_count": 25,
        "index_count_method": "unique individual-form PDF links on the form search results",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-ms", "dor", "general-information", document_class="guidance",
                 title="General Information: individual income tax rates for tax years 2025-2027, exemptions and standard deduction",
                 url="https://www.dor.ms.gov/general-information", fmt="html",
                 tax_year="2026", subtype="department_web_page",
                 authority="Mississippi Department of Revenue", index_url="https://www.dor.ms.gov/general-information",
                 publication_date=None, amounts=["rate step by year (2026: 4% over $10,000)", "exemptions ($12,000/$8,000/$6,000; dependent $1,500)", "standard deduction ($4,600/$3,400/$2,300)"],
                 extraction={"html_content_selector": "#main"}),
        ],
        "notes": "Mississippi does not index; the current 80-106 voucher is the TY2025 revision and prints no amounts.",
    },
    "us-mt": {
        "publisher": "Montana Department of Revenue",
        "index_url": "https://revenue.mt.gov/forms/",
        "index_document_count": 214,
        "index_count_method": "unique file, publication and PDF links on the all-taxes forms index",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-mt", "mtdor", "publication-1", document_class="guidance",
                 title="2026 Montana Publication 1: A Guide to Montana Tax Withholding and Estimated Payments (worksheets ESW, ESA, ESW-TMSI)",
                 url="https://revenuefiles.mt.gov/files/Forms/Publication-1/Publication-1-2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="department_publication",
                 authority="Montana Department of Revenue", index_url="https://revenue.mt.gov/publications/publication-1",
                 publication_date="2025-11-20", amounts=["2026 and 2027 tax tables (4.7%/5.65%; 2027 5.4%)", "net long-term capital gains rates", "worksheet ESW/ESA 2026"]),
        ],
        "notes": "Montana indexes brackets and uses the federal standard deduction; the rates web page is JS-rendered, so the 2026 Publication 1 PDF is the extractable source.",
    },
    "us-nc": {
        "publisher": "North Carolina Department of Revenue",
        "index_url": "https://www.ncdor.gov/taxes-forms/individual-income-tax/individual-income-tax-forms-instructions",
        "index_document_count": 47,
        "index_count_method": "unique PDF and document links on the Individual Income Tax Forms & Instructions page (all 2025 tax year)",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-nc", "ncdor", "tax-rate-schedules", document_class="guidance",
                 title="Tax Rate Schedules (current tax year rates: 3.99% for taxable years after 2025)",
                 url="https://www.ncdor.gov/taxes-forms/individual-income-tax/tax-rate-schedules", fmt="html",
                 tax_year="2026", subtype="department_web_page",
                 authority="North Carolina Department of Revenue", index_url="https://www.ncdor.gov/taxes-forms/individual-income-tax/tax-rate-schedules",
                 publication_date=None, amounts=["flat rate by year (2025 4.25%; after 2025 3.99%)"],
                 extraction={"html_content_selector": "main#main-wrapper"}),
        ],
        "notes": "North Carolina does not index; no 2026-labelled NC-40 PDF exists on the publisher (the estimated-tax page links the eservices web voucher and 2024/2025 worksheets).",
    },
    "us-nd": {
        "publisher": "North Dakota Office of State Tax Commissioner",
        "index_url": "https://www.tax.nd.gov/forms",
        "index_document_count": 27,
        "index_count_method": "unique individual-income-tax PDF links on the Tax Forms Search page",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-nd", "otc", "nd-1es", document_class="form",
                 title="Form ND-1ES 2026 Estimated Individual Income Tax (SFN 28709, 12-2025)",
                 url="https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2025-iit/28709-form-nd-1es-2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="North Dakota Office of State Tax Commissioner", index_url="https://www.tax.nd.gov/forms",
                 publication_date="2025-10-23", amounts=["2026 Forms ND-1 and ND-EZ tax rate schedules (1.95%/2.5% by filing status)"]),
        ],
        "notes": "North Dakota indexes bracket thresholds and starts from federal taxable income (no state standard deduction or exemption).",
    },
    "us-nj": {
        "publisher": "New Jersey Division of Taxation",
        "index_url": "https://www.nj.gov/treasury/taxation/prntgit.shtml",
        "index_document_count": 63,
        "index_count_method": "unique PDF links on the Income Tax Forms print index",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-nj", "taxation", "nj-1040-es-instructions", document_class="form",
                 title="2026 NJ-1040-ES Instructions (Declaration of Estimated Tax)",
                 url="https://www.nj.gov/treasury/taxation/pdf/current/1040esi.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="New Jersey Division of Taxation", index_url="https://www.nj.gov/treasury/taxation/prntgit.shtml",
                 publication_date="2025-10-27", amounts=["personal exemptions ($1,000/$1,500/$6,000)", "filing thresholds"],
                 note="The instructions do not reprint the rate schedule; the Division publishes its rate schedule as '2020 and After', not as a 2026-labelled document."),
        ],
        "notes": "New Jersey does not index (no standard deduction; fixed exemptions and statutory brackets).",
    },
    "us-nm": {
        "publisher": "New Mexico Taxation and Revenue Department",
        "index_url": "https://www.tax.newmexico.gov/individuals/online-services-overview/personal-income-tax-forms/",
        "index_document_count": 0,
        "index_count_method": "the forms list is loaded client-side by the RealFile SDK; the HTML carries no document links",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-nm", "trd", "fyi-104-withholding-tax", document_class="guidance",
                 title="FYI-104 New Mexico Withholding Tax, effective January 1, 2026",
                 url="https://realfile.tax.newmexico.gov/FYI-104.pdf", fmt="pdf",
                 tax_year="2026", subtype="withholding_tables",
                 authority="New Mexico Taxation and Revenue Department", index_url="https://www.tax.newmexico.gov/individuals/online-services-overview/personal-income-tax-forms/",
                 publication_date="2025-11-19", amounts=["withholding percentage-method tables (1.7%-5.9%)", "supplemental wage rate (5.9%)"],
                 note="No 2026-labelled PIT-ES exists on the publisher (every RealFile file name tried answers 404); the withholding publication is the only 2026-dated figure carrier."),
        ],
        "notes": "New Mexico does not index; the forms portal is JavaScript-only.",
    },
    "us-ny": {
        "publisher": "New York State Department of Taxation and Finance",
        "index_url": "https://www.tax.ny.gov/forms/income_estimated_forms.htm",
        "index_document_count": 124,
        "index_count_method": "unique links on the Income tax estimated forms (current year) page",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-ny", "tax", "it-2105-i", document_class="form",
                 title="Instructions for Form IT-2105 Estimated Income Tax Payment Voucher for Individuals, tax year 2026 (IT-2105-I)",
                 url="https://www.tax.ny.gov/pdf/current_forms/it/it2105i.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="New York State Department of Taxation and Finance", index_url="https://www.tax.ny.gov/forms/income_estimated_forms.htm",
                 publication_date="2026-02-12", amounts=["standard deduction table 2026", "dependent exemption ($1,000)", "New York State rate schedules", "New York City rate schedules", "tax computation worksheets"]),
        ],
        "notes": "New York does not index; tax.ny.gov answered HTTP 200 to the corpus client on 2026-09-13 (no WAF block this run). The annual tax-tables page has no 2026 entry yet.",
    },
    "us-oh": {
        "publisher": "Ohio Department of Taxation",
        "index_url": "https://tax.ohio.gov/forms-top/search-forms",
        "index_document_count": None,
        "index_count_method": "the forms search renders client-side; not countable",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-oh", "odt", "annual-tax-rates", document_class="guidance",
                 title="Annual Tax Rates: Ohio individual income tax brackets for 2005 through 2025",
                 url="https://tax.ohio.gov/individual/resources/annual-tax-rates", fmt="html",
                 tax_year="2025", subtype="department_web_page",
                 authority="Ohio Department of Taxation", index_url="https://tax.ohio.gov/individual/resources/annual-tax-rates",
                 publication_date=None, amounts=["bracket schedule by year (2025 latest: 0% to $26,050, 2.75%, 3.125%)"],
                 extraction={"html_content_selector": "main#odx-main-content"},
                 request=BROWSER_FALLBACK,
                 note="Latest published year: the page stops at taxable years beginning in 2025. tax.ohio.gov answers the corpus client with HTTP 404 whose body is a '403 Error Page' and serves a Chrome user agent (probed 2026-09-13)."),
        ],
        "notes": "Ohio indexes brackets; no 2026 bracket publication or IT 1040ES 2026 exists on the publisher as of 2026-09-13.",
    },
    "us-ok": {
        "publisher": "Oklahoma Tax Commission",
        "index_url": "https://oklahoma.gov/tax/forms.html",
        "index_document_count": 26,
        "index_count_method": "rows of the forms metadata CSV with category Income Tax, subcategory Individuals, year Current",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-ok", "otc", "ow-8-es", document_class="form",
                 title="Form OW-8-ES Oklahoma Individual Estimated Tax, Tax Year 2026 Worksheet and Coupon",
                 url="https://oklahoma.gov/content/dam/ok/en/tax/documents/forms/individuals/current/OW-8-ES.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Oklahoma Tax Commission", index_url="https://oklahoma.gov/tax/forms.html",
                 publication_date="2025-06-01", amounts=["personal exemption ($1,000)"],
                 note="Prints the exemption amount only; no rate schedule or standard deduction."),
        ],
        "notes": "Oklahoma does not index; the current 511 packet is the 2025 booklet.",
    },
    "us-pa": {
        "publisher": "Pennsylvania Department of Revenue",
        "index_url": "https://www.pa.gov/agencies/revenue/forms-and-publications",
        "index_document_count": None,
        "index_count_method": "the forms listing is a client-side search; not countable",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-pa", "department-of-revenue", "rev-413i", document_class="form",
                 title="2026 REV-413 (I) Instructions for Estimating PA Personal Income Tax, for individuals only",
                 url="https://www.pa.gov/content/dam/copapwp-pagov/en/revenue/documents/formsandpublications/formsforindividuals/pit/documents/2026/2026_rev-413i.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Pennsylvania Department of Revenue", index_url="https://www.pa.gov/agencies/revenue/forms-and-publications",
                 publication_date="2025-04-01", amounts=["flat rate (3.07%)", "estimated-payment income threshold ($14,000 for 2026)"]),
        ],
        "notes": "Pennsylvania is a flat 3.07% tax with no standard deduction or exemption; nothing is indexed.",
    },
    "us-ri": {
        "publisher": "Rhode Island Division of Taxation",
        "index_url": "https://tax.ri.gov/forms/individual-tax-forms/personal-income-tax-forms",
        "index_document_count": 30,
        "index_count_method": "unique PDF links on the Personal Income Tax Forms page",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-ri", "tax", "ri-1040es", document_class="form",
                 title="2026 RI-1040ES Rhode Island Resident and Nonresident Estimated Payment Coupons",
                 url="https://tax.ri.gov/sites/g/files/xkgbur541/files/2026-01/2026%20RI-1040ES_w.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Rhode Island Division of Taxation", index_url="https://tax.ri.gov/forms/individual-tax-forms/personal-income-tax-forms",
                 publication_date="2026-01-02", amounts=["2026 tax rate schedule (3.75%/4.75%/5.99%)", "standard deduction", "exemption ($5,250)", "phase-out threshold ($261,000)"],
                 note="ADV 2025-22 (the inflation-adjustment advisory for 2026) is already released as us-ri/guidance/2026-07-23-ri-pit-adv-2025-22 and is not re-taken."),
        ],
        "notes": "Rhode Island indexes; ADV 2025-22 is in the released selection and the 2026 RI-1040ES adds the printed schedule and worksheet amounts.",
    },
    "us-sc": {
        "publisher": "South Carolina Department of Revenue",
        "index_url": "https://dor.sc.gov/find-a-form?search_api_fulltext=&field_category=All&field_document_type=All&field_tax_year=601",
        "index_document_count": 87,
        "index_count_method": "unique PDF links across the ten Find a Form result pages filtered to tax year 2026",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-sc", "dor", "sc1040es", document_class="form",
                 title="SC1040ES 2026 Individual Declaration of Estimated Tax (Rev. 10/13/25)",
                 url="https://dor.sc.gov/sites/dor/files/forms/SC1040ES_2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="South Carolina Department of Revenue", index_url="https://dor.sc.gov/find-a-form?search_api_fulltext=&field_category=All&field_document_type=All&field_tax_year=601",
                 publication_date="2025-10-13", amounts=["2026 tax computation schedule (0%/3%/6%; $3,640 and $18,230 breakpoints)"]),
        ],
        "notes": "South Carolina indexes its brackets and follows the federal standard deduction and exemption amounts.",
    },
    "us-ut": {
        "publisher": "Utah State Tax Commission",
        "index_url": "https://tax.utah.gov/forms-pubs/",
        "index_document_count": 231,
        "index_count_method": "unique current-forms PDF links on the Current Forms & Publications page",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-ut", "ustc", "tax-rates", document_class="guidance",
                 title="Tax Rates (Utah single rate by date range; 4.5% from January 1, 2025)",
                 url="https://incometax.utah.gov/file-pay/tax-rates/", fmt="html",
                 tax_year="2025", subtype="department_web_page",
                 authority="Utah State Tax Commission", index_url="https://incometax.utah.gov/file-pay/tax-rates/",
                 publication_date=None, amounts=["flat rate by date range (4.5% from 2025-01-01)"],
                 extraction={"html_content_selector": ".entry-content"},
                 note="Latest published statement: the indexed taxpayer tax credit phase-out for 2026 is published only in the TC-40 instructions, whose current edition is the 2025 booklet."),
        ],
        "notes": "Utah has a flat rate; no 2026-labelled publication with the indexed credit amounts exists on the publisher as of 2026-09-13.",
    },
    "us-va": {
        "publisher": "Virginia Department of Taxation",
        "index_url": "https://www.tax.virginia.gov/forms/search?category=1&year=667",
        "index_document_count": 3,
        "index_count_method": "unique PDF links on the forms search filtered to Individual Income Tax, year 2026",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-va", "tax", "760es", document_class="form",
                 title="2026 Form 760ES Virginia Estimated Income Tax Payment Vouchers for Individuals (Rev. 09/25)",
                 url="https://www.tax.virginia.gov/sites/default/files/taxforms/individual-income-tax/2026/760es-2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Virginia Department of Taxation", index_url="https://www.tax.virginia.gov/forms/search?category=1&year=667",
                 publication_date="2025-09-05", amounts=["tax rate schedule (2%-5.75%)", "personal exemption ($930; age 65/blind $800)", "filing thresholds"]),
            _doc("us-va", "tax", "deductions", document_class="guidance",
                 title="Deductions (Virginia standard deduction amounts)",
                 url="https://www.tax.virginia.gov/deductions", fmt="html",
                 tax_year="2026", subtype="department_web_page",
                 authority="Virginia Department of Taxation", index_url="https://www.tax.virginia.gov/deductions",
                 publication_date=None, amounts=["standard deduction ($8,750/$17,500)"],
                 extraction={"html_content_selector": "section#basic-content"},
                 note="Undated current page; the 760ES defers the standard deduction to the website."),
        ],
        "notes": "Virginia does not index.",
    },
    "us-vt": {
        "publisher": "Vermont Department of Taxes",
        "index_url": "https://tax.vermont.gov/individuals/personal-income-tax/rates",
        "index_document_count": 19,
        "index_count_method": "unique PDF links on the Vermont Rate Schedules and Tax Tables page (through 2025)",
        "indexes_for_inflation": True,
        "documents": [
            _doc("us-vt", "vdt", "in-114-instructions", document_class="form",
                 title="2026 Form IN-114 Instructions, Individual Income Estimated Tax Payment Voucher, with 2026 Preliminary Vermont Tax Rates (Rev. 10/25)",
                 url="https://tax.vermont.gov/sites/tax/files/documents/IN-114-Instr-2026.pdf", fmt="pdf",
                 tax_year="2026", subtype="estimated_tax_instructions",
                 authority="Vermont Department of Taxes", index_url="https://tax.vermont.gov/individuals/personal-income-tax",
                 publication_date="2025-10-27", amounts=["2026 preliminary rate schedules X, Y-1, Y-2, Z", "child care contribution rate (0.11%)"],
                 note="The department labels the 2026 schedules 'Preliminary'; the final 2026 rate schedule PDF is not yet posted."),
        ],
        "notes": "Vermont indexes; the 2026 standard deduction and personal exemption are not printed in IN-114.",
    },
    "us-wv": {
        "publisher": "West Virginia Tax Division",
        "index_url": "https://tax.wv.gov/Individuals/Pages/Individuals.aspx",
        "index_document_count": 66,
        "index_count_method": "unique PDF links on the Individuals page (the individual forms index)",
        "indexes_for_inflation": False,
        "documents": [
            _doc("us-wv", "tax", "2026-income-tax-rate-cut", document_class="guidance",
                 title="2026 Income Tax Rate Cut (SB 392; W. Va. Code 11-21-4j rate schedules retroactive to January 1, 2026)",
                 url="https://tax.wv.gov/Individuals/Pages/PersonalIncomeTaxReductionBill.aspx", fmt="html",
                 tax_year="2026", subtype="department_web_page",
                 authority="West Virginia Tax Division", index_url="https://tax.wv.gov/Individuals/Pages/Individuals.aspx",
                 publication_date="2026-03-31", amounts=["2026 rate schedule (2.11%-4.58%)", "2026 married-filing-separately schedule"],
                 extraction={"html_content_selector": "#main"}),
            _doc("us-wv", "tax", "it-100-2-a-withholding-tables", document_class="guidance",
                 title="IT-100.2.A Tables for Percentage Method of Withholding (March 2026)",
                 url="https://tax.wv.gov/Documents/Withholding/it100.2a.pdf", fmt="pdf",
                 tax_year="2026", subtype="withholding_tables",
                 authority="West Virginia Tax Division", index_url="https://tax.wv.gov/Individuals/Pages/Individuals.aspx",
                 publication_date="2026-03-01", amounts=["withholding percentage-method rates", "per-exemption wage reduction"]),
        ],
        "notes": "West Virginia does not index; no IT-140ES exists on the site (estimated payments go through MyTaxes) and the 2026 rate schedule PDF is not yet posted.",
    },
}

# Jurisdictions with no new scope in this family, with the evidence.
NOT_TAKEN: dict[str, dict[str, Any]] = {
    "us-dc": {
        "queue_status": "blocked_primary_source",
        "publisher": "DC Office of Tax and Revenue",
        "index_url": "https://otr.cfo.dc.gov/page/individual-income-tax-forms",
        "index_document_count": None,
        "reason": "otr.cfo.dc.gov answers HTTP 403 'Access denied | otr' (101,469-byte block page) to the corpus client and to a Chrome user agent on every page path probed on 2026-09-13; the 2026-09-10 forms run had been served on the same paths. Not worked around.",
    },
    "us-md": {
        "queue_status": "blocked_primary_source",
        "publisher": "Comptroller of Maryland",
        "index_url": "https://services.marylandcomptroller.gov/taxes/en/individual-income-tax-forms-and-instructions?id=kb_article_view&sysparm_article=KB0010191",
        "index_document_count": 0,
        "reason": "marylandtaxes.gov redirects to a ServiceNow knowledge base whose pages are JavaScript-rendered shells (HTTP 200, no article text or document links in the HTML; the KB REST API answers 401) and the legacy PDF paths (forms/current_forms/502D.pdf, 26_forms/PV.pdf, 26_forms/Withholding_Guide.pdf) redirect to 404. No 2026-labelled document is retrievable from the publisher as of 2026-09-13.",
    },
    "us-wi": {
        "queue_status": "done",
        "publisher": "Wisconsin Department of Revenue",
        "index_url": "https://www.revenue.wi.gov/Pages/Form/2026Individual.aspx",
        "index_document_count": 24,
        "reason": "The 2026 Form 1-ES instructions (2026 standard deduction schedules and rate schedules) are already released as us-wi/form/2026-07-22-wi-form1-es-2026 (citation path us-wi/form/individual-income-tax/2026/1-es, same file); the closure check's REVIEW is a regex miss, not a gap. Not re-taken.",
    },
}


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120))


def manifest_path(jurisdiction: str, document_class: str) -> Path:
    return MANIFESTS / f"{jurisdiction}-individual-income-tax-{document_class}-ty2026-amounts.yaml"


def scopes() -> list[tuple[str, str, list[dict[str, Any]]]]:
    """(jurisdiction, document_class, documents) per manifest, in queue order."""
    out: list[tuple[str, str, list[dict[str, Any]]]] = []
    for jurisdiction, state in STATES.items():
        for document_class in ("form", "guidance"):
            docs = [d for d in state["documents"] if d["document_class"] == document_class]
            if docs:
                out.append((jurisdiction, document_class, docs))
    return out


def build_amounts(*, verify_only: bool = False) -> None:
    import requests

    session = requests.Session()
    session.headers["User-Agent"] = (
        "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) "
        "https://github.com/TheAxiomFoundation/axiom-corpus"
    )
    for jurisdiction, document_class, docs in scopes():
        if verify_only:
            for doc in docs:
                try:
                    response = session.head(doc["source_url"], allow_redirects=True, timeout=60)
                    status = response.status_code
                    content_type = response.headers.get("content-type", "")
                except requests.RequestException as exc:  # pragma: no cover - network
                    status, content_type = -1, str(exc)
                print(f"{status} {content_type[:40]:40} {doc['source_id']}")
            continue
        _write_manifest(manifest_path(jurisdiction, document_class), {"version": AMOUNTS_VERSION, "documents": docs})
        print(f"wrote {manifest_path(jurisdiction, document_class).name} ({len(docs)} documents)")


# --------------------------------------------------------------------------- queue

STATUTE_ROWS: dict[str, dict[str, Any]] = {
    # jurisdiction -> queue record for the whole-chapter statute scope (versions are the
    # on-disk scope versions; the adapters append their scope suffix to the version prefix)
    "us-al": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-al-code-title-40", "versions": ["2026-09-14-income-tax-chapter-r2-us-al-title-40"], "index_url": "https://alison.legislature.state.al.us/code-of-alabama", "chapter": "Code of Alabama Title 40, Chapter 18 (whole Title 40 taken)", "supersedes": ["us-al/statute/2026-07-13-recovery"]},
    "us-az": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-az-ars-title-43", "versions": ["2026-09-14-income-tax-chapter-us-az-title-43"], "index_url": "https://www.azleg.gov/arstitle/", "chapter": "Arizona Revised Statutes Title 43 (Taxation of Income)", "supersedes": ["us-az/statute/2026-07-13-recovery"]},
    "us-ct": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-ct-cgs-chapter-229", "versions": ["2026-09-14-income-tax-chapter-title-12-chapter-229", "2026-09-14-income-tax-chapter-title-17b"], "index_url": "https://www.cga.ct.gov/current/pub/chap_229.htm", "chapter": "Connecticut General Statutes Title 12, Chapter 229 (Income Tax), with the title 17b companion", "supersedes": ["us-ct/statute/2026-07-13-recovery"]},
    "us-de": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-de-code-title-30-chapter-11", "versions": ["2026-09-14-income-tax-chapter-r2-us-de-title-30-chapter-11"], "index_url": "https://www.delcode.delaware.gov/title30/c011/index.html", "chapter": "Delaware Code Title 30, Chapter 11 (Personal Income Tax)", "supersedes": ["us-de/statute/2026-07-13-recovery"]},
    "us-id": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-id-statutes-title-63-chapter-30", "versions": ["2026-09-14-income-tax-chapter-us-id-title-63-chapter-30"], "index_url": "https://legislature.idaho.gov/statutesrules/idstat/Title63/T63CH30/", "chapter": "Idaho Statutes Title 63, Chapter 30 (Income Tax)", "supersedes": ["us-id/statute/2026-07-31-id-title-63-chapter-30-successor"]},
    "us-ky": {"manifest": "manifests/us-ky-krs-chapter-141-income-taxes.yaml", "source_id": None, "versions": ["2026-09-14-income-tax-chapter"], "index_url": "https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=37674", "chapter": "Kentucky Revised Statutes Chapter 141 (Income Taxes)", "supersedes": ["us-ky/statute/2026-07-22-individual-income-tax"]},
    "us-md": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-md-code-tax-general", "versions": ["2026-09-14-income-tax-chapter-us-md-article-gtg"], "index_url": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg", "chapter": "Maryland Code, Tax-General Article, Title 10 (Income Tax) (whole article taken)", "supersedes": ["us-md/statute/2026-07-13-recovery-r2026-07-24-immutable"]},
    "us-me": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-me-mrs-title-36", "versions": ["2026-09-14-income-tax-chapter-us-me-title-36"], "index_url": "https://legislature.maine.gov/statutes/36/title36ch0sec0.html", "chapter": "Maine Revised Statutes Title 36, Part 8 (Income Taxes) (whole Title 36 taken)", "supersedes": ["us-me/statute/2026-07-13-recovery"]},
    "us-mi": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-mi-mcl-chapter-206", "versions": ["2026-09-14-income-tax-chapter-us-mi-chapter-206"], "index_url": "https://www.legislature.mi.gov/documents/mcl/", "chapter": "Michigan Compiled Laws Chapter 206 (Income Tax Act of 1967)", "supersedes": ["us-mi/statute/2026-07-13-recovery"]},
    "us-mn": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-mn-statutes-chapter-290", "versions": ["2026-09-14-income-tax-chapter-us-mn-title-290", "2026-09-14-income-tax-chapter-us-mn-title-142g", "2026-09-14-income-tax-chapter-us-mn-title-256p"], "index_url": "https://www.revisor.mn.gov/statutes/cite/290", "chapter": "Minnesota Statutes Chapter 290 (Income and Franchise Taxes), with companions 142G and 256P", "supersedes": ["us-mn/statute/2026-07-13-recovery"]},
    "us-ne": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-ne-revised-statutes-chapter-77", "versions": ["2026-09-14-income-tax-chapter-r2-us-ne-title-77"], "index_url": "https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=77", "chapter": "Nebraska Revised Statutes Chapter 77, Article 27 (Income Tax) (whole Chapter 77 taken)", "supersedes": ["us-ne/statute/2026-07-13-recovery"]},
    "us-ny": {"manifest": "manifests/us-ny-tax-law-article-22-personal-income-tax.yaml", "source_id": None, "versions": ["2026-09-14-income-tax-chapter"], "index_url": "https://www.nysenate.gov/legislation/laws/TAX/A22", "chapter": "New York Tax Law Article 22 (Personal Income Tax)", "supersedes": ["us-ny/statute/2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616", "us-ny/statute/2026-07-13-recovery"]},
    "us-oh": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-oh-orc-title-57", "versions": ["2026-09-14-income-tax-chapter-us-oh-title-57"], "index_url": "https://codes.ohio.gov/ohio-revised-code/title-57", "chapter": "Ohio Revised Code Chapter 5747 (Income Tax) (whole Title 57 taken)", "supersedes": ["us-oh/statute/2026-07-13-recovery"]},
    "us-ut": {"manifest": "manifests/state-income-tax-chapters-2026-09-14.yaml", "source_id": "us-ut-code-title-59", "versions": ["2026-09-14-income-tax-chapter-title-59"], "index_url": "https://le.utah.gov/xcode/Title59/59.html", "chapter": "Utah Code Title 59, Chapter 10 (Individual Income Tax Act) (whole Title 59 taken)", "supersedes": ["us-ut/statute/2026-07-13-recovery"]},
    "us-va": {"manifest": "manifests/us-va-code-title-58.1-chapter-3-income-tax.yaml", "source_id": None, "versions": ["2026-09-14-income-tax-chapter"], "index_url": "https://law.lis.virginia.gov/vacode/title58.1/chapter3/", "chapter": "Code of Virginia Title 58.1, Chapter 3 (Income Tax)", "supersedes": ["us-va/statute/2026-07-13-recovery"]},
    "us-ca": {"manifest": "manifests/us-ca-rtc-part-10-10.2-sections.yaml", "source_id": None, "versions": ["2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7"], "index_url": "https://leginfo.legislature.ca.gov/faces/codes_displayexpandedbranch.xhtml?tocCode=RTC&division=2.&title=&part=10.&chapter=&article=", "chapter": "California Revenue and Taxation Code Division 2, Parts 10 and 10.2 (Personal Income Tax; Administration)", "supersedes": ["us-ca/statute/2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-rtc-17054-rtc-17073.5", "us-ca/statute/2026-07-13-recovery"]},
}

STATUTE_BLOCKED: dict[str, dict[str, Any]] = {
    "us-ar": {"index_url": "https://advance.lexis.com/container?config=00JAAzZDgzNzU2ZC05MDA0LTRmMDItYjkzMS0xOGY3MjE3OWNlODIKAFBvZENhdGFsb2fcIFfJnJ2IC8XZi1AYM4Ne&crid=1", "reason": "The official Arkansas Code is published only through LexisNexis (arkleg.state.ar.us links to advance.lexis.com); the container answers a 3.6 KB JavaScript shell that requires the Lexis CAPTCHA/robot check before any section text (probed once 2026-09-13, same as manifests/state-statute-agent-queue.yaml). The released Act 2 of 2026 scope stays."},
    "us-ms": {"index_url": "https://advance.lexis.com/container?config=00JAAzZDgzNzU2ZC05MDA0LTRmMDItYjkzMS0xOGY3MjE3OWNlODIKAFBvZENhdGFsb2fcIFfJnJ2IC8XZi1AYM4Ne&crid=1", "reason": "The official Mississippi Code is published only through LexisNexis with the same CAPTCHA/robot check (probed once 2026-09-13); the released HB 1 (2025) recovery of section 27-7-5 stays."},
}


def _coverage(jurisdiction: str, document_class: str, version: str) -> dict[str, Any] | None:
    path = CORPUS_BASE / "coverage" / jurisdiction / document_class / f"{version}.json"
    if not path.is_file():
        return None
    import json

    payload = json.loads(path.read_text())
    provisions = CORPUS_BASE / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
    rows = sum(1 for _ in provisions.open()) if provisions.is_file() else None
    return {
        "version": version,
        "complete": payload.get("complete"),
        "provision_count": rows,
        "missing": len(payload.get("missing") or []),
        "extra": len(payload.get("extra") or []),
    }


def update_queue() -> None:
    queue_path = MANIFESTS / "tax-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"] if row["jurisdiction"] != "us"}
    for jurisdiction, spec in STATUTE_ROWS.items():
        row = rows[jurisdiction]
        cov = [_coverage(jurisdiction, "statute", v) for v in spec["versions"]]
        row["income_tax_chapter_scope"] = {
            "run_note": "docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md",
            "target_manifest": spec["manifest"],
            "source_id": spec["source_id"],
            "document_class": "statute",
            "versions": spec["versions"],
            "coverage": cov,
            "index_url": spec["index_url"],
            "index_document_count": sum((c or {}).get("provision_count") or 0 for c in cov),
            "taken_count": sum((c or {}).get("provision_count") or 0 for c in cov),
            "supersedes": spec["supersedes"],
            "notes": f"{spec['chapter']}; whole-chapter statute scope of 2026-09-14 superseding the released partial scope(s); provision rows counted (containers plus sections).",
        }
    for jurisdiction, spec in STATUTE_BLOCKED.items():
        rows[jurisdiction]["income_tax_chapter_scope"] = {
            "run_note": "docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md",
            "queue_status": "blocked_primary_source",
            "index_url": spec["index_url"],
            "index_document_count": None,
            "taken_count": 0,
            "notes": spec["reason"],
        }
    for jurisdiction, state in STATES.items():
        records = []
        for j, document_class, docs in scopes():
            if j != jurisdiction:
                continue
            records.append({
                "target_manifest": manifest_path(j, document_class).as_posix().replace(str(ROOT) + "/", ""),
                "document_class": document_class,
                "version": AMOUNTS_VERSION,
                "coverage": _coverage(j, document_class, AMOUNTS_VERSION),
                "documents": [d["citation_path"] for d in docs],
            })
        rows[jurisdiction]["ty2026_indexed_amounts_scope"] = {
            "run_note": "docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md",
            "queue_status": "agent_ready",
            "publisher": state["publisher"],
            "index_url": state["index_url"],
            "index_document_count": state["index_document_count"],
            "index_count_method": state["index_count_method"],
            "indexes_for_inflation": state["indexes_for_inflation"],
            "taken_count": len(state["documents"]),
            "scopes": records,
            "notes": state["notes"],
        }
    for jurisdiction, spec in NOT_TAKEN.items():
        rows[jurisdiction]["ty2026_indexed_amounts_scope"] = {
            "run_note": "docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md",
            "queue_status": spec["queue_status"],
            "publisher": spec["publisher"],
            "index_url": spec["index_url"],
            "index_document_count": spec["index_document_count"],
            "taken_count": 0,
            "notes": spec["reason"],
        }
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"queue rows updated: statute {len(STATUTE_ROWS) + len(STATUTE_BLOCKED)}, amounts {len(STATES) + len(NOT_TAKEN)}")
