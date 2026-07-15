#!/usr/bin/env python3
"""Repair a publisher conflict plan into fresh, self-contained release scopes.

The conflict plan is publisher evidence, not a corpus artifact.  This command
only reads it and fails closed unless every conflict can be assigned either to
its immutable release scope or to a release scope which owns the legacy parent
whose replacement would cascade outside the load.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.supabase import deterministic_provision_id

ARTIFACT_KINDS = ("coverage", "inventory", "provisions", "sources")
DEFAULT_SUFFIX = "r2026-07-15-self-contained"


def _json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _scope_prefix(scope: tuple[str, str, str]) -> str:
    return f"{scope[0]}/{scope[1]}"


def _scope_paths(base: Path, scope: tuple[str, str, str]) -> dict[str, Path]:
    jurisdiction, document_class, version = scope
    return {
        "coverage": base / "coverage" / jurisdiction / document_class / f"{version}.json",
        "inventory": base / "inventory" / jurisdiction / document_class / f"{version}.json",
        "provisions": base / "provisions" / jurisdiction / document_class / f"{version}.jsonl",
        "sources": base / "sources" / jurisdiction / document_class / version,
    }


def _release_scopes(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [
        (str(row["jurisdiction"]), str(row["document_class"]), str(row["version"]))
        for row in payload["scopes"]
    ]


def _direct_scope(
    conflict: dict[str, Any], scopes: list[tuple[str, str, str]]
) -> tuple[str, str, str] | None:
    matches = [
        scope
        for scope in scopes
        if scope[2] == conflict["version"]
        and (
            conflict["citation_path"] == _scope_prefix(scope)
            or conflict["citation_path"].startswith(_scope_prefix(scope) + "/")
        )
    ]
    if len(matches) > 1:
        raise ValueError(f"ambiguous direct conflict scope: {conflict}")
    return matches[0] if matches else None


def _artifact_index(
    base: Path, scopes: list[tuple[str, str, str]]
) -> tuple[
    dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
    dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
]:
    by_path: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]] = defaultdict(list)
    by_legacy_id: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]] = defaultdict(list)
    for scope in scopes:
        for row in _rows(_scope_paths(base, scope)["provisions"]):
            by_path[str(row["citation_path"])].append((scope, row))
            legacy_ids = {
                str(row.get("id") or ""),
                deterministic_provision_id(str(row["citation_path"])),
            }
            for legacy_id in legacy_ids - {""}:
                by_legacy_id[legacy_id].append((scope, row))
    return by_path, by_legacy_id


def _choose_parent_template(
    citation_path: str,
    scope: tuple[str, str, str],
    child: dict[str, Any],
    by_path: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
) -> dict[str, Any]:
    candidates = by_path.get(citation_path, [])
    if candidates:
        same_kind = [row for candidate_scope, row in candidates if candidate_scope[:2] == scope[:2]]
        if same_kind:
            parent = deepcopy(same_kind[0])
            # Templates from another scope may carry historical explicit ids.
            # A newly materialized container and all of its children use the
            # canonical citation-derived identity together.
            parent["id"] = deterministic_provision_id(citation_path)
            return parent
    level = max(0, int(child.get("level") or 1) - 1)
    label = citation_path.rsplit("/", 1)[-1]
    parent_path = citation_path.rsplit("/", 1)[0] if level else None
    row = deepcopy(child)
    row.update(
        {
            "body": None,
            "citation_label": label,
            "citation_path": citation_path,
            "heading": label,
            "id": deterministic_provision_id(citation_path),
            "kind": "container",
            "level": level,
            "ordinal": 0,
        }
    )
    row.pop("source_id", None)
    if parent_path and parent_path.startswith(_scope_prefix(scope)):
        row["parent_citation_path"] = parent_path
        row["parent_id"] = deterministic_provision_id(parent_path)
    else:
        row.pop("parent_citation_path", None)
        row.pop("parent_id", None)
    metadata = dict(row.get("metadata") or {})
    metadata.update({"kind": "container", "self_containment_container": True})
    row["metadata"] = metadata
    return row


def _close_scope(
    scope: tuple[str, str, str],
    rows: list[dict[str, Any]],
    by_path: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], int]:
    existing = {str(row["citation_path"]): row for row in rows}
    added = 0
    while True:
        missing = sorted(
            {
                str(row["parent_citation_path"])
                for row in existing.values()
                if row.get("parent_citation_path")
                and str(row["parent_citation_path"]) not in existing
            }
        )
        if not missing:
            break
        for parent_path in missing:
            child = next(
                row for row in existing.values() if row.get("parent_citation_path") == parent_path
            )
            parent = _choose_parent_template(parent_path, scope, child, by_path)
            canonical_parent_id = deterministic_provision_id(parent_path)
            parent["id"] = canonical_parent_id
            metadata = dict(parent.get("metadata") or {})
            metadata["self_containment_container"] = True
            parent["metadata"] = metadata
            for candidate in existing.values():
                if candidate.get("parent_citation_path") == parent_path:
                    candidate["parent_id"] = canonical_parent_id
            parent["jurisdiction"], parent["document_class"], parent["version"] = scope
            existing[parent_path] = parent
            added += 1
    ordered = sorted(
        existing.values(),
        key=lambda row: (int(row.get("level") or 0), int(row.get("ordinal") or 0), row["citation_path"]),
    )
    return ordered, added


def _inventory_item(row: dict[str, Any], template: dict[str, Any] | None = None) -> dict[str, Any]:
    if template is not None:
        item = deepcopy(template)
        item["citation_path"] = row["citation_path"]
        return item
    item: dict[str, Any] = {"citation_path": row["citation_path"]}
    for field in ("source_url", "source_path", "source_format"):
        if row.get(field):
            item[field] = row[field]
    metadata = dict(row.get("metadata") or {})
    metadata["derived_from"] = "provisions"
    metadata["primary_source"] = bool(metadata.get("primary_source", True))
    if row.get("source_id"):
        metadata["source_id"] = row["source_id"]
    metadata.setdefault("title", row.get("heading") or row.get("citation_label"))
    item["metadata"] = metadata
    return item


def _rewrite_value(value: Any, old_version: str, new_version: str) -> Any:
    if isinstance(value, str):
        if value == old_version:
            return value
        return value.replace(old_version, new_version)
    if isinstance(value, list):
        return [_rewrite_value(item, old_version, new_version) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_value(item, old_version, new_version) for key, item in value.items()}
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_manifest(
    repo: Path,
    old_scope: tuple[str, str, str],
    new_scope: tuple[str, str, str],
) -> None:
    root = repo / ".axiom" / "ingest-manifests"
    old = root / old_scope[0] / old_scope[1] / f"{old_scope[2]}.json"
    new = root / new_scope[0] / new_scope[1] / f"{new_scope[2]}.json"
    payload = _rewrite_value(_json(old), old_scope[2], new_scope[2])
    payload["version"] = new_scope[2]
    payload.pop("signature", None)
    paths = _scope_paths(repo / "data/corpus", new_scope)
    files = sorted(path for path in paths["sources"].rglob("*") if path.is_file())
    files += [paths["inventory"], paths["provisions"], paths["coverage"]]
    payload["applied_files"] = [
        {"path": path.relative_to(repo).as_posix(), "sha256": _sha(path)} for path in sorted(files)
    ]
    new.parent.mkdir(parents=True, exist_ok=True)
    _write_json(new, payload)
    if new != old:
        old.unlink()


def _rename_sources(old: Path, new: Path, old_version: str, new_version: str) -> None:
    if new.exists():
        raise FileExistsError(new)
    shutil.move(old, new)
    for path in sorted(new.rglob("*"), reverse=True):
        if old_version not in path.name:
            continue
        path.rename(path.with_name(path.name.replace(old_version, new_version)))
    for path in new.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        replaced = text.replace(old_version, new_version)
        if replaced != text:
            path.write_text(replaced)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conflicts", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--release", type=Path, default=Path("manifests/releases/us-rulespec-2026-07-13.json"))
    parser.add_argument("--suffix", default=DEFAULT_SUFFIX)
    parser.add_argument("--report", type=Path, default=Path("/tmp/cascade-self-containment-report.json"))
    args = parser.parse_args()
    repo = args.repo.resolve()
    base = repo / "data/corpus"
    release_path = repo / args.release
    release = _json(release_path)
    scopes = _release_scopes(release)
    conflicts = _json(args.conflicts)
    if not isinstance(conflicts, list) or len(conflicts) != 27849:
        raise ValueError("expected the complete 27,849-row publisher conflict plan")
    by_path, by_legacy_id = _artifact_index(base, scopes)

    repair: set[tuple[str, str, str]] = set()
    assigned = 0
    cascade_parent_paths: dict[str, str] = {}
    for conflict in conflicts:
        direct = _direct_scope(conflict, scopes)
        if direct is not None:
            repair.add(direct)
            assigned += 1
            continue
        if conflict.get("kind") != "cascade-outside-load":
            raise ValueError(f"unassigned non-cascade conflict: {conflict}")
        owners = {scope for scope, _row in by_legacy_id.get(conflict["staged_parent_id"], [])}
        if owners:
            repair.update(owners)
            assigned += 1
            continue
        inferred_parent = str(conflict["citation_path"]).rsplit("/", 1)[0]
        cascade_parent_paths[str(conflict["staged_parent_id"])] = inferred_parent
        inferred = {
            scope
            for scope, row in by_path.get(inferred_parent, [])
            if scope in scopes
        } | {
            scope
            for scope in scopes
            if any(
                row.get("parent_citation_path") == inferred_parent
                for _candidate_scope, row in by_path.get(str(conflict["citation_path"]), [])
                if _candidate_scope == scope
            )
        }
        if not inferred:
            inferred = {
                scope
                for scope in scopes
                if scope[:2] == tuple(str(conflict["citation_path"]).split("/")[:2])
                and inferred_parent in by_path
            }
        if not inferred:
            # The legacy title container is absent from durable artifacts.  All
            # release scopes containing children of that title must be closed.
            inferred = {
                scope
                for scope in scopes
                if any(
                    candidate_scope == scope and row.get("parent_citation_path") == inferred_parent
                    for candidates in by_path.values()
                    for candidate_scope, row in candidates
                )
            }
        if not inferred:
            raise ValueError(f"cannot assign cascade parent {conflict['staged_parent_id']}")
        repair.update(inferred)
        assigned += 1
    if assigned != len(conflicts):
        raise AssertionError(f"assigned {assigned}/{len(conflicts)} conflicts")

    mappings = {scope: (scope[0], scope[1], f"{scope[2]}-{args.suffix}") for scope in repair}
    total_added = 0
    for old_scope, new_scope in sorted(mappings.items()):
        old_paths = _scope_paths(base, old_scope)
        new_paths = _scope_paths(base, new_scope)
        old_inventory = _json(old_paths["inventory"])
        inventory_by_path = {
            str(item["citation_path"]): item for item in old_inventory.get("items", [])
        }
        rows, added = _close_scope(old_scope, _rows(old_paths["provisions"]), by_path)
        total_added += added
        _rename_sources(old_paths["sources"], new_paths["sources"], old_scope[2], new_scope[2])
        rows = _rewrite_value(rows, old_scope[2], new_scope[2])
        for row in rows:
            row["version"] = new_scope[2]
        _write_rows(new_paths["provisions"], rows)
        old_paths["provisions"].unlink()
        items = []
        for row in rows:
            template = inventory_by_path.get(str(row["citation_path"]))
            if template is None:
                child = next(
                    candidate
                    for candidate in rows
                    if candidate.get("parent_citation_path") == row["citation_path"]
                )
                template = inventory_by_path.get(str(child["citation_path"]))
                if template is None:
                    raise ValueError(f"no inventory template for added container {row['citation_path']}")
                for field in ("source_url", "source_path", "source_format"):
                    if child.get(field):
                        row[field] = child[field]
            items.append(_rewrite_value(_inventory_item(row, template), old_scope[2], new_scope[2]))
        _write_json(
            new_paths["inventory"],
            {
                "document_class": new_scope[1],
                "items": items,
                "jurisdiction": new_scope[0],
                "source_count": len(items),
                "version": new_scope[2],
            },
        )
        old_paths["inventory"].unlink()
        coverage = {
            "complete": True,
            "document_class": new_scope[1],
            "duplicate_provision_citations": [],
            "duplicate_source_citations": [],
            "extra_provisions": [],
            "jurisdiction": new_scope[0],
            "matched_count": len(rows),
            "missing_from_provisions": [],
            "provision_count": len(rows),
            "source_count": len(rows),
            "version": new_scope[2],
        }
        _write_json(new_paths["coverage"], coverage)
        old_paths["coverage"].unlink()
        _rewrite_manifest(repo, old_scope, new_scope)

    for row in release["scopes"]:
        old = (row["jurisdiction"], row["document_class"], row["version"])
        if old in mappings:
            row["version"] = mappings[old][2]
    _write_json(release_path, release)

    for path in (repo / "manifests").rglob("*.yaml"):
        text = path.read_text()
        for old, new in mappings.items():
            text = text.replace(f"version: {old[2]}", f"version: {new[2]}")
        path.write_text(text)
    signing = repo / "SIGNING-COMMANDS.md"
    text = signing.read_text()
    for old, new in mappings.items():
        text = text.replace(
            f"sign_scope {old[0]} {old[1]} {old[2]}",
            f"sign_scope {new[0]} {new[1]} {new[2]}",
        )
    signing.write_text(text)

    # Final local assertion: every repaired projection has its complete parent
    # closure, and every plan row was assigned to a freshly identified scope.
    for scope in mappings.values():
        rows = _rows(_scope_paths(base, scope)["provisions"])
        paths = {row["citation_path"] for row in rows}
        missing = [row["citation_path"] for row in rows if row.get("parent_citation_path") not in paths | {None}]
        if missing:
            raise AssertionError(f"scope {scope} still has missing parents: {missing[:5]}")
    report = {
        "assertion": f"PASS: {assigned}/{len(conflicts)} conflict rows assigned; all repaired parent closures complete",
        "conflict_rows": len(conflicts),
        "rows_added": total_added,
        "scopes_repaired": [list(scope) for scope in sorted(mappings.values())],
        "scopes_repaired_count": len(mappings),
        "cascade_parent_paths": cascade_parent_paths,
    }
    _write_json(args.report, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
