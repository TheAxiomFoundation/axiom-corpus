import json
from pathlib import Path
from urllib.parse import urljoin

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ct-snap-manual.yaml"
VERSION = "2026-07-17-ct-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ct" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ct" / "manual" / f"{VERSION}.json"


def test_connecticut_snap_manifest_matches_retained_official_toc() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    policy_documents = [
        document
        for document in documents
        if document["metadata"]["document_subtype"] == "policy_manual_topic"
    ]
    toc_document = next(
        document
        for document in documents
        if document["metadata"]["document_subtype"] == "manual_toc_snapshot"
    )
    landing_document = next(
        document
        for document in documents
        if document["metadata"]["document_subtype"] == "manual_landing_page_snapshot"
    )
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    document_items = [item for item in inventory if item["metadata"]["kind"] == "document"]
    source_path_by_url = {
        item["source_url"]: CORPUS_ROOT / item["source_path"] for item in document_items
    }

    assert len(documents) == 279
    assert len(policy_documents) == 277
    assert len(document_items) == len(documents)
    assert set(source_path_by_url) == {document["source_url"] for document in documents}

    retained_toc = source_path_by_url[toc_document["source_url"]]
    toc_rows = json.loads(retained_toc.read_text())
    assert len(toc_rows) == len(policy_documents)
    assert [row["id"] for row in toc_rows] == [
        document["metadata"]["toc_id"] for document in policy_documents
    ]
    assert [row["parent"] for row in toc_rows] == [
        document["metadata"]["toc_parent"] for document in policy_documents
    ]
    assert [row["text"].strip() for row in toc_rows] == [
        document["title"].removeprefix("Connecticut SNAP Policy Manual: ")
        for document in policy_documents
    ]
    assert [
        urljoin(toc_document["metadata"]["manual_base_url"], row["a_attr"]["href"])
        for row in toc_rows
    ] == [document["source_url"] for document in policy_documents]

    retained_landing = source_path_by_url[landing_document["source_url"]]
    assert "https://portaldir.ct.gov/dss/SNAP/index.htm" in retained_landing.read_text()


def test_connecticut_snap_scope_retains_exact_official_sources() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    document_items = [item for item in inventory if item["metadata"]["kind"] == "document"]
    retained_files = sorted(path for path in SOURCE_ROOT.rglob("*") if path.is_file())

    assert len(retained_files) == 279
    assert len(document_items) == 279
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(document["expression_date"] == "2026-01-28" for document in documents)
    landing_document = next(
        document
        for document in documents
        if document["metadata"]["document_subtype"] == "manual_landing_page_snapshot"
    )
    assert "source_last_modified" not in landing_document["metadata"]
    assert all(
        document["metadata"]["source_last_modified"] == "2026-01-28"
        for document in documents
        if document is not landing_document
    )
    assert all(
        document["metadata"]["discovered_via"]
        == "official-toc:connecticut-dss-snap-policy-manual"
        for document in documents
    )
    for item in document_items:
        source_path = CORPUS_ROOT / item["source_path"]
        assert source_path.is_relative_to(SOURCE_ROOT)
        assert source_path.is_file()
        assert item["sha256"] == sha256_file(source_path)

    toc_items = [
        item
        for item in inventory
        if item["source_url"] == "https://portaldir.ct.gov/dss/SNAP/_toc.json"
    ]
    assert len(toc_items) == 1
    assert toc_items[0]["metadata"]["block_count"] == 0
