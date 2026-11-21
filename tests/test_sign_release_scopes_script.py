"""End-to-end runs of scripts/sign_release_scopes.sh in a throwaway git repository.

The script calls ``python3``, ``uv run python`` and ``uv run axiom-corpus-ingest``. Shims
on PATH run all three with this interpreter, so sign-ingest-manifest, guard-ingested and
validate-release are the real commands; the ``uv`` shim also logs each
``axiom-corpus-ingest`` subcommand line it runs (``uv run python`` goes unlogged), and on
request fails a signing or a validation, or interrupts the run during validation as
Ctrl-C does.
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

from axiom_corpus.corpus import releases
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
# A draft names its predecessor first in its description, as the CI lineage guard reads it.
DRAFT_DESCRIPTION = "Successor to test-rel-1."
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
if [ "$1" = run ] && [ "$2" = python ]; then shift 2; exec "@PYTHON@" "$@"; fi
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


def _selector(name: str, versions: list[str], description: str | None = None) -> dict:
    return {
        "name": name,
        **({} if description is None else {"description": description}),
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


def _run(repo: Path, predecessor: str = PREDECESSOR) -> subprocess.CompletedProcess[str]:
    # In a session of its own, a simulated Ctrl-C reaches the script, never pytest.
    return subprocess.run(
        ["bash", str(SCRIPT), DRAFT, predecessor],
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
    _write_json(
        root / DRAFT,
        _selector("test-rel-2", [RELEASED, *UNRELEASED], description=DRAFT_DESCRIPTION),
    )
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
    # The signer records a link's target, so guard-ingested never finds the link's path.
    "symlinked-source": ("sources/{scope}/source.html", "symlink {path}"),
    "symlinked-provisions": ("provisions/{scope}.jsonl", "symlink {path}"),
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
    elif defect.startswith("symlinked-"):
        target = repo / "elsewhere" / Path(path).name
        target.parent.mkdir()
        (repo / path).rename(target)
        (repo / path).symlink_to(target)
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

    if (repo / path).is_symlink():  # else _write_scope would write through the link
        (repo / path).unlink()
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
    origin_main_behind: bool = False  # origin/main is set before main gains the manifest


# Each manifest of the first unreleased scope has the one property that rules it out.
FILES = ("sources/{scope}/source.html", "inventory/{scope}.json", "provisions/{scope}.jsonl")
FOREIGN_MANIFESTS = {
    # By the command this script writes, but on main: where it was committed protects it.
    "committed-on-main": Foreign(on_main=True),
    # ... even when origin/main is behind the main the branch was cut from.
    "committed-on-newer-local-main": Foreign(on_main=True, origin_main_behind=True),
    # The rest are on this branch.
    "ingest-command": Foreign(on_main=False, command="test ingest {version}"),
    "custom-manifest-path": Foreign(
        on_main=False,
        command=SCRIPT_COMMAND.replace(
            " (run note:", " --manifest custom/scope.yml (run note:"
        ),
    ),
    "consolidation-for-ordinary-version": Foreign(
        on_main=False,
        command=(
            "scripts/consolidate_release_scopes.py --base data/corpus --jurisdiction us-co"
            " --document-class policy --target-version {version}"
            " (run note: docs/ingest-runs/2026-09-11-release-consolidation.md)"
        ),
    ),
    "reasoning-log": Foreign(on_main=False, extra_args=("--reasoning-log", REASONING_LOG)),
    "deleted-file": Foreign(
        on_main=False,
        extra_args=(
            *(
                arg
                for artifact in (*FILES, "coverage/{scope}.json")
                for arg in ("--file", f"data/corpus/{artifact}")
            ),
            "--deleted-file",
            "data/corpus/sources/{scope}/retired.html",
        ),
    ),
    "unreadable": Foreign(on_main=False),  # truncated, then committed
    "entry-without-sha256": Foreign(on_main=False),  # one entry's sha256 dropped, then committed
    # A hand-picked --file list (no coverage), not the scope as the signer infers it.
    "file-subset": Foreign(
        on_main=False,
        extra_args=tuple(arg for f in FILES for arg in ("--file", f"data/corpus/{f}")),
    ),
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
    if not case.on_main or case.origin_main_behind:
        _set_main_refs(repo, "origin-main")
    if not case.on_main:
        _git(repo, "checkout", "-qb", "release")
    _ingest_pr(repo, (kept,), command=case.command, extra_args=extra_args)
    if case.on_main:
        if not case.origin_main_behind:
            _set_main_refs(repo, "origin-main")
        _git(repo, "checkout", "-qb", "release")
    if foreign == "unreadable":
        _manifest(repo, kept).write_text('{"schema_version": "axiom-corpus/ingest-man')
        _git(repo, "commit", "-qam", "Truncate the manifest")
    elif foreign == "entry-without-sha256":
        payload = json.loads(_manifest(repo, kept).read_text())
        del payload["applied_files"][0]["sha256"]
        _write_json(_manifest(repo, kept), payload)
        _git(repo, "commit", "-qam", "Drop a sha256")
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


def test_stops_when_a_scope_it_would_sign_removes_an_artifact_main_has(repo: Path) -> None:
    """This script cannot mark an artifact deleted; it says how to sign such a scope by hand."""
    kept, legacy = UNRELEASED
    # Main tracks the second scope's artifacts without a manifest (as before signing was
    # required), with one more source, which the release branch removes.
    _write_scope(repo, legacy)
    retired = f"data/corpus/sources/{_scope(legacy)}/retired.html"
    (repo / retired).write_text("<p>Retired.</p>")
    _git(repo, "add", "-f", "data/corpus")
    _git(repo, "commit", "-qm", "Track a scope without a manifest")
    _set_main_refs(repo, "origin-main")
    _git(repo, "checkout", "-qb", "release")
    start = _git(repo, "rev-parse", "HEAD")
    _git(repo, "rm", "-q", retired)
    _git(repo, "commit", "-qm", "Remove retired.html")
    _write_scope(repo, kept)

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert (
        "nothing staged; these scopes remove artifacts that origin/main has:\n"
        f"  {_scope(legacy)}: {retired}\n"
    ) in first.stderr
    assert "--deleted-file for\neach removed one" in first.stderr
    assert _branch_subjects(repo, start) == ["Remove retired.html"]
    _assert_resumable(repo)
    assert _uv_calls() == []

    # The procedure it names: sign the scope by hand, marking the removal.
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
            legacy,
            "--command",
            "test signed by hand",
            *(
                arg
                for artifact in (*FILES, "coverage/{scope}.json")
                for arg in ("--file", "data/corpus/" + artifact.format(scope=_scope(legacy)))
            ),
            "--deleted-file",
            retired,
        ]
    )
    assert exit_code == 0
    _git(repo, "add", f"{MANIFEST_DIR}/{legacy}.json")
    _git(repo, "commit", "-qm", "Sign the scope by hand")
    second = _run(repo)

    _assert_cut(
        repo, second, start, (CUT, SIGN, ADD, "Sign the scope by hand", "Remove retired.html")
    )
    assert f"already signed, keeping existing manifest: {_scope(legacy)}" in second.stdout
    assert "guard-ingested: ok" in second.stdout
    assert _signed_versions() == [kept]


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
    _write_json(
        repo / DRAFT,
        _selector("test-rel-2", [RELEASED, kept, version], description=DRAFT_DESCRIPTION),
    )
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


# A selector's scopes as (version, layer); a layer of None is a primary scope.
LayeredScopes = list[tuple[str, str | None]]
# A version older than every other here; its scope is a base wherever a selector says so.
BASE = "2026-05-01"
NOT_CARRIED = (
    "base scope {scope} is not carried from the predecessor; a base scope enters through its"
    " restore manifest (axiom-corpus#728), not this script"
)
MADE_PRIMARY = (
    "base scope {scope} of the predecessor is primary in the draft; a successor carries a"
    " base scope unchanged, as a base"
)
BAD_LAYER = (
    "scope {scope} in {path} has layer 'Base'; a selector marks a base scope"
    ' "layer": "base" and a primary scope with no layer'
)


def _layered_selector(name: str, scopes: LayeredScopes, description: str | None = None) -> dict:
    selector = _selector(name, [version for version, _ in scopes], description=description)
    for entry, (_, layer) in zip(selector["scopes"], scopes, strict=True):
        if layer is not None:
            entry["layer"] = layer
    return selector


def _track_selectors(repo: Path, predecessor: LayeredScopes, draft: LayeredScopes) -> None:
    """Rewrite test-rel-1 and the test-rel-2 draft with these scopes, and commit them."""
    _write_json(repo / PREDECESSOR, _layered_selector("test-rel-1", predecessor))
    _write_json(repo / DRAFT, _layered_selector("test-rel-2", draft, description=DRAFT_DESCRIPTION))
    _git(repo, "add", PREDECESSOR, DRAFT)
    _git(repo, "commit", "-qm", "Layer the selectors")


PRIMARIES: LayeredScopes = [(version, None) for version in UNRELEASED]
# case: (the predecessor's scopes, the draft's, and every line the run stops with)
BASE_REFUSALS: dict[str, tuple[LayeredScopes, LayeredScopes, list[str]]] = {
    "draft-adds-a-base": (
        [(RELEASED, None)],
        [(BASE, "base"), (RELEASED, None), *PRIMARIES],
        [NOT_CARRIED.format(scope=_scope(BASE))],
    ),
    "draft-has-a-released-primary-as-a-base": (
        [(RELEASED, None)],
        [(RELEASED, "base"), *PRIMARIES],
        [NOT_CARRIED.format(scope=_scope(RELEASED))],
    ),
    "draft-has-a-released-base-as-a-primary": (
        [(RELEASED, "base")],
        [(RELEASED, None), *PRIMARIES],
        [MADE_PRIMARY.format(scope=_scope(RELEASED))],
    ),
    "draft-misspells-a-layer": (
        [(RELEASED, None)],
        [(RELEASED, None), (UNRELEASED[0], None), (UNRELEASED[1], "Base")],
        [BAD_LAYER.format(scope=_scope(UNRELEASED[1]), path=DRAFT)],
    ),
    "predecessor-misspells-a-layer": (
        [(RELEASED, "Base")],
        [(RELEASED, None), *PRIMARIES],
        [BAD_LAYER.format(scope=_scope(RELEASED), path=PREDECESSOR)],
    ),
    "every-scope-named": (
        [(RELEASED, "base")],
        [(BASE, "base"), (RELEASED, None), (UNRELEASED[0], None), (UNRELEASED[1], "Base")],
        [
            BAD_LAYER.format(scope=_scope(UNRELEASED[1]), path=DRAFT),
            NOT_CARRIED.format(scope=_scope(BASE)),
            MADE_PRIMARY.format(scope=_scope(RELEASED)),
        ],
    ),
}


@pytest.mark.parametrize("case", BASE_REFUSALS)
def test_stops_before_staging_when_the_draft_does_not_carry_a_base_as_it_is(
    repo: Path, case: str
) -> None:
    """A base scope enters through its restore manifest, never as a scope this script signs.

    Every scope's artifacts are complete and the private key is set, so without the layer
    check the run would go on to commit and sign the draft's scopes.
    """
    predecessor, draft, lines = BASE_REFUSALS[case]
    _track_selectors(repo, predecessor, draft)
    _write_scope(repo, BASE)  # untracked and unsigned, as the unreleased scopes are
    start = _cut_release_branch(repo)

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == "".join(f"{line}\n" for line in lines)
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []
    for version in (BASE, *UNRELEASED):
        assert not _manifest(repo, version).exists()


# A selector spells each part of a scope as releases._SCOPE_COMPONENT_RE allows and lists
# each scope once. Bash reads "2026-05-01 " as 2026-05-01, so a misspelled name can stand
# for a base scope's files.
MISSPELLED = (
    "a scope in {path} has {field} {value!r}; a selector spells each part of a scope as a"
    " lowercase letter or digit followed by up to 255 lowercase letters, digits, '.', '_'"
    " or '-'"
)
REPEATED = "scope {scope} appears more than once in {path}; a selector selects each scope once"
RawScopes = list[dict[str, str]]


def _raw(
    version: str,
    *,
    jurisdiction: str = JURISDICTION,
    document_class: str = DOCUMENT_CLASS,
    layer: str | None = None,
) -> dict[str, str]:
    raw = {"jurisdiction": jurisdiction, "document_class": document_class, "version": version}
    if layer is not None:
        raw["layer"] = layer
    return raw


def _track_raw_selectors(repo: Path, predecessor: RawScopes, draft: RawScopes) -> None:
    """Rewrite test-rel-1 and the test-rel-2 draft with these raw scopes, and commit them."""
    _write_json(repo / PREDECESSOR, {"name": "test-rel-1", "scopes": predecessor})
    _write_json(
        repo / DRAFT, {"name": "test-rel-2", "description": DRAFT_DESCRIPTION, "scopes": draft}
    )
    _git(repo, "add", PREDECESSOR, DRAFT)
    _git(repo, "commit", "-qm", "Spell the selectors")


CARRIED_BASE: RawScopes = [_raw(BASE, layer="base"), _raw(RELEASED)]
DRAFT_TAIL: RawScopes = [_raw(RELEASED), *(_raw(version) for version in UNRELEASED)]
# case: (the predecessor's scopes, the draft's, and every line the run stops with)
SPELLING_REFUSALS: dict[str, tuple[RawScopes, RawScopes, list[str]]] = {
    "draft-version-trailing-space": (
        CARRIED_BASE,
        [_raw(BASE, layer="base"), _raw(f"{BASE} "), *DRAFT_TAIL],
        [MISSPELLED.format(path=DRAFT, field="version", value=f"{BASE} ")],
    ),
    "draft-jurisdiction-trailing-space": (
        CARRIED_BASE,
        [_raw(BASE, layer="base"), _raw(BASE, jurisdiction=f"{JURISDICTION} "), *DRAFT_TAIL],
        [MISSPELLED.format(path=DRAFT, field="jurisdiction", value=f"{JURISDICTION} ")],
    ),
    "draft-document-class-leading-tab": (
        CARRIED_BASE,
        [_raw(BASE, layer="base"), _raw(BASE, document_class=f"\t{DOCUMENT_CLASS}"), *DRAFT_TAIL],
        [MISSPELLED.format(path=DRAFT, field="document_class", value=f"\t{DOCUMENT_CLASS}")],
    ),
    "draft-version-trailing-newline": (
        CARRIED_BASE,
        [_raw(BASE, layer="base"), _raw(f"{BASE}\n"), *DRAFT_TAIL],
        [MISSPELLED.format(path=DRAFT, field="version", value=f"{BASE}\n")],
    ),
    "predecessor-version-trailing-space": (
        [_raw(f"{RELEASED} ")],
        DRAFT_TAIL,
        [MISSPELLED.format(path=PREDECESSOR, field="version", value=f"{RELEASED} ")],
    ),
    "predecessor-lists-a-base-then-the-same-scope-as-primary": (
        [_raw(BASE, layer="base"), _raw(BASE), _raw(RELEASED)],
        [_raw(BASE), *DRAFT_TAIL],
        [REPEATED.format(scope=_scope(BASE), path=PREDECESSOR)],
    ),
    # The layer check would read the base and add its own line: the run stops before it.
    "predecessor-lists-a-scope-as-primary-then-as-a-base": (
        [_raw(BASE), _raw(BASE, layer="base"), _raw(RELEASED)],
        [_raw(BASE), *DRAFT_TAIL],
        [REPEATED.format(scope=_scope(BASE), path=PREDECESSOR)],
    ),
    "draft-lists-a-scope-twice": (
        CARRIED_BASE,
        [_raw(RELEASED), _raw(UNRELEASED[0]), _raw(UNRELEASED[0]), _raw(UNRELEASED[1])],
        [REPEATED.format(scope=_scope(UNRELEASED[0]), path=DRAFT)],
    ),
    "draft-scope-without-a-version": (
        CARRIED_BASE,
        [{"jurisdiction": JURISDICTION, "document_class": DOCUMENT_CLASS}, *DRAFT_TAIL],
        [MISSPELLED.format(path=DRAFT, field="version", value=None)],
    ),
}


@pytest.mark.parametrize("case", SPELLING_REFUSALS)
def test_stops_before_staging_when_a_selector_misspells_or_repeats_a_scope(
    repo: Path, case: str
) -> None:
    """A part a selector cannot spell, or a scope listed twice, stops the run before step 1.

    Without the check, bash would read a misspelled base as the base itself and stage and
    sign it, and a predecessor listing a base again as primary would let the draft carry
    it as primary.
    """
    predecessor, draft, lines = SPELLING_REFUSALS[case]
    _track_raw_selectors(repo, predecessor, draft)
    _write_scope(repo, BASE)  # untracked and unsigned, as the unreleased scopes are
    start = _cut_release_branch(repo)

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == "".join(f"{line}\n" for line in lines)
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []
    for version in (BASE, *UNRELEASED):
        assert not _manifest(repo, version).exists()


def test_the_preflight_spells_scope_parts_as_a_selector_does() -> None:
    match = re.search(r'COMPONENT = re\.compile\(r"(.*?)"\)', SCRIPT.read_text())

    assert match is not None
    assert match.group(1) == releases._SCOPE_COMPONENT_RE.pattern


def _draft_with(**fields: object) -> dict:
    """The default draft, named first after test-rel-1, with these fields set."""
    draft = _selector("test-rel-2", [RELEASED, *UNRELEASED], description=DRAFT_DESCRIPTION)
    return {**draft, **fields}


# case: the draft, which the selector parser refuses for one reason
PARSER_REFUSALS: dict[str, dict] = {
    "not-a-class": _draft_with(
        scopes=[
            _raw(RELEASED),
            _raw(UNRELEASED[0]),
            _raw(UNRELEASED[1], document_class="not-a-class"),
        ]
    ),
    "extra-layer-field": _draft_with(
        scopes=[_raw(RELEASED), _raw(UNRELEASED[0]), {**_raw(UNRELEASED[1]), "Layer": "base"}]
    ),
    "bad-name": _draft_with(name="Next Cut"),
    "top-level-field": _draft_with(notes="cut by hand"),
    "quality-profile": _draft_with(quality_profile="strict"),
}


@pytest.mark.parametrize("case", PARSER_REFUSALS)
def test_stops_on_a_draft_the_selector_parser_refuses(
    repo: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """A draft validate-release would refuse in step 4 stops the run before step 1.

    The spelling and layer checks pass each of these drafts.
    """
    _commit_selectors(repo, {DRAFT: PARSER_REFUSALS[case]}, "Draft the parser refuses")
    start = _cut_release_branch(repo)
    monkeypatch.chdir(repo)  # the script loads the draft by the path it was given
    with pytest.raises(ValueError) as refusal:
        releases.ReleaseManifest.load(DRAFT)

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == f"{DRAFT} does not load as a release selector: {refusal.value}\n"
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []


def test_stops_on_a_predecessor_the_selector_parser_refuses(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The predecessor gets the parser load too, after the draft, and stops the run before step 1.

    Main commits test-rel-1 with a top-level field the parser refuses, so the predecessor
    passes the checks against HEAD and the merge base, and the spelling and layer checks.
    """
    selector = {**_selector("test-rel-1", [RELEASED]), "notes": "cut by hand"}
    _commit_selectors(repo, {PREDECESSOR: selector}, "Predecessor the parser refuses")
    start = _cut_release_branch(repo)
    monkeypatch.chdir(repo)  # the script loads the predecessor by the path it was given
    with pytest.raises(ValueError) as refusal:
        releases.ReleaseManifest.load(PREDECESSOR)

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == (
        f"{PREDECESSOR} does not load as a release selector: {refusal.value}\n"
    )
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []


