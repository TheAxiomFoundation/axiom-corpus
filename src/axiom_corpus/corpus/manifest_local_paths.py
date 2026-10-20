"""Paths on one machine, which a signed ingest manifest must not record.

A signed ingest manifest is public, and its ``command.text`` is the record of
how a scope was built. A path such as ``/Users/<name>/...``, ``/private/tmp/...``
or ``~/...`` names a place on the machine that ran the ingest: it reaches no one
else, says nothing a reader can rerun, and publishes the operator's account
name and directory layout. The convention instead is repository-relative paths
for repository files and placeholders such as ``TMPDIR=<scratchpad>`` or
``<ocr-cache>`` for scratch and cache directories, plus a parenthetical naming
the run note under ``docs/ingest-runs/``.

``find_local_paths`` finds such paths in text; ``local_path_fields`` lists the
fields of a manifest that hold one; ``relativize_repo_paths`` rewrites absolute
paths inside the repository to repository-relative ones, the one rewrite that
loses nothing.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Roots of paths that exist on one machine only: home directories (macOS,
# Linux, root's), temporary directories (``/private`` is where macOS keeps
# ``/tmp`` and ``/var``), per-user caches, and mounted volumes.
LOCAL_PATH_ROOTS: tuple[str, ...] = (
    "/Users/",
    "/home/",
    "/root/",
    "/private/",
    "/tmp/",
    "/var/folders/",
    "/var/tmp/",
    "/Volumes/",
    "/mnt/",
    "/media/",
)

# Characters that end a path token in a command line, and so may also begin
# one: whitespace, quotes, shell operators, brackets, and the ``=`` of an
# assignment or ``--flag=value`` and the ``:`` of a ``PATH``-style list. A root
# preceded by anything else (``https://example.gov/home/``, ``data/tmp/``) is
# part of a URL or a relative path, not an absolute path.
_DELIMITERS = "\\s\"'`=:,;|&()<>\\[\\]{}"
_AT_TOKEN_START = f"(?<![^{_DELIMITERS}])"
_TOKEN_REST = f"[^{_DELIMITERS}]*"

_LOCAL_PATH = re.compile(
    "|".join(
        (
            # Any file: URL names a file on the machine that wrote it.
            rf"(?P<file_url>(?i:(?<![A-Za-z0-9+.-])file:/){_TOKEN_REST})",
            # An absolute path under one of the roots above.
            rf"(?P<absolute>{_AT_TOKEN_START}"
            rf"(?:{'|'.join(re.escape(root) for root in LOCAL_PATH_ROOTS)}){_TOKEN_REST})",
            # A home-relative path: ~/..., ~user/..., or ~ alone.
            rf"(?P<tilde>{_AT_TOKEN_START}~"
            rf"(?:[A-Za-z0-9._-]*/{_TOKEN_REST}|(?=[{_DELIMITERS}]|\Z)))",
            # The home directory by variable, wherever it appears.
            rf"(?P<home_variable>(?:\$HOME\b|\$\{{HOME\}}|(?i:%USERPROFILE%)){_TOKEN_REST})",
            # A Windows user profile.
            rf"(?P<windows>{_AT_TOKEN_START}[A-Za-z]:[\\/](?i:Users|Documents and Settings)[\\/]"
            rf"{_TOKEN_REST})",
        )
    )
)

# A placeholder such as ``<scratchpad>`` stands in for a directory, so a path
# that follows it (``<scratchpad>/tmp/replay.json``) is relative to it.
_PLACEHOLDER_BEFORE = re.compile(r"<[A-Za-z0-9._-]+>\Z")

_ROOT_LABELS = {
    "file_url": "file:",
    "tilde": "~",
    "home_variable": "$HOME",
    "windows": "C:\\Users\\",
}


@dataclass(frozen=True)
class LocalPath:
    """One path on the writing machine, found at ``text[start:end]``."""

    start: int
    end: int
    kind: str
    root: str

    def describe(self) -> str:
        """Name the path by its root only (``/Users/…``), never by the whole path."""
        if self.kind == "absolute":
            return f"{self.root}…"
        return f"{_ROOT_LABELS[self.kind]}…"


def find_local_paths(text: str) -> list[LocalPath]:
    """Return every path on the writing machine in ``text``, in order.

    A path is a ``file:`` URL; an absolute path under one of
    ``LOCAL_PATH_ROOTS`` that starts a token (at the start of the text or after
    whitespace, a quote, ``=``, ``:``, or a shell operator); a home-relative
    path (``~/``, ``~user/``, ``$HOME``, ``${HOME}``, ``%USERPROFILE%``); or a
    Windows user profile (``C:\\Users\\``). A root inside a URL or a relative
    path (``https://example.gov/home/``, ``data/tmp/``) is not one, and nor is
    a path after a placeholder (``<scratchpad>/tmp/``).
    """
    found: list[LocalPath] = []
    for match in _LOCAL_PATH.finditer(text):
        kind = match.lastgroup or "absolute"
        if kind == "absolute" and _PLACEHOLDER_BEFORE.search(text, 0, match.start()):
            continue
        root = ""
        if kind == "absolute":
            root = next(root for root in LOCAL_PATH_ROOTS if match.group().startswith(root))
        found.append(LocalPath(match.start(), match.end(), kind, root))
    return found


def redact_local_paths(text: str) -> str:
    """Replace each local path in ``text`` with its root (``/Users/…``)."""
    pieces: list[str] = []
    position = 0
    for path in find_local_paths(text):
        pieces.append(text[position : path.start])
        pieces.append(path.describe())
        position = path.end
    pieces.append(text[position:])
    return "".join(pieces)


# The value of ``signature.value`` is base64, whose alphabet holds ``/``; it
# records bytes, not a path.
_UNSCANNED_FIELDS = frozenset({"signature.value"})


def local_path_fields(payload: Any) -> list[tuple[str, LocalPath]]:
    """Return ``(field, path)`` for every local path in a manifest's strings.

    Every string is read, at any depth: values and object keys alike, with
    lists indexed (``applied_files[3].path``). ``signature.value`` is base64
    and is not read.
    """
    return list(_walk(payload, ""))


def _walk(value: Any, field: str) -> Iterator[tuple[str, LocalPath]]:
    if isinstance(value, dict):
        for key, child in value.items():
            # A key that is itself a local path is named by its root only.
            name = redact_local_paths(key) if isinstance(key, str) else str(key)
            child_field = f"{field}.{name}" if field else name
            if isinstance(key, str):
                for path in find_local_paths(key):
                    yield f"{child_field} (key)", path
            if child_field not in _UNSCANNED_FIELDS:
                yield from _walk(child, child_field)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{field}[{index}]")
    elif isinstance(value, str):
        for path in find_local_paths(value):
            yield field, path


class ManifestReadError(ValueError):
    """A manifest whose strings cannot all be read, so cannot be cleared."""


def _refuse_repeated_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    members: dict[str, Any] = {}
    for key, value in pairs:
        if key in members:
            raise ManifestReadError(f"repeats the key {redact_local_paths(repr(key))}")
        members[key] = value
    return members


def manifest_local_path_fields(payload: bytes) -> list[tuple[str, LocalPath]]:
    """Return the local paths in a manifest file's bytes.

    Fails closed: raises ``ManifestReadError`` for bytes that are not UTF-8
    JSON, or that repeat a key in one object (parsing would keep only the last
    value, so a path in an earlier one would go unseen).
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestReadError("is not UTF-8 text") from exc
    try:
        parsed = json.loads(text, object_pairs_hook=_refuse_repeated_keys)
    except json.JSONDecodeError as exc:
        raise ManifestReadError("is not JSON") from exc
    return local_path_fields(parsed)


# A path token: an absolute path, or a home-relative one, starting a token.
_PATH_TOKEN = re.compile(
    rf"{_AT_TOKEN_START}(?:/|~/|\$HOME/|\$\{{HOME\}}/){_TOKEN_REST}"
    rf"|{_AT_TOKEN_START}(?:~|\$HOME\b|\$\{{HOME\}})(?=[{_DELIMITERS}]|\Z)"
)


def relativize_repo_paths(text: str, *, repo: Path) -> str:
    """Rewrite each absolute path inside ``repo`` as a repository-relative path.

    ``/Users/<name>/axiom-corpus/.venv/bin/python`` becomes
    ``.venv/bin/python`` and the checkout itself becomes ``.``, so a command run
    from the checkout records what a reader of the repository can run. A path
    is inside the checkout when, with ``~`` and ``$HOME`` expanded and ``..``
    collapsed, it is the checkout or lies under it, spelled either as given or
    through symbolic links (macOS ``/tmp`` is ``/private/tmp``). Every other
    path is left as written.
    """
    roots = _checkout_spellings(repo)
    home = os.path.expanduser("~")

    def rewrite(match: re.Match[str]) -> str:
        token = match.group()
        if _PLACEHOLDER_BEFORE.search(text, 0, match.start()):
            return token
        expanded = token
        for prefix in ("~", "$HOME", "${HOME}"):
            if token == prefix or token.startswith(prefix + "/"):
                expanded = home + token[len(prefix) :]
                break
        if not expanded.startswith("/"):
            return token
        trailing = "/" if expanded.endswith("/") and expanded != "/" else ""
        for candidate in _path_spellings(expanded):
            for root in roots:
                if candidate == root:
                    return "." + trailing if trailing else "."
                if candidate.startswith(root + "/"):
                    return candidate[len(root) + 1 :] + trailing
        return token

    return _PATH_TOKEN.sub(rewrite, text)


def _checkout_spellings(repo: Path) -> list[str]:
    spellings = _path_spellings(str(repo))
    # Longest first, so a nested checkout is matched before its parent.
    return sorted(set(spellings), key=len, reverse=True)


def _path_spellings(path: str) -> list[str]:
    """The path normalized as written, and with its symbolic links resolved."""
    normalized = os.path.normpath(path)
    spellings = [normalized]
    # A NUL byte, or a path the OS will not resolve, has no other spelling.
    with contextlib.suppress(OSError, ValueError):
        spellings.append(os.path.realpath(normalized))
    # macOS: /tmp and /var are links into /private.
    for spelling in list(spellings):
        if spelling.startswith("/private/"):
            spellings.append(spelling[len("/private") :])
    return spellings
