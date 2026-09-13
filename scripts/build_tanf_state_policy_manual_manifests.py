"""Build the TANF state policy manual manifests for the TANF agent queue batches
and update ``manifests/tanf-agent-queue.yaml``.

Batch rule (recorded in docs/ingest-runs/2026-09-10-tanf-state-policy-manuals-batch-1.md):
walk the queue's state rows in queue order; a state whose current TANF cash
assistance policy manual (or the adopted rule the state itself publishes as its
primary policy document) is already in the corpus is marked ``done`` and does not
count; batch 1 is the first ten remaining rows. Batch 1 = CA, CO, DC, MO, MS, MT,
ND, NY, OK, OR. NY and OR are blocked publishers (see BLOCKED below); the other
eight get one manifest each, generated here from the publisher's own index.

Batch 4 (docs/ingest-runs/2026-09-10-tanf-state-policy-manuals-batch-4-retry.md) retried the
blocked and needs-review rows from a US network: SC, KY, TN, VT, NM, NE build manifests here;
OR and OH are descriptor manifests for the existing OAR/OAC adapters; NY stays blocked.
The Nebraska builder needs ``REQUESTS_CA_BUNDLE`` (certifi plus data/certs/digicert-*.pem).

Every index is fetched live from the publisher. Some publishers (Montana DPHHS,
Mississippi SoS, CDSS) answer plain HTTP clients with 403/reset pages, so index
fetches use curl-cffi browser impersonation; the manifests carry
``request: browser_impersonation: true`` where the document host needs it.

    uv run python scripts/build_tanf_state_policy_manual_manifests.py \
        [--mo-title-cache <json>]

The Missouri TA manual has 472 section pages whose titles are only in each page's
``<title>``; the script fetches them (about 10 minutes) unless a cache JSON from a
previous run is supplied.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import yaml
from curl_cffi import requests as curl_requests

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "manifests" / "tanf-agent-queue.yaml"
VERSION = "2026-09-10-tanf-state-policy-manual"
SOURCE_AS_OF = dt.date.today().isoformat()
IMPERSONATE = "chrome"
DISCOVERED_VIA = "manual-review:tanf-agent-queue; index {index}"

BATCH_1 = ("us-ca", "us-co", "us-dc", "us-mo", "us-ms", "us-mt", "us-nd", "us-ny", "us-ok", "us-or")
# Batch 2 (docs/ingest-runs/2026-09-10-tanf-state-policy-manuals-batch-2.md): the four rows batch 1
# deferred, then - the queue having no further state rows - the next states in alphabetical order
# whose TANF policy manual or adopted rule is not already in the corpus, until ten were attempted.
BATCH_2 = ("us-pa", "us-sc", "us-sd", "us-va", "us-id", "us-ky", "us-la", "us-ne", "us-nh", "us-nm")
# Batch 3 (docs/ingest-runs/2026-09-10-tanf-state-policy-manuals-batch-3.md): the last jurisdictions
# of the 50 states plus DC without a queue row.
BATCH_3 = ("us-oh", "us-ri", "us-tn", "us-vt", "us-wi")
# Batch 4 (docs/ingest-runs/2026-09-10-tanf-state-policy-manuals-batch-4-retry.md): retry of every
# blocked_primary_source row and the NM needs_review row from a US network.
BATCH_4 = ("us-ny", "us-or", "us-sc", "us-ky", "us-ne", "us-oh", "us-tn", "us-vt", "us-nm")
# Territories pass (docs/ingest-runs/2026-09-11-territories-ten-programs.md): PR and GU extracted, VI
# publishes no manual, AS operates no TANF program, MP is outside the statutory definition of State.
BATCH_5 = ("us-pr", "us-gu", "us-vi", "us-as", "us-mp")
BATCH_LABEL = {
    **dict.fromkeys(BATCH_1, "Batch 1"),
    **dict.fromkeys(BATCH_2, "Batch 2"),
    **dict.fromkeys(BATCH_3, "Batch 3"),
    **dict.fromkeys(BATCH_4, "Batch 4 (retry)"),
    **dict.fromkeys(BATCH_5, "Territories pass (2026-09-11)"),
}
# Rows added to the queue by batches 2 and 3 (not on the lead list): name per jurisdiction.
NEW_ROWS = {
    "us-ak": "Alaska",
    "us-ar": "Arkansas",
    "us-ct": "Connecticut",
    "us-ia": "Iowa",
    "us-id": "Idaho",
    "us-ky": "Kentucky",
    "us-la": "Louisiana",
    "us-ma": "Massachusetts",
    "us-md": "Maryland",
    "us-mi": "Michigan",
    "us-mn": "Minnesota",
    "us-ne": "Nebraska",
    "us-nh": "New Hampshire",
    "us-nj": "New Jersey",
    "us-nm": "New Mexico",
    "us-oh": "Ohio",
    "us-ri": "Rhode Island",
    "us-tn": "Tennessee",
    "us-ut": "Utah",
    "us-vt": "Vermont",
    "us-wi": "Wisconsin",
    "us-wv": "West Virginia",
    "us-wy": "Wyoming",
    "us-pr": "Puerto Rico",
    "us-gu": "Guam",
    "us-vi": "Virgin Islands",
    "us-as": "American Samoa",
    "us-mp": "Northern Mariana Islands",
}

# States whose TANF cash-assistance policy manual (or state-published adopted rule)
# is already in the corpus. target_manifest / target_scope name the existing
# artifacts; these rows do not count toward a batch.
DONE: dict[str, dict[str, Any]] = {
    "us-al": {
        "target_manifest": "manifests/us-al-tanf-official-documents.yaml",
        "scope": ("policy", "2026-07-02-al-tanf-official-documents"),
        "notes": "Alabama Family Assistance: Admin Code 660-2-2 (regulation, 2026-07-02-al-admin-code-660-2-2), "
        "TANF State Plan 2024 and Public Assistance Payment Manual Appendix N Sec 2 (policy). Reviewer judgment: "
        "the DHR-published payment manual appendix plus the adopted rule is the state's primary policy document set; "
        "no separate DHR TANF policy manual index exists. Done per the prior-ingest list.",
    },
    "us-az": {
        "target_manifest": "manifests/us-az-des-faa5-manual.yaml",
        "scope": ("manual", "2025-10-30-az-des-faa5-manual"),
        "notes": "Arizona DES FAA policy manual (combined CA/NA) already ingested; recovery scope 2026-07-17-faa5-recovery also exists. Done per the prior-ingest list.",
    },
    "us-de": {
        "target_manifest": "manifests/us-de-tanf-rules.yaml",
        "scope": ("regulation", "2026-07-03-de-tanf-rules"),
        "notes": "Delaware DSSM 3000 TANF rules (state-published adopted rule) already ingested. Done per the prior-ingest list.",
    },
    "us-fl": {
        "target_manifest": "manifests/us-fl-ess-manual.yaml",
        "scope": ("manual", "2026-05-27-fl-ess-manual"),
        "notes": "Florida DCF ESS Program Policy Manual is the combined FS/TCA/Medicaid manual (48 chapters incl. 1400/1800 TCA chapters, 2600 benefit calculation). Reviewer judgment: combined manual counts as the TCA policy manual; not re-ingested.",
    },
    "us-ga": {
        "target_manifest": "manifests/us-ga-tanf-manual.yaml",
        "scope": ("manual", "2026-06-25-ga-tanf"),
        "notes": "Georgia DFCS TANF Policy Manual already ingested. Done per the prior-ingest list.",
    },
    "us-hi": {
        "target_manifest": "manifests/us-hi-tanf-admin-rules.yaml",
        "scope": ("regulation", "2026-07-03-hi-tanf-admin-rules"),
        "notes": "Hawaii HAR TANF rules already ingested. Done per the prior-ingest list.",
    },
    "us-il": {
        "target_manifest": "manifests/us-il-snap-manual.yaml",
        "scope": ("manual", "2026-05-27-il-cash-snap-medical-manual"),
        "notes": "Illinois DHS Cash, SNAP and Medical Manual (combined; PM chapters incl. cash/TANF) already ingested as us-il/manual/dhs/csmm. Reviewer judgment: combined manual counts; not re-ingested.",
    },
    "us-in": {
        "target_manifest": "manifests/us-in-snap-manual.yaml",
        "scope": ("manual", "2026-05-27-in-snap-manual"),
        "notes": "Indiana FSSA/DFR SNAP/TANF Program Policy Manual (combined) already ingested at page granularity. Reviewer judgment: combined manual counts; chapter-level re-segmentation is a later improvement, not a batch item.",
    },
    "us-ks": {
        "target_manifest": "manifests/us-ks-keesm.yaml",
        "scope": ("manual", "2026-05-27-ks-keesm"),
        "notes": "Kansas KEESM (combined) already ingested. Done per the prior-ingest list.",
    },
    "us-me": {
        "target_manifest": "manifests/us-me-tanf-regulation-official-documents.yaml",
        "scope": ("regulation", "2026-07-03-me-tanf-regulation"),
        "notes": "Maine TANF rule (10-144 CMR ch. 331) and rule 125A already ingested; Maine publishes its TANF policy as adopted rules. Done per the prior-ingest list.",
    },
    "us-nc": {
        "target_manifest": "manifests/us-nc-work-first-manual-official-documents.yaml",
        "scope": ("manual", "2026-07-03-nc-work-first-manual"),
        "notes": "North Carolina Work First Manual section 114 (Income and Budgeting) already ingested. Reviewer judgment: done per the prior-ingest list, but only section 114 of the manual is in the corpus; the remaining Work First manual sections are a follow-up, not a batch-1 item.",
    },
    "us-nv": {
        "target_manifest": "manifests/us-nv-eligibility-payments-manual.yaml",
        "scope": ("manual", "2026-05-27-nv-eligibility-payments-manual"),
        "notes": "Nevada DWSS Eligibility and Payments Manual (combined TANF/SNAP/Medicaid, 51 chapter PDFs) already ingested. Reviewer judgment: combined manual counts as the TANF policy manual; not re-ingested.",
    },
    "us-tx": {
        "target_manifest": "manifests/us-tx-manuals.yaml",
        "scope": ("manual", "2026-05-27-tx-manuals"),
        "notes": "Texas Works Handbook (combined) already ingested. Done per the prior-ingest list.",
    },
    "us-wa": {
        "target_manifest": "manifests/us-wa-eaz-manual.yaml",
        "scope": ("manual", "2026-07-21-wa-eaz-manual"),
        "notes": "Washington EA-Z Manual (combined) already ingested. Done per the prior-ingest list.",
    },
    # Batch 2: states not on the lead list, checked in alphabetical order while extending the
    # batch to ten attempts; their TANF policy document is already in the corpus.
    "us-ak": {
        "target_manifest": "manifests/us-ak-atap-regulations.yaml",
        "scope": ("regulation", "2026-07-01-ak-atap-regulations"),
        "notes": "Batch 2 check: Alaska ATAP regulations (7 AAC 45, adopted rule) and ATAP standards (guidance, 2026-07-01-ak-atap-standards) already ingested. Done.",
    },
    "us-ar": {
        "target_manifest": "manifests/us-ar-tea-official-documents.yaml",
        "scope": ("policy", "2026-07-02-ar-tea-official-documents"),
        "notes": "Batch 2 check: Arkansas TEA official documents already ingested. Done.",
    },
    "us-ct": {
        "target_manifest": "manifests/us-ct-ssp-official-documents.yaml",
        "scope": ("policy", "2026-07-02-ct-ssp-upm-and-standards"),
        "notes": "Batch 2 check: Connecticut DSS Uniform Policy Manual (TFA) and standards already ingested. Done.",
    },
    "us-ia": {
        "target_manifest": "manifests/us-ia-fip-admin-rules.yaml",
        "scope": ("regulation", "2026-07-03-ia-fip-admin-rules"),
        "notes": "Batch 2 check: Iowa FIP administrative rules (441 IAC, adopted rule) already ingested. Done.",
    },
    "us-ma": {
        "target_manifest": "manifests/us-ma-tafdc-regulations.yaml",
        "scope": ("regulation", "2026-06-27-ma-tafdc-regulations"),
        "notes": "Batch 2 check: Massachusetts DTA TAFDC regulations 106 CMR 701-707 (adopted rule published by DTA) already ingested. Done.",
    },
    "us-md": {
        "target_manifest": "manifests/us-md-tca-guidance-official-documents.yaml",
        "scope": ("regulation", "2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03"),
        "notes": "Batch 2 check: Maryland TCA COMAR 07.03.03 (adopted rule), TCA guidance and statutes already ingested. Done.",
    },
    "us-mi": {
        "target_manifest": "manifests/us-mi-bridges-manual.yaml",
        "scope": ("manual", "2026-07-17-mi-bridges-manual"),
        "notes": "Batch 2 check: Michigan MDHHS Bridges Eligibility Manual (combined, incl. FIP) and RFT 248 already ingested. Reviewer judgment: combined manual counts. Done.",
    },
    "us-mn": {
        "target_manifest": "manifests/us-mn-combined-manual.yaml",
        "scope": ("manual", "2026-05-27-mn-combined-manual-r2026-07-15-self-contained"),
        "notes": "Batch 2 check: Minnesota DHS Combined Manual (MFIP) already ingested. Reviewer judgment: combined manual counts. Done.",
    },
    "us-nj": {
        "target_manifest": "manifests/us-nj-wfnj-rules.yaml",
        "scope": ("regulation", "2026-07-13-recovery"),
        "notes": "Batch 2 check: New Jersey WFNJ rules N.J.A.C. 10:90 (adopted rule) are in the corpus in the page-level 2026-07-13-recovery scope. Done with that caveat.",
    },
    "us-ut": {
        "target_manifest": "manifests/us-ut-fep-official-documents.yaml",
        "scope": ("regulation", "2026-07-02-ut-fep-official-documents"),
        "notes": "Batch 2 check: Utah FEP rules R986 (adopted rule) and the DWS eligibility manual already ingested. Done.",
    },
    "us-wv": {
        "target_manifest": "manifests/us-wv-manuals.yaml",
        "scope": ("manual", "2026-07-21-wv-income-maintenance-manual"),
        "notes": "Batch 2 check: West Virginia Income Maintenance Manual (combined, incl. WV WORKS) already ingested. Reviewer judgment: combined manual counts. Done.",
    },
    "us-wy": {
        "target_manifest": "manifests/us-wy-manuals.yaml",
        "scope": ("manual", "2026-05-27-wy-manuals-r2026-07-15-self-contained"),
        "notes": "Batch 2 check: Wyoming SNAP and POWER Policy Manual (combined) already ingested. Reviewer judgment: combined manual counts. Done.",
    },
}

# Publishers that blocked retrieval on 2026-09-10 and again on the batch-4 retry from a US network. Exact
# failures observed by the agent. The batch 2/3 blocked rows (SC, KY, NE, OH, TN, VT) and OR answered on the
# retry and moved to BUILDERS; their earlier failures are recorded in the batch notes.
BLOCKED: dict[str, dict[str, Any]] = {
    "us-ny": {
        "source_kind": "official_pdf_manual",
        "primary_source_url": "https://otda.ny.gov/programs/temporary-assistance/TASB.pdf",
        "index_url": "https://otda.ny.gov/programs/temporary-assistance/",
        "index_document_count": 1,
        "document_class": "manual",
        "notes": "BLOCKED 2026-09-10: OTDA Temporary Assistance Source Book (TASB.pdf, HTTP Last-Modified 2024-11-27). "
        "Plain requests/curl to otda.ny.gov: TCP connection reset by peer. curl-cffi browser impersonation "
        "(chrome, chrome110, chrome124, edge101, firefox): HTTP 200 text/html 6.7 KB JavaScript bot-challenge page "
        "('Please enable JavaScript to view the page content. Your support ID is ...') instead of the PDF; safari "
        "profiles: connection reset. No workaround attempted. The 2024-2026 TANF State Plan (policy) is already in "
        "the corpus (us-ny-tanf-state-plan); the Employment Policy Manual is in 2026-07-17-ny-snap-manuals. "
        "Retried 2026-09-10T20:37+02:00 (batch 2: one plain curl HEAD, connection reset by peer; one curl-cffi "
        "chrome/firefox GET, HTTP 200 text/html 5.5 KB challenge page; 15 s timeouts), same failure. Retried "
        "2026-09-10T21:34Z from a US network (batch 4: one plain requests GET, 'Remote end closed connection without "
        "response'; one curl-cffi chrome GET, HTTP 200 text/html 7.6 KB bot-challenge page (window['bobcmn'] ... TSPD); "
        "20 s timeouts), same failure.",
    },
}

# Rows attempted but neither extracted nor blocked by the publisher (index needs a reviewer decision).
NEEDS_REVIEW: dict[str, dict[str, Any]] = {}  # NM moved to BUILDERS in batch 4 (HCA/ISD parts index found)

# Territories pass (2026-09-11; first probes 2026-09-11T21:15Z from a US network). Rows with no
# territory document: the publisher posts nothing (VI) or the program is not operated there (AS, MP).
# The queue schema has no not-applicable status; AS and MP are blocked_primary_source with the
# statutory reason and program_applicability: not_applicable.
USC_619_URL = "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section619&num=0&edition=prelim"
NOT_PUBLISHED: dict[str, dict[str, Any]] = {
    "us-vi": {
        "source_kind": "official_state_agency_manual_not_published",
        "primary_source_url": None,
        "index_url": "https://dhs.vi.gov/family-assistance-programs/",
        "index_document_count": 24,
        "document_class": "manual",
        "notes": (
            "Territories pass (2026-09-11): the Virgin Islands Department of Human Services, Division of Family "
            "Assistance page (HTTP 200 to the plain client) lists 24 PDFs: SNAP application packets and forms, the "
            "FY 2026 SNAP income-limits chart and simplified-reporting notice, the SNAP E&T plan and handbook, ABAWD "
            "flyers, ECAP forms, waivers and one TANF brochure (participant leaflet). No TANF policy manual, adopted "
            "rule or state plan is posted; the TANF state plan is filed with ACF through OLDC and not published by "
            "the territory. 0 taken. Nothing was worked around."
        ),
    },
}
NOT_APPLICABLE: dict[str, dict[str, Any]] = {
    "us-as": {
        "source_kind": "program_not_operated",
        "primary_source_url": USC_619_URL,
        "index_url": "http://dhss.as/index.html",
        "index_document_count": 0,
        "notes": (
            "Not applicable (recorded as blocked_primary_source because the queue schema has no not-applicable "
            "status): American Samoa is a 'State' for TANF under 42 U.S.C. 619(5) but has never operated a TANF "
            "program; ACF's TANF grantees are the 50 states, DC, Guam, Puerto Rico and the Virgin Islands (ACF OFA "
            "TANF program pages and the OPRE Welfare Rules Databook territory coverage). The Department of Human and "
            "Social Services site (http://dhss.as; the https host presents a self-signed, expired certificate, "
            "verification not disabled) lists no TANF program and its program pages are 'coming.html' placeholders. "
            "No territory TANF document exists to inventory; nothing was fetched. (2026-09-11 territories pass.)"
        ),
    },
    "us-mp": {
        "source_kind": "federal_statute_excludes_jurisdiction",
        "primary_source_url": USC_619_URL,
        "index_url": None,
        "index_document_count": None,
        "notes": (
            "Not applicable (recorded as blocked_primary_source because the queue schema has no not-applicable "
            "status): 42 U.S.C. 619(5) defines 'State' for title IV-A as the 50 States, the District of Columbia, "
            "Puerto Rico, the Virgin Islands, Guam and American Samoa; the Northern Mariana Islands is not a TANF "
            "jurisdiction and receives no TANF block grant (42 U.S.C. 619 is not in the corpus; cited from "
            "uscode.house.gov). No territory TANF document exists to inventory; nothing was fetched. (2026-09-11 "
            "territories pass.)"
        ),
    },
}


DROP_EAS = [
    r"^\d\d-\d\d\d\s+\(Cont\.\)\s.*$",
    r"^\d\d-\d\d\d\s+.*\s+Regulations$",
    r"^\d\d-\d\d\d\s+.*\((?:Continued|Cont\.)\)$",
    r"^Regulations\s+.*\s+\d\d-\d\d\d(?:\s+\(Cont\.\))?$",
    r"^CALIFORNIA-DSS-MANUAL-EAS$",
    r"^MANUAL LETTER NO\. .*$",
    r"^Page \d+$",
    r"^This page is intentionally left blank\.$",
]
EAS_EXTRACTION = {
    "segmentation": "styled_labeled_sections",
    "section_heading_pattern": r"^(?P<label>\d\d-\d\d\d)\s+(?P<heading>\S.*?)(?:\s+\d\d-\d\d\d)?$",
    # the EAS DOCX files style only some headings as Word headings; real section
    # headings are all-caps, cross-reference lines in body text are mixed case
    "heading_paragraphs_only": False,
    "heading_text_pattern": r"^[A-Z0-9][A-Z0-9 ,/&()'.;:-]*$",
    "drop_line_patterns": DROP_EAS,
}
CO_EXTRACTION = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r'^(?P<label>3\.6\d\d(?:\.\d{1,2})?)\s+(?P<heading>[A-Z“"][A-Za-z“"].*)$',
    "section_label_pattern": r"^(?P<label>3\.6\d\d(?:\.\d{1,2})?)$",
    "label_only_heading_pattern": r'^[A-Z“"].*$',
    "label_only_requires_heading": True,
    "drop_line_patterns": [
        r"^CODE OF COLORADO REGULATIONS$",
        r"^9 CCR 2503-6$",
        r"^Income Maintenance \(Volume 3\)$",
        r"^\d{1,3}$",
    ],
}
OK_EXTRACTION = {
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
        "segmentStatusId",
        "segmentTypeId",
        "recordStatus",
        "effectiveDate",
        "filingId",
        "hasEmergency",
        "segmentNotes",
    ],
}


def fetch(url: str, *, attempts: int = 3, head: bool = False) -> Any:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            if head:
                return curl_requests.head(
                    url, impersonate=IMPERSONATE, timeout=120, allow_redirects=True
                )
            return curl_requests.get(
                url, impersonate=IMPERSONATE, timeout=120, allow_redirects=True
            )
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def links(text: str) -> list[tuple[str, str]]:
    return [
        (href, re.sub(r"<[^>]+>", "", html.unescape(label)).strip())
        for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', text, re.S)
    ]


def http_date(value: str | None) -> str | None:
    if not value:
        return None
    return dt.datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z").date().isoformat()


def base_doc(
    *,
    source_id: str,
    jurisdiction: str,
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
        "jurisdiction": jurisdiction,
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
        "program": "TANF",
        "state_program": state_program,
        "federal_program": "TANF",
        "manual_landing_page": index_url,
        "source_discovery_group": f"{jurisdiction}/{document_class}/tanf",
        "discovered_via": DISCOVERED_VIA.format(index=index_url),
        **(extra or {}),
    }
    return doc


# --------------------------------------------------------------------------- CA
def build_ca() -> dict[str, Any]:
    index = (
        "https://www.cdss.ca.gov/inforesources/Rules-Regulations/Legislation-and-Regulations/"
        "CalWORKs-CalFresh-Regulations/Eligibility-and-Assistance-Standards"
    )
    page = fetch(index).text
    files = [
        (h, t) for h, t in links(page) if re.search(r"/Portals/9/Regs/Man/EAS/[^\"']+\.docx", h)
    ]
    docs = []
    for href, text in files:
        m = re.match(r"^(\d+)\.\s+(.*)$", text)
        if not m or not re.search(r"\bDiv(?:ision)?\s+4[0-4]\b", text):
            continue
        number, label = m.group(1), m.group(2)
        url = "https://www.cdss.ca.gov" + href if href.startswith("/") else href
        head = fetch(url, head=True)
        expression = http_date(head.headers.get("last-modified")) or SOURCE_AS_OF
        docs.append(
            base_doc(
                source_id=f"us-ca-cdss-mpp-eas-{number}",
                jurisdiction="us-ca",
                document_class="regulation",
                title=f"CDSS Manual of Policies and Procedures, Eligibility and Assistance Standards {number}: {label}",
                source_url=url,
                source_format="docx",
                citation_path=f"us-ca/regulation/mpp/eas/{number}",
                expression_date=expression,
                authority="California Department of Social Services",
                subtype="adopted_regulation_manual_docx",
                state_program="CalWORKs",
                index_url=index,
                extra={
                    "manual": "MPP Eligibility and Assistance Standards (Divisions 40-44 taken)",
                    "index_ordinal": int(number),
                    "source_last_modified": expression,
                    "extraction_note": "styled_labeled_sections merges page-break heading restatements; running heads dropped",
                },
                request={"browser_impersonation": True},
                extraction=EAS_EXTRACTION,
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(files),
        "inventory": f"{len(files)} EAS DOCX files (Div 40 through Div 91); taken {len(docs)} (Div 40-44, CalWORKs/AFDC eligibility and assistance standards); Div 46-91 (refugee, IHSS, adoptions, admin, hearings) not taken",
        "source_kind": "official_docx_regulation_manual",
        "document_class": "regulation",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- CO
def build_co() -> dict[str, Any]:
    index = (
        "https://www.coloradosos.gov/CCR/DisplayRule.do?action=ruleinfo&ruleId=3145&deptID=9&agencyID=53"
        "&deptName=Department+of+Human+Services&agencyName=Income+Maintenance+(Volume+3)&seriesNum=9+CCR+2503-6"
    )
    page = fetch(index).text
    versions = re.findall(r"OpenRuleWindow\('(\d+)'", page)
    dates = re.findall(r"(\d\d/\d\d/\d{4})\s*\(PDF\)", page)
    if not versions or not dates:
        raise RuntimeError("Colorado SoS rule-info page layout changed")
    current = versions[0]
    effective = dt.datetime.strptime(dates[0], "%m/%d/%Y").date().isoformat()
    url = f"https://www.coloradosos.gov/CCR/GenerateRulePdf.do?ruleVersionId={current}&fileName=9%20CCR%202503-6"
    doc = base_doc(
        source_id="us-co-ccr-9-2503-6-colorado-works",
        jurisdiction="us-co",
        document_class="regulation",
        title="Code of Colorado Regulations 9 CCR 2503-6 Colorado Works Program",
        source_url=url,
        source_format="pdf",
        citation_path="us-co/regulation/9-ccr-2503-6",
        expression_date=effective,
        authority="Colorado Department of Human Services",
        subtype="administrative_code_rule",
        state_program="Colorado Works",
        index_url=index,
        extra={
            "official_publisher": "Colorado Secretary of State",
            "code_rule": "9 CCR 2503-6",
            "rule_version_id": current,
            "rule_effective_date": effective,
            "archived_version_count": len(set(versions)) - 1,
            "extraction_note": "labeled_sections on 3.6xx / 3.6xx.y labels; editor's notes at the end fall into the last section",
        },
        extraction=CO_EXTRACTION,
    )
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(set(versions)),
        "inventory": f"SoS rule-info page: 1 current version (eff. {effective}, PDF+DOCX) and {len(set(versions)) - 1} archived versions; taken the current PDF",
        "source_kind": "official_pdf_regulation",
        "document_class": "regulation",
        "primary_source_url": url,
    }


# --------------------------------------------------------------------------- DC
def build_dc() -> dict[str, Any]:
    index = "https://dhs.dc.gov/publication/esa-policy-manuals"
    page = fetch(index).text
    pdfs = [(h, t) for h, t in links(page) if h.lower().endswith(".pdf")]
    target = [h for h, t in pdfs if "ESA-Policy-Manual-Combined" in h]
    if len(target) != 1:
        raise RuntimeError(f"expected one combined ESA manual link, found {target}")
    url = target[0]
    head = fetch(url, head=True)
    modified = http_date(head.headers.get("last-modified")) or SOURCE_AS_OF
    doc = base_doc(
        source_id="us-dc-dhs-esa-policy-manual",
        jurisdiction="us-dc",
        document_class="manual",
        title="District of Columbia DHS ESA Policy Manual (Combined, Revised 2)",
        source_url=url,
        source_format="pdf",
        citation_path="us-dc/manual/dhs/tanf/esa-policy-manual",
        expression_date=modified,
        authority="District of Columbia Department of Human Services, Economic Security Administration",
        subtype="policy_manual",
        state_program="DC TANF",
        index_url=index,
        extra={
            "source_last_modified": modified,
            "manual_scope": "ESA programs other than SNAP: TANF, Medical Assistance, GC, IDA, Burial Assistance",
            "extraction_granularity": "pdf_page",
            "extraction_note": "page-level; Part/Chapter headings restart numbering per part so chapter-level labels are not unique",
        },
    )
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(pdfs),
        "inventory": f"{len(pdfs)} PDFs on the ESA Policy Manuals page (ESA SNAP Policy Manual 1-24-25, already ingested as us-dc/manual/dhs/esa/snap-policy-manual; ESA Policy Manual Combined Revised 2); taken 1",
        "source_kind": "official_pdf_manual",
        "document_class": "manual",
        "primary_source_url": url,
    }


# --------------------------------------------------------------------------- MO
def build_mo(title_cache: Path | None) -> dict[str, Any]:
    index = "https://dssmanuals.mo.gov/temporary-assistance-case-management/"
    landing = fetch(index).text
    appendices = [
        (h, t)
        for h, t in links(landing)
        if h.lower().endswith(".pdf")
        and "dssmanuals.mo.gov" in h
        and re.match(r"^Appendix [A-Z]", t)
    ]
    sitemap = ""
    for n in (1, 2, 3):
        r = fetch(f"https://dssmanuals.mo.gov/wp-sitemap-posts-page-{n}.xml")
        if r.status_code != 200:
            break
        sitemap += r.text
    entries = re.findall(r"<url>\s*<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", sitemap)
    pages = [
        (u, m[:10])
        for u, m in entries
        if "/temporary-assistance-case-management/" in u and u.rstrip("/") != index.rstrip("/")
    ]
    cache: dict[str, Any] = {}
    if title_cache and title_cache.exists():
        cache = json.loads(title_cache.read_text())

    def title_for(url: str) -> str:
        cached = cache.get(url, {}).get("title")
        if cached:
            return cached
        r = fetch(url)
        m = re.search(r"<title>(.*?)</title>", r.text, re.S)
        time.sleep(0.2)
        return html.unescape(m.group(1)).strip() if m else url

    slugs = [u.rstrip("/").split("/")[-1] for u, _ in pages]
    numbers = [re.match(r"^(\d{4}-\d{2,3}-\d{2}(?:-\d{2,3})*)", s) for s in slugs]
    number_counts: dict[str, int] = {}
    for m in numbers:
        if m:
            number_counts[m.group(1)] = number_counts.get(m.group(1), 0) + 1
    docs = []
    docs.append(
        base_doc(
            source_id="us-mo-dss-tanf-landing",
            jurisdiction="us-mo",
            document_class="manual",
            title="Missouri Temporary Assistance/Case Management Manual (landing page and chapter index)",
            source_url=index,
            source_format="html",
            citation_path="us-mo/manual/dss/tanf/navigation/landing",
            expression_date=SOURCE_AS_OF,
            authority="Missouri Department of Social Services, Family Support Division",
            subtype="manual_landing_page_snapshot",
            state_program="Temporary Assistance",
            index_url=index,
            extraction={"html_content_selector": ".entry-content"},
        )
    )
    for (url, lastmod), slug, m in zip(pages, slugs, numbers, strict=True):
        suffix = m.group(1) if m and number_counts[m.group(1)] == 1 else slug
        title = title_for(url).replace(" – DSS Manuals", "").strip()
        docs.append(
            base_doc(
                source_id=f"us-mo-dss-tanf-{suffix}",
                jurisdiction="us-mo",
                document_class="manual",
                title=f"Missouri Temporary Assistance/Case Management Manual: {title}",
                source_url=url,
                source_format="html",
                citation_path=f"us-mo/manual/dss/tanf/{suffix}",
                expression_date=lastmod,
                authority="Missouri Department of Social Services, Family Support Division",
                subtype="policy_manual_section",
                state_program="Temporary Assistance",
                index_url=index,
                extra={
                    "sitemap_lastmod": lastmod,
                    "source_sitemap_urls": [
                        "https://dssmanuals.mo.gov/wp-sitemap-posts-page-1.xml",
                        "https://dssmanuals.mo.gov/wp-sitemap-posts-page-2.xml",
                    ],
                },
                extraction={"html_content_selector": ".entry-content"},
            )
        )
    for href, text in appendices:
        letter = re.match(r"^Appendix ([A-Z])", text).group(1).lower()
        head = fetch(href, head=True)
        modified = http_date(head.headers.get("last-modified")) or SOURCE_AS_OF
        docs.append(
            base_doc(
                source_id=f"us-mo-dss-tanf-appendix-{letter}",
                jurisdiction="us-mo",
                document_class="manual",
                title=f"Missouri Temporary Assistance/Case Management Manual: {text}",
                source_url=href,
                source_format="pdf",
                citation_path=f"us-mo/manual/dss/tanf/appendix-{letter}",
                expression_date=modified,
                authority="Missouri Department of Social Services, Family Support Division",
                subtype="policy_manual_appendix",
                state_program="Temporary Assistance",
                index_url=index,
                extra={"source_last_modified": modified, "extraction_granularity": "pdf_page"},
            )
        )
    total = 1 + len(pages) + len(appendices)
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": total,
        "inventory": f"landing page + {len(pages)} section pages (WordPress sitemap, chapters 0200-0330) + {len(appendices)} appendix PDFs; taken all {total}",
        "source_kind": "official_html_manual",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- MS
def build_ms() -> dict[str, Any]:
    index = "https://www.mdhs.ms.gov/help/tanf/"
    page = fetch(index).text
    manual = [h for h, t in links(page) if t.strip() == "TANF Policy Manual"]
    if len(set(manual)) != 1:
        raise RuntimeError(f"expected one TANF Policy Manual link, found {manual}")
    url = manual[0]
    head = fetch(url, head=True)
    modified = http_date(head.headers.get("last-modified")) or SOURCE_AS_OF
    doc_links = [(h, t) for h, t in links(page) if h.lower().endswith(".pdf") or "/document/" in h]
    doc = base_doc(
        source_id="us-ms-mdhs-tanf-policy-manual",
        jurisdiction="us-ms",
        document_class="manual",
        title="Mississippi TANF Policy Manual (Title 18 Part 13, Volume III)",
        source_url=url,
        source_format="pdf",
        citation_path="us-ms/manual/mdhs/tanf/volume-iii",
        expression_date=modified,
        authority="Mississippi Department of Human Services (published through the Mississippi Secretary of State administrative code)",
        subtype="policy_manual",
        state_program="Mississippi TANF",
        index_url=index,
        extra={
            "source_last_modified": modified,
            "extraction_granularity": "pdf_page",
            "extraction_note": "page-level; the manual is paginated by chapter (1000-, 2000- ...) without machine-stable section labels",
        },
        request={"browser_impersonation": True},
    )
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len({h for h, _ in doc_links}),
        "inventory": f"MDHS TANF page links {len({h for h, _ in doc_links})} documents (TANF Policy Manual on sos.ms.gov, flyer(s), client forms); taken the TANF Policy Manual",
        "source_kind": "official_pdf_manual",
        "document_class": "manual",
        "primary_source_url": url,
    }


# --------------------------------------------------------------------------- MT
def build_mt() -> dict[str, Any]:
    index = "https://dphhs.mt.gov/hcsd/Manuals/TANFpolicymanual"
    page = fetch(index).text
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        hrefs = re.findall(r'href="([^"]+)"', row)
        cells = [
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(c))).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        ]
        if hrefs and "tanfmanual" in hrefs[0]:
            cells = [c for c in cells if c]
            rows.append((hrefs[0], cells))
    docs = []
    seen: set[str] = set()
    for href, cells in rows:
        if len(cells) < 3:
            raise RuntimeError(f"unexpected Montana index row {cells}")
        label, title, date_text = cells[0], cells[1], cells[-1]
        if label in seen:
            raise RuntimeError(f"duplicate Montana section label {label}")
        seen.add(label)
        for fmt in ("%m/%d/%y", "%m/%d/%Y"):
            try:
                effective = dt.datetime.strptime(date_text, fmt).date().isoformat()
                break
            except ValueError:
                effective = SOURCE_AS_OF
        url = (
            "https://dphhs.mt.gov" + href.replace("../..", "") if href.startswith("../..") else href
        )
        docs.append(
            base_doc(
                source_id=f"us-mt-dphhs-tanf-{label.lower()}",
                jurisdiction="us-mt",
                document_class="manual",
                title=f"Montana TANF Policy Manual {label}: {title}",
                source_url=url,
                source_format="pdf",
                citation_path=f"us-mt/manual/dphhs/tanf/{label.lower()}",
                expression_date=effective,
                authority="Montana Department of Public Health and Human Services",
                subtype="policy_manual_section",
                state_program="Montana TANF",
                index_url=index,
                extra={
                    "official_section_number": label,
                    "official_listing_title": title,
                    "official_effective_date": date_text,
                    "extraction_granularity": "pdf_page",
                },
                request={"browser_impersonation": True},
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(rows),
        "inventory": f"{len(rows)} section PDFs listed with effective dates (TOC, index, introduction, definitions, income standards, sections 101-1 through 1702-1); taken all {len(docs)}",
        "source_kind": "official_pdf_manual_sections",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- ND
def build_nd() -> dict[str, Any]:
    base = "https://www.nd.gov/dhs/policymanuals/40019/"
    index = base + "40019.htm"
    toc_url = base + "Data/Tocs/40019_Chunk0.js"
    toc = fetch(toc_url).text
    entries = re.findall(r"'(/[^']+\.htm)':\{i:\[\d+\],t:\['((?:[^'\\]|\\.)*)'\]", toc)
    landing = fetch(base + "Default.htm").text
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(landing)))
    release = re.search(r"Current Release ([\d.]+)", text)
    published = re.search(r"last published on ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    release_log = fetch(base + "Release%20Log.htm").text
    log_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(release_log)))
    eff = re.search(r"(\d{2}\.\d)\s+(\d{1,2}\.\d{1,2}\.\d{4})", log_text)
    expression = (
        dt.datetime.strptime(eff.group(2), "%m.%d.%Y").date().isoformat() if eff else SOURCE_AS_OF
    )
    common = {
        "current_release": release.group(1) if release else None,
        "manual_last_published": published.group(1) if published else None,
        "manual_toc_url": toc_url,
        "manual_base_url": base,
    }
    docs = [
        base_doc(
            source_id="us-nd-hhs-tanf-landing",
            jurisdiction="us-nd",
            document_class="manual",
            title="North Dakota HHS TANF Policy Manual 400-19 landing page",
            source_url=base + "Default.htm",
            source_format="html",
            citation_path="us-nd/manual/hhs/tanf/navigation/landing",
            expression_date=expression,
            authority="North Dakota Health and Human Services",
            subtype="manual_landing_page_snapshot",
            state_program="North Dakota TANF",
            index_url=index,
            extra=common,
            extraction={"html_content_selector": "#mc-main-content"},
        ),
        base_doc(
            source_id="us-nd-hhs-tanf-toc",
            jurisdiction="us-nd",
            document_class="manual",
            title="North Dakota HHS TANF Policy Manual 400-19 official table of contents",
            source_url=toc_url,
            source_format="javascript",
            citation_path="us-nd/manual/hhs/tanf/navigation/toc",
            expression_date=expression,
            authority="North Dakota Health and Human Services",
            subtype="manual_toc_snapshot",
            state_program="North Dakota TANF",
            index_url=index,
            extra=common,
        ),
        base_doc(
            source_id="us-nd-hhs-tanf-release-log",
            jurisdiction="us-nd",
            document_class="manual",
            title="North Dakota HHS TANF Policy Manual 400-19 release log",
            source_url=base + "Release%20Log.htm",
            source_format="html",
            citation_path="us-nd/manual/hhs/tanf/navigation/release-log",
            expression_date=expression,
            authority="North Dakota Health and Human Services",
            subtype="manual_release_log_snapshot",
            state_program="North Dakota TANF",
            index_url=index,
            extra=common,
            extraction={"html_content_selector": "#mc-main-content"},
        ),
    ]
    seen: set[str] = set()
    for path, title in entries:
        name = path.lstrip("/")[: -len(".htm")]
        suffix = (
            name.replace("_", "-").lower()
            if re.match(r"^400_19(_\d+)*$", name)
            else re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        )
        if suffix in seen:
            raise RuntimeError(f"duplicate North Dakota topic {suffix}")
        seen.add(suffix)
        docs.append(
            base_doc(
                source_id=f"us-nd-hhs-tanf-{suffix}",
                jurisdiction="us-nd",
                document_class="manual",
                title=f"North Dakota TANF Policy Manual: {title.replace(chr(92) + chr(39), chr(39))}",
                source_url=base + path.lstrip("/"),
                source_format="html",
                citation_path=f"us-nd/manual/hhs/tanf/{suffix}",
                expression_date=expression,
                authority="North Dakota Health and Human Services",
                subtype="policy_manual_section",
                state_program="North Dakota TANF",
                index_url=index,
                extra=common,
                extraction={"html_content_selector": "#mc-main-content"},
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(entries) + 3,
        "inventory": f"MadCap TriPane manual: TOC lists {len(entries)} topic pages (400-19-05 definitions through the sanction/hearing sections) plus landing page and release log; taken all {len(docs)} (release {common['current_release']}, effective {expression})",
        "source_kind": "official_html_manual",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- OK
def build_ok() -> dict[str, Any]:
    index = "https://rules.ok.gov/home"
    api = "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=340&chapterNum=10"
    data = fetch(api).json()
    counts: dict[str, int] = {}
    for segment in data:
        key = f"{segment.get('name')}:{segment.get('statusName')}"
        counts[key] = counts.get(key, 0) + 1
    active_sections = sum(
        1
        for s in data
        if s.get("name") == "Section" and s.get("statusName") not in {"Revoked", "Reserved"}
    )
    doc = base_doc(
        source_id="us-ok-oac-340-10-tanf-rules",
        jurisdiction="us-ok",
        document_class="regulation",
        title="Oklahoma Administrative Code Title 340 Chapter 10 Temporary Assistance for Needy Families (TANF)",
        source_url=index,
        source_format="json",
        citation_path="us-ok/regulation/oac/340/10",
        expression_date=SOURCE_AS_OF,
        authority="Oklahoma Department of Human Services",
        subtype="administrative_code_chapter",
        state_program="Oklahoma TANF",
        index_url=index,
        extra={
            "official_publisher": "Oklahoma Secretary of State Office of Administrative Rules",
            "rules_api_url": api,
            "legacy_okdhs_chapter_url": "https://oklahoma.gov/okdhs/library/policy/current/oac-340/chapter-10.html",
            "title_number": "340",
            "chapter_number": "10",
            "segment_counts": counts,
            "access_note": "rules.ok.gov and the tecuity rules API answer plain clients with Cloudflare 403; fetched with browser impersonation (same API as us-ok-snap-rules)",
        },
        request={"browser_impersonation": True, "browser_impersonation_direct": True},
        extraction=OK_EXTRACTION,
    )
    doc["download_url"] = api
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(data),
        "inventory": f"chapter API returns {len(data)} segments ({counts}); taken the chapter as one document, {active_sections} non-revoked sections become records",
        "source_kind": "official_json_regulation",
        "document_class": "regulation",
        "primary_source_url": index,
    }


def slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def last_modified(url: str) -> str:
    head = fetch(url, head=True)
    return http_date(head.headers.get("last-modified")) or SOURCE_AS_OF


# --------------------------------------------------------------------------- PA
def build_pa() -> dict[str, Any]:
    """OIM Cash Assistance Handbook (Adobe RoboHelp site; TOC in whxdata/toc*.js like the SNAP handbook)."""
    base = "http://services.dpw.state.pa.us/oimpolicymanuals/cash/"
    index = base + "index.htm"
    fetch(index)  # the landing page is a JS shell; the TOC data files carry the inventory
    pages: dict[str, dict[str, Any]] = {}
    entries = 0

    def parse_toc(js: str) -> list[tuple[str, dict[str, str]]]:
        match = re.search(r'gXMLBuffer\s*=\s*"(.*)"\s*;?\s*$', js.strip(), re.S)
        # the JS string only escapes double quotes; file names contain literal UTF-8 (e.g. an en dash)
        xml = match.group(1).replace('\\"', '"') if match else js
        return [
            (kind, dict(re.findall(r'(\w+)="([^"]*)"', attrs)))
            for kind, attrs in re.findall(r"<(book|item)\s+([^>]*?)/?>", xml)
        ]

    def walk(src: str, parent: str | None) -> None:
        nonlocal entries
        for kind, attrs in parse_toc(fetch(base + "whxdata/" + src).text):
            entries += 1
            name = html.unescape(attrs.get("name", "")).strip()
            url = attrs.get("url")
            if url and "#" not in url and url not in pages:
                pages[url] = {"name": name, "parent": parent, "order": len(pages) + 1}
            if kind == "book" and attrs.get("src"):
                walk(attrs["src"], name)

    walk("toc.js", None)
    docs = []
    for url, info in pages.items():
        page_slug = slug(re.sub(r"\.htm$", "", url))
        full = base + url
        docs.append(
            base_doc(
                source_id=f"us-pa-dhs-cash-{page_slug}",
                jurisdiction="us-pa",
                document_class="manual",
                title=f"Pennsylvania Cash Assistance Handbook: {info['name']}",
                source_url=full,
                source_format="html",
                citation_path=f"us-pa/manual/dhs/cash/{page_slug}",
                expression_date=last_modified(full),
                authority="Pennsylvania Department of Human Services, Office of Income Maintenance",
                subtype="policy_manual_topic",
                state_program="Pennsylvania TANF (Cash Assistance)",
                index_url=index,
                extra={
                    "manual_toc_url": base + "whxdata/toc.js",
                    "manual_base_url": base,
                    "toc_parent": info["parent"],
                    "toc_order": info["order"],
                },
                extraction={"html_drop_selectors": [".topic-header", ".topic-header-shadow"]},
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(pages),
        "inventory": (
            f"RoboHelp TOC lists {entries} entries resolving to {len(pages)} topic pages (chapters 100-192, "
            f"including appendices; the remaining entries are in-page anchors); taken all {len(docs)} topic pages. "
            "Glossary pop-ups (_Popups/) are not on the TOC and were not taken"
        ),
        "source_kind": "official_html_manual",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- VA
def build_va() -> dict[str, Any]:
    index = "https://www.dss.virginia.gov/relief/tanf/tanf-manual/"
    page = fetch(index).text
    pdfs = [(h, t) for h, t in links(page) if h.lower().endswith(".pdf")]
    chapters = [(h, t) for h, t in pdfs if re.match(r"^Chapter \d+", t)]
    docs = []
    for href, text in chapters:
        number = re.match(r"^Chapter (\d+)", text).group(1)
        url = "https://www.dss.virginia.gov" + href if href.startswith("/") else href
        docs.append(
            base_doc(
                source_id=f"us-va-dss-tanf-manual-chapter-{number}",
                jurisdiction="us-va",
                document_class="manual",
                title=f"Virginia TANF Manual {text}",
                source_url=url,
                source_format="pdf",
                citation_path=f"us-va/manual/dss/tanf/chapter-{number}",
                expression_date=last_modified(url),
                authority="Virginia Department of Social Services",
                subtype="policy_manual_chapter",
                state_program="Virginia TANF",
                index_url=index,
                extra={
                    "chapter_number": int(number),
                    "official_listing_title": text,
                    "extraction_granularity": "pdf_page",
                    "extraction_note": "page-level; each page carries a transmittal date (e.g. 10/23) in its running head",
                },
                request={"browser_impersonation": True},
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(pdfs),
        "inventory": (
            f"{len(pdfs)} PDFs on the TANF Manual page: Contents (table of contents), Full Manual (combined file) and "
            f"{len(chapters)} chapter files (Chapter 100 through Chapter 1000, incl. VIEW chapters 900-1000); taken the "
            f"{len(docs)} chapter files (the Full Manual duplicates them; the Contents file is a TOC)"
        ),
        "source_kind": "official_pdf_manual_chapters",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- SD
def build_sd() -> dict[str, Any]:
    """ARSD article 67:10 from the Legislative Research Council rules API (one JSON per rule, HTML body)."""
    index = "https://sdlegislature.gov/Rules/Administrative/67:10"
    api = "https://sdlegislature.gov/api/Rules/"
    rules = []
    current = "67:10"
    while current and current.startswith("67:10"):
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
        docs.append(
            base_doc(
                source_id=f"us-sd-arsd-{'-'.join(parts)}",
                jurisdiction="us-sd",
                document_class="regulation",
                title=f"ARSD {number} {catchline}",
                source_url=f"https://sdlegislature.gov/Rules/Administrative/{number}",
                source_format="json",
                citation_path="us-sd/regulation/arsd/" + "/".join(parts),
                expression_date=SOURCE_AS_OF,
                authority="South Dakota Department of Social Services",
                subtype="administrative_rule_section",
                state_program="South Dakota TANF",
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
        )
        docs[-1]["download_url"] = api + number
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(rules),
        "inventory": (
            f"rules API chain from 67:10 returns {len(rules)} records ({counts}: B article, C chapters, D sections); "
            f"taken the {len(docs)} sections whose catchline is not Repealed/Transferred; not taken: the article and "
            f"chapter table-of-contents records and {len(skipped)} repealed/transferred sections ({', '.join(skipped)})"
        ),
        "source_kind": "official_json_regulation_sections",
        "document_class": "regulation",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- NH
def build_nh() -> dict[str, Any]:
    """DHHS Family Assistance Manual (RoboHelp WebHelp 5; TOC in whgdata/whlstt*.htm)."""
    root = "https://www.dhhs.nh.gov/fam_htm/"
    index = root + "newfam.htm"
    fetch(index)
    pages: dict[str, dict[str, Any]] = {}
    entries = 0
    n = 0
    while True:
        response = fetch(f"{root}whgdata/whlstt{n}.htm")
        if response.status_code != 200:
            break
        for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', response.text, re.S):
            entries += 1
            if href.startswith("whlstt"):
                continue
            path = href.split("#")[0]
            if path not in pages:
                pages[path] = {
                    "name": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(label))).strip(),
                    "toc_file": f"whlstt{n}.htm",
                }
        n += 1
    docs = []
    for path, info in pages.items():
        url = root + path.replace("../", "")
        page_slug = slug(re.sub(r"\.htm$", "", path.rsplit("/", 1)[-1]))
        docs.append(
            base_doc(
                source_id=f"us-nh-dhhs-fam-{page_slug}",
                jurisdiction="us-nh",
                document_class="manual",
                title=f"New Hampshire Family Assistance Manual: {info['name']}",
                source_url=url,
                source_format="html",
                citation_path=f"us-nh/manual/dhhs/fam/{page_slug}",
                expression_date=last_modified(url),
                authority="New Hampshire Department of Health and Human Services, Bureau of Family Assistance",
                subtype="policy_manual_topic",
                state_program="New Hampshire FANF",
                index_url=index,
                extra={
                    "manual_toc_url": root + "whgdata/whlstt0.htm",
                    "toc_file": info["toc_file"],
                    "manual_scope": "combined Family Assistance Manual: FANF cash assistance, medical assistance categories, NH child care scholarship",
                },
                # dhhs.nh.gov answers plain clients with an Akamai "Access Denied" 403
                request={"browser_impersonation": True},
                extraction={"html_drop_selectors": ["#header", ".no-print", ".navBtnCusStyle"]},
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(pages),
        "inventory": (
            f"WebHelp TOC ({n} list files, {entries} entries) resolves to {len(pages)} topic pages (Introduction, "
            f"100 Case Processing through 900 NH Child Care Scholarship, Glossary); taken all {len(docs)}. "
            "The linked SR (supervisory release) letters and 'Previous Policy' archive pages are separate families, not taken"
        ),
        "source_kind": "official_html_manual",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- ID
def build_id() -> dict[str, Any]:
    """IDAPA 16.03.08 from the Office of the Administrative Rules Coordinator's current-rules index (WordPress REST)."""
    import requests as plain_requests  # adminrules.idaho.gov rejects curl-cffi's chrome TLS profile; plain requests verify fine

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
    title_16 = [(h, t) for h, t in all_rules if h.startswith("/rules/current/16/")]
    target = [(h, t) for h, t in title_16 if h.endswith("/160308.pdf")]
    if len(target) != 1:
        raise RuntimeError(f"expected one IDAPA 16.03.08 link, found {target}")
    href, text = target[0]
    url = "https://adminrules.idaho.gov" + href
    head = plain_requests.head(url, timeout=60, headers=headers)
    modified = http_date(head.headers.get("last-modified")) or SOURCE_AS_OF
    body = plain_requests.get(url, timeout=120, headers=headers).content
    import fitz

    marks: dict[str, int] = {}
    with fitz.open(stream=body, filetype="pdf") as pdf:
        for pdf_page in pdf:
            for mark in re.findall(r"\((\d{1,2}-\d{1,2}-\d{2})\)", pdf_page.get_text("text")):
                marks[mark] = marks.get(mark, 0) + 1
    effective = SOURCE_AS_OF
    if marks:
        mark = max(marks, key=marks.get)
        effective = dt.datetime.strptime(mark, "%m-%d-%y").date().isoformat()
    doc = base_doc(
        source_id="us-id-dhw-idapa-16-03-08-tafi",
        jurisdiction="us-id",
        document_class="regulation",
        title=f"IDAPA {text}",
        source_url=url,
        source_format="pdf",
        citation_path="us-id/regulation/idapa/16/03/08",
        expression_date=effective,
        authority="Idaho Department of Health and Welfare",
        subtype="administrative_rules",
        state_program="Temporary Assistance for Families in Idaho (TAFI)",
        index_url=index,
        extra={
            "official_publisher": "Idaho Office of the Administrative Rules Coordinator",
            "idapa_chapter": "16.03.08",
            "source_last_modified": modified,
            "rule_effective_marks": marks,
            "extraction_note": "numbered_sections like the IDAPA 16.03.05 scope; the rule is short (TAFI plus LIHEAP standards) after Idaho's rule reduction",
        },
        extraction={
            "segmentation": "numbered_sections",
            "start_page": 3,
            "sort_text": True,
            "drop_lines": ["IDAHO ADMINISTRATIVE CODE", "Department of Health and Welfare"],
            "drop_line_patterns": [
                r"^Section [0-9]+\s+Page [0-9]+.*$",
                r"^IDAHO ADMINISTRATIVE CODE\s+IDAPA 16\.03\.08$",
                r"^Department of Health and Welfare\s+Federal Welfare Programs$",
                r"^16\.03\.08 – FEDERAL WELFARE PROGRAMS$",
                # reserved ranges carry no text; left in, the numbered_sections reader treats the
                # all-caps heading of the following section as a continuation of the reserved heading
                r"^\d{3}\. – \d{3}\.\s+\(RESERVED\)$",
                r"^TANF PROGRAM$",
                r"^LIHEAP$",
            ],
        },
    )
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(all_rules),
        "inventory": (
            f"OARC current-rules listing (REST fetch-documents, documentType currentRules) has {len(all_rules)} rule "
            f"chapters, {len(title_16)} under IDAPA 16 (Health and Welfare); taken IDAPA 16.03.08 Federal Welfare Programs "
            "(TAFI rule). Not taken: 16.03.04 Food Stamp Program and 16.03.05 AABD (already in the corpus) and the other title 16 chapters"
        ),
        "source_kind": "official_pdf_regulation",
        "document_class": "regulation",
        "primary_source_url": url,
    }


