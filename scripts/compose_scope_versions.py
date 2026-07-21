#!/usr/bin/env python3
"""Compose several immutable corpus scope versions into one derived version.

Amendment discovery in axiom-encode only considers candidate rows whose
``version`` equals the resolved target's version, so an amending instrument
ingested in its own wave is invisible next to the consolidation it amends.
This script derives a single new scope version from ordered constituent
versions (for example the existing consolidation wave plus a later
amending-instrument wave) without re-fetching anything: constituent artifacts
stay byte-identical and the composed rows are rewritten the same way
``reversion_expression_dates.py`` rewrites a re-versioned scope.
"""

from __future__ import annotations

import argparse
import shutil
import unicodedata
from dataclasses import replace
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id


def _rewrite_source_path(
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
        raise ValueError(f"source_path is outside the source scope: {value}")
    return f"sources/{jurisdiction}/{document_class}/{target_version}/{value[len(source_prefix):]}"


def compose_scope_versions(
    *,
    base: Path,
    jurisdiction: str,
    document_class: str,
    source_versions: list[str],
    target_version: str,
) -> tuple[Path, ...]:
    """Concatenate constituent scope versions into one new immutable version."""
    if len(source_versions) < 2:
        raise ValueError("compose requires at least two source versions")
    if len(set(source_versions)) != len(source_versions):
        raise ValueError("source versions must be distinct")
    if target_version in source_versions:
        raise ValueError("target version must differ from every source version")

    store = CorpusArtifactStore(base)
    target_inventory_path = store.inventory_path(
        jurisdiction, document_class, target_version
    )
    target_provisions_path = store.provisions_path(
        jurisdiction, document_class, target_version
    )
    target_coverage_path = store.coverage_path(
        jurisdiction, document_class, target_version
    )
    target_directory = (
        store.root / "sources" / jurisdiction / document_class / target_version
    )
    for path in (
        target_inventory_path,
        target_provisions_path,
        target_coverage_path,
        target_directory,
    ):
        if path.exists() or path.is_symlink():
            raise ValueError(f"target artifact already exists: {path}")

    source_directories: list[tuple[str, Path]] = []
    for source_version in source_versions:
        inventory_path = store.inventory_path(
            jurisdiction, document_class, source_version
        )
        provisions_path = store.provisions_path(
            jurisdiction, document_class, source_version
        )
        directory = (
            store.root / "sources" / jurisdiction / document_class / source_version
        )
        for path in (inventory_path, provisions_path):
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"source artifact is not a regular file: {path}")
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(
                f"source directory is not a regular directory: {directory}"
            )
        if any(path.is_symlink() for path in directory.rglob("*")):
            raise ValueError(f"source directory contains a symlink: {directory}")
        source_directories.append((source_version, directory))

    # Aggregate coverage alone would let complementary missing/extra
    # citations across constituents cancel out; require each constituent
    # scope to be complete on its own first.
    for source_version in source_versions:
        constituent_coverage = compare_provision_coverage(
            tuple(
                load_source_inventory(
                    store.inventory_path(jurisdiction, document_class, source_version)
                )
            ),
            tuple(
                load_provisions(
                    store.provisions_path(jurisdiction, document_class, source_version)
                )
            ),
            jurisdiction,
            document_class,
            source_version,
        )
        if not constituent_coverage.complete:
            raise ValueError(
                f"constituent scope does not have complete coverage: {source_version}"
            )

    # Detect source-path collisions before creating anything so a refused
    # compose never leaves a partial target behind. Directories may merge
    # with directories, but a file may never share a relative path with
    # anything from another constituent (including a directory — otherwise
    # copy2 would silently write file "node" INTO directory "node/").
    # Collision keys use the Unicode canonical caseless form,
    # NFD(casefold(NFD(s))): case-insensitive, normalization-insensitive
    # filesystems (APFS) resolve exactly such spellings to one entry, so
    # lexical distinctness alone would let the second copy silently replace
    # the first. Plain NFC+casefold is not enough — e.g. "Ś" and "ſ́"
    # casefold to precomposed vs decomposed ś and only the double-NFD form
    # equates them.
    def collision_key(relative: Path) -> str:
        decomposed = unicodedata.normalize("NFD", relative.as_posix())
        return unicodedata.normalize("NFD", decomposed.casefold())

    seen_relative_paths: dict[str, tuple[str, str, Path]] = {}
    for source_version, directory in source_directories:
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory)
            kind = "directory" if path.is_dir() else "file"
            previous = seen_relative_paths.get(collision_key(relative))
            if previous is None:
                seen_relative_paths[collision_key(relative)] = (
                    kind,
                    source_version,
                    relative,
                )
                continue
            previous_kind, previous_version, previous_relative = previous
            if kind == "directory" and previous_kind == "directory":
                continue
            raise ValueError(
                "source file collides across source versions: "
                f"{previous_version}/{previous_relative} ({previous_kind}) vs "
                f"{source_version}/{relative} ({kind})"
            )

    inventory = []
    seen_inventory_paths: set[str] = set()
    for source_version in source_versions:
        for item in load_source_inventory(
            store.inventory_path(jurisdiction, document_class, source_version)
        ):
            if item.citation_path in seen_inventory_paths:
                raise ValueError(
                    "duplicate inventory citation_path across source versions: "
                    f"{item.citation_path}"
                )
            seen_inventory_paths.add(item.citation_path)
            inventory.append(
                replace(
                    item,
                    source_path=_rewrite_source_path(
                        item.source_path,
                        jurisdiction=jurisdiction,
                        document_class=document_class,
                        source_version=source_version,
                        target_version=target_version,
                    ),
                )
            )

    provisions = []
    seen_provision_paths: set[str] = set()
    for source_version in source_versions:
        for record in load_provisions(
            store.provisions_path(jurisdiction, document_class, source_version)
        ):
            if record.citation_path in seen_provision_paths:
                raise ValueError(
                    "duplicate provision citation_path across source versions: "
                    f"{record.citation_path}"
                )
            seen_provision_paths.add(record.citation_path)
            provisions.append(
                replace(
                    record,
                    version=target_version,
                    id=deterministic_provision_id(
                        record.citation_path, target_version
                    ),
                    parent_id=(
                        deterministic_provision_id(
                            record.parent_citation_path, target_version
                        )
                        if record.parent_citation_path
                        else None
                    ),
                    source_path=_rewrite_source_path(
                        record.source_path,
                        jurisdiction=jurisdiction,
                        document_class=document_class,
                        source_version=source_version,
                        target_version=target_version,
                    ),
                )
            )

    inventory_tuple = tuple(inventory)
    provision_tuple = tuple(provisions)
    coverage = compare_provision_coverage(
        inventory_tuple,
        provision_tuple,
        jurisdiction,
        document_class,
        target_version,
    )
    if not coverage.complete:
        raise ValueError("composed scope does not have complete coverage")

    try:
        target_directory.mkdir(parents=True)
        for _, directory in source_directories:
            for path in sorted(directory.rglob("*")):
                relative = path.relative_to(directory)
                destination = target_directory / relative
                if path.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
        store.write_inventory(target_inventory_path, inventory_tuple)
        store.write_provisions(target_provisions_path, provision_tuple)
        store.write_json(target_coverage_path, coverage.to_mapping())
    except BaseException:
        # Never leave a partial target: a later retry must not be rejected by
        # the existing-target guard because of our own debris.
        shutil.rmtree(target_directory, ignore_errors=True)
        for path in (
            target_inventory_path,
            target_provisions_path,
            target_coverage_path,
        ):
            path.unlink(missing_ok=True)
        raise
    return (
        target_directory,
        target_inventory_path,
        target_provisions_path,
        target_coverage_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--document-class", required=True)
    parser.add_argument(
        "--source-version",
        action="append",
        required=True,
        help="Constituent version, repeatable; order fixes row order.",
    )
    parser.add_argument("--target-version", required=True)
    args = parser.parse_args()
    generated = compose_scope_versions(
        base=args.base,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        source_versions=args.source_version,
        target_version=args.target_version,
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
