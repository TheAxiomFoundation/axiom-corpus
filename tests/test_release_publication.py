from __future__ import annotations

import hashlib
from base64 import b64encode
from io import BytesIO
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.r2 import R2Config
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.release.manifest import (
    ReleaseManifestError,
    build_unsigned_release_object,
    content_addressed_r2_key,
    selector_sha256,
    sign_release_object,
)
from axiom_corpus.release.publication import (
    _read_object_or_none,
    _verify_bytes,
    stage_release_artifacts,
    stage_signed_release_object,
)


class FakeR2:
    def __init__(self, objects: dict[str, bytes] | None = None):
        self.objects = dict(objects or {})
        self.uploads: list[str] = []

    def get_object(self, **kwargs):
        assert kwargs["Bucket"] == "axiom-corpus"
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}

    def upload_file(self, filename, bucket, key, **kwargs):
        assert bucket == "axiom-corpus"
        self.objects[key] = Path(filename).read_bytes()
        self.uploads.append(key)

    def put_object(self, **kwargs):
        assert kwargs["Bucket"] == "axiom-corpus"
        self.objects[kwargs["Key"]] = bytes(kwargs["Body"])


def _config() -> R2Config:
    return R2Config("axiom-corpus", "https://r2.example", "key", "secret")


def _content(tmp_path: Path) -> dict:
    artifact = tmp_path / "data" / "corpus" / "provisions" / "nz" / "statute" / "v1.jsonl"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b'{"body":"text"}\n')
    inventory = tmp_path / "data" / "corpus" / "inventory" / "nz" / "statute" / "v1.json"
    coverage = tmp_path / "data" / "corpus" / "coverage" / "nz" / "statute" / "v1.json"
    source = tmp_path / "data" / "corpus" / "sources" / "nz" / "statute" / "v1" / "act.html"
    for path, body in ((inventory, b"{}\n"), (coverage, b"{}\n"), (source, b"official")):
        path.parent.mkdir(parents=True)
        path.write_bytes(body)
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
    return content


def _keys() -> tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    return (
        b64encode(
            private.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
        ).decode(),
        b64encode(
            private.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode(),
    )


def test_stage_artifacts_uploads_then_hashes_readback(tmp_path: Path) -> None:
    content = _content(tmp_path)
    client = FakeR2()
    report = stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_config(),
        client=client,
    )

    expected_keys = tuple(entry["r2_key"] for entry in content["artifacts"])
    unique_keys = tuple(dict.fromkeys(expected_keys))
    assert report.uploaded_count == len(unique_keys)
    assert report.reused_count == len(expected_keys) - len(unique_keys)
    assert report.verified_keys == expected_keys
    assert report.to_mapping()["artifact_count"] == len(expected_keys)
    assert client.uploads == list(unique_keys)


def test_stage_artifacts_rejects_corrupt_existing_content(tmp_path: Path) -> None:
    content = _content(tmp_path)
    key = content["artifacts"][0]["r2_key"]
    client = FakeR2({key: b"corrupt same-address content"})

    with pytest.raises(ReleaseManifestError, match="readback byte count mismatch|sha256 mismatch"):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
        )
    assert client.uploads == []


def test_stage_artifacts_rejects_local_tamper_before_upload(tmp_path: Path) -> None:
    content = _content(tmp_path)
    artifact = tmp_path / content["artifacts"][0]["path"]
    artifact.write_bytes(b"changed after release content was built")
    client = FakeR2()

    with pytest.raises(
        ReleaseManifestError,
        match="local artifact (byte count|sha256) mismatch",
    ):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
        )

    assert client.objects == {}
    assert client.uploads == []


def test_stage_artifacts_rejects_non_content_addressed_key(tmp_path: Path) -> None:
    content = _content(tmp_path)
    content["artifacts"][0]["r2_key"] = "mutable/latest.json"
    client = FakeR2()

    with pytest.raises(ReleaseManifestError, match="R2 key is not content-addressed"):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
        )

    assert client.objects == {}
    assert client.uploads == []


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("no_artifacts", "no artifacts"),
        ("r2_boundary", "R2 bucket does not match"),
        ("non_object", "non-object artifact"),
        ("path", "missing path or R2 key"),
        ("metadata", "metadata is invalid"),
        ("bucket", "wrong R2 bucket"),
        ("escape", "escapes repository"),
        ("missing", "missing locally"),
    ],
)
def test_stage_artifacts_rejects_invalid_local_boundary(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    content = _content(tmp_path)
    if case == "no_artifacts":
        content["artifacts"] = []
    elif case == "r2_boundary":
        content["r2"]["bucket"] = "other"
    elif case == "non_object":
        content["artifacts"] = [None]
    elif case == "path":
        content["artifacts"][0]["path"] = None
    elif case == "metadata":
        content["artifacts"][0]["bytes"] = True
    elif case == "bucket":
        content["artifacts"][0]["r2_bucket"] = "other"
    elif case == "escape":
        content["artifacts"][0]["path"] = "data/corpus/../../../outside"
    else:
        content["artifacts"][0]["path"] = "data/corpus/coverage/nz/statute/missing.json"

    client = FakeR2()
    with pytest.raises(ReleaseManifestError, match=message):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
        )
    assert client.objects == {}


