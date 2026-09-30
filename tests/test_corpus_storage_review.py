"""Regression tests for the #769 review findings (corpus bytes outside git).

Each test names the finding it pins. See docs/corpus-storage.md.
"""

from __future__ import annotations

import errno
import hashlib
import os
import subprocess
import threading
import unicodedata
from io import BytesIO
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from axiom_corpus.corpus import content_store, corpus_cli
from axiom_corpus.corpus import resolver as resolver_module
from axiom_corpus.corpus.cli import _corpus_wide_prefixes, build_parser
from axiom_corpus.corpus.cli import main as cli_main
from axiom_corpus.corpus.content_store import (
    ContentCache,
    GitBlobSource,
    R2ObjectStore,
    content_key,
    materialize,
    materialize_entry,
    publish_no_replace,
)
from axiom_corpus.corpus.corpus_locks import (
    FETCH_TEMP_DIR,
    CorpusLock,
    LockEntry,
    LockFormatError,
    LockSet,
    load_locks,
    lock_from_worktree,
    parse_lock,
    serialize_lock,
    write_lock,
)
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.resolver import (
    CorpusNotMaterializedError,
    CorpusResolver,
    InvalidCorpusLocksError,
    ensure_corpus_paths,
)

SCOPE = ("nz", "statute", "2026-07-10")
FILES = {
    "data/corpus/sources/nz/statute/2026-07-10/official/act.html": b"<html>Act 1</html>\n",
    "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml": b"<s>2</s>",
    "data/corpus/inventory/nz/statute/2026-07-10.json": b'{"items": []}\n',
    "data/corpus/provisions/nz/statute/2026-07-10.jsonl": b'{"citation_path":"nz/statute/a"}\n',
    "data/corpus/coverage/nz/statute/2026-07-10.json": b'{"complete": true}\n',
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _write(repo: Path, rel: str, data: bytes) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _lock(files: dict[str, bytes] = FILES) -> CorpusLock:
    return CorpusLock.from_entries(
        SCOPE, [LockEntry(path=p, sha256=_sha(d), size=len(d)) for p, d in files.items()]
    )


class FakeR2:
    def __init__(self, objects: dict[str, bytes] | None = None):
        self.objects = dict(objects or {})
        self._lock = threading.Lock()

    def get_object(self, **kwargs):
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


def _remote(objects: dict[str, bytes] | None = None) -> R2ObjectStore:
    return R2ObjectStore(bucket="axiom-corpus", client=FakeR2(objects))


def _full_remote() -> R2ObjectStore:
    return _remote({content_key(_sha(d)): d for d in FILES.values()})


@pytest.fixture(autouse=True)
def no_real_r2(monkeypatch, tmp_path: Path):
    """Keep tests off the developer's R2 credentials and shared cache."""

    def refuse(cls, **_kwargs):
        raise RuntimeError("R2 is disabled in tests")

    monkeypatch.setattr(content_store.R2ObjectStore, "from_environment", classmethod(refuse))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "default-cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})


# Opus B1 ------------------------------------------------------------------------


def test_subcommand_marker_survives_a_command_flag() -> None:
    """sign-ingest-manifest's --command overwrote args.command, so the auto-fetch
    exemption for signing never applied."""
    args = build_parser().parse_args(
        [
            "sign-ingest-manifest",
            "--jurisdiction", "nz",
            "--document-class", "statute",
            "--version", "v1",
            "--command", "axiom-corpus-ingest extract-nz-legislation",
        ]
    )
    assert args.command == "axiom-corpus-ingest extract-nz-legislation"
    assert args._cli_command == "sign-ingest-manifest"


def test_signing_never_refetches_a_deleted_file(tmp_path: Path, monkeypatch) -> None:
    import json
    from base64 import b64encode

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "lock")
    for rel, data in FILES.items():
        _write(repo, rel, data)
    deleted = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    (repo / deleted).unlink()
    # The locked bytes are fetchable, so a wrongly exempted hook *would* restore them.
    monkeypatch.setattr(
        content_store.R2ObjectStore,
        "from_environment",
        classmethod(lambda cls, **_k: _full_remote()),
    )
    key = Ed25519PrivateKey.generate()
    private = b64encode(
        key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    ).decode("ascii")
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY", private)
    monkeypatch.chdir(repo)
    status = cli_main(
        [
            "sign-ingest-manifest",
            "--repo", str(repo),
            "--jurisdiction", "nz",
            "--document-class", "statute",
            "--version", "2026-07-10",
            "--command", "x",
            "--deleted-file", deleted,
            "--lock",
        ]
    )
    assert status == 0
    assert not (repo / deleted).exists()
    assert deleted not in load_locks(repo).by_path
    manifest = json.loads((repo / ".axiom/ingest-manifests/nz/statute/2026-07-10.json").read_text())
    assert {"path": deleted, "deleted": True} in manifest["applied_files"]


# Astra 1 / Opus S8 --------------------------------------------------------------


def test_fetch_never_replaces_a_file_written_while_bytes_were_in_flight(tmp_path: Path, monkeypatch) -> None:
    lock = _lock()
    entry = next(e for e in lock.files if e.path.endswith(".jsonl"))
    repo = tmp_path / "repo"
    real_ensure = content_store.ensure_cached

    def ensure_then_race(entry_arg, cache, sources):
        result = real_ensure(entry_arg, cache, sources)
        _write(repo, entry_arg.path, b"extractor output written meanwhile")
        return result

    monkeypatch.setattr(content_store, "ensure_cached", ensure_then_race)
    state, _source, _method = materialize_entry(
        repo, entry, ContentCache(tmp_path / "cache"), [_full_remote()]
    )
    assert state == "modified"
    assert (repo / entry.path).read_bytes() == b"extractor output written meanwhile"


# Opus S2 ------------------------------------------------------------------------


def test_fetch_temporary_files_never_land_inside_a_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    assert materialize(repo, _lock().files, ContentCache(tmp_path / "cache"), [_full_remote()]).ok
    names = [p.as_posix() for p in (repo / "data" / "corpus").rglob("*") if ".corpus-fetch-" in p.name]
    assert all(FETCH_TEMP_DIR in name for name in names)
    leftover = repo / "data/corpus/sources/nz/statute/2026-07-10/official/.act.html.corpus-fetch-1-2"
    leftover.write_bytes(b"partial")
    with pytest.raises(LockFormatError, match="interrupted fetch"):
        lock_from_worktree(repo, SCOPE)


# Opus S7 ------------------------------------------------------------------------


def test_a_corrupt_cache_object_is_refetched_not_copied(tmp_path: Path) -> None:
    lock = _lock()
    cache_root = tmp_path / "cache"
    assert materialize(tmp_path / "first", lock.files, ContentCache(cache_root), [_full_remote()]).ok
    victim = next(e for e in lock.files if e.size > 4)
    obj = ContentCache(cache_root).object_path(victim.sha256)
    os.chmod(obj, 0o644)
    obj.write_bytes(b"X" * victim.size)  # same size, wrong bytes
    report = materialize(tmp_path / "second", lock.files, ContentCache(cache_root), [_full_remote()])
    assert report.ok
    assert (tmp_path / "second" / victim.path).read_bytes() == FILES[victim.path]
    assert ContentCache(cache_root).verify_object(victim.sha256)


# Astra 4 ------------------------------------------------------------------------


def test_a_partly_fetched_sources_directory_is_rolled_back(tmp_path: Path) -> None:
    sources = [e for e in _lock().files if "/sources/" in e.path]
    remote = _remote({content_key(sources[0].sha256): FILES[sources[0].path]})
    repo = tmp_path / "repo"
    report = materialize(repo, sources, ContentCache(tmp_path / "cache"), [remote], workers=1)
    assert set(report.failed) == {sources[1].path}
    assert report.rolled_back == [sources[0].path]
    assert not (repo / sources[0].path).exists()


def test_resolving_one_source_fetches_its_whole_directory(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[_full_remote()])
    resolver.resolve("data/corpus/sources/nz/statute/2026-07-10/official/act.html")
    assert (repo / "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml").is_file()


# Opus S3 ------------------------------------------------------------------------


