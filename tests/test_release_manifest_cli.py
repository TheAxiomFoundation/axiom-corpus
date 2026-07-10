from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.release import cli
from axiom_corpus.release.cli import _verify_local_artifacts
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    build_unsigned_release_object,
    content_addressed_r2_key,
    selector_sha256,
    serialize_release_object,
    sign_release_object,
)


def _write_object(tmp_path: Path) -> tuple[Path, str, Path]:
    artifact = tmp_path / "data" / "corpus" / "provisions" / "nz" / "statute" / "v1.jsonl"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"body":"text"}\n')
    inventory = tmp_path / "data" / "corpus" / "inventory" / "nz" / "statute" / "v1.json"
    coverage = tmp_path / "data" / "corpus" / "coverage" / "nz" / "statute" / "v1.json"
    source = tmp_path / "data" / "corpus" / "sources" / "nz" / "statute" / "v1" / "act.html"
    for path, body in ((inventory, "{}\n"), (coverage, "{}\n"), (source, "official")):
        path.parent.mkdir(parents=True)
        path.write_text(body)
    release = ReleaseManifest(
        name="nz-rulespec-v1",
        scopes=(ReleaseScope("nz", "statute", "v1"),),
    )
    artifact_paths = {
        "inventory": inventory,
        "provisions": artifact,
        "coverage": coverage,
        "sources": source,
    }
    entries = []
    for artifact_class, local_path in artifact_paths.items():
        digest = hashlib.sha256(local_path.read_bytes()).hexdigest()
        entry = {
            "artifact_class": artifact_class,
            "path": local_path.relative_to(tmp_path).as_posix(),
            "sha256": digest,
            "bytes": local_path.stat().st_size,
            "r2_bucket": "axiom-corpus",
            "r2_key": content_addressed_r2_key(digest),
        }
        if artifact_class == "provisions":
            entry["rows"] = 1
        entries.append(entry)
    entries.sort(key=lambda entry: entry["path"])
    content = {
        "release": "nz-rulespec-v1",
        "created_at": "2026-07-10T00:00:00Z",
        "selector_sha256": selector_sha256(release),
        "corpus_base": "data/corpus",
        "git": {},
        "r2": {"bucket": "axiom-corpus", "addressing": "sha256"},
        "scopes": [
            {
                "jurisdiction": "nz",
                "document_class": "statute",
                "version": "v1",
                "provision_rows": 1,
                "navigation_rows": 1,
            }
        ],
        "artifacts": entries,
        "validation": {},
    }
    content["validation"] = {
        "passed": True,
        "deep_validation": {"error_count": 0, "warning_count": 0, "scope_count": 1},
        "r2_readback": {
            "bucket": "axiom-corpus",
            "artifact_count": len(entries),
            "artifact_bytes": sum(entry["bytes"] for entry in entries),
            "verified_keys": [entry["r2_key"] for entry in entries],
        },
        "supabase_counts": [
            {
                "jurisdiction": "nz",
                "document_class": "statute",
                "version": "v1",
                "expected": 1,
                "actual": 1,
                "expected_navigation": 1,
                "actual_navigation": 1,
            }
        ],
    }
    private = Ed25519PrivateKey.generate()
    private_text = b64encode(
        private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
    ).decode()
    public_text = b64encode(
        private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode()
    signed = sign_release_object(build_unsigned_release_object(content), private_key=private_text)
    path = tmp_path / "release.json"
    path.write_bytes(serialize_release_object(signed))
    return path, public_text, artifact


def test_cli_requires_public_key(tmp_path: Path, monkeypatch, capsys) -> None:
    path, _, _ = _write_object(tmp_path)
    monkeypatch.delenv(RELEASE_OBJECT_PUBLIC_KEY_ENV, raising=False)
    assert cli.main([str(path)]) == 2
    assert RELEASE_OBJECT_PUBLIC_KEY_ENV in capsys.readouterr().err


def test_cli_verifies_signature(tmp_path: Path, monkeypatch, capsys) -> None:
    path, public_key, _ = _write_object(tmp_path)
    monkeypatch.setenv(RELEASE_OBJECT_PUBLIC_KEY_ENV, public_key)

    assert cli.main([str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["signature_verified"] is True
    assert report["release"] == "nz-rulespec-v1"


def test_cli_can_rehash_local_artifacts(tmp_path: Path, monkeypatch, capsys) -> None:
    path, public_key, artifact = _write_object(tmp_path)
    monkeypatch.setenv(RELEASE_OBJECT_PUBLIC_KEY_ENV, public_key)
    artifact.write_text("tampered")

    assert cli.main([str(path), "--repo-root", str(tmp_path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert any("sha256 mismatch" in issue for issue in report["issues"])


def test_cli_rejects_invalid_release_object(tmp_path: Path, monkeypatch, capsys) -> None:
    _, public_key, _ = _write_object(tmp_path)
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}")
    monkeypatch.setenv(RELEASE_OBJECT_PUBLIC_KEY_ENV, public_key)

    assert cli.main([str(invalid)]) == 1
    assert "unsupported schema version" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({}, "content is missing"),
        ({"content": {}}, "artifacts are missing"),
        ({"content": {"artifacts": [None]}}, "non-object artifact"),
        ({"content": {"artifacts": [{}]}}, "missing its path"),
        (
            {"content": {"artifacts": [{"path": "data/corpus/../../../outside"}]}},
            "escapes repository",
        ),
        (
            {"content": {"artifacts": [{"path": "data/corpus/missing.json"}]}},
            "artifact is missing",
        ),
    ],
)
def test_local_artifact_verifier_rejects_invalid_inventory(
    tmp_path: Path,
    payload: dict,
    expected: str,
) -> None:
    assert any(expected in issue for issue in _verify_local_artifacts(payload, tmp_path))


def test_local_artifact_verifier_reports_hash_and_size_mismatch(tmp_path: Path) -> None:
    artifact = tmp_path / "data" / "corpus" / "file.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("actual")
    payload = {
        "content": {
            "artifacts": [
                {
                    "path": "data/corpus/file.txt",
                    "sha256": "0" * 64,
                    "bytes": 999,
                }
            ]
        }
    }

    issues = _verify_local_artifacts(payload, tmp_path)
    assert any("sha256 mismatch" in issue for issue in issues)
    assert any("byte-count mismatch" in issue for issue in issues)
