import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ia-snap-manual.yaml"
VERSION = "2026-07-17-ia-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ia" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ia" / "manual" / f"{VERSION}.json"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-ia" / "manual" / f"{VERSION}.json"

EXPECTED_SOURCES = {
    "ia-hhs-em-toc": (7, "e42856e0ac3710b5010e6f8de88645e4bfc27cd9d014692f9ba6ba8eb82219e7"),
    "ia-hhs-em-7-a": (49, "97317cdd8e56e02cc5a6491f392fd59843c20ba5a147af662fbc696e588354a0"),
    "ia-hhs-em-7-b": (37, "ab40ec05ff61a5955a89e1dc98042974719a3bcd81f0b3ad96342456c2ea8394"),
    "ia-hhs-em-7-c": (40, "8890678e124f9034dfc44c72877fa0257dce985467759a2b3138c4a91def5a26"),
    "ia-hhs-em-7-d": (27, "f250fc6293e82b44f488a766e96d70bd9b944086940aa113c057dbef20e977b0"),
    "ia-hhs-em-7-e": (62, "cabb5f53ffc17a342428480475b3dd1acc69d0108557d6cb0f5f885fce479f6f"),
    "ia-hhs-em-7-f": (20, "8363be34c1e7d586350c9ea675c451fbae31beb8ddfd8b84bde1a2296d5ed8a7"),
    "ia-hhs-em-7-g": (52, "f642b534f967aca54ea54d84ae1344a91ecec95240356d5f6a06d78c1631befd"),
    "ia-hhs-em-7-h": (27, "daddcc87f10b9c082cc6574c4bf0d1000a2395f4e2778776835996cb22f85266"),
    "ia-hhs-em-7-i": (81, "e1c6bbc079e97527b67a7d10a5f73b33249a155b47f2446e355f69d8aea83727"),
    "ia-hhs-em-7-j": (17, "166b63b1fd121dfc8b02e2db6d9b9addb7ebf297c75f97a909559f5a65232062"),
    "ia-hhs-em-7-m": (12, "3b82e99987d57839c461734f81606244891583b2a976692a6ca70db504386043"),
}


def test_iowa_snap_manifest_pins_complete_official_title_7_manual() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]

    assert {document["source_id"] for document in documents} == set(EXPECTED_SOURCES)
    assert all(document["source_url"].startswith("https://hhs.iowa.gov/media/") for document in documents)
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(
        document["metadata"]["discovered_via"]
        == "official-toc:iowa-hhs-employees-manual"
        for document in documents
    )
    assert all(document["metadata"]["manual_revision_date"] for document in documents)
    assert all(document["metadata"]["source_last_modified"] for document in documents)


def test_iowa_snap_scope_retains_every_official_pdf_page() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(path for path in SOURCE_ROOT.rglob("*.pdf") if path.is_file())

    assert len(retained_files) == len(EXPECTED_SOURCES) == 12
    assert len(inventory) == sum(page_count + 1 for page_count, _ in EXPECTED_SOURCES.values())
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 443
    assert coverage["provision_count"] == 443

    for source_id, (expected_pages, expected_hash) in EXPECTED_SOURCES.items():
        source_file = SOURCE_ROOT / "official-documents" / f"{source_id}.pdf"
        relative_source_path = source_file.relative_to(CORPUS_ROOT).as_posix()
        source_items = [
            item for item in inventory if item["source_path"] == relative_source_path
        ]

        assert source_file.read_bytes().startswith(b"%PDF-")
        assert sha256_file(source_file) == expected_hash
        assert len(source_items) == expected_pages + 1
        assert all(CORPUS_ROOT / item["source_path"] == source_file for item in source_items)
        assert all(item["sha256"] == expected_hash for item in source_items)
        with fitz.open(source_file) as pdf:
            assert pdf.page_count == expected_pages

        document_item = next(item for item in source_items if item["metadata"]["kind"] == "document")
        page_items = [item for item in source_items if item["metadata"]["kind"] == "page"]
        assert {item["citation_path"] for item in page_items} == {
            f"{document_item['citation_path']}/page-{page}" for page in range(1, expected_pages + 1)
        }
