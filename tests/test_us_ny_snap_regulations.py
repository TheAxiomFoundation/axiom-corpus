import json
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ny-snap-regulations.yaml"
VERSION = "2026-07-17-ny-snap-regulations"
SOURCE_DIR = CORPUS_ROOT / "sources/us-ny/regulation" / VERSION / "nycrr"
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-ny/regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-ny/regulation" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-ny/regulation" / f"{VERSION}.json"

EXPECTED_ROW_COUNT = 1_678
EXPECTED_SECTION_CITATIONS = {
    "18 CRR-NY 385.0",
    *(f"18 CRR-NY 385.{number}" for number in range(2, 14)),
    *(f"18 CRR-NY 387.{number}" for number in range(26)),
}
EXPECTED_AMENDMENT_FILES = {
    "ny-register-tda-41-25-00025-text.pdf": (
        1_022_894,
        "4dbfc93a066b640da53f0a0817bccd65d37f850e065ed3b707330fa6d582a993",
    ),
    "ny-register-tda-41-25-00025-adoption.pdf": (
        7_555_813,
        "0b613beba5abed601f7fb879a05a9a8802975776fabc3274e1b8d1954b5ec25e",
    ),
}


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_new_york_manifest_pins_full_snap_regulation_boundary() -> None:
    manifest = _manifest()
    parts = manifest["parts"]
    amendments = manifest["adopted_amendments"]

    assert [(part["part"], part["expected_document_count"], part["expected_section_count"]) for part in parts] == [
        ("385", 14, 13),
        ("387", 28, 26),
    ]
    assert all("govt.westlaw.com/nycrr/Browse/" in part["source_url"] for part in parts)
    assert all(part["metadata"]["discovered_via"] == "official-nycrr-part-browse" for part in parts)
    assert len(amendments) == 1
    assert amendments[0]["target_citation_path"] == "us-ny/regulation/18-nycrr/387/12/f/3/v"
    assert amendments[0]["effective_date"] == "2026-02-25"
    assert amendments[0]["adoption_confirmation"].endswith("No changes.")


def test_new_york_sources_and_generated_scope_are_complete() -> None:
    rows = _provisions()
    paths = {row["citation_path"] for row in rows}
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    source_files = [path for path in SOURCE_DIR.rglob("*") if path.is_file()]

    assert len(source_files) == 46
    assert len(list((SOURCE_DIR / "browse").glob("*.html"))) == 2
    assert len(list((SOURCE_DIR / "document").glob("*.html"))) == 42
    assert len(list((SOURCE_DIR / "amendment").glob("*.pdf"))) == 2
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len(paths) == EXPECTED_ROW_COUNT
    assert sum(row["kind"] == "part" for row in rows) == 2
    assert sum(row["kind"] == "section" for row in rows) == 39
    assert {row["citation_label"] for row in rows if row["kind"] == "section"} == EXPECTED_SECTION_CITATIONS
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT

    for path in paths - {
        "us-ny/regulation/18-nycrr/385",
        "us-ny/regulation/18-nycrr/387",
    }:
        assert path.rsplit("/", 1)[0] in paths

    for filename, (byte_count, digest) in EXPECTED_AMENDMENT_FILES.items():
        source_file = SOURCE_DIR / "amendment" / filename
        assert source_file.stat().st_size == byte_count
        assert sha256_file(source_file) == digest


def test_new_york_nested_paths_and_current_sua_amendment_are_preserved() -> None:
    rows = {row["citation_path"]: row for row in _provisions()}
    amendment_base = "us-ny/regulation/18-nycrr/387/12/f/3/v"

    assert "exemption shall last no longer than three months" in rows[
        "us-ny/regulation/18-nycrr/385/2/b/7/i"
    ]["body"]
    assert "all members are recipients" in rows[
        "us-ny/regulation/18-nycrr/387/14/a/5/i/a"
    ]["body"]
    nested_kinds = {"subdivision", "paragraph", "subparagraph", "clause", "subclause"}
    assert all(row["body"] for row in rows.values() if row["kind"] in nested_kinds)
    assert not any(
        "\ufffd" in (row.get("heading") or "") + (row["body"] or "")
        for row in rows.values()
    )

    amended = [rows[amendment_base], *(rows[f"{amendment_base}/{label}"] for label in "abc")]
    assert all(row["source_format"] == "ny-state-register-pdf" for row in amended)
    assert all(row["source_as_of"] == row["expression_date"] == "2026-02-25" for row in amended)
    assert all(row["metadata"]["adopted_amendment"] == "ny-register-tda-41-25-00025" for row in amended)
    assert "$1,062" in rows[f"{amendment_base}/a"]["body"]
    assert "$988" in rows[f"{amendment_base}/a"]["body"]
    assert "$877" in rows[f"{amendment_base}/a"]["body"]
    assert "$419" in rows[f"{amendment_base}/b"]["body"]
    assert "$388" in rows[f"{amendment_base}/b"]["body"]
    assert "$355" in rows[f"{amendment_base}/b"]["body"]
    assert "$32" in rows[f"{amendment_base}/c"]["body"]
    assert "Department of Agriculture" in rows[f"{amendment_base}/a"]["body"]

    amended_text = "\n".join(row["body"] for row in amended)
    for superseded_value in ("$1,034", "$962", "$854", "$408", "$378", "$346", "$31"):
        assert superseded_value not in amended_text


def test_new_york_base_rows_disclose_official_online_source_caveat() -> None:
    base_rows = [row for row in _provisions() if "adopted_amendment" not in row["metadata"]]

    assert all(row["metadata"]["primary_source"] is True for row in base_rows)
    assert all(
        row["metadata"]["source_caveat"]
        == "Online NYCRR is unofficial and not for evidentiary use."
        for row in base_rows
    )
    assert all(
        row["metadata"].get("current_through") == "2021-09-15"
        for row in base_rows
        if row["kind"] != "part"
    )
