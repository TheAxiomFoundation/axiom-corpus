"""Find corpus bytes for code that reads ``data/corpus`` paths.

Callers keep reading ``data/corpus/...``. The resolver makes sure the locked
files they need exist there first, fetching from the shared cache, local git
objects, or R2. With no lock files it does nothing, so the same code runs
before and after the corpus left git. See ``docs/corpus-storage.md``.
"""

from __future__ import annotations

import contextlib
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
    PROTECTED_CORPUS_PREFIXES,
    LockEntry,
    LockSet,
    ScopeKey,
    fold_path,
    is_protected_corpus_path,
    load_locks,
    scope_for_path,
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


def _standing_places(probe: Path, physical: Path, home: Path | None) -> list[tuple[Path, str]]:
    """Each guarded place ``probe`` stands at below a symlink, in the order it resolves.

    The path is resolved as the operating system resolves it, links inside a
    link's target included. At each symlink the path stands at the link's own
    place plus the rest of the path. A ``..`` after the link is resolved from
    the link's target, so such a place counts only where it reaches the same
    entry. A symlinked file ends the walk: it never stands anywhere else.
    """
    places: list[tuple[Path, str]] = []
    for _link in range(_MAX_LINKS):
        parts = probe.parts
        prefix = Path(parts[0])
        for index in range(1, len(parts)):
            prefix = prefix / parts[index]
            if prefix.is_symlink():
                break
        else:
            return places
        parent = Path(os.path.realpath(prefix.parent))
        rest = parts[index + 1 :]
        stands = _protected_at((*parent.parts, parts[index], *rest), home)
        if stands is not None and (".." not in rest or _same_place(stands[0] / stands[1], physical)):
            places.append(stands)
        if not rest and not prefix.is_dir():
            return places
        try:
            target = os.readlink(prefix)
        except OSError:
            return places
        probe = Path(parent, target, *rest)
    return places


def _protected_name(probe: Path, physical: Path, home: Path | None = None) -> tuple[Path, str] | None:
    """The checkout and guarded corpus path that ``probe`` names, if it names one.

    ``probe`` is absolute and ``physical`` is its realpath. A symlink at or
    above a guarded path (``_guarded``) stands where locked files belong, so
    a path through one names, in order:

    1. a symlinked file: the last guarded place it stands at, its own path;
    2. a path that reaches a guarded path whose name it spells exactly: that
       path, through any links. A worktree whose ``data/corpus/provisions``
       links to another checkout's names that checkout's files;
    3. otherwise the last guarded place it stands at below a link (one
       leading to another corpus path, outside every checkout, nowhere, an
       unprotected directory), so that place's lock applies; unless that
       place has the name of the guarded path it reaches, which it then names.

    A path that stands nowhere names the guarded path it reaches, if any.
    """
    reached = None if _is_symlinked_file(probe) else _protected_at(physical.parts, home)
    if reached is not None and _spells(probe, reached[1]):
        return reached
    places = _standing_places(probe, physical, home)
    found = places[-1] if places else None
    if reached is not None and (found is None or found[1] == reached[1]):
        return reached
    return found


def _link_holder(probe: Path) -> Path | None:
    """The checkout in which ``probe`` is a symlinked file at a protected path, if any.

    A link outside the protected paths (``/etc/localtime``) is settled
    without a git process.
    """
    if not _is_symlinked_file(probe):
        return None
    named = _protected_name(probe, Path(os.path.realpath(probe)))
    return named[0] if named is not None else None


