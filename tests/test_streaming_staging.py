"""Spooled provision staging plans and writes exactly what in-memory staging did.

Invariants, checked on generated incoming loads and pre-staged database
states (identical rows, divergent content, superseded ids, stale parent
pointers, unexpected rows, cross-scope dependents, repeated keys, cycles):

- The spooled ``load_provisions_to_supabase`` and the pre-streaming
  implementation return the same report, or raise the same exception with
  the same conflicts, issue the same HTTP requests with the same payloads in
  the same order, and leave the same table state.
- Every staging conflict is raised before any write.
- A staged state that is a verified subset of the load (the partial May load
  the base-layer restore must reconcile) converges by inserting exactly the
  missing rows.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from unittest import mock

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.supabase as supabase
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.supabase import (
    ProvisionStagingConflictError,
    deterministic_provision_id,
    load_provisions_to_supabase,
    provision_to_supabase_row,
)
from tests._reference_publication import _reference_load_provisions_to_supabase
from tests.test_corpus_supabase import FakeSupabaseProvisions

_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

_PATHS = (
    "us/regulation/7/273",
    "us/regulation/7/273/1",
    "us/regulation/7/273/2",
    "us/regulation/7/274",
    "us/regulation/7/274/a",
)
_VERSIONS = ("2026-05-13", "2026-06-01")


class _RecordingFake(FakeSupabaseProvisions):
    """The stateful PostgREST double, also recording every request body."""

    def __init__(self, rows=()):
        super().__init__(rows)
        self.requests: list[tuple[str, str, object]] = []

    def urlopen(self, req, timeout):
        body = json.loads(req.data) if req.data else None
        self.requests.append((req.get_method(), req.full_url, body))
        return super().urlopen(req, timeout)


def _parent_of(path: str) -> str | None:
    parent = path.rsplit("/", 1)[0]
    return parent if parent in _PATHS else None


@st.composite
def _record(draw: st.DrawFn, path: str, version: str, *, borrow: bool = True) -> ProvisionRecord:
    parent = _parent_of(path)
    schemes = ["derived", "derived", "legacy", "borrowed"] if borrow else ["derived", "legacy"]
    id_scheme = draw(st.sampled_from(schemes))
    record_id: str | None = None
    parent_id: str | None = None
    if id_scheme == "legacy":
        record_id = deterministic_provision_id(path)
        if parent is not None and draw(st.booleans()):
            parent_id = deterministic_provision_id(parent)
    elif id_scheme == "borrowed":
        # Explicit ids naming another path's row, legacy or versioned: these
        # reach duplicate pending ids, parent cycles, and references to rows
        # a replacement deletes.
        other = draw(st.sampled_from(_PATHS))
        borrowed = draw(
            st.sampled_from(
                [deterministic_provision_id(other), deterministic_provision_id(other, version)]
            )
        )
        if draw(st.booleans()):
            record_id = borrowed
        else:
            parent_id = borrowed
    return ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path=path,
        version=version,
        parent_citation_path=parent,
        body=draw(st.sampled_from(["text", "other text", None])),
        level=path.count("/") - 3,
        ordinal=draw(st.integers(min_value=0, max_value=3)),
        id=record_id,
        parent_id=parent_id,
        expression_date=version,
    )


@st.composite
def _scenario(draw: st.DrawFn) -> tuple[list[ProvisionRecord], list[dict[str, object]]]:
    keys = draw(
        st.lists(
            st.tuples(st.sampled_from(_PATHS), st.sampled_from(_VERSIONS)),
            max_size=7,
            unique=True,
        )
    )
    if draw(st.integers(min_value=0, max_value=3)) != 0:
        # Usually every parent is loaded too, so the load can succeed.
        for path, version in list(keys):
            while (path := _parent_of(path) or "") and (path, version) not in keys:
                keys.append((path, version))
    records = [draw(_record(path, version)) for path, version in keys]
    if records and draw(st.sampled_from([False] * 15 + [True])):
        records.append(records[0])  # a repeated immutable key
    staged: list[dict[str, object]] = []
    for record in records:
        state = draw(
            st.sampled_from(
                ["absent", "absent", "identical", "identical", "legacy-id", "stale-parent", "content"]
            )
        )
        if state == "absent":
            continue
        row = provision_to_supabase_row(record, versioned_ids=True)
        if state == "legacy-id":
            row["id"] = deterministic_provision_id(record.citation_path)
        elif state == "stale-parent" and record.parent_citation_path:
            row["parent_id"] = deterministic_provision_id(record.parent_citation_path)
        elif state == "content":
            row["body"] = "drifted text"
        staged.append(row)
    for _ in range(draw(st.integers(min_value=0, max_value=2))):
        # Rows the load does not describe, in loaded or other scopes; their
        # parents may be rows the load replaces (a cascade outside the load).
        path = draw(st.sampled_from(_PATHS))
        version = draw(st.sampled_from([*_VERSIONS, "2026-07-01"]))
        extra = provision_to_supabase_row(
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path=f"{path}/extra",
                version=version,
                body="extra",
            ),
            versioned_ids=True,
        )
        if staged and draw(st.booleans()):
            extra["parent_id"] = draw(st.sampled_from(staged))["id"]
        staged.append(extra)
    return records, staged


def _run(
    loader: Callable[..., object],
    records: list[ProvisionRecord],
    staged: list[dict[str, object]],
    *,
    chunk_size: int,
    dry_run: bool,
) -> tuple[object, dict, list]:
    fake = _RecordingFake(copy.deepcopy(staged))
    with mock.patch.object(supabase.urllib.request, "urlopen", fake.urlopen):
        try:
            outcome: object = (
                "ok",
                loader(
                    list(records),
                    service_key="service",
                    supabase_url="https://example.supabase.co",
                    chunk_size=chunk_size,
                    dry_run=dry_run,
                ).to_mapping(),  # type: ignore[attr-defined]
            )
        except ProvisionStagingConflictError as exc:
            outcome = ("conflict", str(exc), exc.conflicts)
        except Exception as exc:
            outcome = ("raised", type(exc), str(exc))
    return outcome, fake.rows, fake.requests


@settings(_SETTINGS, max_examples=500)
@given(
    scenario=_scenario(),
    chunk_size=st.integers(min_value=1, max_value=3),
    dry_run=st.integers(min_value=0, max_value=9).map(lambda roll: roll == 0),
)
def test_spooled_staging_matches_in_memory_staging(
    scenario: tuple[list[ProvisionRecord], list[dict[str, object]]],
    chunk_size: int,
    dry_run: bool,
) -> None:
    records, staged = scenario
    expected = _run(
        _reference_load_provisions_to_supabase,
        records,
        staged,
        chunk_size=chunk_size,
        dry_run=dry_run,
    )
    actual = _run(
        load_provisions_to_supabase, records, staged, chunk_size=chunk_size, dry_run=dry_run
    )
    outcome, _rows, requests = actual
    if outcome[0] == "conflict":  # type: ignore[index]
        for conflict in outcome[2]:  # type: ignore[index]
            event(f"conflict {conflict['kind']}")
        # Conflicts are raised before any write.
        assert [request for request in requests if request[0] != "GET"] == []
    elif outcome[0] == "ok":  # type: ignore[index]
        report = outcome[1]  # type: ignore[index]
        event("ok" if report["dry_run"] else "ok staged")
        if report["rows_replaced"]:
            event("ok with replaced or converged rows")
        if report["rows_already_staged"]:
            event("ok with verified no-op rows")
    else:
        event(f"raised {str(outcome[2])[:50]}")  # type: ignore[index]
    assert actual == expected


@_SETTINGS
@given(data=st.data())
def test_verified_partial_staging_converges_by_inserting_the_rest(data: st.DataObject) -> None:
    keys = set(
        data.draw(
            st.lists(
                st.tuples(st.sampled_from(_PATHS), st.sampled_from(_VERSIONS)),
                min_size=1,
                max_size=8,
            )
        )
    )
    # Every parent is part of the load, as in a complete artifact.
    for path, version in list(keys):
        while (path := _parent_of(path) or "") and (path, version) not in keys:
            keys.add((path, version))
    records = [data.draw(_record(path, version, borrow=False)) for path, version in sorted(keys)]
    projected = [provision_to_supabase_row(record, versioned_ids=True) for record in records]
    already = data.draw(st.lists(st.sampled_from(range(len(projected))), unique=True))
    fake = _RecordingFake([copy.deepcopy(projected[index]) for index in already])

    with mock.patch.object(supabase.urllib.request, "urlopen", fake.urlopen):
        report = load_provisions_to_supabase(
            records,
            service_key="service",
            supabase_url="https://example.supabase.co",
            chunk_size=data.draw(st.integers(min_value=1, max_value=4)),
        )

    assert report.rows_loaded == len(records)
    assert report.rows_already_staged == len(already)
    assert report.rows_inserted == len(records) - len(already)
    assert report.rows_replaced == 0
    assert {request[0] for request in fake.requests} <= {"GET", "POST"}
    inserted = [row for method, _url, body in fake.requests if method == "POST" for row in body]
    assert sorted(row["id"] for row in inserted) == sorted(
        row["id"] for index, row in enumerate(projected) if index not in already
    )
    assert fake.rows == {str(row["id"]): row for row in projected}


def test_staged_rows_are_compared_a_page_at_a_time(monkeypatch) -> None:
    """Planning consumes the staged-row stream lazily; no whole-scope fetch."""
    records = [
        ProvisionRecord(
            jurisdiction="us",
            document_class="regulation",
            citation_path=f"us/regulation/7/{index}",
            version="2026-05-13",
            body=f"body {index}",
        )
        for index in range(5)
    ]
    fake = _RecordingFake([provision_to_supabase_row(record) for record in records])
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)
    monkeypatch.setattr(
        supabase,
        "fetch_staged_scope_rows",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("whole-scope fetch")),
    )
    real_iter = supabase.iter_staged_scope_rows
    monkeypatch.setattr(
        supabase,
        "iter_staged_scope_rows",
        lambda **kwargs: real_iter(**{**kwargs, "page_size": 2}),
    )

    report = load_provisions_to_supabase(
        records, service_key="service", supabase_url="https://example.supabase.co"
    )

    assert report.rows_already_staged == 5
    pages = [url for method, url, _ in fake.requests if method == "GET" and "doc_type" in url]
    assert len(pages) == 3
