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


# =========================================================================== round 2


def _stage_blob(repo: Path, path: str, data: bytes) -> None:
    """Stage ``data`` at exactly ``path`` without touching a case-folding filesystem."""
    oid = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=repo, input=data, check=True, capture_output=True
    ).stdout.decode().strip()
    _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{oid},{path}")


@pytest.mark.parametrize("top", ["DATA", "Data"])
def test_a_differently_cased_top_level_directory_is_checked(repo: Path, top: str) -> None:
    """Astra r2-2 / Opus r2-B1: `DATA/corpus/...` is the locked location on APFS."""
    private, public = _keys()
    base = _ingest(repo, private)
    odd = f"{top}/corpus/provisions/nz/statute/2026-07-11.jsonl"
    _stage_blob(repo, odd, b'{"citation_path":"nz/statute/unsigned"}\n')
    _git(repo, "commit", "-q", "-m", "unsigned bytes under another spelling")
    result = _guard(repo, base, public)
    assert not result.passed
    assert any(odd in issue for issue in result.issues)


def test_audit_ignores_bytes_a_merged_branch_added_and_removed(repo: Path) -> None:
    """Astra r2-5 / Opus r2-S1: only the base branch's first-parent states count."""
    private, public = _keys()
    _ingest(repo, private)
    _git(repo, "checkout", "-q", "-b", "launder")
    path = "data/corpus/provisions/zz/statute/v1.jsonl"
    data = b'{"citation_path":"zz/statute/unsigned"}\n'
    _write_files(repo, {path: data})
    _git(repo, "add", "-f", path)
    _git(repo, "commit", "-q", "-m", "unsigned bytes, briefly")
    blob = _git(repo, "rev-parse", f"HEAD:{path}")
    _git(repo, "rm", "-q", "--cached", path)
    write_lock(
        repo,
        CorpusLock.from_entries(
            ("zz", "statute", "v1"),
            [LockEntry(path, hashlib.sha256(data).hexdigest(), len(data), git_blob=blob)],
        ),
    )
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "lock naming the removed blob")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "launder", "-m", "merge launder")
    issues = audit_lock_attestation(repo, ref="HEAD", public_key=public)
    assert any(path in issue and "first-parent" in issue for issue in issues)


def test_first_parent_scan_sees_both_sides_of_a_change(repo: Path) -> None:
    from axiom_corpus.corpus.ingest_manifests import first_parent_path_blobs

    path = "data/corpus/provisions/zz/statute/v1.jsonl"
    blobs = []
    for version in (b"one\n", b"two\n"):
        _stage_blob(repo, path, version)
        _git(repo, "commit", "-q", "-m", "write")
        blobs.append(_git(repo, "rev-parse", f"HEAD:{path}"))
    _git(repo, "rm", "-q", "--cached", path)
    _git(repo, "commit", "-q", "-m", "remove")
    wanted = {path: {*blobs, "f" * 40}}
    assert first_parent_path_blobs(repo, "HEAD", wanted) == {(path, blobs[0]), (path, blobs[1])}


def test_verify_attest_checks_the_same_locks_it_audits(repo: Path, monkeypatch, capsys) -> None:
    """Astra r2-6: worktree locks and HEAD's locks are never mixed."""
    from axiom_corpus.corpus.cli import main as cli_main

    private, public = _keys()
    _ingest(repo, private)
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", public)
    monkeypatch.chdir(repo)
    assert cli_main(["corpus", "verify", "--repo", str(repo), "--attest"]) == 0
    capsys.readouterr()
    unsigned = b"unsigned\n"
    write_lock(
        repo,
        CorpusLock.from_entries(
            ("zz", "statute", "v1"),
            [LockEntry("data/corpus/provisions/zz/statute/v1.jsonl", hashlib.sha256(unsigned).hexdigest(), 9)],
        ),
    )
    assert cli_main(["corpus", "verify", "--repo", str(repo), "--attest", "--json"]) == 1
    assert "differ from HEAD" in capsys.readouterr().out
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "commit the unsigned lock")
    assert cli_main(["corpus", "verify", "--repo", str(repo), "--attest", "--json"]) == 1
    assert "zz/statute/v1.jsonl" in capsys.readouterr().out


