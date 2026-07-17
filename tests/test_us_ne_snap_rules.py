import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ne-snap-rules.yaml"
VERSION = "2026-07-17-ne-snap-rules"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ne" / "regulation" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ne" / "regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-ne" / "regulation" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-ne" / "regulation" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 5
EXPECTED_SECTION_COUNT = 737
EXPECTED_ROW_COUNT = EXPECTED_DOCUMENT_COUNT + EXPECTED_SECTION_COUNT
EXPECTED_SECTIONS_BY_CHAPTER = {"1": 181, "2": 133, "3": 284, "4": 119, "5": 20}
EXPECTED_SOURCE_SET_SHA256 = "25143e250e2c33e00d7b4c8888737356c5c90f04e94950c994930d2be58bbae1"
SECTION_START_RE = re.compile(
    r"^(?P<label>0\d{2}(?:\.\d{1,2})?(?:\([A-Za-z0-9]+\))*)\.?\s+"
)


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_nebraska_manifest_pins_current_title_475_chapters() -> None:
    documents = _documents()
    source_set = "".join(
        "\t".join(
            (
                document["source_id"],
                document["source_url"],
                document["expression_date"],
                document["metadata"]["source_sha256"],
                str(document["metadata"]["provision_count"]),
            )
        )
        + "\n"
        for document in documents
    ).encode()

    assert len(documents) == EXPECTED_DOCUMENT_COUNT
    assert [document["metadata"]["chapter_number"] for document in documents] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert hashlib.sha256(source_set).hexdigest() == EXPECTED_SOURCE_SET_SHA256
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(document["source_format"] == "pdf" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(document["metadata"]["program"] == "SNAP" for document in documents)
    assert all(
        document["source_url"].startswith(
            "https://rules.nebraska.gov/api/fileStorage/GetAsByteArray/chapter-pdfs/"
        )
        for document in documents
    )
    assert documents[0]["metadata"]["official_pdf_blob_name"].endswith("_Official.pdf")
    assert all(
        document["request"]
        == {
            "verify_tls": False,
            "range_fetch": True,
            "range_backend": "curl",
            "browser_user_agent": True,
        }
        for document in documents
    )


def test_nebraska_scope_retains_every_labeled_pdf_provision() -> None:
    documents = {document["source_id"]: document for document in _documents()}
    rows = _provisions()
    sections = [row for row in rows if row["kind"] == "section"]
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted((SOURCE_ROOT / "official-documents").glob("*.pdf"))
    sections_by_source = Counter(row["source_id"] for row in sections)

    assert len(retained_files) == len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len(sections) == EXPECTED_SECTION_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT

    for source_file in retained_files:
        source_id = source_file.stem
        document = documents[source_id]
        chapter = document["metadata"]["chapter_number"]
        generated_labels = {
            row["metadata"]["section_label"]
            for row in sections
            if row["source_id"] == source_id
        }
        with fitz.open(source_file) as pdf:
            source_labels = [
                match.group("label")
                for page in pdf
                for line in page.get_text().splitlines()
                if (match := SECTION_START_RE.match(line.strip())) is not None
            ]
            assert pdf.page_count == document["metadata"]["page_count"]

        assert sha256_file(source_file) == document["metadata"]["source_sha256"]
        assert len(source_labels) == len(set(source_labels))
        assert set(source_labels) == generated_labels
        assert len(generated_labels) == EXPECTED_SECTIONS_BY_CHAPTER[chapter]
        assert sections_by_source[source_id] == EXPECTED_SECTIONS_BY_CHAPTER[chapter]


def test_nebraska_sections_preserve_inline_text_and_policy_boundaries() -> None:
    sections = {
        row["citation_path"]: row for row in _provisions() if row["kind"] == "section"
    }

    expanded_resources = sections[
        "us-ne/regulation/title-475/chapter-1/002.24"
    ]["body"]
    self_employment = sections[
        "us-ne/regulation/title-475/chapter-3/002.04(B)"
    ]["body"]
    replacements = sections["us-ne/regulation/title-475/chapter-5/002.03"]["body"]

    assert expanded_resources.startswith("The Expanded Resource Program provides")
    assert self_employment.startswith(
        "The following regulations apply to determining self-employment income."
    )
    assert "reported within ten days" in replacements
    assert "us-ne/regulation/title-475/chapter-3/273.11" not in sections
    assert not any(
        marker in (row.get("body") or "")
        for row in sections.values()
        for marker in ("APPROVED", "ATTORNEY GENERAL", "RULES SPECIALIST")
    )
