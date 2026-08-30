from __future__ import annotations

import json
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
VERSION = "2026-08-29-snap-obbb-alien-eligibility-qanda-1"
MANIFEST_PATH = REPO_ROOT / "manifests/us-snap-obbb-alien-eligibility-qanda-documents.yaml"
SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us/guidance"
    / VERSION
    / "official-documents/snap-obbb-alien-eligibility-qanda-1.pdf"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us/guidance" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us/guidance" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us/guidance" / f"{VERSION}.json"
IMPLEMENTATION_MEMO_SOURCE_ID = "snap-obbb-alien-eligibility-implementation-memo"
SOURCE_SHA256 = "7daaf18ea2a6f091ecd820a0a4e79543778a1d5f5ec4531cc5077acb288911e4"


def _manifest_metadata() -> dict:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return manifest["documents"][0]["metadata"]


def _provisions() -> list[dict]:
    return [
        json.loads(line)
        for line in PROVISIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_qanda_explicitly_clarifies_the_implementation_memo() -> None:
    manifest_metadata = _manifest_metadata()
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))["items"]
    provisions = _provisions()

    assert manifest_metadata["clarifies"] == IMPLEMENTATION_MEMO_SOURCE_ID
    assert "supersedes" not in manifest_metadata
    assert "supersedes_or_clarifies" not in manifest_metadata
    assert "provides additional information" in manifest_metadata["provenance_note"]
    assert "Question 5 was revised only to correct a typo" in (manifest_metadata["provenance_note"])
    cover_letter = provisions[1]["body"]
    assert "provides additional information on Section 10108" in cover_letter
    assert "FNS revised Question 5 due to a typo." in cover_letter
    for metadata in [
        *(item["metadata"] for item in inventory),
        *(provision["metadata"] for provision in provisions),
    ]:
        assert metadata["clarifies"] == IMPLEMENTATION_MEMO_SOURCE_ID
        assert "supersedes" not in metadata
        assert "supersedes_or_clarifies" not in metadata


def test_qanda_regenerated_scope_is_complete_and_preserves_source_bytes() -> None:
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))

    assert SOURCE_PATH.stat().st_size == 613_905
    assert sha256_file(SOURCE_PATH) == SOURCE_SHA256
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 6
    assert coverage["provision_count"] == 6
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
