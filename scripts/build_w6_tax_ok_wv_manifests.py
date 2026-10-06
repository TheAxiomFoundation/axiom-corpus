#!/usr/bin/env python3
"""Wave 6, group tax-ok-wv: manifests and decisions for the program-bundle gaps.

Work order: ``docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-ok-wv.csv`` (394 rows,
state individual income tax, EITC and CTC documents, Oklahoma to West Virginia) on the
``bundle-gaps`` branch. Every document below was fetched from its official publisher on
2026-10-06 with the corpus user agent and read (printed title, tax year, page count);
the facts are recorded in each entry. Run note: ``docs/ingest-runs/2026-10-06-w6-tax-ok-wv.md``.

Usage::

    uv run python scripts/build_w6_tax_ok_wv_manifests.py            # write manifests
    uv run python scripts/build_w6_tax_ok_wv_manifests.py --decisions WORK_ORDER.csv

``--decisions`` writes ``docs/ingest-runs/2026-10-06-w6-tax-ok-wv-decisions.csv`` with one
row per work-order row (PRESENT rows come from the document tables; the other statuses
from ``DECISIONS``). ``--scope-report`` adds row counts from the extracted coverage files.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-10-06"
VERSION_PREFIX = "2026-10-06-w6-income-tax"
FAMILY = {
    "form": "forms",
    "guidance": "guidance",
    "statute": "statute",
    "regulation": "regulation",
    "rulemaking": "rulemaking",
}
AUTHORITY = {
    "us-ok": "Oklahoma Tax Commission",
    "us-or": "Oregon Department of Revenue",
    "us-pa": "Pennsylvania Department of Revenue",
    "us-ri": "Rhode Island Division of Taxation",
    "us-sc": "South Carolina Department of Revenue",
    "us-ut": "Utah State Tax Commission",
    "us-va": "Virginia Department of Taxation",
    "us-vt": "Vermont Department of Taxes",
    "us-wa": "Washington State Department of Revenue",
    "us-wi": "Wisconsin Department of Revenue",
    "us-wv": "West Virginia Tax Division",
}
SINGLE_BLOCK = {"segmentation": "single_block"}
# Leaf-block text nodes for pages that print their text in div/span containers (SharePoint).
LEAF_MAIN = "main *:not(:has(div, p, li, table, h1, h2, h3, h4))"

# Content roots of the HTML publishers (read from the 2026-10-06 pages).
HTML_SELECTOR = {
    "www.oregon.gov": "main",
    "www.oregonlegislature.gov": "[role=main]",
    "www.pa.gov": "main",
    "www.revenue.pa.gov": "main",
    "www.pa529.com": "main",
    "www.oklahoma529.com": "main",
    "incometax.utah.gov": "article",
    "tax.utah.gov": "article",
    "my529.org": "main",
    "www.tax.virginia.gov": "main",
    "budget.lis.virginia.gov": "#content",
    "tax.vermont.gov": "main",
    "legislature.vermont.gov": "#main-content",
    "dor.wa.gov": "main",
    "workingfamiliescredit.wa.gov": "[role=main]",
    "app.leg.wa.gov": "#contentWrapper",
    "apps.leg.wa.gov": "#contentWrapper",
    "lawfilesext.leg.wa.gov": "body",
    "www.revenue.wi.gov": "main",
    "dfi.wi.gov": "main",
    "www.edvest.com": "main",
    "docs.legis.wisconsin.gov": "body",
    "webserver.rilegislature.gov": "body",
    "www.rilegislature.gov": "body",
    "governor.ri.gov": "main",
    "www.scstatehouse.gov": "body",
    "treasurer.sc.gov": ".main-content",
    "www.smart529.com": "body",
}


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/")[0].lower()


# ---------------------------------------------------------------------------
# Document tables. Each entry: source_url, citation_path, title, tax year (or None),
# subtype, pages (PDF) and the work-order ids the document closes (default: the URL).
# ---------------------------------------------------------------------------

D: list[dict[str, Any]] = []


def doc(
    url: str,
    path: str,
    title: str,
    year: str | None = None,
    subtype: str = "form",
    pages: int | None = None,
    closes: list[str] | None = None,
    fmt: str | None = None,
    selector: str | None = None,
    authority: str | None = None,
    note: str | None = None,
    text_selector: str | None = None,
    download: str | None = None,
) -> None:
    jur, cls = path.split("/")[:2]
    fmt = fmt or ("pdf" if pages is not None else "html")
    D.append(
        {
            "url": url,
            "path": path,
            "title": title,
            "year": year,
            "subtype": subtype,
            "pages": pages,
            "closes": closes if closes is not None else [url],
            "fmt": fmt,
            "selector": selector,
            "text_selector": text_selector,
            "download": download,
            "jur": jur,
            "cls": cls,
            "authority": authority or AUTHORITY.get(jur),
            "note": note,
        }
    )


OK = "https://oklahoma.gov/content/dam/ok/en/tax/documents/forms/individuals"
# --- Oklahoma ---------------------------------------------------------------
doc(f"{OK}/current/511-EIC.pdf", "us-ok/form/otc/ty2025/form-511-eic", "2025 Form 511-EIC, Oklahoma Earned Income Credit Worksheet", "2025", "worksheet", 10)
doc(f"{OK}/current/511-NR-Pkt.pdf", "us-ok/form/otc/ty2025/form-511-nr-packet", "2025 Form 511-NR, Oklahoma Nonresident/Part-Year Individual Income Tax Forms and Instructions", "2025", "forms_and_instructions_packet", 52)
doc(f"{OK}/current/538-H.pdf", "us-ok/form/otc/ty2025/form-538-h", "2025 Form 538-H, Oklahoma Claim for Credit or Refund of Property Tax (due June 30, 2026)", "2025", "claim_form", 3)
doc(f"{OK}/current/538-S.pdf", "us-ok/form/otc/ty2025/form-538-s", "2025 Form 538-S, Oklahoma Claim for Credit/Refund of Sales Tax", "2025", "claim_form", 3)
doc(f"{OK}/past-year/2021/511-Pkt-2021.pdf", "us-ok/form/otc/ty2021/form-511-packet", "2021 Form 511, Oklahoma Resident Individual Income Tax Forms and Instructions", "2021", "forms_and_instructions_packet", 51)
doc(f"{OK}/past-year/2021/538-H-2021.pdf", "us-ok/form/otc/ty2021/form-538-h", "2021 Form 538-H, Oklahoma Claim for Credit or Refund of Property Tax (due June 30, 2022)", "2021", "claim_form", 2)
doc(f"{OK}/past-year/2022/511-Pkt-2022.pdf", "us-ok/form/otc/ty2022/form-511-packet", "2022 Form 511, Oklahoma Resident Individual Income Tax Forms and Instructions", "2022", "forms_and_instructions_packet", 53)
doc(f"{OK}/past-year/2022/538-H-2022.pdf", "us-ok/form/otc/ty2022/form-538-h", "2022 Form 538-H, Oklahoma Claim for Credit or Refund of Property Tax (due June 30, 2023)", "2022", "claim_form", 3)
doc(f"{OK}/past-year/2023/511-EIC.pdf", "us-ok/form/otc/ty2023/form-511-eic", "2023 Form 511-EIC, Oklahoma Earned Income Credit Worksheet", "2023", "worksheet", 11)
doc(f"{OK}/past-year/2023/511-Pkt.pdf", "us-ok/form/otc/ty2023/form-511-packet", "2023 Form 511, Oklahoma Resident Individual Income Tax Forms and Instructions", "2023", "forms_and_instructions_packet", 52)
doc(f"{OK}/past-year/2023/538-H.pdf", "us-ok/form/otc/ty2023/form-538-h", "2023 Form 538-H, Oklahoma Claim for Credit or Refund of Property Tax (due June 30, 2024)", "2023", "claim_form", 3)
doc(f"{OK}/past-year/2024/511-EIC-2024.pdf", "us-ok/form/otc/ty2024/form-511-eic", "2024 Form 511-EIC, Oklahoma Earned Income Credit Worksheet", "2024", "worksheet", 10)
doc(f"{OK}/past-year/2024/511-Pkt-2024.pdf", "us-ok/form/otc/ty2024/form-511-packet", "2024 Form 511, Oklahoma Resident Individual Income Tax Forms and Instructions", "2024", "forms_and_instructions_packet", 52)
doc(f"{OK}/past-year/2024/538-H-2024.pdf", "us-ok/form/otc/ty2024/form-538-h", "2024 Form 538-H, Oklahoma Claim for Credit or Refund of Property Tax (due June 30, 2025)", "2024", "claim_form", 3)
doc("https://www.oklegislature.gov/cf_pdf/2021-22%20ENR/hB/HB2962%20ENR.PDF", "us-ok/statute/bills/2021-2022/hb2962-enrolled", "Enrolled House Bill No. 2962 (Oklahoma Legislature, 2021-22 session)", None, "enrolled_bill", 10, authority="Oklahoma Legislature")
doc("https://www.oklegislature.gov/cf_pdf/2025-26%20ENR/hB/HB2764%20ENR.PDF", "us-ok/statute/bills/2025-2026/hb2764-enrolled", "Enrolled House Bill No. 2764 (Oklahoma Legislature, 2025-26 session)", None, "enrolled_bill", 16, authority="Oklahoma Legislature")
doc("https://www.oklahoma529.com/resources/faq/", "us-ok/guidance/oklahoma-529/faq", "Oklahoma 529 College Savings Plan: Frequently Asked Questions (tax benefits)", None, "program_faq", authority="Oklahoma College Savings Plan (Oklahoma State Treasurer)")

# --- Oregon -----------------------------------------------------------------
doc("https://www.oregon.gov/dor/forms/FormsPubs/publication-or-40-fy_101-043_2019.pdf", "us-or/form/dor/ty2019/publication-or-40-fy", "2019 Oregon Income Tax Publication OR-40-FY (full-year residents; updated April 28, 2020)", "2019", "instructions", 56)
doc("https://www.oregon.gov/dor/programs/individuals/Documents/Part-year%20and%20nonresident,%20Form%20OR-40-P%20and%20OR-40-N%20filers.pdf.pdf", "us-or/form/dor/ty2022/or-40-p-or-40-n-tax-rate-charts", "2022 Tax rate charts for part-year and nonresident filers (Forms OR-40-P and OR-40-N)", "2022", "tax_rate_schedule", 1)
doc("https://www.oregon.gov/dor/forms/FormsPubs/schedule-or-wfhdc_101-195_2021.pdf", "us-or/form/dor/ty2021/schedule-or-wfhdc", "2021 Schedule OR-WFHDC, Oregon Working Family Household and Dependent Care Credit", "2021", "schedule", 5, closes=["https://taxsim.nber.org/historical_state_tax_forms/OR/2021/schedule-or-wfhdc_101-195_2021.pdf"])
doc("https://www.oregon.gov/dor/forms/FormsPubs/schedule-or-wfhdc-inst_101-195-1_2024.pdf", "us-or/form/dor/ty2024/schedule-or-wfhdc-instructions", "Schedule OR-WFHDC Instructions 2024, Oregon Working Family Household and Dependent Care Credit", "2024", "instructions", 8, closes=["https://www.google.com/url?sa=i&url=https%3A%2F%2Fsecure.dor.state.or.us%2FServices%2Fdraftforms%2Fapi%2Fdocument%2F6793%2Fdownload&psig=AOvVaw01yzy9QiRloWlbInbZcNG4&ust=1742309265624000&source=images&cd=vfe&opi=89978449&ved=0CAYQrpoMahcKEwjI16b4rZGMAxUAAAAAHQAAAAAQBA"])
doc("https://www.oregon.gov/dor/programs/individuals/pages/credits.aspx", "us-or/guidance/dor/tax-benefits-for-families", "Oregon Department of Revenue: Tax benefits for families", None, "web_page")
doc("https://www.oregon.gov/dor/programs/individuals/pages/kicker.aspx", "us-or/guidance/dor/oregon-surplus-kicker", "Oregon Department of Revenue: Oregon Surplus (\"Kicker\")", None, "web_page", text_selector=LEAF_MAIN)
doc("https://www.oregonlegislature.gov/bills_laws/Pages/OrConst.aspx", "us-or/statute/constitution", "Oregon Constitution (Oregon State Legislature edition)", None, "constitution", authority="Oregon State Legislature")
doc("https://olis.oregonlegislature.gov/liz/2023R1/Downloads/MeasureDocument/HB3235/Enrolled", "us-or/statute/bills/2023/hb3235-enrolled", "Enrolled House Bill 3235 (82nd Oregon Legislative Assembly, 2023 Regular Session)", "2023", "enrolled_bill", 9, authority="Oregon Legislative Assembly")

# --- Pennsylvania -----------------------------------------------------------
PA = "https://www.pa.gov/content/dam/copapwp-pagov/en/revenue/documents/formsandpublications"
doc(f"{PA}/formsforindividuals/pit/documents/2021/2021_pa-40in.pdf", "us-pa/form/department-of-revenue/ty2021/pa-40-instructions", "2021 PA-40 IN, Pennsylvania Personal Income Tax Return Instructions Booklet", "2021", "instructions", 48)
doc(f"{PA}/formsforindividuals/pit/documents/2021/2021_pa-40sp.pdf", "us-pa/form/department-of-revenue/ty2021/pa-40-schedule-sp", "2021 PA Schedule SP, Special Tax Forgiveness (PA-40 SP)", "2021", "schedule", 8)
for _y in ("2022", "2023", "2024", "2025"):
    doc(f"{PA}/formsforindividuals/pit/documents/{_y}/{_y}_pa-40dc.pdf", f"us-pa/form/department-of-revenue/ty{_y}/pa-40-schedule-dc", f"{_y} PA Schedule DC, Child and Dependent Care Enhancement Tax Credit", _y, "schedule", {"2022": 3}.get(_y, 4))
for _y, _p in (("2023", 48), ("2024", 48), ("2025", 48)):
    doc(f"{PA}/formsforindividuals/pit/documents/{_y}/{_y}_pa-40in.pdf", f"us-pa/form/department-of-revenue/ty{_y}/pa-40-instructions", f"{_y} PA-40 IN, Pennsylvania Personal Income Tax Return Instructions Booklet", _y, "instructions", _p)
doc(f"{PA}/papersonalincometaxguide/documents/pitguide_grosscompensation.pdf", "us-pa/guidance/department-of-revenue/pit-guide/gross-compensation", "PA Personal Income Tax Guide: Gross Compensation (PDF edition)", None, "tax_guide", 74)
doc(f"{PA}/papersonalincometaxguide/documents/pitguide_taxforgiveness.pdf", "us-pa/guidance/department-of-revenue/pit-guide/tax-forgiveness", "PA Personal Income Tax Guide: Tax Forgiveness", None, "tax_guide", 9)
doc("https://www.pa.gov/agencies/revenue/forms-and-publications/pa-personal-income-tax-guide/gross-compensation.html", "us-pa/guidance/department-of-revenue/pit-guide-web/gross-compensation", "PA Personal Income Tax Guide: Gross Compensation (web edition)", None, "tax_guide")
doc("https://www.revenue.pa.gov/TaxTypes/PIT/Child%20and%20Dependent%20Care%20Enhancement%20Tax%20Credit/Pages/default.aspx", "us-pa/guidance/department-of-revenue/child-and-dependent-care-credit", "Pennsylvania Department of Revenue: Child and Dependent Care Enhancement Tax Credit", None, "web_page")
doc("https://www.legis.state.pa.us/CFDOCS/Legis/PN/Public/btCheck.cfm?txtType=PDF&sessYr=2003&sessInd=0&billBody=H&billTyp=B&billNbr=0200&pn=3160", "us-pa/statute/bills/2003-2004/hb200-pn3160", "House Bill 200, Printer's No. 3160 (Pennsylvania General Assembly, 2003-2004 session; Senate amended)", None, "bill_text", 94, authority="Pennsylvania General Assembly")
doc("https://www.palegis.us/legislation/bills/text/PDF/2025/0/HB0416/PN2576", "us-pa/statute/bills/2025-2026/hb416-pn2576", "House Bill 416, Printer's No. 2576 (Pennsylvania General Assembly, 2025-2026 session; Senate amended)", None, "bill_text", 141, authority="Pennsylvania General Assembly")
doc("https://www.pa529.com/faqs/", "us-pa/guidance/pa-treasury/pa-529-faqs", "PA 529 College and Career Savings Program: Frequently Asked Questions", None, "program_faq", authority="Pennsylvania Treasury (PA 529 College and Career Savings Program)")

# --- Rhode Island -----------------------------------------------------------
RI = "https://tax.ri.gov/sites/g/files/xkgbur541/files"
for _u, _p, _t, _y, _s, _n in (
    ("2021-11/2021-tax-rate-and-worksheets.pdf", "ty2021/tax-rate-schedule-and-worksheets", "Rhode Island Tax Rate Schedule and Worksheets 2021", "2021", "tax_rate_schedule", 1),
    ("2021-12/2021-1040r-instructions.pdf", "ty2021/ri-1040-instructions", "2021 Instructions for Filing RI-1040", "2021", "instructions", 10),
    ("2022-01/2021-ri-1040h_w.pdf", "ty2021/ri-1040h", "2021 Form RI-1040H, Rhode Island Property Tax Relief Claim", "2021", "claim_form", 3),
    ("2022-01/2021-ri-schedule-m_w.pdf", "ty2021/schedule-m", "2021 RI Schedule M, RI Modifications to Federal AGI", "2021", "schedule", 2),
    ("2022-01/2021-ri-tax-tables_web.pdf", "ty2021/tax-tables", "Rhode Island Tax Rate Schedule and Tax Tables 2021", "2021", "tax_table", 7),
    ("2022-01/2021_1040we_w.pdf", "ty2021/ri-1040", "2021 Form RI-1040, Resident Individual Income Tax Return", "2021", "return_form", 5),
    ("2022-01/social-security-worksheet_b_0.pdf", "ty2021/taxable-social-security-income-worksheet", "2021 Modification Worksheet: Taxable Social Security Income Worksheet", "2021", "worksheet", 1),
    ("2022-10/2022%20RI%20Tax%20Tables_Complete.pdf", "ty2022/tax-tables", "Rhode Island Tax Rate Schedule and Tax Tables 2022", "2022", "tax_table", 7),
    ("2022-12/2022%201041%20Schedule%20M_w.pdf", "ty2022/ri-1041-schedule-m", "2022 RI Schedule M for RI-1041, RI Modifications to Federal Total Income", "2022", "schedule", 2),
    ("2022-12/2022%20NR%20Instructions_v4_w.pdf", "ty2022/ri-1040nr-instructions", "2022 Instructions for Filing RI-1040NR (nonresidents and part-year residents)", "2022", "instructions", 13),
    ("2022-12/2022%20RI%20Schedule%20M_w.pdf", "ty2022/schedule-m", "2022 RI Schedule M, RI Modifications to Federal AGI", "2022", "schedule", 2),
    ("2022-12/2022%20RI-1040H_v2_w.pdf", "ty2022/ri-1040h", "2022 Form RI-1040H, Rhode Island Property Tax Relief Claim", "2022", "claim_form", 3),
    ("2022-12/2022%20Tax%20Rate%20and%20Worksheets.pdf", "ty2022/tax-rate-schedule-and-worksheets", "Rhode Island Tax Rate Schedule and Worksheets 2022", "2022", "tax_rate_schedule", 1),
    ("2022-12/2022_1040WE_w_0.pdf", "ty2022/ri-1040", "2022 Form RI-1040, Resident Individual Income Tax Return", "2022", "return_form", 5),
    ("2022-12/Social%20Security%20Worksheet_w.pdf", "ty2022/taxable-social-security-income-worksheet", "2022 Modification Worksheet: Taxable Social Security Income Worksheet", "2022", "worksheet", 1),
    ("2023-11/2023%20Tax%20Rate%20and%20Worksheets_d.pdf", "ty2023/tax-rate-schedule-and-worksheets-2023-11", "Rhode Island Tax Rate Schedule and Worksheets 2023 (posted November 2023)", "2023", "tax_rate_schedule", 1),
    ("2023-12/2023%201040H_w.pdf", "ty2023/ri-1040h", "2023 Form RI-1040H, Rhode Island Property Tax Relief Claim", "2023", "claim_form", 3),
    ("2023-12/2023%201040R%20Instructions.pdf", "ty2023/ri-1040-instructions", "2023 Instructions for Filing RI-1040", "2023", "instructions", 11),
    ("2023-12/2023%20Tax%20Rate%20and%20Worksheets.pdf", "ty2023/tax-rate-schedule-and-worksheets", "Rhode Island Tax Rate Schedule and Worksheets 2023 (posted December 2023)", "2023", "tax_rate_schedule", 1),
    ("2023-12/Social%20Security%20Worksheet_w.pdf", "ty2023/taxable-social-security-income-worksheet", "2023 Modification Worksheet: Taxable Social Security Income Worksheet", "2023", "worksheet", 1),
    ("2024-09/Social%20Security%20Worksheet_bd.pdf", "ty2024/taxable-social-security-income-worksheet", "2024 Modification Worksheet: Taxable Social Security Income Worksheet", "2024", "worksheet", 1),
    ("2024-12/2024%201040H_w.pdf", "ty2024/ri-1040h", "2024 Form RI-1040H, Rhode Island Property Tax Relief Claim", "2024", "claim_form", 3),
    ("2024-12/2024%201040R%20Instructions%20-%20updated%2012092024.pdf", "ty2024/ri-1040-instructions", "2024 Instructions for Filing RI-1040 (updated 12/09/2024)", "2024", "instructions", 11),
    ("2024-12/2024%20Tax%20Rate%20and%20Worksheets.pdf", "ty2024/tax-rate-schedule-and-worksheets", "Rhode Island Tax Rate Schedule and Worksheets 2024", "2024", "tax_rate_schedule", 1),
    ("2024-12/2024_1040WE_w.pdf", "ty2024/ri-1040", "2024 Form RI-1040, Resident Individual Income Tax Return", "2024", "return_form", 5),
    ("2025-10/2025%20Tax%20Rate%20and%20Worksheets_d.pdf", "ty2025/tax-rate-schedule-and-worksheets-2025-10", "Rhode Island Tax Rate Schedule and Worksheets 2025 (posted October 2025)", "2025", "tax_rate_schedule", 1),
    ("2026-01/2025%201040H_w.pdf", "ty2025/ri-1040h", "2025 Form RI-1040H, Rhode Island Property Tax Relief Claim", "2025", "claim_form", 3),
    ("2026-01/2025%20RI%20Schedule%20M_w.pdf", "ty2025/schedule-m", "2025 RI Schedule M, RI Modifications to Federal AGI", "2025", "schedule", 2),
    ("2026-01/Social%20Security%20Worksheet_b.pdf", "ty2025/taxable-social-security-income-worksheet", "2025 Modification Worksheet: Taxable Social Security Income Worksheet", "2025", "worksheet", 1),
    ("forms/2014/Income/2014-1040_h.pdf", "ty2014/ri-1040", "2014 Form RI-1040, Resident Individual Income Tax Return", "2014", "return_form", 2),
    ("forms/2015/Income/2015-1040_hhh.pdf", "ty2015/ri-1040", "2015 Form RI-1040, Resident Individual Income Tax Return", "2015", "return_form", 2),
    ("forms/2020/Income/2020-RI-1040H_w.pdf", "ty2020/ri-1040h", "2020 Form RI-1040H, Rhode Island Property Tax Relief Claim", "2020", "claim_form", 3),
):
    _closes = [f"{RI}/{_u}"]
    if _p == "ty2025/ri-1040h":
        _closes.append("https://www.taxformfinder.org/rhodeisland/form-1040h")
    doc(f"{RI}/{_u}", f"us-ri/form/tax/{_p}", _t, _y, _s, _n, closes=_closes)
doc(f"{RI}/2022-12/ADV_2022_40_Inflation_Adjustments.pdf", "us-ri/guidance/tax/adv-2022-40", "ADV 2022-40, Advisory for Taxpayers and Tax Professionals: inflation-adjusted amounts set for tax year 2023 (December 27, 2022)", "2023", "advisory", 4)
doc(f"{RI}/2023-02/RI-MA%20NATP%20Jan%205%202023-CA.pdf", "us-ri/guidance/tax/natp-presentation-2023-01-05", "Rhode Island Division of Taxation presentation to the RI/MA Chapter of NATP (January 5, 2023)", None, "presentation", 34)
doc(f"{RI}/notice/Pub_2021_02_pension_income_guide_04_06_21.pdf", "us-ri/guidance/tax/pub-2021-02-pension-income-guide", "Publication 2021-02, Rhode Island Personal Income Tax Guide: Modification for Income from Pensions, 401(k) Plans, Annuities and Similar Sources", None, "tax_guide", 26)
doc("https://tax.ri.gov/media/18021/download?language=en", "us-ri/guidance/tax/adv-2021-53", "ADV 2021-53, Advisory for Taxpayers and Tax Professionals: inflation-adjusted amounts set for tax year 2022 (December 23, 2021)", "2022", "advisory", 5)
doc(f"{RI}/2022-08/H7123Aaa_CTR_0.pdf", "us-ri/statute/bills/2022/h7123-sub-a-aa-child-tax-rebates", "2022 H 7123 Substitute A as amended: section adding R.I. Gen. Laws 44-30-103 (Child Tax Rebates), excerpt posted by the Division of Taxation", "2022", "bill_excerpt", 1, authority="Rhode Island General Assembly (excerpt posted by the Division of Taxation)")
doc("https://webserver.rilegislature.gov/BillText/BillText26/HouseText26/H7127Aaa.html", "us-ri/statute/bills/2026/h7127-sub-a-aa", "2026 H 7127 Substitute A as amended (FY2027 appropriations act)", "2026", "bill_text", authority="Rhode Island General Assembly", text_selector="h1, h2, p")
doc("https://webserver.rilegislature.gov/Statutes/TITLE44/44-33/44-33-3.htm", "us-ri/statute/44-33-3", "R.I. Gen. Laws 44-33-3, Definitions (Property Tax Relief)", None, "statute_section", authority="Rhode Island General Assembly", closes=["https://webserver.rilegislature.gov/Statutes/TITLE44/44-33/44-33-3.htm", "http://webserver.rilin.state.ri.us/Statutes/TITLE44/44-33/44-33-3.htm", "https://law.justia.com/codes/rhode-island/2022/title-44/chapter-44-33/section-44-33-3/"])
doc("https://webserver.rilegislature.gov/Statutes/TITLE44/44-33/44-33-9.htm", "us-ri/statute/44-33-9", "R.I. Gen. Laws 44-33-9, Computation of credit (Property Tax Relief)", None, "statute_section", authority="Rhode Island General Assembly", closes=["https://webserver.rilegislature.gov/Statutes/TITLE44/44-33/44-33-9.htm", "http://webserver.rilin.state.ri.us/Statutes/TITLE44/44-33/44-33-9.htm"])
doc("https://www.rilegislature.gov/pressrelease/_layouts/15/ril.pressrelease.inputform/DisplayForm.aspx?List=c8baae31-3c10-431c-8dcd-9dbbe21ce3e9&ID=376675", "us-ri/guidance/general-assembly/press-release-376675", "Sen. Vargas lauds child tax credit in state budget bill (General Assembly press release 376675, June 10, 2026)", "2026", "press_release", authority="Rhode Island General Assembly", selector="#Displaycontent")
doc("https://www.rilegislature.gov/sfiscal/Budget%20Analyses/FY2027%20SFO%20Budget%20as%20passed%20by%20House%20Finance.pdf", "us-ri/guidance/senate-fiscal-office/fy2027-budget-as-passed-by-house-finance", "Senate Fiscal Office Report: FY2027 Budget, Changes to the Governor (2026-H-7127 Substitute A, as passed by House Finance)", "2026", "fiscal_analysis", 106, authority="Rhode Island Senate Fiscal Office")
doc("https://governor.ri.gov/press-releases/governor-mckee-signs-fiscal-year-2027-budget-advancing-key-affordability-all", "us-ri/guidance/governor/press-release-fy2027-budget-signed", "Governor McKee Signs Fiscal Year 2027 Budget, Advancing Key Affordability for All (press release)", "2026", "press_release", authority="Office of the Governor of Rhode Island")

# --- South Carolina ---------------------------------------------------------
doc("https://dor.sc.gov/forms-site/Forms/I319_2021.pdf", "us-sc/form/dor/ty2021/i-319", "I-319 2021 Tuition Tax Credit (Rev. 3/1/21)", "2021", "form", 5)
for _y, _p in (("2020", 35), ("2021", 37), ("2022", 38), ("2023", 48)):
    doc(f"https://dor.sc.gov/forms-site/Forms/IITPacket_{_y}.pdf", f"us-sc/form/dor/ty{_y}/sc1040-packet", f"{_y} SC1040 Individual Income Tax Form and Instructions (packet)", _y, "forms_and_instructions_packet", _p)
doc("https://dor.sc.gov/forms-site/Forms/TC60_2023.pdf", "us-sc/form/dor/ty2023/sc-schedule-tc-60", "SC Schedule TC-60, South Carolina Earned Income Tax Credit (Rev. 5/8/23)", "2023", "schedule", 1)
doc("https://dor.sc.gov/sites/dor/files/forms/TC60_2021.pdf", "us-sc/form/dor/ty2021/sc-schedule-tc-60", "SC Schedule TC-60, South Carolina Earned Income Tax Credit 2021", "2021", "schedule", 1)
doc("https://dor.sc.gov/sites/dor/files/forms/TC60_2022.pdf", "us-sc/form/dor/ty2022/sc-schedule-tc-60", "SC Schedule TC-60, South Carolina Earned Income Tax Credit 2022 (Rev. 3/21/22)", "2022", "schedule", 1)
doc("https://dor.sc.gov/sites/dor/files/forms/SC4972_2024.pdf", "us-sc/form/dor/ty2024/sc4972", "SC4972, Tax on Lump-Sum Distributions (Rev. 7/11/24)", "2024", "form", 2)
doc("https://dor.sc.gov/income-tax-south-carolina-internal-revenue-code-conformity-update", "us-sc/guidance/dor/income-tax-irc-conformity-update", "SC Information Letter #26-4 (Revised), South Carolina Internal Revenue Code Conformity Update (Individual Income Tax), January 30, 2026", "2025", "information_letter", 2)
doc("https://treasurer.sc.gov/about-us/newsroom/529-updates-in-one-big-beautiful-bill-give-south-carolina-families-even-more-flexibility-for-educational-savings/", "us-sc/guidance/treasurer/529-updates-one-big-beautiful-bill", "529 updates in 'One Big, Beautiful Bill' give South Carolina families even more flexibility for educational savings (State Treasurer news release)", None, "press_release", authority="South Carolina State Treasurer")
doc("https://www.scstatehouse.gov/sess124_2021-2022/bills/1087.htm", "us-sc/statute/bills/2021-2022/1087", "2021-2022 Bill 1087: Comprehensive tax cut act of 2022 (South Carolina General Assembly)", "2022", "bill_text", authority="South Carolina General Assembly")
doc("https://www.scstatehouse.gov/sess126_2025-2026/bills/4216.htm", "us-sc/statute/bills/2025-2026/4216", "2025-2026 Bill 4216: Income tax (South Carolina General Assembly)", "2026", "bill_text", authority="South Carolina General Assembly")

# --- Utah -------------------------------------------------------------------
doc("https://files.tax.utah.gov/tax/forms/2021/tc-40.pdf", "us-ut/form/ustc/ty2021/tc-40", "2021 TC-40, Utah Individual Income Tax Return", "2021", "return_form", 9)
for _y, _p in (("2021", 32), ("2022", 32), ("2023", 33), ("2024", 34)):
    _closes = [f"https://files.tax.utah.gov/tax/forms/{_y}/tc-40inst.pdf"]
    if _y == "2021":
        _closes.append("https://www.taxformfinder.org/forms/2021/2021-utah-tc-40-full-packet.pdf")
    doc(f"https://files.tax.utah.gov/tax/forms/{_y}/tc-40inst.pdf", f"us-ut/form/ustc/ty{_y}/tc-40-instructions", f"{_y} TC-40 Utah Individual Income Tax Forms and Instructions", _y, "instructions", _p, closes=_closes)
doc("https://incometax.utah.gov/tc-40a/", "us-ut/guidance/ustc/tc-40a-supplemental-schedule-instructions", "TC-40A Supplemental Schedule Instructions (Utah Income Tax, 2025)", "2025", "web_instructions", closes=["https://incometax.utah.gov/tc-40a/"] + [f"https://incometax.utah.gov/credits/{s}" for s in ("at-home-parent", "military-retirement", "my529", "retirement-credit", "ss-benefits")])
doc("https://incometax.utah.gov/credits/taxpayer-tax-credit", "us-ut/guidance/ustc/tc-40-line-by-line-instructions", "TC-40 Line-by-Line Instructions (Utah Income Tax, 2025; the taxpayer tax credit address redirects to line 20)", "2025", "web_instructions")
doc("https://incometax.utah.gov/credits", "us-ut/guidance/ustc/information-about-tax-credits", "Information About Tax Credits (Utah Income Tax, 2025)", "2025", "web_page")
doc("https://tax.utah.gov/relief/homeowner-renter-relief/", "us-ut/guidance/ustc/homeowner-renter-relief", "Homeowner's or Renter's Relief (Utah State Tax Commission)", None, "web_page", text_selector="article *:not(:has(div, p, li, table, h1, h2, h3, h4))")
doc("https://my529.org/utah-state-tax-benefits-information/", "us-ut/guidance/my529/utah-state-tax-benefits-information", "Utah state tax benefits information (my529)", None, "program_faq", authority="my529 (Utah Educational Savings Plan)")
for _sess, _bill, _t, _p, _html in (
    ("2025", "HB0106", "H.B. 106 Income Tax Revisions", 8, "https://le.utah.gov/~2025/bills/static/HB0106.html"),
    ("2025", "SB0071", "S.B. 71 Social Security Tax Revisions", 3, "https://le.utah.gov/~2025/bills/static/SB0071.html"),
    ("2026", "HB0290", "H.B. 290 Child Tax Credit Amendments", 3, "https://le.utah.gov/~2026/bills/static/HB0290.html"),
    ("2026", "SB0060", "S.B. 60 Income Tax Rate Amendments", 2, "https://le.utah.gov/~2026/bills/static/SB0060.html"),
):
    _u = f"https://le.utah.gov/Session/{_sess}/bills/enrolled/{_bill}.pdf"
    doc(_u, f"us-ut/statute/bills/{_sess}/{_bill.lower()}-enrolled", f"{_t}, Enrolled Copy ({_sess} General Session, State of Utah)", _sess, "enrolled_bill", _p, closes=[_u, _html], authority="Utah State Legislature")

# Prior versions of Utah Code sections that PolicyEngine cites by version. The xcode page
# (?v=<id>) and historical.html wrappers render the version through JavaScript; the
# publisher serves each version as a static file C59-10-S<sec>_<id>.html, fetched here as
# download_url (it prints "Effective ... Superseded ..."). The current text of every
# section is held in us-ut/statute/2026-09-14-income-tax-chapter-title-59.
_UTX = "https://le.utah.gov/xcode/Title59/Chapter10"
_UT_VERSIONS: dict[tuple[str, str], list[str]] = {}
for _wrapper in (
    f"{_UTX}/59-10-S1018.html?v=C59-10-S1018_2023050320230503",
    f"{_UTX}/59-10-S1019.html?v=C59-10-S1019_2022032320220323",
    f"{_UTX}/59-10-S104.1.html?v=C59-10-S104.1_1800010118000101",
    f"{_UTX}/59-10-S104.html?v=C59-10-S104_2022050420220504",
    f"{_UTX}/59-10-S104.html?v=C59-10-S104_2024010120240501",
    f"{_UTX}/59-10-S1042.html?v=C59-10-S1042_2023050320230503",
    f"{_UTX}/59-10-S1044.html?v=C59-10-S1044_2022050420220504",
    f"{_UTX}/59-10-S1047.html?v=C59-10-S1047_2023050320240101",
    f"{_UTX}/59-10-S1047.html?v=C59-10-S1047_2025010120240501",
    f"{_UTX}/59-10-S114.html?v=C59-10-S114_2022032320220323",
    "https://le.utah.gov/xcode/historical.html?date=1/1/2014&oc=/xcode/Title59/Chapter10/C59-10-S104_1800010118000101.html",
    "https://le.utah.gov/xcode/historical.html?date=2/7/2025&oc=/xcode/Title59/Chapter10/C59-10-S1018_2018051620180721.html",
    "https://le.utah.gov/xcode/historical.html?date=2/7/2025&oc=/xcode/Title59/Chapter10/C59-10-S1018_2021050520210505.html",
    "https://le.utah.gov/xcode/historical.html?date=5/8/2018&oc=/xcode/Title59/Chapter10/C59-10-S104_2018050820180508.html",
    "https://le.utah.gov/xcode/historical.html?date=8/17/2022&oc=/xcode/Title59/Chapter10/C59-10-S104_2022050420220504.html",
):
    _m = re.search(r"C59-10-S([0-9.]+)_(\d{16})", _wrapper)
    _UT_VERSIONS.setdefault((_m.group(1), _m.group(2)), []).append(_wrapper)
# Effective / superseded dates printed on each version file (read 2026-10-06).
_UT_VERSION_DATES = {
    ("1018", "2018051620180721"): "effective 7/21/2018, superseded 5/5/2021",
    ("1018", "2021050520210505"): "effective 5/5/2021, superseded 5/3/2023",
    ("1018", "2023050320230503"): "effective 5/3/2023, superseded 5/6/2026",
    ("1019", "2022032320220323"): "effective 3/23/2022",
    ("104.1", "1800010118000101"): "superseded 1/1/2026",
    ("104", "1800010118000101"): "superseded 5/8/2018",
    ("104", "2018050820180508"): "effective 5/8/2018, superseded 5/4/2022",
    ("104", "2022050420220504"): "effective 5/4/2022, superseded 5/3/2023",
    ("104", "2024010120240501"): "effective 1/1/2024, superseded 5/7/2025",
    ("1042", "2023050320230503"): "effective 5/3/2023, superseded 5/7/2025",
    ("1044", "2022050420220504"): "effective 5/4/2022, superseded 5/3/2023",
    ("1047", "2023050320240101"): "effective 1/1/2024, superseded 1/1/2025",
    ("1047", "2025010120240501"): "effective 1/1/2025, superseded 5/7/2025",
    ("114", "2022032320220323"): "effective 3/23/2022, superseded 5/3/2023",
}
for (_sec, _vid), _wrappers in _UT_VERSIONS.items():
    doc(
        _wrappers[0],
        f"us-ut/statute/59-10-{_sec}--version-{_vid}",
        f"Utah Code 59-10-{_sec}, prior version ({_UT_VERSION_DATES[(_sec, _vid)]}; le.utah.gov version file C59-10-S{_sec}_{_vid})",
        None,
        "statute_section_version",
        closes=_wrappers,
        authority="Utah Office of Legislative Research and General Counsel",
        selector="#secdiv",
        download=f"{_UTX}/C59-10-S{_sec}_{_vid}.html",
        note="prior version of the section; the current text is in us-ut/statute/2026-09-14-income-tax-chapter-title-59",
    )

# --- Virginia ---------------------------------------------------------------
VA = "https://www.tax.virginia.gov/sites/default/files/taxforms/individual-income-tax"
doc(f"{VA}/2020/schedule-and-instructions-2020.pdf", "us-va/form/tax/ty2020/schedule-a-and-instructions", "2020 Virginia Schedule A, Itemized Deductions, with instructions", "2020", "schedule", 4)
for _y in ("2021", "2022", "2023", "2024", "2025"):
    doc(f"{VA}/{_y}/schedule-{_y}.pdf", f"us-va/form/tax/ty{_y}/schedule-a", f"{_y} Virginia Schedule A, Itemized Deductions", _y, "schedule", 2)
for _y in ("2021", "2022", "2023"):
    doc(f"{VA}/{_y}/schedule-adj-{_y}.pdf", f"us-va/form/tax/ty{_y}/schedule-adj", f"{_y} Virginia Schedule ADJ (Form 760-ADJ)", _y, "schedule", 2)
doc(f"{VA}/2022/760-2022.pdf", "us-va/form/tax/ty2022/form-760", "2022 Virginia Form 760, Resident Income Tax Return", "2022", "return_form", 2)
doc("https://www.tax.virginia.gov/filing-status", "us-va/guidance/tax/filing-status", "Filing Status (Virginia Tax)", None, "web_page")
doc("https://www.tax.virginia.gov/rebate", "us-va/guidance/tax/rebate", "What You Need to Know About the 2025 Tax Rebate (Virginia Tax)", "2025", "web_page")
doc("https://www.tax.virginia.gov/laws-rules-decisions/rulings-tax-commissioner/13-5", "us-va/guidance/tax/rulings-of-the-tax-commissioner/13-5", "Ruling of the Tax Commissioner 13-5 (Virginia age deduction and obligations of the United States)", None, "ruling", selector="#lrdContent article", text_selector="article > div")
doc("https://www.tax.virginia.gov/sites/default/files/inline-files/2023-legislative-summary.pdf", "us-va/guidance/tax/legislative-summary-2023", "2023 Legislative Summary, Virginia Department of Taxation (updated September 15, 2023)", "2023", "legislative_summary", 31)
doc("https://www.tax.virginia.gov/sites/default/files/inline-files/2026-legislative-summary.pdf", "us-va/guidance/tax/legislative-summary-2026", "2026 Legislative Summary, Virginia Department of Taxation (July 6, 2026)", "2026", "legislative_summary", 24)
doc("https://budget.lis.virginia.gov/amendment/2026/2/HB30/Introduced/CR/4-14/1c", "us-va/statute/budget/2026/hb30/conference-report/4-14-1c", "HB30 (2026) Conference Report amendment 4-14#1c (Effective Date) Standard Deduction", "2026", "budget_amendment", authority="Virginia General Assembly (Legislative Information System)")
doc("https://budget.lis.virginia.gov/item/2023/2/HB6001/Introduced/3/3-5.28/", "us-va/statute/budget/2023/hb6001/introduced/3-5.28", "HB6001 (2023 Special Session) Item 3-5.28, Individual Income Tax Rebate (as introduced)", "2023", "budget_item", authority="Virginia General Assembly (Legislative Information System)")

# --- Vermont ----------------------------------------------------------------
VT = "https://tax.vermont.gov/sites/tax/files/documents"
for _f, _p, _t, _y, _s, _n in (
    ("IN-111-2021.pdf", "ty2021/in-111", "2021 Form IN-111, Vermont Income Tax Return", "2021", "return_form", 2),
    ("IN-111-2022.pdf", "ty2022/in-111", "2022 Form IN-111, Vermont Income Tax Return", "2022", "return_form", 2),
    ("IN-111-2023.pdf", "ty2023/in-111", "2023 Form IN-111, Vermont Income Tax Return", "2023", "return_form", 2),
    ("IN-111-2024.pdf", "ty2024/in-111", "2024 Form IN-111, Vermont Income Tax Return", "2024", "return_form", 2),
    ("IN-111-Instr-2023.pdf", "ty2023/in-111-instructions", "2023 Form IN-111 Instructions, Vermont Income Tax Return", "2023", "instructions", 19),
    ("IN-112%20Instr-2021.pdf", "ty2021/in-112-instructions", "2021 Schedule IN-112 Instructions, Vermont Tax Adjustments and Credits", "2021", "instructions", 3),
    ("IN-112%20Instr-2022.pdf", "ty2022/in-112-instructions", "2022 Schedule IN-112 Instructions, Vermont Tax Adjustments and Credits", "2022", "instructions", 4),
    ("IN-112-Instr-2023.pdf", "ty2023/in-112-instructions", "2023 Schedule IN-112 Instructions, Vermont Tax Adjustments and Credits", "2023", "instructions", 4),
    ("IN-112-Instr-2024.pdf", "ty2024/in-112-instructions", "2024 Schedule IN-112 Instructions, Vermont Tax Adjustments and Credits", "2024", "instructions", 4),
    ("IN-112-2020.pdf", "ty2020/in-112", "2020 Schedule IN-112, Vermont Tax Adjustments and Credits", "2020", "schedule", 2),
    ("IN-112-2021.pdf", "ty2021/in-112", "2021 Schedule IN-112, Vermont Tax Adjustments and Credits", "2021", "schedule", 2),
    ("IN-112-2022.pdf", "ty2022/in-112", "2022 Schedule IN-112, Vermont Tax Adjustments and Credits", "2022", "schedule", 2),
    ("IN-112-2023.pdf", "ty2023/in-112", "2023 Schedule IN-112, Vermont Tax Adjustments and Credits", "2023", "schedule", 2),
    ("IN-112-2024.pdf", "ty2024/in-112", "2024 Schedule IN-112, Vermont Tax Adjustments and Credits", "2024", "schedule", 2),
    ("IN-119-2021.pdf", "ty2021/in-119", "2021 Schedule IN-119, Vermont Tax Adjustments and Nonrefundable Credits", "2021", "schedule", 2),
    ("IN-119-2022.pdf", "ty2022/in-119", "2022 Schedule IN-119, Vermont Tax Adjustments and Nonrefundable Credits", "2022", "schedule", 2),
    ("IN-119-2023.pdf", "ty2023/in-119", "2023 Schedule IN-119, Vermont Tax Adjustments and Nonrefundable Credits", "2023", "schedule", 2),
    ("IN-119-2024.pdf", "ty2024/in-119", "2024 Schedule IN-119, Vermont Tax Adjustments and Nonrefundable Credits", "2024", "schedule", 2),
    ("IN-153-2021.pdf", "ty2021/in-153", "2021 Schedule IN-153, Vermont Capital Gain Exclusion Calculation", "2021", "schedule", 2),
    ("IN-153-2022.pdf", "ty2022/in-153", "2022 Schedule IN-153, Vermont Capital Gains Exclusion Calculation", "2022", "schedule", 2),
    ("IN-153-2023.pdf", "ty2023/in-153", "2023 Schedule IN-153, Vermont Capital Gains Exclusion Calculation", "2023", "schedule", 2),
    ("IN-153-2024.pdf", "ty2024/in-153", "2024 Schedule IN-153, Vermont Capital Gains Exclusion Calculation", "2024", "schedule", 2),
    ("Income-Booklet-2021.pdf", "ty2021/income-tax-return-booklet", "Vermont Income Tax Return Booklet, 2021 Forms and Instructions", "2021", "forms_and_instructions_packet", 48),
    ("Income%20Booklet-2022.pdf", "ty2022/income-tax-return-booklet", "Vermont Income Tax Return Booklet, 2022 Forms and Instructions", "2022", "forms_and_instructions_packet", 52),
    ("Income-Booklet-2023.pdf", "ty2023/income-tax-return-booklet", "Vermont Income Tax Return Booklet, 2023 Forms and Instructions", "2023", "forms_and_instructions_packet", 52),
    ("Income%20Booklet-2024.pdf", "ty2024/income-tax-return-booklet", "Vermont Income Tax Return Booklet, 2024 Forms and Instructions", "2024", "forms_and_instructions_packet", 52),
    ("Income-Booklet-2025.pdf", "ty2025/income-tax-return-booklet", "Vermont Income Tax Return Booklet, 2025 Forms and Instructions", "2025", "forms_and_instructions_packet", 52),
    ("RCC-146-2022.pdf", "ty2022/rcc-146", "2022 Form RCC-146, Vermont Renter Credit Claim", "2022", "claim_form", 1),
    ("RateSched-2021.pdf", "ty2021/tax-rate-schedules", "2021 Vermont Tax Rate Schedules", "2021", "tax_rate_schedule", 1),
    ("RateSched-2022.pdf", "ty2022/tax-rate-schedules", "2022 Vermont Tax Rate Schedules", "2022", "tax_rate_schedule", 1),
    ("RateSched-2023.pdf", "ty2023/tax-rate-schedules", "2023 Vermont Tax Rate Schedules", "2023", "tax_rate_schedule", 1),
    ("RateSched-2024.pdf", "ty2024/tax-rate-schedules", "2024 Vermont Tax Rate Schedules", "2024", "tax_rate_schedule", 1),
    ("RateSched-2025.pdf", "ty2025/wage-bracket-withholding-charts", "2025 Vermont Wage Bracket Withholding Charts (file RateSched-2025.pdf)", "2025", "withholding_tables", 10),
):
    _closes = [f"{VT}/{_f}"]
    if _f == "IN-112-2021.pdf":
        _closes.append("https://taxsim.nber.org/historical_state_tax_forms/VT/2021/IN-112-2021.pdf")
    doc(f"{VT}/{_f}", f"us-vt/form/vdt/{_p}", _t, _y, _s, _n, closes=_closes)
doc("https://tax.vermont.gov/individuals/personal-income-tax/tax-credits", "us-vt/guidance/vdt/tax-credits-and-adjustments-for-individuals", "Tax Credits and Adjustments for Individuals (Vermont Department of Taxes)", None, "web_page")
doc("https://tax.vermont.gov/individuals/renter-credit/calculator-and-credit-amounts", "us-vt/guidance/vdt/renter-credit-calculator-and-credit-amounts", "Renter Credit: Calculator and Credit Amounts (Vermont Department of Taxes)", None, "web_page")
doc("https://tax.vermont.gov/individuals/seniors-and-retirees", "us-vt/guidance/vdt/seniors-and-retirees", "Seniors and Retirees (Vermont Department of Taxes)", None, "web_page")
doc("https://legislature.vermont.gov/statutes/section/32/154/06066", "us-vt/statute/32-6066", "32 V.S.A. § 6066, Computation of homestead property tax exemption, municipal property tax credit, and renter credit", None, "statute_section", authority="Vermont General Assembly", closes=["https://legislature.vermont.gov/statutes/section/32/154/06066", "https://law.justia.com/codes/vermont/2022/title-32/chapter-154/section-6066/"])
doc("https://legislature.vermont.gov/statutes/section/32/154/06061", "us-vt/statute/32-6061", "32 V.S.A. § 6061, Definitions (chapter 154, homestead property tax exemption and renter credit)", None, "statute_section", authority="Vermont General Assembly", closes=["https://law.justia.com/codes/vermont/2022/title-32/chapter-154/section-6061/"])
doc("https://legislature.vermont.gov/statutes/fullchapter/32/246", "us-vt/statute/chapter-246", "32 V.S.A. chapter 246, Child Care Contribution (full chapter)", None, "statute_chapter", authority="Vermont General Assembly")
doc("https://legislature.vermont.gov/Documents/2022/Docs/ACTS/ACT138/ACT138%20As%20Enacted.pdf", "us-vt/statute/session-laws/2022/act-138", "Act No. 138 (2022), An act relating to tax reductions and other aid for Vermonters (H.510), as enacted", "2022", "session_law", 15, authority="Vermont General Assembly")
doc("https://legislature.vermont.gov/Documents/2024/Docs/ACTS/ACT072/ACT072%20As%20Enacted.pdf", "us-vt/statute/session-laws/2024/act-072", "Act No. 72 (2023-2024 session), An act relating to technical and administrative changes to Vermont's tax laws, as enacted", "2024", "session_law", 39, authority="Vermont General Assembly")
doc("https://legislature.vermont.gov/Documents/2026/Docs/ACTS/ACT169/ACT169%20As%20Enacted.pdf", "us-vt/statute/session-laws/2026/act-169", "Act No. 169 (2026), An act relating to homestead property tax yields, the nonhomestead property tax rate, and technical changes to education laws, as enacted", "2026", "session_law", 18, authority="Vermont General Assembly")
doc("https://legislature.vermont.gov/Documents/2026/Docs/BILLS/S-0051/S-0051%20As%20Passed%20by%20Both%20House%20and%20Senate%20Official.pdf", "us-vt/statute/bills/2025-2026/s-51-as-passed", "S.51 as introduced and passed by Senate and House (2025-2026 session; Act 71)", "2026", "bill_text", 12, authority="Vermont General Assembly")

# --- Washington -------------------------------------------------------------
doc("https://app.leg.wa.gov/RCW/default.aspx?cite=82.08.0206", "us-wa/statute/82/82.08/82.08.0206", "RCW 82.08.0206, Credits—Working families—Eligible low-income persons", None, "statute_section", authority="Washington State Legislature")
doc("https://lawfilesext.leg.wa.gov/biennium/2021-22/Pdf/Bills/Session%20Laws/Senate/5096-S.SL.pdf", "us-wa/statute/session-laws/2021/chapter-196", "Engrossed Substitute Senate Bill 5096, Chapter 196, Laws of 2021 (session law)", "2021", "session_law", 17, authority="Washington State Legislature")
doc("https://lawfilesext.leg.wa.gov/biennium/2025-26/Htm/Bills/Session%20Laws/Senate/5813-S.SL.htm", "us-wa/statute/session-laws/2025/chapter-421", "Engrossed Substitute Senate Bill 5813, Chapter 421, Laws of 2025 (session law)", "2025", "session_law", authority="Washington State Legislature", text_selector="body > div")
doc("https://lawfilesext.leg.wa.gov/biennium/2025-26/Pdf/Bills/Senate%20Passed%20Legislature/6346-S.PL.pdf", "us-wa/statute/bills/2026/sb6346-passed-legislature", "Engrossed Substitute Senate Bill 6346 as passed by the Legislature (2026 Regular Session)", "2026", "bill_text", 109, authority="Washington State Legislature")
doc("https://apps.leg.wa.gov/wac/default.aspx?cite=458-20-285", "us-wa/regulation/458/458-20/458-20-285", "WAC 458-20-285, Working families tax credit", None, "regulation_section", authority="Washington State Legislature (Code Reviser)", text_selector="#contentWrapper div")
doc("https://lawfilesext.leg.wa.gov/law/wsrpdf/2025/10/25-10-017.pdf", "us-wa/rulemaking/wsr/25-10-017", "Washington State Register WSR 25-10-017, permanent rules", "2025", "register_filing", 2, authority="Washington State Code Reviser")
for _yr, _slug, _t in (
    ("2023", "applications-now-being-accepted-working-families-tax-credit", "Applications Now Being Accepted for the Working Families Tax Credit (2023 news release)"),
    ("2024", "tax-year-2023-applications-now-being-accepted-working-families-tax-credit", "Tax year 2023 applications now being accepted for the Working Families Tax Credit (2024 news release)"),
    ("2025", "working-families-tax-credit-application-window-opens-feb-1", "Working Families Tax Credit application window opens Feb. 1 (2025 news release)"),
    ("2026", "working-families-tax-credit-application-window-opens-feb-1", "Working Families Tax Credit application window opens Feb. 1 (2026 news release)"),
):
    doc(f"https://dor.wa.gov/about/news-releases/{_yr}/{_slug}", f"us-wa/guidance/dor/news-releases/{_yr}/{_slug}", _t, _yr, "press_release")
doc("https://dor.wa.gov/forms-publications/publications-subject/tax-topics/2021-tax-legislation", "us-wa/guidance/dor/tax-topics/2021-tax-legislation", "2021 Tax Legislation (Washington Department of Revenue tax topic)", "2021", "web_page")
doc("https://dor.wa.gov/sites/default/files/2026-07/ETA3240.2026.pdf", "us-wa/guidance/dor/eta-3240-2026", "Excise Tax Advisory ETA 3240.2026, Working Families Tax Credit (issued January 5, 2026)", "2026", "advisory", 3)
doc("https://workingfamiliescredit.wa.gov/eligibility", "us-wa/guidance/dor/working-families-tax-credit-eligibility", "Eligibility, Washington State Working Families Tax Credit", None, "web_page")
doc("https://workingfamiliescredit.wa.gov/sites/default/files/2024-01/WFTC_AppInstr_English_2023.pdf", "us-wa/form/dor/ty2023/wftc-application-instructions", "2023 Working Families Tax Credit Application Instructions", "2023", "instructions", 12)
doc("https://workingfamiliescredit.wa.gov/sites/default/files/2024-01/WFTC_app_2023_English.pdf", "us-wa/form/dor/ty2023/wftc-application", "2023 Working Families Tax Credit Application (Form 14 0001)", "2023", "application_form", 6)

# --- Wisconsin --------------------------------------------------------------
doc("https://www.revenue.wi.gov/DOR%20Publications/pb126.pdf", "us-wi/guidance/dor/publication-126", "Publication 126, How Your Retirement Benefits Are Taxed (1/26)", "2025", "publication", 13)
doc("https://www.revenue.wi.gov/DORReports/23sumrpt.pdf", "us-wi/guidance/dor/tax-exemption-devices-2023-25", "Wisconsin Tax Exemption Devices 2023-25 (Department of Revenue summary report)", "2023", "report", 132)
doc("https://www.revenue.wi.gov/DORReports/25sumrpt.pdf", "us-wi/guidance/dor/tax-exemption-devices-2025-27", "Wisconsin Tax Exemption Devices 2025-27 (Department of Revenue summary report)", "2025", "report", 116)
doc("https://www.revenue.wi.gov/Pages/FAQS/pcs-taxrates.aspx", "us-wi/guidance/dor/tax-rates", "Tax Rates (Wisconsin Department of Revenue)", None, "web_page", closes=["https://www.revenue.wi.gov/Pages/FAQS/pcs-taxrates.aspx", "https://www.efile.com/wisconsin-tax-brackets-rates-and-forms/"])
doc("https://www.revenue.wi.gov/TaxForms2023/2023-Form1-ES-Inst.pdf", "us-wi/form/dor/ty2023/form-1-es-instructions", "2023 Form 1-ES Instructions, Estimated Income Tax for Individuals, Estates, and Trusts", "2023", "instructions", 2)
doc("https://www.revenue.wi.gov/TaxForms2025/2025-Form1-ES-Inst.pdf", "us-wi/form/dor/ty2025/form-1-es-instructions", "2025 Form 1-ES Instructions, Estimated Income Tax for Individuals, Estates, and Trusts", "2025", "instructions", 4)
doc("https://docs.legis.wisconsin.gov/misc/lfb/informational_papers/january_2021/0013_homestead_tax_credit_informational_paper_13.pdf", "us-wi/guidance/lfb/informational-paper-13-homestead-tax-credit-2021", "Informational Paper 13, Homestead Tax Credit (Legislative Fiscal Bureau, January 2021)", "2021", "fiscal_analysis", 14, authority="Wisconsin Legislative Fiscal Bureau")
doc("https://docs.legis.wisconsin.gov/misc/lfb/informational_papers/january_2023/0002_individual_income_tax_informational_paper_2.pdf", "us-wi/guidance/lfb/informational-paper-2-individual-income-tax-2023", "Informational Paper 2, Individual Income Tax (Legislative Fiscal Bureau, January 2023)", "2023", "fiscal_analysis", 48, authority="Wisconsin Legislative Fiscal Bureau")
doc("https://dfi.wi.gov/Pages/EducationalServices/CollegeSavingsCareerPlanning/CollegeSavingsProgram.aspx", "us-wi/guidance/dfi/college-savings-program", "Wisconsin 529 College Savings Program (Department of Financial Institutions)", None, "web_page", authority="Wisconsin Department of Financial Institutions", text_selector=LEAF_MAIN)
doc("https://www.edvest.com/learn/tax-benefits/", "us-wi/guidance/edvest/tax-benefits", "Edvest 529: Wisconsin 529 Triple Tax Benefits", None, "program_faq", authority="Edvest 529 (State of Wisconsin College Savings Program, Department of Financial Institutions)")
doc("https://docs.legis.wisconsin.gov/2023/statutes/statutes/71/i/05/22/dm", "us-wi/statute/2023-24-edition/71.05/22/dm", "Wis. Stat. 71.05(22)(dm) (2023-24 Wisconsin Statutes edition page)", None, "statute_subunit", authority="Wisconsin Legislative Reference Bureau", selector='div[data-path="/2023/statutes/statutes/71/i/05/22/dm"]')
doc("https://docs.legis.wisconsin.gov/2023/statutes/statutes/71/i/07/9/b/5", "us-wi/statute/2023-24-edition/71.07/9/b/5", "Wis. Stat. 71.07(9)(b)5. (2023-24 Wisconsin Statutes edition page)", None, "statute_subunit", authority="Wisconsin Legislative Reference Bureau", selector='div[data-path="/2023/statutes/statutes/71/i/07/9/b/5"]')

# --- West Virginia ----------------------------------------------------------
doc("https://tax.wv.gov/Documents/TaxForms/2020/it140.booklet.pdf", "us-wv/form/tax/ty2020/it-140-booklet", "2020 West Virginia Personal Income Tax Forms & Instructions (IT-140 booklet)", "2020", "forms_and_instructions_packet", 52)
doc("https://tax.wv.gov/Documents/TaxForms/2021/it140.booklet.pdf", "us-wv/form/tax/ty2021/it-140-booklet", "2021 West Virginia Personal Income Tax Forms & Instructions (IT-140 booklet)", "2021", "forms_and_instructions_packet", 52)
doc("https://tax.wv.gov/Documents/TaxForms/2021/it140.pdf", "us-wv/form/tax/ty2021/it-140", "2021 Form IT-140, West Virginia Personal Income Tax Return (REV 9-21)", "2021", "return_form", 34)
doc("https://www.wvlegislature.gov/Bill_Text_HTML/2026_SESSIONS/RS/bills/sb392%20sub1%20enr.pdf", "us-wv/statute/bills/2026/sb392-enrolled", "Enrolled Committee Substitute for Senate Bill 392 (West Virginia Legislature, 2026 Regular Session)", "2026", "enrolled_bill", 9, authority="West Virginia Legislature")
doc("https://www.smart529.com/learn/features-and-benefits.html", "us-wv/guidance/smart529/features-and-benefits", "SMART529: Features and Benefits", None, "program_faq", authority="SMART529 (West Virginia State Treasurer's Office)")


# ---------------------------------------------------------------------------
# EXTRACT-MANIFEST rows: the May 2026 tax-forms manifests on main name the document
# (citation_path below is that manifest's path with the grammar slug applied: underscores
# and other characters outside the citation-path alphabet fold to hyphens).
# ---------------------------------------------------------------------------

EM_MANIFESTS = (
    "manifests/us-or-tax-forms.yaml",
    "manifests/us-sc-individual-income-tax-forms.yaml",
    "manifests/us-va-tax-forms.yaml",
    "manifests/us-wi-tax-forms.yaml",
    "manifests/us-wv-individual-income-tax-forms.yaml",
)
# Facts read from each PDF on 2026-10-06: (title, tax year, subtype, pages).
EM_FACTS: dict[str, tuple[str, str, str, int]] = {
    "form-or-40-inst_101-040-1_2021": ("2021 Oregon Income Tax Form OR-40 Instructions (full-year resident; updated April 20, 2022)", "2021", "instructions", 29),
    "form-or-40-inst_101-040-1_2022": ("2022 Oregon Income Tax Form OR-40 Instructions (full-year resident)", "2022", "instructions", 25),
    "form-or-40-inst_101-040-1_2023": ("2023 Oregon Income Tax Form OR-40 Instructions (full-year resident; updated March 14, 2024)", "2023", "instructions", 30),
    "form-or-40-inst_101-040-1_2024": ("2024 Oregon Income Tax Form OR-40 Instructions (full-year resident)", "2024", "instructions", 28),
    "form-or-40-n_or-40-p-inst_101-048-1_2024": ("2024 Oregon Income Tax Form OR-40-N and Form OR-40-P Instructions (nonresident/part-year resident)", "2024", "instructions", 31),
    "form-or-40_101-040_2021": ("2021 Form OR-40, Oregon Individual Income Tax Return for Full-year Residents", "2021", "return_form", 8),
    "publication-or-17_101-431_2020": ("2020 Publication OR-17, Oregon Individual Income Tax Guide (150-101-431, Rev. 04-01-22)", "2020", "tax_guide", 138),
    "publication-or-17_101-431_2021": ("2021 Publication OR-17, Oregon Individual Income Tax Guide (150-101-431, Rev. 04-21-22)", "2021", "tax_guide", 142),
    "publication-or-17_101-431_2022": ("2022 Publication OR-17, Oregon Individual Income Tax Guide (150-101-431, Rev. 09-30-22)", "2022", "tax_guide", 145),
    "publication-or-17_101-431_2023": ("2023 Publication OR-17, Oregon Individual Income Tax Guide (150-101-431, Rev. 06-17-24)", "2023", "tax_guide", 146),
    "publication-or-17_101-431_2024": ("2024 Publication OR-17, Oregon Individual Income Tax Guide (150-101-431, Rev. 11-27-24)", "2024", "tax_guide", 143),
    "publication-or-wfhdc-tb_101-458_2021": ("Publication OR-WFHDC-TB, Working Family Household and Dependent Care (WFHDC) Tables, tax year 2021", "2021", "tax_table", 6),
    "publication-or-wfhdc-tb_101-458_2022": ("Publication OR-WFHDC-TB, Working Family Household and Dependent Care (WFHDC) Tables, tax year 2022", "2022", "tax_table", 6),
    "publication-or-wfhdc-tb_101-458_2023": ("Publication OR-WFHDC-TB, Working Family Household and Dependent Care (WFHDC) Tables, tax year 2023", "2023", "tax_table", 6),
    "schedule-or-wfhdc-inst_101-195-1_2021": ("Schedule OR-WFHDC Instructions 2021, Oregon Working Family Household and Dependent Care Credit", "2021", "instructions", 7),
    "schedule-or-wfhdc-inst_101-195-1_2022": ("Schedule OR-WFHDC Instructions 2022, Oregon Working Family Household and Dependent Care Credit", "2022", "instructions", 8),
    "schedule-or-wfhdc-inst_101-195-1_2023": ("Schedule OR-WFHDC Instructions 2023, Oregon Working Family Household and Dependent Care Credit", "2023", "instructions", 8),
    "combined-payroll_211-155-2_2026": ("Oregon Combined 2026 Payroll Tax Report, Instructions for Oregon employers", "2026", "instructions", 32),
    "sc1040_2020": ("2020 SC1040 Individual Income Tax Return (Rev. 10/14/20)", "2020", "return_form", 3),
    "sc1040_2021": ("2021 SC1040 Individual Income Tax Return (Rev. 8/11/21)", "2021", "return_form", 3),
    "sc1040_2022": ("2022 SC1040 Individual Income Tax Return (Rev. 4/29/22)", "2022", "return_form", 3),
    "sc1040inst_2022": ("SC1040 Instructions 2022 (Rev 10/13/2022)", "2022", "instructions", 19),
    "sc1040instr_2024": ("SC1040 2024 Individual Income Tax Instructions (September 2024)", "2024", "instructions", 26),
    "sc1040tt_2021": ("2021 South Carolina Individual Income Tax Tables (Revised 3/23/21)", "2021", "tax_table", 4),
    "sc1040tt_2022": ("2022 South Carolina Individual Income Tax Tables (Revised 10/4/22)", "2022", "tax_table", 4),
    "sc1040tt_2024": ("2024 South Carolina Individual Income Tax Tables (Revised 7/11/24)", "2024", "tax_table", 4),
    "2019-schedule-a-instructions": ("2019 Instructions for Virginia Schedule A, Itemized Deductions", "2019", "instructions", 2),
    "2021-760-instructions": ("2021 Virginia Form 760 Resident Individual Income Tax Booklet", "2021", "instructions", 52),
    "2022-760-instructions": ("2022 Virginia Form 760 Resident Individual Income Tax Booklet", "2022", "instructions", 52),
    "2023-760-instructions": ("2023 Virginia Form 760 Resident Individual Income Tax Instructions", "2023", "instructions", 52),
    "2024-760-instructions": ("2024 Virginia Form 760 Resident Individual Income Tax Instructions", "2024", "instructions", 52),
    "personalincometaxformsandinstructions.2022": ("2022 West Virginia Personal Income Tax Forms & Instructions", "2022", "forms_and_instructions_packet", 56),
    "it140.personalincometaxformsandinstructions.2023": ("2023 West Virginia Personal Income Tax Forms & Instructions", "2023", "forms_and_instructions_packet", 56),
    "it140.personalincometaxformsandinstructions.2024": ("2024 West Virginia Personal Income Tax Forms & Instructions", "2024", "forms_and_instructions_packet", 56),
}
WI_EM_FACTS: dict[str, tuple[str, str, int]] = {
    # file stem -> (title, subtype, pages); the tax year is the TaxFormsYYYY folder.
    "Form1-Inst": ("Form 1 Instructions, Wisconsin Income Tax", "instructions", 0),
    "Form1f": ("Form 1, Wisconsin Income Tax (fillable)", "return_form", 4),
    "Form1": ("Form 1, Wisconsin Income Tax", "return_form", 5),
    "ScheduleAD": ("Schedule AD, Additions to Income", "schedule", 2),
    "ScheduleADf": ("Schedule AD, Additions to Income (fillable)", "schedule", 2),
    "ScheduleAD-Inst": ("Schedule AD Instructions, Additions to Income", "instructions", 7),
    "ScheduleH": ("Schedule H, Wisconsin Homestead Credit", "claim_form", 4),
    "ScheduleH-Inst": ("Schedule H and H-EZ Instructions, Wisconsin Homestead Credit", "instructions", 26),
    "ScheduleSB": ("Schedule SB, Subtractions from Income", "schedule", 3),
    "ScheduleSBf": ("Schedule SB, Subtractions from Income (fillable)", "schedule", 3),
    "ScheduleSB-Inst": ("Schedule SB Instructions, Subtractions from Income", "instructions", 18),
    "ScheduleWDf": ("Schedule WD, Capital Gains and Losses (fillable)", "schedule", 2),
    "ScheduleWD-Inst": ("Schedule WD Instructions, Capital Gains and Losses", "instructions", 3),
    "ScheduleWI-2441-Inst": ("Schedule WI-2441 Instructions, Additional Child and Dependent Care Credit", "instructions", 5),
}
# EXTRACT-MANIFEST rows held by a scope already (sha256 of the 2026-10-06 download equals the held source).
EM_HELD = {
    "us-or/form/tax_forms/oregon.gov/dor/forms/formspubs/form-or-40-inst_101-040-1_2025",
    "us-sc/form/individual_income_tax_forms/dor.sc.gov/sites/dor/files/forms/sc1040_2025",
    "us-sc/form/individual_income_tax_forms/dor.sc.gov/sites/dor/files/forms/sc1040instr_2025",
    "us-va/form/tax_forms/tax.virginia.gov/sites/default/files/vatax-pdf/2025-760-instructions",
    "us-wi/form/individual-income-tax/2025/schedule-sb-instructions",
    "us-wi/form/tax_forms/revenue.wi.gov/taxforms2025/2025-form1",
    "us-wi/form/tax_forms/revenue.wi.gov/taxforms2025/2025-form1-inst",
    "us-wi/form/tax_forms/revenue.wi.gov/taxforms2025/2025-schedulesb-inst/taxforms2025-2025-schedulesb-inst-1e6e63914c",
    "us-wv/form/individual_income_tax_forms/tax.wv.gov/documents/pit/2025/it140.personalincometaxformsandinstructions.2025",
}


def slug_path(path: str) -> str:
    from axiom_corpus.corpus.citation_segment import citation_segment

    head = path.split("/")[:2]
    return "/".join(head + [citation_segment(s) for s in path.split("/")[2:]])


def em_documents(work_order: Path | None) -> None:
    """Add the EXTRACT-MANIFEST documents from the manifests on main."""
    wanted: set[str] | None = None
    if work_order is not None:
        with work_order.open() as handle:
            wanted = {r["id"] for r in csv.DictReader(handle) if r["action"] == "EXTRACT-MANIFEST"}
    for manifest in EM_MANIFESTS:
        data = yaml.safe_load((REPO / manifest).read_text())
        for entry in data["documents"]:
            path = entry.get("citation_path") or ""
            if path in EM_HELD or (wanted is not None and path not in wanted):
                continue
            leaf = path.split("/")[-1]
            facts = EM_FACTS.get(leaf)
            if facts is None and path.startswith("us-wi/"):
                m = re.search(r"TaxForms(\d{4})/\d{4}-([^/]+)\.pdf$", entry["source_url"], re.I)
                if not m:
                    continue
                year, stem = m.group(1), m.group(2)
                key = next((k for k in WI_EM_FACTS if k.lower() == stem.lower()), None)
                if key is None:
                    continue
                title, subtype, pages = WI_EM_FACTS[key]
                facts = (f"{year} {title}", year, subtype, None)
            if facts is None:
                continue
            title, year, subtype, pages = facts
            D.append(
                {
                    "url": entry["source_url"],
                    "path": slug_path(path),
                    "title": title,
                    "year": year,
                    "subtype": subtype,
                    "pages": pages,
                    "closes": [path],
                    "fmt": "pdf",
                    "selector": None,
                    "jur": entry["jurisdiction"],
                    "cls": "form",
                    "authority": AUTHORITY[entry["jurisdiction"]],
                    "note": f"EXTRACT-MANIFEST: {manifest} entry {entry['source_id']} (path slugged to the citation-path grammar)",
                    "em_source_id": entry["source_id"],
                }
            )


# ---------------------------------------------------------------------------
# Adapter-driven statute scopes (manifests/state-income-tax-chapters-w6-tax-ok-wv.yaml).
# ---------------------------------------------------------------------------

ADAPTER_SCOPES = [
    {
        "source_id": "us-or-ors-chapter-315",
        "jurisdiction": "us-or",
        "adapter": "oregon-ors",
        "source_url": "https://www.oregonlegislature.gov/bills_laws/ors/ors315.html",
        "options": {"source_year": 2025, "only_chapter": "315", "workers": 1},
        "authority": "Oregon State Legislature",
        "note": "ORS chapter 315 (Personal and Corporation Income Tax Credits), 2025 Edition, from the official Legislature HTML.",
        "closes": {
            "https://www.oregonlegislature.gov/bills_laws/ors/ors315.html": "us-or/statute/chapter-315",
            "https://oregon.public.law/statutes/ors_315.264": "us-or/statute/315.264",
            "https://oregon.public.law/statutes/ors_315.273": "us-or/statute/315.273",
            "https://oregon.public.law/statutes/ors_315.643": "us-or/statute/315.643",
        },
    },
    {
        "source_id": "us-sc-code-title-59-chapter-2",
        "jurisdiction": "us-sc",
        "adapter": "south-carolina-code",
        "source_url": "https://www.scstatehouse.gov/code/t59c002.php",
        "options": {"only_title": "59", "only_chapter": "2", "request_delay_seconds": 0.3},
        "authority": "South Carolina Legislative Council",
        "note": "S.C. Code Title 59 Chapter 2 (Tuition prepayment and college savings; 529 deduction) from the official Code of Laws HTML.",
        "closes": {"https://www.scstatehouse.gov/code/t59c002.php": "us-sc/statute/title-59/chapter-2"},
    },
]


def manifest_entry(d: dict[str, Any]) -> dict[str, Any]:
    source_id = d.get("em_source_id") or re.sub(r"[^a-z0-9]+", "-", d["path"].lower()).strip("-")
    extraction: dict[str, Any]
    if d["fmt"] == "pdf":
        extraction = dict(SINGLE_BLOCK)
    else:
        extraction = {"html_content_selector": d["selector"] or HTML_SELECTOR.get(_host(d["url"]), "body")}
        if d.get("text_selector"):
            extraction["html_text_selector"] = d["text_selector"]
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": d["authority"],
        "document_subtype": d["subtype"],
        "program": "individual_income_tax",
        "source_family": "w6-tax-ok-wv-2026-10-06",
        "discovered_via": "program-bundle-gaps-2026-10-06 wave6/tax-ok-wv.csv (bundle_url read 2026-10-06)",
    }
    if d["year"]:
        metadata["tax_year"] = d["year"]
    if d["pages"]:
        metadata["page_count_at_research"] = d["pages"]
    if d.get("note"):
        metadata["source_note"] = d["note"]
    entry: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": d["jur"],
        "document_class": d["cls"],
        "title": d["title"],
        "source_url": d["url"],
        **({"download_url": d["download"]} if d.get("download") else {}),
        "source_format": d["fmt"],
        "source_as_of": SOURCE_AS_OF,
        "citation_path": d["path"],
        "extraction": extraction,
        "metadata": metadata,
    }
    if d["year"] and d["cls"] == "form":
        entry["expression_date"] = f"{d['year']}-01-01"
    return entry


def version_for(jur: str, cls: str) -> str:
    return f"{VERSION_PREFIX}-{FAMILY[cls]}-{jur.split('-')[1]}"


def manifest_path_for(jur: str, cls: str) -> Path:
    return REPO / "manifests" / f"{jur}-income-tax-w6-{FAMILY[cls]}.yaml"


def write_manifests() -> list[tuple[str, str, Path]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for d in D:
        groups.setdefault((d["jur"], d["cls"]), []).append(d)
    written = []
    for (jur, cls), docs in sorted(groups.items()):
        paths = [d["path"] for d in docs]
        if len(paths) != len(set(paths)):
            raise SystemExit(f"duplicate citation paths in {jur}/{cls}")
        body = {
            "version": version_for(jur, cls),
            "documents": [manifest_entry(d) for d in docs],
        }
        out = manifest_path_for(jur, cls)
        header = (
            f"# Wave 6 tax-ok-wv ({SOURCE_AS_OF}): {jur} {cls} documents named by the program bundles.\n"
            "# Generated by scripts/build_w6_tax_ok_wv_manifests.py; run note docs/ingest-runs/2026-10-06-w6-tax-ok-wv.md.\n"
        )
        out.write_text(header + yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=120))
        written.append((jur, cls, out))
    adapter = {
        "version": f"{VERSION_PREFIX}-statute",
        "sources": [
            {
                "source_id": s["source_id"],
                "jurisdiction": s["jurisdiction"],
                "document_class": "statute",
                "adapter": s["adapter"],
                "source_url": s["source_url"],
                "version": f"{VERSION_PREFIX}-statute-{s['jurisdiction'].split('-')[1]}",
                "options": {
                    "source_as_of": SOURCE_AS_OF,
                    "expression_date": SOURCE_AS_OF,
                    "download_dir": f"/Users/pavelmakarchuk/axiom-corpus/data/corpus/downloads/{s['jurisdiction']}-w6-tax-ok-wv/{SOURCE_AS_OF}",
                    **s["options"],
                },
                "metadata": {"source_authority": s["authority"], "source_scope_note": s["note"]},
            }
            for s in ADAPTER_SCOPES
        ],
    }
    (REPO / "manifests" / "state-income-tax-chapters-w6-tax-ok-wv.yaml").write_text(
        "# Wave 6 tax-ok-wv: whole statute chapters taken through the state adapters (the adapter appends its scope suffix).\n"
        + yaml.safe_dump(adapter, sort_keys=False, allow_unicode=True, width=120)
    )
    return written


# ---------------------------------------------------------------------------
# Decisions for rows not closed by a new document.
# (status, scope "jur/class/version", citation_path, official_url, note)
# ---------------------------------------------------------------------------

H = "ALREADY-HELD"
DECISIONS: dict[str, tuple[str, str, str, str, str]] = {}


def decide(row_id: str, status: str, scope: str = "", path: str = "", url: str = "", note: str = "") -> None:
    DECISIONS[row_id] = (status, scope, path, url, note)


# Held by sha256-identical sources (EXTRACT-MANIFEST rows).
_W5 = "2026-09-15-income-tax-forms-ty2025"
decide("us-or/form/tax_forms/oregon.gov/dor/forms/formspubs/form-or-40-inst_101-040-1_2025", H, f"us-or/form/{_W5}", "us-or/form/dor/ty2025/form-or-40-instructions", "https://oregon.gov/dor/forms/FormsPubs/form-or-40-inst_101-040-1_2025.pdf", "wave-5 TY2025 forms scope (PR #716, unsigned); 2026-10-06 download sha256-identical to the held source")
decide("us-sc/form/individual_income_tax_forms/dor.sc.gov/sites/dor/files/forms/sc1040_2025", H, f"us-sc/form/{_W5}", "us-sc/form/dor/ty2025/sc1040", "https://dor.sc.gov/sites/dor/files/forms/SC1040_2025.pdf", "wave-5 TY2025 forms scope; sha256-identical")
decide("us-sc/form/individual_income_tax_forms/dor.sc.gov/sites/dor/files/forms/sc1040instr_2025", H, f"us-sc/form/{_W5}", "us-sc/form/dor/ty2025/sc1040-instructions", "https://dor.sc.gov/sites/dor/files/forms/SC1040Instr_2025.pdf", "wave-5 TY2025 forms scope; sha256-identical")
decide("us-va/form/tax_forms/tax.virginia.gov/sites/default/files/vatax-pdf/2025-760-instructions", H, f"us-va/form/{_W5}", "us-va/form/tax/ty2025/form-760-instructions", "https://tax.virginia.gov/sites/default/files/vatax-pdf/2025-760-instructions.pdf", "wave-5 TY2025 forms scope; sha256-identical")
decide("us-wi/form/individual-income-tax/2025/schedule-sb-instructions", H, "us-wi/form/2026-09-23-wi-schedule-sb-2025", "us-wi/form/individual-income-tax/2025/schedule-sb-instructions", "https://www.revenue.wi.gov/TaxForms2025/2025-ScheduleSB-Inst.pdf", "locked scope on main (manifests/us-wi-2025-schedule-sb-instructions.yaml), not yet in a release")
decide("us-wi/form/tax_forms/revenue.wi.gov/taxforms2025/2025-schedulesb-inst/taxforms2025-2025-schedulesb-inst-1e6e63914c", H, "us-wi/form/2026-09-23-wi-schedule-sb-2025", "us-wi/form/individual-income-tax/2025/schedule-sb-instructions", "https://revenue.wi.gov/TaxForms2025/2025-ScheduleSB-inst.pdf", "same PDF as the held 2025 Schedule SB instructions (sha256-identical; URL differs only in case)")
decide("us-wi/form/tax_forms/revenue.wi.gov/taxforms2025/2025-form1", H, f"us-wi/form/{_W5}", "us-wi/form/dor/ty2025/form-1", "https://revenue.wi.gov/TaxForms2025/2025-Form1.pdf", "wave-5 TY2025 forms scope; sha256-identical")
decide("us-wi/form/tax_forms/revenue.wi.gov/taxforms2025/2025-form1-inst", H, f"us-wi/form/{_W5}", "us-wi/form/dor/ty2025/form-1-instructions", "https://revenue.wi.gov/TaxForms2025/2025-Form1-inst.pdf", "wave-5 TY2025 forms scope; sha256-identical")
decide("us-wv/form/individual_income_tax_forms/tax.wv.gov/documents/pit/2025/it140.personalincometaxformsandinstructions.2025", H, f"us-wv/form/{_W5}", "us-wv/form/tax/ty2025/it-140-forms-and-instructions", "https://tax.wv.gov/Documents/PIT/2025/it140.PersonalIncomeTaxFormsAndInstructions.2025.pdf", "wave-5 TY2025 forms scope; sha256-identical")

# Oklahoma
decide("https://www.oklegislature.gov/OK_Statutes/CompleteTitles/os68.pdf", H, "us-ok/statute/2026-07-16-pit-central-us-ok-title-68-r2026-07-24-immutable", "us-ok/statute/title-68", "https://www.oklegislature.gov/OK_Statutes/CompleteTitles/os68.pdf", "Title 68 (Revenue and Taxation) is held whole (1,840 sections) from the same publisher's complete-title RTF edition; the PDF (1,566 pages) is the same title")
for _cid in ("92565", "92568"):
    decide(f"https://www.oscn.net/applications/oscn/DeliverDocument.asp?CiteID={_cid}", "OUTREACH", "", "", f"https://www.oscn.net/applications/oscn/DeliverDocument.asp?CiteID={_cid}", "OSCN (Oklahoma Supreme Court, official) answers HTTP 201 with a Cloudflare Turnstile challenge page (2,304 bytes) to the corpus client; not worked around. PolicyEngine cites it as Oklahoma Statutes for the income-tax rates; 68 O.S. 2355 is held in us-ok/statute/2026-07-16-pit-central-us-ok-title-68-r2026-07-24-immutable")
decide("https://www.law.cornell.edu/regulations/oklahoma/OAC-710-50-15-49", H, "us-ok/regulation/2026-09-14-income-tax-regulations", "us-ok/regulation/oac/710/50/710-50-15-49", "https://rules.ok.gov/home", "mirror; the official OAC 710:50-15-49 is held from the Office of Administrative Rules API")

# Oregon
decide("https://secure.sos.state.or.us/oard/viewSingleRule.action?ruleVrsnRsn=238290", H, "us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated", "us-or/regulation/chapter-150/division-316/rule-150-316-0225", "https://secure.sos.state.or.us/oard/viewSingleRule.action?ruleVrsnRsn=238290", "OAR 150-316-0225 held in the consolidated OAR 150-316 scope (same rule version URL in its inventory)")
decide("https://www.oregonlegislature.gov/bills_laws/ors/ors316.html", H, "us-or/statute/2026-07-16-pit-west-us-or-chapter-316", "us-or/statute/chapter-316", "https://www.oregonlegislature.gov/bills_laws/ors/ors316.html", "ORS chapter 316 held whole")
decide("https://oregon.public.law/statutes/ors_316.157", H, "us-or/statute/2026-07-16-pit-west-us-or-chapter-316", "us-or/statute/316.157", "https://www.oregonlegislature.gov/bills_laws/ors/ors316.html", "mirror; ORS 316.157 held from the Legislature's chapter 316 page")
decide("https://olis.oregonlegislature.gov/liz/2026R1/Downloads/MeasureDocument/SB1507/Enrolled", H, "us-or/statute/2026-07-24-or-pit-session-laws", "us-or/statute/session-laws/2026/sb1507", "https://www.oregonlegislature.gov/bills_laws/lawsstatutes/2026orLaw0142.pdf", "the enrolled SB 1507 (2026) is held as the chaptered Oregon Laws 2026, chapter 142; OLIS answered this run (HTTP 200, 44 pages)")

# Pennsylvania
decide("https://www.legis.state.pa.us/WU01/LI/LI/US/PDF/1971/0/0002..PDF", H, "us-pa/statute/2026-07-16-pit-west-us-pa-act-1971-2-article-3", "us-pa/statute/act-1971-2", "https://www.legis.state.pa.us/WU01/LI/LI/US/PDF/1971/0/0002..PDF", "Tax Reform Code of 1971 (Act 2): the personal income tax article (Article III) is held from the same publisher's unconsolidated-statutes HTML edition; the PDF is the whole act (634 pages, all taxes)")
decide("https://www.pa.gov/agencies/revenue/forms-and-publications/", "OUT-OF-SCOPE", "", "", "https://www.pa.gov/agencies/revenue/forms-and-publications", "forms index page of the Department of Revenue (882 characters of links); not a source of rules; the forms it lists are taken individually")
for _aid in ("1470/", "2208/~/what-is-the-limit-on-a-deduction-to-a-529-plan", "274/~/taxability-of-roth-iras-according-to-pa-income-tax-rules"):
    decide(f"https://revenue-pa.custhelp.com/app/answers/detail/a_id/{_aid}", "OUTREACH", "", "", f"https://revenue-pa.custhelp.com/app/answers/detail/a_id/{_aid}", "Department of Revenue answer center (Oracle custhelp) answers HTTP 403 (3,988 bytes) to the corpus client on 2026-10-06 (second refusal; the 2026-10-06 check was the first); no documented fallback; not worked around")

# Rhode Island
for _u, _p in (
    ("https://webserver.rilegislature.gov/Statutes/TITLE44/44-30/44-I/44-30-2.6.htm", "us-ri/statute/44-30-2.6"),
    ("https://webserver.rilegislature.gov/Statutes/TITLE44/44-30/44-II/44-30-12.htm", "us-ri/statute/44-30-12"),
    ("http://webserver.rilin.state.ri.us/Statutes/TITLE44/44-30/44-30-2.6.HTM", "us-ri/statute/44-30-2.6"),
    ("http://webserver.rilin.state.ri.us/Statutes/title44/44-30/44-30-12.HTM", "us-ri/statute/44-30-12"),
    ("https://law.justia.com/codes/rhode-island/2022/title-44/chapter-44-30/part-i/section-44-30-2-6/", "us-ri/statute/44-30-2.6"),
    ("https://law.justia.com/codes/rhode-island/title-44/chapter-44-30/part-i/section-44-30-2-6/", "us-ri/statute/44-30-2.6"),
):
    decide(_u, H, "us-ri/statute/2026-07-16-pit-west-us-ri-chapter-44-30", _p, "https://webserver.rilegislature.gov/Statutes/TITLE44/44-30/INDEX.htm", "section held in the chapter 44-30 scope (current text); the rilin.state.ri.us host redirects to the statutes index, Justia is a mirror")

# South Carolina
decide("https://www.scstatehouse.gov/code/t12c006.php", H, "us-sc/statute/2026-07-24-sc-act110-us-sc-title-12-chapter-6", "us-sc/statute/title-12/chapter-6", "https://www.scstatehouse.gov/code/t12c006.php", "S.C. Code Title 12 Chapter 6 held whole")
decide("https://dor.sc.gov/forms-site/Forms/SC1040ES_2023.pdf", "ABSENT", "", "", "https://dor.sc.gov/sites/dor/files/forms/SC1040ES_2023.pdf", "404 at the forms-site address and at the sites/dor/files/forms address the publisher now uses for its other forms (2026-10-06); the 2026 SC1040ES is held in us-sc/form/2026-09-14-ty2026-indexed-amounts")
decide("https://dor.sc.gov/rebate-2022", "ABSENT", "", "", "https://dor.sc.gov/rebate-2022", "404 (2026-10-06), and dor.sc.gov/rebate 404; the 2022 rebate page is no longer published; the law is the 2022 bill 1087 taken in us-sc/statute")

# Texas
decide("https://www.sidley.com/en/insights/newsupdates/2024/12/us-district-court-vacates-dol-final-rule-on-flsa-overtime-exemptions", "OUT-OF-SCOPE", "", "", "https://www.sidley.com/en/insights/newsupdates/2024/12/us-district-court-vacates-dol-final-rule-on-flsa-overtime-exemptions", "law-firm news update (third-party analysis) on a federal court ruling about the DOL overtime rule; not a Texas tax source")

# Utah
_UT = "us-ut/statute/2026-09-14-income-tax-chapter-title-59"
decide("https://tax.utah.gov/forms/current/tc-40.pdf", H, "us-ut/form/2026-09-10-tax-state-forms-ty2025", "us-ut/form/ustc/ty2025/tc-40", "https://files.tax.utah.gov/tax/forms/current/tc-40.pdf", "current edition is TY2025, held")
decide("https://tax.utah.gov/forms/current/tc-40inst.pdf", H, "us-ut/form/2026-09-10-tax-state-forms-ty2025", "us-ut/form/ustc/ty2025/tc-40-instructions", "https://files.tax.utah.gov/tax/forms/current/tc-40inst.pdf", "current edition is TY2025, held")
decide("https://files.tax.utah.gov/tax/forms/2025/tc-40inst.pdf", H, "us-ut/form/2026-09-10-tax-state-forms-ty2025", "us-ut/form/ustc/ty2025/tc-40-instructions", "https://files.tax.utah.gov/tax/forms/2025/tc-40inst.pdf", "sha256-identical to the held TY2025 instructions")
decide("https://law.justia.com/codes/utah/2022/title-59/chapter-10/part-10/section-1044/", H, _UT, "us-ut/statute/59-10-1044", "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1044.html", "mirror (2022 edition); Utah Code 59-10-1044 held (current text)")
_ut_sec = re.compile(r"59-10-S([0-9.]+)\.html|C59-10-S([0-9.]+)_")
for _u in (
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1005.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1018.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1018.html?v=C59-10-S1018_2023050320230503",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1019.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1019.html?v=C59-10-S1019_2022032320220323",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S104.1.html?v=C59-10-S104.1_1800010118000101",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S104.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S104.html?v=C59-10-S104_2022050420220504",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S104.html?v=C59-10-S104_2024010120240501",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1042.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1042.html?v=C59-10-S1042_2023050320230503",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1043.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1044.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1044.html?v=C59-10-S1044_2022050420220504",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1047.html",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1047.html?v=C59-10-S1047_2023050320240101",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S1047.html?v=C59-10-S1047_2025010120240501",
    "https://le.utah.gov/xcode/Title59/Chapter10/59-10-S114.html?v=C59-10-S114_2022032320220323",
    "https://le.utah.gov/xcode/historical.html?date=1/1/2014&oc=/xcode/Title59/Chapter10/C59-10-S104_1800010118000101.html",
    "https://le.utah.gov/xcode/historical.html?date=2/7/2025&oc=/xcode/Title59/Chapter10/C59-10-S1018_2018051620180721.html",
    "https://le.utah.gov/xcode/historical.html?date=2/7/2025&oc=/xcode/Title59/Chapter10/C59-10-S1018_2021050520210505.html",
    "https://le.utah.gov/xcode/historical.html?date=5/8/2018&oc=/xcode/Title59/Chapter10/C59-10-S104_2018050820180508.html",
    "https://le.utah.gov/xcode/historical.html?date=8/17/2022&oc=/xcode/Title59/Chapter10/C59-10-S104_2022050420220504.html",
):
    _m = _ut_sec.search(_u)
    _sec = _m.group(1) or _m.group(2)
    _versioned = "?v=" in _u or "historical" in _u
    if _versioned:
        continue
    decide(
        _u,
        H,
        _UT,
        f"us-ut/statute/59-10-{_sec}",
        _u,
        "Utah Code section held (current text, wave-4 Title 59 scope); le.utah.gov answers with the committed Sectigo OV R36 intermediate (the check's URLError was the missing chain)"
        + ("; this address names a prior version, which the publisher renders only through JavaScript (body empty to a plain fetch) and is not held separately" if _versioned else ""),
    )

# Virginia
_VA = "us-va/statute/2026-09-14-income-tax-chapter"
decide("https://law.lis.virginia.gov/vacode/title58.1/section58.1-322.03/", H, _VA, "us-va/statute/58.1/58.1-322.03", "https://law.lis.virginia.gov/vacode/title58.1/section58.1-322.03/", "Code of Virginia chapter 3 held per section")
decide("https://law.lis.virginia.gov/vacodefull/title58.1/chapter3/article2/", H, _VA, "us-va/statute/58.1/58.1-320", "https://law.lis.virginia.gov/vacodefull/title58.1/chapter3/article2/", "Article 2 (Individual Income Tax, 58.1-320 et seq.) of chapter 3 is held section by section in the chapter 3 scope (no article container row)")
decide("https://law.lis.virginia.gov/vacodeupdates/title58.1/section58.1-339.8/", H, _VA, "us-va/statute/58.1/58.1-339.8", "https://law.lis.virginia.gov/vacodeupdates/title58.1/section58.1-339.8/", "section held (current text); this is the publisher's 2026 updates page for the section")
decide("https://legiscan.com/VA/text/HB1600/id/3262750/Virginia-2025-HB1600-Chaptered.pdf", "SKIPPED", "", "", "https://budget.lis.virginia.gov/bill/2025/1/HB1600/Chapter/", "mirror of the 2025 Appropriation Act (HB1600, Chapter 725); the official budget site renders items through JavaScript and the rebate item address was not resolved in the time box")

# Vermont
_VT = "us-vt/statute/2026-07-16-pit-central-us-vt-title-32-chapter-151"
for _u, _s in (
    ("http://legislature.vermont.gov/statutes/section/32/151/05811", "5811"),
    ("https://legislature.vermont.gov/statutes/section/32/151/05811", "5811"),
    ("https://legislature.vermont.gov/statutes/section/32/151/05822", "5822"),
    ("https://legislature.vermont.gov/statutes/section/32/151/05828b", "5828b"),
    ("https://legislature.vermont.gov/statutes/section/32/151/05828c", "5828c"),
    ("https://legislature.vermont.gov/statutes/section/32/151/05830e", "5830e"),
    ("https://legislature.vermont.gov/statutes/section/32/151/05830f", "5830f"),
    ("https://law.justia.com/codes/vermont/2020/title-32/chapter-151/section-5828c/", "5828c"),
    ("https://law.justia.com/codes/vermont/2021/title-32/chapter-151/section-5822/", "5822"),
    ("https://law.justia.com/codes/vermont/2021/title-32/chapter-151/section-5828c/", "5828c"),
    ("https://law.justia.com/codes/vermont/2022/title-32/chapter-151/section-5822/", "5822"),
    ("https://law.justia.com/codes/vermont/2022/title-32/chapter-151/section-5828c/", "5828c"),
):
    decide(_u, H, _VT, f"us-vt/statute/32-{_s}", f"https://legislature.vermont.gov/statutes/section/32/151/0{_s}", "32 V.S.A. chapter 151 section held (current text)" + ("; Justia is a mirror of a prior edition" if "justia" in _u else ""))
decide("https://legislature.vermont.gov/bill/status/2026/S.51", "OUT-OF-SCOPE", "", "", "https://legislature.vermont.gov/bill/status/2026/S.51", "bill status record (actions and dates), not a source of rules; the S.51 text as passed (Act 71) is taken in us-vt/statute")
for _u in ("https://tax.vermont.gov/document/2022-property-tax-credit-calculator", "https://tax.vermont.gov/document/2025-renter-credit-website-calculator", "https://tax.vermont.gov/sites/tax/files/documents/2024%20Renter%20Credit%20Website%20Calculator.xlsx"):
    decide(_u, "OUT-OF-SCOPE", "", "", _u, "Department of Taxes calculator (spreadsheet or its download page), not a source of rules; the credit amounts page and 32 V.S.A. 6066 are taken")
decide("https://tax.vermont.gov/document/2023-renter-credit-website-calculator", "OUT-OF-SCOPE", "", "", "https://tax.vermont.gov/document/2023-renter-credit-website-calculator", "calculator download page (404 on 2026-10-06); a calculator is not a source of rules")
decide("https://tax.vermont.gov/sites/tax/files/documents/renter_credit_2021.pdf", "OUT-OF-SCOPE", "", "", "https://tax.vermont.gov/sites/tax/files/documents/renter_credit_2021.pdf", "statistical report (2021 renter credit recipients, average income and credit by county; 13 pages); a dataset, not a source of rules")
decide("https://vt529.org/benefits", "OUTREACH", "", "", "https://vt529.org/benefits", "VSAC's Vermont 529 site answers HTTP 403 (118 bytes) to the corpus client (2026-10-06, second refusal); not worked around")
decide("https://vtdigger.org/2025/06/25/gov-phil-scott-signs-13-5-million-tax-credit-package-benefiting-low-income-workers-families-retirees-and-veterans/", "OUT-OF-SCOPE", "", "", "https://vtdigger.org/2025/06/25/gov-phil-scott-signs-13-5-million-tax-credit-package-benefiting-low-income-workers-families-retirees-and-veterans/", "news article (third party, HTTP 403); the law it reports is S.51 (Act 71 of 2025), taken in us-vt/statute")

# Washington
for _s in ("040", "060", "080"):
    decide(f"https://app.leg.wa.gov/RCW/default.aspx?cite=82.87.{_s}", H, "us-wa/statute/2026-07-13-recovery", f"us-wa/statute/82/82.87/82.87.{_s}", f"https://app.leg.wa.gov/RCW/default.aspx?cite=82.87.{_s}", "RCW section held (same URL in the scope inventory)")
decide("https://lawfilesext.leg.wa.gov/law/WACArchive/2025/pdf/WAC%20388%20-478%20%20CHAPTER/WAC%20388%20-478%20-0015.pdf", H, "us-wa/regulation/2026-06-25-388-478", "us-wa/regulation/388/388-478/388-478-0015", "https://app.leg.wa.gov/WAC/default.aspx?cite=388-478-0015", "WAC 388-478-0015 held from the current WAC page; this address is the 2025 WAC archive PDF of the same section")

# Wisconsin
_WI = "us-wi/statute/2026-09-23-income-tax-subunits-chapter-71"
for _u, _p in (
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/i/05/22", "us-wi/statute/71.05/22"),
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/i/05/22/dt", "us-wi/statute/71.05/22/dt"),
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/i/05/6/b/43", "us-wi/statute/71.05/6/b/43"),
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/i/05/6/b/54", "us-wi/statute/71.05/6/b/54"),
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/i/05/6/b/54m/a", "us-wi/statute/71.05/6/b/54m/a"),
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/i/07/6/am/1", "us-wi/statute/71.07/6/am/1"),
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/i/07/9g", "us-wi/statute/71.07/9g"),
    ("https://docs.legis.wisconsin.gov/statutes/statutes/71/viii/54", "us-wi/statute/71.54"),
):
    decide(_u, H, _WI, _p, _u, "Wis. Stat. chapter 71 subunit held (locked scope on main, docs/ingest-runs/2026-09-23-wi-chapter-71-subunits.md)")

# West Virginia
decide("https://code.wvlegislature.gov/11-21/", H, "us-wv/statute/2026-07-16-pit-west-us-wv-chapter-11-article-21", "us-wv/statute/chapter-11/article-21", "https://code.wvlegislature.gov/11-21/", "W. Va. Code chapter 11 article 21 held whole")


# Row notes for work-order addresses that are not the publisher's own address of the document.
ROW_NOTES = {
    "https://www.google.com/url?sa=i&url=https%3A%2F%2Fsecure.dor.state.or.us%2FServices%2Fdraftforms%2Fapi%2Fdocument%2F6793%2Fdownload&psig=AOvVaw01yzy9QiRloWlbInbZcNG4&ust=1742309265624000&source=images&cd=vfe&opi=89978449&ved=0CAYQrpoMahcKEwjI16b4rZGMAxUAAAAAHQAAAAAQBA": "Google redirect to an Oregon DOR draft-forms API document (secure.dor.state.or.us/Services/draftforms/api/document/6793/download answers HTTP 500 on 2026-10-06); PolicyEngine cites it as the 2024 Schedule OR-WFHDC instructions, taken here as the final 2024 edition from the DOR forms library",
    "https://taxsim.nber.org/historical_state_tax_forms/OR/2021/schedule-or-wfhdc_101-195_2021.pdf": "third-party repost (NBER TAXSIM); the official 2021 Schedule OR-WFHDC is taken from the DOR forms library",
    "https://taxsim.nber.org/historical_state_tax_forms/VT/2021/IN-112-2021.pdf": "third-party repost (NBER TAXSIM); the official 2021 Schedule IN-112 is taken from the Department of Taxes",
    "https://www.taxformfinder.org/rhodeisland/form-1040h": "third-party form site; its RI-1040H page shows the current edition, taken here as the official 2025 Form RI-1040H",
    "https://www.taxformfinder.org/forms/2021/2021-utah-tc-40-full-packet.pdf": "third-party repost of the 2021 TC-40 forms and instructions packet; the official 2021 TC-40 Forms and Instructions is taken",
    "https://www.efile.com/wisconsin-tax-brackets-rates-and-forms/": "third-party summary of Wisconsin brackets; the Department of Revenue's Tax Rates page is taken",
}


def present_rows() -> dict[str, tuple[str, str, str, str, str]]:
    out: dict[str, tuple[str, str, str, str, str]] = {}
    for d in D:
        scope = f"{d['jur']}/{d['cls']}/{version_for(d['jur'], d['cls'])}"
        fetched = d.get("download") or d["url"]
        for row_id in d["closes"]:
            note = d["title"]
            if row_id in ROW_NOTES:
                note += f" ({ROW_NOTES[row_id]})"
            elif row_id != fetched:
                note += f" (same document as the work-order address; fetched {fetched})"
            out[row_id] = ("PRESENT", scope, d["path"], fetched, note)
    for s in ADAPTER_SCOPES:
        for row_id, path in s["closes"].items():
            note = s["note"]
            if row_id != s["source_url"]:
                note += " (official text of the mirror's section)"
            out[row_id] = ("PRESENT", f"{s['jurisdiction']}/statute/{VERSION_PREFIX}-statute-{s['jurisdiction'].split('-')[1]}{{adapter suffix}}", path, s["source_url"], note)
    return out


def write_decisions(work_order: Path, out: Path, scope_suffix: dict[str, str] | None = None) -> None:
    present = present_rows()
    rows = list(csv.DictReader(work_order.open()))
    fields = ["id", "jurisdiction", "programs", "action", "new_status", "scope_version", "citation_path", "official_url", "note"]
    counts: dict[str, int] = {}
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            rid = r["id"]
            if rid in present:
                status, scope, path, url, note = present[rid]
            elif rid in DECISIONS:
                status, scope, path, url, note = DECISIONS[rid]
            else:
                status, scope, path, url, note = ("SKIPPED", "", "", r["bundle_url"], "not reached in the time box")
            if scope_suffix and "{adapter suffix}" in scope:
                scope = scope.replace("{adapter suffix}", scope_suffix.get(r["jurisdiction"], ""))
            counts[status] = counts.get(status, 0) + 1
            writer.writerow(
                {
                    "id": rid,
                    "jurisdiction": r["jurisdiction"],
                    "programs": r["programs"],
                    "action": r["action"],
                    "new_status": status,
                    "scope_version": scope,
                    "citation_path": path,
                    "official_url": url,
                    "note": note,
                }
            )
    print(json.dumps(counts, sort_keys=True))


STATE_NAMES = {
    "us-ok": "Oklahoma", "us-or": "Oregon", "us-pa": "Pennsylvania", "us-ri": "Rhode Island",
    "us-sc": "South Carolina", "us-tx": "Texas", "us-ut": "Utah", "us-va": "Virginia",
    "us-vt": "Vermont", "us-wa": "Washington", "us-wi": "Wisconsin", "us-wv": "West Virginia",
}


def update_queue(base: Path, decisions: Path) -> None:
    """Add a ``w6_bundle_gap_scopes`` block to each state's main row of the tax queue.

    The block is inserted textually after the row's ``queue_status`` line (no re-dump of the
    queue file, so rows owned by other wave-6 groups are untouched); an existing block of
    this group is replaced.
    """
    queue = REPO / "manifests" / "tax-agent-queue.yaml"
    text = queue.read_text()
    status_counts: dict[str, dict[str, int]] = {}
    with decisions.open() as handle:
        for r in csv.DictReader(handle):
            status_counts.setdefault(r["jurisdiction"], {}).setdefault(r["new_status"], 0)
            status_counts[r["jurisdiction"]][r["new_status"]] += 1
    scopes: dict[str, list[dict[str, Any]]] = {}
    for prov in sorted(base.glob(f"provisions/us-*/*/{VERSION_PREFIX}-*.jsonl")):
        jur, cls = prov.parts[-3], prov.parts[-2]
        version = prov.stem
        if jur not in STATE_NAMES or not re.search(rf"-{jur.split('-')[1]}(-|$)", version.replace(VERSION_PREFIX, "")):
            continue
        rows = prov.read_text().count("\n")
        family = next((f for c, f in FAMILY.items() if c == cls), cls)
        manifest = manifest_path_for(jur, cls) if not version.endswith(("-chapter-315", "-chapter-2")) else REPO / "manifests" / "state-income-tax-chapters-w6-tax-ok-wv.yaml"
        scopes.setdefault(jur, []).append(
            {"jurisdiction": jur, "document_class": cls, "version": version, "family": family,
             "target_manifest": str(manifest.relative_to(REPO)), "rows": rows}
        )
    for jur, name in STATE_NAMES.items():
        block = {
            "w6_bundle_gap_scopes": {
                "run_note": "docs/ingest-runs/2026-10-06-w6-tax-ok-wv.md",
                "decisions": "docs/ingest-runs/2026-10-06-w6-tax-ok-wv-decisions.csv",
                "row_status_counts": dict(sorted(status_counts.get(jur, {}).items())),
                "scopes": scopes.get(jur, []),
            }
        }
        rendered = "".join("  " + line + "\n" for line in yaml.safe_dump(block, sort_keys=False, width=120).splitlines())
        header = f"- jurisdiction: {jur}\n  name: {name}\n"
        start = text.find(header)
        if start < 0:
            raise SystemExit(f"queue row not found: {jur}")
        status_line_end = text.index("\n", text.index("  queue_status:", start)) + 1
        existing = re.compile(r"  w6_bundle_gap_scopes:\n(?:    .*\n|  - .*\n)*")
        m = existing.match(text, status_line_end)
        if m:
            text = text[:status_line_end] + rendered + text[m.end():]
        else:
            text = text[:status_line_end] + rendered + text[status_line_end:]
    queue.write_text(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-order", type=Path, help="wave6/tax-ok-wv.csv (restricts EXTRACT-MANIFEST rows)")
    parser.add_argument("--decisions", action="store_true", help="also write the decisions CSV (needs --work-order)")
    parser.add_argument("--adapter-suffix", action="append", default=[], help="jur=suffix of an adapter scope version")
    parser.add_argument("--queue", type=Path, help="corpus base: add w6_bundle_gap_scopes rows to manifests/tax-agent-queue.yaml")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(REPO / "src"))
    em_documents(args.work_order)
    written = write_manifests()
    for jur, cls, path in written:
        print(f"{jur}\t{cls}\t{version_for(jur, cls)}\t{path.relative_to(REPO)}")
    if args.decisions:
        if args.work_order is None:
            parser.error("--decisions needs --work-order")
        suffix = dict(item.split("=", 1) for item in args.adapter_suffix)
        write_decisions(args.work_order, REPO / "docs" / "ingest-runs" / "2026-10-06-w6-tax-ok-wv-decisions.csv", suffix)
    if args.queue:
        update_queue(args.queue, REPO / "docs" / "ingest-runs" / "2026-10-06-w6-tax-ok-wv-decisions.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
