"""Hard-cut provenance tests for signed corpus ingest manifests."""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
import subprocess
import sys
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus import atomic_write
from axiom_corpus.corpus.ingest_manifests import (
    INGEST_MANIFEST_SIGNATURE_ALGORITHM,
    build_ingest_manifest,
    guard_ingested_artifacts,
    sign_ingest_manifest,
    verify_ingest_manifest,
    write_signed_ingest_manifest,
)
from tests.test_atomic_write import _FaultyOs


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "README.md").write_text("seed\n")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "Initial commit")
    return path


def _keys() -> tuple[Ed25519PrivateKey, str, str]:
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
    return key, private, public


def _artifact(repo: Path, *, version: str = "2026-07-10") -> Path:
    path = repo / f"data/corpus/provisions/nz/statute/{version}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"citation_path":"nz/statute/example","body":"Example."}\n')
    return path


def _manifest(repo: Path, artifact: Path) -> dict[str, object]:
    return build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
    )


def _sign_unchecked(payload: dict[str, object], key: Ed25519PrivateKey) -> dict[str, object]:
    signed = copy.deepcopy(payload)
    signed.pop("signature", None)
    canonical = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
    signed["signature"] = {
        "algorithm": INGEST_MANIFEST_SIGNATURE_ALGORITHM,
        "key_id": "test",
        "value": b64encode(key.sign(canonical)).decode("ascii"),
    }
    return signed


def _write_manifest(repo: Path, payload: dict[str, object], *, version: str) -> Path:
    path = repo / f".axiom/ingest-manifests/nz/statute/{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_build_records_clean_repo_relative_full_commit(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    manifest = _manifest(repo, _artifact(repo))

    assert manifest["axiom_corpus_git"] == {
        "root": ".",
        "commit": _git(repo, "rev-parse", "HEAD"),
        "dirty_tracked": False,
    }


@pytest.mark.parametrize("staged", [False, True])
def test_build_rejects_dirty_tracked_generator_state(tmp_path: Path, staged: bool) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    (repo / "README.md").write_text("modified\n")
    if staged:
        _git(repo, "add", "README.md")

    with pytest.raises(ValueError, match="dirty_tracked.*must be false"):
        _manifest(repo, artifact)


