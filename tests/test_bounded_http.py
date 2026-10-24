"""Tests for ``bounded_http.get_bytes``, the deadline-bounded GET for live sources.

The example tests run the real ``requests``/``urllib3`` stack against local
servers that never answer, trickle their headers or body, redirect, drop
connections or answer normally, with budgets of a fraction of a second. The property tests
drive the retry and budget logic (``_get_with_retries``) synchronously on a
virtual clock, with a transport that waits out exactly the timeouts it is
given, so no assertion there depends on how the machine schedules threads.
"""

from __future__ import annotations

import contextlib
import gc
import subprocess
import sys
import threading
import time
import urllib.parse
import weakref
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import requests
import urllib3.util.connection
from hypothesis import example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import bounded_http
from axiom_corpus.corpus.bounded_http import get_bytes
from tests._local_http import (
    OVERFLOWING_COOKIE,
    LocalHttpServer,
    RunningCount,
    drop_connection,
    held_headers,
    never_answer,
    redirect,
    respond,
    stream_body,
    trickle_body,
    trickle_headers,
    until_client_closes,
    wait_until,
    warnings_as_errors,
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
        assert wait_until(lambda: slots.used == 0)

        assert [request.split(b" ")[1] for request in server.requests] == [b"/"]


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_no_request_is_sent_once_the_deadline_has_passed(scheme):
    # Past the deadline the adapter raises requests.Timeout, which the retry
    # loop and the Oregon fetcher handle. Without its check, requests would
    # reject the timeouts, cut to zero or less, with a ValueError that neither
    # catches, and a caller still waiting would get that instead. An https URL
    # goes through the adapter too: requests' own adapter would connect.
    with LocalHttpServer([respond(b"too late")]) as server:
        url = server.url.replace("http://", f"{scheme}://")
        with pytest.raises(requests.Timeout):
            bounded_http._open(url, headers={}, timeout=(1.0, 1.0), give_up_at=time.monotonic())
        assert server.max_concurrent == 0  # not even a connection


@settings(max_examples=300, deadline=None)
@given(
    connect=st.floats(min_value=0.001, max_value=100),
    read=st.floats(min_value=0.001, max_value=100),
    left=st.floats(min_value=-10, max_value=100),
)
def test_the_adapter_starts_no_request_after_the_deadline_and_cuts_each_to_the_time_left(
    connect, read, left
):
    clock = _VirtualClock()
    clock.now = 1_000.0
    give_up_at = clock.now + left
    handed = []

    def transport(self, request, **kwargs):
        handed.append(kwargs["timeout"])
        return requests.Response()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(bounded_http, "time", SimpleNamespace(monotonic=clock.monotonic))
        monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", transport)
        adapter = bounded_http._DeadlineAdapter("http://example.test/", give_up_at, [])
        request = requests.Request("GET", "http://example.test/").prepare()
        try:
            adapter.send(request, timeout=(connect, read))
            refused = False
        except requests.Timeout:
            refused = True

    remaining = give_up_at - clock.now
    if remaining <= 0:
        assert refused
        assert handed == []
    else:
        assert not refused
        assert handed == [(min(connect, remaining), min(read, remaining))]


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
        assert wait_until(lambda: slots.used == 0)

        assert [request.split(b" ")[1] for request in server.requests] == [b"/"]


def test_get_bytes_cuts_a_redirects_timeouts_to_the_time_left(slots, monkeypatch):
    # With timeouts far above the deadline, each request's are cut to the time
    # left when it starts, which only shrinks, so the redirect's are below the
    # first request's. Without the cut, the redirect would get the attempt's.
    handed = []
    send = requests.adapters.HTTPAdapter.send

    def recording_send(self, request, **kwargs):
        handed.append((request.path_url, kwargs["timeout"]))
        return send(self, request, **kwargs)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", recording_send)
    routes = {"/": redirect("/moved"), "/moved": respond(b"moved")}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        body = get_bytes(server.url, connect_timeout=30, read_timeout=30, deadline=5)

    assert body == b"moved"
    (first_path, first), (second_path, second) = handed
    assert (first_path, second_path) == ("/", "/moved")
    assert first[0] == first[1] <= 5
    assert second[0] == second[1] < first[1]


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
        # Kept-alive connections go back to the session's pool, so these also
        # need the session closed.
        (
            [respond(b"wrong")],
            {
                "/": redirect("/moved", keep_alive=True),
                "/moved": until_client_closes(respond(b"moved")),
            },
            5,
            bytes,
        ),
        (
            [respond(b"wrong")],
            {"/": redirect("/moved", slowly_for=0.6, keep_alive=True), "/moved": respond(b"late")},
            0.3,
            requests.Timeout,
        ),
        # requests raises TooManyRedirects with the last response attached,
        # its body read and its kept-alive connection back in the pool.
        ([respond(b"wrong")], {"/": redirect("/", keep_alive=True)}, 5, requests.TooManyRedirects),
        # requests raises UnicodeDecodeError for this Location before it reads
        # the body, with the response, and its connection, still open.
        (
            [respond(b"wrong")],
            {"/": until_client_closes(redirect("/\xff", body=b"oops"))},
            5,
            requests.RequestException,
        ),
    ],
    ids=[
        "body",
        "http-error",
        "followed-redirect",
        "late-redirect",
        "body-cut-at-the-deadline",
        "followed-keep-alive-redirect",
        "late-keep-alive-redirect",
        "redirect-loop",
        "location-not-utf-8",
    ],
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
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: server.open_connections == 0), (
            f"{server.open_connections} connection(s) still open"
        )
        assert result is not None  # still kept


