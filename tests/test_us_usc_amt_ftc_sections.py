from __future__ import annotations

import json
import zipfile
from collections import Counter
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-07-27-usc-amt-ftc-sections-title-26"
SOURCE_ROOT = (
    REPO_ROOT / "data/corpus/sources/us/statute" / VERSION
)
INVENTORY_PATH = (
    REPO_ROOT / "data/corpus/inventory/us/statute" / f"{VERSION}.json"
)
PROVISIONS_PATH = (
    REPO_ROOT / "data/corpus/provisions/us/statute" / f"{VERSION}.jsonl"
)
COVERAGE_PATH = (
    REPO_ROOT / "data/corpus/coverage/us/statute" / f"{VERSION}.json"
)
EXPECTED_SECTION_COUNTS = {
    "27": 1,
    "57": 43,
    "58": 17,
    "59": 98,
    "901": 131,
    "902": 1,
    "903": 1,
    "904": 259,
}


def test_retained_title_26_source_is_exact_olrc_zip_member() -> None:
    zip_path = SOURCE_ROOT / "olrc/xml_usc26@119-102not101.zip"
    xml_path = SOURCE_ROOT / "uslm/usc26.xml"
    zip_bytes = zip_path.read_bytes()
    xml_bytes = xml_path.read_bytes()

    assert sha256(zip_bytes).hexdigest() == (
        "d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0"
    )
    assert sha256(xml_bytes).hexdigest() == (
        "d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621"
    )
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == ["usc26.xml"]
        assert archive.read("usc26.xml") == xml_bytes


def test_amt_ftc_scope_is_complete_and_section_specific() -> None:
    rows = [
        json.loads(line)
        for line in PROVISIONS_PATH.read_text(encoding="utf-8").splitlines()
    ]
    rows_by_path = {row["citation_path"]: row for row in rows}
    section_counts = Counter(
        parts[3]
        for row in rows
        if len(parts := row["citation_path"].split("/")) >= 4
    )

    assert len(rows) == 552
    assert section_counts == EXPECTED_SECTION_COUNTS
    assert len(json.loads(INVENTORY_PATH.read_text())["items"]) == 552
    coverage = json.loads(COVERAGE_PATH.read_text())
    assert coverage["complete"] is True
    assert coverage["document_class"] == "statute"
    assert coverage["jurisdiction"] == "us"
    assert coverage["version"] == VERSION
    assert coverage["source_count"] == 552
    assert coverage["provision_count"] == 552
    assert coverage["matched_count"] == 552
    assert coverage["missing_from_provisions"] == []
    assert coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []

    for section in EXPECTED_SECTION_COUNTS:
        root = rows_by_path[f"us/statute/26/{section}"]
        assert root["source_url"] == (
            "https://uscode.house.gov/view.xhtml?"
            f"req=granuleid:USC-prelim-title26-section{section}"
            "&num=0&edition=prelim"
        )

    repeal = rows_by_path["us/statute/26/902"]
    assert repeal["body"] == ""
    assert repeal["metadata"]["status"] == "repealed"
    assert repeal["heading"].startswith("Repealed.")
    assert not any(
        path.startswith("us/statute/26/902/")
        for path in rows_by_path
    )
