"""Build the state-administered SSI state-supplement manifests (batch 1) from each
publisher's own index, and update the SSI agent queue rows.

Batch 1 covers the ten largest ``needs_review`` states by population (Census Vintage
2024 estimates): TX, FL, NY, IL, OH, NC, VA, WA, MA, CO, with replacements in
population order (MN, SC, AL, ...) for publishers that blocked on the first probe.
Per state the primary document is the state agency's own governing document for the
optional state supplement (agency manual chapter, adopted rule the state itself
publishes, or published payment standard), confirmed from the publisher's index.

States whose supplement rules already live in a corpus scope are recorded as ``done``
with a pointer (``POINTER_ROWS``); publishers that blocked both a plain request and one
browser-impersonation attempt are recorded as ``blocked_primary_source``
(``BLOCKED_ROWS``). The remaining states get one manifest each::

    manifests/us-fl-ssi-state-supplement.yaml   FAC chapter 65A-2 (flrules.org, .doc rule text)
    manifests/us-ma-ssi-state-supplement.yaml   106 CMR 327.000 (mass.gov regulation page + PDF)
    manifests/us-nc-ssi-state-supplement.yaml   State/County Special Assistance manuals (PDF)
    manifests/us-va-ssi-state-supplement.yaml   DARS Auxiliary Grant Program Manual chapters (PDF)

Index pages are cached under ``--cache-dir`` (default ``~/.axiom/ssi-state-supplement-cache``)
so the script can be re-run without re-fetching; the corpus extractor re-fetches every
document itself when it snapshots the source.

    uv run python scripts/build_ssi_state_supplement_manifests.py --batch 1 [--only fl,ma] [--print-index] [--skip-queue]

Batch 2 (default ``--batch 2``; see the "batch 2" section below) adds KY, LA, NE, NM, NH, ME and
SC manifests, adapter rows for OH and MD, pointers for OR, UT, ID, the OK block and the NY retry::

    uv run python scripts/build_ssi_state_supplement_manifests.py --batch 2 --print-index

Batch 3 (default ``--batch 3``; the "batch 3" section below) finishes the queue: AK, WI, MO, SD and OK
manifests, ``done`` rows for the six states with no optional supplement (AR, AZ, MS, ND, TN, WV; POMS
SI 01415.010 pointer) and the WY block::

    uv run python scripts/build_ssi_state_supplement_manifests.py --print-index
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
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "manifests" / "ssi-agent-queue.yaml"
VERSION = "2026-09-10-ssi-state-supplement"
SOURCE_AS_OF = "2026-09-10"
USER_AGENT = "axiom-corpus/0.1 (source discovery; https://github.com/TheAxiomFoundation/axiom-corpus)"
DISCOVERED_VIA = "manual-review:ssi-agent-queue batch 1 (state-administered supplements); publisher index"

# Reviewer judgment (2026-09-10): population order for the 29 needs_review rows, Census
# Vintage 2024 estimates (CO 5.96M ranks above MN 5.79M). The first ten are attempted;
# the rest are replacements, taken in order only when a publisher blocks.
POPULATION_ORDER = (
    "TX", "FL", "NY", "IL", "OH", "NC", "VA", "WA", "MA", "CO",
    "MN", "SC", "AL", "LA", "KY", "OR", "OK", "UT", "NE", "NM", "ID", "NH", "ME", "MD", "MO", "WI", "SD", "AK", "WY",
)
BATCH = POPULATION_ORDER[:10]

BUILDERS: dict[str, str] = {}

# Rows resolved by pointer to a scope that already holds the state's supplement rules.
POINTER_ROWS = {
    "TX": {
        "index_families": 'pointer to the 2026-09-10 Medicaid MEPD handbook scope (H-6000, Appendix VIII, Appendix XXXI already taken there): 0 new documents taken; MEPD index chapters A-R, appendices, glossary, forms, revisions, bulletins not re-inventoried',
        "target_manifest": "manifests/us-tx-medicaid-eligibility-manual.yaml",
        "target_scope": {"jurisdiction": "us-tx", "document_class": "manual",
                         "version": "2026-09-10-medicaid-state-eligibility-manual"},
        "index_url": "https://fhb.hhs.texas.gov/handbooks/medicaid-elderly-people-disabilities-handbook",
        "notes": (
            "Done by pointer. Texas supplements only institutionalized SSI recipients: HHSC MEPD Handbook H-6000 "
            "'Co-Payment for SSI Cases' (Revision 26-1, effective 2026-03-01) states that HHSC supplements the $30 reduced "
            "SSI payment standard by $45 so recipients keep a $75 personal needs allowance. H-6000, Appendix VIII "
            "(effects of institutionalization on SSI) and Appendix XXXI (budget reference chart) are already in the "
            "2026-09-10 Medicaid eligibility-manual scope as us-tx/manual/hhsc/medicaid/mepd-h-6000, "
            "mepd-appendix-viii and mepd-appendix-xxxi (manifest on branch discovery/ingest-medicaid). The MEPD handbook "
            "index (fhb.hhs.texas.gov, HTTP 200 to a plain client on 2026-09-10; the hhs.texas.gov alias redirects there) "
            "lists chapters A-R plus appendices, glossary, forms, revisions and bulletins; Chapter H lists H-1000 to H-8000."
        ),
    },
    "IL": {
        "index_families": 'pointer to the IDHS Cash, SNAP and Medical Policy Manual / WAG scope (12,450 rows; AABD Cash sections present): 0 new documents taken',
        "target_manifest": "manifests/us-il-snap-manual.yaml",
        "target_scope": {"jurisdiction": "us-il", "document_class": "manual",
                         "version": "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained"},
        "index_url": "https://www.dhs.state.il.us/page.aspx?item=13108",
        "notes": (
            "Done by pointer. Illinois' supplement is AABD Cash (Aid to the Aged, Blind or Disabled), governed by the IDHS "
            "Cash, SNAP and Medical Policy Manual / Workers' Action Guide, which is in the corpus in full (12,450 rows). "
            "AABD sections present include PM I-02-02 (csmm/12262), PM I-03-03 Adult Programs (12286), PM/WAG 11-01-00 AABD "
            "Cash Assistance Standard (15910, 15911), PM/WAG 11-02-03 Using the AABD Cash Assistance Standard (15967, 15968), "
            "WAG 03-03-02 SSI and AABD Cash (13254), WAG 25-03-03 AABD Fuel and Utility Allowances (12668) and PM 22-05-01 "
            "Excess Shelter Allowance (18641); 493 rows mention AABD."
        ),
    },
    "WA": {
        "index_families": 'pointer to WAC chapter 388-474 (4 sections, all in the corpus): 4 found / 0 new documents taken',
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-wa", "document_class": "regulation", "version": "2026-07-01-388-474"},
        "index_url": "https://app.leg.wa.gov/WAC/default.aspx?cite=388-474",
        "notes": (
            "Done by pointer. Washington's SSI State Supplemental Payment is governed by WAC chapter 388-474, which is in the "
            "corpus in full (388-474-0001, -0010, -0012 'What is a state supplemental payment and who can get it?', -0020) as "
            "us-wa/regulation/388/388-474/... from the Legislature's WAC site (adapter scope, no manifest; selected in "
            "manifests/releases/us-rulespec-2026-07-17.json). The DSHS EA-Z manual scope (2026-07-21) carries no SSP page."
        ),
    },
    "CO": {
        "index_families": 'pointer to 9 CCR 2503-5 Adult Financial (92 rows incl. 3.530 OAP and 3.540 AND-SO, all in the corpus): 1 rule found / 0 new documents taken',
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-co", "document_class": "regulation", "version": "2026-06-19-co-oap-9-ccr-2503-5"},
        "index_url": "https://www.sos.state.co.us/CCR/NumericalCCRDocList.do?deptID=9&agencyID=31",
        "notes": (
            "Done by pointer. Colorado's supplements to SSI are the Old Age Pension (OAP) and Aid to the Needy Disabled - "
            "State Only (AND-SO) programs under the Adult Financial rule 9 CCR 2503-5, already in the corpus in full (92 "
            "rows: 3.500-3.587 incl. 3.530 OAP and 3.540 AND-SO) as us-co/regulation/9-ccr-2503-5/... from the Secretary "
            "of State CCR PDF (adapter scope, no manifest)."
        ),
    },
    "MN": {
        "index_families": 'pointer to the DHS Combined Manual scope (1 PDF, 1,354 rows) and the MSA revised sections 01/2026 scope: 0 new documents taken',
        "target_manifest": "manifests/us-mn-combined-manual.yaml",
        "target_scope": {"jurisdiction": "us-mn", "document_class": "manual",
                         "version": "2026-05-27-mn-combined-manual-r2026-07-15-self-contained"},
        "index_url": "https://www.dhs.state.mn.us/main/idcplg?IdcService=GET_DYNAMIC_CONVERSION&RevisionSelectionMethod=LatestReleased&dDocName=CM_MANUAL",
        "notes": (
            "Done by pointer (replacement 1, after NY blocked). Minnesota Supplemental Aid (MSA) is governed by the DHS "
            "Combined Manual, in the corpus as one PDF (dhs-327301.pdf, 1,354 rows; 523 pages mention MSA, incl. 0020.21 MSA "
            "Assistance Standards), plus the MSA revised sections issued 01/2026 "
            "(us-mn/manual/2026-06-27-mn-dhs-msa-revised-sections-2026-01, mndhs-073585.pdf). mn.gov/dhs answered a Radware "
            "challenge to a plain client on 2026-09-10 (federal run); the corpus copies came from dhs.state.mn.us."
        ),
    },
    "AL": {
        "index_families": 'pointer to Alabama Administrative Code chapter 660-2-4 Optional Supplementation (62 rows, in the corpus): 1 chapter found / 0 new documents taken',
        "target_manifest": "manifests/us-al-admin-code-660-2-4.yaml",
        "target_scope": {"jurisdiction": "us-al", "document_class": "regulation", "version": "2026-06-30-al-admin-code-660-2-4"},
        "index_url": "https://dhr.alabama.gov/",
        "notes": (
            "Done by pointer (replacement 3, after SC blocked). Alabama's optional supplementation rule, Alabama Administrative "
            "Code Chapter 660-2-4 'Optional Supplementation' (DHR), is already in the corpus (62 rows, page granularity) as "
            "us-al/regulation/... from the 2026-06-30 run. dhr.alabama.gov answered HTTP 200 to a plain client on 2026-09-10; "
            "medicaid.alabama.gov did not answer TCP."
        ),
    },
}

# Publishers that blocked a plain request and one browser-impersonation attempt (20 s timeouts).
BLOCKED_ROWS = {
    "NY": (
        "https://otda.ny.gov/programs/ssp/",
        "otda.ny.gov (OTDA State Supplement Program page): plain client TCP connection reset by peer (site root too); "
        "curl-cffi chrome120 impersonation HTTP 200 but a 5,615-byte JavaScript challenge ('Please enable JavaScript to "
        "view the page content. Your support ID is ...') with no page content. No index inventory possible. "
        "SSA regional description remains in the federal family: us/manual/ssa/poms/si/ny01415.026.",
    ),
    "OH": (
        "https://codes.ohio.gov/ohio-administrative-code/chapter-5122-36",
        "Ohio's Residential State Supplement is governed by OAC chapter 5122-36 (Department of Behavioral Health, formerly "
        "OhioMHAS). codes.ohio.gov: connect timeout at 20 s for a plain client and for chrome120 impersonation (same as the "
        "2026-09-10 Medicaid batch). Agency site: mha.ohio.gov redirects to dbh.ohio.gov, which answers HTTP 404 (5,264-byte "
        "error shell) to every plain request and, impersonated, HTTP 200 generic 'Community' pages without the RSS program "
        "text or rule documents; its Rules & Regulations page carries no 5122-36 links. No index inventory possible.",
    ),
    "SC": (
        "https://www.scdhhs.gov/resources/mppm",
        "South Carolina's Optional State Supplementation is administered by SCDHHS (Medicaid Policy and Procedures Manual). "
        "scdhhs.gov answers HTTP 403 (919-byte body) to a plain client for the site root and the MPPM page, and HTTP 403 "
        "(919 bytes) to chrome120 impersonation (replacement 2, after OH blocked). No index inventory possible.",
    ),
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "CO": "Colorado", "FL": "Florida", "ID": "Idaho", "IL": "Illinois",
    "KY": "Kentucky", "LA": "Louisiana", "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine", "MN": "Minnesota",
    "MO": "Missouri", "NC": "North Carolina", "NE": "Nebraska", "NH": "New Hampshire", "NM": "New Mexico",
    "NY": "New York", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "SC": "South Carolina", "SD": "South Dakota",
    "TX": "Texas", "UT": "Utah", "VA": "Virginia", "WA": "Washington", "WI": "Wisconsin", "WY": "Wyoming",
}


def fetch(session: requests.Session, url: str, cache: Path | None, *, pause: float = 0.0) -> str:
    if cache is not None and cache.exists():
        return cache.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            if pause:
                time.sleep(pause)
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:  # transient: retry with backoff
            if attempt == 3:
                raise
            print(f"retry {attempt + 1} for {url}: {exc}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    text = resp.text
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
    return text


def strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def us_date(value: str) -> str:
    month, day, year = value.split("/")
    return f"{year}-{int(month):02d}-{int(day):02d}"


def builder(code: str):
    def register(func):
        BUILDERS[code] = func.__name__
        return func

    return register


# ---------------------------------------------------------------- Florida (FAC 65A-2)

FL_INDEX_URL = "https://flrules.org/gateway/ChapterHome.asp?Chapter=65A-2"
FL_RULE_URL = "https://flrules.org/gateway/RuleNo.asp?title={title}&ID={rule}"


@builder("FL")
def build_fl(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Florida Optional State Supplementation: FAC chapter 65A-2 from the Department of State's
    Florida Administrative Code site (flrules.org), the official publisher of DCF's adopted rules.
    The corpus has FAC 65A-1 (SNAP) as us-fl/regulation/fac/65a-1/<section>; the same convention
    is used here. DCF's own site has no OSS page (guessed paths answered 404)."""
    page = fetch(session, FL_INDEX_URL, cache_dir / "fl" / "chapter-65A-2.html")
    chapter_title = strip_tags(re.search(r"title=([^&\"']+)&", page).group(1)).title()
    rules = []
    for match in re.finditer(r"href=\"/gateway/RuleNo\.asp\?title=([^\"&]+)&ID=(65A-2\.\d+)\"", page):
        rule = match.group(2)
        if rule not in [r[1] for r in rules]:
            rules.append((match.group(1), rule))
    if len(rules) < 5:
        raise SystemExit(f"only {len(rules)} rules parsed from {FL_INDEX_URL}; layout changed?")
    docs = []
    for title_param, rule in rules:
        url = FL_RULE_URL.format(title=quote(title_param), rule=rule)
        body = fetch(session, url, cache_dir / "fl" / f"{rule}.html", pause=1.0)
        text = strip_tags(body)
        rule_title = re.search(r"Rule Title:\s*(.*?)\s*Department", text)
        effective = re.search(r"Effective Date:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
        file_match = re.search(r"readFile\.asp\?sid=0&amp;tid=(\d+)&amp;type=1&amp;file=(65A-2\.\d+\.doc)", body)
        if not (rule_title and effective and file_match):
            raise SystemExit(f"rule page {url} lacks title/effective date/rule text link")
        number = rule.split(".", 1)[1]
        history = re.search(r"History Notes:\s*(.*?)(?:\s*Rule Text|$)", text)
        docs.append(
            {
                "source_id": f"fl-fac-65a-2-{number}",
                "jurisdiction": "us-fl",
                "document_class": "regulation",
                "title": f"Fla. Admin. Code R. {rule}: {rule_title.group(1).strip()}",
                "source_url": url,
                "download_url": f"https://flrules.org/gateway/readFile.asp?sid=0&tid={file_match.group(1)}&type=1&file={file_match.group(2)}",
                "source_format": "doc",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": us_date(effective.group(1)),
                "citation_path": f"us-fl/regulation/fac/65a-2/{number}",
                "extraction": {"heading": f"{rule} {rule_title.group(1).strip()}"},
                "metadata": {
                    "primary_source": True,
                    "source_authority": "Florida Department of Children and Families (rule adopted); Florida Department of State (Florida Administrative Code publisher)",
                    "document_subtype": "agency_regulation_section",
                    "program": "ssi_state_supplement",
                    "state_program": "Optional State Supplementation (OSS)",
                    "federal_program": "SSI",
                    "state": "FL",
                    "manual": "Florida Administrative Code",
                    "title_number": "65",
                    "division": "A",
                    "chapter": "2",
                    "chapter_title": chapter_title,
                    "section": number,
                    "effective_date_printed": us_date(effective.group(1)),
                    "history_notes": history.group(1).strip()[:400] if history else None,
                    "index_url": FL_INDEX_URL,
                    "source_discovery_group": "us-fl/regulation/fac/65a-2",
                    "discovered_via": f"{DISCOVERED_VIA} {FL_INDEX_URL}",
                    "download_note": "the RuleNo page is the publisher's rule record; the rule text is its .doc download (readFile.asp), fetched as download_url",
                },
            }
        )
    for doc in docs:
        doc["metadata"] = {k: v for k, v in doc["metadata"].items() if v is not None}
    index = {
        "index_url": FL_INDEX_URL,
        "index_document_count": len(rules),
        "taken_count": len(docs),
        "families": [{"family": f"FAC chapter 65A-2 {chapter_title} rules", "found": len(rules), "taken": len(docs)}],
    }
    return docs, index


# ---------------------------------------------------------------- Massachusetts (106 CMR 327.000)

MA_INDEX_URL = "https://www.mass.gov/law-library/106-cmr"
MA_PAGE_URL = "https://www.mass.gov/regulations/106-CMR-32700-eligibility-requirements-for-state-supplement-program-ssp"


@builder("MA")
def build_ma(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Massachusetts State Supplement Program: 106 CMR 327.000 from the mass.gov law library
    (DTA regulations index), regulation page + official PDF. Section-level rows via the
    labeled_sections segmentation (327.010: ... headings), citation us-ma/regulation/106-cmr/327/<label>
    (the TAFDC scope's 106 CMR convention)."""
    index_page = fetch(session, MA_INDEX_URL, cache_dir / "ma" / "106-cmr.html", pause=3.0)
    chapters = sorted(set(re.findall(r"href=\"/regulations/(106-CMR-\d{5}[^\"]*)\"", index_page)))
    if not any(c.startswith("106-CMR-32700") for c in chapters):
        raise SystemExit(f"106 CMR 327.00 not listed on {MA_INDEX_URL}")
    page = fetch(session, MA_PAGE_URL, cache_dir / "ma" / "106-cmr-327.html", pause=3.0)
    title = strip_tags(re.search(r"<title>([^<]*)</title>", page).group(1)).split("|")[0].strip()
    download = re.search(r"href=\"(https://www\.mass\.gov/doc/[^\"]+/download)\"", page)
    if not download:
        raise SystemExit(f"no PDF download link on {MA_PAGE_URL}")
    families = {
        "SSP (327)": [c for c in chapters if c.startswith("106-CMR-327")],
        "Fair hearing rules (343)": [c for c in chapters if c.startswith("106-CMR-343")],
        "SNAP (360-367)": [c for c in chapters if c.startswith("106-CMR-36")],
        "TCAP / TAFDC / EAEDC (701-708)": [c for c in chapters if c.startswith("106-CMR-70")],
    }
    other = [c for c in chapters if not any(c in v for v in families.values())]
    if other:
        families["other"] = other
    doc = {
        "source_id": "ma-dta-106-cmr-327",
        "jurisdiction": "us-ma",
        "document_class": "regulation",
        "title": title,
        "source_url": MA_PAGE_URL,
        "download_url": download.group(1),
        "source_format": "pdf",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": SOURCE_AS_OF,
        "citation_path": "us-ma/regulation/106-cmr/327",
        "extraction": {
            "segmentation": "labeled_sections",
            "start_page": 1,
            # page 1 carries the table of contents (327.010: ... 327.410: ...) followed directly by the
            # body of 327.010; skip lines through the last TOC entry so the TOC does not become sections
            "start_after_pattern": r"^327\.410:\s+Recovery of Overpayments\s*$",
            "section_heading_pattern": r"^(?P<label>327\.\d{3})\s*:\s+(?P<heading>(?!continued\b).+?)\s*$",
            "drop_lines": ["106 CMR: DEPARTMENT OF TRANSITIONAL ASSISTANCE"],
            "drop_line_patterns": [r"^327\.\d{3}\s*:\s*continued\s*$"],
        },
        "metadata": {
            "primary_source": True,
            "source_authority": "Massachusetts Department of Transitional Assistance",
            "document_subtype": "regulation_chapter_pdf",
            "program": "ssi_state_supplement",
            "state_program": "State Supplement Program (SSP)",
            "federal_program": "SSI",
            "state": "MA",
            "cmr_chapter": "106 CMR 327.000",
            "index_url": MA_INDEX_URL,
            "source_discovery_group": "us-ma/regulation/106-cmr/327",
            "discovered_via": f"{DISCOVERED_VIA} {MA_INDEX_URL}",
            "extraction_granularity": "labeled_sections (327.xxx headings); the page-1 table of contents is skipped with start_after_pattern so 327.010-327.110, which begin on page 1, are kept",
            "download_note": "the mass.gov regulation page carries only the official PDF download; the PDF is fetched as download_url",
            "expression_date_note": "fetch date; the PDF's own modification date is 2019-05-06 and the page prints no effective date",
        },
    }
    index = {
        "index_url": MA_INDEX_URL,
        "index_document_count": len(chapters),
        "taken_count": 1,
        "families": [{"family": name, "found": len(items), "taken": 1 if name.startswith("SSP") else 0} for name, items in families.items()],
    }
    return [doc], index


# ---------------------------------------------------------------- North Carolina (Special Assistance)

NC_INDEX_URL = "https://policies.ncdhhs.gov/divisional-n-z/social-services/special-assistance/special-assistance/"
NC_MANUALS = {
    "special-assistance-manual": ("manual", "State/County Special Assistance Manual"),
    "special-assistance-in-home-program-manual": ("in-home-manual", "Special Assistance In-Home Program Manual"),
}


@builder("NC")
def build_nc(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """North Carolina State/County Special Assistance: the DSS Special Assistance Manual and the
    Special Assistance In-Home Program Manual (both revised June 1, 2026) from the NCDHHS
    Policies and Manuals site; PDF page granularity like the 2026-09-10 Medicaid batch."""
    page = fetch(session, NC_INDEX_URL, cache_dir / "nc" / "special-assistance-index.html")
    entries: list[tuple[str, str]] = []
    for slug, label in re.findall(r"href=\"https://policies\.ncdhhs\.gov/document/([^\"/]+)/?\"[^>]*>(.*?)</a>", page, re.S):
        label = strip_tags(label)
        if label and (slug, label) not in entries:
            entries.append((slug, label))
    if len(entries) < 50:
        raise SystemExit(f"only {len(entries)} documents parsed from {NC_INDEX_URL}; layout changed?")

    def family(slug: str, label: str) -> str:
        if slug in NC_MANUALS:
            return "program manuals"
        if re.match(r"CHANGE NO|EFS-SA-CN|SAIH CASE MANAGEMENT MANUAL CHANGE", label, re.I):
            return "change notices"
        if re.search(r"administrative letter", label, re.I):
            return "administrative letters"
        if re.match(r"EIS ", label):
            return "EIS system documents"
        return "forms and notices"

    counts: dict[str, int] = {}
    for slug, label in entries:
        counts[family(slug, label)] = counts.get(family(slug, label), 0) + 1
    docs = []
    for slug, (suffix, title) in NC_MANUALS.items():
        doc_page = fetch(session, f"https://policies.ncdhhs.gov/document/{slug}/", cache_dir / "nc" / f"{slug}.html")
        pdf = re.search(r"href=\"(https://policies\.ncdhhs\.gov/wp-content/uploads/[^\"]+\.pdf)\"", doc_page)
        if not pdf:
            raise SystemExit(f"no PDF link on the {slug} document page")
        revision = re.search(r"Rev-([A-Za-z]+)-(\d{4})\.pdf", pdf.group(1))
        docs.append(
            {
                "source_id": f"nc-dss-{slug}",
                "jurisdiction": "us-nc",
                "document_class": "manual",
                "title": f"NC DSS {title} (revised June 1, 2026)",
                "source_url": f"https://policies.ncdhhs.gov/document/{slug}/",
                "download_url": pdf.group(1),
                "source_format": "pdf",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": "2026-06-01",
                "citation_path": f"us-nc/manual/dss/special-assistance/{suffix}",
                "extraction": {"ocr": True},
                "metadata": {
                    "primary_source": True,
                    "source_authority": "North Carolina Department of Health and Human Services, Division of Social Services",
                    "document_subtype": "program_manual_pdf",
                    "program": "ssi_state_supplement",
                    "state_program": "State/County Special Assistance",
                    "federal_program": "SSI",
                    "state": "NC",
                    "revision_printed": "Revised: June 1, 2026" + (f" (file Rev-{revision.group(1)}-{revision.group(2)})" if revision else ""),
                    "index_url": NC_INDEX_URL,
                    "source_discovery_group": "us-nc/manual/dss/special-assistance",
                    "discovered_via": f"{DISCOVERED_VIA} {NC_INDEX_URL}",
                    "extraction_granularity": "pdf_page",
                    "download_note": "the document page carries only the PDF; the PDF is fetched as download_url",
                },
            }
        )
    index = {
        "index_url": NC_INDEX_URL,
        "index_document_count": len(entries),
        "taken_count": len(docs),
        "families": [{"family": name, "found": count, "taken": len(docs) if name == "program manuals" else 0}
                     for name, count in sorted(counts.items())],
    }
    return docs, index


# ---------------------------------------------------------------- Virginia (Auxiliary Grant)

VA_INDEX_URL = "https://dars.virginia.gov/benefits/auxiliary-grant/for-providers/"
VA_MAIN_URL = "https://dars.virginia.gov/benefits/auxiliary-grant/"
VA_VAC_URL = "https://law.lis.virginia.gov/admincode/title22/agency30/chapter80/"


@builder("VA")
def build_va(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Virginia Auxiliary Grant Program Manual chapters A-L, listed on the DARS Auxiliary Grant
    'for providers' page and served from the agency's document repository (www.vadsa.org, which
    redirects to www.dsa.virginia.gov, 'Virginia Disability Services Agencies'). PDF page granularity.
    The adopted rule 22VAC30-80 (Virginia LIS) is inventoried as the alternative family, not taken."""
    page = fetch(session, VA_INDEX_URL, cache_dir / "va" / "for-providers.html")
    main = re.search(r"<main.*?</main>", page, re.S)
    body = main.group(0) if main else page
    links: list[tuple[str, str]] = []
    for url, label in re.findall(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", body, re.S):
        label = strip_tags(label)
        if label and not url.startswith(("#", "tel:")) and (url, label) not in links:
            links.append((url, label))
    chapters = [(u, text) for u, text in links if re.match(r"Chapter [A-L] ", text)]
    transmittals = [(u, text) for u, text in links if text.startswith("Manual Transmittal")]
    provider_docs = [
        (u, text) for u, text in links
        if re.search(r"\.(pdf|docx)$", u) and (u, text) not in chapters + transmittals
    ]
    if len(chapters) != 12:
        raise SystemExit(f"expected 12 Auxiliary Grant manual chapters on {VA_INDEX_URL}, found {len(chapters)}")
    vac_page = fetch(session, VA_VAC_URL, cache_dir / "va" / "22vac30-80.html")
    vac_sections = sorted(set(re.findall(r"chapter80/section(\d+)/", vac_page)), key=int)
    docs = []
    for url, label in chapters:
        letter = re.match(r"Chapter ([A-L]) [—-]+ (.+)", label)
        if not letter:
            raise SystemExit(f"unexpected chapter label {label!r}")
        file_id = url.rstrip("/").rsplit("/", 1)[1]
        canonical = f"https://www.dsa.virginia.gov/apps/DocumentRepositoryViewer/fileviewer/{file_id}"
        docs.append(
            {
                "source_id": f"va-dars-auxiliary-grant-manual-chapter-{letter.group(1).lower()}",
                "jurisdiction": "us-va",
                "document_class": "manual",
                "title": f"Virginia DARS Auxiliary Grant Program Manual, Chapter {letter.group(1)}: {letter.group(2).strip()}",
                "source_url": canonical,
                "source_format": "pdf",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": SOURCE_AS_OF,
                "citation_path": f"us-va/manual/dars/auxiliary-grant/chapter-{letter.group(1).lower()}",
                "extraction": {"ocr": True},
                "metadata": {
                    "primary_source": True,
                    "source_authority": "Virginia Department for Aging and Rehabilitative Services",
                    "hosting_authority": "Virginia Disability Services Agencies document repository (www.dsa.virginia.gov; the index links www.vadsa.org, which redirects there)",
                    "document_subtype": "program_manual_chapter_pdf",
                    "program": "ssi_state_supplement",
                    "state_program": "Auxiliary Grant (AG)",
                    "federal_program": "SSI",
                    "state": "VA",
                    "manual_chapter": letter.group(1),
                    "index_link_url": url,
                    "index_url": VA_INDEX_URL,
                    "program_page_url": VA_MAIN_URL,
                    "regulation_alternative": f"{VA_VAC_URL} (22VAC30-80, {len(vac_sections)} sections incl. FORMS; not taken)",
                    "source_discovery_group": "us-va/manual/dars/auxiliary-grant",
                    "discovered_via": f"{DISCOVERED_VIA} {VA_INDEX_URL}",
                    "extraction_granularity": "pdf_page",
                    "expression_date_note": "fetch date; each chapter prints its own revision month (e.g. Chapter D 11/18) on the cover",
                },
            }
        )
    index = {
        "index_url": VA_INDEX_URL,
        "index_document_count": len(chapters) + len(transmittals) + len(provider_docs),
        "taken_count": len(docs),
        "families": [
            {"family": "Auxiliary Grant Program Manual chapters", "found": len(chapters), "taken": len(docs)},
            {"family": "manual transmittals", "found": len(transmittals), "taken": 0},
            {"family": "provider manuals, agreements, certification and forms", "found": len(provider_docs), "taken": 0},
            {"family": f"22VAC30-80 Auxiliary Grants Program sections on Virginia LIS ({VA_VAC_URL}; separate index)",
             "found": len(vac_sections), "taken": 0},
        ],
    }
    return docs, index


# ---------------------------------------------------------------- queue

def manifest_path(code: str) -> Path:
    return ROOT / "manifests" / f"us-{code.lower()}-ssi-state-supplement.yaml"


def update_queue(results: dict[str, dict]) -> dict:
    queue = yaml.safe_load(QUEUE.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    for code, index in results.items():
        row = rows[f"us-{code.lower()}"]
        docs = index["docs"]
        families = "; ".join(f"{f['family']}: {f['found']} found / {f['taken']} taken" for f in index["families"])
        row.update(
            {
                "queue_status": "agent_ready",
                "source_kind": index["source_kind"],
                "primary_source_url": docs[0]["source_url"],
                "target_manifest": str(manifest_path(code).relative_to(ROOT)),
                "target_scope": {"jurisdiction": f"us-{code.lower()}", "document_class": docs[0]["document_class"], "version": VERSION},
                "index_url": index["index_url"],
                "index_document_count": index["index_document_count"],
                "taken_count": index["taken_count"],
                "index_families": families,
                "notes": index["note"],
            }
        )
    for code, pointer in POINTER_ROWS.items():
        row = rows[f"us-{code.lower()}"]
        row.update(
            {
                "queue_status": "done",
                "source_kind": "official_state_or_ssa_document",
                "primary_source_url": None,
                "target_manifest": pointer["target_manifest"],
                "target_scope": pointer["target_scope"],
                "index_url": pointer["index_url"],
                "index_document_count": None,
                "taken_count": 0,
                "index_families": pointer["index_families"],
                "notes": pointer["notes"] + " (2026-09-10 state-supplement batch 1.)",
            }
        )
    for code, (url, note) in BLOCKED_ROWS.items():
        row = rows[f"us-{code.lower()}"]
        row.update(
            {
                "queue_status": "blocked_primary_source",
                "source_kind": "state_agency_document",
                "primary_source_url": url,
                "target_manifest": None,
                "index_url": url,
                "index_document_count": None,
                "taken_count": 0,
                "index_families": "no index inventory possible (publisher blocked; see notes)",
                "notes": f"Blocked 2026-09-10 (state-supplement batch 1): {note}",
            }
        )
    queue["status_counts"] = {}
    for row in queue["states"]:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    note = (
        "2026-09-10 SSI state-supplement batch 1: scripts/build_ssi_state_supplement_manifests.py; ten largest "
        "needs_review states by population attempted (TX, FL, NY, IL, OH, NC, VA, WA, MA, CO) with replacements MN, SC, AL; "
        "docs/ingest-runs/2026-09-10-ssi-state-supplements-batch-1.md."
    )
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


SOURCE_KINDS = {
    "FL": "official_state_regulation",
    "MA": "official_state_regulation",
    "NC": "official_state_agency_manual",
    "VA": "official_state_agency_manual",
}
ROW_NOTES = {
    "FL": (
        "Optional State Supplementation (OSS): FAC chapter 65A-2 (8 rules, each rule's .doc text from flrules.org, the "
        "Department of State's FAC publisher; rule pages print the effective dates 2001-12-16 to 2025-06-24). DCF's own "
        "site has no OSS page (guessed paths 404) and the ESS Program Policy Manual scope carries no OSS text. "
        "document_class regulation, citation us-fl/regulation/fac/65a-2/<section> (the FAC 65A-1 convention)."
    ),
    "MA": (
        "State Supplement Program (SSP): 106 CMR 327.000 Eligibility Requirements for SSP (DTA), one regulation PDF from the "
        "mass.gov law library 106 CMR index (18 chapters listed; 327 taken), 24 section rows 327.010-327.410 (the TOC misprints 327.160 as 322.160). document_class "
        "regulation, citation us-ma/regulation/106-cmr/327/<section>. mass.gov answered HTTP 200 to a paced plain client "
        "on 2026-09-10 (the guessed law-library/106-cmr-327 path is 404; the regulation page is /regulations/106-CMR-32700-...)."
    ),
    "NC": (
        "State/County Special Assistance (SA, adult care home) and SA In-Home: the two DSS program manuals (PDF, revised "
        "2026-06-01; 368 and 48 pages) from the NCDHHS Policies and Manuals Special Assistance index, which also lists "
        "change notices, administrative letters, forms and EIS documents (not taken). document_class manual, citation "
        "us-nc/manual/dss/special-assistance/{manual,in-home-manual}, page granularity."
    ),
    "VA": (
        "Auxiliary Grant (AG): DARS Auxiliary Grant Program Manual chapters A-L (12 PDFs) listed on the DARS AG 'for "
        "providers' page and served by the agency repository www.dsa.virginia.gov (linked as www.vadsa.org). Manual "
        "transmittal DARS-APSD-18 and provider documents not taken; the adopted rule 22VAC30-80 (Virginia LIS, 12 sections) "
        "is the alternative family, not taken. document_class manual, citation us-va/manual/dars/auxiliary-grant/chapter-<x>, "
        "page granularity."
    ),
}


# ================================================================ batch 2 (2026-09-10, US-network retry pass)
#
# Batch 2 covers the next ten ``needs_review`` states by population (LA, KY, OR, OK, UT, NE,
# NM, ID, NH, ME) with replacements in the same order (MD, MO, WI, SD, AK, WY) for publishers
# that block a plain request and one browser-impersonation attempt. It also retries the three
# batch-1 blocked rows (NY, OH, SC) from a US network. OH and MD are adapter scopes
# (``extract-ohio-administrative-code``, ``extract-maryland-comar``) recorded in ``ADAPTER_ROWS``.

BATCH2_ORDER = ("LA", "KY", "OR", "OK", "UT", "NE", "NM", "ID", "NH", "ME", "MD", "MO", "WI", "SD", "AK", "WY")
DISCOVERED_VIA_2 = "manual-review:ssi-agent-queue batch 2 (state-administered supplements); publisher index"
CERTS_DIR = ROOT / "data" / "certs"
NE_CA_BUNDLE = CERTS_DIR / "rules-nebraska-gov-ca-bundle.pem"
SC_CA_BUNDLE = CERTS_DIR / "img1-scdhhs-gov-ca-bundle.pem"
BUILDERS_2: dict[str, str] = {}


def builder2(code: str):
    def register(func):
        BUILDERS_2[code] = func.__name__
        return func

    return register


def fetch_impersonated(url: str, cache: Path | None, *, pause: float = 0.5) -> str:
    """Fetch through curl-cffi (chrome120 TLS fingerprint) for publishers whose WAF answers
    403 to a plain client but 200 to a browser fingerprint. Verification is never disabled."""
    if cache is not None and cache.exists():
        return cache.read_text(encoding="utf-8")
    from curl_cffi import requests as curl_requests

    if pause:
        time.sleep(pause)
    resp = curl_requests.get(url, impersonate="chrome120", timeout=20)
    if resp.status_code != 200:
        raise SystemExit(f"{url}: HTTP {resp.status_code} with browser impersonation")
    text = resp.text
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
    return text


def long_date(value: str) -> str:
    return dt.datetime.strptime(value.strip(), "%B %d, %Y").date().isoformat()


# ---------------------------------------------------------------- Kentucky (921 KAR 2:015)

KY_INDEX_URL = "https://apps.legislature.ky.gov/law/kar/titles/921/002/"
KY_RULE_URL = "https://apps.legislature.ky.gov/law/kar/titles/921/002/015/"


@builder2("KY")
def build_ky(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Kentucky State Supplementation: 921 KAR 2:015 'Supplemental programs for persons who are
    aged, blind, or have a disability' (CHFS/DCBS rule) from the Legislative Research
    Commission's KAR site, the same publisher and citation convention (us-ky/regulation/kar/...)
    as the 2026-09-10 CHIP scope (907 KAR 4:020)."""
    index = strip_tags(fetch(session, KY_INDEX_URL, cache_dir / "ky" / "921-kar-2.html"))
    regs = re.findall(r"Regulation (\d+) — (.*?) (Current|Inactive|Repealed)(?= Regulation| |$)", index)
    if not any(n == "015" for n, _, _ in regs):
        raise SystemExit(f"921 KAR 2:015 not listed on {KY_INDEX_URL}")
    page = fetch(session, KY_RULE_URL, cache_dir / "ky" / "921-kar-2-015.html", pause=1.0)
    heading = re.search(r'<h1 class="citation"[^>]*>(.*?)</h1>', page, re.S)
    history = re.search(r'<div class="history-content">(.*?)</div>', page, re.S)
    if not (heading and history):
        raise SystemExit("921 KAR 2:015 page lacks the heading or history block")
    title = strip_tags(re.sub(r"</span>", " ", heading.group(1)))
    if not title.startswith("921 KAR 2:015"):
        raise SystemExit(f"unexpected 921 KAR 2:015 heading {title!r}")
    effective = re.findall(r"eff\.\s*(\d{1,2}-\d{1,2}-\d{4})", strip_tags(history.group(1)))
    if not effective:
        raise SystemExit("no effective date in 921 KAR 2:015 history")
    month, day, year = effective[-1].split("-")
    last_effective = f"{year}-{int(month):02d}-{int(day):02d}"
    doc = {
        "source_id": "ky-lrc-921-kar-2-015",
        "jurisdiction": "us-ky",
        "document_class": "regulation",
        "title": title,
        "source_url": KY_RULE_URL,
        "source_format": "html",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": last_effective,
        "citation_path": "us-ky/regulation/kar/921/002/015",
        "extraction": {
            # #regular-content carries the engrossed (current) text; #alternate-content is the hidden
            # "how this document appeared before it was engrossed" copy (17 sections) and is dropped
            "html_content_selector": "#regular-content div.regulation-content",
            "html_drop_selectors": ["#alternate-content", "#alternate-card"],
        },
        "metadata": {
            "primary_source": True,
            "source_authority": "Kentucky Cabinet for Health and Family Services, Department for Community Based Services (921 KAR), published by the Legislative Research Commission",
            "document_subtype": "administrative_regulation",
            "legal_identifier": "921 KAR 2:015",
            "program": "ssi_state_supplement",
            "state_program": "State Supplementation",
            "federal_program": "SSI",
            "state": "KY",
            "history_last_effective": last_effective,
            "index_url": KY_INDEX_URL,
            "source_discovery_group": "us-ky/regulation/kar/921/002",
            "discovered_via": f"{DISCOVERED_VIA_2} {KY_INDEX_URL}",
            "extraction_note": "the page carries two div.regulation-content copies: #regular-content (the engrossed, current text, 16 sections; taken as one block, as the CHIP 907 KAR scope) and the hidden #alternate-content pre-engrossment copy (17 sections; dropped); the history block is not part of the body",
        },
    }
    counts = {s: sum(1 for _, _, st in regs if st == s) for s in ("Current", "Inactive", "Repealed")}
    index_info = {
        "index_url": KY_INDEX_URL,
        "index_document_count": len(regs),
        "taken_count": 1,
        "families": [
            {"family": "921 KAR Chapter 2 (DCBS cash assistance) regulations, Current", "found": counts["Current"], "taken": 1},
            {"family": "921 KAR Chapter 2 regulations, Inactive or Repealed", "found": counts["Inactive"] + counts["Repealed"], "taken": 0},
        ],
    }
    return [doc], index_info


# ---------------------------------------------------------------- Louisiana (LDH Medicaid Eligibility Manual J-0000)

LA_INDEX_URL = "https://ldh.la.gov/page/medicaid-eligibility-manual"
LA_J0000_URL = "https://ldh.la.gov/assets/medicaid/MedicaidEligibilityPolicy/J-0000.pdf"
LA_J0000_REISSUED = "2025-07-21"  # "Reissued July 21, 2025" printed on every page of J-0000


@builder2("LA")
def build_la(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Louisiana Optional State Supplement (OSS): LDH Medicaid Eligibility Manual section J-0000
    'Medicaid Eligibility Cards and Optional State Supplement Payments' (Bureau of Health Services
    Financing). ldh.la.gov answers HTTP 403 to a plain client and HTTP 200 to a browser TLS
    fingerprint; the extractor's browser_impersonation request option is used (as today's POMS SI
    manifest does). PDF page granularity."""
    page = fetch_impersonated(LA_INDEX_URL, cache_dir / "la" / "medicaid-eligibility-manual.html")
    links: list[tuple[str, str]] = []
    for url, label in re.findall(r'<a[^>]*href="(/assets/medicaid/MedicaidEligibilityPolicy/[^"]+)"[^>]*>(.*?)</a>', page, re.S):
        label = strip_tags(label)
        if (url, label) not in links:
            links.append((url, label))
    if len(links) < 80:
        raise SystemExit(f"only {len(links)} manual sections parsed from {LA_INDEX_URL}; layout changed?")
    if not any(u.endswith("/J-0000.pdf") for u, _ in links):
        raise SystemExit("J-0000 not listed on the LDH manual index")
    j_label = next(label for u, label in links if u.endswith("/J-0000.pdf"))
    doc = {
        "source_id": "la-ldh-medicaid-eligibility-manual-j-0000",
        "jurisdiction": "us-la",
        "document_class": "manual",
        "title": f"Louisiana Medicaid Eligibility Manual {j_label}",
        "source_url": LA_J0000_URL,
        "source_format": "pdf",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": LA_J0000_REISSUED,
        "citation_path": "us-la/manual/ldh/medicaid-eligibility/j-0000",
        "request": {"browser_impersonation": True},
        "extraction": {"ocr": True},
        "metadata": {
            "primary_source": True,
            "source_authority": "Louisiana Department of Health, Bureau of Health Services Financing (Medicaid)",
            "document_subtype": "eligibility_manual_section_pdf",
            "program": "ssi_state_supplement",
            "state_program": "Optional State Supplement (OSS)",
            "federal_program": "SSI",
            "state": "LA",
            "manual_section": "J-0000",
            "reissued_printed": "Reissued July 21, 2025 (replacing September 30, 2024)",
            "index_url": LA_INDEX_URL,
            "source_discovery_group": "us-la/manual/ldh/medicaid-eligibility",
            "discovered_via": f"{DISCOVERED_VIA_2} {LA_INDEX_URL}",
            "extraction_granularity": "pdf_page",
            "access_note": "ldh.la.gov: HTTP 403 (118-byte body) to a plain client, HTTP 200 to a chrome120 TLS fingerprint on 2026-09-10; fetched with the extractor's browser_impersonation option, TLS verification on",
        },
    }
    def family(url: str, label: str) -> str:
        if url.endswith("/J-0000.pdf"):
            return "J medical eligibility cards and OSS payments"
        if label.startswith("Preface"):
            return "preface"
        if re.match(r"\s*Z\b", label):
            return "Z appendix tables and standards"
        return "manual sections A-X (eligibility policy)"
    counts: dict[str, int] = {}
    for url, label in links:
        counts[family(url, label)] = counts.get(family(url, label), 0) + 1
    index_info = {
        "index_url": LA_INDEX_URL,
        "index_document_count": len(links),
        "taken_count": 1,
        "families": [{"family": k, "found": v, "taken": 1 if k.startswith("J ") else 0} for k, v in sorted(counts.items())],
    }
    return [doc], index_info


# ---------------------------------------------------------------- Nebraska (469 NAC)

NE_AGENCY_TITLES_URL = "https://rules.nebraska.gov/api/title/GetByAgencyId/37"
NE_CHAPTERS_URL = "https://rules.nebraska.gov/api/chapter/GetByTitleId/{title_id}"
NE_LANDING_URL = "https://rules.nebraska.gov/rules?agencyId=37&titleId={title_id}"
NE_PDF_URL = "https://rules.nebraska.gov/api/fileStorage/GetAsByteArray/{container}/{blob}"
NE_EXTRACTION = {
    "segmentation": "labeled_sections",
    "normalize_parenthetical_label_components": True,
    "section_heading_pattern": r"^(?P<label>0\d{2}(?:\.\d{1,2})?(?:\([A-Za-z0-9]+\))*)\.?\s+(?P<heading>[A-Z][A-Z0-9 ’'&,/()\-–‑§]+?(?:\.(?=\s|$)|$))(?:\s+(?P<body>.*))?$",
    "heading_continuation_pattern": r"^(?P<heading>[A-Z][A-Z0-9 ’'&,/()\-–‑§$]+?(?:\.(?=\s|$)|$))(?:\s+(?P<body>.*))?$",
}


@builder2("NE")
def build_ne(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Nebraska Assistance to the Aged, Blind, or Disabled (AABD) payment program, the state's
    supplement to SSI: Title 469 NAC (DHHS) from the Secretary of State's rules.nebraska.gov, the
    same publisher, API and labeled_sections convention as the 475 NAC SNAP scope
    (us-ne/regulation/title-475/chapter-N). rules.nebraska.gov serves a chain without the DigiCert
    Global G2 TLS RSA SHA256 2020 CA1 intermediate; the publisher's public intermediate is added
    under data/certs and verification stays on (the SNAP manifest's verify_tls: false is not used)."""
    if not NE_CA_BUNDLE.exists():
        raise SystemExit(f"missing {NE_CA_BUNDLE}; build it from certifi + data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem")
    ne_session = requests.Session()
    ne_session.headers.update(session.headers)
    ne_session.verify = str(NE_CA_BUNDLE)
    titles = json.loads(fetch(ne_session, NE_AGENCY_TITLES_URL, cache_dir / "ne" / "dhhs-titles.json"))["output"]
    title = next(t for t in titles if t["titleNumber"] == 469)
    chapters = json.loads(fetch(ne_session, NE_CHAPTERS_URL.format(title_id=title["id"]), cache_dir / "ne" / "title-469-chapters.json"))["output"]
    if len(chapters) < 3:
        raise SystemExit(f"only {len(chapters)} chapters in 469 NAC; API changed?")
    docs = []
    for chapter in sorted(chapters, key=lambda c: int(c["chapterNumber"])):
        blob = chapter.get("officialPdfBlobName") or chapter["pdfBlobName"]
        number = chapter["chapterNumber"]
        docs.append(
            {
                "source_id": f"ne-dhhs-title-469-chapter-{number}",
                "jurisdiction": "us-ne",
                "document_class": "regulation",
                "title": f"Nebraska Title 469 NAC Chapter {number}: {chapter['chapterName'].title()}",
                "source_url": NE_PDF_URL.format(container=chapter["pdfContainerName"], blob=quote(blob)),
                "source_format": "pdf",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": chapter["effectiveDate"][:10],
                "citation_path": f"us-ne/regulation/title-469/chapter-{number}",
                "extraction": dict(NE_EXTRACTION),
                "metadata": {
                    "primary_source": True,
                    "source_authority": "Nebraska Department of Health and Human Services (469 NAC), filed with the Secretary of State",
                    "document_subtype": "filed_administrative_regulation_chapter",
                    "program": "ssi_state_supplement",
                    "state_program": "Assistance to the Aged, Blind, or Disabled (AABD) payment program; State Disability Program",
                    "federal_program": "SSI",
                    "state": "NE",
                    "nac_title": "469",
                    "nac_title_name": title["titleName"],
                    "nac_chapter": number,
                    "effective_date_api": chapter["effectiveDate"][:10],
                    "pdf_blob_name": blob,
                    "rules_landing_page": NE_LANDING_URL.format(title_id=title["id"]),
                    "rules_api_url": NE_CHAPTERS_URL.format(title_id=title["id"]),
                    "index_url": NE_LANDING_URL.format(title_id=title["id"]),
                    "source_discovery_group": "us-ne/regulation/title-469",
                    "discovered_via": f"{DISCOVERED_VIA_2} {NE_CHAPTERS_URL.format(title_id=title['id'])}",
                    "tls_note": "rules.nebraska.gov omits the DigiCert Global G2 TLS RSA SHA256 2020 CA1 intermediate; extract with REQUESTS_CA_BUNDLE=data/certs/rules-nebraska-gov-ca-bundle.pem (certifi + the publisher's public intermediate); verification not disabled",
                },
            }
        )
    index_info = {
        "index_url": NE_LANDING_URL.format(title_id=title["id"]),
        "index_document_count": len(chapters),
        "taken_count": len(docs),
        "families": [
            {"family": f"469 NAC {title['titleName'].title()} chapters (API GetByTitleId/{title['id']})", "found": len(chapters), "taken": len(docs)},
            {"family": "other DHHS (agency 37) NAC titles on the agency listing (separate titles, not inventoried)", "found": len(titles) - 1, "taken": 0},
        ],
    }
    return docs, index_info


# ---------------------------------------------------------------- New Mexico (8.106 NMAC)

NM_INDEX_URL = "https://www.hca.nm.gov/lookingforinformation/income-support-division-1/"
NM_SRCA_CHAPTER_URL = "https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/chapter-106-state-funded-assistance-programs/"


@builder2("NM")
def build_nm(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """New Mexico supplement for SSI recipients in adult residential shelter care homes (ARSCH)
    and General Assistance: 8.106 NMAC 'State Funded Assistance Programs' (HCA Income Support
    Division), all parts linked from the HCA ISD regulations index and served by the State
    Records Center and Archives (srca.nm.gov), the same publisher and convention as the 8.100 /
    8.139 NMAC SNAP scope (us-nm/regulation/nmac/8/<chapter>/<part>)."""
    index = fetch(session, NM_INDEX_URL, cache_dir / "nm" / "hca-isd-index.html")
    all_parts = re.findall(r'href="(https://www\.srca\.nm\.gov/parts/title08/08\.(\d{3})\.(\d{4})\.html)"', index)
    chapter_counts: dict[str, int] = {}
    seen: set[str] = set()
    for url, chapter, _part in all_parts:
        if url in seen:
            continue
        seen.add(url)
        chapter_counts[chapter] = chapter_counts.get(chapter, 0) + 1
    parts = sorted({(url, part) for url, chapter, part in all_parts if chapter == "106"}, key=lambda x: int(x[1]))
    if len(parts) < 10:
        raise SystemExit(f"only {len(parts)} 8.106 NMAC parts on {NM_INDEX_URL}")
    docs = []
    for url, part in parts:
        page = fetch(session, url, cache_dir / "nm" / f"08.106.{part}.html", pause=0.5)
        text = strip_tags(re.sub(r"<style.*?</style>|<xml>.*?</xml>|<!--.*?-->", "", page, flags=re.S))
        part_number = str(int(part))
        title_match = re.search(r"CHAPTER 106\s+STATE FUNDED ASSISTANCE(?: PROGRAMS)?\s+PART " + part_number + r"\s+(.*?)\s+8\.106\." + part_number + r"\.1\s+ISSUING AGENCY", text)
        eff = re.search(r"8\.106\." + part_number + r"\.5\s+EFFECTIVE DATE:\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
        if not (title_match and eff):
            raise SystemExit(f"8.106.{part_number} NMAC page lacks title or effective date")
        part_title = title_match.group(1).strip().title().replace("Ga ", "GA ").replace("Ssi", "SSI")
        docs.append(
            {
                "source_id": f"nm-srca-nmac-8-106-{part_number}",
                "jurisdiction": "us-nm",
                "document_class": "regulation",
                "title": f"8.106.{part_number} NMAC {part_title}",
                "source_url": url,
                "source_format": "html",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": long_date(eff.group(1)),
                "citation_path": f"us-nm/regulation/nmac/8/106/{part_number}",
                "extraction": {
                    "html_content_selector": ".WordSection1, .Section1",
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": (
                        r"^(?P<label>8\.\s*106\.\s*" + part_number + r"\.\s*\d+(?:\s*-\s*\d+)?)\s+"
                        r"(?P<heading>[A-Z][^:]{0,180}:|\[RESERVED\]|[A-Z][A-Z0-9 /()\[\]\-–—,'&]{0,180})(?:\s+(?P<body>.*))?$"
                    ),
                    "normalize_label_internal_whitespace": True,
                },
                "metadata": {
                    "primary_source": True,
                    "source_authority": "New Mexico State Records Center and Archives (NMAC publisher)",
                    "issuing_agency": "New Mexico Health Care Authority, Income Support Division",
                    "document_subtype": "administrative_code",
                    "program": "ssi_state_supplement",
                    "state_program": "Supplement for SSI recipients in adult residential shelter care homes (ARSCH); General Assistance (same chapter)",
                    "federal_program": "SSI",
                    "state": "NM",
                    "nmac_citation": f"8.106.{part_number}",
                    "nmac_title": "8",
                    "nmac_chapter": "106",
                    "nmac_part": part_number,
                    "effective_date_printed": long_date(eff.group(1)),
                    "index_url": NM_INDEX_URL,
                    "srca_chapter_page": NM_SRCA_CHAPTER_URL,
                    "source_discovery_group": "us-nm/regulation/nmac/8/106",
                    "discovered_via": f"{DISCOVERED_VIA_2} {NM_INDEX_URL}",
                },
            }
        )
    index_info = {
        "index_url": NM_INDEX_URL,
        "index_document_count": len(seen),
        "taken_count": len(docs),
        "families": [
            {"family": f"8.{ch} NMAC parts linked on the HCA ISD index", "found": n, "taken": len(docs) if ch == "106" else 0}
            for ch, n in sorted(chapter_counts.items())
        ],
    }
    return docs, index_info


# ---------------------------------------------------------------- New Hampshire (Adult Assistance Manual)

NH_LANDING_URL = "https://www.dhhs.nh.gov/aam_htm/newaam.htm"
NH_TOC_BASE = "https://www.dhhs.nh.gov/aam_htm/whgdata/"
NH_HTML_BASE = "https://www.dhhs.nh.gov/aam_htm/html/"


@builder2("NH")
def build_nh(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """New Hampshire Old Age Assistance, Aid to the Needy Blind and Aid to the Permanently and
    Totally Disabled (the state supplement categories): the DHHS Adult Assistance Manual (AAM),
    every topic page reachable from the RoboHelp table of contents (whgdata/whlstt*.htm), the same
    publisher, structure and citation convention as the Family Assistance Manual scope
    (us-nh/manual/dhhs/fam/<topic>-fam). dhhs.nh.gov answers HTTP 403 to a plain client and 200
    to a browser TLS fingerprint; the extractor's browser_impersonation option is used."""
    queue = ["whlstt0.htm"]
    seen_toc: list[str] = []
    pages: list[tuple[str, str]] = []
    while queue:
        name = queue.pop(0)
        if name in seen_toc:
            continue
        seen_toc.append(name)
        text = fetch_impersonated(NH_TOC_BASE + name, cache_dir / "nh" / "whgdata" / name, pause=0.3)
        for match in re.finditer(r'href="(whlstt\d+\.htm)#?\d*"', text):
            if match.group(1) not in seen_toc:
                queue.append(match.group(1))
        for match in re.finditer(r'<a[^>]*href="\.\./html/([^"#]+\.htm)"[^>]*>(.*?)</a>', text, re.S):
            item = (match.group(1), strip_tags(match.group(2)))
            if item[0] not in {p[0] for p in pages}:
                pages.append(item)
    if len(pages) < 400:
        raise SystemExit(f"only {len(pages)} AAM topic pages found from the TOC; layout changed?")
    docs = []
    for filename, label in pages:
        slug = re.sub(r"[^a-z0-9]+", "-", filename[:-4].lower()).strip("-")
        docs.append(
            {
                "source_id": f"nh-dhhs-aam-{slug}",
                "jurisdiction": "us-nh",
                "document_class": "manual",
                "title": f"New Hampshire Adult Assistance Manual: {label}",
                "source_url": NH_HTML_BASE + filename,
                "source_format": "html",
                "source_as_of": SOURCE_AS_OF,
                "expression_date": SOURCE_AS_OF,
                "citation_path": f"us-nh/manual/dhhs/aam/{slug}",
                "request": {"browser_impersonation": True},
                "metadata": {
                    "primary_source": True,
                    "source_authority": "New Hampshire Department of Health and Human Services, Bureau of Family Assistance",
                    "document_subtype": "policy_manual_topic",
                    "program": "ssi_state_supplement",
                    "state_program": "Old Age Assistance (OAA), Aid to the Needy Blind (ANB), Aid to the Permanently and Totally Disabled (APTD)",
                    "federal_program": "SSI",
                    "state": "NH",
                    "manual_landing_page": NH_LANDING_URL,
                    "manual_toc_url": NH_TOC_BASE + "whlstt0.htm",
                    "toc_label": label,
                    "index_url": NH_TOC_BASE + "whlstt0.htm",
                    "source_discovery_group": "us-nh/manual/dhhs/aam",
                    "discovered_via": f"{DISCOVERED_VIA_2} {NH_TOC_BASE}whlstt0.htm",
                    "access_note": "dhhs.nh.gov: HTTP 403 (424-byte body) to a plain client, HTTP 200 to a chrome120 TLS fingerprint on 2026-09-10; fetched with the extractor's browser_impersonation option, TLS verification on",
                },
            }
        )
    if len({d["citation_path"] for d in docs}) != len(docs):
        raise SystemExit("duplicate AAM citation paths")
    index_info = {
        "index_url": NH_TOC_BASE + "whlstt0.htm",
        "index_document_count": len(pages),
        "taken_count": len(docs),
        "families": [
            {"family": f"Adult Assistance Manual topic pages ({len(seen_toc)} RoboHelp TOC files walked)", "found": len(pages), "taken": len(docs)},
        ],
    }
    return docs, index_info


# ---------------------------------------------------------------- Maine (10-144 Ch. 332 Part 11)

ME_RULES_INDEX_URL = "https://www.maine.gov/sos/rulemaking/agency-rules/department-health-and-human-services-rules"
ME_CH332_INDEX_URL = "https://www.maine.gov/sos/rulemaking/agency-rules/mainecare-eligibility-manual"
ME_CH332_EXPRESSION_DATE = "2025-04-29"  # filing 2025-101; the date the 2026-09-10 CHIP scope records for the same docx


@builder2("ME")
def build_me(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Maine State Supplement: 10-144 C.M.R. Chapter 332 MaineCare Eligibility Manual, Part 11
    'State Supplement' (DHHS Office for Family Independence), from the Secretary of State's
    agency-rules index (the chapter is one Word document; Part 11 is segmented out with the same
    start/stop convention and citation as the CHIP scope's Part 5,
    us-me/regulation/dhhs/ofi/chapter-332/part-<n>/section-<m>)."""
    rules_index = fetch(session, ME_RULES_INDEX_URL, cache_dir / "me" / "dhhs-rules.html")
    start = rules_index.find("10-144 Department of He")
    end = rules_index.find("10-146 Office of Data")
    segment = rules_index[start:end] if 0 < start < end else rules_index
    chapters_10_144 = sorted(set(re.findall(r"Ch\. (\d+)\b", strip_tags(segment))), key=int)
    if "332" not in chapters_10_144:
        raise SystemExit("10-144 Ch. 332 not listed on the SOS DHHS rules index")
    ch332 = fetch(session, ME_CH332_INDEX_URL, cache_dir / "me" / "ch332.html", pause=1.0)
    docx = re.search(r'href="(/sos/sites/maine\.gov\.sos/files/inline-files/144c332-[^"]+\.docx)"', ch332)
    appendices = re.findall(r'href="(/sos/sites/maine\.gov\.sos/files/inline-files/144c332-App[^"]+\.docx)"', ch332)
    others = sorted(set(re.findall(r'href="(/sos/sites/maine\.gov\.sos/files/content/assets/144c33[3-6]\.docx?)"', ch332)))
    if not docx:
        raise SystemExit("no Chapter 332 Word document on the MaineCare Eligibility Manual page")
    url = "https://www.maine.gov" + docx.group(1)
    filing = re.search(r"144c332-(\d{4}-\d{3})", url)
    doc = {
        "source_id": "me-ofi-mainecare-eligibility-manual-part-11",
        "jurisdiction": "us-me",
        "document_class": "regulation",
        "title": "Maine 10-144 C.M.R. Chapter 332 MaineCare Eligibility Manual, Part 11: State Supplement",
        "source_url": url,
        "source_format": "docx",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": ME_CH332_EXPRESSION_DATE,
        "citation_path": "us-me/regulation/dhhs/ofi/chapter-332/part-11",
        "extraction": {
            "segmentation": "labeled_sections",
            "start_after_pattern": r"^PART 11$",
            "stop_text_pattern": r"^PART 12$",
            "section_heading_pattern": r"^SECTION (?P<section>\d+):\s+(?P<heading>.+?)\s*$",
            "section_label_template": "section-{section}",
        },
        "metadata": {
            "primary_source": True,
            "source_authority": "Maine Department of Health and Human Services Office for Family Independence",
            "publication_authority": "Maine Secretary of State Administrative Procedure Act Office",
            "document_subtype": "administrative_rules_part",
            "program": "ssi_state_supplement",
            "state_program": "State Supplement (State Optional Supplement Program, 1974)",
            "federal_program": "SSI",
            "state": "ME",
            "rule_chapter": "10-144 C.M.R. Chapter 332",
            "rule_part": "11",
            "rule_filing": filing.group(1) if filing else None,
            "manual_landing_page": ME_CH332_INDEX_URL,
            "index_url": ME_RULES_INDEX_URL,
            "source_discovery_group": "us-me/regulation/ssi-state-supplement",
            "discovered_via": f"{DISCOVERED_VIA_2} {ME_RULES_INDEX_URL}",
            "extraction_note": "the chapter Word document carries all 18 parts; Part 11 is cut from the body heading 'PART 11' (the table-of-contents line 'PART 11: STATE SUPPLEMENT' is not matched) to 'PART 12'; the Part 11 preamble before SECTION 1 is not a labeled section",
            "expression_date_note": "filing 2025-101; the same date the 2026-09-10 CHIP scope records for this document",
        },
    }
    doc["metadata"] = {k: v for k, v in doc["metadata"].items() if v is not None}
    index_info = {
        "index_url": ME_RULES_INDEX_URL,
        "index_document_count": len(chapters_10_144) + len(appendices),
        "taken_count": 1,
        "families": [
            {"family": "10-144 Ch. 332 MaineCare Eligibility Manual parts (one Word document, 18 parts)", "found": 18, "taken": 1},
            {"family": "10-144 Ch. 332 appendices and charts", "found": len(appendices), "taken": 0},
            {"family": f"other 10-144 chapters on the SOS DHHS rules index (incl. OFI Ch. 301, 323, 331, 333-336; Ch. 332 page also links {len(others)} of them)", "found": len(chapters_10_144) - 1, "taken": 0},
        ],
    }
    return [doc], index_info


# ---------------------------------------------------------------- South Carolina (MPPM Chapter 403)

SC_MPPM_PAGE_URL = "https://www.scdhhs.gov/providers/manuals/sc-medicaid-policy-and-procedures-manual"
SC_OSS_PROGRAM_URL = "https://www.scdhhs.gov/resources/programs-and-initiatives/long-term-living/optional-state-supplementation-oss"
SC_OSS_PROVIDER_MANUAL_URL = "https://www.scdhhs.gov/providers/manuals/optional-state-supplementation-services-manual"


@builder2("SC")
def build_sc(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """South Carolina Optional State Supplementation (OSS): SCDHHS Medicaid Policy and Procedures
    Manual Chapter 403 (Word document) from the MPPM index (scdhhs.gov redirects to
    img1.scdhhs.gov/mppm/, whose chain omits the Go Daddy Secure Certificate Authority G2
    intermediate; the publisher's public intermediate is added under data/certs, verification on).
    Retry of the batch-1 blocked row: scdhhs.gov answered on 2026-09-10 from a US network."""
    if not SC_CA_BUNDLE.exists():
        raise SystemExit(f"missing {SC_CA_BUNDLE}; build it from certifi + data/certs/godaddy-secure-certificate-authority-g2.pem")
    sc_session = requests.Session()
    sc_session.headers.update(session.headers)
    sc_session.verify = str(SC_CA_BUNDLE)
    page = fetch(sc_session, SC_MPPM_PAGE_URL, cache_dir / "sc" / "mppm-index.html")
    links: list[tuple[str, str]] = []
    for url, label in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        label = strip_tags(label)
        if label and (url, label) not in links and not url.startswith("#"):
            links.append((url, label))
    mppm_docs = [(u, text) for u, text in links if re.search(r"img1\.scdhhs\.gov/mppm/SCMPPM/.*\.docx$", u)]
    internal = [(u, text) for u, text in links if "sharepoint.com" in u]
    forms = [(u, text) for u, text in links if "medsweb.scdhhs.gov" in u]
    chapter = [(u, text) for u, text in mppm_docs if u.endswith("/Chapter_403.docx")]
    if len(chapter) != 1:
        raise SystemExit("MPPM Chapter 403 (Optional State Supplementation) not found on the MPPM index")
    url, label = chapter[0]
    doc = {
        "source_id": "sc-scdhhs-mppm-chapter-403",
        "jurisdiction": "us-sc",
        "document_class": "manual",
        "title": f"South Carolina Medicaid Policy and Procedures Manual, Chapter 403: {label}",
        "source_url": url,
        "source_format": "docx",
        "source_as_of": SOURCE_AS_OF,
        "expression_date": SOURCE_AS_OF,
        "citation_path": "us-sc/manual/scdhhs/mppm/chapter-403",
        "extraction": {
            "segmentation": "labeled_sections",
            # page 1 is the chapter table of contents ("403.01 Introduction 2" ... "403.12 Terminated SSI Benefits 12")
            "start_after_pattern": r"^403\.12\s+Terminated SSI Benefits\s+\d+\s*$",
            "section_heading_pattern": r"^(?P<label>403\.\d{2}(?:\.\d{2}[A-Z]?)?)\s+(?P<heading>[A-Z][^\n]{2,120}?)\s*$",
        },
        "metadata": {
            "primary_source": True,
            "source_authority": "South Carolina Department of Health and Human Services",
            "hosting_authority": "img1.scdhhs.gov (SCDHHS document host the MPPM page redirects to)",
            "document_subtype": "policy_manual_chapter_docx",
            "program": "ssi_state_supplement",
            "state_program": "Optional State Supplementation (OSS)",
            "federal_program": "SSI",
            "state": "SC",
            "manual_chapter": "403",
            "mppm_index_url": SC_MPPM_PAGE_URL,
            "program_page_url": SC_OSS_PROGRAM_URL,
            "provider_manual_alternative": f"{SC_OSS_PROVIDER_MANUAL_URL} (OSS Services provider manual; separate family, not taken)",
            "index_url": SC_MPPM_PAGE_URL,
            "source_discovery_group": "us-sc/manual/scdhhs/mppm",
            "discovered_via": f"{DISCOVERED_VIA_2} {SC_MPPM_PAGE_URL}",
            "extraction_granularity": "labeled_sections (403.xx headings); the page-1 table of contents is skipped with start_after_pattern",
            "expression_date_note": "fetch date; each section prints its own Eff./Rev. date (latest 05/01/25)",
            "tls_note": "img1.scdhhs.gov omits the Go Daddy Secure Certificate Authority - G2 intermediate; extract with REQUESTS_CA_BUNDLE=data/certs/img1-scdhhs-gov-ca-bundle.pem (certifi + the publisher's public intermediate); verification not disabled",
            "retry_note": "batch 1 (2026-09-10, non-US network): HTTP 403 to plain and chrome120 clients; retried 2026-09-10T21:38Z from a US network: site answers, /resources/mppm is HTTP 404 (moved to /providers/manuals/sc-medicaid-policy-and-procedures-manual)",
        },
    }
    index_info = {
        "index_url": SC_MPPM_PAGE_URL,
        "index_document_count": len(mppm_docs) + len(internal) + len(forms) + 1,
        "taken_count": 1,
        "families": [
            {"family": "MPPM Word documents (sections 100-800, chapters 401-703, MIAP manual)", "found": len(mppm_docs), "taken": 1},
            {"family": "internal SharePoint training and job-aid links (not public)", "found": len(internal), "taken": 0},
            {"family": "forms and manual notices listing (medsweb.scdhhs.gov)", "found": len(forms), "taken": 0},
            {"family": f"OSS Services provider manual ({SC_OSS_PROVIDER_MANUAL_URL})", "found": 1, "taken": 0},
        ],
    }
    return [doc], index_info


# ---------------------------------------------------------------- batch 2 static rows

# Adapter scopes extracted directly into the corpus base (no manifest): OH and MD.
ADAPTER_ROWS = {
    "OH": {
        "queue_status": "agent_ready",
        "source_kind": "official_state_regulation",
        "primary_source_url": "https://codes.ohio.gov/ohio-administrative-code/chapter-5122-36",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-oh", "document_class": "regulation",
                         "version": "2026-09-10-ssi-state-supplement-agency-5122-chapter-5122-36"},
        "index_url": "https://codes.ohio.gov/ohio-administrative-code/chapter-5122-36",
        "index_document_count": 5,
        "taken_count": 5,
        "index_families": "OAC chapter 5122-36 Residential State Supplement Program rules (5122-36-01 Purpose and definitions, -02 RSS non-financial eligibility, -03 Application process, -04 Responsibilities of the living arrangement, -05 Determination of RSS payment): 5 found / 5 taken",
        "notes": (
            "Retry 2026-09-10T21:36Z from a US network: codes.ohio.gov HTTP 200 (48,015 bytes) to a plain client (batch 1: "
            "connect timeout). Residential State Supplement (RSS), OAC chapter 5122-36 (Department of Behavioral Health, "
            "agency 5122), extracted with the existing adapter `extract-ohio-administrative-code --only-chapter 5122-36` "
            "(no manifest; run id 2026-09-10-ssi-state-supplement-agency-5122-chapter-5122-36): 8 rows (collection, agency, "
            "chapter, 5 rules; rules effective 2022-09-03 and 2023-07-01), coverage complete. Citation "
            "us-oh/regulation/agency-5122/chapter-5122-36/rule-5122-36-0N, the adapter convention of the 5101-4 SNAP scope. "
            "The container row us-oh/regulation is shared with the 2026-07-16-agency-5101-4 scope by adapter design "
            "(collection root); rule rows are unique across us-oh."
        ),
    },
    "MD": {
        "queue_status": "agent_ready",
        "source_kind": "official_state_regulation",
        "primary_source_url": "https://regs.maryland.gov",
        "target_manifest": None,
        "target_scope": {"jurisdiction": "us-md", "document_class": "regulation",
                         "version": "2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapter-07"},
        "index_url": "https://github.com/maryland-dsd/law-xml-codified (us/md/exec/comar/07/03, publication/2026-09-09.2026-09-09)",
        "index_document_count": 25,
        "taken_count": 2,
        "index_families": "COMAR Title 07 Subtitle 03 Family Investment Administration chapters: 25 found / 2 taken (07.03.06 Mandatory State Supplement for Supplemental Security Income Recipients, 07.03.07 Public Assistance to Adults); 07.03.03 Family Investment Program already in the corpus (TCA scope)",
        "notes": (
            "Replacement 1 (after OK blocked). Maryland's supplements: Public Assistance to Adults (PAA, optional supplement "
            "for adults in assisted living and certain group homes) under COMAR 07.03.07 and the Mandatory State Supplement "
            "for SSI recipients under COMAR 07.03.06 (DHS Family Investment Administration). Both chapters extracted with the "
            "existing adapter `extract-maryland-comar --only-title 07 --only-subtitle 03 --only-chapter 06|07` from the "
            "Division of State Documents' official COMAR XML publication (publication/2026-09-09.2026-09-09), two run ids "
            "(...-chapter-06: 14 rows; ...-chapter-07: 19 rows), coverage complete, citation "
            "us-md/regulation/title-07/subtitle-03/chapter-0N/regulation-NN (the TCA scope's convention). Container rows "
            "us-md/regulation, .../title-07 and .../title-07/subtitle-03 are shared with the TCA chapter-03 scope by adapter "
            "design; regulation rows are unique across us-md. regs.maryland.gov paths answered HTTP 404 to guessed URLs; the "
            "adapter's XML source is the DSD publication repository."
        ),
    },
}

POINTER_ROWS_2 = {
    "OR": {
        "index_families": "pointer to the ODHS Oregon Programs Eligibility Notebook scope (1 PDF, 1,323 page rows; 47 pages name OSIP cash, 392 name OSIP or OSIPM): 0 new documents taken; OAR chapter 461 (secure.sos.state.or.us, HTTP 200) is the adopted-rule family, not taken",
        "target_manifest": "manifests/us-or-snap-manual.yaml",
        "target_scope": {"jurisdiction": "us-or", "document_class": "manual", "version": "2026-07-16-or-programs-eligibility-notebook"},
        "index_url": "https://sharedsystems.dhsoha.state.or.us/DHSForms/Served/de2818.pdf",
        "notes": (
            "Done by pointer. Oregon Supplemental Income Program (OSIP) cash supplements and special needs payments are covered "
            "by the ODHS Oregon Programs Eligibility Notebook (OPEN, DE 2818, 07/2026), in the corpus as us-or/manual/odhs/open "
            "(1,323 page rows; 47 pages name OSIP cash, e.g. 'OSIP Oregon Supplemental Income Program Cash supplements and "
            "special needs', OSIP maintenance standard, OAR 461-140-0296/-0300 references). The adopted rules are OAR chapter 461 "
            "on the Secretary of State's OARD (displayChapterRules.action?selectedChapter=99, HTTP 200 on 2026-09-10), a "
            "chapter shared with SNAP, TANF and ERDC; not taken. oregon.gov/odhs guessed OSIP page 404."
        ),
    },
    "UT": {
        "index_families": "pointer to the DWS Eligibility Manual scope (2,398 rows; section 205-10 State Supplemental Payments to SSI Recipients present with the 2026-01-01 rates): 0 new documents taken",
        "target_manifest": "manifests/us-ut-manuals.yaml",
        "target_scope": {"jurisdiction": "us-ut", "document_class": "manual", "version": "2026-05-27-ut-manuals-r2026-07-15-self-contained"},
        "index_url": "https://jobs.utah.gov/infosource/eligibilitymanual/Welcome/Welcome.htm",
        "notes": (
            "Done by pointer. Utah's State Supplemental Payment to SSI recipients is administered by the Department of Workforce "
            "Services under Eligibility Manual section 205-10 'State Supplemental Payments to SSI Recipients - General "
            "Information' (rates as of 2026-01-01: $3.91/month single, $12.19 couples in the household of another, $5.75 couples "
            "living alone or with others; institutionalized SSI recipients are handled under Medicaid, Utah Admin. Code "
            "R414-306-6), in the corpus as us-ut/manual/dws/eligibility-manual/200-program-eligibility-requirements-205-10-... "
            "(2 blocks). R414-306-6 (adminrules.utah.gov) is not in the corpus and not taken."
        ),
    },
    "ID": {
        "index_families": "pointer to IDAPA 16.03.05 Eligibility for Aid to the Aged, Blind, and Disabled (AABD) (1 PDF, 286 rows, program ssi_state_supplement, in the corpus): 0 new documents taken",
        "target_manifest": "manifests/us-id-aabd-rules.yaml",
        "target_scope": {"jurisdiction": "us-id", "document_class": "regulation", "version": "2026-07-04-id-aabd-rules"},
        "index_url": "https://adminrules.idaho.gov/rules/current/16/160305.pdf",
        "notes": (
            "Done by pointer. Idaho's supplement is AABD cash assistance under IDAPA 16.03.05 'Eligibility for Aid to the Aged, "
            "Blind, and Disabled (AABD)' (Department of Health and Welfare), already in the corpus in full as "
            "us-id/regulation/idapa/16/03/05 (286 rows, version 2026-07-04-id-aabd-rules, metadata program ssi_state_supplement)."
        ),
    },
}

BLOCKED_ROWS_2 = {
    "OK": (
        "https://oklahoma.gov/okdhs/library/policy/current/oac-340/chapter-15.html",
        "Oklahoma's State Supplemental Payment (SSP) is governed by OAC 340:15 (OKDHS). Both official publishers answer a "
        "Cloudflare challenge: oklahoma.gov/okdhs policy library (chapter-15 and the OAC 340 index) HTTP 403 (5,564-byte "
        "'Just a moment...' page) to a plain client and HTTP 403 (5,906 bytes) to chrome120 impersonation; the Secretary of "
        "State's rules.ok.gov/home likewise HTTP 403 to both (the 2026-07-21 SNAP rules scope came from rules.ok.gov). The "
        "corpus's OHCA Medicaid manual scope mentions SSP on 11 rows but does not carry OAC 340:15. No index inventory possible.",
    ),
}

# Batch-1 blocked rows retried in batch 2; NY stays blocked.
RETRY_NOTES = {
    "NY": (
        "Retried 2026-09-10T21:36Z from a US network, same failure: plain client 'Remote end closed connection without "
        "response' on https://otda.ny.gov/programs/ssp/; chrome120 impersonation HTTP 200 with a 7,559-byte JavaScript "
        "challenge ('Please enable JavaScript to view the page content. Your support ID is ...'), no page content."
    ),
}

SOURCE_KINDS_2 = {
    "KY": "official_state_regulation",
    "LA": "official_state_agency_manual",
    "NE": "official_state_regulation",
    "NM": "official_state_regulation",
    "NH": "official_state_agency_manual",
    "ME": "official_state_regulation",
    "SC": "official_state_agency_manual",
}
ROW_NOTES_2 = {
    "KY": (
        "State Supplementation: 921 KAR 2:015 'Supplemental programs for persons who are aged, blind, or have a disability' "
        "(CHFS/DCBS), one HTML regulation from the LRC's 921 KAR Chapter 2 index (19 regulations listed: 14 current, 5 "
        "inactive/repealed; 015 taken), history last effective 2024-07-30. document_class regulation, citation "
        "us-ky/regulation/kar/921/002/015 (the CHIP 907 KAR convention). apps.legislature.ky.gov HTTP 200 to a plain client; "
        "chfs.ky.gov operations-manual path guessed 404."
    ),
    "LA": (
        "Optional State Supplement (OSS): LDH Medicaid Eligibility Manual section J-0000 'Medicaid Eligibility Cards and "
        "Optional State Supplement Payments' (Reissued July 21, 2025; J-300 to J-340 OSS payment rules), one PDF of the 99 "
        "sections on the LDH manual index. ldh.la.gov HTTP 403 to a plain client, 200 to a chrome120 TLS fingerprint: fetched "
        "with the extractor's browser_impersonation option (as the POMS SI manifest), TLS verification on. document_class "
        "manual, citation us-la/manual/ldh/medicaid-eligibility/j-0000, page granularity."
    ),
    "NE": (
        "Assistance to the Aged, Blind, or Disabled (AABD) payment program: Title 469 NAC chapters 1-4 (DHHS; effective "
        "2022-06-06) from the Secretary of State's rules.nebraska.gov chapter API, the 475 NAC SNAP scope's publisher. "
        "rules.nebraska.gov omits the DigiCert Global G2 TLS RSA SHA256 2020 CA1 intermediate; the publisher's public "
        "intermediate is in data/certs and REQUESTS_CA_BUNDLE=data/certs/rules-nebraska-gov-ca-bundle.pem is used "
        "(verification on; the SNAP manifest's verify_tls: false is not used). document_class regulation, citation "
        "us-ne/regulation/title-469/chapter-N/<section>, labeled sections."
    ),
    "NM": (
        "Supplement for SSI recipients in adult residential shelter care homes (ARSCH) and General Assistance: 8.106 NMAC "
        "'State Funded Assistance Programs' (HCA Income Support Division), all 17 parts linked from the HCA ISD regulations "
        "index and served by the State Records Center and Archives (effective dates 2004-07-01 to 2025-03-01). GA and the "
        "ARSCH supplement share the chapter's general, eligibility and benefit parts, so the whole chapter is taken. "
        "document_class regulation, citation us-nm/regulation/nmac/8/106/<part>/8.106.<part>.<section> (the 8.100/8.139 SNAP "
        "convention)."
    ),
    "NH": (
        "Old Age Assistance, Aid to the Needy Blind and Aid to the Permanently and Totally Disabled (the state supplement "
        "categories): DHHS Adult Assistance Manual, every topic page from the RoboHelp table of contents (the Family "
        "Assistance Manual scope's structure). dhhs.nh.gov HTTP 403 to a plain client, 200 to a chrome120 TLS fingerprint: "
        "fetched with the extractor's browser_impersonation option, TLS verification on. document_class manual, citation "
        "us-nh/manual/dhhs/aam/<topic>-aam."
    ),
    "ME": (
        "State Supplement: 10-144 C.M.R. Chapter 332 MaineCare Eligibility Manual, Part 11 'State Supplement' (DHHS OFI), "
        "cut from the chapter Word document on the Secretary of State's agency-rules index (filing 2025-101; Part 5 CHIP is "
        "already in the corpus from the same document). The SOS 10-144 index lists no separate state-supplement chapter. "
        "document_class regulation, citation us-me/regulation/dhhs/ofi/chapter-332/part-11/section-N."
    ),
    "SC": (
        "Optional State Supplementation (OSS): SCDHHS Medicaid Policy and Procedures Manual Chapter 403 (Word document, "
        "sections 403.01-403.12 with printed Eff./Rev. dates to 05/01/25) from the MPPM index at img1.scdhhs.gov/mppm/ "
        "(19 MPPM documents listed; 403 taken). Retry of the batch-1 blocked row: scdhhs.gov answered from a US network on "
        "2026-09-10; img1.scdhhs.gov omits the Go Daddy G2 intermediate, added under data/certs "
        "(REQUESTS_CA_BUNDLE=data/certs/img1-scdhhs-gov-ca-bundle.pem, verification on). document_class manual, citation "
        "us-sc/manual/scdhhs/mppm/chapter-403/<section>. The OSS Services provider manual is a separate family, not taken."
    ),
}


def update_queue_batch2(results: dict[str, dict]) -> dict:
    """Rewrite only the batch-2 rows (and the retried batch-1 blocked rows NY, OH, SC)."""
    queue = yaml.safe_load(QUEUE.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    for code, index in results.items():
        row = rows[f"us-{code.lower()}"]
        docs = index["docs"]
        families = "; ".join(f"{f['family']}: {f['found']} found / {f['taken']} taken" for f in index["families"])
        row.update(
            {
                "queue_status": "agent_ready",
                "source_kind": index["source_kind"],
                "primary_source_url": docs[0]["source_url"],
                "target_manifest": str(manifest_path(code).relative_to(ROOT)),
                "target_scope": {"jurisdiction": f"us-{code.lower()}", "document_class": docs[0]["document_class"], "version": VERSION},
                "index_url": index["index_url"],
                "index_document_count": index["index_document_count"],
                "taken_count": index["taken_count"],
                "index_families": families,
                "notes": index["note"],
            }
        )
    for code, fields in ADAPTER_ROWS.items():
        rows[f"us-{code.lower()}"].update(fields)
    for code, pointer in POINTER_ROWS_2.items():
        rows[f"us-{code.lower()}"].update(
            {
                "queue_status": "done",
                "source_kind": "official_state_or_ssa_document",
                "primary_source_url": None,
                "target_manifest": pointer["target_manifest"],
                "target_scope": pointer["target_scope"],
                "index_url": pointer["index_url"],
                "index_document_count": None,
                "taken_count": 0,
                "index_families": pointer["index_families"],
                "notes": pointer["notes"] + " (2026-09-10 state-supplement batch 2.)",
            }
        )
    for code, (url, note) in BLOCKED_ROWS_2.items():
        rows[f"us-{code.lower()}"].update(
            {
                "queue_status": "blocked_primary_source",
                "source_kind": "state_agency_document",
                "primary_source_url": url,
                "target_manifest": None,
                "index_url": url,
                "index_document_count": None,
                "taken_count": 0,
                "index_families": "no index inventory possible (publisher blocked; see notes)",
                "notes": f"Blocked 2026-09-10 (state-supplement batch 2): {note}",
            }
        )
    for code, note in RETRY_NOTES.items():
        row = rows[f"us-{code.lower()}"]
        if note not in row["notes"]:
            row["notes"] = row["notes"].rstrip() + " " + note
    queue["status_counts"] = {}
    for row in queue["states"]:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    note = (
        "2026-09-10 SSI state-supplement batch 2: scripts/build_ssi_state_supplement_manifests.py --batch 2; NY, OH, SC retried "
        "from a US network (OH, SC extracted; NY still blocked); next ten needs_review states by population attempted (LA, KY, "
        "OR, OK, UT, NE, NM, ID, NH, ME) with replacement MD after OK blocked; "
        "docs/ingest-runs/2026-09-10-ssi-state-supplements-batch-2.md."
    )
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


# ======================================================================= batch 3 (2026-09-11)
# The remaining rows: the six states with no row (AR, AZ, MS, ND, TN, WV: no optional state
# supplement per POMS SI 01415.010, done with the POMS pointer), the five needs_review rows
# (MO, WI, SD, AK, WY) and one re-probe of OK.

BATCH3_ORDER = ("AR", "AZ", "MS", "ND", "TN", "WV", "MO", "WI", "SD", "AK", "WY", "OK")
SOURCE_AS_OF_3 = "2026-09-11"
DISCOVERED_VIA_3 = "manual-review:ssi-agent-queue batch 3 (state-administered supplements); publisher index"
POMS_SI_01415_010_URL = "https://secure.ssa.gov/apps10/poms.nsf/lnx/0501415010"
POMS_SI_01415_INDEX_URL = "https://secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05014"
BUILDERS_3: dict[str, str] = {}


def builder3(code: str):
    def register(func):
        BUILDERS_3[code] = func.__name__
        return func

    return register


def robohelp_toc(load, first: str = "toc.new.js") -> tuple[list[tuple[str, str]], list[str]]:
    """Walk an Adobe RoboHelp 2022 table of contents: ``whxdata/toc.new.js`` and every book's
    ``whxdata/<key>.new.js`` file. ``load(name)`` returns the JavaScript text. Returns the
    topic pages in TOC order as (relative url, label) and the list of TOC files walked."""
    queue = [first]
    seen: list[str] = []
    topics: list[tuple[str, str]] = []
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.append(name)
        text = load(name)
        match = re.search(r"var toc =\s*(\[.*?\]);\s*window", text, re.S)
        if not match:
            raise SystemExit(f"RoboHelp TOC file {name} has no toc array; layout changed?")
        for item in json.loads(match.group(1)):
            url = (item.get("url") or "").split("#")[0]
            if url and url not in {t[0] for t in topics}:
                topics.append((url, re.sub(r"\s+", " ", item["name"]).strip()))
            if item.get("key"):
                queue.append(f"{item['key']}.new.js")
    return topics, seen


ROBOHELP_DROP_SELECTORS = [".topic-header", ".topic-header-shadow", ".breadcrumbs", ".minitoc", ".expanding-content"]


# ---------------------------------------------------------------- Alaska (Adult Public Assistance Manual)

AK_LANDING_URL = "http://dpaweb.hss.state.ak.us/manuals/apa/apa.htm"
AK_BASE_URL = "http://dpaweb.hss.state.ak.us/manuals/apa/"
AK_TOC_URL = AK_BASE_URL + "whxdata/toc.new.js"


@builder3("AK")
def build_ak(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Alaska Adult Public Assistance (APA), the state's SSI supplement: the Division of Public
    Assistance's Adult Public Assistance Manual, every topic page reachable from the RoboHelp
    table of contents, plus a snapshot of each TOC file, the structure and citation convention
    of the 2026-07-16 Alaska SNAP manual scope (us-ak/manual/dpa/snap/...)."""
    topics, toc_files = robohelp_toc(
        lambda name: fetch(session, AK_BASE_URL + "whxdata/" + name, cache_dir / "ak" / "whxdata" / name, pause=0.2)
    )
    # the TOC lists 561 entries, 336 of them same-page anchors (#...): 225 distinct topic pages
    if len(topics) < 200:
        raise SystemExit(f"only {len(topics)} APA topic pages found from the TOC; layout changed?")
    title_page = strip_tags(fetch(session, AK_BASE_URL + "transmittals/title_page.htm", cache_dir / "ak" / "title_page.htm"))
    if "ADULT PUBLIC ASSISTANCE MANUAL" not in title_page.upper():
        raise SystemExit("APA title page does not name the Adult Public Assistance Manual")
    common = {
        "primary_source": True,
        "source_authority": "Alaska Department of Health, Division of Public Assistance",
        "program": "ssi_state_supplement",
        "state_program": "Adult Public Assistance (APA)",
        "federal_program": "SSI",
        "state": "AK",
        "manual_landing_page": AK_LANDING_URL,
        "manual_toc_url": AK_TOC_URL,
        "manual_base_url": AK_BASE_URL,
        "index_url": AK_TOC_URL,
        "source_discovery_group": "us-ak/manual/dpa/apa",
        "discovered_via": f"{DISCOVERED_VIA_3} {AK_TOC_URL}",
        "expression_date_note": "fetch date; topic pages carry their own manual-change (MC) transmittal references, latest Memo MC #76 (09/26)",
    }
    docs = []
    for order, (url, label) in enumerate(topics, start=1):
        slug = re.sub(r"[^a-z0-9]+", "-", url[:-4].lower()).strip("-") if url.lower().endswith(".htm") else re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")
        docs.append(
            {
                "source_id": f"ak-dpa-apa-{slug}",
                "jurisdiction": "us-ak",
                "document_class": "manual",
                "title": f"Alaska Adult Public Assistance Manual: {label}",
                "source_url": AK_BASE_URL + quote(url, safe="/:()_.-"),
                "source_format": "html",
                "source_as_of": SOURCE_AS_OF_3,
                "expression_date": SOURCE_AS_OF_3,
                "citation_path": f"us-ak/manual/dpa/apa/{slug}",
                "extraction": {
                    "html_drop_selectors": [".topic-header", ".topic-header-shadow", ".expanding-content", 'table:has(a[href*="transmittals/"])']
                },
                "metadata": {**common, "document_subtype": "policy_manual_topic", "toc_label": label, "toc_order": order},
            }
        )
    for order, name in enumerate(toc_files, start=1):
        key = "root" if name == "toc.new.js" else name[: -len(".new.js")]
        docs.append(
            {
                "source_id": f"ak-dpa-apa-toc-{key}",
                "jurisdiction": "us-ak",
                "document_class": "manual",
                "title": f"Alaska Adult Public Assistance Manual TOC: {key}",
                "source_url": AK_BASE_URL + "whxdata/" + name,
                "source_format": "javascript",
                "source_as_of": SOURCE_AS_OF_3,
                "expression_date": SOURCE_AS_OF_3,
                "citation_path": f"us-ak/manual/dpa/apa/navigation/toc-{key}",
                "metadata": {**common, "document_subtype": "manual_toc_snapshot", "toc_snapshot_key": key, "snapshot_order": order},
            }
        )
    if len({d["citation_path"] for d in docs}) != len(docs):
        raise SystemExit("duplicate APA citation paths")
    transmittals = sum(1 for url, _ in topics if url.lower().startswith("transmittals/"))
    index_info = {
        "index_url": AK_TOC_URL,
        "index_document_count": len(topics) + len(toc_files),
        "taken_count": len(docs),
        "families": [
            {"family": "Adult Public Assistance Manual policy topic pages (sections 400-482, addendum)", "found": len(topics) - transmittals, "taken": len(topics) - transmittals},
            {"family": "Adult Public Assistance Manual transmittal and manual-change memo pages", "found": transmittals, "taken": transmittals},
            {"family": "RoboHelp table-of-contents files (whxdata/*.new.js), snapshotted as navigation rows", "found": len(toc_files), "taken": len(toc_files)},
        ],
    }
    return docs, index_info


# ---------------------------------------------------------------- Wisconsin (DHS SSI handbooks)

WI_SSI_INDEX_URL = "https://www.dhs.wisconsin.gov/ssi/index.htm"
WI_PUBLICATIONS_URL = "https://www.dhs.wisconsin.gov/ssi/publications.htm"
WI_HANDBOOK_BASE = "https://www.emhandbooks.wisconsin.gov/"
WI_HANDBOOKS = {
    # slug on emhandbooks.wisconsin.gov -> (publication number, title, taken)
    "ssi-admin": ("P-23129", "SSI Administration Handbook", True),
    "ssi-e": ("P-20679", "SSI Exceptional Expense (SSI-E) Handbook", True),
    "cts": ("P-23131", "SSI Caretaker Supplement (CTS) Policy Handbook", False),
}


@builder3("WI")
def build_wi(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Wisconsin state SSI supplement (Wis. Stat. 49.77): the Department of Health Services'
    SSI Administration Handbook (P-23129) and SSI Exceptional Expense (SSI-E) Handbook
    (P-20679), every topic page from each handbook's RoboHelp table of contents on
    emhandbooks.wisconsin.gov, the DHS handbook host. Both handbooks are listed on the DHS
    SSI program's Forms and Publications page. The Caretaker Supplement handbook (P-23131) is
    a TANF-funded benefit to SSI parents (Wis. Stat. 49.775) and is a separate family."""
    pubs_page = fetch(session, WI_PUBLICATIONS_URL, cache_dir / "wi" / "publications.htm")
    main = re.search(r"<main.*?</main>", pubs_page, re.S)
    body = main.group(0) if main else pubs_page
    anchors = [(href, strip_tags(text)) for href, text in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)]
    handbooks = [(h, t) for h, t in anchors if "emhandbooks.wisconsin.gov" in h]
    forms = [(h, t) for h, t in anchors if re.search(r"/library/[Ff]-\d", h)]
    letters = [(h, t) for h, t in anchors if re.search(r"\.docx?$", h, re.I)]
    publications = [(h, t) for h, t in anchors if re.search(r"\bP-\d{5}", t) and "emhandbooks" not in h]
    for slug in WI_HANDBOOKS:
        if not any(f"/{slug}/" in h for h, _ in handbooks):
            raise SystemExit(f"{slug} handbook not linked from {WI_PUBLICATIONS_URL}")
    index_page = fetch(session, WI_SSI_INDEX_URL, cache_dir / "wi" / "index.htm")
    program_pages = sorted(set(re.findall(r'href="(/ssi/[a-z-]+\.htm)"', index_page)))
    docs = []
    families = []
    for slug, (pub, title, taken) in WI_HANDBOOKS.items():
        base = f"{WI_HANDBOOK_BASE}{slug}/"
        topics, toc_files = robohelp_toc(
            lambda name, base=base, slug=slug: fetch(session, base + "whxdata/" + name, cache_dir / "wi" / slug / "whxdata" / name, pause=0.2)
        )
        if not topics:
            raise SystemExit(f"no topics in the {slug} handbook TOC")
        families.append({"family": f"{title} ({pub}) topic pages, RoboHelp TOC on emhandbooks.wisconsin.gov", "found": len(topics), "taken": len(topics) if taken else 0})
        if not taken:
            continue
        first = strip_tags(fetch(session, base + topics[0][0], cache_dir / "wi" / slug / "first-topic.htm", pause=0.2))
        release = re.search(r"Release (\d\d-\d\d) ([A-Z][a-z]+ \d{1,2}, \d{4})", first)
        if not release:
            raise SystemExit(f"no 'Release NN-NN <date>' line on the first {slug} topic page")
        expression_date = long_date(release.group(2))
        for order, (url, label) in enumerate(topics, start=1):
            topic_slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^policyfiles/", "", url[:-4].lower())).strip("-")
            docs.append(
                {
                    "source_id": f"wi-dhs-{slug}-{topic_slug}",
                    "jurisdiction": "us-wi",
                    "document_class": "manual",
                    "title": f"Wisconsin {title}: {label}",
                    "source_url": base + url,
                    "source_format": "html",
                    "source_as_of": SOURCE_AS_OF_3,
                    "expression_date": expression_date,
                    "citation_path": f"us-wi/manual/dhs/ssi/{slug}/{topic_slug}",
                    "extraction": {"html_drop_selectors": ROBOHELP_DROP_SELECTORS},
                    "metadata": {
                        "primary_source": True,
                        "source_authority": "Wisconsin Department of Health Services",
                        "hosting_authority": "emhandbooks.wisconsin.gov (the DHS eligibility-handbook host)",
                        "document_subtype": "policy_handbook_topic",
                        "publication_number": pub,
                        "handbook": title,
                        "handbook_release": release.group(1),
                        "program": "ssi_state_supplement",
                        "state_program": "State SSI Supplement (Wis. Stat. 49.77)" if slug == "ssi-admin" else "SSI Exceptional Expense Supplement (SSI-E)",
                        "federal_program": "SSI",
                        "state": "WI",
                        "manual_landing_page": f"{base}{slug}.htm",
                        "manual_toc_url": base + "whxdata/toc.new.js",
                        "toc_label": label,
                        "toc_order": order,
                        "index_url": WI_PUBLICATIONS_URL,
                        "program_index_url": WI_SSI_INDEX_URL,
                        "source_discovery_group": f"us-wi/manual/dhs/ssi/{slug}",
                        "discovered_via": f"{DISCOVERED_VIA_3} {WI_PUBLICATIONS_URL}",
                        "extraction_note": "RoboHelp 2022 topic page; the topic header, breadcrumbs, mini table of contents and glossary pop-up text (.expanding-content) are dropped",
                    },
                }
            )
    families.extend(
        [
            {"family": "DHS SSI program web pages (index, apply, benefits, caretaker, eligibility, forms & publications, glossary, SSI-E, contacts)", "found": len(program_pages), "taken": 0},
            {"family": "Forms (F-numbers) on the Forms and Publications page", "found": len(forms), "taken": 0},
            {"family": "Interim-assistance letter templates (Word)", "found": len(letters), "taken": 0},
            {"family": "Fact sheets and publications (P-numbers other than the handbooks)", "found": len(publications), "taken": 0},
        ]
    )
    if len({d["citation_path"] for d in docs}) != len(docs):
        raise SystemExit("duplicate WI citation paths")
    index_info = {
        "index_url": WI_PUBLICATIONS_URL,
        "index_document_count": sum(f["found"] for f in families),
        "taken_count": len(docs),
        "families": families,
    }
    return docs, index_info


# ---------------------------------------------------------------- Missouri (SNC and SAB manuals)

MO_MANUALS_INDEX_URL = "https://dssmanuals.mo.gov/"
MO_SITEMAP_URLS = ["https://dssmanuals.mo.gov/wp-sitemap-posts-page-1.xml", "https://dssmanuals.mo.gov/wp-sitemap-posts-page-2.xml"]
MO_MANUALS = {
    # site slug -> (short code, manual title, state program, taken)
    "supplemental-nursing-care": ("snc", "Supplemental Nursing Care (SNC) Manual", "Supplemental Nursing Care (SNC)", True),
    "supplemental-aid-to-the-blind": ("sab", "Supplemental Aid to the Blind (SAB) Manual", "Supplemental Aid to the Blind (SAB)", True),
    "blind-pension": ("bp", "Blind Pension Manual", "Blind Pension (BP)", False),
}


@builder3("MO")
def build_mo(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Missouri's state supplements to SSI: the Family Support Division's Supplemental Nursing
    Care (SNC) Manual and Supplemental Aid to the Blind (SAB) Manual on dssmanuals.mo.gov,
    every section page from the site's WordPress sitemap (the 2026-09-10 MHABD Medicaid scope's
    method; citation us-mo/manual/dss/<manual>/<section path>). The Blind Pension Manual is a
    state-only pension for blind persons not eligible for SAB (separate family, not taken;
    its 0505.000.00 eligibility page is password-protected)."""
    home = fetch(session, MO_MANUALS_INDEX_URL, cache_dir / "mo" / "index.html")
    site_manuals = sorted(
        {
            m.group(1)
            for m in re.finditer(r'href="https://dssmanuals\.mo\.gov/([a-z0-9-]+)/"', home)
            if m.group(1) not in {"search", "comments", "feed", "memorandums", "nvr", "wp-json"}
        }
    )
    pages: list[str] = []
    for n, url in enumerate(MO_SITEMAP_URLS, start=1):
        pages.extend(re.findall(r"<loc>(https://dssmanuals\.mo\.gov/[^<]+)</loc>", fetch(session, url, cache_dir / "mo" / f"sitemap-page-{n}.xml")))
    docs = []
    families = []
    for slug, (code, manual_title, state_program, taken) in MO_MANUALS.items():
        landing = fetch(session, f"{MO_MANUALS_INDEX_URL}{slug}/", cache_dir / "mo" / f"{slug}.html", pause=0.3)
        labels = {
            href: strip_tags(text)
            for href, text in re.findall(rf'href="(https://dssmanuals\.mo\.gov/{slug}/[^"]+/)"[^>]*>(.*?)</a>', landing, re.S)
        }
        section_pages = sorted(p for p in pages if p.startswith(f"{MO_MANUALS_INDEX_URL}{slug}/") and p != f"{MO_MANUALS_INDEX_URL}{slug}/")
        if len(section_pages) < 5:
            raise SystemExit(f"only {len(section_pages)} {slug} pages in the sitemap; layout changed?")
        families.append({"family": f"{manual_title} section pages (dssmanuals.mo.gov sitemap)", "found": len(section_pages), "taken": len(section_pages) if taken else 0})
        if not taken:
            continue
        for url in section_pages:
            rel = url[len(f"{MO_MANUALS_INDEX_URL}{slug}/"):].strip("/")
            label = labels.get(url)
            title = f"Missouri {manual_title}: {label}" if label else f"Missouri {manual_title}: {rel.split('/')[-1]}"
            docs.append(
                {
                    "source_id": f"mo-dss-{code}-{rel.replace('/', '-')}",
                    "jurisdiction": "us-mo",
                    "document_class": "manual",
                    "title": title,
                    "source_url": url,
                    "source_format": "html",
                    "source_as_of": SOURCE_AS_OF_3,
                    "expression_date": SOURCE_AS_OF_3,
                    "citation_path": f"us-mo/manual/dss/{code}/{rel}",
                    "extraction": {"html_content_selector": ".entry-content"},
                    "metadata": {
                        "primary_source": True,
                        "source_authority": "Missouri Department of Social Services, Family Support Division",
                        "document_subtype": "eligibility_manual_section",
                        "manual": f"Missouri {manual_title}",
                        "manual_index_url": f"{MO_MANUALS_INDEX_URL}{slug}/",
                        "program": "ssi_state_supplement",
                        "state_program": state_program,
                        "federal_program": "SSI",
                        "state": "MO",
                        "index_url": MO_MANUALS_INDEX_URL,
                        "source_sitemap_urls": MO_SITEMAP_URLS,
                        "source_discovery_group": f"us-mo/manual/dss/{code}",
                        "discovered_via": f"{DISCOVERED_VIA_3} {MO_MANUALS_INDEX_URL}{slug}/",
                        "expression_date_note": "fetch date; each section prints its own IM memo date",
                    },
                }
            )
    families.append(
        {
            "family": "other DSS manuals on the site index (" + ", ".join(m for m in site_manuals if m not in MO_MANUALS) + ")",
            "found": len([m for m in site_manuals if m not in MO_MANUALS]),
            "taken": 0,
        }
    )
    if len({d["citation_path"] for d in docs}) != len(docs):
        raise SystemExit("duplicate MO citation paths")
    index_info = {
        "index_url": MO_MANUALS_INDEX_URL,
        "index_document_count": sum(f["found"] for f in families),
        "taken_count": len(docs),
        "families": families,
    }
    return docs, index_info


# ---------------------------------------------------------------- South Dakota (ARSD 67:12:14)

SD_ARTICLE_API_URL = "https://sdlegislature.gov/api/Rules/67:12"
SD_CHAPTER_API_URL = "https://sdlegislature.gov/api/Rules/67:12:14"
SD_LANDING_URL = "https://sdlegislature.gov/Rules/Administrative/67:12:14"


@builder3("SD")
def build_sd(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """South Dakota Optional State Supplemental Program: ARSD chapter 67:12:14 (Department of
    Social Services) from the Legislative Research Council's rules API, the same publisher,
    document shape (JSON ``Html`` field, labeled sections) and citation convention
    (us-sd/regulation/arsd/67/12/14/<section>) as the 2026-09-10 CHIP and TANF scopes."""
    article = json.loads(fetch(session, SD_ARTICLE_API_URL, cache_dir / "sd" / "67-12.json"))
    article_text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", article["Html"])))
    # the article's chapter list ends at the first "Rule 67:12:NN..." chapter heading; every catchline ends with "."
    toc_text = article_text.split(" Rule 67:12:", 1)[0]
    by_number: dict[str, str] = {}
    for number, catchline in re.findall(r"67:12:(\d\d)\s+([A-Z][^.]{3,120}?)\.", toc_text):
        by_number.setdefault(number, catchline.strip(" ."))  # the TOC entry comes first; chapter headings repeat later
    chapters = sorted(by_number.items())
    if len(chapters) < 15:
        raise SystemExit(f"only {len(chapters)} chapters parsed from the Article 67:12 index")
    if not any(n == "14" for n, _ in chapters):
        raise SystemExit(f"chapter 67:12:14 not listed in {SD_ARTICLE_API_URL}")
    chapter = json.loads(fetch(session, SD_CHAPTER_API_URL, cache_dir / "sd" / "67-12-14.json", pause=0.5))
    if chapter["RuleNumber"] != "67:12:14" or "OPTIONAL STATE SUPPLEMENTAL" not in chapter["Catchline"].upper():
        raise SystemExit(f"unexpected chapter payload: {chapter.get('RuleNumber')} {chapter.get('Catchline')}")
    chapter_text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", chapter["Html"])))
    sections = sorted(set(re.findall(r"67:12:14:(\d\d)\.", chapter_text)))
    effective = [long_date(d) for d in re.findall(r"effective ([A-Z][a-z]+ \d{1,2}, \d{4})", chapter_text)]
    if not sections or not effective:
        raise SystemExit("chapter 67:12:14 has no sections or no 'effective <date>' source notes")
    doc = {
        "source_id": "sd-lrc-arsd-67-12-14",
        "jurisdiction": "us-sd",
        "document_class": "regulation",
        "title": "ARSD Chapter 67:12:14 Optional State Supplemental Program",
        "source_url": SD_CHAPTER_API_URL,
        "source_format": "json",
        "source_as_of": SOURCE_AS_OF_3,
        "expression_date": max(effective),
        "citation_path": "us-sd/regulation/arsd/67/12/14",
        "extraction": {
            "json_html_field": "Html",
            "segmentation": "labeled_sections",
            "section_heading_pattern": r"^67:12:14:(?P<num>\d{2})\s*\.\s+(?P<heading>[^.]+\.)\s*(?P<body>.*)$",
            "section_label_template": "{num}",
        },
        "metadata": {
            "primary_source": True,
            "source_authority": "South Dakota Department of Social Services (ARSD Article 67:12), published by the South Dakota Legislative Research Council",
            "document_subtype": "administrative_rule_chapter",
            "legal_identifier": "ARSD 67:12:14",
            "program": "ssi_state_supplement",
            "state_program": "Optional State Supplemental Program",
            "federal_program": "SSI",
            "state": "SD",
            "landing_page": SD_LANDING_URL,
            "article_index": SD_ARTICLE_API_URL,
            "index_url": SD_ARTICLE_API_URL,
            "section_count": len(sections),
            "latest_source_effective_date": max(effective),
            "source_discovery_group": "us-sd/regulation/arsd/67/12",
            "discovered_via": f"{DISCOVERED_VIA_3} {SD_ARTICLE_API_URL}",
            "expression_date_note": "latest 'effective' date in the chapter's SDR source notes",
        },
    }
    repealed = [c for c in chapters if re.search(r"Repealed|Transferred", c[1])]
    index_info = {
        "index_url": SD_ARTICLE_API_URL,
        "index_document_count": len(chapters),
        "taken_count": 1,
        "families": [
            {"family": "ARSD Article 67:12 Assistance Payments chapters in force", "found": len(chapters) - len(repealed), "taken": 1},
            {"family": "ARSD Article 67:12 chapters repealed or transferred", "found": len(repealed), "taken": 0},
        ],
        "chapters": chapters,
    }
    return [doc], index_info


# ---------------------------------------------------------------- Oklahoma (OAC 340:15)

OK_LANDING_URL = "https://rules.ok.gov/home"
OK_TITLE_API_URL = "https://prod-ok-rules-api.tecuity.com/GetSegmentsByTitleNum?titleNum=340"
OK_CHAPTER_API_URL = "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=340&chapterNum=15"
OK_LEGACY_CHAPTER_URL = "https://oklahoma.gov/okdhs/library/policy/current/oac-340/chapter-15.html"


@builder3("OK")
def build_ok(session: requests.Session, cache_dir: Path) -> tuple[list[dict], dict]:
    """Oklahoma State Supplemental Payment (SSP): OAC Title 340 Chapter 15 (Department of Human
    Services) from the Secretary of State's Office of Administrative Rules, the rules.ok.gov
    publication's own segments API, the same source, extraction and citation convention
    (us-ok/regulation/oac/340/<chapter>) as the 2026-07-21 Oklahoma SNAP rules scope."""
    title_segments = json.loads(fetch(session, OK_TITLE_API_URL, cache_dir / "ok" / "title-340.json"))
    chapters = sorted(
        ((int(s["chapterNum"]), s["description"] or "", s["statusName"]) for s in title_segments if s["name"] == "Chapter"),
    )
    if not any(n == 15 for n, _, _ in chapters):
        raise SystemExit(f"chapter 15 not in the Title 340 segments at {OK_TITLE_API_URL}")
    segments = json.loads(fetch(session, OK_CHAPTER_API_URL, cache_dir / "ok" / "chapter-15.json", pause=0.5))
    sections = [s for s in segments if s["name"] == "Section"]
    subchapters = [s for s in segments if s["name"] == "Subchapter"]
    if not any("State Supplemental Payment" in (s["description"] or "") for s in subchapters):
        raise SystemExit("OAC 340:15 segments do not carry the State Supplemental Payment subchapter")
    doc = {
        "source_id": "ok-oac-340-15-state-supplemental-payment",
        "jurisdiction": "us-ok",
        "document_class": "regulation",
        "citation_path": "us-ok/regulation/oac/340/15",
        "title": "Oklahoma Administrative Code Title 340 Chapter 15 State Supplemental Payment; Children and Youth with Special Health Care Needs",
        "source_url": OK_LANDING_URL,
        "download_url": OK_CHAPTER_API_URL,
        "source_format": "json",
        "source_as_of": SOURCE_AS_OF_3,
        "expression_date": SOURCE_AS_OF_3,
        "extraction": {
            "segmentation": "records",
            "json_record_text_field": "text",
            "json_record_text_is_html": True,
            "json_record_label_field": "sectionNum",
            "json_record_heading_field": "description",
            "json_record_kind_field": "name",
            "json_record_status_field": "statusName",
            "json_record_exclude_statuses": ["Revoked", "Reserved"],
            "json_record_metadata_fields": [
                "id", "parentId", "name", "titleNum", "chapterNum", "subChapterNum", "partNum", "sectionNum", "appendixNum",
                "description", "statusName", "segmentStatusId", "segmentTypeId", "recordStatus", "effectiveDate", "filingId",
                "hasEmergency", "segmentNotes",
            ],
        },
        "metadata": {
            "primary_source": True,
            "source_authority": "Oklahoma Department of Human Services",
            "official_publisher": "Oklahoma Secretary of State Office of Administrative Rules",
            "document_subtype": "administrative_code_chapter",
            "program": "ssi_state_supplement",
            "state_program": "State Supplemental Payment (SSP)",
            "federal_program": "SSI",
            "state": "OK",
            "rules_landing_page": OK_LANDING_URL,
            "rules_api_url": OK_CHAPTER_API_URL,
            "legacy_okdhs_chapter_url": OK_LEGACY_CHAPTER_URL,
            "title_number": "340",
            "title_name": "Department of Human Services",
            "chapter_number": "15",
            "chapter_name": next((d for n, d, _ in chapters if n == 15), ""),
            "subchapters": "; ".join(f"{s['subChapterNum']} {s['description']}" for s in subchapters),
            "section_count": len(sections),
            "revoked_section_count": sum(1 for s in sections if s["statusName"] == "Revoked"),
            "index_url": OK_TITLE_API_URL,
            "source_discovery_group": "us-ok/regulation/oac/340",
            "discovered_via": f"{DISCOVERED_VIA_3} {OK_TITLE_API_URL}",
            "access_note": (
                "re-probed 2026-09-11 from a US network: oklahoma.gov OKDHS policy-library chapter page 301 -> rules.ok.gov/home; "
                "rules.ok.gov answers Cloudflare HTTP 403 to a plain client and HTTP 200 (JavaScript application shell) or 403 to a chrome120 "
                "TLS fingerprint; the publication's own segments API (prod-ok-rules-api.tecuity.com, the SNAP rules scope's download_url) "
                "answers HTTP 200 to a plain client; no proxy, mirror or third-party copy"
            ),
        },
    }
    current = [c for c in chapters if c[2] != "Revoked"]
    index_info = {
        "index_url": OK_TITLE_API_URL,
        "index_document_count": len(chapters),
        "taken_count": 1,
        "families": [
            {"family": "OAC Title 340 (Department of Human Services) chapters, current", "found": len(current), "taken": 1},
            {"family": "OAC Title 340 chapters, revoked", "found": len(chapters) - len(current), "taken": 0},
        ],
        "chapters": chapters,
        "sections": [(s["sectionNum"], s["description"], s["statusName"]) for s in sections],
    }
    return [doc], index_info


SOURCE_KINDS_3 = {
    "AK": "official_state_agency_manual",
    "WI": "official_state_agency_manual",
    "MO": "official_state_agency_manual",
    "SD": "official_state_regulation",
    "OK": "official_state_regulation",
}
ROW_NOTES_3 = {
    "AK": (
        "Adult Public Assistance (APA), Alaska's SSI supplement: the Division of Public Assistance's Adult Public Assistance "
        "Manual, every topic page from the RoboHelp table of contents at dpaweb.hss.state.ak.us/manuals/apa/ (sections 400 "
        "General Information to 482 Claims, addendum, transmittals and manual-change memos) plus a snapshot of each TOC file, "
        "the 2026-07-16 SNAP manual scope's structure. document_class manual, citation us-ak/manual/dpa/apa/<topic> and "
        "us-ak/manual/dpa/apa/navigation/toc-<key>. dpaweb.hss.state.ak.us HTTP 200 to a plain client over http (the https "
        "port does not answer). The corpus's us-ak/guidance APA standards PDF (2026-06-30) is the payment-standard table; the "
        "manual is the governing text."
    ),
    "WI": (
        "State SSI Supplement (Wis. Stat. 49.77, administered by DHS): the SSI Administration Handbook (P-23129) and the "
        "SSI Exceptional Expense (SSI-E) Handbook (P-20679), every topic page from each RoboHelp TOC on "
        "emhandbooks.wisconsin.gov (the DHS handbook host), both listed on the DHS SSI program's Forms and Publications page. "
        "document_class manual, citation us-wi/manual/dhs/ssi/ssi-admin/<topic> and us-wi/manual/dhs/ssi/ssi-e/<topic>; "
        "expression_date the handbooks' printed Release 26-01 date (2026-05-01). The SSI Caretaker Supplement handbook "
        "(P-23131; TANF-funded benefit to SSI parents, Wis. Stat. 49.775), the DHS SSI program web pages, forms and fact sheets "
        "are separate families, not taken. Wisconsin has no administrative-rule chapter for the state SSI payment (the batch-2 "
        "lead 'DHS 2 Wis. Adm. Code' is Recoupment of Benefit Overpayments)."
    ),
    "MO": (
        "Supplemental Nursing Care (SNC) and Supplemental Aid to the Blind (SAB), Missouri's state-administered supplements: "
        "the Family Support Division's SNC Manual (0600-0635) and SAB Manual (0400-0440), every section page from the "
        "dssmanuals.mo.gov WordPress sitemap (the 2026-09-10 MHABD Medicaid scope's method). document_class manual, citation "
        "us-mo/manual/dss/snc/<section> and us-mo/manual/dss/sab/<section>, .entry-content selector. The Blind Pension Manual "
        "(state-only pension for blind persons not eligible for SAB; 0505.000.00 password-protected) is a separate family, not "
        "taken. The MHABD scope mentions SNC on 22 rows but carries no SNC or SAB eligibility text. 13 CSR 40-2 (Secretary of "
        "State) has no SNC/SAB-specific rule; the manuals are the governing text."
    ),
    "SD": (
        "Optional State Supplemental Program: ARSD chapter 67:12:14 (Department of Social Services; 11 sections, sources 5 SDR 6 "
        "1978 to 20 SDR 92 effective 1993-12-31) from the Legislative Research Council's rules API (sdlegislature.gov/api/Rules), "
        "the publisher and JSON/labeled-section convention of the 2026-09-10 CHIP (67:46) and TANF (67:10) scopes. The Article "
        "67:12 Assistance Payments index lists 21 chapters (11 repealed or transferred); 67:12:14 taken. document_class "
        "regulation, citation us-sd/regulation/arsd/67/12/14/<section>. sdlegislature.gov HTTP 200 to a plain client (the "
        "HTML site is a JavaScript application; the API is its data source)."
    ),
    "OK": (
        "State Supplemental Payment (SSP): OAC Title 340 Chapter 15 (Department of Human Services; Subchapter 1 State "
        "Supplemental Payment, 7 sections of which 2 revoked, and Subchapter 3 Children and Youth with Special Health Care Needs) "
        "from the Secretary of State's Office of Administrative Rules (rules.ok.gov) segments API, the 2026-07-21 SNAP rules "
        "scope's source and convention (records segmentation; revoked sections excluded). Title 340 lists 30 chapters (17 "
        "current, 13 revoked); chapter 15 taken. document_class regulation, citation us-ok/regulation/oac/340/15/<section>. "
        "Re-probe 2026-09-11 (batch 3, US network): oklahoma.gov/okdhs policy library now 301 -> rules.ok.gov/home; "
        "rules.ok.gov/home Cloudflare HTTP 403 (5,316 bytes) plain, HTTP 200 (1,551-byte application shell) then 403 (5,906 "
        "bytes) to chrome120 impersonation; the publication's own API (prod-ok-rules-api.tecuity.com) HTTP 200 plain. Batch 2 "
        "(2026-09-10): both hosts 403."
    ),
}

# The six states with no optional state supplement (POMS SI 01415.010, column Optional = N):
# done with that finding and the POMS pointer; (mandatory-column value, note).
NO_SUPPLEMENT_ROWS = {
    "AR": ("Arkansas", "F", "federally administered mandatory supplement only"),
    "AZ": ("Arizona", "S", "state-administered mandatory supplement only"),
    "MS": ("Mississippi", "F", "federally administered mandatory supplement only"),
    "ND": ("North Dakota", "NR", "no mandatory supplement (NR)"),
    "TN": ("Tennessee", "F", "federally administered mandatory supplement only"),
    "WV": ("West Virginia", "N", "no mandatory supplement"),
}

BLOCKED_ROWS_3 = {
    "WY": (
        "https://ecom.wyo.gov/m1800-other-programs/m1804-state-supplemental-payments",
        "Wyoming's State Supplemental Payments are administered by the Department of Health (Division of Healthcare Financing); "
        "the agency's governing text is Eligibility Operations Manual (EOM) section M1804 State Supplemental Payments on "
        "ecom.wyo.gov (Google Sites; the EOM navigation lists 107 sections, M1804 the one SSP section). The page answers HTTP 200 "
        "(248,711 bytes) to a plain client, but its content is a Google Drive viewer embed rendered by script "
        "(embeds.googleusercontent.com inner frame); the HTML carries only the title and navigation and no document URL or file "
        "id, so the document is not addressable from the publisher's page. DFS (dfs.wyo.gov) lists no SSI supplement family "
        "(Cash Assistance = POWER; policy manuals: APS, Child Support, SNAP/POWER, Foster Care). rules.wyo.gov (Secretary of "
        "State, ASP.NET search application) was not searched for a Department of Health SSP rule chapter. No index document taken. "
        "The SSA regional description is in the federal family: us/manual/ssa/poms/si/01415.010 (Wyoming row S/S).",
    ),
}


def update_queue_batch3(results: dict[str, dict]) -> dict:
    """Rewrite only the batch-3 rows (MO, WI, SD, AK, WY, OK) and add the six no-supplement rows."""
    queue = yaml.safe_load(QUEUE.read_text())
    rows = {row["jurisdiction"]: row for row in queue["states"]}
    federal_scope = rows["us"]["target_scope"]
    for code, index in results.items():
        row = rows[f"us-{code.lower()}"]
        docs = index["docs"]
        families = "; ".join(f"{f['family']}: {f['found']} found / {f['taken']} taken" for f in index["families"])
        row.update(
            {
                "queue_status": "agent_ready",
                "source_kind": index["source_kind"],
                "primary_source_url": docs[0]["source_url"],
                "target_manifest": str(manifest_path(code).relative_to(ROOT)),
                "target_scope": {"jurisdiction": f"us-{code.lower()}", "document_class": docs[0]["document_class"], "version": VERSION},
                "index_url": index["index_url"],
                "index_document_count": index["index_document_count"],
                "taken_count": index["taken_count"],
                "index_families": families,
                "notes": index["note"],
            }
        )
    for code, (name, mandatory, mandatory_note) in NO_SUPPLEMENT_ROWS.items():
        jurisdiction = f"us-{code.lower()}"
        row = rows.get(jurisdiction)
        if row is None:
            row = {"jurisdiction": jurisdiction, "name": name, "lead_counts": {}, "candidate_sources": []}
            queue["states"].append(row)
            rows[jurisdiction] = row
        row.update(
            {
                "queue_status": "done",
                "source_kind": "ssa_poms_section",
                "primary_source_url": POMS_SI_01415_010_URL,
                "target_manifest": "manifests/us-ssa-poms-si-2026-09-10.yaml",
                "target_scope": federal_scope,
                "index_url": POMS_SI_01415_INDEX_URL,
                "index_document_count": 1,
                "taken_count": 1,
                "index_families": "POMS SI 01415.010 Administration of State Supplementary Programs (state table): 1 found / 1 taken in the federal family; no state document family exists",
                "administration": "N",
                "notes": (
                    f"No optional state supplement (POMS SI 01415.010 state table, {name} row: Mandatory = {mandatory}, "
                    f"Optional = N; {mandatory_note}). Done with that finding: the governing text is the federal POMS row, "
                    "already in the corpus as us/manual/ssa/poms/si/01415.010 (version 2026-09-10-ssi-poms-si); no state "
                    "agency document exists to inventory and nothing was fetched. (2026-09-11 state-supplement batch 3.)"
                ),
            }
        )
    for code, (url, note) in BLOCKED_ROWS_3.items():
        rows[f"us-{code.lower()}"].update(
            {
                "queue_status": "blocked_primary_source",
                "source_kind": "state_agency_document",
                "primary_source_url": url,
                "target_manifest": None,
                "index_url": "https://ecom.wyo.gov/",
                "index_document_count": 107,
                "taken_count": 0,
                "index_families": "Department of Health EOM sections (Google Sites navigation): 107 found / 0 taken (M1804 content is a script-rendered Drive embed; see notes); DFS index: no SSI supplement family",
                "notes": f"Blocked 2026-09-11 (state-supplement batch 3): {note}",
            }
        )
    queue["states"].sort(key=lambda row: (row["jurisdiction"] != "us", row["jurisdiction"]))
    queue["status_counts"] = {}
    for row in queue["states"]:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    note = (
        "2026-09-11 SSI state-supplement batch 3: scripts/build_ssi_state_supplement_manifests.py --batch 3; the six states with "
        "no optional supplement (AR, AZ, MS, ND, TN, WV) added as done rows pointing at POMS SI 01415.010; MO, WI, SD, AK "
        "extracted; WY blocked (script-rendered Drive embed); OK re-probed and extracted from the rules.ok.gov segments API; "
        "docs/ingest-runs/2026-09-10-ssi-state-supplements-batch-3.md."
    )
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def index_markdown(code: str, index: dict) -> str:
    lines = [f"**us-{code.lower()}** — {index['index_url']}", "", "| Family | Found | Taken |", "| --- | ---: | ---: |"]
    for fam in index["families"]:
        lines.append(f"| {fam['family']} | {fam['found']} | {fam['taken']} |")
    lines.append(f"| **Total on index** | {index['index_document_count']} | {index['taken_count']} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".axiom" / "ssi-state-supplement-cache")
    parser.add_argument("--only", help="comma-separated state codes to build (default: all extractable states)")
    parser.add_argument("--print-index", action="store_true", help="print each publisher index inventory as markdown")
    parser.add_argument("--skip-queue", action="store_true", help="do not rewrite manifests/ssi-agent-queue.yaml")
    parser.add_argument("--batch", type=int, choices=(1, 2, 3), default=3,
                        help="which batch's builders and queue rows to run (default 3; earlier batches' states are never regenerated by default)")
    args = parser.parse_args()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    builders = {1: BUILDERS, 2: BUILDERS_2, 3: BUILDERS_3}[args.batch]
    source_kinds = {1: SOURCE_KINDS, 2: SOURCE_KINDS_2, 3: SOURCE_KINDS_3}[args.batch]
    row_notes = {1: ROW_NOTES, 2: ROW_NOTES_2, 3: ROW_NOTES_3}[args.batch]
    codes = [c.strip().upper() for c in args.only.split(",")] if args.only else list(builders)
    results: dict[str, dict] = {}
    for code in codes:
        build = globals()[builders[code]]
        docs, index = build(session, args.cache_dir)
        paths = [d["citation_path"] for d in docs]
        if len(set(paths)) != len(paths):
            raise SystemExit(f"duplicate citation paths in {code} manifest")
        manifest_path(code).write_text(
            yaml.safe_dump({"version": VERSION, "documents": docs}, sort_keys=False, allow_unicode=True, width=120)
        )
        index.update({"docs": docs, "source_kind": source_kinds[code], "note": row_notes[code]})
        results[code] = index
        if args.print_index:
            print(index_markdown(code, index), "\n")
        print(
            json.dumps(
                {
                    "state": code,
                    "manifest": str(manifest_path(code).relative_to(ROOT)),
                    "index_document_count": index["index_document_count"],
                    "taken_count": index["taken_count"],
                    "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                }
            )
        )
    if not args.skip_queue:
        update = {1: update_queue, 2: update_queue_batch2, 3: update_queue_batch3}[args.batch]
        print("queue status_counts:", update(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
