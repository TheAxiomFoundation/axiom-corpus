"""HTTP GETs that finish within a wall-clock deadline.

``requests`` applies ``timeout`` to each socket operation, not to a request. A
host that drops connection attempts costs one full connect timeout per attempt,
a server that sends its status line, headers or body a few bytes at a time
never trips a read timeout at all, and a DNS lookup has no timeout of its own.
On 2026-10-24 two 30-second connect timeouts to www.oregonlegislature.gov
(``timeout=30``, two attempts) outlasted CI's 60-second per-test limit, so the
real-source smoke test that skips when its source cannot be fetched failed the
required ``test`` job instead (axiom-corpus CI run 40042942746).

``get_bytes`` gives each request explicit connect and read timeouts, cut to the
time left when it is started, and gives the whole call (every attempt, the
pauses between them, redirects, the DNS lookup, the headers and the body) one
deadline. No request, a redirect's included, is started once the deadline has
passed; one started just before it can still go out after it if its DNS lookup,
which has no timeout, returns late. The attempts run on a daemon worker thread
that the caller waits on for at most the deadline, so the call returns the body
or raises by then whatever the server does.

At the deadline the caller raises ``requests.Timeout`` and leaves the worker
behind. A worker stops at its next socket timeout, at the next body chunk after
the deadline, before the next request (a redirect's) after it, or when the
server closes the connection. Every response, connection and connection pool
it opens is closed by the time it ends, however it ends, unless closing one
fails: a failure to close one is noted on the error being raised, or, if
nothing else failed, fails the attempt. Once an answer has arrived, any
failure but an interrupt fails the attempt as a ``requests.RequestException``.
But a server that keeps trickling bytes, or a DNS lookup that hangs, can hold
a worker open longer, so workers
are capped process-wide (``MAX_FETCH_THREADS``): a call takes a slot before it
starts its worker, and the worker gives the slot back when it ends. While every
slot is taken, a call waits for one within its own deadline and otherwise
raises ``requests.Timeout`` without making a request. However many URLs are
tried, and whatever the servers do, at most ``MAX_FETCH_THREADS`` workers are
making requests at once. A call interrupted (Ctrl-C) while starting its worker,
before the worker takes over its slot, gives the slot back itself, and the
worker then makes no request.
"""

from __future__ import annotations

import contextlib
import math
import threading
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import requests
from requests.adapters import HTTPAdapter

if TYPE_CHECKING:
    # requests allows urllib3 1, which has no BaseHTTPResponse.
    from urllib3 import BaseHTTPResponse, HTTPConnectionPool, PoolManager

# Fetch threads, process-wide, that may be making requests at once, counting
# those still open after the call that started them gave up.
MAX_FETCH_THREADS = 32
_CHUNK_BYTES = 64 * 1024


class _Slots:
    """How many fetch threads hold a slot, out of ``limit``, and a condition on it."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0
        self.changed = threading.Condition()

    def release(self) -> None:
        with self.changed:
            self.used -= 1
            self.changed.notify_all()


_SLOTS = _Slots(MAX_FETCH_THREADS)


class _Call:
    """One call's result, and which of the caller and the worker owns its slot."""

    def __init__(self) -> None:
        self.finished = threading.Event()
        # The caller has taken a slot for the worker.
        self.reserved = False
        # The worker has started and owns the slot; it gives it back when it ends.
        self.claimed = False
        # The caller was interrupted before the worker started and gave the slot
        # back itself; the worker, if it starts at all, does nothing.
        self.cancelled = False
        self.body: bytes | None = None
        self.error: BaseException | None = None


