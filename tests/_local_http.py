"""A local HTTP server that answers slowly, partly or not at all, for fetch tests.

``LocalHttpServer`` listens on 127.0.0.1 and gives each connection the next of
its behaviours (the last one repeats), so a test can make a fetcher meet a
server that never answers, sends its headers or body a byte at a time, drops
the connection, or answers normally. Every behaviour returns when the server
closes, so no test leaves a thread blocked on a socket.
"""

from __future__ import annotations

import gzip
import socket
import threading
from collections.abc import Callable, Sequence

Behaviour = Callable[[socket.socket, threading.Event], None]


class LocalHttpServer:
    """Serve connections on 127.0.0.1 with ``behaviours``, one per connection in turn."""

    def __init__(self, behaviours: Sequence[Behaviour]) -> None:
        if not behaviours:
            raise ValueError("at least one behaviour is required")
        self._behaviours = list(behaviours)
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
        index = 0
        while not self._closing.is_set():
            try:
                connection, _ = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            behaviour = self._behaviours[min(index, len(self._behaviours) - 1)]
            index += 1
            thread = threading.Thread(target=self._serve, args=(connection, behaviour), daemon=True)
            with self._lock:
                self._connections.append(connection)
                self._threads.append(thread)
            thread.start()

    def _serve(self, connection: socket.socket, behaviour: Behaviour) -> None:
        try:
            request = _read_request_head(connection, self._closing)
            if request is None:
                return
            with self._lock:
                self.requests.append(request)
            behaviour(connection, self._closing)
        except OSError:
            pass
        finally:
            connection.close()


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
) -> Behaviour:
    """Answer at once with ``body``, optionally gzip-encoded or chunked."""

    def behaviour(connection: socket.socket, closing: threading.Event) -> None:
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