# case: the draft, and the one line the run stops with
MALFORMED_SCOPES: dict[str, tuple[dict, str]] = {
    "version-list": (
        _draft_with(
            scopes=[_raw(RELEASED), _raw(UNRELEASED[0]), {**_raw(UNRELEASED[1]), "version": []}]
        ),
        MISSPELLED.format(path=DRAFT, field="version", value=[]),
    ),
    "jurisdiction-object": (
        _draft_with(
            scopes=[
                _raw(RELEASED),
                _raw(UNRELEASED[0]),
                {**_raw(UNRELEASED[1]), "jurisdiction": {}},
            ]
        ),
        MISSPELLED.format(path=DRAFT, field="jurisdiction", value={}),
    ),
    "scope-as-list": (
        _draft_with(
            scopes=[
                _raw(RELEASED),
                _raw(UNRELEASED[0]),
                [JURISDICTION, DOCUMENT_CLASS, UNRELEASED[1]],
            ]
        ),
        f"a scope in {DRAFT} is {[JURISDICTION, DOCUMENT_CLASS, UNRELEASED[1]]!r}; a selector"
        " gives each scope as an object",
    ),
    "scopes-not-a-list": (
        _draft_with(scopes=UNRELEASED[0]),
        f'{DRAFT} has no list of scopes; a selector lists its scopes under "scopes"',
    ),
}


