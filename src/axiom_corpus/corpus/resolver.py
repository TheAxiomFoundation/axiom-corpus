"""Find corpus bytes for code that reads ``data/corpus`` paths.

Callers keep reading ``data/corpus/...``. The resolver makes sure the locked
files they need exist there first, fetching from the shared cache, local git
objects, or R2. With no lock files it does nothing, so the same code runs
before and after the corpus left git. See ``docs/corpus-storage.md``.
"""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import os
import posixpath
import stat
import subprocess
import sys
import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.content_store import (
    ContentCache,
    ContentStoreError,
    FetchReport,
    GitBlobSource,
    ObjectSource,
    R2ObjectStore,
    destination_state,
    materialize,
)
from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    LOCK_ROOT,
    PROTECTED_ARTIFACT_CLASSES,
    PROTECTED_CORPUS_PREFIXES,
    SINGLE_FILE_SUFFIXES,
    LockEntry,
    LockSet,
    ScopeKey,
    _caseless,
    fold_path,
    is_protected_corpus_path,
    load_locks,
    scope_for_path,
    stored_together,
)

NO_FETCH_ENV = "AXIOM_CORPUS_NO_FETCH"


class CorpusNotMaterializedError(FileNotFoundError):
    """A locked corpus file is absent and could not be fetched."""


class InvalidCorpusLocksError(CorpusNotMaterializedError):
    """Lock files failed to parse, so no lock-based guarantee can be given."""


def _existing_ancestor(path: Path) -> Path:
    probe = path if path.is_absolute() else Path.cwd() / path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe


@functools.lru_cache(maxsize=256)
def _repo_root_for_dir(directory: Path) -> Path | None:
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    root = Path(top)
    # A sparse checkout may hold the lock files and data without src/.
    if (root / "src" / "axiom_corpus").is_dir() or (root / LOCK_ROOT).is_dir():
        return root
    return None


def find_repo_root(start: Path | None = None) -> Path | None:
    """The axiom-corpus checkout containing ``start`` (default: cwd), if any."""
    here = (start or Path.cwd()).resolve()
    return _repo_root_for_dir(here if here.is_dir() else here.parent)


def _is_symlinked_file(path: Path) -> bool:
    """A symlink that does not lead to a directory (a file, a cache object, nothing)."""
    return path.is_symlink() and not path.is_dir()


def _placed(path: Path) -> bool:
    """A regular file at ``path`` itself, as fetch places one.

    A symlink is never a placed corpus file, whatever it points to: fetch
    refuses to write through one and release code rejects one.
    """
    return path.is_file() and not path.is_symlink()


_CORPUS_ROOT = CORPUS_BASE.split("/")[0]
# How many places below links one selection may have before the helpers refuse
# it rather than check fewer (aliases of aliases multiply them).
_MAX_PARTS = 4096
# How many symlinks one resolution may pass through, as the operating system
# bounds it (ELOOP).
_MAX_LINKS = 40


def _guarded(name: str) -> bool:
    """True for a protected corpus path or a directory that holds protected paths.

    ``data``, ``data/corpus`` and ``data/corpus/<class>`` select locked files
    as surely as the paths below them do.
    """
    folded = fold_path(name).rstrip("/") + "/"
    return is_protected_corpus_path(folded) or any(
        prefix.startswith(folded) for prefix in PROTECTED_CORPUS_PREFIXES
    )


def _checkout_at(root: Path, home: Path | None) -> Path | None:
    """The checkout whose top level ``root`` is, in any spelling, or None.

    ``home`` (a resolver's own checkout) is matched by identity without a git
    process; any other directory asks git, once per directory.
    """
    real = os.path.realpath(root)
    try:
        root_stat = os.stat(real)
    except OSError:
        return None
    if not stat.S_ISDIR(root_stat.st_mode):
        return None
    if home is not None:
        with contextlib.suppress(OSError):
            if os.path.samestat(root_stat, os.stat(home)):
                return home
    top = _repo_root_for_dir(Path(real))
    if top is None:
        return None
    try:
        return top if os.path.samestat(os.stat(top), root_stat) else None
    except OSError:
        return None


def _protected_at(parts: Sequence[str], home: Path | None) -> tuple[Path, str] | None:
    """The checkout and guarded corpus path (``_guarded``) that the absolute path ``parts`` spells.

    A ``..`` is resolved lexically (callers check that the path reaches the
    same entry), and the innermost checkout wins.
    """
    folded = [fold_path(part) for part in parts]
    for index in range(len(parts) - 1, 0, -1):
        if folded[index] != _CORPUS_ROOT:
            continue
        name = posixpath.normpath("/".join(parts[index:]))
        if not _guarded(name):
            continue
        root = _checkout_at(Path(*parts[:index]), home)
        if root is not None:
            return root, name
    return None


def _same_place(first: Path, second: Path) -> bool:
    if os.path.realpath(first) == os.path.realpath(second):
        return True
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def _spells(probe: Path, name: str) -> bool:
    """True when ``probe`` ends in ``name``, exactly."""
    tail = tuple(name.split("/"))
    return probe.parts[-len(tail) :] == tail


def _spells_place(probe: Path, name: str) -> bool:
    """True when ``probe`` ends in ``name``, exactly or in another spelling that its
    filesystem stores in the same place (``stored_together``): on APFS
    ``.../DATA/corpus/provisions`` ends in ``data/corpus/provisions``."""
    if _spells(probe, name):
        return True
    tail = name.split("/")
    if len(probe.parts) <= len(tail):
        return False
    spelled = "/".join(probe.parts[-len(tail) :])
    if fold_path(spelled) != fold_path(name) and _caseless(spelled) != _caseless(name):
        return False  # no filesystem merges them: no lookups
    return stored_together(Path(*probe.parts[: -len(tail)]), spelled, name)


def _standing_places(
    probe: Path, physical: Path, home: Path | None, *, spellings: list[Path] | None = None
) -> tuple[list[tuple[Path, str]], bool]:
    """Each guarded place ``probe`` stands at below a symlink, in the order it resolves.

    The path is resolved as the operating system resolves it, links inside a
    link's target included. At each symlink the path stands at the link's own
    place plus the rest of the path. A ``..`` after the link is resolved from
    the link's target, so such a place counts only where it reaches the same
    entry. A symlinked file that stands at a guarded place ends the walk, and
    the second value is then True: it stands there and nowhere else. Any other
    symlinked file (a pointer such as ``latest.jsonl``) is followed like a
    directory link. ``spellings``, when supplied, keeps the complete path at
    each resolution step so witness collection can also check its enclosing
    checkouts without changing which checkout names the path.
    """
    places: list[tuple[Path, str]] = []
    for _link in range(_MAX_LINKS):
        if spellings is not None:
            spellings.append(probe)
        parts = probe.parts
        prefix = Path(parts[0])
        for index in range(1, len(parts)):
            prefix = prefix / parts[index]
            if prefix.is_symlink():
                break
        else:
            return places, False
        parent = Path(os.path.realpath(prefix.parent))
        rest = parts[index + 1 :]
        stands = _protected_at((*parent.parts, parts[index], *rest), home)
        if stands is not None and (".." not in rest or _same_place(stands[0] / stands[1], physical)):
            places.append(stands)
        if not rest and not prefix.is_dir() and places:
            return places, True
        try:
            target = os.readlink(prefix)
        except OSError:
            return places, False
        probe = Path(parent, target, *rest)
    return places, False


def _protected_name(probe: Path, physical: Path, home: Path | None = None) -> tuple[Path, str] | None:
    """The checkout and guarded corpus path that ``probe`` names, if it names one.

    ``probe`` is absolute and ``physical`` is its realpath. A symlink at or
    above a guarded path (``_guarded``) stands where locked files belong, so
    a path through one names, in order:

    1. a symlinked file that stands at a guarded place: that place, its own
       path. A symlinked file at no guarded place (a pointer) is followed
       like any other link;
    2. a path that reaches a guarded path whose name it spells exactly: that
       path, through any links. A worktree whose ``data/corpus/provisions``
       links to another checkout's names that checkout's files;
    3. otherwise the last guarded place it stands at below a link (one
       leading to another corpus path, outside every checkout, nowhere, an
       unprotected directory), so that place's lock applies; unless that
       place has the name of the guarded path it reaches, which it then names.

    A path that stands nowhere names the guarded path it reaches, if any.
    """
    file_link = _is_symlinked_file(probe)
    reached = None if file_link else _protected_at(physical.parts, home)
    if reached is not None and _spells_place(probe, reached[1]):
        return reached
    places, stands_as_file = _standing_places(probe, physical, home)
    if stands_as_file:
        return places[-1]
    if file_link:  # a pointer at no guarded place: named like the path it leads to
        reached = _protected_at(physical.parts, home)
    found = places[-1] if places else None
    if reached is not None and (found is None or found[1] == reached[1]):
        return reached
    return found


