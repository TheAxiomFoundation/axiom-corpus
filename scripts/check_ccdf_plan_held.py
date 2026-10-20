#!/usr/bin/env python3
"""Report whether the corpus already holds CCDF plan citation paths for a jurisdiction.

Ask this before fetching or extracting a CCDF plan. On 2026-10-20 two runs in one
wave did the work twice: Missouri's Initial Plan was extracted and the whole scope
was then withdrawn because the uniqueness check found all 42 citation paths already
held by ``us-mo/policy/2026-10-12-w7-state-benefits-policy-mo``, and Maryland's plan
text turned out to be held the same way. See
``docs/ingest-runs/2026-10-20-ccdf-held-plan-path-audit.md``.

A sweep of ``data/corpus/provisions`` alone cannot answer the question, and that is
what made the omission expensive: when ``.axiom/corpus-locks/`` exists, the corpus
holds every locked scope but ``data/corpus`` holds only what has been fetched, so a
local sweep sees a handful of jurisdictions where 49 are held. This script therefore
reads, in this order:

1. ``.axiom/corpus-locks/<jurisdiction>/<class>/<version>.json`` - the scopes the
   corpus holds, fetched or not. This is the authoritative answer.
2. ``.axiom/ingest-manifests/<jurisdiction>/<class>/<version>.json`` - the signature
   and the coverage counts of each of those scopes.
3. ``manifests/ccdf-agent-queue.yaml`` - the ``held_in_scope``/``held_in_scopes``
   pointers, which name the holding scope of a plan held under a scope whose version
   does not say "ccdf-plan" (the wave-7 ``*-w7-state-benefits-policy-*`` scopes).
4. ``data/corpus/provisions/<jurisdiction>/<class>/<version>.jsonl``, when fetched -
   the exact citation paths, and any path under a variant spelling of the family root.

The family root is ``<jurisdiction>/policy/acf/ccdf-plan/<plan-version>``. The plan,
its amendments and its appendices are three sub-families under that root, so a plan
collides only with a plan. The amendment version is in the path for some
jurisdictions (``fy2025-2027-amendment-1``) and not for others, where an amendment
sits at the bare ``fy2025-2027`` path; a new plan or amendment written to the bare
path therefore collides with whatever already holds it.

Read-only: this script opens files for reading only. It fetches nothing and it
writes nothing, not even a report file.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

LOCK_ROOT = Path(".axiom") / "corpus-locks"
INGEST_MANIFEST_ROOT = Path(".axiom") / "ingest-manifests"
PROVISIONS_ROOT = Path("data") / "corpus" / "provisions"
QUEUE = Path("manifests") / "ccdf-agent-queue.yaml"

# `<jurisdiction>/policy/acf/ccdf-plan/<plan-version>/...`, confirmed against the held
# scopes rather than assumed.
FAMILY_ROOT = "policy/acf/ccdf-plan"
# A citation path that names a CCDF plan under any other spelling of the root.
VARIANT_PATH = re.compile(r"ccdf[-_]?(state[-_]?)?plan", re.IGNORECASE)
# Scope versions that say on their face that they hold a CCDF plan family.
PLAN_SCOPE = re.compile(r"ccdf-plan-fy\d{4}-\d{4}$")
AMENDMENTS_SCOPE = re.compile(r"ccdf-state-plan-amendments$")
APPENDICES_SCOPE = re.compile(r"ccdf-state-plan-appendices$")

SUBFAMILY_PLAN = "plan"
SUBFAMILY_AMENDMENTS = "amendments"
SUBFAMILY_APPENDICES = "appendices"


def _subfamily_of_version(version: str) -> str | None:
    if APPENDICES_SCOPE.search(version):
        return SUBFAMILY_APPENDICES
    if AMENDMENTS_SCOPE.search(version):
        return SUBFAMILY_AMENDMENTS
    if PLAN_SCOPE.search(version):
        return SUBFAMILY_PLAN
    return None


def _subfamily_of_path(citation_path: str) -> str:
    """Classify a path under the family root by its plan-version segment."""
    segments = citation_path.split("/")
    plan_version = segments[4] if len(segments) > 4 else ""
    if "appendix" in plan_version:
        return SUBFAMILY_APPENDICES
    if "amendment" in plan_version:
        return SUBFAMILY_AMENDMENTS
    return SUBFAMILY_PLAN


def _queue_pointers(repo_root: Path) -> dict[str, list[str]]:
    """Read every ``held_in_scope``/``held_in_scopes`` pointer out of the queue."""
    queue_path = repo_root / QUEUE
    if not queue_path.is_file():
        return {}
    with queue_path.open(encoding="utf-8") as handle:
        queue = yaml.safe_load(handle)
    pointers: dict[str, list[str]] = defaultdict(list)

    def collect(row: dict[str, Any], jurisdiction: str) -> None:
        one = row.get("held_in_scope")
        if isinstance(one, str):
            pointers[jurisdiction].append(one)
        many = row.get("held_in_scopes")
        if isinstance(many, list):
            pointers[jurisdiction].extend(str(item) for item in many)

    for row in (queue or {}).get("states") or []:
        jurisdiction = str(row.get("jurisdiction") or "")
        collect(row, jurisdiction)
        for family in row.get("additional_families") or []:
            collect(family, jurisdiction)
    return dict(pointers)


def _fetched_paths(repo_root: Path, jurisdiction: str) -> tuple[
    dict[str, set[str]], list[str]
]:
    """Citation paths under the family root, per scope, plus variant-spelling paths."""
    per_scope: dict[str, set[str]] = defaultdict(set)
    variants: list[str] = []
    root = repo_root / PROVISIONS_ROOT / jurisdiction
    if not root.is_dir():
        return {}, []
    prefix = f"{jurisdiction}/{FAMILY_ROOT}"
    for provisions_file in sorted(root.glob("*/*.jsonl")):
        document_class = provisions_file.parent.name
        version = provisions_file.name.removesuffix(".jsonl")
        scope = f"{jurisdiction}/{document_class}/{version}"
        with provisions_file.open(encoding="utf-8") as handle:
            for line in handle:
                if "ccdf" not in line.lower():
                    continue
                citation_path = (json.loads(line).get("citation_path") or "").strip()
                if citation_path.startswith(prefix):
                    per_scope[scope].add(citation_path)
                elif VARIANT_PATH.search(citation_path):
                    variants.append(f"{scope}: {citation_path}")
    return dict(per_scope), sorted(set(variants))


def _scope_evidence(repo_root: Path, scope: str) -> dict[str, Any]:
    jurisdiction, document_class, version = scope.split("/", 2)
    lock = repo_root / LOCK_ROOT / jurisdiction / document_class / f"{version}.json"
    manifest = (
        repo_root / INGEST_MANIFEST_ROOT / jurisdiction / document_class / f"{version}.json"
    )
    evidence: dict[str, Any] = {
        "scope": scope,
        "locked": lock.is_file(),
        "signed": False,
        "provision_count": None,
        "coverage_complete": None,
        "fetched": (
            repo_root / PROVISIONS_ROOT / jurisdiction / document_class / f"{version}.jsonl"
        ).is_file(),
    }
    if manifest.is_file():
        with manifest.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        evidence["signed"] = bool((payload.get("signature") or {}).get("value"))
        coverage = payload.get("coverage") or {}
        evidence["provision_count"] = coverage.get("provision_count")
        evidence["coverage_complete"] = coverage.get("complete")
    return evidence


def holdings(repo_root: Path, jurisdiction: str) -> dict[str, Any]:
    """Everything the repo records about CCDF plan text held for one jurisdiction."""
    candidates: dict[str, str | None] = {}
    lock_dir = repo_root / LOCK_ROOT / jurisdiction
    for lock in sorted(lock_dir.glob("*/*.json")) if lock_dir.is_dir() else []:
        version = lock.name.removesuffix(".json")
        subfamily = _subfamily_of_version(version)
        if subfamily is not None:
            candidates[f"{jurisdiction}/{lock.parent.name}/{version}"] = subfamily
    for pointer in _queue_pointers(repo_root).get(jurisdiction, []):
        # A queue pointer exists because somebody recorded that this scope holds plan
        # text, so it answers for itself even when its version name carries no CCDF
        # subfamily (a wave-named scope such as `2026-10-12-w7-state-benefits-policy-mo`
        # classifies as None). Falling through to None would drop the scope out of
        # `plan_scopes` and report NOT HELD for a jurisdiction whose plan text is held,
        # which is the false negative this check exists to prevent.
        named = _subfamily_of_version(pointer.rsplit("/", 1)[-1])
        candidates.setdefault(pointer, named if named is not None else "mixed")

    fetched, variants = _fetched_paths(repo_root, jurisdiction)
    for scope, paths in fetched.items():
        subfamilies = {_subfamily_of_path(path) for path in paths}
        # A fetched scope answers for itself, whatever its version is called.
        candidates[scope] = sorted(subfamilies)[0] if len(subfamilies) == 1 else "mixed"

    held: list[dict[str, Any]] = []
    for scope in sorted(candidates):
        evidence = _scope_evidence(repo_root, scope)
        if not (evidence["locked"] or evidence["fetched"]):
            # The queue named it but neither a lock nor fetched bytes back it up.
            evidence["unverified"] = True
        evidence["subfamily"] = candidates[scope]
        paths = sorted(fetched.get(scope, ()))
        evidence["citation_paths"] = paths
        evidence["citation_path_count"] = len(paths) if paths else None
        held.append(evidence)

    plan_scopes = [
        entry for entry in held if entry["subfamily"] in (SUBFAMILY_PLAN, "mixed")
    ]
    return {
        "jurisdiction": jurisdiction,
        "plan_text_held": bool(plan_scopes),
        "plan_scopes": [entry["scope"] for entry in plan_scopes],
        "scopes": held,
        "variant_citation_paths": variants,
    }


def _print_report(report: dict[str, Any]) -> None:
    verdict = "HELD" if report["plan_text_held"] else "NOT HELD"
    print(f"{report['jurisdiction']}: CCDF plan text {verdict}")
    for entry in report["scopes"]:
        marks = [entry["subfamily"] or "unclassified"]
        marks.append("locked" if entry["locked"] else "UNLOCKED")
        marks.append("signed" if entry["signed"] else "UNSIGNED")
        marks.append("fetched" if entry["fetched"] else "not fetched")
        if entry.get("unverified"):
            marks.append("NO LOCK AND NO BYTES")
        count = entry["citation_path_count"]
        if count is None:
            count = entry["provision_count"]
            suffix = " provisions (from the signed ingest manifest)"
        else:
            suffix = " citation paths under the family root"
        print(f"  {entry['scope']}  [{', '.join(marks)}]  {count}{suffix}")
    for variant in report["variant_citation_paths"]:
        print(f"  variant spelling, not counted as plan text: {variant}")
    if report["plan_text_held"]:
        print(
            "  Do not fetch or extract this plan before reading those scopes: a new "
            "scope writing the same citation paths collides with them."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "jurisdiction",
        nargs="?",
        help="jurisdiction code, for example us-mo; omit to report every jurisdiction "
        "the CCDF queue lists",
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument(
        "--exit-code",
        action="store_true",
        help="exit 1 when the plan text is already held, for use as a pre-fetch gate",
    )
    args = parser.parse_args()

    if args.jurisdiction:
        jurisdictions = [args.jurisdiction]
    else:
        with (args.repo_root / QUEUE).open(encoding="utf-8") as handle:
            queue = yaml.safe_load(handle) or {}
        jurisdictions = sorted(
            {
                str(row.get("jurisdiction"))
                for row in queue.get("states") or []
                if row.get("jurisdiction") not in (None, "us")
            }
        )

    reports = [holdings(args.repo_root, jurisdiction) for jurisdiction in jurisdictions]
    if args.json:
        print(json.dumps(reports if len(reports) > 1 else reports[0], indent=2))
    else:
        for report in reports:
            _print_report(report)
    if args.exit_code and any(report["plan_text_held"] for report in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
