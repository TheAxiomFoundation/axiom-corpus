#!/usr/bin/env python3
"""Build a program bundle: the documents that make up each delivery tier of one
program in one jurisdiction.

Two tiers, as the 2026-09-30 document-releases plan defines them:

- ``screener``: screener-level parity. Every document PolicyEngine-US cites for
  the program in the state is encoded, or excluded with a recorded reason.
  Membership is the union of two inputs: the plan's document list (the
  PolicyEngine-cited documents of the program, federal and state, which
  include the income rules the program leans on) and a references export
  (the PolicyEngine-US references in the program's own files that apply to
  the state, each with the citation path the parity model derived for it).
  Both group into documents: a US Code or CFR section, a state manual page,
  or the registered document that holds the citation.
- ``full``: the full document bundle. Every primary source of the state's own
  rules for the program, from the source manifests named on the command line.

The bundle records membership and exclusions only. Progress (in the corpus,
encoded, in main, tests pass) is telemetry that the axiom.org collector reads
from the served corpus and the RuleSpec index, so it never goes stale here.

Example::

    python scripts/build_program_bundle.py \\
      --id us-az/snap --title "Arizona SNAP" \\
      --references sources/policyengine-us/snap-us-az-references.json \\
      --plan document-sizing.json --plan-ref <repo>@<commit>:<path> \\
      --full manifests/us-az-des-faa5-manual.yaml \\
      --full manifests/us-az-snap-primary-policy.yaml \\
      --out manifests/program-bundles/us-az-snap.yaml
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import yaml

REPO = Path(__file__).resolve().parent.parent

SCREENER_DEFINITION = (
    "Every document that PolicyEngine-US cites for this program in this state is encoded, "
    "or excluded with a recorded reason. A conformance report against a pinned PolicyEngine "
    "version closes the tier."
)
FULL_DEFINITION = (
    "Every primary source of the state's own rules for this program: its policy manual, "
    "regulations, state plans, waivers and change notices. The federal layer it builds on "
    "is the screener tier's federal documents."
)

# Parity buckets that are not current law, with the reason a reader sees.
EXCLUDED_BUCKETS = {
    "back-year": "Back-year table: not current law",
    "secondary": "Secondary source: not law",
    "data-series": "Data series: not law",
}

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
    "dc",
]
# Publishers of a state's own sources, by host, beyond <state>.gov and <xx>.gov.
STATE_HOSTS = {"azdes.gov": "az", "az.gov": "az"}
BACK_YEAR = re.compile(
    r"(?i)\bfy[-_ %]?(?:20)?(\d{2})\b|/(20\d{2})[-/]|\b(20\d{2})-poverty-guidelines"
)
DATA_SERIES = re.compile(r"(?i)snapqcdata\.net|data\.census\.gov|data\.bls\.gov|fred\.stlouisfed")
# The parity model's secondary hosts, and USDA State Options Reports, which the
# corpus SNAP queue policy forbids as a source.
SECONDARY = re.compile(
    r"(?i)snapscreener|docs\.google\.com|benefitswiki|website-files\.com|policyengine\.org"
    r"|github\.com|state[-_ ]?options"
)
# Plan ids that name a US Code or CFR section: "USC 7 2014", "CFR 7 273.1".
PLAN_USC = re.compile(r"^USC (\d+) (\S+)$")
PLAN_CFR = re.compile(r"^CFR (\d+) (\d+)\.(\S+)$")

# The parts of the SNAP calculation, in its order. A PolicyEngine reference
# takes the part its PolicyEngine file sits in (gov/usda/snap/<part>/...).
CALCULATION_PARTS = [
    "Household and eligibility",
    "Income",
    "Deductions",
    "Assets",
    "Work requirements",
    "Benefit amount",
    "Definitions from other programs",
    "Other",
]
SNAP_FILE_PARTS = {
    "eligibility": "Household and eligibility",
    "categorical_eligibility": "Household and eligibility",
    "student": "Household and eligibility",
    "snap_unit_size": "Household and eligibility",
    "has_snap_elderly_disabled_member": "Household and eligibility",
    "asset_test": "Assets",
    "work_requirements": "Work requirements",
    "min_allotment": "Benefit amount",
    "max_allotment": "Benefit amount",
    "uprating": "Benefit amount",
    "emergency_allotment": "Benefit amount",
}
# A plan document no SNAP file cites: the part its subject feeds.
PLAN_PARTS = [
    (
        re.compile(r"^us/(statute/(26|38|25)|regulation/26|form/irs|manual/ssa)/"),
        "Definitions from other programs",
    ),
    (re.compile(r"(?i)poverty"), "Income"),
    (re.compile(r"(?i)cola|allotment"), "Benefit amount"),
    (re.compile(r"(?i)abawd|work-requirement|time-limit"), "Work requirements"),
    (re.compile(r"(?i)utility|sua-|deduction"), "Deductions"),
    (re.compile(r"(?i)alien|elderly|disabled|eligib"), "Household and eligibility"),
]


def calculation_part(file: str) -> str:
    """The part of the SNAP calculation a PolicyEngine file belongs to."""
    f = file.removeprefix("parameters/").removeprefix("variables/")
    m = re.match(r"gov/usda/snap/([a-z_]+)(?:/([a-z_]+))?", f)
    if not m:
        return "Other"
    head, sub = m.groups()
    if head == "income":
        if sub == "deductions":
            return "Deductions"
        if sub == "ineligible_members":
            return "Household and eligibility"
        return "Income"
    return SNAP_FILE_PARTS.get(head, "Other")


def plan_part(*texts: str | None) -> str:
    for pattern, part in PLAN_PARTS:
        if any(t and pattern.search(t) for t in texts):
            return part
    return "Other"


def url_state(url: str) -> str | None:
    """The two-letter state a URL's publisher belongs to, by its host or a Cornell state path."""
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    for suffix, code in STATE_HOSTS.items():
        if host == suffix or host.endswith("." + suffix):
            return code
    m = re.search(r"(?:^|\.)([a-z]{2})\.gov$|\.state\.([a-z]{2})\.us$", host)
    if m and (m.group(1) or m.group(2)) in STATE_CODES:
        return m.group(1) or m.group(2)
    text = (host + parts.path.lower()).replace("-", "").replace("_", "")
    for name in US_STATES:
        if f".{name}.gov" in "." + text or f"/regulations/{name}/" in text:
            return STATE_CODES[US_STATES.index(name)] if name != "arizona" else "az"
    return None


