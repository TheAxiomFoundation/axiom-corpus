"""Tests for ``bounded_http.get_bytes``, the deadline-bounded GET for live sources.

The example tests run the real ``requests``/``urllib3`` stack against local
servers that never answer, trickle their headers or body, redirect, drop
connections or answer normally, with budgets of a fraction of a second. The property tests
drive the retry and budget logic (``_get_with_retries``) synchronously on a
virtual clock, with a transport that waits out exactly the timeouts it is
given, so no assertion there depends on how the machine schedules threads.
"""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

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
    held_headers,
    never_answer,
    redirect,
    respond,
    stream_body,
    trickle_body,
    trickle_headers,
    until_client_closes,
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


def _open_workers(url: str) -> int:
    return sum(1 for thread in threading.enumerate() if thread.name == f"get_bytes {url}")


def _wait_until(condition, *, within: float = 5.0) -> bool:
    give_up_at = time.monotonic() + within
    while time.monotonic() < give_up_at:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


@pytest.fixture
def slots(monkeypatch):
    """A fresh cap of 3 fetch threads, so tests neither see nor leave other tests' workers."""
    cap = bounded_http._Slots(3)
    monkeypatch.setattr(bounded_http, "_SLOTS", cap)
    return cap


def test_get_bytes_returns_the_body(slots):
    with LocalHttpServer([respond(b"ORS chapter 316")]) as server:
        body = get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5)

    assert body == b"ORS chapter 316"
    assert len(server.requests) == 1
    assert slots.used == 0  # the worker gave its slot back before the call returned


@pytest.mark.parametrize(
    "behaviour",
    [
        respond(b"x" * 200_000, gzip_encoded=True),
        respond(b"x" * 200_000, chunked=True),
        respond(b"x" * 200_000, gzip_encoded=True, chunked=True),
    ],
    ids=["gzip", "chunked", "gzip-chunked"],
)
def test_get_bytes_returns_the_decoded_body_as_response_content_would(behaviour, slots):
    with LocalHttpServer([behaviour]) as server:
        body = get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5)
        expected = requests.get(server.url, timeout=5).content

    assert body == expected == b"x" * 200_000


def test_get_bytes_sends_the_given_headers(slots):
    with LocalHttpServer([respond(b"ok")]) as server:
        get_bytes(
            server.url,
            connect_timeout=1,
            read_timeout=1,
            deadline=5,
            headers={"User-Agent": "axiom-corpus-test/1"},
        )

    assert b"User-Agent: axiom-corpus-test/1" in server.requests[0]


def test_get_bytes_retries_a_dropped_connection_then_returns_the_body(slots):
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


def test_get_bytes_raises_an_http_error_status_after_its_attempts(slots):
    with LocalHttpServer([respond(b"missing", status="404 Not Found")]) as server:
        with pytest.raises(requests.HTTPError, match="404") as excinfo:
            get_bytes(
                server.url,
                connect_timeout=1,
                read_timeout=1,
                deadline=5,
                attempts=2,
                retry_delay=0.01,
            )

    assert excinfo.value.response.status_code == 404
    assert len(server.requests) == 2


def test_get_bytes_follows_a_redirect_inside_the_deadline(slots):
    routes = {"/": redirect("/moved"), "/moved": respond(b"moved here")}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        body = get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5)

    assert body == b"moved here"
    assert [request.split(b" ")[1] for request in server.requests] == [b"/", b"/moved"]


def test_get_bytes_follows_no_redirect_after_the_deadline(slots):
    # The redirect's headers trickle in until 0.6 s into a 0.3 s deadline, so no
    # read timeout ends the worker the caller already left; requests alone would
    # then request /moved.
    routes = {"/": redirect("/moved", slowly_for=0.6), "/moved": respond(b"too late")}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.3)
        )
        assert isinstance(error, requests.Timeout)
        assert elapsed < 0.3 + _SLACK_SECONDS
        # The worker ends when the redirect arrives, without following it. A
        # followed redirect would have reached the server before the worker
        # got its answer and ended.
        assert _wait_until(lambda: slots.used == 0)

        assert [request.split(b" ")[1] for request in server.requests] == [b"/"]