def _link_holder(probe: Path) -> Path | None:
    """The checkout in which ``probe`` is a symlinked file at a protected path, if any.

    A pointer at no protected path is none, even when what it leads to is.
    A link outside the protected paths (``/etc/localtime``) is settled
    without a git process.
    """
    if not _is_symlinked_file(probe):
        return None
    places, stands_as_file = _standing_places(probe, Path(os.path.realpath(probe)), None)
    return places[-1][0] if stands_as_file else None


def _checkout_for(path: Path, physical: Path | None = None) -> Path | None:
    """The checkout that names ``path`` (see ``CorpusResolver.relative``).

    The checkout whose protected path ``path`` names (``_protected_name``),
    else the one it resolves into, a dangling link's target included.
    ``physical`` is the path's realpath, when the caller has it.
    """
    probe = path if path.is_absolute() else Path.cwd() / path
    physical = physical or Path(os.path.realpath(probe))
    named = _protected_name(probe, physical)
    if named is not None:
        return named[0]
    return find_repo_root(_existing_ancestor(physical))


def _symlink_on_path(repo: Path, rel: str) -> Path | None:
    """The first component of ``rel`` below ``repo`` that is a symlink (fetch refuses them)."""
    lexical = repo
    for part in rel.split("/"):
        lexical = lexical / part
        if lexical.is_symlink():
            return lexical
    return None


def _link_note(repo: Path, rel: str) -> str:
    """Why fetching ``rel`` would fail, when a symlink stands on its path."""
    link = _symlink_on_path(repo, rel)
    if link is None:
        return ""
    return (
        f" {link} is a symlink; corpus files are placed as regular files, never through "
        "symlinks, so remove it first."
    )


def _symlinked_error(rel: str, target: Path) -> CorpusNotMaterializedError:
    try:
        leads_to = os.readlink(target)
    except OSError:  # removed or replaced meanwhile
        leads_to = "?"
    return CorpusNotMaterializedError(
        f"{rel} is a symlink in this checkout ({target} -> {leads_to}); "
        "corpus files are placed as regular files, never symlinks. Remove it and run "
        f"`axiom-corpus-ingest corpus fetch --path {rel}`."
    )


