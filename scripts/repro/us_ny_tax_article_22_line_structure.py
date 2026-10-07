#!/usr/bin/env python3
"""Rebuild the released New York Tax Law Article 22 scope with structured bodies.

The released scope ``us-ny/statute/2026-09-14-income-tax-chapter`` was taken
through the generic official-documents extractor, which read each Senate page's
``div.nys-openleg-result-text`` as one run of text: the OpenLegislation line
structure (a line per paragraph the publisher indents and per table row) was
collapsed into a single line per section, stored in a ``block-1`` row under a
bodiless document root. A narrow citation such as
``us-ny/statute/TAX/606/e/7/D`` therefore cannot be sliced out of the section.

This successor re-parses the exact retained HTML bytes of that run with the New
York adapter (:func:`parse_new_york_law_page`), whose OpenLegislation
normalization keeps one line per paragraph the publisher indents and per table
row (a label the publisher runs in after a heading or its parent label stays on
that line), and puts each body on its section row (the shape of the earlier
OpenLegislation and recovery NY statute scopes). No publisher traffic: the
source bytes are copied byte for byte after their SHA-256 is checked against the
released inventory, and every section body is checked to carry exactly the
released word sequence (only whitespace moves). The released scope is left
untouched.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import OfficialDocumentManifest
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.state_adapters.new_york import (
    NEW_YORK_SENATE_SOURCE_FORMAT,
    _append_inventory_and_record,
    _page_identifiers,
    _state_source_key,
    parse_new_york_law_page,
)

JURISDICTION = "us-ny"
DOCUMENT_CLASS = DocumentClass.STATUTE
SOURCE_VERSION = "2026-09-14-income-tax-chapter"
VERSION = "2026-09-14-income-tax-chapter-r2026-09-23-line-structure"
SOURCE_AS_OF = "2026-09-14"
EXPRESSION_DATE = "2026-09-14"
MANIFEST = Path("manifests/us-ny-tax-law-article-22-personal-income-tax.yaml")
_MANIFEST_METADATA_KEYS = (
    "primary_source",
    "source_authority",
    "document_subtype",
    "program",
    "source_status",
    "source_family",
    "index_url",
    "discovered_via",
    "article",
    "part",
    "part_heading",
    "part_index_url",
)


@dataclass(frozen=True)
class SuccessorScope:
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    section_count: int


def _released_items(source_base: Path) -> dict[str, SourceInventoryItem]:
    inventory = load_source_inventory(
        source_base / "inventory" / JURISDICTION / DOCUMENT_CLASS.value / f"{SOURCE_VERSION}.json"
    )
    return {
        item.citation_path: item
        for item in inventory
        if (item.metadata or {}).get("kind") == "document"
    }


def _released_bodies(source_base: Path) -> dict[str, str]:
    records = load_provisions(
        source_base / "provisions" / JURISDICTION / DOCUMENT_CLASS.value / f"{SOURCE_VERSION}.jsonl"
    )
    return {
        record.parent_citation_path: record.body or ""
        for record in records
        if record.kind == "block" and record.parent_citation_path is not None
    }


def build_scope(
    *,
    base: Path,
    source_base: Path,
    manifest_path: Path = MANIFEST,
) -> SuccessorScope:
    """Build the successor scope from the retained 2026-09-14 Senate pages."""
    store = CorpusArtifactStore(base)
    manifest = OfficialDocumentManifest.load(manifest_path)
    manifest.require_unique_sources()
    released = _released_items(source_base)
    released_bodies = _released_bodies(source_base)
    if len(released) != len(manifest.documents):
        raise ValueError(
            f"released scope has {len(released)} documents; manifest lists "
            f"{len(manifest.documents)}"
        )

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for ordinal, document in enumerate(manifest.documents):
        if document.jurisdiction != JURISDICTION or document.document_class != "statute":
            raise ValueError(f"{document.source_id}: not a {JURISDICTION} statute source")
        citation_path = str(document.citation_path)
        item = released.get(citation_path)
        if item is None:
            raise ValueError(f"{citation_path}: not in the released {SOURCE_VERSION} inventory")
        raw = (source_base / item.source_path).read_bytes()
        if sha256_bytes(raw) != item.sha256:
            raise ValueError(f"{citation_path}: retained source hash changed")
        page = parse_new_york_law_page(raw, source_url=document.source_url)
        if page.kind != "section" or page.citation_path != citation_path:
            raise ValueError(
                f"{citation_path}: retained page parses as {page.kind} {page.citation_path}"
            )
        if not page.body:
            raise ValueError(f"{citation_path}: retained page has no section text")
        if page.body.split() != released_bodies.get(citation_path, "").split():
            raise ValueError(f"{citation_path}: words differ from the released section body")

        relative_name = f"{NEW_YORK_SENATE_SOURCE_FORMAT}/{page.law_id}/{page.location_id}.html"
        sha256 = store.write_bytes(
            store.source_path(JURISDICTION, DOCUMENT_CLASS, VERSION, relative_name),
            raw,
        )
        manifest_metadata = document.metadata or {}
        metadata: dict[str, Any] = {
            "kind": page.kind,
            "law_id": page.law_id,
            "location_id": page.location_id,
            "display_number": page.display_number,
            "revision_date": page.revision_date,
            "breadcrumb_labels": list(page.breadcrumb_labels),
            **{
                key: manifest_metadata[key]
                for key in _MANIFEST_METADATA_KEYS
                if manifest_metadata.get(key) is not None
            },
            "manifest_source_id": document.source_id,
            "successor_of_version": SOURCE_VERSION,
            "successor_of_source_path": item.source_path,
        }
        _append_inventory_and_record(
            items,
            records,
            citation_path=citation_path,
            version=VERSION,
            source_url=document.source_url,
            source_path=_state_source_key(JURISDICTION, VERSION, relative_name),
            source_id=page.source_id,
            sha256=sha256,
            source_as_of=SOURCE_AS_OF,
            expression_date=EXPRESSION_DATE,
            kind=page.kind,
            heading=page.heading,
            body=page.body,
            legal_identifier=page.legal_identifier,
            level=1,
            ordinal=ordinal,
            identifiers=_page_identifiers(page),
            metadata=metadata,
            source_format=NEW_YORK_SENATE_SOURCE_FORMAT,
        )

    inventory_path = store.inventory_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    provisions_path = store.provisions_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    coverage_path = store.coverage_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    store.write_inventory(inventory_path, items)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS.value,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError("New York Article 22 successor scope does not have complete coverage")
    store.write_json(coverage_path, coverage.to_mapping())
    return SuccessorScope(
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        section_count=len(records),
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
                "sections": scope.section_count,
                "inventory": str(scope.inventory_path),
                "provisions": str(scope.provisions_path),
                "coverage": str(scope.coverage_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
