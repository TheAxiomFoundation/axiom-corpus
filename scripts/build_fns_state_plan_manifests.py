"""Build the FNS-hosted state plan manifests (SNAP E&T state plans, WIC state
plans, SNAP 7 CFR 272.2 plans of operation) and the queue that tracks them,
`manifests/fns-state-plan-agent-queue.yaml`.

Work order: docs/coverage/needs-closure-2026-09-11/snap.md (elements snap_s31,
snap_s32) and wic.md (element wic_s30). Publisher policy is the one every agent
queue carries: the Food and Nutrition Administration (fns.usda.gov / fna.usda.gov,
FNS until 2026-06-01) and the state agency are the only sources; no mirrors,
proxies, archived copies or State Options Reports.

SNAP E&T state plans (7 CFR 273.7(c), element snap_s31). FNA posts one page per
state under https://www.fna.usda.gov/snap-et/stateplan (the closure check's
`fns.usda.gov/snap/et/plans` path now answers 404 on every host; the front door
answers 200 to a plain browser user agent again, so the origin host is not
needed). Each state page carries one "Print Version" PDF,
`/sites/default/files/resource-files/<st>-snapet-stateplanFY26.pdf`. The index
lists 47 of the 51 state agencies (46 states plus DC); New Mexico's entry links
the state's own FFY 2025 PDF on hca.nm.gov, and Arkansas, Colorado and Texas are
not listed. Colorado's FFY 2026 plan is already in the corpus
(`us-co/policy/co-cdhs-snap-et-state-plan-ffy2026`). Arkansas posts its FY26
original submission in the DHS media library (the SNAP E&T page links only the
provider contact list). New Mexico posts the FFY 2026 final plan and its
Amendment 1 on the ISD plans-and-reports page, which are taken instead of the
FFY 2025 file FNA links. Texas posts none: TWC's SNAP program page links an HHSC
report page for the FFY 2024 plan that answers 404 and nothing newer, and the
HHSC site search and sitemap carry no E&T plan (details in the queue row).

WIC state plans (7 CFR 246.4, element wic_s30). FNA posts none (the resource
browser filtered to WIC returns no state plan; every guessed /wic/state-plan
path answers 404). The eight publishers the closure report names are built here
from their own pages: MT (2026 plan, one PDF per policy attachment), WV (FY 2025
plan page, one PDF per chapter and appendix; ten Appendix II files answer 404),
UT (FY 2027 plan, three section pages; the ten Section II drafts whose URL is
already in the released Utah manual scope are not re-taken), CT (Section 1
plan for program operations FY 2025 and the FY 2026 peer counseling update),
VT (2025 goals and objectives), MA (2027 plan PDF, mass.gov needs the Safari
fingerprint), WI (two FY 2025 sections; the /wic/state-plan.htm index answers
the publisher's own 403 page) and AL (2027 plan of program operations linked
from the WIC home page's public notice).

SNAP State Plan of Operation (7 CFR 272.2, element snap_s32). FNA does not post
them. Every state SNAP publisher index in the two SNAP queues was fetched and
its text searched for "plan of operation" / "state plan" (results in
PLAN_OF_OPERATION_CHECKS); no state posts the plan itself. The New Mexico
"State Verification Plan" the closure report named as a 272.2 attachment is the
MAGI-based Medicaid eligibility verification plan (Nov 2018), not a SNAP
document, and is not taken.

    uv run python scripts/build_fns_state_plan_manifests.py                 # everything
    uv run python scripts/build_fns_state_plan_manifests.py --only us-al,us-ak
    uv run python scripts/build_fns_state_plan_manifests.py --family wic
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin

import certifi
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "manifests" / "fns-state-plan-agent-queue.yaml"
WIC_QUEUE = ROOT / "manifests" / "wic-agent-queue.yaml"
SOURCE_AS_OF = dt.date.today().isoformat()
ET_VERSION = "2026-09-13-snap-et-state-plan"
WIC_VERSION = "2026-09-13-wic-state-plan"
FNA_INDEX = "https://www.fna.usda.gov/snap-et/stateplan"
FNA = "https://www.fna.usda.gov"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
RUN_NOTE = "docs/ingest-runs/2026-09-13-fns-state-plans.md"

STATES: dict[str, str] = {
    "us-al": "Alabama",
    "us-ak": "Alaska",
    "us-az": "Arizona",
    "us-ar": "Arkansas",
    "us-ca": "California",
    "us-co": "Colorado",
    "us-ct": "Connecticut",
    "us-de": "Delaware",
    "us-dc": "District of Columbia",
    "us-fl": "Florida",
    "us-ga": "Georgia",
    "us-hi": "Hawaii",
    "us-id": "Idaho",
    "us-il": "Illinois",
    "us-in": "Indiana",
    "us-ia": "Iowa",
    "us-ks": "Kansas",
    "us-ky": "Kentucky",
    "us-la": "Louisiana",
    "us-me": "Maine",
    "us-md": "Maryland",
    "us-ma": "Massachusetts",
    "us-mi": "Michigan",
    "us-mn": "Minnesota",
    "us-ms": "Mississippi",
    "us-mo": "Missouri",
    "us-mt": "Montana",
    "us-ne": "Nebraska",
    "us-nv": "Nevada",
    "us-nh": "New Hampshire",
    "us-nj": "New Jersey",
    "us-nm": "New Mexico",
    "us-ny": "New York",
    "us-nc": "North Carolina",
    "us-nd": "North Dakota",
    "us-oh": "Ohio",
    "us-ok": "Oklahoma",
    "us-or": "Oregon",
    "us-pa": "Pennsylvania",
    "us-ri": "Rhode Island",
    "us-sc": "South Carolina",
    "us-sd": "South Dakota",
    "us-tn": "Tennessee",
    "us-tx": "Texas",
    "us-ut": "Utah",
    "us-vt": "Vermont",
    "us-va": "Virginia",
    "us-wa": "Washington",
    "us-wv": "West Virginia",
    "us-wi": "Wisconsin",
    "us-wy": "Wyoming",
}

# FNA page slugs that are not the lower-cased state name without spaces.
FNA_SLUGS = {"us-dc": "dc"}

WIC_STATES = ("us-mt", "us-wv", "us-ut", "us-ct", "us-vt", "us-ma", "us-wi", "us-al")


# --------------------------------------------------------------------------- fetch helpers


class Fetched:
    def __init__(
        self,
        url: str,
        status: int | None,
        content: bytes,
        seconds: float,
        client: str,
        content_type: str = "",
        error: str | None = None,
        content_length: int | None = None,
    ) -> None:
        self.url = url
        self.status = status
        self.content = content
        self.seconds = seconds
        self.client = client
        self.content_type = content_type
        self.error = error
        self.content_length = content_length

    @property
    def size(self) -> int | None:
        return len(self.content) or self.content_length

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def record(self) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "url": self.url,
            "status": self.status,
            "bytes": self.size,
            "seconds": self.seconds,
            "client": self.client,
        }
        if self.error:
            rec["error"] = self.error
        return rec


def fetch(url: str, *, impersonate: str | None = None, method: str = "GET") -> Fetched:
    """Fetch a publisher URL with the plain client or, when the publisher needs it,
    the curl_cffi browser fingerprint (TLS verified against certifi in both cases)."""
    started = time.time()
    try:
        if impersonate:
            from curl_cffi import requests as curl_requests

            response = curl_requests.request(
                method,
                url,
                impersonate=impersonate,
                timeout=120,
                allow_redirects=True,
                verify=certifi.where(),
            )
            return Fetched(
                url,
                response.status_code,
                response.content,
                round(time.time() - started, 1),
                f"curl_cffi:{impersonate}",
                response.headers.get("content-type", ""),
                content_length=int(response.headers.get("content-length") or 0) or None,
            )
        response = requests.request(method, url, headers=UA, timeout=120, allow_redirects=True)
        return Fetched(
            url,
            response.status_code,
            response.content,
            round(time.time() - started, 1),
            "requests",
            response.headers.get("content-type", ""),
            content_length=int(response.headers.get("content-length") or 0) or None,
        )
    except Exception as exc:  # noqa: BLE001 - recorded, not raised
        return Fetched(
            url,
            None,
            b"",
            round(time.time() - started, 1),
            f"curl_cffi:{impersonate}" if impersonate else "requests",
            error=repr(exc)[:160],
        )


def links(text: str, base: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for href, inner in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.S | re.I):
        label = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", inner))).strip()
        label = label.replace("​", "").strip()
        out.append((urljoin(base, html.unescape(href)), label))
    return out


def slug(value: str) -> str:
    value = unquote(value).replace("&", " and ")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    value = re.sub(r"-+", "-", value)
    return value or "document"


def unique_slug(base: str, taken: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in taken:
        candidate = f"{base}-{index}"
        index += 1
    taken.add(candidate)
    return candidate


def dump_manifest(path: Path, version: str, documents: list[dict[str, Any]]) -> None:
    path.write_text(
        yaml.safe_dump(
            {"version": version, "documents": documents},
            sort_keys=False,
            allow_unicode=True,
            width=110,
        )
    )


def scope(jurisdiction: str, version: str) -> dict[str, str]:
    return {"jurisdiction": jurisdiction, "document_class": "policy", "version": version}


# --------------------------------------------------------------------------- SNAP E&T plans


def et_index() -> tuple[Fetched, dict[str, str]]:
    """The FNA index: state name -> state page URL (New Mexico -> its hca.nm.gov PDF)."""
    page = fetch(FNA_INDEX)
    listed: dict[str, str] = {}
    for href, label in links(page.text, FNA):
        if href.startswith(f"{FNA_INDEX}/") and label in STATES.values():
            listed.setdefault(label, href)
        if "hca.nm.gov" in href and label == "New Mexico":
            listed.setdefault(label, href)
    return page, listed


def et_metadata(
    jurisdiction: str,
    *,
    source_authority: str,
    publisher_page_url: str,
    index_note: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": source_authority,
        "document_subtype": "state_plan",
        "program": "SNAP",
        "topic": "employment_and_training",
        "fiscal_year": "2026",
        "effective_start": "2025-10-01",
        "effective_end": "2026-09-30",
        "source_status": "current",
        "policy_status": "current",
        "extraction_granularity": "pdf_page",
        "publisher_index_url": FNA_INDEX,
        "publisher_page_url": publisher_page_url,
        "source_discovery_group": f"{jurisdiction}/policy/snap-et-state-plan",
        "discovered_via": f"manual-review:fns-state-plan-agent-queue; {index_note}",
        "closure_element": "snap_s31",
    }
    if extra:
        metadata.update(extra)
    return metadata


def build_et(jurisdiction: str, listed: dict[str, str], index_page: Fetched) -> dict[str, Any]:
    name = STATES[jurisdiction]
    row: dict[str, Any] = {"index_url": FNA_INDEX, "listed_on_fna_index": name in listed}
    manifest_path = ROOT / "manifests" / f"{jurisdiction}-snap-et-state-plan.yaml"

    if jurisdiction == "us-co":
        row.update(
            status="already_in_corpus",
            existing_scope={
                "jurisdiction": "us-co",
                "document_class": "policy",
                "version": "2026-07-21-co-snap-policy",
            },
            existing_citation_path="us-co/policy/co-cdhs-snap-et-state-plan-ffy2026",
            notes="Colorado is not on the FNA index; its FFY 2026 plan (Google Drive link on cdhs.colorado.gov) "
            "is already in the released Colorado SNAP policy scope (425 page rows). Nothing to take.",
        )
        return row

    if jurisdiction == "us-tx":
        checks = [
            fetch("https://www.twc.texas.gov/programs/snap", impersonate="safari17_0"),
            fetch(
                "https://www.hhs.texas.gov/reports/2024/02/snap-et-state-plan-ffy-2024",
                impersonate="chrome120",
            ),
            fetch(
                "https://www.hhs.texas.gov/search?keys=SNAP+E%26T+State+Plan",
                impersonate="chrome120",
            ),
        ]
        row.update(
            status="not_published",
            checks=[c.record() for c in checks],
            notes="Texas is not on the FNA index. The Texas Workforce Commission SNAP program page (twc.texas.gov/programs/snap; "
            "the host answers an AWS WAF JavaScript challenge, HTTP 202 / 2,007 bytes, to the Chrome fingerprint and serves "
            "the page to the Safari fingerprint) links the SNAP E&T Guide, the TPP guide, TAC Title 40 Chapter 813 and an HHSC "
            "report page 'SNAP E&T State Plan FFY 2024' that answers HTTP 404; it links no FFY 2025 or 2026 plan. The HHSC "
            "site search for 'SNAP E&T State Plan' returns no plan, the Reports and Presentations listing ignores its keyword "
            "filter, and the HHSC sitemap (2,012 URLs) carries no E&T plan. Not taken; the plan exists (every state files "
            "one) but neither FNA nor the state posts it.",
        )
        return row

    documents: list[dict[str, Any]] = []
    if jurisdiction == "us-ar":
        page = fetch(
            "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/"
            "supplemental-nutrition-assistance-snap/snap-employment-and-training/",
            impersonate="safari17_0",
        )
        media = fetch(
            "https://humanservices.arkansas.gov/wp-json/wp/v2/media?search=State%20Plan&per_page=50",
            impersonate="safari17_0",
        )
        chosen = None
        if media.status == 200:
            import json

            for item in json.loads(media.text):
                if item.get("source_url", "").endswith(
                    "StatePlan_AR_2026_Original-Submission_126.pdf"
                ):
                    chosen = item
        if chosen is None:
            row.update(
                status="blocked_primary_source",
                checks=[page.record(), media.record()],
                notes="DHS media library did not answer or no longer lists the FY26 plan.",
            )
            return row
        pdf = fetch(chosen["source_url"], impersonate="safari17_0", method="HEAD")
        documents.append(
            {
                "source_id": "ar-snap-et-state-plan-ffy2026",
                "jurisdiction": "us-ar",
                "document_class": "policy",
                "title": "Arkansas SNAP E&T State Plan FFY 2026 (original submission)",
                "source_url": chosen["source_url"],
                "source_format": "pdf",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": "2025-10-01",
                "citation_path": "us-ar/policy/snap-et-state-plan/ffy2026",
                "request": {
                    "browser_impersonation": "safari17_0",
                    "browser_impersonation_direct": True,
                },
                "metadata": et_metadata(
                    "us-ar",
                    source_authority="Arkansas Department of Human Services, Division of County Operations",
                    publisher_page_url=page.url,
                    index_note="not on the FNA index; DHS media library (wp-json/wp/v2/media, search 'State Plan') item "
                    f"uploaded {chosen.get('date', '')[:10]}, title {chosen.get('title', {}).get('rendered', '')!r}",
                    extra={
                        "publisher_index_url": media.url,
                        "media_library_uploaded": chosen.get("date", "")[:10],
                        "tls_note": "humanservices.arkansas.gov (Cloudflare) answers 403 to the plain client and the Chrome "
                        "fingerprint; the Safari 17 fingerprint is served. curl_cffi needs CURL_CA_BUNDLE or "
                        "SSL_CERT_FILE pointed at certifi on this machine.",
                    },
                ),
            }
        )
        row.update(
            status="taken",
            publisher_page_url=page.url,
            media_library_url=media.url,
            pdf_url=chosen["source_url"],
            pdf_bytes=pdf.size,
            checks=[page.record(), media.record(), pdf.record()],
            notes="Arkansas is not on the FNA index. The DHS SNAP Employment and Training page links only the E&T provider "
            "contact list (SNAP-Employment-and-Training-7.24.26.pdf); the DHS media library lists 'StatePlan_AR_2026_"
            "Original Submission_126' (uploaded 2026-01-20, 112 pages, the FNS template 'USDA FNS SNAP E&T STATE PLAN "
            "... Arkansas AR 2026') and the FFY25 plan v1.3 (2024-11-26, superseded). The FY26 original submission is taken.",
        )
    elif jurisdiction == "us-nm":
        plans = fetch(
            "https://www.hca.nm.gov/income-support-division-plans-and-reports/",
            impersonate="chrome120",
        )
        found = {label: href for href, label in links(plans.text, "https://www.hca.nm.gov")}
        final = found.get("FFY 2026 E&T Final State Plan")
        amendment = found.get("FFY 2026 E&T State Plan Amendment")
        if not final:
            row.update(
                status="blocked_primary_source",
                checks=[plans.record()],
                notes="HCA plans-and-reports page no longer lists the FFY 2026 E&T plan.",
            )
            return row
        for source_id, title, url, suffix, extra in (
            (
                "nm-snap-et-state-plan-ffy2026",
                "New Mexico SNAP E&T State Plan FFY 2026 (original submission, approved)",
                final,
                "",
                {"plan_version": "original submission, FNS approved"},
            ),
            (
                "nm-snap-et-state-plan-ffy2026-amendment-1",
                "New Mexico SNAP E&T State Plan FFY 2026, Amendment 1",
                amendment,
                "/amendment-1",
                {"plan_version": "Amendment 1"},
            ),
        ):
            if not url:
                continue
            documents.append(
                {
                    "source_id": source_id,
                    "jurisdiction": "us-nm",
                    "document_class": "policy",
                    "title": title,
                    "source_url": url,
                    "source_format": "pdf",
                    "source_as_of": SOURCE_AS_OF,
                    "expression_date": "2025-10-01",
                    "citation_path": f"us-nm/policy/snap-et-state-plan/ffy2026{suffix}",
                    "metadata": et_metadata(
                        "us-nm",
                        source_authority="New Mexico Health Care Authority, Income Support Division",
                        publisher_page_url=plans.url,
                        index_note="FNA index links the state's FFY 2025 PDF; the ISD Plans and Reports page lists the FFY 2026 "
                        "final plan and Amendment 1, which supersede it",
                        extra={"publisher_index_url": plans.url, **extra},
                    ),
                }
            )
        row.update(
            status="taken",
            fna_linked_url=listed.get(name),
            publisher_page_url=plans.url,
            pdf_urls=[d["source_url"] for d in documents],
            checks=[plans.record()],
            notes="The FNA index entry for New Mexico is a link to the state's own FFY 2025 plan (hca.nm.gov, 107 pages). "
            "The HCA Income Support Division 'Plans and Reports' page lists the FFY 2026 E&T Final State Plan (77 pages, "
            "FNS approved) and the FFY 2026 Amendment 1 (99 pages), plus a FFY 2027 draft; the two FFY 2026 documents are "
            "taken as the current plan and the FFY 2025 file is not.",
        )
    else:
        page_url = listed.get(name)
        if not page_url:
            row.update(
                status="not_on_fna_index",
                checks=[index_page.record()],
                notes="Not listed on the FNA SNAP E&T State Plans index.",
            )
            return row
        page = fetch(page_url)
        pdfs = [
            (href, label)
            for href, label in links(page.text, FNA)
            if "/sites/default/files/" in href and href.lower().endswith(".pdf")
        ]
        updated = re.search(r"Page updated:\s*([A-Za-z]+ \d{1,2}, \d{4})", page.text)
        if page.status != 200 or not pdfs:
            row.update(
                status="blocked_primary_source",
                publisher_page_url=page_url,
                checks=[page.record()],
                notes="FNA state page did not answer or links no PDF.",
            )
            return row
        pdf_url, pdf_label = pdfs[0]
        head = fetch(pdf_url, method="HEAD")
        st = jurisdiction.split("-")[1]
        documents.append(
            {
                "source_id": f"{st}-snap-et-state-plan-ffy2026",
                "jurisdiction": jurisdiction,
                "document_class": "policy",
                "title": f"{name} SNAP E&T State Plan FFY 2026",
                "source_url": page_url,
                "download_url": pdf_url,
                "source_format": "pdf",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": "2025-10-01",
                "citation_path": f"{jurisdiction}/policy/snap-et-state-plan/ffy2026",
                "metadata": et_metadata(
                    jurisdiction,
                    source_authority=f"USDA Food and Nutrition Administration (Food and Nutrition Service until 2026-06-01), "
                    f"publishing the {name} SNAP state agency's plan",
                    publisher_page_url=page_url,
                    index_note=f"FNA SNAP E&T State Plans index, state page '{pdf_label}' link",
                    extra={"fna_page_updated": updated.group(1) if updated else None},
                ),
            }
        )
        row.update(
            status="taken",
            publisher_page_url=page_url,
            pdf_url=pdf_url,
            pdf_bytes=head.size,
            fna_page_updated=updated.group(1) if updated else None,
            checks=[page.record(), head.record()],
            notes=f"FNA state page '{name} SNAP E&T State Plan' ({pdf_label}); the PDF is the FNS template "
            "('USDA FNS SNAP E&T STATE PLAN'), text-extractable on every page, taken at page granularity like the "
            "Colorado precedent.",
        )
    dump_manifest(manifest_path, ET_VERSION, documents)
    row.update(
        target_manifest=str(manifest_path.relative_to(ROOT)),
        target_scope=scope(jurisdiction, ET_VERSION),
        document_count=len(documents),
    )
    return row


# --------------------------------------------------------------------------- WIC state plans


def wic_document(
    jurisdiction: str,
    source_id: str,
    title: str,
    url: str,
    citation_path: str,
    *,
    expression_date: str,
    source_authority: str,
    publisher_page_url: str,
    fiscal_year: str,
    plan_period: str,
    plan_status: str,
    extra: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    ocr: bool = False,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": jurisdiction,
        "document_class": "policy",
        "title": title,
        "source_url": url,
        "source_format": "pdf",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": expression_date,
        "citation_path": citation_path,
    }
    if request:
        doc["request"] = request
    if ocr:
        doc["extraction"] = {"ocr": True}
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": source_authority,
        "document_subtype": "state_plan",
        "program": "WIC",
        "fiscal_year": fiscal_year,
        "plan_period": plan_period,
        "plan_status": plan_status,
        "extraction_granularity": "pdf_page",
        "publisher_page_url": publisher_page_url,
        "source_discovery_group": f"{jurisdiction}/policy/wic-state-plan",
        "discovered_via": "manual-review:fns-state-plan-agent-queue; state WIC agency state plan page",
        "closure_element": "wic_s30",
    }
    if extra:
        metadata.update(extra)
    doc["metadata"] = metadata
    return doc


def build_wic(jurisdiction: str) -> dict[str, Any]:
    manifest_path = ROOT / "manifests" / f"{jurisdiction}-wic-state-plan.yaml"
    documents: list[dict[str, Any]] = []
    row: dict[str, Any] = {}
    checks: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if jurisdiction == "us-mt":
        index = "https://dphhs.mt.gov/ecfsd/wic/wicstateplan"
        page = fetch(index)
        checks.append(page.record())
        seen: set[str] = set()
        taken_slugs: set[str] = set()
        for href, label in links(page.text, index):
            if "/StatePlan/" not in href or href in seen:
                continue
            seen.add(href)
            rel = href.split("/StatePlan/", 1)[1]
            parts = rel.split("/")
            stem = re.sub(r"\.pdf$", "", parts[-1], flags=re.I)
            if stem.lower() == "montanawicmap":
                skipped.append(
                    {"url": href, "reason": "clinic location map, image only (no policy text)"}
                )
                continue
            group = parts[0]
            group_slug = {"GoalsObjectives": "goals-objectives", "Attachments": "attachments"}.get(
                group, slug(re.sub(r"^Section(\d)$", r"section-\1", group))
            )
            sub = ""
            if len(parts) == 3:
                sub = slug(re.sub(r"^Section\d", "", parts[1])) + "/"
            base = f"us-mt/policy/wic-state-plan/2026/{group_slug}/{sub}{slug(label if group != 'Attachments' else stem)}"
            path = unique_slug(base, taken_slugs)
            documents.append(
                wic_document(
                    "us-mt",
                    f"mt-wic-state-plan-2026-{slug(rel)}"[:120],
                    f"Montana WIC State Plan 2026: {label}",
                    href,
                    path,
                    expression_date="2025-10-01",
                    source_authority="Montana Department of Public Health and Human Services, Early Childhood and Family Support Division, WIC Program",
                    publisher_page_url=index,
                    fiscal_year="2026",
                    plan_period="2025-10-01 to 2026-09-30",
                    plan_status="current (published as the state's program policies)",
                    extra={"plan_component": rel},
                )
            )
        row.update(
            index_url=index,
            index_document_count=len(seen),
            notes=(
                "Montana publishes its WIC policies only as the 2026 Montana WIC State Plan page: Goals and Objectives (the FFY "
                "2023-2027 State Nutrition and Breastfeeding Services Plan), Section II attachments by functional area (vendor, "
                "nutrition, MIS, organization and management, NSA, caseload, certification/eligibility/coordination, food delivery, "
                "monitoring, civil rights), Section III attachments and plan Attachments (forms, food list, risk codes). Every PDF is "
                "text-extractable; the clinic location map is an image and is not taken."
            ),
        )
    elif jurisdiction == "us-wv":
        index = "https://dhhr.wv.gov/WIC/policyprocedure/Pages/West-Virginia-WIC-State-Plan-FY-2025.aspx"
        listing = "https://dhhr.wv.gov/WIC/policyprocedure/Pages/Default.aspx"
        page = fetch(index)
        checks.append(page.record())
        seen = set()
        taken_slugs = set()
        dead: list[str] = []
        for href, label in links(page.text, index):
            if "dhhr.wv.gov" not in href or not href.lower().endswith(".pdf") or href in seen:
                continue
            seen.add(href)
            head = fetch(href, method="HEAD")
            if head.status != 200:
                dead.append(href)
                skipped.append(
                    {"url": href, "label": label, "reason": f"publisher answers HTTP {head.status}"}
                )
                continue
            label_clean = label or unquote(href.rsplit("/", 1)[1])
            path = unique_slug(
                f"us-wv/policy/wic-state-plan/fy2025/{slug(label_clean)}", taken_slugs
            )
            documents.append(
                wic_document(
                    "us-wv",
                    f"wv-wic-state-plan-fy2025-{path.rsplit('/', 1)[1]}",
                    f"West Virginia WIC State Plan FY 2025: {label_clean}",
                    href,
                    path,
                    expression_date="2024-10-01",
                    source_authority="West Virginia Department of Health, Office of Nutrition Services, WIC Program",
                    publisher_page_url=index,
                    fiscal_year="2025",
                    plan_period="2024-10-01 to 2025-09-30",
                    plan_status="current (latest plan posted; the FY 2024 page is also posted)",
                    ocr=True,
                )
            )
        row.update(
            index_url=listing,
            plan_page_url=index,
            index_document_count=len(seen),
            dead_links=dead,
            notes=(
                "The WV WIC Policy/Procedure index links 'West Virginia WIC State Plan FY 2025' and 'FY 2024' pages beside the "
                "eleven policy chapters (the manual, released scope). The FY 2025 page lists the plan chapters I-XI (Food Delivery, "
                "Nutrition Services, MIS, Organization and Management, NSA, Food Funds, Caseload, Certification, Monitoring, Civil "
                "Rights), the FY 2024 policy status lists and the appendices; ten 'State Plan 2025/Appendix II' files answer HTTP "
                "404 on the publisher and are recorded, not taken. Four appendices are image-only (contact sheet, indirect cost "
                "rate agreement, data sharing agreement, authorized user report), so the scope extracts with ocr: true."
            ),
        )
    elif jurisdiction == "us-ut":
        index = "https://wic.utah.gov/about/wic-policies/proposed-state-plan/"
        page = fetch(index)
        checks.append(page.record())
        released = yaml.safe_load((ROOT / "manifests" / "us-ut-wic-policy-manual.yaml").read_text())
        released_urls = {d["source_url"] for d in released["documents"]}
        section_pages = [
            (href, label)
            for href, label in links(page.text, "https://wic.utah.gov")
            if href.startswith(index) and href.rstrip("/") != index.rstrip("/")
        ]
        taken_slugs = set()
        seen = set()
        total = 0
        for section_url, section_label in section_pages:
            section_page = fetch(section_url)
            checks.append(section_page.record())
            roman = re.match(r"Section\s+([IVX]+)", section_label)
            section_slug = f"section-{roman.group(1).lower()}" if roman else slug(section_label)
            main = re.search(r"<main.*?</main>", section_page.text, re.S)
            body = main.group(0) if main else section_page.text
            for href, label in links(body, "https://wic.utah.gov"):
                if not re.search(r"\.pdf$", href, re.I) or href in seen:
                    continue
                seen.add(href)
                total += 1
                if href in released_urls:
                    skipped.append(
                        {
                            "url": href,
                            "label": label,
                            "reason": "same file already in us-ut/manual/2026-09-10-wic-state-policy-manual",
                        }
                    )
                    continue
                if re.search(r"No-policies", href):
                    skipped.append(
                        {"url": href, "label": label, "reason": "placeholder ('No policies')"}
                    )
                    continue
                path = unique_slug(
                    f"us-ut/policy/wic-state-plan/fy2027/{section_slug}/{slug(label)}", taken_slugs
                )
                documents.append(
                    wic_document(
                        "us-ut",
                        f"ut-wic-state-plan-fy2027-{section_slug}-{path.rsplit('/', 1)[1]}"[:120],
                        f"Utah WIC State Plan FY 2027, {section_label}: {label}",
                        href,
                        path,
                        expression_date="2026-10-01",
                        source_authority="Utah Department of Health and Human Services, WIC Program",
                        publisher_page_url=section_url,
                        fiscal_year="2027",
                        plan_period="2026-10-01 to 2027-09-30",
                        plan_status="proposed (FY 2027 draft posted for comment)",
                        extra={"plan_section": section_label},
                    )
                )
        row.update(
            index_url=index,
            index_document_count=total,
            section_pages=[u for u, _ in section_pages],
            notes=(
                "The Utah WIC 'State Plan' page (wic.utah.gov/about/wic-policies/proposed-state-plan) posts the FY 2027 Utah WIC "
                "State Plan as three section pages: Section I Goals and Objectives (1 PDF), Section II Local Agency Policy and "
                "Procedure Manual (110 draft policies) and Section III State Operations (57 PDFs). Ten Section II files are the same "
                "URLs the released Utah WIC manual scope already carries and are not re-taken; the 'No policies' placeholder is "
                "skipped. Every PDF is text-extractable."
            ),
        )
    elif jurisdiction == "us-ct":
        index = "https://portal.ct.gov/dph/wic/ct-wic-state-plan"
        page = fetch(index)
        checks.append(page.record())
        for href, _label in links(page.text, "https://portal.ct.gov"):
            if "state-plan-policies---section-1" not in href:
                continue
            if "bf-peer-counseling" in href:
                documents.append(
                    wic_document(
                        "us-ct",
                        "ct-wic-state-plan-bf-peer-counseling-update-fy2026",
                        "Connecticut WIC State Plan: Breastfeeding Peer Counseling Program Update to Implementation Plan FY 2026",
                        href,
                        "us-ct/policy/wic-state-plan/fy2026/bf-peer-counseling-program-update",
                        expression_date="2025-10-01",
                        source_authority="Connecticut Department of Public Health, WIC Program",
                        publisher_page_url=index,
                        fiscal_year="2026",
                        plan_period="2025-10-01 to 2026-09-30",
                        plan_status="current",
                        ocr=True,
                    )
                )
            else:
                documents.append(
                    wic_document(
                        "us-ct",
                        "ct-wic-state-plan-section-1-program-operations-fy2025",
                        "Connecticut WIC State Plan Section 1: State Plan for Program Operations FY 2025",
                        href,
                        "us-ct/policy/wic-state-plan/fy2025/section-1-state-plan-for-program-operations",
                        expression_date="2024-10-01",
                        source_authority="Connecticut Department of Public Health, WIC Program",
                        publisher_page_url=index,
                        fiscal_year="2025",
                        plan_period="2024-10-01 to 2025-09-30",
                        plan_status="current (latest Section 1 posted)",
                        ocr=True,
                    )
                )
        row.update(
            index_url=index,
            index_document_count=len(documents),
            notes=(
                "The CT DPH 'WIC State Plan' page links Section 1 'CT State Plan for Program Operations FY 2025' (92 pages) and "
                "the FY 2026 breastfeeding peer counseling update, then the State Plan Policies series 100-400 (the manual, "
                "released scope us-ct/manual/2026-09-10-wic-state-policy-manual). The two Section 1 PDFs are taken; one page is "
                "image-only so the scope extracts with ocr: true."
            ),
        )
    elif jurisdiction == "us-vt":
        index = "https://www.healthvermont.gov/family/wic/wic-plans-reports"
        page = fetch(index)
        checks.append(page.record())
        for href, _label in links(page.text, "https://www.healthvermont.gov"):
            if href.endswith("2025-WIC-State-Plan.pdf"):
                documents.append(
                    wic_document(
                        "us-vt",
                        "vt-wic-state-plan-2025-goals-objectives",
                        "Vermont WIC State Plan 2025: Goals and Objectives",
                        href,
                        "us-vt/policy/wic-state-plan/2025/goals-and-objectives",
                        expression_date="2024-10-01",
                        source_authority="Vermont Department of Health, WIC Program",
                        publisher_page_url=index,
                        fiscal_year="2025",
                        plan_period="2024-10-01 to 2025-09-30",
                        plan_status="current (goals and objectives only; the rest of the plan is not posted)",
                    )
                )
                break
        row.update(
            index_url=index,
            index_document_count=len(documents),
            notes=(
                "Vermont posts no WIC policy manual; the WIC 'Plans & Reports' page links '2025 State Plan Goals and Objectives' "
                "(5 pages) beside data reports. That document is the only state plan text posted and is taken."
            ),
        )
    elif jurisdiction == "us-ma":
        index = "https://www.mass.gov/info-details/massachusetts-wic-state-plan"
        page = fetch(index, impersonate="safari17_0")
        checks.append(page.record())
        for href, _label in links(page.text, "https://www.mass.gov"):
            if "massachusetts-wic-state-plan-2027/download" in href:
                documents.append(
                    wic_document(
                        "us-ma",
                        "ma-wic-state-plan-ffy2027",
                        "Massachusetts WIC State Plan 2027",
                        href,
                        "us-ma/policy/wic-state-plan/ffy2027",
                        expression_date="2026-10-01",
                        source_authority="Massachusetts Department of Public Health, WIC Nutrition Program",
                        publisher_page_url=index,
                        fiscal_year="2027",
                        plan_period="2026-10-01 to 2027-09-30",
                        plan_status="current (FFY 2027 plan as posted)",
                        request={
                            "browser_impersonation": "safari17_0",
                            "browser_impersonation_direct": True,
                        },
                        extra={
                            "tls_note": "mass.gov answers HTTP 403 to non-browser clients; the Safari 17 fingerprint is served"
                        },
                    )
                )
                break
        row.update(
            index_url=index,
            index_document_count=len(documents),
            notes=(
                "The mass.gov 'Massachusetts WIC State Plan' page links the 'Massachusetts WIC State Plan 2027' PDF (41 pages). "
                "The WIC Program Manual it names is not published (wic-agent-queue). Taken with the Safari fingerprint."
            ),
        )
    elif jurisdiction == "us-wi":
        index = "https://www.dhs.wisconsin.gov/wic/state-plan.htm"
        page = fetch(index, impersonate="safari17_0")
        checks.append(page.record())
        for stem, label in (
            (
                "certification-eligibility-coordination",
                "Certification, Eligibility and Coordination of Services",
            ),
            ("caseload-management", "Caseload Management"),
        ):
            href = f"https://www.dhs.wisconsin.gov/wic/{stem}.pdf"
            head = fetch(href, impersonate="safari17_0", method="HEAD")
            checks.append(head.record())
            if head.status != 200:
                skipped.append({"url": href, "reason": f"HTTP {head.status}"})
                continue
            documents.append(
                wic_document(
                    "us-wi",
                    f"wi-wic-state-plan-fy2025-{stem}",
                    f"Wisconsin WIC State Plan FY 2025: {label}",
                    href,
                    f"us-wi/policy/wic-state-plan/fy2025/{stem}",
                    expression_date="2024-10-01",
                    source_authority="Wisconsin Department of Health Services, WIC Program",
                    publisher_page_url="https://www.dhs.wisconsin.gov/wic/professionals.htm",
                    fiscal_year="2025",
                    plan_period="2024-10-01 to 2025-09-30",
                    plan_status="current (the two sections the publisher serves)",
                    request={
                        "browser_impersonation": "safari17_0",
                        "browser_impersonation_direct": True,
                    },
                    extra={
                        "tls_note": "dhs.wisconsin.gov answers HTTP 403 to the Chrome fingerprint; the Safari 17 fingerprint is served"
                    },
                )
            )
        row.update(
            index_url=index,
            index_document_count=len(documents),
            notes=(
                "dhs.wisconsin.gov serves the FY 2025 state plan sections wic/certification-eligibility-coordination.pdf and "
                "wic/caseload-management.pdf (the WIC queue found them; the WIC home, Providers and Professionals pages link no "
                "manual), while the index page wic/state-plan.htm answers the publisher's own HTTP 403 page (152 KB) to every "
                "client and the site search returns nothing. The two served sections are taken; no other section is reachable."
            ),
        )
    elif jurisdiction == "us-al":
        index = "https://www.alabamapublichealth.gov/wic/index.html"
        page = fetch(index)
        checks.append(page.record())
        for href, _label in links(page.text, index):
            if href.endswith("/wic/assets/2027-state-plan.pdf"):
                documents.append(
                    wic_document(
                        "us-al",
                        "al-wic-state-plan-2027",
                        "Alabama WIC 2027 State Plan of Program Operations",
                        href,
                        "us-al/policy/wic-state-plan/fy2027",
                        expression_date="2026-10-01",
                        source_authority="Alabama Department of Public Health, WIC Program",
                        publisher_page_url=index,
                        fiscal_year="2027",
                        plan_period="2026-10-01 to 2027-09-30",
                        plan_status="posted for public comment (public notice on the WIC home page)",
                        ocr=True,
                    )
                )
                break
        row.update(
            index_url=index,
            index_document_count=len(documents),
            notes=(
                "The Alabama WIC home page carries 'Public Notice - WIC State Plan of Operations' linking the full '2027 State "
                "Plan of Program Operations' PDF (489 pages: administrative documents, goals and objectives, functional area "
                "chapters I-XI). 22 pages are image-only (signatures, forms), so the scope extracts with ocr: true."
            ),
        )

    if not documents:
        row.update(status="blocked_primary_source", checks=checks, skipped=skipped)
        return row
    dump_manifest(manifest_path, WIC_VERSION, documents)
    row.update(
        status="taken",
        target_manifest=str(manifest_path.relative_to(ROOT)),
        target_scope=scope(jurisdiction, WIC_VERSION),
        document_count=len(documents),
        checks=checks,
        skipped=skipped,
    )
    return row


def wic_absent(jurisdiction: str) -> dict[str, Any]:
    return {
        "status": "not_published_or_not_inventoried",
        "notes": "FNA posts no WIC state plans (resource browser filtered to WIC returns none; /wic/state-plan paths answer 404). "
        "The closure report records this publisher's state plan family as REVIEW (WIC queue inventoried the manual family "
        "only) or OUTREACH (publisher blocked); not attempted in this pass.",
    }


# --------------------------------------------------------------------------- 272.2 plans of operation

PLAN_OF_OPERATION_NOTES = {
    "us-nm": "The HCA Income Support Division page's 'State Verification Plan' (new-mexico-verification-plan-template-final-nov-2018-pw.pdf, "
    "14 pages) is the MAGI-based Medicaid eligibility verification plan, not a SNAP 272.2 attachment; the closure report's "
    "EXTRACTABLE note is corrected here. The ISD Plans and Reports page lists E&T, Outreach, SNAP-Ed and D-SNAP plans, no plan of operation.",
    "us-wv": "bfa.wv.gov/bfa-policy-and-plans/state-plans lists SNAP E&T, SNAP Outreach, SNAP-Ed, D-SNAP, Summer EBT, TANF, LIHEAP, "
    "Refugee and CCDF plans; no 7 CFR 272.2 plan of operation.",
    "us-ar": "The SNAP Certification Manual says the plan of operation and its planning documents are available for public review at "
    "the Central Office on request; not posted.",
    "us-id": "IDAPA 16.03.04 rule 866 says state plans of operation are available for public examination; not posted.",
    "us-ms": "MDHS SNAP manual Rule 1.6 describes the annual state plan of operation (7 CFR 272.2); the plan itself is not posted.",
    "us-ok": "OAC 340:50 says State Plans of Operation are available upon request for inspection; not posted.",
}


def plan_of_operation_row(jurisdiction: str) -> dict[str, Any]:
    checks = PLAN_OF_OPERATION_CHECKS.get(jurisdiction, [])
    row: dict[str, Any] = {
        "status": "not_published",
        "fna_posts": False,
        "checks": checks,
        "notes": "FNA does not post 7 CFR 272.2 plans of operation. The publisher's SNAP index (state-snap-manual-agent-queue and "
        "snap-completion-agent-queue index URLs) was fetched 2026-09-13 and its links and text searched for 'plan of "
        "operation', '272.2' and 'state plan'; no plan of operation or option attachment is posted.",
    }
    if any(c.get("status") not in (200, None) for c in checks) and not any(
        c.get("status") == 200 for c in checks
    ):
        row["status"] = "publisher_blocked"
    if any(c.get("status") is None for c in checks) and not any(
        c.get("status") == 200 for c in checks
    ):
        row["status"] = "publisher_unreachable_tls"
    if jurisdiction in PLAN_OF_OPERATION_NOTES:
        row["notes"] += " " + PLAN_OF_OPERATION_NOTES[jurisdiction]
    return row


# --------------------------------------------------------------------------- queue


def load_queue() -> dict[str, Any]:
    if QUEUE.exists():
        return yaml.safe_load(QUEUE.read_text())
    return {
        "version": "2026-09-13",
        "document_family": "fns_state_plans",
        "programs": ["SNAP", "WIC"],
        "queue_status": "in_progress",
        "policy": {
            "canonical_pipeline": "source-first",
            "source_policy": "primary_official_only",
            "durable_artifacts": ["sources", "inventory", "provisions", "coverage"],
            "forbidden_sources": [
                "secondary summaries",
                "State Options Reports",
                "benefitswiki",
                "policy manuals reposted by non-government sites",
                "mirrors, proxies and archived copies of blocked publishers",
            ],
            "notes": [
                "Work order: docs/coverage/needs-closure-2026-09-11/snap.md elements snap_s31 (SNAP E&T State Plan) and snap_s32 "
                "(State Plan of Operation, 7 CFR 272.2) and wic.md element wic_s30 (WIC State Plan, 7 CFR 246.4).",
                f"Scopes: us-xx/policy/{ET_VERSION} (manifests/us-xx-snap-et-state-plan.yaml) and us-xx/policy/{WIC_VERSION} "
                "(manifests/us-xx-wic-state-plan.yaml), one document per posted plan file, page granularity like the Colorado "
                "E&T precedent us-co/policy/co-cdhs-snap-et-state-plan-ffy2026. Citation paths us-xx/policy/snap-et-state-plan/ffy2026 "
                "and us-xx/policy/wic-state-plan/<fy>/... collide with nothing in the corpus (checked against every provisions JSONL).",
                "FNA (fns.usda.gov / fna.usda.gov) posts SNAP E&T state plans at https://www.fna.usda.gov/snap-et/stateplan; it posts "
                "no WIC state plans and no 272.2 plans of operation. Generator: scripts/build_fns_state_plan_manifests.py. "
                f"Run note: {RUN_NOTE}.",
            ],
        },
        "states": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--only", help="comma-separated jurisdictions (us-xx); default every state and DC"
    )
    parser.add_argument("--family", choices=("et", "wic", "operation", "all"), default="all")
    args = parser.parse_args(argv)
    wanted = [j.strip() for j in args.only.split(",")] if args.only else list(STATES)
    for j in wanted:
        if j not in STATES:
            raise SystemExit(f"unknown jurisdiction {j}")

    queue = load_queue()
    rows = {r["jurisdiction"]: r for r in queue["states"]}
    index_page: Fetched | None = None
    listed: dict[str, str] = {}
    if args.family in ("et", "all"):
        index_page, listed = et_index()
        print(
            f"FNA index: {index_page.status} {len(index_page.content)} bytes, {len(listed)} state agencies listed"
        )

    for jurisdiction in wanted:
        row = rows.setdefault(
            jurisdiction, {"jurisdiction": jurisdiction, "name": STATES[jurisdiction]}
        )
        if args.family in ("et", "all") and index_page is not None:
            row["snap_et_state_plan"] = build_et(jurisdiction, listed, index_page)
            print(f"{jurisdiction} E&T: {row['snap_et_state_plan']['status']}")
        if args.family in ("wic", "all"):
            row["wic_state_plan"] = (
                build_wic(jurisdiction) if jurisdiction in WIC_STATES else wic_absent(jurisdiction)
            )
            print(
                f"{jurisdiction} WIC: {row['wic_state_plan']['status']} "
                f"({row['wic_state_plan'].get('document_count', 0)} documents)"
            )
        if args.family in ("operation", "all"):
            row["snap_plan_of_operation"] = plan_of_operation_row(jurisdiction)

    queue["states"] = [rows[j] for j in sorted(rows)]
    counts: dict[str, dict[str, int]] = {}
    for r in queue["states"]:
        for family in ("snap_et_state_plan", "wic_state_plan", "snap_plan_of_operation"):
            if family in r:
                counts.setdefault(family, {})
                status = r[family]["status"]
                counts[family][status] = counts[family].get(status, 0) + 1
    queue["status_counts"] = counts
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))

    # Cross-reference the WIC queue rows for the eight state-plan publishers.
    if args.family in ("wic", "all") and WIC_QUEUE.exists():
        wic_queue = yaml.safe_load(WIC_QUEUE.read_text())
        changed = False
        for r in wic_queue["states"]:
            j = r["jurisdiction"]
            if (
                j in wanted
                and j in WIC_STATES
                and rows[j].get("wic_state_plan", {}).get("status") == "taken"
            ):
                r["state_plan_scope"] = {
                    **rows[j]["wic_state_plan"]["target_scope"],
                    "manifest": rows[j]["wic_state_plan"]["target_manifest"],
                    "document_count": rows[j]["wic_state_plan"]["document_count"],
                    "queue": str(QUEUE.relative_to(ROOT)),
                    "run_note": RUN_NOTE,
                }
                changed = True
        if changed:
            WIC_QUEUE.write_text(
                yaml.safe_dump(wic_queue, sort_keys=False, allow_unicode=True, width=120)
            )
    print(f"queue {counts}")
    return 0


# Per-state 272.2 plan-of-operation probe of the SNAP publisher indexes (2026-09-13).
# One entry per index URL in state-snap-manual-agent-queue / snap-completion-agent-queue.
PLAN_OF_OPERATION_CHECKS: dict[str, list[dict[str, Any]]] = {
    "us-ak": [
        {
            "url": "http://dpaweb.hss.state.ak.us/manuals/fs/fsp.htm#t=title_page_alaska_fsp_manual.htm",
            "status": 200,
            "bytes": 33481,
            "seconds": 1.4,
            "client": "requests",
            "links": 7,
        },
    ],
    "us-al": [
        {
            "url": "https://apps.dhr.alabama.gov/POE/POEhome",
            "status": 200,
            "bytes": 7591,
            "seconds": 0.2,
            "client": "requests",
            "links": 20,
        },
    ],
    "us-ar": [
        {
            "url": "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/supplemental-nutrition-assistance-snap/",
            "status": 200,
            "bytes": 437405,
            "seconds": 0.3,
            "client": "curl_cffi:safari17_0",
            "links": 851,
        },
        {
            "url": "https://humanservices.arkansas.gov/wp-content/uploads/SNAP-Policy-Manual-04.02.2026.pdf",
            "status": 200,
            "bytes": 5056427,
            "seconds": 0.7,
            "client": "curl_cffi:safari17_0",
            "pdf_pages": 589,
            "plan_text_hits": 2,
        },
    ],
    "us-az": [
        {
            "url": "https://dbmefaapolicy.azdes.gov/FAA5.html",
            "status": 403,
            "bytes": 5824,
            "seconds": 0.1,
            "client": "curl_cffi:safari17_0",
            "links": 0,
        },
        {
            "url": "https://dbmefaapolicy.azdes.gov/#page/How_To_Use_This_Manual/Customer_Info.html",
            "status": 403,
            "bytes": 5776,
            "seconds": 0.1,
            "client": "curl_cffi:safari17_0",
            "links": 0,
        },
    ],
    "us-ca": [
        {
            "url": "https://www.cdss.ca.gov/inforesources/letters-regulations/legislation-and-regulations/calworks-calfresh-regulations/calfresh-regulations",
            "status": 200,
            "bytes": 28761,
            "seconds": 1.2,
            "client": "requests",
            "links": 44,
        },
        {
            "url": "https://www.cdss.ca.gov/inforesources/Rules-Regulations/Legislation-and-Regulations/CalWORKs-CalFresh-Regulations/CalFresh-Regulations",
            "status": 200,
            "bytes": 28761,
            "seconds": 1.8,
            "client": "requests",
            "links": 44,
        },
    ],
    "us-co": [
        {
            "url": "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2818",
            "status": 200,
            "bytes": 88282,
            "seconds": 0.6,
            "client": "requests",
            "links": 285,
        },
    ],
    "us-ct": [
        {
            "url": "https://portal.ct.gov/dss/snap/snap-policy-manual",
            "status": 200,
            "bytes": 59918,
            "seconds": 0.5,
            "client": "requests",
            "links": 69,
        },
    ],
    "us-dc": [
        {
            "url": "https://dhs.dc.gov/publication/esa-policy-manuals",
            "status": 200,
            "bytes": 168806,
            "seconds": 0.4,
            "client": "requests",
            "links": 59,
        },
    ],
    "us-de": [
        {
            "url": "https://regulations.delaware.gov/AdminCode/title16/9000",
            "status": 200,
            "bytes": 65540,
            "seconds": 0.2,
            "client": "requests",
            "links": 0,
        },
    ],
    "us-fl": [
        {
            "url": "https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual",
            "status": 200,
            "bytes": 31823,
            "seconds": 0.3,
            "client": "requests",
            "links": 91,
        },
    ],
    "us-ga": [
        {
            "url": "https://pamms.dhs.ga.gov/dfcs/snap/",
            "status": 200,
            "bytes": 171111,
            "seconds": 0.6,
            "client": "requests",
            "links": 1076,
        },
    ],
    "us-hi": [
        {
            "url": "https://humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/",
            "status": 200,
            "bytes": 97620,
            "seconds": 0.4,
            "client": "requests",
            "links": 192,
        },
    ],
    "us-ia": [
        {
            "url": "https://hhs.iowa.gov/media/4035/download?inline",
            "status": 200,
            "bytes": 101577,
            "seconds": 0.6,
            "client": "requests",
            "pdf_pages": 7,
        },
    ],
    "us-id": [
        {
            "url": "https://adminrules.idaho.gov/current-rules/",
            "status": 200,
            "bytes": 196769,
            "seconds": 1.4,
            "client": "requests",
            "links": 44,
        },
        {
            "url": "https://adminrules.idaho.gov/rules/current/16/160304.pdf",
            "status": 200,
            "bytes": 1246593,
            "seconds": 1.4,
            "client": "requests",
            "pdf_pages": 70,
            "plan_text_hits": 2,
        },
    ],
    "us-il": [
        {
            "url": "https://www.dhs.state.il.us/page.aspx?item=13473",
            "status": 200,
            "bytes": 10727,
            "seconds": 0.2,
            "client": "requests",
            "links": 58,
        },
    ],
    "us-in": [
        {
            "url": "https://www.in.gov/fssa/dfr/forms-documents-and-tools/policy-manual/",
            "status": 200,
            "bytes": 85550,
            "seconds": 0.4,
            "client": "requests",
            "links": 162,
        },
    ],
    "us-ks": [
        {
            "url": "https://content.dcf.ks.gov/EES/KEESM/Current/Home.htm",
            "status": 200,
            "bytes": 4446,
            "seconds": 0.4,
            "client": "requests",
            "links": 0,
        },
    ],
    "us-ky": [
        {
            "url": "https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx",
            "status": 200,
            "bytes": 58132,
            "seconds": 1.6,
            "client": "requests",
            "links": 79,
        },
    ],
    "us-la": [
        {
            "url": "https://public.powerdms.com/LADCFS/tree/documents/398463",
            "status": 200,
            "bytes": 2404,
            "seconds": 0.3,
            "client": "requests",
            "links": 0,
        },
    ],
    "us-ma": [
        {
            "url": "https://www.mass.gov/lists/department-of-transitional-assistance-regulations",
            "status": 200,
            "bytes": 209572,
            "seconds": 0.5,
            "client": "curl_cffi:safari17_0",
            "links": 94,
        },
    ],
    "us-md": [
        {
            "url": "https://dhs.maryland.gov/supplemental-nutrition-assistance-program/food-supplement-program-manual/",
            "status": 200,
            "bytes": 105282,
            "seconds": 0.8,
            "client": "requests",
            "links": 219,
        },
    ],
    "us-me": [
        {
            "url": "https://www.maine.gov/sos/rulemaking/agency-rules/department-health-and-human-services-rules",
            "status": 200,
            "bytes": 136019,
            "seconds": 0.1,
            "client": "requests",
            "links": 538,
        },
    ],
    "us-mi": [
        {
            "url": "https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/000.pdf",
            "status": 200,
            "bytes": 167226,
            "seconds": 0.3,
            "client": "requests",
            "pdf_pages": 6,
        },
    ],
    "us-mn": [
        {
            "url": "https://www.dhs.state.mn.us/main/groups/county_access/documents/pub/dhs-327301.pdf",
            "status": 200,
            "bytes": 6389130,
            "seconds": 7.1,
            "client": "requests",
            "pdf_pages": 1354,
            "plan_text_hits": 1,
        },
    ],
    "us-mo": [
        {
            "url": "https://dssmanuals.mo.gov/food-stamps/",
            "status": 200,
            "bytes": 46509,
            "seconds": 0.6,
            "client": "requests",
            "links": 34,
        },
    ],
    "us-ms": [
        {
            "url": "https://www.sos.ms.gov/adminsearch/ACCode/00000331c.pdf",
            "status": 200,
            "bytes": 1635091,
            "seconds": 0.8,
            "client": "curl_cffi:safari17_0",
            "pdf_pages": 168,
            "plan_text_hits": 10,
        },
    ],
    "us-mt": [
        {
            "url": "https://dphhs.mt.gov/hcsd/Manuals/snapmanual",
            "status": 200,
            "bytes": 72828,
            "seconds": 0.4,
            "client": "requests",
            "links": 322,
            "plan_text_hits": 1,
        },
    ],
    "us-nc": [
        {
            "url": "https://policies.ncdhhs.gov/divisional-n-z/social-services/food-and-nutrition-services/fns-policies-manuals/",
            "status": 200,
            "bytes": 333424,
            "seconds": 1.1,
            "client": "requests",
            "links": 583,
        },
    ],
    "us-nd": [
        {
            "url": "https://www.nd.gov/dhs/policymanuals/SNAP/Content/Home%202.htm",
            "status": 200,
            "bytes": 29054,
            "seconds": 0.3,
            "client": "requests",
            "links": 18,
        },
    ],
    "us-ne": [
        {
            "url": "https://rules.nebraska.gov/rules?agencyId=37&titleId=230",
            "status": None,
            "bytes": 0,
            "seconds": 0.2,
            "client": "curl_cffi:safari17_0",
            "links": 0,
            "error": "SSLError: certificate chain not verifiable with certifi",
        },
    ],
    "us-nh": [
        {
            "url": "https://www.dhhs.nh.gov/fsm_htm/newfsm.htm",
            "status": 200,
            "bytes": 5781,
            "seconds": 0.3,
            "client": "curl_cffi:safari17_0",
            "links": 1,
        },
        {
            "url": "https://gc.nh.gov/rules/state_agencies/he-w700.html",
            "status": 200,
            "bytes": 569579,
            "seconds": 0.4,
            "client": "requests",
            "links": 70,
        },
    ],
    "us-nj": [
        {
            "url": "https://www.nj.gov/humanservices/notices/rules-and-fees/rules-and-regulations/",
            "status": 200,
            "bytes": 74542,
            "seconds": 0.1,
            "client": "requests",
            "links": 231,
            "plan_text_hits": 1,
        },
    ],
    "us-nm": [
        {
            "url": "https://www.hca.nm.gov/lookingforinformation/income-support-division-1/",
            "status": 200,
            "bytes": 246816,
            "seconds": 1.8,
            "client": "requests",
            "links": 251,
            "plan_text_hits": 4,
        },
    ],
    "us-nv": [
        {
            "url": "https://dwss.nv.gov/Home/Features/eligibility/eligibility-n-payment-info-manual/",
            "status": 200,
            "bytes": 90997,
            "seconds": 1.3,
            "client": "requests",
            "links": 185,
            "plan_text_hits": 1,
        },
    ],
    "us-ny": [
        {
            "url": "https://otda.ny.gov/programs/snap/",
            "status": 200,
            "bytes": 6620,
            "seconds": 0.2,
            "client": "curl_cffi:safari17_0",
            "links": 0,
        },
        {
            "url": "https://otda.ny.gov/programs/snap/SNAPSB.pdf",
            "status": 200,
            "bytes": 6620,
            "seconds": 0.1,
            "client": "requests",
            "links": 0,
        },
    ],
    "us-oh": [
        {
            "url": "https://codes.ohio.gov/ohio-administrative-code/5101%3A4",
            "status": 200,
            "bytes": 14653,
            "seconds": 0.7,
            "client": "requests",
            "links": 29,
        },
    ],
    "us-ok": [
        {
            "url": "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=340&chapterNum=50",
            "status": 200,
            "bytes": 730010,
            "seconds": 2.0,
            "client": "requests",
            "links": 0,
            "plan_text_hits": 3,
        },
        {
            "url": "https://rules.ok.gov/home",
            "status": 200,
            "bytes": 1551,
            "seconds": 0.5,
            "client": "curl_cffi:safari17_0",
            "links": 0,
        },
    ],
    "us-or": [
        {
            "url": "https://sharedsystems.dhsoha.state.or.us/DHSForms/Served/de2818.pdf",
            "status": None,
            "bytes": 0,
            "seconds": 0.5,
            "client": "curl_cffi:safari17_0",
            "links": 0,
            "error": "SSLError: certificate chain not verifiable with certifi",
        },
    ],
    "us-pa": [
        {
            "url": "http://services.dpw.state.pa.us/oimpolicymanuals/snap/index.htm#t=SNAP_Handbook_Title_Page.htm",
            "status": 200,
            "bytes": 33577,
            "seconds": 0.3,
            "client": "requests",
            "links": 7,
        },
    ],
    "us-ri": [
        {
            "url": "https://rules.sos.ri.gov/regulations/part/218-20-00-1",
            "status": 200,
            "bytes": 1124513,
            "seconds": 0.4,
            "client": "requests",
            "links": 62,
            "plan_text_hits": 2,
        },
    ],
    "us-sc": [
        {
            "url": "https://dss.sc.gov/about/data-and-resources/manuals/",
            "status": 200,
            "bytes": 76706,
            "seconds": 0.2,
            "client": "requests",
            "links": 469,
        },
    ],
    "us-sd": [
        {
            "url": "https://dss.sd.gov/docs/economicassistance/snap/snapmanual.pdf",
            "status": 200,
            "bytes": 2773728,
            "seconds": 13.7,
            "client": "requests",
            "pdf_pages": 339,
        },
    ],
    "us-tn": [
        {
            "url": "https://www.tn.gov/humanservices/information-and-resources/dhs-publications.html",
            "status": 200,
            "bytes": 94260,
            "seconds": 0.3,
            "client": "requests",
            "links": 255,
        },
    ],
    "us-tx": [
        {
            "url": "https://fhb.hhs.texas.gov/handbooks/texas-works-handbook",
            "status": 200,
            "bytes": 30202,
            "seconds": 0.9,
            "client": "requests",
            "links": 55,
        },
        {
            "url": "https://www.hhs.texas.gov/handbooks/texas-works-handbook",
            "status": 200,
            "bytes": 30202,
            "seconds": 0.3,
            "client": "curl_cffi:safari17_0",
            "links": 55,
        },
    ],
    "us-ut": [
        {
            "url": "https://jobs.utah.gov/infosource/eligibilitymanual/eligibility_manual.htm",
            "status": 200,
            "bytes": 33544,
            "seconds": 1.0,
            "client": "requests",
            "links": 7,
        },
    ],
    "us-va": [
        {
            "url": "https://www.dss.virginia.gov/relief/food-assistance/snap/snap-policy--procedures/snap-manual/",
            "status": 200,
            "bytes": 46411,
            "seconds": 0.2,
            "client": "requests",
            "links": 134,
        },
    ],
    "us-vt": [
        {
            "url": "https://www.ahsnet.ahs.state.vt.us/Public/3sVT/whxdata/toc.new.js",
            "status": 200,
            "bytes": 2863,
            "seconds": 0.3,
            "client": "requests",
            "links": 0,
        },
        {
            "url": "https://www.ahsnet.ahs.state.vt.us/Public/3sVT/assets/BRM/100GenInfo.htm",
            "status": 200,
            "bytes": 23918,
            "seconds": 0.2,
            "client": "requests",
            "links": 26,
        },
    ],
    "us-wa": [
        {
            "url": "https://www.dshs.wa.gov/esa/manuals/eaz",
            "status": 200,
            "bytes": 88777,
            "seconds": 0.9,
            "client": "requests",
            "links": 292,
        },
    ],
    "us-wi": [
        {
            "url": "https://www.emhandbooks.wisconsin.gov/fsh/fsh.htm#t=home.htm",
            "status": 200,
            "bytes": 31704,
            "seconds": 0.3,
            "client": "requests",
            "links": 6,
        },
    ],
    "us-wv": [
        {
            "url": "https://bfa.wv.gov/income-maintenance-manual",
            "status": 200,
            "bytes": 42526,
            "seconds": 0.1,
            "client": "requests",
            "links": 63,
            "plan_text_hits": 1,
        },
    ],
    "us-wy": [
        {
            "url": "https://dfs.wyo.gov/about/policy-manuals/snap-and-power-policy-manual/",
            "status": 200,
            "bytes": 946427,
            "seconds": 1.6,
            "client": "requests",
            "links": 136,
            "plan_text_hits": 2,
        },
    ],
}


if __name__ == "__main__":
    raise SystemExit(main())
