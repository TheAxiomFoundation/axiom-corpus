"""The repository's release policy files agree with its locks, selectors and run notes.

``manifests/withdrawn-scopes.yaml`` is the freeze guard for every withdrawn
scope: a tracked selector may select one only if the registry names it, pinned
to its current selector digest. ``test (3.14)`` is a required check, so this
gates merges as well as ``validate_release`` gates publication.
``manifests/release-content-baseline.json`` is checked in full by the CI step
``content-check --all --check-baseline``; here, the audited July recovery
scopes and their replacements are re-scanned. ``manifests/reviewed-empty-nodes.yaml``
names only locked scopes and existing run notes, and the rows the hollow-root
audit found correctly empty are exactly the rows it lists from that audit.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from functools import cache
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus.content_quality import CONTENT_CHECK_VERSION
from axiom_corpus.corpus.release_policy import (
    CONTENT_BASELINE_PATH,
    REVIEWED_EMPTY_PATH,
    WITHDRAWN_SCOPES_PATH,
    ReleaseGatePolicy,
    WithdrawnScope,
    load_reviewed_empty,
    load_withdrawn_scopes,
    scan_scope,
    scope_label,
)
from axiom_corpus.corpus.releases import ReleaseManifest, ScopeKey
from axiom_corpus.release.manifest import selector_sha256

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
RELEASES = REPO_ROOT / "manifests/releases"
LOCKS = REPO_ROOT / ".axiom/corpus-locks"


@cache
def _policy() -> ReleaseGatePolicy:
    return ReleaseGatePolicy.load(REPO_ROOT)


@cache
def _selectors() -> dict[str, ReleaseManifest]:
    return {path.stem: ReleaseManifest.load(path) for path in sorted(RELEASES.glob("*.json"))}


def _locked(key: ScopeKey) -> bool:
    return (LOCKS / key[0] / key[1] / f"{key[2]}.json").is_file()


def test_the_policy_files_parse() -> None:
    policy = _policy()
    assert policy.withdrawn == load_withdrawn_scopes(REPO_ROOT / WITHDRAWN_SCOPES_PATH)
    assert policy.content_baseline.check_version == CONTENT_CHECK_VERSION
    assert (REPO_ROOT / CONTENT_BASELINE_PATH).is_file()


def test_every_named_scope_is_locked_and_every_run_note_exists() -> None:
    for entry in _policy().withdrawn.values():
        assert _locked(entry.scope.key), scope_label(entry.scope)
        for other in (*entry.replace_with, *entry.carried_by):
            assert _locked(other.key), (scope_label(entry.scope), scope_label(other))
        assert (REPO_ROOT / entry.run_note).is_file(), entry.run_note
    for key in _policy().content_baseline.entries:
        assert _locked(key), scope_label(key)
    for key, reviewed in _policy().reviewed_empty.items():
        assert _locked(key), scope_label(key)
        assert (REPO_ROOT / reviewed.run_note).is_file(), reviewed.run_note


HOLLOW_ROOT_AUDIT = "docs/ingest-runs/2026-10-13-hollow-document-root-audit.md"


def test_the_reviewed_rows_are_the_rows_the_hollow_root_audit_found_empty() -> None:
    """Each row the audit classified ``expected_empty`` is listed, citing the audit, and no other."""
    assert _policy().reviewed_empty == load_reviewed_empty(REPO_ROOT / REVIEWED_EMPTY_PATH)
    table = (REPO_ROOT / HOLLOW_ROOT_AUDIT).with_suffix(".csv")
    with table.open(encoding="utf-8", newline="") as handle:
        expected_empty = {
            (row["scope"], row["citation_path"])
            for row in csv.DictReader(handle)
            if row["classification"] == "expected_empty"
        }
    listed = {
        (scope_label(key), node.path)
        for key, reviewed in _policy().reviewed_empty.items()
        if reviewed.run_note == HOLLOW_ROOT_AUDIT
        for node in reviewed.nodes
    }
    assert len(expected_empty) == 72
    assert listed == expected_empty


def _yaml_for(name: str, release: ReleaseManifest) -> str:
    return (
        f"  {name}: {selector_sha256(release)}   # under selector_digests, and either "
        "under the scope's grandfathered_selectors (cut before the withdrawal) or as "
        "an exception with a reason"
    )


def test_no_tracked_selector_selects_a_withdrawn_scope_without_an_allowance() -> None:
    """The freeze guard: replace the scope as its registry entry says, or record why not."""
    missing: list[str] = []
    for name, release in _selectors().items():
        for key in release.scope_keys:
            entry = _policy().withdrawn.get(key)
            if entry is not None and entry.allowance_for(release) is None:
                missing.append(
                    f"{name} selects withdrawn {scope_label(key)} ({entry.remedy()}); "
                    f"to keep it on purpose add\n{_yaml_for(name, release)}"
                )
    assert not missing, "\n".join(missing)


def test_every_allowance_names_a_tracked_selector_that_selects_the_scope() -> None:
    for entry in _policy().withdrawn.values():
        for name, allowance in entry.allowances.items():
            release = _selectors().get(name)
            assert release is not None, f"{name} is not a tracked selector"
            assert entry.scope.key in release.scope_keys, (name, scope_label(entry.scope))
            assert allowance.selector_sha256 == selector_sha256(release), name


def test_cuts_since_the_decisions_carry_only_the_scopes_they_already_had() -> None:
    """A withdrawal grandfathers exactly the selectors that selected the scope at the time.

    Its later cuts (the three October unions that still carry the landing and SC
    statute scopes, and the 2026-10-13 snap-fy2026 memo cut, #848) are listed, so
    they validate as they did; the next cut in each line must take the swap.
    """
    for entry in _policy().withdrawn.values():
        selecting = {
            name for name, release in _selectors().items() if entry.scope.key in release.scope_keys
        }
        assert set(entry.allowances) == selecting, scope_label(entry.scope)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout


# The ref whose first-parent line is main's history; a checkout whose remote
# for TheAxiomFoundation/axiom-corpus has another name sets this variable.
MAIN_REF_VARIABLE = "AXIOM_CORPUS_MAIN_REF"


@cache
def _main_ref() -> str:
    """Main's ref, required: grandfathering is decided on main's own history.

    A branch's line is no stand-in (a selector added on the branch before an
    entry would look grandfathered), and a shallow clone has no first listing to
    find, so both fail with what to fetch.
    """
    ref = os.environ.get(MAIN_REF_VARIABLE, "origin/main")
    needs = "this test needs git and a git checkout of axiom-corpus with main's history"
    try:
        top = Path(_git("rev-parse", "--show-toplevel").strip())
        shallow = _git("rev-parse", "--is-shallow-repository").strip()
    except (OSError, subprocess.CalledProcessError):
        pytest.fail(needs)
    try:
        # Same directory, however spelled (symlinks, worktrees, letter case).
        same = top.samefile(REPO_ROOT)
    except OSError:
        pytest.fail(f"{needs}; git names {top} as the top level, which cannot be read")
    if not same:
        # e.g. an unpacked sdist inside another repository: its refs are not main's.
        pytest.fail(f"{needs}; git resolves {REPO_ROOT} to the repository at {top}")
    if shallow not in {"true", "false"}:
        pytest.fail(f"{needs}; this git (older than 2.15?) cannot say whether it is shallow")
    if shallow == "true":
        pytest.fail(
            "this checkout is shallow; grandfathering is decided on main's whole history: "
            "run `git fetch --unshallow origin` (CI checks out with fetch-depth: 0)"
        )
    try:
        _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except subprocess.CalledProcessError:
        pytest.fail(
            f"{ref} is not in this checkout; grandfathering is decided on main's history: "
            f"run `git fetch origin main`, or set {MAIN_REF_VARIABLE} to main's ref"
        )
    return ref


@cache
def _main_line() -> dict[str, int]:
    """Each commit of main's first-parent line, numbered from the oldest."""
    commits = _git("rev-list", "--first-parent", "--reverse", _main_ref()).split()
    return {commit: index for index, commit in enumerate(commits)}


