"""The corpus-scan timeout budget (tests/corpus_scan.py).

The budget is computed at collection time for every session that imports it, so
sizing the corpus must never raise, and the budget must stay between the
suite-wide timeout and the cap while growing with provision bytes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests import test_citation_path_grammar as grammar_tests
from tests import test_claims as claims_tests
from tests import test_provision_identity_convention as identity_tests
from tests.corpus_scan import (
    MAX_TIMEOUT_SECONDS,
    MIN_SCAN_BYTES_PER_SECOND,
    SUITE_TIMEOUT_SECONDS,
    corpus_scan,
    corpus_scan_timeout,
    provision_jsonl_bytes,
)

corpus_sizes = st.integers(min_value=0, max_value=10**13)


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


# --------------------------------------------------------------------------
# Budget arithmetic
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("corpus_bytes", "expected"),
    [
        (0, 60),
        (600_000_000, 60),
        (600_000_001, 61),
        (2_688_317_382, 269),  # the corpus on 2026-10-10
        (12_000_000_000, 1200),
        (12_000_000_001, 1200),
        (10**13, 1200),
    ],
)
def test_budget_for_known_corpus_sizes(corpus_bytes, expected):
    assert corpus_scan_timeout(corpus_bytes) == expected


@given(corpus_sizes)
def test_budget_stays_between_the_suite_timeout_and_the_cap(corpus_bytes):
    assert SUITE_TIMEOUT_SECONDS <= corpus_scan_timeout(corpus_bytes) <= MAX_TIMEOUT_SECONDS


@given(corpus_sizes, corpus_sizes)
def test_budget_never_shrinks_as_the_corpus_grows(first, second):
    smaller, larger = sorted((first, second))
    assert corpus_scan_timeout(smaller) <= corpus_scan_timeout(larger)


@given(corpus_sizes)
def test_budget_below_the_cap_covers_a_scan_at_the_floor_rate(corpus_bytes):
    budget = corpus_scan_timeout(corpus_bytes)
    if budget < MAX_TIMEOUT_SECONDS:
        assert budget * MIN_SCAN_BYTES_PER_SECOND >= corpus_bytes


# --------------------------------------------------------------------------
# Sizing the corpus on disk
# --------------------------------------------------------------------------
def test_missing_and_empty_trees_have_no_bytes(tmp_path):
    assert provision_jsonl_bytes(tmp_path / "absent") == 0
    assert provision_jsonl_bytes(tmp_path) == 0


def test_sizing_sums_nested_jsonl_and_ignores_other_files(tmp_path):
    _write(tmp_path / "us" / "statute" / "v1.jsonl", 40)
    _write(tmp_path / "us-ca" / "regulation" / "v2.jsonl", 50)
    _write(tmp_path / "us" / "statute" / "v1.json", 500)
    assert provision_jsonl_bytes(tmp_path) == 90


def test_a_dangling_link_does_not_fail_sizing(tmp_path):
    # A broken file must fail in the scan that reads it, not abort the session
    # while this module is imported.
    scope = tmp_path / "us" / "statute"
    _write(scope / "v1.jsonl", 70)
    (scope / "dangling.jsonl").symlink_to(scope / "never-fetched.jsonl")
    assert provision_jsonl_bytes(tmp_path) == 70


# --------------------------------------------------------------------------
# The marker and the tests that carry it
# --------------------------------------------------------------------------
def test_marker_is_a_timeout_carrying_the_budget_of_this_checkout():
    assert corpus_scan.mark.name == "timeout"
    assert corpus_scan.mark.args == (corpus_scan_timeout(provision_jsonl_bytes()),)


def test_the_known_whole_corpus_scans_carry_the_marker():
    # This list is maintained by hand: add any new test that parses every
    # provision row. The grammar module's scan is a module-scoped fixture, charged
    # to whichever test requests it first, so the whole module carries the marker.
    assert grammar_tests.pytestmark is corpus_scan
    for scan in (
        claims_tests.test_every_evidence_span_reextracts_to_its_selector,
        identity_tests.test_committed_provision_ids_follow_the_identity_convention,
    ):
        assert corpus_scan.mark in scan.pytestmark