@pytest.mark.parametrize("case", MALFORMED_SCOPES)
def test_stops_with_one_line_on_a_malformed_scope(repo: Path, case: str) -> None:
    """A scope part that is not a string, or a scope that is not an object, gets one line."""
    draft, line = MALFORMED_SCOPES[case]
    _commit_selectors(repo, {DRAFT: draft}, "Draft a malformed scope")
    start = _cut_release_branch(repo)

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert result.stderr == line + "\n"
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []


def test_skips_a_base_scope_the_predecessor_has_as_a_base(repo: Path) -> None:
    """A base carried as it is is not unreleased: the run commits and signs none of it.

    Main commits and signs the base, so that validate-release can read its artifacts.
    """
    _ingest_pr(repo, (BASE,))
    carried: LayeredScopes = [(BASE, "base"), (RELEASED, None)]
    _track_selectors(repo, carried, [*carried, (UNRELEASED[0], None)])
    _write_scope(repo, UNRELEASED[0])
    _set_main_refs(repo, "origin-main")
    _git(repo, "checkout", "-qb", "release")
    start = _git(repo, "rev-parse", "HEAD")

    result = _run(repo)

    _assert_cut(repo, result, start)
    assert "unreleased scopes: 1 (draft test-rel-2)\n" in result.stdout
    assert _signed_versions() == [UNRELEASED[0]]
    scope = _scope(UNRELEASED[0])
    assert _git(repo, "show", "--name-only", "--format=", "HEAD~2").splitlines() == [
        f"data/corpus/coverage/{scope}.json",
        f"data/corpus/inventory/{scope}.json",
        f"data/corpus/provisions/{scope}.jsonl",
        f"data/corpus/sources/{scope}/source.html",
    ]
    assert _git(repo, "show", "--name-only", "--format=", "HEAD~1").splitlines() == [
        f"{MANIFEST_DIR}/{UNRELEASED[0]}.json"
    ]