# --------------------------------------------------------------------------- LA
LA_POLICY_PARTS = ("B.", "C.", "E.", "F.", "G.", "J.", "M.", "N.", "P.", "S.")


def build_la() -> dict[str, Any]:
    """DCFS Economic Independence manual from the department's PowerDMS public document directory."""
    index = "https://public.powerdms.com/LADCFS/tree"
    listing_api = "https://public.powerdms.com/LADCFS/documents"
    data = fetch(listing_api).json()["data"]

    def trail(entry: dict[str, Any]) -> list[str]:
        crumbs = entry.get("breadcrumbs") or []
        return [step["name"] for step in crumbs[0]["trail"]] if crumbs else []

    ei = [d for d in data if len(trail(d)) >= 3 and trail(d)[1] == "Economic Independence (EI)"]
    families: dict[str, int] = {}
    for entry in ei:
        families[trail(entry)[2]] = families.get(trail(entry)[2], 0) + 1
    manual = [d for d in ei if trail(d)[2] == "4. Economic Independence" and len(trail(d)) >= 4]
    parts: dict[str, int] = {}
    for entry in manual:
        parts[trail(entry)[3]] = parts.get(trail(entry)[3], 0) + 1
    taken = [d for d in manual if trail(d)[3].startswith(LA_POLICY_PARTS)]
    taken.sort(key=lambda d: (trail(d)[3], trail(d)[4] if len(trail(d)) > 4 else "", d["name"]))
    docs = []
    seen: set[str] = set()
    for entry in taken:
        name = re.sub(r"\s+", " ", entry["name"]).strip()
        doc_slug = slug(name)
        if doc_slug in seen:
            raise RuntimeError(f"duplicate Louisiana document slug {doc_slug}")
        seen.add(doc_slug)
        crumbs = trail(entry)
        docs.append(
            base_doc(
                source_id=f"us-la-dcfs-ei-{entry['id']}",
                jurisdiction="us-la",
                document_class="manual",
                title=f"Louisiana DCFS Economic Independence Manual {name}",
                source_url=entry["publicUrl"],
                source_format="pdf",
                citation_path=f"us-la/manual/dcfs/ei/{doc_slug}",
                expression_date=SOURCE_AS_OF,
                authority="Louisiana Department of Children and Family Services",
                subtype="policy_manual_section",
                state_program="Louisiana FITAP",
                index_url=index,
                extra={
                    "official_publisher": "Louisiana DCFS public document directory (PowerDMS)",
                    "listing_api_url": listing_api,
                    "powerdms_document_id": entry["id"],
                    "manual_part": crumbs[3],
                    "manual_section": crumbs[4] if len(crumbs) > 4 else None,
                    "extraction_granularity": "pdf_page",
                    "extraction_note": "the effective date is printed in each document's header block; PowerDMS sends no Last-Modified",
                },
                request={"browser_impersonation": True},
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(data),
        "inventory": (
            f"PowerDMS listing has {len(data)} public documents; Economic Independence (EI) folder {len(ei)} in "
            f"{len(families)} families ({families}); the '4. Economic Independence' manual has {len(manual)} documents by "
            f"part ({parts}); taken the {len(docs)} policy documents in parts {', '.join(LA_POLICY_PARTS)} (eligibility, "
            "case processing, special households, case maintenance, nondiscrimination, charts, KCSP, reporting, STEP); "
            "not taken: Y forms and instructions, O DSNAP and K LaCAP (SNAP-only), and the other EI families"
        ),
        "source_kind": "official_pdf_manual_sections",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- RI
def build_ri() -> dict[str, Any]:
    """218-RICR-20-00-2 (Rhode Island Works) from the Department of State's RICR chapter listing and part page."""
    host = "https://rules.sos.ri.gov"
    index = host + "/organizations/chapter/218-20"
    chapter = fetch(index).text
    subchapters = re.findall(r'onclick="return get_parts\(this\)" id="([^"]+)"', chapter)
    if not subchapters:
        raise RuntimeError("no subchapter rows on the RICR chapter 218-20 page")
    parts: dict[str, str] = {}
    for sub in subchapters:
        # the chapter page loads each subchapter's parts table with this XHR
        listing = fetch(f"{host}/Organizations/get_parts/{sub}").text
        for href, label in links(listing):
            if "/Regulations/Part/" in href and not re.match(r"^Part \d+$", label):
                parts.setdefault(href.rstrip("/").rsplit("/", 1)[1], label)
    part_id = "218-20-00-2"
    if part_id not in parts:
        raise RuntimeError(f"{part_id} not in the chapter listing: {sorted(parts)}")
    part_url = f"{host}/regulations/part/{part_id}"
    page = fetch(part_url).text
    pdfs = sorted(set(re.findall(r"https://risos-apa-production-public\.s3\.amazonaws\.com/[^\"'<>& ]+\.pdf", page)))
    if len(pdfs) != 1:
        raise RuntimeError(f"expected one Download Regulation PDF, found {pdfs}")

    def pane(pane_id: str) -> str:
        match = re.search(rf'class="tab-pane[^"]*"[^>]*id="{pane_id}"[^>]*>(.*?)<div[^>]+class="tab-pane', page, re.S)
        text = re.sub(r"<[^>]+>", " | ", html.unescape(match.group(1) if match else ""))
        return re.sub(r"(\s*\|\s*)+", " | ", re.sub(r"\s+", " ", text))

    overview = pane("second")

    def field(label: str) -> str | None:
        match = re.search(re.escape(label) + r" \| ([^|]+) \|", overview)
        return match.group(1).strip() if match else None

    filing_type = field("Type of Filing")
    status = field("Regulation Status")
    effective_raw = field("Effective")
    if not effective_raw:
        raise RuntimeError(f"no effective date in the overview pane: {overview[:300]}")
    effective = dt.datetime.strptime(effective_raw, "%m/%d/%Y").date().isoformat()
    history = pane("four")
    filings = re.findall(r"(ACTIVE RULE|INACTIVE RULE) \| (?:EMERGENCY RULE \| )?([A-Za-z ]+) \| - effective from (\d{2}/\d{2}/\d{4})", history)
    amendments = [f for f in filings if f[1].strip() == "Amendment"]
    latest_amendment = (
        dt.datetime.strptime(amendments[0][2], "%m/%d/%Y").date().isoformat() if amendments else None
    )
    doc = base_doc(
        source_id="us-ri-dhs-riw-218-20-00-2",
        jurisdiction="us-ri",
        document_class="regulation",
        title=f"{parts[part_id]}",
        source_url=part_url,
        source_format="pdf",
        citation_path="us-ri/regulation/218-ricr/20/00/2",
        expression_date=effective,
        authority="Rhode Island Department of Human Services",
        subtype="administrative_regulation",
        state_program="Rhode Island Works (RIW)",
        index_url=index,
        extra={
            "official_publisher": "Rhode Island Department of State",
            "legal_identifier": "218-RICR-20-00-2",
            "filing_type": filing_type,
            "regulation_status": status,
            "regulation_effective_date": effective,
            "latest_amendment_effective_date": latest_amendment,
            "filing_history_count": len(filings),
            "pdf_last_modified": last_modified(pdfs[0]),
            "extraction_granularity": "pdf_page",
            "extraction_note": "the Download Regulation PDF of the active filing, page-level like the 218-RICR-20-00-1 SNAP scope",
        },
    )
    doc["download_url"] = pdfs[0]
    listing_text = "; ".join(f"Part {k.rsplit('-', 1)[1]} {v}" for k, v in sorted(parts.items(), key=lambda kv: int(kv[0].rsplit('-', 1)[1])))
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(parts),
        "inventory": (
            f"RICR Title 218 Chapter 20 (Individual and Family Support Programs), {len(subchapters)} subchapter(s), "
            f"{len(parts)} parts via the chapter page's get_parts listing ({listing_text}); taken Part 2 "
            f"({filing_type}, {status}, effective {effective}; {len(filings)} filings in the part's history, latest "
            f"Amendment effective {latest_amendment}); not taken: the other parts (SNAP already in the corpus as "
            "218-RICR-20-00-1; GPA, CCAP, SSI/SSP, refugee assistance, social services are other programs)"
        ),
        "source_kind": "official_pdf_regulation",
        "document_class": "regulation",
        "primary_source_url": part_url,
    }


# --------------------------------------------------------------------------- WI
def build_wi() -> dict[str, Any]:
    """DCF Wisconsin Works (W-2) Manual (Adobe RoboHelp 2022 responsive output; TOC in whxdata/toc.new.js + toc<N>.new.js)."""
    base = "https://dcf.wisconsin.gov/manuals/w-2-manual/Production/"
    index = base + "default.htm"
    policies_page = "https://dcf.wisconsin.gov/w2/partners/policy"
    listing = links(fetch(policies_page).text)
    manuals = [(h, t) for h, t in listing if "/manuals/" in h]
    if not any(h.endswith("/manuals/w-2-manual/Production/default.htm") for h, _ in manuals):
        raise RuntimeError(f"W-2 Manual link not on the DCF policies page: {manuals}")
    admin_code = [t for h, t in listing if "docs.legis.wisconsin.gov" in h]
    fetch(index)  # redirect shell; the TOC data files carry the inventory

    def load(key: str) -> list[dict[str, Any]]:
        js = fetch(base + f"whxdata/{key}.new.js").text
        match = re.search(r"var toc\s*=\s*(\[.*?\]);\s*window\.rh", js, re.S)
        if not match:
            raise RuntimeError(f"unexpected RoboHelp TOC file whxdata/{key}.new.js")
        return json.loads(match.group(1))

    pages: dict[str, dict[str, Any]] = {}
    books = 0
    items = 0

    def walk(key: str, parent: str | None) -> None:
        nonlocal books, items
        for entry in load(key):
            if entry.get("type") == "book":
                books += 1
                walk(entry["key"], entry["name"])
                continue
            items += 1
            url = (entry.get("url") or "").split("#")[0]
            if url and url not in pages:
                pages[url] = {"name": entry["name"], "parent": parent, "order": len(pages) + 1}

    walk("toc", None)
    docs = []
    seen: set[str] = set()
    for url, info in pages.items():
        page_slug = slug(re.sub(r"\.htm$", "", url))
        if page_slug in seen:
            raise RuntimeError(f"duplicate Wisconsin topic slug {page_slug}")
        seen.add(page_slug)
        full = base + url
        docs.append(
            base_doc(
                source_id=f"us-wi-dcf-w2-{page_slug}",
                jurisdiction="us-wi",
                document_class="manual",
                title=f"Wisconsin Works (W-2) Manual: {info['name']}",
                source_url=full,
                source_format="html",
                citation_path=f"us-wi/manual/dcf/w2/{page_slug}",
                expression_date=last_modified(full),
                authority="Wisconsin Department of Children and Families, Division of Family and Economic Security",
                subtype="policy_manual_topic",
                state_program="Wisconsin Works (W-2)",
                index_url=index,
                extra={
                    "manual_toc_url": base + "whxdata/toc.new.js",
                    "manual_base_url": base,
                    "policies_listing_page": policies_page,
                    "toc_parent": info["parent"],
                    "toc_order": info["order"],
                },
                extraction={
                    "html_content_selector": "#rh-topic",
                    # every topic starts with the master page's banner table (agency name and manual title) and
                    # RoboHelp expand-spots repeat the trigger text in a data-close-text span
                    "html_drop_selectors": ["#rh-topic > div:first-child > table:has(p.layout)", "span[data-close-text]"],
                },
            )
        )
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(pages),
        "inventory": (
            f"RoboHelp 2022 TOC (whxdata/toc.new.js plus {books} book files) lists {items} items resolving to "
            f"{len(pages)} topic pages (Welcome, chapters 01 Introduction through 18 Emergency Assistance and related "
            f"programs, appendices); taken all {len(docs)}. The DCF W-2 policies page also lists the EA Manual and the "
            f"TJ/TMJ Manual ({len(manuals)} manual links; separate programs) and {len(admin_code)} Wisconsin "
            "Administrative Code DCF chapter links (legislature host), not taken"
        ),
        "source_kind": "official_html_manual",
        "document_class": "manual",
        "primary_source_url": index,
    }


