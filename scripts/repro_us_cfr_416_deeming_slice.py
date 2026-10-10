"""Reproduce the approved 20 CFR Part 416 deeming slice from official snapshots."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.ecfr import (
    build_ecfr_inventory_from_structures,
    iter_ecfr_title_provisions,
    part_targets_from_structure,
)
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_BASE = REPO_ROOT / "data" / "corpus"

JURISDICTION = "us"
DOCUMENT_CLASS = DocumentClass.REGULATION
VERSION = "2026-07-23-title-20-part-416"
SOURCE_AS_OF = "2026-07-14"
EXPRESSION_DATE = "2026-07-14"
TITLE = 20
PART = "416"
EXPECTED_FULL_PATH_COUNT = 622

STRUCTURE_RELATIVE_PATH = Path(
    "sources/us/regulation/2026-07-23-title-20-part-416/"
    "ecfr/title-20.structure.json"
)
XML_RELATIVE_PATH = Path(
    "sources/us/regulation/2026-07-23-title-20-part-416/"
    "ecfr/title-20-part-416.xml"
)
INVENTORY_RELATIVE_PATH = Path(
    "inventory/us/regulation/2026-07-23-title-20-part-416.json"
)
PROVISIONS_RELATIVE_PATH = Path(
    "provisions/us/regulation/2026-07-23-title-20-part-416.jsonl"
)
COVERAGE_RELATIVE_PATH = Path(
    "coverage/us/regulation/2026-07-23-title-20-part-416.json"
)

EXPECTED_SOURCE_SHA256 = {
    STRUCTURE_RELATIVE_PATH: (
        "f3946c95dd8e4c88f51910538b7c99e98f6563fcd667786771c34d14801b1228"
    ),
    XML_RELATIVE_PATH: (
        "11ec5a3f11457ebdca99bc958c9666740590a544cd44bd88e681f29b9bf41b26"
    ),
}

APPROVED_CITATION_PATHS = (
    "us/regulation/20/416",
    "us/regulation/20/416/subpart-K",
    "us/regulation/20/416/1149",
    "us/regulation/20/416/1160",
    "us/regulation/20/416/1161",
    "us/regulation/20/416/1163",
    "us/regulation/20/416/1167",
    "us/regulation/20/416/subpart-L",
    "us/regulation/20/416/1202",
    "us/regulation/20/416/1207",
    "us/regulation/20/416/subpart-R",
    "us/regulation/20/416/1801",
    "us/regulation/20/416/1802",
    "us/regulation/20/416/1806",
)

CONTAINER_COMPONENT_COUNTS = {
    "us/regulation/20/416": 10,
    "us/regulation/20/416/subpart-K": 5,
    "us/regulation/20/416/subpart-L": 2,
    "us/regulation/20/416/subpart-R": 3,
}

GENERATED_RELATIVE_PATHS = (
    STRUCTURE_RELATIVE_PATH,
    XML_RELATIVE_PATH,
    INVENTORY_RELATIVE_PATH,
    PROVISIONS_RELATIVE_PATH,
    COVERAGE_RELATIVE_PATH,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild the approved 20 CFR Part 416 deeming slice from the "
            "retained official eCFR structure and XML snapshots."
        )
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=DEFAULT_CORPUS_BASE,
        help="Destination corpus base (default: repository data/corpus).",
    )
    parser.add_argument(
        "--source-base",
        type=Path,
        default=None,
        help=(
            "Corpus base containing the hash-pinned official source snapshots "
            "(default: --base)."
        ),
    )
    return parser.parse_args()


def _read_verified_source(source_base: Path, relative_path: Path) -> bytes:
    source_path = source_base / relative_path
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError(f"official source must be a regular non-symlink file: {source_path}")
    content = source_path.read_bytes()
    digest = sha256_bytes(content)
    expected_digest = EXPECTED_SOURCE_SHA256[relative_path]
    if digest != expected_digest:
        raise ValueError(
            f"official source hash mismatch for {source_path}: "
            f"expected {expected_digest}, got {digest}"
        )
    return content


def _record_component(record: ProvisionRecord) -> str:
    parts = tuple(part for part in (record.heading, record.body) if part and part.strip())
    if not parts:
        raise ValueError(f"empty materialization component: {record.citation_path}")
    return "\n\n".join(parts)


def _materialize_selected_containers(
    records: tuple[ProvisionRecord, ...],
) -> tuple[ProvisionRecord, ...]:
    records_by_path = {record.citation_path: record for record in records}
    if len(records_by_path) != len(records):
        raise ValueError("duplicate provision citation paths")

    container_paths = sorted(
        CONTAINER_COMPONENT_COUNTS,
        key=lambda citation_path: records_by_path[citation_path].level or 0,
        reverse=True,
    )
    for container_path in container_paths:
        container = records_by_path[container_path]
        children = tuple(
            record
            for record in records_by_path.values()
            if record.parent_citation_path == container_path
        )
        if not children:
            raise ValueError(f"selected container has no children: {container_path}")

        component_count = 0
        components: list[str] = []
        for child in children:
            components.append(_record_component(child))
            if child.citation_path in CONTAINER_COMPONENT_COUNTS:
                component_count += int(
                    (child.metadata or {})["body_materialization_component_count"]
                )
            else:
                component_count += 1

        expected_count = CONTAINER_COMPONENT_COUNTS[container_path]
        if component_count != expected_count:
            raise ValueError(
                f"unexpected component count for {container_path}: "
                f"expected {expected_count}, got {component_count}"
            )
        metadata = dict(container.metadata or {})
        metadata.update(
            {
                "body_materialization_algorithm": (
                    "official-descendant-heading-body-join-v1"
                ),
                "body_materialization_component_count": component_count,
                "body_status": "materialized_from_official_descendants",
            }
        )
        records_by_path[container_path] = replace(
            container,
            body="\n\n".join(components),
            metadata=metadata,
        )

    materialized = tuple(records_by_path[path] for path in APPROVED_CITATION_PATHS)
    if any(not record.body or not record.body.strip() for record in materialized):
        raise ValueError("every selected provision must have a non-empty body")
    return materialized


def _build_staged_scope(
    staging_base: Path,
    structure_bytes: bytes,
    xml_bytes: bytes,
) -> dict[str, Any]:
    staging_store = CorpusArtifactStore(staging_base)
    staging_store.write_bytes(staging_base / STRUCTURE_RELATIVE_PATH, structure_bytes)
    staging_store.write_bytes(staging_base / XML_RELATIVE_PATH, xml_bytes)

    structure = json.loads(structure_bytes)
    xml_content = xml_bytes.decode("utf-8")
    xml_digest = sha256_bytes(xml_bytes)
    full_inventory = build_ecfr_inventory_from_structures(
        (structure,),
        only_part=PART,
        run_id=VERSION,
        source_sha256_by_title={TITLE: xml_digest},
        # The pinned 622-path hierarchy and approved slice contain sections
        # and their containers; subpart appendices are outside this scope.
        include_appendices=False,
    )
    if len(full_inventory.items) != EXPECTED_FULL_PATH_COUNT:
        raise ValueError(
            f"official hierarchy changed: expected {EXPECTED_FULL_PATH_COUNT} paths, "
            f"got {len(full_inventory.items)}"
        )

    full_paths = {item.citation_path for item in full_inventory.items}
    targets = tuple(
        target
        for target in part_targets_from_structure(structure)
        if target.title == TITLE and target.part == PART
    )
    full_records = tuple(
        iter_ecfr_title_provisions(
            xml_content,
            targets,
            version=VERSION,
            source_path=str(XML_RELATIVE_PATH),
            source_as_of=SOURCE_AS_OF,
            expression_date=EXPRESSION_DATE,
            allowed_citation_paths=full_paths,
        )
    )
    if len(full_records) != EXPECTED_FULL_PATH_COUNT:
        raise ValueError(
            f"official extraction changed: expected {EXPECTED_FULL_PATH_COUNT} "
            f"provisions, got {len(full_records)}"
        )

    approved = set(APPROVED_CITATION_PATHS)
    inventory = tuple(
        item for item in full_inventory.items if item.citation_path in approved
    )
    records = tuple(
        record for record in full_records if record.citation_path in approved
    )
    if tuple(item.citation_path for item in inventory) != APPROVED_CITATION_PATHS:
        raise ValueError("approved inventory paths are missing or out of source order")
    if tuple(record.citation_path for record in records) != APPROVED_CITATION_PATHS:
        raise ValueError("approved provision paths are missing or out of source order")

    records = _materialize_selected_containers(records)
    inventory_path = staging_base / INVENTORY_RELATIVE_PATH
    provisions_path = staging_base / PROVISIONS_RELATIVE_PATH
    coverage_path = staging_base / COVERAGE_RELATIVE_PATH
    staging_store.write_inventory(inventory_path, inventory)
    staging_store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        inventory,
        records,
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS.value,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError(f"incomplete selected coverage: {coverage.to_mapping()}")
    staging_store.write_json(coverage_path, coverage.to_mapping())

    return {
        "full_source_count": len(full_inventory.items),
        "selected_count": len(records),
        "container_component_counts": CONTAINER_COMPONENT_COUNTS,
        "coverage_complete": coverage.complete,
    }


def reproduce(base: Path, source_base: Path) -> dict[str, Any]:
    base = base.resolve()
    source_base = source_base.resolve()
    source_bytes = {
        relative_path: _read_verified_source(source_base, relative_path)
        for relative_path in EXPECTED_SOURCE_SHA256
    }

    with TemporaryDirectory(prefix="repro-us-cfr-416-") as temp_dir:
        staging_base = Path(temp_dir) / "corpus"
        summary = _build_staged_scope(
            staging_base,
            source_bytes[STRUCTURE_RELATIVE_PATH],
            source_bytes[XML_RELATIVE_PATH],
        )
        target_store = CorpusArtifactStore(base)
        hashes: dict[str, str] = {}
        for relative_path in GENERATED_RELATIVE_PATHS:
            content = (staging_base / relative_path).read_bytes()
            target_store.write_bytes(base / relative_path, content)
            hashes[str(relative_path)] = sha256_bytes(content)

    summary["base"] = str(base)
    summary["files"] = hashes
    return summary


def main() -> int:
    args = _parse_args()
    result = reproduce(args.base, args.source_base or args.base)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
