"""Streaming projection digests and navigation equal the materialized ones.

Invariants, each checked against the pre-streaming implementation on
generated inputs, valid and invalid:

- ``projection_sha256`` returns the same digest, or raises the same exception
  type and message, as hashing the materialized rows.
- ``build_navigation_nodes`` returns the same node tuple, or raises the same
  exception, as building from full records.
- Release content's snapshot projection (digest plus navigation) of a
  provisions file equals ``_load_provision_snapshot`` followed by the
  materialized digest and navigation build, including every failure: a
  changed artifact, undecodable bytes, an unparseable or non-object row, a
  changed row count, a row the Supabase projection rejects, digest errors and
  navigation errors, in the same precedence.
- The digest of rows with distinct identities does not depend on row order.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

import axiom_corpus.release.manifest as manifest
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.navigation import build_navigation_nodes
from axiom_corpus.corpus.projection_digest import (
    NAVIGATION_PROJECTION_COLUMNS,
    PROVISION_PROJECTION_COLUMNS,
    navigation_projection_sha256,
    projection_sha256,
    provision_projection_sha256,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id, iter_supabase_rows
from axiom_corpus.release.manifest import _provision_snapshot_projection, jsonl_row_count
from tests._reference_publication import (
    _reference_build_navigation_nodes,
    _reference_iter_supabase_rows,
    _reference_load_provision_snapshot,
    _reference_navigation_projection_sha256,
    _reference_projection_sha256,
    _reference_provision_projection_sha256,
)

_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)


def _outcome(call: Callable[[], object]) -> tuple[str, object]:
    try:
        return ("ok", call())
    except Exception as exc:
        return ("raised", (type(exc), str(exc)))


def _labelled(outcome: tuple[str, object]) -> tuple[str, object]:
    # Recorded for --hypothesis-show-statistics: generated inputs must reach
    # both successful results and each kind of failure.
    if outcome[0] == "ok":
        event("ok")
    else:
        error_type, message = outcome[1]  # type: ignore[misc]
        event(f"raised {error_type.__name__}: {str(message)[:40]}")
    return outcome


# --- projection_sha256 -----------------------------------------------------

_PROJECTION_TEXT = st.text(
    alphabet=st.sampled_from(list("ab/1:V N") + ["\xe9", "\u4e2d", "\ud800", "\U0001f600"]),
    max_size=6,
)
_PROJECTION_VALUE = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**40), max_value=2**40),
    _PROJECTION_TEXT,
    st.floats(allow_nan=False),
    st.lists(st.integers(), max_size=2),
    st.dictionaries(_PROJECTION_TEXT, st.integers(), max_size=2),
)
_IDENTIFIERS = st.one_of(
    st.none(),
    st.dictionaries(_PROJECTION_TEXT, st.one_of(_PROJECTION_TEXT, st.integers()), max_size=3),
    st.dictionaries(st.integers(), _PROJECTION_TEXT, min_size=1, max_size=2),
    st.dictionaries(_PROJECTION_TEXT, st.lists(st.integers(), max_size=1), min_size=1, max_size=2),
    _PROJECTION_VALUE,
)


_VALID_SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**40), max_value=2**40),
    _PROJECTION_TEXT.filter(lambda text: "\ud800" not in text),
)
_VALID_IDENTIFIERS = st.one_of(
    st.none(),
    st.dictionaries(
        _PROJECTION_TEXT.filter(lambda text: "\ud800" not in text),
        st.one_of(st.integers(), _PROJECTION_TEXT.filter(lambda text: "\ud800" not in text)),
        max_size=3,
    ),
)


@st.composite
def _projection_rows(draw: st.DrawFn, columns: tuple[str, ...], identity: tuple[str, str]):
    # Half the examples are valid rows; in the rest each row may carry one
    # fault (a missing or extra field, an invalid identity, an unencodable
    # value), so several faults of different rank can meet in one example.
    valid = draw(st.booleans())
    rows = []
    for _ in range(draw(st.integers(min_value=0, max_value=7))):
        row: dict[str, object] = {}
        for column in columns:
            if column in identity:
                row[column] = draw(st.sampled_from(["us/a", "us/a/1", "us/b", "id-1", "id-2"]))
            elif column == "identifiers":
                row[column] = draw(_VALID_IDENTIFIERS)
            else:
                row[column] = draw(_VALID_SCALAR)
        fault = 99 if valid else draw(st.integers(min_value=0, max_value=6))
        if fault == 0:
            del row[draw(st.sampled_from(sorted(row)))]
        elif fault == 1:
            row["unexpected"] = None
        elif fault == 2:
            row[draw(st.sampled_from(identity))] = draw(st.one_of(st.just(""), _PROJECTION_VALUE))
        elif fault == 3:
            column = draw(st.sampled_from([c for c in columns if c not in identity]))
            row[column] = draw(_IDENTIFIERS if column == "identifiers" else _PROJECTION_VALUE)
        rows.append(row)
    return rows


@_SETTINGS
@given(data=st.data(), navigation=st.booleans())
def test_projection_digest_matches_materialized_digest(data: st.DataObject, navigation: bool) -> None:
    columns = NAVIGATION_PROJECTION_COLUMNS if navigation else PROVISION_PROJECTION_COLUMNS
    order_by = ("path", "id") if navigation else ("citation_path", "id")
    mapping = None if navigation else {"identifiers"}
    rows = data.draw(_projection_rows(columns, order_by))

    expected = _labelled(
        _outcome(
            lambda: _reference_projection_sha256(
                rows, columns=columns, order_by=order_by, mapping_columns=mapping
            )
        )
    )
    actual = _outcome(
        lambda: projection_sha256(iter(rows), columns=columns, order_by=order_by, mapping_columns=mapping)
    )
    assert actual == expected


@_SETTINGS
@given(data=st.data())
def test_projection_digest_is_independent_of_row_order(data: st.DataObject) -> None:
    rows = [
        dict.fromkeys(PROVISION_PROJECTION_COLUMNS)
        | {
            "id": f"id-{index}",
            "citation_path": data.draw(st.sampled_from(["us/a", "us/b", "us/c"])),
            "body": data.draw(_PROJECTION_TEXT.filter(lambda text: "\ud800" not in text)),
            "level": data.draw(st.integers(min_value=0, max_value=3)),
        }
        for index in range(data.draw(st.integers(min_value=0, max_value=8)))
    ]
    shuffled = data.draw(st.permutations(rows))

    digest = provision_projection_sha256(rows)
    assert provision_projection_sha256(shuffled) == digest
    assert _reference_provision_projection_sha256(shuffled) == digest


def test_projection_digest_propagates_a_failing_row_source() -> None:
    def rows() -> Iterator[dict[str, object]]:
        yield dict.fromkeys(PROVISION_PROJECTION_COLUMNS)  # bad identity, held
        raise RuntimeError("row source failed")

    with pytest.raises(RuntimeError, match="row source failed"):
        provision_projection_sha256(rows())
    with pytest.raises(RuntimeError, match="row source failed"):
        _reference_provision_projection_sha256(rows())


# --- navigation --------------------------------------------------------------

_SEGMENTS = st.sampled_from(["1", "2", "10", "a", "b"])
_PATHS = st.builds(
    lambda parts: "us/statute/" + "/".join(parts),
    st.lists(_SEGMENTS, min_size=1, max_size=3),
)
_UUIDS = st.sampled_from(
    [
        "4f3a7c1e-2d5b-4e8f-9a1c-6b7d8e9f0a1b",
        "0c9e8d7f-6a5b-4c3d-2e1f-0a9b8c7d6e5f",
    ]
)


@st.composite
def _record(draw: st.DrawFn, *, valid: bool = False) -> ProvisionRecord:
    """A provision record; ``valid`` limits every field to publishable values."""
    path = draw(_PATHS)
    if valid:
        version: str | None = "2026-05-01"
        parent: object = draw(st.one_of(st.none(), st.just(path.rsplit("/", 1)[0]), _PATHS))
        record_id: object = draw(
            st.one_of(
                st.none(),
                st.just(deterministic_provision_id(path)),
                st.just(deterministic_provision_id(path, version)),
                _UUIDS,
            )
        )
        parent_id: object = draw(st.one_of(st.none(), _UUIDS))
        heading: object = draw(st.sampled_from([None, "", "  ", "Heading", " padded "]))
        metadata: object = draw(st.sampled_from([None, {}, {"status": "repealed"}, {"other": 1}]))
    else:
        version = draw(st.sampled_from(["2026-05-01", None, "", " "]))
        parent = draw(
            st.one_of(
                st.none(),
                st.just(path.rsplit("/", 1)[0]),
                _PATHS,
                st.just(path),
                st.just(["unhashable"]),
            )
        )
        record_id = draw(
            st.one_of(
                st.none(),
                _UUIDS,
                st.just(deterministic_provision_id(path)),
                st.just("not-a-uuid"),
                st.just(12345),
            )
        )
        parent_id = draw(st.one_of(st.none(), _UUIDS, st.just("not-a-uuid")))
        heading = draw(st.sampled_from([None, "", "Heading", ["list"]]))
        metadata = draw(
            st.sampled_from([None, {}, {"status": "repealed"}, {"status": "  "}, ["x"], "text"])
        )
    return ProvisionRecord(
        jurisdiction=draw(st.sampled_from(["us", "us", "ca"])),
        document_class=draw(st.sampled_from(["statute", "statute", "regulation"])),
        citation_path=path,
        version=version,
        body=draw(
            st.one_of(
                st.none(),
                st.just(""),
                _PROJECTION_TEXT.filter(lambda text: "\ud800" not in text) if valid else _PROJECTION_TEXT,
            )
        ),
        heading=heading,  # type: ignore[arg-type]
        citation_label=draw(st.sampled_from([None, "", "Label", "  "])),
        parent_citation_path=parent,  # type: ignore[arg-type]
        id=record_id,  # type: ignore[arg-type]
        parent_id=parent_id,  # type: ignore[arg-type]
        ordinal=draw(st.sampled_from([None, 0, 3, 11, -1, 2**40, True])),
        level=draw(st.sampled_from([None, 0, 1, 2])),
        has_rulespec=draw(st.sampled_from([None, True, False, 1, "yes"])),
        metadata=metadata,  # type: ignore[arg-type]
        identifiers=draw(st.one_of(st.none(), st.just({"k": "v"}))),
    )


_RECORDS = st.booleans().flatmap(lambda valid: st.lists(_record(valid=valid), max_size=8))


@_SETTINGS
@given(
    records=_RECORDS,
    jurisdiction=st.sampled_from([None, "us"]),
    document_class=st.sampled_from([None, "statute"]),
    encoded=st.one_of(st.none(), st.lists(_PATHS, max_size=3)),
)
def test_navigation_build_matches_full_record_build(
    records: list[ProvisionRecord],
    jurisdiction: str | None,
    document_class: str | None,
    encoded: list[str] | None,
) -> None:
    def build(builder: Callable[..., object]) -> Callable[[], object]:
        return lambda: builder(
            iter(records),
            jurisdiction=jurisdiction,
            document_class=document_class,
            encoded_paths=encoded,
        )

    expected = _labelled(_outcome(build(_reference_build_navigation_nodes)))
    assert _outcome(build(build_navigation_nodes)) == expected


# --- release content snapshot projection -------------------------------------


@st.composite
def _snapshot_file(draw: st.DrawFn) -> tuple[bytes, int]:
    valid = draw(st.booleans())
    records = draw(st.lists(_record(valid=valid), max_size=6))
    lines = [
        json.dumps(record.to_mapping(), sort_keys=True, ensure_ascii=draw(st.booleans()))
        for record in records
    ]
    fault = 99 if valid else draw(st.integers(min_value=0, max_value=4))
    if fault == 0:
        lines.insert(draw(st.integers(min_value=0, max_value=len(lines))), "{broken")
    elif fault == 1:
        lines.insert(draw(st.integers(min_value=0, max_value=len(lines))), "[1]")
    elif fault == 2:
        lines.insert(draw(st.integers(min_value=0, max_value=len(lines))), '{"citation_path": "x"}')
    separator = draw(st.sampled_from(["\n", "\r\n", "\n\n"]))
    data = (separator.join(lines) + draw(st.sampled_from(["", "\n"]))).encode(
        "utf-8", "surrogatepass"
    )
    if data and fault == 3:
        at = draw(st.integers(min_value=0, max_value=len(data)))
        data = data[:at] + b"\xff" + data[at:]
    return data, fault


def _reference_snapshot_projection(path: Path, **expected: object) -> object:
    records = _reference_load_provision_snapshot(path, **expected)  # type: ignore[arg-type]
    digest = _reference_provision_projection_sha256(_reference_iter_supabase_rows(records))
    return digest, _reference_build_navigation_nodes(records)


@_SETTINGS
@given(
    snapshot=_snapshot_file(),
    wrong=st.sampled_from([None] * 7 + ["sha256", "bytes", "rows"]),
    memory_bytes=st.sampled_from([1, 64, 8 * 1024 * 1024]),
    read_bytes=st.sampled_from([1, 7, 1024 * 1024]),
)
def test_snapshot_projection_matches_whole_snapshot(
    snapshot: tuple[bytes, int],
    wrong: str | None,
    memory_bytes: int,
    read_bytes: int,
) -> None:
    data, _fault = snapshot
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "provisions.jsonl"
        path.write_bytes(data)
        expected_args: dict[str, object] = {
            "expected_sha256": hashlib.sha256(data).hexdigest(),
            "expected_bytes": len(data),
            "expected_rows": jsonl_row_count(path),
        }
        if wrong == "sha256":
            expected_args["expected_sha256"] = "0" * 64
        elif wrong == "bytes":
            expected_args["expected_bytes"] = len(data) + 1
        elif wrong == "rows":
            expected_args["expected_rows"] = int(expected_args["expected_rows"]) + 1  # type: ignore[call-overload]

        expected = _labelled(
            _outcome(lambda: _reference_snapshot_projection(path, **expected_args))
        )
        with (
            mock.patch.object(manifest, "_SNAPSHOT_MEMORY_BYTES", memory_bytes),
            mock.patch.object(manifest, "_SNAPSHOT_READ_BYTES", read_bytes),
        ):
            actual = _outcome(
                lambda: _provision_snapshot_projection(path, **expected_args)  # type: ignore[arg-type]
            )
    assert actual == expected


def test_snapshot_projection_names_the_whole_file_byte_position(tmp_path: Path) -> None:
    row = json.dumps({"jurisdiction": "us", "document_class": "statute", "citation_path": "us/1"})
    data = (row + "\n").encode() * 3000 + b"{broken\n\xff\n"
    path = tmp_path / "provisions.jsonl"
    path.write_bytes(data)
    expected_args = {
        "expected_sha256": hashlib.sha256(data).hexdigest(),
        "expected_bytes": len(data),
        "expected_rows": jsonl_row_count(path),
    }

    expected = _outcome(lambda: _reference_snapshot_projection(path, **expected_args))
    assert expected[0] == "raised"
    assert f"position {len(data) - 2}" in str(expected[1])
    assert _outcome(lambda: _provision_snapshot_projection(path, **expected_args)) == expected


def test_snapshot_projection_digests_match_the_publish_evidence_helpers(tmp_path: Path) -> None:
    # The exact digests the publisher compares with staged Supabase evidence.
    records = [
        ProvisionRecord(
            jurisdiction="us",
            document_class="statute",
            citation_path="us/statute/26",
            version="2026-04-29",
            heading="Title 26",
            expression_date="2026-04-29",
        ),
        ProvisionRecord(
            jurisdiction="us",
            document_class="statute",
            citation_path="us/statute/26/1",
            parent_citation_path="us/statute/26",
            version="2026-04-29",
            body="Tax imposed.",
            ordinal=10701001001,
        ),
    ]
    path = tmp_path / "provisions.jsonl"
    path.write_text("\n".join(json.dumps(r.to_mapping(), sort_keys=True) for r in records) + "\n")
    data = path.read_bytes()

    digest, navigation = _provision_snapshot_projection(
        path,
        expected_sha256=hashlib.sha256(data).hexdigest(),
        expected_bytes=len(data),
        expected_rows=2,
    )

    assert digest == provision_projection_sha256(iter_supabase_rows(records))
    assert navigation == build_navigation_nodes(records)
    assert navigation_projection_sha256(node.to_supabase_row() for node in navigation) == (
        _reference_navigation_projection_sha256(
            node.to_supabase_row() for node in _reference_build_navigation_nodes(records)
        )
    )
