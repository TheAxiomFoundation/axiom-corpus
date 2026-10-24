"""A local HTTP server that answers slowly, partly or not at all, for fetch tests.

``LocalHttpServer`` listens on 127.0.0.1 and gives each connection the
behaviour routed to its request path, or else the next of its behaviours (the
last one repeats), so a test can make a fetcher meet a server that never
answers, sends its headers or body a byte at a time, redirects, drops the
connection, or answers normally. Every behaviour returns when the server
closes, so no test leaves a thread blocked on a socket.
"""

from __future__ import annotations

import gzip
import socket
import threading
import time
from collections.abc import Callable, Mapping, Sequence

Behaviour = Callable[[socket.socket, threading.Event], None]


class LocalHttpServer:
    """Serve connections on 127.0.0.1 with ``behaviours``, one per connection in turn.

    A request whose path is a key of ``routes`` gets that behaviour instead.
    ``requests`` holds every request head received, and ``max_concurrent`` the
    most connections served at once.
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
            behaviour(connection, self._closing)
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


def respond(
    body: bytes,
    *,
    status: str = "200 OK",
    gzip_encoded: bool = False,
    chunked: bool = False,
    after: float = 0.0,
) -> Behaviour:
    """Answer with ``body`` after ``after`` seconds, optionally gzip-encoded or chunked."""

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        if closing.wait(after):
            return
        payload = gzip.compress(body) if gzip_encoded else body
        headers = [f"HTTP/1.1 {status}", "Connection: close"]
        if gzip_encoded:
            headers.append("Content-Encoding: gzip")
        if chunked:
            headers.append("Transfer-Encoding: chunked")
            middle = len(payload) // 2
            parts = [payload[:middle], payload[middle:]]
            framed = b"".join(
                f"{len(part):x}\r\n".encode() + part + b"\r\n" for part in parts if part
            )
            payload = framed + b"0\r\n\r\n"
        else:
            headers.append(f"Content-Length: {len(payload)}")
        connection.sendall(("\r\n".join(headers) + "\r\n\r\n").encode() + payload)

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


def redirect(location: str, *, slowly_for: float = 0.0, interval: float = 0.02) -> Behaviour:
    """Answer ``302 Found`` to ``location``, trickling its headers for ``slowly_for`` seconds first."""

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        rest = (
            b"Connection: close\r\nContent-Length: 0\r\n" + f"Location: {location}\r\n\r\n".encode()
        )
        if not slowly_for:
            connection.sendall(b"HTTP/1.1 302 Found\r\n" + rest)
            return
        connection.sendall(b"HTTP/1.1 302 Found\r\nX-Slow: ")
        if _trickle(connection, closing, seconds=slowly_for, interval=interval):
            connection.sendall(b"\r\n" + rest)

    return behaviour


def slow_headers(seconds: float, body: bytes, *, interval: float = 0.02) -> Behaviour:
    """Trickle one header byte every ``interval`` seconds for ``seconds``, then answer ``body``."""

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
        connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
        if _trickle(connection, closing, seconds=seconds, interval=interval):
            connection.sendall(
                b"\r\nConnection: close\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode()
                + body
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
