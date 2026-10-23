"""Transient R2 read errors: bounded retries that never weaken verification.

On 2026-10-23 R2 answered CI fetches with ``ServiceUnavailable: Reduce your
rate of simultaneous reads on the same object`` (GetObject) and ``429 Too Many
Requests`` (HeadObject); one failed object failed the whole job. Invariants,
exercised as properties with Hypothesis alongside example tests:

1. fidelity: under any sequence of transient failures, before the body or in
   the middle of it, a fetch places exactly the locked bytes or nothing; bytes
   that do not hash to the lock are refused, never retried into acceptance;
2. bounded: one object gets at most ``RetryPolicy.attempts`` requests, its
   resumes included; an error that is not transient (a missing object, a
   refusal, wrong bytes, a TLS failure) gets exactly one;
3. backoff: the wait after failure ``n`` lies in ``[b / 2, b]`` with
   ``b = min(max_delay, base_delay * 2 ** (n - 1))``, or, with a
   ``Retry-After``, in ``[r, r + base_delay]`` with ``r`` that value capped at
   ``max_delay``;
4. exclusion: no more than ``reads_per_object`` reads of one key run at once,
   and every read slot is freed after success, failure, early close or
   exhaustion (a later read of the key never waits forever);
5. order: the fetch, verify and push commands read every selected entry once,
   in a random order.
"""

from __future__ import annotations

import hashlib
import http.client
import subprocess
import threading
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
import urllib3
from botocore.awsrequest import AWSResponse
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    IncompleteReadError,
    ReadTimeoutError,
    ResponseStreamingError,
    SSLError,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from urllib3.response import HTTPResponse

from axiom_corpus.corpus import corpus_cli
from axiom_corpus.corpus.cli import main as cli_main
from axiom_corpus.corpus.content_store import (
    ContentStoreError,
    R2ObjectStore,
    R2UnavailableError,
    RetryPolicy,
    content_key,
    ensure_cached,
    is_transient,
    materialize,
)
from axiom_corpus.corpus.corpus_locks import CORPUS_BASE, CorpusLock, LockEntry, write_lock
from axiom_corpus.corpus.r2 import R2Config, make_r2_client

THROTTLED = "Reduce your rate of simultaneous reads on the same object."


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(data: bytes, name: str = "v1") -> LockEntry:
    return LockEntry(
        path=f"{CORPUS_BASE}/provisions/us/statute/{name}.jsonl", sha256=_sha(data), size=len(data)
    )


def _client_error(
    code: str, status: int, operation: str = "GetObject", headers: dict[str, str] | None = None
) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": THROTTLED},
            "ResponseMetadata": {"HTTPStatusCode": status, "HTTPHeaders": headers or {}},
        },
        operation,
    )


def _throttle() -> ClientError:
    return _client_error("ServiceUnavailable", 503)


class _Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _policy(attempts: int = 5, jitter: float = 0.0, **kwargs: Any) -> tuple[RetryPolicy, _Sleeps]:
    sleeps = _Sleeps()
    return RetryPolicy(attempts=attempts, sleep=sleeps, jitter=lambda: jitter, **kwargs), sleeps


class _Body:
    """A response body that raises ``fail_after`` bytes in, if asked to."""

    def __init__(self, data: bytes, fail_after: int | None = None, error: BaseException | None = None):
        self._stream = BytesIO(data)
        self._fail_after = fail_after
        self._error = error or ConnectionResetError(104, "Connection reset by peer")
        self.closed = False

    def read(self, amount: int = -1) -> bytes:
        if self._fail_after is not None:
            if self._stream.tell() >= self._fail_after:
                raise self._error
            amount = min(amount, self._fail_after - self._stream.tell())
        return self._stream.read(amount)

    def close(self) -> None:
        self.closed = True


class ScriptedR2:
    """An S3 client subset whose GetObject/HeadObject answers follow a script.

    Each script item is an exception to raise, ``("body", fail_after)`` for
    the object's body breaking ``fail_after`` bytes into this response, or
    ``"ok"``. Once the script runs out every request succeeds. Ranged
    requests are honoured unless ``honour_range`` is False.
    """

    def __init__(self, objects: dict[str, bytes], script: list[Any] | None = None, *, honour_range: bool = True):
        self.objects = objects
        self.script = list(script or [])
        self.honour_range = honour_range
        self.gets: list[dict[str, Any]] = []
        self.heads: list[str] = []
        self._lock = threading.Lock()

    def _next(self) -> Any:
        with self._lock:
            return self.script.pop(0) if self.script else "ok"

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.gets.append(kwargs)
        step = self._next()
        if isinstance(step, BaseException):
            raise step
        key = kwargs["Key"]
        if key not in self.objects:
            raise _client_error("NoSuchKey", 404)
        data = self.objects[key]
        fail_after = step[1] if isinstance(step, tuple) else None
        start = 0
        response: dict[str, Any] = {}
        if "Range" in kwargs and self.honour_range:
            start = int(kwargs["Range"].removeprefix("bytes=").removesuffix("-"))
            response["ContentRange"] = f"bytes {start}-{len(data) - 1}/{len(data)}"
        response["Body"] = _Body(data[start:], fail_after)
        return response

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        self.heads.append(kwargs["Key"])
        step = self._next()
        if isinstance(step, BaseException):
            raise step
        if kwargs["Key"] not in self.objects:
            raise _client_error("404", 404, "HeadObject")
        return {"ContentLength": len(self.objects[kwargs["Key"]])}


