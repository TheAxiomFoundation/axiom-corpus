from __future__ import annotations

import hashlib
import re
import threading
import time
from base64 import b64encode
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.r2 import R2Config
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)
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
        # R2's conditional write is atomic; the fake must be too when the
        # staging pool drives it from several threads.
        self._lock = threading.Lock()

    def get_object(self, **kwargs):
        assert kwargs["Bucket"] == "axiom-corpus"
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}

    def put_object(self, **kwargs):
        assert kwargs["Bucket"] == "axiom-corpus"
        assert kwargs["IfNoneMatch"] == "*"
        key = kwargs["Key"]
        body = kwargs["Body"]
        payload = body.read() if hasattr(body, "read") else bytes(body)
        with self._lock:
            if key in self.objects:
                raise ClientError(
                    {
                        "Error": {"Code": "PreconditionFailed"},
                        "ResponseMetadata": {"HTTPStatusCode": 412},
                    },
                    "PutObject",
                )
            self.objects[key] = payload
            self.uploads.append(key)


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
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
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
        "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
        "created_at": "2026-07-10T00:00:00Z",
        "selector_sha256": selector_sha256(release),
        "corpus_base": "data/corpus",
        "git": {
            "commit": "a" * 40,
            "committed_at": "2026-07-10T00:00:00Z",
        },
        "r2": {"bucket": "axiom-corpus", "addressing": "sha256"},
        "scopes": [
            {
                "jurisdiction": "nz",
                "document_class": "statute",
                "version": "v1",
                "provision_rows": 1,
                "navigation_rows": 1,
                "provision_projection_sha256": "a" * 64,
                "navigation_projection_sha256": "b" * 64,
            }
        ],
        "artifacts": entries,
        "validation": {},
    }
    content["validation"] = {
        "passed": True,
        "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
        "deep_validation": {"error_count": 0, "warning_count": 0, "scope_count": 1},
        "r2_readback": {
            "bucket": "axiom-corpus",
            "artifact_count": len(entries),
            "artifact_bytes": sum(entry["bytes"] for entry in entries),
            "verified_keys": [entry["r2_key"] for entry in entries],
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
        ("escape", "escapes exact data/corpus boundary"),
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


def test_stage_artifacts_rejects_symlinked_artifact(tmp_path: Path) -> None:
    content = _content(tmp_path)
    relative = content["artifacts"][0]["path"]
    artifact = tmp_path / relative
    target = tmp_path / "inside-repository.txt"
    target.write_bytes(artifact.read_bytes())
    artifact.unlink()
    artifact.symlink_to(target)

    with pytest.raises(ReleaseManifestError, match="path contains a symlink"):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=FakeR2(),
        )


def test_stage_artifacts_rejects_symlinked_parent_directory(tmp_path: Path) -> None:
    content = _content(tmp_path)
    relative = content["artifacts"][0]["path"]
    artifact = tmp_path / relative
    original_parent = artifact.parent
    relocated_parent = tmp_path / "relocated-artifacts"
    original_parent.rename(relocated_parent)
    original_parent.symlink_to(relocated_parent, target_is_directory=True)

    with pytest.raises(ReleaseManifestError, match="path contains a symlink"):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=FakeR2(),
        )


def test_stage_artifacts_uploads_one_immutable_snapshot(tmp_path: Path) -> None:
    content = _content(tmp_path)
    entry = content["artifacts"][0]
    artifact = tmp_path / entry["path"]
    original = artifact.read_bytes()

    class MutatingR2(FakeR2):
        mutated = False

        def put_object(self, **kwargs):
            if kwargs["Key"] == entry["r2_key"] and not self.mutated:
                self.mutated = True
                artifact.write_bytes(b"changed after hashing")
            return super().put_object(**kwargs)

    client = MutatingR2()
    stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_config(),
        client=client,
    )

    assert artifact.read_bytes() != original
    assert client.objects[entry["r2_key"]] == original


@pytest.mark.parametrize(
    ("code", "status"),
    [("ConditionalRequestConflict", 409), ("PreconditionFailed", 412)],
)
def test_stage_artifacts_handles_conditional_write_race(
    tmp_path: Path,
    code: str,
    status: int,
) -> None:
    content = _content(tmp_path)
    entry = content["artifacts"][0]
    expected = (tmp_path / entry["path"]).read_bytes()

    class RacingR2(FakeR2):
        raced = False

        def put_object(self, **kwargs):
            if kwargs["Key"] == entry["r2_key"] and not self.raced:
                self.raced = True
                if status == 412:
                    self.objects[kwargs["Key"]] = expected
                raise ClientError(
                    {
                        "Error": {"Code": code},
                        "ResponseMetadata": {"HTTPStatusCode": status},
                    },
                    "PutObject",
                )
            return super().put_object(**kwargs)

    client = RacingR2()
    report = stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_config(),
        client=client,
    )

    assert client.objects[entry["r2_key"]] == expected
    if status == 412:
        assert report.reused_count >= 1
    else:
        assert entry["r2_key"] in client.uploads


