"""Backfill deterministic provision identity for one committed corpus scope.

Stamps the legacy deterministic ``id`` (and ``parent_id`` where a
``parent_citation_path`` is present) onto every row of one committed
provisions JSONL scope, matching what the fixed writers now emit. The
Supabase loader converges these legacy deterministic UUIDs to their
version-qualified form at load time, so stamping is metadata-only: no row
text, citation path, count, or hierarchy changes.

Fails closed if a row already carries a non-deterministic explicit id, or if
any parent link does not resolve inside the same scope file.

Usage:

    uv run python scripts/backfill_provision_identity.py \
      --base data/corpus \
      --jurisdiction us-ca \
      --document-class regulation \
      --version 2026-07-13-recovery

The rewritten scope must be re-signed with
``axiom-corpus-ingest sign-ingest-manifest`` from a clean checkout.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from axiom_corpus.corpus.artifacts import CorpusArtifactStore  # noqa: E402
from axiom_corpus.corpus.models import ProvisionRecord  # noqa: E402
from axiom_corpus.corpus.supabase import deterministic_provision_id  # noqa: E402


def backfill_scope_identity(
    base: Path,
    *,
    jurisdiction: str,
    document_class: str,
    version: str,
) -> dict[str, int]:
    store = CorpusArtifactStore(base)
    path = store.provisions_path(jurisdiction, document_class, version)
    records = [
        ProvisionRecord.from_mapping(json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    by_path = {record.citation_path: record for record in records}
    if len(by_path) != len(records):
        raise ValueError(f"{path} contains duplicate citation paths")

    ids_stamped = 0
    parent_ids_stamped = 0
    repaired: list[ProvisionRecord] = []
    for record in records:
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
        repaired.append(replace(record, id=expected_id, parent_id=expected_parent_id))

    store.write_provisions(path, repaired)
    return {
        "rows": len(repaired),
        "ids_stamped": ids_stamped,
        "parent_ids_stamped": parent_ids_stamped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--document-class", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    summary = backfill_scope_identity(
        args.base,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        version=args.version,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
