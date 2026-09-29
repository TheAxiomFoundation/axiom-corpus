"""Content-addressed corpus bytes: a shared local cache backed by R2.

The cache holds each distinct corpus file once, under the same key layout R2
uses for release artifacts (``objects/sha256/<xx>/<sha256>``). Worktrees get
copy-on-write clones of cache objects, never symlinks or hardlinks. See
``docs/corpus-storage.md``.
"""

from __future__ import annotations

import atexit
import ctypes
import ctypes.util
import errno
import fcntl
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Protocol

from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    FETCH_TEMP_DIR,
    FETCH_TEMP_MARKER,
    LockEntry,
    scope_for_path,
)

CACHE_ENV = "AXIOM_CORPUS_CACHE"
DEFAULT_CACHE_ROOT = Path.home() / ".axiom" / "corpus-cache"
CHUNK_SIZE = 1 << 20
_FICLONE = 0x40049409  # Linux ioctl: clone the source file's extents into the target.
_NO_HARDLINK_ERRNOS = {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK}


class ContentStoreError(RuntimeError):
    """Raised when bytes cannot be obtained, verified, or placed."""


def content_key(sha256: str) -> str:
    """Object key shared by the local cache and R2: ``objects/sha256/<xx>/<sha256>``."""
    return f"objects/sha256/{sha256[:2]}/{sha256}"


def default_cache_root() -> Path:
    configured = os.environ.get(CACHE_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_CACHE_ROOT


# --------------------------------------------------------------------------- cloning


def _load_clonefile() -> Callable[[bytes, bytes, int], int] | None:
    if sys.platform != "darwin":
        return None
    path = ctypes.util.find_library("c") or "/usr/lib/libSystem.B.dylib"
    try:
        libc = ctypes.CDLL(path, use_errno=True)
        clonefile = libc.clonefile
    except (OSError, AttributeError):
        return None
    clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
    clonefile.restype = ctypes.c_int
    return clonefile


_CLONEFILE = _load_clonefile()


def clone_file(source: Path, target: Path) -> str:
    """Create ``target`` as a copy-on-write clone of ``source`` where possible.

    Returns the method used: ``clonefile`` (APFS), ``ficlone`` (Linux reflink
    filesystems) or ``copy``. ``target`` must not exist. The result is always a
    new, independent regular file: never a symlink, never a hardlink.
    """
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    if _CLONEFILE is not None:
        result = _CLONEFILE(os.fsencode(source), os.fsencode(target), 0)
        if result == 0:
            return "clonefile"
        err = ctypes.get_errno()
        if err not in {errno.EXDEV, errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EINVAL}:
            raise OSError(err, os.strerror(err), str(target))
    if sys.platform.startswith("linux"):
        with source.open("rb") as src, target.open("xb") as dst:
            try:
                fcntl.ioctl(dst.fileno(), _FICLONE, src.fileno())
                return "ficlone"
            except OSError:
                shutil.copyfileobj(src, dst, CHUNK_SIZE)
                return "copy"
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst, CHUNK_SIZE)
    return "copy"


def publish_no_replace(tmp: Path, target: Path) -> bool:
    """Give ``tmp``'s file the name ``target`` only if ``target`` does not exist.

    Returns False, leaving ``target`` untouched, when something already exists
    there. ``tmp`` is gone either way. ``link`` is the atomic create-if-absent
    step; where the filesystem has no hardlinks, an exclusive create plus copy
    keeps the no-replace guarantee (a reader that checks size and hash never
    uses the partly written file).
    """
    try:
        try:
            os.link(tmp, target)
            return True
        except FileExistsError:
            return False
        except OSError as exc:
            if exc.errno not in _NO_HARDLINK_ERRNOS:
                raise
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(fd, "wb") as dst, tmp.open("rb") as src:
            shutil.copyfileobj(src, dst, CHUNK_SIZE)
            dst.flush()
            os.fsync(dst.fileno())
        os.chmod(target, tmp.stat().st_mode & 0o777)
        return True
    finally:
        tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------- cache


