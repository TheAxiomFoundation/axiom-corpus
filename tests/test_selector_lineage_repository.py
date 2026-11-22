"""No tracked selector breaks its line without a record (axiom-corpus#935).

The check (``axiom_corpus.corpus.selector_lineage``) reads only the selector
files under ``manifests/releases/`` and ``manifests/selector-lineage-baseline.yaml``:
no corpus fetch and no database. The check reads no git history; the guard's
layer-conflict remedy runs git to list the selectors at the merge bases of HEAD
with ``origin/main`` and ``main``, as of the last fetch
(``_selectors_at_merge_base``). It fails on a cut that selects no version of a
``(jurisdiction, document_class)`` pair its predecessor carries, carries a pair
without its predecessor's base scope for it unchanged, selects a scope its
predecessor selects as primary as a base, names a predecessor another cut
already succeeds, extends a fork's branch the line did not continue, names no
tracked predecessor without a first-cut record, or forms a cycle.
``test (3.14)`` is a required check, so none of these merges unrecorded. A
document that leaves a pair the cut still carries is not checked.

For each finding the guard prints a remedy (``_remedy``): the usual fix, then
the baseline entry that records the finding on purpose.
``test_every_printed_remedy_can_be_followed`` builds each kind of finding on a
copy of main's selectors and baseline, follows each option as printed, and
requires the guard and the freeze test to pass on the result. Main has no
layered selector, so each base case first cuts one into its copy.

A layer conflict has no record. Its remedy addresses only selectors that main
does not have at the merge bases of HEAD with ``origin/main`` and ``main`` (as
of the last fetch), and a pinned one only with an instruction to replace its
pin, or asks to undo a change to a pinned one; when neither merge base resolves
it names no selector. Following it leaves every selector main tracks byte for
byte.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus import selector_lineage, successors
from axiom_corpus.corpus.releases import LAYER_BASE, ReleaseManifest, ReleaseScope, ScopeKey
from axiom_corpus.corpus.selector_lineage import (
    LINEAGE_BASELINE_PATH,
    Cycle,
    DroppedBase,
    DroppedPair,
    EndedBranch,
    Fork,
    LayerChanged,
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
    resolved_predecessors,
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

type Finding = (
    DroppedPair
    | DroppedBase
    | LayerChanged
    | selector_lineage.LayerConflict
    | Fork
    | EndedBranch
    | UnnamedPredecessor
    | Cycle
)


@cache
def _selectors() -> dict[str, ReleaseManifest]:
    return load_tracked_selectors(RELEASES)


@cache
def _baseline() -> LineageBaseline:
    return load_lineage_baseline(REPO_ROOT / LINEAGE_BASELINE_PATH, selectors=_selectors())


@cache
def _main_names() -> frozenset[str]:
    """The selectors main tracks: in the follow harness, main means ``RELEASES``."""
    return frozenset(_selectors())


def _selectors_at_merge_base(repo: Path = REPO_ROOT) -> frozenset[str] | None:
    """The selectors main has, for the layer-conflict remedy, or None when git cannot say.

    They are read at the merge bases of HEAD with ``origin/main`` and with ``main``, as
    of the last fetch; the union keeps a selector that a stale ``origin/main`` lacks but
    ``main`` has. A checkout with neither ref, such as a shallow CI clone, gets None.
    """
    names: set[str] = set()
    read = False
    for ref in ("origin/main", "main"):
        merge_base = successors._git(repo, "merge-base", "HEAD", ref)
        if merge_base.returncode != 0:
            continue
        listing = successors._git(
            repo,
            "ls-tree",
            "-z",
            "--full-tree",
            "--name-only",
            merge_base.stdout.decode("utf-8").strip(),
            "--",
            "manifests/releases/",
        )
        if listing.returncode != 0:
            continue
        read = True
        for path in listing.stdout.decode("utf-8").split("\0"):
            directory, _, file_name = path.rpartition("/")
            if directory == "manifests/releases" and file_name.endswith(".json"):
                names.add(file_name.removesuffix(".json"))
    return frozenset(names) if read else None


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
_CLOSE = "no record allows a layer conflict, and a selector main has keeps its bytes"
_PINNED_LEAD = (
    "The selectors here that main lacks are pinned at their current bytes. Change only the one "
    "this change cut, and replace its selector_digests entry with its new digest: "
)
_NO_MAIN = (
    "This check cannot list main's selectors, because HEAD has no merge base with origin/main "
    "or main. "
)
_CHANGE_ONLY_THE_CUT = "Change only the selector this change cut, never one main has."


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


def _may_follow_from_a_change(finding: Finding, changed: list[str], what: str) -> str:
    """The remedy for ``what`` (a drop) by or from pinned selectors that changed.

    The pin's old digest does not say which scopes the selector had, so the
    finding may or may not come from the change. Either way no entry can pass
    while the pin is stale: undo the change, then see what is left.
    """
    them, that, change = (
        ("it", "that", "change") if len(changed) == 1 else ("them", "those", "changes")
    )
    return (
        f"{finding.describe()}.\n  {' and '.join(changed)} changed since the baseline "
        f"pinned {them}, and this {what} may follow from {that} {change}: undo the {change} "
        "the baseline errors below describe, then run the check again"
    )


def _base_of(release: ReleaseManifest, pair: tuple[str, str]) -> ScopeKey | None:
    """The scope ``release`` selects as the base of ``pair``, if any."""
    return next(
        (scope.key for scope in release.scopes if scope.is_base and scope.pair == pair), None
    )


def _remedy(
    finding: Finding,
    selectors: Mapping[str, ReleaseManifest],
    baseline: LineageBaseline,
    *,
    history: frozenset[str] | None,
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
            return _may_follow_from_a_change(finding, changed, "drop")
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
    if isinstance(finding, DroppedBase):
        if (finding.selector, finding.pair) in baseline.base_replacements:
            return _no_longer_holds(finding)
        changed = _changed_since_pinned(selectors, baseline, finding.predecessor, finding.selector)
        if changed:
            return _may_follow_from_a_change(finding, changed, "dropped base")
        carry = f"{finding.describe()}.\n  Carry {'/'.join(finding.base)} as a base scope unchanged"
        replacing = _base_of(selectors[finding.selector], finding.pair)
        if (
            replacing is None
            or replacing in selectors[finding.predecessor].scope_keys
            or finding.base in selectors[finding.selector].scope_keys
        ):
            # With no other base, a base that is a layer change, or a replaced base the cut
            # keeps as a primary scope, no record can hold.
            return (
                f"{carry}. Only a base version {finding.predecessor} does not select can "
                "replace it, as a reviewed release decision recorded under base_replacements "
                f"in {LINEAGE_BASELINE_PATH}"
            )
        return (
            f"{carry}, or record the reviewed base replacement, with pins in name order and "
            f"replacements in order of selector, then pair, in {LINEAGE_BASELINE_PATH}:"
            f"{_pins(selectors, baseline, finding.predecessor, finding.selector)}\n"
            "    base_replacements:\n"
            f"      - selector: {finding.selector}\n"
            f"        predecessor: {finding.predecessor}\n"
            f"        pair: {pair_label(finding.pair)}\n"
            f'        replaced: "{finding.base_version}"\n'
            f"        replaced_by: {'/'.join(replacing)}\n"
            "        listed_on: <today>\n"
            "        reason: <the decision, and why the new base replaces the old one>"
        )
    if isinstance(finding, LayerChanged):
        return (
            f"{finding.describe()}.\n  Select {'/'.join(finding.scope)} as a primary scope, as "
            f"{finding.predecessor} does: a scope keeps its layer from one cut to the next, so "
            f"a base for {pair_label(finding.scope[:2])} takes a version {finding.predecessor} "
            "does not select"
        )
    if isinstance(finding, selector_lineage.LayerConflict):
        return _layer_conflict_remedy(finding, selectors, baseline, history)
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


def _generic(pair: str, scope: str) -> str:
    """The layer-conflict remedy that names no selector."""
    return (
        f"{_CHANGE_ONLY_THE_CUT} There, select as the base of {pair} a version that no tracked "
        f"selector selects as a primary scope; or, if it selects no other base of {pair}, select "
        f"{scope} as a base scope; or select a new version of that text as the primary scope. If "
        "that selector is pinned, replace its selector_digests entry with its new digest"
    )


def _options(
    finding: selector_lineage.LayerConflict,
    selectors: Mapping[str, ReleaseManifest],
    free: Collection[str],
) -> list[str]:
    """The sides of ``finding`` whose selectors are all in ``free``, each as a remedy step.

    A primary-side selector that already selects a base for the pair can only select a
    new version of the text: a pair holds one base.
    """
    scope = "/".join(finding.scope)
    pair = pair_label(finding.scope[:2])
    options = []
    if all(name in free for name in finding.bases):
        options.append(
            f"in {', '.join(finding.bases)}, select as the base of {pair} a version that no "
            "tracked selector selects as a primary scope"
        )
    if all(name in free for name in finding.primaries):
        steps = [
            f"in {name}, select {scope} as a base scope, or a new version of that text as the "
            "primary scope"
            if _base_of(selectors[name], finding.scope[:2]) is None
            else f"in {name}, select a new version of that text as the primary scope"
            for name in finding.primaries
        ]
        options.append(" and ".join(steps))
    return options


def _layer_conflict_remedy(
    finding: selector_lineage.LayerConflict,
    selectors: Mapping[str, ReleaseManifest],
    baseline: LineageBaseline,
    history: frozenset[str] | None,
) -> str:
    """What to do about a layer conflict: change only a selector main does not have.

    A changed pinned selector comes first: undo the change. Otherwise a selector is
    free when main does not have it (``history``, read at the merge bases of HEAD with
    origin/main and main) and the baseline does not pin it, and the remedy addresses
    only free selectors. When the selectors main lacks are pinned, as a first cut
    pinned with its record is, it addresses those and says to replace the pin. When
    ``history`` is None, or no selector main lacks covers a side, it names no selector.
    """
    involved = sorted({*finding.bases, *finding.primaries})
    scope = "/".join(finding.scope)
    pair = pair_label(finding.scope[:2])
    changed = _changed_since_pinned(selectors, baseline, *involved)
    if changed:
        return _may_follow_from_a_change(finding, changed, "layer conflict")
    if history is None:
        return f"{finding.describe()}.\n  {_NO_MAIN}{_generic(pair, scope)}; {_CLOSE}"
    cut_here = [name for name in involved if name not in history]
    free = {name for name in cut_here if name not in baseline.selector_digests}
    options = _options(finding, selectors, free)
    if options:
        text = "; or ".join(options)
        return f"{finding.describe()}.\n  {text[:1].upper()}{text[1:]}; {_CLOSE}"
    options = _options(finding, selectors, cut_here)
    if options:
        return f"{finding.describe()}.\n  {_PINNED_LEAD}{'; or '.join(options)}; {_CLOSE}"
    return f"{finding.describe()}.\n  {_generic(pair, scope)}; {_CLOSE}"


def _guard_problems(
    selectors: Mapping[str, ReleaseManifest],
    baseline: LineageBaseline,
    *,
    history: frozenset[str] | None,
) -> list[str]:
    """Each finding with its remedy, then each record that no longer holds.

    ``history`` names the selectors main has, for the layer-conflict remedy; None means
    this check cannot list them.
    """
    report = check_selector_lineage(selectors, baseline)
    findings: list[Finding] = [
        *report.dropped,
        *report.dropped_bases,
        *report.layer_changes,
        *report.layer_conflicts,
        *report.forks,
        *report.ended_branches,
        *report.unnamed,
        *report.cycles,
    ]
    problems = [*(_remedy(finding, selectors, baseline, history=history) for finding in findings)]
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
    problems = _guard_problems(_selectors(), _baseline(), history=_selectors_at_merge_base())
    assert not problems, "\n".join(problems)


_REMEDY_TEST_SCOPE: ScopeKey = ("us", "statute", "2026-05-01-remedy-test-base")
_REMEDY_TEST_OTHER: ScopeKey = ("us", "regulation", "2026-05-01-remedy-test-other")
_GENERIC_REMEDY = (
    "Change only the selector this change cut, never one main has. There, select as the base "
    "of us/statute a version that no tracked selector selects as a primary scope; or, if it "
    "selects no other base of us/statute, select us/statute/2026-05-01-remedy-test-base as a "
    "base scope; or select a new version of that text as the primary scope. If that selector "
    "is pinned, replace its selector_digests entry with its new digest; no record allows a "
    "layer conflict, and a selector main has keeps its bytes"
)
_NO_MERGE_BASE_REMEDY = (
    "This check cannot list main's selectors, because HEAD has no merge base with origin/main "
    f"or main. {_GENERIC_REMEDY}"
)


def _shape_a() -> tuple[dict[str, ReleaseManifest], LineageBaseline, tuple[str, str]]:
    """line-x selects the scope as a base and line-y as a primary; both are pinned first cuts."""
    selectors = {
        "line-x": ReleaseManifest("line-x", (ReleaseScope(*_REMEDY_TEST_SCOPE, layer=LAYER_BASE),)),
        "line-y": ReleaseManifest("line-y", (ReleaseScope(*_REMEDY_TEST_SCOPE),)),
    }
    return selectors, _first_cuts_pinned(selectors, "line-x", "line-y"), ("line-x", "line-y")


def _shape_b() -> tuple[dict[str, ReleaseManifest], LineageBaseline, tuple[str, str]]:
    """Finding 8's shape: an unpinned cut adds as a base a scope a pinned first cut selects.

    line-y and line-z are pinned first cuts; line-x, unpinned, succeeds line-z, keeps its
    scope and adds the scope line-y selects as a primary scope as a base.
    """
    selectors = {
        "line-x": ReleaseManifest(
            "line-x",
            (
                ReleaseScope(*_REMEDY_TEST_OTHER),
                ReleaseScope(*_REMEDY_TEST_SCOPE, layer=LAYER_BASE),
            ),
            description="Successor to line-z.",
        ),
        "line-y": ReleaseManifest("line-y", (ReleaseScope(*_REMEDY_TEST_SCOPE),)),
        "line-z": ReleaseManifest("line-z", (ReleaseScope(*_REMEDY_TEST_OTHER),)),
    }
    return selectors, _first_cuts_pinned(selectors, "line-y", "line-z"), ("line-x", "line-y")


def _first_cuts_pinned(selectors: Mapping[str, ReleaseManifest], *names: str) -> LineageBaseline:
    from axiom_corpus.corpus.selector_lineage import RecordedFirstCut

    return LineageBaseline(
        selector_digests={name: selector_sha256(selectors[name]) for name in names},
        first_cuts={name: RecordedFirstCut(name, "2026-11-02", "first cut") for name in names},
    )


@pytest.mark.parametrize(
    ("shape", "history", "expected"),
    [
        pytest.param(
            _shape_a,
            frozenset(),
            "The selectors here that main lacks are pinned at their current bytes. Change only "
            "the one this change cut, and replace its selector_digests entry with its new "
            "digest: in line-x, select as the base of us/statute a version that no tracked "
            "selector selects as a primary scope; or in line-y, select "
            "us/statute/2026-05-01-remedy-test-base as a base scope, or a new version of that "
            "text as the primary scope; no record allows a layer conflict, and a selector main "
            "has keeps its bytes",
            id="main-lacks-both-pinned-cuts",
        ),
        pytest.param(_shape_a, None, _NO_MERGE_BASE_REMEDY, id="no-merge-base"),
        pytest.param(
            _shape_a, frozenset({"line-x", "line-y"}), _GENERIC_REMEDY, id="main-has-both"
        ),
        pytest.param(
            _shape_b,
            frozenset({"line-y", "line-z"}),
            "In line-x, select as the base of us/statute a version that no tracked selector "
            "selects as a primary scope; no record allows a layer conflict, and a selector "
            "main has keeps its bytes",
            id="finding-8-main-has-the-pinned-cuts",
        ),
        pytest.param(_shape_b, None, _NO_MERGE_BASE_REMEDY, id="finding-8-no-merge-base"),
    ],
)
def test_the_guard_prints_a_layer_conflict_with_its_remedy(
    shape: Callable[[], tuple[dict[str, ReleaseManifest], LineageBaseline, tuple[str, str]]],
    history: frozenset[str] | None,
    expected: str,
) -> None:
    """The remedy addresses only selectors main lacks and the baseline does not pin.

    When the selectors main lacks are pinned, it says to change only the one this change
    cut and to replace its pin; when main has them all, or HEAD has no merge base with
    main, it names no selector.
    """
    from axiom_corpus.corpus.selector_lineage import LayerConflict

    selectors, baseline, (base, primary) = shape()
    conflict = LayerConflict(_REMEDY_TEST_SCOPE, (base,), (primary,))
    assert _guard_problems(selectors, baseline, history=history) == [
        f"{conflict.describe()}.\n  {expected}"
    ]


def _git_in(repo: Path, *args: str) -> None:
    """Run a fixture git command in ``repo``, a ``tmp_path`` repository, with no user config."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Remedy Test",
        GIT_AUTHOR_EMAIL="remedy-test@example.invalid",
        GIT_COMMITTER_NAME="Remedy Test",
        GIT_COMMITTER_EMAIL="remedy-test@example.invalid",
    )
    subprocess.run(["git", *args], cwd=repo, env=environment, check=True, capture_output=True)


