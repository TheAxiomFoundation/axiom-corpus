#!/usr/bin/env python3
"""Rebuild the consolidated Colorado regulation scope with 8 CCR 1403-1 in sections.

``us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated`` carries
the Colorado Child Care Assistance Program rules (8 CCR 1403-1) as the July
recovery made them: a bodyless ``document`` root at
``us-co/regulation/8-ccr-1403-1/3.111`` over 75 ``page-N`` rows. A reader that
composes a bodyless root from its descendants (axiom-encode's corpus resolver
does) therefore gets the whole rulebook for ``8-ccr-1403-1/3.111``, not §3.111.

This successor re-extracts the retained PDF with the shared official-documents
adapter (``labeled_sections``, configured in
``manifests/us-co-ccap-8-ccr-1403-1.yaml``, as 9 CCR 2503-6 is in
``manifests/us-co-tanf-state-policy-manual.yaml``): a bodyless root at
``us-co/regulation/8-ccr-1403-1`` and one ``section`` row per rule section
(``3.100`` ... ``3.116.95``) plus the editor's notes. Those rows take the place
of the 76 recovery rows, in the same position. No publisher traffic: the
retained bytes are checked against the scope's inventory and provenance hash
and extracted offline.

Every other row and inventory item is carried unchanged except for the fields
that name the scope: ``version``, ``source_path`` (its version segment) and,
for provisions, ``id``/``parent_id``, which the consolidated file derives from
``(citation_path, version)`` and this file derives the same way from the new
version. The source tree is copied file for file, so the successor carries the
same bytes as the consolidated scope and no new ones. The consolidated scope is
left untouched.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import OfficialDocumentManifest, extract_official_documents
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

JURISDICTION = "us-co"
DOCUMENT_CLASS = DocumentClass.REGULATION
SOURCE_VERSION = "2026-07-13-recovery-r2026-09-11-tanf-consolidated"
VERSION = f"{SOURCE_VERSION}-r2026-09-27-ccap-sections"
MANIFEST = Path("manifests/us-co-ccap-8-ccr-1403-1.yaml")
SOURCE_ID = "us-co-8-ccr-1403-1"
ROOT_CITATION_PATH = "us-co/regulation/8-ccr-1403-1"
REPLACED_ROOT = f"{ROOT_CITATION_PATH}/3.111"
PAGE_COUNT = 75
RETAINED_SOURCE = "2026-07-13-recovery/official-documents/us-co-8-ccr-1403-1"
RETAINED_PROVENANCE = "2026-07-13-recovery/provenance/us-co-8-ccr-1403-1.json"
RETAINED_SHA256 = "b76234b6ce316b86adef29e5ea8d5942bb490b1fe630c37c71a44516229765af"
SCOPE_FIELDS = ("version", "id", "parent_id", "source_path")


@dataclass(frozen=True)
class SuccessorScope:
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    source_directory: Path
    carried_count: int
    replaced_count: int
    section_count: int


def _sources_prefix(version: str) -> str:
    return f"sources/{JURISDICTION}/{DOCUMENT_CLASS.value}/{version}/"


def _rehome(source_path: str | None) -> str | None:
    if source_path is None:
        return None
    prefix = _sources_prefix(SOURCE_VERSION)
    if not source_path.startswith(prefix):
        raise ValueError(f"source_path is outside {SOURCE_VERSION}: {source_path}")
    return _sources_prefix(VERSION) + source_path[len(prefix) :]


def _versioned_ids(record: ProvisionRecord, version: str) -> dict[str, str | None]:
    return {
        "id": deterministic_provision_id(record.citation_path, version),
        "parent_id": (
            deterministic_provision_id(record.parent_citation_path, version)
            if record.parent_citation_path
            else None
        ),
    }


def carry_record(record: ProvisionRecord) -> ProvisionRecord:
    """Move one consolidated row into the successor, changing only its scope fields."""
    return replace(
        record,
        version=VERSION,
        source_path=_rehome(record.source_path),
        **_versioned_ids(record, VERSION),
    )


def carry_item(item: SourceInventoryItem) -> SourceInventoryItem:
    """Move one consolidated inventory item into the successor (source_path only)."""
    return replace(item, source_path=_rehome(item.source_path))


def _replaced_block(citation_paths: list[str]) -> range:
    """Return the contiguous index range of the recovery's 8 CCR 1403-1 rows."""
    expected = [REPLACED_ROOT, *(f"{REPLACED_ROOT}/page-{n}" for n in range(1, PAGE_COUNT + 1))]
    start = citation_paths.index(REPLACED_ROOT)
    block = range(start, start + len(expected))
    if citation_paths[block.start : block.stop] != expected:
        raise ValueError("8 CCR 1403-1 recovery rows are not the expected root and page rows")
    if any(
        path == ROOT_CITATION_PATH or path.startswith(f"{ROOT_CITATION_PATH}/")
        for index, path in enumerate(citation_paths)
        if index not in block
    ):
        raise ValueError("another row outside the recovery block sits under 8-ccr-1403-1")
    return block


