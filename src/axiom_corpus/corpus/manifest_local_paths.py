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
# ``/tmp`` and ``/var``), per-user caches, and mounted volumes. Matched in any
# case, since macOS file systems ignore case (``/users/x`` is ``/Users/x``).
LOCAL_PATH_ROOTS: tuple[str, ...] = (
    "/Users",
    "/home",
    "/root",
    "/private",
    "/tmp",
    "/var/folders",
    "/var/tmp",
    "/Volumes",
    "/mnt",
    "/media",
)

# Characters that end a path token in a command line, and so may also begin
# one: whitespace, quotes, shell operators, brackets, and the ``=`` of an
# assignment or ``--flag=value`` and the ``:`` of a ``PATH``-style list. A root
# preceded by anything else (``https://example.gov/home/``, ``data/tmp/``) is
# part of a URL or a relative path, not an absolute path.
_DELIMITERS = "\\s\"'`=:,;|&()<>\\[\\]{}"
_AT_TOKEN_START = f"(?<![^{_DELIMITERS}])"
_TOKEN_REST = f"[^{_DELIMITERS}]*"
_TOKEN_END = f"(?=/|[{_DELIMITERS}]|\\Z)"
# What may come between a token start and the path it gives: a cluster of short
# options taking an attached value (``-o/path``, ``-I/path``), and curl's
# ``@file``.
_LEAD = "(?:-[A-Za-z]+)?@?"
# The home directory and Windows per-user directories, by variable.
_HOME_VARIABLE = (
    r"(?:\$HOME|\$\{HOME\}|(?i:%(?:USERPROFILE|HOMEPATH|TEMP|TMP|LOCALAPPDATA|APPDATA)%))"
)

_LOCAL_PATH = re.compile(
    "|".join(
        (
            # Any file: URL names a file on the machine that wrote it.
            rf"(?P<file_url>(?i:(?<![A-Za-z0-9+.-])file:/){_TOKEN_REST})",
            rf"{_AT_TOKEN_START}{_LEAD}(?:"
            # An absolute path under one of the roots above, or the root itself.
            rf"(?P<absolute>(?i:{'|'.join(re.escape(root) for root in LOCAL_PATH_ROOTS)})"
            rf"{_TOKEN_END}{_TOKEN_REST})"
            # A home-relative path: ~/... or ~user/...
            rf"|(?P<tilde>~[A-Za-z0-9._-]*/{_TOKEN_REST})"
            # A Windows user profile.
            rf"|(?P<windows>[A-Za-z]:[\\/](?i:Users|Documents and Settings)[\\/]{_TOKEN_REST})"
            ")",
            # A path under the home directory by variable, wherever it appears.
            rf"(?P<home_variable>{_HOME_VARIABLE}[\\/]{_TOKEN_REST})",
        )
    )
)
_KINDS = ("file_url", "absolute", "tilde", "windows", "home_variable")

# A placeholder such as ``<scratchpad>`` stands in for a directory, so a path
# that follows it (``<scratchpad>/tmp/replay.json``) is relative to it. A name
# with a dot (``<in.json>/tmp/out``) is a redirect, not a placeholder.
_PLACEHOLDER_BEFORE = re.compile(r"<[A-Za-z0-9_-]+>\Z")
# A URL's scheme in the same word: what follows it is the URL's path, query or
# fragment (``https://x.gov/?file=/home/a.htm``), not a path on this machine.
_WORD_START = re.compile(r"[\s\"'`][^\s\"'`]*\Z")
_URL_SCHEME = re.compile(r"(?i)(?<![A-Za-z0-9+.-])(?!file:)[A-Za-z][A-Za-z0-9+.-]*://")

_ROOT_LABELS = {
    "file_url": "file:",
    # ``~user/`` would name an account; every tilde path is shown as ``~/``.
    "tilde": "~/",
    "windows": "C:\\Users\\",
}
_HOME_VARIABLE_ROOT = re.compile(rf"{_HOME_VARIABLE}[\\/]")


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
            return f"{self.root}/…"
        if self.kind == "home_variable":
            return f"{self.root}…"
        return f"{_ROOT_LABELS[self.kind]}…"


