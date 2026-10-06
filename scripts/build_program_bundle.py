#!/usr/bin/env python3
"""Build the program bundles from their config: for each core program, the
documents that make up each delivery tier, for the federal layer once and for
each state and DC, and the part of the program each one feeds.

Every choice lives in the config (manifests/program-bundles/programs.config.yaml):
the inputs and their versions, the exclusions and their reasons, how
PolicyEngine folders, plan documents and corpus manifests map to programs and
states, and how documents map to parts. This script holds only the mechanics.

Two tiers, each built per layer (the federal layer, shared by every state, and
one layer per state):

- ``screener``: screener-level parity. The PolicyEngine-US references of one
  release (scripts/export_policyengine_references.py: every file that cites a
  URL, in the program's federal folders and each state's), and the plan's
  documents. A reference lands in the layer of the law it names: a US Code or
  CFR citation and a federal publisher's page in the federal layer, a state's
  own source in that state's. They group into documents: a code or CFR
  section, a manual page, or the registered document that holds the citation.
- ``full``: the full document bundle. Every in-scope screener document of the
  layer; in the federal layer, the program's federal law section by section
  (from its needs-closure schema) and its federal guidance manifests; in a
  state's layer, the state's own sources from its manifests for the program,
  and the sources the config knows the corpus does not hold yet.

A state's bundle is its layer and the federal layer together, so the federal
law is listed once. The bundles record membership, exclusions and parts only.
Progress is telemetry the axiom.org collector reads from the served corpus,
the RuleSpec modules and the encode runs.

Usage::

    python scripts/build_program_bundle.py manifests/program-bundles/programs.config.yaml

Writes manifests/program-bundles/<program>.yaml for every program.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import yaml

try:
    from scripts.export_policyengine_references import citation_from_url
except ImportError:  # run as a script from scripts/
    from export_policyengine_references import citation_from_url

REPO = Path(__file__).resolve().parent.parent

US_STATES = [
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "newhampshire",
    "newjersey",
    "newmexico",
    "newyork",
    "northcarolina",
    "northdakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhodeisland",
    "southcarolina",
    "southdakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "westvirginia",
    "wisconsin",
    "wyoming",
]
STATE_CODES = [
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
] + ["dc", "pr", "vi", "gu", "as", "mp"]
# Names a reference title can use for a state or territory.
STATE_NAMES = {
    **dict(
        zip(
            [
                "Alabama",
                "Alaska",
                "Arizona",
                "Arkansas",
                "California",
                "Colorado",
                "Connecticut",
                "Delaware",
                "Florida",
                "Georgia",
                "Hawaii",
                "Idaho",
                "Illinois",
                "Indiana",
                "Iowa",
                "Kansas",
                "Kentucky",
                "Louisiana",
                "Maine",
                "Maryland",
                "Massachusetts",
                "Michigan",
                "Minnesota",
                "Mississippi",
                "Missouri",
                "Montana",
                "Nebraska",
                "Nevada",
                "New Hampshire",
                "New Jersey",
                "New Mexico",
                "New York",
                "North Carolina",
                "North Dakota",
                "Ohio",
                "Oklahoma",
                "Oregon",
                "Pennsylvania",
                "Rhode Island",
                "South Carolina",
                "South Dakota",
                "Tennessee",
                "Texas",
                "Utah",
                "Vermont",
                "Virginia",
                "Washington",
                "West Virginia",
                "Wisconsin",
                "Wyoming",
            ],
            STATE_CODES,
            strict=False,
        )
    ),
    "District of Columbia": "dc",
    "Puerto Rico": "pr",
    "Virgin Islands": "vi",
    "Guam": "gu",
}
# A federal fiscal year a URL or title names ("fy-2024-cola", "FY25-Quarter-2",
# "cola/fy26", "COLAMemoFY23", "abawd-response-fy2025"). A year in a URL's
# folder is a publication date, not the year a rule applies to, so it says
# nothing; poverty guidelines are by calendar year.
FISCAL_YEAR = re.compile(r"(?i)fy[-_ %]?(?:20)?(\d{2})(?!\d)|cola(20\d{2})(?!\d)")
ARCHIVED = re.compile(r"^https?://web\.archive\.org/web/[^/]+/(.+)$")
# Enacting texts: public laws and bills on congress.gov or govinfo, and
# Federal Register notices.
ENACTING = re.compile(
    r"(?i)congress\.gov/(?:\d+/(?:plaws|bills)/|bill/)|govinfo\.gov/.*(?:PLAW-|/FR-\d{4}|pkg/FR-)"
)
# Plan ids that name a US Code or CFR section: "USC 7 2014", "CFR 7 273.1".
PLAN_USC = re.compile(r"^USC (\d+) (\S+)$")
PLAN_CFR = re.compile(r"^CFR (\d+) (\d+)\.(\S+)$")


def url_state(
    url: str, state_hosts: dict[str, str], state_patterns: list[str] | None = None
) -> str | None:
    """The two-letter state a URL belongs to: by its host, a Cornell state
    path, or a pattern for federal documents about one state."""
    url = unarchive(url)
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    for suffix, code in state_hosts.items():
        if host == suffix or host.endswith("." + suffix):
            return code
    for pattern in state_patterns or []:
        if (m := re.search(pattern, url, re.I)) and m.group("state").lower() in STATE_CODES:
            return m.group("state").lower()
    m = re.search(r"(?:^|\.)([a-z]{2})\.gov$|\.state\.([a-z]{2})\.us$", host)
    if m and (m.group(1) or m.group(2)) in STATE_CODES:
        return m.group(1) or m.group(2)
    text = (host + parts.path.lower()).replace("-", "").replace("_", "")
    for name, code in zip(US_STATES, STATE_CODES, strict=False):
        if f".{name}.gov" in "." + text or f"/regulations/{name}/" in text:
            return code
    return None


def unarchive(url: str) -> str:
    """The page a Wayback Machine link archives."""
    m = ARCHIVED.match(url.strip())
    if not m:
        return url
    inner = m.group(1)
    return inner if re.match(r"https?://", inner) else "http://" + inner


def normalize_url(url: str) -> str:
    """The page a link names: an archived page, and a WebWorks manual link
    (index.html#page/<chapter>/<page>.html) names its page in the fragment."""
    url = unarchive(url)
    m = re.match(r"(https?://[^/]+)/index\.html#page/(.+)$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else url.split("#")[0]


def title_state(titles: list[str]) -> str | None:
    """The one state or territory reference titles name, if exactly one."""
    named = {
        code
        for title in titles
        for name, code in STATE_NAMES.items()
        if re.search(rf"\b{name}\b", title)
    }
    return named.pop() if len(named) == 1 else None


def url_key(url: str, aliases: dict[str, str] | None = None) -> tuple[str, str]:
    """A URL's host and path, with alias hosts read as the host they serve for."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    return (aliases or {}).get(host, host), parts.path.rstrip("/").lower()


def fiscal_year(day: dt.date) -> int:
    """The federal fiscal year of a day: FY2027 runs from 1 October 2026."""
    return day.year + (1 if day.month >= 10 else 0)


def back_year(text: str, day: dt.date) -> bool:
    """A URL or title names a fiscal year before the day's, or poverty
    guidelines of an earlier calendar year."""
    for m in FISCAL_YEAR.finditer(text):
        y = m.group(1) or m.group(2)
        if (int(y) if len(y) == 4 else 2000 + int(y)) < fiscal_year(day):
            return True
    if re.search(r"(?i)poverty[-_ ]guidelines", text):
        years = [int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", text)]
        return bool(years) and max(years) < day.year
    return False


def document_key(citation: str, registered: list[str]) -> str:
    """The document that holds a cited provision."""
    seg = citation.split("/")
    if len(seg) >= 4 and seg[1] == "statute":
        return "/".join(seg[:4])
    if len(seg) >= 5 and seg[1] == "regulation" and seg[0] == "us":
        return "/".join(seg[:5])
    if len(seg) >= 5 and seg[1] == "manual" and seg[2] == "des":
        return "/".join(seg[:5])
    # Elsewhere the registered document is the unit: the longest manifest
    # citation path that holds the citation.
    holders = [r for r in registered if citation == r or citation.startswith(r + "/")]
    return max(holders, key=len) if holders else citation


def document_name(key: str, titles: dict[str, str]) -> str:
    seg = key.split("/")
    if key.startswith("us/statute/") and len(seg) >= 4:
        return f"{seg[2]} USC {seg[3]}"
    if key.startswith("us/regulation/") and len(seg) >= 5:
        return f"{seg[2]} CFR {seg[3]}.{seg[4]}"
    if key in titles:
        return titles[key]
    if key.startswith("http"):
        parts = urlsplit(key)
        return (parts.netloc.removeprefix("www.") + parts.path)[:90]
    return key


def part_of(votes: Counter) -> str:
    """The most voted part; "Other" only when nothing else has a vote."""
    named = [(n, p) for p, n in votes.items() if p != "Other"]
    return max(named)[1] if named else "Other"


def _in_range(rule: dict, manifest: str, toc: int | None) -> bool:
    if rule.get("manifest") != manifest:
        return False
    if "toc" not in rule:
        return True
    return toc is not None and rule["toc"][0] <= toc <= rule["toc"][1]


def _part_matches(rule: dict, manifest: str, toc: int | None, entry: dict) -> bool:
    if "key" in rule:
        return rule["key"] in (entry["citation_path"], entry["source_url"], entry["key"])
    return _in_range(rule, manifest, toc)


def as_of(cfg: dict) -> dt.date:
    value = cfg["as_of"]
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def _rules(rules: list | None) -> list[dict]:
    """A part rule list, with nested lists (YAML aliases of shared rule sets) flattened."""
    out: list[dict] = []
    for rule in rules or []:
        out.extend(_rules(rule) if isinstance(rule, list) else [rule])
    return out


def rule_part(rules: list[dict], *texts: str | None) -> str | None:
    """The part of the first rule any of the texts matches."""
    for rule in rules:
        if any(t and re.search(rule["pattern"], t) for t in texts):
            return rule["part"]
    return None


USC_TEXT = re.compile(r"(\d+)\s*U\.?\s*S\.?\s*C\.?\s*(?:§+\s*)?(\d+[a-z]*)", re.I)
CFR_SECTION_TEXT = re.compile(r"(\d+)\s*C\.?\s*F\.?\s*R\.?\s*(?:§+\s*)?(\d+)\.(\d+[a-z]?)", re.I)
CFR_PART_TEXT = re.compile(r"(\d+)\s*C\.?\s*F\.?\s*R\.?\s*(?:part\s*)?(\d+)(?![.\d])", re.I)


def schema_sections(schema: dict) -> list[tuple[str, str, str]]:
    """(citation path, label, element id) for each federal element of a
    needs-closure schema, whatever its shape: a corpus path, a citation in its
    text (42 U.S.C. 601, 45 CFR 98.20, 42 CFR 431), or tax code sections."""
    elements = list(schema.get("elements") or [])
    for key in (
        "federal_statute_elements",
        "federal_regulation_elements",
        "federal_guidance_elements",
    ):
        elements += [dict(e, level=e.get("level") or "federal") for e in schema.get(key) or []]
    out: list[tuple[str, str, str]] = []
    for e in elements:
        if not str(e.get("level", "")).startswith("federal"):
            continue
        label = str(e.get("label") or e.get("title") or e.get("name") or "")
        paths: list[str] = []
        if str(e.get("citation_path") or "").startswith("us/"):
            paths.append(e["citation_path"])
        else:
            text = " ".join(
                str(e.get(k) or "") for k in ("citation", "federal_citation", "authority")
            )
            paths += [f"us/statute/{t}/{s}" for t, s in USC_TEXT.findall(text)]
            paths += [f"us/regulation/{t}/{p}/{s}" for t, p, s in CFR_SECTION_TEXT.findall(text)]
            if not paths:
                paths += [f"us/regulation/{t}/{p}" for t, p in CFR_PART_TEXT.findall(text)]
            paths += [f"us/statute/26/{s}" for s in e.get("sections") or []]
        for path in dict.fromkeys(paths):
            out.append((path, label, str(e.get("id", ""))))
    return out


class Layer:
    """One jurisdiction's documents of one program, per tier."""

    def __init__(self, jurisdiction: str):
        self.jurisdiction = jurisdiction
        self.docs: dict[str, dict] = {}
        self.cited: dict[str, dict[str, int]] = defaultdict(dict)
        self.parts: dict[str, Counter] = defaultdict(Counter)
        self.cited_parts: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
        self.full: dict[str, dict] = {}


def load_manifests() -> dict[str, list[dict]]:
    """Every manifest's documents, by manifest path."""
    out: dict[str, list[dict]] = {}
    for f in sorted((REPO / "manifests").glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(errors="ignore"))
        except yaml.YAMLError:
            continue
        docs = data.get("documents") if isinstance(data, dict) else None
        if isinstance(docs, list):
            out[f"manifests/{f.name}"] = [d for d in docs if isinstance(d, dict)]
    return out


def index_manifests(
    manifests: dict[str, list[dict]], aliases: dict[str, str]
) -> tuple[list[str], dict[tuple[str, str], str], dict[str, str]]:
    """Every registered citation path, the citation path of each source and
    download URL (a document's own path over a recovery scope's), and titles."""
    paths, by_url, titles = set(), {}, {}
    for docs in manifests.values():
        for doc in docs:
            cp = doc.get("citation_path")
            if not cp:
                continue
            paths.add(cp)
            if doc.get("title"):
                titles.setdefault(cp, doc["title"])
            for field in ("source_url", "download_url"):
                if doc.get(field):
                    k = url_key(normalize_url(doc[field]), aliases)
                    if k not in by_url or ("/recovery/" in by_url[k] and "/recovery/" not in cp):
                        by_url[k] = cp
    return sorted(paths), by_url, titles


def build_program(
    cfg: dict,
    pid: str,
    references: dict,
    plan: dict | None,
    manifests: dict[str, list[dict]],
    index: tuple[list[str], dict[tuple[str, str], str], dict[str, str]],
) -> dict:
    prog = cfg["programs"][pid]
    registered, by_url, titles = index
    aliases = cfg.get("host_aliases") or {}
    state_hosts = cfg.get("state_hosts") or {}
    state_patterns = cfg.get("state_url_patterns") or []
    federal_hosts = re.compile(cfg["federal_hosts"])
    jurisdictions = [f"us-{st}" for st in cfg["jurisdictions"]]
    day = as_of(cfg)
    reasons = cfg["exclusions"]
    secondary = re.compile(cfg["secondary_hosts"])
    data_series = re.compile(cfg["data_series_hosts"])
    expired = [(re.compile(e["pattern"]), e["reason"]) for e in prog.get("expired") or []]
    same = {
        url_key(normalize_url(a), aliases): b for a, b in (cfg.get("same_document") or {}).items()
    }
    rules = _rules(prog.get("part_rules"))
    overrides = prog.get("states") or {}
    layers = {j: Layer(j) for j in ["us", *jurisdictions]}
    dropped = Counter()

    def jurisdiction_of(citation, url, states, ref_titles) -> str:
        """The layer of the law a reference names."""
        if citation:
            return citation.split("/")[0]
        code = url_state(url, state_hosts, state_patterns) if url else None
        if code:
            return f"us-{code}"
        host = (urlsplit(unarchive(url or "")).hostname or "").removeprefix("www.")
        if federal_hosts.search(host):
            return "us"
        if len(states) == 1:
            return f"us-{states[0]}"
        code = title_state(ref_titles or [])
        if code:
            return f"us-{code}"
        return f"us-{states[0]}" if states else "us"

    def add(layer: Layer, source, url, citation, reason, part, name=None, ref_titles=None):
        text = " ".join([url or "", *(ref_titles or [])])
        if url and not citation and reason is None and secondary.search(url):
            reason = reasons["secondary"]
        elif url and reason is None and data_series.search(url):
            reason = reasons["data_series"]
        elif url and reason is None and back_year(text, day):
            reason = reasons["back_year"]
        key = document_key(citation, registered) if citation else normalize_url(url or "")
        doc = layer.docs.setdefault(
            key,
            {
                "key": key,
                "name": name or document_name(key, titles),
                "layer": "federal" if layer.jurisdiction == "us" else "state",
                "citation_path": key if citation else None,
                "source_url": None if citation else key,
                "sources": [],
                "references": 0,
                "scope": "excluded",
                "reason": reason,
            },
        )
        if source not in doc["sources"]:
            doc["sources"].append(source)
        if source == "policyengine-references":
            doc["references"] += 1
        layer.parts[key][part] += 1
        # PolicyEngine's citations are the tier's units, a whole section
        # included; the plan names sections, which add a unit only below one.
        unit = citation and (citation != key or source == "policyengine-references")
        if unit:
            layer.cited_parts[key][citation][part] += 1
        if reason is None:
            # A URL is one document with one classification: a source that
            # finds a reason to exclude it outweighs one that does not look.
            if doc["citation_path"] or not doc["reason"]:
                doc["scope"], doc["reason"] = "in", None
            if unit:
                layer.cited[key][citation] = layer.cited[key].get(citation, 0) + 1
        elif not doc["citation_path"]:
            doc["scope"], doc["reason"] = "excluded", doc["reason"] or reason
        elif doc["scope"] == "excluded" and not doc["reason"]:
            doc["reason"] = reason

    # Files that cite a US Code or CFR section: an enacting text they also
    # cite is codified there.
    codifying = {
        f
        for ref in references["references"]
        if (ref.get("citation") or "").startswith(("us/statute/", "us/regulation/"))
        for f in ref.get("files") or []
    }

    # 1. PolicyEngine's references.
    for ref in references["references"]:
        files = ref.get("files") or []
        url = ref["url"]
        if url_key(normalize_url(url), aliases) in same:
            url = same[url_key(normalize_url(url), aliases)]
        citation = ref.get("citation") or by_url.get(url_key(normalize_url(url), aliases))
        reason = next(
            (why for rx, why in expired if any(rx.search(t) for t in [url, *files])), None
        )
        if reason is None and ENACTING.search(url) and any(f in codifying for f in files):
            reason = reasons["enacting"]
        jur = jurisdiction_of(citation, url, ref.get("states") or [], ref.get("titles"))
        if jur not in layers:
            dropped[jur] += 1
            continue
        votes = Counter(p for f in files if (p := rule_part(rules, f)))
        part = (
            votes.most_common(1)[0][0]
            if votes
            else rule_part(rules, citation, url, *(ref.get("titles") or [])) or "Other"
        )
        add(
            layers[jur],
            "policyengine-references",
            url,
            citation,
            reason,
            part,
            ref_titles=ref.get("titles"),
        )

    # 2. The plan's documents for the program.
    plan_docs = [
        d
        for d in (plan or {}).get("documents", [])
        if set(d.get("programs") or []) & set(prog.get("plan_programs") or [])
    ]
    for doc in plan_docs:
        jur = "us" if doc["jurisdiction"] == "US" else doc["jurisdiction"].lower()
        if jur not in layers:
            dropped[jur] += 1
            continue
        crosswalk = (overrides.get(jur.removeprefix("us-")) or {}).get("crosswalk") or {}
        usc, cfr = PLAN_USC.match(doc["id"]), PLAN_CFR.match(doc["id"])
        citation = (
            crosswalk.get(doc["id"])
            or next(iter(doc.get("citation_paths") or []), None)
            or (f"us/statute/{usc.group(1)}/{usc.group(2)}" if usc else None)
            or (f"us/regulation/{cfr.group(1)}/{cfr.group(2)}/{cfr.group(3)}" if cfr else None)
        )
        urls = doc.get("urls") or []
        url = urls[0] if urls else None
        if url and url_key(normalize_url(url), aliases) in same:
            url = same[url_key(normalize_url(url), aliases)]
        joined = by_url.get(url_key(normalize_url(url), aliases)) if url else None
        structured = citation_from_url(url) if url else None
        # A plan row that names a recovery scope's path: the document's own path.
        if citation and "/recovery/" in citation and joined and "/recovery/" not in joined:
            citation = joined
        citation = citation or joined or (structured[1] if structured else None)
        part = rule_part(rules, citation, url, doc.get("title")) or "Other"
        add(
            layers[jur],
            "plan",
            url,
            citation,
            None,
            part,
            name=None if citation else doc.get("title") or doc["id"],
        )

    # The screener tier of each layer.
    screener: dict[str, list[dict]] = {}
    for jur, layer in layers.items():
        out = []
        for key, doc in sorted(layer.docs.items(), key=lambda kv: (kv[1]["scope"] != "in", kv[0])):
            doc["part"] = part_of(layer.parts[key])
            if layer.cited.get(key):
                doc["cited"] = [
                    {"path": p, "references": n, "part": part_of(layer.cited_parts[key][p])}
                    for p, n in sorted(layer.cited[key].items())
                ]
            if not doc["references"]:
                doc.pop("references")
            if doc["scope"] == "in":
                doc.pop("reason")
            out.append(doc)
        screener[jur] = out

    # The full bundle of each layer.
    all_state_patterns = [
        re.compile(p["state_manifests"])
        for p in cfg["programs"].values()
        if p.get("state_manifests")
    ]
    own_manifests = re.compile(prog["state_manifests"]) if prog.get("state_manifests") else None
    own_documents = re.compile(prog["state_documents"]) if prog.get("state_documents") else None
    federal_manifests = (
        re.compile(prog["federal_manifests"]) if prog.get("federal_manifests") else None
    )
    full: dict[str, list[dict]] = {}
    for jur in layers:
        st = jur.removeprefix("us-")
        state_cfg = overrides.get(st) or {}
        out: list[dict] = []
        by_key: dict[str, dict] = {}
        seen: dict[tuple[str, str], dict] = {}

        def place(entry: dict, out: list[dict] = out, by_key: dict[str, dict] = by_key) -> None:
            held = by_key.get(entry["key"])
            if held is not None:
                for source in entry["sources"]:
                    if source not in held["sources"]:
                        held["sources"].append(source)
                if held["scope"] == "excluded" and entry["scope"] == "in":
                    held["scope"] = "in"
                    held.pop("reason", None)
                return
            by_key[entry["key"]] = entry
            out.append(entry)

        for doc in screener[jur]:
            if doc["scope"] == "in":
                place(
                    {
                        k: doc[k]
                        for k in ("key", "name", "layer", "citation_path", "source_url", "part")
                    }
                    | {"sources": ["screener"], "scope": "in"}
                )

        if jur == "us" and prog.get("schema"):
            schema = yaml.safe_load((REPO / prog["schema"]).read_text())
            excludes = [
                (re.compile(e["pattern"]), e["reason"]) for e in prog.get("federal_exclude") or []
            ]
            only = re.compile(prog["schema_filter"]) if prog.get("schema_filter") else None
            for path, label, element in schema_sections(schema):
                if only and not only.search(path):
                    continue
                key = document_key(path, [])
                reason = next((why for rx, why in excludes if rx.search(key)), None)
                if reason is None and back_year(f"{key} {label}", day):
                    reason = reasons["back_year"]
                entry = {
                    "key": key,
                    "name": document_name(key, {}),
                    "layer": "federal",
                    "citation_path": key,
                    "source_url": None,
                    "sources": [f"schema:{element}"],
                    "scope": "excluded" if reason else "in",
                    "part": rule_part(rules, key, label) or "Other",
                }
                if reason:
                    entry["reason"] = reason
                place(entry)

        for manifest, docs in manifests.items():
            name = manifest.removeprefix("manifests/").removesuffix(".yaml")
            if jur == "us":
                if (
                    not federal_manifests
                    or re.match(r"us-[a-z]{2}-", name)
                    or not federal_manifests.search(name)
                ):
                    continue
                pick = docs
            else:
                if not name.startswith(f"{jur}-"):
                    continue
                if own_manifests and own_manifests.search(name):
                    pick = docs
                elif own_documents and not any(rx.search(name) for rx in all_state_patterns):
                    # A manual shared by programs: the documents that name this one.
                    pick = [
                        d
                        for d in docs
                        if own_documents.search(
                            f"{d.get('citation_path') or ''} {d.get('title') or ''}"
                        )
                    ]
                else:
                    continue
            for doc in pick:
                meta = doc.get("metadata") or {}
                toc = meta.get("toc_sequence")
                cp = doc.get("citation_path")
                entry = {
                    "key": cp or doc.get("source_url"),
                    "name": doc.get("title"),
                    "layer": "federal" if jur == "us" else "state",
                    "citation_path": cp,
                    "source_url": doc.get("source_url"),
                    "sources": [manifest],
                    "manifest": manifest,
                    "scope": "in",
                }
                if not entry["key"]:
                    continue
                if toc == 0 or meta.get("document_subtype") in (
                    "agency_policy_manual_index",
                    "agency_page",
                ):
                    entry["scope"], entry["reason"] = (
                        "excluded",
                        "Index or overview page: no rules of its own",
                    )
                elif back_year(
                    f"{cp or ''} {doc.get('title') or ''} {doc.get('source_url') or ''}", day
                ):
                    entry["scope"], entry["reason"] = "excluded", reasons["back_year"]
                for rule in state_cfg.get("exclude") or []:
                    if _in_range(rule, manifest, toc):
                        entry["scope"], entry["reason"] = "excluded", rule["reason"]
                entry["part"] = (
                    next(
                        (
                            r["part"]
                            for r in state_cfg.get("parts") or []
                            if _part_matches(r, manifest, toc, entry)
                        ),
                        None,
                    )
                    or rule_part(rules, cp, doc.get("title"))
                    or "Other"
                )
                url = entry["source_url"]
                if url:
                    dup = seen.get(url_key(normalize_url(url), aliases))
                    if dup is not None:
                        if dup["citation_path"] or not entry["citation_path"]:
                            continue
                        out.remove(dup)
                        by_key.pop(dup["key"], None)
                    seen[url_key(normalize_url(url), aliases)] = entry
                place(entry)

        for doc in state_cfg.get("known_sources") or []:
            place(
                {
                    "key": doc["citation_path"],
                    "name": doc["title"],
                    "layer": "state",
                    "citation_path": doc["citation_path"],
                    "source_url": doc.get("source_url"),
                    "sources": ["known-source"],
                    "note": doc.get("note"),
                    "scope": "in",
                    "part": doc.get("part", "Other"),
                }
            )
        full[jur] = out

    tiers_cfg = cfg["tiers"]
    in_scope = lambda tier: Counter(  # noqa: E731
        "federal" if j == "us" else "state"
        for j, docs in tier.items()
        for d in docs
        if d["scope"] == "in"
    )
    return {
        "schema": "axiom-program-bundle/v2",
        "id": pid,
        "program": pid,
        "title": prog["title"],
        "as_of": day.isoformat(),
        "generator": "scripts/build_program_bundle.py",
        "parts": prog["parts"],
        "comparison": prog.get("comparison"),
        "tiers": [
            {
                "id": "screener",
                "title": tiers_cfg["screener"]["title"],
                "definition": tiers_cfg["screener"]["definition"],
                "membership": {
                    "rule": "The PolicyEngine-US references of the release it was built from (the newest, by "
                    "default) and the plan's documents, each in the layer of the law it names, grouped into "
                    "documents",
                    "references": cfg["policyengine_us"]["references"].format(program=pid),
                    "policyengine_us_release": references.get("policyengine_us_release"),
                    "policyengine_us_version": references.get("policyengine_us_version"),
                    "policyengine_us_commit": references.get("policyengine_us_commit"),
                    "policyengine_us_folders": references.get("folders"),
                    "policyengine_us_state_folders": references.get("state_folders"),
                    "references_derived_by": references.get("derived_by"),
                    "reference_count": len(references["references"]),
                    "plan": cfg.get("plan"),
                    "plan_source": (plan or {}).get("source"),
                    "plan_documents": len(plan_docs),
                    "fiscal_year": fiscal_year(day),
                    "outside_the_states": dict(sorted(dropped.items())),
                    "in_scope_by_layer": dict(sorted(in_scope(screener).items())),
                },
            },
            {
                "id": "full",
                "title": tiers_cfg["full"]["title"],
                "definition": tiers_cfg["full"]["definition"],
                "membership": {
                    "rule": "Every in-scope document of the screener tier; the federal law of the program, "
                    "section by section, from its needs-closure schema, and its federal guidance manifests; "
                    "each state's own sources from its manifests for the program; and the sources the "
                    "config knows the corpus does not hold yet",
                    "federal_schema": prog.get("schema"),
                    "federal_manifests": prog.get("federal_manifests"),
                    "state_manifests": prog.get("state_manifests"),
                    "known_sources": sum(
                        len((o or {}).get("known_sources") or []) for o in overrides.values()
                    ),
                    "in_scope_by_layer": dict(sorted(in_scope(full).items())),
                },
            },
        ],
        "layers": [
            {"jurisdiction": jur, "screener": screener[jur], "full": full[jur]} for jur in layers
        ],
    }


def build(config_path: Path) -> dict[str, dict]:
    cfg = yaml.safe_load(config_path.read_text())
    aliases = cfg.get("host_aliases") or {}
    manifests = load_manifests()
    index = index_manifests(manifests, aliases)
    plan = json.loads((REPO / cfg["plan"]).read_text()) if cfg.get("plan") else None
    out = {}
    for pid, prog in cfg["programs"].items():
        references = json.loads(
            (REPO / cfg["policyengine_us"]["references"].format(program=pid)).read_text()
        )
        bundle = build_program(cfg, pid, references, plan, manifests, index)
        known = set(prog["parts"])
        for layer in bundle["layers"]:
            for tier in ("screener", "full"):
                for doc in layer[tier]:
                    for part in [doc.get("part")] + [c["part"] for c in doc.get("cited", [])]:
                        if part and part not in known:
                            raise SystemExit(
                                f"{pid} {layer['jurisdiction']} {tier}: part {part!r} of {doc['key']} "
                                "is not in the program's parts"
                            )
        out[pid] = bundle
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("config", type=Path, help="manifests/program-bundles/programs.config.yaml")
    ap.add_argument("--only", action="append", help="build only these programs")
    args = ap.parse_args()
    bundles = build(args.config)
    for pid, bundle in bundles.items():
        if args.only and pid not in args.only:
            continue
        out = args.config.with_name(f"{pid}.yaml")
        out.write_text(yaml.safe_dump(bundle, sort_keys=False, allow_unicode=True, width=110))
        s, f = (t["membership"]["in_scope_by_layer"] for t in bundle["tiers"])
        states = sum(
            1
            for layer in bundle["layers"]
            if layer["jurisdiction"] != "us" and any(d["scope"] == "in" for d in layer["full"])
        )
        print(
            f"{pid}: screener {s.get('federal', 0)} federal + {s.get('state', 0)} state documents; "
            f"full {f.get('federal', 0)} federal + {f.get('state', 0)} state; {states} states with sources"
        )


if __name__ == "__main__":
    main()
