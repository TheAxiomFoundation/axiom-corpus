"""Publication memory is bounded by row count, not by provision body bytes.

Each regression test runs one publication path over the same number of rows
with small and with large bodies, under ``tracemalloc``. The streaming path's
peak may grow by a few bodies (one row is parsed at a time) but not by the
total body bytes, which the pre-streaming implementation held; the test also
runs that implementation to show the bound would catch a regression.

R2 artifact verification is exercised with a body that refuses an unsized
``read()``, and a differential test checks that streamed verification stages,
reuses and rejects exactly the objects whole-object verification did.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import tracemalloc
import urllib.parse
from collections.abc import Callable, Iterator
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from botocore.exceptions import ClientError
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.supabase as supabase
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.projection_digest import provision_projection_sha256
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.corpus.supabase import iter_supabase_rows, load_provisions_to_supabase
from axiom_corpus.release.manifest import (
    ReleaseManifestError,
    _provision_snapshot_projection,
    content_addressed_r2_key,
)
from axiom_corpus.release.publication import _ArtifactEntry, _stage_one_artifact
from tests._reference_publication import (
    _reference_iter_supabase_rows,
    _reference_load_provision_snapshot,
    _reference_load_provisions_to_supabase,
    _reference_provision_projection_sha256,
    _reference_stage_one_artifact,
    _reference_validate_release,
)

_ROWS = 48
_SMALL_BODY = 1024
_LARGE_BODY = 1024 * 1024
_SCOPE = ("us", "regulation", "2026-05-01")


def _peak(call: Callable[[], object]) -> int:
    tracemalloc.start()
    try:
        call()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def _records(body_bytes: int) -> Iterator[ProvisionRecord]:
    for index in range(_ROWS):
        yield ProvisionRecord(
            jurisdiction=_SCOPE[0],
            document_class=_SCOPE[1],
            citation_path=f"us/regulation/7/{index}",
            version=_SCOPE[2],
            body=("x" * body_bytes) + str(index),
            source_path=f"sources/{_SCOPE[0]}/{_SCOPE[1]}/{_SCOPE[2]}/title-7.xml",
            source_as_of=_SCOPE[2],
            expression_date=_SCOPE[2],
        )


def _write_scope(root: Path, body_bytes: int) -> Path:
    jurisdiction, document_class, version = _SCOPE
    source = root / "sources" / jurisdiction / document_class / version / "title-7.xml"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"<title n='7'/>")
    provisions = root / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
    provisions.parent.mkdir(parents=True)
    with provisions.open("w") as handle:
        for record in _records(body_bytes):
            handle.write(json.dumps(record.to_mapping(), sort_keys=True) + "\n")
    inventory = root / "inventory" / jurisdiction / document_class / f"{version}.json"
    inventory.parent.mkdir(parents=True)
    items = [
        {
            "citation_path": f"us/regulation/7/{index}",
            "source_path": f"sources/{jurisdiction}/{document_class}/{version}/title-7.xml",
            "sha256": hashlib.sha256(b"<title n='7'/>").hexdigest(),
        }
        for index in range(_ROWS)
    ]
    inventory.write_text(json.dumps({"items": items}, indent=2, sort_keys=True))
    coverage = root / "coverage" / jurisdiction / document_class / f"{version}.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text(
        json.dumps(
            {
                "complete": True,
                "source_count": _ROWS,
                "provision_count": _ROWS,
                "matched_count": _ROWS,
            }
        )
    )
    return provisions


def _assert_bounded(
    small: int, large: int, reference_large: int, *, bodies_in_flight: int = 8
) -> None:
    body_growth = _LARGE_BODY - _SMALL_BODY
    # A handful of bodies in flight at once, never the scope's total.
    assert large - small < bodies_in_flight * body_growth, (small, large)
    assert bodies_in_flight < _ROWS // 2
    # The whole-artifact implementation holds at least every body once, so
    # this bound distinguishes the two.
    assert reference_large > _ROWS * body_growth, reference_large


def test_projection_digest_memory_does_not_grow_with_body_bytes() -> None:
    def digest(builder: Callable[..., str], body_bytes: int) -> Callable[[], object]:
        return lambda: builder(iter_supabase_rows(_records(body_bytes)))

    small = _peak(digest(provision_projection_sha256, _SMALL_BODY))
    large = _peak(digest(provision_projection_sha256, _LARGE_BODY))
    reference = _peak(
        lambda: _reference_provision_projection_sha256(
            _reference_iter_supabase_rows(_records(_LARGE_BODY))
        )
    )
    _assert_bounded(small, large, reference)


def test_release_validation_memory_does_not_grow_with_body_bytes() -> None:
    release = ReleaseManifest(
        name="us-bounded-2026-05-01",
        scopes=(ReleaseScope(*_SCOPE),),
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
    )
    peaks = {}
    for body_bytes in (_SMALL_BODY, _LARGE_BODY):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_scope(root, body_bytes)
            report = validate_release(root, release)
            assert report.to_mapping() == _reference_validate_release(root, release).to_mapping()
            assert report.ok
            peaks[body_bytes] = _peak(lambda root=root: validate_release(root, release))
            if body_bytes == _LARGE_BODY:
                reference = _peak(lambda root=root: _reference_validate_release(root, release))
    _assert_bounded(peaks[_SMALL_BODY], peaks[_LARGE_BODY], reference)


def test_release_content_projection_memory_does_not_grow_with_body_bytes() -> None:
    peaks = {}
    for body_bytes in (_SMALL_BODY, _LARGE_BODY):
        with tempfile.TemporaryDirectory() as directory:
            provisions = _write_scope(Path(directory), body_bytes)
            data = provisions.read_bytes()
            expected = {
                "expected_sha256": hashlib.sha256(data).hexdigest(),
                "expected_bytes": len(data),
                "expected_rows": _ROWS,
            }
            del data
            peaks[body_bytes] = _peak(
                lambda provisions=provisions, expected=expected: _provision_snapshot_projection(
                    provisions, **expected
                )
            )
            if body_bytes == _LARGE_BODY:
                reference = _peak(
                    lambda provisions=provisions, expected=expected: _reference_load_provision_snapshot(
                        provisions, **expected
                    )
                )
    # The snapshot keeps up to 8 MB in memory, copied once as it spills to
    # disk; parsing then holds a few bodies at a time.
    spool = 8 * 1024 * 1024
    assert peaks[_LARGE_BODY] - peaks[_SMALL_BODY] < 2 * spool + 8 * _LARGE_BODY, peaks
    assert reference > _ROWS * (_LARGE_BODY - _SMALL_BODY), reference


def _discarding_supabase(inserted: list[int]) -> Callable[..., Any]:
    """An empty ``corpus.provisions`` that counts inserted rows and keeps none."""

    class _Response:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self._payload

    def urlopen(req: Any, timeout: float) -> _Response:
        method = req.get_method()
        if method == "GET":
            assert "doc_type" in urllib.parse.urlparse(req.full_url).query
            return _Response(b"[]")
        assert method == "POST"
        inserted.append(len(json.loads(req.data)))
        return _Response(b"")

    return urlopen


def test_provision_staging_memory_does_not_grow_with_body_bytes() -> None:
    def stage(loader: Callable[..., Any], body_bytes: int) -> Callable[[], object]:
        def run() -> object:
            inserted: list[int] = []
            with mock.patch.object(
                supabase.urllib.request, "urlopen", _discarding_supabase(inserted)
            ):
                report = loader(
                    _records(body_bytes),
                    service_key="service",
                    supabase_url="https://example.supabase.co",
                    chunk_size=2,
                )
            assert sum(inserted) == _ROWS == report.rows_loaded
            return report

        return run

    small = _peak(stage(load_provisions_to_supabase, _SMALL_BODY))
    large = _peak(stage(load_provisions_to_supabase, _LARGE_BODY))
    reference = _peak(stage(_reference_load_provisions_to_supabase, _LARGE_BODY))
    # An insert request carries chunk_size=2 rows as rows, JSON text and
    # bytes at once; that is the only body-sized working set.
    _assert_bounded(small, large, reference, bodies_in_flight=16)


# --- R2 ----------------------------------------------------------------------


class _SizedReadsOnly:
    """An R2 body that fails an unsized ``read()``, as a streaming reader must avoid."""

    def __init__(self, path: Path) -> None:
        self._handle = path.open("rb")

    def read(self, amt: int | None = None) -> bytes:
        if amt is None:
            raise AssertionError("artifact object read whole")
        return self._handle.read(amt)

    def close(self) -> None:
        self._handle.close()


class _DiskR2:
    """Content-addressed objects kept on disk, served and stored in chunks."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.uploads: list[str] = []

    def _path(self, key: str) -> Path:
        return self.directory / key.replace("/", "_")

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        path = self._path(kwargs["Key"])
        if not path.exists():
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": _SizedReadsOnly(path)}

    def put_object(self, **kwargs: Any) -> None:
        path = self._path(kwargs["Key"])
        if path.exists():
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        with path.open("wb") as target:
            for chunk in iter(lambda: kwargs["Body"].read(1024 * 1024), b""):
                target.write(chunk)
        self.uploads.append(kwargs["Key"])


