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
paths inside the repository to repository-relative ones, where that names the
same file.
"""

from __future__ import annotations

import contextlib
import json
import os
import posixpath
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
# What may come between a token start and the path it gives: a cluster of short
# options taking an attached value (``-o/path``, ``-I/path``), and curl's
# ``@file``.
_LEAD = "(?:-[A-Za-z]+)?@?"
# Detection also reads through parameters in front of a path, named, positional
# or special: unset, ``$X`` is empty and ``$X/Users/...`` is ``/Users/...``, and
# the text names the path anyway.
_DETECTION_LEAD = rf"{_LEAD}(?:\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-]))*"
# The home directory and Windows per-user directories, by variable.
_HOME_VARIABLE = (
    r"(?:\$HOME\b|\$\{HOME\}|\$TMPDIR\b|\$\{TMPDIR\}"
    r"|(?i:%(?:USERPROFILE|HOMEPATH|TEMP|TMP|LOCALAPPDATA|APPDATA)%))"
)

# Every absolute path token; whether it lies under a root is decided after
# normalizing it (``/./Users``, ``//private``, ``/var/../tmp``).
_ABSOLUTE = re.compile(rf"{_AT_TOKEN_START}{_DETECTION_LEAD}(?P<absolute>/{_TOKEN_REST})")
_OTHER_PATHS = re.compile(
    "|".join(
        (
            # Any file: URL names a file on the machine that wrote it.
            rf"(?P<file_url>(?i:(?<![A-Za-z0-9+.-])file:/){_TOKEN_REST})",
            rf"{_AT_TOKEN_START}{_DETECTION_LEAD}(?:"
            # A home-relative path: ~/... or ~user/...
            rf"(?P<tilde>~[A-Za-z0-9._-]*/{_TOKEN_REST})"
            # A Windows user profile.
            rf"|(?P<windows>[A-Za-z]:[\\/](?i:Users|Documents and Settings)[\\/]{_TOKEN_REST})"
            ")",
            # A path under the home directory by variable, wherever it appears.
            rf"(?P<home_variable>{_HOME_VARIABLE}[\\/]{_TOKEN_REST})",
        )
    )
)
_OTHER_KINDS = ("file_url", "tilde", "windows", "home_variable")

# A placeholder such as ``<scratchpad>`` stands in for a directory, so a path
# that follows it (``<scratchpad>/tmp/replay.json``) is relative to it. A name
# with a dot (``<in.json>/tmp/out``) is a redirect, not a placeholder.
_PLACEHOLDER_BEFORE = re.compile(r"<[A-Za-z0-9_-]+>\Z")
# A URL's scheme earlier in the same shell word: what follows it is the URL's
# path, query or fragment (``https://x.gov/?file=/home/a.htm``), not a path on
# this machine. ``file:`` is not such a scheme.
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


# --- How a POSIX shell would read the text ----------------------------------

_SHELL_OPERATORS = frozenset(";|&()<>")
_QUOTES = frozenset("'\"`")


@dataclass(frozen=True)
class _ShellLayout:
    """Per character: the quote around it, whether it is a quote mark, whether it ends a word.

    ``quote[i]`` is the quote character enclosing ``text[i]`` (``None`` outside
    quotes and for the marks themselves); ``mark[i]`` is true for an opening or
    closing quote; ``boundary[i]`` is true for unquoted, unescaped whitespace
    or a shell operator (``; | & ( ) < >``), which end a word.
    """

    quote: tuple[str | None, ...]
    mark: tuple[bool, ...]
    boundary: tuple[bool, ...]
    literal_quotes: frozenset[int] = frozenset()

    def word_start(self, index: int) -> int:
        while index > 0 and not self.boundary[index - 1]:
            index -= 1
        return index

    def word_end(self, index: int) -> int:
        while index < len(self.boundary) and not self.boundary[index]:
            index += 1
        return index


def _shell_layout(text: str) -> _ShellLayout:
    """Lay ``text`` out as a POSIX shell reads it.

    A quote left open at the end is read as a literal character, so an
    unbalanced quote never stretches a word over the rest of the text.
    """
    literal: set[int] = set()
    while True:
        layout, unclosed = _scan_shell(text, literal)
        if unclosed is None:
            return _ShellLayout(layout.quote, layout.mark, layout.boundary, frozenset(literal))
        literal.add(unclosed)


def _scan_shell(text: str, literal: set[int]) -> tuple[_ShellLayout, int | None]:
    quote: list[str | None] = [None] * len(text)
    mark = [False] * len(text)
    boundary = [False] * len(text)
    open_quote: str | None = None
    opened_at = -1
    index = 0
    while index < len(text):
        char = text[index]
        if open_quote is None:
            if char == "\\":
                index += 2  # the escaped character is neither a quote nor a boundary
                continue
            if char in _QUOTES and index not in literal:
                open_quote, opened_at = char, index
                mark[index] = True
            elif char.isspace() or char in _SHELL_OPERATORS:
                boundary[index] = True
        elif char == open_quote:
            open_quote = None
            mark[index] = True
        else:
            quote[index] = open_quote
            if char == "\\" and open_quote == '"' and index + 1 < len(text):
                quote[index + 1] = open_quote
                index += 2
                continue
        index += 1
    layout = _ShellLayout(tuple(quote), tuple(mark), tuple(boundary))
    return layout, (opened_at if open_quote is not None else None)


def _inside_url(text: str, layout: _ShellLayout, start: int) -> bool:
    """Whether ``text[start:]`` continues a URL begun earlier in the same argument.

    A URL runs to the first whitespace (a URL holds none, quoted or not) or
    unquoted shell operator (``>``, ``;``, ``&``...), and an argument holding a
    command substitution (``$(...)``, a backtick) is never treated as a URL's.
    A token can start at the ``//`` of the URL's own ``://`` (after its colon),
    so a scheme ending up to two characters past ``start`` counts.
    """
    url_start = start
    while url_start > 0 and not (layout.boundary[url_start - 1] or text[url_start - 1].isspace()):
        url_start -= 1
    # A command substitution runs a command of its own, whose redirections and
    # arguments are not the URL's text: no exemption across one.
    for index in range(url_start, start):
        if layout.quote[index] != "'" and (text[index] == "`" or text.startswith("$(", index)):
            return False
    scheme = _URL_SCHEME.search(text, url_start, min(len(text), start + 2))
    return scheme is not None and scheme.start() < start


def _after_placeholder(text: str, start: int) -> bool:
    return _PLACEHOLDER_BEFORE.search(text, 0, start) is not None


def _root_of(path: str) -> str | None:
    """The local root an absolute path lies under once ``//``, ``.`` and ``..`` are collapsed."""
    normalized = posixpath.normpath(re.sub("/+", "/", path)).lower()
    for root in LOCAL_PATH_ROOTS:
        if normalized == root.lower() or normalized.startswith(root.lower() + "/"):
            return root
    return None


