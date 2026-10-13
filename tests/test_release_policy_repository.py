"""The repository's release policy files agree with its locks, selectors and run notes.

``manifests/withdrawn-scopes.yaml`` is the freeze guard for every withdrawn
scope: a tracked selector may select one only if the registry names it, pinned
to its current selector digest. ``test (3.14)`` is a required check, so this
gates merges as well as ``validate_release`` gates publication.
``manifests/release-content-baseline.json`` is checked in full by the CI step
``content-check --all --check-baseline``; here, the audited July recovery
scopes and their replacements are re-scanned.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import pytest

from axiom_corpus.corpus.content_quality import CONTENT_CHECK_VERSION
from axiom_corpus.corpus.release_policy import (
    CONTENT_BASELINE_PATH,
    WITHDRAWN_SCOPES_PATH,
    ReleaseGatePolicy,
    WithdrawnScope,
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
    statute scopes) are listed, so they validate as they did; the next cut in
    each line must take the swap.
    """
    for entry in _policy().withdrawn.values():
        selecting = {
            name for name, release in _selectors().items() if entry.scope.key in release.scope_keys
        }
        assert set(entry.allowances) == selecting, scope_label(entry.scope)


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
    assert scan_scope(CORPUS_ROOT, key) == recorded


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