# Two earlier cuts still mark BASE as a base. A later cut replaced it with REPLACING, or
# carries no base, so the predecessor says nothing about BASE.
REPLACING = "2026-05-02"
EARLIER = ("manifests/releases/test-rel-0.json", "manifests/releases/test-rel-0a.json")
TRACKED_BASE = (
    "base scope {scope} of {path} is primary in the draft; a scope that a tracked selector"
    ' marks "layer": "base" is selected only as a base, never signed as a primary scope'
)
# case: (the predecessor's scopes, the draft's)
TRACKED_BASE_REFUSALS: dict[str, tuple[LayeredScopes, LayeredScopes]] = {
    "replaced-base-re-added": (
        [(REPLACING, "base"), (RELEASED, None)],
        [(REPLACING, "base"), (RELEASED, None), (BASE, None), *PRIMARIES],
    ),
    "predecessor-lacks-the-base": (
        [(RELEASED, None)],
        [(RELEASED, None), (BASE, None), *PRIMARIES],
    ),
}


@pytest.mark.parametrize("case", TRACKED_BASE_REFUSALS)
def test_stops_before_staging_when_the_draft_selects_a_tracked_base_as_primary(
    repo: Path, case: str
) -> None:
    """A scope that any tracked selector marks as a base is never signed as a primary scope.

    The predecessor does not carry the base, so the comparison with it finds nothing:
    without the tracked selectors the run would commit and sign the base as unreleased.
    The line names the first selector, in name order, that marks the scope as a base.
    """
    predecessor, draft = TRACKED_BASE_REFUSALS[case]
    for path in EARLIER:
        earlier = _layered_selector(Path(path).stem, [(BASE, "base"), (RELEASED, None)])
        _write_json(repo / path, earlier)
    _git(repo, "add", *EARLIER)  # committed with the two selectors below
    _track_selectors(repo, predecessor, draft)
    _write_scope(repo, BASE)  # untracked and unsigned, as the unreleased scopes are
    start = _cut_release_branch(repo)

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == TRACKED_BASE.format(scope=_scope(BASE), path=EARLIER[0]) + "\n"
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []
    for version in (BASE, *UNRELEASED):
        assert not _manifest(repo, version).exists()


