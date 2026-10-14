"""End-to-end runs of scripts/sign_release_scopes.sh in a throwaway git repository.

The script calls ``python3`` and ``uv run axiom-corpus-ingest``. Shims on PATH run both
with this interpreter, so sign-ingest-manifest, guard-ingested and validate-release are
the real commands; the ``uv`` shim also logs each subcommand line it runs, and on request
fails a signing or a validation, or interrupts the run during validation as Ctrl-C does.
A commit-msg hook can reject one of the script's commits, or hold it while a test sends
the script a signal. A ``git`` shim can hold the cleanup while a test sends another, or
fail the cleanup's first unstage. The resumability tests use these to stop a run at each
step, then check that the same command, re-run, cuts the selector. A property-based test
runs the Python of step 2's plan, read out of the script, against manifests the real
signer wrote.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem

SCRIPT = Path(__file__).parents[1] / "scripts/sign_release_scopes.sh"
JURISDICTION = "us-co"
DOCUMENT_CLASS = "policy"
RELEASED = "2026-09-01"
UNRELEASED = ("2026-09-24-a", "2026-09-24-b")
PREDECESSOR = "manifests/releases/test-rel-1.json"
DRAFT = "docs/ingest-runs/test-rel-2.selector.json"
TARGET = "manifests/releases/test-rel-2.json"
MANIFEST_DIR = f".axiom/ingest-manifests/{JURISDICTION}/{DOCUMENT_CLASS}"
ADD = "Add test-rel-2 artifacts (unsigned data commit)"
SIGN = "Sign test-rel-2 scopes"
CUT = "Cut test-rel-2"
# The command the script signs a scope with when no manifests/*.yaml carries its version.
SCRIPT_COMMAND = (
    "axiom-corpus-ingest extract-official-documents --base data/corpus --version {version}"
    " (run note: docs/ingest-runs/2026-09-10-*.md)"
)
# Where step 2 puts a manifest it signs again until step 3 moves it into place.
RESIGN_DIRS = ".sign-release-scopes.*"

PYTHON3_SHIM = """#!/bin/sh
exec "@PYTHON@" "$@"
"""
UV_SHIM = """#!/bin/sh
# uv run axiom-corpus-ingest <subcommand> ...: log the call, then run the real CLI.
[ "$1" = run ] && [ "$2" = axiom-corpus-ingest ] || { echo "unexpected uv call: $*" >&2; exit 97; }
shift 2
printf '%s\\n' "$*" >> "$UV_CALL_LOG"
if [ "$1" = sign-ingest-manifest ] && [ -n "${FAIL_SIGN_VERSION:-}" ]; then
  case " $* " in *" --version $FAIL_SIGN_VERSION "*) echo "simulated signing failure" >&2; exit 1 ;; esac
fi
if [ "$1" = validate-release ] && [ -n "${FAIL_VALIDATE_RELEASE:-}" ]; then
  # Ctrl-C signals the whole foreground process group: the script and this shim.
  [ "$FAIL_VALIDATE_RELEASE" != interrupt ] || kill -INT 0
  if [ "$FAIL_VALIDATE_RELEASE" = hold ]; then  # until a signal ends it (60 s at most)
    : > "$HOLD_DIR/held"
    i=0
    while [ "$i" -lt 600 ]; do sleep 0.1; i=$((i + 1)); done
  fi
  echo "simulated validation failure" >&2; exit 1
fi
exec "@PYTHON@" -m axiom_corpus.corpus.cli "$@"
"""
COMMIT_MSG_HOOK = """#!/bin/sh
# Hold the commit whose subject is $HOLD_COMMIT: create $HOLD_DIR/held, then wait (up to
# 60 s) for $HOLD_DIR/release. Reject the one whose subject is $FAIL_COMMIT, as a failing
# hook would, after waiting $FAIL_COMMIT_DELAY seconds (default 0).
subject=$(head -n 1 "$1")
if [ -n "${HOLD_COMMIT:-}" ] && [ "$subject" = "$HOLD_COMMIT" ]; then
  : > "$HOLD_DIR/held"
  i=0
  while [ ! -e "$HOLD_DIR/release" ] && [ "$i" -lt 600 ]; do sleep 0.1; i=$((i + 1)); done
fi
[ -n "${FAIL_COMMIT:-}" ] && [ "$subject" = "$FAIL_COMMIT" ] || exit 0
echo "simulated commit failure" >&2
sleep "${FAIL_COMMIT_DELAY:-0}"
exit 1
"""
GIT_SHIM = """#!/bin/sh
# While $HOLD_CLEANUP is set, hold on_exit's check that the selector is committed
# (`git cat-file -e HEAD:<target>`): create $HOLD_DIR/cleanup, then wait (up to 60 s) for
# $HOLD_DIR/release. Python, not sh, does the waiting: with sh, whether a SIGINT ended
# the hold depended on timing.
if [ -n "${HOLD_CLEANUP:-}" ] && [ "$*" = "cat-file -e HEAD:@TARGET@" ]; then
  exec "@PYTHON@" -c '
import os, sys, time
hold, git, args = sys.argv[1], sys.argv[2], sys.argv[3:]
open(os.path.join(hold, "cleanup"), "w").close()
deadline = time.monotonic() + 60
while not os.path.exists(os.path.join(hold, "release")) and time.monotonic() < deadline:
    time.sleep(0.1)
os.execv(git, [git, *args])
' "$HOLD_DIR" "@GIT@" "$@"
fi
# While $FAIL_RESET_ONCE is set, fail on_exit's first unstage, as a signal to a git that
# holds index.lock does.
if [ -n "${FAIL_RESET_ONCE:-}" ] && [ "$*" = "reset -q -- data/corpus .axiom/ingest-manifests @TARGET@" ] \\
  && [ ! -e "$HOLD_DIR/reset-failed" ]; then
  : > "$HOLD_DIR/reset-failed"
  echo "fatal: simulated index.lock write error" >&2
  exit 128
fi
# While $FAIL_CHECKOUT_ONCE is set, fail on_exit's first put-back of committed manifests
# the same way.
if [ -n "${FAIL_CHECKOUT_ONCE:-}" ] && [ "$*" = "checkout -q -- .axiom/ingest-manifests" ] \\
  && [ ! -e "$HOLD_DIR/checkout-failed" ]; then
  : > "$HOLD_DIR/checkout-failed"
  echo "fatal: simulated index.lock write error" >&2
  exit 128
fi
exec "@GIT@" "$@"
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _b64(raw: bytes) -> str:
    return b64encode(raw).decode("ascii")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _selector(name: str, versions: list[str]) -> dict:
    return {
        "name": name,
        "scopes": [
            {"jurisdiction": JURISDICTION, "document_class": DOCUMENT_CLASS, "version": version}
            for version in versions
        ],
    }