def _commit_selector(repo: Path, name: str) -> None:
    path = repo / "manifests" / "releases" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "scopes": []}) + "\n", encoding="utf-8")
    _git_in(repo, "add", f"manifests/releases/{name}.json")
    _git_in(repo, "commit", "-q", "-m", f"Cut {name}")


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        pytest.param("resolves", frozenset({"a"}), id="resolves"),
        pytest.param("local-main-only", frozenset({"a"}), id="local-main-only"),
        pytest.param("stale-origin-main", frozenset({"a", "c"}), id="stale-origin-main"),
        pytest.param("origin-main-only", frozenset({"a"}), id="origin-main-only"),
        pytest.param("no-main", None, id="no-main"),
    ],
)
def test_selectors_at_merge_base_reads_main_or_says_it_cannot(
    tmp_path: Path, layout: str, expected: frozenset[str] | None
) -> None:
    """The selectors at the merge bases of HEAD with origin/main and main, or None."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_in(
        repo, "init", "-q", "-b", "trunk" if layout in ("no-main", "origin-main-only") else "main"
    )
    _commit_selector(repo, "a")
    if layout in ("resolves", "stale-origin-main"):
        _git_in(repo, "update-ref", "refs/remotes/origin/main", "main")
    if layout == "origin-main-only":
        _git_in(repo, "update-ref", "refs/remotes/origin/main", "trunk")
    if layout == "stale-origin-main":
        _commit_selector(repo, "c")
    _git_in(repo, "checkout", "-q", "-b", "feature")
    _commit_selector(repo, "b")
    assert _selectors_at_merge_base(repo) == expected


def test_the_w7_union_line_keeps_its_head_and_arizona_stays_a_first_cut() -> None:
    selectors = _selectors()
    baseline = _baseline()
    predecessors = resolved_predecessors(selectors, baseline)
    continued_by = {
        predecessor: baseline.fork_continued_by(predecessor) for predecessor in baseline.forks
    }
    w7 = "us-rulespec-2026-10-13-w7-bundle-gaps-union"
    arizona = "us-az-snap-ece-2026-10-23-manual-union"
    heads = line_heads(predecessors, continued_by, (w7,))
    assert w7 in heads
    assert arizona not in heads
    assert predecessors[arizona] is None
    assert arizona not in baseline.successions
    assert baseline.first_cuts[arizona].listed_on == GUARD_BEGAN


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
        *_baseline().successions.values(),
        *_baseline().base_replacements.values(),
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
    # Pair components follow the loader's (jurisdiction, document_class) order.
    "dropped_pairs": lambda entry: (str(entry["selector"]), *str(entry["pair"]).split("/")),
    "forks": lambda entry: (str(entry["predecessor"]), str(entry["listed_on"])),
    "first_cuts": lambda entry: (str(entry["listed_on"]),),
    "successions": lambda entry: (str(entry["selector"]),),
    "base_replacements": lambda entry: (str(entry["selector"]), *str(entry["pair"]).split("/")),
}

_CUT = "cut from the selector it names"
_RECORD = "record"
_GOES_ON = "record, and the line goes on through it"
_DOES_NOT_GO_ON = "record, and the line does not go on through it"
_KEEP = "keep the pair"
_CARRY = "carry the base unchanged"
_KEEP_PRIMARY = "keep the scope primary"
_NAME = "name the predecessor"
_NAME_EACH = "name each real predecessor"
_UNDO = "undo the change"
_OTHER_BASE = "select another version as the base"
_AS_BASE = "select the scope as a base"
_NEW_PRIMARY = "select a new version as the primary scope"


def _findings(report: LineageReport) -> list[Finding]:
    return [
        *report.dropped,
        *report.dropped_bases,
        *report.layer_changes,
        *report.layer_conflicts,
        *report.forks,
        *report.ended_branches,
        *report.unnamed,
        *report.cycles,
    ]


class _MainCopy:
    """main's tracked selectors and lineage baseline, copied where a case can change them."""

    def __init__(self, root: Path) -> None:
        self.releases = root / "manifests" / "releases"
        self.baseline_path = root / LINEAGE_BASELINE_PATH
        shutil.copytree(RELEASES, self.releases)
        shutil.copyfile(REPO_ROOT / LINEAGE_BASELINE_PATH, self.baseline_path)
        self._selector_cache: dict[str, ReleaseManifest] | None = _selectors().copy()
        self._baseline_cache: LineageBaseline | None = None

    def selectors(self) -> dict[str, ReleaseManifest]:
        if self._selector_cache is None:
            self._selector_cache = load_tracked_selectors(self.releases)
        return self._selector_cache.copy()

    def baseline(self) -> LineageBaseline:
        if self._baseline_cache is None:
            self._baseline_cache = load_lineage_baseline(
                self.baseline_path, selectors=self.selectors()
            )
        return self._baseline_cache

    def text(self, name: str) -> str:
        return (self.releases / f"{name}.json").read_text(encoding="utf-8")

    def write_text(self, name: str, text: str) -> None:
        path = self.releases / f"{name}.json"
        path.write_text(text, encoding="utf-8")
        cached = self._selector_cache
        self._selector_cache = None
        self._baseline_cache = None
        if cached is not None:
            try:
                changed = ReleaseManifest.load(path)
            except (OSError, ValueError):
                return  # The next read uses the full loader's error path.
            if changed.name == name:
                cached[name] = changed
                self._selector_cache = cached

    def write(self, name: str, keys: Iterable[ScopeKey], description: str) -> None:
        self.write_scopes(name, [ReleaseScope(*key) for key in keys], description)

    def write_scopes(self, name: str, scopes: Iterable[ReleaseScope], description: str) -> None:
        """Write a selector of ``scopes`` in each one's canonical encoding, layer included."""
        mappings = [
            scope.to_selector_mapping() for scope in sorted(set(scopes), key=lambda s: s.key)
        ]
        payload = {"name": name, "description": description, "scopes": mappings}
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
        self.baseline_path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )
        self._baseline_cache = None

    def repin(self, name: str) -> None:
        """Replace ``name``'s selector_digests entry with its selector's current digest."""
        data = yaml.safe_load(self.baseline_path.read_text(encoding="utf-8"))
        assert name in data["selector_digests"], f"the baseline does not pin {name}"
        data["selector_digests"][name] = selector_sha256(self.selectors()[name])
        self.baseline_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        self._baseline_cache = None


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
    ``originals`` each edited selector's name and its file before the edit.
    """

    kinds: tuple[type, ...]
    selectors: tuple[str, ...]
    base: str
    added: frozenset[ScopeKey] = frozenset()
    originals: tuple[tuple[str, str], ...] = ()


def _successor_counts(selectors: Mapping[str, ReleaseManifest]) -> dict[str, int]:
    # Copies used by the remedies retain main's prose successions. Counting only
    # named edges would choose a superseded prose base as an open head.
    predecessors = resolved_predecessors(selectors, _baseline())
    counts = dict.fromkeys(selectors, 0)
    for predecessor in predecessors.values():
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
    predecessors = resolved_predecessors(copy.selectors(), baseline)
    return line_heads(predecessors, continued, continued[fork])


def _open_heads(copy: _MainCopy) -> list[str]:
    """The selectors no tracked selector names, on branches their lines did not end."""
    selectors = copy.selectors()
    counts = _successor_counts(selectors)
    ended = _ended_branches(copy.baseline())
    heads = sorted(
        name
        for name, count in counts.items()
        if count == 0 and name not in ended and len(pair_versions(selectors[name])) > 1
    )
    assert heads, "main has no open head with two pairs"
    return heads


def _open_head(copy: _MainCopy) -> str:
    """A selector no tracked selector names, on a branch its line did not end."""
    return _open_heads(copy)[0]


def _pinned_open_head(copy: _MainCopy) -> str:
    """An open head the baseline pins, at a digest it still has."""
    selectors = copy.selectors()
    baseline = copy.baseline()
    counts = _successor_counts(selectors)
    ended = _ended_branches(baseline)
    heads = sorted(
        name
        for name, count in counts.items()
        if count == 0
        and name not in ended
        and len(pair_versions(selectors[name])) > 1
        and baseline.selector_digests.get(name) == selector_sha256(selectors[name])
    )
    assert heads, "main has no pinned open head with two pairs"
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


def _build_dropped_pair_from_a_pinned_head(copy: _MainCopy) -> _Case:
    """A drop from a selector the baseline pins and that has not changed: the usual remedy."""
    base = _pinned_open_head(copy)
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
    return _Case((UnnamedPredecessor,), (name,), name, originals=((name, _edit(copy, name)),))


def _build_edited_selector_of_a_recorded_drop(copy: _MainCopy) -> _Case:
    name = sorted(record.selector for record in copy.baseline().drops.values())[0]
    return _Case((DroppedPair,), (name,), name, originals=((name, _edit(copy, name)),))


def _build_edited_selector_whose_successor_lacks_the_pair_it_gained(copy: _MainCopy) -> _Case:
    """The recorded drop's selector gains a pair its successor lacks: two findings, one edit."""
    name = sorted(record.selector for record in copy.baseline().drops.values())[0]
    original = _edit(copy, name, _ADDED)
    return _Case((DroppedPair, DroppedPair), (name,), name, originals=((name, original),))


