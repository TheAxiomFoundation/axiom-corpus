import json
from collections import Counter
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ny-snap-manual.yaml"
VERSION = "2026-07-17-ny-snap-manuals"
SOURCE_DIR = (
    CORPUS_ROOT / "sources/us-ny/manual" / VERSION / "official-documents"
)
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-ny/manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-ny/manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-ny/manual" / f"{VERSION}.json"

EXPECTED_SOURCE_BOOK_SECTIONS = {f"section-{number}" for number in range(1, 22)}
EXPECTED_SOURCES = {
    "ny-otda-snap-source-book": (
        "us-ny/manual/otda/snap-source-book",
        576,
        3_581_357,
        "719ebf91d11071de67199b6c145eaedbcdc4e0affe0791d07603a9917fd0301b",
        "Sept 2025",
    ),
    "ny-otda-employment-manual-introduction": (
        "us-ny/manual/otda/employment-policy-manual/introduction",
        4,
        123_128,
        "28c9a960a954ad226b9e7add1c2adaf3ea0bb3b67a7e13703717540b54dd173e",
        "3/2022",
    ),
    "ny-otda-employment-manual-385-2": (
        "us-ny/manual/otda/employment-policy-manual/385-2",
        38,
        328_686,
        "3b0a44d67381780500ba6cb844a2b7c1dea5223cb3f274db9499bac7c3539fae",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-3": (
        "us-ny/manual/otda/employment-policy-manual/385-3",
        36,
        413_505,
        "68315e38abc893849d644f69a34178d8b1476530f96551affd3c0f28fbc0ba1e",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-4": (
        "us-ny/manual/otda/employment-policy-manual/385-4",
        14,
        169_498,
        "7fc6f1f94a816d01faa8561fc6931ef38bd3f12d858ba665b159f95922fda5b1",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-5": (
        "us-ny/manual/otda/employment-policy-manual/385-5",
        6,
        121_106,
        "b5c2ad993292762cb6d1bae8461abdae4b33b328379a267ea3d21d6b3e3e68f8",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-6": (
        "us-ny/manual/otda/employment-policy-manual/385-6",
        9,
        179_473,
        "c4a73cbd9b800192cc1e45e94f9c572654ef998aefd4f000a98d10f88d4ea473",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-7": (
        "us-ny/manual/otda/employment-policy-manual/385-7",
        9,
        130_246,
        "8a79ad5bdcebe5667f676d53dfb4c3c310f8d963752d6e3d53dc51815a24b455",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-8": (
        "us-ny/manual/otda/employment-policy-manual/385-8",
        23,
        227_771,
        "40d2aeb616cdab287615ea131779efdd77d5e1d13c292138d5cf186d8ba99814",
        "3/2022",
    ),
    "ny-otda-employment-manual-385-9": (
        "us-ny/manual/otda/employment-policy-manual/385-9",
        27,
        304_612,
        "45fa3764731452406b9a9def46886f91004343b4328ccbfe9cb1439752b284f0",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-10": (
        "us-ny/manual/otda/employment-policy-manual/385-10",
        5,
        98_372,
        "8eaba40d9e247a2e735642095f38bf79e0099bc3749993b218eecb2330ae67d6",
        "4/2025",
    ),
    "ny-otda-employment-manual-385-11": (
        "us-ny/manual/otda/employment-policy-manual/385-11",
        20,
        223_708,
        "8f0e458c0f2ed4f33d413dbe61323ae7c1566c420cf26936d8f72eecb4900466",
        "3/2022",
    ),
    "ny-otda-employment-manual-385-12": (
        "us-ny/manual/otda/employment-policy-manual/385-12",
        18,
        204_834,
        "c8aa3c9fde39038f4ae0a382ce18edd146683fd888d726ebcb9d51f4d3b63ba7",
        "3/2022",
    ),
    "ny-otda-employment-manual-385-13": (
        "us-ny/manual/otda/employment-policy-manual/385-13",
        15,
        187_836,
        "7a646dbc5a53ee95a5de110750de86dbbf18044937285b636d9268e4dc15c0a5",
        "3/2022",
    ),
    "ny-otda-employment-manual-appendix-a": (
        "us-ny/manual/otda/employment-policy-manual/appendix-a",
        17,
        278_623,
        "4390495b9f66e09a3c8671a98d84111c67f5b30eb555e25d50dddc591e90f448",
        "3/2022",
    ),
    "ny-otda-employment-manual-appendix-b": (
        "us-ny/manual/otda/employment-policy-manual/appendix-b",
        41,
        1_318_772,
        "5050de6a402d895b90a820353b9a34d6ea6ef239556e60c80ddc33ae98f0b683",
        "3/2022",
    ),
    "ny-otda-employment-manual-appendix-c": (
        "us-ny/manual/otda/employment-policy-manual/appendix-c",
        20,
        249_941,
        "c6a2935408b6f16138025b08991afda6bc898f4c00d1ae62d2888eca5ff83e3a",
        "3/2022",
    ),
}


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_new_york_manifest_pins_complete_official_manual_boundary() -> None:
    documents = _documents()

    assert len(documents) == len(EXPECTED_SOURCES) == 17
    assert {document["source_id"] for document in documents} == set(EXPECTED_SOURCES)
    assert sum(document["metadata"]["page_count"] for document in documents) == 878
    assert sum(document["metadata"]["provision_count"] for document in documents) == 323
    assert all(document["jurisdiction"] == "us-ny" for document in documents)
    assert all(document["document_class"] == "manual" for document in documents)
    assert all(document["source_format"] == "pdf" for document in documents)
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert all(
        document["metadata"]["verified_current_on"] == "2026-07-17"
        for document in documents
    )

    for document in documents:
        citation_path, pages, byte_count, digest, revision = EXPECTED_SOURCES[
            document["source_id"]
        ]
        assert document["citation_path"] == citation_path
        assert document["metadata"]["page_count"] == pages
        assert document["metadata"]["source_byte_count"] == byte_count
        assert document["metadata"]["source_sha256"] == digest
        if document["source_id"] == "ny-otda-snap-source-book":
            assert document["metadata"]["official_manual_version"] == revision
        else:
            assert document["metadata"]["official_revision"] == revision
            assert document["extraction"]["page_citation_prefix"] == "p"


