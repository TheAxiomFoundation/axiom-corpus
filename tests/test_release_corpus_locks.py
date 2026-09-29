"""Release publication and scope tracking with corpus bytes pinned by lock files."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.scope_tracking import verify_scope_tracked
from axiom_corpus.release.manifest import ReleaseManifestError, _require_tracked_release_inputs

SCOPE = ("nz", "statute", "v1")
FILES = {
    "data/corpus/sources/nz/statute/v1/act.html": b"<p>Act</p>\n",
    "data/corpus/sources/nz/statute/v1/regs.html": b"<p>Regs</p>\n",
    "data/corpus/inventory/nz/statute/v1.json": json.dumps(
        {"items": [{"citation_path": "nz/statute/a", "source_path": "sources/nz/statute/v1/act.html"}]}
    ).encode(),
    "data/corpus/provisions/nz/statute/v1.jsonl": b'{"citation_path":"nz/statute/a"}\n',
    "data/corpus/coverage/nz/statute/v1.json": b'{"complete": true}\n',
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _entry(path: str, data: bytes) -> LockEntry:
    return LockEntry(path, hashlib.sha256(data).hexdigest(), len(data))


@pytest.fixture(autouse=True)
def no_real_r2(monkeypatch, tmp_path: Path):
    """Keep tests off the developer's R2 credentials and shared cache."""
    from axiom_corpus.corpus import content_store
    from axiom_corpus.corpus import resolver as resolver_module

    def refuse(cls, **_kwargs):
        raise RuntimeError("R2 is disabled in tests")

    monkeypatch.setattr(content_store.R2ObjectStore, "from_environment", classmethod(refuse))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "default-cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})


@pytest.fixture
def locked_repo(tmp_path: Path) -> tuple[Path, ReleaseManifest]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text("data/\n")
    release = ReleaseManifest(name="nz-rulespec-v1", scopes=(ReleaseScope(*SCOPE),))
    selector = repo / "manifests/releases/nz-rulespec-v1.json"
    selector.parent.mkdir(parents=True)
    selector.write_text(
        json.dumps(
            {"name": release.name, "scopes": [dict(zip(("jurisdiction", "document_class", "version"), SCOPE, strict=True))]}
        )
    )
    for rel, data in FILES.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes(data)
    write_lock(repo, CorpusLock.from_entries(SCOPE, [_entry(p, d) for p, d in FILES.items()]))
    _git(repo, "add", ".gitignore", "manifests", ".axiom")
    _git(repo, "commit", "-q", "-m", "lock and selector")
    return repo, release


def _artifacts(files: dict[str, bytes]) -> list[dict[str, object]]:
    return [
        {"path": p, "sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d)}
        for p, d in sorted(files.items())
    ]


def test_locked_artifacts_satisfy_the_committed_inputs_check(locked_repo) -> None:
    repo, release = locked_repo
    _require_tracked_release_inputs(repo, release=release, artifacts=_artifacts(FILES))


def test_an_artifact_whose_bytes_differ_from_its_lock_is_rejected(locked_repo) -> None:
    repo, release = locked_repo
    files = dict(FILES)
    files["data/corpus/provisions/nz/statute/v1.jsonl"] = b'{"citation_path":"nz/statute/b"}\n'
    with pytest.raises(ReleaseManifestError, match="pinned by a committed corpus lock"):
        _require_tracked_release_inputs(repo, release=release, artifacts=_artifacts(files))


def test_a_partly_fetched_scope_cannot_be_released(locked_repo) -> None:
    repo, release = locked_repo
    files = {p: d for p, d in FILES.items() if not p.endswith("regs.html")}
    with pytest.raises(ReleaseManifestError, match="not fully materialized"):
        _require_tracked_release_inputs(repo, release=release, artifacts=_artifacts(files))


def test_an_unlocked_extra_file_is_rejected(locked_repo) -> None:
    repo, release = locked_repo
    files = dict(FILES)
    files["data/corpus/sources/nz/statute/v1/stray.html"] = b"stray"
    with pytest.raises(ReleaseManifestError, match="stray.html"):
        _require_tracked_release_inputs(repo, release=release, artifacts=_artifacts(files))


def test_scope_tracking_accepts_locked_inventories_and_sources(locked_repo) -> None:
    repo, _release = locked_repo
    result = verify_scope_tracked(repo=repo, jurisdiction="nz")
    assert result.passed, result.missing_paths
    assert result.scopes_checked == 1 and result.files_verified == 1


def test_scope_tracking_flags_a_reference_to_an_unlocked_source(locked_repo) -> None:
    repo, _release = locked_repo
    inventory = json.dumps(
        {"items": [{"citation_path": "nz/statute/b", "source_path": "sources/nz/statute/v1/missing.html"}]}
    ).encode()
    files = dict(FILES)
    files["data/corpus/inventory/nz/statute/v1.json"] = inventory
    (repo / "data/corpus/inventory/nz/statute/v1.json").write_bytes(inventory)
    write_lock(repo, CorpusLock.from_entries(SCOPE, [_entry(p, d) for p, d in files.items()]))
    _git(repo, "add", ".axiom")  # scope tracking reads staged locks
    result = verify_scope_tracked(repo=repo)
    assert result.missing_paths == ("data/corpus/sources/nz/statute/v1/missing.html",)