def _build_drop_whose_selector_and_predecessor_both_changed(copy: _MainCopy) -> _Case:
    """The recorded drop's predecessor gains a pair, and the drop's selector a version."""
    record = sorted(copy.baseline().drops.values(), key=lambda item: item.selector)[0]
    before = _edit(copy, record.predecessor, _ADDED)
    original = _edit(copy, record.selector)
    return _Case(
        (DroppedPair, DroppedPair),
        (record.selector,),
        record.selector,
        originals=((record.predecessor, before), (record.selector, original)),
    )


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
    return _Case((DroppedPair, Fork), (branch,), fork, originals=((branch, original),))


def _build_edited_successor_of_a_recorded_fork(copy: _MainCopy) -> _Case:
    available = _unextended_ended_branches(copy)
    fork, branch = next(
        (fork, branch)
        for fork, branch in sorted(available, key=lambda item: item[0] != _REVIEW_RECORDED_FORK)
    )
    return _Case((Fork,), (branch,), fork, originals=((branch, _edit(copy, branch)),))


_LAYERED = "remedy-test-layered"
_BASE_VERSION = "2026-05-01-remedy-test-base"
_REPLACING_VERSION = "2026-11-03-remedy-test-base-replacement"


def _write_layered_predecessor(copy: _MainCopy) -> ReleaseScope:
    """Cut a selector with a base under its first pair from an open head; return the base.

    Main has no layered selector. Adding a base to a pair whose predecessor has
    none is not a finding, so the copy stays green.
    """
    head = _open_head(copy)
    selector = copy.selectors()[head]
    pair = sorted(pair_versions(selector))[0]
    base = ReleaseScope(*pair, _BASE_VERSION, layer=LAYER_BASE)
    copy.write_scopes(_LAYERED, [*selector.scopes, base], f"Successor to {head}. {_NOTE}")
    return base


