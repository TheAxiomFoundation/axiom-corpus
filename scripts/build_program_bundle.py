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
  references in the program's own files that apply to the state, each with
  the citation path the parity model derived for it. Both group into
  documents: a US Code or CFR section, a state manual page, or the registered
  document that holds the citation.
- ``full``: the full document bundle. Every primary source of the state's own
  rules for the program, from the source manifests the config names.

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
] + ["dc"]
BACK_YEAR = re.compile(
    r"(?i)\bfy[-_ %]?(?:20)?(\d{2})\b|/(20\d{2})[-/]|\b(20\d{2})-poverty-guidelines"
)
# Plan ids that name a US Code or CFR section: "USC 7 2014", "CFR 7 273.1".
PLAN_USC = re.compile(r"^USC (\d+) (\S+)$")
PLAN_CFR = re.compile(r"^CFR (\d+) (\d+)\.(\S+)$")


def url_state(url: str, state_hosts: dict[str, str]) -> str | None:
    """The two-letter state a URL's publisher belongs to, by its host or a Cornell state path."""
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    for suffix, code in state_hosts.items():
        if host == suffix or host.endswith("." + suffix):
            return code
    m = re.search(r"(?:^|\.)([a-z]{2})\.gov$|\.state\.([a-z]{2})\.us$", host)
    if m and (m.group(1) or m.group(2)) in STATE_CODES:
        return m.group(1) or m.group(2)
    text = (host + parts.path.lower()).replace("-", "").replace("_", "")
    for name, code in zip(US_STATES, STATE_CODES, strict=False):
        if f".{name}.gov" in "." + text or f"/regulations/{name}/" in text:
            return code
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
        if (int(y) if len(y) == 4 else 2000 + int(y)) < current_fy:
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


def folder_part(file: str, folder_parts: dict[str, str]) -> str | None:
    """The part of the PolicyEngine folder a file sits in: gov/usda/snap/<a>/<b>/..., <a>/<b> before <a>."""
    f = file.removeprefix("parameters/").removeprefix("variables/")
    m = re.match(r"gov/usda/snap/([a-z_]+)(?:/([a-z_]+))?", f)
    if not m:
        return None
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
    registered, by_url, titles = manifest_index()
    state = cfg["jurisdiction"].removeprefix("us-")
    own = cfg["jurisdiction"]
    fy = cfg["current_fiscal_year"]
    reasons = tier_cfg["exclusions"]
    secondary = re.compile(tier_cfg["secondary_hosts"])
    data_series = re.compile(tier_cfg["data_series_hosts"])
    state_hosts = tier_cfg.get("state_hosts", {})
    bucket_reasons = {
        "back-year": reasons["back_year"],
        "secondary": reasons["secondary"],
        "data-series": reasons["data_series"],
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
    ):
        if not citation and url:
            citation = by_url.get(url_key(normalize_url(url)))
        other = None
        if citation:
            head = citation.split("/")[0]
            other = head if head not in ("us", own) else None
        elif url:
            code = url_state(url, state_hosts)
            other = code if code and code != state else None
        if other:
            reason = reasons["other_state"]
        elif url and not citation and reason is None and secondary.search(url):
            reason = reasons["secondary"]
        elif url and reason is None and data_series.search(url):
            reason = reasons["data_series"]
        elif url and reason is None and back_year(url, fy):
            reason = reasons["back_year"]
        key = document_key(citation, registered) if citation else normalize_url(url or "")
        layer = "federal" if key.startswith("us/") else "state" if key.startswith(own) else None
        if layer is None and url:
            code = url_state(url, state_hosts)
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

    for ref in references["references"]:
        votes = Counter(
            p for f in ref.get("files") or [] if (p := folder_part(f, tier_cfg["folder_parts"]))
        )
        add(
            "policyengine-references",
            ref["url"],
            ref.get("citation"),
            bucket_reasons.get(ref["bucket"]),
            part=votes.most_common(1)[0][0] if votes else None,
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
        "references in the program's own files that apply to the state, grouped into documents",
        "references": tier_cfg["references"],
        "policyengine_us_commit": references.get("policyengine_us_commit"),
        "references_derived_by": references.get("derived_by"),
        "reference_count": len(references["references"]),
    }
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


def full_tier(cfg: dict) -> dict:
    tier_cfg = cfg["full"]
    out: list[dict] = []
    seen: dict[tuple[str, str], dict] = {}
    for manifest in tier_cfg["manifests"]:
        data = yaml.safe_load((REPO / manifest).read_text()) or {}
        for doc in data.get("documents", []):
            meta = doc.get("metadata") or {}
            toc = meta.get("toc_sequence")
            entry = {
                "key": doc.get("citation_path") or doc.get("source_url"),
                "name": doc.get("title"),
                "citation_path": doc.get("citation_path"),
                "source_url": doc.get("source_url"),
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
                dup = seen.get(url_key(normalize_url(url)))
                if dup is not None:
                    if dup["citation_path"] or not entry["citation_path"]:
                        continue
                    out.remove(dup)
                seen[url_key(normalize_url(url))] = entry
            out.append(entry)
    return {
        "id": "full",
        "title": tier_cfg["title"],
        "definition": tier_cfg["definition"],
        "membership": {
            "rule": "Documents of the named source manifests, less the excluded pages",
            "manifests": tier_cfg["manifests"],
        },
        "documents": out,
    }


def build(config_path: Path) -> dict:
    cfg = yaml.safe_load(config_path.read_text())
    references = json.loads((REPO / cfg["screener"]["references"]).read_text())
    plan_file = cfg["screener"].get("plan")
    plan = json.loads((REPO / plan_file).read_text()) if plan_file else None
    tiers = [screener_tier(cfg, references, plan), full_tier(cfg)]
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
        "as_of": dt.date.today().isoformat(),
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
