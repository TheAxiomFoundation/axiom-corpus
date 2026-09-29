"""Test-session setup for corpus bytes kept outside git (docs/corpus-storage.md).

Many tests read real corpus artifacts, often every scope of a release selector,
so the suite runs on a fully fetched checkout. Once ``.axiom/corpus-locks``
exists, the session stops before collecting tests if any locked file is absent
and names the command that fetches them (``axiom-corpus-ingest corpus fetch
--all``; on APFS the fetched files are clones that share the cache's disk
blocks).

``AXIOM_CORPUS_PARTIAL_TESTS=1`` runs on a partly fetched checkout instead. An
audit hook then records every attempt to open a locked file that is absent and
fails the session, naming the files, so a test cannot pass or skip on data it
never read. The hook only sees this interpreter; tests that read corpus files
from a subprocess fail on their own when the file is absent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PARTIAL_ENV = "AXIOM_CORPUS_PARTIAL_TESTS"
_CORPUS_PREFIX = str(REPO_ROOT / "data" / "corpus") + os.sep

_locked: frozenset[str] = frozenset()
_absent_opens: set[str] = set()


def _audit(event: str, args: tuple[object, ...]) -> None:
    if event != "open" or not _locked or not args:
        return
    raw = args[0]
    if not isinstance(raw, str | bytes | os.PathLike):
        return
    path = os.path.abspath(os.fsdecode(raw))
    if not path.startswith(_CORPUS_PREFIX):
        return
    rel = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
    if rel in _locked and not os.path.exists(path):
        _absent_opens.add(rel)


def pytest_sessionstart(session: pytest.Session) -> None:
    global _locked
    from axiom_corpus.corpus.corpus_locks import load_locks

    locks = load_locks(REPO_ROOT)
    if not locks:
        return
    _locked = frozenset(locks.by_path)
    if os.environ.get(PARTIAL_ENV, "").strip() == "1":
        sys.addaudithook(_audit)
        return
    absent = sorted(path for path in _locked if not (REPO_ROOT / path).is_file())
    if absent:
        pytest.exit(
            f"{len(absent)} locked corpus file(s) are not in this checkout (first: "
            f"{absent[0]}). The tests read real corpus data: run "
            "`axiom-corpus-ingest corpus fetch --all`, or set "
            f"{PARTIAL_ENV}=1 to run a subset on a partial tree.",
            returncode=2,
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _absent_opens:
        return
    listed = "\n".join(sorted(_absent_opens))
    print(
        f"\nTests opened locked corpus files that this checkout has not fetched:\n{listed}\n"
        "Fetch them (`axiom-corpus-ingest corpus fetch --path <file>`) and rerun.",
        file=sys.stderr,
    )
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