def find_local_paths(text: str) -> list[LocalPath]:
    """Return every path on the writing machine in ``text``, in order.

    A path is a ``file:`` URL; an absolute path that lies under one of
    ``LOCAL_PATH_ROOTS`` (any case) once ``//``, ``.`` and ``..`` are collapsed,
    or is the root itself; a home-relative path (``~/``, ``~user/``,
    ``$HOME/``, ``${HOME}/``, ``$TMPDIR/``, ``%USERPROFILE%\\`` and the other
    Windows per-user variables); or a Windows user profile (``C:\\Users\\``).
    All but the variables must start a token: at the start of the text, or after
    whitespace, a quote, ``=``, ``:``, a shell operator or bracket, optionally
    behind a short-option cluster, ``@`` or variables (``-o/path``, ``@/path``,
    ``$X/path``).

    The text is read three times: as written; as a shell's words spell it once
    quotes, backslash escapes and line continuations are removed
    (``/U\\sers``, ``/U'se'rs`` and ``\\/Users`` are ``/Users``); and with every
    quote mark and backslash removed whatever its context, which also reads
    the quoting inside a command substitution (``"$(cat '/U'sers/x)"``). A path
    found in any reading is reported, at its span in ``text``. Expansions are
    not evaluated: a glob, a brace list, a variable other than the home
    directory, or a command's output is read as the text it is.

    Not paths: a root later in a URL argument than its ``scheme://`` (the URL's
    path, query or fragment, ``https://x.gov/?f=/home/a``; whitespace or an
    unquoted shell operator such as ``>`` or ``;`` ends the argument, and one
    holding a command substitution is no URL's); a root inside a relative path
    (``data/tmp/``) or after a placeholder (``<scratchpad>/tmp/``); ``~`` or
    ``$HOME`` with no path after it. A ``file:`` URL is read wherever it
    appears, even inside another URL; a home-directory variable is read quoted
    or not, and after a placeholder. A URL spelled across quotes or escapes is
    read as text, and what follows it may be reported.
    """
    layout = _shell_layout(text)
    found = _find_in_reading(text, list(range(len(text))), text, layout)
    for reading, origin in (_dequote(text, layout.literal_quotes), _strip_quoting(text)):
        if reading != text:
            found += _find_in_reading(reading, origin, text, layout)
    # A path inside a longer one, or found in both readings, is reported once.
    found.sort(key=lambda path: (path.start, -path.end))
    reported: list[LocalPath] = []
    for path in found:
        if reported and path.start < reported[-1].end:
            continue
        reported.append(path)
    return reported