def _store(client: Any, policy: RetryPolicy, **kwargs: Any) -> R2ObjectStore:
    return R2ObjectStore(bucket="axiom-corpus", client=client, legacy_path_keys=False, retry=policy, **kwargs)


# --------------------------------------------------------------------------- classification


@pytest.mark.parametrize(
    "error",
    [
        _client_error("ServiceUnavailable", 503),
        _client_error("SlowDown", 503),
        _client_error("429", 429, "HeadObject"),
        _client_error("TooManyRequests", 429),
        _client_error("InternalError", 500),
        _client_error("RequestTimeout", 400),
        _client_error("Unknown", 502),
        _client_error("Unknown", 504),
        ConnectionResetError(104, "Connection reset by peer"),
        BrokenPipeError(32, "Broken pipe"),
        TimeoutError("timed out"),
        http.client.IncompleteRead(b"partial", 10),
        EndpointConnectionError(endpoint_url="https://r2.example"),
        ConnectTimeoutError(endpoint_url="https://r2.example"),
        ReadTimeoutError(endpoint_url="https://r2.example"),
        ResponseStreamingError(error="Connection broken: IncompleteRead"),
        IncompleteReadError(actual_bytes=1, expected_bytes=2),
    ],
)
def test_throttling_server_faults_timeouts_and_resets_are_transient(error: BaseException) -> None:
    assert is_transient(error)


@pytest.mark.parametrize(
    "error",
    [
        _client_error("NoSuchKey", 404),
        _client_error("404", 404, "HeadObject"),
        _client_error("AccessDenied", 403),
        _client_error("InvalidRange", 416),
        _client_error("InvalidArgument", 400),
        KeyError("objects/sha256/00/missing"),
        ContentStoreError("refusing bytes for abc"),
        R2UnavailableError("gave up"),
        SSLError(endpoint_url="https://r2.example", error="certificate verify failed"),
        ValueError("anything else"),
        PermissionError(13, "Permission denied"),
    ],
)
def test_missing_refused_wrong_and_tls_errors_are_not_transient(error: BaseException) -> None:
    assert not is_transient(error)


def test_a_missing_object_is_never_transient_whatever_status_comes_with_it() -> None:
    assert not is_transient(_client_error("NoSuchKey", 503))
    assert not is_transient(_client_error("NotFound", 500, "HeadObject"))


# --------------------------------------------------------------------------- GetObject


def test_a_read_that_is_throttled_n_times_then_served_succeeds(tmp_path: Path) -> None:
    data = b'{"id": "us/statute/1"}\n'
    entry = _entry(data)
    policy, sleeps = _policy(attempts=5)
    client = ScriptedR2({content_key(entry.sha256): data}, [_throttle()] * 3)
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert report.ok, report.failed
    assert (tmp_path / entry.path).read_bytes() == data
    assert len(client.gets) == 4
    assert sleeps.calls == [0.5, 1.0, 2.0]  # jitter 0: half of 1, 2, 4 seconds


def test_a_read_that_is_always_throttled_fails_after_the_cap_and_places_nothing(tmp_path: Path) -> None:
    data = b"bytes R2 never serves"
    entry = _entry(data)
    policy, sleeps = _policy(attempts=4)
    client = ScriptedR2({content_key(entry.sha256): data}, [_throttle()] * 100)
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert set(report.failed) == {entry.path}
    assert "gave up after 4 attempts" in report.failed[entry.path]
    assert THROTTLED in report.failed[entry.path]
    assert len(client.gets) == 4 and len(sleeps.calls) == 3
    assert not (tmp_path / entry.path).exists()


