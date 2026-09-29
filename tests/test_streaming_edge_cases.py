"""Edge cases an adversarial review found in the streaming publication paths.

Each was reproduced against the pre-streaming implementation and fixed; these
tests keep them fixed.
"""

from __future__ import annotations

import hashlib
import json
import tracemalloc
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

import axiom_corpus.corpus.supabase as supabase
from axiom_corpus.corpus.io import iter_provisions
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.navigation import build_navigation_nodes
from axiom_corpus.corpus.projection_digest import (
    PROVISION_PROJECTION_COLUMNS,
    provision_projection_sha256,
)
from axiom_corpus.corpus.supabase import load_provisions_to_supabase
from axiom_corpus.release.manifest import _provision_snapshot_projection
from tests._reference_publication import (
    _reference_build_navigation_nodes,
    _reference_load_provisions_to_supabase,
    _reference_provision_projection_sha256,
)


def _outcome(call: Callable[[], object]) -> tuple[str, object]:
    try:
        return ("ok", call())
    except Exception as exc:
        return ("raised", (type(exc), str(exc)))


def test_navigation_raises_the_node_id_error_before_the_label_error() -> None:
    # A surrogate in the path fails the navigation id when there is no
    # version; the non-string heading fails the label. The id came first.
    record = ProvisionRecord.from_mapping(
        {
            "jurisdiction": "us",
            "document_class": "statute",
            "citation_path": "a\ud800",
            "heading": 1,
        }
    )
    expected = _outcome(lambda: _reference_build_navigation_nodes([record]))
    assert expected[0] == "raised" and expected[1][0] is UnicodeEncodeError  # type: ignore[index]
    assert _outcome(lambda: build_navigation_nodes([record])) == expected


class _Ambiguous:
    """A truth value that cannot be decided, like ``pandas.NA``."""

    def __bool__(self) -> bool:
        raise TypeError("boolean value is ambiguous")


def _navigation_record(path: str, **fields: Any) -> ProvisionRecord:
    jurisdiction = path.split("/")[0]
    return ProvisionRecord(
        jurisdiction=jurisdiction, document_class="statute", citation_path=path, **fields
    )


@pytest.mark.parametrize(
    ("records", "kwargs"),
    [
        # A record the jurisdiction filter drops never had its flag read.
        (
            [_navigation_record("us/1"), _navigation_record("ca/1", has_rulespec=_Ambiguous())],
            {"jurisdiction": "us"},
        ),
        # Nor did a repeated citation path.
        ([_navigation_record("us/1"), _navigation_record("us/1", has_rulespec=_Ambiguous())], {}),
        # Parent resolution failed before any flag was read.
        (
            [
                _navigation_record("us/2", parent_citation_path=["x"]),
                _navigation_record("us/3", has_rulespec=_Ambiguous()),
            ],
            {},
        ),
        ([_navigation_record("us/3", has_rulespec=_Ambiguous()), _navigation_record("us/1")], {}),
    ],
)
def test_navigation_reads_the_rulespec_flag_only_where_the_build_did(
    records: list[ProvisionRecord], kwargs: dict[str, object]
) -> None:
    expected = _outcome(lambda: _reference_build_navigation_nodes(records, **kwargs))
    assert _outcome(lambda: build_navigation_nodes(records, **kwargs)) == expected


def test_held_navigation_errors_do_not_keep_record_bodies(tmp_path: Path) -> None:
    rows = 24
    body = "x" * (1024 * 1024)
    path = tmp_path / "provisions.jsonl"
    with path.open("w") as handle:
        for index in range(rows):
            record = {
                "jurisdiction": "us",
                "document_class": "statute",
                "citation_path": f"us/statute/{index}",
                "id": f"not-a-uuid-{index}",
                "body": body,
            }
            handle.write(json.dumps(record) + "\n")
    data = path.read_bytes()
    expected = {
        "expected_sha256": hashlib.sha256(data).hexdigest(),
        "expected_bytes": len(data),
        "expected_rows": rows,
    }
    del data

    def peak(call: Callable[[], object]) -> int:
        tracemalloc.start()
        try:
            try:
                call()
            except ValueError as exc:
                assert "provision id must be a UUID" in str(exc)
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    # Every row's id is invalid, so every row holds an error until the build
    # raises the first; none of them may keep its 1 MB body alive.
    assert peak(lambda: build_navigation_nodes(iter_provisions(path))) < 8 * len(body)
    assert peak(lambda: _provision_snapshot_projection(path, **expected)) < 24 * 1024 * 1024


@pytest.mark.parametrize(
    ("record", "dry_run"),
    [
        (
            ProvisionRecord(
                jurisdiction="us", document_class="regulation", citation_path="us/1", version="v1"
            ),
            True,
        ),
        (
            ProvisionRecord(jurisdiction="us", document_class="regulation", citation_path="us/2"),
            False,
        ),
    ],
)
def test_staging_reads_the_url_only_where_it_did(record: ProvisionRecord, dry_run: bool) -> None:
    # A dry run never needed the URL, and a missing version failed first.
    def run(loader: Callable[..., object]) -> Callable[[], object]:
        return lambda: loader(
            [record], service_key="service", supabase_url=None, dry_run=dry_run
        ).to_mapping()  # type: ignore[attr-defined]

    with mock.patch.object(supabase.urllib.request, "urlopen", side_effect=AssertionError):
        assert _outcome(run(load_provisions_to_supabase)) == _outcome(
            run(_reference_load_provisions_to_supabase)
        )


class _RowView(Mapping[str, object]):
    """A read-only row whose lookups or iteration can fail."""

    def __init__(
        self, row: dict[str, object], *, get_fails: bool = False, iter_fails: bool = False
    ):
        self._row = row
        self._get_fails = get_fails
        self._iter_fails = iter_fails

    def __getitem__(self, key: str) -> object:
        return self._row[key]

    def __iter__(self) -> Iterator[str]:
        if self._iter_fails:
            raise KeyError("iteration failed")
        return iter(self._row)

    def __len__(self) -> int:
        return len(self._row)

    def get(self, key: str, default: object = None) -> object:  # type: ignore[override]
        if self._get_fails:
            raise TypeError("lookup failed")
        return self._row.get(key, default)


_BASE_ROW = dict.fromkeys(PROVISION_PROJECTION_COLUMNS) | {"id": "id-1", "citation_path": "us/1"}
_INVALID_IDENTITY_ROW = dict(_BASE_ROW, citation_path="")


@pytest.mark.parametrize(
    "rows",
    [
        [_RowView(_BASE_ROW, get_fails=True)],
        [_RowView(_BASE_ROW, get_fails=True), _RowView(_BASE_ROW, iter_fails=True)],
        [_INVALID_IDENTITY_ROW, _RowView(_BASE_ROW, get_fails=True)],
        [_RowView(_BASE_ROW, iter_fails=True), _INVALID_IDENTITY_ROW],
    ],
)
def test_projection_digest_keeps_the_materialized_error_for_unusual_rows(
    rows: list[Mapping[str, object]],
) -> None:
    # A TypeError while sorting by identity became "not comparable"; a row
    # whose fields cannot be listed fails before any identity is checked.
    assert _outcome(lambda: provision_projection_sha256(iter(rows))) == _outcome(
        lambda: _reference_provision_projection_sha256(rows)
    )
