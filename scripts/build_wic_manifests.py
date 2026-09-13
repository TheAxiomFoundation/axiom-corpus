"""Build the WIC corpus manifests from the publishers' own index pages and update
the WIC agent queue.

Federal (USDA Food and Nutrition Service, renamed Food and Nutrition Administration
on 2026-06-01): the WIC policy-memorandum index is the FNA resource browser filtered
to WIC + Policy Memos, https://www.fna.usda.gov/resources?f[0]=program:32&f[1]=resource_type:160.
The www.fns.usda.gov / www.fna.usda.gov front door (Akamai) answers 403 "Access Denied"
to every client we have (plain, browser UA, curl_cffi impersonation, the Claude fetch
proxy, and a real browser on this machine), so the index and memo pages are read from
the publisher's own origin host fns-prod.azureedge.us (the same Drupal site; the
existing manifests/us-snap-guidance.yaml already downloads FNS files from that host).
Memo pages carry no text of their own: each embeds its PDF from the USDA guidance
portal (www.usda.gov/sites/default/files/guidance-documents/...), which serves PDFs
only to browser-impersonated clients; the extractor's existing
``request: browser_impersonation`` option handles that. The Income Eligibility
Guidelines notices are taken from govinfo.gov (Federal Register), which the FNA memo
#2026-5 / #2025-4 pages cite.

States (first batch: the ten largest by population): one manifest per state built from
the state WIC agency's own manual index page; one document per policy/chapter PDF.

TLS: www.cdph.ca.gov (California) presents a chain that certifi cannot complete
(issuer Sectigo Public Server Authentication CA OV R36) and www.dhs.state.il.us
(Illinois) omits its Entrust OV TLS Issuing RSA CA 2 intermediate. Both public
intermediates were fetched from the leaf certificates' AIA URLs into data/certs/ and
are appended to certifi in data/certs/wic-state-ca-bundle.pem. Run extraction with
REQUESTS_CA_BUNDLE pointing at that bundle. No verification is disabled.

Second batch (the next ten states by population: NJ, VA, WA, AZ, TN, MA, IN, MD, MO, WI):
VA, WA and MD publish chapter/policy PDF indexes and are built here; NJ publishes only the
vendor-management functional area of its WIC Services Policy and Procedure Manual, which is
taken as a flagged partial; AZ (Cloudflare 403 to every client), TN (tn.gov 403/timeout to
every client), MO (manual behind the local-agency portal login), MA, IN and WI (manual not
published) are blocked_primary_source with the exact failure. Batch-1 blocked rows (NY, FL,
IL, OH) carry a re-check stamp.

Third batch (the next ten states by population: CO, MN, SC, AL, LA, KY, OR, OK, CT, UT, with replacements
IA, NV, AR, MS, KS, NM for states whose publisher blocked the first probe or does not publish the manual): CO
(policies on the agency's Google Drive, linked from coloradowic.gov; handled by the extractor's existing
google_drive_download_url), MN, CT, UT and IA are built here. SC, LA, KY, AR, KS (403 on the first probe), OR
(www.oregon.gov SERVFAIL at every resolver), AL, OK, MS, NM (manual not published) and NV (manual page
password-protected) are blocked_primary_source with the exact failure.

Fourth batch (retry from a US network, 2026-09-10T21:34Z): every blocked row was re-probed once. OR (www.oregon.gov
resolves again; the wicpolicy.aspx index lists 88 policies) and KY (www.chfs.ky.gov answers; the WIC page's 'WIC and
Nutrition Manual' heading lists ten policy-group PDFs) are built here. AZ, TN, SC, LA and KS now answer but publish no
manual index (details in BLOCKED); AR and MA still answer 403; IL does not resolve; the not-published rows are unchanged
(RETRIED stamps). The same batch then attempted the next ten not-yet-attempted states by population (NE, WV, ID, HI, NH,
ME, MT, RI, DE, SD): WV (eleven chapter pages, one PDF per policy), ME (one PDF per series-coded policy) and RI (the
compiled Procedures Manual and the Vendor Policies PDFs on the program page) are built here; NE, ID, HI, SD publish no
manual, MT publishes its policies only as the State Plan, and NH and DE answer 403 to the plain client.

Fifth batch (the last five jurisdictions without a queue row: AK, DC, ND, VT, WY; first probes 2026-09-10T22:58Z from a US
network): DC is built here from dcwic.org, the DC Health WIC State Agency's program site (linked from dchealth.dc.gov's
WIC service page), whose public 'Policies, Forms, & Tools' page lists one PDF per numbered policy in ten chapter
dropdowns. AK, ND, VT and WY publish no policy manual on their agency sites (VT posts its State Plan and a Grocer
Handbook, WY a vendor manual as a Google Doc). The AZ and DE access blocks from batch 4 were re-checked once (RETRIED).

    uv run python scripts/build_wic_manifests.py                      # everything
    uv run python scripts/build_wic_manifests.py --only us-va,us-wa   # selected rows only
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import time
from pathlib import Path
from urllib.parse import quote, urljoin

import certifi
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = dt.date.today().isoformat()
FEDERAL_VERSION = "2026-09-10-wic-fns-guidance"
STATE_VERSION = "2026-09-10-wic-state-policy-manual"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
FNA_ORIGIN = "https://fns-prod.azureedge.us"
FNA_CANONICAL = "https://www.fna.usda.gov"
FNA_MEMO_INDEX = "/resources?f%5B0%5D=program%3A32&f%5B1%5D=resource_type%3A160"
FNA_GUIDANCE_INDEX = "/resources?f%5B0%5D=program%3A32&f%5B1%5D=resource_type%3A401"
FNA_FR_INDEX = "/resources?f%5B0%5D=program%3A32&f%5B1%5D=resource_type%3A16"
IMPERSONATE = {"browser_impersonation": True, "browser_impersonation_direct": True}
# wic.health.pa.gov stalls urllib3 keep-alive downloads mid-body; the extractor's curl
# range backend exists for exactly that case.
CURL_RANGES = {"range_fetch": True, "range_backend": "curl"}
SINGLE_BLOCK = {"segmentation": "single_block"}

CERTS = ROOT / "data" / "certs"
INTERMEDIATES = (
    CERTS / "sectigo-public-server-authentication-ca-ov-r36.pem",
    CERTS / "entrust-ov-tls-issuing-rsa-ca-2.pem",
)


def ca_bundle() -> Path:
    out = CERTS / "wic-state-ca-bundle.pem"
    out.write_text(
        Path(certifi.where()).read_text()
        + "".join("\n" + p.read_text() for p in INTERMEDIATES)
    )
    return out


def get(url: str, *, verify: str | bool = True, impersonate: bool = False) -> bytes:
    if impersonate:
        from curl_cffi import requests as curl_requests

        resp = curl_requests.get(url, headers=UA, timeout=90, impersonate="chrome120")
        resp.raise_for_status()
        return resp.content
    for attempt in range(1, 4):  # wic.health.pa.gov intermittently stalls mid-response
        try:
            # keep-alive responses from wic.health.pa.gov stall mid-body (Connection: close does not);
            # compressed responses from fns-prod.azureedge.us are cached without the query string,
            # so the facet filter is only honored for identity encoding.
            headers = {**UA, "Connection": "close", "Accept-Encoding": "identity"}
            resp = requests.get(url, headers=headers, timeout=90, verify=verify)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError(url)


def soup_of(content: bytes) -> BeautifulSoup:
    return BeautifulSoup(content, "html.parser")


def write_manifest(stem: str, documents: list[dict], version: str) -> str:
    path = ROOT / "manifests" / f"{stem}.yaml"
    path.write_text(
        yaml.safe_dump({"version": version, "documents": documents}, sort_keys=False, allow_unicode=True, width=120)
    )
    return f"manifests/{stem}.yaml"


# --------------------------------------------------------------------------- federal

# FY 2025 and FY 2026 WIC policy memoranda confirmed on the FNA index / memo pages.
# The Azure origin host ignores the listing's ``page`` parameter, so only the first
# listing page (the ten newest resources, which cover calendar 2025-2026 exactly per the
# index's own year facet) is enumerable; #2025-1 and #2025-2 (dated December 2024) were
# located by their FNA page slugs and confirmed on those pages. Memo numbers and dates
# were read from each PDF's header.
FEDERAL_MEMOS = [
    # slug, memo number, memo date, title
    ("wic/clarification-corporate-changes-ownership", "2025-1", "2024-12-06",
     "WIC Policy Memorandum #2025-1: Clarification on Corporate Changes of Ownership"),
    ("wic/cancellation-exit-counseling-brochure", "2025-2", "2024-12-20",
     "WIC Policy Memorandum #2025-2: Cancellation of WIC Policy Memorandum #1994-9 WIC Exit Counseling Brochure"),
    ("wic/banked-human-breastmilk", "2025-3", "2025-01-10",
     "WIC Policy Memorandum #2025-3: Policy Memorandum Revision: Use of Banked Human Breast Milk in WIC"),
    ("wic/income-eligibility-guidelines-2025-26", "2025-4", "2025-03-27",
     "WIC Policy Memorandum #2025-4: Publication of the 2025-2026 WIC Income Eligibility Guidelines"),
    ("wic/revised-food-packages-flexibilities", "2025-5", "2025-08-19",
     "WIC Policy Memorandum #2025-5: Implementing Revisions to the WIC Food Packages: Flexibilities to Support Healthy Choices, Healthy Outcomes, and Healthy Families"),
    ("wic/agency/increase-mma-fluidmilk", "2026-1", "2025-12-05",
     "WIC Policy Memorandum #2026-1: Implementation of P.L. 119-37, Temporary Increase to the Maximum Monthly Allowance of Fluid Milk"),
    ("wic/agency/cvvb-fy26", "2026-2", "2025-12-10",
     "WIC Policy Memorandum #2026-2: Fiscal Year 2026 Cash-Value Voucher/Benefit Amounts"),
    ("wic/agency/dgas-eat-real-food", "2026-4", "2026-03-30",
     "WIC Policy Memorandum #2026-4: Dietary Guidelines for Americans, 2025-2030 - Eat Real Food"),
    ("wic/agency/ieg-2026-27", "2026-5", "2026-04-29",
     "WIC Policy Memorandum #2026-5: Publication of 2026-2027 WIC Income Eligibility Guidelines"),
]

FEDERAL_IEG_NOTICES = [
    # period, FR citation, document number, publication date, effective date
    ("2026-2027", "91 FR 23050", "2026-08323", "2026-04-29", "2026-07-01"),
    ("2025-2026", "90 FR 11598", "2025-03576", "2025-03-10", "2025-07-01"),
]


def memo_pdf_url(slug: str) -> str:
    page = soup_of(get(f"{FNA_ORIGIN}/{slug}"))
    frames = [f["src"] for f in page.find_all("iframe", src=True) if "guidance-documents" in f["src"]]
    if len(frames) != 1:
        raise RuntimeError(f"memo page {slug} does not embed exactly one guidance-portal PDF: {frames}")
    return frames[0]


def federal_index_inventory() -> dict:
    """Return the index's own counts (rows on the first listing page and year facets)."""
    page = soup_of(get(FNA_ORIGIN + FNA_MEMO_INDEX))
    rows = []
    active = [a.get_text(" ", strip=True) for a in page.find_all("a") if a.get_text(" ", strip=True).startswith("(-)")]
    if not any("WIC" in t for t in active) or not any("Policy Memos" in t for t in active):
        raise RuntimeError(f"FNA listing did not apply the WIC / Policy Memos facets: {active}")
    for row in page.select(".views-row"):
        a = row.find("a", href=True)
        d = row.select_one(".listing__date")
        rows.append({"date": d.get_text(strip=True) if d else None, "title": a.get_text(" ", strip=True), "href": a["href"]})
    facets = {}
    for a in page.find_all("a", href=True):
        m = re.match(r"^(\d{4}) \((\d+)\)$", a.get_text(" ", strip=True))
        if m:
            facets[m.group(1)] = int(m.group(2))
        m = re.match(r"^\(-\) Policy Memos \((\d+)\)$", a.get_text(" ", strip=True))
        if m:
            facets["total"] = int(m.group(1))
    return {"first_page_rows": rows, "year_facets": facets}


