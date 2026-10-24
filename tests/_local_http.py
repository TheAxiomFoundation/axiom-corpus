"""A local HTTP server that answers slowly, partly or not at all, for fetch tests.

``LocalHttpServer`` listens on 127.0.0.1 and gives each connection the
behaviour routed to its request path, or else the next of its behaviours (the
last one repeats), so a test can make a fetcher meet a server that never
answers, sends its headers or body a byte at a time, redirects, drops the
connection, or answers normally. Every behaviour returns when the server
closes, so no test leaves a thread blocked on a socket.

The server closes each connection when its behaviour returns, unless the
behaviour returns True to keep it alive for the client's next request, as
``redirect(..., keep_alive=True)`` does. A client that leaves a connection
open is invisible unless the behaviour waits for the client's close
(``until_client_closes``) or keeps the connection alive; ``open_connections``
then counts the connections a client has not yet closed.
"""

from __future__ import annotations

import gzip
import socket
import threading
import time
import warnings
from collections.abc import Callable, Mapping, Sequence
from typing import Any

# A behaviour answers one request on a connection. It returns True to keep the
# connection for the client's next request, and None or False to close it.
Behaviour = Callable[[socket.socket, threading.Event], bool | None]


# A Set-Cookie header line whose Max-Age is too large for a float. http.cookiejar
# warns about it (a UserWarning) and ignores the cookie; under a
# warnings-as-errors policy the warning is raised while requests builds the
# response.
OVERFLOWING_COOKIE = "Set-Cookie: broken=yes; Max-Age=" + "9" * 400


def warnings_as_errors[Result](function: Callable[..., Result]) -> Callable[..., Result]:
    """Wrap ``function`` to raise each ``UserWarning`` as an error, in the thread that calls it.

    A filter set with ``warnings.catch_warnings`` in a test reaches a worker
    thread only while filters are process-wide or a new thread inherits its
    starter's context, which depends on how Python was built and started.

    Where filters are process-wide, the filter applies to every thread while
    ``function`` runs, and two calls that overlap can restore each other's
    filters out of order. So wrap only work that ends before the next wrapped
    call starts, as a ``get_bytes`` worker that ends before its call returns does.
    """

    def wrapped(*args: Any, **kwargs: Any) -> Result:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            return function(*args, **kwargs)

    return wrapped


class RunningCount[Result]:
    """Wrap ``function`` to count, across threads, the calls started and the most running at once."""

    def __init__(self, function: Callable[..., Result]) -> None:
        self._function = function
        self._lock = threading.Lock()
        self.started = 0
        self.running = 0
        self.most_running = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        with self._lock:
            self.started += 1
            self.running += 1
            self.most_running = max(self.most_running, self.running)
        try:
            return self._function(*args, **kwargs)
        finally:
            with self._lock:
                self.running -= 1


