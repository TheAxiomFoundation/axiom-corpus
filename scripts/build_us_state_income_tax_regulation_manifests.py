#!/usr/bin/env python3
"""Build the 2026-09-14 state income-tax regulation manifests (needs-closure gap R01).

One manifest per jurisdiction under ``manifests/us-<st>-income-tax-regulations.yaml``.
Static specifications describe publishers that post one file per chapter; discovery
functions enumerate publishers that post one file per section or that expose a JSON
API (the official publisher's own index is always the enumeration source).

Run: ``uv run python scripts/build_us_state_income_tax_regulation_manifests.py [--only us-xx]``

Every network call goes to the official publisher; ``--cache-dir`` keeps the index
responses so a rebuild is reproducible offline. The script prints a JSON summary
(index URL, index document count, taken count) per jurisdiction for the queue rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

USER_AGENT = (
    "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) "
    "https://github.com/TheAxiomFoundation/axiom-corpus"
)
SOURCE_AS_OF = "2026-09-14"
DISCOVERED_VIA = "manual-review:tax-agent-queue 2026-09-14 (needs-closure R01)"
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "manifests"

_cache_dir: Path | None = None
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})


def fetch(url: str, *, impersonate: bool = False, delay: float = 0.0) -> bytes:
    """Fetch ``url`` once (cached under --cache-dir) from the official publisher."""

    key = hashlib.sha1(url.encode()).hexdigest()
    if _cache_dir is not None:
        cached = _cache_dir / f"{key}.bin"
        if cached.exists():
            return cached.read_bytes()
    if delay:
        time.sleep(delay)
    if impersonate:
        from curl_cffi import requests as curl_requests

        response = curl_requests.get(url, impersonate="chrome120", timeout=120)
        content = response.content
        status = response.status_code
    else:
        # A fresh request without cookies: govt.westlaw.com serves an interstitial once
        # a cookie jar exists.
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}, timeout=120
        )
        content = response.content
        status = response.status_code
    if status != 200:
        raise RuntimeError(f"{url}: HTTP {status}")
    if _cache_dir is not None:
        _cache_dir.mkdir(parents=True, exist_ok=True)
        (_cache_dir / f"{key}.bin").write_bytes(content)
    return content


def soup(url: str, **kwargs: Any) -> BeautifulSoup:
    return BeautifulSoup(fetch(url, **kwargs), "html.parser")


def document(
    *,
    jurisdiction: str,
    source_id: str,
    citation_path: str,
    title: str,
    source_url: str,
    source_format: str,
    expression_date: str,
    authority: str,
    publisher: str,
    subtype: str,
    index_url: str,
    extraction: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    download_url: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": jurisdiction,
        "document_class": "regulation",
        "citation_path": citation_path,
        "title": title,
        "source_url": source_url,
        "source_format": source_format,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": expression_date,
    }
    if download_url:
        entry["download_url"] = download_url
    if request:
        entry["request"] = request
    if extraction:
        entry["extraction"] = extraction
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": authority,
        "official_publisher": publisher,
        "document_subtype": subtype,
        "program": "individual_income_tax",
        "source_discovery_group": f"{jurisdiction}/regulation/income-tax",
        "discovered_via": f"{DISCOVERED_VIA}; index {index_url}",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    entry["metadata"] = metadata
    return entry


class Builder:
    def __init__(self) -> None:
        self.summary: dict[str, dict[str, Any]] = {}

    def write(
        self,
        jurisdiction: str,
        documents: list[dict[str, Any]],
        *,
        index_url: str,
        index_document_count: int,
        note: str,
        extra_top: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"version": SOURCE_AS_OF}
        if extra_top:
            payload.update(extra_top)
        payload["documents"] = documents
        path = MANIFEST_DIR / f"{jurisdiction}-income-tax-regulations.yaml"
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=110)
        )
        self.summary[jurisdiction] = {
            "manifest": str(path.relative_to(REPO_ROOT)),
            "index_url": index_url,
            "index_document_count": index_document_count,
            "taken_count": len(documents),
            "note": note,
        }
        print(f"{jurisdiction}: {len(documents)} documents -> {path.name}", file=sys.stderr)


# --------------------------------------------------------------------------------------
# Static publishers: one file (or a few) per chapter
# --------------------------------------------------------------------------------------


def build_az(b: Builder) -> None:
    index = "https://apps.azsos.gov/public_services/Title_15/15-02.pdf"
    docs = [
        document(
            jurisdiction="us-az",
            source_id="az-sos-aac-title-15-chapter-2-income-tax",
            citation_path="us-az/regulation/aac/title-15/chapter-2",
            title="Arizona Administrative Code Title 15, Chapter 2: Department of Revenue, "
            "Income and Withholding Tax Section",
            source_url=index,
            source_format="pdf",
            expression_date=SOURCE_AS_OF,
            authority="Arizona Department of Revenue",
            publisher="Arizona Secretary of State, Administrative Rules Division",
            subtype="administrative_code_chapter",
            index_url=index,
            request={"browser_impersonation": True},
            extraction={
                "segmentation": "labeled_sections",
                "section_label_pattern": r"^\s*(?P<label>R15-2[A-Z]?-\d+)\.\s*$",
                "section_heading_pattern": r"^\s*(?P<label>R15-2[A-Z]?-\d+)\.\s+(?P<heading>[A-Z].+)$",
                "label_only_heading_pattern": r"^[A-Z][A-Za-z0-9,;:'’().\- /]+$",
                "label_only_requires_heading": True,
                "section_heading_requires_bold": True,
                "drop_line_patterns": [
                    r"^TITLE 15\. REVENUE$",
                    r"^CHAPTER 2\. DEPARTMENT OF REVENUE.*$",
                    r"^Title 15$",
                    r"^15 A\.A\.C\. 2$",
                    r"^Arizona Administrative Code$",
                    r"^Supp\. [0-9-]+$",
                    r"^Page [0-9]+$",
                    r"^[A-Z][a-z]+ [0-9]{1,2}, [0-9]{4}$",
                ],
            },
            extra_metadata={
                "access_note": "apps.azsos.gov answers the plain client with a Cloudflare "
                "challenge (HTTP 403); the PDF is served to the browser-impersonation fetch."
            },
        )
    ]
    b.write("us-az", docs, index_url=index, index_document_count=1, note="AAC 15-2 chapter PDF")


def build_co(b: Builder) -> None:
    index = "https://www.sos.state.co.us/CCR/NumericalCCRDocList.do?deptID=19&agencyID=122"
    docs = [
        document(
            jurisdiction="us-co",
            source_id="co-sos-1-ccr-201-2-income-tax",
            citation_path="us-co/regulation/1-ccr-201-2",
            title="Code of Colorado Regulations 1 CCR 201-2: Income Tax (Taxation Division)",
            source_url="https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleVersionId=12424",
            download_url="https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=12424&fileName=1%20CCR%20201-2",
            source_format="pdf",
            expression_date="2026-08-13",
            authority="Colorado Department of Revenue, Taxation Division",
            publisher="Colorado Secretary of State",
            subtype="administrative_code_rule",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_heading_pattern": (
                    r"^Rule (?P<label>39-22-[0-9]+(?:\.[0-9]+)?(?:\([0-9a-zA-Z.]+\))*(?:[–-]\d+)?)\.\s*"
                    r"(?P<heading>[^,]*)$"
                ),
                "section_heading_requires_bold": True,
                "drop_line_patterns": [
                    r"^CODE OF COLORADO REGULATIONS$",
                    r"^1 CCR 201-2$",
                    r"^Taxation Division$",
                    r"^\d{1,3}$",
                ],
            },
        )
    ]
    b.write("us-co", docs, index_url=index, index_document_count=1, note="1 CCR 201-2 rule PDF")


def build_ct(b: Builder) -> None:
    index = "https://eregulations.ct.gov/eRegsPortal/Browse/RCSA/Title_12"
    docs = [
        document(
            jurisdiction="us-ct",
            source_id="ct-eregs-title-12-income-tax-drs",
            citation_path="us-ct/regulation/rcsa/12/income-tax",
            title="Regulations of Connecticut State Agencies, Title 12: Income Tax "
            "(Department of Revenue Services, sections 12-701(a)(1)-1 to 12-740(c)-2)",
            source_url="https://eregulations.ct.gov/eRegsPortal/Browse/getDocument?guid=%7B80F3E757-0000-CC89-BCB7-C50B40EC8ECF%7D",
            source_format="html",
            expression_date=SOURCE_AS_OF,
            authority="Connecticut Department of Revenue Services",
            publisher="Connecticut Secretary of the State, eRegulations System",
            subtype="administrative_code_subject_matter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "html_drop_selectors": ["p:has(> a[href^='#_'])"],
                "section_heading_pattern": (
                    r"^Sec\.\s*(?P<label>12-7\d\d[^\s]*?-\d+[a-z]?)\.?\s*(?P<heading>.*)$"
                ),
            },
            extra_metadata={
                "eregs_pdf_guid": "{80F3E757-0100-C329-9AB2-7F04B3D642EB}",
                "eregs_subject_matter": "12-740(a) INCOME TAX",
            },
        )
    ]
    b.write("us-ct", docs, index_url=index, index_document_count=1, note="eRegs income tax HTML")


def build_ga(b: Builder) -> None:
    index = "https://rules.sos.ga.gov/gac/560-7"
    docs = [
        document(
            jurisdiction="us-ga",
            source_id="ga-sos-560-7-income-tax-division",
            citation_path="us-ga/regulation/560-7",
            title="Rules and Regulations of the State of Georgia, Chapter 560-7: Income Tax Division",
            source_url="https://rules.sos.ga.gov/Download_pdf.aspx?st=GASOS&year=2026&dept=Departments&pdf=Department%20560%20RULES%20OF%20DEPARTMENT%20OF%20REVENUE",
            source_format="pdf",
            expression_date="2026-09-02",
            authority="Georgia Department of Revenue",
            publisher="Georgia Secretary of State, Rules and Regulations of the State of Georgia",
            subtype="administrative_code_chapter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "page_windows": [{"start_page": 389, "end_page": 822}],
                "section_heading_pattern": (
                    r"^Rule (?P<label>560-7-\d+-\.\d+)\.\s*(?P<heading>[A-Z][^.]{0,160}\.)\s*$"
                ),
                "drop_line_patterns": [r"^Cite as Ga\. Comp\. R\. & Regs\..*$"],
            },
            extra_metadata={
                "access_note": "Rule pages on rules.sos.ga.gov render their text only through a "
                "session-bound POST (/loadthedata.aspx); the Department 560 PDF download is "
                "the publisher's stable document and is page-windowed to Chapter 560-7."
            },
        )
    ]
    b.write("us-ga", docs, index_url=index, index_document_count=8, note="Dept 560 PDF, ch. 560-7")


def build_hi(b: Builder) -> None:
    index = "https://tax.hawaii.gov/legal/"
    docs = [
        document(
            jurisdiction="us-hi",
            source_id="hi-dotax-har-18-235-income-tax-law",
            citation_path="us-hi/regulation/har/18/235",
            title="Hawaii Administrative Rules Title 18, Chapter 235: Income Tax Law",
            source_url="https://files.hawaii.gov/tax/legal/har/har_235.pdf",
            source_format="pdf",
            expression_date="2025-12-31",
            authority="Hawaii Department of Taxation",
            publisher="Hawaii Department of Taxation",
            subtype="administrative_rules_chapter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_label_pattern": r"^§(?P<label>18-235-[0-9.]+(?:-[0-9]+)?[a-z]?)\s*$",
                "label_only_heading_pattern": r"^[A-Z“(][^.]{2,140}\.(?:\s|$)",
                "label_only_requires_heading": True,
                "page_windows": [{"start_page": 7, "end_page": 158}],
                "drop_line_patterns": [
                    r"^INCOME TAX LAW\s*$",
                    r"^235-\s*\d+\s+\(Unofficial Compilation.*$",
                    r"^HAWAII ADMINISTRATIVE RULES\s*$",
                    r"^\[THIS PAGE HAS BEEN INTENTIONALLY LEFT BLANK\.\]\s*$",
                ],
            },
        )
    ]
    b.write("us-hi", docs, index_url=index, index_document_count=1, note="HAR 18-235 PDF")


IA_CHAPTERS = {
    "300": "Administration",
    "301": "Filing Return and Payment of Tax",
    "302": "Determination of Net Income",
    "303": "Determination of Taxable Income",
    "304": "Adjustments to Computed Tax and Tax Credits",
    "305": "Assessments and Refunds",
    "306": "Penalty and Interest",
    "307": "Withholding",
    "308": "Estimated Income Tax for Individuals",
}


def build_ia(b: Builder) -> None:
    index = "https://www.legis.iowa.gov/law/administrativeRules/chapters?agency=701"
    docs = []
    for chapter, title in IA_CHAPTERS.items():
        docs.append(
            document(
                jurisdiction="us-ia",
                source_id=f"ia-legis-iac-701-{chapter}",
                citation_path=f"us-ia/regulation/iac/701/{chapter}",
                title=f"Iowa Administrative Code 701—Chapter {chapter}: {title}",
                source_url=f"https://www.legis.iowa.gov/docs/iac/chapter/701.{chapter}.pdf",
                source_format="pdf",
                expression_date="2026-09-02",
                authority="Iowa Department of Revenue",
                publisher="Iowa Legislature, Legislative Services Agency",
                subtype="administrative_code_chapter",
                index_url=index,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        r"^701[—-](?P<chapter>\d+)\.(?P<section>\d+)\([^)]+\)\s+(?P<heading>[A-Z].+)$"
                    ),
                    "section_label_template": "{section}",
                    "drop_line_patterns": [
                        r"^IAC \d+/\d+/\d+\s+Revenue\[701\]\s+Ch \d+, p\.\d+$",
                        r"^Ch \d+, p\.\d+\s+Revenue\[701\]\s+IAC \d+/\d+/\d+$",
                        r"^Revenue\[701\]\s+IAC \d+/\d+/\d+\s+Ch \d+, p\.\d+$",
                        r"^Revenue\[701\]\s+Ch \d+, p\.\d+\s+IAC \d+/\d+/\d+$",
                        r"^Chapter rescission date pursuant to Iowa Code section 17A\.7: .*$",
                    ],
                },
            )
        )
    b.write("us-ia", docs, index_url=index, index_document_count=9, note="IAC 701 ch. 300-308")


def build_id(b: Builder) -> None:
    index = "https://adminrules.idaho.gov/rules/current/35/"
    docs = [
        document(
            jurisdiction="us-id",
            source_id="id-oar-idapa-35-01-01-income-tax",
            citation_path="us-id/regulation/idapa/35/01/01",
            title="IDAPA 35.01.01: Income Tax Administrative Rules (Idaho State Tax Commission)",
            source_url="https://adminrules.idaho.gov/rules/current/35/350101.pdf",
            source_format="pdf",
            expression_date="2026-07-01",
            authority="Idaho State Tax Commission",
            publisher="Idaho Office of the Administrative Rules Coordinator",
            subtype="administrative_code_chapter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_heading_pattern": (
                    r"^(?P<label>\d{3})\.\s+(?P<heading>[A-Z][A-Z0-9 ,;:'&()\-/–]+?)\.?$"
                ),
                "section_label_pattern": r"^(?P<label>\d{3})\.$",
                "label_only_heading_pattern": r"^[A-Z][A-Z0-9 ,;:'&()\-/–]+\.?$",
                "label_only_requires_heading": True,
                "drop_line_patterns": [
                    r"^IDAHO ADMINISTRATIVE CODE.*$",
                    r"^Idaho State Tax Commission.*$",
                    r"^IDAPA 35\.01\.01.*$",
                    r"^Section \d+\s+Page \d+.*$",
                    r"^Page \d+$",
                ],
            },
        )
    ]
    b.write("us-id", docs, index_url=index, index_document_count=1, note="IDAPA 35.01.01 PDF")


def build_la(b: Builder) -> None:
    index = "https://www.doa.la.gov/doa/osr/louisiana-administrative-code/"
    docs = [
        document(
            jurisdiction="us-la",
            source_id="la-osr-lac-61-i-chapter-13-income-individual",
            citation_path="us-la/regulation/lac/61/i/chapter-13",
            title="Louisiana Administrative Code Title 61, Part I, Chapter 13: Income: Individual",
            source_url="https://www.doa.la.gov/media/kwhdydi3/61v01.docx",
            source_format="docx",
            expression_date=SOURCE_AS_OF,
            authority="Louisiana Department of Revenue",
            publisher="Louisiana Division of Administration, Office of the State Register",
            subtype="administrative_code_chapter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "start_after_pattern": r"^Chapter 13\.\s*Income: Individual\s*$",
                "stop_text_pattern": r"^Chapter (?:1[4-9]|[2-9]\d)\.",
                "section_heading_pattern": r"^§(?P<label>13\d\d)\.\s*(?P<heading>.+)$",
            },
        )
    ]
    b.write("us-la", docs, index_url=index, index_document_count=1, note="LAC 61:I ch. 13 DOCX")


def build_mi(b: Builder) -> None:
    index = (
        "https://ars.apps.lara.state.mi.us/AdminCode/DeptBureauAdminCode?"
        "Department=Treasury&Bureau=All"
    )
    docs = [
        document(
            jurisdiction="us-mi",
            source_id="mi-ars-r-206-income-tax",
            citation_path="us-mi/regulation/r-206",
            title="Michigan Administrative Code R 206.1 to R 206.33: Income Tax (Department of Treasury)",
            source_url="https://ars.apps.lara.state.mi.us/AdminCode/DownloadAdminCodeFile?FileName=1613_2016-006TY_AdminCode.pdf",
            source_format="pdf",
            expression_date=SOURCE_AS_OF,
            authority="Michigan Department of Treasury",
            publisher="Michigan Office of Administrative Hearings and Rules (ARS)",
            subtype="administrative_code_rule_set",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_heading_pattern": r"^R (?P<label>206\.\d+)\s+(?P<heading>.+)$",
            },
        )
    ]
    b.write("us-mi", docs, index_url=index, index_document_count=1, note="R 206 PDF")


MN_CHAPTERS = {
    "8001": "Tax Definitions",
    "8002": "Individual Income Determination",
    "8007": "Accounting Methods; Taxable Year",
    "8038": "Returns",
    "8050": "Overpayments",
    "8092": "Withholding",
    "8093": "Estimated Tax",
}


def build_mn(b: Builder) -> None:
    index = "https://www.revisor.mn.gov/rules/agency/181"
    docs = []
    for chapter, title in MN_CHAPTERS.items():
        docs.append(
            document(
                jurisdiction="us-mn",
                source_id=f"mn-revisor-rules-{chapter}",
                citation_path=f"us-mn/regulation/minnesota-rules/{chapter}",
                title=f"Minnesota Rules Chapter {chapter}: {title} (Department of Revenue)",
                source_url=f"https://www.revisor.mn.gov/rules/{chapter}/full",
                source_format="html",
                expression_date=SOURCE_AS_OF,
                authority="Minnesota Department of Revenue",
                publisher="Minnesota Office of the Revisor of Statutes",
                subtype="administrative_code_chapter",
                index_url=index,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        rf"^(?P<label>{chapter}\.\d{{4}})\s+(?P<heading>[A-Z\[].+)$"
                    ),
                },
            )
        )
    b.write("us-mn", docs, index_url=index, index_document_count=43, note="MN Rules Revenue chapters")


def build_mo(b: Builder) -> None:
    index = "https://www.sos.mo.gov/adrules/csr/current/12csr/12csr"
    docs = [
        document(
            jurisdiction="us-mo",
            source_id="mo-sos-12-csr-10-2-income-tax",
            citation_path="us-mo/regulation/12-csr/10-2",
            title="Missouri Code of State Regulations 12 CSR 10-2: Income Tax (Director of Revenue)",
            source_url="https://www.sos.mo.gov/cmsimages/adrules/csr/current/12csr/12c10-2.pdf",
            source_format="pdf",
            expression_date="2026-03-31",
            authority="Missouri Department of Revenue",
            publisher="Missouri Secretary of State, Administrative Rules Division",
            subtype="administrative_code_chapter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_heading_pattern": r"^12 CSR 10-2\.(?P<num>\d{3})\s+(?P<heading>[A-Z].+)$",
                "section_label_template": "{num}",
                "start_page": 4,
                "drop_line_patterns": [
                    r"^12 CSR 10-2\.\d{3}\s*\t.*$",
                    r"^CODE OF STATE REGULATIONS$",
                    r"^\d{1,3}$",
                    r"^Denny Hoskins\s+\(\d+/\d+/\d+\)$",
                    r"^Secretary of State$",
                ],
            },
        )
    ]
    b.write("us-mo", docs, index_url=index, index_document_count=1, note="12 CSR 10-2 PDF")


def build_ms(b: Builder) -> None:
    index = "https://www.dor.ms.gov/forms-resources/mississippi-tax-laws-rules-and-regulations"
    docs = [
        document(
            jurisdiction="us-ms",
            source_id="ms-sos-title-35-part-iii-income-and-franchise-tax",
            citation_path="us-ms/regulation/title-35/part-iii",
            title="Mississippi Administrative Code Title 35, Part III: Income and Franchise Tax",
            source_url="https://www.sos.ms.gov/adminsearch/ACCode/00000158c.pdf",
            source_format="pdf",
            expression_date=SOURCE_AS_OF,
            authority="Mississippi Department of Revenue",
            publisher="Mississippi Secretary of State, Administrative Code",
            subtype="administrative_code_part",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_heading_pattern": (
                    r"^(?P<label>35\.III\.\d+\.\d+)\s+(?P<heading>Chapter \d+\..*)$"
                ),
                "section_label_pattern": r"^(?P<label>35\.III\.\d+\.\d+)\s*$",
                "label_only_heading_pattern": r"^Chapter \d+\..*$",
                "label_only_requires_heading": True,
                "drop_line_patterns": [r"^Page \d+ of \d+$"],
            },
        )
    ]
    b.write("us-ms", docs, index_url=index, index_document_count=1, note="Title 35 Part III PDF")


def build_nc(b: Builder) -> None:
    """17 NCAC Chapter 06 rule PDFs (one file per rule) from the OAH rules index."""

    index = (
        "http://reports.oah.state.nc.us/ncac.asp?folderName=%5CTitle%2017%20-%20Revenue"
        "%5CChapter%2006%20-%20Individual%20Income%20Tax"
    )
    page = soup(index)
    docs = []
    listed = 0
    for anchor in page.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        href = anchor["href"]
        match = re.match(r"^17 NCAC 06(?P<sub>[A-Z]) \.(?P<num>\d{4}(?:-\.\d{4})?)$", text)
        if not match or not href.lower().endswith(".pdf"):
            continue
        listed += 1
        sub = match.group("sub").lower()
        num = match.group("num").replace("-.", "-")
        docs.append(
            document(
                jurisdiction="us-nc",
                source_id=f"nc-oah-17-ncac-06{sub}-{num}",
                citation_path=f"us-nc/regulation/17-ncac/06/{sub}/{num}",
                title=f"{text} (17 NCAC Chapter 06, Individual Income Tax)",
                source_url=urljoin("http://reports.oah.state.nc.us/", href.replace(" ", "%20")),
                source_format="pdf",
                expression_date=SOURCE_AS_OF,
                authority="North Carolina Department of Revenue",
                publisher="North Carolina Office of Administrative Hearings, Rules Division",
                subtype="administrative_code_rule",
                index_url=index,
                extraction={"page_citation_prefix": "page"},
            )
        )
    b.write(
        "us-nc",
        docs,
        index_url=index,
        index_document_count=listed,
        note="one PDF per rule from the OAH chapter index (the consolidated and subchapter "
        "PDFs repeat every rule heading in a table of contents)",
    )


ND_CHAPTERS = {
    "81-03-01.1": "General Considerations",
    "81-03-02.1": "Income Tax on Individuals, Estates, Trusts, and Fiduciaries",
    "81-03-02.2": "Income Tax on Nonresident Individuals, Estates, Trusts, and Fiduciaries",
    "81-03-03.1": "Income Tax Withholding",
    "81-03-03.2": "New Jobs Credit from Withholding",
    "81-03-04": "Estimated Tax",
    "81-03-10": "Voluntary Contributions",
}


def build_nd(b: Builder) -> None:
    index = "https://ndlegis.gov/agency-rules/north-dakota-administrative-code"
    docs = []
    for chapter, title in ND_CHAPTERS.items():
        docs.append(
            document(
                jurisdiction="us-nd",
                source_id=f"nd-legis-ndac-{chapter}",
                citation_path=f"us-nd/regulation/ndac/{chapter}",
                title=f"North Dakota Administrative Code Chapter {chapter}: {title}",
                source_url=f"https://ndlegis.gov/information/acdata/pdf/{chapter}.pdf",
                source_format="pdf",
                expression_date=SOURCE_AS_OF,
                authority="North Dakota Office of State Tax Commissioner",
                publisher="North Dakota Legislative Council",
                subtype="administrative_code_chapter",
                index_url=index,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        rf"^(?P<label>{re.escape(chapter)}-\d{{2}}(?:\.\d)?)\.\s+(?P<heading>.+)$"
                    ),
                },
            )
        )
    b.write("us-nd", docs, index_url=index, index_document_count=25, note="NDAC art. 81-03 chapters")


def build_ne(b: Builder) -> None:
    index = "https://revenue.nebraska.gov/about/legal-information/regulations"
    docs = [
        document(
            jurisdiction="us-ne",
            source_id="ne-dor-regulations-chapter-22-individual-income-tax",
            citation_path="us-ne/regulation/revenue/chapter-22",
            title="Nebraska Department of Revenue Regulations, Chapter 22: Individual Income Tax",
            source_url=(
                "https://revenue.nebraska.gov/about/legal-information/regulations/"
                "chapter-22-individual-income-tax"
            ),
            source_format="html",
            expression_date=SOURCE_AS_OF,
            authority="Nebraska Department of Revenue",
            publisher="Nebraska Department of Revenue",
            subtype="agency_regulation_chapter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_heading_pattern": r"^REG-22-(?P<num>\d{3})\s+(?P<heading>.+)$",
                "section_label_template": "{num}",
            },
        )
    ]
    b.write("us-ne", docs, index_url=index, index_document_count=1, note="DOR chapter 22 HTML")


def build_ok(b: Builder) -> None:
    index = "https://rules.ok.gov/home"
    docs = [
        document(
            jurisdiction="us-ok",
            source_id="ok-oar-oac-710-50-income-tax",
            citation_path="us-ok/regulation/oac/710/50",
            title="Oklahoma Administrative Code Title 710, Chapter 50: Income (Oklahoma Tax Commission)",
            source_url=index,
            download_url=(
                "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=710&chapterNum=50"
            ),
            source_format="json",
            expression_date=SOURCE_AS_OF,
            authority="Oklahoma Tax Commission",
            publisher="Oklahoma Secretary of State, Office of Administrative Rules",
            subtype="administrative_code_chapter",
            index_url=index,
            extraction={
                "segmentation": "records",
                "json_record_text_field": "text",
                "json_record_text_is_html": True,
                "json_record_label_field": "sectionNum",
                "json_record_heading_field": "description",
                "json_record_kind_field": "name",
                "json_record_status_field": "statusName",
                "json_record_exclude_statuses": ["Revoked", "Reserved"],
                "json_record_metadata_fields": [
                    "id",
                    "parentId",
                    "name",
                    "titleNum",
                    "chapterNum",
                    "subChapterNum",
                    "partNum",
                    "sectionNum",
                    "appendixNum",
                    "description",
                    "statusName",
                    "effectiveDate",
                    "filingId",
                ],
            },
            extra_metadata={
                "rules_api_url": (
                    "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?"
                    "titleNum=710&chapterNum=50"
                ),
                "title_number": "710",
                "chapter_number": "50",
            },
        )
    ]
    b.write("us-ok", docs, index_url=index, index_document_count=1, note="OAC 710:50 JSON")


def build_sc(b: Builder) -> None:
    index = "https://www.scstatehouse.gov/coderegs/statmast.php"
    docs = [
        document(
            jurisdiction="us-sc",
            source_id="sc-legislature-code-regs-chapter-117-revenue",
            citation_path="us-sc/regulation/117",
            title="South Carolina Code of Regulations, Chapter 117: Department of Revenue",
            source_url="https://www.scstatehouse.gov/coderegs/Chapter%20117.pdf",
            source_format="pdf",
            expression_date=SOURCE_AS_OF,
            authority="South Carolina Department of Revenue",
            publisher="South Carolina Legislative Services Agency",
            subtype="code_of_regulations_chapter",
            index_url=index,
            extraction={
                "segmentation": "labeled_sections",
                "section_heading_pattern": (
                    r"^117[–-](?P<num>\d+(?:\.\d+)*)\.\s+(?P<heading>[A-Z].+)$"
                ),
                "section_label_template": "{num}",
            },
        )
    ]
    b.write("us-sc", docs, index_url=index, index_document_count=1, note="Chapter 117 PDF")


def build_vt(b: Builder) -> None:
    index = "https://tax.vermont.gov/research-and-reports/legal-library/regulations"
    specs = [
        (
            "reg-1-5811-21-b-ii-capital-gains-exclusion",
            "Vermont Department of Taxes Regulation § 1.5811(21)(B)(ii): Capital Gains Exclusion",
            "https://tax.vermont.gov/sites/tax/files/documents/Capital%20Gains%20Exclusion%20Reg%20section%201.5811%2821%29%28B%29%28ii%29.pdf",
            "2014-03-11",
        ),
        (
            "reg-1-5811-11-a-i-domicile",
            "Vermont Department of Taxes Regulation § 1.5811(11)(A)(i): Domicile",
            "https://tax.vermont.gov/sites/tax/files/documents/15811.pdf",
            "2004-08-06",
        ),
    ]
    docs = []
    for slug, title, url, effective in specs:
        docs.append(
            document(
                jurisdiction="us-vt",
                source_id=f"vt-tax-{slug}",
                citation_path=f"us-vt/regulation/tax/{slug}",
                title=title,
                source_url=url,
                source_format="pdf",
                expression_date=effective,
                authority="Vermont Department of Taxes",
                publisher="Vermont Department of Taxes",
                subtype="agency_regulation",
                index_url=index,
                extraction={"page_citation_prefix": "page"},
            )
        )
    b.write("us-vt", docs, index_url=index, index_document_count=17, note="income tax regulation PDFs")


def build_wi(b: Builder) -> None:
    index = "https://docs.legis.wisconsin.gov/code/admin_code/tax"
    specs = [
        ("2", "Income Taxation, Returns, Records and Gross Income"),
        ("3", "Income Taxation, Deductions from Gross Income, Exclusions and Exemptions"),
    ]
    docs = []
    for chapter, title in specs:
        docs.append(
            document(
                jurisdiction="us-wi",
                source_id=f"wi-legis-tax-{chapter}",
                citation_path=f"us-wi/regulation/tax/{chapter}",
                title=f"Wisconsin Administrative Code Chapter Tax {chapter}: {title}",
                source_url=f"https://docs.legis.wisconsin.gov/code/admin_code/tax/{chapter}.pdf",
                source_format="pdf",
                expression_date=SOURCE_AS_OF,
                authority="Wisconsin Department of Revenue",
                publisher="Wisconsin Legislative Reference Bureau",
                subtype="administrative_code_chapter",
                index_url=index,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        rf"^Tax (?P<label>{chapter}\.\d+)\s+(?P<heading>[A-Z].+)$"
                    ),
                    "drop_line_patterns": [
                        r"^Published under s\. 35\.93, Wis\. Stats\., by the Legislative Reference Bureau\.$",
                        r"^Tax \d+\.\d+$",
                        r"^\d{1,3}$",
                        r"^DEPARTMENT OF REVENUE$",
                        r"^Register .* No\. \d+$",
                    ],
                },
            )
        )
    b.write("us-wi", docs, index_url=index, index_document_count=22, note="Tax 2 and Tax 3 PDFs")


WV_RULES = [
    ("110-21", "Personal Income Tax", 21111, "1990-04-02"),
    ("110-21A", "Personal Income Tax Low Income Exclusion", 21132, "1997-06-01"),
    ("110-21B", "Citizen Tax Credit for Property Taxes Paid", 57149, "2024-04-30"),
    (
        "110-21C",
        "Method of Claiming the Qualified Rehabilitated Buildings Investment Credit",
        50936,
        "2018-12-31",
    ),
    ("110-21G", "Income Tax Paid at the Entity Level by Electing Pass-Through Entities", 57151, "2024-04-30"),
    ("110-21H", "Income Tax Credits for Property Taxes Paid", 58905, "2026-04-28"),
]


def build_wv(b: Builder) -> None:
    index = "https://apps.sos.wv.gov/adlaw/csr/rule.aspx?rule=110-21"
    docs = []
    for series, title, doc_id, effective in WV_RULES:
        docs.append(
            document(
                jurisdiction="us-wv",
                source_id=f"wv-sos-csr-{series.lower()}",
                citation_path=f"us-wv/regulation/110-csr/{series[4:].lower()}",
                title=f"West Virginia Code of State Rules {series}: {title}",
                source_url=f"https://apps.sos.wv.gov/adlaw/csr/readfile.aspx?DocId={doc_id}&Format=PDF",
                source_format="pdf",
                expression_date=effective,
                authority="West Virginia Tax Division",
                publisher="West Virginia Secretary of State, Code of State Rules",
                subtype="code_of_state_rules_series",
                index_url=index,
                extraction={"ocr": True, "page_citation_prefix": "page"},
                extra_metadata={"csr_series": series, "sos_document_id": doc_id},
            )
        )
    b.write("us-wv", docs, index_url=index, index_document_count=6, note="110 CSR 21 series PDFs (OCR)")


# --------------------------------------------------------------------------------------
# Discovered publishers
# --------------------------------------------------------------------------------------


def build_al(b: Builder) -> None:
    """Alabama Administrative Code rule PDFs 810-3-N-.NN (Department of Revenue, income tax)."""

    index = "https://admincode.legislature.state.al.us/administrative-code/810-3"
    chapters: list[int] = []
    for number in range(1, 251):
        url = f"https://admincode.legislature.state.al.us/api/chapter/810-3-{number}"
        response = _session.head(url, timeout=60, allow_redirects=True)
        if response.status_code == 200:
            chapters.append(number)
    docs = []
    listed = 0
    for number in chapters:
        import fitz

        chapter_pdf = fetch(f"https://admincode.legislature.state.al.us/api/chapter/810-3-{number}")
        with fitz.open(stream=chapter_pdf, filetype="pdf") as pdf:
            text = "\n".join(page.get_text() for page in pdf)
        rules: list[str] = []
        for line in text.splitlines():
            match = re.match(rf"^\s*810-3-{number}-\.(?P<sec>\d+)\s*$", line)
            if match and match.group("sec") not in rules:
                rules.append(match.group("sec"))
        for sec in rules:
            rule_id = f"810-3-{number}-.{sec}"
            listed += 1
            docs.append(
                document(
                    jurisdiction="us-al",
                    source_id=f"al-admin-code-{rule_id.replace('.', '')}",
                    citation_path=f"us-al/regulation/alabama-administrative-code/810/3/{number}/{sec}",
                    title=f"Alabama Administrative Code Rule {rule_id} (Department of Revenue, Income Tax)",
                    source_url=f"https://admincode.legislature.state.al.us/api/rule/{rule_id}",
                    source_format="pdf",
                    expression_date=SOURCE_AS_OF,
                    authority="Alabama Department of Revenue",
                    publisher="Alabama Legislative Services Agency, Administrative Code",
                    subtype="administrative_code_rule",
                    index_url=index,
                    request={"browser_user_agent": True},
                    extraction={"page_citation_prefix": "page"},
                    extra_metadata={"chapter": f"810-3-{number}"},
                )
            )
    b.write(
        "us-al",
        docs,
        index_url=index,
        index_document_count=listed,
        note="one PDF per rule from the LSA API (/api/rule/<id>); rule ids come from the "
        "tables of contents of the 810-3 chapter PDFs (/api/chapter/810-3-<n>, n = 1..250 "
        "probed), because the chapter index is a JavaScript application backed by "
        "persisted GraphQL queries",
    )


def build_ca(b: Builder) -> None:
    """18 CCR Division 3 Chapter 2.5 section documents from the OAL/Westlaw CCR site."""

    base = "https://govt.westlaw.com"
    root = (
        "/calregs/Browse/Home/California/CaliforniaCodeofRegulations?"
        "guid=IEB2CC7D04C8311EC89E5000D3A7C4BC3&originationContext=documenttoc"
        "&transitionType=Default&contextData=(sc.Default)"
    )
    sections: list[tuple[list[str], str, str]] = []
    seen: set[str] = set()

    def walk(href: str, path: list[str]) -> None:
        if href in seen:
            return
        seen.add(href)
        page = BeautifulSoup(fetch(base + href, delay=0.7), "html.parser")
        for anchor in page.find_all("a", href=True):
            text = anchor.get_text(" ", strip=True)
            link = anchor["href"]
            if "/calregs/Document/" in link:
                sections.append((path, text, link.split("?")[0]))
            elif (
                "guid=" in link
                and re.match(r"(Subchapter|Article)\s", text)
                and link not in seen
                and text not in path
            ):
                walk(link, path + [text])

    walk(root, [])
    docs = []
    for path, text, link in sections:
        if re.search(r"\[(Repealed|Renumbered|Reserved)", text) or "Refs & Annos" in text:
            continue
        match = re.match(
            r"§\s*(?P<num>[0-9.]+[a-z]?)\.?\s*(?:[–-]\s*(?P<sub>\d+)\.)?\s*(?P<heading>.*)$", text
        )
        if not match:
            continue
        number = match.group("num").rstrip(".")
        if match.group("sub"):
            number = f"{number}-{match.group('sub')}"
        docs.append(
            document(
                jurisdiction="us-ca",
                source_id=f"ca-ccr-18-{number}",
                citation_path=f"us-ca/regulation/18-ccr/{number}",
                title=f"18 CCR § {number}. {match.group('heading')}",
                source_url=base + link + "?viewType=FullText&originationContext=documenttoc"
                "&transitionType=CategoryPageItem&contextData=(sc.Default)",
                source_format="html",
                expression_date=SOURCE_AS_OF,
                authority="California Franchise Tax Board",
                publisher="California Office of Administrative Law (CCR via govt.westlaw.com)",
                subtype="administrative_code_section",
                index_url=base + root,
                request={"fresh_session": True, "cookies": {"bhCookieSess": "1", "bhCookiePerm": "1"}},
                extraction={
                    "html_content_selector": "#co_document",
                    "html_text_selector": "h1, h2, h3, .co_headtext, .co_paragraph, p, li, table",
                },
                extra_metadata={"ccr_toc_path": " > ".join(path)},
            )
        )
    b.write(
        "us-ca",
        docs,
        index_url=base + root,
        index_document_count=len(sections),
        note="section documents of 18 CCR div. 3 ch. 2.5; repealed, renumbered and "
        "reserved section stubs and the Refs & Annos page are not taken",
    )


def build_ks(b: Builder) -> None:
    """K.A.R. Article 92-12 (Income Tax) from the Secretary of State's rules.ks.gov API."""

    api = "https://rules.ks.gov/api/policy-library-public"
    collections = json.loads(fetch(f"{api}/collections"))["collections"]
    kar = next(c for c in collections if c["name"] == "Kansas Administrative Regulations")
    tree = json.loads(fetch(f"{api}/collections/{kar['uuid']}/tree"))
    article_uuid = None

    def walk(node: dict[str, Any], parent: dict[str, Any] | None) -> None:
        nonlocal article_uuid
        if (
            parent is not None
            and parent.get("sectionId") == "92"
            and node.get("sectionType") == "Article"
            and node.get("sectionId") == "12"
        ):
            article_uuid = node["uuid"]
        for child in node.get("childFolders", []):
            walk(child, node)

    walk(tree, None)
    if article_uuid is None:
        raise RuntimeError("K.A.R. article 92-12 not found in rules.ks.gov tree")
    article = json.loads(fetch(f"{api}/collections/{kar['uuid']}/sections/{article_uuid}"))
    policies = article.get("childPolicies", [])
    docs = []
    for policy in policies:
        if policy.get("effectiveStatus") != "EFFECTIVE":
            continue
        detail = json.loads(fetch(f"{api}/collections/{kar['uuid']}/policies/{policy['uuid']}"))
        policy_detail = detail.get("policy") or detail
        versions = policy_detail.get("policyVersions") or []
        current_uuid = policy_detail.get("currentVersionUuid")
        current = next((v for v in versions if v.get("uuid") == current_uuid), None) or (
            versions[0] if versions else None
        )
        if current is None:
            continue
        html_doc = current.get("accessibleHtmlDocument") or {}
        content_url = html_doc.get("contentUrl")
        if not content_url:
            continue
        section_id = policy["sectionId"]
        fields = {f["key"]: f.get("value") for f in policy.get("policyFields", [])}
        number = section_id.split("-")[-1]
        docs.append(
            document(
                jurisdiction="us-ks",
                source_id=f"ks-kar-{section_id}",
                citation_path=f"us-ks/regulation/kar/92/12/{number}",
                title=f"K.A.R. {section_id}. {policy.get('name') or ''}".strip(),
                source_url=urljoin("https://rules.ks.gov", content_url),
                source_format="html",
                expression_date=(fields.get("effective_start_date") or SOURCE_AS_OF)[:10],
                authority="Kansas Department of Revenue",
                publisher="Kansas Secretary of State, Kansas Administrative Regulations (rules.ks.gov)",
                subtype="administrative_regulation",
                index_url="https://rules.ks.gov/",
                extra_metadata={
                    "kar_policy_uuid": policy["uuid"],
                    "kar_version_uuid": current.get("uuid"),
                    "kar_api_section_url": f"{api}/collections/{kar['uuid']}/sections/{article_uuid}",
                },
            )
        )
    b.write(
        "us-ks",
        docs,
        index_url=f"{api}/collections/{kar['uuid']}/sections/{article_uuid}",
        index_document_count=len(policies),
        note="effective regulations of K.A.R. article 92-12; revoked numbers are listed "
        "by the publisher but carry no text and are not taken",
    )