def test_get_bytes_sends_no_redirect_whose_body_ends_after_the_deadline(slots):
    # The redirect's headers arrive at once, inside the deadline, and its body
    # a byte at a time until 0.6 s, after it. requests reads that body before
    # it follows the redirect, so the deadline is checked again just before
    # the next request is sent.
    routes = {"/": redirect("/moved", body_slowly_for=0.6), "/moved": respond(b"too late")}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.3)
        )
        assert isinstance(error, requests.Timeout)
        assert elapsed < 0.3 + _SLACK_SECONDS
        assert _wait_until(lambda: slots.used == 0)

        assert [request.split(b" ")[1] for request in server.requests] == [b"/"]


def test_get_bytes_cuts_a_redirects_timeouts_to_the_time_left(slots):
    # The redirect arrives 1.5 s into a 2 s deadline and points at a server
    # that never answers. Its request may wait only the 0.5 s left, not the
    # 2 s the attempt started with (nor the 10 s read timeout), so the worker
    # ends with the caller rather than 1.5 s after it.
    routes = {"/": redirect("/hang", slowly_for=1.5), "/hang": never_answer}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=10, deadline=2.0)
        )
        assert isinstance(error, requests.Timeout)
        assert elapsed < 2.0 + _SLACK_SECONDS
        assert _wait_until(lambda: slots.used == 0, within=_SLACK_SECONDS)

        assert [request.split(b" ")[1] for request in server.requests] == [b"/", b"/hang"]


@pytest.mark.parametrize(
    "behaviours, routes, deadline, outcome",
    [
        ([until_client_closes(respond(b"ok"))], {}, 5, bytes),
        (
            [until_client_closes(respond(b"missing", status="404 Not Found"))],
            {},
            5,
            requests.HTTPError,
        ),
        (
            [respond(b"wrong")],
            {
                "/": until_client_closes(redirect("/moved")),
                "/moved": until_client_closes(respond(b"moved")),
            },
            5,
            bytes,
        ),
        (
            [respond(b"wrong")],
            {
                "/": until_client_closes(redirect("/moved", slowly_for=0.6)),
                "/moved": respond(b"too late"),
            },
            0.3,
            requests.Timeout,
        ),
        ([stream_body(64 * 1024, 0.02)], {}, 0.3, requests.Timeout),
    ],
    ids=["body", "http-error", "followed-redirect", "late-redirect", "body-cut-at-the-deadline"],
)
def test_get_bytes_leaves_no_connection_open_while_its_result_is_kept(
    behaviours, routes, deadline, outcome, slots
):
    """Every response a worker opens is closed when it ends, even while its error is still held.

    The result is kept, as discovery's finished futures keep theirs. A
    caller's exception reaches the worker's error through its traceback, and
    that error's traceback reaches every frame and response of the attempt, so
    a response left open would keep its connection open for as long as the
    result is kept, whatever the garbage collector does.
    """
    with LocalHttpServer(behaviours, routes=routes) as server:
        _, result = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=deadline)
        )
        assert isinstance(result, outcome)
        assert _wait_until(lambda: slots.used == 0)

        assert _wait_until(lambda: server.open_connections == 0), (
            f"{server.open_connections} connection(s) still open"
        )
        assert result is not None  # still kept


def test_get_bytes_deadline_stops_a_worker_reading_a_body_that_keeps_arriving(slots):
    # 64 KiB every 20 ms of a body declared as 1 TiB: the worker checks the
    # deadline at each chunk, so it stops just after it, while the server is
    # still sending.
    with LocalHttpServer([stream_body(64 * 1024, 0.02)]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.3)
        )
        assert isinstance(error, requests.Timeout)
        assert elapsed < 0.3 + _SLACK_SECONDS
        assert _wait_until(lambda: slots.used == 0, within=_SLACK_SECONDS)


def test_get_bytes_read_timeout_ends_a_server_that_never_answers(slots):
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
    assert slots.used == 0  # the read timeouts ended the worker before the deadline


def test_get_bytes_deadline_ends_a_server_that_trickles_its_headers(slots):
    # One header byte every 50 ms never trips the 2 s read timeout; requests
    # alone would wait until the header line passed http.client's 64 KiB limit,
    # about 55 minutes at this rate.
    with LocalHttpServer([trickle_headers(0.05)]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.6)
        )
        assert slots.used == 1  # the worker is still reading, and holds its slot

    assert isinstance(error, requests.Timeout)
    assert "within 0.6s" in str(error)
    assert 0.6 <= elapsed < 0.6 + _SLACK_SECONDS
    # Closing the connection ends the worker, which gives its slot back.
    assert _wait_until(lambda: slots.used == 0)


