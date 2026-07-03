"""Tests for corpus release-manifest build, determinism, and signing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axiom_corpus.release.manifest import (
    RELEASE_MANIFEST_SCHEMA_VERSION,
    RELEASE_MANIFEST_SIGNATURE_ALGORITHM,
    RELEASE_MANIFEST_SIGNATURE_KEY_ID,
    ReleaseManifestError,
    build_release_manifest,
    canonical_manifest_bytes,
    declared_r2_key,
    jsonl_row_count,
    manifest_signature_issue,
    serialize_manifest,
    sha256_file,
    sign_manifest,
    verify_manifest,
)

SIGNING_KEY = "test-release-signing-key-0123456789"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_corpus_repo(root: Path) -> Path:
    """Create a tiny, git-committed corpus tree for deterministic tests."""
    base = root / "data" / "corpus"
    (base / "provisions" / "us" / "statute").mkdir(parents=True)
    (base / "inventory" / "us" / "statute").mkdir(parents=True)
    (base / "coverage" / "us" / "statute").mkdir(parents=True)
    (base / "sources" / "us" / "statute").mkdir(parents=True)
    (base / "manifests" / "us").mkdir(parents=True)
    (root / "claims" / "us" / "guidance").mkdir(parents=True)

    # Two provision rows + a blank trailing line (must not count as a row).
    (base / "provisions" / "us" / "statute" / "a.jsonl").write_text(
        '{"id": "1", "body": "x"}\n{"id": "2", "body": "y"}\n'
    )
    (base / "provisions" / "us" / "statute" / "b.jsonl").write_text(
        '{"id": "3"}\n\n'
    )
    (base / "inventory" / "us" / "statute" / "a.json").write_text(
        '{"items": [1, 2]}\n'
    )
    (base / "coverage" / "us" / "statute" / "a.json").write_text(
        '{"complete": true}\n'
    )
    (base / "sources" / "us" / "statute" / "a.xml").write_text("<root/>\n")
    (base / "manifests" / "us" / "m.yaml").write_text("version: 1\n")
    (root / "claims" / "us" / "guidance" / "c.jsonl").write_text(
        '{"subject": {"id": "x"}}\n'
    )
    (root / "DATA_INVENTORY.md").write_text("# Inventory\n")

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "-A", "-f")
    _git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed")
    return root


@pytest.fixture()
def corpus_repo(tmp_path: Path) -> Path:
    return _make_corpus_repo(tmp_path / "repo")


# ---------------------------------------------------------------------------
# Hash / row-count primitives
# ---------------------------------------------------------------------------


def test_jsonl_row_count_ignores_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\n\n{"b": 2}\n')
    assert jsonl_row_count(path) == 2


def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    import hashlib

    path = tmp_path / "x.bin"
    path.write_bytes(b"hello world")
    assert sha256_file(path) == hashlib.sha256(b"hello world").hexdigest()


def test_declared_r2_key_strips_base_prefix() -> None:
    key = declared_r2_key(
        "data/corpus/provisions/us/statute/a.jsonl",
        base="data/corpus",
        bucket="axiom-corpus",
    )
    assert key == "r2://axiom-corpus/provisions/us/statute/a.jsonl"


# ---------------------------------------------------------------------------
# Manifest build
# ---------------------------------------------------------------------------


def test_build_manifest_records_all_classes_and_counts(corpus_repo: Path) -> None:
    manifest = build_release_manifest(corpus_repo, release="r0")

    assert manifest["schema_version"] == RELEASE_MANIFEST_SCHEMA_VERSION
    assert manifest["release"] == "r0"
    assert manifest["source_of_truth"] == "local-artifact-hashes"

    summary = manifest["summary"]
    # 2 provision files, 3 rows total (2 + 1; blank line excluded).
    assert summary["provisions"]["files"] == 2
    assert summary["provisions"]["rows"] == 3
    assert summary["inventory"]["files"] == 1
    assert summary["coverage"]["files"] == 1
    assert summary["sources"]["files"] == 1
    assert summary["manifests"]["files"] == 1
    assert summary["claims"]["files"] == 1
    assert summary["claims"]["rows"] == 1

    # totals aggregate every class.
    assert summary["totals"]["files"] == 2 + 1 + 1 + 1 + 1 + 1

    # DATA_INVENTORY.md lands in documents with a real hash.
    assert "DATA_INVENTORY.md" in manifest["documents"]
    inv = manifest["documents"]["DATA_INVENTORY.md"]
    assert inv["sha256"] == sha256_file(corpus_repo / "DATA_INVENTORY.md")

    # Provision entries carry declared R2 keys and rows.
    prov = manifest["artifacts"]["provisions"]
    a_entry = next(e for e in prov if e["path"].endswith("a.jsonl"))
    assert a_entry["rows"] == 2
    assert a_entry["r2_key"] == (
        "r2://axiom-corpus/provisions/us/statute/a.jsonl"
    )


def test_created_at_uses_git_commit_time(corpus_repo: Path) -> None:
    epoch = subprocess.run(
        ["git", "-C", str(corpus_repo), "show", "-s", "--format=%ct", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = build_release_manifest(corpus_repo, release="r0")
    # created_at is derived from the commit epoch, not the wall clock.
    from datetime import UTC, datetime

    expected = (
        datetime.fromtimestamp(int(epoch), tz=UTC).isoformat().replace("+00:00", "Z")
    )
    assert manifest["created_at"] == expected
    assert manifest["git"]["committed_at"] == expected
    assert manifest["git"]["commit"]


def test_created_at_required_without_git(tmp_path: Path) -> None:
    base = tmp_path / "data" / "corpus" / "provisions"
    base.mkdir(parents=True)
    (base / "x.jsonl").write_text('{"id": 1}\n')
    with pytest.raises(ReleaseManifestError, match="created_at is required"):
        build_release_manifest(tmp_path, release="r0")


def test_created_at_override_accepted_without_git(tmp_path: Path) -> None:
    base = tmp_path / "data" / "corpus" / "provisions"
    base.mkdir(parents=True)
    (base / "x.jsonl").write_text('{"id": 1}\n')
    manifest = build_release_manifest(
        tmp_path, release="r0", created_at="2026-07-03T00:00:00Z"
    )
    assert manifest["created_at"] == "2026-07-03T00:00:00Z"
    assert manifest["git"] == {}


def test_missing_corpus_base_raises(tmp_path: Path) -> None:
    with pytest.raises(ReleaseManifestError, match="corpus base directory not found"):
        build_release_manifest(tmp_path, release="r0")


# ---------------------------------------------------------------------------
# Determinism: same tree -> byte-identical canonical bytes
# ---------------------------------------------------------------------------


def test_manifest_emission_is_deterministic(corpus_repo: Path) -> None:
    first = build_release_manifest(corpus_repo, release="r0")
    second = build_release_manifest(corpus_repo, release="r0")
    assert canonical_manifest_bytes(first) == canonical_manifest_bytes(second)
    assert serialize_manifest(first) == serialize_manifest(second)


def test_signed_manifest_is_deterministic(corpus_repo: Path) -> None:
    first = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    second = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    assert serialize_manifest(first) == serialize_manifest(second)
    assert first["signature"]["value"] == second["signature"]["value"]


def test_content_change_changes_manifest(corpus_repo: Path) -> None:
    before = canonical_manifest_bytes(
        build_release_manifest(corpus_repo, release="r0")
    )
    # Append a provision row.
    prov = corpus_repo / "data" / "corpus" / "provisions" / "us" / "statute" / "a.jsonl"
    prov.write_text(prov.read_text() + '{"id": "99"}\n')
    after = canonical_manifest_bytes(
        build_release_manifest(corpus_repo, release="r0")
    )
    assert before != after


# ---------------------------------------------------------------------------
# Signing + verification (mirrors axiom-encode apply manifests)
# ---------------------------------------------------------------------------


def test_sign_and_verify_roundtrip(corpus_repo: Path) -> None:
    manifest = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    assert manifest["signature"]["algorithm"] == RELEASE_MANIFEST_SIGNATURE_ALGORITHM
    assert manifest["signature"]["key_id"] == RELEASE_MANIFEST_SIGNATURE_KEY_ID
    # Should not raise.
    verify_manifest(manifest, SIGNING_KEY)
    assert manifest_signature_issue(manifest, SIGNING_KEY) is None


def test_signature_excludes_signature_field(corpus_repo: Path) -> None:
    manifest = build_release_manifest(corpus_repo, release="r0")
    unsigned_bytes = canonical_manifest_bytes(manifest)
    signed = sign_manifest(manifest, SIGNING_KEY)
    # Canonical bytes are identical before and after signing (signature dropped).
    assert canonical_manifest_bytes(signed) == unsigned_bytes


def test_tampered_payload_fails_verification(corpus_repo: Path) -> None:
    manifest = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    # Tamper with a recorded hash after signing.
    manifest["artifacts"]["provisions"][0]["sha256"] = "0" * 64
    assert manifest_signature_issue(manifest, SIGNING_KEY) == (
        "has an invalid release manifest signature"
    )
    with pytest.raises(ReleaseManifestError, match="invalid release manifest signature"):
        verify_manifest(manifest, SIGNING_KEY)


def test_wrong_key_fails_verification(corpus_repo: Path) -> None:
    manifest = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    assert manifest_signature_issue(manifest, "a-different-key") == (
        "has an invalid release manifest signature"
    )


def test_missing_signature_reported(corpus_repo: Path) -> None:
    manifest = build_release_manifest(corpus_repo, release="r0")
    assert manifest_signature_issue(manifest, SIGNING_KEY) == (
        "is missing a release manifest signature"
    )


def test_unknown_algorithm_reported(corpus_repo: Path) -> None:
    manifest = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    manifest["signature"]["algorithm"] = "rot13"
    assert manifest_signature_issue(manifest, SIGNING_KEY) == (
        "uses an unsupported release manifest signature algorithm"
    )


def test_unknown_key_id_reported(corpus_repo: Path) -> None:
    manifest = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    manifest["signature"]["key_id"] = "someone-elses-key"
    assert manifest_signature_issue(manifest, SIGNING_KEY) == (
        "uses an unknown release manifest signing key"
    )


def test_canonical_bytes_match_axiom_encode_convention(corpus_repo: Path) -> None:
    """Canonical form is sorted-keys, tight separators, ascii, signature-free."""
    manifest = sign_manifest(
        build_release_manifest(corpus_repo, release="r0"), SIGNING_KEY
    )
    unsigned = {k: v for k, v in manifest.items() if k != "signature"}
    expected = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    assert canonical_manifest_bytes(manifest) == expected
