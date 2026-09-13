from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-07-26-va-2026-760es"
ROOT_CITATION = "us-va/form/individual-income-tax/2026/760es"
RATE_SCHEDULE_CITATION = f"{ROOT_CITATION}/tax-rate-schedule"
SOURCE_SHA256 = "d2f9a56c429ffcabea81d985f980835223cf403867fe3613a2aa9377f990efa1"


def _provisions() -> list[dict[str, object]]:
    path = REPO_ROOT / f"data/corpus/provisions/us-va/form/{VERSION}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_va_2026_760es_source_and_coverage_are_complete() -> None:
    source = (
        REPO_ROOT
        / f"data/corpus/sources/us-va/form/{VERSION}/official-documents/"
        "us-va-tax-2026-760es.pdf"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256

    coverage_path = REPO_ROOT / f"data/corpus/coverage/us-va/form/{VERSION}.json"
    coverage = json.loads(coverage_path.read_text())
    assert coverage == {
        "complete": True,
        "document_class": "form",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us-va",
        "matched_count": 2,
        "missing_from_provisions": [],
        "provision_count": 2,
        "source_count": 2,
        "version": VERSION,
    }
    assert [row["citation_path"] for row in _provisions()] == [
        ROOT_CITATION,
        RATE_SCHEDULE_CITATION,
    ]


def test_va_2026_760es_preserves_the_full_rate_schedule() -> None:
    schedule = _provisions()[1]
    assert schedule["body"] == (
        "Not over $3,000, your tax is 2% of your Virginia taxable income. "
        "over... but not over... your tax is... of excess over... "
        "$ 3,000 $ 5,000 $ 60 + 3% $ 3,000 "
        "$ 5,000 $ 17,000 $ 120 + 5% $ 5,000 "
        "$ 17,000 $ 720 + 5.75% $ 17,000"
    )


def test_va_2026_760es_is_bounded_to_estimated_tax() -> None:
    schedule = _provisions()[1]
    metadata = schedule["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["tax_year"] == "2026"
    assert metadata["form_number"] == "760ES"
    assert metadata["application_scope"] == "estimated_tax_rate_schedule_only"
    assert metadata["source_status"] == "current_official_tax_year_estimated_form"

    source_note = metadata["source_note"]
    assert isinstance(source_note, str)
    assert "does not establish final Form 760 resident-return liability" in source_note
    assert "taxable-income construction" in source_note
    assert "final-return ordering" in source_note
