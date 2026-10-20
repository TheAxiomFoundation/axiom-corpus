"""Paths on one machine in the repository's unsigned records.

Run notes (``docs/ingest-runs/``), closure work (``docs/coverage/``), reasoning
logs (``.axiom/reasoning-logs/``) and source manifests (``manifests/``) are
public, like the signed ingest manifests that ``manifest_local_paths`` guards.
A path such as ``/Users/<name>/...``, ``/private/tmp/...`` or ``~/...`` reaches
no reader and publishes the operator's account name and directory layout. The
convention is the same: repository-relative paths for repository files, and
placeholders for directories on the machine (``<main-checkout>``,
``<worktrees>/<name>``, ``<rulespec-us>``, ``<axiom-cache>``, ``<scratchpad>``).

``find_record_local_paths`` finds such paths in a record's prose, markup or
data; ``audit_record_local_paths`` checks every record in the repository against
``.axiom/record-local-paths.yaml``, which grandfathers only records an ingest
manifest attests in ``reasoning_logs`` (their bytes cannot change without
signing that manifest again; signatures are verified where manifests are).
"""

from __future__ import annotations

import bisect
import functools
import hashlib
import json
import math
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import INGEST_MANIFEST_ROOT
from axiom_corpus.corpus.manifest_local_paths import (
    LOCAL_PATH_ROOTS,
    LocalPath,
    find_local_paths,
)

# Directories whose files are records of how the corpus was built.
RECORD_ROOTS: tuple[str, ...] = (
    ".axiom/reasoning-logs",
    "docs/coverage",
    "docs/ingest-runs",
    "manifests",
)
RECORD_LOCAL_PATH_ALLOWLIST_PATH = Path(".axiom") / "record-local-paths.yaml"
RECORD_LOCAL_PATH_ALLOWLIST_SCHEMA_VERSION = "axiom-corpus/record-local-paths/v1"

# Spellings that name no place below a root, so publish neither an account name
# nor a layout: a lone ``~`` (in records, "approximately", OCR noise, a
# ``#:~:text=`` URL fragment or a CSS sibling combinator), a bare ``file:``
# scheme (prose about ``file://`` URLs), ``$HOME`` alone, and a root alone.
_NO_PLACE = {
    "tilde": re.compile(r"~/?"),
    "file_url": re.compile(r"(?i)file:/*"),
    "home_variable": re.compile(r"(?i)(?:\$HOME|\$\{HOME\}|%USERPROFILE%)/?"),
    "windows": re.compile(r"(?i)[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]?"),
}
# ``/media/file/...`` is the path Drupal sites such as medicaid.gov serve files
# under; no machine mounts a volume for a user named ``file``. Every other
# ``/media/<user>/...`` path is a Linux removable-drive mount and is reported.
_WEB_PATH_PREFIXES = ("/media/file/",)

