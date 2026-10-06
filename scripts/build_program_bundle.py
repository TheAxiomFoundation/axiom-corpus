#!/usr/bin/env python3
"""Build a program bundle from its config: the documents that make up each
delivery tier of one program in one jurisdiction, and the part of the
program each one feeds.

Every choice lives in the config (manifests/program-bundles/<id>.config.yaml):
the inputs and their versions, the exclusions and their reasons, the parts
and how documents map to them. This script holds only the mechanics.

Two tiers, as the 2026-09-30 document-releases plan defines them:

- ``screener``: screener-level parity. Every document PolicyEngine-US cites for
  the program in the state is encoded, or excluded with a recorded reason.
  Membership is the union of the plan's document list (federal and state,
  which includes the income rules the program leans on) and the PolicyEngine-US
  references of one release, the newest by default (scripts/export_policyengine_references.py:
  every file that cites a URL, in the program's folders and the ones it
  reads). Both group into documents: a US Code or CFR section, a state manual
  page, or the registered document that holds the citation.
- ``full``: the full document bundle. Every relevant document: the screener
  tier's documents, the federal law of the program section by section (from
  its needs-closure schema), the state's own sources from the source
  manifests the config names, and the state's known sources the corpus does
  not hold yet. The screener tier is part of it by construction.

The bundle records membership, exclusions and parts only. Progress (in the
corpus, encoded, in progress) is telemetry the axiom.org collector reads from
the served corpus, the RuleSpec module mirror and the encode runs.

Usage::

    python scripts/build_program_bundle.py manifests/program-bundles/us-az-snap.config.yaml

The bundle is written next to the config, without ``.config``.
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


def manifest_index(
    aliases: dict[str, str] | None = None,
) -> tuple[list[str], dict[tuple[str, str], str], dict[str, str]]:
    """Every registered citation path, the citation path of each source and
    download URL, and titles."""
    paths, by_url, titles = set(), {}, {}
    for f in sorted((REPO / "manifests").glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(errors="ignore"))
        except yaml.YAMLError:
            continue
        docs = data.get("documents") if isinstance(data, dict) else None
        for doc in docs or []:
            cp = doc.get("citation_path") if isinstance(doc, dict) else None
            if not cp:
                continue
            paths.add(cp)
            if doc.get("title"):
                titles.setdefault(cp, doc["title"])
            for field in ("source_url", "download_url"):
                if doc.get(field):
                    # A recovery scope re-registers a document under its own
                    # path: the document's own path wins.
                    k = url_key(normalize_url(doc[field]), aliases)
                    if k not in by_url or ("/recovery/" in by_url[k] and "/recovery/" not in cp):
                        by_url[k] = cp
    return sorted(paths), by_url, titles


def folder_part(file: str, folder_parts: dict[str, str]) -> str | None:
    """The part of the PolicyEngine folder a file sits in: gov/usda/snap/<a>/<b>/...
    by <a>/<b> before <a>; a file outside SNAP's folder by its longest gov/... key."""
    f = file.removeprefix("parameters/").removeprefix("variables/")
    m = re.match(r"gov/usda/snap/([a-z_]+)(?:/([a-z_]+))?", f)
    if not m:
        held = [
            k for k in folder_parts if k.startswith("gov/") and (f == k or f.startswith(k + "/"))
        ]
        return folder_parts[max(held, key=len)] if held else None
    a, b = m.groups()
    return folder_parts.get(f"{a}/{b}") or folder_parts.get(a)


def plan_part(patterns: list[dict], *texts: str | None) -> str | None:
    """The part of the first pattern any of the texts matches."""
    for rule in patterns:
        if any(t and re.search(rule["pattern"], t) for t in texts):
            return rule["part"]
    return None


def part_of(votes: Counter) -> str:
    """The most voted part; "Other" only when nothing else has a vote."""
    named = [(n, p) for p, n in votes.items() if p != "Other"]
    return max(named)[1] if named else "Other"


