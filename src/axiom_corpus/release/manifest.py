"""Build, sign, and verify corpus release manifests.

A release manifest is a deterministic, content-addressed description of a
corpus state. Given the same tracked tree it produces byte-identical canonical
JSON, which is what makes the HMAC signature a stable release identity.

Design notes
------------
* **Local hashes are the source of truth.** Each artifact entry records the
  SHA-256 of the on-disk bytes. For line-delimited ``.jsonl`` artifacts we also
  record a ``rows`` count (non-empty lines) so downstream consumers can detect
  truncation without re-reading the file.
* **R2 keys are declared paths, not verified objects.** We never contact R2.
  The declared key is derived mechanically from the artifact's path under
  ``data/corpus`` (``data/corpus/<class>/<jurisdiction>/... -> <class>/<...>``)
  against the ``axiom-corpus`` bucket, matching the ingest/sync-r2 layout. A
  consumer with credentials can later confirm the object matches the recorded
  hash.
* **Time comes from git, not the wall clock.** ``created_at`` is the committer
  time of ``HEAD`` (UTC), so re-emitting a manifest for the same commit is
  reproducible. When the tree is not a git checkout (or ``git`` is
  unavailable), the caller must pass ``created_at`` explicitly.
* **Signing mirrors axiom-encode.** Canonical JSON is
  ``json.dumps(payload_without_signature, sort_keys=True,
  separators=(",", ":"), ensure_ascii=True)`` and the signature is
  ``hmac.new(key, canonical, sha256).hexdigest()`` wrapped in a
  ``{"algorithm", "key_id", "value"}`` block. This matches
  ``axiom_encode``'s applied-encoding manifest convention (and the repo's own
  Ed25519 ingest-manifest canonicalization) so verification stays consistent
  across repositories.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RELEASE_MANIFEST_SCHEMA_VERSION = "axiom-corpus/release-manifest/v1"
RELEASE_MANIFEST_SIGNATURE_ALGORITHM = "hmac-sha256"
RELEASE_MANIFEST_SIGNATURE_KEY_ID = "axiom-corpus-release-v1"
RELEASE_MANIFEST_SIGNING_KEY_ENV = "AXIOM_CORPUS_RELEASE_SIGNING_KEY"

# R2 bucket that holds published corpus artifacts (see CLAUDE.md / architecture
# doc: ``data/corpus/{sources,inventory,provisions,coverage} -> R2 bucket:
# axiom-corpus``).
DEFAULT_R2_BUCKET = "axiom-corpus"

# Artifact classes under ``data/corpus`` and the file suffixes we hash for
# each. ``sources`` holds heterogeneous original documents (xml/html/pdf/...),
# so it is hashed by any file rather than a fixed suffix.
_JSONL_SUFFIX = ".jsonl"
_JSON_SUFFIX = ".json"

# Ordered so the manifest is stable and human-scannable.
_ARTIFACT_CLASSES: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("provisions", (_JSONL_SUFFIX,)),
    ("inventory", (_JSON_SUFFIX,)),
    ("coverage", (_JSON_SUFFIX,)),
    ("manifests", None),
    ("sources", None),
)


class ReleaseManifestError(RuntimeError):
    """Raised when a release manifest cannot be built or verified."""


@dataclass(frozen=True)
class _ArtifactEntry:
    path: str
    sha256: str
    bytes: int
    rows: int | None
    r2_key: str | None

    def to_mapping(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "path": self.path,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }
        if self.r2_key is not None:
            entry["r2_key"] = self.r2_key
        if self.rows is not None:
            entry["rows"] = self.rows
        return entry


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_row_count(path: Path) -> int:
    """Count non-empty lines in a line-delimited JSONL artifact.

    A blank trailing line (the artifacts are newline-terminated) is not a row.
    """
    rows = 0
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                rows += 1
    return rows


# ---------------------------------------------------------------------------
# R2 declared-path derivation
# ---------------------------------------------------------------------------


def declared_r2_key(relative_path: str, *, base: str, bucket: str) -> str:
    """Derive the declared R2 object key for an artifact.

    ``relative_path`` is repo-relative (e.g.
    ``data/corpus/provisions/us/statute/x.jsonl``); ``base`` is the corpus
    base (``data/corpus``). The R2 layout drops the base prefix, so the key
    becomes ``<bucket>/provisions/us/statute/x.jsonl`` expressed as
    ``r2://<bucket>/<key>``.
    """
    base_prefix = base.rstrip("/") + "/"
    key_tail = (
        relative_path[len(base_prefix) :]
        if relative_path.startswith(base_prefix)
        else relative_path
    )
    return f"r2://{bucket}/{key_tail}"


# ---------------------------------------------------------------------------
# Git provenance
# ---------------------------------------------------------------------------


def _run_git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            check=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip()


def git_commit_provenance(repo_root: Path) -> dict[str, str] | None:
    """Return ``{commit, committed_at}`` for ``HEAD``, or ``None`` if unavailable.

    ``committed_at`` is the committer timestamp normalized to UTC ISO-8601.
    """
    commit = _run_git(repo_root, "rev-parse", "HEAD")
    if not commit:
        return None
    epoch = _run_git(repo_root, "show", "-s", "--format=%ct", "HEAD")
    if not epoch:
        return None
    committed_at = (
        datetime.fromtimestamp(int(epoch), tz=UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return {"commit": commit, "committed_at": committed_at}


# ---------------------------------------------------------------------------
# Artifact collection
# ---------------------------------------------------------------------------


def _iter_class_files(
    class_dir: Path,
    suffixes: tuple[str, ...] | None,
) -> list[Path]:
    if not class_dir.is_dir():
        return []
    files = [path for path in class_dir.rglob("*") if path.is_file()]
    if suffixes is not None:
        files = [path for path in files if path.suffix in suffixes]
    return sorted(files, key=lambda p: p.as_posix())


def _artifact_entry(
    path: Path,
    *,
    repo_root: Path,
    base: str,
    bucket: str,
    with_rows: bool,
    in_r2: bool,
) -> _ArtifactEntry:
    relative = path.relative_to(repo_root).as_posix()
    # Only artifacts published under the corpus base are R2 objects. Repo-root
    # artifacts (claims/, DATA_INVENTORY.md) live in git only, so we record no
    # declared R2 key rather than a path that would not resolve in the bucket.
    r2_key = (
        declared_r2_key(relative, base=base, bucket=bucket) if in_r2 else None
    )
    return _ArtifactEntry(
        path=relative,
        sha256=sha256_file(path),
        bytes=path.stat().st_size,
        rows=jsonl_row_count(path) if with_rows else None,
        r2_key=r2_key,
    )


def _collect_corpus_artifacts(
    repo_root: Path,
    base_dir: Path,
    base: str,
    bucket: str,
) -> dict[str, list[_ArtifactEntry]]:
    artifacts: dict[str, list[_ArtifactEntry]] = {}
    for class_name, suffixes in _ARTIFACT_CLASSES:
        class_dir = base_dir / class_name
        with_rows = suffixes == (_JSONL_SUFFIX,)
        entries = [
            _artifact_entry(
                path,
                repo_root=repo_root,
                base=base,
                bucket=bucket,
                with_rows=with_rows,
                in_r2=True,
            )
            for path in _iter_class_files(class_dir, suffixes)
        ]
        artifacts[class_name] = entries
    return artifacts


def _collect_extra_files(
    repo_root: Path,
    relative_paths: Iterable[str],
    *,
    base: str,
    bucket: str,
    with_rows: bool,
) -> list[_ArtifactEntry]:
    entries: list[_ArtifactEntry] = []
    for relative in sorted(set(relative_paths)):
        path = repo_root / relative
        if not path.is_file():
            continue
        entries.append(
            _artifact_entry(
                path,
                repo_root=repo_root,
                base=base,
                bucket=bucket,
                with_rows=with_rows and path.suffix == _JSONL_SUFFIX,
                in_r2=False,
            )
        )
    return entries


def _class_summary(entries: Sequence[_ArtifactEntry]) -> dict[str, int]:
    summary = {
        "files": len(entries),
        "bytes": sum(entry.bytes for entry in entries),
    }
    row_entries = [entry.rows for entry in entries if entry.rows is not None]
    if row_entries:
        summary["rows"] = sum(row_entries)
    return summary


# ---------------------------------------------------------------------------
# Manifest construction
# ---------------------------------------------------------------------------


def build_release_manifest(
    repo_root: Path,
    *,
    release: str,
    base: str = "data/corpus",
    bucket: str = DEFAULT_R2_BUCKET,
    claims_paths: Iterable[str] | None = None,
    data_inventory_path: str = "DATA_INVENTORY.md",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build an unsigned release manifest for the corpus tree at ``repo_root``.

    Parameters
    ----------
    repo_root:
        Repository root containing ``data/corpus``, the claims files, and
        ``DATA_INVENTORY.md``.
    release:
        Release identifier, e.g. ``"r0"``.
    base:
        Corpus base directory, repo-relative.
    bucket:
        R2 bucket name for declared object keys.
    claims_paths:
        Repo-relative claims JSONL paths. Defaults to every ``*.jsonl`` under
        ``claims/``.
    data_inventory_path:
        Repo-relative path to the data-inventory markdown.
    created_at:
        Override for the manifest timestamp. Defaults to ``HEAD``'s committer
        time (UTC). Raises if omitted and git provenance is unavailable, so a
        manifest is never silently stamped with the wall clock.
    """
    repo_root = repo_root.resolve()
    base_dir = repo_root / base
    if not base_dir.is_dir():
        raise ReleaseManifestError(
            f"corpus base directory not found: {base_dir}"
        )

    git = git_commit_provenance(repo_root)
    if created_at is None:
        if git is None:
            raise ReleaseManifestError(
                "created_at is required when git commit time is unavailable "
                "(pass created_at=... explicitly)"
            )
        created_at = git["committed_at"]

    corpus_artifacts = _collect_corpus_artifacts(
        repo_root, base_dir, base, bucket
    )

    if claims_paths is None:
        claims_root = repo_root / "claims"
        discovered = (
            path.relative_to(repo_root).as_posix()
            for path in claims_root.rglob(f"*{_JSONL_SUFFIX}")
            if path.is_file()
        )
        claims_paths = list(discovered)
    claims_entries = _collect_extra_files(
        repo_root,
        claims_paths,
        base=base,
        bucket=bucket,
        with_rows=True,
    )

    inventory_entries = _collect_extra_files(
        repo_root,
        [data_inventory_path],
        base=base,
        bucket=bucket,
        with_rows=False,
    )

    artifacts_block = {
        class_name: [entry.to_mapping() for entry in entries]
        for class_name, entries in corpus_artifacts.items()
    }
    artifacts_block["claims"] = [entry.to_mapping() for entry in claims_entries]

    summary = {
        class_name: _class_summary(entries)
        for class_name, entries in corpus_artifacts.items()
    }
    summary["claims"] = _class_summary(claims_entries)
    summary["totals"] = {
        "files": sum(block["files"] for block in summary.values()),
        "bytes": sum(block["bytes"] for block in summary.values()),
    }

    documents_block = {
        entry.path: {"sha256": entry.sha256, "bytes": entry.bytes}
        for entry in inventory_entries
    }

    manifest: dict[str, Any] = {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "release": release,
        "created_at": created_at,
        "source_of_truth": "local-artifact-hashes",
        "corpus_base": base,
        "r2": {"bucket": bucket, "keys": "declared"},
        "git": git or {},
        "summary": summary,
        "documents": documents_block,
        "artifacts": artifacts_block,
    }
    return manifest


