"""Hard-cut provenance tests for signed corpus ingest manifests."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.ingest_manifests import (
    INGEST_MANIFEST_SIGNATURE_ALGORITHM,
    build_ingest_manifest,
    guard_ingested_artifacts,
    sign_ingest_manifest,
    verify_ingest_manifest,
)


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
