"""Corpus bytes outside git: lock files, content cache, fetch, push and migrate.

Invariants (docs/corpus-storage.md) are exercised as properties with
Hypothesis alongside example tests:

1. lock round trip and canonical form;
2. scope partition (every entry lies in its lock's scope, once);
3. conservation at migration (locks == tracked blobs, byte for byte);
4. fetch fidelity (materialized bytes hash to the lock, or nothing changes);
5. cache integrity (objects hash to their names);
6. idempotence (a second fetch changes nothing);
7. no links (materialized files are independent regular files);
10. path naming (every spelling of a checkout names one entry, and one
    checkout names it; a symlinked corpus file, or a path below a directory
    link to a place no lock guards, is named, and refused, as itself).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import posixpath
import subprocess
import threading
import unicodedata
from io import BytesIO
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import corpus_cli
from axiom_corpus.corpus import resolver as resolver_module
from axiom_corpus.corpus.cli import main as cli_main
from axiom_corpus.corpus.content_store import (
    ContentCache,
    ContentStoreError,
    GitBlobSource,
    R2ObjectStore,
    clone_file,
    content_key,
    ensure_cached,
    materialize,
    read_entry_bytes,
)
from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    LOCK_ROOT,
    CorpusLock,
    LockEntry,
    LockFormatError,
    LockSet,
    diff_lock_sets,
    fold_collisions,
    hash_tree_blobs,
    is_protected_corpus_path,
    list_tree_blobs,
    load_locks,
    load_locks_at_ref,
    lock_from_worktree,
    lock_path_for_scope,
    locks_from_hashed_blobs,
    parse_lock,
    parse_scope_selector,
    protected_tree_blobs,
    scope_for_lock_path,
    scope_for_path,
    serialize_lock,
    write_lock,
)
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.resolver import (
    CorpusNotMaterializedError,
    CorpusResolver,
    corpus_inputs_from_args,
    ensure_corpus_paths,
    fetch_locked_file,
    require_materialized,
    resolve_corpus_path,
)

PROPERTY_SETTINGS = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)


# --------------------------------------------------------------------------- helpers


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "src" / "axiom_corpus").mkdir(parents=True)
    (path / ".gitignore").write_text("data/\n")
    (path / "README.md").write_text("seed\n")
    _git(path, "add", ".gitignore", "README.md")
    _git(path, "commit", "-q", "-m", "seed")
    return path


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(repo: Path, rel: str, data: bytes) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


SCOPE = ("nz", "statute", "2026-07-10")
SCOPE_FILES = {
    "data/corpus/sources/nz/statute/2026-07-10/official/act.html": b"<html>Act 1</html>\n",
    "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml": b"<s>2</s>",
    "data/corpus/inventory/nz/statute/2026-07-10.json": b'{"items": []}\n',
    "data/corpus/provisions/nz/statute/2026-07-10.jsonl": b'{"citation_path":"nz/statute/a"}\n',
    "data/corpus/coverage/nz/statute/2026-07-10.json": b'{"complete": true}\n',
}


def _scope_lock(files: dict[str, bytes] = SCOPE_FILES, scope=SCOPE) -> CorpusLock:
    return CorpusLock.from_entries(
        scope,
        [LockEntry(path=p, sha256=_sha(d), size=len(d)) for p, d in files.items()],
    )


class FakeR2:
    """In-memory S3 subset with R2's conditional-write semantics."""

    def __init__(self, objects: dict[str, bytes] | None = None):
        self.objects = dict(objects or {})
        self.puts: list[str] = []
        self.gets: list[str] = []
        self._lock = threading.Lock()

    def get_object(self, **kwargs):
        self.gets.append(kwargs["Key"])
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}

    def head_object(self, **kwargs):
        return {"ContentLength": len(self.objects[kwargs["Key"]])}

    def put_object(self, **kwargs):
        body = kwargs["Body"]
        payload = body.read() if hasattr(body, "read") else bytes(body)
        with self._lock:
            if kwargs.get("IfNoneMatch") == "*" and kwargs["Key"] in self.objects:
                raise ClientError(
                    {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                    "PutObject",
                )
            self.objects[kwargs["Key"]] = payload
            self.puts.append(kwargs["Key"])


def _remote(objects: dict[str, bytes] | None = None) -> tuple[R2ObjectStore, FakeR2]:
    fake = FakeR2(objects)
    return R2ObjectStore(bucket="axiom-corpus", client=fake), fake


# --------------------------------------------------------------------------- lock format

segment = st.from_regex(r"[a-z0-9][a-z0-9._-]{0,12}", fullmatch=True)
file_segment = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9 ._()-]{0,10}", fullmatch=True).filter(
    lambda s: s not in {".", ".."} and not s.endswith(" ")
)


@st.composite
def scope_lock(draw) -> tuple[CorpusLock, dict[str, bytes]]:
    scope = (draw(segment), draw(segment), draw(segment))
    j, dc, v = scope
    files: dict[str, bytes] = {}
    for kind in draw(st.sets(st.sampled_from(["inventory", "provisions", "coverage"]))):
        suffix = ".jsonl" if kind == "provisions" else ".json"
        files[f"data/corpus/{kind}/{j}/{dc}/{v}{suffix}"] = draw(st.binary(max_size=64))
    for rel in draw(st.lists(st.lists(file_segment, min_size=1, max_size=3), max_size=6)):
        files[f"data/corpus/sources/{j}/{dc}/{v}/" + "/".join(rel)] = draw(st.binary(max_size=64))
    # Keep only a tree that can exist on disk everywhere: no path that is also
    # a directory, and no two names a case-insensitive filesystem merges.
    while collisions := fold_collisions(sorted(files)):
        dropped = collisions[0][1].removesuffix("/…")
        for path in [p for p in files if p == dropped or p.startswith(f"{dropped}/")]:
            del files[path]
    if not files:
        files[f"data/corpus/provisions/{j}/{dc}/{v}.jsonl"] = b"{}\n"
    return _scope_lock(files, scope), files


@PROPERTY_SETTINGS
@given(scope_lock())
def test_lock_round_trip_is_canonical(drawn) -> None:
    lock, _files = drawn
    payload = serialize_lock(lock)
    assert parse_lock(payload) == lock
    assert serialize_lock(parse_lock(payload)) == payload
    assert payload.endswith(b"\n") and payload.isascii()


@PROPERTY_SETTINGS
@given(scope_lock())
def test_every_entry_lies_in_its_lock_scope(drawn) -> None:
    lock, _files = drawn
    assert {scope_for_path(entry.path) for entry in lock.files} == {lock.scope}
    assert scope_for_lock_path(lock_path_for_scope(lock.scope)) == lock.scope


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s.replace('"schema_version"', ' "schema_version"', 1),
        lambda s: s.replace("\n  ]\n}\n", "\n  ]\n}"),
        lambda s: s.replace('"size": ', '"size":  ', 1),
        lambda s: s.replace('"jurisdiction": "nz"', '"jurisdiction": "NZ"'),
        lambda s: s.replace("axiom-corpus/corpus-lock/v1", "axiom-corpus/corpus-lock/v2"),
    ],
)
def test_non_canonical_lock_bytes_are_rejected(mutate) -> None:
    payload = serialize_lock(_scope_lock()).decode()
    with pytest.raises(LockFormatError):
        parse_lock(mutate(payload).encode())


def test_lock_rejects_unsorted_duplicate_and_foreign_entries() -> None:
    entries = list(_scope_lock().files)
    with pytest.raises(LockFormatError, match="not sorted"):
        CorpusLock(*SCOPE, files=tuple(reversed(entries)))
    with pytest.raises(LockFormatError, match="twice"):
        CorpusLock(*SCOPE, files=tuple(sorted(entries + entries[:1])))
    foreign = LockEntry(
        path="data/corpus/provisions/nz/statute/other.jsonl", sha256="0" * 64, size=1
    )
    with pytest.raises(LockFormatError, match="outside the scope"):
        CorpusLock.from_entries(SCOPE, entries + [foreign])


@pytest.mark.parametrize(
    "path",
    [
        "data/corpus/../etc/passwd",
        "/data/corpus/sources/a/b/c/d",
        "data/corpus/sources/a/b/c/./d",
        "data/corpus/sources/a/b/c/d\\e",
        "data/corpus/anchors/a/b/c.jsonl",
        "README.md",
        "data/corpus/sources/a/b/c/d\x01",
    ],
)
def test_lock_entry_rejects_unsafe_or_unprotected_paths(path: str) -> None:
    with pytest.raises(LockFormatError):
        LockEntry(path=path, sha256="0" * 64, size=0)


def test_scope_mapping_matches_the_artifact_layout() -> None:
    assert scope_for_path("data/corpus/sources/us-ca/statute/v1/a/b.html") == ("us-ca", "statute", "v1")
    assert scope_for_path("data/corpus/provisions/us-ca/statute/v1.jsonl") == ("us-ca", "statute", "v1")
    assert scope_for_path("data/corpus/inventory/us-ca/statute/v1.json") == ("us-ca", "statute", "v1")
    assert scope_for_path("data/corpus/provisions/us-ca/statute/v1.json") is None
    assert scope_for_path("data/corpus/sources/us-ca/statute/v1") is None
    assert scope_for_path("data/corpus/snapshots/x.json") is None
    assert parse_scope_selector("us-ca/statute") == ("us-ca", "statute")
    with pytest.raises(ValueError):
        parse_scope_selector("us-ca/statute/v1/extra")