def _checkout_for(path: Path) -> Path | None:
    """The checkout that names ``path`` (see ``CorpusResolver.relative``).

    The checkout whose protected path ``path`` names (``_protected_name``),
    else the one it resolves into, a dangling link's target included.
    """
    probe = path if path.is_absolute() else Path.cwd() / path
    physical = Path(os.path.realpath(probe))
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
            for entry in self.locks.entries_under(rel):
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
        physical = Path(os.path.realpath(candidate))
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
        try:
            return physical.relative_to(self.repo).as_posix()
        except ValueError:
            pass
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
        is itself already present: callers list the directory next.
        """
        rel = self.relative(path)
        if rel is None:
            raise ValueError(f"{path} is not inside {self.repo}")
        target = self.repo / rel
        present = _placed(target)
        if present and not fold_path(rel).startswith(f"{CORPUS_BASE}/sources/"):
            return target
        self.require_valid_locks()
        # A case-variant spelling names the same locked file only where the
        # filesystem merged them, i.e. when the variant exists on disk.
        entry = self.locks.by_path.get(rel)
        if entry is None and present:
            folded = self.locks.find_folded(rel)
            canonical = self.repo / folded.path if folded is not None else None
            # Only a spelling the filesystem merged, i.e. the same file on disk.
            try:
                merged = canonical is not None and os.path.samefile(target, canonical)
            except FileNotFoundError:  # one of them vanished meanwhile (a rollback)
                merged = False
            if merged:
                entry = folded
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


def _by_checkout(paths: Sequence[str | Path]) -> dict[Path | None, list[str | Path]]:
    """``paths`` grouped by the checkout that names each (``_checkout_for``), in order.

    None collects the paths no checkout names; the callers hand those to the
    working directory's checkout, as before.
    """
    groups: dict[Path | None, list[str | Path]] = {}
    for path in paths:
        groups.setdefault(_checkout_for(Path(path)), []).append(path)
    return groups


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


def ensure_corpus_paths(paths: Iterable[str | Path], *, repo: Path | None = None) -> FetchReport:
    """Materialize the locked files at or under each path. No-op without locks.

    Without ``repo``, each path goes to the checkout that names it. With
    fetching disabled, locked files that are absent raise instead.
    """
    path_list = list(paths)
    if repo is None and path_list:
        return _merged(
            _ensure_paths_in(checkout, group) for checkout, group in _by_checkout(path_list).items()
        )
    return _ensure_paths_in(repo, path_list)


def _ensure_paths_in(repo: Path | None, path_list: list[str | Path]) -> FetchReport:
    resolver = resolver_for(repo)
    if resolver is None or not resolver.active:
        return FetchReport()
    if fetch_disabled():
        _require_in(resolver.repo, [Path(path) for path in path_list], fetch=False)
        return FetchReport()
    return resolver.ensure_paths(path_list)


def ensure_corpus_scopes(scopes: Iterable[ScopeKey], *, repo: Path | None = None) -> FetchReport:
    """Materialize whole scopes. No-op without locks.

    With fetching disabled, locked files that are absent raise instead.
    """
    scope_list = list(scopes)
    resolver = resolver_for(repo)
    if resolver is None or not resolver.active:
        return FetchReport()
    entries = resolver.entries_for_scopes(scope_list)
    if fetch_disabled():
        resolver.require_valid_locks()
        absent = [entry.path for entry in entries if not _placed(resolver.repo / entry.path)]
        if absent:
            raise CorpusNotMaterializedError(
                f"{len(absent)} locked corpus file(s) are absent and fetching is off "
                f"({NO_FETCH_ENV}); first: {absent[0]}" + _link_note(resolver.repo, absent[0])
            )
        return FetchReport()
    return resolver.ensure(entries)


def require_materialized(
    paths: Iterable[str | Path],
    *,
    repo: Path | None = None,
    fetch: bool = False,
) -> None:
    """Refuse to walk a corpus directory that holds only part of its locked files.

    Code that lists ``data/corpus`` directories would otherwise compute on
    whatever subset happens to be fetched. With ``fetch`` the missing files
    are fetched instead. Without ``repo``, each path is checked in the
    checkout that names it. No-op without lock files.
    """
    path_list = [Path(path) for path in paths]
    if repo is None and path_list:
        for checkout, group in _by_checkout(path_list).items():
            _require_in(checkout, [Path(path) for path in group], fetch=fetch)
        return
    _require_in(repo, path_list, fetch=fetch)


def _require_in(repo: Path | None, path_list: list[Path], *, fetch: bool) -> None:
    resolver = resolver_for(repo)
    if resolver is None or not resolver.active:
        return
    resolver.require_valid_locks()
    missing: list[LockEntry] = []
    rels = [rel for rel in (resolver.relative(path) for path in path_list) if rel is not None]
    for rel in rels:
        missing.extend(resolver.locks.missing_under(resolver.repo, rel))
    if not missing:
        return
    if fetch and not fetch_disabled():
        resolver.ensure(resolver.locks.with_whole_source_dirs(missing))
        return
    # Name at most a few paths: callers may pass thousands of exact files.
    named = rels if len(rels) <= 3 else [*rels[:3], f"and {len(rels) - 3} more"]
    command = (
        " ".join(f"--path {rel}" for rel in rels)
        if len(rels) <= 3
        else "--paths-from <file listing them>"
    )
    raise CorpusNotMaterializedError(
        f"{len(missing)} locked corpus file(s) under {', '.join(named)} are not in this "
        f"checkout (first: {missing[0].path}); results would cover only part of the "
        f"corpus. Run `axiom-corpus-ingest corpus fetch {command}` first."
        + _link_note(resolver.repo, missing[0].path)
    )


def fetch_locked_file(path: str | Path) -> bool:
    """Fetch ``path`` if a lock in its checkout names it; True when it is now in place.

    Returns False (and does nothing) for paths no lock names, outside any
    checkout, or with fetching disabled. Raises ``CorpusNotMaterializedError``
    when a locked file cannot be fetched, or when a symlink stands where it
    belongs: silently reading nothing, or bytes no lock checked, would be
    worse.
    """
    candidate = Path(path)
    anchor = candidate if candidate.is_absolute() else Path.cwd() / candidate
    # A present path is read as it is, save a symlinked file at a protected
    # path, which stands where a locked file belongs.
    if candidate.exists() and _link_holder(anchor) is None:
        return True
    resolver = resolver_for(_checkout_for(anchor))
    if resolver is None or not resolver.active:
        return False
    resolver.require_valid_locks()
    rel = resolver.relative(anchor)
    if rel is None or rel not in resolver.locks.by_path:
        return False
    if (resolver.repo / rel).is_symlink():
        raise _symlinked_error(rel, resolver.repo / rel)
    if fetch_disabled():
        raise CorpusNotMaterializedError(
            f"{rel} is locked but absent, and fetching is off ({NO_FETCH_ENV}); reading it "
            "as empty would be wrong. Fetch it first." + _link_note(resolver.repo, rel)
        )
    resolver.ensure(resolver.entries_for_paths([rel]))
    return True


def resolve_corpus_path(path: str | Path, *, repo: Path | None = None) -> Path:
    """Return a regular file for ``path``, fetching it if it is locked and absent."""
    candidate = Path(path)
    absolute = os.path.abspath(candidate)
    if (
        candidate.is_file()
        and not candidate.is_symlink()
        # Spelled through no symlink, so it stands nowhere but where it is,
        # and no source file, so there are no siblings to bring.
        and os.path.realpath(candidate) == absolute
        and f"/{CORPUS_BASE}/sources/" not in fold_path(absolute)
    ):
        return candidate  # nothing to widen, no git call
    if repo is None:
        repo = _checkout_for(candidate)
    resolver = resolver_for(repo)
    if resolver is None or not resolver.active or resolver.relative(candidate) is None:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
        raise CorpusNotMaterializedError(f"{path} does not exist")
    return resolver.resolve(path)


# --------------------------------------------------------------------------- CLI hook

_SCOPE_ARG_NAMES = ("jurisdiction", "document_class", "version")
# Argument names that never name corpus inputs: the dispatch marker, and the
# free-text command that sign-ingest-manifest records in the manifest.
_NON_INPUT_ARGS = frozenset({"func", "command", "_cli_command"})


def cli_repo(args: Any) -> Path | None:
    """The checkout a CLI invocation works on: the one holding ``--base``, else cwd's."""
    base = getattr(args, "base", None)
    if isinstance(base, str | Path) and str(base):
        found = find_repo_root(_existing_ancestor(Path(base)))
        if found is not None:
            return found
    return find_repo_root()


