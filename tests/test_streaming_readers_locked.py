"""Streaming readers on locked corpus files (docs/corpus-storage.md).

``iter_provisions`` and ``load_source_inventory_references`` must treat a file
that a corpus lock names but this checkout lacks exactly as the whole-file
readers do: fetch it when fetching is on, refuse it when fetching is off, and
never read it as an empty scope.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from axiom_corpus.corpus import content_store
from axiom_corpus.corpus import resolver as resolver_module
from axiom_corpus.corpus.content_store import ContentCache, content_key
from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock
from axiom_corpus.corpus.io import (
    iter_provisions,
    load_provisions,
    load_source_inventory,
    load_source_inventory_references,
)
from axiom_corpus.corpus.resolver import CorpusNotMaterializedError, CorpusResolver
from tests.test_corpus_storage_review import FILES as _BASE_FILES
from tests.test_corpus_storage_review import SCOPE, _init_repo, _remote, _sha

PROVISIONS = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
INVENTORY = "data/corpus/inventory/nz/statute/2026-07-10.json"
FILES = {
    **_BASE_FILES,
    PROVISIONS: (
        b'{"jurisdiction":"nz","document_class":"statute","citation_path":"nz/statute/a"}\n'
    ),
    INVENTORY: (
        b'{"items": [{"citation_path": "nz/statute/a", "source_path": "x", "sha256": "y"}]}\n'
    ),
}


@pytest.fixture(autouse=True)
def no_real_r2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(cls: type, **_kwargs: object) -> None:
        raise RuntimeError("R2 is disabled in tests")

    monkeypatch.setattr(content_store.R2ObjectStore, "from_environment", classmethod(refuse))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "default-cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})


def _locked_repo(tmp_path: Path) -> Path:
    repo = _init_repo(tmp_path / "repo")
    lock = CorpusLock.from_entries(
        SCOPE,
        [LockEntry(path=path, sha256=_sha(data), size=len(data)) for path, data in FILES.items()],
    )
    write_lock(repo, lock)
    return repo


def _use_fake_remote(repo: Path, tmp_path: Path) -> None:
    remote = _remote({content_key(_sha(data)): data for data in FILES.values()})
    resolver_module._RESOLVERS[repo.resolve()] = CorpusResolver(
        repo, cache=ContentCache(tmp_path / "cache"), sources=[remote]
    )


def _outcome(read: Callable[[], Any]) -> tuple[Any, ...]:
    try:
        return ("ok", read())
    except Exception as exc:  # noqa: BLE001 - the exception itself is compared
        return ("error", type(exc), str(exc))


def test_locked_absent_file_is_refused_when_fetching_is_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _locked_repo(tmp_path)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")

    records = iter_provisions(repo / PROVISIONS)
    with pytest.raises(CorpusNotMaterializedError, match="fetching is off"):
        next(records)

    streamed = _outcome(lambda: load_source_inventory_references(repo / INVENTORY))
    whole = _outcome(lambda: load_source_inventory(repo / INVENTORY))
    assert streamed[:2] == ("error", CorpusNotMaterializedError)
    assert streamed == whole


@pytest.mark.parametrize("no_fetch", ["1", ""])
def test_unlocked_absent_file_reads_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_fetch: str
) -> None:
    repo = _locked_repo(tmp_path)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", no_fetch)
    provisions = repo / "data/corpus/provisions/nz/statute/unlocked.jsonl"
    inventory = repo / "data/corpus/inventory/nz/statute/unlocked.json"

    assert tuple(iter_provisions(provisions)) == load_provisions(provisions) == ()
    streamed = _outcome(lambda: load_source_inventory_references(inventory))
    assert streamed[:2] == ("error", FileNotFoundError)
    assert streamed == _outcome(lambda: load_source_inventory(inventory))


def test_paths_outside_a_checkout_read_as_before(tmp_path: Path) -> None:
    assert tuple(iter_provisions(tmp_path / "nowhere" / "x.jsonl")) == ()
    inventory = tmp_path / "nowhere" / "x.json"
    streamed = _outcome(lambda: load_source_inventory_references(inventory))
    assert streamed[:2] == ("error", FileNotFoundError)
    assert streamed == _outcome(lambda: load_source_inventory(inventory))


def test_locked_absent_files_are_fetched_before_streaming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _locked_repo(tmp_path)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH", raising=False)
    _use_fake_remote(repo, tmp_path)

    assert not (repo / PROVISIONS).exists()
    assert [record.citation_path for record in iter_provisions(repo / PROVISIONS)] == [
        "nz/statute/a"
    ]
    assert (repo / PROVISIONS).read_bytes() == FILES[PROVISIONS]

    assert not (repo / INVENTORY).exists()
    references = load_source_inventory_references(repo / INVENTORY)
    assert [reference.citation_path for reference in references] == ["nz/statute/a"]
    assert (repo / INVENTORY).read_bytes() == FILES[INVENTORY]


def test_relative_paths_are_fetched_from_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _locked_repo(tmp_path)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH", raising=False)
    _use_fake_remote(repo, tmp_path)
    monkeypatch.chdir(repo)

    assert [record.citation_path for record in iter_provisions(PROVISIONS)] == ["nz/statute/a"]
    assert [
        reference.citation_path for reference in load_source_inventory_references(INVENTORY)
    ] == ["nz/statute/a"]


def test_present_files_are_read_without_fetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _locked_repo(tmp_path)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    for relative, data in FILES.items():
        (repo / relative).parent.mkdir(parents=True, exist_ok=True)
        (repo / relative).write_bytes(data)

    assert tuple(iter_provisions(repo / PROVISIONS)) == load_provisions(repo / PROVISIONS)
    assert [
        reference.citation_path for reference in load_source_inventory_references(repo / INVENTORY)
    ] == [item.citation_path for item in load_source_inventory(repo / INVENTORY)]
