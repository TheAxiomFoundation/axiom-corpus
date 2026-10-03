"""Signed ingest manifests and guards for generated corpus artifacts."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.metadata
import io
import json
import os
import re
import subprocess
import tempfile
from base64 import b64decode, b64encode
from binascii import Error as BinasciiError
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeGuard

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    LOCK_ROOT,
    PROTECTED_CORPUS_PREFIXES,
    HashedBlob,
    LockEntry,
    diff_lock_sets,
    hash_tree_blobs,
    iter_blob_contents,
    lands_on_lock_root,
    lands_on_protected_path,
    list_tree_blobs,
    load_locks,
    load_locks_at_ref,
)

INGEST_MANIFEST_SCHEMA_VERSION = "axiom-corpus/ingest-manifest/v1"
INGEST_MANIFEST_SIGNATURE_ALGORITHM = "ed25519"
INGEST_MANIFEST_KEY_ID = "axiom-corpus-ingest-v1"
INGEST_MANIFEST_PRIVATE_KEY_ENV = "AXIOM_CORPUS_INGEST_PRIVATE_KEY"
INGEST_MANIFEST_PUBLIC_KEY_ENV = "AXIOM_CORPUS_INGEST_PUBLIC_KEY"
INGEST_MANIFEST_ROOT = Path(".axiom") / "ingest-manifests"
TEXT_OFFICIAL_DOCUMENT_SUFFIXES = {
    ".csv",
    ".html",
    ".htm",
    ".json",
    ".jsonl",
    ".md",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
FULL_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class IngestGuardResult:
    """Result from checking changed corpus artifacts against ingest manifests."""

    repo: Path
    protected_changes: tuple[str, ...]
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    def to_mapping(self) -> dict[str, Any]:
        return {
            "repo": str(self.repo),
            "passed": self.passed,
            "protected_changes": list(self.protected_changes),
            "issues": list(self.issues),
        }


def build_ingest_manifest(
    *,
    repo: Path,
    base: Path,
    jurisdiction: str,
    document_class: str,
    version: str,
    command: str,
    applied_files: list[Path] | None = None,
    deleted_files: list[Path] | None = None,
    reasoning_logs: list[Path] | None = None,
) -> dict[str, Any]:
    """Build an unsigned ingest manifest for one corpus scope."""
    repo = repo.resolve()
    base = _resolve_under_repo(repo, base)
    git_metadata = _git_metadata(repo)
    provenance_issues = _git_provenance_issues(git_metadata)
    if provenance_issues:
        raise ValueError(
            "Cannot build an ingest manifest from non-canonical generator state: "
            + " ".join(provenance_issues)
        )
    deleted_files = deleted_files or []
    files = applied_files
    if files is None and not deleted_files:
        files = _infer_scope_artifacts(
            base=base,
            jurisdiction=jurisdiction,
            document_class=document_class,
            version=version,
        )
    if files is None:
        files = []
    if not files and not deleted_files:
        raise FileNotFoundError(
            f"No corpus artifacts found for {jurisdiction}/{document_class}/{version} under {base}."
        )
    coverage = _load_scope_coverage(
        base=base,
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=version,
    )
    manifest: dict[str, Any] = {
        "schema_version": INGEST_MANIFEST_SCHEMA_VERSION,
        "tool": "axiom-corpus-ingest signed ingest manifest",
        "axiom_corpus_version": _package_version(),
        "axiom_corpus_git": git_metadata,
        "generated_at": datetime.now(UTC).isoformat(),
        "jurisdiction": jurisdiction,
        "document_class": document_class,
        "version": version,
        "command": {"text": command},
        "coverage": coverage,
        "reasoning_logs": [
            _manifest_file_entry(repo, _resolve_under_repo(repo, path))
            for path in sorted(reasoning_logs or [])
        ],
        "applied_files": [
            _manifest_file_entry(repo, _resolve_under_repo(repo, path)) for path in sorted(files)
        ]
        + [
            _manifest_deleted_file_entry(repo, _resolve_under_repo(repo, path))
            for path in sorted(deleted_files)
        ],
    }
    return manifest


def sign_ingest_manifest(
    payload: dict[str, Any],
    *,
    private_key: str,
    key_id: str = INGEST_MANIFEST_KEY_ID,
) -> dict[str, Any]:
    """Return a copy of an ingest manifest with an Ed25519 signature."""
    signed = copy.deepcopy(payload)
    signed.pop("signature", None)
    provenance_issues = _manifest_git_provenance_issues(signed)
    if provenance_issues:
        raise ValueError(
            "Cannot sign an ingest manifest with non-canonical generator state: "
            + " ".join(provenance_issues)
        )
    signed["signature"] = {
        "algorithm": INGEST_MANIFEST_SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "value": _manifest_ed25519_signature(signed, private_key),
    }
    return signed


def verify_ingest_manifest(
    payload: dict[str, Any],
    *,
    public_key: str,
    repo: Path,
    head_ref: str,
) -> list[str]:
    """Return verification issues for a signed ingest manifest."""
    repo = repo.resolve()
    issues = _manifest_git_provenance_issues(payload)
    git_metadata = payload.get("axiom_corpus_git")
    commit = git_metadata.get("commit") if isinstance(git_metadata, dict) else None
    if _is_full_git_commit(commit) and not _git_commit_is_ancestor(
        repo,
        commit=commit,
        head_ref=head_ref,
    ):
        issues.append(
            f"`axiom_corpus_git.commit` `{commit}` is not an ancestor of guarded head `{head_ref}`."
        )
    if payload.get("schema_version") != INGEST_MANIFEST_SCHEMA_VERSION:
        issues.append("Unsupported ingest manifest schema version.")
    signature = payload.get("signature")
    if not isinstance(signature, dict):
        issues.append("Missing ingest manifest signature.")
        return issues
    if signature.get("algorithm") != INGEST_MANIFEST_SIGNATURE_ALGORITHM:
        issues.append("Unsupported ingest manifest signature algorithm.")
    actual = str(signature.get("value") or "")
    try:
        _verify_manifest_ed25519_signature(payload, public_key, actual)
    except ValueError as exc:
        issues.append(str(exc))
    except InvalidSignature:
        issues.append("Invalid ingest manifest signature.")
    return issues


def write_signed_ingest_manifest(
    *,
    repo: Path,
    manifest: dict[str, Any],
    private_key: str,
    output: Path | None = None,
    key_id: str = INGEST_MANIFEST_KEY_ID,
) -> Path:
    """Sign and write an ingest manifest."""
    repo = repo.resolve()
    signed = sign_ingest_manifest(manifest, private_key=private_key, key_id=key_id)
    manifest_path = output or default_ingest_manifest_path(
        jurisdiction=str(signed["jurisdiction"]),
        document_class=str(signed["document_class"]),
        version=str(signed["version"]),
    )
    manifest_path = _resolve_under_repo(repo, manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
    return manifest_path


def default_ingest_manifest_path(
    *,
    jurisdiction: str,
    document_class: str,
    version: str,
) -> Path:
    """Return the default repo-relative manifest path for one corpus scope."""
    return (
        INGEST_MANIFEST_ROOT
        / _safe_segment(jurisdiction)
        / _safe_segment(document_class)
        / f"{_safe_segment(version)}.json"
    )


def guard_ingested_artifacts(
    *,
    repo: Path,
    base_ref: str | None = None,
    head_ref: str | None = "HEAD",
    public_key: str | None = None,
    content_reader: ContentReader | None = None,
) -> IngestGuardResult:
    """Check changed generated corpus artifacts against signed manifests.

    Protected artifacts reach a commit either as tracked git files or as
    entries in ``.axiom/corpus-locks`` (see ``docs/corpus-storage.md``). A
    changed tracked file or lock entry needs a valid signed ingest manifest
    carrying the same path and sha256, except a file that moves out of git
    into a lock with its bytes unchanged.
    """
    repo = repo.resolve()
    public_key = public_key or os.environ.get(INGEST_MANIFEST_PUBLIC_KEY_ENV)
    try:
        changes = _changed_paths(repo=repo, base_ref=base_ref, head_ref=head_ref)
    except (subprocess.CalledProcessError, UnicodeDecodeError, ValueError) as exc:
        return IngestGuardResult(
            repo=repo,
            protected_changes=(),
            issues=(f"Unable to read changed paths: {exc}",),
        )
    if not base_ref:
        # Worktree mode diffs against HEAD, which misses lock files never staged.
        changes = changes + _untracked_lock_changes(repo)
    protected = tuple(path for path in changes if _is_protected_corpus_artifact(path.path))
    if not changes:
        return IngestGuardResult(repo=repo, protected_changes=(), issues=())

    read_ref = (head_ref or "HEAD") if base_ref else None
    baseline_ref = base_ref or "HEAD"
    try:
        manifests = _load_ingest_manifests(repo, ref=read_ref)
        baseline_manifests = _load_ingest_manifests(repo, ref=baseline_ref)
    except ValueError as exc:
        return IngestGuardResult(
            repo=repo,
            protected_changes=tuple(change.path for change in protected),
            issues=(str(exc),),
        )
    # Changed paths come from ``base...head`` (the merge-base), so locks and
    # base blobs are compared against the same commit.
    try:
        lock_baseline = _merge_base(repo, base_ref, head_ref or "HEAD") if base_ref else "HEAD"
    except (subprocess.CalledProcessError, ValueError) as exc:
        return IngestGuardResult(
            repo=repo,
            protected_changes=tuple(change.path for change in protected),
            issues=(f"Unable to find the merge base of `{base_ref}` and the head: {exc}",),
        )
    lock_check = _LockCheck.load(
        repo,
        base_ref=lock_baseline,
        head_ref=read_ref,
        changes=changes,
    )
    variant_locks = [
        change.path
        for change in changes
        if change.status != "D"
        and lands_on_lock_root(change.path)
        and not change.path.startswith(f"{LOCK_ROOT.as_posix()}/")
    ]
    if lock_check.load_error is not None:
        return IngestGuardResult(
            repo=repo,
            protected_changes=tuple(change.path for change in protected),
            issues=(lock_check.load_error,),
        )
    entries_by_path: dict[str, tuple[Path, dict[str, Any], dict[str, Any]]] = {}
    reasoning_manifests_by_path: dict[str, set[Path]] = {}
    for manifest_path, payload in manifests.items():
        for entry in payload.get("applied_files", []):
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if isinstance(path, str) and path:
                entries_by_path[path] = (manifest_path, payload, entry)
        for path in _reasoning_log_paths(payload):
            reasoning_manifests_by_path.setdefault(path, set()).add(manifest_path)

    baseline_reasoning_manifests_by_path: dict[str, set[Path]] = {}
    for manifest_path, payload in baseline_manifests.items():
        for path in _reasoning_log_paths(payload):
            baseline_reasoning_manifests_by_path.setdefault(path, set()).add(manifest_path)

    changed_reasoning_paths_by_manifest: dict[Path, set[str]] = {}
    for change in changes:
        manifest_paths = reasoning_manifests_by_path.get(change.path, set()) | (
            baseline_reasoning_manifests_by_path.get(change.path, set())
        )
        for manifest_path in manifest_paths:
            changed_reasoning_paths_by_manifest.setdefault(manifest_path, set()).add(change.path)

    changed_manifest_paths = {
        Path(change.path)
        for change in changes
        if change.path.startswith(f"{INGEST_MANIFEST_ROOT.as_posix()}/")
        and change.path.endswith(".json")
    }
    for manifest_path in changed_manifest_paths:
        candidate_payload = manifests.get(manifest_path, {})
        baseline_payload = baseline_manifests.get(manifest_path, {})
        attested_paths = _reasoning_log_paths(candidate_payload) | _reasoning_log_paths(
            baseline_payload
        )
        if attested_paths:
            changed_reasoning_paths_by_manifest.setdefault(manifest_path, set()).update(
                attested_paths
            )
    changed_reasoning_manifests = set(changed_reasoning_paths_by_manifest)
    protected_paths = tuple(change.path for change in protected) + lock_check.changed_entry_paths
    if (
        not protected
        and not changed_reasoning_manifests
        and not lock_check.touched
        and not lock_check.issues
        and not variant_locks
    ):
        return IngestGuardResult(repo=repo, protected_changes=(), issues=())
    if not public_key:
        return IngestGuardResult(
            repo=repo,
            protected_changes=protected_paths,
            issues=(
                f"{INGEST_MANIFEST_PUBLIC_KEY_ENV} is required to verify corpus ingest manifests.",
            ),
        )

    manifest_issues: dict[Path, list[str]] = {}

    def verification_issues(
        manifest_path: Path,
        payload: dict[str, Any],
    ) -> list[str]:
        if manifest_path not in manifest_issues:
            manifest_issues[manifest_path] = verify_ingest_manifest(
                payload,
                public_key=public_key,
                repo=repo,
                head_ref=head_ref or "HEAD",
            )
        return manifest_issues[manifest_path]

    issues: list[str] = list(lock_check.issues)
    issues.extend(
        f"`{path}` is a lock file under another spelling of `{LOCK_ROOT.as_posix()}`; "
        "case-insensitive filesystems read it as the lock directory, but the guard "
        "never checks it."
        for path in variant_locks
    )
    authorizing_manifests: set[Path] = set()
    for change in protected:
        if change.path in lock_check.moved:
            # Tracked file left git for a lock entry holding its exact bytes.
            continue
        if lock_check.lock_mode and change.status != "D":
            issues.append(
                f"`{change.path}` is a corpus artifact tracked in git while "
                f"`{LOCK_ROOT.as_posix()}` exists; corpus bytes enter through lock files "
                "only. Run `axiom-corpus-ingest sign-ingest-manifest ... --lock`."
            )
            continue
        manifest_entry = entries_by_path.get(change.path)
        if manifest_entry is None:
            issues.append(
                f"Unmanifested corpus artifact change: `{change.path}`. "
                "Run `axiom-corpus-ingest sign-ingest-manifest` for the scope."
            )
            continue
        manifest_path, _payload, entry = manifest_entry
        authorizing_manifests.add(manifest_path)
        current_manifest_issues = verification_issues(manifest_path, _payload)
        if current_manifest_issues:
            for issue in current_manifest_issues:
                issues.append(f"{manifest_path.as_posix()}: {issue}")
            continue
        if change.status == "D":
            if entry.get("deleted") is not True:
                issues.append(
                    f"`{change.path}` is deleted but its ingest manifest does not mark it deleted."
                )
            continue
        actual_sha = _artifact_sha(repo, change.path, ref=read_ref)
        if actual_sha is None:
            issues.append(f"Manifested corpus artifact is missing: `{change.path}`.")
            continue
        expected_sha = str(entry.get("sha256") or "")
        if actual_sha != expected_sha:
            issues.append(
                f"`{change.path}` sha256 does not match ingest manifest "
                f"`{manifest_path.as_posix()}`."
            )
            continue
        issues.extend(_artifact_content_issues(repo, change.path, ref=read_ref))

    reader = content_reader
    to_read: list[LockEntry] = []
    for lock_entry in lock_check.to_attest:
        manifest_entry = entries_by_path.get(lock_entry.path)
        if manifest_entry is None:
            issues.append(
                f"Unmanifested corpus lock entry: `{lock_entry.path}`. "
                "Run `axiom-corpus-ingest sign-ingest-manifest` for the scope."
            )
            continue
        manifest_path, _payload, entry = manifest_entry
        authorizing_manifests.add(manifest_path)
        current_manifest_issues = verification_issues(manifest_path, _payload)
        if current_manifest_issues:
            for issue in current_manifest_issues:
                issues.append(f"{manifest_path.as_posix()}: {issue}")
            continue
        if entry.get("deleted") is True or str(entry.get("sha256") or "") != lock_entry.sha256:
            issues.append(
                f"`{lock_entry.path}` lock sha256 does not match ingest manifest "
                f"`{manifest_path.as_posix()}`."
            )
            continue
        to_read.append(lock_entry)
    if to_read:
        issues.extend(_locked_content_issues(repo, to_read, reader))

    for lock_entry in lock_check.removed:
        manifest_entry = entries_by_path.get(lock_entry.path)
        if manifest_entry is None or manifest_entry[2].get("deleted") is not True:
            issues.append(
                f"`{lock_entry.path}` was removed from its lock but no signed ingest "
                "manifest marks it deleted."
            )
            continue
        manifest_path, _payload, _entry = manifest_entry
        authorizing_manifests.add(manifest_path)
        for issue in verification_issues(manifest_path, _payload):
            issues.append(f"{manifest_path.as_posix()}: {issue}")

    for manifest_path in sorted(authorizing_manifests | changed_reasoning_manifests):
        current_payload = manifests.get(manifest_path)
        if current_payload is None:
            changed_paths = sorted(changed_reasoning_paths_by_manifest.get(manifest_path, set()))
            issues.append(
                f"{manifest_path.as_posix()}: signed manifest was removed while its "
                f"reasoning log changed: {changed_paths}."
            )
            continue
        current_manifest_issues = verification_issues(manifest_path, current_payload)
        if current_manifest_issues:
            for issue in current_manifest_issues:
                issues.append(f"{manifest_path.as_posix()}: {issue}")
            continue
        for issue in _reasoning_log_issues(repo, current_payload, ref=read_ref):
            issues.append(f"{manifest_path.as_posix()}: {issue}")
        current_reasoning_paths = _reasoning_log_paths(current_payload)
        for path in sorted(changed_reasoning_paths_by_manifest.get(manifest_path, set())):
            if path not in current_reasoning_paths:
                issues.append(
                    f"{manifest_path.as_posix()}: reasoning log `{path}` is no longer "
                    "attested after a related log or manifest change."
                )

    return IngestGuardResult(
        repo=repo,
        protected_changes=protected_paths,
        issues=tuple(dict.fromkeys(issues)),
    )


ContentReader = Callable[[LockEntry], bytes | None]


GUARD_READ_WORKERS = 8
GUARD_READ_BATCH = 32


def _locked_content_issues(
    repo: Path, entries: list[LockEntry], reader: ContentReader | None
) -> list[str]:
    """Run the content checks on locked bytes, reading them concurrently.

    Reads go to R2 for new ingests, so they run in parallel; batches keep at
    most ``GUARD_READ_BATCH`` files in memory, and issues keep entry order.
    """
    read = reader or default_content_reader(repo)

    def read_one(entry: LockEntry) -> tuple[bytes | None, str]:
        try:
            return read(entry), ""
        except Exception as exc:  # noqa: BLE001 - any failure to read fails closed
            return None, f": {exc}"

    issues: list[str] = []
    with ThreadPoolExecutor(max_workers=GUARD_READ_WORKERS) as pool:
        for start in range(0, len(entries), GUARD_READ_BATCH):
            batch = entries[start : start + GUARD_READ_BATCH]
            for entry, (payload_bytes, read_error) in zip(
                batch, pool.map(read_one, batch), strict=True
            ):
                if payload_bytes is None:
                    issues.append(
                        f"Cannot read the locked bytes of `{entry.path}` (sha256 "
                        f"{entry.sha256}) from the worktree, cache, git or R2{read_error}. "
                        "Upload them with `axiom-corpus-ingest corpus push`."
                    )
                    continue
                issues.extend(_content_issues(entry.path, payload_bytes))
    return issues


def default_content_reader(repo: Path) -> ContentReader:
    """Read locked bytes from the worktree, the shared cache, git objects, or R2."""
    from axiom_corpus.corpus.content_store import (
        ContentCache,
        ContentStoreError,
        GitBlobSource,
        ObjectSource,
        R2ObjectStore,
        read_entry_bytes,
    )

    cache = ContentCache()
    sources: list[ObjectSource] = [GitBlobSource(repo)]
    with contextlib.suppress(RuntimeError):  # no R2 credentials: git and cache only
        sources.append(R2ObjectStore.from_environment())

    def read(entry: LockEntry) -> bytes | None:
        try:
            return read_entry_bytes(repo, entry, cache, sources)
        except ContentStoreError:
            return None

    return read


@dataclass(frozen=True)
class _LockCheck:
    """Lock-file facts one guard run needs, computed once."""

    lock_mode: bool = False
    touched: bool = False
    moved: frozenset[str] = frozenset()
    to_attest: tuple[LockEntry, ...] = ()
    removed: tuple[LockEntry, ...] = ()
    issues: tuple[str, ...] = ()
    load_error: str | None = None

    @property
    def changed_entry_paths(self) -> tuple[str, ...]:
        return tuple(entry.path for entry in (*self.to_attest, *self.removed))

    @classmethod
    def load(
        cls,
        repo: Path,
        *,
        base_ref: str,
        head_ref: str | None,
        changes: tuple[_ChangedPath, ...],
    ) -> _LockCheck:
        lock_prefix = f"{LOCK_ROOT.as_posix()}/"
        lock_files_changed = any(change.path.startswith(lock_prefix) for change in changes)
        deleted_protected = {
            change.path
            for change in changes
            if change.status == "D" and _is_protected_corpus_artifact(change.path)
        }
        try:
            head = load_locks_at_ref(repo, head_ref) if head_ref else load_locks(repo)
            base = load_locks_at_ref(repo, base_ref)
        except (subprocess.CalledProcessError, OSError, ValueError) as exc:
            return cls(load_error=f"Unable to read corpus lock files: {exc}")
        if not head and not base and not head.errors:
            return cls()

        # A lock file that fails to parse would otherwise hide its entries.
        issues: list[str] = list(head.errors)
        lock_mode = bool(head) or bool(head.errors)
        if lock_mode:
            # Tracked files this diff adds or modifies are reported one by one by
            # the guard loop; this catches the ones already tracked at the base.
            changed_here = {change.path for change in changes if change.status != "D"}
            tracked = [
                path for path in _tracked_protected_paths(repo, head_ref) if path not in changed_here
            ]
            if tracked:
                shown = ", ".join(f"`{path}`" for path in tracked[:10])
                issues.append(
                    f"{len(tracked)} protected corpus file(s) are tracked in git while "
                    f"`{LOCK_ROOT.as_posix()}` exists; corpus bytes enter through lock files "
                    f"only. Run `axiom-corpus-ingest corpus migrate`. First: {shown}."
                )

        moved: set[str] = set()
        candidates = sorted(path for path in deleted_protected if path in head.by_path)
        if candidates:
            try:
                base_blobs = _base_blobs(repo, base_ref, candidates)
            except (subprocess.CalledProcessError, ValueError) as exc:
                return cls(load_error=f"Unable to read base corpus blobs: {exc}")
            for path in candidates:
                entry = head.by_path[path]
                blob = base_blobs.get(path)
                if blob is None:
                    issues.append(f"`{path}` is locked but was not tracked at `{base_ref}`.")
                elif (
                    entry.sha256 != blob.sha256
                    or entry.size != blob.size
                    or (entry.git_blob is not None and entry.git_blob != blob.oid)
                ):
                    issues.append(
                        f"`{path}` left git for a lock entry that does not match its "
                        f"tracked blob {blob.oid} (sha256 {blob.sha256}, {blob.size} bytes)."
                    )
                else:
                    moved.add(path)

        diff = diff_lock_sets(base, head)
        to_attest: list[LockEntry] = []
        new_blob_refs: list[LockEntry] = []
        for entry in diff.added:
            if entry.path in moved:
                continue
            to_attest.append(entry)
            if entry.git_blob is not None:
                new_blob_refs.append(entry)
        for before, after in diff.changed:
            if before.content != after.content:
                to_attest.append(after)
            if after.git_blob is not None and (
                after.git_blob != before.git_blob or after.content != before.content
            ):
                new_blob_refs.append(after)
        issues.extend(_git_blob_reference_issues(repo, new_blob_refs))

        tracked_at_head = set(_tracked_protected_paths(repo, head_ref)) if diff.removed else set()
        removed = [
            entry
            for entry in diff.removed
            # Moving a file back into git (only possible once no locks remain)
            # is checked as a tracked-file addition by the main guard loop.
            if not (not lock_mode and entry.path in tracked_at_head)
        ]
        touched = lock_files_changed or bool(candidates) or not diff.is_empty
        return cls(
            lock_mode=lock_mode,
            touched=touched,
            moved=frozenset(moved),
            to_attest=tuple(to_attest),
            removed=tuple(removed),
            issues=tuple(issues),
        )


def _tracked_protected_paths(repo: Path, head_ref: str | None) -> list[str]:
    """Tracked paths under a protected prefix, compared case-insensitively.

    On a case-insensitive filesystem ``data/corpus/Provisions/x`` lands on the
    locked path, so every spelling counts.
    """
    # No pathspec: git matches pathspecs case-sensitively, so ``data`` would
    # miss ``DATA/corpus/...``. List everything and fold case here.
    command = (
        ["git", "ls-tree", "-r", "--name-only", "-z", head_ref]
        if head_ref
        else ["git", "ls-files", "-z", "--cached"]
    )
    result = subprocess.run(command, cwd=repo, check=True, capture_output=True)
    tracked = {raw.decode("utf-8", errors="surrogateescape") for raw in result.stdout.split(b"\0") if raw}
    return sorted(path for path in tracked if _is_protected_corpus_artifact(path))


def _untracked_lock_changes(repo: Path) -> tuple[_ChangedPath, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--others", "--exclude-standard", "--", LOCK_ROOT.as_posix()],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return tuple(
        _ChangedPath(status="A", path=os.fsdecode(raw))
        for raw in result.stdout.split(b"\0")
        if raw
    )


def _merge_base(repo: Path, base_ref: str, head_ref: str) -> str:
    result = subprocess.run(
        ["git", "merge-base", base_ref, head_ref],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if not _is_full_git_commit(commit):
        raise ValueError(f"unexpected merge-base output {commit!r}")
    return commit


def _base_blobs(repo: Path, base_ref: str, paths: list[str]) -> dict[str, HashedBlob]:
    wanted = set(paths)
    prefixes = [prefix.rstrip("/") for prefix in PROTECTED_CORPUS_PREFIXES]
    blobs = [blob for blob in list_tree_blobs(repo, base_ref, *prefixes) if blob.path in wanted]
    return hash_tree_blobs(repo, blobs)


def _git_blob_reference_issues(repo: Path, entries: list[LockEntry]) -> list[str]:
    """A lock entry's ``git_blob`` must name a local blob holding exactly its bytes."""
    if not entries:
        return []
    oids = sorted({entry.git_blob for entry in entries if entry.git_blob})
    check = subprocess.run(
        ["git", "cat-file", "--batch-check"],
        cwd=repo,
        input="".join(f"{oid}\n" for oid in oids).encode("ascii"),
        capture_output=True,
        check=False,
    )
    present: dict[str, int] = {}
    for line in check.stdout.decode("ascii", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            present[parts[0]] = int(parts[2])
    digests: dict[str, str] = {}
    for oid, chunks in iter_blob_contents(repo, sorted(present)):
        digest = hashlib.sha256()
        for chunk in chunks:
            digest.update(chunk)
        digests[oid] = digest.hexdigest()
    issues: list[str] = []
    for entry in entries:
        oid = entry.git_blob or ""
        if oid not in present:
            issues.append(f"`{entry.path}` names git_blob {oid}, which this repository lacks.")
        elif present[oid] != entry.size or digests.get(oid) != entry.sha256:
            issues.append(f"`{entry.path}` names git_blob {oid}, whose bytes differ from the lock.")
    return issues


def audit_lock_attestation(
    repo: Path,
    *,
    ref: str = "HEAD",
    public_key: str | None = None,
) -> list[str]:
    """Check every lock entry at ``ref``, not just the ones a diff changed.

    An entry passes when a valid signed ingest manifest at ``ref`` attests its
    path and sha256, or when its ``git_blob`` holds exactly its bytes and a
    commit on ``ref``'s first-parent history held that blob at that path (see
    ``first_parent_path_blobs``). The guard checks lock changes against the
    base; this also covers lock files that reached a base the guard never
    checked.
    """
    repo = repo.resolve()
    public_key = public_key or os.environ.get(INGEST_MANIFEST_PUBLIC_KEY_ENV)
    if not public_key:
        return [f"{INGEST_MANIFEST_PUBLIC_KEY_ENV} is required to audit corpus locks."]
    locks = load_locks_at_ref(repo, ref)
    issues = list(locks.errors)
    # A lock file under another spelling of the lock root is read as a lock on
    # case-insensitive checkouts but never by the guard; flag any already there.
    tracked = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", ref],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    issues.extend(
        f"`{path}` is a lock file under another spelling of `{LOCK_ROOT.as_posix()}`."
        for path in (raw.decode("utf-8", errors="surrogateescape") for raw in tracked if raw)
        if lands_on_lock_root(path) and not path.startswith(f"{LOCK_ROOT.as_posix()}/")
    )
    if not locks:
        return issues
    manifests = _load_ingest_manifests(repo, ref=ref)
    attestations: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for manifest_path, payload in manifests.items():
        for entry in payload.get("applied_files", []):
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                attestations.setdefault(entry["path"], []).append((manifest_path, entry))
    verdicts: dict[Path, bool] = {}

    def manifest_valid(manifest_path: Path) -> bool:
        if manifest_path not in verdicts:
            verdicts[manifest_path] = not verify_ingest_manifest(
                manifests[manifest_path], public_key=public_key, repo=repo, head_ref=ref
            )
        return verdicts[manifest_path]

    unattested: list[LockEntry] = []
    for lock_entry in locks.entries():
        attested = any(
            entry.get("deleted") is not True
            and entry.get("sha256") == lock_entry.sha256
            and manifest_valid(manifest_path)
            for manifest_path, entry in attestations.get(lock_entry.path, [])
        )
        if not attested:
            unattested.append(lock_entry)
    with_blob = [entry for entry in unattested if entry.git_blob]
    issues.extend(
        f"`{entry.path}` has neither a signed ingest manifest nor a git blob attesting it."
        for entry in unattested
        if not entry.git_blob
    )
    issues.extend(_git_blob_reference_issues(repo, with_blob))
    wanted: dict[str, set[str]] = {}
    for entry in with_blob:
        wanted.setdefault(entry.path, set()).add(entry.git_blob or "")
    try:
        held = first_parent_path_blobs(repo, ref, wanted)
    except (subprocess.CalledProcessError, OSError) as exc:
        issues.append(f"Unable to read the first-parent history of `{ref}`: {exc}")
        return list(dict.fromkeys(issues))
    issues.extend(
        f"`{entry.path}` names git_blob {entry.git_blob}, which no commit on the "
        f"first-parent history of `{ref}` held at that path."
        for entry in with_blob
        if (entry.path, entry.git_blob) not in held
    )
    return list(dict.fromkeys(issues))


