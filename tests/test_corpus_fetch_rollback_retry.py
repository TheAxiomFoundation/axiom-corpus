"""A retry must restore a source directory or account for every absent file."""

from __future__ import annotations

import errno
import hashlib
import json
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from axiom_corpus.corpus import content_store, corpus_cli
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.content_store import ContentCache, FetchReport, LockEntry
from axiom_corpus.corpus.corpus_locks import CorpusLock, write_lock
from axiom_corpus.corpus.resolver import CorpusNotMaterializedError, CorpusResolver

SCOPE = ("zz", "statute", "2026-01-01")
SOURCE_DIR = "data/corpus/sources/zz/statute/2026-01-01"
BODIES = {f"{SOURCE_DIR}/{name}.html": name.encode() * 8 for name in ("a", "b", "c")}


class ScheduledSource:
    name = "fake"

    def __init__(self, failures: dict[str, set[int]]) -> None:
        self.failures = failures
        self.asks: list[str] = []
        self.counts: Counter[str] = Counter()

    def open(self, entry: LockEntry) -> Iterator[bytes] | None:
        self.asks.append(entry.path)
        self.counts[entry.path] += 1
        if self.counts[entry.path] in self.failures.get(entry.path, set()):
            return None
        return iter([BODIES[entry.path]])


class CapacitySource(ScheduledSource):
    """Disk usage is measured anew, so rollback really frees simulated space."""

    def __init__(self, repo: Path, capacity: int) -> None:
        super().__init__({})
        self.repo = repo
        self.capacity = capacity

    def open(self, entry: LockEntry) -> Iterator[bytes]:
        self.asks.append(entry.path)
        used = sum(
            (self.repo / path).stat().st_size for path in BODIES if (self.repo / path).is_file()
        )
        if used + entry.size > self.capacity:
            raise OSError(errno.ENOSPC, "No space left on device")
        return iter([BODIES[entry.path]])


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def _entries() -> list[LockEntry]:
    return [
        LockEntry(path=path, sha256=hashlib.sha256(body).hexdigest(), size=len(body))
        for path, body in BODIES.items()
    ]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "data/corpus").mkdir(parents=True)
    write_lock(repo, CorpusLock.from_entries(SCOPE, _entries()))
    return repo


