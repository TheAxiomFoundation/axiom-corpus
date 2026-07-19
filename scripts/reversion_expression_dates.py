#!/usr/bin/env python3
"""Re-version an immutable corpus scope while repairing expression dates."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id


def _is_iso_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


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


def reversion_expression_dates(
    *,
    base: Path,
    jurisdiction: str,
    document_class: str,
    source_version: str,
    target_version: str,
) -> tuple[Path, ...]:
    """Generate a new scope, preserving valid dates and repairing invalid ones."""
    if source_version == target_version:
        raise ValueError("source and target versions must differ")

    store = CorpusArtifactStore(base)
    source_inventory_path = store.inventory_path(
        jurisdiction, document_class, source_version
    )
    source_provisions_path = store.provisions_path(
        jurisdiction, document_class, source_version
    )
    source_directory = (
        store.root / "sources" / jurisdiction / document_class / source_version
    )
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

    for path in (source_inventory_path, source_provisions_path):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"source artifact is not a regular file: {path}")
    if not source_directory.is_dir() or source_directory.is_symlink():
        raise ValueError(f"source directory is not a regular directory: {source_directory}")
    if any(path.is_symlink() for path in source_directory.rglob("*")):
        raise ValueError(f"source directory contains a symlink: {source_directory}")
    for path in (
        target_inventory_path,
        target_provisions_path,
        target_coverage_path,
        target_directory,
    ):
        if path.exists() or path.is_symlink():
            raise ValueError(f"target artifact already exists: {path}")

    inventory = tuple(
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
        for item in load_source_inventory(source_inventory_path)
    )

    provisions = []
    for record in load_provisions(source_provisions_path):
        expression_date = record.expression_date
        if not _is_iso_date(expression_date):
            if not _is_iso_date(record.source_as_of):
                raise ValueError(
                    f"{record.citation_path} has no valid source_as_of fallback"
                )
            expression_date = record.source_as_of
        provisions.append(
            replace(
                record,
                version=target_version,
                id=deterministic_provision_id(record.citation_path, target_version),
                parent_id=(
                    deterministic_provision_id(
                        record.parent_citation_path, target_version
                    )
                    if record.parent_citation_path
                    else None
                ),
                expression_date=expression_date,
                source_path=_rewrite_source_path(
                    record.source_path,
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    source_version=source_version,
                    target_version=target_version,
                ),
            )
        )
    provision_tuple = tuple(provisions)
    coverage = compare_provision_coverage(
        inventory,
        provision_tuple,
        jurisdiction,
        document_class,
        target_version,
    )
    if not coverage.complete:
        raise ValueError("re-versioned scope does not have complete coverage")

    shutil.copytree(source_directory, target_directory)
    store.write_inventory(target_inventory_path, inventory)
    store.write_provisions(target_provisions_path, provision_tuple)
    store.write_json(target_coverage_path, coverage.to_mapping())
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
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--target-version", required=True)
    args = parser.parse_args()
    generated = reversion_expression_dates(
        base=args.base,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        source_version=args.source_version,
        target_version=args.target_version,
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