_NULL_OID = "0" * 40


def first_parent_path_blobs(
    repo: Path, ref: str, wanted: dict[str, set[str]]
) -> set[tuple[str, str]]:
    """The ``(path, blob)`` pairs in ``wanted`` that a tree on ``ref``'s first-parent chain held.

    Only the first-parent chain counts: with merge commits only, that is the
    sequence of states the base branch itself held, so bytes a pull request
    committed and removed again before merging never qualify. Each commit is
    diffed against its first parent, and both sides of a change are states of
    the chain; the walk stops once every wanted pair is found (a migration
    commit's deletions name them all at once).
    """
    remaining = {(path, oid) for path, oids in wanted.items() for oid in oids}
    found: set[tuple[str, str]] = set()
    if not remaining:
        return found
    command = [
        "git", "-c", "log.showSignature=false", "log", "--first-parent",
        "--diff-merges=first-parent", "--root", "--raw", "--no-renames", "--no-abbrev",
        "-z", "--format=", ref, "--", CORPUS_BASE,
    ]  # fmt: skip
    # stderr goes to a file: an undrained pipe could block git while stdout is read.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, cwd=repo, stdout=subprocess.PIPE, stderr=errors)
        assert process.stdout is not None
        stopped_early = False
        pending = b""
        header: list[str] | None = None
        try:
            while remaining:
                chunk = process.stdout.read(1 << 20)
                if not chunk:
                    break
                tokens = (pending + chunk).split(b"\0")
                pending = tokens.pop()
                for token in tokens:
                    if header is None:
                        text = token.lstrip(b"\n").decode("ascii", errors="replace")
                        if text.startswith(":"):
                            header = text[1:].split()
                        continue
                    path = token.decode("utf-8", errors="surrogateescape")
                    for oid in header[2:4] if len(header) >= 4 else ():
                        if oid != _NULL_OID and (path, oid) in remaining:
                            remaining.discard((path, oid))
                            found.add((path, oid))
                    header = None
            stopped_early = not remaining
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()
        errors.seek(0)
        stderr = errors.read()
    if not stopped_early and process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, command, stderr=stderr.decode("utf-8", errors="replace")
        )
    return found


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a local file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    """Return the SHA-256 digest for bytes."""
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class _ChangedPath:
    status: str
    path: str