class _Abort(BaseException):
    """Stands in for ``KeyboardInterrupt`` or ``SystemExit`` raised mid-request."""


class _UnprintableError(ValueError):
    """An error whose ``repr`` raises ``repr_failure``, as a third-party one's can."""

    def __init__(self, message: str, repr_failure: BaseException | None = None) -> None:
        super().__init__(message)
        self.repr_failure = repr_failure or RuntimeError("no repr")

    def __repr__(self) -> str:
        raise self.repr_failure


def _shown(failure: BaseException) -> str:
    """How a note or a failed attempt's message shows ``failure``."""
    return object.__repr__(failure) if isinstance(failure, _UnprintableError) else repr(failure)


def _pool_close_failed_note(failure: BaseException) -> str:
    return f"closing a connection pool also failed: {_shown(failure)}"


def _assert_failed_attempt(error: BaseException, url: str, failure: BaseException) -> None:
    """``error`` is the failed attempt at ``url`` that ``failure`` ended after an answer arrived."""
    assert type(error) is requests.RequestException
    assert error.__cause__ is failure
    assert str(error) == f"fetching {url} failed after an answer arrived: {_shown(failure)}"


def _redirect_chain(hosts: int, last=None) -> list[LocalHttpServer]:
    """``hosts`` servers, each redirecting to the next and keeping its connection alive.

    The last runs ``last``, or redirects back to the first, round and round.
    The adapter caches pools for ten hosts, so a longer chain evicts the
    first host's pool when it reaches the eleventh, and the session closes
    the rest.
    """
    # targets[i] is where host i redirects to; filled in once every host has
    # its address.
    targets: list[str] = []

    def redirect_onwards(index):
        def behaviour(connection, closing):
            return redirect(targets[index], keep_alive=True)(connection, closing)

        return behaviour

    servers = [LocalHttpServer([redirect_onwards(index)]) for index in range(hosts - 1)]
    servers.append(LocalHttpServer([last or redirect_onwards(hosts - 1)]))
    targets.extend(server.url for server in servers[1:])
    targets.append(servers[0].url)
    return servers


@pytest.mark.parametrize(
    "pool_failure",
    [None, OSError, ValueError, _UnprintableError],
    ids=["pools-close", "two-pools-fail-to-close", "other-error", "unprintable-error"],
)
@pytest.mark.parametrize("ending", ["http-error", "redirect-loop"])
def test_get_bytes_closes_the_pools_a_long_redirect_chain_drops(
    ending, pool_failure, slots, monkeypatch
):
    """A chain across more hosts than the adapter caches pools for (ten) leaves none open.

    Each host keeps its redirect's connection alive, so it waits idle in its
    pool, and the error is kept, as discovery keeps it. Pools the cache
    evicts are closed then and there; the rest when the session closes. When
    the first host's pool (evicted mid-chain) and the sixth's (closed with
    the session) fail to close, the chain goes on, every other pool is closed
    all the same, and the failures are noted on the error, or fail the
    attempt when nothing else did.
    """
    if ending == "http-error":
        last = until_client_closes(respond(b"broken", status="500 Internal Server Error"))
        outcome: type[Exception] = requests.HTTPError
    else:
        last = None
        outcome = requests.TooManyRedirects
    servers = _redirect_chain(12, last)
    raised: list[BaseException] = []
    if pool_failure is not None:
        _make_connections_fail_to_close(
            monkeypatch, servers[0].url, servers[5].url, failure_type=pool_failure, raised=raised
        )
    with contextlib.ExitStack() as stack:
        for server in servers:
            stack.enter_context(server)
        _, error = _elapsed(
            lambda: get_bytes(servers[0].url, connect_timeout=1, read_timeout=2, deadline=5)
        )
        if pool_failure is None:
            assert isinstance(error, outcome)
        elif ending == "http-error":
            # The 500 is never checked: the session's pools failed to close first.
            assert type(error) is requests.RequestException
            assert len(raised) == 2
            assert error.__cause__ is raised[0]
            assert error.__cause__.__notes__ == [_pool_close_failed_note(raised[1])]
        else:
            # Round and round, each host's pool is evicted again and again.
            assert type(error) is requests.TooManyRedirects
            assert len(raised) > 2
            assert error.__notes__ == [_pool_close_failed_note(failure) for failure in raised]
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: sum(server.open_connections for server in servers) == 0), [
            server.open_connections for server in servers
        ]
        assert error is not None  # still kept