class CorpusResolver:
    """Materialize locked corpus files into one worktree on demand."""

    def __init__(
        self,
        repo: Path,
        *,
        cache: ContentCache | None = None,
        sources: Sequence[ObjectSource] | None = None,
        workers: int = 8,
    ):
        self.repo = repo.resolve()
        self.cache = cache or ContentCache()
        self._sources = list(sources) if sources is not None else None
        self.workers = workers
        self._locks: LockSet | None = None
        self._lock = threading.Lock()
        self._complete_source_scopes: set[ScopeKey] = set()

    @property
    def locks(self) -> LockSet:
        with self._lock:
            if self._locks is None:
                self._locks = load_locks(self.repo)
            return self._locks

    @property
    def active(self) -> bool:
        """True once any lock file exists, valid or not."""
        return bool(self.locks) or bool(self.locks.errors)

    def require_valid_locks(self) -> None:
        if self.locks.errors:
            raise InvalidCorpusLocksError(
                "corpus lock files are invalid, so this checkout cannot say which files "
                "it should hold: " + "; ".join(self.locks.errors[:5])
            )

    @property
    def sources(self) -> list[ObjectSource]:
        if self._sources is None:
            sources: list[ObjectSource] = [GitBlobSource(self.repo)]
            # Without R2 credentials the cache and local git objects still work.
            with contextlib.suppress(RuntimeError):
                sources.append(R2ObjectStore.from_environment(workers=self.workers))
            self._sources = sources
        return self._sources

    def entries_for_paths(self, paths: Iterable[str | Path]) -> list[LockEntry]:
        selected: dict[str, LockEntry] = {}
        for path in paths:
            rel = self.relative(path)
            if rel is None:
                continue
            for entry in self.locks.entries_under(self.locks.locked_spelling(self.repo, rel)):
                selected[entry.path] = entry
        return self.locks.with_whole_source_dirs(selected.values())

    def entries_for_scopes(self, scopes: Iterable[ScopeKey]) -> list[LockEntry]:
        entries: list[LockEntry] = []
        for lock in self.locks.select(scopes=scopes):
            entries.extend(lock.files)
        return entries

    def relative(self, path: str | Path) -> str | None:
        """Repository-relative posix path for ``path``, or None outside the repo.

        A relative ``data/corpus/...`` spelling is taken as repository-relative,
        as written unless it has a ``..`` component, which resolves through the
        checkout; any other relative path is relative to the working directory.
        Every spelling of the checkout gives the same answer: through a symlink,
        ``/tmp`` for ``/private/tmp``, a case variant or a firmlink.

        A symlink at or above a protected path of this checkout stands where
        locked files belong, so a path through it names that path
        (``_protected_name``): the callers must see that path's lock and
        refuse the link, rather than follow it to a cache object, another
        corpus path, or an empty directory and read an unfetched scope as
        empty. One link is followed: a directory link to the same path in
        another checkout, so a worktree whose ``data/corpus/provisions``
        links to another checkout's names that checkout's files, and this
        one names none of them.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            text = candidate.as_posix()
            if text == CORPUS_BASE or text.startswith(f"{CORPUS_BASE}/"):
                if ".." not in candidate.parts:
                    return text
                candidate = self.repo / candidate
            else:
                candidate = Path.cwd() / candidate
        return self._name(candidate, Path(os.path.realpath(candidate)))

    def _name(self, candidate: Path, physical: Path) -> str | None:
        """``relative`` for the absolute ``candidate``, whose realpath is ``physical``."""
        inside = self._inside(physical)
        if (
            inside is not None
            and _guarded(inside)
            and not _is_symlinked_file(candidate)
            and _spells(candidate, inside)
        ):
            return inside  # spells the guarded path it reaches here: no git process
        named = _protected_name(candidate, physical, self.repo)
        if named is None:
            return inside
        root, name = named
        return name if root == self.repo else None

    def _inside(self, physical: Path) -> str | None:
        """``physical`` (symlink-free above its last component) relative to the checkout."""
        text, top = str(physical), str(self.repo)
        if text.startswith(f"{top}/"):
            return text[len(top) + 1 :]  # Path.relative_to, without its cost
        if text == top:
            return "."
        # realpath keeps some spellings of one directory apart: a case variant
        # on a case-insensitive filesystem, a firmlink such as
        # /System/Volumes/Data/Users. Match the checkout by identity instead.
        try:
            root = os.lstat(self.repo)
        except OSError:
            return None
        for ancestor in (physical, *physical.parents):
            try:
                same = os.path.samestat(os.lstat(ancestor), root)
            except OSError:
                continue
            if same:
                return physical.relative_to(ancestor).as_posix()
        return None

    def ensure(self, entries: Sequence[LockEntry], *, verify: bool = False) -> FetchReport:
        """Fetch the entries this checkout lacks; raise if any cannot be placed.

        Only entries without a regular file at their own path go to fetch. A
        file in place is reported as fetch would report it (``present``, or
        ``modified`` when its size or, with ``verify``, its hash differs from
        the lock) and left alone. Fetch refuses every path through a symlink,
        so a file in place beneath a directory link would otherwise fail the
        call with nothing to write; an absent one there still fails. A
        symlink at the entry's own path is never in place.
        """
        self.require_valid_locks()
        if not entries:
            return FetchReport()
        pending = list(entries)
        # A concurrent fetch that fails rolls back the source files it placed,
        # which may be ones this call counted as present; check and retry once.
        for _attempt in range(2):
            in_place: dict[str, list[str]] = {"present": [], "modified": []}
            absent: list[LockEntry] = []
            for entry in pending:
                target = self.repo / entry.path
                try:
                    state = destination_state(target, entry, verify=verify)
                except OSError:  # unreadable (a link to a file on the path): fetch reports it
                    state = "missing"
                if state == "present" or (state == "modified" and _placed(target)):
                    in_place[state].append(entry.path)
                else:
                    absent.append(entry)
            report = (
                materialize(
                    self.repo,
                    absent,
                    self.cache,
                    self.sources,
                    verify=verify,
                    workers=self.workers,
                )
                if absent
                else FetchReport()
            )
            report.present[:0] = in_place["present"]
            report.modified[:0] = in_place["modified"]
            if report.failed:
                first, reason = next(iter(sorted(report.failed.items())))
                hint = (
                    "Corpus files are placed as regular files, never through symlinks: "
                    "remove the symlink and fetch again."
                    if _symlink_on_path(self.repo, first) is not None
                    else "Check R2 credentials (~/.config/axiom-foundation/r2-credentials.json) "
                    "or run `axiom-corpus-ingest corpus fetch` with network access."
                )
                raise CorpusNotMaterializedError(
                    f"{len(report.failed)} locked corpus file(s) could not be fetched; "
                    f"first: {first}: {reason}. {hint}"
                )
            pending = [entry for entry in entries if not (self.repo / entry.path).is_file()]
            if not pending:
                return report
        blocked = [entry.path for entry in pending if (self.repo / entry.path).is_dir()]
        if blocked:
            raise CorpusNotMaterializedError(
                f"{len(blocked)} locked corpus path(s) are directories in this checkout "
                f"(first: {blocked[0]}); remove them and fetch again."
            )
        raise CorpusNotMaterializedError(
            f"{len(pending)} locked corpus file(s) disappeared while being fetched "
            f"(first: {pending[0].path}); another process may be removing them."
        )

    def ensure_paths(self, paths: Iterable[str | Path], *, verify: bool = False) -> FetchReport:
        return self.ensure(self.entries_for_paths(paths), verify=verify)

    def ensure_scopes(self, scopes: Iterable[ScopeKey], *, verify: bool = False) -> FetchReport:
        return self.ensure(self.entries_for_scopes(scopes), verify=verify)

    def resolve(self, path: str | Path) -> Path:
        """A regular file for one corpus path, fetched if it is locked and absent.

        A source file comes with every locked source of its scope, even when it
        is itself already present: callers list the directory next. A spelling
        the filesystem stores where a locked file belongs (``DATA/corpus/...``
        on APFS) is that file, present or not.
        """
        rel = self.relative(path)
        if rel is None:
            raise ValueError(f"{path} is not inside {self.repo}")
        target = self.repo / rel
        present = _placed(target)
        if present and not fold_path(rel).startswith(f"{CORPUS_BASE}/sources/"):
            return target
        self.require_valid_locks()
        entry = self.locks.by_path.get(self.locks.locked_spelling(self.repo, rel))
        if entry is None:
            if present:
                return target
            if target.is_symlink():
                raise CorpusNotMaterializedError(
                    f"{rel} is a symlink, not a placed corpus file, and no lock names it."
                )
            raise CorpusNotMaterializedError(
                f"{rel} is neither present nor locked. Run `axiom-corpus-ingest corpus "
                "status` to see which scopes this checkout has."
            )
        if target.is_symlink():
            raise _symlinked_error(rel, target)
        scope = scope_for_path(entry.path)
        if present and scope in self._complete_source_scopes:
            return target
        missing = [
            item
            for item in self.locks.with_whole_source_dirs([entry])
            if not _placed(self.repo / item.path)
        ]
        if missing:
            if fetch_disabled():
                raise CorpusNotMaterializedError(
                    f"{len(missing)} locked corpus file(s) that {rel} needs are absent and "
                    f"fetching is off ({NO_FETCH_ENV}); first: {missing[0].path}"
                    + _link_note(self.repo, missing[0].path)
                )
            self.ensure(missing)
        if entry.path != rel and not _placed(target):
            # Taken for the locked file, the spelling must now reach it; a
            # filesystem that keeps the two apart makes it another, absent file.
            raise CorpusNotMaterializedError(
                f"{rel} is neither present nor locked; this filesystem keeps it apart "
                f"from the locked {entry.path}."
            )
        if scope is not None and entry.path.startswith(f"{CORPUS_BASE}/sources/"):
            self._complete_source_scopes.add(scope)
        return target


_RESOLVERS: dict[Path, CorpusResolver] = {}
_RESOLVERS_LOCK = threading.Lock()


def resolver_for(repo: Path | None = None) -> CorpusResolver | None:
    """Shared resolver for a checkout (default: the one containing cwd)."""
    root = repo.resolve() if repo is not None else find_repo_root()
    if root is None:
        return None
    with _RESOLVERS_LOCK:
        resolver = _RESOLVERS.get(root)
        if resolver is None:
            resolver = CorpusResolver(root)
            _RESOLVERS[root] = resolver
        return resolver


def fetch_disabled() -> bool:
    return os.environ.get(NO_FETCH_ENV, "").strip().lower() in {"1", "true", "yes"}


def _resolver(root: Path) -> CorpusResolver:
    resolver = resolver_for(root)
    assert resolver is not None  # an explicit root always has one
    return resolver


def _locked_name(resolver: CorpusResolver, name: str) -> str:
    """``name`` as ``resolver``'s locks spell the place its filesystem stores it in.

    ``DATA/corpus/SOURCES`` on APFS is ``data/corpus/sources``
    (``LockSet.locked_spelling``). Every view and part takes its name from
    here, so a lock lookup by that name, and the check of which checkout
    owns an entry, see the lock's own spelling.
    """
    if not resolver.active:
        return name
    return resolver.locks.locked_spelling(resolver.repo, name)


def _view(resolver: CorpusResolver, name: str, sub: str) -> _View:
    return _View(resolver, _locked_name(resolver, name), sub)


# --------------------------------------------------------------------------- selections
#
# A path through a symlink can lie under more than one lock: the lock of the
# checkout that names it (``relative``), and the lock of every other checkout
# where it stands at a protected place on the way, such as a worktree whose
# ``data/corpus/provisions`` links to another checkout's. Enclosing protected
# paths also apply when a checkout is nested in another's corpus tree. A directory also
# holds every symlink below it. So the helpers split each path they are given
# (a selection) into parts, one per checkout that names a subtree of it: that
# checkout's lock decides what is fetched there, and fetch writes into that
# checkout. Every other lock that applies witnesses: a file it names there
# must be in place once the parts' checkouts have placed theirs, or the
# helpers refuse, rather than read the file as absent.


@dataclasses.dataclass(frozen=True)
class _View:
    """``resolver``'s lock at ``name``, which a selection spells ``sub`` below itself."""

    resolver: CorpusResolver
    name: str
    sub: str


@dataclasses.dataclass(frozen=True)
class _Witnessed:
    """A file ``holder``'s lock names where ``owner`` names the path ``owner_name``."""

    holder: CorpusResolver
    entry: LockEntry
    owner: CorpusResolver
    owner_name: str


@dataclasses.dataclass
class _Plan:
    """The locked files some selections cover, by the checkout that fetches them.

    ``owned`` maps each checkout that names a part to the entries its lock
    names there; ``names`` keeps each part's name, for messages; ``tops``
    the part each selection itself is; ``witnessed`` holds, per file any
    other lock that applies names, each place a selection reads it from;
    ``spelled`` (when asked for) every path a selection spells for each entry;
    ``scope_dirs`` (when asked for) the spelled sources directory of each
    source entry's scope.
    """

    owned: dict[Path, tuple[CorpusResolver, dict[str, LockEntry]]] = dataclasses.field(default_factory=dict)
    names: dict[Path, dict[str, None]] = dataclasses.field(default_factory=dict)
    tops: list[_View] = dataclasses.field(default_factory=list)
    witnessed: dict[tuple[Path, str], list[_Witnessed]] = dataclasses.field(default_factory=dict)
    spelled: dict[tuple[Path, str], list[Path]] = dataclasses.field(default_factory=dict)
    scope_dirs: dict[tuple[Path, str], list[Path]] = dataclasses.field(default_factory=dict)


def _join(head: str, tail: str) -> str:
    return f"{head}/{tail}" if head and tail else head or tail


def _below(path: str, prefix: str) -> str | None:
    """``path`` relative to ``prefix`` ("" for the same path), or None outside it."""
    if not prefix or path == prefix:
        return path if not prefix else ""
    return path[len(prefix) + 1 :] if path.startswith(f"{prefix}/") else None


