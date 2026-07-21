#!/usr/bin/env python3
"""Build one source-complete Canadian RuleSpec program scope."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.consolidate_release_scopes import consolidate_release_scopes


def _load_citation_contract(path: Path) -> tuple[str, ...]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "citation_paths" not in payload:
        raise ValueError("citation contract must contain citation_paths")
    raw_paths = payload["citation_paths"]
    if not isinstance(raw_paths, list) or not all(
        isinstance(value, str) and value for value in raw_paths
    ):
        raise ValueError("citation_paths must be a list of non-empty strings")
    paths = tuple(raw_paths)
    if len(paths) != len(set(paths)):
        raise ValueError("citation contract contains duplicate paths")
    return paths


def promote_program_roots(
    *,
    base: Path,
    version: str,
    citation_paths: tuple[str, ...],
) -> tuple[Path, Path, Path]:
    """Move each root body to a child so root resolution composes all documents."""

    store = CorpusArtifactStore(base)
    inventory_path = store.inventory_path("ca", "policy", version)
    provisions_path = store.provisions_path("ca", "policy", version)
    coverage_path = store.coverage_path("ca", "policy", version)
    inventory = list(load_source_inventory(inventory_path))
    provisions = list(load_provisions(provisions_path))
    inventory_by_path = {item.citation_path: item for item in inventory}
    provisions_by_path = {record.citation_path: record for record in provisions}

    missing = sorted(set(citation_paths) - provisions_by_path.keys())
    if missing:
        raise ValueError(f"composite scope is missing contracted roots: {missing}")

    promoted_inventory: dict[str, SourceInventoryItem] = dict(inventory_by_path)
    promoted_provisions: dict[str, ProvisionRecord] = dict(provisions_by_path)
    for citation_path in citation_paths:
        root = promoted_provisions[citation_path]
        child_path = f"{citation_path}/primary-document"
        if root.body is None or not root.body.strip():
            if not any(
                record.body is not None
                and bool(record.body.strip())
                and record.citation_path.startswith(f"{citation_path}/")
                for record in provisions
            ):
                raise ValueError(f"bodyless program root has no document: {citation_path}")
            if root.body is not None:
                promoted_provisions[citation_path] = replace(root, body=None)
            existing_child = promoted_provisions.get(child_path)
            if existing_child is not None and not (existing_child.body or "").strip():
                promoted_provisions.pop(child_path)
                promoted_inventory.pop(child_path, None)
            continue

        if child_path in promoted_provisions or child_path in promoted_inventory:
            raise ValueError(f"primary document path already exists: {child_path}")
        inventory_item = promoted_inventory[citation_path]
        promoted_inventory[child_path] = replace(
            inventory_item,
            citation_path=child_path,
        )
        promoted_provisions[citation_path] = replace(root, body=None)
        promoted_provisions[child_path] = replace(
            root,
            citation_path=child_path,
            id=deterministic_provision_id(child_path, version),
            parent_citation_path=citation_path,
            parent_id=deterministic_provision_id(citation_path, version),
            level=(root.level or 1) + 1,
            ordinal=1,
            kind="document",
        )

    ordered_inventory = tuple(
        promoted_inventory[path] for path in sorted(promoted_inventory)
    )
    ordered_provisions = tuple(
        promoted_provisions[path] for path in sorted(promoted_provisions)
    )
    coverage = compare_provision_coverage(
        ordered_inventory,
        ordered_provisions,
        "ca",
        "policy",
        version,
    )
    if not coverage.complete:
        raise ValueError("promoted composite scope does not have complete coverage")
    store.write_inventory(inventory_path, ordered_inventory)
    store.write_provisions(provisions_path, ordered_provisions)
    store.write_json(coverage_path, coverage.to_mapping())
    return inventory_path, provisions_path, coverage_path


def build_ca_rulespec_composite_scope(
    *,
    base: Path,
    selector_path: Path,
    citation_contract_path: Path,
    target_version: str,
    supplemental_versions: tuple[str, ...] = (),
    additional_citation_paths: tuple[str, ...] = (),
) -> tuple[Path, ...]:
    release = ReleaseManifest.load(selector_path)
    unexpected = sorted(
        scope.key
        for scope in release.scopes
        if scope.jurisdiction != "ca" or scope.document_class != "policy"
    )
    if unexpected:
        raise ValueError(f"selector contains non-Canadian-policy scopes: {unexpected}")
    contracted_paths = _load_citation_contract(citation_contract_path)
    citation_paths = (*contracted_paths, *additional_citation_paths)
    if len(citation_paths) != len(set(citation_paths)):
        raise ValueError("composite citation paths must be unique")
    source_versions = tuple(scope.version for scope in release.scopes)
    all_source_versions = (*source_versions, *supplemental_versions)
    if len(all_source_versions) != len({*all_source_versions}):
        raise ValueError("composite source versions must be unique")
    generated = consolidate_release_scopes(
        base=base,
        jurisdiction="ca",
        document_class="policy",
        source_versions=all_source_versions,
        target_version=target_version,
    )
    promote_program_roots(
        base=base,
        version=target_version,
        citation_paths=citation_paths,
    )
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--selector", type=Path, required=True)
    parser.add_argument("--citation-contract", type=Path, required=True)
    parser.add_argument("--target-version", required=True)
    parser.add_argument(
        "--supplemental-version",
        action="append",
        default=[],
        help="Additional ca/policy source version to compose (repeatable).",
    )
    parser.add_argument(
        "--additional-citation",
        action="append",
        default=[],
        help="Additional program-root citation outside the base contract (repeatable).",
    )
    args = parser.parse_args()
    generated = build_ca_rulespec_composite_scope(
        base=args.base,
        selector_path=args.selector,
        citation_contract_path=args.citation_contract,
        target_version=args.target_version,
        supplemental_versions=tuple(args.supplemental_version),
        additional_citation_paths=tuple(args.additional_citation),
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
