"""End-to-end runs of scripts/sign_release_scopes.sh in a throwaway git repository.

The script calls ``python3`` and ``uv run axiom-corpus-ingest``. Shims on PATH run both
with this interpreter, so sign-ingest-manifest, guard-ingested and validate-release are
the real commands; the ``uv`` shim also logs each subcommand line it runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
exec "@PYTHON@" -m axiom_corpus.corpus.cli "$@"
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


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), DRAFT, PREDECESSOR],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _uv_calls() -> list[str]:
    log = Path(os.environ["UV_CALL_LOG"])
    return log.read_text().splitlines() if log.exists() else []


def _branch_subjects(repo: Path, start: str) -> list[str]:
    return _git(repo, "log", "--format=%s", f"{start}..HEAD").splitlines()


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
    monkeypatch.delenv("FAIL_SIGN_VERSION", raising=False)
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


@pytest.mark.parametrize("guard", [*GUARD_BASES, "no-public-key"])
def test_cuts_the_selector_when_every_unreleased_scope_is_already_signed(
    repo: Path, monkeypatch: pytest.MonkeyPatch, guard: str
) -> None:
    # As in #742: the ingest PR committed and signed its scopes, so steps 1-3 commit nothing.
    _ingest_pr(repo, UNRELEASED)
    if guard == "no-public-key":
        _set_main_refs(repo, "origin-main")
        monkeypatch.delenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY")
    else:
        _set_main_refs(repo, guard)
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
    base = None if guard == "no-public-key" else GUARD_BASES[guard]
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
