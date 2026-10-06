"""Wave 6 tax-mn-oh: build the official-documents manifests for the program-bundle gaps.

Work order: docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-mn-oh.csv (bundle-gaps branch).
Every document below was fetched once from its official publisher on 2026-10-06 with the corpus
user agent (revenue.nh.gov with the documented chrome120 fallback; tax.ohio.gov with the
documented browser fallback) and its printed tax year was read from page 1 before it was listed.

Each entry lists the work-order ids it closes (``rows``). ``source_url`` is the bundle address
whenever that address served the document; ``download_url`` is set only where the publisher
redirects to a different file host.

Usage:
    uv run python scripts/build_w6_tax_mn_oh_manifests.py            # write manifests
    uv run python scripts/build_w6_tax_mn_oh_manifests.py --list     # print the table
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-10-06"
RUN = "w6"
WORK_ORDER = "program-bundle-gaps-2026-10-06/wave6/tax-mn-oh.csv"

AGENCY = {
    "us-mn": ("department-of-revenue", "Minnesota Department of Revenue"),
    "us-mo": ("dor", "Missouri Department of Revenue"),
    "us-ms": ("dor", "Mississippi Department of Revenue"),
    "us-mt": ("mtdor", "Montana Department of Revenue"),
    "us-nc": ("ncdor", "North Carolina Department of Revenue"),
    "us-nd": ("otc", "North Dakota Office of State Tax Commissioner"),
    "us-ne": ("dor", "Nebraska Department of Revenue"),
    "us-nh": ("dra", "New Hampshire Department of Revenue Administration"),
    "us-nj": ("taxation", "New Jersey Division of Taxation"),
    "us-nm": ("trd", "New Mexico Taxation and Revenue Department"),
    "us-ny": ("tax", "New York State Department of Taxation and Finance"),
    "us-oh": ("odt", "Ohio Department of Taxation"),
}

PDF = {"segmentation": "single_block"}
NH_REQUEST = {
    "browser_user_agent": True,
    "browser_impersonation": True,
    "browser_impersonation_direct": True,
}
OH_REQUEST = {"browser_impersonation": True}

DOCS: list[dict] = []


def add(jur, cls, path, title, url, *, rows=None, ty=None, sub=None, fmt="pdf", selector=None,
        download_url=None, request=None, authority=None, expression_date=None, note=None,
        index_url=None, text_selector=None, drop=None):
    """Register one document. ``path`` is relative to ``<jur>/<cls>/``."""
    extraction = dict(PDF) if fmt == "pdf" else {"html_content_selector": selector or "body"}
    if text_selector:
        extraction["html_text_selector"] = text_selector
    if drop:
        extraction["html_drop_selectors"] = list(drop)
    DOCS.append(
        {
            "jurisdiction": jur,
            "document_class": cls,
            "citation_path": f"{jur}/{cls}/{path}",
            "title": title,
            "source_url": url,
            "download_url": download_url,
            "source_format": fmt,
            "extraction": extraction,
            "request": request,
            "tax_year": ty,
            "document_subtype": sub,
            "source_authority": authority or AGENCY[jur][1],
            "expression_date": expression_date or (f"{ty}-01-01" if ty else SOURCE_AS_OF),
            "rows": list(rows or [url]),
            "note": note,
            "index_url": index_url,
        }
    )


def form(jur, ty, ident, title, url, **kw):
    add(jur, "form", f"{AGENCY[jur][0]}/ty{ty}/{ident}", title, url, ty=str(ty),
        sub=kw.pop("sub", "form"), **kw)


def guidance(jur, path, title, url, **kw):
    add(jur, "guidance", path, title, url, sub=kw.pop("sub", "department_web_page"), **kw)


def statute(jur, path, title, url, **kw):
    add(jur, "statute", path, title, url, authority=kw.pop("authority"), sub=kw.pop("sub", "statute_section"), **kw)


# --------------------------------------------------------------------------------------------
# Minnesota (revenue.state.mn.us, revisor.mn.gov)
MN = "https://www.revenue.state.mn.us/sites/default/files/"
MN_INDEX = "https://www.revenue.state.mn.us/form-search"
MN_SCHEDULES = {
    "m1ref": "Schedule M1REF, Refundable Credits",
    "m1c": "Schedule M1C, Nonrefundable Credits",
    "m1cd": "Schedule M1CD, Child and Dependent Care Credit",
    "m1ma": "Schedule M1MA, Marriage Credit",
    "m1mt": "Schedule M1MT, Alternative Minimum Tax",
    "m1r": "Schedule M1R, Age 65 or Older/Disabled Subtraction",
    "m1sa": "Schedule M1SA, Minnesota Itemized Deductions",
    "m1m": "Schedule M1M, Income Additions and Subtractions",
    "m1qpen": "Schedule M1QPEN, Qualified Public Pension Subtraction",
    "m1cwfc": "Schedule M1CWFC, Minnesota Child and Working Family Credits",
    "niit": "Schedule NIIT, Net Investment Income Tax",
    "m1dqc": "Schedule M1DQC, Dependents and Qualifying Children",
    "m1ed": "Schedule M1ED, K-12 Education Credit",
    "m1rent": "Schedule M1RENT, Renter's Credit",
    "m1529": "Schedule M1529, Education Savings Account Contribution Credit or Subtraction",
}
for file, ty, sched, extra_rows in [
    ("2021-12/m1ref_21_0.pdf", 2021, "m1ref", ()),
    ("2022-12/m1ref_22.pdf", 2022, "m1ref", ()),
    ("2023-01/m1c_22.pdf", 2022, "m1c", ()),
    ("2023-01/m1cd_22_0.pdf", 2022, "m1cd", ()),
    ("2023-01/m1ma_21.pdf", 2021, "m1ma", ()),
    ("2023-01/m1ma_22.pdf", 2022, "m1ma", ()),
    ("2023-01/m1mt_22.pdf", 2022, "m1mt", ()),
    ("2023-01/m1r_21.pdf", 2021, "m1r", ()),
    ("2023-01/m1r_22.pdf", 2022, "m1r", ()),
    ("2023-01/m1sa_22.pdf", 2022, "m1sa", ()),
    ("2023-02/m1cd_21.pdf", 2021, "m1cd", ()),
    ("2023-02/m1mt_21.pdf", 2021, "m1mt", ()),
    ("2023-12/m1cd-23.pdf", 2023, "m1cd", ()),
    ("2023-12/m1ma-23.pdf", 2023, "m1ma", ()),
    ("2023-12/m1mt-23.pdf", 2023, "m1mt", ()),
    ("2023-12/m1r-23.pdf", 2023, "m1r", ()),
    ("2024-01/m1c_21.pdf", 2021, "m1c", ()),
    ("2024-01/m1m-22.pdf", 2022, "m1m", ()),
    ("2024-04/m1m-23_0.pdf", 2023, "m1m", ()),
    ("2024-04/m1ref-23.pdf", 2023, "m1ref", ()),
    ("2024-12/m1cd-24.pdf", 2024, "m1cd", ()),
    ("2024-12/m1ma-24.pdf", 2024, "m1ma", ()),
    ("2024-12/m1qpen-24.pdf", 2024, "m1qpen", ()),
    ("2024-12/m1r-24.pdf", 2024, "m1r", ()),
    ("2024-12/m1sa-24.pdf", 2024, "m1sa", ()),
    ("2025-01/m1cwfc-23.pdf", 2023, "m1cwfc", ()),
    ("2025-01/m1cwfc-24.pdf", 2024, "m1cwfc", ()),
    ("2025-02/m1c-24.pdf", 2024, "m1c", ()),
    ("2025-07/m1mt-24.pdf", 2024, "m1mt", ()),
    ("2025-08/m1ref-24.pdf", 2024, "m1ref", ()),
    ("2025-11/m1m-24.pdf", 2024, "m1m", ()),
    ("2025-12/m1c-23.pdf", 2023, "m1c", ()),
    ("2025-12/m1ref-25.pdf", 2025, "m1ref", ()),
    ("2025-12/m1sa-23.pdf", 2023, "m1sa", ()),
    ("2025-12/m1sa-25_0.pdf", 2025, "m1sa", ()),
    ("2025-12/niit-25.pdf", 2025, "niit", ()),
    ("2026-01/m1dqc-25.pdf", 2025, "m1dqc", ()),
    ("2026-07/m1cd-25.pdf", 2025, "m1cd", ()),
    ("2026-07/m1cwfc-25.pdf", 2025, "m1cwfc", ()),
    ("2026-07/m1ed-25.pdf", 2025, "m1ed", ()),
    ("2026-07/m1m-25.pdf", 2025, "m1m", ()),
    ("2026-07/m1ma-25.pdf", 2025, "m1ma", ()),
    ("2026-07/m1mt-25.pdf", 2025, "m1mt", ()),
    ("2026-07/m1qpen-25.pdf", 2025, "m1qpen", ()),
    ("2026-07/m1r-25.pdf", 2025, "m1r", ()),
    ("2026-07/m1rent-25.pdf", 2025, "m1rent", ()),
    ("2026-08/m1529-25.pdf", 2025, "m1529", ()),
    # Official copies of the two third-party rows (taxsim.nber.org, taxformfinder.org):
    ("2023-02/m1sa_21.pdf", 2021, "m1sa", ("https://taxsim.nber.org/historical_state_tax_forms/MN/2021/m1sa_21.pdf",)),
    ("2024-01/m1m-21.pdf", 2021, "m1m", ("https://www.taxformfinder.org/forms/2021/2021-minnesota-form-m1m.pdf",)),
]:
    url = MN + file
    rows = list(extra_rows) if extra_rows else [url]
    form("us-mn", ty, f"schedule-{sched}", f"{ty} {MN_SCHEDULES[sched]}", url, rows=rows,
         sub="schedule", index_url=MN_INDEX)
for file, ty in [("2023-12/m1_21_0.pdf", 2021), ("2023-12/m1_22.pdf", 2022), ("2026-01/m1-24.pdf", 2024)]:
    form("us-mn", ty, "form-m1", f"{ty} Form M1, Minnesota Individual Income Tax", MN + file,
         sub="return_form", index_url=MN_INDEX)
for file, ty in [("2023-12/m1_inst_21.pdf", 2021), ("2024-02/m1-inst-22.pdf", 2022),
                 ("2025-06/m1-inst-23.pdf", 2023), ("2026-01/m1-inst-24.pdf", 2024)]:
    form("us-mn", ty, "form-m1-instructions", f"{ty} Minnesota Individual Income Tax Instructions (Form M1)",
         MN + file, sub="instructions", index_url=MN_INDEX)
for file, ty in [("2023-12/Inflation%20Adjustments%20TY%202021.pdf", 2021),
                 ("2023-12/Inflation_Adjustments_TY_2022.pdf", 2022),
                 ("2023-12/inflation-adjusted-amounts-ty-2024.pdf", 2024)]:
    guidance("us-mn", f"department-of-revenue/ty{ty}/inflation-adjusted-amounts",
             f"Tax Year {ty} Inflation-Adjusted Amounts in Minnesota Statutes", MN + file, ty=str(ty),
             sub="inflation_adjustment_notice", fmt="pdf")
guidance("us-mn", "department-of-revenue/crp-instructions", "Certificate of Rent Paid (CRP) Instructions",
         "https://www.revenue.state.mn.us/crp-instructions", fmt="html", selector=".uswds-main-content-wrapper")
guidance("us-mn", "department-of-revenue/education-savings-account-contribution-subtraction",
         "Education Savings Account Contribution Subtraction",
         "https://www.revenue.state.mn.us/education-savings-account-contribution-subtraction", fmt="html",
         selector=".uswds-main-content-wrapper")
statute("us-mn", "270C.22", "Minnesota Statutes 270C.22, Statutory Inflation Adjustments (2025 Minnesota Statutes)",
        "https://www.revisor.mn.gov/statutes/cite/270c.22", fmt="html", selector="main",
        authority="Minnesota Office of the Revisor of Statutes")

# --------------------------------------------------------------------------------------------
# Missouri (dor.mo.gov, revisor.mo.gov, senate.mo.gov)
MOF = "https://dor.mo.gov/forms/"
MO_INDEX = "https://dor.mo.gov/forms/"
MO_MANIFEST = "us-mo/form/individual_income_tax_forms/dor.mo.gov/forms/"
for ty, ident in [(2021, "form-mo-1040"), (2023, "form-mo-1040")]:
    form("us-mo", ty, ident, f"{ty} Form MO-1040, Individual Income Tax Return (fillable calculating version)",
         f"{MOF}MO-1040%20Fillable%20Calculating_{ty}.pdf",
         rows=[f"{MO_MANIFEST}mo-1040-20fillable-20calculating_{ty}"], sub="return_form")
form("us-mo", 2021, "form-mo-1040-print-only", "2021 Form MO-1040, Individual Income Tax Return - Long Form (print only)",
     f"{MOF}MO-1040%20Print%20Only_2021.pdf", rows=[f"{MO_MANIFEST}mo-1040-20print-20only_2021"], sub="return_form")
for ty in range(2017, 2025):
    form("us-mo", ty, "form-mo-1040-instructions", f"{ty} Form MO-1040 Instructions (Individual Income Tax)",
         f"{MOF}MO-1040%20Instructions_{ty}.pdf", rows=[f"{MO_MANIFEST}mo-1040-20instructions_{ty}"],
         sub="instructions")
form("us-mo", 2021, "form-4711", "2021 Missouri Income Tax Reference Guide (Form 4711, revised 12-2021)",
     f"{MOF}4711_2021.pdf", sub="reference_guide")
form("us-mo", 2025, "form-5695", "Form 5695, Qualified Health Insurance Premiums Worksheet for MO-A (2025)",
     f"{MOF}5695.pdf", sub="worksheet")
for ty in range(2020, 2025):
    form("us-mo", ty, "form-mo-a", f"{ty} Form MO-A, Individual Income Tax Adjustments", f"{MOF}MO-A_{ty}.pdf",
         sub="schedule")
form("us-mo", 2025, "form-mo-ptc-instructions", "2025 Form MO-PTC, Property Tax Credit Claim, with instructions",
     f"{MOF}MO-PTC%20Instructions_2025.pdf", sub="instructions")
for ty in (2021, 2023, 2024):
    form("us-mo", ty, "form-mo-pts", f"{ty} Form MO-PTS, Property Tax Credit Schedule", f"{MOF}MO-PTS_{ty}.pdf",
         sub="schedule")
for ty in (2023, 2024):
    form("us-mo", ty, "form-mo-wftc", f"{ty} Form MO-WFTC, Missouri Working Family Tax Credit",
         f"{MOF}MO-WFTC_{ty}.pdf", sub="schedule")
form("us-mo", 2025, "property-tax-claim-chart", "2025 Property Tax Credit Claim Chart (MO-PTC / MO-PTS)",
     f"{MOF}Property%20Tax%20Claim%20Chart_2025.pdf", sub="tax_table")
guidance("us-mo", "dor/ty2025/withholding-table-weekly", "2025 Missouri Income Tax Withholding Table - Weekly",
         f"{MOF}Withholding%20Table%20-%20Weekly_2025.pdf", fmt="pdf", ty="2025", sub="withholding_table")
guidance("us-mo", "dor/faq-capital-gains-subtraction", "Capital Gains Subtraction FAQs (Section 143.121 RSMo)",
         "https://dor.mo.gov/faq/taxation/individual/capital-gains-subtraction.html", fmt="html",
         selector="#main-content", sub="faq")
guidance("us-mo", "dor/faq-missouri-working-family-tax-credit",
         "Missouri Working Family Tax Credit FAQs (Section 143.177 RSMo)",
         "https://dor.mo.gov/faq/taxation/individual/missouri-working-family-tax-credit.html", fmt="html",
         selector="#main-content", sub="faq")
guidance("us-mo", "dor/individual-income-tax-year-changes", "Individual Income Tax Year Changes (What's New?)",
         "https://dor.mo.gov/taxation/individual/tax-types/income/year-changes/", fmt="html", selector="#main-content")
MO_RSMO = "Missouri Revisor of Statutes"
RV = "https://revisor.mo.gov/main/OneSection.aspx?"
statute("us-mo", "135.010", "RSMo 135.010, Definitions (property tax credit) (effective 28 Aug 2025)",
        RV + "section=135.010&bid=57540", authority=MO_RSMO, selector="body", fmt="html")
statute("us-mo", "135.010--effective-2008-08-28",
        "RSMo 135.010, Definitions (property tax credit) (version effective 28 Aug 2008 to 28 Aug 2025)",
        RV + "section=135.010&bid=6435", authority=MO_RSMO, selector="body", fmt="html",
        rows=[RV + "section=135.010&bid=6435", RV + "section=135.010&bid=6435&hl=property+tax+credit%u2044"],
        sub="statute_section_historical_version")
statute("us-mo", "135.020", "RSMo 135.020, Credit allowed (property tax credit) (effective 1 Oct 1973)",
        RV + "section=135.020&bid=6437", authority=MO_RSMO, selector="body", fmt="html")
statute("us-mo", "135.025", "RSMo 135.025, Accrued taxes and rent constituting taxes to be totaled (effective 28 Aug 2025)",
        RV + "section=135.025", authority=MO_RSMO, selector="body", fmt="html")
statute("us-mo", "135.025--effective-2008-08-28",
        "RSMo 135.025 (version effective 28 Aug 2008 to 28 Aug 2025)", RV + "section=135.025&bid=6438",
        authority=MO_RSMO, selector="body", fmt="html", sub="statute_section_historical_version")
statute("us-mo", "135.030", "RSMo 135.030, Amount of credit (effective 28 Aug 2025)", RV + "section=135.030",
        authority=MO_RSMO, selector="body", fmt="html",
        rows=[RV + "section=135.030", RV + "section=135.030&bid=57542"])
statute("us-mo", "135.030--effective-2008-08-28", "RSMo 135.030 (version effective 28 Aug 2008 to 28 Aug 2025)",
        RV + "section=135.030&bid=6439", authority=MO_RSMO, selector="body", fmt="html",
        sub="statute_section_historical_version")
statute("us-mo", "143.121--effective-2007-08-28",
        "RSMo 143.121, Missouri adjusted gross income (version effective 28 Aug 2007, superseded)",
        "https://www.revisor.mo.gov/main/OneSection.aspx?bid=50493&section=143.121", authority=MO_RSMO,
        selector="body", fmt="html", sub="statute_section_historical_version")
statute("us-mo", "bills/2025/hb594-bill-information", "HB 594 (2025) Bill Information - Missouri Senate",
        "https://www.senate.mo.gov/BillTracking/Bills/BillInformation?year=2025&billid=4957943",
        authority="Missouri Senate", selector="main", fmt="html", sub="bill_information_page")

# --------------------------------------------------------------------------------------------
# Mississippi (dor.ms.gov, billstatus.ls.state.ms.us)
MSF = "https://www.dor.ms.gov/sites/default/files/"
form("us-ms", 2024, "form-80-100-instructions",
     "2024 Resident, Non-Resident and Part-Year Resident Income Tax Instructions (Form 80-100-24-1-1-000, Rev. 10/24)",
     MSF + "Forms/Individual/80100241.pdf", download_url=MSF + "tax-forms/individual/80100241.pdf",
     rows=[MSF + "Forms/Individual/80100241.pdf", MSF + "forms/individual/80100241.pdf"], sub="instructions")
for f, ty, rev in [("80100211_0.pdf", 2021, "Rev. 8/21"), ("80100221.pdf", 2022, "Rev. 11/22"),
                   ("80100231.pdf", 2023, "Rev. 09/23")]:
    form("us-ms", ty, "form-80-100-instructions",
         f"{ty} Resident, Non-Resident and Part-Year Resident Income Tax Instructions (Form 80-100, {rev})",
         MSF + "tax-forms/individual/" + f, sub="instructions")
for f, ty in [("80105228.pdf", 2022), ("80105248.pdf", 2024)]:
    form("us-ms", ty, "form-80-105", f"{ty} Mississippi Resident Individual Income Tax Return (Form 80-105)",
         MSF + "tax-forms/individual/" + f, sub="return_form")
form("us-ms", 2022, "form-80-108", "2022 Mississippi Adjustments and Contributions (Form 80-108)",
     MSF + "tax-forms/individual/80108228.pdf", sub="schedule")
MSB = "https://billstatus.ls.state.ms.us/documents/"
statute("us-ms", "session-laws/2017/sb2311", "Senate Bill 2311, 2017 Regular Session (as signed by the Governor)",
        MSB + "2017/pdf/SB/2300-2399/SB2311SG.pdf", authority="Mississippi Legislature", fmt="pdf",
        sub="session_law")
statute("us-ms", "session-laws/2023/hb1671",
        "House Bill 1671, 2023 Regular Session (as signed by the Governor): tax credits; revise certain existing and authorize additional",
        MSB + "2023/pdf/HB/1600-1699/HB1671SG.pdf", authority="Mississippi Legislature", fmt="pdf",
        sub="session_law", rows=["https://legiscan.com/MS/text/HB1671/id/2767768"])

# --------------------------------------------------------------------------------------------
# Montana (revenue.mt.gov, revenuefiles.mt.gov, legmt.gov)
MTF = "https://revenuefiles.mt.gov/files/Forms/"
MT2 = MTF + "Montana-Individual-Income-Tax-Return-Form-2/"
MT2I = MTF + "Montana-Individual-Income-Tax-Return-Form-2-Instructions/"
MTREV = "https://revenue.mt.gov/files/Forms/Montana-Individual-Income-Tax-Return-Form-2/"
TAXSIM_MT = "https://taxsim.nber.org/historical_state_tax_forms/MT/"
for ty, extra in [(2021, [MTREV + "2021_Montana_Individual_Income_Tax_Return_Form_2.pdf", TAXSIM_MT + "2021/form%202%202021.pdf"]),
                  (2022, []),
                  (2023, [MTREV + "2023_Montana_Individual_Income_Tax_Return_Form_2.pdf"]),
                  (2024, [MTREV + "2024_Montana_Individual_Income_Tax_Return_Form_2.pdf"])]:
    url = f"{MT2}{ty}_Montana_Individual_Income_Tax_Return_Form_2.pdf"
    form("us-mt", ty, "form-2", f"{ty} Montana Individual Income Tax Return (Form 2)", url, rows=[url, *extra],
         sub="return_form")
for ty, extra in [
    (2021, [TAXSIM_MT + "2021/form%202%202021%20instructions.pdf", "https://www.zillionforms.com/2021/I7184008043.PDF"]),
    (2022, ["https://mtrevenue.gov/wp-content/uploads/dlm_uploads/2022/12/Form-2-2022-Instructions.pdf"]),
    (2023, []),
    (2024, [TAXSIM_MT + "2024/Form_2_2024_Instrux.pdf"]),
]:
    url = f"{MT2I}{ty}_Montana_Individual_Income_Tax_Return_Form_2_Instructions.pdf"
    form("us-mt", ty, "form-2-instructions", f"{ty} Montana Form 2 Individual Income Tax Instructions", url,
         rows=[url, *extra], sub="instructions")
form("us-mt", 2024, "form-2-instructions-rev-2024-12-03",
     "2024 Montana Form 2 Individual Income Tax Instructions (file of 2024-12-03 under the Form 2 folder)",
     MT2 + "2024_Montana_Individual_Income_Tax_Return_Form_2_Instructions.pdf", sub="instructions",
     note="Second 2024 instructions file on the publisher's file host (PDF modified 2024-12-03; the Form-2-Instructions "
          "folder copy is modified 2024-12-17); same page count, text differs.")
form("us-mt", 2024, "schedule-2ec", "2024 Montana Form 2 Schedule 2EC, Elderly Homeowner/Renter Credit",
     MT2 + "Form_2_2024_Schedule_2EC.pdf", sub="schedule")
url_2441 = MTF + "Child-and-Dependent-Care-Expense-Deduction-Form-2441-M/2022_Child_and_Dependent_Care_Expense_Deduction_Form_2441-M.pdf"
form("us-mt", 2022, "form-2441-m", "2022 Montana Form 2441-M, Child and Dependent Care Expense Deductions", url_2441,
     rows=[url_2441, "https://mtrevenue.gov/wp-content/uploads/dlm_uploads/2022/12/2441-M_2022.pdf"], sub="schedule")
guidance("us-mt", "mtdor/montana-tax-simplification-resource-hub", "Montana Tax Simplification Resource Hub",
         "https://revenue.mt.gov/montana-tax-simplification-resource-hub", fmt="html", selector="main")
guidance("us-mt", "mtdor/2025-legislative-roundup-529-changes",
         "2025 Legislative Roundup - Changes to the 529 College Savings Subtraction",
         "https://revenue.mt.gov/news/recent-news/529-changes", fmt="html", selector="main", sub="news_release")
for ty in (2024, 2025):
    guidance("us-mt", f"mtdor/ty{ty}/tax-tables-and-deductions", f"{ty} Montana Tax Tables and Deductions",
             f"https://revenue.mt.gov/taxes/tax-tables-and-deductions/{ty}", fmt="html", selector="main", ty=str(ty))
guidance("us-mt", "mtdor/2024-income-and-property-tax-rebate-report",
         "Montana Department of Revenue, Income Tax and Property Tax Rebate Report (May 9, 2024; Revenue Interim Committee)",
         "https://archive.legmt.gov/content/Committees/Interim/2023-2024/Revenue/Meetings/May-2024/5.1-DOR-rebate-report.pdf",
         fmt="pdf", sub="agency_report")
guidance("us-mt", "legislative-services-division/2021-montana-legislative-review",
         "Montana Legislative Review: A Summary of Enactments in the 67th Montana Legislature (2021)",
         "https://www.leg.mt.gov/content/Publications/sales/2021-legislative-review.pdf",
         download_url="https://archive.legmt.gov/content/Publications/sales/2021-legislative-review.pdf",
         fmt="pdf", sub="legislative_summary", authority="Montana Legislative Services Division")
MTA = "Montana Legislature"
statute("us-mt", "session-laws/2021/sb399", "Senate Bill 399 (2021): An act generally revising taxation of income (enrolled)",
        "https://docs.legmt.gov/download-ticket?ticketId=fa765563-ee0b-4c30-8549-720e03d0f349", authority=MTA,
        fmt="pdf", sub="session_law",
        rows=["https://docs.legmt.gov/download-ticket?ticketId=fa765563-ee0b-4c30-8549-720e03d0f349",
              "https://leg.mt.gov/bills/2021/billpdf/SB0399.pdf"])
statute("us-mt", "bills/2021/sb399-version-3", "Senate Bill 399 (2021), version SB 399.3",
        "https://docs.legmt.gov/download-ticket?ticketId=2f0614a3-8bb9-4b4e-93de-21647c203b7c", authority=MTA,
        fmt="pdf", sub="bill_version")
statute("us-mt", "session-laws/2023/hb222",
        "House Bill 222 (2023): An act providing for a property tax rebate on a principal residence (enrolled)",
        "https://docs.legmt.gov/download-ticket?ticketId=ff6faf83-515f-4472-a079-c41a4a75e827", authority=MTA,
        fmt="pdf", sub="session_law")
for ed, _folder, url in [
    ("2019", "2019", "https://mca.legmt.gov/bills/2019/mca/title_0150/chapter_0300/part_0210/section_0310/0150-0300-0210-0310.html"),
    ("2021", "2022", "https://mca.legmt.gov/bills/2022/mca/title_0150/chapter_0300/part_0210/section_0310/0150-0300-0210-0310.html"),
]:
    statute("us-mt", f"15-30-2131--mca-{ed}",
            f"MCA 15-30-2131, Deductions allowed in computing net income (Montana Code Annotated {ed})", url,
            authority="Montana Legislative Services Division", fmt="html", selector="body",
            sub="statute_section_historical_edition")

# --------------------------------------------------------------------------------------------
# North Carolina (ncdor.gov, ncleg.gov)
NCD = "https://www.ncdor.gov/"
for ty, ident, title, url in [
    (2021, "form-d-400-schedule-s", "2021 D-400 Schedule S, North Carolina Supplemental Schedule", NCD + "2021-d-400-schedule-s-north-carolina-supplemental-schedule-web/open"),
    (2021, "form-d-401-instructions", "2021 Form D-401, North Carolina Individual Income Tax Instructions", NCD + "2021-d-401-individual-income-tax-instructions/open"),
    (2022, "form-d-400", "2022 Form D-400, Individual Income Tax Return (handwritten version)", NCD + "2022-d-400-handwritten-version/open"),
    (2022, "form-d-400-schedule-s", "2022 D-400 Schedule S, North Carolina Supplemental Schedule", NCD + "2022-d-400-schedule-s-web-fill-version/open"),
    (2022, "form-d-400tc", "2022 Form D-400TC, Individual Tax Credits", NCD + "2022-d-400tc-web-fill-version/open"),
    (2022, "form-d-401-instructions", "2022 Form D-401, North Carolina Individual Income Tax Instructions", NCD + "2022-d-401-individual-income-tax-instructions/open"),
    (2023, "form-d-400", "2023 Form D-400, Individual Income Tax Return (handwritten version)", NCD + "2023-d-400-handwritten-version/open"),
    (2023, "form-d-400-schedule-s", "2023 D-400 Schedule S, North Carolina Supplemental Schedule", NCD + "2023-d-400-schedule-s-web-fill-version/open"),
    (2023, "form-d-400tc", "2023 Form D-400TC, Individual Tax Credits", NCD + "2023-d-400tc-web-fill-version/open"),
    (2023, "form-d-401-instructions", "2023 Form D-401, North Carolina Individual Income Tax Instructions", NCD + "2023-d-401-individual-income-tax-instructions/open"),
    (2024, "form-d-401-instructions", "2024 Form D-401, North Carolina Individual Income Tax Instructions", NCD + "2024-d-401-individual-income-tax-instructions/open"),
    (2017, "form-d-400tc", "2017 Form D-400TC, Individual Tax Credits", NCD + "documents/files/2017-d-400tc-webfill-0/open"),
    (2017, "form-d-401-instructions", "2017 Form D-401, North Carolina Individual Income Tax Instructions", NCD + "documents/files/2017-d-401-individual-income-tax-instructions/open"),
]:
    form("us-nc", ty, ident, title, url, sub="instructions" if "instructions" in ident else "form")
form("us-nc", 2021, "form-d-401-instructions-rev-2022-03-04",
     "2021 Form D-401, North Carolina Individual Income Tax Instructions (instruction booklet file, revised 2022-03-04)",
     NCD + "2021-d-401-instruction-bookletpdf/open", sub="instructions",
     note="Second 2021 D-401 file (PDF modified 2022-03-04; the other 2021 file is modified 2021-12-21); text differs.")
NCT = NCD + "taxes-forms/individual-income-tax/"
guidance("us-nc", "ncdor/north-carolina-child-deduction", "North Carolina Child Deduction",
         NCT + "filing-topics/north-carolina-child-deduction", fmt="html", selector="main#main-wrapper",
         rows=[NCT + "filing-topics/north-carolina-child-deduction", NCT + "credit-children"])
guidance("us-nc", "ncdor/military-retirement", "Military Retirement", NCT + "filing-topics/military-retirement",
         fmt="html", selector="main#main-wrapper")
guidance("us-nc", "ncdor/north-carolina-standard-deduction-or-itemized-deductions",
         "North Carolina Standard Deduction or North Carolina Itemized Deductions",
         NCT + "filing-topics/north-carolina-standard-deduction-or-north-carolina-itemized-deductions", fmt="html",
         selector="main#main-wrapper",
         rows=[NCT + "filing-topics/north-carolina-standard-deduction-or-north-carolina-itemized-deductions",
               NCT + "north-carolina-standard-deduction-or-north-carolina-itemized-deductions"])
statute("us-nc", "105/105-153.10", "G.S. 105-153.10 (repealed by Session Laws 2015-241, s. 32.13(c))",
        "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_105/GS_105-153.10.html",
        authority="North Carolina General Assembly", fmt="html", selector="body")
statute("us-nc", "bills/2023/h259-bill-information", "House Bill 259 / S.L. 2023-134 (2023-2024 Session) bill information",
        "https://www.ncleg.gov/BillLookup/2023/H259", authority="North Carolina General Assembly", fmt="html",
        selector="main", sub="bill_information_page")

# --------------------------------------------------------------------------------------------
# North Dakota (tax.nd.gov): manifest-on-main rows (manifests/us-nd-individual-income-tax-forms.yaml)
NDF = "https://tax.nd.gov/sites/www/files/documents/forms/individual/"
ND_MANIFEST = "us-nd/form/individual_income_tax_forms/tax.nd.gov/sites/www/files/documents/forms/individual/"
for ty, file, ident, title in [
    (2021, "2021-iit/2021-individual-income-tax-booklet", "individual-income-tax-booklet", "2021 North Dakota Individual Income Tax Booklet"),
    (2021, "2021-iit/form-nd-1-2021", "form-nd-1", "2021 Form ND-1, Individual Income Tax Return"),
    (2021, "2021-iit/individual-income-tax-booklet-2021", "individual-income-tax-booklet-rev-2021-12-20", "2021 North Dakota Individual Income Tax Booklet (file of 2021-12-20)"),
    (2022, "2022-iit/2022-individual-income-tax-booklet", "individual-income-tax-booklet", "2022 North Dakota Individual Income Tax Booklet"),
    (2022, "2022-iit/form-nd-1-2022", "form-nd-1", "2022 Form ND-1, Individual Income Tax Return"),
    (2022, "2022-iit/schedule-nd-1sa-2022", "schedule-nd-1sa", "2022 Schedule ND-1SA, Statutory Adjustments"),
    (2023, "2023-iit/2023-individual-income-tax-booklet", "individual-income-tax-booklet", "2023 North Dakota Individual Income Tax Booklet"),
    (2023, "2023-iit/form-nd-1-2023", "form-nd-1", "2023 Form ND-1, Individual Income Tax Return"),
    (2023, "2023-iit/schedule-nd-1sa-2023", "schedule-nd-1sa", "2023 Schedule ND-1SA, Statutory Adjustments"),
    (2024, "2024-iit/2024-individual-income-tax-booklet", "individual-income-tax-booklet", "2024 North Dakota Individual Income Tax Booklet"),
    (2024, "2024-iit/28710-schedule-nd-1sa-2024", "schedule-nd-1sa", "2024 Schedule ND-1SA, Statutory Adjustments"),
    (2025, "2025-iit/28710-schedule-nd-1sa-2025", "schedule-nd-1sa", "2025 Schedule ND-1SA, Statutory Adjustments"),
]:
    note = None
    if ident.startswith("individual-income-tax-booklet-rev"):
        note = ("Second 2021 booklet file on the publisher's host (PDF modified 2021-12-20; "
                "2021-individual-income-tax-booklet.pdf is modified 2022-01-14); text differs.")
    form("us-nd", ty, ident, title, f"{NDF}{file}.pdf", rows=[ND_MANIFEST + file],
         sub="instructions" if "booklet" in ident else ("schedule" if "schedule" in ident else "return_form"), note=note)

# --------------------------------------------------------------------------------------------
# Nebraska (revenue.nebraska.gov, nebraskalegislature.gov)
NER = "https://revenue.nebraska.gov/"
for ty, url, extra, dl in [
    (2021, NER + "files/doc/tax-forms/2021/f_1040n_booklet.pdf", [NER + "sites/revenue.nebraska.gov/files/doc/f_1040n_booklet.pdf"],
     NER + "sites/default/files/doc/tax-forms/2021/f_1040n_booklet.pdf"),
    (2022, NER + "files/doc/2022_Ne_Individual_Income_Tax_Booklet_8-307-2022_final_5.pdf",
     [NER + "sites/revenue.nebraska.gov/files/doc/2022_Ne_Individual_Income_Tax_Booklet_8-307-2022_final_8.pdf"],
     NER + "sites/default/files/doc/2022_Ne_Individual_Income_Tax_Booklet_8-307-2022_final_5.pdf"),
    (2023, NER + "sites/revenue.nebraska.gov/files/doc/tax-forms/2023/incometax/f_1040n_booklet_2023_Final.pdf", [],
     NER + "sites/default/files/doc/tax-forms/2023/incometax/f_1040n_booklet_2023_Final.pdf"),
    (2024, NER + "sites/default/files/doc/tax-forms/2024/f_Individual_Income_Tax_Booklet.pdf", [], None),
]:
    form("us-ne", ty, "individual-income-tax-booklet", f"{ty} Nebraska Individual Income Tax Booklet", url,
         rows=[url, *extra], download_url=dl, sub="instructions")
for ty, url, dl in [
    (2021, NER + "files/doc/tax-forms/2021/f_2441n.pdf", NER + "sites/default/files/doc/tax-forms/2021/f_2441n.pdf"),
    (2022, NER + "sites/revenue.nebraska.gov/files/doc/Form_2441N_Ne_Child_and_Dependent_Care_Expenses_8-618-2022_final_2.pdf",
     NER + "sites/default/files/doc/Form_2441N_Ne_Child_and_Dependent_Care_Expenses_8-618-2022_final_2.pdf"),
    (2023, NER + "sites/revenue.nebraska.gov/files/doc/tax-forms/2023/incometax/f_2441N_2023_Final.pdf",
     NER + "sites/default/files/doc/tax-forms/2023/incometax/f_2441N_2023_Final.pdf"),
    (2024, NER + "sites/default/files/doc/tax-forms/2024/f_2441N.pdf", None),
    (2025, NER + "sites/default/files/doc/tax-forms/2025/f_2441N.pdf", None),
]:
    form("us-ne", ty, "form-2441n", f"{ty} Form 2441N, Nebraska Child and Dependent Care Expenses", url,
         download_url=dl, sub="schedule")
guidance("us-ne", "dor/tax-rate-chronology-table-1",
         "Nebraska Tax Rate Chronologies, Table 1: Income Tax and Sales Tax Rates",
         NER + "sites/default/files/doc/research/chronology/4-607table1_0.pdf", fmt="pdf", sub="research_table")
guidance("us-ne", "dor/2023-nebraska-legislative-changes", "2023 Nebraska Legislative Changes",
         NER + "about/2023-nebraska-legislative-changes", fmt="html", selector="main")
guidance("us-ne", "dor/child-care-tax-credit-act", "Child Care Tax Credit Act",
         NER + "businesses/child-care-tax-credit-act", download_url=NER + "tax-credits/child-care-tax-credit-act",
         fmt="html", selector="main")
for year, lb, legislature, url in [
    (2021, "lb432", "107", "https://nebraskalegislature.gov/FloorDocs/107/PDF/Slip/LB432.pdf"),
    (2023, "lb754", "108", "https://www.nebraskalegislature.gov/FloorDocs/108/PDF/Slip/LB754.pdf"),
]:
    statute("us-ne", f"session-laws/{year}/{lb}", f"Legislative Bill {lb[2:]} ({year}), slip law ({legislature}th Legislature)",
            url, authority="Nebraska Legislature", fmt="pdf", sub="session_law")

# --------------------------------------------------------------------------------------------
# New Hampshire (revenue.nh.gov; chrome120 fallback documented in the 2026-09-10 batch-2 note)
NHD = "https://www.revenue.nh.gov/sites/g/files/ehbemt736/files/documents/"
for ty, file, extra in [
    (2020, "dp-10-2020-print.pdf", []),
    (2021, "dp-10-2021-print.pdf", ["https://www.revenue.nh.gov/forms/2022/documents/dp-10-2021-print.pdf"]),
    (2022, "dp-10-2022-print.pdf", []),
    (2023, "dp-10-2023-form.pdf", []),
    (2024, "dp-10-2024.pdf", []),
]:
    form("us-nh", ty, "dp-10", f"{ty} Form DP-10, Interest and Dividends Tax Return", NHD + file,
         rows=[NHD + file, *extra], request=NH_REQUEST, sub="return_form")
for ty, extra in [(2022, ["https://www.revenue.nh.gov/forms/2023/documents/dp-10-instructions-2022.pdf"]), (2023, []), (2024, [])]:
    url = f"{NHD}dp-10-instructions-{ty}.pdf"
    form("us-nh", ty, "dp-10-instructions", f"{ty} Form DP-10 Interest and Dividends Tax Return, General Instructions",
         url, rows=[url, *extra], request=NH_REQUEST, sub="instructions")

# --------------------------------------------------------------------------------------------
# New Jersey (nj.gov/treasury/taxation, pub.njleg.gov)
NJT = "https://www.nj.gov/treasury/taxation/"
for ty, url, extra in [
    (2021, NJT + "pdf/other_forms/tgi-ee/2021/1040i.pdf", ["https://www.state.nj.us/treasury/taxation/pdf/other_forms/tgi-ee/2021/1040i.pdf"]),
    (2022, NJT + "pdf/other_forms/tgi-ee/2022/1040i.pdf", []),
    (2024, NJT + "pdf/other_forms/tgi-ee/2024/1040i.pdf", []),
]:
    form("us-nj", ty, "nj-1040-instructions", f"{ty} NJ-1040 Resident Return Instructions booklet", url, rows=[url, *extra],
         sub="instructions")
form("us-nj", 2025, "pas-1-instructions",
     "2025 Application for Property Tax Relief (PAS-1) instructions (ANCHOR, Senior Freeze, Stay NJ)",
     NJT + "pdf/25-pas1in.pdf", sub="instructions")
guidance("us-nj", "taxation/git-1-2-retirement-income", "GIT-1 & 2, Retirement Income (Understanding Income Tax)",
         NJT + "pdf/pubs/tgi-ee/git1&2.pdf", fmt="pdf", sub="publication")
for slug, title, path in [
    ("anchor-program", "ANCHOR Program", "anchor/"),
    ("anchor-how-benefits-are-calculated", "ANCHOR Program: How benefits are calculated", "anchor/calculated.shtml"),
    ("child-and-dependent-care-credit", "Child and Dependent Care Credit", "depcarecred.shtml"),
    ("property-tax-deduction-credit-for-homeowners-and-renters",
     "Property Tax Deduction/Credit for Homeowners and Renters", "njit35.shtml"),
    ("senior-freeze-property-tax-reimbursement", "Senior Freeze (Property Tax Reimbursement)", "ptr/index.shtml"),
    ("property-tax-relief-programs", "Property Tax Relief Programs", "relief.shtml"),
    ("stay-nj", "Stay NJ - Property Tax Relief for Senior Citizens", "staynj/index.shtml"),
]:
    guidance("us-nj", f"taxation/{slug}", title, NJT + path, fmt="html", selector="div.background-white")
NJL = "New Jersey Legislature"
statute("us-nj", "session-laws/2021/pl-2021-c130",
        "P.L.2021, c.130: modifying age requirements under the New Jersey earned income tax credit program",
        "https://pub.njleg.gov/bills/2020/PL21/130_.PDF", authority=NJL, fmt="pdf", sub="session_law")
statute("us-nj", "session-laws/2023/pl-2023-c75",
        "P.L.2023, c.75: property tax credit of up to one-half of property taxes for senior citizens (Stay NJ)",
        "https://pub.njleg.state.nj.us/Bills/2022/PL23/75_.PDF", authority=NJL, fmt="pdf", sub="session_law",
        rows=["https://pub.njleg.state.nj.us/Bills/2022/PL23/75_.PDF", "https://pub.njleg.state.nj.us/Bills/2022/PL23/75_.HTM"])
statute("us-nj", "session-laws/2024/pl-2024-c88", "P.L.2024, c.88: Stay NJ property tax benefit program",
        "https://pub.njleg.state.nj.us/Bills/2024/PL24/88_.PDF", authority=NJL, fmt="pdf", sub="session_law")
statute("us-nj", "session-laws/2026/pl-2026-c27", "P.L.2026, c.27 (Assembly No. 5327): FY2027 appropriations act",
        "https://pub.njleg.state.nj.us/Bills/2026/AL26/27_.PDF", authority=NJL, fmt="pdf", sub="session_law")
statute("us-nj", "bills/2026/s4531-introduced", "Senate Bill 4531 (2026-2027 session), as introduced",
        "https://pub.njleg.state.nj.us/Bills/2026/S5000/4531_I1.HTM", authority=NJL, fmt="html", selector="body",
        sub="bill_version")

# --------------------------------------------------------------------------------------------
# New Mexico (TRD RealFile host klvg4oyd4j.execute-api..., the department's own file service; hed.nm.gov; nmlegis.gov)
NMF = "https://klvg4oyd4j.execute-api.us-west-2.amazonaws.com/prod/PublicFiles/34821a9573ca43e7b06dfad20f5183fd/"
NM_INDEX = "https://www.tax.newmexico.gov/individuals/online-services-overview/personal-income-tax-forms/"
TAXSIM_NM = "https://taxsim.nber.org/historical_state_tax_forms/NM/"
for ty, fid, ident, title, extra in [
    (2025, "0558a902-6362-47ca-8e3b-7cca3bc69b9d/2025%20PIT%20Packet_Final.pdf", "pit-packet", "2025 Personal Income Tax Form Packet", []),
    (2022, "1afc56af-ea90-4d48-82e5-1f9aeb43255a/PITbook2022.pdf", "pit-packet", "2022 Personal Income Tax Form Packet", [TAXSIM_NM + "2022/PITbook2022.pdf"]),
    (2021, "608063af-0c4c-4f28-ba42-cf40e04557ca/PITbook2021.pdf", "pit-packet", "2021 Personal Income Tax Form Packet", []),
    (2023, "90560f4e-0ef0-4e52-a003-878b84f858bb/PITbook2023.pdf", "pit-packet", "2023 Personal Income Tax Form Packet", []),
    (2024, "97f27f33-5e23-4a25-ad68-0980a22b802d/PITbook2024.pdf", "pit-packet", "2024 Personal Income Tax Form Packet",
     [NMF + "90560f4e-0ef0-4e52-a003-878b84f858bb/PITbook2024.pdf"]),
    (2023, "247e3a1f-2a1f-4002-a689-e1c3994dde9d/2023pit-adj.pdf", "pit-adj", "2023 PIT-ADJ, Schedule of Additions, Deductions, and Exemptions", []),
    (2024, "d36fdefa-8c60-4b26-b368-ee712432a54d/2024pit-adj.pdf", "pit-adj", "2024 PIT-ADJ, Schedule of Additions, Deductions, and Exemptions", []),
    (2022, "41cdedb5-199d-4604-b2cb-68c168f36984/2022pit-adj.pdf", "pit-adj", "2022 PIT-ADJ, Schedule of Additions, Deductions, and Exemptions",
     ["https://www.taxformfinder.org/forms/2022/2022-new-mexico-form-pit-adj.pdf"]),
    (2022, "2f1a6781-9534-4436-b427-1557f9592099/2022pit-adj-ins.pdf", "pit-adj-instructions", "Instructions for 2022 PIT-ADJ", []),
    (2023, "cb0dc85c-5c28-45b1-a3f5-1e00fffaaf6b/2023pit-adj-ins.pdf", "pit-adj-instructions", "Instructions for 2023 PIT-ADJ", []),
    (2021, "b60e3775-495d-4b64-aabd-255818dbb420/2021pit-1-ins.pdf", "pit-1-instructions", "Instructions for 2021 PIT-1, New Mexico Personal Income Tax Return",
     [TAXSIM_NM + "2021/2021pit-1-ins.pdf"]),
    (2021, "5d7e5285-3975-4df4-952f-1f83c9e7b770/2021pit-rc.pdf", "pit-rc", "2021 PIT-RC, New Mexico Rebate and Credit Schedule",
     [TAXSIM_NM + "2021/2021pit-rc.pdf"]),
]:
    url = NMF + fid
    # The 2021 PIT-1 instructions, 2021 PIT-RC and 2022 PIT-ADJ addresses were found in the TRD RealFile
    # prior-years folders (GetWidgetFiles listing) for the third-party rows; they are not bundle addresses.
    found_for_third_party = (ty, ident) in {(2021, "pit-1-instructions"), (2021, "pit-rc"), (2022, "pit-adj")}
    rows = list(extra) if found_for_third_party else [url, *extra]
    note = None
    if ty == 2024 and ident == "pit-packet":
        note = ("The bundle also names .../90560f4e-.../PITbook2024.pdf; that file id serves the 2023 packet (same bytes as "
                "PITbook2023.pdf, printed '2023 Personal Income Tax Form Packet'), so it is joined to this 2024 packet.")
    form("us-nm", ty, ident, title, url, rows=rows, sub="instructions" if ("packet" in ident or "instructions" in ident) else "schedule",
         index_url=NM_INDEX, note=note)
guidance("us-nm", "trd/income-tax-act-regulations-publication-2023",
         "TRD Publication: 3.3 NMAC Regulations pertaining to the Income Tax Act, Sections 7-2-1 through 7-2-40 NMSA 1978 (revised July 2023)",
         NMF + "856ebf4b-3814-49dd-8631-ebe579d6a42b/Personal%20Income%20Tax.pdf", fmt="pdf", sub="publication",
         index_url=NM_INDEX)
guidance("us-nm", "hed/new-mexico-529-college-savings-plan", "New Mexico's 529 Education Savings Plan",
         "https://hed.nm.gov/financial-aid/new-mexico-529-college-savings-plan", fmt="html", selector="main",
         authority="New Mexico Higher Education Department")
statute("us-nm", "bills/2024/hb37", "House Bill 37 (2024 Regular Session)",
        "https://www.nmlegis.gov/Sessions/24%20Regular/bills/house/HB0037.HTML", authority="New Mexico Legislature",
        fmt="html", selector="body", sub="bill_version")

# --------------------------------------------------------------------------------------------
# New York (tax.ny.gov, nyassembly.gov)
NYP = "https://www.tax.ny.gov/pdf/"
NYC = NYP + "current_forms/it/"
add("us-ny", "form", "tax/ty2025/it-214",
    "Form IT-214, Claim for Real Property Tax Credit for Homeowners and Renters (2025)", NYC + "it214_fill_in.pdf",
    ty="2025", sub="form", rows=["us-ny/form/tax/ty2025/it-214"],
    note="Entry copied from manifests/us-ny-it-214-real-property-tax-credit-ty2025.yaml (manifest on main, never extracted).")
add("us-ny", "form", "tax/ty2025/it-214-i",
    "Instructions for Form IT-214, Claim for Real Property Tax Credit for Homeowners and Renters (2025) (IT-214-I)",
    NYC + "it214i.pdf", ty="2025", sub="instructions", rows=["us-ny/form/tax/ty2025/it-214-i"],
    note="Entry copied from manifests/us-ny-it-214-real-property-tax-credit-ty2025.yaml (manifest on main, never extracted).")
for ty, ident, title, url in [
    (2021, "it-196-i", "2021 Instructions for Form IT-196, New York Itemized Deductions", NYP + "2021/inc/it196i_2021.pdf"),
    (2021, "it-201-i", "2021 Instructions for Form IT-201, Full-Year Resident Income Tax Return", NYP + "2021/inc/it201i_2021.pdf"),
    (2021, "it-215-i", "2021 Instructions for Form IT-215, Claim for Earned Income Credit", NYP + "2021/inc/it215i_2021.pdf"),
    (2022, "it-196-i", "2022 Instructions for Form IT-196, New York Itemized Deductions", NYP + "2022/inc/it196i_2022.pdf"),
    (2022, "it-201-i", "2022 Instructions for Form IT-201, Full-Year Resident Income Tax Return", NYP + "2022/printable-pdfs/inc/it201i-2022.pdf"),
    (2024, "it-196-i", "2024 Instructions for Form IT-196, New York Itemized Deductions", NYP + "2024/inc/it196i_2024.pdf"),
    (2024, "it-201", "2024 Form IT-201, Resident Income Tax Return", NYP + "2024/inc/it201_2024_fill_in.pdf"),
    (2024, "it-201-i", "2024 Instructions for Form IT-201, Full-Year Resident Income Tax Return", NYP + "2024/inc/it201i_2024.pdf"),
    (2024, "it-214-i", "2024 Instructions for Form IT-214, Claim for Real Property Tax Credit", NYP + "2024/inc/it214i_2024.pdf"),
    (2024, "it-267-i", "2024 Instructions for Form IT-267, Geothermal Energy System Credit", NYP + "2024/inc/it267i_2024.pdf"),
    (2025, "it-196-i", "2025 Instructions for Form IT-196, New York Itemized Deductions", NYC + "it196i.pdf"),
    (2025, "it-213", "2025 Form IT-213, Claim for Empire State Child Credit", NYC + "it213_fill_in.pdf"),
    (2025, "it-213-i", "2025 Instructions for Form IT-213, Claim for Empire State Child Credit", NYC + "it213i.pdf"),
    (2025, "it-215", "2025 Form IT-215, Claim for Earned Income Credit", NYC + "it215_fill_in.pdf"),
    (2025, "it-216", "2025 Form IT-216, Claim for Child and Dependent Care Credit", NYC + "it216_fill_in.pdf"),
    (2025, "it-255", "2025 Form IT-255, Claim for Solar Energy System Equipment Credit", NYC + "it255_fill_in.pdf"),
    (2025, "it-272", "2025 Form IT-272, Claim for College Tuition Credit or Itemized Deduction", NYC + "it272_fill_in.pdf"),
]:
    form("us-ny", ty, ident, title, url, sub="instructions" if ident.endswith("-i") else "form")
NYH = "https://www.tax.ny.gov/forms/html-instructions/2023/it/"
form("us-ny", 2023, "it-201-i", "2023 Instructions for Form IT-201, Full-Year Resident Income Tax Return (HTML edition)",
     NYH + "it201i-2023.htm", fmt="html", selector="main", sub="instructions")
form("us-ny", 2023, "it-213-i", "2023 Instructions for Form IT-213, Claim for Empire State Child Credit (HTML edition)",
     NYH + "it213i-2023.htm", fmt="html", selector="main", sub="instructions")
form("us-ny", 2023, "it-196-i", "2023 Form IT-196-I, Instructions for Form IT-196 (HTML edition)", NYH + "it196i-2023.htm",
     fmt="html", selector="main", sub="instructions",
     rows=["https://www.tax.ny.gov/pdf/2023/printable-pdfs/inc/it196i-2023.pdf"],
     index_url="https://www.tax.ny.gov/forms/prvforms/income_tax_2023.htm",
     note="The bundle's printable PDF address is 404; the department's 2023 income tax forms index links this HTML edition.")
for ty in (2020, 2022, 2025):
    guidance("us-ny", f"tax/ty{ty}/pit-corp-changes", f"Summary of {ty} corporation tax and personal income tax changes",
             f"https://www.tax.ny.gov/legal/{ty}/pit-corp-changes.htm", fmt="html", selector="main", ty=str(ty),
             sub="legislative_summary")
guidance("us-ny", "tax/tsb-m-98-7-i", "TSB-M-98(7)I (Income Tax), December 24, 1998", NYP + "memos/income/m98_7i.pdf",
         fmt="pdf", sub="technical_memorandum")
for slug, title, path in [
    ("empire-state-child-credit", "Empire State child credit", "pit/credits/empire_state_child_credit.htm"),
    ("geothermal-energy-system-credit", "Geothermal Energy System Credit", "pit/credits/geothermal-energy-system-credit.htm"),
    ("solar-energy-system-equipment-credit", "Solar Energy System Equipment Credit", "pit/credits/solar_energy_system_equipment_credit.htm"),
    ("additional-empire-state-child-credit-payments", "Additional Empire State child credit payments", "pit/empire-child-credit-payments.htm"),
    ("itemized-deductions", "Itemized deductions", "pit/file/itemized-deductions.htm"),
    ("vita-and-tce", "Volunteer Income Tax Assistance (VITA) and Tax Counseling for the Elderly (TCE)", "pit/file/vita.htm"),
]:
    guidance("us-ny", f"tax/{slug}", title, "https://www.tax.ny.gov/" + path, fmt="html", selector="main")
statute("us-ny", "bills/2025/s3009", "Senate Bill S3009 (2025-2026 session) bill text, New York State Assembly",
        "https://assembly.state.ny.us/leg/?Text=Y&bn=S3009&default_fld=&leg_video=&term=2025",
        authority="New York State Assembly", fmt="html", selector="main", sub="bill_version",
        text_selector="pre", drop=["s"],
        note="Bill text is printed in <pre> blocks with <u>/<b> insertions and <s> deletions; struck (<s>) text is "
             "dropped so the body reads as amended. First run (2026-10-06-w6-income-tax-statute-ny) read only the "
             "page tabs (90 characters) and is superseded by the -r2 version.")

# --------------------------------------------------------------------------------------------
# Ohio (tax.ohio.gov / dam.assets.ohio.gov, search-prod.lis.state.oh.us); manifest-on-main rows
OHD = "https://dam.assets.ohio.gov/image/upload/tax.ohio.gov/forms/ohio_individual/individual/"
OHS = "https://tax.ohio.gov/static/forms/ohio_individual/individual/"
OH_MANIFEST = "us-oh/form/individual_income_tax_forms/"
for ty, ident, title, url, rows, req in [
    (2022, "it-1040-sd-100-instructions", "2022 Ohio IT 1040 / SD 100 Instructions", OHD + "2022/it1040-sd100-instruction-booklet.pdf",
     [OH_MANIFEST + "dam.assets.ohio.gov/image/upload/tax.ohio.gov/forms/ohio_individual/individual/2022/it1040-sd100-instruction-booklet",
      OH_MANIFEST + "tax.ohio.gov/static/forms/ohio_individual/individual/2022/it1040-sd100-instruction-booklet"], None),
    (2023, "form-it-1040", "2023 Ohio IT 1040, Individual Income Tax Return", OHD + "2023/1040-bundle-original.pdf",
     [OH_MANIFEST + "dam.assets.ohio.gov/image/upload/tax.ohio.gov/forms/ohio_individual/individual/2023/1040-bundle-original"], None),
    (2023, "it-1040-sd-100-instructions", "Tax Year 2023 Ohio IT 1040 / SD 100 Instructions", OHD + "2023/it1040-sd100-instructionbooklet.pdf",
     [OH_MANIFEST + "dam.assets.ohio.gov/image/upload/tax.ohio.gov/forms/ohio_individual/individual/2023/it1040-sd100-instructionboo"], None),
    (2024, "it-1040-sd-100-instructions", "Tax Year 2024 Ohio IT 1040 / SD 100 Instructions",
     "https://dam.assets.ohio.gov/image/upload/v1735920104/tax.ohio.gov/forms/ohio_individual/individual/2024/it1040-booklet.pdf",
     [OH_MANIFEST + "dam.assets.ohio.gov/image/upload/v1735920104/tax.ohio.gov/forms/ohio_individual/individual/2024/it1040-booklet"], None),
    (2021, "it-1040-sd-100-instructions", "2021 Ohio IT 1040 / SD 100 Instructions", OHS + "2021/pit-it1040-booklet.pdf",
     [OH_MANIFEST + "tax.ohio.gov/static/forms/ohio_individual/individual/2021/pit-it1040-booklet"], OH_REQUEST),
    (2021, "schedule-of-credits", "2021 Ohio Schedule of Credits", OHS + "2021/sch-cre.pdf",
     [OH_MANIFEST + "tax.ohio.gov/static/forms/ohio_individual/individual/2021/sch-cre"], OH_REQUEST),
    (2022, "form-it-1040", "2022 Ohio IT 1040, Individual Income Tax Return", OHS + "2022/it1040-bundle.pdf",
     [OH_MANIFEST + "tax.ohio.gov/static/forms/ohio_individual/individual/2022/it1040-bundle"], OH_REQUEST),
    (2022, "schedule-of-credits", "2022 Ohio Schedule of Credits", OHS + "2022/itschedule-credits.pdf",
     [OH_MANIFEST + "tax.ohio.gov/static/forms/ohio_individual/individual/2022/itschedule-credits"], OH_REQUEST),
    (2024, "form-it-1040", "2024 Ohio IT 1040, Individual Income Tax Return (fillable bundle)", OHS + "2024/1040-bundle-original-fi.pdf",
     [OH_MANIFEST + "tax.ohio.gov/static/webview/view1/uiextension/1/pdf-view/41fe23480d"], OH_REQUEST),
]:
    form("us-oh", ty, ident, title, url, rows=rows, request=req, sub="instructions" if "instructions" in ident else "return_form")
guidance("us-oh", "odt/individual-income-tax-ohio-publication", "Individual Income Tax - Ohio (department publication)",
         "https://tax.ohio.gov/static/communications/publications/individual_income_tax_ohio.pdf",
         download_url="https://dam.assets.ohio.gov/image/upload/tax.ohio.gov/communications/publications/individual_income_tax_ohio.pdf",
         fmt="pdf", sub="publication", request=OH_REQUEST)
guidance("us-oh", "odt/faq-income-individual-credits",
         "Income - Individual Credits (Education, Displaced Workers and Adoption) FAQs",
         "https://tax.ohio.gov/wps/portal/gov/tax/help-center/faqs/income+-+individual+credits/income-individual-credits",
         download_url="https://tax.ohio.gov/help-center/faqs/income+-+individual+credits/income-individual-credits",
         fmt="html", selector="main#odx-main-content", sub="faq", request=OH_REQUEST)
OHL = "https://search-prod.lis.state.oh.us/api/v2/"
statute("us-oh", "session-laws/134th-ga/hb45", "Am. Sub. H.B. 45, 134th General Assembly (as enacted)",
        OHL + "general_assembly_134/legislation/hb45/07_EN/pdf/", authority="Ohio General Assembly", fmt="pdf",
        sub="session_law")
statute("us-oh", "session-laws/136th-ga/hb96", "Am. Sub. H.B. 96, 136th General Assembly (as enacted; FY2026-2027 operating budget)",
        OHL + "general_assembly_136/legislation/hb96/07_EN/pdf/", authority="Ohio General Assembly", fmt="pdf",
        sub="session_law")


# --------------------------------------------------------------------------------------------
FAMILY = {"form": "forms", "guidance": "guidance", "statute": "statute"}


# Scopes re-run under a new version after review of the first run (the first-run versions stay on disk,
# are superseded and must not be selected): us-ny/statute (S3009 bill text in <pre> blocks was not read)
# and us-nj/guidance (njit35.shtml carried the site's generic <title>; slug corrected).
REVISION = {("us-ny", "statute"): "r2", ("us-nj", "guidance"): "r2"}


def version_for(jur: str, cls: str) -> str:
    base = f"2026-10-06-{RUN}-income-tax-{FAMILY[cls]}-{jur.split('-')[1]}"
    rev = REVISION.get((jur, cls))
    return f"{base}-{rev}" if rev else base


def manifest_path(jur: str, cls: str) -> Path:
    return REPO / "manifests" / f"{jur}-income-tax-{RUN}-{FAMILY[cls]}.yaml"


def manifest_entry(doc: dict) -> dict:
    jur = doc["jurisdiction"]
    tail = doc["citation_path"].split("/", 2)[2].replace("/", "-").replace(".", "-")
    entry = {
        "source_id": f"{jur}-{doc['document_class']}-{tail}".lower()[:120],
        "jurisdiction": jur,
        "document_class": doc["document_class"],
        "title": doc["title"],
        "source_url": doc["source_url"],
    }
    if doc["download_url"]:
        entry["download_url"] = doc["download_url"]
    entry.update(
        {
            "source_format": doc["source_format"],
            "source_as_of": SOURCE_AS_OF,
            "expression_date": doc["expression_date"],
            "citation_path": doc["citation_path"],
            "extraction": doc["extraction"],
        }
    )
    if doc["request"]:
        entry["request"] = doc["request"]
    metadata = {
        "primary_source": True,
        "source_authority": doc["source_authority"],
        "document_subtype": doc["document_subtype"],
        "program": "individual_income_tax",
        "source_family": "w6-tax-mn-oh-2026-10-06",
        "discovered_via": f"{WORK_ORDER} (bundle rows: {len(doc['rows'])}); fetched and read 2026-10-06",
        "bundle_rows": doc["rows"],
    }
    if doc["tax_year"]:
        metadata["tax_year"] = doc["tax_year"]
    if doc["index_url"]:
        metadata["index_url"] = doc["index_url"]
    if doc["note"]:
        metadata["source_note"] = doc["note"]
    entry["metadata"] = metadata
    return entry


def build() -> dict[Path, dict]:
    paths = [d["citation_path"] for d in DOCS]
    dupes = {p for p in paths if paths.count(p) > 1}
    if dupes:
        raise SystemExit(f"duplicate citation paths: {sorted(dupes)}")
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for doc in DOCS:
        grouped[(doc["jurisdiction"], doc["document_class"])].append(doc)
    out = {}
    for (jur, cls), docs in sorted(grouped.items()):
        out[manifest_path(jur, cls)] = {
            "version": version_for(jur, cls),
            "documents": [manifest_entry(d) for d in docs],
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print documents as JSON lines")
    args = parser.parse_args()
    if args.list:
        for doc in DOCS:
            print(json.dumps({k: doc[k] for k in ("citation_path", "source_url", "rows")}))
        return
    for path, payload in build().items():
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120))
        print(f"{path.relative_to(REPO)}: {len(payload['documents'])} documents, version {payload['version']}")


if __name__ == "__main__":
    main()
