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

For each finding the guard prints a remedy (``_remedy``): the usual fix, then
the baseline entry that records the finding on purpose.
``test_every_printed_remedy_can_be_followed`` builds each kind of finding on a
copy of main's selectors and baseline, follows each option as printed, and
requires the guard and the freeze test to pass on the result.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus.releases import ReleaseManifest, ScopeKey
from axiom_corpus.corpus.selector_lineage import (
    LINEAGE_BASELINE_PATH,
    Cycle,
    DroppedPair,
    EndedBranch,
    Fork,
    LineageBaseline,
    RecordedFork,
    UnnamedPredecessor,
    check_selector_lineage,
    load_lineage_baseline,
    load_tracked_selectors,
    pair_label,
    pair_versions,
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

Finding = DroppedPair | Fork | EndedBranch | UnnamedPredecessor | Cycle


@cache
def _selectors() -> dict[str, ReleaseManifest]:
    return load_tracked_selectors(RELEASES)


@cache
def _baseline() -> LineageBaseline:
    return LineageBaseline.load(REPO_ROOT)


def _fork_entries(baseline: LineageBaseline) -> list[RecordedFork]:
    return list(baseline.forks.values())


def _fork_branches(baseline: LineageBaseline, fork: str) -> tuple[set[str], set[str]]:
    """The successors a fork's record lists, and the ones the line continued through."""
    record = baseline.forks.get(fork)
    return (set(record.successors), set(record.continued_by)) if record else (set(), set())


def _digests(selectors: Mapping[str, ReleaseManifest], *names: str) -> str:
    return "".join(f"\n      {name}: {selector_sha256(selectors[name])}" for name in names)


def _remedy(
    finding: Finding, selectors: Mapping[str, ReleaseManifest], baseline: LineageBaseline
) -> str:
    """What to do about a finding, with the baseline entry that records it on purpose."""
    if isinstance(finding, DroppedPair):
        return (
            f"{finding.describe()}.\n  Keep a version of {pair_label(finding.pair)}, or record "
            f"the release decision in {LINEAGE_BASELINE_PATH}:\n    selector_digests:"
            f"{_digests(selectors, finding.predecessor, finding.selector)}\n    dropped_pairs:\n"
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
            f"{_digests(selectors, finding.predecessor, *finding.successors)}\n    forks:\n"
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
            f"{LINEAGE_BASELINE_PATH}:\n    selector_digests:"
            f"{_digests(selectors, finding.selector)}\n"
            "    first_cuts:\n      - listed_on: <today>\n"
            "        reason: <the line it starts>\n"
            f"        selectors:\n          - {finding.selector}"
        )
    return (
        f"{finding.describe()}.\n  Name each selector's real predecessor first in its description"
    )


def _guard_problems(
    selectors: Mapping[str, ReleaseManifest], baseline: LineageBaseline
) -> list[str]:
    """Each finding with its remedy, then each record that no longer holds."""
    report = check_selector_lineage(selectors, baseline)
    findings: list[Finding] = [
        *report.dropped,
        *report.forks,
        *report.ended_branches,
        *report.unnamed,
        *report.cycles,
    ]
    problems = [*(_remedy(finding, selectors, baseline) for finding in findings)]
    problems.extend(report.baseline_errors)
    assert report.ok == (not problems)
    return problems


def _assert_frozen(baseline: LineageBaseline) -> None:
    """The entries listed when the guard began are what main held then."""
    drops = {
        (record.selector, record.predecessor, pair_label(record.pair))
        for record in baseline.drops.values()
        if record.listed_on == GUARD_BEGAN
    }
    forks = {
        entry.predecessor: (entry.successors, entry.continued_by)
        for entry in _fork_entries(baseline)
        if entry.listed_on == GUARD_BEGAN
    }
    first_cuts = [
        record for record in baseline.first_cuts.values() if record.listed_on == GUARD_BEGAN
    ]
    assert drops == DROPS_ON_MAIN_WHEN_THE_GUARD_BEGAN
    assert forks == FORKS_ON_MAIN_WHEN_THE_GUARD_BEGAN
    assert len(first_cuts) == FIRST_CUTS_ON_MAIN_WHEN_THE_GUARD_BEGAN


def test_the_baseline_parses() -> None:
    path = REPO_ROOT / LINEAGE_BASELINE_PATH
    assert path.is_file(), f"{LINEAGE_BASELINE_PATH} is missing"
    assert _baseline() == load_lineage_baseline(path)


def test_no_tracked_selector_drops_a_pair_or_forks_its_line_without_a_record() -> None:
    """The guard: a cut names its predecessor, keeps its pairs, and grows the line's head."""
    problems = _guard_problems(_selectors(), _baseline())
    assert not problems, "\n".join(problems)


def test_the_entries_listed_when_the_guard_began_are_what_main_held_then() -> None:
    """The baseline grows only by later, dated release decisions."""
    _assert_frozen(_baseline())


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
        *_fork_entries(_baseline()),
        *_baseline().first_cuts.values(),
    ]
    for record in records:
        assert GUARD_BEGAN <= record.listed_on <= head, record


