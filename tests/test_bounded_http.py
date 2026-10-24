"""Tests for ``bounded_http.get_bytes``, the deadline-bounded GET for live sources.

The example tests run the real ``requests``/``urllib3`` stack against local
servers that never answer, trickle their headers or body, drop connections or
answer normally, with budgets of a fraction of a second. The property tests
drive the retry and budget logic on a virtual clock with a transport that waits
out exactly the timeouts it is given.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest import mock

import pytest
import requests
import urllib3.util.connection
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import bounded_http
from axiom_corpus.corpus.bounded_http import get_bytes
from tests._local_http import (
    LocalHttpServer,
    drop_connection,
    never_answer,
    respond,
    trickle_body,
    trickle_headers,
)

# Slack for thread start-up and scheduling on a loaded CI runner. Every
# elapsed-time assertion below allows this much over its budget, and the
# budgets are small enough that a wait the code fails to bound overshoots it.
_SLACK_SECONDS = 1.0


def _elapsed(call):
    started = time.monotonic()
    try:
        result = call()
    except Exception as exc:  # returned so the test can assert on it
        return time.monotonic() - started, exc
    return time.monotonic() - started, result


def test_get_bytes_returns_the_body():
    with LocalHttpServer([respond(b"ORS chapter 316")]) as server:
        body = get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5)

    assert body == b"ORS chapter 316"
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    "behaviour",
    [
        respond(b"x" * 200_000, gzip_encoded=True),
        respond(b"x" * 200_000, chunked=True),
        respond(b"x" * 200_000, gzip_encoded=True, chunked=True),
    ],
    ids=["gzip", "chunked", "gzip-chunked"],
)
def test_get_bytes_returns_the_decoded_body_as_response_content_would(behaviour):
    with LocalHttpServer([behaviour]) as server:
        body = get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5)
        expected = requests.get(server.url, timeout=5).content

    assert body == expected == b"x" * 200_000


def test_get_bytes_sends_the_given_headers():
    with LocalHttpServer([respond(b"ok")]) as server:
        get_bytes(
            server.url,
            connect_timeout=1,
            read_timeout=1,
            deadline=5,
            headers={"User-Agent": "axiom-corpus-test/1"},
        )

    assert b"User-Agent: axiom-corpus-test/1" in server.requests[0]


def test_get_bytes_retries_a_dropped_connection_then_returns_the_body():
    with LocalHttpServer([drop_connection, respond(b"second try")]) as server:
        body = get_bytes(
            server.url,
            connect_timeout=1,
            read_timeout=1,
            deadline=5,
            attempts=2,
            retry_delay=0.01,
        )

    assert body == b"second try"
    assert len(server.requests) == 2


def test_get_bytes_raises_an_http_error_status_after_its_attempts():
    with LocalHttpServer([respond(b"missing", status="404 Not Found")]) as server:
        with pytest.raises(requests.HTTPError, match="404"):
            get_bytes(
                server.url,
                connect_timeout=1,
                read_timeout=1,
                deadline=5,
                attempts=2,
                retry_delay=0.01,
            )

    assert len(server.requests) == 2


def test_get_bytes_read_timeout_ends_a_server_that_never_answers():
    with LocalHttpServer([never_answer]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(
                server.url,
                connect_timeout=1,
                read_timeout=0.3,
                deadline=5,
                attempts=2,
                retry_delay=0.05,
            )
        )

    assert isinstance(error, requests.ReadTimeout)
    assert len(server.requests) == 2
    assert elapsed < 0.3 + 0.05 + 0.3 + _SLACK_SECONDS


def test_get_bytes_deadline_ends_a_server_that_trickles_its_headers():
    # One header byte every 50 ms never trips the 2 s read timeout; requests
    # alone would wait until the header line passed http.client's 64 KiB limit.
    with LocalHttpServer([trickle_headers(0.05)]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.6)
        )

    assert isinstance(error, requests.Timeout)
    assert "within 0.6s" in str(error)
    assert 0.6 <= elapsed < 0.6 + _SLACK_SECONDS


def test_get_bytes_deadline_ends_a_server_that_trickles_its_body():
    with LocalHttpServer([trickle_body(0.02)]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.6)
        )

    assert isinstance(error, requests.Timeout)
    assert 0.6 <= elapsed < 0.6 + _SLACK_SECONDS


def test_get_bytes_connect_timeout_ends_a_host_that_drops_connection_attempts(monkeypatch):
    # A host that drops SYNs cannot be reproduced on loopback, so the socket
    # connect blocks for exactly the timeout urllib3 hands it, then fails as
    # socket.connect does.
    connect_timeouts: list[float] = []

    def black_hole(address, timeout=None, *args, **kwargs):
        connect_timeouts.append(timeout)
        time.sleep(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib3.util.connection, "create_connection", black_hole)

    elapsed, error = _elapsed(
        lambda: get_bytes(
            "http://oregon.invalid/ors316.html",
            connect_timeout=0.2,
            read_timeout=1,
            deadline=5,
            attempts=2,
            retry_delay=0.05,
        )
    )

    assert isinstance(error, requests.ConnectTimeout)
    assert connect_timeouts == [0.2, 0.2]
    assert elapsed < 0.2 + 0.05 + 0.2 + _SLACK_SECONDS


def test_get_bytes_cuts_the_last_attempt_to_the_time_left(monkeypatch):
    connect_timeouts: list[float] = []

    def black_hole(address, timeout=None, *args, **kwargs):
        connect_timeouts.append(timeout)
        time.sleep(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib3.util.connection, "create_connection", black_hole)

    elapsed, error = _elapsed(
        lambda: get_bytes(
            "http://oregon.invalid/ors316.html",
            connect_timeout=0.4,
            read_timeout=1,
            deadline=0.6,
            attempts=3,
        )
    )

    assert isinstance(error, (requests.ConnectTimeout, requests.Timeout))
    assert connect_timeouts[0] == 0.4
    assert len(connect_timeouts) == 2
    assert connect_timeouts[1] <= 0.2 + 0.05
    assert elapsed < 0.6 + _SLACK_SECONDS


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"attempts": 0}, "attempts must be at least 1"),
        ({"connect_timeout": 0}, "must be positive"),
        ({"read_timeout": -1}, "must be positive"),
        ({"deadline": 0}, "must be positive"),
        ({"retry_delay": -0.1}, "must not be negative"),
    ],
)
def test_get_bytes_rejects_budgets_that_cannot_bound_a_request(kwargs, message):
    budget = {"connect_timeout": 1.0, "read_timeout": 1.0, "deadline": 1.0, **kwargs}
    with pytest.raises(ValueError, match=message):
        get_bytes("http://oregon.invalid/", **budget)


# Property tests: the retry and budget logic on a virtual clock.


class _VirtualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.now += seconds


class _VirtualResponse:
    def __init__(self, body: bytes, status_error: requests.HTTPError | None = None) -> None:
        self._body = body
        self._status_error = status_error

    def __enter__(self) -> _VirtualResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self._status_error is not None:
            raise self._status_error

    def iter_content(self, chunk_size: int = 1):
        for start in range(0, len(self._body), chunk_size):
            yield self._body[start : start + chunk_size]


_BODY = b"<p>Chapter 316</p>" * 10_000
_FLOAT_SLACK = 1e-9

# One attempt's server behaviour: ("connect_hang",), ("read_hang",),
# ("status", code), or ("answer", seconds of silence before the whole body).
_outcomes = st.one_of(
    st.just(("connect_hang",)),
    st.just(("read_hang",)),
    st.tuples(st.just("status"), st.sampled_from([404, 429, 500, 503])),
    st.tuples(st.just("answer"), st.floats(min_value=0, max_value=40)),
)


class _VirtualTransport:
    """``requests.get`` on the virtual clock: waits out exactly what each outcome needs."""

    def __init__(self, clock: _VirtualClock, outcomes, give_up_at: float) -> None:
        self.clock = clock
        self.outcomes = list(outcomes)
        self.give_up_at = give_up_at
        self.calls: list[dict[str, float]] = []

    def get(self, url, *, headers=None, timeout=None, stream=False, **kwargs):
        assert stream, "the body must stream so the deadline is checked as it arrives"
        connect, read = timeout
        self.calls.append(
            {"connect": connect, "read": read, "remaining": self.give_up_at - self.clock.now}
        )
        outcome = self.outcomes[len(self.calls) - 1]
        if outcome[0] == "connect_hang":
            self.clock.sleep(connect)
            raise requests.ConnectTimeout("connect timed out")
        if outcome[0] == "read_hang":
            self.clock.sleep(read)
            raise requests.ReadTimeout("read timed out")
        if outcome[0] == "status":
            response = requests.Response()
            response.status_code = outcome[1]
            return _VirtualResponse(
                b"", requests.HTTPError(f"{outcome[1]} error", response=response)
            )
        silence = outcome[1]
        if silence > read:
            self.clock.sleep(read)
            raise requests.ReadTimeout("read timed out")
        self.clock.sleep(silence)
        return _VirtualResponse(_BODY)


@settings(max_examples=300, deadline=None)
@given(
    connect_timeout=st.floats(min_value=0.01, max_value=15),
    read_timeout=st.floats(min_value=0.01, max_value=30),
    deadline=st.floats(min_value=0.01, max_value=60),
    retry_delay=st.floats(min_value=0, max_value=5),
    outcomes=st.lists(_outcomes, min_size=1, max_size=4),
)
def test_get_bytes_budget_properties(
    connect_timeout, read_timeout, deadline, retry_delay, outcomes
):
    """For every budget and every sequence of server behaviours:

    1. no request goes out without a connect and a read timeout, and neither
       exceeds its configured value or the time left before the deadline;
    2. the call never spends more than ``deadline`` (virtual) seconds;
    3. at most ``attempts`` requests are made;
    4. a returned body is the whole body, from an attempt that answered;
    5. a raised error is a ``requests.RequestException``, and the call stops
       early (fewer requests than ``attempts``) only once the deadline passed.
    """
    attempts = len(outcomes)
    clock = _VirtualClock()
    transport = _VirtualTransport(clock, outcomes, give_up_at=deadline)
    fake_time = SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep)
    with (
        mock.patch.object(bounded_http, "time", fake_time),
        mock.patch.object(bounded_http.requests, "get", transport.get),
    ):
        try:
            result: bytes | BaseException = get_bytes(
                "https://www.oregonlegislature.gov/bills_laws/ors/ors316.html",
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                deadline=deadline,
                attempts=attempts,
                retry_delay=retry_delay,
            )
        except requests.RequestException as exc:
            result = exc

    for call in transport.calls:
        assert 0 < call["connect"] <= min(connect_timeout, call["remaining"])
        assert 0 < call["read"] <= min(read_timeout, call["remaining"])
    # The time left is the deadline less the time spent, so spending all of it
    # can land a rounding error past the deadline: (d - t) + t != d in floats.
    assert clock.now <= deadline + _FLOAT_SLACK
    assert len(transport.calls) <= attempts
    if isinstance(result, bytes):
        assert result == _BODY
        assert outcomes[len(transport.calls) - 1][0] == "answer"
    else:
        assert isinstance(result, requests.RequestException)
        if len(transport.calls) < attempts:
            assert clock.now >= deadline


@settings(max_examples=100, deadline=None)
@given(
    deadline=st.floats(min_value=0.5, max_value=60),
    silence=st.floats(min_value=0, max_value=20),
)
def test_get_bytes_first_answer_is_returned_without_a_retry(deadline, silence):
    clock = _VirtualClock()
    transport = _VirtualTransport(clock, [("answer", silence), ("answer", 0)], give_up_at=deadline)
    fake_time = SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep)
    with (
        mock.patch.object(bounded_http, "time", fake_time),
        mock.patch.object(bounded_http.requests, "get", transport.get),
    ):
        try:
            result: bytes | BaseException = get_bytes(
                "https://www.oregonlegislature.gov/bills_laws/ors/ors316.html",
                connect_timeout=10,
                read_timeout=20,
                deadline=deadline,
                attempts=2,
                retry_delay=0.5,
            )
        except requests.RequestException as exc:
            result = exc

    if silence <= min(20, deadline) and silence < deadline:
        assert result == _BODY
        assert len(transport.calls) == 1
    else:
        assert isinstance(result, requests.RequestException)
