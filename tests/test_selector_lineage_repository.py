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
    LineageReport,
    RecordedFork,
    UnnamedPredecessor,
    check_selector_lineage,
    line_heads,
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

type Finding = DroppedPair | Fork | EndedBranch | UnnamedPredecessor | Cycle


@cache
def _selectors() -> dict[str, ReleaseManifest]:
    return load_tracked_selectors(RELEASES)


@cache
def _baseline() -> LineageBaseline:
    return LineageBaseline.load(REPO_ROOT)


def _fork_entries(baseline: LineageBaseline) -> list[RecordedFork]:
    return [entry for entries in baseline.forks.values() for entry in entries]


def _fork_branches(baseline: LineageBaseline, fork: str) -> tuple[set[str], set[str]]:
    """The successors a fork's entries list, and the ones the line continued through."""
    return set(baseline.fork_successors(fork)), set(baseline.fork_continued_by(fork))


def _pins(selectors: Mapping[str, ReleaseManifest], baseline: LineageBaseline, *names: str) -> str:
    """The selector_digests lines an entry needs that the baseline lacks, in name order."""
    lines = "".join(
        f"\n      {name}: {selector_sha256(selectors[name])}"
        for name in sorted(set(names))
        if name not in baseline.selector_digests
    )
    return f"\n    selector_digests:{lines}" if lines else ""


def _items(names: Iterable[str], indent: int = 10) -> str:
    return "".join(f"\n{' ' * indent}- {name}" for name in names)


def _cut_from(heads: tuple[str, ...], continued_by: Iterable[str]) -> str:
    """Where the usual fix cuts from: the line's newest selector, named when there is one."""
    through = ", ".join(continued_by)
    if len(heads) == 1:
        return (
            f"{heads[0]}, the newest selector of the line that continued through {through}, "
            f"and name it first in its description (Successor to {heads[0]}.)"
        )
    newest = f" ({', '.join(heads)})" if heads else ""
    return (
        f"the newest selector of the line that continued through {through}{newest}, and name "
        "that one first in its description"
    )


_SEVERAL_CUTS = (
    "If this change adds more than one cut to the line, cut them one after another, each from "
    "the one before."
)
_ONE_ENTRY_A_DAY = (
    "after its earlier entries (decisions about one fork made on one day share one entry)"
)


def _no_longer_holds(finding: Finding) -> str:
    return (
        f"{finding.describe()}.\n  {LINEAGE_BASELINE_PATH} already records this, but the record "
        "no longer holds: undo the change the baseline errors below describe"
    )


def _changed_since_pinned(
    selectors: Mapping[str, ReleaseManifest], baseline: LineageBaseline, *names: str
) -> list[str]:
    """The names the baseline pins at a digest their selector no longer has."""
    return [
        name
        for name in names
        if name in baseline.selector_digests
        and name in selectors
        and selector_sha256(selectors[name]) != baseline.selector_digests[name]
    ]


