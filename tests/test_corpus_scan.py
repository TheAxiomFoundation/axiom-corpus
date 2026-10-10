"""The corpus-scan timeout budget (tests/corpus_scan.py).

The budget is computed at collection time for every session, so it must never
raise, never drop below the suite-wide timeout, and grow with provision bytes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.corpus_scan import (
    MIN_SCAN_BYTES_PER_SECOND,
    SUITE_TIMEOUT_SECONDS,
    corpus_scan,
    corpus_scan_timeout,
)


def _sparse(path: Path, size: int) -> None:
    """Create a file that reports ``size`` bytes without writing them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.truncate(size)


def test_missing_and_empty_trees_get_the_suite_timeout(tmp_path):
    assert corpus_scan_timeout(tmp_path / "absent") == SUITE_TIMEOUT_SECONDS
    assert corpus_scan_timeout(tmp_path) == SUITE_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (1, SUITE_TIMEOUT_SECONDS),
        (SUITE_TIMEOUT_SECONDS * MIN_SCAN_BYTES_PER_SECOND, SUITE_TIMEOUT_SECONDS),
        (SUITE_TIMEOUT_SECONDS * MIN_SCAN_BYTES_PER_SECOND + 1, SUITE_TIMEOUT_SECONDS + 1),
        (200 * MIN_SCAN_BYTES_PER_SECOND, 200),
        (200 * MIN_SCAN_BYTES_PER_SECOND + 1, 201),
    ],
)
def test_budget_is_one_second_per_floor_bytes_and_never_below_the_suite_timeout(
    tmp_path, size, expected
):
    _sparse(tmp_path / "us" / "statute" / "v1.jsonl", size)
    assert corpus_scan_timeout(tmp_path) == expected


def test_budget_sums_nested_jsonl_and_ignores_other_files(tmp_path):
    _sparse(tmp_path / "us" / "statute" / "v1.jsonl", 40 * MIN_SCAN_BYTES_PER_SECOND)
    _sparse(tmp_path / "us-ca" / "regulation" / "v2.jsonl", 50 * MIN_SCAN_BYTES_PER_SECOND)
    _sparse(tmp_path / "us" / "statute" / "v1.json", 500 * MIN_SCAN_BYTES_PER_SECOND)
    assert corpus_scan_timeout(tmp_path) == 90


def test_budget_grows_with_the_corpus(tmp_path):
    budgets = []
    for index in range(4):
        _sparse(tmp_path / "us" / "statute" / f"v{index}.jsonl", 45 * MIN_SCAN_BYTES_PER_SECOND)
        budgets.append(corpus_scan_timeout(tmp_path))
    assert budgets == [SUITE_TIMEOUT_SECONDS, 90, 135, 180]


def test_a_dangling_link_does_not_fail_collection(tmp_path):
    # A broken file must fail in the scan that reads it, not abort the session
    # while this module is imported.
    scope = tmp_path / "us" / "statute"
    _sparse(scope / "v1.jsonl", 70 * MIN_SCAN_BYTES_PER_SECOND)
    (scope / "dangling.jsonl").symlink_to(scope / "never-fetched.jsonl")
    assert corpus_scan_timeout(tmp_path) == 70


def test_marker_carries_the_budget_of_the_checkout_corpus():
    assert corpus_scan.mark.name == "timeout"
    assert corpus_scan.mark.args == (corpus_scan_timeout(),)
    assert corpus_scan.mark.args[0] >= SUITE_TIMEOUT_SECONDS