def test_no_fetch_mode_refuses_to_read_a_locked_absent_file_as_empty(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    with pytest.raises(CorpusNotMaterializedError, match="fetching is off"):
        load_provisions(repo / "data/corpus/provisions/nz/statute/2026-07-10.jsonl")
    assert load_provisions(repo / "data/corpus/provisions/nz/statute/unlocked.jsonl") == ()


# Astra 6 ------------------------------------------------------------------------


def test_malformed_locks_fail_closed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    path = write_lock(repo, _lock())
    path.write_text(path.read_text().replace('"files": [', '"files":['))
    with pytest.raises(InvalidCorpusLocksError):
        ensure_corpus_paths(["data/corpus/provisions"], repo=repo)
    for rel, data in FILES.items():
        _write(repo, rel, data)
    with pytest.raises(corpus_cli.LockRefusedError, match="invalid"):
        corpus_cli.lock_scopes(repo, [SCOPE], cache=ContentCache(tmp_path / "cache"))


# Astra 7 ------------------------------------------------------------------------


def test_locking_refuses_a_symlinked_scope_directory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "doc.html").write_bytes(b"not ours")
    link = repo / "data/corpus/sources/nz/statute/2026-07-10"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    with pytest.raises(LockFormatError, match="symlink"):
        lock_from_worktree(repo, SCOPE)


# Opus nit (non-ASCII) -------------------------------------------------------------


def test_non_ascii_paths_lock_in_nfc_only() -> None:
    nfc = unicodedata.normalize("NFC", "data/corpus/sources/de/statute/v1/gesetz-§-ä.html")
    lock = CorpusLock.from_entries(("de", "statute", "v1"), [LockEntry(nfc, "0" * 64, 1)])
    payload = serialize_lock(lock)
    assert payload.isascii() and parse_lock(payload) == lock
    with pytest.raises(LockFormatError):
        LockEntry(unicodedata.normalize("NFD", nfc), "0" * 64, 1)
    with pytest.raises(LockFormatError):
        LockEntry("data/corpus/sources/de/statute/v1/a​b.html", "0" * 64, 1)


# Opus S5 / Astra 10 ---------------------------------------------------------------