def screener_tier(cfg: dict, references: dict, plan: dict | None) -> dict:
    tier_cfg = cfg["screener"]
    aliases = tier_cfg.get("host_aliases") or {}
    registered, by_url, titles = manifest_index(aliases)
    state = cfg["jurisdiction"].removeprefix("us-")
    own = cfg["jurisdiction"]
    day = as_of(cfg)
    reasons = tier_cfg["exclusions"]
    secondary = re.compile(tier_cfg["secondary_hosts"])
    data_series = re.compile(tier_cfg["data_series_hosts"])
    state_hosts = tier_cfg.get("state_hosts", {})
    state_patterns = tier_cfg.get("state_url_patterns") or []
    expired = [(re.compile(e["pattern"]), e["reason"]) for e in tier_cfg.get("expired") or []]
    same = {
        url_key(normalize_url(a), aliases): b
        for a, b in (tier_cfg.get("same_document") or {}).items()
    }
    # Files that cite a US Code or CFR section: an enacting text they also
    # cite is codified there.
    codifying = {
        f
        for ref in references["references"]
        if (ref.get("citation") or "").startswith(("us/statute/", "us/regulation/"))
        for f in ref.get("files") or []
    }
    docs: dict[str, dict] = {}
    cited: dict[str, dict[str, int]] = defaultdict(dict)
    parts: dict[str, Counter] = defaultdict(Counter)
    cited_parts: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))

    def add(
        source: str,
        url: str | None,
        citation: str | None,
        reason: str | None,
        name: str | None = None,
        part: str | None = None,
        ref_titles: list[str] | None = None,
    ):
        if url and url_key(normalize_url(url), aliases) in same:
            url = same[url_key(normalize_url(url), aliases)]
        if not citation and url:
            citation = by_url.get(url_key(normalize_url(url), aliases))
        code = url_state(url, state_hosts, state_patterns) if url else None
        # A title names the state only of a document that is not federal law.
        if not code and not (citation or "").startswith("us/"):
            code = title_state(ref_titles or [])
        text = " ".join([url or "", *(ref_titles or [])])
        other = None
        if citation:
            head = citation.split("/")[0]
            other = head if head not in ("us", own) else None
        if not other and url and not (citation or "").startswith("us/"):
            other = code if code and code != state else None
        if other:
            reason = reasons["other_state"]
        elif url and not citation and reason is None and secondary.search(url):
            reason = reasons["secondary"]
        elif url and reason is None and data_series.search(url):
            reason = reasons["data_series"]
        elif url and reason is None and back_year(text, day):
            reason = reasons["back_year"]
        key = document_key(citation, registered) if citation else normalize_url(url or "")
        layer = "federal" if key.startswith("us/") else "state" if key.startswith(own) else None
        if other:
            layer = "other state"
        elif layer is None and url:
            layer = "state" if code == state else "federal" if code is None else "other state"
        doc = docs.setdefault(
            key,
            {
                "key": key,
                "name": name or document_name(key, titles),
                "layer": layer or "other state",
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
        part = part or plan_part(tier_cfg["plan_parts"], citation, url, name) or "Other"
        parts[key][part] += 1
        # PolicyEngine's citations are the tier's units, a whole section
        # included; the plan names sections, which add a unit only below one.
        unit = citation and (citation != key or source == "policyengine-references")
        if unit:
            cited_parts[key][citation][part] += 1
        if reason is None:
            # A URL is one document with one classification: a source that
            # finds a reason to exclude it outweighs one that does not look.
            if doc["citation_path"] or not doc["reason"]:
                doc["scope"], doc["reason"] = "in", None
            if unit:
                cited[key][citation] = cited[key].get(citation, 0) + 1
        elif not doc["citation_path"]:
            doc["scope"], doc["reason"] = "excluded", doc["reason"] or reason
        elif doc["scope"] == "excluded" and not doc["reason"]:
            doc["reason"] = reason

    for ref in references["references"]:
        files = ref.get("files") or []
        votes = Counter(p for f in files if (p := folder_part(f, tier_cfg["folder_parts"])))
        reason = next(
            (why for rx, why in expired if any(rx.search(t) for t in [ref["url"], *files])), None
        )
        if reason is None and ENACTING.search(ref["url"]) and any(f in codifying for f in files):
            reason = reasons["enacting"]
        add(
            "policyengine-references",
            ref["url"],
            ref.get("citation"),
            reason,
            part=votes.most_common(1)[0][0] if votes else None,
            ref_titles=ref.get("titles"),
        )
    crosswalk = tier_cfg.get("crosswalk") or {}
    for doc in (plan or {}).get("documents", []):
        usc, cfr = PLAN_USC.match(doc["id"]), PLAN_CFR.match(doc["id"])
        citation = (
            crosswalk.get(doc["id"])
            or next(iter(doc.get("citation_paths") or []), None)
            or (f"us/statute/{usc.group(1)}/{usc.group(2)}" if usc else None)
            or (f"us/regulation/{cfr.group(1)}/{cfr.group(2)}/{cfr.group(3)}" if cfr else None)
        )
        urls = doc.get("urls") or []
        # A plan row that names a recovery scope's path: the document's own
        # path, when its URL is registered under one.
        if citation and "/recovery/" in citation and urls:
            own_path = by_url.get(url_key(normalize_url(urls[0]), aliases))
            if own_path and "/recovery/" not in own_path:
                citation = own_path
        add(
            "plan",
            urls[0] if urls else None,
            citation,
            None,
            None if citation else doc.get("title") or doc["id"],
        )

    out = []
    for key, doc in sorted(
        docs.items(), key=lambda kv: (kv[1]["scope"] != "in", kv[1]["layer"], kv[0])
    ):
        # The part most of its references feed; a document no SNAP file cites
        # takes its plan subject's part.
        doc["part"] = part_of(parts[key])
        if cited.get(key):
            doc["cited"] = [
                {"path": p, "references": n, "part": part_of(cited_parts[key][p])}
                for p, n in sorted(cited[key].items())
            ]
        if not doc["references"]:
            doc.pop("references")
        if doc["scope"] == "in":
            doc.pop("reason")
        out.append(doc)
    membership = {
        "rule": "The plan's documents for the program (federal and state), and the PolicyEngine-US "
        "references of the release it was built from (the newest, by default) that apply to the "
        "state, grouped into documents",
        "references": tier_cfg["references"],
        "policyengine_us_release": references.get("policyengine_us_release"),
        "policyengine_us_version": references.get("policyengine_us_version"),
        "policyengine_us_commit": references.get("policyengine_us_commit"),
        "policyengine_us_folders": references.get("folders"),
        "references_derived_by": references.get("derived_by"),
        "reference_count": len(references["references"]),
        "fiscal_year": fiscal_year(day),
    }
    if tier_cfg.get("comparison"):
        membership["comparison"] = tier_cfg["comparison"]
    if plan:
        membership.update(
            {
                "plan": tier_cfg["plan"],
                "plan_source": plan.get("source"),
                "plan_as_of": plan.get("as_of"),
                "plan_documents": len(plan["documents"]),
            }
        )
    return {
        "id": "screener",
        "title": tier_cfg["title"],
        "definition": tier_cfg["definition"],
        "membership": membership,
        "documents": out,
    }


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


def _first_part(patterns: list[dict], path: str) -> str:
    return next((r["part"] for r in patterns if re.search(r["pattern"], path)), "Other")


def full_tier(cfg: dict, screener: dict) -> dict:
    """Every relevant document, in four layers, each document once:

    1. every in-scope document of the screener tier, so the screener tier is
       part of this one;
    2. the federal law of the program: each section the program's
       needs-closure schema names a corpus path in, less the parts the config
       excludes;
    3. the state's own sources, from the named source manifests;
    4. the state's sources the corpus does not hold yet, as the config lists
       them. They stay in the tier and count as not in the corpus.
    """
    tier_cfg = cfg["full"]
    aliases = cfg["screener"].get("host_aliases") or {}
    own = cfg["jurisdiction"]
    day = as_of(cfg)
    out: list[dict] = []
    by_key: dict[str, dict] = {}
    seen: dict[tuple[str, str], dict] = {}

    def layer_of(path: str | None, fallback: str = "state") -> str:
        if path and path.startswith("us/"):
            return "federal"
        return "state" if path and path.startswith(own) else fallback

    def place(entry: dict) -> None:
        """Add an entry, or record its source on the entry that holds its key."""
        held = by_key.get(entry["key"])
        if held is not None:
            for source in entry["sources"]:
                if source not in held["sources"]:
                    held["sources"].append(source)
            return
        by_key[entry["key"]] = entry
        out.append(entry)

    # 1. The screener tier, as it scopes it.
    for doc in screener["documents"]:
        if doc["scope"] != "in":
            continue
        place(
            {
                "key": doc["key"],
                "name": doc["name"],
                "layer": doc["layer"],
                "citation_path": doc["citation_path"],
                "source_url": doc["source_url"],
                "sources": ["screener"],
                "scope": "in",
                "part": doc["part"],
            }
        )

    # 2. The federal law of the program.
    federal = tier_cfg.get("federal") or {}
    if federal:
        schema = yaml.safe_load((REPO / federal["schema"]).read_text())
        excludes = [(re.compile(e["pattern"]), e["reason"]) for e in federal.get("exclude") or []]
        reasons = cfg["screener"]["exclusions"]
        for element in schema["elements"]:
            path = element.get("citation_path")
            if not path or not path.startswith("us/"):
                continue
            key = document_key(path, [])
            reason = next((why for rx, why in excludes if rx.search(key)), None)
            if reason is None and back_year(f"{key} {element.get('label', '')}", day):
                reason = reasons["back_year"]
            entry = {
                "key": key,
                "name": document_name(key, {}),
                "layer": "federal",
                "citation_path": key,
                "source_url": None,
                "sources": [f"schema:{element['id']}"],
                "scope": "excluded" if reason else "in",
                "part": _first_part(federal.get("parts") or [], key),
            }
            if reason:
                entry["reason"] = reason
            held = by_key.get(key)
            if held is not None and held["scope"] == "excluded" and not reason:
                held["scope"] = "in"
                held.pop("reason", None)
            place(entry)

    # 3. The state's own sources.
    for manifest in tier_cfg["manifests"]:
        data = yaml.safe_load((REPO / manifest).read_text()) or {}
        for doc in data.get("documents", []):
            meta = doc.get("metadata") or {}
            toc = meta.get("toc_sequence")
            entry = {
                "key": doc.get("citation_path") or doc.get("source_url"),
                "name": doc.get("title"),
                "layer": layer_of(doc.get("citation_path")),
                "citation_path": doc.get("citation_path"),
                "source_url": doc.get("source_url"),
                "sources": [manifest],
                "manifest": manifest,
                "scope": "in",
            }
            if toc == 0 or meta.get("document_subtype") in (
                "agency_policy_manual_index",
                "agency_page",
            ):
                entry["scope"], entry["reason"] = (
                    "excluded",
                    "Index or overview page: no rules of its own",
                )
            for rule in tier_cfg.get("exclude") or []:
                if _in_range(rule, manifest, toc):
                    entry["scope"], entry["reason"] = "excluded", rule["reason"]
            entry["part"] = next(
                (
                    rule["part"]
                    for rule in tier_cfg.get("parts") or []
                    if _part_matches(rule, manifest, toc, entry)
                ),
                "Other",
            )
            # One source registered twice (a primary-policy row and its own
            # manifest) is one document: keep the entry that has a citation path.
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

    # 4. The state's sources the corpus does not hold yet.
    for doc in tier_cfg.get("known_sources") or []:
        place(
            {
                "key": doc["citation_path"],
                "name": doc["title"],
                "layer": layer_of(doc["citation_path"]),
                "citation_path": doc["citation_path"],
                "source_url": doc.get("source_url"),
                "sources": ["known-source"],
                "note": doc.get("note"),
                "scope": "in",
                "part": doc.get("part", "Other"),
            }
        )

    in_scope = Counter(d["layer"] for d in out if d["scope"] == "in")
    return {
        "id": "full",
        "title": tier_cfg["title"],
        "definition": tier_cfg["definition"],
        "membership": {
            "rule": "Every in-scope document of the screener tier; the federal law of the program, "
            "section by section, from its needs-closure schema; the state's own sources from the "
            "named manifests; and the state's known sources the corpus does not hold yet",
            "screener_documents": sum(d["scope"] == "in" for d in screener["documents"]),
            "federal_schema": federal.get("schema"),
            "manifests": tier_cfg["manifests"],
            "known_sources": len(tier_cfg.get("known_sources") or []),
            "in_scope_by_layer": dict(sorted(in_scope.items())),
        },
        "documents": out,
    }


def build(config_path: Path) -> dict:
    cfg = yaml.safe_load(config_path.read_text())
    references = json.loads((REPO / cfg["screener"]["references"]).read_text())
    plan_file = cfg["screener"].get("plan")
    plan = json.loads((REPO / plan_file).read_text()) if plan_file else None
    screener = screener_tier(cfg, references, plan)
    tiers = [screener, full_tier(cfg, screener)]
    known = set(cfg["parts"])
    for tier in tiers:
        for doc in tier["documents"]:
            for part in [doc.get("part")] + [c["part"] for c in doc.get("cited", [])]:
                if part and part not in known:
                    raise SystemExit(
                        f"{tier['id']}: part {part!r} of {doc['key']} is not in the config's parts"
                    )
    config = config_path.resolve()
    return {
        "schema": "axiom-program-bundle/v1",
        "id": cfg["id"],
        "program": cfg["program"],
        "jurisdiction": cfg["jurisdiction"],
        "title": cfg["title"],
        "as_of": as_of(cfg).isoformat(),
        "config": str(config.relative_to(REPO))
        if config.is_relative_to(REPO)
        else str(config_path),
        "generator": "scripts/build_program_bundle.py",
        "parts": cfg["parts"],
        "tiers": tiers,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("config", type=Path, help="manifests/program-bundles/<id>.config.yaml")
    ap.add_argument("--out", type=Path, help="default: the config's path without .config")
    args = ap.parse_args()
    bundle = build(args.config)
    out = args.out or args.config.with_name(args.config.name.replace(".config.yaml", ".yaml"))
    out.write_text(yaml.safe_dump(bundle, sort_keys=False, allow_unicode=True, width=110))
    for tier in bundle["tiers"]:
        docs = tier["documents"]
        print(
            f"{tier['id']}: {len(docs)} documents, {sum(d['scope'] == 'in' for d in docs)} in scope"
        )


if __name__ == "__main__":
    main()