def test_wrong_bytes_are_refused_once_and_never_retried_into_acceptance(tmp_path: Path) -> None:
    data = b"the locked bytes"
    entry = _entry(data)
    policy, sleeps = _policy(attempts=5)
    client = ScriptedR2({content_key(entry.sha256): b"other bytes, same key"})
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert set(report.failed) == {entry.path}
    assert "refusing bytes" in report.failed[entry.path]
    assert len(client.gets) == 1 and sleeps.calls == []
    assert not (tmp_path / entry.path).exists()


def test_a_missing_object_is_not_retried(tmp_path: Path) -> None:
    entry = _entry(b"nowhere")
    policy, sleeps = _policy()
    client = ScriptedR2({})
    with pytest.raises(ContentStoreError, match="no source holds it"):
        ensure_cached(entry, _cache(tmp_path), [_store(client, policy)])
    assert len(client.gets) == 1 and sleeps.calls == []


def test_a_refused_read_is_not_retried(tmp_path: Path) -> None:
    data = b"forbidden"
    entry = _entry(data)
    policy, sleeps = _policy()
    client = ScriptedR2({content_key(entry.sha256): data}, [_client_error("AccessDenied", 403)])
    with pytest.raises(ContentStoreError, match="AccessDenied"):
        ensure_cached(entry, _cache(tmp_path), [_store(client, policy)])
    assert len(client.gets) == 1 and sleeps.calls == []


def test_a_retry_after_header_sets_the_wait_capped_at_max_delay(tmp_path: Path) -> None:
    data = b"retry after"
    entry = _entry(data)
    policy, sleeps = _policy(attempts=5, max_delay=30.0)
    later = format_datetime(datetime.now(UTC) + timedelta(seconds=120), usegmt=True)
    client = ScriptedR2(
        {content_key(entry.sha256): data},
        [
            _client_error("ServiceUnavailable", 503, headers={"retry-after": "7"}),
            _client_error("SlowDown", 503, headers={"Retry-After": "1000"}),
            _client_error("TooManyRequests", 429, headers={"retry-after": later}),
            _client_error("ServiceUnavailable", 503, headers={"retry-after": "soon"}),
        ],
    )
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert report.ok
    # 7 s as asked; 1000 s and a date two minutes away capped at 30 s; an
    # unreadable value falls back to backoff (half of 2 ** 3 s at jitter 0).
    assert sleeps.calls == [7.0, 30.0, 30.0, 4.0]


# --------------------------------------------------------------------------- mid-body


def test_a_connection_reset_mid_body_resumes_from_the_next_byte(tmp_path: Path) -> None:
    data = bytes(range(256)) * 50
    entry = _entry(data)
    policy, sleeps = _policy()
    client = ScriptedR2({content_key(entry.sha256): data}, [("body", 1000), ("body", 3000)])
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert report.ok, report.failed
    assert (tmp_path / entry.path).read_bytes() == data
    assert [get.get("Range") for get in client.gets] == [None, "bytes=1000-", "bytes=4000-"]
    assert len(sleeps.calls) == 2


def test_a_reset_before_the_first_byte_retries_the_whole_object(tmp_path: Path) -> None:
    data = b"short object"
    entry = _entry(data)
    policy, _sleeps = _policy()
    client = ScriptedR2({content_key(entry.sha256): data}, [("body", 0)])
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert report.ok and (tmp_path / entry.path).read_bytes() == data
    assert [get.get("Range") for get in client.gets] == [None, None]


def test_a_wrong_resumed_tail_is_refused_and_not_retried(tmp_path: Path) -> None:
    data = b"A" * 4000
    entry = _entry(data)
    policy, sleeps = _policy()
    tampered = b"A" * 1000 + b"B" * 3000
    # The first 1000 bytes served match the lock; the resumed tail does not.
    client = ScriptedR2({content_key(entry.sha256): tampered}, [("body", 1000)])
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert "refusing bytes" in report.failed[entry.path]
    assert len(client.gets) == 2 and len(sleeps.calls) == 1
    assert not (tmp_path / entry.path).exists()


def test_a_resume_the_server_does_not_range_fails_closed(tmp_path: Path) -> None:
    data = b"C" * 4000
    entry = _entry(data)
    policy, _sleeps = _policy()
    client = ScriptedR2({content_key(entry.sha256): data}, [("body", 1000)], honour_range=False)
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert "did not resume" in report.failed[entry.path]
    assert len(client.gets) == 2
    assert not (tmp_path / entry.path).exists()


def test_mid_body_failures_share_the_objects_attempt_budget(tmp_path: Path) -> None:
    data = b"D" * 4000
    entry = _entry(data)
    policy, _sleeps = _policy(attempts=3)
    client = ScriptedR2(
        {content_key(entry.sha256): data},
        [_throttle(), ("body", 100), ("body", 100)],
    )
    report = materialize(tmp_path, [entry], None, [_store(client, policy)])
    assert "gave up after 3 attempts" in report.failed[entry.path]
    assert len(client.gets) == 3


