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
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    FETCH_TEMP_DIR,
    FETCH_TEMP_MARKER,
    LockEntry,
    fold_path,
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


def _load_rename_noreplace() -> Callable[[Path, Path], int] | None:
    """An atomic "rename unless the target exists" from the C library, if any.

    macOS has ``renamex_np(RENAME_EXCL)``; Linux has ``renameat2(RENAME_NOREPLACE)``.
    Returns a function giving 0 on success or an errno.
    """
    path = ctypes.util.find_library("c")
    try:
        libc = ctypes.CDLL(path, use_errno=True)
    except OSError:
        return None
    if sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        renamex = libc.renamex_np
        renamex.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex.restype = ctypes.c_int

        def rename_excl(src: Path, dst: Path) -> int:
            if renamex(os.fsencode(src), os.fsencode(dst), 0x4) == 0:  # RENAME_EXCL
                return 0
            return ctypes.get_errno()

        return rename_excl
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        renameat2 = libc.renameat2
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int

        def rename_noreplace(src: Path, dst: Path) -> int:
            at_fdcwd = -100
            if renameat2(at_fdcwd, os.fsencode(src), at_fdcwd, os.fsencode(dst), 1) == 0:
                return 0
            return ctypes.get_errno()

        return rename_noreplace
    return None


_RENAME_NOREPLACE = _load_rename_noreplace()


def publish_no_replace(tmp: Path, target: Path) -> bool:
    """Give ``tmp``'s file the name ``target`` only if ``target`` does not exist.

    Returns False, leaving ``target`` untouched, when something already exists
    there. No path ever shows partial bytes under ``target``:

    1. ``link(2)``, where the filesystem has hardlinks;
    2. otherwise a no-replace rename (``renamex_np``/``renameat2``);
    3. otherwise (exFAT, some network filesystems) a plain rename made while
       holding an exclusive publish lock in ``tmp``'s directory, after checking
       that ``target`` is still absent. Writers that publish through this
       function exclude each other; a writer that does not (an extractor)
       could only be replaced in the instant between that check and the
       rename.

    Across filesystems (``EXDEV``) the bytes are first copied to a hidden
    temporary file beside ``target``. The caller removes ``tmp`` afterwards if
    it still exists.
    """
    return _publish(tmp, target, allow_sibling=True, lock_dir=tmp.parent)


def _publish(tmp: Path, target: Path, *, allow_sibling: bool, lock_dir: Path) -> bool:
    try:
        os.link(tmp, target)
        return True
    except FileExistsError:
        return False
    except OSError as exc:
        if exc.errno == errno.EXDEV and allow_sibling:
            return _publish_via_sibling(tmp, target, lock_dir)
        if exc.errno not in _NO_HARDLINK_ERRNOS:
            raise
    if _RENAME_NOREPLACE is not None:
        err = _RENAME_NOREPLACE(tmp, target)
        if err == 0:
            return True
        if err == errno.EEXIST:
            return False
        if err == errno.EXDEV and allow_sibling:
            return _publish_via_sibling(tmp, target, lock_dir)
        if err not in {errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL, errno.ENOSYS}:
            raise OSError(err, os.strerror(err), str(target))
    return _publish_locked_rename(tmp, target, lock_dir)


def _publish_via_sibling(tmp: Path, target: Path, lock_dir: Path) -> bool:
    """Copy ``tmp`` next to ``target`` (same filesystem), then publish that copy."""
    fd, name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name[:40]}{FETCH_TEMP_MARKER}"
    )
    sibling = Path(name)
    try:
        with os.fdopen(fd, "wb") as dst, tmp.open("rb") as src:
            shutil.copyfileobj(src, dst, CHUNK_SIZE)
            dst.flush()
            os.fsync(dst.fileno())
        os.chmod(sibling, tmp.stat().st_mode & 0o777)
        # The sibling shares target's directory, so this cannot hit EXDEV again;
        # the publish lock stays in the staging directory, outside the scope.
        return _publish(sibling, target, allow_sibling=False, lock_dir=lock_dir)
    finally:
        sibling.unlink(missing_ok=True)


