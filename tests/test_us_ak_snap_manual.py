import json
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ak-snap-manual.yaml"
VERSION = "2026-07-16-ak-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ak" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ak" / "manual" / f"{VERSION}.json"
TOC_ARRAY_PATTERN = re.compile(r"var toc\s*=\s*(\[.*?\]);\s*window")


def test_alaska_snap_manifest_matches_retained_robohelp_toc() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    policy_documents = [
        document
        for document in documents
        if document["metadata"]["document_subtype"] == "policy_manual_topic"
    ]
    toc_documents = {
        document["metadata"]["toc_snapshot_key"]: document
        for document in documents
        if document["metadata"]["document_subtype"] == "manual_toc_snapshot"
    }
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    source_path_by_url = {
        item["source_url"]: CORPUS_ROOT / item["source_path"] for item in inventory
    }

    assert len(policy_documents) == 194
    assert len(toc_documents) == 45
    assert set(toc_documents) == {"root", *(f"toc{index}" for index in range(1, 45))}

    manual_base_url = policy_documents[0]["metadata"]["manual_base_url"]
    ordered_urls: list[str] = []
    seen_urls: set[str] = set()
    visited_toc_keys: set[str] = set()

    def visit(toc_key: str) -> None:
        assert toc_key not in visited_toc_keys
        visited_toc_keys.add(toc_key)
        toc_document = toc_documents[toc_key]
        retained_source = source_path_by_url[toc_document["source_url"]]
        assert retained_source.is_relative_to(SOURCE_ROOT)
        match = TOC_ARRAY_PATTERN.search(retained_source.read_text())
        assert match, toc_document["source_url"]
        for node in json.loads(match.group(1)):
            if source_url := node.get("url"):
                canonical_url = urldefrag(urljoin(manual_base_url, source_url)).url
                if canonical_url not in seen_urls:
                    seen_urls.add(canonical_url)
                    ordered_urls.append(canonical_url)
            if child_key := node.get("key"):
                visit(str(child_key))

    visit("root")

    expected_urls = [document["source_url"] for document in policy_documents[1:]]
    assert visited_toc_keys == set(toc_documents)
    assert ordered_urls == expected_urls