@pytest.mark.parametrize("hide", ["skip-worktree", "sparse"])
def test_stops_on_a_tracked_base_hidden_from_the_working_tree(repo: Path, hide: str) -> None:
    """A tracked selector is one committed at HEAD, whether or not the working tree shows it.

    The predecessor lacks the base, and the only selector that marks it is off disk while
    the tracked tree stays clean. A check of the files on disk would find no tracked base
    and commit and sign the base as unreleased.
    """
    earlier = EARLIER[0]
    _write_json(
        repo / earlier, _layered_selector(Path(earlier).stem, [(BASE, "base"), (RELEASED, None)])
    )
    _git(repo, "add", earlier)  # committed with the two selectors below
    _track_selectors(repo, [(RELEASED, None)], [(RELEASED, None), (BASE, None), *PRIMARIES])
    _write_scope(repo, BASE)  # untracked and unsigned, as the unreleased scopes are
    start = _cut_release_branch(repo)
    if hide == "skip-worktree":
        _git(repo, "update-index", "--skip-worktree", earlier)
        (repo / earlier).unlink()
    else:
        _git(repo, "sparse-checkout", "set", "--no-cone", "/*", f"!/{earlier}")
    assert not (repo / earlier).exists()
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == TRACKED_BASE.format(scope=_scope(BASE), path=earlier) + "\n"
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []


