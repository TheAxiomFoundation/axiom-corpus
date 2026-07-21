import csv
import json
from collections import Counter
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ok-snap-policy.yaml"
VERSION = "2026-07-21-ok-snap-policy"
SOURCE_DIR = CORPUS_ROOT / "sources/us-ok/policy" / VERSION / "official-documents"
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-ok/policy" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-ok/policy" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-ok/policy" / f"{VERSION}.json"

EXPECTED_SOURCE_SHA256 = {
    "ok-oac-340-10-snap-dependencies.json": "c21811db09ecf6870b7f230277c16eab5f78e3dea96d40b949863e4699e78879",
    "ok-oac-340-2-snap-dependencies.json": "1ab7049c71f0b6c6abd12c9bfd393136a922b214bfbd65573b2907249fee42ec",
    "ok-oac-340-65-snap-dependencies.json": "35638b78a8c28e64748bd76092c15199bb57f4a72d9b3b54dd2df7d1304e3b8c",
    "okdhs-appendix-b-2-deadlines-for-case-actions.pdf": "d35ff5d9d5374165b6a936f5a7b1c55e452cd6d020f818f1929fc5a32364ebe8",
    "okdhs-appendix-c-1-schedule-of-maximum-income.pdf": "f4fdfd4924b1f3193fecd195ac4a2fbea4dbb752a82b69ed2e09092c5f6aea67",
    "okdhs-appendix-c-3-a-disaster-income-limits-and-allotments.pdf": "1862579b8fcc55fe722037d1877b1c04efe5c137a407deaff77c522af614d571",
    "okdhs-appendix-c-3-allotment-table-data.csv": "a2f9183f5ec73554545498a5b1e75850cee6e14b4d723daf744a384669a618ea",
    "okdhs-appendix-c-3-allotment-table-landing-page.html": "36e93feb7607a188ac86627b480213f969d1d5e4d285c0de81c6808f1fd307e4",
    "okdhs-appendix-c-3-snap-allotment-table.pdf": "f87dca203cb015fbd90f45a2777dbe06e4a4cf9608e3e89a16fc6a43278205fe",
    "okdhs-appendix-d-4-c-indian-food-distribution-programs.pdf": "b2ad5bf13b05f68d958947443f8eec7eba692d2c4aa79b85a7400c283c05c3dc",
}
EXPECTED_PROVISION_COUNTS = {
    "ok-oac-340-10-snap-dependencies": 16,
    "ok-oac-340-2-snap-dependencies": 62,
    "ok-oac-340-65-snap-dependencies": 9,
    "okdhs-appendix-b-2-deadlines-for-case-actions": 2,
    "okdhs-appendix-c-1-schedule-of-maximum-income": 9,
    "okdhs-appendix-c-3-a-disaster-income-limits-and-allotments": 2,
    "okdhs-appendix-c-3-allotment-table-data": 2,
    "okdhs-appendix-c-3-allotment-table-landing-page": 2,
    "okdhs-appendix-c-3-snap-allotment-table": 4,
    "okdhs-appendix-d-4-c-indian-food-distribution-programs": 5,
}


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_oklahoma_policy_manifest_uses_current_official_sources() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]

    assert len(documents) == 10
    assert all(document["jurisdiction"] == "us-ok" for document in documents)
    assert all(document["document_class"] == "policy" for document in documents)
    assert all(document["source_as_of"] == "2026-07-21" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(
        document["source_url"].startswith(
            ("https://oklahoma.gov/", "https://rules.ok.gov/")
        )
        for document in documents
    )


def test_oklahoma_policy_retains_complete_official_source_snapshots() -> None:
    actual_sources = {path.name: sha256_file(path) for path in SOURCE_DIR.iterdir()}

    assert actual_sources == EXPECTED_SOURCE_SHA256
    assert len(json.loads((SOURCE_DIR / "ok-oac-340-2-snap-dependencies.json").read_text())) == 733
    assert len(json.loads((SOURCE_DIR / "ok-oac-340-10-snap-dependencies.json").read_text())) == 190
    assert len(json.loads((SOURCE_DIR / "ok-oac-340-65-snap-dependencies.json").read_text())) == 95
    with (SOURCE_DIR / "okdhs-appendix-c-3-allotment-table-data.csv").open(
        encoding="utf-8-sig", newline=""
    ) as csv_file:
        assert len(list(csv.reader(csv_file))) == 1790


def test_oklahoma_policy_extracts_only_cited_active_oac_dependencies() -> None:
    sections_by_source: dict[str, list[dict]] = {}
    for provision in _provisions():
        if provision["kind"] == "section":
            sections_by_source.setdefault(provision["source_id"], []).append(provision)

    chapter_2 = sections_by_source["ok-oac-340-2-snap-dependencies"]
    chapter_10 = sections_by_source["ok-oac-340-10-snap-dependencies"]
    chapter_65 = sections_by_source["ok-oac-340-65-snap-dependencies"]
    assert len(chapter_2) == 61
    assert len(chapter_10) == 15
    assert len(chapter_65) == 8
    assert all(row["metadata"]["sectionNum"].startswith("340:2-5-") for row in chapter_2)
    assert {"340:2-5-63", "340:2-5-65", "340:2-5-76"} <= {
        row["metadata"]["sectionNum"] for row in chapter_2
    }
    assert {"340:10-1-3", "340:10-4-1", "340:10-14-1"} <= {
        row["metadata"]["sectionNum"] for row in chapter_10
    }
    assert {"340:65-3-1", "340:65-3-2.1", "340:65-3-4", "340:65-3-5"} <= {
        row["metadata"]["sectionNum"] for row in chapter_65
    }
    assert all(
        row["metadata"]["statusName"] not in {"Revoked", "Reserved"}
        for rows in sections_by_source.values()
        for row in rows
    )


def test_oklahoma_policy_generated_scope_is_complete() -> None:
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    assert Counter(row["source_id"] for row in rows) == EXPECTED_PROVISION_COUNTS
    assert len(rows) == len(inventory) == 113
    assert len({row["citation_path"] for row in rows}) == 113
    allotment_rows = next(
        row
        for row in rows
        if row["source_id"] == "okdhs-appendix-c-3-allotment-table-data"
        and row["kind"] == "sheet"
    )
    assert allotment_rows["metadata"]["row_count"] == 1789
    assert "1790 | 5957-5960" in allotment_rows["body"]
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == 113
    assert coverage["provision_count"] == 113
