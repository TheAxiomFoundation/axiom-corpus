"""Build the LIHEAP benefit-matrix closure manifests (needs-closure-2026-09-11 LIHEAP-ST-09 /
LIHEAP-ST-18) and record the scopes on the LIHEAP agent queue.

One manifest per (jurisdiction, document_class): the state's LIHEAP policy/operations manual
(``manual``), the adopted rule chapter where the state publishes its program as a rule
(``regulation``), and the benefit matrix tables published as plan attachments (``policy``).
Every document is the copy served by the official publisher: the state agency's own site, the
state's rules publisher, or the HHS/ACF LIHEAP Clearinghouse (liheapch.acf.gov, operated by
ACF/OCS), whose "State LIHEAP Policy Manuals" index (https://liheapch.acf.gov/stateplans.htm#MANUALS)
is the index every row is checked against. Facts per state (URLs, dates, matrix pages, access
notes) were verified by hand on 2026-09-13/14 and are the STATES table below; the run note is
docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md.

    uv run python scripts/build_liheap_benefit_matrix_manifests.py [--only us-al,us-ar] [--no-queue]

Wave 5 (2026-09-15, needs-closure-2026-09-14 LIHEAP-ST-18) adds the ``policy-manual`` family
(``--family policy-manual``, version ``2026-09-15-liheap-policy-manual``, ``MANUAL_STATES``): the state
policy manuals the 2026-09-14 run did not take. Only Arkansas qualifies: the Clearinghouse manuals
index links AR_Manual_2026.pdf (HTTP 404) while the publisher still serves its FFY 2025 predecessor
under its own naming, and the Arkansas Energy Office page posts matrices, charts and forms but no
manual. Every other LIHEAP-ST-18 state either has its manual or rule in the 2026-09-14 scopes or was
recorded absent/blocked there.

    uv run python scripts/build_liheap_benefit_matrix_manifests.py --family policy-manual [--only us-ar] [--no-queue]
"""
from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-09-14-liheap-benefit-matrix"
SOURCE_AS_OF = "2026-09-14"
RUN_NOTE = "docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md"
CLEARINGHOUSE_INDEX = "https://liheapch.acf.gov/stateplans.htm#MANUALS"
CLEARINGHOUSE_INDEX_COUNT = 39  # 38 states listed, Vermont as two rule links (read 2026-09-13)
CLEARINGHOUSE_AUTHORITY = (
    "HHS Administration for Children and Families, Office of Community Services (LIHEAP Clearinghouse)"
)
TLS_NOTE = (
    "liheapch.acf.gov omits its intermediate certificate; extraction uses REQUESTS_CA_BUNDLE = certifi + "
    "data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem"
)


@dataclass
class Doc:
    slug: str
    title: str
    url: str
    expression_date: str
    expression_note: str
    document_class: str = "manual"
    fmt: str = "pdf"
    subtype: str = "policy_manual_pdf"
    pages: int | None = None
    matrix_pages: str | None = None
    download_url: str | None = None
    request: dict[str, Any] | None = None
    extraction: dict[str, Any] | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Family:
    """One version of this generator's output: the 2026-09-14 benefit-matrix run (default) or the
    2026-09-15 policy-manual follow-up; the strings below are the ones written into every document."""

    name: str
    version: str
    source_as_of: str
    run_note: str
    manifest_infix: str  # "benefit-matrix" -> manifests/<jur>-liheap-benefit-matrix-<suffix>.yaml
    queue_key: str
    discovery_group_suffix: str
    discovered_via_prefix: str
    queue_sentence_date: str


BENEFIT_MATRIX = Family(
    name="benefit-matrix", version=VERSION, source_as_of=SOURCE_AS_OF, run_note=RUN_NOTE,
    manifest_infix="benefit-matrix", queue_key="benefit_matrix_scope", discovery_group_suffix="liheap-benefit-matrix",
    discovered_via_prefix="manual-review:liheap-agent-queue (needs-closure-2026-09-11 LIHEAP-ST-09)",
    queue_sentence_date="2026-09-14",
)
POLICY_MANUAL = Family(
    name="policy-manual", version="2026-09-15-liheap-policy-manual", source_as_of="2026-09-15",
    run_note="docs/ingest-runs/2026-09-15-ssi-liheap-medicare.md",
    manifest_infix="policy-manual", queue_key="policy_manual_scope", discovery_group_suffix="liheap-policy-manual",
    discovered_via_prefix="manual-review:liheap-agent-queue (needs-closure-2026-09-14 LIHEAP-ST-18)",
    queue_sentence_date="2026-09-15",
)
FAMILIES = {f.name: f for f in (BENEFIT_MATRIX, POLICY_MANUAL)}


@dataclass
class State:
    name: str
    publisher: str
    publisher_index_url: str
    docs: list[Doc]
    path_stem: str  # citation path stem after the class, e.g. "adeca/liheap-policy-manual"
    on_clearinghouse_index: bool
    matrix_status: str  # taken | in_manual | absent | blocked
    access_note: str
    queue_note: str
    hosting: str | None = None
    robohelp: tuple[str, str, str, str, str] | None = None  # (base url, shell file, path stem, expression date, expression note)


CLEARINGHOUSE_MATRIX_NOTE = (
    "FY 2026 benefit matrix as submitted with the state's FY 2026 plan, served by the ACF LIHEAP Clearinghouse under "
    "/docs/2026/benefits-matricies/ (the plan attachment the Clearinghouse plan PDF omits); the file is not linked from "
    "any Clearinghouse index page read on 2026-09-13 (stateplans.htm, the state profile pages, tables/benefits.htm, "
    "delivery/benefits.htm) and was located by the publisher's own file naming; 21 states have a 2026 file"
)


def ch_matrix(code: str, title: str, pages: int, expression_date: str, expression_note: str, **kw: Any) -> Doc:
    return Doc(
        slug="",
        title=title,
        url=f"https://liheapch.acf.gov/docs/2026/benefits-matricies/{code}_BenefitMatrix_2026.pdf",
        expression_date=expression_date,
        expression_note=expression_note,
        document_class="policy",
        subtype="plan_attachment_benefit_matrix_pdf",
        pages=pages,
        matrix_pages=kw.pop("matrix_pages", f"1-{pages}" if pages > 1 else "1"),
        extra_metadata={"hosting_authority": CLEARINGHOUSE_AUTHORITY, "clearinghouse_matrix_note": CLEARINGHOUSE_MATRIX_NOTE, **kw.pop("extra_metadata", {})},
        **kw,
    )


def robohelp_topics(base: str, shell: str) -> list[tuple[str, str]]:
    """Walk a RoboHelp 2022 manual's table of contents (whxdata/toc*.new.js) and return (relative url, label) topics."""
    headers = {"User-Agent": "axiom-corpus/0.1 (source discovery)"}
    topics: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index in ["", *[str(n) for n in range(1, 60)]]:
        response = None
        for _ in range(3):
            try:
                response = requests.get(f"{base}whxdata/toc{index}.new.js", headers=headers, timeout=30)
                break
            except requests.RequestException:
                time.sleep(2)
        if response is None:
            raise RuntimeError(f"RoboHelp TOC file unreachable: {base}whxdata/toc{index}.new.js")
        if response.status_code != 200:
            if index and int(index) > 40:
                break
            continue
        for block in re.finditer(r"\{[^{}]*\}", response.text):
            text = block.group(0)
            url = re.search(r'"url"\s*:\s*"([^"]+)"', text)
            name = re.search(r'"name"\s*:\s*"([^"]+)"', text)
            kind = re.search(r'"type"\s*:\s*"([^"]+)"', text)
            if not url or (kind and kind.group(1) == "book"):
                continue
            relative = url.group(1).split("#")[0]
            if relative and relative not in seen:
                seen.add(relative)
                topics.append((relative, (name.group(1) if name else "").replace("\\u200b", "").strip()))
    if len(topics) < 20:
        raise RuntimeError(f"RoboHelp walk of {base}{shell} found only {len(topics)} topics")
    return topics


def robohelp_docs(state: State) -> list[Doc]:
    assert state.robohelp is not None
    base, shell, _stem, expression_date, expression_note = state.robohelp
    docs = []
    for relative, label in robohelp_topics(base, shell):
        slug = re.sub(r"[^a-z0-9]+", "-", Path(relative).stem.lower()).strip("-")
        docs.append(Doc(
            slug=slug,
            title=f"{state.name} LIHEAP manual: {label or slug}",
            url=base + relative,
            expression_date=expression_date,
            expression_note=expression_note,
            fmt="html",
            subtype="policy_manual_topic_html",
            extra_metadata={"toc_label": label, "manual_landing_page": base + shell},
        ))
    return docs


def d(**kw: Any) -> Doc:
    return Doc(**kw)


