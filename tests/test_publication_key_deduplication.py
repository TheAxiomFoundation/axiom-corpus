"""Each content-addressed key gets one streaming staging sequence per release."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from botocore.exceptions import ClientError
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import axiom_corpus.release.publication as publication
from axiom_corpus.corpus.r2 import R2Config
from axiom_corpus.release.manifest import ReleaseManifestError, content_addressed_r2_key
from axiom_corpus.release.publication import stage_release_artifacts

_CONFIG = R2Config("axiom-corpus", "https://r2.invalid", "key", "secret")


class _StreamingBody:
    """Keep the fake GET in flight until its streamed response body closes."""

    def __init__(self, client: _OverlapRejectingR2, key: str, payload: bytes) -> None:
        self._client = client
        self._key = key
        self._body = BytesIO(payload)

    def read(self, size: int = -1) -> bytes:
        assert size >= 0, "artifact GET must use bounded reads"
        return self._body.read(size)

    def close(self) -> None:
        if not self._body.closed:
            self._body.close()
            self._client.finish_read(self._key)


class _OverlapRejectingR2:
    """Model R2's same-object read limit, including streaming body lifetime."""

    def __init__(
        self, objects: dict[str, bytes] | None = None, *, reject_overlap: bool = True
    ) -> None:
        self.objects = dict(objects or {})
        self.gets: Counter[str] = Counter()
        self.readbacks: Counter[str] = Counter()
        self.puts: Counter[str] = Counter()
        self.active_reads: Counter[str] = Counter()
        self.max_active_reads: Counter[str] = Counter()
        self.overlapping_reads: Counter[str] = Counter()
        self._reject_overlap = reject_overlap
        self._lock = threading.Lock()

    def get_object(self, **request: Any) -> dict[str, _StreamingBody]:
        assert request["Bucket"] == _CONFIG.bucket
        key = request["Key"]
        with self._lock:
            self.gets[key] += 1
            if self.active_reads[key]:
                self.overlapping_reads[key] += 1
                if self._reject_overlap:
                    raise ClientError(
                        {
                            "Error": {
                                "Code": "ServiceUnavailable",
                                "Message": "Reduce your rate of simultaneous reads on the same object.",
                            },
                            "ResponseMetadata": {"HTTPStatusCode": 503},
                        },
                        "GetObject",
                    )
            self.active_reads[key] += 1
            self.max_active_reads[key] = max(
                self.max_active_reads[key], self.active_reads[key]
            )
        # Release the GIL while a request is in flight so duplicate-key tasks
        # overlap reliably. Missing-key GETs also occupy the read slot.
        time.sleep(0.01)
        with self._lock:
            if key not in self.objects:
                self.active_reads[key] -= 1
                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                    "GetObject",
                )
            self.readbacks[key] += 1
            return {"Body": _StreamingBody(self, key, self.objects[key])}

    def finish_read(self, key: str) -> None:
        with self._lock:
            self.active_reads[key] -= 1

    def put_object(self, **request: Any) -> None:
        assert request["Bucket"] == _CONFIG.bucket
        assert request["IfNoneMatch"] == "*"
        key = request["Key"]
        payload = bytearray()
        while chunk := request["Body"].read(1024):
            payload.extend(chunk)
        with self._lock:
            self.puts[key] += 1
            if key in self.objects:
                raise ClientError(
                    {
                        "Error": {"Code": "PreconditionFailed"},
                        "ResponseMetadata": {"HTTPStatusCode": 412},
                    },
                    "PutObject",
                )
            self.objects[key] = bytes(payload)


def _release_content(root: Path, payloads: list[bytes]) -> dict[str, Any]:
    entries = []
    for index, payload in enumerate(payloads):
        relative_path = f"data/corpus/sources/nz/statute/v1/{index}.html"
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        entries.append(
            {
                "path": relative_path,
                "sha256": digest,
                "bytes": len(payload),
                "r2_bucket": _CONFIG.bucket,
                "r2_key": content_addressed_r2_key(digest),
            }
        )
    return {"r2": {"bucket": _CONFIG.bucket}, "artifacts": entries}


def _objects(payloads: list[bytes]) -> dict[str, bytes]:
    return {
        content_addressed_r2_key(hashlib.sha256(payload).hexdigest()): payload
        for payload in payloads
    }


def test_parallel_duplicate_keys_do_not_trigger_r2_simultaneous_read_error(
    tmp_path: Path,
) -> None:
    payloads = [b"same official source"] * 4
    content = _release_content(tmp_path, payloads)
    client = _OverlapRejectingR2(_objects(payloads))
    progress = StringIO()

    report = stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_CONFIG,
        client=client,
        workers=4,
        progress_stream=progress,
    )

    key = content["artifacts"][0]["r2_key"]
    assert report.verified_keys == (key,) * 4
    assert report.uploaded_count == 0
    assert report.reused_count == 4
    assert client.gets == {key: 2}
    assert client.max_active_reads == {key: 1}
    assert not any(client.active_reads.values())
    assert "r2 staging start: artifacts=4" in progress.getvalue()
    assert "r2 staging end: verified=4" in progress.getvalue()


