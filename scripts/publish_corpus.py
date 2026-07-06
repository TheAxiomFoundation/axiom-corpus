#!/usr/bin/env python
"""Publish corpus provision versions that are not yet live in Supabase.

This is the controller-side publication runbook
(docs/agent-ingestion-runbook.md), automated for CI. It:

1. Determines which corpus provision versions are *unpublished* — present in
   the git checkout but not yet an active row in ``corpus.release_scopes``.
   The candidate set comes either from a git diff (the push that triggered the
   workflow) or, for the backlog first run, from an explicit ``--since`` range
   or ``--all`` scan. The published set is read live from the database. This is
   the "git vs live DB" listing mechanism.
2. Publishes each unpublished version in a stable order, one at a time:
   ``sync-r2`` (upload the version's artifacts) then ``load-supabase
   --replace-scope`` (upsert provisions and auto-register an active
   ``release_scopes`` row). ``load-supabase`` refreshes the materialized count
   views as its final step, so ``current_provisions`` catches up per version.
3. Verifies the version landed by reading its ``current_provision_counts`` row
   back from the database.
4. Writes a provision-counts snapshot to ``data/corpus/snapshots/`` per the
   runbook convention. The caller (the workflow) commits it with ``[skip ci]``.

Design guarantees:

* **Publication only.** This script never writes to ``data/corpus`` except the
  snapshot under ``data/corpus/snapshots/`` (which is outside the ingest guard's
  protected prefixes). It never edits provision, source, inventory, or coverage
  artifacts.
* **Idempotent / safe on rerun.** A version already active in the DB is skipped.
  Re-loading a version whose ``release_scopes`` row already exists is a no-op at
  the release-scope layer (``ensure_release_scopes_for_loaded_data`` uses
  ignore-duplicates), so a rerun never resurrects an intentionally-staged or
  intentionally-superseded predecessor version.
* **One failure does not block the rest.** Each version publishes in its own
  try/except; failures are collected and reported, and the process exits
  non-zero at the end so CI turns red, but every independent version still gets
  its chance.

Scope determination detail: the *database* scope of a provisions file is the
distinct ``(jurisdiction, document_class, version)`` triple(s) carried by its
records — exactly what ``load-supabase`` registers. The *R2 artifact* scope is
the file's on-disk ``(jurisdiction, document_class, <path-stem>)``. These
usually coincide but can differ (a file's record ``version`` may not equal its
filename stem); the two publish steps are driven independently so each targets
the correct keyspace.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Imported lazily-friendly: these are cheap, pure-Python corpus helpers.
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    DEFAULT_SERVICE_KEY_ENV,
    fetch_provision_counts,
    list_release_scopes,
    resolve_service_key,
)

PROVISIONS_ROOT = Path("data/corpus/provisions")
SNAPSHOTS_DIR = Path("data/corpus/snapshots")

# A DB scope triple: (jurisdiction, document_class, version).
Scope = tuple[str, str, str]


@dataclass(frozen=True)
class FileScope:
    """A provisions file mapped to its DB scope and its R2 artifact stem."""

    path: Path  # repo-relative path to the .jsonl
    jurisdiction: str
    document_class: str
    version: str  # record ``version`` — the DB release-scope version
    artifact_stem: str  # filename stem — the R2 ``--version`` filter value

    @property
    def db_scope(self) -> Scope:
        return (self.jurisdiction, self.document_class, self.version)


@dataclass
class PublishOutcome:
    scope: Scope
    path: str
    ok: bool
    skipped: bool = False
    reason: str = ""
    r2_uploaded: int | None = None
    provision_count: int | None = None
    steps: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Candidate discovery
# --------------------------------------------------------------------------- #
def _run_git(args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _is_provisions_jsonl(rel: str) -> bool:
    p = Path(rel)
    return (
        rel.startswith("data/corpus/provisions/")
        and p.suffix == ".jsonl"
        and len(p.relative_to(PROVISIONS_ROOT).parts) == 3
    )


def discover_changed_files(base_ref: str, head_ref: str) -> list[Path]:
    """Provisions .jsonl files added/modified between two git refs.

    Uses name-status and keeps Added/Modified/Renamed/Copied (drops Deleted:
    a deletion is never something to publish). Returns repo-relative paths that
    still exist in the working tree.
    """
    out = _run_git(
        ["diff", "--name-status", "--diff-filter=ACMR", f"{base_ref}", f"{head_ref}"]
    )
    files: list[Path] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        # For ACMR, the destination path is the last field (handles renames).
        rel = parts[-1]
        if _is_provisions_jsonl(rel) and Path(rel).exists():
            files.append(Path(rel))
    return files


def discover_all_files() -> list[Path]:
    """Every provisions .jsonl currently in the checkout."""
    return sorted(p for p in PROVISIONS_ROOT.rglob("*.jsonl") if p.is_file())


def file_scopes(paths: Iterable[Path]) -> tuple[list[FileScope], list[tuple[str, str]]]:
    """Map provisions files to their DB scope(s).

    A single file can, in principle, carry more than one
    ``(jurisdiction, document_class, version)`` triple; each becomes its own
    FileScope sharing the file path and artifact stem. Files that cannot be
    parsed as provision records (legacy shapes without jurisdiction/version)
    are returned as skips — they are not loadable by ``load-supabase`` either,
    so they can never be part of the publishable set.
    """
    scopes: list[FileScope] = []
    skipped: list[tuple[str, str]] = []
    for path in paths:
        stem = path.name[: -len(".jsonl")] if path.name.endswith(".jsonl") else path.stem
        try:
            records = load_provisions(path)
        except Exception as exc:  # noqa: BLE001 - report and skip, never crash
            skipped.append((str(path), f"unparseable: {type(exc).__name__}: {exc}"))
            continue
        if not records:
            skipped.append((str(path), "empty"))
            continue
        triples = sorted(
            {
                (r.jurisdiction, r.document_class, r.version)
                for r in records
                if r.version is not None
            }
        )
        if not triples:
            skipped.append((str(path), "no versioned records"))
            continue
        for jurisdiction, document_class, version in triples:
            scopes.append(
                FileScope(
                    path=path,
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    version=version,
                    artifact_stem=stem,
                )
            )
    return scopes, skipped


def fetch_active_scopes(
    *, supabase_url: str, service_key: str, release_name: str = "current"
) -> set[Scope]:
    """The set of version scopes currently active (published) in the DB."""
    rows = list_release_scopes(
        release_name=release_name,
        active=True,
        service_key=service_key,
        supabase_url=supabase_url,
    )
    return {
        (str(r["jurisdiction"]), str(r["document_class"]), str(r["version"]))
        for r in rows
        if r.get("version") is not None
    }


def fetch_all_scope_versions(
    *, supabase_url: str, service_key: str, release_name: str = "current"
) -> set[Scope]:
    """Every version scope with a release_scopes row (active or inactive)."""
    rows = list_release_scopes(
        release_name=release_name,
        active=None,
        service_key=service_key,
        supabase_url=supabase_url,
    )
    return {
        (str(r["jurisdiction"]), str(r["document_class"]), str(r["version"]))
        for r in rows
        if r.get("version") is not None
    }


# --------------------------------------------------------------------------- #
# Publication
# --------------------------------------------------------------------------- #
def _ingest(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Invoke the corpus CLI in-process-equivalent via the console script."""
    return subprocess.run(
        ["axiom-corpus-ingest", *cmd],
        capture_output=True,
        text=True,
    )