# =========================================================================== batch 4 (retry)
RETRY_STAMP = "2026-09-10T21:34Z"
RETRY_NOTE = f"Retried {RETRY_STAMP} from a US network (batch 4): the publisher answered plain and browser clients"


def plain_fetch(url: str, *, head: bool = False, timeout: int = 120, user_agent: str = "axiom-corpus-ingest") -> Any:
    """Plain ``requests`` fetch for hosts where curl-cffi's chrome TLS profile is not wanted (honours REQUESTS_CA_BUNDLE)."""
    import requests as plain_requests

    headers = {"User-Agent": user_agent}
    if head:
        return plain_requests.head(url, timeout=timeout, headers=headers, allow_redirects=True)
    response = plain_requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
    response.raise_for_status()
    return response


def heading_case(value: str) -> str:
    """Title-case an all-caps publisher heading, keeping program acronyms and lowercasing connectives."""
    small = {"and", "or", "of", "the", "to", "for", "with", "in", "on", "by", "a", "an"}
    keep = {"ADC", "EA", "EF", "TANF", "SNAP", "AABD", "EBT", "NMW", "NMAC", "GA", "LIHEAP", "SSI", "SSN", "DHHS", "HCA"}
    words = []
    for index, word in enumerate(value.split()):
        core = re.sub(r"[^A-Za-z]", "", word)
        if core.upper() in keep:
            words.append(word)
        elif index and word.lower() in small:
            words.append(word.lower())
        elif word.isupper():
            words.append("-".join(part.capitalize() for part in word.split("-")))
        else:
            words.append(word)
    return " ".join(words)


