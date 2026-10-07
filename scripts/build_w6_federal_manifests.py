#!/usr/bin/env python3
"""Wave 6, group `federal`: manifests for the federal-layer documents of the program bundles.

Reads nothing from the network. Every address, title, printed edition and date below was read
from the publisher on 2026-10-06 (see docs/ingest-runs/2026-10-06-w6-federal.md). One manifest per
family; each family is one scope (one jurisdiction and document class):

    uv run python scripts/build_w6_federal_manifests.py            # write every manifest
    uv run python scripts/build_w6_federal_manifests.py --only irs-forms

`source_url` is the bundle's address whenever that is the address fetched, because the bundle
generator joins documents to manifests by URL. Where the bundle names a mirror, a bot wall or a
dead address, `source_url` is the official alternative and the decisions CSV records the join.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-10-06"
RUN_NOTE = "docs/ingest-runs/2026-10-06-w6-federal.md"
DISCOVERED_VIA = (
    "wave6 program-bundle gaps 2026-10-06 (axiom-corpus#780 bundles; group federal, "
    "docs/coverage/program-bundle-gaps-2026-10-06/wave6/federal.csv)"
)
IMPERSONATE = {"browser_impersonation": True, "browser_impersonation_direct": True}
PAGES = {"page_citation_prefix": "page"}
SINGLE = {"segmentation": "single_block"}
IRS_BOOK = {"html_content_selector": ".book"}
# dol.gov and www.ssa.gov leave the banner <header>/<nav> unclosed; lxml then nests the page body inside
# it and the extractor's header/nav drop removes the content, so these pages are parsed with html.parser.
ARTICLE = {"html_parser": "html.parser", "html_content_selector": "article"}
# HealthCare.gov repeats glossary tooltips inline; they are another term's definition, not this page's text.
HEALTHCARE_GOV = {"html_drop_selectors": [".ds-c-tooltip__content"]}


@dataclass(frozen=True)
class Family:
    key: str
    manifest: str
    version: str
    document_class: str
    authority: str


FAMILIES = {
    f.key: f
    for f in (
        Family(
            "irs-forms",
            "us-irs-w6-federal-forms.yaml",
            "2026-10-06-w6-federal-irs-forms",
            "form",
            "Internal Revenue Service",
        ),
        Family(
            "irs-guidance",
            "us-irs-w6-federal-guidance.yaml",
            "2026-10-06-w6-federal-irs-guidance",
            "guidance",
            "Internal Revenue Service",
        ),
        Family(
            "cms-guidance",
            "us-cms-w6-federal-guidance.yaml",
            "2026-10-06-w6-federal-cms-guidance",
            "guidance",
            "Centers for Medicare & Medicaid Services",
        ),
        Family(
            "cms-state-plans",
            "us-cms-w6-federal-state-plans.yaml",
            "2026-10-06-w6-federal-cms-state-plans",
            "policy",
            "Centers for Medicare & Medicaid Services",
        ),
        Family(
            "agency-guidance",
            "us-agencies-w6-federal-guidance.yaml",
            "2026-10-06-w6-federal-agency-guidance",
            "guidance",
            "federal agency (per document)",
        ),
        Family(
            "ssa-guidance",
            "us-ssa-w6-federal-guidance.yaml",
            "2026-10-06-w6-federal-ssa-guidance",
            "guidance",
            "Social Security Administration",
        ),
        Family(
            "public-laws",
            "us-public-laws-w6-federal.yaml",
            "2026-10-06-w6-federal-public-laws",
            "statute",
            "United States Congress (enrolled public law)",
        ),
        Family(
            "usc-editions",
            "us-usc-historical-editions-w6-federal.yaml",
            "2026-10-06-w6-federal-usc-historical-editions",
            "statute",
            "United States Code (historical printed edition)",
        ),
        Family(
            "federal-register",
            "us-federal-register-w6-federal.yaml",
            "2026-10-06-w6-federal-federal-register",
            "rulemaking",
            "Office of the Federal Register (GPO govinfo edition)",
        ),
    )
}


@dataclass(frozen=True)
class Doc:
    family: str
    source_id: str
    title: str
    source_url: str
    citation_path: str
    source_format: str
    expression_date: str | None = None
    download_url: str | None = None
    extraction: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    bundle_rows: tuple[str, ...] = ()  # work-order ids this document closes (besides source_url)
    metadata: dict[str, Any] = field(default_factory=dict)


def irs_pdf(
    product: str,
    ty: str,
    title: str,
    url: str,
    *,
    subtype: str,
    printed: str,
    expression_date: str | None = None,
) -> Doc:
    form = subtype in {"form", "schedule"}
    return Doc(
        family="irs-forms",
        source_id=f"irs-{product}-ty{ty}",
        title=title,
        source_url=url,
        citation_path=f"us/form/irs/ty{ty}/{product}",
        source_format="pdf",
        expression_date=expression_date or f"{ty}-01-01",
        extraction=SINGLE if form else PAGES,
        metadata={
            "document_subtype": subtype,
            "irs_product_id": product,
            "tax_year": ty,
            "printed_edition": printed,
        },
    )


def irs_html(product: str, ty: str, title: str, url: str, *, subtype: str, printed: str) -> Doc:
    return Doc(
        family="irs-forms",
        source_id=f"irs-{product}-ty{ty}",
        title=title,
        source_url=url,
        citation_path=f"us/form/irs/ty{ty}/{product}",
        source_format="html",
        expression_date=f"{ty}-01-01",
        extraction=IRS_BOOK,
        metadata={
            "document_subtype": subtype,
            "irs_product_id": product,
            "tax_year": ty,
            "printed_edition": printed,
        },
    )


P = "https://www.irs.gov/pub/irs-prior/"
C = "https://www.irs.gov/pub/irs-pdf/"
IRS_FORMS = [
    # current-year PDFs (irs-pdf) whose edition is not already held
    irs_pdf(
        "f5695",
        "2025",
        "Form 5695, Residential Energy Credits (2025)",
        C + "f5695.pdf",
        subtype="form",
        printed="Form 5695 2025",
    ),
    irs_pdf(
        "f8917",
        "2020",
        "Form 8917, Tuition and Fees Deduction (Rev. January 2020)",
        C + "f8917.pdf",
        subtype="form",
        printed="Form 8917 (Rev. January 2020)",
        expression_date="2020-01-01",
    ),
    irs_pdf(
        "i1040sr",
        "2025",
        "Instructions for Schedule R (Form 1040), Credit for the Elderly or the Disabled (2025)",
        C + "i1040sr.pdf",
        subtype="instructions",
        printed="2025 Instructions for Schedule R (Form 1040)",
    ),
    irs_pdf(
        "i5695",
        "2025",
        "Instructions for Form 5695, Residential Energy Credits (2025)",
        C + "i5695.pdf",
        subtype="instructions",
        printed="2025 Instructions for Form 5695",
    ),
    irs_pdf(
        "i8814",
        "2025",
        "Instructions for Form 8814, Parents' Election To Report Child's Interest and Dividends (2025)",
        C + "i8814.pdf",
        subtype="instructions",
        printed="2025 Instructions for Form 8814",
    ),
    irs_pdf(
        "i8936",
        "2025",
        "Instructions for Form 8936, Clean Vehicle Credits (2025)",
        C + "i8936.pdf",
        subtype="instructions",
        printed="2025 Instructions for Form 8936",
    ),
    irs_pdf(
        "i940",
        "2025",
        "Instructions for Form 940, Employer's Annual Federal Unemployment (FUTA) Tax Return (2025)",
        C + "i940.pdf",
        subtype="instructions",
        printed="2025 Instructions for Form 940",
    ),
    irs_pdf(
        "p1101",
        "2026",
        "Publication 1101 (Rev. 4-2026), Tax Counseling for the Elderly Application Package and Guidelines",
        C + "p1101.pdf",
        subtype="publication",
        printed="Publication 1101 (Rev. 4-2026)",
        expression_date="2026-04-01",
    ),
    irs_pdf(
        "p590a",
        "2025",
        "Publication 590-A (2025), Contributions to Individual Retirement Arrangements (IRAs)",
        C + "p590a.pdf",
        subtype="publication",
        printed="Publication 590-A, For use in preparing 2025 Returns",
    ),
    irs_pdf(
        "p6126",
        "2026",
        "Publication 6126 (1-2026), Purchased A New Vehicle?",
        C + "p6126.pdf",
        subtype="publication",
        printed="Publication 6126 (1-2026)",
        expression_date="2026-01-01",
    ),
    # prior-year PDFs (irs-prior; the --YYYY file name is the IRS edition key, page 1 checked)
    irs_pdf(
        "f1040",
        "2021",
        "Form 1040, U.S. Individual Income Tax Return (2021)",
        P + "f1040--2021.pdf",
        subtype="form",
        printed="Form 1040 2021",
    ),
    irs_pdf(
        "f1040s1",
        "2024",
        "Schedule 1 (Form 1040), Additional Income and Adjustments to Income (2024)",
        P + "f1040s1--2024.pdf",
        subtype="schedule",
        printed="SCHEDULE 1 (Form 1040) 2024",
    ),
    irs_pdf(
        "f1040s8",
        "2021",
        "Schedule 8812 (Form 1040), Credits for Qualifying Children and Other Dependents (2021)",
        P + "f1040s8--2021.pdf",
        subtype="schedule",
        printed="SCHEDULE 8812 (Form 1040) 2021",
    ),
    irs_pdf(
        "f2555",
        "2025",
        "Form 2555, Foreign Earned Income (2025)",
        P + "f2555--2025.pdf",
        subtype="form",
        printed="Form 2555 (2025 file)",
    ),
    irs_pdf(
        "f461",
        "2025",
        "Form 461, Limitation on Business Losses (2025)",
        P + "f461--2025.pdf",
        subtype="form",
        printed="Form 461 (2025 file)",
    ),
    irs_pdf(
        "f4952",
        "2025",
        "Form 4952, Investment Interest Expense Deduction (2025)",
        P + "f4952--2025.pdf",
        subtype="form",
        printed="Form 4952 2025",
    ),
    irs_pdf(
        "f5695",
        "2013",
        "Form 5695, Residential Energy Credits (2013)",
        P + "f5695--2013.pdf",
        subtype="form",
        printed="Form 5695 (2013 file)",
    ),
    irs_pdf(
        "f8815",
        "2025",
        "Form 8815, Exclusion of Interest From Series EE and I U.S. Savings Bonds Issued After 1989 (2025)",
        P + "f8815--2025.pdf",
        subtype="form",
        printed="Form 8815 (2025 file)",
    ),
    irs_pdf(
        "f8863",
        "2015",
        "Form 8863, Education Credits (2015)",
        P + "f8863--2015.pdf",
        subtype="form",
        printed="Form 8863 (2015 file)",
    ),
    irs_pdf(
        "f8863",
        "2020",
        "Form 8863, Education Credits (2020)",
        P + "f8863--2020.pdf",
        subtype="form",
        printed="Form 8863 (2020 file)",
    ),
    irs_pdf(
        "f8880",
        "2013",
        "Form 8880, Credit for Qualified Retirement Savings Contributions (2013)",
        P + "f8880--2013.pdf",
        subtype="form",
        printed="Form 8880 (2013 file)",
    ),
    irs_pdf(
        "f8880",
        "2018",
        "Form 8880, Credit for Qualified Retirement Savings Contributions (2018)",
        P + "f8880--2018.pdf",
        subtype="form",
        printed="Form 8880 (2018 file)",
    ),
    irs_pdf(
        "f8880",
        "2021",
        "Form 8880, Credit for Qualified Retirement Savings Contributions (2021)",
        P + "f8880--2021.pdf",
        subtype="form",
        printed="Form 8880 (2021 file)",
    ),
    irs_pdf(
        "f940sa",
        "2013",
        "Schedule A (Form 940) for 2013: Multi-State Employer and Credit Reduction Information",
        P + "f940sa--2013.pdf",
        subtype="schedule",
        printed="Schedule A (Form 940) for 2013",
    ),
    irs_pdf(
        "f940sa",
        "2014",
        "Schedule A (Form 940) for 2014: Multi-State Employer and Credit Reduction Information",
        P + "f940sa--2014.pdf",
        subtype="schedule",
        printed="Schedule A (Form 940) for 2014",
    ),
    irs_pdf(
        "f940sa",
        "2023",
        "Schedule A (Form 940) for 2023: Multi-State Employer and Credit Reduction Information",
        P + "f940sa--2023.pdf",
        subtype="schedule",
        printed="Schedule A (Form 940) for 2023",
    ),
    irs_pdf(
        "i1040gi",
        "2009",
        "Instructions for Form 1040 (2009)",
        P + "i1040gi--2009.pdf",
        subtype="instructions",
        printed="2009 Form 1040 instructions (2009 file)",
    ),
    irs_pdf(
        "i1040s8",
        "2022",
        "Instructions for Schedule 8812, Credits for Qualifying Children and Other Dependents (2022)",
        P + "i1040s8--2022.pdf",
        subtype="instructions",
        printed="2022 Instructions for Schedule 8812",
    ),
    *[
        irs_pdf(
            "i1040sca",
            y,
            f"Instructions for Schedule A (Form 1040), Itemized Deductions ({y})",
            P + f"i1040sca--{y}.pdf",
            subtype="instructions",
            printed={
                "2013": "2013 Schedule A instructions (2013 file)",
                "2018": "2018 Instructions for Schedule A (Rev. February 2020)",
                "2019": "2019 Instructions for Schedule A (Rev. January 2020)",
            }.get(y, f"{y} Instructions for Schedule A"),
        )
        for y in ("2013", "2014", "2015", "2016", "2017", "2018", "2019", "2020")
    ],
    irs_pdf(
        "i1040se",
        "2024",
        "Instructions for Schedule E (Form 1040), Supplemental Income and Loss (2024)",
        P + "i1040se--2024.pdf",
        subtype="instructions",
        printed="2024 Instructions for Schedule E",
    ),
    irs_pdf(
        "i1040sr",
        "2013",
        "Instructions for Schedule R (Form 1040A or 1040), Credit for the Elderly or the Disabled (2013)",
        P + "i1040sr--2013.pdf",
        subtype="instructions",
        printed="2013 Instructions for Schedule R",
    ),
    irs_pdf(
        "i1040sr",
        "2021",
        "Instructions for Schedule R (Form 1040), Credit for the Elderly or the Disabled (2021)",
        P + "i1040sr--2021.pdf",
        subtype="instructions",
        printed="2021 Instructions for Schedule R",
    ),
    irs_pdf(
        "i2441",
        "2013",
        "Instructions for Form 2441, Child and Dependent Care Expenses (2013)",
        P + "i2441--2013.pdf",
        subtype="instructions",
        printed="2013 Instructions for Form 2441",
    ),
    irs_pdf(
        "i2441",
        "2021",
        "Instructions for Form 2441, Child and Dependent Care Expenses (2021)",
        P + "i2441--2021.pdf",
        subtype="instructions",
        printed="2021 Instructions for Form 2441",
    ),
    irs_pdf(
        "i5695",
        "2022",
        "Instructions for Form 5695, Residential Energy Credits (2022)",
        P + "i5695--2022.pdf",
        subtype="instructions",
        printed="2022 Instructions for Form 5695",
    ),
    irs_pdf(
        "i706",
        "2011",
        "Instructions for Form 706 (Rev. August 2011), United States Estate (and Generation-Skipping Transfer) Tax Return",
        P + "i706--2011.pdf",
        subtype="instructions",
        printed="Instructions for Form 706 (Rev. August 2011)",
        expression_date="2011-08-01",
    ),
    irs_pdf(
        "i706",
        "2021",
        "Instructions for Form 706 (Rev. September 2021), United States Estate (and Generation-Skipping Transfer) Tax Return",
        P + "i706--2021.pdf",
        subtype="instructions",
        printed="Instructions for Form 706 (Rev. September 2021)",
        expression_date="2021-09-01",
    ),
    irs_pdf(
        "i706",
        "2022",
        "Instructions for Form 706 (Rev. September 2022), United States Estate (and Generation-Skipping Transfer) Tax Return",
        P + "i706--2022.pdf",
        subtype="instructions",
        printed="Instructions for Form 706 (Rev. September 2022)",
        expression_date="2022-09-01",
    ),
    irs_pdf(
        "i706",
        "2023",
        "Instructions for Form 706 (Rev. September 2023), United States Estate (and Generation-Skipping Transfer) Tax Return",
        P + "i706--2023.pdf",
        subtype="instructions",
        printed="Instructions for Form 706 (Rev. September 2023)",
        expression_date="2023-09-01",
    ),
    irs_pdf(
        "i706",
        "2024",
        "Instructions for Form 706 (Rev. October 2024), United States Estate (and Generation-Skipping Transfer) Tax Return",
        P + "i706--2024.pdf",
        subtype="instructions",
        printed="Instructions for Form 706 (Rev. October 2024)",
        expression_date="2024-10-01",
    ),
    irs_pdf(
        "i8863",
        "2013",
        "Instructions for Form 8863, Education Credits (2013)",
        P + "i8863--2013.pdf",
        subtype="instructions",
        printed="2013 Instructions for Form 8863",
    ),
    irs_pdf(
        "i8863",
        "2021",
        "Instructions for Form 8863, Education Credits (2021)",
        P + "i8863--2021.pdf",
        subtype="instructions",
        printed="2021 Instructions for Form 8863",
    ),
    irs_pdf(
        "i8936",
        "2017",
        "Instructions for Form 8936, Qualified Plug-in Electric Drive Motor Vehicle Credit (2017)",
        P + "i8936--2017.pdf",
        subtype="instructions",
        printed="2017 Instructions for Form 8936",
    ),
    irs_pdf(
        "i8936",
        "2022",
        "Instructions for Form 8936 (Rev. January 2022), Qualified Plug-in Electric Drive Motor Vehicle Credit",
        P + "i8936--2022.pdf",
        subtype="instructions",
        printed="Instructions for Form 8936 (Rev. January 2022)",
    ),
    irs_pdf(
        "i8936",
        "2023",
        "Instructions for Form 8936, Clean Vehicle Credits (2023)",
        P + "i8936--2023.pdf",
        subtype="instructions",
        printed="2023 Instructions for Form 8936",
    ),
    irs_pdf(
        "i8960",
        "2024",
        "Instructions for Form 8960, Net Investment Income Tax (2024)",
        P + "i8960--2024.pdf",
        subtype="instructions",
        printed="2024 Instructions for Form 8960",
    ),
    irs_pdf(
        "p501",
        "2014",
        "Publication 501 (2014), Exemptions, Standard Deduction, and Filing Information",
        P + "p501--2014.pdf",
        subtype="publication",
        printed="Publication 501 (2014 file)",
    ),
    irs_pdf(
        "p501",
        "2022",
        "Publication 501 (2022), Dependents, Standard Deduction, and Filing Information",
        P + "p501--2022.pdf",
        subtype="publication",
        printed="Publication 501 (2022 file)",
    ),
    irs_pdf(
        "p526",
        "2020",
        "Publication 526 (2020), Charitable Contributions",
        P + "p526--2020.pdf",
        subtype="publication",
        printed="Publication 526 (2020 file)",
    ),
    irs_pdf(
        "p526",
        "2021",
        "Publication 526 (2021), Charitable Contributions",
        P + "p526--2021.pdf",
        subtype="publication",
        printed="Publication 526 (2021 file)",
    ),
    irs_pdf(
        "p535",
        "2018",
        "Publication 535 (2018), Business Expenses",
        P + "p535--2018.pdf",
        subtype="publication",
        printed="Publication 535 (2018 file; page 1 is the IRS prior-year caution page)",
    ),
    irs_pdf(
        "p590a",
        "2018",
        "Publication 590-A (2018), Contributions to Individual Retirement Arrangements (IRAs)",
        P + "p590a--2018.pdf",
        subtype="publication",
        printed="Publication 590-A (2018 file; page 1 is the IRS prior-year caution page)",
    ),
    irs_pdf(
        "p596",
        "2021",
        "Publication 596 (2021), Earned Income Credit (EIC)",
        P + "p596--2021.pdf",
        subtype="publication",
        printed="Publication 596, For use in preparing 2021 Returns",
    ),
    irs_pdf(
        "p915",
        "2022",
        "Publication 915 (2022), Social Security and Equivalent Railroad Retirement Benefits",
        P + "p915--2022.pdf",
        subtype="publication",
        printed="Publication 915 (2022 file)",
    ),
    irs_pdf(
        "p929",
        "2021",
        "Publication 929 (2021), Tax Rules for Children and Dependents",
        P + "p929--2021.pdf",
        subtype="publication",
        printed="Publication 929, For use in preparing 2021 Returns",
    ),
    irs_pdf(
        "p970",
        "2021",
        "Publication 970 (2021), Tax Benefits for Education",
        P + "p970--2021.pdf",
        subtype="publication",
        printed="Publication 970, For use in preparing 2021 Returns",
    ),
    irs_pdf(
        "p970",
        "2022",
        "Publication 970 (2022), Tax Benefits for Education",
        P + "p970--2022.pdf",
        subtype="publication",
        printed="Publication 970, For use in preparing 2022 Returns",
    ),
    irs_pdf(
        "p972",
        "2013",
        "Publication 972 (2013), Child Tax Credit",
        P + "p972--2013.pdf",
        subtype="publication",
        printed="Publication 972, For use in preparing 2013 Returns",
    ),
    irs_pdf(
        "p972",
        "2020",
        "Publication 972 (2020), Child Tax Credit and Credit for Other Dependents",
        P + "p972--2020.pdf",
        subtype="publication",
        printed="Publication 972 (2020 file)",
    ),
    # HTML editions
    irs_html(
        "i461",
        "2025",
        "Instructions for Form 461 (2025)",
        "https://www.irs.gov/instructions/i461",
        subtype="instructions",
        printed="Instructions for Form 461 (2025)",
    ),
    irs_html(
        "p15",
        "2026",
        "Publication 15 (2026), (Circular E), Employer's Tax Guide",
        "https://www.irs.gov/publications/p15",
        subtype="publication",
        printed="Publication 15 (2026)",
    ),
    irs_html(
        "p590b",
        "2025",
        "Publication 590-B (2025), Distributions from Individual Retirement Arrangements (IRAs)",
        "https://www.irs.gov/publications/p590b",
        subtype="publication",
        printed="Publication 590-B (2025)",
    ),
    irs_html(
        "p915",
        "2025",
        "Publication 915 (2025), Social Security and Equivalent Railroad Retirement Benefits",
        "https://www.irs.gov/publications/p915",
        subtype="publication",
        printed="Publication 915 (2025)",
    ),
]


def irs_drop(kind: str, number: str, title: str, url: str, expression_date: str) -> Doc:
    slug = f"{'rev-proc' if kind == 'rp' else 'notice'}-{number}"
    return Doc(
        family="irs-guidance",
        source_id=f"irs-{slug}",
        title=title,
        source_url=url,
        citation_path=f"us/guidance/irs/{slug}",
        source_format="pdf",
        expression_date=expression_date,
        extraction=PAGES,
        metadata={
            "document_subtype": "revenue_procedure" if kind == "rp" else "notice",
            "document_number": f"{'Rev. Proc.' if kind == 'rp' else 'Notice'} {number}",
        },
    )


def irs_page(
    slug: str, title: str, url: str, *, subtype: str, extraction: dict | None = None
) -> Doc:
    return Doc(
        family="irs-guidance",
        source_id=f"irs-{slug.replace('/', '-')}",
        title=title,
        source_url=url,
        citation_path=f"us/guidance/irs/{slug}",
        source_format="html",
        extraction=extraction,
        metadata={"document_subtype": subtype},
    )


D = "https://www.irs.gov/pub/irs-drop/"
IRS_GUIDANCE = [
    irs_drop(
        "n",
        "2018-70",
        "Notice 2018-70, Guidance on Qualifying Relative and the Exemption Amount",
        D + "n-18-70.pdf",
        "2018-01-01",
    ),
    irs_drop(
        "n",
        "2023-75",
        "Notice 2023-75, 2024 Limitations Adjusted as Provided in Section 415(d), etc.",
        D + "n-23-75.pdf",
        "2024-01-01",
    ),
    irs_drop(
        "n",
        "2024-80",
        "Notice 2024-80, 2025 Amounts Relating to Retirement Plans and IRAs",
        D + "n-24-80.pdf",
        "2025-01-01",
    ),
    irs_drop(
        "rp",
        "2013-15",
        "Rev. Proc. 2013-15 (2013 adjusted items)",
        D + "rp-13-15.pdf",
        "2013-01-01",
    ),
    irs_drop(
        "rp",
        "2013-35",
        "Rev. Proc. 2013-35 (2014 inflation-adjusted items)",
        D + "rp-13-35.pdf",
        "2014-01-01",
    ),
    irs_drop(
        "rp",
        "2014-61",
        "Rev. Proc. 2014-61 (2015 inflation-adjusted items)",
        D + "rp-14-61.pdf",
        "2015-01-01",
    ),
    irs_drop(
        "rp",
        "2015-53",
        "Rev. Proc. 2015-53 (2016 inflation-adjusted items)",
        D + "rp-15-53.pdf",
        "2016-01-01",
    ),
    irs_drop(
        "rp",
        "2016-55",
        "Rev. Proc. 2016-55 (2017 inflation-adjusted items)",
        D + "rp-16-55.pdf",
        "2017-01-01",
    ),
    irs_drop(
        "rp",
        "2017-58",
        "Rev. Proc. 2017-58 (2018 inflation-adjusted items)",
        D + "rp-17-58.pdf",
        "2018-01-01",
    ),
    irs_drop(
        "rp",
        "2018-22",
        "Rev. Proc. 2018-22 (modifies and supersedes sections 3.08 and 3.10 of Rev. Proc. 2018-18)",
        D + "rp-18-22.pdf",
        "2018-01-01",
    ),
    irs_drop(
        "rp",
        "2018-57",
        "Rev. Proc. 2018-57 (2019 inflation-adjusted items)",
        D + "rp-18-57.pdf",
        "2019-01-01",
    ),
    irs_drop(
        "rp",
        "2019-44",
        "Rev. Proc. 2019-44 (2020 inflation-adjusted items)",
        D + "rp-19-44.pdf",
        "2020-01-01",
    ),
    irs_drop(
        "rp",
        "2020-45",
        "Rev. Proc. 2020-45 (2021 inflation-adjusted items)",
        D + "rp-20-45.pdf",
        "2021-01-01",
    ),
    irs_drop(
        "rp",
        "2023-34",
        "Rev. Proc. 2023-34 (2024 inflation-adjusted items)",
        D + "rp-23-34.pdf",
        "2024-01-01",
    ),
    Doc(
        family="irs-guidance",
        source_id="irs-retirement-plan-cola-table",
        title="Cost-of-Living Adjustments for Retirement Items (IRS table, 2020-2025 columns)",
        source_url="https://www.irs.gov/pub/irs-tege/cola-table.pdf",
        citation_path="us/guidance/irs/retirement-plan-cola-table",
        source_format="pdf",
        extraction=PAGES,
        metadata={"document_subtype": "table"},
    ),
    irs_page(
        "irb/2025-42",
        "Internal Revenue Bulletin: 2025-42",
        "https://www.irs.gov/irb/2025-42_IRB",
        subtype="internal_revenue_bulletin",
        extraction=IRS_BOOK,
    ),
    irs_page(
        "newsroom/2025-401k-ira-limits",
        "401(k) limit increases to $23,500 for 2025, IRA limit remains $7,000",
        "https://www.irs.gov/newsroom/401k-limit-increases-to-23500-for-2025-ira-limit-remains-7000",
        subtype="news_release",
    ),
    irs_page(
        "newsroom/2026-401k-ira-limits",
        "401(k) limit increases to $24,500 for 2026, IRA limit increases to $7,500",
        "https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500",
        subtype="news_release",
    ),
    irs_page(
        "newsroom/2021-charitable-deductions-non-itemizers",
        "Expanded tax benefits help individuals and businesses give to charity during 2021; deductions up to $600 available for cash donations by non-itemizers",
        "https://www.irs.gov/newsroom/expanded-tax-benefits-help-individuals-and-businesses-give-to-charity-during-2021-deductions-up-to-600-available-for-cash-donations-by-non-itemizers",
        subtype="news_release",
    ),
    irs_page(
        "newsroom/what-if-i-withdraw-money-from-my-ira",
        "What if I withdraw money from my IRA?",
        "https://www.irs.gov/newsroom/what-if-i-withdraw-money-from-my-ira",
        subtype="news_release",
    ),
    irs_page(
        "tax-topic/409",
        "Topic no. 409, Capital gains and losses",
        "https://www.irs.gov/taxtopics/tc409",
        subtype="tax_topic",
    ),
    irs_page(
        "tax-topic/452",
        "Topic no. 452, Alimony and separate maintenance",
        "https://www.irs.gov/taxtopics/tc452",
        subtype="tax_topic",
    ),
    irs_page(
        "tax-topic/505",
        "Topic no. 505, Interest expense",
        "https://www.irs.gov/taxtopics/tc505",
        subtype="tax_topic",
    ),
    irs_page(
        "faq/social-security-income",
        "Social Security Income (IRS frequently asked questions)",
        "https://www.irs.gov/faqs/social-security-income",
        subtype="faq",
    ),
    irs_page(
        "faq/government-entities-cafeteria-plans",
        "FAQs for government entities regarding cafeteria plans",
        "https://www.irs.gov/government-entities/federal-state-local-governments/faqs-for-government-entities-regarding-cafeteria-plans",
        subtype="faq",
    ),
    irs_page(
        "free-tax-return-preparation-for-qualifying-taxpayers",
        "Free tax return preparation for qualifying taxpayers",
        "https://www.irs.gov/individuals/free-tax-return-preparation-for-qualifying-taxpayers",
        subtype="program_page",
    ),
    irs_page(
        "tax-counseling-for-the-elderly",
        "Tax Counseling for the Elderly",
        "https://www.irs.gov/individuals/tax-counseling-for-the-elderly",
        subtype="program_page",
    ),
    irs_page(
        "whats-new-estate-and-gift-tax",
        "What's new — Estate and gift tax",
        "https://www.irs.gov/businesses/small-businesses-self-employed/whats-new-estate-and-gift-tax",
        subtype="guidance_page",
    ),
    irs_page(
        "savers-credit",
        "Retirement Savings Contributions Credit (Saver's Credit)",
        "https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-savings-contributions-savers-credit",
        subtype="guidance_page",
    ),
    irs_page(
        "about-schedule-f-form-1040",
        "About Schedule F (Form 1040), Profit or Loss From Farming",
        "https://www.irs.gov/forms-pubs/about-schedule-f-form-1040",
        subtype="product_page",
    ),
]


def cms(
    slug: str,
    title: str,
    url: str,
    fmt: str,
    expression_date: str | None = None,
    *,
    subtype: str,
    extraction: dict | None = None,
    bundle_rows: tuple[str, ...] = (),
) -> Doc:
    return Doc(
        family="cms-guidance",
        source_id=f"cms-{slug.replace('/', '-')}",
        title=title,
        source_url=url,
        citation_path=f"us/guidance/cms/{slug}",
        source_format=fmt,
        expression_date=expression_date,
        extraction=extraction if extraction is not None else (PAGES if fmt == "pdf" else None),
        bundle_rows=bundle_rows,
        metadata={"document_subtype": subtype},
    )


MG = "https://www.medicaid.gov/federal-policy-guidance/downloads/"
CMS_GUIDANCE = [
    cms(
        "sho/10-006",
        "SHO #10-006 (State Health Official letter, July 1, 2010)",
        "https://downloads.cms.gov/cmsgov/archived-downloads/smdl/downloads/sho10006.pdf",
        "pdf",
        "2010-07-01",
        subtype="state_health_official_letter",
    ),
    cms(
        "smd/10-003",
        "SMDL #10-003 (State Medicaid Director letter, February 18, 2010)",
        "https://downloads.cms.gov/cmsgov/archived-downloads/smdl/downloads/smd10003.pdf",
        "pdf",
        "2010-02-18",
        subtype="state_medicaid_director_letter",
    ),
    cms(
        "sho/12-002",
        "SHO #12-002 (State Health Official letter, August 28, 2012)",
        MG + "SHO-12-002.pdf",
        "pdf",
        "2012-08-28",
        subtype="state_health_official_letter",
        bundle_rows=("https://www.medicaid.gov/federal-policy-guidance/downloads/sho-12-002.pdf",),
    ),
    cms(
        "sho/21-007",
        "SHO #21-007, Improving Maternal Health and Extending Postpartum Coverage (December 7, 2021)",
        MG + "sho21007.pdf",
        "pdf",
        "2021-12-07",
        subtype="state_health_official_letter",
    ),
    cms(
        "sho/26-001",
        "SHO #26-001, Implementation of Section 71109 Alien Medicaid Eligibility of Public Law 119-21 (April 8, 2026)",
        MG + "sho26001.pdf",
        "pdf",
        "2026-04-08",
        subtype="state_health_official_letter",
    ),
    cms(
        "cib/2025-05-28",
        "CMCS Informational Bulletin, May 28, 2025",
        MG + "cib05282025.pdf",
        "pdf",
        "2025-05-28",
        subtype="informational_bulletin",
    ),
    cms(
        "cib/2025-11-18",
        "CMCS Informational Bulletin, November 18, 2025",
        MG + "cib11182025.pdf",
        "pdf",
        "2025-11-18",
        subtype="informational_bulletin",
    ),
    cms(
        "cib/2025-12-08",
        "CMCS Informational Bulletin, December 8, 2025",
        MG + "cib12082025.pdf",
        "pdf",
        "2025-12-08",
        subtype="informational_bulletin",
    ),
    cms(
        "cib/2025-12-09",
        "CMCS Informational Bulletin, December 9, 2025",
        MG + "cib12092025.pdf",
        "pdf",
        "2025-12-09",
        subtype="informational_bulletin",
    ),
    cms(
        "cib/2026-04-27",
        "CMCS Informational Bulletin, April 27, 2026",
        MG + "cib04272026.pdf",
        "pdf",
        "2026-04-27",
        subtype="informational_bulletin",
    ),
    cms(
        "macpro-implementation-guide/more-restrictive-requirements-1902f-209b",
        "Implementation Guide: Medicaid State Plan Eligibility More Restrictive Requirements than SSI under 1902(f) (209(b) States)",
        "https://www.medicaid.gov/resources-for-states/downloads/macpro-ig-more-restrictive-requirements-1902f-209bstates.pdf",
        "pdf",
        subtype="implementation_guide",
    ),
    cms(
        "mac-learning-collaborative/magi-household-composition-and-income-training",
        "MAGI-Based Household Income Eligibility Training Manual (last updated December 1, 2020)",
        "https://www.medicaid.gov/state-resource-center/mac-learning-collaboratives/downloads/household-composition-and-income-training.pdf",
        "pdf",
        "2020-12-01",
        subtype="training_manual",
    ),
    cms(
        "medicaid-gov/chip-eligibility-enrollment",
        "CHIP Eligibility & Enrollment",
        "https://www.medicaid.gov/chip/chip-eligibility-enrollment",
        "html",
        subtype="program_page",
    ),
    cms(
        "medicaid-gov/coverage-of-lawfully-residing-children-and-pregnant-women",
        "Medicaid and CHIP Coverage of Lawfully Residing Children & Pregnant Women",
        "https://www.medicaid.gov/medicaid/enrollment-strategies/medicaid-and-chip-coverage-lawfully-residing-children-pregnant-individuals",
        "html",
        subtype="program_page",
    ),
    cms(
        "medicaid-gov/section-1115-demonstrations",
        "Section 1115 Demonstrations",
        "https://www.medicaid.gov/medicaid/section-1115-demonstrations/",
        "html",
        subtype="program_page",
    ),
    cms(
        "medicare-program-general-information",
        "Medicare Program - General Information",
        "https://www.cms.gov/about-cms/what-we-do/medicare",
        "html",
        subtype="program_page",
    ),
    cms(
        "parts-a-b-premiums-deductibles/2021/press-release",
        "2021 Medicare Part B Premiums Remain Steady (CMS press release)",
        "https://www.cms.gov/newsroom/press-releases/2021-medicare-part-b-premiums-remain-steady",
        "html",
        "2021-01-01",
        subtype="press_release",
    ),
    cms(
        "parts-a-b-premiums-deductibles/2022/fact-sheet",
        "2022 Medicare Parts A & B Premiums and Deductibles / 2022 Medicare Part D Income-Related Monthly Adjustment Amounts (CMS fact sheet)",
        "https://www.cms.gov/newsroom/fact-sheets/2022-medicare-parts-b-premiums-deductibles-2022-medicare-part-d-income-related-monthly-adjustment",
        "html",
        "2022-01-01",
        subtype="fact_sheet",
    ),
    cms(
        "parts-a-b-premiums-deductibles/2023/fact-sheet",
        "2023 Medicare Parts A & B Premiums and Deductibles / 2023 Medicare Part D Income-Related Monthly Adjustment Amounts (CMS fact sheet)",
        "https://www.cms.gov/newsroom/fact-sheets/2023-medicare-parts-b-premiums-and-deductibles-2023-medicare-part-d-income-related-monthly",
        "html",
        "2023-01-01",
        subtype="fact_sheet",
    ),
    cms(
        "parts-a-b-premiums-deductibles/2024/fact-sheet",
        "2024 Medicare Parts A & B Premiums and Deductibles (CMS fact sheet)",
        "https://www.cms.gov/newsroom/fact-sheets/2024-medicare-parts-b-premiums-and-deductibles",
        "html",
        "2024-01-01",
        subtype="fact_sheet",
    ),
    cms(
        "parts-a-b-premiums-deductibles/2025/fact-sheet",
        "2025 Medicare Parts A & B Premiums and Deductibles (CMS fact sheet)",
        "https://www.cms.gov/newsroom/fact-sheets/2025-medicare-parts-b-premiums-and-deductibles",
        "html",
        "2025-01-01",
        subtype="fact_sheet",
    ),
    cms(
        "medicare-gov/medicare-savings-programs",
        "Medicare Savings Programs (Medicare.gov)",
        "https://www.medicare.gov/basics/costs/help/medicare-savings-programs",
        "html",
        subtype="beneficiary_page",
    ),
    cms(
        "medicare-gov/medicare-costs",
        "Costs (Medicare.gov)",
        "https://www.medicare.gov/basics/costs/medicare-costs",
        "html",
        subtype="beneficiary_page",
    ),
    cms(
        "healthcare-gov/glossary/federal-poverty-level",
        "Federal Poverty Level (FPL) - Glossary (HealthCare.gov)",
        "https://www.healthcare.gov/glossary/federal-poverty-level-fpl/",
        "html",
        subtype="glossary_entry",
        extraction=HEALTHCARE_GOV,
    ),
    cms(
        "healthcare-gov/glossary/modified-adjusted-gross-income",
        "Modified Adjusted Gross Income (MAGI) - Glossary (HealthCare.gov)",
        "https://www.healthcare.gov/glossary/modified-adjusted-gross-income-magi",
        "html",
        subtype="glossary_entry",
        extraction=HEALTHCARE_GOV,
    ),
    cms(
        "healthcare-gov/childrens-health-insurance-program",
        "Children's Health Insurance Program (CHIP) Eligibility Requirements (HealthCare.gov)",
        "https://www.healthcare.gov/medicaid-chip/childrens-health-insurance-program/",
        "html",
        subtype="beneficiary_page",
        extraction=HEALTHCARE_GOV,
    ),
]


def plan(
    path: str, title: str, url: str, fmt: str, expression_date: str | None = None, *, subtype: str
) -> Doc:
    return Doc(
        family="cms-state-plans",
        source_id=f"cms-{path.replace('/', '-')}",
        title=title,
        source_url=url,
        citation_path=f"us/policy/cms/{path}",
        source_format=fmt,
        expression_date=expression_date,
        extraction=PAGES if fmt == "pdf" else None,
        metadata={"document_subtype": subtype},
    )


MS = "https://www.medicaid.gov/sites/default/files/"
CMS_STATE_PLANS = [
    plan(
        "medicaid-spa/la/la-14-04",
        "Louisiana Medicaid State Plan Amendment 14-04 (approval package)",
        "https://www.medicaid.gov/State-resource-center/Medicaid-State-Plan-Amendments/Downloads/LA/LA-14-04.pdf",
        "pdf",
        subtype="medicaid_state_plan_amendment",
    ),
    plan(
        "medicaid-spa/ri/ri-22-0024",
        "Rhode Island Medicaid State Plan Amendment 22-0024 (approval package)",
        "https://www.medicaid.gov/medicaid/spa/downloads/RI-22-0024.pdf",
        "pdf",
        subtype="medicaid_state_plan_amendment",
    ),
    plan(
        "medicaid-spa/mt/mt-24-0002",
        "Montana Medicaid State Plan Amendment 24-0002 (approval package, May 3, 2024)",
        MS + "2024-05/MT-24-0002.pdf",
        "pdf",
        "2024-05-03",
        subtype="medicaid_state_plan_amendment",
    ),
    plan(
        "chip-spa/ca/ca-chipspa-20",
        "California CHIP State Plan Amendment 20 (approval package)",
        MS + "CHIP/Downloads/CA/CA-CHIPSPA-20.pdf",
        "pdf",
        subtype="chip_state_plan_amendment",
    ),
    plan(
        "medicaid-spa/ga/ga-18-0004",
        "Georgia Medicaid State Plan Amendment 18-0004 (approval package, December 3, 2018)",
        MS + "State-resource-center/Medicaid-State-Plan-Amendments/Downloads/GA/GA-18-0004.pdf",
        "pdf",
        "2018-12-03",
        subtype="medicaid_state_plan_amendment",
    ),
    plan(
        "medicaid-spa/ga/ga-19-0010",
        "Georgia Medicaid State Plan Amendment 19-0010 (approval package)",
        MS + "State-resource-center/Medicaid-State-Plan-Amendments/Downloads/GA/GA-19-0010.pdf",
        "pdf",
        subtype="medicaid_state_plan_amendment",
    ),
    plan(
        "section-1115/ar/arkansas-works",
        "Arkansas Works (Medicaid.gov section 1115 demonstration page)",
        "https://www.medicaid.gov/medicaid/section-1115-demo/demonstration-and-waiver-list/81021",
        "html",
        subtype="section_1115_demonstration_page",
    ),
    plan(
        "section-1115/ar/arkansas-works-annual-report-2018",
        "Arkansas Works Section 1115 Demonstration Waiver Annual Report, January 1, 2018 - December 31, 2018",
        "https://www.medicaid.gov/Medicaid-CHIP-Program-Information/By-Topics/Waivers/1115/downloads/ar/Health-Care-Independence-Program-Private-Option/ar-works-annl-rpt-jan-dec-2018.pdf",
        "pdf",
        "2018-12-31",
        subtype="section_1115_annual_report",
    ),
    plan(
        "section-1115/mi/healthy-michigan-waiver-amendment-request-2013-11-08",
        "Healthy Michigan Plan Section 1115 Waiver Amendment Request (November 8, 2013)",
        "https://www.medicaid.gov/Medicaid-CHIP-Program-Information/By-Topics/Waivers/1115/downloads/mi/Healthy-Michigan/mi-healthy-michigan-waiver-amend-req-11082013.pdf",
        "pdf",
        "2013-11-08",
        subtype="section_1115_amendment_request",
    ),
    plan(
        "section-1115/in/healthy-indiana-plan-approval-2023-03-21",
        "Healthy Indiana Plan (HIP) Section 1115 Demonstration Approval (CMS letter and special terms, March 21, 2023)",
        "https://www.medicaid.gov/medicaid/section-1115-demonstrations/downloads/in-healthy-indiana-plan-support-20-ca-20230321.pdf",
        "pdf",
        "2023-03-21",
        subtype="section_1115_approval",
    ),
]


def agency(
    path: str,
    title: str,
    url: str,
    fmt: str,
    expression_date: str | None = None,
    *,
    authority: str,
    subtype: str,
    extraction: dict | None = None,
    request: dict | None = None,
    bundle_rows: tuple[str, ...] = (),
    download_url: str | None = None,
    note: str | None = None,
) -> Doc:
    metadata: dict[str, Any] = {"document_subtype": subtype, "source_authority": authority}
    if note:
        metadata["source_note"] = note
    return Doc(
        family="agency-guidance",
        source_id=path.replace("/", "-"),
        title=title,
        source_url=url,
        download_url=download_url,
        citation_path=f"us/guidance/{path}",
        source_format=fmt,
        expression_date=expression_date,
        extraction=extraction if extraction is not None else (PAGES if fmt == "pdf" else None),
        request=request,
        bundle_rows=bundle_rows,
        metadata=metadata,
    )


DOL = "U.S. Department of Labor"
FNS = "USDA Food and Nutrition Service (Food and Nutrition Administration since 2026-06-01)"
AGENCY_GUIDANCE = [
    agency(
        "hhs/aspe/prior-poverty-guidelines-federal-register-references",
        "Prior HHS Poverty Guidelines and Federal Register References",
        "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines/prior-hhs-poverty-guidelines-federal-register-references",
        "html",
        authority="HHS Office of the Assistant Secretary for Planning and Evaluation",
        subtype="reference_table",
    ),
    agency(
        "dol/whd/overtime-salary-levels",
        "Earnings thresholds for the Executive, Administrative, and Professional exemption from minimum wage and overtime protections under the FLSA",
        "https://www.dol.gov/agencies/whd/overtime/salary-levels",
        "html",
        authority=DOL + " Wage and Hour Division",
        subtype="guidance_page",
        extraction=ARTICLE,
    ),
    agency(
        "dol/eta/futa-credit-reductions",
        "FUTA Credit Reductions (Employment & Training Administration)",
        "https://oui.doleta.gov/unemploy/futa_credit.asp",
        "html",
        authority=DOL + " Employment and Training Administration",
        subtype="guidance_page",
        extraction={"html_content_selector": "div#content"},
    ),
    agency(
        "dol/eta/futa-credit-reduction-states-2010-2025",
        "FUTA credit reduction states and rates, 2010-2025 (workbook)",
        "https://oui.doleta.gov/unemploy/docs/reduced_credit_states_2010-2025.xlsx",
        "xlsx",
        authority=DOL + " Employment and Training Administration",
        subtype="rate_table",
        extraction={},
    ),
    agency(
        "usda/fns/snap-elderly-disabled-special-rules",
        "SNAP Special Rules for the Elderly or Disabled",
        "https://www.fns.usda.gov/snap/eligibility/elderly-disabled-special-rules",
        "html",
        authority=FNS,
        subtype="program_page",
    ),
    agency(
        "usda/fns/snap-provisions-fiscal-responsibility-act-2023",
        "SNAP Provisions in the Fiscal Responsibility Act of 2023",
        "https://www.fns.usda.gov/snap/provisions-fiscal-responsibility-act-2023",
        "pdf",
        "2023-06-01",
        authority=FNS,
        subtype="policy_memorandum",
        request=IMPERSONATE,
        download_url="https://www.usda.gov/sites/default/files/guidance-documents/fns.snap-Provisions-in-FRA.pdf",
        note="the FNA page carries no text of its own; it embeds this PDF from the USDA guidance portal; the "
        "memorandum prints 'June __, 2023' (the day is not in the text layer), so expression_date is 2023-06-01",
    ),
    agency(
        "usda/fns/snap-time-limit-waivers-fy2025-2029",
        "Time Limit Waivers FY 2025-2029",
        "https://www.fns.usda.gov/snap/waivers/timelimit/2025-2029",
        "html",
        authority=FNS,
        subtype="program_page",
    ),
    agency(
        "usda/fns/snap-work-requirements",
        "SNAP Work Requirements",
        "https://www.fns.usda.gov/snap/work-requirements",
        "html",
        authority=FNS,
        subtype="program_page",
    ),
    agency(
        "usda/fns/snap-obbb-time-limit-waivers-reinstatement-memo",
        "SNAP - Waiver of the Time Limit: Reinstatement (memorandum, February 26, 2026)",
        "https://www.usda.gov/sites/default/files/guidance-documents/fna.obbb-time-limit-waivers-reinstatement.pdf",
        "pdf",
        "2026-02-26",
        authority=FNS,
        subtype="policy_memorandum",
        request=IMPERSONATE,
        bundle_rows=(
            "https://www.fns.usda.gov/snap/work-requirements/policies/waiver-reinstatement",
        ),
        note="the FNA page 'SNAP Waiver of the Time Limit - Status Update' (work-requirements/policies/"
        "waiver-reinstatement) carries no text of its own and embeds this PDF",
    ),
    agency(
        "usda/fns/snap-farm-bill-2018-section-4004-memo",
        "SNAP Provisions of the Agriculture Improvement Act of 2018 - Section 4004 - Information Memorandum (questions and answers, March 12, 2019)",
        "https://www.usda.gov/sites/default/files/guidance-documents/fns.snap-FarmBill2018Section4004.pdf",
        "pdf",
        "2019-03-12",
        authority=FNS,
        subtype="policy_memorandum",
        request=IMPERSONATE,
    ),
    agency(
        "fns/wic/food-packages",
        "WIC Food Packages",
        "https://www.fns.usda.gov/wic/food-packages",
        "html",
        authority=FNS,
        subtype="program_page",
    ),
]


def ssa(
    path: str,
    title: str,
    url: str,
    fmt: str,
    expression_date: str | None = None,
    *,
    subtype: str,
    extraction: dict | None = None,
) -> Doc:
    return Doc(
        family="ssa-guidance",
        source_id=f"ssa-{path.replace('/', '-')}",
        title=title,
        source_url=url,
        citation_path=f"us/guidance/ssa/{path}",
        source_format=fmt,
        expression_date=expression_date,
        extraction=extraction if extraction is not None else (PAGES if fmt == "pdf" else None),
        request=IMPERSONATE,
        metadata={"document_subtype": subtype},
    )


SSIR = "https://www.ssa.gov/oact/ssir/"
SSA_STATE = "https://www.ssa.gov/policy/docs/progdesc/ssi_st_asst/"
STATE_NAMES = {
    "ak": "Alaska",
    "co": "Colorado",
    "ct": "Connecticut",
    "dc": "District of Columbia",
    "de": "Delaware",
    "fl": "Florida",
    "hi": "Hawaii",
    "in": "Indiana",
    "la": "Louisiana",
    "ma": "Massachusetts",
    "me": "Maine",
    "mi": "Michigan",
    "mo": "Missouri",
    "ne": "Nebraska",
    "nm": "New Mexico",
}
SSA_GUIDANCE = [
    ssa(
        "oact/ssi-annual-report/2011/income-and-resource-exclusions",
        "SSI Annual Report 2011: Income and Resource Exclusions",
        SSIR + "SSI11/Exclusions.html",
        "html",
        subtype="ssi_annual_report_section",
    ),
    ssa(
        "oact/ssi-annual-report/2012/income-and-resource-exclusions",
        "SSI Annual Report 2012: Income and Resource Exclusions",
        "https://www.ssa.gov/OACT/ssir/SSI12/V_B_Exclusions.html",
        "html",
        subtype="ssi_annual_report_section",
    ),
    *[
        ssa(
            f"oact/ssi-annual-report/20{yy}/income-and-resource-exclusions",
            f"SSI Annual Report 20{yy}: Income and Resource Exclusions",
            SSIR + f"SSI{yy}/V_B_Exclusions.html",
            "html",
            subtype="ssi_annual_report_section",
        )
        for yy in ("13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23")
    ],
    ssa(
        "oact/ssi-annual-report/2024/incentives-for-work-and-rehabilitation",
        "SSI Annual Report 2024: Incentives for Work and Opportunities for Rehabilitation",
        "https://www.ssa.gov/OACT/ssir/SSI24/V_E_WorkIncentives.html",
        "html",
        subtype="ssi_annual_report_section",
    ),
    *[
        ssa(
            f"state-assistance-programs-for-ssi-recipients/{year}/{st}",
            f"State Assistance Programs for SSI Recipients, January {year} - {STATE_NAMES[st]}",
            SSA_STATE + f"{year}/{st}.{ext}",
            ext,
            f"{year}-01-01",
            subtype="state_assistance_programs_report",
        )
        for year, st, ext in (
            ("2002", "co", "html"),
            ("2002", "ma", "html"),
            ("2005", "ct", "html"),
            ("2005", "ma", "html"),
            ("2011", "ak", "pdf"),
            ("2011", "co", "html"),
            ("2011", "ct", "html"),
            ("2011", "dc", "pdf"),
            ("2011", "de", "html"),
            ("2011", "fl", "html"),
            ("2011", "hi", "pdf"),
            ("2011", "in", "html"),
            ("2011", "la", "html"),
            ("2011", "ma", "html"),
            ("2011", "me", "html"),
            ("2011", "mi", "html"),
            ("2011", "mo", "html"),
            ("2011", "ne", "pdf"),
            ("2011", "nm", "html"),
        )
    ],
    ssa(
        "pubs/en-05-11125",
        "Supplemental Security Income (SSI) in California (SSA Publication No. 05-11125, 2026)",
        "https://www.ssa.gov/pubs/EN-05-11125.pdf",
        "pdf",
        "2026-01-01",
        subtype="publication",
    ),
    ssa(
        "pubs/en-05-11162",
        "Supplemental Security Income (SSI) in the District of Columbia (SSA Publication No. 05-11162, 2026)",
        "https://www.ssa.gov/pubs/EN-05-11162.pdf",
        "pdf",
        "2026-01-01",
        subtype="publication",
    ),
    ssa(
        "request-withhold-taxes",
        "Request to withhold taxes (SSA; the retirement planner taxes page now redirects here)",
        "https://www.ssa.gov/benefits/retirement/planner/taxes.html",
        "html",
        subtype="beneficiary_page",
        extraction=ARTICLE,
    ),
]


def law(
    number: str,
    title: str,
    url: str,
    expression_date: str,
    *,
    stat: str,
    bill: str,
    bundle_rows: tuple[str, ...] = (),
) -> Doc:
    return Doc(
        family="public-laws",
        source_id=f"public-law-{number}",
        title=title,
        source_url=url,
        citation_path=f"us/statute/public-law/{number}",
        source_format="pdf",
        expression_date=expression_date,
        extraction=PAGES,
        bundle_rows=bundle_rows,
        metadata={
            "document_subtype": "public_law",
            "public_law": f"Pub. L. {number}",
            "statutes_at_large": stat,
            "bill": bill,
        },
    )


PUBLIC_LAWS = [
    law(
        "119-21",
        "Public Law 119-21 (An Act to provide for reconciliation pursuant to title II of H. Con. Res. 14), July 4, 2025",
        "https://www.govinfo.gov/content/pkg/PLAW-119publ21/pdf/PLAW-119publ21.pdf",
        "2025-07-04",
        stat="139 Stat. 72",
        bill="H.R. 1 (119th Congress)",
        bundle_rows=(
            "https://www.congress.gov/119/plaws/publ21/PLAW-119publ21.pdf",
            "https://www.congress.gov/bill/119th-congress/house-bill/1",
            "https://www.congress.gov/bill/119th-congress/house-bill/1/text",
        ),
    ),
    law(
        "113-186",
        "Public Law 113-186, Child Care and Development Block Grant Act of 2014, November 19, 2014",
        "https://www.congress.gov/113/statute/STATUTE-128/STATUTE-128-Pg1971.pdf",
        "2014-11-19",
        stat="128 Stat. 1971",
        bill="S. 1086 (113th Congress)",
        bundle_rows=("https://www.congress.gov/bill/113th-congress/senate-bill/1086/text",),
    ),
    law(
        "115-97",
        "Public Law 115-97 (An Act to provide for reconciliation pursuant to titles II and V of the concurrent resolution "
        "on the budget for fiscal year 2018; commonly the Tax Cuts and Jobs Act), December 22, 2017",
        "https://www.congress.gov/115/plaws/publ97/PLAW-115publ97.pdf",
        "2017-12-22",
        stat="131 Stat. 2054",
        bill="H.R. 1 (115th Congress)",
    ),
    law(
        "117-169",
        "Public Law 117-169 (Inflation Reduction Act of 2022), August 16, 2022",
        "https://www.govinfo.gov/content/pkg/PLAW-117publ169/pdf/PLAW-117publ169.pdf",
        "2022-08-16",
        stat="136 Stat. 1818",
        bill="H.R. 5376 (117th Congress)",
        bundle_rows=(
            "https://www.democrats.senate.gov/imo/media/doc/inflation_reduction_act_of_2022.pdf",
        ),
    ),
    law(
        "103-66",
        "Public Law 103-66 (Omnibus Budget Reconciliation Act of 1993), August 10, 1993",
        "https://www.govinfo.gov/content/pkg/STATUTE-107/pdf/STATUTE-107-Pg312.pdf",
        "1993-08-10",
        stat="107 Stat. 312",
        bill="H.R. 2264 (103rd Congress)",
        bundle_rows=("https://www.congress.gov/bill/103rd-congress/house-bill/2264",),
    ),
    law(
        "98-21",
        "Public Law 98-21 (Social Security Amendments of 1983), April 20, 1983",
        "https://www.govinfo.gov/content/pkg/STATUTE-97/pdf/STATUTE-97-Pg65.pdf",
        "1983-04-20",
        stat="97 Stat. 65",
        bill="H.R. 1900 (98th Congress)",
        bundle_rows=("https://www.congress.gov/bill/98th-congress/house-bill/1900",),
    ),
]

USC_EDITIONS = [
    Doc(
        family="usc-editions",
        source_id="usc-1994-42-606",
        title="42 U.S.C. 606 (1994 edition), Definitions (AFDC)",
        source_url="https://www.govinfo.gov/content/pkg/USCODE-1994-title42/html/USCODE-1994-title42-chap6-subchapIV_2-partA-sec606.htm",
        citation_path="us/statute/edition-1994/42/606",
        source_format="html",
        expression_date="1994-01-01",
        extraction={"html_content_selector": "body"},
        bundle_rows=(
            "https://uscode.house.gov/view.xhtml?req=granuleid:USC-1994-title42-section606&num=0&edition=1994",
        ),
        metadata={
            "document_subtype": "us_code_historical_edition",
            "edition": "United States Code, 1994 Edition",
            "publisher": "U.S. Government Publishing Office (govinfo)",
            "edition_note": "expression_date is the edition year; the page prints no currency date",
        },
    ),
    Doc(
        family="usc-editions",
        source_id="usc-1976-title-26-volume",
        title="United States Code, 1976 Edition, Title 26 - Internal Revenue Code (Library of Congress scan, uscode1976-007026001)",
        source_url="https://tile.loc.gov/storage-services/service/ll/uscode/uscode1976-00702/uscode1976-007026001/uscode1976-007026001.pdf",
        citation_path="us/statute/edition-1976/26/uscode1976-007026001",
        source_format="pdf",
        expression_date="1976-01-01",
        extraction=PAGES,
        metadata={
            "document_subtype": "us_code_historical_edition",
            "edition": "United States Code, 1976 Edition",
            "publisher": "Library of Congress (scanned GPO print edition)",
            "edition_note": "expression_date is the edition year (the scan prints no currency date in this volume); "
            "the OCR text layer is the Library of Congress's own",
        },
    ),
]


def fr(date: str, number: str, title: str, citation: str, bundle_url: str) -> Doc:
    return Doc(
        family="federal-register",
        source_id=f"fr-{number}",
        title=title,
        source_url=f"https://www.govinfo.gov/content/pkg/FR-{date}/pdf/{number}.pdf",
        citation_path=f"us/rulemaking/federal-register/{date}/{number}",
        source_format="pdf",
        expression_date=date,
        extraction=PAGES,
        bundle_rows=(bundle_url,),
        metadata={
            "document_subtype": "final_rule",
            "federal_register_citation": citation,
            "federal_register_document_number": number,
            "federalregister_gov_url": bundle_url,
            "access_note": "the federalregister.gov document page redirects the corpus client to "
            "unblock.federalregister.gov (a bot wall); the GPO govinfo edition of the "
            "same Federal Register document is taken",
        },
    )


FR = "https://www.federalregister.gov/documents/"
FEDERAL_REGISTER = [
    fr(
        "2019-09-27",
        "2019-20353",
        "Defining and Delimiting the Exemptions for Executive, Administrative, Professional, Outside Sales and Computer Employees (final rule)",
        "84 FR 51230",
        FR
        + "2019/09/27/2019-20353/defining-and-delimiting-the-exemptions-for-executive-administrative-professional-outside-sales-and",
    ),
    fr(
        "2024-03-27",
        "2024-06464",
        "Omitting Food From In-Kind Support and Maintenance Calculations (final rule)",
        "89 FR 21199",
        FR
        + "2024/03/27/2024-06464/omitting-food-from-in-kind-support-and-maintenance-calculations",
    ),
    fr(
        "2024-04-26",
        "2024-08038",
        "Defining and Delimiting the Exemptions for Executive, Administrative, Professional, Outside Sales, and Computer Employees (final rule)",
        "89 FR 32842",
        FR
        + "2024/04/26/2024-08038/defining-and-delimiting-the-exemptions-for-executive-administrative-professional-outside-sales-and",
    ),
]

ALL_DOCS: list[Doc] = [
    *IRS_FORMS,
    *IRS_GUIDANCE,
    *CMS_GUIDANCE,
    *CMS_STATE_PLANS,
    *AGENCY_GUIDANCE,
    *SSA_GUIDANCE,
    *PUBLIC_LAWS,
    *USC_EDITIONS,
    *FEDERAL_REGISTER,
]


def manifest_entry(doc: Doc, family: Family) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source_id": doc.source_id,
        "jurisdiction": "us",
        "document_class": family.document_class,
        "title": doc.title,
        "source_url": doc.source_url,
    }
    if doc.download_url:
        entry["download_url"] = doc.download_url
    entry["source_format"] = doc.source_format
    entry["source_as_of"] = SOURCE_AS_OF
    if doc.expression_date:
        entry["expression_date"] = doc.expression_date
    entry["citation_path"] = doc.citation_path
    if doc.extraction:
        entry["extraction"] = dict(doc.extraction)
    if doc.request:
        entry["request"] = dict(doc.request)
    metadata: dict[str, Any] = {"primary_source": True}
    metadata["source_authority"] = doc.metadata.get("source_authority", family.authority)
    metadata.update({k: v for k, v in doc.metadata.items() if k != "source_authority"})
    metadata["source_family"] = f"w6-federal-{family.key}"
    metadata["discovered_via"] = DISCOVERED_VIA
    metadata["run_note"] = RUN_NOTE
    if doc.bundle_rows:
        metadata["bundle_addresses"] = list(doc.bundle_rows)
    if doc.request and doc.request.get("browser_impersonation"):
        metadata["access_note"] = (
            "fetched with the chrome120 browser_impersonation request option, which a run note already "
            "documents for this publisher (www.ssa.gov: docs/ingest-runs/2026-07-05-ssa-cola-2026.md; "
            "www.usda.gov guidance portal: docs/ingest-runs/2026-09-13-federal-guidance-layer.md); "
            "TLS verified; no challenge solved"
        )
    entry["metadata"] = metadata
    return entry


def build(only: set[str] | None) -> None:
    seen_paths: set[str] = set()
    seen_urls: set[str] = set()
    for doc in ALL_DOCS:
        if doc.citation_path in seen_paths:
            raise SystemExit(f"duplicate citation path {doc.citation_path}")
        if doc.source_url in seen_urls:
            raise SystemExit(f"duplicate source url {doc.source_url}")
        seen_paths.add(doc.citation_path)
        seen_urls.add(doc.source_url)
    for family in FAMILIES.values():
        if only and family.key not in only:
            continue
        docs = [d for d in ALL_DOCS if d.family == family.key]
        payload = {
            "version": family.version,
            "documents": [manifest_entry(d, family) for d in docs],
        }
        path = REPO / "manifests" / family.manifest
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120))
        print(f"{path.relative_to(REPO)}: {len(docs)} documents, version {family.version}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated family keys")
    args = parser.parse_args()
    build(set(args.only.split(",")) if args.only else None)


if __name__ == "__main__":
    main()