def get_bytes(
    url: str,
    *,
    connect_timeout: float,
    read_timeout: float,
    deadline: float,
    attempts: int = 1,
    retry_delay: float = 0.0,
    headers: Mapping[str, str] | None = None,
) -> bytes:
    """Return the body of a successful GET of ``url`` within ``deadline`` seconds.

    Makes up to ``attempts`` attempts, pausing ``retry_delay`` seconds after a
    failed one, and retries every ``requests.RequestException``, an HTTP error
    status included, while time is left after the pause. An attempt makes one
    request, and one more for each redirect it follows. No request, a
    redirect's included, is started once the deadline has passed. A network or
    HTTP failure, an answer ``requests`` cannot handle (a redirect whose
    Location is not UTF-8, say), or a failure to close what an attempt opened
    raises the last attempt's ``requests.RequestException``, or
    ``requests.Timeout`` when the deadline
    passes first or no fetch slot comes free in time. A first request that
    ``requests`` cannot make fails with what ``requests`` raises for it: a
    ``requests.RequestException`` (an invalid URL, say) is retried like any
    other, and anything else (a missing CA bundle's ``OSError``, say) is raised
    at once. A redirect to such a URL is an answer ``requests`` cannot handle.
    """
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, not {attempts}")
    for name, value in (
        ("connect_timeout", connect_timeout),
        ("read_timeout", read_timeout),
        ("deadline", deadline),
    ):
        if not (math.isfinite(value) and value > 0):
            raise ValueError(f"{name} must be a positive finite number, not {value!r}")
    if not (math.isfinite(retry_delay) and retry_delay >= 0):
        raise ValueError(f"retry_delay must be a non-negative finite number, not {retry_delay!r}")
    give_up_at = time.monotonic() + deadline
    slots = _SLOTS
    call = _Call()

    def run() -> None:
        with slots.changed:
            if call.cancelled:
                return
            call.claimed = True
        try:
            call.body = _get_with_retries(
                url,
                headers=dict(headers or {}),
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                give_up_at=give_up_at,
                attempts=attempts,
                retry_delay=retry_delay,
            )
        except BaseException as exc:  # raised again on the caller's thread
            call.error = exc
        finally:
            slots.release()
            call.finished.set()

    try:
        with slots.changed:
            has_room = slots.changed.wait_for(
                lambda: slots.used < slots.limit,
                timeout=max(0.0, give_up_at - time.monotonic()),
            )
            if not has_room:
                raise requests.Timeout(
                    f"did not request {url}: all {slots.limit} fetch threads stayed busy "
                    f"for the whole {deadline:g}s deadline"
                )
            slots.used += 1
            call.reserved = True
        threading.Thread(target=run, name=f"get_bytes {url}", daemon=True).start()
    except BaseException:
        # Interrupted (Ctrl-C), or out of threads, after taking a slot but
        # before the worker took it over: give it back here, and stop the
        # worker if it starts later.
        with slots.changed:
            if call.reserved and not call.claimed:
                call.cancelled = True
                slots.used -= 1
                slots.changed.notify_all()
        raise
    # From here the slot is the worker's to give back, so an interrupted wait
    # leaves nothing to undo.
    if not call.finished.wait(timeout=max(0.0, give_up_at - time.monotonic())):
        raise requests.Timeout(f"no complete response from {url} within {deadline:g}s")
    if call.error is not None:
        raise call.error
    assert call.body is not None
    return call.body


def _get_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    connect_timeout: float,
    read_timeout: float,
    give_up_at: float,
    attempts: int,
    retry_delay: float,
) -> bytes:
    last_error: requests.RequestException | None = None
    for attempt in range(attempts):
        if attempt:
            if give_up_at - time.monotonic() <= retry_delay:
                # No time would be left for another attempt after the pause, so
                # the last failure stands, now rather than at the deadline.
                break
            time.sleep(retry_delay)
        remaining = give_up_at - time.monotonic()
        if remaining <= 0:
            break
        try:
            return _get_once(
                url,
                headers=headers,
                timeout=(min(connect_timeout, remaining), min(read_timeout, remaining)),
                give_up_at=give_up_at,
            )
        except requests.RequestException as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise requests.Timeout(f"no complete response from {url} before the deadline")


def _get_once(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[float, float],
    give_up_at: float,
) -> bytes:
    response = _open(url, headers=headers, timeout=timeout, give_up_at=give_up_at)
    # An answer has arrived, so whatever fails from here on, closing the
    # response included, fails this attempt.
    try:
        try:
            response.raise_for_status()
            chunks: list[bytes] = []
            for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
                if time.monotonic() >= give_up_at:
                    raise requests.Timeout(f"no complete response from {url} before the deadline")
                chunks.append(chunk)
        except BaseException as error:
            _close_noting_failure(response, error)
            raise
        response.close()
        return b"".join(chunks)
    except requests.RequestException:
        raise
    except Exception as error:
        raise _failed_attempt(url, error) from error


