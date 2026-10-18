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
    link to a place no lock guards, is named, and refused, as itself; a
    spelling of a locked path names the locked file exactly where the
    filesystem stores both in one place, fetched or not);
11. every lock that applies (through a link to another checkout, the checkout
    that names a path fetches it, and any other lock that applies refuses a
    file it names that no fetch places).
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
from hypothesis import HealthCheck, event, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import corpus_cli
from axiom_corpus.corpus import corpus_locks as corpus_locks_module
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
    looks_up_case_insensitively,
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
    InvalidCorpusLocksError,
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
@given(st.text(alphabet=st.characters(max_codepoint=127), max_size=40))
def test_fold_path_lowercases_ascii_exactly_as_the_full_fold_does(text: str) -> None:
    """``fold_path``'s ASCII shortcut agrees with the full Unicode fold."""
    from axiom_corpus.corpus.corpus_locks import _fold_unicode, fold_path

    assert fold_path(text) == _fold_unicode(text) == text.lower()


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


# Locked spellings: a spelling the filesystem stores where a locked file belongs.

def _folds_case_on_disk(directory: Path) -> bool:
    """Ground truth, by writing a file: does ``directory`` find it in another case?"""
    probe = directory / "case-probe"
    probe.write_bytes(b"")
    try:
        return (directory / "CASE-PROBE").exists()
    finally:
        probe.unlink()


CASE_VARIANTS = [
    PROV.replace("data/", "DATA/", 1),  # the #876 review's spelling
    PROV.replace("/provisions/", "/PROVISIONS/", 1),
    PROV.replace("/nz/", "/NZ/", 1),
    PROV.replace(".jsonl", ".JSONL"),
]


@pytest.mark.parametrize("fetched_beside", [False, True])
@pytest.mark.parametrize("variant", CASE_VARIANTS)
def test_another_case_of_an_absent_locked_file_is_that_file_where_case_folds(
    tmp_path: Path, monkeypatch, variant: str, fetched_beside: bool
) -> None:
    """#876 review (2026-10-14): on APFS ``DATA/corpus/provisions/...`` names the
    locked file's place, but no lock named that spelling, so an unfetched scope
    loaded as empty, require_materialized passed it, and fetch skipped it."""
    if not _folds_case_on_disk(tmp_path):
        pytest.skip("needs a case-insensitive filesystem")
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    if fetched_beside:  # data/corpus exists: some components are found, some probed
        resolver.ensure_paths([COVERAGE])
    spelled = repo / variant
    assert resolver.locks.locked_spelling(repo, variant) == PROV
    assert resolver.entries_for_paths([spelled]) == resolver.entries_for_paths([PROV])
    directory = variant.rsplit("/", 1)[0]
    assert resolver.locks.missing_under(repo, directory) == [resolver.locks.by_path[PROV]]

    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match=f"{PROV} is locked but absent"):
        load_provisions(spelled)
    with pytest.raises(CorpusNotMaterializedError, match=f"fetch --path {PROV}"):
        require_materialized([spelled], repo=repo)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([repo / directory], repo=repo)
    with pytest.raises(CorpusNotMaterializedError, match="absent and fetching is off"):
        resolve_corpus_path(spelled, repo=repo)
    assert not (repo / PROV).exists()

    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert load_provisions(spelled)[0].citation_path == "nz/statute/a"
    assert _placed_regular(repo, PROV)
    (repo / PROV).unlink()
    assert fetch_locked_file(spelled) and _placed_regular(repo, PROV)
    (repo / PROV).unlink()
    assert resolve_corpus_path(spelled, repo=repo).read_bytes() == READABLE_FILES[PROV]
    (repo / PROV).unlink()
    require_materialized([repo / directory], repo=repo, fetch=True)
    assert _placed_regular(repo, PROV)


@pytest.mark.parametrize("variant", CASE_VARIANTS)
def test_another_case_names_another_unlocked_file_where_case_is_kept(
    tmp_path: Path, monkeypatch, variant: str
) -> None:
    """On a case-sensitive filesystem the variant is a different path that no
    lock names: it reads as before and fetches nothing."""
    if _folds_case_on_disk(tmp_path):
        pytest.skip("needs a case-sensitive filesystem")
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    spelled = repo / variant
    assert resolver.locks.locked_spelling(repo, variant) == variant
    assert resolver.entries_for_paths([spelled]) == []
    assert not fetch_locked_file(spelled)
    assert load_provisions(spelled) == ()
    require_materialized([spelled], repo=repo)
    if not PROV.startswith(f"{variant.rsplit('/', 1)[0]}/"):  # the directory is respelled too
        require_materialized([spelled.parent], repo=repo)
    assert not (repo / PROV).exists()
    # Present side by side, each spelling names its own file.
    resolver.ensure_paths([PROV])
    other_row = {**PROV_ROW, "citation_path": "nz/statute/b"}
    _write(repo, variant, (json.dumps(other_row) + "\n").encode())
    assert resolver.locks.locked_spelling(repo, variant) == variant
    assert load_provisions(spelled)[0].citation_path == "nz/statute/b"
    assert _placed_regular(repo, PROV)


def test_hard_links_in_another_case_are_two_names_not_one(tmp_path: Path, monkeypatch) -> None:
    """On a case-sensitive filesystem a file hard-linked under another case reaches
    one inode through both names. Neither the probe nor the identity check may
    take that for a filesystem that folds case."""
    if _folds_case_on_disk(tmp_path):
        pytest.skip("needs a case-sensitive filesystem")
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "a").write_bytes(b"")
    os.link(probe / "a", probe / "A")
    assert not looks_up_case_insensitively(probe)
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    resolver.ensure_paths([PROV])
    variant = PROV.replace(".jsonl", ".JSONL")
    os.link(repo / PROV, repo / variant)
    assert resolver.locks.locked_spelling(repo, variant) == variant


