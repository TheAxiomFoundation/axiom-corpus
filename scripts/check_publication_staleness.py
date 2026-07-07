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

Two lagging categories
----------------------
* **never-published** — the scope has *no* ``release_scopes`` row at all (active
  or inactive): the publisher never loaded it. This is the silent-failure the
  guard exists to catch, so it alarms past the grace window **regardless of the
  ``--since`` cutoff** — a committed-but-never-loaded scope is a real gap no
  matter when it merged. (A 2026-07 backlog once sat unpublished behind a
  ``--since`` cutoff set to a *newer* commit; that hole is now closed.)
* **drift** — the scope *has* a ``release_scopes`` row but it is inactive
  (intentionally staged or a superseded predecessor). These respect
  ``--respect-inactive`` and the ``--since`` activation cutoff so pre-automation
  backlog and deliberate staging do not cry wolf.

Distinguishing the two needs to *see* inactive rows, so run with a key that can
read them (a service key, resolved from ``SUPABASE_ACCESS_TOKEN``). Under an
anon key inactive rows are invisible and every not-active scope looks
never-published; ``--never-published-since`` can floor that case.

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


def collect_git_scopes(cutoff: datetime | None = None) -> list[GitScope]:
    """Every provisions scope in the checkout, tagged with its newest commit.

    ``cutoff`` (when given) drops scopes committed before it — used only for the
    drift category. The never-published check calls this with no cutoff so a
    committed-but-never-loaded scope can never be excluded from consideration.
    """
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
        help="Exclude *drift* versions that have an inactive release_scopes row "
        "(explicitly staged/superseded). Requires a service key that can read "
        "inactive rows. Never-published scopes (no row at all) still alarm.",
    )
    parser.add_argument(
        "--never-published-since",
        default=None,
        help="Optional commit/ISO floor for the never-published alarm. Unlike "
        "--since (which only graces drift), never-published scopes alarm "
        "regardless of --since; set this only to suppress a known "
        "pre-automation never-loaded backlog.",
    )
    args = parser.parse_args(argv)

    drift_cutoff = _parse_cutoff(args.since)
    never_cutoff = _parse_cutoff(args.never_published_since)
    # Collect every scope with no cutoff so a committed-but-never-loaded scope is
    # always in view; the cutoffs are applied per category below.
    git_scopes = collect_git_scopes()
    if not git_scopes:
        print("No git provisions scopes found; nothing to check.")
        return 0

    service_key = resolve_service_key(
        args.supabase_url,
        service_key_env=args.service_key_env,
        access_token_env=args.access_token_env,
    )
    active = fetch_scopes(
        supabase_url=args.supabase_url, service_key=service_key, active=True
    )
    # active ∪ inactive — everything that has *ever* been published. A scope
    # absent here was never loaded (never-published); one present-but-not-active
    # is inactive drift. Under an anon key this equals ``active`` (inactive rows
    # are invisible), so run under a service key for exact classification.
    ever_published = fetch_scopes(
        supabase_url=args.supabase_url, service_key=service_key, active=None
    )

    now = datetime.now(UTC)
    lagging_never: list[tuple[GitScope, float]] = []
    lagging_drift: list[tuple[GitScope, float]] = []
    within_grace = 0
    excluded_backlog = 0
    for gs in git_scopes:
        if gs.scope in active:
            continue
        lag_hours = (now - gs.committed_at).total_seconds() / 3600.0
        if gs.scope not in ever_published:
            # Never loaded: a broken/silent publisher. --since does NOT grace it.
            if never_cutoff is not None and gs.committed_at < never_cutoff:
                excluded_backlog += 1
            elif lag_hours > args.max_lag_hours:
                lagging_never.append((gs, lag_hours))
            else:
                within_grace += 1
        else:
            # Has an inactive release_scopes row: staged/superseded predecessor.
            # Graced by --respect-inactive or the pre-automation drift cutoff.
            if args.respect_inactive or (
                drift_cutoff is not None and gs.committed_at < drift_cutoff
            ):
                excluded_backlog += 1
            elif lag_hours > args.max_lag_hours:
                lagging_drift.append((gs, lag_hours))
            else:
                within_grace += 1

    lagging = lagging_never + lagging_drift
    print(f"Considered git scopes: {len(git_scopes)}")
    print(f"Active in DB: {len(active)}  (ever published: {len(ever_published)})")
    print(f"Excluded (pre-automation / staged): {excluded_backlog}")
    print(f"Unpublished but within {args.max_lag_hours}h grace: {within_grace}")
    print(
        f"Lagging beyond {args.max_lag_hours}h: {len(lagging)} "
        f"(never-published: {len(lagging_never)}, drift: {len(lagging_drift)})"
    )

    if not lagging:
        print("\nPublication is current. OK.")
        return 0

    print(
        "\n::error::Corpus publication is lagging. These versions have been on "
        f"main unpublished for more than {args.max_lag_hours}h:"
    )
    for label, group in (("never-published", lagging_never), ("drift", lagging_drift)):
        for gs, lag in sorted(group, key=lambda t: -t[1]):
            print(
                f"  [{label}] {gs.scope[0]}/{gs.scope[1]} v{gs.scope[2]}  "
                f"lag={lag:.1f}h  file={gs.path}"
            )
    print(
        "\nRun the publish workflow (or `python scripts/publish_corpus.py "
        "--since <ref>`) to clear the backlog."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