def _sync_r2(scope: FileScope, credentials_file: Path | None, workers: int) -> str:
    args = [
        "sync-r2",
        "--base",
        "data/corpus",
        "--jurisdiction",
        scope.jurisdiction,
        "--document-class",
        scope.document_class,
        "--version",
        scope.artifact_stem,
        "--workers",
        str(workers),
        "--apply",
    ]
    if credentials_file is not None:
        args += ["--credentials-file", str(credentials_file)]
    proc = _ingest(args)
    if proc.returncode != 0:
        raise RuntimeError(f"sync-r2 failed (exit {proc.returncode}): {proc.stderr.strip()}")
    try:
        report = json.loads(proc.stdout)
        return str(report.get("uploaded_count", "?"))
    except json.JSONDecodeError:
        return "?"


# Transient PostgREST/edge statuses worth retrying with backoff. Data errors
# (400 bad value, 409 FK violation) are deterministic and never retried.
_TRANSIENT_MARKERS = ("500", "502", "503", "504", "Internal Server Error", "Gateway", "timed out")


def _is_transient(stderr: str) -> bool:
    return any(marker in stderr for marker in _TRANSIENT_MARKERS)


def _load_supabase(
    scope: FileScope,
    chunk_size: int,
    *,
    build_navigation: bool = False,
    retries: int = 2,
    backoff_s: float = 10.0,
) -> None:
    """Load one version's provisions and auto-register its active scope.

    ``--skip-refresh`` defers the (expensive) materialized-view refresh; the
    caller refreshes once after all versions load. ``--replace-scope`` clears
    prior rows for this jurisdiction/document_class version before upsert so a
    re-cut of the same version is exact. Navigation is deferred by default
    (``--no-build-navigation``) and rebuilt once at the end; this halves the
    per-scope work and removes the large-scope nav-rebuild timeout surface.

    Transient 5xx/gateway failures are retried with backoff; deterministic data
    errors (400/409) fail immediately so a defective file is reported, not
    hammered.
    """
    import time

    args = [
        "load-supabase",
        "--provisions",
        str(scope.path),
        "--replace-scope",
        "--skip-refresh",
        "--chunk-size",
        str(chunk_size),
    ]
    args.append("--build-navigation" if build_navigation else "--no-build-navigation")
    last_err = ""
    for attempt in range(retries + 1):
        proc = _ingest(args)
        if proc.returncode == 0:
            return
        last_err = proc.stderr.strip()[-800:]
        if attempt < retries and _is_transient(last_err):
            wait = backoff_s * (attempt + 1)
            print(
                f"  load-supabase transient error (attempt {attempt + 1}); "
                f"retrying in {wait:.0f}s",
                flush=True,
            )
            time.sleep(wait)
            continue
        break
    raise RuntimeError(f"load-supabase failed: {last_err}")