def test_migrate_refuses_dirty_protected_paths_and_other_refs(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    for rel, data in FILES.items():
        _write(repo, rel, data)
    _git(repo, "add", "-f", *FILES)
    _git(repo, "commit", "-q", "-m", "track corpus")
    monkeypatch.chdir(repo)
    edited = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
    (repo / edited).write_bytes(b'{"edited": true}\n')
    assert cli_main(["corpus", "migrate", "--repo", str(repo)]) == 2
    _git(repo, "add", "-f", edited)
    assert cli_main(["corpus", "migrate", "--repo", str(repo)]) == 2
    _git(repo, "commit", "-q", "-m", "commit the edit")
    assert cli_main(["corpus", "migrate", "--repo", str(repo), "--ref", "HEAD~1"]) == 2
    assert cli_main(["corpus", "migrate", "--repo", str(repo), "--ref", "HEAD~1", "--dry-run"]) == 0
    assert cli_main(["corpus", "migrate", "--repo", str(repo)]) == 0
    assert load_locks(repo).by_path[edited].sha256 == _sha(b'{"edited": true}\n')


# Astra 12 -------------------------------------------------------------------------


@pytest.mark.parametrize("rename_noreplace", [True, False], ids=["rename-noreplace", "exclusive-copy"])
def test_publish_without_hardlinks_still_never_replaces(
    tmp_path: Path, monkeypatch, rename_noreplace: bool
) -> None:
    def no_links(*_args, **_kwargs):
        raise OSError(errno.EPERM, "no hardlinks here")

    monkeypatch.setattr(content_store.os, "link", no_links)
    if not rename_noreplace:
        monkeypatch.setattr(content_store, "_RENAME_NOREPLACE", None)
    target = tmp_path / "object"
    first = tmp_path / "a"
    first.write_bytes(b"first writer")
    assert publish_no_replace(first, target)
    second = tmp_path / "b"
    second.write_bytes(b"second writer")
    assert not publish_no_replace(second, target)
    assert target.read_bytes() == b"first writer"


# Opus nit (git spawns) ------------------------------------------------------------


def test_git_source_serves_many_blobs_from_one_process(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    for rel, data in FILES.items():
        _write(repo, rel, data)
    _git(repo, "add", "-f", *FILES)
    _git(repo, "commit", "-q", "-m", "track")
    source = GitBlobSource(repo)
    try:
        for rel, data in FILES.items():
            oid = _git(repo, "rev-parse", f"HEAD:{rel}")
            chunks = source.open(LockEntry(rel, _sha(data), len(data), git_blob=oid))
            assert chunks is not None and b"".join(chunks) == data
        missing = LockEntry(next(iter(FILES)), "0" * 64, 1, git_blob="1" * 40)
        assert source.open(missing) is None
    finally:
        source.close()


# #770 finding ---------------------------------------------------------------------


def test_relative_paths_resolve_through_symlinked_spellings(tmp_path: Path) -> None:
    real = _init_repo(tmp_path / "real")
    alias = tmp_path / "alias"
    alias.symlink_to(real)
    resolver = CorpusResolver(real, sources=[])
    assert resolver.relative(alias / "data/corpus/provisions/x.jsonl") == "data/corpus/provisions/x.jsonl"


# Opus S4 / Astra 3 ----------------------------------------------------------------


def test_corpus_wide_reports_recognize_an_absolute_base(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(["artifact-report", "--base", str(repo / "data/corpus"), "--version", "v1"])
    prefixes = {p.relative_to(repo).as_posix().rstrip("/") for p in _corpus_wide_prefixes(args, "artifact-report")}
    assert prefixes == {
        "data/corpus/sources",
        "data/corpus/inventory",
        "data/corpus/provisions",
        "data/corpus/coverage",
    }


# =========================================================================== round 2


# Astra r2-1 / Opus r2-S4: rollback removes only what this call placed -------------


def _failing_sibling_fetch(tmp_path: Path, monkeypatch, rewrite) -> tuple[Path, LockEntry, object]:
    """Fetch two sources where the second fails; ``rewrite`` runs just before it."""
    sources = [e for e in _lock().files if "/sources/" in e.path]
    first, second = sources
    repo = tmp_path / "repo"
    remote = _remote({content_key(first.sha256): FILES[first.path]})
    real_ensure = content_store.ensure_cached

    def ensure(entry_arg, cache, sources_arg):
        if entry_arg.path == second.path:
            rewrite(repo / first.path)
        return real_ensure(entry_arg, cache, sources_arg)

    monkeypatch.setattr(content_store, "ensure_cached", ensure)
    report = materialize(repo, sources, ContentCache(tmp_path / "cache"), [remote], workers=1)
    assert set(report.failed) == {second.path}
    return repo, first, report


def test_rollback_keeps_a_file_an_extractor_rewrote_in_place(tmp_path: Path, monkeypatch) -> None:
    repo, first, report = _failing_sibling_fetch(
        tmp_path, monkeypatch, lambda path: path.write_bytes(b"extractor output")
    )
    assert (repo / first.path).read_bytes() == b"extractor output"
    assert report.rolled_back == [] and first.path in report.modified


def test_rollback_keeps_a_file_another_writer_replaced(tmp_path: Path, monkeypatch) -> None:
    def replace(path: Path) -> None:
        tmp = path.with_name("replacement")
        tmp.write_bytes(FILES[first_path])  # same bytes, new file
        os.replace(tmp, path)

    first_path = next(p for p in FILES if "/sources/" in p)
    repo, first, report = _failing_sibling_fetch(tmp_path, monkeypatch, replace)
    assert (repo / first.path).read_bytes() == FILES[first.path]
    assert report.rolled_back == []


def test_rollback_still_removes_an_untouched_placed_file(tmp_path: Path, monkeypatch) -> None:
    repo, first, report = _failing_sibling_fetch(tmp_path, monkeypatch, lambda _path: None)
    assert report.rolled_back == [first.path]
    assert not (repo / first.path).exists()


# Astra r2-3 / Opus r2-S2: a wrong-size cache object is repaired ------------------------


def test_a_truncated_cache_object_is_replaced_by_verified_bytes(tmp_path: Path) -> None:
    lock = _lock()
    cache_root = tmp_path / "cache"
    assert materialize(tmp_path / "first", lock.files, ContentCache(cache_root), [_full_remote()]).ok
    victim = next(e for e in lock.files if e.size > 4)
    obj = ContentCache(cache_root).object_path(victim.sha256)
    os.chmod(obj, 0o644)
    obj.write_bytes(b"bad")  # wrong size
    report = materialize(tmp_path / "second", lock.files, ContentCache(cache_root), [_full_remote()])
    assert report.ok
    assert (tmp_path / "second" / victim.path).read_bytes() == FILES[victim.path]
    assert ContentCache(cache_root).verify_object(victim.sha256)


def test_publish_replaces_a_corrupt_object_that_won_the_race(tmp_path: Path) -> None:
    data = b"verified bytes"
    sha = _sha(data)
    cache = ContentCache(tmp_path / "cache")
    target = cache.object_path(sha)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"X" * len(data))  # appeared after this writer's usable() check
    tmp = tmp_path / "tmp-object"
    tmp.write_bytes(data)
    assert cache._publish(tmp, target, sha, len(data)) == target
    assert target.read_bytes() == data


# Astra r2-4 / Opus r2-S3: the exclusive-copy fallback never leaves partial bytes -------


def _no_links_no_noreplace(monkeypatch) -> None:
    def no_links(*_args, **_kwargs):
        raise OSError(errno.EPERM, "no hardlinks here")

    monkeypatch.setattr(content_store.os, "link", no_links)
    monkeypatch.setattr(content_store, "_RENAME_NOREPLACE", None)


def test_locked_rename_publication_never_exposes_partial_or_mixed_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    """Round 3 (exFAT): concurrent publishers of one object, with neither
    hardlinks nor a no-replace rename, leave exactly one writer's full bytes."""
    _no_links_no_noreplace(monkeypatch)
    target = tmp_path / "object"
    payloads = {i: bytes([i]) * (64 * 1024) for i in range(8)}
    temps = {}
    for i, data in payloads.items():
        temps[i] = tmp_path / f"tmp-{i}"
        temps[i].write_bytes(data)
    barrier = threading.Barrier(len(temps))
    results = {}
    seen_partial = []
    real_copy = content_store.shutil.copyfileobj
    real_rename = content_store.os.rename

    def observe() -> None:
        # Whenever bytes move, the target is absent or holds one full payload.
        if target.exists() and target.read_bytes() not in payloads.values():
            seen_partial.append(target.stat().st_size)

    def copy(src, dst, *args):
        observe()
        return real_copy(src, dst, *args)

    def rename(src, dst):
        observe()
        return real_rename(src, dst)

    monkeypatch.setattr(content_store.shutil, "copyfileobj", copy)
    monkeypatch.setattr(content_store.os, "rename", rename)

    def publish(i: int) -> None:
        barrier.wait()
        results[i] = publish_no_replace(temps[i], target)

    threads = [threading.Thread(target=publish, args=(i,)) for i in temps]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    winners = [i for i, won in results.items() if won]
    assert len(winners) == 1
    assert target.read_bytes() == payloads[winners[0]]
    assert seen_partial == []  # the old exclusive-copy fallback exposed a growing file
    assert not any("corpus-fetch-lock" in p.name for p in tmp_path.iterdir())  # every lock released


def test_a_stale_publish_lock_is_broken(tmp_path: Path, monkeypatch) -> None:
    _no_links_no_noreplace(monkeypatch)
    target = tmp_path / "object"
    lock = content_store.publish_lock_path(target, tmp_path)
    lock.write_bytes(b"")
    old = content_store.time.time() - 2 * content_store.PUBLISH_LOCK_STALE_SECONDS
    os.utime(lock, (old, old))
    tmp = tmp_path / "tmp"
    tmp.write_bytes(b"bytes")
    assert publish_no_replace(tmp, target)
    assert target.read_bytes() == b"bytes" and not lock.exists()


def test_publication_across_filesystems_copies_beside_the_target(tmp_path: Path, monkeypatch) -> None:
    """Round 3 nit: EXDEV used to raise instead of falling back."""

    def cross_device(*_args, **_kwargs):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    real_link = os.link
    calls = []

    def link(src, dst):
        calls.append(src)
        if len(calls) == 1:
            cross_device()
        return real_link(src, dst)

    monkeypatch.setattr(content_store.os, "link", link)
    siblings = []
    real_sibling = content_store._publish_via_sibling

    def spy(tmp, target, *args):
        siblings.append(target)
        return real_sibling(tmp, target, *args)

    monkeypatch.setattr(content_store, "_publish_via_sibling", spy)
    target = tmp_path / "dest" / "object"
    target.parent.mkdir()
    tmp = tmp_path / "elsewhere"
    tmp.write_bytes(b"cross-device bytes")
    assert publish_no_replace(tmp, target)
    assert siblings == [target]  # copied beside the target, then linked into place
    assert target.read_bytes() == b"cross-device bytes"
    assert sorted(p.name for p in target.parent.iterdir()) == ["object"]


def test_an_unsupported_noreplace_rename_falls_back_to_the_locked_rename(
    tmp_path: Path, monkeypatch
) -> None:
    def no_links(*_args, **_kwargs):
        raise OSError(errno.EPERM, "no hardlinks here")

    monkeypatch.setattr(content_store.os, "link", no_links)
    monkeypatch.setattr(content_store, "_RENAME_NOREPLACE", lambda _src, _dst: errno.ENOTSUP)
    locked = []
    real = content_store._publish_locked_rename

    def spy(tmp, target, *args):
        locked.append(target)
        return real(tmp, target, *args)

    monkeypatch.setattr(content_store, "_publish_locked_rename", spy)
    tmp = tmp_path / "tmp"
    tmp.write_bytes(b"x")
    assert publish_no_replace(tmp, tmp_path / "object")
    assert locked == [tmp_path / "object"]


# Opus r2-N4: interrupted fetches' temporaries are cleaned up ----------------------------


def test_stale_fetch_temporaries_are_removed_but_fresh_clones_are_not(
    tmp_path: Path, monkeypatch
) -> None:
    """Round 3: a clone keeps the cache object's old mtime, so age is judged by ctime."""
    monkeypatch.setattr(content_store, "_PRUNED_TMP_DIRS", set())
    monkeypatch.setattr(content_store, "STALE_FETCH_TEMP_SECONDS", 1.0)
    repo = tmp_path / "repo"
    tmp_dir = repo / FETCH_TEMP_DIR
    tmp_dir.mkdir(parents=True)
    stale = tmp_dir / "act.html.corpus-fetch-old"
    stale.write_bytes(b"old")
    content_store.time.sleep(1.5)
    in_flight = tmp_dir / "act.html.corpus-fetch-new"
    in_flight.write_bytes(b"new")
    two_days_ago = content_store.time.time() - 2 * 24 * 3600
    os.utime(in_flight, (two_days_ago, two_days_ago))  # what clonefile leaves
    assert materialize(repo, _lock().files, ContentCache(tmp_path / "cache"), [_full_remote()]).ok
    assert not stale.exists() and in_flight.exists()


# Astra r2 table (Astra 4): an existing source still brings its siblings --------------


def test_resolving_a_present_source_fetches_its_missing_siblings(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    present = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    sibling = "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml"
    _write(repo, present, FILES[present])
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[_full_remote()])
    assert resolver.resolve(present) == repo / present
    assert (repo / sibling).read_bytes() == FILES[sibling]


def test_resolving_a_present_source_with_fetching_off_refuses_a_partial_scope(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    present = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    _write(repo, present, FILES[present])
    monkeypatch.setenv("AXIOM_CORPUS_NO_FETCH", "1")
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[_full_remote()])
    with pytest.raises(CorpusNotMaterializedError, match="fetching is off"):
        resolver.resolve(present)


# Opus r2-S4: the resolver re-checks what a concurrent rollback removed ------------------


def test_ensure_refetches_files_removed_while_it_ran(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    victim = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
    real = resolver_module.materialize
    calls = []

    def materialize_then_lose_one(*args, **kwargs):
        report = real(*args, **kwargs)
        calls.append(len(args[1]))
        if len(calls) == 1:
            (repo / victim).unlink()  # another process's rollback
        return report

    monkeypatch.setattr(resolver_module, "materialize", materialize_then_lose_one)
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[_full_remote()])
    resolver.ensure_scopes([SCOPE])
    assert (repo / victim).read_bytes() == FILES[victim]
    assert calls == [len(FILES), 1]


def test_ensure_gives_up_when_files_keep_disappearing(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    victim = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
    real = resolver_module.materialize

    def materialize_then_lose_one(*args, **kwargs):
        report = real(*args, **kwargs)
        (repo / victim).unlink(missing_ok=True)
        return report

    monkeypatch.setattr(resolver_module, "materialize", materialize_then_lose_one)
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[_full_remote()])
    with pytest.raises(CorpusNotMaterializedError, match="disappeared"):
        resolver.ensure_scopes([SCOPE])


# Astra r2-10 / Opus r2-N1: unread R2 bodies are closed ----------------------------------


def test_closing_an_unread_r2_stream_closes_its_body() -> None:
    body = BytesIO(b"payload")
    content_store._close(content_store._iter_body(body))
    assert body.closed


def test_an_r2_body_is_closed_when_another_worker_cached_it_first(tmp_path: Path) -> None:
    data = FILES["data/corpus/provisions/nz/statute/2026-07-10.jsonl"]
    cache = ContentCache(tmp_path / "cache")
    cache.add_stream([data], sha256=_sha(data), size=len(data))
    body = BytesIO(data)
    cache.add_stream(content_store._iter_body(body), sha256=_sha(data), size=len(data))
    assert body.closed


# Opus r2-S5: git blobs stream in chunks and an abandoned stream frees the process -------


def test_git_source_streams_large_blobs_and_survives_an_abandoned_stream(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    big = os.urandom(content_store.CHUNK_SIZE * 2 + 17)
    rel = "data/corpus/sources/nz/statute/2026-07-10/official/big.pdf"
    small_rel = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
    _write(repo, rel, big)
    _write(repo, small_rel, FILES[small_rel])
    _git(repo, "add", "-f", rel, small_rel)
    _git(repo, "commit", "-q", "-m", "track")
    big_entry = LockEntry(rel, _sha(big), len(big), git_blob=_git(repo, "rev-parse", f"HEAD:{rel}"))
    small = FILES[small_rel]
    small_entry = LockEntry(
        small_rel, _sha(small), len(small), git_blob=_git(repo, "rev-parse", f"HEAD:{small_rel}")
    )
    source = GitBlobSource(repo)
    try:
        chunks = source.open(big_entry)
        assert chunks is not None
        first = next(iter(chunks))
        assert len(first) <= content_store.CHUNK_SIZE < len(big)
        content_store._close(chunks)  # abandoned mid-blob
        again = source.open(small_entry)
        assert again is not None and b"".join(again) == small
        whole = source.open(big_entry)
        assert whole is not None and b"".join(whole) == big
    finally:
        source.close()


# Astra r2-11: invalid selectors are usage errors, not tracebacks -------------------------


def test_invalid_scope_selectors_exit_cleanly(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    monkeypatch.chdir(repo)
    assert cli_main(["corpus", "lock", "--repo", str(repo), "NZ/statute/v1"]) == 2
    assert "scope must be" in capsys.readouterr().err
    for command in (["corpus", "status"], ["corpus", "fetch"]):
        with pytest.raises(SystemExit) as stopped:
            cli_main([*command, "--repo", str(repo), "NZ/statute/v1"])
        assert stopped.value.code == 2
        assert "scope must be" in capsys.readouterr().err
    # A well-formed selector that matches no lock is a typo, not an empty fetch.
    for command in (["corpus", "status"], ["corpus", "fetch"]):
        with pytest.raises(SystemExit) as stopped:
            cli_main([*command, "--repo", str(repo), "nz/statut"])
        assert stopped.value.code == 2
        assert "no lock matches scope nz/statut" in capsys.readouterr().err


# Opus r2-N3 / N5: hidden files -------------------------------------------------------


def test_hidden_files_in_the_lock_directory_are_ignored(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    path = write_lock(repo, _lock())
    (path.parent / ".DS_Store").write_bytes(b"\0finder")
    (path.parent / f".{path.name}.swp").write_bytes(b"vim")
    locks = load_locks(repo)
    assert locks.errors == () and SCOPE in locks.locks
    (path.parent / "notes.txt").write_text("stray")
    assert load_locks(repo).errors  # any other stray file is still an error


def test_lock_refuses_a_hidden_source_file_that_status_reports(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _init_repo(tmp_path / "repo")
    for rel, data in FILES.items():
        _write(repo, rel, data)
    hidden = "data/corpus/sources/nz/statute/2026-07-10/official/.DS_Store"
    _write(repo, hidden, b"finder")
    with pytest.raises(LockFormatError, match="hidden file"):
        lock_from_worktree(repo, SCOPE)
    write_lock(repo, _lock())
    monkeypatch.chdir(repo)
    assert cli_main(["corpus", "status", "--repo", str(repo), "--json"]) in (0, 1)
    assert hidden in capsys.readouterr().out


# Opus r2-N8: analytics requires only the version and scopes it reports ---------------


def test_analytics_requires_only_its_version_and_filters(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    other_scope = ("nz", "statute", "2026-08-01")
    other = {p.replace("2026-07-10", "2026-08-01"): d for p, d in FILES.items()}
    write_lock(
        repo,
        CorpusLock.from_entries(
            other_scope, [LockEntry(p, _sha(d), len(d)) for p, d in other.items()]
        ),
    )
    part = "data/corpus/provisions/us/statute/2026-07-10-part-a.jsonl"
    write_lock(
        repo,
        CorpusLock.from_entries(("us", "statute", "2026-07-10-part-a"), [LockEntry(part, "0" * 64, 1)]),
    )
    monkeypatch.chdir(repo)
    base = str(repo / "data/corpus")

    def required(*extra: str) -> set[str]:
        args = build_parser().parse_args(["analytics", "--base", base, "--version", "2026-07-10", *extra])
        return {p.relative_to(repo).as_posix() for p in _corpus_wide_prefixes(args, "analytics")}

    assert required() == {
        "data/corpus/inventory/nz/statute/2026-07-10.json",
        "data/corpus/provisions/nz/statute/2026-07-10.jsonl",
        part,
    }
    assert required("--jurisdiction", "us") == {part}


# entries_under is a sorted-prefix query; check it against the obvious scan -----------


def test_entries_under_matches_a_linear_scan() -> None:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    segment = st.text(alphabet="ab-/", min_size=1, max_size=4).filter(
        lambda s: "//" not in s and not s.startswith("/") and not s.endswith("/")
    )

    @settings(max_examples=200, deadline=None)
    @given(st.sets(segment, min_size=1, max_size=12), segment)
    def check(tails: set[str], query_tail: str) -> None:
        paths = sorted({f"data/corpus/sources/nz/statute/v1/{tail}" for tail in tails})
        lock = CorpusLock.from_entries(
            ("nz", "statute", "v1"), [LockEntry(p, "0" * 64, 1) for p in paths]
        )
        locks = LockSet(locks={lock.scope: lock})
        query = f"data/corpus/sources/nz/statute/v1/{query_tail}"
        expected = (
            [locks.by_path[query]]
            if query in locks.by_path
            else [locks.by_path[p] for p in paths if p.startswith(query + "/")]
        )
        assert locks.entries_under(query) == expected

    check()


# =========================================================================== round 3


class _FailingMidBody:
    """A source whose stream breaks after the first chunk (a dropped R2 connection)."""

    name = "flaky"

    def __init__(self, payload: bytes):
        self.payload = payload

    def open(self, entry):
        def chunks():
            yield self.payload[:1]
            raise RuntimeError("IncompleteRead: connection dropped")

        return chunks()


def test_a_read_error_mid_body_falls_through_to_the_next_source(tmp_path: Path) -> None:
    """Round 3: botocore stream errors are not OSError and used to escape."""
    entry = next(e for e in _lock().files if e.path.endswith(".jsonl"))
    data = FILES[entry.path]
    good = _remote({content_key(entry.sha256): data})
    for cache in (ContentCache(tmp_path / "cache"), None):
        repo = tmp_path / f"repo-{cache is None}"
        report = materialize(repo, [entry], cache, [_FailingMidBody(data), good])
        assert report.ok and (repo / entry.path).read_bytes() == data


def test_one_entrys_unexpected_error_fails_that_entry_and_rolls_back_its_directory(
    tmp_path: Path,
) -> None:
    sources = [e for e in _lock().files if "/sources/" in e.path]
    first, second = sources
    remote = _remote({content_key(first.sha256): FILES[first.path]})
    report = materialize(
        tmp_path / "repo",
        sources,
        ContentCache(tmp_path / "cache"),
        [remote, _FailingMidBody(FILES[second.path])],
        workers=1,
    )
    assert set(report.failed) == {second.path}
    assert "IncompleteRead" in report.failed[second.path]
    assert report.rolled_back == [first.path]


def test_a_wrong_size_lock_entry_does_not_delete_a_good_cache_object(tmp_path: Path) -> None:
    data = b"shared object bytes"
    cache = ContentCache(tmp_path / "cache")
    cache.add_stream([data], sha256=_sha(data), size=len(data))
    assert not cache.usable(_sha(data), len(data) + 1)  # a bad entry elsewhere
    assert cache.object_path(_sha(data)).read_bytes() == data


def test_rollback_keeps_a_same_size_rewrite_even_if_its_identity_matches(
    tmp_path: Path, monkeypatch
) -> None:
    """Round 3: a coarse timestamp tick can hide an in-place rewrite of the same size."""
    monkeypatch.setattr(content_store, "_identity", lambda _path: (0, 0, 0, 0))

    def rewrite_same_size(path: Path) -> None:
        path.write_bytes(b"X" * path.stat().st_size)

    repo, first, report = _failing_sibling_fetch(tmp_path, monkeypatch, rewrite_same_size)
    assert (repo / first.path).read_bytes() == b"X" * first.size
    assert report.rolled_back == [] and first.path in report.modified


def test_lock_sets_refuse_names_one_checkout_cannot_hold(tmp_path: Path) -> None:
    """Round 3: `B` and `b/3` (or `Act.html` and `act.html`) cannot coexist on APFS."""
    base = "data/corpus/sources/nz/statute/2026-07-10/official"
    for names in (["B", "b/3"], ["Act.html", "act.html"], ["x", "x/y"], ["café", "CAFÉ"]):
        repo = _init_repo(tmp_path / f"repo-{len(list(tmp_path.iterdir()))}")
        entries = [LockEntry(f"{base}/{name}", _sha(name.encode()), len(name.encode())) for name in names]
        write_lock(repo, CorpusLock.from_entries(SCOPE, entries))
        errors = load_locks(repo).errors
        assert any("cannot both exist in one checkout" in error for error in errors), names


def test_the_real_corpus_path_shape_has_no_fold_collisions_and_loads_fast(tmp_path: Path) -> None:
    """55,000 synthetic entries in the corpus's shape load in well under the
    old 1.2-2.6 s and trip no portability error."""
    from axiom_corpus.corpus.corpus_locks import _lock_set_from_payloads

    payloads = {}
    for s_index in range(200):
        scope = ("us-ca", "statute", f"v{s_index:04d}")
        entries = [
            LockEntry(f"data/corpus/sources/us-ca/statute/v{s_index:04d}/leginfo/{i:05d}.html", "0" * 64, 1)
            for i in range(275)
        ]
        lock = CorpusLock.from_entries(scope, entries)
        payloads[lock.relative_path.as_posix()] = serialize_lock(lock)
    started = content_store.time.perf_counter()
    locks = _lock_set_from_payloads(payloads)
    elapsed = content_store.time.perf_counter() - started
    assert locks.errors == () and len(locks.by_path) == 55_000
    assert elapsed < 5.0, elapsed


def test_sign_with_lock_derives_deletions_from_the_manifest_spelling(tmp_path: Path, monkeypatch) -> None:
    """Round 3 nit: `./data/...` and absolute spellings name the same deletion."""
    import json
    from base64 import b64encode

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "lock")
    for rel, data in FILES.items():
        _write(repo, rel, data)
    deleted = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    (repo / deleted).unlink()
    key = Ed25519PrivateKey.generate()
    private = b64encode(
        key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    ).decode("ascii")
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY", private)
    monkeypatch.chdir(repo)
    status = cli_main(
        [
            "sign-ingest-manifest", "--repo", str(repo),
            "--jurisdiction", "nz", "--document-class", "statute", "--version", "2026-07-10",
            "--command", "x", "--deleted-file", f"./{deleted}", "--lock",
        ]
    )  # fmt: skip
    assert status == 0
    assert deleted not in load_locks(repo).by_path
    manifest = json.loads((repo / ".axiom/ingest-manifests/nz/statute/2026-07-10.json").read_text())
    assert {"path": deleted, "deleted": True} in manifest["applied_files"]


def test_push_refuses_invalid_locks(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _init_repo(tmp_path / "repo")
    path = write_lock(repo, _lock())
    path.write_text("{not json")
    monkeypatch.chdir(repo)
    assert cli_main(["corpus", "push", "--repo", str(repo), "--all"]) == 2
    assert "invalid" in capsys.readouterr().err


def test_analytics_treats_the_version_as_the_glob_it_is(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    monkeypatch.chdir(repo)
    args = build_parser().parse_args(
        ["analytics", "--base", str(repo / "data/corpus"), "--version", "2026-07-*"]
    )
    required = {p.relative_to(repo).as_posix() for p in _corpus_wide_prefixes(args, "analytics")}
    assert required == {
        "data/corpus/inventory/nz/statute/2026-07-10.json",
        "data/corpus/provisions/nz/statute/2026-07-10.jsonl",
    }


def test_resolve_corpus_path_returns_a_present_file_without_git(tmp_path: Path, monkeypatch) -> None:
    present = tmp_path / "data/corpus/provisions/nz/statute/v1.jsonl"
    present.parent.mkdir(parents=True)
    present.write_bytes(b"{}\n")

    def no_git(*_args, **_kwargs):
        raise AssertionError("resolve_corpus_path looked for a repository")

    monkeypatch.setattr(resolver_module, "find_repo_root", no_git)
    assert resolver_module.resolve_corpus_path(present) == present


def test_ensure_names_a_directory_squatting_on_a_locked_path(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    squatter = repo / "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
    squatter.mkdir(parents=True)
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[_full_remote()])
    with pytest.raises(CorpusNotMaterializedError, match="are directories in this checkout"):
        resolver.ensure_scopes([SCOPE])


def test_an_unexpected_placement_error_fails_only_that_entry(tmp_path: Path, monkeypatch) -> None:
    """Round 3: a non-OSError from placement used to escape materialize() mid-run."""
    real_clone = content_store.clone_file
    victim = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"

    def clone(src, dst):
        if dst.name.startswith(f"{content_store.FETCH_TEMP_MARKER}2026-07-10.jsonl"):
            raise RuntimeError("unexpected placement failure")
        return real_clone(src, dst)

    monkeypatch.setattr(content_store, "clone_file", clone)
    report = materialize(tmp_path / "repo", _lock().files, ContentCache(tmp_path / "cache"), [_full_remote()])
    assert set(report.failed) == {victim}
    assert "RuntimeError" in report.failed[victim]
    assert len(report.materialized) == len(FILES) - 1


# =========================================================================== round 4


def test_the_publish_lock_never_lands_inside_a_scope(tmp_path: Path, monkeypatch) -> None:
    """Round 4: a killed publisher left `.<name>.corpus-fetch-lock` in sources/."""
    _no_links_no_noreplace(monkeypatch)
    staging = tmp_path / "staging"
    staging.mkdir()
    scope_dir = tmp_path / "data/corpus/sources/nz/statute/v1"
    scope_dir.mkdir(parents=True)
    created = []
    real_open = os.open

    def spy_open(path, flags, *args):
        if flags & os.O_EXCL:
            created.append(Path(path))
        return real_open(path, flags, *args)

    monkeypatch.setattr(content_store.os, "open", spy_open)
    tmp = staging / "tmp"
    tmp.write_bytes(b"bytes")
    assert publish_no_replace(tmp, scope_dir / "act.html")
    assert created and all(path.parent == staging for path in created)
    assert sorted(p.name for p in scope_dir.iterdir()) == ["act.html"]


def test_a_publish_lock_dated_in_the_future_is_broken(tmp_path: Path, monkeypatch) -> None:
    """Round 4: a lock with a future mtime made the wait spin forever."""
    _no_links_no_noreplace(monkeypatch)
    monkeypatch.setattr(content_store, "PUBLISH_LOCK_STALE_SECONDS", 0.5)
    target = tmp_path / "object"
    tmp = tmp_path / "tmp"
    tmp.write_bytes(b"bytes")
    lock = content_store.publish_lock_path(target, tmp_path)
    lock.write_bytes(b"")
    future = content_store.time.time() + 3600
    os.utime(lock, (future, future))
    assert publish_no_replace(tmp, target)
    assert target.read_bytes() == b"bytes"


def test_rollback_tolerates_a_file_removed_during_its_check(tmp_path: Path, monkeypatch) -> None:
    """Round 4 nit: the content check could raise FileNotFoundError out of materialize()."""
    real_hash = content_store.hash_path

    def vanish(path):
        if "/sources/" in str(path) and Path(path).name == "act.html" and Path(path).exists():
            Path(path).unlink()
            raise FileNotFoundError(path)
        return real_hash(path)

    sources = [e for e in _lock().files if "/sources/" in e.path]
    first, second = sources
    remote = _remote({content_key(first.sha256): FILES[first.path]})
    monkeypatch.setattr(content_store, "hash_path", vanish)
    report = materialize(tmp_path / "repo", sources, ContentCache(tmp_path / "cache"), [remote], workers=1)
    assert set(report.failed) == {second.path}


def test_an_interrupted_fetch_rolls_back_a_half_fetched_sources_directory(
    tmp_path: Path, monkeypatch
) -> None:
    """Round 4: Ctrl-C waited for every queued entry, then skipped the rollback."""
    sources = [e for e in _lock().files if "/sources/" in e.path]
    first, second = sources
    real = content_store._materialize_one

    def interrupt_on_second(repo, entry, *args, **kwargs):
        if entry.path == second.path:
            raise KeyboardInterrupt
        return real(repo, entry, *args, **kwargs)

    monkeypatch.setattr(content_store, "_materialize_one", interrupt_on_second)
    repo = tmp_path / "repo"
    with pytest.raises(KeyboardInterrupt):
        materialize(repo, sources, ContentCache(tmp_path / "cache"), [_full_remote()], workers=1)
    assert not (repo / first.path).exists()


def test_resolve_corpus_path_widens_a_source_spelled_relative_to_data_corpus(
    tmp_path: Path, monkeypatch
) -> None:
    """Round 4: the fast path tested a literal 'data/corpus/sources/' substring."""
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    present = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    sibling = "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml"
    _write(repo, present, FILES[present])
    monkeypatch.setattr(
        content_store.R2ObjectStore, "from_environment", classmethod(lambda cls, **_k: _full_remote())
    )
    monkeypatch.chdir(repo / "data/corpus")
    resolver_module.resolve_corpus_path("sources/nz/statute/2026-07-10/official/act.html")
    assert (repo / sibling).read_bytes() == FILES[sibling]


def test_signing_checks_names_before_it_signs(tmp_path: Path, monkeypatch) -> None:
    """Round 4: check_lockable missed non-canonical and colliding names.

    The worktree listing is stubbed, so the test does not depend on whether
    this filesystem can hold both spellings.
    """
    repo = _init_repo(tmp_path / "repo")
    base = "data/corpus/sources/nz/statute/2026-07-10/official"
    listing: list[str] = []
    monkeypatch.setattr(
        corpus_cli, "scope_files_in_worktree", lambda repo_arg, _scope: [repo_arg / rel for rel in listing]
    )
    listing[:] = [f"{base}/act.html", f"{base}/ACT.html"]
    with pytest.raises(corpus_cli.LockRefusedError, match="cannot both exist"):
        corpus_cli.check_lockable(repo, [SCOPE])
    listing[:] = [unicodedata.normalize("NFD", base + "/caf" + chr(0xE9) + ".html")]
    with pytest.raises(LockFormatError):
        corpus_cli.check_lockable(repo, [SCOPE])
    listing[:] = [f"{base}/act.html"]
    corpus_cli.check_lockable(repo, [SCOPE])


def test_a_selector_on_invalid_locks_names_the_real_problem(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _init_repo(tmp_path / "repo")
    path = write_lock(repo, _lock())
    path.write_text("{not json")
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit) as stopped:
        cli_main(["corpus", "status", "--repo", str(repo), "nz/statute"])
    assert stopped.value.code == 2
    assert "invalid" in capsys.readouterr().err


def test_paths_from_accepts_the_corpus_root_like_path() -> None:
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write("data/corpus\nnz/statute\ndata/corpus/provisions\n")
    scopes, paths = corpus_cli._read_paths_file(Path(handle.name))
    assert scopes == ["nz/statute"] and paths == ["data/corpus", "data/corpus/provisions"]


def test_a_many_path_refusal_names_only_a_few_paths(tmp_path: Path) -> None:
    """Round 3 nit, pinned in round 4: the analytics refusal listed every file twice."""
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    many = [repo / entry.path for entry in _lock().files]
    with pytest.raises(CorpusNotMaterializedError) as refused:
        resolver_module.require_materialized(many, repo=repo)
    message = str(refused.value)
    assert f"and {len(many) - 3} more" in message and "--paths-from" in message
    assert len(message) < 800


# =========================================================================== round 5


def test_an_interrupt_from_the_progress_callback_still_rolls_back(tmp_path: Path) -> None:
    """Round 5: the handler recorded a finished entry twice, so a scope missing
    one cancelled entry counted as complete and kept its half-fetched files."""
    lock = _lock()
    ordered = sorted(lock.files, key=lambda e: (0 if e.path.endswith("act.html") else 1, e.path))
    calls = []

    def progress(done: int, total: int) -> None:
        calls.append(done)
        if len(calls) == 1:
            raise KeyboardInterrupt

    repo = tmp_path / "repo"
    with pytest.raises(KeyboardInterrupt):
        materialize(repo, ordered, ContentCache(tmp_path / "cache"), [_full_remote()], workers=1, progress=progress)
    sources = [e for e in lock.files if "/sources/" in e.path]
    present = [e.path for e in sources if (repo / e.path).exists()]
    assert present == [] or len(present) == len(sources)
    assert calls == [1]  # the handler never calls progress again


def test_an_interrupt_while_submitting_cancels_and_rolls_back(tmp_path: Path, monkeypatch) -> None:
    """Round 5 nit: a Ctrl-C during submission escaped before the try."""
    lock = _lock()
    real_submit = content_store.ThreadPoolExecutor.submit
    count = []

    def submit(self, fn, *args, **kwargs):
        count.append(1)
        if len(count) == len(lock.files):  # the last entry: the second source file
            content_store.time.sleep(0.2)  # let the first source file land
            raise KeyboardInterrupt
        return real_submit(self, fn, *args, **kwargs)

    monkeypatch.setattr(content_store.ThreadPoolExecutor, "submit", submit)
    repo = tmp_path / "repo"
    with pytest.raises(KeyboardInterrupt):
        materialize(repo, lock.files, ContentCache(tmp_path / "cache"), [_full_remote()], workers=1)
    sources = [e for e in lock.files if "/sources/" in e.path]
    assert lock.files[-1] == sources[-1]  # the interrupted submit is a source file
    assert [e.path for e in sources if (repo / e.path).exists()] == []


def test_the_exdev_path_keeps_its_publish_lock_in_the_staging_directory(tmp_path: Path, monkeypatch) -> None:
    """Round 5 nit: the EXDEV sibling path created its lock inside the scope."""
    real_link = os.link

    def link(src, dst):
        raise OSError(errno.EXDEV if len(created_by_link) == 0 else errno.EPERM, "no")

    created_by_link: list[str] = []
    monkeypatch.setattr(content_store.os, "link", link)
    monkeypatch.setattr(content_store, "_RENAME_NOREPLACE", None)
    opened = []
    real_open = os.open

    def spy_open(path, flags, *args):
        if flags & os.O_EXCL:
            opened.append(Path(path))
        return real_open(path, flags, *args)

    monkeypatch.setattr(content_store.os, "open", spy_open)
    staging = tmp_path / "staging"
    staging.mkdir()
    scope_dir = tmp_path / "data/corpus/sources/nz/statute/v1"
    scope_dir.mkdir(parents=True)
    tmp = staging / "tmp"
    tmp.write_bytes(b"bytes")
    assert publish_no_replace(tmp, scope_dir / "act.html")
    locks = [path for path in opened if "lock-" in path.name]
    assert locks and all(path.parent == staging for path in locks)
    assert sorted(p.name for p in scope_dir.iterdir()) == ["act.html"]
    del real_link


def test_two_spellings_of_one_target_share_a_publish_lock(tmp_path: Path, monkeypatch) -> None:
    """Round 5 nit: the lock key hashed abspath, so /tmp and /private/tmp differed."""
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real_dir)
    _no_links_no_noreplace(monkeypatch)
    names = []
    real_open = os.open

    def spy_open(path, flags, *args):
        if flags & os.O_EXCL:
            names.append(Path(path).name)
        return real_open(path, flags, *args)

    monkeypatch.setattr(content_store.os, "open", spy_open)
    for spelling, data in ((real_dir / "object", b"one"), (alias / "object", b"two")):
        tmp = tmp_path / f"tmp-{data.decode()}"
        tmp.write_bytes(data)
        publish_no_replace(tmp, spelling)
    assert len(set(names)) == 1


def test_the_source_check_folds_case_variant_spellings(tmp_path: Path, monkeypatch) -> None:
    """Round 5 nit: `Data/corpus/sources/...` on APFS skipped sibling widening."""
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    present = "data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    sibling = "data/corpus/sources/nz/statute/2026-07-10/official/sub dir/s 2.xml"
    _write(repo, present, FILES[present])
    variant = repo / present.replace("data/corpus/sources", "Data/corpus/Sources", 1)
    if not variant.exists():
        pytest.skip("case-sensitive filesystem: the variant spelling names no file")
    monkeypatch.setattr(
        content_store.R2ObjectStore, "from_environment", classmethod(lambda cls, **_k: _full_remote())
    )
    resolver_module.resolve_corpus_path(variant)
    assert (repo / sibling).exists()


# =========================================================================== round 6


class _SlowSource:
    """Serves every locked file, slowly, so an interrupt lands mid-run."""

    name = "slow"

    def __init__(self, payloads: dict[str, bytes], delay: float):
        self.by_sha = {_sha(data): data for data in payloads.values()}
        self.delay = delay

    def open(self, entry):
        content_store.time.sleep(self.delay)
        data = self.by_sha.get(entry.sha256)
        return None if data is None else [data]


def test_a_real_sigint_anywhere_leaves_every_sources_directory_whole_or_empty(tmp_path: Path) -> None:
    """Round 6: an asynchronous KeyboardInterrupt could land between submit()
    queuing an entry and the future being stored, orphaning a placed file."""
    import signal as signal_module

    files: dict[str, bytes] = {}
    for scope_index in range(12):
        for file_index in range(6):
            files[f"data/corpus/sources/zz/statute/v{scope_index:02d}/f{file_index}.html"] = (
                f"{scope_index}-{file_index}".encode()
            )
    entries = [LockEntry(path, _sha(data), len(data)) for path, data in sorted(files.items())]
    by_scope: dict[str, list[str]] = {}
    for path in files:
        by_scope.setdefault(path.rsplit("/", 1)[0], []).append(path)
    # A harmless handler outside materialize(): a signal that lands after it
    # restores the handler is recorded, never a KeyboardInterrupt in pytest.
    late: list[int] = []
    saved = signal_module.signal(signal_module.SIGINT, lambda _s, _f: late.append(1))
    original = signal_module.getsignal(signal_module.SIGINT)
    try:
        _sigint_trials(tmp_path, files, entries, by_scope, original, signal_module, late)
    finally:
        signal_module.signal(signal_module.SIGINT, saved)


def _sigint_trials(tmp_path, files, entries, by_scope, original, signal_module, late) -> None:
    interruptions = 0
    for trial, delay in enumerate([0.0, 0.002, 0.005, 0.01, 0.02, 0.04, 0.08]):
        repo = tmp_path / f"repo-{trial}"

        def fire(delay: float = delay) -> None:
            deadline = content_store.time.monotonic() + 2.0
            while signal_module.getsignal(signal_module.SIGINT) is original:
                if content_store.time.monotonic() > deadline:
                    return  # materialize finished before we saw it: no signal this trial
                content_store.time.sleep(0.0005)  # wait until materialize owns SIGINT
            content_store.time.sleep(delay)
            if signal_module.getsignal(signal_module.SIGINT) is not original:
                os.kill(os.getpid(), signal_module.SIGINT)

        killer = threading.Thread(target=fire, daemon=True)
        killer.start()
        try:
            materialize(repo, entries, ContentCache(tmp_path / f"cache-{trial}"), [_SlowSource(files, 0.004)], workers=8)
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True
        killer.join()
        assert signal_module.getsignal(signal_module.SIGINT) is original  # handler restored
        for scope_dir, paths in by_scope.items():
            present = [path for path in paths if (repo / path).exists()]
            assert present == [] or len(present) == len(paths), (trial, scope_dir, present)
        assert interrupted or all((repo / path).exists() for path in files)
        interruptions += interrupted
    assert interruptions >= 3  # the signal really landed mid-run in most trials


def test_a_future_dated_publish_lock_is_waited_out_not_broken_at_once(tmp_path: Path, monkeypatch) -> None:
    """Round 6: a skewed clock must not let a live lock be broken instantly."""
    _no_links_no_noreplace(monkeypatch)
    monkeypatch.setattr(content_store, "PUBLISH_LOCK_STALE_SECONDS", 0.4)
    target = tmp_path / "object"
    tmp = tmp_path / "tmp"
    tmp.write_bytes(b"bytes")
    lock = content_store.publish_lock_path(target, tmp_path)
    lock.write_bytes(b"")
    future = content_store.time.time() + 3600
    os.utime(lock, (future, future))
    started = content_store.time.monotonic()
    assert publish_no_replace(tmp, target)
    assert content_store.time.monotonic() - started >= 0.4


def test_the_publish_lock_key_folds_case(tmp_path: Path) -> None:
    upper = content_store.publish_lock_path(tmp_path / "Data" / "Act.HTML", tmp_path)
    lower = content_store.publish_lock_path(tmp_path / "data" / "act.html", tmp_path)
    assert upper == lower


def test_resolving_an_absent_case_variant_does_not_map_onto_a_locked_file(tmp_path: Path) -> None:
    """Round 6: find_folded used as a mapping returned paths that do not exist."""
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[_full_remote()])
    variant = "data/corpus/sources/nz/statute/2026-07-10/official/act‌.html"  # ZWNJ: another name
    with pytest.raises(CorpusNotMaterializedError, match="neither present nor locked"):
        resolver.resolve(variant)


# =========================================================================== round 7


def _with_safe_sigint(run):
    """Run ``run`` with a harmless SIGINT handler around it, so a signal that
    lands outside materialize() never interrupts pytest."""
    import signal as signal_module

    late: list[int] = []
    saved = signal_module.signal(signal_module.SIGINT, lambda _s, _f: late.append(1))
    try:
        return run(signal_module.getsignal(signal_module.SIGINT))
    finally:
        signal_module.signal(signal_module.SIGINT, saved)


def _signal_when_owned(original, delays: list[float], *, only_while_owned: bool = True) -> threading.Thread:
    import signal as signal_module

    def fire() -> None:
        deadline = content_store.time.monotonic() + 2.0
        while signal_module.getsignal(signal_module.SIGINT) is original:
            if content_store.time.monotonic() > deadline:
                return
            content_store.time.sleep(0.0005)
        started = content_store.time.monotonic()
        for delay in delays:
            content_store.time.sleep(max(0.0, started + delay - content_store.time.monotonic()))
            if not only_while_owned or signal_module.getsignal(signal_module.SIGINT) is not original:
                os.kill(os.getpid(), signal_module.SIGINT)

    thread = threading.Thread(target=fire, daemon=True)
    thread.start()
    return thread


def test_a_second_sigint_during_cleanup_changes_nothing(tmp_path: Path, monkeypatch) -> None:
    """Round 7: `uv run` delivers each Ctrl-C twice; the second one must not
    skip the rollback. It is sent from inside the rollback itself, so it lands
    during cleanup on every machine, with no timing race."""
    import signal as signal_module

    files = {
        f"data/corpus/sources/zz/statute/v{scope:02d}/f{index}.html": f"{scope}-{index}".encode()
        for scope in range(8)
        for index in range(6)
    }
    entries = [LockEntry(path, _sha(data), len(data)) for path, data in sorted(files.items())]
    repo = tmp_path / "repo"
    real_roll_back = content_store._roll_back

    def roll_back_after_a_second_sigint(*args, **kwargs):
        os.kill(os.getpid(), signal_module.SIGINT)  # the second Ctrl-C, mid-cleanup
        return real_roll_back(*args, **kwargs)

    monkeypatch.setattr(content_store, "_roll_back", roll_back_after_a_second_sigint)
    # Python's default handler outside materialize(), as in the real CLI: code
    # that gave SIGINT back before cleanup would raise mid-rollback.
    saved = signal_module.signal(signal_module.SIGINT, signal_module.default_int_handler)
    try:
        original = signal_module.getsignal(signal_module.SIGINT)
        killer = _signal_when_owned(original, [0.55])
        with pytest.raises(KeyboardInterrupt):
            materialize(repo, entries, ContentCache(tmp_path / "cache"), [_SlowSource(files, 0.5)], workers=8)
        killer.join()
    finally:
        signal_module.signal(signal_module.SIGINT, saved)
    for scope in range(8):
        paths = [p for p in files if f"/v{scope:02d}/" in p]
        present = [p for p in paths if (repo / p).exists()]
        assert present == [] or len(present) == len(paths), (scope, present)


def test_a_sigint_during_final_cleanup_is_raised_not_swallowed(tmp_path: Path, monkeypatch) -> None:
    """Round 7 nit: a Ctrl-C after the result loop was swallowed."""
    import signal as signal_module

    real = content_store._roll_back
    sent = []

    def roll_back_then_interrupt(*args, **kwargs):
        if not sent:
            sent.append(1)
            os.kill(os.getpid(), signal_module.SIGINT)
        return real(*args, **kwargs)

    monkeypatch.setattr(content_store, "_roll_back", roll_back_then_interrupt)

    def run(_original):
        with pytest.raises(KeyboardInterrupt):
            materialize(tmp_path / "repo", _lock().files, ContentCache(tmp_path / "cache"), [_full_remote()])

    _with_safe_sigint(run)
    lock = _lock()
    assert all((tmp_path / "repo" / e.path).exists() for e in lock.files)  # the fetch itself completed


def test_a_workers_system_exit_is_raised_as_itself(tmp_path: Path) -> None:
    """Round 7 nit: a worker's SystemExit came back as a bare KeyboardInterrupt."""

    class Exits:
        name = "exits"

        def open(self, entry):
            raise SystemExit(3)

    with pytest.raises(SystemExit) as stopped:
        materialize(tmp_path / "repo", _lock().files, ContentCache(tmp_path / "cache"), [Exits()])
    assert stopped.value.code == 3


def test_a_distinct_file_with_a_variant_name_is_not_mapped_onto_a_locked_entry(tmp_path: Path) -> None:
    """Round 7 nit: on a case-sensitive disk `Data/...` is another file."""
    repo = _init_repo(tmp_path / "repo")
    write_lock(repo, _lock())
    variant = "Data/corpus/sources/nz/statute/2026-07-10/official/act.html"
    _write(repo, variant, b"someone else's file")
    if (repo / "data/corpus/sources/nz/statute/2026-07-10/official/act.html").exists():
        pytest.skip("case-insensitive filesystem: the variant is the locked file")
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[])
    # Absolute: a relative path other than `data/corpus/...` is cwd-relative by design.
    assert resolver.resolve(repo / variant) == repo / variant  # returned as is, nothing fetched
    assert not (repo / "data/corpus/sources/nz/statute/2026-07-10/official/act.html").exists()


def test_report_source_and_method_counts_exclude_rolled_back_entries(tmp_path: Path) -> None:
    """Round 7 nit (pre-existing): rolled-back files still counted as fetched."""
    sources = [e for e in _lock().files if "/sources/" in e.path]
    first, second = sources
    others = [e for e in _lock().files if "/sources/" not in e.path]
    remote = _remote({content_key(e.sha256): FILES[e.path] for e in [first, *others]})
    report = materialize(tmp_path / "repo", _lock().files, ContentCache(tmp_path / "cache"), [remote], workers=1)
    assert report.rolled_back == [first.path]
    assert sum(report.sources.values()) == len(report.materialized) == len(others)
    assert sum(report.methods.values()) == len(report.materialized)


_BURST_CHILD = r'''
import hashlib, json, os, signal, sys, threading, time
from pathlib import Path
from axiom_corpus.corpus import content_store
from axiom_corpus.corpus.content_store import ContentCache, materialize
from axiom_corpus.corpus.corpus_locks import LockEntry

root = Path(sys.argv[1])
files = {f"data/corpus/sources/zz/statute/v{s:02d}/f{i}.html": f"{s}-{i}".encode() for s in range(20) for i in range(6)}
entries = [LockEntry(p, hashlib.sha256(d).hexdigest(), len(d)) for p, d in sorted(files.items())]
by_sha = {hashlib.sha256(d).hexdigest(): d for d in files.values()}

class Slow:
    name = "slow"
    def open(self, entry):
        time.sleep(0.005)
        return [by_sha[entry.sha256]]

original = signal.getsignal(signal.SIGINT)
def burst():
    while signal.getsignal(signal.SIGINT) is original:
        time.sleep(0.0005)
    time.sleep(0.01)
    import random
    for _ in range(200):  # microseconds apart, so some land while the handler runs
        os.kill(os.getpid(), signal.SIGINT)
        spin_until = time.perf_counter() + random.uniform(0, 30e-6)
        while time.perf_counter() < spin_until:
            pass
threading.Thread(target=burst, daemon=True).start()
try:
    materialize(root / "repo", entries, ContentCache(root / "cache"), [Slow()], workers=8)
    outcome = "completed"
except KeyboardInterrupt:
    outcome = "interrupted"
by_scope = {}
for p in files:
    by_scope.setdefault(p.rsplit("/", 1)[0], []).append((root / "repo" / p).exists())
partial = [s for s, flags in by_scope.items() if any(flags) and not all(flags)]
print(json.dumps({"outcome": outcome, "partial": partial}))
'''


def test_a_burst_of_sigints_cannot_deadlock_the_handler(tmp_path: Path) -> None:
    """Round 7: an Event.set() handler re-entered by a second signal deadlocked
    forever; the lock-free flag cannot. Run in a subprocess with a timeout."""
    import json
    import sys

    child = tmp_path / "child.py"
    child.write_text(_BURST_CHILD)
    outcomes = []
    for trial in range(5):
        result = subprocess.run(
            [sys.executable, str(child), str(tmp_path / f"t{trial}")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        report = json.loads(result.stdout.strip().splitlines()[-1])
        assert report["partial"] == [], report
        outcomes.append(report["outcome"])
    assert "interrupted" in outcomes  # the burst really landed mid-fetch
