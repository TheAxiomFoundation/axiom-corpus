"""HTTP GETs that finish within a wall-clock deadline.

``requests`` applies ``timeout`` to each socket operation, not to a request. A
host that drops connection attempts costs one full connect timeout per attempt,
and a server that sends its status line, headers or body a few bytes at a time
never trips a read timeout at all. On 2026-10-24 two 30-second connect
timeouts to www.oregonlegislature.gov (``timeout=30``, two attempts) outlasted
CI's 60-second per-test limit, so the real-source smoke test that skips when
its source cannot be fetched failed the required ``test`` job instead
(axiom-corpus CI run 40042942746).

``get_bytes`` gives each attempt explicit connect and read timeouts, cut to the
time left, and gives the whole call (every attempt, the pauses between them,
the headers and the body) one deadline. The attempts run on a daemon thread
that the caller waits on for at most the deadline, so the call returns the body
or raises ``requests.RequestException`` by then whatever the server does. At
the deadline the caller raises ``requests.Timeout`` and abandons the thread,
which stops at its next body chunk or socket timeout; nothing waits for it.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from concurrent.futures import Future, wait

import requests

_CHUNK_BYTES = 64 * 1024


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
    status included. No attempt starts once the deadline has passed. Raises the
    last attempt's error, or ``requests.Timeout`` if the deadline passes first.
    """
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, not {attempts}")
    if connect_timeout <= 0 or read_timeout <= 0 or deadline <= 0:
        raise ValueError("connect_timeout, read_timeout and deadline must be positive")
    if retry_delay < 0:
        raise ValueError(f"retry_delay must not be negative, not {retry_delay}")
    give_up_at = time.monotonic() + deadline
    abandoned = threading.Event()
    outcome: Future[bytes] = Future()

    def run() -> None:
        try:
            body = _get_with_retries(
                url,
                headers=dict(headers or {}),
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                give_up_at=give_up_at,
                attempts=attempts,
                retry_delay=retry_delay,
                abandoned=abandoned,
            )
        except BaseException as exc:  # handed to the caller by outcome.result()
            outcome.set_exception(exc)
        else:
            outcome.set_result(body)

    threading.Thread(target=run, name=f"get_bytes {url}", daemon=True).start()
    try:
        done, _ = wait((outcome,), timeout=deadline)
    finally:
        # Also on success, and when the wait itself is interrupted (Ctrl-C).
        abandoned.set()
    if not done:
        raise requests.Timeout(f"no complete response from {url} within {deadline:g}s")
    return outcome.result()


def _get_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    connect_timeout: float,
    read_timeout: float,
    give_up_at: float,
    attempts: int,
    retry_delay: float,
    abandoned: threading.Event,
) -> bytes:
    last_error: requests.RequestException | None = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(min(retry_delay, max(0.0, give_up_at - time.monotonic())))
        remaining = give_up_at - time.monotonic()
        if remaining <= 0 or abandoned.is_set():
            break
        try:
            return _get_once(
                url,
                headers=headers,
                timeout=(min(connect_timeout, remaining), min(read_timeout, remaining)),
                give_up_at=give_up_at,
                abandoned=abandoned,
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
    abandoned: threading.Event,
) -> bytes:
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
            if abandoned.is_set() or time.monotonic() >= give_up_at:
                raise requests.Timeout(f"no complete response from {url} before the deadline")
            chunks.append(chunk)
        return b"".join(chunks)