def _cli(repo: Path, source: ScheduledSource, monkeypatch: pytest.MonkeyPatch, *extra: str) -> int:
    # Exercise the registered console entry point, selection, real retry and
    # placement; replace only the external object source and random ordering.
    monkeypatch.setattr(corpus_cli, "_sources", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(corpus_cli, "_spread", list)
    return main(
        [
            "corpus",
            "fetch",
            "--repo",
            str(repo),
            "--all",
            "--no-cache",
            "--no-r2",
            "--verify",
            "--workers",
            "1",
            *extra,
        ]
    )


def test_retry_restores_every_rolled_back_source(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    entries = _entries()
    source = ScheduledSource({entries[-1].path: {1}})

    report = content_store.materialize_resilient(
        repo,
        entries,
        None,
        [source],
        workers=1,
        delays=(0,),
        verify=True,
    )

    assert {p: (repo / p).read_bytes() for p in BODIES if (repo / p).is_file()} == BODIES
    assert report.failed == {}
    assert report.rolled_back == []
    assert report.ok
    assert set(report.materialized) == set(BODIES)
    assert source.counts == Counter(dict.fromkeys(BODIES, 2))
    assert report.bytes_materialized == sum(map(len, BODIES.values()))
    assert report.sources == {"fake": len(BODIES)}
    assert report.methods == {"stream": len(BODIES)}


@pytest.mark.parametrize("recreated_outcome", ["present", "modified"])
def test_retry_accepts_a_source_recreated_after_rollback(
    tmp_path: Path, recreated_outcome: str
) -> None:
    repo = _repo(tmp_path)
    entries = _entries()
    recreated, *retained = list(BODIES)
    body = BODIES[recreated]
    replacement = bytes([body[0] ^ 1]) + body[1:] if recreated_outcome == "modified" else body
    source = ScheduledSource({entries[-1].path: {1}})
    passes = 0

    def fetch(*args: object, **kwargs: object) -> FetchReport:
        nonlocal passes
        report = content_store.materialize(*args, **kwargs)
        passes += 1
        if passes == 1:
            assert set(report.rolled_back) == {entry.path for entry in entries[:-1]}
            assert report.materialized == []
            assert report.bytes_materialized == 0
            assert report.sources == report.methods == {}
            assert not (repo / recreated).exists()
            (repo / recreated).write_bytes(replacement)
        return report

    report = content_store.materialize_resilient(
        repo, entries, None, [source], workers=1, verify=True, delays=(0,), fetch=fetch
    )

    outcomes = Counter(
        report.present
        + report.materialized
        + report.modified
        + list(report.failed)
        + report.rolled_back
    )
    assert outcomes == Counter(dict.fromkeys(BODIES, 1)), "each path has exactly one final outcome"
    assert passes == 2
    assert report.present == ([recreated] if recreated_outcome == "present" else [])
    assert report.modified == ([recreated] if recreated_outcome == "modified" else [])
    assert report.materialized == retained
    assert report.failed == {}
    assert report.rolled_back == []
    assert report.ok
    assert (repo / recreated).read_bytes() == replacement
    assert all((repo / path).read_bytes() == BODIES[path] for path in retained)
    assert report.bytes_materialized == sum(len(BODIES[path]) for path in retained)
    assert report.sources == {"fake": len(retained)}
    assert report.methods == {"stream": len(retained)}
    assert source.counts == Counter({recreated: 1, **dict.fromkeys(retained, 2)})


def test_permanent_failure_leaves_no_sources_and_no_duplicate_rollback(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    entries = _entries()
    source = ScheduledSource({entries[-1].path: {1, 2, 3, 4}})

    report = content_store.materialize_resilient(
        repo,
        entries,
        None,
        [source],
        workers=1,
        delays=(0, 0, 0),
    )

    assert not any((repo / p).exists() for p in BODIES)
    assert set(report.failed) == {entries[-1].path}
    assert sorted(report.rolled_back) == sorted(BODIES)[:-1]
    assert not report.ok
    assert report.materialized == []
    assert report.bytes_materialized == 0
    assert sum(report.sources.values()) == sum(report.methods.values()) == 0
    assert source.counts == Counter(dict.fromkeys(BODIES, 4))


def test_a_report_holding_only_rolled_back_files_still_retries(tmp_path: Path) -> None:
    entries = _entries()
    missing = entries[0].path
    asked: list[list[str]] = []

    def fetch(
        _repo: Path, selected: list[LockEntry], *_args: object, **_kwargs: object
    ) -> FetchReport:
        asked.append([entry.path for entry in selected])
        if len(asked) == 1:
            return FetchReport(rolled_back=[missing])
        return FetchReport(materialized=[missing])

    report = content_store.materialize_resilient(
        tmp_path, entries, None, [], delays=(0,), fetch=fetch
    )

    assert asked == [[entry.path for entry in entries], [missing]]
    assert report.ok
    assert report.rolled_back == []


@pytest.mark.parametrize("when", ["before_rollback_reads_it", "while_rollback_hashes_it"])
@pytest.mark.parametrize("retries", [True, False])
def test_a_placed_file_someone_removes_stays_on_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, when: str, retries: bool
) -> None:
    repo = _repo(tmp_path)
    entries = _entries()
    removed, failing = entries[0].path, entries[-1].path

    class RemovesASibling(ScheduledSource):
        def open(self, entry: LockEntry) -> Iterator[bytes] | None:
            first_ask = self.counts[failing] == 0
            if when == "before_rollback_reads_it" and entry.path == failing and first_ask:
                (repo / removed).unlink()
            return super().open(entry)

    real_hash_path = content_store.hash_path

    def hash_path_removing_it(path: Path) -> tuple[str, int]:
        # Rollback hashes the file only on the pass where a sibling fails.
        if when == "while_rollback_hashes_it" and path == repo / removed:
            path.unlink(missing_ok=True)
        return real_hash_path(path)

    monkeypatch.setattr(content_store, "hash_path", hash_path_removing_it)

    report = content_store.materialize_resilient(
        repo,
        entries,
        None,
        [RemovesASibling({failing: {1}})],
        workers=1,
        delays=(0,) if retries else (),
    )

    if retries:
        assert report.ok
        assert report.rolled_back == []
        assert (repo / removed).read_bytes() == BODIES[removed]
    else:
        assert not report.ok
        assert removed in report.rolled_back
        assert removed not in report.materialized
        assert not (repo / removed).exists()


@pytest.mark.parametrize("succeeds", [True, False])
@pytest.mark.parametrize("as_json", [True, False])
def test_cli_reports_complete_success_or_names_missing_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    succeeds: bool,
    as_json: bool,
) -> None:
    repo = _repo(tmp_path)
    failed = _entries()[-1].path
    source = ScheduledSource({failed: {1} if succeeds else {1, 2, 3, 4}})

    status = _cli(repo, source, monkeypatch, *(["--json"] if as_json else []))
    output = capsys.readouterr().out

    assert status == (0 if succeeds else 1)
    if succeeds:
        assert {p: (repo / p).read_bytes() for p in BODIES if (repo / p).is_file()} == BODIES
    else:
        assert not any((repo / p).exists() for p in BODIES)
        assert all(path in output for path in BODIES)
    if as_json:
        report = json.loads(output)
        assert report["ok"] is succeeds
        assert report["materialized"] == (3 if succeeds else 0)
        assert report["rolled_back"] == ([] if succeeds else sorted(BODIES)[:-1])
    else:
        assert ("0 failed, 0 rolled back." if succeeds else "1 failed, 2 rolled back.") in output


def test_cli_refuses_a_report_with_only_rolled_back_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Defense at the exit boundary even when no failed file remains."""
    repo = _repo(tmp_path)
    missing = _entries()[0].path
    report = FetchReport(rolled_back=[missing])
    monkeypatch.setattr(corpus_cli, "materialize_resilient", lambda *_args, **_kwargs: report)

    status = _cli(repo, ScheduledSource({}), monkeypatch)

    assert status == 1
    assert not report.ok
    output = capsys.readouterr().out
    assert "0 failed, 1 rolled back." in output
    assert missing in output


def test_cli_full_disk_stops_before_redownloading_rolled_back_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _repo(tmp_path)
    source = CapacitySource(repo, capacity=16)

    status = _cli(repo, source, monkeypatch)

    assert status == 1
    assert source.asks == list(BODIES), "ENOSPC must not start another pass after rollback"
    assert not any((repo / p).exists() for p in BODIES)
    output = capsys.readouterr().out
    assert "[Errno 28]" in output
    assert "1 failed, 2 rolled back." in output
    assert all(path in output for path in BODIES)


@pytest.mark.parametrize("cached", [False, True])
def test_resolver_full_disk_stops_before_a_second_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cached: bool,
) -> None:
    repo = _repo(tmp_path)

    class FullDiskSource(ScheduledSource):
        def open(self, entry: LockEntry) -> Iterator[bytes]:
            self.asks.append(entry.path)
            raise OSError(errno.ENOSPC, "No space left on device")

    source = FullDiskSource({})
    resolver = CorpusResolver(
        repo,
        cache=ContentCache(tmp_path / "cache"),
        sources=[source],
        workers=1,
    )
    if not cached:
        monkeypatch.setattr(resolver, "cache", None)

    with pytest.raises(CorpusNotMaterializedError, match=r"\[Errno 28\]"):
        resolver.ensure(_entries())

    assert source.asks == list(BODIES), "the resolver must combine ENOSPC with its symlink refusal"
    assert not any((repo / p).exists() for p in BODIES)
