"""A fake clock for ``bounded_http``, so tests check the deadline on it, not on elapsed time.

``FakeClock`` takes the place of ``bounded_http._CLOCK``. Its time moves only
when the code under test pauses on it, when a fake server or transport says a
step took so long, or when a timed wait ends without what it waited for: the
wait then ends exactly at its deadline. A wait for a worker thread learns from
the worker itself when it finished on this clock, or that it will not finish
until the test lets it, so its outcome never depends on how fast the machine is
or how it schedules threads. Tests then assert what the clock reads.
"""

from __future__ import annotations

import heapq
import itertools
import queue
import threading
from collections.abc import Callable
from typing import Any

# A worker is still a real thread. One that never reports fails the test after
# this long instead of hanging it; no assertion depends on this bound.
_REPORT_WITHIN_SECONDS = 30.0
_HANGS = None


class FakeClock:
    """``monotonic``, ``sleep``, ``wait`` and ``wait_for`` on virtual time, plus what tests drive."""

    def __init__(self, now: float = 1_000.0) -> None:
        self._lock = threading.Lock()
        self._now = now
        self._due: list[tuple[float, int, Callable[[], None]]] = []
        self._order = itertools.count()
        self._reports: queue.Queue[float | None] = queue.Queue()
        self._released = threading.Event()
        # The deadline (``until``) of every timed wait, in the order they began.
        self.waits: list[float] = []

    # --- bounded_http._CLOCK -------------------------------------------------

    def monotonic(self) -> float:
        with self._lock:
            return self._now

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0, seconds
        self.advance(seconds)

    def wait(self, event: threading.Event, until: float) -> bool:
        """Wait for a worker's ``event`` until ``until``.

        The worker's report decides: it finished at a time on this clock, or it
        hangs. A worker that finished by ``until`` has its ``event`` set, and
        the wait returns true at once. Otherwise the wait ends at ``until``, as
        a real one would, and returns false.
        """
        self.waits.append(until)
        try:
            finished_at = self._reports.get(timeout=_REPORT_WITHIN_SECONDS)
        except queue.Empty:
            raise AssertionError("the worker never reported to the fake clock") from None
        if finished_at is not _HANGS and finished_at <= until:
            assert event.wait(_REPORT_WITHIN_SECONDS), "the worker reported, then never finished"
            return True
        self.advance_to(until)
        return False

    def wait_for(
        self, condition: threading.Condition, predicate: Callable[[], bool], until: float
    ) -> bool:
        """Wait until ``predicate()``, running what is due on the way, or until ``until``.

        Only a callback due by ``until`` (``call_at``) can change what the
        predicate reads, since no other thread waits on this clock here.
        """
        self.waits.append(until)
        while not predicate():
            due = self._next_due()
            if due is None or due > until:
                self.advance_to(until)
                return predicate()
            self.advance_to(due)
        return True

    # --- What tests, fake servers and fake workers drive ----------------------

    def advance(self, seconds: float) -> None:
        """Move on by ``seconds``, as a step that took that long."""
        assert seconds >= 0, seconds
        with self._lock:
            when = self._now + seconds
        self.advance_to(when)

    def advance_to(self, when: float) -> None:
        """Move to ``when``, never back, running each callback due by then in time order."""
        while True:
            with self._lock:
                if self._due and self._due[0][0] <= when:
                    at, _, callback = heapq.heappop(self._due)
                    self._now = max(self._now, at)
                else:
                    self._now = max(self._now, when)
                    return
            callback()

    def call_at(self, when: float, callback: Callable[[], None]) -> None:
        """Run ``callback`` when this clock reaches ``when``, as another thread's step would."""
        with self._lock:
            heapq.heappush(self._due, (when, next(self._order), callback))

    def finished(self) -> None:
        """A worker's report that it has finished, now on this clock."""
        self._reports.put(self.monotonic())

    def hang(self) -> None:
        """A worker's report that it will not finish; it then blocks until ``release``."""
        self._reports.put(_HANGS)
        assert self._released.wait(_REPORT_WITHIN_SECONDS), "a hanging worker was never released"

    def release(self) -> None:
        """Let every hanging worker go on."""
        self._released.set()

    def reporting(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """``function``, a worker's whole run, reporting to this clock when it ends."""

        def reported(*args: Any, **kwargs: Any) -> Any:
            try:
                return function(*args, **kwargs)
            finally:
                self.finished()

        return reported

    def _next_due(self) -> float | None:
        with self._lock:
            return self._due[0][0] if self._due else None
