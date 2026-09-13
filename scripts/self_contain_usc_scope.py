#!/usr/bin/env python3
"""Detach out-of-scope parent links so a section-filtered US Code scope is self-contained.

``extract-usc --section`` emits section rows whose ``parent_citation_path`` is the
title row (``us/statute/42``) and, with ``--citation-path``, subsection or paragraph
rows whose parents are the omitted section. Release validation checks parent
integrity scope-locally, and the title row is already released in the consolidated
title scope, so a partial scope cannot carry it a second time. This mirrors the
released ``-r2026-07-15-self-contained`` statute scopes and the
``repair_us_release_source_references.py`` precedent: do not fabricate the omitted
container and do not retain the dangling relationship; record the detached parent
in metadata and rewrite the coverage report. Fail-closed on incomplete coverage.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory


def self_contain_scope(
    base: Path,
    *,
    jurisdiction: str,
    document_class: str,
    version: str,
) -> dict[str, object]:
    store = CorpusArtifactStore(base)
    inventory_path = store.inventory_path(jurisdiction, document_class, version)
    provisions_path = store.provisions_path(jurisdiction, document_class, version)
    coverage_path = store.coverage_path(jurisdiction, document_class, version)
    inventory = load_source_inventory(inventory_path)
    provisions = load_provisions(provisions_path)
    in_scope = {record.citation_path for record in provisions}
    detached_by_kind: Counter[str] = Counter()
    detached_parents: Counter[str] = Counter()
    rewritten = []
    for record in provisions:
        parent = record.parent_citation_path
        if parent and parent not in in_scope:
            metadata = dict(record.metadata or {})
            metadata["self_contained_root"] = True
            metadata["detached_parent_citation_path"] = parent
            rewritten.append(
                replace(record, parent_citation_path=None, parent_id=None, metadata=metadata)
            )
            detached_by_kind[record.kind or "unknown"] += 1
            detached_parents[parent] += 1
        else:
            rewritten.append(record)
    records = tuple(rewritten)
    coverage = compare_provision_coverage(
        inventory,
        records,
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=version,
    )
    if not coverage.complete:
        raise ValueError(f"coverage is incomplete for {jurisdiction}/{document_class}/{version}")
    store.write_provisions(provisions_path, records)
    store.write_json(coverage_path, coverage.to_mapping())
    return {
        "jurisdiction": jurisdiction,
        "document_class": document_class,
        "version": version,
        "provision_count": len(records),
        "detached_rows": sum(detached_by_kind.values()),
        "detached_by_kind": dict(sorted(detached_by_kind.items())),
        "detached_parents": dict(sorted(detached_parents.items())),
        "coverage_complete": coverage.complete,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--jurisdiction", default="us")
    parser.add_argument("--document-class", default="statute")
    parser.add_argument("--version", action="append", required=True)
    args = parser.parse_args()
    for version in args.version:
        report = self_contain_scope(
            args.base,
            jurisdiction=args.jurisdiction,
            document_class=args.document_class,
            version=version,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