class ContentCache:
    """A directory of read-only, write-once objects named by their sha256.

    Objects are verified when written and again the first time this process
    uses them, so a corrupted object is dropped rather than copied into every
    checkout.
    """

    def __init__(self, root: Path | None = None):
        self.root = (root or default_cache_root()).expanduser()
        self._verified: set[str] = set()
        self._verified_lock = threading.Lock()

    def object_path(self, sha256: str) -> Path:
        return self.root / content_key(sha256)

    def contains(self, sha256: str, size: int | None = None) -> bool:
        path = self.object_path(sha256)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return False
        return size is None or stat.st_size == size

    def usable(self, sha256: str, size: int) -> bool:
        """True when a complete object with bytes hashing to ``sha256`` is present.

        The first use in this process hashes the object; a corrupt object is
        removed so the caller refetches it.
        """
        if not self.contains(sha256, size):
            return False
        with self._verified_lock:
            if sha256 in self._verified:
                return True
        if self.verify_object(sha256):
            with self._verified_lock:
                self._verified.add(sha256)
            return True
        self._discard(sha256)
        return False

    def _discard(self, sha256: str) -> None:
        path = self.object_path(sha256)
        with suppress(FileNotFoundError):
            os.chmod(path, 0o644)
            path.unlink()

    def _tmp_dir(self) -> Path:
        tmp = self.root / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        return tmp

    def add_stream(self, chunks: Iterable[bytes], *, sha256: str, size: int) -> Path:
        """Write bytes into the cache after checking they hash to ``sha256``."""
        target = self.object_path(sha256)
        if self.usable(sha256, size):
            _close(chunks)
            return target
        fd, tmp_name = tempfile.mkstemp(dir=self._tmp_dir(), prefix=f"{sha256[:12]}.")
        tmp = Path(tmp_name)
        try:
            write_verified(fd, chunks, sha256=sha256, size=size)
            return self._publish(tmp, target, sha256)
        finally:
            tmp.unlink(missing_ok=True)

    def add_file(self, path: Path, *, sha256: str | None = None, size: int | None = None) -> Path:
        """Clone a local file into the cache, verifying its bytes first."""
        actual_sha, actual_size = hash_path(path)
        if sha256 is not None and (actual_sha, actual_size) != (sha256, size):
            raise ContentStoreError(
                f"{path} hashes to {actual_sha} ({actual_size} bytes), "
                f"expected {sha256} ({size} bytes)"
            )
        target = self.object_path(actual_sha)
        if self.usable(actual_sha, actual_size):
            return target
        tmp = self._tmp_dir() / f"{actual_sha[:12]}.{os.getpid()}.{threading.get_ident()}"
        tmp.unlink(missing_ok=True)
        try:
            clone_file(path, tmp)
            # Re-hash the placed copy: the source could have changed after hashing.
            if hash_path(tmp) != (actual_sha, actual_size):
                raise ContentStoreError(f"{path} changed while it was being cached")
            return self._publish(tmp, target, actual_sha)
        finally:
            tmp.unlink(missing_ok=True)

    def _publish(self, tmp: Path, target: Path, sha256: str) -> Path:
        """Publish a verified object once; never replace an existing one.

        Replacing an object while another thread cloned it made ``clonefile``
        fail with ENOENT. A losing writer holds the same verified bytes and
        discards them.
        """
        os.chmod(tmp, 0o444)
        target.parent.mkdir(parents=True, exist_ok=True)
        if publish_no_replace(tmp, target):
            with self._verified_lock:
                self._verified.add(sha256)
        return target

    def verify_object(self, sha256: str) -> bool:
        path = self.object_path(sha256)
        if not path.is_file():
            return False
        return hash_path(path)[0] == sha256


def _close(chunks: Iterable[bytes]) -> None:
    close = getattr(chunks, "close", None)
    if callable(close):
        close()