def _layered_successor_case(
    copy: _MainCopy,
    kinds: tuple[type, ...],
    change: Callable[[set[ReleaseScope], ReleaseScope], set[ReleaseScope]],
    name: str,
) -> _Case:
    """Cut ``name`` from the layered predecessor, with ``change`` made to its scopes."""
    base = _write_layered_predecessor(copy)
    scopes = change(set(copy.selectors()[_LAYERED].scopes), base)
    copy.write_scopes(name, scopes, f"Successor to {_LAYERED}. {_NOTE}")
    return _Case(kinds, (name,), _LAYERED)


def _replaced(scopes: set[ReleaseScope], base: ReleaseScope) -> set[ReleaseScope]:
    replacing = ReleaseScope(base.jurisdiction, base.document_class, _REPLACING_VERSION, LAYER_BASE)
    return (scopes - {base}) | {replacing}


def _build_dropped_base(copy: _MainCopy) -> _Case:
    """The successor selects another version as the pair's base: a replacement."""
    return _layered_successor_case(copy, (DroppedBase,), _replaced, "remedy-test-dropped-base")


def _build_left_out_base(copy: _MainCopy) -> _Case:
    return _layered_successor_case(
        copy, (DroppedBase,), lambda scopes, base: scopes - {base}, "remedy-test-left-out-base"
    )