def test_stage_artifacts_rejects_same_size_local_hash_tamper(tmp_path: Path) -> None:
    content = _content(tmp_path)
    artifact = tmp_path / content["artifacts"][0]["path"]
    artifact.write_bytes(b"x" * artifact.stat().st_size)

    with pytest.raises(ReleaseManifestError, match="local artifact sha256 mismatch"):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=FakeR2(),
        )


def test_stage_artifacts_requires_post_upload_readback(tmp_path: Path) -> None:
    content = _content(tmp_path)

    class DiscardingR2(FakeR2):
        def upload_file(self, filename, bucket, key, **kwargs):
            self.uploads.append(key)

    with pytest.raises(ReleaseManifestError, match="readback is missing after staging"):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=DiscardingR2(),
        )


def test_signed_release_object_is_read_back_and_publicly_verified(tmp_path: Path) -> None:
    content = _content(tmp_path)
    private, public = _keys()
    signed = sign_release_object(build_unsigned_release_object(content), private_key=private)
    client = FakeR2()

    key = stage_signed_release_object(
        signed,
        public_key=public,
        config=_config(),
        client=client,
    )

    assert key in client.objects
    assert key.startswith("releases/nz-rulespec-v1/")


def test_signed_release_object_rejects_conflicting_or_corrupt_storage(tmp_path: Path) -> None:
    content = _content(tmp_path)
    private, public = _keys()
    signed = sign_release_object(build_unsigned_release_object(content), private_key=private)
    key = f"releases/{signed['release']}/{signed['content_sha256']}.json"

    with pytest.raises(ReleaseManifestError, match="already exists with different bytes"):
        stage_signed_release_object(
            signed,
            public_key=public,
            config=_config(),
            client=FakeR2({key: b"different"}),
        )

    class CorruptReadback(FakeR2):
        def get_object(self, **kwargs):
            if kwargs["Key"] not in self.objects:
                raise KeyError(kwargs["Key"])
            return {"Body": BytesIO(b"corrupt")}

    with pytest.raises(ReleaseManifestError, match="readback mismatch"):
        stage_signed_release_object(
            signed,
            public_key=public,
            config=_config(),
            client=CorruptReadback(),
        )


@pytest.mark.parametrize(
    ("serialized", "message"),
    [(b"not json", "invalid JSON"), (b"[]", "not an object")],
)
def test_signed_release_object_rejects_invalid_decoded_readback(
    tmp_path: Path,
    monkeypatch,
    serialized: bytes,
    message: str,
) -> None:
    import axiom_corpus.release.publication as publication

    content = _content(tmp_path)
    private, public = _keys()
    signed = sign_release_object(build_unsigned_release_object(content), private_key=private)
    monkeypatch.setattr(publication, "serialize_release_object", lambda payload: serialized)

    with pytest.raises(ReleaseManifestError, match=message):
        stage_signed_release_object(
            signed,
            public_key=public,
            config=_config(),
            client=FakeR2(),
        )


def test_r2_read_helpers_fail_closed() -> None:
    class ErrorR2:
        def __init__(self, code: str):
            self.code = code

        def get_object(self, **kwargs):
            raise ClientError({"Error": {"Code": self.code}}, "GetObject")

    assert _read_object_or_none(ErrorR2("404"), bucket="axiom-corpus", key="missing") is None
    with pytest.raises(ClientError):
        _read_object_or_none(ErrorR2("500"), bucket="axiom-corpus", key="broken")

    class BodyR2:
        def __init__(self, body):
            self.body = body

        def get_object(self, **kwargs):
            return {"Body": self.body}

    with pytest.raises(ReleaseManifestError, match="returned no body"):
        _read_object_or_none(BodyR2(None), bucket="axiom-corpus", key="empty")
    assert (
        _read_object_or_none(BodyR2(BytesIO(b"bytes")), bucket="axiom-corpus", key="bytes")
        == b"bytes"
    )

    class StringBody:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return "text"

        def close(self):
            return None

    assert _read_object_or_none(BodyR2(StringBody()), bucket="axiom-corpus", key="text") == b"text"

    class InvalidBody(StringBody):
        def read(self):
            return 1

    with pytest.raises(ReleaseManifestError, match="non-byte body"):
        _read_object_or_none(BodyR2(InvalidBody()), bucket="axiom-corpus", key="invalid")

    with pytest.raises(ReleaseManifestError, match="sha256 mismatch"):
        _verify_bytes(b"abc", sha256="0" * 64, size=3, label="same-size")