KY_CHAPTERS = {
    "015": "Income Tax; General Administration",
    "017": "Income Tax; Individual",
    "018": "Income Tax; Withholding",
    "019": "Income Tax; Miscellaneous",
}


def build_ky(b: Builder) -> None:
    index = "https://apps.legislature.ky.gov/law/kar/titles/103/"
    docs = []
    listed = 0
    for chapter, chapter_title in KY_CHAPTERS.items():
        page = soup(f"{index}{chapter}/")
        for anchor in page.find_all("a", href=True):
            href = anchor["href"]
            match = re.search(rf"/law/kar/titles/103/{chapter}/(\d+)/", href)
            if not match:
                continue
            listed += 1
            text = anchor.get_text(" ", strip=True)
            if not text.endswith("Current"):
                continue
            number = match.group(1)
            title = re.sub(r"^Regulation \d+\s+[—-]\s+", "", text)[: -len("Current")].strip()
            page_url = f"https://apps.legislature.ky.gov{href}"
            regulation_page = soup(page_url)
            pdf = next(
                (
                    a["href"]
                    for a in regulation_page.find_all("a", href=True)
                    if "/law/kar/downloads/" in a["href"] and a["href"].endswith(".pdf")
                ),
                None,
            )
            if pdf is None:
                continue
            docs.append(
                document(
                    jurisdiction="us-ky",
                    source_id=f"ky-lrc-103-kar-{chapter}-{number}",
                    citation_path=f"us-ky/regulation/kar/103/{chapter}/{number}",
                    title=f"103 KAR {int(chapter)}:{number}. {title}",
                    source_url=page_url,
                    download_url=urljoin("https://apps.legislature.ky.gov/", pdf),
                    source_format="pdf",
                    expression_date=SOURCE_AS_OF,
                    authority="Kentucky Department of Revenue",
                    publisher="Kentucky Legislative Research Commission",
                    subtype="administrative_regulation",
                    index_url=index,
                    extraction={
                        "segmentation": "labeled_sections",
                        "section_heading_pattern": r"^Section (?P<num>\d+)\.\s+(?P<heading>[A-Z].*)$",
                        "section_label_pattern": r"^Section (?P<num>\d+)\.\s*$",
                        "section_label_template": "section-{num}",
                        "label_only_heading_pattern": r"^[A-Z].+$",
                        "label_only_requires_heading": True,
                    },
                    extra_metadata={"kar_chapter": chapter, "kar_chapter_title": chapter_title},
                )
            )
    b.write(
        "us-ky",
        docs,
        index_url=index,
        index_document_count=listed,
        note="current regulations of 103 KAR chapters 15, 17, 18 and 19 (chapter 16 is "
        "corporation income tax); expired, repealed and withdrawn numbers are not taken",
    )