def build_navigation_once(paths: Sequence[Path]) -> None:
    """Rebuild corpus.navigation_nodes for all published files in one pass.

    Called after loads (which ran with ``--no-build-navigation``). Nav is a
    separate tree used by the browser UI; ``current_provisions`` visibility for
    bulk/cloud workers does not depend on it, so a nav failure here is a warning
    rather than a per-scope publication failure.
    """
    if not paths:
        return
    args = ["build-navigation-index", "--replace-scope"]
    for p in paths:
        args += ["--provisions", str(p)]
    proc = _ingest(args)
    if proc.returncode != 0:
        print(
            f"::warning::navigation rebuild failed (provisions are still published): "
            f"{proc.stderr.strip()[-400:]}",
            flush=True,
        )
    else:
        print("Navigation rebuilt for published scopes.", flush=True)


def refresh_analytics(
    *,
    supabase_url: str,
    service_key: str,
    expected_pairs: set[tuple[str, str]] | None = None,
    poll_deadline_s: float = 420.0,
    poll_interval_s: float = 15.0,
) -> None:
    """Refresh corpus materialized views once, after loads.

    ``current_provision_counts`` (a materialized view) only reflects freshly
    loaded rows after this call, so per-version verification must run after it.

    On this production database the refresh (a ``REFRESH MATERIALIZED VIEW``
    with ``statement_timeout = 0``) routinely outlasts the PostgREST edge
    gateway timeout and returns HTTP 504/502/503, even though Postgres keeps
    running it to completion. So a client-side timeout — ``TimeoutError``,
    ``URLError``, or an HTTP gateway error — is not treated as failure: the
    count view is polled until every ``expected_pairs`` scope shows a positive
    count (the refresh landed) or ``poll_deadline_s`` elapses (a real failure).
    With no ``expected_pairs`` the timeout is swallowed and the subsequent
    verify step is the source of truth.
    """
    import time
    import urllib.error

    from axiom_corpus.corpus.supabase import _rest_url, refresh_corpus_analytics

    # Gateway/timeout statuses returned when the refresh outlives the edge
    # proxy but the DB is still working: proxy timeouts and unavailability.
    gateway_timeout_statuses = {408, 429, 502, 503, 504}
    try:
        refresh_corpus_analytics(service_key=service_key, rest_url=_rest_url(supabase_url))
        return
    except urllib.error.HTTPError as exc:
        if exc.code not in gateway_timeout_statuses:
            raise
        print(
            f"::warning::analytics refresh returned HTTP {exc.code} "
            "(edge timeout; DB still refreshing); polling count view for completion",
            flush=True,
        )
    except (TimeoutError, urllib.error.URLError) as exc:
        print(
            f"::warning::analytics refresh client timeout ({exc}); "
            "polling count view for completion",
            flush=True,
        )

    if not expected_pairs:
        return
    deadline = time.monotonic() + poll_deadline_s
    while time.monotonic() < deadline:
        counts = verify_scope_counts(supabase_url=supabase_url, service_key=service_key)
        if all(counts.get(pair, 0) > 0 for pair in expected_pairs):
            print("Refresh confirmed via count-view poll.", flush=True)
            return
        time.sleep(poll_interval_s)
    raise TimeoutError(
        "analytics refresh did not surface expected scopes within "
        f"{poll_deadline_s:.0f}s of polling"
    )