def test_sign_rejects_dirty_tracked_generator_provenance(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    manifest = _manifest(repo, _artifact(repo))
    manifest["axiom_corpus_git"]["dirty_tracked"] = True
    _key, private, _public = _keys()

    with pytest.raises(ValueError, match="dirty_tracked.*must be false"):
        sign_ingest_manifest(manifest, private_key=private)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("root", "/tmp/checkout", "root` must be `.`"),
        ("dirty_tracked", True, "dirty_tracked` must be false"),
        ("commit", "abc123", "full 40-character lowercase Git commit"),
    ],
)
def test_verification_rejects_noncanonical_generator_provenance(
    tmp_path: Path,
    field: str,
    value: object,
    expected: str,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    manifest = _manifest(repo, _artifact(repo))
    manifest["axiom_corpus_git"][field] = value
    key, _private, public = _keys()
    signed = _sign_unchecked(manifest, key)

    issues = verify_ingest_manifest(
        signed,
        public_key=public,
        repo=repo,
        head_ref="HEAD",
    )

    assert any(expected in issue for issue in issues)
    assert "Invalid ingest manifest signature." not in issues


def test_verification_accepts_attested_commit_ancestor_of_guarded_head(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    manifest = _manifest(repo, _artifact(repo))
    _key, private, public = _keys()
    signed = sign_ingest_manifest(manifest, private_key=private)
    (repo / "CHANGELOG.md").write_text("later\n")
    _git(repo, "add", "CHANGELOG.md")
    _git(repo, "commit", "-m", "Later commit")

    assert (
        verify_ingest_manifest(
            signed,
            public_key=public,
            repo=repo,
            head_ref="HEAD",
        )
        == []
    )


def test_verification_rejects_attested_commit_outside_guarded_head_history(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    manifest = _manifest(repo, _artifact(repo))
    _git(repo, "checkout", "-b", "side")
    (repo / "side.txt").write_text("side\n")
    _git(repo, "add", "side.txt")
    _git(repo, "commit", "-m", "Side commit")
    side_commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    (repo / "main.txt").write_text("main\n")
    _git(repo, "add", "main.txt")
    _git(repo, "commit", "-m", "Main commit")
    manifest["axiom_corpus_git"]["commit"] = side_commit
    key, _private, public = _keys()
    signed = _sign_unchecked(manifest, key)

    issues = verify_ingest_manifest(
        signed,
        public_key=public,
        repo=repo,
        head_ref="main",
    )

    assert any("is not an ancestor of guarded head `main`" in issue for issue in issues)


def test_guard_rejects_noncanonical_manifest_when_it_authorizes_change(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    base_commit = _git(repo, "rev-parse", "HEAD")
    artifact = _artifact(repo)
    manifest = _manifest(repo, artifact)
    manifest["axiom_corpus_git"]["root"] = "/legacy/checkout"
    key, _private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        _sign_unchecked(manifest, key),
        version=artifact.stem,
    )
    _git(repo, "add", str(artifact.relative_to(repo)), str(manifest_path.relative_to(repo)))
    _git(repo, "commit", "-m", "Add artifact with legacy manifest")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert any("root` must be `.`" in issue for issue in result.issues)


def test_guard_rejects_manifest_commit_outside_guarded_head_history(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    base_commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-b", "side")
    (repo / "side.txt").write_text("side\n")
    _git(repo, "add", "side.txt")
    _git(repo, "commit", "-m", "Side commit")
    side_commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    artifact = _artifact(repo)
    manifest = _manifest(repo, artifact)
    manifest["axiom_corpus_git"]["commit"] = side_commit
    key, _private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        _sign_unchecked(manifest, key),
        version=artifact.stem,
    )
    _git(repo, "add", str(artifact.relative_to(repo)), str(manifest_path.relative_to(repo)))
    _git(repo, "commit", "-m", "Add artifact from unrelated generator commit")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert any("is not an ancestor of guarded head `HEAD`" in issue for issue in result.issues)


def test_guard_rejects_changed_reasoning_log_without_resigning(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    _key, private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    base_commit = _git(repo, "rev-parse", "HEAD")

    reasoning_log.write_text("changed reasoning\n")
    _git(repo, "add", str(reasoning_log.relative_to(repo)))
    _git(repo, "commit", "-m", "Change reasoning")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert result.protected_changes == ()
    assert any(
        f"{reasoning_log.relative_to(repo)}` sha256 does not match" in issue
        for issue in result.issues
    )
    assert manifest_path.relative_to(repo).as_posix() in result.issues[0]


def test_guard_accepts_changed_reasoning_log_after_resigning(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    _key, private, public = _keys()

    def signed_manifest() -> dict[str, object]:
        manifest = build_ingest_manifest(
            repo=repo,
            base=Path("data/corpus"),
            jurisdiction="nz",
            document_class="statute",
            version=artifact.stem,
            command="axiom-corpus-ingest extract-nz-legislation",
            applied_files=[artifact],
            reasoning_logs=[reasoning_log],
        )
        return sign_ingest_manifest(manifest, private_key=private)

    manifest_path = _write_manifest(repo, signed_manifest(), version=artifact.stem)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    base_commit = _git(repo, "rev-parse", "HEAD")

    reasoning_log.write_text("changed reasoning\n")
    _git(repo, "add", str(reasoning_log.relative_to(repo)))
    _git(repo, "commit", "-m", "Change reasoning")
    manifest_path.write_text(json.dumps(signed_manifest(), indent=2, sort_keys=True) + "\n")
    _git(repo, "add", str(manifest_path.relative_to(repo)))
    _git(repo, "commit", "-m", "Re-sign reasoning")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert result.passed
    assert result.protected_changes == ()
    assert result.issues == ()


def test_guard_rejects_changed_reasoning_log_with_removed_attestation(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    key, _private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        _sign_unchecked(manifest, key),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    base_commit = _git(repo, "rev-parse", "HEAD")

    reasoning_log.write_text("changed reasoning\n")
    manifest["reasoning_logs"] = []
    manifest_path.write_text(
        json.dumps(_sign_unchecked(manifest, key), indent=2, sort_keys=True) + "\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Remove reasoning attestation")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert any("is no longer attested" in issue for issue in result.issues)


def test_guard_rejects_manifest_only_reasoning_attestation_removal(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    _key, private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    base_commit = _git(repo, "rev-parse", "HEAD")

    payload = json.loads(manifest_path.read_text())
    payload["reasoning_logs"] = []
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", str(manifest_path.relative_to(repo)))
    _git(repo, "commit", "-m", "Remove reasoning attestation")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert any("Invalid ingest manifest signature" in issue for issue in result.issues)


def test_guard_rejects_uncommitted_reasoning_attestation_removal(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    _key, private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")

    payload = json.loads(manifest_path.read_text())
    payload["reasoning_logs"] = []
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    result = guard_ingested_artifacts(
        repo=repo,
        public_key=public,
    )

    assert not result.passed
    assert any("Invalid ingest manifest signature" in issue for issue in result.issues)


def test_guard_manifest_reads_ignore_export_attributes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    _key, private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    signed_commit = _git(repo, "rev-parse", "HEAD")

    (repo / ".gitattributes").write_text(
        f"{manifest_path.relative_to(repo).as_posix()} export-ignore\n"
    )
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "Exclude manifest from archives")
    attributes_commit = _git(repo, "rev-parse", "HEAD")

    attribute_result = guard_ingested_artifacts(
        repo=repo,
        base_ref=signed_commit,
        head_ref="HEAD",
        public_key=public,
    )
    assert attribute_result.passed

    reasoning_log.write_text("changed reasoning\n")
    _git(repo, "add", str(reasoning_log.relative_to(repo)))
    _git(repo, "commit", "-m", "Change reasoning")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=attributes_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert any("signed reasoning log entry" in issue for issue in result.issues)


def test_guard_reports_manifest_batch_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    _key, private, public = _keys()
    _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    base_commit = _git(repo, "rev-parse", "HEAD")
    reasoning_log.write_text("changed reasoning\n")
    _git(repo, "add", str(reasoning_log.relative_to(repo)))
    _git(repo, "commit", "-m", "Change reasoning")

    real_run = subprocess.run

    def failing_ls_tree(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command = args[0]
        if isinstance(command, list) and command[:2] == ["git", "ls-tree"]:
            return subprocess.CompletedProcess(command, 1, b"", b"synthetic failure")
        return real_run(*args, **kwargs)  # type: ignore[arg-type,return-value]

    monkeypatch.setattr(subprocess, "run", failing_ls_tree)
    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert result.issues == (
        "Unable to list ingest manifests at `HEAD`: synthetic failure",
    )


@pytest.mark.parametrize("filename", ["résumé.jsonl", "control\tname.jsonl"])
def test_guard_rejects_unmanifested_quoted_protected_paths(
    tmp_path: Path,
    filename: str,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    base_commit = _git(repo, "rev-parse", "HEAD")
    artifact = repo / "data/corpus/provisions/nz/statute" / filename
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"citation_path":"nz/statute/example","body":"Example."}\n')
    _git(repo, "add", str(artifact.relative_to(repo)))
    _git(repo, "commit", "-m", "Add unmanifested artifact")
    _key, _private, public = _keys()

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    relative_path = artifact.relative_to(repo).as_posix()
    assert not result.passed
    assert result.protected_changes == (relative_path,)
    assert any(relative_path in issue for issue in result.issues)


@pytest.mark.parametrize(
    "filename",
    [
        "résumé.md",
        "control\tname.md",
        "terminal-tab.md\t",
        "terminal-newline.md\n",
        "terminal-space.md ",
    ],
)
@pytest.mark.parametrize("committed", [False, True])
def test_guard_rejects_quoted_reasoning_log_drift(
    tmp_path: Path,
    filename: str,
    committed: bool,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs" / filename
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    _key, private, public = _keys()
    _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    base_commit = _git(repo, "rev-parse", "HEAD")

    reasoning_log.write_text("changed reasoning\n")
    if committed:
        _git(repo, "add", str(reasoning_log.relative_to(repo)))
        _git(repo, "commit", "-m", "Change reasoning")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit if committed else None,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert any("signed reasoning log entry" in issue for issue in result.issues)


@pytest.mark.parametrize("suffix", ["\t", "\n", " "])
@pytest.mark.parametrize("committed", [False, True])
def test_guard_preserves_exact_applied_file_paths(
    tmp_path: Path,
    suffix: str,
    committed: bool,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact_dir = repo / "data/corpus/provisions/nz/statute"
    artifact_dir.mkdir(parents=True)
    signed_artifact = artifact_dir / f"authorized.jsonl{suffix}"
    changed_artifact = artifact_dir / "authorized.jsonl"
    signed_body = '{"citation_path":"nz/statute/signed","body":"Authorized."}\n'
    signed_artifact.write_text(signed_body)
    changed_artifact.write_text('{"citation_path":"nz/statute/changed","body":"Original."}\n')
    _git(repo, "add", str(artifact_dir.relative_to(repo)))
    _git(repo, "commit", "-m", "Add distinct artifact paths")

    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version="2026-07-10",
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[signed_artifact],
    )
    _key, private, public = _keys()
    _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version="2026-07-10",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Sign padded artifact path")
    base_commit = _git(repo, "rev-parse", "HEAD")

    changed_artifact.write_text(signed_body)
    if committed:
        _git(repo, "add", str(changed_artifact.relative_to(repo)))
        _git(repo, "commit", "-m", "Change unpadded artifact")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit if committed else None,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert any("Unmanifested corpus artifact change" in issue for issue in result.issues)


def test_guard_checks_reasoning_logs_for_authorized_artifact_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    artifact = _artifact(repo)
    reasoning_log = repo / "docs/ingest-runs/example.md"
    reasoning_log.parent.mkdir(parents=True)
    reasoning_log.write_text("original reasoning\n")
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version=artifact.stem,
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[artifact],
        reasoning_logs=[reasoning_log],
    )
    key, _private, public = _keys()
    manifest_path = _write_manifest(
        repo,
        _sign_unchecked(manifest, key),
        version=artifact.stem,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add signed artifact")
    base_commit = _git(repo, "rev-parse", "HEAD")

    artifact.write_text('{"citation_path":"nz/statute/example","body":"Changed."}\n')
    reasoning_log.write_text("changed reasoning\n")
    _git(repo, "add", str(artifact.relative_to(repo)), str(reasoning_log.relative_to(repo)))
    _git(repo, "commit", "-m", "Change artifact and reasoning")

    manifest["axiom_corpus_git"]["commit"] = _git(repo, "rev-parse", "HEAD")
    manifest["applied_files"][0]["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(_sign_unchecked(manifest, key), indent=2, sort_keys=True) + "\n"
    )
    _git(repo, "add", str(manifest_path.relative_to(repo)))
    _git(repo, "commit", "-m", "Re-sign artifact only")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert not result.passed
    assert not any("corpus artifact" in issue for issue in result.issues)
    assert any("signed reasoning log entry" in issue for issue in result.issues)


def test_guard_ignores_noncanonical_manifest_until_it_authorizes_change(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    base_commit = _git(repo, "rev-parse", "HEAD")
    artifact = _artifact(repo)
    manifest = _manifest(repo, artifact)
    key, private, public = _keys()
    valid_path = _write_manifest(
        repo,
        sign_ingest_manifest(manifest, private_key=private),
        version=artifact.stem,
    )
    legacy = copy.deepcopy(manifest)
    legacy["version"] = "legacy-unused"
    legacy["axiom_corpus_git"]["root"] = "/legacy/checkout"
    legacy["applied_files"] = [
        {
            "path": "data/corpus/provisions/nz/statute/legacy-unused.jsonl",
            "sha256": "0" * 64,
        }
    ]
    legacy_path = _write_manifest(
        repo,
        _sign_unchecked(legacy, key),
        version="legacy-unused",
    )
    _git(
        repo,
        "add",
        str(artifact.relative_to(repo)),
        str(valid_path.relative_to(repo)),
        str(legacy_path.relative_to(repo)),
    )
    _git(repo, "commit", "-m", "Add artifact and manifests")

    result = guard_ingested_artifacts(
        repo=repo,
        base_ref=base_commit,
        head_ref="HEAD",
        public_key=public,
    )

    assert result.passed
    assert result.issues == ()


# A manifest at its final path is always a complete signed document. The
# signing script keeps any manifest that already exists
# (scripts/sign_release_scopes.sh), so a truncated one would be committed.

_SIGNED_MANIFEST = Path(".axiom/ingest-manifests/nz/statute/2026-07-10.json")


def _signed_manifest_setup(
    tmp_path: Path, *, prior: bool
) -> tuple[Path, dict[str, object], str, str, bytes | None]:
    """A repo, a manifest to sign, the key pair, and the manifest already signed, if any."""
    repo = _init_repo(tmp_path / "repo")
    manifest = _manifest(repo, _artifact(repo))
    _key, private, public = _keys()
    previous = None
    if prior:
        earlier = copy.deepcopy(manifest)
        earlier["command"] = {"text": "an earlier signing of the same scope"}
        write_signed_ingest_manifest(repo=repo, manifest=earlier, private_key=private)
        previous = (repo / _SIGNED_MANIFEST).read_bytes()
    return repo, manifest, private, public, previous


def _assert_manifest_untouched(repo: Path, previous: bytes | None) -> None:
    manifest_path = repo / _SIGNED_MANIFEST
    if previous is None:
        assert not manifest_path.exists()
        assert list(manifest_path.parent.iterdir()) == []
    else:
        assert manifest_path.read_bytes() == previous
        assert list(manifest_path.parent.iterdir()) == [manifest_path]


@pytest.mark.parametrize("prior", [False, True], ids=["first-signing", "re-signing"])
@pytest.mark.parametrize(
    "exc",
    [OSError(errno.ENOSPC, "No space left on device"), KeyboardInterrupt()],
    ids=["disk-full", "ctrl-c"],
)
def test_manifest_write_failing_partway_leaves_no_partial_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prior: bool, exc: BaseException
) -> None:
    """Half the manifest's bytes are written, then the write raises."""
    repo, manifest, private, _public, previous = _signed_manifest_setup(tmp_path, prior=prior)
    monkeypatch.setattr(atomic_write, "os", _FaultyOs("fdopen", exc))

    with pytest.raises(type(exc)):
        write_signed_ingest_manifest(repo=repo, manifest=manifest, private_key=private)

    _assert_manifest_untouched(repo, previous)


# Signs under a file-size limit, so the OS itself cuts the write short: the
# file stops at RLIMIT_FSIZE bytes and the rest fails with EFBIG (CPython
# ignores SIGXFSZ, so the process gets the error instead of being killed).
# A limit of 0 means no limit.
_SIGN_UNDER_FILE_SIZE_LIMIT = """
import errno
import json
import os
import resource
import sys
from pathlib import Path

from axiom_corpus.corpus.ingest_manifests import write_signed_ingest_manifest

repo, limit = Path(sys.argv[1]), int(sys.argv[2])
manifest = json.load(sys.stdin)
if limit:
    _soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, hard))
try:
    write_signed_ingest_manifest(
        repo=repo, manifest=manifest, private_key=os.environ["TEST_INGEST_PRIVATE_KEY"]
    )
except OSError as exc:
    print(errno.errorcode.get(exc.errno, exc.errno))
    sys.exit(3)
"""
_FILE_SIZE_LIMIT = 256


@pytest.mark.skipif(sys.platform == "win32", reason="RLIMIT_FSIZE is POSIX-only")
@pytest.mark.parametrize("prior", [False, True], ids=["first-signing", "re-signing"])
def test_manifest_write_cut_short_by_the_os_leaves_no_partial_manifest(
    tmp_path: Path, prior: bool
) -> None:
    """A short write at the OS level, with no patching of the writer.

    Writing in place at the final path left the first bytes of the manifest
    there (a truncated JSON document) when the write failed.
    """
    repo, manifest, private, public, previous = _signed_manifest_setup(tmp_path, prior=prior)

    def sign(limit: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", _SIGN_UNDER_FILE_SIZE_LIMIT, str(repo), str(limit)],
            input=json.dumps(manifest),
            env={**os.environ, "TEST_INGEST_PRIVATE_KEY": private},
            capture_output=True,
            text=True,
            check=False,
        )

    cut_short = sign(_FILE_SIZE_LIMIT)

    assert (cut_short.returncode, cut_short.stdout.strip()) == (3, "EFBIG"), cut_short.stderr
    _assert_manifest_untouched(repo, previous)

    retried = sign(0)

    assert retried.returncode == 0, retried.stderr
    manifest_path = repo / _SIGNED_MANIFEST
    written = manifest_path.read_bytes()
    assert len(written) > _FILE_SIZE_LIMIT
    signed = json.loads(written)
    assert signed["command"] == manifest["command"]
    assert verify_ingest_manifest(signed, public_key=public, repo=repo, head_ref="HEAD") == []
    assert list(manifest_path.parent.iterdir()) == [manifest_path]