MA_UNNUMBERED_REGULATIONS = {"62.6.1", "62.17A.2"}


def build_ma(b: Builder) -> None:
    index = "https://www.mass.gov/lists/dor-regulations"
    page = soup(index)
    docs = []
    listed = 0
    seen: set[str] = set()
    for anchor in page.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        match = re.match(r"^830 CMR (?P<reg>62B?\.[0-9A-Z.]+):\s*(?P<title>.+)$", text)
        if not match:
            continue
        listed += 1
        title = match.group("title")
        if re.search(r"Reg Fact Sheet|WORKING DRAFT|PROPOSED|Working Draft|Repealed|EMERGENCY", title, re.I):
            continue
        reg = match.group("reg")
        if reg in seen:
            continue
        seen.add(reg)
        href = anchor["href"]
        docs.append(
            document(
                jurisdiction="us-ma",
                source_id=f"ma-dor-830-cmr-{reg.lower().replace('.', '-')}",
                citation_path=f"us-ma/regulation/830-cmr/{reg.lower()}",
                title=f"830 CMR {reg}: {title}",
                source_url=urljoin("https://www.mass.gov/", href),
                source_format="html",
                expression_date=SOURCE_AS_OF,
                authority="Massachusetts Department of Revenue",
                publisher="Massachusetts Department of Revenue (mass.gov regulations)",
                subtype="administrative_regulation",
                index_url=index,
                request={"browser_impersonation": True},
                extraction=(
                    {"html_content_selector": "main"}
                    if reg in MA_UNNUMBERED_REGULATIONS
                    else {
                        "html_content_selector": "main",
                        "segmentation": "labeled_sections",
                        "section_heading_pattern": (
                            r"^\((?P<num>\d+)\)\s+(?P<heading>[A-Z][A-Za-z0-9 ,'/():-]{2,100})$"
                        ),
                        "section_label_template": "{num}",
                    }
                ),
            )
        )
    b.write(
        "us-ma",
        docs,
        index_url=index,
        index_document_count=listed,
        note="830 CMR 62.x and 62B.x regulations; fact sheets, working drafts, proposed and "
        "emergency versions are not taken",
    )


