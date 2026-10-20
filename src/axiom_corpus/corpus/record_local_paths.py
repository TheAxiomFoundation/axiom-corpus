"""Paths on one machine in the repository's unsigned records.

Run notes (``docs/ingest-runs/``), closure work (``docs/coverage/``), reasoning
logs (``.axiom/reasoning-logs/``) and source manifests (``manifests/``) are
public, like the signed ingest manifests that ``manifest_local_paths`` guards.
A path such as ``/Users/<name>/...``, ``/private/tmp/...`` or ``~/...`` reaches
no reader and publishes the operator's account name and directory layout. The
convention is the same: repository-relative paths for repository files, and
placeholders for directories on the machine (``<worktrees>/<name>``,
``<rulespec-us>``, ``<axiom-cache>``, ``<scratchpad>``, ``<uv-cache>``).

``find_record_local_paths`` finds such paths in a record's text;
``audit_record_local_paths`` checks every record in the repository against
``.axiom/record-local-paths.yaml``, which grandfathers only records a signed
ingest manifest attests (their bytes cannot change without signing it again).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from axiom_corpus.corpus.manifest_local_paths import LocalPath, find_local_paths

# Directories whose files are records of how the corpus was built.
RECORD_ROOTS: tuple[str, ...] = (
    ".axiom/reasoning-logs",
    "docs/coverage",
    "docs/ingest-runs",
    "manifests",
)
RECORD_LOCAL_PATH_ALLOWLIST_PATH = Path(".axiom") / "record-local-paths.yaml"
RECORD_LOCAL_PATH_ALLOWLIST_SCHEMA_VERSION = "axiom-corpus/record-local-paths/v1"
INGEST_MANIFEST_ROOT = ".axiom/ingest-manifests"

# Spellings that name no place below a root, so publish neither an account name
# nor a layout: a lone ``~`` (in records, "approximately", OCR noise, a
# ``#:~:text=`` URL fragment or a CSS sibling combinator), a bare ``file:``
# scheme (prose about ``file://`` URLs), ``$HOME`` alone, and a root alone.
_NO_PLACE = {
    "tilde": re.compile(r"~/?"),
    "file_url": re.compile(r"(?i)file:/*"),
    "home_variable": re.compile(r"(?i)(?:\$HOME|\$\{HOME\}|%USERPROFILE%)/?"),
    "windows": re.compile(r"(?i)[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]?"),
}
# On the macOS machines that write these records ``/media/`` does not exist;
# in them it is the path of a page on content-managed sites
# (``/media/file/ia-13-0022-mc5.pdf`` on medicaid.gov).
_URL_PATH_ROOTS = frozenset({"/media/"})

_TRACKING_ISSUE = re.compile(
    r"https://github\.com/TheAxiomFoundation/axiom-corpus/issues/[1-9][0-9]*"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def find_record_local_paths(text: str) -> list[LocalPath]:
    """Return the paths on the writing machine in a record's ``text``, in order.

    These are ``find_local_paths``'s, less the spellings that name no place
    (``~``, ``file://``, ``$HOME`` or a root such as ``/Users/`` alone) and
    ``/media/`` paths, which in these records are web paths.
    """
    return [path for path in find_local_paths(text) if not _names_no_place(text, path)]


def _names_no_place(text: str, path: LocalPath) -> bool:
    token = text[path.start : path.end]
    if path.kind == "absolute":
        return token == path.root or path.root in _URL_PATH_ROOTS
    return _NO_PLACE[path.kind].fullmatch(token) is not None


@dataclass(frozen=True)
class RecordAllowance:
    """One grandfathered record: its exact bytes, the manifests that attest them, its issue."""

    path: str
    sha256: str
    attested_by: tuple[str, ...]
    issue: str


def load_record_local_path_allowlist(path: Path) -> list[RecordAllowance]:
    """Read ``.axiom/record-local-paths.yaml``; raise ``ValueError`` if malformed."""
    try:
        document = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ValueError("is not YAML") from exc
    if not isinstance(document, dict):
        raise ValueError("is not a mapping")
    if document.get("schema_version") != RECORD_LOCAL_PATH_ALLOWLIST_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be `{RECORD_LOCAL_PATH_ALLOWLIST_SCHEMA_VERSION}`")
    raw = document.get("records")
    if not isinstance(raw, list):
        raise ValueError("`records` must be a list")
    allowances: list[RecordAllowance] = []
    for index, item in enumerate(raw):
        where = f"`records[{index}]`"
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "attested_by", "issue"}:
            raise ValueError(f"{where} must have exactly path, sha256, attested_by and issue")
        entry_path, digest, attested_by, issue = (
            item["path"],
            item["sha256"],
            item["attested_by"],
            item["issue"],
        )
        if not (isinstance(entry_path, str) and _is_record_path(entry_path)):
            raise ValueError(f"{where} path must name a file under {', '.join(RECORD_ROOTS)}")
        if not (isinstance(digest, str) and _SHA256.fullmatch(digest)):
            raise ValueError(f"{where} sha256 must be 64 lowercase hex digits")
        if not (
            isinstance(attested_by, list)
            and attested_by
            and all(
                isinstance(name, str) and _is_ingest_manifest_path(name) for name in attested_by
            )
            and attested_by == sorted(set(attested_by))
        ):
            raise ValueError(
                f"{where} attested_by must be a sorted list of distinct .json files "
                f"under {INGEST_MANIFEST_ROOT}/"
            )
        if not (isinstance(issue, str) and _TRACKING_ISSUE.fullmatch(issue)):
            raise ValueError(f"{where} issue must be an axiom-corpus issue URL")
        allowances.append(RecordAllowance(entry_path, digest, tuple(attested_by), issue))
    return allowances


def _is_record_path(path: str) -> bool:
    parts = path.split("/")
    return (
        ".." not in parts
        and "" not in parts
        and any(path.startswith(f"{root}/") for root in RECORD_ROOTS)
    )


def _is_ingest_manifest_path(path: str) -> bool:
    parts = path.split("/")
    return (
        path.startswith(f"{INGEST_MANIFEST_ROOT}/")
        and path.endswith(".json")
        and ".." not in parts
        and "" not in parts
    )


def record_files(repo: Path) -> list[str]:
    """Return the records in ``repo``: tracked or untracked, never git-ignored.

    Ignored files (``__pycache__/``, ``.DS_Store``, ``downloads/``) are local
    by-products, not records.
    """
    listed = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *RECORD_ROOTS,
        ],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return sorted({name for name in listed.split("\0") if name and (repo / name).is_file()})


def _attestations(repo: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Map each record a signed ingest manifest attests to ``{manifest: sha256}``."""
    attested: dict[str, dict[str, str]] = {}
    issues: list[str] = []
    root = repo / INGEST_MANIFEST_ROOT
    for manifest in sorted(root.rglob("*.json")) if root.is_dir() else []:
        relative = manifest.relative_to(repo).as_posix()
        try:
            payload = json.loads(manifest.read_bytes())
            logs = payload.get("reasoning_logs") or []
            entries = [(str(log["path"]), str(log["sha256"])) for log in logs]
        except (ValueError, TypeError, KeyError, AttributeError):
            issues.append(f"`{relative}` cannot be read, so the records it attests are unknown.")
            continue
        for path, digest in entries:
            attested.setdefault(path, {})[relative] = digest
    return attested, issues


def audit_record_local_paths(
    repo: Path,
    *,
    grandfathered_sha256: frozenset[str],
    allowlist: Path = RECORD_LOCAL_PATH_ALLOWLIST_PATH,
) -> list[str]:
    """Return the issues that keep the repository's records from passing.

    Every record under ``RECORD_ROOTS`` must hold no path on the machine that
    wrote it (``find_record_local_paths``), unless the allowlist grandfathers
    it. An allowance holds only while its record keeps the bytes it pins, still
    holds a local path, and is attested at those bytes by exactly the signed
    ingest manifests it names, and only for bytes in ``grandfathered_sha256``,
    so the allowlist only shrinks. A record that is not UTF-8 text fails closed.
    Messages name a path by its root only (``/Users/…``), never in full.
    """
    repo = repo.resolve()
    issues: list[str] = []
    try:
        allowances = load_record_local_path_allowlist(repo / allowlist)
    except OSError as exc:
        # strerror only: the exception's text names the absolute path.
        return [f"`{allowlist.as_posix()}` cannot be read ({exc.strerror})."]
    except ValueError as exc:
        return [f"`{allowlist.as_posix()}` {exc}."]
    attested, attestation_issues = _attestations(repo)
    issues.extend(attestation_issues)
    by_path: dict[str, RecordAllowance] = {}
    for allowance in allowances:
        if allowance.path in by_path:
            issues.append(f"`{allowlist.as_posix()}` lists `{allowance.path}` twice.")
        by_path[allowance.path] = allowance
        if allowance.sha256 not in grandfathered_sha256:
            issues.append(
                f"`{allowlist.as_posix()}` lists `{allowance.path}` at bytes that were not "
                "grandfathered on 2026-10-20. The allowlist only shrinks: write the record "
                "without local paths instead of listing it."
            )
    for relative in record_files(repo):
        payload = (repo / relative).read_bytes()
        allowed = by_path.pop(relative, None)
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(
                f"`{relative}` is not UTF-8 text, so it cannot be checked for local paths."
            )
            continue
        found = find_record_local_paths(text)
        if not found:
            if allowed is not None:
                issues.append(
                    f"`{relative}` no longer holds a local path; remove its entry from "
                    f"`{allowlist.as_posix()}` ({allowed.issue})."
                )
            continue
        if allowed is None:
            issues.append(f"`{relative}`: {_describe(text, found)}. {_REMEDY}")
            continue
        digest = hashlib.sha256(payload).hexdigest()
        if digest != allowed.sha256:
            issues.append(
                f"`{relative}` changed since it was grandfathered (sha256 "
                f"{allowed.sha256[:12]}…). A changed record must not hold local paths: "
                f"scrub them and remove its entry from `{allowlist.as_posix()}` "
                f"({allowed.issue}). {_describe(text, found)}."
            )
            continue
        attesting = tuple(
            sorted(
                manifest
                for manifest, recorded in attested.get(relative, {}).items()
                if recorded == digest
            )
        )
        if attesting != allowed.attested_by:
            issues.append(
                f"`{relative}` is attested at these bytes by "
                f"{', '.join(f'`{name}`' for name in attesting) or 'no signed ingest manifest'}, "
                f"but `{allowlist.as_posix()}` names "
                f"{', '.join(f'`{name}`' for name in allowed.attested_by)}. Only a record a "
                "signed ingest manifest attests is grandfathered; scrub any other."
            )
    for allowance in by_path.values():
        issues.append(
            f"`{allowlist.as_posix()}` lists `{allowance.path}`, which is not a record in the "
            "repository; remove its entry."
        )
    return issues


_REMEDY = (
    "Name repository files by their repository-relative path and directories on "
    "your machine by a placeholder such as `<worktrees>/<name>`, `<scratchpad>` or "
    "`<axiom-cache>`; a new record is never grandfathered."
)


def _describe(text: str, found: list[LocalPath]) -> str:
    by_line: dict[int, set[str]] = {}
    for path in found:
        line = text.count("\n", 0, path.start) + 1
        by_line.setdefault(line, set()).add(path.describe())
    return "; ".join(
        f"line {line} holds {', '.join(sorted(roots))}" for line, roots in sorted(by_line.items())
    )