def wait_until(condition: Callable[[], bool], *, within: float = 5.0) -> bool:
    """Whether ``condition`` holds within ``within`` seconds, checked every 10 ms."""
    give_up_at = time.monotonic() + within
    while time.monotonic() < give_up_at:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class LocalHttpServer:
    """Serve connections on 127.0.0.1 with ``behaviours``, one per connection in turn.

    A request whose path is a key of ``routes`` gets that behaviour instead.
    ``requests`` holds every request head received, ``max_concurrent`` the
    most connections served at once, and ``open_connections`` those being
    served now.
    """

    def __init__(
        self,
        behaviours: Sequence[Behaviour],
        *,
        routes: Mapping[str, Behaviour] | None = None,
    ) -> None:
        if not behaviours:
            raise ValueError("at least one behaviour is required")
        self._behaviours = list(behaviours)
        self._routes = dict(routes or {})
        self._next_behaviour = 0
        self._serving = 0
        self.max_concurrent = 0
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.settimeout(0.05)
        host, port = self._listener.getsockname()[:2]
        self.url = f"http://{host}:{port}/"
        self.requests: list[bytes] = []
        self._closing = threading.Event()
        self._lock = threading.Lock()
        self._connections: list[socket.socket] = []
        self._threads: list[threading.Thread] = []
        self._acceptor = threading.Thread(target=self._accept, daemon=True)

    @property
    def open_connections(self) -> int:
        with self._lock:
            return self._serving

    def __enter__(self) -> LocalHttpServer:
        self._acceptor.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._closing.set()
        self._acceptor.join(timeout=5)
        with self._lock:
            connections = list(self._connections)
            threads = list(self._threads)
        for connection in connections:
            connection.close()
        for thread in threads:
            thread.join(timeout=5)
        self._listener.close()

    def _accept(self) -> None:
        while not self._closing.is_set():
            try:
                connection, _ = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            thread = threading.Thread(target=self._serve, args=(connection,), daemon=True)
            with self._lock:
                self._connections.append(connection)
                self._threads.append(thread)
            thread.start()

    def _serve(self, connection: socket.socket) -> None:
        with self._lock:
            self._serving += 1
            self.max_concurrent = max(self.max_concurrent, self._serving)
        try:
            keep_alive = True
            while keep_alive:
                request = _read_request_head(connection, self._closing)
                if request is None:
                    return
                path = request.split(b" ", 2)[1].decode("latin-1")
                with self._lock:
                    self.requests.append(request)
                    behaviour = self._routes.get(path)
                    if behaviour is None:
                        index = min(self._next_behaviour, len(self._behaviours) - 1)
                        behaviour = self._behaviours[index]
                        self._next_behaviour += 1
                keep_alive = bool(behaviour(connection, self._closing))
        except OSError:
            pass
        finally:
            connection.close()
            with self._lock:
                self._serving -= 1


def _read_request_head(connection: socket.socket, closing: threading.Event) -> bytes | None:
    connection.settimeout(0.05)
    head = b""
    while b"\r\n\r\n" not in head:
        if closing.is_set():
            return None
        try:
            data = connection.recv(4096)
        except TimeoutError:
            continue
        if not data:
            return None
        head += data
    return head


def never_answer(connection: socket.socket, closing: threading.Event) -> None:
    """Accept the request and send nothing, as a hung server does."""
    closing.wait()


def drop_connection(connection: socket.socket, closing: threading.Event) -> None:
    """Close the connection without a response."""


def until_client_closes(behaviour: Behaviour) -> Behaviour:
    """Run ``behaviour``, then keep the connection until the client closes it."""

    def waiting(connection: socket.socket, closing: threading.Event) -> None:
        if behaviour(connection, closing):
            raise ValueError("until_client_closes needs a behaviour that closes its connection")
        connection.settimeout(0.05)
        while not closing.is_set():
            try:
                if not connection.recv(4096):
                    return
            except TimeoutError:
                continue

    return waiting


def respond(
    body: bytes,
    *,
    status: str = "200 OK",
    gzip_encoded: bool = False,
    chunked: bool = False,
    after: float = 0.0,
    gate: threading.Event | None = None,
    headers: Sequence[str] = (),
) -> Behaviour:
    """Answer with ``body`` after ``after`` seconds, and once ``gate`` is set, if given.

    The body is optionally gzip-encoded or chunked. ``headers`` are extra
    header lines, sent as Latin-1 as HTTP headers are.
    """

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        if closing.wait(after):
            return
        while gate is not None and not gate.wait(0.05):
            if closing.is_set():
                return
        payload = gzip.compress(body) if gzip_encoded else body
        lines = [f"HTTP/1.1 {status}", "Connection: close", *headers]
        if gzip_encoded:
            lines.append("Content-Encoding: gzip")
        if chunked:
            lines.append("Transfer-Encoding: chunked")
            middle = len(payload) // 2
            parts = [payload[:middle], payload[middle:]]
            framed = b"".join(
                f"{len(part):x}\r\n".encode() + part + b"\r\n" for part in parts if part
            )
            payload = framed + b"0\r\n\r\n"
        else:
            lines.append(f"Content-Length: {len(payload)}")
        connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + payload)

    return behaviour