def _build_base_flipped_to_primary(copy: _MainCopy) -> _Case:
    return _layered_successor_case(
        copy,
        (DroppedBase,),
        lambda scopes, base: (scopes - {base}) | {ReleaseScope(*base.key)},
        "remedy-test-base-flipped",
    )


def _build_replaced_base_kept_as_primary(copy: _MainCopy) -> _Case:
    return _layered_successor_case(
        copy,
        (DroppedBase,),
        lambda scopes, base: _replaced(scopes, base) | {ReleaseScope(*base.key)},
        "remedy-test-replaced-base-kept",
    )


def _first_primary(scopes: set[ReleaseScope], pair: tuple[str, str] | None = None) -> ReleaseScope:
    """The first primary scope of ``pair``, or of the first pair other than a base's."""
    based = {scope.pair for scope in scopes if scope.is_base}
    return min(
        (
            scope
            for scope in scopes
            if not scope.is_base and (scope.pair == pair if pair else scope.pair not in based)
        ),
        key=lambda scope: scope.key,
    )


def _into_base(scope: ReleaseScope) -> ReleaseScope:
    return ReleaseScope(*scope.key, layer=LAYER_BASE)


def _build_layer_changed(copy: _MainCopy) -> _Case:
    """A primary scope of a pair with no base becomes that pair's base."""

    def change(scopes: set[ReleaseScope], base: ReleaseScope) -> set[ReleaseScope]:
        moved = _first_primary(scopes)
        return (scopes - {moved}) | {_into_base(moved)}

    return _layered_successor_case(copy, (LayerChanged,), change, "remedy-test-layer-changed")


def _build_primary_moved_into_a_base(copy: _MainCopy) -> _Case:
    """A primary scope of the base's pair takes the base's place: both findings."""

    def change(scopes: set[ReleaseScope], base: ReleaseScope) -> set[ReleaseScope]:
        moved = _first_primary(scopes, base.pair)
        return (scopes - {base, moved}) | {_into_base(moved)}

    return _layered_successor_case(
        copy, (DroppedBase, LayerChanged), change, "remedy-test-primary-into-base"
    )


def _build_edited_selector_of_a_recorded_base_replacement(copy: _MainCopy) -> _Case:
    """A recorded replacement holds until its selector changes."""
    case = _build_dropped_base(copy)
    (name,) = case.selectors
    selectors = copy.selectors()
    base = next(scope for scope in selectors[_LAYERED].scopes if scope.is_base)
    replacing = _base_of(selectors[name], base.pair)
    assert replacing is not None
    _record_on_main(
        copy,
        f"selector_digests:\n  {_LAYERED}: {selector_sha256(selectors[_LAYERED])}\n"
        f"  {name}: {selector_sha256(selectors[name])}\n"
        f"base_replacements:\n  - selector: {name}\n    predecessor: {_LAYERED}\n"
        f'    pair: {pair_label(base.pair)}\n    replaced: "{base.version}"\n'
        f"    replaced_by: {'/'.join(replacing)}\n    listed_on: <today>\n"
        "    reason: A reviewed replacement.\n",
    )
    assert not _guard_problems(copy.selectors(), copy.baseline(), history=_main_names())
    original = copy.text(name)
    edited = ReleaseScope(*base.pair, _EDITED_VERSION)
    copy.write_scopes(name, {*selectors[name].scopes, edited}, selectors[name].description or "")
    return _Case((DroppedBase,), (name,), _LAYERED, originals=((name, original),))


