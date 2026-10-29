"""Content-addressed R2 staging with exact readback verification."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any, TextIO

from botocore.exceptions import ClientError

from axiom_corpus.corpus.content_store import R2UnavailableError, RetryPolicy, is_transient
from axiom_corpus.corpus.r2 import R2Config, make_r2_client
from axiom_corpus.release.manifest import (
    ReleaseManifestError,
    canonical_corpus_artifact_file,
    content_addressed_r2_key,
    release_object_r2_key,
    serialize_release_object,
    verify_release_object,
)

_CONDITIONAL_WRITE_CONFLICT_CODES = {
    "409",
    "412",
    "ConditionalRequestConflict",
    "PreconditionFailed",
}
_MAX_CONDITIONAL_WRITE_ATTEMPTS = 3
# Artifact objects are verified from R2 in reads of this size, never whole: a
# provisions artifact can be 756 MB, and sixteen staging workers run at once.
_R2_READ_BYTES = 1024 * 1024
# Publication drives R2 from a bounded thread pool. Sixteen workers keep a
# 17,000-object release inside one CI job without approaching R2's per-bucket
# request limits; ``publish_corpus.py --r2-workers`` overrides it.
DEFAULT_R2_STAGING_WORKERS = 16
_R2_PROGRESS_INTERVAL_SECONDS = 30.0


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


@dataclass(frozen=True)
class _ArtifactEntry:
    """One validated release artifact, ready to stage."""

    index: int
    path_value: str
    path: Path
    key: str
    sha256: str
    size: int


@dataclass(frozen=True)
class _StagedArtifact:
    index: int
    key: str
    size: int
    uploaded: bool


def stage_release_artifacts(
    repo_root: Path,
    *,
    release_content: Mapping[str, Any],
    config: R2Config,
    client: Any | None = None,
    workers: int = 1,
    progress_stream: TextIO | None = None,
    read_retry: RetryPolicy | None = None,
) -> R2ReadbackReport:
    """Upload missing content objects and hash their downloaded bytes.

    Existing objects are never overwritten. A byte mismatch at a SHA-256 key is
    a storage-integrity failure and aborts publication.

    ``workers`` bounds a thread pool over the per-artifact sequence (snapshot
    and hash locally, read the existing object, conditionally write, read back,
    verify bytes and hash). Every artifact still runs that whole sequence on
    its own. Entries sharing a content key are serialized, including body
    consumption, so duplicate source bytes do not produce overlapping reads.
    Transient reads retry under ``read_retry`` (up to eight requests per
    verification read by default),
    restarting the stream and its hash after a failure. Non-transient errors
    and exhausted retries cancel the remaining work and are re-raised.
    ``verified_keys`` keeps the artifact order of ``release_content`` regardless
    of completion order, so the signed readback evidence is identical for any
    worker count. ``progress_stream`` receives flushed, timestamped progress.
    """
    if workers < 1:
        raise ValueError("workers must be positive")
    r2 = client or make_r2_client(config, max_pool_connections=workers)
    reader = client or make_r2_client(config, max_pool_connections=workers, sdk_retries=False)
    retry = read_retry or RetryPolicy()
    artifacts = release_content.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ReleaseManifestError("release content has no artifacts to stage")
    declared_r2 = release_content.get("r2")
    if not isinstance(declared_r2, dict) or declared_r2.get("bucket") != config.bucket:
        raise ReleaseManifestError("release content R2 bucket does not match publication target")

    root = repo_root.resolve()
    # Every entry is checked before the first network request: a malformed
    # manifest fails closed without staging anything.
    entries = tuple(
        _validated_artifact_entry(root, index, raw_entry, bucket=config.bucket)
        for index, raw_entry in enumerate(artifacts)
    )
    key_locks = {entry.key: threading.Lock() for entry in entries}

    def _stage(entry: _ArtifactEntry) -> _StagedArtifact:
        with key_locks[entry.key]:
            return _stage_one_artifact(
                r2, bucket=config.bucket, entry=entry, read_client=reader, read_retry=retry
            )

    expected_bytes = sum(entry.size for entry in entries)
    started = time.monotonic()
    emit_progress(
        progress_stream,
        f"r2 staging start: artifacts={len(entries)} bytes={expected_bytes} workers={workers}",
    )

    staged: dict[int, _StagedArtifact] = {}
    last_report = started

    def _report(force: bool = False) -> None:
        nonlocal last_report
        now = time.monotonic()
        if not force and now - last_report < _R2_PROGRESS_INTERVAL_SECONDS:
            return
        last_report = now
        done_bytes = sum(item.size for item in staged.values())
        uploaded_so_far = sum(1 for item in staged.values() if item.uploaded)
        emit_progress(
            progress_stream,
            f"r2 staging progress: verified={len(staged)}/{len(entries)} "
            f"bytes={done_bytes}/{expected_bytes} uploaded={uploaded_so_far} "
            f"reused={len(staged) - uploaded_so_far} elapsed={now - started:.1f}s",
        )

    if workers == 1:
        for entry in entries:
            staged[entry.index] = _stage(entry)
            _report()
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures: list[Future[_StagedArtifact]] = [
                executor.submit(_stage, entry) for entry in entries
            ]
            try:
                for future in as_completed(futures):
                    # The first failure propagates unchanged; pending work is
                    # cancelled so a storage-integrity error stops staging.
                    result = future.result()
                    staged[result.index] = result
                    _report()
            except BaseException:
                for pending in futures:
                    pending.cancel()
                raise

    if len(staged) != len(entries) or set(staged) != {entry.index for entry in entries}:
        raise ReleaseManifestError("R2 staging did not verify every release artifact")
    ordered = [staged[entry.index] for entry in entries]
    uploaded = sum(1 for item in ordered if item.uploaded)
    report = R2ReadbackReport(
        bucket=config.bucket,
        artifact_count=len(entries),
        artifact_bytes=sum(item.size for item in ordered),
        uploaded_count=uploaded,
        reused_count=len(ordered) - uploaded,
        verified_keys=tuple(item.key for item in ordered),
    )
    emit_progress(
        progress_stream,
        f"r2 staging end: verified={report.artifact_count} bytes={report.artifact_bytes} "
        f"uploaded={report.uploaded_count} reused={report.reused_count} "
        f"elapsed={time.monotonic() - started:.1f}s",
    )
    return report


def _validated_artifact_entry(
    root: Path,
    index: int,
    raw_entry: object,
    *,
    bucket: str,
) -> _ArtifactEntry:
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
    if raw_entry.get("r2_bucket") != bucket:
        raise ReleaseManifestError(f"release artifact uses the wrong R2 bucket: {path_value}")
    path = canonical_corpus_artifact_file(root, path_value)
    return _ArtifactEntry(
        index=index,
        path_value=path_value,
        path=path,
        key=key,
        sha256=digest,
        size=expected_bytes,
    )


def _stage_one_artifact(
    client: Any,
    *,
    bucket: str,
    entry: _ArtifactEntry,
    read_client: Any | None = None,
    read_retry: RetryPolicy | None = None,
) -> _StagedArtifact:
    """Stage one artifact: snapshot, hash, conditional write, exact readback."""
    reader = read_client if read_client is not None else client
    retry = read_retry or RetryPolicy()

    def verify_remote() -> bool:
        return _retry_read(
            lambda: _verify_object_or_none(
                reader, bucket=bucket, key=entry.key, sha256=entry.sha256, size=entry.size
            ),
            key=entry.key,
            retry=retry,
        )

    with _snapshot_file(entry.path) as (snapshot, actual_digest, actual_bytes):
        # Hash, size, and upload all refer to this one immutable snapshot.
        # In particular, the repository path is never reopened after the
        # digest has been computed.
        if actual_bytes != entry.size:
            raise ReleaseManifestError(
                f"local artifact byte count mismatch for {entry.path_value}: "
                f"expected {entry.size}, got {actual_bytes}"
            )
        if actual_digest != entry.sha256:
            raise ReleaseManifestError(
                f"local artifact sha256 mismatch for {entry.path_value}: "
                f"expected {entry.sha256}, got {actual_digest}"
            )

        if verify_remote():
            was_uploaded = False
        else:
            was_uploaded = _put_snapshot_if_absent(
                client,
                bucket=bucket,
                key=entry.key,
                snapshot=snapshot,
                filename=entry.path.name,
                sha256=entry.sha256,
                size=entry.size,
                verify_existing=verify_remote,
            )

    # Always read after the upload decision. Metadata, ETags, and upload
    # return values are not evidence that R2 persisted the expected bytes.
    if not verify_remote():
        raise ReleaseManifestError(f"R2 readback is missing after staging: {entry.key}")
    return _StagedArtifact(index=entry.index, key=entry.key, size=entry.size, uploaded=was_uploaded)


def _retry_read[ReadResult](
    read: Callable[[], ReadResult], *, key: str, retry: RetryPolicy
) -> ReadResult:
    """Retry a complete verified read, with one HTTP request per attempt.

    The read client has SDK retries disabled. The existing streaming verifier
    closes a failed response before returning here and starts a fresh hash and
    length for each retry. Missing objects, malformed responses, and integrity
    failures retain their existing fail-closed behavior.
    """
    for attempt in range(1, max(1, retry.attempts) + 1):
        try:
            return read()
        except Exception as exc:  # noqa: BLE001 - only classified transient reads retry
            if not is_transient(exc):
                raise
            if attempt >= retry.attempts:
                raise R2UnavailableError(
                    f"{exc} (R2 GetObject {key}: gave up after {attempt} attempts)"
                ) from exc
            retry.sleep(retry.delay(attempt, exc))
    raise AssertionError("read retry loop must return or raise")


def emit_progress(stream: TextIO | None, message: str) -> None:
    """Write one flushed, UTC-timestamped progress line to ``stream``."""
    if stream is None:
        return
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{stamp} {message}", file=stream, flush=True)


def stage_signed_release_object(
    release_object: Mapping[str, Any],
    *,
    public_key: str,
    config: R2Config,
    client: Any | None = None,
    read_retry: RetryPolicy | None = None,
) -> str:
    """Store and read back the signed release object before activation."""
    verify_release_object(release_object, public_key=public_key)
    release_name = str(release_object["release"])
    content_sha256 = str(release_object["content_sha256"])
    key = release_object_r2_key(release_name, content_sha256)
    payload = serialize_release_object(release_object)
    r2 = client or make_r2_client(config)
    reader = client or make_r2_client(config, sdk_retries=False)
    retry = read_retry or RetryPolicy()

    def read_remote() -> bytes | None:
        return _retry_read(
            lambda: _read_object_or_none(reader, bucket=config.bucket, key=key),
            key=key,
            retry=retry,
        )

    existing = read_remote()
    if existing is None:
        _put_release_object_if_absent(
            r2,
            bucket=config.bucket,
            key=key,
            payload=payload,
            content_sha256=content_sha256,
            read_existing=read_remote,
        )
    elif existing != payload:
        raise ReleaseManifestError(
            f"immutable release object already exists with different bytes: {key}"
        )

    readback = read_remote()
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


@contextmanager
def _snapshot_file(path: Path) -> Iterator[tuple[SpooledTemporaryFile[bytes], str, int]]:
    with SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as snapshot:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                snapshot.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        snapshot.seek(0)
        yield snapshot, digest.hexdigest(), size


def _put_snapshot_if_absent(
    client: Any,
    *,
    bucket: str,
    key: str,
    snapshot: SpooledTemporaryFile[bytes],
    filename: str,
    sha256: str,
    size: int,
    verify_existing: Callable[[], bool] | None = None,
) -> bool:
    request: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": snapshot,
        "ContentLength": size,
        "IfNoneMatch": "*",
        "Metadata": {"sha256": sha256},
    }
    content_type = mimetypes.guess_type(filename)[0]
    if content_type:
        request["ContentType"] = content_type

    for attempt in range(_MAX_CONDITIONAL_WRITE_ATTEMPTS):
        snapshot.seek(0)
        try:
            client.put_object(**request)
        except ClientError as exc:
            if not _is_conditional_write_conflict(exc):
                raise
            verified = (
                verify_existing()
                if verify_existing is not None
                else _verify_object_or_none(
                    client, bucket=bucket, key=key, sha256=sha256, size=size
                )
            )
            if verified:
                return False
            if attempt + 1 == _MAX_CONDITIONAL_WRITE_ATTEMPTS:
                raise ReleaseManifestError(
                    f"R2 conditional write conflict did not converge: {key}"
                ) from exc
            continue
        return True
    raise AssertionError("conditional write loop must return or raise")


def _put_release_object_if_absent(
    client: Any,
    *,
    bucket: str,
    key: str,
    payload: bytes,
    content_sha256: str,
    read_existing: Callable[[], bytes | None] | None = None,
) -> None:
    for attempt in range(_MAX_CONDITIONAL_WRITE_ATTEMPTS):
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
                ContentLength=len(payload),
                IfNoneMatch="*",
                Metadata={"content-sha256": content_sha256},
            )
        except ClientError as exc:
            if not _is_conditional_write_conflict(exc):
                raise
            remote = (
                read_existing()
                if read_existing is not None
                else _read_object_or_none(client, bucket=bucket, key=key)
            )
            if remote is not None:
                if remote != payload:
                    raise ReleaseManifestError(
                        f"immutable release object already exists with different bytes: {key}"
                    ) from exc
                return
            if attempt + 1 == _MAX_CONDITIONAL_WRITE_ATTEMPTS:
                raise ReleaseManifestError(
                    f"R2 conditional release-object write did not converge: {key}"
                ) from exc
            continue
        return
    raise AssertionError("conditional write loop must return or raise")


def _is_conditional_write_conflict(exc: ClientError) -> bool:
    error = exc.response.get("Error", {})
    code = str(error.get("Code", ""))
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in _CONDITIONAL_WRITE_CONFLICT_CODES or status in {409, 412}


def _object_body_or_none(client: Any, *, bucket: str, key: str) -> Any | None:
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
    return body


def _read_object_or_none(client: Any, *, bucket: str, key: str) -> bytes | None:
    """Read a whole object; only for small ones, such as signed release objects."""
    body = _object_body_or_none(client, bucket=bucket, key=key)
    if body is None:
        return None
    with closing(body):
        raw = body.read()
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if not isinstance(raw, bytes):
        raise ReleaseManifestError(f"R2 returned a non-byte body for {key}")
    return raw


def _verify_object_or_none(
    client: Any,
    *,
    bucket: str,
    key: str,
    sha256: str,
    size: int,
) -> bool:
    """Stream one artifact object and verify its bytes; ``False`` if absent.

    Reads in bounded chunks and holds only a running hash and length, then
    fails exactly as reading the whole object and calling ``_verify_bytes``
    did: byte count first, then SHA-256.
    """
    body = _object_body_or_none(client, bucket=bucket, key=key)
    if body is None:
        return False
    digest = hashlib.sha256()
    length = 0
    with closing(body):
        while True:
            chunk = body.read(_R2_READ_BYTES)
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            if not isinstance(chunk, bytes):
                raise ReleaseManifestError(f"R2 returned a non-byte body for {key}")
            if not chunk:
                break
            digest.update(chunk)
            length += len(chunk)
    if length != size:
        raise ReleaseManifestError(
            f"R2 readback byte count mismatch for {key}: expected {size}, got {length}"
        )
    actual = digest.hexdigest()
    if actual != sha256:
        raise ReleaseManifestError(
            f"R2 readback sha256 mismatch for {key}: expected {sha256}, got {actual}"
        )
    return True


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