def test_get_bytes_leaves_no_proxy_connection_open_while_its_error_is_kept(slots, monkeypatch):
    # The proxy keeps its connection alive through a redirect loop, so the
    # connection waits idle in the proxy manager's pool when requests gives up.
    for name in ("no_proxy", "NO_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    target = "http://proxied.test/"
    with LocalHttpServer([redirect(target, keep_alive=True)]) as proxy:
        for name in ("http_proxy", "HTTP_PROXY"):
            monkeypatch.setenv(name, proxy.url)
        _, error = _elapsed(
            lambda: get_bytes(target, connect_timeout=1, read_timeout=2, deadline=5)
        )
        assert isinstance(error, requests.TooManyRedirects)
        assert proxy.requests[0].startswith(b"GET http://proxied.test/ ")
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: proxy.open_connections == 0), (
            f"{proxy.open_connections} connection(s) still open"
        )
        assert error is not None  # still kept


@pytest.mark.parametrize("hop", ["first", "redirected"])
def test_get_bytes_closes_an_answer_whose_response_requests_fails_to_build(hop, slots, monkeypatch):
    monkeypatch.setattr(
        bounded_http, "_get_with_retries", warnings_as_errors(bounded_http._get_with_retries)
    )
    answer = until_client_closes(respond(b"oops", headers=[OVERFLOWING_COOKIE]))
    routes = {"/": answer}
    if hop == "redirected":
        routes = {"/": until_client_closes(redirect("/moved")), "/moved": answer}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        with pytest.raises(requests.RequestException) as excinfo:
            get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=5)
        assert isinstance(excinfo.value.__cause__, UserWarning)
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: server.open_connections == 0), (
            f"{server.open_connections} connection(s) still open"
        )
        assert excinfo.value is not None  # still kept


_CLOSE_FAILED_NOTE = "closing the answer also failed: OSError('close failed')"


def _make_answers_fail_to_close(monkeypatch):
    """Make each urllib3 answer close, then report a failure, as a socket's close can."""
    close = urllib3.response.HTTPResponse.close

    def close_then_fail(self):
        close(self)
        raise OSError("close failed")

    monkeypatch.setattr(urllib3.response.HTTPResponse, "close", close_then_fail)


def _make_connections_fail_to_close(monkeypatch, *urls, failure_type=OSError, raised=None):
    """Make each urllib3 connection to ``urls`` close, then raise ``failure_type("close failed")``.

    Each failure raised is added to ``raised``, if given. Called again, it
    adds more failing hosts.
    """
    ports = {urllib.parse.urlsplit(url).port for url in urls}
    close = urllib3.connection.HTTPConnection.close

    def close_then_fail(self):
        close(self)
        if self.port in ports:
            failure = failure_type("close failed")
            if raised is not None:
                raised.append(failure)
            raise failure

    monkeypatch.setattr(urllib3.connection.HTTPConnection, "close", close_then_fail)