# ---------------------------------------------------------------------------
# Canonicalization + signing (mirrors axiom-encode apply manifests)
# ---------------------------------------------------------------------------


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Return the canonical, signature-independent JSON bytes for ``manifest``.

    The ``signature`` field is excluded so signing and verification hash the
    same content.
    """
    unsigned = {key: value for key, value in manifest.items() if key != "signature"}
    return json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()


def manifest_signature_value(manifest: dict[str, Any], signing_key: str) -> str:
    return hmac.new(
        signing_key.encode(),
        canonical_manifest_bytes(manifest),
        hashlib.sha256,
    ).hexdigest()


def sign_manifest(manifest: dict[str, Any], signing_key: str) -> dict[str, Any]:
    """Return a copy of ``manifest`` with an HMAC-SHA256 signature attached."""
    signed = {key: value for key, value in manifest.items() if key != "signature"}
    signed["signature"] = {
        "algorithm": RELEASE_MANIFEST_SIGNATURE_ALGORITHM,
        "key_id": RELEASE_MANIFEST_SIGNATURE_KEY_ID,
        "value": manifest_signature_value(signed, signing_key),
    }
    return signed


def manifest_signature_issue(
    manifest: dict[str, Any], signing_key: str
) -> str | None:
    """Return a human-readable problem with the signature, or ``None`` if valid."""
    signature = manifest.get("signature")
    if not isinstance(signature, dict):
        return "is missing a release manifest signature"
    if signature.get("algorithm") != RELEASE_MANIFEST_SIGNATURE_ALGORITHM:
        return "uses an unsupported release manifest signature algorithm"
    if signature.get("key_id") != RELEASE_MANIFEST_SIGNATURE_KEY_ID:
        return "uses an unknown release manifest signing key"
    expected = manifest_signature_value(manifest, signing_key)
    actual = signature.get("value")
    if not isinstance(actual, str) or not hmac.compare_digest(actual, expected):
        return "has an invalid release manifest signature"
    return None


def verify_manifest(manifest: dict[str, Any], signing_key: str) -> None:
    """Raise :class:`ReleaseManifestError` if the signature does not verify."""
    issue = manifest_signature_issue(manifest, signing_key)
    if issue is not None:
        raise ReleaseManifestError(f"Release manifest {issue}.")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def serialize_manifest(manifest: dict[str, Any]) -> str:
    """Serialize a manifest for on-disk storage.

    Uses sorted keys and a trailing newline so committed manifests are stable
    and diff cleanly. This pretty form is for humans/git; the *signature* is
    always computed over :func:`canonical_manifest_bytes`, never this text.
    """
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