# --- every printed remedy can be followed ---

# The bases the review followed the remedies at: #746 extends the canada-338
# fork's branch the line did not continue, #729 names a selector another cut
# already succeeds, and a third successor of ca-concurrent-versions joins a
# recorded fork. If main moves past one of them, the case takes the next base
# that still shows the finding.
_REVIEW_ENDED_BRANCH = (
    "us-rulespec-2026-08-23-canada-338-suspension-union",
    "us-rulespec-2026-09-24-irs-sales-tax-tables-union",
)
_REVIEW_NEW_FORK = "us-rulespec-2026-09-14-wave4-r2-union"
_REVIEW_RECORDED_FORK = "us-rulespec-2026-10-22-ca-concurrent-versions"
_ADDED: ScopeKey = ("us-ks", "policy", "2026-11-03-remedy-test")
_NOTE = "Built by the remedy test."
_MARKER = f"{LINEAGE_BASELINE_PATH}:\n"
_SECTION_ORDER: dict[str, Callable[[Mapping[str, object]], tuple[str, ...]]] = {
    "dropped_pairs": lambda entry: (str(entry["selector"]), str(entry["pair"])),
    "forks": lambda entry: (str(entry["predecessor"]), str(entry["listed_on"])),
    "first_cuts": lambda entry: (str(entry["listed_on"]),),
}


