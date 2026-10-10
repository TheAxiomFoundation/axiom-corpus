from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_BASE = REPO_ROOT / "data/corpus"
VERSION = "2026-07-27-usc-63-repair-165-title-26"
SOURCE_BASE = CORPUS_BASE / "sources/us/statute" / VERSION
SOURCE_ZIP = SOURCE_BASE / "olrc/xml_usc26@119-102not101.zip"
SOURCE_XML = SOURCE_BASE / "uslm/usc26.xml"
INVENTORY = CORPUS_BASE / "inventory/us/statute" / f"{VERSION}.json"
PROVISIONS = CORPUS_BASE / "provisions/us/statute" / f"{VERSION}.jsonl"
COVERAGE = CORPUS_BASE / "coverage/us/statute" / f"{VERSION}.json"
LEGACY_PROVISIONS = (
    CORPUS_BASE
    / "provisions/us/statute/"
    "2026-05-10-tax-sections-r2026-07-15-self-contained-"
    "r2026-07-15-self-contained.jsonl"
)

ZIP_SHA256 = "d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0"
XML_SHA256 = "d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621"
SOURCE_PATH = f"sources/us/statute/{VERSION}/uslm/usc26.xml"
SECTION_URLS = {
    "63": (
        "https://uscode.house.gov/view.xhtml?"
        "req=granuleid:USC-prelim-title26-section63&num=0&edition=prelim"
    ),
    "165": (
        "https://uscode.house.gov/view.xhtml?"
        "req=granuleid:USC-prelim-title26-section165&num=0&edition=prelim"
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def test_us_63_repair_165_retains_exact_olrc_bytes():
    zip_bytes = SOURCE_ZIP.read_bytes()
    xml_bytes = SOURCE_XML.read_bytes()

    assert _sha256(zip_bytes) == ZIP_SHA256
    assert _sha256(xml_bytes) == XML_SHA256
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        assert archive.namelist() == ["usc26.xml"]
        assert archive.read("usc26.xml") == xml_bytes


def test_us_63_repair_165_scope_is_complete_and_exactly_sourced():
    records = _jsonl(PROVISIONS)
    records_by_path = {record["citation_path"]: record for record in records}
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))

    assert len(records) == len(records_by_path) == 163
    assert len(inventory["items"]) == 163
    assert coverage == {
        "complete": True,
        "document_class": "statute",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us",
        "matched_count": 163,
        "missing_from_provisions": [],
        "provision_count": 163,
        "source_count": 163,
        "version": VERSION,
    }
    assert Counter(record["kind"] for record in records) == {
        "title": 1,
        "section": 2,
        "subsection": 20,
        "paragraph": 58,
        "subparagraph": 62,
        "clause": 18,
        "subclause": 2,
    }

    for section, expected_count in {"63": 62, "165": 100}.items():
        root = f"us/statute/26/{section}"
        section_records = tuple(
            record
            for record in records
            if record["citation_path"] == root
            or str(record["citation_path"]).startswith(f"{root}/")
        )
        assert len(section_records) == expected_count
        assert {record["source_url"] for record in section_records} == {
            SECTION_URLS[section]
        }
        assert {record["source_path"] for record in section_records} == {
            SOURCE_PATH
        }
        assert all(
            str(record["source_id"]).startswith(f"/us/usc/t26/s{section}")
            for record in section_records
        )

    inventory_items = inventory["items"]
    assert {item["sha256"] for item in inventory_items} == {XML_SHA256}
    assert {item["source_path"] for item in inventory_items} == {SOURCE_PATH}
    assert {item["source_format"] for item in inventory_items} == {"uslm-xml"}

    assert {
        "us/statute/26/63/c/5",
        "us/statute/26/63/f",
        "us/statute/26/165/d/1/A",
        "us/statute/26/165/d/1/B",
        "us/statute/26/165/h/5/C/ii",
    } <= records_by_path.keys()

    legacy_63 = next(
        record
        for record in _jsonl(LEGACY_PROVISIONS)
        if record["citation_path"] == "us/statute/26/63"
    )
    repaired_63 = records_by_path["us/statute/26/63"]
    assert repaired_63["body"] == legacy_63["body"]
    assert "section 225 and 1 1 So in original." in str(repaired_63["body"])