def test_get_bytes_deadline_ends_a_server_that_trickles_its_body(slots):
    # A declared 10 MB at one byte every 20 ms would take about 55 hours.
    with LocalHttpServer([trickle_body(0.02)]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.6)
        )

    assert isinstance(error, requests.Timeout)
    assert 0.6 <= elapsed < 0.6 + _SLACK_SECONDS
    assert _wait_until(lambda: slots.used == 0)


def test_get_bytes_caps_workers_left_open_by_a_trickling_server(slots):
    """Timed-out calls cannot pile up open workers: with every slot held, a call does not start."""
    with LocalHttpServer([trickle_headers(0.02)]) as server:
        errors = []
        for _ in range(8):
            elapsed, error = _elapsed(
                lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.3)
            )
            errors.append(error)
            assert elapsed < 0.3 + _SLACK_SECONDS

        # Checked while the server is still trickling, so nothing has ended them.
        assert slots.used == 3
        assert _open_workers(server.url) == 3
        assert len(server.requests) == 3
        assert all(isinstance(error, requests.Timeout) for error in errors)
        assert all("fetch threads stayed busy" in str(error) for error in errors[3:])
        assert all("0.3s deadline" in str(error) for error in errors[3:])

        url = server.url

    assert _wait_until(lambda: slots.used == 0)
    assert _wait_until(lambda: _open_workers(url) == 0)
    with LocalHttpServer([respond(b"recovered")]) as server:
        assert get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5) == b"recovered"


def test_get_bytes_caps_workers_left_open_by_concurrent_callers(slots):
    """Eight callers trying 40 URLs on a trickling server leave at most 3 workers open."""
    # The server closes before the callers are joined, so a get_bytes that
    # failed to return at its deadline fails this test instead of hanging it.
    with (
        ThreadPoolExecutor(max_workers=8) as callers,
        LocalHttpServer([trickle_headers(0.02)]) as server,
    ):
        errors = list(
            callers.map(
                lambda _: _elapsed(
                    lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.3)
                )[1],
                range(40),
                timeout=30,
            )
        )

        assert all(isinstance(error, requests.Timeout) for error in errors)
        assert _open_workers(server.url) == 3
        assert len(server.requests) == 3
        assert server.max_concurrent == 3
        assert slots.used == 3

    assert _wait_until(lambda: slots.used == 0)


def test_get_bytes_never_exceeds_the_cap_under_heavy_thread_switching(monkeypatch, slots):
    """Sixteen callers on four slots: never more than four workers at once, no slot lost."""
    # Counted in the workers themselves, between taking over a slot and giving
    # it back, so a connection the server has yet to tidy up is not counted.
    running = 0
    most_running = 0
    count_lock = threading.Lock()
    attempts = bounded_http._get_with_retries

    def counted_attempts(*args, **kwargs):
        nonlocal running, most_running
        with count_lock:
            running += 1
            most_running = max(most_running, running)
        try:
            return attempts(*args, **kwargs)
        finally:
            with count_lock:
                running -= 1

    monkeypatch.setattr(bounded_http, "_get_with_retries", counted_attempts)
    switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # switch threads as often as the interpreter allows
    try:
        with (
            ThreadPoolExecutor(max_workers=16) as callers,
            LocalHttpServer([respond(b"ok", after=0.005)]) as server,
        ):
            slots.limit = 4
            bodies = list(
                callers.map(
                    lambda _: get_bytes(server.url, connect_timeout=2, read_timeout=2, deadline=20),
                    range(160),
                    timeout=60,
                )
            )
            assert _wait_until(lambda: slots.used == 0)
    finally:
        sys.setswitchinterval(switch_interval)

    assert 1 <= most_running <= 4
    assert bodies == [b"ok"] * 160
    assert len(server.requests) == 160