# --------------------------------------------------------------------------- HeadObject


def test_head_retries_429_then_answers() -> None:
    data = b"present"
    policy, sleeps = _policy()
    client = ScriptedR2({content_key(_sha(data)): data}, [_client_error("429", 429, "HeadObject")] * 2)
    assert _store(client, policy).has(_sha(data), len(data))
    assert len(client.heads) == 3 and len(sleeps.calls) == 2


def test_head_that_is_always_throttled_raises_after_the_cap() -> None:
    data = b"present"
    policy, _sleeps = _policy(attempts=3)
    client = ScriptedR2({content_key(_sha(data)): data}, [_client_error("429", 429, "HeadObject")] * 10)
    with pytest.raises(R2UnavailableError, match="gave up after 3 attempts"):
        _store(client, policy).has(_sha(data))
    assert len(client.heads) == 3


def test_head_of_a_missing_object_is_not_retried() -> None:
    policy, sleeps = _policy()
    client = ScriptedR2({})
    assert not _store(client, policy).has("0" * 64)
    assert len(client.heads) == 1 and sleeps.calls == []


# --------------------------------------------------------------------------- one read per object


class _ConcurrencyProbe(ScriptedR2):
    """Counts reads of each key that are in flight, from request to body close."""

    def __init__(self, objects: dict[str, bytes]):
        super().__init__(objects)
        self.active: Counter[str] = Counter()
        self.peak: Counter[str] = Counter()
        self.peak_total = 0
        self._probe = threading.Lock()

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        key = kwargs["Key"]
        with self._probe:
            self.active[key] += 1
            self.peak[key] = max(self.peak[key], self.active[key])
            self.peak_total = max(self.peak_total, sum(self.active.values()))
        time.sleep(0.05)  # hold the read open long enough for others to collide
        response = super().get_object(**kwargs)
        body = response["Body"]
        close = body.close

        def closing() -> None:
            with self._probe:
                if not body.closed:
                    self.active[key] -= 1
            close()

        body.close = closing
        return response


def test_reads_of_one_object_never_overlap_but_different_objects_do(tmp_path: Path) -> None:
    shared = b"bytes a successor scope repeats"
    others = [f"distinct object {i}".encode() for i in range(12)]
    entries = [_entry(shared, f"copy-{i}") for i in range(12)] + [
        _entry(data, f"other-{i}") for i, data in enumerate(others)
    ]
    objects = {content_key(_sha(d)): d for d in [shared, *others]}
    policy, _sleeps = _policy()
    # Control: without the cap the probe sees the copies' reads overlap.
    uncapped = _ConcurrencyProbe(objects)
    store = _store(uncapped, policy, reads_per_object=len(entries))
    assert materialize(tmp_path / "uncapped", entries, None, [store], workers=8).ok
    assert uncapped.peak[content_key(_sha(shared))] > 1
    client = _ConcurrencyProbe(objects)
    report = materialize(tmp_path / "capped", entries, None, [_store(client, policy)], workers=8)
    assert report.ok, report.failed
    assert max(client.peak.values()) == 1
    assert client.peak_total > 1


def _open_within(store: R2ObjectStore, entry: LockEntry, seconds: float = 5.0) -> Any:
    result: list[Any] = []
    thread = threading.Thread(target=lambda: result.append(store.open(entry)), daemon=True)
    thread.start()
    thread.join(seconds)
    assert result, "a later read of the key waited for a slot nobody frees"
    return result[0]


def test_every_way_a_read_ends_frees_its_slot() -> None:
    data = b"slot"
    entry = _entry(data)
    policy, _sleeps = _policy(attempts=2)
    key = content_key(entry.sha256)
    # Closed before the first read.
    store = _store(ScriptedR2({key: data}), policy)
    store.open(entry).close()
    _open_within(store, entry).close()
    # Read to the end.
    chunks = _open_within(store, entry)
    assert b"".join(chunks) == data
    _open_within(store, entry).close()
    # A body error that is not transient.
    broken = _store(ScriptedR2({key: data}, [("body", 1)]), policy)
    stream = broken.open(entry)
    stream._body._error = ValueError("not transient")
    with pytest.raises(ValueError):
        list(stream)
    _open_within(broken, entry).close()
    # Exhausted retries, before a body and mid-body.
    for script in ([_throttle(), _throttle()], [("body", 1), _throttle()]):
        store = _store(ScriptedR2({key: data}, script), policy)
        with pytest.raises(R2UnavailableError):
            stream = store.open(entry)
            list(stream)
        _open_within(store, entry).close()
    # Missing: no body, no slot kept.
    store = _store(ScriptedR2({}), policy)
    assert store.open(entry) is None
    assert _open_within(store, entry) is None


