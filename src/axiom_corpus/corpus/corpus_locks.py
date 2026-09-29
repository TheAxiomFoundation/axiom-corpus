"""Scope lock files: git's record of which corpus bytes a commit contains.

Protected corpus artifacts (``data/corpus/{sources,inventory,provisions,coverage}``)
live outside git. Each scope has one lock file under ``.axiom/corpus-locks`` that
pins every protected file of the scope by repository path, sha256 and size. See
``docs/corpus-storage.md``.
"""

from __future__ import annotations

import bisect
import contextlib
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

ScopeKey = tuple[str, str, str]

CORPUS_BASE = "data/corpus"
LOCK_ROOT = Path(".axiom") / "corpus-locks"
LOCK_SCHEMA_VERSION = "axiom-corpus/corpus-lock/v1"
PROTECTED_ARTIFACT_CLASSES = ("sources", "inventory", "provisions", "coverage")
PROTECTED_CORPUS_PREFIXES = tuple(
    f"{CORPUS_BASE}/{artifact_class}/" for artifact_class in PROTECTED_ARTIFACT_CLASSES
)
SINGLE_FILE_SUFFIXES = {
    "inventory": ".json",
    "provisions": ".jsonl",
    "coverage": ".json",
}

# Fetch writes its temporary files under this directory (git-ignored, never
# inside a scope), and names them with this marker.
FETCH_TEMP_DIR = f"{CORPUS_BASE}/.corpus-fetch-tmp"
FETCH_TEMP_MARKER = ".corpus-fetch-"

_SCOPE_COMPONENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,255}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_BLOB_RE = re.compile(r"^[0-9a-f]{40}$")
_ENTRY_KEYS = ("path", "sha256", "size", "git_blob")
_LOCK_KEYS = ("schema_version", "jurisdiction", "document_class", "version", "files")


class LockFormatError(ValueError):
    """Raised when a lock file or lock entry violates the lock contract."""


@dataclass(frozen=True, order=True)
class LockEntry:
    """One protected corpus file pinned by content."""

    path: str
    sha256: str
    size: int
    git_blob: str | None = None

    def __post_init__(self) -> None:
        _validate_corpus_path(self.path)
        if not isinstance(self.sha256, str) or not _SHA256_RE.fullmatch(self.sha256):
            raise LockFormatError(f"lock entry sha256 must be 64 lowercase hex: {self.path}")
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 0:
            raise LockFormatError(f"lock entry size must be a non-negative integer: {self.path}")
        if self.git_blob is not None and (
            not isinstance(self.git_blob, str) or not _GIT_BLOB_RE.fullmatch(self.git_blob)
        ):
            raise LockFormatError(f"lock entry git_blob must be 40 lowercase hex: {self.path}")

    @property
    def content(self) -> tuple[str, int]:
        """The (sha256, size) pair that identifies this entry's bytes."""
        return (self.sha256, self.size)

    def to_mapping(self) -> dict[str, object]:
        mapping: dict[str, object] = {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
        }
        if self.git_blob is not None:
            mapping["git_blob"] = self.git_blob
        return mapping