def test_get_bytes_waits_within_its_deadline_for_a_slot(monkeypatch):
    cap = bounded_http._Slots(1)
    monkeypatch.setattr(bounded_http, "_SLOTS", cap)
    cap.used = 1  # one worker still open from an earlier call

    with LocalHttpServer([respond(b"ok")]) as server:
        threading.Timer(0.2, cap.release).start()
        elapsed, body = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=3)
        )

    assert body == b"ok"
    assert 0.2 <= elapsed < 0.2 + _SLACK_SECONDS
    assert cap.used == 0


def _callers_waiting_for_a_slot(cap) -> int:
    # threading.Condition keeps one lock per waiting thread in _waiters.
    return len(cap.changed._waiters)


def test_a_finishing_worker_wakes_the_callers_waiting_for_its_slot(monkeypatch):
    """The slot a left-behind worker gives back goes to waiting callers, whatever their deadlines."""
    cap = bounded_http._Slots(1)
    monkeypatch.setattr(bounded_http, "_SLOTS", cap)
    first_answer = threading.Event()
    # The first request's headers trickle in until first_answer is set; every
    # later request is answered at once.
    with LocalHttpServer([held_headers(first_answer, b"slow"), respond(b"fast")]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=1.0)
        )
        assert isinstance(error, requests.Timeout)
        assert cap.used == 1  # the first worker still holds the only slot

        with ThreadPoolExecutor(max_workers=2) as callers:
            waiting = [
                callers.submit(
                    lambda deadline=deadline: (
                        get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=deadline),
                        time.monotonic(),
                    )
                )
                for deadline in (10.0, 8.0)
            ]
            assert _wait_until(lambda: _callers_waiting_for_a_slot(cap) == 2)
            released = time.monotonic()
            first_answer.set()  # the first worker ends and gives its slot back
            results = [future.result(timeout=30) for future in waiting]

    # Both took the slot in turn as soon as it came back, long before either
    # deadline; without a wake-up each would wait until its deadline.
    assert [body for body, _ in results] == [b"fast", b"fast"]
    assert all(finished - released < 2 * _SLACK_SECONDS for _, finished in results)
    assert len(server.requests) == 3
    assert cap.used == 0


def _patch_worker_threads(monkeypatch, thread_class):
    monkeypatch.setattr(
        bounded_http,
        "threading",
        SimpleNamespace(Thread=thread_class, Event=threading.Event, Condition=threading.Condition),
    )


@pytest.mark.parametrize(
    "failure",
    [KeyboardInterrupt(), RuntimeError("can't start new thread")],
    ids=["ctrl-c", "out-of-threads"],
)
def test_get_bytes_gives_the_slot_back_when_its_worker_does_not_start(monkeypatch, slots, failure):
    class FailedStart(threading.Thread):
        def start(self) -> None:
            raise failure  # Ctrl-C, or no thread to be had, before the thread exists

    _patch_worker_threads(monkeypatch, FailedStart)
    with LocalHttpServer([respond(b"ok")]) as server:
        with pytest.raises(type(failure)):
            get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5)

        assert slots.used == 0
        assert server.requests == []


def test_get_bytes_cancels_a_worker_interrupted_before_it_takes_its_slot(monkeypatch, slots):
    class Gated(threading.Thread):
        """A worker that waits for ``gate`` before running, as a slow-to-schedule one does."""

        gate = threading.Event()

        def start(self) -> None:
            super().start()
            raise KeyboardInterrupt  # Ctrl-C once the thread exists, before it runs

        def run(self) -> None:
            self.gate.wait(timeout=10)
            super().run()

    _patch_worker_threads(monkeypatch, Gated)
    with LocalHttpServer([respond(b"ok")]) as server:
        with pytest.raises(KeyboardInterrupt):
            get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5)
        assert slots.used == 0  # given back by the interrupted caller

        Gated.gate.set()  # the worker now runs, finds itself cancelled, and stops
        assert _wait_until(lambda: _open_workers(server.url) == 0)
        assert server.requests == []
        assert slots.used == 0


def test_get_bytes_leaves_the_slot_to_a_worker_that_took_it_before_the_interrupt(
    monkeypatch, slots
):
    class InterruptedAfterRequest(threading.Thread):
        def start(self) -> None:
            super().start()
            # Ctrl-C after the worker took the slot and sent its request.
            assert _wait_until(lambda: len(server.requests) == 1)
            raise KeyboardInterrupt

    _patch_worker_threads(monkeypatch, InterruptedAfterRequest)
    answer = threading.Event()
    with LocalHttpServer([respond(b"ok", gate=answer)]) as server:
        with pytest.raises(KeyboardInterrupt):
            get_bytes(server.url, connect_timeout=1, read_timeout=5, deadline=10)
        assert slots.used == 1  # still the worker's, which is waiting for its answer

        answer.set()
        assert _wait_until(lambda: slots.used == 0)  # it gives it back when it ends
        assert len(server.requests) == 1


