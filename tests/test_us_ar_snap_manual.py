import json
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ar-snap-manual.yaml"
VERSION = "2026-07-16-ar-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ar" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ar" / "manual" / f"{VERSION}.json"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-ar" / "manual" / f"{VERSION}.json"


def test_arkansas_snap_scope_retains_complete_current_policy_set() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    document_items = [item for item in inventory if item["metadata"]["kind"] == "document"]

    assert len(documents) == 7
    assert Counter(document["source_format"] for document in documents) == {
        "pdf": 4,
        "html": 3,
    }
    assert {document["source_id"] for document in documents} == {
        "ar-dhs-snap-policy-manual",
        "ar-dhs-snap-manual-appendices",
        "ar-dhs-snap-july-2026-final-filing",
        "ar-dhs-snap-quick-reference-fy2026",
        "ar-dhs-snap-nutrition-waiver",
        "ar-dhs-snap-nutrition-waiver-faq",
        "ar-dhs-snap-time-limit-rules",
    }
    assert len(document_items) == len(documents)
    assert all(
        (CORPUS_ROOT / item["source_path"]).is_relative_to(SOURCE_ROOT)
        for item in document_items
    )
    block_counts = {
        item["citation_path"]: item["metadata"]["block_count"] for item in document_items
    }
    assert {
        "us-ar/manual/dhs/snap-policy-manual": 624,
        "us-ar/manual/dhs/snap-manual-appendices": 84,
        "us-ar/manual/dhs/snap-july-2026-final-filing": 117,
        "us-ar/manual/dhs/snap-quick-reference-fy2026": 2,
    }.items() <= block_counts.items()
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == []
    assert coverage["extra_provisions"] == []
    assert coverage["source_count"] == coverage["provision_count"] == len(inventory)