def test_scope_tracking_fails_on_a_malformed_staged_lock(repo: Path) -> None:
    """Astra r2-8 / Opus r2-N6."""
    path = repo / ".axiom/corpus-locks/nz/statute/v1.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    _git(repo, "add", ".axiom")
    result = verify_scope_tracked(repo=repo)
    assert not result.passed and result.lock_errors


def test_an_unmerged_lock_file_is_an_error(repo: Path) -> None:
    """Opus r2-N6: a conflicted index must not silently pick one side."""
    from axiom_corpus.corpus.corpus_locks import load_locks_from_index

    def lock_with(data: bytes) -> None:
        write_lock(
            repo,
            CorpusLock.from_entries(
                ("zz", "statute", "v1"),
                [LockEntry("data/corpus/provisions/zz/statute/v1.jsonl", hashlib.sha256(data).hexdigest(), len(data))],
            ),
        )
        _git(repo, "add", ".axiom")

    lock_with(b"base\n")
    _git(repo, "commit", "-q", "-m", "base lock")
    _git(repo, "checkout", "-q", "-b", "side")
    lock_with(b"side\n")
    _git(repo, "commit", "-q", "-m", "side")
    _git(repo, "checkout", "-q", "main")
    lock_with(b"main\n")
    _git(repo, "commit", "-q", "-m", "main")
    merge = subprocess.run(["git", "merge", "-q", "side"], cwd=repo, capture_output=True)
    assert merge.returncode != 0
    locks = load_locks_from_index(repo)
    assert any("unresolved merge conflicts" in error for error in locks.errors)


def _publishability_script():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_us_release_publishability.py"
    spec = importlib.util.spec_from_file_location("audit_us_release_publishability", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publishability_repair_fetches_locked_artifacts_instead_of_inventing_them(
    repo: Path, tmp_path: Path, monkeypatch
) -> None:
    """Astra r2-7 and r2-9: repair never synthesizes a locked artifact, and
    presence checks use the named repository, not the working directory."""
    from axiom_corpus.corpus.content_store import ContentCache

    script = _publishability_script()
    write_lock(
        repo,
        CorpusLock.from_entries(
            SCOPE, [LockEntry(p, hashlib.sha256(d).hexdigest(), len(d)) for p, d in FILES.items()]
        ),
    )
    cache = ContentCache()
    for data in FILES.values():
        cache.add_stream([data], sha256=hashlib.sha256(data).hexdigest(), size=len(data))
    monkeypatch.chdir(tmp_path)  # far from the repository
    scope = dict(zip(("jurisdiction", "document_class", "version"), SCOPE, strict=True))
    paths = script._paths(repo / "data/corpus", **scope)
    assert all(script._exists(repo, name, paths[name]) for name in script.ARTIFACT_CLASSES)
    provisions = "data/corpus/provisions/nz/statute/2026-07-10.jsonl"
    _write_files(repo, {provisions: FILES[provisions]})
    assert script._repair_derived(repo, paths, scope) == []
    for rel in ("data/corpus/inventory/nz/statute/2026-07-10.json", "data/corpus/coverage/nz/statute/2026-07-10.json"):
        assert (repo / rel).read_bytes() == FILES[rel]


def test_sign_with_lock_reports_lock_failures_without_a_traceback(
    repo: Path, monkeypatch, capsys
) -> None:
    """Opus r2-N2."""
    from axiom_corpus.corpus.cli import main as cli_main

    private, _public = _keys()
    _write_files(repo, FILES)
    _write_files(repo, {"data/corpus/sources/nz/statute/2026-07-10/official-documents/.DS_Store": b"x"})
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
            "--file", "data/corpus/provisions/nz/statute/2026-07-10.jsonl",
            "--lock",
        ]
    )  # fmt: skip
    assert status == 2
    assert "hidden file" in capsys.readouterr().err
    # Round 3: the check runs before signing, so no manifest attests the hidden file.
    assert not (repo / ".axiom/ingest-manifests/nz/statute/2026-07-10.json").exists()