def _inside_url(text: str, start: int) -> bool:
    """Whether ``text[start:]`` continues a URL begun earlier in the same word."""
    word = _WORD_START.search(text, 0, start)
    word_start = word.start() + 1 if word else 0
    return _URL_SCHEME.search(text, word_start, start) is not None


def _after_placeholder(text: str, start: int) -> bool:
    return _PLACEHOLDER_BEFORE.search(text, 0, start) is not None


def find_local_paths(text: str) -> list[LocalPath]:
    """Return every path on the writing machine in ``text``, in order.

    A path is a ``file:`` URL; an absolute path under one of
    ``LOCAL_PATH_ROOTS`` (any case), or the root itself; a home-relative path
    (``~/``, ``~user/``, ``$HOME/``, ``${HOME}/``, ``%USERPROFILE%\\`` and the
    other Windows per-user variables); or a Windows user profile
    (``C:\\Users\\``). All but the variables must start a token: at the start of
    the text, or after whitespace, a quote, ``=``, ``:``, a shell operator or
    bracket, optionally behind a short-option cluster or ``@`` (``-o/path``,
    ``@/path``). A root inside a URL (``https://x.gov/home/``,
    ``https://x.gov/?f=/home/a``), inside a relative path (``data/tmp/``) or
    after a placeholder (``<scratchpad>/tmp/``) is not one; nor is ``~`` or
    ``$HOME`` with no path after it.
    """
    found: list[LocalPath] = []
    for match in _LOCAL_PATH.finditer(text):
        kind = next(name for name in _KINDS if match.group(name) is not None)
        start, end = match.span(kind)
        if kind != "file_url" and _inside_url(text, start):
            continue
        if kind == "absolute" and _after_placeholder(text, start):
            continue
        root = ""
        if kind == "home_variable":
            variable = _HOME_VARIABLE_ROOT.match(match.group(kind))
            root = variable.group() if variable else ""
        if kind == "absolute":
            lowered = match.group(kind).lower()
            root = next(
                root
                for root in LOCAL_PATH_ROOTS
                if lowered == root.lower() or lowered.startswith(root.lower() + "/")
            )
        found.append(LocalPath(start, end, kind, root))
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


# A path token that may name a place in the checkout: absolute, or under the
# home directory.
_PATH_TOKEN = re.compile(
    rf"{_AT_TOKEN_START}(?P<lead>{_LEAD})"
    rf"(?P<path>(?:/|~[A-Za-z0-9._-]*/|\$HOME/|\$\{{HOME\}}/){_TOKEN_REST})"
)
_HAS_DELIMITER = re.compile(f"[{_DELIMITERS}]")


@dataclass(frozen=True)
class RepoRewrite:
    """``text[start:end]``, a path inside the checkout, recorded as ``relative``."""

    start: int
    end: int
    relative: str


def relativize_repo_paths(text: str, *, repo: Path) -> str:
    """Rewrite each absolute path inside ``repo`` as a repository-relative path.

    ``/Users/<name>/axiom-corpus/.venv/bin/python`` becomes
    ``.venv/bin/python`` and the checkout itself becomes ``.``, so a command run
    from the checkout records what a reader of the repository can run. See
    ``repo_rewrites`` for which paths are rewritten.
    """
    pieces: list[str] = []
    position = 0
    for rewrite in repo_rewrites(text, repo=repo):
        pieces.append(text[position : rewrite.start])
        pieces.append(rewrite.relative)
        position = rewrite.end
    pieces.append(text[position:])
    return "".join(pieces)