def test_a_stream_dropped_unclosed_frees_its_slot_when_collected() -> None:
    data = b"dropped"
    entry = _entry(data)
    policy, _sleeps = _policy()
    store = _store(ScriptedR2({content_key(entry.sha256): data}), policy)
    stream = store.open(entry)
    del stream
    _open_within(store, entry).close()


# --------------------------------------------------------------------------- properties


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    data=st.binary(min_size=1, max_size=3000),
    steps=st.lists(
        st.one_of(
            st.just("throttle"),
            st.just("reset"),
            st.just("timeout"),
            st.tuples(st.just("break"), st.integers(min_value=0, max_value=3000)),
        ),
        max_size=10,
    ),
    attempts=st.integers(min_value=1, max_value=8),
)
def test_any_transient_failures_place_the_locked_bytes_or_nothing(
    tmp_path_factory: pytest.TempPathFactory, data: bytes, steps: list[Any], attempts: int
) -> None:
    """Invariants 1 and 2 over arbitrary failure scripts."""
    entry = _entry(data)
    script: list[Any] = []
    for step in steps:
        if step == "throttle":
            script.append(_throttle())
        elif step == "reset":
            script.append(ConnectionResetError(104, "reset"))
        elif step == "timeout":
            script.append(ReadTimeoutError(endpoint_url="https://r2.example"))
        else:
            script.append(("body", step[1]))
    policy, _sleeps = _policy(attempts=attempts)
    client = ScriptedR2({content_key(entry.sha256): data}, script)
    repo = tmp_path_factory.mktemp("repo")
    report = materialize(repo, [entry], None, [_store(client, policy)])
    target = repo / entry.path
    if report.ok:
        assert target.read_bytes() == data
    else:
        assert not target.exists()
        assert "gave up after" in report.failed[entry.path]
    assert len(client.gets) <= attempts


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    data=st.binary(min_size=1, max_size=2000),
    corrupt_at=st.integers(min_value=0, max_value=1999),
    break_at=st.one_of(st.none(), st.integers(min_value=0, max_value=2000)),
)
def test_bytes_that_differ_from_the_lock_are_never_placed(
    tmp_path_factory: pytest.TempPathFactory, data: bytes, corrupt_at: int, break_at: int | None
) -> None:
    """Invariant 1: a corrupted object, resumed or not, is refused."""
    index = corrupt_at % len(data)
    served = data[:index] + bytes([data[index] ^ 0xFF]) + data[index + 1 :]
    entry = _entry(data)
    script = [] if break_at is None else [("body", break_at)]
    policy, _sleeps = _policy()
    client = ScriptedR2({content_key(entry.sha256): served}, script)
    repo = tmp_path_factory.mktemp("repo")
    report = materialize(repo, [entry], None, [_store(client, policy)])
    assert not report.ok and not (repo / entry.path).exists()


@given(
    failures=st.integers(min_value=1, max_value=64),
    base=st.floats(min_value=0.01, max_value=10.0),
    cap=st.floats(min_value=0.01, max_value=120.0),
    jitter=st.floats(min_value=0.0, max_value=1.0),
)
def test_backoff_lies_between_half_and_all_of_the_capped_exponential(
    failures: int, base: float, cap: float, jitter: float
) -> None:
    """Invariant 3 without Retry-After."""
    policy = RetryPolicy(base_delay=base, max_delay=cap, jitter=lambda: jitter)
    bound = min(cap, base * 2.0 ** min(failures - 1, 32))
    delay = policy.delay(failures, _throttle())
    assert bound / 2 - 1e-9 <= delay <= bound + 1e-9


@given(
    retry_after=st.floats(min_value=0.0, max_value=1e6, allow_nan=False),
    base=st.floats(min_value=0.01, max_value=10.0),
    cap=st.floats(min_value=0.01, max_value=120.0),
    jitter=st.floats(min_value=0.0, max_value=1.0),
)
def test_retry_after_is_honoured_up_to_the_cap(retry_after: float, base: float, cap: float, jitter: float) -> None:
    """Invariant 3 with Retry-After."""
    policy = RetryPolicy(base_delay=base, max_delay=cap, jitter=lambda: jitter)
    error = _client_error("SlowDown", 503, headers={"retry-after": repr(retry_after)})
    wait = min(cap, retry_after)
    assert wait - 1e-9 <= policy.delay(1, error) <= wait + base + 1e-9


