#!/usr/bin/env python3
"""Rebuild merged California LegInfo section scopes with ``--preserve-tables``.

The ``california-code-sections`` adapter's default body collects every ``<p>`` and
``<i>`` block of a LegInfo page and keeps only the first copy of any repeated
block. That drops repeated table cells and row labels (R&TC 17041's rate tables,
17052(b)'s EITC tables, 17052.6 and 19025) and repeated statutory paragraphs such
as the second (ii)/(I)/(II) clause of R&TC 17053.5 and WIC 11450's second (ib).
Each successor here re-extracts the exact retained bytes of one merged scope with
``preserve_tables=True`` and stores it under ``<original version>-<REVISION>``,
so no merged version changes and nothing is fetched again.

The adapter runs into a scratch base under the original version prefix, which
reproduces the original run id from the original's inventory order, and the
scope is then moved to the successor version: only ``version``, ``source_path``
and the coverage report's ``version`` change in that step. Each successor keeps
its original's capture date and parent handling: the 2026-06-25 and 2026-07-06
scopes had their out-of-scope parent links nulled by the 2026-07-15
release-provenance repair (de4c33abb), and the 2026-09-14 chapter scope was
detached with ``scripts/self_contain_usc_scope.py``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import DocumentClass
from axiom_corpus.corpus.states import (
    _california_html_has_section,
    _california_section_html_relative_name,
    _california_sections_run_id,
    extract_california_code_sections,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAINED_BASE = REPO_ROOT / "data/corpus"
SELF_CONTAIN_SCRIPT = REPO_ROOT / "scripts/self_contain_usc_scope.py"
JURISDICTION = "us-ca"
DOCUMENT_CLASS = DocumentClass.STATUTE
REVISION = "r2026-09-24-preserve-tables"
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_ca_leginfo_preserve_tables_successors.py --base data/corpus"
)

# How each original scope's out-of-scope parent link was removed after extraction.
PARENT_NULLED = "nulled"  # parent_citation_path and parent_id set to None
PARENT_SELF_CONTAINED = "self-contained"  # scripts/self_contain_usc_scope.py


@dataclass(frozen=True)
class Successor:
    original_version: str
    original_prefix: str
    capture_date: str
    parent_handling: str

    @property
    def version(self) -> str:
        return f"{self.original_version}-{REVISION}"


SUCCESSORS = (
    Successor(
        original_version=(
            "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-"
            "wic-11451.5-wic-11452-wic-11452.018"
        ),
        original_prefix="2026-06-25-ca-wic-calworks",
        capture_date="2026-06-25",
        parent_handling=PARENT_NULLED,
    ),
    Successor(
        original_version=(
            "2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-"
            "rtc-17045-rtc-17052-rtc-17054-rtc-17073.5"
        ),
        original_prefix="2026-07-06-ca-rtc-pit-core",
        capture_date="2026-07-06",
        parent_handling=PARENT_NULLED,
    ),
    Successor(
        original_version="2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7",
        original_prefix="2026-09-14-income-tax-chapter",
        capture_date="2026-09-14",
        parent_handling=PARENT_SELF_CONTAINED,
    ),
)


def _load_self_contain_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("self_contain_usc_scope", SELF_CONTAIN_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SELF_CONTAIN_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_key(version: str) -> str:
    return f"sources/{JURISDICTION}/{DOCUMENT_CLASS.value}/{version}/"


def _original_sections(
    retained_base: Path, successor: Successor
) -> tuple[tuple[tuple[str, str], ...], dict[str, bytes]]:
    """Return the original selection order and its verified retained bytes."""
    store = CorpusArtifactStore(retained_base)
    inventory = load_source_inventory(
        store.inventory_path(JURISDICTION, DOCUMENT_CLASS, successor.original_version)
    )
    sections: list[tuple[str, str]] = []
    retained: dict[str, bytes] = {}
    for item in inventory:
        metadata = item.metadata or {}
        law_code = str(metadata["law_code"])
        section = str(metadata["section"])
        relative_name = _california_section_html_relative_name(law_code, section)
        if item.source_path != _source_key(successor.original_version) + relative_name:
            raise ValueError(f"unexpected retained source path {item.source_path!r}")
        payload = (retained_base / item.source_path).read_bytes()
        if sha256_bytes(payload) != item.sha256:
            raise ValueError(f"retained bytes changed for {item.citation_path}")
        if not _california_html_has_section(payload):
            # The adapter fetches LegInfo again for a cached page without a section.
            raise ValueError(f"retained page lacks single_law_section: {item.citation_path}")
        sections.append((law_code, section))
        retained[relative_name] = payload
    selected = tuple(sections)
    run_id = _california_sections_run_id(successor.original_prefix, selected)
    if run_id != successor.original_version:
        raise ValueError(f"inventory order does not reproduce {successor.original_version}")
    return selected, retained


def _detach_parents(base: Path, successor: Successor) -> None:
    version = successor.original_version
    if successor.parent_handling == PARENT_SELF_CONTAINED:
        _load_self_contain_module().self_contain_scope(
            base,
            jurisdiction=JURISDICTION,
            document_class=DOCUMENT_CLASS.value,
            version=version,
        )
        return
    store = CorpusArtifactStore(base)
    provisions_path = store.provisions_path(JURISDICTION, DOCUMENT_CLASS, version)
    store.write_provisions(
        provisions_path,
        (
            replace(record, parent_citation_path=None, parent_id=None)
            for record in load_provisions(provisions_path)
        ),
    )


def _move_to_successor_version(stage: Path, base: Path, successor: Successor) -> int:
    """Write the staged scope under the successor version; return its file count."""
    old, new = successor.original_version, successor.version
    old_key, new_key = _source_key(old), _source_key(new)

    def rekey(source_path: str) -> str:
        if not source_path.startswith(old_key):
            raise ValueError(f"source path outside {old_key}: {source_path!r}")
        return new_key + source_path.removeprefix(old_key)

    stage_store, store = CorpusArtifactStore(stage), CorpusArtifactStore(base)
    items = tuple(
        replace(item, source_path=rekey(item.source_path))
        for item in load_source_inventory(
            stage_store.inventory_path(JURISDICTION, DOCUMENT_CLASS, old)
        )
    )
    records = tuple(
        replace(record, version=new, source_path=rekey(record.source_path or ""))
        for record in load_provisions(
            stage_store.provisions_path(JURISDICTION, DOCUMENT_CLASS, old)
        )
    )
    for item in items:
        staged = stage / (old_key + item.source_path.removeprefix(new_key))
        store.write_bytes(base / item.source_path, staged.read_bytes())
    coverage = compare_provision_coverage(
        items,
        records,
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS.value,
        version=new,
    )
    if not coverage.complete:
        raise ValueError(f"coverage is incomplete for {new}")
    store.write_inventory(store.inventory_path(JURISDICTION, DOCUMENT_CLASS, new), items)
    store.write_provisions(store.provisions_path(JURISDICTION, DOCUMENT_CLASS, new), records)
    store.write_json(store.coverage_path(JURISDICTION, DOCUMENT_CLASS, new), coverage.to_mapping())
    return len(items) + 3


def build_successor(base: Path, retained_base: Path, successor: Successor) -> dict[str, Any]:
    """Write one successor scope under ``base`` from the original's retained bytes."""
    sections, retained = _original_sections(retained_base, successor)
    with TemporaryDirectory(prefix="ca-leginfo-preserve-tables-") as work_name:
        cache_root = Path(work_name) / "cache"
        stage = Path(work_name) / "corpus"
        cache_store = CorpusArtifactStore(cache_root)
        for relative_name, payload in retained.items():
            cache_store.write_bytes(cache_root / relative_name, payload)
        report = extract_california_code_sections(
            CorpusArtifactStore(stage),
            version=successor.original_prefix,
            sections=tuple(f"{law_code}:{section}" for law_code, section in sections),
            source_as_of=successor.capture_date,
            expression_date=successor.capture_date,
            download_dir=cache_root,
            request_delay_seconds=0,
            preserve_tables=True,
        )
        if report.errors:
            raise ValueError(f"California section extractor errors: {report.errors}")
        if not report.coverage.complete or report.provisions_written != len(sections):
            raise ValueError(f"unexpected extract report: {report.coverage.to_mapping()}")
        if report.provisions_path.name != f"{successor.original_version}.jsonl":
            raise ValueError(f"adapter wrote {report.provisions_path.name}")
        for relative_name, payload in retained.items():
            # Byte equality shows every page came from the retained cache, not LegInfo.
            staged = stage / _source_key(successor.original_version) / relative_name
            if staged.read_bytes() != payload:
                raise ValueError(f"staged source {relative_name} differs from retained bytes")
        _detach_parents(stage, successor)
        files = _move_to_successor_version(stage, base, successor)
    return {
        "original_version": successor.original_version,
        "version": successor.version,
        "sections": len(sections),
        "files": files,
        "capture_date": successor.capture_date,
        "parent_handling": successor.parent_handling,
    }


def reproduce(base: Path, retained_base: Path | None = None) -> dict[str, Any]:
    target_base = base.resolve()
    input_base = (retained_base or RETAINED_BASE).resolve()
    scopes = [build_successor(target_base, input_base, successor) for successor in SUCCESSORS]
    return {"base": str(target_base), "command": REPRO_COMMAND, "scopes": scopes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, required=True, help="Destination corpus base.")
    parser.add_argument(
        "--retained-base",
        type=Path,
        help="Corpus base holding the original scopes; defaults to repository data/corpus.",
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.retained_base), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