def verify_scope_counts(
    *, supabase_url: str, service_key: str
) -> dict[tuple[str, str], int]:
    """Snapshot per-(jurisdiction, document_class) provision counts once.

    ``current_provision_counts`` aggregates by (jurisdiction, document_class),
    not version; a positive count for a scope's pair confirms the version is
    visible in ``current_provisions`` — the runbook's per-version check.
    Fetched once and shared across all verifications to avoid N round trips.
    """
    rows = fetch_provision_counts(service_key=service_key, supabase_url=supabase_url)
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        j = str(row.get("jurisdiction"))
        dc = str(row.get("document_class"))
        raw = row.get("provision_count")
        counts[(j, dc)] = int(raw) if isinstance(raw, int | str) else 0
    return counts


def sync_and_load_scope(
    scope: FileScope,
    *,
    credentials_file: Path | None,
    r2_workers: int,
    chunk_size: int,
) -> PublishOutcome:
    """Upload artifacts and load provisions for one version (no verify yet)."""
    outcome = PublishOutcome(scope=scope.db_scope, path=str(scope.path), ok=False)
    try:
        outcome.r2_uploaded = int(_sync_r2(scope, credentials_file, r2_workers) or 0)
        outcome.steps["sync-r2"] = f"uploaded {outcome.r2_uploaded}"
    except (RuntimeError, ValueError) as exc:
        outcome.steps["sync-r2"] = f"FAILED: {exc}"
        outcome.reason = str(exc)
        return outcome
    try:
        _load_supabase(scope, chunk_size)
        outcome.steps["load-supabase"] = "ok (refresh deferred)"
    except RuntimeError as exc:
        outcome.steps["load-supabase"] = f"FAILED: {exc}"
        outcome.reason = str(exc)
        return outcome
    # Loaded successfully; verification happens after the shared refresh.
    outcome.ok = True
    return outcome


