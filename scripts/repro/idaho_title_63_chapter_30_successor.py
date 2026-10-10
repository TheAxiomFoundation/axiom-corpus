#!/usr/bin/env python3
"""Rebuild the retained Idaho income-tax sections as a native successor scope."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass
from axiom_corpus.corpus.state_adapters.idaho import (
    IDAHO_SECTION_SOURCE_FORMAT,
    IdahoChapter,
    IdahoSectionListing,
    IdahoTitle,
    _chapter_inventory_item,
    _chapter_record,
    _RecordedSource,
    _section_inventory_item,
    _section_record,
    _title_inventory_item,
    _title_record,
    parse_idaho_section_page,
)

JURISDICTION = "us-id"
DOCUMENT_CLASS = DocumentClass.STATUTE
SOURCE_VERSION = "2026-07-13-recovery"
VERSION = "2026-07-31-id-title-63-chapter-30-successor"
SOURCE_AS_OF = "2026-07-13"
EXPRESSION_DATE = "2026-07-13"
SOURCE_IDS = (
    "us-id-code-63-3022d",
    "us-id-code-63-3022e",
    "us-id-code-63-3024",
    "us-id-code-63-3024a",
    "us-id-code-63-3025d",
)
SECTIONS = ("63-3022D", "63-3022E", "63-3024", "63-3024A", "63-3025D")
BASE_RELEASE = "us-rulespec-2026-07-24-snap-cms-pit-union"
RELEASE = "us-rulespec-2026-07-31-idaho-statutes-current"


def _source_key(version: str, leaf: str) -> str:
    return f"sources/{JURISDICTION}/{DOCUMENT_CLASS.value}/{version}/{leaf}"


def build_scope(*, base: Path, source_base: Path) -> tuple[Path, Path, Path]:
    """Build one self-contained successor from the exact retained HTML bytes."""
    store = CorpusArtifactStore(base)
    old_root = source_base / "sources" / JURISDICTION / DOCUMENT_CLASS.value / SOURCE_VERSION
    new_root = base / "sources" / JURISDICTION / DOCUMENT_CLASS.value / VERSION
    inventories = []
    records = []
    parsed_sections = []

    for ordinal, (source_id, section_number) in enumerate(
        zip(SOURCE_IDS, SECTIONS, strict=True), 1
    ):
        source_leaf = f"official-documents/{source_id}"
        provenance_leaf = f"provenance/{source_id}.json"
        raw = (old_root / source_leaf).read_bytes()
        provenance_bytes = (old_root / provenance_leaf).read_bytes()
        provenance = json.loads(provenance_bytes)
        expected_sha = str(provenance["sha256"])
        source_path = store.source_path(JURISDICTION, DOCUMENT_CLASS, VERSION, source_leaf)
        actual_sha = store.write_bytes(source_path, raw)
        if actual_sha != expected_sha:
            raise ValueError(
                f"retained Idaho source hash changed for {section_number}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        store.write_bytes(new_root / provenance_leaf, provenance_bytes)
        source = _RecordedSource(
            source_url=str(provenance["url"]),
            source_path=_source_key(VERSION, source_leaf),
            source_format=IDAHO_SECTION_SOURCE_FORMAT,
            sha256=actual_sha,
        )
        listing = IdahoSectionListing(
            title_number="63",
            chapter="30",
            section=section_number,
            heading=f"Section {section_number}",
            source_url=source.source_url,
            ordinal=ordinal,
        )
        section = parse_idaho_section_page(
            raw,
            listing=listing,
            source=source,
            expression_date=EXPRESSION_DATE,
        )
        if not section.body:
            raise ValueError(f"Idaho section {section_number} has no substantive body")
        parsed_sections.append(section)

    anchor = parsed_sections[0]
    title = IdahoTitle(
        number="63",
        heading="REVENUE AND TAXATION",
        source_url=anchor.source_url,
        source_path=anchor.source_path,
        source_format=anchor.source_format,
        sha256=anchor.sha256,
        ordinal=1,
    )
    chapter = IdahoChapter(
        title_number="63",
        title_heading=title.heading,
        chapter="30",
        heading="INCOME TAX",
        source_url=anchor.source_url,
        source_path=anchor.source_path,
        source_format=anchor.source_format,
        sha256=anchor.sha256,
        ordinal=1,
    )
    inventories.extend((_title_inventory_item(title), _chapter_inventory_item(chapter)))
    records.extend(
        (
            _title_record(
                title,
                version=VERSION,
                source_as_of=SOURCE_AS_OF,
                expression_date=EXPRESSION_DATE,
            ),
            _chapter_record(
                chapter,
                version=VERSION,
                source_as_of=SOURCE_AS_OF,
                expression_date=EXPRESSION_DATE,
            ),
        )
    )
    for section in parsed_sections:
        inventories.append(_section_inventory_item(section))
        records.append(
            _section_record(
                section,
                version=VERSION,
                source_as_of=SOURCE_AS_OF,
                expression_date=EXPRESSION_DATE,
            )
        )

    # The first retained section page proves the title/chapter headings, but the
    # two container rows must not claim that its section URL is their own URL.
    inventories[0] = replace(
        inventories[0],
        metadata={**(inventories[0].metadata or {}), "container_source": "retained section header"},
    )
    inventories[1] = replace(
        inventories[1],
        metadata={**(inventories[1].metadata or {}), "container_source": "retained section header"},
    )
    inventory_path = store.inventory_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    provisions_path = store.provisions_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    coverage_path = store.coverage_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    store.write_inventory(inventory_path, inventories)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(inventories),
        tuple(records),
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS.value,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError("Idaho successor scope does not have complete coverage")
    store.write_json(coverage_path, coverage.to_mapping())
    return inventory_path, provisions_path, coverage_path


def write_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    """Write a named-release successor replacing only the Idaho statute scope."""
    source_path = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    replacements = 0
    for scope in payload["scopes"]:
        if (
            scope.get("jurisdiction") == JURISDICTION
            and scope.get("document_class") == DOCUMENT_CLASS.value
            and scope.get("version") == SOURCE_VERSION
        ):
            scope["version"] = VERSION
            replacements += 1
    if replacements != 1:
        raise ValueError(f"expected one Idaho statute release selector, found {replacements}")
    payload["name"] = RELEASE
    payload["description"] = (
        f"Successor to {BASE_RELEASE}. It replaces only the malformed Idaho "
        "income-tax statute recovery scope with native section records rebuilt "
        "from the same retained official HTML bytes."
    )
    output = (output_dir or release_dir) / f"{RELEASE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--source-base", type=Path)
    parser.add_argument("--release-dir", type=Path, default=Path("manifests/releases"))
    args = parser.parse_args()
    source_base = args.source_base or args.base
    for path in build_scope(base=args.base, source_base=source_base):
        print(path)
    print(write_release(release_dir=args.release_dir))


if __name__ == "__main__":
    main()
