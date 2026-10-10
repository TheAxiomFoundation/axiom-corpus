import json
import re
from collections import defaultdict
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-nm-snap-regulations.yaml"
VERSION = "2026-07-17-nm-snap-regulations"
SOURCE_DIR = (
    CORPUS_ROOT
    / "sources/us-nm/regulation"
    / VERSION
    / "official-documents"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-nm/regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-nm/regulation" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-nm/regulation" / f"{VERSION}.json"

EXPECTED_DOCUMENT_COUNT = 28
EXPECTED_SECTION_COUNT = 360
EXPECTED_ROW_COUNT = 388
EXPECTED_NMAC_CITATIONS = {
    "8.100.100",
    "8.100.110",
    "8.100.120",
    "8.100.130",
    "8.100.140",
    "8.100.150",
    "8.100.180",
    "8.100.390",
    "8.100.640",
    "8.100.970",
    "8.139.100",
    "8.139.110",
    "8.139.120",
    "8.139.400",
    "8.139.410",
    "8.139.420",
    "8.139.500",
    "8.139.501",
    "8.139.502",
    "8.139.503",
    "8.139.504",
    "8.139.510",
    "8.139.520",
    "8.139.527",
    "8.139.610",
    "8.139.640",
    "8.139.647",
    "8.139.650",
}


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def _source_labels(document: dict) -> list[str]:
    source_path = SOURCE_DIR / f"{document['source_id']}.html"
    soup = BeautifulSoup(source_path.read_bytes(), "html.parser")
    citation = document["metadata"]["nmac_citation"]
    heading_pattern = re.compile(
        rf"^({re.escape(citation)}\.\d+(?:\s*-\s*\d+)?)\s+"
        r"(?:[A-Z]|\[RESERVED\])"
    )
    labels = []
    for paragraph in soup.select(".WordSection1 p, .Section1 p"):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        text = re.sub(r"(?<=\.)\s+(?=\d)", "", text)
        text = re.sub(r"(?<=\d)\s*-\s*(?=\d)", "-", text)
        if match := heading_pattern.match(text):
            labels.append(match.group(1))
    return labels


def test_new_mexico_manifest_pins_complete_current_source_boundary() -> None:
    documents = _documents()

    assert len(documents) == EXPECTED_DOCUMENT_COUNT
    assert len({document["source_id"] for document in documents}) == len(documents)
    assert {
        document["metadata"]["nmac_citation"] for document in documents
    } == EXPECTED_NMAC_CITATIONS
    assert {document["metadata"]["nmac_chapter"] for document in documents} == {
        "100",
        "139",
    }
    assert sum(
        document["metadata"]["provision_count"] for document in documents
    ) == EXPECTED_SECTION_COUNT
    assert all(document["source_as_of"] == "2026-07-17" for document in documents)
    assert all(document["expression_date"] == "2026-07-01" for document in documents)
    assert all(
        document["metadata"]["nmac_current_through"] == "2026-07-01"
        for document in documents
    )
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(
        document["extraction"]["normalize_label_internal_whitespace"] is True
        for document in documents
    )
    assert {
        document["metadata"]["nmac_citation"]
        for document in documents
        if document["metadata"].get("repealed")
    } == {"8.139.640", "8.139.650"}
    part_640 = next(
        document
        for document in documents
        if document["metadata"]["nmac_citation"] == "8.139.640"
    )
    assert part_640["metadata"]["discovered_via"] == (
        "official-hca-income-support-index"
    )


def test_new_mexico_scope_matches_every_retained_nmac_heading() -> None:
    documents = _documents()
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    generated_by_source: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        if row["kind"] == "section":
            generated_by_source[row["source_id"]].add(
                row["metadata"]["section_label"]
            )

    for document in documents:
        source_path = SOURCE_DIR / f"{document['source_id']}.html"
        source_labels = _source_labels(document)
        expected_count = document["metadata"]["provision_count"]

        assert source_path.stat().st_size == document["metadata"]["source_byte_count"]
        assert sha256_file(source_path) == document["metadata"]["source_sha256"]
        assert len(source_labels) == len(set(source_labels)) == expected_count
        assert set(source_labels) == generated_by_source[document["source_id"]]

    assert len(list(SOURCE_DIR.glob("*.html"))) == EXPECTED_DOCUMENT_COUNT
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert sum(row["kind"] == "document" for row in rows) == EXPECTED_DOCUMENT_COUNT
    assert sum(row["kind"] == "section" for row in rows) == EXPECTED_SECTION_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT


def test_new_mexico_sections_restore_split_labels_ranges_and_policy_text() -> None:
    sections = {
        row["metadata"]["section_label"]: row
        for row in _provisions()
        if row["kind"] == "section"
    }

    assert sections["8.139.120.10"]["heading"] == "[RESERVED]"
    assert sections["8.139.610.8-9"]["heading"] == "[RESERVED]"
    assert sections["8.139.502.8"]["heading"] == "STATE SNAP SUPPLEMENT BENEFITS:"
    assert "Maximum benefit amount" in sections["8.139.502.8"]["body"]
    assert "supplement benefits" not in sections["8.139.502.7"]["body"].lower()
    assert "Earned income includes" in sections["8.139.520.9"]["body"]
    assert "secure electronic data management system" in sections["8.100.140.8"]["body"]
    assert not any(
        "\ufffd" in (row.get("heading") or "") + (row.get("body") or "")
        for row in sections.values()
    )


def test_new_mexico_repealed_parts_are_retained_as_source_roots() -> None:
    rows = _provisions()
    repealed_source_ids = {
        "nm-srca-nmac-8-139-640",
        "nm-srca-nmac-8-139-650",
    }

    for source_id in repealed_source_ids:
        source_rows = [row for row in rows if row["source_id"] == source_id]
        assert len(source_rows) == 1
        assert source_rows[0]["kind"] == "document"
        assert source_rows[0]["metadata"]["repealed"] is True