def snapshot_counts(
    *, supabase_url: str, service_key: str, snapshot_date: str
) -> Path | None:
    out_path = SNAPSHOTS_DIR / f"provision-counts-{snapshot_date}.json"
    args = [
        "snapshot-provision-counts",
        "--output",
        str(out_path),
    ]
    proc = _ingest(args)
    if proc.returncode != 0:
        print(
            f"::warning::snapshot-provision-counts failed (exit {proc.returncode}): "
            f"{proc.stderr.strip()[-400:]}",
            file=sys.stderr,
        )
        return None
    return out_path if out_path.exists() else None


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def build_publish_plan(
    candidate_scopes: list[FileScope],
    *,
    active_scopes: set[Scope],
    all_scope_versions: set[Scope],
) -> tuple[list[FileScope], list[FileScope], list[FileScope]]:
    """Split candidates into (to_publish, already_active, staged/held).

    * already_active — DB already has this version active: skip (idempotent).
    * staged/held — a release_scopes row exists but is inactive: this version
      was explicitly staged or superseded; publishing is a deliberate act, not
      something the automation should do implicitly, so skip.
    * to_publish — no release_scopes row at all: a genuinely new, unpublished
      version. Publish it. Deduplicated by db_scope, keeping stable order.
    """
    to_publish: list[FileScope] = []
    already_active: list[FileScope] = []
    held: list[FileScope] = []
    seen: set[Scope] = set()
    for fs in sorted(
        candidate_scopes, key=lambda s: (s.jurisdiction, s.document_class, s.version, str(s.path))
    ):
        if fs.db_scope in active_scopes:
            already_active.append(fs)
            continue
        if fs.db_scope in all_scope_versions:
            held.append(fs)
            continue
        if fs.db_scope in seen:
            continue
        seen.add(fs.db_scope)
        to_publish.append(fs)
    return to_publish, already_active, held


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--range",
        nargs=2,
        metavar=("BASE", "HEAD"),
        help="Publish provisions files changed between two git refs (a push).",
    )
    source.add_argument(
        "--since",
        metavar="REF",
        help="Publish provisions files changed since REF (REF..HEAD). Use for "
        "the backlog first run over the weekend merge range.",
    )
    source.add_argument(
        "--all",
        action="store_true",
        help="Consider every provisions file in the checkout (full backlog scan).",
    )
    parser.add_argument("--head", default="HEAD", help="Head ref for --since (default HEAD).")
    parser.add_argument("--supabase-url", default=DEFAULT_AXIOM_SUPABASE_URL)
    parser.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    parser.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    parser.add_argument("--credentials-file", type=Path, default=None)
    parser.add_argument("--r2-workers", type=int, default=4)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument(
        "--snapshot-date",
        default=date.today().isoformat(),
        help="Date stamp for the counts snapshot filename (default today, UTC-agnostic).",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Skip writing the provision-counts snapshot (e.g. dry inspection).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the publish plan and exit without publishing or snapshotting.",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        default=None,
        help="Append key=value results here for the workflow (GITHUB_OUTPUT).",
    )
    args = parser.parse_args(argv)

    # --- discover candidates ---
    if args.range:
        candidate_files = discover_changed_files(args.range[0], args.range[1])
        source_desc = f"range {args.range[0]}..{args.range[1]}"
    elif args.since:
        candidate_files = discover_changed_files(args.since, args.head)
        source_desc = f"since {args.since}..{args.head}"
    else:
        candidate_files = discover_all_files()
        source_desc = "all provisions files"

    scopes, unparseable = file_scopes(candidate_files)
    print(f"Candidate source: {source_desc}")
    print(f"Candidate provisions files: {len(candidate_files)}")
    print(f"Candidate versioned scopes: {len(scopes)}")
    if unparseable:
        print(f"Skipped (non-loadable) files: {len(unparseable)}")
        for path, why in unparseable:
            print(f"  - {path}: {why}")

    if not scopes:
        print("No candidate scopes; nothing to publish.")
        _write_github_output(args.github_output, published=0, failed=0, skipped=0, planned=0)
        return 0

    # --- read live DB state ---
    service_key = resolve_service_key(
        args.supabase_url,
        service_key_env=args.service_key_env,
        access_token_env=args.access_token_env,
    )
    active_scopes = fetch_active_scopes(
        supabase_url=args.supabase_url, service_key=service_key
    )
    all_scope_versions = fetch_all_scope_versions(
        supabase_url=args.supabase_url, service_key=service_key
    )

    to_publish, already_active, held = build_publish_plan(
        scopes, active_scopes=active_scopes, all_scope_versions=all_scope_versions
    )

    print(f"\nAlready active (skip): {len(already_active)}")
    print(f"Staged/held inactive (skip, respected): {len(held)}")
    for fs in held:
        print(f"  HELD {fs.jurisdiction}/{fs.document_class} v{fs.version}")
    print(f"To publish: {len(to_publish)}")
    for fs in to_publish:
        print(f"  PUBLISH {fs.jurisdiction}/{fs.document_class} v{fs.version}  ({fs.path})")

    if args.dry_run:
        print("\n--dry-run: not publishing.")
        _write_github_output(
            args.github_output,
            published=0,
            failed=0,
            skipped=len(already_active) + len(held),
            planned=len(to_publish),
        )
        return 0

    if not to_publish:
        print("\nEverything is already published. Nothing to do.")
        if not args.no_snapshot:
            snap = snapshot_counts(
                supabase_url=args.supabase_url,
                service_key=service_key,
                snapshot_date=args.snapshot_date,
            )
            if snap:
                print(f"Snapshot written: {snap}")
        _write_github_output(
            args.github_output,
            published=0,
            failed=0,
            skipped=len(already_active) + len(held),
            planned=0,
        )
        return 0

    # --- phase 1: sync + load each version, resilient (refresh deferred) ---
    outcomes: list[PublishOutcome] = []
    for i, fs in enumerate(to_publish, 1):
        print(
            f"\n=== [{i}/{len(to_publish)}] Publishing "
            f"{fs.jurisdiction}/{fs.document_class} v{fs.version} ===",
            flush=True,
        )
        outcome = sync_and_load_scope(
            fs,
            credentials_file=args.credentials_file,
            r2_workers=args.r2_workers,
            chunk_size=args.chunk_size,
        )
        for step, detail in outcome.steps.items():
            print(f"  {step}: {detail}", flush=True)
        outcomes.append(outcome)

    loaded = [o for o in outcomes if o.ok]

    # --- phase 2: rebuild navigation once for every loaded file ---
    if loaded:
        print("\n=== Rebuilding navigation for published scopes (once) ===", flush=True)
        build_navigation_once(sorted({Path(o.path) for o in loaded}))

    # --- phase 3: one refresh, then per-version count verification ---
    if loaded:
        print("\n=== Refreshing corpus analytics (once) ===", flush=True)
        expected_pairs = {(o.scope[0], o.scope[1]) for o in loaded}
        try:
            refresh_analytics(
                supabase_url=args.supabase_url,
                service_key=service_key,
                expected_pairs=expected_pairs,
            )
            counts = verify_scope_counts(
                supabase_url=args.supabase_url, service_key=service_key
            )
        except Exception as exc:  # noqa: BLE001 - refresh/verify failure is real
            print(f"::error::analytics refresh/verify failed: {exc}", flush=True)
            for o in loaded:
                o.ok = False
                o.reason = f"post-load refresh/verify failed: {exc}"
                o.steps["verify"] = "FAILED (refresh error)"
            counts = {}
        else:
            for o in loaded:
                pair = (o.scope[0], o.scope[1])
                count = counts.get(pair, 0)
                o.provision_count = count
                if count <= 0:
                    o.ok = False
                    o.reason = "zero provisions visible in current_provisions after publish"
                    o.steps["verify"] = "FAILED: zero provisions visible"
                else:
                    o.steps["verify"] = f"{count} provisions visible ({pair[0]}/{pair[1]})"

    published = [o for o in outcomes if o.ok]
    failed = [o for o in outcomes if not o.ok]

    # --- snapshot (reflects everything that landed) ---
    snapshot_path: Path | None = None
    if not args.no_snapshot and published:
        snapshot_path = snapshot_counts(
            supabase_url=args.supabase_url,
            service_key=service_key,
            snapshot_date=args.snapshot_date,
        )
        if snapshot_path:
            print(f"\nSnapshot written: {snapshot_path}")

    # --- summary ---
    print("\n" + "=" * 60)
    print(f"PUBLISHED: {len(published)}   FAILED: {len(failed)}")
    for o in published:
        print(f"  OK   {o.scope[0]}/{o.scope[1]} v{o.scope[2]}  ({o.provision_count} provisions)")
    for o in failed:
        print(f"  FAIL {o.scope[0]}/{o.scope[1]} v{o.scope[2]}  — {o.reason}")

    _write_github_output(
        args.github_output,
        published=len(published),
        failed=len(failed),
        skipped=len(already_active) + len(held),
        planned=len(to_publish),
        snapshot=str(snapshot_path) if snapshot_path else "",
    )

    # Non-zero exit if any version failed, so CI turns red — but only after
    # every independent version had its turn.
    return 1 if failed else 0


def _write_github_output(
    path: Path | None,
    *,
    published: int,
    failed: int,
    skipped: int,
    planned: int,
    snapshot: str = "",
) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"published={published}\n")
        fh.write(f"failed={failed}\n")
        fh.write(f"skipped={skipped}\n")
        fh.write(f"planned={planned}\n")
        fh.write(f"snapshot={snapshot}\n")


if __name__ == "__main__":
    raise SystemExit(main())
