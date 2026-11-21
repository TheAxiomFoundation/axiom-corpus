"""Test-session setup for corpus bytes kept outside git (docs/corpus-storage.md).

Many tests read real corpus artifacts, often every scope of a release selector,
so the suite runs on a fully fetched checkout. Once ``.axiom/corpus-locks``
exists, the session stops before collecting tests if any locked file is absent
and names the command that fetches them (``axiom-corpus-ingest corpus fetch
--all``; on APFS the fetched files are clones that share the cache's disk
blocks).

``AXIOM_CORPUS_PARTIAL_TESTS=1`` runs on a partly fetched checkout instead, for
test runs that do not read corpus data (the PostgreSQL job) or deliberate
subsets. An audit hook then fails the session, naming the files, if a test
tries to open a locked file that is absent. The hook sees only ``open`` in
this interpreter: a test that checks ``exists()``, lists a directory, or reads
from a subprocess is not caught, so real runs use the full tree.

``make_checkout`` builds a small axiom-corpus checkout under ``tmp_path`` with
committed selectors, and ``fixture_git`` runs git inside one with no global or
system configuration and no inherited ``GIT_*`` location variables.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# The variables that point git at another repository, index or working tree.
_GIT_LOCATION_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")
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


def pytest_configure(config: pytest.Config) -> None:
    # Importing axiom_corpus.api.main builds the module's default app, whose
    # archive creates the tables of ./axiom.db when they are missing. Under
    # pytest-xdist every worker imports it while collecting, and concurrent
    # table creation fails with "database is locked"; create them once, here in
    # the controlling process, before any worker starts.
    if not hasattr(config, "workerinput"):
        import axiom_corpus.api.main  # noqa: F401


def pytest_sessionstart(session: pytest.Session) -> None:
    global _locked
    from axiom_corpus.corpus.corpus_locks import load_locks

    locks = load_locks(REPO_ROOT)
    if locks.errors:
        pytest.exit("corpus lock files are invalid: " + "; ".join(locks.errors[:5]), returncode=2)
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


@pytest.fixture(autouse=True)
def _no_real_corpus_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never reach the real R2 bucket through the corpus fetch path.

    Tests that exercise R2 pass an in-memory client explicitly; the resolver's
    default sources would otherwise read the developer's credentials.
    """
    from axiom_corpus.corpus import content_store

    def refuse(cls: type, **_kwargs: object) -> object:
        raise RuntimeError("R2 is disabled in tests")

    monkeypatch.setattr(content_store.R2ObjectStore, "from_environment", classmethod(refuse))


def fixture_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git in ``cwd`` for a test fixture, failing the test on a non-zero exit.

    Global and system configuration are ignored, the author and committer are
    explicit, and the inherited ``GIT_*`` location variables are dropped, so a
    fixture command never reaches another repository.
    """
    environment = {
        key: value for key, value in os.environ.items() if key not in _GIT_LOCATION_VARIABLES
    }
    environment.update(
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Fixture",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_NAME="Fixture",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
    )
    return subprocess.run(
        ["git", *args], cwd=cwd, env=environment, capture_output=True, text=True, check=True
    )


@pytest.fixture
def make_checkout(tmp_path: Path) -> Callable[[str, Mapping[str, Mapping[str, object]]], Path]:
    """Return a factory that builds the checkout ``tmp_path/<name>`` and returns its path.

    The checkout holds ``src/axiom_corpus/__init__.py`` (a marker the resolver
    recognises a checkout by) and each selector at
    ``manifests/releases/<selector name>.json``, all committed on ``main``.
    The resolver's cache of checkout roots is cleared, since it may hold a
    "no checkout" answer for the new directory; a test that later applies a
    sparse pattern clears it again.
    """
    from axiom_corpus.corpus import resolver

    def make(name: str, selectors: Mapping[str, Mapping[str, object]]) -> Path:
        root = tmp_path / name
        package = root / "src" / "axiom_corpus"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        releases = root / "manifests" / "releases"
        releases.mkdir(parents=True)
        for stem, payload in selectors.items():
            (releases / f"{stem}.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        fixture_git(root, "init", "-q", "-b", "main")
        fixture_git(root, "add", "--", "src", "manifests")
        fixture_git(root, "commit", "-q", "-m", "Fixture checkout")
        resolver._repo_root_for_dir.cache_clear()
        return root

    return make