def write_verified(fd: int, chunks: Iterable[bytes], *, sha256: str, size: int) -> None:
    """Write ``chunks`` to ``fd`` (then close it); raise unless they hash to ``sha256``."""
    digest = hashlib.sha256()
    written = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            for chunk in chunks:
                digest.update(chunk)
                written += len(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        _close(chunks)
    if written != size or digest.hexdigest() != sha256:
        raise ContentStoreError(
            f"refusing bytes for {sha256}: got sha256 {digest.hexdigest()} "
            f"and {written} bytes, expected {size} bytes"
        )


def hash_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


# --------------------------------------------------------------------------- sources


class ObjectSource(Protocol):
    """Somewhere cache misses can be filled from."""

    name: str

    def open(self, entry: LockEntry) -> Iterator[bytes] | None:
        """Return a chunk iterator for the entry's bytes, or None when absent."""


class GitBlobSource:
    """Serve migrated entries from the local git object store (no network).

    One long-lived ``git cat-file --batch`` process answers every request;
    ``GIT_NO_LAZY_FETCH`` keeps a partial clone from fetching missing objects.
    """

    name = "git"

    def __init__(self, repo: Path):
        self.repo = repo
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[bytes] | None = None

    def _process(self) -> subprocess.Popen[bytes]:
        if self._proc is None or self._proc.poll() is not None:
            env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
            self._proc = subprocess.Popen(
                ["git", "cat-file", "--batch"],
                cwd=self.repo,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            atexit.register(self.close)
        return self._proc

    def open(self, entry: LockEntry) -> Iterator[bytes] | None:
        if entry.git_blob is None:
            return None
        with self._lock:
            proc = self._process()
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(entry.git_blob.encode("ascii") + b"\n")
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            if len(header) == 2 and header[1] == b"missing":
                return None
            if len(header) != 3 or header[1] != b"blob":
                self.close()
                raise ContentStoreError(f"unexpected git cat-file reply for {entry.git_blob}")
            data = _read_exact(proc.stdout, int(header[2]))
            if proc.stdout.read(1) != b"\n":
                self.close()
                raise ContentStoreError(f"malformed git cat-file output for {entry.git_blob}")
        return iter((data,))

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        with suppress(OSError, ValueError):
            if proc.stdin is not None:
                proc.stdin.close()
        with suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
        if proc.poll() is None:
            proc.kill()


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    parts: list[bytes] = []
    left = size
    while left:
        chunk = stream.read(min(left, CHUNK_SIZE))
        if not chunk:
            raise ContentStoreError("truncated git cat-file output")
        parts.append(chunk)
        left -= len(chunk)
    return b"".join(parts)


class R2ObjectStore:
    """R2 content-addressed objects, with read-only fallback to legacy path keys."""

    name = "r2"

    def __init__(
        self,
        *,
        bucket: str,
        client: Any | None = None,
        client_factory: Callable[[], Any] | None = None,
        legacy_path_keys: bool = True,
    ):
        if client is None and client_factory is None:
            raise ValueError("R2ObjectStore needs a client or a client factory")
        self.bucket = bucket
        self._client = client
        self._client_factory = client_factory
        self._client_lock = threading.Lock()
        self.legacy_path_keys = legacy_path_keys

    @classmethod
    def from_environment(cls, *, workers: int = 16) -> R2ObjectStore:
        from axiom_corpus.corpus.r2 import load_r2_config, make_r2_client

        config = load_r2_config()
        return cls(
            bucket=config.bucket,
            client_factory=lambda: make_r2_client(config, max_pool_connections=workers + 4),
        )

    @property
    def client(self) -> Any:
        with self._client_lock:
            if self._client is None:
                assert self._client_factory is not None
                self._client = self._client_factory()
            return self._client

    def open(self, entry: LockEntry) -> Iterator[bytes] | None:
        body = self._get(content_key(entry.sha256))
        if body is None and self.legacy_path_keys:
            body = self._get(entry.path.removeprefix(f"{CORPUS_BASE}/"))
        if body is None:
            return None
        return _iter_body(body)

    def has(self, sha256: str, size: int | None = None) -> bool:
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=content_key(sha256))
        except Exception as exc:  # noqa: BLE001 - boto raises ClientError; fakes raise KeyError
            if _is_missing(exc):
                return False
            raise
        return size is None or int(response.get("ContentLength", -1)) == size

    def put(self, path: Path, *, sha256: str, size: int) -> bool:
        """Upload one verified object if absent; return True when this call wrote it.

        Conditional write (``IfNoneMatch: *``) plus exact readback: an existing
        object must already hold the same bytes, and the stored object must hash
        to ``sha256`` afterwards.
        """
        from axiom_corpus.release.publication import (
            _put_snapshot_if_absent,
            _read_object_or_none,
            _snapshot_file,
            _verify_bytes,
        )

        key = content_key(sha256)
        with _snapshot_file(path) as (snapshot, actual_sha, actual_size):
            if (actual_sha, actual_size) != (sha256, size):
                raise ContentStoreError(f"{path} no longer hashes to {sha256}")
            existing = _read_object_or_none(self.client, bucket=self.bucket, key=key)
            if existing is None:
                uploaded = _put_snapshot_if_absent(
                    self.client,
                    bucket=self.bucket,
                    key=key,
                    snapshot=snapshot,
                    filename=path.name,
                    sha256=sha256,
                    size=size,
                )
            else:
                _verify_bytes(existing, sha256=sha256, size=size, label=key)
                uploaded = False
        readback = _read_object_or_none(self.client, bucket=self.bucket, key=key)
        if readback is None:
            raise ContentStoreError(f"R2 readback is missing after upload: {key}")
        _verify_bytes(readback, sha256=sha256, size=size, label=key)
        return uploaded

    def _get(self, key: str) -> Any | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            if _is_missing(exc):
                return None
            raise
        return response.get("Body")


def _is_missing(exc: Exception) -> bool:
    if isinstance(exc, KeyError):
        return True
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str(response.get("Error", {}).get("Code", ""))
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return code in {"404", "NoSuchKey", "NotFound"} or status == 404
    return False


def _iter_body(body: Any) -> Iterator[bytes]:
    with closing(body):
        while True:
            chunk = body.read(CHUNK_SIZE)
            if not chunk:
                return
            yield chunk if isinstance(chunk, bytes) else bytes(chunk)


# --------------------------------------------------------------------------- fetch


def ensure_cached(
    entry: LockEntry,
    cache: ContentCache,
    sources: Iterable[ObjectSource],
) -> tuple[Path, str]:
    """Return the cache path for ``entry``, filling it from the first source that has it."""
    if cache.usable(entry.sha256, entry.size):
        return cache.object_path(entry.sha256), "cache"
    failures: list[str] = []
    for source in sources:
        try:
            chunks = source.open(entry)
        except Exception as exc:  # noqa: BLE001 - try the next source, report all
            failures.append(f"{source.name}: {exc}")
            continue
        if chunks is None:
            continue
        try:
            return cache.add_stream(chunks, sha256=entry.sha256, size=entry.size), source.name
        except ContentStoreError as exc:
            failures.append(f"{source.name}: {exc}")
    detail = "; ".join(failures) if failures else "no source holds it"
    raise ContentStoreError(
        f"cannot obtain {entry.path} (sha256 {entry.sha256}, {entry.size} bytes): {detail}"
    )


@dataclass
class FetchReport:
    """What one fetch did, per entry."""

    present: list[str] = field(default_factory=list)
    materialized: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    rolled_back: list[str] = field(default_factory=list)
    sources: dict[str, int] = field(default_factory=dict)
    methods: dict[str, int] = field(default_factory=dict)
    bytes_materialized: int = 0

    @property
    def ok(self) -> bool:
        return not self.failed

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "present": len(self.present),
            "materialized": len(self.materialized),
            "bytes_materialized": self.bytes_materialized,
            "modified": sorted(self.modified),
            "failed": dict(sorted(self.failed.items())),
            "rolled_back": sorted(self.rolled_back),
            "sources": dict(sorted(self.sources.items())),
            "methods": dict(sorted(self.methods.items())),
        }