ME_INDIVIDUAL_RULES = {"803", "805", "806", "807", "811", "812", "813", "825"}


def build_me(b: Builder) -> None:
    index = "https://www.maine.gov/revenue/publications/rules"
    page = soup(index)
    docs = []
    listed = 0
    seen: set[str] = set()
    for anchor in page.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        match = re.match(r"^(?P<num>\d{3}) (?P<title>.+?) \(PDF\)$", text)
        href = anchor["href"]
        if not match or "Proposed" in href:
            continue
        listed += 1
        number = match.group("num")
        if number not in ME_INDIVIDUAL_RULES or number in seen:
            continue
        seen.add(number)
        docs.append(
            document(
                jurisdiction="us-me",
                source_id=f"me-mrs-rule-{number}",
                citation_path=f"us-me/regulation/18-125-cmr/{number}",
                title=f"18-125 CMR Chapter {number}: {match.group('title')} (Maine Revenue Services)",
                source_url=urljoin("https://www.maine.gov/", href),
                source_format="pdf",
                expression_date=SOURCE_AS_OF,
                authority="Maine Revenue Services",
                publisher="Maine Revenue Services",
                subtype="agency_rule_chapter",
                index_url=index,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": r"^\.(?P<num>\d{2})\s+(?P<heading>[A-Z].+)$",
                    "section_label_pattern": r"^\.(?P<num>\d{2})\s*$",
                    "label_only_heading_pattern": r"^[A-Z].+$",
                    "label_only_requires_heading": True,
                    "section_label_template": "{num}",
                    "section_heading_requires_bold": True,
                },
            )
        )
    b.write(
        "us-me",
        docs,
        index_url=index,
        index_document_count=listed,
        note="individual income tax rules of 18-125 CMR chapter 8xx (withholding, composite, "
        "nonresident, residency, credits, tribal income); corporate rules 801, 808, 810, "
        "815-818 and the proposed July 2026 drafts are not taken",
    )


