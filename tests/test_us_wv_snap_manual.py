import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANUAL_MANIFEST_PATH = REPO_ROOT / "manifests" / "us-wv-manuals.yaml"
OVERLAY_MANIFEST_PATH = (
    REPO_ROOT / "manifests" / "us-wv-snap-healthy-choices-overlay.yaml"
)
MANUAL_VERSION = "2026-07-21-wv-income-maintenance-manual"
OVERLAY_VERSION = "2026-07-21-wv-snap-healthy-choices-overlay"
MANUAL_SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-wv/manual"
    / MANUAL_VERSION
    / "official-documents/wv-bfa-income-maintenance-manual-2026-07-01.pdf"
)
OVERLAY_SOURCE_PATH = (
    CORPUS_ROOT
    / "sources/us-wv/manual"
    / OVERLAY_VERSION
    / "official-documents/wv-bfa-snap-healthy-choices-pause-2026-07-10.html"
)

EXPECTED_MANUAL_SHA256 = "551ed2bcc677262e9bcbc2b28d1474d27b6734d89ad07b1cb5da829dc2c4bb3f"
EXPECTED_MANUAL_BYTES = 24_621_268
EXPECTED_PAGE_COUNT = 2_275
EXPECTED_MANUAL_ROW_COUNT = EXPECTED_PAGE_COUNT + 1
EXPECTED_CHAPTER_RANGES = [
    ("IMM Introduction Final", 1, 7),
    ("Chapter_01_Application_Redetermination_Process ", 8, 273),
    ("Chapter_02_Common_Eligibility_Requirments", 274, 301),
    ("Chapter_03_Eligibility_Determination_Groups", 302, 402),
    ("Chapter_04_Appendices", 403, 455),
    ("Chapter_04_Income", 456, 719),
    ("Chapter_05_Assets", 720, 831),
    ("Chapter_06_Data_Exchanges", 832, 865),
    ("Chapter_07_Verification", 866, 911),
    ("Chapter_08_Resource_Development_Medicaid_WV_WORKS_Only", 912, 940),
    ("Chapter_09_Client_Notification", 941, 980),
    ("Chapter_10_Case_Maintenance_Process", 981, 1080),
    ("Chapter_11_Benefit_Repayment", 1081, 1126),
    ("Chapter_12_Benefit_Replacement", 1127, 1148),
    ("Chapter_13_Determining_Disability_Incapacity_Blindness", 1149, 1208),
    ("Chapter_14_Work_Requirements", 1209, 1255),
    ("Chapter_15_NonCitzens_Refugees_Citizenship", 1256, 1350),
    ("Chapter_16_Specific_SNAP_Requirements", 1351, 1369),
    ("Chapter_17_SNAP_E&T", 1370, 1402),
    ("Chapter_18_WV_WORKS_Activities_Requirements-8-2-23", 1403, 1606),
    ("Chapter_19_School_Clothing_Allowance", 1607, 1625),
    ("Chapter_20_Emergency_Special_ Assistance_ Programs", 1626, 1717),
    ("Chapter_21_LIEAP", 1718, 1779),
    ("Chapter_22_WVCHIP", 1780, 1836),
    ("Chapter_23_Specific_Medicaid_Requirements", 1837, 1906),
    ("Chapter_24_Long_Term_Care", 1907, 2112),
    ("Chapter_25_Medicaid_Buy_In_Procedures", 2113, 2119),
    ("Chapter_26_M_WIN", 2120, 2159),
    ("Chapter_27_NEMT", 2160, 2173),
    ("Chapter_28_Special_Pharmacy", 2174, 2197),
    ("Chapter_29_COVID-19_Testing_Group_Medicaid", 2198, 2209),
    ("IMM Acronyms Forms Glossary", 2210, 2275),
]


def _document(path: Path) -> dict:
    return yaml.safe_load(path.read_text())["documents"][0]


def _scope_paths(version: str) -> tuple[Path, Path, Path]:
    return (
        CORPUS_ROOT / "inventory/us-wv/manual" / f"{version}.json",
        CORPUS_ROOT / "provisions/us-wv/manual" / f"{version}.jsonl",
        CORPUS_ROOT / "coverage/us-wv/manual" / f"{version}.json",
    )


def _provisions(version: str) -> list[dict]:
    return [json.loads(line) for line in _scope_paths(version)[1].read_text().splitlines()]