def test_get_bytes_interrupted_while_waiting_leaves_the_slot_to_the_worker(monkeypatch, slots):
    class InterruptedWait(threading.Event):
        def wait(self, timeout=None):
            raise KeyboardInterrupt  # Ctrl-C while the caller waits for the body

    class Call(bounded_http._Call):
        def __init__(self) -> None:
            super().__init__()
            self.finished = InterruptedWait()

    monkeypatch.setattr(bounded_http, "_Call", Call)
    answer = threading.Event()
    with LocalHttpServer([respond(b"ok", gate=answer)]) as server:
        with pytest.raises(KeyboardInterrupt):
            get_bytes(server.url, connect_timeout=1, read_timeout=5, deadline=10)
        assert _wait_until(lambda: len(server.requests) == 1)
        assert slots.used == 1  # the worker's, which is waiting for its answer

        answer.set()
        assert _wait_until(lambda: _open_workers(server.url) == 0)
        assert slots.used == 0  # given back once, by the worker


def test_get_bytes_connect_timeout_ends_a_host_that_drops_connection_attempts(monkeypatch, slots):
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


def test_get_bytes_cuts_each_attempt_to_the_time_left(monkeypatch, slots):
    timeouts: list[float] = []

    def black_hole(address, timeout=None, *args, **kwargs):
        timeouts.append(timeout)
        time.sleep(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib3.util.connection, "create_connection", black_hole)
    url = "http://oregon.invalid/ors316.html"

    elapsed, error = _elapsed(
        lambda: get_bytes(url, connect_timeout=0.4, read_timeout=1, deadline=1.0, attempts=5)
    )
    assert _wait_until(lambda: _open_workers(url) == 0)

    assert isinstance(error, (requests.ConnectTimeout, requests.Timeout))
    assert timeouts
    assert all(0 < timeout <= 0.4 for timeout in timeouts)
    # Each attempt starts after the last one waited out its whole timeout, and
    # may take only what is left, so the timeouts sum to at most the deadline
    # however the threads were scheduled. Uncut, five attempts would sum to 2 s.
    assert sum(timeouts) <= 1.0 + 1e-6
    assert elapsed < 1.0 + _SLACK_SECONDS


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"attempts": 0}, "attempts must be at least 1"),
        ({"connect_timeout": 0}, "connect_timeout must be a positive finite number"),
        ({"read_timeout": -1}, "read_timeout must be a positive finite number"),
        ({"deadline": 0}, "deadline must be a positive finite number"),
        ({"deadline": float("inf")}, "deadline must be a positive finite number"),
        ({"deadline": float("nan")}, "deadline must be a positive finite number"),
        ({"connect_timeout": float("nan")}, "connect_timeout must be a positive finite"),
        ({"retry_delay": -0.1}, "retry_delay must be a non-negative finite number"),
        ({"retry_delay": float("inf")}, "retry_delay must be a non-negative finite number"),
    ],
)
def test_get_bytes_rejects_budgets_that_cannot_bound_a_request(kwargs, message):
    budget = {"connect_timeout": 1.0, "read_timeout": 1.0, "deadline": 1.0, **kwargs}
    with pytest.raises(ValueError, match=message):
        get_bytes("http://oregon.invalid/", **budget)


# Property tests: the retry and budget logic, synchronously, on a virtual clock.


class _VirtualClock:
    """A clock that moves only when slept on.

    ``sleep`` is the transport waiting out exactly a timeout. ``pause`` is
    ``time.sleep`` in the module under test, which may return ``oversleep``
    seconds late, as a real sleep on a loaded machine can.
    """

    def __init__(self, oversleep: float = 0.0) -> None:
        self.now = 0.0
        self.oversleep = oversleep

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.now += seconds

    def pause(self, seconds: float) -> None:
        assert seconds >= 0
        self.now += seconds + self.oversleep


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
    """``bounded_http._open`` on the virtual clock: waits out exactly what each outcome needs."""

    def __init__(self, clock: _VirtualClock, outcomes, give_up_at: float) -> None:
        self.clock = clock
        self.outcomes = list(outcomes)
        self.give_up_at = give_up_at
        self.calls: list[dict[str, float]] = []

    def open(self, url, *, headers=None, timeout=None, give_up_at=None):
        assert give_up_at == self.give_up_at
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


