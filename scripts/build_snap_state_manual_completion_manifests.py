"""Build the SNAP state-manual completion manifests (axiom-corpus#680, batch 1) and the
completion queue `manifests/snap-completion-agent-queue.yaml`.

Issue #680 splits the thin SNAP states into an ingestion gap (FL, AL, MD, MA: more documents
registered in manifests than "captured") and a discovery gap (TX, CA, NY, NH, KY, ME, ...:
little registered). Released SNAP scopes are immutable, so every document that is missing
from the corpus goes into a NEW scope per state:

    jurisdiction us-xx, document_class per the state's existing convention,
    version 2026-09-10-snap-state-manual-completion,
    manifest manifests/us-xx-snap-manual-completion.yaml.

Every document is confirmed from the publisher's own index, fetched live here so the manifest
reflects what the publisher lists today. Nothing is taken from mirrors, archives or compiled
lists, and a citation path that already exists in any provisions JSONL of the corpus
(`--corpus-base`) is skipped and recorded, because a release rejects duplicate citation paths.

    uv run python scripts/build_snap_state_manual_completion_manifests.py \
        --corpus-base /path/to/axiom-corpus/data/corpus          # both live builders
    uv run python scripts/build_snap_state_manual_completion_manifests.py --only us-tx

Live builders, batch 1: us-tx (Texas Works Handbook Parts A-C and glossary on fhb.hhs.texas.gov)
and us-nh (DHHS Food Stamp Manual WebHelp on www.dhhs.nh.gov). The other eight batch-1 states are
static rows: FL, AL, MD, MA (diagnosed, nothing failed to land), CA and ME (publisher index
confirmed complete), KY and NY (publisher blocked from the batch-1 network). See
docs/ingest-runs/2026-09-10-snap-state-manual-completion-batch-1.md.

Batch 2 (same day, from a US network): KY answered on retry and is a live builder (DFS Operation
Manual Volume I); NY stays blocked. Live builders us-wy (DFS SNAP and POWER Policy Manual
subpages) and us-nd (HHS SNAP Policy Manual topics and release updates added since Release 26.5);
static rows AZ (blocked), NE, AR, IA, HI, NM, VT, NV, ID (publisher index confirmed complete; the
findings, including revised editions that need a superseding scope, are in the row notes). See
docs/ingest-runs/2026-09-10-snap-state-manual-completion-batch-2.md. Batch-1 manifests are never
regenerated: run with ``--only us-ky --only us-wy --only us-nd`` for batch 2.

Batch 3 (2026-09-11, US network): the issue's last seven discovery-gap states NC, OH, MT, OK, GA,
TN and MI were diagnosed against the released scopes and confirmed on the publisher's own index, and
AZ and NY were re-probed once. Every index is already fully in the corpus, so batch 3 builds no
completion scope: all nine rows are static (NC, MT, OK, GA, TN, MI done with revised editions recorded
for superseding scopes; OH blocked for the eManuals manual family while OAC 5101:4 is complete; AZ and
NY still bot-challenged). Run with ``--static-only`` for batch 3 so no live builder runs and no
earlier manifest is regenerated. See
docs/ingest-runs/2026-09-10-snap-state-manual-completion-batch-3.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "manifests" / "snap-completion-agent-queue.yaml"
VERSION = "2026-09-10-snap-state-manual-completion"
SOURCE_AS_OF = dt.date.today().isoformat()
EXPRESSION_DATE = SOURCE_AS_OF  # current-effective manual trees as fetched; see run note
UA = "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) https://github.com/TheAxiomFoundation/axiom-corpus"
ISSUE = "https://github.com/TheAxiomFoundation/axiom-corpus/issues/680"
RUN_NOTE = "docs/ingest-runs/2026-09-10-snap-state-manual-completion-batch-1.md"
RUN_NOTE_BATCH2 = "docs/ingest-runs/2026-09-10-snap-state-manual-completion-batch-2.md"
RUN_NOTE_BATCH3 = "docs/ingest-runs/2026-09-10-snap-state-manual-completion-batch-3.md"

_LINK_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)


def fetch(url: str, *, session: requests.Session | None = None) -> str:
    """GET with TLS verification on; retry only transient connection errors."""
    client = session or requests
    for attempt in range(4):
        try:
            resp = client.get(url, headers={"User-Agent": UA}, timeout=60)
            resp.raise_for_status()
            return resp.text
        except requests.ConnectionError:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch_impersonated(url: str, *, timeout: int = 20) -> tuple[int, bytes]:
    """GET through curl-cffi browser impersonation (the existing manifest option
    `request: browser_impersonation: true`); TLS verification stays on."""
    from curl_cffi import requests as curl_requests

    resp = curl_requests.get(url, impersonate="chrome120", timeout=timeout)
    return resp.status_code, resp.content


def links(page: str, base: str) -> list[tuple[str, str]]:
    """Return (absolute href, text) pairs in document order, de-duplicated."""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for href, text in _LINK_RE.findall(page):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
        href = html.unescape(href).strip()
        absolute = urljoin(base, href).split("#", 1)[0]
        if (absolute, text) in seen:
            continue
        seen.add((absolute, text))
        out.append((absolute, text))
    return out


def slug(value: str, limit: int = 100) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:limit].strip("-")


def slug_full(value: str) -> str:
    """Untruncated slug (the released ND topic convention keeps the whole Content path)."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def registered_citation_paths(*manifests: str) -> set[str]:
    """Citation paths already registered in the named (released, immutable) manifests."""
    paths: set[str] = set()
    for name in manifests:
        payload = yaml.safe_load((ROOT / "manifests" / name).read_text())
        paths.update(str(d["citation_path"]) for d in payload.get("documents", []))
    return paths


def corpus_citation_paths(corpus_base: Path | None, jurisdiction: str) -> set[str]:
    """Every citation_path in every provisions JSONL of the jurisdiction (all document
    classes, all versions). Empty when no corpus base is available (sparse worktree)."""
    if corpus_base is None:
        return set()
    paths: set[str] = set()
    for jsonl in sorted((corpus_base / "provisions" / jurisdiction).glob("*/*.jsonl")):
        with jsonl.open() as handle:
            for line in handle:
                if line.strip():
                    paths.add(json.loads(line)["citation_path"])
    return paths


# --------------------------------------------------------------------------- Texas