def destination_for(repo: Path, entry: LockEntry) -> Path:
    """The worktree path for ``entry``; refuses any symlinked component."""
    target = repo / entry.path
    lexical = repo
    for part in entry.path.split("/"):
        lexical = lexical / part
        if lexical.is_symlink():
            raise ContentStoreError(f"refusing to write through a symlink: {lexical}")
    return target


def destination_state(target: Path, entry: LockEntry, *, verify: bool) -> str:
    """``missing``, ``present`` or ``modified`` for one worktree file."""
    try:
        stat = target.lstat()
    except FileNotFoundError:
        return "missing"
    if not target.is_file() or target.is_symlink():
        return "modified"
    if stat.st_size != entry.size:
        return "modified"
    if verify and hash_path(target)[0] != entry.sha256:
        return "modified"
    return "present"


def _fetch_tmp(repo: Path, target: Path) -> Path:
    """A temporary name for a file bound for ``target``: same filesystem, outside any scope."""
    directory = repo / FETCH_TEMP_DIR
    directory.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=directory, prefix=f"{FETCH_TEMP_MARKER}{target.name[:40]}.")
    os.close(fd)
    os.unlink(name)
    return Path(name)


def _place(tmp: Path, target: Path, *, replace: bool) -> bool:
    """Move a verified temporary file into place; False if ``target`` appeared meanwhile."""
    os.chmod(tmp, 0o644)
    target.parent.mkdir(parents=True, exist_ok=True)
    if replace:
        os.replace(tmp, target)
        return True
    return publish_no_replace(tmp, target)


def materialize_entry(
    repo: Path,
    entry: LockEntry,
    cache: ContentCache | None,
    sources: Iterable[ObjectSource],
    *,
    force: bool = False,
    verify: bool = False,
) -> tuple[str, str | None, str | None]:
    """Place one locked file in the worktree.

    Returns ``(state, source, method)`` where state is ``present``,
    ``materialized`` or ``modified`` (left untouched). A file that is missing
    is only ever created, never replaced: if something writes it while the
    bytes are on their way, that file wins and the entry reports
    ``modified``. With ``cache=None`` the verified bytes stream straight into
    place (hosts without copy-on-write clones, where a cache would double disk
    use).
    """
    target = destination_for(repo, entry)
    state = destination_state(target, entry, verify=verify)
    if state == "present":
        return "present", None, None
    if state == "modified" and not force:
        return "modified", None, None
    replace = state == "modified"
    tmp = _fetch_tmp(repo, target)
    try:
        if cache is None:
            source, method = _stream_to(tmp, entry, sources)
        else:
            cached, source = ensure_cached(entry, cache, sources)
            method = clone_file(cached, tmp)
        if verify and hash_path(tmp) != (entry.sha256, entry.size):
            raise ContentStoreError(f"placed copy of {entry.path} does not match its lock")
        if not _place(tmp, target, replace=replace):
            return "modified", None, None
    finally:
        tmp.unlink(missing_ok=True)
    return "materialized", source, method