def build_nm(b: Builder) -> None:
    index = (
        "https://www.srca.nm.gov/nmac-home/nmac-titles/title-3-taxation/"
        "chapter-3-personal-income-taxes/"
    )
    docs = []
    found = 0
    for part in range(1, 60):
        url = f"https://www.srca.nm.gov/parts/title03/03.003.{part:04d}.html"
        response = _session.get(url, timeout=60)
        if response.status_code != 200 or b"NMAC" not in response.content[:8000]:
            continue
        found += 1
        text = BeautifulSoup(response.content, "html.parser").get_text(" ", strip=True)
        if re.search(r"\[This part expired", text[:600]):
            continue
        match = re.search(r"PART\s+\d+:?\s+(?P<title>[A-Z][A-Z0-9 ,;()'&\-]+?)\s+3\.3\.\d+\.1\b", text)
        title = match.group("title").title() if match else f"Part {part}"
        docs.append(
            document(
                jurisdiction="us-nm",
                source_id=f"nm-srca-nmac-3-3-{part}",
                citation_path=f"us-nm/regulation/nmac/3/3/{part}",
                title=f"3.3.{part} NMAC: {title}",
                source_url=url,
                source_format="html",
                expression_date=SOURCE_AS_OF,
                authority="New Mexico Taxation and Revenue Department",
                publisher="New Mexico Commission of Public Records, State Records Center and Archives",
                subtype="administrative_code_part",
                index_url=index,
                extraction={
                    "html_content_selector": ".WordSection1, .Section1, body",
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        rf"^(?P<label>3\s*\.\s*3\s*\.\s*{part}\s*\.\s*(?P<num>\d+(?:\s*-\s*\d+)?))\s+"
                        r"(?P<heading>[A-Z][^:]{0,180}:|\[RESERVED\]|[A-Z][A-Z0-9 /()\[\]\-–—,'&]{0,180})"
                        r"(?:\s+(?P<body>.*))?$"
                    ),
                    "section_label_template": f"3.3.{part}.{{num}}",
                    "normalize_label_internal_whitespace": True,
                },
            )
        )
    b.write(
        "us-nm",
        docs,
        index_url=index,
        index_document_count=found,
        note="every published part of 3.3 NMAC (chapter index page is script-rendered; "
        "parts enumerated by probing 03.003.NNNN.html for NNNN = 1..59)",
    )


