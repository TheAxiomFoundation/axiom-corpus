"""Fetch reports conserve entries and describe the files the whole call leaves.

For every selected entry the final report names exactly one outcome. Source
directories are complete or retain none of this call's placements; success
requires every selected file to be present or deliberately left modified.
Attribution and byte counts describe final placements, never discarded attempts.
An ENOSPC refusal of the shared retry stops after the first pass.
"""

from __future__ import annotations

import errno
import hashlib
import tempfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import content_store
from axiom_corpus.corpus.content_store import FetchReport, LockEntry
from axiom_corpus.corpus.corpus_locks import scope_for_path


@dataclass(frozen=True)
class _File:
    path: str
    body: bytes
    prior: str = "absent"
    failures: tuple[bool, ...] = ()

    def entry(self) -> LockEntry:
        return LockEntry(
            path=self.path, sha256=hashlib.sha256(self.body).hexdigest(), size=len(self.body)
        )


class _ScheduledSource:
    """Each file has its own failure schedule, including failures after a success."""

    name = "scheduled"

    def __init__(self, files: tuple[_File, ...]) -> None:
        self.files = {file.path: file for file in files}
        self.asks: Counter[str] = Counter()

    def open(self, entry: LockEntry) -> Iterator[bytes] | None:
        file = self.files[entry.path]
        attempt = self.asks[entry.path]
        self.asks[entry.path] += 1
        if attempt < len(file.failures) and file.failures[attempt]:
            return None
        return iter([file.body])


@st.composite
def _fetch_cases(draw: st.DrawFn) -> tuple[_File, ...]:
    files = []
    for scope in range(draw(st.integers(min_value=1, max_value=3))):
        scope_root = f"nz-{scope}/statute/2026"
        paths = [
            f"data/corpus/sources/{scope_root}/file-{index}.txt"
            for index in range(draw(st.integers(min_value=2, max_value=4)))
        ]
        for artifact, suffix in (("inventory", ".json"), ("provisions", ".jsonl")):
            if draw(st.booleans()):
                paths.append(f"data/corpus/{artifact}/{scope_root}{suffix}")
        for path in paths:
            files.append(
                _File(
                    path=path,
                    body=path.encode() + draw(st.binary(max_size=16)),
                    prior=draw(st.sampled_from(("absent", "present", "modified"))),
                    failures=tuple(draw(st.lists(st.booleans(), max_size=4))),
                )
            )
    return tuple(files)


def _prepare(repo: Path, files: tuple[_File, ...]) -> None:
    for file in files:
        if file.prior == "absent":
            continue
        target = repo / file.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.body if file.prior == "present" else file.body + b"edited")


def _assert_invariants(repo: Path, files: tuple[_File, ...], report: FetchReport) -> None:
    by_path = {file.path: file for file in files}
    outcomes = Counter(
        report.present
        + report.materialized
        + report.modified
        + list(report.failed)
        + report.rolled_back
    )
    assert outcomes == Counter(dict.fromkeys(by_path, 1)), "conservation"

    source_scopes = {
        scope_for_path(file.path) for file in files if file.path.startswith("data/corpus/sources/")
    }
    for scope in source_scopes:
        sources = [
            file
            for file in files
            if file.path.startswith("data/corpus/sources/") and scope_for_path(file.path) == scope
        ]
        if not all((repo / file.path).is_file() for file in sources):
            assert all(
                not (repo / file.path).exists() for file in sources if file.prior == "absent"
            ), "an incomplete scope retains none of this call's placements"

    if report.ok:
        assert all(
            file.path in report.modified
            or (
                (repo / file.path).is_file()
                and hashlib.sha256((repo / file.path).read_bytes()).hexdigest()
                == file.entry().sha256
            )
            for file in files
        ), "success means complete"
    assert report.bytes_materialized == sum(
        len(by_path[path].body) for path in report.materialized
    ), "byte accounting"
    assert sum(report.sources.values()) == len(report.materialized), "source accounting"
    assert sum(report.methods.values()) == len(report.materialized), "method accounting"
    assert all(count > 0 for count in report.sources.values())
    assert all(count > 0 for count in report.methods.values())
    for path in report.present + report.materialized:
        assert (repo / path).read_bytes() == by_path[path].body
    for path in report.failed.keys() | set(report.rolled_back):
        assert not (repo / path).exists()
    for file in files:
        if file.prior == "modified":
            assert (repo / file.path).read_bytes() == file.body + b"edited"


@pytest.mark.timeout(180)
@settings(max_examples=80, deadline=None)
@given(files=_fetch_cases())
@example(
    files=(
        _File("data/corpus/sources/nz/statute/2026/a.txt", b"a"),
        _File("data/corpus/sources/nz/statute/2026/b.txt", b"bb", failures=(True,)),
        _File("data/corpus/sources/nz/statute/2026/c.txt", b"ccc"),
    )
)
@example(
    files=(
        _File("data/corpus/sources/nz/statute/2026/a.txt", b"a", failures=(False, True)),
        _File("data/corpus/sources/nz/statute/2026/b.txt", b"bb", failures=(True,)),
        _File("data/corpus/sources/nz/statute/2026/c.txt", b"ccc"),
    )
)
@example(
    files=(
        _File("data/corpus/sources/nz/statute/2026/a.txt", b"a"),
        _File("data/corpus/sources/nz/statute/2026/b.txt", b"bb", failures=(True,) * 4),
    )
)
@example(
    files=(
        _File(
            "data/corpus/sources/nz/statute/2026/a.txt", b"a", failures=(False, True, True, True)
        ),
        _File("data/corpus/sources/nz/statute/2026/b.txt", b"bb", failures=(True,)),
    )
)
def test_fetch_conserves_entries_scopes_success_and_accounting(files: tuple[_File, ...]) -> None:
    with tempfile.TemporaryDirectory(prefix="axiom-fetch-property-") as raw:
        repo = Path(raw)
        _prepare(repo, files)
        report = content_store.materialize_resilient(
            repo,
            [file.entry() for file in files],
            None,
            [_ScheduledSource(files)],
            workers=1,
            verify=True,
            delays=(0, 0, 0),
        )

        _assert_invariants(repo, files, report)


