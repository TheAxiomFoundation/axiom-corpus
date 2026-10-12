"""guard-ingested with corpus bytes outside git (``.axiom/corpus-locks``).

A lock entry that differs from the base needs a valid signed ingest manifest
with the same path and sha256, unless a tracked file moved into the lock with
its bytes unchanged. See docs/corpus-storage.md.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.corpus_locks import (
    CorpusLock,
    LockEntry,
    lock_from_worktree,
    lock_path_for_scope,
    serialize_lock,
    write_lock,
)
from axiom_corpus.corpus.ingest_manifests import (
    build_ingest_manifest,
    guard_ingested_artifacts,
    sign_ingest_manifest,
)

SCOPE = ("nz", "statute", "2026-07-10")
FILES = {
    "data/corpus/sources/nz/statute/2026-07-10/official-documents/act.html": b"<p>Act text</p>\n",
    "data/corpus/inventory/nz/statute/2026-07-10.json": b'{"items": []}\n',
    "data/corpus/provisions/nz/statute/2026-07-10.jsonl": b'{"citation_path":"nz/statute/a"}\n',
    "data/corpus/coverage/nz/statute/2026-07-10.json": b'{"complete": true}\n',
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _keys() -> tuple[str, str]:
    key = Ed25519PrivateKey.generate()
    private = b64encode(
        key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    ).decode("ascii")
    public = b64encode(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    return private, public


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / ".gitignore").write_text("data/\n")
    (path / "README.md").write_text("seed\n")
    _git(path, "add", ".gitignore", "README.md")
    _git(path, "commit", "-q", "-m", "seed")
    return path


@pytest.fixture
def keys() -> tuple[str, str]:
    return _keys()


def _write_files(repo: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _sign_scope(
    repo: Path,
    private: str,
    *,
    applied: list[str] | None = None,
    deleted: list[str] | None = None,
) -> Path:
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction=SCOPE[0],
        document_class=SCOPE[1],
        version=SCOPE[2],
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[Path(p) for p in applied] if applied is not None else None,
        deleted_files=[Path(p) for p in (deleted or [])],
    )
    signed = sign_ingest_manifest(manifest, private_key=private)
    path = repo / ".axiom/ingest-manifests/nz/statute/2026-07-10.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
    return path


def _worktree_reader(repo: Path):
    def read(entry: LockEntry) -> bytes | None:
        path = repo / entry.path
        return path.read_bytes() if path.is_file() else None

    return read


def _guard(repo: Path, base: str, public: str, **kwargs):
    kwargs.setdefault("content_reader", _worktree_reader(repo))
    return guard_ingested_artifacts(
        repo=repo, base_ref=base, head_ref="HEAD", public_key=public, **kwargs
    )


def _ingest_and_commit(repo: Path, private: str, files: dict[str, bytes] = FILES) -> str:
    """Extract (ignored files), sign, lock, commit manifest + lock; return base sha."""
    base = _git(repo, "rev-parse", "HEAD")
    _write_files(repo, files)
    _sign_scope(repo, private)
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "ingest nz statute")
    return base


def test_signed_ingest_into_a_lock_passes(repo: Path, keys) -> None:
    private, public = keys
    base = _ingest_and_commit(repo, private)
    result = _guard(repo, base, public)
    assert result.passed, result.issues
    assert set(result.protected_changes) == set(FILES)
    assert _git(repo, "ls-files", "data") == ""


def test_lock_entry_without_a_manifest_fails(repo: Path, keys) -> None:
    _private, public = keys
    base = _git(repo, "rev-parse", "HEAD")
    _write_files(repo, FILES)
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "lock without manifest")
    result = _guard(repo, base, public)
    assert not result.passed
    assert sum("Unmanifested corpus lock entry" in i for i in result.issues) == len(FILES)


def test_lock_sha_that_differs_from_the_manifest_fails(repo: Path, keys) -> None:
    private, public = keys
    base = _git(repo, "rev-parse", "HEAD")
    _write_files(repo, FILES)
    _sign_scope(repo, private)
    coverage = "data/corpus/coverage/nz/statute/2026-07-10.json"
    (repo / coverage).write_bytes(b'{"complete": false}\n')  # edited after signing
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "edited after signing")
    result = _guard(repo, base, public)
    assert any(f"`{coverage}` lock sha256 does not match ingest manifest" in i for i in result.issues)


def test_manifest_signed_with_another_key_fails(repo: Path, keys) -> None:
    private, _public = keys
    _other_private, other_public = _keys()
    base = _ingest_and_commit(repo, private)
    result = _guard(repo, base, other_public)
    assert any("Invalid ingest manifest signature." in i for i in result.issues)


def test_unreadable_locked_bytes_fail_closed(repo: Path, keys) -> None:
    private, public = keys
    base = _ingest_and_commit(repo, private)
    result = _guard(repo, base, public, content_reader=lambda entry: None)
    assert sum("Cannot read the locked bytes" in i for i in result.issues) == len(FILES)


def test_content_checks_run_on_locked_bytes(repo: Path, keys) -> None:
    private, public = keys
    files = dict(FILES)
    files["data/corpus/sources/nz/statute/2026-07-10/official-documents/act.html"] = (
        b"Title: Summary\nSources: an agent\n"
    )
    base = _ingest_and_commit(repo, private, files)
    result = _guard(repo, base, public)
    assert any("looks like an agent digest" in i for i in result.issues)


def test_removed_lock_entry_needs_a_deleted_mark(repo: Path, keys) -> None:
    private, public = keys
    _ingest_and_commit(repo, private)
    base = _git(repo, "rev-parse", "HEAD")
    gone = "data/corpus/sources/nz/statute/2026-07-10/official-documents/act.html"
    (repo / gone).unlink()
    keep = [p for p in FILES if p != gone]
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "drop a source without a deleted mark")
    result = _guard(repo, base, public)
    assert any(f"`{gone}` was removed from its lock" in i for i in result.issues)

    _git(repo, "reset", "-q", "--hard", base)
    _write_files(repo, {p: FILES[p] for p in keep})
    (repo / gone).unlink(missing_ok=True)
    _sign_scope(repo, private, applied=keep, deleted=[gone])
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "drop a source with a signed deleted mark")
    result = _guard(repo, base, public)
    assert result.passed, result.issues


def _track_files(repo: Path) -> str:
    _write_files(repo, FILES)
    _git(repo, "add", "-f", *FILES)
    _git(repo, "commit", "-q", "-m", "track corpus files (pre-switch layout)")
    return _git(repo, "rev-parse", "HEAD")


def _move_into_lock(repo: Path, lock: CorpusLock) -> None:
    write_lock(repo, lock)
    _git(repo, "rm", "-q", "--cached", *FILES)
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "move into lock")


def _moved_lock(repo: Path, base: str) -> CorpusLock:
    entries = []
    for rel, data in FILES.items():
        oid = _git(repo, "rev-parse", f"{base}:{rel}")
        entries.append(LockEntry(rel, hashlib.sha256(data).hexdigest(), len(data), git_blob=oid))
    return CorpusLock.from_entries(SCOPE, entries)


def test_moving_tracked_files_into_a_lock_needs_no_manifest(repo: Path, keys) -> None:
    _private, public = keys
    base = _track_files(repo)
    _move_into_lock(repo, _moved_lock(repo, base))
    result = _guard(repo, base, public, content_reader=lambda entry: None)
    assert result.passed, result.issues


def test_moving_into_a_lock_with_different_bytes_fails(repo: Path, keys) -> None:
    _private, public = keys
    base = _track_files(repo)
    lock = _moved_lock(repo, base)
    tampered = [
        LockEntry(e.path, hashlib.sha256(b"other").hexdigest(), e.size, git_blob=e.git_blob)
        if e.path.endswith(".jsonl")
        else e
        for e in lock.files
    ]
    _move_into_lock(repo, CorpusLock.from_entries(SCOPE, tampered))
    result = _guard(repo, base, public)
    assert any("left git for a lock entry that does not match its tracked blob" in i for i in result.issues)


def test_tracking_protected_files_alongside_locks_fails(repo: Path, keys) -> None:
    private, public = keys
    base = _ingest_and_commit(repo, private)
    extra = "data/corpus/provisions/nz/statute/2026-07-11.jsonl"
    _write_files(repo, {extra: b"{}\n"})
    _git(repo, "add", "-f", extra)
    _git(repo, "commit", "-q", "-m", "track a corpus file in lock mode")
    result = _guard(repo, base, public)
    assert any("tracked in git while `.axiom/corpus-locks` exists" in i for i in result.issues)


def test_git_blob_must_hold_the_locked_bytes(repo: Path, keys) -> None:
    private, public = keys
    base = _git(repo, "rev-parse", "HEAD")
    _write_files(repo, FILES)
    _sign_scope(repo, private)
    readme_blob = _git(repo, "rev-parse", "HEAD:README.md")
    lock = lock_from_worktree(repo, SCOPE)
    wrong = [
        LockEntry(e.path, e.sha256, e.size, git_blob=readme_blob) if e.path.endswith(".jsonl") else e
        for e in lock.files
    ]
    write_lock(repo, CorpusLock.from_entries(SCOPE, wrong))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "lock names the wrong blob")
    result = _guard(repo, base, public)
    assert any("whose bytes differ from the lock" in i for i in result.issues)


def test_malformed_lock_file_fails(repo: Path, keys) -> None:
    private, public = keys
    base = _ingest_and_commit(repo, private)
    lock_file = repo / lock_path_for_scope(SCOPE)
    lock_file.write_text(lock_file.read_text().replace('"files": [', '"files":['))
    _git(repo, "commit", "-qam", "non-canonical lock")
    result = _guard(repo, base, public)
    assert any("not in canonical form" in i for i in result.issues)


def test_guard_without_locks_or_changes_is_unchanged(repo: Path, keys) -> None:
    _private, public = keys
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "notes.md").write_text("docs only\n")
    _git(repo, "add", "notes.md")
    _git(repo, "commit", "-q", "-m", "docs")
    result = _guard(repo, base, public)
    assert result.passed and result.protected_changes == ()
    assert serialize_lock  # the lock module imports cleanly beside the guard