# --------------------------------------------------------------------------- SC
def build_sc() -> dict[str, Any]:
    """SC DSS TANF Policy Manual (one PDF volume) from the DSS manuals page."""
    host = "https://dss.sc.gov"
    index = host + "/about/data-and-resources/manuals/"
    page = fetch(index).text
    pdfs = [(h, t) for h, t in links(page) if h.lower().endswith(".pdf")]
    tanf = [(h, t) for h, t in pdfs if re.search(r"tanf-policy-manual-volume-\d+", h)]
    if len(tanf) != 1:
        raise RuntimeError(f"expected one TANF Policy Manual link on the DSS manuals page, found {tanf}")
    href, title = tanf[0]
    volume = int(re.search(r"volume-(\d+)", href).group(1))
    url = host + href
    modified = last_modified(url)
    doc = base_doc(
        source_id=f"us-sc-dss-tanf-policy-manual-volume-{volume}",
        jurisdiction="us-sc",
        document_class="manual",
        title=f"South Carolina {title} (Volume {volume})",
        source_url=url,
        source_format="pdf",
        citation_path="us-sc/manual/dss/tanf-policy-manual",
        expression_date=modified,
        authority="South Carolina Department of Social Services",
        subtype="policy_manual",
        state_program="South Carolina TANF (Family Independence)",
        index_url=index,
        extra={
            "manual_volume": volume,
            "official_listing_title": title,
            "listing_section": "Economic Services Policy and Procedure Manuals",
            "source_last_modified": modified,
            "extraction_granularity": "pdf_page",
            "extraction_note": "page-level like the us-sc SNAP manual scope (SNAP manual volume 71 on the same page)",
            "superseded_lead_url": "https://dss.sc.gov/media/ojqddxsk/tanf-policy-manual-volume-65.pdf",
        },
    )
    return {
        "docs": [doc],
        "index_url": index,
        "index_document_count": len(pdfs),
        "inventory": (
            f"{len(pdfs)} PDF documents on the DSS manuals page (APS policies, SNAP manual volume 71 - already in the corpus "
            f"as the us-sc SNAP manual scope -, DSNAP manual, TANF Policy Manual volume {volume}, SNAP/TANF Benefit Integrity "
            f"manual, Refugee Resettlement manual, SC Voucher manual, child welfare documents); taken the TANF Policy Manual "
            f"(volume {volume}, HTTP Last-Modified {modified}; the lead list's volume 65 URL still serves the superseded "
            f"volume). {RETRY_NOTE}"
        ),
        "source_kind": "official_pdf_manual",
        "document_class": "manual",
        "primary_source_url": url,
    }


