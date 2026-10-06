"""Wave 6, group tax-ia-mi: manifests and decisions for the program-bundle gap rows of
Iowa, Idaho, Illinois, Indiana, Kansas, Kentucky, Louisiana, Massachusetts, Maryland, Maine
and Michigan (state individual income tax, EITC and CTC documents).

Static tables only: every URL below was fetched and read on 2026-10-06 (corpus user agent;
michigan.gov with the documented chrome120 fallback).  The script writes one
``extract-official-documents`` manifest per (jurisdiction, document class) and, with
``--work-order``, the decisions CSV (one row per work-order row).

    uv run python scripts/build_w6_tax_ia_mi_manifests.py
    uv run python scripts/build_w6_tax_ia_mi_manifests.py --work-order <tax-ia-mi.csv> \
        --decisions docs/ingest-runs/2026-10-06-w6-tax-ia-mi-decisions.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-10-06"
FAMILY = {"form": "income-tax-forms", "guidance": "income-tax-guidance", "statute": "income-tax-statute"}
MANIFEST_SUFFIX = {"form": "forms", "guidance": "guidance", "statute": "statute"}
AUTHORITY = {
    "us-ia": "Iowa Department of Revenue",
    "us-id": "Idaho State Tax Commission",
    "us-il": "Illinois Department of Revenue",
    "us-in": "Indiana Department of Revenue",
    "us-ks": "Kansas Department of Revenue",
    "us-ky": "Kentucky Department of Revenue",
    "us-la": "Louisiana Department of Revenue",
    "us-ma": "Massachusetts Department of Revenue",
    "us-md": "Comptroller of Maryland",
    "us-me": "Maine Revenue Services",
    "us-mi": "Michigan Department of Treasury",
}
MICHIGAN_REQUEST = {"browser_user_agent": True, "browser_impersonation": "chrome120"}
MICHIGAN_NOTE = (
    "michigan.gov answers HTTP 403 to the corpus client and serves the chrome120 fingerprint "
    "(browser fallback documented for this host in the 2026-09-10 WIC, 2026-09-14 LIHEAP and "
    "2026-09-15 wave-5 tax run notes)."
)


def version(jurisdiction: str, document_class: str) -> str:
    return f"{SOURCE_AS_OF}-w6-{FAMILY[document_class]}-{jurisdiction.split('-', 1)[1]}"


# Each document: (jurisdiction, class, source_url, citation_path, title, year or None, subtype,
# options).  ``year`` is the tax year (forms; expression date YYYY-01-01) or None.  ``options``
# may carry ``sel`` (html_content_selector), ``request``, ``ids`` (extra work-order ids joined to
# this document) and ``note``.
DOCS: list[tuple[str, str, str, str, str, int | None, str, dict[str, Any]]] = []


def doc(jur, cls, url, path, title, year=None, subtype=None, **opts):
    DOCS.append((jur, cls, url, path, title, year, subtype or cls, opts))


# ---------------------------------------------------------------- Iowa
IA_EXP = "https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax/1040-expanded-instructions"
doc("us-ia", "guidance", f"{IA_EXP}/iowa-taxable-income",
    "us-ia/guidance/revenue/individual-income-tax/iowa-taxable-income",
    "IA 1040 Expanded Instructions, Line 04: Iowa Taxable Income (instruction year 2025)", None,
    "instructions", sel="main",
    ids=["us-ia/guidance/revenue/individual-income-tax/iowa-taxable-income"])
doc("us-ia", "guidance", "https://revenue.iowa.gov/retirement-income-tax-guidance",
    "us-ia/guidance/revenue/individual-income-tax/retirement-income",
    "Retirement Income Tax Guidance (Iowa Department of Revenue, updated 2025-03-13)", None,
    "guidance", sel="main", ids=["us-ia/guidance/revenue/individual-income-tax/retirement-income"])
for slug, title in [
    ("child-dependent-care-credit", "Line 24: Child and Dependent Care Credit or Early Childhood Development Credit"),
    ("exemption-credits", "Intro 6: Exemption Credits"),
    ("ia-1040-schedule-1", "IA 1040 Schedule 1"),
    ("iowa-earned-income-tax-credit", "Line 25: Iowa Earned Income Tax Credit"),
    ("iowa-tax", "Line 05: Iowa Tax"),
]:
    doc("us-ia", "guidance", f"{IA_EXP}/{slug}", f"us-ia/guidance/revenue/individual-income-tax/{slug}",
        f"IA 1040 Expanded Instructions, {title} (instruction year 2025)", None, "instructions", sel="main")
doc("us-ia", "guidance",
    "https://revenue.iowa.gov/press-release/2024-10-16/idr-announces-2025-individual-income-tax-brackets-and-interest-rates",
    "us-ia/guidance/idr/press-releases/2024-10-16-2025-individual-income-tax-brackets",
    "IDR Announces 2025 Individual Income Tax Brackets and Interest Rates (press release, 2024-10-16)",
    None, "press_release", sel="main")
doc("us-ia", "guidance", "https://content.govdelivery.com/accounts/IACIO/bulletins/3779769",
    "us-ia/guidance/idr/press-releases/2023-2024-individual-income-tax-brackets",
    "IDR Announces 2024 Individual Income Tax Brackets and Interest Rates (Iowa Department of Revenue bulletin)",
    None, "press_release", sel="main",
    note="The Department of Revenue's own bulletin, issued through the State of Iowa GovDelivery account (IACIO).")
doc("us-ia", "guidance",
    "https://www.iowatreasurer.gov/the-treasurers-office/news/treasurer-smith-announces-2025-isave-529-state-tax-deduction-amount",
    "us-ia/guidance/treasurer/news/2025-isave-529-state-tax-deduction-amount",
    "Treasurer Smith Announces 2025 ISave 529 State Tax Deduction Amount (Treasurer of State)", None,
    "press_release", sel="div.main-content-section")
IA_MEDIA = "https://revenue.iowa.gov/media"
doc("us-ia", "form", f"{IA_MEDIA}/2650/download?inline", "us-ia/form/idr/ty2021/ia-1040-instructions-rev-2023-01-03",
    "2021 IA 1040 Instructions (revised 01/03/2023; 'New for 2021')", 2021, "instructions",
    ids=["https://taxsim.nber.org/historical_state_tax_forms/IA/2021/2021%20Expanded%20Instructions_0.pdf"])
doc("us-ia", "form", f"{IA_MEDIA}/2721/download?inline", "us-ia/form/idr/ty2022/ia-1040-instructions-rev-2023-02-20",
    "2022 IA 1040 Instructions (revised 02/20/2023; 'New for 2022')", 2022, "instructions",
    ids=["https://taxsim.nber.org/historical_state_tax_forms/IA/2022/2022%20Expanded%20Instructions_022023.pdf"])
doc("us-ia", "form", f"{IA_MEDIA}/2746/download?inline", "us-ia/form/idr/ty2023/ia-1040",
    "2023 IA 1040 Iowa Individual Income Tax Return", 2023, "return_form")
doc("us-ia", "form", f"{IA_MEDIA}/2748/download?inline", "us-ia/form/idr/ty2023/41-026a-tax-calculation-worksheet-non-joint",
    "2023 Tax Calculation Worksheet, Non-Joint Filers (41-026a, 11/01/2023)", 2023, "worksheet")
doc("us-ia", "form", f"{IA_MEDIA}/2754/download?inline", "us-ia/form/idr/ty2023/41-145-alternate-tax-worksheet",
    "2023 Iowa Alternate Tax Worksheet (41-145, 01/23/2024)", 2023, "worksheet")
doc("us-ia", "form", f"{IA_MEDIA}/4093/download?inline", "us-ia/form/idr/ty2024/41-026a-tax-calculation-worksheet-non-joint",
    "2024 Tax Calculation Worksheet, Non-Joint Filers (41-026a, 05/06/2024)", 2024, "worksheet")
doc("us-ia", "form", f"{IA_MEDIA}/4152/download?inline", "us-ia/form/idr/ty2024/ia-1040-instructions",
    "2024 IA 1040 Instructions", 2024, "instructions")
IA_FILES = "https://revenue.iowa.gov/sites/default/files"
doc("us-ia", "form", f"{IA_FILES}/2021-12/IA6251%2841131%29.pdf", "us-ia/form/idr/ty2021/ia-6251",
    "2021 IA 6251 Iowa Alternative Minimum Tax - Individuals (41-131a, 06/18/2021)", 2021, "schedule")
doc("us-ia", "form", f"{IA_FILES}/2022-01/IA1040%2841-001%29.pdf", "us-ia/form/idr/ty2021/ia-1040",
    "2021 IA 1040 Iowa Individual Income Tax Return (41-001, 10/08/2021)", 2021, "return_form")
doc("us-ia", "form", f"{IA_FILES}/2023-01/2022IA1040%2841001%29.pdf", "us-ia/form/idr/ty2022/ia-1040",
    "2022 IA 1040 Iowa Individual Income Tax Return (41-001, 06/29/2022)", 2022, "return_form")
doc("us-ia", "form", f"{IA_FILES}/2023-01/IA6251%2841131%29.pdf", "us-ia/form/idr/ty2022/ia-6251",
    "2022 IA 6251 Iowa Alternative Minimum Tax - Individuals (41-131a, 05/19/2022)", 2022, "schedule")
doc("us-ia", "form", f"{IA_FILES}/2023-11/IA1041Inst%2863002%29.pdf", "us-ia/form/idr/ty2023/ia-1041-instructions",
    "2023 IA 1041 Iowa Fiduciary Return Instructions (63-002a, 11/09/2023)", 2023, "instructions")
doc("us-ia", "statute", "https://www.legis.iowa.gov/docs/publications/LGE/90/Attachments/SF2442_GovLetter.pdf",
    "us-ia/statute/session-laws/2024/sf2442",
    "Senate File 2442 (90th General Assembly, 2024): enrolled Act as transmitted by the Governor (2024-05-01)", None,
    "session_law", ids=["https://www.legis.iowa.gov/legislation/BillBook?ga=90&ba=SF%202442"],
    note="The BillBook page for SF 2442 displays this PDF (its iframe); the page itself carries no bill text.")

# ---------------------------------------------------------------- Idaho
ID_FORMS = "https://tax.idaho.gov/wp-content/uploads/forms"
ID_FORM_ROWS = [
    ("EFO00086", "09-15-2021", 2021, "form-24", "Form 24 Grocery Credit Refund (EFO00086, 09-15-2021)"),
    ("EFO00086", "12-30-2022", 2022, "form-24", "Form 24 Grocery Credit Refund (EFO00086, 12-30-2022)"),
    ("EFO00088", "09-23-2021", 2021, "form-39r", "Form 39R Resident Supplemental Schedule (EFO00088, 09-23-2021)"),
    ("EFO00088", "12-30-2022", 2022, "form-39r", "Form 39R Resident Supplemental Schedule (EFO00088, 12-30-2022)"),
    ("EFO00088", "03-01-2023", 2022, "form-39r", "Form 39R Resident Supplemental Schedule (EFO00088, 03-01-2023)"),
    ("EFO00088", "09-07-2023", 2023, "form-39r", "Form 39R Resident Supplemental Schedule (EFO00088, 09-07-2023)"),
    ("EFO00088", "08-22-2024", 2024, "form-39r", "Form 39R Resident Supplemental Schedule (EFO00088, 08-22-2024)"),
    ("EFO00089", "09-23-2021", 2021, "form-40", "Form 40 Individual Income Tax Return (EFO00089, 09-23-2021)"),
    ("EFO00089", "12-30-2022", 2022, "form-40", "Form 40 Individual Income Tax Return (EFO00089, 12-30-2022)"),
    ("EFO00089", "08-23-2023", 2023, "form-40", "Form 40 Individual Income Tax Return (EFO00089, 08-23-2023)"),
    ("EFO00093", "09-15-2021", 2021, "form-cg", "Form CG Capital Gains Deduction (EFO00093, 09-15-2021)"),
    ("EFO00093", "05-19-2022", 2022, "form-cg", "Form CG Capital Gains Deduction (EFO00093, 05-19-2022)"),
    ("EFO00093", "08-23-2023", 2023, "form-cg", "Form CG Capital Gains Deduction (EFO00093, 08-23-2023)"),
    ("EFO00093", "09-17-2024", 2024, "form-cg", "Form CG Capital Gains Deduction (EFO00093, 09-17-2024)"),
    ("EIN00046", "11-15-2021", 2021, "individual-income-tax-instructions", "Individual Income Tax Forms and Instructions (EIN00046, 11-15-2021)"),
    ("EIN00046", "03-01-2023", 2022, "individual-income-tax-instructions", "Individual Income Tax General Information and Instructions 2022 (EIN00046, 03-01-2023)"),
    ("EIN00046", "11-06-2023", 2023, "individual-income-tax-instructions", "Individual Income Tax General Information and Instructions 2023 (EIN00046, 11-06-2023)"),
    ("EIN00046", "10-23-2024", 2024, "individual-income-tax-instructions", "Individual Income Tax General Information and Instructions 2024 (EIN00046, 10-23-2024)"),
]
for code, rev, year, slug, title in ID_FORM_ROWS:
    old = f"us-id/form/tax_forms/tax.idaho.gov/wp-content/uploads/forms/{code.lower()}/{code.lower()}_{rev}"
    mm, dd, yyyy = rev.split("-")
    doc("us-id", "form", f"{ID_FORMS}/{code}/{code}_{rev}.pdf",
        f"us-id/form/istc/ty{year}/{slug}-{code.lower()}-{yyyy}-{mm}-{dd}", f"{year} {title}", year,
        "instructions" if code == "EIN00046" else "form", ids=[old])
ID_LEG = "https://legislature.idaho.gov"
for path, url, title in [
    ("2022/h0001-legislation-page", f"{ID_LEG}/sessioninfo/2022extra1/legislation/H0001/",
     "House Bill 1 (2022 First Extraordinary Session): legislation page"),
    ("2025/h0040-legislation-page", f"{ID_LEG}/sessioninfo/2025/legislation/H0040/",
     "House Bill 40 (2025): legislation page"),
    ("2025/h0231-legislation-page", f"{ID_LEG}/sessioninfo/2025/legislation/h0231/",
     "House Bill 231 (2025): legislation page"),
    ("2026/h0559-legislation-page", f"{ID_LEG}/sessioninfo/2026/legislation/H0559/",
     "House Bill 559 (2026): legislation page"),
]:
    doc("us-id", "statute", url, f"us-id/statute/session-laws/{path}", title, None, "bill_page",
        sel="section.parent-section")
for path, url, title in [
    ("2024/h0521", f"{ID_LEG}/wp-content/uploads/sessioninfo/2024/legislation/H0521.pdf", "House Bill 521 (2024)"),
    ("2025/h0040", f"{ID_LEG}/wp-content/uploads/sessioninfo/2025/legislation/H0040.pdf", "House Bill 40 (2025)"),
    ("2025/h0231", f"{ID_LEG}/wp-content/uploads/sessioninfo/2025/legislation/H0231.pdf", "House Bill 231 (2025)"),
]:
    doc("us-id", "statute", url, f"us-id/statute/session-laws/{path}", title, None, "bill_text")
doc("us-id", "statute", "https://legislature.idaho.gov/statutesrules/idstat/Title57/T57CH11/SECT57-1110/",
    "us-id/statute/57-1110",
    "Idaho Code 57-1110. Additional tax on filing income tax credited to permanent building fund", None, "section",
    sel="div.pgbrk", ids=["https://law.justia.com/codes/idaho/2022/title-57/chapter-11/section-57-1110/"])
doc("us-id", "guidance", "https://tax.idaho.gov/governance/statutes/irc/", "us-id/guidance/istc/irc-conformity",
    "Conformity to Federal Internal Revenue Code (IRC) (Idaho State Tax Commission)", None, "guidance", sel="main")
doc("us-id", "guidance",
    "https://tax.idaho.gov/pressrelease/update-on-filing-2025-idaho-income-taxes-now-that-conformity-is-law/",
    "us-id/guidance/istc/press-releases/2026-02-17-filing-2025-income-taxes-conformity",
    "Update on filing 2025 Idaho income taxes now that conformity is law (press release, 2026-02-17)", None,
    "press_release", sel="main")
doc("us-id", "guidance",
    "https://tax.idaho.gov/taxes/income-tax/individual-income/popular-credits-and-deductions/ideal-college-savings-program/",
    "us-id/guidance/istc/ideal-college-savings-program",
    "IDeal Idaho College Savings Program (popular credits and deductions)", None, "guidance", sel="main")

# ---------------------------------------------------------------- Illinois
IL_TAX = "https://tax.illinois.gov/content/dam/soi/en/web/tax"
for year in (2021, 2022, 2023, 2024):
    doc("us-il", "form", f"{IL_TAX}/forms/incometax/documents/{year}/individual/il-1040-instr.pdf",
        f"us-il/form/idor/ty{year}/form-il-1040-instructions", f"{year} Form IL-1040 Instructions", year, "instructions")
doc("us-il", "form", f"{IL_TAX}/forms/incometax/documents/currentyear/individual/il-1040-schedule-icr.pdf",
    "us-il/form/idor/ty2025/schedule-icr", "2025 Schedule ICR Illinois Credits (R-12/25)", 2025, "schedule")
doc("us-il", "form", f"{IL_TAX}/forms/incometax/documents/currentyear/individual/il-1040-schedule-il-e-eic.pdf",
    "us-il/form/idor/ty2025/schedule-il-e-eitc",
    "2025 Schedule IL-E/EITC Illinois Exemption and Earned Income Tax Credit", 2025, "schedule")
IL_ARCH = "https://taxarchive.illinois.gov/content/dam/soi/en/web/taxarchive/forms/income-tax"
doc("us-il", "form", f"{IL_ARCH}/2019/individual/il-1040-schedule-m.pdf", "us-il/form/idor/ty2019/schedule-m",
    "2019 Schedule M Other Additions and Subtractions for Individuals", 2019, "schedule")
for year in (2021, 2022, 2023, 2024):
    doc("us-il", "form", f"{IL_ARCH}/{year}/individual/il-1040-schedule-icr.pdf", f"us-il/form/idor/ty{year}/schedule-icr",
        f"{year} Schedule ICR Illinois Credits (R-12/{str(year)[2:]})", year, "schedule")
    eic = "EITC" if year >= 2023 else "EIC"
    doc("us-il", "form", f"{IL_ARCH}/{year}/individual/il-1040-schedule-il-e-eic.pdf",
        f"us-il/form/idor/ty{year}/schedule-il-e-{eic.lower()}",
        f"{year} Schedule IL-E/{eic} Illinois Exemption and Earned Income {'Tax ' if year >= 2023 else ''}Credit",
        year, "schedule")
    doc("us-il", "form", f"{IL_ARCH}/{year}/individual/il-1040.pdf", f"us-il/form/idor/ty{year}/form-il-1040",
        f"{year} Form IL-1040 Individual Income Tax Return (R-12/{str(year)[2:]})", year, "return_form")
doc("us-il", "guidance", f"{IL_TAX}/research/publications/pubs/documents/pub-120.pdf", "us-il/guidance/idor/pub-120",
    "Publication 120 Retirement Income (Illinois Department of Revenue)", None, "publication")
doc("us-il", "guidance", "https://tax.illinois.gov/programs/eitc.html", "us-il/guidance/idor/eitc",
    "Illinois Earned Income Tax Credit (EITC)", None, "guidance", sel="main")
doc("us-il", "guidance", "https://tax.illinois.gov/questionsandanswers/answer.206.html",
    "us-il/guidance/idor/questions-and-answers/206",
    "Question and answer 206: contributions to IRC Section 529 college savings and tuition programs", None,
    "faq", sel="main")
doc("us-il", "guidance", "https://tax.illinois.gov/research/taxrates/income.html", "us-il/guidance/idor/income-tax-rates",
    "Income Tax Rates (Illinois Department of Revenue)", None, "guidance", sel="main")
doc("us-il", "guidance", "https://gov.illinois.gov/newsroom/press-release.25425.html",
    "us-il/guidance/governor/press-releases/2022-09-12-tax-rebate-payments",
    "Tax Rebate Payments Begin for Millions of Illinoisans (Office of the Governor press release, 2022-09-12)", None,
    "press_release", sel="div.press-release", ids=["https://www.illinois.gov/news/release.html?releaseid=25425"])

# ---------------------------------------------------------------- Indiana
doc("us-in", "statute", "https://iga.in.gov/pdf-documents/124/2026/senate/bills/SB0243/SB0243.05.ENRH.pdf",
    "us-in/statute/session-laws/2026/sb0243",
    "Senate Enrolled Act 243 (124th General Assembly, Second Regular Session, 2026), enrolled version", None,
    "session_law", ids=["https://iga.in.gov/legislative/2026/bills/senate/243"],
    note="iga.in.gov serves its JavaScript application shell to the corpus user agent and the PDF to the "
    "extractor's built-in browser user agent fallback (not an access-denied page).")
doc("us-in", "guidance", "https://www.in.gov/dor/files/ib117.pdf", "us-in/guidance/dor/income-tax-information-bulletin-117",
    "Income Tax Information Bulletin #117 (Indiana Department of Revenue)", None, "bulletin")
doc("us-in", "guidance", "https://www.in.gov/dor/files/ib98.pdf", "us-in/guidance/dor/income-tax-information-bulletin-98",
    "Income Tax Information Bulletin #98 (Indiana Department of Revenue)", None, "bulletin")
doc("us-in", "guidance",
    "https://www.in.gov/dor/tax-forms/individual/individual-prior-year/2023-individual-tax-forms/",
    "us-in/guidance/dor/2023-individual-tax-forms", "2023 Individual Tax Forms (Indiana DOR forms index page)", None,
    "forms_index", sel="main")

# ---------------------------------------------------------------- Kansas
doc("us-ks", "guidance", "https://ksrevenue.gov/taxnotices/notice24-08.pdf", "us-ks/guidance/revenue/notice-24-08",
    "Notice 24-08 Changes to Individual Income Tax", None, "notice", ids=["us-ks/guidance/revenue/notice-24-08"])
doc("us-ks", "guidance", "https://ksrevenue.gov/taxnotices/notice24-09.pdf", "us-ks/guidance/revenue/notice-24-09",
    "Notice 24-09 Child and Dependent Care Expenses Credit", None, "notice", ids=["us-ks/guidance/revenue/notice-24-09"])
doc("us-ks", "guidance", "https://www.ksrevenue.gov/faqs-taxii.html", "us-ks/guidance/revenue/faqs-individual-income-tax",
    "Frequently Asked Questions About Individual Income Tax (Kansas Department of Revenue)", None, "faq")
doc("us-ks", "guidance", "https://www.kansasstatetreasurer.ks.gov/learn_quest.html",
    "us-ks/guidance/treasurer/quest529-savings-program", "Quest529 Savings Program (Kansas State Treasurer)", None,
    "guidance")
for year in (2021, 2022, 2023, 2024):
    doc("us-ks", "form", f"https://www.ksrevenue.gov/pdf/ip{str(year)[2:]}.pdf",
        f"us-ks/form/kdor/ty{year}/individual-income-tax-instruction-booklet",
        f"{year} Kansas Individual Income Tax booklet (Form K-40 and instructions)", year, "instructions")
for year in (2023, 2024):
    doc("us-ks", "form", f"https://www.ksrevenue.gov/pdf/k-40{str(year)[2:]}.pdf", f"us-ks/form/kdor/ty{year}/form-k-40",
        f"{year} Kansas Individual Income Tax Form K-40", year, "return_form")
doc("us-ks", "statute", "https://kslegislature.gov/li/b2025_26/measures/documents/hb2231_01_0000.pdf?",
    "us-ks/statute/session-laws/2025/hb2231", "House Bill 2231 (2025), as amended by House Committee", None, "bill_text")
doc("us-ks", "statute", "https://kslegislature.gov/li_2022/b2021_22/measures/hb2106/",
    "us-ks/statute/session-laws/2021/hb2106", "House Bill 2106 (2021-2022 Legislative Sessions): measure page", None,
    "bill_page", sel="#main_content")

# ---------------------------------------------------------------- Kentucky
doc("us-ky", "statute", "https://apps.legislature.ky.gov/recorddocuments/bill/25RS/hb1/bill.pdf",
    "us-ky/statute/session-laws/2025/hb1", "House Bill 1 (2025 Regular Session), Acts Ch. 1: individual income tax rate",
    None, "bill_text")
doc("us-ky", "statute", "https://apps.legislature.ky.gov/record/25rs/hb1.html", "us-ky/statute/session-laws/2025/hb1-record",
    "House Bill 1 (2025 Regular Session): bill record page", None, "bill_page")
KY = "https://revenue.ky.gov/Forms"
for year in (2001, 2002, 2003, 2004, 2005):
    doc("us-ky", "form", f"{KY}/{year}_42A740P.pdf", f"us-ky/form/dor/ty{year}/schedule-p",
        f"{year} Schedule P (42A740-P) Kentucky Pension Income Exclusion", year, "schedule")
for name, year, slug, title, sub in [
    ("740%20(2025).pdf", 2025, "form-740", "2025 Form 740 Kentucky Individual Income Tax Return", "return_form"),
    ("740%20Packet%20Instructions%202023.pdf", 2023, "form-740-instructions", "2023 Kentucky Individual Income Tax Forms and Instructions (Form 740 packet)", "instructions"),
    ("740%20Packet%20Instructions%205-9-23.pdf", 2022, "form-740-instructions-rev-2023-05-09", "2022 Kentucky Individual Income Tax Forms and Instructions (Form 740 packet, revised 5-9-23)", "instructions"),
    ("740%20Packet%20Instructions.pdf", 2025, "form-740-instructions", "2025 Kentucky Individual Income Tax Forms and Instructions (Form 740 packet)", "instructions"),
    ("740%20instructions%20packet%20(2024).pdf", 2024, "form-740-instructions", "2024 Kentucky Individual Income Tax Forms and Instructions (Form 740 packet)", "instructions"),
    ("740-ES%20Instructions%203-21-23.pdf", 2023, "form-740-es-instructions", "2023 Instructions for Filing Estimated Tax Vouchers (42A740-S4)", "instructions"),
    ("8863-K%20(2025).pdf", 2025, "form-8863-k", "2025 Form 8863-K Kentucky Education Tuition Tax Credit", "schedule"),
    ("Form%208863-K%202022.pdf", 2022, "form-8863-k", "2022 Form 8863-K Kentucky Education Tuition Tax Credit", "schedule"),
    ("Form%208863-K%202023.pdf", 2023, "form-8863-k", "2023 Form 8863-K Kentucky Education Tuition Tax Credit", "schedule"),
    ("Form%20740%205-9-23.pdf", 2022, "form-740-rev-2023-05-09", "2022 Form 740 Kentucky Individual Income Tax Return (revised 5-9-23)", "return_form"),
    ("Form%20740%20Schedule%20A%202022.pdf", 2022, "schedule-a", "2022 Form 740 Schedule A Kentucky Itemized Deductions", "schedule"),
    ("Form%20740-2021.pdf", 2021, "form-740", "2021 Form 740 Kentucky Individual Income Tax Return", "return_form"),
    ("Schedule%20ITC%20(2025).pdf", 2025, "schedule-itc", "2025 Schedule ITC Kentucky Individual Tax Credit Schedule", "schedule"),
    ("Schedule%20ITC%202022.pdf", 2022, "schedule-itc", "2022 Schedule ITC Kentucky Individual Tax Credit Schedule", "schedule"),
    ("Schedule%20ITC%202023.pdf", 2023, "schedule-itc", "2023 Schedule ITC Kentucky Individual Tax Credit Schedule", "schedule"),
    ("Schedule%20ITC-2021.pdf", 2021, "schedule-itc", "2021 Schedule ITC Kentucky Individual Tax Credit Schedule", "schedule"),
    ("Schedule%20M%202022.pdf", 2022, "schedule-m", "2022 Schedule M Kentucky Federal Adjusted Gross Income Modifications", "schedule"),
    ("Schedule%20M%202023.pdf", 2023, "schedule-m", "2023 Schedule M Kentucky Federal Adjusted Gross Income Modifications", "schedule"),
    ("Schedule%20M-2021.pdf", 2021, "schedule-m", "2021 Schedule M Kentucky Federal Adjusted Gross Income Modifications", "schedule"),
    ("Schedule%20P%20(2025).pdf", 2025, "schedule-p", "2025 Schedule P Kentucky Pension Income Exclusion", "schedule"),
    ("Schedule%20P%202018.pdf", 2018, "schedule-p", "2018 Schedule P Kentucky Pension Income Exclusion (42A740-P, 10-18)", "schedule"),
    ("Schedule%20P%202022.pdf", 2022, "schedule-p", "2022 Schedule P Kentucky Pension Income Exclusion", "schedule"),
    ("Schedule%20P%202023.pdf", 2023, "schedule-p", "2023 Schedule P Kentucky Pension Income Exclusion", "schedule"),
]:
    extra = {}
    if name == "Form%20740-2021.pdf":
        extra["ids"] = ["https://www.taxformfinder.org/forms/2021/2021-kentucky-form-740.pdf"]
    doc("us-ky", "form", f"{KY}/{name}", f"us-ky/form/dor/ty{year}/{slug}", title, year, sub, **extra)
doc("us-ky", "guidance", "https://revenue.ky.gov/News/Pages/DOR-Announces-Updates-to-Individual-Income-Tax-for-2023-Tax-Year.aspx",
    "us-ky/guidance/dor/news/2022-09-21-individual-income-tax-updates-2023",
    "DOR Announces Updates to Individual Income Tax for 2023 Tax Year (news release)", None, "press_release", sel="main")
doc("us-ky", "guidance", "https://revenue.ky.gov/News/Pages/Kentucky-DOR-Announces-2025-Standard-Deduction.aspx",
    "us-ky/guidance/dor/news/2025-standard-deduction", "Kentucky DOR Announces 2025 Standard Deduction (news release)",
    None, "press_release", sel="main")

# ---------------------------------------------------------------- Louisiana
LA = "https://dam.ldr.la.gov/taxforms"
doc("us-la", "guidance", "https://dam.ldr.la.gov/lawspolicies/RIB%2026-019.pdf", "us-la/guidance/ldr/rib-26-019",
    "Revenue Information Bulletin 26-019 (Louisiana Department of Revenue)", None, "bulletin")
for name, year, slug, title, sub in [
    ("6935(11_02)F.pdf", None, "r-6935-tax-computation-worksheet-rev-2002-11", "R-6935 (11/02) Tax Computation Worksheet", "worksheet"),
    ("IT-540-WEB-2021-F.pdf", 2021, "form-it-540", "2021 Form IT-540 Louisiana Resident Income Tax Return", "return_form"),
    ("IT-540-WEB-2022-F.pdf", 2022, "form-it-540", "2022 Form IT-540 Louisiana Resident Income Tax Return", "return_form"),
    ("IT540(2022)%20Tax%20Table.pdf", 2022, "tax-table", "2022 Louisiana Tax Table (IT-540)", "tax_table"),
    ("IT540(2023)%20TT.pdf", 2023, "tax-table", "2023 Louisiana Tax Table (IT-540)", "tax_table"),
    ("IT540WEB(2022)%20F%20D2.pdf", 2022, "form-it-540-d2", "2022 Form IT-540 Louisiana Resident Income Tax Return (D2 revision)", "return_form"),
    ("IT540WEB(2023)%20F.pdf", 2023, "form-it-540", "2023 Form IT-540 Louisiana Resident Income Tax Return", "return_form"),
    ("IT540i%20WEB%20(2024)D18%20INSTRUCTIONS.pdf", 2024, "form-it-540-instructions", "2024 Form IT-540 Instructions (D18)", "instructions"),
    ("IT540i%20WEB(2023)%20INSTRUCTIONS.pdf", 2023, "form-it-540-instructions", "2023 Form IT-540 Instructions", "instructions"),
    ("IT540i%20WEB(2025)D11.pdf", 2025, "form-it-540-instructions-d11", "2025 Form IT-540 Instructions (D11)", "instructions"),
    ("IT540i(2021)%20Instructions.pdf", 2021, "form-it-540-instructions", "2021 Form IT-540 Instructions", "instructions"),
    ("IT540iWEB(2022)D1.pdf", 2022, "form-it-540-instructions", "2022 Form IT-540 Instructions (D1)", "instructions"),
]:
    path = f"us-la/form/ldr/{slug}" if year is None else f"us-la/form/ldr/ty{year}/{slug}"
    doc("us-la", "form", f"{LA}/{name}", path, title, year, sub)
LA_NAV_NOTE = ("revenue.louisiana.gov leaves a <nav> element open around the whole page; the manifest keeps nav "
               "(html_keep_default_drop_selectors) and reads only the page's <main> element.")
doc("us-la", "guidance", "https://revenue.louisiana.gov/individuals/general-resources/school-readiness-credit/",
    "us-la/guidance/ldr/school-readiness-credit", "School Readiness Credit (Louisiana Department of Revenue)", None,
    "guidance", sel="main", keep=["nav"], note=LA_NAV_NOTE)
doc("us-la", "guidance",
    "https://revenue.louisiana.gov/tax-education-and-faqs/faqs/income-tax-reform/what-are-the-individual-income-tax-rates-and-brackets/",
    "us-la/guidance/ldr/faqs/income-tax-reform/individual-income-tax-rates-and-brackets",
    "What are the individual income tax rates and brackets? (Income tax reform FAQ, Louisiana Department of Revenue)",
    None, "faq", sel="main", keep=["nav"], note=LA_NAV_NOTE)
doc("us-la", "guidance", "https://www.startsaving.la.gov/startfaqs.aspx", "us-la/guidance/losfa/start-faqs",
    "START Frequently Asked Questions (Louisiana Student Tuition Assistance and Revenue Trust, LOSFA)", None, "faq",
    sel="#content")

# ---------------------------------------------------------------- Massachusetts
MASS = "https://www.mass.gov"
doc("us-ma", "guidance", f"{MASS}/technical-information-release/tir-02-21-capital-gains-and-losses-massachusetts-tax-law-changes",
    "us-ma/guidance/department-of-revenue/tir-02-21",
    "TIR 02-21: Capital Gains and Losses: Massachusetts Tax Law Changes", None, "technical_information_release",
    sel="main", ids=["https://www.mass.gov/technical-information-release/tir-02-21-capital-gains-and-losses-massachusetts-tax-law-changes"])
doc("us-ma", "guidance", f"{MASS}/technical-information-release/tir-22-5-tax-provisions-in-recent-massachusetts-legislation",
    "us-ma/guidance/department-of-revenue/tir-22-5", "TIR 22-5: Tax Provisions in Recent Massachusetts Legislation", None,
    "technical_information_release", sel="main")
for slug, path, title in [
    ("info-details/covid-19-essential-employee-premium-pay-program", "executive-office-for-administration-and-finance/covid-19-essential-employee-premium-pay-program",
     "COVID-19 Essential Employee Premium Pay Program (Executive Office for Administration and Finance)"),
    ("info-details/filing-status-on-massachusetts-personal-income-tax", "department-of-revenue/filing-status-on-personal-income-tax",
     "Filing Status on Personal Income Tax (Massachusetts Department of Revenue)"),
    ("info-details/massachusetts-child-and-family-tax-credit", "department-of-revenue/child-and-family-tax-credit",
     "Massachusetts Child and Family Tax Credit (Department of Revenue)"),
    ("info-details/massachusetts-senior-circuit-breaker-tax-credit", "department-of-revenue/senior-circuit-breaker-tax-credit",
     "Senior Circuit Breaker Tax Credit (Department of Revenue)"),
    ("info-details/personal-income-tax-exemptions", "department-of-revenue/personal-income-tax-exemptions",
     "Personal Income Tax Exemptions (Department of Revenue)"),
    ("service-details/massachusetts-tax-rates", "department-of-revenue/tax-rates", "Tax Rates (Department of Revenue)"),
    ("audit/audit-of-the-determination-of-whether-net-state-tax-revenues-exceeded-allowable-state-tax-revenues-0",
     "state-auditor/determination-net-state-tax-revenues-exceeded-allowable-fy2022",
     "Determination of Whether Net State Tax Revenues Exceeded Allowable State Tax Revenues (Office of the State Auditor, chapter 62F)"),
]:
    extra = {}
    if slug == "info-details/personal-income-tax-exemptions":
        extra["ids"] = [f"{MASS}/service-details/view-massachusetts-personal-income-tax-exemptions"]
    doc("us-ma", "guidance", f"{MASS}/{slug}", f"us-ma/guidance/{path}", title, None, "guidance", sel="main", **extra)
doc("us-ma", "form", f"{MASS}/doc/2022-form-1-massachusetts-resident-income-tax-return/download",
    "us-ma/form/dor/ty2022/form-1", "2022 Form 1 Massachusetts Resident Income Tax Return", 2022, "return_form")
for year in (2022, 2023, 2025):
    doc("us-ma", "form", f"{MASS}/doc/{year}-schedule-cb-circuit-breaker-credit/download",
        f"us-ma/form/dor/ty{year}/schedule-cb", f"{year} Schedule CB Circuit Breaker Credit", year, "schedule")
for year in (2023, 2024):
    doc("us-ma", "form", f"{MASS}/doc/{year}-form-1-instructions/download", f"us-ma/form/dor/ty{year}/form-1-instructions",
        f"{year} Massachusetts Form 1 Resident Income Tax Return Instructions", year, "instructions")
MALEG = "https://malegislature.gov"
doc("us-ma", "statute", f"{MALEG}/Laws/SessionLaws/Acts/2023/Chapter50", "us-ma/statute/session-laws/2023/chapter-50",
    "Acts of 2023, Chapter 50: An Act to improve the Commonwealth's competitiveness, affordability, and equity", None,
    "session_law", sel="main")
doc("us-ma", "statute", f"{MALEG}/Bills/193/H4104/BillHistory", "us-ma/statute/session-laws/2023/h4104-bill-history",
    "Bill H.4104 (193rd General Court, 2023-2024): bill history", None, "bill_page", sel="main")
doc("us-ma", "statute", f"{MALEG}/Bills/191/H86", "us-ma/statute/session-laws/2019/h86",
    "Proposal for Constitutional Amendment H.86 (191st General Court, 2019-2020)", None, "bill_page", sel="main")

# ---------------------------------------------------------------- Maryland
MDC = "https://www.marylandcomptroller.gov/content/dam/mdcomp/tax"
doc("us-md", "form", f"{MDC}/forms/2023/502CR.pdf", "us-md/form/comptroller/ty2023/502cr",
    "2023 Maryland Form 502CR Income Tax Credits for Individuals", 2023, "schedule",
    ids=["us-md/form/tax_forms/marylandtaxes.gov/content/dam/mdcomp/tax/forms/2023/502cr",
         "https://marylandtaxes.gov/forms/23_forms/502CR.pdf"])
doc("us-md", "form", f"{MDC}/forms/2024/502CR.pdf", "us-md/form/comptroller/ty2024/502cr",
    "2024 Maryland Form 502CR Income Tax Credits for Individuals", 2024, "schedule",
    ids=["us-md/form/tax_forms/marylandtaxes.gov/content/dam/mdcomp/tax/forms/2024/502cr"])
doc("us-md", "form", "https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/forms/2025/502cr.pdf",
    "us-md/form/comptroller/ty2025/502cr", "2025 Maryland Form 502CR Income Tax Credits for Individuals", 2025, "schedule")
doc("us-md", "form", f"{MDC}/instructions/2023/Resident-Booklet.pdf", "us-md/form/comptroller/ty2023/resident-booklet",
    "2023 Maryland State and Local Tax Forms and Instructions (Resident Booklet)", 2023, "instructions",
    ids=["us-md/form/tax_forms/marylandtaxes.gov/content/dam/mdcomp/tax/instructions/2023/resident-booklet",
         "https://www.marylandtaxes.gov/forms/23_forms/Resident-Booklet.pdf"])
doc("us-md", "form", f"{MDC}/instructions/2024/Resident-Booklet.pdf", "us-md/form/comptroller/ty2024/resident-booklet",
    "2024 Maryland State and Local Tax Forms and Instructions (Resident Booklet)", 2024, "instructions",
    ids=["us-md/form/tax_forms/marylandtaxes.gov/content/dam/mdcomp/tax/instructions/2024/resident-booklet"])
doc("us-md", "form", f"{MDC}/instructions/2024/Nonresident-Booklet.pdf", "us-md/form/comptroller/ty2024/nonresident-booklet",
    "2024 Maryland Nonresident Tax Forms and Instructions (Nonresident Booklet)", 2024, "instructions",
    ids=["us-md/form/tax_forms/marylandtaxes.gov/content/dam/mdcomp/tax/instructions/2024/nonresident-booklet"])
doc("us-md", "form", "https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/instructions/2025/resident-booklet.pdf",
    "us-md/form/comptroller/ty2025/resident-booklet",
    "2025 Maryland State and Local Tax Forms and Instructions (Resident Booklet)", 2025, "instructions")
for year in (2020, 2021, 2022):
    doc("us-md", "form",
        f"https://interactive.marylandtaxes.gov/Individuals/iFile_ChooseForm/PriorYearForms/Resident_Booklet_{year}.pdf",
        f"us-md/form/comptroller/ty{year}/resident-booklet",
        f"{year} Maryland State and Local Tax Forms and Instructions (Resident Booklet)", year, "instructions")
MGA = "https://mgaleg.maryland.gov"
doc("us-md", "statute", f"{MGA}/2023RS/chapters_noln/Ch_613_hb0554T.pdf", "us-md/statute/session-laws/2023/chapter-613",
    "Chapter 613 of 2023 (House Bill 554): Income Tax - Subtraction Modification for Military Retirement Income", None,
    "session_law")
doc("us-md", "statute", f"{MGA}/2025RS/Chapters_noln/CH_604_hb0352e.pdf", "us-md/statute/session-laws/2025/chapter-604",
    "Chapter 604 of 2025 (House Bill 352): Budget Reconciliation and Financing Act of 2025", None, "session_law")
doc("us-md", "statute", f"{MGA}/mgawebsite/Legislation/Details/hb0186?ys=2022RS", "us-md/statute/session-laws/2022/hb0186",
    "House Bill 186 (2022 Regular Session): legislation details page", None, "bill_page", sel="#mainBody")
doc("us-md", "guidance", f"{MGA}/2023RS/fnotes/bil_0007/hb0547.pdf", "us-md/guidance/dls/fiscal-notes/2023/hb0547",
    "Fiscal and Policy Note, House Bill 547 (2023 Session), Department of Legislative Services", None, "fiscal_note")

# ---------------------------------------------------------------- Maine
MLEG = "https://legislature.maine.gov"
doc("us-me", "statute", f"{MLEG}/backend/App/services/getDocument.aspx?documentId=120256",
    "us-me/statute/session-laws/132/ld210-committee-amendment-120256",
    "Committee Amendment to L.D. 210 (132nd Legislature), Appropriations and Financial Affairs", None, "amendment")
doc("us-me", "statute", f"{MLEG}/legis/bills/getPDF.asp?paper=HP1491&item=37&snum=132",
    "us-me/statute/session-laws/132/ld2212",
    "H.P. 1491 - L.D. 2212 (132nd Legislature, 2026): An Act Making Supplemental Appropriations and Allocations", None,
    "session_law")
doc("us-me", "statute", f"{MLEG}/legis/bills/getPDF.asp?paper=SP0031&item=5&snum=130",
    "us-me/statute/session-laws/130/ld23",
    "S.P. 31 - L.D. 23 (130th Legislature, 2022): An Act To Reinstate and Increase the Income Tax Deduction for "
    "Contributions to Education Savings Plans", None, "session_law")
doc("us-me", "guidance", "https://www.maine.gov/governor/mills/relief-checks", "us-me/guidance/governor/relief-checks",
    "Relief Checks (Office of Governor Janet T. Mills)", None, "guidance", sel="article")
ME = "https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files"
ME_KIND = [
    (r"sched ?2|_2_|_2 _|sch2", "schedule-2", "Schedule 2 Itemized Deductions", "schedule"),
    (r"sched ?ptfc|sch ptfc|sch_ptfc", "schedule-ptfc", "Schedule PTFC Property Tax Fairness Credit", "schedule"),
    (r"pstfc", "schedule-pstfc", "Schedule PS/TFC Property Tax Fairness Credit and Sales Tax Fairness Credit", "schedule"),
    (r"sched_a|_a_d|_a_dwnld|sch a", "schedule-a", "Schedule A Adjustments to Tax", "schedule"),
    (r"sched_1a", "schedule-1a", "Schedule 1A Income Additions", "schedule"),
    (r"sched_1s|sch 1s", "schedule-1s", "Schedule 1S Income Subtractions", "schedule"),
    (r"tax_tables", "tax-tables", "Maine Income Tax Tables", "tax_table"),
    (r"earned_income_cred", "earned-income-tax-credit-worksheet", "Earned Income Tax Credit Worksheet", "worksheet"),
    (r"item_stand", "itemized-standard-deduction-phaseout-worksheet", "Estimated Tax Worksheet Line 6a, Phaseout of Itemized / Standard Deductions", "worksheet"),
    (r"pers_exempt", "personal-exemption-phaseout-worksheet", "Estimated Tax Worksheet Line 6b, Phaseout of Personal Exemption Deduction Amount", "worksheet"),
    (r"book|gen_instr|instr", "form-1040me-instructions", "Form 1040ME Individual Income Tax Instructions", "instructions"),
    (r"1040me_dwnld", "form-1040me", "Form 1040ME Individual Income Tax Return", "return_form"),
]
ME_FILES = [
    "13_1040_sched2_downloadable.pdf",
    "14_1040%20sched%202_download.pdf",
    "14_1040_sched%20ptfc_download.pdf",
    "15_1040%20sched%202_download.pdf",
    "16_1040%20sched%202_download.pdf",
    "16_1040me_book_download.pdf",
    "17_1040me_book_dwnld_sept18.pdf",
    "17_1040me_sch2_d_sept18.pdf",
    "18_1040_2_d.pdf",
    "18_1040me_a_d.pdf",
    "18_1040me_book_noncon.pdf",
    "19_1040me_2_dwnldff.pdf",
    "19_1040me_a_dwnldff.pdf",
    "19_1040me_instr_noncon.pdf",
    "20_1040me_2_dwnldff.pdf",
    "20_1040me_gen_instr.pdf",
    "20_1040me_sched_a_dwnloadff.pdf",
    "21_1040me_2_dwnldff.pdf",
    "21_1040me_book_gen_instr_revMay2022.pdf",
    "21_1040me_sched_a_dwnldff.pdf",
    "21_1040me_sched_pstfc_dwnldff.pdf",
    "21_1040me_tax_tables.pdf",
    "22_1040me_book_gen_instruc_revisedFeb23.pdf",
    "22_1040me_dwnld_ff.pdf",
    "22_1040me_sched_1a_ff.pdf",
    "22_1040me_sched_1s_ff.pdf",
    "22_1040me_sched_2_ff.pdf",
    "22_1040me_sched_a_ff.pdf",
    "22_1040me_sched_pstfc_ff.pdf",
    "22_1040me_tax_tables.pdf",
    "22_earned_income_cred_ff.pdf",
    "22_item_stand_%20ded_phaseout_wksht.pdf",
    "23_1040me_book_gen_instr.pdf",
    "23_1040me_sched_1s.pdf",
    "23_1040me_sched_2_ff_0.pdf",
    "23_1040me_sched_a_ff.pdf",
    "23_1040me_sched_pstfc_ff.pdf",
    "23_1040me_tax_tables.pdf",
    "23_earned_income_cred_ff.pdf",
    "24_1040me_book_gen_instr.pdf",
    "24_1040me_sched_2%20_ff.pdf",
    "24_Form%201040ME_Sch%201S_ff.pdf",
    "24_Form%201040ME_Sch%20PTFC_ff.pdf",
    "24_Form%201040ME_Sch%20PTFC_ff_0.pdf",
    "24_Form1040me_Sch%20A_ff.pdf",
    "24_earned_income_cred_ff_0.pdf",
    "25_1040me_sch_ptfc_fillable.pdf",
    "26_1040es_pers_exempt_phaseout_wksht.pdf",
    "26_item_stand_%20ded_phaseout_wksht_0.pdf",
]
ME_SEEN: dict[str, int] = {}
ME_EDITION = {
    "17_1040me_book_dwnld_sept18.pdf": " (September 2018 revision)",
    "17_1040me_sch2_d_sept18.pdf": " (September 2018 revision)",
    "18_1040me_book_noncon.pdf": " (with the conformity/nonconformity update page)",
    "19_1040me_instr_noncon.pdf": " (with the conformity/nonconformity update page)",
    "20_1040me_gen_instr.pdf": " (with the conformity update page)",
    "21_1040me_book_gen_instr_revMay2022.pdf": " (revised May 2022)",
    "22_1040me_book_gen_instruc_revisedFeb23.pdf": " (revised February 2023)",
    "24_Form%201040ME_Sch%20PTFC_ff_0.pdf": " (second posted revision)",
}


def _maine_kind(name: str) -> tuple[str, str, str]:
    plain = name.replace("%20", " ").lower()[3:]
    for pattern, slug, title, sub in ME_KIND:
        if re.search(pattern, plain):
            return slug, title, sub
    raise SystemExit(f"unclassified Maine file {name}")


for name in ME_FILES:
    year = 2000 + int(name[:2])
    slug, title, sub = _maine_kind(name)
    key = f"ty{year}/{slug}"
    ME_SEEN[key] = ME_SEEN.get(key, 0) + 1
    suffix = "" if ME_SEEN[key] == 1 else f"-{ME_SEEN[key]}"
    edition = ME_EDITION.get(name, "")
    doc("us-me", "form", f"{ME}/{name}", f"us-me/form/mrs/{key}{suffix}", f"{year} {title}{edition}", year, sub)
doc("us-me", "form", f"{ME}/ind_tax_rate_sched_2024.pdf", "us-me/form/mrs/ty2024/tax-rate-schedules",
    "State of Maine Individual Income Tax 2024 Rates (Maine Revenue Services, 2023-09-15)", 2024, "rate_schedule")
doc("us-me", "guidance", f"{ME}/legischange26.pdf", "us-me/guidance/mrs/2026-session-legislation-enacted",
    "2026 Session Legislation Enacted (Maine Revenue Services summary, 2nd Regular Session)", None, "legislative_summary")

# ---------------------------------------------------------------- Michigan
MI = "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT"
MI_OLD = "us-mi/form/individual_income_tax_forms/michigan.gov/taxes/source/media/project/websites/taxes/forms/iit"
for ty, name, slug, title, sub in [
    (2020, "Book_MI-1040_instructions_only.pdf", "mi-1040-instructions", "2020 Michigan Individual Income Tax Instructions (MI-1040 book, instructions only)", "instructions"),
    (2022, "BOOK_MI-1040.pdf", "mi-1040-book", "2022 Michigan MI-1040 Individual Income Tax Forms and Instructions", "instructions"),
    (2022, "MI-1040.pdf", "form-mi-1040", "2022 MI-1040 Michigan Individual Income Tax Return", "return_form"),
    (2022, "MI-1040CR.pdf", "form-mi-1040cr", "2022 MI-1040CR Michigan Homestead Property Tax Credit Claim", "schedule"),
    (2023, "BOOK_MI-1040.pdf", "mi-1040-book", "2023 Michigan MI-1040 Individual Income Tax Forms and Instructions", "instructions"),
    (2023, "MI-1040.pdf", "form-mi-1040", "2023 MI-1040 Michigan Individual Income Tax Return", "return_form"),
    (2023, "MI-1040CR.pdf", "form-mi-1040cr", "2023 MI-1040CR Michigan Homestead Property Tax Credit Claim", "schedule"),
    (2024, "MI-1040-Instructions.pdf", "mi-1040-instructions", "2024 Michigan MI-1040 Individual Income Tax Forms and Instructions", "instructions"),
    (2024, "MI-1040CR.pdf", "form-mi-1040cr", "2024 MI-1040CR Michigan Homestead Property Tax Credit Claim", "schedule"),
    (2025, "MI-1040CR.pdf", "form-mi-1040cr", "2025 MI-1040CR Michigan Homestead Property Tax Credit Claim", "schedule"),
]:
    old = f"{MI_OLD}/ty{ty}/{name.rsplit('.', 1)[0].lower()}"
    doc("us-mi", "form", f"{MI}/TY{ty}/{name}", f"us-mi/form/treasury/ty{ty}/{slug}", title, ty, sub,
        request=MICHIGAN_REQUEST, note=MICHIGAN_NOTE, ids=[old])
for ty, name, slug, title, sub in [
    (2021, "Book-1040-Instructions-Only.pdf", "mi-1040-instructions", "2021 Michigan MI-1040 Individual Income Tax Instructions (instructions only)", "instructions"),
    (2022, "4884.pdf", "form-4884", "2022 Form 4884 Michigan Pension Schedule", "schedule"),
    (2022, "Form-4884-Section-C-worksheet.pdf", "form-4884-section-c-worksheet", "2022 Form 4884 Section C Worksheet (railroad retirement and qualifying pension benefits; no printed year, linked from the 2022 forms index)", "worksheet"),
    (2022, "Schedule-1.pdf", "schedule-1", "2022 Michigan Schedule 1 Additions and Subtractions", "schedule"),
    (2024, "4884-Instructions.pdf", "form-4884-instructions", "2024 Form 4884 Pension Schedule Instructions", "instructions"),
]:
    doc("us-mi", "form", f"{MI}/TY{ty}/{name}", f"us-mi/form/treasury/ty{ty}/{slug}", title, ty, sub,
        request=MICHIGAN_REQUEST, note=MICHIGAN_NOTE)
doc("us-mi", "form", "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/SUW/TY2025/446_Withholding-Guide_2025.pdf",
    "us-mi/form/treasury/ty2025/446-withholding-guide", "2025 Michigan Income Tax Withholding Guide (Form 446, Rev. 01-25)", 2025,
    "withholding_guide", request=MICHIGAN_REQUEST, note=MICHIGAN_NOTE)
doc("us-mi", "form", "https://www.michigan.gov/-/media/Project/Websites/ors/ORS-Forms/R0012X_Income_Tax_Withholding_Authorization.pdf",
    "us-mi/form/ors/r0012x-income-tax-withholding-authorization",
    "R0012X Income Tax Withholding Authorization (Office of Retirement Services)", None, "withholding_form",
    request=MICHIGAN_REQUEST, note=MICHIGAN_NOTE)
MIG = "https://www.michigan.gov"
for url, path, title, sub in [
    (f"{MIG}/taxes/iit/tax-guidance/tax-situations/retirement-and-pension-benefits",
     "us-mi/guidance/treasury/retirement-and-pension-benefits", "Retirement and Pension Benefits (Michigan Treasury tax guidance)", "guidance"),
    (f"{MIG}/taxes/questions/tax-faqs/income-tax-rate-change/income-tax-rate-change-overview",
     "us-mi/guidance/treasury/income-tax-rate-change-overview", "Income Tax Rate Change: Overview (Michigan Treasury FAQ)", "faq"),
    (f"{MIG}/taxes/rep-legal/rab/2026-revenue-administrative-bulletins/revenue-administrative-bulletin-2026-1",
     "us-mi/guidance/treasury/rab/2026-1", "Revenue Administrative Bulletin 2026-1", "revenue_administrative_bulletin"),
    (f"{MIG}/taxes/business-taxes/withholding/withholding-tax-faqs/what-is-michigans-2023-personal-exemption-amount",
     "us-mi/guidance/treasury/withholding-faqs/personal-exemption-amount", "What is Michigan's personal exemption amount? (withholding tax FAQ)", "faq"),
    (f"{MIG}/treasury/reference/taxpayer-notices/2025/05/01/2025-tax-year-income-tax-rate-for-individuals-and-fiduciaries",
     "us-mi/guidance/treasury/taxpayer-notices/2025-05-01-2025-income-tax-rate", "2025 Tax Year Income Tax Rate for Individuals and Fiduciaries (taxpayer notice, 2025-05-01)", "notice"),
    (f"{MIG}/treasury/reference/taxpayer-notices/2025/11/17/social-security-taxation-changes-in-public-act-24-of-2025",
     "us-mi/guidance/treasury/taxpayer-notices/2025-11-17-social-security-taxation-public-act-24-of-2025", "Social Security Taxation Changes in Public Act 24 of 2025 (taxpayer notice, 2025-11-17)", "notice"),
    (f"{MIG}/treasury/reference/taxpayer-notices/2026/01/06/new-deductions-for-qualified-overtime-compensation-and-qualified-tips",
     "us-mi/guidance/treasury/taxpayer-notices/2026-01-06-qualified-overtime-and-tips-deductions", "New Deductions for Qualified Overtime Compensation and Qualified Tips (taxpayer notice, 2026-01-06)", "notice"),
]:
    extra = {}
    if path.endswith("retirement-and-pension-benefits"):
        extra["ids"] = [f"{MIG}/taxes/iit/retirement-and-pension-benefits"]
    doc("us-mi", "guidance", url, path, title, None, sub, sel="section#pagebody", request=MICHIGAN_REQUEST,
        note=MICHIGAN_NOTE, **extra)
doc("us-mi", "guidance",
    f"{MIG}/treasury/-/media/Project/Websites/treasury/Uncategorized/2023/Economic-Reports-and-Notices-2023/Home-Heating-Expenses-Reported-by-Home-Heating-Credit-Filers/rpt-text_2021data.pdf",
    "us-mi/guidance/treasury/reports/home-heating-expenses-2021-data",
    "2021 Home Heating Expenses Reported by Home Heating Credit Filers (Office of Revenue and Tax Analysis)", None, "report",
    request=MICHIGAN_REQUEST, note=MICHIGAN_NOTE)
doc("us-mi", "guidance", "https://www.legislature.mi.gov/Publications/TaxpayerGuide.pdf",
    "us-mi/guidance/legislature/taxpayers-guide-2025", "Michigan Taxpayer's Guide for the 2025 tax year (Michigan Legislature)",
    None, "publication")
doc("us-mi", "statute", "https://legislature.mi.gov/Bills/Bill?ObjectName=2025-HB-4961", "us-mi/statute/session-laws/2025/hb4961",
    "House Bill 4961 of 2025 (Public Act 24 of 2025): bill page", None, "bill_page", sel="main")


# ------------------------------------------------------------ non-extracted decisions
HELD = {
    "id-ch30": "us-id/statute/2026-09-14-income-tax-chapter-us-id-title-63-chapter-30",
    "ks-a32": "us-ks/statute/2026-07-16-pit-west-us-ks-chapter-79-article-32",
    "la-t47": "us-la/statute/2026-07-22-la-title-47-official-current-us-la-title-47",
    "me-t36": "us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36",
    "ma-c62": "us-ma/statute/2026-09-15-income-tax-chapter-us-ma-part-i-title-ix-chapter-62",
    "ia-422": "us-ia/statute/2026-07-16-pit-east-us-ia-title-x-chapter-422-r2026-07-24-immutable",
    "ia-reg": "us-ia/regulation/2026-09-14-income-tax-regulations",
    "il-core": "us-il/statute/2026-07-24-il-individual-income-tax-resident-core",
    "il-reg": "us-il/regulation/2026-09-14-income-tax-regulations-title-086-part-00100",
    "in-t6": "us-in/statute/2026-07-16-pit-east-us-in-title-6",
    "ky-141": "us-ky/statute/2026-09-14-income-tax-chapter",
    "md-gtg": "us-md/statute/2026-09-14-income-tax-chapter-us-md-article-gtg",
    "mi-206": "us-mi/statute/2026-09-14-income-tax-chapter-us-mi-chapter-206",
    "mi-w5": "us-mi/form/2026-09-15-income-tax-forms-ty2025",
}
OUTREACH_ILGA = (
    "ilga.gov answers HTTP 403 'Access Denied ... Automated Request Blocked' to the corpus client "
    "(2026-10-06, one retry; wave-5 recorded the same block); the extractor's browser user agent "
    "receives the page, which a reviewer may allow; not worked around"
)


OTHER: dict[str, tuple[str, str, str, str]] = {}
OFFICIAL_URL: dict[str, str] = {}


def other(key: str, status: str, scope: str, path: str, note: str, official: str = "") -> None:
    OTHER[key] = (status, scope, path, note)
    if official:
        OFFICIAL_URL[key] = official


def held(key: str, scope: str, path: str, note: str, official: str = "") -> None:
    other(key, "ALREADY-HELD", HELD[scope], path, note, official)


# Iowa
held("https://www.legis.iowa.gov/docs/code/422.7.pdf", "ia-422", "us-ia/statute/422.7",
     "Iowa Code 422.7 is held (current text, chapter 422 scope)")
held("https://www.legis.iowa.gov/docs/iac/rule/701.302.47.pdf", "ia-reg", "us-ia/regulation/iac/701/302/47",
     "701-302.47 held in the IAC 701 chapter 302 scope")
held("https://www.legis.iowa.gov/docs/iac/rule/701.304.15.pdf", "ia-reg", "us-ia/regulation/iac/701/304/15",
     "701-304.15 held in the IAC 701 chapter 304 scope")
held("https://www.law.cornell.edu/regulations/iowa/Iowa-Code-r-701-304.15", "ia-reg", "us-ia/regulation/iac/701/304/15",
     "mirror; the official LSA text of 701-304.15 is held", "https://www.legis.iowa.gov/docs/iac/chapter/701.304.pdf")
held("https://www.legis.iowa.gov/docs/iac/agency/01-24-2024.701.pdf", "ia-reg", "us-ia/regulation/iac/701",
     "the 2024-01-24 IAC agency 701 compilation (1,545 pages, all Revenue rules) is superseded; the current income-tax "
     "chapters 300-308 of agency 701 are held from the LSA chapter PDFs; not re-taken")
held("https://www.isave529.com/save/tax-benefits", "ia-422", "us-ia/statute/422.7",
     "isave529.com is the plan manager's marketing site, not the official publisher; the deduction it describes is "
     "Iowa Code 422.7 (held); the 2025 deduction amount is in the Treasurer's notice (PRESENT)")
other("https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax/2023-changes-iowa-individual-income-tax",
      "ABSENT", "", "", "the page now redirects to the general Tax Guidance index (https://revenue.iowa.gov/taxes/tax-guidance); "
      "the 2023 changes page is no longer published (its alias answers 'no longer available')",
      "https://revenue.iowa.gov/taxes/tax-guidance")
other("https://revenue.iowa.gov/2023-changes-iowa-individual-income-tax", "ABSENT", "", "",
      "HTTP 403 page 'We can't find that page ... no longer available' (plain and browser user agents, 2026-10-06)")
other("https://revenue.iowa.gov/media/3305/download?inline", "OUT-OF-SCOPE", "", "",
      "2021 Iowa Individual Income Tax Annual Statistical Report (IDR Research and Policy Division): statistics, not rules")
other("https://revenue.iowa.gov/media/3379/download?inline", "OUT-OF-SCOPE", "", "",
      "2022 Iowa Individual Income Tax Annual Statistical Report (IDR Research and Policy Division): statistics, not rules")
# Idaho
for sec in ["63-3004", "63-3022", "63-3029L", "63-3022A", "63-3022D", "63-3022E", "63-3022H", "63-3024", "63-3024B", "63-3025D"]:
    for url in [
        f"https://legislature.idaho.gov/statutesrules/idstat/Title63/T63CH30/SECT{sec}/",
        f"https://legislature.idaho.gov/statutesrules/idstat/title63/t63ch30/sect{sec.lower()}/",
    ]:
        held(url, "id-ch30", f"us-id/statute/{sec}", f"Idaho Code {sec} held (Title 63 chapter 30 scope)")
held("https://www.idsaves.org/tax-benefits/", "id-ch30", "us-id/statute/63-3022",
     "idsaves.org is the IDeal plan's program site; the deduction is Idaho Code 63-3022 (held); the State Tax "
     "Commission's IDeal page is PRESENT")
other("https://www.cassia.gov/media/Assessor/Forms/Forms_Property/PTR_Tax%20Form-40.pdf", "ABSENT", "", "",
      "a county assessor's copy of the 2024 Idaho Form 40 (not the publisher); the State Tax Commission's 2024 Form 40 "
      "file was not found (tax.idaho.gov forms paths read 2026-10-06); 2021-2023 and 2025 Form 40 are held or PRESENT")
# Illinois
held("us-il/regulation/title-86/part-100", "il-reg", "us-il/regulation/title-086/chapter-i/part-100",
     "86 Ill. Adm. Code Part 100 held (wave-4 JCAR scope)", "https://www.ilga.gov/ftp/JCAR/AdminCode/086/086001000sections.html")
for url in ["https://www.ilga.gov/Documents/legislation/ilcs/documents/003500050K244.htm"]:
    held(url, "il-core", "us-il/statute/35/5/244-current", "35 ILCS 5/244 held (resident core)")
for url in ["https://www.ilga.gov/Legislation/ILCS/fulltext.asp?DocName=003500050K212&SeqStart=15400000&SeqEnd=16000000",
            "https://www.ilga.gov/legislation/ilcs/fulltext.asp?DocName=003500050K212"]:
    held(url, "il-core", "us-il/statute/35/5/212-current", "35 ILCS 5/212 held (resident core)")
held("https://www.ilga.gov/documents/legislation/ilcs/documents/003500050K208.htm", "il-core", "us-il/statute/35/5/208-current",
     "35 ILCS 5/208 held (resident core)")
held("https://brightstart.com/account/illinois-taxpayer-guide/", "il-core", "us-il/statute/35/5/203-current",
     "brightstart.com is the plan's program site; the deduction is 35 ILCS 5/203(a)(2)(Y) (held)")
for url in ["https://ilga.gov/documents/legislation/publicacts/102/102-0700.htm",
            "https://www.ilga.gov/Documents/legislation/publicacts/102/PDF/102-0700.pdf",
            "https://www.ilga.gov/Legislation/PublicActs/Fulltext.asp?Name=102-0700&GA=102",
            "https://www.ilga.gov/Documents/legislation/103/HB/10300HB4917.htm",
            "https://www.ilga.gov/legislation/ilcs/ilcs5.asp?ActID=577&ChapterID=8",
            "https://witnessslips.ilga.gov/legislation/ilcs/ilcs5.asp?ActID=577&ChapterID=8"]:
    other(url, "OUTREACH", "", "", OUTREACH_ILGA + ("; 7 sections of 35 ILCS 5 are held in the resident core" if "ilcs5" in url else ""))
# Indiana
for url in ["http://iga.in.gov/legislative/laws/2021/ic/titles/006", "http://iga.in.gov/legislative/laws/2021/ic/titles/6",
            "https://iga.in.gov/laws/2021/ic/titles/6", "https://iga.in.gov/laws/2022/ic/titles/6",
            "https://iga.in.gov/laws/2024/ic/titles/6"]:
    held(url, "in-t6", "us-in/statute/6",
         "IC Title 6 is held as its 2025 edition (iga.in.gov/ic/2025/Title_6.html); the earlier-year title pages are "
         "the IGA JavaScript application and serve no text")
held("https://law.justia.com/codes/indiana/title-6/article-3/chapter-1/section-6-3-1-3-5/", "in-t6",
     "us-in/statute/6-3-1-3.5", "mirror; IC 6-3-1-3.5 held (official IGA 2025 edition)")
other("https://iga.in.gov/legislative/2025/bills/senate/243", "OUTREACH", "", "",
      "the IGA bill page is a JavaScript application (691-byte shell to the corpus client); no enrolled-act link in the "
      "served HTML for the 2025 SB 243")
IN_T4 = "us-in/statute/2026-10-06-w6-income-tax-statute-in-us-in-title-4"
IN_ZIP = "https://iga.in.gov/ic/2026/2026-Indiana-Code-html.zip"
for url, path in [("https://law.justia.com/codes/indiana/2022/title-4/article-10/chapter-22/", "us-in/statute/4-10-22"),
                  ("https://law.justia.com/codes/indiana/2022/title-4/article-10/chapter-22/section-4-10-22-2/",
                   "us-in/statute/4-10-22-2"),
                  ("https://law.justia.com/codes/indiana/2022/title-4/article-10/chapter-22/section-4-10-22-4/",
                   "us-in/statute/4-10-22-4")]:
    other(url, "PRESENT", IN_T4, path,
          "mirror; IC 4-10-22 (use of excess reserves; automatic taxpayer refund) extracted from the General Assembly's "
          "2026 Indiana Code HTML release with the indiana-code adapter (Title 4, manifests/us-in-w6-indiana-code-title-4.yaml)",
          IN_ZIP)
# Kansas
for sec, urls in {
    "79-32-205": ["https://kslegislature.gov/b2023_24/laws/079_000_0000_chapter/079_032_0000_article/079_032_0205_section/079_032_0205_k/"],
    "79-32-271": ["https://kslegislature.gov/b2023_24/laws/079_000_0000_chapter/079_032_0000_article/079_032_0271_section/079_032_0271_k/",
                  "http://www.kslegislature.org/li_2022/b2021_22/statute/079_000_0000_chapter/079_032_0000_article/079_032_0271_section/079_032_0271_k/"],
    "79-32-110": ["https://kslegislature.gov/li_2022/b2021_22/statute/079_000_0000_chapter/079_032_0000_article/079_032_0110_section/079_032_0110_k/"],
    "79-32-111c": ["https://kslegislature.gov/li_2022/b2021_22/statute/079_000_0000_chapter/079_032_0000_article/079_032_0111c_section/079_032_0111c_k/"],
    "79-32-119": ["https://kslegislature.gov/li_2022/b2021_22/statute/079_000_0000_chapter/079_032_0000_article/079_032_0119_section/079_032_0119_k/"],
    "79-32-117": ["https://ksrevisor.gov/statutes/chapters/ch79/079_032_0117.html"],
    "79-32-121": ["https://ksrevisor.gov/statutes/chapters/ch79/079_032_0121.html",
                  "https://law.justia.com/codes/kansas/chapter-79/article-32/section-79-32-121/"],
}.items():
    for url in urls:
        held(url, "ks-a32", f"us-ks/statute/{sec}",
             f"K.S.A. {sec} held (current Revisor text, chapter 79 article 32 scope)"
             + ("; the Legislature's biennium page is an earlier edition of the same section" if "kslegislature" in url else "")
             + ("; mirror" if "justia" in url else ""))
# Kentucky
held("https://codes.findlaw.com/ky/title-xi-revenue-and-taxation/ky-rev-st-sect-141-066.html", "ky-141", "us-ky/statute/krs/141.066",
     "mirror; KRS 141.066 held (LRC chapter 141 scope)")
other("https://taxsim.nber.org/historical_state_tax_forms/KY/2021/Form%20740%20Packet%20Instructions-2021.pdf", "OUTREACH", "", "",
      "third-party repost (NBER TAXSIM); the Department's Find a Form library is client-rendered and no 2021 Form 740 "
      "packet instructions URL is confirmable on revenue.ky.gov (known block)")
for url in ["https://revenue.ky.gov/Forms/1999_42a740p.pdf", "https://revenue.ky.gov/Forms/2000_42a740p.pdf"]:
    other(url, "ABSENT", "", "", "HTTP 404 'File Not Found' (also with the upper-case 42A740P spelling the 2001-2005 files use, "
          "2026-10-06); the Forms library serves Schedule P from 2001")
# Louisiana
for d, sec in [("101760", "47:293"), ("101761", "47:294"), ("101769", "47:297.4"), ("101946", "47:32"), ("102133", "47:44.1"),
               ("102518", "47:79"), ("453085", "47:297.8"), ("453233", "47:6104")]:
    for url in [f"https://legis.la.gov/Legis/Law.aspx?d={d}", f"https://www.legis.la.gov/Legis/Law.aspx?d={d}",
                f"https://www.legis.la.gov/legis/Law.aspx?d={d}"]:
        held(url, "la-t47", f"us-la/statute/{sec}", f"La. R.S. {sec} held (Title 47 scope; Law.aspx?d={d})")
held("https://law.justia.com/codes/louisiana/2021/revised-statutes/title-47/rs-298/", "la-t47", "us-la/statute/47:298",
     "mirror; La. R.S. 47:298 held (repealed by Acts 2021, No. 395, eff. 2022-01-01, as the official page prints)")
held("https://law.justia.com/codes/louisiana/revised-statutes/title-47/rs-47-293/", "la-t47", "us-la/statute/47:293",
     "mirror; La. R.S. 47:293 held")
other("https://www.bls.gov/news.release/archives/cpi_01132026.htm", "OUT-OF-SCOPE", "", "",
      "BLS Consumer Price Index news release (December 2025 data): a federal statistical release, not a Louisiana rule")
# Massachusetts
for sec in ["2", "3", "4", "5", "6", "9"]:
    held(f"https://malegislature.gov/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section{sec}", "ma-c62", f"us-ma/statute/62/{sec}",
         f"M.G.L. c. 62, s. {sec} held (chapter 62 scope)")
held("https://malegislature.gov/Laws/GeneralLaws/PartI/TitleIX/Chapter62/section4", "ma-c62", "us-ma/statute/62/4",
     "M.G.L. c. 62, s. 4 held (chapter 62 scope)")
held("https://law.justia.com/codes/massachusetts/2022/part-i/title-ix/chapter-62/section-6/", "ma-c62", "us-ma/statute/62/6",
     "mirror; M.G.L. c. 62, s. 6 held")
for sec in ["2", "3", "6"]:
    held(f"https://www.mass.gov/info-details/mass-general-laws-c62-ss-{sec}", "ma-c62", f"us-ma/statute/62/{sec}",
         f"Trial Court Law Libraries' reproduction of M.G.L. c. 62, s. {sec}; the General Court's text is held")
for year in range(2011, 2023):
    other(f"https://www.mass.gov/doc/{year}-form-1-instructions/download", "ABSENT", "", "",
          "HTTP 404 (plain and chrome120, 2026-10-06); mass.gov now lists personal income tax forms for 2023-2025 only "
          "(/info-details/personal-income-tax-forms-and-instructions)")
for slug in ["2021-form-1-massachusetts-resident-income-tax-return", "2021-schedule-b-interest-dividends-and-certain-capital-gains-and-losses",
             "2021-schedule-nts-l-nrpy-no-tax-status-and-limited-income-credit"]:
    other(f"https://www.mass.gov/doc/{slug}/download", "ABSENT", "", "",
          "HTTP 404 (plain and chrome120, 2026-10-06); mass.gov lists personal income tax forms for 2023-2025 only")
# Maryland
for url in ["https://marylandtaxes.gov/forms/22_forms/502CR.pdf", "https://www.marylandtaxes.gov/forms/20_forms/502CR.pdf",
            "https://www.marylandtaxes.gov/forms/21_forms/502CR.pdf"]:
    other(url, "ABSENT", "", "", "HTTP 404; the Comptroller's content/dam/mdcomp/tax/forms/<year>/502CR.pdf path also answers 404 "
          "for 2020-2022 (2023-2025 are PRESENT); the prior-year forms index is a ServiceNow knowledge base (known block)")
other("https://www.marylandtaxes.gov/forms/current_forms/Md_Tax_Computation.pdf", "ABSENT", "", "",
      "HTTP 404 (2026-10-06); the tax computation worksheet is printed in the Resident Booklets (PRESENT)")
other("https://services.marylandcomptroller.gov/taxes/en/maryland-pension-exclusion?id=kb_article_view&sysparm_article=KB0010012",
      "OUTREACH", "", "", "Comptroller ServiceNow knowledge base: HTTP 200 JavaScript shell with no article text (known block)")
other("https://www.marylandtaxes.gov/new-tax-year-update.php", "OUTREACH", "", "",
      "redirects into the Comptroller ServiceNow knowledge base ('What's New for the 2026 Tax Filing'), a JavaScript shell with no text")
held("https://law.justia.com/codes/maryland/2022/tax-general/title-10/subtitle-2/part-ii/", "md-gtg", "us-md/statute/gtg/10-204",
     "mirror; Tax-General Title 10, Subtitle 2, Part II (Maryland adjusted gross income, 10-204 to 10-210) held in the "
     "Maryland General Assembly article scope")
for url in ["https://govt.westlaw.com/mdc/Browse/Home/Maryland/MarylandCodeCourtRules?guid=NAE804370A64411DBB5DDAC3692B918BC&transitionType=Default&contextData=%28sc.Default%29",
            "https://govt.westlaw.com/mdc/Document/NF59A76006EA511E8ABBEE50DE853DFF4?viewType=FullText&originationContext=documenttoc&transitionType=CategoryPageItem&contextData=(sc.Default)"]:
    other(url, "OUTREACH", "", "", "vendor (Westlaw); govt.westlaw.com answers a Cloudflare 'Just a moment' challenge (HTTP 403); "
          "the Maryland Code text is held from mgaleg.maryland.gov (gtg article) but the section behind this link cannot be read")
# Maine
for sec, urls in {
    "5111": ["https://legislature.maine.gov/statutes/36/title36sec5111.html", "https://www.mainelegislature.org/legis/statutes/36/title36sec5111.html"],
    "5122": ["https://legislature.maine.gov/statutes/36/title36sec5122.html", "https://www.mainelegislature.org/legis/statutes/36/title36sec5122.html"],
    "5124-C": ["https://legislature.maine.gov/statutes/36/title36sec5124-C.html", "https://www.mainelegislature.org/legis/statutes/36/title36sec5124-C.html"],
    "5126-A": ["https://legislature.maine.gov/statutes/36/title36sec5126-A.html", "https://www.mainelegislature.org/legis/statutes/36/title36sec5126-A.html"],
    "5213-A": ["https://legislature.maine.gov/statutes/36/title36sec5213-A.html"],
    "5219-KK": ["https://legislature.maine.gov/statutes/36/title36sec5219-KK.html", "https://www.mainelegislature.org/legis/statutes/36/title36sec5219-KK.html"],
    "5219-S": ["https://legislature.maine.gov/statutes/36/title36sec5219-S.html", "https://www.mainelegislature.org/legis/statutes/36/title36sec5219-S.html"],
    "5403": ["https://legislature.maine.gov/statutes/36/title36sec5403.html", "https://www.mainelegislature.org/legis/statutes/36/title36sec5403.html"],
    "111": ["https://www.mainelegislature.org/legis/statutes/36/title36sec111.html"],
    "5125": ["https://www.mainelegislature.org/legis/statutes/36/title36sec5125.html"],
    "5218": ["https://www.mainelegislature.org/legis/statutes/36/title36sec5218.html"],
    "5219-SS": ["https://www.mainelegislature.org/legis/statutes/36/title36sec5219-SS.html"],
}.items():
    for url in urls:
        held(url, "me-t36", f"us-me/statute/36/{sec}", f"36 M.R.S. {sec} held (Title 36 scope)"
             + ("; mainelegislature.org is the Legislature's own domain" if "mainelegislature" in url else ""))
held("https://www.nextgenforme.com/maine-state-tax-deduction/", "me-t36", "us-me/statute/36/5122",
     "nextgenforme.com is the plan's program site (Finance Authority of Maine); the deduction is 36 M.R.S. 5122 (held)")
# Michigan
held("us-mi/form/individual_income_tax_forms/michigan.gov/taxes/source/media/project/websites/taxes/forms/iit/ty2025/mi-1040-book",
     "mi-w5", "us-mi/form/treasury/ty2025/mi-1040-book", "the 2025 MI-1040 Book is held (wave-5 forms scope, same file)",
     "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2025/MI-1040-Book.pdf")
held("https://www.legislature.mi.gov/documents/mcl/pdf/mcl-act-281-of-1967.pdf", "mi-206", "us-mi/statute/206",
     "the Income Tax Act of 1967 (Act 281) is MCL chapter 206, held section by section (307 sections)")
MI_CR7 = ("michigan.gov answers HTTP 404 to the chrome120 client (2026-10-06); no year's forms index (2021-2025 read) lists "
          "the MI-1040CR-7 home heating credit forms any more")
for url in ["https://www.michigan.gov/-/media/Project/Websites/taxes/2022RM/IIT/BOOK_MI-1040CR-7.pdf?rev=d7990c15e0034d768a43c47b6d3ba0ac",
            "https://www.michigan.gov/-/media/Project/Websites/taxes/2022RM/IIT/MI-1040CR7.pdf?rev=84f72df3f8664b96903aa6b655dc34d2",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/2022/2022-IIT-Forms/BOOK_MI-1040CR-7.pdf?rev=d765b421bc7343c0a54793499dc550db&hash=0B10BE7DD0B91D7F609230E8F636EBC8",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/2022/2022-IIT-Forms/MI-1040CR7.pdf",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/2023/2023-IIT-Forms/BOOK_MI-1040CR-7.pdf?rev=048b871ae3294dec8ca7761afb2d8f78&hash=C3FFD92D4D764FFFE75A88FE25F09C97",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/2023/2023-IIT-Forms/MI-1040CR7.pdf",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2024/BOOK_MI-1040CR-7.pdf",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2024/MI-1040CR-7.pdf",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2025/MI-1040CR-7-Book.pdf"]:
    other(url, "ABSENT", "", "", MI_CR7)
other("https://www.semcoenergygas.com/wp-content/uploads/2022-MI-1040CR7.pdf", "ABSENT", "", "",
      "third-party repost (a utility's copy) of the 2022 MI-1040CR-7; the official copy is gone: " + MI_CR7)
other("https://www.michigan.gov/taxes/iit/accordion/credits/table-a-2022-home-heating-credit-mi-1040cr-7-standard-allowance",
      "ABSENT", "", "", "HTTP 404 (chrome120); michigan.gov now publishes only the current-year Table A "
      "(/taxes/iit/tax-guidance/credits-exemptions/home-heating-credit/table-a-...); the 2022 edition is gone")
for url in ["https://www.michigan.gov/-/media/Project/Websites/taxes/2022RM/UNCAT/2019_Taxpayer_Assistance_Manual.pdf",
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/MISC/Tax-Professionals/Taxpayer_Assistance_Manual.pdf"]:
    other(url, "ABSENT", "", "", "HTTP 404 (chrome120, 2026-10-06); no current address found")
other("https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/", "OUT-OF-SCOPE", "", "",
      "a media-library folder path, not a document (HTTP 404 to chrome120)")
other("https://www.michigan.gov/taxes/iit/retirement-and-pension-benefits/michigan-standard-deduction", "ABSENT", "", "",
      "HTTP 404 (chrome120); the retirement-and-pension guidance moved to /taxes/iit/tax-guidance/tax-situations/"
      "retirement-and-pension-benefits (PRESENT), which links no standard-deduction subpage")


# ------------------------------------------------------------------ outputs
def source_id(path: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    if len(slug) > 90:
        slug = slug[:80] + "-" + hashlib.sha1(path.encode()).hexdigest()[:8]
    return slug


def manifest_entries() -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for jur, cls, url, path, title, year, subtype, opts in DOCS:
        if path in seen:
            raise SystemExit(f"duplicate citation path {path}")
        seen.add(path)
        fmt = "pdf" if (url.lower().split("?")[0].endswith(".pdf") or "/download" in url or "getPDF" in url
                        or "getDocument" in url) else "html"
        extraction: dict[str, Any] = {"segmentation": "single_block"} if fmt == "pdf" else {}
        if opts.get("sel"):
            extraction["html_content_selector"] = opts["sel"]
        if opts.get("keep"):
            extraction["html_keep_default_drop_selectors"] = list(opts["keep"])
        meta: dict[str, Any] = {
            "primary_source": True,
            "source_authority": AUTHORITY[jur] if cls != "statute" else "state legislature",
            "document_subtype": subtype,
            "program": "individual_income_tax",
            "source_family": f"w6-tax-ia-mi-{FAMILY[cls]}",
            "discovered_via": "wave-6 program-bundle gaps 2026-10-06 (tax-ia-mi.csv); fetched and read 2026-10-06",
        }
        if year:
            meta["tax_year"] = str(year)
        if opts.get("note"):
            meta["source_note"] = opts["note"]
        entry: dict[str, Any] = {
            "source_id": source_id(path),
            "jurisdiction": jur,
            "document_class": cls,
            "title": title,
            "source_url": url,
            "source_format": fmt,
            "source_as_of": SOURCE_AS_OF,
            "citation_path": path,
        }
        if year:
            entry["expression_date"] = f"{year}-01-01"
        if extraction:
            entry["extraction"] = extraction
        entry["metadata"] = meta
        if opts.get("request"):
            entry["request"] = dict(opts["request"])
        out.setdefault((jur, cls), []).append(entry)
    return out


def write_manifests() -> list[Path]:
    paths = []
    for (jur, cls), docs in sorted(manifest_entries().items()):
        path = ROOT / "manifests" / f"{jur}-w6-income-tax-{MANIFEST_SUFFIX[cls]}.yaml"
        body = {"version": version(jur, cls), "documents": docs}
        path.write_text(yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=120))
        paths.append(path)
    return paths


def write_decisions(work_order: Path, out: Path) -> dict[str, int]:
    by_key: dict[str, tuple[str, str, str, str]] = {}
    for jur, cls, url, path, _title, _year, _sub, opts in DOCS:
        for key in [url, *opts.get("ids", [])]:
            by_key[key] = ("PRESENT", f"{jur}/{cls}/{version(jur, cls)}", path, url)
    counts: dict[str, int] = {}
    rows = list(csv.DictReader(work_order.open()))
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "jurisdiction", "programs", "action", "new_status", "scope_version", "citation_path",
                         "official_url", "note"])
        for row in rows:
            keys = [row["id"], row["bundle_url"], row["bundle_path"]]
            hit = next((by_key[k] for k in keys if k and k in by_key), None)
            if hit:
                status, scope, cpath, official = hit
                note = "extracted 2026-10-06"
                if official != (row["bundle_url"] or official):
                    note += f"; same document as the bundle address ({row['bundle_url'] or row['bundle_path']})"
            else:
                other_hit = next((k for k in keys if k and k in OTHER), None)
                if other_hit is None:
                    status, scope, cpath, official, note = ("SKIPPED", "", "", row["bundle_url"], "not reached in the time box")
                else:
                    status, scope, cpath, note = OTHER[other_hit]
                    official = OFFICIAL_URL.get(other_hit, row["bundle_url"] if status != "ALREADY-HELD" else "")
            counts[status] = counts.get(status, 0) + 1
            writer.writerow([row["id"], row["jurisdiction"], row["programs"], row["action"], status, scope, cpath,
                             official, note])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-order", type=Path)
    parser.add_argument("--decisions", type=Path)
    args = parser.parse_args()
    for path in write_manifests():
        print(path.relative_to(ROOT))
    if args.work_order and args.decisions:
        print(write_decisions(args.work_order, args.decisions))


if __name__ == "__main__":
    main()
