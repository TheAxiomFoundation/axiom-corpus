"""Upload a signed ingest's locked corpus objects to R2 from CI.

An ingest pull request commits signed ingest manifests and lock files; the
bytes stay on the ingester's machine until ``corpus push`` uploads them, which
needs R2 write credentials there. This module lets a dispatched workflow on
``main`` do that upload instead (``.github/workflows/corpus-object-upload.yml``,
``docs/corpus-ci-upload.md``):

1. the ingester packs the changed lock entries' files into a tar archive whose
   members are named by sha256 (``pack_objects``) and attaches it to a draft
   release;
2. the workflow picks that one asset (``select_staged_asset``) and hands the
   archive to a job that holds the R2 write credentials;
3. that job reads the pull request's lock files and signed manifests from git
   as data (``build_upload_plan``), checks every archive member against the
   plan (``stage_archive``), and writes the objects (``execute_upload``).

Nothing here executes pull-request code, and nothing an archive names decides
where bytes go: an object's key comes from the sha256 its lock entry pins.
Every check fails closed with ``UploadRefusedError``.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
import subprocess
import tarfile
import unicodedata
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.content_store import R2ObjectStore, content_key
from axiom_corpus.corpus.corpus_locks import (
    LOCK_ROOT,
    LockEntry,
    ScopeKey,
    diff_lock_sets,
    load_locks_at_ref,
    scope_for_path,
)
from axiom_corpus.corpus.ingest_manifests import (
    INGEST_MANIFEST_PUBLIC_KEY_ENV,
    default_ingest_manifest_path,
    verify_ingest_manifest,
)

ARCHIVE_ASSET_NAME = "corpus-objects.tar"
PUBLIC_KEY_ENV = INGEST_MANIFEST_PUBLIC_KEY_ENV
RELEASE_TAG_PREFIX = "corpus-upload-pr-"

# One run uploads at most this much. A larger ingest is split over pull
# requests or pushed with ``corpus push`` by someone who holds the credentials.
MAX_OBJECTS = 5000
MAX_TOTAL_BYTES = 1536 * 1024 * 1024
# GitHub caps a release asset at 2 GiB. A tar adds a 512-byte header and up to
# 511 bytes of padding per member, and two zero blocks at the end.
MAX_ARCHIVE_BYTES = MAX_TOTAL_BYTES + MAX_OBJECTS * 1024 + 1024 * 1024

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_PR_NUMBER_RE = re.compile(r"[1-9][0-9]{0,8}")
_CHUNK = 1024 * 1024


# Every lock file a pull request may carry has exactly this shape. Anything
# else under the lock directory refuses the run before its name is printed.
_SCOPE_PART = r"[a-z0-9][a-z0-9._-]{0,255}"
_LOCK_PATH_RE = re.compile(
    re.escape(LOCK_ROOT.as_posix()) + rf"/{_SCOPE_PART}/{_SCOPE_PART}/{_SCOPE_PART}\.json"
)
_MAX_MESSAGE = 600


def clean_text(text: object, *, limit: int = _MAX_MESSAGE) -> str:
    """``text`` on one line with no control or format characters.

    Refusal messages quote pull-request data (paths, manifest fields, verifier
    output). On a runner a line that starts with ``::`` is a workflow command,
    so nothing from a pull request may start a line or carry a control
    character into the log or the job summary.
    """
    cleaned = "".join(
        "\ufffd" if unicodedata.category(ch)[0] == "C" or unicodedata.category(ch) in {"Zl", "Zp"}
        else ch
        for ch in str(text)
    )
    if len(cleaned) > limit:
        cleaned = cleaned[:limit] + "…"
    return cleaned


class UploadRefusedError(RuntimeError):
    """A check failed; nothing further is read or written."""

    def __init__(self, message: object):
        super().__init__(clean_text(message))


# --------------------------------------------------------------------------- plan


@dataclass(frozen=True)
class PlannedObject:
    """One distinct object the pull request's changed lock entries name."""

    sha256: str
    size: int
    paths: tuple[str, ...]

    @property
    def key(self) -> str:
        return content_key(self.sha256)


@dataclass(frozen=True)
class UploadPlan:
    """What one run may write, derived only from signed, committed data."""

    head_commit: str
    base_commit: str
    scopes: tuple[ScopeKey, ...]
    manifests: tuple[str, ...]
    entries: tuple[LockEntry, ...]
    objects: Mapping[str, PlannedObject]

    @property
    def total_bytes(self) -> int:
        return sum(planned.size for planned in self.objects.values())


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True)