def build_federal() -> tuple[str, int, dict]:
    inventory = federal_index_inventory()
    docs = []
    for period, citation, number, published, effective in FEDERAL_IEG_NOTICES:
        docs.append({
            "source_id": f"us-fns-wic-income-eligibility-guidelines-{period}",
            "jurisdiction": "us",
            "document_class": "guidance",
            "title": f"WIC: {period.replace('-', '/')} Income Eligibility Guidelines ({citation})",
            "source_url": f"https://www.govinfo.gov/content/pkg/FR-{published}/html/{number}.htm",
            "source_format": "html",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": published,
            "citation_path": f"us/guidance/fns/wic/income-eligibility-guidelines/{period}",
            "metadata": {
                "primary_source": True,
                "source_authority": "USDA Food and Nutrition Service (Food and Nutrition Administration since 2026-06-01) via U.S. Government Publishing Office",
                "document_subtype": "federal_register_notice",
                "program": "WIC",
                "federal_register_citation": citation,
                "federal_register_document_number": number,
                "federal_register_publication_date": published,
                "federal_register_pdf_url": f"https://www.govinfo.gov/content/pkg/FR-{published}/pdf/{number}.pdf",
                "effective_start": effective,
                "effective_end": f"{int(effective[:4]) + 1}-06-30",
                "source_discovery_group": "us/guidance/fns/wic",
                "discovered_via": "manual-review:wic-agent-queue; FNA WIC agency page 'View guidelines' link and policy memo transmitting the notice",
            },
        })
    for slug, number, memo_date, title in FEDERAL_MEMOS:
        pdf = memo_pdf_url(slug)
        fy = number.split("-")[0]
        docs.append({
            "source_id": f"us-fns-wic-policy-memo-{number}",
            "jurisdiction": "us",
            "document_class": "guidance",
            "title": title,
            "source_url": f"{FNA_CANONICAL}/{slug}",
            "download_url": pdf,
            "source_format": "pdf",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": memo_date,
            "citation_path": f"us/guidance/fns/wic/policy-memo/{number}",
            "request": dict(IMPERSONATE),
            "extraction": dict(SINGLE_BLOCK),
            "metadata": {
                "primary_source": True,
                "source_authority": "USDA Food and Nutrition Service (Food and Nutrition Administration since 2026-06-01)",
                "document_subtype": "policy_memorandum",
                "program": "WIC",
                "memo_number": number,
                "memo_date": memo_date,
                "fiscal_year": fy,
                "index_url": FNA_CANONICAL + FNA_MEMO_INDEX.replace("%5B", "[").replace("%5D", "]").replace("%3A", ":"),
                "source_discovery_group": "us/guidance/fns/wic",
                "discovered_via": "manual-review:wic-agent-queue; FNA resource browser WIC/Policy Memos",
                "access_note": (
                    "www.fna.usda.gov / www.fns.usda.gov answer HTTP 403 to every client; the memo page was read from the "
                    "publisher's origin host fns-prod.azureedge.us and carries only an embedded PDF from the USDA guidance "
                    "portal, which is downloaded with browser impersonation."
                ),
            },
        })
    return write_manifest("us-wic-fns-guidance", docs, FEDERAL_VERSION), len(docs), inventory


# --------------------------------------------------------------------------- states

def state_doc(jur: str, agency: str, label: str, title: str, url: str, *, authority: str, index_url: str,
              manual: str, request: dict | None = None, extra: dict | None = None) -> dict:
    doc = {
        "source_id": f"{jur}-wic-manual-{label.lower()}",
        "jurisdiction": jur,
        "document_class": "manual",
        "title": title,
        "source_url": url,
        "source_format": "pdf",
        "source_as_of": SOURCE_AS_OF,
        "citation_path": f"{jur}/manual/{agency}/wic/{label.lower()}",
        "extraction": dict(SINGLE_BLOCK),
        "metadata": {
            "primary_source": True,
            "source_authority": authority,
            "document_subtype": "state_policy_manual_section",
            "program": "WIC",
            "manual": manual,
            "section_label": label,
            "index_url": index_url,
            "source_discovery_group": f"{jur}/manual/wic",
            "discovered_via": "manual-review:wic-agent-queue; state WIC agency manual index page",
            **(extra or {}),
        },
    }
    if request:
        doc["request"] = dict(request)
    return doc


