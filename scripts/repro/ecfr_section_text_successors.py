#!/usr/bin/env python3
"""Refresh section text in two assembled scopes from their locked source bytes.

Fetch each predecessor first, then run this script from the repository root:

    uv run python scripts/repro/ecfr_section_text_successors.py --key recovery
    uv run python scripts/repro/ecfr_section_text_successors.py --key 26-1

These scopes combine captures and retained row choices that one native extraction
cannot reproduce. Keep every raw row and source byte, move version-bearing fields,
and render only section bodies. Recovery applies the precise #832 rendering delta
and retains its fourteen known earlier-extractor omissions. The 26-1 successor
renders every section from the particular locked snapshot that supplied its row.
The script neither signs nor locks nor uploads its output.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

from axiom_corpus.corpus import ecfr
from axiom_corpus.corpus.corpus_locks import LockEntry, parse_lock
from axiom_corpus.corpus.ecfr import (
    _section_body,
    _section_citation_from_element,
    _section_heading,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "de81c43afd87bacb828b193a59e98b0439561e50"
BASELINE_SOURCE = "src/axiom_corpus/corpus/ecfr.py"
BASELINE_SOURCE_SHA256 = "5439c5a61e2646be10f8a1c26b4423d370088a9fbcb9ca411090373ebb250fe2"
REVISION = "r2026-10-29-ecfr-section-text"
_RECOVERY = "2026-07-13-recovery-r2026-07-17-dedup"
_TITLE_26 = (
    "2026-07-24-1401-coordination-repair-title-26-part-1-"
    "r2026-09-13-closure-sections-consolidated-r2026-10-07-w6-1-414-consolidated"
)
SCOPES = {
    "recovery": {"old": _RECOVERY, "new": f"{_RECOVERY}-{REVISION}"},
    "26-1": {"old": _TITLE_26, "new": f"{_TITLE_26}-{REVISION}"},
}
INHERITED_RECOVERY_DRIFT = {
    "us/regulation/42/457/608",
    "us/regulation/42/457/618",
    "us/regulation/42/457/628",
    "us/regulation/7/246/2",
    "us/regulation/7/246/4",
    "us/regulation/7/246/7",
    "us/regulation/7/246/16",
    "us/regulation/7/247/8",
    "us/regulation/7/247/9",
    "us/regulation/7/273/1",
    "us/regulation/7/273/11",
    "us/regulation/7/273/12",
    "us/regulation/7/273/13",
    "us/regulation/7/273/21",
}
EXPECTED = {
    "recovery": {"us/regulation/42/457/555", "us/regulation/7/246/10"},
    "26-1": {
        f"us/regulation/26/1/{section}"
        for section in (
            "36B-3", "36B-4", "163-2", "163-j-2", "163-j-5", "163-j-6",
            "170A-10", "170A-12", "199A-6", "401-k-1", "401-k-2", "401-l-2",
            "401-l-3", "401-l-4", "401-m-2", "404-a-13", "1016-3", "1411-3",
            "414-c-2", "414-c-4", "414-l-1",
        )
    },
}


def _require(condition: bool, message: str) -> None:
    """Keep integrity checks active when Python runs with optimization enabled."""
    if not condition:
        raise ValueError(message)


def rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def rewrite(value: Any, old: str, new: str) -> Any:
    """Move version values and exact scope-source prefixes, including image refs."""
    if isinstance(value, dict):
        return {key: rewrite(child, old, new) for key, child in value.items()}
    if isinstance(value, list):
        return [rewrite(child, old, new) for child in value]
    if isinstance(value, str):
        if value == old:
            return new
        return value.replace(f"sources/us/regulation/{old}/", f"sources/us/regulation/{new}/")
    return value


def pre832_renderer() -> Callable[[ET.Element], str]:
    """Extract exactly three renderer functions from hash-pinned git history.

    All other dependencies come from the current ecfr module. A missing commit,
    mismatched source digest or unexpected AST fails before any successor writes.
    No historical package is imported and no network fallback runs.
    """
    reference = f"{BASELINE_COMMIT}:{BASELINE_SOURCE}"
    try:
        result = subprocess.run(
            ["git", "show", reference],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"cannot read pinned pre-#832 renderer from git: {reference}") from exc
    _require(
        hashlib.sha256(result.stdout).hexdigest() == BASELINE_SOURCE_SHA256,
        "pre832 renderer source digest differs",
    )
    names = {"_section_body", "_table_text", "_element_text_with_breaks"}
    tree = ast.parse(result.stdout.decode("utf-8"), filename=reference)
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    _require(
        len(functions) == 3 and {node.name for node in functions} == names,
        "baseline renderer functions missing or duplicated",
    )
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *functions], type_ignores=[]))
    namespace = dict(vars(ecfr))
    exec(compile(module, reference, "exec"), namespace)
    return cast(Callable[[ET.Element], str], namespace["_section_body"])


def _locked_files(base: Path, lock_dir: Path, old: str) -> dict[str, LockEntry]:
    path = lock_dir / "us" / "regulation" / f"{old}.json"
    lock = parse_lock(path.read_bytes(), source=str(path))
    _require(lock.scope == ("us", "regulation", old), "predecessor lock scope differs")
    locked: dict[str, LockEntry] = {}
    for entry in lock.files:
        relative = Path(entry.path).relative_to("data/corpus").as_posix()
        retained = base / relative
        _require(
            retained.stat().st_size == entry.size and digest(retained) == entry.sha256,
            f"locked file differs: {retained}",
        )
        locked[relative] = entry
    for category, suffix in (("provisions", ".jsonl"), ("inventory", ".json"), ("coverage", ".json")):
        _require(
            f"{category}/us/regulation/{old}{suffix}" in locked,
            f"predecessor lock lacks {category}",
        )
    return locked


def reconstruct(
    key: str,
    *,
    base: Path = Path("data/corpus"),
    lock_dir: Path = Path(".axiom/corpus-locks"),
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Write one guarded successor and return its JSON-compatible comparison report."""
    if key not in SCOPES:
        raise ValueError(f"unknown assembled successor key: {key}")
    config = SCOPES[key]
    old, new = config["old"], config["new"]
    targets = {
        "provisions": base / f"provisions/us/regulation/{new}.jsonl",
        "inventory": base / f"inventory/us/regulation/{new}.json",
        "coverage": base / f"coverage/us/regulation/{new}.json",
        "sources": base / f"sources/us/regulation/{new}",
    }
    _require(not any(path.exists() for path in targets.values()), "successor output already exists")
    locked_files = _locked_files(base, lock_dir, old)
    original = rows(base / f"provisions/us/regulation/{old}.jsonl")
    by_path = {row["citation_path"]: row for row in original}
    _require(len(by_path) == len(original), "predecessor has duplicate citations")
    inventory = json.loads((base / f"inventory/us/regulation/{old}.json").read_text())
    _require(
        Counter(item["citation_path"] for item in inventory["items"]) == Counter(by_path.keys()),
        "inventory differs",
    )
    for item in inventory["items"]:
        source = item.get("source_path")
        _require(source in locked_files, f"inventory source is not locked: {source}")
        _require(
            item.get("sha256") == locked_files[source].sha256,
            f"inventory source hash differs: {item['citation_path']}",
        )
        _require(
            by_path[item["citation_path"]].get("source_path") == source,
            f"provision/inventory source differs: {item['citation_path']}",
        )

    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    preserved_placeholders = []
    for row in original:
        metadata = row.get("metadata") or {}
        if metadata.get("structure_only"):
            _require(
                row.get("body") is None,
                f"structure-only row unexpectedly has body: {row['citation_path']}",
            )
            _require(
                metadata.get("body_status") == "not_in_ecfr_full_xml",
                f"unknown structure-only status: {row['citation_path']}",
            )
            preserved_placeholders.append({
                "citation_path": row["citation_path"],
                "body_status": metadata["body_status"],
                "source_path": row.get("source_path"),
                "preserved": True,
            })
            continue
        if row.get("source_format") == "ecfr-xml" and row.get("kind") == "section":
            source = row["source_path"]
            _require(source in locked_files, f"row source is not locked: {source}")
            _require(source.endswith(".xml"), f"row source is not XML: {source}")
            pieces = row["citation_path"].split("/")
            groups[(source, int(pieces[2]), pieces[3])].append(row)

    parsed: dict[str, Any] = {}
    source_report = []
    inherited_drift = []
    rendering_delta: set[str] = set()
    baseline_renderer = pre832_renderer() if key == "recovery" else None
    for (source, title, part), selected in sorted(groups.items()):
        allowed = {row["citation_path"] for row in selected}
        # Preserve each row's capture dates in scopes assembled from several XMLs.
        dates = {(row.get("source_as_of"), row.get("expression_date")) for row in selected}
        _require(len(dates) == 1, f"mixed dates within one XML source: {source}")
        as_of, expression = dates.pop()
        root = ET.parse(base / source).getroot()
        matched = {}
        # Direct rendering retains reserved rows current native inventory skips.
        for element in root.iter("DIV8"):
            identity = _section_citation_from_element(title, element, part)
            if identity is None or identity[0] not in allowed:
                continue
            citation, actual_part, section = identity
            _require(citation not in matched, f"duplicate section in XML: {citation}")
            before = baseline_renderer(element) if baseline_renderer else None
            matched[citation] = (
                _section_body(element), _section_heading(element, actual_part, section), before
            )
        _require(
            set(matched) == allowed,
            f"XML identity mismatch: {source}: {sorted(allowed - set(matched))}",
        )
        for row in selected:
            citation = row["citation_path"]
            body, heading, before = matched[citation]
            _require(row.get("heading") == heading, f"heading drift: {citation}")
            if baseline_renderer:
                before = cast(str, before)
                if before != body:
                    rendering_delta.add(citation)
                    _require(
                        row.get("body") == before,
                        f"changed section is not pre832-equivalent: {citation}",
                    )
                    parsed[citation] = body
                else:
                    parsed[citation] = row.get("body")
                    if row.get("body") != before:
                        inherited_drift.append({
                            "citation_path": citation,
                            "source_path": source,
                            "locked_body_sha256": hashlib.sha256(row["body"].encode()).hexdigest(),
                            "pre832_body_sha256": hashlib.sha256(before.encode()).hexdigest(),
                            "main_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                            "locked_chars": len(row["body"]),
                            "pre832_chars": len(before),
                            "main_chars": len(body),
                            "preserved": True,
                            "pre832_equals_main": True,
                        })
            else:
                parsed[citation] = body
        source_report.append({
            "source_path": source,
            "sha256": locked_files[source].sha256,
            "selected_section_rows": len(selected),
            "source_as_of": as_of,
            "expression_date": expression,
        })
    if baseline_renderer:
        _require(
            rendering_delta == EXPECTED[key],
            f"unexpected #832 delta: {sorted(rendering_delta)}",
        )
        _require(
            {row["citation_path"] for row in inherited_drift} == INHERITED_RECOVERY_DRIFT,
            "inherited recovery drift set changed",
        )
    changed = {path for path, body in parsed.items() if by_path[path].get("body") != body}
    _require(
        changed == EXPECTED[key],
        f"unexpected body changes: actual={sorted(changed)}, expected={sorted(EXPECTED[key])}",
    )
    for row in original:
        if row.get("kind") == "paragraph":
            _require(
                row.get("parent_citation_path") not in changed
                and not any(row["citation_path"].startswith(path + "/") for path in changed),
                "paragraph must be regenerated with changed parent body",
            )

    updated = []
    for row in original:
        result = rewrite(deepcopy(row), old, new)
        result["version"] = new
        for field, citation in (
            ("id", result["citation_path"]), ("parent_id", result.get("parent_citation_path"))
        ):
            if not citation or field not in result or not result[field]:
                continue
            if result[field] == deterministic_provision_id(citation):
                pass  # Keep historical path-only identities.
            elif result[field] == deterministic_provision_id(citation, old):
                result[field] = deterministic_provision_id(citation, new)
            else:
                raise ValueError(f"unknown {field} scheme: {result['citation_path']}: {result[field]}")
        if row["citation_path"] in parsed:
            result["body"] = parsed[row["citation_path"]]
        updated.append(result)

    # Copy only locked sources; never carry an extra local file into a successor.
    source_prefix = f"sources/us/regulation/{old}/"
    for relative in locked_files:
        if relative.startswith(source_prefix):
            target = base / rewrite(relative, old, new)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base / relative, target)
    for category in ("provisions", "inventory", "coverage"):
        targets[category].parent.mkdir(parents=True, exist_ok=True)
    targets["provisions"].write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in updated),
        encoding="utf-8",
    )
    new_inventory = rewrite(inventory, old, new)
    targets["inventory"].write_text(
        json.dumps(new_inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    coverage = rewrite(
        json.loads((base / f"coverage/us/regulation/{old}.json").read_text()), old, new
    )
    targets["coverage"].write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")
    for relative, entry in locked_files.items():
        if relative.startswith(source_prefix):
            target = base / rewrite(relative, old, new)
            _require(
                target.stat().st_size == entry.size and digest(target) == entry.sha256,
                f"copied source byte drift: {target}",
            )
    missing = [
        {"citation_path": row["citation_path"], "parent": row["parent_citation_path"]}
        for row in updated
        if row.get("parent_citation_path") not in (None, "")
        and row["parent_citation_path"] not in by_path
    ]
    report = {
        "key": key,
        "old": old,
        "new": new,
        "recipe": "locked-byte section-body refresh with main _section_body and _section_citation_from_element",
        "row_count": len(updated),
        "rendered_section_rows": len(parsed),
        "body_changed_count": len(changed),
        "body_changed_paths": sorted(changed),
        "inherited_parent_residuals": missing,
        "sources": source_report,
        "inherited_rendering_drift": inherited_drift,
        "preserved_structure_only_rows": preserved_placeholders,
        "pre832_baseline": {
            "commit": BASELINE_COMMIT,
            "source_path": BASELINE_SOURCE,
            "source_sha256": BASELINE_SOURCE_SHA256,
            "delta_paths": sorted(rendering_delta),
        } if baseline_renderer else None,
        "artifacts": {category: str(path) for category, path in targets.items()},
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, choices=tuple(SCOPES))
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--lock-dir", type=Path, default=Path(".axiom/corpus-locks"))
    parser.add_argument("--report", type=Path, help="Also write the JSON report to this path; it always prints to stdout.")
    args = parser.parse_args()
    report = reconstruct(args.key, base=args.base, lock_dir=args.lock_dir, report_path=args.report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
