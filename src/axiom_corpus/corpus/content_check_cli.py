"""``axiom-corpus-ingest content-check``: run the release content checks and keep their baseline.

``content-check SCOPE...`` prints the findings of the named scopes.
``content-check --all --check-baseline`` checks every locked scope against
``manifests/release-content-baseline.json`` and exits 1 on any difference; CI
runs it. ``--update-baseline`` records the named scopes' findings (with
``--all``, rebuilds the whole baseline), which is how a new finding is accepted
on purpose. See docs/release-gate-policy.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from axiom_corpus.corpus.content_quality import CONTENT_CHECK_VERSION, findings_by_code
from axiom_corpus.corpus.corpus_locks import parse_scope_selector, scope_matches
from axiom_corpus.corpus.release_policy import (
    CONTENT_BASELINE_PATH,
    ContentBaseline,
    ContentBaselineEntry,
    compare_content_baseline,
    load_content_baseline,
    scan_scope,
    scope_label,
    write_content_baseline,
)
from axiom_corpus.corpus.releases import ScopeKey
from axiom_corpus.corpus.resolver import (
    CorpusNotMaterializedError,
    cli_repo,
    ensure_corpus_scopes,
    resolver_for,
)

DEFAULT_WORKERS = 4


def add_content_check_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = sub.add_parser(
        "content-check",
        help=(
            "Find rows that are page navigation, chrome-prefixed text, hollow document roots "
            "or LegInfo version pickers; check or update the release content baseline."
        ),
    )
    parser.add_argument(
        "scopes", nargs="*", metavar="SCOPE", help="<jurisdiction>[/<class>[/<version>]]"
    )
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--all", action="store_true", help="Every locked scope.")
    parser.add_argument(
        "--check-baseline",
        action="store_true",
        help="Exit 1 unless the baseline matches fresh scans of the selected scopes.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Record the selected scopes' findings (with --all, rebuild the baseline).",
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--output", type=Path, help="Also write the JSON report here.")
    parser.set_defaults(func=cmd_content_check)


def _selected_scopes(
    locked: Iterable[ScopeKey], selectors: Sequence[str], select_all: bool
) -> list[ScopeKey]:
    parsed = [parse_scope_selector(text) for text in selectors]
    return sorted(
        scope
        for scope in locked
        if select_all or any(scope_matches(scope, selector) for selector in parsed)
    )


def _corpus_base(base: Path, repo: Path) -> Path:
    """``--base`` as given when it exists from here, else under the checkout fetched into."""
    if base.is_absolute():
        return base
    here = Path.cwd() / base
    return here if here.exists() else repo / base


def _scan(arguments: tuple[str, ScopeKey]) -> ContentBaselineEntry:
    base, scope = arguments
    return scan_scope(base, scope)


def scan_scopes(
    base: Path, scopes: Sequence[ScopeKey], *, workers: int = DEFAULT_WORKERS
) -> dict[ScopeKey, ContentBaselineEntry]:
    """Scan ``scopes`` (in parallel when ``workers`` > 1)."""
    jobs = [(str(base), scope) for scope in scopes]
    if workers <= 1 or len(jobs) <= 1:
        return {scope: _scan(job) for scope, job in zip(scopes, jobs, strict=True)}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_scan, jobs, chunksize=8))
    return {entry.scope.key: entry for entry in results}


def _scannable(repo: Path, scopes: Iterable[ScopeKey]) -> list[ScopeKey]:
    """Locked scopes that have both a provisions and an inventory file to check."""
    resolver = resolver_for(repo)
    if resolver is None:
        return []
    locks = resolver.locks.locks
    keep = []
    for scope in scopes:
        paths = {entry.path for entry in locks[scope].files}
        stem = "/".join(scope)
        if {
            f"data/corpus/provisions/{stem}.jsonl",
            f"data/corpus/inventory/{stem}.json",
        } <= paths:
            keep.append(scope)
    return keep


def cmd_content_check(args: argparse.Namespace) -> int:
    if not args.all and not args.scopes:
        print("content-check: name scopes or pass --all", file=sys.stderr)
        return 2
    repo = cli_repo(args)
    resolver = resolver_for(repo) if repo is not None else None
    if repo is None or resolver is None or not resolver.active:
        print(
            "content-check: run inside an axiom-corpus checkout with corpus locks", file=sys.stderr
        )
        return 2
    resolver.require_valid_locks()
    locked = sorted(resolver.locks.locks)
    selected = _scannable(repo, _selected_scopes(locked, args.scopes, args.all))
    unmatched = [
        text
        for text in args.scopes
        if not any(scope_matches(scope, parse_scope_selector(text)) for scope in selected)
    ]
    if unmatched:
        # A mistyped scope must not pass as a clean check of nothing.
        print(
            "content-check: no locked scope with provisions and inventory matches "
            + ", ".join(unmatched),
            file=sys.stderr,
        )
        return 2
    try:
        ensure_corpus_scopes(selected, repo=repo)
    except CorpusNotMaterializedError as exc:
        print(f"corpus: {exc}", file=sys.stderr)
        return 2
    base = _corpus_base(args.base, repo)
    scanned = scan_scopes(base, selected, workers=max(1, int(args.workers)))
    baseline_path = repo / CONTENT_BASELINE_PATH
    baseline = (
        load_content_baseline(baseline_path)
        if baseline_path.exists()
        else ContentBaseline(CONTENT_CHECK_VERSION, {})
    )
    payload: dict[str, object] = {
        "check_version": CONTENT_CHECK_VERSION,
        "scopes_scanned": len(scanned),
        "scopes_with_findings": sum(1 for entry in scanned.values() if entry.findings),
        "findings": dict(
            findings_by_code(finding for entry in scanned.values() for finding in entry.findings)
        ),
    }
    exit_code = 0
    if not args.all:
        payload["scopes"] = {
            scope_label(key): [[f.code, f.path] for f in entry.findings]
            for key, entry in sorted(scanned.items())
        }
    if args.check_baseline:
        if args.all:
            compared = baseline
        else:
            # A partial check compares only the selected scopes' entries.
            chosen = set(selected)
            compared = ContentBaseline(
                baseline.check_version,
                {key: entry for key, entry in baseline.entries.items() if key in chosen},
            )
        differences = compare_content_baseline(
            compared,
            scanned,
            locked_scopes=_scannable(repo, locked) if args.all else selected,
        )
        payload["baseline_differences"] = [
            {"scope": difference.scope, "problem": difference.problem} for difference in differences
        ]
        if differences:
            exit_code = 1
    if args.update_baseline:
        if args.all:
            entries = dict(scanned)
        elif baseline.check_version != CONTENT_CHECK_VERSION:
            print(
                f"content-check: {CONTENT_BASELINE_PATH} was made by {baseline.check_version}; "
                f"rebuild it for {CONTENT_CHECK_VERSION} with --all --update-baseline",
                file=sys.stderr,
            )
            return 2
        else:
            entries = dict(baseline.entries)
            entries.update(scanned)
        write_content_baseline(baseline_path, entries.values())
        payload["baseline_written"] = str(CONTENT_BASELINE_PATH)
        payload["baseline_scopes"] = len(entries)
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if exit_code:
        print(
            f"content-check: {CONTENT_BASELINE_PATH} disagrees with the corpus; fix the extraction "
            "or record the findings with `axiom-corpus-ingest content-check --update-baseline "
            "<scope>` (docs/release-gate-policy.md)",
            file=sys.stderr,
        )
    return exit_code