# ``find_local_paths`` reads command lines: a root starts a path only after
# whitespace, a quote, ``=``, ``:`` or a shell operator; a path right after
# ``<name>`` is relative to that placeholder; and text is read as written.
# Records are prose, markup and data, so each line that could hold a path is
# read up to three ways, and a path found in any reading is reported at its
# offset in the record:
# A. as written, with block tags (``<td>``, ``<li>``, ``<br>``) as spaces;
# B. as rendered: block tags as spaces and inline tags deleted (``<code>``,
#    ``<em class="x">``, or any tag the record closes, such as ``</path>``), so
#    ``/tmp/<b>job</b>/out`` is whole and ``data<em>/tmp/x</em>`` stays
#    relative; A keeps what B drops, such as a path in an attribute value;
# C. as B, after decoding the JSON and YAML escapes ``\\`` and ``\/``.
# In each, an opener before a path start (``@``, a typographic quote, or
# Markdown emphasis such as ``**`` that closes later on the line) becomes
# spaces. A placeholder such as ``<scratchpad>`` is neither a tag nor closed.
_BLOCK_ELEMENT = re.compile(
    r"address|article|aside|blockquote|body|br|caption|dd|details|div|dl|dt|figcaption"
    r"|figure|footer|h[1-6]|head|header|hr|html|li|main|nav|ol|p|pre|section|summary|table"
    r"|tbody|td|tfoot|th|thead|tr|ul"
)
_INLINE_ELEMENT = re.compile(
    r"a|abbr|b|cite|code|del|dfn|em|i|ins|kbd|mark|q|s|samp|small|span|strong|sub|sup|time"
    r"|tt|u|var"
)
_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9-]*)(\s[^<>]*)?/?>")
_CLOSING_TAG = re.compile(r"</([A-Za-z][A-Za-z0-9-]*)\s*>")
_ESCAPE = re.compile(r"\\([\\/])")
# Where a path can begin: a root, a home-relative ``~``, a Windows drive.
_PATH_START = re.compile(
    "|".join(re.escape(root) for root in LOCAL_PATH_ROOTS) + r"|~|[A-Za-z]:[\\/]"
)
_DELIMITER = re.compile(r"[\s\"'`=:,;|&()<>\[\]{}]")
_QUOTE_OPENERS = frozenset(
    "@\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u00ab\u00bb\u2039\u203a"
)
_EMPHASIS = frozenset("*_")
# Lower-cased bytes, one of which every line a reading can find a path in
# holds: what ``find_local_paths`` matches (its case-insensitive parts are
# ASCII, but Python also folds the four letters at the end onto ``i``, ``s``
# and ``k``), a closing tag (B can join a root split by markup) and the escapes
# C decodes. A line holding none is never read, which keeps a full scan fast.
_CANDIDATE = re.compile(
    b"|".join(
        re.escape(candidate)
        for candidate in (
            *sorted({root.lower().encode() for root in LOCAL_PATH_ROOTS}),
            b"~",
            b"$home",
            b"${home}",
            b"%userprofile%",
            b"file:/",
            b":\\users",
            b":/users",
            b":\\documents and settings",
            b":/documents and settings",
            b"</",
            b"\\\\",
            b"\\/",
            *(letter.encode() for letter in "\u0130\u0131\u017f\u212a"),
        )
    )
)