@pytest.mark.parametrize("close_fails", [False, True], ids=["closes", "close-fails"])
@pytest.mark.parametrize(
    "target",
    [
        "requests.adapters.extract_cookies_to_jar",
        "requests.sessions.extract_cookies_to_jar",
        "requests.models.Response.iter_content",
    ],
    ids=["while-building-the-response", "after-the-response", "while-reading-the-body"],
)
def test_get_bytes_raises_an_interrupt_after_an_answer_unchanged_and_closes_the_answer(
    target, close_fails, slots, monkeypatch
):
    # requests stores an answer's cookies twice: in requests.adapters while it
    # builds the Response, and in requests.sessions once the adapter returns it.
    # get_bytes then reads the body with iter_content.
    def interrupt(*args, **kwargs):
        raise _Abort

    monkeypatch.setattr(target, interrupt)
    if close_fails:
        _make_answers_fail_to_close(monkeypatch)
    with LocalHttpServer(
        [respond(b"wrong")], routes={"/": until_client_closes(respond(b"ok"))}
    ) as server:
        with pytest.raises(_Abort) as excinfo:
            get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        assert type(excinfo.value) is _Abort
        assert len(server.requests) == 1  # not retried
        if close_fails:
            assert excinfo.value.__notes__ == [_CLOSE_FAILED_NOTE]
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: server.open_connections == 0), (
            f"{server.open_connections} connection(s) still open"
        )
        assert excinfo.value is not None  # still kept


def test_get_bytes_retries_an_http_error_whose_answer_fails_to_close(slots, monkeypatch):
    _make_answers_fail_to_close(monkeypatch)
    routes = {"/": until_client_closes(respond(b"busy", status="503 Service Unavailable"))}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        with pytest.raises(requests.HTTPError) as excinfo:
            get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        assert len(server.requests) == 2  # retried, as an HTTP error is
        assert excinfo.value.__notes__ == [_CLOSE_FAILED_NOTE]
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: server.open_connections == 0), (
            f"{server.open_connections} connection(s) still open"
        )


@pytest.mark.parametrize(
    "failure_type",
    [OSError, ValueError, _UnprintableError],
    ids=["os-error", "other-error", "unprintable-error"],
)
@pytest.mark.parametrize("ending", ["ok", "http-error", "interrupt"])
def test_get_bytes_fails_an_attempt_whose_connection_pool_fails_to_close(
    ending, failure_type, slots, monkeypatch
):
    """A pool that fails to close with the session fails the attempt, or is noted on an interrupt.

    The first host redirects to the second and keeps its connection alive, so
    the connection waits idle in its pool until the session closes it. The
    failure never takes the place of an interrupt, and it is retried, and
    reported, as a failed fetch, whatever the second host answered.
    """
    status = "503 Service Unavailable" if ending == "http-error" else "200 OK"
    with (
        LocalHttpServer([until_client_closes(respond(b"body", status=status))]) as target,
        LocalHttpServer([redirect(target.url, keep_alive=True)]) as source,
    ):
        raised: list[BaseException] = []
        _make_connections_fail_to_close(
            monkeypatch, source.url, failure_type=failure_type, raised=raised
        )
        if ending == "interrupt":
            extract = requests.sessions.extract_cookies_to_jar

            def interrupt_at_the_target(jar, request, response):
                if request.url == target.url:
                    raise _Abort
                extract(jar, request, response)

            monkeypatch.setattr(
                requests.sessions, "extract_cookies_to_jar", interrupt_at_the_target
            )
        with pytest.raises(BaseException) as excinfo:
            get_bytes(source.url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        if ending == "interrupt":
            assert type(excinfo.value) is _Abort
            assert len(raised) == 1
            assert excinfo.value.__notes__ == [_pool_close_failed_note(raised[0])]
            assert len(source.requests) + len(target.requests) == 2  # not retried
        else:
            assert len(raised) == 2
            _assert_failed_attempt(excinfo.value, source.url, raised[1])
            assert len(source.requests) + len(target.requests) == 4  # retried
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: source.open_connections + target.open_connections == 0), (
            f"{source.open_connections + target.open_connections} connection(s) still open"
        )
        assert excinfo.value is not None  # still kept


def test_get_bytes_closes_the_session_when_closing_an_answer_is_interrupted(slots, monkeypatch):
    """An interrupt while closing the last answer is raised once the session has closed its pools.

    The first host redirects to the second and keeps its connection alive, so
    the connection waits idle in its pool. An interrupt is raised once the
    second answer arrives, and closing that answer raises another, which is
    raised in its place.
    """
    with (
        LocalHttpServer([until_client_closes(respond(b"body"))]) as target,
        LocalHttpServer([redirect(target.url, keep_alive=True)]) as source,
    ):
        extract = requests.sessions.extract_cookies_to_jar
        close = requests.models.Response.close
        raised: list[BaseException] = []

        def interrupt_at_the_target(jar, request, response):
            if request.url == target.url:
                raise _Abort("answered")
            extract(jar, request, response)

        def close_then_interrupt(self):
            close(self)
            if self.url == target.url:
                raised.append(_Abort("closing"))
                raise raised[-1]

        monkeypatch.setattr(requests.sessions, "extract_cookies_to_jar", interrupt_at_the_target)
        monkeypatch.setattr(requests.models.Response, "close", close_then_interrupt)
        with pytest.raises(_Abort) as excinfo:
            get_bytes(source.url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        assert len(raised) == 1
        assert excinfo.value is raised[0]
        assert len(source.requests) + len(target.requests) == 2  # not retried
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: source.open_connections + target.open_connections == 0), (
            f"{source.open_connections + target.open_connections} connection(s) still open"
        )