def test_cli_inputs_take_another_case_of_corpus_paths_and_the_base(tmp_path: Path, monkeypatch) -> None:
    """The CLI names inputs, and corpus-wide reports require whole trees, under
    every spelling the filesystem stores in the corpus's place."""
    import argparse
    import importlib.util

    from axiom_corpus.corpus.cli import _corpus_wide_prefixes, build_parser

    folds = _folds_case_on_disk(tmp_path)
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    monkeypatch.chdir(repo)
    variant = PROV.replace("data/", "DATA/", 1)
    args = argparse.Namespace(
        base=Path("DATA/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version="2026-07-10",
        provisions=Path(variant),
    )
    paths, scopes, _selectors = corpus_inputs_from_args(args, repo=repo)
    assert paths == [variant]  # named as given; the locks decide what it names
    assert scopes == ([SCOPE] if folds else [])
    resolver_module.materialize_cli_inputs(args, repo=repo, include_scope=True)
    assert all(_placed_regular(repo, rel) for rel in READABLE_FILES) is folds
    assert (repo / PROV).exists() is folds

    report = build_parser().parse_args(["artifact-report", "--base", "DATA/corpus", "--version", "v1"])
    prefixes = {p.relative_to(repo).as_posix() for p in _corpus_wide_prefixes(report, "artifact-report")}
    kinds = ("sources", "inventory", "provisions", "coverage")
    assert prefixes == ({f"data/corpus/{kind}" for kind in kinds} if folds else set())

    locks = load_locks(repo)
    select = {"scopes": [], "select_all": False, "paths": ["DATA/corpus/provisions"]}
    if folds:  # `corpus fetch --path DATA/corpus/provisions`
        assert corpus_cli._selected_entries(repo, locks, **select) == [locks.by_path[PROV]]
    else:
        with pytest.raises(SystemExit):
            corpus_cli._selected_entries(repo, locks, **select)
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_us_release_publishability.py"
    spec = importlib.util.spec_from_file_location("audit_us_release_publishability", script)
    assert spec is not None and spec.loader is not None
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    assert audit._locked_under(repo, repo / variant) is folds


def test_corpus_status_counts_a_file_stored_in_another_case_as_the_locked_one(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """r1 review note: on APFS a locked file an extractor wrote as ``.JSONL`` was
    both present (under its locked name) and unlocked (under its own)."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    variant = PROV.replace(".jsonl", ".JSONL")
    _write(repo, variant, READABLE_FILES[PROV])
    capsys.readouterr()
    cli_main(["corpus", "status", "--repo", str(repo), "--json"])
    payload = json.loads(capsys.readouterr().out)
    if _folds_case_on_disk(tmp_path):
        assert payload["unlocked_paths"] == [] and payload["present"] == 1
    else:  # another file, which no lock names
        assert payload["unlocked_paths"] == [variant] and payload["present"] == 0


def test_resolve_never_returns_a_spelling_the_filesystem_keeps_apart(tmp_path: Path, monkeypatch) -> None:
    """Were a filesystem's comparison of names misjudged (one that compares them
    differently from APFS), the spelling would be fetched as the locked file but
    still not reach it; resolve refuses rather than return a path that does not
    exist."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    monkeypatch.setattr(corpus_locks_module, "stored_together", lambda *_args: True)
    variant = COVERAGE.replace(".json", "\u200c.json")  # a zero-width non-joiner: another name
    with pytest.raises(CorpusNotMaterializedError, match="keeps it apart from the locked"):
        resolve_corpus_path(repo / variant, repo=repo)
    assert _placed_regular(repo, COVERAGE) and not (repo / variant).exists()
    assert not fetch_locked_file(repo / variant)


# One character's respellings beyond ASCII case. fold_path merges each with the
# original; only some of them name the same place on a case-insensitive APFS.
_RESPELLINGS = {
    "s": ("S", "\u017f"),  # long s: APFS folds it to s
    "k": ("K", "\u212a"),  # Kelvin sign: folds to k
    "K": ("k", "\u212a"),  # Kelvin sign: also canonically equivalent to K
    "i": ("I", "\u0131"),  # dotless i: APFS keeps it apart
    "a": ("A", "\uff41"),  # fullwidth a: APFS keeps it apart
    "\u00e9": ("\u00c9", "e\u0301"),  # e acute: capital, and decomposed
}
KISS = "data/corpus/sources/nz/statute/2026-07-10/official/Kiss caf\u00e9.html"
# Alpha, combining square below, iota (NFC). Case-insensitive APFS also stores
# capital alpha with prosgegrammeni plus the mark there, which fold_path keys
# apart (the iota lands before the mark): review r1, finding 2.
GREEK_DIR = "\u03b1\u033b\u03b9"
GREEK = f"data/corpus/sources/nz/statute/2026-07-10/{GREEK_DIR}/official.jsonl"
GREEK_ALTERNATES = ("\u1fbc\u033b", "\u1fb3\u033b")  # capital, and small, with the iota subscript
SPELLING_FILES = {PROV: READABLE_FILES[PROV], KISS: b"<html/>", GREEK: READABLE_FILES[PROV]}


def _respell(draw, name: str) -> str:
    """One edit that fold_path ignores and a filesystem may or may not."""
    kind = draw(st.sampled_from(["character", "character", "upper", "sharp s", "zero-width"]))
    if kind == "upper":
        return name.upper()
    if kind == "sharp s" and "ss" in name:
        return name.replace("ss", "\u00df", 1)  # sharp s: APFS folds it to ss
    if kind == "zero-width":  # a zero-width non-joiner: APFS keeps it apart
        cut = draw(st.integers(0, len(name)))
        return name[:cut] + "\u200c" + name[cut:]
    if GREEK_DIR in name and draw(st.booleans()):
        return name.replace(GREEK_DIR, draw(st.sampled_from(GREEK_ALTERNATES)))
    spots = [i for i, ch in enumerate(name) if ch in _RESPELLINGS or (ch.isascii() and ch.isalpha())]
    if not spots:
        return name
    index = draw(st.sampled_from(spots))
    options = _RESPELLINGS.get(name[index], (name[index].swapcase(),))
    return name[:index] + draw(st.sampled_from(options)) + name[index + 1 :]


@st.composite
def _respelled_locked_names(draw):
    full = draw(st.sampled_from(sorted(SPELLING_FILES)))
    parts = full.split("/")
    depth = draw(st.integers(1, len(parts)))  # the file, or a directory above it
    spelled = parts[:depth]
    # A few edits in one or two components, so single foldings get tested alone.
    for index in draw(st.lists(st.integers(0, depth - 1), max_size=2, unique=True)):
        for _ in range(draw(st.integers(1, 2))):
            spelled[index] = _respell(draw, spelled[index])
    present = draw(st.integers(0, len(parts)))  # how much of the locked path exists already
    return full, "/".join(parts[:depth]), "/".join(spelled), present


@settings(PROPERTY_SETTINGS, max_examples=200)
@given(_respelled_locked_names())
# The review's spelling, before anything is fetched and after.
@example((PROV, PROV, PROV.replace("data/", "DATA/", 1), 0))
@example((PROV, PROV, PROV.replace("data/", "DATA/", 1), 6))
# Canonical equivalents (decomposed e acute, the Kelvin sign for K): one place
# on APFS of either kind, two on ext4.
@example((KISS, KISS, KISS.replace("\u00e9", "e\u0301"), 0))
@example((KISS, KISS, KISS.replace("\u00e9", "e\u0301"), 8))
@example((KISS, KISS, KISS.replace("Kiss", "\u212aiss"), 0))
@example((KISS, KISS, KISS.replace("Kiss", "\u212aiss"), 8))
# Merged by fold_path, never by APFS: a zero-width non-joiner, a dotless i.
@example((KISS, KISS, KISS.replace("Kiss", "Ki\u200css"), 0))
@example((KISS, KISS, KISS.replace("Kiss", "K\u0131ss"), 8))
# Merged by APFS, keyed apart by fold_path: the iota subscript before a mark.
@example((GREEK, GREEK, GREEK.replace(GREEK_DIR, GREEK_ALTERNATES[0]), 0))
@example((GREEK, GREEK, GREEK.replace(GREEK_DIR, GREEK_ALTERNATES[1]), 8))
@example((GREEK, GREEK.rsplit("/", 1)[0], GREEK.rsplit("/", 1)[0].replace(GREEK_DIR, GREEK_ALTERNATES[0]), 6))
def test_a_spelling_names_a_locked_file_exactly_where_the_filesystem_puts_both(
    tmp_path_factory, drawn
) -> None:
    """Invariant 10, locked spellings. Asked before the file exists (or with part of
    its path in place), ``locked_spelling`` maps a respelled locked path or
    directory onto it exactly when the filesystem, once the file is there,
    reaches the same entry through both spellings; ``missing_under`` follows."""
    full, canonical, spelled, present = drawn
    repo = tmp_path_factory.mktemp("spelling")
    (repo / "docs").mkdir()
    locks = LockSet({SCOPE: _scope_lock(SPELLING_FILES)})
    parts = full.split("/")
    if present == len(parts):
        _write(repo, full, SPELLING_FILES[full])
    elif present:
        (repo / "/".join(parts[:present])).mkdir(parents=True)

    named = locks.locked_spelling(repo, spelled)
    missing = locks.missing_under(repo, spelled)
    expected_missing = locks.missing_under(repo, canonical)
    folds_case = looks_up_case_insensitively(repo)

    if not (repo / full).exists():
        _write(repo, full, SPELLING_FILES[full])
    try:
        together = os.path.samestat(os.lstat(repo / spelled), os.lstat(repo / canonical))
    except FileNotFoundError:
        together = False
    assert folds_case == _folds_case_on_disk(repo)
    differs = [i for i, pair in enumerate(zip(spelled.split("/"), parts, strict=False)) if len(set(pair)) > 1]
    decided_by = "entry" if differs and present > differs[0] else "probe" if differs else "none"
    event(f"together={together} folds_case={folds_case} decided by {decided_by}")
    if named == (canonical if together else spelled):
        assert missing == (expected_missing if together else [])
        return
    event("intended: canonical equivalents on a case-sensitive filesystem")
    # Intended: a case-sensitive filesystem that still merges canonically
    # equivalent names (case-sensitive APFS) is taken to keep apart names
    # neither of which exists yet. CI's ext4 and case-insensitive APFS do not
    # reach this.
    assert decided_by == "probe" and together and not folds_case and named == spelled
    assert unicodedata.normalize("NFD", spelled) == unicodedata.normalize("NFD", canonical)


def test_a_directory_alias_keeps_the_whole_sources_directory_required(tmp_path: Path, monkeypatch) -> None:
    """r1 finding 1: a separate symlink to a scope's sources directory under a name
    fold_path merges with it (a fullwidth o) reached the locked file, but the
    component check compared the link itself with the directory, so the source
    read as unlocked and its absent sibling was never required."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    official = "data/corpus/sources/nz/statute/2026-07-10/official"
    alias = official.replace("/official", "/\uff4ffficial")
    act = f"{official}/act.html"
    resolver = resolver_module.resolver_for(repo)
    assert resolver is not None
    resolver.ensure_paths([act])
    (repo / f"{official}/sub dir/s 2.xml").unlink()
    (repo / alias).symlink_to("official", target_is_directory=True)
    spelled_act = act.replace(official, alias)
    assert os.path.samefile(repo / spelled_act, repo / act)
    assert resolver.locks.locked_spelling(repo, spelled_act) == act
    assert resolver.locks.locked_spelling(repo, alias) == official
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="absent and fetching is off"):
        CorpusResolver(repo, cache=resolver.cache, sources=[]).resolve(spelled_act)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([alias], repo=repo)
    # A symlinked file under such a name is still its own entry, never its target.
    (repo / f"{official}/\uff41ct.html").symlink_to("act.html")
    assert resolver.locks.locked_spelling(repo, f"{official}/\uff41ct.html") == f"{official}/\uff41ct.html"


@pytest.mark.parametrize("change", ["replaced", "removed, then made again"])
def test_the_case_probe_never_classifies_a_name_that_changed_under_it(
    tmp_path: Path, monkeypatch, change: str
) -> None:
    """r1 finding 3: replacing the sampled name between the probe's two lookups
    gave it a new inode, which read as a case-sensitive filesystem, so on APFS
    an absent locked file in another case loaded as empty."""
    sample = tmp_path / "Probe"
    sample.write_bytes(b"old")
    truth = _folds_case_on_disk(tmp_path)
    assert corpus_locks_module._case_probe(tmp_path, "Probe") is truth
    real_lstat = os.lstat

    def interleaved(path, *args, **kwargs):
        if Path(path) == tmp_path / "pROBE":
            (tmp_path / "next").write_bytes(b"new")  # a new inode, whatever the filesystem reuses
            if change == "replaced":
                os.replace(tmp_path / "next", sample)
            else:
                sample.unlink()
                os.rename(tmp_path / "next", sample)
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", interleaved)
    answer = corpus_locks_module._case_probe(tmp_path, "Probe")
    monkeypatch.setattr(os, "lstat", real_lstat)
    assert answer is None  # left open: the next name decides
    assert looks_up_case_insensitively(tmp_path) is truth


# --------------------------------------------------------------------------- divergent locks
#
# The sharing layout: a worktree links a protected directory to the same path
# in another checkout (invariant 10 names the path there), and the two
# checkouts' locks differ. Every lock that applies decides (invariant 11).

US_PROV = "data/corpus/provisions/us/statute/2026-07-10.jsonl"
US_SCOPE = ("us", "statute", "2026-07-10")
SHARED_FILES = {
    PROV: READABLE_FILES[PROV],
    US_PROV: (json.dumps({**PROV_ROW, "jurisdiction": "us", "citation_path": "us/statute/a"}) + "\n").encode(),
}


def _lock_files(repo: Path, files: dict[str, bytes]) -> None:
    """Write one lock per scope, naming ``files``."""
    by_scope: dict[tuple[str, str, str], dict[str, bytes]] = {}
    for rel, data in files.items():
        scope = scope_for_path(rel)
        assert scope is not None, rel
        by_scope.setdefault(scope, {})[rel] = data
    for scope, scoped in by_scope.items():
        write_lock(repo, _scope_lock(scoped, scope=scope))


def _sharing(
    tmp_path: Path,
    monkeypatch,
    *,
    worktree_locks: dict[str, bytes],
    shared_locks: dict[str, bytes],
    link: str = "data/corpus/provisions",
    every_file: dict[str, bytes] = SHARED_FILES,
    dangling: bool = False,
) -> tuple[Path, Path]:
    """A worktree whose ``link`` leads to the same path in a shared checkout (not
    made yet, if ``dangling``). Each checkout locks the files given; an
    in-memory R2 serves every file."""
    shared = _init_repo(tmp_path / "shared")
    worktree = _init_repo(tmp_path / "worktree")
    _lock_files(worktree, worktree_locks)
    _lock_files(shared, shared_locks)
    if not dangling:
        (shared / link).mkdir(parents=True)
    (worktree / link).parent.mkdir(parents=True, exist_ok=True)
    (worktree / link).symlink_to(shared / link, target_is_directory=True)
    remote, _fake = _remote({content_key(_sha(d)): d for d in every_file.values()})
    monkeypatch.setattr(R2ObjectStore, "from_environment", classmethod(lambda cls, **_kwargs: remote))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    monkeypatch.setattr(resolver_module, "_WITNESSED_SOURCE_DIRS", set(), raising=False)
    monkeypatch.chdir(worktree)
    return worktree, shared


def _selection(worktree: Path, how: str, rel: str) -> Path:
    return {
        "the file": worktree / rel,
        "the file, bare": Path(rel),
        "the linked directory": worktree / "data/corpus/provisions",
        "a directory above the link": worktree / "data/corpus",
    }[how]


_SELECTIONS = ("the file", "the file, bare", "the linked directory", "a directory above the link")


def _unfetchable(rel: str, holder: str, owner: str) -> str:
    return (
        rf"absent and no fetch will place them \(first: {rel}, which the lock of \S*/{holder} names; "
        rf"it reads through the symlink \S*/{holder}/\S* -> \S*\)\. \S*/{owner} names that path, and its "
        rf"lock, which decides what is fetched there, does not list {rel}"
    )


@pytest.mark.parametrize("how", _SELECTIONS)
@pytest.mark.parametrize("with_repo", [False, True])
@pytest.mark.parametrize("shared_has_locks", [True, False])
def test_a_file_only_the_worktrees_lock_names_is_refused_through_a_sharing_link(
    tmp_path: Path, monkeypatch, how: str, with_repo: bool, shared_has_locks: bool
) -> None:
    """The limit #881 left open, first direction: sharing worktrees' locks can
    name files their shared checkout's lock does not. Only the shared
    checkout's lock was read, so a file only the worktree's lock names was never
    fetched and read as an empty scope; with ``repo`` given, every helper passed
    over the path. Every helper now refuses it, from any selection, and writes
    nothing; once the file is in place it reads as before."""
    worktree, shared = _sharing(
        tmp_path,
        monkeypatch,
        worktree_locks=SHARED_FILES,
        shared_locks={PROV: SHARED_FILES[PROV]} if shared_has_locks else {},
    )
    _write(shared, PROV, SHARED_FILES[PROV])
    selection = _selection(worktree, how, US_PROV)
    kwargs = {"repo": worktree} if with_repo else {}
    refused = _unfetchable(US_PROV, "worktree", "shared")
    for fetch_off in (False, True):
        if fetch_off:
            monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
        for fetch in (False, True):
            with pytest.raises(CorpusNotMaterializedError, match=refused):
                require_materialized([selection], fetch=fetch, **kwargs)
        with pytest.raises(CorpusNotMaterializedError, match=refused):
            ensure_corpus_paths([selection], **kwargs)
        if how.startswith("the file"):
            with pytest.raises(CorpusNotMaterializedError, match=refused):
                load_provisions(selection)
            with pytest.raises(CorpusNotMaterializedError, match=refused):
                fetch_locked_file(selection)
            with pytest.raises(CorpusNotMaterializedError, match=refused):
                resolve_corpus_path(selection, **kwargs)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert _tree(shared / "data/corpus/provisions") == ["nz", "nz/statute", "nz/statute/2026-07-10.jsonl"]
    assert _tree(worktree / "data/corpus") == ["provisions"]

    # In place (the shared checkout holds it unlocked), it reads as before.
    _write(shared, US_PROV, SHARED_FILES[US_PROV])
    assert load_provisions(worktree / US_PROV)[0].citation_path == "us/statute/a"
    require_materialized([selection], **kwargs)
    ensure_corpus_paths([selection], **kwargs)
    if how.startswith("the file"):
        assert os.path.samefile(resolve_corpus_path(selection, **kwargs), selection)


@pytest.mark.parametrize("how", _SELECTIONS)
@pytest.mark.parametrize("with_repo", [False, True])
def test_a_file_only_the_shared_checkouts_lock_names_is_fetched_there_from_any_selection(
    tmp_path: Path, monkeypatch, how: str, with_repo: bool
) -> None:
    """The second direction (review r2c of #881): the shared checkout's lock names an
    absent file the worktree's lock does not. ``require_materialized`` over
    ``worktree/data/corpus`` read the worktree's lock alone and passed, while over
    ``worktree/data/corpus/provisions`` it raised: two selections of the same files
    gave opposite answers. A selection above the link now reads the shared lock
    for the part below the link, so every selection refuses the absent file and
    fetches it into the shared checkout."""
    worktree, shared = _sharing(
        tmp_path, monkeypatch, worktree_locks={PROV: SHARED_FILES[PROV]}, shared_locks=SHARED_FILES
    )
    _write(shared, PROV, SHARED_FILES[PROV])
    selection = _selection(worktree, how, US_PROV)
    kwargs = {"repo": worktree} if with_repo else {}
    absent = rf"not in this checkout \(first: {US_PROV}\).*corpus fetch --path \S+` in \S*/shared first"
    with pytest.raises(CorpusNotMaterializedError, match=absent):
        require_materialized([selection], **kwargs)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    for fetch in (False, True):
        with pytest.raises(CorpusNotMaterializedError, match=absent):
            require_materialized([selection], fetch=fetch, **kwargs)
    with pytest.raises(CorpusNotMaterializedError, match=absent):
        ensure_corpus_paths([selection], **kwargs)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert not (shared / US_PROV).exists()

    if how.startswith("the file"):
        assert load_provisions(selection)[0].citation_path == "us/statute/a"
    else:
        report = ensure_corpus_paths([selection], **kwargs)
        assert report.materialized == [US_PROV] and report.present == [PROV]
    target = shared / US_PROV
    assert target.is_file() and not target.is_symlink() and target.read_bytes() == SHARED_FILES[US_PROV]
    assert _tree(worktree / "data/corpus") == ["provisions"]
    require_materialized([selection], **kwargs)


@pytest.mark.parametrize("how", ["the linked directory", "a directory above the link", "the file"])
def test_a_dangling_sharing_link_is_the_shared_checkouts_directory_not_made_yet(
    tmp_path: Path, monkeypatch, how: str
) -> None:
    """The shared checkout has not made ``data/corpus/provisions`` yet, so the
    worktree's link dangles. The link's own path names itself (a symlinked file,
    invariant 10), but every path below it is the shared checkout's, so a
    selection of the link, or above it, fetches the files below into the shared
    checkout as a selection of a file below does; it did refuse them as files no
    fetch places."""
    worktree, shared = _sharing(
        tmp_path, monkeypatch, worktree_locks=SHARED_FILES, shared_locks=SHARED_FILES, dangling=True
    )
    assert not os.path.exists(worktree / "data/corpus/provisions")
    selection = _selection(worktree, how, PROV)
    with pytest.raises(CorpusNotMaterializedError, match=r"not in this checkout .* in \S*/shared first"):
        require_materialized([selection])
    require_materialized([selection], fetch=True)
    assert (shared / PROV).read_bytes() == SHARED_FILES[PROV]
    if how != "the file":
        assert (shared / US_PROV).read_bytes() == SHARED_FILES[US_PROV]
    assert _tree(worktree / "data/corpus") == ["provisions"]


def test_a_file_both_locks_name_is_fetched_into_the_shared_checkout(tmp_path: Path, monkeypatch) -> None:
    """Where both locks name a file, the shared checkout's lock fetches it, and the
    worktree's lock then finds it in place."""
    worktree, shared = _sharing(tmp_path, monkeypatch, worktree_locks=SHARED_FILES, shared_locks=SHARED_FILES)
    report = ensure_corpus_paths([worktree / "data/corpus"])
    assert sorted(report.materialized) == sorted(SHARED_FILES)
    assert all((shared / rel).read_bytes() == data for rel, data in SHARED_FILES.items())
    assert _tree(worktree / "data/corpus") == ["provisions"]
    require_materialized([worktree / "data/corpus"], repo=worktree)


@pytest.mark.parametrize(
    ("worktree_locks_it", "third_locks_it"), [(False, True), (True, False), (True, True)]
)
def test_a_selection_above_a_chain_of_sharing_links_reads_every_lock_on_it(
    tmp_path: Path, monkeypatch, worktree_locks_it: bool, third_locks_it: bool
) -> None:
    """The worktree shares the shared checkout's provisions, whose ``us`` is itself
    shared from a third checkout. A selection above both links reads the third
    checkout's lock for ``us`` (the walk follows the first link's target), fetches
    into the third checkout what its lock names, and refuses what only the
    worktree's lock names."""
    worktree, shared = _sharing(
        tmp_path,
        monkeypatch,
        worktree_locks=SHARED_FILES if worktree_locks_it else {PROV: SHARED_FILES[PROV]},
        shared_locks={PROV: SHARED_FILES[PROV]},
    )
    _write(shared, PROV, SHARED_FILES[PROV])
    third = _init_repo(tmp_path / "third")
    _lock_files(third, {US_PROV: SHARED_FILES[US_PROV]} if third_locks_it else {})
    (third / "data/corpus/provisions/us").mkdir(parents=True)
    (shared / "data/corpus/provisions/us").symlink_to(third / "data/corpus/provisions/us", target_is_directory=True)
    holder = resolver_module._checkout_for(worktree / US_PROV)
    assert holder is not None and os.path.samefile(holder, third)
    for selection in (worktree / "data/corpus", worktree / "data/corpus/provisions", worktree / US_PROV):
        if third_locks_it:
            with pytest.raises(CorpusNotMaterializedError, match=r"in \S*/third first"):
                require_materialized([selection])
        else:
            with pytest.raises(CorpusNotMaterializedError, match=_unfetchable(US_PROV, "worktree", "third")):
                require_materialized([selection], fetch=True)
    if third_locks_it:
        require_materialized([worktree / "data/corpus"], fetch=True)
        assert (third / US_PROV).read_bytes() == SHARED_FILES[US_PROV]
    else:
        assert _tree(third / "data/corpus/provisions/us") == []
    assert _tree(worktree / "data/corpus") == ["provisions"]


def test_a_directory_link_to_another_corpus_path_reads_that_paths_lock_too(tmp_path: Path, monkeypatch) -> None:
    """``provisions/nz`` links to ``provisions/us`` of the same checkout (named, by
    invariant 10, as ``nz``). The checkout's lock names the ``us`` file the path
    reads, not the ``nz`` one, so the absent file read as an empty scope. The
    lock of the place a path reaches applies too."""
    repo = _init_repo(tmp_path / "repo")
    _lock_files(repo, {US_PROV: SHARED_FILES[US_PROV]})
    (repo / "data/corpus/provisions/us/statute").mkdir(parents=True)
    (repo / "data/corpus/provisions/nz").symlink_to(repo / "data/corpus/provisions/us", target_is_directory=True)
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    assert CorpusResolver(repo, sources=[]).relative(repo / PROV) == PROV
    reached = rf"first: {US_PROV}, which the lock of \S*/repo names\)\. .*run `axiom-corpus-ingest corpus fetch --path {US_PROV}` in \S*/repo"
    with pytest.raises(CorpusNotMaterializedError, match=reached):
        load_provisions(repo / PROV)
    with pytest.raises(CorpusNotMaterializedError, match=reached):
        require_materialized([repo / PROV])
    _write(repo, US_PROV, SHARED_FILES[US_PROV])
    assert load_provisions(repo / PROV)[0].citation_path == "us/statute/a"


def test_an_invalid_lock_of_the_worktree_counts_through_a_sharing_link(tmp_path: Path, monkeypatch) -> None:
    """The worktree's lock applies to paths through its sharing link, so a lock that
    fails to parse there raises instead of reading as no lock."""
    worktree, shared = _sharing(tmp_path, monkeypatch, worktree_locks=SHARED_FILES, shared_locks=SHARED_FILES)
    next((worktree / LOCK_ROOT).rglob("*.json")).write_text("not a lock\n")
    with pytest.raises(InvalidCorpusLocksError):
        load_provisions(worktree / PROV)
    with pytest.raises(InvalidCorpusLocksError):
        require_materialized([worktree / "data/corpus/provisions"])
    assert not (shared / PROV).exists()


def test_an_invalid_lock_still_raises_for_a_path_no_checkout_names(tmp_path: Path, monkeypatch) -> None:
    """As before, a path outside every checkout goes to the working directory's
    checkout, so a lock that fails to parse there raises rather than read as no
    lock."""
    repo = _locked_checkout(tmp_path / "repo", monkeypatch)
    next((repo / LOCK_ROOT).rglob("*.json")).write_text("not a lock\n")
    monkeypatch.chdir(repo)
    outside = tmp_path / "elsewhere.jsonl"
    with pytest.raises(InvalidCorpusLocksError):
        require_materialized([outside])
    with pytest.raises(InvalidCorpusLocksError):
        ensure_corpus_paths([outside])


def test_scopes_cli_inputs_and_sources_through_a_sharing_link_follow_every_lock(
    tmp_path: Path, monkeypatch
) -> None:
    """``ensure_corpus_scopes``, the CLI's input fetch and ``resolve_corpus_path``
    read only the worktree's lock (or the shared one), so a scope only the shared
    lock names was skipped, and a source sibling only the worktree's lock names was
    missed. They now take each scope's paths, and each input, as selections."""
    import argparse

    act = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    sibling = "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml"
    every = {**SHARED_FILES, **SCOPE_FILES}
    worktree, shared = _sharing(
        tmp_path / "scopes",
        monkeypatch,
        worktree_locks={PROV: every[PROV], act: every[act], sibling: every[sibling]},
        shared_locks={PROV: every[PROV], act: every[act], US_PROV: every[US_PROV]},
        link="data/corpus",
        every_file=every,
    )
    # A scope only the shared lock names is fetched there.
    report = resolver_module.ensure_corpus_scopes([US_SCOPE], repo=worktree)
    assert report.materialized == [US_PROV] and (shared / US_PROV).is_file()
    # A scope whose sibling only the worktree's lock names is refused.
    with pytest.raises(CorpusNotMaterializedError, match=_unfetchable(sibling, "worktree", "shared")):
        resolver_module.ensure_corpus_scopes([SCOPE], repo=worktree)
    _write(shared, act, every[act])
    with pytest.raises(CorpusNotMaterializedError, match=_unfetchable(sibling, "worktree", "shared")):
        resolve_corpus_path(worktree / act)
    # CLI inputs, bare or absolute through the link, are selections too.
    (shared / US_PROV).unlink()
    for spelled in (Path(US_PROV), worktree / US_PROV):
        args = argparse.Namespace(base=Path("data/corpus"), provisions=spelled)
        assert corpus_inputs_from_args(args, repo=worktree)[0] == [US_PROV]
        report = resolver_module.materialize_cli_inputs(args, repo=worktree)
        assert report is not None and report.materialized == [US_PROV]
        (shared / US_PROV).unlink()
    args = argparse.Namespace(base=Path("data/corpus"), source=worktree / sibling)
    with pytest.raises(CorpusNotMaterializedError, match=_unfetchable(sibling, "worktree", "shared")):
        resolver_module.materialize_cli_inputs(args, repo=worktree)
    # In place, the source and its siblings read.
    _write(shared, sibling, every[sibling])
    assert os.path.samefile(resolve_corpus_path(worktree / act), worktree / act)
    assert _tree(worktree / "data") == ["corpus"]


def test_analytics_requires_the_shared_checkouts_files_through_a_sharing_link(tmp_path: Path, monkeypatch) -> None:
    """``analytics`` required the versions its glob matches in the working
    checkout's lock alone, so a matching scope only the shared lock names, read
    through the link, was not required and an unfetched one read as absent."""
    from axiom_corpus.corpus.cli import _corpus_wide_prefixes, build_parser

    worktree, _shared = _sharing(
        tmp_path, monkeypatch, worktree_locks={PROV: SHARED_FILES[PROV]}, shared_locks={US_PROV: SHARED_FILES[US_PROV]}
    )
    args = build_parser().parse_args(["analytics", "--base", str(worktree / "data/corpus"), "--version", "2026-07-*"])
    required = {path.relative_to(worktree).as_posix() for path in _corpus_wide_prefixes(args, "analytics")}
    assert required == {PROV, US_PROV}
    with pytest.raises(CorpusNotMaterializedError):
        require_materialized([worktree / US_PROV])


def test_the_cli_works_in_the_checkout_holding_a_sharing_link(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 1: with ``data/corpus`` itself shared, the CLI took the
    checkout ``--base`` resolves into (the shared one) for its own, so analytics
    and the input fetch read the shared lock alone and passed over a file only
    the worktree's lock names."""
    import argparse

    from axiom_corpus.corpus.cli import _corpus_wide_prefixes, build_parser

    every = {**SHARED_FILES, COVERAGE: SCOPE_FILES[COVERAGE]}
    worktree, _shared = _sharing(
        tmp_path,
        monkeypatch,
        worktree_locks={PROV: every[PROV]},
        shared_locks={COVERAGE: every[COVERAGE]},
        link="data/corpus",
        every_file=every,
    )
    base = str(worktree / "data/corpus")
    args = build_parser().parse_args(["analytics", "--base", base, "--version", "2026-07-10"])
    holder = resolver_module.cli_repo(args)
    assert holder is not None and os.path.samefile(holder, worktree)
    assert worktree / PROV in _corpus_wide_prefixes(args, "analytics")
    assert cli_main(["analytics", "--base", base, "--version", "2026-07-10"]) == 2
    inputs = argparse.Namespace(base=Path(base), provisions=worktree / PROV)
    with pytest.raises(CorpusNotMaterializedError, match=_unfetchable(PROV, "worktree", "shared")):
        resolver_module.materialize_cli_inputs(inputs)


def test_analytics_selects_by_the_path_it_reads_not_the_lock_that_names_it(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 2: the worktree's ``nz`` links to another checkout's
    ``us``, whose lock names the file read as ``nz``'s. Analytics filtered by the
    lock entry's own scope (``us``), so ``--jurisdiction nz`` dropped it."""
    from axiom_corpus.corpus.cli import _corpus_wide_prefixes, build_parser

    worktree = _init_repo(tmp_path / "worktree")
    _lock_files(worktree, {COVERAGE: SCOPE_FILES[COVERAGE]})  # an unrelated lock: not the nz provisions
    other = _init_repo(tmp_path / "other")
    _lock_files(other, {US_PROV: SHARED_FILES[US_PROV]})
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    (other / "data/corpus/provisions/us/statute").mkdir(parents=True)
    (worktree / "data/corpus/provisions").mkdir(parents=True)
    (worktree / "data/corpus/provisions/nz").symlink_to(other / "data/corpus/provisions/us", target_is_directory=True)
    monkeypatch.chdir(worktree)
    argv = ["analytics", "--base", str(worktree / "data/corpus"), "--version", "2026-07-10", "--jurisdiction", "nz"]
    assert worktree / PROV in _corpus_wide_prefixes(build_parser().parse_args(argv), "analytics")
    assert cli_main(argv) == 2


@pytest.mark.parametrize("spelling", ["official/act.html", "official/../official/act.html", "official/./act.html"])
@pytest.mark.parametrize("with_repo", [False, True])
def test_a_source_spelled_with_dotdot_still_needs_every_locked_sibling(
    tmp_path: Path, monkeypatch, spelling: str, with_repo: bool
) -> None:
    """Review r1 finding 3: a ``..`` in a source file's spelling skipped widening
    the witness check to its scope's sources directory, so a sibling only the
    worktree's lock names was missed for that spelling alone."""
    version = "data/corpus/sources/nz/statute/2026-07-10"
    act, sibling = f"{version}/official/act.html", f"{version}/official/sub dir/s 2.xml"
    every = {**SHARED_FILES, **SCOPE_FILES}
    worktree, shared = _sharing(
        tmp_path,
        monkeypatch,
        worktree_locks={act: every[act], sibling: every[sibling]},
        shared_locks={act: every[act]},
        link=version,
        every_file=every,
    )
    _write(shared, act, every[act])
    kwargs = {"repo": worktree} if with_repo else {}
    path = worktree / version / spelling
    for fetch_off in (False, True):
        if fetch_off:
            monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
        with pytest.raises(CorpusNotMaterializedError, match=_unfetchable(sibling, "worktree", "shared")):
            resolve_corpus_path(path, **kwargs)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    _write(shared, sibling, every[sibling])
    assert os.path.samefile(resolve_corpus_path(path, **kwargs), shared / act)


def test_two_links_to_one_directory_each_keep_the_links_below_it(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 4: ``a`` and ``b`` both link to ``x`` in a lock-free
    checkout, whose ``x/statute`` is shared from a third. The walk entered ``x``
    once, so the files below ``b`` lost their owner and fetch tried to write
    through ``b``. Each spelling of the directory is walked."""
    first = "data/corpus/provisions/a/statute/2026-07-10.jsonl"
    second = "data/corpus/provisions/b/statute/2026-07-10.jsonl"
    third = "data/corpus/provisions/x/statute/2026-07-10.jsonl"
    data = SHARED_FILES[PROV]
    every = {first: data, second: data, third: data}
    a = _init_repo(tmp_path / "a")
    b = _init_repo(tmp_path / "b")
    c = _init_repo(tmp_path / "c")
    _lock_files(a, {first: data, second: data})
    _lock_files(c, {third: data})
    (c / "data/corpus/provisions/x/statute").mkdir(parents=True)
    (b / "data/corpus/provisions/x").mkdir(parents=True)
    (b / "data/corpus/provisions/x/statute").symlink_to(c / "data/corpus/provisions/x/statute", target_is_directory=True)
    (a / "data/corpus/provisions").mkdir(parents=True)
    for name in ("a", "b"):
        (a / f"data/corpus/provisions/{name}").symlink_to(b / "data/corpus/provisions/x", target_is_directory=True)
    remote, _fake = _remote({content_key(_sha(d)): d for d in every.values()})
    monkeypatch.setattr(R2ObjectStore, "from_environment", classmethod(lambda cls, **_kwargs: remote))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    monkeypatch.chdir(a)
    for name in (first, second):
        holder = resolver_module._checkout_for(a / name)
        assert holder is not None and os.path.samefile(holder, c)
    report = ensure_corpus_paths([a / "data/corpus/provisions"], repo=a)
    assert report.materialized == [third] and (c / third).read_bytes() == data
    require_materialized([a / "data/corpus/provisions"], repo=a)


def test_a_lock_free_worktree_still_reads_the_shared_checkouts_lock(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 5: ``ensure_corpus_scopes`` and the CLI input fetch did
    nothing when the selecting checkout had no locks of its own, though its
    sharing link leads to a checkout whose lock names the scope."""
    import argparse

    worktree, shared = _sharing(tmp_path, monkeypatch, worktree_locks={}, shared_locks={PROV: SHARED_FILES[PROV]})
    absent = rf"not in this checkout \(first: {PROV}\)"
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match=rf"absent and fetching is off .*first: {PROV}"):
        resolver_module.ensure_corpus_scopes([SCOPE], repo=worktree)
    with pytest.raises(CorpusNotMaterializedError, match=absent):
        ensure_corpus_paths([worktree / PROV], repo=worktree)
    inputs = argparse.Namespace(base=Path("data/corpus"), provisions=Path(PROV))
    with pytest.raises(CorpusNotMaterializedError, match=rf"absent and fetching is off .*first: {PROV}"):
        resolver_module.materialize_cli_inputs(inputs, repo=worktree)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert resolver_module.ensure_corpus_scopes([SCOPE], repo=worktree).materialized == [PROV]
    assert (shared / PROV).read_bytes() == SHARED_FILES[PROV]


def test_a_bare_path_with_repo_is_that_checkouts_even_when_present_here(tmp_path: Path, monkeypatch) -> None:
    """Review r1 finding 6: ``resolve_corpus_path`` returned the working
    directory's present file for a bare ``data/corpus/...`` path before taking it
    in ``repo``."""
    here = _locked_checkout(tmp_path / "here", monkeypatch)
    there = _locked_checkout(tmp_path / "there", monkeypatch)
    _write(here, PROV, READABLE_FILES[PROV])
    _write(there, PROV, READABLE_FILES[PROV])
    monkeypatch.chdir(here)
    assert os.path.samefile(resolve_corpus_path(PROV, repo=there), there / PROV)
    assert os.path.samefile(resolve_corpus_path(PROV), here / PROV)


_VERSION_DIR = "data/corpus/sources/nz/statute/2026-07-10"
_ACT = f"{_VERSION_DIR}/official/act.html"
_SIBLING = f"{_VERSION_DIR}/official/sub dir/s 2.xml"
_LINKED_SOURCE = f"{_VERSION_DIR}/linked/b.html"
_SOURCE_FILES = {**SCOPE_FILES, _LINKED_SOURCE: b"<html>B</html>\n"}


def _serve(tmp_path: Path, monkeypatch, files: dict[str, bytes]) -> None:
    remote, _fake = _remote({content_key(_sha(d)): d for d in files.values()})
    monkeypatch.setattr(R2ObjectStore, "from_environment", classmethod(lambda cls, **_kwargs: remote))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    monkeypatch.setattr(resolver_module, "_WITNESSED_SOURCE_DIRS", set(), raising=False)


def test_analytics_counts_every_spelling_of_a_locked_file(tmp_path: Path, monkeypatch) -> None:
    """Review r2 finding 1: ``provisions/b`` links to ``provisions/x`` of the same
    checkout, whose lock names the absent ``x`` file. Only one spelling per entry
    was kept, so ``--jurisdiction b`` dropped the file read as ``b``'s."""
    from axiom_corpus.corpus.cli import _corpus_wide_prefixes, build_parser

    locked = "data/corpus/provisions/x/statute/2026-07-10.jsonl"
    repo = _init_repo(tmp_path / "repo")
    _lock_files(repo, {locked: SHARED_FILES[PROV]})
    (repo / "data/corpus/provisions/x/statute").mkdir(parents=True)
    (repo / "data/corpus/provisions/b").symlink_to(repo / "data/corpus/provisions/x", target_is_directory=True)
    _serve(tmp_path, monkeypatch, {locked: SHARED_FILES[PROV]})
    monkeypatch.chdir(repo)
    argv = ["analytics", "--base", str(repo / "data/corpus"), "--version", "2026-07-10", "--jurisdiction", "b"]
    assert repo / "data/corpus/provisions/b/statute/2026-07-10.jsonl" in _corpus_wide_prefixes(
        build_parser().parse_args(argv), "analytics"
    )
    assert cli_main(argv) == 2


def test_the_cli_works_where_base_stands_when_it_links_to_another_checkouts_root(
    tmp_path: Path, monkeypatch
) -> None:
    """Review r2 finding 2: ``data/corpus`` links to another checkout's top level;
    the walk up from ``--base`` met that checkout first, through the link, so the
    CLI read its (empty) lock and passed over the holder's absent file."""
    holder = _init_repo(tmp_path / "holder")
    _lock_files(holder, {PROV: SHARED_FILES[PROV]})
    target = _init_repo(tmp_path / "target")
    (target / "provisions/nz/statute").mkdir(parents=True)
    (holder / "data").mkdir()
    (holder / "data/corpus").symlink_to(target, target_is_directory=True)
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(holder)
    base = str(holder / "data/corpus")
    args = build_parser_for_cli().parse_args(["analytics", "--base", base, "--version", "2026-07-10"])
    found = resolver_module.cli_repo(args)
    assert found is not None and os.path.samefile(found, holder)
    assert cli_main(["analytics", "--base", base, "--version", "2026-07-10"]) == 2


def build_parser_for_cli():
    from axiom_corpus.corpus.cli import build_parser

    return build_parser()


def test_a_source_read_needs_siblings_another_checkout_names_below_a_link(tmp_path: Path, monkeypatch) -> None:
    """Review r2 finding 3: a link inside a scope's sources directory leads to
    another checkout whose lock names an absent file there. Reading a source of
    the scope saw no witness and cached the directory as complete; listing the
    directory would miss that file. The read now fetches it into that checkout,
    or refuses it with fetching off."""
    a = _init_repo(tmp_path / "a")
    z = _init_repo(tmp_path / "z")
    _lock_files(a, {_ACT: _SOURCE_FILES[_ACT]})
    _lock_files(z, {_LINKED_SOURCE: _SOURCE_FILES[_LINKED_SOURCE]})
    _write(a, _ACT, _SOURCE_FILES[_ACT])
    (z / f"{_VERSION_DIR}/linked").mkdir(parents=True)
    (a / f"{_VERSION_DIR}/linked").symlink_to(z / f"{_VERSION_DIR}/linked", target_is_directory=True)
    _serve(tmp_path, monkeypatch, _SOURCE_FILES)
    monkeypatch.chdir(a)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match=f"fetching is off .*first: {_LINKED_SOURCE}"):
        resolve_corpus_path(a / _ACT, repo=a)
    with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
        require_materialized([a / _VERSION_DIR], repo=a)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert resolve_corpus_path(a / _ACT, repo=a) == a / _ACT
    assert (z / _LINKED_SOURCE).read_bytes() == _SOURCE_FILES[_LINKED_SOURCE]


def test_a_source_pointer_widens_the_directory_it_points_into(tmp_path: Path, monkeypatch) -> None:
    """Review r2 finding 4: a ``latest.html`` pointer outside every checkout, to a
    source through a sharing link, widened the pointer's own parents (the wrong
    directory, or an IndexError near ``/``), so the worktree's locked sibling was
    never checked."""
    every = {**SHARED_FILES, **SCOPE_FILES}
    worktree, shared = _sharing(
        tmp_path,
        monkeypatch,
        worktree_locks={_ACT: every[_ACT], _SIBLING: every[_SIBLING]},
        shared_locks={_ACT: every[_ACT]},
        link=_VERSION_DIR,
        every_file=every,
    )
    _write(shared, _ACT, every[_ACT])
    pointer = tmp_path / "latest.html"
    pointer.symlink_to(worktree / _ACT)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    for path in (worktree / _ACT, pointer):
        with pytest.raises(CorpusNotMaterializedError, match=_unfetchable(_SIBLING, "worktree", "shared")):
            resolve_corpus_path(path, repo=worktree)


def test_whole_source_directories_fetch_each_file_into_the_checkout_naming_it(
    tmp_path: Path, monkeypatch
) -> None:
    """Review r2 finding 5: making a sources directory whole re-added, to the
    first checkout's batch, a file the planner had given to the checkout a link
    inside the directory leads to, so fetch refused to write through the link."""
    a = _init_repo(tmp_path / "a")
    z = _init_repo(tmp_path / "z")
    _lock_files(a, {_ACT: _SOURCE_FILES[_ACT], _LINKED_SOURCE: _SOURCE_FILES[_LINKED_SOURCE]})
    _lock_files(z, {_LINKED_SOURCE: _SOURCE_FILES[_LINKED_SOURCE]})
    _write(a, _ACT, _SOURCE_FILES[_ACT])
    (z / f"{_VERSION_DIR}/linked").mkdir(parents=True)
    (a / f"{_VERSION_DIR}/linked").symlink_to(z / f"{_VERSION_DIR}/linked", target_is_directory=True)
    _serve(tmp_path, monkeypatch, _SOURCE_FILES)
    monkeypatch.chdir(a)
    for selection in (a / _ACT, a / _VERSION_DIR):
        report = ensure_corpus_paths([selection], repo=a)
        assert (z / _LINKED_SOURCE).read_bytes() == _SOURCE_FILES[_LINKED_SOURCE]
        assert _LINKED_SOURCE in report.materialized + report.present
        (z / _LINKED_SOURCE).unlink()
    # require_materialized fetches what the selection lacks, its whole sources
    # directory with it; the act is in place, so select the directory.
    require_materialized([a / _VERSION_DIR], repo=a, fetch=True)
    assert (z / _LINKED_SOURCE).is_file()
    (z / _LINKED_SOURCE).unlink()
    (a / _ACT).unlink()
    require_materialized([a / _ACT], repo=a, fetch=True)  # absent: fetched with its directory
    assert (a / _ACT).is_file() and (z / _LINKED_SOURCE).is_file()
    (z / _LINKED_SOURCE).unlink()
    assert _tree(a / f"{_VERSION_DIR}") == ["linked", "official", "official/act.html"]


@pytest.mark.parametrize("locked", [False, True])
def test_a_directory_cycle_is_walked_in_bounded_time(tmp_path: Path, monkeypatch, locked: bool) -> None:
    """Review r2 finding 6: two links in a directory back to itself made the walk
    follow every left/right combination up to the link bound (exponential). A
    link back to a directory already walked on its spelled path (with the same
    names protected below it) is a cycle and is not followed; a locked file
    below it is placed by its own path."""
    repo = _init_repo(tmp_path / "repo")
    if locked:
        _lock_files(repo, {PROV: SHARED_FILES[PROV]})
    statute = repo / "data/corpus/provisions/nz/statute"
    statute.mkdir(parents=True)
    for name in ("left", "right"):
        (statute / name).symlink_to(statute, target_is_directory=True)
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    monkeypatch.chdir(repo)
    parts, _views, _cut = resolver_module._selection(repo / "data/corpus/provisions", None, walk=True)
    # The selection, each link, and each link once more below the other's
    # spelling: 1 + k + k*k for k links, not every combination up to 40 deep.
    assert len(parts) <= 1 + 2 + 2 * 2
    if locked:
        with pytest.raises(CorpusNotMaterializedError, match="not in this checkout"):
            require_materialized([repo / "data/corpus/provisions"], repo=repo)
    else:
        require_materialized([repo / "data/corpus/provisions"], repo=repo)


def _file_of(jurisdiction: str) -> str:
    return f"data/corpus/provisions/{jurisdiction}/statute/2026-07-10.jsonl"


def test_a_link_to_a_parent_directory_does_not_hide_links_below_it(tmp_path: Path, monkeypatch) -> None:
    """Review r3 finding 1: ``provisions`` links to ``data/corpus`` itself, whose
    ``side/statute`` links to another checkout. Selected from ``data/corpus``,
    the walk took the second visit of ``data/corpus`` (through ``provisions``) for
    a cycle and stopped, though below ``provisions`` every name is protected and
    ``side/statute`` stands where the other checkout's lock names a file."""
    side = _file_of("side")
    a = _init_repo(tmp_path / "a")
    b = _init_repo(tmp_path / "b")
    _lock_files(b, {side: SHARED_FILES[PROV]})
    (b / "data/corpus/provisions/side/statute").mkdir(parents=True)
    (a / "data/corpus/side").mkdir(parents=True)
    (a / "data/corpus/provisions").symlink_to(a / "data/corpus", target_is_directory=True)
    (a / "data/corpus/side/statute").symlink_to(b / "data/corpus/provisions/side/statute", target_is_directory=True)
    _serve(tmp_path, monkeypatch, {side: SHARED_FILES[PROV]})
    monkeypatch.chdir(a)
    for selection in (a / "data/corpus/provisions", a / "data/corpus"):
        with pytest.raises(CorpusNotMaterializedError, match=rf"first: {side}"):
            require_materialized([selection], repo=a)
        assert a / side in dict(resolver_module.locked_entries_under([selection], repo=a))


def test_every_alias_keeps_the_owner_below_it(tmp_path: Path, monkeypatch) -> None:
    """Review r3 finding 2: ``a`` and ``b`` both link to ``x`` in a lock-free
    checkout, whose ``statute`` is shared from a third checkout with the only
    lock. The second alias was walked only when a lock already seen named files
    below it, which the third checkout's (not yet seen) could not, so analytics
    dropped one jurisdiction."""
    a = _init_repo(tmp_path / "a")
    b = _init_repo(tmp_path / "b")
    c = _init_repo(tmp_path / "c")
    _lock_files(c, {_file_of("x"): SHARED_FILES[PROV]})
    (c / "data/corpus/provisions/x/statute").mkdir(parents=True)
    (b / "data/corpus/provisions/x").mkdir(parents=True)
    (b / "data/corpus/provisions/x/statute").symlink_to(c / "data/corpus/provisions/x/statute", target_is_directory=True)
    (a / "data/corpus/provisions").mkdir(parents=True)
    for name in ("a", "b"):
        (a / f"data/corpus/provisions/{name}").symlink_to(b / "data/corpus/provisions/x", target_is_directory=True)
    _serve(tmp_path, monkeypatch, {_file_of("x"): SHARED_FILES[PROV]})
    monkeypatch.chdir(a)
    found = dict(resolver_module.locked_entries_under([a / "data/corpus/provisions"], repo=a))
    assert {a / _file_of("a"), a / _file_of("b")} <= set(found)
    for jurisdiction in ("a", "b"):
        argv = ["analytics", "--base", str(a / "data/corpus"), "--version", "2026-07-10", "--jurisdiction", jurisdiction]
        assert cli_main(argv) == 2, jurisdiction


def test_a_selected_source_makes_its_directory_whole_across_checkouts(tmp_path: Path, monkeypatch) -> None:
    """Review r3 finding 3: selecting one source widened only the selecting
    checkout's lock, so a sibling only the checkout a link inside the directory
    leads to names stayed absent, though resolving the same source fetched it."""
    a = _init_repo(tmp_path / "a")
    z = _init_repo(tmp_path / "z")
    _lock_files(a, {_ACT: _SOURCE_FILES[_ACT]})
    _lock_files(z, {_LINKED_SOURCE: _SOURCE_FILES[_LINKED_SOURCE]})
    (z / f"{_VERSION_DIR}/linked").mkdir(parents=True)
    (a / _VERSION_DIR).mkdir(parents=True)
    (a / f"{_VERSION_DIR}/linked").symlink_to(z / f"{_VERSION_DIR}/linked", target_is_directory=True)
    _serve(tmp_path, monkeypatch, _SOURCE_FILES)
    monkeypatch.chdir(a)
    for fetch in ("ensure_corpus_paths", "require_materialized", "fetch_locked_file"):
        for placed in (a / _ACT, z / _LINKED_SOURCE):
            placed.unlink(missing_ok=True)
        if fetch == "ensure_corpus_paths":
            ensure_corpus_paths([a / _ACT], repo=a)
        elif fetch == "require_materialized":
            require_materialized([a / _ACT], repo=a, fetch=True)
        else:
            assert fetch_locked_file(a / _ACT)
        assert (a / _ACT).is_file(), fetch
        assert (z / _LINKED_SOURCE).read_bytes() == _SOURCE_FILES[_LINKED_SOURCE], fetch
    require_materialized([a / _VERSION_DIR], repo=a)


def test_a_directory_listed_under_one_namespace_is_listed_again_under_another(
    tmp_path: Path, monkeypatch
) -> None:
    """Review r3 finding 4: one directory is reached as ``data/corpus`` (where only
    the class directories are protected) and as ``provisions/a`` (where every name
    is). Its listing was cached by inode alone, so whichever came first decided
    whether ``statute`` (a link to the checkout that locks the file) was seen."""
    file = _file_of("a")
    a = _init_repo(tmp_path / "a")
    b = _init_repo(tmp_path / "b")
    c = _init_repo(tmp_path / "c")
    _lock_files(a, {file: SHARED_FILES[PROV]})
    _lock_files(c, {file: SHARED_FILES[PROV]})
    (c / "data/corpus/provisions/a/statute").mkdir(parents=True)
    (b / "data/corpus").mkdir(parents=True)
    (b / "data/corpus/statute").symlink_to(c / "data/corpus/provisions/a/statute", target_is_directory=True)
    (a / "data/corpus/provisions/z/statute/data").mkdir(parents=True)
    (a / "data/corpus/provisions/a").symlink_to(b / "data/corpus", target_is_directory=True)
    (a / "data/corpus/provisions/z/statute/data/corpus").symlink_to(b / "data/corpus", target_is_directory=True)
    _serve(tmp_path, monkeypatch, {file: SHARED_FILES[PROV]})
    monkeypatch.chdir(a)
    for selection in (a / "data/corpus/provisions", a / "data/corpus/provisions/a"):
        (c / file).unlink(missing_ok=True)
        ensure_corpus_paths([selection], repo=a)
        assert (c / file).read_bytes() == SHARED_FILES[PROV], selection


def test_a_nested_checkout_is_used_even_when_the_outer_repo_is_given(tmp_path: Path, monkeypatch) -> None:
    """Review r3 finding 5: with the outer checkout passed as ``repo``, the outer
    checkout named a nested checkout's corpus file (as one of its own sources)
    and its lock, which names nothing there, passed it. The helpers use the
    nested checkout, as invariant 10 says, whatever ``repo`` is given."""
    outer = _init_repo(tmp_path / "outer")
    nested = _init_repo(outer / f"{_VERSION_DIR}/vendored")
    _lock_files(nested, {PROV: SHARED_FILES[PROV]})
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(outer)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    for kwargs in ({}, {"repo": outer}):
        with pytest.raises(CorpusNotMaterializedError, match=rf"first: {PROV}"):
            require_materialized([nested / PROV], **kwargs)


_NESTED_SOURCE_DIR = "data/corpus/sources/nz/statute/v1"
_NESTED_PROV = "data/corpus/provisions/nz/statute/v1.jsonl"


def _nested_witness_checkout(tmp_path: Path, monkeypatch, unrelated_lock: bool) -> tuple[Path, Path, str]:
    outer = _init_repo(tmp_path / "outer")
    nested = _init_repo(outer / f"{_NESTED_SOURCE_DIR}/vendored")
    outer_rel = f"{_NESTED_SOURCE_DIR}/vendored/{_NESTED_PROV}"
    _lock_files(outer, {outer_rel: SHARED_FILES[PROV]})
    if unrelated_lock:
        _lock_files(nested, {US_PROV: SHARED_FILES[US_PROV]})
        _write(nested, US_PROV, SHARED_FILES[US_PROV])
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(outer)
    return outer, nested, outer_rel


@pytest.mark.parametrize("unrelated_lock", [False, True], ids=["no-nested-lock", "unrelated-nested-lock"])
@pytest.mark.parametrize("repo_hint", [None, "outer", "nested"], ids=["no-repo", "outer-repo", "nested-repo"])
@pytest.mark.parametrize("selection", ["exact", "broad"])
@pytest.mark.parametrize("action", ["require", "require-fetch", "ensure"])
def test_an_enclosing_lock_refuses_an_absent_nested_checkout_file(
    tmp_path: Path, monkeypatch, unrelated_lock: bool, repo_hint: str | None, selection: str, action: str
) -> None:
    """The outer source lock remains a witness when the nested checkout owns fetches."""
    outer, nested, outer_rel = _nested_witness_checkout(tmp_path, monkeypatch, unrelated_lock)
    path = nested / _NESTED_PROV if selection == "exact" else outer / _NESTED_SOURCE_DIR
    kwargs = {} if repo_hint is None else {"repo": outer if repo_hint == "outer" else nested}
    assert CorpusResolver(nested, sources=[]).relative(nested / _NESTED_PROV) == _NESTED_PROV
    assert CorpusResolver(outer, sources=[]).relative(nested / _NESTED_PROV) == outer_rel
    for no_fetch in ("", "1"):
        monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", no_fetch)
        with pytest.raises(CorpusNotMaterializedError, match="absent and no fetch will place them") as refused:
            if action == "ensure":
                ensure_corpus_paths([path], **kwargs)
            else:
                require_materialized([path], fetch=action == "require-fetch", **kwargs)
        message = str(refused.value)
        assert f"{outer_rel}, which the lock of {outer} names" in message
        assert f"{nested} names that path" in message
        assert f"does not list {_NESTED_PROV}" in message
        assert f"Lock that scope in {nested} and fetch it there" in message
        assert f"axiom-corpus-ingest corpus fetch --path {outer_rel}` in {outer}" in message
        # The remote has the outer lock's bytes: refusal must precede fetching them
        # into the nested checkout, whose lock does not name this file.
        assert not (nested / _NESTED_PROV).exists()


@pytest.mark.parametrize("unrelated_lock", [False, True], ids=["no-nested-lock", "unrelated-nested-lock"])
@pytest.mark.parametrize("no_fetch", ["", "1"], ids=["fetch-on", "fetch-off"])
@pytest.mark.parametrize(
    "reader", [fetch_locked_file, load_provisions, resolve_corpus_path],
    ids=["fetch-locked-file", "load-provisions", "resolve-corpus-path"],
)
def test_an_enclosing_lock_refuses_an_empty_read_of_an_absent_nested_checkout_file(
    tmp_path: Path, monkeypatch, unrelated_lock: bool, no_fetch: str, reader
) -> None:
    outer, nested, outer_rel = _nested_witness_checkout(tmp_path, monkeypatch, unrelated_lock)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", no_fetch)
    with pytest.raises(CorpusNotMaterializedError, match="absent and no fetch will place them") as refused:
        reader(nested / _NESTED_PROV)
    assert f"axiom-corpus-ingest corpus fetch --path {outer_rel}` in {outer}" in str(refused.value)
    assert not (nested / _NESTED_PROV).exists()


def test_every_enclosing_lock_counts_through_multiple_nested_checkouts(tmp_path: Path, monkeypatch) -> None:
    """An outer witness applies even when a nearer enclosing checkout does not name the file."""
    outer = _init_repo(tmp_path / "outer")
    middle = _init_repo(outer / f"{_NESTED_SOURCE_DIR}/vendored")
    inner = _init_repo(middle / f"{_NESTED_SOURCE_DIR}/vendored")
    outer_rel = inner.relative_to(outer).as_posix() + f"/{_NESTED_PROV}"
    _lock_files(outer, {outer_rel: SHARED_FILES[PROV]})
    _lock_files(middle, {US_PROV: SHARED_FILES[US_PROV]})
    _write(middle, US_PROV, SHARED_FILES[US_PROV])
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(inner)
    for hint in (None, outer, middle, inner):
        for selection in (outer / _NESTED_SOURCE_DIR, middle / _NESTED_SOURCE_DIR, inner / _NESTED_PROV):
            with pytest.raises(CorpusNotMaterializedError, match="absent and no fetch will place them") as refused:
                require_materialized([selection], repo=hint, fetch=True)
            assert f"{outer_rel}, which the lock of {outer} names" in str(refused.value)
            assert f"Lock that scope in {inner} and fetch it there" in str(refused.value)
            assert not (inner / _NESTED_PROV).exists()


def test_a_nested_checkout_is_used_for_source_reads_and_any_spelling_of_the_outer_repo(
    tmp_path: Path, monkeypatch
) -> None:
    """Review r4 finding 1: ``resolve_corpus_path`` took the outer checkout's name
    for a nested checkout's source (widening the outer scope), and the nested
    check compared strings, so a case-variant spelling of the outer checkout
    passed over the nested lock."""
    outer = _init_repo(tmp_path / "outer")
    nested = _init_repo(outer / f"{_VERSION_DIR}/vendored")
    _lock_files(nested, {_ACT: _SOURCE_FILES[_ACT], _SIBLING: _SOURCE_FILES[_SIBLING], PROV: SHARED_FILES[PROV]})
    _write(nested, _ACT, _SOURCE_FILES[_ACT])
    _serve(tmp_path, monkeypatch, {**_SOURCE_FILES, PROV: SHARED_FILES[PROV]})
    monkeypatch.chdir(outer)
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    for kwargs in ({}, {"repo": outer}):
        with pytest.raises(CorpusNotMaterializedError, match="fetching is off"):
            resolve_corpus_path(nested / _ACT, **kwargs)
        with pytest.raises(CorpusNotMaterializedError, match=f"first: {_SIBLING}"):
            require_materialized([nested / _VERSION_DIR], **kwargs)
    spellings = _checkout_spellings(outer)
    for name, spelling in spellings.items():
        if name in {"case variant", "firmlink"}:
            path = spelling / f"{_VERSION_DIR}/vendored" / PROV
            with pytest.raises(CorpusNotMaterializedError, match=f"first: {PROV}"):
                require_materialized([path], repo=outer)


def test_a_lock_naming_a_path_through_a_cycle_is_owned_where_that_path_leads(
    tmp_path: Path, monkeypatch
) -> None:
    """Review r4 finding 2: ``S/loop`` links back to ``S`` and ``S/shared`` to
    another checkout; this checkout's lock names ``S/loop/shared/b``. The walk cut
    the cycle before seeing ``loop/shared``, so the broad selection gave the file
    to this checkout and refused to write through ``loop``, while selecting the
    file fetched it into the other checkout. Cycles are still not followed; a
    locked file below a cut is placed by its own path."""
    through = f"{_VERSION_DIR}/loop/shared/b.html"
    shared = f"{_VERSION_DIR}/shared/b.html"
    data = _SOURCE_FILES[_LINKED_SOURCE]
    a = _init_repo(tmp_path / "a")
    c = _init_repo(tmp_path / "c")
    _lock_files(a, {through: data})
    _lock_files(c, {shared: data})
    (c / f"{_VERSION_DIR}/shared").mkdir(parents=True)
    (a / _VERSION_DIR).mkdir(parents=True)
    (a / f"{_VERSION_DIR}/loop").symlink_to(a / _VERSION_DIR, target_is_directory=True)
    (a / f"{_VERSION_DIR}/shared").symlink_to(c / f"{_VERSION_DIR}/shared", target_is_directory=True)
    _serve(tmp_path, monkeypatch, {shared: data})
    monkeypatch.chdir(a)
    for selection in (a / _VERSION_DIR, a / through):
        (c / shared).unlink(missing_ok=True)
        ensure_corpus_paths([selection], repo=a)
        assert (c / shared).read_bytes() == data, selection
    require_materialized([a / _VERSION_DIR], repo=a)


def test_a_selection_containing_a_nested_checkout_uses_its_lock_inside(tmp_path: Path, monkeypatch) -> None:
    """Review r5 finding 1: a checkout nested in the selection's tree names its own
    corpus files (invariant 10), but a selection of the outer directory gave them
    to the outer checkout, which fetched its own bytes into the nested tree. The
    nested checkout's corpus is a part of the selection, and its lock decides."""
    outer_bytes, nested_bytes = b'{"citation_path":"outer"}\n', b'{"citation_path":"nested"}\n'
    through_outer = f"{_VERSION_DIR}/vendored/{PROV}"
    outer = _init_repo(tmp_path / "outer")
    nested = _init_repo(outer / f"{_VERSION_DIR}/vendored")
    _lock_files(outer, {through_outer: outer_bytes})
    _lock_files(nested, {PROV: nested_bytes})
    _serve(tmp_path, monkeypatch, {"outer": outer_bytes, "nested": nested_bytes})
    monkeypatch.chdir(outer)
    for selection in (outer / _VERSION_DIR, nested / PROV):
        (nested / PROV).unlink(missing_ok=True)
        ensure_corpus_paths([selection], repo=outer)
        assert (nested / PROV).read_bytes() == nested_bytes, selection
    require_materialized([outer / _VERSION_DIR], repo=outer)


def test_a_file_placed_by_its_own_path_below_a_cycle_is_fetched_by_its_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    """Review r5 finding 2: below a cut cycle a locked file is placed by its own
    path, here into the other checkout, whose lock names it; but that checkout's
    entry was not enrolled for fetching, so the broad selection refused both
    locks as unfetchable while selecting the file fetched it. With both
    selections at once, every place a file is read from counts (mutation M19)."""
    through = "data/corpus/provisions/loop/shared/2026-07-10.jsonl"
    data = SHARED_FILES[PROV]
    a = _init_repo(tmp_path / "a")
    c = _init_repo(tmp_path / "c")
    _lock_files(a, {through: data})
    _lock_files(c, {through: data})
    (c / "data/corpus/provisions/loop/shared").mkdir(parents=True)
    (a / "data/corpus/provisions").mkdir(parents=True)
    (a / "data/corpus/provisions/loop").symlink_to(a / "data/corpus/provisions", target_is_directory=True)
    (a / "data/corpus/provisions/shared").symlink_to(c / "data/corpus/provisions/loop/shared", target_is_directory=True)
    _serve(tmp_path, monkeypatch, {through: data})
    monkeypatch.chdir(a)
    for selections in ([a / "data/corpus/provisions"], [a / through], [a / through, a / "data/corpus/provisions"]):
        (c / through).unlink(missing_ok=True)
        ensure_corpus_paths(selections, repo=a)
        assert (c / through).read_bytes() == data, selections
        require_materialized(selections, repo=a)


def test_selecting_a_nested_checkout_itself_uses_its_lock(tmp_path: Path, monkeypatch) -> None:
    """Review r6 finding 1: the walk found checkouts nested below a selection but
    not one the selection itself is, so selecting the nested checkout's top
    level read its corpus under the outer checkout's lock (and fetched the outer
    bytes into it, where both lock the file)."""
    outer_bytes, nested_bytes = b'{"citation_path":"outer"}\n', b'{"citation_path":"nested"}\n'
    outer = _init_repo(tmp_path / "outer")
    nested = _init_repo(outer / f"{_VERSION_DIR}/vendored")
    _lock_files(outer, {f"{_VERSION_DIR}/vendored/{PROV}": outer_bytes})
    _lock_files(nested, {PROV: nested_bytes})
    _serve(tmp_path, monkeypatch, {"outer": outer_bytes, "nested": nested_bytes})
    monkeypatch.chdir(outer)
    with pytest.raises(CorpusNotMaterializedError, match=f"first: {PROV}"):
        require_materialized([nested], repo=outer)
    ensure_corpus_paths([nested], repo=outer)
    assert (nested / PROV).read_bytes() == nested_bytes
    require_materialized([nested], repo=outer)


def test_a_source_only_another_lock_names_still_needs_its_whole_directory(tmp_path: Path, monkeypatch) -> None:
    """Review r6 finding 2: the worktree's lock names two sources of a scope shared
    from a checkout with no source lock. Selecting the present one checked its
    directory only when some checkout owned an entry there, so the absent
    sibling was never checked, though selecting the directory refused it."""
    import argparse

    every = {**SHARED_FILES, **SCOPE_FILES}
    worktree, shared = _sharing(
        tmp_path,
        monkeypatch,
        worktree_locks={_ACT: every[_ACT], _SIBLING: every[_SIBLING]},
        shared_locks={PROV: every[PROV]},
        link=_VERSION_DIR,
        every_file=every,
    )
    _write(shared, _ACT, every[_ACT])
    refused = _unfetchable(_SIBLING, "worktree", "shared")
    with pytest.raises(CorpusNotMaterializedError, match=refused):
        ensure_corpus_paths([worktree / _ACT], repo=worktree)
    with pytest.raises(CorpusNotMaterializedError, match=refused):
        resolver_module.materialize_cli_inputs(argparse.Namespace(source=worktree / _ACT), repo=worktree)
    with pytest.raises(CorpusNotMaterializedError, match=refused):
        resolve_corpus_path(worktree / _ACT, repo=worktree)


def test_a_file_enrolled_below_a_cycle_is_reported_without_fetching(tmp_path: Path, monkeypatch) -> None:
    """Review r6 finding 3: the checkout a file below a cut cycle is placed in had
    no part name, so the fetching-off error raised KeyError instead of naming
    the absent file."""
    through = "data/corpus/provisions/loop/shared/2026-07-10.jsonl"
    data = SHARED_FILES[PROV]
    a = _init_repo(tmp_path / "a")
    c = _init_repo(tmp_path / "c")
    _lock_files(a, {through: data})
    _lock_files(c, {through: data})
    (c / "data/corpus/provisions/loop/shared").mkdir(parents=True)
    (a / "data/corpus/provisions").mkdir(parents=True)
    (a / "data/corpus/provisions/loop").symlink_to(a / "data/corpus/provisions", target_is_directory=True)
    (a / "data/corpus/provisions/shared").symlink_to(c / "data/corpus/provisions/loop/shared", target_is_directory=True)
    _serve(tmp_path, monkeypatch, {through: data})
    monkeypatch.chdir(a)
    for selection in (a / "data/corpus/provisions", a / through):
        with pytest.raises(CorpusNotMaterializedError, match=rf"not in this checkout \(first: {through}\)"):
            require_materialized([selection], repo=a)


def test_a_file_of_a_nested_checkout_outside_its_corpus_stays_the_outer_checkouts(
    tmp_path: Path, monkeypatch
) -> None:
    """Review r7 finding 1: with the outer checkout as ``repo``, a locked outer
    source inside a nested checkout but outside its ``data`` was skipped. The
    nested check set the outer checkout aside, the checkout lookup returned it
    again, and that answer was dropped as "the same as the hint"."""
    licence = f"{_VERSION_DIR}/vendored/license.txt"
    outer = _init_repo(tmp_path / "outer")
    nested = _init_repo(outer / f"{_VERSION_DIR}/vendored")
    _lock_files(outer, {licence: b"licence\n"})
    _serve(tmp_path, monkeypatch, {licence: b"licence\n"})
    monkeypatch.chdir(outer)
    for kwargs in ({}, {"repo": outer}):
        (outer / licence).unlink(missing_ok=True)
        with pytest.raises(CorpusNotMaterializedError, match=f"first: {licence}"):
            require_materialized([nested / "license.txt"], **kwargs)
        assert ensure_corpus_paths([nested / "license.txt"], **kwargs).materialized == [licence]
        assert (outer / licence).read_bytes() == b"licence\n"


# The sharing layout with random locks, files and selections, against a
# reference model of invariant 11 written over the layout, not the filesystem.
_SHARED_UNIVERSE = {**SHARED_FILES, COVERAGE: SCOPE_FILES[COVERAGE]}
_SHARING_LINKS = ("data/corpus", "data/corpus/provisions", "data/corpus/provisions/nz")
_SHARING_SELECTIONS = ("data/corpus", "data/corpus/provisions", "data/corpus/provisions/nz", *_SHARED_UNIVERSE)


@st.composite
def _divergent_sharing(draw):
    files = sorted(_SHARED_UNIVERSE)
    return {
        "link": draw(st.sampled_from(_SHARING_LINKS)),
        "worktree_locks": draw(st.sets(st.sampled_from(files))),
        "shared_locks": draw(st.sets(st.sampled_from(files))),
        "present": draw(st.sets(st.sampled_from(files))),
        "selection": draw(st.sampled_from(_SHARING_SELECTIONS)),
        "bare": draw(st.booleans()),
        "with_repo": draw(st.booleans()),
        "action": draw(st.sampled_from(["require, fetching", "ensure", "read"])),
        # The link's target is not made until something is placed below it.
        "dangling": draw(st.booleans()),
    }


def _placed_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _expected_sharing(link: str, worktree_locks: set[str], shared_locks: set[str], present: set[str], selection: str):
    """Reference model of invariant 11 in the sharing layout.

    A file below the link lives in the shared checkout, whose lock decides what
    is fetched there; any other file lives in the worktree. The worktree's lock
    applies to every file the selection reaches, the shared lock only to those
    below the link. Returns the selected files a lock names that are absent, and
    those of them no fetch places (the shared lock lacks one below the link, or
    the worktree's lock one elsewhere).
    """

    def below(rel: str) -> bool:
        return rel == link or rel.startswith(f"{link}/")

    selected = {rel for rel in _SHARED_UNIVERSE if rel == selection or rel.startswith(f"{selection}/")}
    locked = {rel for rel in selected if rel in worktree_locks or (below(rel) and rel in shared_locks)}
    fetched = {rel for rel in selected if rel in (shared_locks if below(rel) else worktree_locks)}
    absent = locked - present
    return absent, absent - fetched


@PROPERTY_SETTINGS
@given(_divergent_sharing())
def test_every_lock_that_applies_through_a_sharing_link_counts(tmp_path_factory, monkeypatch, drawn) -> None:
    """Invariant 11. For any locks the worktree and the shared checkout hold, any
    files in place, a live or dangling link, and any selection, spelled bare or
    absolute, with ``repo`` or without: every helper refuses exactly when a lock that applies names an absent
    file, and with fetching on, it fetches the absent files the shared lock names
    below the link into the shared checkout (and the others the worktree's lock
    names into the worktree), unless some absent file no fetch places, in which
    case it refuses before fetching anything."""
    base = tmp_path_factory.mktemp("sharing")
    link, selection = drawn["link"], drawn["selection"]
    worktree, shared = _sharing(
        base,
        monkeypatch,
        worktree_locks={rel: _SHARED_UNIVERSE[rel] for rel in drawn["worktree_locks"]},
        shared_locks={rel: _SHARED_UNIVERSE[rel] for rel in drawn["shared_locks"]},
        link=link,
        every_file=_SHARED_UNIVERSE,
        dangling=drawn["dangling"],
    )

    def home(rel: str) -> Path:
        return (shared if rel == link or rel.startswith(f"{link}/") else worktree) / rel

    for rel in drawn["present"]:
        _write(home(rel).parent, home(rel).name, _SHARED_UNIVERSE[rel])
    absent, unfetchable = _expected_sharing(
        link, drawn["worktree_locks"], drawn["shared_locks"], drawn["present"], selection
    )
    path = Path(selection) if drawn["bare"] else worktree / selection
    kwargs = {"repo": worktree} if drawn["with_repo"] else {}

    def outcome(call) -> str:
        try:
            result = call()
        except CorpusNotMaterializedError as exc:
            return "unfetchable" if "no fetch will place them" in str(exc) else "absent"
        return f"passed: {result!r}" if isinstance(result, bool) else "passed"

    refused = "unfetchable" if unfetchable else "absent" if absent else "passed"
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    assert outcome(lambda: require_materialized([path], **kwargs)) == refused
    assert outcome(lambda: require_materialized([path], fetch=True, **kwargs)) == refused
    assert outcome(lambda: ensure_corpus_paths([path], **kwargs)) == refused
    is_file = selection in _SHARED_UNIVERSE
    if is_file:
        read = "passed: True" if selection in drawn["present"] else refused if absent else "passed: False"
        assert outcome(lambda: fetch_locked_file(path)) == read
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")
    assert outcome(lambda: require_materialized([path], **kwargs)) == refused

    action = drawn["action"] if is_file or drawn["action"] != "read" else "ensure"
    if action == "read":
        expected = (
            "passed: True"
            if selection in drawn["present"] or (absent and not unfetchable)
            else "unfetchable" if unfetchable else "passed: False"
        )
        assert outcome(lambda: fetch_locked_file(path)) == expected
    elif action == "ensure":
        assert outcome(lambda: ensure_corpus_paths([path], **kwargs)) == ("unfetchable" if unfetchable else "passed")
    else:
        assert outcome(lambda: require_materialized([path], fetch=True, **kwargs)) == (
            "unfetchable" if unfetchable else "passed"
        )
    placed = set(drawn["present"]) | (set() if unfetchable else absent)
    for rel, data in _SHARED_UNIVERSE.items():
        where = home(rel)
        assert (where.is_file() and not where.is_symlink()) == (rel in placed), rel
        assert rel not in placed or where.read_bytes() == data
    # Nothing else was written, in either checkout.
    for root in (worktree, shared):
        written = {
            (Path(directory) / name).relative_to(root).as_posix()
            for directory, _dirs, names in os.walk(root / "data")
            for name in names
            if _placed_file(Path(directory) / name)  # a dangling link is listed as a name too
        }
        assert written == {rel for rel in placed if home(rel) == root / rel}, root


@PROPERTY_SETTINGS
@given(
    layout=st.sampled_from(["ordinary", "sharing", "nested"]),
    outer_locks=st.booleans(),
    owner_locks=st.booleans(),
    present=st.booleans(),
    fetch=st.booleans(),
    repo_hint=st.sampled_from([None, "outer", "owner"]),
)
@example(layout="nested", outer_locks=True, owner_locks=False, present=False, fetch=True, repo_hint="outer")
def test_broad_and_exact_selections_agree_for_every_checkout_layout(
    tmp_path_factory, monkeypatch, layout: str, outer_locks: bool, owner_locks: bool,
    present: bool, fetch: bool, repo_hint: str | None,
) -> None:
    """Every generated layout applies the same locks to an exact file and its enclosing selection."""
    base = tmp_path_factory.mktemp("selection-agreement")
    outer = _bare_checkout(base / "outer")
    if layout == "nested":
        owner = _bare_checkout(outer / f"{_NESTED_SOURCE_DIR}/vendored")
        outer_rel = f"{_NESTED_SOURCE_DIR}/vendored/{_NESTED_PROV}"
        broad = outer / _NESTED_SOURCE_DIR
    elif layout == "sharing":
        owner = _bare_checkout(base / "owner")
        (owner / "data/corpus/provisions").mkdir(parents=True)
        (outer / "data/corpus").mkdir(parents=True)
        (outer / "data/corpus/provisions").symlink_to(owner / "data/corpus/provisions", target_is_directory=True)
        outer_rel = _NESTED_PROV
        broad = outer / "data/corpus/provisions"
    else:
        owner, outer_rel, broad = outer, _NESTED_PROV, outer / "data/corpus/provisions"
    outer_bytes, owner_bytes, present_bytes = b"outer lock\n", b"owner lock\n", b"already present\n"
    if outer_locks:
        _lock_files(outer, {outer_rel: outer_bytes})
    if owner_locks and layout != "ordinary":
        _lock_files(owner, {_NESTED_PROV: owner_bytes})
    _serve(base, monkeypatch, {"outer": outer_bytes, "owner": owner_bytes})
    monkeypatch.chdir(outer)
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH", raising=False)
    kwargs = {} if repo_hint is None else {"repo": outer if repo_hint == "outer" else owner}
    path = outer / outer_rel
    owned = outer_locks if layout == "ordinary" else owner_locks
    any_lock = outer_locks or owned
    expected = "refused" if not present and any_lock and (not fetch or not owned) else "passed"
    outcomes = []
    for selection in (broad, path):
        path.unlink(missing_ok=True)
        if present:
            _write(owner, _NESTED_PROV, present_bytes)
        try:
            require_materialized([selection], fetch=fetch, **kwargs)
        except CorpusNotMaterializedError:
            outcomes.append("refused")
        else:
            outcomes.append("passed")
        placed = present or (fetch and owned)
        assert path.is_file() == placed
        if placed:
            assert path.read_bytes() == (present_bytes if present else outer_bytes if layout == "ordinary" else owner_bytes)
    assert outcomes[0] == outcomes[1], (layout, outcomes)
    assert outcomes == [expected, expected]


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
    # Which checkouts' locks name the path itself (when it is a lockable path).
    lockers = draw(st.sets(st.sampled_from(["repo", "other"])))
    if above == "dangling":  # nothing can be made below a dangling link
        return rel, None, False, above, depth, lockers
    return rel, draw(st.sampled_from(_LINK_KINDS)), draw(st.booleans()), above, depth, lockers


def _expected_naming(rel: str, link_kind: str | None, above: str | None):
    """Reference model of invariant 10 for ``repo/<rel>`` in the layouts above.

    Returns what ``repo`` and ``other`` name the path, what they name its
    realpath, whether a name is the symlinked file itself (lstat identity), and
    the protected places whose locks apply to it (invariant 11).
    A place is (checkout, name); the path stands at a place below each link on
    its way and reaches a place at its end. It names, in order of precedence:
    the last protected place a symlinked file stands at; the protected place
    any other path reaches, when it stands at no protected place or the last
    one has the same name (a link to the same path in another checkout); the
    last protected place it stands at; the place it reaches. The lock of every
    protected place it stands at or reaches applies.
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
    reached_protected = [reached] if reached is not None and is_protected_corpus_path(reached[1]) else []
    return named, physical, file_link and owner is not None, {*stands, *reached_protected}


def _bare_checkout(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "src" / "axiom_corpus").mkdir(parents=True)
    _git(path, "init", "-q")
    return path


_SHARED_SOURCE = "data/corpus/sources/nz/statute/v1/official/a"


@PROPERTY_SETTINGS
@given(_named_paths())
# Only the worktree's lock names an absent file below a sharing link (and a
# chain of them): the generator draws these rarely, and #881 read them as absent.
@example(drawn=(_SHARED_SOURCE, None, False, "another checkout", 2, {"repo"}))
@example(drawn=(_SHARED_SOURCE, None, False, "chain via another checkout", 2, {"repo"}))
@example(drawn=(_SHARED_SOURCE, None, False, "another checkout", 2, {"other"}))
def test_every_spelling_names_the_entry_it_reaches(tmp_path_factory, monkeypatch, drawn) -> None:
    """Invariant 10. ``relative`` answers the same for every spelling of the checkout,
    at most one checkout names a path at a protected path, a name reaches the
    directory entry the path reaches (the link itself for a symlinked file standing
    at a protected path), and the name follows the reference model: a directory link
    to the same path in another checkout is followed, and any other link at a
    protected path, a symlinked file included, names its own path. With fetching
    off, the helpers refuse the path exactly when it is not in place and the lock
    of a place it stands at or reaches names it (invariant 11)."""
    rel, link_kind, create, above, depth, lockers = drawn
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
    expected, physical, link_itself, lock_places = _expected_naming(rel, link_kind, above)
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

    scope = scope_for_path(rel)
    if scope is None:
        return  # no lock can name it
    checkouts = {"repo": repo, "other": other}
    for name in lockers:
        write_lock(checkouts[name], CorpusLock.from_entries(scope, [LockEntry(path=rel, sha256=_sha(b"x"), size=1)]))
    applies = any((name, rel) in lock_places for name in lockers)
    placed = path.is_file() and not path.is_symlink()
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    try:
        if applies and not placed:
            with pytest.raises(CorpusNotMaterializedError):
                require_materialized([path])
        else:
            require_materialized([path])
        if os.path.exists(path) and not link_itself:
            assert fetch_locked_file(path)
        elif applies:
            with pytest.raises(CorpusNotMaterializedError):
                fetch_locked_file(path)
        else:
            assert not fetch_locked_file(path)
    finally:
        monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH")


# Round 2: exact selections must retain every sharing and enclosing witness.


def _sharing_into_nested_witness(
    tmp_path: Path, monkeypatch, links: int, lock_holder: str
) -> tuple[dict[str, Path], Path, Path, str]:
    source = _init_repo(tmp_path / "source")
    nested = _init_repo(source / _NESTED_SOURCE_DIR / "vendored")
    worktree = _init_repo(tmp_path / "worktree")
    checkouts = {"source": source, "worktree": worktree, "nested": nested}
    target = source
    if links == 2:
        middle = _init_repo(tmp_path / "middle")
        (middle / "data/corpus").mkdir(parents=True)
        (middle / "data/corpus/sources").symlink_to(source / "data/corpus/sources", target_is_directory=True)
        checkouts["middle"] = middle
        target = middle
    (worktree / "data/corpus").mkdir(parents=True)
    (worktree / "data/corpus/sources").symlink_to(target / "data/corpus/sources", target_is_directory=True)
    rel = f"{_NESTED_SOURCE_DIR}/vendored/{_NESTED_PROV}"
    holder = checkouts[lock_holder]
    _lock_files(holder, {rel: SHARED_FILES[PROV]})
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(worktree)
    return checkouts, holder, nested, rel


def _assert_round2_witness_refusal(
    monkeypatch,
    action: str,
    path: Path,
    holder: Path,
    owner: Path,
    holder_name: str,
    kwargs: dict[str, Path] | None = None,
    owner_name: str = _NESTED_PROV,
) -> None:
    from axiom_corpus.corpus.io import iter_provisions

    for no_fetch in ("", "1"):
        monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", no_fetch)
        with pytest.raises(CorpusNotMaterializedError, match="absent and no fetch will place them") as refused:
            if action == "ensure":
                ensure_corpus_paths([path], **(kwargs or {}))
            elif action in {"require", "require-fetch"}:
                require_materialized([path], fetch=action == "require-fetch", **(kwargs or {}))
            elif action == "fetch-locked-file":
                fetch_locked_file(path)
            elif action == "load-provisions":
                load_provisions(path)
            elif action == "iter-provisions":
                tuple(iter_provisions(path))
            elif action == "resolve":
                resolve_corpus_path(path, **(kwargs or {}))
            else:
                raise AssertionError(action)
        message = str(refused.value)
        assert f"{holder_name}, which the lock of {holder} names" in message
        assert f"{owner} names that path" in message
        assert f"does not list {owner_name}" in message
        assert f"Lock that scope in {owner} and fetch it there" in message
        assert f"axiom-corpus-ingest corpus fetch --path {holder_name}` in {holder}" in message
        # Even though the remote holds the witness's bytes, only the owner may
        # fetch here, and its lock does not name this file.
        assert not (owner / _NESTED_PROV).exists()


@pytest.mark.parametrize("links,lock_holder", [(1, "worktree"), (2, "worktree"), (2, "middle")])
@pytest.mark.parametrize("repo_hint", [None, "worktree", "source"], ids=["no-repo", "worktree-repo", "source-repo"])
@pytest.mark.parametrize("selection", ["exact", "broad"])
@pytest.mark.parametrize("action", ["require", "require-fetch", "ensure"])
def test_every_sharing_lock_refuses_an_absent_file_inside_a_nested_checkout(
    tmp_path: Path, monkeypatch, links: int, lock_holder: str, repo_hint: str | None, selection: str, action: str
) -> None:
    checkouts, holder, owner, rel = _sharing_into_nested_witness(tmp_path, monkeypatch, links, lock_holder)
    path = checkouts["worktree"] / (rel if selection == "exact" else _NESTED_SOURCE_DIR)
    kwargs = {} if repo_hint is None else {"repo": checkouts[repo_hint]}
    _assert_round2_witness_refusal(monkeypatch, action, path, holder, owner, rel, kwargs)


@pytest.mark.parametrize("links,lock_holder", [(1, "worktree"), (2, "worktree"), (2, "middle")])
@pytest.mark.parametrize("action", ["require", "require-fetch", "ensure", "resolve"])
def test_a_bare_path_keeps_every_sharing_lock_when_the_worktree_repo_is_given(
    tmp_path: Path, monkeypatch, links: int, lock_holder: str, action: str
) -> None:
    checkouts, holder, owner, rel = _sharing_into_nested_witness(tmp_path, monkeypatch, links, lock_holder)
    _assert_round2_witness_refusal(
        monkeypatch, action, Path(rel), holder, owner, rel, {"repo": checkouts["worktree"]}
    )


@pytest.mark.parametrize("links,lock_holder", [(1, "worktree"), (2, "worktree"), (2, "middle")])
@pytest.mark.parametrize(
    "action,repo_hint",
    [
        ("fetch-locked-file", None),
        ("load-provisions", None),
        ("iter-provisions", None),
        ("resolve", None),
        ("resolve", "worktree"),
        ("resolve", "source"),
    ],
)
def test_exact_readers_keep_every_sharing_lock_above_a_nested_checkout(
    tmp_path: Path, monkeypatch, links: int, lock_holder: str, action: str, repo_hint: str | None
) -> None:
    checkouts, holder, owner, rel = _sharing_into_nested_witness(tmp_path, monkeypatch, links, lock_holder)
    kwargs = {} if repo_hint is None else {"repo": checkouts[repo_hint]}
    _assert_round2_witness_refusal(monkeypatch, action, checkouts["worktree"] / rel, holder, owner, rel, kwargs)


_ROUND2_SELECTION_ACTIONS = [
    (selection, action)
    for selection in ("exact", "broad")
    for action in ("require", "require-fetch", "ensure")
] + [("exact", action) for action in ("fetch-locked-file", "load-provisions", "iter-provisions", "resolve")]


@pytest.mark.parametrize("selection,action", _ROUND2_SELECTION_ACTIONS)
def test_an_enclosing_lock_survives_a_nested_checkouts_own_sharing_link(
    tmp_path: Path, monkeypatch, selection: str, action: str
) -> None:
    """Kill M3: the enclosing witness is absent from the resolved path."""
    outer = _init_repo(tmp_path / "outer")
    nested = _init_repo(outer / _NESTED_SOURCE_DIR / "vendored")
    owner = _init_repo(tmp_path / "owner")
    (owner / "data/corpus/provisions").mkdir(parents=True)
    (nested / "data/corpus").mkdir(parents=True)
    (nested / "data/corpus/provisions").symlink_to(owner / "data/corpus/provisions", target_is_directory=True)
    rel = f"{_NESTED_SOURCE_DIR}/vendored/{_NESTED_PROV}"
    _lock_files(outer, {rel: SHARED_FILES[PROV]})
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(outer)
    path = nested / _NESTED_PROV if selection == "exact" else nested / "data/corpus/provisions"
    _assert_round2_witness_refusal(monkeypatch, action, path, outer, owner, rel)


@pytest.mark.parametrize("selection,action", _ROUND2_SELECTION_ACTIONS)
def test_only_the_middle_of_three_nested_checkouts_can_witness_an_absent_file(
    tmp_path: Path, monkeypatch, selection: str, action: str
) -> None:
    """Kill M4: retaining only the outermost enclosing checkout loses the lock."""
    outer = _init_repo(tmp_path / "outer")
    middle = _init_repo(outer / _NESTED_SOURCE_DIR / "vendored")
    owner = _init_repo(middle / _NESTED_SOURCE_DIR / "vendored")
    rel = f"{_NESTED_SOURCE_DIR}/vendored/{_NESTED_PROV}"
    _lock_files(middle, {rel: SHARED_FILES[PROV]})
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(outer)
    path = owner / _NESTED_PROV if selection == "exact" else middle / _NESTED_SOURCE_DIR
    _assert_round2_witness_refusal(monkeypatch, action, path, middle, owner, rel)


@pytest.mark.parametrize(
    "action", ["require", "require-fetch", "ensure", "fetch-locked-file", "load-provisions", "iter-provisions", "resolve"]
)
def test_a_sharing_lock_applies_when_dotdot_returns_to_the_normalized_spelling(
    tmp_path: Path, monkeypatch, action: str
) -> None:
    """A sharing checkout visited before ``..`` still witnesses the final file."""
    worktree = _init_repo(tmp_path / "worktree")
    middle = _init_repo(tmp_path / "middle")
    provisions = "data/corpus/provisions"
    (worktree / provisions / "child").mkdir(parents=True)
    (middle / "data/corpus").mkdir(parents=True)
    (middle / provisions).symlink_to(worktree / provisions, target_is_directory=True)
    (worktree / provisions / "link").symlink_to(middle / provisions / "child", target_is_directory=True)
    _lock_files(middle, {_NESTED_PROV: SHARED_FILES[PROV]})
    _serve(tmp_path, monkeypatch, SHARED_FILES)
    monkeypatch.chdir(worktree)
    path = worktree / provisions / "link/../nz/statute/v1.jsonl"
    # The spelling enters middle's corpus, then returns to the same normalized
    # path in worktree. Equal final paths do not mean no sharing link was used.
    assert os.path.normpath(path) == os.path.realpath(path) == str(worktree / _NESTED_PROV)
    _assert_round2_witness_refusal(monkeypatch, action, path, middle, worktree, _NESTED_PROV)


# #884 round-3 review (Axiom eng hub, 2026-10-17): on APFS the sharing layout
# above, reached through another case of one directory, lost the worktree's
# lock, so the absent file inside the nested checkout read as empty. Each
# respelling reaches the same places; on a case-sensitive filesystem it names
# other, absent paths instead.
_SHARING_CASE_VARIANTS = {
    "the shared link": ("/sources/", "/SOURCES/"),
    "the worktree's data": ("data/", "DATA/"),
    "a directory below the link": ("/nz/", "/NZ/"),
    "the nested checkout's data": ("vendored/data/", "vendored/DATA/"),
    "the file": (".jsonl", ".JSONL"),
}
_SHARING_CASE_ACTIONS = [
    *((action, hint) for action in ("require", "require-fetch", "ensure") for hint in (None, "worktree", "source")),
    ("fetch-locked-file", None),
    ("load-provisions", None),
    ("iter-provisions", None),
    ("resolve", None),
    ("resolve", "worktree"),
]


def _respelled_in_sharing(tmp_path: Path, monkeypatch, links: int, lock_holder: str, variant: str):
    if not _folds_case_on_disk(tmp_path):
        pytest.skip("needs a case-insensitive filesystem")
    checkouts, holder, owner, rel = _sharing_into_nested_witness(tmp_path, monkeypatch, links, lock_holder)
    old, new = _SHARING_CASE_VARIANTS[variant]
    return checkouts, holder, owner, rel, rel.replace(old, new, 1)


def _owner_spelling(spelled: str) -> str:
    """The nested checkout's name for ``spelled``: as spelled, since its own lock
    (it has none) cannot say otherwise."""
    return spelled.split("/vendored/", 1)[1]


@pytest.mark.parametrize("variant", list(_SHARING_CASE_VARIANTS))
@pytest.mark.parametrize("action,repo_hint", _SHARING_CASE_ACTIONS)
def test_every_sharing_lock_refuses_an_absent_file_spelled_in_another_case(
    tmp_path: Path, monkeypatch, variant: str, action: str, repo_hint: str | None
) -> None:
    checkouts, holder, owner, rel, spelled = _respelled_in_sharing(tmp_path, monkeypatch, 1, "worktree", variant)
    kwargs = {} if repo_hint is None else {"repo": checkouts[repo_hint]}
    _assert_round2_witness_refusal(
        monkeypatch, action, checkouts["worktree"] / spelled, holder, owner, rel, kwargs, _owner_spelling(spelled)
    )


@pytest.mark.parametrize("links,lock_holder", [(2, "worktree"), (2, "middle")])
@pytest.mark.parametrize("action,repo_hint", _SHARING_CASE_ACTIONS)
def test_every_sharing_lock_in_a_chain_refuses_an_absent_file_spelled_in_another_case(
    tmp_path: Path, monkeypatch, links: int, lock_holder: str, action: str, repo_hint: str | None
) -> None:
    checkouts, holder, owner, rel, spelled = _respelled_in_sharing(
        tmp_path, monkeypatch, links, lock_holder, "the shared link"
    )
    kwargs = {} if repo_hint is None else {"repo": checkouts[repo_hint]}
    _assert_round2_witness_refusal(monkeypatch, action, checkouts["worktree"] / spelled, holder, owner, rel, kwargs)


@pytest.mark.parametrize("variant", ["the shared link", "the worktree's data", "a directory below the link"])
@pytest.mark.parametrize("action", ["require", "require-fetch", "ensure"])
def test_a_directory_spelled_in_another_case_keeps_every_sharing_lock(
    tmp_path: Path, monkeypatch, variant: str, action: str
) -> None:
    checkouts, holder, owner, rel, _spelled = _respelled_in_sharing(tmp_path, monkeypatch, 1, "worktree", variant)
    old, new = _SHARING_CASE_VARIANTS[variant]
    directory = checkouts["worktree"] / _NESTED_SOURCE_DIR.replace(old, new, 1)
    _assert_round2_witness_refusal(monkeypatch, action, directory, holder, owner, rel)


@pytest.mark.parametrize("action", ["require", "require-fetch", "ensure", "resolve"])
def test_a_bare_path_spelled_in_another_case_keeps_every_sharing_lock(tmp_path: Path, monkeypatch, action: str) -> None:
    checkouts, holder, owner, rel, spelled = _respelled_in_sharing(
        tmp_path, monkeypatch, 1, "worktree", "the shared link"
    )
    _assert_round2_witness_refusal(monkeypatch, action, Path(spelled), holder, owner, rel, {"repo": checkouts["worktree"]})