def build_ny(b: Builder) -> None:
    """20 NYCRR Chapter II Subchapter A parts as an extract-nycrr-parts manifest."""

    base = "https://govt.westlaw.com"
    index = base + "/nycrr/Index?transitionType=Default&contextData=(sc.Default)"
    page = soup(index)
    title_20 = next(
        a["href"] for a in page.find_all("a", href=True) if a.get_text(" ", strip=True).startswith("Title 20")
    )

    def browse(href: str, pattern: str) -> list[tuple[str, str]]:
        page = soup(base + href, delay=0.7)
        return [
            (a.get_text(" ", strip=True), a["href"])
            for a in page.find_all("a", href=True)
            if "guid=" in a["href"] and re.match(pattern, a.get_text(" ", strip=True))
        ]

    chapter_ii = next(h for t, h in browse(title_20, r"Chapter") if t.startswith("Chapter II"))
    subchapter_a = next(h for t, h in browse(chapter_ii, r"Subchapter") if t.startswith("Subchapter A"))
    parts: list[dict[str, Any]] = []
    listed = 0
    for article_title, article_href in browse(subchapter_a, r"Article"):
        for text, href in browse(article_href, r"Part"):
            listed += 1
            match = re.match(r"^Part (?P<num>\d+)\s*(?P<title>.*)$", text)
            if not match or "(Repealed)" in text:
                continue
            parts.append(
                {
                    "part": match.group("num"),
                    "citation_path": f"us-ny/regulation/20-nycrr/{match.group('num')}",
                    "title": match.group("title").strip(),
                    "source_url": base + href,
                    "metadata": {
                        "document_subtype": "administrative_code_part",
                        "official_title": f"20 NYCRR Part {match.group('num')}",
                        "nycrr_article": article_title,
                        "source_discovery_group": "us-ny/regulation/income-tax",
                        "discovered_via": f"{DISCOVERED_VIA}; index {index}",
                    },
                }
            )
    path = MANIFEST_DIR / "us-ny-income-tax-regulations.yaml"
    path.write_text(yaml.safe_dump({"parts": parts}, sort_keys=False, allow_unicode=True, width=110))
    b.summary["us-ny"] = {
        "manifest": str(path.relative_to(REPO_ROOT)),
        "index_url": index,
        "index_document_count": listed,
        "taken_count": len(parts),
        "note": "20 NYCRR Chapter II Subchapter A (Article 22 personal income tax) parts; "
        "repealed part numbers are not taken",
    }
    print(f"us-ny: {len(parts)} parts -> {path.name}", file=sys.stderr)


