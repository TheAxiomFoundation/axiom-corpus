"""Build the CCDF state subsidy rulebook manifests (needs-closure element ccdf-s29).

Wave 5 (2026-09-15). The 2026-09-14 recount marked 15 states EXTRACTABLE for ``ccdf-s29`` (the
state regulation or agency manual that operationalises the subsidy program's eligibility, copays,
authorisation hours and payment rules). Each state's rulebook is read live from the publisher index
the recount named and written as ``manifests/us-<st>-ccdf-subsidy-rules.yaml`` under the shared
version ``2026-09-15-ccdf-subsidy-rules``; the CCDF queue row gets an ``additional_families`` entry
(``ccdf_subsidy_rulebook``) the way the 2026-09-13 follow-up families were recorded.

Publisher conventions are the ones the TANF whole-rulebook generator proved for the same hosts
(``scripts/build_tanf_state_policy_manual_manifests.py``): OARC PDF for Idaho, the rules.nebraska.gov
API for Nebraska (needs REQUESTS_CA_BUNDLE with the DigiCert intermediate in data/certs), the
tecuity rules API with browser impersonation for Oklahoma, the LRC rules API with browser
impersonation for South Dakota, the RICR part page for Rhode Island, the SRCA part files listed on
the HCA ISD page for New Mexico. Oregon (OAR 414-175) and Ohio (OAC 5180:6-1) are descriptor
manifests: the existing ``extract-oregon-administrative-rules`` and ``extract-ohio-administrative-code``
adapters do the extraction. Kentucky, South Carolina, Indiana, Maine and Vermont are agency PDFs.

Usage::

    export REQUESTS_CA_BUNDLE=/path/to/certifi-plus-data-certs.pem   # Nebraska only
    uv run python scripts/build_ccdf_subsidy_rules_manifests.py [--only id,ne,...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_ccdf_state_plan_manifests import ROOT, attach_family  # noqa: E402
from build_tanf_state_policy_manual_manifests import (  # noqa: E402
    NE_CONTINUATION_PATTERN,
    NE_SECTION_PATTERN,
    OK_EXTRACTION,
    fetch,
    heading_case,
    http_date,
    links,
    plain_fetch,
)

SOURCE_AS_OF = "2026-09-15"
VERSION = f"{SOURCE_AS_OF}-ccdf-subsidy-rules"
FAMILY = "ccdf_subsidy_rulebook"
PLAIN_UA = "axiom-corpus/0.1 (max@axiom-foundation.org)"
NAMES = {
    "id": "Idaho", "ne": "Nebraska", "ok": "Oklahoma", "sd": "South Dakota", "ri": "Rhode Island",
    "nm": "New Mexico", "me": "Maine", "ky": "Kentucky", "sc": "South Carolina", "in": "Indiana",
    "vt": "Vermont", "or": "Oregon", "oh": "Ohio", "tn": "Tennessee", "wi": "Wisconsin",
}


def ccdf_doc(
    *,
    jur: str,
    source_id: str,
    document_class: str,
    title: str,
    source_url: str,
    source_format: str,
    citation_path: str,
    expression_date: str,
    authority: str,
    subtype: str,
    state_program: str,
    index_url: str,
    extra: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    extraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": jur,
        "document_class": document_class,
        "title": title,
        "source_url": source_url,
        "source_format": source_format,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": expression_date,
        "citation_path": citation_path,
    }
    if request:
        doc["request"] = request
    if extraction:
        doc["extraction"] = extraction
    doc["metadata"] = {
        "primary_source": True,
        "source_authority": authority,
        "document_subtype": subtype,
        "program": "CCDF",
        "state_program": state_program,
        "federal_program": "CCDF",
        "manual_landing_page": index_url,
        "source_discovery_group": f"{jur}/{document_class}/ccdf",
        "discovered_via": f"manual-review:ccdf-agent-queue additional_families (needs-closure-2026-09-14 ccdf-s29); index {index_url}",
        "closure_elements": ["ccdf-s29"],
        **(extra or {}),
    }
    return doc


def last_modified(url: str, *, plain: bool = True) -> str | None:
    head = plain_fetch(url, head=True, user_agent=PLAIN_UA) if plain else fetch(url, head=True)
    return http_date(head.headers.get("last-modified") or head.headers.get("Last-Modified"))


# --------------------------------------------------------------------------- ID
def build_id() -> dict[str, Any]:
    """IDAPA 16.06.12 Idaho Child Care Program from the OARC current-rules listing (WordPress REST)."""
    import requests as plain_requests

    index = "https://adminrules.idaho.gov/current-rules/"
    headers = {"User-Agent": "axiom-corpus-ingest/1.0"}
    page = plain_requests.get(index, timeout=60, headers=headers).text
    nonce = re.search(r'dfmFetchDocuments = \{"nonce":"([0-9a-f]+)"', page).group(1)
    listing = plain_requests.post(
        "https://adminrules.idaho.gov/wp-json/dfm-document-display/fetch-documents",
        json={"azurePayload": {"documentType": "currentRules"}, "updateAgency": True},
        timeout=120,
        headers={**headers, "X-WP-Nonce": nonce, "Referer": index},
    ).json()["body"]
    all_rules = [(h, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(t))).strip()) for h, t in links(listing)]
    target = [(h, t) for h, t in all_rules if h.endswith("/160612.pdf")]
    if len(target) != 1:
        raise RuntimeError(f"expected one IDAPA 16.06.12 link, found {target}")
    href, text = target[0]
    url = "https://adminrules.idaho.gov" + href
    head = plain_requests.head(url, timeout=60, headers=headers, allow_redirects=True)
    modified = http_date(head.headers.get("last-modified")) or SOURCE_AS_OF
    body = plain_requests.get(url, timeout=120, headers=headers).content
    import fitz

    marks: dict[str, int] = {}
    with fitz.open(stream=body, filetype="pdf") as pdf:
        pages = len(pdf)
        for pdf_page in pdf:
            for mark in re.findall(r"\((\d{1,2}-\d{1,2}-\d{2})\)", pdf_page.get_text("text")):
                marks[mark] = marks.get(mark, 0) + 1
    effective = SOURCE_AS_OF
    if marks:
        latest = max(marks, key=lambda m: dt.datetime.strptime(m, "%m-%d-%y"))
        effective = dt.datetime.strptime(latest, "%m-%d-%y").date().isoformat()
    doc = ccdf_doc(
        jur="us-id",
        source_id="us-id-dhw-idapa-16-06-12-iccp",
        document_class="regulation",
        title=f"IDAPA {text}",
        source_url=url,
        source_format="pdf",
        citation_path="us-id/regulation/idapa/16/06/12",
        expression_date=effective,
        authority="Idaho Department of Health and Welfare",
        subtype="administrative_rules",
        state_program="Idaho Child Care Program (ICCP)",
        index_url=index,
        extra={
            "official_publisher": "Idaho Office of the Administrative Rules Coordinator",
            "idapa_chapter": "16.06.12",
            "source_last_modified": modified,
            "final_url": head.url,
            "page_count": pages,
            "rule_effective_marks": marks,
            "expression_date_note": "latest rule-history mark printed in the chapter (the 16.03.08 TAFI scope used the most frequent mark)",
            "extraction_note": "numbered_sections like the IDAPA 16.03.08 TAFI scope; table of contents on pages 2-3 skipped with start_page 4",
        },
        extraction={
            "segmentation": "numbered_sections",
            "start_page": 4,
            "sort_text": True,
            "drop_lines": ["IDAHO ADMINISTRATIVE CODE", "Department of Health and Welfare"],
            "drop_line_patterns": [
                r"^Section [0-9]+\s+Page [0-9]+.*$",
                r"^Page [0-9]+\s*$",
                r"^IDAHO ADMINISTRATIVE CODE\s+IDAPA 16\.06\.12$",
                r"^Department of Health and Welfare\s+Idaho Child Care Program \(ICCP\)$",
                r"^16\.06\.12 – IDAHO CHILD CARE PROGRAM \(ICCP\)$",
                r"^\d{3}\. -- \d{3}\.\s+\(RESERVED\)$",
                r"^\d{3}\.\s+\(RESERVED\)$",
            ],
        },
    )
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(all_rules),
        "primary_source_url": url,
        "inventory": (
            f"OARC current-rules listing has {len(all_rules)} rule chapters; taken IDAPA 16.06.12 Idaho Child Care "
            f"Program (ICCP), {pages} pages, HTTP Last-Modified {modified}, rule-history marks {marks}. The listing link "
            f"301-redirects to {head.url}."
        ),
    }


# --------------------------------------------------------------------------- NE
def build_ne() -> dict[str, Any]:
    """392 NAC Child Care Subsidy Program chapters from the rules.nebraska.gov API."""
    import os

    if not os.environ.get("REQUESTS_CA_BUNDLE"):
        raise RuntimeError(
            "rules.nebraska.gov serves only its leaf certificate: set REQUESTS_CA_BUNDLE to certifi's cacert.pem "
            "concatenated with data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem"
        )
    api = "https://rules.nebraska.gov/api"
    titles = plain_fetch(f"{api}/title/GetByAgencyId/37").json()["output"]
    ccs = [t for t in titles if t["titleNumber"] == 392]
    if len(ccs) != 1:
        raise RuntimeError(f"title 392 not listed once for agency 37: {ccs}")
    title_id = ccs[0]["id"]
    landing = f"https://rules.nebraska.gov/rules?agencyId=37&titleId={title_id}"
    chapters_api = f"{api}/chapter/GetByTitleId/{title_id}"
    chapters = plain_fetch(chapters_api).json()["output"]
    docs = []
    for chapter in sorted(chapters, key=lambda c: int(c["chapterNumber"])):
        number = int(chapter["chapterNumber"])
        blob = chapter.get("officialPdfBlobName") or chapter["pdfBlobName"]
        url = f"{api}/fileStorage/GetAsByteArray/{chapter['pdfContainerName']}/{quote(blob)}"
        effective = chapter["effectiveDate"][:10]
        docs.append(
            ccdf_doc(
                jur="us-ne",
                source_id=f"us-ne-dhhs-392-nac-chapter-{number}",
                document_class="regulation",
                title=f"Nebraska Title 392 NAC Chapter {number}: {heading_case(chapter['chapterName'])}",
                source_url=url,
                source_format="pdf",
                citation_path=f"us-ne/regulation/title-392/chapter-{number}",
                expression_date=effective,
                authority="Nebraska Department of Health and Human Services",
                subtype="filed_administrative_regulation_chapter",
                state_program="Nebraska Child Care Subsidy Program",
                index_url=landing,
                extra={
                    "official_publisher": "Nebraska Secretary of State (rules.nebraska.gov)",
                    "rules_landing_page": landing,
                    "rules_api_url": chapters_api,
                    "chapter_id": chapter["id"],
                    "chapter_name": chapter["chapterName"],
                    "pdf_blob_name": blob,
                    "official_pdf_blob_available": bool(chapter.get("officialPdfBlobName")),
                    "chapter_effective_date": effective,
                    "tls_note": "host serves its leaf certificate only; verified with the DigiCert public intermediate in data/certs (REQUESTS_CA_BUNDLE)",
                    "extraction_note": "labeled sections with the 468/475 NAC heading patterns",
                },
                extraction={
                    "segmentation": "labeled_sections",
                    "normalize_parenthetical_label_components": True,
                    "section_heading_pattern": NE_SECTION_PATTERN,
                    "heading_continuation_pattern": NE_CONTINUATION_PATTERN,
                },
            )
        )
    listing = "; ".join(f"{int(c['chapterNumber'])} {c['chapterName']} (eff. {c['effectiveDate'][:10]})" for c in sorted(chapters, key=lambda c: int(c["chapterNumber"])))
    return {
        "docs": docs,
        "index_url": landing,
        "index_document_count": len(chapters),
        "primary_source_url": landing,
        "inventory": (
            f"DHHS (agency 37) has {len(titles)} titles on rules.nebraska.gov; title 392 Child Care Subsidy Program has "
            f"{len(chapters)} chapters ({listing}); taken all {len(docs)} as the publisher's chapter PDF blobs."
        ),
    }


# --------------------------------------------------------------------------- OK
def build_ok() -> dict[str, Any]:
    index = "https://rules.ok.gov/home"
    api = "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=340&chapterNum=40"
    data = fetch(api).json()
    counts: dict[str, int] = {}
    for segment in data:
        key = f"{segment.get('name')}:{segment.get('statusName')}"
        counts[key] = counts.get(key, 0) + 1
    active = sum(1 for s in data if s.get("name") == "Section" and s.get("statusName") not in {"Revoked", "Reserved"})
    doc = ccdf_doc(
        jur="us-ok",
        source_id="us-ok-oac-340-40-child-care-subsidy-rules",
        document_class="regulation",
        title="Oklahoma Administrative Code Title 340 Chapter 40 Child Care Subsidy Program",
        source_url=index,
        source_format="json",
        citation_path="us-ok/regulation/oac/340/40",
        expression_date=SOURCE_AS_OF,
        authority="Oklahoma Department of Human Services",
        subtype="administrative_code_chapter",
        state_program="Oklahoma Child Care Subsidy Program",
        index_url=index,
        extra={
            "official_publisher": "Oklahoma Secretary of State Office of Administrative Rules",
            "rules_api_url": api,
            "title_number": "340",
            "chapter_number": "40",
            "segment_counts": counts,
            "access_note": "rules.ok.gov and the tecuity rules API answer plain clients with Cloudflare 403; fetched with browser impersonation (same API as us-ok-snap-rules and the OAC 340:10 TANF scope)",
        },
        request={"browser_impersonation": True, "browser_impersonation_direct": True},
        extraction=OK_EXTRACTION,
    )
    doc["download_url"] = api
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(data),
        "primary_source_url": index,
        "inventory": f"chapter API returns {len(data)} segments ({counts}); taken the chapter as one document, {active} non-revoked sections become records",
    }


# --------------------------------------------------------------------------- SD
def build_sd() -> dict[str, Any]:
    index = "https://sdlegislature.gov/Rules/Administrative/67:47"
    api = "https://sdlegislature.gov/api/Rules/"
    rules = []
    current = "67:47"
    while current and current.startswith("67:47"):
        data = fetch(api + current).json()
        rules.append(data)
        current = data.get("Next")
    counts: dict[str, int] = {}
    for rule in rules:
        counts[rule["Type"]] = counts.get(rule["Type"], 0) + 1
    docs = []
    skipped = []
    for rule in rules:
        if rule["Type"] != "D":
            continue
        number = rule["RuleNumber"]
        catchline = html.unescape(rule.get("Catchline") or "").strip()
        if re.search(r"\b(repealed|transferred|reserved)\b", catchline, re.I):
            skipped.append(number)
            continue
        parts = number.split(":")
        doc = ccdf_doc(
            jur="us-sd",
            source_id=f"us-sd-arsd-{'-'.join(parts)}",
            document_class="regulation",
            title=f"ARSD {number} {catchline}",
            source_url=f"https://sdlegislature.gov/Rules/Administrative/{number}",
            source_format="json",
            citation_path="us-sd/regulation/arsd/" + "/".join(parts),
            expression_date=SOURCE_AS_OF,
            authority="South Dakota Department of Social Services",
            subtype="administrative_rule_section",
            state_program="South Dakota Child Care Assistance",
            index_url=index,
            extra={
                "official_publisher": "South Dakota Legislative Research Council",
                "rules_api_url": api + number,
                "rule_id": rule.get("RuleId"),
                "rule_number": number,
                "chapter": ":".join(parts[:3]),
                "extraction_note": "JSON 'Html' field rendered as the rule text; the source note at the end of each rule carries its history",
            },
            request={"browser_impersonation": True},
            extraction={"json_html_field": "Html"},
        )
        doc["download_url"] = api + number
        docs.append(doc)
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(rules),
        "primary_source_url": index,
        "inventory": (
            f"rules API chain from 67:47 returns {len(rules)} records ({counts}: B article, C chapters, D sections); "
            f"taken the {len(docs)} sections whose catchline is not Repealed/Transferred; not taken: the article and "
            f"chapter table-of-contents records and {len(skipped)} repealed/transferred sections ({', '.join(skipped)})"
        ),
    }


# --------------------------------------------------------------------------- RI
RI_PARTS = {
    "218-20-00-4": ("us-ri-dhs-ccap-218-20-00-4", "us-ri/regulation/218-ricr/20/00/4", "Child Care Assistance Program (CCAP)"),
    "218-20-00-13": ("us-ri-dhs-ccap-educators-218-20-00-13", "us-ri/regulation/218-ricr/20/00/13", "Child Care Assistance Program for Child Care Educators and Child Care Staff"),
}


def _ri_pane(page: str, pane_id: str) -> str:
    match = re.search(rf'class="tab-pane[^"]*"[^>]*id="{pane_id}"[^>]*>(.*?)<div[^>]+class="tab-pane', page, re.S)
    text = re.sub(r"<[^>]+>", " | ", html.unescape(match.group(1) if match else ""))
    return re.sub(r"(\s*\|\s*)+", " | ", re.sub(r"\s+", " ", text))


def _ri_field(overview: str, label: str) -> str | None:
    match = re.search(re.escape(label) + r" \| ([^|]+) \|", overview)
    return match.group(1).strip() if match else None


def build_ri() -> dict[str, Any]:
    host = "https://rules.sos.ri.gov"
    index = host + "/organizations/chapter/218-20"
    chapter = fetch(index).text
    subchapters = re.findall(r'onclick="return get_parts\(this\)" id="([^"]+)"', chapter)
    if not subchapters:
        raise RuntimeError("no subchapter rows on the RICR chapter 218-20 page")
    parts: dict[str, str] = {}
    for sub in subchapters:
        listing = fetch(f"{host}/Organizations/get_parts/{sub}").text
        for href, label in links(listing):
            if "/Regulations/Part/" in href and not re.match(r"^Part \d+$", label):
                parts.setdefault(href.rstrip("/").rsplit("/", 1)[1], label)
    docs = []
    summaries = []
    for part_id, (source_id, citation_path, program) in RI_PARTS.items():
        if part_id not in parts:
            raise RuntimeError(f"{part_id} not in the chapter listing: {sorted(parts)}")
        part_url = f"{host}/regulations/part/{part_id}"
        page = fetch(part_url).text
        pdfs = sorted(set(re.findall(r"https://risos-apa-production-public\.s3\.amazonaws\.com/DHS/REG_[^\"'<>& ]+\.pdf", page)))
        if not pdfs:
            raise RuntimeError(f"no Download Regulation PDF on {part_url}")

        overview = _ri_pane(page, "second")
        filing_type = _ri_field(overview, "Type of Filing")
        status = _ri_field(overview, "Regulation Status")
        effective_raw = _ri_field(overview, "Effective")
        if not effective_raw:
            raise RuntimeError(f"no effective date in the overview pane of {part_url}: {overview[:300]}")
        effective = dt.datetime.strptime(effective_raw, "%m/%d/%Y").date().isoformat()
        history = _ri_pane(page, "four")
        filings = re.findall(r"(ACTIVE RULE|INACTIVE RULE) \| (?:EMERGENCY RULE \| )?([A-Za-z ]+) \| - effective from (\d{2}/\d{2}/\d{4})", history)
        # the active filing's PDF is the one whose S3 key carries the latest stamp
        pdf = sorted(pdfs)[-1]
        doc = ccdf_doc(
            jur="us-ri",
            source_id=source_id,
            document_class="regulation",
            title=parts[part_id],
            source_url=part_url,
            source_format="pdf",
            citation_path=citation_path,
            expression_date=effective,
            authority="Rhode Island Department of Human Services",
            subtype="administrative_regulation",
            state_program=program,
            index_url=index,
            extra={
                "official_publisher": "Rhode Island Department of State",
                "legal_identifier": f"218-RICR-{part_id.split('-', 1)[1]}",
                "filing_type": filing_type,
                "regulation_status": status,
                "regulation_effective_date": effective,
                "filing_history_count": len(filings),
                "pdf_candidates_on_page": len(pdfs),
                "pdf_last_modified": last_modified(pdf),
                "extraction_granularity": "pdf_page",
                "extraction_note": "the Download Regulation PDF of the active filing, page-level like the 218-RICR-20-00-1 SNAP and 218-RICR-20-00-2 RIW scopes",
            },
        )
        doc["download_url"] = pdf
        docs.append(doc)
        summaries.append(f"Part {part_id.rsplit('-', 1)[1]} ({filing_type}, {status}, effective {effective}, {len(filings)} filings)")
    listing_text = "; ".join(f"Part {k.rsplit('-', 1)[1]} {v}" for k, v in sorted(parts.items(), key=lambda kv: int(kv[0].rsplit('-', 1)[1])))
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(parts),
        "primary_source_url": f"{host}/regulations/part/218-20-00-4",
        "inventory": (
            f"RICR Title 218 Chapter 20, {len(parts)} parts via the chapter page's get_parts listing ({listing_text}); "
            f"taken {'; '.join(summaries)}. Parts 1 (SNAP) and 2 (RIW) are already in the corpus."
        ),
    }


# --------------------------------------------------------------------------- NM
# The recount named "8.150 NMAC child care parts (17)" on the HCA ISD index; read on 2026-09-15 those 17 SRCA part
# files are chapter 150, the Low Income Home Energy Assistance Program (the HCA page's own listing swaps the two
# chapters' labels). Child care assistance is chapter 9 (Early Childhood Education and Care Department): the ECECD
# Child Care Assistance program page links the SRCA part file 8.9.3 NMAC, which replaced the former 8.15.2 NMAC.
NM_9_HEADING_PATTERN = (
    r"^(?P<label>8\.\s*9\.\s*{part}\.\s*\d+(?:\s*-\s*\d+)?)\s+(?P<heading>[A-Z][^:]{{0,180}}:|\[RESERVED\]|"
    r"[A-Z][A-Z0-9 /()\[\]\-–—,'&]{{0,180}})(?:\s+(?P<body>.*))?$"
)


def build_nm() -> dict[str, Any]:
    index = "https://www.nmececd.org/child-care-assistance/"
    page = plain_fetch(index, user_agent=PLAIN_UA).text
    parts = sorted({(h, t) for h, t in links(page) if re.search(r"srca\.nm\.gov/parts/title08/08\.009\.\d{4}\.html$", h)})
    if not parts:
        raise RuntimeError("no chapter 9 SRCA part links on the ECECD Child Care Assistance page")
    docs = []
    for href, text in parts:
        part = int(re.search(r"/08\.009\.(\d{4})\.html$", href).group(1))
        response = plain_fetch(href)
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(response.text)))
        match = re.search(r"CHAPTER 9 (.+?) PART (\d+) (.+?) (?:&nbsp; )?8\.9\.\d+\.1 ", body)
        if not match or int(match.group(2)) != part:
            raise RuntimeError(f"part heading not found in {href}: {body[:300]}")
        part_title = heading_case(match.group(3).strip())
        modified = http_date(response.headers.get("Last-Modified"))
        docs.append(
            ccdf_doc(
                jur="us-nm",
                source_id=f"us-nm-srca-nmac-8-9-{part}",
                document_class="regulation",
                title=f"8.9.{part} NMAC {part_title}",
                source_url=href,
                source_format="html",
                citation_path=f"us-nm/regulation/nmac/8/9/{part}",
                expression_date=modified or SOURCE_AS_OF,
                authority="New Mexico Early Childhood Education and Care Department",
                subtype="administrative_code_part",
                state_program="New Mexico Child Care Assistance",
                index_url=index,
                extra={
                    "official_publisher": "New Mexico State Records Center and Archives",
                    "nmac_citation": f"8.9.{part}",
                    "nmac_title": "8",
                    "nmac_chapter": "9",
                    "nmac_part": str(part),
                    "nmac_chapter_title": heading_case(match.group(1).strip()),
                    "official_listing_title": text,
                    "nmac_chapter_index_url": "https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/chapter-9-early-childhood-education-and-care/",
                    "source_last_modified": modified,
                    "recount_note": "the recount's '8.150 NMAC child care parts' on the HCA ISD page are the LIHEAP rule (chapter 150); the SRCA chapter 15 (Child Care Assistance) page lists 8.15.1 as reserved and its part widget is client-rendered; 8.9.3 NMAC is the rule the ECECD program page links",
                    "extraction_note": "labeled sections like the us-nm SNAP (8.139) and cash assistance (8.102) part scopes",
                },
                extraction={
                    "html_content_selector": ".WordSection1, .Section1",
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": NM_9_HEADING_PATTERN.format(part=part),
                    "normalize_label_internal_whitespace": True,
                },
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(parts),
        "primary_source_url": parts[0][0],
        "inventory": (
            f"ECECD Child Care Assistance page links {len(parts)} SRCA chapter 9 part file(s) ({', '.join(t for _h, t in parts)}); "
            "taken all. The HCA ISD page's 8.150 parts the recount named are the LIHEAP rule, not child care."
        ),
    }


# --------------------------------------------------------------------------- agency PDFs (page-level)
def _pdf_doc(*, jur: str, source_id: str, document_class: str, title: str, url: str, citation_path: str,
             expression_date: str, authority: str, subtype: str, state_program: str, index_url: str,
             extra: dict[str, Any] | None = None) -> dict[str, Any]:
    modified = last_modified(url)
    doc = ccdf_doc(
        jur=jur, source_id=source_id, document_class=document_class, title=title, source_url=url,
        source_format="pdf", citation_path=citation_path, expression_date=expression_date or modified or SOURCE_AS_OF,
        authority=authority, subtype=subtype, state_program=state_program, index_url=index_url,
        extra={"source_last_modified": modified, "extraction_granularity": "pdf_page", **(extra or {})},
    )
    return doc


def _linked(index: str, pattern: str) -> tuple[str, str]:
    page = plain_fetch(index, user_agent=PLAIN_UA).text
    hits = [(h, t) for h, t in links(page) if re.search(pattern, h + " " + t, re.I)]
    if len({h for h, _ in hits}) != 1:
        raise RuntimeError(f"{index}: expected one link matching {pattern!r}, found {hits}")
    href, text = hits[0]
    if href.startswith("/"):
        from urllib.parse import urljoin

        href = urljoin(index, href)
    return href, text


def build_me() -> dict[str, Any]:
    index = "https://www.maine.gov/dhhs/ocfs/provider-resources/child-care-subsidy-information-for-providers"
    url, text = _linked(index, r"CCAP%20Full%20Rule")
    doc = _pdf_doc(
        jur="us-me", source_id="us-me-ocfs-ccap-rules-10-148-cmr-chapter-6", document_class="regulation",
        title="Maine Child Care Affordability Program (CCAP) Rules, 10-148 CMR Chapter 6",
        url=url, citation_path="us-me/regulation/dhhs/ocfs/10-148-cmr-chapter-6",
        expression_date="2025-08-18",
        authority="Maine Department of Health and Human Services, Office of Child and Family Services",
        subtype="administrative_rules", state_program="Child Care Affordability Program (CCAP)", index_url=index,
        extra={"official_listing_title": text, "rule_chapter": "10-148 C.M.R. Chapter 6",
               "expression_date_note": "the file name carries the 8.18.2025 adoption date and the HTTP Last-Modified is the same day"},
    )
    return {"docs": [doc], "index_url": index, "index_document_count": 1, "primary_source_url": url,
            "inventory": f"OCFS Child Care Affordability page links '{text}' ({url}); taken page-level."}


def build_ky() -> dict[str, Any]:
    index = "https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx"
    url, text = _linked(index, r"omvolviii\.pdf")
    doc = _pdf_doc(
        jur="us-ky", source_id="us-ky-dcbs-dfs-operation-manual-volume-viii-ccap", document_class="manual",
        title="Kentucky DCBS Operation Manual Volume VIII: Child Care Assistance Program (CCAP)",
        url=url, citation_path="us-ky/manual/dcbs/dfs/volume-viii-ccap", expression_date="",
        authority="Kentucky Cabinet for Health and Family Services, Department for Community Based Services",
        subtype="agency_operation_manual_volume", state_program="Child Care Assistance Program (CCAP)", index_url=index,
        extra={"official_listing_title": text, "extraction_note": "page-level like the volume III (KTAP) and volume II (SNAP) scopes from the same page"},
    )
    return {"docs": [doc], "index_url": index, "index_document_count": 1, "primary_source_url": url,
            "inventory": f"DFS manual volume index lists '{text}'; taken page-level (expression date = HTTP Last-Modified, as for volume III)."}


def build_sc() -> dict[str, Any]:
    index_dss = "https://dss.sc.gov/about/data-and-resources/manuals/"
    index_dece = "https://www.scchildcare.org/resources/"
    url_v, text_v = _linked(index_dss, r"voucher-policy-manual")
    url_s, text_s = _linked(index_dece, r"Policy Manual Vol\. 39")
    doc = _pdf_doc(
        jur="us-sc", source_id="us-sc-dss-child-care-scholarship-policy-manual-vol-39", document_class="manual",
        title=f"{text_s}", url=url_s, citation_path="us-sc/manual/dss/child-care-scholarship-policy-manual",
        expression_date="2026-02-09", authority="South Carolina Department of Social Services, Division of Early Care and Education",
        subtype="agency_policy_manual", state_program="SC Child Care Scholarship Program", index_url=index_dece,
        extra={"official_listing_title": text_s, "manual_volume": "039", "expression_date_note": "page 1 prints 'Volume 039 - Revised 02/09/2026'",
               "extraction_note": "current volume (39) of the scholarship policy manual; volumes 36-38 stay listed as superseded",
               "not_taken": f"DSS manuals page '{text_v}' ({url_v}) is Volume 028 dated 06/01/2018 of the program's former name (SC Voucher); superseded by this manual, not taken"},
    )
    return {"docs": [doc], "index_url": index_dece, "index_document_count": 1, "primary_source_url": url_s,
            "inventory": f"scchildcare.org resources page lists scholarship policy manuals vol. 36-39 (taken vol. 39, '{text_s}', revised 2026-02-09); the DSS manuals page's '{text_v}' is volume 028 (06/01/2018) under the program's former name, superseded, not taken."}


def build_in() -> dict[str, Any]:
    url = "https://www.in.gov/fssa/carefinder/files/CCDF-Policy-Manual.pdf"
    doc = _pdf_doc(
        jur="us-in", source_id="us-in-fssa-ccdf-policy-manual", document_class="manual",
        title="Indiana FSSA Office of Early Childhood and Out-of-School Learning: CCDF Policy Manual",
        url=url, citation_path="us-in/manual/fssa/oecosl/ccdf-policy-manual", expression_date="2025-02-02",
        authority="Indiana Family and Social Services Administration, Office of Early Childhood and Out-of-School Learning",
        subtype="agency_policy_manual", state_program="Indiana CCDF child care voucher program",
        index_url="https://www.in.gov/fssa/carefinder/information-and-resources2/",
        extra={"expression_date_note": "page 1 prints 'Revised, Effective October 14, 2024' and 'Revised February 2, 2025'",
               "extraction_note": "the queue's needs_review row 2026-09-10-ccdf-in-policy-manual named this file (HTTP 200, application/pdf); the carefinder information page does not list it, so the lead-list URL is the index"},
    )
    return {"docs": [doc], "index_url": "https://www.in.gov/fssa/carefinder/information-and-resources2/", "index_document_count": 1,
            "primary_source_url": url, "inventory": "FSSA CCDF Policy Manual PDF (queue candidate source, HTTP 200) taken page-level; the Provider Manual is not taken (no index page names it)."}


def build_vt() -> dict[str, Any]:
    index = "https://dcf.vermont.gov/cdd/laws-rules"
    url, text = _linked(index, r"CCFAP-Regulations\.pdf")
    doc = _pdf_doc(
        jur="us-vt", source_id="us-vt-dcf-cdd-ccfap-regulations", document_class="regulation",
        title="Vermont Child Care Financial Assistance Program (CCFAP) Regulations",
        url=url, citation_path="us-vt/regulation/dcf/cdd/ccfap-regulations", expression_date="2009-02-09",
        authority="Vermont Department for Children and Families, Child Development Division",
        subtype="program_regulations", state_program="Child Care Financial Assistance Program (CCFAP)", index_url=index,
        extra={"official_listing_title": text, "expression_date_note": "page 1 prints 'Effective Date: February 9, 2009'; HTTP Last-Modified 2022-07-15",
               "extraction_note": "page-level like the ESD rules scopes; the CDD 'Policies & Procedures' PDFs listed on the same page are procedures, not taken"},
    )
    return {"docs": [doc], "index_url": index, "index_document_count": 1, "primary_source_url": url,
            "inventory": f"CDD Laws, Rules and Procedures page links '{text}' ({url}) under CCFAP, and its CCFAP sub-page lists about 27 policy/procedure PDFs; taken the regulations page-level."}


# --------------------------------------------------------------------------- OR / OH descriptors (adapter-extracted)
def build_or() -> dict[str, Any]:
    chapter_url = "https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=115"
    page = plain_fetch(chapter_url, user_agent=PLAIN_UA).text
    divisions = sorted(set(re.findall(r"Division (\d+)(?:&nbsp;|\s)*-(?:&nbsp;|\s)*([^<]+?)\s*<", page)), key=lambda d: int(d[0]))
    rules_175 = sorted(set(re.findall(r"(414-175-\d{4})", page)))
    if not divisions or not rules_175:
        raise RuntimeError("OARD chapter 414 listing did not parse")
    run_id = f"{VERSION}-chapter-414-division-175"
    doc = ccdf_doc(
        jur="us-or", source_id="us-or-delc-oar-414-175-erdc", document_class="regulation",
        title="Oregon Administrative Rules Chapter 414 Division 175: Employment Related Day Care Program",
        source_url=chapter_url, source_format="html", citation_path="us-or/regulation/chapter-414/division-175",
        expression_date=SOURCE_AS_OF, authority="Oregon Department of Early Learning and Care",
        subtype="administrative_rules_division", state_program="Employment Related Day Care (ERDC)", index_url=chapter_url,
        extra={
            "official_publisher": "Oregon Secretary of State, Oregon Administrative Rules Database (OARD)",
            "extraction_adapter": "extract-oregon-administrative-rules --only-chapter 414 --only-division 175",
            "extraction_run_id": run_id,
            "chapter_division_count": len(divisions),
            "division_rule_count": len(rules_175),
            "extraction_note": "descriptor manifest like the chapter 461 TANF scope: division and rule rows come from the OAR adapter, not from extract-official-documents",
        },
    )
    return {"docs": [doc], "version": run_id, "index_url": chapter_url, "index_document_count": len(rules_175),
            "primary_source_url": chapter_url,
            "inventory": f"OARD chapter 414 (DELC) lists {len(divisions)} divisions; division 175 Employment Related Day Care Program has {len(rules_175)} rules, taken through the OAR adapter (run id {run_id}). The licensing and other DELC divisions are not taken."}


def build_oh() -> dict[str, Any]:
    host = "https://codes.ohio.gov"
    agency_url = host + "/ohio-administrative-code/5180:6"
    page = plain_fetch(agency_url, user_agent=PLAIN_UA).text
    chapters = [(h.rsplit("-", 1)[1], re.sub(r"\s+", " ", t), host + h) for h, t in links(page) if re.match(r"^/ohio-administrative-code/chapter-5180:6-\d+$", h)]
    if not chapters:
        raise RuntimeError("no 5180:6 chapter links on codes.ohio.gov")
    chapter_url = host + "/ohio-administrative-code/chapter-5180:6-1"
    rule_count = len(set(re.findall(r'href="/ohio-administrative-code/rule-5180:6-1-[\d.\-]+"', plain_fetch(chapter_url, user_agent=PLAIN_UA).text)))
    run_id = f"{VERSION}-agency-5180-6-chapter-5180-6-1"
    doc = ccdf_doc(
        jur="us-oh", source_id="us-oh-dcy-oac-5180-6-1-publicly-funded-child-care", document_class="regulation",
        title="Ohio Administrative Code Chapter 5180:6-1 Publicly Funded Child Care",
        source_url=chapter_url, source_format="html", citation_path="us-oh/regulation/agency-5180-6/chapter-5180-6-1",
        expression_date=SOURCE_AS_OF, authority="Ohio Department of Children and Youth",
        subtype="administrative_code_chapter", state_program="Ohio Publicly Funded Child Care (PFCC)", index_url=agency_url,
        extra={
            "official_publisher": "Ohio Laws and Administrative Rules (Legislative Service Commission)",
            "code_agency": "5180:6",
            "extraction_adapter": "extract-ohio-administrative-code --only-chapter 5180:6-1",
            "extraction_run_id": run_id,
            "rule_count": rule_count,
            "renumbering_note": "the recount named OAC 5101:2-16; codes.ohio.gov answers 'Number Not Found' for 5101:2-16 and lists agency 5101:2 with chapters 5101:2-20 and 5101:2-25 only; the publicly funded child care rules now sit under the Department of Children and Youth as 5180:6-1",
            "extraction_note": "descriptor manifest like manifests/us-oh-snap-rules.yaml (OAC 5101:4): chapter and rule rows come from the OAC adapter",
        },
    )
    listing = "; ".join(f"5180:6-{n} {t.split(' | ')[-1].strip()}" for n, t, _ in chapters)
    return {"docs": [doc], "version": run_id, "index_url": agency_url, "index_document_count": rule_count,
            "primary_source_url": chapter_url,
            "inventory": f"codes.ohio.gov agency 5180:6 Early Care and Education Eligibility: {len(chapters)} chapters ({listing}); taken chapter 5180:6-1 ({rule_count} rule links) through the OAC adapter, run id {run_id}."}


BUILDERS = {
    "id": build_id, "ne": build_ne, "ok": build_ok, "sd": build_sd, "ri": build_ri, "nm": build_nm,
    "me": build_me, "ky": build_ky, "sc": build_sc, "in": build_in, "vt": build_vt, "or": build_or, "oh": build_oh,
}

# Read on 2026-09-15 and found not to carry the rulebook the recount described.
NOT_TAKEN = {
    "tn": ("https://www.tn.gov/humanservices/information-and-resources/dhs-publications.html",
           "the TDHS publications page (106 PDF links: APS 8.xx, SSBG 14.xx, Families First 23.xx, SNAP 24.xx, handbooks) "
           "lists no Child Care Certificate Program policy; the only child-care item is 23.22 Families First Child Care, a "
           "TANF policy already in the 2026-09-10 TANF manual scope. The subsidy rules are codified as Tenn. Comp. R. & Regs. "
           "1240-04 on the Secretary of State's site, which no queue row inventories"),
    "wi": ("https://dcf.wisconsin.gov/wishares",
           "the Wisconsin Shares pages (/wishares, /wishares/parents, /wishares/providers, /wishares/maxrates) link the "
           "Maximum Rates chart, the Copayment chart, eligibility brochures (DCF-P-5186 etc.) and the child-welfare "
           "'Policies and Standards' portal, but not the Wisconsin Shares Child Care Subsidy Policy Manual; "
           "dcf.wisconsin.gov/manuals/ answers HTTP 403 to the plain client, so the manual's index was not located"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated codes (id,ne,...); default: every builder")
    args = parser.parse_args()
    codes = args.only.split(",") if args.only else list(BUILDERS) + list(NOT_TAKEN)
    queue_path = ROOT / "manifests" / "ccdf-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    for code in codes:
        jur = f"us-{code}"
        if code in NOT_TAKEN:
            index, reason = NOT_TAKEN[code]
            attach_family(queue, jur, {
                "family": FAMILY, "queue_status": "needs_review", "index_url": index, "target_manifest": None,
                "taken_count": 0, "notes": f"Reviewed {SOURCE_AS_OF} (closure ccdf-s29): {reason}.",
            })
            print(f"{jur}: not taken ({reason[:60]}...)")
            continue
        result = BUILDERS[code]()
        version = result.get("version", VERSION)
        manifest = {"version": version, "documents": result["docs"]}
        stem = f"{jur}-ccdf-subsidy-rules"
        (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
        attach_family(queue, jur, {
            "family": FAMILY,
            "queue_status": "agent_ready",
            "index_url": result["index_url"],
            "index_document_count": result["index_document_count"],
            "primary_source_url": result["primary_source_url"],
            "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": result["docs"][0]["document_class"], "version": version},
            "taken_count": len(result["docs"]),
            "notes": f"State CCDF subsidy rulebook taken {SOURCE_AS_OF} (closure ccdf-s29): {result['inventory']}",
        })
        print(f"{jur}: {len(result['docs'])} document(s) -> manifests/{stem}.yaml (version {version})")
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
