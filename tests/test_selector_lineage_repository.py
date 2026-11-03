"""No tracked selector breaks its line without a record (axiom-corpus#935).

The check (``axiom_corpus.corpus.selector_lineage``) reads only the selector
files under ``manifests/releases/`` and ``manifests/selector-lineage-baseline.yaml``:
no corpus fetch, no database, no git history beyond this commit's date. It
fails on a cut that selects no version of a ``(jurisdiction, document_class)``
pair its predecessor carries, names a predecessor another cut already succeeds,
extends a fork's branch the line did not continue, names no tracked
predecessor without a first-cut record, or forms a cycle. ``test (3.14)`` is a
required check, so none of these merges unrecorded. A document that leaves a
pair the cut still carries is not checked.
"""

from __future__ import annotations

import subprocess
from functools import cache
from pathlib import Path

from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.selector_lineage import (
    LINEAGE_BASELINE_PATH,
    Cycle,
    DroppedPair,
    EndedBranch,
    Fork,
    LineageBaseline,
    UnnamedPredecessor,
    check_selector_lineage,
    load_lineage_baseline,
    load_tracked_selectors,
    pair_label,
)
from axiom_corpus.release.manifest import selector_sha256

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASES = REPO_ROOT / "manifests" / "releases"

# The day the check began. Entries listed on it are the drops, forks and first
# cuts that were already on main (980e39792); every later entry is a release
# decision.
GUARD_BEGAN = "2026-11-02"
FIRST_CUTS_ON_MAIN_WHEN_THE_GUARD_BEGAN = 100
DROPS_ON_MAIN_WHEN_THE_GUARD_BEGAN = {
    ("uk-rulespec-2026-08-02", "uk-rulespec-2026-07-26", "uk-shropshire/manual"),
}
# Each fork's successors, and the ones the line continued through.
FORKS_ON_MAIN_WHEN_THE_GUARD_BEGAN = {
    "us-rulespec-2026-07-21-az-140es-current": (
        ("us-rulespec-2026-07-21-oh-hb96-current", "us-rulespec-2026-07-22-current"),
        ("us-rulespec-2026-07-22-current",),
    ),
    "us-rulespec-2026-07-22-current-la-status-fix": (
        (
            "us-rulespec-2026-07-22-hi-capital-gain-current",
            "us-rulespec-2026-07-24-cms-435-correction",
        ),
        ("us-rulespec-2026-07-24-cms-435-correction",),
    ),
    "us-rulespec-2026-08-08-obbb-alien-snap": (
        (
            "us-rulespec-2026-08-09-cutover-surface-union",
            "us-rulespec-2026-09-24-snap-fy2027-cola",
            "us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected",
        ),
        (
            "us-rulespec-2026-08-09-cutover-surface-union",
            "us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected",
        ),
    ),
    "us-rulespec-2026-08-23-canada-338-suspension-union": (
        (
            "us-rulespec-2026-09-11-program-ingestion-union",
            "us-rulespec-2026-09-24-irs-sales-tax-tables-union",
        ),
        ("us-rulespec-2026-09-11-program-ingestion-union",),
    ),
    "us-rulespec-2026-10-09-az-des-ece-dated": (
        (
            "us-rulespec-2026-10-16-snap-abawd-memo-source-corrected",
            "us-rulespec-2026-10-20-fs-pilot-reg-e-f",
        ),
        ("us-rulespec-2026-10-20-fs-pilot-reg-e-f",),
    ),
    "us-rulespec-2026-10-22-ca-concurrent-versions": (
        ("us-rulespec-2026-10-23-ks-liheap", "us-rulespec-2026-10-25-ssi-poms-public-laws"),
        ("us-rulespec-2026-10-25-ssi-poms-public-laws",),
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


def _remedy(finding: DroppedPair | Fork | EndedBranch | UnnamedPredecessor | Cycle) -> str:
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
    if isinstance(finding, Fork):
        successors = "".join(f"\n          - {name}" for name in finding.successors)
        return (
            f"{finding.describe()}.\n  Cut the new selector from the newest selector of its "
            "line and name that one first in its description, or record the split in "
            f"{LINEAGE_BASELINE_PATH}:\n    selector_digests:"
            f"{_digests(finding.predecessor, *finding.successors)}\n    forks:\n"
            f"      - predecessor: {finding.predecessor}\n        successors:{successors}\n"
            "        continued_by: [<the successors the line goes on through>]\n"
            "        listed_on: <today>\n        reason: <why the line splits here>"
        )
    if isinstance(finding, EndedBranch):
        return (
            f"{finding.describe()}.\n  Cut it from the newest selector of the line that "
            f"continued through {', '.join(finding.continued_by)}, or, if the line now goes on "
            f"through {finding.predecessor}, add it to continued_by of the fork at "
            f"{finding.fork} in {LINEAGE_BASELINE_PATH} with the reason"
        )
    if isinstance(finding, UnnamedPredecessor):
        return (
            f"{finding.describe()}.\n  Name the selector it succeeds first in its description "
            f"(Successor to <name>.), or record it as the first cut of a line in "
            f"{LINEAGE_BASELINE_PATH}:\n    selector_digests:{_digests(finding.selector)}\n"
            "    first_cuts:\n      - listed_on: <today>\n"
            "        reason: <the line it starts>\n"
            f"        selectors:\n          - {finding.selector}"
        )
    return (
        f"{finding.describe()}.\n  Name each selector's real predecessor first in its description"
    )


def test_the_baseline_parses() -> None:
    path = REPO_ROOT / LINEAGE_BASELINE_PATH
    assert path.is_file(), f"{LINEAGE_BASELINE_PATH} is missing"
    assert _baseline() == load_lineage_baseline(path)


def test_no_tracked_selector_drops_a_pair_or_forks_its_line_without_a_record() -> None:
    """The guard: a cut names its predecessor, keeps its pairs, and grows the line's head."""
    report = check_selector_lineage(_selectors(), _baseline())
    findings = [
        *report.dropped,
        *report.forks,
        *report.ended_branches,
        *report.unnamed,
        *report.cycles,
    ]
    problems = [*(_remedy(finding) for finding in findings), *report.baseline_errors]
    assert not problems, "\n".join(problems)
    assert report.ok


def test_the_entries_listed_when_the_guard_began_are_what_main_held_then() -> None:
    """The baseline grows only by later, dated release decisions."""
    drops = {
        (record.selector, record.predecessor, pair_label(record.pair))
        for record in _baseline().drops.values()
        if record.listed_on == GUARD_BEGAN
    }
    forks = {
        record.predecessor: (record.successors, record.continued_by)
        for record in _baseline().forks.values()
        if record.listed_on == GUARD_BEGAN
    }
    first_cuts = [
        record for record in _baseline().first_cuts.values() if record.listed_on == GUARD_BEGAN
    ]
    assert drops == DROPS_ON_MAIN_WHEN_THE_GUARD_BEGAN
    assert forks == FORKS_ON_MAIN_WHEN_THE_GUARD_BEGAN
    assert len(first_cuts) == FIRST_CUTS_ON_MAIN_WHEN_THE_GUARD_BEGAN


def test_no_entry_is_listed_before_the_guard_or_after_this_commit() -> None:
    head = subprocess.run(
        ["git", "log", "-1", "--format=%cs"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    records = [
        *_baseline().drops.values(),
        *_baseline().forks.values(),
        *_baseline().first_cuts.values(),
    ]
    for record in records:
        assert GUARD_BEGAN <= record.listed_on <= head, record