def build_ri(b: Builder) -> None:
    index = "https://rules.sos.ri.gov/Organizations/SubChapter/280-20-55"
    page = soup(index)
    docs = []
    parts: list[tuple[str, str]] = []
    for anchor in page.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        href = anchor["href"]
        if "/regulations/Part/" in href and not text.startswith("Part"):
            parts.append((text, href))
    for text, href in parts:
        match = re.match(r"^(?P<title>.+?)\s*\((?P<cite>280-RICR-20-55-(?P<num>\d+))\)$", text)
        if not match:
            continue
        detail = soup(href)
        pdf = next(
            (a["href"] for a in detail.find_all("a", href=True) if "amazonaws" in a["href"]),
            None,
        )
        if pdf is None:
            continue
        number = match.group("num")
        docs.append(
            document(
                jurisdiction="us-ri",
                source_id=f"ri-sos-280-ricr-20-55-{number}",
                citation_path=f"us-ri/regulation/280-ricr/20/55/{number}",
                title=f"{match.group('cite')}: {match.group('title')}",
                source_url=href,
                download_url=pdf,
                source_format="pdf",
                expression_date=SOURCE_AS_OF,
                authority="Rhode Island Department of Revenue, Division of Taxation",
                publisher="Rhode Island Department of State, Rhode Island Code of Regulations",
                subtype="administrative_code_part",
                index_url=index,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        rf"^(?P<label>{number}\.\d+)\s+(?P<heading>[A-Z].+)$"
                    ),
                    "section_label_pattern": rf"^(?P<label>{number}\.\d+)\s*$",
                    "label_only_heading_pattern": r"^[A-Z].+$",
                    "label_only_requires_heading": True,
                },
            )
        )
    b.write(
        "us-ri",
        docs,
        index_url=index,
        index_document_count=len(parts),
        note="280-RICR-20-55 Personal Income Tax parts (part pages link the published PDF)",
    )


def build_in(b: Builder) -> None:
    index = "https://iar.iga.in.gov/code/2026/45"
    api = (
        "https://drxya2s1hkmtl.cloudfront.net/api/adminCodeArticle?"
        "doc_stage=public&edition_year=2026&title_num=45&article_num=3.1"
    )
    docs = [
        document(
            jurisdiction="us-in",
            source_id="in-iar-45-iac-3-1-adjusted-gross-income-tax",
            citation_path="us-in/regulation/iac/45/3.1",
            title="45 IAC Article 3.1: Adjusted Gross Income Tax (Department of State Revenue)",
            source_url=index + "/3.1",
            download_url=api,
            source_format="json",
            expression_date=SOURCE_AS_OF,
            authority="Indiana Department of State Revenue",
            publisher="Indiana General Assembly, Indiana Administrative Rules and Policies (iar.iga.in.gov)",
            subtype="administrative_code_article",
            index_url=index,
            request={"browser_impersonation": True, "browser_impersonation_direct": True},
            extraction={
                "json_html_field": "iar_iac_article_doc.doc_html",
                "html_drop_selectors": ["ol.toc"],
                "html_text_selector": "h1, h2, h3, div.subsection, div.emphasize, p, li, table",
                "segmentation": "labeled_sections",
                "section_heading_pattern": r"^45 IAC 3\.1-(?P<label>\d+-\d+(?:\.\d+)?)\s+(?P<heading>.+)$",
            },
            extra_metadata={
                "access_note": "iar.iga.in.gov is a JavaScript application; its article text is "
                "served by the General Assembly's own API distribution "
                "(drxya2s1hkmtl.cloudfront.net/api, referenced from the site's bundle), which "
                "answers the plain client with a CloudFront 403 and the browser-impersonation "
                "fetch with the article JSON.",
            },
        )
    ]
    b.write("us-in", docs, index_url=index, index_document_count=1, note="45 IAC 3.1 JSON article")


