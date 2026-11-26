#!/usr/bin/env python3
"""Repair a publisher conflict plan into fresh, self-contained release scopes.

The conflict plan is publisher evidence, not a corpus artifact.  This command
only reads it and fails closed unless every conflict can be assigned either to
its immutable release scope or to a release scope which owns the legacy parent
whose replacement would cascade outside the load.

Repair re-versions no base scope it knows. It reads the selectors committed
at HEAD of ``--repo``, of the checkouts that physically hold a path it
touches or ``--release``, of each checkout the resolver recognises that holds
a link on those paths as repair spells them, and of the working directory's
checkout, plus the bases ``--release`` itself marks. After it fetches and
plans the repair, and before its first move, rewrite or unlink, it refuses a
scope any of them marks as a base, a link at a checkout's guarded place that
leads into no checkout, a path through a symlinked file at or below a guarded
place of a checkout the resolver recognises, a checkout whose ``manifests``
or ``manifests/releases`` is a symlink, a scope artifact path that does not
resolve to a path ending in its own artifact kind, jurisdiction, document
class and version, a new scope's path that already exists, a symlink or a
file with another hard link in the sources it moves, and a file or sources
directory it would unlink or move that a base it knows reaches through a link
(``successors.guard_scope_artifacts`` and ``refuse_links_into_bases``). Its
rewrites of ``--release``, ``manifests/**/*.yaml`` and ``SIGNING-COMMANDS.md``
follow links and are not guarded (the threat model's stated limit 9), and a
checkout it does not read is one of its stated limits (2, 11 and 15).

Before it fetches anything, repair refuses a ``--report`` path that lies at
or below a corpus, lock or selector place (``PLACES``) of ``--repo``, of the
checkout that physically holds it, or of a checkout that holds a link at one
of its guarded places on the path as spelled. Each place is followed to
where it leads, a place that does not exist yet and a dangling link at a
place included. It also refuses a path below an entry that is not a
directory; the ``--release`` or ``--conflicts`` file; a link (a dangling one
included), a directory, anything but a regular file (``/dev/null`` included:
the report has no "drop" mode) or a file with another hard link; and a file
this script did not write. Just before the write, the content, place and
directory rules run again, before any directory is made, and the report
replaces its path without following a link. A report path that does not
exist yet, where a link leads that the place rule does not follow, is
created there: a link below a place, or a link of a checkout the rule does
not read, such as the working directory's, or another checkout's linked
``.axiom``, ``.axiom/corpus-locks`` or ``manifests`` that the path is spelled
through (the threat model's stated limit 14).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import stat
import tempfile
from collections import defaultdict
from collections.abc import Collection, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.corpus_locks import _caseless, fold_path
from axiom_corpus.corpus.releases import LAYER_BASE
from axiom_corpus.corpus.resolver import ensure_corpus_scopes
from axiom_corpus.corpus.successors import (
    canonical_scope_key,
    checkouts_holding,
    guard_scope_artifacts,
    refuse_links_into_bases,
    tracked_base_scopes,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id

ARTIFACT_KINDS = ("coverage", "inventory", "provisions", "sources")
DEFAULT_SUFFIX = "r2026-07-15-self-contained"
# The keys of the report main() writes: an existing report path must hold exactly these.
REPORT_KEYS = frozenset(
    {
        "assertion",
        "conflict_rows",
        "rows_added",
        "scopes_repaired",
        "scopes_repaired_count",
        "cascade_parent_paths",
    }
)
# A checkout's corpus, lock and selector places, which a report path must not resolve into.
PLACES = (
    "data",
    "data/corpus",
    "data/corpus/coverage",
    "data/corpus/inventory",
    "data/corpus/provisions",
    "data/corpus/sources",
    ".axiom",
    ".axiom/ingest-manifests",
    ".axiom/corpus-locks",
    "manifests",
    "manifests/releases",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _alike(first: str, second: str) -> bool:
    """One name as a case- or normalization-insensitive filesystem stores it, as
    ``resolver._spells_place`` compares."""
    return bool(fold_path(first) == fold_path(second) or _caseless(first) == _caseless(second))


def _anchors(path: Path) -> list[tuple[os.stat_result, tuple[str, ...]]]:
    """Each existing entry on ``path``, deepest first, with the names below it."""
    found: list[tuple[os.stat_result, tuple[str, ...]]] = []
    for depth in range(len(path.parts), 0, -1):
        with contextlib.suppress(OSError):
            found.append((os.stat(Path(*path.parts[:depth])), path.parts[depth:]))
    return found


def _report_roots(spelled: Path, *, repo: Path) -> list[Path]:
    """The checkouts whose places a report path must stay out of, once each by realpath.

    They are ``repo``, the checkout that physically holds ``spelled`` and the
    checkouts that hold a link at one of their guarded places on the path as
    spelled (``checkouts_holding``), the last sorted.
    """
    links, holder = checkouts_holding(spelled)
    roots: list[Path] = []
    for root in (repo, holder, *sorted(links)):
        if root is None:
            continue
        if all(os.path.realpath(root) != os.path.realpath(seen) for seen in roots):
            roots.append(root)
    return roots


def _refuse_report_location(spelled: Path, *, repo: Path) -> None:
    """Refuse a report path at or below a place in ``PLACES`` of a root, wherever it leads.

    The roots are ``_report_roots``, found afresh on each call. Each place is
    followed with ``os.path.realpath``, a dangling link and a place that does
    not exist yet included, and its deepest existing entry is compared with
    each existing entry on the report's realpath by ``os.path.samestat``; the
    names below the report's entry must start with the place's remaining
    names, letter case and normalization ignored (``_alike``).
    """
    report_anchors = _anchors(Path(os.path.realpath(spelled)))
    for root in _report_roots(spelled, repo=repo):
        for place in PLACES:
            place_status, place_rest = _anchors(Path(os.path.realpath(root / place)))[0]
            if any(
                os.path.samestat(place_status, status)
                and len(rest) >= len(place_rest)
                and all(_alike(a, b) for a, b in zip(rest, place_rest, strict=False))
                for status, rest in report_anchors
            ):
                raise ValueError(
                    f"report path resolves into {place} of the checkout {root}: {spelled}"
                )


def _refuse_report_directory(spelled: Path) -> None:
    """Refuse a report path whose nearest existing entry above it is not a directory.

    Such an entry, a dangling link or a file, passes the place rule, and the
    write would then fail with ``FileExistsError`` after the repair.
    """
    for entry in spelled.parents:
        if os.path.lexists(entry):
            if not os.path.isdir(entry):
                raise ValueError(
                    f"report path passes through {entry}, which is not a directory: {spelled}"
                )
            return


def _refuse_report_destination(
    report: Path, *, repo: Path, inputs: Mapping[str, Path | None]
) -> None:
    """Refuse a report path in a checkout's protected places, an input, or another file.

    ``report`` is spelled from the working directory when relative. In order:

    1. Location: the roots are ``repo``, the checkout that physically holds
       the path (``checkouts_holding``, by git toplevel and HEAD) and each
       checkout that holds a link at one of its guarded places on the path as
       spelled (the resolver's rules). Each place in ``PLACES`` of each root
       is followed with ``os.path.realpath`` to where it leads, a dangling
       link and a place that does not exist yet included. The path is
       refused when the deepest existing entry on that place's path is the
       same file as an existing entry on the report's realpath, and the names
       below that entry start with the place's remaining names, letter case
       and normalization ignored.
    2. Directory: the nearest existing entry above the path must be a
       directory.
    3. Inputs: the path is refused when it is an existing ``inputs`` file.
    4. Target: ``_refuse_report_target``.

    It opens no file but a regular one, and writes nothing.
    """
    spelled = report if report.is_absolute() else Path.cwd() / report
    _refuse_report_location(spelled, repo=repo)
    _refuse_report_directory(spelled)
    for flag, path in inputs.items():
        if path is None or not os.path.exists(spelled) or not os.path.exists(path):
            continue
        if os.path.samefile(spelled, path):
            raise ValueError(f"report path is the {flag} file this run reads: {spelled}")
    _refuse_report_target(spelled)


def _refuse_report_target(spelled: Path) -> None:
    """Refuse an existing report path that is not a previous report of this script.

    Nothing is checked when nothing is at ``spelled``. The final component is
    read with ``lstat``, so a symlink, dangling or not, is refused; so are a
    directory, anything but a regular file (a FIFO, a socket, a device such as
    ``/dev/null``) and a file with another hard link. Only then is the file
    opened: its text must parse as a JSON object whose keys are exactly
    ``REPORT_KEYS``.
    """
    if not os.path.lexists(spelled):
        return
    status = os.lstat(spelled)
    if stat.S_ISLNK(status.st_mode):
        raise ValueError(f"report path is a symlink: {spelled}")
    if stat.S_ISDIR(status.st_mode):
        raise ValueError(f"report path is a directory: {spelled}")
    if not stat.S_ISREG(status.st_mode):
        raise ValueError(f"report path is not a regular file: {spelled}")
    if status.st_nlink > 1:
        raise ValueError(f"report path is a file with another hard link: {spelled}")
    try:
        held = json.loads(spelled.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        held = None
    if not isinstance(held, dict) or set(held) != REPORT_KEYS:
        raise ValueError(f"report path holds a file this script did not write: {spelled}")


def _write_report(report: Path, value: Mapping[str, object], *, repo: Path) -> None:
    """Write the report without following a link or writing into another file.

    The target rules run again first, since the fetch can create a file at the
    report path (a base's artifact, through a link deeper than the protected
    places) and a link can appear there. The place and directory rules run
    again too, with the roots found afresh, before any directory is made,
    since the fetch can relink a place of any root or turn a directory on the
    path into a link. The JSON goes to a temporary file in the same
    directory, which then replaces the path's directory entry.
    """
    spelled = report if report.is_absolute() else Path.cwd() / report
    _refuse_report_target(spelled)
    _refuse_report_location(spelled, repo=repo)
    _refuse_report_directory(spelled)
    spelled.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=spelled.parent, prefix=f".{spelled.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, spelled)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _scope_prefix(scope: tuple[str, str, str]) -> str:
    return f"{scope[0]}/{scope[1]}"


def _scope_paths(base: Path, scope: tuple[str, str, str]) -> dict[str, Path]:
    jurisdiction, document_class, version = scope
    return {
        "coverage": base / "coverage" / jurisdiction / document_class / f"{version}.json",
        "inventory": base / "inventory" / jurisdiction / document_class / f"{version}.json",
        "provisions": base / "provisions" / jurisdiction / document_class / f"{version}.jsonl",
        "sources": base / "sources" / jurisdiction / document_class / version,
    }


def _release_scopes(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [
        (str(row["jurisdiction"]), str(row["document_class"]), str(row["version"]))
        for row in payload["scopes"]
    ]


def _payload_bases(release_payload: dict[str, Any]) -> set[tuple[str, str, str]]:
    """The scopes the release payload marks ``"layer": "base"``.

    A payload scope whose ``layer`` is anything but ``"base"`` is refused,
    since only the base layer is spelled out.
    """
    payload_bases: set[tuple[str, str, str]] = set()
    for row in release_payload["scopes"]:
        scope = (str(row["jurisdiction"]), str(row["document_class"]), str(row["version"]))
        if "layer" not in row:
            continue
        if row["layer"] != LAYER_BASE:
            raise ValueError(
                f"release scope {'/'.join(scope)} has an invalid layer: {row['layer']!r}"
            )
        payload_bases.add(scope)
    return payload_bases


def _refuse_base_repairs(
    release_payload: dict[str, Any],
    mappings: Mapping[tuple[str, str, str], tuple[str, str, str]],
    base_scopes: Collection[tuple[str, str, str]],
) -> None:
    """Refuse a repair that would re-version a base scope or write over one.

    A base scope is carried into every successor unchanged. A repaired scope
    (a key of ``mappings``) or its new scope (a value) is refused when the
    release payload marks it ``"layer": "base"`` or when it is in
    ``base_scopes``, the scopes that the tracked selectors of one checkout
    mark as bases. A payload scope whose ``layer`` is anything but ``"base"``
    is refused too, since only the base layer is spelled out. Every payload
    scope and every new scope must be spelled as a selector spells it
    (``canonical_scope_key``): a suffix such as ``FIX`` or ``fix/``, or a
    payload base spelled with an upper-case letter, would otherwise name
    another scope's files on APFS or through ``safe_segment`` while comparing
    unequal to it. The check reads and writes nothing, so ``main`` runs it
    before the first move or unlink, once for ``--repo``'s selectors and once
    for each other checkout ``guard_scope_artifacts`` returns. A base is known
    here only once a selector repair reads marks it (the threat model's
    stated limits 2, 3, 11 and 15).
    """
    payload_bases = _payload_bases(release_payload)
    # A name no selector can spell is refused before any comparison.
    for scope in _release_scopes(release_payload):
        canonical_scope_key(*scope)
    for new_scope in sorted(mappings.values()):
        canonical_scope_key(*new_scope)
    bases = payload_bases | set(base_scopes)
    refused = sorted(bases.intersection({*mappings, *mappings.values()}))
    if refused:
        raise ValueError(
            "base scopes are carried unchanged and cannot be repaired: "
            + ", ".join("/".join(scope) for scope in refused)
        )


def _direct_scope(
    conflict: dict[str, Any], scopes: list[tuple[str, str, str]]
) -> tuple[str, str, str] | None:
    matches = [
        scope
        for scope in scopes
        if scope[2] == conflict["version"]
        and (
            conflict["citation_path"] == _scope_prefix(scope)
            or conflict["citation_path"].startswith(_scope_prefix(scope) + "/")
        )
    ]
    if len(matches) > 1:
        raise ValueError(f"ambiguous direct conflict scope: {conflict}")
    return matches[0] if matches else None


def _artifact_index(
    base: Path, scopes: list[tuple[str, str, str]]
) -> tuple[
    dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
    dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
]:
    by_path: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]] = defaultdict(list)
    by_legacy_id: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]] = defaultdict(list)
    for scope in scopes:
        for row in _rows(_scope_paths(base, scope)["provisions"]):
            by_path[str(row["citation_path"])].append((scope, row))
            legacy_ids = {
                str(row.get("id") or ""),
                deterministic_provision_id(str(row["citation_path"])),
            }
            for legacy_id in legacy_ids - {""}:
                by_legacy_id[legacy_id].append((scope, row))
    return by_path, by_legacy_id


def _choose_parent_template(
    citation_path: str,
    scope: tuple[str, str, str],
    child: dict[str, Any],
    by_path: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
) -> dict[str, Any]:
    candidates = by_path.get(citation_path, [])
    if candidates:
        same_kind = [row for candidate_scope, row in candidates if candidate_scope[:2] == scope[:2]]
        if same_kind:
            parent = deepcopy(same_kind[0])
            # Templates from another scope may carry historical explicit ids.
            # A newly materialized container and all of its children use the
            # canonical citation-derived identity together.
            parent["id"] = deterministic_provision_id(citation_path)
            return parent
    level = max(0, int(child.get("level") or 1) - 1)
    label = citation_path.rsplit("/", 1)[-1]
    parent_path = citation_path.rsplit("/", 1)[0] if level else None
    row = deepcopy(child)
    row.update(
        {
            "body": None,
            "citation_label": label,
            "citation_path": citation_path,
            "heading": label,
            "id": deterministic_provision_id(citation_path),
            "kind": "container",
            "level": level,
            "ordinal": 0,
        }
    )
    row.pop("source_id", None)
    if parent_path and parent_path.startswith(_scope_prefix(scope)):
        row["parent_citation_path"] = parent_path
        row["parent_id"] = deterministic_provision_id(parent_path)
    else:
        row.pop("parent_citation_path", None)
        row.pop("parent_id", None)
    metadata = dict(row.get("metadata") or {})
    metadata.update({"kind": "container", "self_containment_container": True})
    row["metadata"] = metadata
    return row


def _close_scope(
    scope: tuple[str, str, str],
    rows: list[dict[str, Any]],
    by_path: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], int]:
    existing = {str(row["citation_path"]): row for row in rows}
    added = 0
    while True:
        missing = sorted(
            {
                str(row["parent_citation_path"])
                for row in existing.values()
                if row.get("parent_citation_path")
                and str(row["parent_citation_path"]) not in existing
            }
        )
        if not missing:
            break
        for parent_path in missing:
            child = next(
                row for row in existing.values() if row.get("parent_citation_path") == parent_path
            )
            parent = _choose_parent_template(parent_path, scope, child, by_path)
            # A template borrowed from another scope must not retain that
            # scope's source path: release validation and provenance require
            # every synthesized container to point into its own source tree.
            source_prefix = f"sources/{scope[0]}/{scope[1]}/{scope[2]}/"
            source_template = next(
                (
                    candidate
                    for candidate in existing.values()
                    if str(candidate.get("source_path") or "").startswith(source_prefix)
                ),
                child,
            )
            for field in ("source_url", "source_path", "source_format"):
                if source_template.get(field):
                    parent[field] = source_template[field]
            canonical_parent_id = deterministic_provision_id(parent_path)
            parent["id"] = canonical_parent_id
            metadata = dict(parent.get("metadata") or {})
            metadata["self_containment_container"] = True
            parent["metadata"] = metadata
            for candidate in existing.values():
                if candidate.get("parent_citation_path") == parent_path:
                    candidate["parent_id"] = canonical_parent_id
            parent["jurisdiction"], parent["document_class"], parent["version"] = scope
            existing[parent_path] = parent
            added += 1
    ordered = sorted(
        existing.values(),
        key=lambda row: (int(row.get("level") or 0), int(row.get("ordinal") or 0), row["citation_path"]),
    )
    return ordered, added


def _inventory_item(row: dict[str, Any], template: dict[str, Any] | None = None) -> dict[str, Any]:
    if template is not None:
        item = deepcopy(template)
        item["citation_path"] = row["citation_path"]
        return item
    item: dict[str, Any] = {"citation_path": row["citation_path"]}
    for field in ("source_url", "source_path", "source_format"):
        if row.get(field):
            item[field] = row[field]
    metadata = dict(row.get("metadata") or {})
    metadata["derived_from"] = "provisions"
    metadata["primary_source"] = bool(metadata.get("primary_source", True))
    if row.get("source_id"):
        metadata["source_id"] = row["source_id"]
    metadata.setdefault("title", row.get("heading") or row.get("citation_label"))
    item["metadata"] = metadata
    return item


def _rewrite_value(value: Any, old_version: str, new_version: str) -> Any:
    if isinstance(value, str):
        if value == old_version:
            return value
        return value.replace(old_version, new_version)
    if isinstance(value, list):
        return [_rewrite_value(item, old_version, new_version) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_value(item, old_version, new_version) for key, item in value.items()}
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ingest_manifest_path(repo: Path, scope: tuple[str, str, str]) -> Path:
    return repo / ".axiom" / "ingest-manifests" / scope[0] / scope[1] / f"{scope[2]}.json"


def _refuse_unsafe_repair_paths(
    base: Path,
    repo: Path,
    mappings: Mapping[tuple[str, str, str], tuple[str, str, str]],
) -> None:
    """Refuse a new scope's path that exists, and a link or shared file in moved sources.

    Repair writes each new scope's files and ingest manifest fresh, so any
    entry already at one of those paths (a file, a directory or a link,
    dangling or not) is refused. ``_rename_sources`` rewrites the moved
    sources with ``write_text``, which follows a symlink and writes into a
    shared inode, so a symlink anywhere in an old scope's sources, and a file
    there with another hard link, are refused. It writes nothing.
    """
    for new_scope in sorted(mappings.values()):
        for path in (
            *_scope_paths(base, new_scope).values(),
            _ingest_manifest_path(repo, new_scope),
        ):
            if os.path.lexists(path):
                raise ValueError(f"repaired scope artifact already exists: {path}")
    for old_scope in sorted(mappings):
        sources = _scope_paths(base, old_scope)["sources"]
        for path in sorted(sources.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"source directory contains a symlink: {sources}")
            if not path.is_file():
                continue
            links = path.stat().st_nlink
            if links > 1:
                raise ValueError(
                    f"scope artifact shares its file with another path: {path} ({links} links)"
                )


def _rewrite_manifest(
    repo: Path,
    old_scope: tuple[str, str, str],
    new_scope: tuple[str, str, str],
) -> None:
    old = _ingest_manifest_path(repo, old_scope)
    new = _ingest_manifest_path(repo, new_scope)
    payload = _rewrite_value(_json(old), old_scope[2], new_scope[2])
    payload["version"] = new_scope[2]
    payload.pop("signature", None)
    paths = _scope_paths(repo / "data/corpus", new_scope)
    files = sorted(path for path in paths["sources"].rglob("*") if path.is_file())
    files += [paths["inventory"], paths["provisions"], paths["coverage"]]
    payload["applied_files"] = [
        {"path": path.relative_to(repo).as_posix(), "sha256": _sha(path)} for path in sorted(files)
    ]
    new.parent.mkdir(parents=True, exist_ok=True)
    _write_json(new, payload)
    if new != old:
        old.unlink()


def _rename_sources(old: Path, new: Path, old_version: str, new_version: str) -> None:
    if new.exists():
        raise FileExistsError(new)
    shutil.move(old, new)
    for path in sorted(new.rglob("*"), reverse=True):
        if old_version not in path.name:
            continue
        path.rename(path.with_name(path.name.replace(old_version, new_version)))
    for path in new.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        replaced = text.replace(old_version, new_version)
        if replaced != text:
            path.write_text(replaced)


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--conflicts", type=Path)
    source.add_argument(
        "--audit-residuals",
        action="store_true",
        help="repair every scope whose own artifact omits a referenced parent",
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--release", type=Path, default=Path("manifests/releases/us-rulespec-2026-07-13.json"))
    parser.add_argument("--suffix", default=DEFAULT_SUFFIX)
    parser.add_argument("--report", type=Path, default=Path("/tmp/cascade-self-containment-report.json"))
    args = parser.parse_args()
    repo = args.repo.resolve()
    base = repo / "data/corpus"
    release_path = repo / args.release
    report_path = args.report if args.report.is_absolute() else Path.cwd() / args.report
    # Before the fetch and before any read or write: a report path in a
    # protected place, below an entry that is not a directory, on an input or
    # over another file stops the run.
    _refuse_report_destination(
        report_path,
        repo=repo,
        inputs={"--release": release_path, "--conflicts": args.conflicts},
    )
    release = _json(release_path)
    scopes = _release_scopes(release)
    # Corpus bytes may live outside git: fetch every scope this repair reads.
    ensure_corpus_scopes([tuple(scope) for scope in scopes], repo=repo)
    by_path, by_legacy_id = _artifact_index(base, scopes)

    repair: set[tuple[str, str, str]] = set()
    assigned = 0
    cascade_parent_paths: dict[str, str] = {}
    if args.audit_residuals:
        conflicts: list[dict[str, Any]] = []
        for scope in scopes:
            rows = _rows(_scope_paths(base, scope)["provisions"])
            local_paths = {str(row["citation_path"]) for row in rows}
            if any(
                row.get("parent_citation_path")
                and str(row["parent_citation_path"]) not in local_paths
                for row in rows
            ) or any(
                (row.get("metadata") or {}).get("self_containment_container")
                for row in rows
            ):
                repair.add(scope)
    else:
        conflicts = _json(args.conflicts)
        if not isinstance(conflicts, list) or len(conflicts) != 27849:
            raise ValueError("expected the complete 27,849-row publisher conflict plan")
    for conflict in conflicts:
        direct = _direct_scope(conflict, scopes)
        if direct is not None:
            repair.add(direct)
            assigned += 1
            continue
        if conflict.get("kind") != "cascade-outside-load":
            raise ValueError(f"unassigned non-cascade conflict: {conflict}")
        owners = {scope for scope, _row in by_legacy_id.get(conflict["staged_parent_id"], [])}
        if owners:
            repair.update(owners)
            assigned += 1
            continue
        inferred_parent = str(conflict["citation_path"]).rsplit("/", 1)[0]
        cascade_parent_paths[str(conflict["staged_parent_id"])] = inferred_parent
        inferred = {
            scope
            for scope, row in by_path.get(inferred_parent, [])
            if scope in scopes
        } | {
            scope
            for scope in scopes
            if any(
                row.get("parent_citation_path") == inferred_parent
                for _candidate_scope, row in by_path.get(str(conflict["citation_path"]), [])
                if _candidate_scope == scope
            )
        }
        if not inferred:
            inferred = {
                scope
                for scope in scopes
                if scope[:2] == tuple(str(conflict["citation_path"]).split("/")[:2])
                and inferred_parent in by_path
            }
        if not inferred:
            # The legacy title container is absent from durable artifacts.  All
            # release scopes containing children of that title must be closed.
            inferred = {
                scope
                for scope in scopes
                if any(
                    candidate_scope == scope and row.get("parent_citation_path") == inferred_parent
                    for candidates in by_path.values()
                    for candidate_scope, row in candidates
                )
            }
        if not inferred:
            raise ValueError(f"cannot assign cascade parent {conflict['staged_parent_id']}")
        repair.update(inferred)
        assigned += 1
    if assigned != len(conflicts):
        raise AssertionError(f"assigned {assigned}/{len(conflicts)} conflicts")

    mappings = {scope: (scope[0], scope[1], f"{scope[2]}-{args.suffix}") for scope in repair}
    # No scope artifact has been moved, rewritten or unlinked yet.
    tracked = tracked_base_scopes(repo / "manifests" / "releases")
    _refuse_base_repairs(release, mappings, tracked)
    # The paths repair reads, moves, writes or unlinks, and the checkouts that
    # hold them, a link on them, --release or the working directory.
    touched = [
        path
        for scope in (*mappings, *mappings.values())
        for path in (*_scope_paths(base, scope).values(), _ingest_manifest_path(repo, scope))
    ]
    known = set(tracked)
    for inventory in guard_scope_artifacts(
        touched,
        releases_dir=repo / "manifests" / "releases",
        holders_of=(release_path, Path.cwd()),
    ):
        extra = tracked_base_scopes(inventory)
        _refuse_base_repairs(release, mappings, extra)
        known |= extra
    _refuse_unsafe_repair_paths(base, repo, mappings)
    refuse_links_into_bases(
        corpus=base,
        bases=known | _payload_bases(release),
        rewritten=[
            path
            for scope in sorted(mappings)
            for path in (
                _scope_paths(base, scope)["provisions"],
                _scope_paths(base, scope)["inventory"],
                _scope_paths(base, scope)["coverage"],
                _ingest_manifest_path(repo, scope),
            )
        ],
        moved=[_scope_paths(base, scope)["sources"] for scope in sorted(mappings)],
        ingest_manifests=repo / ".axiom" / "ingest-manifests",
    )
    total_added = 0
    for old_scope, new_scope in sorted(mappings.items()):
        old_paths = _scope_paths(base, old_scope)
        new_paths = _scope_paths(base, new_scope)
        old_inventory = _json(old_paths["inventory"])
        inventory_by_path = {
            str(item["citation_path"]): item for item in old_inventory.get("items", [])
        }
        rows, added = _close_scope(old_scope, _rows(old_paths["provisions"]), by_path)
        total_added += added
        _rename_sources(old_paths["sources"], new_paths["sources"], old_scope[2], new_scope[2])
        rows = _rewrite_value(rows, old_scope[2], new_scope[2])
        for row in rows:
            row["version"] = new_scope[2]
        _write_rows(new_paths["provisions"], rows)
        old_paths["provisions"].unlink()
        items = []
        for row in rows:
            template = inventory_by_path.get(str(row["citation_path"]))
            if template is None:
                child = next(
                    candidate
                    for candidate in rows
                    if candidate.get("parent_citation_path") == row["citation_path"]
                )
                template = inventory_by_path.get(str(child["citation_path"]))
                if template is None:
                    template = next(
                        (
                            item
                            for path, item in inventory_by_path.items()
                            if path.startswith(f"{row['citation_path']}/")
                        ),
                        None,
                    )
                if template is None:
                    raise ValueError(f"no inventory template for added container {row['citation_path']}")
                for field in ("source_url", "source_path", "source_format"):
                    if child.get(field):
                        row[field] = child[field]
            items.append(_rewrite_value(_inventory_item(row, template), old_scope[2], new_scope[2]))
        _write_json(
            new_paths["inventory"],
            {
                "document_class": new_scope[1],
                "items": items,
                "jurisdiction": new_scope[0],
                "source_count": len(items),
                "version": new_scope[2],
            },
        )
        old_paths["inventory"].unlink()
        coverage = {
            "complete": True,
            "document_class": new_scope[1],
            "duplicate_provision_citations": [],
            "duplicate_source_citations": [],
            "extra_provisions": [],
            "jurisdiction": new_scope[0],
            "matched_count": len(rows),
            "missing_from_provisions": [],
            "provision_count": len(rows),
            "source_count": len(rows),
            "version": new_scope[2],
        }
        _write_json(new_paths["coverage"], coverage)
        old_paths["coverage"].unlink()
        _rewrite_manifest(repo, old_scope, new_scope)

    for row in release["scopes"]:
        old = (row["jurisdiction"], row["document_class"], row["version"])
        if old in mappings:
            row["version"] = mappings[old][2]
    _write_json(release_path, release)

    for path in (repo / "manifests").rglob("*.yaml"):
        text = path.read_text()
        for old, new in mappings.items():
            text = text.replace(f"version: {old[2]}", f"version: {new[2]}")
        path.write_text(text)
    signing = repo / "SIGNING-COMMANDS.md"
    text = signing.read_text()
    for old, new in mappings.items():
        text = text.replace(
            f"sign_scope {old[0]} {old[1]} {old[2]}",
            f"sign_scope {new[0]} {new[1]} {new[2]}",
        )
    signing.write_text(text)

    # Final local assertion: every repaired projection has its complete parent
    # closure, and every plan row was assigned to a freshly identified scope.
    for scope in mappings.values():
        rows = _rows(_scope_paths(base, scope)["provisions"])
        paths = {row["citation_path"] for row in rows}
        missing = [row["citation_path"] for row in rows if row.get("parent_citation_path") not in paths | {None}]
        if missing:
            raise AssertionError(f"scope {scope} still has missing parents: {missing[:5]}")
    report = {
        "assertion": f"PASS: {assigned}/{len(conflicts)} conflict rows assigned; all repaired parent closures complete",
        "conflict_rows": len(conflicts),
        "rows_added": total_added,
        "scopes_repaired": [list(scope) for scope in sorted(mappings.values())],
        "scopes_repaired_count": len(mappings),
        "cascade_parent_paths": cascade_parent_paths,
    }
    _write_report(report_path, report, repo=repo)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