def _main_changes(path: str) -> list[str]:
    """The commits of main's first-parent line that change ``path``, oldest first.

    ``--first-parent`` implies ``--diff-merges=first-parent``, so a file merged
    by pull request changes on the merge commit: where it reached ``main``.
    """
    return _git(
        "log", "--first-parent", "--reverse", "--format=%H", _main_ref(), "--", path
    ).split()


def _show(commit: str, path: str) -> str | None:
    """``path`` (in git's form, with "/") as of ``commit``, or None where the commit deletes it.

    Absence is read from the commit's tree; any other failure to read the file
    (a missing or unreadable object) raises rather than passing for a deletion,
    which could move an entry's first listing later.
    """
    if not _git("ls-tree", "--name-only", commit, "--", path).strip():
        return None
    return _git("show", f"{commit}:{path}")


@cache
def _entries_listed() -> dict[str, int | None]:
    """Where each withdrawn scope's entry first reached main; None while it is pending.

    Every version of the registry on main's first-parent line is parsed as
    YAML, so any spelling of an entry counts. An entry not on main yet (on a
    branch, or arriving with the pull request under test) is pending.
    """
    line = _main_line()
    registry = WITHDRAWN_SCOPES_PATH.as_posix()  # git paths use "/" on every platform
    first: dict[str, int] = {}
    changes = _main_changes(registry)
    read = 0
    for commit in changes:
        text = _show(commit, registry)
        if text is None:
            continue
        read += 1
        document = yaml.safe_load(text) or {}
        for item in document.get("scopes") or []:
            first.setdefault(str(item["scope"]).strip(), line[commit])
    if changes and not read:
        pytest.fail(f"main changes {registry} in {len(changes)} commits but none could be read")
    return {
        scope_label(entry.scope): first.get(scope_label(entry.scope))
        for entry in _policy().withdrawn.values()
    }