@settings(max_examples=20, deadline=None)
@given(
    cases=st.lists(
        st.tuples(
            st.binary(min_size=1, max_size=32),
            st.sampled_from(("present", "modified", "absent")),
        ),
        min_size=1,
        max_size=4,
    ),
    failing_body=st.binary(min_size=1, max_size=32),
)
@example(cases=[(b"a", "present"), (b"bb", "modified"), (b"ccc", "absent")], failing_body=b"d")
def test_recreated_sources_conserve_outcomes_and_retained_accounting(
    cases: list[tuple[bytes, str]], failing_body: bytes
) -> None:
    files = tuple(
        _File(f"data/corpus/sources/nz/statute/2026/{index}.txt", body)
        for index, (body, _outcome) in enumerate(cases)
    ) + (_File("data/corpus/sources/nz/statute/2026/failing.txt", failing_body, failures=(True,)),)
    replacements = {
        file.path: bytes([body[0] ^ 1]) + body[1:] if outcome == "modified" else body
        for file, (body, outcome) in zip(files[:-1], cases, strict=True)
        if outcome != "absent"
    }
    expected_present = {
        file.path for file, (_, mode) in zip(files[:-1], cases, strict=True) if mode == "present"
    }
    expected_modified = {
        file.path for file, (_, mode) in zip(files[:-1], cases, strict=True) if mode == "modified"
    }
    expected_materialized = {file.path for file in files} - replacements.keys()
    source = _ScheduledSource(files)

    with tempfile.TemporaryDirectory(prefix="axiom-fetch-recreated-property-") as raw:
        repo = Path(raw)
        passes = 0

        def fetch(*args: object, **kwargs: object) -> FetchReport:
            nonlocal passes
            report = content_store.materialize(*args, **kwargs)
            passes += 1
            if passes == 1:
                assert set(report.rolled_back) == {file.path for file in files[:-1]}
                assert report.materialized == []
                assert report.bytes_materialized == 0
                assert report.sources == report.methods == {}
                for path, body in replacements.items():
                    assert not (repo / path).exists()
                    (repo / path).write_bytes(body)
            return report

        report = content_store.materialize_resilient(
            repo,
            [file.entry() for file in files],
            None,
            [source],
            workers=1,
            verify=True,
            delays=(0,),
            fetch=fetch,
        )

        _assert_invariants(repo, files, report)
        assert passes == 2
        assert report.ok
        assert set(report.present) == expected_present
        assert set(report.modified) == expected_modified
        assert set(report.materialized) == expected_materialized
        assert all((repo / path).read_bytes() == body for path, body in replacements.items())
        assert report.sources == {"scheduled": len(expected_materialized)}
        assert report.methods == {"stream": len(expected_materialized)}
        assert source.asks == Counter(
            {file.path: 1 if file.path in replacements else 2 for file in files}
        )


class _FullDiskSource:
    """A streamed body raises a real ENOSPC once its byte capacity is exhausted."""

    name = "capacity-limited"

    def __init__(self, files: tuple[_File, ...], capacity: int) -> None:
        self.bodies = {file.path: file.body for file in files}
        self.capacity = capacity
        self.used = 0
        self.asks: Counter[str] = Counter()

    def open(self, entry: LockEntry) -> Iterator[bytes]:
        self.asks[entry.path] += 1
        return self._chunks(self.bodies[entry.path])

    def _chunks(self, body: bytes) -> Iterator[bytes]:
        for byte in body:
            if self.used == self.capacity:
                raise OSError(errno.ENOSPC, "No space left on device")
            self.used += 1
            yield bytes([byte])


@settings(max_examples=40, deadline=None)
@given(
    sizes=st.lists(st.integers(min_value=1, max_value=32), min_size=2, max_size=8),
    capacity_fraction=st.integers(min_value=0, max_value=99),
)
def test_first_pass_enospc_asks_for_no_more_objects(
    sizes: list[int], capacity_fraction: int
) -> None:
    files = tuple(
        _File(f"data/corpus/sources/nz-{index % 2}/statute/2026/{index}.txt", b"x" * size)
        for index, size in enumerate(sizes)
    )
    capacity = sum(sizes) * capacity_fraction // 100
    source = _FullDiskSource(files, capacity)
    with tempfile.TemporaryDirectory(prefix="axiom-fetch-enospc-property-") as raw:
        repo = Path(raw)
        report = content_store.materialize_resilient(
            repo,
            [file.entry() for file in files],
            None,
            [source],
            workers=1,
            verify=True,
            delays=(0, 0, 0),
            retriable=lambda failed: all("[Errno 28]" not in reason for reason in failed.values()),
        )

        assert any("[Errno 28]" in reason for reason in report.failed.values())
        assert not report.ok
        assert source.asks == Counter({file.path: 1 for file in files}), "no second pass"
        _assert_invariants(repo, files, report)
