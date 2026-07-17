import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ky-snap-manual.yaml"
VERSION = "2026-07-17-ky-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ky" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ky" / "manual" / f"{VERSION}.json"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-ky" / "manual" / f"{VERSION}.json"

EXPECTED_SOURCES = {
    "ky-dcbs-dfs-om-vol-ii": (
        346,
        "7ef887dacc2332da4b2e49312b8d9d66c8ab5aa47258c51d666d5db0c84996c0",
        "OMTL – 701",
    ),
    "ky-dcbs-dfs-om-vol-iia": (
        52,
        "a1a7f8d111f38003d14ad5bb18fe9c4761a8ce3d688be5ace7d682e652c6279a",
        "OMTL-683",
    ),
}


def test_kentucky_snap_manifest_pins_both_current_official_manuals() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]

    assert {document["source_id"] for document in documents} == set(EXPECTED_SOURCES)
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(document["request"]["browser_user_agent"] is True for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(
        document["metadata"]["discovered_via"]
        == "official-agency-page:kentucky-dfs-family-support-manuals"
        for document in documents
    )
    assert {document["source_id"]: document["expression_date"] for document in documents} == {
        "ky-dcbs-dfs-om-vol-ii": "2026-07-01",
        "ky-dcbs-dfs-om-vol-iia": "2025-10-25",
    }


def test_kentucky_snap_scope_retains_every_official_pdf_page() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(path for path in SOURCE_ROOT.rglob("*.pdf") if path.is_file())

    assert len(retained_files) == len(EXPECTED_SOURCES) == 2
    assert len(inventory) == sum(page_count + 1 for page_count, _, _ in EXPECTED_SOURCES.values())
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 400
    assert coverage["provision_count"] == 400

    for source_id, (expected_pages, expected_hash, latest_omtl) in EXPECTED_SOURCES.items():
        source_file = SOURCE_ROOT / "official-documents" / f"{source_id}.pdf"
        relative_source_path = source_file.relative_to(CORPUS_ROOT).as_posix()
        source_items = [
            item for item in inventory if item["source_path"] == relative_source_path
        ]

        assert source_file.read_bytes().startswith(b"%PDF-")
        assert sha256_file(source_file) == expected_hash
        assert len(source_items) == expected_pages + 1
        assert all(item["sha256"] == expected_hash for item in source_items)
        with fitz.open(source_file) as pdf:
            assert pdf.page_count == expected_pages
            text = "\n".join(page.get_text() for page in pdf)
        assert "The request is blocked." not in text
        assert latest_omtl in text

        document_item = next(item for item in source_items if item["metadata"]["kind"] == "document")
        page_items = [item for item in source_items if item["metadata"]["kind"] == "page"]
        assert {item["citation_path"] for item in page_items} == {
            f"{document_item['citation_path']}/page-{page}" for page in range(1, expected_pages + 1)
        }