def _stream_to(tmp: Path, entry: LockEntry, sources: Iterable[ObjectSource]) -> tuple[str, str]:
    failures: list[str] = []
    for source in sources:
        try:
            chunks = source.open(entry)
        except Exception as exc:  # noqa: BLE001 - try the next source, report all
            failures.append(f"{source.name}: {exc}")
            continue
        if chunks is None:
            continue
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            write_verified(fd, chunks, sha256=entry.sha256, size=entry.size)
            return source.name, "stream"
        except ContentStoreError as exc:
            failures.append(f"{source.name}: {exc}")
    detail = "; ".join(failures) if failures else "no source holds it"
    raise ContentStoreError(
        f"cannot obtain {entry.path} (sha256 {entry.sha256}, {entry.size} bytes): {detail}"
    )


def materialize(
    repo: Path,
    entries: Iterable[LockEntry],
    cache: ContentCache | None,
    sources: Iterable[ObjectSource],
    *,
    force: bool = False,
    verify: bool = False,
    workers: int = 8,
    progress: Callable[[int, int], None] | None = None,
) -> FetchReport:
    """Materialize many entries; never raises for a single entry's failure.

    A scope's ``sources/`` directory stays all or nothing: when any of its
    files fails, the files this call created in that directory are removed
    again (``rolled_back``), because code lists that directory to find a
    scope's sources.
    """
    entry_list = list(entries)
    source_list = list(sources)
    report = FetchReport()
    total = len(entry_list)

    def one(entry: LockEntry) -> tuple[LockEntry, str, str | None, str | None, str | None]:
        try:
            state, source, method = materialize_entry(
                repo, entry, cache, source_list, force=force, verify=verify
            )
            return entry, state, source, method, None
        except (ContentStoreError, OSError) as exc:
            return entry, "failed", None, None, str(exc)

    created_by_scope: dict[tuple[str, str, str], list[LockEntry]] = {}
    failed_scopes: set[tuple[str, str, str]] = set()
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(one, entry) for entry in entry_list]
        for future in as_completed(futures):
            entry, state, source, method, error = future.result()
            done += 1
            sources_scope = _sources_scope(entry)
            if state == "present":
                report.present.append(entry.path)
            elif state == "modified":
                report.modified.append(entry.path)
            elif state == "materialized":
                report.materialized.append(entry.path)
                report.bytes_materialized += entry.size
                if source:
                    report.sources[source] = report.sources.get(source, 0) + 1
                if method:
                    report.methods[method] = report.methods.get(method, 0) + 1
                if sources_scope is not None:
                    created_by_scope.setdefault(sources_scope, []).append(entry)
            else:
                report.failed[entry.path] = error or "unknown error"
                if sources_scope is not None:
                    failed_scopes.add(sources_scope)
            if progress is not None:
                progress(done, total)
    for scope in failed_scopes:
        for entry in created_by_scope.get(scope, []):
            (repo / entry.path).unlink(missing_ok=True)
            report.materialized.remove(entry.path)
            report.bytes_materialized -= entry.size
            report.rolled_back.append(entry.path)
    report.present.sort()
    report.materialized.sort()
    return report


def _sources_scope(entry: LockEntry) -> tuple[str, str, str] | None:
    if not entry.path.startswith(f"{CORPUS_BASE}/sources/"):
        return None
    return scope_for_path(entry.path)


def read_entry_bytes(
    repo: Path,
    entry: LockEntry,
    cache: ContentCache,
    sources: Iterable[ObjectSource],
) -> bytes:
    """Return the verified bytes of one entry (worktree, cache, or a source)."""
    target = repo / entry.path
    if target.is_file() and not target.is_symlink():
        payload = target.read_bytes()
        if len(payload) == entry.size and hashlib.sha256(payload).hexdigest() == entry.sha256:
            return payload
    cached, _source = ensure_cached(entry, cache, sources)
    payload = cached.read_bytes()
    if len(payload) != entry.size or hashlib.sha256(payload).hexdigest() != entry.sha256:
        raise ContentStoreError(f"cache object for {entry.path} changed while being read")
    return payload