def normalize_url(url: str) -> str:
    """A WebWorks manual link (index.html#page/<chapter>/<page>.html) names its page in the fragment."""
    m = re.match(r"(https?://[^/]+)/index\.html#page/(.+)$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else url.split("#")[0]


def url_key(url: str) -> tuple[str, str]:
    parts = urlsplit(url.strip())
    return parts.netloc.lower().removeprefix("www."), parts.path.rstrip("/").lower()


def back_year(url: str, current_fy: int) -> bool:
    for m in BACK_YEAR.finditer(url):
        y = m.group(1) or m.group(2) or m.group(3)
        year = int(y) if len(y) == 4 else 2000 + int(y)
        if year < current_fy:
            return True
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


def manifest_index() -> tuple[list[str], dict[tuple[str, str], str], dict[str, str]]:
    """Every registered citation path, the citation path of each source URL, and titles."""
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
            if doc.get("source_url"):
                by_url.setdefault(url_key(normalize_url(doc["source_url"])), cp)
    return sorted(paths), by_url, titles


def screener_tier(
    export: dict,
    plan: dict | None,
    plan_ref: str | None,
    state: str,
    crosswalk: dict[str, str],
    current_fy: int,
) -> dict:
    registered, by_url, titles = manifest_index()
    own = f"us-{state}"
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
    ):
        if not citation and url:
            citation = by_url.get(url_key(normalize_url(url)))
        other = None
        if citation:
            head = citation.split("/")[0]
            other = head if head not in ("us", own) else None
        elif url:
            code = url_state(url)
            other = code if code and code != state else None
        if other:
            reason = "Another state's source"
        elif url and not citation and reason is None and SECONDARY.search(url):
            reason = EXCLUDED_BUCKETS["secondary"]
        elif url and reason is None and DATA_SERIES.search(url):
            reason = EXCLUDED_BUCKETS["data-series"]
        elif url and reason is None and back_year(url, current_fy):
            reason = EXCLUDED_BUCKETS["back-year"]
        key = document_key(citation, registered) if citation else normalize_url(url or "")
        layer = "federal" if key.startswith("us/") else "state" if key.startswith(own) else None
        if layer is None and url:
            code = url_state(url)
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
        part = part or plan_part(citation, url, name)
        parts[key][part] += 1
        if citation and citation != key:
            cited_parts[key][citation][part] += 1
        if reason is None:
            # A URL is one document with one classification: a source that
            # finds a reason to exclude it outweighs one that does not look.
            if doc["citation_path"] or not doc["reason"]:
                doc["scope"], doc["reason"] = "in", None
            if citation and citation != key:
                cited[key][citation] = cited[key].get(citation, 0) + 1
        elif not doc["citation_path"]:
            doc["scope"], doc["reason"] = "excluded", doc["reason"] or reason
        elif doc["scope"] == "excluded" and not doc["reason"]:
            doc["reason"] = reason

    for ref in export["references"]:
        add(
            "policyengine-references",
            ref["url"],
            ref.get("citation"),
            EXCLUDED_BUCKETS.get(ref["bucket"]),
            part=Counter(calculation_part(f) for f in ref.get("files") or []).most_common(1)[0][0]
            if ref.get("files")
            else None,
        )
    plan_count = 0
    if plan:
        by_id = {d["id"]: d for d in plan["documents"]}
        program = next(p for p in plan["programs"] if p["id"] == export.get("program", "snap"))
        for doc_id in program["documentIds"]:
            doc = by_id[doc_id]
            if doc["jurisdiction"] not in ("US", own.upper()):
                continue
            plan_count += 1
            measurement = doc.get("measurement") or {}
            if isinstance(measurement, str):
                measurement = ast.literal_eval(measurement)
            usc, cfr = PLAN_USC.match(doc_id), PLAN_CFR.match(doc_id)
            citation = (
                crosswalk.get(doc_id)
                or next(iter(measurement.get("citationPaths") or []), None)
                or (f"us/statute/{usc.group(1)}/{usc.group(2)}" if usc else None)
                or (f"us/regulation/{cfr.group(1)}/{cfr.group(2)}/{cfr.group(3)}" if cfr else None)
            )
            urls = doc.get("urls") or []
            add(
                "plan",
                urls[0] if urls else None,
                citation,
                None,
                None if citation else doc.get("title") or doc_id,
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
        "references in the program's own files that apply to the state, grouped into documents",
        "policyengine_us_commit": export.get("policyengine_us_commit"),
        "references": len(export["references"]),
        "references_derived_by": export.get("derived_by"),
    }
    if plan:
        membership.update(
            {"plan": plan_ref, "plan_as_of": plan.get("asOf"), "plan_documents": plan_count}
        )
    if crosswalk:
        membership["crosswalk"] = crosswalk
    return {
        "id": "screener",
        "title": "Screener-level parity",
        "definition": SCREENER_DEFINITION,
        "membership": membership,
        "documents": out,
    }