@dataclass(frozen=True)
class CorpusLock:
    """All protected files of one ``(jurisdiction, document_class, version)`` scope."""

    jurisdiction: str
    document_class: str
    version: str
    files: tuple[LockEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for label, value in (
            ("jurisdiction", self.jurisdiction),
            ("document_class", self.document_class),
            ("version", self.version),
        ):
            if not isinstance(value, str) or not _SCOPE_COMPONENT_RE.fullmatch(value):
                raise LockFormatError(f"lock {label} is not a valid scope component: {value!r}")
        if not self.files:
            raise LockFormatError(f"lock for {'/'.join(self.scope)} lists no files")
        paths = [entry.path for entry in self.files]
        if paths != sorted(paths):
            raise LockFormatError(f"lock entries for {'/'.join(self.scope)} are not sorted by path")
        if len(set(paths)) != len(paths):
            raise LockFormatError(f"lock for {'/'.join(self.scope)} lists a path twice")
        for entry in self.files:
            if scope_for_path(entry.path) != self.scope:
                raise LockFormatError(
                    f"lock for {'/'.join(self.scope)} lists a path outside the scope: {entry.path}"
                )

    @property
    def scope(self) -> ScopeKey:
        return (self.jurisdiction, self.document_class, self.version)

    @property
    def relative_path(self) -> Path:
        return lock_path_for_scope(self.scope)

    @property
    def total_bytes(self) -> int:
        return sum(entry.size for entry in self.files)

    @classmethod
    def from_entries(cls, scope: ScopeKey, entries: Iterable[LockEntry]) -> CorpusLock:
        return cls(*scope, files=tuple(sorted(entries, key=lambda entry: entry.path)))


def is_protected_corpus_path(path: str) -> bool:
    """True for repository paths under the four git-excluded artifact prefixes."""
    return any(path.startswith(prefix) for prefix in PROTECTED_CORPUS_PREFIXES)


def fold_path(path: str) -> str:
    """A spelling-insensitive key for ``path``.

    Case-insensitive, normalization-insensitive filesystems (APFS, HFS+, NTFS)
    put ``DATA/corpus``, ``data/corpus``, ``data/corpu\u017f`` (long s) and,
    on HFS+, ``data/corpu\u200cs`` (a zero-width non-joiner) in one place.
    Dropping format characters, then full case mapping and folding plus NFKC,
    maps every spelling we know to merge onto one key; it also merges some
    spellings a filesystem keeps apart, which only makes the checks that use
    it stricter.
    """
    text = unicodedata.normalize("NFKC", path)
    # HFS+ ignores format characters (ZWNJ, bidi marks, BOM) in names; drop them.
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    # upper().lower() maps the dotless i and long s to plain letters, as
    # NTFS-style upcasing does; casefold() covers the remaining foldings.
    return unicodedata.normalize("NFKC", text.upper().lower().casefold())


def lands_on_protected_path(path: str) -> bool:
    """True when ``path``, in any spelling a filesystem may merge, is a protected path.

    That includes the directories above the protected prefixes (``data``,
    ``data/corpus``, ``data/corpus/provisions``): a tracked file or symlink
    there would stand in for the whole directory.
    """
    folded = fold_path(path).rstrip("/")
    return any(
        folded.startswith(prefix) or prefix.startswith(f"{folded}/")
        for prefix in PROTECTED_CORPUS_PREFIXES
    )


def fold_collisions(paths: Iterable[str]) -> list[tuple[str, str]]:
    """Pairs of locked names that cannot both exist in one checkout.

    Two paths, or a path and a directory above another path, collide when
    they are equal (a file cannot also be a directory) or when a case- and
    normalization-insensitive filesystem stores them in one place
    (``B`` and ``b/3``, ``Act.html`` and ``act.html``). A lock set must be
    free of both, so it materializes the same way on every filesystem.
    """
    owner: dict[str, str] = {}
    directories: set[str] = set()
    files: set[str] = set()
    collisions: list[tuple[str, str]] = []
    for path in paths:
        files.add(path)
        parts = path.split("/")
        for depth in range(1, len(parts) + 1):
            name = "/".join(parts[:depth])
            if depth < len(parts):
                if name in directories:
                    continue
                directories.add(name)
            key = name.lower() if name.isascii() else fold_path(name)
            other = owner.setdefault(key, name)
            if other != name:
                collisions.append((other, name))
    collisions.extend((path, f"{path}/…") for path in sorted(files & directories))
    return collisions


def lands_on_lock_root(path: str) -> bool:
    """True when ``path``, in any merged spelling, lies under the lock directory."""
    return fold_path(path).startswith(f"{LOCK_ROOT.as_posix()}/")


def scope_for_path(path: str) -> ScopeKey | None:
    """Return the scope a protected repository path belongs to, or None."""
    if not is_protected_corpus_path(path):
        return None
    parts = path.split("/")[2:]
    artifact_class = parts[0]
    if artifact_class == "sources":
        if len(parts) < 5 or any(not part for part in parts):
            return None
        scope = (parts[1], parts[2], parts[3])
    else:
        suffix = SINGLE_FILE_SUFFIXES[artifact_class]
        if len(parts) != 4 or not parts[3].endswith(suffix):
            return None
        scope = (parts[1], parts[2], parts[3][: -len(suffix)])
    if not all(_SCOPE_COMPONENT_RE.fullmatch(part) for part in scope):
        return None
    return scope


def lock_path_for_scope(scope: ScopeKey) -> Path:
    """Repository-relative lock file path for one scope."""
    for part in scope:
        if not _SCOPE_COMPONENT_RE.fullmatch(part):
            raise LockFormatError(f"invalid scope component: {part!r}")
    jurisdiction, document_class, version = scope
    return LOCK_ROOT / jurisdiction / document_class / f"{version}.json"


def scope_for_lock_path(path: str | Path) -> ScopeKey | None:
    """Return the scope a repository-relative lock file path names, or None."""
    parts = Path(path).as_posix().split("/")
    root = LOCK_ROOT.as_posix().split("/")
    if len(parts) != len(root) + 3 or parts[: len(root)] != root:
        return None
    if not parts[-1].endswith(".json"):
        return None
    scope = (parts[-3], parts[-2], parts[-1][: -len(".json")])
    if not all(_SCOPE_COMPONENT_RE.fullmatch(part) for part in scope):
        return None
    return scope


def parse_scope_selector(text: str) -> tuple[str, ...]:
    """Parse ``<jurisdiction>[/<document_class>[/<version>]]`` into a prefix tuple."""
    parts = tuple(part for part in text.strip().strip("/").split("/"))
    if not parts or len(parts) > 3 or not all(_SCOPE_COMPONENT_RE.fullmatch(p) for p in parts):
        raise ValueError(
            f"scope must be <jurisdiction>[/<document_class>[/<version>]]: {text!r}"
        )
    return parts


def scope_matches(scope: ScopeKey, selector: tuple[str, ...]) -> bool:
    return scope[: len(selector)] == selector


def serialize_lock(lock: CorpusLock) -> bytes:
    """Canonical lock bytes: fixed key order, one entry per line, ASCII, final newline."""
    header = [
        f'  "schema_version": {json.dumps(LOCK_SCHEMA_VERSION)},',
        f'  "jurisdiction": {json.dumps(lock.jurisdiction)},',
        f'  "document_class": {json.dumps(lock.document_class)},',
        f'  "version": {json.dumps(lock.version)},',
        '  "files": [',
    ]
    entries = [
        "    " + json.dumps(entry.to_mapping(), ensure_ascii=True, separators=(", ", ": "))
        for entry in lock.files
    ]
    body = ",\n".join(entries)
    text = "{\n" + "\n".join(header) + "\n" + body + "\n  ]\n}\n"
    return text.encode("ascii")


def parse_lock(payload: bytes, *, source: str = "<lock>") -> CorpusLock:
    """Parse and validate lock bytes; reject anything but the canonical encoding."""
    try:
        raw = json.loads(payload.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LockFormatError(f"{source}: lock is not ASCII JSON: {exc}") from exc
    if not isinstance(raw, dict) or tuple(raw) != _LOCK_KEYS:
        raise LockFormatError(f"{source}: lock keys must be exactly {list(_LOCK_KEYS)} in order")
    if raw["schema_version"] != LOCK_SCHEMA_VERSION:
        raise LockFormatError(f"{source}: unsupported lock schema {raw['schema_version']!r}")
    files = raw["files"]
    if not isinstance(files, list):
        raise LockFormatError(f"{source}: lock files must be a list")
    entries: list[LockEntry] = []
    for item in files:
        if not isinstance(item, dict):
            raise LockFormatError(f"{source}: lock entry must be an object")
        keys = tuple(item)
        expected = _ENTRY_KEYS if "git_blob" in item else _ENTRY_KEYS[:3]
        if keys != expected:
            raise LockFormatError(f"{source}: lock entry keys must be {list(expected)} in order")
        entries.append(
            LockEntry(
                path=item["path"],
                sha256=item["sha256"],
                size=item["size"],
                git_blob=item.get("git_blob"),
            )
        )
    try:
        lock = CorpusLock(
            jurisdiction=raw["jurisdiction"],
            document_class=raw["document_class"],
            version=raw["version"],
            files=tuple(entries),
        )
    except LockFormatError as exc:
        raise LockFormatError(f"{source}: {exc}") from exc
    if serialize_lock(lock) != payload:
        raise LockFormatError(f"{source}: lock bytes are not in canonical form")
    return lock


def write_lock(repo: Path, lock: CorpusLock) -> Path:
    """Write one lock file atomically; return its absolute path."""
    target = repo / lock.relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(serialize_lock(lock))
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def remove_lock(repo: Path, scope: ScopeKey) -> bool:
    target = repo / lock_path_for_scope(scope)
    if target.exists():
        target.unlink()
        return True
    return False


@dataclass(frozen=True)
class LockSet:
    """All lock files of one tree, indexed by scope and by path."""

    locks: Mapping[ScopeKey, CorpusLock]
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        index: dict[str, LockEntry] = {}
        for lock in self.locks.values():
            for entry in lock.files:
                index[entry.path] = entry
        object.__setattr__(self, "_by_path", index)

    @property
    def by_path(self) -> Mapping[str, LockEntry]:
        return self._by_path  # type: ignore[attr-defined,no-any-return]

    def __bool__(self) -> bool:
        return bool(self.locks)

    def entries(self) -> Iterator[LockEntry]:
        for scope in sorted(self.locks):
            yield from self.locks[scope].files

    def select(
        self,
        selectors: Iterable[tuple[str, ...]] = (),
        *,
        scopes: Iterable[ScopeKey] = (),
    ) -> list[CorpusLock]:
        wanted_scopes = set(scopes)
        selector_list = list(selectors)
        return [
            lock
            for scope, lock in sorted(self.locks.items())
            if scope in wanted_scopes or any(scope_matches(scope, s) for s in selector_list)
        ]

    def entries_under(self, path: str) -> list[LockEntry]:
        """Entries at ``path`` or below it (a repository-relative file or directory)."""
        cleaned = path.strip("/")
        prefix = cleaned + "/"
        exact = self.by_path.get(cleaned)
        if exact is not None:
            return [exact]
        paths: list[str] | None = getattr(self, "_sorted_paths", None)
        if paths is None:
            paths = sorted(self.by_path)
            object.__setattr__(self, "_sorted_paths", paths)
        found: list[LockEntry] = []
        for index in range(bisect.bisect_left(paths, prefix), len(paths)):
            if not paths[index].startswith(prefix):
                break
            found.append(self.by_path[paths[index]])
        return found

    def with_whole_source_dirs(self, entries: Iterable[LockEntry]) -> list[LockEntry]:
        """Widen a selection so every scope's ``sources/`` directory is all or nothing.

        Code enumerates a scope's sources by listing the directory, so a
        partly fetched directory would read as a smaller scope.
        """
        chosen = {entry.path: entry for entry in entries}
        scopes = {
            scope_for_path(path)
            for path in chosen
            if path.startswith(f"{CORPUS_BASE}/sources/")
        }
        for scope in scopes:
            lock = self.locks.get(scope) if scope is not None else None
            if lock is None:
                continue
            for entry in lock.files:
                if entry.path.startswith(f"{CORPUS_BASE}/sources/"):
                    chosen.setdefault(entry.path, entry)
        return [chosen[path] for path in sorted(chosen)]

    def missing_under(self, repo: Path, path: str) -> list[LockEntry]:
        """Locked entries at or under ``path`` that the worktree lacks."""
        return [entry for entry in self.entries_under(path) if not (repo / entry.path).is_file()]


def load_locks(repo: Path) -> LockSet:
    """Load every lock file from a worktree, collecting (not raising) format errors.

    Hidden files (``.DS_Store``, editor swap files) are not lock files and
    git ignores them by default here, so they are skipped; any other stray
    file is an error.
    """
    root = repo / LOCK_ROOT
    payloads: dict[str, bytes] = {}
    if not root.is_dir():
        return _lock_set_from_payloads(payloads)
    spelling_error = _lock_root_spelling_error(repo)
    if spelling_error:
        return LockSet(locks={}, errors=(spelling_error,))
    nested = [path for path in root.rglob(".git") if path.parent != repo]
    if nested:
        return LockSet(
            locks={},
            errors=(
                f"`{nested[0].parent.relative_to(repo).as_posix()}` is a nested git "
                "repository (a submodule) inside the lock directory; the guard never "
                "checks locks there.",
            ),
        )
    links: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            links.append(path.relative_to(repo).as_posix())
            continue
        if not path.is_file():
            continue
        payloads[path.relative_to(repo).as_posix()] = path.read_bytes()
    loaded = _lock_set_from_payloads(payloads)
    if not links:
        return loaded
    return LockSet(
        locks=loaded.locks,
        errors=loaded.errors
        + tuple(f"`{link}` is a symlink in the lock directory; locks must be regular files." for link in links),
    )


def _lock_root_spelling_error(repo: Path) -> str | None:
    """An error when the on-disk lock directory is spelled other than ``.axiom/corpus-locks``.

    On a case-insensitive filesystem ``repo / ".axiom/corpus-locks"`` also opens
    ``.AXIOM/Corpus-Locks``, which git (and so the guard) sees as a different,
    unguarded path.
    """
    directory = repo
    for part in LOCK_ROOT.parts:
        try:
            names = os.listdir(directory)
        except OSError:
            return None
        if part not in names:
            actual = next((name for name in names if fold_path(name) == part), part)
            return (
                f"the lock directory is spelled `{(directory / actual).relative_to(repo).as_posix()}`, "
                f"not `{LOCK_ROOT.as_posix()}`; the guard never checks it. Rename it."
            )
        directory = directory / part
    return None


def load_locks_from_index(repo: Path) -> LockSet:
    """Load the lock files staged in git's index (what the next commit carries)."""
    result = subprocess.run(
        ["git", "ls-files", "-s", "-z", "--", LOCK_ROOT.as_posix()],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    staged: list[tuple[str, str]] = []
    unmerged: set[str] = set()
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, raw_oid, stage = meta.split()
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if stage != b"0":
            unmerged.add(path)
            continue
        if mode.decode("ascii") not in _REGULAR_MODES:
            unmerged.add(path)  # reported below; a gitlink or symlink is never a lock
            continue
        staged.append((path, raw_oid.decode("ascii")))
    by_oid: dict[str, bytes] = {}
    for blob_oid, chunks in iter_blob_contents(repo, sorted({oid for _path, oid in staged})):
        by_oid[blob_oid] = b"".join(chunks)
    loaded = _lock_set_from_payloads({path: by_oid[oid] for path, oid in staged})
    if not unmerged:
        return loaded
    conflicts = tuple(
        f"`{path}` has unresolved merge conflicts in the index, or is not a regular file."
        for path in sorted(unmerged)
    )
    return LockSet(locks=loaded.locks, errors=loaded.errors + conflicts)


def load_locks_at_ref(repo: Path, ref: str) -> LockSet:
    """Load every lock file from a git tree without touching the worktree."""
    payloads = read_tree_blobs(repo, ref, LOCK_ROOT.as_posix())
    loaded = _lock_set_from_payloads(payloads)
    irregular = _irregular_lock_tree_entries(repo, ref)
    if not irregular:
        return loaded
    return LockSet(locks=loaded.locks, errors=loaded.errors + irregular)


_REGULAR_MODES = frozenset({"100644", "100755"})


def _irregular_lock_tree_entries(repo: Path, ref: str) -> tuple[str, ...]:
    """Errors for anything under the lock root that is not a regular file.

    A submodule (gitlink) or symlink there is invisible to the blob readers,
    but ``git submodule update`` or a checkout would fill the directory with
    locks no guard ever read.
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-z", ref, "--", LOCK_ROOT.as_posix()],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    errors: list[str] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, kind, _oid = meta.decode("ascii").split()
        if kind != "blob" or mode not in _REGULAR_MODES:
            path = raw_path.decode("utf-8", errors="surrogateescape")
            errors.append(
                f"`{path}` is a {'submodule' if mode == '160000' else 'symlink' if mode == '120000' else kind} "
                "in the lock directory; only regular lock files may live there."
            )
    return tuple(errors)


def _lock_set_from_payloads(payloads: Mapping[str, bytes]) -> LockSet:
    locks: dict[ScopeKey, CorpusLock] = {}
    errors: list[str] = []
    owner: dict[str, ScopeKey] = {}
    for rel_path, payload in sorted(payloads.items()):
        if any(part.startswith(".") for part in rel_path.split("/")[len(LOCK_ROOT.parts) :]):
            continue  # .DS_Store, editor swap files: never locks, in any tree
        scope = scope_for_lock_path(rel_path)
        if scope is None:
            errors.append(f"`{rel_path}` is not a lock file path (.axiom/corpus-locks/<j>/<dc>/<v>.json).")
            continue
        try:
            lock = parse_lock(payload, source=rel_path)
        except LockFormatError as exc:
            errors.append(str(exc))
            continue
        if lock.scope != scope:
            errors.append(f"`{rel_path}` holds the lock for {'/'.join(lock.scope)}.")
            continue
        for entry in lock.files:
            previous = owner.get(entry.path)
            if previous is not None:
                errors.append(
                    f"`{entry.path}` is locked by both {'/'.join(previous)} and {'/'.join(scope)}."
                )
            owner[entry.path] = scope
        locks[scope] = lock
    errors.extend(
        f"`{first}` and `{second}` cannot both exist in one checkout "
        "(one is a directory of the other, or they differ only in case or Unicode form)."
        for first, second in fold_collisions(owner)[:20]
    )
    return LockSet(locks=locks, errors=tuple(errors))


@dataclass(frozen=True)
class TreeBlob:
    """One blob in a git tree."""

    path: str
    mode: str
    oid: str
    size: int


def list_tree_blobs(repo: Path, ref: str, *pathspecs: str) -> list[TreeBlob]:
    """List blobs under ``pathspecs`` at ``ref`` with their sizes."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-l", "-z", ref, "--", *pathspecs],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    blobs: list[TreeBlob] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, kind, oid, size = meta.split()
        if kind != b"blob":
            continue
        blobs.append(
            TreeBlob(
                path=raw_path.decode("utf-8", errors="surrogateescape"),
                mode=mode.decode("ascii"),
                oid=oid.decode("ascii"),
                size=int(size),
            )
        )
    return blobs


def iter_blob_contents(repo: Path, oids: Iterable[str]) -> Iterator[tuple[str, Iterator[bytes]]]:
    """Stream blob contents through one ``git cat-file --batch`` process.

    Yields ``(oid, chunks)``; the caller must exhaust ``chunks`` before advancing.
    """
    oid_list = list(oids)
    if not oid_list:
        return
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    import threading

    def feed() -> None:
        assert proc.stdin is not None
        try:
            for oid in oid_list:
                proc.stdin.write(oid.encode("ascii") + b"\n")
        except BrokenPipeError:
            pass  # the reader stopped early and closed the process
        finally:
            with contextlib.suppress(BrokenPipeError):
                proc.stdin.close()

    feeder = threading.Thread(target=feed, daemon=True)
    feeder.start()
    stdout = proc.stdout
    completed = False
    try:
        for oid in oid_list:
            header = stdout.readline().split()
            if len(header) != 3 or header[0].decode("ascii") != oid or header[1] != b"blob":
                raise LockFormatError(f"unexpected git cat-file header for {oid}: {header!r}")
            remaining = int(header[2])

            def chunks(remaining: int = remaining, oid: str = oid) -> Iterator[bytes]:
                left = remaining
                while left:
                    chunk = stdout.read(min(left, 1 << 20))
                    if not chunk:
                        raise LockFormatError(f"truncated git blob {oid}")
                    left -= len(chunk)
                    yield chunk

            generator = chunks()
            yield oid, generator
            for _ in generator:  # drain anything the caller left unread
                pass
            if stdout.read(1) != b"\n":
                raise LockFormatError(f"malformed git cat-file output after {oid}")
        completed = True
    finally:
        stdout.close()
        returncode = proc.wait()
        feeder.join(timeout=5)
    if completed and returncode != 0:
        raise LockFormatError(f"git cat-file --batch exited with status {returncode}")


def read_tree_blobs(repo: Path, ref: str, *pathspecs: str) -> dict[str, bytes]:
    """Read small blobs (lock files, manifests) under ``pathspecs`` at ``ref``."""
    blobs = list_tree_blobs(repo, ref, *pathspecs)
    by_oid: dict[str, bytes] = {}
    for oid, chunks in iter_blob_contents(repo, sorted({blob.oid for blob in blobs})):
        by_oid[oid] = b"".join(chunks)
    return {blob.path: by_oid[blob.oid] for blob in blobs}


@dataclass(frozen=True)
class HashedBlob:
    path: str
    oid: str
    sha256: str
    size: int


def hash_tree_blobs(repo: Path, blobs: Iterable[TreeBlob]) -> dict[str, HashedBlob]:
    """sha256 every blob once (deduplicated by object id); key the result by path."""
    blob_list = list(blobs)
    digests: dict[str, tuple[str, int]] = {}
    for oid, chunks in iter_blob_contents(repo, sorted({blob.oid for blob in blob_list})):
        digest = hashlib.sha256()
        size = 0
        for chunk in chunks:
            digest.update(chunk)
            size += len(chunk)
        digests[oid] = (digest.hexdigest(), size)
    return {
        blob.path: HashedBlob(
            path=blob.path,
            oid=blob.oid,
            sha256=digests[blob.oid][0],
            size=digests[blob.oid][1],
        )
        for blob in blob_list
    }


def protected_tree_blobs(repo: Path, ref: str) -> list[TreeBlob]:
    """Every tracked protected corpus blob at ``ref``."""
    return list_tree_blobs(repo, ref, *(prefix.rstrip("/") for prefix in PROTECTED_CORPUS_PREFIXES))


def locks_from_hashed_blobs(hashed: Mapping[str, HashedBlob]) -> dict[ScopeKey, CorpusLock]:
    """Group hashed protected blobs into per-scope locks that keep each blob id."""
    by_scope: dict[ScopeKey, list[LockEntry]] = {}
    unscoped: list[str] = []
    for path, blob in sorted(hashed.items()):
        scope = scope_for_path(path)
        if scope is None:
            unscoped.append(path)
            continue
        by_scope.setdefault(scope, []).append(
            LockEntry(path=path, sha256=blob.sha256, size=blob.size, git_blob=blob.oid)
        )
    if unscoped:
        raise LockFormatError(
            "protected paths outside any scope cannot be locked: " + ", ".join(unscoped[:20])
        )
    return {scope: CorpusLock.from_entries(scope, entries) for scope, entries in by_scope.items()}


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def scope_files_in_worktree(repo: Path, scope: ScopeKey) -> list[Path]:
    """Every regular protected file of ``scope`` present under ``data/corpus``."""
    jurisdiction, document_class, version = scope
    base = repo / CORPUS_BASE
    files: list[Path] = []
    source_root = base / "sources" / jurisdiction / document_class / version
    _refuse_symlinked_ancestors(repo, source_root)
    if source_root.is_dir():
        for directory, dirnames, filenames in os.walk(source_root, followlinks=False):
            for name in dirnames:
                if (Path(directory) / name).is_symlink():
                    raise LockFormatError(f"refusing to lock through a symlink: {Path(directory) / name}")
            files.extend(Path(directory) / name for name in filenames)
    for artifact_class, suffix in SINGLE_FILE_SUFFIXES.items():
        path = base / artifact_class / jurisdiction / document_class / f"{version}{suffix}"
        _refuse_symlinked_ancestors(repo, path)
        if path.exists() or path.is_symlink():
            files.append(path)
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise LockFormatError(f"refusing to lock a symlink or non-regular file: {path}")
        if FETCH_TEMP_MARKER in path.name:
            raise LockFormatError(
                f"refusing to lock an interrupted fetch's temporary file: {path}; delete it"
            )
        if path.name.startswith("."):
            # .DS_Store and editor files; no corpus artifact is hidden.
            raise LockFormatError(f"refusing to lock a hidden file: {path}; delete it")
    return sorted(files)


def _refuse_symlinked_ancestors(repo: Path, path: Path) -> None:
    """Refuse a path whose directories (below ``repo``) include a symlink."""
    lexical = repo
    for part in path.relative_to(repo).parts:
        lexical = lexical / part
        if lexical.is_symlink():
            raise LockFormatError(f"refusing to lock through a symlink: {lexical}")


def lock_from_worktree(
    repo: Path,
    scope: ScopeKey,
    *,
    previous: CorpusLock | None = None,
) -> CorpusLock:
    """Hash a scope's files in the worktree into a lock.

    Entries whose bytes match ``previous`` keep its ``git_blob``, so a relock
    of unchanged migrated files is a no-op.
    """
    previous_by_path = {entry.path: entry for entry in previous.files} if previous else {}
    entries: list[LockEntry] = []
    for path in scope_files_in_worktree(repo, scope):
        rel = path.relative_to(repo).as_posix()
        sha256, size = sha256_file(path)
        prior = previous_by_path.get(rel)
        git_blob = prior.git_blob if prior and prior.content == (sha256, size) else None
        entries.append(LockEntry(path=rel, sha256=sha256, size=size, git_blob=git_blob))
    if not entries:
        raise FileNotFoundError(
            f"No corpus artifacts found for {'/'.join(scope)} under {repo / CORPUS_BASE}."
        )
    return CorpusLock.from_entries(scope, entries)


@dataclass(frozen=True)
class LockDiff:
    """Per-path lock changes between two lock sets."""

    added: tuple[LockEntry, ...]
    changed: tuple[tuple[LockEntry, LockEntry], ...]
    removed: tuple[LockEntry, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.changed or self.removed)


def diff_lock_sets(base: LockSet, head: LockSet) -> LockDiff:
    added: list[LockEntry] = []
    changed: list[tuple[LockEntry, LockEntry]] = []
    removed: list[LockEntry] = []
    for path, entry in sorted(head.by_path.items()):
        prior = base.by_path.get(path)
        if prior is None:
            added.append(entry)
        elif prior != entry:
            changed.append((prior, entry))
    for path, entry in sorted(base.by_path.items()):
        if path not in head.by_path:
            removed.append(entry)
    return LockDiff(added=tuple(added), changed=tuple(changed), removed=tuple(removed))


_ASCII_CONTROL = frozenset(chr(code) for code in (*range(0x20), 0x7F))


def _validate_corpus_path(path: object) -> None:
    if not isinstance(path, str) or not path:
        raise LockFormatError("lock entry path must be a non-empty string")
    if path.isascii():
        # Fast path: ASCII is already NFC and its only category-C characters
        # are the controls.
        bad_characters = any(ch in _ASCII_CONTROL for ch in path)
    else:
        bad_characters = unicodedata.normalize("NFC", path) != path or any(
            unicodedata.category(ch).startswith("C") for ch in path
        )
    if (
        path.startswith("/")
        or "\\" in path
        or bad_characters
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise LockFormatError(f"lock entry path is not a canonical repository path: {path!r}")
    if not is_protected_corpus_path(path):
        raise LockFormatError(
            f"lock entry path is outside the protected corpus prefixes: {path!r}"
        )