@pytest.mark.parametrize(
    "failure_type",
    [OSError, ValueError, _UnprintableError, _Abort],
    ids=["os-error", "other-error", "unprintable-error", "interrupt"],
)
def test_get_bytes_fails_an_attempt_whose_answer_fails_to_close_after_its_body(
    failure_type, slots, monkeypatch
):
    """A response that fails to close once its whole body is read fails the attempt.

    A failure is retried as a failed fetch, as any failure after an answer is,
    and an interrupt is raised unchanged.
    """
    close = requests.models.Response.close
    raised: list[BaseException] = []

    def close_then_fail(self):
        close(self)
        raised.append(failure_type("close failed"))
        raise raised[-1]

    monkeypatch.setattr(requests.models.Response, "close", close_then_fail)
    with LocalHttpServer([until_client_closes(respond(b"ok"))]) as server:
        with pytest.raises(BaseException) as excinfo:
            get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        if failure_type is _Abort:
            assert excinfo.value is raised[-1]
            assert len(server.requests) == 1  # not retried
        else:
            _assert_failed_attempt(excinfo.value, server.url, raised[-1])
            assert len(server.requests) == 2  # retried
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: server.open_connections == 0), (
            f"{server.open_connections} connection(s) still open"
        )


def test_get_bytes_fails_an_attempt_whose_body_cannot_be_put_together(slots, monkeypatch):
    """Putting the body together comes after the answer, so a failure there fails the attempt.

    A chunk that is not bytes stands in for running out of memory there.
    """

    def not_bytes(self, chunk_size=1, decode_unicode=False):
        yield "not bytes"

    monkeypatch.setattr(requests.models.Response, "iter_content", not_bytes)
    with LocalHttpServer([until_client_closes(respond(b"ok"))]) as server:
        with pytest.raises(requests.RequestException) as excinfo:
            get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        assert type(excinfo.value) is requests.RequestException
        assert type(excinfo.value.__cause__) is TypeError
        assert len(server.requests) == 2  # retried
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: server.open_connections == 0), (
            f"{server.open_connections} connection(s) still open"
        )


def test_get_bytes_stops_at_once_when_a_pool_it_evicts_raises_an_interrupt(slots, monkeypatch):
    """The first host's pool is evicted on the way to the eleventh, which is never asked.

    The interrupt is raised unchanged, and every other pool is closed with the session.
    """
    servers = _redirect_chain(12, until_client_closes(respond(b"ok")))
    raised: list[BaseException] = []
    _make_connections_fail_to_close(monkeypatch, servers[0].url, failure_type=_Abort, raised=raised)
    with contextlib.ExitStack() as stack:
        for server in servers:
            stack.enter_context(server)
        with pytest.raises(_Abort) as excinfo:
            get_bytes(servers[0].url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        assert len(raised) == 1
        assert excinfo.value is raised[0]
        assert [len(server.requests) for server in servers] == [1] * 10 + [0, 0]
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: sum(server.open_connections for server in servers) == 0), [
            server.open_connections for server in servers
        ]


def test_get_bytes_closes_every_other_pool_before_raising_an_interrupt_from_one(slots, monkeypatch):
    """urllib3 takes every pool out before it closes the first, so an interrupt waits for the rest.

    The session closes the pools of the last ten hosts in the order they were
    first used. The sixth's and the eighth's raise interrupts, and the
    tenth's fails: every pool is still closed, the first interrupt is raised,
    and the failure is noted on it.
    """
    servers = _redirect_chain(12, until_client_closes(respond(b"ok")))
    aborts: list[BaseException] = []
    failures: list[BaseException] = []
    _make_connections_fail_to_close(
        monkeypatch, servers[5].url, servers[7].url, failure_type=_Abort, raised=aborts
    )
    _make_connections_fail_to_close(monkeypatch, servers[9].url, raised=failures)
    with contextlib.ExitStack() as stack:
        for server in servers:
            stack.enter_context(server)
        with pytest.raises(_Abort) as excinfo:
            get_bytes(servers[0].url, connect_timeout=1, read_timeout=2, deadline=5, attempts=2)
        assert len(aborts) == 2
        assert excinfo.value is aborts[0]
        assert len(failures) == 1
        assert excinfo.value.__notes__ == [_pool_close_failed_note(failures[0])]
        assert [len(server.requests) for server in servers] == [1] * 12  # not retried
        assert wait_until(lambda: slots.used == 0)

        assert wait_until(lambda: sum(server.open_connections for server in servers) == 0), [
            server.open_connections for server in servers
        ]