def _find_in_reading(
    reading: str, origin: list[int], text: str, layout: _ShellLayout
) -> list[LocalPath]:
    """The paths in ``reading``, a version of ``text`` whose ``i``-th character is ``text[origin[i]]``."""

    def span(start: int, end: int) -> tuple[int, int]:
        return origin[start], origin[end - 1] + 1

    found: list[LocalPath] = []
    for match in _ABSOLUTE.finditer(reading):
        start, end = span(*match.span("absolute"))
        root = _root_of(match.group("absolute"))
        if (
            root is None
            or _inside_url(text, layout, start)
            or _after_placeholder(reading, match.start("absolute"))
        ):
            continue
        found.append(LocalPath(start, end, "absolute", root))
    for match in _OTHER_PATHS.finditer(reading):
        kind = next(name for name in _OTHER_KINDS if match.group(name) is not None)
        start, end = span(*match.span(kind))
        if kind != "file_url" and _inside_url(text, layout, start):
            continue
        root = ""
        if kind == "home_variable":
            variable = _HOME_VARIABLE_ROOT.match(match.group(kind))
            root = variable.group() if variable else ""
        found.append(LocalPath(start, end, kind, root))
    return found


def _strip_quoting(text: str) -> tuple[str, list[int]]:
    """``text`` with line continuations, then every quote mark and backslash, removed.

    A superset reading: it ignores where each quote opens and closes, so it
    reads quoting the shell would apply in a nested context (a command
    substitution inside double quotes) as well as some it would not.
    """
    out: list[str] = []
    origin: list[int] = []
    index = 0
    while index < len(text):
        if text.startswith("\\\n", index):
            index += 2
            continue
        if text[index] not in "'\"\\":
            out.append(text[index])
            origin.append(index)
        index += 1
    return "".join(out), origin


def _dequote(text: str, literal_quotes: frozenset[int] = frozenset()) -> tuple[str, list[int]]:
    """``text`` with quote marks, backslash escapes and line continuations removed.

    Returns the result and, for each of its characters, the index in ``text``
    it came from. Outside quotes a backslash escapes the next character and a
    backslash-newline disappears; inside double quotes only ``$ ` " \\`` and a
    newline can be escaped; inside single quotes nothing can. Backticks are kept,
    and so is a quote in ``literal_quotes`` (one left open, as ``_shell_layout``
    reads it).
    """
    out: list[str] = []
    origin: list[int] = []
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        escapable = None if quote == "'" else ('$`"\\\n' if quote == '"' else "")
        if char == "\\" and escapable is not None and index + 1 < len(text):
            following = text[index + 1]
            if quote is None or following in escapable:
                if following != "\n":
                    out.append(following)
                    origin.append(index + 1)
                index += 2
                continue
        if quote is None and char in "'\"" and index not in literal_quotes:
            quote = char
        elif char == quote:
            quote = None
        else:
            out.append(char)
            origin.append(index)
        index += 1
    return "".join(out), origin


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


# The signature's value is base64, whose alphabet holds ``/``; it records bytes,
# not a path. Only that node is skipped: a key spelled ``"signature.value"`` is
# read like any other.
_UNSCANNED_NODE = ("signature", "value")


def local_path_fields(payload: Any) -> list[tuple[str, LocalPath]]:
    """Return ``(field, path)`` for every local path in a manifest's strings.

    Every string is read, at any depth: values and object keys alike, with
    lists indexed (``applied_files[3].path``). The top-level ``signature``
    object's ``value`` is base64 and is not read when it is a string.
    """
    return list(_walk(payload, "", ()))