def test_stage_artifacts_requires_post_upload_readback(tmp_path: Path) -> None:
    content = _content(tmp_path)

    class DiscardingR2(FakeR2):
        def put_object(self, **kwargs):
            self.uploads.append(kwargs["Key"])

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


@pytest.mark.parametrize(
    ("code", "status"),
    [("ConditionalRequestConflict", 409), ("PreconditionFailed", 412)],
)
def test_signed_release_object_handles_conditional_write_race(
    tmp_path: Path,
    code: str,
    status: int,
) -> None:
    content = _content(tmp_path)
    private, public = _keys()
    signed = sign_release_object(build_unsigned_release_object(content), private_key=private)

    class RacingR2(FakeR2):
        raced = False

        def put_object(self, **kwargs):
            if not self.raced:
                self.raced = True
                if status == 412:
                    self.objects[kwargs["Key"]] = bytes(kwargs["Body"])
                raise ClientError(
                    {
                        "Error": {"Code": code},
                        "ResponseMetadata": {"HTTPStatusCode": status},
                    },
                    "PutObject",
                )
            return super().put_object(**kwargs)

    key = stage_signed_release_object(
        signed,
        public_key=public,
        config=_config(),
        client=RacingR2(),
    )

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


_TIMESTAMP_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ")


def _many_artifact_content(tmp_path: Path, extra_sources: int = 12) -> dict:
    """The single-scope fixture plus enough source files to exercise a pool."""
    content = _content(tmp_path)
    source_dir = tmp_path / "data" / "corpus" / "sources" / "nz" / "statute" / "v1"
    for index in range(extra_sources):
        path = source_dir / f"part-{index:03d}.html"
        body = f"<p>Official part {index}.</p>".encode()
        path.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        content["artifacts"].append(
            {
                "artifact_class": "sources",
                "path": path.relative_to(tmp_path).as_posix(),
                "sha256": digest,
                "bytes": len(body),
                "r2_bucket": "axiom-corpus",
                "r2_key": content_addressed_r2_key(digest),
            }
        )
    content["artifacts"].sort(key=lambda entry: entry["path"])
    return content


def test_stage_artifacts_parallel_workers_produce_identical_signed_evidence(
    tmp_path: Path,
) -> None:
    content = _many_artifact_content(tmp_path)
    expected_keys = tuple(entry["r2_key"] for entry in content["artifacts"])
    # Half the objects already exist so both the upload and the reuse branch
    # run under the pool. The fixture's inventory and coverage files share
    # bytes, so one content-addressed key is legitimately uploaded once and
    # reused once.
    preexisting = {
        entry["r2_key"]: (tmp_path / entry["path"]).read_bytes()
        for entry in content["artifacts"][::2]
    }
    expected_uploads = len(set(expected_keys) - set(preexisting))

    serial_client = FakeR2(preexisting)
    serial = stage_release_artifacts(
        tmp_path, release_content=content, config=_config(), client=serial_client, workers=1
    )
    parallel_client = FakeR2(preexisting)
    parallel = stage_release_artifacts(
        tmp_path, release_content=content, config=_config(), client=parallel_client, workers=4
    )

    # The report is signed content: order and counts must not depend on the
    # worker count or on completion order.
    assert serial == parallel
    assert parallel.verified_keys == expected_keys
    assert parallel.artifact_count == len(content["artifacts"])
    assert parallel.uploaded_count == expected_uploads
    assert parallel.reused_count == len(content["artifacts"]) - expected_uploads
    assert parallel_client.objects == serial_client.objects
    assert sorted(parallel_client.uploads) == sorted(serial_client.uploads)


def test_stage_artifacts_parallel_actually_runs_concurrently(tmp_path: Path) -> None:
    content = _many_artifact_content(tmp_path)
    seen = {"max_in_flight": 0, "in_flight": 0}
    lock = threading.Lock()

    class SlowR2(FakeR2):
        def get_object(self, **kwargs):
            with lock:
                seen["in_flight"] += 1
                seen["max_in_flight"] = max(seen["max_in_flight"], seen["in_flight"])
            try:
                # Long enough that a serial loop can never overlap two reads.
                time.sleep(0.02)
                return super().get_object(**kwargs)
            finally:
                with lock:
                    seen["in_flight"] -= 1

    stage_release_artifacts(
        tmp_path, release_content=content, config=_config(), client=SlowR2(), workers=4
    )
    assert seen["max_in_flight"] >= 2

    seen.update(max_in_flight=0, in_flight=0)
    stage_release_artifacts(
        tmp_path, release_content=content, config=_config(), client=SlowR2(), workers=1
    )
    assert seen["max_in_flight"] == 1