def _open(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[float, float],
    give_up_at: float,
) -> requests.Response:
    """Start a streaming GET of ``url``, as ``requests.get`` does, through ``_DeadlineAdapter``.

    Like ``requests.get``, it uses a session of its own, closed on return; the
    streaming response keeps its connection until it is closed. If ``requests``
    fails after an answer has arrived, or closing the session fails to close
    one of its connection pools, every answer is closed, and an ``Exception``
    that is not a ``requests.RequestException`` is raised as one; a
    ``BaseException`` such as ``KeyboardInterrupt`` is raised unchanged. An
    answer, session or pool that fails to close while an error is raised is
    noted on the error, not raised in its place; an interrupt while closing
    one is raised in its place once the others are closed.
    """
    opened: list[requests.Response] = []
    adapter = _DeadlineAdapter(url, give_up_at, opened)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    try:
        response = session.get(url, headers=headers, timeout=timeout, stream=True)
        session.close()
        if adapter.close_failures:
            raise adapter.close_failures[0]
    except BaseException as error:
        # requests can fail after a response arrives and before it hands
        # that response back, which then still holds its connection: a
        # redirect whose Location is not UTF-8 raises UnicodeDecodeError
        # before its body is read.
        _close_all_noting_failures(
            [*((answer, "the answer") for answer in opened), (session, "the session")], error
        )
        for failure in adapter.close_failures:
            if failure is not error:
                _note_close_failure(error, "a connection pool", failure)
        if (
            adapter.answered
            and isinstance(error, Exception)
            and not isinstance(error, requests.RequestException)
        ):
            raise _failed_attempt(url, error) from error
        raise
    finally:
        opened.clear()  # each response refers back to the adapter
    return response


class _DeadlineAdapter(HTTPAdapter):
    """Starts no request once ``give_up_at`` has passed, and cuts each one's timeouts to the time left.

    ``requests`` sends every request of a session through its adapter, each
    redirect it follows included, and closes the response before a redirect
    first, so this check comes right before each request is started and leaves
    no response open when it refuses one. A DNS lookup, which has no timeout,
    can still hold a request it started past the deadline. ``answered`` says
    whether an answer has arrived, and each response built from one is added
    to ``opened``. An answer whose response ``requests`` fails to build is
    closed here, since nothing else can reach it.

    The adapter is one call's, used by one thread, so it closes every
    connection pool it drops: when its pool manager's cache (ten pools; a
    redirect chain across hosts can pass that) evicts one, and when the
    session closes it. urllib3 2 leaves both to the garbage collector, so a
    connection a server kept alive stayed open for as long as anything still
    reached its pool, as a kept error's traceback can. A closed pool closes
    its idle connections, and any connection still in use when it is given
    back. A pool that fails to close is added to ``close_failures``, and the
    others are closed all the same (see ``_PoolCloser``).
    """

    def __init__(self, url: str, give_up_at: float, opened: list[requests.Response]) -> None:
        self._url = url
        self._give_up_at = give_up_at
        self._opened = opened
        self.answered = False
        self._pool_closer = _PoolCloser()
        self.close_failures = self._pool_closer.failures
        super().__init__()

    def init_poolmanager(
        self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any
    ) -> None:
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)  # type: ignore[no-untyped-call]  # untyped in the requests stubs
        self.poolmanager.pools.dispose_func = self._pool_closer

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> PoolManager:
        manager: PoolManager = super().proxy_manager_for(proxy, **proxy_kwargs)  # type: ignore[no-untyped-call]  # untyped in the requests stubs
        manager.pools.dispose_func = self._pool_closer
        return manager

    def close(self) -> None:
        closer = self._pool_closer
        closer.holding = True
        try:
            super().close()  # type: ignore[no-untyped-call]  # untyped in the requests stubs
        finally:
            closer.holding = False
            held, closer.held = closer.held, []
        if held:
            raise held[0]

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: None | float | tuple[float, float] | tuple[float, None] = None,
        verify: bool | str = True,
        cert: None | bytes | str | tuple[bytes | str, bytes | str] = None,
        proxies: Mapping[str, str] | None = None,
    ) -> requests.Response:
        read = timeout[1] if isinstance(timeout, tuple) else None
        if not isinstance(timeout, tuple) or read is None:
            raise TypeError(f"expected (connect, read) timeouts, not {timeout!r}")
        remaining = self._give_up_at - time.monotonic()
        if remaining <= 0:
            raise requests.Timeout(f"no complete response from {self._url} before the deadline")
        return super().send(
            request,
            stream=stream,
            timeout=(min(timeout[0], remaining), min(read, remaining)),
            verify=verify,
            cert=cert,
            proxies=proxies,
        )

    def build_response(
        self, req: requests.PreparedRequest, resp: BaseHTTPResponse
    ) -> requests.Response:
        self.answered = True
        try:
            response = super().build_response(req, resp)
        except BaseException as error:
            # requests stores the answer's cookies here, and http.cookiejar's
            # warning about a malformed one is raised under warnings-as-errors.
            _close_noting_failure(resp, error)
            raise
        self._opened.append(response)
        return response