# --------------------------------------------------------------------------- KY
KY_VOLUMES = {
    "III": ("volume-iii-ktap", "Kentucky Transitional Assistance Program (KTAP)"),
    "IIIA": ("volume-iiia-kwp", "Kentucky Works Program (KWP)"),
}


def build_ky() -> dict[str, Any]:
    """CHFS DCBS Division of Family Support Operation Manual volumes III (KTAP) and IIIA (KWP) from the DFS page."""
    import fitz

    host = "https://www.chfs.ky.gov"
    index = host + "/agencies/dcbs/dfs/Pages/default.aspx"
    page = plain_fetch(index).text
    volumes = []
    for href, text in links(page):
        match = re.match(r"^DFS Manual Volume (\S+) - (.*?)(?:\s*\(PDF\))?$", text)
        if match and "/documents/omvol" in href.lower():
            volumes.append((match.group(1), match.group(2), host + href if href.startswith("/") else href))
    if not volumes:
        raise RuntimeError("no DFS Manual Volume links on the DFS page")
    docs = []
    for numeral, (slug_part, program) in KY_VOLUMES.items():
        hits = [v for v in volumes if v[0] == numeral]
        if len(hits) != 1:
            raise RuntimeError(f"Volume {numeral} not listed once on the DFS page: {volumes}")
        _, listing_title, url = hits[0]
        body = plain_fetch(url).content
        head = plain_fetch(url, head=True)
        modified = http_date(head.headers.get("Last-Modified"))
        with fitz.open(stream=body, filetype="pdf") as pdf:
            pages = len(pdf)
            first = pdf[0].get_text("text")
        omtl = re.search(r"OMTL-(\d+)", first)
        revised = re.search(r"R\.\s*(\d{1,2})/(\d{1,2})/(\d{2})", first)
        revision = f"20{revised.group(3)}-{int(revised.group(1)):02d}-{int(revised.group(2)):02d}" if revised else None
        docs.append(
            base_doc(
                source_id=f"us-ky-dcbs-dfs-om-vol-{numeral.lower()}",
                jurisdiction="us-ky",
                document_class="manual",
                title=f"Kentucky DFS Operation Manual Volume {numeral} - {listing_title}",
                source_url=url,
                source_format="pdf",
                citation_path=f"us-ky/manual/dcbs/dfs/{slug_part}",
                expression_date=modified or SOURCE_AS_OF,
                authority="Kentucky Department for Community Based Services, Division of Family Support",
                subtype="policy_manual_volume",
                state_program=program,
                index_url=index,
                extra={
                    "manual_volume": numeral,
                    "official_listing_title": listing_title,
                    "manual_revision_date": revision,
                    "latest_omtl": omtl.group(1) if omtl else None,
                    "pdf_page_count": pages,
                    "source_last_modified": modified,
                    "extraction_granularity": "pdf_page",
                    "extraction_note": "page-level like the us-ky SNAP manual scope (volumes II and IIA from the same page)",
                },
            )
        )
    listing = "; ".join(f"Vol. {n} {t}" for n, t, _ in volumes)
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(volumes),
        "inventory": (
            f"{len(volumes)} Operation Manual volumes linked from the DFS page ({listing}); taken Volume III (KTAP) and "
            f"Volume IIIA (KWP, the KTAP work program). Not taken: volumes I (general administration), II/IIA (SNAP, already "
            f"in the corpus), IV/IVA/IVB (Medicaid), V (State Supplementation), VIII (CCAP), IX (OMTL cover letters), X "
            f"(policy updates). The lead list's opmanual.aspx index is now HTTP 404 (the K-TAP program page moved to "
            f"/agencies/dcbs/dfs/fssb/Pages/ktap.aspx and links the Policy Development Branch); the DFS page carries the "
            f"volume list. {RETRY_NOTE} (no Azure Front Door 403)"
        ),
        "source_kind": "official_pdf_manual_volumes",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- TN
