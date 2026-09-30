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
    materialize,
)
from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
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
    return root if (root / "src" / "axiom_corpus").is_dir() else None


def find_repo_root(start: Path | None = None) -> Path | None:
    """The axiom-corpus checkout containing ``start`` (default: cwd), if any."""
    here = (start or Path.cwd()).resolve()
    return _repo_root_for_dir(here if here.is_dir() else here.parent)


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

        A relative ``data/corpus/...`` spelling is taken as repository-relative;
        any other relative path is relative to the working directory. Symlinked
        spellings (``/tmp`` for ``/private/tmp``) resolve to the same answer.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            text = candidate.as_posix()
            if text == CORPUS_BASE or text.startswith(f"{CORPUS_BASE}/"):
                return text
            candidate = Path.cwd() / candidate
        real = Path(os.path.realpath(candidate))
        try:
            return real.relative_to(self.repo).as_posix()
        except ValueError:
            return None

    def ensure(self, entries: Sequence[LockEntry], *, verify: bool = False) -> FetchReport:
        self.require_valid_locks()
        if not entries:
            return FetchReport()
        pending = list(entries)
        # A concurrent fetch that fails rolls back the source files it placed,
        # which may be ones this call counted as present; check and retry once.
        for _attempt in range(2):
            report = materialize(
                self.repo,
                pending,
                self.cache,
                self.sources,
                verify=verify,
                workers=self.workers,
            )
            if report.failed:
                first, reason = next(iter(sorted(report.failed.items())))
                raise CorpusNotMaterializedError(
                    f"{len(report.failed)} locked corpus file(s) could not be fetched; "
                    f"first: {first}: {reason}. Check R2 credentials "
                    "(~/.config/axiom-foundation/r2-credentials.json) or run "
                    "`axiom-corpus-ingest corpus fetch` with network access."
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
        present = target.is_file() and not target.is_symlink()
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
            if canonical is not None and canonical.exists() and os.path.samefile(target, canonical):
                entry = folded
        if entry is None:
            if present:
                return target
            raise CorpusNotMaterializedError(
                f"{rel} is neither present nor locked. Run `axiom-corpus-ingest corpus "
                "status` to see which scopes this checkout has."
            )
        scope = scope_for_path(entry.path)
        if present and scope in self._complete_source_scopes:
            return target
        missing = [
            item
            for item in self.locks.with_whole_source_dirs([entry])
            if not (self.repo / item.path).is_file()
        ]
        if missing:
            if fetch_disabled():
                raise CorpusNotMaterializedError(
                    f"{len(missing)} locked corpus file(s) that {rel} needs are absent and "
                    f"fetching is off ({NO_FETCH_ENV}); first: {missing[0].path}"
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


def ensure_corpus_paths(paths: Iterable[str | Path], *, repo: Path | None = None) -> FetchReport:
    """Materialize the locked files at or under each path. No-op without locks.

    With fetching disabled, locked files that are absent raise instead.
    """
    path_list = list(paths)
    resolver = resolver_for(repo)
    if resolver is None or not resolver.active:
        return FetchReport()
    if fetch_disabled():
        require_materialized(path_list, repo=resolver.repo)
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
        absent = [entry.path for entry in entries if not (resolver.repo / entry.path).is_file()]
        if absent:
            raise CorpusNotMaterializedError(
                f"{len(absent)} locked corpus file(s) are absent and fetching is off "
                f"({NO_FETCH_ENV}); first: {absent[0]}"
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
    are fetched instead. No-op without lock files.
    """
    path_list = [Path(path) for path in paths]
    if repo is None and path_list:
        repo = find_repo_root(_existing_ancestor(path_list[0]))
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
    )


def fetch_locked_file(path: str | Path) -> bool:
    """Fetch ``path`` if a lock in its checkout names it; True when it now exists.

    Returns False (and does nothing) for paths no lock names, outside any
    checkout, or with fetching disabled. Raises ``CorpusNotMaterializedError``
    when a locked file cannot be fetched: silently reading nothing would be
    worse.
    """
    candidate = Path(path)
    if candidate.exists():
        return True
    anchor = candidate if candidate.is_absolute() else Path.cwd() / candidate
    resolver = resolver_for(find_repo_root(_existing_ancestor(anchor)))
    if resolver is None or not resolver.active:
        return False
    resolver.require_valid_locks()
    rel = resolver.relative(anchor)
    if rel is None or rel not in resolver.locks.by_path:
        return False
    if fetch_disabled():
        raise CorpusNotMaterializedError(
            f"{rel} is locked but absent, and fetching is off ({NO_FETCH_ENV}); reading it "
            "as empty would be wrong. Fetch it first."
        )
    resolver.ensure(resolver.entries_for_paths([rel]))
    return True


def resolve_corpus_path(path: str | Path, *, repo: Path | None = None) -> Path:
    """Return a regular file for ``path``, fetching it if it is locked and absent."""
    candidate = Path(path)
    if (
        candidate.is_file()
        and not candidate.is_symlink()
        # The real path, so a relative or symlinked spelling of a source file
        # still gets its siblings; realpath runs no git process.
        and f"/{CORPUS_BASE}/sources/" not in fold_path(os.path.realpath(candidate))
    ):
        return candidate  # present and not a source: nothing to widen, no git call
    if repo is None:
        repo = find_repo_root(_existing_ancestor(candidate))
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
        if not (resolver.repo / entry.path).is_file()
    ]
    if not missing:
        return None
    if fetch_disabled():
        raise CorpusNotMaterializedError(
            f"{len(missing)} locked corpus file(s) this command reads are absent and "
            f"fetching is off ({NO_FETCH_ENV}); first: {sorted(e.path for e in missing)[0]}"
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