def test_new_york_retained_pdfs_and_generated_rows_match_manifest() -> None:
    documents = {document["source_id"]: document for document in _documents()}
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    retained_files = sorted(SOURCE_DIR.glob("*.pdf"))
    rows_by_source = Counter(row["source_id"] for row in rows)

    assert len(retained_files) == len(documents) == 17
    assert len(rows) == len(inventory) == 340
    assert sum(row["kind"] == "document" for row in rows) == 17
    assert sum(row["kind"] != "document" for row in rows) == 323
    assert len({row["citation_path"] for row in rows}) == 340
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["matched_count"] == coverage["source_count"] == 340
    assert coverage["provision_count"] == 340

    for source_file in retained_files:
        document = documents[source_file.stem]
        with fitz.open(source_file) as pdf:
            assert pdf.page_count == document["metadata"]["page_count"]
        assert source_file.stat().st_size == document["metadata"]["source_byte_count"]
        assert sha256_file(source_file) == document["metadata"]["source_sha256"]
        assert rows_by_source[source_file.stem] == (
            document["metadata"]["provision_count"] + 1
        )


def test_new_york_source_book_sections_and_employment_pages_are_complete() -> None:
    rows = _provisions()
    source_book_rows = [
        row for row in rows if row["source_id"] == "ny-otda-snap-source-book"
    ]
    employment_rows = [
        row
        for row in rows
        if row["source_id"] != "ny-otda-snap-source-book"
        and row["kind"] == "page"
    ]

    assert {
        row["metadata"]["section_label"]
        for row in source_book_rows
        if row["kind"] == "section"
    } == EXPECTED_SOURCE_BOOK_SECTIONS
    assert len(employment_rows) == 302
    assert all("/page-" not in row["citation_path"] for row in rows)

    for source_id, (_, page_count, _, _, _) in EXPECTED_SOURCES.items():
        if source_id == "ny-otda-snap-source-book":
            continue
        page_rows = [row for row in employment_rows if row["source_id"] == source_id]
        assert [row["metadata"]["page_number"] for row in page_rows] == list(
            range(1, page_count + 1)
        )
        assert [row["citation_path"].rsplit("/", 1)[-1] for row in page_rows] == [
            f"p-{page}" for page in range(1, page_count + 1)
        ]


def test_new_york_rows_preserve_delegated_and_current_snap_policy() -> None:
    rows = {row["citation_path"]: row for row in _provisions()}
    base = "us-ny/manual/otda/employment-policy-manual"

    assert "please refer to the Employment Policy Manual" in rows[
        "us-ny/manual/otda/snap-source-book/section-10"
    ]["body"]
    assert "Rev. 4/2025" in rows[f"{base}/385-3/p-1"]["body"]
    assert "Work Registration, Registration Exemptions" in rows[
        f"{base}/385-3/p-1"
    ]["body"]
    assert "required to register for employment" in rows[f"{base}/385-3/p-2"][
        "body"
    ]
    assert "b) SNAP." in rows[f"{base}/385-4/p-2"]["body"]
    assert "SNAP sanctions" in rows[f"{base}/385-12/p-1"]["body"]
    assert "SNAP ABAWD" in rows[f"{base}/appendix-b/p-1"]["body"]
    assert not any(
        "\ufffd" in (row.get("heading") or "") + (row.get("body") or "")
        for row in rows.values()
    )
