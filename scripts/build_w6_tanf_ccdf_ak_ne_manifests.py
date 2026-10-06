#!/usr/bin/env python3
"""Wave 6, group tanf-ccdf-ak-ne: manifests for the TANF and CCDF bundle documents (AK to NE).

Work order: docs/coverage/program-bundle-gaps-2026-10-06/wave6/tanf-ccdf-ak-ne.csv (372 rows).
Run note: docs/ingest-runs/2026-10-06-w6-tanf-ccdf-ak-ne.md.

Two steps:

    # 1. one plain GET per address with the corpus user agent, one request at a time per host
    uv run python scripts/build_w6_tanf_ccdf_ak_ne_manifests.py probe \\
        --work-order <tanf-ccdf-ak-ne.csv> --out /tmp/w6-probe.json [--ca-bundle <pem>]
    # 2. manifests (titles and dates read from the probe) and the decisions file
    uv run python scripts/build_w6_tanf_ccdf_ak_ne_manifests.py manifests \\
        --work-order <tanf-ccdf-ak-ne.csv> --probe /tmp/w6-probe.json

Every document taken is the official publisher's own file; `source_url` is the bundle's address
whenever that is the address fetched (the bundle generator joins by URL). Rows that a scope already
holds, that are no source of rules, or that the publisher blocks are recorded in `DECISIONS` and
written to the decisions CSV, one row per work-order row.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "manifests"
DECISIONS_CSV = REPO_ROOT / "docs/ingest-runs/2026-10-06-w6-tanf-ccdf-ak-ne-decisions.csv"
SOURCE_AS_OF = "2026-10-06"
GROUP = "tanf-ccdf-ak-ne"
DISCOVERED_VIA = "program-bundle-gaps-2026-10-06 wave6 tanf-ccdf-ak-ne work order"
USER_AGENT = (
    "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) "
    "https://github.com/TheAxiomFoundation/axiom-corpus"
)

# Version per (jurisdiction, document_class): family + state, never shared with another agent.
FAMILY_BY_CLASS = {
    "policy": "tanf-ccdf-docs",
    "manual": "tanf-ccdf-manual",
    "regulation": "tanf-ccdf-rules",
    "statute": "tanf-ccdf-statutes",
}

STATE_NAMES = {
    "us-ak": "Alaska", "us-al": "Alabama", "us-ar": "Arkansas", "us-az": "Arizona",
    "us-ca": "California", "us-co": "Colorado", "us-ct": "Connecticut", "us-dc": "District of Columbia",
    "us-de": "Delaware", "us-fl": "Florida", "us-ga": "Georgia", "us-hi": "Hawaii", "us-ia": "Iowa",
    "us-id": "Idaho", "us-il": "Illinois", "us-in": "Indiana", "us-ks": "Kansas", "us-ky": "Kentucky",
    "us-la": "Louisiana", "us-ma": "Massachusetts", "us-md": "Maryland", "us-me": "Maine",
    "us-mi": "Michigan", "us-mn": "Minnesota", "us-mo": "Missouri", "us-ms": "Mississippi",
    "us-mt": "Montana", "us-nc": "North Carolina", "us-nd": "North Dakota", "us-ne": "Nebraska",
}

# host -> (agency path segment, publisher name)
HOSTS: dict[str, tuple[str, str]] = {
    "health.alaska.gov": ("doh", "Alaska Department of Health"),
    "dhr.alabama.gov": ("dhr", "Alabama Department of Human Resources"),
    "humanservices.arkansas.gov": ("dhs", "Arkansas Department of Human Services"),
    "www.azleg.gov": ("ars", "Arizona State Legislature"),
    "cdss.ca.gov": ("cdss", "California Department of Social Services"),
    "www.cdss.ca.gov": ("cdss", "California Department of Social Services"),
    "dpss.lacounty.gov": ("la-county-dpss", "Los Angeles County Department of Public Social Services"),
    "my.dpss.lacounty.gov": ("la-county-dpss", "Los Angeles County Department of Public Social Services"),
    "rcscc.adm.dss.ca.gov": ("cdss", "California Department of Social Services"),
    "stgenssa.sccgov.org": ("santa-clara-county-ssa", "County of Santa Clara Social Services Agency"),
    "portal.ct.gov": ("dss", "Connecticut Department of Social Services"),
    "www.ctcare4kids.com": ("oec", "Connecticut Office of Early Childhood, Care 4 Kids program"),
    "www.ctoec.org": ("oec", "Connecticut Office of Early Childhood"),
    "cga.ct.gov": ("cga", "Connecticut General Assembly"),
    "www.cga.ct.gov": ("cga", "Connecticut General Assembly, Office of Legislative Research"),
    "dhs.dc.gov": ("dhs", "District of Columbia Department of Human Services"),
    "osse.dc.gov": ("osse", "District of Columbia Office of the State Superintendent of Education"),
    "dhss.delaware.gov": ("dss", "Delaware Department of Health and Social Services, Division of Social Services"),
    "www.myflfamilies.com": ("dcf", "Florida Department of Children and Families"),
    "pamms.dhs.ga.gov": ("dfcs", "Georgia Division of Family and Children Services (PAMMS)"),
    "rules.sos.ga.gov": ("gac", "Georgia Secretary of State, Rules and Regulations of the State of Georgia"),
    "childcaresubsidyapplication.dhs.hawaii.gov": ("dhs", "Hawaii Department of Human Services"),
    "humanservices.hawaii.gov": ("dhs", "Hawaii Department of Human Services"),
    "hhs.iowa.gov": ("hhs", "Iowa Department of Health and Human Services"),
    "www.legis.iowa.gov": ("iac", "Iowa Legislature, Legislative Services Agency"),
    "healthandwelfare.idaho.gov": ("dhw", "Idaho Department of Health and Welfare"),
    "idec.illinois.gov": ("idec", "Illinois Department of Early Childhood"),
    "www.dhs.state.il.us": ("dhs", "Illinois Department of Human Services"),
    "www.in.gov": ("fssa", "Indiana Family and Social Services Administration"),
    "content.dcf.ks.gov": ("dcf", "Kansas Department for Children and Families"),
    "ksrevisor.gov": ("ksa", "Kansas Office of Revisor of Statutes"),
    "apps.legislature.ky.gov": ("kar", "Kentucky Legislative Research Commission"),
    "prd.webapps.chfs.ky.gov": ("chfs", "Kentucky Cabinet for Health and Family Services"),
    "www.chfs.ky.gov": ("chfs", "Kentucky Cabinet for Health and Family Services"),
    "doe.louisiana.gov": ("ldoe", "Louisiana Department of Education"),
    "www.louisianabelieves.com": ("ldoe", "Louisiana Department of Education"),
    "louisianabelieves.com": ("ldoe", "Louisiana Department of Education"),
    "www.dcfs.louisiana.gov": ("dcfs", "Louisiana Department of Children and Family Services"),
    "www.doa.la.gov": ("osr", "Louisiana Division of Administration, Office of the State Register"),
    "archives.lib.state.ma.us": ("eec", "Massachusetts Department of Early Education and Care (State Library of Massachusetts repository)"),
    "www.mass.gov": ("eec", "Massachusetts Department of Early Education and Care"),
    "dhs.maryland.gov": ("dhs", "Maryland Department of Human Services, Family Investment Administration"),
    "mgaleg.maryland.gov": ("mga", "Maryland General Assembly"),
    "regs.maryland.gov": ("comar", "Maryland Division of State Documents (COMAR)"),
    "content.govdelivery.com": ("msde", "Maryland State Department of Education, Division of Early Childhood"),
    "legislature.maine.gov": ("legislature", "Maine Legislature"),
    "www.maine.gov": ("dhhs", "Maine Department of Health and Human Services"),
    "mdhhs-pres-prod.michigan.gov": ("mdhhs", "Michigan Department of Health and Human Services"),
    "www.michigan.gov": ("mdhhs", "Michigan Department of Health and Human Services"),
    "edocs.dhs.state.mn.us": ("dhs", "Minnesota Department of Human Services"),
    "www.dhs.state.mn.us": ("dhs", "Minnesota Department of Human Services"),
    "www.house.mn.gov": ("house-research", "Minnesota House Research Department"),
    "www.revisor.mn.gov": ("revisor", "Minnesota Office of the Revisor of Statutes"),
    "dese.mo.gov": ("dese", "Missouri Department of Elementary and Secondary Education, Office of Childhood"),
    "dssmanuals.mo.gov": ("dss", "Missouri Department of Social Services"),
    "revisor.mo.gov": ("rsmo", "Missouri Revisor of Statutes"),
    "www.sos.mo.gov": ("csr", "Missouri Secretary of State, Administrative Rules Division"),
    "www.mdhs.ms.gov": ("mdhs", "Mississippi Department of Human Services"),
    "archive.legmt.gov": ("legislature", "Montana Legislative Fiscal Division"),
    "dphhs.mt.gov": ("dphhs", "Montana Department of Public Health and Human Services"),
    "www.ncleg.gov": ("ncgs", "North Carolina General Assembly"),
    "ncchildcare.ncdhhs.gov": ("dcdee", "North Carolina DHHS, Division of Child Development and Early Education"),
    "policies.ncdhhs.gov": ("dcdee", "North Carolina DHHS, Division of Child Development and Early Education"),
    "www.ncdhhs.gov": ("dss", "North Carolina Department of Health and Human Services, Division of Social Services"),
    "ndlegis.gov": ("legislature", "North Dakota Legislative Branch"),
    "www.hhs.nd.gov": ("hhs", "North Dakota Health and Human Services"),
    "www.nd.gov": ("hhs", "North Dakota Health and Human Services"),
    "dhhs.ne.gov": ("dhhs", "Nebraska Department of Health and Human Services"),
    "leg.ne.gov": ("legislature", "Nebraska Legislature, Revisor of Statutes"),
    "nebraskalegislature.gov": ("legislature", "Nebraska Legislature"),
    "rules.nebraska.gov": ("sos", "Nebraska Secretary of State"),
}

# --------------------------------------------------------------------------------------
# Probe
# --------------------------------------------------------------------------------------


def read_work_order(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def probe(rows: list[dict[str, str]], out: Path, ca_bundle: str | None, extra: dict[str, str]) -> None:
    import fitz  # noqa: PLC0415
    import requests  # noqa: PLC0415
    from bs4 import BeautifulSoup  # noqa: PLC0415

    targets: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for i, row in enumerate(rows):
        if row["bundle_url"] and row["action"] in {"FETCH", "CHECK-PUBLISHER", "EXTRACT-MANIFEST", "DEAD-LINK"}:
            targets[urllib.parse.urlsplit(row["bundle_url"]).netloc.lower()].append((str(i), row["bundle_url"]))
    for key, url in extra.items():
        targets[urllib.parse.urlsplit(url).netloc.lower()].append((key, url))
    results: dict[str, Any] = json.loads(out.read_text()) if out.exists() else {}
    lock = threading.Lock()

    def summarize(content: bytes) -> dict[str, Any]:
        info: dict[str, Any] = {}
        if content[:5] == b"%PDF-":
            with fitz.open(stream=content, filetype="pdf") as doc:
                info["pages"] = doc.page_count
                text = ""
                for page in doc:
                    text += page.get_text()
                    if len(text) > 1500:
                        break
                info["text"] = " ".join(text.split())[:900]
                info["meta"] = {k: v for k, v in (doc.metadata or {}).items() if v}
        elif b"<html" in content[:3000].lower() or b"<!doctype" in content[:300].lower():
            page = BeautifulSoup(content, "lxml")
            info["title"] = (page.title.get_text(strip=True) if page.title else "")[:200]
            h1 = page.find("h1")
            info["h1"] = h1.get_text(" ", strip=True)[:200] if h1 else ""
            main = page.find("main") or page.body or page
            info["text"] = " ".join(main.get_text(" ").split())[:900]
        return info

    def work(items: list[tuple[str, str]]) -> None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        for key, url in items:  # one request at a time per host
            started = time.time()
            record: dict[str, Any] = {"url": url}
            try:
                response = session.get(url, timeout=40, verify=ca_bundle or True)
                record.update(
                    status=response.status_code,
                    ctype=response.headers.get("content-type"),
                    final_url=response.url,
                    size=len(response.content),
                    lm=response.headers.get("last-modified"),
                    sha=hashlib.sha256(response.content).hexdigest()[:16],
                    secs=round(time.time() - started, 1),
                )
                record.update(summarize(response.content))
            except Exception as exc:  # noqa: BLE001 - record and move on
                record.update(error=f"{type(exc).__name__}: {str(exc)[:200]}")
            with lock:
                results[key] = record
            time.sleep(0.5)

    threads = [threading.Thread(target=work, args=(items,)) for items in targets.values()]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    out.write_text(json.dumps(results, indent=1))
    print(f"probed {sum(len(v) for v in targets.values())} addresses on {len(targets)} hosts", file=sys.stderr)


# --------------------------------------------------------------------------------------
# Titles, dates, slugs
# --------------------------------------------------------------------------------------

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTHS.split("|"))}


def _iso(month: str, day: str, year: str) -> str | None:
    m = MONTH_NUM.get(month.rstrip(".").capitalize())
    if not m or not (1990 <= int(year) <= 2027):
        return None
    return f"{int(year):04d}-{m:02d}-{int(day):02d}"


def date_from_text(text: str) -> tuple[str | None, str | None]:
    for pattern, basis in (
        (rf"[Ee]ffective(?: [Dd]ate)?:?\s*(?:on |as of )?({MONTHS})\.? (\d{{1,2}}),? (\d{{4}})", "printed effective date"),
        (r"[Ee]ffective(?: [Dd]ate)?:?\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", "printed effective date"),
        (rf"\b({MONTHS}) (\d{{1,2}}),? (\d{{4}})", "first printed date"),
    ):
        match = re.search(pattern, text[:600])
        if not match:
            continue
        a, b, c = match.groups()
        if a.isdigit():
            year = int(c) + (2000 if len(c) == 2 else 0)
            if 1990 <= year <= 2027 and 1 <= int(a) <= 12 and 1 <= int(b) <= 31:
                return f"{year:04d}-{int(a):02d}-{int(b):02d}", basis
            continue
        iso = _iso(a, b, c)
        if iso:
            return iso, basis
    return None, None


def http_date(value: str | None) -> str | None:
    if not value:
        return None
    from email.utils import parsedate_to_datetime  # noqa: PLC0415

    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def slug(value: str, limit: int = 80) -> str:
    text = urllib.parse.unquote(value).lower()
    text = re.sub(r"\.(pdf|html?|aspx|docx?|xlsx?|php)$", "", text)
    text = re.sub(r"[^a-z0-9.]+", "-", text).strip("-.")
    text = re.sub(r"-{2,}", "-", text)
    return text[:limit].strip("-.")


def url_slug(url: str) -> str:
    parts = [p for p in urllib.parse.urlsplit(url).path.split("/") if p]
    for part in reversed(parts):
        if part.lower() not in {"download", "content", "open", "index.aspx", "index.html"}:
            return slug(part)
    return "index"


def clean_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    for sep in (" | ", " :: ", " - Mississippi", " – DHSS", " | Department"):
        if sep in text:
            text = text.split(sep)[0].strip()
    return text[:160]


def auto_title(row: dict[str, str], probe_rec: dict[str, Any]) -> str:
    host = urllib.parse.urlsplit(row["bundle_url"]).netloc.lower()
    publisher = HOSTS.get(host, ("", STATE_NAMES[row["jurisdiction"]]))[1]
    if probe_rec.get("title") or probe_rec.get("h1"):
        base = clean_title(probe_rec.get("title") or probe_rec.get("h1") or "")
    else:
        meta_title = clean_title((probe_rec.get("meta") or {}).get("title", ""))
        if meta_title and not re.match(r"(?i)^(microsoft word|untitled|document\d*|pdf)", meta_title) and len(meta_title) > 8:
            base = meta_title
        else:
            words = (probe_rec.get("text") or "").split()
            base = " ".join(words[:16]) or url_slug(row["bundle_url"])
    return f"{publisher}: {base}"[:220]


def auto_date(probe_rec: dict[str, Any]) -> tuple[str, str]:
    iso, basis = date_from_text(probe_rec.get("text") or "")
    if iso:
        return iso, basis or "printed date"
    lm = http_date(probe_rec.get("lm"))
    if lm:
        return lm, "HTTP Last-Modified"
    return SOURCE_AS_OF, "source date (no printed or HTTP date)"


def source_format(probe_rec: dict[str, Any], url: str) -> str:
    ctype = (probe_rec.get("ctype") or "").lower()
    if "pages" in probe_rec or "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
        return "pdf"
    if "wordprocessingml" in ctype or url.lower().endswith(".docx"):
        return "docx"
    if "spreadsheetml" in ctype or url.lower().endswith(".xlsx"):
        return "xlsx"
    return "html"


# --------------------------------------------------------------------------------------
# What is taken (row -> manifest entry) and what is decided without extraction
# --------------------------------------------------------------------------------------

IMPERSONATE = {"browser_impersonation": True}  # documented for mass.gov, michigan.gov (CCDF/TANF plan runs)

# row -> (document_class, citation_path, overrides)
# overrides: title, url (source_url when it differs from bundle_url), download_url, format, extraction,
# request, expression_date, subtype, note
TAKE: dict[int, tuple[str, str, dict[str, Any]]] = {}


def take(row: int, cls: str, path: str, **overrides: Any) -> None:
    TAKE[row] = (cls, path, overrides)


# us-ak
take(0, "policy", "us-ak/policy/doh/ccdf/alaska-inclusive-child-care-program")
take(1, "policy", "us-ak/policy/doh/tanf/alaska-temporary-assistance-program")
take(2, "manual", "us-ak/manual/doh/ccdf/child-care-assistance-program-policies-and-procedures", subtype="agency_policy_manual")
take(3, "policy", "us-ak/policy/doh/ccdf/family-income-and-contribution-schedule-2022-02-21")
take(4, "policy", "us-ak/policy/doh/ccdf/ccap-rate-schedule")
# us-al
take(5, "policy", "us-al/policy/dhr/tanf/state-plan-2021")
take(6, "policy", "us-al/policy/dhr/ccdf/provider-rates-with-qris-tiers-2022-04-01")
take(7, "policy", "us-al/policy/dhr/tanf/dhr-fad-595-2023-10")
take(8, "policy", "us-al/policy/dhr/ccdf/child-care-fact-sheet-2024")
# us-ar
take(9, "policy", "us-ar/policy/dhs/tanf/transitional-employment-assistance")
# us-az statutes (azleg.gov answers; the adapter's section paths)
take(12, "statute", "us-az/statute/46-207.01")
take(13, "statute", "us-az/statute/46-207")
take(14, "statute", "us-az/statute/46-292")
# us-ca
for i, n in ((20, "ccb-25-15"),):
    take(i, "policy", f"us-ca/policy/cdss/ccdf/{n}")
for i, n in ((21, "acl-18-124"), (22, "acl-18-66"), (23, "acl-19-47"), (24, "acl-19-73"), (34, "acl-17-44"),
             (35, "acl-20-60"), (36, "acl-21-87"), (37, "acl-22-60"), (38, "acl-23-47"), (39, "acl-23-71"),
             (40, "acl-23-74"), (41, "acl-24-37"), (42, "acl-25-37"), (43, "acl-25-65"), (44, "acl-26-38"),
             (45, "acl-26-39"), (46, "acl-15-52"), (47, "acl-16-47")):
    take(i, "policy", f"us-ca/policy/cdss/tanf/{n}", subtype="all_county_letter")
take(25, "policy", "us-ca/policy/la-county-dpss/tanf/calworks")
for i, n in ((26, "44-212-minimum-basic-standard-of-adequate-care"), (27, "44-111.23-earned-income-disregards"),
             (28, "44-315-calworks-maximum-aid-payment-levels"), (29, "42-215-determining-value-of-property-vehicles"),
             (30, "42-200-property"), (31, "1210-child-care-overview"), (32, "1210.8-regional-market-rate-ceilings")):
    take(i, "manual", f"us-ca/manual/la-county-dpss/epolicy/{n}", subtype="county_policy_manual_page")
take(33, "policy", "us-ca/policy/cdss/ccdf/reimbursement-ceilings-for-subsidized-child-care")
for i, n in ((48, "10eas"), (49, "12eas"), (50, "14eas"), (51, "4eas")):
    take(i, "regulation", f"us-ca/regulation/cdss/mpp-eas-pdf/{n}", subtype="agency_regulation_manual_legacy_pdf",
         note="legacy PDF print of the CDSS MPP Eligibility and Assistance Standards at the old /ord/entres address; "
         "an older edition than the DOCX files of us-ca/regulation/2026-09-10-tanf-state-policy-manual")
take(52, "policy", "us-ca/policy/santa-clara-county-ssa/tanf/non-exempt-au-standards-chart-region-1")
take(53, "policy", "us-ca/policy/santa-clara-county-ssa/tanf/standards-chart-region-2")
# us-ct
take(75, "policy", "us-ct/policy/dss/tanf/ct-tanf-plan-2021-2023-draft")
for i, n in ((76, "care-4-kids-weekly-payment-rates-2024-07-01"), (77, "care-4-kids-weekly-payment-rates-2024-01-01"),
             (78, "care-4-kids-weekly-payment-rates-2025-01-01"), (79, "care-4-kids-weekly-payment-rates-2025-07-01"),
             (80, "care-4-kids-weekly-payment-rates-2026-01-01")):
    take(i, "policy", f"us-ct/policy/oec/ccdf/{n}", subtype="rate_or_copay_schedule")
take(81, "policy", "us-ct/policy/oec/ccdf/care-4-kids-policies-and-procedures")
take(82, "policy", "us-ct/policy/oec/ccdf/c4k-pol-24-02-family-fee-transmittal-update")
take(84, "policy", "us-ct/policy/cga/ccdf/olr-2020-r-0274")
take(85, "policy", "us-ct/policy/cga/tanf/olr-2023-r-0100")
take(86, "policy", "us-ct/policy/cga/ccdf/olr-2023-r-0249")
# us-dc
take(91, "policy", "us-dc/policy/dhs/tanf/temporary-cash-assistance-for-needy-families")
take(92, "policy", "us-dc/policy/dhs/tanf/tanf-state-plan-for-comment-2020-01-07")
take(93, "policy", "us-dc/policy/osse/ccdf/final-rulemaking-licensing-of-child-development-facilities")
take(94, "policy", "us-dc/policy/osse/ccdf/sliding-fee-scale-2024-10-25", subtype="rate_or_copay_schedule")
take(95, "policy", "us-dc/policy/osse/ccdf/dc-child-care-subsidy-program")
# us-de
take(97, "policy", "us-de/policy/dss/tanf/temporary-assistance-for-needy-families")
take(98, "policy", "us-de/policy/dss/tanf/oct-2022-cola")
take(99, "policy", "us-de/policy/dss/tanf/de-tanf-state-plan-2017")
# us-fl
take(104, "policy", "us-fl/policy/dcf/tanf/temporary-cash-assistance")
# us-ga
take(107, "manual", "us-ga/manual/dfcs/tanf-policy-manual-pdf-export", subtype="agency_policy_manual_pdf_export",
     note="PAMMS PDF export of the whole TANF manual, dated 2026-10-05 on its cover; the HTML pages are also held "
     "as us-ga/manual/2026-09-14-tanf-manual-whole")
take(108, "manual", "us-ga/manual/dfcs/tanf-policy-manual-index", subtype="agency_policy_manual_index")
take(109, "regulation", "us-ga/regulation/290-2-28")
take(110, "regulation", "us-ga/regulation/290-2-28/290-2-28-.02")
take(111, "regulation", "us-ga/regulation/290-2-28/290-2-28-.13")
# us-hi
take(113, "policy", "us-hi/policy/dhs/ccdf/gross-income-eligibility-limits-and-sliding-fee-scale")
take(114, "regulation", "us-hi/regulation/har/17/798-2")
take(115, "regulation", "us-hi/regulation/har/17/798-3")
take(116, "policy", "us-hi/policy/dhs/tanf/hrs-346-54-public-assistance-expenditures-report-2016")
take(117, "policy", "us-hi/policy/dhs/tanf/hrs-346-51.5-tanf-legislative-report-2025")
# us-ia
for i, n in ((120, "cca-family-fee-chart-2024-07-01"), (121, "general-letter-13-g-56-2024-06-14"),
             (122, "cca-family-fee-chart-2025-07-01"), (123, "cca-family-fee-chart-2026-07-01")):
    take(i, "policy", f"us-ia/policy/hhs/ccdf/{n}")
take(124, "regulation", "us-ia/regulation/iac/441/41/edition-2026-01-07",
     note="the 01-07-2026 print of 441 IAC chapter 41; the current print is held in us-ia/regulation/2026-07-03-ia-fip-admin-rules")
take(125, "regulation", "us-ia/regulation/iac/441/170")
# us-id
take(129, "policy", "us-id/policy/dhw/ccdf/idaho-child-care-program")
# us-il
take(132, "policy", "us-il/policy/idec/ccdf/il444-3455b-important-parent-copayment-information")
take(133, "policy", "us-il/policy/idec/ccdf/il444-4343-child-care-payment-rates")
take(134, "policy", "us-il/policy/dhs/ccdf/july-1-2025-changes-to-ccap-memo")
take(135, "policy", "us-il/policy/dhs/ccdf/443455b-ccap-income-and-copay-chart-2025-07-01")
# us-in
take(154, "policy", "us-in/policy/dcs/tanf/16.02-assistance-for-unlicensed-relative-placements-archived")
take(155, "manual", "us-in/manual/fssa/oecosl/ccdf-provider-manual", subtype="agency_policy_manual")
for i, n in ((156, "ccdf-sliding-fee-schedule-with-copays-2026"), (157, "income-get-on-ccdf"), (158, "income-stay-on-ccdf"),
             (159, "marion-reimbursement-rate-ccdf"), (160, "reimbursement-rate-faqs"), (161, "updated-child-care-voucher-rates"),
             (162, "system-updates-2023")):
    take(i, "policy", f"us-in/policy/fssa/oecosl/{n}")
for i, n in ((163, "2600"), (164, "3000"), (165, "3400")):
    take(i, "manual", f"us-in/manual/dfr/snap-tanf-program-policy-manual-chapters/{n}", subtype="agency_policy_manual_chapter",
         note="chapter file the DFR posts separately; the whole ICES Program Policy Manual PDF is held in "
         "us-in/manual/2026-05-27-in-snap-manual-r2026-07-15-self-contained")
take(166, "policy", "us-in/policy/fssa/dfr/about-tanf")
# us-ks
take(168, "manual", "us-ks/manual/dcf/keesm/appendix/f-1-monthly-family-income-and-family-share-deduction-schedule")
take(169, "manual", "us-ks/manual/dcf/keesm/implementation-memo/2026-05-01-ccfpl-increase")
take(170, "manual", "us-ks/manual/dcf/keesm/appendix/f-4-taf-table-07-11")
take(171, "manual", "us-ks/manual/dcf/keesm/appendix/c-18-provider-rate-chart")
take(172, "manual", "us-ks/manual/dcf/keesm/implementation-memo/2008-03-26-taf-earned-income-disregard")
take(173, "manual", "us-ks/manual/dcf/keesm/implementation-memo/2021-07-01-increase-to-250-percent")
take(174, "statute", "us-ks/statute/39-709")
# us-ky
take(181, "regulation", "us-ky/regulation/kar/922/002/160/document-10239")
take(182, "regulation", "us-ky/regulation/kar/922/002/160/document-13685")
take(183, "regulation", "us-ky/regulation/kar/922/002/160/document-15544")
take(184, "regulation", "us-ky/regulation/register/49/02-august-2022", subtype="administrative_register_issue")
take(185, "regulation", "us-ky/regulation/kar/921/002/016")
take(186, "regulation", "us-ky/regulation/kar/921/002/016/version-10142")
take(187, "policy", "us-ky/policy/chfs/tanf/kentucky-transitional-assistance-program")
take(188, "policy", "us-ky/policy/chfs/ccdf/dcc-113")
take(189, "policy", "us-ky/policy/chfs/ccdf/dcc-300-ky-max-payment-chart")
# us-la
take(191, "policy", "us-la/policy/ldoe/ccdf/bulletin-139")
take(192, "policy", "us-la/policy/ldoe/ccdf/ccap-sliding-fee-scale")
take(193, "policy", "us-la/policy/ldoe/ccdf/early-childhood-provider-updates-2025-02")
take(194, "policy", "us-la/policy/dcfs/tanf/louisiana-to-increase-tanf-cash-assistance-benefits-2022")
take(195, "regulation", "us-la/regulation/lac/28/clxv", format="docx", subtype="administrative_code_part")
take(196, "regulation", "us-la/regulation/register/2025-04", subtype="administrative_register_issue")
take(197, "regulation", "us-la/regulation/register/2022-05", subtype="administrative_register_issue")
take(198, "regulation", "us-la/regulation/register/2021-05", subtype="administrative_register_issue")
take(200, "policy", "us-la/policy/ldoe/ccdf/ccap-rate-changes", url="https://doe.louisiana.gov/docs/default-source/child-care-providers/ccap-rate-changes.pdf?sfvrsn=2f5d8d1f_10")
# us-ma
take(208, "policy", "us-ma/policy/eec/ccdf/policy-advisory-interim-income-eligible-state-library-copy")
for i, n in ((212, "eec-ccfa-2026-04-income-eligible-consolidated-policies-2026-05-06"),
             (213, "policy-advisory-field-operations-2023-4-ccfa"),
             (214, "policy-advisory-field-operations-2024-6-ccfa-enrollment-and-attendance-codes"),
             (215, "policy-advisory-field-operations-7-ccfa-updated-policy-guidance"),
             (216, "financial-assistance-policy-guide-2022-02-01"),
             (217, "financial-assistance-procedures-manual-for-subsidy-administrators"),
             (219, "board-vote-improves-access-to-ccfa")):
    take(i, "policy", f"us-ma/policy/eec/ccdf/{n}", request=IMPERSONATE)
# 606 CMR: the agency's posted regulation files (Cornell and Justia are mirrors)
take(209, "regulation", "us-ma/regulation/eec/606-cmr/10", request=IMPERSONATE,
     url="https://www.mass.gov/doc/child-care-financial-assistance-regulations-606-cmr-1000/download",
     title="Massachusetts Department of Early Education and Care: 606 CMR 10.00, Child Care Financial Assistance",
     subtype="agency_posted_regulation", note="the EEC regulation file linked from mass.gov (effective January 1, 2026)")
take(211, "regulation", "us-ma/regulation/eec/606-cmr/7", request=IMPERSONATE,
     url="https://www.mass.gov/doc/606-cmr-700-regulations-for-family-group-school-age-child-care-programs/download",
     title="Massachusetts Department of Early Education and Care: 606 CMR 7.00, Standards for the Licensure or "
     "Approval of Family Child Care; Small Group and School Age and Large Group and School Age Child Care Programs",
     subtype="agency_posted_regulation")
# us-mo Code of State Regulations (Secretary of State; Cornell is a mirror)
MO_DROP = [r"^CODE OF STATE REGULATIONS$", r"^\d{1,3}$", r"^[A-Z][A-Za-z. ]+ \(\d+/\d+/\d+\)$", r"^Secretary of State$"]
take(283, "regulation", "us-mo/regulation/5-csr/25-200", extraction={
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^5 CSR 25-200\.(?P<num>\d{3})\s+(?P<heading>[A-Z].+)$",
    "section_label_template": "{num}", "drop_line_patterns": MO_DROP},
    title="Missouri Code of State Regulations 5 CSR 25-200: Child Care Subsidy (DESE Office of Childhood)")
take(284, "regulation", "us-mo/regulation/13-csr/40-2",
     url="https://www.sos.mo.gov/cmsimages/adrules/csr/current/13csr/13c40-2.pdf", extraction={
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^13 CSR 40-2\.(?P<num>\d{3})\s+(?P<heading>[A-Z].+)$",
    "section_label_template": "{num}", "start_page": 4, "drop_line_patterns": MO_DROP},
    title="Missouri Code of State Regulations 13 CSR 40-2: Income Maintenance (Family Support Division)")
# us-nd NDAC 75-02-01.2 (TANF), Legislative Council (Cornell is a mirror)
take(347, "regulation", "us-nd/regulation/ndac/75-02-01.2", url="https://ndlegis.gov/prod/acdata/pdf/75-02-01.2.pdf", extraction={
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>75-02-01\.2-\d{2}(?:\.\d)?)\.\s+(?P<heading>.+)$"},
    title="North Dakota Administrative Code Chapter 75-02-01.2: Temporary Assistance for Needy Families")
# us-fl F.A.C. 65A-4.220 (Department of State; Cornell is a mirror)
take(105, "regulation", "us-fl/regulation/fac/65a-4/220", url="https://www.flrules.org/gateway/RuleNo.asp?id=65A-4.220",
     download_url="https://www.flrules.org/gateway/readFile.asp?sid=0&tid=28092187&type=1&file=65A-4.220.doc", format="doc",
     title="Florida Administrative Code Rule 65A-4.220: Amount and Duration of Cash Payment",
     note="rule page links the final adopted rule file as readFile.asp ... 65A-4.220.doc (the SSI precedent's download_url pattern)")
# us-nc 10A NCAC 10 (OAH; publichealthlawcenter.org is a repost)
take(334, "regulation", "us-nc/regulation/10a-ncac/10",
     url="http://reports.oah.state.nc.us/ncac/title%2010a%20-%20health%20and%20human%20services/chapter%2010%20-%20subsidized%20child%20care/chapter%2010%20rules.pdf",
     extraction={"segmentation": "labeled_sections", "section_label_pattern": r"^10A NCAC 10 \.(?P<label>\d{4})\s*$"},
     title="North Carolina Administrative Code 10A NCAC 10: Subsidized Child Care (Office of Administrative Hearings)")
# us-la LAC Title 67 (Office of the State Register; Cornell is a mirror, the old 67.pdf address is gone)
take(204, "regulation", "us-la/regulation/lac/67", url="https://www.doa.la.gov/media/oq1j3hys/67.docx", format="docx",
     title="Louisiana Administrative Code Title 67: Social Services (Office of the State Register)",
     note="linked as 'Title 67, Social Services' from https://www.doa.la.gov/doa/osr/louisiana-administrative-code/")
# us-ms session law (billstatus host needs the GlobalSign RSA OV SSL CA 2018 intermediate, data/certs)
take(301, "statute", "us-ms/statute/session-laws/2021/sb-2759",
     title="Mississippi Legislature 2021 Regular Session: Senate Bill 2759 (As Sent to Governor)")
# us-in 470 IAC 10.3 (iar.iga.in.gov app; the General Assembly's API, documented in the tax regulation run)
take(152, "regulation", "us-in/regulation/iac/470/10.3",
     download_url="https://drxya2s1hkmtl.cloudfront.net/api/adminCodeArticle?doc_stage=public&edition_year=2026&title_num=470&article_num=10.3",
     format="json", request={"browser_impersonation": True, "browser_impersonation_direct": True},
     extraction={"json_html_field": "iar_iac_article_doc.doc_html", "html_drop_selectors": ["ol.toc"],
                 "html_text_selector": "h1, h2, h3, div.subsection, div.emphasize, p, li, table",
                 "segmentation": "labeled_sections",
                 "section_heading_pattern": r"^470 IAC 10\.3-(?P<label>\d+-\d+(?:\.\d+)?)\s+(?P<heading>.+)$"},
     title="470 IAC Article 10.3: Child Care and Development Fund (Indiana Administrative Code)",
     note="iar.iga.in.gov is a JavaScript application; the article JSON is served by the General Assembly's API "
     "distribution (drxya2s1hkmtl.cloudfront.net/api), as in docs/ingest-runs/2026-09-14-state-tax-regulations.md")
# us-md
take(221, "policy", "us-md/policy/dhs/fia/at-19-04-tca-benefit-increase")
take(222, "policy", "us-md/policy/dhs/fia/at-20-06-tca-benefit-increase")
take(227, "statute", "us-md/statute/session-laws/2022/chapter-525")
take(228, "statute", "us-md/statute/session-laws/2024/chapter-717")
take(229, "policy", "us-md/policy/mga/ccdf/ways-and-means-2026-child-care-scholarship-briefing")
for i, n in ((230, "02"), (231, "03"), (232, "11"), (233, "12")):
    take(i, "regulation", f"us-md/regulation/title-13a/subtitle-14/chapter-06/regulation-{n}")
take(234, "policy", "us-md/policy/msde/ccdf/tuesday-tidbits-changes-to-child-care-scholarship-program")
# us-me
take(239, "statute", "us-me/statute/bills/131/hp0592")
take(240, "policy", "us-me/policy/dhhs/ofi/tanf")
take(241, "policy", "us-me/policy/dhhs/ocfs/ccdf/market-rates-2021-07-03")
take(242, "policy", "us-me/policy/dhhs/ocfs/ccdf/market-rates-2024-07-06")
take(243, "policy", "us-me/policy/dhhs/ofi/tanf-rule-121a-rule-pages-2024-09")
# us-mi
take(250, "manual", "us-mi/manual/mdhhs/bridges/rft/270")
take(252, "manual", "us-mi/manual/mdhhs/bridges/rft/210")
for i, n in ((253, "tanf-state-plan-2017"), (254, "state-plans-and-federal-regulations-a"), (255, "state-plans-and-federal-regulations-b")):
    take(i, "policy", f"us-mi/policy/mdhhs/tanf/{n}", request=IMPERSONATE)
# us-mn
take(256, "policy", "us-mn/policy/dhs/ccdf/dhs-6413n")
take(257, "policy", "us-mn/policy/dhs/ccdf/dhs-6441f")
take(258, "manual", "us-mn/manual/dhs/combined-manual-2021-12", subtype="agency_policy_manual")
take(259, "manual", "us-mn/manual/dhs/ccap-policy-manual-2023-07", subtype="agency_policy_manual")
for i, n in ((260, "cash-assistance-in-minnesota-2022-12"), (261, "mfip-grant"), (262, "mfip-pap"), (263, "mfip-short-subject-2025-08")):
    take(i, "policy", f"us-mn/policy/house-research/tanf/{n}")
take(264, "statute", "us-mn/statute/session-laws/2019-1st-special-session/chapter-9")
take(265, "regulation", "us-mn/regulation/minnesota-rules/3400/3400.0040")
take(266, "regulation", "us-mn/regulation/minnesota-rules/3400/3400.0170")
take(267, "regulation", "us-mn/regulation/minnesota-rules/3400")
take(268, "regulation", "us-mn/regulation/minnesota-rules/9502/9502.0315")
take(269, "regulation", "us-mn/regulation/minnesota-rules/9503/9503.0005")
for i, n in ((270, "142B.01"), (271, "142E.01"), (272, "142E.10"), (273, "142E.12"), (274, "142E.17")):
    take(i, "statute", f"us-mn/statute/{n}")
# us-mo
take(275, "policy", "us-mo/policy/dese/ccdf/child-care-subsidy-payments")
take(276, "manual", "us-mo/manual/dese/child-care-manual/2010-045-00")
take(277, "policy", "us-mo/policy/dese/ccdf/2025-rates-held-harmless", format="xlsx")
take(278, "policy", "us-mo/policy/dese/ccdf/income-eligibility-table-2025-10")
take(279, "manual", "us-mo/manual/dss/tanf/0210-015-30-10")
take(280, "manual", "us-mo/manual/dss/tanf/memos/im-67-03")
take(281, "manual", "us-mo/manual/dss/tanf/memos/im-109-99")
take(282, "statute", "us-mo/statute/208.040")
# us-ms
for i, n in ((292, "tanf"), (293, "applying-for-tanf"), (294, "historic-tanf-increase"), (295, "tanf-eligibility-flyer")):
    take(i, "policy", f"us-ms/policy/mdhs/tanf/{n}")
take(296, "policy", "us-ms/policy/mdhs/ccdf/market-rate-survey-2024")
take(297, "manual", "us-ms/manual/mdhs/eccd/ccpp-policy-manual-2025-11", subtype="agency_policy_manual")
# us-mt
take(302, "policy", "us-mt/policy/legislature/tanf/2016-tanf-brochure")
take(303, "policy", "us-mt/policy/dphhs/tanf/temporary-assistance-for-needy-families")
take(304, "policy", "us-mt/policy/dphhs/ccdf/bbs-provider-rates-monthly")
take(305, "manual", "us-mt/manual/dphhs/ccdf/cc-21-eligibility-2018-07-07")
take(306, "manual", "us-mt/manual/dphhs/ccdf/cc-23-non-tanf-activity-2018-07-07")
take(307, "manual", "us-mt/manual/dphhs/ccdf/cc-26-income-table-2018-07-07")
take(308, "policy", "us-mt/policy/dphhs/ccdf/sliding-fee-scale-2023-07-01")
take(309, "manual", "us-mt/manual/dphhs/tanf/501-1-2018-01-01",
     note="the 2018-01-01 print of TANF 501-1 (dphhs.mt.gov/assets/hcsd/tanfmanual/); the manual's current section "
     "files are held in us-mt/manual/2026-09-10-tanf-state-policy-manual")
# us-nc
take(324, "statute", "us-nc/statute/chapter-108a/108a-27-01", request={"browser_user_agent": True},
     title="North Carolina General Statutes section 108A-27.01, Income eligibility and payment level for Work First Family Assistance",
     note="entry copied from manifests/us-nc-work-first-statute-official-documents.yaml (May-July 2026, never extracted)")
take(325, "policy", "us-nc/policy/dcdee/ccdf/market-rate-study-report-2024-09")
take(326, "manual", "us-nc/manual/dcdee/subsidized-child-care/chapter-4-cn-26-03")
take(327, "manual", "us-nc/manual/dcdee/subsidized-child-care/chapter-8-cn-26-03")
take(328, "manual", "us-nc/manual/dcdee/subsidized-child-care/chapter-7-2024-08-05")
take(329, "manual", "us-nc/manual/dcdee/subsidized-child-care/chapter-7-2024-08-black")
take(330, "manual", "us-nc/manual/dcdee/subsidized-child-care/acronyms-and-definitions")
take(331, "policy", "us-nc/policy/dss/tanf/state-plan-2022-2025")
take(332, "policy", "us-nc/policy/dss/tanf/state-plan-2019-2022-draft")
take(333, "policy", "us-nc/policy/dss/tanf/efs-wf-29-2015a")
# us-nd
take(336, "policy", "us-nd/policy/legislature/ccdf/testimony-hb-2190-2023-01-18")
take(337, "regulation", "us-nd/regulation/ndac/75-02-01.3", extraction={
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>75-02-01\.3-\d{2}(?:\.\d)?)\.\s+(?P<heading>.+)$",
})
take(338, "policy", "us-nd/policy/hhs/ccdf/child-care-assistance-program")
take(339, "policy", "us-nd/policy/hhs/ccdf/ccap-updates-2026")
take(340, "policy", "us-nd/policy/hhs/ccdf/ccap-provider-information")
take(341, "manual", "us-nd/manual/hhs/tanf/archive/2016-ml-3482/400-19-55-20-15")
take(342, "manual", "us-nd/manual/hhs/tanf/archive/2023-ml-3740/400-19-110-05")
take(343, "manual", "us-nd/manual/hhs/tanf/archive/2024-ml-3869/400-19-110-05")
take(344, "manual", "us-nd/manual/hhs/tanf/archive/2025-release-25.1/400-19-110-05")
take(346, "manual", "us-nd/manual/hhs/ccap/ml-3909-2025-05-01")
# us-ne
take(350, "policy", "us-ne/policy/dhhs/ccdf/ccdf-state-plan-ffy2019-2021-amended-2020-06-11")
take(351, "policy", "us-ne/policy/dhhs/ccdf/lb-485-faq-2021-08")
take(352, "policy", "us-ne/policy/dhhs/ccdf/rate-structure-faq")
take(353, "policy", "us-ne/policy/dhhs/ccdf/subsidy-rates-2025-2027", subtype="rate_or_copay_schedule")
take(354, "policy", "us-ne/policy/dhhs/tanf/468-000-209")
take(355, "policy", "us-ne/policy/dhhs/ccdf/cc-subsidy-provider-booklet")
take(356, "policy", "us-ne/policy/dhhs/tanf/nebraska-state-tanf-plan-2025")
take(357, "policy", "us-ne/policy/dhhs/ccdf/title-392-complete-2008")
take(358, "policy", "us-ne/policy/dhhs/ccdf/title-392-guidance-document")
take(359, "policy", "us-ne/policy/dhhs/tanf/title-468-guidance-document")
take(360, "policy", "us-ne/policy/dhhs/tanf/temporary-assistance-for-needy-families")
take(361, "policy", "us-ne/policy/dhhs/tanf/title-468-index")
take(362, "policy", "us-ne/policy/legislature/ccdf/revisor-datelist-2014")
take(363, "statute", "us-ne/statute/session-laws/103/lb359")
take(364, "statute", "us-ne/statute/session-laws/109/lb304")
for i, n in ((365, "43/43-512"), (366, "43/43-513"), (367, "68/68-1206"), (368, "68/68-1713"), (369, "68/68-1726")):
    take(i, "statute", f"us-ne/statute/{n}")
take(370, "policy", "us-ne/policy/legislature/tanf/2024-tanf-report")
take(371, "regulation", "us-ne/regulation/title-392/complete-title-pdf",
     note="the Secretary of State's whole-title print of 392 NAC (chapters 1-5, effective 2020-09-15); the five "
     "chapter files are held in us-ne/regulation/2026-09-15-ccdf-subsidy-rules")

# Rows that point at a document another row takes (same file after a redirect, or the same
# document at a newer address): row -> row whose document holds it.
# row -> (taken row, note[, citation path when the row names one section of the taken document])
SAME_AS: dict[int, tuple] = {
    210: (209, "606 CMR 10.04 is a section of 606 CMR 10.00 (Justia is a mirror)", "us-ma/regulation/eec/606-cmr/10"),
    285: (284, "13 CSR 40-2.310 (Cornell is a mirror)", "us-mo/regulation/13-csr/40-2/310"),
    286: (284, "13 CSR 40-2.325 (Cornell is a mirror)", "us-mo/regulation/13-csr/40-2/325"),
    287: (283, "5 CSR 25-200.050 (Cornell is a mirror)", "us-mo/regulation/5-csr/25-200/050"),
    288: (283, "5 CSR 25-200.060 (Cornell is a mirror)", "us-mo/regulation/5-csr/25-200/060"),
    348: (347, "N.D.A.C. 75-02-01.2-35 (Cornell is a mirror)", "us-nd/regulation/ndac/75-02-01.2/75-02-01.2-35"),
    349: (347, "N.D.A.C. 75-02-01.2-51 (Cornell is a mirror)", "us-nd/regulation/ndac/75-02-01.2/75-02-01.2-51"),
    206: (204, "the old 67.pdf address answers HTTP 404; the Office of the State Register posts Title 67 as 67.docx"),
    90: (91, "dhs.dc.gov answers both addresses with the same page"),
    190: (181, "the karmaservice ToPDF address of KAR document 10239 answers HTTP 500; the same document "
          "is served as document.engrossed.pdf (row 181)"),
    199: (192, "louisianabelieves.com redirects to the same doe.louisiana.gov file"),
    201: (192, "louisianabelieves.com redirects to the same doe.louisiana.gov file"),
    202: (192, "louisianabelieves.com redirects to the same doe.louisiana.gov file"),
    203: (192, "louisianabelieves.com redirects to the same doe.louisiana.gov file"),
    207: (195, "the .pdf print of LAC 28:CLXV is gone (HTTP 404); the Office of the State Register posts the "
          "same part as 28v165.docx (row 195)"),
}

# The decision's citation path for a taken row that names one section of the document.
DECISION_PATH: dict[int, str] = {
    209: "us-ma/regulation/eec/606-cmr/10",
    284: "us-mo/regulation/13-csr/40-2/300",
    347: "us-nd/regulation/ndac/75-02-01.2/75-02-01.2-22",
}

# Rows decided without extraction: row -> (status, scope, citation_path, official_url, note)
DECISIONS: dict[int, tuple[str, str, str, str, str]] = {}


def decide(row: int, status: str, scope: str = "", path: str = "", url: str = "", note: str = "") -> None:
    DECISIONS[row] = (status, scope, path, url, note)


# ALREADY-HELD
decide(63, "ALREADY-HELD", "us-ca/statute/2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018",
       "us-ca/statute/wic/11450.12", "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=11450.12",
       "WIC 11450.12 taken from LegInfo by the California section extractor on 2026-06-25")
decide(71, "ALREADY-HELD", "us-co/regulation/2026-09-10-tanf-state-policy-manual", "us-co/regulation/9-ccr-2503-6/3.605",
       "https://www.coloradosos.gov/CCR/GenerateRulePdf.do?ruleVersionId=12030&fileName=9%20CCR%202503-6",
       "9 CCR 2503-6 section 3.605 from the Secretary of State's current rule PDF (Cornell is a mirror)")
decide(83, "ALREADY-HELD", "us-ct/statute/2026-09-14-income-tax-chapter-title-17b", "us-ct/statute/chapter-319s",
       "https://www.cga.ct.gov/current/pub/chap_319s.htm",
       "the address answers (the 2026-10-06 check failed on the missing Go Daddy G2 intermediate); whole title 17b held")
decide(87, "ALREADY-HELD", "us-ct/statute/2026-09-14-income-tax-chapter-title-17b", "us-ct/statute/chapter-319t",
       "https://www.cga.ct.gov/current/pub/chap_319t.htm",
       "the address answers (missing Go Daddy G2 intermediate on 2026-10-06); whole title 17b held")
decide(88, "ALREADY-HELD", "us-dc/manual/2026-07-19-dc-child-care-subsidy", "us-dc/manual/osse/child-care-subsidy-policy-manual",
       "", "manifests/us-dc-child-care-subsidy-manual.yaml was extracted on 2026-07-19 (88 rows)")
decide(89, "ALREADY-HELD", "us-dc/statute/2026-05-19-title-4", "us-dc/statute/4/chapter-2/subchapter-i",
       "https://code.dccouncil.gov/us/dc/council/code/titles/4/chapters/2/subchapters/I",
       "D.C. Code title 4 held whole from the Council's code")
decide(96, "ALREADY-HELD", "us-de/regulation/2026-07-03-de-tanf-rules", "us-de/regulation/title-16/4000-financial-responsibility",
       "https://regulations.delaware.gov/AdminCode/title16/4000",
       "the archive address serves the same DSSM 4000 Financial Responsibility PDF (Last-Modified 2025-03-03) as the held scope")
for r, sec in ((101, "4002"), (102, "4007"), (103, "4008")):
    decide(r, "ALREADY-HELD", "us-de/regulation/2026-07-03-de-tanf-rules", f"us-de/regulation/title-16/4000-financial-responsibility/{sec}",
           "https://regulations.delaware.gov/AdminCode/title16/4000", f"16 Del. Admin. Code 4000 section {sec} (Cornell is a mirror)")
decide(100, "ALREADY-HELD", "us-de/regulation/2026-07-03-de-tanf-rules", "us-de/regulation/title-16/4000-financial-responsibility",
       "https://regulations.delaware.gov/AdminCode/title16/4000",
       "help.workworldapp.com is third-party software help (WorkWORLD, VCU); the TANF/GA earned income disregards it "
       "restates are DSSM 4000 rules, held")
decide(119, "ALREADY-HELD", "us-hi/statute/2026-07-03-hi-hrs-us-hi-chapter-346", "us-hi/statute/346-71",
       "https://www.capitol.hawaii.gov/hrscurrent/Vol07_Ch0346-0398/HRS0346/HRS_0346-0071.htm",
       "HRS 346-71 held from the chapter 346 scope; capitol.hawaii.gov answered HTTP 403 to the 2026-10-06 check")
decide(126, "ALREADY-HELD", "us-ia/regulation/2026-07-03-ia-fip-admin-rules", "us-ia/regulation/iac/441/41/41.26",
       "https://www.legis.iowa.gov/docs/iac/chapter/441.41.pdf", "rule 441-41.26 held in the current chapter 41 print")
decide(127, "ALREADY-HELD", "us-ia/regulation/2026-07-03-ia-fip-admin-rules", "us-ia/regulation/iac/441/41/41.27",
       "https://www.legis.iowa.gov/docs/iac/chapter/441.41.pdf", "rule 441-41.27 (Cornell is a mirror)")
decide(128, "ALREADY-HELD", "us-id/regulation/2026-09-15-ccdf-subsidy-rules", "us-id/regulation/idapa/16/06/12",
       "https://files.dfm.idaho.gov/dfm-admin-website/rules/current/16/160612.pdf", "IDAPA 16.06.12, wave 5")
decide(130, "ALREADY-HELD", "us-id/policy/2026-09-13-ccdf-rate-schedules", "us-id/policy/ccdf/rate-schedules/iccp-local-market-rates-2025-07-01",
       "https://publicdocuments.dhw.idaho.gov/WebLink/ElectronicFile.aspx?docid=19508&dbid=0&repo=PUBLIC-DOCUMENTS",
       "Laserfiche DocView id=19508; the held scope fetched the same document through the repository's ElectronicFile endpoint")
decide(131, "ALREADY-HELD", "us-id/policy/2026-09-13-ccdf-rate-schedules", "us-id/policy/ccdf/rate-schedules/iccp-copay-chart-2025-10-01",
       "https://publicdocuments.dhw.idaho.gov/WebLink/ElectronicFile.aspx?docid=4671&dbid=0&repo=PUBLIC-DOCUMENTS",
       "Laserfiche DocView id=4671; held through the ElectronicFile endpoint")
for r, reg in ((223, "03"), (224, "12"), (225, "13"), (226, "17"), (238, "13")):
    decide(r, "ALREADY-HELD",
           "us-md/regulation/2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-consolidated",
           f"us-md/regulation/title-07/subtitle-03/chapter-03/regulation-{reg}", "https://regs.maryland.gov",
           f"COMAR 07.03.03.{reg} held from the Division of State Documents' COMAR publication")
for r, path, note in ((244, "us-me/regulation/dhhs/ofi/chapter-331", "10-144 CMR ch. 331"),
                      (245, "us-me/regulation/dhhs/ofi/chapter-331", "10-144 CMR ch. 331 charts, in the chapter file"),
                      (246, "us-me/regulation/dhhs/ofi/chapter-331", "10-144 CMR ch. 331 part III, in the chapter file"),
                      (247, "us-me/regulation/dhhs/ofi/chapter-331", "10-144 CMR ch. 331 part IV, in the chapter file")):
    decide(r, "ALREADY-HELD", "us-me/regulation/2026-07-03-me-tanf-regulation", path,
           "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c331-2025-231%20%28AMD%29.docx",
           f"{note} (Cornell is a mirror); the Secretary of State's chapter 331 file is held")
decide(248, "ALREADY-HELD", "us-me/regulation/2026-09-15-ccdf-subsidy-rules", "us-me/regulation/dhhs/ocfs/10-148-cmr-chapter-6",
       "", "148c006.docx answers HTTP 404; 10-148 CMR ch. 6 (CCAP rules, 8/18/2025) was taken in wave 5 from the DHHS site")
decide(249, "ALREADY-HELD", "us-me/statute/2026-07-03-me-tanf-statute", "us-me/statute/title-22/3762/assistance-standards",
       "", "22 M.R.S. 3762 is held under the July path us-me/statute/title-22/3762/assistance-standards, not the bundle's "
       "us-me/statute/title-22/3762; the bundle path needs a join or a re-path")
decide(251, "ALREADY-HELD", "us-mi/manual/2026-07-17-mi-bridges-manual", "us-mi/manual/mdhhs/bridges/bem/710",
       "https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/710.pdf", "BEM 710, same file (path case differs)")
decide(300, "ALREADY-HELD", "us-ms/policy/2026-09-13-tanf-state-plan", "us-ms/policy/acf/tanf-plan/2020",
       "https://www.sos.ms.gov/adminsearch/ACCode/00000566c.pdf", "Miss. Admin. Code tit. 18 pt. 19 is the TANF State Plan as filed (Cornell is a mirror)")

# OUT-OF-SCOPE
decide(112, "OUT-OF-SCOPE", note="Georgia Budget and Policy Institute explainer (advocacy organization's analysis)")
decide(167, "OUT-OF-SCOPE", note="Urban Institute Welfare Rules Databook (third-party research compilation)")
decide(291, "OUT-OF-SCOPE", note="CDC NCHS urban-rural classification scheme (statistical dataset)")
decide(298, "OUT-OF-SCOPE", note="Census Bureau CBSA delineation file (statistical dataset, .xls)")
decide(335, "OUT-OF-SCOPE", note="Power BI dashboard (app.powerbigov.us report viewer, no document text)")
decide(220, "OUT-OF-SCOPE", note="directory listing of the DHS FIA AT-IM 2017 folder (an index of files, no text of its own)")

# OUTREACH (publisher blocks the corpus client; documented walls)
for r in (15, 16, 17, 18):
    decide(r, "OUTREACH", note="AZ DES (des.az.gov, dbmefaapolicy.azdes.gov): Cloudflare challenge to plain and "
           "browser-impersonated clients, documented 2026-09-13/14/15; not worked around")
decide(235, "OUTREACH", note="earlychildhood.marylandpublicschools.org answered HTTP 403 Cloudflare 'Just a moment' "
       "(2026-10-06); the MSDE early-childhood host's challenge is documented in the 2026-09-13 re-probe")
decide(218, "ABSENT", url="https://www.mass.gov/doc/interim-income-eligible-child-care-financial-assistance-program-policies-october-1-2023/download",
       note="mass.gov answers HTTP 404 to the documented browser-impersonated client (2026-10-06); the October 2023 interim "
       "policies were superseded by CCFA-25-03 (row 208) and the 2026 consolidated policies (row 212)")
decide(299, "OUTREACH", note="Mississippi Code is published only through LexisNexis (vendor); Justia is a mirror")


# --------------------------------------------------------------------------------------
# Manifest writer
# --------------------------------------------------------------------------------------


def version_for(jurisdiction: str, cls: str) -> str:
    return f"{SOURCE_AS_OF}-w6-{FAMILY_BY_CLASS[cls]}-{jurisdiction.removeprefix('us-')}"


def manifest_path(jurisdiction: str, cls: str) -> Path:
    return MANIFEST_DIR / f"{jurisdiction}-tanf-ccdf-w6-{FAMILY_BY_CLASS[cls].removeprefix('tanf-ccdf-')}.yaml"


def build_entries(rows: list[dict[str, str]], probe_data: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for index, (cls, path, overrides) in sorted(TAKE.items()):
        row = rows[index]
        jurisdiction = row["jurisdiction"]
        if not path.startswith(f"{jurisdiction}/{cls}/"):
            raise SystemExit(f"row {index}: path {path} does not start with {jurisdiction}/{cls}/")
        rec = probe_data.get(str(index), {})
        url = overrides.get("url") or row["bundle_url"]
        host = urllib.parse.urlsplit(url).netloc.lower()
        agency, publisher = HOSTS.get(host, ("", STATE_NAMES[jurisdiction]))
        fmt = overrides.get("format") or source_format(rec, url)
        expression_date, basis = (overrides["expression_date"], "manual") if overrides.get("expression_date") else auto_date(rec)
        program = row["programs"].upper()
        entry: dict[str, Any] = {
            "source_id": f"{jurisdiction}-w6-{slug(path.split('/', 2)[2], 120).replace('.', '-').replace('/', '-')}",
            "jurisdiction": jurisdiction,
            "document_class": cls,
            "title": overrides.get("title") or auto_title({**row, "bundle_url": url}, rec),
            "source_url": url,
            "source_format": fmt,
            "source_as_of": SOURCE_AS_OF,
            "expression_date": expression_date,
            "citation_path": path,
        }
        if overrides.get("download_url"):
            entry["download_url"] = overrides["download_url"]
        if overrides.get("request"):
            entry["request"] = overrides["request"]
        if overrides.get("extraction"):
            entry["extraction"] = overrides["extraction"]
        metadata: dict[str, Any] = {
            "primary_source": True,
            "source_authority": publisher,
            "official_publisher": publisher,
            "document_subtype": overrides.get("subtype") or ("statute_section" if cls == "statute" else f"agency_{cls}_document"),
            "program": program,
            "federal_program": program,
            "source_discovery_group": f"{jurisdiction}/{cls}/{row['programs']}",
            "discovered_via": f"{DISCOVERED_VIA}; bundle id {row['id']}",
            "bundle_tiers": row["tiers"],
            "work_order_action": row["action"],
            "expression_date_basis": basis,
        }
        if rec.get("lm"):
            metadata["source_last_modified"] = http_date(rec["lm"])
        if rec.get("pages"):
            metadata["page_count"] = rec["pages"]
        if overrides.get("note"):
            metadata["source_note"] = overrides["note"]
        if agency:
            metadata["agency_segment"] = agency
        entry["metadata"] = metadata
        grouped[(jurisdiction, cls)].append(entry)
    return grouped


def write_manifests(grouped: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
    for (jurisdiction, cls), entries in sorted(grouped.items()):
        paths = [e["citation_path"] for e in entries]
        dupes = [p for p, n in collections.Counter(paths).items() if n > 1]
        if dupes:
            raise SystemExit(f"{jurisdiction}/{cls}: duplicate citation paths {dupes}")
        payload = {"version": version_for(jurisdiction, cls), "documents": entries}
        out = manifest_path(jurisdiction, cls)
        header = (
            f"# Wave 6 ({GROUP}): {STATE_NAMES[jurisdiction]} TANF/CCDF bundle documents, class {cls}.\n"
            "# Generated by scripts/build_w6_tanf_ccdf_ak_ne_manifests.py; edit the generator, not this file.\n"
        )
        out.write_text(header + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=110))
        print(f"{out.relative_to(REPO_ROOT)}: {len(entries)} documents", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--work-order", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ca-bundle")
    p.add_argument("--extra", type=Path, help="JSON {key: url} of extra addresses to probe")
    m = sub.add_parser("manifests")
    m.add_argument("--work-order", type=Path, required=True)
    m.add_argument("--probe", type=Path, required=True)
    args = parser.parse_args()
    rows = read_work_order(args.work_order)
    if args.cmd == "probe":
        extra = json.loads(args.extra.read_text()) if args.extra else {}
        probe(rows if not extra else [], args.out, args.ca_bundle, extra)
        return
    probe_data = json.loads(args.probe.read_text())
    overlap = set(TAKE) & (set(DECISIONS) | set(SAME_AS))
    if overlap:
        raise SystemExit(f"rows both taken and decided: {sorted(overlap)}")
    write_manifests(build_entries(rows, probe_data))


if __name__ == "__main__":
    main()