def test_an_untracked_selector_does_not_stop_the_run(repo: Path) -> None:
    """A selector file that HEAD does not commit is not a tracked selector."""
    start = _cut_release_branch(repo)
    scratch = repo / "manifests/releases/scratch.json"
    _write_json(scratch, _layered_selector("scratch", [(RELEASED, "base")]))

    result = _run(repo)

    _assert_cut(repo, result, start)
    assert scratch.exists()


def test_stops_when_the_target_is_committed_but_hidden(repo: Path) -> None:
    """The draft's selector name is taken once HEAD commits it, even off disk."""
    _write_json(repo / TARGET, _selector("test-rel-2", [RELEASED]))
    _git(repo, "add", TARGET)
    _git(repo, "commit", "-qm", "Track test-rel-2")
    start = _cut_release_branch(repo)
    _git(repo, "update-index", "--skip-worktree", TARGET)
    (repo / TARGET).unlink()
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == f"{TARGET} already exists; selectors are immutable\n"
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    assert not (repo / TARGET).exists()
    assert _uv_calls() == []


def test_stops_with_one_line_when_the_tracked_selectors_cannot_be_read(repo: Path) -> None:
    """A selector entry that HEAD commits as something other than a file stops the run.

    Main commits manifests/releases/alias.json as a symlink to test-rel-1.json. The run
    prints one line naming it, not a traceback, before step 1.
    """
    alias = "manifests/releases/alias.json"
    os.symlink("test-rel-1.json", repo / alias)
    _git(repo, "add", alias)
    _git(repo, "commit", "-qm", "Commit a selector symlink")
    start = _cut_release_branch(repo)

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert result.stderr.startswith("cannot read the tracked selectors at HEAD: ")
    assert result.stderr.endswith(f"{alias} is not a selector file\n")
    assert result.stderr.count("\n") == 1
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == start
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []


