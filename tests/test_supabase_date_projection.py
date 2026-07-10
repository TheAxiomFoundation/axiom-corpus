"""Regression tests for safe Supabase date projection."""

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.supabase import (
    _coerce_date_column_value,
    provision_to_supabase_row,
)


def test_coerce_date_truncates_version_slug_to_iso_prefix() -> None:
    value, original = _coerce_date_column_value("2026-07-01-be-company-car-tax-benefit-guidance")
    assert value == "2026-07-01"
    assert original == "2026-07-01-be-company-car-tax-benefit-guidance"


def test_coerce_date_canonicalizes_valid_dates_and_timestamps() -> None:
    assert _coerce_date_column_value("2026-07-03") == ("2026-07-03", None)
    assert _coerce_date_column_value("2026-07-01T12:00:00") == (
        "2026-07-01",
        "2026-07-01T12:00:00",
    )
    assert _coerce_date_column_value("2026-07-10T23:00:00Z") == (
        "2026-07-10",
        "2026-07-10T23:00:00Z",
    )
    assert _coerce_date_column_value(None) == (None, None)


def test_coerce_date_nulls_unparseable_values() -> None:
    assert _coerce_date_column_value("not-a-date") == (None, "not-a-date")
    assert _coerce_date_column_value("2026-13-99-x") == (None, "2026-13-99-x")


def test_projection_coerces_bad_dates_and_stashes_originals() -> None:
    record = ProvisionRecord(
        jurisdiction="be",
        document_class="guidance",
        citation_path="be/guidance/spf/company-car/2026-faq",
        version="2026-07-01-be-company-car-tax-benefit-guidance",
        expression_date="2026-07-01-be-company-car-tax-benefit-guidance",
        source_as_of="2026-06-30-be-tax-benefit",
    )

    row = provision_to_supabase_row(record)

    assert row["expression_date"] == "2026-07-01"
    assert row["source_as_of"] == "2026-06-30"
    assert (
        row["identifiers"]["corpus:raw_expression_date"]
        == "2026-07-01-be-company-car-tax-benefit-guidance"
    )
    assert row["identifiers"]["corpus:raw_source_as_of"] == "2026-06-30-be-tax-benefit"
    assert row["version"] == "2026-07-01-be-company-car-tax-benefit-guidance"