def _entry(path: Path, data_size: int, digest: str) -> _ArtifactEntry:
    return _ArtifactEntry(
        index=0,
        path_value="data/corpus/provisions/us/regulation/2026-05-01.jsonl",
        path=path,
        key=content_addressed_r2_key(digest),
        sha256=digest,
        size=data_size,
    )


def test_r2_artifact_verification_streams_and_is_bounded(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.jsonl"
    size = 32 * 1024 * 1024
    with artifact.open("wb") as handle:
        for index in range(size // (1024 * 1024)):
            handle.write(bytes([index]) * (1024 * 1024))
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    store = tmp_path / "r2"
    store.mkdir()
    client = _DiskR2(store)

    uploaded_peak = _peak(
        lambda: _stage_one_artifact(client, bucket="axiom-corpus", entry=_entry(artifact, size, digest))
    )
    reused_peak = _peak(
        lambda: _stage_one_artifact(client, bucket="axiom-corpus", entry=_entry(artifact, size, digest))
    )

    assert client.uploads == [content_addressed_r2_key(digest)]
    # The local snapshot holds 8 MB before spilling; reads are 1 MB chunks.
    assert uploaded_peak < 12 * 1024 * 1024, uploaded_peak
    assert reused_peak < 12 * 1024 * 1024, reused_peak
    with pytest.raises(AssertionError, match="read whole"):
        _reference_stage_one_artifact(
            client, bucket="axiom-corpus", entry=_entry(artifact, size, digest)
        )


class _ScriptedR2:
    """An in-memory R2 whose existing object and write behaviour are scripted."""

    def __init__(self, existing: bytes | None, put_behaviour: str, expected: bytes) -> None:
        self.objects: dict[str, bytes] = {}
        self.existing = existing
        self.put_behaviour = put_behaviour
        self.expected = expected
        self.puts = 0

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        key = kwargs["Key"]
        if key not in self.objects:
            if self.existing is None:
                raise ClientError({"Error": {"Code": "404"}}, "GetObject")
            self.objects[key] = self.existing
        return {"Body": BytesIO(self.objects[key])}

    def put_object(self, **kwargs: Any) -> None:
        self.puts += 1
        key = kwargs["Key"]
        payload = kwargs["Body"].read()
        behaviour = self.put_behaviour
        if behaviour == "discard":
            return
        if behaviour == "conflict-then-write" and self.puts == 1:
            raise ClientError(
                {"Error": {"Code": "409"}, "ResponseMetadata": {"HTTPStatusCode": 409}},
                "PutObject",
            )
        if behaviour.startswith("race-"):
            self.objects[key] = self.expected if behaviour == "race-identical" else b"raced"
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )
        if behaviour == "always-conflict":
            raise ClientError({"Error": {"Code": "409"}}, "PutObject")
        self.objects[key] = payload


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    content=st.binary(max_size=64),
    existing=st.sampled_from(["absent", "identical", "longer", "same-size-corrupt", "empty"]),
    put_behaviour=st.sampled_from(
        ["write", "discard", "conflict-then-write", "race-identical", "race-corrupt", "always-conflict"]
    ),
    local=st.sampled_from(["intact"] * 4 + ["tampered"]),
)
def test_streamed_r2_staging_matches_whole_object_staging(
    content: bytes, existing: str, put_behaviour: str, local: str
) -> None:
    digest = hashlib.sha256(content).hexdigest()
    remote = {
        "absent": None,
        "identical": content,
        "longer": content + b"!",
        "same-size-corrupt": bytes(len(content)) if content != bytes(len(content)) else b"x" * len(content),
        "empty": b"",
    }[existing]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "artifact"
        path.write_bytes(content if local == "intact" else content + b"tamper")

        def run(stage: Callable[..., object]) -> tuple[object, dict[str, bytes], int]:
            client = _ScriptedR2(remote, put_behaviour, content)
            try:
                outcome: object = ("ok", stage(client, bucket="axiom-corpus", entry=_entry(path, len(content), digest)))
            except (ReleaseManifestError, ClientError) as exc:
                outcome = ("raised", type(exc), str(exc))
            return outcome, client.objects, client.puts

        expected = run(_reference_stage_one_artifact)
        outcome = expected[0]
        if outcome[0] == "ok":  # type: ignore[index]
            event(f"ok uploaded={outcome[1].uploaded}")  # type: ignore[index]
        else:
            event(f"raised {str(outcome[2])[:40]}")  # type: ignore[index]
        assert run(_stage_one_artifact) == expected
