"""Build SSA POMS official-document manifests (part SI for SSI, part HI for
Medicare) from the publisher's own table of contents, and update the program
agent queues.

Primary official source: SSA Program Operations Manual System (POMS), public site
https://secure.ssa.gov/poms.nsf/. Each part has a chapter list
(``chapterlist!openview&restricttocategory=<category>``: 05 for part SI, 06 for
part HI); each chapter links to a subchapter list that enumerates every section
(national and regional) with its ``lnx`` URL. This script reads those index
pages, selects the subchapters of one family (``FAMILIES``), fetches each taken
section page once to read its printed "Effective Dates" start date and
transmittal ("TN") line, and writes one manifest document per section with
citation path ``us/manual/ssa/poms/<part>/<section number>``.

Families (``--family``):

* ``si-core`` (default): the 2026-09-10 SSI run, the bounded encoder-relevant set
  ``TAKEN_SUBCHAPTERS`` (23 subchapters, 915 sections), version
  ``2026-09-10-ssi-poms-si``; also rewrites the SSI state rows of the queue.
* ``si-remainder``: the 2026-09-13 closure run, every other part SI subchapter
  (56 subchapters), version ``2026-09-13-ssi-poms-si-remainder``. Citation paths
  are section numbers, so the two SI scopes share no path and both can sit in one
  release selector; the extractor emits no part- or chapter-level container rows.
* ``hi``: the 2026-09-13 closure run, the whole of part HI (Health Insurance:
  Medicare entitlement, SMI enrollment, state buy-in, premiums, IRMAA, Part D
  Extra Help), version ``2026-09-13-medicare-poms-hi``.

Section pages are cached under ``--cache-dir`` (default ``~/.axiom/poms-<part>-cache``)
so the script can be re-run without re-fetching; the corpus extractor still
re-fetches every page itself when it snapshots the source.

    uv run python scripts/build_ssi_poms_si_manifests.py [--family si-core|si-remainder|hi]
        [--print-index] [--skip-queue]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://secure.ssa.gov"
CHAPTER_LIST_URL = f"{HOST}/poms.nsf/chapterlist!openview&restricttocategory={{category}}"
SUBCHAPTER_URL = f"{HOST}/apps10/poms.nsf/subchapterlist!openview&restricttocategory={{chapter}}"
# POMS part -> (chapter-list category, program the queue tracks)
PARTS = {"SI": ("05", "SSI"), "HI": ("06", "MEDICARE")}
VERSION = "2026-09-10-ssi-poms-si"
SOURCE_AS_OF = "2026-09-10"
INDEX_URL = CHAPTER_LIST_URL.format(category="05")
MANIFEST = ROOT / "manifests" / "us-ssa-poms-si-2026-09-10.yaml"
QUEUE = ROOT / "manifests" / "ssi-agent-queue.yaml"
MEDICARE_QUEUE = ROOT / "manifests" / "medicare-agent-queue.yaml"
USER_AGENT = "axiom-corpus/0.1 (source discovery; https://github.com/TheAxiomFoundation/axiom-corpus)"

# Reviewer judgment (2026-09-10): the bounded, encoder-relevant SI family. The work
# order minimum is SI 00501, 00810, 00820, 00830, 01110, 01120, 01130, 01310, 01320,
# 02001 and all of SI 014 (01400-01415). Added because PolicyEngine-US SSI variables
# cite them and they carry parameter values: SI 00502 (alien eligibility), SI 00520
# (institutionalization, the $30 payment cases), SI 00815 (what is not income),
# SI 00835 (living arrangements and in-kind support and maintenance), SI 01140
# (countable resources), SI 01330 (deeming of resources), SI 02005 (computation of
# benefits). Every section the subchapter list enumerates for a taken subchapter is
# taken, including regional (BOS/CHI/DAL/DEN/NY/PHI/SEA/SF...) sections and the
# ``.000`` table-of-contents section, so taken_count equals the index count.
TAKEN_SUBCHAPTERS = (
    "SI 00501", "SI 00502", "SI 00520",
    "SI 00810", "SI 00815", "SI 00820", "SI 00830", "SI 00835",
    "SI 01110", "SI 01120", "SI 01130", "SI 01140",
    "SI 01310", "SI 01320", "SI 01330",
    "SI 01400", "SI 01401", "SI 01403", "SI 01405", "SI 01410", "SI 01415",
    "SI 02001", "SI 02005",
)


@dataclass(frozen=True)
class Family:
    """One POMS extraction scope: a part, the subchapters it takes (None = every
    subchapter the chapter list enumerates; ``exclude`` removes the ones another
    scope already holds), and the version, manifest and dates it is written with."""

    name: str
    part: str
    version: str
    source_as_of: str
    manifest: str
    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] = ()
    discovered_via: str = "manual-review:ssi-agent-queue; SSA POMS SI table of contents"

    @property
    def category(self) -> str:
        return PARTS[self.part][0]

    @property
    def program(self) -> str:
        return PARTS[self.part][1]

    @property
    def index_url(self) -> str:
        return CHAPTER_LIST_URL.format(category=self.category)

    @property
    def manifest_path(self) -> Path:
        return ROOT / "manifests" / self.manifest

    def takes(self, subchapter: str) -> bool:
        if subchapter in self.exclude:
            return False
        return self.include is None or subchapter in self.include


FAMILIES = {
    "si-core": Family(
        name="si-core", part="SI", version=VERSION, source_as_of=SOURCE_AS_OF,
        manifest=MANIFEST.name, include=TAKEN_SUBCHAPTERS,
    ),
    # 2026-09-13 closure run (docs/coverage/needs-closure-2026-09-11/ssi.md, SSI-F-POMS-*):
    # the 56 part SI subchapters the 2026-09-10 scope did not take.
    "si-remainder": Family(
        name="si-remainder", part="SI", version="2026-09-13-ssi-poms-si-remainder",
        source_as_of="2026-09-13", manifest="us-ssa-poms-si-remainder-2026-09-13.yaml",
        exclude=TAKEN_SUBCHAPTERS,
        discovered_via="manual-review:ssi-agent-queue; needs-closure-2026-09-11 SSI-F-POMS; SSA POMS SI table of contents",
    ),
    # 2026-09-13 closure run (medicare.md, MED-F-POMS-HI-*): the whole of part HI.
    "hi": Family(
        name="hi", part="HI", version="2026-09-13-medicare-poms-hi", source_as_of="2026-09-13",
        manifest="us-ssa-poms-hi-2026-09-13.yaml",
        discovered_via="manual-review:medicare-agent-queue; needs-closure-2026-09-11 MED-F-POMS-HI; SSA POMS HI table of contents",
    ),
}

EXTRACTION = {
    # the section body; excludes the Effective Dates breadcrumb, Previous/Next links
    # and the "To Link to this section" footer table
    "html_content_selector": "div.poms",
    # p.tninfo: transmittal line, e.g. "TN 63 (11-23)"; kept in metadata.transmittal instead.
    # div.poms-citation: the "CITATIONS:" box; its Act/CFR references sit in <div> nodes the
    # extractor does not read, so without the drop it yields an empty "CITATIONS:" block.
    "html_drop_selectors": ["p.tninfo", "div.poms-citation"],
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# Optional state supplement administration, transcribed by the agent from POMS
# SI 01415.010 (TN 26, effective 09/23/2015; column "Optional") and cross-checked
# against SI 01415.058 (TN 95, January 2026 federally administered programs:
# CA, DE, DC, HI, IA, MI, MT, NV, NJ, PA, RI, VT). F = SSA administers,
# F/S = SSA and the state, S = state administers, N = no optional program.
OPTIONAL_ADMIN = {
    "AL": "S", "AK": "S", "AZ": "N", "AR": "N", "CA": "F", "CO": "S", "CT": "S", "DE": "F/S",
    "DC": "F/S", "FL": "S", "GA": "S", "HI": "F", "ID": "S", "IL": "S", "IN": "S", "IA": "F/S",
    "KS": "S", "KY": "S", "LA": "S", "ME": "S", "MD": "S", "MA": "S", "MI": "F/S", "MN": "S",
    "MS": "N", "MO": "S", "MT": "F", "NE": "S", "NV": "F", "NH": "S", "NJ": "F", "NM": "S",
    "NY": "S", "NC": "S", "ND": "N", "OH": "S", "OK": "S", "OR": "S", "PA": "F/S", "RI": "F/S",
    "SC": "S", "SD": "S", "TN": "N", "TX": "S", "UT": "S", "VT": "F", "VA": "S", "WA": "S",
    "WV": "N", "WI": "S", "WY": "S",
}

# SI 01415.058 subsection letter per federally administered state (page anchors).
SI_01415_058_ANCHOR = {
    "CA": "b", "DE": "c", "DC": "d", "HI": "e", "IA": "f", "MI": "g", "MT": "h", "NV": "i",
    "NJ": "j", "PA": "k", "RI": "l", "VT": "m",
}

# Regional POMS sections in the taken family that describe one state's supplement
# (from the SI 01415 / SI 01401 subchapter lists; parenthetical state tags or titles).
REGIONAL_STATE_SECTIONS = {
    "CA": ["SI SF01415.100", "SI SF01415.110", "SI SF01415.120", "SI SF01415.130", "SI SF01415.140",
           "SI SF01415.150", "SI SF01415.160", "SI SF01415.170", "SI SF01415.180", "SI SF01415.190"],
    "DE": ["SI PHI01415.008"],
    "DC": ["SI PHI01415.009"],
    "HI": ["SI SF01415.200", "SI SF01415.210", "SI SF01415.220"],
    "IL": ["SI CHI01401.002"],
    "IN": ["SI CHI01401.001"],
    "ME": ["SI BOS01415.010", "SI BOS01415.910"],
    "MA": ["SI BOS01415.024", "SI BOS01415.930"],
    "MI": ["SI CHI01415.001"],
    "MT": ["SI DEN01415.010"],
    "NV": ["SI SF01415.300"],
    "NJ": ["SI NY01415.025"],
    "NY": ["SI NY01415.026"],
    "PA": ["SI PHI01415.010"],
    "RI": ["SI BOS01415.012", "SI BOS01415.950"],
    "SD": ["SI DEN01415.011"],
    "VT": ["SI BOS01415.013", "SI BOS01415.970"],
    "WY": ["SI DEN01415.013"],
    # Seattle region (AK, ID, OR, WA) shares one regional section
    "AK": ["SI SEA01415.034"], "ID": ["SI SEA01415.034"], "OR": ["SI SEA01415.034"], "WA": ["SI SEA01415.034"],
}

# State agency index pages the agent verified on 2026-09-10 (HTTP 200 from the official
# host, page title names the program). Guessed URLs for other states returned 403/404 or
# were bot-gated, so they are deliberately not recorded; see the run note.
STATE_INDEX_URLS = {
    "WI": "https://www.dhs.wisconsin.gov/ssi/index.htm",
}
STATE_INDEX_NOTES = {
    "TX": "Lead-list HHSC handbook page H-6000 (hhs.texas.gov) answered 403 to a plain client on 2026-09-10; "
          "a future extraction needs the manifest browser_impersonation option.",
    "MN": "mn.gov/dhs answered with a Radware bot-manager challenge to a plain client on 2026-09-10.",
    "MA": "mass.gov answered 403 to a plain client on 2026-09-10.",
}

# Rows already ingested by earlier SSI state-supplement runs (docs/ingest-runs/*).
DONE_ROWS = {
    "CA": ("manifests/us-ca-ssi-state-supplement.yaml", "guidance", "2026-06-27-ca-dor-ssi-ssp-newsletter",
           "2026-06 run: California DOR January 2026 Spotlight on Social Security newsletter (SSI/SSP levels); SSA-administered levels also in POMS SI 01415.058B (federal family)."),
    "CT": ("manifests/us-ct-ssp-official-documents.yaml", "policy", "2026-07-02-ct-ssp-upm-and-standards",
           "2026-07-02 runs: CT DSS UPM 4005/4520/5000/5030/5045/5050/5520/6000/6005 and the 2026-01-01 program standards chart (docs/ingest-runs/2026-07-02-ct-ssp-*.md)."),
    "DC": ("manifests/us-dc-ossp-ssa-poms.yaml", "guidance", "2026-07-03-dc-ossp-ssa-poms",
           "2026-07-03 run: POMS SI 01415.058 (2026) and SI PHI01415.009 under us/guidance/ssa/poms/...; the same two sections are re-taken in the federal manual family under us/manual/ssa/poms/si/ (different citation paths, same documents)."),
    "DE": ("manifests/us-de-ssi-state-supplement-poms.yaml", "guidance", "2026-07-03-de-ssi-state-supplement-poms",
           "2026-07-03 run: POMS SI 01415.058 Delaware subsection (us-de/guidance) plus DSSM 13000 (us-de/regulation); docs/ingest-runs/2026-07-03-de-ssi-state-supplement.md."),
    "GA": ("manifests/us-ga-ssp-manual.yaml", "manual", "2026-06-24-ga-ssp",
           "2026-06 run: Georgia DFCS Medicaid Policy Manual 2578 and 2136 (us-ga/manual)."),
    "IN": ("manifests/us-in-ssp-sapn-official-documents.yaml", "manual", "2026-07-04-in-ssp-sapn",
           "2026-07-04 run: Indiana FSSA Medicaid Policy Manual Chapter 5000 (SAPN); docs/ingest-runs/2026-07-04-in-ssp-sapn.md. SSA regional description SI CHI01401.001 is in the federal family."),
    "KS": ("manifests/us-ks-sspp-guidance-official-documents.yaml", "guidance", "2026-07-04-ks-sspp-guidance",
           "2026-07-04 runs: K.S.A. 39-972 (us-ks/statute) and KHPA Policy 2007-05-01 (us-ks/guidance); docs/ingest-runs/2026-07-04-ks-sspp.md."),
}


def fetch(session: requests.Session, url: str, cache: Path | None) -> str:
    if cache is not None and cache.exists():
        return cache.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:  # transient: retry with backoff
            if attempt == 3:
                raise
            print(f"retry {attempt + 1} for {url}: {exc}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    text = resp.text
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
    return text


def read_index(session: requests.Session, cache_dir: Path, part: str = "SI") -> dict[str, dict]:
    """Return {chapter: {title, url, subchapters: {sub: {title, sections: [...]}}}}
    for one POMS part (``SI`` or ``HI``)."""
    category = PARTS[part][0]
    index_url = CHAPTER_LIST_URL.format(category=category)
    page = fetch(session, index_url, cache_dir / "index" / f"chapterlist-{category}.html")
    chapters: dict[str, dict] = {}
    for code, title in re.findall(
        rf"<div class='chaptitletoc'>{part} (\d{{3}}): <A HREF='/apps10/poms\.nsf/subchapterlist!openview"
        rf"&restricttocategory={category}\d{{3}}'>([^<]+)</A>",
        page,
    ):
        chapters[f"{part} {code}"] = {
            "title": html.unescape(title).strip(), "code": f"{category}{code}", "subchapters": {},
        }
    if len(chapters) < 10:
        raise SystemExit(f"only {len(chapters)} {part} chapters parsed from {index_url}; layout changed?")
    for _chapter, info in chapters.items():
        url = SUBCHAPTER_URL.format(chapter=info["code"])
        info["url"] = url
        body = fetch(session, url, cache_dir / "index" / f"subchapterlist-{info['code']}.html")
        current = None
        pattern = re.compile(
            rf'<div class="subchaptitle">&nbsp;({part} [A-Z]*\d+): ([^<]+)<br></div>'
            rf'|<div class="sectionTitle">({part} [A-Z]*\d+\.\d+): <A class="sectionTitle" HREF=\'([^\']+)\' target="_blank">(.*?)</A><br></div>'
        )
        for match in pattern.finditer(body):
            if match.group(1):
                current = match.group(1)
                info["subchapters"][current] = {"title": html.unescape(match.group(2)).strip(), "sections": []}
            else:
                if current is None:
                    raise SystemExit(f"section before subchapter heading in {url}")
                info["subchapters"][current]["sections"].append(
                    {
                        "section": match.group(3),
                        "url": HOST + match.group(4),
                        "title": html.unescape(re.sub(r"<[^>]+>", "", match.group(5))).strip(),
                    }
                )
    return chapters


def section_number(section: str) -> str:
    """'SI 00501.001' -> '00501.001'; 'SI CHI01415.001' -> 'chi01415.001'."""
    return section.split(" ", 1)[1].lower()


def parse_section_page(text: str) -> tuple[str | None, str | None]:
    effective = None
    match = re.search(r"Effective Dates:(?:&nbsp;|\s)*(\d{2})/(\d{2})/(\d{4})", text)
    if match:
        month, day, year = match.groups()
        effective = f"{year}-{month}-{day}"
    tn = None
    match = re.search(r'class="tninfo">([^<]*)<', text)
    if match:
        tn = html.unescape(match.group(1)).strip() or None
    return effective, tn


def build_documents(
    chapters: dict[str, dict],
    session: requests.Session,
    cache_dir: Path,
    family: Family = FAMILIES["si-core"],
) -> list[dict]:
    part = family.part
    docs: list[dict] = []
    seen: set[str] = set()
    for chapter, info in chapters.items():
        for sub, subinfo in info["subchapters"].items():
            if not family.takes(sub):
                continue
            for item in subinfo["sections"]:
                number = section_number(item["section"])
                if number in seen:
                    raise SystemExit(f"duplicate section in index: {item['section']}")
                seen.add(number)
                lnx = item["url"].rsplit("/", 1)[1]
                page = fetch(session, item["url"], cache_dir / "sections" / f"{lnx}.html")
                if 'class="poms"' not in page:
                    raise SystemExit(f"no div.poms body on {item['url']}")
                effective, tn = parse_section_page(page)
                region = re.match(rf"{part} ([A-Z]+)\d", item["section"])
                metadata = {
                    "primary_source": True,
                    "source_authority": "Social Security Administration",
                    "document_subtype": "poms_section",
                    "program": family.program,
                    "poms_part": part,
                    "poms_chapter": chapter,
                    "poms_chapter_title": info["title"],
                    "poms_subchapter": sub,
                    "poms_subchapter_title": subinfo["title"],
                    "poms_section": item["section"],
                    "poms_regional": region.group(1) if region else None,
                    "transmittal": tn,
                    "effective_date_printed": effective,
                    "index_url": family.index_url,
                    "subchapter_index_url": info["url"],
                    "source_discovery_group": f"us/manual/ssa/poms/{part.lower()}",
                    "discovered_via": family.discovered_via,
                }
                docs.append(
                    {
                        "source_id": f"ssa-poms-{part.lower()}-{number.replace('.', '-')}",
                        "jurisdiction": "us",
                        "document_class": "manual",
                        "title": f"POMS {item['section']}: {item['title']}",
                        "source_url": item["url"],
                        "source_format": "html",
                        "source_as_of": family.source_as_of,
                        "expression_date": effective or family.source_as_of,
                        "citation_path": f"us/manual/ssa/poms/{part.lower()}/{number}",
                        # secure.ssa.gov served plain requests during discovery; the option only
                        # enables the extractor's browser fallback if SSA starts rejecting them.
                        "request": {"browser_impersonation": True},
                        "extraction": EXTRACTION,
                        "metadata": {k: v for k, v in metadata.items() if v is not None},
                    }
                )
    return docs


def index_markdown(chapters: dict[str, dict], family: Family = FAMILIES["si-core"]) -> str:
    lines = ["| Chapter / subchapter | Title | Sections listed | Taken |", "| --- | --- | ---: | --- |"]
    total = taken_total = 0
    for chapter, info in chapters.items():
        count = sum(len(s["sections"]) for s in info["subchapters"].values())
        taken = sum(len(s["sections"]) for k, s in info["subchapters"].items() if family.takes(k))
        total += count
        taken_total += taken
        lines.append(f"| **{chapter}** | {info['title']} | {count} | {taken} |")
        for sub, subinfo in info["subchapters"].items():
            flag = "yes" if family.takes(sub) else ""
            lines.append(f"| {sub} | {subinfo['title']} | {len(subinfo['sections'])} | {flag} |")
    lines.append(f"| **Total** | | {total} | {taken_total} |")
    return "\n".join(lines)


def update_queue(docs: list[dict], index_count: int) -> dict:
    queue = yaml.safe_load(QUEUE.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    by_section = {d["metadata"]["poms_section"]: d["citation_path"] for d in docs}
    scope = {"jurisdiction": "us", "document_class": "manual", "version": VERSION}
    federal = rows.get("us") or {"jurisdiction": "us", "name": "Federal"}
    federal.update(
        {
            "name": "Federal",
            "queue_status": "agent_ready",
            "source_kind": "official_html_agency_manual",
            "primary_source_url": INDEX_URL,
            "target_manifest": str(MANIFEST.relative_to(ROOT)),
            "target_scope": scope,
            "index_url": INDEX_URL,
            "index_document_count": index_count,
            "taken_count": len(docs),
            "notes": (
                "SSA POMS part SI, one document per section, citation path us/manual/ssa/poms/si/<section>. "
                f"Taken subchapters: {', '.join(TAKEN_SUBCHAPTERS)} (every section the subchapter list enumerates, "
                "national and regional). Primary source confirmed from the publisher's own chapter/subchapter lists. "
                "42 USC 1381-1382j (2026-06-20 run) and the 20 CFR 416 deeming slice (2026-07-23 run, 14 rows) already exist "
                "and are not re-ingested; the rest of 20 CFR 416 remains a separate follow-up. "
                "Sibling POMS documents already under us/guidance (SI 01415.058 2026, SI PHI01415.009 from the DC run) keep "
                "their guidance citation paths; the manual family re-takes them under the section-number path."
            ),
        }
    )
    rows["us"] = federal
    for code, admin in OPTIONAL_ADMIN.items():
        if admin == "N":
            continue
        jur = f"us-{code.lower()}"
        name = STATE_NAMES[code]
        row = rows.get(jur) or {"jurisdiction": jur, "name": name, "lead_counts": {}, "candidate_sources": []}
        row["name"] = name
        regional = REGIONAL_STATE_SECTIONS.get(code, [])
        regional_paths = [by_section[s] for s in regional if s in by_section]
        federal_paths = []
        if code in SI_01415_058_ANCHOR:
            federal_paths.append(f"{by_section['SI 01415.058']} (subsection {SI_01415_058_ANCHOR[code].upper()})")
        if code in DONE_ROWS:
            manifest, doc_class, version, note = DONE_ROWS[code]
            row.update(
                {
                    "queue_status": "done",
                    "source_kind": "official_state_or_ssa_document",
                    "primary_source_url": None,
                    "target_manifest": manifest,
                    "target_scope": {"jurisdiction": "us" if code == "DC" else jur, "document_class": doc_class, "version": version},
                    "index_url": None,
                    "index_document_count": None,
                    "taken_count": None,
                    "administration": admin,
                    "notes": note + (f" Federal-family POMS paths for this state: {', '.join(federal_paths + regional_paths)}." if federal_paths or regional_paths else ""),
                }
            )
        elif admin in ("F", "F/S"):
            row.update(
                {
                    "queue_status": "agent_ready",
                    "source_kind": "ssa_poms_section",
                    "primary_source_url": f"{HOST}/apps10/poms.nsf/lnx/0501415058#{SI_01415_058_ANCHOR[code]}",
                    "target_manifest": str(MANIFEST.relative_to(ROOT)),
                    "target_scope": scope,
                    "index_url": f"{HOST}/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05014",
                    "index_document_count": 1 + len(regional),
                    "taken_count": 1 + len(regional_paths),
                    "administration": admin,
                    "notes": (
                        f"SSA administers the optional supplement (POMS SI 01415.010 column Optional = {admin}; listed in SI 01415.058A for January 2026). "
                        f"Primary source is the per-state SSA POMS text, extracted as part of the federal family: {', '.join(federal_paths + regional_paths)}. "
                        "No separate state extraction."
                        + (" F/S: the state also administers part of its program itself; that state-administered part is not covered here." if admin == "F/S" else "")
                    ),
                }
            )
        else:
            row.update(
                {
                    "queue_status": "needs_review",
                    "source_kind": "state_agency_document",
                    "primary_source_url": None,
                    "target_manifest": None,
                    "target_scope": {"jurisdiction": jur, "document_class": None, "version": None},
                    "index_url": STATE_INDEX_URLS.get(code),
                    "index_document_count": None,
                    "taken_count": 0,
                    "administration": admin,
                    "notes": (
                        "State-administered optional supplement (POMS SI 01415.010 column Optional = S). The primary source is the state "
                        "agency's own document and must be confirmed from the state's official index; not extracted in the 2026-09-10 run."
                        + (f" SSA regional description in the federal family: {', '.join(regional_paths)}." if regional_paths else "")
                        + (f" {STATE_INDEX_NOTES[code]}" if code in STATE_INDEX_NOTES else "")
                    ),
                }
            )
        rows[jur] = row
    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for row in queue["states"]:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    queue["queue_status"] = "in_progress"
    queue.setdefault("policy", {}).setdefault("notes", []).append(
        "2026-09-10 SSI run: POMS SI family manifest built by scripts/build_ssi_poms_si_manifests.py; "
        "state rows categorised from POMS SI 01415.010 / SI 01415.058 (AZ, AR, MS, ND, TN, WV have no optional program and get no row)."
    )
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def _recount(queue: dict) -> None:
    queue["status_counts"] = {}
    for row in queue["states"]:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1


def update_queue_si_remainder(docs: list[dict], chapters: dict[str, dict], index_count: int) -> dict:
    """Record the remainder scope on the SSI queue's federal row without touching the
    2026-09-10 row fields the core family owns."""
    family = FAMILIES["si-remainder"]
    queue = yaml.safe_load(QUEUE.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    federal = rows["us"]
    subchapters = sorted({d["metadata"]["poms_subchapter"] for d in docs})
    federal["remainder_scope"] = {
        "jurisdiction": "us", "document_class": "manual", "version": family.version,
        "target_manifest": str(family.manifest_path.relative_to(ROOT)),
        "index_url": family.index_url,
        "index_document_count": index_count,
        "taken_count": len(docs),
        "subchapters_taken": subchapters,
        "run_note": "docs/ingest-runs/2026-09-13-federal-guidance-layer.md",
    }
    note = (
        f"2026-09-13 closure run (needs-closure-2026-09-11 SSI-F-POMS): the remaining {len(subchapters)} part SI "
        f"subchapters ({len(docs)} sections) taken as scope us/manual/{family.version} through the same generator "
        "(--family si-remainder); together with the 2026-09-10 scope every section of part SI is held."
    )
    if note not in str(federal.get("notes") or ""):
        federal["notes"] = f"{federal.get('notes') or ''} {note}".strip()
    _recount(queue)
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def update_queue_hi(docs: list[dict], chapters: dict[str, dict], index_count: int) -> dict:
    """Record the POMS HI family on the Medicare queue's federal row (the CMS IOM
    generator owns the row's singular keys; this adds a sibling family record)."""
    family = FAMILIES["hi"]
    queue = yaml.safe_load(MEDICARE_QUEUE.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    federal = rows["us"]
    federal["poms_hi"] = {
        "jurisdiction": "us", "document_class": "manual", "version": family.version,
        "target_manifest": str(family.manifest_path.relative_to(ROOT)),
        "source_kind": "official_html_agency_manual",
        "index_url": family.index_url,
        "index_document_count": index_count,
        "taken_count": len(docs),
        "chapters": [
            {
                "chapter": chapter, "title": info["title"],
                "subchapters": [
                    {"subchapter": sub, "title": s["title"], "sections": len(s["sections"])}
                    for sub, s in info["subchapters"].items()
                ],
            }
            for chapter, info in chapters.items()
        ],
        "run_note": "docs/ingest-runs/2026-09-13-federal-guidance-layer.md",
    }
    note = (
        f"2026-09-13 closure run (needs-closure-2026-09-11 MED-F-POMS-HI): SSA POMS part HI taken whole "
        f"({len(chapters)} chapters, {index_count} sections) as scope us/manual/{family.version}, citation path "
        "us/manual/ssa/poms/hi/<section>, through scripts/build_ssi_poms_si_manifests.py --family hi."
    )
    if note not in str(federal.get("notes") or ""):
        federal["notes"] = f"{federal.get('notes') or ''} {note}".strip()
    _recount(queue)
    MEDICARE_QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--family", choices=sorted(FAMILIES), default="si-core", help="POMS scope to build")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="section-page cache (default ~/.axiom/poms-<part>-cache)")
    parser.add_argument("--print-index", action="store_true", help="print the part's index inventory as markdown")
    parser.add_argument("--skip-queue", action="store_true", help="do not rewrite the program agent queue")
    args = parser.parse_args()
    family = FAMILIES[args.family]
    cache_dir = args.cache_dir or Path.home() / ".axiom" / f"poms-{family.part.lower()}-cache"
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    chapters = read_index(session, cache_dir, family.part)
    index_count = sum(len(s["sections"]) for c in chapters.values() for s in c["subchapters"].values())
    if args.print_index:
        print(index_markdown(chapters, family))
    docs = build_documents(chapters, session, cache_dir, family)
    manifest = {"version": family.version, "documents": docs}
    family.manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
    missing_dates = [d["metadata"]["poms_section"] for d in docs if "effective_date_printed" not in d["metadata"]]
    print(
        json.dumps(
            {
                "family": family.name,
                "manifest": str(family.manifest_path.relative_to(ROOT)),
                "index_section_count": index_count,
                "taken_count": len(docs),
                "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "sections_without_printed_effective_date": missing_dates,
            }
        )
    )
    if not args.skip_queue:
        if family.name == "si-core":
            print("queue status_counts:", update_queue(docs, index_count))
        elif family.name == "si-remainder":
            print("queue status_counts:", update_queue_si_remainder(docs, chapters, index_count))
        else:
            print("queue status_counts:", update_queue_hi(docs, chapters, index_count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