def _canonical_manifest_bytes(payload: dict[str, Any]) -> bytes:
    unsigned = copy.deepcopy(payload)
    unsigned.pop("signature", None)
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _manifest_ed25519_signature(payload: dict[str, Any], private_key: str) -> str:
    key = _load_ed25519_private_key(private_key)
    signature = key.sign(_canonical_manifest_bytes(payload))
    return b64encode(signature).decode("ascii")


def _verify_manifest_ed25519_signature(
    payload: dict[str, Any], public_key: str, signature: str
) -> None:
    key = _load_ed25519_public_key(public_key)
    try:
        signature_bytes = b64decode(signature.encode("ascii"), validate=True)
    except (BinasciiError, UnicodeEncodeError) as exc:
        raise ValueError("Invalid ingest manifest signature encoding.") from exc
    key.verify(signature_bytes, _canonical_manifest_bytes(payload))


def _load_ed25519_private_key(private_key: str) -> Ed25519PrivateKey:
    text = private_key.strip().replace("\\n", "\n")
    if text.startswith("-----BEGIN "):
        loaded = serialization.load_pem_private_key(
            text.encode("utf-8"),
            password=None,
        )
        if not isinstance(loaded, Ed25519PrivateKey):
            raise ValueError("Ingest manifest private key must be Ed25519.")
        return loaded
    raw = _load_raw_key_bytes(text, expected_length=32, kind="private")
    return Ed25519PrivateKey.from_private_bytes(raw)


