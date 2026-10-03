"""Corpus bytes outside git: lock files, content cache, fetch, push and migrate.

Invariants (docs/corpus-storage.md) are exercised as properties with
Hypothesis alongside example tests:

1. lock round trip and canonical form;
2. scope partition (every entry lies in its lock's scope, once);
3. conservation at migration (locks == tracked blobs, byte for byte);
4. fetch fidelity (materialized bytes hash to the lock, or nothing changes);
5. cache integrity (objects hash to their names);
6. idempotence (a second fetch changes nothing);
7. no links (materialized files are independent regular files).
"""

from __future__ import annotations

import hashlib
import json
import os
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
    LOCK_ROOT,
    CorpusLock,
    LockEntry,
    LockFormatError,
    LockSet,
    diff_lock_sets,
    fold_collisions,
    hash_tree_blobs,
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
from axiom_corpus.corpus.resolver import (
    CorpusNotMaterializedError,
    CorpusResolver,
    corpus_inputs_from_args,
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


def test_repro_script_fetches_the_locked_inputs_it_reads_and_not_its_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    from axiom_corpus.corpus import resolver as corpus_resolver
    from scripts.repro import us_ny_tax_article_22_line_structure as repro

    released = f"us-ny/statute/{repro.SOURCE_VERSION}"
    successor = f"us-ny/statute/{repro.VERSION}"
    # The reproduction reads the released scope's sources, inventory and provisions.
    inputs = {
        f"data/corpus/sources/{released}/official-documents/601.html": b"<html>601</html>",
        f"data/corpus/sources/{released}/official-documents/606.html": b"<html>606</html>",
        f"data/corpus/inventory/{released}.json": b'{"items": []}\n',
        f"data/corpus/provisions/{released}.jsonl": b'{"citation_path": "a"}\n',
    }
    # It never reads the released coverage, and it writes the successor scope,
    # whose version starts with the released one.
    others = {
        f"data/corpus/coverage/{released}.json": b'{"complete": true}\n',
        f"data/corpus/sources/{successor}/official-documents/601.html": b"<html>new</html>",
        f"data/corpus/inventory/{successor}.json": b'{"items": [1]}\n',
        f"data/corpus/provisions/{successor}.jsonl": b'{"citation_path": "b"}\n',
        f"data/corpus/coverage/{successor}.json": b'{"complete": false}\n',
    }
    files = {**inputs, **others}
    repo = _init_repo(tmp_path / "repo")
    remote, _fake = _remote({content_key(_sha(d)): d for d in files.values()})
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH", raising=False)

    def use_fresh_resolver() -> None:
        resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[remote])
        monkeypatch.setitem(corpus_resolver._RESOLVERS, repo.resolve(), resolver)

    def present() -> set[str]:
        root = repo / "data" / "corpus"
        return {p.relative_to(repo).as_posix() for p in root.rglob("*") if p.is_file()}

    use_fresh_resolver()
    repro.ensure_corpus_inputs(repo=repo)
    assert not (repo / "data").exists()

    for scope in {scope_for_path(path) for path in files}:
        write_lock(repo, _scope_lock({p: d for p, d in files.items() if scope_for_path(p) == scope}, scope))
    use_fresh_resolver()
    repro.ensure_corpus_inputs(repo=repo, source_base=tmp_path / "elsewhere")
    assert not (repo / "data").exists()

    repro.ensure_corpus_inputs(repo=repo)
    assert present() == set(inputs)
    assert all((repo / path).read_bytes() == data for path, data in inputs.items())

    # main() always passes --source-base (default data/corpus), which the helper
    # resolves; a symlinked spelling of the checkout resolves to the same files.
    (tmp_path / "link").symlink_to(repo)
    for source_base in (repo / "data" / "corpus", tmp_path / "link" / "data" / "corpus"):
        for path in inputs:
            (repo / path).unlink()
        use_fresh_resolver()
        repro.ensure_corpus_inputs(repo=repo, source_base=source_base)
        assert present() == set(inputs)

    # From another directory, a relative --source-base names <cwd>/data/corpus,
    # which is what the script reads; that is outside the checkout.
    for path in inputs:
        (repo / path).unlink()
    monkeypatch.chdir(tmp_path)
    use_fresh_resolver()
    repro.ensure_corpus_inputs(repo=repo, source_base=Path("data/corpus"))
    assert present() == set()


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
