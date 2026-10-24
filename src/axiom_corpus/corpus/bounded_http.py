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
time left when it is sent, and gives the whole call (every attempt, the pauses
between them, redirects, the DNS lookup, the headers and the body) one
deadline. No request, a redirect's included, is sent once the deadline has
passed. The attempts run on a daemon worker thread that the caller waits on for
at most the deadline, so the call returns the body or raises by then whatever
the server does.

At the deadline the caller raises ``requests.Timeout`` and leaves the worker
behind. A worker stops at its next socket timeout, at the next body chunk after
the deadline, before the next request (a redirect's) after it, or when the
server closes the connection, but a server that keeps trickling bytes, or a DNS
lookup that hangs, can hold it open longer. Every response a worker opens is
closed when it ends, however it ends. So workers are capped process-wide (``MAX_FETCH_THREADS``): a call
takes a slot before it starts its worker, and the worker gives the slot back
when it ends. While every slot is taken, a call waits for one within its own
deadline and otherwise raises ``requests.Timeout`` without making a request.
However many URLs are tried, and whatever the servers do, at most
``MAX_FETCH_THREADS`` workers are making requests at once. A call interrupted
(Ctrl-C) while starting its worker gives the slot back itself, and the worker
then makes no request.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Mapping

import requests
from requests.adapters import HTTPAdapter
from urllib3 import PoolManager

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
    redirect's included, is sent once the deadline has passed. A network or
    HTTP failure raises the last attempt's
    ``requests.RequestException``, or ``requests.Timeout`` when the deadline
    passes first or no fetch slot comes free in time. A request that
    ``requests`` cannot make at all (a malformed URL, say) raises what
    ``requests`` raises for it.
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
    with _open(url, headers=headers, timeout=timeout, give_up_at=give_up_at) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
            if time.monotonic() >= give_up_at:
                raise requests.Timeout(f"no complete response from {url} before the deadline")
            chunks.append(chunk)
        return b"".join(chunks)


def _open(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[float, float],
    give_up_at: float,
) -> requests.Response:
    """Start a streaming GET of ``url``, as ``requests.get`` does, through ``_DeadlineAdapter``.

    Like ``requests.get``, it uses a session of its own, closed on return; the
    streaming response keeps its connection until it is closed.
    """
    adapter = _DeadlineAdapter(url, give_up_at)
    with requests.Session() as session:
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            return session.get(url, headers=headers, timeout=timeout, stream=True)
        except requests.RequestException as error:
            # requests attaches the last response to some errors without closing
            # it (TooManyRedirects, after reading its body); a kept error would
            # then keep its connection open.
            if error.response is not None:
                error.response.close()
            raise


class _DeadlineAdapter(HTTPAdapter):
    """Sends no request once ``give_up_at`` has passed, and cuts each one's timeouts to the time left.

    ``requests`` sends every request of a session through its adapter, each
    redirect it follows included, and closes the response before a redirect
    first, so this check comes right before each request goes out and leaves
    no response open when it refuses one.
    """

    def __init__(self, url: str, give_up_at: float) -> None:
        super().__init__()
        self._url = url
        self._give_up_at = give_up_at

    def close(self) -> None:
        # urllib3 2's PoolManager.clear() forgets its pools without closing
        # them, so a kept-alive connection would stay open for as long as
        # anything still reaches its pool, as a kept error's traceback can.
        # A closed pool closes its idle connections, and closes any connection
        # still in use when that is given back.
        managers: list[PoolManager] = [self.poolmanager, *self.proxy_manager.values()]
        for manager in managers:
            # The pools' container refuses plain iteration; keys() is a copy.
            for key in manager.pools.keys():  # noqa: SIM118
                manager.pools[key].close()
        super().close()  # type: ignore[no-untyped-call]  # untyped in the requests stubs

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
