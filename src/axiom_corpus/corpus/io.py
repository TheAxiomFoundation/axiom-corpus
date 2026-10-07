"""JSON artifact readers for corpus inventory and provision records.

``load_provisions`` and ``load_source_inventory`` hold a whole artifact. The
release gates read artifacts of up to hundreds of megabytes (the May whole-eCFR
provisions file is 756 MB), so they use the streaming forms here instead:
``iter_provisions`` yields one record per line, and
``load_source_inventory_references`` keeps only the three inventory fields the
gates read. Both return or raise what the whole-file readers would, so
switching a gate to them cannot change what it accepts or the error it reports.
The one exception is JSON nested within a few levels of the parser's recursion
limit (about 52,000 levels): there a streaming reader may raise
``RecursionError`` on a file the whole-file reader accepted, or accept a file it
rejected with ``RecursionError``. No artifact nests that deep.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple, TextIO

from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem

# Characters the streaming inventory reader requests per read. Tests shrink it
# so that JSON values straddle read boundaries.
_INVENTORY_READ_CHARS = 1024 * 1024
# The whitespace ``json.loads`` skips between tokens.
_JSON_WHITESPACE = re.compile(r"[ \t\n\r]*")
_JSON_DECODER = json.JSONDecoder()


class SourceInventoryReference(NamedTuple):
    """The fields of one inventory item that the release gates read.

    Values are exactly those of the ``SourceInventoryItem`` the whole-file
    reader builds; ``metadata``, ``source_url`` and ``source_format`` are
    dropped because no gate reads them.
    """

    citation_path: str
    source_path: object
    sha256: object


def load_source_inventory(path: str | Path) -> tuple[SourceInventoryItem, ...]:
    data = json.loads(_fetched(Path(path)).read_text())
    rows = data.get("items", data if isinstance(data, list) else [])
    return tuple(SourceInventoryItem.from_mapping(row) for row in rows)


def load_source_inventory_references(path: str | Path) -> tuple[SourceInventoryReference, ...]:
    """Return ``load_source_inventory(path)`` reduced to the gate fields.

    Inventories written by ``CorpusArtifactStore.write_inventory`` have one
    shape, ``{"items": [...]}``, and are read one item at a time. Any other
    document (another key, a syntax error, text that is not valid in the file's
    encoding) is handed to ``load_source_inventory`` itself, so the result or
    the exception is the whole-file reader's own in every case.
    """
    p = _fetched(Path(path))
    streamed = _stream_inventory_references(p)
    if streamed is not None:
        return streamed
    return tuple(_inventory_reference(item, {}) for item in load_source_inventory(p))


def load_provisions(path: str | Path) -> tuple[ProvisionRecord, ...]:
    return tuple(iter_provisions(path))


def iter_provisions(path: str | Path) -> Iterator[ProvisionRecord]:
    """Yield the records of a provisions JSONL file one line at a time.

    The records, and any exception, are those of reading the whole file with
    ``Path.read_text().splitlines()``: the same decoding and line boundaries,
    blank lines skipped, rows parsed in order. That reader decoded the whole
    file before parsing any line, so a file that cannot be decoded raises the
    decode error even when an earlier line is malformed; this iterator checks
    the rest of the file before raising a parse error, and re-reads a file that
    fails to decode whole to raise the same error at the same position.

    A caller that stops on an exception must discard what it has consumed.
    """
    p = _fetched(Path(path))
    if not p.exists():
        return
    failure: Exception | None = None
    undecodable = False
    try:
        with p.open() as handle:
            for line in iter_nonblank_lines(handle):
                try:
                    record = ProvisionRecord.from_mapping(json.loads(line))
                except Exception as exc:
                    failure = exc
                    break
                yield record
            if failure is not None:
                for _ in handle:
                    pass
    except UnicodeDecodeError:
        undecodable = True
    if undecodable:
        # Only a file that is not valid in its encoding is read whole, so the
        # error names the same byte position as the whole-file reader's.
        p.read_text()
        raise OSError(f"provisions file changed while it was read: {p}")
    if failure is not None:
        raise failure


def iter_nonblank_lines(handle: TextIO) -> Iterator[str]:
    """Yield the non-blank lines of ``handle.read().splitlines()`` in order.

    Text files are read one physical line at a time. ``str.splitlines`` also
    breaks at separators such as U+2028, so each physical line is split again
    to keep the exact line boundaries of the whole-text split.
    """
    for physical in handle:
        for line in physical.splitlines():
            if line.strip():
                yield line


def _inventory_reference(
    item: SourceInventoryItem,
    shared: dict[str, str],
) -> SourceInventoryReference:
    # Items of one scope repeat a few source paths and hashes many times;
    # sharing one string object per value keeps the references compact.
    source_path: object = item.source_path
    if isinstance(source_path, str):
        source_path = shared.setdefault(source_path, source_path)
    sha256: object = item.sha256
    if isinstance(sha256, str):
        sha256 = shared.setdefault(sha256, sha256)
    return SourceInventoryReference(item.citation_path, source_path, sha256)


def _stream_inventory_references(path: Path) -> tuple[SourceInventoryReference, ...] | None:
    """Stream a canonical ``{"items": [...]}`` inventory, else return ``None``.

    ``None`` means the document is not the canonical shape or is not valid
    JSON in the file's encoding; the caller then reads it whole. When the
    document is canonical and valid, the first item ``from_mapping`` rejects
    is raised, as the whole-file reader would raise it.
    """
    references: list[SourceInventoryReference] = []
    shared: dict[str, str] = {}
    failure: Exception | None = None
    try:
        with path.open() as handle:
            stream = _JsonTextStream(handle)
            if not stream.consume("{"):
                return None
            parsed, key = stream.value()
            if not parsed or key != "items" or not stream.consume(":"):
                return None
            if not stream.consume("["):
                return None
            if not stream.consume("]"):
                while True:
                    parsed, element = stream.value()
                    if not parsed:
                        return None
                    if failure is None:
                        try:
                            item = SourceInventoryItem.from_mapping(element)  # type: ignore[arg-type]
                        except Exception as exc:
                            failure = exc
                        else:
                            references.append(_inventory_reference(item, shared))
                    if stream.consume(","):
                        continue
                    if stream.consume("]"):
                        break
                    return None
            if not stream.consume("}") or not stream.at_end():
                return None
    except (OSError, UnicodeDecodeError):
        return None
    if failure is not None:
        raise failure
    return tuple(references)


class _JsonTextStream:
    """Token-level reader over a text handle for one streamed JSON document."""

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle
        self._buffer = ""
        self._pos = 0
        self._eof = False

    def _read(self, size: int) -> bool:
        if self._eof:
            return False
        chunk = self._handle.read(size)
        if not chunk:
            self._eof = True
            return False
        if self._pos > len(self._buffer) // 2:
            self._buffer = self._buffer[self._pos :]
            self._pos = 0
        self._buffer += chunk
        return True

    def _skip_whitespace(self) -> None:
        while True:
            match = _JSON_WHITESPACE.match(self._buffer, self._pos)
            self._pos = match.end() if match else self._pos
            if self._pos < len(self._buffer) or not self._read(_INVENTORY_READ_CHARS):
                return

    def consume(self, token: str) -> bool:
        """Consume ``token`` after optional whitespace, if it is next."""
        self._skip_whitespace()
        if self._buffer.startswith(token, self._pos):
            self._pos += len(token)
            return True
        return False

    def at_end(self) -> bool:
        self._skip_whitespace()
        return self._pos >= len(self._buffer)

    def value(self) -> tuple[bool, object]:
        """Decode the next JSON value; ``(False, None)`` if there is none."""
        self._skip_whitespace()
        read_size = _INVENTORY_READ_CHARS
        while True:
            end = -1
            value: object = None
            try:
                value, end = _JSON_DECODER.raw_decode(self._buffer, self._pos)
            except Exception:
                # A value cut off by the read boundary fails to decode; so
                # does an invalid one, which fails again at end of file.
                end = -1
            if end >= 0:
                # A number can stop at the read boundary with its digits cut
                # short, so accept a value only once the character after it is
                # in hand (or the document has ended).
                following = _JSON_WHITESPACE.match(self._buffer, end)
                after = following.end() if following else end
                if after < len(self._buffer) or self._eof:
                    self._pos = end
                    return True, value
            if not self._read(read_size):
                if end >= 0:
                    self._pos = end
                    return True, value
                return False, None
            # Grow geometrically so a large value is re-parsed O(log n) times.
            read_size *= 2


def _fetched(path: Path) -> Path:
    """Fetch a locked corpus file this checkout lacks (docs/corpus-storage.md).

    Without this, an unfetched provisions file would read as an empty scope.
    Paths that no lock names behave exactly as before.
    """
    if path.exists():
        return path
    from axiom_corpus.corpus.resolver import fetch_locked_file

    fetch_locked_file(path)
    return path