def trickle_headers(interval: float) -> Behaviour:
    """Send a status line, then one header byte every ``interval`` seconds, forever.

    Each byte arrives well inside any read timeout, so only a deadline on the
    whole request ends the wait.
    """

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
        while not closing.wait(interval):
            connection.sendall(b"a")

    return behaviour


def trickle_body(interval: float, *, declared_length: int = 10_000_000) -> Behaviour:
    """Send complete headers, then one body byte every ``interval`` seconds, forever."""

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        connection.sendall(
            b"HTTP/1.1 200 OK\r\nConnection: close\r\n"
            + f"Content-Length: {declared_length}\r\n\r\n".encode()
        )
        while not closing.wait(interval):
            connection.sendall(b"a")

    return behaviour


def redirect(
    location: str,
    *,
    body: bytes = b"",
    slowly_for: float = 0.0,
    body_slowly_for: float = 0.0,
    interval: float = 0.02,
    keep_alive: bool = False,
) -> Behaviour:
    """Answer ``302 Found`` to ``location``, sent as Latin-1 as HTTP headers are.

    Its headers trickle in for ``slowly_for`` seconds first. Its body is
    ``body``, or, with ``body_slowly_for``, a chunked body sent a byte at a
    time for that long. With ``keep_alive`` it keeps the connection for the
    client's next request instead of closing it.
    """

    def behaviour(connection: socket.socket, closing: threading.Event) -> bool:
        framing = (
            b"Transfer-Encoding: chunked\r\n"
            if body_slowly_for
            else f"Content-Length: {len(body)}\r\n".encode()
        )
        persistence = b"" if keep_alive else b"Connection: close\r\n"
        rest = persistence + framing + f"Location: {location}\r\n\r\n".encode("latin-1")
        if not body_slowly_for:
            rest += body
        if not slowly_for:
            connection.sendall(b"HTTP/1.1 302 Found\r\n" + rest)
        else:
            connection.sendall(b"HTTP/1.1 302 Found\r\nX-Slow: ")
            if not _trickle(connection, closing, seconds=slowly_for, interval=interval):
                return False
            connection.sendall(b"\r\n" + rest)
        if body_slowly_for:
            finish_at = time.monotonic() + body_slowly_for
            while time.monotonic() < finish_at:
                if closing.wait(interval):
                    return False
                connection.sendall(b"1\r\na\r\n")
            connection.sendall(b"0\r\n\r\n")
        return keep_alive

    return behaviour


def stream_body(chunk: int, interval: float, *, declared_length: int = 1 << 40) -> Behaviour:
    """Send complete headers, then ``chunk`` body bytes every ``interval`` seconds.

    It sends until the server closes or the client does, far short of the
    declared length, so the body is still arriving whenever a reader stops.
    """

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        connection.sendall(
            b"HTTP/1.1 200 OK\r\nConnection: close\r\n"
            + f"Content-Length: {declared_length}\r\n\r\n".encode()
        )
        while not closing.wait(interval):
            connection.sendall(b"a" * chunk)

    return behaviour


def held_headers(gate: threading.Event, body: bytes, *, interval: float = 0.02) -> Behaviour:
    """Trickle one header byte every ``interval`` seconds until ``gate`` is set, then answer ``body``."""

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
        while not gate.wait(interval):
            if closing.is_set():
                return
            connection.sendall(b"a")
        connection.sendall(
            b"\r\nConnection: close\r\n" + f"Content-Length: {len(body)}\r\n\r\n".encode() + body
        )

    return behaviour


def _trickle(
    connection: socket.socket, closing: threading.Event, *, seconds: float, interval: float
) -> bool:
    """Send one header byte every ``interval`` seconds for ``seconds``; False if the server closed."""
    finish_at = time.monotonic() + seconds
    while time.monotonic() < finish_at:
        if closing.wait(interval):
            return False
        connection.sendall(b"a")
    return True