@given(st.lists(st.integers(), max_size=200))
def test_spread_is_a_permutation(values: list[int]) -> None:
    """Invariant 5."""
    entries = [_entry(str(value).encode(), f"e{i}") for i, value in enumerate(values)]
    spread = corpus_cli._spread(entries)
    assert sorted(spread, key=lambda e: e.path) == sorted(entries, key=lambda e: e.path)


def test_fetch_verify_and_push_read_r2_in_the_shuffled_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariant 5 through the CLI: each command reads what ``_spread`` returned, once each."""
    repo = tmp_path / "repo"
    (repo / "src" / "axiom_corpus").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    scope = ("nz", "statute", "2026-07-10")
    files = {
        f"{CORPUS_BASE}/{kind}/nz/statute/2026-07-10.{suffix}": f"{kind} bytes".encode()
        for kind, suffix in (("inventory", "json"), ("provisions", "jsonl"), ("coverage", "json"))
    }
    entries = [LockEntry(path, _sha(data), len(data)) for path, data in files.items()]
    write_lock(repo, CorpusLock.from_entries(scope, entries))
    client = ScriptedR2({content_key(_sha(data)): data for data in files.values()})
    store = _store(client, _policy()[0])
    monkeypatch.setattr(corpus_cli, "_sources", lambda *_args, **_kwargs: [store])
    monkeypatch.setattr(corpus_cli, "_remote", lambda _workers: store)
    orders: list[list[str]] = []

    def reverse(items: list[Any]) -> None:
        items.reverse()
        orders.append([content_key(item.sha256) for item in items])

    monkeypatch.setattr(corpus_cli.random, "shuffle", reverse)
    argv = ["--repo", str(repo), "--workers", "1"]
    assert cli_main(["corpus", "fetch", *argv, "--all", "--no-cache", "--json"]) == 0
    assert all((repo / path).read_bytes() == data for path, data in files.items())
    assert cli_main(["corpus", "verify", *argv, "--remote"]) == 0
    assert cli_main(["corpus", "push", *argv, "--all", "--dry-run"]) == 0
    natural = [content_key(entry.sha256) for entry in sorted(entries, key=lambda e: e.path)]
    assert len(orders) == 3 and all(sorted(order) == sorted(natural) for order in orders)
    assert [get["Key"] for get in client.gets] == orders[0] != natural
    assert client.heads == orders[1] + orders[2]


def _cache(tmp_path: Path) -> Any:
    from axiom_corpus.corpus.content_store import ContentCache

    return ContentCache(tmp_path / "cache")


# --------------------------------------------------------------------------- the real SDK
#
# The fakes above stand in for the client. These run botocore itself, with an
# in-memory transport on ``before-send``, so they count HTTP requests: the
# retry budget must bound requests, not SDK calls (review of the first draft:
# botocore's own five retries multiplied it to 48 requests).

# conftest refuses ``from_environment`` so no test reads real credentials or
# R2. The one test of its client wiring restores it with a fixture config and
# an in-memory transport, so it still cannot reach either.
_FROM_ENVIRONMENT = R2ObjectStore.__dict__["from_environment"]

R2_CONFIG = R2Config(
    bucket="axiom-corpus",
    endpoint_url="https://r2.invalid",
    access_key_id="fixture-key",
    secret_access_key="fixture-secret",
)


def _xml_error(code: str, status: int, headers: dict[str, str] | None = None) -> tuple[int, bytes, dict[str, str]]:
    body = f"<Error><Code>{code}</Code><Message>{THROTTLED}</Message></Error>".encode()
    return status, body, {"Content-Type": "application/xml", **(headers or {})}


class _BreakingRaw:
    """A response stream that drops the connection ``after`` bytes in."""

    def __init__(self, data: bytes, after: int):
        self._stream = BytesIO(data)
        self._after = after

    def read(self, amount: int | None = None) -> bytes:
        if self._stream.tell() >= self._after:
            raise urllib3.exceptions.ProtocolError("Connection broken: connection reset by peer")
        limit = self._after - self._stream.tell()
        return self._stream.read(limit if amount is None else min(amount, limit))

    def stream(self, *_args: Any, **_kwargs: Any) -> Any:
        yield self.read()

    def close(self) -> None:
        pass


class Transport:
    """Answers a real client's HTTP requests in memory and records each one.

    ``answers`` are taken in order and the last repeats: an exception to
    raise, ``(status, body, headers)``, ``"object"`` for the stored bytes
    (honouring a Range header), or ``("break", n)`` for the stored bytes
    breaking ``n`` bytes in.
    """

    def __init__(self, client: Any, data: bytes, answers: list[Any]):
        self.data = data
        self.answers = list(answers)
        self.requests: list[tuple[str, str | None]] = []
        client.meta.events.register("before-send.s3", self)

    def __call__(self, request: Any, **_kwargs: Any) -> AWSResponse:
        requested = request.headers.get("Range")
        self.requests.append((request.method, requested.decode() if isinstance(requested, bytes) else requested))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, tuple) and answer[0] != "break":
            status, body, headers = answer
            body = b"" if request.method == "HEAD" else body  # a HEAD answer has no body
            raw = HTTPResponse(body=BytesIO(body), headers=headers, status=status,
                               preload_content=False, request_method=request.method)
            return AWSResponse(request.url, status, headers, raw)
        start = 0
        status, headers = 200, {"ETag": '"fixture"'}
        if request.headers.get("Range"):
            requested = request.headers["Range"]
            requested = requested.decode() if isinstance(requested, bytes) else requested
            start = int(requested.removeprefix("bytes=").removesuffix("-"))
            status = 206
            headers["Content-Range"] = f"bytes {start}-{len(self.data) - 1}/{len(self.data)}"
        body = self.data[start:]
        headers["Content-Length"] = str(len(body))
        if request.method == "HEAD":
            empty = HTTPResponse(body=BytesIO(b""), headers=headers, status=status,
                                 preload_content=False, request_method="HEAD")
            return AWSResponse(request.url, status, headers, empty)
        raw: Any = (
            _BreakingRaw(body, answer[1]) if isinstance(answer, tuple)
            else HTTPResponse(body=BytesIO(body), headers=headers, status=status, preload_content=False)
        )
        return AWSResponse(request.url, status, headers, raw)


def _sdk_store(answers: list[Any], data: bytes, *, attempts: int = 4) -> tuple[R2ObjectStore, Transport, _Sleeps]:
    client = make_r2_client(R2_CONFIG, sdk_retries=False)
    transport = Transport(client, data, answers)
    policy, sleeps = _policy(attempts=attempts)
    return _store(client, policy), transport, sleeps


def test_the_sdk_read_client_makes_one_request_per_attempt(tmp_path: Path) -> None:
    data = b"bytes R2 keeps refusing"
    entry = _entry(data)
    store, transport, sleeps = _sdk_store([_xml_error("ServiceUnavailable", 503)], data, attempts=4)
    report = materialize(tmp_path, [entry], None, [store])
    assert "gave up after 4 attempts" in report.failed[entry.path]
    assert len(transport.requests) == 4 and len(sleeps.calls) == 3
    assert not (tmp_path / entry.path).exists()


@pytest.mark.parametrize(
    "answer",
    [
        SSLError(endpoint_url="https://r2.invalid", error="certificate verify failed"),
        _xml_error("NoSuchKey", 503),
        _xml_error("AccessDenied", 403),
        _xml_error("NoSuchKey", 404),
    ],
)
def test_the_sdk_read_client_never_retries_what_must_fail_closed(tmp_path: Path, answer: Any) -> None:
    data = b"never fetched"
    entry = _entry(data)
    store, transport, sleeps = _sdk_store([answer], data)
    report = materialize(tmp_path, [entry], None, [store])
    assert set(report.failed) == {entry.path}
    assert len(transport.requests) == 1 and sleeps.calls == []


def test_the_sdk_read_client_retries_throttling_then_reads_the_object(tmp_path: Path) -> None:
    data = bytes(range(256)) * 40
    entry = _entry(data)
    store, transport, sleeps = _sdk_store(
        [_xml_error("ServiceUnavailable", 503), _xml_error("SlowDown", 503), "object"], data
    )
    report = materialize(tmp_path, [entry], None, [store])
    assert report.ok, report.failed
    assert (tmp_path / entry.path).read_bytes() == data
    assert len(transport.requests) == 3 and len(sleeps.calls) == 2


def test_the_sdk_read_client_resumes_a_broken_body_with_a_range_request(tmp_path: Path) -> None:
    data = bytes(range(256)) * 40
    entry = _entry(data)
    store, transport, _sleeps = _sdk_store([("break", 3000), "object"], data)
    report = materialize(tmp_path, [entry], None, [store])
    assert report.ok, report.failed
    assert (tmp_path / entry.path).read_bytes() == data
    assert [rng for _method, rng in transport.requests] == [None, "bytes=3000-"]


def test_the_sdk_head_retries_429_and_counts_requests() -> None:
    data = b"present"
    client = make_r2_client(R2_CONFIG, sdk_retries=False)
    transport = Transport(client, data, [(429, b"", {}), (429, b"", {}), "object"])
    policy, _sleeps = _policy(attempts=4)
    assert _store(client, policy).has(_sha(data), len(data))
    assert [method for method, _rng in transport.requests] == ["HEAD"] * 3


def test_the_write_client_keeps_botocore_retries_and_the_transport_counts_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: the transport sees SDK retries, so the read tests above count them too."""
    monkeypatch.setattr("botocore.retries.standard.ExponentialBackoff.delay_amount", lambda self, context: 0)
    client = make_r2_client(R2_CONFIG)
    transport = Transport(client, b"", [_xml_error("ServiceUnavailable", 503)])
    with pytest.raises(ClientError):
        client.get_object(Bucket="axiom-corpus", Key="objects/sha256/00/0")
    assert len(transport.requests) == 6