def part_of(votes: Counter) -> str:
    """The most voted part, other than "Other" when anything else has a vote."""
    named = [(n, p) for p, n in votes.items() if p != "Other"]
    return max(named)[1] if named else "Other"


def parse_toc_exclusions(specs: list[str]) -> list[dict]:
    """``<manifest>:<first>-<last>=<reason>``: pages of a manifest, by toc_sequence, outside the program."""
    out = []
    for spec in specs:
        where, reason = spec.split("=", 1)
        manifest, span = where.rsplit(":", 1)
        first, _, last = span.partition("-")
        out.append(
            {"manifest": manifest, "toc": [int(first), int(last or first)], "reason": reason}
        )
    return out


def parse_toc_parts(specs: list[str]) -> list[dict]:
    """``<manifest>:<first>-<last>=<part>``, or ``<manifest>:all=<part>`` for every page of a manifest."""
    out = []
    for spec in specs:
        where, part = spec.split("=", 1)
        manifest, span = where.rsplit(":", 1)
        if span == "all":
            out.append({"manifest": manifest, "toc": None, "part": part})
        else:
            first, _, last = span.partition("-")
            out.append(
                {"manifest": manifest, "toc": [int(first), int(last or first)], "part": part}
            )
    return out


def full_tier(manifests: list[Path], toc_exclusions: list[dict], toc_parts: list[dict]) -> dict:
    out = []
    seen: dict[tuple[str, str], dict] = {}
    for path in manifests:
        rel = path.resolve().relative_to(REPO) if path.resolve().is_relative_to(REPO) else path
        data = yaml.safe_load(path.read_text()) or {}
        for doc in data.get("documents", []):
            meta = doc.get("metadata") or {}
            toc = meta.get("toc_sequence")
            entry = {
                "key": doc.get("citation_path") or doc.get("source_url"),
                "name": doc.get("title"),
                "citation_path": doc.get("citation_path"),
                "source_url": doc.get("source_url"),
                "manifest": str(rel),
                "scope": "in",
            }
            subtype = meta.get("document_subtype")
            if toc == 0 or subtype in ("agency_policy_manual_index", "agency_page"):
                entry["scope"], entry["reason"] = (
                    "excluded",
                    "Index or overview page: no rules of its own",
                )
            for rule in toc_exclusions:
                if (
                    rule["manifest"] == str(rel)
                    and toc is not None
                    and rule["toc"][0] <= toc <= rule["toc"][1]
                ):
                    entry["scope"], entry["reason"] = "excluded", rule["reason"]
            # The manual part: a toc range, else the whole manifest's part.
            for rule in toc_parts:
                in_range = rule["toc"] is None or (
                    toc is not None and rule["toc"][0] <= toc <= rule["toc"][1]
                )
                if rule["manifest"] == str(rel) and in_range:
                    entry["part"] = rule["part"]
            entry.setdefault("part", "Other")
            # One source registered twice (a primary-policy row and its own
            # manifest) is one document: keep the entry that has a citation path.
            url = entry["source_url"]
            if url:
                dup = seen.get(url_key(normalize_url(url)))
                if dup is not None:
                    if dup["citation_path"] or not entry["citation_path"]:
                        continue
                    out.remove(dup)
                seen[url_key(normalize_url(url))] = entry
            out.append(entry)
    return {
        "id": "full",
        "title": "Full document bundle",
        "definition": FULL_DEFINITION,
        "membership": {
            "rule": "Documents of the named source manifests, less the ranges excluded below",
            "manifests": sorted({e["manifest"] for e in out}),
            **({"excluded_ranges": toc_exclusions} if toc_exclusions else {}),
        },
        "documents": out,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--id", required=True, help="<jurisdiction>/<program>, e.g. us-az/snap")
    ap.add_argument("--title", required=True)
    ap.add_argument(
        "--references", required=True, type=Path, help="PolicyEngine-US references export (JSON)"
    )
    ap.add_argument("--plan", type=Path, help="the plan's document list (document-sizing.json)")
    ap.add_argument("--plan-ref", help="where the plan file came from: <repo>@<commit>:<path>")
    ap.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="PLAN_ID=CITATION_PATH",
        help="a plan document whose URL names no page, mapped to its citation path by title",
    )
    ap.add_argument("--current-fy", type=int, default=2026)
    ap.add_argument(
        "--full",
        action="append",
        default=[],
        type=Path,
        help="a source manifest of the full bundle",
    )
    ap.add_argument(
        "--part-toc",
        action="append",
        default=[],
        metavar="MANIFEST:FIRST-LAST=PART",
        help="the manual part of manifest pages, by toc_sequence; MANIFEST:all=PART for a whole manifest",
    )
    ap.add_argument(
        "--exclude-toc",
        action="append",
        default=[],
        metavar="MANIFEST:FIRST-LAST=REASON",
        help="manifest pages, by toc_sequence, that belong to another program",
    )
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    jurisdiction, program = args.id.split("/")
    export = json.loads(args.references.read_text())
    plan = json.loads(args.plan.read_text()) if args.plan else None
    crosswalk = dict(m.split("=", 1) for m in args.map)
    bundle = {
        "schema": "axiom-program-bundle/v1",
        "id": args.id,
        "program": program,
        "jurisdiction": jurisdiction,
        "title": args.title,
        "as_of": dt.date.today().isoformat(),
        "generator": "scripts/build_program_bundle.py",
        "tiers": [
            screener_tier(
                export,
                plan,
                args.plan_ref,
                jurisdiction.removeprefix("us-"),
                crosswalk,
                args.current_fy,
            ),
            full_tier(
                args.full,
                parse_toc_exclusions(args.exclude_toc),
                parse_toc_parts(args.part_toc),
            ),
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(bundle, sort_keys=False, allow_unicode=True, width=110))
    for tier in bundle["tiers"]:
        docs = tier["documents"]
        print(
            f"{tier['id']}: {len(docs)} documents, {sum(d['scope'] == 'in' for d in docs)} in scope"
        )


if __name__ == "__main__":
    main()