def test_lock_set_reports_a_path_claimed_by_two_locks(tmp_path: Path) -> None:
    repo = tmp_path
    write_lock(repo, _scope_lock())
    bad = LOCK_ROOT / "nz" / "statute" / "renamed.json"
    (repo / bad).write_bytes(serialize_lock(_scope_lock()))
    locks = load_locks(repo)
    assert any("holds the lock for" in error for error in locks.errors)


def test_diff_distinguishes_added_changed_and_removed() -> None:
    base = LockSet(locks={SCOPE: _scope_lock()})
    files = dict(SCOPE_FILES)
    files["data/corpus/coverage/nz/statute/2026-07-10.json"] = b'{"complete": false}\n'
    files.pop("data/corpus/sources/nz/statute/2026-07-10/official/act.html")
    files["data/corpus/sources/nz/statute/2026-07-10/official/new.html"] = b"new"
    head = LockSet(locks={SCOPE: _scope_lock(files)})
    diff = diff_lock_sets(base, head)
    assert [e.path for e in diff.added] == ["data/corpus/sources/nz/statute/2026-07-10/official/new.html"]
    assert [a.path for _b, a in diff.changed] == ["data/corpus/coverage/nz/statute/2026-07-10.json"]
    assert [e.path for e in diff.removed] == ["data/corpus/sources/nz/statute/2026-07-10/official/act.html"]


# --------------------------------------------------------------------------- cache and cloning


def test_cache_refuses_bytes_that_do_not_match_the_name(tmp_path: Path) -> None:
    cache = ContentCache(tmp_path / "cache")
    with pytest.raises(ContentStoreError):
        cache.add_stream([b"wrong"], sha256=_sha(b"right"), size=5)
    assert not cache.contains(_sha(b"right"))
    assert not list((tmp_path / "cache" / "tmp").iterdir())


