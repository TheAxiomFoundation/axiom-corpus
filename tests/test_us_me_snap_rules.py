import json
import zipfile
from collections import Counter
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-me-snap-rules.yaml"
VERSION = "2026-07-17-me-snap-rules"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-me" / "regulation" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-me" / "regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-me" / "regulation" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-me" / "regulation" / f"{VERSION}.json"

EXPECTED_SOURCES = {
    "me-ofi-snap-rules-chapter-301": {
        "citation_path": "us-me/regulation/dhhs/ofi/chapter-301",
        "expression_date": "2026-06-28",
        "filing": "2026-133",
        "row_count": 219,
        "sha256": "45ee047d0e2a888dc78ba28dfe64db152db76ffc3682e4b1a6f15ddd6cdb7bb0",
        "url": "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c301-2026-133-NSC.docx",
    },
    "me-ofi-snap-et-rules-chapter-609": {
        "citation_path": "us-me/regulation/dhhs/ofi/chapter-609",
        "expression_date": "2025-07-08",
        "filing": "2025-138",
        "row_count": 4,
        "sha256": "9e68369bf2462f3fd4ee0fad07361f7eba38af01424294094bfd566164cec9d1",
        "url": "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c609_0.docx",
    },
}


def test_maine_snap_manifest_pins_every_current_official_snap_rulebook() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]

    assert {document["source_id"] for document in documents} == set(EXPECTED_SOURCES)
    for document in documents:
        expected = EXPECTED_SOURCES[document["source_id"]]
        assert document["citation_path"] == expected["citation_path"]
        assert document["source_url"] == expected["url"]
        assert document["source_as_of"] == "2026-07-17"
        assert document["expression_date"] == expected["expression_date"]
        assert document["metadata"]["rule_filing"] == expected["filing"]
        assert document["metadata"]["primary_source"] is True
        assert document["metadata"]["program"] == "SNAP"
        assert document["metadata"]["federal_program"] == "SNAP"
        assert (
            document["metadata"]["discovered_via"]
            == "official-agency-rules-index:maine-dhhs"
        )


def test_maine_snap_scope_retains_official_docx_files_and_complete_rows() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    provisions = [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(SOURCE_ROOT.glob("official-documents/*.docx"))

    assert len(retained_files) == len(EXPECTED_SOURCES) == 2
    assert len(inventory) == len(provisions) == 223
    assert Counter(record["source_id"] for record in provisions) == Counter(
        {
            source_id: expected["row_count"]
            for source_id, expected in EXPECTED_SOURCES.items()
        }
    )
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 223
    assert coverage["provision_count"] == 223

    documents = {
        document["source_id"]: document
        for document in yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    }
    for source_id, expected in EXPECTED_SOURCES.items():
        source_file = SOURCE_ROOT / "official-documents" / f"{source_id}.docx"
        relative_source_path = source_file.relative_to(CORPUS_ROOT).as_posix()
        source_items = [item for item in inventory if item["source_path"] == relative_source_path]
        source_rows = [row for row in provisions if row["source_id"] == source_id]

        assert source_file.read_bytes().startswith(b"PK")
        assert zipfile.is_zipfile(source_file)
        assert sha256_file(source_file) == expected["sha256"]
        assert len(source_items) == len(source_rows) == expected["row_count"]
        assert all(item["sha256"] == expected["sha256"] for item in source_items)
        assert all(row["source_path"] == relative_source_path for row in source_rows)
        assert all(row["source_url"] == expected["url"] for row in source_rows)
        assert all(row["source_as_of"] == "2026-07-17" for row in source_rows)
        assert all(row["expression_date"] == expected["expression_date"] for row in source_rows)
        assert all(row["metadata"]["program"] == "SNAP" for row in source_rows)
        assert all(
            row["metadata"]["rule_filing"] == documents[source_id]["metadata"]["rule_filing"]
            for row in source_rows
        )
        assert all(row["body"] for row in source_rows if row["kind"] == "block")
