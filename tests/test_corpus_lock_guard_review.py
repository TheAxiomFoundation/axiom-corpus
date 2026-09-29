"""Guard and audit regressions from the #769 review (corpus bytes outside git)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus import content_store
from axiom_corpus.corpus import resolver as resolver_module
from axiom_corpus.corpus.corpus_locks import (
    CorpusLock,
    LockEntry,
    lock_from_worktree,
    lock_path_for_scope,
    serialize_lock,
    write_lock,
)
from axiom_corpus.corpus.ingest_manifests import (
    audit_lock_attestation,
    build_ingest_manifest,
    guard_ingested_artifacts,
    sign_ingest_manifest,
)
from axiom_corpus.corpus.scope_tracking import verify_scope_tracked

SCOPE = ("nz", "statute", "2026-07-10")
FILES = {
    "data/corpus/sources/nz/statute/2026-07-10/official-documents/act.html": b"<p>Act text</p>\n",
    "data/corpus/inventory/nz/statute/2026-07-10.json": json.dumps(
        {
            "items": [
                {
                    "citation_path": "nz/statute/a",
                    "source_path": "sources/nz/statute/2026-07-10/official-documents/act.html",
                }
            ]
        }
    ).encode(),
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
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
    ).decode("ascii")
    return private, public


@pytest.fixture(autouse=True)
def no_real_r2(monkeypatch, tmp_path: Path):
    def refuse(cls, **_kwargs):
        raise RuntimeError("R2 is disabled in tests")

    monkeypatch.setattr(content_store.R2ObjectStore, "from_environment", classmethod(refuse))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "default-cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "src" / "axiom_corpus").mkdir(parents=True)
    (path / ".gitignore").write_text("data/\n")
    (path / "README.md").write_text("seed\n")
    _git(path, "add", ".gitignore", "README.md")
    _git(path, "commit", "-q", "-m", "seed")
    return path


def _write_files(repo: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _sign(repo: Path, private: str) -> None:
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction=SCOPE[0],
        document_class=SCOPE[1],
        version=SCOPE[2],
        command="axiom-corpus-ingest extract-nz-legislation",
    )
    signed = sign_ingest_manifest(manifest, private_key=private)
    path = repo / ".axiom/ingest-manifests/nz/statute/2026-07-10.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")


def _ingest(repo: Path, private: str) -> str:
    base = _git(repo, "rev-parse", "HEAD")
    _write_files(repo, FILES)
    _sign(repo, private)
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "ingest")
    return base


def _reader(repo: Path):
    return lambda entry: (repo / entry.path).read_bytes() if (repo / entry.path).is_file() else None


def _guard(repo: Path, base: str | None, public: str, head: str = "HEAD"):
    return guard_ingested_artifacts(
        repo=repo,
        base_ref=base,
        head_ref=head,
        public_key=public,
        content_reader=_reader(repo),
    )


def test_worktree_mode_sees_an_untracked_lock(repo: Path) -> None:
    """Astra 8: `git diff HEAD` is empty for an unstaged lock; it is still checked."""
    _private, public = _keys()
    _write_files(repo, FILES)
    write_lock(repo, lock_from_worktree(repo, SCOPE))  # never staged, never signed
    result = _guard(repo, None, public, head=None)
    assert any("Unmanifested corpus lock entry" in issue for issue in result.issues)


def test_content_change_must_not_keep_a_stale_git_blob(repo: Path) -> None:
    """Astra 9: a new sha256 with the old blob id is contradictory."""
    private, public = _keys()
    _write_files(repo, FILES)
    _git(repo, "add", "-f", *FILES)
    _git(repo, "commit", "-q", "-m", "track")
    old_blob = _git(repo, "rev-parse", "HEAD:data/corpus/provisions/nz/statute/2026-07-10.jsonl")
    entries = [
        LockEntry(p, hashlib.sha256(d).hexdigest(), len(d), git_blob=_git(repo, "rev-parse", f"HEAD:{p}"))
        for p, d in FILES.items()
    ]
    write_lock(repo, CorpusLock.from_entries(SCOPE, entries))
    _git(repo, "rm", "-q", "--cached", *FILES)
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "move into lock")
    base = _git(repo, "rev-parse", "HEAD")
    new = b'{"citation_path":"nz/statute/b"}\n'
    (repo / "data/corpus/provisions/nz/statute/2026-07-10.jsonl").write_bytes(new)
    _sign(repo, private)
    changed = [
        LockEntry(e.path, hashlib.sha256(new).hexdigest(), len(new), git_blob=old_blob)
        if e.path.endswith(".jsonl")
        else e
        for e in entries
    ]
    write_lock(repo, CorpusLock.from_entries(SCOPE, changed))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "signed change keeps old blob id")
    result = _guard(repo, base, public)
    assert any("whose bytes differ from the lock" in issue for issue in result.issues)


def test_stale_branch_is_compared_at_the_merge_base(repo: Path) -> None:
    """Opus S10 / Astra 8: entries main added after the branch point are not 'removed'."""
    private, public = _keys()
    _git(repo, "checkout", "-q", "-b", "stale")
    (repo / "notes.md").write_text("docs only\n")
    _git(repo, "add", "notes.md")
    _git(repo, "commit", "-q", "-m", "docs on a stale branch")
    _git(repo, "checkout", "-q", "main")
    _ingest(repo, private)
    result = _guard(repo, "main", public, head="stale")
    assert result.passed, result.issues


def test_a_differently_cased_tracked_path_counts_as_protected(repo: Path) -> None:
    """Opus nit: on APFS `Provisions/` is the locked directory."""
    private, public = _keys()
    base = _ingest(repo, private)
    odd = "data/corpus/Provisions/nz/statute/2026-07-11.jsonl"
    _write_files(repo, {odd: b"{}\n"})
    _git(repo, "add", "-f", odd)
    _git(repo, "commit", "-q", "-m", "differently cased path")
    result = _guard(repo, base, public)
    assert not result.passed


def test_removing_a_whole_lock_file_needs_deleted_marks(repo: Path) -> None:
    private, public = _keys()
    _ingest(repo, private)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "rm", "-q", lock_path_for_scope(SCOPE).as_posix())
    _git(repo, "commit", "-q", "-m", "drop the lock")
    result = _guard(repo, base, public)
    assert sum("was removed from its lock" in issue for issue in result.issues) == len(FILES)


def test_a_lock_at_the_wrong_path_fails(repo: Path) -> None:
    private, public = _keys()
    base = _ingest(repo, private)
    moved = repo / ".axiom/corpus-locks/nz/statute/renamed.json"
    moved.write_bytes((repo / lock_path_for_scope(SCOPE)).read_bytes())
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "second copy under another name")
    result = _guard(repo, base, public)
    assert any("holds the lock for" in issue for issue in result.issues)


def test_audit_rejects_a_planted_lock_and_accepts_attested_or_moved_entries(repo: Path) -> None:
    """Opus S1: a lock that reached the base unchecked is caught by the full audit."""
    private, public = _keys()
    _ingest(repo, private)
    assert audit_lock_attestation(repo, ref="HEAD", public_key=public) == []

    planted_path = "data/corpus/provisions/zz/statute/v1.jsonl"
    planted = CorpusLock.from_entries(
        ("zz", "statute", "v1"),
        [LockEntry(planted_path, hashlib.sha256(b"planted").hexdigest(), 7)],
    )
    write_lock(repo, planted)
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "planted lock")
    issues = audit_lock_attestation(repo, ref="HEAD", public_key=public)
    assert any(planted_path in issue for issue in issues)

    # A moved entry is attested by the blob history tracked at that path.
    moved_path = "data/corpus/provisions/yy/statute/v1.jsonl"
    (repo / moved_path).parent.mkdir(parents=True, exist_ok=True)
    (repo / moved_path).write_bytes(b"legacy\n")
    _git(repo, "add", "-f", moved_path)
    _git(repo, "commit", "-q", "-m", "legacy tracked file")
    blob = _git(repo, "rev-parse", f"HEAD:{moved_path}")
    _git(repo, "rm", "-q", "--cached", moved_path)
    (repo / lock_path_for_scope(("zz", "statute", "v1"))).unlink()
    write_lock(
        repo,
        CorpusLock.from_entries(
            ("yy", "statute", "v1"),
            [LockEntry(moved_path, hashlib.sha256(b"legacy\n").hexdigest(), 7, git_blob=blob)],
        ),
    )
    _git(repo, "add", "-A", ".axiom")
    _git(repo, "commit", "-q", "-m", "move legacy file")
    assert audit_lock_attestation(repo, ref="HEAD", public_key=public) == []


def test_scope_tracking_reads_staged_locks_and_locked_bytes(repo: Path) -> None:
    """Astra 5 / Opus S6: an unstaged lock is not committed evidence, and the
    check reads the locked inventory, not whatever the worktree holds."""
    from axiom_corpus.corpus.content_store import ContentCache
    from axiom_corpus.corpus.corpus_cli import lock_scopes

    _write_files(repo, FILES)
    lock_scopes(repo, [SCOPE], cache=ContentCache())  # writes the lock and caches the bytes
    unstaged = verify_scope_tracked(repo=repo)
    assert unstaged.scopes_checked == 0  # nothing staged yet
    _git(repo, "add", ".axiom")
    staged = verify_scope_tracked(repo=repo)
    assert staged.passed, staged.missing_paths
    inventory = repo / "data/corpus/inventory/nz/statute/2026-07-10.json"
    inventory.write_text(
        json.dumps({"items": [{"citation_path": "x", "source_path": "sources/nz/statute/2026-07-10/elsewhere.html"}]})
    )
    # The worktree edit is ignored in favour of the locked bytes (from the cache).
    assert verify_scope_tracked(repo=repo).passed


def test_serialize_lock_is_stable_for_audit_inputs() -> None:
    lock = CorpusLock.from_entries(
        SCOPE, [LockEntry(p, hashlib.sha256(d).hexdigest(), len(d)) for p, d in FILES.items()]
    )
    assert serialize_lock(lock) == serialize_lock(lock)