class _PoolCloser:
    """Closes each connection pool a ``_DeadlineAdapter``'s pool managers drop.

    A pool that fails to close is added to ``failures``. An interrupt while
    one closes is raised at once when a request evicted it, which stops that
    request. But while the adapter closes (``holding``) it is held until the
    other pools are closed, since urllib3 takes every pool out of a manager
    before it closes the first; the first held is then raised. Not the
    adapter's own method, which would keep the adapter in a reference cycle.
    """

    def __init__(self) -> None:
        self.failures: list[Exception] = []
        self.holding = False
        self.held: list[BaseException] = []

    def __call__(self, pool: HTTPConnectionPool) -> None:
        try:
            pool.close()
        except Exception as error:  # the other pools are closed all the same
            self.failures.append(error)
        except BaseException as interrupt:
            if not self.holding:
                raise
            self.held.append(interrupt)


def _failed_attempt(url: str, error: Exception) -> requests.RequestException:
    """The failure of an attempt at ``url`` that ``error`` ended after an answer arrived."""
    return requests.RequestException(
        f"fetching {url} failed after an answer arrived: {_described(error)}"
    )


def _close_noting_failure(
    closable: requests.Response | requests.Session | BaseHTTPResponse,
    error: BaseException,
    *,
    what: str = "the answer",
) -> None:
    """Close ``closable`` while ``error`` is raised, adding a failure to close it to ``error``'s notes.

    An interrupt while closing is raised in place of ``error``.
    """
    try:
        closable.close()
    except Exception as close_error:
        _note_close_failure(error, what, close_error)


def _close_all_noting_failures(
    closables: list[tuple[requests.Response | requests.Session, str]], error: BaseException
) -> None:
    """Close each ``(closable, what)`` while ``error`` is raised, as ``_close_noting_failure`` does.

    An interrupt while closing one, or noting a failure to, is raised in place
    of ``error`` once the others are closed; the first, if there are more.
    """
    interrupt: BaseException | None = None
    for closable, what in closables:
        try:
            _close_noting_failure(closable, error, what=what)
        except BaseException as raised:
            if interrupt is None:
                interrupt = raised
    if interrupt is not None:
        raise interrupt


def _note_close_failure(error: BaseException, what: str, failure: Exception) -> None:
    """Note on ``error`` that closing ``what`` failed with ``failure``.

    The note is dropped if ``error``'s notes cannot take it; an interrupt is raised.
    """
    with contextlib.suppress(Exception):  # __notes__ set to something not a list, say
        error.add_note(f"closing {what} also failed: {_described(failure)}")


def _described(error: BaseException) -> str:
    """``repr(error)``, or, if its ``__repr__`` fails, the default one; an interrupt is raised."""
    try:
        return repr(error)
    except Exception:
        return object.__repr__(error)
