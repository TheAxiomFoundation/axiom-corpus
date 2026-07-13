#!/usr/bin/env python3
"""Build the audited RuleSpec-US source-promotion classification manifest.

This tool is deliberately offline.  It may widen a release to an existing corpus
scope, but it never turns RuleSpec excerpts or an encoder cache into corpus text.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULESPEC_ROOT = ROOT.parent / "rulespec-us"
RULESPEC_COMMIT = "8a35bfaceb5754a38c111f4f246e69891de6c2d3"
VERSION = "2026-07-13-us-rulespec-source-promotion"
GAPS_PATH = ROOT / "us-coverage-gaps.txt"
OUTPUT_PATH = ROOT / "manifests/migrations/rulespec-us-source-promotion.json"
CACHE_ROOT = Path("/Users/maxghenis/TheAxiomFoundation/_bulk_drain/wt")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gaps() -> list[str]:
    marker = "Exact unresolved corpus_citation_path values:\n"
    text = GAPS_PATH.read_text(encoding="utf-8")
    return [line.strip() for line in text.split(marker, 1)[1].splitlines() if line.strip()]


def input_coverage_counts() -> dict[str, int]:
    text = GAPS_PATH.read_text(encoding="utf-8")
    counts = {
        key.replace(" ", "_"): int(value)
        for key, value in re.findall(r"^(total citations|resolved|unresolved): (\d+)$", text, re.M)
    }
    if counts != {"total_citations": 2968, "resolved": 2257, "unresolved": 711}:
        raise SystemExit(f"unexpected input coverage counts: {counts}")
    return counts


def corpus_matches(
    wanted: set[str],
) -> tuple[dict[str, list[dict[str, object]]], dict[str, list[dict[str, object]]]]:
    matches: dict[str, list[dict[str, object]]] = {}
    placeholders: dict[str, list[dict[str, object]]] = {}
    for path in sorted((ROOT / "data/corpus/provisions").glob("*/*/*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            citation = row.get("citation_path")
            if citation not in wanted:
                continue
            relative = path.relative_to(ROOT).as_posix()
            match = {
                    "artifact_path": relative,
                    "artifact_line": line_number,
                    "row_sha256": sha256(
                        json.dumps(
                            row, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                        ).encode()
                    ),
                    "scope": {
                        "jurisdiction": path.parts[-3],
                        "document_class": path.parts[-2],
                        "version": path.stem,
                    },
                }
            target = matches if isinstance(row.get("body"), str) and row["body"] else placeholders
            target.setdefault(str(citation), []).append(match)
    return matches, placeholders


def rulespec_tracked_source_candidates() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(RULESPEC_ROOT), "ls-tree", "-r", "--name-only", RULESPEC_COMMIT],
        check=True,
        text=True,
        capture_output=True,
    )
    candidates = []
    for path in result.stdout.splitlines():
        lower = path.lower()
        if lower == ".axiom/upstream-source-check-baseline.txt":
            continue
        if lower.endswith((".jsonl", ".txt", ".html", ".htm", ".pdf", ".xml")) and (
            "source" in lower or lower.startswith(("data/", "bulk/"))
        ):
            candidates.append(path)
    return candidates


def retained_cache_snapshots(wanted: set[str]) -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    if not CACHE_ROOT.is_dir():
        return found
    for metadata_path in CACHE_ROOT.glob(
        "*/encode-out/_eval_workspaces/*/*/workspace/source-metadata.json"
    ):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        citation = metadata.get("corpus_citation_path")
        source_path = metadata_path.with_name("source.txt")
        if citation not in wanted or not source_path.is_file():
            continue
        source_bytes = source_path.read_bytes()
        found[str(citation)] = {
            "cache_source_sha256": sha256(source_bytes),
            "cache_source_bytes": len(source_bytes),
            "reason": (
                "Encoder cache text exists outside rulespec-us, but its metadata only says "
                "corpus_source=supabase and carries neither the official source URL nor a "
                "retained official raw artifact; external official-source recovery is required."
            ),
        }
    return found


def main() -> None:
    gap_list = gaps()
    wanted = set(gap_list)
    if len(gap_list) != 711 or len(wanted) != 711:
        raise SystemExit("expected exactly 711 unique gap citations")

    tracked_candidates = rulespec_tracked_source_candidates()
    if tracked_candidates:
        raise SystemExit(f"unexpected tracked RuleSpec source candidates: {tracked_candidates[:5]}")
    existing, placeholders = corpus_matches(wanted)
    cache = retained_cache_snapshots(wanted)
    widening = sorted(existing)
    absent = sorted(wanted - set(existing))
    scopes = sorted(
        {tuple(match["scope"].values()) for values in existing.values() for match in values}
    )

    entries = []
    for citation in gap_list:
        if citation in existing:
            entries.append(
                {
                    "citation_path": citation,
                    "classification": "widen_existing_scope",
                    "matches": existing[citation],
                }
            )
        else:
            entry: dict[str, object] = {
                "citation_path": citation,
                "classification": "external_fetch_required",
                "reason": "No promotable official-source snapshot is tracked in rulespec-us.",
            }
            if citation in cache:
                entry["encoder_cache_observation"] = cache[citation]
            if citation in placeholders:
                entry["bodyless_corpus_placeholders"] = placeholders[citation]
                entry["reason"] = (
                    "Only bodyless document inventory rows exist in corpus; they cannot satisfy "
                    "a source-text citation. No promotable official-source snapshot is tracked "
                    "in rulespec-us."
                )
            entries.append(entry)

    payload = {
        "schema_version": "axiom-corpus/source-promotion/v1",
        "migration": VERSION,
        "source": {
            "rulespec_repository": "https://github.com/TheAxiomFoundation/rulespec-us",
            "rulespec_commit": RULESPEC_COMMIT,
            "gap_inventory": GAPS_PATH.relative_to(ROOT).as_posix(),
            "gap_inventory_sha256": sha256(GAPS_PATH.read_bytes()),
        },
        "preservation_contract": (
            "Promote only a tracked official-source snapshot with sufficient provenance to "
            "preserve its exact body and source URL. RuleSpec summaries/excerpts and unprovenanced "
            "encoder caches are not source snapshots."
        ),
        "coverage_verification": {
            **input_coverage_counts(),
            "post_migration_resolved": 2257 + len(widening),
            "post_migration_unresolved": len(absent),
            "method": (
                "Reclassified every exact unresolved citation against all tracked provision "
                "versions; only nonempty provision bodies count as resolved."
            ),
        },
        "counts": {
            "total": len(gap_list),
            "promotable_repo_local_snapshot": 0,
            "widen_existing_scope": len(widening),
            "external_fetch_required": len(absent),
            "external_fetch_with_unprovenanced_encoder_cache_text": len(cache),
            "external_fetch_without_retained_text": len(absent) - len(cache),
            "external_fetch_with_bodyless_corpus_placeholder": len(placeholders),
            "widened_scopes": len(scopes),
        },
        "rulespec_source_audit": {
            "tracked_source_candidate_count": len(tracked_candidates),
            "tracked_source_candidates": tracked_candidates,
            "git_object_search": "git ls-tree -r --name-only at the pinned RuleSpec commit",
        },
        "scope_additions": [
            {"jurisdiction": j, "document_class": c, "version": v} for j, c, v in scopes
        ],
        "classification_by_jurisdiction_and_class": {
            f"{classification}:{jurisdiction}/{document_class}": count
            for (classification, jurisdiction, document_class), count in sorted(
                Counter(
                    (
                        entry["classification"],
                        str(entry["citation_path"]).split("/")[0],
                        str(entry["citation_path"]).split("/")[1],
                    )
                    for entry in entries
                ).items()
            )
        },
        "entries": entries,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