STATES: dict[str, State] = {
    "us-al": State(
        name="Alabama",
        publisher="Alabama Department of Economic and Community Affairs (ADECA)",
        publisher_index_url="https://adeca.alabama.gov/liheap/",
        path_stem="adeca/liheap-policy-manual",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="adeca.alabama.gov HTTP 200 to the plain client (963,902 bytes)",
        queue_note="ADECA LIHEAP Policy Manual (99 pages, effective 2024-10-01 to 2025-02-16 as printed); the benefit matrix is printed on page 57.",
        docs=[d(slug="", title="Alabama LIHEAP Policy Manual (ADECA), effective October 1, 2024",
                url="https://adeca.alabama.gov/wp-content/uploads/LIHEAP-Manual.pdf",
                expression_date="2024-10-01", expression_note="printed 'Effective October 1, 2024 - February 16, 2025'; PDF dated 2025-02-18",
                pages=99, matrix_pages="57")],
    ),
    "us-ar": State(
        name="Arkansas",
        publisher="Arkansas Department of Energy and Environment, Arkansas Energy Office",
        publisher_index_url="https://adeq.state.ar.us/energy/assistance/liheap.aspx",
        path_stem="aeo/liheap-benefit-matrix/ffy2026",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="adeq.state.ar.us HTTP 200 to the plain client; the Clearinghouse link (/docs/2026/manuals/AR_Manual_2026.pdf) answers 404 (its FFY 2025 predecessor is served but not linked)",
        queue_note="FFY 2026 benefit matrices (electric, natural gas, propane, fuel oil, other/wood pellets; 2 pages each) and the FFY 2026 eligibility chart from the Arkansas Energy Office LIHEAP page; the plan (section 2.6) refers to these attachments.",
        docs=[
            d(slug="electric", title="Arkansas LIHEAP FFY 2026 Benefits Matrix: Electric", url="https://adeq.state.ar.us/energy/assistance/pdfs/LIHEAP_Benefit-Matix_2026_Electric.pdf",
              expression_date="2025-10-01", expression_note="FFY 2026 table (2025-10-01 to 2026-09-30)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=2, matrix_pages="1-2"),
            d(slug="natural-gas", title="Arkansas LIHEAP FFY 2026 Benefits Matrix: Natural Gas", url="https://adeq.state.ar.us/energy/assistance/pdfs/LIHEAP_Benefit-Matix_2026_Natural-Gas.pdf",
              expression_date="2025-10-01", expression_note="FFY 2026 table (2025-10-01 to 2026-09-30)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=2, matrix_pages="1-2"),
            d(slug="propane", title="Arkansas LIHEAP FFY 2026 Benefits Matrix: Propane", url="https://adeq.state.ar.us/energy/assistance/pdfs/LIHEAP_Benefit-Matix_2026_Propane.pdf",
              expression_date="2025-10-01", expression_note="FFY 2026 table (2025-10-01 to 2026-09-30)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=2, matrix_pages="1-2"),
            d(slug="fuel-oil", title="Arkansas LIHEAP FFY 2026 Benefits Matrix: Fuel Oil", url="https://adeq.state.ar.us/energy/assistance/pdfs/LIHEAP_Benefit-Matix_2026_Fuel-Oil.pdf",
              expression_date="2025-10-01", expression_note="FFY 2026 table (2025-10-01 to 2026-09-30)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=2, matrix_pages="1-2"),
            d(slug="other-wood-pellets", title="Arkansas LIHEAP FFY 2026 Benefits Matrix: Other and Wood Pellets", url="https://adeq.state.ar.us/energy/assistance/pdfs/LIHEAP_Benefit-Matix_2026_Other-Wood-Pellets.pdf",
              expression_date="2025-10-01", expression_note="FFY 2026 table (2025-10-01 to 2026-09-30)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=2, matrix_pages="1-2"),
            d(slug="eligibility-chart", title="Arkansas LIHEAP FFY 2026 Eligibility Chart", url="https://adeq.state.ar.us/energy/assistance/pdfs/LIHEAP_Eligibility-Chart_2026.pdf",
              expression_date="2025-10-01", expression_note="FFY 2026 chart (2025-10-01 to 2026-09-30)", document_class="policy", subtype="plan_attachment_eligibility_chart_pdf", pages=1),
        ],
    ),
    "us-az": State(
        name="Arizona",
        publisher="Arizona Department of Economic Security, Community Services Division",
        publisher_index_url="https://des.az.gov/services/basic-needs/utility-assistance",
        path_stem="des/liheap-policy",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="des.az.gov HTTP 403 (5,578-byte body) to the plain client and HTTP 200 to a chrome120 TLS fingerprint on 2026-09-13; fetched with browser_impersonation, TLS verification on",
        queue_note="DES CCSD LIHEAP Policy, Rev. 16A effective 07/01/2026 (41 pages); benefit table on page 39.",
        docs=[d(slug="", title="Arizona DES LIHEAP Policy (CCSD), Rev. 16A, effective July 1, 2026",
                url="https://des.az.gov/sites/default/files/dl/CCSD-LIHEAP-Policy.pdf",
                expression_date="2026-07-01", expression_note="printed 'Effective Date: 07/01/2026' (Rev. 16A)",
                pages=41, matrix_pages="39", request={"browser_impersonation": "chrome120"})],
    ),
    "us-co": State(
        name="Colorado",
        publisher="Colorado Department of Human Services (rule); Colorado Secretary of State, Code of Colorado Regulations (publisher)",
        publisher_index_url="https://www.sos.state.co.us/CCR/Welcome.do",
        path_stem="9-ccr-2503-7",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="sos.state.co.us HTTP 200 to the plain client (512,442 bytes)",
        queue_note="9 CCR 2503-7 Other Assistance Programs (Income Maintenance Volume 3), the rendition the Clearinghouse index links (ruleVersionId 7308, generated 2017-10-20); LEAP rules 3.750-3.759 (rev. eff. 12/1/14) with the benefit points table on page 33. The CCR site's current-version listing needs a browser session (DisplayRule.do answers a 5 KB shell to the plain client), so the linked rendition is taken as listed.",
        docs=[d(slug="", title="9 CCR 2503-7 Colorado Department of Human Services, Income Maintenance (Volume 3), Other Assistance Programs (LEAP rules 3.750)",
                url="https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=7308&fileName=9%20CCR%202503-7",
                expression_date="2017-10-20", expression_note="Secretary of State rendition date (PDF ModDate 2017-10-20); the LEAP sections print 'Rev. eff. 12/1/14' and 'Eff. 9/1/16'",
                document_class="regulation", subtype="administrative_code_rule_pdf", pages=38, matrix_pages="33")],
    ),
    "us-de": State(
        name="Delaware",
        publisher="Delaware Department of Health and Social Services, Division of State Service Centers",
        publisher_index_url="https://bidcondocs.delaware.gov/HSS/",
        path_stem="dhss/deap-policies-and-procedures-manual",
        on_clearinghouse_index=True,
        matrix_status="absent",
        access_note="bidcondocs.delaware.gov HTTP 200 to the plain client (2,514,551 bytes)",
        queue_note="DEAP Policies and Procedures Manual (102 pages, PDF dated 2015-04-22, posted with solicitation HSS-15-027); it says the benefit matrix is in the current Delaware State Plan (page 8) and prints no matrix.",
        docs=[d(slug="", title="Delaware Energy Assistance Program (LIHEAP) Policies and Procedures Manual",
                url="https://bidcondocs.delaware.gov/HSS/HSS_15027Liheap_MAN.pdf",
                expression_date="2015-04-22", expression_note="PDF ModDate 2015-04-22; the manual prints no effective date (posted as a solicitation attachment)",
                pages=102, subtype="policy_manual_pdf")],
        hosting="Delaware bid and contract documents server (bidcondocs.delaware.gov), a state.delaware.gov service",
    ),
    "us-fl": State(
        name="Florida",
        publisher="Florida Department of Commerce (formerly Department of Economic Opportunity), Division of Community Development",
        publisher_index_url=CLEARINGHOUSE_INDEX,
        path_stem="commerce/liheap-policy-manual",
        on_clearinghouse_index=True,
        matrix_status="absent",
        access_note="liheapch.acf.gov HTTP 200 with the Entrust intermediate in the CA bundle (2,098,739 bytes)",
        queue_note="LIHEAP Policy Manual (73 pages, last revised 2021-11-17, effective 2022-05-27), the Clearinghouse-hosted copy; no dollar matrix is printed (benefit amounts are set in the state plan).",
        docs=[d(slug="", title="Florida LIHEAP Policy Manual, effective May 27, 2022",
                url="https://liheapch.acf.gov/sites/default/files/webfiles/docs/2023/manuals/FL_PolicyManual_2023.pdf",
                expression_date="2022-05-27", expression_note="printed 'EFFECTIVE DATE: May 27, 2022' (last revised November 17, 2021)",
                pages=73)],
        hosting=CLEARINGHOUSE_AUTHORITY,
    ),
    "us-ga": State(
        name="Georgia",
        publisher="Georgia Department of Human Services, Division of Family and Children Services",
        publisher_index_url=CLEARINGHOUSE_INDEX,
        path_stem="dfcs/liheap-policy-manual",
        on_clearinghouse_index=True,
        matrix_status="absent",
        access_note="liheapch.acf.gov HTTP 200 with the Entrust intermediate in the CA bundle (1,243,400 bytes)",
        queue_note="DFCS LIHEAP Policy Manual revised January 2022 (89 pages), the Clearinghouse-hosted copy; no dollar matrix is printed.",
        docs=[d(slug="", title="Georgia DFCS Low Income Home Energy Assistance Program Policy Manual, revised January 2022",
                url="https://liheapch.acf.gov/sites/default/files/webfiles/docs/2023/manuals/GA_PolicyManual_2023.pdf",
                expression_date="2022-01-01", expression_note="printed 'REVISED JANUARY 2022'",
                pages=89)],
        hosting=CLEARINGHOUSE_AUTHORITY,
    ),
    "us-hi": State(
        name="Hawaii",
        publisher="Hawaii Department of Human Services, Benefit, Employment and Support Services Division",
        publisher_index_url="https://humanservices.hawaii.gov/bessd/liheap/",
        path_stem="dhs/liheap-policies-and-procedures",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="humanservices.hawaii.gov HTTP 200 to the plain client (311,631 bytes)",
        queue_note="DHS LIHEAP Policies and Procedures, FFY 2020 (22 pages, PDF dated 2019-07-15); the benefit is a points allocation (five point categories, pages 19-20), not a dollar matrix.",
        docs=[d(slug="", title="Hawaii DHS LIHEAP Policies and Procedures, FFY 2020",
                url="https://humanservices.hawaii.gov/wp-content/uploads/2019/07/Policies-and-Procedures-2020.pdf",
                expression_date="2019-10-01", expression_note="FFY 2020 manual (title '2020 Policies and Procedures'); PDF dated 2019-07-15",
                pages=22, matrix_pages="19-20"),
            ch_matrix("HI", "Hawaii LIHEAP FY 2026 plan attachment: 2026 categorical income tables", 3, "2025-10-01", "FY 2026 attachment (PDF dated 2025-12-18; income limits noted as pending the official FY 2026 charts)")],
    ),
    "us-ia": State(
        name="Iowa",
        publisher="Iowa Department of Health and Human Services, Community Action Agencies Unit",
        publisher_index_url="https://hhs.iowa.gov/programs/programs-and-services/liheap",
        path_stem="hhs/liheap-policy-and-procedures-manual",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="hhs.iowa.gov HTTP 200 to the plain client (1,612,960 bytes)",
        queue_note="FY24 LIHEAP Policy and Procedures Manual (114 pages, PDF dated 2023-09-11); benefit matrix on pages 22-23.",
        docs=[d(slug="", title="Iowa LIHEAP FY24 Policy and Procedures Manual",
                url="https://hhs.iowa.gov/media/2702/download?inline=",
                expression_date="2023-10-01", expression_note="FY 2024 manual (2023-10-01 to 2024-09-30); PDF dated 2023-09-11",
                pages=114, matrix_pages="22-23")],
    ),
    "us-in": State(
        name="Indiana",
        publisher="Indiana Housing and Community Development Authority",
        publisher_index_url="https://www.in.gov/ihcda/program-partners/energy-assistance-program-eap/",
        path_stem="ihcda/liheap-intake-and-operations-manual",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="in.gov HTTP 200 to the plain client (1,185,182 bytes)",
        queue_note="IHCDA LIHEAP Intake and Operations Program Manual PY2024 v1.0 (111 pages); benefit matrices on pages 60-71.",
        docs=[d(slug="", title="Indiana LIHEAP Intake and Operations Program Manual, Program Year 2024 (version 1.0)",
                url="https://www.in.gov/ihcda/files/Indiana-LIHEAP-Intake-and-Operations-Program-Manual-PY2024-version-1.0.pdf",
                expression_date="2023-10-01", expression_note="Program Year 2024 (2023-2024) manual; the PDF prints no day-level effective date",
                pages=111, matrix_pages="60-71")],
    ),
    "us-me": State(
        name="Maine",
        publisher="Maine State Housing Authority (MaineHousing)",
        publisher_index_url="https://www.mainehousing.org/policy-research/mainehousing-rules",
        path_stem="mainehousing-rules/chapter-24",
        on_clearinghouse_index=True,
        matrix_status="absent",
        access_note="mainehousing.org HTTP 200 to the plain client (390,680 bytes)",
        queue_note="MaineHousing Rule Chapter 24 Home Energy Assistance Program, effective 2026-06-29 (33 pages); the rule sets the benefit method and refers to the program-year HEAP Guide for the matrix.",
        docs=[d(slug="", title="MaineHousing Rules Chapter 24: Home Energy Assistance Program (HEAP), effective June 29, 2026",
                url="https://www.mainehousing.org/docs/default-source/msha-rules/ch24-home-energy-assistance-program-rule.pdf",
                expression_date="2026-06-29", expression_note="printed 'EFFECTIVE DATE: June 29, 2026'",
                document_class="regulation", subtype="agency_rule_chapter_pdf", pages=33)],
    ),
    "us-mi": State(
        name="Michigan",
        publisher="Michigan Public Service Commission",
        publisher_index_url="https://www.michigan.gov/mpsc/consumer/meap",
        path_stem="",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="michigan.gov HTTP 403 (503-byte body) to the plain client and HTTP 200 to a chrome120 TLS fingerprint on 2026-09-13; fetched with browser_impersonation, TLS verification on",
        queue_note="2024 MEAP Policy and Procedure Manual v1.0 (MPSC, effective 2023-10-01, 78 pages; benefit computation on page 44, no matrix) and MDHHS Emergency Relief Manual item ERM 301 Energy Services (ERB 2026-002 of 2026-04-01, 16 pages) whose page 13 prints the SER energy payment limits effective 2025-10-01; Michigan's LIHEAP heating benefit is the Treasury Home Heating Credit and the crisis benefits run through SER and MEAP.",
        docs=[d(slug="mpsc/meap-policy-manual", title="Michigan Energy Assistance Program (MEAP) Policy and Procedure Manual, FY 2024 (v1.0)",
                url="https://www.michigan.gov/mpsc/-/media/Project/Websites/mpsc/consumer/meap/2024/2024_MEAP_Policy_Manual.pdf",
                expression_date="2023-10-01", expression_note="printed 'Effective October 1, 2023 for Fiscal Year 2024'",
                pages=78, request={"browser_impersonation": "chrome120"}),
            d(slug="mdhhs/erm/301", title="Michigan MDHHS Emergency Relief Manual ERM 301: Energy Services (ERB 2026-002, April 1, 2026)",
                url="https://mdhhs-pres-prod.michigan.gov/olmweb/ex/ER/Public/ERM/301.pdf",
                expression_date="2026-04-01", expression_note="printed 'ERB 2026-002 4-1-2026'; payment limits effective October 1, 2025 on page 13",
                pages=16, matrix_pages="13", subtype="policy_manual_item_pdf",
                extra_metadata={"manual_landing_page": "https://mdhhs-pres-prod.michigan.gov/olmweb/ex/ER/Public/ERM/000.pdf", "program_note": "State Emergency Relief energy services, the LIHEAP-funded crisis component with the fiscal-year payment caps by energy type"})],
    ),
    "us-mn": State(
        name="Minnesota",
        publisher="Minnesota Department of Commerce, Energy Assistance Program",
        publisher_index_url="https://mn.gov/commerce/energy/consumer-assistance/energy-assistance/",
        path_stem="commerce/eap-policy-manual",
        on_clearinghouse_index=True,
        matrix_status="absent",
        access_note="mn.gov HTTP 200 to the plain client (2,619,550 bytes)",
        queue_note="FFY24 EAP Policy Manual (309 pages, PDF dated 2023-12-19); chapter 4 Primary Heat computes the benefit from the household's energy cost and income (no grid is printed; the Clearinghouse has no Minnesota matrix for 2025 or 2026).",
        docs=[d(slug="", title="Minnesota Energy Assistance Program (EAP) Policy Manual, FFY 2024",
                url="https://mn.gov/commerce-stat/pdfs/eap/providers/2024/FINAL-FFY24-EAP-Policy-Manual.pdf",
                expression_date="2023-10-01", expression_note="FFY 2024 manual (2023-10-01 to 2024-09-30); PDF dated 2023-12-19",
                pages=309)],
    ),
    "us-ms": State(
        name="Mississippi",
        publisher="Mississippi Department of Human Services (rule); Mississippi Secretary of State, Administrative Code (publisher)",
        publisher_index_url="https://www.sos.ms.gov/adminsearch/",
        path_stem="title-18/part-24",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="sos.ms.gov HTTP 200 to the plain client (1,062,896 bytes)",
        queue_note="Title 18 Part 24 LIHEAP Policy Manual, revised January 2026 (64 pages), from the Secretary of State's administrative code; benefit table on page 39.",
        docs=[d(slug="", title="Mississippi Administrative Code Title 18 Part 24: Low-Income Home Energy Assistance Program (LIHEAP) Policy Manual, revised January 2026",
                url="https://www.sos.ms.gov/adminsearch/ACCode/00000693c.pdf",
                expression_date="2026-01-01", expression_note="printed 'Revised January 2026'; PDF dated 2026-01-06",
                document_class="regulation", subtype="administrative_code_part_pdf", pages=64, matrix_pages="39")],
    ),
    "us-mt": State(
        name="Montana",
        publisher="Montana Department of Public Health and Human Services, Human and Community Services Division",
        publisher_index_url="https://dphhs.mt.gov/hcsd/energyassistance/",
        path_stem="dphhs/liheap-policy-manual",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="dphhs.mt.gov HTTP 200 to the plain client (1,409,971 bytes)",
        queue_note="2025-2026 LIHEAP Policy Manual (135 pages, PDF dated 2026-05-04); benefit matrices on pages 122-125.",
        docs=[d(slug="", title="Montana LIHEAP Policy Manual, 2025-2026",
                url="https://dphhs.mt.gov/assets/hcsd/liheap/LIHEAPmanual.pdf",
                expression_date="2025-10-01", expression_note="2025-2026 heating season manual; PDF dated 2026-05-04",
                pages=135, matrix_pages="122-125")],
    ),
    "us-nd": State(
        name="North Dakota",
        publisher="North Dakota Department of Health and Human Services",
        publisher_index_url="https://www.hhs.nd.gov/applying-help/low-income-home-energy-assistance-program-liheap",
        path_stem="hhs/liheap-service-chapter-415",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="nd.gov HTTP 200 to the plain client (1,499,137 bytes)",
        queue_note="LIHEAP Service Chapter 415, Manual Letter 3750 effective 2023-10-01 (369 pages); benefit tables on pages 137, 201 and 245.",
        docs=[d(slug="", title="North Dakota LIHEAP Service Chapter 415 (Manual Letter 3750, October 1, 2023)",
                url="https://www.nd.gov/dhs/policymanuals/415/MLs/ML%203750%2010.1.2023.%20Full.pdf",
                expression_date="2023-10-01", expression_note="Manual Letter 3750 dated 10.1.2023 in the file name; PDF dated 2023-09-26",
                pages=369, matrix_pages="137,201,245")],
    ),
    "us-ne": State(
        name="Nebraska",
        publisher="Nebraska Department of Health and Human Services",
        publisher_index_url="https://dhhs.ne.gov/Pages/Guidance-Documents.aspx",
        path_stem="dhhs/liheap-guidance-document",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        # class guidance: DHHS publishes it in its Guidance Documents register (the Clearinghouse lists it as the manual)
        access_note="dhhs.ne.gov HTTP 200 to the plain client (377,116 bytes)",
        queue_note="DHHS LIHEAP Guidance Document dated 07/18/2026 (6 pages) with the 2026 heating season payment table (pages 3-4, effective 10/1/25 through 9/30/26).",
        docs=[d(slug="", title="Nebraska DHHS Low Income Home Energy Assistance Program (LIHEAP) Guidance Document (July 18, 2026)",
                url="https://dhhs.ne.gov/Guidance%20Docs/Low%20Income%20Home%20Energy%20Assistance%20Program%20(LIHEAP)%20Guidance%20Document.pdf",
                expression_date="2026-07-18", expression_note="printed 07/18/2026; payment table 'Effective 10/1/25 through 9/30/26'",
                pages=6, matrix_pages="3-4", subtype="agency_guidance_document_pdf", document_class="guidance")],
    ),
    "us-nh": State(
        name="New Hampshire",
        publisher="New Hampshire Department of Energy",
        publisher_index_url="https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/fuel-assistance-program",
        path_stem="energy/fuel-assistance-program-procedures-manual",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="energy.nh.gov HTTP 403 (524-byte body) to the plain client and HTTP 200 to a chrome120 TLS fingerprint on 2026-09-13; fetched with browser_impersonation, TLS verification on",
        queue_note="Fuel Assistance Program Policy and Procedures Manual, Program Year 2027 (2026-2027; 103 pages, PDF dated 2026-08-10); benefit tables on pages 19 and 78.",
        docs=[d(slug="", title="New Hampshire Fuel Assistance Program Policy and Procedures Manual, Program Year 2026-2027",
                url="https://www.energy.nh.gov/sites/g/files/ehbemt551/files/inline-documents/sonh/fuel-assistance-program-procedures-manual.pdf",
                expression_date="2026-08-10", expression_note="PDF dated 2026-08-10; the manual is for Program Year 2027 (2026-10-01 to 2027-09-30) and prints no day-level effective date",
                pages=103, matrix_pages="19,78", request={"browser_impersonation": "chrome120"}),
            ch_matrix("NH", "New Hampshire Fuel Assistance PY26 plan attachment: Program Benefits tables", 2, "2025-10-01", "PY26 (2025-10-01 to 2026-09-30) benefit tables; PDF dated 2025-12-19")],
    ),
    "us-nj": State(
        name="New Jersey",
        publisher="New Jersey Department of Community Affairs, Division of Housing and Community Resources",
        publisher_index_url="https://www.nj.gov/dca/dhcr/offices/liheap.shtml",
        path_stem="dca/liheap/fy2026",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="nj.gov HTTP 200 to the plain client (419,963 bytes)",
        queue_note="FY2026 LIHEAP Handbook (25 pages, PDF dated 2025-08-07; it says the benefit level matrix is published by public notice in the New Jersey Register) and the FY 2026 Benefit Matrix (1 image-only page, OCR) from the same DCA docs directory.",
        docs=[d(slug="handbook", title="New Jersey DCA LIHEAP Handbook, FY 2026",
                url="https://www.nj.gov/dca/dhcr/offices/docs/FY2026%20LIHEAP%20Handbook%20.pdf",
                expression_date="2025-10-01", expression_note="FY 2026 handbook (2025-10-01 to 2026-09-30); PDF dated 2025-08-07",
                pages=25),
            d(slug="", title="New Jersey DCA FY 2026 LIHEAP Benefit Matrix (benefit grids for deliverables, electric, gas and renters)",
                url="https://www.nj.gov/dca/dhcr/offices/docs/FY2026%20Benefit%20Matrix.pdf",
                expression_date="2025-10-01", expression_note="FY 2026 grid (PDF dated 2025-08-07); the DCA pages now link the FY 2027 grid as a PNG image with the same values",
                document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=1, matrix_pages="1",
                extraction={"ocr": True, "ocr_dpi": 300},
                extra_metadata={"ocr_note": "image-only PDF (one 428x700 image); read with tesseract at 300 dpi", "clearinghouse_copy_url": "https://liheapch.acf.gov/docs/2026/benefits-matricies/NJ_BenefitMatrix_2026.pdf", "clearinghouse_copy_note": "byte-identical (md5 8db15e890cab0a0bfb2879ac439bda4f)", "index_note": "not linked from the DCA LIHEAP/USF pages on 2026-09-13, which link the FY2027 Benefit Matrix.png; the FY 2026 PDF is the publisher's own file in the same docs directory"})],
    ),
    "us-nv": State(
        name="Nevada",
        publisher="Nevada Division of Welfare and Supportive Services",
        publisher_index_url="https://dwss.nv.gov/Energy/Energy_Assistance/",
        path_stem="dwss/eap-manual",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="dwss.nv.gov HTTP 200 to the plain client, redirecting to dss.nv.gov (1,266,615 bytes)",
        queue_note="FY 2024 Energy Assistance Program Manual, MTL 01/24 of 2024-06-25 (116 pages); benefit tables on pages 63-64 and 111-113.",
        docs=[d(slug="", title="Nevada Energy Assistance Program (EAP) Manual, FY 2024 (MTL 01/24)",
                url="https://dwss.nv.gov/uploadedFiles/dwssnvgov/content/Energy/FY%202024%20EAP%20Manual.pdf",
                expression_date="2024-06-25", expression_note="printed 'MTL 01/24 June 25, 2024'",
                pages=116, matrix_pages="63-64,111-113",
                extra_metadata={"redirect_note": "dwss.nv.gov redirects to https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/energy/FY_2024_EAP_Manual.pdf"}),
            ch_matrix("NV", "Nevada Energy Assistance Program FY 2026 plan attachment: Appendix A income guidelines, energy burden and benefit cap", 2, "2025-10-01", "FY 2026 appendix (PDF dated 2025-12-10)")],
    ),
    "us-sd": State(
        name="South Dakota",
        publisher="South Dakota Department of Social Services, Office of Energy Assistance",
        publisher_index_url=CLEARINGHOUSE_INDEX,
        path_stem="dss/oea-policies-and-procedures-manual",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="liheapch.acf.gov HTTP 200 with the Entrust intermediate in the CA bundle (1,984,214 bytes)",
        queue_note="Office of Energy Assistance Policies and Procedures Manual 2018 (60 pages, PDF dated 2017-12-05), the Clearinghouse-hosted copy; benefit table on page 50.",
        docs=[d(slug="", title="South Dakota Office of Energy Assistance Policies and Procedures Manual (2018)",
                url="https://liheapch.acf.gov/sites/default/files/webfiles/docs/SD_Policy-and-Procedures-Manual2018.pdf",
                expression_date="2017-12-05", expression_note="PDF dated 2017-12-05 (file name '2018'); the manual prints no effective date",
                pages=60, matrix_pages="50"),
            ch_matrix("SD", "South Dakota LIHEAP FY 2026 plan attachment: benefit matrix by region, fuel and income tier", 1, "2025-10-01", "HY2026 table (PDF dated 2025-09-02)")],
        hosting=CLEARINGHOUSE_AUTHORITY,
    ),
    "us-ut": State(
        name="Utah",
        publisher="Utah Department of Workforce Services, Housing and Community Development Division",
        publisher_index_url="https://jobs.utah.gov/housing/scso/seal/heat.html",
        path_stem="dws/heat-policy-manual",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="jobs.utah.gov HTTP 200 to the plain client (1,027,302 bytes)",
        queue_note="HEAT Program Policy Manual revised 2023-03-01 (53 pages); benefit table on page 37.",
        docs=[d(slug="", title="Utah HEAT Program Policy Manual, revised March 1, 2023",
                url="https://jobs.utah.gov/housing/scso/seal/documents/heatpolicymanual.pdf",
                expression_date="2023-03-01", expression_note="printed 'Revised March 1, 2023'",
                pages=53, matrix_pages="37")],
    ),
    "us-ak": State(
        name="Alaska",
        publisher="Alaska Department of Health, Division of Public Assistance",
        publisher_index_url="http://dpaweb.hss.state.ak.us/manuals/HAP/hap.htm",
        path_stem="dpa/hap",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="dpaweb.hss.state.ak.us HTTP 200 to the plain client (RoboHelp shell 33,470 bytes; topic pages about 1 s each); liheapch.acf.gov HTTP 200 with the Entrust intermediate in the CA bundle",
        queue_note="Heating Assistance Program Policy Manual, a RoboHelp 2022 manual (66 topic pages walked from whxdata/toc*.new.js; latest transmittal 2026-02 of 2026-09-01); 3004-5 Grant Computation and Addendum A (FFY 2027 community fuel points) carry the benefit computation; plus the FY 2026 Heating Assistance Benefit Computation attachment (6 pages) from the Clearinghouse.",
        robohelp=("http://dpaweb.hss.state.ak.us/manuals/HAP/", "hap.htm", "dpa/hap", "2026-09-01", "date of the manual's latest transmittal (2026-02, September 1, 2026); topic pages print no dates of their own"),
        docs=[ch_matrix("AK", "Alaska LIHEAP FY 2026 plan attachment: Heating Assistance Benefit Computation", 6, "2025-10-01", "FY 2026 attachment (PDF dated 2025-12-17)")],
    ),
    "us-ca": State(
        name="California",
        publisher="California Department of Community Services and Development",
        publisher_index_url="https://www.csd.ca.gov/Pages/LIHEAPProgram.aspx",
        path_stem="csd/liheap-benefit-matrix",
        on_clearinghouse_index=False,
        matrix_status="taken",
        access_note="liheapch.acf.gov HTTP 200 with the Entrust intermediate in the CA bundle; csd.ca.gov HTTP 200 to the plain client",
        queue_note="2026 LIHEAP County Base Benefit Amounts (BBA) and HEAP/Fast Track/WPO payment tables (7 pages) from the Clearinghouse; the same tables are pages 182-188 of CSD's own 2026 LIHEAP State Plan PDF (https://www.csd.ca.gov/Shared%20Documents/2026-Final-LIHEAP-State-Plan.pdf, 442 pages, HTTP 200), which the CSD program page lists.",
        docs=[ch_matrix("CA", "California LIHEAP 2026 plan attachment: County Base Benefit Amounts and payment tables", 7, "2026-01-01", "Program Year 2026 tables (PDF dated 2025-12-16); CSD's plan PDF is dated 2025-09-24",
                        extra_metadata={"agency_copy_url": "https://www.csd.ca.gov/Shared%20Documents/2026-Final-LIHEAP-State-Plan.pdf", "agency_copy_note": "pages 182-188 of the 442-page CSD plan PDF print the same tables"})],
    ),
    "us-ct": State(
        name="Connecticut",
        publisher="Connecticut Department of Social Services",
        publisher_index_url="https://portal.ct.gov/dss/knowledge-base/articles/state-plans-and-federal-reports/community-services-allocation-plans",
        path_stem="dss/liheap-allocation-plan/ffy2026",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="portal.ct.gov HTTP 200 to the plain client (400,574 bytes); the Clearinghouse-listed FFY 2025 plan URL answers 404 (portal 404 page)",
        queue_note="FFY 2026 LIHEAP Block Grant Allocation Plan as approved 2025-08-07 (19 pages; basic benefit levels on pages 10-11), the DSS document the Clearinghouse lists as the state's manual (its FFY 2025 link is dead; the FFY 2026 plan is on the DSS allocation-plans page).",
        docs=[d(slug="", title="Connecticut LIHEAP Block Grant Allocation Plan, FFY 2026 (as approved August 7, 2025)",
                url="https://portal.ct.gov/dss/-/media/departments-and-agencies/dss/state-plans-and-federal-reports/liheap-allocation-plans/ffy-2026-liheap-allocation-plan-approved.pdf",
                expression_date="2025-10-01", expression_note="plan period October 1, 2025 to September 30, 2026; approved August 7, 2025",
                document_class="policy", subtype="state_allocation_plan_pdf", pages=19, matrix_pages="10-11")],
    ),
    "us-dc": State(
        name="District of Columbia",
        publisher="District of Columbia Department of Energy and Environment",
        publisher_index_url="https://doee.dc.gov/liheap",
        path_stem="doee/liheap-benefit-matrix/fy2026",
        on_clearinghouse_index=False,
        matrix_status="taken",
        access_note="doee.dc.gov HTTP 200 to the plain client (27,999 bytes, Word document)",
        queue_note="FY26 LIHEAP Benefit Matrix (DOEE's Regular Benefits Table for FY 2026, a Word document; heating only) linked from the DOEE LIHEAP page.",
        docs=[d(slug="", title="District of Columbia DOEE FY 2026 LIHEAP Benefit Matrix (Regular Benefits Table)",
                url="https://doee.dc.gov/sites/default/files/dc/sites/doee/service_content/attachments/DC%20DOEE%20-%20FY26%20LIHEAP%20Benefit%20Matrix.docx",
                expression_date="2025-10-01", expression_note="FY 2026 table; the document's core properties are dated 2025-08-08",
                document_class="policy", fmt="docx", subtype="plan_attachment_benefit_matrix_docx", matrix_pages="whole document")],
    ),
    "us-id": State(
        name="Idaho",
        publisher="Idaho Department of Health and Welfare",
        publisher_index_url="https://healthandwelfare.idaho.gov/services-programs/food-cash-assistance/heating-assistance",
        path_stem="", on_clearinghouse_index=False, matrix_status="absent",
        access_note="healthandwelfare.idaho.gov HTTP 200 to the plain client; liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="Absent: the IDHW heating-assistance pages list benefit factors only and link no manual or matrix; the FY 2026 plan states min $122 / max $1,285 with no attachment; the Clearinghouse serves only a 2025 benefit determination chart (ID_BenefitMatrix_2025.pdf) and answers 404 for 2026.",
        docs=[],
    ),
    "us-il": State(
        name="Illinois",
        publisher="Illinois Department of Commerce and Economic Opportunity",
        publisher_index_url="https://dceo.illinois.gov/communityservices/utilitybillassistance.html",
        path_stem="", on_clearinghouse_index=False, matrix_status="absent",
        access_note="dceo.illinois.gov HTTP 200 to the plain client; liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="Absent: DCEO's FY26 accepted plan (dceo.illinois.gov, 54 pages) refers to 'Illinois' LIHEAP Benefit Matrix' but does not attach it (min $58 / max $2,564); the utility-bill-assistance pages link brochures only; the Clearinghouse serves a 2025 matrix (IL_BenefitMatrix_2025.pdf) and answers 404 for 2026.",
        docs=[],
    ),
    "us-ks": State(
        name="Kansas",
        publisher="Kansas Department for Children and Families",
        publisher_index_url="https://content.dcf.ks.gov/EES/KEESM/Keesm.htm",
        path_stem="dcf/lieap-benefit-matrix",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="liheapch.acf.gov HTTP 200 with the Entrust intermediate in the CA bundle",
        queue_note="FY 2026 LIEAP Benefits Matrix attachment (4 pages, benefit adjustment at 80 percent, by fuel, household size and dwelling type) from the Clearinghouse; KEESM 13000 (the manual the Clearinghouse lists) is already in the selected KEESM scope.",
        docs=[ch_matrix("KS", "Kansas LIEAP FY 2026 plan attachment: LIEAP Benefits Matrix", 4, "2025-10-01", "FY 2026 attachment (PDF dated 2025-09-09)")],
    ),
    "us-ky": State(
        name="Kentucky",
        publisher="Kentucky Cabinet for Health and Family Services, Department for Community Based Services",
        publisher_index_url="https://www.chfs.ky.gov/agencies/dcbs/dfs/pdb/Pages/liheap.aspx",
        path_stem="", on_clearinghouse_index=True, matrix_status="absent",
        access_note="chfs.ky.gov HTTP 200 to the plain client; kyhousing.org HTTP 200",
        queue_note="Absent: the Clearinghouse-listed document (kyhousing.org '2022 Kentucky Health and Safety Plan') is the Weatherization Assistance Program health-and-safety plan, not a LIHEAP manual; the CHFS LIHEAP page posts narrative only (the only PDF is the LIHWAP plan) and the Clearinghouse has no Kentucky matrix for 2025 or 2026.",
        docs=[],
    ),
    "us-la": State(
        name="Louisiana",
        publisher="Louisiana Housing Corporation",
        publisher_index_url="https://www.lhc.la.gov/energy-assistance",
        path_stem="lhc/liheap",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="lhc.la.gov HTTP 200 to the plain client",
        queue_note="LIHEAP Service Delivery Guide effective 2026-04-01 (108 pages; the current edition of the 2022 guide the Clearinghouse lists) and LHC's own FFY 2026 Model Plan (62 pages) whose page 60 is the 'FFY2026 Heating and Cooling - Benefit Matrix' attachment.",
        docs=[
            d(slug="service-delivery-guide", title="Louisiana LIHEAP Service Delivery Guide, effective April 1, 2026",
              url="https://www.lhc.la.gov/hubfs/Document%20Libraries/Energy%20Assistance/Louisiana%20LIHEAP%20Service%20Delivery%20Guide%20-%20FINAL%20-%20Effective%20April%201%2c%202026.pdf",
              expression_date="2026-04-01", expression_note="printed 'Effective: April 1, 2026'", pages=108),
            d(slug="model-plan-ffy2026", title="Louisiana LIHEAP FFY 2026 Model Plan with the Heating and Cooling Benefit Matrix attachment",
              url="https://www.lhc.la.gov/hubfs/Document%20Libraries/Energy%20Assistance/FFY%202026%20LIHEAP%20Model%20Plan.pdf",
              expression_date="2025-10-01", expression_note="report period 10/01/2025 to 09/30/2026", document_class="policy", subtype="state_plan_with_attachments_pdf", pages=62, matrix_pages="60"),
        ],
    ),
    "us-ma": State(
        name="Massachusetts",
        publisher="Massachusetts Executive Office of Housing and Livable Communities",
        publisher_index_url="https://www.mass.gov/how-to/apply-for-home-energy-assistance-heap",
        path_stem="eohlc/heap-benefit-levels",
        on_clearinghouse_index=False,
        matrix_status="taken",
        access_note="mass.gov HTTP 403 to plain and Chrome-UA clients and HTTP 200 to a chrome120 TLS fingerprint for pages, but the linked FY 2027 chart download (/doc/fy-2027-liheap-income-eligibility-and-benefit-chart-july-2026/download) and the FY 2026 March 2026 chart answer 404 to the chrome120 fetch on 2026-09-14; liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="FY 2026 HEAP Income Eligibility and Benefit Levels chart (3 pages) from the Clearinghouse; the EOHLC HEAP page links its own chart but the download answers 404 (blocked as evidence shows).",
        docs=[ch_matrix("MA", "Massachusetts HEAP FY 2026 plan attachment: Income Eligibility and Benefit Levels", 3, "2025-10-01", "Fiscal Year 2026 chart (PDF dated 2025-12-16)")],
    ),
    "us-md": State(
        name="Maryland",
        publisher="Maryland Department of Human Services, Office of Home Energy Programs",
        publisher_index_url="https://dhs.maryland.gov/office-of-home-energy-programs/",
        path_stem="dhs/ohep",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="dhs.maryland.gov HTTP 200 to the plain client; the Clearinghouse-listed 2021 manual URL answers 404",
        queue_note="OHEP Operations Manual updated May 2025 (163 pages; benefit levels narrative 1.6 and 6.1, matrices not printed) and the FY27 MEAP Benefit Matrices (2 pages, text) and FY27 EUSP Benefit Matrix (3 pages, image-only, OCR) from the OHEP documents directory; program year FY27 runs 2026-07-01 to 2027-06-30.",
        docs=[
            d(slug="operations-manual", title="Maryland OHEP Operations Manual (updated May 2025)",
              url="https://dhs.maryland.gov/documents/OHEP/OHEP-Operations-Manual.pdf",
              expression_date="2025-05-01", expression_note="cover 'Updated May 2025'", pages=163),
            d(slug="fy27-meap-benefit-matrices", title="Maryland OHEP FY27 MEAP Benefit Matrices",
              url="https://dhs.maryland.gov/documents/OHEP/FY27-MEAP-Benefit-Matrices.pdf",
              expression_date="2026-07-01", expression_note="FY27 (2026-07-01 to 2027-06-30) tables; PDF dated 2026-06-23", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=2, matrix_pages="1-2"),
            d(slug="fy27-eusp-benefit-matrix", title="Maryland OHEP FY27 EUSP Benefit Matrix",
              url="https://dhs.maryland.gov/documents/OHEP/FY27-EUSP-Benefit-Matrix-1.pdf",
              expression_date="2026-07-01", expression_note="FY27 (2026-07-01 to 2027-06-30) tables; PDF dated 2026-06-23", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=3, matrix_pages="1-3",
              extraction={"ocr": True, "ocr_dpi": 300}, extra_metadata={"ocr_note": "image-only PDF (3 characters of text layer); read with tesseract at 300 dpi"}),
        ],
    ),
    "us-mo": State(
        name="Missouri",
        publisher="Missouri Department of Social Services, Family Support Division",
        publisher_index_url="https://dss.mo.gov/fsd/energy-assistance/liheap-contractor-supplier-information",
        path_stem="dss/liheap-policy-procedure-manual",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="dss.mo.gov HTTP 200 to the plain client (the Clearinghouse link mydss.mo.gov/media/pdf/liheap-manual redirects to an HTML media page embedding the 2024 edition; the 2025 edition is linked from the contractor information page)",
        queue_note="LIHEAP Policy and Procedure Manual, 2025 edition (129 pages, PDF dated 2025-09-30); Appendix K on page 129 prints the FFY 24 income ranges and benefit amounts by fuel type.",
        docs=[d(slug="", title="Missouri LIHEAP Policy and Procedure Manual (2025 edition)",
                url="https://dss.mo.gov/media/pdf/liheap-policy-procedure-manual",
                download_url="https://dss.mo.gov/sites/mydss/files/media/pdf/2025/10/liheap-policy-procedure-manual.pdf",
                expression_date="2025-10-01", expression_note="FFY 2026 edition posted 2025-10 (PDF dated 2025-09-30); the manual prints no effective date; Appendix K is labelled FFY 24",
                pages=129, matrix_pages="129")],
    ),
    "us-nc": State(
        name="North Carolina",
        publisher="North Carolina Department of Health and Human Services, Division of Social Services",
        publisher_index_url="https://policies.ncdhhs.gov/document/ep-300-low-income-energy-assistance-program-lieap/",
        path_stem="dss/energy-programs/ep-300",
        on_clearinghouse_index=False,
        matrix_status="in_manual",
        access_note="policies.ncdhhs.gov HTTP 200 to the plain client",
        queue_note="Energy Programs manual EP-300 Low Income Energy Assistance Program, Change #2-2026 effective 2026-05-01 (22 pages); section 300.12 B on page 19 prints the benefit chart by household size and income category.",
        docs=[d(slug="", title="North Carolina DSS Energy Programs Manual EP-300: Low Income Energy Assistance Program (Change #2-2026, May 1, 2026)",
                url="https://policies.ncdhhs.gov/wp-content/uploads/EP-300-5.1.2026.pdf",
                expression_date="2026-05-01", expression_note="printed 'Change #2-2026, May 1, 2026'", pages=22, matrix_pages="19")],
    ),
    "us-nm": State(
        name="New Mexico",
        publisher="New Mexico Health Care Authority, Income Support Division",
        publisher_index_url="https://www.hca.nm.gov/lookingforinformation/income-eligibility-federal-poverty-level-guidelines/",
        path_stem="hca/liheap-point-and-income-guide/ffy2026",
        on_clearinghouse_index=False,
        matrix_status="taken",
        access_note="hca.nm.gov HTTP 200 to the plain client",
        queue_note="LIHEAP Heating and Cooling Point and Income Guide FFY 2026 (1 page: income guidelines at 150 percent of poverty, point categories and the $35 point value) from the HCA income-eligibility page; NMAC 8.150.620.10 sets the point value annually outside the rule.",
        docs=[d(slug="", title="New Mexico LIHEAP FFY 2026 Heating and Cooling Point and Income Guide",
                url="https://www.hca.nm.gov/wp-content/uploads/Heating-and-Cooling-Point-and-Income-Guide-2026.pdf",
                expression_date="2025-10-01", expression_note="FFY 2026 guide (PDF dated 2025-09-10)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=1, matrix_pages="1")],
    ),
    "us-ny": State(
        name="New York",
        publisher="New York State Office of Temporary and Disability Assistance",
        publisher_index_url="https://otda.ny.gov/programs/heap/",
        path_stem="", on_clearinghouse_index=True, matrix_status="blocked",
        access_note="otda.ny.gov: HTTPS connection reset with no HTTP response to plain and Chrome-UA clients; HTTP 200 text/html 7,510-byte JavaScript challenge (F5/Shape, window['bobcmn']) to a chrome120 TLS fingerprint on 2026-09-13, for the HEAP manual, the HEAP page and the 2025-26 HEAP GIS alike",
        queue_note="Blocked: the HEAP manual (http://otda.ny.gov/programs/heap/HEAP-manual.pdf, 302 to HTTPS) and every otda.ny.gov page sit behind the OTDA JavaScript challenge (the same block as the SSI, TANF and SNAP queues); no other official host serves the manual or the benefit table; nothing was worked around.",
        docs=[],
    ),
    "us-oh": State(
        name="Ohio",
        publisher="Ohio Department of Job and Family Services (HEAP since 2026-04-06; formerly Ohio Department of Development)",
        publisher_index_url="https://jfs.ohio.gov/public-assistance/energy-and-community-assistance",
        path_stem="odjfs/heap-benefit-matrix",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="the Clearinghouse-listed manual is on a third-party CDN (irp.cdn-website.com) and is not taken; jfs.ohio.gov answers HTTP 404 to the plain client and a 1.1 MB single-page application to a Chrome UA, and its HEAP page HTTP 502/504 to a chrome120 fetch on 2026-09-13; liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="2025 LIHEAP Benefit Matrix attachment of the FY 2026 plan (1 page, headed 'DRAFT Funding' and dated 5/1/2025) from the Clearinghouse; the state's EAP guidelines are posted only on a non-government CDN, and the ODJFS HEAP page was unreachable to every client.",
        docs=[ch_matrix("OH", "Ohio LIHEAP FY 2026 plan attachment: 2025 LIHEAP Benefit Matrix (HWAP transfer up to 25 percent)", 1, "2025-10-01", "attachment dated 5/1/2025 for the FY 2026 plan (headed DRAFT Funding); PDF dated 2025-08-04")],
    ),
    "us-ok": State(
        name="Oklahoma",
        publisher="Oklahoma Human Services",
        publisher_index_url="https://oklahoma.gov/okdhs/services/liheap/utilityservicesliheapmain.html",
        path_stem="okdhs/oac-340-appendix/c-7-a",
        on_clearinghouse_index=False,
        matrix_status="in_manual",
        access_note="oklahoma.gov HTTP 200 to the plain client; rules.ok.gov (the OAC 340:20-1 text) HTTP 403 Cloudflare to plain and Chrome-UA clients and a JavaScript shell to chrome120",
        queue_note="OKDHS Appendix C-7-A 'Estimated LIHEAP Benefit Level for all Households' (2 pages, footer 10/1/2021, file dated 2026-06-17; winter heating, LP/oil, heat-in-rent and summer cooling tables) reached from the OKDHS forms search center; the FY 2026 plan cites it as the OAC 340:20-1 appendix.",
        docs=[d(slug="", title="Oklahoma Human Services Appendix C-7-A: Estimated LIHEAP Benefit Level for all Households",
                url="https://oklahoma.gov/content/dam/ok/en/okdhs/documents/searchcenter/okdhsformresults/c-7-a.pdf",
                expression_date="2021-10-01", expression_note="footer 'Appendix C-7-A 10/1/2021'; the served file is dated 2026-06-17 and the values match the FY 2026 plan sections 2.6 and 3.6",
                subtype="policy_appendix_pdf", pages=2, matrix_pages="1-2")],
    ),
    "us-or": State(
        name="Oregon",
        publisher="Oregon Housing and Community Services",
        publisher_index_url="https://www.oregon.gov/ohcs/energy-weatherization/pages/energy-service-provider-resources.aspx",
        path_stem="ohcs/energy-assistance-intake-operations-policy-manual",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="oregon.gov HTTP 200 to the plain client; the Clearinghouse-listed 2022 manual URL answers 404",
        queue_note="2026 Energy Programs (LIHEAP and OEAP) Intake Operations and Policy Manual, effective 2025-10-01 to 2026-09-30 (95 pages); the 2026 benefit matrices for regions 1 and 2 are on pages 77-80.",
        docs=[d(slug="", title="Oregon LIHEAP and OEAP Intake Operations and Policy Manual, Program Year 2026",
                url="https://www.oregon.gov/ohcs/energy-weatherization/Documents/2026%20Final%20Energy%20Assistance%20Intake%20Operations%20&%20Policy%20Manual.pdf",
                expression_date="2025-10-01", expression_note="printed 'Effective October 1, 2025 - September 30, 2026'; PDF dated 2026-06-30", pages=95, matrix_pages="77-80")],
    ),
    "us-pa": State(
        name="Pennsylvania",
        publisher="Pennsylvania Department of Human Services",
        publisher_index_url="http://services.dpw.state.pa.us/oimpolicymanuals/liheap/index.htm",
        path_stem="dhs/liheap-handbook",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="services.dpw.state.pa.us HTTP 200 to the plain client (one TOC file read timed out once and was retried); liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="LIHEAP Handbook, a RoboHelp 2026 manual (75 topic pages walked from whxdata/toc*.new.js; chapter 638 and its appendices carry the benefit calculation, the benefit table page links only the DHS dynamic lookup), plus the 2025-2026 energy year LIHEAP Benefit Charts for all 67 counties (469 pages, report generated 2025-08-07) from the Clearinghouse.",
        robohelp=("http://services.dpw.state.pa.us/oimpolicymanuals/liheap/", "index.htm", "dhs/liheap-handbook", "2026-09-14", "fetch date; topic pages print their own 'Reviewed' dates (e.g. Appendix A: August 5, 2026)"),
        docs=[ch_matrix("PA", "Pennsylvania LIHEAP FY 2026 plan attachment: LIHEAP Benefit Charts by county, energy year 2025-2026", 469, "2025-10-01", "energy year 2025-2026 charts, report generated 8/7/2025", matrix_pages="1-469")],
    ),
    "us-ri": State(
        name="Rhode Island",
        publisher="Rhode Island Department of Human Services",
        publisher_index_url="https://dhs.ri.gov/programs-and-services/energy-assistance-programs-heating/ffy-2026-low-income-guidelines",
        path_stem="", on_clearinghouse_index=False, matrix_status="absent",
        access_note="dhs.ri.gov HTTP 200 to the plain client; liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="Absent: DHS posts the FFY 2026 eligibility (income) table, the plan summary and the proposed rule but no grant table; the Clearinghouse file RI_BenefitMatrix_2026.pdf (1 page, dated 2025-07-18) is headed '[Moderate matrix dependent on funding levels at FFY 2025, to be input 9/30/2025]' and is a provisional placeholder, not taken.",
        docs=[],
    ),
    "us-sc": State(
        name="South Carolina",
        publisher="South Carolina Office of Economic Opportunity",
        publisher_index_url="https://oeo.sc.gov/managedsites/prd/oeo/liheap.html",
        path_stem="oeo/liheap-benefit-matrix",
        on_clearinghouse_index=False,
        matrix_status="taken",
        access_note="oeo.sc.gov HTTP 200 to the plain client (lists plans, the administrative guide and the fiscal manual, no matrix); liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="2026 Benefit Matrix attachment of the FY 2026 plan (2 pages: income eligibility at 60 percent SMI, non-emergency benefit add-on table, crisis caps) from the Clearinghouse; the OEO site posts no matrix.",
        docs=[ch_matrix("SC", "South Carolina LIHEAP FY 2026 plan attachment: 2026 Benefit Matrix", 2, "2025-10-01", "2026 matrix (PDF dated 2025-08-14)")],
    ),
    "us-tn": State(
        name="Tennessee",
        publisher="Tennessee Housing Development Agency",
        publisher_index_url="https://thda.org/govt-non-profit/low-income-home-energy-assistance-program-liheap-forms/",
        path_stem="thda/liheap",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="thda.org HTTP 200 to the plain client; its documents are served from THDA's own WordPress asset distribution (dogvxws799i6n.cloudfront.net), linked directly from the THDA index page; the Clearinghouse-listed thda.org/pdf/ URL answers 404",
        queue_note="LIHEAP 2026 Policy Manual for Regular and Crisis Assistance, revised 2025-08-29 (67 pages; section 2.20 refers to form LI-11) plus the LIHEAP 2026 Benefit Matrix (1 page) and the Fiscal Year 2027 Benefit Matrix (4 pages, dated 2026-07-15) from the THDA LIHEAP forms page.",
        hosting="THDA WordPress asset distribution (dogvxws799i6n.cloudfront.net), linked from thda.org",
        docs=[
            d(slug="policy-manual-2026", title="Tennessee LIHEAP 2026 Policy Manual for Regular and Crisis Assistance (revised August 29, 2025)",
              url="https://dogvxws799i6n.cloudfront.net/wp-content/uploads/LIHEAP-2026-Policy-Manual-for-Tennessee.pdf",
              expression_date="2025-10-01", expression_note="FY 2026 manual, printed 'Revised 8/29/2025'", pages=67),
            d(slug="benefit-matrix-2026", title="Tennessee LIHEAP 2026 Benefit Matrix (form LI-11)",
              url="https://dogvxws799i6n.cloudfront.net/wp-content/uploads/2026-LIHEAP-Eligible-Income-Household-Size-Benefits.pdf",
              expression_date="2025-10-01", expression_note="FY 2026 matrix (PDF dated 2025-09-05)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=1, matrix_pages="1"),
            d(slug="benefit-matrix-2027", title="Tennessee LIHEAP Fiscal Year 2027 Benefit Matrix (form LI-12)",
              url="https://dogvxws799i6n.cloudfront.net/wp-content/uploads/2027-LIHEAP-LI-12-Eligible-Income-Benefit-Matrix.pdf",
              expression_date="2026-07-15", expression_note="dated 2026-07-15 for fiscal year 2027 (from 2026-10-01)", document_class="policy", subtype="plan_attachment_benefit_matrix_pdf", pages=4, matrix_pages="1-4"),
        ],
    ),
    "us-tx": State(
        name="Texas",
        publisher="Texas Department of Housing and Community Affairs",
        publisher_index_url="https://www.tdhca.texas.gov/community-affairs/ceap",
        path_stem="", on_clearinghouse_index=False, matrix_status="absent",
        access_note="tdhca.texas.gov HTTP 200 to the plain client; the Texas SOS administrative code portal (texas-sos.appianportalsgov.com) serves a 2.5 KB JavaScript shell to the plain client",
        queue_note="Absent as a table: CEAP benefits are a sliding scale by income set by subrecipients under 10 TAC 6.309(e) (caps per component); the 2026 plan (55 pages, min $1 / max $12,600) attaches no matrix and the Clearinghouse serves only a 2025 file reproducing the rule's caps; the rule text is on the SOS JavaScript-only portal.",
        docs=[],
    ),
    "us-va": State(
        name="Virginia",
        publisher="Virginia Department of Social Services",
        publisher_index_url="https://www.dss.virginia.gov/relief/ea/",
        path_stem="vdss/energy-assistance-manual",
        on_clearinghouse_index=True,
        matrix_status="taken",
        access_note="dss.virginia.gov HTTP 200 to the plain client (the Clearinghouse-listed /files/division/bp/ea/ URL answers 404); liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="VDSS Energy Assistance Manual, Volumes IX and X (138 pages, PDF created 2025-05-16; benefits are points-based with amounts set by the home office, no dollar chart printed) plus the FY 2026 plan attachment from the Clearinghouse (7 image-only pages of manual excerpts with the FFY 2026 income limits, OCR).",
        docs=[
            d(slug="", title="Virginia Department of Social Services Energy Assistance Manual (Volumes IX and X)",
              url="https://www.dss.virginia.gov/media/vdss/benefit-programs/documents/eap/Complete_Manual.pdf",
              expression_date="2025-05-16", expression_note="PDF created 2025-05-16; chapter pages carry their own transmittal dates (e.g. 06/11, Transmittal 11-1)", pages=138),
            ch_matrix("VA", "Virginia LIHEAP FY 2026 plan attachment: Energy Assistance Manual excerpts with FFY 2026 income limits", 7, "2025-10-01", "FY 2026 attachment (PDF dated 2025-08-27)",
                      extraction={"ocr": True, "ocr_dpi": 300}, extra_metadata={"ocr_note": "image-only PDF (707 characters of text layer); read with tesseract at 300 dpi"}),
        ],
    ),
    "us-vt": State(
        name="Vermont",
        publisher="Vermont Department for Children and Families, Economic Services Division",
        publisher_index_url="https://dcf.vermont.gov/esd/laws-rules/proposed/P2900",
        path_stem="dcf",
        on_clearinghouse_index=True,
        matrix_status="in_manual",
        access_note="dcf.vermont.gov and outside.vermont.gov HTTP 200 to the plain client",
        queue_note="Seasonal Fuel Assistance rule 2900 and Crisis Fuel rule 3100 (adopted 2024-06-22, from the ESD current-rules page) and the Fuel Assistance procedures P2914A-D (calculation of benefits), P2915 (heat cost percentage table, 7/1/25) and P2916 (standard heating cost tables, 2025-26 season) from the P2900 procedures index the Clearinghouse lists; the seasonal payment rate itself is looked up in ACCESS (P2914B).",
        docs=[
            d(slug="esd-rules/2900", title="Vermont DCF Economic Services Division Rule 2900: Seasonal Fuel Assistance (adopted June 22, 2024)",
              url="https://outside.vermont.gov/dept/DCF/Shared%20Documents/ESD/Rules/2900-Seasonal-Fuel-Assistance.pdf",
              expression_date="2024-06-22", expression_note="printed '(06/22/2024, 23-18)'", document_class="regulation", subtype="agency_rule_pdf", pages=56, matrix_pages="39-40 (calculation steps)"),
            d(slug="esd-rules/3100", title="Vermont DCF Economic Services Division Rule 3100: Crisis Fuel Assistance (adopted June 22, 2024)",
              url="https://outside.vermont.gov/dept/DCF/Shared%20Documents/ESD/Rules/3100-Crisis-Fuel.pdf",
              expression_date="2024-06-22", expression_note="printed '(06/22/2024, 23-20)'", document_class="regulation", subtype="agency_rule_pdf", pages=23),
            d(slug="esd-procedures/p2914a", title="Vermont ESD Procedure P-2914A: Calculation of Benefits, Percentage of Poverty (2025-2026)",
              url="https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2914A.pdf",
              expression_date="2025-07-01", expression_note="2025-2026 heating season table; PDF dated 2025-07-28", subtype="procedure_pdf", pages=3, matrix_pages="1-3"),
            d(slug="esd-procedures/p2914b", title="Vermont ESD Procedure P-2914B: Calculation of Benefits, Payment Rate",
              url="https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2914B.pdf",
              expression_date="2025-07-01", expression_note="PDF dated 2025-07-28 (7/1/25 procedures release)", subtype="procedure_pdf", pages=1),
            d(slug="esd-procedures/p2914c", title="Vermont ESD Procedure P-2914C: Calculation of Benefits, Types of Benefits",
              url="https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2914C.pdf",
              expression_date="2025-07-01", expression_note="PDF dated 2025-07-28 (7/1/25 procedures release)", subtype="procedure_pdf", pages=2),
            d(slug="esd-procedures/p2914d", title="Vermont ESD Procedure P-2914D: Calculation of Benefits, Manual Budget",
              url="https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2914D.pdf",
              expression_date="2025-07-01", expression_note="PDF dated 2025-07-21 (7/1/25 procedures release)", subtype="procedure_pdf", pages=9),
            d(slug="esd-procedures/p2915", title="Vermont ESD Procedure P-2915: Heat Cost Percentage Table (7/1/25)",
              url="https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2915.pdf",
              expression_date="2025-07-01", expression_note="printed '(7/1/25, 25-16)'", subtype="procedure_pdf", pages=1, matrix_pages="1"),
            d(slug="esd-procedures/p2916", title="Vermont ESD Procedure P-2916: Standard Heating Cost Tables, 2025-26 heating season",
              url="https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/ESD-Procedure-P2916.pdf",
              expression_date="2025-07-01", expression_note="tables 'for 2025-26 heating season'; PDF dated 2025-07-28", subtype="procedure_pdf", pages=2, matrix_pages="1-2"),
        ],
    ),
    "us-wa": State(
        name="Washington",
        publisher="Washington State Department of Commerce",
        publisher_index_url="https://www.commerce.wa.gov/community-opportunities/liheap/",
        path_stem="commerce/liheap-benefit-calculation-worksheet",
        on_clearinghouse_index=False,
        matrix_status="taken",
        access_note="commerce.wa.gov HTTP 200 to the plain client (links Box-hosted eligibility guidelines and the plan only); liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="Benefit Calculation Worksheet (actual and surrogate heat cost, household adjuster table; 5 pages) attached to the FY 2026 plan, from the Clearinghouse; Washington computes benefits by formula rather than a grid and Commerce posts no matrix.",
        docs=[ch_matrix("WA", "Washington LIHEAP FY 2026 plan attachment: Benefit Calculation Worksheet (actual and surrogate heat cost)", 5, "2025-10-01", "FY 2026 attachment (PDF dated 2025-12-22)")],
    ),
    "us-wi": State(
        name="Wisconsin",
        publisher="Wisconsin Department of Energy, Housing and Community Resources",
        publisher_index_url="https://energyandhousing.wi.gov/Pages/AgencyResources/energy-assistance.aspx",
        path_stem="dehcr/wheap-manual/py2026",
        on_clearinghouse_index=True,
        matrix_status="absent",
        access_note="energyandhousing.wi.gov HTTP 200 to the plain client (the Clearinghouse-listed PY 2024 URL answers 404)",
        queue_note="WHEAP Manual Program Year 2026, revised August 2025 (178 pages; the program year in force on the fetch date, PY 2027 is also posted); section 2.3 says the HE+ system calculates benefits from income, household size, fuel type, fuel use and rooms, so no matrix is printed.",
        docs=[d(slug="", title="Wisconsin Home Energy Assistance Program (WHEAP) Manual, Program Year 2026",
                url="https://energyandhousing.wi.gov/Documents/WHEAP/WheapManual_PY26.pdf",
                expression_date="2025-10-01", expression_note="Program Year 2026 (2025-10-01 to 2026-09-30), printed 'Revised: August 2025'", pages=178)],
    ),
    "us-wv": State(
        name="West Virginia",
        publisher="West Virginia Department of Human Services, Bureau for Family Assistance",
        publisher_index_url="https://bfa.wv.gov/utility-assistancelieap",
        path_stem="", on_clearinghouse_index=True, matrix_status="absent",
        access_note="bfa.wv.gov and wvdhhr.org HTTP 200 to the plain client",
        queue_note="Absent: the Clearinghouse-listed chapter 26 files (wvdhhr.org legacy Income Maintenance Manual, sections 26.1-26.5 dated to 2014) refer to a 'LIEAP benefit payment chart' that is not published; the current DoHS Income Maintenance Manual (bfa.wv.gov, effective 2026-07-01, in the selected corpus) assigns chapter 26 to the Medicaid Work Incentive and carries no LIEAP chapter; the BFA LIEAP page posts only the FY 2026 fact sheet (income limits) and the FY 2026 plan.",
        docs=[],
    ),
    "us-wy": State(
        name="Wyoming",
        publisher="Wyoming Department of Family Services",
        publisher_index_url="https://dfs.wyo.gov/assistance-programs/home-utilities-energy-assistance/low-income-energy-assistance-program-lieap/",
        path_stem="", on_clearinghouse_index=False, matrix_status="absent",
        access_note="dfs.wyo.gov HTTP 200 to the plain client; liheapch.acf.gov HTTP 200 with the CA bundle",
        queue_note="Absent: DFS posts the FFY 2026 LIEAP State Model Plan (53 pages, min $48 / max $1,901, no attachment), application guides and an income-guidelines handout; the Clearinghouse serves only a 2025 matrix workbook (WY_BenefitMatrix_2025.pdf) and answers 404 for 2026.",
        docs=[],
    ),
}


# -------------------------------------------------------------- wave 5: state policy manuals (2026-09-15)
MANUAL_STATES: dict[str, State] = {
    "us-ar": State(
        name="Arkansas",
        publisher="Arkansas Department of Energy and Environment, Arkansas Energy Office",
        publisher_index_url="https://adeq.state.ar.us/energy/assistance/liheap.aspx",
        path_stem="aeo/liheap-policy-and-procedures-manual",
        on_clearinghouse_index=True,
        matrix_status="taken",
        hosting=CLEARINGHOUSE_AUTHORITY,
        access_note=(
            "liheapch.acf.gov HTTP 200 with the Entrust intermediate in the CA bundle (9,871,526 bytes, Last-Modified "
            "2024-12-04); the Clearinghouse manuals index links /sites/default/files/webfiles/docs/2026/manuals/AR_Manual_2026.pdf, "
            "which answers HTTP 404 (re-read 2026-09-15), while /docs/2025/manuals/AR_Manual_2025.pdf is served under the "
            "publisher's own naming and is not linked from any index page read; adeq.state.ar.us HTTP 200 to the plain client "
            "(the LIHEAP page posts the FY 2026 matrices, eligibility chart, application form, brochure and the proposed "
            "FY 2027 model plan, no policy manual)"
        ),
        queue_note=(
            "Arkansas Energy Office LIHEAP Policy and Procedures Manual, FFY 2025 (190 pages, effective 2024-10-01 to "
            "2025-09-30 as printed; the crisis benefit table is Appendix J on PDF page 178; the regular-assistance benefit "
            "matrices are the separate FFY 2026 attachments taken on 2026-09-14), the Clearinghouse-hosted copy: the "
            "index's FFY 2026 link is dead and the agency posts no manual of its own."
        ),
        docs=[d(slug="ffy2025",
                title="Arkansas LIHEAP Policy and Procedures Manual, FFY 2025 (Arkansas Energy Office; effective October 1, 2024 - September 30, 2025)",
                url="https://liheapch.acf.gov/docs/2025/manuals/AR_Manual_2025.pdf",
                expression_date="2024-10-01",
                expression_note="cover 'Effective October 1, 2024 – September 30, 2025'; PDF created 2024-11-18, Clearinghouse Last-Modified 2024-12-04",
                pages=190, matrix_pages="178",
                extra_metadata={
                    "clearinghouse_manual_note": (
                        "the Clearinghouse 'State LIHEAP Policy Manuals' index (read 2026-09-15) links the FFY 2026 file, "
                        "which answers HTTP 404; this FFY 2025 file is served by the same publisher under its own naming "
                        "(/docs/2025/manuals/) and was located by that naming, not from an index page"
                    ),
                    "benefit_matrix_note": (
                        "PDF page 178 is Appendix J, the crisis benefit table; the regular-assistance benefit matrices are "
                        "the FFY 2026 attachments in us-ar/policy/2026-09-14-liheap-benefit-matrix"
                    ),
                })],
    ),
}


def citation_path(jur: str, state: State, doc: Doc) -> str:
    stem = state.path_stem
    if doc.fmt == "html" and state.robohelp:
        stem = state.robohelp[2]
    elif doc.document_class == "policy" and "liheapch.acf.gov" in doc.url:
        stem = "acf/liheap-plan/fy2026-benefit-matrix"
    parts = [jur, doc.document_class, *(x for x in (stem, doc.slug) if x)]
    return "/".join(parts)


def build_document(jur: str, state: State, doc: Doc, family: Family = BENEFIT_MATRIX) -> dict[str, Any]:
    source_id = f"{jur}-liheap-" + re.sub(r"[^a-z0-9]+", "-", "/".join(citation_path(jur, state, doc).split("/")[2:])).strip("-")
    record: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": jur,
        "document_class": doc.document_class,
        "title": doc.title,
        "source_url": doc.url,
    }
    if doc.download_url:
        record["download_url"] = doc.download_url
    record.update({
        "source_format": doc.fmt,
        "source_as_of": family.source_as_of,
        "expression_date": doc.expression_date,
        "citation_path": citation_path(jur, state, doc),
    })
    if doc.request:
        record["request"] = dict(doc.request)
    if doc.extraction:
        record["extraction"] = dict(doc.extraction)
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": state.publisher,
    }
    if state.hosting:
        metadata["hosting_authority"] = state.hosting
    metadata.update({
        "document_subtype": doc.subtype,
        "program": "LIHEAP",
        "state": jur.split("-")[1].upper(),
        "closure_elements": ["LIHEAP-ST-09", "LIHEAP-ST-18"] if doc.document_class != "policy" else ["LIHEAP-ST-09"],
        "index_url": CLEARINGHOUSE_INDEX,
        "publisher_index_url": state.publisher_index_url,
        "on_clearinghouse_index": state.on_clearinghouse_index,
        "source_discovery_group": f"{jur}/{doc.document_class}/{family.discovery_group_suffix}",
        "discovered_via": (
            f"{family.discovered_via_prefix}; ACF LIHEAP Clearinghouse "
            f"'State LIHEAP Policy Manuals' index {CLEARINGHOUSE_INDEX}, publisher page {state.publisher_index_url}"
        ),
        "extraction_granularity": "pdf_page" if doc.fmt == "pdf" and not (doc.extraction or {}).get("segmentation") else "html_blocks" if doc.fmt == "html" else (doc.extraction or {}).get("segmentation"),
        "expression_date_note": doc.expression_note,
        "access_note": state.access_note,
    })
    if doc.pages is not None:
        metadata["page_count"] = doc.pages
    metadata["benefit_matrix_pdf_pages"] = doc.matrix_pages if doc.matrix_pages else "none printed in this document"
    if doc.fmt == "pdf":
        metadata["page_numbering_note"] = (
            "benefit_matrix_pdf_pages counts PDF pages; the corpus citation suffix page-N counts text-bearing pages only "
            "(image-only and blank pages are skipped), so N can be smaller than the PDF page number"
        )
    if "liheapch.acf.gov" in doc.url:
        metadata["tls_note"] = TLS_NOTE
    metadata.update(doc.extra_metadata)
    record["metadata"] = metadata
    return record


def manifest_stem(jur: str, document_class: str, family: Family = BENEFIT_MATRIX) -> str:
    suffix = {"manual": "manual", "regulation": "rule", "policy": "attachments", "guidance": "guidance"}[document_class]
    return f"{jur}-liheap-{family.manifest_infix}-{suffix}"


def write_manifests(only: set[str] | None, family: Family = BENEFIT_MATRIX) -> dict[str, list[dict[str, Any]]]:
    states = STATES if family is BENEFIT_MATRIX else MANUAL_STATES
    written: dict[str, list[dict[str, Any]]] = {}
    for jur, state in sorted(states.items()):
        if only and jur not in only:
            continue
        if not state.docs and not state.robohelp:
            written[jur] = []
            continue
        by_class: dict[str, list[dict[str, Any]]] = {}
        docs = list(state.docs)
        if state.robohelp:
            docs = robohelp_docs(state) + docs
        for doc in docs:
            by_class.setdefault(doc.document_class, []).append(build_document(jur, state, doc, family))
        scopes = []
        for document_class, documents in by_class.items():
            stem = manifest_stem(jur, document_class, family)
            path = ROOT / "manifests" / f"{stem}.yaml"
            path.write_text(yaml.safe_dump({"version": family.version, "documents": documents}, sort_keys=False, allow_unicode=True, width=120))
            scopes.append({
                "jurisdiction": jur,
                "document_class": document_class,
                "version": family.version,
                "manifest": f"manifests/{stem}.yaml",
                "document_count": len(documents),
            })
        written[jur] = scopes
    return written


def update_queue(written: dict[str, list[dict[str, Any]]], family: Family = BENEFIT_MATRIX) -> None:
    queue_path = ROOT / "manifests" / "liheap-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    states = STATES if family is BENEFIT_MATRIX else MANUAL_STATES
    for row in queue["states"]:
        jur = row["jurisdiction"]
        if jur not in written or row.get("source_kind") != "official_pdf_state_plan":
            continue
        state = states[jur]
        scopes = written[jur]
        record: dict[str, Any] = {
            "status": "taken" if scopes else state.matrix_status,
            "scopes": scopes,
            "index_url": CLEARINGHOUSE_INDEX,
            "index_document_count": CLEARINGHOUSE_INDEX_COUNT,
            "publisher_index_url": state.publisher_index_url,
            "on_clearinghouse_index": state.on_clearinghouse_index,
            "taken_count": sum(s["document_count"] for s in scopes),
            "matrix_status": state.matrix_status,
            "closure_elements": ["LIHEAP-ST-09", "LIHEAP-ST-18"] if family is BENEFIT_MATRIX else ["LIHEAP-ST-18"],
            "run_note": family.run_note,
            "notes": f"{family.queue_sentence_date} closure run: {state.queue_note} Publisher: {state.publisher}. Access: {state.access_note}.",
        }
        row[family.queue_key] = record
        family_label = "the benefit-matrix family (LIHEAP-ST-09/ST-18)" if family is BENEFIT_MATRIX else "the state policy-manual family (LIHEAP-ST-18)"
        if scopes:
            sentence = (
                f" {family.queue_sentence_date}: {family_label} was taken as "
                + ", ".join(f"{s['jurisdiction']}/{s['document_class']}/{s['version']}" for s in scopes)
                + f" (see {family.queue_key})."
            )
        else:
            sentence = f" {family.queue_sentence_date}: {family_label} is {state.matrix_status} (see {family.queue_key})."
        if sentence.strip() not in row["notes"]:
            row["notes"] = row["notes"].rstrip() + sentence
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated jurisdictions (default: every state in STATES)")
    parser.add_argument("--no-queue", action="store_true", help="write manifests only")
    parser.add_argument("--family", choices=sorted(FAMILIES), default=BENEFIT_MATRIX.name,
                        help="benefit-matrix (2026-09-14, STATES) or policy-manual (2026-09-15, MANUAL_STATES)")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None
    family = FAMILIES[args.family]
    written = write_manifests(only, family)
    for jur, scopes in written.items():
        for scope in scopes:
            print(f"{jur} {scope['document_class']} {scope['manifest']} documents={scope['document_count']}")
    states = STATES if family is BENEFIT_MATRIX else MANUAL_STATES
    for jur, scopes in written.items():
        if not scopes:
            print(f"{jur} {states[jur].matrix_status}: no manifest")
    if not args.no_queue:
        update_queue(written, family)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