def _extract_sections(
    manifest_path: Path, retained_path: Path, provenance: dict[str, Any]
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    """Run the official-documents adapter over the retained bytes, offline."""
    manifest = yaml.safe_load(manifest_path.read_text())
    documents = manifest.get("documents") if isinstance(manifest, dict) else None
    if not isinstance(documents, list) or len(documents) != 1:
        raise ValueError(f"{manifest_path}: expected exactly one document")
    document = documents[0]
    if (
        document.get("source_id") != SOURCE_ID
        or document.get("citation_path") != ROOT_CITATION_PATH
        or document.get("source_url") != provenance["url"]
    ):
        raise ValueError(f"{manifest_path}: not the retained 8 CCR 1403-1 document")
    with tempfile.TemporaryDirectory() as scratch:
        scratch_path = Path(scratch)
        local_manifest = scratch_path / "manifest.yaml"
        local_manifest.write_text(
            yaml.safe_dump(
                {
                    **manifest,
                    "documents": [{**document, "local_path": str(retained_path.resolve())}],
                },
                allow_unicode=True,
                sort_keys=False,
            )
        )
        OfficialDocumentManifest.load(local_manifest).require_unique_sources()
        report = extract_official_documents(
            CorpusArtifactStore(scratch_path / "corpus"),
            manifest_path=local_manifest,
            version=VERSION,
        )
        if not report.coverage.complete:
            raise ValueError("8 CCR 1403-1 extraction does not have complete coverage")
        items = load_source_inventory(report.inventory_path)
        records = load_provisions(report.provisions_path)

    source_path = _sources_prefix(VERSION) + RETAINED_SOURCE
    provenance_metadata = {"download_url": provenance["url"]}
    successor_metadata = {
        "successor_of_version": SOURCE_VERSION,
        "successor_of_citation_path": REPLACED_ROOT,
    }
    rewritten_items = []
    for item in items:
        if item.sha256 != RETAINED_SHA256:
            raise ValueError(f"{item.citation_path}: extracted bytes are not the retained PDF")
        rewritten_items.append(
            replace(
                item,
                source_path=source_path,
                metadata={**(item.metadata or {}), **provenance_metadata},
            )
        )
    rewritten_records = [
        replace(
            record,
            source_path=source_path,
            metadata={**(record.metadata or {}), **provenance_metadata, **successor_metadata},
            **_versioned_ids(record, VERSION),
        )
        for record in records
    ]
    return rewritten_items, rewritten_records


def build_scope(
    *,
    base: Path,
    source_base: Path,
    manifest_path: Path = MANIFEST,
) -> SuccessorScope:
    """Build the successor scope from the consolidated scope's retained artifacts."""
    source_store = CorpusArtifactStore(source_base)
    target_store = CorpusArtifactStore(base)
    source_directory = (
        source_store.root / "sources" / JURISDICTION / DOCUMENT_CLASS.value / (SOURCE_VERSION)
    )
    target_directory = target_store.root / "sources" / JURISDICTION / DOCUMENT_CLASS.value / VERSION
    inventory_path = target_store.inventory_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    provisions_path = target_store.provisions_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    coverage_path = target_store.coverage_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    for path in (inventory_path, provisions_path, coverage_path, target_directory):
        if path.exists() or path.is_symlink():
            raise ValueError(f"target artifact already exists: {path}")

    items = load_source_inventory(
        source_store.inventory_path(JURISDICTION, DOCUMENT_CLASS, SOURCE_VERSION)
    )
    records = load_provisions(
        source_store.provisions_path(JURISDICTION, DOCUMENT_CLASS, SOURCE_VERSION)
    )
    for record in records:
        if record.version != SOURCE_VERSION or _versioned_ids(record, SOURCE_VERSION) != {
            "id": record.id,
            "parent_id": record.parent_id,
        }:
            raise ValueError(f"{record.citation_path}: ids are not derived from its version")
    record_block = _replaced_block([record.citation_path for record in records])
    item_block = _replaced_block([item.citation_path for item in items])
    if record_block != item_block:
        raise ValueError("inventory and provisions place 8 CCR 1403-1 differently")

    retained_path = source_directory / RETAINED_SOURCE
    retained = retained_path.read_bytes()
    provenance = json.loads((source_directory / RETAINED_PROVENANCE).read_text())
    if not (
        sha256_bytes(retained) == RETAINED_SHA256 == provenance["sha256"]
        and all(items[index].sha256 == RETAINED_SHA256 for index in item_block)
        and all(
            items[index].source_path == _sources_prefix(SOURCE_VERSION) + RETAINED_SOURCE
            for index in item_block
        )
    ):
        raise ValueError("retained 8 CCR 1403-1 bytes do not match the scope's recorded hash")

    new_items, new_records = _extract_sections(manifest_path, retained_path, provenance)
    successor_items = [
        *(carry_item(item) for item in items[: item_block.start]),
        *new_items,
        *(carry_item(item) for item in items[item_block.stop :]),
    ]
    successor_records = [
        *(carry_record(record) for record in records[: record_block.start]),
        *new_records,
        *(carry_record(record) for record in records[record_block.stop :]),
    ]
    carried = [
        (old, new)
        for old, new in zip(
            [*records[: record_block.start], *records[record_block.stop :]],
            [
                *successor_records[: record_block.start],
                *successor_records[record_block.start + len(new_records) :],
            ],
            strict=True,
        )
    ]
    for old, new in carried:
        if replace(new, **{field: getattr(old, field) for field in SCOPE_FIELDS}) != old:
            raise ValueError(f"{old.citation_path}: carried row changed beyond its scope fields")

    coverage = compare_provision_coverage(
        tuple(successor_items),
        tuple(successor_records),
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS.value,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError("8 CCR 1403-1 successor scope does not have complete coverage")

    try:
        target_directory.mkdir(parents=True)
        for path in sorted(source_directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"source directory contains a symlink: {path}")
            destination = target_directory / path.relative_to(source_directory)
            if path.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            target_store.write_bytes(destination, path.read_bytes())
        target_store.write_inventory(inventory_path, successor_items)
        target_store.write_provisions(provisions_path, successor_records)
        target_store.write_json(coverage_path, coverage.to_mapping())
    except BaseException:
        shutil.rmtree(target_directory, ignore_errors=True)
        for path in (inventory_path, provisions_path, coverage_path):
            path.unlink(missing_ok=True)
        raise
    return SuccessorScope(
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        source_directory=target_directory,
        carried_count=len(carried),
        replaced_count=len(record_block),
        section_count=sum(1 for record in new_records if record.kind == "section"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--source-base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args(argv)
    scope = build_scope(base=args.base, source_base=args.source_base, manifest_path=args.manifest)
    print(
        json.dumps(
            {
                "version": VERSION,
                "carried_rows": scope.carried_count,
                "replaced_rows": scope.replaced_count,
                "sections": scope.section_count,
                "inventory": str(scope.inventory_path),
                "provisions": str(scope.provisions_path),
                "coverage": str(scope.coverage_path),
                "sources": str(scope.source_directory),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