@st.composite
def _duplicated_payloads(draw: st.DrawFn) -> list[bytes]:
    payloads = draw(st.lists(st.binary(max_size=32), min_size=1, max_size=3))
    duplicate = draw(st.sampled_from(payloads))
    return list(draw(st.permutations([*payloads, duplicate])))


@pytest.mark.parametrize("workers", [1, 4, 16])
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(payloads=_duplicated_payloads(), existing=st.booleans())
def test_random_duplicate_keys_preserve_entry_order_and_stage_each_key_once(
    tmp_path: Path, workers: int, payloads: list[bytes], existing: bool
) -> None:
    # At most four entries means the workers=16 case also respects the host's
    # limit of four actual staging threads, including on the old code.
    content = _release_content(tmp_path, payloads)
    expected_objects = _objects(payloads)
    client = _OverlapRejectingR2(expected_objects if existing else None)

    report = stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_CONFIG,
        client=client,
        workers=workers,
    )

    keys = tuple(entry["r2_key"] for entry in content["artifacts"])
    assert report.verified_keys == keys
    assert report.artifact_count == len(payloads)
    assert report.artifact_bytes == sum(map(len, payloads))
    assert report.uploaded_count + report.reused_count == len(payloads)
    assert report.uploaded_count == (0 if existing else len(expected_objects))
    assert client.objects == expected_objects
    for key in expected_objects:
        assert client.puts[key] == (0 if existing else 1)
        assert client.gets[key] == 2
        assert client.readbacks[key] >= 1
        assert client.max_active_reads[key] == 1
    assert not client.overlapping_reads
    assert not any(client.active_reads.values())


@pytest.mark.parametrize("existing", [False, True])
def test_serial_and_parallel_duplicate_key_reports_are_identical(
    tmp_path: Path, existing: bool
) -> None:
    payloads = [b"second", b"first", b"second", b"third"]
    content = _release_content(tmp_path, payloads)
    objects = _objects(payloads)
    clients = [
        _OverlapRejectingR2(objects if existing else None, reject_overlap=False)
        for _ in range(2)
    ]
    reports = [
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_CONFIG,
            client=client,
            workers=workers,
        )
        for workers, client in zip((1, 16), clients, strict=True)
    ]

    assert reports[0] == reports[1]
    # This is the pre-deduplication serial report, including its duplicated
    # keys, artifact-byte accounting and uploaded/reused entry counts.
    assert reports[0].to_mapping() == {
        "bucket": _CONFIG.bucket,
        "artifact_count": len(payloads),
        "artifact_bytes": sum(map(len, payloads)),
        "uploaded_count": 0 if existing else len(objects),
        "reused_count": len(payloads) if existing else len(payloads) - len(objects),
        "verified_keys": [entry["r2_key"] for entry in content["artifacts"]],
    }
    for client in clients:
        assert client.gets == dict.fromkeys(objects, 2)
        assert not client.overlapping_reads


@pytest.mark.parametrize("workers", [1, 16])
def test_duplicate_key_size_disagreement_fails_before_remote_requests(
    tmp_path: Path, workers: int
) -> None:
    content = _release_content(tmp_path, [b"same", b"same"])
    content["artifacts"][1]["bytes"] += 1
    client = _OverlapRejectingR2()

    with pytest.raises(ReleaseManifestError):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_CONFIG,
            client=client,
            workers=workers,
        )

    assert not client.gets
    assert not client.puts


@pytest.mark.parametrize("workers", [1, 16])
@pytest.mark.parametrize("index", [0, 1, 2, 3])
@pytest.mark.parametrize("tampered", [b"longer changed source", b"evil"])
def test_every_duplicate_local_path_is_checked(
    tmp_path: Path, workers: int, index: int, tampered: bytes
) -> None:
    content = _release_content(tmp_path, [b"same"] * 4)
    (tmp_path / content["artifacts"][index]["path"]).write_bytes(tampered)
    client = _OverlapRejectingR2()
    expected_mismatch = "sha256" if len(tampered) == 4 else "byte count"

    with pytest.raises(
        ReleaseManifestError, match=f"local artifact {expected_mismatch} mismatch"
    ):
        stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_CONFIG,
            client=client,
            workers=workers,
        )


def test_duplicate_keys_keep_only_one_local_snapshot_open(tmp_path: Path) -> None:
    payloads = [b"same source"] * 4
    content = _release_content(tmp_path, payloads)
    client = _OverlapRejectingR2(reject_overlap=False)
    original_snapshot = publication._snapshot_file
    lock = threading.Lock()
    active = 0
    peak = 0
    snapshotted: list[Path] = []

    @contextmanager
    def snapshot(path: Path) -> Iterator[Any]:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
            snapshotted.append(path)
        try:
            with original_snapshot(path) as result:
                time.sleep(0.01)
                yield result
        finally:
            with lock:
                active -= 1

    with mock.patch.object(publication, "_snapshot_file", snapshot):
        report = stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_CONFIG,
            client=client,
            workers=16,
        )

    assert report.artifact_count == 4
    assert active == 0
    assert peak == 1
    assert Counter(snapshotted) == Counter(
        (tmp_path / entry["path"]).resolve() for entry in content["artifacts"]
    )