def test_a_differently_cased_file_already_tracked_blocks_lock_mode(repo: Path) -> None:
    """Astra r2-2: the tracked-file listing must fold case, not use a `data` pathspec."""
    private, public = _keys()
    legacy = "DATA/corpus/provisions/zz/statute/v1.jsonl"
    _stage_blob(repo, legacy, b"legacy\n")
    _git(repo, "commit", "-q", "-m", "legacy file under another spelling")
    _git(repo, "update-index", "--skip-worktree", legacy)  # never written to disk
    base = _ingest(repo, private)  # this diff touches only lock files
    result = _guard(repo, base, public)
    assert any("tracked in git while" in issue and legacy in issue for issue in result.issues)


# =========================================================================== round 3


@pytest.mark.parametrize(
    "spelling",
    [
        "data/corpuſ/provisions/nz/statute/2026-07-11.jsonl",  # long s
        "DATA/CORPUS/PROVISIONS/nz/statute/2026-07-11.jsonl",
    ],
    ids=["long-s", "upper"],
)
def test_every_merged_spelling_of_a_protected_path_is_checked(repo: Path, spelling: str) -> None:
    """Round 3 (blocking): `.lower()` left U+017F long s unfolded."""
    from axiom_corpus.corpus.corpus_locks import lands_on_protected_path

    assert lands_on_protected_path(spelling)
    private, public = _keys()
    base = _ingest(repo, private)
    _stage_blob(repo, spelling, b'{"citation_path":"nz/statute/unsigned"}\n')
    _git(repo, "commit", "-q", "-m", "unsigned bytes under a merged spelling")
    result = _guard(repo, base, public)
    assert not result.passed
    assert any(spelling in issue for issue in result.issues)


@pytest.mark.parametrize("ancestor", ["data", "data/corpus", "data/corpus/provisions", "Data/Corpus"])
def test_a_tracked_file_standing_in_for_a_protected_directory_is_checked(repo: Path, ancestor: str) -> None:
    """Round 3 nit: a tracked symlink or file at a protected directory redirects it."""
    from axiom_corpus.corpus.corpus_locks import lands_on_protected_path

    assert lands_on_protected_path(ancestor)
    assert not lands_on_protected_path("data/corpus/anchors/us.json")
    assert not lands_on_protected_path("docs/data/corpus.md")


def test_a_lock_file_under_another_spelling_of_the_lock_root_fails_the_guard(repo: Path) -> None:
    """Round 3: `.AXIOM/corpus-locks` is the lock root on APFS but invisible to the guard."""
    _private, public = _keys()
    base = _git(repo, "rev-parse", "HEAD")
    lock = CorpusLock.from_entries(
        ("zz", "statute", "v1"),
        [LockEntry("data/corpus/provisions/zz/statute/v1.jsonl", hashlib.sha256(b"x").hexdigest(), 1)],
    )
    _stage_blob(repo, ".AXIOM/corpus-locks/zz/statute/v1.json", serialize_lock(lock))
    _git(repo, "commit", "-q", "-m", "planted lock under a variant spelling")
    result = _guard(repo, base, public)
    assert not result.passed
    assert any("another spelling" in issue for issue in result.issues)


def test_the_worktree_refuses_a_lock_directory_spelled_differently(tmp_path: Path) -> None:
    from axiom_corpus.corpus.corpus_locks import load_locks

    repo = tmp_path / "repo"
    variant = repo / ".AXIOM" / "Corpus-Locks" / "zz" / "statute"
    variant.mkdir(parents=True)
    (variant / "v1.json").write_text("{}")
    case_insensitive = (repo / ".axiom" / "corpus-locks").is_dir()
    locks = load_locks(repo)
    if case_insensitive:
        assert locks.errors and "spelled" in locks.errors[0]
    else:
        assert not locks and not locks.errors  # git and the resolver see no lock root