def build_tx() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Texas Works Handbook (TWH) on fhb.hhs.texas.gov, the publisher's own handbook host
    (www.hhs.texas.gov/handbooks/texas-works-handbook redirects there).

    Pages carry either policy text (``article.c-article div.c-field--name-body``) or only a
    "Pages in this section" sub-menu (``.c-view--hb-submenus``); many carry both. Text-bearing
    pages become documents; menu-only pages are counted as landing pages. Parts A (Determining
    Eligibility), B (Case Management) and C (Appendix) govern SNAP alongside TANF and Medicaid
    and are taken with the TWH Glossary; Parts D-X are medical-program-only parts and are
    inventoried, not taken. Sections already in the released TX scopes keep their citation paths
    and are skipped (inventoried as ``twh_section_already_in_released_scope``).
    """
    from bs4 import BeautifulSoup

    host = "https://fhb.hhs.texas.gov"
    twh = host + "/handbooks/texas-works-handbook"
    manual = "Texas Works Handbook"
    existing = registered_citation_paths("us-tx-manuals.yaml", "us-tx-twh-c120-snap-deduction-amounts.yaml")
    session = requests.Session()
    families: dict[str, dict[str, int]] = {}
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    taken_parts = {"part-a-determining-eligibility": "a", "part-b-case-management": "b", "part-c-appendix": "c"}

    def document_for(url: str, title: str) -> dict[str, Any]:
        section = url.rsplit("/", 1)[-1]
        return {
            "source_id": f"tx-hhs-texas-works-{section}",
            "jurisdiction": "us-tx",
            "document_class": "manual",
            "citation_path": f"us-tx/manual/hhs/texas-works-handbook/{section}",
            "title": f"{manual}: {title}",
            "source_url": url,
            "source_format": "html",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": EXPRESSION_DATE,
            "extraction": {
                "html_content_selector": "article.c-article div.c-field--name-body",
                "html_drop_selectors": [".c-field__label"],
            },
            "metadata": {
                "primary_source": True,
                "source_authority": "Texas Health and Human Services Commission",
                "document_subtype": "handbook_section",
                "program": "SNAP",
                "state_program": "Texas Works (SNAP, TANF and Medicaid for children and families)",
                "federal_program": "SNAP",
                "manual": manual,
                "manual_landing_page": twh,
                "source_discovery_group": "us-tx/manual/snap",
                "discovered_via": f"manual-review:snap-completion-agent-queue batch 1 ({ISSUE}); publisher index {twh}",
            },
        }

    def crawl(start: str, *, part: str) -> None:
        fam = families.setdefault(f"twh_part_{part}_section_html", {"found": 0, "taken": 0})
        landing = families.setdefault(f"twh_part_{part}_section_landing_html", {"found": 0, "taken": 0})
        already = families.setdefault("twh_section_already_in_released_scope", {"found": 0, "taken": 0})
        label_re = re.compile(re.escape(twh) + rf"/({part}-\d{{3,4}})-")
        queue = [start]
        while queue:
            url = queue.pop(0)
            if url in seen or not url.startswith(twh + "/"):
                continue
            seen.add(url)
            soup = BeautifulSoup(fetch(url, session=session), "html.parser")
            heading = soup.select_one("h1.c-page-title")
            title = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)) if heading else url.rsplit("/", 1)[-1]
            children = [urljoin(url, str(a["href"])).split("#", 1)[0] for a in soup.select(".c-view--hb-submenus a[href]")]
            queue.extend(children)
            if url == start or label_re.match(url) is None:
                landing["found"] += 1
                continue
            if soup.select_one("article.c-article div.c-field--name-body") is None:
                landing["found"] += 1
                continue
            doc = document_for(url, title)
            if doc["citation_path"] in existing:
                already["found"] += 1
                continue
            fam["found"] += 1
            fam["taken"] += 1
            docs.append(doc)

    index_page = fetch(twh, session=session)
    parts = [(h, t) for h, t in links(index_page, twh) if h.startswith(twh + "/part-")]
    families["twh_part_landing_html"] = {"found": len(parts), "taken": 0}
    for phref, ptext in parts:
        part_slug = phref.rsplit("/", 1)[-1]
        if part_slug in taken_parts:
            crawl(phref, part=taken_parts[part_slug])
            continue
        letter = part_slug.split("-", 2)[1]
        chapters = {h for h, _ in links(fetch(phref, session=session), phref) if re.match(re.escape(twh) + rf"/{letter}-\d{{3,4}}-", h)}
        families[f"twh_{slug(ptext.split(',')[0])}_chapters_html"] = {"found": len(chapters), "taken": 0}
    glossary = twh + "/twh-glossary"
    glossary_doc = document_for(glossary, "TWH Glossary")
    glossary_doc["source_id"] = "tx-hhs-texas-works-twh-glossary"
    glossary_doc["citation_path"] = "us-tx/manual/hhs/texas-works-handbook/twh-glossary"
    families["twh_glossary_html"] = {"found": 1, "taken": 1}
    docs.append(glossary_doc)
    other = [t for h, t in links(index_page, twh) if h.startswith(twh + "/twh-") and h != glossary]
    families["twh_forms_documents_notices_revisions_bulletins_contact_pages"] = {"found": len(set(other)), "taken": 0}
    return docs, {"index_url": twh, "families": families, "existing_citation_paths_skipped": sorted(existing)}


# --------------------------------------------------------------------------- New Hampshire


def build_nh() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """New Hampshire DHHS Food Stamp Manual (RoboHelp WebHelp at www.dhhs.nh.gov/fsm_htm/),
    linked as "Food Stamp/SNAP Policy Manual" from the DHHS SNAP program page.

    The host answers HTTP 403 to the plain Axiom request and HTTP 200 to the existing manifest
    option ``browser_impersonation`` (curl-cffi chrome120); the manifest therefore carries that
    option, exactly as the NH Family Assistance Manual scope does. Topics are enumerated from the
    WebHelp plain-HTML table of contents (``whgdata/whlstt0.htm`` ... until 404), de-duplicated by
    topic file (the TOC lists a topic under several books), and every topic is fetched once to
    confirm it answers 200 and to inventory the Service Release (SR) documents it cites
    (``../../sr_htm/html/sr_*.htm``), which are a separate document family, not taken.
    """
    base = "https://www.dhhs.nh.gov/fsm_htm/"
    landing = base + "newfsm.htm"
    manual = "New Hampshire Food Stamp Manual"
    families: dict[str, dict[str, int]] = {}
    toc_pages: list[tuple[str, str]] = []
    for i in range(0, 500):
        toc_url = f"{base}whgdata/whlstt{i}.htm"
        status, content = fetch_impersonated(toc_url)
        if status != 200:
            break
        toc_pages.append((f"whlstt{i}.htm", content.decode("utf-8", "replace")))
    families["webhelp_toc_pages_html"] = {"found": len(toc_pages), "taken": 0}

    topics: dict[str, tuple[str, str]] = {}
    toc_links = 0
    for toc_file, page in toc_pages:
        for href, text in _LINK_RE.findall(page):
            href = html.unescape(href).strip()
            if href.startswith("whlstt"):
                continue
            toc_links += 1
            absolute = urljoin(f"{base}whgdata/", href).split("#", 1)[0]
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
            topics.setdefault(absolute, (text, toc_file))
    families["webhelp_toc_links"] = {"found": toc_links, "taken": 0}

    def probe(url: str) -> tuple[str, int, set[str]]:
        status, content = fetch_impersonated(url)
        text = content.decode("utf-8", "replace") if status == 200 else ""
        srs = {urljoin(url, html.unescape(h)).split("#", 1)[0] for h in re.findall(r'href="([^"]*sr_htm/[^"]+)"', text)}
        return url, status, srs

    with ThreadPoolExecutor(max_workers=6) as pool:
        probes = {url: (status, srs) for url, status, srs in pool.map(probe, sorted(topics))}
    service_releases: set[str] = set()
    docs: list[dict[str, Any]] = []
    fam = families.setdefault("food_stamp_manual_topic_html", {"found": 0, "taken": 0})
    unreachable = families.setdefault("food_stamp_manual_topic_unreachable", {"found": 0, "taken": 0})
    for url in sorted(topics, key=lambda u: (topics[u][1], u)):
        title, toc_file = topics[url]
        status, srs = probes[url]
        service_releases |= srs
        if status != 200:
            unreachable["found"] += 1
            print(f"us-nh: topic {url} answered HTTP {status}; not taken", file=sys.stderr)
            continue
        stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        label = slug(stem)
        fam["found"] += 1
        fam["taken"] += 1
        docs.append(
            {
                "source_id": f"us-nh-dhhs-fsm-{label}",
                "jurisdiction": "us-nh",
                "document_class": "manual",
                "title": f"{manual}: {title}",
                "source_url": url,
                "source_format": "html",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": EXPRESSION_DATE,
                "citation_path": f"us-nh/manual/dhhs/fsm/{label}",
                "request": {"browser_impersonation": True},
                "extraction": {"html_drop_selectors": ["#header", ".no-print", ".navBtnCusStyle"]},
                "metadata": {
                    "primary_source": True,
                    "source_authority": "New Hampshire Department of Health and Human Services, Bureau of Family Assistance",
                    "document_subtype": "policy_manual_topic",
                    "program": "SNAP",
                    "federal_program": "SNAP",
                    "manual": manual,
                    "manual_landing_page": landing,
                    "manual_toc_url": f"{base}whgdata/whlstt0.htm",
                    "toc_file": toc_file,
                    "source_discovery_group": "us-nh/manual/snap",
                    "discovered_via": (
                        f"manual-review:snap-completion-agent-queue batch 1 ({ISSUE}); DHHS SNAP program page "
                        "https://www.dhhs.nh.gov/programs-services/food-meals-assistance/supplemental-nutrition-assistance-program-snap "
                        f"links the manual at {landing}"
                    ),
                },
            }
        )
    families["service_release_html_cited_by_topics"] = {"found": len(service_releases), "taken": 0}
    return docs, {"index_url": landing, "families": families}


# --------------------------------------------------------------------------- Kentucky (batch 2)


def _pdf_revision_facts(content: bytes) -> dict[str, Any]:
    """Latest "R. m/d/yy" section revision, latest OMTL number and page count of a KY DFS
    Operation Manual volume (the released KY scope records the same facts)."""
    import fitz

    doc = fitz.open(stream=content, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    dates: set[dt.date] = set()
    for month, day, year in re.findall(r"R\.\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", text):
        y = int(year) if len(year) == 4 else 2000 + int(year)
        try:
            dates.add(dt.date(y, int(month), int(day)))
        except ValueError:
            continue
    omtls = [int(n) for n in re.findall(r"OMTL[- ]?(\d{3})", text)]
    toc = re.search(r"Table of Contents\s*[-\u2013]\s*R\.\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    toc_date = None
    if toc:
        m, d, y = toc.groups()
        toc_date = dt.date(int(y) if len(y) == 4 else 2000 + int(y), int(m), int(d)).isoformat()
    return {
        "latest_section_revision": max(dates).isoformat() if dates else None,
        "latest_omtl": str(max(omtls)) if omtls else None,
        "toc_revision_date": toc_date,
        "page_count": doc.page_count,
    }


def build_ky() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Kentucky DCBS Division of Family Support Operation Manual volumes, listed on the DFS page
    https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx (the released KY SNAP scope's
    ``manual_landing_page``). The page answered HTTP 403 from the batch-1 network and HTTP 200 to
    the plain Axiom request from the batch-2 network, so no request option is needed.

    Volumes II (SNAP) and IIA (SNAP work requirements) are in the released scope; both have newer
    editions today (Volume II OMTL-704, R. 8/1/26), but their citation paths exist, so they are
    inventoried, not re-taken. Volume I (General Administration) governs case processing,
    confidentiality, civil rights and hearings for every DFS program including SNAP and is not in
    the corpus; it is taken under the released KY convention ``us-ky/manual/dcbs/dfs/<volume>``.
    Program-specific volumes for KTAP, KWP, Medicaid, State Supplementation and CCAP, the OMTL
    cover-letter and policy-update volumes (IX, X; transmittal history, no SNAP policy text per
    the released queue row), the SNAP application forms and the SNAP E&T State Plan are separate
    families, not taken.
    """
    index = "https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx"
    session = requests.Session()
    page = fetch(index, session=session)
    families: dict[str, dict[str, int]] = {}
    volumes = [(h, t) for h, t in links(page, index) if re.search(r"/Documents/OMVOL", h, re.I)]
    apps = [(h, t) for h, t in links(page, index) if re.search(r"SNAPApp\.pdf$", h, re.I)]
    snap_existing = {"OMVOLII.pdf", "OMVOLIIA.pdf"}
    taken_file = "OMVOL1.pdf"
    fam_snap = families.setdefault("snap_volume_already_in_released_scope_revised_edition", {"found": 0, "taken": 0})
    fam_vol1 = families.setdefault("general_administration_volume_pdf", {"found": 0, "taken": 0})
    fam_other = families.setdefault("other_program_volume_pdf", {"found": 0, "taken": 0})
    fam_hist = families.setdefault("omtl_cover_letter_and_policy_update_volume_pdf", {"found": 0, "taken": 0})
    docs: list[dict[str, Any]] = []
    for href, _text in volumes:
        name = href.rsplit("/", 1)[-1]
        if name in snap_existing:
            fam_snap["found"] += 1
        elif name.upper() in {"OMVOL9.PDF", "OMVOLX.PDF"}:
            fam_hist["found"] += 1
        elif name == taken_file:
            fam_vol1["found"] += 1
            resp = session.get(href, headers={"User-Agent": UA}, timeout=120)
            resp.raise_for_status()
            facts = _pdf_revision_facts(resp.content)
            expression = facts["latest_section_revision"] or SOURCE_AS_OF
            fam_vol1["taken"] += 1
            docs.append(
                {
                    "source_id": "ky-dcbs-dfs-om-vol-i",
                    "jurisdiction": "us-ky",
                    "document_class": "manual",
                    "citation_path": "us-ky/manual/dcbs/dfs/volume-i-general-administration",
                    "title": "Kentucky DFS Manual Volume I - General Administration",
                    "source_url": href,
                    "source_format": "pdf",
                    "source_as_of": SOURCE_AS_OF,
                    "expression_date": expression,
                    "metadata": {
                        "primary_source": True,
                        "source_authority": "Kentucky Department for Community Based Services Division of Family Support",
                        "document_subtype": "policy_manual",
                        "program": "SNAP",
                        "state_program": "DFS Operation Manual general administration (all Family Support programs incl. SNAP)",
                        "federal_program": "SNAP",
                        "manual_landing_page": index,
                        "manual_revision_date": expression,
                        "manual_toc_revision_date": facts["toc_revision_date"],
                        "latest_omtl": facts["latest_omtl"],
                        "pdf_page_count": facts["page_count"],
                        "source_last_modified": resp.headers.get("Last-Modified"),
                        "source_discovery_group": "us-ky/manual/snap",
                        "discovered_via": f"manual-review:snap-completion-agent-queue batch 2 ({ISSUE}); publisher index {index}",
                    },
                }
            )
        else:
            fam_other["found"] += 1
    families["snap_application_form_pdf"] = {"found": len(apps), "taken": 0}
    return docs, {"index_url": index, "families": families}


# --------------------------------------------------------------------------- Wyoming (batch 2)


