"""End-to-end runs of scripts/sign_release_scopes.sh in a throwaway git repository.

The script calls ``python3`` and ``uv run axiom-corpus-ingest``. Shims on PATH run both
with this interpreter, so sign-ingest-manifest, guard-ingested and validate-release are
the real commands; the ``uv`` shim also logs each subcommand line it runs, and on request
fails a signing or a validation, or interrupts the run during validation as Ctrl-C does.
A commit-msg hook can reject one of the script's commits, or hold it while a test sends
the script a signal, and a ``git`` shim can hold the cleanup while a test sends another. The resumability tests use these to stop a run at each step, then
check that the same command, re-run, cuts the selector.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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
# hook would.
subject=$(head -n 1 "$1")
if [ -n "${HOLD_COMMIT:-}" ] && [ "$subject" = "$HOLD_COMMIT" ]; then
  : > "$HOLD_DIR/held"
  i=0
  while [ ! -e "$HOLD_DIR/release" ] && [ "$i" -lt 600 ]; do sleep 0.1; i=$((i + 1)); done
fi
[ -n "${FAIL_COMMIT:-}" ] && [ "$subject" = "$FAIL_COMMIT" ] || exit 0
echo "simulated commit failure" >&2
exit 1
"""
GIT_SHIM = """#!/bin/sh
# While $HOLD_CLEANUP is set, hold on_exit's check that the selector is committed
# (`git cat-file -e HEAD:<target>`): create $HOLD_DIR/cleanup, then wait (up to 60 s) for
# $HOLD_DIR/release. Every git call runs the real git.
if [ -n "${HOLD_CLEANUP:-}" ] && [ "$*" = "cat-file -e HEAD:@TARGET@" ]; then
  : > "$HOLD_DIR/cleanup"
  i=0
  while [ ! -e "$HOLD_DIR/release" ] && [ "$i" -lt 600 ]; do sleep 0.1; i=$((i + 1)); done
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


def _ingest_pr(repo: Path, versions: tuple[str, ...]) -> None:
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
                f"test ingest {version}",
            ]
        )
        assert exit_code == 0
    _git(repo, "add", ".axiom/ingest-manifests")
    _git(repo, "commit", "-qm", "Sign artifacts")


def _default_sigint() -> None:
    # Bash cannot trap a signal that was ignored when it started.
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def _run(repo: Path, *, interruptible: bool = False) -> subprocess.CompletedProcess[str]:
    # In a session of its own, a simulated Ctrl-C reaches the script, never pytest.
    return subprocess.run(
        ["bash", str(SCRIPT), DRAFT, PREDECESSOR],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        start_new_session=True,
        preexec_fn=_default_sigint if interruptible else None,
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


def _assert_cut(repo: Path, result: subprocess.CompletedProcess[str], start: str) -> None:
    assert result.returncode == 0, result.stdout + result.stderr
    assert _branch_subjects(repo, start) == [CUT, SIGN, ADD]
    assert json.loads((repo / TARGET).read_text()) == json.loads((repo / DRAFT).read_text())
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""


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

    first = _run(repo, interruptible=True)

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
        result = _run(repo, interruptible=True)
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


def _start(repo: Path) -> subprocess.Popen[str]:
    """Start the script in a session of its own, so signals to its group miss pytest."""
    return subprocess.Popen(
        ["bash", str(SCRIPT), DRAFT, PREDECESSOR],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
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


def test_resumes_after_an_artifact_fix_once_its_stale_manifest_is_deleted(repo: Path) -> None:
    """The header's exception: the fix changes an artifact this branch committed and signed."""
    start = _cut_release_branch(repo)
    scope = f"{JURISDICTION}/{DOCUMENT_CLASS}/{UNRELEASED[1]}"
    sources = repo / f"data/corpus/sources/{scope}"
    # Step 1 sees a sources directory with a file in it; validate-release sees that the
    # file the provisions name is not there.
    (sources / "source.html").rename(sources / "renamed.html")

    first = _run(repo)

    assert first.returncode == 1, first.stdout + first.stderr
    assert _branch_subjects(repo, start) == [SIGN, ADD]
    _assert_resumable(repo)
    assert f"validate-release failed; not cutting {TARGET}" in first.stderr

    # The fix alone: the kept manifest describes the old artifacts, so the guard stops it.
    (sources / "renamed.html").rename(sources / "source.html")
    _git(repo, "add", "-f", "-A", f"data/corpus/sources/{scope}")
    _git(repo, "commit", "-qm", "Restore source.html")
    second = _run(repo)

    assert second.returncode == 1, second.stdout + second.stderr
    assert f"guard-ingested failed; not cutting {TARGET}" in second.stderr
    _assert_resumable(repo)

    # With the scope's manifest deleted, step 2 signs it again and the run cuts.
    _git(repo, "rm", "-q", f"{MANIFEST_DIR}/{UNRELEASED[1]}.json")
    _git(repo, "commit", "-qm", "Delete the stale manifest")
    third = _run(repo)

    assert third.returncode == 0, third.stdout + third.stderr
    assert "guard-ingested: ok" in third.stdout
    assert _branch_subjects(repo, start) == [
        CUT,
        SIGN,
        "Delete the stale manifest",
        "Restore source.html",
        SIGN,
        ADD,
    ]
    assert _signed_versions() == [*UNRELEASED, UNRELEASED[1]]


@pytest.mark.parametrize(
    "second", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP], ids=["SIGINT", "SIGTERM", "SIGHUP"]
)
def test_a_second_signal_does_not_cut_the_cleanup_short(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, second: int
) -> None:
    # As when a closing terminal sends SIGHUP twice: the first ends validate-release, and
    # the second lands while on_exit is cleaning up.
    start = _cut_release_branch(repo)
    git = shutil.which("git")
    assert git is not None
    shim = tmp_path / "bin/git"
    shim.write_text(GIT_SHIM.replace("@GIT@", git).replace("@TARGET@", TARGET))
    shim.chmod(0o755)
    hold = tmp_path / "hold"
    hold.mkdir()
    monkeypatch.setenv("HOLD_DIR", str(hold))
    monkeypatch.setenv("FAIL_VALIDATE_RELEASE", "hold")
    monkeypatch.setenv("HOLD_CLEANUP", "1")
    proc = _start(repo)
    try:
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

    assert proc.returncode == 128 + signal.SIGHUP, out + err
    assert _branch_subjects(repo, start) == [SIGN, ADD]
    _assert_resumable(repo)
    assert f"deleted {TARGET}, this run's copy of the draft: the selector was not cut" in err

    monkeypatch.delenv("FAIL_VALIDATE_RELEASE")
    monkeypatch.delenv("HOLD_CLEANUP")
    _assert_cut(repo, _run(repo), start)