def build_tn() -> dict[str, Any]:
    """TDHS Families First policy manual: the 23-series policy PDFs on the DHS publications page."""
    host = "https://www.tn.gov"
    index = host + "/humanservices/information-and-resources/dhs-publications.html"
    page = fetch(index).text
    pdfs = [(h, t) for h, t in links(page) if ".pdf" in h.lower()]
    family = []
    for href, text in pdfs:
        match = re.search(r"/23\.(\d\d)[ _%]", href)
        if match:
            family.append((int(match.group(1)), href, text))
    family.sort()
    if not family:
        raise RuntimeError("no 23-series Families First policy PDFs on the DHS publications page")
    docs = []
    for number, href, text in family:
        url = href if href.startswith("http") else host + href
        label = re.sub(r"\s+", " ", text.replace("_", " ")).strip()
        modified = last_modified(url)
        docs.append(
            base_doc(
                source_id=f"us-tn-dhs-families-first-23-{number:02d}",
                jurisdiction="us-tn",
                document_class="manual",
                title=f"Tennessee Families First Policy Manual: {label}",
                source_url=url,
                source_format="pdf",
                citation_path=f"us-tn/manual/dhs/families-first/23-{number:02d}",
                expression_date=modified,
                authority="Tennessee Department of Human Services",
                subtype="policy_manual_section",
                state_program="Families First",
                index_url=index,
                extra={
                    "policy_series": "23",
                    "policy_number": f"23.{number:02d}",
                    "official_listing_title": text,
                    "listing_section": "Families First (TANF)",
                    "source_last_modified": modified,
                    "extraction_granularity": "pdf_page",
                    "extraction_note": "page-level like the us-tn SNAP policy manual scope (24-series on the same page)",
                },
            )
        )
    numbers = ", ".join(f"23.{n:02d}" for n, _, _ in family)
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(pdfs),
        "inventory": (
            f"{len(pdfs)} PDF documents on the DHS publications page (APS, SSBG, CREVAA, child care, child support, "
            f"Families First, SNAP and departmental policies); the Families First (TANF) section lists {len(family)} "
            f"23-series policies ({numbers}; 23.08-23.10, 23.15 and 23.20 are not published), taken all {len(docs)}. Not "
            f"taken: the 24-series SNAP policies (already in the corpus) and the other program sections. {RETRY_NOTE} "
            f"(no read timeout)"
        ),
        "source_kind": "official_pdf_manual_sections",
        "document_class": "manual",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- VT
VT_TANF_RULES = range(2000, 2501)


def build_vt() -> dict[str, Any]:
    """DCF Economic Services Division adopted rules 2000-2500 (Reach Up family) from the Current ESD Rules page."""
    index = "https://dcf.vermont.gov/esd/laws-rules/current"
    page = fetch(index).text
    rule_pdfs = [(h, t) for h, t in links(page) if "/ESD/Rules/" in h and h.lower().endswith(".pdf")]
    numbered = []
    for href, text in rule_pdfs:
        match = re.search(r"/Rules/(\d{4})-", href)
        if match:
            numbered.append((int(match.group(1)), href, text))
    numbered.sort()
    taken = [n for n in numbered if n[0] in VT_TANF_RULES]
    if len(taken) != 6:
        raise RuntimeError(f"expected the six 2000-2500 rule files, found {taken}")
    docs = []
    for number, href, text in taken:
        modified = http_date(plain_fetch(href, head=True).headers.get("Last-Modified"))
        docs.append(
            base_doc(
                source_id=f"us-vt-dcf-esd-rule-{number}",
                jurisdiction="us-vt",
                document_class="regulation",
                title=f"Vermont DCF Economic Services Division Rules {number}: {text}",
                source_url=href,
                source_format="pdf",
                citation_path=f"us-vt/regulation/dcf/esd-rules/{number}",
                expression_date=modified or SOURCE_AS_OF,
                authority="Vermont Department for Children and Families, Economic Services Division",
                subtype="administrative_rule",
                state_program="Reach Up (Reach First, Reach Up Services, Postsecondary Education, Reach Ahead)",
                index_url=index,
                extra={
                    "rule_series": number,
                    "official_listing_title": text,
                    "file_host": "outside.vermont.gov (DCF SharePoint document library)",
                    "source_last_modified": modified,
                    "extraction_granularity": "pdf_page",
                    "extraction_note": "page-level; the 2000 series carries the all-programs general rules",
                },
            )
        )
    listing = "; ".join(f"{n} {t}" for n, _, t in numbered)
    others = [t for h, t in rule_pdfs if not re.search(r"/Rules/\d{4}-", h)]
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(rule_pdfs),
        "inventory": (
            f"{len(rule_pdfs)} rule PDFs linked from the Current ESD Rules page: {len(numbered)} numbered rule files "
            f"({listing}) plus {', '.join(others)}; the page also links the 3SquaresVT manual (already in the corpus). "
            f"Taken the six TANF-family files 2000-2500; not taken 2600-3100 (GA, AABD, EA, fuel, refugee cash) and the "
            f"other two documents. {RETRY_NOTE} (outside.vermont.gov served every file, HTTP 200 application/pdf; no F5 "
            f"rejection)"
        ),
        "source_kind": "official_pdf_regulation",
        "document_class": "regulation",
        "primary_source_url": index,
    }


# --------------------------------------------------------------------------- NM
NM_HEADING_PATTERN = (
    r"^(?P<label>8\.\s*102\.\s*{part}\.\s*\d+(?:\s*-\s*\d+)?)\s+(?P<heading>[A-Z][^:]{{0,180}}:|\[RESERVED\]|"
    r"[A-Z][A-Z0-9 /()\[\]\-–—,'&]{{0,180}})(?:\s+(?P<body>.*))?$"
)