def build_ar(b: Builder) -> None:
    index = "https://www.dfa.arkansas.gov/office/policy-legal/rules/"
    page = soup(index)
    docs = []
    listed = 0
    for anchor in page.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        href = anchor["href"]
        if not href.lower().endswith(".pdf"):
            continue
        listed += 1
        if not re.search(r"individual income tax", text, re.I):
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
        docs.append(
            document(
                jurisdiction="us-ar",
                source_id=f"ar-dfa-{slug}",
                citation_path=f"us-ar/regulation/dfa/{slug}",
                title=f"Arkansas DFA rule: {text}",
                source_url=urljoin(index, href),
                source_format="pdf",
                expression_date=SOURCE_AS_OF,
                authority="Arkansas Department of Finance and Administration",
                publisher="Arkansas Department of Finance and Administration",
                subtype="agency_rule",
                index_url=index,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        r"^(?P<label>\d\.26-5[01]-\d+(?:\([a-z0-9]+\))*)\s+(?P<heading>.+)$"
                    ),
                },
            )
        )
    b.write(
        "us-ar",
        docs,
        index_url=index,
        index_document_count=listed,
        note="DFA rules page PDFs named individual income tax",
    )


# --------------------------------------------------------------------------------------
# Pointer manifests for jurisdictions extracted with dedicated adapters
# --------------------------------------------------------------------------------------


ADAPTER_POINTERS: dict[str, dict[str, Any]] = {
    "us-il": {
        "source_id": "il-jcar-86-ill-adm-code-100-income-tax",
        "citation_path": "us-il/regulation/title-86/part-100",
        "title": "86 Ill. Adm. Code Part 100: Income Tax (Department of Revenue)",
        "source_url": "https://www.ilga.gov/ftp/JCAR/AdminCode/086/086001000sections.html",
        "authority": "Illinois Department of Revenue",
        "publisher": "Illinois General Assembly, Joint Committee on Administrative Rules",
        "extractor": "extract-illinois-admin-code --only-title 86 --only-part 100",
        "index_url": "https://www.ilga.gov/ftp/JCAR/AdminCode/086/",
    },
    "us-md": {
        "source_id": "md-dsd-comar-03-04-income-tax",
        "citation_path": "us-md/regulation/title-03/subtitle-04",
        "title": "COMAR Title 03 Comptroller of the Treasury, Subtitle 04 Income Tax",
        "source_url": "https://regs.maryland.gov",
        "authority": "Maryland Comptroller of the Treasury",
        "publisher": "Maryland Division of State Documents (COMAR XML publication)",
        "extractor": "extract-maryland-comar --only-title 03 --only-subtitle 04",
        "index_url": "https://github.com/maryland-dsd/law-xml-codified (us/md/exec/comar/03/04)",
    },
    "us-mt": {
        "source_id": "mt-sos-arm-42-15-income-tax",
        "citation_path": "us-mt/regulation/title-42/chapter-42-15",
        "title": "Administrative Rules of Montana Title 42 (Department of Revenue), Chapter 15 Income Tax",
        "source_url": "https://rules.mt.gov/",
        "authority": "Montana Department of Revenue",
        "publisher": "Montana Secretary of State, Administrative Rules of Montana",
        "extractor": "extract-montana-admin-rules --only-title 42 --only-section 42.15",
        "index_url": "https://rules.mt.gov/api/policy-library-public/collections",
    },
    "us-oh": {
        "source_id": "oh-oac-5703-7-income-tax",
        "citation_path": "us-oh/regulation/agency-5703/chapter-5703-7",
        "title": "Ohio Administrative Code Chapter 5703-7: Income Tax (Department of Taxation)",
        "source_url": "https://codes.ohio.gov/ohio-administrative-code/chapter-5703-7",
        "authority": "Ohio Department of Taxation",
        "publisher": "Ohio Laws and Administrative Rules (codes.ohio.gov)",
        "extractor": "extract-ohio-administrative-code --only-agency 5703 --only-chapter 5703-7",
        "index_url": "https://codes.ohio.gov/ohio-administrative-code/5703",
    },
    "us-or": {
        "source_id": "or-oard-oar-150-316-personal-income-tax",
        "citation_path": "us-or/regulation/chapter-150/division-316",
        "title": "Oregon Administrative Rules Chapter 150 (Department of Revenue), Division 316 "
        "Personal Income Tax General Provisions",
        "source_url": "https://secure.sos.state.or.us/oard/displayDivisionRules.action?selectedDivision=2098",
        "authority": "Oregon Department of Revenue",
        "publisher": "Oregon Secretary of State, Administrative Rules (OARD)",
        "extractor": "extract-oregon-administrative-rules --only-chapter 150 --only-division 316",
        "index_url": "https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=61",
    },
    "us-pa": {
        "source_id": "pa-pacode-61-article-v-personal-income-tax",
        "citation_path": "us-pa/regulation/title-61",
        "title": "61 Pa. Code Part I Subpart B Article V: Personal Income Tax (chapters 101-125)",
        "source_url": "https://www.pacodeandbulletin.gov/Display/pacode?file=/secure/pacode/data/061/061toc.html",
        "authority": "Pennsylvania Department of Revenue",
        "publisher": "Pennsylvania Legislative Reference Bureau (pacodeandbulletin.gov)",
        "extractor": "extract-pennsylvania-code --only-title 61 --only-chapter "
        "101,103,105,107,109,111,113,115,117,119,121,123,125",
        "index_url": "https://www.pacodeandbulletin.gov/Display/pacode?file=/secure/pacode/data/061/061toc.html",
    },
    "us-va": {
        "source_id": "va-vac-23-10-110-individual-income-tax",
        "citation_path": "us-va/regulation/title-23/agency-10",
        "title": "23VAC10-110 Individual Income Tax and 23VAC10-140 Income Tax Withholding "
        "(Department of Taxation)",
        "source_url": "https://law.lis.virginia.gov/admincode/title23/agency10/",
        "authority": "Virginia Department of Taxation",
        "publisher": "Virginia Law Portal (law.lis.virginia.gov), Virginia Administrative Code",
        "extractor": "extract-virginia-vac --only-title 23 --only-agency 10 --only-chapter 110,140",
        "index_url": "https://law.lis.virginia.gov/admincode/title23/agency10/",
    },
}


def build_pointers(b: Builder, only: set[str] | None) -> None:
    for jurisdiction, spec in ADAPTER_POINTERS.items():
        if only and jurisdiction not in only:
            continue
        entry = document(
            jurisdiction=jurisdiction,
            source_id=spec["source_id"],
            citation_path=spec["citation_path"],
            title=spec["title"],
            source_url=spec["source_url"],
            source_format="html",
            expression_date=SOURCE_AS_OF,
            authority=spec["authority"],
            publisher=spec["publisher"],
            subtype="administrative_code_chapter",
            index_url=spec["index_url"],
            extra_metadata={
                "extractor": f"uv run axiom-corpus-ingest {spec['extractor']}",
                "pointer_manifest": True,
            },
        )
        path = MANIFEST_DIR / f"{jurisdiction}-income-tax-regulations.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "version": SOURCE_AS_OF,
                    "extractor": spec["extractor"],
                    "documents": [entry],
                },
                sort_keys=False,
                allow_unicode=True,
                width=110,
            )
        )
        print(f"{jurisdiction}: pointer manifest -> {path.name}", file=sys.stderr)


BUILDERS = {
    "us-al": build_al,
    "us-ar": build_ar,
    "us-az": build_az,
    "us-ca": build_ca,
    "us-co": build_co,
    "us-ct": build_ct,
    "us-ga": build_ga,
    "us-hi": build_hi,
    "us-ia": build_ia,
    "us-id": build_id,
    "us-in": build_in,
    "us-ks": build_ks,
    "us-ky": build_ky,
    "us-la": build_la,
    "us-ma": build_ma,
    "us-me": build_me,
    "us-mi": build_mi,
    "us-mn": build_mn,
    "us-mo": build_mo,
    "us-ms": build_ms,
    "us-nc": build_nc,
    "us-nd": build_nd,
    "us-ne": build_ne,
    "us-nm": build_nm,
    "us-ny": build_ny,
    "us-ok": build_ok,
    "us-ri": build_ri,
    "us-sc": build_sc,
    "us-vt": build_vt,
    "us-wi": build_wi,
    "us-wv": build_wv,
}


def main() -> int:
    global _cache_dir
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="jurisdiction (repeatable)")
    parser.add_argument("--cache-dir", type=Path, help="cache publisher index responses")
    parser.add_argument("--summary", type=Path, help="write the JSON summary here")
    args = parser.parse_args()
    _cache_dir = args.cache_dir
    only = set(args.only) if args.only else None
    builder = Builder()
    for jurisdiction, build in BUILDERS.items():
        if only and jurisdiction not in only:
            continue
        build(builder)
    build_pointers(builder, only)
    text = json.dumps(builder.summary, indent=2, sort_keys=True)
    if args.summary:
        args.summary.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