def test_first_parent_scan_reads_the_old_side_of_a_change(monkeypatch, tmp_path: Path) -> None:
    """Round 3 nit: a blob seen only as the old side (a deletion) must count."""
    from axiom_corpus.corpus import ingest_manifests

    old_blob = "a" * 40
    new_blob = "b" * 40
    raw = (
        f":100644 000000 {old_blob} {'0' * 40} D\0data/corpus/provisions/zz/statute/v1.jsonl\0"
        f"\n:000000 100644 {'0' * 40} {new_blob} A\0data/corpus/provisions/zz/statute/v2.jsonl\0"
    ).encode()

    class FakeProcess:
        def __init__(self, *_args, **_kwargs):
            import io

            self.stdout = io.BytesIO(raw)
            self.returncode = 0

        def poll(self):
            return 0

        def kill(self):
            pass

        def communicate(self):
            return b"", b""

    monkeypatch.setattr(ingest_manifests.subprocess, "Popen", FakeProcess)
    wanted = {
        "data/corpus/provisions/zz/statute/v1.jsonl": {old_blob},
        "data/corpus/provisions/zz/statute/v2.jsonl": {new_blob},
    }
    found = ingest_manifests.first_parent_path_blobs(tmp_path, "HEAD", wanted)
    assert found == {
        ("data/corpus/provisions/zz/statute/v1.jsonl", old_blob),
        ("data/corpus/provisions/zz/statute/v2.jsonl", new_blob),
    }


def test_audit_accepts_a_blob_main_gained_through_a_merge_commit(repo: Path) -> None:
    """Round 3 nit: the only way bytes reach main is a --no-ff merge; that must count."""
    _private, public = _keys()
    path = "data/corpus/provisions/yy/statute/v1.jsonl"
    data = b"legacy via merge\n"
    _git(repo, "checkout", "-q", "-b", "legacy")
    _stage_blob(repo, path, data)
    _git(repo, "commit", "-q", "-m", "legacy bytes on a branch")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "legacy", "-m", "merge legacy")
    blob = _git(repo, "rev-parse", f"HEAD:{path}")
    _git(repo, "rm", "-q", "--cached", path)
    write_lock(
        repo,
        CorpusLock.from_entries(
            ("yy", "statute", "v1"),
            [LockEntry(path, hashlib.sha256(data).hexdigest(), len(data), git_blob=blob)],
        ),
    )
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "move into lock")
    assert audit_lock_attestation(repo, ref="HEAD", public_key=public) == []


def test_guard_reads_locked_bytes_concurrently_and_reports_each_failure(repo: Path) -> None:
    """Round 3 (scale): reads run in parallel; one unreadable entry fails alone."""
    from axiom_corpus.corpus import ingest_manifests

    entries = [
        LockEntry(f"data/corpus/sources/nz/statute/2026-07-10/official/{i}.html", "0" * 64, 1)
        for i in range(70)
    ]
    unreadable = entries[40].path

    def reader(entry):
        if entry.path == unreadable:
            raise RuntimeError("R2 said no")
        return b"<p>ok</p>\n"

    issues = ingest_manifests._locked_content_issues(repo, entries, reader)
    assert len([i for i in issues if "Cannot read" in i]) == 1
    assert unreadable in next(i for i in issues if "Cannot read" in i)


def test_publishability_audit_keeps_going_past_an_unfetchable_scope(
    repo: Path, tmp_path: Path, monkeypatch
) -> None:
    """Round 3 nit: one scope's fetch failure used to abort the whole audit."""
    script = _publishability_script()
    write_lock(
        repo,
        CorpusLock.from_entries(
            SCOPE, [LockEntry(p, hashlib.sha256(d).hexdigest(), len(d)) for p, d in FILES.items()]
        ),
    )
    selector = repo / "manifests/releases/r.json"
    selector.parent.mkdir(parents=True)
    selector.write_text(
        json.dumps(
            {
                "name": "r",
                "scopes": [
                    dict(zip(("jurisdiction", "document_class", "version"), SCOPE, strict=True)),
                    {"jurisdiction": "zz", "document_class": "statute", "version": "v9"},
                ],
            }
        )
    )
    monkeypatch.setattr(
        "sys.argv",
        ["audit", "--repo", str(repo), "--release-ref", "WORKTREE", "--release-path",
         "manifests/releases/r.json", "--repair-derived"],
    )  # fmt: skip
    import contextlib
    import io

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status = script.main()
    report = json.loads(out.getvalue())
    assert status == 2
    assert report["scope_count"] == 2 and report["unfetchable_count"] == 1