def build_nm() -> dict[str, Any]:
    """NMAC 8.102 Cash Assistance Programs: parts listed on the HCA Income Support Division page, files from SRCA."""
    index = "https://www.hca.nm.gov/lookingforinformation/income-support-division-1/"
    page = plain_fetch(index).text
    parts = [(h, t) for h, t in links(page) if "srca.nm.gov/parts/title08/" in h]
    family = []
    for href, text in parts:
        match = re.search(r"/08\.102\.(\d{4})\.html$", href)
        if match:
            family.append((int(match.group(1)), href, text))
    family.sort()
    if not family:
        raise RuntimeError("no 8.102 part links on the HCA ISD page")
    docs = []
    for part, href, text in family:
        response = plain_fetch(href)
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(response.text)))
        match = re.search(r"CHAPTER 102 CASH ASSISTANCE PROGRAMS PART (\d+) (.+?) (?:&nbsp; )?8\.102\.\d+\.1 ", body)
        if not match or int(match.group(1)) != part:
            raise RuntimeError(f"part heading not found in {href}: {body[:300]}")
        part_title = heading_case(match.group(2).strip())
        modified = http_date(response.headers.get("Last-Modified"))
        docs.append(
            base_doc(
                source_id=f"us-nm-srca-nmac-8-102-{part}",
                jurisdiction="us-nm",
                document_class="regulation",
                title=f"8.102.{part} NMAC {part_title}",
                source_url=href,
                source_format="html",
                citation_path=f"us-nm/regulation/nmac/8/102/{part}",
                expression_date=modified or SOURCE_AS_OF,
                authority="New Mexico Health Care Authority",
                subtype="administrative_code_part",
                state_program="New Mexico Works (NMW) cash assistance",
                index_url=index,
                extra={
                    "official_publisher": "New Mexico State Records Center and Archives",
                    "nmac_citation": f"8.102.{part}",
                    "nmac_title": "8",
                    "nmac_chapter": "102",
                    "nmac_part": str(part),
                    "official_listing_title": text,
                    "nmac_title_index_url": "https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/",
                    "nmac_chapter_index_url": "https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/chapter-102-cash-assistance-programs/",
                    "source_last_modified": modified,
                    "extraction_note": "labeled sections like the us-nm SNAP regulations scope (8.100 and 8.139 parts)",
                },
                extraction={
                    "html_content_selector": ".WordSection1, .Section1",
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": NM_HEADING_PATTERN.format(part=part),
                    "normalize_label_internal_whitespace": True,
                },
            )
        )
    chapters: dict[str, int] = {}
    for href, _ in parts:
        chapter = re.search(r"/08\.(\d{3})\.", href)
        if chapter:
            chapters[chapter.group(1)] = chapters.get(chapter.group(1), 0) + 1
    chapter_text = ", ".join(f"8.{c} x{n}" for c, n in sorted(chapters.items()))
    return {
        "docs": docs,
        "index_url": index,
        "index_document_count": len(parts),
        "inventory": (
            f"HCA Income Support Division page lists {len(parts)} SRCA NMAC part files ({chapter_text}); the 8.102 Cash "
            f"Assistance Programs family has {len(family)} parts ({', '.join(str(p) for p, _, _ in family)}), taken all. "
            f"Not taken: 8.100 general provisions and 8.139 SNAP (already in the corpus as us-nm SNAP regulations), 8.106 "
            f"(GA), 8.119 (LIHEAP), 8.150 (child care). The SRCA chapter page itself lists only reserved ranges (its "
            f"listing is a vendor RealFile widget); the agency-published parts index resolves the batch-2 review question"
        ),
        "source_kind": "official_html_regulation_parts",
        "document_class": "regulation",
        "primary_source_url": "https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/chapter-102-cash-assistance-programs/",
    }


# --------------------------------------------------------------------------- NE
NE_SECTION_PATTERN = (
    r"^(?P<label>0\d{2}(?:\.\d{1,2})?(?:\([A-Za-z0-9]+\))*)\.?\s+"
    r"(?P<heading>[A-Z][A-Z0-9 ’'&,/()\-–‑§]+?(?:\.(?=\s|$)|$))(?:\s+(?P<body>.*))?$"
)
NE_CONTINUATION_PATTERN = (
    r"^(?P<heading>[A-Z][A-Z0-9 ’'&,/()\-–‑§$]+?(?:\.(?=\s|$)|$))(?:\s+(?P<body>.*))?$"
)


def build_ne() -> dict[str, Any]:
    """468 NAC (ADC) chapters from the Secretary of State's rules.nebraska.gov API (the app is client-rendered)."""
    import os
    from urllib.parse import quote

    if not os.environ.get("REQUESTS_CA_BUNDLE"):
        raise RuntimeError(
            "rules.nebraska.gov serves only its leaf certificate: set REQUESTS_CA_BUNDLE to certifi's cacert.pem "
            "concatenated with data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem"
        )
    api = "https://rules.nebraska.gov/api"
    titles = plain_fetch(f"{api}/title/GetByAgencyId/37").json()["output"]
    adc = [t for t in titles if t["titleNumber"] == 468]
    if len(adc) != 1:
        raise RuntimeError(f"title 468 not listed once for agency 37: {adc}")
    title_id = adc[0]["id"]
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
            base_doc(
                source_id=f"us-ne-dhhs-468-nac-chapter-{number}",
                jurisdiction="us-ne",
                document_class="regulation",
                title=f"Nebraska Title 468 NAC Chapter {number}: {heading_case(chapter['chapterName'])}",
                source_url=url,
                source_format="pdf",
                citation_path=f"us-ne/regulation/title-468/chapter-{number}",
                expression_date=effective,
                authority="Nebraska Department of Health and Human Services",
                subtype="filed_administrative_regulation_chapter",
                state_program="Aid to Dependent Children (ADC)",
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
                    "extraction_note": "labeled sections with the 475 NAC SNAP scope's heading patterns (no signature-page drop lines: these blobs are the unsigned chapter files)",
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
        "inventory": (
            f"DHHS (agency 37) has {len(titles)} titles on rules.nebraska.gov; title 468 Aid to Dependent Children (ADC) "
            f"has {len(chapters)} chapters ({listing}); taken all {len(docs)} as the publisher's chapter PDF blobs (the API "
            f"carries no signed official blob for this title). Not taken: 469 AABD, 470 refugee programs, 475 SNAP "
            f"(already in the corpus). {RETRY_NOTE} (HTTP 200 JSON and PDF with the repaired chain; no Azure gateway 403)"
        ),
        "source_kind": "official_pdf_regulation",
        "document_class": "regulation",
        "primary_source_url": landing,
    }


# --------------------------------------------------------------------------- OR (descriptor; extracted by the OAR adapter)
def build_or() -> dict[str, Any]:
    """OAR chapter 461 descriptor: the existing extract-oregon-administrative-rules adapter does the extraction."""
    chapter_url = "https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=90"
    page = plain_fetch(chapter_url, user_agent="axiom-corpus/0.1 (max@axiom-foundation.org)").text
    divisions = sorted(set(re.findall(r"Division (\d+)(?:&nbsp;|\s)*-(?:&nbsp;|\s)*([^<]+?)\s*<", page)), key=lambda d: int(d[0]))
    rules = set(re.findall(r"ruleVrsnRsn=(\d+)", page))
    if not divisions or not rules:
        raise RuntimeError("OARD chapter 461 listing did not parse")
    run_id = f"{VERSION}-chapter-461"
    doc = base_doc(
        source_id="us-or-odhs-oar-chapter-461",
        jurisdiction="us-or",
        document_class="regulation",
        title="Oregon Administrative Rules Chapter 461: Department of Human Services, Self-Sufficiency Programs",
        source_url=chapter_url,
        source_format="html",
        citation_path="us-or/regulation/chapter-461",
        expression_date=SOURCE_AS_OF,
        authority="Oregon Department of Human Services, Self-Sufficiency Programs",
        subtype="administrative_rules_chapter",
        state_program="Oregon TANF (chapter 461 is the combined self-sufficiency rulebook: TANF, SNAP, ERDC, REF, TA-DVS and related programs)",
        index_url=chapter_url,
        extra={
            "official_publisher": "Oregon Secretary of State, Oregon Administrative Rules Database (OARD)",
            "extraction_adapter": "extract-oregon-administrative-rules --only-chapter 461",
            "extraction_run_id": run_id,
            "division_count": len(divisions),
            "rule_count": len(rules),
            "agency_rule_site": "https://ch461rules.odhs.oregon.gov/ (ODHS: displays unofficial rules and refers to the Secretary of State for the official text)",
            "extraction_note": "descriptor manifest, like manifests/us-oh-snap-rules.yaml for the OAC adapter: division and rule rows come from the OAR adapter, not from extract-official-documents",
        },
    )
    listing = "; ".join(f"{n} {html.unescape(t).strip()}" for n, t in divisions)
    return {
        "docs": [doc],
        "version": run_id,
        "index_url": chapter_url,
        "index_document_count": len(rules),
        "inventory": (
            f"OARD chapter 461 listing: {len(divisions)} divisions ({listing}), {len(rules)} current rules; taken the whole "
            f"chapter (combined rulebook, as combined manuals were taken whole in batches 1-3) through the existing OAR "
            f"adapter, run id {run_id}. The lead list's ODHS rule site (ch461rules.odhs.oregon.gov) answers too but "
            f"labels itself unofficial. {RETRY_NOTE} (both oregon.gov hosts resolve; no DNS failure)"
        ),
        "source_kind": "official_html_regulation_chapter",
        "document_class": "regulation",
        "primary_source_url": chapter_url,
    }


# --------------------------------------------------------------------------- OH (descriptor; extracted by the OAC adapter)
OH_EMANUALS_FAILURE = (
    f"emanuals.jfs.ohio.gov retried {RETRY_STAMP} from a US network: TCP connects but the TLS handshake is dropped "
    "(plain requests SSLError after 12 s; curl-cffi chrome 'curl: (35) TLS connect error'; curl 'SSL_ERROR_SYSCALL' on the "
    "ClientHello; http:// 'Empty reply from server'), so the Cash Assistance Manual stays unreachable"
)


def build_oh() -> dict[str, Any]:
    """OAC 5101:1 descriptor: the existing extract-ohio-administrative-code adapter does the extraction."""
    host = "https://codes.ohio.gov"
    agency_url = host + "/ohio-administrative-code/5101:1"
    page = plain_fetch(agency_url, user_agent="axiom-corpus/0.1 (max@axiom-foundation.org)").text
    chapters = []
    for href, text in links(page):
        if re.match(r"^/ohio-administrative-code/chapter-5101:1-\d+$", href):
            chapters.append((href.rsplit("-", 1)[1], re.sub(r"\s*\|\s*", " | ", text), host + href))
    if not chapters:
        raise RuntimeError("no 5101:1 chapter links on codes.ohio.gov")
    rule_count = 0
    for _, _, url in chapters:
        rule_count += len(set(re.findall(r'href="/ohio-administrative-code/rule-5101:1-[\d.\-]+"', plain_fetch(url, user_agent="axiom-corpus/0.1 (max@axiom-foundation.org)").text)))
    run_id = f"{VERSION}-agency-5101-1"
    doc = base_doc(
        source_id="us-oh-odjfs-oac-5101-1",
        jurisdiction="us-oh",
        document_class="regulation",
        title="Ohio Administrative Code 5101:1 Division of Public Assistance",
        source_url=agency_url,
        source_format="html",
        citation_path="us-oh/regulation/agency-5101-1",
        expression_date=SOURCE_AS_OF,
        authority="Ohio Department of Job and Family Services",
        subtype="administrative_code_agency",
        state_program="Ohio Works First (OWF)",
        index_url=agency_url,
        extra={
            "official_publisher": "Ohio Laws and Administrative Rules (Legislative Service Commission)",
            "code_agency": "5101:1",
            "extraction_adapter": "extract-ohio-administrative-code --only-agency 5101:1",
            "extraction_run_id": run_id,
            "chapter_count": len(chapters),
            "rule_count": rule_count,
            "agency_manual": "https://emanuals.jfs.ohio.gov/CashFoodAssist/CAM/ (ODJFS Cash Assistance Manual; " + OH_EMANUALS_FAILURE + ")",
            "extraction_note": "descriptor manifest like manifests/us-oh-snap-rules.yaml (OAC 5101:4): chapter and rule rows come from the OAC adapter",
        },
    )
    listing = "; ".join(f"5101:1-{n} {t.split(' | ')[-1].strip()}" for n, t, _ in chapters)
    return {
        "docs": [doc],
        "version": run_id,
        "index_url": agency_url,
        "index_document_count": rule_count,
        "inventory": (
            f"codes.ohio.gov agency 5101:1 Division of Public Assistance: {len(chapters)} chapters ({listing}), "
            f"{rule_count} rule links on the chapter pages; taken the whole agency division through the existing OAC "
            f"adapter, run id {run_id} (as the us-oh SNAP scope took 5101:4). {OH_EMANUALS_FAILURE}; the OAC rules are "
            f"the adopted text the CAM reproduces"
        ),
        "source_kind": "official_html_regulation_agency",
        "document_class": "regulation",
        "primary_source_url": agency_url,
    }


# --------------------------------------------------------------------------- GU (territories pass)
GU_BES_INDEX = "https://dphss.guam.gov/bureau-economic-security-bes"
TERRITORY_PLAN_VERSION = "2026-09-11-tanf-territory-state-plan"
TERRITORY_REGULATION_VERSION = "2026-09-11-tanf-territory-regulation"