class _MainCopy:
    """main's tracked selectors and lineage baseline, copied where a case can change them."""

    def __init__(self, root: Path) -> None:
        self.releases = root / "manifests" / "releases"
        self.baseline_path = root / LINEAGE_BASELINE_PATH
        shutil.copytree(RELEASES, self.releases)
        shutil.copyfile(REPO_ROOT / LINEAGE_BASELINE_PATH, self.baseline_path)

    def selectors(self) -> dict[str, ReleaseManifest]:
        return load_tracked_selectors(self.releases)

    def baseline(self) -> LineageBaseline:
        return load_lineage_baseline(self.baseline_path)

    def write(self, name: str, keys: Iterable[ScopeKey], description: str) -> None:
        scopes = [
            {"document_class": document_class, "jurisdiction": jurisdiction, "version": version}
            for jurisdiction, document_class, version in sorted(set(keys))
        ]
        payload = {"name": name, "description": description, "scopes": scopes}
        (self.releases / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def record(self, entry: str) -> None:
        """Add a printed baseline entry where the loader expects it, as a person pastes it."""
        data = yaml.safe_load(self.baseline_path.read_text(encoding="utf-8"))
        added = yaml.safe_load(entry)
        digests = data["selector_digests"]
        for name, digest in (added.pop("selector_digests", None) or {}).items():
            assert digests.setdefault(name, digest) == digest, f"{name} is pinned at another digest"
        data["selector_digests"] = dict(sorted(digests.items()))
        for section, entries in added.items():
            merged = [*(data.get(section) or []), *entries]
            data[section] = sorted(merged, key=_SECTION_ORDER[section])
        self.baseline_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@dataclass(frozen=True)
class _Case:
    """A finding built on the copy: the selector to fix, its real base, the scopes it adds."""

    kind: type
    selector: str
    base: str
    added: frozenset[ScopeKey]


def _successor_counts(selectors: Mapping[str, ReleaseManifest]) -> dict[str, int]:
    report = check_selector_lineage(selectors)
    counts = dict.fromkeys(selectors, 0)
    for predecessor in report.predecessors.values():
        if predecessor is not None:
            counts[predecessor] += 1
    return counts


def _ended_branches(baseline: LineageBaseline) -> set[str]:
    ended: set[str] = set()
    for fork in baseline.forks:
        successors, continued_by = _fork_branches(baseline, fork)
        ended |= successors - continued_by
    return ended


def _open_head(copy: _MainCopy) -> str:
    """A selector no tracked selector names, on a branch its line did not end."""
    selectors = copy.selectors()
    counts = _successor_counts(selectors)
    ended = _ended_branches(copy.baseline())
    heads = sorted(
        name
        for name, count in counts.items()
        if count == 0 and name not in ended and len(pair_versions(selectors[name])) > 1
    )
    assert heads, "main has no open head with two pairs"
    return heads[0]


def _write_successor(copy: _MainCopy, name: str, base: str, kind: type) -> _Case:
    copy.write(name, {*copy.selectors()[base].scope_keys, _ADDED}, f"Successor to {base}. {_NOTE}")
    return _Case(kind, name, base, frozenset({_ADDED}))


def _build_dropped_pair(copy: _MainCopy) -> _Case:
    base = _open_head(copy)
    keys = copy.selectors()[base].scope_keys
    pair = sorted(pair_versions(copy.selectors()[base]))[0]
    copy.write(
        "remedy-test-dropped-pair",
        [key for key in keys if key[:2] != pair],
        f"Successor to {base}. {_NOTE}",
    )
    return _Case(DroppedPair, "remedy-test-dropped-pair", base, frozenset())


def _build_new_fork(copy: _MainCopy) -> _Case:
    counts = _successor_counts(copy.selectors())
    recorded = set(copy.baseline().forks)
    candidates = [_REVIEW_NEW_FORK, *sorted(counts)]
    base = next(name for name in candidates if counts.get(name) == 1 and name not in recorded)
    return _write_successor(copy, "remedy-test-new-fork", base, Fork)


def _build_new_successor_of_a_recorded_fork(copy: _MainCopy) -> _Case:
    assert _REVIEW_RECORDED_FORK in copy.baseline().forks
    return _write_successor(copy, "remedy-test-new-successor", _REVIEW_RECORDED_FORK, Fork)


def _build_ended_branch(copy: _MainCopy) -> _Case:
    counts = _successor_counts(copy.selectors())
    baseline = copy.baseline()
    candidates = [
        _REVIEW_ENDED_BRANCH,
        *sorted(
            (fork, branch)
            for fork in baseline.forks
            for branch in sorted(_fork_branches(baseline, fork)[0])
        ),
    ]
    _, branch = next(
        (fork, branch)
        for fork, branch in candidates
        if branch in _fork_branches(baseline, fork)[0] - _fork_branches(baseline, fork)[1]
        and counts.get(branch) == 0
    )
    return _write_successor(copy, "remedy-test-ended-branch", branch, EndedBranch)


def _build_unnamed_predecessor(copy: _MainCopy) -> _Case:
    base = _open_head(copy)
    copy.write(
        "remedy-test-unnamed",
        {*copy.selectors()[base].scope_keys, _ADDED},
        "A successor whose description leaves its base unnamed, as 819 does.",
    )
    return _Case(UnnamedPredecessor, "remedy-test-unnamed", base, frozenset({_ADDED}))


def _build_cycle(copy: _MainCopy) -> _Case:
    base = _open_head(copy)
    keys = {*copy.selectors()[base].scope_keys, _ADDED}
    copy.write("remedy-test-cycle-a", keys, f"Successor to remedy-test-cycle-b. {_NOTE}")
    copy.write("remedy-test-cycle-b", keys, f"Successor to remedy-test-cycle-a. {_NOTE}")
    return _Case(Cycle, "remedy-test-cycle-b", base, frozenset({_ADDED}))


def _today(baseline: LineageBaseline) -> str:
    """The day after the newest entry: when a person follows the remedy."""
    listed = [
        *(record.listed_on for record in baseline.drops.values()),
        *(entry.listed_on for entry in _fork_entries(baseline)),
        *(record.listed_on for record in baseline.first_cuts.values()),
    ]
    return (date.fromisoformat(max(listed)) + timedelta(days=1)).isoformat()


def _printed_entry(remedy: str, today: str, continued_by: str | None) -> str:
    """The entry a remedy prints, with its placeholders filled as a person would fill them."""
    assert _MARKER in remedy, f"the remedy prints no baseline entry to add:\n{remedy}"
    entry = textwrap.dedent(remedy.split(_MARKER, 1)[1])
    entry = entry.replace("listed_on: <today>", f"listed_on: {today}")
    entry = re.sub(r"reason: <[^>]*>", "reason: Recorded by the remedy test.", entry)
    entry = re.sub(r"replaced_by: \[<[^>]*>\]", "replaced_by: []", entry)
    entry = re.sub(
        r"(?m)^( *)continued_by: \[<[^>]*>\]\n?",
        lambda match: "" if continued_by is None else f"{match[1]}continued_by: [{continued_by}]\n",
        entry,
    )
    assert "<" not in entry, f"the printed entry keeps a placeholder:\n{entry}"
    return entry


def _base_to_cut_from(remedy: str, case: _Case) -> str:
    """The selector a remedy says to cut from."""
    named = re.search(r"\(Successor to ([a-z0-9-]+)\.\)", remedy)
    if named:
        return named[1]
    listed = re.search(
        r"The newest selectors from [a-z0-9-]+, through its successors: ([^.]+)\.", remedy
    )
    assert listed, f"the remedy names no selector to cut from:\n{remedy}"
    others = [name for name in listed[1].split(", ") if name != case.selector]
    assert len(others) == 1, others
    return others[0]


def _follow(copy: _MainCopy, case: _Case, option: str, finding: Finding, remedy: str) -> None:
    selectors = copy.selectors()
    if option == "record":
        continued_by = None
        if isinstance(finding, Fork) and finding.predecessor not in copy.baseline().forks:
            # A new fork: the line goes on through the branch that was there first.
            continued_by = next(name for name in finding.successors if name != case.selector)
        copy.record(_printed_entry(remedy, _today(copy.baseline()), continued_by))
    elif option == "record, and the line goes on through it":
        copy.record(_printed_entry(remedy, _today(copy.baseline()), case.selector))
    elif option == "record, and the line does not go on through it":
        copy.record(_printed_entry(remedy, _today(copy.baseline()), None))
    elif option == "cut from the selector it names":
        base = _base_to_cut_from(remedy, case)
        copy.write(
            case.selector,
            {*selectors[base].scope_keys, *case.added},
            f"Successor to {base}. {_NOTE}",
        )
    elif option == "keep the pair":
        assert isinstance(finding, DroppedPair)
        assert f"Keep a version of {pair_label(finding.pair)}" in remedy, remedy
        restored = [key for key in selectors[case.base].scope_keys if key[:2] == finding.pair]
        copy.write(
            case.selector,
            {*selectors[case.selector].scope_keys, *restored},
            f"Successor to {case.base}. {_NOTE}",
        )
    elif option == "name the predecessor":
        assert "Name the selector it succeeds first in its description" in remedy, remedy
        copy.write(
            case.selector, selectors[case.selector].scope_keys, f"Successor to {case.base}. {_NOTE}"
        )
    else:
        assert option == "name each real predecessor", option
        assert "Name each selector's real predecessor first in its description" in remedy, remedy
        copy.write(
            case.selector, selectors[case.selector].scope_keys, f"Successor to {case.base}. {_NOTE}"
        )


_REMEDY_CASES: list[tuple[str, Callable[[_MainCopy], _Case], str]] = [
    ("dropped pair", _build_dropped_pair, "keep the pair"),
    ("dropped pair", _build_dropped_pair, "record"),
    ("new fork (#729)", _build_new_fork, "cut from the selector it names"),
    ("new fork (#729)", _build_new_fork, "record"),
    (
        "third successor of ca-concurrent-versions",
        _build_new_successor_of_a_recorded_fork,
        "cut from the selector it names",
    ),
    (
        "third successor of ca-concurrent-versions",
        _build_new_successor_of_a_recorded_fork,
        "record, and the line goes on through it",
    ),
    (
        "third successor of ca-concurrent-versions",
        _build_new_successor_of_a_recorded_fork,
        "record, and the line does not go on through it",
    ),
    ("ended branch (#746)", _build_ended_branch, "cut from the selector it names"),
    ("ended branch (#746)", _build_ended_branch, "record"),
    ("unnamed predecessor (#819)", _build_unnamed_predecessor, "name the predecessor"),
    ("unnamed predecessor (#819)", _build_unnamed_predecessor, "record"),
    ("cycle", _build_cycle, "name each real predecessor"),
]


@pytest.mark.parametrize(
    ("build", "option"),
    [(build, option) for _, build, option in _REMEDY_CASES],
    ids=[f"{case}: {option}" for case, _, option in _REMEDY_CASES],
)
def test_every_printed_remedy_can_be_followed(
    tmp_path: Path, build: Callable[[_MainCopy], _Case], option: str
) -> None:
    """Follow each option a remedy prints; the guard and the freeze test then pass."""
    copy = _MainCopy(tmp_path)
    case = build(copy)
    selectors, baseline = copy.selectors(), copy.baseline()
    report = check_selector_lineage(selectors, baseline)
    findings: list[Finding] = [
        *report.dropped,
        *report.forks,
        *report.ended_branches,
        *report.unnamed,
        *report.cycles,
    ]
    assert [type(finding) for finding in findings] == [case.kind], report.problems()
    _follow(copy, case, option, findings[0], _remedy(findings[0], selectors, baseline))
    problems = _guard_problems(copy.selectors(), copy.baseline())
    assert not problems, "\n".join(problems)
    _assert_frozen(copy.baseline())