@cache
def _selector_versions(name: str) -> tuple[tuple[int, str], ...]:
    """(position, selector digest) of each version of a selector on main's first-parent line."""
    line = _main_line()
    path = f"manifests/releases/{name}.json"
    versions = []
    for commit in _main_changes(path):
        text = _show(commit, path)
        if text is None:
            continue
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / f"{name}.json"
            copy.write_text(text, encoding="utf-8")
            versions.append((line[commit], selector_sha256(ReleaseManifest.load(copy))))
    return tuple(versions)


def test_grandfathered_selectors_predate_the_listing_and_later_ones_are_exceptions() -> None:
    """A grandfathered selector was on main, at its pinned digest, before its entry was.

    Order on main's first-parent line decides, not dates: a selector merged
    earlier on the day an entry is written is grandfathered, one merged after
    it is not. While an entry is pending (on a branch, or in pull-request CI)
    any selector already on main at that digest may be grandfathered, but not
    one the same branch adds or changes. A selector deleted and recreated with
    other contents has a new digest, which was never on main before the entry.
    """
    listed = _entries_listed()
    for entry in _policy().withdrawn.values():
        label = scope_label(entry.scope)
        cutoff = listed[label]
        for name, allowance in entry.allowances.items():
            if allowance.is_exception:
                continue
            eligible = [
                position
                for position, digest in _selector_versions(name)
                if digest == allowance.selector_sha256 and (cutoff is None or position < cutoff)
            ]
            assert eligible, (
                f"{name} at digest {allowance.selector_sha256[:12]} was not on {_main_ref()} "
                f"before {label} was listed; list it under the entry's exceptions with a "
                "reason, or take the swap"
            )


def test_an_unreadable_version_is_an_error_not_a_deletion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only a path absent from the commit's tree reads as deleted; a failed read raises."""
    module = sys.modules[__name__]

    def listed_but_unreadable(*args: str) -> str:
        if args[0] == "ls-tree":
            return f"{WITHDRAWN_SCOPES_PATH.as_posix()}\n"
        raise subprocess.CalledProcessError(128, ["git", *args])

    monkeypatch.setattr(module, "_git", listed_but_unreadable)
    with pytest.raises(subprocess.CalledProcessError):
        _show("0" * 40, WITHDRAWN_SCOPES_PATH.as_posix())

    def absent(*args: str) -> str:
        assert args[0] == "ls-tree", args
        return ""

    monkeypatch.setattr(module, "_git", absent)
    assert _show("0" * 40, WITHDRAWN_SCOPES_PATH.as_posix()) is None