class _Closable:
    def __init__(self, failure: BaseException | None) -> None:
        self.failure = failure
        self.closed = False

    def close(self) -> None:
        self.closed = True
        if self.failure is not None:
            raise self.failure


@pytest.mark.parametrize("failure_type", [OSError, ValueError], ids=["os-error", "other-error"])
@pytest.mark.parametrize("error_type", [_Abort, RuntimeError], ids=["interrupt", "ordinary-error"])
def test_a_failure_to_close_an_answer_is_noted_on_the_error_being_raised(error_type, failure_type):
    error = error_type("original")
    failure = failure_type("close failed")
    answer = _Closable(failure)
    bounded_http._close_noting_failure(answer, error)
    assert answer.closed
    assert error.__notes__ == [f"closing the answer also failed: {failure!r}"]


def test_closing_everything_raises_the_first_interrupt_once_the_rest_are_closed():
    first, second = _Abort("first"), _Abort("second")
    closables = [_Closable(first), _Closable(None), _Closable(OSError("socket")), _Closable(second)]
    error = RuntimeError("original")
    with pytest.raises(_Abort) as excinfo:
        bounded_http._close_all_noting_failures(
            [(closable, "the answer") for closable in closables], error
        )
    assert excinfo.value is first
    assert all(closable.closed for closable in closables)
    assert error.__notes__ == ["closing the answer also failed: OSError('socket')"]


def test_an_interrupt_while_closing_an_answer_is_raised_in_place_of_the_error():
    interrupt = _Abort()
    with pytest.raises(_Abort) as excinfo:
        bounded_http._close_noting_failure(_Closable(interrupt), RuntimeError("original"))
    assert excinfo.value is interrupt


class _UnnoteableError(RuntimeError):
    """An error whose ``add_note`` raises ``failure``."""

    def __init__(self, failure: BaseException) -> None:
        super().__init__("original")
        self.failure = failure

    def add_note(self, note: str) -> None:
        raise self.failure


def _with_fixed_notes() -> RuntimeError:
    error = RuntimeError("original")
    error.__notes__ = ("fixed",)  # add_note raises TypeError for anything not a list
    return error


@pytest.mark.parametrize(
    "unnoteable",
    [_with_fixed_notes, lambda: _UnnoteableError(MemoryError())],
    ids=["notes-not-a-list", "noting-fails"],
)
def test_a_failure_to_close_is_dropped_when_the_error_cannot_take_notes(unnoteable):
    error = unnoteable()
    notes = getattr(error, "__notes__", None)
    bounded_http._close_noting_failure(_Closable(OSError("socket")), error)
    assert getattr(error, "__notes__", None) == notes


def test_an_interrupt_while_noting_a_failure_to_close_is_raised_in_place_of_the_error():
    interrupt = _Abort()
    with pytest.raises(_Abort) as excinfo:
        bounded_http._close_noting_failure(
            _Closable(OSError("socket")), _UnnoteableError(interrupt)
        )
    assert excinfo.value is interrupt


@pytest.mark.parametrize(
    "repr_failure", [RuntimeError("no repr"), MemoryError()], ids=["error", "out-of-memory"]
)
def test_a_failure_to_close_whose_repr_fails_is_noted_by_its_default_repr(repr_failure):
    error = _Abort("original")
    failure = _UnprintableError("close failed", repr_failure)
    bounded_http._close_noting_failure(_Closable(failure), error)
    assert error.__notes__ == [f"closing the answer also failed: {object.__repr__(failure)}"]


def test_an_interrupt_while_showing_a_failure_to_close_is_raised_in_place_of_the_error():
    interrupt = _Abort()
    failure = _UnprintableError("close failed", interrupt)
    with pytest.raises(_Abort) as excinfo:
        bounded_http._close_noting_failure(_Closable(failure), RuntimeError("original"))
    assert excinfo.value is interrupt