def repo_rewrites(text: str, *, repo: Path) -> list[RepoRewrite]:
    """Return the paths in ``text`` that lie inside ``repo``, with their relative form.

    A path token (absolute, ``~``, ``~user`` or ``$HOME``, starting a token as in
    ``find_local_paths``) is inside the checkout when, with the home directory
    expanded, it is the checkout or lies under it: compared as written with
    ``.`` and ``..`` collapsed (only when it holds no ``..``, which a symbolic
    link can carry outside), and with every symbolic link resolved (macOS
    ``/tmp`` is ``/private/tmp``). A checkout whose path holds a space or other
    delimiter is matched as written. Paths inside a URL, after a placeholder or
    in a ``file:`` URL are left alone. A relative form that could be misread (a
    checkout directory named ``~cache``, or one after a short option) is written
    ``./~cache`` (see ``_unambiguous``).
    """
    roots = _checkout_spellings(repo)
    home = os.path.expanduser("~")
    rewrites: list[RepoRewrite] = []

    def skipped(start: int) -> bool:
        return (
            _after_placeholder(text, start)
            or _FILE_SCHEME_BEFORE.search(text, 0, start) is not None
            or _inside_url(text, start)
        )

    # A checkout path the tokenizer would split (``/Users/x/My Repo``), as written.
    for root in roots:
        if not _HAS_DELIMITER.search(root):
            continue
        literal = re.compile(
            rf"{_AT_TOKEN_START}(?P<lead>{_LEAD})"
            rf"(?P<path>{re.escape(root)}(?P<rest>/{_TOKEN_REST})?)(?=[{_DELIMITERS}]|\Z)"
        )
        for match in literal.finditer(text):
            start, end = match.span("path")
            rest = match.group("rest") or ""
            if skipped(start) or ".." in rest.split("/") or _overlaps(rewrites, start, end):
                continue
            if rest in ("", "/"):
                relative = "." + rest
            else:
                relative = os.path.normpath(rest[1:]) + ("/" if rest.endswith("/") else "")
            rewrites.append(RepoRewrite(start, end, _unambiguous(relative, match.group("lead"))))

    for match in _PATH_TOKEN.finditer(text):
        start, end = match.span("path")
        if skipped(start) or _overlaps(rewrites, start, end):
            continue
        inside = _relative_to_checkout(match.group("path"), roots=roots, home=home)
        if inside is not None:
            rewrites.append(RepoRewrite(start, end, _unambiguous(inside, match.group("lead"))))
    return sorted(rewrites, key=lambda rewrite: rewrite.start)


_FILE_SCHEME_BEFORE = re.compile(r"(?i)(?<![A-Za-z0-9+.-])file:/*\Z")


def _overlaps(rewrites: list[RepoRewrite], start: int, end: int) -> bool:
    return any(rewrite.start < end and start < rewrite.end for rewrite in rewrites)


def _relative_to_checkout(token: str, *, roots: list[str], home: str) -> str | None:
    expanded = token
    if token.startswith("~"):
        expanded = os.path.expanduser(token)
    else:
        for prefix in ("$HOME/", "${HOME}/"):
            if token.startswith(prefix):
                expanded = home + "/" + token[len(prefix) :]
                break
    if not expanded.startswith("/"):
        return None
    trailing = "/" if expanded.endswith("/") and expanded != "/" else ""
    for candidate in _path_spellings(expanded):
        for root in roots:
            if candidate == root:
                return "./" if trailing else "."
            if candidate.startswith(root + "/"):
                return candidate[len(root) + 1 :] + trailing
    return None


def _unambiguous(relative: str, lead: str) -> str:
    """``relative``, prefixed ``./`` where it could be read as something else.

    That is where it would read as a home-relative path, curl's ``@file`` or an
    option (``~cache``, ``@x``, ``-v``), or where it follows a short option and
    would run into it: ``-o`` and ``private/var/x`` would read as the option
    ``-oprivate`` with the path ``/var/x``. A relative path that a shell would
    still expand (``$HOME/z``) gains nothing from ``./``; ``recordable_command``
    refuses it.
    """
    if relative.startswith(("~", "@", "-")) or (
        lead[-1:].isalpha() and not relative.startswith(".")
    ):
        return "./" + relative
    return relative


def _checkout_spellings(repo: Path) -> list[str]:
    spellings = _path_spellings(str(repo))
    # Longest first, so a nested checkout is matched before its parent.
    return sorted(set(spellings), key=len, reverse=True)


def _path_spellings(path: str) -> list[str]:
    """The path as written with ``.`` and ``..`` collapsed, and with its links resolved.

    Collapsing ``..`` as text is wrong after a symbolic link (``link/..`` is the
    link target's parent), so a path holding ``..`` is only compared resolved.
    """
    spellings = []
    if ".." not in path.split("/"):
        spellings.append(os.path.normpath(path))
    # A NUL byte, or a path the OS will not resolve, has no resolved spelling.
    with contextlib.suppress(OSError, ValueError):
        spellings.append(os.path.realpath(path))
    return spellings
