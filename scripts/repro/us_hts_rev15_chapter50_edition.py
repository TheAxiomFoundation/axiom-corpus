"""Build a disjoint source-edition scope; does not sign or promote a release.

The citation root identifies retained 2026 Revision 15 source evidence, not a
new legal heading. Existing HTS coordinates and historical scopes are untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from scripts.repro import us_hts_tariff_full_schedule_2026_rev15 as full

VERSION = "2026-10-01-usitc-hts-2026-rev15-chapter50-edition"
ROOT = "us/statute/hts-2026-rev15/chapter-50"
SNAPSHOT = full.SNAPSHOTS[0]


def build_scope(base: Path, retained_source: Path) -> dict[str, object]:
    content = retained_source.read_bytes()
    if hashlib.sha256(content).hexdigest() != SNAPSHOT.sha256:
        raise ValueError("retained Rev15 snapshot SHA mismatch")
    rows = json.loads(content)
    if not isinstance(rows, list) or len(rows) != SNAPSHOT.total_rows:
        raise ValueError("unexpected full-schedule row census")
    all_blocks = full._target_blocks(rows)
    if len(all_blocks) != SNAPSHOT.target_rows:
        raise ValueError("unexpected full-schedule provision census")
    selected = [b for b in all_blocks if full._chapter_key(str(b.metadata["htsno"])) == "50"]
    if len(selected) != 41 or len({b.metadata["htsno"] for b in selected}) != 41:
        raise ValueError("chapter 50 must contain exactly 41 unique source rows")
    blocks = tuple(replace(b, ordinal=i) for i, b in enumerate(selected, 1))
    source = replace(
        full._snapshot_source(SNAPSHOT),
        source_id="usitc-hts-2026-rev15-chapter50-edition",
        citation_path=ROOT,
        title="HTS 2026 Revision 15 — chapter 50 source-edition evidence",
        metadata={
            **full._row_metadata_base(),
            "normalization_scope": "chapter-50-source-edition-all-htsno-rows",
        },
    )
    source_path = Path("sources/us/statute") / VERSION / "usitc-hts" / SNAPSHOT.official_filename
    inventory_path = Path("inventory/us/statute") / f"{VERSION}.json"
    provisions_path = Path("provisions/us/statute") / f"{VERSION}.jsonl"
    coverage_path = Path("coverage/us/statute") / f"{VERSION}.json"
    paths = (source_path, inventory_path, provisions_path, coverage_path)
    if any((base / p).exists() or (base / p).is_symlink() for p in paths):
        raise ValueError("refusing to overwrite an existing scope artifact")
    common = {
        "source_key": source_path.as_posix(),
        "source_format": "json",
        "content_type": "application/json",
        "final_url": SNAPSHOT.download_url,
    }
    inventory = list(
        documents._inventory_items(source, blocks=blocks, source_sha=SNAPSHOT.sha256, **common)
    )
    records = list(
        documents._provision_records(
            source,
            blocks=blocks,
            version=VERSION,
            source_as_of=full.SOURCE_AS_OF,
            expression_date=SNAPSHOT.expression_date,
            **common,
        )
    )
    evidence = {
        "source_identity_kind": "edition-qualified-evidence",
        "retained_snapshot_sha256": SNAPSHOT.sha256,
        "source_edition": "2026HTSRev15",
        "chapter": "50",
        "members": [
            {
                "htsno": b.metadata["htsno"],
                "source_row_index": b.metadata["row_index"],
                "body_sha256": hashlib.sha256(b.body.encode()).hexdigest(),
            }
            for b in blocks
        ],
    }
    records[0] = replace(records[0], metadata={**(records[0].metadata or {}), **evidence})
    inventory[0] = replace(inventory[0], metadata={**(inventory[0].metadata or {}), **evidence})
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction="us",
        document_class="statute",
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError("incomplete chapter scope coverage")
    # Refuse existing outputs and symlinked ancestors before creating files.
    base = base.absolute()
    if any(parent.is_symlink() for parent in (base, *base.parents)):
        raise ValueError("output path must not contain symlinks")
    if base.exists():
        raise ValueError("output directory must be fresh")
    base.mkdir()
    store = CorpusArtifactStore(base)
    store.write_bytes(base / source_path, content)
    store.write_inventory(base / inventory_path, inventory)
    store.write_provisions(base / provisions_path, records)
    store.write_json(base / coverage_path, coverage.to_mapping())
    return {
        "version": VERSION,
        "citation_root": ROOT,
        "rows": len(records),
        "artifacts": [p.as_posix() for p in paths],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retained-source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_scope(args.output, args.retained_source), indent=2))