def _spelled(path: str | Path, repo: Path | None) -> Path:
    """``path`` made absolute. A bare ``data/corpus/...`` path lies in ``repo``
    (default: the working directory's checkout), as ``relative`` takes it."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    text = candidate.as_posix()
    if text == CORPUS_BASE or text.startswith(f"{CORPUS_BASE}/"):
        base = Path(os.path.realpath(repo)) if repo is not None else find_repo_root()
        if base is not None:
            return base / candidate
    return Path.cwd() / candidate


def _owner_of(
    spelled: Path, physical: Path, hint: CorpusResolver | None
) -> tuple[CorpusResolver, str] | None:
    """The checkout that names ``spelled`` (realpath ``physical``) and the name,
    as ``relative`` gives it.

    ``hint`` (a caller's ``repo``) is asked first: it names its own paths
    without git. A path it does not name goes to the checkout that does.
    """
    hint_name = None
    if hint is not None:
        hint_name = hint._name(spelled, physical)
        if hint_name is not None and not _nested_checkout(hint, physical):
            return hint, hint_name
    resolver = resolver_for(_checkout_for(spelled, physical))
    if resolver is None:
        return None
    if resolver is hint:  # set aside for a nested checkout that does not name it after all
        return (hint, hint_name) if hint_name is not None else None
    name = resolver._name(spelled, physical)
    return (resolver, name) if name is not None else None


def _directory_place(name: str) -> bool:
    """True for a guarded place above every path a lock can name, so only ever a
    directory: ``data``, ``data/corpus``, a class directory, and below it the
    jurisdiction and document-class directories (and, for sources, the version
    directory)."""
    parts = fold_path(name).strip("/").split("/")
    if parts == ["data"]:
        return True
    if parts[:2] != CORPUS_BASE.split("/"):
        return False
    rest = parts[2:]
    if not rest:
        return True
    if rest[0] not in PROTECTED_ARTIFACT_CLASSES:
        return False
    return len(rest) <= (4 if rest[0] == "sources" else 3)


def _part_owner(path: Path, found: tuple[CorpusResolver, str] | None) -> tuple[CorpusResolver, str] | None:
    """The checkout whose lock decides what is fetched below ``path``, and its name.

    That is the one that names ``path`` (``found``), save for a dangling link
    at a directory place to the same path in another checkout: a sharing link
    whose directory that checkout has not made yet. The link's own path names
    itself (a symlinked file, invariant 10), but every path below it is named
    in that checkout, so the files below are that checkout's.
    """
    if found is None or not _directory_place(found[1]) or not os.path.islink(path) or os.path.exists(path):
        return found
    reached = _protected_at(Path(os.path.realpath(path)).parts, None)
    # The same path in any spelling its checkout stores in one place: a link
    # named ``PROVISIONS`` on APFS is at ``provisions`` (``stored_together``).
    if reached is None or not (
        reached[1] == found[1] or stored_together(found[0].repo, found[1], reached[1])
    ):
        return found
    return _resolver(reached[0]), reached[1]


def _nested_checkout(resolver: CorpusResolver, physical: Path) -> bool:
    """True when a directory between ``resolver``'s checkout and ``physical``
    holds ``.git``: the path may lie in a checkout nested in its tree, which
    then names it (invariant 10), so ``resolver`` is not asked first. The
    checkout is matched as ``_inside`` matches it, in any spelling."""
    inside = resolver._inside(physical)
    if inside is None or inside == ".":
        return False
    steps = inside.split("/")
    probe = str(physical.parents[len(steps) - 1])  # the checkout, spelled as physical spells it
    for part in steps[:-1]:
        probe = f"{probe}/{part}"
        if _holds_git(probe):
            return True
    return False


@functools.lru_cache(maxsize=4096)
def _holds_git(directory: str) -> bool:
    """True when ``directory`` holds ``.git``; cached per directory, as checkout
    tops are (``_repo_root_for_dir``)."""
    return os.path.lexists(os.path.join(directory, ".git"))


def _places_above(spelled: Path, physical: Path) -> list[tuple[Path, str]]:
    """The protected places reached through links and enclosing a nested corpus.

    A nested checkout owns its corpus paths, but every enclosing checkout's
    protected-path lock still witnesses them, even without a symlink. Keep
    every full spelling along a sharing chain: its innermost protected place
    alone may already belong to a nested checkout and omit the sharing one.
    """
    places: list[tuple[Path, str]] = []
    spellings: list[Path] = []
    if str(physical) != os.path.normpath(spelled) or ".." in spelled.parts:
        places, _stands_as_file = _standing_places(spelled, physical, None, spellings=spellings)
        reached = _protected_at(physical.parts, None)
        if reached is not None:
            places.append(reached)
    for probe in [physical, *spellings, *(root / name for root, name in places)]:
        normalized = Path(os.path.normpath(probe))
        if ".." in probe.parts and not _same_place(normalized, physical):
            continue  # a link before .. makes this lexical spelling name another entry
        probe = normalized
        parts = probe.parts
        starts = [
            index
            for index in range(1, len(parts))
            if fold_path(parts[index]) == _CORPUS_ROOT and _guarded("/".join(parts[index:]))
        ]
        # The innermost possible corpus place is the owner's, already in the
        # selection. Ordinary paths have just that place and need no git call.
        for index in starts[:-1]:
            root = _checkout_at(Path(*parts[:index]), None)
            if root is not None:
                places.append((root, "/".join(parts[index:])))
    return list(dict.fromkeys(places))


def _links_below(top: Path, name: str) -> list[str]:
    """Where (relative to the directory ``top``, which ``name`` names) another
    checkout's lock may decide below it: a directory link or dangling link at a
    protected place, or the ``data`` directory of a checkout nested in the tree,
    whose corpus files that checkout names (invariant 10).

    Real directories are entered, links are not; a nested checkout's ``data``
    is reported, not entered. A link to a file is left out: it names its own
    place, which the lock of the directory holding it covers.
    """
    found: list[str] = []
    top_holds_checkout = _holds_checkout(top)
    if top_holds_checkout:
        found.append(_CORPUS_ROOT)  # the selection is itself a nested checkout
    stack = [(top, "", name, top_holds_checkout)]
    while stack:
        directory, sub, space, nested = stack.pop()
        all_guarded = is_protected_corpus_path(fold_path(space).rstrip("/") + "/")
        try:
            with os.scandir(directory) as listing:
                entries = list(listing)
        except OSError:
            continue
        for entry in entries:
            child = _join(space, entry.name)
            if not all_guarded and not _guarded(child):
                continue
            where = _join(sub, entry.name)
            try:
                if entry.is_symlink():
                    if entry.is_dir() or not os.path.exists(entry.path):
                        found.append(where)
                elif entry.is_dir(follow_symlinks=False):
                    if nested and entry.name == _CORPUS_ROOT:
                        continue  # the nested checkout's own corpus: reported below
                    holds_checkout = _holds_checkout(Path(entry.path))
                    if holds_checkout:
                        found.append(_join(where, _CORPUS_ROOT))  # made yet or not
                    stack.append((Path(entry.path), where, child, holds_checkout))
            except OSError:  # removed meanwhile
                continue
    return found


def _holds_checkout(directory: Path) -> bool:
    """True when ``directory`` is a checkout's top level (it holds ``.git``)."""
    return os.path.lexists(directory / ".git") and _checkout_at(directory, None) is not None


def _selection(
    spelled: Path, hint: CorpusResolver | None, *, walk: bool
) -> tuple[list[_View], list[_View], set[str]]:
    """The parts of the selection ``spelled`` and every lock view that applies to it.

    The first part is the selection itself, in the checkout that names it.
    With ``walk``, a directory adds a part for each directory link (or
    dangling link) at a protected place below it, the links below a linked
    directory's target included, and a part takes the checkout that names
    the paths below it (``_part_owner``). The third value holds the places
    where the walk stopped short (a cycle).
    """
    physical = Path(os.path.realpath(spelled))
    top = _owner_of(spelled, physical, hint)
    if walk:
        top = _part_owner(spelled, top)
    if top is None:
        return [], [], set()
    top = (top[0], _locked_name(top[0], top[1]))
    parts = [_View(top[0], top[1], "")]
    views = [*parts, *(_view(_resolver(root), name, "") for root, name in _places_above(spelled, physical))]
    if not walk or top[1] in top[0].locks.by_path or not _guarded(top[1]):
        return parts, views, set()  # a locked name is a file: nothing lies below it
    # A directory is listed once per listing class of the name it is walked
    # under (``_listing_class``: which names below it are protected), and
    # walked under every spelling that reaches it, so each alias keeps its
    # parts. A link back to a directory already walked, under the same
    # listing class, on the same spelled path is a cycle and is not followed:
    # every link below it was found the first time. Its place is "cut": a
    # locked file whose own name runs through it is classified by its own
    # path (``_plan``). So is one below a chain longer than the operating
    # system resolves, and too many spellings refuse loudly.
    pending: list[tuple[Path, str, str, int, frozenset[tuple[int, int, str]]]] = [
        (physical, "", top[1], 0, frozenset())
    ]
    seen: set[tuple[int, int, str]] = set()
    listed: dict[tuple[int, int, str], list[str]] = {}
    cut: set[str] = set()
    while pending:
        directory, sub, name, hops, trail = pending.pop()
        try:
            info = os.stat(directory)
        except OSError:
            continue
        key = (info.st_dev, info.st_ino, _listing_class(name))
        if not stat.S_ISDIR(info.st_mode) or (*key[:2], sub) in seen:
            continue
        if key in trail or hops > _MAX_LINKS:
            cut.add(sub)  # a cycle (or too long a chain): files below are classified one by one
            continue
        seen.add((*key[:2], sub))
        if key not in listed:
            listed[key] = _links_below(directory, name)
        for below in listed[key]:
            where = _join(sub, below)
            link = spelled / where
            link_physical = Path(os.path.realpath(link))
            found = _part_owner(link, _owner_of(link, link_physical, hint))
            if found is None:
                continue
            found = (found[0], _locked_name(found[0], found[1]))
            parts.append(_View(found[0], found[1], where))
            if len(parts) > _MAX_PARTS:
                raise CorpusNotMaterializedError(
                    f"more than {_MAX_PARTS} symlinked places below {spelled}: its links spell too many "
                    "paths to check every lock that applies. Replace some of them with directories."
                )
            views.append(parts[-1])
            views.extend(_view(_resolver(root), place, where) for root, place in _places_above(link, link_physical))
            pending.append((link_physical, where, found[1], hops + 1, trail | {key}))
    return parts, views, cut


def _listing_class(name: str) -> str:
    """What decides which names below ``name`` a walk keeps (``_links_below``):
    "" at or below a class directory, where every name is protected, else the
    name itself (``data``, ``data/corpus``), above which fewer are."""
    folded = fold_path(name).rstrip("/")
    return "" if is_protected_corpus_path(f"{folded}/") else folded


def _covers(outer: _View, inner: _View) -> bool:
    """True when ``outer`` lists every entry ``inner`` does, at the same places."""
    if outer.resolver is not inner.resolver:
        return False
    rest = _below(inner.name, outer.name)
    return rest is not None and inner.sub == _join(outer.sub, rest)


def _plan(
    paths: Iterable[str | Path],
    *,
    repo: Path | None,
    exact: bool = False,
    spell: bool = False,
    widen: bool = False,
) -> _Plan:
    """The locked files ``paths`` select, split by the checkout that fetches them.

    With ``exact``, each path selects only a file of its own name (no
    directory below it, no link below it). With ``spell``, ``spelled`` is
    filled in; with ``widen``, ``scope_dirs``.
    """
    hint = resolver_for(repo) if repo is not None else None
    plan = _Plan()
    for path in paths:
        selection = _spelled(path, repo)
        parts, views, cut = _selection(selection, hint, walk=not exact)
        if not parts:
            fallback = hint or resolver_for(None)
            if fallback is not None and fallback.active:
                fallback.require_valid_locks()  # an invalid lock never reads as "no locks"
            continue
        plan.tops.append(parts[0])
        for part in parts:
            plan.names.setdefault(part.resolver.repo, {})[part.name] = None
        deepest = sorted(parts, key=lambda part: len(part.sub), reverse=True)
        distinct: list[_View] = []
        for view in sorted(views, key=lambda view: (str(view.resolver.repo), len(view.name))):
            if not any(_covers(kept, view) for kept in distinct):
                distinct.append(view)
        for view in distinct:
            resolver = view.resolver
            if not resolver.active:
                continue
            resolver.require_valid_locks()
            # ``view.name`` is already the lock's own spelling (``_locked_name``).
            if exact:
                exact_entry = resolver.locks.by_path.get(view.name)
                entries = [exact_entry] if exact_entry is not None else []
            else:
                entries = resolver.locks.entries_under(view.name)
            for entry in entries:
                where = _join(view.sub, _below(entry.path, view.name) or "")
                part, rest = deepest[-1], where  # the selection itself, below no link
                for candidate in deepest[:-1]:
                    below = _below(where, candidate.sub)
                    if below is not None:
                        part, rest = candidate, below
                        break
                owner, owner_name = part.resolver, _join(part.name, rest)
                if owner is not resolver:  # another lock may spell the rest otherwise
                    owner_name = _locked_name(owner, owner_name)
                if rest and part.sub in cut:
                    # Below a place the walk stopped at (a cycle): the file's
                    # own path decides who names it, and that checkout fetches
                    # it there when its lock lists it.
                    here = selection / where
                    named = _owner_of(here, Path(os.path.realpath(here)), hint)
                    if named is not None:
                        owner, owner_name = named[0], _locked_name(*named)
                        listed_there = owner.locks.by_path.get(owner_name) if owner.active else None
                        if listed_there is not None:
                            owner.require_valid_locks()
                            plan.owned.setdefault(owner.repo, (owner, {}))[1][owner_name] = listed_there
                            plan.names.setdefault(owner.repo, {})[owner_name] = None
                if spell:
                    spots = plan.spelled.setdefault((resolver.repo, entry.path), [])
                    here = selection / where if where else selection
                    if here not in spots:
                        spots.append(here)
                if widen and entry.path.startswith(f"{CORPUS_BASE}/sources/"):
                    scope_dir = _spelled_scope_dir(selection, where, entry.path)
                    if scope_dir is not None:
                        dirs = plan.scope_dirs.setdefault((resolver.repo, entry.path), [])
                        if scope_dir not in dirs:
                            dirs.append(scope_dir)
                if resolver is owner and entry.path == owner_name:
                    plan.owned.setdefault(resolver.repo, (resolver, {}))[1][entry.path] = entry
                else:
                    item = _Witnessed(resolver, entry, owner, owner_name)
                    places = plan.witnessed.setdefault((resolver.repo, entry.path), [])
                    if item not in places:
                        places.append(item)
    return plan


def _owns(plan: _Plan, resolver: CorpusResolver, name: str) -> bool:
    return name in plan.owned.get(resolver.repo, (resolver, {}))[1]


def _absent_owned(plan: _Plan) -> list[tuple[CorpusResolver, list[LockEntry]]]:
    """Per checkout, the entries it names in a part that are not in place."""
    found = []
    for resolver, entries in plan.owned.values():
        absent = [entry for entry in entries.values() if not _placed(resolver.repo / entry.path)]
        if absent:
            found.append((resolver, absent))
    return found


def _covered(plan: _Plan, places: Sequence[_Witnessed]) -> list[tuple[Path, str]]:
    """The owned entries that are the witnessed file of ``places``: its own
    checkout's, where that checkout names it in a part, and that of each owner
    whose lock lists a place it is read from. Each reaches the same directory
    entry as the witnessed file (invariant 10), so its fetch places that file."""
    first = places[0]
    found = [(first.holder.repo, first.entry.path)] if _owns(plan, first.holder, first.entry.path) else []
    found.extend((item.owner.repo, item.owner_name) for item in places if _owns(plan, item.owner, item.owner_name))
    return found


def _unfetchable(plan: _Plan, *, recheck: bool = False) -> list[_Witnessed]:
    """Witnessed files that are not in place and that no part's checkout fetches.

    A covered file (``_covered``) is left to the owned entry that covers it,
    without a ``stat`` of its own. With ``recheck``, every witnessed file that
    is not in place counts.
    """
    found = []
    for places in plan.witnessed.values():
        if not recheck and _covered(plan, places):
            continue
        first = places[0]
        if not _placed(first.holder.repo / first.entry.path):
            found.append(first)
    return found


def _unfetchable_error(items: Sequence[_Witnessed]) -> CorpusNotMaterializedError:
    first = items[0]
    rel = first.entry.path
    link = _symlink_on_path(first.holder.repo, rel)
    if link is None:
        through, remedy = "", f"run `axiom-corpus-ingest corpus fetch --path {rel}` in {first.holder.repo}"
    else:
        try:
            through = f"; it reads through the symlink {link} -> {os.readlink(link)}"
        except OSError:  # removed or replaced meanwhile
            through = f"; it reads through the symlink {link}"
        remedy = (
            f"replace that symlink with a directory and run `axiom-corpus-ingest corpus fetch "
            f"--path {rel}` in {first.holder.repo}"
        )
    if _owns_name(first.owner, first.owner_name):
        why = f"{first.owner.repo} names that path and its lock lists it, but it is still absent"
    else:
        why = (
            f"{first.owner.repo} names that path, and its lock, which decides what is fetched "
            f"there, does not list {first.owner_name}"
        )
    return CorpusNotMaterializedError(
        f"{len(items)} locked corpus file(s) are absent and no fetch will place them (first: "
        f"{rel}, which the lock of {first.holder.repo} names{through}). {why}. Lock that scope "
        f"in {first.owner.repo} and fetch it there, or {remedy}."
    )


def _owns_name(resolver: CorpusResolver, name: str) -> bool:
    return resolver.active and not resolver.locks.errors and name in resolver.locks.by_path


def _fetch_command(resolver: CorpusResolver, rels: Sequence[str]) -> str:
    command = (
        " ".join(f"--path {rel}" for rel in rels)
        if len(rels) <= 3
        else "--paths-from <file listing them>"
    )
    here = find_repo_root()
    where = "" if here is not None and here == resolver.repo else f" in {resolver.repo}"
    return f"`axiom-corpus-ingest corpus fetch {command}`{where}"


def _whole_sources(
    plan: _Plan,
    batches: Sequence[tuple[CorpusResolver, list[LockEntry]]],
    *,
    only_absent: bool,
) -> list[tuple[CorpusResolver, list[LockEntry]]]:
    """``batches`` with the sources directory of each source entry's scope made
    whole, across every checkout that names files there. The entries are those
    of the batches and every witnessed source (absent ones, with
    ``only_absent``).

    The directory is planned as a selection, spelled through the original
    one (``scope_dirs``), so a link inside it sends its files to the checkout
    it leads to, and every lock that applies there counts (invariant 11).
    With ``only_absent``, entries already in place are not added. The plan
    gains the directory's entries, for the check after fetching.
    """
    dirs: dict[str, Path] = {}
    for resolver, entries in batches:
        for entry in entries:
            for directory in plan.scope_dirs.get((resolver.repo, entry.path), ()):
                dirs.setdefault(str(directory), directory)
    # A source only another lock names (a witness) needs its whole directory too.
    for key, places in plan.witnessed.items():
        first = places[0]
        if only_absent and _placed(first.holder.repo / first.entry.path):
            continue
        for directory in plan.scope_dirs.get(key, ()):
            dirs.setdefault(str(directory), directory)
    merged = {resolver.repo: (resolver, {entry.path: entry for entry in entries}) for resolver, entries in batches}
    if dirs:
        whole = _plan(list(dirs.values()), repo=None)
        unfetchable = _unfetchable(whole)
        if unfetchable:
            raise _unfetchable_error(unfetchable)
        for owner, owned in whole.owned.values():
            plan.owned.setdefault(owner.repo, (owner, {}))[1].update(owned)
            for entry in owned.values():
                if not (only_absent and _placed(owner.repo / entry.path)):
                    merged.setdefault(owner.repo, (owner, {}))[1].setdefault(entry.path, entry)
        for key, places in whole.witnessed.items():
            plan.witnessed.setdefault(key, []).extend(item for item in places if item not in plan.witnessed.get(key, []))
    return [(resolver, [chosen[path] for path in sorted(chosen)]) for resolver, chosen in merged.values()]


def _place_owned(plan: _Plan, batches: Sequence[tuple[CorpusResolver, list[LockEntry]]]) -> list[FetchReport]:
    """Fetch each checkout's entries into it, then check that every witnessed file
    a fetched entry covers is in place.

    Callers first refuse what no fetch places (``_unfetchable``); a covered file
    whose owned entry was already in place is that same file, so it is in place.
    """
    reports = []
    fetched: set[tuple[Path, str]] = set()
    for resolver, entries in batches:
        report = resolver.ensure(entries)
        reports.append(report)
        fetched.update((resolver.repo, path) for path in report.materialized)
    unplaced = [
        places[0]
        for places in plan.witnessed.values()
        if fetched.intersection(_covered(plan, places))
        and not _placed(places[0].holder.repo / places[0].entry.path)
    ]
    if unplaced:
        raise _unfetchable_error(unplaced)
    return reports


def _merged(reports: Iterable[FetchReport]) -> FetchReport:
    total = FetchReport()
    for report in reports:
        total.present.extend(report.present)
        total.materialized.extend(report.materialized)
        total.modified.extend(report.modified)
        total.failed.update(report.failed)
        total.rolled_back.extend(report.rolled_back)
        for name, count in report.sources.items():
            total.sources[name] = total.sources.get(name, 0) + count
        for name, count in report.methods.items():
            total.methods[name] = total.methods.get(name, 0) + count
        total.bytes_materialized += report.bytes_materialized
    return total


def locked_entries_under(paths: Iterable[str | Path], *, repo: Path | None = None) -> list[tuple[Path, LockEntry]]:
    """Each locked file at or below each path, under every lock that applies.

    Pairs each path a selection spells for the file with its lock entry: that
    of the checkout that names it where one does, else that of another lock
    that applies (invariant 11). ``repo`` is taken as ``ensure_corpus_paths``
    takes it.
    """
    plan = _plan(list(paths), repo=repo, spell=True)
    found: dict[Path, LockEntry] = {}
    for resolver, entries in plan.owned.values():
        for entry in entries.values():
            for here in plan.spelled[(resolver.repo, entry.path)]:
                found.setdefault(here, entry)
    for places in plan.witnessed.values():
        first = places[0]
        for here in plan.spelled[(first.holder.repo, first.entry.path)]:
            found.setdefault(here, first.entry)
    return sorted(found.items())


def ensure_corpus_paths(paths: Iterable[str | Path], *, repo: Path | None = None) -> FetchReport:
    """Materialize the locked files at or under each path. No-op without locks.

    Each part of a path is fetched into the checkout that names it, by that
    checkout's lock, and a file any other lock that applies names must then be
    in place, or this raises (see the selections above). ``repo`` is where
    bare ``data/corpus/...`` paths lie and is asked first; a path it does not
    name goes to the checkout that does. With fetching disabled, locked files
    that are absent raise instead.
    """
    plan = _plan(list(paths), repo=repo, widen=not fetch_disabled())
    if fetch_disabled():
        _require(plan, fetch=False)
        return FetchReport()
    unfetchable = _unfetchable(plan)
    if unfetchable:
        raise _unfetchable_error(unfetchable)
    selected = _whole_sources(
        plan, [(resolver, list(entries.values())) for resolver, entries in plan.owned.values()], only_absent=False
    )
    return _merged(_place_owned(plan, selected))


def ensure_corpus_scopes(scopes: Iterable[ScopeKey], *, repo: Path | None = None) -> FetchReport:
    """Materialize whole scopes. No-op without locks.

    A scope is its four paths in ``repo`` (default: the working directory's
    checkout), taken as ``ensure_corpus_paths`` takes paths. With fetching
    disabled, locked files that are absent raise instead.
    """
    scope_list = list(scopes)
    resolver = resolver_for(repo)
    if resolver is None:
        return FetchReport()
    if resolver.active:
        resolver.require_valid_locks()
    # A checkout without locks of its own may still link to one with them.
    plan = _plan(_scope_paths(resolver.repo, scope_list), repo=resolver.repo)
    unfetchable = _unfetchable(plan)
    if unfetchable:
        raise _unfetchable_error(unfetchable)
    if fetch_disabled():
        absent = _absent_owned(plan)
        if absent:
            holder, entries = absent[0]
            count = sum(len(found) for _resolver_, found in absent)
            raise CorpusNotMaterializedError(
                f"{count} locked corpus file(s) are absent and fetching is off "
                f"({NO_FETCH_ENV}); first: {entries[0].path}" + _link_note(holder.repo, entries[0].path)
            )
        return FetchReport()
    return _merged(_place_owned(plan, [(owner, list(entries.values())) for owner, entries in plan.owned.values()]))


def _scope_paths(repo: Path, scopes: Iterable[ScopeKey]) -> list[Path]:
    """The paths that hold each scope's files in ``repo``: its sources directory
    and its inventory, provisions and coverage files."""
    paths: list[Path] = []
    for jurisdiction, document_class, version in scopes:
        base = repo / CORPUS_BASE
        paths.append(base / "sources" / jurisdiction / document_class / version)
        paths.extend(
            base / artifact_class / jurisdiction / document_class / f"{version}{suffix}"
            for artifact_class, suffix in SINGLE_FILE_SUFFIXES.items()
        )
    return paths


def require_materialized(
    paths: Iterable[str | Path],
    *,
    repo: Path | None = None,
    fetch: bool = False,
) -> None:
    """Refuse to walk a corpus directory that holds only part of its locked files.

    Code that lists ``data/corpus`` directories would otherwise compute on
    whatever subset happens to be fetched. With ``fetch`` the missing files
    are fetched instead, each into the checkout that names it. Every lock
    that applies to a path counts (see the selections above), and ``repo``
    is taken as ``ensure_corpus_paths`` takes it. No-op without lock files.
    """
    _require(_plan(list(paths), repo=repo, widen=fetch and not fetch_disabled()), fetch=fetch)


def _require(plan: _Plan, *, fetch: bool) -> None:
    unfetchable = _unfetchable(plan)
    if unfetchable:
        raise _unfetchable_error(unfetchable)
    absent = _absent_owned(plan)
    if not absent:
        return
    if fetch and not fetch_disabled():
        _place_owned(plan, _whole_sources(plan, absent, only_absent=True))
        return
    resolver, missing = absent[0]
    rels = list(plan.names.get(resolver.repo, {})) or [missing[0].path]
    # Name at most a few paths: callers may pass thousands of exact files.
    named = rels if len(rels) <= 3 else [*rels[:3], f"and {len(rels) - 3} more"]
    raise CorpusNotMaterializedError(
        f"{len(missing)} locked corpus file(s) under {', '.join(named)} are not in this "
        f"checkout (first: {missing[0].path}); results would cover only part of the "
        f"corpus. Run {_fetch_command(resolver, rels)} first."
        + _link_note(resolver.repo, missing[0].path)
    )


def fetch_locked_file(path: str | Path) -> bool:
    """Fetch ``path`` if a lock in its checkout names it; True when it is now in place.

    A lock names ``path`` when it names the place the filesystem stores
    ``path`` in: on a case-insensitive filesystem ``DATA/corpus/...`` is
    ``data/corpus/...``, fetched or not. Returns False (and does nothing) for
    paths no lock names, outside any checkout, or with fetching disabled.
    Raises ``CorpusNotMaterializedError``
    when a locked file cannot be fetched, when a symlink stands where it
    belongs, or when another applicable lock (through a symlink or enclosing a
    nested checkout) names it and no fetch will place it: silently
    reading nothing, or bytes no lock checked, would be worse.
    """
    candidate = Path(path)
    anchor = candidate if candidate.is_absolute() else Path.cwd() / candidate
    # A present path is read as it is, save a symlinked file at a protected
    # path, which stands where a locked file belongs.
    if candidate.exists() and _link_holder(anchor) is None:
        return True
    plan = _plan([anchor], repo=None, exact=True, widen=not fetch_disabled())
    unfetchable = _unfetchable(plan)
    if unfetchable:
        raise _unfetchable_error(unfetchable)
    if not plan.tops:
        return False
    resolver, rel = plan.tops[0].resolver, plan.tops[0].name
    if not _owns(plan, resolver, rel):
        return False
    if (resolver.repo / rel).is_symlink():
        raise _symlinked_error(rel, resolver.repo / rel)
    if fetch_disabled():
        raise CorpusNotMaterializedError(
            f"{rel} is locked but absent, and fetching is off ({NO_FETCH_ENV}); reading it "
            "as empty would be wrong. Fetch it first." + _link_note(resolver.repo, rel)
        )
    _place_owned(plan, _whole_sources(plan, [(resolver, [resolver.locks.by_path[rel]])], only_absent=True))
    # A spelling taken for the locked file (``DATA/corpus/...`` on APFS) must
    # now reach it; on a filesystem misjudged as merging the two, it does not.
    return anchor.exists()


def resolve_corpus_path(path: str | Path, *, repo: Path | None = None) -> Path:
    """Return a regular file for ``path``, fetching it if it is locked and absent.

    The checkout that names the path fetches it; a bare ``data/corpus/...``
    path lies in ``repo``. Another lock that applies (see the selections
    above) that names the file, or for a source file a sibling, refuses the
    read when no fetch will place it.
    """
    candidate = Path(path)
    text = candidate.as_posix()
    bare = not candidate.is_absolute() and (text == CORPUS_BASE or text.startswith(f"{CORPUS_BASE}/"))
    probe = _spelled(candidate, repo) if bare and repo is not None else candidate
    absolute = os.path.abspath(probe)
    if (
        probe.is_file()
        and not probe.is_symlink()
        # Spelled through no symlink, so it stands nowhere but where it is,
        # and no source file, so there are no siblings to bring.
        and os.path.realpath(probe) == absolute
        and f"/{CORPUS_BASE}/sources/" not in fold_path(absolute)
    ):
        return probe  # nothing to widen, no git call
    # A bare data/corpus path lies in ``repo``; the checkout that names the
    # path, which ``repo`` may not be (a link to another checkout), decides.
    spelled = _spelled(candidate, repo)
    physical = Path(os.path.realpath(spelled))
    owner = _owner_of(spelled, physical, resolver_for(repo) if repo is not None else None)
    resolver: CorpusResolver | None
    rel: str | None
    if owner is not None:
        resolver, rel = owner
    else:
        resolver, rel = resolver_for(_checkout_for(spelled, physical)), None
    witnesses = _read_witnesses(spelled, physical, resolver, rel)
    if resolver is None or not resolver.active or rel is None:
        found = probe if probe.is_file() and not probe.is_symlink() else None
    else:
        found = resolver.resolve(spelled)
    if witnesses is not None:
        unplaced = _unfetchable(witnesses[0], recheck=True)
        if unplaced:
            raise _unfetchable_error(unplaced)
        if witnesses[1] is not None:
            _WITNESSED_SOURCE_DIRS.add(witnesses[1])
    if found is None:
        raise CorpusNotMaterializedError(f"{path} does not exist")
    return found


# Spelled sources directories whose every applicable lock was found satisfied
# once; like ``CorpusResolver._complete_source_scopes``, checked once per process.
_WITNESSED_SOURCE_DIRS: set[str] = set()


def _read_witnesses(
    anchor: Path, physical: Path, resolver: CorpusResolver | None, rel: str | None
) -> tuple[_Plan, str | None] | None:
    """Refuse a read of the absolute ``anchor`` (realpath ``physical``, ``rel`` in
    ``resolver``'s checkout) that a lock that applies says no fetch completes.

    A source file counts with its scope's whole sources directory, as
    ``CorpusResolver.resolve`` fetches it. Returns the plan, and the directory
    to remember once the read succeeds, for a check after the read; None
    when there is nothing to check.
    """
    if resolver is None or rel is None:
        return None  # no checkout names it, so it stands at no protected place
    selection, exact, remember = anchor, True, None
    depth = len(rel.split("/")) - 6  # below data/corpus/sources/<j>/<dc>/<v>
    # Folded, so a scope spelled in another case (``.../NZ/...``) is still a
    # scope: its directory is planned below, under every lock that applies.
    folded = fold_path(rel)
    if scope_for_path(folded) is not None and folded.startswith(f"{CORPUS_BASE}/sources/") and depth >= 1:
        selection, exact = _scope_directory(anchor, rel, depth), False
        remember = str(selection)
        if remember in _WITNESSED_SOURCE_DIRS:
            return None
    if exact and str(physical) == os.path.normpath(anchor) and not _places_above(anchor, physical):
        return None  # no symlink or enclosing protected place: only its own lock applies
    plan = _plan([selection], repo=resolver.repo, exact=exact)
    unfetchable = _unfetchable(plan)
    if unfetchable:
        raise _unfetchable_error(unfetchable)
    # Files another checkout names there (through a link inside the scope's
    # directory) are that checkout's to fetch, as ``resolve`` fetches its own.
    others = [(owner, found) for owner, found in _absent_owned(plan) if owner is not resolver]
    if others:
        if fetch_disabled():
            owner, found = others[0]
            raise CorpusNotMaterializedError(
                f"{sum(len(items) for _owner, items in others)} locked corpus file(s) that {rel} "
                f"needs are absent and fetching is off ({NO_FETCH_ENV}); first: {found[0].path}"
                + _link_note(owner.repo, found[0].path)
            )
        _place_owned(plan, others)
    if plan.witnessed:
        return plan, remember
    if remember is not None:
        _WITNESSED_SOURCE_DIRS.add(remember)  # no other lock applies: nothing to recheck
    return None


def _spelled_scope_dir(selection: Path, where: str, rel: str) -> Path | None:
    """The sources directory of the scope of ``rel`` (a source file a selection
    spells ``where`` below itself), spelled through the selection, or None
    for a path not below a scope's sources directory."""
    depth = len(rel.split("/")) - 6  # below data/corpus/sources/<j>/<dc>/<v>
    if depth < 1 or scope_for_path(rel) is None:
        return None
    steps = where.split("/") if where else []
    if len(steps) >= depth:  # the directory lies within the selection
        return selection.joinpath(*steps[: len(steps) - depth])
    return _scope_directory(selection.joinpath(*steps), rel, depth)


def _scope_directory(anchor: Path, rel: str, depth: int) -> Path:
    """The scope's sources directory, ``depth`` levels above the file ``anchor``
    (named ``rel``), spelled through the same links.

    A path that spells its name climbs lexically. Any other (a ``..``, a
    pointer, a link that renames a directory) climbs with ``..`` from the
    directory the operating system finds the file in, a pointer resolved.
    """
    if ".." not in anchor.parts and _spells(anchor, rel) and (
        not os.path.islink(anchor) or _link_holder(anchor) is not None
    ):
        return anchor.parents[depth - 1]
    leaf = anchor
    for _hop in range(_MAX_LINKS):
        if not os.path.islink(leaf):
            break
        leaf = leaf.parent / os.readlink(leaf)
    return Path(leaf.parent, *[".."] * (depth - 1))


# --------------------------------------------------------------------------- CLI hook

_SCOPE_ARG_NAMES = ("jurisdiction", "document_class", "version")
# Argument names that never name corpus inputs: the dispatch marker, and the
# free-text command that sign-ingest-manifest records in the manifest.
_NON_INPUT_ARGS = frozenset({"func", "command", "_cli_command"})


def cli_repo(args: Any) -> Path | None:
    """The checkout a CLI invocation works on: the one holding ``--base``, else cwd's.

    ``--base`` is taken as spelled: through a symlink, the checkout of the
    first protected place it stands at (``_standing_places``), so a
    ``data/corpus`` that links elsewhere belongs to the checkout holding the
    link, whose lock still applies there (invariant 11). Otherwise the
    checkout that names it (``_checkout_for``).
    """
    base = getattr(args, "base", None)
    if isinstance(base, str | Path) and str(base):
        spelled = Path(base) if Path(base).is_absolute() else Path.cwd() / Path(base)
        physical = Path(os.path.realpath(spelled))
        places, _stands_as_file = _standing_places(spelled, physical, None)
        if places:
            return places[0][0]
        found = _checkout_for(spelled, physical)
        if found is not None:
            return found
    return find_repo_root()


def _is_corpus_base(repo: Path, base: object) -> bool:
    if not isinstance(base, str | Path) or not str(base):
        return False
    candidate = Path(base) if Path(base).is_absolute() else Path.cwd() / Path(base)
    if Path(os.path.realpath(candidate)) == (repo / CORPUS_BASE).resolve():
        return True
    # Another spelling of it: through a firmlink, or a case variant on APFS
    # (fetched or not).
    rel = CorpusResolver(repo, sources=[]).relative(candidate)
    return (
        rel is not None
        and fold_path(rel) == CORPUS_BASE
        and stored_together(repo, rel, CORPUS_BASE)
    )


def corpus_inputs_from_args(
    args: Any,
    *,
    repo: Path,
) -> tuple[list[str], list[ScopeKey], list[Path]]:
    """Corpus paths (repository-relative), scopes and release selectors in CLI arguments."""
    resolver = CorpusResolver(repo, sources=[])
    paths: list[str] = []
    selectors: list[Path] = []
    for name, value in sorted(vars(args).items()):
        if name in _NON_INPUT_ARGS:
            continue
        values = value if isinstance(value, list | tuple) else [value]
        for item in values:
            if not isinstance(item, Path | str) or not str(item):
                continue
            if name in {"release", "selector"}:
                selectors.append(Path(item))
                continue
            candidate = Path(item)
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            rel = resolver.relative(candidate)
            if rel is None:  # another checkout names it: its path here, through a link
                rel = _name_here(resolver, candidate)
            # A path under a protected prefix, in any spelling (the locks
            # decide which spellings name locked files), names files to read;
            # the bare base (``--base data/corpus``) names nothing by itself.
            if rel is not None and is_protected_corpus_path(fold_path(rel).rstrip("/") + "/"):
                paths.append(rel.rstrip("/"))
    scopes: list[ScopeKey] = []
    if _is_corpus_base(repo, getattr(args, "base", None)):
        values = [getattr(args, name, None) for name in _SCOPE_ARG_NAMES]
        if all(isinstance(v, str) and v for v in values):
            scopes.append((str(values[0]), str(values[1]), str(values[2])))
    return paths, scopes, selectors


def _name_here(resolver: CorpusResolver, candidate: Path) -> str | None:
    """The protected path of ``resolver``'s checkout that ``candidate`` stands at
    below a symlink, when another checkout names ``candidate`` (a link to the
    same path there), else None."""
    places, _stands_as_file = _standing_places(candidate, Path(os.path.realpath(candidate)), resolver.repo)
    return next((name for root, name in places if root == resolver.repo), None)


def materialize_cli_inputs(
    args: Any,
    *,
    repo: Path | None = None,
    include_scope: bool = False,
) -> FetchReport | None:
    """Fetch the locked files a CLI invocation names as inputs, before it runs.

    Paths under the protected prefixes and release selectors always count as
    inputs. A ``--jurisdiction/--document-class/--version`` triple counts only
    when ``include_scope`` is set: for extractors it names the output.
    """
    resolver = resolver_for(repo or cli_repo(args))
    if resolver is None:
        return None
    if resolver.active:
        resolver.require_valid_locks()
    # A checkout without locks of its own may still link to one with them.
    paths, scopes, selectors = corpus_inputs_from_args(args, repo=resolver.repo)
    if not include_scope:
        scopes = []
    for selector in selectors:
        scopes.extend(_selector_scopes(resolver.repo, selector))
    if not paths and not scopes:
        return None
    plan = _plan(
        [resolver.repo / path for path in paths] + _scope_paths(resolver.repo, scopes),
        repo=resolver.repo,
        widen=True,
    )
    unfetchable = _unfetchable(plan)
    if unfetchable:
        raise _unfetchable_error(unfetchable)
    missing = [
        (owner, found)
        for owner, entries in _whole_sources(
            plan, [(owner, list(entries.values())) for owner, entries in plan.owned.values()], only_absent=False
        )
        if (found := [entry for entry in entries if not _placed(owner.repo / entry.path)])
    ]
    if not missing:
        return None
    count = sum(len(found) for _owner, found in missing)
    if fetch_disabled():
        owner, found = min(missing, key=lambda item: item[1][0].path)
        first = found[0].path
        raise CorpusNotMaterializedError(
            f"{count} locked corpus file(s) this command reads are absent and "
            f"fetching is off ({NO_FETCH_ENV}); first: {first}" + _link_note(owner.repo, first)
        )
    print(
        f"corpus: fetching {count} locked file(s) this command reads "
        f"(set {NO_FETCH_ENV}=1 to skip)",
        file=sys.stderr,
    )
    try:
        return _merged(_place_owned(plan, missing))
    except ContentStoreError as exc:
        raise CorpusNotMaterializedError(str(exc)) from exc


def _selector_scopes(repo: Path, selector: Path) -> list[ScopeKey]:
    """Scopes of a release selector given as a path or a bare release name."""
    from axiom_corpus.corpus.releases import ReleaseManifest, resolve_release_manifest_path

    try:
        path = resolve_release_manifest_path(selector.as_posix())
    except ValueError:
        return []
    if not path.is_absolute() and not path.exists():
        path = repo / path
    try:
        release = ReleaseManifest.load(path)
    except (OSError, ValueError):
        return []
    return list(release.scope_keys)
