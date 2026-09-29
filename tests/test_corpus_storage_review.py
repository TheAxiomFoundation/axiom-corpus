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


def test_exclusive_copy_fallback_removes_a_partial_target(tmp_path: Path, monkeypatch) -> None:
    def no_links(*_args, **_kwargs):
        raise OSError(errno.EPERM, "no hardlinks here")

    def copy_then_fill_disk(src, dst, _length=0):
        dst.write(src.read(7))
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(content_store.os, "link", no_links)
    monkeypatch.setattr(content_store, "_RENAME_NOREPLACE", None)
    monkeypatch.setattr(content_store.shutil, "copyfileobj", copy_then_fill_disk)
    tmp = tmp_path / "tmp"
    tmp.write_bytes(b"complete object bytes")
    target = tmp_path / "target"
    with pytest.raises(OSError, match="No space"):
        publish_no_replace(tmp, target)
    assert not target.exists()


# Opus r2-N4: interrupted fetches' temporaries are cleaned up ----------------------------


def test_stale_fetch_temporaries_are_removed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(content_store, "_PRUNED_TMP_DIRS", set())
    repo = tmp_path / "repo"
    tmp_dir = repo / FETCH_TEMP_DIR
    tmp_dir.mkdir(parents=True)
    stale = tmp_dir / "act.html.corpus-fetch-old"
    fresh = tmp_dir / "act.html.corpus-fetch-new"
    stale.write_bytes(b"old")
    fresh.write_bytes(b"new")
    two_days_ago = content_store.time.time() - 2 * 24 * 3600
    os.utime(stale, (two_days_ago, two_days_ago))
    assert materialize(repo, _lock().files, ContentCache(tmp_path / "cache"), [_full_remote()]).ok
    assert not stale.exists() and fresh.exists()


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
        with pytest.raises(SystemExit, match="scope must be"):
            cli_main([*command, "--repo", str(repo), "NZ/statute/v1"])


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