_TRACKING_ISSUE = re.compile(
    r"https://github\.com/TheAxiomFoundation/axiom-corpus/issues/[1-9][0-9]*"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def find_record_local_paths(text: str) -> list[LocalPath]:
    """Return the paths on the writing machine in a record's ``text``, in order.

    Each path ``find_local_paths`` finds starts inside one of these, unless it
    is a spelling that names no place (``~``, ``file://``, ``$HOME`` or a root
    such as ``/Users/`` alone) or a ``/media/file/`` web path. These also hold
    the paths it misses in prose, markup and data: after a tag
    (``<code>/Users/...``), split by inline markup (``/tmp/<b>job</b>/out``),
    after an opener (``**/tmp/...**``, ``@/Users/...``, ``“~alice/...”``) and
    escaped in JSON or YAML (``"C:\\\\Users\\\\alice"``). Offsets are the
    record's.
    """
    found: dict[int, LocalPath] = {}
    closed = _closed_tags(text)
    for start, line in _candidate_lines(text):
        for path in _line_paths(start, line, closed):
            found.setdefault(path.start, path)
    return [found[offset] for offset in sorted(found)]


def _closed_tags(text: str) -> set[str]:
    return {name.lower() for name in _CLOSING_TAG.findall(text)}


def _line_paths(start: int, line: str, closed: set[str]) -> list[LocalPath]:
    """Return the paths in ``line`` (at ``start`` in its record), read each way."""
    paths = []
    for reading in _readings(line, closed):
        for path in find_local_paths(reading.text):
            if not _names_no_place(reading.text, path):
                begin, end = reading.origin(path.start), reading.origin(path.end)
                paths.append(LocalPath(start + begin, start + end, path.kind, path.root))
    return paths


def _candidate_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(offset, line)`` for each line of ``text`` holding a ``_CANDIDATE``."""
    data = text.encode("utf-8", "surrogatepass")
    lines: list[tuple[int, str]] = []
    line_end = -1
    char_at = byte_at = 0
    for candidate in _CANDIDATE.finditer(data.lower()):
        if candidate.start() <= line_end:
            continue
        line_start = data.rfind(b"\n", 0, candidate.start()) + 1
        line_end = data.find(b"\n", candidate.start())
        line_end = len(data) if line_end == -1 else line_end
        char_at += len(data[byte_at:line_start].decode("utf-8", "surrogatepass"))
        byte_at = line_start
        lines.append((char_at, data[line_start:line_end].decode("utf-8", "surrogatepass")))
    return lines


@dataclass(frozen=True)
class _Reading:
    """A line as read: ``(offset here, offset in base)`` at each piece's start."""

    text: str
    pieces: tuple[tuple[int, int], ...] = ((0, 0),)
    base: _Reading | None = None

    def origin(self, offset: int) -> int:
        """Map an offset in this reading to the line's."""
        at, source = self.pieces[bisect.bisect_right(self.pieces, (offset, math.inf)) - 1]
        offset = source + offset - at
        return offset if self.base is None else self.base.origin(offset)

    def with_text(self, text: str) -> _Reading:
        """The same reading with ``text`` of the same length in place of its own."""
        return _Reading(text, self.pieces, self.base)

    def rewritten(
        self, pattern: re.Pattern[str], replace: Callable[[re.Match[str]], str]
    ) -> _Reading:
        """This reading with each match of ``pattern`` replaced."""
        parts: list[str] = []
        pieces = [(0, 0)]
        length = position = 0
        for match in pattern.finditer(self.text):
            new = replace(match)
            if new == match.group():
                continue
            parts.append(self.text[position : match.start()])
            length += match.start() - position
            pieces.append((length, match.start()))
            parts.append(new)
            length += len(new)
            pieces.append((length, match.end()))
            position = match.end()
        parts.append(self.text[position:])
        return _Reading("".join(parts), tuple(pieces), self)


def _readings(line: str, closed: set[str]) -> list[_Reading]:
    def is_block(tag: re.Match[str]) -> bool:
        return _BLOCK_ELEMENT.fullmatch(tag.group(2).lower()) is not None

    def is_inline(tag: re.Match[str]) -> bool:
        name = tag.group(2).lower()
        return not is_block(tag) and (_INLINE_ELEMENT.fullmatch(name) is not None or name in closed)

    def as_written(tag: re.Match[str]) -> str:
        bare_block = is_block(tag) and tag.group(3) is None
        return " " * len(tag.group()) if bare_block else tag.group()

    def as_rendered(tag: re.Match[str]) -> str:
        if is_block(tag):
            return " " * len(tag.group())
        return "" if is_inline(tag) else tag.group()

    line_reading = _Reading(line)
    written = line_reading.rewritten(_TAG, as_written)
    readings = [written.with_text(_open_tokens(written.text))]
    if any(is_block(tag) or is_inline(tag) for tag in _TAG.finditer(line)):
        rendered = line_reading.rewritten(_TAG, as_rendered)
        readings.append(rendered.with_text(_open_tokens(rendered.text)))
    if _ESCAPE.search(line):
        decoded = line_reading.rewritten(_ESCAPE, lambda escape: escape.group(1))
        rendered = decoded.rewritten(_TAG, as_rendered)
        readings.append(rendered.with_text(_open_tokens(rendered.text)))
    return readings


def _open_tokens(line: str) -> str:
    """Blank the openers before each path start, keeping offsets."""
    chars: list[str] | None = None
    for start in _PATH_START.finditer(line):
        at = begin = start.start()
        while begin > 0 and (line[begin - 1] in _QUOTE_OPENERS or line[begin - 1] in _EMPHASIS):
            begin -= 1
        if begin == at or (begin > 0 and not _DELIMITER.match(line, begin - 1)):
            continue
        emphasis = "".join(char for char in line[begin:at] if char in _EMPHASIS)
        if emphasis and not _closes(line, at, emphasis):
            continue
        chars = chars or list(line)
        chars[begin:at] = " " * (at - begin)
    return line if chars is None else "".join(chars)


def _closes(line: str, after: int, emphasis: str) -> bool:
    """Whether Markdown emphasis ``emphasis`` closes on ``line`` after ``after``."""
    return _closer(emphasis).search(line, after) is not None


@functools.cache
def _closer(emphasis: str) -> re.Pattern[str]:
    return re.compile(rf"(?<=\S){re.escape(emphasis)}(?=$|[\s.,;:!?)\]\"'`])")


def _names_no_place(text: str, path: LocalPath) -> bool:
    token = text[path.start : path.end]
    if path.kind == "absolute":
        return token == path.root or token.startswith(_WEB_PATH_PREFIXES)
    return _NO_PLACE[path.kind].fullmatch(token) is not None


@dataclass(frozen=True)
class RecordAllowance:
    """One grandfathered record: its exact bytes, the manifests that attest them, its issue."""

    path: str
    sha256: str
    attested_by: tuple[str, ...]
    issue: str


def load_record_local_path_allowlist(path: Path) -> list[RecordAllowance]:
    """Read ``.axiom/record-local-paths.yaml``; raise ``ValueError`` if malformed."""
    try:
        document = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ValueError("is not YAML") from exc
    if not isinstance(document, dict):
        raise ValueError("is not a mapping")
    if document.get("schema_version") != RECORD_LOCAL_PATH_ALLOWLIST_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be `{RECORD_LOCAL_PATH_ALLOWLIST_SCHEMA_VERSION}`")
    raw = document.get("records")
    if not isinstance(raw, list):
        raise ValueError("`records` must be a list")
    allowances: list[RecordAllowance] = []
    for index, item in enumerate(raw):
        where = f"`records[{index}]`"
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "attested_by", "issue"}:
            raise ValueError(f"{where} must have exactly path, sha256, attested_by and issue")
        entry_path, digest, attested_by, issue = (
            item["path"],
            item["sha256"],
            item["attested_by"],
            item["issue"],
        )
        if not (isinstance(entry_path, str) and _is_record_path(entry_path)):
            raise ValueError(f"{where} path must name a file under {', '.join(RECORD_ROOTS)}")
        if not (isinstance(digest, str) and _SHA256.fullmatch(digest)):
            raise ValueError(f"{where} sha256 must be 64 lowercase hex digits")
        if not (
            isinstance(attested_by, list)
            and attested_by
            and all(
                isinstance(name, str) and _is_ingest_manifest_path(name) for name in attested_by
            )
            and attested_by == sorted(set(attested_by))
        ):
            raise ValueError(
                f"{where} attested_by must be a sorted list of distinct .json files "
                f"under {INGEST_MANIFEST_ROOT.as_posix()}/"
            )
        if not (isinstance(issue, str) and _TRACKING_ISSUE.fullmatch(issue)):
            raise ValueError(f"{where} issue must be an axiom-corpus issue URL")
        allowances.append(RecordAllowance(entry_path, digest, tuple(attested_by), issue))
    return allowances