def _load_ed25519_public_key(public_key: str) -> Ed25519PublicKey:
    text = public_key.strip().replace("\\n", "\n")
    if text.startswith("-----BEGIN "):
        loaded = serialization.load_pem_public_key(text.encode("utf-8"))
        if not isinstance(loaded, Ed25519PublicKey):
            raise ValueError("Ingest manifest public key must be Ed25519.")
        return loaded
    raw = _load_raw_key_bytes(text, expected_length=32, kind="public")
    return Ed25519PublicKey.from_public_bytes(raw)


def _load_raw_key_bytes(text: str, *, expected_length: int, kind: str) -> bytes:
    try:
        raw = b64decode(text.encode("ascii"), validate=True)
    except (BinasciiError, UnicodeEncodeError) as exc:
        raise ValueError(f"Ingest manifest {kind} key must be raw base64 or PEM.") from exc
    if len(raw) != expected_length:
        raise ValueError(f"Ingest manifest {kind} key must decode to {expected_length} bytes.")
    return raw


def _manifest_file_entry(repo: Path, path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return {
        "path": _repo_relative(repo, path),
        "sha256": sha256_file(path),
    }


def _manifest_deleted_file_entry(repo: Path, path: Path) -> dict[str, Any]:
    return {
        "path": _repo_relative(repo, path),
        "deleted": True,
    }


def _infer_scope_artifacts(
    *,
    base: Path,
    jurisdiction: str,
    document_class: str,
    version: str,
) -> list[Path]:
    files: list[Path] = []
    source_root = base / "sources" / jurisdiction / document_class / version
    if source_root.exists():
        files.extend(path for path in source_root.rglob("*") if path.is_file())
    # Hidden files (.DS_Store, an interrupted download's .part) are never corpus
    # artifacts, and `corpus lock` refuses them; refuse them here too rather
    # than sign bytes no lock may carry.
    hidden = [
        path
        for path in files
        if any(part.startswith(".") for part in path.relative_to(source_root).parts)
    ]
    if hidden:
        raise ValueError(
            f"refusing to sign hidden file(s) in {source_root}: "
            + ", ".join(str(path) for path in hidden[:5])
            + "; delete them first."
        )
    for path in (
        base / "inventory" / jurisdiction / document_class / f"{version}.json",
        base / "provisions" / jurisdiction / document_class / f"{version}.jsonl",
        base / "coverage" / jurisdiction / document_class / f"{version}.json",
    ):
        if path.exists():
            files.append(path)
    if not files:
        raise FileNotFoundError(
            f"No corpus artifacts found for {jurisdiction}/{document_class}/{version} under {base}."
        )
    return sorted(files)


def _load_scope_coverage(
    *,
    base: Path,
    jurisdiction: str,
    document_class: str,
    version: str,
) -> dict[str, Any] | None:
    coverage_path = base / "coverage" / jurisdiction / document_class / f"{version}.json"
    if not coverage_path.exists():
        return None
    try:
        payload = json.loads(coverage_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "complete": payload.get("complete"),
        "source_count": payload.get("source_count"),
        "provision_count": payload.get("provision_count"),
        "matched_count": payload.get("matched_count"),
        "missing_count": len(payload.get("missing_from_provisions") or []),
        "extra_count": len(payload.get("extra_provisions") or []),
    }


def _load_ingest_manifests(repo: Path, *, ref: str | None = None) -> dict[Path, dict[str, Any]]:
    if ref:
        return _load_ingest_manifests_from_ref(repo, ref=ref)
    manifest_root = repo / INGEST_MANIFEST_ROOT
    manifests: dict[Path, dict[str, Any]] = {}
    if not manifest_root.exists():
        return manifests
    for path in sorted(manifest_root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            manifests[path.relative_to(repo)] = {}
            continue
        if isinstance(payload, dict):
            manifests[path.relative_to(repo)] = payload
    return manifests


def _load_ingest_manifests_from_ref(repo: Path, *, ref: str) -> dict[Path, dict[str, Any]]:
    manifests: dict[Path, dict[str, Any]] = {}
    tree_result = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "-z",
            ref,
            "--",
            INGEST_MANIFEST_ROOT.as_posix(),
        ],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if tree_result.returncode != 0:
        detail = tree_result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Unable to list ingest manifests at `{ref}`: {detail}")

    objects: list[tuple[Path, str]] = []
    for raw_entry in tree_result.stdout.split(b"\0"):
        if not raw_entry:
            continue
        try:
            metadata, raw_path = raw_entry.split(b"\t", 1)
            _mode, object_type, raw_oid = metadata.split(b" ", 2)
        except ValueError as exc:
            raise ValueError(f"Malformed Git tree entry while reading `{ref}`.") from exc
        path = Path(raw_path.decode("utf-8", errors="surrogateescape"))
        if object_type == b"blob" and path.suffix == ".json":
            objects.append((path, raw_oid.decode("ascii")))
    objects.sort(key=lambda item: item[0].as_posix())
    if not objects:
        return manifests

    batch_result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        check=False,
        input="".join(f"{oid}\n" for _path, oid in objects).encode("ascii"),
        capture_output=True,
    )
    if batch_result.returncode != 0:
        detail = batch_result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Unable to read ingest manifests at `{ref}`: {detail}")

    output = io.BytesIO(batch_result.stdout)
    for path, expected_oid in objects:
        header = output.readline().rstrip(b"\n").split()
        if len(header) != 3 or header[0].decode("ascii", errors="replace") != expected_oid:
            raise ValueError(f"Malformed Git batch header for ingest manifest `{path}`.")
        if header[1] != b"blob":
            raise ValueError(f"Git object for ingest manifest `{path}` is not a blob.")
        try:
            size = int(header[2])
        except ValueError as exc:
            raise ValueError(f"Malformed Git object size for ingest manifest `{path}`.") from exc
        blob = output.read(size)
        if len(blob) != size or output.read(1) != b"\n":
            raise ValueError(f"Truncated Git object for ingest manifest `{path}`.")
        try:
            payload = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            manifests[path] = {}
            continue
        if isinstance(payload, dict):
            manifests[path] = payload
    if output.read(1):
        raise ValueError(f"Unexpected trailing Git batch output while reading `{ref}`.")
    return manifests