def _build_edited_first_cut_that_gains_a_base(copy: _MainCopy) -> _Case:
    """A pinned first cut gains a base its one successor lacks: the change, not the cut."""
    selectors = copy.selectors()
    baseline = copy.baseline()
    predecessors = resolved_predecessors(selectors, baseline)
    in_other_records = {
        *(
            name
            for record in baseline.drops.values()
            for name in (record.selector, record.predecessor)
        ),
        *(
            name
            for entry in _fork_entries(baseline)
            for name in (entry.predecessor, *entry.successors)
        ),
        *(
            name
            for record in baseline.successions.values()
            for name in (record.selector, record.predecessor)
        ),
    }
    for name in sorted(baseline.first_cuts):
        successors = sorted(child for child, prior in predecessors.items() if prior == name)
        if (
            name in in_other_records
            or baseline.selector_digests.get(name) != selector_sha256(selectors[name])
            or len(successors) != 1
        ):
            continue
        shared = sorted(
            set(pair_versions(selectors[name])) & set(pair_versions(selectors[successors[0]]))
        )
        if shared:
            break
    else:
        raise AssertionError("main has no pinned first cut with one successor sharing a pair")
    original = copy.text(name)
    base = ReleaseScope(*shared[0], _BASE_VERSION, layer=LAYER_BASE)
    copy.write_scopes(name, {*selectors[name].scopes, base}, selectors[name].description or "")
    return _Case((DroppedBase, UnnamedPredecessor), (name,), name, originals=((name, original),))


_CONFLICT_BASE = "remedy-test-layer-conflict-base"
_CONFLICT_PRIMARY = "remedy-test-layer-conflict-primary"
_OTHER_BASE_VERSION = "2026-05-01-remedy-test-other-base"
# The triple finding 8's critic found that only an unpinned selector of main,
# be-rulespec-2026-08-29, selects (as a primary scope).
_UNPINNED_MAIN_PRIMARY: ScopeKey = ("be", "statute", "2026-08-23-be-rulespec-source-promotion")


def _pinned_now(copy: _MainCopy) -> set[str]:
    """The selectors the baseline pins at the digest they have."""
    selectors = copy.selectors()
    return {
        name
        for name, digest in copy.baseline().selector_digests.items()
        if name in selectors and selector_sha256(selectors[name]) == digest
    }


def _scope_a_pinned_selector_selects(
    copy: _MainCopy, head: str, also_not_in: str | None = None
) -> ScopeKey:
    """The first scope a pinned selector other than ``head`` selects and ``head`` does not.

    ``also_not_in`` names another selector that must not select it either.
    """
    selectors = copy.selectors()
    return min(
        key
        for name in sorted(_pinned_now(copy))
        if name != head
        for key in selectors[name].scope_keys
        if key not in selectors[head].scope_keys
        and (also_not_in is None or key not in selectors[also_not_in].scope_keys)
    )


def _write_base_cut(
    copy: _MainCopy, name: str, head: str, scope: ScopeKey, description: str
) -> None:
    """Cut ``name`` with ``head``'s scopes and ``scope`` as a base."""
    scopes = [*copy.selectors()[head].scopes, ReleaseScope(*scope, layer=LAYER_BASE)]
    copy.write_scopes(name, scopes, description)


def _build_new_base_over_a_pinned_primary(copy: _MainCopy) -> _Case:
    """Finding 8: a new cut adds as a base a scope a pinned selector of main selects."""
    head = _open_head(copy)
    scope = _scope_a_pinned_selector_selects(copy, head)
    _write_base_cut(copy, _CONFLICT_BASE, head, scope, f"Successor to {head}. {_NOTE}")
    return _Case((selector_lineage.LayerConflict,), (_CONFLICT_BASE,), head)


def _new_primary_over_a_new_base(copy: _MainCopy, *, with_a_base: bool) -> _Case:
    """A layered cut, then a cut from another head that selects its base as a primary scope.

    With ``with_a_base``, the second cut also selects another base for that pair.
    """
    base = _write_layered_predecessor(copy)
    other = next(head for head in _open_heads(copy) if head != _LAYERED)
    scopes = [*copy.selectors()[other].scopes, ReleaseScope(*base.key)]
    if with_a_base:
        scopes.append(ReleaseScope(*base.pair, _OTHER_BASE_VERSION, layer=LAYER_BASE))
    copy.write_scopes(_CONFLICT_PRIMARY, scopes, f"Successor to {other}. {_NOTE}")
    return _Case((selector_lineage.LayerConflict,), (_LAYERED, _CONFLICT_PRIMARY), other)


def _build_new_primary_over_a_new_base(copy: _MainCopy) -> _Case:
    return _new_primary_over_a_new_base(copy, with_a_base=False)


def _build_new_primary_that_has_a_base_over_a_new_base(copy: _MainCopy) -> _Case:
    return _new_primary_over_a_new_base(copy, with_a_base=True)


def _build_edited_pinned_head_that_gains_a_base(copy: _MainCopy) -> _Case:
    """A pinned open head gains as a base a scope another pinned selector selects."""
    head = _pinned_open_head(copy)
    selectors = copy.selectors()
    predecessor = resolved_predecessors(selectors, copy.baseline())[head]
    scope = _scope_a_pinned_selector_selects(copy, head, also_not_in=predecessor)
    original = copy.text(head)
    edited = {*selectors[head].scopes, ReleaseScope(*scope, layer=LAYER_BASE)}
    copy.write_scopes(head, edited, selectors[head].description or "")
    return _Case((selector_lineage.LayerConflict,), (head,), head, originals=((head, original),))


def _build_edited_pinned_head_that_gains_a_primary(copy: _MainCopy) -> _Case:
    """A pinned open head gains as a primary scope the base a new layered cut selects."""
    base = _write_layered_predecessor(copy)
    head = _pinned_open_head(copy)
    selectors = copy.selectors()
    original = copy.text(head)
    edited = {*selectors[head].scopes, ReleaseScope(*base.key)}
    copy.write_scopes(head, edited, selectors[head].description or "")
    return _Case(
        (selector_lineage.LayerConflict,), (_LAYERED, head), head, originals=((head, original),)
    )


def _build_first_cut_pinned_with_its_record(copy: _MainCopy) -> _Case:
    """Finding 8's cut as the first cut of a line, pinned with its record in the same change."""
    head = _open_head(copy)
    scope = _scope_a_pinned_selector_selects(copy, head)
    _write_base_cut(copy, _CONFLICT_BASE, head, scope, f"A layered first cut. {_NOTE}")
    digest = selector_sha256(copy.selectors()[_CONFLICT_BASE])
    _record_on_main(
        copy,
        f"selector_digests:\n  {_CONFLICT_BASE}: {digest}\n"
        "first_cuts:\n  - listed_on: <today>\n    reason: A layered first cut.\n"
        f"    selectors: [{_CONFLICT_BASE}]\n",
    )
    return _Case((selector_lineage.LayerConflict,), (_CONFLICT_BASE,), _CONFLICT_BASE)