def build_wy() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Wyoming DFS SNAP and POWER Policy Manual on dfs.wyo.gov. The manual is one long page
    (sections 100-1400, in the released scope with its two accordion "extended menu" pages and
    Table II) plus a sub-navigation of subpages: EDI (case-file imaging guidance), Glossary, Codes,
    Notices, CM Updates, Policy Clarifications, Resources, Tables (landing for Table I SNAP income
    limits and Table II POWER income limits), a Medical Handbook, and a policy page on purchasing
    and preparing food separately linked from the manual text.

    Taken (SNAP-governing text absent from the corpus): Glossary, Policy Clarifications, Table I
    SNAP Income Limits and the purchasing-and-preparing-food-separately page. Not taken: CM Updates
    (change log), EDI/Codes/Notices/Resources (system and form catalogues, no eligibility policy),
    the Tables landing page, the Medical Handbook (Medicaid) and the pages already in the released
    scope. Citation paths follow the released convention
    ``us-wy/manual/dfs/snap-power-policy-manual/<slug>``; text is the WordPress ``.entry-content``.
    """
    from bs4 import BeautifulSoup

    index = "https://dfs.wyo.gov/about/policy-manuals/snap-and-power-policy-manual/"
    existing = registered_citation_paths("us-wy-manuals.yaml")
    session = requests.Session()
    page = fetch(index, session=session)
    families: dict[str, dict[str, int]] = {"manual_main_page_html_already_in_released_scope": {"found": 1, "taken": 0}}
    subpages = {h for h, _ in links(page, index) if h.startswith(index) and h != index}
    extended = {h for h, _ in links(page, index) if "/accordions/snap-and-power-policy-manual-" in h}
    clarifier = {h for h, _ in links(page, index) if "purchasing-and-preparing-food-separately" in h and "/about/policy-manuals/" in h and "snap-power-policy-manual/" not in h}
    families["extended_menu_accordion_html_already_in_released_scope"] = {
        "found": len(extended) or sum(1 for c in existing if c.endswith("-extended-menu")), "taken": 0}
    take = {
        "glossary": ("manual_glossary_html", "manual_glossary"),
        "policy-clarifications": ("policy_clarifications_html", "policy_clarifications"),
        "table-i-snap-income-limits": ("table_i_snap_income_limits_html", "manual_table"),
    }
    skip = {
        "case-file": "edi_case_file_guidance_html", "codes": "system_codes_html", "notices": "notice_catalogue_html",
        "cm-updates": "cm_updates_change_log_html", "forms": "resources_and_forms_html", "tables": "tables_landing_html",
        "medical-handbook": "medical_handbook_html", "table-ii-power-income-limits": "table_ii_already_in_released_scope_revised",
    }
    docs: list[dict[str, Any]] = []

    def document_for(url: str, label: str, subtype: str, fam: str) -> None:
        soup = BeautifulSoup(fetch(url, session=session), "html.parser")
        h1 = soup.select_one("h1")
        title = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else label
        path = f"us-wy/manual/dfs/snap-power-policy-manual/{label}"
        f = families.setdefault(fam, {"found": 0, "taken": 0})
        f["found"] += 1
        if path in existing:
            return
        f["taken"] += 1
        docs.append(
            {
                "source_id": f"wy-dfs-snap-power-{label}"[:80],
                "jurisdiction": "us-wy",
                "document_class": "manual",
                "citation_path": path,
                "title": f"Wyoming SNAP and POWER Policy Manual: {title}",
                "source_url": url,
                "source_format": "html",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": EXPRESSION_DATE,
                "extraction": {"html_content_selector": ".entry-content"},
                "metadata": {
                    "primary_source": True,
                    "source_authority": "Wyoming Department of Family Services",
                    "document_subtype": subtype,
                    "program": "SNAP",
                    "federal_program": "SNAP",
                    "manual": "SNAP and POWER Policy Manual",
                    "manual_landing_page": index,
                    "source_discovery_group": "us-wy/manual/snap",
                    "discovered_via": f"manual-review:snap-completion-agent-queue batch 2 ({ISSUE}); publisher index {index}",
                },
            }
        )

    for url in sorted(subpages):
        label = url.rstrip("/").rsplit("/", 1)[-1]
        if label in take:
            fam, subtype = take[label]
            document_for(url, label, subtype, fam)
        elif label in skip:
            families.setdefault(skip[label], {"found": 0, "taken": 0})["found"] += 1
        else:
            families.setdefault("other_subpage_html", {"found": 0, "taken": 0})["found"] += 1
            print(f"us-wy: unclassified subpage {url}; inventoried, not taken", file=sys.stderr)
    for url in sorted(clarifier):
        document_for(url, url.rstrip("/").rsplit("/", 1)[-1], "policy_clarification", "policy_clarification_page_linked_from_manual_html")
    return docs, {"index_url": index, "families": families, "existing_citation_paths_skipped": sorted(existing)}


# --------------------------------------------------------------------------- North Dakota (batch 2)


def build_nd() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """North Dakota HHS SNAP Policy Manual (MadCap Flare) at
    https://www.nd.gov/dhs/policymanuals/SNAP/. The TOC (``Data/Tocs/Online_Chunk0.js``) lists
    every topic; the Release Log lists every release-update PDF. The released scope
    (Release 26.5) holds the landing page, the TOC, the 26.5 update PDF and 64 topics. Releases 26.6
    (effective 2026-08-13) and 26.7 (effective 2026-10-01) landed since: two new topics and two
    release PDFs are taken under the released conventions
    ``us-nd/manual/hhs/snap/<slug of the Content path>`` and ``us-nd/manual/hhs/snap/updates/release-NN-N``.
    Older release PDFs (25.2-26.4) predate the released baseline and are the change-history
    family, not taken; topics already in the corpus keep their paths (their text was revised by
    26.6/26.7, which a superseding scope must carry).
    """
    from urllib.parse import quote, unquote

    root = "https://www.nd.gov/dhs/policymanuals/SNAP"
    landing = root + "/Content/Home%202.htm"
    existing = registered_citation_paths("us-nd-snap-manual.yaml")
    session = requests.Session()
    toc = fetch(root + "/Data/Tocs/Online_Chunk0.js", session=session)
    entries = re.findall(r"'(/Content/[^']+)':\{i:\[(\d+)\],t:\['([^']*)'\]", toc)
    families: dict[str, dict[str, int]] = {"toc_topic_html": {"found": len(entries), "taken": 0},
                                           "toc_topic_already_in_released_scope": {"found": 0, "taken": 0}}
    docs: list[dict[str, Any]] = []
    authority = "North Dakota Health and Human Services"
    families["landing_and_toc_already_in_released_scope"] = {"found": 0, "taken": 0}
    for path, _order, title in sorted(entries, key=lambda e: int(e[1])):
        if path == "/Content/Home 2.htm":  # released as us-nd/manual/hhs/snap/navigation/landing
            families["landing_and_toc_already_in_released_scope"]["found"] += 1
            families["toc_topic_html"]["found"] -= 1
            continue
        label = slug_full(unquote(f"/dhs/policymanuals/SNAP{path}"))
        citation = f"us-nd/manual/hhs/snap/{label}"
        if citation in existing:
            families["toc_topic_already_in_released_scope"]["found"] += 1
            continue
        url = root + quote(path)
        families["toc_topic_html"]["taken"] += 1
        docs.append(
            {
                "source_id": f"nd-hhs-snap-{label}",
                "jurisdiction": "us-nd",
                "document_class": "manual",
                "citation_path": citation,
                "title": f"North Dakota SNAP Policy Manual: {title.strip()}",
                "source_url": url,
                "source_format": "html",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": EXPRESSION_DATE,
                "extraction": {"html_content_selector": "#mc-main-content"},
                "metadata": {
                    "primary_source": True, "source_authority": authority, "document_subtype": "policy_manual_section",
                    "program": "SNAP", "federal_program": "SNAP", "manual_landing_page": landing,
                    "manual_toc_url": root + "/Data/Tocs/Online_Chunk0.js",
                    "source_discovery_group": "us-nd/manual/snap",
                    "discovered_via": f"manual-review:snap-completion-agent-queue batch 2 ({ISSUE}); publisher TOC {root}/Data/Tocs/Online_Chunk0.js",
                },
            }
        )
    log = fetch(root + "/Content/Release%20Log.htm", session=session)
    releases = [(urljoin(root + "/Content/", html.unescape(h)), t) for h, t in _LINK_RE.findall(log) if ".pdf" in h.lower()]
    fam_rel = families.setdefault("release_update_pdf", {"found": len(releases), "taken": 0})
    already = families.setdefault("release_update_pdf_already_in_released_scope", {"found": 0, "taken": 0})
    older = families.setdefault("release_update_pdf_before_released_baseline", {"found": 0, "taken": 0})
    baseline_versions = [tuple(int(x) for x in m.groups()) for m in re.finditer(r"updates/release-(\d+)-(\d+)$", "\n".join(existing), re.M)]
    baseline_version = max(baseline_versions) if baseline_versions else (0, 0)
    for url, text in releases:
        m = re.search(r"(?:Release|Relase|ML \d+)\s*(\d+)\.(\d+)\s*Effective\s*([A-Za-z]+|\d{1,2})\.(\d{1,2})\.(\d{4})", unquote(url))
        m2 = re.search(r"(\d+)\.(\d+)", text)
        if not m2:
            continue
        version = (int(m2.group(1)), int(m2.group(2)))
        citation = f"us-nd/manual/hhs/snap/updates/release-{version[0]}-{version[1]}"
        if citation in existing:
            already["found"] += 1
            continue
        if version < baseline_version:
            older["found"] += 1
            continue
        effective = None
        if m:
            mon, day, year = m.group(3), int(m.group(4)), int(m.group(5))
            month = int(mon) if mon.isdigit() else dt.datetime.strptime(mon[:3], "%b").month
            effective = dt.date(year, month, day).isoformat()
        fam_rel["taken"] += 1
        docs.append(
            {
                "source_id": f"nd-hhs-snap-release-{version[0]}-{version[1]}",
                "jurisdiction": "us-nd",
                "document_class": "manual",
                "citation_path": citation,
                "title": f"North Dakota SNAP Policy Manual Release {version[0]}.{version[1]} update",
                "source_url": unquote(url),
                "source_format": "pdf",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": effective or EXPRESSION_DATE,
                "metadata": {
                    "primary_source": True, "source_authority": authority, "document_subtype": "policy_manual_release",
                    "program": "SNAP", "federal_program": "SNAP", "manual_landing_page": landing,
                    "release_effective_date": effective,
                    "source_discovery_group": "us-nd/manual/snap",
                    "discovered_via": f"manual-review:snap-completion-agent-queue batch 2 ({ISSUE}); publisher Release Log {root}/Content/Release%20Log.htm",
                },
            }
        )
    families["landing_and_toc_already_in_released_scope"]["found"] += 1  # Data/Tocs/Online_Chunk0.js, released as navigation/toc
    return docs, {"index_url": landing, "families": families, "existing_citation_paths_skipped": sorted(existing)}


# --------------------------------------------------------------------------- queue rows

BUILDERS = {"us-tx": build_tx, "us-nh": build_nh, "us-ky": build_ky, "us-wy": build_wy, "us-nd": build_nd}
BATCH = {"us-tx": 1, "us-nh": 1, "us-ky": 2, "us-wy": 2, "us-nd": 2}
NAMES = {
    "us-fl": "Florida", "us-al": "Alabama", "us-md": "Maryland", "us-ma": "Massachusetts", "us-tx": "Texas",
    "us-ca": "California", "us-ny": "New York", "us-nh": "New Hampshire", "us-ky": "Kentucky", "us-me": "Maine",
    "us-ne": "Nebraska", "us-wy": "Wyoming", "us-az": "Arizona", "us-ar": "Arkansas", "us-ia": "Iowa", "us-hi": "Hawaii",
    "us-nm": "New Mexico", "us-vt": "Vermont", "us-nv": "Nevada", "us-nd": "North Dakota", "us-id": "Idaho",
    "us-nc": "North Carolina", "us-oh": "Ohio", "us-mt": "Montana", "us-ok": "Oklahoma", "us-ga": "Georgia",
    "us-tn": "Tennessee", "us-mi": "Michigan",
}
SOURCE_KIND = {
    "us-tx": "official_html_handbook_sections", "us-nh": "official_html_webhelp_manual_topics",
    "us-ky": "official_pdf_manual_volume", "us-wy": "official_html_manual_subpages", "us-nd": "official_html_manual_topics_and_release_pdfs",
}
BATCH_NOTE = (
    "Batch 1 (2026-09-10, axiom-corpus#680): ingestion-gap states FL, AL, MD, MA diagnosed against the released "
    "scopes, then discovery-gap states TX, CA, NY, NH, KY, ME checked on the publisher's own index. Generator: "
    "scripts/build_snap_state_manual_completion_manifests.py."
)
BATCH2_NOTE = (
    "Batch 2 (2026-09-10, axiom-corpus#680, US network): KY and NY retried (KY answers, NY still bot-challenged); "
    "discovery-gap states NE, WY, AZ, AR, IA, HI, NM, VT, NV, ND attempted in the issue's order, ID taken as the "
    "replacement for AZ (blocked on the first probe). Every publisher index was fetched live; revised editions of "
    "documents already in a released scope are recorded, not re-taken (their citation paths exist). Generator: "
    "scripts/build_snap_state_manual_completion_manifests.py --only us-ky --only us-wy --only us-nd."
)

BATCH3_NOTE = (
    "Batch 3 (2026-09-11, axiom-corpus#680, US network): the issue's last seven discovery-gap states NC, OH, MT, OK, GA, TN, "
    "MI diagnosed against the released scopes and confirmed on the publisher's own index; AZ and NY re-probed once (both still "
    "bot-challenged). Every index is already fully in the corpus, so no completion scope was built; revised editions since the "
    "released scopes are recorded for superseding scopes. Ohio's OAC 5101:4 is complete (82 of 82 rules) and its eManuals host "
    "does not answer (blocked_primary_source for the manual family). Generator: "
    "scripts/build_snap_state_manual_completion_manifests.py --static-only."
)

STATIC_ROWS: dict[str, dict[str, Any]] = {
    "us-fl": {
        "queue_status": "done",
        "source_kind": "official_pdf_manual_sections",
        "primary_source_url": "https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-fl", "document_class": "manual", "version": "2026-05-27-fl-ess-manual-r2026-07-15-self-contained"},
        "index_url": "https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual",
        "index_document_count": 76, "taken_count": 0,
        "index_families": {"ess_program_policy_manual_section_pdf": {"found": 48, "taken": 0, "already_in_corpus": 48},
                           "ess_summary_of_changes_quarterly_pdf": {"found": 28, "taken": 0}},
        "notes": (
            "Diagnosis 2026-09-10 (#680 says 68 registered, 48 captured): nothing failed to land. 'Registered' counts manifests whose "
            "program tag is SNAP: the 68 are manifests/us-fl-snap-primary-policy.yaml, FAC 65A-1 sections republished by Cornell LII "
            "(metadata primary_source: false), all 68 roots present in the released scope us-fl/regulation/2026-05-29-r2026-07-15-self-contained "
            "(204 provisions, coverage complete). 'Captured' is the encoding queue plus rulespec artifacts: the 48 are the DCF ESS Program "
            "Policy Manual PDFs (manifests/us-fl-ess-manual.yaml, program tag ESS, so not counted as SNAP-registered), all 48 roots present in "
            "us-fl/manual/2026-05-27-fl-ess-manual-r2026-07-15-self-contained (1,107 provisions, coverage complete). The difference is 61 "
            "registered-and-ingested regulation sections that sit in no encoding queue and have no artifact (dashboard stalled_registered), "
            "not an extraction, scope-cut or selector failure. Publisher index today: 76 PDF links = the same 48 manual sections plus 28 "
            "quarterly Summary of Changes PDFs (separate change-summary family, not taken). No completion scope needed. Reviewer: the "
            "Cornell LII regulation manifest is a non-primary republication under this queue's forbidden-sources policy; replacing it with "
            "the official flrules.org FAC 65A-1 text is a separate work order."
        ),
    },
    "us-al": {
        "queue_status": "done",
        "source_kind": "official_pdf_chapter_manual",
        "primary_source_url": "https://apps.dhr.alabama.gov/POE/POEhome",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-al", "document_class": "manual", "version": "2026-05-27-al-snap-poe-manual-r2026-07-15-self-contained"},
        "index_url": "https://apps.dhr.alabama.gov/POE/POEhome",
        "index_document_count": None, "taken_count": 0,
        "index_families": {"poe_manual_chapter_pdf": {"found": 17, "taken": 0, "already_in_corpus": 17}},
        "notes": (
            "Diagnosis 2026-09-10 (#680 says 59 registered, 17 captured): nothing failed to land. Registered 59 = 42 Ala. Admin. Code 660-4 "
            "sections republished by Cornell LII (manifests/us-al-snap-primary-policy.yaml, primary_source: false; all 42 roots present in the "
            "released scope us-al/regulation/2026-05-29-r2026-07-15-self-contained, 126 provisions) + the 17 DHR POE Online Manual chapter PDFs "
            "(manifests/us-al-snap-manual.yaml; all 17 roots present in us-al/manual/2026-05-27-al-snap-poe-manual-r2026-07-15-self-contained, "
            "149 provisions, coverage complete). Captured 17 = the POE chapters in the encoding queue; the 42 regulation sections are ingested "
            "but in no queue (dashboard stalled_registered 20 after de-duplication against artifacts). Publisher index re-check blocked today: "
            "apps.dhr.alabama.gov TCP connect timeout (curl 28 after 30 s plain request; curl-cffi chrome120 the same after 20 s); the 17-chapter "
            "inventory stands from the queue row of 2026-05-27. No completion scope needed."
        ),
    },
    "us-md": {
        "queue_status": "done",
        "source_kind": "official_pdf_or_html_manual",
        "primary_source_url": "https://dhs.maryland.gov/supplemental-nutrition-assistance-program/food-supplement-program-manual/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-md", "document_class": "manual", "version": "2026-07-17-md-snap-manual"},
        "index_url": "https://dhs.maryland.gov/supplemental-nutrition-assistance-program/food-supplement-program-manual/",
        "index_document_count": 51, "taken_count": 0,
        "index_families": {"snap_manual_section_file": {"found": 51, "taken": 0, "already_in_corpus": 51}},
        "notes": (
            "Diagnosis 2026-09-10 (#680 says 54 registered, 53 captured): nothing failed to land. Registered 54 = 51 manual files "
            "(manifests/us-md-fsp-manual.yaml; all 51 roots present in the released scope us-md/manual/2026-07-17-md-snap-manual, 379 "
            "provisions, coverage complete) + 3 FIA FY2026 SNAP guidance documents (manifests/us-md-fia-snap-fy2026-guidance.yaml, released "
            "scope us-md/guidance/2026-07-12-md-fia-snap-fy2026). Captured 53 = 51 queue items + 2 rulespec artifacts; the 1-document gap is "
            "a guidance row with no queue item or artifact. Publisher index today lists exactly the same 51 files (0 new, 0 removed). No "
            "completion scope needed."
        ),
    },
    "us-ma": {
        "queue_status": "done",
        "source_kind": "official_regulations",
        "primary_source_url": "https://www.mass.gov/lists/department-of-transitional-assistance-regulations",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ma", "document_class": "regulation", "version": "2026-07-21-ma-dta-regulations-consolidated"},
        "index_url": "https://www.mass.gov/lists/department-of-transitional-assistance-regulations",
        "index_document_count": 18, "taken_count": 0,
        "index_families": {"dta_snap_regulation_chapter_pdf": {"found": 9, "taken": 0, "already_in_corpus": 9},
                           "dta_snap_regulation_chapter_docx_duplicate": {"found": 9, "taken": 0}},
        "notes": (
            "Diagnosis 2026-09-10 (#680 says 54 registered, 12 captured): nothing failed to land. Registered 54 = 44 106 CMR 364-365 sections "
            "republished by Cornell LII (manifests/us-ma-snap-primary-policy.yaml, primary_source: false) + 9 official DTA chapter files "
            "(343, 360-367; manifests/us-ma-dta-snap-regulations.yaml) + 1 COLA guidance document. 53 of the 54 registered citation paths are "
            "present in the released consolidated scope us-ma/regulation/2026-07-21-ma-dta-regulations-consolidated (332 provisions; the 9 "
            "chapter roots all present). The one absent path, us-ma/regulation/106-cmr/364/360, is a Cornell LII manifest entry for a "
            "section number the official chapter 364 PDF does not carry, so it is not a missing official document. Captured 12 = 9 queue items "
            "+ 3 artifacts; the remainder is ingested-but-unqueued. Publisher index today: the same 9 chapter PDFs (all in the manifest) plus a "
            "DOCX copy of each chapter (same text, other format; not taken). The DTA Online Guide named in #680 "
            "(https://www.mass.gov/info-details/the-department-of-transitional-assistance-online-guide) is a separate manual family whose "
            "index page carries only in-page anchors and DTA Connect links; it is not an ingestion gap and is left for a discovery batch. No "
            "completion scope needed."
        ),
    },
    "us-ca": {
        "queue_status": "done",
        "source_kind": "official_docx_and_ocr_pdf_manual_regulations",
        "primary_source_url": "https://www.cdss.ca.gov/inforesources/letters-regulations/legislation-and-regulations/calworks-calfresh-regulations/calfresh-regulations",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ca", "document_class": "regulation", "version": "2026-07-17-ca-cdss-mpp-calfresh"},
        "index_url": "https://www.cdss.ca.gov/inforesources/letters-regulations/legislation-and-regulations/calworks-calfresh-regulations/calfresh-regulations",
        "index_document_count": 15, "taken_count": 0,
        "index_families": {"mpp_division_63_food_stamp_manual_file": {"found": 15, "taken": 0, "already_in_corpus": 15}},
        "notes": (
            "Index confirmed 2026-09-10: the CDSS CalFresh Regulations page (the publisher's own index of the Manual of Policies and "
            "Procedures Division 63) lists 15 Food Stamp Manual files (fsman01-fsman12 incl. 04a/04b and 11a/11b/11c); all 15 are in "
            "manifests/us-ca-cdss-mpp-calfresh-complete.yaml and the released scope us-ca/regulation/2026-07-17-ca-cdss-mpp-calfresh (436 "
            "provisions, coverage complete). CDSS publishes no separate CalFresh handbook; county handbooks are not state primary sources. "
            "#680's 18 'captured' = 15 queue items + 3 artifacts, i.e. a document count, not a section count. Nothing new to take."
        ),
    },
    "us-me": {
        "queue_status": "done",
        "source_kind": "official_agency_rules",
        "primary_source_url": "https://www.maine.gov/sos/rulemaking/agency-rules/department-health-and-human-services-rules",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-me", "document_class": "regulation", "version": "2026-07-17-me-snap-rules"},
        "index_url": "https://www.maine.gov/sos/rulemaking/agency-rules/department-health-and-human-services-rules",
        "index_document_count": 3, "taken_count": 0,
        "index_families": {"ofi_snap_rule_chapter_docx": {"found": 2, "taken": 0, "already_in_corpus": 2},
                           "ofi_sun_bucks_rule_chapter_docx": {"found": 1, "taken": 0}},
        "notes": (
            "Index confirmed 2026-09-10: the Secretary of State DHHS rules index lists 10-144 Ch. 301 (SNAP Rules, file "
            "144c301-2026-133-NSC.docx, the same file as the released scope), Ch. 609 (SNAP Employment and Training) and Ch. 302 (SUN Bucks, "
            "a Summer EBT program, outside SNAP). Both SNAP chapters are in manifests/us-me-snap-rules.yaml and the released scope "
            "us-me/regulation/2026-07-17-me-snap-rules (223 provisions). Reviewer: the index now links Ch. 609 as 144c609-2026-191-AMD.docx, "
            "an amended edition newer than the released 144c609_0.docx; its citation path us-me/regulation/dhhs/ofi/chapter-609 already exists, "
            "so a completion scope cannot carry it and a superseding ME rules scope is needed instead. #680's 2 'captured' is a document count "
            "(two rulebooks), not a section count. Nothing new to take here."
        ),
    },
    "us-ky": {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_agency_page",
        "primary_source_url": "https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ky", "document_class": "manual", "version": "2026-07-17-ky-snap-manual"},
        "index_url": "https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx",
        "index_document_count": None, "taken_count": 0,
        "index_families": {},
        "notes": (
            "Blocked 2026-09-10: the DCBS Division of Family Support page (the publisher index that lists the Operation Manual volumes) "
            "returns HTTP 403 (1,484-byte error page) to the plain Axiom request and the same HTTP 403 to curl-cffi chrome120 browser "
            "impersonation (20 s timeout). No workaround attempted. The released scope us-ky/manual/2026-07-17-ky-snap-manual already holds "
            "Volume II (SNAP) and Volume IIA (SNAP work requirements) in full (400 page provisions), so #680's 2 'captured' is a document count; "
            "the index re-check for newer OMTL editions or further SNAP volumes is what is blocked."
        ),
    },
    "us-ny": {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_pdf_manuals",
        "primary_source_url": "https://otda.ny.gov/programs/snap/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ny", "document_class": "manual", "version": "2026-07-17-ny-snap-manuals"},
        "index_url": "https://otda.ny.gov/programs/snap/",
        "index_document_count": None, "taken_count": 0,
        "index_families": {},
        "notes": (
            "Blocked 2026-09-10: otda.ny.gov resets the plain Axiom request (curl 56, connection reset by peer, 30 s timeout) and answers "
            "curl-cffi chrome120 browser impersonation with HTTP 200 carrying a 5,609-byte F5/TSPD JavaScript bot-challenge page instead of the "
            "SNAP program page, so no index inventory is possible. No workaround attempted (the released scope's pinned official-URL archive "
            "captures are not an option for new documents under this run's rules). The released scopes already hold the 576-page SNAP Source "
            "Book, the 16-part Employment Policy Manual (340 provisions) and 18 NYCRR Parts 385 and 387 (1,678 provisions); #680's 18 'captured' "
            "is a document count. OTDA policy directives (ADM/INF/GIS) remain a separate family to inventory when the host answers."
        ),
    },
}


# Batch-2 static rows. KY moved to a live builder (build_ky); the batch-1 NY row is superseded by the retry below.
STATIC_ROWS_BATCH2: dict[str, dict[str, Any]] = {
    "us-ny": {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_pdf_manuals",
        "primary_source_url": "https://otda.ny.gov/programs/snap/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ny", "document_class": "manual", "version": "2026-07-17-ny-snap-manuals"},
        "index_url": "https://otda.ny.gov/programs/snap/",
        "index_document_count": None, "taken_count": 0,
        "index_families": {},
        "notes": (
            "Blocked 2026-09-10 (batch 1, first network): otda.ny.gov reset the plain Axiom request (curl 56) and answered curl-cffi "
            "chrome120 impersonation with a 5,609-byte F5/TSPD JavaScript bot-challenge page. Retried 2026-09-10 (batch 2, US network, "
            "20 s timeouts, one plain request and one browser-impersonation request): the plain request is closed without a response "
            "(requests ConnectionError: RemoteDisconnected('Remote end closed connection without response') after 0.7 s); "
            "curl-cffi chrome120 gets HTTP 200 carrying a 7,562-byte TSPD bot-challenge page instead of the SNAP program page. No "
            "index inventory is possible; no workaround attempted. The released scopes already hold the 576-page SNAP Source Book, "
            "the 16-part Employment Policy Manual (340 provisions) and 18 NYCRR Parts 385 and 387 (1,678 provisions); #680's 18 "
            "'captured' is a document count. OTDA policy directives (ADM/INF/GIS) remain a separate family to inventory when the host answers."
        ),
    },
    "us-az": {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_html_manual",
        "primary_source_url": "https://dbmefaapolicy.azdes.gov/FAA5.html",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-az", "document_class": "manual", "version": "2025-10-30-az-des-faa5-manual-r2026-07-15-self-contained"},
        "index_url": "https://dbmefaapolicy.azdes.gov/FAA5.html",
        "index_document_count": None, "taken_count": 0,
        "index_families": {},
        "notes": (
            "Blocked 2026-09-10 (batch 2, first probe): the DES FAA policy manual host dbmefaapolicy.azdes.gov answers HTTP 403 with a "
            "5,675-byte page to the plain Axiom request and HTTP 403 with a 5,995-byte F5/TSPD JavaScript bot-challenge page to curl-cffi "
            "chrome120 browser impersonation (20 s timeouts). No workaround attempted; the released scope's archived-snapshot captures "
            "(web.archive.org download_url) are not an option for new documents under this run's rules. The released scopes hold 80 FAA5 "
            "manual pages (2025-10-30, 7 provisions) and the FAA5 recovery scope (143 provisions); #680's 7 'captured' reflects that thin "
            "release. ID was taken as the replacement state."
        ),
    },
    "us-ne": {
        "queue_status": "done",
        "source_kind": "official_administrative_rules",
        "primary_source_url": "https://rules.nebraska.gov/rules?agencyId=37&titleId=230",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ne", "document_class": "regulation", "version": "2026-07-17-ne-snap-rules"},
        "index_url": "https://rules.nebraska.gov/rules?agencyId=37&titleId=230",
        "index_document_count": 5, "taken_count": 0,
        "index_families": {"title_475_nac_chapter_pdf": {"found": 5, "taken": 0, "already_in_corpus": 5, "revised_edition_since_release": 2}},
        "notes": (
            "Index confirmed 2026-09-10: the Nebraska Rules site (a React app whose data is the same-origin API "
            "/api/title/GetByAgencyId/37 and /api/chapter/GetByTitleId/230) lists Title 475 NAC 'Supplemental Nutrition Assistance "
            "Program' with five chapters (1 General Provisions, 2 Household Processing, 3 Eligibility, 4 Benefits, 5 EBT Card Issuance "
            "and Accountability); all five are in manifests/us-ne-snap-rules.yaml and the released scope us-ne/regulation/2026-07-17-ne-snap-rules "
            "(742 provisions, coverage complete). Nothing new to take. Reviewer: chapters 2 and 3 now carry an effective date of "
            "2026-07-28 (new editions; the released files are the 09-17-2024 editions), chapters 1, 4 and 5 are unchanged; the two "
            "revised chapters' citation paths exist, so a superseding NE rules scope is needed, not a completion scope. TLS: "
            "rules.nebraska.gov serves *.nebraska.gov without its DigiCert Global G2 TLS RSA SHA256 2020 CA1 intermediate (openssl "
            "verify code 21); the released manifest worked around this with request.verify_tls: false. This run fetched with "
            "verification on by adding the publisher's public intermediate as data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem "
            "(from cacerts.digicert.com) and REQUESTS_CA_BUNDLE = certifi + that file; the superseding scope should use the same bundle "
            "instead of verify_tls: false. #680's 5 'captured' is the document count."
        ),
    },
    "us-ar": {
        "queue_status": "done",
        "source_kind": "official_pdf_and_html_policy_set",
        "primary_source_url": "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/supplemental-nutrition-assistance-snap/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ar", "document_class": "manual", "version": "2026-07-16-ar-snap-manual"},
        "index_url": "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/supplemental-nutrition-assistance-snap/",
        "index_document_count": 13, "taken_count": 0,
        "index_families": {
            "snap_program_page_policy_html": {"found": 3, "taken": 0, "already_in_corpus": 3},
            "snap_quick_reference_chart_pdf": {"found": 1, "taken": 0, "already_in_corpus": 1},
            "snap_policy_manual_pdf_media_library": {"found": 4, "taken": 0, "already_in_corpus": 1, "revised_edition_since_release": 1},
            "snap_appendices_pdf_media_library": {"found": 2, "taken": 0, "already_in_corpus": 0, "revised_edition_since_release": 1},
            "snap_et_provider_contact_list_pdf": {"found": 1, "taken": 0},
            "snap_et_state_plan_pdf": {"found": 2, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-10: the DHS DCO SNAP page and its sub-pages (nutrition waiver, waiver FAQ, work requirement and "
            "time-limit rules, SNAP Overview and How to Apply, SNAP E&T) link the three policy HTML pages and the FY2026 Quick Reference "
            "chart that are already in manifests/us-ar-snap-manual.yaml (us-ar/manual/2026-07-16-ar-snap-manual, 810 provisions). No DHS "
            "web page links the SNAP Certification Manual PDF itself; the publisher's own media library (humanservices.arkansas.gov "
            "/wp-json/wp/v2/media, search 'SNAP') lists SNAP-Policy-Manual-11.21.2025, -03.01.2026, -04.02.2026 (the released edition) "
            "and -07.01.2026 (uploaded 2026-07-22), and SNAP-Appendices-04.02.2026 and -07.30.2026; the released appendices URL "
            "SNAP-Appendices-05.15.2026.pdf now answers HTTP 404. Reviewer: the July 2026 manual and appendices are new editions of "
            "documents whose citation paths (us-ar/manual/dhs/snap-policy-manual, snap-manual-appendices) exist, so a superseding AR "
            "scope is needed, not a completion scope; nothing new to take here. SNAP-Employment-and-Training-7.24.26.pdf is the E&T "
            "provider contact list (a directory, not policy) and the two state-plan PDFs are the FFY25/FY26 SNAP E&T State Plans "
            "(state-plan family, not the manual). #680's 8 'captured' is the document count."
        ),
    },
    "us-ia": {
        "queue_status": "done",
        "source_kind": "official_manual_index_pdf",
        "primary_source_url": "https://hhs.iowa.gov/media/4035/download?inline",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ia", "document_class": "manual", "version": "2026-07-17-ia-snap-manual"},
        "index_url": "https://hhs.iowa.gov/media/4035/download?inline",
        "index_document_count": 13, "taken_count": 0,
        "index_families": {"employees_manual_title_7_chapter_pdf": {"found": 11, "taken": 0, "already_in_corpus": 11},
                           "employees_manual_toc_pdf": {"found": 1, "taken": 0, "already_in_corpus": 1},
                           "title_7_omnibus_duplicate_pdf": {"found": 1, "taken": 0}},
        "notes": (
            "Index confirmed 2026-09-10: the HHS Employees' Manual table of contents (revised March 3, 2023) lists Title 7 SNAP as "
            "chapters A-J and M plus an 'All SNAP Chapters' omnibus; all eleven chapters and the TOC are in manifests/us-ia-snap-manual.yaml "
            "and the released scope us-ia/manual/2026-07-17-ia-snap-manual (443 provisions, coverage complete); the omnibus is the same "
            "text in one file (excluded by the released row). All 12 released files are byte-identical to the publisher's files today "
            "(SHA-256 match against the released inventory), so nothing is revised and nothing is new. #680's 12 'captured' is the document count."
        ),
    },
    "us-hi": {
        "queue_status": "done",
        "source_kind": "official_administrative_rules",
        "primary_source_url": "https://humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-hi", "document_class": "regulation", "version": "2026-05-27-hi-snap-rules-r2026-07-15-self-contained"},
        "index_url": "https://humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/",
        "index_document_count": 140, "taken_count": 0,
        "index_families": {
            "har_title_17_subtitle_6_snap_chapter_pdf": {"found": 20, "taken": 0, "already_in_corpus": 20},
            "har_title_17_subtitle_6_other_program_chapter_pdf": {"found": 11, "taken": 0},
            "har_title_17_other_subtitle_chapter_pdf": {"found": 108, "taken": 0},
            "har_dead_link_files_hawaii_gov": {"found": 1, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-10: the DHS 'Administrative Rules for Programs' page lists 140 HAR Title 17 chapter PDFs. The 20 "
            "Subtitle 6 (Benefit, Employment and Support Services Division) chapters that govern SNAP (600-606 general, 610 Food Stamp "
            "Program Administration, 647-650, 655, 663, 675, 676, 680, 681, 683, 684.1) are all in manifests/us-hi-snap-rules.yaml and the "
            "released scope (594 provisions, coverage complete), and every one of the 20 files carries a Last-Modified of 2018-2022, so none "
            "is revised. The other Subtitle 6 chapters are not SNAP: 653 child support/third-party liability, 654 no-fault insurance, 656.1 "
            "TANF, 658 AABD financial assistance, 659 General Assistance, 661 refugee/repatriate/SLIAG, 678 financial assistance standards, "
            "685.4 replacement of stolen financial-assistance/child-care benefits, 686.1 Summer EBT (outside SNAP, as ME SUN Bucks), 687 "
            "Hawaii Emergency Food Assistance Program (HEFAP), and 17-602.1 at files.hawaii.gov is a dead link (404). Nothing new to take. "
            "#680's 20 'captured' is the document count."
        ),
    },
    "us-nm": {
        "queue_status": "done",
        "source_kind": "official_administrative_code",
        "primary_source_url": "https://www.hca.nm.gov/lookingforinformation/income-support-division-1/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-nm", "document_class": "regulation", "version": "2026-07-17-nm-snap-regulations"},
        "index_url": "https://www.hca.nm.gov/lookingforinformation/income-support-division-1/",
        "index_document_count": 102, "taken_count": 0,
        "index_families": {
            "nmac_8_139_food_stamp_program_part_html": {"found": 18, "taken": 0, "already_in_corpus": 18},
            "nmac_8_100_general_provisions_part_html": {"found": 10, "taken": 0, "already_in_corpus": 10},
            "nmac_other_isd_program_part_html": {"found": 73, "taken": 0},
            "isd_state_verification_plan_pdf": {"found": 1, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-10: the HCA Income Support Division page links the NMAC parts on the State Records Center (srca.nm.gov) "
            "for 8.100 (10 parts), 8.102 TANF/NMW (17), 8.106 GA (18), 8.119 refugee (7), 8.139 Food Stamp Program (17) and 8.150 LIHEAP (17); "
            "the SRCA Title 8 chapter page marks every other 8.139 part number RESERVED, which leaves 18 active 8.139 parts (the 17 on the HCA "
            "page plus 8.139.640). All 18 8.139 parts and all 10 8.100 parts are in manifests/us-nm-snap-regulations.yaml and the released "
            "scope us-nm/regulation/2026-07-17-nm-snap-regulations (388 provisions, coverage complete), and all 28 SRCA part files are "
            "byte-identical to the released inventory (SHA-256). Nothing new to take; nothing revised. #680's 28 'captured' is the document count."
        ),
    },
    "us-vt": {
        "queue_status": "done",
        "source_kind": "official_html_manual",
        "primary_source_url": "https://www.ahsnet.ahs.state.vt.us/Public/3sVT/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-vt", "document_class": "manual", "version": "2026-07-21-vt-3squaresvt-manual"},
        "index_url": "https://www.ahsnet.ahs.state.vt.us/Public/3sVT/whxdata/toc.new.js",
        "index_document_count": 32, "taken_count": 0,
        "index_families": {"robohelp_toc_books": {"found": 32, "taken": 0}, "robohelp_toc_entries": {"found": 252, "taken": 0},
                           "brm_chapter_topic_html": {"found": 32, "taken": 0, "already_in_corpus": 32}},
        "notes": (
            "Index confirmed 2026-09-10: the 3SquaresVT manual (RoboHelp) TOC (whxdata/toc.new.js plus one toc<N>.new.js per book) has 32 "
            "books and 252 entries that resolve to 32 distinct topic files (the entries are in-page anchors); all 32 are in "
            "manifests/us-vt-3squaresvt-manual.yaml and the released scope us-vt/manual/2026-07-21-vt-3squaresvt-manual (911 provisions, "
            "coverage complete), and all 32 files are byte-identical to the released inventory (SHA-256). Nothing new to take; nothing "
            "revised. #680's 32 'captured' is the document count."
        ),
    },
    "us-id": {
        "queue_status": "done",
        "source_kind": "official_administrative_rules_pdf",
        "primary_source_url": "https://adminrules.idaho.gov/current-rules/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-id", "document_class": "regulation", "version": "2026-05-27-id-food-stamp-rules-r2026-07-15-self-contained"},
        "index_url": "https://adminrules.idaho.gov/current-rules/",
        "index_document_count": 369, "taken_count": 0,
        "index_families": {
            "idapa_16_03_04_food_stamp_program_pdf": {"found": 1, "taken": 0, "already_in_corpus": 1},
            "idapa_title_16_other_chapter_pdf": {"found": 20, "taken": 0},
            "idapa_other_agency_rule_chapter_pdf": {"found": 348, "taken": 0},
        },
        "notes": (
            "Replacement for AZ (blocked on its first probe). Index confirmed 2026-09-10: the Office of the Administrative Rules "
            "Coordinator's Current Rules page renders its list from the site's own REST endpoint "
            "(/wp-json/dfm-document-display/fetch-documents, documentType currentRules, called with the page's nonce exactly as the "
            "page does; the legacy directory URL /rules/current/16/ answers HTTP 404). It lists 369 current rule chapters, 21 of them "
            "IDAPA Title 16 (Department of Health and Welfare); 16.03.04 'Idaho Food Stamp Program' is the only SNAP chapter and is in "
            "manifests/us-id-snap-rules.yaml and the released scope us-id/regulation/2026-05-27-id-food-stamp-rules-r2026-07-15-self-contained; "
            "the live /rules/current/16/160304.pdf (70 pages, Last-Modified 2026-07-01) is byte-identical to the released inventory (SHA-256 "
            "1d542968...), so nothing is revised. The other Title 16 chapters (16.03.01 health-care eligibility, 16.03.05 AABD, 16.03.08 "
            "Federal Welfare Programs (cash assistance), 16.03.19-26 provider and Medicaid rules, 16.02, 16.04-16.06) are not SNAP. DHW "
            "publishes no separate public SNAP manual. Nothing new to take. #680's 70 'captured' is a section count of the one chapter."
        ),
    },
    "us-nv": {
        "queue_status": "done",
        "source_kind": "official_manual_page",
        "primary_source_url": "https://dwss.nv.gov/Home/Features/eligibility/eligibility-n-payment-info-manual/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-nv", "document_class": "manual", "version": "2026-05-27-nv-eligibility-payments-manual-r2026-07-15-self-contained"},
        "index_url": "https://dwss.nv.gov/Home/Features/eligibility/eligibility-n-payment-info-manual/",
        "index_document_count": 139, "taken_count": 0,
        "index_families": {
            "ep_manual_chapter_and_reference_pdf": {"found": 51, "taken": 0, "already_in_corpus": 45, "revised_edition_since_release": 6},
            "ep_manual_transmittal_letter_pdf": {"found": 86, "taken": 0},
            "state_web_standards_pdf_offsite": {"found": 2, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-10: the DWSS Eligibility & Payments Manual page lists 51 chapter and reference PDFs (sections A-D, F, R, "
            "TOC, glossary, index) and 86 manual transmittal letters (2010-July 2026). All 51 chapter citation paths are in "
            "manifests/us-nv-eligibility-payments-manual.yaml and the released scope (821 provisions, coverage complete). Reviewer: six "
            "chapters are now served as new files (A-100 Application Processing, A-200 Verification and Documentation, A-700 Income, "
            "A-1800 Case Disposition, B-400 Special Households, B-900 Program Violations/Sanctions; the released URLs for them are no longer "
            "on the index), i.e. editions revised by the April-July 2026 transmittals; their citation paths exist, so a superseding NV scope "
            "is needed, not a completion scope. The transmittal letters are the change-summary family (as FL Summary of Changes and NH Service "
            "Releases), not taken. Nothing new to take. #680's 51 'captured' is the document count."
        ),
    },
}


STATIC_ROWS_BATCH3: dict[str, dict[str, Any]] = {
    "us-nc": {
        "queue_status": "done",
        "source_kind": "official_pdf_manual_sections",
        "primary_source_url": "https://policies.ncdhhs.gov/divisional-n-z/social-services/food-and-nutrition-services/fns-policies-manuals/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-nc", "document_class": "manual", "version": "2026-05-27-nc-fns-manuals-r2026-07-15-self-contained"},
        "index_url": "https://policies.ncdhhs.gov/divisional-n-z/social-services/food-and-nutrition-services/fns-policies-manuals/",
        "index_document_count": 758, "taken_count": 0,
        "index_families": {
            "fns_manual_section_pdf": {"found": 77, "taken": 0, "already_in_corpus": 77, "revised_edition_since_release": 4},
            "fns_manual_appendix_pdf": {"found": 2, "taken": 0, "already_in_corpus": 2},
            "fns_administrative_letter_document": {"found": 367, "taken": 0},
            "fns_change_notice_document": {"found": 312, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-11: the NCDHHS FNS Policies & Manuals page lists 77 FNS manual sections (FNS 100-175, 200-270, "
            "300-390, 400-450, 500-515, 600, 650, 700-705, 800-865, 900-915) as document pages with their PDFs, plus Appendix 3100 "
            "(Social Security district offices) and Appendix 3300 (glossary): 79 documents, all 79 in manifests/us-nc-fns-manuals.yaml "
            "and the released scope us-nc/manual/2026-05-27-nc-fns-manuals-r2026-07-15-self-contained (723 provisions, coverage "
            "complete). Nothing new to take. Reviewer: four sections are revised editions since the release, served under new August "
            "2026 file names (FNS 212 Household Composition Special Arrangements 8.17.2026, FNS 215 Residence 8.4.2026, FNS 340 "
            "Deductions 8.4.2026, FNS 515 SR Changes During the Certification Period 8.13.2026; Last-Modified 2026-08-05 to 2026-08-31); "
            "the released URLs still answer HTTP 200 with the old files and none of the other 75 released files is modified after "
            "2026-05-27 (Last-Modified headers; the self-contained release object keeps no per-file hashes). Their citation paths exist, "
            "so a superseding NC scope is needed, not a completion scope. The FNS Administrative Letters page (367 documents, 2002-2020) "
            "and FNS Change Notices page (312 documents, 2022-2026; FNS-CN-01..03-2026 carry the four revised sections as attachments) "
            "are the transmittal and change-summary families, not the manual. #680's 79 'captured' is the document count."
        ),
    },
    "us-oh": {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_administrative_code_and_emanuals",
        "primary_source_url": "https://emanuals.jfs.ohio.gov/FoodAssistance/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-oh", "document_class": "regulation", "version": "2026-07-16-agency-5101-4"},
        "index_url": "https://codes.ohio.gov/ohio-administrative-code/5101%3A4",
        "index_document_count": 82, "taken_count": 0,
        "index_families": {
            "oac_5101_4_rule_html": {"found": 82, "taken": 0, "already_in_corpus": 82},
            "emanuals_food_assistance_manual_html": {"found": 0, "taken": 0, "blocked": True},
        },
        "notes": (
            "Diagnosed 2026-09-11: #680's 82 'captured' is the rule count of the OAC 5101:4 adapter scope "
            "us-oh/regulation/2026-07-16-agency-5101-4 (93 rows: 82 rules in 9 chapters plus the agency, division and OAC container "
            "rows). The Ohio Laws and Rules site lists 9 chapters (5101:4-1 to 5101:4-9) with 82 rules; every one is in the scope and "
            "the scope has none the publisher lacks, so the OAC gap is nil and no second OAC adapter scope is built (the adapter's shared "
            "container rows would collide across scopes in release validation). A per-rule revision check was not completed: "
            "codes.ohio.gov rate-limited the rule pages (HTTP 429) after 21 of 82. The SNAP-governing manual family is the ODJFS "
            "eManuals Food Assistance manual, and that host does not answer from this network: emanuals.jfs.ohio.gov (156.63.50.60) "
            "TCP connect timeout to the plain Axiom request (requests ConnectTimeout after 20.7 s) and to curl-cffi chrome120 browser "
            "impersonation (curl 28, 20.0 s); the legacy host emanuals.odjfs.state.oh.us (156.63.65.106) also times out after 20 s. "
            "No index inventory of the manual is possible; no workaround attempted. When the host answers, inventory the Food "
            "Assistance manual as a new us-oh manual scope."
        ),
    },
    "us-mt": {
        "queue_status": "done",
        "source_kind": "official_pdf_manual_sections",
        "primary_source_url": "https://dphhs.mt.gov/hcsd/Manuals/snapmanual",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-mt", "document_class": "manual", "version": "2026-07-17-mt-snap-policy-manual"},
        "index_url": "https://dphhs.mt.gov/hcsd/Manuals/snapmanual",
        "index_document_count": 90, "taken_count": 0,
        "index_families": {
            "snap_policy_manual_section_pdf": {"found": 82, "taken": 0, "already_in_corpus": 82},
            "other_program_manual_and_site_pdf": {"found": 8, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-11: the DPHHS SNAP policy manual page links 90 PDFs: 82 SNAP manual sections (TOC, index, "
            "introduction, sections 100-1900 and appendices), all in manifests/us-mt-snap-manual.yaml and the released scope "
            "us-mt/manual/2026-07-17-mt-snap-policy-manual (435 provisions, coverage complete), plus 8 non-SNAP documents (Commodity "
            "Supplemental Food Program, CSBG, ESG, LIHEAP and Weatherization manuals, the TANF State Plan, a sign-language interpreter "
            "list and a state privacy notice). All 83 released files were re-fetched and are byte-identical to the released inventory "
            "(SHA-256), so nothing is revised; the 83rd, SNAP 1704.1 Nutrition Education Programs, is no longer linked from the index but "
            "still answers HTTP 200 at its released URL. Nothing new to take. #680's 83 'captured' is the document count."
        ),
    },
    "us-ok": {
        "queue_status": "done",
        "source_kind": "official_rules_api_and_agency_appendices",
        "primary_source_url": "https://rules.ok.gov/home",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ok", "document_class": "regulation", "version": "2026-07-21-ok-snap-rules"},
        "index_url": "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=340&chapterNum=50",
        "index_document_count": 11, "taken_count": 0,
        "index_families": {
            "oac_340_50_chapter_api_response_json": {"found": 1, "taken": 0, "already_in_corpus": 1},
            "okdhs_snap_appendix_document": {"found": 7, "taken": 0, "already_in_corpus": 7, "revised_edition_since_release": 1},
            "oac_dependency_chapter_api_response_json": {"found": 3, "taken": 0, "already_in_corpus": 3},
        },
        "notes": (
            "Index confirmed 2026-09-11: the Oklahoma Secretary of State rules site (rules.ok.gov/home) answers HTTP 403 to both the "
            "plain Axiom request and curl-cffi chrome120 impersonation, but its own production API, the released scope's download_url, "
            "answers: GetSegmentsByChapterNum for OAC 340 Chapter 50 returns 205 segments (1 chapter, 9 subchapters, 19 parts, 162 "
            "sections, 14 appendices). 77 sections are active (statusName Undefined) and all 77 are in "
            "us-ok/regulation/2026-07-21-ok-snap-rules (78 rows with the chapter root; 340:50-5-7.1, 5-10.1 and 5-64.1 are held as "
            "340-50-5-7.1 etc.); the other 85 sections (80 Revoked, 5 Reserved) and the 14 appendices (all Revoked) carry no text and are "
            "excluded by the released extraction's json_record_exclude_statuses. The supporting policy scope "
            "us-ok/policy/2026-07-21-ok-snap-policy holds the seven OKDHS appendix documents (B-2, C-1, C-3 PDF, C-3 landing page and "
            "allotment-table data, C-3-A, D-4-C) and the Chapter 2, 10 and 65 dependency API responses; oklahoma.gov's OKDHS policy "
            "library now redirects to rules.ok.gov (HTTP 403), so the appendices have no reachable HTML index and were verified "
            "document by document. Reviewer: D-4-C is a revised edition (new SHA-256, Last-Modified 2026-08-28); the C-3 landing page "
            "differs only in the site menu, the C-3 table is still the 10/01/2025 edition (no 10012026 page yet, HTTP 404), and the "
            "three dependency-chapter API responses are content-identical to the released files. D-4-C's citation path exists, so a "
            "superseding OK policy scope is needed. Nothing new to take. #680's 87 'captured' is 77 sections plus the policy rows."
        ),
    },
    "us-ga": {
        "queue_status": "done",
        "source_kind": "official_html_manual",
        "primary_source_url": "https://pamms.dhs.ga.gov/dfcs/snap/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ga", "document_class": "manual", "version": "2026-05-27-ga-snap-manual-r2026-07-15-self-contained"},
        "index_url": "https://pamms.dhs.ga.gov/dfcs/snap/",
        "index_document_count": 369, "taken_count": 0,
        "index_families": {
            "snap_manual_section_html": {"found": 82, "taken": 0, "already_in_corpus": 82, "revised_edition_since_release": 16},
            "snap_manual_appendix_html": {"found": 14, "taken": 0, "already_in_corpus": 14, "revised_edition_since_release": 2},
            "snap_manual_appendix_table_pdf": {"found": 4, "taken": 0, "already_in_corpus": 4},
            "manual_transmittal_cover_letter_pdf": {"found": 87, "taken": 0},
            "manual_form_attachment_pdf": {"found": 181, "taken": 0},
            "manual_landing_html": {"found": 1, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-11: the DHS PAMMS SNAP Policy Manual index links 369 distinct dfcs/snap URLs: 82 policy sections "
            "(3000-3810), 14 appendix pages (A, B hearings set, D, E glossary, F forms TOC, J, L) and 4 Appendix A BOI table PDFs, all "
            "100 in manifests/us-ga-snap-manual.yaml and the released scope us-ga/manual/2026-05-27-ga-snap-manual-r2026-07-15-self-contained "
            "(1,214 provisions, coverage complete); 87 Manual Transmittal cover letters (MT 1-87, the change-summary family); 181 form "
            "attachments under Appendix F (applications, notices and verification forms in 16 languages, the form family); and the "
            "landing page. Nothing new to take. Reviewer: Manual Transmittal 87 (dated June 1, 2026, after the released 2026-05-27 "
            "scope) revised sections 3035, 3105, 3110, 3205, 3335, 3350, 3405, 3420, 3515, 3614, 3617, 3710, 3715, 3725, 3730 and 3805 "
            "and Appendices E and F (18 items); their citation paths exist, so a superseding GA scope is needed (MT 86 of January 3, 2026 "
            "and MT 85 of November 1, 2025 predate the release). #680's 110 'captured' is the document count plus queue rows."
        ),
    },
    "us-tn": {
        "queue_status": "done",
        "source_kind": "official_publications_page",
        "primary_source_url": "https://www.tn.gov/humanservices/information-and-resources/dhs-publications.html",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-tn", "document_class": "manual", "version": "2026-05-27-tn-snap-policies-r2026-07-15-self-contained"},
        "index_url": "https://www.tn.gov/humanservices/information-and-resources/dhs-publications.html",
        "index_document_count": 106, "taken_count": 0,
        "index_families": {
            "snap_policy_manual_section_pdf": {"found": 27, "taken": 0, "already_in_corpus": 27, "revised_edition_since_release": 1},
            "other_dhs_publication_pdf": {"found": 79, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-11 (borderline state, re-checked against the publisher, not the threshold): the TDHS Publications "
            "page links 106 PDFs; the 27 SNAP policy sections 24.00-24.31 are all in manifests/us-tn-snap-policies.yaml and the released "
            "scope us-tn/manual/2026-05-27-tn-snap-policies-r2026-07-15-self-contained (233 provisions, coverage complete); the other 79 "
            "are Families First, child care, child support, APS and agency publications. The SNAP resource-library page lists 11 "
            "customer flyers and checklists (no policy). Nothing new to take. Reviewer: 24.31 Tennessee Summer Nutrition Initiative is a "
            "revised edition (Last-Modified 2026-06-01, after the release; the other 26 files are dated 2026-04-24 and unchanged); its "
            "citation path exists, so a superseding TN scope is needed. The TN regulation scope (Tenn. Comp. R. & Regs. 1240-01) is "
            "republished by Cornell LII (primary_source false); a primary Secretary of State edition is a separate follow-on family. "
            "#680's 180 'captured' is the manual plus regulation section count; the manual is complete, as the issue noted."
        ),
    },
    "us-mi": {
        "queue_status": "done",
        "source_kind": "official_pdf_manual_tree",
        "primary_source_url": "https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/000.pdf",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-mi", "document_class": "manual", "version": "2026-07-17-mi-bridges-manual"},
        "index_url": "https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/000.pdf",
        "index_document_count": 639, "taken_count": 0,
        "index_families": {
            "bem_chapter_pdf": {"found": 129, "taken": 0, "already_in_corpus": 129, "revised_edition_since_release": 5},
            "bam_chapter_pdf": {"found": 56, "taken": 0, "already_in_corpus": 56, "revised_edition_since_release": 3},
            "rft_reference_table_pdf": {"found": 22, "taken": 0, "already_in_corpus": 7},
            "rfs_reference_schedule_pdf": {"found": 8, "taken": 0, "already_in_corpus": 2},
            "bpg_glossary_pdf": {"found": 1, "taken": 0, "already_in_corpus": 1},
            "bpb_bulletin_log_pdf": {"found": 1, "taken": 0, "already_in_corpus": 1, "revised_edition_since_release": 1},
            "bpb_policy_bulletin_pdf": {"found": 422, "taken": 0},
        },
        "notes": (
            "Index confirmed 2026-09-11 (borderline state, re-checked against the publisher): the current BEM 000 (BPB 2026-024, "
            "8-1-2026) and BAM 000 (BPB 2026-023, 8-1-2026) tables of contents list 128 BEM and 55 BAM chapters; with the two TOCs, all "
            "185 are in manifests/us-mi-bridges-manual.yaml and the released scope us-mi/manual/2026-07-17-mi-bridges-manual (2,310 "
            "provisions, coverage complete), as are the BPG glossary, the BPB bulletin log and 7 of the 22 RFT reference tables (000, "
            "248 SSI payment levels, 250 FAP income limits, 255 food assistance standards, 260 issuance table, 262 restaurants, 295 "
            "combined budget tables) and 2 of the 8 RFS schedules (000, 305 transaction deadlines and issuance schedule); the 15 other RFT "
            "tables (zip codes, MA shelter areas, FIP/RCA/SDA payment standards, MA income levels, CDC scale, exam fees) and 6 other RFS "
            "schedules (SSI payroll, home help, APS, Great Start, foster care, independent living) are other programs' tables, as the "
            "released row decided. The bulletin log lists 422 Bridges Policy Bulletins (BPB/<year>-<nnn>.pdf), the change-summary "
            "family. Nothing new to take. Reviewer: the six August 2026 bulletins (BPB 2026-019 to 2026-024, after the released "
            "2026-07-01 TOC edition) revised BEM 106, 230B, 554 and 630, BAM 220 and 401E, both TOCs and the log (9 revised editions); "
            "RFT 000 (RFB 2026-006, 5-1-2026) and RFS 000 (RFB 2026-003, 1-1-2026) are the released editions. Their citation paths "
            "exist, so a superseding MI scope is needed. #680's 196 'captured' is the document count; the manual is complete."
        ),
    },
    "us-az": {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_html_manual",
        "primary_source_url": "https://dbmefaapolicy.azdes.gov/FAA5.html",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-az", "document_class": "manual", "version": "2025-10-30-az-des-faa5-manual-r2026-07-15-self-contained"},
        "index_url": "https://dbmefaapolicy.azdes.gov/FAA5.html",
        "index_document_count": None, "taken_count": 0,
        "index_families": {},
        "notes": (
            "Blocked 2026-09-10 (batch 2, first probe): the DES FAA policy manual host dbmefaapolicy.azdes.gov answers HTTP 403 with a "
            "5,675-byte page to the plain Axiom request and HTTP 403 with a 5,995-byte F5/TSPD JavaScript bot-challenge page to curl-cffi "
            "chrome120 browser impersonation (20 s timeouts). No workaround attempted; the released scope's archived-snapshot captures "
            "(web.archive.org download_url) are not an option for new documents under this run's rules. The released scopes hold 80 FAA5 "
            "manual pages (2025-10-30, 7 provisions) and the FAA5 recovery scope (143 provisions); #680's 7 'captured' reflects that thin "
            "release. ID was taken as the replacement state. Re-probed 2026-09-11 (batch 3, US network, 20 s timeouts, one plain request "
            "and one browser-impersonation request): HTTP 403 with a 5,654-byte page after 6.7 s and HTTP 403 with a 5,995-byte TSPD "
            "challenge page after 2.0 s; still blocked."
        ),
    },
    "us-ny": {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_pdf_manuals",
        "primary_source_url": "https://otda.ny.gov/programs/snap/",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-ny", "document_class": "manual", "version": "2026-07-17-ny-snap-manuals"},
        "index_url": "https://otda.ny.gov/programs/snap/",
        "index_document_count": None, "taken_count": 0,
        "index_families": {},
        "notes": (
            "Blocked 2026-09-10 (batch 1, first network): otda.ny.gov reset the plain Axiom request (curl 56) and answered curl-cffi "
            "chrome120 impersonation with a 5,609-byte F5/TSPD JavaScript bot-challenge page. Retried 2026-09-10 (batch 2, US network, "
            "20 s timeouts, one plain request and one browser-impersonation request): the plain request is closed without a response "
            "(requests ConnectionError: RemoteDisconnected('Remote end closed connection without response') after 0.7 s); "
            "curl-cffi chrome120 gets HTTP 200 carrying a 7,562-byte TSPD bot-challenge page instead of the SNAP program page. No "
            "index inventory is possible; no workaround attempted. The released scopes already hold the 576-page SNAP Source Book, "
            "the 16-part Employment Policy Manual (340 provisions) and 18 NYCRR Parts 385 and 387 (1,678 provisions); #680's 18 "
            "'captured' is a document count. OTDA policy directives (ADM/INF/GIS) remain a separate family to inventory when the host answers. "
            "Re-probed 2026-09-11 (batch 3, US network, 20 s timeouts): the plain request is reset (requests ConnectionError: "
            "ConnectionResetError(54, 'Connection reset by peer') after 3.2 s); curl-cffi chrome120 gets HTTP 200 with a 7,355-byte "
            "TSPD challenge page (/TSPD/... scripts) after 2.6 s; still blocked."
        ),
    },
}


RUN_NOTE_SUPERSEDE = "docs/ingest-runs/2026-09-11-snap-superseding-scopes-batch-1.md"
SUPERSEDE_NOTE = (
    "Superseding batch 1 (2026-09-11, US network): the revised editions recorded by batches 1-3 for NC, GA, TN, OK, MI and KY "
    "were taken as whole-manual re-extractions of the released manifests under new version strings "
    "2026-09-11-<state>-snap-manual-supersede (released scopes untouched; the next selector swaps the released version for the "
    "superseding one). Document-level citation paths are identical to the released scopes; page/block sub-paths move where a "
    "revised edition changed its page or block count. See " + RUN_NOTE_SUPERSEDE + "."
)
# Applied after the batch-3 static rows: keys are merged into the row and `notes_suffix` is appended to the row's notes.
SUPERSEDING_SCOPES: dict[str, dict[str, Any]] = {
    "us-nc": {
        "superseding_manifest": "manifests/us-nc-fns-manuals.yaml",
        "superseding_scope": {"jurisdiction": "us-nc", "document_class": "manual", "version": "2026-09-11-nc-snap-manual-supersede"},
        "superseding_queue_status": "agent_ready",
        "notes_suffix": (
            " Superseded 2026-09-11: us-nc/manual/2026-09-11-nc-snap-manual-supersede (79 documents, 725 provisions, coverage complete) "
            "re-extracts the whole manifest with FNS 212, 215, 340 and 515 pointed at the August 2026 files (expression dates "
            "2026-08-17, 2026-08-04, 2026-08-04, 2026-08-13); the other 75 documents extract byte-identically to the released scope. "
            "Sub-paths: FNS 212 gains page-10..12, FNS 340 loses page-29."
        ),
    },
    "us-ga": {
        "superseding_manifest": "manifests/us-ga-snap-manual.yaml",
        "superseding_scope": {"jurisdiction": "us-ga", "document_class": "manual", "version": "2026-09-11-ga-snap-manual-supersede"},
        "superseding_queue_status": "agent_ready",
        "notes_suffix": (
            " Superseded 2026-09-11: us-ga/manual/2026-09-11-ga-snap-manual-supersede (100 documents, 1,207 provisions, coverage "
            "complete). The 18 MT 87 items carry 2026-06-01; 3025 (ADA and Section 504) is a further revised edition not on MT 87 "
            "(DFCS Civil Rights Policy Manual policy 3601, effective June 15, 2026; expression date 2026-06-15); 3030 differs only by "
            "two backtick characters around its policy number (dates unchanged); the other 80 documents extract byte-identically. "
            "Sub-paths: 3025 collapses from 24 to 10 blocks; 3205, 3335, 3405, 3515, 3614, 3715 and 3805 gain one block each. "
            "Release validation flagged 3614/block-12 against the released us-ga/manual/2026-07-13-recovery-r2026-07-17-dedup scope "
            "(an orphan July page-split fragment of 3614 that survived the July dedup because the May edition had 11 blocks); "
            "its 12-row successor us-ga/manual/2026-07-13-recovery-r2026-07-17-dedup-r2026-09-11-snap-supersede-dedup drops that "
            "fragment (scripts/consolidate_release_scopes.py, --include-citation-from for the other 12 rows) and the selector "
            "swaps both Georgia scopes."
        ),
        "superseding_companion_scope": {
            "jurisdiction": "us-ga", "document_class": "manual",
            "version": "2026-07-13-recovery-r2026-07-17-dedup-r2026-09-11-snap-supersede-dedup",
            "replaces": "2026-07-13-recovery-r2026-07-17-dedup",
        },
    },
    "us-tn": {
        "superseding_manifest": "manifests/us-tn-snap-policies.yaml",
        "superseding_scope": {"jurisdiction": "us-tn", "document_class": "manual", "version": "2026-09-11-tn-snap-manual-supersede"},
        "superseding_queue_status": "agent_ready",
        "notes_suffix": (
            " Superseded 2026-09-11: us-tn/manual/2026-09-11-tn-snap-manual-supersede (27 documents, 233 provisions, coverage "
            "complete, citation-path set identical to the released scope). 24.31 carries 2026-06-01 (effective June 1, 2026; last "
            "review May 26, 2026); the other 26 sections extract byte-identically."
        ),
    },
    "us-ok": {
        "superseding_manifest": "manifests/us-ok-snap-policy.yaml",
        "superseding_scope": {"jurisdiction": "us-ok", "document_class": "policy", "version": "2026-09-11-ok-snap-manual-supersede"},
        "superseding_queue_status": "agent_ready",
        "notes_suffix": (
            " Superseded 2026-09-11: us-ok/policy/2026-09-11-ok-snap-manual-supersede (10 documents, 113 provisions, coverage "
            "complete, citation-path set identical). Appendix D-4-C is a new file (Last-Modified 2026-08-28, source_as_of updated) "
            "whose extracted text is identical to the released edition, still dated 7/9/2025 on its pages (expression date kept); "
            "all ten documents extract byte-identically, the C-3 landing page again differing only in raw site menu HTML."
        ),
    },
    "us-mi": {
        "superseding_manifest": "manifests/us-mi-bridges-manual.yaml",
        "superseding_scope": {"jurisdiction": "us-mi", "document_class": "manual", "version": "2026-09-11-mi-snap-manual-supersede"},
        "superseding_queue_status": "agent_ready",
        "notes_suffix": (
            " Superseded 2026-09-11: us-mi/manual/2026-09-11-mi-snap-manual-supersede (196 documents, 2,317 provisions, coverage "
            "complete). 20 files changed since the released 2026-07-17 fetch, not 9: the nine August bulletins items (BEM 000, 106, "
            "230B, 554, 630, BAM 000, 220, 401E, BPB log; BPB 2026-019 to -024, effective 8-1-2026) plus eleven chapters re-served on "
            "2026-07-20 as their BPB 2026-006/2026-007 editions (BAM 120, 200; BEM 171, 227, 400, 405, 500, 503, 550, 617, 800; "
            "effective 3-1-2026 and 4-1-2026, later than the editions the released scope held). source_revision, source_sha256, "
            "source_as_of (Last-Modified) and expression_date (bulletin effective date) updated for all 20; the other 176 documents "
            "extract byte-identically. Sub-paths: BEM 106 loses page-11; BAM 220, BAM 401E, BEM 500 and BEM 503 gain pages."
        ),
    },
    "us-ky": {
        "superseding_manifest": "manifests/us-ky-snap-manual.yaml",
        "superseding_scope": {"jurisdiction": "us-ky", "document_class": "manual", "version": "2026-09-11-ky-snap-manual-supersede"},
        "superseding_queue_status": "agent_ready",
        "notes_suffix": (
            " Superseded 2026-09-11: us-ky/manual/2026-09-11-ky-snap-manual-supersede (2 documents, 405 provisions, coverage "
            "complete) re-extracts Volumes II and IIA; the batch-2 completion scope (Volume I) is unaffected. Volume II moved again "
            "after the batch-2 probe: OMTL-708, sections revised through R. 9/1/26, Last-Modified 2026-09-11 (released OMTL-701); "
            "Volume IIA is OMTL-707, R. 9/1/26, Last-Modified 2026-09-09 (released OMTL-683). Sub-paths: Volume II gains "
            "page-347..349, Volume IIA gains page-53..54."
        ),
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append", default=[], metavar="JURISDICTION",
                        help="restrict live builders to these jurisdictions (static rows are still applied)")
    parser.add_argument("--static-only", action="store_true",
                        help="apply only the static rows (batch 3 built no scope); no live builder runs and no manifest is written")
    parser.add_argument("--corpus-base", type=Path, default=None,
                        help="corpus root whose provisions JSONL are scanned for citation paths that already exist "
                             "(skipped and recorded); omit in a sparse worktree without data/corpus")
    args = parser.parse_args()
    corpus_base = args.corpus_base
    if corpus_base is not None and not (corpus_base / "provisions").is_dir():
        print(f"--corpus-base {corpus_base} has no provisions directory", file=sys.stderr)
        return 1

    queue = yaml.safe_load(QUEUE.read_text()) if QUEUE.exists() else {
        "version": "2026-09-10",
        "document_family": "state_snap_policy_sources",
        "program": "SNAP",
        "queue_status": "in_progress",
        "policy": {
            "canonical_pipeline": "source-first",
            "source_policy": "primary_official_only",
            "durable_artifacts": ["sources", "inventory", "provisions", "coverage"],
            "forbidden_sources": ["secondary summaries", "State Options Reports", "benefitswiki",
                                  "policy manuals reposted by non-government sites", "mirrors, proxies and archived copies of blocked publishers"],
            "notes": [
                f"Completion pass for {ISSUE} (SNAP discovery missed ~24 states). The 51-row manifests/state-snap-manual-agent-queue.yaml "
                "stays as released; this queue tracks the per-state completion rows.",
                "Released SNAP scopes are immutable. Missing documents go into new per-state scopes, version "
                f"{VERSION}, manifests/us-xx-snap-manual-completion.yaml, document_class per the state's existing convention.",
                "A release rejects duplicate citation paths across scopes: every new document's citation path is checked against every "
                "provisions JSONL of its jurisdiction before it is taken.",
            ],
        },
        "states": [],
    }
    rows = {s["jurisdiction"]: s for s in queue.get("states", [])}
    summary: dict[str, Any] = {}
    built: set[str] = set()
    for jur, build in BUILDERS.items():
        if args.static_only or (args.only and jur not in args.only):
            continue
        docs, info = build()
        if not docs:
            print(f"{jur}: no documents found; index layout changed?", file=sys.stderr)
            return 1
        in_corpus = corpus_citation_paths(corpus_base, jur)
        skipped = sorted(d["citation_path"] for d in docs if d["citation_path"] in in_corpus)
        if skipped:
            docs = [d for d in docs if d["citation_path"] not in in_corpus]
            info["families"]["citation_path_already_in_corpus"] = {"found": len(skipped), "taken": 0}
            info["citation_paths_already_in_corpus"] = skipped
            print(f"{jur}: {len(skipped)} citation paths already in the corpus, skipped: {skipped[:10]}", file=sys.stderr)
        paths = [d["citation_path"] for d in docs]
        if len(set(paths)) != len(paths):
            dupes = sorted({p for p in paths if paths.count(p) > 1})
            print(f"{jur}: duplicate citation paths {dupes}", file=sys.stderr)
            return 1
        stem = f"{jur}-snap-manual-completion"
        (ROOT / "manifests" / f"{stem}.yaml").write_text(
            yaml.safe_dump({"version": VERSION, "documents": docs}, sort_keys=False, allow_unicode=True, width=120))
        found = sum(f["found"] for f in info["families"].values())
        taken = sum(f["taken"] for f in info["families"].values())
        summary[jur] = {"documents": len(docs), **info}
        row = rows.get(jur) or {"jurisdiction": jur, "name": NAMES[jur]}
        row.update({
            "name": NAMES[jur], "queue_status": "agent_ready", "source_kind": SOURCE_KIND[jur],
            "primary_source_url": info["index_url"], "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": docs[0]["document_class"], "version": VERSION},
            "index_url": info["index_url"], "index_document_count": found, "taken_count": taken,
            "index_families": info["families"],
            "notes": (f"Batch {BATCH[jur]} (2026-09-10, #680): {len(docs)} documents taken from the publisher's own index ({found} documents "
                      f"inventoried across {len(info['families'])} families; {taken} taken; citation paths checked against every "
                      f"{jur} provisions file{' in ' + str(corpus_base) if corpus_base else ''}). Extraction proven with the "
                      f"official-documents extractor; see {RUN_NOTE if BATCH[jur] == 1 else RUN_NOTE_BATCH2}."),
        })
        rows[jur] = row
        built.add(jur)
        print(f"{jur}: {len(docs)} documents; index families {info['families']}")
    for jur, static in {**STATIC_ROWS, **STATIC_ROWS_BATCH2, **STATIC_ROWS_BATCH3}.items():
        if jur in BUILDERS:
            continue  # a live-built state (KY in batch 2) keeps its generated row; the batch-1 KY/NY static rows are superseded
        row = rows.get(jur) or {"jurisdiction": jur, "name": NAMES[jur]}
        row.update({"name": NAMES[jur], **static})
        rows[jur] = row
    for jur, overlay in SUPERSEDING_SCOPES.items():
        row = rows[jur]
        suffix = overlay["notes_suffix"]
        row.update({key: value for key, value in overlay.items() if key != "notes_suffix"})
        if suffix.strip() not in (row.get("notes") or ""):
            row["notes"] = (row.get("notes") or "").rstrip() + suffix
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    for note in (BATCH_NOTE, BATCH2_NOTE, BATCH3_NOTE, SUPERSEDE_NOTE):
        if note not in notes:
            notes.append(note)
    queue["states"] = [rows[j] for j in sorted(rows)]
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue["queue_status"] = "in_progress"
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(json.dumps(summary, indent=1))
    print(f"queue {queue['status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
