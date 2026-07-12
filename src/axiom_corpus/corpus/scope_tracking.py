"""Verify that corpus scope references point to git-tracked artifacts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True)
class ScopeTrackingResult:
    """Result of checking inventory and ingest-manifest file references."""

    scopes_checked: int
    files_verified: int
    missing_paths: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.missing_paths


def verify_scope_tracked(
    *,
    repo: Path,
    jurisdiction: str | None = None,
    document_class: str | None = None,
    version: str | None = None,
) -> ScopeTrackingResult:
    """Check scoped inventory and signed-manifest references against git's index."""
    repo = repo.resolve()
    tracked_paths = _git_cached_paths(repo)
    inventory_paths = sorted(
        path
        for path in tracked_paths
        if _scope_matches(
            _inventory_scope(path),
            jurisdiction=jurisdiction,
            document_class=document_class,
            version=version,
        )
    )
    manifest_paths = sorted(
        path
        for path in tracked_paths
        if _scope_matches(
            _manifest_scope(path),
            jurisdiction=jurisdiction,
            document_class=document_class,
            version=version,
        )
    )
    indexed_payloads = _git_indexed_json_batch(
        repo, [*inventory_paths, *manifest_paths]
    )

    referenced_paths: set[str] = set()
    for inventory_path in inventory_paths:
        payload = indexed_payloads[inventory_path]
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            source_path = item.get("source_path")
            if isinstance(source_path, str) and source_path.strip():
                referenced_paths.add(_inventory_source_repo_path(source_path))

    for manifest_path in manifest_paths:
        payload = indexed_payloads[manifest_path]
        if not isinstance(payload.get("signature"), dict):
            continue
        for entry in payload.get("applied_files", []):
            if not isinstance(entry, dict):
                continue
            if entry.get("deleted") is True:
                continue
            path = entry.get("path")
            if isinstance(path, str) and path.strip():
                referenced_paths.add(_repo_relative_path(path))

    missing_paths = tuple(sorted(referenced_paths - tracked_paths))
    return ScopeTrackingResult(
        scopes_checked=len(inventory_paths),
        files_verified=len(referenced_paths),
        missing_paths=missing_paths,
    )


def _git_cached_paths(repo: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return {
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    }


def _git_indexed_json(repo: Path, path: str) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _git_indexed_json_batch(repo: Path, paths: list[str]) -> dict[str, dict[str, Any]]:
    """Read JSON objects from git's index through one cat-file process."""
    if not paths:
        return {}
    requests = b"".join(
        b":" + path.encode("utf-8", errors="surrogateescape") + b"\n" for path in paths
    )
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        input=requests,
        check=True,
        capture_output=True,
    )
    output = memoryview(result.stdout)
    offset = 0
    payloads: dict[str, dict[str, Any]] = {}
    for path in paths:
        newline = result.stdout.find(b"\n", offset)
        if newline < 0:
            raise ValueError(f"Missing git cat-file response for {path}")
        header = bytes(output[offset:newline])
        offset = newline + 1
        if header.endswith(b" missing"):
            continue
        try:
            _object_name, object_type, size_text = header.rsplit(b" ", 2)
            size = int(size_text)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid git cat-file response for {path}: {header!r}") from exc
        if object_type != b"blob":
            raise ValueError(f"Expected a git blob for {path}, got {object_type.decode()}")
        end = offset + size
        if end >= len(output) or output[end] != 10:
            raise ValueError(f"Truncated git cat-file response for {path}")
        payload = json.loads(bytes(output[offset:end]).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        payloads[path] = payload
        offset = end + 1
    return payloads


def _inventory_source_repo_path(path: str) -> str:
    normalized = _repo_relative_path(path)
    if normalized.startswith("data/corpus/"):
        return normalized
    return f"data/corpus/{normalized}"


def _repo_relative_path(path: str) -> str:
    normalized = PurePosixPath(path.strip()).as_posix()
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        raise ValueError(f"Referenced path must be repository-relative: {path}")
    return normalized.removeprefix("./")


def _inventory_scope(path: str) -> tuple[str, str, str] | None:
    parts = PurePosixPath(path).parts
    if len(parts) != 6 or parts[:3] != ("data", "corpus", "inventory"):
        return None
    if not parts[5].endswith(".json"):
        return None
    return parts[3], parts[4], parts[5].removesuffix(".json")


def _manifest_scope(path: str) -> tuple[str, str, str] | None:
    parts = PurePosixPath(path).parts
    if len(parts) != 5 or parts[:2] != (".axiom", "ingest-manifests"):
        return None
    if not parts[4].endswith(".json"):
        return None
    return parts[2], parts[3], parts[4].removesuffix(".json")


def _scope_matches(
    scope: tuple[str, str, str] | None,
    *,
    jurisdiction: str | None,
    document_class: str | None,
    version: str | None,
) -> bool:
    if scope is None:
        return False
    return (
        (jurisdiction is None or scope[0] == jurisdiction)
        and (document_class is None or scope[1] == document_class)
        and (version is None or scope[2] == version)
    )