def _remedy(
    finding: Finding, selectors: Mapping[str, ReleaseManifest], baseline: LineageBaseline
) -> str:
    """What to do about a finding: the usual fix, then the entry that records it on purpose.

    Entries are append-only. A recorded fork that gains a successor, or a branch
    the line now continues through, gets a new dated entry for its predecessor.
    A finding the baseline already records, whose record a changed selector
    broke, is fixed by undoing the change, not by recording it again.
    """
    if isinstance(finding, DroppedPair):
        if (finding.selector, finding.pair) in baseline.drops:
            return _no_longer_holds(finding)
        changed = _changed_since_pinned(selectors, baseline, finding.predecessor, finding.selector)
        if changed:
            # The pin's old digest does not say which pairs the selector had, so the
            # drop may or may not come from the change. Either way no entry can pass
            # while the pin is stale: undo the change, then see what is left.
            return (
                f"{finding.describe()}.\n  {' and '.join(changed)} changed since the baseline "
                "pinned it, and this drop may follow from that change: undo the change the "
                "baseline errors below describe, then run the check again"
            )
        return (
            f"{finding.describe()}.\n  Keep a version of {pair_label(finding.pair)}, or record "
            "the release decision, with pins in name order and drops in order of selector, then "
            f"pair, in {LINEAGE_BASELINE_PATH}:"
            f"{_pins(selectors, baseline, finding.predecessor, finding.selector)}\n"
            "    dropped_pairs:\n"
            f"      - selector: {finding.selector}\n"
            f"        predecessor: {finding.predecessor}\n"
            f"        pair: {pair_label(finding.pair)}\n"
            "        listed_on: <today>\n"
            "        replaced_by: [<scopes this selector selects that carry the pair's text>]\n"
            "        reason: <the decision; say why nothing replaces the pair if nothing does>"
        )
    if isinstance(finding, Fork):
        new = [name for name in finding.successors if name not in finding.recorded]
        if not finding.recorded:
            return (
                f"{finding.describe()}.\n  Cut the new selector from the newest selector of "
                "its line, and name that one first in its description. The newest selectors "
                f"from {finding.predecessor}, through its successors: {', '.join(finding.heads)}"
                f". {_SEVERAL_CUTS} If the line splits here on purpose, record the split, with "
                "pins in name order and the entry among the forks in order of predecessor, in "
                f"{LINEAGE_BASELINE_PATH}:"
                f"{_pins(selectors, baseline, finding.predecessor, *finding.successors)}\n"
                f"    forks:\n      - predecessor: {finding.predecessor}\n"
                "        listed_on: <today>\n"
                f"        successors:{_items(finding.successors)}\n"
                "        continued_by: [<the successors the line goes on through>]\n"
                "        reason: <why the line splits here>"
            )
        if not new:
            return _no_longer_holds(finding)
        continued_by = baseline.fork_continued_by(finding.predecessor)
        then = "".join(
            f", then {name} from {before} (Successor to {before}.)"
            for before, name in zip(new, new[1:], strict=False)
        )
        return (
            f"{finding.describe()}.\n  Cut {new[0]} from "
            f"{_cut_from(finding.heads, continued_by)}{then}. {_SEVERAL_CUTS} If the line splits "
            f"here on purpose, record {', '.join(new)} in a new entry for the fork at "
            f"{finding.predecessor}, {_ONE_ENTRY_A_DAY}, in {LINEAGE_BASELINE_PATH}:"
            f"{_pins(selectors, baseline, *new)}\n"
            f"    forks:\n      - predecessor: {finding.predecessor}\n"
            "        listed_on: <today>\n"
            f"        successors:{_items(new)}\n"
            "        continued_by: [<those of them the line goes on through; leave this line "
            "out if none>]\n"
            "        reason: <why the line splits here>"
        )
    if isinstance(finding, EndedBranch):
        return (
            f"{finding.describe()}.\n  Cut it from {_cut_from(finding.heads, finding.continued_by)}"
            f". {_SEVERAL_CUTS} If the line goes on through {finding.predecessor} on purpose, "
            f"record that in a new entry for the fork at {finding.fork}, {_ONE_ENTRY_A_DAY}, in "
            f"{LINEAGE_BASELINE_PATH}:"
            f"{_pins(selectors, baseline, finding.fork, finding.predecessor)}\n"
            f"    forks:\n      - predecessor: {finding.fork}\n"
            "        listed_on: <today>\n"
            f"        continued_by:{_items([finding.predecessor])}\n"
            "        reason: <why the line goes on through this branch>"
        )
    if isinstance(finding, UnnamedPredecessor):
        if finding.selector in baseline.first_cuts:
            return _no_longer_holds(finding)
        return (
            f"{finding.describe()}.\n  Name the selector it succeeds first in its description "
            "(Successor to <name>.), or record it as the first cut of a line, with pins in name "
            f"order, in {LINEAGE_BASELINE_PATH}:{_pins(selectors, baseline, finding.selector)}\n"
            "    first_cuts:\n      - listed_on: <today>\n"
            "        reason: <the line it starts>\n"
            f"        selectors:{_items([finding.selector])}"
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
    """What the entries listed when the guard began record is what main held then.

    Compared: the drop's selector, predecessor and pair, each fork's successors
    and continued_by, and how many first cuts are listed on that date. Reasons
    and the first cuts' names are not compared.
    """
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
# already succeeds, and a new successor of ca-concurrent-versions joins a
# recorded fork. A case falls back to another base with the same finding once
# main moves past the review's, and two cases below run on a copy where main
# has moved: #746, or a new successor of ca-concurrent-versions, has recorded
# what its remedy prints.
_REVIEW_ENDED_BRANCH = (
    "us-rulespec-2026-08-23-canada-338-suspension-union",
    "us-rulespec-2026-09-24-irs-sales-tax-tables-union",
)
_REVIEW_NEW_FORK = "us-rulespec-2026-09-14-wave4-r2-union"
_REVIEW_RECORDED_FORK = "us-rulespec-2026-10-22-ca-concurrent-versions"
# The fork whose line went on through both the union line and the dated cuts,
# so a cut from its ended branch has two newest selectors to choose from.
_TWO_LINES_ENDED_BRANCH = (
    "us-rulespec-2026-08-08-obbb-alien-snap",
    "us-rulespec-2026-09-24-snap-fy2027-cola",
)
_ADDED: ScopeKey = ("us-ks", "policy", "2026-11-03-remedy-test")
_EDITED_VERSION = "2026-11-03-remedy-test-edit"
_NOTE = "Built by the remedy test."
_MARKER = f"{LINEAGE_BASELINE_PATH}:\n"
_ONE_AFTER_ANOTHER = "cut them one after another, each from the one before"
_SHARE_ONE_ENTRY = "decisions about one fork made on one day share one entry"
_SECTION_ORDER: dict[str, Callable[[Mapping[str, object]], tuple[str, ...]]] = {
    "dropped_pairs": lambda entry: (str(entry["selector"]), str(entry["pair"])),
    "forks": lambda entry: (str(entry["predecessor"]), str(entry["listed_on"])),
    "first_cuts": lambda entry: (str(entry["listed_on"]),),
}

_CUT = "cut from the selector it names"
_RECORD = "record"
_GOES_ON = "record, and the line goes on through it"
_DOES_NOT_GO_ON = "record, and the line does not go on through it"
_KEEP = "keep the pair"
_NAME = "name the predecessor"
_NAME_EACH = "name each real predecessor"
_UNDO = "undo the change"


def _findings(report: LineageReport) -> list[Finding]:
    return [*report.dropped, *report.forks, *report.ended_branches, *report.unnamed, *report.cycles]


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

    def text(self, name: str) -> str:
        return (self.releases / f"{name}.json").read_text(encoding="utf-8")

    def write_text(self, name: str, text: str) -> None:
        (self.releases / f"{name}.json").write_text(text, encoding="utf-8")

    def write(self, name: str, keys: Iterable[ScopeKey], description: str) -> None:
        scopes = [
            {"document_class": document_class, "jurisdiction": jurisdiction, "version": version}
            for jurisdiction, document_class, version in sorted(set(keys))
        ]
        payload = {"name": name, "description": description, "scopes": scopes}
        self.write_text(name, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def record(self, *entries: str) -> None:
        """Add printed baseline entries where the loader expects them, as a person pastes them.

        A printed pin must be one the baseline lacks. Fork entries for one
        predecessor on one day are merged, as the remedies say they share one entry.
        """
        data = yaml.safe_load(self.baseline_path.read_text(encoding="utf-8"))
        digests = data["selector_digests"]
        already = set(digests)
        today: dict[tuple[str, str], dict[str, object]] = {}
        for entry in entries:
            added = yaml.safe_load(entry)
            if "selector_digests" in added:
                pins = added.pop("selector_digests")
                assert pins, f"the remedy prints an empty selector_digests block:\n{entry}"
                for name, digest in pins.items():
                    assert name not in already, f"the remedy prints {name}'s pin again"
                    assert digests.setdefault(name, digest) == digest, name
            for section, items in added.items():
                for item in items:
                    if section == "forks":
                        key = (str(item["predecessor"]), str(item["listed_on"]))
                        if key in today:
                            _merge_fork_entry(today[key], item)
                            continue
                        today[key] = item
                    data[section] = [*(data.get(section) or []), item]
        data["selector_digests"] = dict(sorted(digests.items()))
        for section, order in _SECTION_ORDER.items():
            if data.get(section):
                data[section] = sorted(data[section], key=order)
        self.baseline_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _merge_fork_entry(entry: dict[str, object], other: Mapping[str, object]) -> None:
    for field_name in ("successors", "continued_by"):
        names = {*(entry.get(field_name) or []), *(other.get(field_name) or [])}  # type: ignore[misc]
        if names:
            entry[field_name] = sorted(names)
    entry["reason"] = f"{entry['reason']} {other['reason']}"


@dataclass(frozen=True)
class _Case:
    """What a case built on the copy: the findings it expects, and how to undo or redo it.

    ``selectors`` are the new or edited selectors, in the order they would be
    cut; ``base`` is the selector the first one really succeeds (for a fork, the
    fork's predecessor); ``added`` the scopes the new selectors add to their base;
    ``original`` an edited selector's file before the edit.
    """

    kinds: tuple[type, ...]
    selectors: tuple[str, ...]
    base: str
    added: frozenset[ScopeKey] = frozenset()
    original: str = ""


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


def _unextended_ended_branches(copy: _MainCopy) -> list[tuple[str, str]]:
    """Each recorded fork's branch the line did not continue through, that nothing extends."""
    counts = _successor_counts(copy.selectors())
    baseline = copy.baseline()
    return [
        (fork, branch)
        for fork in sorted(baseline.forks)
        for branch in sorted(_fork_branches(baseline, fork)[0] - _fork_branches(baseline, fork)[1])
        if counts.get(branch) == 0
    ]


def _newest_through_continued(copy: _MainCopy, fork: str) -> tuple[str, ...]:
    baseline = copy.baseline()
    continued = {
        predecessor: baseline.fork_continued_by(predecessor) for predecessor in baseline.forks
    }
    report = check_selector_lineage(copy.selectors())
    return line_heads(report.predecessors, continued, continued[fork])


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


def _keys(copy: _MainCopy, base: str) -> set[ScopeKey]:
    return {*copy.selectors()[base].scope_keys, _ADDED}


def _write_successor(copy: _MainCopy, name: str, base: str) -> None:
    copy.write(name, _keys(copy, base), f"Successor to {base}. {_NOTE}")


def _edit(copy: _MainCopy, name: str, added: ScopeKey | None = None) -> str:
    """Add a scope, by default a version of one of its pairs, so the digest changes.

    Return the selector's file before the edit.
    """
    original = copy.text(name)
    selector = copy.selectors()[name]
    jurisdiction, document_class, _ = selector.scope_keys[0]
    keys = {*selector.scope_keys, added or (jurisdiction, document_class, _EDITED_VERSION)}
    copy.write(name, keys, selector.description or "")
    return original


def _build_dropped_pair(copy: _MainCopy) -> _Case:
    base = _open_head(copy)
    keys = copy.selectors()[base].scope_keys
    pair = sorted(pair_versions(copy.selectors()[base]))[0]
    copy.write(
        "remedy-test-dropped-pair",
        [key for key in keys if key[:2] != pair],
        f"Successor to {base}. {_NOTE}",
    )
    return _Case((DroppedPair,), ("remedy-test-dropped-pair",), base)


def _build_new_fork(copy: _MainCopy) -> _Case:
    counts = _successor_counts(copy.selectors())
    recorded = set(copy.baseline().forks)
    candidates = [_REVIEW_NEW_FORK, *sorted(counts)]
    base = next(name for name in candidates if counts.get(name) == 1 and name not in recorded)
    _write_successor(copy, "remedy-test-new-fork", base)
    return _Case((Fork,), ("remedy-test-new-fork",), base, frozenset({_ADDED}))


def _build_new_successor_of_a_recorded_fork(copy: _MainCopy) -> _Case:
    assert _REVIEW_RECORDED_FORK in copy.baseline().forks
    _write_successor(copy, "remedy-test-new-successor", _REVIEW_RECORDED_FORK)
    return _Case(
        (Fork,), ("remedy-test-new-successor",), _REVIEW_RECORDED_FORK, frozenset({_ADDED})
    )


def _build_two_new_successors_of_a_recorded_fork(copy: _MainCopy) -> _Case:
    names = ("remedy-test-new-successor-a", "remedy-test-new-successor-b")
    for name in names:
        _write_successor(copy, name, _REVIEW_RECORDED_FORK)
    return _Case((Fork,), names, _REVIEW_RECORDED_FORK, frozenset({_ADDED}))


def _ended_branch_case(copy: _MainCopy, branch: str) -> _Case:
    _write_successor(copy, "remedy-test-ended-branch", branch)
    return _Case((EndedBranch,), ("remedy-test-ended-branch",), branch, frozenset({_ADDED}))


def _build_ended_branch(copy: _MainCopy) -> _Case:
    available = _unextended_ended_branches(copy)
    fork, branch = _REVIEW_ENDED_BRANCH if _REVIEW_ENDED_BRANCH in available else available[0]
    return _ended_branch_case(copy, branch)


def _build_ended_branch_of_a_line_that_went_on_twice(copy: _MainCopy) -> _Case:
    available = [_TWO_LINES_ENDED_BRANCH, *_unextended_ended_branches(copy)]
    fork, branch = next(
        (fork, branch)
        for fork, branch in available
        if (fork, branch) in _unextended_ended_branches(copy)
        and len(_newest_through_continued(copy, fork)) > 1
    )
    return _ended_branch_case(copy, branch)


def _record_on_main(copy: _MainCopy, entry: str) -> None:
    copy.record(entry.replace("<today>", _today(copy.baseline())))


def _build_ended_branch_once_746_records_its_continuation(copy: _MainCopy) -> _Case:
    fork, branch = _REVIEW_ENDED_BRANCH
    _write_successor(copy, "remedy-test-merged-746", branch)
    _record_on_main(
        copy,
        f"forks:\n  - predecessor: {fork}\n    listed_on: <today>\n"
        f"    continued_by: [{branch}]\n    reason: The line goes on through this branch.\n",
    )
    return _build_ended_branch(copy)


def _build_new_successor_once_the_fork_goes_on_twice(copy: _MainCopy) -> _Case:
    _write_successor(copy, "remedy-test-merged-successor", _REVIEW_RECORDED_FORK)
    digest = selector_sha256(copy.selectors()["remedy-test-merged-successor"])
    _record_on_main(
        copy,
        f"selector_digests:\n  remedy-test-merged-successor: {digest}\n"
        f"forks:\n  - predecessor: {_REVIEW_RECORDED_FORK}\n    listed_on: <today>\n"
        "    successors: [remedy-test-merged-successor]\n"
        "    continued_by: [remedy-test-merged-successor]\n    reason: A second line.\n",
    )
    return _build_new_successor_of_a_recorded_fork(copy)


def _build_new_successor_and_ended_branch_at_one_fork(copy: _MainCopy) -> _Case:
    available = _unextended_ended_branches(copy)
    fork, branch = next(
        (fork, branch)
        for fork, branch in sorted(available, key=lambda item: item[0] != _REVIEW_RECORDED_FORK)
    )
    _write_successor(copy, "remedy-test-new-successor", fork)
    _write_successor(copy, "remedy-test-ended-branch", branch)
    return _Case(
        (Fork, EndedBranch),
        ("remedy-test-new-successor", "remedy-test-ended-branch"),
        fork,
        frozenset({_ADDED}),
    )


def _build_unnamed_predecessor(copy: _MainCopy) -> _Case:
    base = _open_head(copy)
    copy.write(
        "remedy-test-unnamed",
        _keys(copy, base),
        "A successor whose description leaves its base unnamed, as 819 does.",
    )
    return _Case((UnnamedPredecessor,), ("remedy-test-unnamed",), base, frozenset({_ADDED}))


def _build_cycle(copy: _MainCopy) -> _Case:
    base = _open_head(copy)
    copy.write(
        "remedy-test-cycle-a", _keys(copy, base), f"Successor to remedy-test-cycle-b. {_NOTE}"
    )
    copy.write(
        "remedy-test-cycle-b", _keys(copy, base), f"Successor to remedy-test-cycle-a. {_NOTE}"
    )
    return _Case((Cycle,), ("remedy-test-cycle-b",), base, frozenset({_ADDED}))


def _build_edited_first_cut(copy: _MainCopy) -> _Case:
    name = sorted(copy.baseline().first_cuts)[0]
    return _Case((UnnamedPredecessor,), (name,), name, original=_edit(copy, name))


def _build_edited_selector_of_a_recorded_drop(copy: _MainCopy) -> _Case:
    name = sorted(record.selector for record in copy.baseline().drops.values())[0]
    return _Case((DroppedPair,), (name,), name, original=_edit(copy, name))


def _build_edited_selector_whose_successor_lacks_the_pair_it_gained(copy: _MainCopy) -> _Case:
    """The recorded drop's selector gains a pair its successor lacks: two findings, one edit."""
    name = sorted(record.selector for record in copy.baseline().drops.values())[0]
    original = _edit(copy, name, _ADDED)
    return _Case((DroppedPair, DroppedPair), (name,), name, original=original)


def _build_edited_fork_successor_that_drops_a_pair(copy: _MainCopy) -> _Case:
    """A recorded fork's successor loses a pair its fork carries: a drop by the edited selector."""
    available = _unextended_ended_branches(copy)
    fork, branch = next(
        (fork, branch)
        for fork, branch in sorted(available, key=lambda item: item[0] != _REVIEW_RECORDED_FORK)
    )
    selectors = copy.selectors()
    original = copy.text(branch)
    pair = sorted(set(pair_versions(selectors[branch])) & set(pair_versions(selectors[fork])))[0]
    kept = [key for key in selectors[branch].scope_keys if key[:2] != pair]
    copy.write(branch, kept, selectors[branch].description or "")
    return _Case((DroppedPair, Fork), (branch,), fork, original=original)


def _build_edited_successor_of_a_recorded_fork(copy: _MainCopy) -> _Case:
    available = _unextended_ended_branches(copy)
    fork, branch = next(
        (fork, branch)
        for fork, branch in sorted(available, key=lambda item: item[0] != _REVIEW_RECORDED_FORK)
    )
    return _Case((Fork,), (branch,), fork, original=_edit(copy, branch))


def _today(baseline: LineageBaseline) -> str:
    """The day after the newest entry: when a person follows the remedy."""
    listed = [
        *(record.listed_on for record in baseline.drops.values()),
        *(entry.listed_on for entry in _fork_entries(baseline)),
        *(record.listed_on for record in baseline.first_cuts.values()),
    ]
    return (date.fromisoformat(max(listed)) + timedelta(days=1)).isoformat()


_PLACEHOLDER = re.compile(r"(?m)^( *)continued_by: \[<[^>]*>\]\n?")


def _printed_entry(
    remedy: str, today: str, choose: Callable[[list[str]], list[str]] = lambda listed: []
) -> str:
    """The entry a remedy prints, with its placeholders filled as a person would fill them.

    ``choose`` picks, from the successors the entry lists, the ones the line goes
    on through when the entry leaves that to the person.
    """
    assert _MARKER in remedy, f"the remedy prints no baseline entry to add:\n{remedy}"
    entry = textwrap.dedent(remedy.split(_MARKER, 1)[1])
    entry = entry.replace("listed_on: <today>", f"listed_on: {today}")
    entry = re.sub(r"reason: <[^>]*>", "reason: Recorded by the remedy test.", entry)
    entry = re.sub(r"replaced_by: \[<[^>]*>\]", "replaced_by: []", entry)
    if _PLACEHOLDER.search(entry):
        listed = yaml.safe_load(_PLACEHOLDER.sub("", entry))["forks"][0]["successors"]
        chosen = choose(listed)
        entry = _PLACEHOLDER.sub(
            lambda match: f"{match[1]}continued_by: [{', '.join(chosen)}]\n" if chosen else "",
            entry,
        )
    assert "<" not in entry, f"the printed entry keeps a placeholder:\n{entry}"
    return entry


_LISTED_HEADS = (
    re.compile(r"continued through [a-z0-9, -]+ \(([a-z0-9, -]+)\), and name that one first"),
    re.compile(r"The newest selectors from [a-z0-9-]+, through its successors: ([a-z0-9, -]+)\."),
)


def _bases(remedy: str, case: _Case) -> list[str]:
    """The selectors a remedy says to cut from: the one it names, or each one it lists."""
    named = [
        name
        for name in re.findall(r"\(Successor to ([a-z0-9-]+)\.\)", remedy)
        if name not in case.selectors
    ]
    if named:
        return named[:1]
    for pattern in _LISTED_HEADS:
        listed = pattern.search(remedy)
        if listed:
            bases = [name for name in listed[1].split(", ") if name not in case.selectors]
            assert bases, remedy
            return bases
    raise AssertionError(f"the remedy names no selector to cut from:\n{remedy}")


def _follow(
    copy: _MainCopy,
    case: _Case,
    option: str,
    findings: list[Finding],
    remedies: list[str],
    base: str | None,
) -> None:
    """Do what ``option`` of the printed remedies says, on ``copy``."""
    selectors = copy.selectors()
    if option == _CUT:
        assert base is not None
        if len(case.selectors) > 1:
            assert all(_ONE_AFTER_ANOTHER in remedy for remedy in remedies), remedies
        before = base
        for name in case.selectors:
            copy.write(
                name,
                {*copy.selectors()[before].scope_keys, *case.added},
                f"Successor to {before}. {_NOTE}",
            )
            before = name
    elif option in (_RECORD, _GOES_ON, _DOES_NOT_GO_ON):
        entries = []
        for finding, remedy in zip(findings, remedies, strict=True):
            choose: Callable[[list[str]], list[str]]
            if option == _GOES_ON:
                choose = lambda listed: [name for name in listed if name in case.selectors]  # noqa: E731
            elif isinstance(finding, Fork) and not finding.recorded and option == _RECORD:
                # A new fork: the line goes on through the branch that was there first.
                choose = lambda listed: [name for name in listed if name not in case.selectors]  # noqa: E731
            else:
                choose = lambda listed: []  # noqa: E731
            entries.append(_printed_entry(remedy, _today(copy.baseline()), choose))
        forks = [remedy for remedy in remedies if "\n    forks:\n" in remedy]
        if len(forks) > 1:
            assert all(_SHARE_ONE_ENTRY in remedy for remedy in forks), forks
        copy.record(*entries)
    elif option == _KEEP:
        (finding,) = findings
        assert isinstance(finding, DroppedPair)
        assert f"Keep a version of {pair_label(finding.pair)}" in remedies[0], remedies[0]
        restored = [key for key in selectors[case.base].scope_keys if key[:2] == finding.pair]
        copy.write(
            case.selectors[0],
            {*selectors[case.selectors[0]].scope_keys, *restored},
            f"Successor to {case.base}. {_NOTE}",
        )
    elif option == _NAME:
        assert "Name the selector it succeeds first in its description" in remedies[0], remedies[0]
        copy.write(
            case.selectors[0],
            selectors[case.selectors[0]].scope_keys,
            f"Successor to {case.base}. {_NOTE}",
        )
    elif option == _NAME_EACH:
        assert "Name each selector's real predecessor first" in remedies[0], remedies[0]
        copy.write(
            case.selectors[0],
            selectors[case.selectors[0]].scope_keys,
            f"Successor to {case.base}. {_NOTE}",
        )
    else:
        assert option == _UNDO, option
        for remedy in remedies:
            assert _MARKER not in remedy, f"the remedy records the change again:\n{remedy}"
            assert "undo the change" in remedy, remedy
        copy.write_text(case.selectors[0], case.original)


def _on_an_ended_branch(
    name: str, predecessors: Mapping[str, str | None], baseline: LineageBaseline
) -> bool:
    """Whether the line to ``name`` leaves a recorded fork through a branch it ended."""
    seen: set[str] = set()
    child, parent = name, predecessors.get(name)
    while parent is not None and child not in seen:
        seen.add(child)
        if parent in baseline.forks and child not in baseline.fork_continued_by(parent):
            return True
        child, parent = parent, predecessors.get(parent)
    return False


def _assert_the_advice_is_sound(
    findings: list[Finding], remedies: list[str], report: LineageReport, baseline: LineageBaseline
) -> None:
    """A remedy names every newest selector, none on an ended branch, and the line it took."""
    for finding, remedy in zip(findings, remedies, strict=True):
        if isinstance(finding, Fork | EndedBranch) and "no longer holds" not in remedy:
            for head in finding.heads:
                assert not _on_an_ended_branch(head, report.predecessors, baseline), head
                assert head in remedy, f"the remedy leaves out the newest selector {head}"
        fork = finding.fork if isinstance(finding, EndedBranch) else None
        if isinstance(finding, Fork) and finding.recorded and "no longer holds" not in remedy:
            fork = finding.predecessor
        if fork is not None:
            through = ", ".join(baseline.fork_continued_by(fork))
            assert f"continued through {through}" in remedy, remedy


_REMEDY_CASES: list[tuple[str, Callable[[_MainCopy], _Case], str]] = [
    ("dropped pair", _build_dropped_pair, _KEEP),
    ("dropped pair", _build_dropped_pair, _RECORD),
    ("new fork (#729)", _build_new_fork, _CUT),
    ("new fork (#729)", _build_new_fork, _RECORD),
    ("new successor of a recorded fork", _build_new_successor_of_a_recorded_fork, _CUT),
    ("new successor of a recorded fork", _build_new_successor_of_a_recorded_fork, _GOES_ON),
    ("new successor of a recorded fork", _build_new_successor_of_a_recorded_fork, _DOES_NOT_GO_ON),
    ("two new successors of a recorded fork", _build_two_new_successors_of_a_recorded_fork, _CUT),
    (
        "two new successors of a recorded fork",
        _build_two_new_successors_of_a_recorded_fork,
        _GOES_ON,
    ),
    ("ended branch (#746)", _build_ended_branch, _CUT),
    ("ended branch (#746)", _build_ended_branch, _RECORD),
    (
        "ended branch of a line that went on twice",
        _build_ended_branch_of_a_line_that_went_on_twice,
        _CUT,
    ),
    (
        "ended branch of a line that went on twice",
        _build_ended_branch_of_a_line_that_went_on_twice,
        _RECORD,
    ),
    (
        "ended branch, once #746 records its continuation",
        _build_ended_branch_once_746_records_its_continuation,
        _CUT,
    ),
    (
        "ended branch, once #746 records its continuation",
        _build_ended_branch_once_746_records_its_continuation,
        _RECORD,
    ),
    (
        "new successor, once the recorded fork goes on twice",
        _build_new_successor_once_the_fork_goes_on_twice,
        _CUT,
    ),
    (
        "new successor, once the recorded fork goes on twice",
        _build_new_successor_once_the_fork_goes_on_twice,
        _GOES_ON,
    ),
    (
        "new successor and ended branch at one fork",
        _build_new_successor_and_ended_branch_at_one_fork,
        _CUT,
    ),
    (
        "new successor and ended branch at one fork",
        _build_new_successor_and_ended_branch_at_one_fork,
        _RECORD,
    ),
    ("unnamed predecessor (#819)", _build_unnamed_predecessor, _NAME),
    ("unnamed predecessor (#819)", _build_unnamed_predecessor, _RECORD),
    ("cycle", _build_cycle, _NAME_EACH),
    ("edited first cut", _build_edited_first_cut, _UNDO),
    ("edited selector of a recorded drop", _build_edited_selector_of_a_recorded_drop, _UNDO),
    (
        "edited selector whose successor lacks the pair it gained",
        _build_edited_selector_whose_successor_lacks_the_pair_it_gained,
        _UNDO,
    ),
    (
        "edited successor of a recorded fork that drops a pair",
        _build_edited_fork_successor_that_drops_a_pair,
        _UNDO,
    ),
    ("edited successor of a recorded fork", _build_edited_successor_of_a_recorded_fork, _UNDO),
]


@pytest.mark.parametrize(
    ("build", "option"),
    [(build, option) for _, build, option in _REMEDY_CASES],
    ids=[f"{case}: {option}" for case, _, option in _REMEDY_CASES],
)
def test_every_printed_remedy_can_be_followed(
    tmp_path: Path, build: Callable[[_MainCopy], _Case], option: str
) -> None:
    """Follow each option the remedies print; the guard and the freeze test then pass.

    Where a remedy lists several newest selectors to cut from, each one is
    followed on its own copy.
    """
    copy = _MainCopy(tmp_path / "found")
    case = build(copy)
    selectors, baseline = copy.selectors(), copy.baseline()
    report = check_selector_lineage(selectors, baseline)
    findings = _findings(report)
    assert [type(finding) for finding in findings] == list(case.kinds), report.problems()
    remedies = [_remedy(finding, selectors, baseline) for finding in findings]
    _assert_the_advice_is_sound(findings, remedies, report, baseline)
    bases = (
        sorted({base for remedy in remedies for base in _bases(remedy, case)})
        if option == _CUT
        else [None]
    )
    for index, base in enumerate(bases):
        followed = _MainCopy(tmp_path / f"followed-{index}")
        assert build(followed) == case
        _follow(followed, case, option, findings, remedies, base)
        problems = _guard_problems(followed.selectors(), followed.baseline())
        assert not problems, f"after {option} from {base}:\n" + "\n".join(problems)
        _assert_frozen(followed.baseline())
        if option in (_GOES_ON, _DOES_NOT_GO_ON):
            continued = set(followed.baseline().fork_continued_by(case.base))
            assert (set(case.selectors) <= continued) == (option == _GOES_ON), continued