def _resolve_commit(repo: Path, ref: str) -> str:
    result = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    commit = result.stdout.decode("ascii", errors="replace").strip()
    if result.returncode != 0 or not _COMMIT_RE.fullmatch(commit):
        raise UploadRefusedError(f"cannot resolve `{ref}` to a commit in this checkout")
    return commit


def require_ref_at(repo: Path, ref: str, commit: str) -> None:
    """Refuse unless ``ref`` resolves to exactly ``commit``."""
    if not _COMMIT_RE.fullmatch(commit):
        raise UploadRefusedError("the head must be a full 40-character lowercase commit id")
    actual = _resolve_commit(repo.resolve(), ref)
    if actual != commit:
        raise UploadRefusedError(
            f"the pull request is at {actual}, not the reviewed {commit}; review the new "
            "head and dispatch again"
        )


def _require_strict_lock_tree(repo: Path, commit: str) -> None:
    """Refuse a tree whose lock directory holds anything but canonical lock paths.

    Names are never printed: a path can carry newlines and ``::`` commands.
    """
    listed = _git(repo, "ls-tree", "-r", "-z", "--name-only", commit, "--", LOCK_ROOT.as_posix())
    if listed.returncode != 0:
        raise UploadRefusedError(f"cannot list the lock files of `{commit}`")
    bad = 0
    for raw in listed.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            path = raw.decode("ascii")
        except UnicodeDecodeError:
            bad += 1
            continue
        if not _LOCK_PATH_RE.fullmatch(path):
            bad += 1
    if bad:
        raise UploadRefusedError(
            f"{bad} path(s) under `{LOCK_ROOT.as_posix()}` at the head are not canonical "
            "lock file paths (<jurisdiction>/<document_class>/<version>.json)"
        )


