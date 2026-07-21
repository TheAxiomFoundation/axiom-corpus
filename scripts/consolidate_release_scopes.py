#!/usr/bin/env python3
"""Consolidate overlapping immutable scopes into one collision-free scope."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

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


def _portable_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    portable = dict(metadata)
    download_url = portable.get("download_url")
    if isinstance(download_url, str) and download_url.startswith("file://"):
        portable.pop("download_url")
    return portable or None


_DUPLICATE_IGNORED_FIELDS = {
    "body",
    "expression_date",
    "id",
    "metadata",
    "parent_id",
    "source_as_of",
    "source_document_id",
    "source_format",
    "source_id",
    "source_path",
    "source_url",
    "version",
}


def _semantic_record(record: ProvisionRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.to_mapping().items()
        if key not in _DUPLICATE_IGNORED_FIELDS
    }


def _is_structural_duplicate(first: ProvisionRecord, other: ProvisionRecord) -> bool:
    return (
        not (first.body or "").strip()
        and not (other.body or "").strip()
        and _semantic_record(first) == _semantic_record(other)
    )


def _remove_artifact(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def consolidate_release_scopes(
    *,
    base: Path,
    jurisdiction: str,
    document_class: str,
    source_versions: tuple[str, ...],
    target_version: str,
    preferred_duplicate_versions: dict[str, str] | None = None,
    preferred_duplicate_version: str | None = None,
    shadowed_block_versions: dict[str, str] | None = None,
) -> tuple[Path, ...]:
    """Create one immutable scope from ordered sources, deduping empty containers."""
    if not source_versions:
        raise ValueError("at least one source version is required")
    if len(source_versions) != len(set(source_versions)):
        raise ValueError("source versions must be unique")
    if target_version in source_versions:
        raise ValueError("target version must differ from source versions")
    preferences = dict(preferred_duplicate_versions or {})
    shadowing = dict(shadowed_block_versions or {})
    preference_versions = set(preferences.values())
    if preferred_duplicate_version is not None:
        preference_versions.add(preferred_duplicate_version)
    unknown_preference_versions = sorted(preference_versions - set(source_versions))
    if unknown_preference_versions:
        raise ValueError(
            "preferred duplicate versions must be source versions: "
            f"{unknown_preference_versions}"
        )
    unknown_shadow_versions = sorted(
        (set(shadowing) | set(shadowing.values())) - set(source_versions)
    )
    if unknown_shadow_versions:
        raise ValueError(
            "shadowed block versions must be source versions: "
            f"{unknown_shadow_versions}"
        )
    if any(source == successor for source, successor in shadowing.items()):
        raise ValueError("shadowed block source and successor versions must differ")

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

    inventory_candidates: dict[str, list[tuple[str, SourceInventoryItem]]] = {}
    provision_candidates: dict[str, list[tuple[str, ProvisionRecord]]] = {}
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
                metadata=_portable_metadata(item.metadata),
                source_path=_rewritten_source_path(
                    item.source_path,
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    source_version=source_version,
                    target_version=target_version,
                ),
            )
            inventory_candidates.setdefault(item.citation_path, []).append(
                (source_version, rewritten)
            )

        for record in load_provisions(provisions_path):
            rewritten = replace(
                record,
                version=target_version,
                id=deterministic_provision_id(record.citation_path, target_version),
                parent_id=(
                    deterministic_provision_id(record.parent_citation_path, target_version)
                    if record.parent_citation_path
                    else None
                ),
                metadata=_portable_metadata(record.metadata),
                source_path=_rewritten_source_path(
                    record.source_path,
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    source_version=source_version,
                    target_version=target_version,
                ),
            )
            provision_candidates.setdefault(record.citation_path, []).append(
                (source_version, rewritten)
            )

    citations_by_version = {
        source_version: {
            citation_path
            for citation_path, candidates in provision_candidates.items()
            if any(version == source_version for version, _record in candidates)
        }
        for source_version in source_versions
    }
    for citation_path in tuple(provision_candidates):
        retained = [
            (source_version, record)
            for source_version, record in provision_candidates[citation_path]
            if not (
                source_version in shadowing
                and record.kind == "block"
                and record.parent_citation_path
                in citations_by_version[shadowing[source_version]]
            )
        ]
        retained_versions = {source_version for source_version, _record in retained}
        if retained:
            provision_candidates[citation_path] = retained
            inventory_candidates[citation_path] = [
                (source_version, item)
                for source_version, item in inventory_candidates[citation_path]
                if source_version in retained_versions
            ]
        else:
            del provision_candidates[citation_path]
            del inventory_candidates[citation_path]

    if set(inventory_candidates) != set(provision_candidates):
        missing = sorted(set(provision_candidates) - set(inventory_candidates))
        extra = sorted(set(inventory_candidates) - set(provision_candidates))
        raise ValueError(f"inventory/provision mismatch; missing={missing}, extra={extra}")

    inventory_by_citation: dict[str, SourceInventoryItem] = {}
    provisions_by_citation: dict[str, ProvisionRecord] = {}
    used_preferences: set[str] = set()
    for citation_path, candidates in provision_candidates.items():
        explicit_preferred_version = preferences.get(citation_path)
        preferred_version = explicit_preferred_version
        if len(candidates) > 1:
            preferred_version = preferred_version or preferred_duplicate_version
            first = candidates[0][1]
            equivalent = all(
                _is_structural_duplicate(first, candidate) for _, candidate in candidates[1:]
            )
            if not equivalent and preferred_version is None:
                raise ValueError(
                    "conflicting duplicate citation_path requires an explicit preferred "
                    f"source version: {citation_path}"
                )
            if explicit_preferred_version is not None:
                used_preferences.add(citation_path)
        selected_version = preferred_version or candidates[0][0]
        selected = next(
            (record for version, record in candidates if version == selected_version),
            None,
        )
        if selected is None:
            raise ValueError(
                f"preferred source version {selected_version} does not carry {citation_path}"
            )
        inventory_item = next(
            (
                item
                for version, item in inventory_candidates[citation_path]
                if version == selected_version
            ),
            None,
        )
        if inventory_item is None:
            raise ValueError(
                f"preferred inventory source version {selected_version} does not carry {citation_path}"
            )
        provisions_by_citation[citation_path] = selected
        inventory_by_citation[citation_path] = inventory_item

    unused_preferences = sorted(set(preferences) - used_preferences)
    if unused_preferences:
        raise ValueError(f"preferred duplicate citations were not duplicated: {unused_preferences}")

    inventory = tuple(inventory_by_citation.values())
    provisions = tuple(provisions_by_citation.values())
    coverage = compare_provision_coverage(
        inventory,
        provisions,
        jurisdiction,
        document_class,
        target_version,
    )
    if not coverage.complete:
        raise ValueError("consolidated scope does not have complete coverage")

    targets = (
        target_sources,
        target_inventory_path,
        target_provisions_path,
        target_coverage_path,
    )
    with TemporaryDirectory(prefix=".consolidate-", dir=store.root) as temporary:
        staging_store = CorpusArtifactStore(Path(temporary))
        staged_sources = (
            staging_store.root / "sources" / jurisdiction / document_class / target_version
        )
        staged_sources.mkdir(parents=True)
        for source_version, source_directory in source_directories:
            shutil.copytree(source_directory, staged_sources / source_version)
        staged_inventory = staging_store.inventory_path(
            jurisdiction, document_class, target_version
        )
        staged_provisions = staging_store.provisions_path(
            jurisdiction, document_class, target_version
        )
        staged_coverage = staging_store.coverage_path(
            jurisdiction, document_class, target_version
        )
        staging_store.write_inventory(staged_inventory, inventory)
        staging_store.write_provisions(staged_provisions, provisions)
        staging_store.write_json(staged_coverage, coverage.to_mapping())
        staged = (staged_sources, staged_inventory, staged_provisions, staged_coverage)
        committed: list[Path] = []
        try:
            for staged_path, target_path in zip(staged, targets, strict=True):
                target_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.replace(target_path)
                committed.append(target_path)
        except Exception:
            for target_path in reversed(committed):
                _remove_artifact(target_path)
            raise
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
    parser.add_argument(
        "--prefer-duplicate-carrier",
        action="append",
        default=[],
        metavar="CITATION_PATH=SOURCE_VERSION",
    )
    parser.add_argument(
        "--prefer-all-duplicates-from",
        metavar="SOURCE_VERSION",
    )
    parser.add_argument(
        "--drop-shadowed-block",
        action="append",
        default=[],
        metavar="SOURCE_VERSION=SUCCESSOR_VERSION",
    )
    args = parser.parse_args()
    preferences: dict[str, str] = {}
    for raw in args.prefer_duplicate_carrier:
        citation_path, separator, source_version = raw.partition("=")
        if not separator or not citation_path or not source_version:
            parser.error("--prefer-duplicate-carrier must be CITATION_PATH=SOURCE_VERSION")
        if citation_path in preferences:
            parser.error(f"duplicate preferred carrier for {citation_path}")
        preferences[citation_path] = source_version
    shadowing: dict[str, str] = {}
    for raw in args.drop_shadowed_block:
        source_version, separator, successor_version = raw.partition("=")
        if not separator or not source_version or not successor_version:
            parser.error("--drop-shadowed-block must be SOURCE_VERSION=SUCCESSOR_VERSION")
        if source_version in shadowing:
            parser.error(f"duplicate shadowed block source version {source_version}")
        shadowing[source_version] = successor_version
    generated = consolidate_release_scopes(
        base=args.base,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        source_versions=tuple(args.source_version),
        target_version=args.target_version,
        preferred_duplicate_versions=preferences,
        preferred_duplicate_version=args.prefer_all_duplicates_from,
        shadowed_block_versions=shadowing,
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
