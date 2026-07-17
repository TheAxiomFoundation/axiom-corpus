"""Re-version one committed corpus scope, stamping deterministic identity.

Published scope keys are content-immutable — including keys frozen by burned
releases — so a committed scope can never be repaired in place once it has
been cut into a release (see corpus#365). This script copies one scope to a
fresh version identifier and stamps the legacy deterministic ``id`` (and
``parent_id`` where a ``parent_citation_path`` is present) onto every
provision row, matching what the fixed writers now emit. The Supabase loader
converges these legacy deterministic UUIDs to their version-qualified form at
load time.

The copy rewrites only: the ``version`` field, ``source_path`` references
into the scope's sources directory, and the stamped identity fields. Row
text, citation paths, ordering, counts, and hierarchy are unchanged; the
coverage report is regenerated for the new version and must stay complete.
Source snapshots are copied byte-identically. The original scope artifacts
are not touched.

Fails closed if a row already carries a non-deterministic explicit id, or if
any parent link does not resolve inside the same scope file.

Usage:

    uv run python scripts/reversion_scope_identity.py \
      --base data/corpus \
      --jurisdiction us-ca \
      --document-class regulation \
      --version 2026-07-13-recovery \
      --new-version 2026-07-13-recovery-r2026-07-17-identity

The new scope must be signed with ``axiom-corpus-ingest
sign-ingest-manifest`` from a clean checkout, and only enters production
when a release cut plan adopts the new scope key.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from axiom_corpus.corpus.artifacts import CorpusArtifactStore  # noqa: E402
from axiom_corpus.corpus.coverage import compare_provision_coverage  # noqa: E402
from axiom_corpus.corpus.models import (  # noqa: E402
    ProvisionRecord,
    SourceInventoryItem,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id  # noqa: E402


def reversion_scope_identity(
    base: Path,
    *,
    jurisdiction: str,
    document_class: str,
    version: str,
    new_version: str,
) -> dict[str, int]:
    if new_version == version:
        raise ValueError("new version must differ from the source version")
    store = CorpusArtifactStore(base)

    old_provisions = store.provisions_path(jurisdiction, document_class, version)
    new_provisions = store.provisions_path(jurisdiction, document_class, new_version)
    old_inventory = store.inventory_path(jurisdiction, document_class, version)
    new_inventory = store.inventory_path(jurisdiction, document_class, new_version)
    new_coverage = store.coverage_path(jurisdiction, document_class, new_version)
    old_sources = base / "sources" / jurisdiction / document_class / version
    new_sources = base / "sources" / jurisdiction / document_class / new_version
    for path in (new_provisions, new_inventory, new_coverage, new_sources):
        if path.exists():
            raise ValueError(f"target scope artifact already exists: {path}")

    old_sources_prefix = old_sources.relative_to(base).as_posix()
    new_sources_prefix = new_sources.relative_to(base).as_posix()

    def rewrite_source_path(value: str | None) -> str | None:
        if value is None:
            return None
        if value == old_sources_prefix or value.startswith(f"{old_sources_prefix}/"):
            return new_sources_prefix + value[len(old_sources_prefix) :]
        return value

    records = [
        ProvisionRecord.from_mapping(json.loads(line))
        for line in old_provisions.read_text().splitlines()
        if line.strip()
    ]
    by_path = {record.citation_path: record for record in records}
    if len(by_path) != len(records):
        raise ValueError(f"{old_provisions} contains duplicate citation paths")

    ids_stamped = 0
    parent_ids_stamped = 0
    reversioned: list[ProvisionRecord] = []
    for record in records:
        if record.version != version:
            raise ValueError(
                f"{record.citation_path} carries version {record.version}; "
                f"expected {version}"
            )
        expected_id = deterministic_provision_id(record.citation_path)
        if record.id is not None and record.id != expected_id:
            raise ValueError(
                f"{record.citation_path} carries explicit id {record.id}; "
                "refusing to overwrite a non-deterministic identity"
            )
        expected_parent_id: str | None = None
        if record.parent_citation_path:
            if record.parent_citation_path not in by_path:
                raise ValueError(
                    f"{record.citation_path} parent not in scope: "
                    f"{record.parent_citation_path}"
                )
            expected_parent_id = deterministic_provision_id(record.parent_citation_path)
            if record.parent_id is not None and record.parent_id != expected_parent_id:
                raise ValueError(
                    f"{record.citation_path} carries explicit parent_id "
                    f"{record.parent_id}; refusing to overwrite"
                )
        ids_stamped += int(record.id is None)
        parent_ids_stamped += int(expected_parent_id is not None and record.parent_id is None)
        reversioned.append(
            replace(
                record,
                version=new_version,
                source_path=rewrite_source_path(record.source_path),
                id=expected_id,
                parent_id=expected_parent_id,
            )
        )

    inventory_payload = json.loads(old_inventory.read_text())
    inventory_items = []
    for raw_item in inventory_payload["items"]:
        item = SourceInventoryItem.from_mapping(raw_item)
        inventory_items.append(replace(item, source_path=rewrite_source_path(item.source_path)))

    coverage = compare_provision_coverage(
        tuple(inventory_items),
        tuple(reversioned),
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=new_version,
    )
    if not coverage.complete:
        raise ValueError("re-versioned scope coverage is incomplete")
    if coverage.provision_count != len(records):
        raise ValueError("re-versioned scope changed the provision count")

    shutil.copytree(old_sources, new_sources)
    store.write_provisions(new_provisions, reversioned)
    store.write_inventory(new_inventory, inventory_items)
    store.write_json(new_coverage, coverage.to_mapping())

    sources_copied = sum(1 for path in new_sources.rglob("*") if path.is_file())
    return {
        "rows": len(reversioned),
        "ids_stamped": ids_stamped,
        "parent_ids_stamped": parent_ids_stamped,
        "inventory_items": len(inventory_items),
        "sources_copied": sources_copied,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--document-class", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--new-version", required=True)
    args = parser.parse_args()
    summary = reversion_scope_identity(
        args.base,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        version=args.version,
        new_version=args.new_version,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
