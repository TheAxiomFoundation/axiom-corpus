"""Unit tests for the grammar-safe citation segment helper."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from axiom_corpus.corpus.citation_segment import citation_segment, variant_segment

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "citation-path.v1.json"


@pytest.fixture(scope="module")
def segment_pattern() -> re.Pattern[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return re.compile(schema["$defs"]["hierarchy_segment"]["pattern"])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Nebraska comma-numbered sections.
        ("77-3,100", "77-3-100"),
        ("77-27,187", "77-27-187"),
        # Connecticut RCSA section ids with parenthesised statute subsections.
        ("12-740(a)-1", "12-740-a-1"),
        ("12-701(a)(20)-1", "12-701-a-20-1"),
        # Colorado 1 CCR 201-2 rule numbers.
        ("39-22-103(1)", "39-22-103-1"),
        ("39-22-103(8)(a)", "39-22-103-8-a"),
        ("39-22-104(1.7)", "39-22-104-1.7"),
        ("39-22-104(2)–1", "39-22-104-2-1"),
        # Delaware combined repealed headings.
        ("1159, 1160", "1159-1160"),
        # Punctuation at the edges is dropped, not turned into a hyphen.
        ("(a)", "a"),
        ("§ 12", "12"),
        # safe_segment's older substitutions still hold.
        ("a\\b:c", "a-b-c"),
    ],
)
def test_citation_segment_folds_unsafe_runs_into_one_hyphen(
    raw: str, expected: str, segment_pattern: re.Pattern[str]
) -> None:
    result = citation_segment(raw)
    assert result == expected
    assert segment_pattern.fullmatch(result)


@pytest.mark.parametrize(
    "already_safe",
    [
        "40-21-123",
        "77-2701.01",
        "He-W 766.01",
        "7 AAC 45.010",
        "8.139.502.9-10",
        "12-747-to-12-789",
        "subpart-A",
        "block-1",
        "foo-",  # trailing hyphens are ratcheted, not rewritten here
        "39-22-303–1",  # en-dash is grammar-valid and kept unless asked
    ],
)
def test_citation_segment_leaves_grammar_valid_segments_unchanged(already_safe: str) -> None:
    assert citation_segment(already_safe) == already_safe


def test_citation_segment_normalizes_dashes_only_on_request() -> None:
    assert citation_segment("39-22-303–1", normalize_dashes=True) == "39-22-303-1"
    assert citation_segment("39-22-303.5–10", normalize_dashes=True) == "39-22-303.5-10"
    assert citation_segment("a—b", normalize_dashes=True) == "a-b"
    assert citation_segment("39-22-303–1") == "39-22-303–1"


def test_citation_segment_is_idempotent() -> None:
    for raw in ("77-3,100", "12-740(a)-1", "1159, 1160", "39-22-104(2)–1"):
        once = citation_segment(raw)
        assert citation_segment(once) == once


@pytest.mark.parametrize("raw", ["", "   ", "()", "@", ".", ".."])
def test_citation_segment_rejects_segments_without_content(raw: str) -> None:
    with pytest.raises(ValueError):
        citation_segment(raw)


def test_variant_segment_joins_with_double_hyphen() -> None:
    assert variant_segment("801", None) == "801"
    assert variant_segment("801", "") == "801"
    assert variant_segment("801", "effective-january-1-2027") == "801--effective-january-1-2027"
    assert variant_segment("40-21-123", "code-28957") == "40-21-123--code-28957"
    assert variant_segment("101", "variant (2)") == "101--variant-2"