@pytest.mark.parametrize(
    "repr_failure", [RuntimeError("no repr"), MemoryError()], ids=["error", "out-of-memory"]
)
def test_a_failed_attempt_whose_error_repr_fails_shows_its_default_repr(repr_failure):
    error = _UnprintableError("boom", repr_failure)
    failed = bounded_http._failed_attempt("http://example.test/", error)
    assert type(failed) is requests.RequestException
    assert str(failed) == (
        f"fetching http://example.test/ failed after an answer arrived: {object.__repr__(error)}"
    )


def test_get_bytes_leaves_no_response_for_the_cycle_collector(slots, monkeypatch):
    """Every response a call builds, and its adapter, is freed when it returns, with the cycle collector off.

    Each response refers to the adapter that built it, which keeps a list of
    the responses it built, and the caches of its pool managers close the
    pools they drop through an object the adapter keeps.
    """
    built = []
    build_response = bounded_http._DeadlineAdapter.build_response

    def recording(self, req, resp):
        response = build_response(self, req, resp)
        built.extend((weakref.ref(response), weakref.ref(self)))
        return response

    monkeypatch.setattr(bounded_http._DeadlineAdapter, "build_response", recording)
    routes = {"/": until_client_closes(redirect("/moved")), "/moved": respond(b"moved")}
    with LocalHttpServer([respond(b"wrong")], routes=routes) as server:
        collecting = gc.isenabled()
        gc.disable()
        try:
            assert get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=5) == b"moved"
            assert wait_until(lambda: slots.used == 0)
            assert len(built) == 4
            assert wait_until(lambda: all(ref() is None for ref in built)), [ref() for ref in built]
        finally:
            if collecting:
                gc.enable()


def test_get_bytes_raises_what_requests_raises_for_a_first_request_it_cannot_make(
    slots, monkeypatch
):
    # requests looks for the CA bundle before it connects, so this fails before
    # any answer arrives: it is not an answer requests cannot handle, and it is
    # not retried.
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/nonexistent/ca-bundle.pem")
    monkeypatch.setenv("NO_PROXY", "*")
    attempts = []
    get_once = bounded_http._get_once

    def counting(*args, **kwargs):
        attempts.append(args)
        return get_once(*args, **kwargs)

    monkeypatch.setattr(bounded_http, "_get_once", counting)
    with pytest.raises(OSError, match="CA certificate bundle") as excinfo:
        get_bytes("https://127.0.0.1:1/", connect_timeout=1, read_timeout=1, deadline=5, attempts=2)
    assert type(excinfo.value) is OSError  # a RequestException is an OSError too
    assert len(attempts) == 1
    assert wait_until(lambda: slots.used == 0)


def test_bounded_http_imports_without_what_urllib3_1_lacks():
    # requests allows urllib3 from 1.21.1, and urllib3 1 has no BaseHTTPResponse.
    code = (
        "import urllib3\n"
        "vars(urllib3).pop('BaseHTTPResponse', None)\n"
        "import axiom_corpus.corpus.bounded_http\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=60)


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
        assert wait_until(lambda: slots.used == 0, within=_SLACK_SECONDS)


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
    assert wait_until(lambda: slots.used == 0)


def test_get_bytes_deadline_ends_a_server_that_trickles_its_body(slots):
    # A declared 10 MB at one byte every 20 ms would take about 55 hours.
    with LocalHttpServer([trickle_body(0.02)]) as server:
        elapsed, error = _elapsed(
            lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.6)
        )

    assert isinstance(error, requests.Timeout)
    assert 0.6 <= elapsed < 0.6 + _SLACK_SECONDS
    assert wait_until(lambda: slots.used == 0)


def test_get_bytes_caps_workers_left_open_by_a_trickling_server(slots, monkeypatch):
    """Timed-out calls cannot pile up open workers: with every slot held, a call does not start.

    A worker left reading the trickle would end at its read timeout, cut to
    the 0.3 s deadline, if the machine stalled that long between two bytes,
    and a later call could then take its slot. So the first three workers are
    also held, in the worker, until the calls are done: every slot stays
    taken whatever the machine does, and the other five calls are refused.
    Workers are counted in the workers themselves.
    """
    workers = RunningCount(bounded_http._get_with_retries, hold=3)
    monkeypatch.setattr(bounded_http, "_get_with_retries", workers)
    with LocalHttpServer([trickle_headers(0.02)]) as server:
        errors = []
        try:
            for _ in range(8):
                elapsed, error = _elapsed(
                    lambda: get_bytes(server.url, connect_timeout=1, read_timeout=2, deadline=0.3)
                )
                errors.append(error)
                assert elapsed < 0.3 + _SLACK_SECONDS
        finally:
            workers.release()
        refused = [error for error in errors if "fetch threads stayed busy" in str(error)]

        assert all(isinstance(error, requests.Timeout) for error in errors)
        assert len(refused) == 5
        assert all("0.3s deadline" in str(error) for error in refused)
        assert wait_until(lambda: workers.started == 3)
        assert workers.most_running <= 3

        url = server.url

    assert wait_until(lambda: slots.used == 0)
    assert wait_until(lambda: _open_workers(url) == 0)
    assert workers.running == 0
    with LocalHttpServer([respond(b"recovered")]) as server:
        assert get_bytes(server.url, connect_timeout=1, read_timeout=1, deadline=5) == b"recovered"


