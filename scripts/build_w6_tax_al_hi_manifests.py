"""Wave-6 group ``tax-al-hi``: manifests and decisions for the program-bundle gaps of
2026-10-06 (state individual income tax, EITC and CTC documents, Alabama to Hawaii).

Work order: ``docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-al-hi.csv`` (399 rows;
the CSV lives on the bundle-gaps branch, pass ``--work-order``). Run note:
``docs/ingest-runs/2026-10-06-w6-tax-al-hi.md``.

Every URL below was fetched on 2026-10-06 with the corpus user agent (one request at a time
per host, TLS verified against certifi plus ``data/certs``) and read: the printed title, tax
year and revision of page 1 are recorded as ``first_page_first_line``. A document the bundle
cites under a third-party or viewer address is taken from the official publisher's own file
and the decisions row records that address as ``official_url``.

Modes:

* default: write one manifest per jurisdiction, class and family
  (``manifests/us-xx-income-tax-w6-<family>.yaml``), version
  ``2026-10-06-w6-<family>-<xx>``.
* ``--decisions``: write ``docs/ingest-runs/2026-10-06-w6-tax-al-hi-decisions.csv``, one row
  per work-order row, and check every PRESENT / ALREADY-HELD citation path against the
  provisions on disk (``AXIOM_CORPUS_BASE``) and the open-PR scopes named in ``OPEN_PR_SCOPES``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
CORPUS_BASE = Path(os.environ.get("AXIOM_CORPUS_BASE", str(ROOT / "data" / "corpus")))
SOURCE_AS_OF = "2026-10-06"
GROUP = "tax-al-hi"
RUN_NOTE = "docs/ingest-runs/2026-10-06-w6-tax-al-hi.md"
DECISIONS = ROOT / "docs" / "ingest-runs" / "2026-10-06-w6-tax-al-hi-decisions.csv"
DISCOVERED_VIA = "wave6:tax-al-hi work order (program-bundle gaps 2026-10-06)"
SINGLE_BLOCK = {"segmentation": "single_block"}
PAGES = {"page_citation_prefix": "page"}

FAMILIES = {
    # family -> (document_class, manifest suffix)
    "income-tax-forms": ("form", "forms"),
    "income-tax-guidance": ("guidance", "guidance"),
    "income-tax-legislation": ("statute", "legislation"),
}

AUTHORITY = {
    "ador": "Alabama Department of Revenue",
    "dfa": "Arkansas Department of Finance and Administration",
    "arkleg": "Arkansas General Assembly",
    "azdor": "Arizona Department of Revenue",
    "azleg": "Arizona State Legislature",
    "azgov": "Office of the Arizona Governor",
    "ftb": "California Franchise Tax Board",
    "cdor": "Colorado Department of Revenue",
    "cga-co": "Colorado General Assembly",
    "lcs": "Colorado Legislative Council Staff",
    "osa": "Colorado Office of the State Auditor",
    "olls": "Colorado Office of Legislative Legal Services",
    "drs": "Connecticut Department of Revenue Services",
    "cga": "Connecticut General Assembly",
    "otr": "District of Columbia Office of Tax and Revenue",
    "dccouncil": "Council of the District of Columbia",
    "dedor": "Delaware Division of Revenue",
    "legis-de": "Delaware General Assembly",
    "news-de": "State of Delaware",
    "treasurer-de": "Delaware Office of the State Treasurer",
    "gador": "Georgia Department of Revenue",
    "gagov": "Office of the Governor of Georgia",
    "dotax": "Hawaii Department of Taxation",
    "hileg": "Hawaii State Legislature",
}

STATE_FAMILY_SOURCE = {
    "al": "Alabama", "ar": "Arkansas", "az": "Arizona", "ca": "California", "co": "Colorado",
    "ct": "Connecticut", "dc": "District of Columbia", "de": "Delaware", "ga": "Georgia",
    "hi": "Hawaii",
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", value.lower()).strip("-")


# Work-order rows whose PDF text layer is set in fonts without a ToUnicode map (shifted glyph
# codes: "<RX\x03FDQQRW" for "You cannot"); measured on the first run as more than 7 percent
# control characters in the body. These are short forms (1 to 3 pages) and are OCRed with the
# local Tesseract CLI at 200 dpi (the PR #753 precedent for the D-40 2023 booklet).
FORCE_OCR_ROWS = {38, 43, 44, 46, 47, 48, 50, 54, 55, 57, 58, 61, 63, 65, 68, 69, 312}
# Booklets whose embedded form pages use the same fonts (pages with more than 3 percent
# control characters: AR 2015 10 of 56, AR 2016 14 of 52, AR 2018 11 of 52, DC 2021 11 of 104,
# DC 2024 41 of 96, GA 2021 6 of 60); the whole booklet is OCRed so those pages carry text.
FORCE_OCR_ROWS |= {84, 85, 71, 313, 314, 329}
OCR_NOTE = ("text layer uses fonts without a ToUnicode map (shifted glyph codes); body taken by OCR "
            "(tesseract, 200 dpi, force_ocr)")

DOCS: list[dict[str, Any]] = []


def doc(
    rows: list[int],
    st: str,
    family: str,
    tail: str,
    title: str,
    url: str,
    *,
    agency: str,
    fmt: str = "pdf",
    ty: str | None = None,
    subtype: str = "form",
    first: str = "",
    extraction: dict[str, Any] | None = None,
    expression_date: str | None = None,
    request: dict[str, Any] | None = None,
    citation_path: str | None = None,
    note: str | None = None,
    bundle_url: str | None = None,
) -> None:
    cls = FAMILIES[family][0]
    path = citation_path or f"us-{st}/{cls}/{tail}"
    if extraction is None:
        extraction = dict(SINGLE_BLOCK) if fmt == "pdf" else {}
    if FORCE_OCR_ROWS.intersection(rows):
        extraction = dict(extraction, force_ocr=True)
        note = OCR_NOTE if not note else f"{note}; {OCR_NOTE}"
    if expression_date is None:
        expression_date = f"{ty}-01-01" if ty and family == "income-tax-forms" else SOURCE_AS_OF
    entry: dict[str, Any] = {
        "rows": rows,
        "st": st,
        "family": family,
        "source_id": f"us-{st}-w6-{_slug(path.split('/', 2)[2])}",
        "jurisdiction": f"us-{st}",
        "document_class": cls,
        "title": title,
        "source_url": url,
        "source_format": fmt,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": expression_date,
        "citation_path": path,
        "extraction": extraction,
        "metadata": {
            "primary_source": True,
            "source_authority": AUTHORITY[agency],
            "document_subtype": subtype,
            "program": "individual_income_tax",
            "source_family": f"w6-{GROUP}-{family}",
            "discovered_via": DISCOVERED_VIA,
            "first_page_first_line": first,
        },
    }
    if ty:
        entry["metadata"]["tax_year"] = ty
    if request:
        entry["request"] = request
    if note:
        entry["metadata"]["note"] = note
    if bundle_url:
        entry["metadata"]["bundle_url"] = bundle_url
    DOCS.append(entry)


F, G, L = "income-tax-forms", "income-tax-guidance", "income-tax-legislation"

# ---------------------------------------------------------------- Alabama (ADOR)
AL = "https://www.revenue.alabama.gov/wp-content/uploads/"
AL_VIEW = "https://www.revenue.alabama.gov/ultraviewer/viewer/basic_viewer/index.html?form="
for rows, ty, tail, title, file, first in [
    ([2], "2021", "form-40", "Form 40, Alabama Individual Income Tax Return (2021)", "2022/06/21f40.pdf", "*21110140* $1,500 Single ... Form 40 2021"),
    ([3], "2021", "schedule-a-b-dc", "Schedules A, B and DC (Form 40), Alabama Itemized Deductions, Interest and Dividend Income, Donations and Contributions (2021)", "2022/06/21f40schabdc_blk.pdf", "*21000740* (Schedules B and DC are on back page) ATTACH TO FORM 40"),
    ([11], "2021", "form-40a-booklet", "Form 40A Booklet, Alabama Short Return Forms and Instructions (2021)", "2022/06/21f40abk.pdf", "Short Return Full-Year Residents Forms and Instructions 2021 Alabama Form 40A Booklet"),
    ([4], "2022", "form-40a-booklet", "Form 40A Booklet, Alabama Short Return Forms and Instructions (2022)", "2023/01/22f40abk.pdf", "Form 40A Booklet 2022 Short Return Full Year Residents Forms and Instructions"),
    ([5, 12], "2022", "form-40-booklet", "Form 40 Booklet, Alabama Long Return Forms and Instructions (2022)", "2023/01/22f40bk.pdf", "Form 40 Booklet Long Return Residents and Part-Year Residents Forms and Instructions 2022"),
    ([6], "2022", "schedule-a-b-dc", "Schedules A, B and DC (Form 40) (2022)", "2023/01/22f40schabdc_blk.pdf", "*22000740* (Schedules B and DC are on back page) ATTACH TO FORM 40"),
    ([7], "2022", "form-40", "Form 40, Alabama Individual Income Tax Return (2022)", "2023/02/22f40.pdf", "*22110140* $1,500 Single ... Form 40 2022"),
    ([21], "2023", "form-40", "Form 40, Alabama Individual Income Tax Return (2023)", "2024/01/23f40.pdf", "*23110140* $1,500 Single ... Form 40 2023"),
    ([8, 13], "2023", "form-40-booklet", "Form 40 Booklet, Alabama Long Return Forms and Instructions (2023)", "2024/01/23f40bk.pdf", "Form 40 Booklet Long Return Residents and Part-Year Residents Forms and Instructions 2023"),
    ([9], "2023", "schedule-a-b-dc", "Schedules A, B and DC (Form 40) (2023)", "2024/01/23f40schabdc_blk.pdf", "*23000740* (Schedules B and DC are on back page) ATTACH TO FORM 40"),
    ([14], "2023", "schedule-rs-instructions", "Schedule RS Line Instructions, Retirement Distributions Exempt from Alabama Income Tax (2023)", "2024/01/23schrsinstr.pdf", "Line Instructions for Completing Schedule RS Part I - Retirement Distribution(s) Exempt from Alabama Income"),
    ([10], "2024", "schedule-a-b-dc", "Schedules A, B and DC (Form 40) (2024)", "2025/01/24f40schabdc_blk.pdf", "*24000740* (Schedules B and DC are on back page) ATTACH TO FORM 40"),
    ([15], "2024", "form-40-booklet", "Form 40 Booklet, Alabama Long Return Forms and Instructions (2024)", "2025/01/24f40bk.pdf", "Form 40 Booklet Long Return Residents and Part-Year Residents Forms and Instructions 2024"),
]:
    doc(rows, "al", F, f"ador/ty{ty}/{tail}", title, AL + file, agency="ador", ty=ty,
        subtype="instructions" if "booklet" in tail or "instructions" in tail else "form", first=first)

# ---------------------------------------------------------------- Arkansas (DFA forms)
AR = "https://www.dfa.arkansas.gov/wp-content/uploads/"
for rows, ty, tail, title, file, first in [
    ([83], "2014", "long-booklet-with-tax-tables", "Arkansas 2014 Individual Income Tax Forms and Instructions, Long Booklet with Tax Tables", "LongBookwTaxTables_2014.pdf", "Arkansas 2014 Individual Income Tax Forms and Instructions Full Year Resident Part Year Resident Nonresident"),
    ([84], "2015", "long-booklet-with-tax-tables", "Arkansas 2015 Individual Income Tax Forms and Instructions, Long Booklet with Tax Tables", "LongBookwTaxTables_2015.pdf", "Arkansas 2015 Individual Income Tax Forms and Instructions"),
    ([85], "2016", "long-booklet-with-tax-tables", "Arkansas 2016 Individual Income Tax Forms and Instructions, Long Booklet with Tax Tables", "LongBookwTaxTables_2016.pdf", "Arkansas 2016 Individual Income Tax Forms and Instructions Long Booklet"),
    ([70], "2017", "ar1000f-ar1000nr-instructions", "Arkansas 2017 Individual Income Tax Forms and Instructions, Long Booklet (AR1000F and AR1000NR)", "AR1000FandAR1000NRInstructions.pdf", "Arkansas 2017 Individual Income Tax Forms and Instructions Long Booklet"),
    ([71], "2018", "ar1000f-ar1000nr-instructions", "Arkansas 2018 Individual Income Tax Forms and Instructions, Long Booklet (AR1000F and AR1000NR)", "AR1000FandAR1000NRInstructions_2018.pdf", "Arkansas 2018 Individual Income Tax Forms and Instructions Long Booklet"),
    ([41], "2019", "ar1000f-ar1000nr-instructions", "Arkansas 2019 Individual Income Tax Forms and Instructions (AR1000F and AR1000NR)", "2019_AR1000F_and_AR1000NR_Instructions.pdf", "Arkansas 2019 Individual Income Tax Forms and Instructions"),
    ([42], "2020", "ar1000f-ar1000nr-instructions", "Arkansas 2020 Individual Income Tax Forms and Instructions (AR1000F and AR1000NR)", "2020_AR1000F_and_AR1000NR_Instructions.pdf", "Arkansas 2020 Individual Income Tax Forms and Instructions"),
    ([45], "2021", "ar1000f-ar1000nr-instructions", "Arkansas 2021 Individual Income Tax Forms and Instructions (AR1000F and AR1000NR)", "2021_AR1000F_and_AR1000NR_Instructions.pdf", "Arkansas 2021 Individual Income Tax Forms and Instructions"),
    ([49], "2022", "ar1000f-ar1000nr-instructions", "Arkansas 2022 Individual Income Tax Forms and Instructions (AR1000F and AR1000NR)", "2022_AR1000F_and_AR1000NR_Instructions.pdf", "The Old Mill ... Arkansas 2022 Individual Income Tax"),
    ([56], "2023", "ar1000f-ar1000nr-instructions", "Arkansas 2023 Individual Income Tax Forms and Instructions (AR1000F and AR1000NR)", "2023_AR1000F_and_AR1000NR_Instructions.pdf", "Pedestal Rocks Scenic Area ... Arkansas 2023 Individual Income Tax"),
    ([62], "2024", "ar1000f-ar1000nr-instructions", "Arkansas 2024 Individual Income Tax Forms and Instructions (AR1000F and AR1000NR)", "2024_AR1000F_and_AR1000NR_Instructions.pdf", "Yancopin Bridge ... Arkansas 2024 Individual Income Tax"),
    ([44], "2021", "ar1000f", "AR1000F Arkansas Individual Income Tax Return, Full Year Resident (2021)", "2021_AR1000F_FullYearResidentIndividualIncomeTaxReturn.pdf", "AR1 Page AR1 (R 7/19/2021)"),
    ([48], "2022", "ar1000f", "AR1000F Arkansas Individual Income Tax Return, Full Year Resident (2022)", "2022_AR1000F_FullYearResidentIndividualIncomeTaxReturn.pdf", "AR1000F, Page 1 (R 7/21/2022) 2022 AR1000F ARKANSAS INDIVIDUAL INCOME TAX RETURN Full Year Resident"),
    ([55], "2023", "ar1000f", "AR1000F Arkansas Individual Income Tax Return, Full Year Resident (2023)", "2023_AR1000F_FullYearResidentIndividualIncomeTaxReturn.pdf", "AR1000F, Page 1 (R 7/3/2023) 2023 AR1000F ARKANSAS INDIVIDUAL INCOME TAX RETURN Full Year Resident"),
    ([43], "2021", "ar1000d", "AR1000D Arkansas Capital Gains and Losses (2021)", "2021_AR1000D_CapitalGains.pdf", "AR1000D (R 6/9/2021) 1. Enter federal long-term capital gain or loss"),
    ([47], "2022", "ar1000d", "AR1000D Arkansas Capital Gains and Losses (2022)", "2022_AR1000D_CapitalGains.pdf", "AR1000D (R 6/1/2022)"),
    ([54], "2023", "ar1000d", "AR1000D Arkansas Capital Gains and Losses (2023)", "2023_AR1000D_CapitalGains.pdf", "AR1000D (R 7/5/2023)"),
    ([61], "2024", "ar1000d", "AR1000D Arkansas Capital Gains and Losses (2024)", "2024_AR1000D_CapitalGains.pdf", "AR1000D (R 10/31/2024)"),
    ([68], "2025", "ar1000d", "AR1000D Arkansas Capital Gains and Losses (2025)", "2025_AR1000D_CapitalGains.pdf", "AR1000D (R 4/25/2025)"),
    ([46], "2021", "ar2441", "AR2441 Arkansas Child and Dependent Care Expenses (2021)", "2021_AR2441_Child_andDependentCareExpenses.pdf", "AR2441 CHILD AND DEPENDENT CARE EXPENSES 2021"),
    ([50], "2022", "ar2441", "AR2441 Arkansas Child and Dependent Care Expenses (2022)", "2022_AR2441_Child_andDependentCareExpenses.pdf", "2022 AR2441 CHILD AND DEPENDENT CARE EXPENSES"),
    ([58], "2023", "ar2441", "AR2441 Arkansas Child and Dependent Care Expenses (2023)", "2023_AR2441_Child_andDependentCareExpenses.pdf", "2023 AR2441 CHILD AND DEPENDENT CARE EXPENSES"),
    ([65], "2024", "ar2441", "AR2441 Arkansas Child and Dependent Care Expenses (2024)", "2024_AR2441_Child_andDependentCareExpenses.pdf", "2024 AR2441 CHILD AND DEPENDENT CARE EXPENSES"),
    ([80], "2011", "ar3", "AR3 Arkansas Itemized Deductions (2011)", "AR3_2011_FI.pdf", "AR3 (R 8/16/2011) MEDICAL AND DENTAL EXPENSES"),
    ([81], "2012", "ar3", "AR3 Arkansas Itemized Deductions (2012)", "AR3_2012_RE.pdf", "AR3 (R 11/7/12) MEDICAL AND DENTAL EXPENSES"),
    ([82], "2013", "ar3", "AR3 Arkansas Itemized Deductions (2013)", "AR3_2013_RE.pdf", "AR3 2013 (R 10/23/13) MEDICAL AND DENTAL EXPENSES"),
    ([51], "2022", "ar3", "AR3 Arkansas Itemized Deductions (2022)", "2022_AR3_ItemizedDeduction.pdf", "AR3 2022 (R 8/25/2022) MEDICAL AND DENTAL EXPENSES"),
    ([73], "2015", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2015)", "AR1075_2015_RE.pdf", "AR1075 2015 (R 7/21/15)"),
    ([74], "2016", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2016)", "AR1075_2016_RE.pdf", "AR1075 2016 (R 8/1/2016)"),
    ([72], "2017", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2017)", "AR1075DedforTuitionPaidtoPostSecEduInst.pdf", "AR1075 2017 (R 8/3/2017)"),
    ([37], "2018", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2018)", "2018_Final_AR1075_BC_FI.pdf", "AR1075 2018 (R 10/09/2018)"),
    ([75], "2019", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2019)", "AR1075_2019.pdf", "AR1075 2019 (R 8/12/2019)"),
    ([76], "2020", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2020)", "AR1075_2020.pdf", "AR1075 2020"),
    ([77], "2021", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2021)", "AR1075_2021.pdf", "AR1075 2021"),
    ([78], "2022", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2022)", "AR1075_2022.pdf", "AR1075 2022"),
    ([79], "2023", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2023)", "AR1075_2023.pdf", "AR1075 2023"),
    ([64], "2024", "ar1075", "AR1075 Deduction for Tuition Paid to Post-Secondary Educational Institutions (2024)", "2024_AR1075.pdf", "AR1075 2024 (R 7/24/2024)"),
    ([38], "2018", "ar4684", "AR4684 Arkansas Casualties and Thefts (2018)", "2018_Final_AR4684_BC_FI.pdf", "AR4684 (R 12/21/2018) AR4684 2018"),
    ([69], "2025", "ar4684", "AR4684 Arkansas Casualties and Thefts (2025)", "2025_AR4684_Casualties_and_Thefts.pdf", "AR4684 Pg 1 (R 4/28/2025) 2025 AR4684"),
    ([57], "2023", "ar1000tc-instructions", "AR1000TC Schedule of Tax Credits and Business Incentive Credits Instructions (2023)", "2023_AR1000TC_Schedule_of_TaxCredits_andBusiness_IncentiveCredits_Instructions.pdf", "LINE 1. A credit of up to $50.00 per taxpayer ($100.00 for a joint return)"),
    ([63], "2024", "ar1000tc-instructions", "AR1000TC Schedule of Tax Credits Instructions (2024)", "2024_AR1000TC_Instructions.pdf", "LINE 1. A credit of up to $50.00 per taxpayer ($100.00 for a joint return)"),
    ([52], "2022", "additional-tax-credit-for-qualified-individuals", "Additional Tax Credit for Qualified Individuals Worksheet (2022)", "2022_Final_AdditionalTaxCreditforQualifiedIndividuals_FI.pdf", "(R 8/30/2022) An individual taxpayer having a net income up to $25,400"),
    ([59], "2023", "additional-tax-credit-for-qualified-individuals", "Additional Tax Credit for Qualified Individuals Worksheet (2023)", "2023_Final_AdditionalTaxCreditforQualifiedIndividuals_FI.pdf", "(R 9/20/2023) An individual taxpayer having a net income up to $26,100"),
    ([66], "2024", "additional-tax-credit-for-qualified-individuals", "Additional Tax Credit for Qualified Individuals Worksheet (2024)", "2024_Final_AdditionalTaxCreditforQualifiedIndividuals_FI.pdf", "(R 10/7/2024) An individual taxpayer having a net income up to $26,900"),
    ([53], "2022", "inflationary-relief-income-tax-credit", "Inflationary Relief Income Tax Credit Worksheet (IRITCWS) (2022)", "2022_Final_InflationaryReliefIncomeTaxCredit_FI.pdf", "IRITCWS (R 1/10/2023) For the tax year beginning January 1, 2022"),
    ([60], "2023", "inflationary-relief-income-tax-credit", "Inflationary Relief Income Tax Credit Worksheet (IRITCWS) (2023)", "2023_Final_InflationaryReliefIncomeTaxCredit_FI.pdf", "IRITCWS (R 9/20/2023) For the tax year beginning January 1, 2023"),
    ([88], "2015", "tax-brackets", "Indexed Tax Brackets (2015)", "TaxBrackets_2015.pdf", "STATE OF ARKANSAS REVENUE DIVISION Individual Income Tax"),
    ([86], "2016", "tax-brackets", "Indexed Tax Brackets (2016)", "Tax%20Brackets_2016.pdf", "STATE OF ARKANSAS REVENUE DIVISION Individual Income Tax"),
    ([87], "2017", "tax-brackets", "Indexed Tax Brackets (2017)", "TaxBrackets2017.pdf", "STATE OF ARKANSAS REVENUE DIVISION Individual Income Tax"),
    ([40], "2018", "tax-brackets", "Indexed Tax Brackets (2018)", "2018_Tax_Brackets.pdf", "STATE OF ARKANSAS REVENUE DIVISION Individual Income Tax"),
    ([89], "2019", "tax-brackets", "Indexed Tax Brackets (2019)", "TaxBrackets_2019.pdf", "STATE OF ARKANSAS REVENUE DIVISION Individual Income Tax"),
    ([90], "2020", "tax-brackets", "Indexed Tax Brackets (2020)", "TaxBrackets_2020.pdf", "STATE OF ARKANSAS Department of Finance and Administration REVENUE DIVISION"),
    ([91], "2021", "tax-brackets", "Indexed Tax Brackets (2021)", "TaxBrackets_2021.pdf", "STATE OF ARKANSAS Department of Finance and Administration REVENUE DIVISION"),
    ([92], "2022", "tax-brackets", "Indexed Tax Brackets (2022)", "TaxBrackets_2022.pdf", "STATE OF ARKANSAS Department of Finance and Administration REVENUE DIVISION"),
    ([93], "2023", "tax-brackets", "Indexed Tax Brackets (2023)", "TaxBrackets_2023.pdf", "STATE OF ARKANSAS Department of Finance and Administration REVENUE DIVISION"),
    ([67], "2024", "tax-brackets", "Indexed Tax Brackets (2024)", "2024_TaxBrackets.pdf", "STATE OF ARKANSAS Department of Finance and Administration REVENUE DIVISION"),
    ([94], "2015", "tax-tables", "Tax Tables (2015)", "TaxTables_2015.pdf", "2015 TAX TABLES The two tax tables used for Individual Income Tax"),
    ([39], "2018", "tax-tables", "Tax Tables with Cover Sheet (2018)", "2018_Final_TaxTable_with_Cover_Sheet.pdf", "2018 TAX TABLES The two tax tables used for Individual Income Tax"),
    ([95], "2024", "tax-tables", "Tax Tables (2024)", "TaxTables_FI_2024.pdf", "2024 TAX TABLES The two tax tables used for Individual Income Tax"),
    ([96], "2025", "tax-tables", "Tax Tables (2025)", "TaxTables_FI_2025.pdf", "2025 TAX TABLES The two tax tables used for Individual Income Tax"),
]:
    doc(rows, "ar", F, f"dfa/ty{ty}/{tail}", title, AR + file, agency="dfa", ty=ty,
        subtype="instructions" if "instructions" in tail or "booklet" in tail else ("tax_table" if "tax-" in tail else "form"),
        first=first)

# ---------------------------------------------------------------- Arkansas (General Assembly)
ARK = "https://www.arkleg.state.ar.us/Acts/FTPDocument?path=%2FACTS%2F"
for rows, session, act, file, sess_q, first in [
    ([23], "1987R", "382", "382.pdf", "1987%2F1987R", 'Act 382 of the 1987 Regular Session HB2003 "INCOME TAX ACT OF 1987"'),
    ([24], "2009R", "372", "372.pdf", "2009%2F2009R", "Act 372 of the 2009 Regular Session"),
    ([25], "2011R", "787", "787.pdf", "2011%2F2011R", "Act 787 of the Regular Session"),
    ([26], "2013R", "1459", "1459.pdf", "2013%2F2013R", "Act 1459 of the Regular Session"),
    ([27], "2015R", "22", "22.pdf", "2015%2F2015R", "Act 22 of the Regular Session"),
    ([28], "2017R", "141", "141.pdf", "2017%2F2017R", "Act 141 of the Regular Session"),
    ([29], "2017R", "78", "78.pdf", "2017%2F2017R", "Act 78 of the Regular Session"),
    ([30], "2019R", "182", "182.pdf", "2019%2F2019R", "Act 182 of the Regular Session"),
    ([31], "2021R", "154", "154.pdf", "2021%2F2021R", "Act 154 of the Regular Session"),
    ([32], "2025R", "614", "614.pdf", "2025%2F2025R", "Act 614 of the Regular Session"),
]:
    url = f"{ARK}{session}%2FPublic%2F&file={file}&ddBienniumSession={sess_q}"
    doc(rows, "ar", L, f"session-laws/{session.lower()}/act-{act}",
        f"Arkansas Act {act} of the {session[:4]} {'Regular' if session.endswith('R') else 'Extraordinary'} Session",
        url, agency="arkleg", subtype="session_law", first=first)
doc([33], "ar", L, "session-laws/2023r/act-532", "Arkansas Act 532 of the 2023 Regular Session",
    "https://www.arkleg.state.ar.us/Home/FTPDocument?path=%2FACTS%2F2023R%2FPublic%2FACT532.pdf",
    agency="arkleg", subtype="session_law", first="Act 532 of the Regular Session")
doc([34], "ar", L, "session-laws/2026s1/act-1", "Arkansas Act 1 of the 2026 First Extraordinary Session (HB1001)",
    "https://www.arkleg.state.ar.us/Home/FTPDocument?path=%2FACTS%2F2026S1%2FPublic%2FACT1.pdf",
    agency="arkleg", subtype="session_law", first="Act 1 of the First Extraordinary Session")
doc([36], "ar", L, "bills/2026s1/hb1001", "Arkansas HB1001, 2026 First Extraordinary Session (bill text)",
    "https://www.arkleg.state.ar.us/Home/FTPDocument?path=%2FBills%2F2026S1%2FPublic%2FHB1001.pdf",
    agency="arkleg", subtype="bill", first="*JLL443* 05/01/2026 8:05:20 AM")
doc([22], "ar", G, "general-assembly/bill-information/2026s1-hb1001",
    "HB1001 Bill Information, Arkansas State Legislature (2025/2026 First Extraordinary Session)",
    "https://arkleg.state.ar.us/Bills/Detail?id=hb1001&ddBienniumSession=2025%2F2026S1",
    agency="arkleg", fmt="html", subtype="bill_information", first="HB1001 Bill Information - Arkansas State Legislature",
    extraction={"html_content_selector": "#content", "html_text_selector": "#content"})
doc([35], "ar", G, "dfa/legislative-impact-statements/2022s3-hb1002",
    "Department of Finance and Administration Legislative Impact Statement, HB1002 (2022 Third Extraordinary Session)",
    "https://www.arkleg.state.ar.us/Home/FTPDocument?path=%2FAssembly%2F2021%2F2022S3%2FFiscal+Impacts%2FHB1002-DFA1.pdf",
    agency="dfa", subtype="fiscal_impact_statement", first="Department of Finance and Administration Legislative Impact Statement Bill: HB1002")

# ---------------------------------------------------------------- Arizona (ADOR forms)
AZ = "https://azdor.gov/sites/default/files/"
for rows, ty, tail, title, file, first in [
    ([117], "2021", "form-140", "Arizona Form 140, Resident Personal Income Tax Return (2021)", "2023-03/FORMS_INDIVIDUAL_2021_140.pdf", "ADOR 10413 (21) AZ Form 140 (2021) Page 1 of 6"),
    ([118], "2021", "form-140-booklet", "Arizona Form 140 Resident Personal Income Tax Booklet (2021)", "2023-03/FORMS_INDIVIDUAL_2021_140BOOKLET.pdf", "Pay your taxes by credit card! ... (2021 booklet, 64 pages)"),
    ([119], "2021", "form-140-instructions", "Arizona Form 140 Resident Personal Income Tax Return Instructions (2021)", "2023-03/FORMS_INDIVIDUAL_2021_140i.pdf", "Arizona Form 2021 Resident Personal Income Tax Return 140"),
    ([120], "2021", "form-140-instructions-2d", "Arizona Form 140 Instructions, 2-D barcode edition (2021)", "2023-03/FORMS_INDIVIDUAL_2021_140i-2D.pdf", "Arizona Form 2021 Resident Personal Income Tax Return 140"),
    ([121], "2021", "form-140ptc", "Arizona Form 140PTC, Property Tax Refund (Credit) Claim (2021)", "2023-03/FORMS_INDIVIDUAL_2021_140PTC.pdf", "ADOR 10567 (21)"),
    ([142], "2021", "form-140ptc-fillable", "Arizona Form 140PTC, Property Tax Refund (Credit) Claim, fillable (2021)", "2023-09/FORMS_INDIVIDUAL_2021_140PTC-f.pdf", "ADOR 10567 (21)"),
    ([122], "2022", "form-140", "Arizona Form 140, Resident Personal Income Tax Return (2022)", "2023-03/FORMS_INDIVIDUAL_2022_140.pdf", "ADOR 10413 (22) AZ Form 140 (2022) Page 1 of 6"),
    ([127], "2022", "form-140-fillable", "Arizona Form 140, Resident Personal Income Tax Return, fillable (2022)", "2023-08/FORMS_INDIVIDUAL_2022_140f.pdf", "Your First Name and Middle Initial ... (Form 140 2022 fillable)"),
    ([123], "2022", "form-140-booklet", "Arizona Form 140 Resident Personal Income Tax Booklet (2022)", "2023-03/FORMS_INDIVIDUAL_2022_140BOOKLET.pdf", "Pay your taxes by credit card! ... (2022 booklet, 60 pages)"),
    ([124], "2022", "form-140-instructions", "Arizona Form 140 Resident Personal Income Tax Return Instructions (2022)", "2023-03/FORMS_INDIVIDUAL_2022_140i.pdf", "Arizona Form 2022 Resident Personal Income Tax Return 140"),
    ([125], "2022", "form-140-instructions-2d", "Arizona Form 140 Instructions, 2-D barcode edition (2022)", "2023-03/FORMS_INDIVIDUAL_2022_140i-2D.pdf", "Arizona Form 2022 Resident Personal Income Tax Return 140"),
    ([135], "2022", "form-140a-instructions", "Arizona Form 140A Resident Personal Income Tax Return (Short Form) Instructions (2022)", "2023-03/FORMS_INDIVIDUAL_2022_140Ai.pdf", "Arizona Form 2022 Resident Personal Income Tax Return (Short Form) 140A"),
    ([126], "2022", "form-140ptc", "Arizona Form 140PTC, Property Tax Refund (Credit) Claim (2022)", "2023-03/FORMS_INDIVIDUAL_2022_140PTC.pdf", "ADOR 10567 (22)"),
    ([140], "2022", "form-201", "Arizona Form 201, Renter's Certificate of Property Taxes Paid (2022)", "2023-03/FORMS_INDIVIDUAL_2022_201_f.pdf", "ADOR 10417 (22) Use Form 201 if you rented in 2022"),
    ([128], "2023", "form-140-instructions-sv", "Arizona Form 140 Resident Personal Income Tax Return Instructions (2023, FORMS_INDIVIDUAL_140-SVi)", "2023-10/FORMS_INDIVIDUAL_140-SVi.pdf", "Arizona Form 2023 Resident Personal Income Tax Return 140"),
    ([129], "2023", "form-140-booklet", "Arizona Form 140 Resident Personal Income Tax Booklet (2023)", "2023-12/FORMS_INDIVIDUAL_2023_140Booklet.pdf", "Pay your taxes by credit card! ... (2023 booklet, 56 pages)"),
    ([130], "2023", "form-140nr-booklet", "Arizona Form 140NR Nonresident Personal Income Tax Booklet (2023)", "2023-12/FORMS_INDIVIDUAL_2023_140NRBooklet.pdf", "Who must use Arizona Form 140NR? (2023 booklet)"),
    ([143], "2023", "form-140ptc-fillable", "Arizona Form 140PTC, Property Tax Refund (Credit) Claim, fillable (2023)", "2023-12/FORMS_INDIVIDUAL_2023_140PTC_f.pdf", "ADOR 10567 (23)"),
    ([131], "2024", "form-140-booklet", "Arizona Form 140 Resident Personal Income Tax Booklet (2024)", "document/FORMS_INDIVIDUAL_2024_140Booklet.pdf", "Pay your taxes by credit card! ... (2024 booklet, 56 pages)"),
    ([132], "2024", "form-140nr-booklet", "Arizona Form 140NR Nonresident Personal Income Tax Booklet (2024)", "document/FORMS_INDIVIDUAL_2024_140NRBooklet.pdf", "Who must use Arizona Form 140NR? (2024 booklet)"),
    ([144], "2024", "form-140ptc-fillable", "Arizona Form 140PTC, Property Tax Refund (Credit) Claim, fillable (2024)", "document/FORMS_INDIVIDUAL_2024_140PTC_f.pdf", "ADOR 10567 (24)"),
    ([134], "2020", "form-140nr-booklet", "Arizona Form 140NR Nonresident Personal Income Tax Booklet (2020)", "2023-03/FORMS_INDIVIDUAL_2020_140NRBOOKLET.pdf", "Who must use Arizona Form 140NR? (2020 booklet, 48 pages)"),
    ([145], "2025", "form-140ptc-fillable", "Arizona Form 140PTC, Property Tax Refund (Credit) Claim, fillable (2025)", "document/FORMS_INDIVIDUAL_2025_140PTC_f.pdf", "ADOR 10567 (25)"),
    ([146], "2025", "mctcp-worksheet", "Middle Class Tax Cuts Package (MCTCP) Worksheet for Calendar Year 2025", "document/FORMS_INDIVIDUAL_2025_MCTCP.pdf", "MCTCP Middle Class Tax Cuts Package (MCTCP) WORKSHEET FOR CALENDAR YEAR 2025"),
]:
    doc(rows, "az", F, f"azdor/ty{ty}/{tail}", title, AZ + file, agency="azdor", ty=ty,
        subtype="instructions" if "instructions" in tail or "booklet" in tail else "form", first=first)
for rows, tail, title, url in [
    ([112], "forms-individual", "Individual Income Tax Forms (ADOR forms index page)", "https://azdor.gov/forms/individual"),
    ([113], "form-140-booklet-page", "Form 140 - Arizona Resident Personal Income Tax Booklet (ADOR form page)", "https://azdor.gov/forms/individual/form-140-arizona-resident-personal-income-tax-booklet"),
    ([114], "form-140-fillable-page", "Form 140 - Resident Personal Income Tax Form -- Fillable (ADOR form page)", "https://azdor.gov/forms/individual/form-140-resident-personal-income-tax-form-calculating"),
    ([115], "form-140a-booklet-page", "Form 140A - Arizona Resident Personal Income Tax Booklet (ADOR form page)", "https://azdor.gov/forms/individual/form-140a-arizona-resident-personal-income-tax-booklet"),
    ([116], "itemized-deduction-adjustments-form-page", "Itemized Deduction Adjustments Form (ADOR form page)", "https://azdor.gov/forms/individual/itemized-deduction-adjustments-form"),
    ([138], "property-tax-refund-credit-claim-form-page", "Property Tax Refund (Credit) Claim Form -- Fillable (ADOR form page)", "https://azdor.gov/forms/tax-credits-forms/property-tax-refund-credit-claim-form-fillable"),
    ([136], "credit-contributions-qualifying-charitable-organizations-page", "Credit for Contributions to Qualifying Charitable Organizations (ADOR form page)", "https://azdor.gov/forms/tax-credits-forms/credit-contributions-qualifying-charitable-organizations"),
    ([137], "credit-contributions-qualifying-foster-care-charitable-organizations-page", "Credit for Contributions to Qualifying Foster Care Charitable Organizations (ADOR form page)", "https://azdor.gov/forms/tax-credits-forms/credit-contributions-qualifying-foster-care-charitable-organizations"),
]:
    doc(rows, "az", F, f"azdor/web/{tail}", title, url, agency="azdor", fmt="html", subtype="form_page", first=title)
doc([139], "az", G, "azdor/arizona-families-tax-rebate", "Arizona Families Tax Rebate (ADOR page)",
    "https://azdor.gov/individuals/arizona-families-tax-rebate", agency="azdor", fmt="html", subtype="agency_page", first="Arizona Families Tax Rebate | Arizona Department of Revenue")
doc([147], "az", G, "azdor/credits-contributions-qcos-and-qfcos", "Credits for Contributions to QCOs and QFCOs (ADOR page)",
    "https://azdor.gov/tax-credits/credits-contributions-qcos-and-qfcos", agency="azdor", fmt="html", subtype="agency_page", first="Credits for Contributions to QCOs and QFCOs")
doc([141], "az", G, "azdor/rulings/itr-12-1", "Income Tax Ruling ITR 12-1, Property Tax Credit Household Income",
    "https://azdor.gov/sites/default/files/2023-03/RULINGS_INDV_2012_itr12-1.pdf", agency="azdor", subtype="ruling", first="STATE OF ARIZONA Department of Revenue ... ITR 12-1")
doc([148], "az", G, "governor/executive-orders/2025-15", "Arizona Executive Order 2025-15",
    "https://azgovernor.gov/office-arizona-governor/executive-order/2025-15", agency="azgov", fmt="html", subtype="executive_order", first="Executive Order 2025-15 | Office of the Arizona Governor")
doc([154], "az", G, "senate/fact-sheets/55leg-1r/sb1828", "Arizona State Senate Fact Sheet for S.B. 1828 (55th Legislature, First Regular Session)",
    "https://www.azleg.gov/legtext/55leg/1R/summary/S.1828APPROP.DOCX.htm", agency="azleg", fmt="html", subtype="fact_sheet", first="SB1828 - 551R - Senate Fact Sheet")
doc([155], "az", L, "session-laws/2023/chapter-147-pdf", "Laws 2023, Chapter 147 (SB 1734, taxation; 2023-2024), PDF",
    "https://www.azleg.gov/legtext/56leg/1R/laws/0147.pdf", agency="azleg", subtype="session_law", first="Senate Engrossed taxation; 2023-2024 ... 2023 CHAPTER 147 SENATE BILL 1734")
doc([156], "az", L, "session-laws/2023/chapter-147", "Laws 2023, Chapter 147 (SB 1734, taxation; 2023-2024), HTML",
    "https://www.azleg.gov/legtext/56leg/1r/laws/0147.htm", agency="azleg", fmt="html", subtype="session_law", first="Chapter 0147 - 561R - S Ver of SB1734")
doc([157], "az", L, "bills/57leg-2r/hb4168-house-engrossed", "HB 4168 (2026), House Engrossed, taxation; omnibus; 2026-2027",
    "https://www.azleg.gov/legtext/57leg/2R/bills/HB4168H.pdf", agency="azleg", subtype="bill", first="House Engrossed taxation; omnibus; 2026-2027 ... Fifty-seventh Legislature Second Regular Session")

# ---------------------------------------------------------------- California (FTB)
FTB = "https://ftb.ca.gov/forms/"
for rows, ty, tail, title, file, fmt, first in [
    ([167], "2020", "3506-instructions", "2020 Instructions for Form FTB 3506 (Child and Dependent Care Expenses Credit)", "2020/2020-3506-instructions.html", "html", "2020 Instructions for Form FTB 3506 | FTB.ca.gov"),
    ([168], "2021", "3506-instructions", "2021 Instructions for Form FTB 3506", "2021/2021-3506-instructions.html", "html", "2021 Instructions for Form FTB 3506 | FTB.ca.gov"),
    ([169], "2021", "3514", "2021 Form FTB 3514, California Earned Income Tax Credit", "2021/2021-3514.pdf", "pdf", "FTB 3514 2021 Side 1 TAXABLE YEAR 2021 California Earned Income Tax Credit"),
    ([170], "2021", "3514-instructions", "2021 Instructions for Form FTB 3514", "2021/2021-3514-instructions.html", "html", "2021 Instructions for Form FTB 3514 | FTB.ca.gov"),
    ([171], "2021", "3526", "2021 Form FTB 3526, Investment Interest Expense Deduction", "2021/2021-3526.pdf", "pdf", "TAXABLE YEAR 2021 Investment Interest Expense Deduction CALIFORNIA FORM 3526"),
    ([172], "2021", "540", "2021 Form 540, California Resident Income Tax Return", "2021/2021-540.pdf", "pdf", "3101213 Form 540 2021 Side 1"),
    ([173], "2021", "540-booklet", "2021 Personal Income Tax Booklet (California Forms and Instructions 540)", "2021/2021-540-booklet.html", "html", "2021 Personal Income Tax Booklet | California Forms & Instructions 540"),
    ([174], "2021", "540-ca-instructions", "2021 Instructions for Schedule CA (540)", "2021/2021-540-ca-instructions.html", "html", "2021 Instructions for Schedule CA (540) | FTB.ca.gov"),
    ([175], "2021", "540-p", "2021 Schedule P (540), Alternative Minimum Tax and Credit Limitations - Residents", "2021/2021-540-p.pdf", "pdf", "7971213 Schedule P (540) 2021 Side 1"),
    ([176], "2021", "540-p-instructions", "2021 Instructions for Schedule P (540)", "2021/2021-540-p-instructions.html", "html", "2021 Instructions for Schedule P 540 | FTB.ca.gov"),
    ([177], "2022", "3506-instructions", "2022 Instructions for Form FTB 3506", "2022/2022-3506-instructions.html", "html", "2022 Instructions for Form FTB 3506 | FTB.ca.gov"),
    ([178], "2022", "3514", "2022 Form FTB 3514, California Earned Income Tax Credit", "2022/2022-3514.pdf", "pdf", "FTB 3514 2022 Side 1 TAXABLE YEAR 2022 California Earned Income Tax Credit"),
    ([179], "2022", "3514-instructions", "2022 Instructions for Form FTB 3514", "2022/2022-3514-instructions.html", "html", "2022 Instructions for Form FTB 3514 | FTB.ca.gov"),
    ([180], "2022", "540", "2022 Form 540, California Resident Income Tax Return", "2022/2022-540.pdf", "pdf", "3101223 Form 540 2022 Side 1"),
    ([181], "2022", "540-booklet", "2022 Personal Income Tax Booklet (California Forms and Instructions 540)", "2022/2022-540-booklet.html", "html", "2022 Personal Income Tax Booklet | California Forms & Instructions 540"),
    ([182], "2022", "540-ca-instructions", "2022 Instructions for Schedule CA (540)", "2022/2022-540-ca-instructions.html", "html", "2022 Instructions for Schedule CA (540) | FTB.ca.gov"),
    ([183], "2022", "540-p", "2022 Schedule P (540)", "2022/2022-540-p.pdf", "pdf", "7971223 Schedule P (540) 2022 Side 1"),
    ([184], "2022", "540-p-instructions", "2022 Instructions for Schedule P (540)", "2022/2022-540-p-instructions.html", "html", "2022 Instructions for Schedule P 540 | FTB.ca.gov"),
    ([185], "2023", "3506-instructions", "2023 Instructions for Form FTB 3506", "2023/2023-3506-instructions.html", "html", "2023 Instructions for Form FTB 3506 | FTB.ca.gov"),
    ([186], "2023", "3514", "2023 Form FTB 3514, California Earned Income Tax Credit", "2023/2023-3514.pdf", "pdf", "FTB 3514 2023 Side 1 TAXABLE YEAR 2023. California Earned Income Tax Credit"),
    ([187], "2023", "3514-instructions", "2023 California Earned Income Tax Credit Booklet (Instructions for Form FTB 3514)", "2023/2023-3514-instructions.html", "html", "2023 California Earned Income Tax Credit Booklet | FTB.ca.gov"),
    ([188], "2023", "540", "2023 Form 540, California Resident Income Tax Return", "2023/2023-540.pdf", "pdf", "3101233 Form 540 2023 Side 1"),
    ([189], "2023", "540-booklet", "2023 Personal Income Tax Booklet (California Forms and Instructions 540)", "2023/2023-540-booklet.html", "html", "2023 Personal Income Tax Booklet | California Forms & Instructions 540"),
    ([190], "2023", "540-ca-instructions", "2023 Instructions for Schedule CA (540)", "2023/2023-540-ca-instructions.html", "html", "2023 Instructions for Schedule CA (540) | FTB.ca.gov"),
    ([191], "2023", "540-p", "2023 Schedule P (540)", "2023/2023-540-p.pdf", "pdf", "TAXABLE YEAR 2023, Alternative Minimum Tax and Credit Limitations - Residents, CALIFORNIA SCHEDULE P (540)"),
    ([192], "2023", "540-p-instructions", "2023 Instructions for Schedule P (540)", "2023/2023-540-p-instructions.html", "html", "2023 Instructions for Schedule P 540 | FTB.ca.gov"),
    ([193], "2024", "3514", "2024 Form FTB 3514, California Earned Income Tax Credit", "2024/2024-3514.pdf", "pdf", "FTB 3514 2024 Side 1 TAXABLE YEAR 2024, California Earned Income Tax Credit"),
    ([194], "2024", "3514-booklet", "2024 California Earned Income Tax Credit Booklet", "2024/2024-3514-booklet.html", "html", "2024 California Earned Income Tax Credit Booklet | FTB.ca.gov"),
    ([195], "2024", "540", "2024 Form 540, California Resident Income Tax Return", "2024/2024-540.pdf", "pdf", "3101243 Form 540 2024 Side 1"),
    ([196], "2024", "540-p", "2024 Schedule P (540)", "2024/2024-540-p.pdf", "pdf", "7971243 Schedule P (540) 2024 Side 1 Taxable Year 2024"),
    ([197], "2025", "1005-publication", "FTB Publication 1005, Pension and Annuity Guidelines (2025)", "2025/2025-1005-publication.pdf", "pdf", "FTB Publication 1005 2025 Pension and Annuity Guidelines"),
    ([198], "2025", "3506-instructions", "2025 Instructions for Form FTB 3506", "2025/2025-3506-instructions.html", "html", "2025 Instructions for Form FTB 3506 | FTB.ca.gov"),
    ([199], "2025", "3514-booklet", "2025 California Earned Income Tax Credit Booklet (HTML)", "2025/2025-3514-booklet.html", "html", "2025 California Earned Income Tax Credit Booklet | FTB.ca.gov"),
    ([202], "2025", "540-ca-instructions", "2025 Instructions for Schedule CA (540)", "2025/2025-540-ca-instructions.html", "html", "2025 Instructions for Schedule CA (540) | FTB.ca.gov"),
    ([203], "2025", "540-instructions", "2025 Instructions for Form 540", "2025/2025-540-instructions.html", "html", "2025 Instructions for Form 540 | FTB.ca.gov"),
    ([204], "2025", "540-p", "2025 Schedule P (540)", "2025/2025-540-p.pdf", "pdf", "7971253 Schedule P (540) 2025 Side 1 TAXABLE YEAR 2025"),
    ([205], "2025", "540-p-instructions", "2025 Instructions for Schedule P (540)", "2025/2025-540-p-instructions.html", "html", "2025 Instructions for Schedule P 540 | FTB.ca.gov"),
]:
    doc(rows, "ca", F, f"ftb/ty{ty}/{tail}", title, FTB + file, agency="ftb", fmt=fmt, ty=ty,
        subtype="instructions" if "instructions" in tail or "booklet" in tail or "publication" in tail else "form", first=first)
# The three 2024 FTB instructions of manifests/us-ca-ftb-2024-tax-instructions.yaml keep their
# (grammar-valid) citation paths.
for rows, path, title, file in [
    ([164], "us-ca/form/ftb/2024/540-booklet", "2024 Personal Income Tax Booklet", "2024/2024-540-booklet.html"),
    ([165], "us-ca/form/ftb/2024/schedule-ca-540-instructions", "2024 Instructions for Schedule CA 540", "2024/2024-540-ca-instructions.html"),
    ([166], "us-ca/form/ftb/2024/schedule-p-540-instructions", "2024 Instructions for Schedule P 540", "2024/2024-540-p-instructions.html"),
]:
    doc(rows, "ca", F, "", title, FTB + file, agency="ftb", fmt="html", ty="2024", subtype="instructions",
        first=f"{title} | FTB.ca.gov", citation_path=path)
# Row 206 (manifests/us-ca-2025-ftb-3514-booklet.yaml) was extracted on 2026-09-23 into the
# scope us-ca/form/2026-09-23-ca-2025-ftb-3514, locked on main (same PDF, same path): ALREADY-HELD.
for rows, ty in [([228], "2021"), ([229], "2022"), ([230], "2023"), ([231], "2024")]:
    doc(rows, "ca", F, f"ftb/ty{ty}/540-tax-rate-schedules", f"{ty} California Tax Rate Schedules",
        f"https://www.ftb.ca.gov/forms/{ty}/{ty}-540-tax-rate-schedules.pdf", agency="ftb", ty=ty, subtype="tax_rate_schedule",
        first=f"{ty} California Tax Rate Schedules")
doc([232], "ca", F, "ftb/ty2025/3526", "2025 Form FTB 3526, Investment Interest Expense Deduction",
    "https://www.ftb.ca.gov/forms/2025/2025-3526.pdf", agency="ftb", ty="2025", first="TAXABLE YEAR 2025 Investment Interest Expense Deduction CALIFORNIA FORM 3526")
doc([223], "ca", G, "ftb/reports/california-eitc-and-yctc-report", "California Earned Income Tax Credit and Young Child Tax Credit Report (FTB Economic and Statistical Research Bureau)",
    "https://www.ftb.ca.gov/about-ftb/data-reports-plans/California-Earned-Income-Tax-Credit-and-Young-Child-Tax-credit-Report.pdf", agency="ftb", subtype="report")
doc([225], "ca", G, "ftb/reports/california-eitc-report-2019", "California Earned Income Tax Credit Report 2019",
    "https://www.ftb.ca.gov/about-ftb/data-reports-plans/california-earned-income-tax-credit-report-2019.pdf", agency="ftb", subtype="report")
doc([224], "ca", G, "ftb/summary-of-federal-income-tax-changes", "Summary of Federal Income Tax Changes (FTB)",
    "https://www.ftb.ca.gov/about-ftb/data-reports-plans/Summary-of-Federal-Income-Tax-Changes/index.html", agency="ftb", fmt="html", subtype="report")
doc([226], "ca", G, "ftb/eitc-calculator-help-qualifying-children", "CalEITC Calculator Help: Qualifying Children (FTB)",
    "https://www.ftb.ca.gov/file/personal/credits/EITC-calculator/Help/QualifyingChildren", agency="ftb", fmt="html", subtype="agency_page")
doc([227], "ca", G, "ftb/foster-youth-tax-credit", "Foster Youth Tax Credit (FTB)",
    "https://www.ftb.ca.gov/file/personal/credits/foster-youth-tax-credit.html", agency="ftb", fmt="html", subtype="agency_page")

# ---------------------------------------------------------------- Colorado
# tax.colorado.gov (CloudFront) answers the corpus client with HTTP 403 and serves the
# extractor's built-in Chrome user-agent retry (documented in
# docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md); no impersonation is needed.
CDOR = "https://tax.colorado.gov/sites/tax/files/documents/"
for rows, ty, tail, title, file, first in [
    ([269], "2021", "dr-0104-book", "2021 Colorado Individual Income Tax Filing Guide (104 Book)", "DR_104_Book_2021.pdf", "Colorado Individual Income Tax Filing Guide ... 104 BOOK (2021)"),
    ([263], "2021", "dr-0104-book-v3", "2021 Colorado Individual Income Tax Filing Guide (104 Book), version 3", "DR0104Book_2021_V3.pdf", "Colorado Individual Income Tax Filing Guide ... 104 BOOK (2021, V3)"),
    ([260], "2021", "dr-0104ad", "2021 DR 0104AD Subtractions from Income Schedule", "DR0104AD_2021.pdf", "DR 0104AD (10/22/21) ... 2021 DR 0104AD - Subtractions from Income Schedule"),
    ([270], "2022", "dr-0104-book", "2022 Colorado Individual Income Tax Filing Guide (104 Book)", "DR_104_Book_2022.pdf", "Colorado Individual Income Tax Filing Guide ... 104 BOOK (2022)"),
    ([261], "2022", "dr-0104ad", "2022 DR 0104AD Subtractions from Income Schedule", "DR0104AD_2022.pdf", "DR 0104AD (11/17/22) ... 2022 DR 0104AD"),
    ([267], "2022", "dr-0104cn", "2022 DR 0104CN Colorado Child Tax Credit", "DR_0104CN_2022.pdf", "Complete this form to calculate the 2022 Colorado child tax credit"),
    ([268], "2022", "dr-0104ep", "2022 DR 0104EP Colorado Individual Estimated Income Tax Payment Form", "DR_0104EP_2022_0.pdf", "Estimated tax is the method used to pay tax on income that is not subject to withholding (2022)"),
    ([259], "2023", "dr-0104-book", "2023 Colorado Individual Income Tax Filing Guide (104 Book)", "Book0104_2023.pdf", "Colorado Individual Income Tax Filing Guide ... 104 BOOK (2023)"),
    ([262], "2023", "dr-0104ad", "2023 DR 0104AD Subtractions from Income Schedule", "DR0104AD_2023.pdf", "DR 0104AD (09/28/23) ... 2023 DR 0104AD"),
    ([264], "2023", "dr-0104cn", "2023 DR 0104CN Colorado Child Tax Credit", "DR0104CN_2023.pdf", "Complete this form to calculate the 2023 Colorado child tax credit"),
    ([265], "2024", "dr-0104cn", "2024 DR 0104CN Colorado Child Tax Credit Instructions", "DR0104CN_2024.pdf", "2024 Colorado Child Tax Credit Instructions"),
    ([266], "2024", "dr-0104-book", "2024 Colorado Individual Income Tax Filing Guide (104 Book)", "DR0104_book_2024.pdf", "(11/26/24) Booklet Includes: Instructions | DR 0104 | Related Forms 2024 104 BOOK"),
]:
    doc(rows, "co", F, f"cdor/ty{ty}/{tail}", title, CDOR + file, agency="cdor", ty=ty,
        subtype="instructions" if "book" in tail else "form", first=first)
for rows, tail, title, file, first in [
    ([271], "income-tax-topics/child-and-dependent-care-expenses-credit-2026-01", "Income Tax Topics: Child and Dependent Care Expenses Credit (Revised January 2026)", "ITT_Child_and_Dependent_Care_Expenses_Credit_Jan_2026.pdf", "Revised January 2026 Income Tax Topics: Child and Dependent Care Expenses Credit"),
    ([272], "income-tax-topics/social-security-pensions-and-annuities-2025-01", "Income Tax Topics: Social Security, Pensions and Annuities (Revised January 2025)", "ITT_Social_Security_Pensions_and_Annuities_Jan_2025.pdf", "Revised January 2025 Income Tax Topics: Social Security, Pensions and Annuities"),
]:
    doc(rows, "co", G, f"cdor/{tail}", title, CDOR + file, agency="cdor", subtype="income_tax_topic", first=first)
for rows, tail, title, url in [
    ([252], "dr-0104amt", "DR 0104AMT - Alternative Minimum Tax Computation Schedule (CDOR page)", "https://tax.colorado.gov/DR0104AMT"),
    ([253], "income-qualified-senior-housing-income-tax-credit", "Income Qualified Senior Housing Income Tax Credit (CDOR page)", "https://tax.colorado.gov/income-qualified-senior-housing-income-tax-credit"),
    ([254], "income-tax-topics-earned-income-tax-credit", "Income Tax Topics: Earned Income Tax Credit (CDOR page)", "https://tax.colorado.gov/income-tax-topics-earned-income-tax-credit"),
    ([255], "income-tax-topics-social-security-pensions-and-annuities", "Income Tax Topics: Social Security, Pensions and Annuities (CDOR page)", "https://tax.colorado.gov/income-tax-topics-social-security-pensions-and-annuities"),
    ([256], "income-tax-topics-state-sales-tax-refund", "Income Tax Topics: State Sales Tax Refund (CDOR page)", "https://tax.colorado.gov/income-tax-topics-state-sales-tax-refund"),
    ([257], "individual-income-tax-guide", "Individual Income Tax Guide (CDOR page)", "https://tax.colorado.gov/individual-income-tax-guide"),
    ([258], "january-2026-tax-policy-updates", "January 2026 Tax Policy Updates (CDOR page)", "https://tax.colorado.gov/january-2026-tax-policy-updates"),
]:
    doc(rows, "co", G, f"cdor/{tail}", title, url, agency="cdor", fmt="html", subtype="agency_page", first=title)
LEGCO = "https://leg.colorado.gov/sites/default/files/"
for rows, year, bill, title, url, first in [
    ([241], "2023", "hb23-1112", "House Bill 23-1112 (signed act), earned income and child tax credits", LEGCO + "2023a_1112_signed.pdf", "HOUSE BILL 23-1112"),
    ([242], "2024", "hb24-1052", "House Bill 24-1052 (signed act), senior housing income tax credit", LEGCO + "2024a_1052_signed.pdf", "HOUSE BILL 24-1052"),
    ([243], "2024", "hb24-1142", "House Bill 24-1142 (signed act), social security subtraction", LEGCO + "2024a_1142_signed.pdf", "HOUSE BILL 24-1142"),
    ([236], "2025", "hb25-1296", "House Bill 25-1296 (signed act)", "https://content.leg.colorado.gov/sites/default/files/2025a_1296_signed.pdf", "HOUSE BILL 25-1296"),
    ([244], "2025", "hb25b-1001", "House Bill 25B-1001 (signed act, 2025 First Extraordinary Session)", LEGCO + "2025b_1001_signed.pdf", "HOUSE BILL 25B-1001"),
]:
    doc(rows, "co", L, f"session-laws/{year}/{bill}", title, url, agency="cga-co", subtype="session_law", first=first)
doc([245], "co", L, "bills/2022/sb22-233-introduced", "Senate Bill 22-233 (introduced), TABOR refund for 2022",
    LEGCO + "documents/2022A/bills/2022a_233_01.pdf", agency="cga-co", subtype="bill", first="Second Regular Session Seventy-third General Assembly ... SENATE BILL 22-233")
for rows, bill, title, url in [
    ([238], "sb24-228", "SB24-228 TABOR Refund Mechanisms (Colorado General Assembly bill page)", "https://leg.colorado.gov/bills/SB24-228"),
    ([239], "hb23-1311", "HB23-1311 Identical Temporary TABOR Refund (Colorado General Assembly bill page)", "https://leg.colorado.gov/bills/hb23-1311"),
    ([240], "hb25-1274", "HB25-1274 Healthy School Meals for All Program (Colorado General Assembly bill page)", "https://leg.colorado.gov/bills/hb25-1274"),
]:
    doc(rows, "co", G, f"general-assembly/bills/{bill}", title, url, agency="cga-co", fmt="html", subtype="bill_information", first=title)
doc([246], "co", G, "legislative-council/fiscal-notes/hb23-1311", "Legislative Council Staff Fiscal Note, HB 23-1311 (May 6, 2023)",
    LEGCO + "documents/2023A/bills/fn/2023a_hb1311_00.pdf", agency="lcs", subtype="fiscal_note", first="May 6, 2023 HB 23-1311 Legislative Council Staff ... Fiscal Note")
doc([248], "co", G, "legislative-council/ballot-analysis/2022-proposition-121", "Legislative Council Draft, Proposition 121: State Income Tax Rate Reduction",
    LEGCO + "initiative%2520referendum_proposition%20121%20final%20lc%20packet.pdf", agency="lcs", subtype="ballot_analysis", first="Legislative Council Draft - 1 - Proposition 121: State Income Tax Rate Reduction")
doc([249], "co", G, "state-auditor/tax-expenditure-evaluations/te19-colorado-eitc", "Office of the State Auditor Tax Expenditure Evaluation: Colorado Earned Income Tax Credit",
    LEGCO + "te19_colorado_earned_income_tax_credit.pdf", agency="osa", subtype="evaluation", first="TAX TYPE Income YEAR ENACTED 1999 ... EARNED INCOME TAX CREDIT")
# Prior official compilations of C.R.S. title 39 (OLLS print editions), one row per page; the
# 2025 edition is held section by section (us-co/statute/39/...).
doc([247], "co", L, "crs-2023/title-39", "Colorado Revised Statutes 2023, Title 39 (Taxation), official OLLS compilation",
    "https://leg.colorado.gov/sites/default/files/images/olls/crs2023-title-39.pdf", agency="olls", subtype="code_edition",
    extraction=dict(PAGES), first="Colorado Revised Statutes 2023 TITLE 39 TAXATION (1,051 pages)")
doc([237], "co", L, "crs-2024/title-39", "Colorado Revised Statutes 2024, Title 39 (Taxation), official OLLS compilation",
    "https://content.leg.colorado.gov/sites/default/files/images/olls/crs2024-title-39.pdf", agency="olls", subtype="code_edition",
    extraction=dict(PAGES), first="Colorado Revised Statutes 2024 TITLE 39 Taxation (1,163 pages)")
doc([251], "co", L, "crs-2025/constitution", "Constitution of the State of Colorado (Colorado Revised Statutes 2025, official OLLS compilation)",
    "https://olls.info/crs/crs2025-title-00.pdf", agency="olls", subtype="constitution",
    extraction=dict(PAGES), first="Colorado Revised Statutes 2025 CONSTITUTION OF THE STATE OF COLORADO Preamble (210 pages)")

# ---------------------------------------------------------------- Connecticut
CTF = "https://portal.ct.gov/-/media/"
for rows, ty, tail, title, file, first in [
    ([281], "2021", "ct-1040-online-booklet", "2021 Form CT-1040 Connecticut Resident Income Tax Return Instructions (online booklet)", "DRS/Forms/2021/Income/CT-1040-Online-Booklet_1221.pdf", "2021 FORM CT-1040 Connecticut Resident Income Tax Return Instructions"),
    ([282], "2022", "ct-1040-instructions", "2022 Form CT-1040 Connecticut Resident Income Tax Return Instructions (Rev. 12/22)", "DRS/Forms/2022/Income/2022-CT-1040-Instructions_1222.pdf", "Department of Revenue Services State of Connecticut (Rev. 12/22) 2022 Form CT-1040 ... Instructions"),
    ([283], "2022", "ct-1040", "2022 Form CT-1040 Connecticut Resident Income Tax Return", "DRS/Forms/2022/Income/CT-1040_1222.pdf", "Due date: April 15, 2023 (Form CT-1040 2022)"),
    ([284], "2022", "ct-6251", "2022 Form CT-6251 Connecticut Alternative Minimum Tax Return - Individuals", "DRS/Forms/2022/Income/CT-6251_1222.pdf", "Page 1 of 8 1. Federal alternative minimum taxable income"),
    ([285], "2022", "schedule-ct-it-credit", "2022 Schedule CT-IT Credit, Income Tax Credit Summary", "drs/forms/2022/income/schedule-ct-it-credit_1222.pdf", "1. Income tax liability: Enter amount from Form CT-1040, Line 12"),
    ([286], "2023", "ct-1040-instructions", "2023 Form CT-1040 Connecticut Resident Income Tax Return Instructions (Rev. 12/23)", "DRS/Forms/2023/Income/2023-CT-1040-Instructions_1223.pdf", "Department of Revenue Services State of Connecticut (Rev. 12/23) 2023 Form CT-1040 ... Instructions"),
    ([287, 290], "2024", "ct-1040-instructions", "2024 Form CT-1040 Connecticut Resident Income Tax Return Instructions (Rev. 01/25)", "drs/forms/2024/income/2024-ct-1040-instructions_1224.pdf", "Department of Revenue Services State of Connecticut (Rev. 01/25) 2024 Form CT-1040 ... Instructions"),
    ([288], "2024", "ct-1040", "2024 Form CT-1040 Connecticut Resident Income Tax Return", "drs/forms/2024/income/ct-1040_1224.pdf", "Due date: April 15, 2025 (Form CT-1040 2024)"),
    ([292], "2020", "schedule-ct-eitc", "2020 Schedule CT-EITC, Connecticut Earned Income Tax Credit (Rev. 01/21)", "DRS/Forms/2020/Income/Schedule-CT-EITC_0121.pdf", "Schedule CT-EITC Connecticut Earned Income Tax Credit 2020 (Rev. 01/21)"),
    ([293], "2021", "schedule-ct-eitc", "2021 Schedule CT-EITC, Connecticut Earned Income Tax Credit (Rev. 12/21)", "DRS/Forms/2021/Income/Schedule-CT-EITC_1221.pdf", "Schedule CT-EITC Connecticut Earned Income Tax Credit 2021 (Rev. 12/21)"),
    ([294], "2022", "schedule-ct-eitc", "2022 Schedule CT-EITC, Connecticut Earned Income Tax Credit (Rev. 12/22)", "DRS/Forms/2022/Income/Schedule-CT-EITC_1222.pdf", "Schedule CT-EITC Connecticut Earned Income Tax Credit 2022 (Rev. 12/22)"),
    ([295], "2023", "schedule-ct-eitc", "2023 Schedule CT-EITC, Connecticut Earned Income Tax Credit (Rev. 12/23)", "DRS/Forms/2023/Income/Schedule-CT-EITC_1223.pdf", "Schedule CT-EITC Connecticut Earned Income Tax Credit 2023 (Rev. 12/23)"),
]:
    doc(rows, "ct", F, f"drs/ty{ty}/{tail}", title, CTF + file, agency="drs", ty=ty,
        subtype="instructions" if "instructions" in tail or "booklet" in tail else "form", first=first)
doc([296], "ct", G, "drs/tssb/2022-5", "TSSB 2022-5, Frequently Asked Questions Concerning the Child Tax Rebate",
    CTF + "drs/publications/tssb/2022/tssb-2022-5.pdf", agency="drs", subtype="special_notice", first="TSSB 2022-5 TAXPAYER SERVICE SPECIAL BULLETIN")
doc([297], "ct", G, "drs/child-tax-rebate-overview", "2022 Child Tax Rebate (DRS page)",
    "https://portal.ct.gov/drs/credit-programs/child-tax-rebate/overview", agency="drs", fmt="html", subtype="agency_page", first="2022 Child Tax Rebate")
doc([298], "ct", G, "drs/state-tax-developments/2025/income-tax", "2025 State Tax Developments: Income Tax (DRS page)",
    "https://portal.ct.gov/drs/miscellaneous-taxes/other-tax-page/state-tax-developments/2025-developments/income-tax", agency="drs", fmt="html", subtype="agency_page", first="Income Tax (2025 developments)")
doc([301, 302], "ct", L, "public-acts/2022/pa-22-118", "Public Act No. 22-118 (House Bill No. 5506), An Act Adjusting the State Budget for the Biennium Ending June 30, 2023",
    "https://www.cga.ct.gov/2022/ACT/PA/PDF/2022PA-00118-R00HB-05506-PA.PDF", agency="cga", subtype="session_law",
    extraction=dict(PAGES), first="House Bill No. 5506 Public Act No. 22-118 AN ACT ADJUSTING THE STATE BUDGET (739 pages)")
doc([303], "ct", L, "public-acts/2023/pa-23-31", "Public Act No. 23-31 (Substitute House Bill No. 6733)",
    "https://www.cga.ct.gov/2023/ACT/PA/PDF/2023PA-00031-R00HB-06733-PA.PDF", agency="cga", subtype="session_law",
    extraction=dict(PAGES), first="Substitute House Bill No. 6733 Public Act No. 23-31 (74 pages)")
doc([304], "ct", L, "supplements/2024/chapter-229", "Connecticut General Statutes, 2024 Supplement, Chapter 229 - Income Tax",
    "https://www.cga.ct.gov/2024/sup/chap_229.htm", agency="cga", fmt="html", subtype="code_supplement", first="Chapter 229 - Income Tax (2024 Supplement)")

# ---------------------------------------------------------------- District of Columbia
OTR = "https://otr.cfo.dc.gov/sites/default/files/dc/sites/otr/publication/attachments/"
doc([312], "dc", F, "otr/ty2020/schedule-elc", "2020 DC Schedule ELC, Early Learning Tax Credit (Revised 04/20)", OTR + "2020_Schedule_ELC.pdf",
    agency="otr", ty="2020", first="2020 Government of the District of Columbia Revised 04/20 (Schedule ELC)")
doc([313], "dc", F, "otr/ty2024/d-40-booklet", "2024 DC Individual Income Tax Forms and Instructions (D-40 Booklet, Revised 09/2024)", OTR + "2024_D40_Booklet_011525.pdf",
    agency="otr", ty="2024", subtype="instructions", first="District of Columbia (DC) Individual Income Tax Forms and Instructions All Individual Income Tax Filers 2024 Revised 09/2024")
doc([314], "dc", F, "otr/ty2021/d-40-booklet", "2021 DC Individual Income Tax Forms and Instructions (D-40 Booklet, Revised 07/2021)", OTR + "52926_D-40_12.21.21_Final_Rev011122.pdf",
    agency="otr", ty="2021", subtype="instructions", first="District of Columbia (DC) Individual Income Tax Forms and Instructions D-40 All Individual Income Tax Filers 2021 Revised 07/2021")
doc([311], "dc", G, "otr/releases/tax-changes-take-effect-october-1-2024", "District of Columbia Tax Changes Take Effect October 1st (OTR release, 2024)",
    "https://otr.cfo.dc.gov/release/district-columbia-tax-changes-take-effect-october1-24", agency="otr", fmt="html", subtype="press_release", first="District of Columbia Tax Changes Take Effect October 1st")
for rows, tail, title, url in [
    ([305], "acts/26-214", "D.C. Act 26-214, D.C. Income and Franchise Tax Conformity and Revision Emergency Amendment Act of 2025", "https://code.dccouncil.gov/us/dc/council/acts/26-214"),
    ([309], "laws/23-149", "D.C. Law 23-149, Fiscal Year 2021 Budget Support Act of 2020", "https://code.dccouncil.gov/us/dc/council/laws/23-149"),
    ([310], "laws/24-301", "D.C. Law 24-301, Give SNAP a Raise Amendment Act of 2022", "https://code.dccouncil.gov/us/dc/council/laws/24-301"),
]:
    doc(rows, "dc", L, f"session-laws/{tail}", title, url, agency="dccouncil", fmt="html", subtype="session_law", first=title)

# ---------------------------------------------------------------- Delaware
DEF = "https://revenuefiles.delaware.gov/"
for rows, ty, tail, title, file, first in [
    ([320], "2021", "pit-res-instructions", "2021 Delaware Resident Individual Income Tax Return Instructions (PIT-RES)", "2021/PIT-RES_TY21_2021-01_Instructions.pdf", "DELAWARE Individual Income Tax Return RESIDENT 2021"),
    ([321], "2021", "pit-res", "2021 Delaware Form PIT-RES, Resident Individual Income Tax Return", "2021/PIT-RES_TY21_2021-01_PaperBase.pdf", "Form PIT-RES 2021 (paper base)"),
    ([322], "2022", "pit-res", "2022 Delaware Form PIT-RES, Resident Individual Income Tax Return (interactive)", "2022/PIT-RES_TY22_2022-01_PaperInteractive.pdf", "Form PIT-UND If you were a part-year resident in 2022"),
    ([323], "2022", "pit-res-instructions", "2022 Delaware Resident Individual Income Tax Return Instructions (PIT-RES)", "2022/PIT-RES_TY22_2022-02_Instructions.pdf", "DELAWARE Individual Income Tax Return RESIDENT 2022"),
    ([324], "2022", "pit-rsa", "2022 Delaware Form PIT-RSA, Resident Schedule A Itemized Deductions (interactive)", "2022/TY22_PIT-RSA_2022-02_PaperInteractive.pdf", "TOTAL ITEMIZED DEDUCTIONS (PIT-RSA 2022)"),
    ([325], "2023", "pit-res-instructions", "2023 Delaware Resident Individual Income Tax Return Instructions (PIT-RES)", "2023/PIT-RES_TY23_2023-01_Instructions.pdf", "DELAWARE Individual Income Tax Return RESIDENT 2023"),
    ([326], "2024", "pit-res-instructions", "2024 Delaware Resident Individual Income Tax Return and Instructions (PIT-RES)", "2024/PIT_2024_Forms/PIT_Instructions/PIT-RES_TY24_2024-01_Instructions.pdf", "DELAWARE Individual Income Tax Return RESIDENT AND INSTRUCTIONS 2024"),
]:
    doc(rows, "de", F, f"dor/ty{ty}/{tail}", title, DEF + file, agency="dedor", ty=ty,
        subtype="instructions" if "instructions" in tail else "form", first=first)
doc([319], "de", G, "dor/tax-rate-changes", "Tax Rate Changes (Division of Revenue software-developer page)",
    "https://revenue.delaware.gov/software-developer/tax-rate-changes/", agency="dedor", fmt="html", subtype="agency_page", first="Tax Rate Changes - Division of Revenue")
doc([318], "de", G, "news/2022-06-30-hb145", "Two State Sponsored Savings Programs to Bring New Tax Deductions (State of Delaware News, 2022-06-30)",
    "https://news.delaware.gov/2022/06/30/hb145/", agency="news-de", fmt="html", subtype="press_release", first="Two State Sponsored Savings Programs to Bring New Tax Deductions")
doc([327], "de", G, "treasurer/education-savings-plan", "DE529 Education Savings Plan (Office of the State Treasurer page)",
    "https://treasurer.delaware.gov/education-savings-plan/", agency="treasurer-de", fmt="html", subtype="agency_page", first="DE529 - Education Savings Plan")
doc([317], "de", G, "general-assembly/bill-detail/99311", "House Bill 360 (151st General Assembly), 2022 Delaware Relief Rebate Program: Bill Detail, Delaware General Assembly",
    "https://legis.delaware.gov/BillDetail?LegislationId=99311", agency="legis-de", fmt="html", subtype="bill_information", first="House Bill 360, 151st General Assembly (2021-2022), Signed 4/14/22",
    extraction={"html_content_selector": "#content", "html_text_selector": "#content"})

# ---------------------------------------------------------------- Georgia
GAD = "https://dor.georgia.gov/document/"
doc([329, 346], "ga", F, "dor/ty2021/it-511", "2021 IT-511 Individual Income Tax Booklet (Form 500 instructions)",
    GAD + "booklet/2021-it-511-individual-income-tax-booklet/download", agency="gador", ty="2021", subtype="instructions",
    first="Charitable Contributions/Donations ... Filing Requirements (2021 IT-511, 60 pages)")
doc([331, 330, 344], "ga", F, "dor/ty2022/it-511", "2022 IT-511 Individual Income Tax Booklet (Rev. 02.15.23)",
    GAD + "document/2022-it-511-individual-income-tax-booklet/download", agency="gador", ty="2022", subtype="instructions",
    first="IT 511 Rev. 02.15.23 ... Georgia Department of Revenue 2022 Individual Income Tax")
doc([332, 345], "ga", F, "dor/ty2023/it-511", "2023 IT-511 Individual Income Tax Booklet",
    GAD + "document/2023-it-511-individual-income-tax-booklet/download", agency="gador", ty="2023", subtype="instructions",
    first="Filing Requirements 9 Form 500 Instructions 11-13 ... Tax returns due April 15, 2024")
doc([333], "ga", F, "dor/ty2024/it-511", "2024 IT-511 Individual Income Tax Booklet",
    GAD + "document/2024-it-511-individual-income-tax-booklet/download", agency="gador", ty="2024", subtype="instructions",
    first="2024 IT-511 Instructions Booklet 2024 Georgia Individual Income Tax Forms and Instructions")
doc([328], "ga", F, "dor/ty2022/form-500", "2022 Georgia Form 500, Individual Income Tax Return (Rev. 06/22/22, approved web version)",
    "https://apps.dor.ga.gov/FillableForms/webpdf/examples/2022GA500.pdf", agency="gador", ty="2022",
    first="Georgia Form 500 (Rev. 06/22/22) Individual Income Tax Return ... 2022")
doc([334, 335], "ga", G, "dor/it-511-individual-income-tax-booklet", "IT-511 Individual Income Tax Instruction Booklet (DOR page listing the 2020-2025 booklets)",
    "https://dor.georgia.gov/it-511-individual-income-tax-booklet", agency="gador", fmt="html", subtype="agency_page", first="IT-511 Individual Income Tax Instruction Booklet")
doc([336], "ga", G, "dor/tax-tables-georgia-tax-rate-schedule", "Tax Tables & Georgia Tax Rate Schedule (DOR page)",
    "https://dor.georgia.gov/tax-tables-georgia-tax-rate-schedule", agency="gador", fmt="html", subtype="agency_page", first="Tax Tables & Georgia Tax Rate Schedule")
doc([337], "ga", G, "governor/press-releases/2024-04-18-tax-cut-package", "Gov. Kemp Signs Historic Tax Cut Package Into Law (2024-04-18)",
    "https://gov.georgia.gov/press-releases/2024-04-18/gov-kemp-signs-historic-tax-cut-package-law", agency="gagov", fmt="html", subtype="press_release", first="Gov. Kemp Signs Historic Tax Cut Package Into Law")
GOVGA = "https://gov.georgia.gov/document/"
for rows, year, bill, title, file, first in [
    ([339], "2022", "hb1437", "House Bill 1437 (2022), Tax Reduction and Reform Act of 2022 (as passed, signed legislation)", "2022-signed-legislation/hb-1437/download", "22 HB 1437/AP House Bill 1437 (AS PASSED HOUSE AND SENATE)"),
    ([340], "2023", "hb162", "House Bill 162 (2023), one-time refund of 2021 income taxes (as passed, signed legislation)", "2023-signed-legislation/hb-162/download", "23 LC 43 2563-EC/AP House Bill 162 (AS PASSED HOUSE AND SENATE)"),
    ([343], "2024", "hb1015", "House Bill 1015 (2024), flat income tax rate (as passed, signed legislation)", "2024-signed-legislation/hb-1015/download", "24 LC 50 0620-EC/AP House Bill 1015 (AS PASSED HOUSE AND SENATE)"),
]:
    doc(rows, "ga", L, f"session-laws/{year}/{bill}", title, GOVGA + file, agency="gagov", subtype="session_law", first=first)

# ---------------------------------------------------------------- Hawaii
HIF = "https://files.hawaii.gov/tax/forms/"
for rows, ty, tail, title, file, first in [
    ([357], "2018", "n-11-instructions", "2018 Form N-11 Hawaii Resident Income Tax Forms and Instructions", "2018/n11ins.pdf", "2018 N-11 Forms and Instructions ... Hawaii Resident Income Tax Forms and Instructions"),
    ([358], "2019", "n-11-instructions", "2019 Form N-11 Hawaii Resident Income Tax Instructions", "2019/n11ins.pdf", "2019 N-11 ... Hawaii Resident Income Tax Instructions"),
    ([359], "2020", "n-11-instructions", "2020 Form N-11 Hawaii Resident Income Tax Instructions", "2020/n11ins.pdf", "2020 N-11 ... Hawaii Resident Income Tax Instructions"),
    ([361], "2021", "n-11-instructions", "2021 Form N-11 Hawaii Resident Income Tax Instructions", "2021/n11ins.pdf", "2021 N-11 ... Hawaii Resident Income Tax Instructions"),
    ([360], "2021", "n-11", "Form N-11 Individual Income Tax Return, Resident (Rev. 2021)", "2021/n11_i.pdf", "FORM N-11 Individual Income Tax Return (Rev. 2021) RESIDENT Calendar Year 2021"),
    ([363], "2022", "n-11-instructions", "2022 Form N-11 Hawaii Resident Income Tax Instructions", "2022/n11ins.pdf", "2022 N-11 ... Hawaii Resident Income Tax Instructions"),
    ([362], "2022", "n-11", "Form N-11 Individual Income Tax Return, Resident (Rev. 2022)", "2022/n11_i.pdf", "FORM N-11 Individual Income Tax Return (Rev. 2022) RESIDENT Calendar Year 2022"),
    ([364], "2023", "n-11-instructions", "2023 Form N-11 Hawaii Resident Income Tax Instructions", "2023/n11ins.pdf", "2023 N-11 ... Hawaii Resident Income Tax Instructions"),
    ([366], "2024", "n-11-instructions", "2024 Form N-11 Hawaii Resident Income Tax Instructions", "2024/n11ins.pdf", "2024 N-11 ... Hawaii Resident Income Tax Instructions"),
    ([365], "2024", "n-11", "Form N-11 Individual Income Tax Return, Resident (Rev. 2024)", "2024/n11_i.pdf", "FORM N-11 Individual Income Tax Return (Rev. 2024) RESIDENT Calendar Year 2024"),
    ([375], "2022", "n-15-instructions", "2022 Form N-15 Hawaii Nonresident and Part-Year Resident Income Tax Instructions", "2022/n15ins.pdf", "2022 N-15 ... Hawaii Nonresident and Part-Year Resident Income Tax Instructions"),
    ([376], "2022", "n-311", "Form N-311 Refundable Food/Excise Tax Credit (Rev. 2022)", "2022/n311_i.pdf", "FORM N-311 (REV. 2022) REFUNDABLE FOOD/EXCISE TAX CREDIT"),
    ([379], "2023", "n-311", "Form N-311 Refundable Food/Excise Tax Credit (Rev. 2023)", "2023/n311_i.pdf", "FORM N-311 (REV. 2023) REFUNDABLE FOOD/EXCISE TAX CREDIT"),
    ([382], "2025", "n-311", "Form N-311 Refundable Food/Excise Tax Credit (Rev. 2025, current)", "current/n311_i.pdf", "FORM N-311 (REV. 2025) REFUNDABLE FOOD/EXCISE TAX CREDIT"),
    ([377], "2022", "n-356", "Form N-356 Earned Income Tax Credit (Rev. 2022)", "2022/n356_i.pdf", "FORM N-356 (REV. 2022)"),
    ([380], "2023", "n-356", "Form N-356 Earned Income Tax Credit (Rev. 2023)", "2023/n356_i.pdf", "FORM N-356 (REV. 2023) EARNED INCOME TAX CREDIT"),
    ([383], "2025", "n-356", "Form N-356 Earned Income Tax Credit (Rev. 2025, current)", "current/n356_i.pdf", "FORM N-356 (REV. 2025) EARNED INCOME TAX CREDIT"),
    ([371], "2018", "schedule-x", "Schedule X (Form N-11/N-15), Tax Credits for Hawaii Residents (Rev. 2018)", "2018/schx_i.pdf", "SCHEDULE X (FORM N-11/N-15) (REV. 2018) TAX CREDITS FOR HAWAII RESIDENTS 2018"),
    ([372], "2019", "schedule-x", "Schedule X (Form N-11/N-15), Tax Credits for Hawaii Residents (Rev. 2019)", "2019/schx_i.pdf", "SCHEDULE X (FORM N-11/N-15) (REV. 2019)"),
    ([373], "2020", "schedule-x", "Schedule X (Form N-11/N-15), Tax Credits for Hawaii Residents (Rev. 2020)", "2020/schx_i.pdf", "SCHEDULE X (FORM N-11/N-15) (REV. 2020)"),
    ([374], "2021", "schedule-x", "Schedule X (Form N-11/N-15), Tax Credits for Hawaii Residents (Rev. 2021)", "2021/schx_i.pdf", "SCHEDULE X (FORM N-11/N-15) (REV. 2021)"),
    ([378], "2022", "schedule-x", "Schedule X (Form N-11/N-15), Tax Credits for Hawaii Residents (Rev. 2022)", "2022/schx_i.pdf", "SCHEDULE X (FORM N-11/N-15) (REV. 2022)"),
    ([381], "2023", "schedule-x", "Schedule X (Form N-11/N-15), Tax Credits for Hawaii Residents (Rev. 2023)", "2023/schx_i.pdf", "SCHEDULE X (FORM N-11/N-15) (REV. 2023)"),
    ([384], "2025", "schedule-x", "Schedule X (Form N-11/N-15), Tax Credits for Hawaii Residents (Rev. 2025, current)", "current/schx_i.pdf", "SCHEDULE X (FORM N-11/N-15) (REV. 2025)"),
]:
    doc(rows, "hi", F, f"dotax/ty{ty}/{tail}", title, HIF + file, agency="dotax", ty=ty,
        subtype="instructions" if "instructions" in tail else "form", first=first)
doc([370], "hi", F, "dotax/ty2025/tax-rate-schedules-page", "Tax Rate Schedules For Taxable Years Beginning After December 31, 2024 (DOTAX page)",
    "https://tax.hawaii.gov/forms/d_25table-on/d_25table-on_p13/", agency="dotax", fmt="html", ty="2025", subtype="tax_rate_schedule",
    first="Tax Rate Schedules For Taxable Years Beginning After December 31, 2024")
doc([388], "hi", F, "dotax/ty2018/tax-rate-schedules-page", "Tax Rate Schedules For Taxable Years Beginning After December 31, 2017 (DOTAX page)",
    "https://tax.hawaii.gov/forms/d_18table-on/d_18table-on_p13/", agency="dotax", fmt="html", ty="2018", subtype="tax_rate_schedule",
    first="Tax Rate Schedules For Taxable Years Beginning After December 31, 2017")
doc([386], "hi", G, "dotax/announcements/2023-04", "Tax Announcement No. 2023-04, Act 163 Tax Law Changes",
    "https://files.hawaii.gov/tax/news/announce/ann23-04.pdf", agency="dotax", subtype="announcement", first="STATE OF HAWAI'I DEPARTMENT OF TAXATION ... ANNOUNCEMENT NO. 2023-04")
doc([387], "hi", G, "dotax/act-115-refund", "Act 115 Refund (DOTAX page)",
    "https://tax.hawaii.gov/act-115-ref/", agency="dotax", fmt="html", subtype="agency_page", first="Act 115 Refund | Department of Taxation")
HILEG = "https://data.capitol.hawaii.gov/"
doc([368], "hi", L, "bills/2024/hb2404-cd1", "H.B. No. 2404, H.D. 1, S.D. 1, C.D. 1 (2024), Relating to Taxation",
    HILEG + "sessions/session2024/bills/HB2404_CD1_.HTM", agency="hileg", fmt="html", subtype="bill", first="HB2404 CD1")
doc([369, 396], "hi", L, "bills/2026/sb3125-cd1", "S.B. No. 3125, C.D. 1 (2026), enacted as Act 24, SLH 2026",
    HILEG + "sessions/session2026/bills/SB3125_CD1_.HTM", agency="hileg", fmt="html", subtype="bill", first="SB3125 CD1")
doc([397], "hi", L, "bills/2022/sb514-cd2", "S.B. No. 514, S.D. 1, H.D. 1, C.D. 2 (2022), Relating to Taxation",
    HILEG + "sessions/session2022/bills/SB514_CD2_.pdf", agency="hileg", subtype="bill", first="THE SENATE 514 THIRTY-FIRST LEGISLATURE ... CD. 2 A BILL FOR AN ACT RELATING")
doc([398], "hi", L, "session-laws/2023/act-163", "Act 163, Session Laws of Hawaii 2023 (H.B. No. 954, Relating to Taxation)",
    HILEG + "slh/Years/SLH2023/SLH2023_Act163.pdf", agency="hileg", subtype="session_law", first="ACT 163 H.B. NO. 954 A Bill for an Act Relating to Taxation")
doc([395], "hi", L, "571-2", "Hawaii Revised Statutes Section 571-2, Definitions (Family Courts)",
    HILEG + "hrscurrent/Vol12_Ch0501-0588/HRS0571/HRS_0571-0002.htm", agency="hileg", fmt="html", subtype="statute_section", first="HRS 571-2 Definitions")

# ---------------------------------------------------------------- EXTRACT-MANIFEST paths
# The May 2026 source-discovery manifests carry citation paths with underscore segments
# (us-az/form/individual_income_tax_forms/azdor.gov/...), which the citation-path grammar rejects.
# A document answering an EXTRACT-MANIFEST row keeps that manifest's path with the slug rule applied
# (citation_segment on every hierarchy segment), the convention of the wave-6 tax-ok-wv run; the
# decisions file maps each bundle path to its new path.
EXTRACT_MANIFEST_ROWS = set(range(112, 136)) | set(range(167, 206)) | set(range(281, 291)) | set(range(357, 367))
MAY_MANIFESTS = {
    "az": "manifests/us-az-individual-income-tax-forms.yaml",
    "ca": "manifests/us-ca-official-forms.yaml",
    "ct": "manifests/us-ct-individual-income-tax-forms.yaml",
    "hi": "manifests/us-hi-individual-income-tax-forms.yaml",
}


def _slug_path(path: str) -> str:
    from axiom_corpus.corpus.citation_segment import citation_segment

    head, tail = path.split("/")[:2], path.split("/")[2:]
    return "/".join(head + [citation_segment(segment) for segment in tail])


def _apply_may_manifest_paths() -> None:
    by_url: dict[str, dict[str, str]] = {}
    for st, rel in MAY_MANIFESTS.items():
        for d in yaml.safe_load((ROOT / rel).read_text())["documents"]:
            by_url.setdefault(st, {})[d["source_url"]] = d["citation_path"]
    for entry in DOCS:
        if not EXTRACT_MANIFEST_ROWS.intersection(entry["rows"]):
            continue
        old = by_url.get(entry["st"], {}).get(entry["source_url"])
        if not old:
            continue
        new = _slug_path(old)
        if new == old:
            continue
        entry["citation_path"] = new
        entry["source_id"] = f"{entry['jurisdiction']}-w6-{_slug(new.split('/', 2)[2])}"[:200]
        entry["metadata"]["may_2026_manifest"] = MAY_MANIFESTS[entry["st"]]
        entry["metadata"]["may_2026_manifest_path"] = old


_apply_may_manifest_paths()

# ---------------------------------------------------------------- rows not extracted here
# row -> (status, scope "jur/class/version", citation path, official url, note).
# ``None`` official url means the bundle address. Held scopes are verified against the
# provisions on disk (or the open PR named in OPEN_PR_SCOPES) by --decisions.
AL40 = "us-al/statute/2026-09-14-income-tax-chapter-r2-us-al-title-40"
AL16 = "us-al/statute/2026-10-06-w6-income-tax-statute-al-us-al-title-16"
AZ43 = "us-az/statute/2026-09-14-income-tax-chapter-us-az-title-43"
CARTC = "us-ca/statute/2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7"
CO39 = "us-co/statute/2026-07-19-rulespec-us-co-title-39-consolidated"
GA48 = "us-ga/statute/2026-07-21-ga-ocga-title-48-release86-us-ga-title-48"
GASL = "us-ga/statute/2026-07-21-ga-pit-session-laws"
HI235 = "us-hi/statute/2026-07-16-pit-east-us-hi-volume-04-chapter-235"
DC47 = "us-dc/statute/2026-09-26-codified-title-47"
OPEN_PR_SCOPES = {DC47: ("ingest/dc-title-47-current-2026-09-26", "#753")}
# Scopes locked on main whose bytes are not on the local disk; their provisions are read from the
# commit that ingested them (before the lock switch, b33d5bf08).
GIT_SCOPES = {"us-ca/form/2026-09-23-ca-2025-ftb-3514": "c643c9ec6"}
LEXIS_AR = ("OUTREACH", "", "", None, "The official Arkansas Code is published only through LexisNexis "
            "(advance.lexis.com, robot check; arkleg.state.ar.us links there); recorded blocked in "
            "docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md and not retried. The mirror is not used.")
HELD: dict[int, tuple[str, str, str, str | None, str]] = {
    0: ("ALREADY-HELD", AL40, "us-al/statute/40-8-1", None, "ALISON Code of Alabama root page; PolicyEngine cites it for Ala. Code 40-8-1(b)(3), held in the Title 40 scope"),
    1: ("ALREADY-HELD", AL40, "us-al/statute/40-18-19", None, "ALISON section page 40-18-19"),
    16: ("ALREADY-HELD", AL40, "us-al/statute/40-18-15", "https://alison.legislature.state.al.us/code-of-alabama?section=40-18-15", "collegecounts529.com is the plan manager's site (not the publisher of law); the deduction it describes is Ala. Code 40-18-15 (contributions to the Alabama College Education Savings Program, Chapter 33C of Title 16), held from ALISON"),
    17: ("PRESENT", AL16, "us-al/statute/16-33C-16", "https://alison.legislature.state.al.us/code-of-alabama?section=16-33C-16", "Justia mirror of Ala. Code 16-33C-16; Title 16 taken from ALISON (adapter at title grain). The section is the PACT appropriation section; the 529 deduction itself is 40-18-15 (held)"),
    18: ("ALREADY-HELD", AL40, "us-al/statute/40-18-14.2", "https://alison.legislature.state.al.us/code-of-alabama?section=40-18-14.2", "Justia mirror of Ala. Code 40-18-14.2; official ALISON text held"),
    19: ("ALREADY-HELD", AL40, "us-al/statute/40-18-14", "https://alison.legislature.state.al.us/code-of-alabama?section=40-18-14", "Justia mirror of Ala. Code 40-18-14; official ALISON text held"),
    20: ("ALREADY-HELD", AL40, "us-al/statute/40-18-21", "https://alison.legislature.state.al.us/code-of-alabama?section=40-18-21", "Justia mirror of Ala. Code 40-18-21; official ALISON text held"),
    106: ("ABSENT", "", "", "https://www.dfa.arkansas.gov/wp-content/uploads/TaxBrackets_2014.pdf", "The 2014 brackets sheet is gone: the old /offices/incomeTax path and the wp-content names TaxBrackets_2014.pdf, Tax_Brackets_2014.pdf, TaxBrackets2014.pdf and 2014_Tax_Brackets.pdf answer 404 (2026-10-06). The 2014 long booklet with tax tables (row LongBookwTaxTables_2014.pdf) is taken in us-ar/form/2026-10-06-w6-income-tax-forms-ar"),
    133: ("ALREADY-HELD", "us-az/form/2026-09-15-income-tax-forms-ty2025", "us-az/form/azdor/ty2025/form-140-instructions", "https://azdor.gov/sites/default/files/document/FORMS_INDIVIDUAL_2025_140i.pdf", "same file taken by wave 5 (open PR #716, scope on disk)"),
    149: ("ALREADY-HELD", AZ43, "us-az/statute/43-1022", None, "azleg.gov ARS section page"),
    150: ("ALREADY-HELD", AZ43, "us-az/statute/43-1042", None, "azleg.gov ARS section page"),
    151: ("ALREADY-HELD", AZ43, "us-az/statute/43-1072", None, "azleg.gov ARS section page"),
    152: ("ALREADY-HELD", AZ43, "us-az/statute/43-1073", None, "azleg.gov ARS section page"),
    153: ("ALREADY-HELD", AZ43, "us-az/statute/43-1088", None, "azleg.gov ARS section page"),
    158: ("ALREADY-HELD", AZ43, "us-az/statute/43-1011", "https://www.azleg.gov/ars/43/01011.htm", "azleg.gov viewdocument wrapper of ARS 43-1011"),
    159: ("ALREADY-HELD", AZ43, "us-az/statute/43-1023", "https://www.azleg.gov/ars/43/01023.htm", "azleg.gov viewdocument wrapper of ARS 43-1023"),
    160: ("ALREADY-HELD", AZ43, "us-az/statute/43-1041", "https://www.azleg.gov/ars/43/01041.htm", "azleg.gov viewdocument wrapper of ARS 43-1041"),
    161: ("ALREADY-HELD", AZ43, "us-az/statute/43-1072.01", "https://www.azleg.gov/ars/43/01072-01.htm", "azleg.gov viewdocument wrapper of ARS 43-1072.01"),
    162: ("ALREADY-HELD", AZ43, "us-az/statute/43-1072", "https://www.azleg.gov/ars/43/01072.htm", "azleg.gov viewdocument wrapper of ARS 43-1072"),
    163: ("ALREADY-HELD", AZ43, "us-az/statute/43-1073.01", "https://www.azleg.gov/ars/43/01073-01.htm", "azleg.gov viewdocument wrapper of ARS 43-1073.01"),
    200: ("ALREADY-HELD", "us-ca/form/2026-09-15-income-tax-forms-ty2025", "us-ca/form/ftb/ty2025/form-540", "https://www.ftb.ca.gov/forms/2025/2025-540.pdf", "same file taken by wave 5 (open PR #716, scope on disk)"),
    201: ("ALREADY-HELD", "us-ca/form/2026-09-15-income-tax-forms-ty2025", "us-ca/form/ftb/ty2025/form-540-booklet", "https://www.ftb.ca.gov/forms/2025/2025-540-booklet.pdf", "the 2025 Personal Income Tax Booklet is held in its PDF edition (wave 5, open PR #716); the HTML edition of the same booklet was not re-taken"),
    206: ("ALREADY-HELD", "us-ca/form/2026-09-23-ca-2025-ftb-3514", "us-ca/form/individual-income-tax/2025/3514-instructions", "https://www.ftb.ca.gov/forms/2025/2025-3514-booklet.pdf", "manifests/us-ca-2025-ftb-3514-booklet.yaml was extracted on 2026-09-23 (commit c643c9ec6) into this scope, locked on main (.axiom/corpus-locks/us-ca/form/2026-09-23-ca-2025-ftb-3514.json); same PDF (sha256 9096ff0e...)"),
    207: ("OUTREACH", "", "", "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=24344", "Justia mirror of Cal. Rev. & Tax. Code 24344 (corporation tax, Part 11, outside the held Parts 10 and 10.2); leginfo.legislature.ca.gov answers HTTP 403 with a Cloudflare 'Just a moment...' challenge to the corpus client (2026-10-06)"),
    208: ("OUTREACH", "", "", None, "leginfo.legislature.ca.gov answers HTTP 403 with a Cloudflare 'Just a moment...' challenge (2026-10-06, probed once); AB 178 (2021, budget act chapter) bill PDF not fetchable; not worked around"),
    209: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17043", None, "leginfo blocked today (Cloudflare challenge); the section is held from the 2026-09-14 leginfo run"),
    210: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17052", None, "leginfo section page (held from the 2026-09-14 run)"),
    211: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17052", None, "leginfo section page 17052 (trailing dot); held"),
    212: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17052.1", None, "leginfo section page (held)"),
    213: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17052.2", None, "leginfo section page (held)"),
    214: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17052.2", None, "leginfo section page 17052.2 (trailing dot); held"),
    215: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17052.6", None, "leginfo section page 17052.6 (trailing dot); held"),
    216: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17053.5", None, "leginfo section page (held)"),
    217: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17062", None, "leginfo section page (held)"),
    218: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17073.5", None, "leginfo section page (held)"),
    219: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17077", None, "leginfo section page (held)"),
    220: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17041", None, "leginfo section page 17041 (trailing dot); held"),
    221: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17054", None, "leginfo section page 17054 (trailing dot); held"),
    222: ("ALREADY-HELD", CARTC, "us-ca/statute/rtc/17054.1", None, "leginfo section page 17054.1 (trailing dot); held"),
    233: ("OUT-OF-SCOPE", "", "", None, "FTB Forms and Publications Search confirmation page (a search tool, no rule text); the forms it lists are taken individually"),
    234: ("OUTREACH", "", "", None, "San Francisco Administrative Code ch. 12S (Working Families Credit) is published only by American Legal Publishing (codelibrary.amlegal.com), which answers HTTP 403 to the corpus client (2026-10-06); no city-hosted official text found"),
    235: ("ALREADY-HELD", "us-co/regulation/2026-09-14-income-tax-regulations-r2", "us-co/regulation/1-ccr-201-2", "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleVersionId=12424", "1 CCR 201-2 held (wave-4 -r2 scope, grammar-fixed paths)"),
    250: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-104", "https://olls.info/crs/crs2025-title-39.htm", "CRS 2025 Title 39 (OLLS official compilation) is held section by section from the HTML edition of the same publication; PolicyEngine cites 39-22-104(3)(p.5) and (p.7)"),
    273: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-104", "https://olls.info/crs/crs2025-title-39.htm", "Lexis C.R.S. 39-22-104(4); Colorado hosts the official CRS at olls.info, held"),
    274: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-104", "https://olls.info/crs/crs2025-title-39.htm", "Lexis C.R.S. 39-22-104(4)(i)(II)(B); official CRS held"),
    275: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-544", "https://olls.info/crs/crs2025-title-39.htm", "Lexis C.R.S. 39-22-544(4); official CRS held"),
    276: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-129", "https://olls.info/crs/crs2025-title-39.htm", "Lexis C.R.S. 39-22-129; official CRS held"),
    277: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-104", "https://olls.info/crs/crs2025-title-39.htm", "Lexis C.R.S. 39-22-104(4)(y)(II)(B); official CRS held"),
    278: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-123.5", "https://olls.info/crs/crs2025-title-39.htm", "Lexis C.R.S. 39-22-123.5; official CRS held"),
    279: ("ALREADY-HELD", CO39, "us-co/statute/39/39-22-119", "https://olls.info/crs/crs2025-title-39.htm", "Lexis teaser of C.R.S. title 39 art. 22 part 1, subsection (1.7), cited for the child care credit match (39-22-119(1.7)); official CRS held"),
    280: ("ALREADY-HELD", "us-co/statute/2026-07-13-us-co-tax-credit-session-laws-r2026-07-19-expression-date", "us-co/statute/session-laws/2024/hb24-1134", None, "PATH-ONLY container us-co/statute/session-laws/2024: no row carries the container path itself; its 2024 session laws (HB24-1134, HB24-1311) are held"),
    289: ("ALREADY-HELD", "us-ct/form/2026-09-15-income-tax-forms-ty2025", "us-ct/form/drs/ty2025/ct-1040-instructions", "https://portal.ct.gov/-/media/drs/forms/2025/income/2025-ct-1040-instructions_1225.pdf", "same file (with Sitecore rev/hash query) taken by wave 5 (open PR #716, scope on disk)"),
    291: ("ALREADY-HELD", "us-ct/regulation/2026-09-14-income-tax-regulations-r2", "us-ct/regulation/rcsa/12/income-tax", "https://eregulations.ct.gov/eRegsPortal/Browse/getDocument?guid=%7B80F3E757-0000-CC89-BCB7-C50B40EC8ECF%7D", "RCSA Title 12 Income Tax held (wave-4 -r2 scope)"),
    299: ("ALREADY-HELD", "us-ct/regulation/2026-09-14-income-tax-regulations-r2", "us-ct/regulation/rcsa/12/income-tax/12-701-a-20-2", "https://eregulations.ct.gov/eRegsPortal/Browse/getDocument?guid=%7B80F3E757-0000-CC89-BCB7-C50B40EC8ECF%7D", "Justia mirror of RCSA 12-701(a)(20)-2; official eRegulations text held"),
    300: ("ALREADY-HELD", "us-ct/regulation/2026-09-14-income-tax-regulations-r2", "us-ct/regulation/rcsa/12/income-tax/12-701-a-20-3", "https://eregulations.ct.gov/eRegsPortal/Browse/getDocument?guid=%7B80F3E757-0000-CC89-BCB7-C50B40EC8ECF%7D", "Justia mirror of RCSA 12-701(a)(20)-3; official eRegulations text held"),
    306: ("ALREADY-HELD", DC47, "us-dc/statute/47/47-1806.15", None, "held in the D.C. title 47 codified scope of open PR #753 (branch ingest/dc-title-47-current-2026-09-26); the 2026-07-16 title-47 scope lacks the section"),
    307: ("ALREADY-HELD", DC47, "us-dc/statute/47/47-1806.17", None, "held in the D.C. title 47 codified scope of open PR #753"),
    308: ("ALREADY-HELD", DC47, "us-dc/statute/47/chapter-18/subchapter-iii", None, "held in the D.C. title 47 codified scope of open PR #753 (subchapter container and its sections)"),
    315: ("ALREADY-HELD", "us-de/statute/2026-09-14-income-tax-chapter-r2-us-de-title-30-chapter-11", "us-de/statute/30/11/subchapter-i", None, "delcode subchapter page; sections held"),
    316: ("ALREADY-HELD", "us-de/statute/2026-09-14-income-tax-chapter-r2-us-de-title-30-chapter-11", "us-de/statute/30/11/subchapter-ii", None, "delcode subchapter page; sections held"),
    338: ("ALREADY-HELD", "us-ga/regulation/2026-09-14-income-tax-regulations", "us-ga/regulation/560-7/560-7-4-.02", "https://rules.sos.ga.gov/Download_pdf.aspx?st=GASOS&year=2026&dept=560", "the text of Rule 560-7-4-.04 (Georgia Higher Education Savings Plan) is held, but inside the 560-7-4-.02 row: the wave-4 labeled-section parse merged rules .03 to .05 into .02 (data-quality finding; a re-split is a follow-up)"),
    341: ("ALREADY-HELD", GASL, "us-ga/statute/session-laws/2024/hb1021", "https://gov.georgia.gov/document/2024-signed-legislation/hb-1021/download", "legis.ga.gov document 20232024/229350 is HB 1021 (2024, as passed); the signed act is held; legis.ga.gov serves only its JavaScript application shell to a plain GET"),
    342: ("ALREADY-HELD", GASL, "us-ga/statute/session-laws/2026/hb463", "https://gov.georgia.gov/document/2026-signed-legislation/hb-463/download", "legis.ga.gov document 20252026/249080 is HB 463 (2025-2026); the signed act is held"),
    347: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7-1", None, "Justia mirror of O.C.G.A. 48-7-1; held in the O.C.G.A. title 48 scope"),
    348: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7-20", None, "Justia mirror of O.C.G.A. 48-7-20; held"),
    349: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7-26", None, "Justia mirror of O.C.G.A. 48-7-26; held"),
    350: ("OUTREACH", "", "", None, "O.C.G.A. 48-7-27.1 is not in the held title-48 release (release 86); the official O.C.G.A. is published only through LexisNexis; the Justia mirror is not used"),
    351: ("ALREADY-HELD", GASL, "us-ga/statute/session-laws/2025/hb136", "https://gov.georgia.gov/document/2025-signed-legislation/hb-136/download", "LegiScan mirror of HB 136 (2025) enrolled; the signed act from the Governor's office is held"),
    352: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7A-3", None, "Lexis O.C.G.A. 48-7A-3(b); held"),
    353: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7-26", None, "Lexis O.C.G.A. 48-7-26 (node ABWAALAADAAL, personal exemptions); held"),
    354: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7-27", None, "Lexis O.C.G.A. 48-7-27(a)(1)(B); held"),
    355: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7-27", None, "Lexis O.C.G.A. 48-7-27(a)(5); held"),
    356: ("ALREADY-HELD", GA48, "us-ga/statute/48/48-7-29.10", None, "Lexis O.C.G.A. 48-7-29.10; held"),
    367: ("ALREADY-HELD", HI235, "us-hi/statute/235-2.4", None, "data.capitol.hawaii.gov HRS 235-2.4 page; held"),
    385: ("ALREADY-HELD", "us-hi/statute/2026-07-13-recovery", "us-hi/statute/235-55.6", "https://data.capitol.hawaii.gov/hrscurrent/Vol04_Ch0201-0257/HRS0235/HRS_0235-0055_0006.htm", "DOTAX 'Unofficial Compilation' of HRS chapter 235 (PolicyEngine cites page 47, HRS 235-55.6); the Legislature's official text of the section is held"),
    389: ("ALREADY-HELD", HI235, "us-hi/statute/235-7", None, "Justia mirror of HRS 235-7; held"),
    390: ("ALREADY-HELD", HI235, "us-hi/statute/235-2.4", None, "Justia mirror of HRS 235-2.4; held"),
    391: ("ABSENT", "", "", "https://files.hawaii.gov/tax/forms/2021/n311_i.pdf", "DocHub filler copy of the 2021 Form N-311; DOTAX no longer posts the 2021 N-311 (files.hawaii.gov/tax/forms/2021/n311_i.pdf, n311.pdf, n311ins.pdf, n311_f.pdf answer 404 on 2026-10-06; the 2022, 2023 and current editions are taken)"),
    392: ("ALREADY-HELD", HI235, "us-hi/statute/235-2.4", "https://data.capitol.hawaii.gov/hrscurrent/Vol04_Ch0201-0257/HRS0235/HRS_0235-0002_0004.htm", "www.capitol.hawaii.gov answers HTTP 403 (Cloudflare 'Attention Required') on 2026-10-06; the Legislature's data host serves the same HRS file and the section is held from it"),
    393: ("ALREADY-HELD", HI235, "us-hi/statute/235-51", "https://data.capitol.hawaii.gov/hrscurrent/Vol04_Ch0201-0257/HRS0235/HRS_0235-0051.htm", "www.capitol.hawaii.gov blocked (Cloudflare); held from the Legislature's data host"),
    394: ("ALREADY-HELD", HI235, "us-hi/statute/235-55.75", "https://data.capitol.hawaii.gov/hrscurrent/Vol04_Ch0201-0257/HRS0235/HRS_0235-0055_0007_0005.htm", "www.capitol.hawaii.gov blocked (Cloudflare); HRS 235-55.75 held from the Legislature's data host"),
}
for _row in (97, 98, 99, 100, 101, 102, 103, 104, 105, 107, 108, 109, 110, 111):
    HELD[_row] = LEXIS_AR

# Notes for PRESENT rows whose official address differs from the bundle address.
PRESENT_NOTES = {
    2: "ADOR form landing page; the PDF it links (2021 Form 40) is taken",
    3: "ADOR UltraViewer page; the PDF it frames is taken",
    4: "ADOR UltraViewer page; the PDF it frames is taken",
    5: "ADOR UltraViewer page; the PDF it frames is taken",
    6: "ADOR UltraViewer page; the PDF it frames is taken",
    7: "ADOR UltraViewer page; the PDF it frames is taken",
    8: "ADOR UltraViewer page; the PDF it frames is taken",
    9: "ADOR UltraViewer page; the PDF it frames is taken",
    10: "ADOR UltraViewer page; the PDF it frames is taken",
    21: "taxformfinder.org mirror of the 2023 Form 40; the ADOR file is taken",
    290: "the bundle address (CT-1040-Instructions_1224.pdf) now serves the DRS 404 page; the 2024 CT-1040 instructions are taken from their current address",
    301: "the bare-host address serves the same PDF; taken from www.cga.ct.gov",
    328: "DOR FillableForms viewer; the PDF it loads (2022GA500.pdf) is taken",
    330: "the address without /download serves the same PDF (same size); taken from the /download address",
    335: "redirects to the IT-511 booklet page, which is taken",
    339: "legis.ga.gov serves only its JavaScript application to a plain GET; HB 1437 (2022, as passed) is taken from the Governor's signed-legislation copy",
    340: "legis.ga.gov serves only its JavaScript application to a plain GET; HB 162 (2023, as passed) is taken from the Governor's signed-legislation copy",
    343: "legis.ga.gov serves only its JavaScript application to a plain GET; HB 1015 (2024, as passed) is taken from the Governor's signed-legislation copy",
    344: "taxsim.nber.org repost of the 2022 IT-511 booklet; the DOR file is taken",
    345: "taxsim.nber.org repost of the 2023 IT-511 booklet; the DOR file is taken",
    346: "zillionforms.com repost of the 2021 Form 500 instructions (the 2021 IT-511 booklet); the DOR file is taken",
    370: "dev1-tax.hawaii.gov is a DOTAX development host; the production page on tax.hawaii.gov is taken",
    396: "www.capitol.hawaii.gov blocked (Cloudflare); the measure's conference draft (enacted as Act 24, SLH 2026) is taken from the Legislature's data host",
    397: "www.capitol.hawaii.gov blocked (Cloudflare); the same bill PDF is taken from the Legislature's data host",
    398: "www.capitol.hawaii.gov blocked (Cloudflare); the same session-law PDF is taken from the Legislature's data host",
    395: "www.capitol.hawaii.gov blocked (Cloudflare); the same HRS section file is taken from the Legislature's data host",
    251: "Justia mirror of Colo. Const. art. X; the official text is the OLLS compilation of the Constitution (CRS 2025 title 00), taken one row per page",
}

# Notes for rows whose starting action was a block or a dead link, by host.
ACTION_HOST_NOTES = {
    ("BLOCKED-CHECK", "tax.colorado.gov"): "tax.colorado.gov answers the corpus client with HTTP 403 (CloudFront) and serves the extractor's built-in Chrome user-agent retry (documented 2026-09-14); no impersonation",
    ("BLOCKED-CHECK", "www.ftb.ca.gov"): "ftb.ca.gov answered the corpus client with HTTP 200 on 2026-10-06; the triage 403 did not reproduce",
    ("DEAD-LINK", "www.cga.ct.gov"): "the triage URLError is cga.ct.gov's missing Go Daddy G2 intermediate; fetched with the committed data/certs/state-tax-statute-ca-bundle.pem, TLS verified",
    ("DEAD-LINK", "cga.ct.gov"): "the triage URLError is cga.ct.gov's missing Go Daddy G2 intermediate; fetched with the committed CA bundle, TLS verified",
}


def _version(st: str, family: str) -> str:
    return f"2026-10-06-w6-{family}-{st}"


def _manifest_path(st: str, family: str) -> Path:
    return MANIFESTS / f"us-{st}-income-tax-w6-{FAMILIES[family][1]}.yaml"


def write_manifests() -> list[Path]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in DOCS:
        groups.setdefault((entry["st"], entry["family"]), []).append(entry)
    written = []
    for (st, family), entries in sorted(groups.items()):
        documents = []
        for e in entries:
            d = {k: e[k] for k in ("source_id", "jurisdiction", "document_class", "title", "source_url",
                                     "source_format", "source_as_of", "expression_date", "citation_path")}
            if e["extraction"]:
                d["extraction"] = e["extraction"]
            if e.get("request"):
                d["request"] = e["request"]
            d["metadata"] = dict(e["metadata"], wave6_work_order_rows=e["rows"])
            documents.append(d)
        payload = {
            "version": _version(st, family),
            "metadata": {
                "work_order": "docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-al-hi.csv",
                "run_note": RUN_NOTE,
                "generator": "scripts/build_w6_tax_al_hi_manifests.py",
                "jurisdiction_name": STATE_FAMILY_SOURCE[st],
            },
            "documents": documents,
        }
        path = _manifest_path(st, family)
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120))
        written.append(path)
    return written


def _held_paths(scope: str) -> set[str]:
    jur, cls, version = scope.split("/", 2)
    if scope in OPEN_PR_SCOPES or scope in GIT_SCOPES:
        import subprocess

        ref = GIT_SCOPES.get(scope) or f"origin/{OPEN_PR_SCOPES[scope][0]}"
        text = subprocess.run(
            ["git", "show", f"{ref}:data/corpus/provisions/{jur}/{cls}/{version}.jsonl"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
        lines = text.splitlines()
    else:
        lines = (CORPUS_BASE / "provisions" / jur / cls / f"{version}.jsonl").read_text().splitlines()
    return {json.loads(line)["citation_path"] for line in lines if line.strip()}


def write_decisions(work_order: Path) -> dict[str, int]:
    rows = list(csv.DictReader(work_order.open()))
    by_row: dict[int, dict[str, Any]] = {}
    for entry in DOCS:
        for r in entry["rows"]:
            if r in by_row:
                raise SystemExit(f"row {r} mapped twice")
            by_row[r] = entry
    cache: dict[str, set[str]] = {}
    out = []
    counts: dict[str, int] = {}
    for i, r in enumerate(rows):
        if i in by_row:
            e = by_row[i]
            scope = f"{e['jurisdiction']}/{e['document_class']}/{_version(e['st'], e['family'])}"
            status, path, url = "PRESENT", e["citation_path"], e["source_url"]
            note = PRESENT_NOTES.get(i, "")
            host = (r["bundle_url"].split("/") + ["", "", ""])[2]
            host_note = ACTION_HOST_NOTES.get((r["action"], host))
            if host_note:
                note = f"{note}; {host_note}" if note else host_note
            if r["action"] == "EXTRACT-MANIFEST" and r["bundle_path"] and r["bundle_path"] != path:
                note = (note + "; " if note else "") + (
                    f"manifest {r['manifest_on_main']} path {r['bundle_path']} fails the citation-path grammar "
                    f"(underscore segment); slug rule applied: {path}")
        elif i in HELD:
            status, scope, path, url, note = HELD[i]
            url = url or r["bundle_url"]
        else:
            status, scope, path, url, note = "SKIPPED", "", "", r["bundle_url"], "not reached in the time box"
        if status in {"PRESENT", "ALREADY-HELD"}:
            if scope not in cache:
                try:
                    cache[scope] = _held_paths(scope)
                except (FileNotFoundError, Exception) as exc:  # noqa: BLE001
                    raise SystemExit(f"row {i}: scope {scope} unreadable: {exc}") from exc
            if path not in cache[scope]:
                raise SystemExit(f"row {i}: {path} not in {scope}")
        counts[status] = counts.get(status, 0) + 1
        out.append({
            "id": r["id"], "jurisdiction": r["jurisdiction"], "programs": r["programs"], "action": r["action"],
            "new_status": status, "scope_version": scope, "citation_path": path, "official_url": url or "",
            "note": note,
        })
    with DECISIONS.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "jurisdiction", "programs", "action", "new_status",
                                                "scope_version", "citation_path", "official_url", "note"])
        writer.writeheader()
        writer.writerows(out)
    return counts


QUEUE = MANIFESTS / "tax-agent-queue.yaml"
QUEUE_KEY = "w6_bundle_gap_closure"


def update_queue(work_order: Path) -> list[str]:
    """Insert (or replace) a ``w6_bundle_gap_closure`` block after ``target_scope`` in the
    first ``states`` row of each jurisdiction of this group. Text edit, so the rows of the
    other wave-6 tax groups and every other key stay byte-identical."""
    decisions = list(csv.DictReader(DECISIONS.open()))
    work_rows = list(csv.DictReader(work_order.open()))
    lines = QUEUE.read_text().splitlines(keepends=True)
    touched = []
    for st in sorted(STATE_FAMILY_SOURCE):
        jur = f"us-{st}"
        mine = [d for d in decisions if d["jurisdiction"] == jur]
        counts: dict[str, int] = {}
        for d in mine:
            counts[d["new_status"]] = counts.get(d["new_status"], 0) + 1
        scopes = sorted({d["scope_version"] for d in mine if d["new_status"] == "PRESENT"})
        block = [
            f"  {QUEUE_KEY}:\n",
            "    work_order: docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-al-hi.csv\n",
            f"    run_note: {RUN_NOTE}\n",
            "    decisions: docs/ingest-runs/2026-10-06-w6-tax-al-hi-decisions.csv\n",
            f"    work_order_rows: {sum(1 for r in work_rows if r['jurisdiction'] == jur)}\n",
            "    status_counts:\n",
            *[f"      {k}: {v}\n" for k, v in sorted(counts.items())],
            "    new_scopes:\n",
            *[f"    - {scope}\n" for scope in scopes],
        ]
        start = next(i for i, line in enumerate(lines) if line.rstrip("\n") == f"- jurisdiction: {jur}")
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("- "))
        # drop an earlier block of this key
        i = start
        while i < end:
            if lines[i].startswith(f"  {QUEUE_KEY}:"):
                j = i + 1
                while j < end and lines[j].startswith("    "):
                    j += 1
                del lines[i:j]
                end -= j - i
                continue
            i += 1
        ts = next(i for i in range(start, end) if lines[i].startswith("  target_scope:"))
        k = ts + 1
        while k < end and lines[k].startswith("    "):
            k += 1
        lines[k:k] = block
        touched.append(jur)
    QUEUE.write_text("".join(lines))
    return touched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--decisions", action="store_true")
    parser.add_argument("--queue", action="store_true", help="update manifests/tax-agent-queue.yaml from the decisions")
    parser.add_argument("--work-order", type=Path)
    parser.add_argument("--only", action="append", default=[], help="state code (al, ar, ...) for manifest mode")
    args = parser.parse_args()
    if args.queue:
        if not args.work_order:
            raise SystemExit("--queue needs --work-order")
        print(update_queue(args.work_order))
        return
    if args.decisions:
        if not args.work_order:
            raise SystemExit("--decisions needs --work-order")
        print(json.dumps(write_decisions(args.work_order), sort_keys=True))
        return
    for path in write_manifests():
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