@PROPERTY_SETTINGS
@given(st.lists(st.binary(max_size=4096), min_size=1, max_size=8))
def test_cache_objects_hash_to_their_names(tmp_path_factory, blobs) -> None:
    cache = ContentCache(tmp_path_factory.mktemp("cache"))
    for blob in blobs:
        path = cache.add_stream([blob[: len(blob) // 2], blob[len(blob) // 2 :]], sha256=_sha(blob), size=len(blob))
        assert path == cache.object_path(_sha(blob))
        assert path.read_bytes() == blob
        assert cache.verify_object(_sha(blob))
        assert not os.access(path, os.W_OK) or os.geteuid() == 0


def test_clone_is_an_independent_regular_file(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"original bytes")
    target = tmp_path / "target"
    method = clone_file(source, target)
    assert method in {"clonefile", "ficlone", "copy"}
    assert not target.is_symlink()
    assert target.stat().st_ino != source.stat().st_ino
    assert target.stat().st_nlink == 1
    target.write_bytes(b"edited")
    assert source.read_bytes() == b"original bytes"
    with pytest.raises(FileExistsError):
        clone_file(source, target)


# --------------------------------------------------------------------------- fetch


def _materialize_all(repo: Path, lock: CorpusLock, cache: ContentCache, sources, **kwargs):
    return materialize(repo, lock.files, cache, sources, workers=4, **kwargs)


@PROPERTY_SETTINGS
@given(scope_lock())
def test_fetch_reproduces_the_locked_tree_byte_for_byte(tmp_path_factory, drawn) -> None:
    lock, files = drawn
    repo = tmp_path_factory.mktemp("repo")
    remote, fake = _remote({content_key(_sha(d)): d for d in files.values()})
    cache = ContentCache(tmp_path_factory.mktemp("cache"))

    report = _materialize_all(repo, lock, cache, [remote])
    assert report.ok
    for rel, data in files.items():
        placed = repo / rel
        assert placed.read_bytes() == data
        assert placed.is_file() and not placed.is_symlink() and placed.stat().st_nlink == 1
    assert lock_from_worktree(repo, lock.scope) == lock

    gets_before = len(fake.gets)
    again = _materialize_all(repo, lock, cache, [remote], verify=True)
    assert again.ok and not again.materialized
    assert sorted(again.present) == sorted(files)
    assert len(fake.gets) == gets_before


def test_fetch_prefers_cache_then_git_then_r2_and_checks_every_source(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    data = b"tracked bytes\n"
    _write(repo, "data/corpus/provisions/nz/statute/v1.jsonl", data)
    _git(repo, "add", "-f", "data/corpus/provisions/nz/statute/v1.jsonl")
    _git(repo, "commit", "-q", "-m", "track")
    oid = _git(repo, "rev-parse", "HEAD:data/corpus/provisions/nz/statute/v1.jsonl")
    entry = LockEntry("data/corpus/provisions/nz/statute/v1.jsonl", _sha(data), len(data), git_blob=oid)
    cache = ContentCache(tmp_path / "cache")
    remote, fake = _remote({content_key(_sha(data)): b"corrupt remote bytes"})

    path, source = ensure_cached(entry, cache, [GitBlobSource(repo), remote])
    assert source == "git" and path.read_bytes() == data and not fake.gets
    assert ensure_cached(entry, cache, [remote])[1] == "cache"

    other = LockEntry("data/corpus/provisions/nz/statute/v2.jsonl", _sha(b"x"), 1)
    with pytest.raises(ContentStoreError, match="refusing bytes"):
        ensure_cached(other, cache, [R2ObjectStore(bucket="axiom-corpus", client=FakeR2({content_key(_sha(b"x")): b"y"}))])
    assert not cache.contains(_sha(b"x"))


def test_fetch_falls_back_to_a_verified_legacy_path_key(tmp_path: Path) -> None:
    data = b"legacy"
    entry = LockEntry("data/corpus/provisions/nz/statute/v1.jsonl", _sha(data), len(data))
    remote, fake = _remote({"provisions/nz/statute/v1.jsonl": data})
    path, source = ensure_cached(entry, ContentCache(tmp_path / "cache"), [remote])
    assert source == "r2" and path.read_bytes() == data
    assert fake.gets == [content_key(entry.sha256), "provisions/nz/statute/v1.jsonl"]


def test_fetch_never_overwrites_modified_files_without_force(tmp_path: Path) -> None:
    lock = _scope_lock()
    remote, _fake = _remote({content_key(_sha(d)): d for d in SCOPE_FILES.values()})
    cache = ContentCache(tmp_path / "cache")
    repo = tmp_path / "repo"
    edited = "data/corpus/coverage/nz/statute/2026-07-10.json"
    _write(repo, edited, b"local edit, different size")
    report = _materialize_all(repo, lock, cache, [remote])
    assert report.modified == [edited]
    assert (repo / edited).read_bytes() == b"local edit, different size"
    forced = _materialize_all(repo, lock, cache, [remote], force=True)
    assert forced.ok and (repo / edited).read_bytes() == SCOPE_FILES[edited]


def test_failed_fetch_leaves_the_destination_untouched(tmp_path: Path) -> None:
    lock = _scope_lock()
    remote, _fake = _remote({})  # R2 has nothing
    repo = tmp_path / "repo"
    report = _materialize_all(repo, lock, ContentCache(tmp_path / "cache"), [remote])
    assert not report.ok and len(report.failed) == len(SCOPE_FILES)
    assert not (repo / "data").exists() or not any(p.is_file() for p in (repo / "data").rglob("*"))


def test_fetch_refuses_to_write_through_a_symlink(tmp_path: Path) -> None:
    lock = _scope_lock()
    remote, _fake = _remote({content_key(_sha(d)): d for d in SCOPE_FILES.values()})
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "data" / "corpus").symlink_to(outside)
    report = _materialize_all(repo, lock, ContentCache(tmp_path / "cache"), [remote])
    assert len(report.failed) == len(SCOPE_FILES)
    assert not any(outside.rglob("*"))


# --------------------------------------------------------------------------- migrate (conservation)


def _tracked_repo(tmp_path: Path, files: dict[str, bytes]) -> Path:
    repo = _init_repo(tmp_path / "repo")
    for rel, data in files.items():
        _write(repo, rel, data)
    _git(repo, "add", "-f", *files)
    _write(repo, "data/corpus/snapshots/counts.json", b"{}")
    _git(repo, "add", "-f", "data/corpus/snapshots/counts.json")
    _git(repo, "commit", "-q", "-m", "track corpus")
    return repo


def test_migrate_conserves_every_tracked_file(tmp_path: Path, monkeypatch) -> None:
    files = dict(SCOPE_FILES)
    files["data/corpus/provisions/us/regulation/v9.jsonl"] = b"{}\n"
    files["data/corpus/sources/us/regulation/v9/doc.pdf"] = SCOPE_FILES[
        "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    ]  # same bytes in two scopes
    repo = _tracked_repo(tmp_path, files)
    base_blobs = {b.path: b for b in protected_tree_blobs(repo, "HEAD")}
    monkeypatch.chdir(repo)

    assert cli_main(["corpus", "migrate", "--repo", str(repo), "--json"]) == 0
    _git(repo, "commit", "-q", "-m", "migrate")

    locks = load_locks_at_ref(repo, "HEAD")
    assert not locks.errors
    assert set(locks.by_path) == set(files)
    for rel, data in files.items():
        entry = locks.by_path[rel]
        assert (entry.sha256, entry.size, entry.git_blob) == (_sha(data), len(data), base_blobs[rel].oid)
    assert protected_tree_blobs(repo, "HEAD") == []
    assert "data/corpus/snapshots/counts.json" in _git(repo, "ls-files")
    assert all((repo / rel).read_bytes() == data for rel, data in files.items())
    # Migrating again is a no-op.
    assert cli_main(["corpus", "migrate", "--repo", str(repo), "--json"]) == 0
    assert _git(repo, "status", "--porcelain") == ""


def test_two_lock_builders_agree(tmp_path: Path) -> None:
    """Differential: hashing the worktree and hashing git blobs give the same lock."""
    repo = _tracked_repo(tmp_path, SCOPE_FILES)
    from_git = locks_from_hashed_blobs(hash_tree_blobs(repo, protected_tree_blobs(repo, "HEAD")))[SCOPE]
    from_worktree = lock_from_worktree(repo, SCOPE)
    assert [(e.path, e.sha256, e.size) for e in from_git.files] == [
        (e.path, e.sha256, e.size) for e in from_worktree.files
    ]
    for blob in list_tree_blobs(repo, "HEAD", "data/corpus"):
        if blob.path in SCOPE_FILES:
            assert from_git.files[[e.path for e in from_git.files].index(blob.path)].git_blob == blob.oid


def test_fetch_after_migration_restores_the_tree_from_git_objects(tmp_path: Path, monkeypatch) -> None:
    repo = _tracked_repo(tmp_path, SCOPE_FILES)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "cache"))
    assert cli_main(["corpus", "migrate", "--repo", str(repo)]) == 0
    _git(repo, "commit", "-q", "-m", "migrate")
    for rel in SCOPE_FILES:
        (repo / rel).unlink()
    assert cli_main(["corpus", "fetch", "--repo", str(repo), "nz", "--no-r2", "--json"]) == 0
    assert all((repo / rel).read_bytes() == data for rel, data in SCOPE_FILES.items())
    assert cli_main(["corpus", "status", "--repo", str(repo), "--verify"]) == 0


# --------------------------------------------------------------------------- lock and push


def test_lock_writes_the_scope_and_push_uploads_only_missing_objects(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    for rel, data in SCOPE_FILES.items():
        _write(repo, rel, data)
    remote, fake = _remote({content_key(_sha(b'{"items": []}\n')): b'{"items": []}\n'})
    monkeypatch.setattr(corpus_cli, "_remote", lambda workers: remote)
    cache = ContentCache(tmp_path / "cache")

    written, pushed = corpus_cli.lock_scopes(repo, [SCOPE], cache=cache, push=True)
    assert written[0]["files"] == len(SCOPE_FILES)
    assert pushed is not None and pushed["uploaded"] == len(SCOPE_FILES) - 1 and not pushed["failed"]
    assert all(fake.objects[content_key(_sha(d))] == d for d in SCOPE_FILES.values())
    assert load_locks(repo).locks[SCOPE] == _scope_lock()

    fake.puts.clear()
    _written, pushed_again = corpus_cli.lock_scopes(repo, [SCOPE], cache=cache, push=True)
    assert pushed_again is not None and pushed_again["uploaded"] == 0 and not fake.puts


def test_lock_refuses_to_drop_files_that_were_never_fetched(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    for rel, data in SCOPE_FILES.items():
        _write(repo, rel, data)
    cache = ContentCache(tmp_path / "cache")
    corpus_cli.lock_scopes(repo, [SCOPE], cache=cache)
    missing = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    (repo / missing).unlink()
    with pytest.raises(corpus_cli.LockRefusedError, match="not in the worktree"):
        corpus_cli.lock_scopes(repo, [SCOPE], cache=cache)
    written, _ = corpus_cli.lock_scopes(repo, [SCOPE], cache=cache, drop_missing=True)
    assert written[0]["removed"] == [missing]


def test_push_detects_a_remote_object_with_wrong_bytes(tmp_path: Path) -> None:
    data = b"good"
    source = tmp_path / "f"
    source.write_bytes(data)
    remote, _fake = _remote({content_key(_sha(data)): b"evil"})
    with pytest.raises(Exception, match="sha256 mismatch|byte count mismatch"):
        remote.put(source, sha256=_sha(data), size=len(data))


# --------------------------------------------------------------------------- resolver


def test_resolver_is_inert_without_locks_and_fetches_with_them(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    remote, _fake = _remote({content_key(_sha(d)): d for d in SCOPE_FILES.values()})
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[remote])
    assert resolver.ensure_paths(["data/corpus/provisions"]).materialized == []

    write_lock(repo, _scope_lock())
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[remote])
    report = resolver.ensure_paths(["data/corpus/provisions"])
    assert report.materialized == ["data/corpus/provisions/nz/statute/2026-07-10.jsonl"]
    target = resolver.resolve("data/corpus/coverage/nz/statute/2026-07-10.json")
    assert target.read_bytes() == SCOPE_FILES["data/corpus/coverage/nz/statute/2026-07-10.json"]
    with pytest.raises(CorpusNotMaterializedError, match="neither present nor locked"):
        resolver.resolve("data/corpus/provisions/nz/statute/unlocked.jsonl")


def test_resolver_raises_when_bytes_are_unavailable(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _scope_lock())
    remote, _fake = _remote({})
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[remote])
    with pytest.raises(CorpusNotMaterializedError, match="could not be fetched"):
        resolver.ensure_scopes([SCOPE])


def test_cli_inputs_name_paths_selectors_and_optional_scopes(tmp_path: Path, monkeypatch) -> None:
    import argparse

    repo = _init_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    args = argparse.Namespace(
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version="v1",
        provisions=Path("data/corpus/provisions/nz/statute/v1.jsonl"),
        source_dir=str(repo / "data/corpus/sources/nz/statute/v1/raw"),
        release="manifests/releases/x.json",
        output=Path("out.json"),
        # sign-ingest-manifest's free-text --command lands on args.command.
        command="uv run x --source-dir data/corpus/sources/nz/statute/v1",
        func=None,
    )
    paths, scopes, selectors = corpus_inputs_from_args(args, repo=repo)
    assert paths == [
        "data/corpus/provisions/nz/statute/v1.jsonl",
        "data/corpus/sources/nz/statute/v1/raw",
    ]
    assert scopes == [("nz", "statute", "v1")]
    assert selectors == [Path("manifests/releases/x.json")]

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    args.base = repo / "data" / "corpus"  # absolute, from another directory
    args.provisions = repo / "data/corpus/provisions/nz/statute/v1.jsonl"
    paths, scopes, _selectors = corpus_inputs_from_args(args, repo=repo)
    assert "data/corpus/provisions/nz/statute/v1.jsonl" in paths
    assert scopes == [("nz", "statute", "v1")]


def test_read_entry_bytes_prefers_a_matching_worktree_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    data = b"on disk"
    _write(repo, "data/corpus/provisions/nz/statute/v1.jsonl", data)
    entry = LockEntry("data/corpus/provisions/nz/statute/v1.jsonl", _sha(data), len(data))
    remote, fake = _remote({})
    assert read_entry_bytes(repo, entry, ContentCache(tmp_path / "cache"), [remote]) == data
    assert not fake.gets


def test_verify_reports_remote_gaps(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _scope_lock())
    present = SCOPE_FILES["data/corpus/provisions/nz/statute/2026-07-10.jsonl"]
    remote, _fake = _remote({content_key(_sha(present)): present})
    monkeypatch.setattr(corpus_cli, "_remote", lambda workers: remote)
    monkeypatch.chdir(repo)
    assert cli_main(["corpus", "verify", "--repo", str(repo)]) == 0
    assert cli_main(["corpus", "verify", "--repo", str(repo), "--remote"]) == 1


def test_lock_json_uses_one_line_per_entry(tmp_path: Path) -> None:
    payload = serialize_lock(_scope_lock()).decode()
    entry_lines = [line for line in payload.splitlines() if line.startswith("    {")]
    assert len(entry_lines) == len(SCOPE_FILES)
    assert all(json.loads(line.rstrip(",")) for line in entry_lines)


def test_concurrent_fetch_of_identical_bytes_never_races(tmp_path: Path) -> None:
    """Regression: replacing a cache object mid-clone made clonefile fail (ENOENT).

    Hypothesis found it with three single-file artifacts holding the same bytes;
    cache objects are now write-once.
    """
    data = b""
    entries = [
        LockEntry(f"data/corpus/{kind}/0/0/0.{'jsonl' if kind == 'provisions' else 'json'}", _sha(data), 0)
        for kind in ("inventory", "provisions", "coverage")
    ]
    lock = CorpusLock.from_entries(("0", "0", "0"), entries)
    for attempt in range(60):
        remote, _fake = _remote({content_key(_sha(data)): data})
        report = materialize(
            tmp_path / f"repo{attempt}",
            lock.files,
            ContentCache(tmp_path / f"cache{attempt}"),
            [remote],
            workers=4,
        )
        assert report.ok, report.failed
        assert (tmp_path / f"cache{attempt}" / content_key(_sha(data))).stat().st_nlink == 1


def test_no_cache_fetch_streams_verified_bytes_into_place(tmp_path: Path) -> None:
    lock = _scope_lock()
    remote, _fake = _remote({content_key(_sha(d)): d for d in SCOPE_FILES.values()})
    repo = tmp_path / "repo"
    report = materialize(repo, lock.files, None, [remote], workers=4)
    assert report.ok and report.methods == {"stream": len(SCOPE_FILES)}
    assert all((repo / rel).read_bytes() == data for rel, data in SCOPE_FILES.items())
    corrupt, _ = _remote({content_key(_sha(d)): b"x" + d for d in SCOPE_FILES.values()})
    bad = materialize(tmp_path / "bad", lock.files, None, [corrupt], workers=2)
    assert len(bad.failed) == len(SCOPE_FILES)
    assert not any(p.is_file() for p in (tmp_path / "bad").rglob("*"))


# --------------------------------------------------------------------------- portable names (invariant 9)

_name = st.sampled_from(["a", "A", "b", "B", "café", "CAFÉ", "café", "ſx", "sx", "x"])


def _reference_collisions(paths: list[str]) -> set[frozenset[str]]:
    """Brute force: every pair of distinct names (files or directories) that fold alike."""
    import unicodedata as ud

    def fold(text: str) -> str:
        return ud.normalize("NFKC", ud.normalize("NFKC", text).casefold())

    names: set[str] = set()
    directories: set[str] = set()
    for path in paths:
        parts = path.split("/")
        for depth in range(1, len(parts) + 1):
            names.add("/".join(parts[:depth]))
            if depth < len(parts):
                directories.add("/".join(parts[:depth]))
    pairs = {frozenset((a, b)) for a in names for b in names if a != b and fold(a) == fold(b)}
    pairs |= {frozenset((path, f"{path}/…")) for path in set(paths) & directories}
    return pairs


@PROPERTY_SETTINGS
@given(st.lists(st.lists(_name, min_size=1, max_size=3).map("/".join), unique=True, max_size=6))
def test_fold_collisions_matches_a_brute_force_reference(paths: list[str]) -> None:
    found = {frozenset(pair) for pair in fold_collisions(paths)}
    reference = _reference_collisions(paths)
    # Same verdict, and every reported pair is a real collision.
    assert bool(found) == bool(reference)
    assert found <= reference
    # Every colliding name appears in some reported pair.
    assert {n for pair in reference for n in pair} <= {n for pair in found for n in pair} | {
        n for pair in reference for n in pair if n.endswith("/…")
    } | {n for pair in found for n in pair}


_nfc_name = _name.filter(lambda n: unicodedata.normalize("NFC", n) == n)  # lock paths are NFC


@PROPERTY_SETTINGS
@given(st.lists(st.lists(_nfc_name, min_size=1, max_size=3).map("/".join), unique=True, min_size=1, max_size=6))
def test_a_lock_set_is_invalid_exactly_when_its_names_collide(tmp_path_factory, tails: list[str]) -> None:
    base = "data/corpus/sources/nz/statute/v1"
    paths = [f"{base}/{tail}" for tail in tails]
    repo = tmp_path_factory.mktemp("portable")
    write_lock(repo, CorpusLock.from_entries(("nz", "statute", "v1"), [LockEntry(p, "0" * 64, 1) for p in paths]))
    errors = load_locks(repo).errors
    assert bool(errors) == bool(_reference_collisions(paths))


# --------------------------------------------------------------------------- path naming (invariant 10)

PROV = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
COVERAGE = "data/corpus/coverage/nz/statute/2026-07-10.json"
INVENTORY = "data/corpus/inventory/nz/statute/2026-07-10.json"
PROV_ROW = {"jurisdiction": "nz", "document_class": "statute", "citation_path": "nz/statute/a"}
# SCOPE_FILES with a provisions row that load_provisions parses.
READABLE_FILES = {**SCOPE_FILES, PROV: (json.dumps(PROV_ROW) + "\n").encode()}


def _locked_checkout(path: Path, monkeypatch) -> Path:
    """A checkout whose scope lock the module-level helpers fetch from an in-memory R2."""
    repo = _init_repo(path)
    write_lock(repo, _scope_lock(READABLE_FILES))
    remote, _fake = _remote({content_key(_sha(d)): d for d in READABLE_FILES.values()})
    monkeypatch.setattr(R2ObjectStore, "from_environment", classmethod(lambda cls, **_kwargs: remote))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(path.parent / f"{path.name}-cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    return repo


def _checkout_spellings(repo: Path) -> dict[str, Path]:
    """Other spellings of ``repo``: symlinks always, others where the platform has them."""
    alias = repo.parent / f"{repo.name}-alias"
    alias.symlink_to(repo, target_is_directory=True)
    double = repo.parent / f"{repo.name}-alias-of-alias"
    double.symlink_to(alias, target_is_directory=True)
    spellings = {"alias": alias, "alias of an alias": double}
    variant = repo.parent / repo.name.upper()
    if variant.exists():  # case-insensitive filesystem (APFS, NTFS)
        spellings["case variant"] = variant
    text = str(repo)
    if text.startswith("/private/") and Path("/" + text[len("/private/") :]).exists():
        spellings["/private-less"] = Path("/" + text[len("/private/") :])  # macOS /var, /tmp
    if Path("/System/Volumes/Data" + text).exists():
        spellings["firmlink"] = Path("/System/Volumes/Data" + text)  # macOS data volume
    return spellings


def _placed_regular(repo: Path, rel: str) -> bool:
    target = repo / rel
    return target.is_file() and not target.is_symlink() and target.read_bytes() == READABLE_FILES[rel]


def test_helpers_fetch_through_every_spelling_of_the_checkout(tmp_path: Path, monkeypatch) -> None:
    """#770 finding: a checkout spelled through a symlink read as no checkout, so an
    absent locked provisions file loaded as an empty scope."""
    kinds = list(_checkout_spellings(_init_repo(tmp_path / "probe")))
    assert {"alias", "alias of an alias"} <= set(kinds)
    for index, name in enumerate(kinds):
        repo = _locked_checkout(tmp_path / f"repo{index}", monkeypatch)
        alias = _checkout_spellings(repo)[name]
        assert str(alias) != str(repo) and os.path.samefile(alias, repo)

        assert load_provisions(alias / PROV)[0].citation_path == "nz/statute/a", name
        assert _placed_regular(repo, PROV), name
        assert fetch_locked_file(alias / INVENTORY), name
        assert _placed_regular(repo, INVENTORY), name
        ensure_corpus_paths([alias / COVERAGE], repo=repo)
        assert _placed_regular(repo, COVERAGE), name
        require_materialized([alias / "data/corpus/sources"], repo=repo, fetch=True)
        assert all(_placed_regular(repo, rel) for rel in READABLE_FILES), name
        assert resolve_corpus_path(alias / COVERAGE, repo=repo).read_bytes() == READABLE_FILES[COVERAGE]


def test_a_dangling_symlink_at_a_locked_path_does_not_read_as_empty(tmp_path: Path, monkeypatch) -> None:
    """Following the link out of the checkout made the locked path no corpus path, so
    load_provisions returned no rows for a scope whose file was never fetched."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    link = repo / PROV
    link.parent.mkdir(parents=True)
    nowhere = tmp_path / "nowhere" / "x.jsonl"
    link.symlink_to(nowhere)
    with pytest.raises(CorpusNotMaterializedError, match="is a symlink in this checkout"):
        load_provisions(link)
    with pytest.raises(CorpusNotMaterializedError, match="symlink"):
        ensure_corpus_paths([link], repo=repo)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([link], repo=repo)
    assert link.is_symlink() and not nowhere.exists() and not nowhere.parent.exists()


@pytest.mark.parametrize(
    "target_kind",
    [
        "cache object",
        "another corpus file",
        "the same file in another checkout",
        "a symlinked file in another checkout",
        "nothing",
    ],
)
def test_a_symlinked_corpus_file_names_its_own_path_and_is_refused(
    tmp_path: Path, monkeypatch, target_kind: str
) -> None:
    """A symlink where a locked file belongs is never accepted as that file: not
    followed to a cache object (an in-place write would corrupt it), not taken for
    the corpus file it points at, and never written through."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    resolver.ensure_paths([COVERAGE])  # puts the coverage bytes in the cache too
    if target_kind == "cache object":
        resolver.ensure_paths([PROV])
        (repo / PROV).unlink()
        target = resolver.cache.object_path(_sha(READABLE_FILES[PROV]))
    elif target_kind == "another corpus file":
        target = repo / COVERAGE
    elif target_kind in {"the same file in another checkout", "a symlinked file in another checkout"}:
        other = _locked_checkout(tmp_path / "other", monkeypatch)
        other_resolver = resolver_module.resolver_for(other)
        assert other_resolver is not None
        other_resolver.ensure_paths([PROV])
        target = other / PROV
        if target_kind == "a symlinked file in another checkout":
            # A link to a link: the walk stops at the path's own symlinked file.
            target.unlink()
            target.symlink_to(other_resolver.cache.object_path(_sha(READABLE_FILES[PROV])))
    else:
        target = tmp_path / "missing.jsonl"
    link = repo / PROV
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    before = target.read_bytes() if target.exists() else None

    assert resolver.relative(link) == PROV
    assert resolver.relative(Path(os.path.realpath(repo)) / PROV) == PROV
    if target_kind in {"the same file in another checkout", "a symlinked file in another checkout"}:
        # Only a directory link to the same path elsewhere is followed.
        assert CorpusResolver(tmp_path / "other", sources=[]).relative(link) is None
    with pytest.raises(CorpusNotMaterializedError, match="symlink"):
        load_provisions(link)
    with pytest.raises(CorpusNotMaterializedError, match="symlink"):
        fetch_locked_file(link)
    with pytest.raises(CorpusNotMaterializedError, match="symlink"):
        resolve_corpus_path(link, repo=repo)
    with pytest.raises(CorpusNotMaterializedError, match="is a symlink in this checkout"):
        resolver.resolve(PROV)
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks: remove the symlink"):
        ensure_corpus_paths([link], repo=repo)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([repo / "data/corpus/provisions"], repo=repo)
    assert link.is_symlink() and os.readlink(link) == str(target)
    assert (target.read_bytes() if target.exists() else None) == before


def test_an_unlocked_symlink_at_a_protected_path_is_not_resolved(tmp_path: Path, monkeypatch) -> None:
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    resolver.ensure_paths([PROV])
    link = repo / "data/corpus/provisions/nz/statute/latest.jsonl"
    link.symlink_to(repo / PROV)
    assert resolver.relative(link) == "data/corpus/provisions/nz/statute/latest.jsonl"
    with pytest.raises(CorpusNotMaterializedError, match="is a symlink, not a placed corpus file"):
        resolve_corpus_path(link, repo=repo)
    # Readers still read a path no lock names, as before.
    assert load_provisions(link)[0].citation_path == "nz/statute/a"


def test_a_link_outside_the_checkout_resolves_to_the_file_it_names(tmp_path: Path, monkeypatch) -> None:
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    link = tmp_path / "latest.jsonl"
    link.symlink_to(repo / PROV)  # dangling until the locked file is fetched
    monkeypatch.chdir(tmp_path)  # the link, not the working directory, finds the checkout
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None and resolver.relative(link) == PROV
    assert load_provisions(link)[0].citation_path == "nz/statute/a"
    assert _placed_regular(repo, PROV)
    # Review r1 finding 2: a live link to a placed file reads with fetching off.
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    assert load_provisions(link)[0].citation_path == "nz/statute/a"
    assert fetch_locked_file(link)
    assert resolve_corpus_path(link) == repo / PROV


@pytest.mark.parametrize("a_under", ["", "data/corpus/provisions"])
def test_an_unprotected_link_resolves_in_the_checkout_it_leads_to(
    tmp_path: Path, monkeypatch, a_under: str
) -> None:
    """Review r1 finding 1: a link outside the protected paths of one checkout,
    into another, belongs to the checkout it leads to, even where the first
    checkout itself sits under a directory spelled like a protected path."""
    a = _locked_checkout(tmp_path / a_under / "a", monkeypatch)
    b = _locked_checkout(tmp_path / "b", monkeypatch)
    (a / "docs").mkdir()
    link = a / "docs/latest.jsonl"
    link.symlink_to(b / PROV)  # dangling until b fetches it
    monkeypatch.chdir(a)
    assert load_provisions(link)[0].citation_path == "nz/statute/a"
    assert _placed_regular(b, PROV) and not (a / PROV).exists()
    assert resolve_corpus_path(link) == b / PROV


def test_reading_a_link_outside_the_protected_paths_consults_no_lock(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 4: any live symlink loaded every lock (and failed on an
    invalid one); only a symlinked file at a protected path is checked."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    next((repo / LOCK_ROOT).rglob("*.json")).write_text("not a lock\n")
    monkeypatch.chdir(repo)
    rows = _write(tmp_path, "elsewhere/rows.jsonl", READABLE_FILES[PROV])
    (repo / "docs").mkdir()
    resolver_module._repo_root_for_dir.cache_clear()
    git_calls: list[object] = []
    real_run = subprocess.run
    monkeypatch.setattr(
        resolver_module.subprocess, "run", lambda *a, **k: git_calls.append(a) or real_run(*a, **k)
    )
    for link in (tmp_path / "rows.jsonl", repo / "docs/rows.jsonl"):
        link.symlink_to(rows)
        assert load_provisions(link)[0].citation_path == "nz/statute/a"
        assert fetch_locked_file(link)
    assert git_calls == []  # review r2 nit 3: no git process to read an unprotected link


def test_a_bare_corpus_path_with_dotdot_resolves_through_the_checkout(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 3: ``data/corpus/provisions/../provisions/...`` named no
    locked file, so require_materialized passed over an absent one."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    dotted = PROV.replace("provisions/", "provisions/../provisions/", 1)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None and resolver.relative(dotted) == PROV
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([dotted], repo=repo)
    require_materialized([dotted], repo=repo, fetch=True)
    assert _placed_regular(repo, PROV)


def test_a_symlinked_directory_still_resolves_into_the_checkout_holding_it(
    tmp_path: Path, monkeypatch
) -> None:
    """Directory symlinks keep their physical meaning: a worktree whose
    ``data/corpus/provisions`` links to another checkout reads, and fetches,
    that checkout's files."""
    other = _locked_checkout(tmp_path / "other", monkeypatch)
    worktree = _init_repo(tmp_path / "worktree")
    write_lock(worktree, _scope_lock(READABLE_FILES))
    (worktree / "data/corpus").mkdir(parents=True)
    (worktree / "data/corpus/provisions").symlink_to(other / "data/corpus/provisions", target_is_directory=True)
    (other / "data/corpus/provisions").mkdir(parents=True)
    monkeypatch.chdir(worktree)
    assert CorpusResolver(worktree, sources=[]).relative(worktree / PROV) is None
    assert CorpusResolver(other, sources=[]).relative(worktree / PROV) == PROV
    assert load_provisions(worktree / PROV)[0].citation_path == "nz/statute/a"
    assert _placed_regular(other, PROV)
    # A pointer outside both checkouts, through the sharing link, names the
    # other checkout's file too (review r2c).
    pointer = tmp_path / "latest.jsonl"
    pointer.symlink_to(worktree / PROV)
    assert CorpusResolver(worktree, sources=[]).relative(pointer) is None
    assert CorpusResolver(other, sources=[]).relative(pointer) == PROV
    holder = resolver_module._checkout_for(pointer)
    assert holder is not None and os.path.samefile(holder, other)
    # A file in place beneath the link needs no fetch, so ensure passes.
    report = CorpusResolver(worktree, sources=[]).ensure_paths(["data/corpus/provisions"])
    assert report.present == [PROV] and report.failed == {}
    # Fetch never writes through the link, and says so rather than blame R2.
    (other / PROV).unlink()
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks: remove the symlink"):
        CorpusResolver(worktree, sources=[]).ensure_paths(["data/corpus/provisions"])
    assert not (other / PROV).exists()


# Where a test links ``data/corpus/provisions/nz`` (or an ancestor), the
# places no lock guards that the link can lead to.
_UNGUARDED_TARGETS = ("empty directory outside", "nothing", "unprotected directory here", "another checkout's docs")


def _link_unguarded(repo: Path, linked: str, target_kind: str, tmp_path: Path, monkeypatch) -> Path:
    """Link ``repo/<linked>`` to a directory no lock guards; return the target."""
    if target_kind == "empty directory outside":
        target = tmp_path / "elsewhere" / "empty"
    elif target_kind == "nothing":  # e.g. the checkout it once shared was removed
        target = tmp_path / "removed-checkout" / linked
    elif target_kind == "unprotected directory here":
        target = repo / "scratch" / linked
    else:
        target = _locked_checkout(tmp_path / "other", monkeypatch) / "docs" / linked
    if target_kind != "nothing":
        target.mkdir(parents=True)
    (repo / linked).parent.mkdir(parents=True, exist_ok=True)
    (repo / linked).symlink_to(target, target_is_directory=True)
    return target


def _tree(path: Path) -> list[str]:
    return sorted(str(p.relative_to(path)) for p in path.rglob("*")) if path.exists() else ["<absent>"]


@pytest.mark.parametrize("linked", ["data/corpus/provisions/nz", "data/corpus/provisions", "data"])
@pytest.mark.parametrize("target_kind", _UNGUARDED_TARGETS)
def test_a_directory_link_to_an_unguarded_place_does_not_read_as_empty(
    tmp_path: Path, monkeypatch, linked: str, target_kind: str
) -> None:
    """A directory link at (or above) a protected path that leads where no lock
    guards (outside every checkout, nowhere, an unprotected directory) made every
    path below it name no locked file, so an unfetched provisions file loaded as
    an empty scope. The path now names itself and every helper refuses the link."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    target = _link_unguarded(repo, linked, target_kind, tmp_path, monkeypatch)
    before = _tree(target)
    monkeypatch.chdir(tmp_path)  # the path, not the working directory, finds the checkout
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    for spelling in [repo, *_checkout_spellings(repo).values()]:
        assert resolver.relative(spelling / PROV) == PROV, spelling
        assert resolver.relative(spelling / "data/corpus/provisions/nz") == "data/corpus/provisions/nz"
        # Review r1 finding 3: the linked directory itself selects locked files.
        assert resolver.relative(spelling / linked) == linked, spelling
    if target_kind == "another checkout's docs":
        other = CorpusResolver(tmp_path / "other", sources=[])
        assert other.relative(repo / PROV) is None  # one checkout names it
        assert other.relative(os.path.realpath(repo / PROV)) == f"docs/{linked}/" + PROV[len(linked) + 1 :]

    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks: remove the symlink"):
        load_provisions(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        fetch_locked_file(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        resolve_corpus_path(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks: remove the symlink"):
        ensure_corpus_paths([repo / "data/corpus/provisions/nz"], repo=repo)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout.*is a symlink"):
        require_materialized([repo / "data/corpus/provisions/nz"])
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout.*is a symlink"):
        require_materialized([repo / linked])
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        ensure_corpus_paths([repo / linked], repo=repo)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="fetching is off.*is a symlink"):
        load_provisions(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout.*is a symlink"):
        ensure_corpus_paths([repo / PROV], repo=repo)
    assert (repo / linked).is_symlink() and _tree(target) == before  # nothing written through it


def test_files_in_place_beneath_a_directory_link_are_read_and_absent_ones_refused(
    tmp_path: Path, monkeypatch
) -> None:
    """A file present beneath a directory link counts as in place, with fetching
    on or off; an absent locked file beneath it is refused, never written."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    holder = tmp_path / "external" / "nz"
    _write(holder, "statute/2026-07-10.jsonl", READABLE_FILES[PROV])
    (repo / "data/corpus/provisions").mkdir(parents=True)
    (repo / "data/corpus/provisions/nz").symlink_to(holder, target_is_directory=True)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    resolver_module._repo_root_for_dir.cache_clear()
    git_calls: list[object] = []
    real_run = subprocess.run
    monkeypatch.setattr(
        resolver_module.subprocess, "run", lambda *a, **k: git_calls.append(a) or real_run(*a, **k)
    )
    assert resolver.relative(repo / PROV) == PROV
    assert git_calls == []  # its own checkout is recognized by identity, without git
    monkeypatch.setattr(resolver_module.subprocess, "run", real_run)

    assert load_provisions(repo / PROV)[0].citation_path == "nz/statute/a"
    require_materialized([repo / "data/corpus/provisions/nz"])
    assert ensure_corpus_paths([repo / "data/corpus/provisions/nz"], repo=repo).present == [PROV]
    assert resolve_corpus_path(repo / PROV) == repo / PROV
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    ensure_corpus_paths([repo / "data/corpus/provisions/nz"], repo=repo)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")

    # A changed file is reported, and left, as it would be anywhere else.
    (holder / "statute/2026-07-10.jsonl").write_bytes(b"{}\n")
    assert ensure_corpus_paths([repo / PROV], repo=repo).modified == [PROV]
    assert (holder / "statute/2026-07-10.jsonl").read_bytes() == b"{}\n"
    (holder / "statute/2026-07-10.jsonl").unlink()
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        load_provisions(repo / PROV)
    assert _tree(holder) == ["statute"]


def test_a_source_beneath_a_directory_link_still_comes_with_its_siblings(tmp_path: Path, monkeypatch) -> None:
    """``resolve_corpus_path`` took a present source file below a directory link
    to an unguarded place for a plain file, so a scope's half-present sources
    directory read as a smaller scope."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    act = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    linked = "data/corpus/sources/nz/statute/2026-07-10/official"
    holder = tmp_path / "external" / "official"
    _write(holder, "act.html", READABLE_FILES[act])  # its sibling "sub dir/s 2.xml" is absent
    (repo / linked).parent.mkdir(parents=True)
    (repo / linked).symlink_to(holder, target_is_directory=True)
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        resolve_corpus_path(repo / act)
    # Review r2: reached through an alias outside the checkout, neither
    # spelling names a sources/ directory, and the sibling was skipped.
    alias = tmp_path / "alias"
    alias.symlink_to(repo / linked, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        resolve_corpus_path(alias / "act.html")
    _write(holder, "sub dir/s 2.xml", READABLE_FILES[linked + "/sub dir/s 2.xml"])
    assert resolve_corpus_path(repo / act) == repo / act


def test_a_link_chain_names_the_last_protected_place_it_stands(tmp_path: Path, monkeypatch) -> None:
    """A worktree shares another checkout's provisions, and that checkout's ``nz``
    links outside every checkout: the sharing link is followed, so the path is
    the other checkout's, and that checkout refuses its own link."""
    other = _locked_checkout(tmp_path / "other", monkeypatch)
    worktree = _init_repo(tmp_path / "worktree")
    write_lock(worktree, _scope_lock(READABLE_FILES))
    (worktree / "data/corpus").mkdir(parents=True)
    (worktree / "data/corpus/provisions").symlink_to(other / "data/corpus/provisions", target_is_directory=True)
    empty = tmp_path / "elsewhere" / "nz"
    empty.mkdir(parents=True)
    (other / "data/corpus/provisions").mkdir(parents=True)
    (other / "data/corpus/provisions/nz").symlink_to(empty, target_is_directory=True)
    assert CorpusResolver(worktree, sources=[]).relative(worktree / PROV) is None
    assert CorpusResolver(other, sources=[]).relative(worktree / PROV) == PROV
    holder = resolver_module._checkout_for(worktree / PROV)
    assert holder is not None and os.path.samefile(holder, other)
    with pytest.raises(CorpusNotMaterializedError, match="through a symlink: .*/other/data/corpus/provisions/nz"):
        load_provisions(worktree / PROV)
    assert _tree(empty) == []


@pytest.mark.parametrize(
    ("where", "name"),
    [
        ("this checkout", "us"),
        ("another checkout", "us"),
        # Review r1 finding 1: a name that only folds to "nz" (fullwidth) is
        # another path; it was taken for the same one.
        ("another checkout", "\uff4e\uff5a"),
    ],
)
def test_a_directory_link_to_another_corpus_path_names_its_own_path(
    tmp_path: Path, monkeypatch, where: str, name: str
) -> None:
    """Following ``provisions/nz`` to another corpus directory named a path no
    lock names (``provisions/us/...``), so an unfetched nz scope read as empty.
    Only a link to exactly the same path in another checkout is followed."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    holder = repo if where == "this checkout" else _locked_checkout(tmp_path / "other", monkeypatch)
    (holder / f"data/corpus/provisions/{name}/statute").mkdir(parents=True)
    (repo / "data/corpus/provisions").mkdir(parents=True, exist_ok=True)
    (repo / "data/corpus/provisions/nz").symlink_to(holder / f"data/corpus/provisions/{name}", target_is_directory=True)
    assert CorpusResolver(repo, sources=[]).relative(repo / PROV) == PROV
    if holder != repo:
        assert CorpusResolver(holder, sources=[]).relative(repo / PROV) is None
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        load_provisions(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout.*is a symlink"):
        require_materialized([repo / "data/corpus/provisions/nz"])
    assert _tree(holder / f"data/corpus/provisions/{name}") == ["statute"]


def test_a_link_to_a_link_names_where_the_chain_stands(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 2: ``a``'s ``nz`` links straight to ``b``'s ``nz``, which
    links to an empty directory. Only links spelled in the path were seen, so
    ``b``'s link (and lock) was skipped and the absent file read as empty. The
    path is followed into ``b``, which refuses its own link."""
    a = _init_repo(tmp_path / "a")
    b = _locked_checkout(tmp_path / "b", monkeypatch)
    write_lock(a, _scope_lock({PROV.replace("/nz/", "/us/"): b"{}\n"}, scope=("us", "statute", "2026-07-10")))
    empty = tmp_path / "empty"
    empty.mkdir()
    for root in (a, b):
        (root / "data/corpus/provisions").mkdir(parents=True)
    (b / "data/corpus/provisions/nz").symlink_to(empty, target_is_directory=True)
    (a / "data/corpus/provisions/nz").symlink_to(b / "data/corpus/provisions/nz", target_is_directory=True)
    assert CorpusResolver(a, sources=[]).relative(a / PROV) is None
    assert CorpusResolver(b, sources=[]).relative(a / PROV) == PROV
    holder = resolver_module._checkout_for(a / PROV)
    assert holder is not None and os.path.samefile(holder, b)
    with pytest.raises(CorpusNotMaterializedError, match="through a symlink: .*/b/data/corpus/provisions/nz"):
        load_provisions(a / PROV)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="fetching is off.*/b/data/corpus/provisions/nz is a symlink"):
        load_provisions(a / PROV)
    assert _tree(empty) == []


def test_a_chain_that_returns_to_the_path_it_spells_is_followed(tmp_path: Path, monkeypatch) -> None:
    """``a/nz`` links to ``b/us``, which links to ``c/nz``: the path reaches
    exactly the path it spells, so ``c`` names it (as a direct link to ``c/nz``
    would), and the fast path that names it without walking agrees."""
    a = _init_repo(tmp_path / "a")
    b = _init_repo(tmp_path / "b")
    c = _locked_checkout(tmp_path / "c", monkeypatch)
    (c / "data/corpus/provisions/nz").mkdir(parents=True)
    (b / "data/corpus/provisions").mkdir(parents=True)
    (b / "data/corpus/provisions/us").symlink_to(c / "data/corpus/provisions/nz", target_is_directory=True)
    (a / "data/corpus/provisions").mkdir(parents=True)
    (a / "data/corpus/provisions/nz").symlink_to(b / "data/corpus/provisions/us", target_is_directory=True)
    names = [CorpusResolver(root, sources=[]).relative(a / PROV) for root in (a, b, c)]
    assert names == [None, None, PROV]
    holder = resolver_module._checkout_for(a / PROV)
    assert holder is not None and os.path.samefile(holder, c)
    assert load_provisions(a / PROV)[0].citation_path == "nz/statute/a"
    assert _placed_regular(c, PROV)


@pytest.mark.parametrize("where", ["outside the checkout", "docs"])
def test_a_pointer_through_a_directory_link_reads_like_the_path_it_names(
    tmp_path: Path, monkeypatch, where: str
) -> None:
    """Review r2c finding 1: a ``latest.jsonl`` pointer at no protected path,
    to a provisions file below a directory link to an empty directory, ended
    the walk at itself, so it read as an empty scope. A pointer is followed
    like any other link: it reads, and is refused, as the path it names."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    empty = tmp_path / "empty"
    (empty / "statute").mkdir(parents=True)
    (repo / "data/corpus/provisions").mkdir(parents=True)
    (repo / "data/corpus/provisions/nz").symlink_to(empty, target_is_directory=True)
    pointer = (tmp_path if where == "outside the checkout" else repo / "docs") / "latest.jsonl"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.symlink_to(repo / PROV)
    monkeypatch.chdir(tmp_path)
    assert resolver_module._link_holder(pointer) is None  # the pointer stands at no protected path
    assert CorpusResolver(repo, sources=[]).relative(pointer) == PROV
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        load_provisions(pointer)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout.*is a symlink"):
        require_materialized([pointer])
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="fetching is off.*is a symlink"):
        load_provisions(pointer)
    # With the file in place beneath the link, the pointer reads it, fetching off too.
    (empty / "statute/2026-07-10.jsonl").write_bytes(READABLE_FILES[PROV])
    assert load_provisions(pointer)[0].citation_path == "nz/statute/a"
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert load_provisions(pointer)[0].citation_path == "nz/statute/a"


def test_a_directory_link_to_a_regular_file_is_refused(tmp_path: Path, monkeypatch) -> None:
    """Review r2: ``provisions/nz`` linking to a regular file makes every path
    below it fail with ENOTDIR; the helpers refuse the link instead of raising
    an unexplained OS error or reading the scope as empty."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    a_file = _write(tmp_path, "a-file", b"x")
    (repo / "data/corpus/provisions").mkdir(parents=True)
    (repo / "data/corpus/provisions/nz").symlink_to(a_file)
    assert CorpusResolver(repo, sources=[]).relative(repo / PROV) == PROV
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        load_provisions(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        ensure_corpus_paths([repo / "data/corpus/provisions/nz"], repo=repo)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="fetching is off.*is a symlink"):
        load_provisions(repo / PROV)
    assert a_file.read_bytes() == b"x"


def test_a_checkout_without_src_is_still_a_checkout(tmp_path: Path, monkeypatch) -> None:
    """Review r2: a sparse checkout that holds lock files and data but no
    ``src/`` was no checkout at all, so its unfetched locked files read as
    empty. A git top level with the lock directory is a checkout."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    for path in sorted((repo / "src").rglob("*"), reverse=True):
        path.rmdir()
    (repo / "src").rmdir()
    resolver_module._repo_root_for_dir.cache_clear()
    monkeypatch.chdir(tmp_path)
    holder = resolver_module._checkout_for(repo / PROV)
    assert holder is not None and os.path.samefile(holder, repo)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="locked but absent"):
        load_provisions(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([repo / "data/corpus/provisions"])
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert load_provisions(repo / PROV)[0].citation_path == "nz/statute/a"


def test_helpers_without_repo_use_the_checkout_each_path_names(tmp_path: Path, monkeypatch) -> None:
    """Review r2: ``ensure_corpus_paths`` without ``repo`` asked the working
    directory's checkout, so from anywhere else it passed over a path below a
    link to an empty directory. Each path now goes to the checkout naming it."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    empty = tmp_path / "empty"
    empty.mkdir()
    (repo / "data/corpus/provisions").mkdir(parents=True)
    (repo / "data/corpus/provisions/nz").symlink_to(empty, target_is_directory=True)
    for cwd in (_init_repo(tmp_path / "elsewhere"), tmp_path):
        monkeypatch.chdir(cwd)
        with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
            ensure_corpus_paths([repo / "data/corpus/provisions/nz"])
        monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
        with pytest.raises(CorpusNotMaterializedError, match="not in this checkout.*is a symlink"):
            ensure_corpus_paths([repo / "data/corpus/provisions/nz"])
        monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    # Paths of two checkouts in one call: each is fetched into its own.
    first = _locked_checkout(tmp_path / "first", monkeypatch)
    second = _locked_checkout(tmp_path / "second", monkeypatch)
    report = ensure_corpus_paths([first / PROV, second / COVERAGE])
    assert sorted(report.materialized) == sorted([PROV, COVERAGE])
    assert _placed_regular(first, PROV) and _placed_regular(second, COVERAGE)
    assert not (first / COVERAGE).exists() and not (second / PROV).exists()
    # The first path's checkout is complete; the second path's is not.
    (second / COVERAGE).unlink()
    with pytest.raises(CorpusNotMaterializedError, match=f"not in this checkout \\(first: {COVERAGE}"):
        require_materialized([first / PROV, second / COVERAGE])


def test_a_nested_checkout_names_its_own_corpus_files(tmp_path: Path) -> None:
    """Worktrees live under the main checkout's ``.claude/worktrees/``: the
    worktree names its corpus files and the checkout around it names none of
    them. A checkout nested inside another's corpus tree belongs to itself for
    the module helpers, as git's top level does; the outer checkout, which
    names its own corpus paths without asking git, names them too (the one
    exception docs/corpus-storage.md invariant 10 states)."""
    outer = _init_repo(tmp_path / "main")
    worktree = _init_repo(outer / ".claude/worktrees/w")
    write_lock(worktree, _scope_lock(READABLE_FILES))
    assert CorpusResolver(worktree, sources=[]).relative(worktree / PROV) == PROV
    assert CorpusResolver(outer, sources=[]).relative(worktree / PROV) is None
    holder = resolver_module._checkout_for(worktree / PROV)
    assert holder is not None and os.path.samefile(holder, worktree)
    vendored = _init_repo(outer / "data/corpus/sources/nz/statute/2026-07-10/vendored")
    holder = resolver_module._checkout_for(vendored / PROV)
    assert holder is not None and os.path.samefile(holder, vendored)
    assert CorpusResolver(vendored, sources=[]).relative(vendored / PROV) == PROV
    assert (
        CorpusResolver(outer, sources=[]).relative(vendored / PROV)
        == f"data/corpus/sources/nz/statute/2026-07-10/vendored/{PROV}"
    )


def test_a_dotdot_below_a_directory_link_names_only_the_place_it_reaches(tmp_path: Path, monkeypatch) -> None:
    """The operating system resolves a ``..`` below a link from the link's
    target, so a lexical reading of it would name a different file."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    outside = tmp_path / "elsewhere"
    (outside / "nz").mkdir(parents=True)
    (repo / "data/corpus/provisions").mkdir(parents=True)
    (repo / "data/corpus/provisions/nz").symlink_to(outside / "nz", target_is_directory=True)
    resolver = CorpusResolver(repo, sources=[])
    back = "data/corpus/provisions/nz/../nz/statute/2026-07-10.jsonl"  # /elsewhere/nz/...: PROV
    away = "data/corpus/provisions/nz/../us/statute/2026-07-10.jsonl"  # /elsewhere/us/...: nothing here
    assert resolver.relative(repo / back) == PROV and resolver.relative(back) == PROV
    assert resolver.relative(repo / away) is None and resolver.relative(away) is None
    with pytest.raises(CorpusNotMaterializedError, match="never through symlinks"):
        require_materialized([back], repo=repo, fetch=True)
    # Climbing out of the class directory stands at no protected place, even
    # where a lexical reading reaches the same entry (data/corpus/x links there).
    (outside / "a/b").mkdir(parents=True)
    (outside / "x").mkdir()
    (repo / "data/corpus/provisions/up").symlink_to(outside / "a/b", target_is_directory=True)
    (repo / "data/corpus/x").symlink_to(outside / "x", target_is_directory=True)
    assert resolver.relative(repo / "data/corpus/provisions/up/../../x") is None


def test_a_symlinked_file_beneath_a_directory_link_is_refused(tmp_path: Path, monkeypatch) -> None:
    """A symlinked file stands where a locked file belongs wherever it lies
    physically, so a link to the right bytes beneath a directory link is
    refused too, not read as the locked file."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    holder = tmp_path / "external" / "nz"
    real = _write(tmp_path, "bytes/prov.jsonl", READABLE_FILES[PROV])
    (holder / "statute").mkdir(parents=True)
    (holder / "statute/2026-07-10.jsonl").symlink_to(real)
    (repo / "data/corpus/provisions").mkdir(parents=True)
    (repo / "data/corpus/provisions/nz").symlink_to(holder, target_is_directory=True)
    holder = resolver_module._link_holder(repo / PROV)
    assert holder is not None and os.path.samefile(holder, repo)
    with pytest.raises(CorpusNotMaterializedError, match="is a symlink in this checkout"):
        load_provisions(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([repo / PROV])
    assert real.read_bytes() == READABLE_FILES[PROV]



def test_a_symlinked_source_sibling_is_not_counted_as_fetched(tmp_path: Path, monkeypatch) -> None:
    """A source comes with its whole directory; a symlinked sibling is not a sibling."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    act = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    sibling = "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml"
    resolver.ensure_paths([act])
    (repo / sibling).unlink()
    (repo / sibling).symlink_to(resolver.cache.object_path(_sha(READABLE_FILES[sibling])))
    with pytest.raises(CorpusNotMaterializedError, match="symlink"):
        CorpusResolver(repo, cache=resolver.cache, sources=resolver.sources).resolve(act)
    assert (repo / sibling).is_symlink()


def test_fetch_off_and_cli_inputs_treat_a_symlinked_corpus_file_as_absent(
    tmp_path: Path, monkeypatch
) -> None:
    import argparse

    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    resolver.ensure_scopes([SCOPE])
    (repo / PROV).unlink()
    (repo / PROV).symlink_to(resolver.cache.object_path(_sha(READABLE_FILES[PROV])))
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="absent and fetching is off"):
        resolver_module.ensure_corpus_scopes([SCOPE], repo=repo)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    args = argparse.Namespace(base=repo / "data/corpus", provisions=repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match="symlink"):
        resolver_module.materialize_cli_inputs(args, repo=repo)
    assert (repo / PROV).is_symlink()


_TAIL_SEGMENT = st.sampled_from(["a", "B", "x.jsonl", "s 2.xml", "2026-07-10"])
_LINK_KINDS = (None, "dangling", "file inside", "file outside", "directory inside", "directory into corpus")
_FILE_LINKS = frozenset({"dangling", "file inside", "file outside"})
# Where a directory link above the path leads: the same subtree outside every
# checkout, nowhere, under an unprotected directory of this checkout, the same
# place in another checkout (the sharing layout), or the same place in another
# checkout that is itself a link to a subtree outside every checkout.
_ABOVE_KINDS = (None, "outside", "dangling", "unprotected inside", "another checkout", "chain via another checkout")


@st.composite
def _named_paths(draw):
    prefix = draw(
        st.sampled_from(
            [
                "data/corpus/provisions/nz/statute",
                "data/corpus/sources/nz/statute/v1/official",
                "data/corpus/manifests",
                "docs",
            ]
        )
    )
    tail = draw(st.lists(_TAIL_SEGMENT, min_size=1, max_size=3))
    rel = "/".join([prefix, *tail])
    above = draw(st.sampled_from(_ABOVE_KINDS))
    # The linked ancestor lies below data/corpus, so COVERAGE (the "file
    # inside" target) stays a plain file of the checkout.
    lowest = len(CORPUS_BASE.split("/")) if rel.startswith(f"{CORPUS_BASE}/") else 0
    depth = draw(st.integers(lowest, rel.count("/") - 1)) if above is not None else None
    if above == "dangling":  # nothing can be made below a dangling link
        return rel, None, False, above, depth
    return rel, draw(st.sampled_from(_LINK_KINDS)), draw(st.booleans()), above, depth


def _expected_naming(rel: str, link_kind: str | None, above: str | None):
    """Reference model of invariant 10 for ``repo/<rel>`` in the layouts above.

    Returns what ``repo`` and ``other`` name the path, what they name its
    realpath, and whether a name is the symlinked file itself (lstat identity).
    A place is (checkout, name); the path stands at a place below each link on
    its way and reaches a place at its end. It names, in order of precedence:
    the last protected place a symlinked file stands at; the protected place
    any other path reaches, when it stands at no protected place or the last
    one has the same name (a link to the same path in another checkout); the
    last protected place it stands at; the place it reaches.
    """
    home = {
        None: ("repo", rel),
        "outside": None,
        "dangling": None,
        "unprotected inside": ("repo", f"scratch/{rel}"),
        "another checkout": ("other", rel),
        "chain via another checkout": None,
    }[above]
    reached = {
        None: home,
        "directory inside": ("repo", "plain"),
        "directory into corpus": ("repo", posixpath.dirname(COVERAGE)),
        "file inside": ("repo", COVERAGE),
        "file outside": None,
        "dangling": None,
    }[link_kind]
    stands = [("repo", rel)] if above is not None else []
    if above == "chain via another checkout":
        stands.append(("other", rel))
    if link_kind is not None and home is not None:
        stands.append(home)
    stands = [place for place in stands if is_protected_corpus_path(place[1])]
    file_link = link_kind in _FILE_LINKS
    followed = not stands or stands[-1][1] == (reached or ("", ""))[1]  # the same path elsewhere
    if not file_link and reached is not None and is_protected_corpus_path(reached[1]) and followed:
        owner = reached
    else:
        owner = stands[-1] if stands else None
    physical = dict.fromkeys(("repo", "other"))
    if reached is not None:
        physical[reached[0]] = reached[1]
    named = dict.fromkeys(("repo", "other"))
    if owner is not None:
        named[owner[0]] = owner[1]
    else:
        named.update(physical)
    return named, physical, file_link and owner is not None


def _bare_checkout(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "src" / "axiom_corpus").mkdir(parents=True)
    _git(path, "init", "-q")
    return path


@PROPERTY_SETTINGS
@given(_named_paths())
def test_every_spelling_names_the_entry_it_reaches(tmp_path_factory, drawn) -> None:
    """Invariant 10. ``relative`` answers the same for every spelling of the checkout,
    at most one checkout names a path at a protected path, a name reaches the
    directory entry the path reaches (the link itself for a symlinked file standing
    at a protected path), and the name follows the reference model: a directory link
    to the same path in another checkout is followed, and any other link at a
    protected path, a symlinked file included, names its own path."""
    rel, link_kind, create, above, depth = drawn
    base = tmp_path_factory.mktemp("naming")
    repo, other = _bare_checkout(base / "repo"), _bare_checkout(base / "other")
    (repo / "plain").mkdir()  # "directory inside" leads here, never through a link
    _write(repo, COVERAGE, b"{}")
    _write(base, "outside.bin", b"x")
    if above is not None:
        ancestor = "/".join(rel.split("/")[: depth + 1])
        target = {
            "outside": base / "outside" / ancestor,
            "dangling": base / "gone" / ancestor,
            "unprotected inside": repo / "scratch" / ancestor,
            "another checkout": other / ancestor,
            "chain via another checkout": other / ancestor,
        }[above]
        if above == "chain via another checkout":
            (base / "outside" / ancestor).mkdir(parents=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(base / "outside" / ancestor, target_is_directory=True)
        elif above != "dangling":
            target.mkdir(parents=True)
        (repo / ancestor).parent.mkdir(parents=True, exist_ok=True)
        (repo / ancestor).symlink_to(target, target_is_directory=True)
    path = repo / rel
    if create or link_kind is not None:
        path.parent.mkdir(parents=True, exist_ok=True)  # beneath any link above
    if link_kind is None and create:
        path.write_bytes(b"x")
    elif link_kind == "dangling":
        path.symlink_to(base / "nowhere")
    elif link_kind == "file inside":
        path.symlink_to(repo / COVERAGE)
    elif link_kind == "file outside":
        path.symlink_to(base / "outside.bin")
    elif link_kind == "directory inside":
        path.symlink_to(repo / "plain", target_is_directory=True)
    elif link_kind == "directory into corpus":
        path.symlink_to(repo / posixpath.dirname(COVERAGE), target_is_directory=True)
    expected, physical, link_itself = _expected_naming(rel, link_kind, above)
    resolvers = {"repo": CorpusResolver(repo, sources=[]), "other": CorpusResolver(other, sources=[])}
    named = {name: resolver.relative(path) for name, resolver in resolvers.items()}

    assert named == expected
    assert sum(is_protected_corpus_path(n) for n in named.values() if n is not None) <= 1
    spellings = [repo, *_checkout_spellings(repo).values()]
    for name, resolver in resolvers.items():
        for spelling in spellings:
            assert resolver.relative(spelling / rel) == named[name], spelling
        with contextlib.chdir(base):
            assert resolver.relative(Path("repo") / rel) == named[name]
        # A symlink-free path names itself: a path and its realpath name one
        # file wherever the path neither is nor stands below such a link.
        assert resolver.relative(os.path.realpath(path)) == physical[name]
    resolver = resolvers["repo"]
    if rel.startswith(f"{CORPUS_BASE}/"):
        parts = rel.split("/")
        # A `..` straight after the class directory: below the link when the
        # link is that directory. The targets above mirror the checkout's
        # layout, so it still reaches the path's own entry.
        dotted = "/".join([*parts[:3], "..", *parts[2:]])
        assert resolver.relative(repo / dotted) == named["repo"]
        assert resolver.relative(dotted) == named["repo"]  # bare: `..` resolves through the checkout
        if named["repo"] == rel:
            assert resolver.relative(rel) == rel  # bare: as written
    for name, checkout in (("repo", repo), ("other", other)):
        if named[name] is not None and os.path.lexists(path):
            probe = os.lstat if link_itself else os.stat
            for spelling in spellings:
                assert os.path.samestat(probe(spelling / rel), probe(checkout / named[name]))
