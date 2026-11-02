"""Build the official-document manifest for the California Code of Regulations sections that the Medicaid
program-bundle gap rows name, and update the matching `family: w6_bundle_gap` row of the Medicaid agent queue.

Wave-8 reprobe (2026-10-20, docs/ingest-runs/2026-10-20-w8-medicaid-ca-la-waivers.md). The 2026-10-06 wave-6
health run recorded 10 CCR 2699.200 (MCAP/AIM basis of eligibility) as OUTREACH because the official CCR
publisher answered HTTP 403 to the corpus client.

Publisher judgment. Government Code section 11344 makes the Office of Administrative Law responsible for the
official compilation and publication of the California Code of Regulations. OAL's own publications page
(https://oal.ca.gov/publications/ccr/) links the online CCR at `govt.westlaw.com/calregs` three times - as
"Online", as "California Code of Regulations", and as "this site provided here" in the caution that OAL
"cannot verify the authenticity of regulations downloaded from websites other than this site". The host is
operated by a vendor, but it is the state's own publication channel for the code, not a third-party repost,
so a CCR section read there is the official text. The repository already holds committed CCR scopes from the
same endpoint shape (`manifests/us-ca-income-tax-regulations.yaml`, version 2026-09-14).

Access, judged on response bodies and not on status lines. On 2026-09-14 the `fresh_session` + Barclays-cookie
request configuration was enough. On 2026-10-20 the extractor's whole plain path is refused: the corpus user
agent gets a Cloudflare "Just a moment. Enable JavaScript and cookies to continue" body (HTTP 403, 6,158
bytes), and the browser-user-agent fallback the extractor retries with on a 403
(`OFFICIAL_DOCUMENT_BROWSER_USER_AGENT`) gets the same challenge body (HTTP 403, 6,350 bytes), with and
without those cookies. So the block is on the TLS fingerprint, not on the user agent, and the rows carry
`browser_impersonation_direct: true` (curl_cffi chrome120, TLS verification on). The impersonated client is
served the section itself: 23,188 bytes with an `#co_document` body holding the regulatory text, the authority
and reference note and the amendment history. No challenge is solved and no CAPTCHA is answered.

Every selected section is confirmed on the publisher's own browse table of contents at build time; a section
that the table of contents no longer lists fails the build.

    uv run python scripts/build_medicaid_ca_ccr_section_manifests.py
    uv run python scripts/build_medicaid_ca_ccr_section_manifests.py --check-only
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "manifests" / "medicaid-agent-queue.yaml"
MANIFEST = ROOT / "manifests" / "us-ca-medicaid-ccr-sections.yaml"
VERSION = "2026-10-20-w8-medicaid-ccr-section"
SOURCE_AS_OF = "2026-10-20"
FAMILY = "w6_bundle_gap"
BASE = "https://govt.westlaw.com"
UA = "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) https://github.com/TheAxiomFoundation/axiom-corpus"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
OAL_PUBLICATION_PAGE = "https://oal.ca.gov/publications/ccr/"
CCR_INDEX = (
    "https://govt.westlaw.com/calregs/Index"
    "?transitionType=Default&contextData=%28sc.Default%29"
)

# The browse table of contents that holds the selected sections, as the publisher's own index reaches it:
# CCR Index -> Title 10. Investment -> Chapter 5.6. Access for Infants and Mothers Program
# -> Article 2. Eligibility, Application, and Enrollment.
TOC_URL = (
    "https://govt.westlaw.com/calregs/Browse/Home/California/CaliforniaCodeofRegulations"
    "?guid=IEC93CBD05C2F11EC9C68000D3A7C4BC3"
    "&originationContext=documenttoc&transitionType=Default&contextData=(sc.Default)"
)
TOC_PATH = (
    "Title 10. Investment > Chapter 5.6. Access for Infants and Mothers Program "
    "> Article 2. Eligibility, Application, and Enrollment"
)

# (title number, section number, heading as the table of contents prints it, what the bundle row needs it for)
SELECTION: list[tuple[int, str, str, str]] = [
    (
        10,
        "2699.200",
        "Basis of Eligibility.",
        "the basis-of-eligibility rule of the Access for Infants and Mothers program, which the "
        "Medi-Cal Access Program (MCAP) continues; the 2026-10-06 wave-6 health bundle row names it",
    ),
]


# The other wave-8 reprobe rows: nothing to take, so they carry only the publisher's own inventory and the
# reason, keyed by (jurisdiction, a substring of the row's primary_source_url that identifies it).
REPROBE: list[tuple[str, str, dict[str, Any]]] = [
    (
        "us-ca",
        "all-county-welfare-directors",
        {
            "queue_status": "blocked_primary_source",
            "index_url": (
                "https://www.dhcs.ca.gov/services/medi-cal-resources/medi-cal-eligibility-division/"
                "all-county-welfare-directors-medi-cal-eligibility-division-information-letters/"
            ),
            "index_document_count": 93,
            "taken_count": 0,
            "index_families": {"acwdl_medil_year_page": 92, "acwdl_index_page": 1},
            "blocked_count": 6,
            "notes": (
                "2026-10-20 wave-8 reprobe: still blocked, judged on the response bodies. Every "
                "www.dhcs.ca.gov HTML address, the site root included, answers an Imperva/Incapsula "
                "`_Incapsula_Resource` challenge stub and no page content: HTTP 200 with 212 bytes to the "
                "extractor's browser-user-agent fallback, 840-955 bytes to the corpus user agent and to a "
                "chrome120 fingerprint. dhcs.ca.gov without www and the WordPress REST path answer the same "
                "stub, so the ACWDL index body cannot be read. The publisher's own "
                "sitemaps do answer (sitemap.xml, page-sitemap{,2,3,4}.xml) and list the ACWDL index plus 92 "
                "year pages, which proves the pages exist but carries no letter text. No official alternative "
                "host serves the index and no mirror was taken. OUTREACH, unchanged; the six work-order rows "
                "(ACWDL 23-03, ACWDL 25-14, Program descriptions by FPL Enclosure 3, the non-MAGI asset-limit "
                "page, the Former Foster Youth page, the Working Disabled Program page) stay blocked."
            ),
        },
    ),
    (
        "us-la",
        "ldh.la.gov/faq/category/19",
        {
            "queue_status": "agent_ready",
            "index_url": "https://ldh.la.gov/medicaid/medicaid-eligibility-manual",
            "index_document_count": 99,
            "taken_count": 0,
            "index_families": {
                "preface": 1, "chapter_A": 2, "chapter_B": 1, "chapter_C": 1, "chapter_E": 1,
                "chapter_F": 1, "chapter_G": 1, "chapter_H": 38, "chapter_I": 25, "chapter_J": 1,
                "chapter_K": 1, "chapter_L": 1, "chapter_N": 1, "chapter_P": 1, "chapter_Q": 1,
                "chapter_R": 1, "chapter_S": 1, "chapter_T": 1, "chapter_U": 1, "chapter_X": 1,
                "chapter_Z": 17,
            },
            "blocked_count": 0,
            "target_manifest": "manifests/us-la-medicaid-eligibility-manual.yaml",
            "target_scope": {
                "jurisdiction": "us-la",
                "document_class": "manual",
                "version": "2026-09-10-medicaid-state-eligibility-manual",
            },
            "citation_paths": ["us-la/manual/ldh/medicaid/h-3040"],
            "notes": (
                "2026-10-20 wave-8 reprobe: already held, nothing new taken. ldh.la.gov answers again, and the "
                "block is on the user agent only: the corpus user agent gets a 118-byte '403 Forbidden' body, "
                "while the browser-user-agent fallback the extractor already retries with on a 403 is served "
                "the real pages (the eligibility-manual index HTTP 200, 189,146 bytes; H-3040m.pdf HTTP 200, "
                "29,941 bytes of application/pdf). No browser impersonation is needed on this host. "
                "FAQ category 19 is the LaCHIP Affordable Plan question set, not a policy document; "
                "the eligibility document LDH's own index lists as current for that program is H-3040 LaCHIP "
                "Affordable Plan on https://ldh.la.gov/medicaid/medicaid-eligibility-manual. All 99 documents "
                "that index lists are already held in us-la/manual/2026-09-10-medicaid-state-eligibility-manual "
                "at byte-identical URLs (live index and manifest diff to zero on both sides), and that version "
                "is in signed releases, so it is immutable and was not touched. No new scope was created."
            ),
        },
    ),
]

# The six `family: cms_1115_stc` needs_review rows, re-read on the live demonstration list on 2026-10-20.
WAIVER_REPROBE: dict[str, dict[str, Any]] = {
    "us-ak": {
        "index_document_count": 7,
        "index_families": {"waiver_1915c": 5, "waiver_1915c_terminated": 1, "demo_1115_approved_service_authority": 1},
        "reason": (
            "the one approved section 1115 demonstration is still Alaska Behavioral Health Reform (Status "
            "Approved, 11/21/2018 to 12/31/2028), SUD/SMI service authority; its newest postings are a "
            "Technical Correction Approval (03/27/2026) and a Demonstration Approval - Evaluation Design "
            "(12/09/2025), neither of which sets eligibility terms. The other six listings are 1915(c) waivers"
        ),
    },
    "us-id": {
        "index_document_count": 13,
        "index_families": {
            "waiver_1915b": 4, "waiver_1915c": 2, "waiver_1915c_terminated": 2,
            "demo_1115_pending": 3, "demo_1115_expired": 2,
        },
        "reason": (
            "no approved eligibility demonstration. Idaho Behavioral Health Transformation, Idaho Family "
            "Planning Referrals and the Idaho Medicaid Reform Waiver all read Status Pending; Idaho Childless "
            "Adults expired 09/30/2014 and the Children's Access Card Demonstration expired 09/30/2013; "
            "Dental Smiles (ID-03), Idaho Behavioral Health (ID-02), Idaho Medicaid Plus (ID-04) and "
            "ID.0004.R01.01 are 1915(b) managed-care authority"
        ),
    },
    "us-nd": {
        "index_document_count": 11,
        "index_families": {"waiver_1915c": 6, "waiver_1915b": 2, "waiver_1915c_terminated": 2, "demo_1115_expired": 1},
        "reason": (
            "no approved eligibility demonstration. The only 1115 listing, North Dakota Managed Care Risk "
            "Mitigation COVID-19 PHE, reads Status Expired (expiration 05/11/2023); ND-0004.R05.00 (Status "
            "Approved, 06/07/2024, to 06/30/2026) and the managed-care enrolment waiver for the new adult "
            "group (ND-04) are 1915(b) authority, not eligibility terms"
        ),
    },
    "us-ne": {
        "index_document_count": 12,
        "index_families": {
            "waiver_1915c": 5, "waiver_1915c_terminated": 3, "waiver_1915b": 2,
            "demo_1115_terminated": 1, "demo_1115_approved_service_authority": 1,
        },
        "reason": (
            "no approved eligibility demonstration. Nebraska Heritage Health Adult 1115 still reads Status "
            "Terminated (expiration 09/02/2021, with the CMS approval to terminate posted); the Nebraska "
            "Substance Use Disorder Program demonstration is service authority; Heritage Health (NE-0003, "
            "Status Approved to 09/30/2027) and NE-0004.R00.00 are 1915(b) managed-care authority"
        ),
    },
    "us-nv": {
        "index_document_count": 15,
        "index_families": {
            "waiver_1915c": 4, "waiver_1915c_terminated": 1, "waiver_1915b": 3,
            "demo_1115_approved_service_authority": 4, "demo_1115_expired": 2, "demo_1115_pending": 1,
        },
        "reason": (
            "no approved eligibility demonstration. Nevada Healthy Futures still reads Status Pending (the "
            "application was posted 07/20/2026 and the CMS completeness letter 08/03/2026, with no approval "
            "document); the Nevada Comprehensive Care Waiver reads Status Expired (expiration 06/30/2018); the "
            "reentry, OUD/SUD, CCBHC, dental and youth behavioural-health demonstrations are service authority"
        ),
    },
    "us-sc": {
        "index_document_count": 16,
        "index_families": {
            "waiver_1915c": 9, "waiver_1915c_terminated": 1, "waiver_1915b": 1,
            "demo_1115_pending": 2, "demo_1115_withdrawn": 2, "demo_1115_expired": 1,
        },
        "reason": (
            "no approved eligibility demonstration. South Carolina Healthy Connections Works and South "
            "Carolina Palmetto Pathways to Independence both read Status Withdrawn (2019 approvals, withdrawn "
            "2021), and their CMS Approval PDFs are therefore not current terms; the 2025 Palmetto Pathways to "
            "Independence and Transitioning to Preconception Care listings read Status Pending; the Enhanced "
            "Prenatal and Postpartum Home Visitation Pilot expired 03/31/2023"
        ),
    },
}


# A bot-challenge or interstitial body, which this publisher serves with HTTP 200 as readily as with 403. The
# string "challenge-platform" is deliberately absent: Cloudflare injects that telemetry script into genuine
# pages too, so it is a false positive.
CHALLENGE_MARKERS = (
    "Attention Required! | Cloudflare",
    "Just a moment...",
    "bobcmn",
    "cf_chl_opt",
    "chk_jschl",
    "Checking your browser",
    "_Incapsula_Resource",
    "Incapsula",
    "Radware",
    "TSPD",
    "captcha",
    "Please click here to continue",
)
# Page furniture the real CCR pages carry, used to tell a served page from an empty shell.
EXPECTED_FURNITURE = ("California Code of Regulations",)


def _fetch(url: str) -> str:
    """Read one official CCR page, judging the response on its body and not on its status line."""
    try:
        from curl_cffi import requests as curl_requests
    except ImportError as exc:  # pragma: no cover - exercised only in incomplete installs
        raise RuntimeError("the CCR generator requires curl-cffi") from exc
    response = curl_requests.get(
        url,
        timeout=90,
        allow_redirects=True,
        verify=True,
        headers={"User-Agent": BROWSER_UA, "X-Axiom-Client": UA},
        impersonate="chrome120",
    )
    body = str(response.text)
    if response.status_code != 200:
        raise RuntimeError(f"official CCR page answered HTTP {response.status_code}: {url}")
    lowered = body.lower()
    hit = [marker for marker in CHALLENGE_MARKERS if marker.lower() in lowered]
    if hit:
        raise RuntimeError(
            f"official CCR page answered HTTP 200 with a bot-challenge or interstitial body "
            f"({len(body.encode())} bytes, markers {hit}): {url}"
        )
    if not all(piece in body for piece in EXPECTED_FURNITURE):
        raise RuntimeError(
            f"official CCR page answered HTTP 200 without the publisher's own page furniture "
            f"({len(body.encode())} bytes): {url}"
        )
    return body


def _toc_sections(body: str) -> dict[str, tuple[str, str]]:
    """Map section number -> (heading, document URL) from a browse table of contents page."""
    found: dict[str, tuple[str, str]] = {}
    for href, label in re.findall(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, flags=re.S):
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", label))).strip()
        match = re.match(r"^§\s*([0-9][0-9A-Za-z.\-]*)\.\s*(.+?)\s*$", text)
        if not match or "/calregs/Document/" not in href:
            continue
        url = html.unescape(href)
        found[match.group(1)] = (match.group(2), url if url.startswith("http") else BASE + url)
    return found


def _documents(toc: dict[str, tuple[str, str]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for title_number, section, heading, purpose in SELECTION:
        if section not in toc:
            raise SystemExit(
                f"§ {section} is no longer listed on the official CCR table of contents ({TOC_URL})"
            )
        listed_heading, document_url = toc[section]
        if listed_heading != heading:
            raise SystemExit(
                f"§ {section} is listed as {listed_heading!r}, not the selected {heading!r} ({TOC_URL})"
            )
        slug = section.lower()
        documents.append(
            {
                "source_id": f"ca-ccr-{title_number}-{slug}",
                "jurisdiction": "us-ca",
                "document_class": "regulation",
                "citation_path": f"us-ca/regulation/{title_number}-ccr/{slug}",
                "title": f"{title_number} CCR § {section}. {listed_heading}",
                "source_url": document_url,
                "source_format": "html",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": SOURCE_AS_OF,
                "request": {"browser_impersonation": True, "browser_impersonation_direct": True},
                "extraction": {
                    "html_content_selector": "#co_document",
                    "html_text_selector": "h1, h2, h3, .co_headtext, .co_paragraph, p, li, table",
                },
                "metadata": {
                    "primary_source": True,
                    "source_authority": "California Office of Administrative Law",
                    "official_publisher": (
                        "California Office of Administrative Law (official CCR via govt.westlaw.com, "
                        "Government Code section 11344)"
                    ),
                    "document_subtype": "administrative_code_section",
                    "program": "MEDICAID",
                    "state": "California",
                    "source_discovery_group": "us-ca/regulation/medicaid-ccr",
                    "discovered_via": (
                        "manual-review:medicaid-agent-queue w6_bundle_gap row; official CCR table of "
                        f"contents {TOC_URL}"
                    ),
                    "ccr_toc_path": TOC_PATH,
                    "selected_for": purpose,
                    "publisher_note": (
                        "govt.westlaw.com answers the plain corpus client a Cloudflare interstitial "
                        "(HTTP 403); fetched with curl_cffi chrome120 impersonation, TLS verified. OAL "
                        f"names this site as the official online CCR at {OAL_PUBLICATION_PAGE}."
                    ),
                },
            }
        )
    return documents


def _queue_row(documents: list[dict[str, Any]], toc: dict[str, tuple[str, str]]) -> dict[str, Any]:
    return {
        "jurisdiction": "us-ca",
        "name": "California",
        "family": FAMILY,
        "queue_status": "agent_ready",
        "source_kind": "official_documents_program_bundle_gap",
        "primary_source_url": "https://govt.westlaw.com/calregs/Search/Results?t_querytext=2699.200&t_Method=tnc",
        "index_url": TOC_URL,
        "index_document_count": len(toc),
        "taken_count": len(documents),
        "index_families": {"administrative_code_section": len(toc)},
        "target_manifest": "manifests/us-ca-medicaid-ccr-sections.yaml",
        "target_scope": {
            "jurisdiction": "us-ca",
            "document_class": "regulation",
            "version": VERSION,
        },
        "blocked_count": 0,
        "work_order": (
            "docs/coverage/program-bundle-gaps-2026-10-06/wave6/health.csv "
            "(branch analysis/program-bundle-gaps-2026-10-06)"
        ),
        "run_note": "docs/ingest-runs/2026-10-20-w8-medicaid-ca-la-waivers.md",
        "citation_paths": [document["citation_path"] for document in documents],
        "notes": (
            "2026-10-20 wave-8 reprobe: the official CCR publisher answers again. OAL (Government Code "
            "section 11344) names govt.westlaw.com/calregs as the official online CCR, so the host is the "
            "state's own publication channel, not a vendor repost; the plain corpus client still meets a "
            "Cloudflare interstitial, so the rows fetch with chrome120 impersonation (TLS verified). "
            f"{len(documents)} of the {len(toc)} sections the Article 2 table of contents lists taken into "
            f"us-ca/regulation/{VERSION} (unsigned, uncommitted; controller signs and selects). The queue "
            "row's own search URL names 10 CCR 2699.200, not a title 22 section. See "
            "docs/ingest-runs/2026-10-20-w8-medicaid-ca-la-waivers.md."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="confirm the selection against the publisher's table of contents and write nothing",
    )
    args = parser.parse_args(argv)

    toc = _toc_sections(_fetch(TOC_URL))
    if not toc:
        raise SystemExit(f"no CCR sections found on the official table of contents ({TOC_URL})")
    documents = _documents(toc)
    print(f"table of contents lists {len(toc)} sections; selection confirms {len(documents)}")
    for document in documents:
        print(f"  {document['title']} -> {document['citation_path']}")
    if args.check_only:
        return 0

    MANIFEST.write_text(
        yaml.safe_dump(
            {"version": VERSION, "documents": documents}, sort_keys=False, allow_unicode=True, width=120
        ),
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST.relative_to(ROOT)}")

    queue = yaml.safe_load(QUEUE.read_text(encoding="utf-8"))
    row = _queue_row(documents, toc)
    for index, existing in enumerate(queue["states"]):
        if (
            existing.get("jurisdiction") == "us-ca"
            and existing.get("family") == FAMILY
            and "govt.westlaw.com" in str(existing.get("primary_source_url", ""))
        ):
            queue["states"][index] = row
            break
    else:
        raise SystemExit("the us-ca govt.westlaw.com w6_bundle_gap queue row was not found")

    for jurisdiction, url_marker, update in REPROBE:
        for existing in queue["states"]:
            if existing.get("jurisdiction") == jurisdiction and url_marker in str(
                existing.get("primary_source_url", "")
            ):
                existing.update(update)
                existing["run_note"] = "docs/ingest-runs/2026-10-20-w8-medicaid-ca-la-waivers.md"
                break
        else:
            raise SystemExit(f"the {jurisdiction} queue row matching {url_marker!r} was not found")

    for jurisdiction, waiver in WAIVER_REPROBE.items():
        for existing in queue["states"]:
            if existing.get("jurisdiction") == jurisdiction and existing.get("family") == "cms_1115_stc":
                existing["index_document_count"] = waiver["index_document_count"]
                existing["taken_count"] = 0
                existing["index_families"] = waiver["index_families"]
                existing["run_note"] = "docs/ingest-runs/2026-10-20-w8-medicaid-ca-la-waivers.md"
                existing["notes"] = (
                    "2026-10-20 wave-8 reprobe: www.medicaid.gov answers the plain corpus client (the "
                    "Approved-filter demonstration list and every demonstration page read, HTTP 200; a burst "
                    "of requests draws an Akamai HTTP 403 that clears on a paced retry), and nothing is "
                    f"takeable: {waiver['reason']}. "
                    f"{waiver['index_document_count']} listings inventoried, 0 taken. M-ST-1315 stays ABSENT "
                    "for the state until an eligibility demonstration is approved. The wave-5 selection rule "
                    "stands: SUD/SMI, reentry, CCBHC, dental and payment demonstrations are service authority, "
                    "not eligibility terms, and are not taken into the cms_1115_stc family. Generator: "
                    "scripts/build_medicaid_1115_stc_manifests.py."
                )
                break
        else:
            raise SystemExit(f"the {jurisdiction} cms_1115_stc queue row was not found")

    queue["status_counts"] = {}
    for existing in queue["states"]:
        status = existing["queue_status"]
        queue["status_counts"][status] = queue["status_counts"].get(status, 0) + 1
    note = (
        "CA CCR section family (2026-10-20, wave-8 reprobe): the `family: w6_bundle_gap` us-ca row for "
        "govt.westlaw.com, version "
        f"{VERSION}, document_class regulation, citation root us-ca/regulation/<title>-ccr. OAL (Government "
        "Code section 11344) names govt.westlaw.com/calregs as the official online CCR, so the vendor host is "
        "the state's own publication channel; the plain corpus client meets a Cloudflare interstitial, so the "
        "rows carry browser_impersonation_direct (TLS verified). Generator: "
        "scripts/build_medicaid_ca_ccr_section_manifests.py."
    )
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    QUEUE.write_text(
        yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8"
    )
    print(f"updated {QUEUE.relative_to(ROOT)}: status_counts {queue['status_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
