"""Build the wave-7 `state-benefits` group manifests (state SNAP, TANF, CCDF, Medicaid/CHIP, SSI and UI
documents named by the program bundles and missing from the served corpus on 2026-10-12) and the per-row
decisions file.

Work order: docs/coverage/program-bundle-gaps-2026-10-12/wave7/state-benefits.csv (79 rows; row numbers below
are 0-based positions in that file). Run note: docs/ingest-runs/2026-10-12-w7-state-benefits.md.

Every document below was fetched from its official publisher on 2026-10-12 (corpus user agent first, TLS
verified against certifi plus data/certs/) and read before it was listed: the printed title, date or edition
is recorded in the entry. No mirror, archive, proxy or CAPTCHA path is used; www.dhs.state.mn.us and the
Indiana IAR API are fetched with the curl_cffi chrome120 profile that earlier run notes document for them.

One manifest per (jurisdiction, document_class): manifests/<jur>-state-benefits-w7-<class>.yaml, version
2026-10-12-w7-state-benefits-<class>-<st>. Rows the corpus already holds, adapter rows (Pennsylvania Code)
and rows that stay open are in DECISIONS with their evidence.

    uv run python scripts/build_w7_state_benefits_manifests.py            # manifests + decisions CSV
    uv run python scripts/build_w7_state_benefits_manifests.py --decisions-only
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-10-12"
RUN_NOTE = "docs/ingest-runs/2026-10-12-w7-state-benefits.md"
WORK_ORDER = ROOT / "docs/coverage/program-bundle-gaps-2026-10-12/wave7/state-benefits.csv"
DECISIONS_CSV = ROOT / "docs/ingest-runs/2026-10-12-w7-state-benefits-decisions.csv"
DISCOVERED_VIA = (
    "axiom.org program-bundle gap list 2026-10-12 (wave 7, group state-benefits, row {rows})"
)
HELD = "ALREADY-HELD"


def version_for(jurisdiction: str, document_class: str) -> str:
    return f"2026-10-12-w7-state-benefits-{document_class}-{jurisdiction.removeprefix('us-')}"


def manifest_path_for(jurisdiction: str, document_class: str) -> Path:
    return ROOT / "manifests" / f"{jurisdiction}-state-benefits-w7-{document_class}.yaml"


DOCS: list[dict[str, Any]] = []
DECISIONS: dict[int, tuple[str, str, str, str, str]] = {}


def doc(
    rows: list[int],
    jurisdiction: str,
    document_class: str,
    citation_path: str,
    title: str,
    url: str,
    fmt: str,
    *,
    program: str,
    authority: str,
    subtype: str,
    expression_date: str = SOURCE_AS_OF,
    expression_note: str | None = None,
    download_url: str | None = None,
    extraction: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    row_paths: dict[int, str] | None = None,
    row_notes: dict[int, str] | None = None,
    **metadata: Any,
) -> None:
    DOCS.append(
        {
            "rows": rows,
            "row_paths": row_paths or {},
            "row_notes": row_notes or {},
            "jurisdiction": jurisdiction,
            "document_class": document_class,
            "citation_path": citation_path,
            "title": title,
            "source_url": url,
            "source_format": fmt,
            "download_url": download_url,
            "extraction": extraction,
            "request": request,
            "expression_date": expression_date,
            "metadata": {
                "primary_source": True,
                "source_authority": authority,
                "document_subtype": subtype,
                "program": program,
                "expression_date_note": expression_note
                or (
                    "fetch date; the publisher serves the current text"
                    if expression_date == SOURCE_AS_OF
                    else "the date the document prints"
                ),
                "discovered_via": DISCOVERED_VIA.format(rows=", ".join(map(str, rows))),
                **metadata,
            },
        }
    )


def decide(rows: int | list[int], status: str, scope: str, path: str, url: str, note: str) -> None:
    for r in [rows] if isinstance(rows, int) else rows:
        DECISIONS[r] = (status, scope, path, url, note)


CCDF_PLAN_EXTRACTION = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>\d{1,2}\.[1-9])\s+(?P<heading>[A-Z]\S.*)$",
    "heading_continuation_pattern": r"^(?P<heading>(?:English )?Proficiency, and Persons with Disabilities)$",
    "start_after_pattern": r"^Overview$",
    "drop_line_patterns": [r"^\d+ \| P a g e\s*$", r"^FFY 2025[–-]2027 CCDF State Plan\s*$"],
}
CCDF_PLAN_META = {
    "form": "ACF-118",
    "fiscal_years": "2025-2027",
    "plan_period": "2024-10-01 to 2027-09-30",
    "central_index_url": "https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027",
}
IL_DHS_PAGE = {"html_content_selector": "#Main2"}

# --------------------------------------------------------------------------------------------
# MEASURE-CHECK and held rows (step 1: the corpus already holds the text)

decide(
    1,
    HELD,
    "us-az/statute/2026-10-06-w6-benefits-snap-statute-us-az-title-46",
    "us-az/statute/title-46",
    "https://www.azleg.gov/arsDetail/?title=46",
    "the bundle names path us-az/statute/46; the served title-46 scope (in us-rulespec-2026-10-07-w6-bundle-gaps-union) "
    "roots the title at us-az/statute/title-46 (inventory source_url https://www.azleg.gov/arsDetail?title=46): "
    "path move us-az/statute/46 -> us-az/statute/title-46",
)
for r, path, when in (
    (3, "us-co/policy/co-fns-food-restriction-waiver-modification-2026-01-23", "January 23, 2026"),
    (4, "us-co/policy/co-fns-food-restriction-waiver-modification-2026-05-11", "May 11, 2026"),
    (5, "us-co/policy/co-fns-food-restriction-waiver-approval-2025", "approval"),
):
    decide(
        r,
        HELD,
        "us-co/policy/2026-07-21-co-snap-policy",
        path,
        "",
        f"held and served (us-co/policy/2026-07-21-co-snap-policy is in us-rulespec-2026-10-07-w6-bundle-gaps-union; "
        f"inventory source_url equals the bundle address; FNS waiver {when}). Counted missing because the bundle's "
        "full-tier entry comes from manifests/us-co-snap-primary-policy.yaml, whose entry has no citation_path (the "
        "extractor derives it from source_id), and scripts/build_program_bundle.py applies joins.yaml document_paths "
        "only to PolicyEngine and plan rows; the existing join needs to reach manifest-sourced entries",
    )
decide(
    2,
    HELD,
    "us-ca/guidance/2026-06-24-ca-cdss-calworks-acl",
    "us-ca/guidance/cdss/acl-2024-24-55",
    "https://cdss.ca.gov/Portals/9/Additional-Resources/Letters-and-Notices/ACLs/2024/24-55.pdf",
    "ACL 24-55 is held from the same CDSS file with a cache-busting query (?ver=2024-08-19-162608-673); same document",
)
decide(
    0,
    HELD,
    "us-ar/manual/2026-09-11-ar-snap-manual-supersede",
    "us-ar/manual/dhs/snap-policy-manual",
    "https://humanservices.arkansas.gov/wp-content/uploads/Complete_SNAP_Manual.pdf",
    "Complete_SNAP_Manual.pdf (1,057 pages, compiled 2020-02-28, transmittals from FSC 00-01) is a superseded "
    "compilation of the Arkansas SNAP (Food Stamp) Certification Manual; the current manual (SNAP-Policy-Manual-"
    "07.01.2026.pdf) is held and served",
)
decide(
    6,
    HELD,
    "us-co/policy/2026-09-10-ccdf-plan-fy2025-2027",
    "us-co/policy/acf/ccdf-plan/fy2025-2027",
    "https://spl.cde.state.co.us/artemis/huserials/hu62510internet/hu62510202527internet.pdf",
    "the State Publications Library copy is byte-identical (sha256 d03ffa1d...) to the held Colorado CCDF Plan FFY "
    "2025-2027",
)
CO_RULE_NOTE = (
    "{rule} ruleVersionId {rv} ({when}) is a superseded version; the current version is held and served at "
    "this path (source ruleVersionId {cur}); the wave-7 rejoin builder joined other ruleVersionIds of the same "
    "rule here"
)
decide(
    7,
    HELD,
    "us-co/regulation/2026-06-19-co-oap-9-ccr-2503-5-r2026-07-15-self-contained",
    "us-co/regulation/9-ccr-2503-5",
    "https://www.coloradosos.gov/CCR/GenerateRulePdf.do?ruleVersionId=10694",
    CO_RULE_NOTE.format(
        rule="9 CCR 2503-5 (Adult Financial Programs)",
        rv=10694,
        when="PDF of 2023-11-20",
        cur=12428,
    ),
)
decide(
    8,
    HELD,
    "us-co/regulation/2026-06-19-co-oap-9-ccr-2503-5-r2026-07-15-self-contained",
    "us-co/regulation/9-ccr-2503-5",
    "https://www.coloradosos.gov/CCR/GenerateRulePdf.do?ruleVersionId=5834",
    CO_RULE_NOTE.format(
        rule="9 CCR 2503-5 (Adult Financial Programs)", rv=5834, when="eff. 3/2/14", cur=12428
    ),
)
decide(
    9,
    HELD,
    "us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated",
    "us-co/regulation/9-ccr-2503-6",
    "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=10321",
    CO_RULE_NOTE.format(
        rule="9 CCR 2503-6 (Colorado Works)", rv=10321, when="rev. eff. 3/1/2022", cur=12030
    ),
)
decide(
    10,
    HELD,
    "us-co/manual/2026-09-10-medicaid-state-eligibility-manual",
    "us-co/manual/hcpf/medicaid/10-ccr-2505-10-8-100",
    "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=10779",
    "10 CCR 2505-10 8.100 ruleVersionId 10779 (PDF of 2023-04-28) is a superseded version; the current section 8.100 is "
    "held and served at this path (the rejoin builder joined ruleVersionId 10703 here)",
)
decide(
    11,
    HELD,
    "us-co/regulation/2026-07-16-10-ccr-2506-1",
    "us-co/regulation/10-ccr-2506-1",
    "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=11645&",
    CO_RULE_NOTE.format(rule="10 CCR 2506-1 (SNAP)", rv=11645, when="PDF of 2024-10-15", cur=12299),
)
for r, rule in ((15, "032"), (16, "033"), (17, "036")):
    decide(
        r,
        HELD,
        "us-fl/regulation/2026-09-10-ssi-state-supplement",
        f"us-fl/regulation/fac/65a-2/{rule}",
        f"https://www.flrules.org/gateway/RuleNo.asp?title=PUBLIC%20ASSISTANCE&ID=65A-2.{rule}",
        f"flrules.org is the Florida Department of State's official Florida Administrative Code site; Rule 65A-2.{rule} "
        "is held from the same RuleNo.asp page (title=OPTIONAL STATE SUPPLEMENTATION in the held address)",
    )
decide(
    18,
    HELD,
    "us-fl/regulation/2026-05-29-r2026-07-15-self-contained",
    "us-fl/regulation/fac/65a-1/703",
    "https://www.flrules.org/gateway/ruleno.asp?id=65A-1.703",
    "flrules.org is the official FAC site; Rule 65A-1.703 (Family-Related Medicaid Coverage Groups) is held and served "
    "from the chapter page (Division.asp?DivID=339)",
)
decide(
    19,
    HELD,
    "us-hi/regulation/2026-05-27-hi-snap-rules-r2026-07-15-self-contained-r2026-09-13-tanf-consolidated",
    "us-hi/regulation/har/17/676",
    "https://humanservices.hawaii.gov/wp-content/uploads/2014/01/17-676.pdf",
    "the 2014 upload of HAR chapter 17-676 (Income) is an older posting; the current chapter is held and served at this "
    "path (the wave-6 join of hawaii.gov/dhs/.../676.pdf points here too)",
)
decide(
    40,
    HELD,
    "us-la/policy/2026-09-10-ccdf-plan-fy2025-2027",
    "us-la/policy/acf/ccdf-plan/fy2025-2027",
    "https://doe.louisiana.gov/docs/default-source/early-childhood/approved-2025-2027-ccdf-state-plan.pdf",
    "the approved Louisiana CCDF Plan FFY 2025-2027 is held from the same file with a Sitefinity version query "
    "(?sfvrsn=3316f8f1_12)",
)
decide(
    66,
    HELD,
    "us-nv/policy/2026-09-10-ccdf-plan-fy2025-2027",
    "us-nv/policy/acf/ccdf-plan/fy2025-2027",
    "https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/care/ACF-118_CCDF_FFY_2025-2027_For_Nevada__3.pdf",
    "byte-identical (sha256 1dcb6f85...) to the held Nevada CCDF Plan FFY 2025-2027 (..._Final_Submission.pdf)",
)
decide(
    73,
    HELD,
    "us-ri/regulation/2026-07-21-ri-snap-rules",
    "us-ri/regulation/218-ricr/20/00/1",
    "https://risos-apa-production-public.s3.amazonaws.com/DHS/7907.pdf",
    "publisher check: the bucket is the Rhode Island Secretary of State's rules-filing store (official). The file is "
    "the October 2014 SNAP Rules and Regulations (sections 1000-1083), superseded by 218-RICR-20-00-1, which is held "
    "and served at this path",
)
decide(
    74,
    HELD,
    "us-sc/policy/2026-09-10-ccdf-plan-fy2025-2027",
    "us-sc/policy/acf/ccdf-plan/fy2025-2027",
    "https://www.scchildcare.org/media/cr5dc51w/submitted-version-of-the-ccdf-ffy-2025-2027-for-south-carolina-as-of-7-1-24pdf.pdf",
    "publisher check: scchildcare.org is the SC DSS Division of Early Care and Education (official, wave-6 precedent). "
    "The file is the plan as submitted on 2024-07-01; the approved plan that superseded it is held and served at this "
    "path",
)
decide(
    78,
    HELD,
    "us-wy/policy/2026-09-10-ccdf-plan-fy2025-2027",
    "us-wy/policy/acf/ccdf-plan/fy2025-2027",
    "https://drive.google.com/file/d/10TJ3S8d_nwyNxdkkbyk2gzCfHTk7CTcA/view",
    "publisher check: the Google Drive file is the Wyoming CCDF Plan FFY 2025-2027 that dfs.wyo.gov links (wave-6 "
    "precedent); held from the same file id (?usp=sharing)",
)
PA_183 = (
    "us-pa/regulation/2026-10-06-w6-tanf-ccdf-regulation-pa",
    "us-pa/regulation/title-55/chapter-183-pdf",
)
decide(
    68,
    HELD,
    *PA_183,
    "https://www.pacodeandbulletin.gov/secure/pacode/data/055/chapter183/055_0183.pdf",
    "55 Pa. Code chapter 183 (Standards for Need and Amount of Assistance) is held and served whole as the chapter PDF "
    "the Pennsylvania Code publishes (wave 6)",
)
for r, sec in ((71, "183.91"), (72, "183.94")):
    decide(
        r,
        HELD,
        *PA_183,
        "https://www.pacodeandbulletin.gov/secure/pacode/data/055/chapter183/055_0183.pdf",
        f"55 Pa. Code § {sec} is inside the held chapter 183 PDF (wave 6)",
    )

# --------------------------------------------------------------------------------------------
# us-co
doc(
    [12],
    "us-co",
    "regulation",
    "us-co/regulation/8-ccr-1403-1-eff-2026-08-14",
    "8 CCR 1403-1 Colorado Child Care Assistance Program Rules and Regulations (ruleVersionId 12658, eff. 08/14/2026)",
    "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=12658&fileName=8%20CCR%201403-1",
    "pdf",
    program="CCDF",
    authority="Colorado Secretary of State (Code of Colorado Regulations); Department of Early Childhood",
    subtype="agency_regulation_document",
    expression_date="2026-08-14",
    expression_note="last editor's note in the PDF: eff. 08/14/2026",
    row_notes={
        12: "the current CCCAP rulebook; the served scope carries ruleVersionId 11042 (eff. 08/14/2023) at "
        "us-co/regulation/8-ccr-1403-1/3.111, so this edition is taken at a dated sibling path (page-level)"
    },
    rule_version_id="12658",
)

# us-dc
doc(
    [13],
    "us-dc",
    "regulation",
    "us-dc/regulation/dcmr/29-7200",
    "DCMR 29-7200 Standards of Assistance and Payment Levels (Chapter 29-72)",
    "https://www.dcregs.dc.gov/Common/DCMR/RuleList.aspx?ChapterNum=29-72",
    "doc",
    download_url="https://dcregs.dc.gov/Common/DCMR/RuleList.aspx?DownloadFile={EE9AF311-8D08-4353-BBFB-D949DFF25242}",
    program="TANF",
    authority="DC Office of Documents and Administrative Issuances (DCMR)",
    subtype="municipal_regulation_section",
    expression_date="2026-05-22",
    expression_note="effective date of the latest version listed on the chapter page",
    chapter_url="https://www.dcregs.dc.gov/Common/DCMR/RuleList.aspx?ChapterNum=29-72",
)

# us-fl
doc(
    [14],
    "us-fl",
    "statute",
    "us-fl/statute/title-xxx/chapter-414/section-414-095",
    "Fla. Stat. 414.095 Determining eligibility for temporary cash assistance (2025 Florida Statutes)",
    "https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0400-0499/0414/Sections/0414.095.html",
    "html",
    program="TANF",
    authority="Florida Legislature (Online Sunshine)",
    subtype="codified_statute_section",
    extraction={"html_content_selector": "div.Section"},
    edition="2025 Florida Statutes",
)

# us-il
IL_DHS = "Illinois Department of Human Services"
doc(
    [20],
    "us-il",
    "policy",
    "us-il/policy/acf/ccdf-plan/fy2025-2027-amendment-2",
    "Illinois CCDF Plan FFY 2025-2027, Amendment 2 (approved 2026-07-01)",
    "https://idec.illinois.gov/content/dam/soi/en/web/idec/documents/policies/ACF-118%20CCDF%20FFY%202025-2027%20For%20Illinois%20Amend%202.pdf",
    "pdf",
    program="CCDF",
    authority="Illinois Department of Early Childhood (CCDF Lead Agency); HHS ACF Office of Child Care",
    subtype="state_plan_pdf",
    expression_date="2026-07-01",
    expression_note="plan status printed: Approved as of 2026-07-01",
    extraction=CCDF_PLAN_EXTRACTION,
    plan_version="Amendment 2",
    **CCDF_PLAN_META,
)
for r, item, title, date in (
    (21, "10160", "CCAP Policy Manual 01.02.03 - Exempt Income", "2024-02-26"),
    (22, "10163", "CCAP Policy Manual 01.02.02 - Non-Exempt Income", "2024-02-26"),
    (24, "10862", "CCAP Policy Manual 06.03.01 - 70% Attendance Rule", "2021-07-01"),
    (25, "10864", "CCAP Policy Manual 06.05.01 - Payment Rates", "2024-07-01"),
    (27, "118832", "CCAP Policy Manual 01.02.01 - Income Guidelines, 2022-07-01", "2022-07-01"),
    (31, "173323", "CCAP Policy Manual 06.05.01 Payment Rates Effective 7/1/2025", "2025-07-01"),
    (32, "178315", "CCAP Policy Manual 01.02.01 Income Guidelines, 2026-07-01", "2026-07-01"),
    (34, "46885", "CCAP Policy Manual 01.01.03 - Citizenship Status of the Child", "2017-04-01"),
    (36, "54862", "CCAP Policy Manual 04.02.01 - Copayments", "2025-04-01"),
):
    doc(
        [r],
        "us-il",
        "manual",
        f"us-il/manual/dhs/ccap/{item}",
        f"IDHS: {title}",
        f"https://www.dhs.state.il.us/page.aspx?item={item}",
        "html",
        program="CCDF",
        authority=IL_DHS,
        subtype="policy_manual_section",
        expression_date=date,
        expression_note="the latest effective or revision date the page prints",
        extraction=IL_DHS_PAGE,
        manual="Illinois Child Care Assistance Program (CCAP) Policy Manual",
        illinois_dhs_item_id=item,
    )
for r, item, title, date, prog in (
    (26, "112906", "MR #18.17: Increase in TANF Payment Levels", "2018-10-09", "TANF"),
    (28, "13251", "WAG 03-03-01: SSI and TANF", SOURCE_AS_OF, "TANF"),
    (29, "149890", "MR #23.30 TANF Payment Level Increase/IED Levels", "2023-10-20", "TANF"),
    (
        30,
        "161600",
        "MR #24.12 Health Benefits for Immigrant Adults (HBIA) and Health Benefits for Immigrant Seniors (HBIS)",
        "2024-04-18",
        "Medicaid",
    ),
):
    doc(
        [r],
        "us-il",
        "manual",
        f"us-il/manual/dhs/csmm/{item}",
        f"IDHS: {title}",
        f"https://www.dhs.state.il.us/page.aspx?item={item}",
        "html",
        program=prog,
        authority=IL_DHS,
        subtype="manual_release" if title.startswith("MR") else "policy_manual_topic",
        expression_date=date,
        expression_note=None if date == SOURCE_AS_OF else "the release date the page prints",
        extraction=IL_DHS_PAGE,
        manual="Illinois DHS Cash, SNAP, and Medical Manual",
        illinois_dhs_item_id=item,
    )
doc(
    [33],
    "us-il",
    "guidance",
    "us-il/guidance/dhs/tanf",
    "IDHS: Temporary Assistance for Needy Families (TANF)",
    "https://www.dhs.state.il.us/page.aspx?item=30358",
    "html",
    program="TANF",
    authority=IL_DHS,
    subtype="agency_web_page",
    extraction=IL_DHS_PAGE,
    illinois_dhs_item_id="30358",
)
doc(
    [35],
    "us-il",
    "guidance",
    "us-il/guidance/dhs/brochure-586-tanf",
    "IDHS: 586 - TANF Temporary Assistance For Needy Families (brochure)",
    "https://www.dhs.state.il.us/page.aspx?item=49833",
    "html",
    program="TANF",
    authority=IL_DHS,
    subtype="agency_brochure",
    extraction=IL_DHS_PAGE,
    illinois_dhs_item_id="49833",
)
doc(
    [23],
    "us-il",
    "guidance",
    "us-il/guidance/idec/child-care-assistance-program",
    "Illinois Department of Early Childhood: Get Help Paying for Child Care (Child Care Assistance Program)",
    "https://www.dhs.state.il.us/page.aspx?item=104995",
    "html",
    program="CCDF",
    authority="Illinois Department of Early Childhood",
    subtype="agency_web_page",
    extraction={"html_content_selector": "main"},
    illinois_dhs_item_id="104995",
    final_url="https://idec.illinois.gov/forparents/child-care-assistance-program.html",
    redirect_note="the IDHS item redirects to the Department of Early Childhood page (CCAP lead agency since 2026-07-01)",
)

# us-in (Indiana Register IAC through the General Assembly's API, the documented route)
doc(
    [37],
    "us-in",
    "regulation",
    "us-in/regulation/iac/455/1",
    "455 IAC Article 1: Aging (Indiana Administrative Code, 2026 edition)",
    "https://iar.iga.in.gov/code/2026/455/1",
    "json",
    download_url="https://drxya2s1hkmtl.cloudfront.net/api/adminCodeArticle?doc_stage=public&edition_year=2026&title_num=455&article_num=1",
    request={"browser_impersonation": True, "browser_impersonation_direct": True},
    extraction={
        "json_html_field": "iar_iac_article_doc.doc_html",
        "html_drop_selectors": ["ol.toc"],
        "html_text_selector": "h1, h2, h3, div.subsection, div.emphasize, p, li, table",
        "segmentation": "labeled_sections",
        "section_heading_pattern": r"^455 IAC 1-(?P<label>\d+-\d+(?:\.\d+)?)\s+(?P<heading>.+)$",
    },
    program="SSI state supplement (Residential Care Assistance Program)",
    authority="Indiana General Assembly (Indiana Register)",
    subtype="agency_regulation_document",
    row_paths={37: "us-in/regulation/iac/455/1/3-3"},
    row_notes={
        37: "Cornell LII mirror of 455 IAC 1-3-3 (per diem reimbursement rates); official text taken from the "
        "Indiana Register's 2026 IAC (Article 1 whole) through the General Assembly's API distribution, the "
        "route of docs/ingest-runs/2026-09-14-state-tax-regulations.md"
    },
    bundle_url="https://www.law.cornell.edu/regulations/indiana/455-IAC-1-3-3",
)

# us-ky
doc(
    [38],
    "us-ky",
    "statute",
    "us-ky/statute/krs/205.200",
    "KRS 205.200 (current version)",
    "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=57029",
    "pdf",
    program="TANF",
    authority="Kentucky Legislative Research Commission",
    subtype="codified_statute_section",
    extraction={"segmentation": "single_block"},
    expression_date="2026-04-14",
    expression_note="Effective: April 14, 2026 (printed)",
    bundle_url="https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=54926",
    row_notes={
        38: "the bundle's statute.aspx?id=54926 redirects to the LRC 'Invalid Statute' notice (a superseded "
        "version of KRS 205.200); the current version the notice links (statute.aspx?id=57029) is taken"
    },
)
doc(
    [39],
    "us-ky",
    "statute",
    "us-ky/statute/krs/205.245",
    "KRS 205.245 Supplementary payments",
    "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=7671",
    "pdf",
    program="SSI state supplement",
    authority="Kentucky Legislative Research Commission",
    subtype="codified_statute_section",
    extraction={"segmentation": "single_block"},
    expression_date="2005-06-20",
    expression_note="Effective: June 20, 2005 (printed)",
)

# us-md
doc(
    [41],
    "us-md",
    "policy",
    "us-md/policy/acf/ccdf-plan/fy2025-2027",
    "Maryland CCDF Plan FFY 2025-2027, Amendment 1 (approved 2025-06-24)",
    "https://earlychildhood.marylandpublicschools.org/system/files/filedepot/12/acf-118_ccdf_ffy_2025-2027_plan_approved_updated_6.25.25_amendment_request_1.pdf",
    "pdf",
    program="CCDF",
    authority="Maryland State Department of Education, Division of Early Childhood (CCDF Lead Agency)",
    subtype="state_plan_pdf",
    expression_date="2025-06-24",
    expression_note="plan status printed: Approved as of 2025-06-24",
    extraction=CCDF_PLAN_EXTRACTION,
    plan_version="Amendment 1",
    **CCDF_PLAN_META,
    row_notes={
        42: "the bundle's 11.9.2024 approval file answers 404 and the MSDE CCDF state-plan page links no "
        "2025-2027 file; MSDE now posts the plan approved and updated 6.25.25 (Amendment 1, row 41), which "
        "supersedes it"
    },
)

# us-mi
doc(
    [43],
    "us-mi",
    "statute",
    "us-mi/statute/400.10",
    "Michigan Compiled Laws 400.10, Administration of social security act and food stamp act",
    "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-400-10",
    "html",
    program="SSI state supplement",
    authority="Michigan Legislature",
    subtype="compiled_law_section",
    extraction={
        "html_content_selector": "body",
        "html_drop_selectors": ["nav", "header", "footer", "script", "style"],
    },
)

# us-mn (www.dhs.state.mn.us: Radware; chrome120 profile documented in the 2026-09-14 MSP and LIHEAP run notes;
# extracted with scripts/extract_w7_state_benefits_mn.py, which paces requests and refuses a challenge page)
MN_DHS = "Minnesota Department of Human Services"
MN_REQUEST = {"browser_impersonation": True, "browser_impersonation_direct": True}
MN_PAGE = {"html_content_selector": "#mainContent"}
MN_CM = "https://www.dhs.state.mn.us/main/idcplg?IdcService=GET_DYNAMIC_CONVERSION&RevisionSelectionMethod=LatestReleased&dDocName="
doc(
    [44],
    "us-mn",
    "manual",
    "us-mn/manual/dhs/mfip-employment-services-manual/3.9",
    "MFIP Employment Services Manual 3.9 Income and Asset Limits for MFIP",
    MN_CM + "ESM_000309",
    "html",
    program="TANF",
    authority=MN_DHS,
    subtype="policy_manual_section",
    request=MN_REQUEST,
    extraction=MN_PAGE,
    manual="MFIP Employment Services Manual",
    mn_ddocname="ESM_000309",
)
for r, ddoc, sec, title in (
    (45, "cm_001121", "0011.21", "Receipt of Other Assistance"),
    (46, "cm_00171203", "0017.12.03", "Unearned Income"),
    (47, "cm_001809", "0018.09", "Dependent Care Deduction"),
    (48, "cm_001818", "0018.18", "Earned Income Disregards"),
    (49, "cm_002009", "0020.09", "MFIP/DWP Assistance Standards"),
):
    doc(
        [r],
        "us-mn",
        "manual",
        f"us-mn/manual/dhs/combined-manual/{sec}",
        f"Combined Manual {sec} {title}",
        MN_CM + ddoc,
        "html",
        program="TANF",
        authority=MN_DHS,
        subtype="policy_manual_section",
        request=MN_REQUEST,
        extraction=MN_PAGE,
        manual="Minnesota DHS Combined Manual",
        mn_ddocname=ddoc,
        held_pdf_note="the served Combined Manual PDF (us-mn/manual/dhs/combined-manual/current) prints older issue "
        "dates for this section; the eManual page is the current text",
    )

# us-mo
doc(
    [60],
    "us-mo",
    "policy",
    "us-mo/policy/acf/ccdf-plan/fy2025-2027",
    "Missouri CCDF Plan FFY 2025-2027, Amendment 2 (approved 2026-03-26)",
    "https://dese.mo.gov/sites/g/files/zuston521/files/media/pdf/2026/04/ACF-118%20CCDF%20FFY%202025-2027%20For%20Missouri%20-%20Approved%203.26.2026.pdf",
    "pdf",
    program="CCDF",
    authority="Missouri Department of Elementary and Secondary Education (CCDF Lead Agency)",
    subtype="state_plan_pdf",
    expression_date="2026-03-26",
    expression_note="plan status printed: Approved as of 2026-03-26",
    extraction=CCDF_PLAN_EXTRACTION,
    plan_version="Amendment 2",
    **CCDF_PLAN_META,
)
for r, slug, url, title, date in (
    (
        61,
        "im-39-03",
        "https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/memos_03/im39_03.html",
        "IM-39 03/04/03 Court Ordered Child Support Expense Policy",
        "2003-03-04",
    ),
    (
        62,
        "im-34-13",
        "https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/memos_13/im34_13.html",
        "IM-#34 03/15/13 Disqualified or Ineligible Members Earned Income and Expense Budgeting for the Food Stamp Program",
        "2013-03-15",
    ),
):
    doc(
        [r],
        "us-mo",
        "manual",
        f"us-mo/manual/dss/snap/memos/{slug}",
        f"Missouri Department of Social Services: {title}",
        url,
        "html",
        program="SNAP",
        authority="Missouri Department of Social Services, Family Support Division",
        subtype="agency_memorandum",
        expression_date=date,
        expression_note="the memorandum date printed",
    )

# us-nc
doc(
    [63],
    "us-nc",
    "guidance",
    "us-nc/guidance/dss/economic-services/admin-letter-6-2005",
    "DSS Administrative Letter Economic Services No. 6-2005, Treatment of Legally Obligated Child Support Exclusion",
    "https://policies.ncdhhs.gov/wp-content/uploads/es_al-6-2005.pdf",
    "pdf",
    program="SNAP",
    authority="North Carolina Department of Health and Human Services, Division of Social Services",
    subtype="administrative_letter",
    expression_date="2005-06-29",
    expression_note="letter date printed (effective July 1, 2005)",
)

# us-nj
doc(
    [64],
    "us-nj",
    "statute",
    "us-nj/statute/session-laws/2013/chapter-45",
    "P.L. 2013, c.45 (S2366 2R), New Jersey SNAP Employment and Training Provider Demonstration Project",
    "https://pub.njleg.gov/bills/2012/PL13/45_.HTM",
    "html",
    program="SNAP",
    authority="New Jersey Legislature",
    subtype="session_law",
    expression_date="2013-04-15",
    expression_note="Approved April 15, 2013 (printed)",
)
doc(
    [65],
    "us-nj",
    "rulemaking",
    "us-nj/rulemaking/new-jersey-register/2016-05-02/prn-2016-017",
    "NJ SNAP proposed amendments, N.J.A.C. 10:87 (PRN 2016-017), New Jersey Register May 2, 2016",
    "https://www.nj.gov/humanservices/notices/documents/rule-proposals/(F)%20PRN%202016-017%20(DHS-DFD%2010_87-1.11).pdf",
    "pdf",
    program="SNAP",
    authority="New Jersey Department of Human Services, Division of Family Development",
    subtype="register_rule_proposal",
    expression_date="2016-05-02",
    expression_note="register date printed",
)

# us-wa
for r, wsr, filed in ((75, "09-15-085", "2009-07-14"), (76, "09-16-095", "2009-08-04")):
    doc(
        [r],
        "us-wa",
        "rulemaking",
        f"us-wa/rulemaking/wsr/{wsr}",
        f"Washington State Register WSR {wsr} (DSHS, permanent rules)",
        f"https://lawfilesext.leg.wa.gov/law/wsr/2009/{wsr[3:5]}/{wsr}.htm",
        "html",
        program="SNAP",
        authority="Washington State Register, Office of the Code Reviser",
        subtype="state_register_filing",
        expression_date=filed,
        expression_note="filing date printed",
    )

# us-wy
doc(
    [77],
    "us-wy",
    "guidance",
    "us-wy/guidance/dfs/child-care-assistance",
    "Wyoming Department of Family Services: Child Care Assistance",
    "https://dfs.wyo.gov/services/family-services/child-care/",
    "html",
    program="CCDF",
    authority="Wyoming Department of Family Services",
    subtype="agency_web_page",
    extraction={"html_content_selector": "main"},
)

# --------------------------------------------------------------------------------------------
# Pennsylvania Code adapter scopes (extract-pennsylvania-code, workers 1); see the run note.
PA_VERSION = "2026-10-12-w7-state-benefits-regulation-pa"
decide(
    67,
    "PRESENT",
    f"us-pa/regulation/{PA_VERSION}-title-55-chapter-178",
    "us-pa/regulation/title-55/chapter-178",
    "https://www.pacodeandbulletin.gov/secure/pacode/data/055/chapter178/chap178toc.html",
    "55 Pa. Code chapter 178 taken whole through the Pennsylvania Code adapter (pacodeandbulletin.gov)",
)
decide(
    69,
    "PRESENT",
    f"us-pa/regulation/{PA_VERSION}-title-34-chapter-65",
    "us-pa/regulation/title-34/chapter-65",
    "https://www.pacodeandbulletin.gov/secure/pacode/data/034/chapter65/chap65toc.html",
    "34 Pa. Code chapter 65 taken whole through the Pennsylvania Code adapter; the one-GET timeout of the triage did "
    "not recur",
)
decide(
    70,
    "PRESENT",
    f"us-pa/regulation/{PA_VERSION}-title-55-chapter-177",
    "us-pa/regulation/title-55/chapter-177/section-177-31",
    "https://www.pacodeandbulletin.gov/secure/pacode/data/055/chapter177/chap177toc.html",
    "55 Pa. Code § 177.31 taken within chapter 177 through the Pennsylvania Code adapter",
)


# --------------------------------------------------------------------------------------------
def manifest_entry(d: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source_id": d["citation_path"].replace("/", "-"),
        "jurisdiction": d["jurisdiction"],
        "document_class": d["document_class"],
        "title": d["title"],
        "source_url": d["source_url"],
        "source_format": d["source_format"],
        "source_as_of": SOURCE_AS_OF,
        "expression_date": d["expression_date"],
        "citation_path": d["citation_path"],
    }
    if d["download_url"]:
        entry["download_url"] = d["download_url"]
    if d["request"]:
        entry["request"] = d["request"]
    if d["extraction"]:
        entry["extraction"] = d["extraction"]
    entry["metadata"] = {
        **d["metadata"],
        "wave7_rows": d["rows"] + sorted(d["row_notes"].keys() - set(d["rows"])),
        "run_note": RUN_NOTE,
    }
    return entry


def build_manifests(only: set[str] | None = None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for d in DOCS:
        groups[(d["jurisdiction"], d["document_class"])].append(manifest_entry(d))
    for (jur, cls), entries in sorted(groups.items()):
        if only and jur not in only:
            continue
        path = manifest_path_for(jur, cls)
        header = (
            f"# Wave 7 (state-benefits): {jur} {cls} documents named by the program bundles.\n"
            "# Generated by scripts/build_w7_state_benefits_manifests.py; edit the generator, not this file.\n"
        )
        data = {"version": version_for(jur, cls), "documents": entries}
        path.write_text(
            header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120)
        )
    return groups


def write_decisions(statuses: dict[int, tuple[str, str]] | None = None) -> None:
    rows = list(csv.DictReader(WORK_ORDER.open()))
    by_row: dict[int, tuple[str, str, str, str, str]] = dict(DECISIONS)
    for d in DOCS:
        scope = f"{d['jurisdiction']}/{d['document_class']}/{version_for(d['jurisdiction'], d['document_class'])}"
        for r in d["rows"] + sorted(d["row_notes"].keys() - set(d["rows"])):
            path = d["row_paths"].get(r, d["citation_path"])
            by_row[r] = ("PRESENT", scope, path, d["source_url"], d["row_notes"].get(r, d["title"]))
    for r, (status, note) in (statuses or {}).items():
        by_row[r] = (status, "", "", by_row.get(r, ("", "", "", "", ""))[3], note)
    with DECISIONS_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
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
        )
        for i, row in enumerate(rows):
            status, scope, path, url, note = by_row.get(
                i, ("SKIPPED", "", "", "", "not reached in the time box")
            )
            w.writerow(
                [
                    row["id"],
                    row["jurisdiction"],
                    row["programs"],
                    row["action"],
                    status,
                    scope,
                    path,
                    url,
                    note,
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions-only", action="store_true")
    parser.add_argument(
        "--only", action="append", help="write manifests only for this jurisdiction"
    )
    args = parser.parse_args()
    if not args.decisions_only:
        groups = build_manifests(set(args.only) if args.only else None)
        for (jur, cls), entries in sorted(groups.items()):
            print(
                f"{manifest_path_for(jur, cls).relative_to(ROOT)}\t{version_for(jur, cls)}\t{len(entries)}"
            )
    write_decisions()


if __name__ == "__main__":
    main()
