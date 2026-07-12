"""Tests for immutable Ed25519 corpus release objects."""

from __future__ import annotations

import copy
import json
import subprocess
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_SCHEMA_VERSION,
    ReleaseManifestError,
    _git_provenance,
    _validate_scope_artifact_membership,
    _validate_validation_attestation,
    build_release_content,
    build_unsigned_release_object,
    content_addressed_r2_key,
    load_release_object,
    release_object_r2_key,
    serialize_release_object,
    sign_release_object,
    verify_release_object,
)


def _keys() -> tuple[str, str]:
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
    return private_text, public_text


def _release_tree(
    tmp_path: Path, *, name: str = "nz-rulespec-2026-07-10"
) -> tuple[Path, ReleaseManifest]:
    root = tmp_path / "repo"
    store = CorpusArtifactStore(root / "data" / "corpus")
    version = "2026-07-10-nz-rulespec"
    source = store.source_path("nz", "statute", version, "act.html")
    source_sha = store.write_text(source, "<p>Official text.</p>")
    source_rel = source.relative_to(store.root).as_posix()
    store.write_inventory(
        store.inventory_path("nz", "statute", version),
        [
            SourceInventoryItem(
                citation_path="nz/statute/act/1",
                source_path=source_rel,
                sha256=source_sha,
            )
        ],
    )
    store.write_provisions(
        store.provisions_path("nz", "statute", version),
        [
            ProvisionRecord(
                jurisdiction="nz",
                document_class="statute",
                citation_path="nz/statute/act/1",
                version=version,
                body="Official text.",
                source_path=source_rel,
            )
        ],
    )
    store.write_json(
        store.coverage_path("nz", "statute", version),
        {
            "complete": True,
            "source_count": 1,
            "provision_count": 1,
            "matched_count": 1,
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )
    release = ReleaseManifest(
        name=name,
        scopes=(ReleaseScope("nz", "statute", version),),
    )
    selector = root / "manifests" / "releases" / f"{name}.json"
    selector.parent.mkdir(parents=True)
    selector.write_text(
        json.dumps(
            {
                "name": name,
                "scopes": [
                    {
                        "jurisdiction": "nz",
                        "document_class": "statute",
                        "version": version,
                    }
                ],
            }
        )
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    return root, release


def _signed(tmp_path: Path) -> tuple[dict, str]:
    content = _valid_content(tmp_path)
    private, public = _keys()
    return sign_release_object(build_unsigned_release_object(content), private_key=private), public


def _valid_content(tmp_path: Path) -> dict:
    root, release = _release_tree(tmp_path)
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )
    content["validation"] = _validation_for(content)
    return content


def _validation_for(content: dict) -> dict:
    return {
        "passed": True,
        "deep_validation": {
            "error_count": 0,
            "warning_count": 0,
            "scope_count": len(content["scopes"]),
        },
        "r2_readback": {
            "bucket": "axiom-corpus",
            "artifact_count": len(content["artifacts"]),
            "artifact_bytes": sum(entry["bytes"] for entry in content["artifacts"]),
            "verified_keys": [entry["r2_key"] for entry in content["artifacts"]],
        },
        "supabase_projection_evidence": [
            {
                "jurisdiction": scope["jurisdiction"],
                "document_class": scope["document_class"],
                "version": scope["version"],
                "expected": scope["provision_rows"],
                "actual": scope["provision_rows"],
                "expected_navigation": scope["navigation_rows"],
                "actual_navigation": scope["navigation_rows"],
                "expected_provision_projection_sha256": scope["provision_projection_sha256"],
                "actual_provision_projection_sha256": scope["provision_projection_sha256"],
                "expected_navigation_projection_sha256": scope["navigation_projection_sha256"],
                "actual_navigation_projection_sha256": scope["navigation_projection_sha256"],
            }
            for scope in content["scopes"]
        ],
    }


def test_release_object_is_scope_specific_and_content_addressed(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )

    assert content["release"] == release.name
    assert content["scopes"] == [
        {
            "jurisdiction": "nz",
            "document_class": "statute",
            "version": "2026-07-10-nz-rulespec",
            "provision_rows": 1,
            "navigation_rows": 1,
            "provision_projection_sha256": content["scopes"][0]["provision_projection_sha256"],
            "navigation_projection_sha256": content["scopes"][0]["navigation_projection_sha256"],
        }
    ]
    assert {entry["artifact_class"] for entry in content["artifacts"]} == {
        "inventory",
        "provisions",
        "coverage",
        "sources",
    }
    for entry in content["artifacts"]:
        assert entry["r2_key"] == content_addressed_r2_key(entry["sha256"])


def test_release_object_verifies_with_public_key(tmp_path: Path) -> None:
    signed, public = _signed(tmp_path)

    verify_release_object(signed, public_key=public)
    assert signed["schema_version"] == RELEASE_OBJECT_SCHEMA_VERSION
    assert signed["signature"]["algorithm"] == "ed25519"
    assert release_object_r2_key(signed["release"], signed["content_sha256"]).endswith(
        f"/{signed['content_sha256']}.json"
    )
    assert serialize_release_object(signed).endswith(b"\n")


def test_release_object_rejects_content_tamper(tmp_path: Path) -> None:
    signed, public = _signed(tmp_path)
    tampered = copy.deepcopy(signed)
    tampered["content"]["scopes"][0]["provision_rows"] = 2

    with pytest.raises(ReleaseManifestError, match="content sha256"):
        verify_release_object(tampered, public_key=public)


def test_release_object_rejects_signature_tamper(tmp_path: Path) -> None:
    signed, public = _signed(tmp_path)
    tampered = copy.deepcopy(signed)
    tampered["signature"]["value"] = b64encode(b"x" * 64).decode()

    with pytest.raises(ReleaseManifestError, match="signature is invalid"):
        verify_release_object(tampered, public_key=public)


def test_release_object_rejects_signature_schema_extensions(tmp_path: Path) -> None:
    signed, public = _signed(tmp_path)
    signed["signature"]["legacy_digest"] = "not-part-of-v2"

    with pytest.raises(ReleaseManifestError, match="signature does not match the v2 schema"):
        verify_release_object(signed, public_key=public)


def test_release_object_rejects_wrong_public_key(tmp_path: Path) -> None:
    signed, _ = _signed(tmp_path)
    _, wrong_public = _keys()

    with pytest.raises(ReleaseManifestError, match="signature is invalid"):
        verify_release_object(signed, public_key=wrong_public)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing", "missing its signature"),
        ("algorithm", "unsupported signature algorithm"),
        ("key_id", "unknown signing key"),
        ("value_type", "signature value is missing"),
        ("encoding", "signature encoding is invalid"),
    ],
)
def test_release_object_rejects_invalid_signature_fields(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    signed, public = _signed(tmp_path)
    if case == "missing":
        signed.pop("signature")
    elif case == "algorithm":
        signed["signature"]["algorithm"] = "hmac-sha256"
    elif case == "key_id":
        signed["signature"]["key_id"] = "unknown"
    elif case == "value_type":
        signed["signature"]["value"] = None
    else:
        signed["signature"]["value"] = "not base64!"

    with pytest.raises(ReleaseManifestError, match=message):
        verify_release_object(signed, public_key=public)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("top_extra", "unsupported top-level fields"),
        ("schema", "unsupported schema version"),
        ("release_type", "missing its release name"),
        ("content_type", "content must be a JSON object"),
        ("content_fields", "content does not match the v2 schema"),
        ("release_mismatch", "name does not match its content"),
        ("created_at", "invalid creation time"),
        ("git", "invalid git provenance"),
        ("digest", "content sha256 does not match"),
        ("validation", "does not attest passed validation"),
        ("scopes_empty", "at least one scope"),
        ("artifacts_empty", "artifact entries"),
        ("selector_type", "invalid selector sha256"),
        ("corpus_base", "non-canonical corpus base"),
        ("r2", "invalid R2 content boundary"),
        ("scope_object", "non-object scope"),
        ("scope_fields", "scope does not match the v2 schema"),
        ("scope_doc_class", "invalid document class"),
        ("scope_duplicate", "duplicate scope"),
        ("scope_rows", "invalid provision_rows"),
        ("scope_navigation", "inconsistent navigation_rows"),
        ("artifact_object", "non-object artifact"),
        ("artifact_class", "unsupported class"),
        ("artifact_path", "path is not canonical"),
        ("artifact_class_path", "class does not match its path"),
        ("artifact_duplicate", "duplicate artifact"),
        ("artifact_sha", "invalid sha256"),
        ("artifact_key", "non-content-addressed R2 key"),
        ("artifact_bytes", "invalid byte count"),
        ("artifact_bucket", "wrong R2 bucket"),
        ("artifact_rows", "invalid row count"),
        ("artifact_order", "not in canonical path order"),
        ("scope_row_mismatch", "row count does not match"),
        ("artifact_extra", "outside its declared scopes"),
        ("validation_schema", "validation does not match the v2 schema"),
        ("deep_type", "lacks deep-validation evidence"),
        ("deep_mismatch", "deep-validation evidence is inconsistent"),
        ("readback_type", "lacks R2 readback evidence"),
        ("readback_schema", "R2 readback does not match the v2 schema"),
        ("readback_mismatch", "R2 readback evidence is inconsistent"),
        ("counts_incomplete", "staged-count evidence is incomplete"),
        ("count_object", "invalid staged-count evidence"),
        ("count_schema", "staged-count evidence does not match the v2 schema"),
        ("count_type", "non-integer staged-count evidence"),
        ("count_identity", "invalid staged-count identity"),
        ("count_mismatch", "staged-count evidence does not match scope"),
    ],
)
def test_release_object_rejects_malformed_v2_variants(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    content = _valid_content(tmp_path)
    payload = build_unsigned_release_object(content)

    if case == "top_extra":
        payload["legacy"] = {}
    elif case == "schema":
        payload["schema_version"] = "axiom-corpus/release-object/v1"
    elif case == "release_type":
        payload["release"] = None
    elif case == "content_type":
        payload["content"] = []
    elif case == "content_fields":
        payload["content"].pop("git")
    elif case == "release_mismatch":
        payload["content"]["release"] = "other-release"
    elif case == "created_at":
        payload["content"]["created_at"] = ""
    elif case == "git":
        payload["content"]["git"] = {"commit": "a" * 40}
    elif case == "digest":
        payload["content_sha256"] = "0" * 64
    elif case == "validation":
        payload["content"]["validation"]["passed"] = False
    elif case == "scopes_empty":
        payload["content"]["scopes"] = []
    elif case == "artifacts_empty":
        payload["content"]["artifacts"] = []
    elif case == "selector_type":
        payload["content"]["selector_sha256"] = None
    elif case == "corpus_base":
        payload["content"]["corpus_base"] = "corpus"
    elif case == "r2":
        payload["content"]["r2"] = {"bucket": "axiom-corpus", "addressing": "mutable"}
    elif case == "scope_object":
        payload["content"]["scopes"] = [None]
    elif case == "scope_fields":
        payload["content"]["scopes"][0].pop("navigation_rows")
    elif case == "scope_doc_class":
        payload["content"]["scopes"][0]["document_class"] = "unknown-class"
    elif case == "scope_duplicate":
        payload["content"]["scopes"].append(copy.deepcopy(payload["content"]["scopes"][0]))
    elif case == "scope_rows":
        payload["content"]["scopes"][0]["provision_rows"] = True
    elif case == "scope_navigation":
        payload["content"]["scopes"][0]["navigation_rows"] = 2
    elif case == "artifact_object":
        payload["content"]["artifacts"][0] = None
    elif case == "artifact_class":
        payload["content"]["artifacts"][0]["artifact_class"] = "legacy"
    elif case == "artifact_path":
        payload["content"]["artifacts"][0]["path"] = "/tmp/artifact"
    elif case == "artifact_class_path":
        payload["content"]["artifacts"][0]["artifact_class"] = "inventory"
    elif case == "artifact_duplicate":
        payload["content"]["artifacts"].append(copy.deepcopy(payload["content"]["artifacts"][0]))
    elif case == "artifact_sha":
        payload["content"]["artifacts"][0]["sha256"] = "bad"
    elif case == "artifact_key":
        payload["content"]["artifacts"][0]["r2_key"] = "mutable/latest"
    elif case == "artifact_bytes":
        payload["content"]["artifacts"][0]["bytes"] = True
    elif case == "artifact_bucket":
        payload["content"]["artifacts"][0]["r2_bucket"] = "other"
    elif case == "artifact_rows":
        provision = next(
            entry
            for entry in payload["content"]["artifacts"]
            if entry["artifact_class"] == "provisions"
        )
        provision["rows"] = 0
    elif case == "artifact_order":
        payload["content"]["artifacts"].reverse()
    elif case == "scope_row_mismatch":
        payload["content"]["scopes"][0]["provision_rows"] = 2
        payload["content"]["scopes"][0]["navigation_rows"] = 2
    elif case == "artifact_extra":
        extra = copy.deepcopy(
            next(
                entry
                for entry in payload["content"]["artifacts"]
                if entry["artifact_class"] == "sources"
            )
        )
        extra["path"] = "data/corpus/sources/nz/statute/unselected/extra.html"
        payload["content"]["artifacts"].append(extra)
        payload["content"]["artifacts"].sort(key=lambda entry: entry["path"])
    elif case == "validation_schema":
        payload["content"]["validation"]["legacy"] = True
    elif case == "deep_type":
        payload["content"]["validation"]["deep_validation"] = None
    elif case == "deep_mismatch":
        payload["content"]["validation"]["deep_validation"]["error_count"] = 1
    elif case == "readback_type":
        payload["content"]["validation"]["r2_readback"] = None
    elif case == "readback_schema":
        payload["content"]["validation"]["r2_readback"].pop("artifact_bytes")
    elif case == "readback_mismatch":
        payload["content"]["validation"]["r2_readback"]["artifact_count"] = 0
    elif case == "counts_incomplete":
        payload["content"]["validation"]["supabase_projection_evidence"] = []
    elif case == "count_object":
        payload["content"]["validation"]["supabase_projection_evidence"] = [None]
    elif case == "count_schema":
        payload["content"]["validation"]["supabase_projection_evidence"][0].pop("actual")
    elif case == "count_type":
        payload["content"]["validation"]["supabase_projection_evidence"][0]["actual"] = True
    elif case == "count_identity":
        payload["content"]["validation"]["supabase_projection_evidence"][0]["jurisdiction"] = ""
    else:
        payload["content"]["validation"]["supabase_projection_evidence"][0]["actual"] = 2

    # Every case intentionally changes content after the original unsigned
    # object was built. Re-address it so the test reaches the targeted schema
    # invariant instead of stopping at the outer digest check.
    if case not in {"top_extra", "schema", "release_type", "content_type", "digest"}:
        payload["content_sha256"] = build_unsigned_release_object(payload["content"])[
            "content_sha256"
        ]
    private, _ = _keys()
    with pytest.raises(ReleaseManifestError, match=message):
        sign_release_object(payload, private_key=private)


def test_release_object_loader_rejects_unreadable_and_non_object_json(tmp_path: Path) -> None:
    _, public = _keys()
    with pytest.raises(ReleaseManifestError, match="cannot read release object"):
        load_release_object(tmp_path / "missing.json", public_key=public)

    path = tmp_path / "release.json"
    path.write_text("[]")
    with pytest.raises(ReleaseManifestError, match="must be a JSON object"):
        load_release_object(path, public_key=public)


def test_release_object_rejects_invalid_key_encodings(tmp_path: Path) -> None:
    content = _valid_content(tmp_path)
    payload = build_unsigned_release_object(content)
    with pytest.raises(ReleaseManifestError, match="private key must be raw base64 or PEM"):
        sign_release_object(payload, private_key="not base64!")

    signed, _ = _signed(tmp_path / "second")
    with pytest.raises(ReleaseManifestError, match="public key must decode to 32 bytes"):
        verify_release_object(signed, public_key=b64encode(b"short").decode())


def test_release_object_supports_ed25519_pem_and_rejects_other_pem_keys(tmp_path: Path) -> None:
    content = _valid_content(tmp_path)
    payload = build_unsigned_release_object(content)
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    signed = sign_release_object(payload, private_key=private_pem)
    verify_release_object(signed, public_key=public_pem)

    with pytest.raises(ReleaseManifestError, match="private key PEM is invalid"):
        sign_release_object(payload, private_key="-----BEGIN PRIVATE KEY-----\ninvalid")
    with pytest.raises(ReleaseManifestError, match="public key PEM is invalid"):
        verify_release_object(signed, public_key="-----BEGIN PUBLIC KEY-----\ninvalid")

    rsa_private = generate_private_key(public_exponent=65537, key_size=2048)
    rsa_private_pem = rsa_private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    rsa_public_pem = (
        rsa_private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    with pytest.raises(ReleaseManifestError, match="private key must be Ed25519"):
        sign_release_object(payload, private_key=rsa_private_pem)
    with pytest.raises(ReleaseManifestError, match="public key must be Ed25519"):
        verify_release_object(signed, public_key=rsa_public_pem)


def test_git_provenance_uses_head_commit_time(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    marker = repo / "marker"
    marker.write_text("tracked")
    subprocess.run(["git", "-C", str(repo), "add", "marker"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-qm", "seed"],
        check=True,
    )

    provenance = _git_provenance(repo)
    assert provenance is not None
    assert len(provenance["commit"]) == 40
    assert provenance["committed_at"].endswith("Z")


def test_git_provenance_rejects_dirty_checkout(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    marker = repo / "marker"
    marker.write_text("tracked")
    subprocess.run(["git", "-C", str(repo), "add", "marker"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-qm", "seed"],
        check=True,
    )
    marker.write_text("dirty")

    with pytest.raises(ReleaseManifestError, match="clean git checkout"):
        _git_provenance(repo)


def test_git_provenance_rejects_empty_git_output(tmp_path: Path, monkeypatch) -> None:
    import axiom_corpus.release.manifest as manifest

    class EmptyResult:
        stdout = ""

    monkeypatch.setattr(manifest.subprocess, "run", lambda *args, **kwargs: EmptyResult())
    assert _git_provenance(tmp_path) is None


def test_defensive_nested_validators_reject_non_object_scope() -> None:
    with pytest.raises(ReleaseManifestError, match="non-object scope"):
        _validate_scope_artifact_membership([None], [])

    validation = {
        "passed": True,
        "deep_validation": {"error_count": 0, "warning_count": 0, "scope_count": 1},
        "r2_readback": {
            "bucket": "axiom-corpus",
            "artifact_count": 0,
            "artifact_bytes": 0,
            "verified_keys": [],
        },
        "supabase_projection_evidence": [
            {
                "jurisdiction": "nz",
                "document_class": "statute",
                "version": "v1",
                "expected": 1,
                "actual": 1,
                "expected_navigation": 1,
                "actual_navigation": 1,
                "expected_provision_projection_sha256": "a" * 64,
                "actual_provision_projection_sha256": "a" * 64,
                "expected_navigation_projection_sha256": "b" * 64,
                "actual_navigation_projection_sha256": "b" * 64,
            }
        ],
    }
    with pytest.raises(ReleaseManifestError, match="non-object scope"):
        _validate_validation_attestation(
            validation,
            scopes=[None],
            artifacts=[],
            bucket="axiom-corpus",
        )


def test_release_content_cannot_be_signed_before_validation(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    with pytest.raises(ReleaseManifestError, match="validation must have passed"):
        build_release_content(
            root,
            release=release,
            validation={"passed": False},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_rejects_invalid_build_boundaries(tmp_path: Path, monkeypatch) -> None:
    root, release = _release_tree(tmp_path)

    with pytest.raises(ReleaseManifestError, match="at least one scope"):
        build_release_content(
            root,
            release=ReleaseManifest(name="empty-release", scopes=()),
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )
    with pytest.raises(ReleaseManifestError, match="corpus_base data/corpus"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            base="corpus",
            created_at="2026-07-10T00:00:00Z",
        )
    with pytest.raises(ReleaseManifestError, match="base directory not found"):
        build_release_content(
            tmp_path / "missing-repo",
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )

    provisions = root / "data/corpus/provisions/nz/statute/2026-07-10-nz-rulespec.jsonl"
    original_provisions = provisions.read_text()
    provisions.write_text("")
    with pytest.raises(ReleaseManifestError, match="must contain at least one row"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )

    # Every production build requires real git provenance; an explicit
    # timestamp cannot substitute for checkout identity.
    provisions.write_text(original_provisions)
    monkeypatch.setattr("axiom_corpus.release.manifest._git_provenance", lambda path: None)
    with pytest.raises(ReleaseManifestError, match="git checkout identity"):
        build_release_content(root, release=release, validation={"passed": True})
    with pytest.raises(ReleaseManifestError, match="git checkout identity"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )
    monkeypatch.setattr(
        "axiom_corpus.release.manifest._git_provenance",
        lambda path: {"commit": "a" * 40, "committed_at": "2026-07-10T00:00:00Z"},
    )
    assert (
        build_release_content(root, release=release, validation={"passed": True})["created_at"]
        == "2026-07-10T00:00:00Z"
    )


def test_release_content_rejects_escaping_corpus_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "data" / "corpus").symlink_to(outside, target_is_directory=True)
    release = ReleaseManifest(
        name="nz-v1",
        scopes=(ReleaseScope("nz", "statute", "v1"),),
    )

    with pytest.raises(ReleaseManifestError, match="corpus base escapes repository"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_rejects_in_repository_corpus_symlink(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    corpus = root / "data" / "corpus"
    relocated = root / "relocated-corpus"
    corpus.rename(relocated)
    corpus.symlink_to(relocated, target_is_directory=True)

    with pytest.raises(ReleaseManifestError, match="path contains a symlink"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_rejects_symlinked_source_file(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    source = root / "data/corpus/sources/nz/statute/2026-07-10-nz-rulespec/act.html"
    source.unlink()
    source.symlink_to(root / ".git" / "config")

    with pytest.raises(ReleaseManifestError, match="path contains a symlink"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_requires_complete_canonical_source_references(
    tmp_path: Path,
) -> None:
    root, release = _release_tree(tmp_path)
    provisions = root / "data/corpus/provisions/nz/statute/2026-07-10-nz-rulespec.jsonl"
    record = json.loads(provisions.read_text())
    record.pop("source_path")
    provisions.write_text(json.dumps(record) + "\n")

    with pytest.raises(ReleaseManifestError, match="must have a non-empty source_path"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_rejects_uninventoried_provision_source(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    store = CorpusArtifactStore(root / "data" / "corpus")
    version = "2026-07-10-nz-rulespec"
    unlisted = store.source_path("nz", "statute", version, "unlisted.html")
    store.write_text(unlisted, "<p>Uninventoried source.</p>")
    provisions = store.provisions_path("nz", "statute", version)
    record = json.loads(provisions.read_text())
    record["source_path"] = unlisted.relative_to(store.root).as_posix()
    provisions.write_text(json.dumps(record) + "\n")

    with pytest.raises(ReleaseManifestError, match="absent from scope inventory"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_rejects_inventory_source_digest_mismatch(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    inventory = root / "data/corpus/inventory/nz/statute/2026-07-10-nz-rulespec.json"
    payload = json.loads(inventory.read_text())
    payload["items"][0]["sha256"] = "a" * 64
    inventory.write_text(json.dumps(payload))

    with pytest.raises(ReleaseManifestError, match="does not match signed artifact"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_rejects_missing_scope_artifact(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    source = root / "data/corpus/sources/nz/statute/2026-07-10-nz-rulespec/act.html"
    source.unlink()

    with pytest.raises(ReleaseManifestError, match="missing sources artifact"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_rejects_ignored_untracked_source_artifact(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    source = root / "data/corpus/sources/nz/statute/2026-07-10-nz-rulespec/act.html"
    relative = source.relative_to(root).as_posix()
    subprocess.run(["git", "-C", str(root), "rm", "--cached", relative], check=True)
    (root / ".gitignore").write_text(f"/{relative}\n")
    subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "ignore source",
        ],
        check=True,
    )

    with pytest.raises(ReleaseManifestError, match="inputs must be tracked"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_content_requires_exactly_one_provisions_entry(tmp_path: Path, monkeypatch) -> None:
    root, release = _release_tree(tmp_path)
    import axiom_corpus.release.manifest as manifest

    monkeypatch.setattr(manifest, "_scope_artifact_entries", lambda *args, **kwargs: [])
    with pytest.raises(ReleaseManifestError, match="exactly one provisions artifact"):
        build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-07-10T00:00:00Z",
        )


def test_release_key_helpers_and_unsigned_builder_reject_missing_identity() -> None:
    with pytest.raises(ReleaseManifestError, match="invalid artifact sha256"):
        content_addressed_r2_key("bad")
    with pytest.raises(ReleaseManifestError, match="invalid release content sha256"):
        release_object_r2_key("nz-v1", "bad")
    with pytest.raises(ReleaseManifestError, match="reserved"):
        release_object_r2_key("current", "a" * 64)
    with pytest.raises(ReleaseManifestError, match="missing its release name"):
        build_unsigned_release_object({})


def test_signature_requires_complete_validation_evidence(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )
    private, _ = _keys()

    with pytest.raises(ReleaseManifestError, match="validation does not match the v2 schema"):
        sign_release_object(build_unsigned_release_object(content), private_key=private)


def test_signature_rejects_artifacts_outside_complete_declared_scope(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )
    content["artifacts"] = [
        entry for entry in content["artifacts"] if entry["artifact_class"] != "sources"
    ]
    content["validation"] = _validation_for(content)
    private, _ = _keys()

    with pytest.raises(ReleaseManifestError, match="lacks source artifacts"):
        sign_release_object(build_unsigned_release_object(content), private_key=private)


def test_signature_rejects_missing_required_inventory_artifact(tmp_path: Path) -> None:
    content = _valid_content(tmp_path)
    content["artifacts"] = [
        entry for entry in content["artifacts"] if entry["artifact_class"] != "inventory"
    ]
    content["validation"] = _validation_for(content)
    private, _ = _keys()

    with pytest.raises(ReleaseManifestError, match="lacks its inventory artifact"):
        sign_release_object(build_unsigned_release_object(content), private_key=private)


def test_signature_rejects_rows_on_non_provision_artifacts(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )
    non_provision = next(
        entry for entry in content["artifacts"] if entry["artifact_class"] != "provisions"
    )
    non_provision["rows"] = 1
    content["validation"] = _validation_for(content)
    private, _ = _keys()

    with pytest.raises(ReleaseManifestError, match="artifact does not match the v2 schema"):
        sign_release_object(build_unsigned_release_object(content), private_key=private)


def test_signature_rejects_selector_digest_unlinked_from_scopes(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )
    content["selector_sha256"] = "a" * 64
    content["validation"] = _validation_for(content)
    private, _ = _keys()

    with pytest.raises(ReleaseManifestError, match="selector sha256"):
        sign_release_object(build_unsigned_release_object(content), private_key=private)


def test_signature_rejects_noncanonical_scope_identity(tmp_path: Path) -> None:
    root, release = _release_tree(tmp_path)
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )
    content["scopes"][0]["jurisdiction"] = "../nz"
    content["validation"] = _validation_for(content)
    private, _ = _keys()

    with pytest.raises(ReleaseManifestError, match="invalid identity field"):
        sign_release_object(build_unsigned_release_object(content), private_key=private)


@pytest.mark.parametrize(
    "path",
    [
        "data/corpus/sources/nz/statute/v1/../escape.html",
        "data/corpus/sources/nz/statute/v1\\escape.html",
        "data/corpus/sources/nz//statute/v1/escape.html",
    ],
)
def test_signature_rejects_noncanonical_artifact_paths(tmp_path: Path, path: str) -> None:
    content = _valid_content(tmp_path)
    content["artifacts"][-1]["path"] = path
    content["artifacts"].sort(key=lambda entry: entry["path"])
    content["validation"] = _validation_for(content)
    private, _ = _keys()

    with pytest.raises(ReleaseManifestError, match="path is not canonical"):
        sign_release_object(build_unsigned_release_object(content), private_key=private)


def test_mutable_current_release_name_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reserved"):
        _release_tree(tmp_path, name="current")


def test_release_serialization_is_valid_json(tmp_path: Path) -> None:
    signed, _ = _signed(tmp_path)
    assert json.loads(serialize_release_object(signed)) == signed


def test_jsonl_source_artifacts_sign_without_rows(tmp_path: Path) -> None:
    """Sources may be .jsonl (promotion input slices); rows stays provisions-only."""
    root, release = _release_tree(tmp_path)
    inputs_dir = (
        root
        / "data"
        / "corpus"
        / "sources"
        / "nz"
        / "statute"
        / "2026-07-10-nz-rulespec"
        / "inputs"
    )
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "slice.selected.jsonl").write_text('{"body": "Official text."}\n')
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", "commit", "-qm", "jsonl source"],
        check=True,
    )
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-07-10T00:00:00Z",
    )
    content["validation"] = _validation_for(content)
    private, _public = _keys()
    signed = sign_release_object(build_unsigned_release_object(content), private_key=private)
    by_class: dict[str, list[dict]] = {}
    for entry in signed["content"]["artifacts"]:
        by_class.setdefault(entry["artifact_class"], []).append(entry)
    jsonl_sources = [
        entry for entry in by_class["sources"] if entry["path"].endswith(".jsonl")
    ]
    assert jsonl_sources, "fixture must include a .jsonl source artifact"
    assert all("rows" not in entry for entry in jsonl_sources)
    assert all("rows" in entry for entry in by_class["provisions"])