def build_upload_plan(
    repo: Path,
    *,
    base_ref: str,
    head_commit: str,
    public_key: str | None,
    max_objects: int = MAX_OBJECTS,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> UploadPlan:
    """Derive the upload plan for ``head_commit`` against ``base_ref``.

    The plan lists the lock entries that are new or whose bytes changed since
    the merge base. Each of their scopes must have, at ``head_commit``, a
    signed ingest manifest at the scope's default path whose signature
    verifies and whose applied files equal the scope's lock, path for path
    and sha256 for sha256. Lock files and manifests are read from git objects;
    the pull request's tree is never checked out.
    """
    repo = repo.resolve()
    if not public_key or not public_key.strip():
        raise UploadRefusedError(
            f"{INGEST_MANIFEST_PUBLIC_KEY_ENV} is required to verify ingest manifests"
        )
    if not _COMMIT_RE.fullmatch(head_commit):
        raise UploadRefusedError("the head must be a full 40-character lowercase commit id")
    if _resolve_commit(repo, head_commit) != head_commit:
        raise UploadRefusedError(f"`{head_commit}` does not name a commit in this checkout")
    base_tip = _resolve_commit(repo, base_ref)
    merge_base = _git(repo, "merge-base", base_tip, head_commit)
    base_commit = merge_base.stdout.decode("ascii", errors="replace").strip()
    if merge_base.returncode != 0 or not _COMMIT_RE.fullmatch(base_commit):
        raise UploadRefusedError(f"`{head_commit}` shares no history with `{base_ref}`")

    _require_strict_lock_tree(repo, head_commit)
    try:
        head_locks = load_locks_at_ref(repo, head_commit)
        base_locks = load_locks_at_ref(repo, base_commit)
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        raise UploadRefusedError(f"cannot read corpus lock files: {exc}") from exc
    if head_locks.errors:
        raise UploadRefusedError(
            "corpus lock files at the head are invalid: " + "; ".join(head_locks.errors[:5])
        )
    if base_locks.errors:
        raise UploadRefusedError(
            "corpus lock files at the base are invalid: " + "; ".join(base_locks.errors[:5])
        )

    diff = diff_lock_sets(base_locks, head_locks)
    entries = list(diff.added) + [
        after for before, after in diff.changed if before.content != after.content
    ]
    if not entries:
        raise UploadRefusedError(
            f"`{head_commit}` adds or changes no lock entry since `{base_commit}`"
        )

    scopes: list[ScopeKey] = []
    for entry in entries:
        scope = scope_for_path(entry.path)
        if scope is None:  # LockEntry and CorpusLock already forbid this
            raise UploadRefusedError(f"lock entry lies in no scope: {entry.path}")
        if scope not in scopes:
            scopes.append(scope)
    scopes.sort()

    manifests: list[str] = []
    for scope in scopes:
        manifests.append(
            _require_signed_scope(
                repo,
                scope,
                head_commit=head_commit,
                public_key=public_key,
                lock_files={e.path: e.sha256 for e in head_locks.locks[scope].files},
            )
        )

    objects: dict[str, PlannedObject] = {}
    for entry in sorted(entries, key=lambda item: item.path):
        known = objects.get(entry.sha256)
        if known is None:
            objects[entry.sha256] = PlannedObject(entry.sha256, entry.size, (entry.path,))
        elif known.size != entry.size:
            raise UploadRefusedError(
                f"lock entries give sha256 {entry.sha256} two sizes: "
                f"{known.size} and {entry.size}"
            )
        else:
            objects[entry.sha256] = PlannedObject(
                known.sha256, known.size, (*known.paths, entry.path)
            )
    plan = UploadPlan(
        head_commit=head_commit,
        base_commit=base_commit,
        scopes=tuple(scopes),
        manifests=tuple(manifests),
        entries=tuple(sorted(entries, key=lambda item: item.path)),
        objects=objects,
    )
    if len(plan.objects) > max_objects:
        raise UploadRefusedError(
            f"the plan names {len(plan.objects)} objects; one run uploads at most {max_objects}"
        )
    if plan.total_bytes > max_total_bytes:
        raise UploadRefusedError(
            f"the plan names {plan.total_bytes:,} bytes; one run uploads at most "
            f"{max_total_bytes:,}"
        )
    return plan


def _require_signed_scope(
    repo: Path,
    scope: ScopeKey,
    *,
    head_commit: str,
    public_key: str,
    lock_files: Mapping[str, str],
) -> str:
    """Return the scope's manifest path once it is proven to equal the lock."""
    label = "/".join(scope)
    jurisdiction, document_class, version = scope
    manifest_path = default_ingest_manifest_path(
        jurisdiction=jurisdiction, document_class=document_class, version=version
    ).as_posix()
    shown = _git(repo, "show", f"{head_commit}:{manifest_path}")
    if shown.returncode != 0:
        raise UploadRefusedError(
            f"scope {label} has no ingest manifest at `{manifest_path}` in `{head_commit}`"
        )
    try:
        payload = json.loads(shown.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UploadRefusedError(f"`{manifest_path}` is not UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise UploadRefusedError(f"`{manifest_path}` is not a JSON object")
    named = (payload.get("jurisdiction"), payload.get("document_class"), payload.get("version"))
    if named != scope:
        raise UploadRefusedError(f"`{manifest_path}` is signed for another scope, not {label}")
    try:
        issues = verify_ingest_manifest(
            payload, public_key=public_key, repo=repo, head_ref=head_commit
        )
    except Exception as exc:  # noqa: BLE001 - any verifier failure refuses the scope
        raise UploadRefusedError(f"`{manifest_path}` could not be verified: {exc}") from exc
    if issues:
        raise UploadRefusedError(f"`{manifest_path}` failed verification: " + " ".join(issues))

    applied = payload.get("applied_files")
    if not isinstance(applied, list):
        raise UploadRefusedError(f"`{manifest_path}` has no applied_files list")
    signed: dict[str, str] = {}
    deleted: set[str] = set()
    for item in applied:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise UploadRefusedError(f"`{manifest_path}` has a malformed applied_files entry")
        path = item["path"]
        if path in signed or path in deleted:
            raise UploadRefusedError(f"`{manifest_path}` lists `{path}` twice")
        if item.get("deleted") is True:
            deleted.add(path)
            continue
        sha256 = item.get("sha256")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise UploadRefusedError(f"`{manifest_path}` gives `{path}` no valid sha256")
        signed[path] = sha256
    if signed != dict(lock_files):
        only_lock = sorted(set(lock_files) - set(signed))
        only_manifest = sorted(set(signed) - set(lock_files))
        differing = sorted(
            path for path in set(signed) & set(lock_files) if signed[path] != lock_files[path]
        )
        detail = "; ".join(
            f"{name}: {paths[0]}" + (f" (+{len(paths) - 1} more)" if len(paths) > 1 else "")
            for name, paths in (
                ("only in the lock", only_lock),
                ("only in the manifest", only_manifest),
                ("different sha256", differing),
            )
            if paths
        )
        raise UploadRefusedError(
            f"the lock for {label} does not equal its signed manifest `{manifest_path}`: {detail}"
        )
    return manifest_path


# --------------------------------------------------------------------------- archive


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def pack_objects(repo: Path, entries: Iterable[LockEntry], output: Path) -> dict[str, Any]:
    """Write ``entries``' worktree files into a tar whose members are sha256 names.

    Runs on the ingester's machine and needs no credentials. Each distinct
    object is stored once; every file is hashed against its lock entry first.
    """
    repo = repo.resolve()
    unique: dict[str, LockEntry] = {}
    for entry in sorted(entries, key=lambda item: item.path):
        unique.setdefault(entry.sha256, entry)
    if not unique:
        raise UploadRefusedError("no lock entries to pack")
    total = sum(entry.size for entry in unique.values())
    if len(unique) > MAX_OBJECTS or total > MAX_TOTAL_BYTES:
        raise UploadRefusedError(
            f"{len(unique)} objects, {total:,} bytes: one archive holds at most "
            f"{MAX_OBJECTS} objects and {MAX_TOTAL_BYTES:,} bytes"
        )
    sources: dict[str, Path] = {}
    for sha256, entry in unique.items():
        source = repo / entry.path
        try:
            mode = source.lstat().st_mode
        except OSError as exc:
            raise UploadRefusedError(f"cannot read {entry.path}: {exc}") from exc
        if not stat.S_ISREG(mode):
            raise UploadRefusedError(f"{entry.path} is not a regular file")
        if _sha256_file(source) != (entry.sha256, entry.size):
            raise UploadRefusedError(f"{entry.path} does not hold the bytes its lock entry pins")
        sources[sha256] = source
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for sha256 in sorted(sources):
            info = tarfile.TarInfo(name=sha256)
            info.size = unique[sha256].size
            info.mode = 0o644
            with sources[sha256].open("rb") as handle:
                archive.addfile(info, handle)
    archive_sha256, archive_size = _sha256_file(output)
    return {
        "archive": str(output),
        "archive_sha256": archive_sha256,
        "archive_bytes": archive_size,
        "objects": len(unique),
        "object_bytes": total,
    }


_BLOCK = 512
_ZERO_BLOCK = bytes(_BLOCK)


def _header_member(header: bytes) -> tuple[str, int]:
    """Name and size of one ustar header block, or refuse.

    Only what ``pack_objects`` writes is accepted: a POSIX ustar header for a
    regular file whose whole name sits in the name field and whose size is
    plain octal. PAX and GNU extension headers (long names, sparse maps, size
    overrides), links, directories and devices are refused, so no header can
    rename, resize or redirect the member that follows it.
    """
    if header[257:263] != b"ustar\0" or header[263:265] != b"00":
        raise UploadRefusedError("an archive header is not a POSIX ustar header")
    stored = header[148:156].rstrip(b" \0")
    expected = sum(header[:148]) + 8 * 0x20 + sum(header[156:])
    if not re.fullmatch(rb"[0-7]{1,7}", stored) or int(stored, 8) != expected:
        raise UploadRefusedError("an archive header has a wrong checksum")
    if header[156:157] not in (b"0", b"\0"):
        raise UploadRefusedError("an archive member is not a plain regular file")
    if header[345:500].strip(b"\0") or header[157:257].strip(b"\0"):
        raise UploadRefusedError("an archive member carries a name prefix or a link target")
    raw_name = header[:100].split(b"\0", 1)[0]
    if header[:100][len(raw_name) :].strip(b"\0"):
        raise UploadRefusedError("an archive member name has bytes after its end")
    name = raw_name.decode("ascii", errors="replace")
    if not _SHA256_RE.fullmatch(name):
        raise UploadRefusedError("an archive member is not named by a lowercase sha256")
    size_field = header[124:136].rstrip(b" \0")
    if not re.fullmatch(rb"[0-7]{1,11}", size_field):
        raise UploadRefusedError(f"archive member {name} has no plain octal size")
    return name, int(size_field, 8)


def _read_exact(handle: Any, count: int) -> bytes:
    data = handle.read(count)
    if len(data) != count:
        raise UploadRefusedError("the archive is truncated")
    return bytes(data)


def stage_archive(archive: Path, plan: UploadPlan, stage_dir: Path) -> dict[str, Path]:
    """Copy the archive's objects into ``stage_dir`` after checking each one.

    The archive is an uncompressed POSIX ustar file, parsed here block by
    block; nothing is extracted by name. A member is accepted only if it is a
    plain regular file, its name is exactly the sha256 of an object the plan
    names, it appears once, its recorded size equals the lock's, and its bytes
    hash to that sha256. Anything else refuses the whole archive: another
    name, a directory, a link, a device, a PAX or GNU extension header, a
    truncated file, or any non-zero byte after the end-of-archive marker
    (which is where a second, concatenated archive would sit). Staged files
    are named by the plan's sha256.
    """
    try:
        archive_stat = archive.lstat()
    except OSError as exc:
        raise UploadRefusedError(f"cannot read the archive: {exc}") from exc
    if not stat.S_ISREG(archive_stat.st_mode):
        raise UploadRefusedError("the archive is not a regular file")
    if archive_stat.st_size > MAX_ARCHIVE_BYTES:
        raise UploadRefusedError(
            f"the archive is {archive_stat.st_size:,} bytes; the limit is {MAX_ARCHIVE_BYTES:,}"
        )
    stage_dir.mkdir(parents=True, exist_ok=False)
    staged: dict[str, Path] = {}
    try:
        with archive.open("rb") as raw:
            while True:
                header = _read_exact(raw, _BLOCK)
                if header == _ZERO_BLOCK:
                    break
                name, size = _header_member(header)
                planned = plan.objects.get(name)
                if planned is None:
                    raise UploadRefusedError(
                        f"archive member {name} is not an object of the signed lock entries"
                    )
                if name in staged:
                    raise UploadRefusedError(f"archive member {name} appears twice")
                if size != planned.size:
                    raise UploadRefusedError(
                        f"archive member {name} is {size} bytes; its lock entry "
                        f"pins {planned.size}"
                    )
                target = stage_dir / planned.sha256
                digest = hashlib.sha256()
                remaining = planned.size
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    while remaining:
                        chunk = _read_exact(raw, min(_CHUNK, remaining))
                        digest.update(chunk)
                        handle.write(chunk)
                        remaining -= len(chunk)
                if digest.hexdigest() != planned.sha256:
                    raise UploadRefusedError(
                        f"archive member {name} does not hold the bytes its name and "
                        "lock entry pin"
                    )
                padding = -planned.size % _BLOCK
                if _read_exact(raw, padding).strip(b"\0"):
                    raise UploadRefusedError(f"archive member {name} has non-zero padding")
                staged[planned.sha256] = target
            # Past the end marker only zero fill may follow.
            for chunk in iter(lambda: raw.read(_CHUNK), b""):
                if chunk.strip(b"\0"):
                    raise UploadRefusedError(
                        "the archive holds data after its end-of-archive marker"
                    )
    except UploadRefusedError:
        raise
    except Exception as exc:  # noqa: BLE001 - any failure to parse refuses the archive
        raise UploadRefusedError(
            f"the archive could not be read: {type(exc).__name__}: {exc}"
        ) from exc
    return staged


# --------------------------------------------------------------------------- upload


@dataclass
class UploadResult:
    """Outcome per object; ``ok`` only when R2 verifiably holds every one."""

    uploaded: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failed

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "uploaded": sorted(self.uploaded),
            "already_present": sorted(self.already_present),
            "failed": dict(sorted(self.failed.items())),
        }


def _remote_holds(store: R2ObjectStore, planned: PlannedObject) -> bool:
    """True when R2 holds exactly the planned bytes under the content key.

    False when the key is absent. An object with other bytes raises: a
    content key must never hold them, and no run may paper over it.
    """
    chunks = store.open(LockEntry(path=planned.paths[0], sha256=planned.sha256, size=planned.size))
    if chunks is None:
        return False
    digest = hashlib.sha256()
    size = 0
    try:
        for chunk in chunks:
            size += len(chunk)
            if size > planned.size:
                break
            digest.update(chunk)
    finally:
        close = getattr(chunks, "close", None)
        if callable(close):
            close()
    if size != planned.size or digest.hexdigest() != planned.sha256:
        raise UploadRefusedError(
            f"R2 object {planned.key} exists with bytes that do not match its key"
        )
    return True


def execute_upload(
    plan: UploadPlan,
    staged: Mapping[str, Path],
    store: R2ObjectStore,
    *,
    workers: int = 8,
) -> UploadResult:
    """Write the staged objects, then report what R2 holds.

    Before any write, every planned object that the archive lacks must
    already be in R2 with exactly the pinned bytes; otherwise the run refuses.
    Writes are conditional (``IfNoneMatch: *``) with exact readback
    (``R2ObjectStore.put``): an object that exists is compared, never replaced.
    A second run with the same inputs writes nothing.
    """
    if store.legacy_path_keys:
        raise UploadRefusedError("the upload store must not read legacy path keys")
    unexpected = sorted(set(staged) - set(plan.objects))
    if unexpected:
        raise UploadRefusedError(f"staged object {unexpected[0]} is not in the plan")
    unstaged = [planned for sha256, planned in plan.objects.items() if sha256 not in staged]

    def probe(planned: PlannedObject) -> tuple[PlannedObject, bool]:
        return planned, _remote_holds(store, planned)

    result = UploadResult()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        try:
            probed = list(pool.map(probe, unstaged))
        except UploadRefusedError:
            raise
        except Exception as exc:  # noqa: BLE001 - an unreadable remote refuses the run
            raise UploadRefusedError(f"cannot read R2 to check for existing objects: {exc}") from exc
        missing = [planned for planned, present in probed if not present]
        if missing:
            shown = ", ".join(f"{planned.paths[0]} ({planned.sha256})" for planned in missing[:5])
            raise UploadRefusedError(
                f"{len(missing)} object(s) are neither in the archive nor in R2: {shown}"
            )
        result.already_present.extend(planned.sha256 for planned, _present in probed)

        def upload(sha256: str) -> tuple[str, bool | str]:
            planned = plan.objects[sha256]
            try:
                return sha256, store.put(staged[sha256], sha256=planned.sha256, size=planned.size)
            except Exception as exc:  # noqa: BLE001 - recorded; the run fails
                return sha256, clean_text(f"{type(exc).__name__}: {exc}")

        for sha256, outcome in pool.map(upload, sorted(staged)):
            if isinstance(outcome, str):
                result.failed[sha256] = outcome
            elif outcome:
                result.uploaded.append(sha256)
            else:
                result.already_present.append(sha256)
    return result


def render_summary(
    plan: UploadPlan | None,
    staged: Mapping[str, Path] | None,
    result: UploadResult | None,
    *,
    refusal: str | None = None,
    verify_only: bool = False,
) -> str:
    """Markdown for the job summary."""
    lines = ["### Corpus object upload", ""]
    if refusal is not None:
        lines += [
            "**Refused. Nothing was written by this step.**",
            "",
            f"<pre>{html.escape(clean_text(refusal), quote=True)}</pre>",
            "",
        ]
    if plan is not None:
        lines += [
            f"- Pull request head: `{plan.head_commit}`",
            f"- Merge base: `{plan.base_commit}`",
            f"- Scopes ({len(plan.scopes)}): "
            + ", ".join(f"`{'/'.join(scope)}`" for scope in plan.scopes),
            f"- Signed manifests verified: {len(plan.manifests)}",
            f"- Changed lock entries: {len(plan.entries)} "
            f"({len(plan.objects)} distinct objects, {plan.total_bytes:,} bytes)",
        ]
    if staged is not None and plan is not None:
        lines.append(f"- Objects in the archive: {len(staged)} of {len(plan.objects)}")
    if result is not None:
        lines += [
            f"- Uploaded: {len(result.uploaded)}",
            f"- Already in R2 with the same bytes: {len(result.already_present)}",
            f"- Failed: {len(result.failed)}",
        ]
        lines += [
            f"  - <code>{sha256}</code>: <code>{html.escape(clean_text(why), quote=True)}</code>"
            for sha256, why in sorted(result.failed.items())[:20]
        ]
        lines += ["", "**Every object is in R2.**" if result.ok else "**The upload failed.**"]
    elif refusal is None and verify_only:
        lines += ["", "Verification passed. This step holds no R2 credentials and wrote nothing."]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- staging


def release_tag_for(pr_number: str) -> str:
    if not _PR_NUMBER_RE.fullmatch(pr_number):
        raise UploadRefusedError("the pull request number must be a positive integer")
    return f"{RELEASE_TAG_PREFIX}{pr_number}"


@dataclass(frozen=True)
class StagedAsset:
    """The one release asset a run may download."""

    asset_id: int
    size: int
    release_id: int
    uploader: str


def select_staged_asset(releases: object, *, pr_number: str) -> StagedAsset:
    """Pick the archive for a pull request from the repository's release list.

    Exactly one release may carry the tag ``corpus-upload-pr-<number>``; it
    must be a draft (a draft has no git tag and is not public), and it must
    hold exactly one asset, named ``corpus-objects.tar``, fully uploaded and
    within the size limit. ``releases`` is the JSON GitHub's release list
    returned, as one list or a list of pages.
    """
    tag = release_tag_for(pr_number)
    if not isinstance(releases, list):
        raise UploadRefusedError("the release list is not a JSON list")
    flat: list[object] = []
    for item in releases:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    matches = [item for item in flat if isinstance(item, dict) and item.get("tag_name") == tag]
    if len(matches) != 1:
        raise UploadRefusedError(
            f"expected exactly one release tagged `{tag}`, found {len(matches)}"
        )
    release = matches[0]
    if release.get("draft") is not True:
        raise UploadRefusedError(f"release `{tag}` is not a draft")
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != 1 or not isinstance(assets[0], dict):
        count = len(assets) if isinstance(assets, list) else 0
        raise UploadRefusedError(f"release `{tag}` must hold exactly one asset, found {count}")
    asset = assets[0]
    if asset.get("name") != ARCHIVE_ASSET_NAME:
        raise UploadRefusedError(f"release `{tag}` asset must be named `{ARCHIVE_ASSET_NAME}`")
    if asset.get("state") != "uploaded":
        raise UploadRefusedError(f"release `{tag}` asset is not fully uploaded")
    asset_id, size, release_id = asset.get("id"), asset.get("size"), release.get("id")
    for label, value in (("asset id", asset_id), ("asset size", size), ("release id", release_id)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise UploadRefusedError(f"release `{tag}` has an invalid {label}")
    assert isinstance(asset_id, int) and isinstance(size, int) and isinstance(release_id, int)
    if size > MAX_ARCHIVE_BYTES:
        raise UploadRefusedError(
            f"release `{tag}` asset is {size:,} bytes; the limit is {MAX_ARCHIVE_BYTES:,}"
        )
    uploader = asset.get("uploader")
    login = uploader.get("login") if isinstance(uploader, dict) else None
    return StagedAsset(
        asset_id=asset_id,
        size=size,
        release_id=release_id,
        uploader=login if isinstance(login, str) else "unknown",
    )


def require_reviewed_pull_request(
    pull_request: object, *, repository: str, pr_number: str, head_commit: str
) -> None:
    """Refuse unless the pull request is open, from this repository, at ``head_commit``.

    ``pull_request`` is GitHub's JSON for the pull request. Fork-head pull
    requests already fail this repository's CI by design, and a closed or
    merged one has nothing left to unblock, so neither is served.
    """
    release_tag_for(pr_number)
    if not _COMMIT_RE.fullmatch(head_commit):
        raise UploadRefusedError("the head must be a full 40-character lowercase commit id")
    if not isinstance(pull_request, dict):
        raise UploadRefusedError("the pull request description is not a JSON object")
    if str(pull_request.get("number")) != pr_number:
        raise UploadRefusedError("the pull request description is for another number")
    if pull_request.get("state") != "open":
        raise UploadRefusedError(f"pull request #{pr_number} is not open")
    for side in ("head", "base"):
        branch = pull_request.get(side)
        repo = branch.get("repo") if isinstance(branch, dict) else None
        full_name = repo.get("full_name") if isinstance(repo, dict) else None
        if full_name != repository:
            raise UploadRefusedError(
                f"pull request #{pr_number} has its {side} branch outside {repository}"
            )
    head = pull_request["head"]
    if head.get("sha") != head_commit:
        raise UploadRefusedError(
            f"pull request #{pr_number} is not at the reviewed commit {head_commit}; "
            "review the new head and dispatch again"
        )
