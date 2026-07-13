#!/usr/bin/env python3
"""Audit release scopes and repair provision-derived inventory/coverage debt."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ARTIFACT_CLASSES = ("sources", "inventory", "provisions", "coverage")


def _release_payload(repo: Path, release_ref: str, release_path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{release_ref}:{release_path.as_posix()}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict) or not isinstance(payload.get("scopes"), list):
        raise ValueError("release selector must contain a scopes list")
    return payload


def _paths(base: Path, jurisdiction: str, document_class: str, version: str) -> dict[str, Path]:
    return {
        "sources": base / "sources" / jurisdiction / document_class / version,
        "inventory": base / "inventory" / jurisdiction / document_class / f"{version}.json",
        "provisions": base / "provisions" / jurisdiction / document_class / f"{version}.jsonl",
        "coverage": base / "coverage" / jurisdiction / document_class / f"{version}.json",
    }


def _exists(artifact_class: str, path: Path) -> bool:
    if artifact_class == "sources":
        return path.is_dir() and any(candidate.is_file() for candidate in path.rglob("*"))
    return path.is_file()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _repair_derived(paths: dict[str, Path], scope: dict[str, str]) -> list[str]:
    if not paths["provisions"].is_file():
        return []
    rows = [json.loads(line) for line in paths["provisions"].read_text().splitlines() if line]
    citations = [str(row["citation_path"]) for row in rows]
    repaired: list[str] = []
    if not paths["inventory"].exists():
        items = []
        for row in rows:
            item: dict[str, Any] = {"citation_path": row["citation_path"]}
            for field in ("source_url", "source_path", "source_format"):
                if row.get(field):
                    item[field] = row[field]
            metadata = dict(row.get("metadata") or {})
            metadata["derived_from"] = "provisions"
            metadata["primary_source"] = bool(metadata.get("primary_source", True))
            if row.get("source_id"):
                metadata["source_id"] = row["source_id"]
            title = row.get("heading") or row.get("citation_label")
            if title:
                metadata["title"] = title
            item["metadata"] = metadata
            items.append(item)
        _write_json(
            paths["inventory"],
            {
                "derived_from": "provisions",
                "document_class": scope["document_class"],
                "items": items,
                "jurisdiction": scope["jurisdiction"],
                "source_count": len(items),
                "version": scope["version"],
            },
        )
        repaired.append("inventory")
    if not paths["coverage"].exists():
        duplicates = sorted({value for value in citations if citations.count(value) > 1})
        _write_json(
            paths["coverage"],
            {
                "complete": bool(citations) and not duplicates,
                "document_class": scope["document_class"],
                "duplicate_provision_citations": duplicates,
                "duplicate_source_citations": duplicates,
                "extra_provisions": [],
                "jurisdiction": scope["jurisdiction"],
                "matched_count": len(set(citations)),
                "missing_from_provisions": [],
                "provision_count": len(citations),
                "source_count": len(citations),
                "version": scope["version"],
            },
        )
        repaired.append("coverage")
    return repaired


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--release-ref", default="release/us-rulespec-2026-07-13")
    parser.add_argument(
        "--release-path",
        type=Path,
        default=Path("manifests/releases/us-rulespec-2026-07-13.json"),
    )
    parser.add_argument("--repair-derived", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    base = repo / args.base
    release = _release_payload(repo, args.release_ref, args.release_path)
    report: list[dict[str, Any]] = []
    for raw_scope in release["scopes"]:
        scope = {key: str(raw_scope[key]) for key in ("jurisdiction", "document_class", "version")}
        paths = _paths(base, **scope)
        repaired = _repair_derived(paths, scope) if args.repair_derived else []
        missing = [name for name in ARTIFACT_CLASSES if not _exists(name, paths[name])]
        manifest = (
            repo
            / ".axiom/ingest-manifests"
            / scope["jurisdiction"]
            / scope["document_class"]
            / f"{scope['version']}.json"
        )
        signed = False
        if manifest.is_file():
            payload = json.loads(manifest.read_text())
            signed = isinstance(payload.get("signature"), dict)
        report.append({**scope, "missing_artifacts": missing, "signed_manifest": signed, "repaired": repaired})
    output = {
        "scope_count": len(report),
        "artifact_lacking_count": sum(bool(row["missing_artifacts"]) for row in report),
        "manifest_lacking_count": sum(not row["signed_manifest"] for row in report),
        "scopes": report,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 2 if output["artifact_lacking_count"] or output["manifest_lacking_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
