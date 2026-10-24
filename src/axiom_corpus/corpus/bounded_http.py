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
the DNS lookup, the headers and the body) one deadline. The attempts run on a
daemon worker thread that the caller waits on for at most the deadline, so the
call returns the body or raises by then whatever the server does.

At the deadline the caller raises ``requests.Timeout`` and leaves the worker
behind. A worker stops at its next socket timeout, at the next body chunk after
the deadline, or when the server closes the connection, but a server that keeps
trickling bytes, or a DNS lookup that hangs, can hold it open longer. Such
stragglers are capped process-wide (``MAX_STRAGGLERS``): while the cap is
reached, a new call waits, within its own deadline, for one to finish, and
never starts a request after its deadline. So a dead or trickling source costs
at most the callers' own threads plus the cap, however many URLs are tried.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Mapping

import requests

# Worker threads, process-wide, that may still be open after the call that
# started them gave up. Healthy calls never count against it.
MAX_STRAGGLERS = 16
_CHUNK_BYTES = 64 * 1024


class _Stragglers:
    """A count of workers that outlived their call, and a condition on it."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.count = 0
        self.changed = threading.Condition()


_STRAGGLERS = _Stragglers(MAX_STRAGGLERS)


class _Call:
    """What one call's worker produced, and whether the caller left it behind."""

    def __init__(self) -> None:
        self.finished = threading.Event()
        self.left_behind = False
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
    status included. No request starts once the deadline has passed. A network
    or HTTP failure raises the last attempt's ``requests.RequestException``, or
    ``requests.Timeout`` when the deadline passes first. A request that
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
    stragglers = _STRAGGLERS
    with stragglers.changed:
        has_room = stragglers.changed.wait_for(
            lambda: stragglers.count < stragglers.limit,
            timeout=max(0.0, give_up_at - time.monotonic()),
        )
        if not has_room:
            raise requests.Timeout(
                f"did not request {url}: {stragglers.count} earlier requests are still "
                f"open past their deadlines (the limit is {stragglers.limit})"
            )
    call = _Call()

    def run() -> None:
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
            with stragglers.changed:
                call.finished.set()
                if call.left_behind:
                    stragglers.count -= 1
                    stragglers.changed.notify_all()

    threading.Thread(target=run, name=f"get_bytes {url}", daemon=True).start()
    try:
        call.finished.wait(timeout=max(0.0, give_up_at - time.monotonic()))
    finally:
        # Also when the wait itself is interrupted (Ctrl-C).
        with stragglers.changed:
            if not call.finished.is_set():
                call.left_behind = True
                stragglers.count += 1
    if call.left_behind:
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
            time.sleep(min(retry_delay, max(0.0, give_up_at - time.monotonic())))
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
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
            if time.monotonic() >= give_up_at:
                raise requests.Timeout(f"no complete response from {url} before the deadline")
            chunks.append(chunk)
        return b"".join(chunks)
