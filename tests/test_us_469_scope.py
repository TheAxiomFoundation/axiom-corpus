from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

from scripts.repro.us_usc_469 import (
    EXPECTED_KIND_COUNTS,
    EXPECTED_PROVISION_COUNT,
    EXPECTED_XML_SHA256,
    EXPECTED_ZIP_SHA256,
    OLRC_URL,
    SECTION_URL,
    SOURCE_AS_OF,
    STATUTE_VERSION,
    TITLE_URL,
    reproduce,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/corpus"
SOURCE_BASE = BASE / "sources/us/statute" / STATUTE_VERSION
SOURCE_ZIP = SOURCE_BASE / "olrc/xml_usc26@119-102.zip"
SOURCE_XML = SOURCE_BASE / "uslm/usc26.xml"
INVENTORY = BASE / "inventory/us/statute" / f"{STATUTE_VERSION}.json"
PROVISIONS = BASE / "provisions/us/statute" / f"{STATUTE_VERSION}.jsonl"
COVERAGE = BASE / "coverage/us/statute" / f"{STATUTE_VERSION}.json"
SOURCE_PATH = f"sources/us/statute/{STATUTE_VERSION}/uslm/usc26.xml"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def test_us_469_scope_retains_exact_official_olrc_bytes() -> None:
    zip_bytes = SOURCE_ZIP.read_bytes()
    xml_bytes = SOURCE_XML.read_bytes()

    assert _sha256(zip_bytes) == EXPECTED_ZIP_SHA256
    assert _sha256(xml_bytes) == EXPECTED_XML_SHA256
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        assert archive.namelist() == ["usc26.xml"]
        assert archive.read("usc26.xml") == xml_bytes


def test_us_469_reproducer_matches_committed_scope(tmp_path: Path) -> None:
    reproduce(tmp_path)
    for committed in (INVENTORY, PROVISIONS, COVERAGE):
        assert (tmp_path / committed.relative_to(BASE)).read_bytes() == (
            committed.read_bytes()
        )


def test_us_469_scope_is_complete_and_exactly_sourced() -> None:
    records = _jsonl(PROVISIONS)
    records_by_path = {
        str(record["citation_path"]): record for record in records
    }
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))

    assert len(records) == len(records_by_path) == EXPECTED_PROVISION_COUNT
    assert len(inventory["items"]) == EXPECTED_PROVISION_COUNT
    assert Counter(str(record["kind"]) for record in records) == Counter(
        EXPECTED_KIND_COUNTS
    )
    assert coverage == {
        "complete": True,
        "document_class": "statute",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us",
        "matched_count": EXPECTED_PROVISION_COUNT,
        "missing_from_provisions": [],
        "provision_count": EXPECTED_PROVISION_COUNT,
        "source_count": EXPECTED_PROVISION_COUNT,
        "version": STATUTE_VERSION,
    }

    assert {
        "us/statute/26",
        "us/statute/26/469",
        "us/statute/26/469/c",
        "us/statute/26/469/c/1",
        "us/statute/26/469/c/1/A",
        "us/statute/26/469/c/1/B",
        "us/statute/26/469/h",
        "us/statute/26/469/h/1",
        "us/statute/26/469/h/2",
        "us/statute/26/469/h/5",
    } <= records_by_path.keys()

    assert records_by_path["us/statute/26"]["source_url"] == TITLE_URL
    assert {
        str(record["source_url"])
        for path, record in records_by_path.items()
        if path != "us/statute/26"
    } == {SECTION_URL}
    assert {
        str(record["source_path"]) for record in records
    } == {SOURCE_PATH}
    assert {
        str(record["source_as_of"]) for record in records
    } == {SOURCE_AS_OF}
    assert {
        str(record["expression_date"]) for record in records
    } == {SOURCE_AS_OF}
    assert {
        str(item["sha256"]) for item in inventory["items"]
    } == {EXPECTED_XML_SHA256}
    assert {
        str(item["metadata"]["source_download_url"])
        for item in inventory["items"]
    } == {OLRC_URL}

    assert records_by_path["us/statute/26/469/c/1"]["body"] == (
        "The term “passive activity” means any activity—\n\n"
        "(A) which involves the conduct of any trade or business, and\n\n"
        "(B) in which the taxpayer does not materially participate."
    )
    assert records_by_path["us/statute/26/469/h/1"]["body"] == (
        "A taxpayer shall be treated as materially participating in an activity "
        "only if the taxpayer is involved in the operations of the activity on "
        "a basis which is—\n\n(A) regular,\n\n(B) continuous, and\n\n"
        "(C) substantial."
    )