def test_get_bytes_caps_workers_left_open_by_concurrent_callers(slots, monkeypatch):
    """Eight callers trying 40 URLs on a trickling server run at most 3 workers at once.

    The first three workers are held until the calls are done, as in the
    test above, so the other 37 calls are refused.
    """
    workers = RunningCount(bounded_http._get_with_retries, hold=3)
    monkeypatch.setattr(bounded_http, "_get_with_retries", workers)
    # The server closes before the callers are joined, so a get_bytes that
    # failed to return at its deadline fails this test instead of hanging it.
    with (
        ThreadPoolExecutor(max_workers=8) as callers,
        LocalHttpServer([trickle_headers(0.02)]) as server,
    ):
        try:
            errors = list(
                callers.map(
                    lambda _: _elapsed(
                        lambda: get_bytes(
                            server.url, connect_timeout=1, read_timeout=2, deadline=0.3
                        )
                    )[1],
                    range(40),
                    timeout=30,
                )
            )
        finally:
            workers.release()

        refused = [error for error in errors if "fetch threads stayed busy" in str(error)]

        assert all(isinstance(error, requests.Timeout) for error in errors)
        assert len(refused) == 37
        assert wait_until(lambda: workers.started == 3)
        assert workers.most_running <= 3

    assert wait_until(lambda: slots.used == 0)


def test_get_bytes_never_exceeds_the_cap_under_heavy_thread_switching(monkeypatch, slots):
    """Sixteen callers on four slots: never more than four workers at once, no slot lost."""
    # Counted in the workers themselves, between taking over a slot and giving
    # it back, so a connection the server has yet to tidy up is not counted.
    workers = RunningCount(bounded_http._get_with_retries)
    monkeypatch.setattr(bounded_http, "_get_with_retries", workers)
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
            assert wait_until(lambda: slots.used == 0)
    finally:
        sys.setswitchinterval(switch_interval)

    assert 1 <= workers.most_running <= 4
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
            assert wait_until(lambda: _callers_waiting_for_a_slot(cap) == 2)
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
        assert wait_until(lambda: _open_workers(server.url) == 0)
        assert server.requests == []
        assert slots.used == 0


def test_get_bytes_leaves_the_slot_to_a_worker_that_took_it_before_the_interrupt(
    monkeypatch, slots
):
    class InterruptedAfterRequest(threading.Thread):
        def start(self) -> None:
            super().start()
            # Ctrl-C after the worker took the slot and sent its request.
            assert wait_until(lambda: len(server.requests) == 1)
            raise KeyboardInterrupt

    _patch_worker_threads(monkeypatch, InterruptedAfterRequest)
    answer = threading.Event()
    with LocalHttpServer([respond(b"ok", gate=answer)]) as server:
        with pytest.raises(KeyboardInterrupt):
            get_bytes(server.url, connect_timeout=1, read_timeout=5, deadline=10)
        assert slots.used == 1  # still the worker's, which is waiting for its answer

        answer.set()
        assert wait_until(lambda: slots.used == 0)  # it gives it back when it ends
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
        assert wait_until(lambda: len(server.requests) == 1)
        assert slots.used == 1  # the worker's, which is waiting for its answer

        answer.set()
        assert wait_until(lambda: _open_workers(server.url) == 0)
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
    assert wait_until(lambda: _open_workers(url) == 0)

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

    def close(self) -> None:
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
# A pause that returns past the deadline: the next attempt must not be made
# with the time left, now below zero, as its timeouts.
@example(
    connect_timeout=10,
    read_timeout=20,
    deadline=1.0,
    retry_delay=0.5,
    oversleep=2.0,
    outcomes=[("status", 503), ("answer", 0)],
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