def _build_new_base_over_an_unpinned_selector_main_has(copy: _MainCopy) -> _Case:
    """A new cut adds as a base a scope that only unpinned selectors of main select.

    The scope is _UNPINNED_MAIN_PRIMARY while it still qualifies: selected only as a
    primary scope, only by unpinned selectors in RELEASES, and not by the head. Otherwise
    it is the first scope that qualifies.
    """
    head = _open_head(copy)
    selectors = copy.selectors()
    pinned = set(copy.baseline().selector_digests)
    primary_in: dict[ScopeKey, set[str]] = {}
    as_base: set[ScopeKey] = set()
    for name, release in selectors.items():
        for scope in release.scopes:
            if scope.is_base:
                as_base.add(scope.key)
            else:
                primary_in.setdefault(scope.key, set()).add(name)

    def qualifies(key: ScopeKey) -> bool:
        names = primary_in.get(key, set())
        return (
            bool(names)
            and key not in as_base
            and not names & pinned
            and names <= _main_names()
            and key not in selectors[head].scope_keys
        )

    scope = (
        _UNPINNED_MAIN_PRIMARY
        if qualifies(_UNPINNED_MAIN_PRIMARY)
        else next(key for key in sorted(primary_in) if qualifies(key))
    )
    assert primary_in[scope] <= _main_names() and not primary_in[scope] & pinned, scope
    _write_base_cut(copy, _CONFLICT_BASE, head, scope, f"Successor to {head}. {_NOTE}")
    return _Case((selector_lineage.LayerConflict,), (_CONFLICT_BASE,), head)


