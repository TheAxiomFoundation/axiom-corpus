import json
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file
from axiom_corpus.corpus.io import load_provisions, load_source_inventory

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ny-it-214-real-property-tax-credit-ty2025.yaml"
VERSION = "2026-09-23-ny-it-214-ty2025"
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-ny/form" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-ny/form" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-ny/form" / f"{VERSION}.json"
EXPECTED = {
    "us-ny/form/tax/ty2025/it-214": (
        "https://www.tax.ny.gov/pdf/current_forms/it/it214_fill_in.pdf",
        "38708017127e49e7dedf4196cd8f25cf263fbda591ea1fcc2f604779c6aba2be",
    ),
    "us-ny/form/tax/ty2025/it-214-i": (
        "https://www.tax.ny.gov/pdf/current_forms/it/it214i.pdf",
        "e8cc5a14cb3c464ac3fd82fdf62c2684bd11ae95177f7f6495b01b5bc62881f8",
    ),
}


def test_manifest_names_the_official_tax_department_pdfs():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["version"] == VERSION
    documents = {row["citation_path"]: row for row in manifest["documents"]}
    assert set(documents) == set(EXPECTED)
    for citation_path, (url, _sha) in EXPECTED.items():
        row = documents[citation_path]
        assert row["source_url"] == url
        assert row["document_class"] == "form"
        assert row["extraction"] == {"segmentation": "single_block"}
        assert row["metadata"]["primary_source"] is True
        assert row["metadata"]["tax_year"] == "2025"


def test_scope_retains_source_bytes_with_matching_hashes():
    inventory = load_source_inventory(INVENTORY_PATH)
    assert {item.citation_path for item in inventory} == {
        *EXPECTED,
        *(f"{path}/document-1" for path in EXPECTED),
    }
    for item in inventory:
        root = item.citation_path.removesuffix("/document-1")
        url, sha = EXPECTED[root]
        assert item.source_url == url
        assert item.sha256 == sha
        assert sha256_file(CORPUS_ROOT / item.source_path) == sha
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    assert coverage["complete"] is True
    assert coverage["matched_count"] == 4


def test_form_body_carries_the_2025_rate_and_credit_tables_in_row_order():
    records = {record.citation_path: record for record in load_provisions(PROVISIONS_PATH)}
    form = records["us-ny/form/tax/ty2025/it-214/document-1"].body or ""
    assert (
        "Table 1 If the amount on line 8 is: Your rate is: $ 0 to 3000 0.035 "
        "3,001 to 5,000 0.040 5,001 to 7,000 0.045 7,001 to 9,000 0.050 "
        "9,001 to 11,000 0.055 11,001 to 14,000 0.060 14,001 to 18,000 0.065"
    ) in form
    assert (
        "Table A: Taxpayers age 65 or older If you made an entry on line 7 and the "
        "amount on line 8 is: Then enter on line 20: $ 0 to 3,000 $375 3,001 to 5,000 330 "
        "5,001 to 7,000 300 7,001 to 9,000 260 9,001 to 11,000 230 11,001 to 14,000 200 "
        "14,001 to 18,000 150"
    ) in form
    assert (
        "Table B: Taxpayers under age 65 If you did not make an entry on line 7 and the "
        "amount on line 8 is: Then enter on line 20: $ 0 to 5,000 $75 5,001 to 9,000 70 "
        "9,001 to 14,000 60 14,001 to 18,000 50"
    ) in form
    assert "If line 13 is more than $450, stop; you do not qualify for this credit." in form

    instructions = records["us-ny/form/tax/ty2025/it-214-i/document-1"].body or ""
    assert "The average monthly rent you or your spouse" in instructions
    assert "was $450 or less" in instructions
