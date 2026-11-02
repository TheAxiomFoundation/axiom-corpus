"""No tracked selector drops a pair its predecessor carries, or forks its line, unrecorded.

The check (``axiom_corpus.corpus.selector_lineage``, axiom-corpus#935) reads only
the selector files under ``manifests/releases/`` and
``manifests/selector-lineage-baseline.yaml``: no corpus fetch, no database, no
git history beyond this commit's date. ``test (3.14)`` is a required check, so
a cut that silently drops a ``(jurisdiction, document_class)`` pair, or is
derived from a selector another cut already succeeds, cannot merge.
"""

from __future__ import annotations

import subprocess
from functools import cache
from pathlib import Path

from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.selector_lineage import (
    LINEAGE_BASELINE_PATH,
    DroppedPair,
    Fork,
    LineageBaseline,
    check_selector_lineage,
    load_lineage_baseline,
    load_tracked_selectors,
    pair_label,
)
from axiom_corpus.release.manifest import selector_sha256

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASES = REPO_ROOT / "manifests" / "releases"

# The day the check began. Entries listed on it are the drops and forks that
# were already on main (980e39792); every later entry is a release decision.
GUARD_BEGAN = "2026-11-02"
DROPS_ON_MAIN_WHEN_THE_GUARD_BEGAN = {
    ("uk-rulespec-2026-08-02", "uk-rulespec-2026-07-26", "uk-shropshire/manual"),
}
FORKS_ON_MAIN_WHEN_THE_GUARD_BEGAN = {
    "us-rulespec-2026-07-21-az-140es-current": (
        "us-rulespec-2026-07-21-oh-hb96-current",
        "us-rulespec-2026-07-22-current",
    ),
    "us-rulespec-2026-07-22-current-la-status-fix": (
        "us-rulespec-2026-07-22-hi-capital-gain-current",
        "us-rulespec-2026-07-24-cms-435-correction",
    ),
    "us-rulespec-2026-08-08-obbb-alien-snap": (
        "us-rulespec-2026-08-09-cutover-surface-union",
        "us-rulespec-2026-09-24-snap-fy2027-cola",
        "us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected",
    ),
    "us-rulespec-2026-08-23-canada-338-suspension-union": (
        "us-rulespec-2026-09-11-program-ingestion-union",
        "us-rulespec-2026-09-24-irs-sales-tax-tables-union",
    ),
    "us-rulespec-2026-10-09-az-des-ece-dated": (
        "us-rulespec-2026-10-16-snap-abawd-memo-source-corrected",
        "us-rulespec-2026-10-20-fs-pilot-reg-e-f",
    ),
    "us-rulespec-2026-10-22-ca-concurrent-versions": (
        "us-rulespec-2026-10-23-ks-liheap",
        "us-rulespec-2026-10-25-ssi-poms-public-laws",
    ),
}


@cache
def _selectors() -> dict[str, ReleaseManifest]:
    return load_tracked_selectors(RELEASES)


@cache
def _baseline() -> LineageBaseline:
    return LineageBaseline.load(REPO_ROOT)


def _digests(*names: str) -> str:
    return "".join(f"\n      {name}: {selector_sha256(_selectors()[name])}" for name in names)


def _remedy(finding: DroppedPair | Fork) -> str:
    """What to do about a finding, with the baseline entry that records it on purpose."""
    if isinstance(finding, DroppedPair):
        return (
            f"{finding.describe()}.\n  Keep a version of {pair_label(finding.pair)}, or record "
            f"the release decision in {LINEAGE_BASELINE_PATH}:\n    selector_digests:"
            f"{_digests(finding.predecessor, finding.selector)}\n    dropped_pairs:\n"
            f"      - selector: {finding.selector}\n"
            f"        predecessor: {finding.predecessor}\n"
            f"        pair: {pair_label(finding.pair)}\n"
            "        listed_on: <today>\n"
            "        replaced_by: [<scopes this selector selects that carry the pair's text>]\n"
            "        reason: <the decision; say why nothing replaces the pair if nothing does>"
        )
    successors = "".join(f"\n          - {name}" for name in finding.successors)
    return (
        f"{finding.describe()}.\n  Cut the new selector from the newest selector of its "
        "line and name that one first in its description, or record the split in "
        f"{LINEAGE_BASELINE_PATH}:\n    selector_digests:"
        f"{_digests(finding.predecessor, *finding.successors)}\n    forks:\n"
        f"      - predecessor: {finding.predecessor}\n        successors:{successors}\n"
        "        listed_on: <today>\n        reason: <why the line splits here>"
    )


def test_the_baseline_parses() -> None:
    path = REPO_ROOT / LINEAGE_BASELINE_PATH
    assert path.is_file(), f"{LINEAGE_BASELINE_PATH} is missing"
    assert _baseline() == load_lineage_baseline(path)


def test_no_tracked_selector_drops_a_pair_or_forks_its_line_without_a_record() -> None:
    """The guard: a cut keeps every pair of its predecessor, and one line has one head."""
    report = check_selector_lineage(_selectors(), _baseline())
    problems = [
        *(_remedy(finding) for finding in report.dropped),
        *(_remedy(fork) for fork in report.forks),
        *report.baseline_errors,
    ]
    assert not problems, "\n".join(problems)


def test_the_entries_listed_when_the_guard_began_are_what_main_held_then() -> None:
    """The baseline grows only by later, dated release decisions."""
    drops = {
        (record.selector, record.predecessor, pair_label(record.pair))
        for record in _baseline().drops.values()
        if record.listed_on == GUARD_BEGAN
    }
    forks = {
        record.predecessor: record.successors
        for record in _baseline().forks.values()
        if record.listed_on == GUARD_BEGAN
    }
    assert drops == DROPS_ON_MAIN_WHEN_THE_GUARD_BEGAN
    assert forks == FORKS_ON_MAIN_WHEN_THE_GUARD_BEGAN


def test_no_entry_is_listed_before_the_guard_or_after_this_commit() -> None:
    head = subprocess.run(
        ["git", "log", "-1", "--format=%cs"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    records = [*_baseline().drops.values(), *_baseline().forks.values()]
    for record in records:
        assert GUARD_BEGAN <= record.listed_on <= head, record
