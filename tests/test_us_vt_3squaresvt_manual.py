import hashlib
import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-vt-3squaresvt-manual.yaml"
VERSION = "2026-07-21-vt-3squaresvt-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources/us-vt/manual" / VERSION / "official-documents"
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-vt/manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-vt/manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-vt/manual" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 32
EXPECTED_BLOCK_COUNT = 879
EXPECTED_ROW_COUNT = EXPECTED_DOCUMENT_COUNT + EXPECTED_BLOCK_COUNT
EXPECTED_SOURCE_SET_SHA256 = "533717e5d50630aa74ed5cab76b1976f9a469512dc7f2f1a22faed256d13605c"


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_vermont_manifest_matches_current_official_chapter_numbering() -> None:
    documents = _documents()

    assert len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len({document["source_url"] for document in documents}) == len(documents)
    assert {document["source_as_of"] for document in documents} == {"2026-07-21"}
    assert {document["expression_date"] for document in documents} == {"2026-07-01"}
    assert all(document["metadata"]["primary_source"] is True for document in documents)

    expected_chapters = [str(chapter) for chapter in range(100, 3200, 100)]
    for index, (document, expected_chapter) in enumerate(
        zip(documents[1:], expected_chapters, strict=True), start=2
    ):
        chapter = re.match(r"(\d+)", document["title"].split(": ", 1)[1])
        assert chapter is not None
        assert chapter.group(1) == expected_chapter
        source_prefix = f"vt-dcf-3squaresvt-{index:03d}-"
        assert document["source_id"].startswith(source_prefix)
        assert document["citation_path"].rsplit("/", 1)[1] == document[
            "source_id"
        ].removeprefix(source_prefix)


def test_vermont_source_set_and_generated_scope_are_complete() -> None:
    source_files = sorted(SOURCE_ROOT.glob("*.html"))
    digest_lines = [
        f"{path.name}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in source_files
    ]
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())

    assert len(source_files) == EXPECTED_DOCUMENT_COUNT
    assert hashlib.sha256("\n".join(digest_lines).encode()).hexdigest() == (
        EXPECTED_SOURCE_SET_SHA256
    )
    assert "07/01/2026" in next(SOURCE_ROOT.glob("*manual-updates*.html")).read_text()
    assert "07/01/2026" in next(SOURCE_ROOT.glob("*1500-resources*.html")).read_text()
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert sum(row["kind"] == "document" for row in rows) == EXPECTED_DOCUMENT_COUNT
    assert sum(row["kind"] == "block" for row in rows) == EXPECTED_BLOCK_COUNT
    assert all(row["body"] for row in rows if row["kind"] == "block")
    assert {row["citation_path"] for row in rows if row["kind"] == "document"} == {
        document["citation_path"] for document in _documents()
    }
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT
