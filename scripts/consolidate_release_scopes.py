#!/usr/bin/env python3
"""Consolidate overlapping immutable scopes into one collision-free scope."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import replace
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id


def _rewritten_source_path(
    value: str | None,
    *,
    jurisdiction: str,
    document_class: str,
    source_version: str,
    target_version: str,
) -> str | None:
    if value is None:
        return None
    source_prefix = f"sources/{jurisdiction}/{document_class}/{source_version}/"
    if not value.startswith(source_prefix):
        raise ValueError(f"source_path is outside source scope {source_version}: {value}")
    relative = value[len(source_prefix) :]
    return f"sources/{jurisdiction}/{document_class}/{target_version}/{source_version}/{relative}"


def _is_structural_duplicate(first: ProvisionRecord, other: ProvisionRecord) -> bool:
    return (
        first.citation_path == other.citation_path
        and first.parent_citation_path == other.parent_citation_path
        and deterministic_provision_id(first.citation_path)
        == deterministic_provision_id(other.citation_path)
        and not (first.body or "").strip()
        and not (other.body or "").strip()
    )


def consolidate_release_scopes(
    *,
    base: Path,
    jurisdiction: str,
    document_class: str,
    source_versions: tuple[str, ...],
    target_version: str,
) -> tuple[Path, ...]:
    """Create one immutable scope from ordered sources, deduping empty containers."""
    if not source_versions:
        raise ValueError("at least one source version is required")
    if len(source_versions) != len(set(source_versions)):
        raise ValueError("source versions must be unique")
    if target_version in source_versions:
        raise ValueError("target version must differ from source versions")

    store = CorpusArtifactStore(base)
    target_inventory_path = store.inventory_path(jurisdiction, document_class, target_version)
    target_provisions_path = store.provisions_path(jurisdiction, document_class, target_version)
    target_coverage_path = store.coverage_path(jurisdiction, document_class, target_version)
    target_sources = store.root / "sources" / jurisdiction / document_class / target_version
    for path in (
        target_inventory_path,
        target_provisions_path,
        target_coverage_path,
        target_sources,
    ):
        if path.exists() or path.is_symlink():
            raise ValueError(f"target artifact already exists: {path}")

    inventory_by_citation: dict[str, SourceInventoryItem] = {}
    provisions_by_citation: dict[str, ProvisionRecord] = {}
    source_directories: list[tuple[str, Path]] = []
    for source_version in source_versions:
        inventory_path = store.inventory_path(jurisdiction, document_class, source_version)
        provisions_path = store.provisions_path(jurisdiction, document_class, source_version)
        source_directory = store.root / "sources" / jurisdiction / document_class / source_version
        for path in (inventory_path, provisions_path):
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"source artifact is not a regular file: {path}")
        if not source_directory.is_dir() or source_directory.is_symlink():
            raise ValueError(f"source directory is not regular: {source_directory}")
        if any(path.is_symlink() for path in source_directory.rglob("*")):
            raise ValueError(f"source directory contains a symlink: {source_directory}")
        source_directories.append((source_version, source_directory))

        for item in load_source_inventory(inventory_path):
            rewritten = replace(
                item,
                source_path=_rewritten_source_path(
                    item.source_path,
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    source_version=source_version,
                    target_version=target_version,
                ),
            )
            inventory_by_citation.setdefault(item.citation_path, rewritten)

        for record in load_provisions(provisions_path):
            previous = provisions_by_citation.get(record.citation_path)
            if previous is not None:
                if not _is_structural_duplicate(previous, record):
                    raise ValueError(f"conflicting duplicate citation_path: {record.citation_path}")
                continue
            provisions_by_citation[record.citation_path] = replace(
                record,
                version=target_version,
                id=deterministic_provision_id(record.citation_path, target_version),
                parent_id=(
                    deterministic_provision_id(record.parent_citation_path, target_version)
                    if record.parent_citation_path
                    else None
                ),
                source_path=_rewritten_source_path(
                    record.source_path,
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    source_version=source_version,
                    target_version=target_version,
                ),
            )

    inventory = tuple(inventory_by_citation.values())
    provisions = tuple(provisions_by_citation.values())
    if set(inventory_by_citation) != set(provisions_by_citation):
        missing = sorted(set(provisions_by_citation) - set(inventory_by_citation))
        extra = sorted(set(inventory_by_citation) - set(provisions_by_citation))
        raise ValueError(f"inventory/provision mismatch; missing={missing}, extra={extra}")
    coverage = compare_provision_coverage(
        inventory,
        provisions,
        jurisdiction,
        document_class,
        target_version,
    )
    if not coverage.complete:
        raise ValueError("consolidated scope does not have complete coverage")

    target_sources.mkdir(parents=True)
    for source_version, source_directory in source_directories:
        shutil.copytree(source_directory, target_sources / source_version)
    store.write_inventory(target_inventory_path, inventory)
    store.write_provisions(target_provisions_path, provisions)
    store.write_json(target_coverage_path, coverage.to_mapping())
    return (
        target_sources,
        target_inventory_path,
        target_provisions_path,
        target_coverage_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--document-class", required=True)
    parser.add_argument("--source-version", action="append", required=True)
    parser.add_argument("--target-version", required=True)
    args = parser.parse_args()
    generated = consolidate_release_scopes(
        base=args.base,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        source_versions=tuple(args.source_version),
        target_version=args.target_version,
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
