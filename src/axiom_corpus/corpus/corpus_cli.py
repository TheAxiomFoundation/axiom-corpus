"""``axiom-corpus-ingest corpus ...``: fetch, lock, push, verify and migrate corpus bytes.

See ``docs/corpus-storage.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.content_store import (
    ContentCache,
    ContentStoreError,
    FetchReport,
    GitBlobSource,
    ObjectSource,
    R2ObjectStore,
    destination_state,
    ensure_cached,
    materialize,
)
from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    LOCK_ROOT,
    PROTECTED_CORPUS_PREFIXES,
    CorpusLock,
    LockEntry,
    LockFormatError,
    LockSet,
    ScopeKey,
    diff_lock_sets,
    hash_tree_blobs,
    load_locks,
    load_locks_at_ref,
    lock_from_worktree,
    locks_from_hashed_blobs,
    parse_scope_selector,
    protected_tree_blobs,
    scope_for_path,
    write_lock,
)
from axiom_corpus.corpus.resolver import _selector_scopes


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the ``corpus`` command group to the ingest CLI."""
    corpus = sub.add_parser(
        "corpus",
        help="Fetch, lock, push, verify and migrate corpus bytes kept outside git.",
        description=(
            "Corpus bytes live in a shared content-addressed cache backed by R2; "
            "git keeps one lock file per scope. See docs/corpus-storage.md."
        ),
    )
    commands = corpus.add_subparsers(dest="corpus_command", required=True, metavar="<action>")

    def common(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--repo", type=Path, default=Path("."))
        parser.add_argument(
            "--cache",
            type=Path,
            help="Content cache root (default: $AXIOM_CORPUS_CACHE or ~/.axiom/corpus-cache).",
        )
        parser.add_argument("--json", action="store_true")

    fetch = commands.add_parser(
        "fetch",
        help="Materialize locked files into data/corpus.",
    )
    common(fetch)
    fetch.add_argument(
        "scopes",
        nargs="*",
        metavar="SCOPE",
        help="<jurisdiction>[/<document_class>[/<version>]]",
    )
    fetch.add_argument("--all", action="store_true", help="Fetch every locked file.")
    fetch.add_argument(
        "--release",
        action="append",
        default=[],
        help="Release selector path or name; fetches its scopes (repeatable).",
    )
    fetch.add_argument(
        "--path",
        action="append",
        default=[],
        help="Corpus file or directory under data/corpus (repeatable).",
    )
    fetch.add_argument(
        "--paths-from",
        type=Path,
        help="File listing corpus paths or scopes, one per line (# comments allowed).",
    )
    fetch.add_argument("--workers", type=int, default=16)
    fetch.add_argument("--verify", action="store_true", help="Hash present files, not just size.")
    fetch.add_argument("--force", action="store_true", help="Replace files that differ from the lock.")
    fetch.add_argument("--no-r2", action="store_true", help="Use only the cache and git objects.")
    fetch.add_argument(
        "--no-cache",
        action="store_true",
        help=(
            "Stream verified bytes straight into data/corpus without keeping cache "
            "objects (CI runners, and filesystems without copy-on-write clones)."
        ),
    )
    fetch.set_defaults(func=_cmd_fetch)

    status = commands.add_parser(
        "status",
        help="Report missing, present, modified and unlocked corpus files.",
    )
    common(status)
    status.add_argument("scopes", nargs="*", metavar="SCOPE")
    status.add_argument("--verify", action="store_true")
    status.set_defaults(func=_cmd_status)

    lock = commands.add_parser(
        "lock",
        help="Hash scopes' files into lock files and cache their bytes.",
    )
    common(lock)
    lock.add_argument("scopes", nargs="+", metavar="SCOPE", help="<jurisdiction>/<class>/<version>")
    lock.add_argument("--push", action="store_true", help="Upload objects R2 lacks.")
    lock.add_argument(
        "--drop-missing",
        action="store_true",
        help="Drop locked files that are absent from the worktree (deliberate deletions).",
    )
    lock.add_argument("--workers", type=int, default=16)
    lock.set_defaults(func=_cmd_lock)

    push = commands.add_parser(
        "push",
        help="Upload locked objects that R2 lacks.",
    )
    common(push)
    push.add_argument("scopes", nargs="*", metavar="SCOPE")
    push.add_argument("--all", action="store_true")
    push.add_argument("--changed-since", metavar="REF", help="Only entries new since REF.")
    push.add_argument("--workers", type=int, default=16)
    push.add_argument("--dry-run", action="store_true")
    push.set_defaults(func=_cmd_push)

    verify = commands.add_parser(
        "verify",
        help="Check lock files; with --remote, check R2 serves every locked object.",
    )
    common(verify)
    verify.add_argument("--ref", help="Read lock files from this git ref instead of the worktree.")
    verify.add_argument("--remote", action="store_true")
    verify.add_argument(
        "--attest",
        action="store_true",
        help=(
            "Require every lock entry to be attested by a valid signed ingest manifest "
            "or by a git blob that history tracked at that path (reads "
            "AXIOM_CORPUS_INGEST_PUBLIC_KEY)."
        ),
    )
    verify.add_argument("--changed-since", metavar="REF")
    verify.add_argument("--workers", type=int, default=32)
    verify.set_defaults(func=_cmd_verify)

    migrate = commands.add_parser(
        "migrate",
        help="Move every tracked protected corpus file into lock files.",
    )
    common(migrate)
    migrate.add_argument("--ref", default="HEAD", help="Tree to migrate (default HEAD).")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument(
        "--seed-cache",
        action="store_true",
        help="Copy the migrated bytes into the content cache from local git objects.",
    )
    migrate.set_defaults(func=_cmd_migrate)


# --------------------------------------------------------------------------- helpers


def _repo(args: argparse.Namespace) -> Path:
    return Path(args.repo).resolve()


def _cache(args: argparse.Namespace) -> ContentCache:
    return ContentCache(Path(args.cache) if args.cache else None)


def _sources(repo: Path, *, r2: bool = True, workers: int = 16) -> list[ObjectSource]:
    sources: list[ObjectSource] = [GitBlobSource(repo)]
    if r2:
        with contextlib.suppress(RuntimeError):  # no credentials: cache and git only
            sources.append(R2ObjectStore.from_environment(workers=workers))
    return sources


def _remote(workers: int) -> R2ObjectStore:
    try:
        return R2ObjectStore.from_environment(workers=workers)
    except RuntimeError as exc:
        raise SystemExit(f"corpus: {exc}") from exc


def _emit(args: argparse.Namespace, payload: dict[str, Any], lines: Iterable[str]) -> None:
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for line in lines:
            print(line)


def _progress(label: str) -> Any:
    last = [-1]

    def report(done: int, total: int) -> None:
        percent = done * 100 // max(total, 1)
        if percent != last[0] and (percent % 10 == 0 or done == total):
            last[0] = percent
            print(f"{label}: {done}/{total}", file=sys.stderr, flush=True)

    return report


def _selected_entries(
    repo: Path,
    locks: LockSet,
    *,
    scopes: Iterable[str],
    select_all: bool,
    releases: Iterable[str] = (),
    paths: Iterable[str] = (),
) -> list[LockEntry]:
    if select_all:
        return list(locks.entries())
    selectors = [parse_scope_selector(text) for text in scopes]
    exact_scopes: list[ScopeKey] = []
    for release in releases:
        found = _selector_scopes(repo, Path(release))
        if not found:
            raise SystemExit(f"corpus: cannot load release selector {release}")
        exact_scopes.extend(found)
    chosen: dict[str, LockEntry] = {}
    for lock in locks.select(selectors, scopes=exact_scopes):
        for entry in lock.files:
            chosen[entry.path] = entry
    for path in paths:
        rel = Path(path).as_posix().rstrip("/")
        matches = locks.entries_under(rel)
        if not matches and rel != CORPUS_BASE:
            raise SystemExit(f"corpus: no locked files at or under {rel}")
        for entry in matches:
            chosen[entry.path] = entry
    return locks.with_whole_source_dirs(chosen.values())


def _read_paths_file(path: Path) -> tuple[list[str], list[str]]:
    """Split a list file into scope selectors and data/corpus paths."""
    scopes: list[str] = []
    paths: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        (paths if line.startswith(f"{CORPUS_BASE}/") else scopes).append(line)
    return scopes, paths


# --------------------------------------------------------------------------- fetch


def _cmd_fetch(args: argparse.Namespace) -> int:
    repo = _repo(args)
    locks = load_locks(repo)
    if locks.errors:
        for error in locks.errors:
            print(f"corpus: {error}", file=sys.stderr)
        return 2
    if not locks:
        _emit(args, {"selected": 0, "lock_files": 0}, ["No corpus lock files; corpus bytes are tracked in git."])
        return 0
    scopes = list(args.scopes)
    paths = list(args.path)
    if args.paths_from:
        extra_scopes, extra_paths = _read_paths_file(args.paths_from)
        scopes.extend(extra_scopes)
        paths.extend(extra_paths)
    if not (args.all or scopes or args.release or paths):
        print("corpus fetch: name scopes, --release, --path, --paths-from or --all", file=sys.stderr)
        return 2
    entries = _selected_entries(
        repo,
        locks,
        scopes=scopes,
        select_all=args.all,
        releases=args.release,
        paths=paths,
    )
    report = materialize(
        repo,
        entries,
        None if args.no_cache else _cache(args),
        _sources(repo, r2=not args.no_r2, workers=args.workers),
        force=args.force,
        verify=args.verify,
        workers=args.workers,
        progress=None if args.json else _progress("corpus fetch"),
    )
    _emit(
        args,
        {"selected": len(entries), **report.to_mapping()},
        _fetch_lines(len(entries), report),
    )
    return 0 if report.ok else 1


def _fetch_lines(selected: int, report: FetchReport) -> list[str]:
    lines = [
        f"{selected} locked file(s) selected: {len(report.materialized)} fetched "
        f"({report.bytes_materialized:,} bytes), {len(report.present)} already present, "
        f"{len(report.modified)} modified, {len(report.failed)} failed."
    ]
    if report.sources:
        lines.append(
            "sources: " + ", ".join(f"{k} {v}" for k, v in sorted(report.sources.items()))
        )
    if report.methods:
        lines.append(
            "placement: " + ", ".join(f"{k} {v}" for k, v in sorted(report.methods.items()))
        )
    lines.extend(f"modified (left as is; --force replaces): {p}" for p in sorted(report.modified)[:20])
    lines.extend(f"FAILED {p}: {why}" for p, why in sorted(report.failed.items())[:20])
    return lines


# --------------------------------------------------------------------------- status


def _cmd_status(args: argparse.Namespace) -> int:
    repo = _repo(args)
    locks = load_locks(repo)
    selectors = [parse_scope_selector(text) for text in args.scopes]
    selected = locks.select(selectors) if selectors else list(locks.locks.values())
    counts = {"present": 0, "missing": 0, "modified": 0}
    modified: list[str] = []
    missing_by_scope: dict[str, int] = {}
    for lock in selected:
        for entry in lock.files:
            state = destination_state(repo / entry.path, entry, verify=args.verify)
            counts[state] += 1
            if state == "modified":
                modified.append(entry.path)
            elif state == "missing":
                key = "/".join(lock.scope)
                missing_by_scope[key] = missing_by_scope.get(key, 0) + 1
    unlocked = _unlocked_files(repo, locks, selectors)
    payload = {
        "lock_files": len(locks.locks),
        "selected_scopes": len(selected),
        **counts,
        "modified_paths": modified,
        "unlocked_paths": unlocked,
        "scopes_with_missing_files": len(missing_by_scope),
        "lock_errors": list(locks.errors),
    }
    lines = [
        f"{len(selected)} scope(s): {counts['present']} present, {counts['missing']} missing, "
        f"{counts['modified']} modified; {len(unlocked)} unlocked file(s) under data/corpus.",
    ]
    lines.extend(f"modified: {p}" for p in modified[:20])
    lines.extend(f"unlocked: {p}" for p in unlocked[:20])
    lines.extend(f"lock error: {e}" for e in locks.errors)
    _emit(args, payload, lines)
    return 1 if locks.errors else 0


def _unlocked_files(repo: Path, locks: LockSet, selectors: list[tuple[str, ...]]) -> list[str]:
    """Protected files present in the worktree that no lock lists."""
    base = repo / CORPUS_BASE
    found: list[str] = []
    for artifact_class in ("sources", "inventory", "provisions", "coverage"):
        root = base / artifact_class
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            if rel in locks.by_path or path.name.startswith("."):
                continue
            scope = scope_for_path(rel)
            if selectors and (scope is None or not any(scope[: len(s)] == s for s in selectors)):
                continue
            found.append(rel)
    return sorted(found)


# --------------------------------------------------------------------------- lock


class LockRefusedError(RuntimeError):
    """A lock rewrite would silently drop files that were never fetched."""


def lock_scopes(
    repo: Path,
    scopes: Iterable[ScopeKey],
    *,
    cache: ContentCache,
    push: bool = False,
    workers: int = 16,
    drop_missing: bool = False,
    deleted: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Write each scope's lock from its worktree files and cache their bytes.

    A scope whose current lock lists files that are absent from the worktree is
    refused unless every absent file is named in ``deleted`` (or
    ``drop_missing``): an unfetched file and a deleted file look the same on
    disk, and only the caller knows which it is. Malformed lock files refuse
    everything, since the current lock of a scope is then unknown.
    """
    existing = load_locks(repo)
    if existing.errors:
        raise LockRefusedError(
            "corpus lock files are invalid; fix them before locking: "
            + "; ".join(existing.errors[:5])
        )
    deleted_paths = set(deleted)
    written: list[dict[str, Any]] = []
    new_entries: list[LockEntry] = []
    for scope in scopes:
        previous = existing.locks.get(scope)
        if previous is not None and not drop_missing:
            absent = [
                entry.path
                for entry in previous.files
                if destination_state(repo / entry.path, entry, verify=False) == "missing"
                and entry.path not in deleted_paths
            ]
            if absent:
                raise LockRefusedError(
                    f"{len(absent)} locked file(s) of {'/'.join(scope)} are not in the "
                    f"worktree (first: {absent[0]}). Fetch the scope first, or name "
                    "deliberate deletions (--deleted-file when signing, --drop-missing "
                    "for corpus lock)."
                )
        lock = lock_from_worktree(repo, scope, previous=previous)
        for entry in lock.files:
            cache.add_file(repo / entry.path, sha256=entry.sha256, size=entry.size)
        write_lock(repo, lock)
        prior = LockSet(locks={scope: previous} if previous else {})
        diff = diff_lock_sets(prior, LockSet(locks={scope: lock}))
        new_entries.extend(diff.added)
        new_entries.extend(after for _before, after in diff.changed)
        written.append(
            {
                "scope": "/".join(scope),
                "lock": lock.relative_path.as_posix(),
                "files": len(lock.files),
                "bytes": lock.total_bytes,
                "added": len(diff.added),
                "changed": len(diff.changed),
                "removed": [entry.path for entry in diff.removed],
            }
        )
    pushed = _push_entries(repo, cache, new_entries, workers=workers, dry_run=False) if push else None
    return written, pushed


def lock_summary_lines(written: list[dict[str, Any]], pushed: dict[str, Any] | None) -> list[str]:
    lines = [
        f"locked {w['scope']}: {w['files']} files, {w['bytes']:,} bytes "
        f"(+{w['added']} ~{w['changed']} -{len(w['removed'])}) -> {w['lock']}"
        for w in written
    ]
    for w in written:
        lines.extend(
            f"removed from lock (the signed ingest manifest must mark it deleted): {p}"
            for p in w["removed"]
        )
    if pushed is not None:
        lines.append(
            f"R2: {pushed['uploaded']} uploaded, {pushed['present']} already present, "
            f"{len(pushed['failed'])} failed"
        )
        lines.extend(f"FAILED {p}: {why}" for p, why in sorted(pushed["failed"].items())[:20])
    return lines


def _cmd_lock(args: argparse.Namespace) -> int:
    repo = _repo(args)
    scopes: list[ScopeKey] = []
    for text in args.scopes:
        parts = parse_scope_selector(text)
        if len(parts) != 3:
            print(
                f"corpus lock: scope must be <jurisdiction>/<class>/<version>: {text}",
                file=sys.stderr,
            )
            return 2
        scopes.append((parts[0], parts[1], parts[2]))
    try:
        written, pushed = lock_scopes(
            repo,
            scopes,
            cache=_cache(args),
            push=args.push,
            workers=args.workers,
            drop_missing=args.drop_missing,
        )
    except (LockRefusedError, FileNotFoundError, LockFormatError, ContentStoreError, OSError) as exc:
        print(f"corpus lock: {exc}", file=sys.stderr)
        return 2
    _emit(args, {"locks": written, "push": pushed}, lock_summary_lines(written, pushed))
    return 1 if pushed and pushed["failed"] else 0


# --------------------------------------------------------------------------- push


def _push_entries(
    repo: Path,
    cache: ContentCache,
    entries: Iterable[LockEntry],
    *,
    workers: int,
    dry_run: bool,
) -> dict[str, Any]:
    unique: dict[str, LockEntry] = {}
    for entry in entries:
        unique.setdefault(entry.sha256, entry)
    remote = _remote(workers)
    local_sources: list[ObjectSource] = [GitBlobSource(repo)]
    result: dict[str, Any] = {"objects": len(unique), "uploaded": 0, "present": 0, "failed": {}}
    missing: list[LockEntry] = []

    def probe(entry: LockEntry) -> tuple[LockEntry, bool]:
        return entry, remote.has(entry.sha256, entry.size)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for future in as_completed([pool.submit(probe, e) for e in unique.values()]):
            entry, present = future.result()
            if present:
                result["present"] += 1
            else:
                missing.append(entry)
    result["missing"] = len(missing)
    result["missing_bytes"] = sum(entry.size for entry in missing)
    if dry_run:
        result["would_upload"] = sorted(entry.path for entry in missing)
        return result

    def upload(entry: LockEntry) -> tuple[LockEntry, bool | str]:
        try:
            worktree = repo / entry.path
            if destination_state(worktree, entry, verify=True) == "present":
                path = worktree
            else:
                path, _source = ensure_cached(entry, cache, local_sources)
            return entry, remote.put(path, sha256=entry.sha256, size=entry.size)
        except (ContentStoreError, OSError, RuntimeError) as exc:
            return entry, str(exc)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for upload_future in as_completed([pool.submit(upload, e) for e in missing]):
            entry, outcome = upload_future.result()
            if isinstance(outcome, str):
                result["failed"][entry.path] = outcome
            elif outcome:
                result["uploaded"] += 1
            else:
                result["present"] += 1
    return result


def _cmd_push(args: argparse.Namespace) -> int:
    repo = _repo(args)
    locks = load_locks(repo)
    if args.changed_since:
        base = load_locks_at_ref(repo, args.changed_since)
        diff = diff_lock_sets(base, locks)
        entries = list(diff.added) + [after for _b, after in diff.changed]
    else:
        if not (args.all or args.scopes):
            print("corpus push: name scopes, --changed-since or --all", file=sys.stderr)
            return 2
        entries = _selected_entries(repo, locks, scopes=args.scopes, select_all=args.all)
    result = _push_entries(repo, _cache(args), entries, workers=args.workers, dry_run=args.dry_run)
    lines = [
        f"{result['objects']} object(s): {result['present']} already in R2, "
        f"{result['missing']} missing ({result['missing_bytes']:,} bytes)"
        + ("" if args.dry_run else f", {result['uploaded']} uploaded, {len(result['failed'])} failed")
    ]
    lines.extend(f"FAILED {p}: {why}" for p, why in sorted(result["failed"].items())[:20])
    _emit(args, result, lines)
    return 1 if result["failed"] else 0


# --------------------------------------------------------------------------- verify


def _cmd_verify(args: argparse.Namespace) -> int:
    repo = _repo(args)
    locks = load_locks_at_ref(repo, args.ref) if args.ref else load_locks(repo)
    problems = list(locks.errors)
    entries = list(locks.entries())
    if args.changed_since:
        base = load_locks_at_ref(repo, args.changed_since)
        diff = diff_lock_sets(base, locks)
        entries = list(diff.added) + [after for _b, after in diff.changed]
    remote_missing: list[str] = []
    if args.remote and entries:
        remote = _remote(args.workers)
        unique: dict[str, LockEntry] = {}
        for entry in entries:
            unique.setdefault(entry.sha256, entry)

        def probe(entry: LockEntry) -> tuple[LockEntry, bool]:
            return entry, remote.has(entry.sha256, entry.size)

        absent: set[str] = set()
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for future in as_completed([pool.submit(probe, e) for e in unique.values()]):
                entry, present = future.result()
                if not present:
                    absent.add(entry.sha256)
        remote_missing = sorted(entry.path for entry in entries if entry.sha256 in absent)
        problems.extend(
            f"R2 lacks objects/sha256/{p_entry.sha256[:2]}/{p_entry.sha256} for {p_entry.path}"
            for p_entry in entries
            if p_entry.sha256 in absent
        )
    attest_issues: list[str] = []
    if args.attest:
        from axiom_corpus.corpus.ingest_manifests import audit_lock_attestation

        attest_issues = audit_lock_attestation(repo, ref=args.ref or "HEAD")
        problems.extend(attest_issues)
    payload = {
        "lock_files": len(locks.locks),
        "entries_checked": len(entries),
        "attest_checked": bool(args.attest),
        "attest_issues": attest_issues,
        "remote_checked": bool(args.remote),
        "remote_missing": remote_missing,
        "problems": problems,
        "ok": not problems,
    }
    lines = [
        f"{len(locks.locks)} lock file(s), {len(entries)} entr(y/ies) checked"
        + (f", {len(remote_missing)} missing from R2" if args.remote else "")
        + (": OK" if not problems else f": {len(problems)} problem(s)")
    ]
    lines.extend(problems[:50])
    _emit(args, payload, lines)
    return 0 if not problems else 1


# --------------------------------------------------------------------------- migrate


def _cmd_migrate(args: argparse.Namespace) -> int:
    repo = _repo(args)
    refusal = _migrate_refusal(repo, args.ref, dry_run=args.dry_run)
    if refusal:
        print(f"corpus migrate: {refusal}", file=sys.stderr)
        return 2
    blobs = protected_tree_blobs(repo, args.ref)
    if not blobs:
        _emit(args, {"migrated": 0}, ["No tracked protected corpus files; nothing to migrate."])
        return 0
    non_regular = [blob.path for blob in blobs if blob.mode not in {"100644", "100755"}]
    if non_regular:
        print("corpus migrate: refusing non-regular tracked files: " + ", ".join(non_regular[:10]), file=sys.stderr)
        return 2
    print(f"corpus migrate: hashing {len(blobs)} tracked file(s)", file=sys.stderr)
    hashed = hash_tree_blobs(repo, blobs)
    moved = locks_from_hashed_blobs(hashed)
    existing = load_locks(repo)
    if existing.errors:
        for error in existing.errors:
            print(f"corpus: {error}", file=sys.stderr)
        return 2
    merged: dict[ScopeKey, CorpusLock] = {}
    replaced: list[str] = []
    for scope, lock in moved.items():
        prior = existing.locks.get(scope)
        if prior is None:
            merged[scope] = lock
            continue
        by_path = {entry.path: entry for entry in prior.files}
        for entry in lock.files:
            if entry.path in by_path and by_path[entry.path].content != entry.content:
                replaced.append(entry.path)
            by_path[entry.path] = entry
        merged[scope] = CorpusLock.from_entries(scope, by_path.values())
    summary = {
        "ref": args.ref,
        "files": len(hashed),
        "bytes": sum(blob.size for blob in hashed.values()),
        "scopes": len(merged),
        "new_lock_files": sum(1 for scope in merged if scope not in existing.locks),
        "replaced_entries": replaced,
        "dry_run": args.dry_run,
    }
    if not args.dry_run:
        for lock in merged.values():
            write_lock(repo, lock)
        _untrack(repo, sorted(hashed))
        subprocess.run(["git", "add", "--", LOCK_ROOT.as_posix()], cwd=repo, check=True)
        if args.seed_cache:
            cache = _cache(args)
            entries = [entry for lock in merged.values() for entry in lock.files]
            report = _seed_from_git(repo, cache, entries)
            summary["seeded"] = report
    lines = [
        f"{'Would migrate' if args.dry_run else 'Migrated'} {summary['files']} file(s) "
        f"({summary['bytes']:,} bytes) into {summary['scopes']} lock file(s) "
        f"({summary['new_lock_files']} new)."
    ]
    if replaced:
        lines.append(f"{len(replaced)} lock entr(y/ies) replaced by the tracked version.")
    if not args.dry_run:
        lines.append(
            "The files stay in the worktree, now git-ignored. Review with `git status`, "
            "then commit the removals and lock files together."
        )
    _emit(args, summary, lines)
    return 0


def _migrate_refusal(repo: Path, ref: str, *, dry_run: bool) -> str | None:
    """Why migrating now would lose work, or None.

    The locks are built from the tree at ``ref`` while the removal edits the
    index, so both must agree: ``ref`` is HEAD, and no protected path has
    staged or unstaged changes (otherwise an edit would silently leave version
    control).
    """
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)

    head = git("rev-parse", "HEAD").stdout.strip()
    target = git("rev-parse", f"{ref}^{{commit}}").stdout.strip()
    if not target:
        return f"cannot resolve {ref}"
    if target != head and not dry_run:
        return f"{ref} is not HEAD; check it out first (or use --dry-run)"
    prefixes = [prefix.rstrip("/") for prefix in PROTECTED_CORPUS_PREFIXES]
    if dry_run:
        return None
    for label, extra in (("staged", ["--cached"]), ("unstaged", [])):
        diff = git("diff", "--name-only", *extra, "HEAD", "--", *prefixes)
        if diff.returncode != 0:
            return f"cannot read {label} changes: {diff.stderr.strip()}"
        changed = [line for line in diff.stdout.splitlines() if line]
        if changed:
            return (
                f"{len(changed)} protected corpus file(s) have {label} changes (first: "
                f"{changed[0]}); commit or restore them before migrating"
            )
    return None


def _untrack(repo: Path, paths: list[str]) -> None:
    """``git rm --cached`` in chunks (keeps the worktree files)."""
    for start in range(0, len(paths), 2000):
        chunk = paths[start : start + 2000]
        subprocess.run(
            # --sparse: the paths may sit outside a sparse checkout's cone.
            ["git", "rm", "--cached", "--sparse", "--quiet", "--", *chunk],
            cwd=repo,
            check=True,
        )


def _seed_from_git(repo: Path, cache: ContentCache, entries: list[LockEntry]) -> dict[str, int]:
    """Fill the cache from local git objects in one ``cat-file`` stream."""
    from axiom_corpus.corpus.corpus_locks import iter_blob_contents

    wanted: dict[str, LockEntry] = {}
    for entry in entries:
        if entry.git_blob and not cache.contains(entry.sha256, entry.size):
            wanted.setdefault(entry.git_blob, entry)
    seeded = 0
    for oid, chunks in iter_blob_contents(repo, sorted(wanted)):
        entry = wanted[oid]
        cache.add_stream(chunks, sha256=entry.sha256, size=entry.size)
        seeded += 1
    return {"seeded": seeded}