def test_signing_refuses_hidden_source_files_even_without_lock(repo: Path) -> None:
    """Round 3 nit: a signed manifest must never attest bytes no lock may carry."""
    _write_files(repo, FILES)
    _write_files(repo, {"data/corpus/sources/nz/statute/2026-07-10/official-documents/.x.part": b"partial"})
    with pytest.raises(ValueError, match="hidden file"):
        build_ingest_manifest(
            repo=repo,
            base=Path("data/corpus"),
            jurisdiction=SCOPE[0],
            document_class=SCOPE[1],
            version=SCOPE[2],
            command="x",
        )


# =========================================================================== round 4


def test_a_submodule_under_the_lock_root_is_a_lock_error(repo: Path, tmp_path: Path) -> None:
    """Round 4: a gitlink under .axiom/corpus-locks passed the guard and the audit."""
    from axiom_corpus.corpus.corpus_locks import (
        load_locks,
        load_locks_at_ref,
        load_locks_from_index,
    )

    private, public = _keys()
    base = _ingest(repo, private)
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "T")
    (other / "README").write_text("x\n")
    _git(other, "add", "README")
    _git(other, "commit", "-q", "-m", "x")
    commit = _git(other, "rev-parse", "HEAD")
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{commit},.axiom/corpus-locks/zz")
    assert any("not a regular file" in error for error in load_locks_from_index(repo).errors)
    _git(repo, "commit", "-q", "-m", "gitlink under the lock root")
    assert any("submodule" in error for error in load_locks_at_ref(repo, "HEAD").errors)
    assert not _guard(repo, base, public).passed
    assert audit_lock_attestation(repo, ref="HEAD", public_key=public)
    # A checked-out submodule in the worktree is refused too.
    nested = repo / ".axiom/corpus-locks/zz"
    nested.mkdir(exist_ok=True)
    (nested / ".git").write_text(f"gitdir: {other}/.git\n")
    assert any("nested git" in error for error in load_locks(repo).errors)


def test_a_symlinked_lock_file_is_a_lock_error(repo: Path) -> None:
    from axiom_corpus.corpus.corpus_locks import load_locks

    private, _public = _keys()
    _ingest(repo, private)
    link = repo / ".axiom/corpus-locks/nz/statute/link.json"
    link.symlink_to(repo / lock_path_for_scope(SCOPE))
    assert any("symlink" in error for error in load_locks(repo).errors)


@pytest.mark.parametrize(
    "spelling",
    [
        "data/corpu‌s/provisions/nz/statute/2026-07-11.jsonl",  # ZWNJ: HFS+ ignores it
        "data/corpus/provısions/nz/statute/2026-07-11.jsonl",  # dotless i: NTFS upcases to I
        "data/corpus/provisions﻿/nz/statute/2026-07-11.jsonl",  # BOM
    ],
    ids=["zwnj", "dotless-i", "bom"],
)
def test_ignorable_and_dotless_spellings_are_protected(repo: Path, spelling: str) -> None:
    """Round 4: fold_path kept format characters and the dotless i."""
    from axiom_corpus.corpus.corpus_locks import lands_on_lock_root, lands_on_protected_path

    assert lands_on_protected_path(spelling)
    assert lands_on_lock_root(".axiom/corpus‌-locks/x.json")
    private, public = _keys()
    base = _ingest(repo, private)
    _stage_blob(repo, spelling, b'{"citation_path":"nz/statute/unsigned"}\n')
    _git(repo, "commit", "-q", "-m", "unsigned bytes under an ignorable spelling")
    assert not _guard(repo, base, public).passed