def _artifact_sha(repo: Path, path: str, *, ref: str | None) -> str | None:
    payload = _artifact_bytes(repo, path, ref=ref)
    if payload is None:
        return None
    return sha256_bytes(payload)


def _artifact_bytes(repo: Path, path: str, *, ref: str | None) -> bytes | None:
    if ref:
        return _git_blob(repo, ref=ref, path=path)
    artifact_path = repo / path
    if not artifact_path.exists():
        return None
    return artifact_path.read_bytes()


def _artifact_content_issues(repo: Path, path: str, *, ref: str | None) -> list[str]:
    payload = _artifact_bytes(repo, path, ref=ref)
    if payload is None:
        return []
    return _content_issues(path, payload)


def _content_issues(path: str, payload: bytes) -> list[str]:
    issues: list[str] = []
    if _is_official_document_artifact(path) and _looks_like_agent_digest(path, payload):
        issues.append(
            f"`{path}` is under official-documents/ but looks like an agent digest "
            "with Title:/Sources: headers. Move it to reasoning/ and keep "
            "primary_source false, or replace it with captured official source text."
        )
    if _is_inventory_artifact(path):
        issues.extend(_inventory_primary_source_issues(path, payload))
    return issues


def _reasoning_log_issues(
    repo: Path,
    payload: dict[str, Any],
    *,
    ref: str | None,
) -> list[str]:
    raw_entries = payload.get("reasoning_logs")
    if not isinstance(raw_entries, list):
        return ["`reasoning_logs` must be a list."]

    issues: list[str] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            issues.append("Each reasoning log entry must be an object.")
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            issues.append("Each reasoning log entry must have a path.")
            continue
        path = raw_path
        actual_sha = _artifact_sha(repo, path, ref=ref)
        if actual_sha is None:
            issues.append(f"Manifested reasoning log is missing: `{path}`.")
            continue
        expected_sha = str(entry.get("sha256") or "")
        if actual_sha != expected_sha:
            issues.append(f"`{path}` sha256 does not match the signed reasoning log entry.")
    return issues


