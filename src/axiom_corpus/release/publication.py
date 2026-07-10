"""Content-addressed R2 staging with exact readback verification."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

from axiom_corpus.corpus.r2 import R2Config, make_r2_client
from axiom_corpus.release.manifest import (
    ReleaseManifestError,
    content_addressed_r2_key,
    release_object_r2_key,
    serialize_release_object,
    sha256_file,
    verify_release_object,
)


@dataclass(frozen=True)
class R2ReadbackReport:
    bucket: str
    artifact_count: int
    artifact_bytes: int
    uploaded_count: int
    reused_count: int
    verified_keys: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "artifact_count": self.artifact_count,
            "artifact_bytes": self.artifact_bytes,
            "uploaded_count": self.uploaded_count,
            "reused_count": self.reused_count,
            "verified_keys": list(self.verified_keys),
        }


def stage_release_artifacts(
    repo_root: Path,
    *,
    release_content: Mapping[str, Any],
    config: R2Config,
    client: Any | None = None,
) -> R2ReadbackReport:
    """Upload missing content objects and hash their downloaded bytes.

    Existing objects are never overwritten. A byte mismatch at a SHA-256 key is
    a storage-integrity failure and aborts publication.
    """
    r2 = client or make_r2_client(config)
    artifacts = release_content.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ReleaseManifestError("release content has no artifacts to stage")
    declared_r2 = release_content.get("r2")
    if not isinstance(declared_r2, dict) or declared_r2.get("bucket") != config.bucket:
        raise ReleaseManifestError("release content R2 bucket does not match publication target")

    root = repo_root.resolve()
    uploaded = 0
    reused = 0
    total_bytes = 0
    verified: list[str] = []
    for raw_entry in artifacts:
        if not isinstance(raw_entry, dict):
            raise ReleaseManifestError("release content contains a non-object artifact")
        path_value = raw_entry.get("path")
        key = raw_entry.get("r2_key")
        digest = raw_entry.get("sha256")
        expected_bytes = raw_entry.get("bytes")
        if (
            not isinstance(path_value, str)
            or not path_value.startswith("data/corpus/")
            or not isinstance(key, str)
        ):
            raise ReleaseManifestError("release artifact is missing path or R2 key")
        if (
            not isinstance(digest, str)
            or not isinstance(expected_bytes, int)
            or isinstance(expected_bytes, bool)
            or expected_bytes < 0
        ):
            raise ReleaseManifestError(f"release artifact metadata is invalid: {path_value}")
        if key != content_addressed_r2_key(digest):
            raise ReleaseManifestError(
                f"release artifact R2 key is not content-addressed: {path_value}"
            )
        if raw_entry.get("r2_bucket") != config.bucket:
            raise ReleaseManifestError(f"release artifact uses the wrong R2 bucket: {path_value}")
        path = (root / path_value).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ReleaseManifestError(
                f"release artifact escapes repository: {path_value}"
            ) from exc
        if not path.is_file():
            raise ReleaseManifestError(f"release artifact is missing locally: {path_value}")
        # Never upload bytes under a digest they do not actually have. Readback
        # remains mandatory after upload, but this preflight prevents a bad
        # local declaration from contaminating an otherwise immutable object
        # key before the mismatch is noticed.
        actual_bytes = path.stat().st_size
        if actual_bytes != expected_bytes:
            raise ReleaseManifestError(
                f"local artifact byte count mismatch for {path_value}: "
                f"expected {expected_bytes}, got {actual_bytes}"
            )
        actual_digest = sha256_file(path)
        if actual_digest != digest:
            raise ReleaseManifestError(
                f"local artifact sha256 mismatch for {path_value}: "
                f"expected {digest}, got {actual_digest}"
            )

        remote = _read_object_or_none(r2, bucket=config.bucket, key=key)
        if remote is None:
            _upload_file(r2, bucket=config.bucket, key=key, path=path, sha256=digest)
            uploaded += 1
        else:
            _verify_bytes(remote, sha256=digest, size=expected_bytes, label=key)
            reused += 1

        # Always read after the upload decision. Metadata, ETags, and upload
        # return values are not evidence that R2 persisted the expected bytes.
        readback = _read_object_or_none(r2, bucket=config.bucket, key=key)
        if readback is None:
            raise ReleaseManifestError(f"R2 readback is missing after staging: {key}")
        _verify_bytes(readback, sha256=digest, size=expected_bytes, label=key)
        total_bytes += expected_bytes
        verified.append(key)

    return R2ReadbackReport(
        bucket=config.bucket,
        artifact_count=len(artifacts),
        artifact_bytes=total_bytes,
        uploaded_count=uploaded,
        reused_count=reused,
        verified_keys=tuple(verified),
    )


def stage_signed_release_object(
    release_object: Mapping[str, Any],
    *,
    public_key: str,
    config: R2Config,
    client: Any | None = None,
) -> str:
    """Store and read back the signed release object before activation."""
    verify_release_object(release_object, public_key=public_key)
    release_name = str(release_object["release"])
    content_sha256 = str(release_object["content_sha256"])
    key = release_object_r2_key(release_name, content_sha256)
    payload = serialize_release_object(release_object)
    r2 = client or make_r2_client(config)

    existing = _read_object_or_none(r2, bucket=config.bucket, key=key)
    if existing is None:
        r2.put_object(
            Bucket=config.bucket,
            Key=key,
            Body=payload,
            ContentType="application/json",
            Metadata={"content-sha256": content_sha256},
        )
    elif existing != payload:
        raise ReleaseManifestError(
            f"immutable release object already exists with different bytes: {key}"
        )

    readback = _read_object_or_none(r2, bucket=config.bucket, key=key)
    if readback != payload:
        raise ReleaseManifestError(f"signed release object readback mismatch: {key}")
    try:
        decoded = json.loads(readback)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ReleaseManifestError(
            f"signed release object readback is invalid JSON: {key}"
        ) from exc
    if not isinstance(decoded, dict):
        raise ReleaseManifestError(f"signed release object readback is not an object: {key}")
    verify_release_object(decoded, public_key=public_key)
    return key


def _upload_file(client: Any, *, bucket: str, key: str, path: Path, sha256: str) -> None:
    extra: dict[str, Any] = {"Metadata": {"sha256": sha256}}
    content_type = mimetypes.guess_type(path.name)[0]
    if content_type:
        extra["ContentType"] = content_type
    client.upload_file(str(path), bucket, key, ExtraArgs=extra)


def _read_object_or_none(client: Any, *, bucket: str, key: str) -> bytes | None:
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    except KeyError:
        # Small in-memory clients used by unit tests model absence as KeyError.
        return None
    body = response.get("Body")
    if body is None:
        raise ReleaseManifestError(f"R2 returned no body for {key}")
    with closing(body):
        raw = body.read()
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if not isinstance(raw, bytes):
        raise ReleaseManifestError(f"R2 returned a non-byte body for {key}")
    return raw


def _verify_bytes(payload: bytes, *, sha256: str, size: int, label: str) -> None:
    if len(payload) != size:
        raise ReleaseManifestError(
            f"R2 readback byte count mismatch for {label}: expected {size}, got {len(payload)}"
        )
    actual = hashlib.sha256(payload).hexdigest()
    if actual != sha256:
        raise ReleaseManifestError(
            f"R2 readback sha256 mismatch for {label}: expected {sha256}, got {actual}"
        )