def _run_retries(monkeypatch, transport, **budget):
    clock = transport.clock
    monkeypatch.setattr(
        bounded_http, "time", SimpleNamespace(monotonic=clock.monotonic, sleep=clock.pause)
    )
    monkeypatch.setattr(bounded_http, "_open", transport.open)
    try:
        return bounded_http._get_with_retries(
            "https://www.oregonlegislature.gov/bills_laws/ors/ors316.html",
            headers={},
            give_up_at=transport.give_up_at,
            **budget,
        )
    except requests.RequestException as exc:
        return exc


@settings(max_examples=300, deadline=None)
@given(
    connect_timeout=st.floats(min_value=0.01, max_value=15),
    read_timeout=st.floats(min_value=0.01, max_value=30),
    deadline=st.floats(min_value=0.01, max_value=60),
    retry_delay=st.floats(min_value=0, max_value=5),
    oversleep=st.one_of(st.just(0.0), st.floats(min_value=0, max_value=2)),
    outcomes=st.lists(_outcomes, min_size=1, max_size=4),
)
def test_retry_budget_properties(
    connect_timeout, read_timeout, deadline, retry_delay, oversleep, outcomes
):
    """For every budget and every sequence of server behaviours:

    1. no request goes out without a connect and a read timeout, and neither
       exceeds its configured value or the time left before the deadline;
    2. the attempts never spend more than ``deadline`` (virtual) seconds, plus
       one late return from a pause;
    3. at most ``attempts`` requests are made;
    4. a returned body is the whole body, from an attempt that answered;
    5. a raised error is a ``requests.RequestException``, and the retries stop
       early (fewer requests than ``attempts``) only once the deadline passed
       or when the pause before the next attempt would reach it.
    """
    attempts = len(outcomes)
    clock = _VirtualClock(oversleep=oversleep)
    transport = _VirtualTransport(clock, outcomes, give_up_at=deadline)
    with pytest.MonkeyPatch.context() as monkeypatch:
        result = _run_retries(
            monkeypatch,
            transport,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            attempts=attempts,
            retry_delay=retry_delay,
        )

    for call in transport.calls:
        assert 0 < call["connect"] <= min(connect_timeout, call["remaining"])
        assert 0 < call["read"] <= min(read_timeout, call["remaining"])
    # The time left is the deadline less the time spent, so spending all of it
    # can land a rounding error past the deadline: (d - t) + t != d in floats.
    # A pause that returns late can pass the deadline, and then nothing follows.
    assert clock.now <= deadline + oversleep + _FLOAT_SLACK
    assert len(transport.calls) <= attempts
    if isinstance(result, bytes):
        assert result == _BODY
        assert outcomes[len(transport.calls) - 1][0] == "answer"
    else:
        assert isinstance(result, requests.RequestException)
        if len(transport.calls) < attempts:
            assert deadline - clock.now <= retry_delay


@settings(max_examples=100, deadline=None)
@given(
    deadline=st.floats(min_value=0.01, max_value=60),
    silence=st.floats(min_value=0, max_value=40),
)
def test_first_answer_is_returned_without_a_retry(deadline, silence):
    clock = _VirtualClock()
    transport = _VirtualTransport(clock, [("answer", silence), ("answer", 0)], give_up_at=deadline)
    with pytest.MonkeyPatch.context() as monkeypatch:
        result = _run_retries(
            monkeypatch,
            transport,
            connect_timeout=10,
            read_timeout=20,
            attempts=2,
            retry_delay=0.5,
        )

    if silence <= 20 and silence < deadline:
        assert result == _BODY
        assert len(transport.calls) == 1
    elif isinstance(result, bytes):
        # The first attempt timed out, and the second, which answers at once,
        # still had time left.
        assert result == _BODY
        assert len(transport.calls) == 2
    else:
        assert isinstance(result, requests.RequestException)
