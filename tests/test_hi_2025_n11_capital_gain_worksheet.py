from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-07-22-hi-2025-n11-capital-gain-worksheet"
ROOT_CITATION = "us-hi/form/individual-income-tax/2025/n-11-instructions"
WORKSHEET_CITATION = f"{ROOT_CITATION}/capital-gains-tax-worksheet"
SOURCE_SHA256 = "7160595e466b376ba9c14da1540d21532be9e05d48d01d877f5d953c85e4e4d4"
PREDECESSOR_RELEASE = (
    REPO_ROOT / "manifests/releases/us-rulespec-2026-07-22-current-la-status-fix.json"
)
SUCCESSOR_RELEASE = (
    REPO_ROOT / "manifests/releases/us-rulespec-2026-07-22-hi-capital-gain-current.json"
)
FORM_SCOPE = ("us-hi", "form", VERSION)
HRS_SCOPE = (
    "us-hi",
    "statute",
    "2026-07-16-pit-east-us-hi-volume-04-chapter-235",
)


def _provisions() -> list[dict[str, object]]:
    path = REPO_ROOT / f"data/corpus/provisions/us-hi/form/{VERSION}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def _scope_keys(path: Path) -> list[tuple[str, str, str]]:
    payload = json.loads(path.read_text())
    return [
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in payload["scopes"]
    ]


def test_hi_2025_n11_source_and_coverage_are_complete() -> None:
    source = (
        REPO_ROOT
        / f"data/corpus/sources/us-hi/form/{VERSION}/official-documents/"
        "us-hi-dotax-2025-n11-instructions.pdf"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256

    coverage_path = REPO_ROOT / f"data/corpus/coverage/us-hi/form/{VERSION}.json"
    coverage = json.loads(coverage_path.read_text())
    assert coverage == {
        "complete": True,
        "document_class": "form",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us-hi",
        "matched_count": 2,
        "missing_from_provisions": [],
        "provision_count": 2,
        "source_count": 2,
        "version": VERSION,
    }
    assert [row["citation_path"] for row in _provisions()] == [
        ROOT_CITATION,
        WORKSHEET_CITATION,
    ]


def test_hi_2025_capital_gain_worksheet_preserves_smaller_of_rules() -> None:
    worksheet = _provisions()[1]
    body = worksheet["body"]
    assert isinstance(body, str)
    assert "This is your Hawaii net long-term capital gain" in body
    assert "This is your Hawaii net capital gain" in body
    assert "Enter the smaller of line 4 or line 7" in body
    assert "enter the amount from line 4e of Form N-158" in body
    assert "Line 8 minus line 9" in body
    assert "Line 1 minus line 10" in body
    assert "Compute the tax on the amount on line 13" in body
    assert "Multiply line 14 by 7.25% (.0725)" in body
    assert "Line 15 plus line 16" in body
    assert "Compute the tax on the amount on line 1" in body
    assert "Enter the smaller of line 17 or line 18" in body
    assert "Other State and Foreign" not in body


def test_hi_2025_worksheet_is_structural_only_for_2026() -> None:
    worksheet = _provisions()[1]
    metadata = worksheet["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["application_scope"] == "structural_only"
    assert metadata["tax_year"] == "2025"
    assert metadata["target_tax_year"] == "2026"
    assert metadata["statutory_corpus_citation"] == "us-hi/statute/235-51"
    assert metadata["tax_year_2026_alternative_rate"] == "0.0725"
    assert metadata["tax_year_2026_threshold_single_or_married_filing_separately"] == (
        "48000"
    )
    assert metadata["tax_year_2026_threshold_head_of_household"] == "72000"
    assert metadata["tax_year_2026_threshold_joint_or_qualifying_surviving_spouse"] == (
        "96000"
    )
    source_note = metadata["source_note"]
    assert isinstance(source_note, str)
    assert "structural use only" in source_note
    assert "printed line-12 amounts" in source_note
    assert "Use corpus citation us-hi/statute/235-51 for 2026 amounts" in source_note


def test_hi_release_successor_adds_form_and_retains_hrs_authority() -> None:
    predecessor = set(_scope_keys(PREDECESSOR_RELEASE))
    successor_keys = _scope_keys(SUCCESSOR_RELEASE)
    successor = set(successor_keys)
    assert successor == predecessor | {FORM_SCOPE}
    assert len(successor_keys) == len(successor) == 199
    assert successor_keys == sorted(successor_keys)
    assert HRS_SCOPE in successor
