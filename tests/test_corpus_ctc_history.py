"""Retained prior-release USC text grounds the child tax credit's former wording."""

import json
from pathlib import Path


def test_retained_2024_child_tax_credit_preserves_prior_law_and_provenance():
    repo = Path(__file__).resolve().parents[1]
    version = "2026-09-27-ctc-history-rp-118-209-title-26"
    provisions = repo / "data/corpus/provisions/us/statute" / f"{version}.jsonl"
    records = [json.loads(line) for line in provisions.read_text().splitlines()]
    source_url = (
        "https://uscode.house.gov/download/releasepoints/us/pl/118/209not159/"
        "xml_usc26@118-209not159.zip"
    )
    assert records
    assert all(record["version"] == version for record in records)
    assert all(record["expression_date"] == "2024-12-23" for record in records)
    assert all(record["source_as_of"] == "2024-12-23" for record in records)
    assert all(record["source_url"] == source_url for record in records)
    by_path = {record["citation_path"]: record for record in records}
    section = "us/statute/26/24"
    assert len(by_path) == len(records)
    assert all(path == section or path.startswith(f"{section}/") for path in by_path)

    amount = by_path[f"{section}/h/2"]["body"]
    assert 'substituting “$2,000” for “$1,000”' in amount
    assert "$2,200" not in amount
    inflation = by_path[f"{section}/h/5/B"]["body"]
    assert "taxable year beginning after 2018, the $1,400 amount" in inflation
    assert 'substituting “2017” for “2016”' in inflation
    assert "rounded to the next lowest multiple of $100" in inflation
    ssn = by_path[f"{section}/h/7"]["body"]
    assert "the taxpayer includes the social security number of such child on the return" in ssn
    assert "the taxpayer’s social security number" not in ssn
    arpa = by_path[f"{section}/i"]
    assert arpa["heading"] == "Special rules for 2021"
    assert "after December 31, 2020" in arpa["body"]
    assert "before January 1, 2022" in arpa["body"]
    assert "$3,000 ($3,600" in arpa["body"]
