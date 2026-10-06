#!/usr/bin/env python3
"""Wave 6, group `federal`: write the decisions CSV (one row per work-order row).

    uv run python scripts/build_w6_federal_decisions.py \
        --work-order <bundle-gaps worktree>/docs/coverage/program-bundle-gaps-2026-10-06/wave6/federal.csv \
        --base /Users/pavelmakarchuk/axiom-corpus/data/corpus

Every PRESENT and ALREADY-HELD row is verified before it is written: the cited citation path must be a
row of the cited scope, read from the local provisions file or, for a locked scope that is not on
disk, from the git blob its lock file names. A row that does not verify stops the script.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_w6_federal_manifests as manifests  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/ingest-runs/2026-10-06-w6-federal-decisions.csv"
COLUMNS = [
    "id",
    "jurisdiction",
    "programs",
    "action",
    "new_status",
    "scope_version",
    "citation_path",
    "official_url",
    "note",
]

OLRC = "https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc{title}@119-103.zip"
USC_VERSION = "2026-10-06-w6-federal-usc-closure"
USC_MEDICAID_VERSION = "2026-10-06-w6-federal-usc-medicaid-sections"
ECFR = "2026-10-06-w6-federal-ecfr-closure"
ECFR_URL = "https://www.ecfr.gov/api/versioner/v1/full/2026-10-05/title-{title}.xml?part={part}"

# Scopes already on the controller's disk (signed or unsigned) that hold a work-order document.
TAX_RECOVERY = "us/statute/2026-07-13-recovery-r2026-07-15-self-contained-r2026-07-17-dedup"
TAX_CLOSURE = "us/statute/2026-09-13-tax-statute-closure-31-title-26"
PART1 = "us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated"
FORMS_0910 = "us/form/2026-09-10-tax-irs-forms-ty2025"
FORMS_0915 = "us/form/2026-09-15-irs-forms-ty2025"
POMS_SI = "us/manual/2026-09-10-ssi-poms-si"
AUTO = ""  # official_url read from the held row (its source_url)

HELD = "ALREADY-HELD"
OUT_OF_SCOPE = "OUT-OF-SCOPE"


def held(scope: str, path: str, url: str, note: str) -> tuple[str, str, str, str, str]:
    return (HELD, scope, path, url, note)


STATIC: dict[str, tuple[str, str, str, str, str]] = {
    # EXTRACT-MANIFEST rows: every one is already held by a later scope
    **{
        f"us/form/irs/ty{y}/i1040sca-line-5a-general-sales-taxes": held(
            "us/form/2026-09-24-irs-optional-sales-tax-tables-ty2021"
            if y == "2021"
            else "us/form/2026-09-24-irs-optional-sales-tax-tables-ty2022-2025",
            f"us/form/irs/ty{y}/i1040sca-line-5a-general-sales-taxes",
            AUTO,
            "the 2026-09-24 optional sales tax tables scope (signed, locked) took this manifest entry; not re-extracted",
        )
        for y in ("2021", "2022", "2023", "2024", "2025")
    },
    "us/guidance/hhs/aspe/poverty-guidelines": held(
        "us/guidance/2026-09-13-liheap-annual-figures-2026",
        "us/guidance/hhs/aspe/poverty-guidelines/2026",
        AUTO,
        "the manifest's undated path was never extracted; the same ASPE page (same source URL) is held as its "
        "2026 edition under .../poverty-guidelines/2026",
    ),
    "us/guidance/usda/fns/snap-fy2027-cola": held(
        "us/guidance/2026-09-24-snap-fy2027-cola",
        "us/guidance/usda/fns/snap-fy2027-cola",
        AUTO,
        "signed, locked scope of 2026-09-24 holds the FY 2027 COLA memorandum (7 pages); not re-extracted",
    ),
    "us/form/cms/chip-children-coverage-map": held(
        "us/form/2026-07-05-cms-chip-children-coverage-map",
        "us/form/cms/chip-children-coverage-map",
        "https://www.medicaid.gov/media/file/chip-program-children-map-04162025.json",
        "held from the same source URL (the CMS map JSON of 2025-04-16)",
    ),
    # FETCH rows that are held, out of scope, or carried elsewhere
    "https://data.medicaid.gov/dataset/d7e4cccb-1c56-5b5d-acce-5e7744c6d3b4": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://data.medicaid.gov/dataset/d7e4cccb-1c56-5b5d-acce-5e7744c6d3b4",
        "data.medicaid.gov dataset landing page (a data catalog record rendered by JavaScript), not a source of rules",
    ),
    "https://download.medicaid.gov/data/medicaid-and-chip-eligibility-levels.xy8t-auhk.csv": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://download.medicaid.gov/data/medicaid-and-chip-eligibility-levels.xy8t-auhk.csv",
        "dataset export (CSV of state eligibility levels); the CMS eligibility-levels page is held at "
        "us/form/cms/medicaid-chip-bhp-eligibility-levels",
    ),
    "https://fns-prod.azureedge.us/sites/default/files/resource-files/WICPC2018FoodPackage-1.pdf": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://fns-prod.azureedge.us/sites/default/files/resource-files/WICPC2018FoodPackage-1.pdf",
        "WIC Participant and Program Characteristics 2018: Food Packages and Costs, Final Report (November 2020), a "
        "contractor research study for FNS's Office of Policy Support; third-party analysis, not a source of rules",
    ),
    "https://secure.ssa.gov/POMS.NSF/lnx/0501415057": held(
        POMS_SI,
        "us/manual/ssa/poms/si/01415.057",
        AUTO,
        "POMS SI 01415.057 (January 2025 optional supplementary payment levels) is a section of the SI 01415 subchapter taken whole",
    ),
    "https://uscode.house.gov/view.xhtml?req=(title:26%20section:63%20edition:prelim)": held(
        "us/statute/2026-08-03-rulespec-title-26-current-union",
        "us/statute/26/63",
        AUTO,
        "26 U.S.C. 63 is held from the OLRC release point; the prelim reader page answered only the site's "
        "'Under Maintenance' page on 2026-10-06",
    ),
    "https://www.fairfaxcounty.gov/familyservices/employment-and-training/volunteer-income-tax-assistance": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.fairfaxcounty.gov/familyservices/employment-and-training/volunteer-income-tax-assistance",
        "a county service page for a local VITA site, not a source of federal rules; the IRS VITA/TCE eligibility pages "
        "are taken (us/guidance/irs/free-tax-return-preparation-for-qualifying-taxpayers)",
    ),
    "https://www.federalregister.gov/documents/2026/06/03/2026-11094/medicaid-program-community-engagement-requirement-for-certain-individuals": held(
        "us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1",
        "us/rulemaking/federal-register/2026-06-03/2026-11094",
        "https://www.govinfo.gov/content/pkg/FR-2026-06-03/pdf/2026-11094.pdf",
        "the federalregister.gov page redirects to the unblock bot wall; the same FR document (91 FR 33348) is held, "
        "and its 42 CFR 435 amendments are held in the CMS-2454-IFC regulation scope",
    ),
    "https://www.govinfo.gov/content/pkg/FR-2026-06-03/pdf/2026-11094.pdf": held(
        "us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1",
        "us/rulemaking/federal-register/2026-06-03/2026-11094",
        "https://www.govinfo.gov/content/pkg/FR-2026-06-03/pdf/2026-11094.pdf",
        "held from the same govinfo PDF",
    ),
    "https://www.govinfo.gov/content/pkg/GPO-CPRT-105WPRT37945/html/GPO-CPRT-105WPRT37945-2-7.htm": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.govinfo.gov/content/pkg/GPO-CPRT-105WPRT37945/html/GPO-CPRT-105WPRT37945-2-7.htm",
        "1998 Green Book (House Ways and Means committee print WMCP 105-7, section 7): background material and data, "
        "a secondary summary of the programs, not a source of rules (AGENTS.md: primary sources only)",
    ),
    "https://www.govinfo.gov/link/cfr/42/435?link-type=pdf&sectionnum=121&year=mostrecent": held(
        "us/regulation/2026-06-25-title-42-part-435",
        "us/regulation/42/435/121",
        AUTO,
        "the govinfo link resolves to the annual CFR edition (10-1-25) PDF page of 42 CFR 435.121; the section is "
        "held from the eCFR",
    ),
    "https://www.macpac.gov/publication/child-enrollment-in-chip-and-medicaid-by-state/": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.macpac.gov/publication/child-enrollment-in-chip-and-medicaid-by-state/",
        "MACStats Exhibit 32 (enrollment statistics) by MACPAC, a legislative-branch advisory commission; data, not rules",
    ),
    "https://www.macpac.gov/publication/chip-spending-by-state/": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.macpac.gov/publication/chip-spending-by-state/",
        "MACStats Exhibit 33 (spending statistics); data, not rules",
    ),
    "https://www.macpac.gov/publication/medicaid-and-chip-income-eligibility-levels-as-a-percentage-of-the-federal-poverty-level-for-children-and-pregnant-women-by-state/": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.macpac.gov/publication/medicaid-and-chip-income-eligibility-levels-as-a-percentage-of-the-federal-poverty-level-for-children-and-pregnant-women-by-state/",
        "MACStats Exhibit 35, a secondary compilation of state eligibility levels; the rules are the state plans "
        "(CMS eligibility-levels page held at us/form/cms/medicaid-chip-bhp-eligibility-levels)",
    ),
    "https://www.macpac.gov/wp-content/uploads/2022/12/MACSTATS_Dec2022_WEB-508.pdf": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.macpac.gov/wp-content/uploads/2022/12/MACSTATS_Dec2022_WEB-508.pdf",
        "MACStats: Medicaid and CHIP Data Book, December 2022 (172 pages of statistics); data, not rules",
    ),
    "https://www.medicaid.gov/medicaid/financial-management/state-expenditure-reporting-for-medicaid-chip/expenditure-reports-mbescbes": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.medicaid.gov/medicaid/financial-management/state-budget-expenditure-reporting-for-medicaid-and-chip/expenditure-reports-mbes/cbes",
        "index of MBES/CBES expenditure data reports (redirects to the expenditure-reports-mbes/cbes page); data, not rules",
    ),
    "https://www.medicaid.gov/sites/default/files/2023-04/AL-23-0026-RIM2.pdf": held(
        "us/policy/2026-07-05-cms-chip-fcep-spa",
        "us/policy/cms/chip-spa/al/al-23-0026-rim2/pdf",
        "https://www.medicaid.gov/sites/default/files/2023-04/AL-23-0026-RIM2.pdf",
        "byte-identical (sha256 d07ff898...) to the held source fetched from medicaid.gov/CHIP/Downloads/AL-23-0026-RIM2.pdf",
    ),
    # IRS PDFs whose edition is held (the HTML edition, or the same file)
    **{
        f"https://www.irs.gov/pub/{folder}/{name}.pdf": held(
            scope,
            f"us/form/irs/ty2025/{product}",
            AUTO,
            f"the 2025 edition is held ({how}); the PDF prints the same 2025 edition",
        )
        for folder, name, product, scope, how in (
            (
                "irs-pdf",
                "i1040gi",
                "i1040gi",
                FORMS_0910,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-pdf",
                "i1040s8",
                "i1040s8",
                FORMS_0910,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-pdf",
                "i1040sd",
                "i1040sd",
                FORMS_0910,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-pdf",
                "i2441",
                "i2441",
                FORMS_0915,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-pdf",
                "i6251",
                "i6251",
                FORMS_0915,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-pdf",
                "i8863",
                "i8863",
                FORMS_0915,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-pdf",
                "i8960",
                "i8960",
                FORMS_0915,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-pdf",
                "p970",
                "p970",
                FORMS_0915,
                "HTML edition; this PDF is its print_version_pdf",
            ),
            (
                "irs-prior",
                "i1040gi--2025",
                "i1040gi",
                FORMS_0910,
                "HTML edition of the same 2025 instructions",
            ),
            (
                "irs-prior",
                "i1040s8--2025",
                "i1040s8",
                FORMS_0910,
                "HTML edition of the same 2025 instructions",
            ),
            (
                "irs-prior",
                "i1040sd--2025",
                "i1040sd",
                FORMS_0910,
                "HTML edition of the same 2025 instructions",
            ),
            (
                "irs-prior",
                "i8960--2025",
                "i8960",
                FORMS_0915,
                "HTML edition of the same 2025 instructions",
            ),
            (
                "irs-prior",
                "f1040sd--2025",
                "f1040sd",
                FORMS_0910,
                "byte-identical PDF, same sha256",
            ),
            (
                "irs-prior",
                "f1040sse--2025",
                "f1040sse",
                FORMS_0910,
                "byte-identical PDF, same sha256",
            ),
        )
    },
    # CHECK-PUBLISHER
    "https://ccf.georgetown.edu/2024/10/15/more-states-expanding-medicaid-chip-for-pregnant-women-including-immigrants/": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://ccf.georgetown.edu/2024/10/15/more-states-expanding-medicaid-chip-for-pregnant-women-including-immigrants/",
        "Georgetown CCF blog post (third-party analysis); the rules behind it are the state plan options (42 U.S.C. "
        "1396b(v)(4), 1397gg(e)(1)(J)), not one official text",
    ),
    "https://www.medicaidscreener.com/?p=table": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.snapscreener.com/",
        "third-party eligibility screener; the address redirects to snapscreener.com (a calculator)",
    ),
    # OFFICIAL-SOURCE (Cornell LII mirrors)
    "https://www.law.cornell.edu/cfr/text/42/part-435/subpart-D": held(
        "us/regulation/2026-06-25-title-42-part-435",
        "us/regulation/42/435/subpart-D",
        AUTO,
        "Cornell mirror; the official eCFR text of 42 CFR part 435 subpart D is held",
    ),
    "https://www.law.cornell.edu/uscode/text": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://uscode.house.gov/",
        "Cornell's table of contents for the whole U.S. Code, not a document; the cited titles' sections are held or "
        "taken from the OLRC release points",
    ),
    **{
        f"https://www.law.cornell.edu/uscode/text/26/{s}": held(
            scope, f"us/statute/26/{s}", AUTO, "Cornell mirror; the OLRC text is held"
        )
        for s, scope in (
            ("199A", TAX_RECOVERY),
            ("25A", TAX_RECOVERY),
            ("25B", TAX_RECOVERY),
            ("25C", TAX_RECOVERY),
            ("25D", TAX_RECOVERY),
            ("25E", TAX_RECOVERY),
            ("30D", TAX_RECOVERY),
            ("36B", TAX_RECOVERY),
        )
    },
    "https://www.law.cornell.edu/uscode/text/26/subtitle-A/chapter-1/subchapter-A/part-IV/subpart-A": held(
        TAX_RECOVERY,
        "us/statute/26/21",
        AUTO,
        "Cornell mirror of subpart A (nonrefundable personal credits, 26 U.S.C. 21-26): 21, 22, 24, 25A-25E and 26 are "
        "held in this scope, 23 and 25 in us/statute/2026-09-13-tax-statute-closure-31-title-26",
    ),
    "https://www.law.cornell.edu/uscode/text/42/1395w-113": held(
        "us/statute/2026-09-13-medicare-statute-eligibility-premiums-title-42",
        "us/statute/42/1395w–113",
        AUTO,
        "Cornell mirror; held under the OLRC en-dash identifier 1395w–113",
    ),
    "https://www.law.cornell.edu/uscode/text/42/1396u-1": held(
        "us/statute/2026-06-26-medicaid-title-42-r2026-07-15-self-contained-r2026-07-15-self-contained-r2026-07-17-dedup",
        "us/statute/42/1396u–1",
        AUTO,
        "Cornell mirror; held under the OLRC en-dash identifier 1396u–1",
    ),
    "https://www.law.cornell.edu/uscode/text/42/1396u-3": held(
        "us/statute/2026-09-13-medicare-statute-eligibility-premiums-title-42",
        "us/statute/42/1396u–3",
        AUTO,
        "Cornell mirror; held under the OLRC en-dash identifier 1396u–3",
    ),
    "https://www.law.cornell.edu/uscode/text/42/chapter-7/subchapter-IV/part-A": held(
        "us/statute/2026-09-13-tanf-statute-part-a-title-42",
        "us/statute/42/601",
        AUTO,
        "Cornell mirror of title IV-A (TANF); every section 601-619 of the part is held in this scope",
    ),
    "https://www.law.cornell.edu/uscode/text/42/chapter-7/subchapter-XXI": held(
        "us/statute/2026-06-26-chip-title-xxi-title-42",
        "us/statute/42/1397aa",
        AUTO,
        "Cornell mirror of title XXI (CHIP); sections 1397aa-1397mm are held in this scope",
    ),
    # DEAD-LINK
    "https://acf.gov/ocs/law-regulation/liheap-statute-and-regulations": held(
        "us/statute/2026-09-13-liheap-statute-chapter-94-title-42",
        "us/statute/42/8621",
        AUTO,
        "acf.gov answered an AWS WAF challenge (HTTP 202); the page is an index of the LIHEAP statute and regulations, "
        "whose texts are held: 42 U.S.C. 8621-8630 here and 45 CFR 96 (subpart H) in us/regulation/2026-09-13-title-45-part-96",
    ),
    "https://fns-prod.azureedge.net/sites/default/files/resource-files/fna-2008-amended-through-pl-116-94.pdf": held(
        "us/statute/2026-07-22-rulespec-title-7-consolidated",
        "us/statute/7/2011",
        AUTO,
        "the FNS compilation PDF answers HTTP 403 'Web App - Unavailable'; the Food and Nutrition Act of 2008 as "
        "codified (7 U.S.C. 2011-2036d, current law) is held",
    ),
    "https://www.medicaid.gov/federal-policy-guidance/downloads/": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.medicaid.gov/federal-policy-guidance/downloads/",
        "a directory address (HTTP 404), not a document; the letters the bundles cite from it are taken one by one "
        "(us/guidance/cms/sho, cib)",
    ),
    "https://www.medicaid.gov/medicaid/national-medicaid-chip-program-information/medicaid-childrens-health-insurance-program-basic-health-program-eligibility-levels/index.html": held(
        "us/form/2026-05-12-cms-medicaid-chip-bhp-eligibility-levels",
        "us/form/cms/medicaid-chip-bhp-eligibility-levels",
        AUTO,
        "the /index.html address answers 404; the page's current address (without /index.html) is held",
    ),
    # BLOCKED-CHECK
    **{
        f"https://www.cbo.gov/system/files/{p}": (
            OUT_OF_SCOPE,
            "",
            "",
            f"https://www.cbo.gov/system/files/{p}",
            "CBO tax parameter projections workbook (budget-baseline projections, not law); HTTP 403 to the plain client",
        )
        for p in (
            "2024-02/53724-2024-02-Tax-Parameters.xlsx",
            "2025-01/53724-2025-01-Tax-Parameters.xlsx",
            "2026-02/53724-2026-02-Tax-Parameters.xlsx",
        )
    },
    "https://www.congress.gov/bill/101st-congress/senate-bill/3209/text": (
        "OUTREACH",
        "",
        "",
        "https://www.congress.gov/bill/101st-congress/senate-bill/3209/text",
        "congress.gov answers a Cloudflare challenge (HTTP 403 'Just a moment...') to the corpus client; govinfo "
        "BILLS starts with the 103rd Congress and no enacted text of S. 3209 (101st) was identified (PL 101-508, OBRA "
        "1990, is H.R. 5835)",
    ),
    "https://www.fns.usda.gov/sites/default/files/resource-files/WICPC2018FoodPackage-Summary.pdf": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.fns.usda.gov/sites/default/files/resource-files/WICPC2018FoodPackage-Summary.pdf",
        "summary of the WIC Participant and Program Characteristics 2018 food package study (contractor research); "
        "answers today via the FNA CDN, but it is analysis, not rules",
    ),
    "https://www.fns.usda.gov/snap/obbb-ABAWD-Waivers-Implementation-Memo": held(
        "us/guidance/2026-09-13-snap-fns-guidance",
        "us/guidance/usda/fns/snap-obbb-abawd-waivers-implementation-memo",
        AUTO,
        "the address redirects to the FNA memo page; the memorandum it embeds is held",
    ),
    "https://www.fns.usda.gov/snap/simplified-homeless-housing-cost-deduction-questions-and-answers": (
        "ABSENT",
        "",
        "",
        "https://www.fna.usda.gov/snap/simplified-homeless-housing-cost-deduction-questions-and-answers",
        "redirects to fna.usda.gov, which answers HTTP 404 'Page or Content Not Found' on 2026-10-06; the FNA site "
        "search answers 403 'Page or Content Archived' to the corpus client, so no successor address was found",
    ),
    "https://www.medicareinteractive.org/understanding-medicare/": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.medicareinteractive.org/understanding-medicare/",
        "Medicare Rights Center consumer site (third party); HTTP 403",
    ),
    "https://www.medicareinteractive.org/understanding-medicare/cost-saving-programs/medicare-savings-programs-qmb-slmb-qi/medicare-savings-program-income-and-asset-limits": (
        OUT_OF_SCOPE,
        "",
        "",
        "https://www.medicareinteractive.org/understanding-medicare/cost-saving-programs/medicare-savings-programs-qmb-slmb-qi/medicare-savings-program-income-and-asset-limits",
        "Medicare Rights Center (third party); the official MSP limits are taken from Medicare.gov "
        "(us/guidance/cms/medicare-gov/medicare-savings-programs)",
    ),
    "https://www.ssa.gov/OP_Home/cfr20/416/416-0971.htm": held(
        "us/regulation/2026-09-11-title-20-part-416",
        "us/regulation/20/416/971",
        AUTO,
        "SSA's CFR reprint; the eCFR text of 20 CFR 416.971 is held",
    ),
    "https://www.ssa.gov/OP_Home/cfr20/416/416-0974.htm": held(
        "us/regulation/2026-09-11-title-20-part-416",
        "us/regulation/20/416/974",
        AUTO,
        "SSA's CFR reprint; the eCFR text of 20 CFR 416.974 is held",
    ),
    "https://www.ssa.gov/OP_Home/ssact/title16b/1614.htm": held(
        "us/statute/2026-06-20-ssi-title-xvi-title-42-r2026-07-15-self-contained-r2026-07-17-dedup",
        "us/statute/42/1382c",
        AUTO,
        "Social Security Act section 1614 is codified as 42 U.S.C. 1382c, held",
    ),
    "https://www.ssa.gov/OP_Home/ssact/title21/2110.htm": held(
        "us/statute/2026-06-26-chip-title-xxi-title-42",
        "us/statute/42/1397jj",
        AUTO,
        "Social Security Act section 2110 is codified as 42 U.S.C. 1397jj, held",
    ),
    # PATH-ONLY rows held already
    "us/statute/26/662": held(
        "us/statute/2026-09-23-tax-statute-policybench-title-26",
        "us/statute/26/662",
        AUTO,
        "held in the signed 2026-09-23 policybench scope",
    ),
    "us/statute/26/852": held(
        "us/statute/2026-09-23-tax-statute-policybench-title-26",
        "us/statute/26/852",
        AUTO,
        "held in the signed 2026-09-23 policybench scope",
    ),
    "us/statute/42/1396u-1": held(
        "us/statute/2026-06-26-medicaid-title-42-r2026-07-15-self-contained-r2026-07-15-self-contained-r2026-07-17-dedup",
        "us/statute/42/1396u–1",
        AUTO,
        "held under the OLRC en-dash identifier 1396u–1 (the bundle path uses a hyphen)",
    ),
    "us/manual/ssa/poms/si/01415.008": held(
        POMS_SI,
        "us/manual/ssa/poms/si/phi01415.008",
        AUTO,
        "the SI 014 subchapter list (read 2026-10-06) has no national SI 01415.008; the number exists only as the "
        "Philadelphia regional section SI PHI01415.008 (Delaware), which is held",
    ),
    "us/manual/ssa/poms/si/01415.210": held(
        POMS_SI,
        "us/manual/ssa/poms/si/sf01415.210",
        AUTO,
        "no national SI 01415.210 exists; the number is the San Francisco regional section SI SF01415.210 (Hawaii), held",
    ),
    **{
        f"us/regulation/26/1/{fam}": held(
            PART1, f"us/regulation/26/1/{first}", AUTO, f"section-family reference; {note}"
        )
        for fam, first, note in (
            ("1411", "1411-1", "26 CFR 1.1411-0 to 1.1411-10 (1.1411-7 reserved) are held"),
            (
                "199",
                "199A-1",
                "eCFR (2026-10-05) has no 1.199-N sections (the section 199 regulations were removed); "
                "the 1.199A-1 to 1.199A-12 family is held",
            ),
            ("21", "21-1", "26 CFR 1.21-1 to 1.21-4 are held"),
            ("32", "32-2", "26 CFR 1.32-2 and 1.32-3 are held"),
            ("61", "61-1", "26 CFR 1.61-1 to 1.61-21 are held"),
        )
    },
    "us/statute/26/subtitle-A": (
        "SKIPPED",
        "",
        "",
        "https://uscode.house.gov/download/download.shtml",
        "container reference to the whole of Subtitle A (income taxes, about 1,600 sections); extract-usc emits no "
        "subtitle row, the cited sections are held one by one, and a whole-subtitle scope would duplicate the 162 held "
        "title 26 sections: needs the controller's consolidation decision",
    ),
    "us/statute/42/chapter-7": (
        "SKIPPED",
        "",
        "",
        "https://uscode.house.gov/download/download.shtml",
        "container reference to the whole Social Security Act chapter (42 U.S.C. chapter 7, thousands of sections); "
        "extract-usc emits no chapter row and the cited titles (IV-A, XVI, XIX, XXI) are held; needs the "
        "controller's decision",
    ),
}

# PATH-ONLY and redirected rows that the U.S. Code closure scopes carry (filled only if the scope exists).
USC_ROWS: dict[str, tuple[str, str, str]] = {
    **{
        f"us/statute/26/{s}": (f"{USC_VERSION}-title-26", f"us/statute/26/{s}", "26")
        for s in (
            "6428",
            "2010",
            "2001",
            "414",
            "111",
            "199",
            "38",
            "404",
            "652",
            "105",
            "106",
            "1221",
            "1223",
            "408A",
        )
    },
    "https://www.law.cornell.edu/uscode/text/26/6428A": (
        f"{USC_VERSION}-title-26",
        "us/statute/26/6428A",
        "26",
    ),
    "https://www.law.cornell.edu/uscode/text/26/6428B": (
        f"{USC_VERSION}-title-26",
        "us/statute/26/6428B",
        "26",
    ),
    "https://irc.bloombergtax.com/public/uscode/doc/irc/section_222": (
        f"{USC_VERSION}-title-26",
        "us/statute/26/222",
        "26",
    ),
    "https://www.law.cornell.edu/uscode/text/26/subtitle-A/chapter-1/subchapter-A/part-IV/subpart-C": (
        f"{USC_VERSION}-title-26",
        "us/statute/26/33",
        "26",
    ),
    **{
        f"us/statute/42/{s}": (f"{USC_VERSION}-title-42", f"us/statute/42/{s}", "42")
        for s in ("1396", "1396u", "1320b", "401", "430", "9902")
    },
    "https://www.ssa.gov/OP_Home/ssact/title02/0205.htm": (
        f"{USC_VERSION}-title-42",
        "us/statute/42/405",
        "42",
    ),
    **{
        f"us/statute/42/{s}": (f"{USC_MEDICAID_VERSION}-title-42", f"us/statute/42/{s}", "42")
        for s in ("1396a", "1396b", "1396d", "1396p")
    },
    "us/statute/8/1611": (f"{USC_VERSION}-title-8", "us/statute/8/1611", "8"),
    "us/statute/8/1645": (f"{USC_VERSION}-title-8", "us/statute/8/1645", "8"),
    "us/statute/20/1091": (f"{USC_VERSION}-title-20", "us/statute/20/1091", "20"),
    "us/statute/25/1603": (f"{USC_VERSION}-title-25", "us/statute/25/1603", "25"),
    "us/statute/25/1679": (f"{USC_VERSION}-title-25", "us/statute/25/1679", "25"),
    "us/statute/29/206": (f"{USC_VERSION}-title-29", "us/statute/29/206", "29"),
    "us/statute/29/207": (f"{USC_VERSION}-title-29", "us/statute/29/207", "29"),
    "us/statute/38/101": (f"{USC_VERSION}-title-38", "us/statute/38/101", "38"),
}
USC_NOTES = {
    "https://www.law.cornell.edu/uscode/text/26/subtitle-A/chapter-1/subchapter-A/part-IV/subpart-C": "Cornell mirror of subpart C (refundable credits, 26 U.S.C. 31-37): 33, 34, 36, 36A and 37 taken here; 31 "
    "and 35 are held in us/statute/2026-09-13-tax-statute-closure-31-title-26, 32 and 36B in the 2026-07-13 "
    "recovery scope",
    "https://www.ssa.gov/OP_Home/ssact/title02/0205.htm": "Social Security Act section 205 is codified as 42 U.S.C. 405; taken from the OLRC release point",
    "https://irc.bloombergtax.com/public/uscode/doc/irc/section_222": "Bloomberg Tax is a vendor reprint; the official text (26 U.S.C. 222) is taken from the OLRC release point",
}
for _s in ("1396a", "1396b", "1396d", "1396p"):
    USC_NOTES[f"us/statute/42/{_s}"] = (
        "whole section from the OLRC release point; released scopes hold some of its subsections as self-contained "
        "roots, so the controller must swap or consolidate (run note, Collisions)"
    )

# eCFR closure rows
ECFR_ROWS: dict[str, tuple[str, str, str, str]] = {
    "us/regulation/29/541/600": (
        "29",
        "541",
        "us/regulation/29/541/600",
        "29 CFR 541.600 within the whole part 541",
    ),
    "us/regulation/29/541": (
        "29",
        "541",
        "us/regulation/29/541",
        "29 CFR part 541 taken whole (54 sections)",
    ),
    "us/regulation/42/440/255": (
        "42",
        "440",
        "us/regulation/42/440/255",
        "section-scoped run (42 CFR 440.255)",
    ),
    "us/regulation/45/146/113": (
        "45",
        "146",
        "us/regulation/45/146/113",
        "section-scoped run (45 CFR 146.113)",
    ),
    "us/regulation/45/155/20": (
        "45",
        "155",
        "us/regulation/45/155/20",
        "section-scoped run (45 CFR 155.20)",
    ),
    "us/regulation/45/233/20": (
        "45",
        "233",
        "us/regulation/45/233/20",
        "section-scoped run (45 CFR 233.20)",
    ),
    "us/regulation/26/1/414": (
        "26",
        "1",
        "us/regulation/26/1/414-b-1",
        "section-family reference: the 28 live 1.414(b)-1 to 1.414(w)-1 sections taken "
        "(1.414(r)-10 reserved); parenthesised identifiers fold to hyphens",
    ),
}


class ScopeReader:
    """Reads a scope's citation paths from disk, or from the git blob its lock file names."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.cache: dict[str, set[str] | None] = {}
        self.urls: dict[tuple[str, str], str] = {}

    def paths(self, scope: str) -> set[str] | None:
        if scope in self.cache:
            return self.cache[scope]
        jur, cls, version = scope.split("/", 2)
        local = self.base / "provisions" / jur / cls / f"{version}.jsonl"
        text: str | None = None
        if local.exists():
            text = local.read_text(encoding="utf-8")
        else:
            lock = REPO / ".axiom/corpus-locks" / jur / cls / f"{version}.json"
            if lock.exists():
                files = json.loads(lock.read_text())["files"]
                blob = next(
                    (
                        f["git_blob"]
                        for f in files
                        if f["path"].startswith("data/corpus/provisions/")
                        and f["path"].endswith(".jsonl")
                    ),
                    None,
                )
                if blob:
                    text = subprocess.run(
                        ["git", "-C", str(REPO), "cat-file", "-p", blob],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout
        result: set[str] | None = None
        if text is not None:
            result = set()
            for line in text.splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                result.add(record["citation_path"])
                url = record.get("source_url") or (record.get("metadata") or {}).get("source_url")
                if url:
                    self.urls[(scope, record["citation_path"])] = url
        self.cache[scope] = result
        return result

    def source_url(self, scope: str, path: str) -> str:
        self.paths(scope)
        return self.urls.get((scope, path), "")

    def complete(self, scope: str) -> bool:
        jur, cls, version = scope.split("/", 2)
        coverage = self.base / "coverage" / jur / cls / f"{version}.json"
        return coverage.exists() and bool(json.loads(coverage.read_text()).get("complete"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-order", required=True, type=Path)
    parser.add_argument("--base", required=True, type=Path)
    args = parser.parse_args()
    reader = ScopeReader(args.base)
    docs_by_url: dict[str, tuple[manifests.Doc, bool]] = {}
    for doc in manifests.ALL_DOCS:
        docs_by_url[doc.source_url] = (doc, True)
        for url in doc.bundle_rows:
            docs_by_url[url] = (doc, False)
    rows = list(csv.DictReader(args.work_order.open(newline="", encoding="utf-8")))
    out: list[dict[str, str]] = []
    for row in rows:
        key, url = row["id"], row["bundle_url"]
        status = scope = path = official = note = ""
        if url and url in docs_by_url:
            doc, direct = docs_by_url[url]
            family = manifests.FAMILIES[doc.family]
            status, scope, path = (
                "PRESENT",
                f"us/{family.document_class}/{family.version}",
                doc.citation_path,
            )
            official = doc.source_url
            printed = doc.metadata.get("printed_edition")
            note = doc.title + (f"; printed: {printed}" if printed else "")
            if not direct:
                note += "; the bundle address is joined to this document through this row"
            if doc.download_url:
                note += f"; text from the embedded file {doc.download_url}"
            if doc.request and doc.request.get("browser_impersonation"):
                note += "; fetched with the documented chrome120 browser_impersonation option"
        elif key in USC_ROWS:
            version, path, title = USC_ROWS[key]
            scope = f"us/statute/{version}"
            if reader.paths(scope) is None:
                status, scope, path = "SKIPPED", "", ""
                official = "https://uscode.house.gov/download/download.shtml"
                note = (
                    "uscode.house.gov answered only its 'Under Maintenance' page during the run (2026-10-06, "
                    "19:20-23:00 ET); the U.S. Code release point could not be read"
                )
            else:
                status, official = "PRESENT", OLRC.format(title=title)
                note = USC_NOTES.get(key, "whole section from the OLRC release point (current law)")
        elif key in ECFR_ROWS:
            title, part, path, note = ECFR_ROWS[key]
            status, scope = "PRESENT", f"us/regulation/{ECFR}-title-{title}-part-{part}"
            official = ECFR_URL.format(title=title, part=part)
        elif key in STATIC:
            status, scope, path, official, note = STATIC[key]
        else:
            raise SystemExit(f"no decision for {key}")
        if status in {"PRESENT", HELD}:
            held_paths = reader.paths(scope)
            if held_paths is None or path not in held_paths:
                raise SystemExit(f"{key}: {path} is not a row of {scope}")
            if status == "PRESENT" and not reader.complete(scope):
                raise SystemExit(f"{key}: coverage of {scope} is not complete")
            if not official:
                official = reader.source_url(scope, path)
                if not official:
                    raise SystemExit(f"{key}: no source_url on {path} in {scope}")
        out.append(
            {
                "id": key,
                "jurisdiction": row["jurisdiction"],
                "programs": row["programs"],
                "action": row["action"],
                "new_status": status,
                "scope_version": scope,
                "citation_path": path,
                "official_url": official,
                "note": note,
            }
        )
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(out)
    counts: dict[str, int] = {}
    for item in out:
        counts[item["new_status"]] = counts.get(item["new_status"], 0) + 1
    print(f"{OUT.relative_to(REPO)}: {len(out)} rows", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