def build_ca(bundle: Path) -> tuple[str, int, dict]:
    index = "https://www.cdph.ca.gov/Programs/CFH/DWICSN/Pages/LocalAgencies/PoliciesandPolicyResources/WPPM.aspx"
    page = soup_of(get(index, verify=str(bundle)))
    docs, seen, families = [], {}, {"wppm_policy_pdf": 0, "other_link": 0}
    for a in page.find_all("a", href=True):
        text = a.get_text(" ", strip=True).replace("​", "")
        m = re.match(r"^\s*(\d{3,4}-\d{2,4})\s+(.*?)\s*(\(PDF\))?\s*$", text)
        if not (m and "/WPPM/" in a["href"]):
            if a["href"].lower().endswith(".pdf"):
                families["other_link"] += 1
            continue
        families["wppm_policy_pdf"] += 1
        label, title = m.group(1), m.group(2)
        if title.lower().endswith("- spanish"):
            label = f"{label}-es"
        if label in seen:  # the index links two files under one policy number
            seen[label] += 1
            label = f"{label}-{seen[label]}"
        else:
            seen[label] = 1
        docs.append(state_doc(
            "us-ca", "cdph", label, f"California WIC Policy and Procedures Manual WPPM #{m.group(1)}: {title}",
            urljoin(index, a["href"]), authority="California Department of Public Health, WIC Division",
            index_url=index, manual="WIC Policy and Procedures Manual (WPPM)",
            extra={"tls_note": "extraction uses REQUESTS_CA_BUNDLE = certifi + data/certs/sectigo-public-server-authentication-ca-ov-r36.pem"},
        ))
    if len(docs) < 100:
        raise RuntimeError(f"CA index yielded only {len(docs)} policies")
    return write_manifest("us-ca-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_tx() -> tuple[str, int, dict]:
    index = "https://www.hhs.texas.gov/providers/wic-providers/wic-policy-procedures-manual"
    page = soup_of(get(index, impersonate=True))
    main = page.select_one("main") or page
    docs, families = [], {"policy_pdf": 0, "policy_pdf_working_draft": 0, "complete_manual_pdf": 0}
    for a in main.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if not a["href"].lower().endswith(".pdf"):
            continue
        if "policy-manual.pdf" in a["href"]:
            families["complete_manual_pdf"] += 1
            continue
        m = re.match(r"^([A-Z]{2,3}):(\d{2}\.\d)\s*(\(T\))?\s*(.*)$", text)
        if not m:
            continue
        draft = bool(m.group(3))
        families["policy_pdf_working_draft" if draft else "policy_pdf"] += 1
        label = f"{m.group(1)}-{m.group(2)}" + ("t" if draft else "")
        docs.append(state_doc(
            "us-tx", "hhsc", label, f"Texas WIC Policy and Procedures Manual {m.group(1)}:{m.group(2)}{' (T)' if draft else ''} {m.group(4)}",
            urljoin(index, a["href"]), authority="Texas Health and Human Services Commission, WIC",
            index_url=index, manual="Texas WIC Policy and Procedures Manual", request=IMPERSONATE,
            extra={"working_draft": draft, "access_note": "hhs.texas.gov answers 403 to non-browser clients; fetched with browser impersonation"},
        ))
    if len(docs) < 100:
        raise RuntimeError(f"TX index yielded only {len(docs)} policies")
    return write_manifest("us-tx-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_ga() -> tuple[str, int, dict]:
    index = "https://dph.georgia.gov/WIC/wic-policy-and-procedures-manual"
    page = soup_of(get(index))
    main = page.select_one("main") or page
    docs, families = [], {"policy_pdf": 0, "section_outline_pdf": 0, "combined_section_pdf": 0}
    for a in main.find_all("a", href=True):
        text = a.get_text(" ", strip=True).replace("\xa0", " ")
        m = re.match(r"^([A-Z]{2,3})-\s?(\d{3,4}\.\d{2})\s*(.*)$", text)
        if not m:
            if re.match(r"^[A-Z]{2,3}-\s?Outline$", text):
                families["section_outline_pdf"] += 1
            elif "Policies Combined" in text:
                families["combined_section_pdf"] += 1
            continue
        label = f"{m.group(1)}-{m.group(2)}"
        # eleven index entries point at document pages or media ids the publisher no longer serves
        # (HTTP 404, one 403); probe each link and record those instead of taking them
        probe = requests.get(urljoin(index, a["href"]), headers=UA, timeout=60, stream=True)
        head = next(probe.iter_content(8), b"")
        probe.close()
        if probe.status_code != 200 or head[:4] != b"%PDF":
            families[f"policy_link_{probe.status_code}_on_publisher"] = families.get(
                f"policy_link_{probe.status_code}_on_publisher", []
            ) + [label]
            continue
        families["policy_pdf"] += 1
        docs.append(state_doc(
            "us-ga", "dph", label, f"Georgia WIC Policy and Procedures Manual {label}: {m.group(3)}".rstrip(": "),
            urljoin(index, a["href"]), authority="Georgia Department of Public Health, WIC Program",
            index_url=index, manual="Georgia WIC Policy and Procedures Manual",
        ))
    if len(docs) < 100:
        raise RuntimeError(f"GA index yielded only {len(docs)} policies")
    return write_manifest("us-ga-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_mi() -> tuple[str, int, dict]:
    index = "https://www.michigan.gov/mdhhs/assistance-programs/wic/wic-staff/wicpolicymanual/mi-wic-policy-manual-table-of-contents"
    page = soup_of(get(index, impersonate=True))
    main = page.select_one("main") or page
    docs, families = [], {"numbered_policy_or_exhibit_pdf": 0, "unnumbered_attachment_pdf": 0, "policy_index_pdf": 0}
    for li in main.find_all("li"):
        a = li.find("a", href=re.compile(r"\.pdf", re.I))
        if not a or a.find_parent("li") is not li:
            continue
        own = li.get_text(" ", strip=True)
        text = a.get_text(" ", strip=True)
        if "Policy Index" in text:
            families["policy_index_pdf"] += 1
            continue
        m = re.match(r"^(\d+\.\d+[A-Z]?)\b", own)
        if not m:
            families["unnumbered_attachment_pdf"] += 1
            continue
        families["numbered_policy_or_exhibit_pdf"] += 1
        label = m.group(1)
        docs.append(state_doc(
            "us-mi", "mdhhs", label, f"MI-WIC Policy Manual {label}: {text}",
            urljoin(index, a["href"]), authority="Michigan Department of Health and Human Services, WIC Division",
            index_url=index, manual="MI-WIC Policy Manual", request=IMPERSONATE,
            extra={"access_note": "michigan.gov answers 403 to non-browser clients; fetched with browser impersonation"},
        ))
    if len(docs) < 80:
        raise RuntimeError(f"MI index yielded only {len(docs)} policies")
    return write_manifest("us-mi-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_pa() -> tuple[str, int, dict]:
    index = "https://wic.health.pa.gov/pawic/PoliciesAndProcedures.aspx"
    page = soup_of(get(index))
    docs, families = [], {"policy_pdf": 0, "policy_index_pdf": 0, "other_pdf": 0}
    for a in page.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if not a["href"].lower().endswith(".pdf"):
            continue
        if "PoliciesAndProcedures/" not in a["href"]:
            families["other_pdf"] += 1
            continue
        m = re.match(r"^(\d\.\d\d)\s+(.*)$", text)
        if not m:
            families["policy_index_pdf"] += 1
            continue
        families["policy_pdf"] += 1
        docs.append(state_doc(
            "us-pa", "doh", m.group(1), f"Pennsylvania WIC Policy and Procedure Manual {m.group(1)}: {m.group(2)}",
            urljoin(index, quote(a["href"], safe="/:%")),  # hrefs contain literal spaces; curl rejects them
            authority="Pennsylvania Department of Health, Bureau of Women, Infants and Children",
            index_url=index, manual="Pennsylvania WIC Policy and Procedure Manual", request=CURL_RANGES,
            extra={"access_note": "wic.health.pa.gov stalls urllib3 keep-alive downloads mid-body; fetched with the curl range backend"},
        ))
    if len(docs) < 40:
        raise RuntimeError(f"PA index yielded only {len(docs)} policies")
    return write_manifest("us-pa-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_nc() -> tuple[str, int, dict]:
    index = "https://www.ncdhhs.gov/divisions/child-and-family-well-being/community-nutrition-services-section/wic/staff/wic-local-agency-resources"
    page = soup_of(get(index))
    docs, families = [], {"chapter_pdf": 0, "complete_manual_pdf": 0}
    for a in page.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if "complete-nc-wic-program-manual" in a["href"]:
            families["complete_manual_pdf"] += 1
            continue
        m = re.match(r"^Chapter (\d+[A-Z]?):\s*(.*)$", text)
        if not m:
            continue
        families["chapter_pdf"] += 1
        label = f"chapter-{m.group(1).lower()}"
        docs.append(state_doc(
            "us-nc", "ncdhhs", label, f"North Carolina WIC Program Manual Chapter {m.group(1)}: {m.group(2)}",
            urljoin(index, a["href"]), authority="North Carolina Department of Health and Human Services, Community Nutrition Services Section",
            index_url=index, manual="North Carolina WIC Program Manual",
        ))
    if len(docs) < 20:
        raise RuntimeError(f"NC index yielded only {len(docs)} chapters")
    return write_manifest("us-nc-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def pdf_header_policy_code(content: bytes) -> str | None:
    """Virginia policies print their number on page one, e.g. ``Policy: CRT 05.2``."""
    import fitz

    with fitz.open(stream=content, filetype="pdf") as document:
        text = " ".join(document[0].get_text().split()) if len(document) else ""
    m = re.search(r"Policy:\s*([A-Z][A-Za-z]{1,3})\s+(\d{2}\.\d+(?:\.\d+)?)", text)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def build_va() -> tuple[str, int, dict]:
    """Virginia: one PDF per policy under roman-numbered functional areas I-VIII and XII; IX forms, X appendices,
    XI glossary are inventoried, not taken. Labels come from the policy number printed on page one (several
    newer files are named by title only), falling back to the code in the filename."""
    index = "https://www.vdh.virginia.gov/wic/wic-policy-and-procedures-manual/"
    page = soup_of(get(index))
    main = page.select_one("main") or page
    docs, labels = [], {}
    families = {"policy_pdf": 0, "overview_pdf": 0, "toc_pdf": 0, "form_pdf": 0, "appendix_pdf": 0, "glossary_pdf": 0,
                "duplicate_link_same_file": 0}
    section = None
    seen_urls: set[str] = set()
    for el in main.find_all(["h3", "h4", "a"]):
        if el.name != "a":
            m = re.match(r"^([IVX]+)\.", el.get_text(" ", strip=True))
            section = m.group(1) if m else None
            continue
        href = el.get("href", "")
        if not href.lower().endswith(".pdf"):
            continue
        url = urljoin(index, href)
        fname = href.rsplit("/", 1)[-1]
        text = " ".join(el.get_text(" ", strip=True).split())
        if "Table-of-Content" in fname:
            families["toc_pdf"] += 1
            continue
        if section == "IX" or (section == "XII" and "form" in fname.lower()):
            families["form_pdf"] += 1
            continue
        if section == "X":
            families["appendix_pdf"] += 1
            continue
        if section == "XI":
            families["glossary_pdf"] += 1
            continue
        if url in seen_urls:  # FDS-02.2.4 is linked twice under two titles
            families["duplicate_link_same_file"] += 1
            continue
        seen_urls.add(url)
        probe = requests.get(url, headers=UA, timeout=90)
        if probe.status_code != 200 or probe.content[:4] != b"%PDF":
            key = f"policy_link_{probe.status_code}_on_publisher"
            families[key] = families.get(key, []) + [text]
            continue
        fm = re.match(r"^([A-Z][A-Za-z]{1,3})-?(\d{1,2}\.\d+(?:\.\d+)?)", fname)
        filename_code = f"{fm.group(1)}-{fm.group(2)}" if fm else None
        if fname.startswith("Overview"):
            code, display = "overview", "Overview"
            families["overview_pdf"] += 1
        else:
            code = pdf_header_policy_code(probe.content) or filename_code
            if code is None and section == "XII":  # the Remote WIC Services policy prints no policy number
                code = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
                families["policy_pdf_labeled_by_title"] = families.get("policy_pdf_labeled_by_title", []) + [f"{text} -> {code}"]
            elif code is None:
                families["policy_pdf_without_policy_number"] = families.get("policy_pdf_without_policy_number", []) + [text]
                continue
            if filename_code and filename_code.lower() != code.lower():
                families["header_number_differs_from_filename"] = families.get("header_number_differs_from_filename", []) + [f"{fname} -> {code}"]
            display = code.replace("-", " ") if re.match(r"^[A-Z]", code) else text
            families["policy_pdf"] += 1
        label = code
        if label.lower() in labels:  # two files printing one policy number
            labels[label.lower()] += 1
            label = f"{label}-{labels[label.lower()]}"
            families["duplicate_policy_number"] = families.get("duplicate_policy_number", []) + [label]
        else:
            labels[label.lower()] = 1
        docs.append(state_doc(
            "us-va", "vdh", label,
            f"Virginia WIC Policy and Procedures Manual {display}: {text}" if display != text else f"Virginia WIC Policy and Procedures Manual: {text}",
            url,
            authority="Virginia Department of Health, Division of Community Nutrition",
            index_url=index, manual="Virginia WIC Policy and Procedures Manual",
            extra={"index_functional_area": section, "label_source": "page-one policy number, else filename"},
        ))
    if len(docs) < 100:
        raise RuntimeError(f"VA index yielded only {len(docs)} policies")
    return write_manifest("us-va-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_wa() -> tuple[str, int, dict]:
    """Washington: Volume 1 and Volume 2 chapter PDFs (plus the chapter-section 'Required Guidance' PDFs the index
    lists under a chapter); revision tables, staff tools, forms and the post-PHE guidance family are inventoried only."""
    index = ("https://doh.wa.gov/public-health-provider-resources/public-health-system-resources-and-services/"
             "local-health-resources-and-tools/wic/policy-procedures")
    page = soup_of(get(index))
    main = page.select_one("main") or page
    docs = []
    families = {"chapter_pdf": 0, "chapter_section_required_guidance_pdf": 0, "revision_table_pdf": 0,
                "policy_revision_pdf": 0, "post_phe_guidance_pdf": 0, "required_local_agency_policies_pdf": 0,
                "staff_tool_form_or_other_file": 0, "vacant_chapter": []}
    volume = chapter = group = None
    for el in main.find_all(["h2", "h3", "a"]):
        if el.name == "h2":
            t = el.get_text(" ", strip=True)
            volume = {"Volume 1": 1, "Volume 2": 2}.get(t)
            group = "phe" if "PHE" in t else ("required_la" if t.startswith("Required Local Agency") else None)
            chapter = None
            continue
        if el.name == "h3":
            t = " ".join(el.get_text(" ", strip=True).replace("\xa0", " ").split())
            m = re.match(r"^(Draft\s+)?Chapter (\d+):\s*(.*)$", t)
            if m and volume:
                chapter = (int(m.group(2)), m.group(3), bool(m.group(1)))
                if "Vacant" in m.group(3):
                    families["vacant_chapter"].append(f"volume-{volume}-chapter-{m.group(2)}")
            elif "PHE" in t:
                group = "phe"
            continue
        href = el.get("href", "")
        if not re.search(r"\.(pdf|docx?|xlsx?)(\?|$)", href, re.I):
            continue
        fname = href.rsplit("/", 1)[-1]
        text = " ".join(el.get_text(" ", strip=True).replace("\xa0", " ").split())
        if re.search(r"RevisionLog|LogOfRevisionDates|Revision-?Table|revisiontable|Notice-?of-?Revisions?-", fname, re.I):
            families["revision_table_pdf"] += 1
            continue
        if volume and chapter:
            number, title, draft = chapter
            if re.search(rf"Volume{volume}Chapter(?:%20|\s)?{number}\.pdf$", fname, re.I):
                families["chapter_pdf"] += 1
                label = f"volume-{volume}-chapter-{number}"
                docs.append(state_doc(
                    "us-wa", "doh", label, f"Washington State WIC Manual Volume {volume}, Chapter {number}: {title}",
                    urljoin(index, href), authority="Washington State Department of Health, WIC Nutrition Program",
                    index_url=index, manual="Washington State WIC Manual (Policy and Procedure Manual, Volumes 1 and 2)",
                    extra={"volume": volume, "chapter": number, "working_draft": draft},
                ))
                continue
            sm = re.search(rf"Volume{volume}Chapter{number}Section(\d+)\.pdf$", fname, re.I)
            if sm:
                families["chapter_section_required_guidance_pdf"] += 1
                label = f"volume-{volume}-chapter-{number}-section-{sm.group(1)}"
                docs.append(state_doc(
                    "us-wa", "doh", label,
                    f"Washington State WIC Manual Volume {volume}, Chapter {number}, Section {sm.group(1)}: {text.replace(' (PDF)', '')}",
                    urljoin(index, href), authority="Washington State Department of Health, WIC Nutrition Program",
                    index_url=index, manual="Washington State WIC Manual (Policy and Procedure Manual, Volumes 1 and 2)",
                    extra={"volume": volume, "chapter": number, "section": int(sm.group(1)), "working_draft": False},
                ))
                continue
            if "CertifyingAfterDelivery" in fname:
                families["policy_revision_pdf"] += 1
                continue
            families["staff_tool_form_or_other_file"] += 1
            continue
        if group == "phe":
            families["post_phe_guidance_pdf"] += 1
        elif group == "required_la":
            families["required_local_agency_policies_pdf"] += 1
        else:
            families["staff_tool_form_or_other_file"] += 1
    if len(docs) < 25:
        raise RuntimeError(f"WA index yielded only {len(docs)} chapters")
    return write_manifest("us-wa-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_md() -> tuple[str, int, dict]:
    """Maryland: eight chapter files (each a compiled chapter of numbered policies) on the Policies and Procedures page."""
    index = "https://health.maryland.gov/phpa/wic/Pages/wic-policy.aspx"
    page = soup_of(get(index))
    docs, families = [], {"chapter_pdf": 0, "other_pdf": 0}
    for a in page.find_all("a", href=True):
        if not a["href"].lower().endswith(".pdf"):
            continue
        text = " ".join(a.get_text(" ", strip=True).replace("​", "").split())
        m = re.match(r"^(\d)\s+(.*)$", text)
        if not (m and "/phpa/wic/Documents/" in a["href"]):
            families["other_pdf"] += 1
            continue
        families["chapter_pdf"] += 1
        docs.append(state_doc(
            "us-md", "mdh", f"chapter-{m.group(1)}", f"Maryland WIC Program Policy and Procedure Manual Chapter {m.group(1)}: {m.group(2)}",
            urljoin(index, quote(a["href"], safe="/:%")), authority="Maryland Department of Health, Maryland WIC Program",
            index_url=index, manual="Maryland WIC Program Policy and Procedure Manual",
            extra={"chapter": int(m.group(1))},
        ))
    if len(docs) < 8:
        raise RuntimeError(f"MD index yielded only {len(docs)} chapters")
    return write_manifest("us-md-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_nj() -> tuple[str, int, dict]:
    """New Jersey publishes only the vendor-management functional area (P&P 1.31-1.50) of its WIC Services Policy and
    Procedure Manual, on the Vendor Policies and Procedures page; the rest of the manual is not on nj.gov."""
    index = "https://www.nj.gov/health/fhs/wic/vendors/policies.shtml"
    page = soup_of(get(index))
    docs, families = [], {"vendor_management_policy_pdf": 0, "other_pdf": 0}
    for a in page.find_all("a", href=True):
        if not a["href"].lower().endswith(".pdf"):
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        m = re.match(r"^P&P (\d\.\d\d)\s+(.*)$", text)
        if not (m and "/documents/PP/" in a["href"]):
            families["other_pdf"] += 1
            continue
        families["vendor_management_policy_pdf"] += 1
        title = re.sub(r"\.pdf$", "", m.group(2))
        title = re.sub(r"\s*-\s*(Approved\s+)?[A-Z][a-z]+ \d{1,2},? \d{4}$", "", title)
        title = re.sub(r"\s+\d{1,2}-\d{1,2}-\d{4}$", "", title)
        docs.append(state_doc(
            "us-nj", "doh", m.group(1), f"New Jersey WIC Services Policy and Procedure Manual P&P {m.group(1)}: {title}",
            urljoin(index, quote(a["href"], safe="/:%")),  # hrefs contain literal (double) spaces
            authority="New Jersey Department of Health, WIC Services",
            index_url=index, manual="New Jersey WIC Services Policy and Procedure Manual",
            extra={"index_link_text": text, "functional_area": "vendor management",
                   "manual_coverage_note": ("only the vendor-management P&Ps are published on nj.gov; the publisher says "
                                            "some are redacted; the remaining functional areas of the manual are not published")},
        ))
    if len(docs) < 5:
        raise RuntimeError(f"NJ index yielded only {len(docs)} policies")
    return write_manifest("us-nj-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.lower().replace("&", " and ")).strip("-.")


def build_co() -> tuple[str, int, dict]:
    """Colorado: the CDPHE WIC site (coloradowic.gov) indexes the FY26 policies by section (drawer titles
    'Section N: ...'); every policy links to a file on the agency's Google Drive (drive.google.com/file/d/...),
    which the extractor's ``google_drive_download_url`` already handles (manifests/us-co-snap-primary-policy.yaml
    takes CDHS state plans the same way). The compiled FY26 manual (one Drive file, linked once at the top and
    once per section as 'Open Section N to view content') is inventoried, not taken."""
    index = "https://www.coloradowic.gov/policies-procedures/manuals/wic-policy-manual"
    page = soup_of(get(index))
    main = page.select_one("main") or page
    docs, labels = [], {}
    families = {"policy_pdf_on_agency_google_drive": 0, "compiled_manual_pdf": 0, "compiled_manual_links": 0,
                "duplicate_policy_title": [], "section_without_policies": []}
    compiled_ids: set[str] = set()
    section = None
    sections_seen: dict[str, int] = {}
    for el in main.find_all(True):
        text = " ".join(el.get_text(" ", strip=True).split())
        if el.name == "span" and "drawer__title" in (el.get("class") or []) and re.match(r"^Section \d+:", text):
            section = text
            sections_seen[section] = 0
            continue
        if el.name != "a":
            continue
        m = re.match(r"^https?://drive\.google\.com/file/d/([^/]+)/", el.get("href", ""))
        if not m:
            continue
        file_id = m.group(1)
        if text.startswith("View FY26 Compiled") or text.startswith("Open Section"):
            families["compiled_manual_links"] += 1
            compiled_ids.add(file_id)
            continue
        families["policy_pdf_on_agency_google_drive"] += 1
        if section:
            sections_seen[section] += 1
        label = slug(text)
        if label in labels:  # 'Nutrition Education Plan' is linked twice to two different files
            labels[label] += 1
            label = f"{label}-{labels[label]}"
            families["duplicate_policy_title"].append(f"{text} -> {label}")
        else:
            labels[label] = 1
        sm = re.match(r"^Section (\d+): (.*)$", section or "")
        docs.append(state_doc(
            "us-co", "cdphe", label, f"Colorado WIC Policies and Procedures, {section}: {text}" if section else f"Colorado WIC Policies and Procedures: {text}",
            f"https://drive.google.com/file/d/{file_id}/view",
            authority="Colorado Department of Public Health and Environment, WIC Program",
            index_url=index, manual="Colorado WIC Policies and Procedures (FY26 Program Manual)",
            extra={"index_section_number": int(sm.group(1)) if sm else None, "index_section_title": sm.group(2) if sm else None,
                   "google_drive_file_id": file_id, "index_link_text": text,
                   "access_note": ("coloradowic.gov links each policy to a file on the agency's Google Drive; the extractor's "
                                   "google_drive_download_url fetches it directly, as for manifests/us-co-snap-primary-policy.yaml")},
        ))
    families["compiled_manual_pdf"] = len(compiled_ids)
    families["section_without_policies"] = [s for s, n in sections_seen.items() if n == 0]
    if len(docs) < 80:
        raise RuntimeError(f"CO index yielded only {len(docs)} policies")
    return write_manifest("us-co-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_mn() -> tuple[str, int, dict]:
    """Minnesota: the Minnesota Operations Manual (MOM) page lists every chapter section PDF (sctnC_S[_T].pdf) and
    exhibit (PDF/Word) under chapter drawers ('N. Title'). Sections are taken; the two '- all' compilations of 5.2 and
    5.3, the draft 7.10 and draft exhibit 7-D, and the exhibits (forms, tables, sample letters) are inventoried."""
    index = "https://www.health.state.mn.us/people/wic/localagency/mom.html"
    page = soup_of(get(index))
    main = page.select_one("main") or page
    docs, seen_urls = [], set()
    families = {"chapter_section_pdf": 0, "chapter_section_compilation_pdf": 0, "draft_section_pdf": 0,
                "exhibit_pdf": 0, "exhibit_docx": 0, "draft_exhibit_pdf": 0, "duplicate_link_same_file": 0,
                "link_text_number_differs_from_filename": [], "chapters": {}}
    chapter = None
    for el in main.find_all(["button", "a"]):
        text = " ".join(el.get_text(" ", strip=True).split())
        if el.name == "button":
            m = re.match(r"^(\d+)\. (.+)$", text)
            if m:
                chapter = (int(m.group(1)), m.group(2))
                families["chapters"][m.group(1)] = m.group(2)
            continue
        href = el.get("href", "")
        if not re.search(r"\.(pdf|docx?)$", href, re.I):
            continue
        url = urljoin(index, href)
        fname = href.rsplit("/", 1)[-1]
        if url in seen_urls:  # 4.8 and exhibits 4-C/4-D/4-E are linked under two chapters
            families["duplicate_link_same_file"] += 1
            continue
        seen_urls.add(url)
        if "/fp/draftsect" in href:
            families["draft_section_pdf"] += 1
            continue
        if "/formula/oct2026ex7d" in href:
            families["draft_exhibit_pdf"] += 1
            continue
        sm = re.match(r"^sctn(\d+)_(\d+)(?:_(\d+))?(all)?\.pdf$", fname, re.I)
        if not sm:
            families["exhibit_docx" if fname.lower().endswith(".docx") else "exhibit_pdf"] += 1
            continue
        if sm.group(4):
            families["chapter_section_compilation_pdf"] += 1
            continue
        label = ".".join(g for g in sm.groups()[:3] if g)
        tm = re.match(r"^(\d+(?:\.\d+)+)\s+(.*?)\s*\((?:PDF|PD)\)$", text)
        title = tm.group(2) if tm else text
        if tm and tm.group(1) != label:
            families["link_text_number_differs_from_filename"].append(f"{text} -> {fname}")
        families["chapter_section_pdf"] += 1
        docs.append(state_doc(
            "us-mn", "mdh", label, f"Minnesota WIC Operations Manual (MOM) Section {label}: {title}", url,
            authority="Minnesota Department of Health, WIC Program",
            index_url=index, manual="Minnesota Operations Manual (MOM)",
            extra={"chapter": int(sm.group(1)), "chapter_title": chapter[1] if chapter and chapter[0] == int(sm.group(1)) else None},
        ))
    if len(docs) < 70:
        raise RuntimeError(f"MN index yielded only {len(docs)} sections")
    return write_manifest("us-mn-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


CT_SERIES = ("100", "101", "102", "104", "105", "106", "200", "300", "400")


def build_ct() -> tuple[str, int, dict]:
    """Connecticut: the CT WIC State Plan page links one 'State Plan Policies - WIC NNN' page per series (100-106,
    200, 300, 400) and two singleton policies (103-01, 108-01). On each series page the first PDF under a policy
    number 'WIC NNN-NN' is the policy; later files under the same number are attachments (forms, tools, guidance),
    except the 300-02 addenda (maximum monthly allowances), which are taken as their own documents."""
    index = "https://portal.ct.gov/dph/wic/ct-wic-state-plan"
    docs, numbers = [], {}
    families = {"policy_pdf": 0, "policy_addendum_pdf": 0, "table_of_contents_pdf": 0, "numbered_attachment_pdf": 0,
                "numbered_attachment_non_pdf": 0, "unnumbered_form_guidance_or_translation_pdf": 0,
                "unnumbered_non_pdf": 0, "state_plan_section_1_pdf": 0, "series_pages": []}
    authority = "Connecticut Department of Public Health, WIC Program"
    manual = "Connecticut WIC Program Manual (State Plan Section 2 policies)"

    def take(number: str, title: str, url: str, page_url: str, series: str, label: str | None = None) -> None:
        docs.append(state_doc(
            "us-ct", "dph", label or number, f"Connecticut WIC Program Manual WIC {number}: {title}", url,
            authority=authority, index_url=page_url, manual=manual,
            extra={"series": series, "policy_number": number, "state_plan_index_url": index},
        ))

    plan = soup_of(get(index))
    main = plan.select_one("main") or plan
    for a in main.find_all("a", href=True):
        href, text = a["href"], " ".join(a.get_text(" ", strip=True).split())
        fname = href.split("?")[0].rsplit("/", 1)[-1].lower()
        if "state-plan-policies---section-1" in href:
            families["state_plan_section_1_pdf"] += 1
            continue
        m = re.match(r"^wic-(\d{3})-(\d{2})-", fname)
        if m and fname.endswith(".pdf"):
            number = f"{m.group(1)}-{m.group(2)}"
            numbers[number] = 1
            families["policy_pdf"] += 1
            take(number, re.sub(r"^\d{3}\s+", "", text), urljoin(index, href), index, m.group(1))
    for series in CT_SERIES:
        page_url = f"https://portal.ct.gov/dph/wic/state-plan-policies---wic-{series}"
        families["series_pages"].append(page_url)
        page = soup_of(get(page_url))
        main = page.select_one("main") or page
        for a in main.find_all("a", href=True):
            href = a["href"]
            if "/media/" not in href or "/wic-2018/" not in href:
                continue
            text = " ".join(a.get_text(" ", strip=True).split())
            fname = href.split("?")[0].rsplit("/", 1)[-1].lower()
            is_pdf = fname.endswith(".pdf")
            if fname.startswith("table-of-contents"):
                families["table_of_contents_pdf"] += 1
                continue
            m = re.match(r"^WIC (\d{3})-(\d{2})\s+(.*)$", text)
            if not m:
                families["unnumbered_form_guidance_or_translation_pdf" if is_pdf else "unnumbered_non_pdf"] += 1
                continue
            number, title = f"{m.group(1)}-{m.group(2)}", m.group(3)
            if number not in numbers and is_pdf:
                numbers[number] = 1
                families["policy_pdf"] += 1
                take(number, title, urljoin(page_url, href), page_url, series)
                continue
            am = re.match(r"^Addendum ([IVX]+)\b", title)
            if am and is_pdf:
                families["policy_addendum_pdf"] += 1
                take(number, title, urljoin(page_url, href), page_url, series, label=f"{number}-addendum-{am.group(1).lower()}")
                continue
            families["numbered_attachment_pdf" if is_pdf else "numbered_attachment_non_pdf"] += 1
    if len(docs) < 90:
        raise RuntimeError(f"CT index yielded only {len(docs)} policies")
    return write_manifest("us-ct-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_ut() -> tuple[str, int, dict]:
    """Utah: the 'WIC policies' page lists the current Local Agency Policy and Procedures Manual, one PDF per policy
    under functional areas I-XI (VI has none). The FY 2027 state plan's 'Section II: Local Agency Policy and
    Procedure Manual' draft page is a separate, proposed version and is only counted."""
    index = "https://wic.utah.gov/about/wic-policies/"
    page = soup_of(get(index))
    main = page.select_one("main") or page
    docs, labels = [], {}
    families = {"policy_pdf": 0, "functional_area_without_policies": [], "duplicate_policy_title": [],
                "fy2027_state_plan_section_ii_draft_pdf_on_separate_page": 0}
    area = None
    counts: dict[str, int] = {}
    for el in main.find_all(["h3", "a"]):
        text = " ".join(el.get_text(" ", strip=True).split())
        if el.name == "h3":
            area = text
            counts[area] = 0
            continue
        href = el.get("href", "")
        if not href.lower().endswith(".pdf") or "/wp-content/uploads/" not in href:
            continue
        families["policy_pdf"] += 1
        if area:
            counts[area] += 1
        label = slug(text)
        if label in labels:
            labels[label] += 1
            label = f"{label}-{labels[label]}"
            families["duplicate_policy_title"].append(f"{text} -> {label}")
        else:
            labels[label] = 1
        docs.append(state_doc(
            "us-ut", "dhhs", label, f"Utah WIC Local Agency Policy and Procedures Manual, {area}: {text}" if area else f"Utah WIC Local Agency Policy and Procedures Manual: {text}",
            urljoin(index, href), authority="Utah Department of Health and Human Services, WIC Program",
            index_url=index, manual="Utah WIC Local Agency Policy and Procedures Manual",
            extra={"functional_area": area, "index_link_text": text},
        ))
    families["functional_area_without_policies"] = [a for a, n in counts.items() if n == 0]
    draft = soup_of(get("https://wic.utah.gov/about/wic-policies/proposed-state-plan/section-ii-local-agency-policy-and-procedure-manual-draft/"))
    families["fy2027_state_plan_section_ii_draft_pdf_on_separate_page"] = sum(
        1 for a in (draft.select_one("main") or draft).find_all("a", href=True) if a["href"].lower().endswith(".pdf") and "/wp-content/uploads/" in a["href"]
    )
    if len(docs) < 90:
        raise RuntimeError(f"UT index yielded only {len(docs)} policies")
    return write_manifest("us-ut-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


# Iowa policy PDFs that are page scans without a text layer (pdftotext yields nothing); the extractor's existing
# ``ocr`` option runs tesseract only on pages that have no text, so it is set per document rather than for the scope.
IA_IMAGE_ONLY_PDFS = {"450.70-snap-wic-mou"}


def build_ia() -> tuple[str, int, dict]:
    """Iowa: the WIC Portal 'Policies' page lists the Policy and Procedure Manual by functional area (I-XI plus
    Program Integrity), each area split into POLICIES, PROCEDURES and FORMS headings; files are Drupal media
    downloads (/media/N/download). Policies and procedures (PDF) are taken; forms, booklets, Word files and the
    translations of forms are inventoried."""
    index = "https://hhs.iowa.gov/wic-portal/policies"
    page = soup_of(get(index))
    main = page.select_one("main") or page
    docs, labels, seen_urls = [], {}, {}
    families = {"policy_pdf": 0, "procedure_pdf": 0, "definitions_pdf": 0, "form_or_booklet_pdf": 0, "non_pdf_file": 0,
                "duplicate_link_same_file": 0, "duplicate_policy_title": [], "image_only_pdf_ocr": []}
    area = kind = None
    for el in main.find_all(["h2", "h3", "a"]):
        text = " ".join(el.get_text(" ", strip=True).split())
        if el.name in ("h2", "h3"):
            m = re.match(r"^((?:[IVX]+\.\s+)?.*?)\s*(POLICIES|PROCEDURES|FORMS)?$", text)
            if text == "Content Information":
                area, kind = "Definitions", "definitions"
            elif m and (m.group(2) or re.match(r"^[IVX]+\.", text)):
                area = m.group(1).strip() or area
                kind = {"POLICIES": "policy", "PROCEDURES": "procedure", "FORMS": "form", None: "policy"}[m.group(2)]
            continue
        href = el.get("href", "")
        if not re.search(r"/media/\d+/download", href):
            continue
        url = urljoin(index, href)
        tm = re.match(r"^(.*?)\s*\(([\d.,]+ [KM]B)\)\s*\.(\w+)$", text)
        title, ext = (tm.group(1), tm.group(3).lower()) if tm else (text, "pdf")
        if url in seen_urls:
            families["duplicate_link_same_file"] += 1
            continue
        seen_urls[url] = title
        if ext != "pdf":
            families["non_pdf_file"] += 1
            continue
        if kind == "form" or re.search(r"\((Form|Booklet)\)\s*$", title):
            families["form_or_booklet_pdf"] += 1
            continue
        families[f"{kind}_pdf"] += 1
        label = slug(title)
        if label in labels:  # 450.40 Sanctions and 450.60 Dual Participation are two files each (vendor and program integrity)
            labels[label] += 1
            label = f"{label}-{labels[label]}"
            families["duplicate_policy_title"].append(f"{area}: {title} -> {label}")
        else:
            labels[label] = 1
        doc = state_doc(
            "us-ia", "hhs", label, f"Iowa WIC Policy and Procedure Manual, {area}: {title}", url,
            authority="Iowa Department of Health and Human Services, WIC Program",
            index_url=index, manual="Iowa WIC Policy and Procedure Manual (WIC Portal)",
            extra={"functional_area": area, "manual_part": kind, "index_link_text": text},
        )
        if label in IA_IMAGE_ONLY_PDFS:  # scanned PDF with no text layer: OCR fallback (tesseract) for its pages
            doc["extraction"]["ocr"] = True
            doc["metadata"]["image_only_pdf"] = True
            families["image_only_pdf_ocr"].append(f"{area}: {title} -> {label}")
        docs.append(doc)
    if len(docs) < 120:
        raise RuntimeError(f"IA index yielded only {len(docs)} policies")
    return write_manifest("us-ia-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_or() -> tuple[str, int, dict]:
    """Oregon: the WIC Policy and Procedure Manual page lists every policy as '<a>NNN</a> Title' under 'Sec NNN: Title'
    headings below the 'Policies' h2 (sections 100-1100; 400 and 500 are both 'Local Operations'). The
    'WIC Policy Updates (Release Notes)' h2 above it lists the quarterly policy-update memos, which are inventoried,
    not taken."""
    index = "https://www.oregon.gov/OHA/PH/HEALTHYPEOPLEFAMILIES/WIC/Pages/wicpolicy.aspx"
    page = soup_of(get(index))
    docs, seen = [], set()
    families = {"policy_pdf": 0, "policy_update_release_notes_pdf": 0, "duplicate_policy_number": [], "sections": {}}
    policies_h2 = next(h for h in page.find_all("h2") if h.get_text(strip=True).startswith("Policies"))
    for h3 in policies_h2.find_all_next("h3"):
        m = re.match(r"^Sec (\d+): (.+)$", " ".join(h3.get_text(" ", strip=True).split()))
        if not m:
            continue
        sec_num, sec_title = m.group(1), m.group(2)
        families["sections"][sec_num] = sec_title
        for a in h3.parent.find_all("a", href=True):
            pm = re.search(r"/ppm/(\d+)\.pdf$", a["href"], re.I)
            if not pm:
                continue
            label = pm.group(1)
            sib = a.next_sibling
            title = " ".join(sib.split()) if isinstance(sib, str) else ""
            families["policy_pdf"] += 1
            if label in seen:
                families["duplicate_policy_number"].append(label)
                continue
            seen.add(label)
            docs.append(state_doc(
                "us-or", "oha", label,
                f"Oregon WIC Policy and Procedure Manual, Section {sec_num} {sec_title}: Policy {label} {title}".rstrip(),
                urljoin(index, a["href"]), authority="Oregon Health Authority, Public Health Division, WIC Program",
                index_url=index, manual="Oregon WIC Policy and Procedure Manual",
                extra={"section": sec_num, "section_title": sec_title, "index_link_text": a.get_text(strip=True),
                       "index_policy_title": title},
            ))
    families["policy_update_release_notes_pdf"] = sum(
        1 for a in page.find_all("a", href=True)
        if "/ppm/" in a["href"] and a["href"].lower().endswith(".pdf") and not re.search(r"/ppm/\d+\.pdf$", a["href"], re.I)
    )
    if len(docs) < 80:
        raise RuntimeError(f"OR index yielded only {len(docs)} policies")
    return write_manifest("us-or-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_ky() -> tuple[str, int, dict]:
    """Kentucky: the WIC page's 'WIC and Nutrition Manual' heading lists the manual's policy groups, one PDF each
    (100-900 plus 800B Farmers Market), and the FY 25 summary of policy changes, which is inventoried, not taken."""
    index = "https://www.chfs.ky.gov/agencies/dph/dmch/nsb/Pages/wic.aspx"
    page = soup_of(get(index))
    heading = next(h for h in page.find_all("h3") if "WIC and Nutrition Manual" in h.get_text(" ", strip=True))
    docs = []
    families = {"policy_group_pdf": 0, "summary_of_policy_changes_pdf": 0, "other_pdf_under_manual_heading": []}
    for el in heading.find_all_next(["h3", "a"]):
        if el.name == "h3":
            break
        href = el.get("href", "")
        if not href.lower().endswith(".pdf"):
            continue
        text = " ".join(el.get_text(" ", strip=True).replace("\u200b", "").split())
        m = re.match(r"^(\d{3}[A-Z]?) ?Policy Group - (.+)$", text)
        if m:
            families["policy_group_pdf"] += 1
            docs.append(state_doc(
                "us-ky", "chfs", m.group(1).lower(), f"Kentucky WIC and Nutrition Manual, {m.group(1)} Policy Group: {m.group(2)}",
                urljoin(index, href),
                authority="Kentucky Cabinet for Health and Family Services, Department for Public Health, Nutrition Services Branch",
                index_url=index, manual="Kentucky WIC and Nutrition Manual",
                extra={"policy_group": m.group(1), "index_link_text": text},
            ))
        elif "Summary of Policy Changes" in text:
            families["summary_of_policy_changes_pdf"] += 1
        else:
            families["other_pdf_under_manual_heading"].append(text)
    if len(docs) < 9:
        raise RuntimeError(f"KY index yielded only {len(docs)} policy groups")
    return write_manifest("us-ky-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_wv() -> tuple[str, int, dict]:
    """West Virginia: the Policy/Procedure page links one page per manual chapter ('N.0 Title', 1.0-11.0); each chapter
    page lists the policies as 'N.NN Title' PDFs with their attachments ('..., Attachment #k') and the chapter's index
    table. Policies are taken; attachments, index tables, the two state plans and the participant agreements are
    inventoried."""
    index = "https://dhhr.wv.gov/WIC/policyprocedure/Pages/Default.aspx"
    page = soup_of(get(index))
    docs, labels, seen_urls = [], {}, set()
    families = {"policy_pdf": 0, "attachment_pdf": 0, "chapter_index_table_pdf": 0, "other_chapter_page_file": [],
                "state_plan_page": 0, "participant_agreement_pdf": 0, "duplicate_link_same_file": [],
                "duplicate_policy_number": [], "chapters": {}}
    chapter_pages = []
    for a in (page.select_one("#contentBox") or page).find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).replace("\u200b", "").split())
        href = a["href"]
        m = re.match(r"^(\d+)\.0 (.+)$", text)
        if m and "/policyprocedure/Pages/" in href:
            chapter_pages.append((m.group(1), m.group(2), urljoin(index, href)))
            families["chapters"][m.group(1)] = m.group(2)
        elif "State Plan" in text and "/policyprocedure/Pages/" in href:
            families["state_plan_page"] += 1
        elif "Participant Agreement" in text and href.lower().endswith(".pdf"):
            families["participant_agreement_pdf"] += 1
    for num, title, url in chapter_pages:
        chapter = soup_of(get(url))
        for a in (chapter.select_one("#contentBox") or chapter).find_all("a", href=True):
            href = a["href"]
            if not href.lower().endswith(".pdf"):
                continue
            text = " ".join(a.get_text(" ", strip=True).replace("\u200b", "").split())
            if "Index Table" in text:
                families["chapter_index_table_pdf"] += 1
                continue
            if re.search(r"Attachment", text, re.I):
                families["attachment_pdf"] += 1
                continue
            pm = re.match(r"^(\d+\.\d+)\s+(.+)$", text)
            if not pm or pm.group(1).split(".")[0] != num:
                families["other_chapter_page_file"].append(f"{num}.0: {text}")
                continue
            label, ptitle = pm.group(1), pm.group(2)
            if urljoin(url, href) in seen_urls:  # 3.16 is linked twice to the same file
                families["duplicate_link_same_file"].append(text)
                continue
            seen_urls.add(urljoin(url, href))
            families["policy_pdf"] += 1
            if label in labels:
                labels[label] += 1
                families["duplicate_policy_number"].append(f"{text} -> {label}-{labels[label]}")
                label = f"{label}-{labels[label]}"
            else:
                labels[label] = 1
            docs.append(state_doc(
                "us-wv", "dhhr", label, f"West Virginia WIC Program Policy and Procedure Manual, Chapter {num}.0 {title}: {pm.group(1)} {ptitle}",
                urljoin(url, href), authority="West Virginia Department of Health, Office of Nutrition Services, WIC Program",
                index_url=url, manual="West Virginia WIC Program Policy and Procedure Manual",
                extra={"chapter": f"{num}.0", "chapter_title": title, "index_link_text": text, "policy_index_url": index},
            ))
    if len(docs) < 50:
        raise RuntimeError(f"WV chapter pages yielded only {len(docs)} policies")
    return write_manifest("us-wv-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_me() -> tuple[str, int, dict]:
    """Maine: the 'WIC Policies' page lists the Maine WIC Policy and Procedure Manual as one PDF per policy, labelled by
    series code and number ('CE-2 Income Eligibility Determination and Documentation'), with the appendices ('Appendix
    CE-2-A ...') under each series. Policies are taken; appendices and any other file are inventoried."""
    index = "https://www.maine.gov/dhhs/mecdc/healthy-living/wic/wic-administration-and-policies/wic-policies"
    page = soup_of(get(index))
    docs, labels = [], {}
    families = {"policy_pdf": 0, "appendix_file": 0, "other_file": [], "duplicate_policy_code": [], "series": {}}
    main = page.select_one("main") or page
    for a in main.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"\.(pdf|docx?)$", href.split("?")[0], re.I) or "/files/" not in href:
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        text = re.sub(r"\s*\((PDF|Word)\)$", "", text)
        text = re.sub(r"\.pdf$", "", text, flags=re.I)
        if text.lower().startswith("appendix"):
            families["appendix_file"] += 1
            continue
        m = re.match(r"^([A-Z]{2,5})-(\d+)[\s_]+(.+)$", text)
        if not m:
            families["other_file"].append(text)
            continue
        code = f"{m.group(1)}-{m.group(2)}"
        label = code.lower()
        families["policy_pdf"] += 1
        families["series"][m.group(1)] = families["series"].get(m.group(1), 0) + 1
        if label in labels:
            labels[label] += 1
            families["duplicate_policy_code"].append(f"{text} -> {label}-{labels[label]}")
            label = f"{label}-{labels[label]}"
        else:
            labels[label] = 1
        docs.append(state_doc(
            "us-me", "mecdc", label, f"Maine WIC Policy and Procedure Manual, {code}: {m.group(3)}", urljoin(index, href),
            authority="Maine Department of Health and Human Services, Maine CDC, WIC Nutrition Program",
            index_url=index, manual="Maine WIC Policy and Procedure Manual",
            extra={"series": m.group(1), "index_link_text": text},
        ))
    if len(docs) < 40:
        raise RuntimeError(f"ME index yielded only {len(docs)} policies")
    return write_manifest("us-me-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_ri() -> tuple[str, int, dict]:
    """Rhode Island: the WIC program page publishes the manual as one compiled PDF ('WIC Procedures Manual') plus the
    'WIC Vendor Policies' PDF; both are taken as single documents (no per-policy index exists)."""
    index = "https://health.ri.gov/programs/wic/"
    page = soup_of(get(index))
    wanted = {"WIC Procedures Manual": ("procedures-manual", "Rhode Island WIC Procedures Manual"),
              "WIC Vendor Policies": ("vendor-policies", "Rhode Island WIC Vendor Policies")}
    docs, families = [], {"compiled_manual_pdf": 0, "vendor_policies_pdf": 0, "other_pdf_on_program_page": 0}
    for a in page.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        if not a["href"].lower().endswith(".pdf"):
            continue
        if text not in wanted:
            families["other_pdf_on_program_page"] += 1
            continue
        label, title = wanted[text]
        families["compiled_manual_pdf" if label == "procedures-manual" else "vendor_policies_pdf"] += 1
        docs.append(state_doc(
            "us-ri", "ridoh", label, title, urljoin(index, a["href"]),
            authority="Rhode Island Department of Health, WIC Program", index_url=index,
            manual="Rhode Island WIC Procedures Manual", extra={"index_link_text": text, "compiled_manual": True},
        ))
    if len(docs) != 2:
        raise RuntimeError(f"RI program page yielded {len(docs)} of the two expected PDFs")
    return write_manifest("us-ri-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


def build_dc() -> tuple[str, int, dict]:
    """District of Columbia: DC Health's WIC State Agency publishes its policies on the program site dcwic.org, which the
    dchealth.dc.gov WIC service page links as 'dcwic.org' (the site footer carries DC Health WIC's headquarters address
    and info.wic@dc.gov). The public 'Policies, Forms, & Tools' page (policies-forms; the 'LA Staff Portal' is
    password-protected and was not entered) has a Webflow tab set whose 'Policy and Procedures' tab holds one dropdown
    per chapter ('2 - Nutrition Services' ... '12 - Administrative Procedures'; no chapter 1 or 6 is listed) of
    '<N.NNN> Title' policy PDFs and lettered '<N.NNNA> Title' attachments (forms, guides, workbooks). Policies are
    taken; attachments, the other four tabs, the two clinical manuals (Anthropometrics, Laboratory) and the style guides
    above the tabs are inventoried, not taken. Files are served from the site's Webflow CDN (cdn.prod.website-files.com)."""
    index = "https://www.dcwic.org/policies-forms"
    page = soup_of(get(index))
    tabs = page.select_one("div.w-tabs")
    docs, seen_labels, seen_urls = [], set(), set()
    families = {"policy_pdf": 0, "policy_attachment_file": 0, "clinical_manual_pdf": 0, "style_guide_pdf": 0,
                "admin_forms_tab_file": 0, "assessment_tools_tab_file": 0, "substance_use_resources_tab_file": 0,
                "teletask_messaging_guides_tab_file": 0, "chapters": {}, "duplicate_link_same_file": 0,
                "duplicate_policy_number": []}
    tab_family = {"Admin Forms": "admin_forms_tab_file", "Assessment Tools": "assessment_tools_tab_file",
                  "Substance Use Resources": "substance_use_resources_tab_file",
                  "Teletask Messaging Guides": "teletask_messaging_guides_tab_file"}
    for pane in tabs.select(".w-tab-content > .w-tab-pane"):
        name = pane.get("data-w-tab")
        if name in tab_family:
            families[tab_family[name]] += len(pane.find_all("a", href=True))
            continue
        if name != "Policy and Procedures":
            raise RuntimeError(f"DC policies page has an unexpected tab {name!r}")
        for dd in pane.select(".w-dropdown"):
            toggle = " ".join(dd.select_one(".w-dropdown-toggle").get_text(" ", strip=True).split())
            cm = re.match(r"^(\d+) - (.+)$", toggle)
            if not cm:
                raise RuntimeError(f"DC chapter dropdown without an 'N - Title' toggle: {toggle!r}")
            ch_num, ch_title = cm.group(1), cm.group(2)
            families["chapters"][ch_num] = ch_title
            for a in dd.select(".w-dropdown-list a[href]"):
                text = " ".join(a.get_text(" ", strip=True).split())
                url = urljoin(index, a["href"])
                # '11.00lB Civil Rights Complaint Form' (letter l for 1) is an attachment of 11.001
                m = re.match(r"^(\d+)\.(\d{2}[0-9l])([A-Za-z]?)\b\s*(.*)$", text)
                if not m:
                    raise RuntimeError(f"DC policy link without a policy number: {text!r}")
                if url in seen_urls:  # 12.008A links the 12.008 file again
                    families["duplicate_link_same_file"] += 1
                    continue
                seen_urls.add(url)
                if m.group(3):
                    families["policy_attachment_file"] += 1
                    continue
                label, title = f"{m.group(1)}.{m.group(2)}", m.group(4)
                families["policy_pdf"] += 1
                if m.group(1) != ch_num or not url.lower().endswith(".pdf"):
                    raise RuntimeError(f"DC policy {label} ({text!r}) is outside chapter {ch_num} or not a PDF")
                if label in seen_labels:
                    families["duplicate_policy_number"].append(label)
                    continue
                seen_labels.add(label)
                docs.append(state_doc(
                    "us-dc", "dchealth", label,
                    f"DC WIC Policy & Procedure Manual, Chapter {ch_num} {ch_title}: Policy {label} {title}",
                    url, authority="District of Columbia Department of Health (DC Health), WIC State Agency",
                    index_url=index, manual="DC WIC Policy & Procedure Manual",
                    extra={"chapter": ch_num, "chapter_title": ch_title, "index_link_text": text,
                           "program_site": "https://www.dcwic.org/",
                           "agency_page_linking_program_site":
                               "https://dchealth.dc.gov/service/special-supplemental-nutrition-program-women-infants-and-children-wic"},
                ))
    for a in page.find_all("a", href=True):
        if "website-files.com" in a["href"] and a.find_parent(class_="w-tabs") is None:
            families["clinical_manual_pdf" if "manual" in a["href"].lower() else "style_guide_pdf"] += 1
    if len(docs) < 85:
        raise RuntimeError(f"DC index yielded only {len(docs)} policies")
    return write_manifest("us-dc-wic-policy-manual", docs, STATE_VERSION), len(docs), {"index_url": index, **families}


BLOCKED = {
    "us-ny": (
        "New York State Department of Health",
        "https://www.health.ny.gov/prevention/nutrition/wic/",
        "The NYS WIC Program Manual is not published on health.ny.gov: the WIC pages link no manual, the only copies on "
        "the host are inactive procurement attachments (funding/ifb/inactive/16429/wic_program_manual_*.pdf), and current "
        "copies exist only as reposts on non-government sites (nwica.org, thewichub.org), which the queue forbids.",
    ),
    "us-fl": (
        "Florida Department of Health",
        "https://www.floridahealth.gov/individual-family-health/womens-health/wic/",
        "The Florida WIC Procedure Manual (DHM 150-24) is not published on floridahealth.gov: the WIC and health-care-provider "
        "pages link only forms, the vendor handbook and outreach material; the manual is referenced by number in county "
        "documents but no state index or PDF is available.",
    ),
    "us-il": (
        "Illinois Department of Human Services",
        "https://www.dhs.state.il.us/page.aspx?item=36418",
        "The IDHS 'WIC Policy and Procedure Manual' page (item=36418) now redirects to 'Page Not Found' (item=27893); the WIC "
        "program page (item=31907) links no manual. One chapter PDF (onenetlibrary/27896/.../wic/ppm/3_certificationstandards.pdf, "
        "issue date May 2006) is still served, but there is no publisher index from which the current manual can be confirmed.",
    ),
    "us-oh": (
        "Ohio Department of Health",
        "https://odh.ohio.gov/know-our-programs/Women-Infants-Children/Local-Staff",
        "The Ohio WIC Policy and Procedure Manual is not published on odh.ohio.gov: the Local Staff and program pages link no "
        "manual; the only public copy is a July 2015 repost by a county health department, which is neither current nor the publisher.",
    ),
    # second batch
    "us-az": (
        "Arizona Department of Health Services",
        "https://www.azdhs.gov/prevention/azwic/local-agencies/index.php",
        "azdhs.gov answered every request with a Cloudflare HTTP 403 in batch 2. Retried 2026-09-10T21:34Z from a US network: the host "
        "now answers 200, but the batch-2 Local Agencies URL (local-agencies/index.php) is a soft 404 ('Page or Document Not Found') and "
        "the relocated Local Agencies page (prevention/azwic/agencies/index.php) links 'WIC Manuals' to an in-page anchor (#manuals) that "
        "the served page does not contain, for the plain client and one curl_cffi impersonation alike; candidate manuals sub-pages are the "
        "same soft 404 and the documents/prevention/azwic/manuals/policy/ directory answers 403. No manual index is published on the site "
        "as served. No mirror was used.",
    ),
    "us-tn": (
        "Tennessee Department of Health",
        "https://www.tn.gov/health/health-program-areas/fhw/wic.html",
        "www.tn.gov answered HTTP 403 (awselb/2.0) or timed out for every client in batch 2. Retried 2026-09-10T21:34Z from a US network: "
        "the host now answers (two of six requests still failed with a TLS EOF), the batch-2 WIC URL (health-program-areas/fhw/wic.html) is "
        "404 and the relocated WIC page (health/wic.html) links participant, vendor and nutrition-education material, the WIC state rule "
        "(1200-15-02) and the vendor Food Package Policy but no Policy & Procedures Manual index; individual manual policies still exist under "
        "content/dam/tn/health/program-areas/wic/ (FY2022-ADM-01-03-02 answers 200 to HEAD) but no page lists them. No mirror was used.",
    ),
    "us-mo": (
        "Missouri Department of Health and Senior Services",
        "https://health.mo.gov/providers/manuals/wic-operations-manual-wom/",
        "The WIC Operations Manual (WOM) is published only behind the WIC Local Agency Portal login: the manual index and every "
        "section URL (e.g. .../wic-operations-manual-wom/usda-definitions-and-justifications/100s-10) redirect to "
        "health.mo.gov/topic/781/login, and the public WIC pages link no manual.",
    ),
    "us-ma": (
        "Massachusetts Department of Public Health",
        "https://www.mass.gov/orgs/women-infants-children-nutrition-program",
        "The Massachusetts WIC Program Manual (PM) is named in the FFY 2027 WIC state plan as the document the state office "
        "updates, but it is not published on mass.gov: the WIC organization page, the providers page and the state-plan page link "
        "no manual (the state plans are a different document family). mass.gov also answers 403 to non-browser clients.",
    ),
    "us-in": (
        "Indiana Department of Health",
        "https://www.in.gov/health/wic/wic-staff",
        "The Indiana WIC Policy and Procedure Manual is not published on in.gov: the WIC Staff page links only the Indiana WIC "
        "Disaster Plan, and the WIC home, eligibility and vendor pages link only the vendor manual and participant material.",
    ),
    "us-wi": (
        "Wisconsin Department of Health Services",
        "https://www.dhs.wisconsin.gov/wic/professionals.htm",
        "The Wisconsin WIC Policy and Procedure Manual is not published on dhs.wisconsin.gov: the WIC home, Providers and "
        "Professionals and local-project pages link no manual and candidate /wic/ppm*, /wic/local-agency* paths answer 404; the "
        "only policy-like PDFs on the host (wic/certification-eligibility-coordination.pdf, wic/caseload-management.pdf) are "
        "FY 2025 state-plan sections, not a manual index.",
    ),
    # third batch
    "us-sc": (
        "South Carolina Department of Public Health",
        "https://dph.sc.gov/health-wellness/family-planning/women-infants-and-children-wic-nutrition-program",
        "dph.sc.gov answered HTTP 403 (CloudFront) in batch 3. Retried 2026-09-10T21:34Z from a US network: the host now answers 200, but the "
        "WIC program page and its WIC Resources, Healthcare Providers & Formulas and South Carolina WIC subpages link only participant, formula, "
        "food-guide and referral material, and the linked apps.dhec.sc.gov/Health/WIC is a participant sign-in portal; no policy manual index "
        "is published on the site. No mirror was used.",
    ),
    "us-al": (
        "Alabama Department of Public Health",
        "https://www.alabamapublichealth.gov/wic/index.html",
        "The Alabama WIC Procedure Manual (cited as 'Procedure Manual 5.3' by the agency's own WIC formulary) is not published on "
        "alabamapublichealth.gov: the WIC home, Health Care Providers and Health Provider Standards pages link only the formulary, "
        "prescription forms, a certification-process handout, two stand-alone policy PDFs (IID policy, informal resolution process) "
        "and the FY2027 state-plan public notice; no page lists the manual.",
    ),
    "us-la": (
        "Louisiana Department of Health",
        "https://ldh.la.gov/bureau-of-nutrition-services/women-infants-children-program",
        "ldh.la.gov answered HTTP 403 (Cloudflare) in batch 3. Retried 2026-09-10T21:34Z from a US network: the host now answers 200, but the "
        "Bureau of Nutrition Services WIC page, the LDH Forms & Policies page and the agency's louisianawic.org site (participant, vendor, "
        "medical-provider pages) link no Policy & Procedure Manual; the one chapter known on the host (assets/docs/LegisReports/Act542/"
        "WIC_Chapter11.pdf) is a legislative-report attachment, not an index. No mirror was used.",
    ),
    "us-ok": (
        "Oklahoma State Department of Health",
        "https://oklahoma.gov/health/services/children-family-health/wic.html",
        "The Oklahoma WIC policy and procedures manual is not published on oklahoma.gov: the WIC program page and its Health Partners, "
        "WIC Forms, Formula Information, Health & Nutrition and Caseload Data subpages link only the formulary, income guidelines, "
        "clinic list, assessment forms and formula documents; no page lists a manual.",
    ),
    "us-nv": (
        "Nevada Department of Health and Human Services, Nevada WIC",
        "https://nevadawic.org/staff/policy-and-procedures/",
        "The Nevada WIC Policy & Procedure Manual page on the agency site (nevadawic.org, Staff > Policy and Procedures) is "
        "password-protected ('This content is password-protected. To view it, please enter the password below.'), so the manual index "
        "cannot be read; individual policy PDFs exist under wp-content/uploads but no public index lists them. Replacement for a "
        "blocked batch-3 state.",
    ),
    "us-ar": (
        "Arkansas Department of Health",
        "https://healthy.arkansas.gov/programs-services/community-family-child-health/wic-women-infants-children/",
        "healthy.arkansas.gov answers HTTP 403 (Cloudflare) to the first probe of the WIC page for the plain client and one curl_cffi "
        "chrome124 impersonation attempt (20 s timeouts), so no manual index could be read from the publisher. Replacement for a "
        "blocked batch-3 state. No mirror was used.",
    ),
    "us-ms": (
        "Mississippi State Department of Health",
        "https://msdh.ms.gov/page/41,0,128,1081.html",
        "The MSDH WIC Policy and Procedure Manual is not published on msdh.ms.gov: the WIC Local Agencies page says sites must operate "
        "under the manual but links only the local-agency application and site-requirements PDFs, and the WIC program pages link no "
        "manual. Replacement for a blocked batch-3 state.",
    ),
    "us-ks": (
        "Kansas Department of Health and Environment",
        "https://www.kdhe.ks.gov/1149/Information-for-WIC-Local-Agencies",
        "www.kdhe.ks.gov answered HTTP 403 (Cloudflare) in batch 3. Retried 2026-09-10T21:34Z from a US network: the host now answers 200 and "
        "the For Local WIC Agencies page links the Policy & Procedure Manual folder (DocumentCenter/Index/903), but that page is an empty React "
        "shell whose document list is fetched from an admin-area endpoint (Admin/DocumentCenter/.../Document_AjaxBinding); the endpoint returned "
        "the site HTML to the plain client and, after five requests, a Cloudflare 'Just a moment' HTTP 429 challenge, which was not worked "
        "around. The manual policies demonstrably exist on the host (DocumentCenter/View/<id>/<POLICY>-PDF) but no static index lists them. "
        "No mirror was used.",
    ),
    "us-nm": (
        "New Mexico Department of Health, New Mexico WIC",
        "https://www.nmwic.org/nm-wic-staff/policy-procedures/",
        "The NM WIC Policies & Procedures page on the agency site (nmwic.org) lists the manual's series headings (100 Introduction "
        "through 1400 Vendor Management, Appendices, Peer Counselor Policies) but links no documents under them; the only links in that "
        "section point at the department intranet (http://chilenet/...). The manual is not published. Replacement for a blocked "
        "batch-3 state.",
    ),
    # fourth batch (retry): next not-yet-attempted states by population
    "us-ne": (
        "Nebraska Department of Health and Human Services",
        "https://dhhs.ne.gov/Pages/WIC-Policies-and-Procedures.aspx",
        "The Nebraska WIC policy manual is not published on dhhs.ne.gov: the Local Agency Staff page's 'Policies, Procedures & Forms' "
        "page lists three policy memos (hospital certification, Afghan refugees, eWIC Journey use), budget templates, forms and two "
        "vendor letter templates from a 'WIC Procedure Manuals' folder, but no manual index or chapter PDFs.",
    ),
    "us-id": (
        "Idaho Department of Health and Welfare",
        "https://healthandwelfare.idaho.gov/services-programs/food-assistance/about-wic",
        "The Idaho WIC Program Policy Manual is not published on healthandwelfare.idaho.gov: the batch-2-era WIC URLs (services-programs/"
        "food-assistance/wic, .../children-families/women-infants-and-children-wic, /wic, providers/wic) all answer 404, and the current "
        "About WIC page links only the vendor page and the public health districts; no page lists a manual.",
    ),
    "us-hi": (
        "Hawaii Department of Health, WIC Services Branch",
        "https://health.hawaii.gov/wic/wic-la-information/",
        "The Hawaii WIC policy and procedure manual is not published on health.hawaii.gov: the 'Information for WIC Local Agencies' page "
        "links only the federal and state cost-principles documents, the WIC Nutrition Services Standards and FNS Instruction 113-1; "
        "no page lists a manual.",
    ),
    "us-nh": (
        "New Hampshire Department of Health and Human Services",
        "https://www.dhhs.nh.gov/programs-services/health-care/nutrition-services/wic",
        "www.dhhs.nh.gov answers HTTP 403 to the plain client with a browser User-Agent for the WIC page and for the site root (first probe, "
        "2026-09-10T21:47Z from a US network); one curl_cffi chrome120 impersonation of the WIC URL answers 404, so the page has also moved "
        "and no manual index could be read from the publisher. No mirror was used.",
    ),
    "us-mt": (
        "Montana Department of Public Health and Human Services, WIC Program",
        "https://dphhs.mt.gov/ecfsd/wic/wicstateplan",
        "Montana publishes no separate WIC policy manual: the WIC page's 'State Plan Program Policies' link is the 2026 Montana WIC State Plan "
        "page (section drawers with State Plan attachments under assets/ecfsd/WIC/StatePlan/), which is the state-plan document family, not "
        "a policy/procedure manual index.",
    ),
    "us-de": (
        "Delaware Division of Public Health, WIC Program",
        "https://www.dhss.delaware.gov/dhss/dph/chs/wichome.html",
        "www.dhss.delaware.gov answers HTTP 403 to the plain client with a browser User-Agent for the WIC home page and the site root (first "
        "probe, 2026-09-10T21:47Z from a US network); one curl_cffi chrome120 impersonation fails TLS verification ('self signed certificate "
        "in certificate chain'), which was not disabled. No manual index could be read from the publisher. No mirror was used.",
    ),
    "us-sd": (
        "South Dakota Department of Health, WIC Program",
        "https://doh.sd.gov/programs/wic/",
        "The South Dakota WIC policy manual is not published on doh.sd.gov: the WIC program page links only the sd.gov/wic participant "
        "portal (approved foods, eligibility, news), the Family Nutrition Services page and the grocery-store lookup; no page lists a manual.",
    ),
    "us-ak": (
        "Alaska Department of Health, Division of Public Assistance, WIC Program",
        "https://health.alaska.gov/en/services/division-of-public-assistance-dpa-services/wic/",
        "The Alaska WIC policy manual is not published on health.alaska.gov: the WIC program page (the legacy dpa/Pages/nutri/wic/default.aspx "
        "URL redirects to it; first probe 2026-09-10T22:58Z from a US network, HTTP 200 to the plain client) links applications, vendor "
        "newsletters, WIC Vendor Forms, WIC Approved Foods, WIC Clinics by Region, the Farmers Market program and the WIC Vendor Management "
        "page; that page links 'WIC Authorized Vendors' only to the learn.dhss.alaska.gov login and lists no manual; the Nutrition topic page "
        "lists none; the legacy manual.aspx and policy.aspx paths and an /en/resources/wic-policy-and-procedure-manual/ guess answer 404. "
        "No page lists a policy manual or a local-agency section.",
    ),
    "us-nd": (
        "North Dakota Health and Human Services, WIC Program",
        "https://www.hhs.nd.gov/food-programs/WIC",
        "The North Dakota WIC policy manual is not published on hhs.nd.gov: the WIC program page (reached via www.hhs.nd.gov/wic; the "
        "health/wic, health/family-health/wic and health/nutrition/wic paths answer 404; first probe 2026-09-10T22:58Z from a US network) "
        "and its sub-pages (Common Questions, Apply, Eligible, Pick-WIC Paper, About, Free Food, Appointment, eWIC for Families, eWIC for "
        "Stores, New Participant Training, Referrals, Breastfeeding Resources) are participant- and store-facing; eWIC for Stores links one "
        "PDF (approved infant formula suppliers) and the site search for 'WIC policy manual' returns only those pages. No page lists a "
        "manual or a local-agency section.",
    ),
    "us-vt": (
        "Vermont Department of Health, WIC Program",
        "https://www.healthvermont.gov/family/wic",
        "The Vermont WIC policy manual is not published on healthvermont.gov: the WIC section (first probe 2026-09-10T22:58Z from a US "
        "network) has fourteen sub-pages (Apply, Check Your Balance, Information for Grocers, Resources for Health Professionals, Shopping, "
        "Basics, Breastfeeding, Community Resources, Discounts, Eligibility, Nutrition, Plans & Reports, Remote Appointments, Rights & "
        "Concerns) and none is a policy or local-agency page; Plans & Reports links the '2025 State Plan Goals and Objectives' PDF (WIC "
        "State Plan, a different document family; MT precedent) and data reports; Information for Grocers links the Vermont WIC Grocer "
        "Handbook and vendor forms (vendor family); the site search for 'WIC policy manual' returns only those pages.",
    ),
    "us-wy": (
        "Wyoming Department of Health, WIC Program",
        "https://health.wyo.gov/publichealth/wic/",
        "The Wyoming WIC policy manual is not published on health.wyo.gov: the WIC program page (first probe 2026-09-10T22:58Z from a US "
        "network) and its sub-pages (Learn About WIC, Apply, Clinic Locator, Appointment FAQ, Medical Documentation, Forms & Documents, "
        "Breastfeeding Support, Nutrition Education, Food Shopping Guide, Where Can I Shop, Yearly Savings, Vendor Services, Complaints and "
        "Fraud) list no policy manual or local-agency section; Vendor Services links a 'Vendor Manual', minimum stocking requirements and a "
        "price survey as Google Docs (vendor family, not the program policy manual); the site search for 'WIC policy manual' returns only "
        "the program page.",
    ),
}

# Territories (2026-09-11 pass; first probes 2026-09-11T21:15Z from a US network, one plain request each with a
# browser User-Agent; nothing was worked around). None of the five WIC State agencies publishes a policy manual.
TERRITORY_BLOCKED = {
    "us-pr": (
        "Puerto Rico Department of Health, WIC Program",
        "https://wic.pr.gov/",
        "The Puerto Rico WIC policy manual is not published on wic.pr.gov (HTTP 200): the site is a single-page Angular "
        "application whose server response is the app-root shell with no document links or text, and the Department of "
        "Health site www.salud.pr.gov lists no WIC manual; the client-side application was not driven. No mirror was used.",
    ),
    "us-gu": (
        "Guam Department of Public Health and Social Services, WIC Program",
        "https://dphss.guam.gov/dphss-programs/women-infants-children-wic-program",
        "The Guam WIC policy manual is not published on dphss.guam.gov (HTTP 200): the WIC program page and the WIC "
        "services page are text-only program descriptions with no document links (0 PDFs), and the only WIC PDF located "
        "on the host is the 2024-2025 income eligibility guidelines in the retired wp-content path. No page lists a manual.",
    ),
    "us-vi": (
        "Virgin Islands Department of Health, WIC Program",
        "https://doh.vi.gov/programs/women-infants-and-children/more-wic-information/",
        "The Virgin Islands WIC policy manual is not published on doh.vi.gov (HTTP 200): the More WIC Information page "
        "lists nine participant PDFs (eligibility checklist, medical referral and formula prescription forms, mobile-app "
        "sheet, rights and responsibilities forms in English and Spanish, eWIC card guides, brochure) and the department's "
        "news item opens the FY 2027 WIC State Plan of Operations for public comment (state-plan family, MT precedent); "
        "no page lists a manual or local-agency section.",
    ),
    "us-as": (
        "American Samoa Department of Human and Social Services, WIC Program",
        "https://aswic.com/",
        "The American Samoa WIC policy manual is not published: the program site aswic.com (the address FNA's WIC "
        "contact page gives for the agency; HTTP 200) carries program descriptions, clinic information and the USDA "
        "complaint form only; the department site www.dhss.as presents a self-signed, expired certificate (verification "
        "not disabled; curl 60 plain and curl_cffi chrome120) and its plain-HTTP ASWIC menu entry is the 'coming.html' "
        "placeholder. No page lists a manual.",
    ),
    "us-mp": (
        "Commonwealth Healthcare Corporation, CNMI WIC Program",
        "https://www.chcc.health/cnmi-wic.php",
        "The CNMI WIC policy manual is not published on chcc.health (HTTP 200): the CNMI WIC page lists referral, "
        "medical-documentation and employment-verification forms, the WIC food list booklet and two National WIC "
        "Association handouts (7 PDFs); no manual or local-agency section.",
    ),
}
BLOCKED.update(TERRITORY_BLOCKED)

STATE_NAMES = {"us-ca": "California", "us-tx": "Texas", "us-fl": "Florida", "us-ny": "New York", "us-pa": "Pennsylvania",
               "us-il": "Illinois", "us-oh": "Ohio", "us-ga": "Georgia", "us-nc": "North Carolina", "us-mi": "Michigan",
               "us-nj": "New Jersey", "us-va": "Virginia", "us-wa": "Washington", "us-az": "Arizona", "us-tn": "Tennessee",
               "us-ma": "Massachusetts", "us-in": "Indiana", "us-md": "Maryland", "us-mo": "Missouri", "us-wi": "Wisconsin",
               "us-co": "Colorado", "us-mn": "Minnesota", "us-sc": "South Carolina", "us-al": "Alabama", "us-la": "Louisiana",
               "us-ky": "Kentucky", "us-or": "Oregon", "us-ok": "Oklahoma", "us-ct": "Connecticut", "us-ut": "Utah",
               "us-ia": "Iowa", "us-nv": "Nevada", "us-ar": "Arkansas", "us-ms": "Mississippi", "us-ks": "Kansas", "us-nm": "New Mexico",
               "us-ne": "Nebraska", "us-wv": "West Virginia", "us-id": "Idaho", "us-hi": "Hawaii", "us-nh": "New Hampshire",
               "us-me": "Maine", "us-mt": "Montana", "us-ri": "Rhode Island", "us-de": "Delaware", "us-sd": "South Dakota",
               "us-ak": "Alaska", "us-dc": "District of Columbia", "us-nd": "North Dakota", "us-vt": "Vermont", "us-wy": "Wyoming",
               "us-pr": "Puerto Rico", "us-gu": "Guam", "us-vi": "Virgin Islands", "us-as": "American Samoa",
               "us-mp": "Northern Mariana Islands"}

BATCH_NOTE = {
    1: "Selected in the first batch as one of the ten largest states by population.",
    2: "Selected in the second batch as one of the next ten states by population (NJ, VA, WA, AZ, TN, MA, IN, MD, MO, WI).",
    3: "Selected in the third batch as one of the next ten states by population (CO, MN, SC, AL, LA, KY, OR, OK, CT, UT).",
    4: "Selected in the third batch as a replacement (in order IA, NV, AR, MS, KS, NM) for a blocked or non-publishing state.",
    5: "Selected in the fourth batch (retry) as one of the next ten not-yet-attempted states by population (NE, WV, ID, HI, NH, ME, MT, RI, DE, SD).",
    6: "Selected in the fifth batch as one of the last five jurisdictions without a queue row (AK, DC, ND, VT, WY).",
    7: "Selected in the territories pass (2026-09-11): the five inhabited territories PR, GU, VI, AS, MP.",
}
BATCH = dict.fromkeys(("us-ca", "us-tx", "us-fl", "us-ny", "us-pa", "us-il", "us-oh", "us-ga", "us-nc", "us-mi"), 1)
BATCH.update(dict.fromkeys(("us-nj", "us-va", "us-wa", "us-az", "us-tn", "us-ma", "us-in", "us-md", "us-mo", "us-wi"), 2))
BATCH.update(dict.fromkeys(("us-co", "us-mn", "us-sc", "us-al", "us-la", "us-ky", "us-or", "us-ok", "us-ct", "us-ut"), 3))
BATCH.update(dict.fromkeys(("us-ia", "us-nv", "us-ar", "us-ms", "us-ks", "us-nm"), 4))
BATCH.update(dict.fromkeys(("us-ne", "us-wv", "us-id", "us-hi", "us-nh", "us-me", "us-mt", "us-ri", "us-de", "us-sd"), 5))
BATCH.update(dict.fromkeys(("us-ak", "us-dc", "us-nd", "us-vt", "us-wy"), 6))
BATCH.update(dict.fromkeys(("us-pr", "us-gu", "us-vi", "us-as", "us-mp"), 7))

# Batch-1 blocked rows re-checked once during batch 2 (agency site only; nothing else was tried).
RECHECKED = {"us-ny": "2026-09-10T18:47Z", "us-fl": "2026-09-10T18:47Z", "us-il": "2026-09-10T18:47Z", "us-oh": "2026-09-10T18:47Z"}

# Batch-4 retry from a US network (2026-09-10T21:34Z first probe of every blocked row; not-published pages re-read 21:38Z).
RETRIED = {
    "us-ar": "retried 2026-09-10T21:34Z from US network, same failure (HTTP 403 Cloudflare for the WIC page and the site root).",
    "us-ma": "retried 2026-09-10T21:34Z from US network, same failure (HTTP 403 for the WIC organization page).",
    "us-il": "retried 2026-09-10T21:34Z from US network: www.dhs.state.il.us did not resolve (NameResolutionError, twice), so the page "
             "could not be re-read.",
    "us-oh": "re-probed 2026-09-10T21:38Z from US network: the Local Staff page and the Women-Infants-Children program page both answer "
             "404; still not published.",
    "us-mo": "re-probed 2026-09-10T21:38Z from US network: the manual URL still redirects to health.mo.gov/topic/781/login.",
    "us-nv": "re-probed 2026-09-10T21:38Z from US network: the Policy and Procedures page is still password-protected.",
    "us-nm": "re-probed 2026-09-10T21:38Z from US network: the Policies & Procedures page still links only the intranet.",
    **dict.fromkeys(("us-ny", "us-fl", "us-in", "us-wi", "us-al", "us-ok", "us-ms"),
                    "re-probed 2026-09-10T21:38Z from US network, still not published (page reachable, no manual link)."),
    # Batch-5 re-check of the two batch-4 access blocks (2026-09-10T23:00Z, US network; one plain request and one impersonation each).
    "us-az": "re-checked 2026-09-10T23:00Z from US network: the relocated Local Agencies page (prevention/azwic/agencies/index.php) still "
             "answers 200 (80,005 bytes) with the 'WIC Manuals' sidebar link to #manuals and no element with that id, to the plain client "
             "and to one curl_cffi chrome120 impersonation alike; same finding.",
    "us-de": "re-checked 2026-09-10T23:00Z from US network: www.dhss.delaware.gov still answers HTTP 403 ('Web App - Unavailable', 1,892 "
             "bytes) to the plain client for the WIC home page, and one curl_cffi chrome120 impersonation still fails TLS verification "
             "(curl 60: self signed certificate in certificate chain), which was not disabled; same failure.",
}

# inventory keys that annotate documents already counted in another family (or that are not documents at all)
INDEX_ANNOTATION_KEYS = {"vacant_chapter", "duplicate_link_same_file", "policy_pdf_labeled_by_title",
                         "header_number_differs_from_filename", "duplicate_policy_number",
                         # batch 3
                         "compiled_manual_links", "section_without_policies", "duplicate_policy_title",
                         "link_text_number_differs_from_filename", "chapters", "series_pages",
                         "functional_area_without_policies", "fy2027_state_plan_section_ii_draft_pdf_on_separate_page",
                         "image_only_pdf_ocr",
                         # batch 4 (retry)
                         "sections", "series", "duplicate_policy_code"}

STATE_BUILDERS = {
    "us-ca": lambda bundle: build_ca(bundle), "us-tx": lambda bundle: build_tx(), "us-ga": lambda bundle: build_ga(),
    "us-mi": lambda bundle: build_mi(), "us-pa": lambda bundle: build_pa(), "us-nc": lambda bundle: build_nc(),
    "us-va": lambda bundle: build_va(), "us-wa": lambda bundle: build_wa(), "us-md": lambda bundle: build_md(),
    "us-nj": lambda bundle: build_nj(),
    "us-co": lambda bundle: build_co(), "us-mn": lambda bundle: build_mn(), "us-ct": lambda bundle: build_ct(),
    "us-ut": lambda bundle: build_ut(), "us-ia": lambda bundle: build_ia(),
    "us-or": lambda bundle: build_or(), "us-ky": lambda bundle: build_ky(),
    "us-wv": lambda bundle: build_wv(), "us-me": lambda bundle: build_me(), "us-ri": lambda bundle: build_ri(),
    "us-dc": lambda bundle: build_dc(),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated jurisdictions to rebuild (us, us-xx); default rebuilds every row")
    args = parser.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None

    def selected(jur: str) -> bool:
        return only is None or jur in only

    bundle = ca_bundle()
    queue_path = ROOT / "manifests" / "wic-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}

    if selected("us"):
        manifest, count, inventory = build_federal()
        fed = rows["us"]
        fed.update({
            "queue_status": "agent_ready",
            "source_kind": "official_agency_guidance_pdf_and_federal_register_html",
            "primary_source_url": FNA_CANONICAL + "/wic/agency",
            "target_manifest": manifest,
            "target_scope": {"jurisdiction": "us", "document_class": "guidance", "version": FEDERAL_VERSION},
            "index_url": FNA_CANONICAL + "/resources?f[0]=program:32&f[1]=resource_type:160",
            "index_document_count": inventory["year_facets"].get("total"),
            "taken_count": count,
            "index_inventory": inventory,
            "notes": (
                "FNS became the Food and Nutrition Administration on 2026-06-01; www.fns.usda.gov and www.fna.usda.gov answer 403 "
                "to every client, so the index and memo pages were read from the publisher's origin host fns-prod.azureedge.us and "
                "the memo PDFs from the USDA guidance portal with browser impersonation. Taken: FY2025 memos #2025-1..#2025-5, "
                "FY2026 memos #2026-1, #2026-2, #2026-4, #2026-5 (no #2026-3 is listed), and the 2025-2026 and 2026-2027 Income "
                "Eligibility Guidelines Federal Register notices from govinfo. 7 CFR 246 is already in the corpus "
                "(data/corpus/provisions/us/regulation/2026-07-13-recovery-r2026-07-17-dedup.jsonl, 268 provisions under "
                "us/regulation/7/246) and was not re-ingested."
            ),
        })

    for jur, builder in STATE_BUILDERS.items():
        if not selected(jur):
            continue
        manifest, count, inventory = builder(bundle)
        row = rows.get(jur) or {"jurisdiction": jur, "name": STATE_NAMES[jur], "lead_counts": {}, "candidate_sources": []}
        partial = " Partial: only the vendor-management functional area of the manual is published." if jur == "us-nj" else ""
        row.update({
            "name": STATE_NAMES[jur],
            "queue_status": "agent_ready",
            "source_kind": "official_state_agency_manual_pdf_per_section",
            "primary_source_url": inventory["index_url"],
            "target_manifest": manifest,
            "target_scope": {"jurisdiction": jur, "document_class": "manual", "version": STATE_VERSION},
            "index_url": inventory["index_url"],
            "index_document_count": sum(
                len(v) if isinstance(v, list) else v
                for k, v in inventory.items() if k != "index_url" and k not in INDEX_ANNOTATION_KEYS
            ),
            "taken_count": count,
            "index_inventory": {k: v for k, v in inventory.items() if k != "index_url"},
            "notes": (
                "Current WIC policy manual confirmed on the state WIC agency's own index page; one document per policy/chapter "
                f"PDF listed there, single_block extraction.{partial} {BATCH_NOTE[BATCH[jur]]}"
            ),
        })
        rows[jur] = row
        print(f"{jur}: {count} documents -> {manifest}; index {inventory}")

    for jur, (agency_name, index_url, failure) in BLOCKED.items():
        if not selected(jur):
            continue
        row = rows.get(jur) or {"jurisdiction": jur, "name": STATE_NAMES[jur], "lead_counts": {}, "candidate_sources": []}
        recheck = f" re-checked {RECHECKED[jur]}, still not published." if jur in RECHECKED else ""
        recheck += f" {RETRIED[jur]}" if jur in RETRIED else ""
        row.update({
            "name": STATE_NAMES[jur],
            "queue_status": "blocked_primary_source",
            "source_kind": "official_state_agency_manual_not_published",
            "primary_source_url": None,
            "target_manifest": f"manifests/{jur}-wic-policy-manual.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": "manual", "version": None},
            "index_url": index_url,
            "index_document_count": 0,
            "taken_count": 0,
            "notes": f"{agency_name}: {failure} {BATCH_NOTE[BATCH[jur]]}{recheck}",
        })
        rows[jur] = row

    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue["queue_status"] = "in_progress"
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"federal: {rows['us']['taken_count']} documents; queue {queue['status_counts']}; ca bundle {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