def _reasoning_log_paths(payload: dict[str, Any]) -> set[str]:
    raw_entries = payload.get("reasoning_logs")
    if not isinstance(raw_entries, list):
        return set()
    return {
        path
        for entry in raw_entries
        if isinstance(entry, dict)
        if isinstance(path := entry.get("path"), str) and path
    }


def _is_official_document_artifact(path: str) -> bool:
    return path.startswith("data/corpus/sources/") and "/official-documents/" in path


def _is_inventory_artifact(path: str) -> bool:
    return path.startswith("data/corpus/inventory/") and path.endswith(".json")


def _looks_like_agent_digest(path: str, payload: bytes) -> bool:
    if Path(path).suffix.lower() not in TEXT_OFFICIAL_DOCUMENT_SUFFIXES:
        return False
    text = _decode_text(payload)
    if text is None:
        return False
    lines = [line.strip() for line in text.splitlines()[:20] if line.strip()]
    has_title = any(line.startswith("Title:") for line in lines[:5])
    has_sources = any(line.startswith("Sources:") for line in lines[:10])
    return has_title and has_sources


def _inventory_primary_source_issues(path: str, payload: bytes) -> list[str]:
    text = _decode_text(payload)
    if text is None:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    issues: list[str] = []
    for item in parsed.get("items") or []:
        if not isinstance(item, dict):
            continue
        raw_metadata = item.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        if metadata.get("primary_source") is not True:
            continue
        source_path = str(item.get("source_path") or "")
        if "/reasoning/" not in source_path:
            continue
        citation = str(item.get("citation_path") or "<unknown citation>")
        issues.append(
            f"`{path}` marks `{citation}` primary_source true while source_path "
            f"`{source_path}` is under reasoning/. Primary rows must point at "
            "official-documents/ captures, not reasoning artifacts."
        )
    return issues