def build_gu() -> dict[str, Any]:
    """Guam DPHSS Bureau of Economic Security: the certified TANF State Plan renewal for FY 2024-2026
    ("FY26 TANF State Plan" under Program State Plans). The same page's "FY26 SNAP State Plan" entry
    carries no link (commented-out anchor); the SNAP E&T plan and the application/change-report forms
    are other families. Guam publishes no TANF policy manual; the plan is its primary policy document."""
    page = fetch(GU_BES_INDEX).text
    pdfs = list({h: (h, t) for h, t in links(page) if h.lower().endswith(".pdf")}.values())  # unique by href
    target = [h for h, t in pdfs if "TANF State Plan" in t]
    if len(target) != 1:
        raise RuntimeError(f"expected one TANF State Plan link on the BES page, found {target}")
    url = urljoin(GU_BES_INDEX, target[0])
    head = fetch(url, head=True)
    modified = http_date(head.headers.get("last-modified"))
    doc = base_doc(
        source_id="us-gu-dphss-tanf-state-plan-fy2024-2026",
        jurisdiction="us-gu",
        document_class="policy",
        title="Guam TANF State Plan Renewal, FY 2024-2026 (final, certified)",
        source_url=url,
        source_format="pdf",
        citation_path="us-gu/policy/acf/tanf-plan/fy2024-2026",
        expression_date="2023-10-01",
        authority="Guam Department of Public Health and Social Services, Division of Public Welfare, Bureau of Economic Security",
        subtype="state_plan_pdf",
        state_program="Guam TANF (Cash Assistance Program)",
        index_url=GU_BES_INDEX,
        extraction={"ocr": True},
        extra={
            "plan_period": "2023-10-01 to 2026-09-30",
            "plan_status": "final certified renewal submitted to ACF OFA (cover letters dated December 2023)",
            "source_last_modified": modified,
            "extraction_granularity": "pdf_page",
            "ocr_note": "scanned image-only PDF; Tesseract (eng) page OCR",
        },
    )
    return {
        "docs": [doc],
        "index_url": GU_BES_INDEX,
        "index_document_count": len(pdfs),
        "inventory": (
            f"{len(pdfs)} PDFs on the Bureau of Economic Security page: Application for Public Benefits, SNAP change "
            "report forms and self-employment income form (application family), FY26 SNAP Employment and Training "
            "State Plan (E&T family), FY26 TANF State Plan (the FY 2024-2026 certified renewal); the 'FY26 SNAP State "
            "Plan' entry has no link; taken 1"
        ),
        "source_kind": "official_pdf_state_plan",
        "document_class": "policy",
        "primary_source_url": url,
        "version": TERRITORY_PLAN_VERSION,
        "proven": "2026-09-11",
    }


# --------------------------------------------------------------------------- PR (territories pass)
PR_ADSEF_REGLAMENTOS = "https://serviciosenlinea.adsef.pr.gov/sobre-adsef/reglamento"


def build_pr() -> dict[str, Any]:
    """Puerto Rico ADSEF (Administracion de Desarrollo Socioeconomico de la Familia): the Reglamentos
    page of the agency's own site lists the two adopted eligibility regulations, PAN 8684 and TANF 7653.
    TANF 7653 (Reglamento de Normas de Certificacion para la Determinacion de Elegibilidad a Solicitantes
    y Participantes del Programa de Ayuda Temporal para Familias Necesitadas) is the territory's TANF
    eligibility rule; ADSEF's 2024 transition memorandum says a revised TANF regulation is in final
    review, but 7653 is the regulation the publisher posts. The scan is image-only and stored rotated,
    so the extractor runs Tesseract with automatic orientation detection (ocr_psm 1)."""
    page = fetch(PR_ADSEF_REGLAMENTOS).text
    pdfs = list({h: (h, t) for h, t in links(page) if h.lower().endswith(".pdf")}.values())  # unique by href
    target = [h for h, t in pdfs if t.strip().upper().startswith("TANF")]
    if len(target) != 1:
        raise RuntimeError(f"expected one TANF reglamento link on the ADSEF Reglamentos page, found {target}")
    url = urljoin(PR_ADSEF_REGLAMENTOS, target[0])
    head = fetch(url, head=True)
    modified = http_date(head.headers.get("last-modified"))
    doc = base_doc(
        source_id="us-pr-adsef-reglamento-7653-tanf",
        jurisdiction="us-pr",
        document_class="regulation",
        title=(
            "Reglamento Num. 7653: Normas de Certificacion para la Determinacion de Elegibilidad a Solicitantes y "
            "Participantes del Programa de Ayuda Temporal para Familias Necesitadas (TANF)"
        ),
        source_url=url,
        source_format="pdf",
        citation_path="us-pr/regulation/adsef/reglamento-7653",
        expression_date=SOURCE_AS_OF,
        authority="Puerto Rico Department of the Family, Administracion de Desarrollo Socioeconomico de la Familia (ADSEF)",
        subtype="adopted_regulation_pdf",
        state_program="Puerto Rico TANF (Programa de Ayuda Temporal para Familias Necesitadas)",
        index_url=PR_ADSEF_REGLAMENTOS,
        extraction={"ocr": True, "ocr_psm": 1},
        extra={
            "regulation_number": "7653",
            "source_last_modified": modified,
            "extraction_granularity": "pdf_page",
            "expression_date_note": (
                "current regulation as posted on the fetch date; the promulgation date is on a scanned cover the "
                "OCR did not read reliably (PDF creation date 2010-04-07)"
            ),
            "ocr_note": (
                "scanned image-only PDF stored rotated (/Rotate 270); Tesseract automatic page segmentation with "
                "orientation detection (ocr_psm 1); only the eng traineddata is installed, so Spanish diacritics are "
                "approximate"
            ),
        },
    )
    families = {
        "adsef_reglamento_pdf": len([1 for _h, t in pdfs if t.strip().upper().startswith(("PAN", "TANF"))]),
        "program_state_plan_pdf": len([1 for _h, t in pdfs if "State Plan" in t or "STATE PLAN" in t]),
        "form_pdf": len([1 for h, _t in pdfs if "/documents/" in h and ".sl-" in h]),
    }
    return {
        "docs": [doc],
        "index_url": PR_ADSEF_REGLAMENTOS,
        "index_document_count": len(pdfs),
        "inventory": (
            f"{len(pdfs)} PDFs on the ADSEF Reglamentos page: {families['adsef_reglamento_pdf']} adopted regulations "
            "(PAN 8684, taken by the SNAP/NAP territories row; TANF 7653, taken here), "
            f"{families['program_state_plan_pdf']} program state plans (TEFAP 2025, CSFP 2025, NAP 2023), "
            f"{families['form_pdf']} application and certification forms, and public notices (LIHEAP benefits, TANF "
            "services convocatoria, NAP-to-SNAP transition RFP); taken 1"
        ),
        "source_kind": "official_pdf_regulation",
        "document_class": "regulation",
        "primary_source_url": url,
        "version": TERRITORY_REGULATION_VERSION,
        "proven": "2026-09-11",
    }



BUILDERS = {
    "us-gu": build_gu,
    "us-pr": build_pr,
    "us-ca": build_ca,
    "us-co": build_co,
    "us-dc": build_dc,
    "us-mo": build_mo,
    "us-ms": build_ms,
    "us-mt": build_mt,
    "us-nd": build_nd,
    "us-ok": build_ok,
    "us-pa": build_pa,
    "us-va": build_va,
    "us-sd": build_sd,
    "us-nh": build_nh,
    "us-la": build_la,
    "us-id": build_id,
    "us-ri": build_ri,
    "us-wi": build_wi,
    "us-sc": build_sc,
    "us-ky": build_ky,
    "us-tn": build_tn,
    "us-vt": build_vt,
    "us-nm": build_nm,
    "us-ne": build_ne,
    "us-or": build_or,
    "us-oh": build_oh,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mo-title-cache", type=Path)
    parser.add_argument("--only", action="append", help="jurisdiction(s) to rebuild; default all")
    args = parser.parse_args()

    queue = yaml.safe_load(QUEUE_PATH.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}
    for jur, name in NEW_ROWS.items():
        rows.setdefault(
            jur,
            {
                "jurisdiction": jur,
                "name": name,
                "queue_status": "needs_review",
                "source_kind": None,
                "primary_source_url": None,
                "target_manifest": None,
                "target_scope": {"jurisdiction": jur, "document_class": None, "version": None},
                "lead_counts": None,
                "candidate_sources": [],
                "notes": f"Row added by {BATCH_LABEL.get(jur, 'batch 2').lower()} (not on the policyengine-us lead list).",
            },
        )
    selected = args.only or list(BUILDERS)
    for jur in selected:
        if jur not in BUILDERS:
            continue  # static-row jurisdictions (territories pass) are applied below
        builder = BUILDERS[jur]
        result = builder(args.mo_title_cache) if jur == "us-mo" else builder()
        stem = f"{jur}-tanf-state-policy-manual"
        manifest = {"version": SOURCE_AS_OF, "documents": result["docs"]}
        (ROOT / "manifests" / f"{stem}.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120)
        )
        row = rows[jur]
        row.update(
            {
                "queue_status": "agent_ready",
                "source_kind": result["source_kind"],
                "primary_source_url": result["primary_source_url"],
                "target_manifest": f"manifests/{stem}.yaml",
                "target_scope": {
                    "jurisdiction": jur,
                    "document_class": result["document_class"],
                    # adapter-driven scopes (OR, OH) carry the adapter's scoped run id
                    "version": result.get("version", VERSION),
                },
                "index_url": result["index_url"],
                "index_document_count": result["index_document_count"],
                "taken_count": len(result["docs"]),
                "notes": f"{BATCH_LABEL[jur]}. Primary source confirmed from the publisher's own index. Inventory: {result['inventory']}. Extraction proven {result.get('proven', '2026-09-10')} (coverage complete, 0 missing/extra/duplicate).",
            }
        )
        print(f"{jur}: {len(result['docs'])} documents -> manifests/{stem}.yaml", file=sys.stderr)

    for jur, info in DONE.items():
        row = rows[jur]
        document_class, version = info["scope"]
        row.update(
            {
                "queue_status": "done",
                "source_kind": "already_ingested",
                "target_manifest": info["target_manifest"],
                "target_scope": {
                    "jurisdiction": jur,
                    "document_class": document_class,
                    "version": version,
                },
                "notes": info["notes"],
            }
        )
    for jur, info in BLOCKED.items():
        row = rows[jur]
        row.update(
            {
                "queue_status": "blocked_primary_source",
                "source_kind": info["source_kind"],
                "primary_source_url": info["primary_source_url"],
                "target_manifest": f"manifests/{jur}-tanf-state-policy-manual.yaml",
                "target_scope": {
                    "jurisdiction": jur,
                    "document_class": info["document_class"],
                    "version": VERSION,
                },
                "index_url": info["index_url"],
                "index_document_count": info["index_document_count"],
                "taken_count": 0,
                "notes": info["notes"],
            }
        )
    for jur, info in NOT_PUBLISHED.items():
        if args.only and jur not in args.only:
            continue
        row = rows[jur]
        row.update(
            {
                "queue_status": "blocked_primary_source",
                "source_kind": info["source_kind"],
                "primary_source_url": info["primary_source_url"],
                "target_manifest": f"manifests/{jur}-tanf-state-policy-manual.yaml",
                "target_scope": {"jurisdiction": jur, "document_class": info["document_class"], "version": None},
                "index_url": info["index_url"],
                "index_document_count": info["index_document_count"],
                "taken_count": 0,
                "notes": info["notes"],
            }
        )
    for jur, info in NOT_APPLICABLE.items():
        if args.only and jur not in args.only:
            continue
        row = rows[jur]
        row.update(
            {
                "queue_status": "blocked_primary_source",
                "program_applicability": "not_applicable",
                "source_kind": info["source_kind"],
                "primary_source_url": info["primary_source_url"],
                "target_manifest": None,
                "target_scope": {"jurisdiction": jur, "document_class": None, "version": None},
                "index_url": info["index_url"],
                "index_document_count": info["index_document_count"],
                "taken_count": 0,
                "notes": info["notes"],
            }
        )
    for jur, info in NEEDS_REVIEW.items():
        row = rows[jur]
        row.update(
            {
                "queue_status": "needs_review",
                "source_kind": info["source_kind"],
                "primary_source_url": info["primary_source_url"],
                "target_manifest": f"manifests/{jur}-tanf-state-policy-manual.yaml",
                "target_scope": {
                    "jurisdiction": jur,
                    "document_class": info["document_class"],
                    "version": VERSION,
                },
                "index_url": info["index_url"],
                "index_document_count": info["index_document_count"],
                "taken_count": 0,
                "notes": info["notes"],
            }
        )
    fed = rows["us"]
    fed.update(
        {
            "queue_status": "needs_review",
            "source_kind": "federal_regulation_and_state_plan_index",
            "primary_source_url": "https://www.ecfr.gov/current/title-45/subtitle-B/chapter-II/part-260",
            "index_url": "https://acf.gov/ofa/programs/temporary-assistance-needy-families-tanf",
            "index_document_count": None,
            "taken_count": 0,
            "notes": (
                "Checked 2026-09-10: 45 CFR parts 260-265 are NOT in the corpus (data/corpus/coverage/us/regulation has title 45 part 1302 only; "
                "no manifest or ingest-run note references parts 260-265). Not re-ingested in this run (federal eCFR adapter extract-ecfr "
                "--only-title 45 --only-part 260..265 is the path). ACF Office of Family Assistance TANF state plans are a separate later "
                "document family (state plans are published by each state; the OFA program page and the acf.gov resource library do not "
                "expose a consolidated plan index to a non-browser client on 2026-09-10 - acf.gov/ofa/programs/tanf/state-plans is 404 and "
                "the resource-library type filter returns an HTTP 202 challenge). index_document_count unknown; record once an index is located."
            ),
        }
    )
    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = (
            queue["status_counts"].get(s["queue_status"], 0) + 1
        )
    queue["queue_status"] = "in_progress"
    QUEUE_PATH.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"queue {queue['status_counts']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
