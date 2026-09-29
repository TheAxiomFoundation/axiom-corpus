"""Content-addressed corpus bytes: a shared local cache backed by R2.

The cache holds each distinct corpus file once, under the same key layout R2
uses for release artifacts (``objects/sha256/<xx>/<sha256>``). Worktrees get
copy-on-write clones of cache objects, never symlinks or hardlinks. See
``docs/corpus-storage.md``.
"""

from __future__ import annotations

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
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    LockEntry,
    iter_blob_contents,
)

CACHE_ENV = "AXIOM_CORPUS_CACHE"
DEFAULT_CACHE_ROOT = Path.home() / ".axiom" / "corpus-cache"
CHUNK_SIZE = 1 << 20
_FICLONE = 0x40049409  # Linux ioctl: clone the source file's extents into the target.


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


# --------------------------------------------------------------------------- cache


class ContentCache:
    """A directory of read-only objects named by the sha256 of their bytes."""

    def __init__(self, root: Path | None = None):
        self.root = (root or default_cache_root()).expanduser()

    def object_path(self, sha256: str) -> Path:
        return self.root / content_key(sha256)

    def contains(self, sha256: str, size: int | None = None) -> bool:
        path = self.object_path(sha256)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return False
        return size is None or stat.st_size == size

    def _tmp_dir(self) -> Path:
        tmp = self.root / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        return tmp

    def add_stream(self, chunks: Iterable[bytes], *, sha256: str, size: int) -> Path:
        """Write bytes into the cache after checking they hash to ``sha256``."""
        target = self.object_path(sha256)
        if self.contains(sha256, size):
            return target
        fd, tmp_name = tempfile.mkstemp(dir=self._tmp_dir(), prefix=f"{sha256[:12]}.")
        tmp = Path(tmp_name)
        try:
            write_verified(fd, chunks, sha256=sha256, size=size)
            return self._publish(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def add_file(self, path: Path, *, sha256: str | None = None, size: int | None = None) -> Path:
        """Clone a local file into the cache, verifying its bytes first."""
        actual_sha, actual_size = _hash_path(path)
        if sha256 is not None and (actual_sha, actual_size) != (sha256, size):
            raise ContentStoreError(
                f"{path} hashes to {actual_sha} ({actual_size} bytes), "
                f"expected {sha256} ({size} bytes)"
            )
        target = self.object_path(actual_sha)
        if self.contains(actual_sha, actual_size):
            return target
        tmp = self._tmp_dir() / f"{actual_sha[:12]}.{os.getpid()}.{threading.get_ident()}"
        tmp.unlink(missing_ok=True)
        try:
            clone_file(path, tmp)
            # Re-hash the placed copy: the source could have changed after hashing.
            if _hash_path(tmp) != (actual_sha, actual_size):
                raise ContentStoreError(f"{path} changed while it was being cached")
            return self._publish(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def _publish(self, tmp: Path, target: Path) -> Path:
        """Publish a verified object once; never replace an existing one.

        Replacing an object while another thread clones it made ``clonefile``
        fail with ENOENT. ``link`` creates the name only if it is absent; the
        losing writer holds the same verified bytes and discards them.
        """
        os.chmod(tmp, 0o444)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(tmp, target)
        except FileExistsError:
            pass
        except OSError as exc:
            if exc.errno not in {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV}:
                raise
            # No hardlinks here: fall back to an atomic create-if-absent rename.
            if not target.exists():
                os.replace(tmp, target)
        tmp.unlink(missing_ok=True)
        return target

    def verify_object(self, sha256: str) -> bool:
        path = self.object_path(sha256)
        if not path.is_file():
            return False
        return _hash_path(path)[0] == sha256


def write_verified(fd: int, chunks: Iterable[bytes], *, sha256: str, size: int) -> None:
    """Write ``chunks`` to ``fd`` (then close it); raise unless they hash to ``sha256``."""
    digest = hashlib.sha256()
    written = 0
    with os.fdopen(fd, "wb") as handle:
        for chunk in chunks:
            digest.update(chunk)
            written += len(chunk)
            handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    if written != size or digest.hexdigest() != sha256:
        raise ContentStoreError(
            f"refusing bytes for {sha256}: got sha256 {digest.hexdigest()} "
            f"and {written} bytes, expected {size} bytes"
        )


def _hash_path(path: Path) -> tuple[str, int]:
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
    """Serve migrated entries from the local git object store (no network)."""

    name = "git"

    def __init__(self, repo: Path):
        self.repo = repo
        self._lock = threading.Lock()
        self._present: dict[str, bool] = {}

    def _has(self, oid: str) -> bool:
        with self._lock:
            cached = self._present.get(oid)
        if cached is not None:
            return cached
        env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
        result = subprocess.run(
            ["git", "cat-file", "-e", oid],
            cwd=self.repo,
            env=env,
            capture_output=True,
            check=False,
        )
        present = result.returncode == 0
        with self._lock:
            self._present[oid] = present
        return present

    def open(self, entry: LockEntry) -> Iterator[bytes] | None:
        if entry.git_blob is None or not self._has(entry.git_blob):
            return None
        return self._stream(entry.git_blob)

    def _stream(self, oid: str) -> Iterator[bytes]:
        for _oid, chunks in iter_blob_contents(self.repo, [oid]):
            yield from chunks


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
    if cache.contains(entry.sha256, entry.size):
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
    if verify and _hash_path(target)[0] != entry.sha256:
        return "modified"
    return "present"


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
    ``materialized`` or ``modified`` (left untouched). With ``cache=None`` the
    verified bytes stream straight into place (for hosts without
    copy-on-write clones, where a cache would double disk use).
    """
    target = destination_for(repo, entry)
    state = destination_state(target, entry, verify=verify)
    if state == "present":
        return "present", None, None
    if state == "modified" and not force:
        return "modified", None, None
    if cache is None:
        return "materialized", *_stream_into_place(target, entry, sources)
    cached, source = ensure_cached(entry, cache, sources)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.corpus-fetch-{os.getpid()}-{threading.get_ident()}")
    tmp.unlink(missing_ok=True)
    try:
        method = clone_file(cached, tmp)
        os.chmod(tmp, 0o644)
        if verify and _hash_path(tmp) != (entry.sha256, entry.size):
            raise ContentStoreError(f"placed copy of {entry.path} does not match its lock")
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return "materialized", source, method


def _stream_into_place(
    target: Path,
    entry: LockEntry,
    sources: Iterable[ObjectSource],
) -> tuple[str, str]:
    failures: list[str] = []
    for source in sources:
        try:
            chunks = source.open(entry)
        except Exception as exc:  # noqa: BLE001 - try the next source, report all
            failures.append(f"{source.name}: {exc}")
            continue
        if chunks is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.corpus-fetch-")
        tmp = Path(tmp_name)
        try:
            write_verified(fd, chunks, sha256=entry.sha256, size=entry.size)
            os.chmod(tmp, 0o644)
            os.replace(tmp, target)
            return source.name, "stream"
        except ContentStoreError as exc:
            failures.append(f"{source.name}: {exc}")
        finally:
            tmp.unlink(missing_ok=True)
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
    """Materialize many entries; never raises for a single entry's failure."""
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

    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(one, entry) for entry in entry_list]
        for future in as_completed(futures):
            entry, state, source, method, error = future.result()
            done += 1
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
            else:
                report.failed[entry.path] = error or "unknown error"
            if progress is not None:
                progress(done, total)
    report.present.sort()
    report.materialized.sort()
    return report


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
    return cached.read_bytes()