@pytest.mark.parametrize(
    ("git_present", "top", "shallow", "ref_exists", "message"),
    [
        (False, REPO_ROOT, "false", True, "with main's history$"),
        (True, REPO_ROOT.parent, "false", True, "resolves .* to the repository at"),
        (True, REPO_ROOT / "no-such-dir", "false", True, "which cannot be read$"),
        (True, REPO_ROOT, "true", True, "fetch --unshallow"),
        (True, REPO_ROOT, "false", False, "is not in this checkout"),
        (True, REPO_ROOT, "--is-shallow-repository", True, "cannot say whether it is shallow"),
    ],
)
def test_main_history_is_required(
    monkeypatch: pytest.MonkeyPatch,
    git_present: bool,
    top: Path,
    shallow: str,
    ref_exists: bool,
    message: str,
) -> None:
    """Without git, this checkout, or main's whole history the order cannot be decided."""

    def git(*args: str) -> str:
        if not git_present:
            raise FileNotFoundError("git")
        if "--show-toplevel" in args:
            return f"{top}\n"
        if "--is-shallow-repository" in args:
            return shallow + "\n"
        if not ref_exists:
            raise subprocess.CalledProcessError(1, ["git", *args])
        return "0" * 40 + "\n"

    monkeypatch.setattr(sys.modules[__name__], "_git", git)
    with pytest.raises(pytest.fail.Exception, match=message):
        _main_ref.__wrapped__()


@pytest.mark.parametrize("override", [None, "refs/remotes/upstream/main"])
def test_main_history_is_found_in_a_full_checkout(
    monkeypatch: pytest.MonkeyPatch, override: str | None
) -> None:
    """With git, this checkout and a full history, main's ref is the default or the override."""
    if override is None:
        monkeypatch.delenv(MAIN_REF_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(MAIN_REF_VARIABLE, override)

    verified: list[str] = []

    def git(*args: str) -> str:
        if "--show-toplevel" in args:
            return f"{REPO_ROOT}\n"
        if "--is-shallow-repository" in args:
            return "false\n"
        if "--verify" in args:
            verified.append(args[-1])
        return "0" * 40 + "\n"

    monkeypatch.setattr(sys.modules[__name__], "_git", git)
    expected = override or "origin/main"
    assert _main_ref.__wrapped__() == expected
    assert verified == [f"{expected}^{{commit}}"]


def test_no_entry_is_listed_in_the_future() -> None:
    """listed_on is the day the entry was written, never later than this commit."""
    head = _git("log", "-1", "--format=%cs").strip()
    for entry in _policy().withdrawn.values():
        assert entry.listed_on <= head, scope_label(entry.scope)


def _entries() -> list[WithdrawnScope]:
    return sorted(_policy().withdrawn.values(), key=lambda entry: entry.scope.key)


AUDITED = sorted(
    {entry.scope.key for entry in _entries()}
    | {other.key for entry in _entries() for other in (*entry.replace_with, *entry.carried_by)}
    | {
        ("us-mt", "regulation", "2026-07-13-recovery"),
        ("us", "guidance", "2026-07-13-recovery"),
        ("us-co", "regulation", "2026-07-13-recovery-r2026-09-11-tanf-consolidated"),
    }
)


@pytest.mark.parametrize("key", AUDITED, ids=scope_label)
def test_the_baseline_reproduces_for_the_audited_scopes(key: ScopeKey) -> None:
    recorded = _policy().content_baseline.entries.get(key)
    assert recorded is not None, scope_label(key)
    reviewed = _policy().reviewed_empty_paths(key)
    scanned = scan_scope(CORPUS_ROOT, key, reviewed_empty=reviewed)
    assert scanned == recorded
    assert set(scanned.reviewed_empty) == reviewed


@pytest.mark.parametrize(
    "key", sorted(ReleaseGatePolicy.load(REPO_ROOT).reviewed_empty), ids=scope_label
)
def test_every_reviewed_row_is_a_hollow_root_of_its_scope(key: ScopeKey) -> None:
    """The CI baseline check enforces this for every scope; here, for the listed ones."""
    reviewed = _policy().reviewed_empty_paths(key)
    scanned = scan_scope(CORPUS_ROOT, key, reviewed_empty=reviewed)
    assert set(scanned.reviewed_empty) == reviewed
    assert scanned == _policy().content_baseline.entries[key]


def test_the_content_check_command_reports_and_checks_a_scope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from axiom_corpus.corpus.cli import main

    assert main(["content-check", "us-ca/statute/2026-07-13-recovery", "--check-baseline"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["baseline_differences"] == []
    assert report["findings"] == {
        "hollow_document_root": 1,
        "navigation_body": 11,
        "version_picker_source": 1,
    }
    assert main(["content-check"]) == 2
    assert main(["content-check", "us-ca/statute/2026-07-13-recovery", "us-ca/statut"]) == 2
    assert "matches us-ca/statut" in capsys.readouterr().err