def test_from_environment_reads_without_sdk_retries_and_writes_with_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("axiom_corpus.corpus.r2.load_r2_config", lambda: R2_CONFIG)
    monkeypatch.setattr(R2ObjectStore, "from_environment", _FROM_ENVIRONMENT)
    store = R2ObjectStore.from_environment(workers=2)
    assert store.client.meta.config.retries == {"total_max_attempts": 1, "mode": "standard"}
    assert store.write_client.meta.config.retries == {"mode": "standard", "total_max_attempts": 6}
    assert store.write_client is not store.client
    data = b"refused"
    transport = Transport(store.client, data, [_xml_error("ServiceUnavailable", 503)])
    store.retry = _policy(attempts=3)[0]
    with pytest.raises(R2UnavailableError, match="gave up after 3 attempts"):
        store.has(_sha(data))
    assert len(transport.requests) == 3


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    data=st.binary(min_size=1, max_size=2000),
    answers=st.lists(
        st.one_of(
            st.sampled_from([429, 500, 502, 503, 504]).map(lambda status: _xml_error("ServiceUnavailable", status)),
            st.just(ConnectionClosedError(endpoint_url="https://r2.invalid")),
            st.integers(min_value=0, max_value=2000).map(lambda n: ("break", n)),
        ),
        max_size=8,
    ),
    attempts=st.integers(min_value=1, max_value=6),
)
def test_over_the_real_sdk_requests_never_exceed_the_budget_and_bytes_are_exact(
    tmp_path_factory: pytest.TempPathFactory, data: bytes, answers: list[Any], attempts: int
) -> None:
    """Invariants 1 and 2 at the HTTP layer."""
    entry = _entry(data)
    store, transport, _sleeps = _sdk_store([*answers, "object"], data, attempts=attempts)
    repo = tmp_path_factory.mktemp("repo")
    report = materialize(repo, [entry], None, [store])
    assert len(transport.requests) <= attempts
    target = repo / entry.path
    if report.ok:
        assert target.read_bytes() == data
    else:
        assert not target.exists() and "gave up after" in report.failed[entry.path]