NAMED_ONLY = (
    "{predecessor} is not manifests/releases/{named}.json as committed at HEAD, the selector"
    " {draft} names first in its description; pass that file"
)
UNNAMED = (
    "{draft} names no tracked selector in its description; a draft names its predecessor"
    " first, and this script compares the draft with that selector only"
)
NOT_ON_MAIN = (
    "manifests/releases/{named}.json is not at the merge base of HEAD with {refs}; a draft's"
    " predecessor is a selector main already tracks, as of the last fetch, so cut the draft"
    " from one of those, or fetch and merge main first"
)
CHANGED_SINCE_MAIN = (
    "manifests/releases/{named}.json differs from its copy at the merge base of HEAD with"
    " {refs}; a tracked selector is never rewritten, so cut the draft from it as main has it"
)
# The predecessor the draft should have carried BASE from, and the draft that carries it.
CARRIES_BASE: LayeredScopes = [(BASE, "base"), (RELEASED, None)]
ADDS_BASE: LayeredScopes = [*CARRIES_BASE, *PRIMARIES]
# A selector cut on the release branch, after the branch point.
BRANCH_CUT = "manifests/releases/test-rel-1b.json"


def _commit_selectors(repo: Path, selectors: dict[str, dict], message: str) -> None:
    for path, selector in selectors.items():
        _write_json(repo / path, selector)
    _git(repo, "add", *selectors)
    _git(repo, "commit", "-qm", message)


def _cut_on_the_branch(repo: Path) -> None:
    """Commit test-rel-1b, carrying BASE, and a draft that names it, on the release branch."""
    _commit_selectors(
        repo,
        {
            BRANCH_CUT: _layered_selector("test-rel-1b", CARRIES_BASE, DRAFT_DESCRIPTION),
            DRAFT: _layered_selector("test-rel-2", ADDS_BASE, "Successor to test-rel-1b."),
        },
        "Cut test-rel-1b on the branch",
    )


# case: the predecessor argument, and the line the run stops with
PREDECESSOR_REFUSALS = {
    "untracked-copy": (
        "docs/ingest-runs/pred-copy.json",
        NAMED_ONLY.format(
            predecessor="docs/ingest-runs/pred-copy.json", named="test-rel-1", draft=DRAFT
        ),
    ),
    "older-tracked-selector": (
        EARLIER[0],
        NAMED_ONLY.format(predecessor=EARLIER[0], named="test-rel-1", draft=DRAFT),
    ),
    "assume-unchanged-edit": (
        PREDECESSOR,
        NAMED_ONLY.format(predecessor=PREDECESSOR, named="test-rel-1", draft=DRAFT),
    ),
    "unnamed-draft": (PREDECESSOR, UNNAMED.format(draft=DRAFT)),
    "another-selector-named-first": (
        PREDECESSOR,
        NAMED_ONLY.format(predecessor=PREDECESSOR, named="test-rel-0", draft=DRAFT),
    ),
    "named-selector-hidden": (
        PREDECESSOR,
        NAMED_ONLY.format(predecessor=PREDECESSOR, named="test-rel-0", draft=DRAFT),
    ),
    # In the origin-main layout both refs resolve to one commit.
    "edited-on-the-branch": (
        PREDECESSOR,
        CHANGED_SINCE_MAIN.format(named="test-rel-1", refs="origin/main and main"),
    ),
    "predecessor-cut-on-the-branch": (
        BRANCH_CUT,
        NOT_ON_MAIN.format(named="test-rel-1b", refs="origin/main and main"),
    ),
}


