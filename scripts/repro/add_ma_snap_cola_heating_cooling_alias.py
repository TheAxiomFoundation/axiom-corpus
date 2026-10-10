#!/usr/bin/env python3
"""Add the RuleSpec heating/cooling alias to an extracted MA SNAP COLA scope."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

JURISDICTION = "us-ma"
DOCUMENT_CLASS = "guidance"
PARENT = "us-ma/guidance/dta/policy-online/snap-cola/2025-10-01"
SOURCE_BLOCK = f"{PARENT}/block-11"
TARGET = f"{PARENT}/standard-utility-allowances/heating-cooling"
TARGET_BODY = "Heating/Cooling SUA increase to $914"


def _deterministic_id(citation_path: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"axiom:{citation_path}"))


def add_alias(*, base: Path, version: str) -> None:
    provisions_path = (
        base / "provisions" / JURISDICTION / DOCUMENT_CLASS / f"{version}.jsonl"
    )
    inventory_path = (
        base / "inventory" / JURISDICTION / DOCUMENT_CLASS / f"{version}.json"
    )
    records = [
        json.loads(line)
        for line in provisions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_citation = {record["citation_path"]: record for record in records}
    if len(by_citation) != len(records):
        raise ValueError("scope contains duplicate citation paths")
    if TARGET in by_citation:
        raise ValueError(f"target citation already exists: {TARGET}")
    parent = by_citation.get(PARENT)
    source = by_citation.get(SOURCE_BLOCK)
    if parent is None or source is None:
        raise ValueError("extracted scope is missing the expected parent or source block")
    if source.get("parent_id") != parent.get("id"):
        raise ValueError("source block is not attached to the expected parent")
    if TARGET_BODY not in str(source.get("body") or ""):
        raise ValueError("official source block does not contain the target statement")
    if any(record.get("version") != version for record in records):
        raise ValueError("scope contains a mismatched provision version")

    alias = copy.deepcopy(source)
    alias.update(
        {
            "body": TARGET_BODY,
            "citation_label": (
                "Massachusetts DTA Policy Online SNAP COLA 2025 "
                "Heating/Cooling SUA"
            ),
            "citation_path": TARGET,
            "heading": "Heating/Cooling Standard Utility Allowance",
            "id": _deterministic_id(TARGET),
        }
    )
    provisions_path.write_text(
        provisions_path.read_text(encoding="utf-8")
        + json.dumps(alias, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    items = inventory.get("items")
    if not isinstance(items, list):
        raise ValueError("scope inventory has no items list")
    source_item = next(
        (item for item in items if item.get("citation_path") == SOURCE_BLOCK), None
    )
    if source_item is None:
        raise ValueError("scope inventory is missing the source block")
    alias_item = copy.deepcopy(source_item)
    alias_item["citation_path"] = TARGET
    metadata = dict(alias_item.get("metadata") or {})
    metadata.update(
        {
            "kind": "block",
            "title": "Heating/Cooling Standard Utility Allowance",
        }
    )
    alias_item["metadata"] = metadata
    items.append(alias_item)
    inventory_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    add_alias(base=args.base, version=args.version)


if __name__ == "__main__":
    main()