def _write_scope(repo: Path, version: str) -> None:
    """Write one complete scope's sources, inventory, provisions and coverage."""
    store = CorpusArtifactStore(repo / "data/corpus")
    citation_path = f"{JURISDICTION}/{DOCUMENT_CLASS}/doc-{version}"
    source = store.source_path(JURISDICTION, DOCUMENT_CLASS, version, "source.html")
    source_sha = store.write_text(source, f"<p>Text {version}.</p>")
    source_path = source.relative_to(store.root).as_posix()
    store.write_inventory(
        store.inventory_path(JURISDICTION, DOCUMENT_CLASS, version),
        [
            SourceInventoryItem(
                citation_path=citation_path, source_path=source_path, sha256=source_sha
            )
        ],
    )
    store.write_provisions(
        store.provisions_path(JURISDICTION, DOCUMENT_CLASS, version),
        [
            ProvisionRecord(
                jurisdiction=JURISDICTION,
                document_class=DOCUMENT_CLASS,
                citation_path=citation_path,
                version=version,
                body=f"Text {version}.",
                source_path=source_path,
                source_as_of="2026-09-24",
                expression_date="2026-09-24",
            )
        ],
    )
    store.write_json(
        store.coverage_path(JURISDICTION, DOCUMENT_CLASS, version),
        {
            "complete": True,
            "source_count": 1,
            "provision_count": 1,
            "matched_count": 1,
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )


def _ingest_pr(
    repo: Path,
    versions: tuple[str, ...],
    *,
    command: str = "test ingest {version}",
    extra_args: tuple[str, ...] = (),
) -> None:
    """Commit scopes, then their manifests signed against that commit, as an ingest PR does."""
    for version in versions:
        _write_scope(repo, version)
    _git(repo, "add", "-f", "data/corpus")
    _git(repo, "commit", "-qm", "Add artifacts")
    for version in versions:
        exit_code = main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                JURISDICTION,
                "--document-class",
                DOCUMENT_CLASS,
                "--version",
                version,
                "--command",
                command.format(version=version),
                *(arg.format(version=version) for arg in extra_args),
            ]
        )
        assert exit_code == 0
    _git(repo, "add", ".axiom/ingest-manifests")
    _git(repo, "commit", "-qm", "Sign artifacts")


def _default_signals() -> None:
    # Bash cannot trap a signal that was ignored when it started, and a background or
    # nohup launch of pytest leaves SIGINT or SIGHUP ignored.
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, signal.SIG_DFL)


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    # In a session of its own, a simulated Ctrl-C reaches the script, never pytest.
    return subprocess.run(
        ["bash", str(SCRIPT), DRAFT, PREDECESSOR],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        start_new_session=True,
        preexec_fn=_default_signals,
    )


def _uv_calls() -> list[str]:
    log = Path(os.environ["UV_CALL_LOG"])
    return log.read_text().splitlines() if log.exists() else []


def _signed_versions() -> list[str]:
    """The --version of every sign-ingest-manifest call so far, failed ones included."""
    return [
        call.split(" --version ")[1].split()[0]
        for call in _uv_calls()
        if call.startswith("sign-ingest-manifest ")
    ]


def _branch_subjects(repo: Path, start: str) -> list[str]:
    return _git(repo, "log", "--format=%s", f"{start}..HEAD").splitlines()


def _assert_resumable(repo: Path) -> None:
    """What the next run's preflight needs: a clean tracked tree and no selector file."""
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert not (repo / TARGET).exists()
    assert not list(repo.glob(RESIGN_DIRS))


def _assert_cut(
    repo: Path,
    result: subprocess.CompletedProcess[str],
    start: str,
    history: tuple[str, ...] = (CUT, SIGN, ADD),
) -> None:
    """The run cut the selector, leaving only these commits (newest first) since start."""
    assert result.returncode == 0, result.stdout + result.stderr
    assert _branch_subjects(repo, start) == list(history)
    assert json.loads((repo / TARGET).read_text()) == json.loads((repo / DRAFT).read_text())
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert not list(repo.glob(RESIGN_DIRS))


def _install_commit_msg_hook(repo: Path) -> None:
    hook = repo / ".git/hooks/commit-msg"
    hook.write_text(COMMIT_MSG_HOOK)
    hook.chmod(0o755)


def _cut_release_branch(repo: Path) -> str:
    """Write the unreleased scopes untracked and unsigned, the usual starting point."""
    for version in UNRELEASED:
        _write_scope(repo, version)
    _set_main_refs(repo, "origin-main")
    _git(repo, "checkout", "-qb", "release")
    return _git(repo, "rev-parse", "HEAD")


# The branch point each layout of main refs leaves the self-check (None: it is skipped).
GUARD_BASES = {
    "origin-main": "origin/main",
    "unrelated-origin-main": "main",
    "local-main": "main",
    "no-main": None,
}