def _today(baseline: LineageBaseline) -> str:
    """The day after the newest entry: when a person follows the remedy."""
    listed = [
        *(record.listed_on for record in baseline.drops.values()),
        *(entry.listed_on for entry in _fork_entries(baseline)),
        *(record.listed_on for record in baseline.first_cuts.values()),
        *(record.listed_on for record in baseline.successions.values()),
        *(record.listed_on for record in baseline.base_replacements.values()),
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
    elif option in (_CARRY, _KEEP_PRIMARY):
        for finding, remedy in zip(findings, remedies, strict=True):
            current = copy.selectors()[finding.selector]
            scopes = set(current.scopes)
            if isinstance(finding, DroppedBase):
                base = "/".join(finding.base)
                assert f"Carry {base} as a base scope unchanged" in remedy, remedy
                scopes = {
                    scope
                    for scope in scopes
                    if scope.key != finding.base
                    and not (scope.is_base and scope.pair == finding.pair)
                }
                scopes.add(ReleaseScope(*finding.base, layer=LAYER_BASE))
            else:
                assert isinstance(finding, LayerChanged), finding
                assert f"Select {'/'.join(finding.scope)} as a primary scope" in remedy, remedy
                scopes = {scope for scope in scopes if scope.key != finding.scope}
                scopes.add(ReleaseScope(*finding.scope))
            copy.write_scopes(finding.selector, scopes, current.description or "")
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
    elif option in (_OTHER_BASE, _AS_BASE, _NEW_PRIMARY):
        rewritten: list[str] = []
        for finding, remedy in zip(findings, remedies, strict=True):
            assert isinstance(finding, selector_lineage.LayerConflict), finding
            pair, version = finding.scope[:2], finding.scope[2]
            said = remedy.lower()
            if option == _OTHER_BASE:
                names = finding.bases
                offered = (
                    f"in {', '.join(names)}, select as the base of {pair_label(pair)} a version"
                )
                assert offered in said, remedy
                new = ReleaseScope(*pair, f"{version}-remedy-other", layer=LAYER_BASE)
            else:
                names = finding.primaries
                step = (
                    f"select {'/'.join(finding.scope)} as a base scope"
                    if option == _AS_BASE
                    else "a new version of that text as the primary scope"
                )
                for name in names:
                    assert f"in {name}, select" in said and step in said, remedy
                new = (
                    ReleaseScope(*finding.scope, layer=LAYER_BASE)
                    if option == _AS_BASE
                    else ReleaseScope(*pair, f"{version}-remedy-text")
                )
            for name in names:
                current = copy.selectors()[name]
                kept = {scope for scope in current.scopes if scope.key != finding.scope}
                copy.write_scopes(name, {*kept, new}, current.description or "")
                rewritten.append(name)
        if any(_PINNED_LEAD in remedy for remedy in remedies):
            for name in rewritten:
                copy.repin(name)
    else:
        assert option == _UNDO, option
        for remedy in remedies:
            assert _MARKER not in remedy, f"the remedy records the change again:\n{remedy}"
            assert "undo the change" in remedy, remedy
        for name, text in case.originals:
            copy.write_text(name, text)


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
    findings: list[Finding],
    remedies: list[str],
    report: LineageReport,
    selectors: Mapping[str, ReleaseManifest],
    baseline: LineageBaseline,
    history: frozenset[str] | None,
) -> None:
    """A remedy says what holds for its finding.

    It names every newest selector, none on an ended branch, and the line it took.
    A record a changed selector broke says the baseline already records it; a drop
    by or from a pinned selector that changed says it may follow from the change;
    any other drop gets the usual keep-or-record remedy. A layer conflict with a
    changed pinned selector says to undo the change; any other addresses only
    selectors main (``history``) lacks, and only unpinned ones unless it says to
    replace their pins, or names none at all. The digests are compared here, apart
    from _remedy.
    """
    drop_endpoints = {
        name
        for finding in findings
        if isinstance(finding, DroppedPair | DroppedBase)
        for name in (finding.predecessor, finding.selector)
    }
    stale_anywhere = {
        name
        for name in selectors
        if name in baseline.selector_digests
        and selector_sha256(selectors[name]) != baseline.selector_digests[name]
    }
    stale = stale_anywhere & drop_endpoints
    broken = "already records this, but the record no longer holds"
    for finding, remedy in zip(findings, remedies, strict=True):
        if isinstance(finding, DroppedPair):
            changed = [n for n in (finding.predecessor, finding.selector) if n in stale]
            if (finding.selector, finding.pair) in baseline.drops:
                expected = broken
            elif len(changed) == 1:
                expected = (
                    f"{changed[0]} changed since the baseline pinned it, and this drop may follow "
                    "from that change: undo the change the baseline errors below describe, then "
                    "run the check again"
                )
            elif changed:
                expected = (
                    f"{' and '.join(changed)} changed since the baseline pinned them, and this drop "
                    "may follow from those changes: undo the changes the baseline errors below "
                    "describe, then run the check again"
                )
            else:
                expected = f"Keep a version of {pair_label(finding.pair)}, or record"
            assert expected in remedy, (expected, remedy)
        if isinstance(finding, DroppedBase):
            changed = [n for n in (finding.predecessor, finding.selector) if n in stale]
            if (finding.selector, finding.pair) in baseline.base_replacements:
                expected = broken
            elif changed:
                them, that, change = (
                    ("it", "that", "change") if len(changed) == 1 else ("them", "those", "changes")
                )
                expected = (
                    f"{' and '.join(changed)} changed since the baseline pinned {them}, and this "
                    f"dropped base may follow from {that} {change}: undo the {change} the baseline "
                    "errors below describe, then run the check again"
                )
            else:
                expected = f"Carry {'/'.join(finding.base)} as a base scope unchanged"
            assert expected in remedy, (expected, remedy)
            if _MARKER in remedy:
                # A record holds only for a base the selector selects in the pair, which
                # its predecessor does not select (that would be a layer change).
                replacing = next(
                    scope.key
                    for scope in selectors[finding.selector].scopes
                    if scope.is_base and scope.pair == finding.pair
                )
                assert replacing not in selectors[finding.predecessor].scope_keys, remedy
                assert finding.base not in selectors[finding.selector].scope_keys, remedy
                assert f"replaced_by: {'/'.join(replacing)}\n" in remedy, remedy
                assert f'replaced: "{finding.base_version}"\n' in remedy, remedy
        if isinstance(finding, LayerChanged):
            assert _MARKER not in remedy, remedy
            assert f"Select {'/'.join(finding.scope)} as a primary scope" in remedy, remedy
        if isinstance(finding, selector_lineage.LayerConflict):
            assert _MARKER not in remedy, remedy
            involved = {*finding.bases, *finding.primaries}
            if involved & stale_anywhere:
                assert "undo the change" in remedy, remedy
            else:
                assert "no record allows a layer conflict" in remedy, remedy
                addressed = set(re.findall(r"(?i)\bin ([a-z0-9-]+), select", remedy))
                assert not addressed & (history or frozenset()), (addressed, remedy)
                if _PINNED_LEAD not in remedy:
                    assert not addressed & set(baseline.selector_digests), (addressed, remedy)
                if _CHANGE_ONLY_THE_CUT in remedy:
                    assert not addressed, (addressed, remedy)
                else:
                    assert addressed, remedy
                scope = "/".join(finding.scope)
                for name in finding.primaries:
                    if _base_of(selectors[name], finding.scope[:2]) is not None:
                        # Selecting it as a base would give the pair a second base.
                        said = f"in {name}, select {scope} as a base scope"
                        assert said not in remedy.lower(), remedy
        if isinstance(finding, UnnamedPredecessor) and finding.selector in baseline.first_cuts:
            assert broken in remedy, remedy
        if (
            isinstance(finding, Fork)
            and finding.recorded
            and set(finding.successors) <= set(finding.recorded)
        ):
            assert broken in remedy, remedy
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
    ("dropped pair from a pinned head", _build_dropped_pair_from_a_pinned_head, _KEEP),
    ("dropped pair from a pinned head", _build_dropped_pair_from_a_pinned_head, _RECORD),
    ("dropped base, replaced", _build_dropped_base, _CARRY),
    ("dropped base, replaced", _build_dropped_base, _RECORD),
    ("dropped base, left out", _build_left_out_base, _CARRY),
    ("dropped base, flipped to primary", _build_base_flipped_to_primary, _CARRY),
    ("dropped base, replaced and kept as primary", _build_replaced_base_kept_as_primary, _CARRY),
    ("layer changed", _build_layer_changed, _KEEP_PRIMARY),
    ("primary moved into a base", _build_primary_moved_into_a_base, _CARRY),
    (
        "edited selector of a recorded base replacement",
        _build_edited_selector_of_a_recorded_base_replacement,
        _UNDO,
    ),
    ("edited first cut that gains a base", _build_edited_first_cut_that_gains_a_base, _UNDO),
    (
        "layer conflict: new base over a pinned primary",
        _build_new_base_over_a_pinned_primary,
        _OTHER_BASE,
    ),
    (
        "layer conflict: new primary over a new base",
        _build_new_primary_over_a_new_base,
        _OTHER_BASE,
    ),
    ("layer conflict: new primary over a new base", _build_new_primary_over_a_new_base, _AS_BASE),
    (
        "layer conflict: new primary over a new base",
        _build_new_primary_over_a_new_base,
        _NEW_PRIMARY,
    ),
    (
        "layer conflict: new primary over a new base, primary already has a base",
        _build_new_primary_that_has_a_base_over_a_new_base,
        _NEW_PRIMARY,
    ),
    (
        "layer conflict: edited pinned head gains a base",
        _build_edited_pinned_head_that_gains_a_base,
        _UNDO,
    ),
    (
        "layer conflict: edited pinned head gains a primary",
        _build_edited_pinned_head_that_gains_a_primary,
        _UNDO,
    ),
    (
        "layer conflict: first cut pinned with its record",
        _build_first_cut_pinned_with_its_record,
        _OTHER_BASE,
    ),
    (
        "layer conflict: new base over an unpinned selector main has",
        _build_new_base_over_an_unpinned_selector_main_has,
        _OTHER_BASE,
    ),
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
    (
        "drop whose selector and predecessor both changed",
        _build_drop_whose_selector_and_predecessor_both_changed,
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
    remedies = [
        _remedy(finding, selectors, baseline, history=_main_names()) for finding in findings
    ]
    _assert_the_advice_is_sound(findings, remedies, report, selectors, baseline, _main_names())
    bases = (
        sorted({base for remedy in remedies for base in _bases(remedy, case)})
        if option == _CUT
        else [None]
    )
    for index, base in enumerate(bases):
        followed = _MainCopy(tmp_path / f"followed-{index}")
        assert build(followed) == case
        _follow(followed, case, option, findings, remedies, base)
        problems = _guard_problems(followed.selectors(), followed.baseline(), history=_main_names())
        assert not problems, f"after {option} from {base}:\n" + "\n".join(problems)
        _assert_frozen(followed.baseline())
        if selector_lineage.LayerConflict in case.kinds:
            edited = [
                name
                for name in sorted(_main_names())
                if followed.text(name) != (RELEASES / f"{name}.json").read_text(encoding="utf-8")
            ]
            assert not edited, f"after {option}, selectors main has changed: {edited}"
        if option in (_GOES_ON, _DOES_NOT_GO_ON):
            continued = set(followed.baseline().fork_continued_by(case.base))
            assert (set(case.selectors) <= continued) == (option == _GOES_ON), continued