def test_west_virginia_manifest_pins_current_integrated_manual() -> None:
    document = _document(MANUAL_MANIFEST_PATH)

    assert document["source_url"] == "https://bfa.wv.gov/media/39948/download?inline="
    assert document["source_as_of"] == "2026-07-21"
    assert document["expression_date"] == "2026-07-01"
    assert document["metadata"]["manual_landing_page"] == (
        "https://bfa.wv.gov/income-maintenance-manual"
    )
    assert document["metadata"]["source_document_filename"] == (
        "Binder4 - Effective 07-01-2026_0.pdf"
    )
    assert document["metadata"]["current_snap_asset_section"] == "5.4"
    assert document["metadata"]["superseded_snap_asset_section"] == "11.3"


def test_west_virginia_manual_source_and_generated_scope_are_complete() -> None:
    inventory_path, _, coverage_path = _scope_paths(MANUAL_VERSION)
    rows = _provisions(MANUAL_VERSION)
    inventory = json.loads(inventory_path.read_text())["items"]
    coverage = json.loads(coverage_path.read_text())

    with fitz.open(MANUAL_SOURCE_PATH) as pdf:
        chapter_starts = [(title, page) for _, title, page in pdf.get_toc()]
        chapter_ranges = [
            (
                title,
                start,
                chapter_starts[index + 1][1] - 1
                if index + 1 < len(chapter_starts)
                else pdf.page_count,
            )
            for index, (title, start) in enumerate(chapter_starts)
        ]
        assert pdf.page_count == EXPECTED_PAGE_COUNT
        assert all(page.get_text().strip() for page in pdf)
        assert chapter_ranges == EXPECTED_CHAPTER_RANGES

    assert MANUAL_SOURCE_PATH.stat().st_size == EXPECTED_MANUAL_BYTES
    assert sha256_file(MANUAL_SOURCE_PATH) == EXPECTED_MANUAL_SHA256
    assert len(rows) == len(inventory) == EXPECTED_MANUAL_ROW_COUNT
    assert rows[0]["kind"] == "document"
    assert [row["metadata"]["page_number"] for row in rows[1:]] == list(
        range(1, EXPECTED_PAGE_COUNT + 1)
    )
    assert all(row["body"] for row in rows[1:])
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_MANUAL_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_MANUAL_ROW_COUNT
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []


def test_west_virginia_manual_pins_current_snap_policy_content() -> None:
    pages = {row["metadata"]["page_number"]: row["body"] for row in _provisions(MANUAL_VERSION)[1:]}

    assert "1.4.20 SNAP HEALTHY CHOICES DEMONSTRATION WAIVER" in pages[119]
    assert "Effective January 1, 2026" in pages[119]
    assert "SNAP benefits may not be used to purchase soda" in pages[119]
    assert "5.4 MAXIMUM ALLOWABLE ASSETS" in pages[747]
    assert "$3,000" in pages[747]
    assert "$4,500" in pages[747]
    assert "Chapter 16 Specific SNAP Requirements" in pages[1351]
    assert "prohibition on soda purchases" in pages[1366]
    assert "Chapter 17 Supplemental Nutrition Assistance Program Employment and Training" in pages[1370]
    assert "SNAP E&T Participant Reimbursements" in pages[1385]
    assert "up to $3,000 lifetime" in pages[1385]


def test_west_virginia_healthy_choices_overlay_is_complete_and_current() -> None:
    document = _document(OVERLAY_MANIFEST_PATH)
    inventory_path, _, coverage_path = _scope_paths(OVERLAY_VERSION)
    rows = _provisions(OVERLAY_VERSION)
    inventory = json.loads(inventory_path.read_text())["items"]
    coverage = json.loads(coverage_path.read_text())

    assert document["expression_date"] == "2026-07-10"
    assert document["extraction"]["html_content_selector"] == (
        ".block-field-blocknodearticlebody .field--name-body"
    )
    assert document["metadata"]["supersedes_manual_sections"] == ["1.4.20", "16.3"]
    assert len(rows) == len(inventory) == 2
    assert [row["kind"] for row in rows] == ["document", "block"]
    assert "discontinuing the implementation" in rows[1]["body"]
    assert "sweetened, carbonated beverages are currently eligible" in rows[1]["body"]
    assert "effective immediately" in rows[1]["body"]
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 2
    assert coverage["provision_count"] == 2
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert OVERLAY_SOURCE_PATH.is_file()