def _set_main_refs(repo: Path, layout: str) -> None:
    """Arrange origin/main and main, from the main branch, before the release branch is cut."""
    if layout == "origin-main":
        _git(repo, "update-ref", "refs/remotes/origin/main", "main")
    elif layout == "unrelated-origin-main":  # e.g. a shallow refetch: no merge base with HEAD
        orphan = _git(repo, "commit-tree", _git(repo, "mktree"), "-m", "Unrelated root")
        _git(repo, "update-ref", "refs/remotes/origin/main", orphan)
    elif layout == "no-main":
        _git(repo, "branch", "-m", "main", "trunk")
    else:
        assert layout == "local-main"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository whose main holds one released, signed scope, its selector and the draft."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {"python3": PYTHON3_SHIM, "uv": UV_SHIM}.items():
        shim = bin_dir / name
        shim.write_text(body.replace("@PYTHON@", sys.executable))
        shim.chmod(0o755)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = Test\n\temail = test@example.com\n")
    for key in [key for key in os.environ if key.startswith("GIT_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("UV_CALL_LOG", str(tmp_path / "uv-calls.log"))
    for name in ("FAIL_SIGN_VERSION", "FAIL_VALIDATE_RELEASE", "FAIL_COMMIT"):
        monkeypatch.delenv(name, raising=False)
    key = Ed25519PrivateKey.generate()
    monkeypatch.setenv(
        "AXIOM_CORPUS_INGEST_PRIVATE_KEY",
        _b64(
            key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        ),
    )
    monkeypatch.setenv(
        "AXIOM_CORPUS_INGEST_PUBLIC_KEY",
        _b64(
            key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ),
    )

    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("data/\n")  # as in this repository: artifacts are force-added
    _git(root, "add", ".gitignore")
    _git(root, "commit", "-qm", "Initial commit")
    _ingest_pr(root, (RELEASED,))
    _write_json(root / PREDECESSOR, _selector("test-rel-1", [RELEASED]))
    _write_json(root / DRAFT, _selector("test-rel-2", [RELEASED, *UNRELEASED]))
    _git(root, "add", PREDECESSOR, DRAFT)
    _git(root, "commit", "-qm", "Track test-rel-1 and the test-rel-2 draft")
    return root


@pytest.mark.parametrize("guard", [*GUARD_BASES, "no-public-key", "no-private-key"])
def test_cuts_the_selector_when_every_unreleased_scope_is_already_signed(
    repo: Path, monkeypatch: pytest.MonkeyPatch, guard: str
) -> None:
    # As in #742: the ingest PR committed and signed its scopes, so steps 1-3 commit nothing.
    _ingest_pr(repo, UNRELEASED)
    layout = guard if guard in GUARD_BASES else "origin-main"
    _set_main_refs(repo, layout)
    if guard == "no-public-key":
        monkeypatch.delenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY")
    elif guard == "no-private-key":  # nothing to sign, so the script does not ask for it
        monkeypatch.delenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY")
    _git(repo, "checkout", "-qb", "release")
    start = _git(repo, "rev-parse", "HEAD")

    result = _run(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    assert "artifacts already committed; skipping data commit" in out
    for version in UNRELEASED:
        assert (
            f"already signed, keeping existing manifest: {JURISDICTION}/{DOCUMENT_CLASS}/{version}"
            in out
        )
    assert "signed manifests already committed; skipping sign commit" in out
    assert "sign commit:" not in out
    assert f"selector commit: {_git(repo, 'rev-parse', '--short', 'HEAD')}" in out
    assert _branch_subjects(repo, start) == ["Cut test-rel-2"]
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines() == [TARGET]
    assert json.loads((repo / TARGET).read_text()) == json.loads((repo / DRAFT).read_text())
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""

    calls = _uv_calls()
    assert not [call for call in calls if call.startswith("sign-ingest-manifest ")]
    assert calls[-1].startswith(f"validate-release --base data/corpus --release {TARGET} ")
    base = None if guard == "no-public-key" else GUARD_BASES[layout]
    if base is None:
        assert len(calls) == 1
        assert "guard-ingested: ok" not in out
        skipped = {
            "no-public-key": "AXIOM_CORPUS_INGEST_PUBLIC_KEY not set;",
            "no-main": "neither origin/main nor main shares history with HEAD;",
        }[guard]
        assert f"{skipped} CI will run guard-ingested on the PR" in out
    else:
        assert calls[:-1] == [f"guard-ingested --base-ref {base} --head-ref HEAD"]
        assert f"guard-ingested: checking {base}...HEAD" in out
        # The branch adds no protected artifact before the selector commit.
        assert "No protected corpus artifact changes." in out
        assert "guard-ingested: ok" in out


@pytest.mark.parametrize("layout", ["origin-main", "local-main"])
def test_resumes_after_a_run_that_stopped_while_signing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    for version in UNRELEASED:
        _write_scope(repo, version)  # untracked and unsigned, the usual starting point
    _set_main_refs(repo, layout)
    _git(repo, "checkout", "-qb", "release")
    start = _git(repo, "rev-parse", "HEAD")

    monkeypatch.setenv("FAIL_SIGN_VERSION", UNRELEASED[1])
    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert "simulated signing failure" in first.stderr
    assert _branch_subjects(repo, start) == ["Add test-rel-2 artifacts (unsigned data commit)"]
    assert (repo / MANIFEST_DIR / f"{UNRELEASED[0]}.json").is_file()
    assert not (repo / MANIFEST_DIR / f"{UNRELEASED[1]}.json").exists()

    monkeypatch.delenv("FAIL_SIGN_VERSION")
    second = _run(repo)

    assert second.returncode == 0, second.stdout + second.stderr
    out = second.stdout
    assert "artifacts already committed; skipping data commit" in out
    assert (
        f"already signed, keeping existing manifest: {JURISDICTION}/{DOCUMENT_CLASS}/{UNRELEASED[0]}"
        in out
    )
    assert "sign commit:" in out
    # <base>...HEAD reaches the first run's data commit, so the guard checks its artifacts.
    base = GUARD_BASES[layout]
    assert [call for call in _uv_calls() if call.startswith("guard-ingested ")] == [
        f"guard-ingested --base-ref {base} --head-ref HEAD"
    ]
    assert "All changed corpus artifacts have signed ingest manifests." in out
    assert "guard-ingested: ok" in out
    assert _branch_subjects(repo, start) == [
        "Cut test-rel-2",
        "Sign test-rel-2 scopes",
        "Add test-rel-2 artifacts (unsigned data commit)",
    ]
    assert _git(repo, "show", "--name-only", "--format=", "HEAD~1").splitlines() == [
        f"{MANIFEST_DIR}/{version}.json" for version in UNRELEASED
    ]


def test_stops_before_cutting_when_guard_ingested_fails(repo: Path) -> None:
    _set_main_refs(repo, "origin-main")
    _git(repo, "checkout", "-qb", "release")
    _ingest_pr(repo, UNRELEASED)
    provisions = (
        repo / f"data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{UNRELEASED[0]}.jsonl"
    )
    provisions.write_text(provisions.read_text().replace("Text", "Edited text"))
    _git(repo, "commit", "-qam", "Edit a scope after signing it")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "sha256 does not match ingest manifest" in result.stdout
    assert f"guard-ingested failed; not cutting {TARGET}" in result.stderr
    assert "guard-ingested: ok" not in result.stdout
    assert _git(repo, "rev-parse", "HEAD") == head
    assert not (repo / TARGET).exists()
    assert not [call for call in _uv_calls() if call.startswith("validate-release ")]


def test_refuses_to_run_on_main(repo: Path) -> None:
    # On main itself, main...HEAD is empty, so the self-check would verify nothing.
    _ingest_pr(repo, UNRELEASED)
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "on main; cut a release branch from main first" in result.stderr
    assert _git(repo, "rev-parse", "HEAD") == head
    assert not (repo / TARGET).exists()
    assert _uv_calls() == []


# Each defect is in the second scope: the old step 1 had already staged the first.
# defect: (the artifact, under data/corpus/, and the problem step 1 reports for it)
STEP_1_DEFECTS = {
    "incomplete-coverage": ("coverage/{scope}.json", "coverage not complete: {path}"),
    "unreadable-coverage": (
        "coverage/{scope}.json",
        "unreadable {path}: Expecting value: line 1 column 1 (char 0)",
    ),
    "no-coverage": ("coverage/{scope}.json", "missing {path}"),
    "no-inventory": ("inventory/{scope}.json", "missing {path}"),
    "no-provisions": ("provisions/{scope}.jsonl", "missing {path}"),
    "no-sources": ("sources/{scope}", "missing {path}"),
    "empty-sources": ("sources/{scope}", "empty {path}"),  # git cannot commit it
}


@pytest.mark.parametrize("defect", STEP_1_DEFECTS)
def test_resumes_after_step_1_finds_a_scope_not_ready(repo: Path, defect: str) -> None:
    start = _cut_release_branch(repo)
    artifact, problem = STEP_1_DEFECTS[defect]
    path = "data/corpus/" + artifact.format(
        scope=f"{JURISDICTION}/{DOCUMENT_CLASS}/{UNRELEASED[1]}"
    )
    if defect == "incomplete-coverage":
        _write_json(repo / path, {**json.loads((repo / path).read_text()), "complete": False})
    elif defect == "unreadable-coverage":
        (repo / path).write_text("not json\n")
    elif defect in ("no-sources", "empty-sources"):
        shutil.rmtree(repo / path)
        if defect == "empty-sources":
            (repo / path).mkdir()
    else:
        (repo / path).unlink()

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert _git(repo, "rev-parse", "HEAD") == start
    _assert_resumable(repo)
    assert _uv_calls() == []
    problem = problem.format(path=path)
    assert f"nothing staged; fix these first:\n  {problem}\n" in first.stderr
    assert f"stopped before cutting {TARGET}; fix the cause and run the same command again" in (
        first.stderr
    )
    assert "unstaged" not in first.stderr  # there was nothing to unstage

    _write_scope(repo, UNRELEASED[1])
    second = _run(repo)

    _assert_cut(repo, second, start)
    added = _git(repo, "show", "--name-only", "--format=", "HEAD~2").splitlines()
    for version in UNRELEASED:
        assert f"data/corpus/coverage/{JURISDICTION}/{DOCUMENT_CLASS}/{version}.json" in added
    assert _signed_versions() == list(UNRELEASED)


def test_step_1_reports_every_scope_not_ready(repo: Path) -> None:
    start = _cut_release_branch(repo)
    for version in UNRELEASED:
        (repo / f"data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{version}.jsonl").unlink()

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    _assert_resumable(repo)
    problems = "".join(
        f"  missing data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{version}.jsonl\n"
        for version in UNRELEASED
    )
    assert f"nothing staged; fix these first:\n{problems}" in first.stderr

    for version in UNRELEASED:
        _write_scope(repo, version)
    _assert_cut(repo, _run(repo), start)


# What each failed commit leaves on the branch: the commits before it.
FAILED_COMMITS = {ADD: [], SIGN: [ADD], CUT: [SIGN, ADD]}


@pytest.mark.parametrize("subject", FAILED_COMMITS)
def test_resumes_after_a_commit_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, subject: str
) -> None:
    start = _cut_release_branch(repo)
    _install_commit_msg_hook(repo)
    monkeypatch.setenv("FAIL_COMMIT", subject)

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert _branch_subjects(repo, start) == FAILED_COMMITS[subject]
    _assert_resumable(repo)
    assert "simulated commit failure" in first.stderr
    assert "unstaged what this run staged but did not commit" in first.stderr
    assert (f"deleted {TARGET}, this run's copy of the draft" in first.stderr) == (subject == CUT)
    if subject == SIGN:  # signed against the data commit, which stays HEAD: kept untracked
        manifests = [f"{MANIFEST_DIR}/{version}.json" for version in UNRELEASED]
        assert all((repo / manifest).is_file() for manifest in manifests)
        assert _git(repo, "ls-files", *manifests) == ""

    monkeypatch.delenv("FAIL_COMMIT")
    second = _run(repo)

    _assert_cut(repo, second, start)
    assert ("artifacts already committed; skipping data commit" in second.stdout) == (
        subject != ADD
    )
    assert _signed_versions() == list(UNRELEASED)  # no scope is signed twice


@pytest.mark.parametrize("failure", ["fail", "interrupt"])
def test_resumes_after_validate_release_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    start = _cut_release_branch(repo)
    monkeypatch.setenv("FAIL_VALIDATE_RELEASE", failure)

    first = _run(repo)

    # The script's INT trap exits 130 once the interrupted shim has exited.
    assert first.returncode == (1 if failure == "fail" else 130), first.stdout + first.stderr
    assert _branch_subjects(repo, start) == [SIGN, ADD]
    _assert_resumable(repo)
    assert f"deleted {TARGET}, this run's copy of the draft: the selector was not cut" in (
        first.stderr
    )
    if failure == "fail":
        assert "simulated validation failure" in first.stderr
        assert f"validate-release failed; not cutting {TARGET}" in first.stderr
    else:
        assert "simulated validation failure" not in first.stderr

    monkeypatch.delenv("FAIL_VALIDATE_RELEASE")
    second = _run(repo)

    _assert_cut(repo, second, start)
    out = second.stdout
    assert "artifacts already committed; skipping data commit" in out
    assert "signed manifests already committed; skipping sign commit" in out
    assert _signed_versions() == list(UNRELEASED)


def test_asks_for_the_private_key_only_when_a_scope_needs_signing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ingest_pr(repo, UNRELEASED[:1])  # signed in its ingest PR
    _write_scope(repo, UNRELEASED[1])  # still to sign
    _set_main_refs(repo, "origin-main")
    _git(repo, "checkout", "-qb", "release")
    start = _git(repo, "rev-parse", "HEAD")
    private_key = os.environ["AXIOM_CORPUS_INGEST_PRIVATE_KEY"]
    monkeypatch.delenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY")

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert (
        "1 of 2 unreleased scopes need signing; "
        "export AXIOM_CORPUS_INGEST_PRIVATE_KEY in this shell first"
    ) in first.stderr
    assert _git(repo, "rev-parse", "HEAD") == start
    _assert_resumable(repo)
    assert _uv_calls() == []

    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY", private_key)
    second = _run(repo)

    _assert_cut(repo, second, start)
    assert _signed_versions() == [UNRELEASED[1]]
    assert _git(repo, "show", "--name-only", "--format=", "HEAD~1").splitlines() == [
        f"{MANIFEST_DIR}/{UNRELEASED[1]}.json"
    ]


def test_resumes_through_a_chain_of_failures(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One branch, stopped at each step in turn, then finished by the same command.

    After every run: it exited 0 if and only if it cut the selector; if it did not, the
    tracked tree is clean and there is no selector file; commits were only added; and
    every manifest that existed before the run is byte for byte the same.
    """
    start = _cut_release_branch(repo)
    _install_commit_msg_hook(repo)
    scope = f"{JURISDICTION}/{DOCUMENT_CLASS}/{UNRELEASED[1]}"
    (repo / f"data/corpus/provisions/{scope}.jsonl").unlink()
    runs = [
        ("", ""),  # step 1: a missing artifact, restored after the run
        ("FAIL_SIGN_VERSION", UNRELEASED[1]),  # step 2, after signing the first scope
        ("FAIL_COMMIT", SIGN),  # step 3
        ("FAIL_VALIDATE_RELEASE", "fail"),  # step 4: validation
        ("FAIL_COMMIT", CUT),  # step 4: the selector commit
        ("FAIL_VALIDATE_RELEASE", "interrupt"),  # step 4: Ctrl-C
        ("", ""),  # nothing fails
    ]
    history: list[str] = []
    manifests: dict[Path, bytes] = {}
    for index, (name, value) in enumerate(runs):
        if name:
            monkeypatch.setenv(name, value)
        result = _run(repo)
        if name:
            monkeypatch.delenv(name)
        report = f"run {index}: {result.stdout}{result.stderr}"
        cut = _git(repo, "ls-tree", "--name-only", "HEAD", TARGET) == TARGET
        assert (result.returncode == 0) == cut, report
        assert cut == (index == len(runs) - 1), report
        if not cut:
            _assert_resumable(repo)
        subjects = _branch_subjects(repo, start)
        assert subjects[len(subjects) - len(history) :] == history, report
        history = subjects
        for manifest, content in manifests.items():
            assert manifest.read_bytes() == content, report
        manifests = {path: path.read_bytes() for path in (repo / MANIFEST_DIR).glob("*.json")}
        if index == 0:
            _write_scope(repo, UNRELEASED[1])

    _assert_cut(repo, result, start)
    # The second scope's first signing was the injected failure; neither was signed again.
    assert _signed_versions() == [UNRELEASED[0], UNRELEASED[1], UNRELEASED[1]]


def _install_git_shim(tmp_path: Path) -> None:
    """Put GIT_SHIM first on PATH (the fixture's bin directory), in front of the real git."""
    git = shutil.which("git", path=os.environ["PATH"].split(os.pathsep, 1)[1])
    assert git is not None
    shim = tmp_path / "bin/git"
    shim.write_text(
        GIT_SHIM.replace("@GIT@", git)
        .replace("@TARGET@", TARGET)
        .replace("@PYTHON@", sys.executable)
    )
    shim.chmod(0o755)


def _start(repo: Path, stdout: int | IO[str] = subprocess.PIPE) -> subprocess.Popen[str]:
    """Start the script in a session of its own, so signals to its group miss pytest."""
    return subprocess.Popen(
        ["bash", str(SCRIPT), DRAFT, PREDECESSOR],
        cwd=repo,
        stdout=stdout,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        preexec_fn=_default_signals,
    )


def _wait_for(path: Path, proc: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 120
    while not path.exists():
        assert proc.poll() is None, f"the script exited before {path.name} appeared"
        assert time.monotonic() < deadline, f"timed out waiting for {path}"
        time.sleep(0.05)


def _wait_for_group_to_exit(pgid: int) -> None:
    """Wait for the script's whole process group, a commit it did not wait for included."""
    deadline = time.monotonic() + 120
    while True:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        assert time.monotonic() < deadline, "processes still running in the script's group"
        time.sleep(0.05)


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGHUP], ids=["SIGTERM", "SIGHUP"])
@pytest.mark.parametrize("subject", [ADD, CUT])
def test_a_signal_to_the_script_alone_waits_for_the_running_commit(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, signum: int, subject: str
) -> None:
    # `kill <pid>` signals the script but not the git commit it is waiting for.
    start = _cut_release_branch(repo)
    _install_commit_msg_hook(repo)
    hold = tmp_path / "hold"
    hold.mkdir()
    monkeypatch.setenv("HOLD_COMMIT", subject)
    monkeypatch.setenv("HOLD_DIR", str(hold))
    proc = _start(repo)
    try:
        _wait_for(hold / "held", proc)
        os.kill(proc.pid, signum)
        # Untrapped, the signal would end the script now, with the commit still held.
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=2)
    finally:
        (hold / "release").touch()
    out, err = proc.communicate(timeout=300)
    _wait_for_group_to_exit(proc.pid)

    assert proc.returncode == 128 + signum, out + err
    if subject == CUT:  # the commit landed before the script acted on the signal
        assert _branch_subjects(repo, start) == [CUT, SIGN, ADD]
        assert json.loads((repo / TARGET).read_text()) == json.loads((repo / DRAFT).read_text())
        assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
        assert "deleted" not in err
        return
    assert _branch_subjects(repo, start) == [ADD]
    _assert_resumable(repo)
    assert f"stopped before cutting {TARGET}" in err

    monkeypatch.delenv("HOLD_COMMIT")
    _assert_cut(repo, _run(repo), start)


def _scope(version: str) -> str:
    return f"{JURISDICTION}/{DOCUMENT_CLASS}/{version}"


def _manifest(repo: Path, version: str) -> Path:
    return repo / MANIFEST_DIR / f"{version}.json"


def _edit_provisions(repo: Path, version: str) -> None:
    provisions = repo / f"data/corpus/provisions/{_scope(version)}.jsonl"
    provisions.write_text(provisions.read_text().replace("Text", "Fixed text"))


def _stop_at_validation(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run once, failing validate-release: both scopes are committed and signed."""
    monkeypatch.setenv("FAIL_VALIDATE_RELEASE", "fail")
    result = _run(repo)
    monkeypatch.delenv("FAIL_VALIDATE_RELEASE")
    assert result.returncode == 1, result.stdout + result.stderr


# Untracked manifests of scopes the draft does not add: one outside it, one released.
OUTSIDERS = (
    f"{MANIFEST_DIR}/2026-09-30-outside.json",
    ".axiom/ingest-manifests/us-ca/statute/2026-09-30.json",
)


@pytest.mark.parametrize("signed", ["on-this-branch", "in-their-ingest-pr"])
def test_commits_the_unreleased_scopes_manifests_and_no_others(repo: Path, signed: str) -> None:
    if signed == "in-their-ingest-pr":  # nothing to sign: before, the outsiders made a Sign commit
        _ingest_pr(repo, UNRELEASED)
        _set_main_refs(repo, "origin-main")
        _git(repo, "checkout", "-qb", "release")
        start = _git(repo, "rev-parse", "HEAD")
    else:
        start = _cut_release_branch(repo)
    for outsider in OUTSIDERS:
        _write_json(repo / outsider, {"outside": outsider})
    before = {outsider: (repo / outsider).read_bytes() for outsider in OUTSIDERS}

    result = _run(repo)

    if signed == "in-their-ingest-pr":
        _assert_cut(repo, result, start, (CUT,))
        assert "signed manifests already committed; skipping sign commit" in result.stdout
    else:
        _assert_cut(repo, result, start)
        assert _git(repo, "show", "--name-only", "--format=", "HEAD~1").splitlines() == [
            f"{MANIFEST_DIR}/{version}.json" for version in UNRELEASED
        ]
    for outsider in OUTSIDERS:
        assert (repo / outsider).read_bytes() == before[outsider]
        assert _git(repo, "ls-files", outsider) == ""


# How a fix to an artifact the branch committed and signed lands before the re-run, as the
# branch's commits between its first Sign commit and its second, newest first.
ARTIFACT_FIXES = {
    "committed": ["Restore source.html"],
    # A fix that only adds files: data/ is gitignored, so the tracked tree stays clean (the
    # preflight refuses any other uncommitted fix) and step 1 commits it.
    "uncommitted": [ADD],
    # The procedure before step 2 signed such a scope again; it still works.
    "manifest-deleted": ["Delete the stale manifest", "Restore source.html"],
}


@pytest.mark.parametrize("fix", ARTIFACT_FIXES)
def test_resumes_after_a_fix_to_artifacts_this_branch_signed(repo: Path, fix: str) -> None:
    """The fix changes an artifact this branch committed and signed; the re-run signs it again."""
    start = _cut_release_branch(repo)
    kept, fixed = UNRELEASED
    sources = repo / f"data/corpus/sources/{_scope(fixed)}"
    # Step 1 sees a sources directory with a file in it; validate-release sees that the
    # file the provisions name is not there.
    (sources / "source.html").rename(sources / "renamed.html")

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert _branch_subjects(repo, start) == [SIGN, ADD]
    _assert_resumable(repo)
    assert f"validate-release failed; not cutting {TARGET}" in first.stderr
    kept_manifest = _manifest(repo, kept).read_bytes()

    if fix == "uncommitted":
        shutil.copy2(sources / "renamed.html", sources / "source.html")
    else:
        (sources / "renamed.html").rename(sources / "source.html")
        _git(repo, "add", "-f", "-A", f"data/corpus/sources/{_scope(fixed)}")
        _git(repo, "commit", "-qm", "Restore source.html")
    if fix == "manifest-deleted":
        _git(repo, "rm", "-q", f"{MANIFEST_DIR}/{fixed}.json")
        _git(repo, "commit", "-qm", "Delete the stale manifest")
    second = _run(repo)

    _assert_cut(repo, second, start, (CUT, SIGN, *ARTIFACT_FIXES[fix], SIGN, ADD))
    out = second.stdout
    assert f"already signed, keeping existing manifest: {_scope(kept)}" in out
    resigned = f"signing again: {_scope(fixed)} (its artifacts changed after it was signed)"
    assert (resigned in out) == (fix != "manifest-deleted")
    assert "guard-ingested: ok" in out
    # The second sign commit holds the fixed scope's manifest only, signed against the fix.
    status = "A" if fix == "manifest-deleted" else "M"
    assert _git(repo, "show", "--name-status", "--format=", "HEAD~1").splitlines() == [
        f"{status}\t{MANIFEST_DIR}/{fixed}.json"
    ]
    resigned_manifest = json.loads(_manifest(repo, fixed).read_text())
    assert resigned_manifest["axiom_corpus_git"]["commit"] == _git(repo, "rev-parse", "HEAD~2")
    assert f"data/corpus/sources/{_scope(fixed)}/source.html" in [
        entry["path"] for entry in resigned_manifest["applied_files"]
    ]
    assert _manifest(repo, kept).read_bytes() == kept_manifest
    assert _signed_versions() == [*UNRELEASED, fixed]


# What stops a run that signs both scopes again, before its sign commit lands.
RESIGN_FAILURES = {
    "signing": {"FAIL_SIGN_VERSION": UNRELEASED[1]},  # the first went aside, the second fails
    "sign-commit": {"FAIL_COMMIT": SIGN},  # both were moved over their committed copies
    # ... and a signal fails the first put-back, as one can fail the unstage.
    "sign-commit-put-back-retried": {"FAIL_COMMIT": SIGN, "FAIL_CHECKOUT_ONCE": "1"},
}


@pytest.mark.parametrize("failure", RESIGN_FAILURES)
def test_a_run_that_stops_after_signing_again_leaves_the_committed_manifests(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    # Both committed manifests go stale, so one run signs both again. Written over its
    # committed copy at once, the first would dirty the tracked tree and the signer would
    # refuse the second.
    start = _cut_release_branch(repo)
    _install_commit_msg_hook(repo)
    _stop_at_validation(repo, monkeypatch)
    for version in UNRELEASED:
        _edit_provisions(repo, version)
    _git(repo, "commit", "-qam", "Fix provisions")
    head = _git(repo, "rev-parse", "HEAD")
    committed = {version: _manifest(repo, version).read_bytes() for version in UNRELEASED}

    failures = RESIGN_FAILURES[failure]
    if "FAIL_CHECKOUT_ONCE" in failures:
        _install_git_shim(tmp_path)
        (tmp_path / "hold").mkdir()
        monkeypatch.setenv("HOLD_DIR", str(tmp_path / "hold"))
    for name, value in failures.items():
        monkeypatch.setenv(name, value)
    second = _run(repo)
    for name in failures:
        monkeypatch.delenv(name)

    assert second.returncode == 1, second.stdout + second.stderr
    assert _git(repo, "rev-parse", "HEAD") == head
    _assert_resumable(repo)
    for version in UNRELEASED:
        assert _manifest(repo, version).read_bytes() == committed[version]
    put_back = "put back the committed manifests this run had replaced but not committed"
    assert (put_back in second.stderr) == ("FAIL_COMMIT" in failures)
    assert "could not put back" not in second.stderr
    if "FAIL_CHECKOUT_ONCE" in failures:
        assert (tmp_path / "hold/checkout-failed").exists()
        assert "simulated index.lock write error" in second.stderr
    for version in UNRELEASED:
        resigned = f"signing again: {_scope(version)} (its artifacts changed after it was signed)"
        assert resigned in second.stdout

    third = _run(repo)

    _assert_cut(repo, third, start, (CUT, SIGN, "Fix provisions", SIGN, ADD))
    assert "guard-ingested: ok" in third.stdout
    assert _git(repo, "show", "--name-status", "--format=", "HEAD~1").splitlines() == [
        f"M\t{MANIFEST_DIR}/{version}.json" for version in UNRELEASED
    ]
    assert _signed_versions() == [*UNRELEASED] * 3


def test_signs_again_a_manifest_signed_against_a_rewritten_commit(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The Sign commit fails, leaving both manifests untracked. Amending the data commit, as
    # a rebase would, keeps the artifacts but drops the commit they were signed against
    # from HEAD's history, which guard-ingested rejects.
    start = _cut_release_branch(repo)
    _install_commit_msg_hook(repo)
    monkeypatch.setenv("FAIL_COMMIT", SIGN)
    first = _run(repo)
    monkeypatch.delenv("FAIL_COMMIT")
    assert first.returncode == 1, first.stdout + first.stderr
    assert _branch_subjects(repo, start) == [ADD]
    _git(repo, "commit", "--amend", "-qm", ADD)

    second = _run(repo)

    _assert_cut(repo, second, start)
    for version in UNRELEASED:
        assert (
            f"signing again: {_scope(version)} "
            "(the commit it was signed against is not in HEAD's history)"
        ) in second.stdout
    assert "guard-ingested: ok" in second.stdout
    assert _signed_versions() == [*UNRELEASED] * 2


@pytest.mark.parametrize(
    "content", ["", '{"schema_version": "axiom-corpus/ingest-manifest/v1", "appl', "[]"]
)
def test_signs_again_an_untracked_manifest_that_is_not_json(repo: Path, content: str) -> None:
    # As a signing cut short mid-write leaves behind: it attests nothing.
    start = _cut_release_branch(repo)
    manifest = _manifest(repo, UNRELEASED[1])
    manifest.write_text(content)

    result = _run(repo)

    _assert_cut(repo, result, start)
    assert (
        f"signing again: {_scope(UNRELEASED[1])} (its untracked manifest is not readable JSON)"
        in result.stdout
    )
    assert json.loads(manifest.read_text())["version"] == UNRELEASED[1]
    assert _signed_versions() == list(UNRELEASED)


def test_asks_for_the_private_key_to_sign_a_scope_again(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = _cut_release_branch(repo)
    _stop_at_validation(repo, monkeypatch)
    _edit_provisions(repo, UNRELEASED[1])
    _git(repo, "commit", "-qam", "Fix provisions")
    head = _git(repo, "rev-parse", "HEAD")
    calls = len(_uv_calls())
    private_key = os.environ["AXIOM_CORPUS_INGEST_PRIVATE_KEY"]
    monkeypatch.delenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY")

    second = _run(repo)

    assert second.returncode == 1, second.stdout + second.stderr
    assert (
        "1 of 2 unreleased scopes need signing; "
        "export AXIOM_CORPUS_INGEST_PRIVATE_KEY in this shell first\n"
        f"  {MANIFEST_DIR}/{UNRELEASED[1]}.json will be signed again: "
        "its artifacts changed after it was signed\n"
    ) in second.stderr
    assert _git(repo, "rev-parse", "HEAD") == head
    _assert_resumable(repo)
    assert len(_uv_calls()) == calls

    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY", private_key)
    third = _run(repo)

    _assert_cut(repo, third, start, (CUT, SIGN, "Fix provisions", SIGN, ADD))
    assert _signed_versions() == [*UNRELEASED, UNRELEASED[1]]


@pytest.mark.parametrize(
    "second", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP], ids=["SIGINT", "SIGTERM", "SIGHUP"]
)
@pytest.mark.parametrize("first", ["failure", "SIGHUP"])
def test_a_second_signal_does_not_cut_the_cleanup_short(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, first: str, second: int
) -> None:
    # The cleanup starts after a failed validate-release, or after a SIGHUP that ends a held
    # one (a closing terminal can send SIGHUP twice). The second signal lands while
    # on_exit is cleaning up.
    start = _cut_release_branch(repo)
    _install_git_shim(tmp_path)
    hold = tmp_path / "hold"
    hold.mkdir()
    monkeypatch.setenv("HOLD_DIR", str(hold))
    monkeypatch.setenv("FAIL_VALIDATE_RELEASE", "fail" if first == "failure" else "hold")
    monkeypatch.setenv("HOLD_CLEANUP", "1")
    proc = _start(repo)
    try:
        if first == "SIGHUP":
            _wait_for(hold / "held", proc)
            os.killpg(proc.pid, signal.SIGHUP)
        _wait_for(hold / "cleanup", proc)
        os.killpg(proc.pid, second)
        # Not ignored, the second signal would end the run now, mid-cleanup.
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=2)
    finally:
        (hold / "release").touch()
    out, err = proc.communicate(timeout=300)
    _wait_for_group_to_exit(proc.pid)

    assert proc.returncode == (1 if first == "failure" else 128 + signal.SIGHUP), out + err
    assert _branch_subjects(repo, start) == [SIGN, ADD]
    _assert_resumable(repo)
    assert f"deleted {TARGET}, this run's copy of the draft: the selector was not cut" in err

    monkeypatch.delenv("FAIL_VALIDATE_RELEASE")
    monkeypatch.delenv("HOLD_CLEANUP")
    _assert_cut(repo, _run(repo), start)


def test_the_cleanup_tries_a_failed_unstage_again(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A signal makes git reset fail while it holds index.lock; git drops the lock first.
    start = _cut_release_branch(repo)
    _install_commit_msg_hook(repo)
    _install_git_shim(tmp_path)
    hold = tmp_path / "hold"
    hold.mkdir()
    monkeypatch.setenv("HOLD_DIR", str(hold))
    monkeypatch.setenv("FAIL_RESET_ONCE", "1")
    monkeypatch.setenv("FAIL_COMMIT", SIGN)  # so the signed manifests are staged

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert (hold / "reset-failed").exists()
    assert "simulated index.lock write error" in first.stderr
    assert "unstaged what this run staged but did not commit" in first.stderr
    assert "could not unstage" not in first.stderr
    assert _branch_subjects(repo, start) == [ADD]
    _assert_resumable(repo)

    monkeypatch.delenv("FAIL_COMMIT")
    _assert_cut(repo, _run(repo), start)


def test_a_closed_output_pipe_does_not_stop_the_cleanup(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # As when the output goes through `head`, which exits early: the reader of stderr goes
    # away while the Cut commit fails, before on_exit writes its first message.
    start = _cut_release_branch(repo)
    _install_commit_msg_hook(repo)
    monkeypatch.setenv("FAIL_COMMIT", CUT)
    monkeypatch.setenv("FAIL_COMMIT_DELAY", "2")  # time for the reader to go away
    with (tmp_path / "stdout").open("w") as stdout:
        proc = _start(repo, stdout=stdout)
        assert proc.stderr is not None
        for line in proc.stderr:
            if "simulated commit failure" in line:
                break
        proc.stderr.close()
        proc.wait(timeout=300)
    _wait_for_group_to_exit(proc.pid)

    assert proc.returncode == 1  # the failed commit's status, not death by SIGPIPE
    assert _branch_subjects(repo, start) == [SIGN, ADD]
    _assert_resumable(repo)

    monkeypatch.delenv("FAIL_COMMIT")
    _assert_cut(repo, _run(repo), start)


REASONING_LOG = ".axiom/reasoning-logs/test-ingest.md"


@dataclass(frozen=True)
class Foreign:
    """How a manifest this script must never sign again was signed, and where."""

    on_main: bool
    command: str = SCRIPT_COMMAND
    extra_args: tuple[str, ...] = ()


# Each manifest of the first unreleased scope has the one property that rules it out.
FOREIGN_MANIFESTS = {
    # By the command this script writes, but on main: where it was committed protects it.
    "committed-on-main": Foreign(on_main=True),
    # The rest are on this branch.
    "ingest-command": Foreign(on_main=False, command="test ingest {version}"),
    "reasoning-log": Foreign(on_main=False, extra_args=("--reasoning-log", REASONING_LOG)),
    "deleted-file": Foreign(
        on_main=False,
        extra_args=(
            *(
                arg
                for artifact in (
                    "sources/{scope}/source.html",
                    "inventory/{scope}.json",
                    "provisions/{scope}.jsonl",
                    "coverage/{scope}.json",
                )
                for arg in ("--file", f"data/corpus/{artifact}")
            ),
            "--deleted-file",
            "data/corpus/sources/{scope}/retired.html",
        ),
    ),
    "unreadable": Foreign(on_main=False),  # truncated, then committed
}


@pytest.mark.parametrize("foreign", FOREIGN_MANIFESTS)
def test_never_signs_again_a_manifest_it_did_not_sign(repo: Path, foreign: str) -> None:
    """A fix to such a scope's artifacts is guard-ingested's to reject, not this script's to sign."""
    kept, unsigned = UNRELEASED
    case = FOREIGN_MANIFESTS[foreign]
    extra_args = tuple(arg.replace("{scope}", _scope(kept)) for arg in case.extra_args)
    if foreign == "reasoning-log":
        (repo / REASONING_LOG).parent.mkdir(parents=True)
        (repo / REASONING_LOG).write_text("How the scope was ingested.\n")
        _git(repo, "add", REASONING_LOG)
        _git(repo, "commit", "-qm", "Add a reasoning log")
    if not case.on_main:
        _set_main_refs(repo, "origin-main")
        _git(repo, "checkout", "-qb", "release")
    _ingest_pr(repo, (kept,), command=case.command, extra_args=extra_args)
    if case.on_main:
        _set_main_refs(repo, "origin-main")
        _git(repo, "checkout", "-qb", "release")
    if foreign == "unreadable":
        _manifest(repo, kept).write_text('{"schema_version": "axiom-corpus/ingest-man')
        _git(repo, "commit", "-qam", "Truncate the manifest")
    _edit_provisions(repo, kept)
    _git(repo, "commit", "-qam", "Fix provisions")
    _write_scope(repo, unsigned)
    head = _git(repo, "rev-parse", "HEAD")
    manifest = _manifest(repo, kept).read_bytes()

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"already signed, keeping existing manifest: {_scope(kept)}" in result.stdout
    assert f"signing again: {_scope(kept)}" not in result.stdout
    assert f"guard-ingested failed; not cutting {TARGET}" in result.stderr
    assert _manifest(repo, kept).read_bytes() == manifest
    assert _signed_versions() == [unsigned]
    assert _branch_subjects(repo, head) == [SIGN, ADD]
    _assert_resumable(repo)


# How the script names a scope's rebuild command, by the shape of its version.
COMMAND_FORMS = {
    "consolidated": (
        "2026-09-24-c-consolidated",
        "scripts/consolidate_release_scopes.py --base data/corpus --jurisdiction us-co"
        " --document-class policy --target-version 2026-09-24-c-consolidated"
        " (run note: docs/ingest-runs/2026-09-11-release-consolidation.md)",
    ),
    "manifest-yaml": (
        "2026-09-24-c",
        "axiom-corpus-ingest extract-official-documents --base data/corpus"
        " --version 2026-09-24-c --manifest manifests/test-scope.yaml"
        " (run note: docs/ingest-runs/2026-09-10-*.md)",
    ),
}


@pytest.mark.parametrize("form", COMMAND_FORMS)
def test_signs_again_a_manifest_signed_with_either_command_form(
    repo: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    kept = UNRELEASED[0]
    version, command = COMMAND_FORMS[form]
    _write_json(repo / DRAFT, _selector("test-rel-2", [RELEASED, kept, version]))
    if form == "manifest-yaml":
        (repo / "manifests/test-scope.yaml").write_text(
            f'version: "{version}"\n'
            f"documents:\n  - jurisdiction: {JURISDICTION}\n    document_class: {DOCUMENT_CLASS}\n"
        )
    _git(repo, "add", "manifests", DRAFT)
    _git(repo, "commit", "-qm", "Select a third scope")
    for scope_version in (kept, version):
        _write_scope(repo, scope_version)
    _set_main_refs(repo, "origin-main")
    _git(repo, "checkout", "-qb", "release")
    start = _git(repo, "rev-parse", "HEAD")
    _stop_at_validation(repo, monkeypatch)
    assert json.loads(_manifest(repo, version).read_text())["command"]["text"] == command
    _edit_provisions(repo, version)
    _git(repo, "commit", "-qam", "Fix provisions")

    second = _run(repo)

    _assert_cut(repo, second, start, (CUT, SIGN, "Fix provisions", SIGN, ADD))
    resigned = f"signing again: {_scope(version)} (its artifacts changed after it was signed)"
    assert resigned in second.stdout
    assert json.loads(_manifest(repo, version).read_text())["command"]["text"] == command
    assert _signed_versions() == [kept, version, version]


@pytest.mark.parametrize("manifests", ["untracked", "committed"])
def test_with_no_main_to_compare_signs_again_only_untracked_manifests(
    repo: Path, monkeypatch: pytest.MonkeyPatch, manifests: str
) -> None:
    # Without a merge base, the script cannot tell main's manifests from this branch's.
    for version in UNRELEASED:
        _write_scope(repo, version)
    _set_main_refs(repo, "no-main")
    _git(repo, "checkout", "-qb", "release")
    start = _git(repo, "rev-parse", "HEAD")
    if manifests == "untracked":
        _install_commit_msg_hook(repo)
        monkeypatch.setenv("FAIL_COMMIT", SIGN)
        assert _run(repo).returncode == 1
        monkeypatch.delenv("FAIL_COMMIT")
    else:
        _stop_at_validation(repo, monkeypatch)
    fixed = UNRELEASED[1]
    _edit_provisions(repo, fixed)
    _git(repo, "add", "-f", f"data/corpus/provisions/{_scope(fixed)}.jsonl")
    _git(repo, "commit", "-qm", "Fix provisions")
    stale = _manifest(repo, fixed).read_bytes()

    second = _run(repo)

    assert "neither origin/main nor main shares history with HEAD;" in second.stdout
    resigned = f"signing again: {_scope(fixed)} (its artifacts changed after it was signed)"
    if manifests == "untracked":
        _assert_cut(repo, second, start, (CUT, SIGN, "Fix provisions", ADD))
        assert resigned in second.stdout
        assert _signed_versions() == [*UNRELEASED, fixed]
    else:  # kept, stale: CI's guard-ingested rejects the PR
        _assert_cut(repo, second, start, (CUT, "Fix provisions", SIGN, ADD))
        assert resigned not in second.stdout
        assert _manifest(repo, fixed).read_bytes() == stale
        assert _signed_versions() == list(UNRELEASED)


# Step 2's plan, in the script's own words, run as the script runs it.
PLAN_SOURCE = re.compile(r"^plan_signing\(\) \{.*?<<'PY'\n(.*?)^PY$", re.S | re.M)
PLAN_VERSION = "2026-09-24-p"
PLAN_SCOPE = f"{JURISDICTION}/{DOCUMENT_CLASS}/{PLAN_VERSION}"
NAME_PART = st.text("abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=6)
# Sources files by path under the scope's sources directory. "d-" and "f-" keep a
# directory from sharing a name with a file.
SOURCE_FILES = st.dictionaries(
    st.builds(
        lambda dirs, name: "/".join([*(f"d-{d}" for d in dirs), f"f-{name}.html"]),
        st.lists(NAME_PART, max_size=2),
        NAME_PART,
    ),
    st.binary(max_size=32),
    max_size=4,
)
OTHER_ARTIFACTS = {
    "inventory": f"inventory/{PLAN_SCOPE}.json",
    "provisions": f"provisions/{PLAN_SCOPE}.jsonl",
    "coverage": f"coverage/{PLAN_SCOPE}.json",
}


def _plan(repo: Path) -> str:
    """Step 2's plan for a scope whose manifest is untracked, with no main to compare."""
    match = PLAN_SOURCE.search(SCRIPT.read_text())
    assert match, "plan_signing's Python is no longer where this test looks for it"
    scope_list = repo / ".git/scope-list"
    scope_list.write_text(f"{JURISDICTION} {DOCUMENT_CLASS} {PLAN_VERSION}\n")
    result = subprocess.run(
        [sys.executable, "-", "", str(scope_list), f"{MANIFEST_DIR}/{PLAN_VERSION}.json"],
        input=match.group(1),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _commit_and_sign(repo: Path) -> None:
    _git(repo, "add", "-f", "-A", "data/corpus")
    _git(repo, "commit", "-qm", "Artifacts")
    exit_code = main(
        [
            "sign-ingest-manifest",
            "--repo",
            str(repo),
            "--jurisdiction",
            JURISDICTION,
            "--document-class",
            DOCUMENT_CLASS,
            "--version",
            PLAN_VERSION,
            "--command",
            SCRIPT_COMMAND.format(version=PLAN_VERSION),
        ]
    )
    assert exit_code == 0


@settings(
    max_examples=10,
    deadline=None,
    # The fixture only sets the environment (git identity, keys); each example makes its
    # own repository.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    sources=SOURCE_FILES, others=st.sets(st.sampled_from(sorted(OTHER_ARTIFACTS))), data=st.data()
)
def test_the_plan_finds_a_manifest_stale_exactly_when_the_signer_would_sign_other_files(
    repo: Path, sources: dict[str, bytes], others: set[str], data: st.DataObject
) -> None:
    """The plan's own reading of a scope's artifacts against the signer's (a differential check).

    A manifest the signer just wrote is kept; any change to the scope's files, their bytes or
    their paths makes it stale; and the manifest the signer writes for the changed scope is
    kept again.
    """
    assume(sources or others)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _git(root, "init", "-q", "-b", "main")
        corpus = root / "data/corpus"
        for path, content in sources.items():
            target = corpus / "sources" / PLAN_SCOPE / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for kind in others:
            target = corpus / OTHER_ARTIFACTS[kind]
            target.parent.mkdir(parents=True, exist_ok=True)
            # sign-ingest-manifest summarises coverage, so it must be JSON.
            target.write_bytes(
                b'{"complete": true}' if kind == "coverage" else data.draw(st.binary(max_size=32))
            )
        _commit_and_sign(root)
        assert _plan(root) == "keep\t\n"

        files = sorted(p for p in corpus.rglob("*") if p.is_file())
        source_files = [p for p in files if "/sources/" in p.as_posix()]
        changes = ["modify", "add"]
        changes += ["delete"] * (len(files) > 1) + ["rename"] * bool(source_files)
        change = data.draw(st.sampled_from(changes))
        if change == "add":  # "F-" is outside NAME_PART, so the file is new
            added = corpus / "sources" / PLAN_SCOPE / "F-added.html"
            added.parent.mkdir(parents=True, exist_ok=True)
            added.write_bytes(b"added")
        else:
            path = data.draw(st.sampled_from(source_files if change == "rename" else files))
            if change == "modify":
                path.write_bytes(path.read_bytes() + b"!")
            elif change == "delete":
                path.unlink()
            else:
                path.rename(path.with_name(f"renamed-{path.name}"))
        assert _plan(root) == "resign\tits artifacts changed after it was signed\n", change

        _commit_and_sign(root)
        assert _plan(root) == "keep\t\n", change
