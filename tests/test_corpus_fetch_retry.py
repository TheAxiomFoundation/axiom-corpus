"""A bulk corpus fetch survives a transient object-store failure.

A release-selector fetch asks the store for tens of thousands of objects at high
concurrency, and a small random subset can fail on throttling or a dropped
connection. `materialize` reports a per-entry failure rather than raising, so
before `CorpusResolver._retry_transient` the whole call died on the first flake:
one CI run could not fetch 22 objects and its own re-run could not fetch 6 wholly
different ones, with the corpus itself intact.

These tests pin both halves of the contract: a failure that clears on a second ask
is retried, and one that never clears still fails with the same error.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from axiom_corpus.corpus import resolver as resolver_module
from axiom_corpus.corpus.content_store import ContentCache, LockEntry
from axiom_corpus.corpus.resolver import CorpusNotMaterializedError, CorpusResolver

PATH = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
BODY = b'{"citation_path": "nz/statute/x"}\n'


class FlakySource:
    """Serves `body` only from the `succeed_from`-th ask onward, per entry."""

    name = "flaky"

    def __init__(self, body: bytes, *, succeed_from: int) -> None:
        self.body = body
        self.succeed_from = succeed_from
        self.asks = 0

    def open(self, entry: LockEntry) -> Iterator[bytes] | None:
        self.asks += 1
        if self.asks < self.succeed_from:
            return None  # absent, which is how a dropped fetch presents
        return iter([self.body])


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """The delays are real seconds in production; tests must not pay them.

    This patches the stdlib function the resolver calls, so the fixture holds
    whether or not the resolver imports `time` itself. Patching an attribute of
    the resolver module would make these tests *error* on a build without the
    retry, instead of failing on the behaviour they are about.
    """
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def _entry() -> LockEntry:
    import hashlib

    return LockEntry(path=PATH, sha256=hashlib.sha256(BODY).hexdigest(), size=len(BODY))


def _resolver(tmp_path: Path, source: FlakySource) -> CorpusResolver:
    repo = tmp_path / "repo"
    (repo / "data" / "corpus").mkdir(parents=True)
    return CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[source])


def test_a_fetch_that_fails_once_then_succeeds_is_retried(tmp_path: Path) -> None:
    source = FlakySource(BODY, succeed_from=2)
    resolver = _resolver(tmp_path, source)

    report = resolver.ensure([_entry()])

    assert report.failed == {}
    assert report.materialized == [PATH]
    assert (resolver.repo / PATH).read_bytes() == BODY
    assert source.asks == 2, "the first ask failed and exactly one retry was needed"


def test_a_fetch_that_never_succeeds_still_raises(tmp_path: Path) -> None:
    source = FlakySource(BODY, succeed_from=99)
    resolver = _resolver(tmp_path, source)

    with pytest.raises(CorpusNotMaterializedError, match="could not be fetched"):
        resolver.ensure([_entry()])

    expected = 1 + len(getattr(resolver_module, "FETCH_RETRY_DELAYS", ()))
    assert source.asks == expected, "every delay is tried once, then the call fails"
