#!/usr/bin/env python
"""Fail if corpus publication has fallen behind main by more than a threshold.

The publish workflow keeps ``corpus.release_scopes`` in step with the
provisions committed to ``main``. This guard is the backstop that makes a
broken pipeline *loud*: if a provisions version has been sitting on ``main``
unpublished for longer than ``--max-lag-hours`` (default 24), exit non-zero so
the repository status turns red. Silence can then never hide a stuck publisher.

What it compares
----------------
* **git side** — every provisions ``(jurisdiction, document_class, version)``
  scope in the checkout, tagged with the author-commit time of the newest
  commit that touched its file (``git log -1 --format=%ct``).
* **published side** — the active version scopes in ``corpus.release_scopes``.
  These are readable with the anon key (RLS exposes only ``active`` rows) as
  well as the service key, so the guard needs no elevated credentials.

A scope is *lagging* when it is not active in the DB and its file was committed
more than ``--max-lag-hours`` ago. Freshly merged versions inside the grace
window are ignored (the publisher is allowed time to run).

Why a grace window and an activation cutoff
-------------------------------------------
Two classes of unpublished-forever scope must not make this guard cry wolf:

1. Versions merged *before* this automation existed. Those are pre-existing
   backlog, not a pipeline failure. ``--since`` (an activation cutoff commit or
   ISO date) excludes any scope whose file has no commit at or after that point.
2. Intentionally-staged or superseded predecessor versions. With the service
   key these appear as inactive ``release_scopes`` rows and are excluded via
   ``--respect-inactive``. Under the anon key those rows are invisible; combine
   ``--since`` with the grace window so only *newly merged* versions can trip
   the guard.

Read-only. Never writes to the DB or to ``data/corpus``.
"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    DEFAULT_SERVICE_KEY_ENV,
    list_release_scopes,
    resolve_service_key,
)

PROVISIONS_ROOT = Path("data/corpus/provisions")
Scope = tuple[str, str, str]


@dataclass(frozen=True)
class GitScope:
    scope: Scope
    path: str
    committed_at: datetime


def _git_commit_epoch(path: Path) -> int | None:
    """Author-commit epoch of the newest commit touching ``path``."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(path)],
        capture_output=True,
        text=True,
    )
    out = result.stdout.strip()
    if result.returncode != 0 or not out:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def _parse_cutoff(since: str | None) -> datetime | None:
    """Resolve ``--since`` to a datetime: a git ref's commit time or ISO date."""
    if not since:
        return None
    # Try as a git ref first.
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", since],
        capture_output=True,
        text=True,
    )
    out = result.stdout.strip()
    if result.returncode == 0 and out:
        try:
            return datetime.fromtimestamp(int(out), tz=UTC)
        except ValueError:
            pass
    # Fall back to an ISO date/datetime.
    try:
        dt = datetime.fromisoformat(since)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError as exc:
        raise SystemExit(
            f"--since could not be parsed as a git ref or ISO date: {since!r}"
        ) from exc


def collect_git_scopes(cutoff: datetime | None) -> list[GitScope]:
    scopes: dict[Scope, GitScope] = {}
    for path in sorted(PROVISIONS_ROOT.rglob("*.jsonl")):
        if not path.is_file():
            continue
        epoch = _git_commit_epoch(path)
        if epoch is None:
            continue
        committed = datetime.fromtimestamp(epoch, tz=UTC)
        if cutoff is not None and committed < cutoff:
            continue
        try:
            records = load_provisions(path)
        except Exception:  # noqa: BLE001 - non-loadable legacy shapes cannot be published
            continue
        for triple in {
            (r.jurisdiction, r.document_class, r.version)
            for r in records
            if r.version is not None
        }:
            existing = scopes.get(triple)
            # Keep the most-recent commit time for a scope spanning files.
            if existing is None or committed > existing.committed_at:
                scopes[triple] = GitScope(
                    scope=triple, path=str(path.relative_to(PROVISIONS_ROOT)), committed_at=committed
                )
    return sorted(scopes.values(), key=lambda g: (g.committed_at, g.scope))


def fetch_scopes(
    *, supabase_url: str, service_key: str, active: bool | None
) -> set[Scope]:
    rows = list_release_scopes(
        release_name="current",
        active=active,
        service_key=service_key,
        supabase_url=supabase_url,
    )
    return {
        (str(r["jurisdiction"]), str(r["document_class"]), str(r["version"]))
        for r in rows
        if r.get("version") is not None
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supabase-url", default=DEFAULT_AXIOM_SUPABASE_URL)
    parser.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    parser.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    parser.add_argument(
        "--max-lag-hours",
        type=float,
        default=24.0,
        help="Fail if a version has been unpublished on main longer than this.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Activation cutoff: a git ref or ISO date. Scopes whose files were "
        "last committed before this are treated as pre-automation backlog and "
        "ignored. Strongly recommended when running under the anon key.",
    )
    parser.add_argument(
        "--respect-inactive",
        action="store_true",
        help="Also exclude versions that have an inactive release_scopes row "
        "(explicitly staged/superseded). Requires a service key that can read "
        "inactive rows; harmless but a no-op under the anon key.",
    )
    args = parser.parse_args(argv)

    cutoff = _parse_cutoff(args.since)
    git_scopes = collect_git_scopes(cutoff)
    if not git_scopes:
        print("No git provisions scopes in the considered window; nothing to check.")
        return 0

    service_key = resolve_service_key(
        args.supabase_url,
        service_key_env=args.service_key_env,
        access_token_env=args.access_token_env,
    )
    active = fetch_scopes(
        supabase_url=args.supabase_url, service_key=service_key, active=True
    )
    excluded_inactive: set[Scope] = set()
    if args.respect_inactive:
        all_rows = fetch_scopes(
            supabase_url=args.supabase_url, service_key=service_key, active=None
        )
        excluded_inactive = all_rows - active

    now = datetime.now(UTC)
    lagging: list[tuple[GitScope, float]] = []
    within_grace = 0
    for gs in git_scopes:
        if gs.scope in active or gs.scope in excluded_inactive:
            continue
        lag_hours = (now - gs.committed_at).total_seconds() / 3600.0
        if lag_hours > args.max_lag_hours:
            lagging.append((gs, lag_hours))
        else:
            within_grace += 1

    considered = len(git_scopes)
    print(f"Considered git scopes (cutoff={args.since or 'none'}): {considered}")
    print(f"Active in DB: {len(active)}")
    if args.respect_inactive:
        print(f"Excluded (inactive/staged): {len(excluded_inactive)}")
    print(f"Unpublished but within {args.max_lag_hours}h grace: {within_grace}")
    print(f"Lagging beyond {args.max_lag_hours}h: {len(lagging)}")

    if not lagging:
        print("\nPublication is current. OK.")
        return 0

    print("\n::error::Corpus publication is lagging. These versions have been on "
          f"main unpublished for more than {args.max_lag_hours}h:")
    for gs, lag in sorted(lagging, key=lambda t: -t[1]):
        print(
            f"  {gs.scope[0]}/{gs.scope[1]} v{gs.scope[2]}  "
            f"lag={lag:.1f}h  file={gs.path}"
        )
    print(
        "\nRun the publish workflow (or `python scripts/publish_corpus.py "
        "--since <ref>`) to clear the backlog."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
