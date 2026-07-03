"""End-to-end tests for the ``axiom-corpus-release`` CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axiom_corpus.release import cli
from axiom_corpus.release.manifest import RELEASE_MANIFEST_SIGNING_KEY_ENV

SIGNING_KEY = "test-release-signing-key-0123456789"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def corpus_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    base = root / "data" / "corpus"
    (base / "provisions" / "us" / "statute").mkdir(parents=True)
    (base / "coverage" / "us" / "statute").mkdir(parents=True)
    (root / "claims" / "us").mkdir(parents=True)
    (base / "provisions" / "us" / "statute" / "a.jsonl").write_text(
        '{"id": "1"}\n{"id": "2"}\n'
    )
    (base / "coverage" / "us" / "statute" / "a.json").write_text('{"complete": true}\n')
    (root / "claims" / "us" / "c.jsonl").write_text('{"subject": {"id": "x"}}\n')
    (root / "DATA_INVENTORY.md").write_text("# Inventory\n")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "-A", "-f")
    _git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed")
    return root


def _emit(repo: Path, out: Path) -> int:
    return cli.main(
        [
            "emit-release-manifest",
            "--release",
            "r0",
            "--repo-root",
            str(repo),
            "--out",
            str(out),
        ]
    )


def test_emit_writes_signed_manifest(
    corpus_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv(RELEASE_MANIFEST_SIGNING_KEY_ENV, SIGNING_KEY)
    out = tmp_path / "out" / "release_manifest.json"
    assert _emit(corpus_repo, out) == 0
    assert out.is_file()

    manifest = json.loads(out.read_text())
    assert manifest["release"] == "r0"
    assert manifest["signature"]["algorithm"] == "hmac-sha256"
    assert manifest["summary"]["provisions"]["rows"] == 2

    report = json.loads(capsys.readouterr().out)
    assert report["signed"] is True
    assert report["provision_rows"] == 2
    assert report["files"] >= 3


def test_emit_unsigned_without_key(
    corpus_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.delenv(RELEASE_MANIFEST_SIGNING_KEY_ENV, raising=False)
    out = tmp_path / "release_manifest.json"
    assert _emit(corpus_repo, out) == 0
    manifest = json.loads(out.read_text())
    assert "signature" not in manifest
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["signed"] is False
    assert "not set" in captured.err


def test_verify_passes_on_clean_tree(
    corpus_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv(RELEASE_MANIFEST_SIGNING_KEY_ENV, SIGNING_KEY)
    out = tmp_path / "release_manifest.json"
    _emit(corpus_repo, out)
    capsys.readouterr()

    rc = cli.main(
        [
            "verify-release-manifest",
            "--manifest",
            str(out),
            "--repo-root",
            str(corpus_repo),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["ok"] is True
    assert report["signature_checked"] is True
    assert report["content_checked"] is True
    assert report["problems"] == []


def test_verify_detects_content_tamper(
    corpus_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv(RELEASE_MANIFEST_SIGNING_KEY_ENV, SIGNING_KEY)
    out = tmp_path / "release_manifest.json"
    _emit(corpus_repo, out)
    capsys.readouterr()

    # Mutate a hashed artifact on disk after the manifest was written.
    prov = (
        corpus_repo
        / "data"
        / "corpus"
        / "provisions"
        / "us"
        / "statute"
        / "a.jsonl"
    )
    prov.write_text('{"id": "1"}\n{"id": "2"}\n{"id": "3"}\n')

    rc = cli.main(
        [
            "verify-release-manifest",
            "--manifest",
            str(out),
            "--repo-root",
            str(corpus_repo),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["ok"] is False
    joined = " ".join(report["problems"])
    assert "sha256 mismatch" in joined
    assert "row-count mismatch" in joined


def test_verify_detects_signature_tamper(
    corpus_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv(RELEASE_MANIFEST_SIGNING_KEY_ENV, SIGNING_KEY)
    out = tmp_path / "release_manifest.json"
    _emit(corpus_repo, out)
    capsys.readouterr()

    manifest = json.loads(out.read_text())
    manifest["signature"]["value"] = "0" * 64
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    rc = cli.main(
        [
            "verify-release-manifest",
            "--manifest",
            str(out),
            "--repo-root",
            str(corpus_repo),
            "--signature-only",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("signature" in problem for problem in report["problems"])
    assert report["content_checked"] is False


def test_verify_missing_key_can_require_signature(
    corpus_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv(RELEASE_MANIFEST_SIGNING_KEY_ENV, SIGNING_KEY)
    out = tmp_path / "release_manifest.json"
    _emit(corpus_repo, out)
    capsys.readouterr()

    monkeypatch.delenv(RELEASE_MANIFEST_SIGNING_KEY_ENV, raising=False)
    # Without the key, signature check is skipped and content still verifies.
    rc = cli.main(
        [
            "verify-release-manifest",
            "--manifest",
            str(out),
            "--repo-root",
            str(corpus_repo),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["signature_checked"] is False

    # With --require-signature and no key, it fails.
    rc = cli.main(
        [
            "verify-release-manifest",
            "--manifest",
            str(out),
            "--repo-root",
            str(corpus_repo),
            "--require-signature",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("required" in problem for problem in report["problems"])