def test_the_audit_flags_a_variant_lock_root_already_on_main(repo: Path) -> None:
    """Round 4 nit: a variant-spelled lock already on main was never reported again."""
    private, public = _keys()
    _ingest(repo, private)
    _stage_blob(repo, ".AXIOM/corpus-locks/zz/statute/v1.json", b"{}\n")
    _git(repo, "commit", "-q", "-m", "variant lock root")
    issues = audit_lock_attestation(repo, ref="HEAD", public_key=public)
    assert any("another spelling" in issue for issue in issues)


def test_the_citation_script_skips_hidden_lock_files(tmp_path: Path, monkeypatch) -> None:
    """Round 4 nit: the stdlib loader crashed on an AppleDouble ._x.json."""
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_citation_paths.py"
    spec = importlib.util.spec_from_file_location("validate_citation_paths", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "repo"
    lock_dir = root / ".axiom/corpus-locks/nz/statute"
    lock_dir.mkdir(parents=True)
    (lock_dir / "._v1.json").write_bytes(b"\x00\x05\x16\x07binary AppleDouble")
    (lock_dir / "v1.json").write_text(
        json.dumps({"files": [{"path": "data/corpus/provisions/nz/statute/v1.jsonl"}]})
    )
    monkeypatch.setattr(module, "REPO_ROOT", root)
    provisions = root / "data/corpus/provisions"
    provisions.mkdir(parents=True)
    assert module.unfetched_locked_provisions(provisions) == ["data/corpus/provisions/nz/statute/v1.jsonl"]


# =========================================================================== round 5


@pytest.mark.parametrize("kind", ["gitlink", "symlink"])
def test_a_non_directory_axiom_hides_nothing(repo: Path, tmp_path: Path, kind: str) -> None:
    """Round 5 nit: `.axiom` as a gitlink or symlink escaped every lock check."""
    from axiom_corpus.corpus.corpus_locks import load_locks_at_ref

    private, public = _keys()
    _ingest(repo, private)
    _git(repo, "rm", "-rq", "--cached", ".axiom")
    if kind == "gitlink":
        other = tmp_path / "other"
        other.mkdir()
        _git(other, "init", "-q", "-b", "main")
        _git(other, "config", "user.email", "t@example.com")
        _git(other, "config", "user.name", "T")
        (other / "README").write_text("x\n")
        _git(other, "add", "README")
        _git(other, "commit", "-q", "-m", "x")
        _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{_git(other, 'rev-parse', 'HEAD')},.axiom")
    else:
        oid = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"], cwd=repo, input=b"docs/elsewhere", check=True, capture_output=True
        ).stdout.decode().strip()
        _git(repo, "update-index", "--add", "--cacheinfo", f"120000,{oid},.axiom")
    _git(repo, "commit", "-q", "-m", f".axiom as a {kind}")
    errors = load_locks_at_ref(repo, "HEAD").errors
    assert any("not a directory" in error for error in errors)
    assert any("not a directory" in issue for issue in audit_lock_attestation(repo, ref="HEAD", public_key=public))


def test_a_symlinked_lock_root_in_the_worktree_is_refused(tmp_path: Path) -> None:
    from axiom_corpus.corpus.corpus_locks import load_locks

    repo = tmp_path / "repo"
    elsewhere = repo / "docs/evil/corpus-locks/zz/statute"
    elsewhere.mkdir(parents=True)
    (elsewhere / "v1.json").write_text("{}")
    (repo / ".axiom").mkdir()
    (repo / ".axiom/corpus-locks").symlink_to(repo / "docs/evil/corpus-locks")
    assert any("symlink" in error for error in load_locks(repo).errors)


def test_an_emacs_lock_link_in_the_lock_directory_is_ignored(repo: Path) -> None:
    """Round 5 (regression): a dangling `.#file` link made every read fail."""
    from axiom_corpus.corpus.corpus_locks import load_locks

    private, _public = _keys()
    _ingest(repo, private)
    link = repo / ".axiom/corpus-locks/nz/statute/.#2026-07-10.json"
    link.symlink_to("user@host.1234:1700000000")
    locks = load_locks(repo)
    assert locks.errors == () and SCOPE in locks.locks
