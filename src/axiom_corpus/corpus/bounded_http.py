"""HTTP GETs that finish within a wall-clock deadline.

``requests`` applies ``timeout`` to each socket operation, not to a request. A
host that drops connection attempts costs one full connect timeout per attempt,
a server that sends its status line, headers or body a few bytes at a time
never trips a read timeout at all, and a DNS lookup has no timeout of its own.
On 2026-10-24 two 30-second connect timeouts to www.oregonlegislature.gov
(``timeout=30``, two attempts) outlasted CI's 60-second per-test limit, so the
real-source smoke test that skips when its source cannot be fetched failed the
required ``test`` job instead (axiom-corpus CI run 40042942746).

``get_bytes`` gives each attempt explicit connect and read timeouts, cut to the
time left, and gives the whole call (every attempt, the pauses between them,
redirects, the DNS lookup, the headers and the body) one deadline. The attempts
run on a daemon worker thread that the caller waits on for at most the
deadline, so the call returns the body or raises by then whatever the server
does.

At the deadline the caller raises ``requests.Timeout`` and leaves the worker
behind. A worker stops at its next socket timeout, at the next body chunk or
redirect after the deadline, or when the server closes the connection, but a
server that keeps trickling bytes, or a DNS lookup that hangs, can hold it open
longer. So workers are capped process-wide (``MAX_FETCH_THREADS``): a call
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

    Makes up to ``attempts`` requests, pausing ``retry_delay`` seconds after a
    failed one, and retries every ``requests.RequestException``, an HTTP error
    status included, while time is left after the pause. No attempt starts,
    and no redirect is followed, once the deadline has passed. A network or HTTP failure raises the last attempt's
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
    def stop_redirects_at_the_deadline(
        response: requests.Response, *args: object, **kwargs: object
    ) -> requests.Response:
        # requests runs this hook on every response before it follows a redirect.
        if response.is_redirect and time.monotonic() >= give_up_at:
            raise requests.Timeout(f"no complete response from {url} before the deadline")
        return response

    with requests.get(
        url,
        headers=headers,
        timeout=timeout,
        stream=True,
        hooks={"response": stop_redirects_at_the_deadline},
    ) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
            if time.monotonic() >= give_up_at:
                raise requests.Timeout(f"no complete response from {url} before the deadline")
            chunks.append(chunk)
        return b"".join(chunks)