def test_stage_artifacts_parallel_fails_closed_on_corrupt_object(tmp_path: Path) -> None:
    content = _many_artifact_content(tmp_path)
    corrupt = content["artifacts"][7]
    # Same length as the signed artifact so only the hash check can catch it.
    corrupt_bytes = b"x" * corrupt["bytes"]
    client = FakeR2({corrupt["r2_key"]: corrupt_bytes})

    with pytest.raises(ReleaseManifestError, match="sha256 mismatch"):
        stage_release_artifacts(
            tmp_path, release_content=content, config=_config(), client=client, workers=4
        )

    # Conditional writes never replace the corrupt object, and every object the
    # pool did upload is byte-exact.
    assert client.objects[corrupt["r2_key"]] == corrupt_bytes
    assert corrupt["r2_key"] not in client.uploads
    by_key = {entry["r2_key"]: entry for entry in content["artifacts"]}
    for key in client.uploads:
        assert hashlib.sha256(client.objects[key]).hexdigest() == by_key[key]["sha256"]


def test_stage_artifacts_parallel_requires_readback_for_every_object(tmp_path: Path) -> None:
    content = _many_artifact_content(tmp_path)
    dropped = content["artifacts"][3]["r2_key"]

    class DroppingR2(FakeR2):
        def put_object(self, **kwargs):
            if kwargs["Key"] == dropped:
                self.uploads.append(dropped)
                return
            super().put_object(**kwargs)

    with pytest.raises(ReleaseManifestError, match="readback is missing after staging"):
        stage_release_artifacts(
            tmp_path, release_content=content, config=_config(), client=DroppingR2(), workers=4
        )


def test_stage_artifacts_validates_every_entry_before_any_request(tmp_path: Path) -> None:
    content = _many_artifact_content(tmp_path)
    content["artifacts"][-1]["r2_bucket"] = "other-bucket"

    class CountingR2(FakeR2):
        calls = 0

        def get_object(self, **kwargs):
            CountingR2.calls += 1
            return super().get_object(**kwargs)

    for workers in (1, 4):
        with pytest.raises(ReleaseManifestError, match="wrong R2 bucket"):
            stage_release_artifacts(
                tmp_path,
                release_content=content,
                config=_config(),
                client=CountingR2(),
                workers=workers,
            )
    assert CountingR2.calls == 0


def test_stage_artifacts_rejects_nonpositive_workers(tmp_path: Path) -> None:
    content = _content(tmp_path)
    with pytest.raises(ValueError, match="workers must be positive"):
        stage_release_artifacts(
            tmp_path, release_content=content, config=_config(), client=FakeR2(), workers=0
        )


def test_stage_artifacts_emits_timestamped_flushed_progress(tmp_path: Path) -> None:
    content = _many_artifact_content(tmp_path)
    total_bytes = sum(entry["bytes"] for entry in content["artifacts"])
    unique_keys = len({entry["r2_key"] for entry in content["artifacts"]})
    duplicates = len(content["artifacts"]) - unique_keys

    class FlushCountingStream(StringIO):
        flushes = 0

        def flush(self) -> None:
            FlushCountingStream.flushes += 1
            super().flush()

    stream = FlushCountingStream()
    stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_config(),
        client=FakeR2(),
        workers=3,
        progress_stream=stream,
    )

    lines = stream.getvalue().splitlines()
    assert all(_TIMESTAMP_PREFIX.match(line) for line in lines), lines
    assert lines[0].endswith(
        f"r2 staging start: artifacts={len(content['artifacts'])} bytes={total_bytes} workers=3"
    )
    assert f"r2 staging end: verified={len(content['artifacts'])} bytes={total_bytes}" in lines[-1]
    assert f"uploaded={unique_keys} reused={duplicates} elapsed=" in lines[-1]
    assert FlushCountingStream.flushes >= len(lines)


def test_stage_artifacts_is_silent_without_progress_stream(tmp_path: Path, capsys) -> None:
    stage_release_artifacts(
        tmp_path, release_content=_content(tmp_path), config=_config(), client=FakeR2(), workers=2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