class _InterruptingBody(_Body):
    def close(self) -> None:
        raise KeyboardInterrupt


def test_an_interrupted_close_still_frees_the_read_slot() -> None:
    data = b"interrupted"
    entry = _entry(data)
    policy, _sleeps = _policy()

    class Client(ScriptedR2):
        def get_object(self, **kwargs: Any) -> dict[str, Any]:
            response = super().get_object(**kwargs)
            if len(self.gets) == 1:
                response["Body"] = _InterruptingBody(data)
            return response

    store = _store(Client({content_key(entry.sha256): data}), policy)
    stream = store.open(entry)
    with pytest.raises(KeyboardInterrupt):
        stream.close()
    stream.close()
    _open_within(store, entry).close()


def test_put_uses_the_write_client_and_reads_use_the_read_client(tmp_path: Path) -> None:
    data = b"uploaded once"
    path = tmp_path / "object.bin"
    path.write_bytes(data)
    reads, writes = ScriptedR2({}), _UploadableR2({})
    store = R2ObjectStore(bucket="axiom-corpus", client=reads, write_client_factory=lambda: writes,
                          legacy_path_keys=False, retry=_policy()[0])
    assert store.put(path, sha256=_sha(data), size=len(data))
    assert writes.objects == {content_key(_sha(data)): data} and not reads.gets
    reads.objects = dict(writes.objects)
    assert store.has(_sha(data), len(data)) and reads.heads and not writes.heads


class _UploadableR2(ScriptedR2):
    """ScriptedR2 plus R2's conditional PutObject."""

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        body = kwargs["Body"]
        payload = body.read() if hasattr(body, "read") else bytes(body)
        if kwargs.get("IfNoneMatch") == "*" and kwargs["Key"] in self.objects:
            raise _client_error("PreconditionFailed", 412, "PutObject")
        self.objects[kwargs["Key"]] = payload
        return {}