PUBLISH_LOCK_STALE_SECONDS = 30.0


def publish_lock_path(target: Path, lock_dir: Path) -> Path:
    """The publish lock for ``target``: one file per real, case-folded target path."""
    real = os.path.join(os.path.realpath(target.parent), target.name)
    key = hashlib.sha256(fold_path(real).encode("utf-8", "surrogateescape")).hexdigest()[:32]
    return lock_dir / f"{FETCH_TEMP_MARKER}lock-{key}"


def _publish_locked_rename(tmp: Path, target: Path, lock_dir: Path) -> bool:
    """Rename ``tmp`` onto an absent ``target`` while holding a publish lock.

    The lock lives in the staging directory (the cache's ``tmp`` or a
    checkout's ``.corpus-fetch-tmp``), named by a hash of ``target``'s real,
    case-folded path, so a killed publisher never leaves a file inside a scope
    and two spellings of one target share one lock; every writer of one
    target stages in the same directory. The lock is held only for a check
    and a rename, so one older than ``PUBLISH_LOCK_STALE_SECONDS``, or one
    this process has waited on that long (a lock dated in the future by a
    skewed clock included), belongs to a process that died and is broken.
    Two processes breaking the same stale lock at once can both rename; the
    second then replaces the first's identical, verified bytes.
    """
    lock = publish_lock_path(target, lock_dir)
    waited_since = time.monotonic()
    while True:
        try:
            os.close(os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue
            if (
                age > PUBLISH_LOCK_STALE_SECONDS
                or time.monotonic() - waited_since > PUBLISH_LOCK_STALE_SECONDS
            ):
                lock.unlink(missing_ok=True)
                waited_since = time.monotonic()
            else:
                time.sleep(0.01)
    try:
        if os.path.lexists(target):
            return False
        os.rename(tmp, target)
        return True
    finally:
        lock.unlink(missing_ok=True)


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
        path = self.object_path(sha256)
        if not path.exists():
            return False
        if not self.contains(sha256, size):
            # Wrong size: a corrupt object, or a lock entry whose size is wrong.
            # Only the first is deleted; a good object stays for other users.
            if not self.verify_object(sha256):
                self._discard(sha256)
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
            return self._publish(tmp, target, sha256, size)
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
            return self._publish(tmp, target, actual_sha, actual_size)
        finally:
            tmp.unlink(missing_ok=True)

    def _publish(self, tmp: Path, target: Path, sha256: str, size: int) -> Path:
        """Publish a verified object once; never replace an existing one.

        Replacing an object while another thread cloned it made ``clonefile``
        fail with ENOENT. A losing writer keeps the winner when it verifies; a
        corrupt winner is removed and the verified copy published instead.
        """
        os.chmod(tmp, 0o444)
        target.parent.mkdir(parents=True, exist_ok=True)
        for _attempt in range(3):
            if publish_no_replace(tmp, target):
                with self._verified_lock:
                    self._verified.add(sha256)
                return target
            if self.usable(sha256, size):  # discards a corrupt winner
                return target
        raise ContentStoreError(f"cannot publish {sha256}: the cache keeps a conflicting object")

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
        """Stream one blob in chunks; the process is held until the stream ends.

        One ``cat-file`` process answers one blob at a time anyway, so streaming
        under the lock serializes nothing extra and keeps memory to one chunk.
        """
        if entry.git_blob is None:
            return None
        self._lock.acquire()
        try:
            proc = self._process()
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(entry.git_blob.encode("ascii") + b"\n")
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            if len(header) == 2 and header[1] == b"missing":
                self._lock.release()
                return None
            if len(header) != 3 or header[1] != b"blob":
                self.close()
                raise ContentStoreError(f"unexpected git cat-file reply for {entry.git_blob}")
        except BaseException:
            if self._lock.locked():
                self._lock.release()
            raise
        return self._stream(proc, int(header[2]), entry.git_blob)

    def _stream(self, proc: subprocess.Popen[bytes], size: int, oid: str) -> Iterator[bytes]:
        return _GitBlobChunks(self, proc, size, oid)

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


class _GitBlobChunks:
    """One blob streamed from the shared ``cat-file`` process.

    Holds the source's lock until the stream ends or is closed; closing early
    (even before the first read) drains the rest so the next request starts
    at a header, then releases the lock.
    """

    def __init__(self, source: GitBlobSource, proc: subprocess.Popen[bytes], size: int, oid: str):
        self._source = source
        self._proc = proc
        self._left = size
        self._oid = oid
        self._done = False

    def __iter__(self) -> _GitBlobChunks:
        return self

    def __next__(self) -> bytes:
        if self._done:
            raise StopIteration
        if not self._left:
            self.close()
            raise StopIteration
        assert self._proc.stdout is not None
        chunk: bytes = self._proc.stdout.read(min(self._left, CHUNK_SIZE))
        if not chunk:
            self._source.close()
            self._finish()
            raise ContentStoreError(f"truncated git cat-file output for {self._oid}")
        self._left -= len(chunk)
        return chunk

    def close(self) -> None:
        if self._done:
            return
        try:
            stdout = self._proc.stdout
            if stdout is not None and self._proc.poll() is None:
                while self._left:
                    chunk = stdout.read(min(self._left, CHUNK_SIZE))
                    if not chunk:
                        break
                    self._left -= len(chunk)
                if self._left or stdout.read(1) != b"\n":
                    self._source.close()
        finally:
            self._finish()

    def _finish(self) -> None:
        if not self._done:
            self._done = True
            self._source._lock.release()

    def __del__(self) -> None:
        self.close()


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


class _BodyChunks:
    """Chunks of an R2 response body; closing it closes the body even unread."""

    def __init__(self, body: Any):
        self._body = body
        self._closed = False

    def __iter__(self) -> _BodyChunks:
        return self

    def __next__(self) -> bytes:
        if self._closed:
            raise StopIteration
        chunk = self._body.read(CHUNK_SIZE)
        if not chunk:
            self.close()
            raise StopIteration
        return chunk if isinstance(chunk, bytes) else bytes(chunk)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            with suppress(Exception):
                self._body.close()


def _iter_body(body: Any) -> Iterator[bytes]:
    return _BodyChunks(body)


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
        except Exception as exc:  # noqa: BLE001 - a read error mid-body: try the next source
            _close(chunks)
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


_PRUNED_TMP_DIRS: set[Path] = set()
_PRUNE_LOCK = threading.Lock()
STALE_FETCH_TEMP_SECONDS = 24 * 3600


def _prune_stale_fetch_tmp(directory: Path) -> None:
    """Remove temporary files that interrupted fetches left more than a day ago."""
    with _PRUNE_LOCK:
        if directory in _PRUNED_TMP_DIRS:
            return
        _PRUNED_TMP_DIRS.add(directory)
    cutoff = time.time() - STALE_FETCH_TEMP_SECONDS
    with suppress(FileNotFoundError), os.scandir(directory) as entries:
        for item in entries:
            if FETCH_TEMP_MARKER in item.name and item.is_file(follow_symlinks=False):
                with suppress(FileNotFoundError):
                    stat = item.stat(follow_symlinks=False)
                    # A clone keeps the cache object's old mtime; ctime is when
                    # this file came to exist.
                    if max(stat.st_mtime, stat.st_ctime) < cutoff:
                        os.unlink(item.path)


def _fetch_tmp(repo: Path, target: Path) -> Path:
    """A temporary name for a file bound for ``target``: same filesystem, outside any scope."""
    directory = repo / FETCH_TEMP_DIR
    directory.mkdir(parents=True, exist_ok=True)
    _prune_stale_fetch_tmp(directory)
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


# (st_dev, st_ino, st_size, st_mtime_ns) of the file one call placed; a later
# write in place or a replacement changes at least one of them.
_Placed = tuple[int, int, int, int]


def _identity(path: Path) -> _Placed:
    stat = path.lstat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def materialize_entry(
    repo: Path,
    entry: LockEntry,
    cache: ContentCache | None,
    sources: Iterable[ObjectSource],
    *,
    force: bool = False,
    verify: bool = False,
) -> tuple[str, str | None, str | None]:
    """Place one locked file in the worktree (see ``_materialize_one``)."""
    state, source, method, _placed = _materialize_one(
        repo, entry, cache, sources, force=force, verify=verify
    )
    return state, source, method


def _materialize_one(
    repo: Path,
    entry: LockEntry,
    cache: ContentCache | None,
    sources: Iterable[ObjectSource],
    *,
    force: bool = False,
    verify: bool = False,
) -> tuple[str, str | None, str | None, _Placed | None]:
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
        return "present", None, None, None
    if state == "modified" and not force:
        return "modified", None, None, None
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
            return "modified", None, None, None
        placed = _identity(target)
    finally:
        tmp.unlink(missing_ok=True)
    return "materialized", source, method, placed


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
        except Exception as exc:  # noqa: BLE001 - a read error mid-body: try the next source
            _close(chunks)
            failures.append(f"{source.name}: {exc}")
    detail = "; ".join(failures) if failures else "no source holds it"
    raise ContentStoreError(
        f"cannot obtain {entry.path} (sha256 {entry.sha256}, {entry.size} bytes): {detail}"
    )


def _roll_back(
    repo: Path,
    report: FetchReport,
    created_by_scope: dict[tuple[str, str, str], list[tuple[LockEntry, _Placed | None]]],
    failed_scopes: set[tuple[str, str, str]],
) -> None:
    """Remove the files this call placed in each failed scope's ``sources/`` directory."""
    undone: set[str] = set()
    for scope in failed_scopes:
        for entry, placed in created_by_scope.get(scope, []):
            undone.add(entry.path)
            report.bytes_materialized -= entry.size
            target = repo / entry.path
            try:
                current = _identity(target)
            except FileNotFoundError:
                continue
            # Remove only the file this call placed, still holding the locked
            # bytes; anything written over it since (an extractor, another
            # fetch) stays. The content check covers an in-place rewrite of
            # the same size within one coarse timestamp tick.
            try:
                still_ours = (
                    placed is not None
                    and current == placed
                    and hash_path(target) == (entry.sha256, entry.size)
                )
            except FileNotFoundError:
                continue  # someone removed it meanwhile
            if still_ours:
                target.unlink(missing_ok=True)
                report.rolled_back.append(entry.path)
            else:
                report.modified.append(entry.path)
    if undone:
        report.materialized = [path for path in report.materialized if path not in undone]


_COMPLETE_STATES = frozenset({"present", "materialized", "modified"})
_Result = tuple[LockEntry, str, str | None, str | None, _Placed | None, str | None]


def _install_sigint_flag(event: threading.Event) -> Any:
    """On the main thread, make SIGINT set ``event`` instead of raising.

    Returns the previous handler to restore, or None when nothing changed
    (not the main thread, or SIGINT already ignored).
    """
    if threading.current_thread() is not threading.main_thread():
        return None
    try:
        previous = signal.getsignal(signal.SIGINT)
        if previous in (signal.SIG_IGN, None):
            return None
        signal.signal(signal.SIGINT, lambda _signum, _frame: event.set())
    except (ValueError, OSError):
        return None
    return previous


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

    Interruption is handled without asynchronous exceptions. On the main
    thread SIGINT only sets a flag; each worker logs its own outcome and the
    file it placed under a lock; and on an interrupt (or a progress callback
    that raises) queued work is cancelled, in-flight entries finish, and the
    rollback reads that log. So a Ctrl-C anywhere, or twice, leaves every
    ``sources/`` directory whole or rolled back before KeyboardInterrupt is
    raised.
    """
    entry_list = list(entries)
    source_list = list(sources)
    report = FetchReport()
    total = len(entry_list)

    log = threading.Condition()
    outcomes: dict[str, str] = {}  # path -> final state, written by the worker that ran it
    placed_log: list[tuple[LockEntry, _Placed]] = []
    inflight = 0
    stop = threading.Event()
    interrupted = threading.Event()
    results: queue.SimpleQueue[_Result] = queue.SimpleQueue()

    def one(entry: LockEntry) -> None:
        nonlocal inflight
        with log:
            if stop.is_set():
                return
            inflight += 1
        result: _Result = (entry, "failed", None, None, None, "interrupted")
        try:
            state, source, method, placed = _materialize_one(
                repo, entry, cache, source_list, force=force, verify=verify
            )
            result = (entry, state, source, method, placed, None)
        except Exception as exc:  # noqa: BLE001 - one entry's failure never stops the rest
            result = (entry, "failed", None, None, None, f"{type(exc).__name__}: {exc}")
        except BaseException as exc:  # an interrupt raised inside a worker: stop the run
            result = (entry, "failed", None, None, None, f"{type(exc).__name__}: {exc}")
            interrupted.set()
        finally:
            with log:
                outcomes[entry.path] = result[1]
                if result[1] == "materialized" and result[4] is not None:
                    placed_log.append((entry, result[4]))
                inflight -= 1
                log.notify_all()
            results.put(result)

    done = 0

    def record(result: _Result) -> None:
        nonlocal done
        entry, state, source, method, _placed, error = result
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

    def placements() -> dict[tuple[str, str, str], list[tuple[LockEntry, _Placed | None]]]:
        grouped: dict[tuple[str, str, str], list[tuple[LockEntry, _Placed | None]]] = {}
        with log:
            logged = list(placed_log)
        for entry, placed in logged:
            if (scope := _sources_scope(entry)) is not None:
                grouped.setdefault(scope, []).append((entry, placed))
        return grouped

    previous_handler = _install_sigint_flag(interrupted)
    pool = ThreadPoolExecutor(max_workers=max(1, workers))
    failure: BaseException | None = None
    try:
        submitted = 0
        received = 0
        try:
            for entry in entry_list:
                if interrupted.is_set():
                    break
                pool.submit(one, entry)
                submitted += 1
            while received < submitted and not interrupted.is_set():
                try:
                    result = results.get(timeout=0.1)
                except queue.Empty:
                    continue
                received += 1
                record(result)
        except BaseException as exc:  # a progress callback raised (Ctrl-C, broken pipe)
            failure = exc
        if failure is None and not interrupted.is_set():
            pool.shutdown(wait=True)
            failed_scopes = {
                scope
                for entry in entry_list
                if (scope := _sources_scope(entry)) is not None
                and outcomes.get(entry.path) == "failed"
            }
            _roll_back(repo, report, placements(), failed_scopes)
            report.present.sort()
            report.materialized.sort()
            return report
        # Interrupted: cancel queued work, let in-flight entries finish, then
        # roll back every sources/ directory this call left incomplete.
        stop.set()
        pool.shutdown(wait=False, cancel_futures=True)
        with log:
            while inflight:
                log.wait(timeout=1.0)
        incomplete = {
            scope
            for entry in entry_list
            if (scope := _sources_scope(entry)) is not None
            and outcomes.get(entry.path) not in _COMPLETE_STATES
        }
        _roll_back(repo, report, placements(), incomplete)
        pool.shutdown(wait=True)
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGINT, previous_handler)
    if failure is not None:
        raise failure
    raise KeyboardInterrupt


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