def _decode_text(payload: bytes) -> str | None:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _git_blob(repo: Path, *, ref: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _changed_paths(
    *,
    repo: Path,
    base_ref: str | None,
    head_ref: str | None,
) -> tuple[_ChangedPath, ...]:
    if base_ref:
        diff_ref = f"{base_ref}...{head_ref or 'HEAD'}"
        args = ["git", "diff", "--name-status", "-z", "--no-renames", diff_ref]
    else:
        args = ["git", "diff", "--name-status", "-z", "--no-renames", "HEAD"]
    result = subprocess.run(
        args,
        cwd=repo,
        check=True,
        capture_output=True,
    )
    fields = result.stdout.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        raise ValueError("Malformed NUL-delimited Git diff output.")

    changes: list[_ChangedPath] = []
    for raw_status, raw_path in zip(fields[::2], fields[1::2], strict=True):
        status = raw_status.decode("ascii")
        if not status:
            raise ValueError("Git diff returned an empty change status.")
        path = os.fsdecode(raw_path)
        changes.append(_ChangedPath(status=status[0], path=path))
    return tuple(changes)


def _is_protected_corpus_artifact(path: str) -> bool:
    return lands_on_protected_path(path)


def _git_metadata(repo: Path) -> dict[str, Any]:
    def git(*args: str) -> str | None:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    status = git("status", "--porcelain", "--untracked-files=no")
    return {
        # The manifest is repository-relative; an absolute checkout path is
        # neither reproducible nor useful provenance.
        "root": ".",
        "commit": git("rev-parse", "HEAD"),
        "dirty_tracked": None if status is None else bool(status),
    }


def _manifest_git_provenance_issues(payload: dict[str, Any]) -> list[str]:
    metadata = payload.get("axiom_corpus_git")
    if not isinstance(metadata, dict):
        return ["`axiom_corpus_git` must be an object."]
    return _git_provenance_issues(metadata)


def _git_provenance_issues(metadata: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if metadata.get("root") != ".":
        issues.append("`axiom_corpus_git.root` must be `.`.")
    if metadata.get("dirty_tracked") is not False:
        issues.append("`axiom_corpus_git.dirty_tracked` must be false.")
    if not _is_full_git_commit(metadata.get("commit")):
        issues.append("`axiom_corpus_git.commit` must be a full 40-character lowercase Git commit.")
    return issues


def _is_full_git_commit(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and FULL_GIT_COMMIT_PATTERN.fullmatch(value) is not None


def _git_commit_is_ancestor(repo: Path, *, commit: str, head_ref: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head_ref],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _package_version() -> str:
    try:
        return importlib.metadata.version("axiom-corpus")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0"


def _resolve_under_repo(repo: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo / path
    resolved = candidate.resolve()
    resolved.relative_to(repo)
    return resolved


def _repo_relative(repo: Path, path: Path) -> str:
    return path.resolve().relative_to(repo).as_posix()


def _safe_segment(value: str) -> str:
    cleaned = value.strip().strip("/")
    cleaned = cleaned.replace("\\", "-").replace(":", "-")
    if cleaned in {"", ".", ".."} or "/" in cleaned:
        raise ValueError(f"unsafe path segment: {value!r}")
    return cleaned