@pytest.mark.parametrize("case", PREDECESSOR_REFUSALS)
def test_stops_unless_the_predecessor_is_the_one_the_draft_names(repo: Path, case: str) -> None:
    """The predecessor argument is the committed selector the draft names first.

    Each passed file carries BASE as a base, so the draft's BASE looks carried and the
    layer report finds nothing; the selector the draft names, as main has it, lacks it.
    When HEAD has a merge base with main, that selector must be there, unchanged.
    """
    predecessor, line = PREDECESSOR_REFUSALS[case]
    if case == "unnamed-draft":
        _commit_selectors(
            repo,
            {DRAFT: _layered_selector("test-rel-2", [(RELEASED, None), *PRIMARIES])},
            "Draft without a description",
        )
    elif case in ("another-selector-named-first", "named-selector-hidden"):
        named_first = "Successor to test-rel-0; replaces test-rel-1."
        _commit_selectors(
            repo,
            {
                EARLIER[0]: _layered_selector("test-rel-0", [(RELEASED, None)]),
                PREDECESSOR: _layered_selector("test-rel-1", CARRIES_BASE),
                DRAFT: _layered_selector("test-rel-2", ADDS_BASE, named_first),
            },
            "Name test-rel-0 first",
        )
    elif case == "older-tracked-selector":
        _write_json(repo / EARLIER[0], _layered_selector("test-rel-0", CARRIES_BASE))
        _git(repo, "add", EARLIER[0])  # committed with the two selectors below
        _track_selectors(repo, [(RELEASED, None)], ADDS_BASE)
    elif case != "predecessor-cut-on-the-branch":
        _track_selectors(repo, [(RELEASED, None)], ADDS_BASE)
    _cut_release_branch(repo)
    if case == "untracked-copy":
        _write_json(repo / predecessor, _layered_selector("test-rel-1", CARRIES_BASE))
    elif case == "assume-unchanged-edit":
        _git(repo, "update-index", "--assume-unchanged", PREDECESSOR)
        _write_json(repo / PREDECESSOR, _layered_selector("test-rel-1", CARRIES_BASE))
    elif case == "named-selector-hidden":
        _git(repo, "update-index", "--skip-worktree", EARLIER[0])
        (repo / EARLIER[0]).unlink()
    elif case == "edited-on-the-branch":
        _commit_selectors(
            repo,
            {PREDECESSOR: _layered_selector("test-rel-1", CARRIES_BASE)},
            "Add a base to test-rel-1",
        )
    elif case == "predecessor-cut-on-the-branch":
        _cut_on_the_branch(repo)
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, predecessor)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == line + "\n"
    assert result.stdout == ""
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    _assert_resumable(repo)
    assert _uv_calls() == []


@pytest.mark.parametrize(
    "case",
    [
        "spelled-with-a-dot",
        "predecessor-cut-on-the-branch-without-main",
        "predecessor-on-newer-local-main",
        "predecessor-on-newer-origin-main",
    ],
)
def test_cuts_when_the_predecessor_is_the_one_the_draft_names(repo: Path, case: str) -> None:
    """Controls: the named selector, spelled another way, or checked by the HEAD rule alone.

    With no merge base with main, a predecessor first committed on the release branch
    passes. When origin/main is behind main, the merge base with main counts, and when
    main is behind origin/main, the merge base with origin/main counts.
    """
    predecessor = PREDECESSOR
    if case == "spelled-with-a-dot":
        predecessor = f"./{PREDECESSOR}"
        _cut_release_branch(repo)
    elif case == "predecessor-cut-on-the-branch-without-main":
        _ingest_pr(repo, (BASE,))  # main commits and signs the base validate-release reads
        for version in UNRELEASED:
            _write_scope(repo, version)
        _set_main_refs(repo, "no-main")
        _git(repo, "checkout", "-qb", "release")
        _cut_on_the_branch(repo)
        predecessor = BRANCH_CUT
    elif case == "predecessor-on-newer-local-main":
        # origin/main still points at main's commit before test-rel-1 was tracked.
        for version in UNRELEASED:
            _write_scope(repo, version)
        _git(repo, "update-ref", "refs/remotes/origin/main", "main~1")
        assert _git(repo, "ls-tree", "--name-only", "origin/main", "--", PREDECESSOR) == ""
        assert _git(repo, "ls-tree", "--name-only", "main", "--", PREDECESSOR) == PREDECESSOR
        _git(repo, "checkout", "-qb", "release")
    else:
        # A fetch moved origin/main to main's tip, and the release branch starts there;
        # local main still points at its commit before test-rel-1 was tracked.
        for version in UNRELEASED:
            _write_scope(repo, version)
        _git(repo, "update-ref", "refs/remotes/origin/main", "main")
        _git(repo, "checkout", "-qb", "release")
        _git(repo, "branch", "-f", "main", "main~1")
        assert _git(repo, "ls-tree", "--name-only", "main", "--", PREDECESSOR) == ""
        assert _git(repo, "ls-tree", "--name-only", "origin/main", "--", PREDECESSOR) == PREDECESSOR
    start = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, predecessor)

    _assert_cut(repo, result, start)
    if case == "predecessor-cut-on-the-branch-without-main":
        assert "neither origin/main nor main shares history with HEAD;" in result.stdout


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
        # No guard ref, merge base or main bases: no main to compare.
        [
            sys.executable, "-", "", "", "", str(scope_list),
            f"{MANIFEST_DIR}/{PLAN_VERSION}.json", SCRIPT_COMMAND.format(version=PLAN_VERSION),
        ],
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
        if change == "add":  # generated names start "f-" or "d-", so this one is new
            added = corpus / "sources" / PLAN_SCOPE / "added.html"
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