def _is_corpus_base(repo: Path, base: object) -> bool:
    if not isinstance(base, str | Path) or not str(base):
        return False
    candidate = Path(base) if Path(base).is_absolute() else Path.cwd() / Path(base)
    return Path(os.path.realpath(candidate)) == (repo / CORPUS_BASE).resolve()


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
            # A path under a protected prefix names files to read; the bare
            # base (``--base data/corpus``) names nothing by itself.
            if rel is not None and is_protected_corpus_path(rel.rstrip("/") + "/"):
                paths.append(rel.rstrip("/"))
    scopes: list[ScopeKey] = []
    if _is_corpus_base(repo, getattr(args, "base", None)):
        values = [getattr(args, name, None) for name in _SCOPE_ARG_NAMES]
        if all(isinstance(v, str) and v for v in values):
            scopes.append((str(values[0]), str(values[1]), str(values[2])))
    return paths, scopes, selectors


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
    if resolver is None or not resolver.active:
        return None
    resolver.require_valid_locks()
    paths, scopes, selectors = corpus_inputs_from_args(args, repo=resolver.repo)
    if not include_scope:
        scopes = []
    for selector in selectors:
        scopes.extend(_selector_scopes(resolver.repo, selector))
    if not paths and not scopes:
        return None
    entries = {e.path: e for e in resolver.entries_for_paths(paths)}
    for entry in resolver.entries_for_scopes(scopes):
        entries[entry.path] = entry
    missing = [
        entry
        for entry in entries.values()
        if not _placed(resolver.repo / entry.path)
    ]
    if not missing:
        return None
    if fetch_disabled():
        first = min(entry.path for entry in missing)
        raise CorpusNotMaterializedError(
            f"{len(missing)} locked corpus file(s) this command reads are absent and "
            f"fetching is off ({NO_FETCH_ENV}); first: {first}" + _link_note(resolver.repo, first)
        )
    print(
        f"corpus: fetching {len(missing)} locked file(s) this command reads "
        f"(set {NO_FETCH_ENV}=1 to skip)",
        file=sys.stderr,
    )
    try:
        return resolver.ensure(sorted(missing, key=lambda e: e.path))
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