def _walk(value: Any, field: str, node: tuple[object, ...]) -> Iterator[tuple[str, LocalPath]]:
    if isinstance(value, dict):
        for key, child in value.items():
            # A key that is itself a local path is named by its root only.
            name = redact_local_paths(key) if isinstance(key, str) else str(key)
            child_field = f"{field}.{name}" if field else name
            if isinstance(key, str):
                for path in find_local_paths(key):
                    yield f"{child_field} (key)", path
            child_node = (*node, key)
            if child_node != _UNSCANNED_NODE or not isinstance(child, str):
                yield from _walk(child, child_field, child_node)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{field}[{index}]", (*node, index))
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


# --- Rewriting checkout paths -----------------------------------------------

# A path token that may name a place in the checkout: absolute, or under the
# home directory.
_PATH_TOKEN = re.compile(
    rf"{_AT_TOKEN_START}(?P<lead>{_LEAD})"
    rf"(?P<path>(?:/|~[A-Za-z0-9._-]*/|\$HOME/|\$\{{HOME\}}/){_TOKEN_REST})"
)
_HAS_DELIMITER = re.compile(f"[{_DELIMITERS}]")
_FILE_SCHEME_BEFORE = re.compile(r"(?i)(?<![A-Za-z0-9+.-])file:/*\Z")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# What may precede a path in its word: an option's or an assignment's ``=``, or
# earlier entries of a search-path list (``PATH=a:``, ``PYTHONPATH=a:b:``).
_VALUE_PREFIX = re.compile(r"(?:--?[A-Za-z0-9][A-Za-z0-9_.-]*|[A-Za-z_][A-Za-z0-9_]*)=")
_LIST_VARIABLE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*)?(?:PATH|DIRS)=")
_LIST_PREFIX = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*)?(?:PATH|DIRS)=(?:[^:]*:)*")
# Characters a shell expands where they are unquoted, and where double-quoted.
_ACTIVE_UNQUOTED = frozenset("$`*?[{\\")
_ACTIVE_DOUBLE_QUOTED = frozenset("$`\\")
_HOME_PREFIX = re.compile(r"\$HOME|\$\{HOME\}")


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
    in a ``file:`` URL are left alone.

    A rewrite is made only where it names the same file to a shell (see
    ``_names_the_same_file``), and a relative form that could be misread (a
    checkout directory named ``~cache``, or one after a short option) is written
    ``./~cache`` (see ``_unambiguous``).
    """
    layout = _shell_layout(text)
    roots = _checkout_spellings(repo)
    home = os.path.expanduser("~")
    rewrites: list[RepoRewrite] = []

    def consider(match: re.Match[str], relative: str | None) -> None:
        start, end = match.span("path")
        if (
            relative is None
            or _after_placeholder(text, start)
            or _FILE_SCHEME_BEFORE.search(text, 0, start) is not None
            or _inside_url(text, layout, start)
            or _overlaps(rewrites, start, end)
        ):
            return
        recorded = _recorded_form(text, layout, match, relative)
        if recorded is not None:
            rewrites.append(RepoRewrite(start, end, recorded))

    # A checkout path the tokenizer would split (``/Users/x/My Repo``), as written.
    for root in roots:
        if not _HAS_DELIMITER.search(root):
            continue
        literal = re.compile(
            rf"{_AT_TOKEN_START}(?P<lead>{_LEAD})"
            rf"(?P<path>{re.escape(root)}(?P<rest>/{_TOKEN_REST})?)(?=[{_DELIMITERS}]|\Z)"
        )
        for match in literal.finditer(text):
            rest = match.group("rest") or ""
            relative: str | None
            if ".." in rest.split("/"):
                relative = None
            elif rest in ("", "/"):
                relative = "." + rest
            else:
                relative = os.path.normpath(rest[1:]) + ("/" if rest.endswith("/") else "")
            consider(match, relative)

    for match in _PATH_TOKEN.finditer(text):
        consider(match, _relative_to_checkout(match.group("path"), roots=roots, home=home))
    return sorted(rewrites, key=lambda rewrite: rewrite.start)


def _recorded_form(
    text: str, layout: _ShellLayout, match: re.Match[str], relative: str
) -> str | None:
    """How to record the checkout path ``match`` names, or ``None`` if no form keeps its file.

    The path is the shell word, or the part of it that option syntax hands a
    program as a value: what precedes it in the word, quote marks aside, must be
    nothing, an option's or assignment's ``--name=`` / ``NAME=``, or earlier
    entries of a search-path list (``PATH=a:``, any ``*PATH`` or ``*DIRS``
    variable). What follows it in the word is harmless when it continues the
    path (``/...``) or, in such a list, starts the next entry (``:``). Anything
    else joins the path's last name, so the path's tail must stay as written:
    ``"<checkout>"-backup`` is a sibling directory, not ``.-backup``, and
    ``<checkout>/data/.=z`` is the file ``.=z`` in ``data``, not ``data=z``.

    Nothing is rewritten where the shell would compute the name: a word (in a
    search-path list, the entry) with an unquoted ``$``, glob, brace or
    backslash (or a double-quoted ``$`` or backslash) other than a leading
    ``$HOME``, or with a backtick anywhere; a ``~`` that is quoted or does not
    start the word; a single-quoted ``$HOME``. Nor is a path that spans a word
    boundary (an unquoted space).

    The form is ``relative``, written ``./relative`` where it could be read as
    something else (see ``_unambiguous``), where it is a whole word without a
    slash (``./tool``, which ``tool`` would not name as a command), and where
    the rewritten word would start like an assignment (``x=:...``), which a
    second reading would take apart differently.
    """
    lead, lead_start, (start, end) = match.group("lead"), match.start("lead"), match.span("path")
    if any(layout.boundary[index] for index in range(lead_start, end)):
        return None
    word_start, word_end = layout.word_start(lead_start), layout.word_end(end)

    def unquoted(begin: int, stop: int) -> str:
        return "".join(text[index] for index in range(begin, stop) if not layout.mark[index])

    before, after = unquoted(word_start, lead_start), unquoted(end, word_end)
    path = match.group("path")
    quote = layout.quote[start]
    if path.startswith("~") and (quote is not None or before or lead):
        return None  # the shell expands ``~`` only unquoted, at the start of a word
    home = _HOME_PREFIX.match(path)
    if home and quote == "'":
        return None  # single-quoted, ``$HOME`` is literal
    in_list = _LIST_VARIABLE.match(unquoted(word_start, word_end)) is not None
    # The text that names this path's file: the word, or in a search-path list
    # only this entry (``PATH=<checkout>/bin:$PATH`` expands ``$PATH`` apart).
    entry_start, entry_end = word_start, word_end
    if in_list:
        entry_start = max(word_start, text.rfind(":", word_start, lead_start) + 1)
        colon = text.find(":", end, word_end)
        entry_end = word_end if colon < 0 else colon
    skipped = range(start, start + home.end()) if home else range(0)
    # A backtick runs a command whose own expansions decide the name.
    if any(
        layout.quote[index] == "`" or text[index] == "`" for index in range(entry_start, entry_end)
    ):
        return None
    for index in range(entry_start, entry_end):
        if layout.mark[index] or index in skipped:
            continue
        active = _ACTIVE_UNQUOTED if layout.quote[index] is None else _ACTIVE_DOUBLE_QUOTED
        if layout.quote[index] in (None, '"') and text[index] in active:
            return None
    if before and not (
        _VALUE_PREFIX.fullmatch(before) or (in_list and _LIST_PREFIX.fullmatch(before))
    ):
        return None
    glued = bool(after) and after[0] != "/" and not (in_list and after[0] == ":")
    # A tail glued to what follows must stay exactly as written.
    if glued and not text[start:end].endswith("/" + relative.removeprefix("./")):
        return None
    recorded = _unambiguous(relative, lead)
    if (
        not before
        and not lead
        and ("/" not in recorded + after or _ASSIGNMENT.match(recorded + after))
    ):
        # A whole word without a slash is a command name to the shell, and to
        # ``env``, ``sudo`` or ``uv run``: ``tool`` is looked up on PATH, while
        # ``<checkout>/tool`` was this file. ``./`` keeps it a path.
        # (``.`` alone becomes ``./``; glued to more of the word it keeps its
        # ``.``: ``<checkout>/.=z`` is ``./.=z``.)
        recorded = "./" if recorded == "." and not after else "./" + recorded
    return recorded


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
    ``-oprivate`` with the path ``/var/x``. (A path holding ``$`` is never
    rewritten; see ``_recorded_form``.)
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