def _is_record_path(path: str) -> bool:
    parts = path.split("/")
    return (
        ".." not in parts
        and "" not in parts
        and any(path.startswith(f"{root}/") for root in RECORD_ROOTS)
    )


def _is_ingest_manifest_path(path: str) -> bool:
    parts = path.split("/")
    return (
        path.startswith(f"{INGEST_MANIFEST_ROOT.as_posix()}/")
        and path.endswith(".json")
        and ".." not in parts
        and "" not in parts
    )


def record_files(repo: Path) -> list[str]:
    """Return the records in ``repo``: tracked or untracked, never git-ignored.

    Ignored files (``__pycache__/``, ``.DS_Store``, ``downloads/``) are local
    by-products, not records. A tracked file deleted from the working tree is
    not listed; a symbolic link is.
    """
    listed = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *RECORD_ROOTS,
        ],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return sorted(
        {
            name
            for name in listed.split("\0")
            if name and ((repo / name).is_symlink() or (repo / name).exists())
        }
    )


def _attestations(repo: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Map each record an ingest manifest attests to ``{manifest: sha256}``."""
    attested: dict[str, dict[str, str]] = {}
    issues: list[str] = []
    root = repo / INGEST_MANIFEST_ROOT
    for manifest in sorted(root.rglob("*.json")) if root.is_dir() else []:
        relative = manifest.relative_to(repo).as_posix()
        try:
            payload = json.loads(manifest.read_bytes())
            logs = payload.get("reasoning_logs") or []
            entries = [(str(log["path"]), str(log["sha256"])) for log in logs]
        except OSError as exc:
            issues.append(f"`{relative}` cannot be read ({exc.strerror}).")
            continue
        except (ValueError, TypeError, KeyError, AttributeError):
            issues.append(f"`{relative}` cannot be read, so the records it attests are unknown.")
            continue
        for path, digest in entries:
            attested.setdefault(path, {})[relative] = digest
    return attested, issues


def audit_record_local_paths(
    repo: Path,
    *,
    grandfathered: frozenset[tuple[str, str]],
    allowlist: Path = RECORD_LOCAL_PATH_ALLOWLIST_PATH,
) -> list[str]:
    """Return the issues that keep the repository's records from passing.

    Every record under ``RECORD_ROOTS`` must hold no path on the machine that
    wrote it (``find_record_local_paths``), unless the allowlist grandfathers
    it. An allowance holds only while its record keeps the bytes it pins, still
    holds a local path, and is attested at those bytes by exactly the ingest
    manifests it names, and only for ``(path, sha256)`` pairs in
    ``grandfathered``, so the allowlist only shrinks. A symbolic link, a record
    that cannot be read or is not UTF-8 text, an unreadable ingest manifest and a
    malformed allowlist fail closed. Messages name a path by its root and line
    only (``line 3 holds /Users/…``), never in full.
    """
    repo = repo.resolve()
    issues: list[str] = []
    try:
        allowances = load_record_local_path_allowlist(repo / allowlist)
    except OSError as exc:
        # strerror only: the exception's text names the absolute path.
        return [f"`{allowlist.as_posix()}` cannot be read ({exc.strerror})."]
    except ValueError as exc:
        return [f"`{allowlist.as_posix()}` {exc}."]
    attested, attestation_issues = _attestations(repo)
    issues.extend(attestation_issues)
    by_path: dict[str, RecordAllowance] = {}
    for allowance in allowances:
        if allowance.path in by_path:
            issues.append(f"`{allowlist.as_posix()}` lists `{allowance.path}` twice.")
        by_path[allowance.path] = allowance
        if (allowance.path, allowance.sha256) not in grandfathered:
            issues.append(
                f"`{allowlist.as_posix()}` lists `{allowance.path}` at bytes that were not "
                "grandfathered on 2026-10-20. The allowlist only shrinks: write the record "
                "without local paths instead of listing it."
            )
    for relative in record_files(repo):
        allowed = by_path.pop(relative, None)
        record = repo / relative
        if record.is_symlink():
            issues.append(
                f"`{relative}` is a symbolic link; a record is a file, and a link's target "
                "can name a path on the machine that made it."
            )
            continue
        try:
            payload = record.read_bytes()
        except OSError as exc:
            issues.append(f"`{relative}` cannot be read ({exc.strerror}).")
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(
                f"`{relative}` is not UTF-8 text, so it cannot be checked for local paths."
            )
            continue
        found = find_record_local_paths(text)
        if not found:
            if allowed is not None:
                issues.append(
                    f"`{relative}` no longer holds a local path; remove its entry from "
                    f"`{allowlist.as_posix()}` ({allowed.issue})."
                )
            continue
        if allowed is None:
            issues.append(f"`{relative}`: {_describe(text, found)}. {_REMEDY}")
            continue
        digest = hashlib.sha256(payload).hexdigest()
        if digest != allowed.sha256:
            issues.append(
                f"`{relative}` changed since it was grandfathered (sha256 "
                f"{allowed.sha256[:12]}…). A changed record must not hold local paths: "
                f"scrub them and remove its entry from `{allowlist.as_posix()}` "
                f"({allowed.issue}). {_describe(text, found)}."
            )
            continue
        attesting = tuple(
            sorted(
                manifest
                for manifest, recorded in attested.get(relative, {}).items()
                if recorded == digest
            )
        )
        if attesting != allowed.attested_by:
            issues.append(
                f"`{relative}` is attested at these bytes by "
                f"{', '.join(f'`{name}`' for name in attesting) or 'no ingest manifest'}, "
                f"but `{allowlist.as_posix()}` names "
                f"{', '.join(f'`{name}`' for name in allowed.attested_by)}. Only a record an "
                "ingest manifest attests is grandfathered; scrub any other."
            )
    for allowance in by_path.values():
        issues.append(
            f"`{allowlist.as_posix()}` lists `{allowance.path}`, which is not a record in the "
            "repository; remove its entry."
        )
    return issues


_REMEDY = (
    "Name repository files by their repository-relative path and directories on "
    "your machine by a placeholder such as `<main-checkout>`, `<worktrees>/<name>`, "
    "`<scratchpad>` or `<axiom-cache>`; a new record is never grandfathered."
)


def _describe(text: str, found: list[LocalPath]) -> str:
    by_line: dict[int, set[str]] = {}
    line, counted = 1, 0
    for path in found:
        line += text.count("\n", counted, path.start)
        counted = path.start
        by_line.setdefault(line, set()).add(path.describe())
    return "; ".join(
        f"line {line} holds {', '.join(sorted(roots))}" for line, roots in sorted(by_line.items())
    )
