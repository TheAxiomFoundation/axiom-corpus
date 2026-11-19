"""The selector lineage check on generated and hand-built selectors (axiom-corpus#935).

Invariants:

- a pair's last version never leaves a line silently: every pair a predecessor
  carries is in its successor, or the check reports the drop, or a pinned
  record allows it;
- along a line of cuts, a pair that leaves is reported at the cut it leaves;
- a base the predecessor selects is carried as the same base scope while its
  pair is carried, or the check reports a dropped base, or a pinned record of
  the replacement allows it; a pair dropped whole is a dropped pair only;
- a scope the predecessor selects as a primary scope never becomes a base
  scope without a report;
- a predecessor named by two or more selectors is a fork, unless a pinned
  record lists exactly those successors;
- a selector that names a fork's successor the line did not continue through is
  reported;
- a selector that names no tracked predecessor is reported unless a pinned
  record says it is the first cut of a line;
- selectors that name each other in a cycle are reported;
- a record holds only for the exact selectors it pins, and a record that no
  longer matches a finding fails;
- a fork's dated entries read as their union: the check reports the same for
  a fork recorded in one entry as for the same fork split across a first entry
  and later ones, and the loader accepts every such split.

The comparison is per pair: a pair the successor still carries is not a drop,
even when one of its documents leaves (``test_a_document_can_leave_a_kept_pair``
pins that limit).

Two differential tests. One holds the check's grouping of scopes into pairs to
the activation gate's (``scripts/check_release_gate.py``), so the pairs the
check protects are the pairs activation repoints. The other holds the heads a
fork or an ended branch names, found by walking down from the branches the
line continued through, to a walk up from every selector.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.models import DocumentClass
from axiom_corpus.corpus.releases import (
    LAYER_BASE,
    LAYER_PRIMARY,
    ReleaseManifest,
    ReleaseScope,
    ScopeKey,
)
from axiom_corpus.corpus.selector_lineage import (
    LINEAGE_BASELINE_SCHEMA,
    Cycle,
    DroppedBase,
    DroppedPair,
    EndedBranch,
    Fork,
    LayerChanged,
    LineageBaseline,
    LineageReport,
    RecordedBaseReplacement,
    RecordedDrop,
    RecordedFirstCut,
    RecordedFork,
    SelectorLineageError,
    UnnamedPredecessor,
    base_changes,
    check_selector_lineage,
    declared_predecessor,
    dropped_pairs,
    line_heads,
    lineage_cycles,
    load_lineage_baseline,
    pair_versions,
)
from axiom_corpus.release.manifest import selector_sha256

_SPEC = importlib.util.spec_from_file_location(
    "check_release_gate_for_lineage",
    Path(__file__).parents[1] / "scripts" / "check_release_gate.py",
)
assert _SPEC and _SPEC.loader
gate = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = gate
_SPEC.loader.exec_module(gate)

_SETTINGS = settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

_JURISDICTIONS = st.sampled_from(["us", "us-mt", "us-ny", "uk", "uk-shropshire"])
_CLASSES = st.sampled_from([document_class.value for document_class in DocumentClass])
_VERSIONS = st.sampled_from(
    ["2026-06-05-nyc-admin-code", "2026-09-28-nyc-admin-code", "2026-10-06-w6", "2026-10-25-a"]
)
_SCOPE_KEYS = st.tuples(_JURISDICTIONS, _CLASSES, _VERSIONS)
_SCOPE_SETS = st.frozensets(_SCOPE_KEYS, min_size=1, max_size=10)
_ONE_SCOPE = [("us", "statute", "2026-10-25-a")]


def _selector(
    name: str, keys: Iterable[ScopeKey], description: str | None = None
) -> ReleaseManifest:
    return ReleaseManifest(
        name=name,
        scopes=tuple(ReleaseScope(*key) for key in sorted(set(keys))),
        description=description,
    )


def _successor(name: str, predecessor: str, keys: Iterable[ScopeKey]) -> ReleaseManifest:
    return _selector(name, keys, f"Successor to {predecessor}. It adds what it adds.")


def _pairs(keys: Iterable[ScopeKey]) -> set[tuple[str, str]]:
    return {key[:2] for key in keys}


def _pin(*releases: ReleaseManifest) -> dict[str, str]:
    return {release.name: selector_sha256(release) for release in releases}


def _first_cuts(*releases: ReleaseManifest) -> dict[str, RecordedFirstCut]:
    return {
        release.name: RecordedFirstCut(release.name, "2026-11-02", "first cut")
        for release in releases
    }


def _baseline(
    *roots: ReleaseManifest,
    pinned: Iterable[ReleaseManifest] = (),
    drops: dict[tuple[str, tuple[str, str]], RecordedDrop] | None = None,
    forks: dict[str, tuple[RecordedFork, ...]] | None = None,
) -> LineageBaseline:
    """A baseline that records ``roots`` as first cuts and pins them and ``pinned``."""
    return LineageBaseline(
        selector_digests=_pin(*roots, *pinned),
        drops=drops or {},
        forks=forks or {},
        first_cuts=_first_cuts(*roots),
    )


def _check(*selectors: ReleaseManifest, baseline: LineageBaseline | None = None) -> LineageReport:
    return check_selector_lineage({s.name: s for s in selectors}, baseline)


# --- the brief's property: a pair's last version never disappears unnamed ---


@_SETTINGS
@given(before=_SCOPE_SETS, after=_SCOPE_SETS)
def test_a_pairs_last_version_never_leaves_without_a_report(
    before: frozenset[ScopeKey], after: frozenset[ScopeKey]
) -> None:
    predecessor = _selector("line-2026-01-01", before)
    successor = _successor("line-2026-02-01", predecessor.name, after)
    report = _check(predecessor, successor, baseline=_baseline(predecessor))

    reported = {finding.pair for finding in report.dropped}
    assert reported == _pairs(before) - _pairs(after)
    for pair in _pairs(before):
        assert pair in _pairs(after) or pair in reported
    assert report.ok == _pairs(before).issubset(_pairs(after))
    for finding in report.dropped:
        assert finding.selector == successor.name
        assert finding.predecessor == predecessor.name
        assert finding.versions == tuple(sorted(k[2] for k in before if k[:2] == finding.pair))


@_SETTINGS
@given(before=_SCOPE_SETS, after=_SCOPE_SETS, data=st.data())
def test_a_pinned_record_allows_exactly_the_drops_it_names(
    before: frozenset[ScopeKey], after: frozenset[ScopeKey], data: st.DataObject
) -> None:
    predecessor = _selector("line-2026-01-01", before)
    successor = _successor("line-2026-02-01", predecessor.name, after)
    lost = sorted(_pairs(before) - _pairs(after))
    recorded = set(data.draw(st.lists(st.sampled_from(lost), unique=True)) if lost else [])
    replaced_by = tuple(sorted(after))[:1]
    baseline = _baseline(
        predecessor,
        pinned=[successor],
        drops={
            (successor.name, pair): RecordedDrop(
                successor.name, predecessor.name, pair, "2026-11-02", "decided", replaced_by
            )
            for pair in recorded
        },
    )
    report = _check(predecessor, successor, baseline=baseline)

    assert {finding.pair for finding in report.recorded_drops} == recorded
    assert {finding.pair for finding in report.dropped} == set(lost) - recorded
    assert report.baseline_errors == ()
    assert report.ok == (recorded == set(lost))


@_SETTINGS
@given(line=st.lists(_SCOPE_SETS, min_size=2, max_size=6))
def test_along_a_line_a_pair_is_reported_at_the_cut_it_leaves(
    line: list[frozenset[ScopeKey]],
) -> None:
    cuts = [_selector("line-cut-0", line[0])]
    for index, keys in enumerate(line[1:], start=1):
        cuts.append(_successor(f"line-cut-{index}", cuts[-1].name, keys))
    report = _check(*cuts, baseline=_baseline(cuts[0]))
    reported = {(finding.selector, finding.pair) for finding in report.dropped}

    for index in range(1, len(cuts)):
        expected = {
            (cuts[index].name, pair) for pair in _pairs(line[index - 1]) - _pairs(line[index])
        }
        assert {key for key in reported if key[0] == cuts[index].name} == expected
    # No pair of any earlier cut is missing from the last one unless some cut
    # in between was reported dropping it.
    for start in range(len(cuts) - 1):
        for pair in _pairs(line[start]) - _pairs(line[-1]):
            assert any((cuts[step].name, pair) in reported for step in range(start + 1, len(cuts)))
    assert report.forks == () and report.unnamed == () and report.cycles == ()


_PARENTS = st.lists(st.one_of(st.none(), st.integers(min_value=0)), min_size=1, max_size=12)


def _tree(
    parents: list[int | None],
) -> tuple[list[ReleaseManifest], list[ReleaseManifest], dict[str, list[str]]]:
    """Selectors that each name an earlier one, or none: the selectors, the roots, who names whom."""
    selectors: list[ReleaseManifest] = []
    roots: list[ReleaseManifest] = []
    named: dict[str, list[str]] = {}
    for index, parent in enumerate(parents):
        name = f"tree-cut-{index}"
        if parent is None or index == 0:
            roots.append(_selector(name, _ONE_SCOPE))
            selectors.append(roots[-1])
            continue
        predecessor = selectors[parent % index].name
        named.setdefault(predecessor, []).append(name)
        selectors.append(_successor(name, predecessor, _ONE_SCOPE))
    return selectors, roots, named


def _forks_of(named: Mapping[str, list[str]]) -> dict[str, tuple[str, ...]]:
    return {
        predecessor: tuple(sorted(successors))
        for predecessor, successors in named.items()
        if len(successors) > 1
    }


def _draw_continued(
    data: st.DataObject, forks: Mapping[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    return {
        predecessor: tuple(sorted(data.draw(st.sets(st.sampled_from(successors), min_size=1))))
        for predecessor, successors in forks.items()
    }


def _whole(
    forks: Mapping[str, tuple[str, ...]], continued: Mapping[str, tuple[str, ...]]
) -> dict[str, tuple[RecordedFork, ...]]:
    return {
        predecessor: (
            RecordedFork(predecessor, successors, continued[predecessor], "2026-11-02", "split"),
        )
        for predecessor, successors in forks.items()
    }


def _heads_walking_up(
    predecessors: Mapping[str, str | None],
    continued: Mapping[str, Collection[str]],
    branches: Collection[str],
) -> tuple[str, ...]:
    """The line's heads found the other way: from every selector, walk up to a branch.

    A selector is on the line if walking up from it reaches a branch, and every
    step up from a recorded fork leaves through a branch the line continued
    through. It is a head if no selector it would step down to is on the line.
    """

    def followed(parent: str, child: str) -> bool:
        return parent not in continued or child in continued[parent]

    def on_line(name: str) -> bool:
        seen: set[str] = set()
        while name not in branches:
            parent = predecessors.get(name)
            if parent is None or name in seen or not followed(parent, name):
                return False
            seen.add(name)
            name = parent
        return True

    children: dict[str, list[str]] = defaultdict(list)
    for name, parent in predecessors.items():
        if parent is not None:
            children[parent].append(name)
    return tuple(
        sorted(
            name
            for name in predecessors
            if on_line(name) and not any(followed(name, child) for child in children[name])
        )
    )


@_SETTINGS
@given(parents=_PARENTS, data=st.data())
def test_forks_and_ended_branches_follow_the_named_predecessors(
    parents: list[int | None], data: st.DataObject
) -> None:
    selectors, roots, named = _tree(parents)
    expected = _forks_of(named)
    unrecorded = _check(*selectors, baseline=_baseline(*roots))
    assert {fork.predecessor: fork.successors for fork in unrecorded.forks} == expected
    assert unrecorded.dropped == () and unrecorded.ended_branches == ()
    for fork in unrecorded.forks:
        assert fork.recorded == ()
        assert fork.heads == _heads_walking_up(unrecorded.predecessors, {}, fork.successors)

    continued = _draw_continued(data, expected)
    recorded = _check(
        *selectors,
        baseline=_baseline(*roots, pinned=selectors, forks=_whole(expected, continued)),
    )
    ended = {
        (extension, branch)
        for predecessor, successors in expected.items()
        for branch in set(successors) - set(continued[predecessor])
        for extension in named.get(branch, [])
    }
    assert recorded.forks == ()
    assert {fork.predecessor for fork in recorded.recorded_forks} == set(expected)
    assert {(b.selector, b.predecessor) for b in recorded.ended_branches} == ended
    assert recorded.ok == (not ended)
    for branch in recorded.ended_branches:
        assert branch.continued_by == continued[branch.fork]
        assert branch.heads == _heads_walking_up(
            recorded.predecessors, continued, continued[branch.fork]
        )


def _split(
    data: st.DataObject, predecessor: str, successors: tuple[str, ...], continued: tuple[str, ...]
) -> tuple[RecordedFork, ...]:
    """One fork's record split into a first entry and later dated ones, as the loader allows.

    The first entry lists at least two successors and one continued branch. Each
    later entry adds at least one successor or continued branch, and continues
    only a successor that it or an earlier entry lists.
    """
    first_branch = data.draw(st.sampled_from(continued))
    others = [name for name in successors if name != first_branch]
    first = {first_branch, data.draw(st.sampled_from(others))}
    first |= data.draw(st.sets(st.sampled_from(others)))
    kept = sorted(set(continued) & first)
    first_continued = {first_branch} | data.draw(st.sets(st.sampled_from(kept)))
    later_successors = [name for name in successors if name not in first]
    later_continued = [name for name in continued if name not in first_continued]
    count = data.draw(
        st.integers(min_value=1 if later_successors or later_continued else 0, max_value=3)
    )
    successor_at = {
        name: data.draw(st.integers(min_value=1, max_value=count)) for name in later_successors
    }
    continued_at = {
        name: data.draw(st.integers(min_value=successor_at.get(name, 1), max_value=count))
        for name in later_continued
    }
    entries = [
        RecordedFork(
            predecessor, tuple(sorted(first)), tuple(sorted(first_continued)), "2026-11-02", "split"
        )
    ]
    for index in range(1, count + 1):
        added = tuple(sorted(name for name, at in successor_at.items() if at == index))
        added_continued = tuple(sorted(name for name, at in continued_at.items() if at == index))
        if added or added_continued:
            listed_on = f"2026-11-{2 + index:02d}"
            entries.append(
                RecordedFork(predecessor, added, added_continued, listed_on, "a later decision")
            )
    return tuple(entries)


def _baseline_yaml(forks: Mapping[str, tuple[RecordedFork, ...]]) -> str:
    entries = []
    for predecessor in sorted(forks):
        for entry in forks[predecessor]:
            item: dict[str, object] = {"predecessor": predecessor}
            if entry.successors:
                item["successors"] = list(entry.successors)
            if entry.continued_by:
                item["continued_by"] = list(entry.continued_by)
            item["listed_on"] = entry.listed_on
            item["reason"] = entry.reason
            entries.append(item)
    names = {
        name
        for entries_of in forks.values()
        for entry in entries_of
        for name in (entry.predecessor, *entry.successors)
    }
    data = {
        "schema_version": LINEAGE_BASELINE_SCHEMA,
        "selector_digests": dict.fromkeys(sorted(names), "0" * 64),
        "forks": entries,
    }
    return yaml.safe_dump(data, sort_keys=False)


@_SETTINGS
@given(parents=_PARENTS, data=st.data())
def test_a_forks_dated_entries_read_as_their_union(
    parents: list[int | None], data: st.DataObject
) -> None:
    """Differential: one entry per fork, or the same forks split across dated entries."""
    selectors, roots, named = _tree(parents)
    expected = _forks_of(named)
    continued = _draw_continued(data, expected)
    whole = _whole(expected, continued)
    split = {
        predecessor: _split(data, predecessor, successors, continued[predecessor])
        for predecessor, successors in expected.items()
    }
    assert _check(*selectors, baseline=_baseline(*roots, pinned=selectors, forks=split)) == _check(
        *selectors, baseline=_baseline(*roots, pinned=selectors, forks=whole)
    )

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "selector-lineage-baseline.yaml"
        path.write_text(_baseline_yaml(split), encoding="utf-8")
        loaded = load_lineage_baseline(path)
    assert loaded.forks == split
    for predecessor, successors in expected.items():
        assert loaded.fork_successors(predecessor) == successors
        assert loaded.fork_continued_by(predecessor) == continued[predecessor]


@_SETTINGS
@given(named=st.lists(st.booleans(), min_size=1, max_size=8), data=st.data())
def test_a_selector_naming_no_predecessor_needs_a_first_cut_record(
    named: list[bool], data: st.DataObject
) -> None:
    head = _selector("head-cut", _ONE_SCOPE)
    others = [
        _successor(f"cut-{index}", "head-cut", _ONE_SCOPE)
        if names_head
        else _selector(f"cut-{index}", _ONE_SCOPE, "A cut that names nothing tracked.")
        for index, names_head in enumerate(named)
    ]
    roots = [
        head,
        *(other for other, names_head in zip(others, named, strict=True) if not names_head),
    ]
    recorded = data.draw(st.sets(st.sampled_from([root.name for root in roots])))
    baseline = LineageBaseline(
        selector_digests=_pin(*roots),
        first_cuts=_first_cuts(*(root for root in roots if root.name in recorded)),
    )
    report = _check(head, *others, baseline=baseline)
    assert {finding.selector for finding in report.unnamed} == {
        root.name for root in roots
    } - recorded
    assert set(report.recorded_first_cuts) == recorded


@_SETTINGS
@given(keys=st.lists(_SCOPE_KEYS, min_size=1, max_size=12, unique=True))
def test_pairs_group_as_the_activation_gate_groups_them(keys: list[ScopeKey]) -> None:
    """Differential: the check's pairs are the pairs activation repoints."""
    release = _selector("diff-2026-01-01", keys)
    scopes = [
        {"jurisdiction": j, "document_class": c, "version": v} for j, c, v in release.scope_keys
    ]
    activation = gate._pair_versions(gate._scope_triples(scopes))
    assert {pair: frozenset(versions) for pair, versions in activation.items()} == pair_versions(
        release
    )


@_SETTINGS
@given(before=_SCOPE_SETS, after=_SCOPE_SETS)
def test_dropped_pairs_is_the_set_difference_of_pairs(
    before: frozenset[ScopeKey], after: frozenset[ScopeKey]
) -> None:
    predecessor = _selector("line-2026-01-01", before)
    successor = _selector("line-2026-02-01", after)
    lost = dropped_pairs(predecessor, successor)
    assert set(lost) == _pairs(before) - _pairs(after)
    for pair, versions in lost.items():
        assert versions == {key[2] for key in before if key[:2] == pair}


@_SETTINGS
@given(targets=st.lists(st.integers(min_value=0, max_value=7), min_size=1, max_size=8))
def test_cycles_are_found_once_each(targets: list[int]) -> None:
    """Each selector names at most one predecessor, so a walk finds every cycle."""
    names = [f"cyc-{index}" for index in range(len(targets))]
    predecessors = {
        name: (names[target] if target < len(names) and target != index else None)
        for index, (name, target) in enumerate(zip(names, targets, strict=True))
    }
    expected = set()
    for start in names:
        seen: list[str] = []
        node: str | None = start
        while node is not None and node not in seen:
            seen.append(node)
            node = predecessors[node]
        if node is not None:
            expected.add(tuple(sorted(seen[seen.index(node) :])))
    assert set(lineage_cycles(predecessors)) == expected
    assert len(lineage_cycles(predecessors)) == len(expected)


# --- the predecessor a description names ---


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Successor to line-a, the pin.", "line-a"),
        ("Fourth release after line-b: the plans.", "line-b"),
        ("UK RuleSpec corpus release: line-a's scope set plus six manuals.", "line-a"),
        ("Everything in (line-b) plus line-a.", "line-b"),
        ("Successor to line-a-r2, which is not tracked, then line-b.", "line-b"),
        ("Re-cut of self-cut that keeps line-a.", "line-a"),
        ("Successor to line-a--it keeps every scope.", "line-a"),
        ("Successor to LINE-A, written in capitals.", None),
        ("No other selector is named here.", None),
        (None, None),
    ],
)
def test_the_predecessor_is_the_first_tracked_selector_named(
    description: str | None, expected: str | None
) -> None:
    release = _selector("self-cut", _ONE_SCOPE, description)
    assert declared_predecessor(release, {"line-a", "line-b", "self-cut"}) == expected


# --- the issue's cuts, rebuilt by hand ---

_PIN = [
    ("us", "manual", "2026-09-10-ssi-poms-si"),
    ("us", "statute", "2026-10-06-w6-federal-public-laws"),
    ("us-mt", "statute", "2026-07-13-recovery"),
    ("us-ny", "statute", "2026-06-05-nyc-admin-code"),
]
_NYC = [key for key in _PIN if key[2] != "2026-06-05-nyc-admin-code"] + [
    ("us-ny", "statute", "2026-09-28-nyc-admin-code"),
    ("us", "statute", "2026-09-29-election-statute-uocava-nvra-title-52"),
]
_MT = _NYC + [
    ("us-mt", "form", "2026-10-06-w6-income-tax-forms-mt"),
    ("us-mt", "statute", "2026-10-25-mt-separate-filing-dated-authority"),
]


def test_leaving_a_pair_is_a_drop() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    mt = _successor("pin-mt", "pin-nyc", _MT)
    stale = _successor("pin-stale", "pin-mt", _NYC)
    report = _check(ssi, nyc, mt, stale, baseline=_baseline(ssi))
    assert report.dropped == (
        DroppedPair(
            "pin-stale", "pin-mt", ("us-mt", "form"), ("2026-10-06-w6-income-tax-forms-mt",)
        ),
    )
    assert "pin-stale selects no us-mt/form scope" in report.problems()[0]
    assert report.forks == ()


def test_a_document_can_leave_a_kept_pair() -> None:
    """The limit of a per-pair check: a kept pair hides a document that leaves it.

    pin-stale keeps us-mt/statute through its 2026-07-13 recovery scope, so
    losing the separate-filing text is not a finding. Swapping one NYC
    Administrative Code version for another is not one either.
    """
    mt = _selector("pin-mt", _MT)
    stale = _successor("pin-stale", "pin-mt", [*_NYC, ("us-mt", "form", "2026-10-06-w6-forms")])
    report = _check(mt, stale, baseline=_baseline(mt))
    assert ("us-mt", "statute", "2026-10-25-mt-separate-filing-dated-authority") not in set(
        stale.scope_keys
    )
    assert report.ok

    nyc = _selector("pin-nyc", _NYC)
    swapped = [key for key in _NYC if key[0] != "us-ny"] + [("us-ny", "statute", "2027-01-01")]
    assert _check(nyc, _successor("pin-next", "pin-nyc", swapped), baseline=_baseline(nyc)).ok


def test_a_cut_from_a_superseded_base_is_a_fork() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", [*_PIN, ("us-ks", "policy", "2026-10-02-plan")])
    report = _check(ssi, nyc, ks, baseline=_baseline(ssi))
    assert report.forks == (Fork("pin-ssi", ("pin-ks", "pin-nyc"), heads=("pin-ks", "pin-nyc")),)
    assert report.dropped == ()
    assert "2 selectors name pin-ssi as their predecessor" in report.problems()[0]


def test_extending_a_branch_the_line_did_not_continue_is_refused() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    follow = _successor("pin-ks-followup", "pin-ks", _PIN)
    head = _successor("pin-mt", "pin-nyc", _MT)
    fork = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split")
    baseline = _baseline(ssi, pinned=[nyc, ks], forks={"pin-ssi": (fork,)})
    assert _check(ssi, nyc, ks, head, baseline=baseline).ok

    report = _check(ssi, nyc, ks, head, follow, baseline=baseline)
    assert report.ended_branches == (
        EndedBranch("pin-ks-followup", "pin-ks", "pin-ssi", ("pin-nyc",), ("pin-mt",)),
    )
    assert report.problems() == [
        "pin-ks-followup names pin-ks, a branch of the fork at pin-ssi that the line did "
        "not continue: it continued through pin-nyc"
    ]


def test_a_selector_that_names_nothing_tracked_is_compared_with_nothing() -> None:
    ssi = _selector("pin-ssi", _PIN)
    unnamed = _selector("pin-ks-r2", _PIN, "Kansas LIHEAP pin for rulespec-us; do not activate.")
    report = _check(ssi, unnamed, baseline=_baseline(ssi))
    assert report.unnamed == (UnnamedPredecessor("pin-ks-r2"),)
    assert report.recorded_first_cuts == ("pin-ssi",)
    assert not report.ok


def test_a_first_cut_record_for_a_selector_that_names_a_predecessor_is_stale() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    report = _check(ssi, nyc, baseline=_baseline(ssi, nyc))
    assert report.baseline_errors == (
        "the baseline records pin-nyc as the first cut of a line, but its description "
        "names pin-ssi",
    )


def test_selectors_naming_each_other_are_a_cycle() -> None:
    a = _selector("cyc-a", _PIN, "Successor to cyc-b.")
    b = _selector("cyc-b", _PIN, "Successor to cyc-a.")
    report = _check(a, b)
    assert report.cycles == (Cycle(("cyc-a", "cyc-b")),)
    assert report.unnamed == () and report.dropped == ()
    assert "cyc-a, cyc-b name each other as predecessors" in report.problems()[0]


# --- records hold only for the exact selectors they pin ---


def _drop_case() -> tuple[ReleaseManifest, ReleaseManifest]:
    return _selector("pin-mt", _MT), _successor("pin-stale", "pin-mt", _NYC)


def _record(**changes: object) -> RecordedDrop:
    values: dict[str, object] = {
        "selector": "pin-stale",
        "predecessor": "pin-mt",
        "pair": ("us-mt", "form"),
        "listed_on": "2026-11-02",
        "reason": "Retired on purpose.",
        "replaced_by": (),
    }
    values.update(changes)
    return RecordedDrop(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("edited", ["pin-stale", "pin-mt"])
def test_a_record_for_an_edited_selector_no_longer_holds(edited: str) -> None:
    """A drop record pins both the selector and the predecessor it was written for."""
    mt, stale = _drop_case()
    baseline = _baseline(mt, pinned=[stale], drops={("pin-stale", ("us-mt", "form")): _record()})
    digests = dict(baseline.selector_digests)
    digests[edited] = "0" * 64
    edited_baseline = LineageBaseline(digests, baseline.drops, first_cuts=baseline.first_cuts)
    report = _check(mt, stale, baseline=edited_baseline)
    assert [finding.pair for finding in report.dropped] == [("us-mt", "form")]
    assert report.recorded_drops == ()
    assert any(f"pins {edited} at" in error for error in report.baseline_errors)


def test_a_record_must_name_replacements_the_selector_selects() -> None:
    mt, stale = _drop_case()
    replaced = _record(replaced_by=(("us-mt", "guidance", "2026-10-06-w6"),))
    drops = {("pin-stale", ("us-mt", "form")): replaced}
    report = _check(mt, stale, baseline=_baseline(mt, pinned=[stale], drops=drops))
    assert [finding.pair for finding in report.dropped] == [("us-mt", "form")]
    assert report.baseline_errors == (
        "the baseline names us-mt/guidance/2026-10-06-w6 as replacing us-mt/form in "
        "pin-stale, which does not select it",
    )

    carried = _successor("pin-stale", "pin-mt", [*_NYC, ("us-mt", "guidance", "2026-10-06-w6")])
    report = _check(mt, carried, baseline=_baseline(mt, pinned=[carried], drops=drops))
    assert report.ok and [f.pair for f in report.recorded_drops] == [("us-mt", "form")]


def test_a_record_that_matches_no_drop_is_stale() -> None:
    mt = _selector("pin-mt", _MT)
    keeps = _successor("pin-stale", "pin-mt", _MT)
    drops = {("pin-stale", ("us-mt", "form")): _record()}
    report = _check(mt, keeps, baseline=_baseline(mt, pinned=[keeps], drops=drops))
    assert report.baseline_errors == (
        "the baseline records pin-stale dropping us-mt/form from pin-mt, but it does not "
        "drop that pair",
    )


def test_a_record_holds_only_for_the_predecessor_the_description_names() -> None:
    """The digest leaves out the description, so the record pins the predecessor too."""
    mt, _ = _drop_case()
    other = _selector("pin-other", _MT)
    lacking = _selector("pin-lacking", _NYC)
    drops = {("pin-stale", ("us-mt", "form")): _record()}
    for prior in (other, lacking):
        moved = _successor("pin-stale", prior.name, _NYC)
        report = _check(
            mt, prior, moved, baseline=_baseline(mt, prior, pinned=[moved], drops=drops)
        )
        expected = (
            [
                DroppedPair(
                    "pin-stale",
                    "pin-other",
                    ("us-mt", "form"),
                    ("2026-10-06-w6-income-tax-forms-mt",),
                )
            ]
            if prior is other
            else []
        )
        assert list(report.dropped) == expected
        assert report.baseline_errors == (
            "the baseline records pin-stale dropping us-mt/form from pin-mt, but pin-stale "
            f"names {prior.name} as its predecessor",
        )


def test_a_record_for_an_untracked_selector_fails() -> None:
    mt, stale = _drop_case()
    baseline = _baseline(mt, pinned=[stale], drops={("pin-stale", ("us-mt", "form")): _record()})
    report = _check(mt, baseline=baseline)
    assert report.baseline_errors == (
        "the baseline pins pin-stale, which is not a tracked selector",
    )


def test_a_fork_record_holds_only_for_the_successors_it_lists() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    late = _successor("pin-late", "pin-ssi", _PIN)
    record = RecordedFork(
        "pin-ssi", ("pin-ks", "pin-nyc"), ("pin-ks", "pin-nyc"), "2026-11-02", "the line splits"
    )
    assert _check(
        ssi, nyc, ks, baseline=_baseline(ssi, pinned=[nyc, ks], forks={"pin-ssi": (record,)})
    ).ok

    report = _check(
        ssi,
        nyc,
        ks,
        late,
        baseline=_baseline(ssi, pinned=[nyc, ks, late], forks={"pin-ssi": (record,)}),
    )
    assert report.forks == (
        Fork(
            "pin-ssi",
            ("pin-ks", "pin-late", "pin-nyc"),
            recorded=("pin-ks", "pin-nyc"),
            heads=("pin-ks", "pin-nyc"),
        ),
    )
    assert report.baseline_errors == (
        "the baseline records pin-ks, pin-nyc as the successors of pin-ssi, but "
        "pin-ks, pin-late, pin-nyc name it",
    )


def _with_digest(baseline: LineageBaseline, name: str, digest: str) -> LineageBaseline:
    digests = dict(baseline.selector_digests)
    digests[name] = digest
    return LineageBaseline(digests, baseline.drops, baseline.forks, baseline.first_cuts)


def test_a_fork_record_for_an_edited_successor_no_longer_holds() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    record = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split")
    baseline = _with_digest(
        _baseline(ssi, pinned=[nyc, ks], forks={"pin-ssi": (record,)}), "pin-ks", "0" * 64
    )
    report = _check(ssi, nyc, ks, baseline=baseline)
    assert report.forks == (
        Fork("pin-ssi", ("pin-ks", "pin-nyc"), recorded=("pin-ks", "pin-nyc"), heads=("pin-nyc",)),
    )
    assert report.recorded_forks == ()
    assert any("pin-ks at " + "0" * 64 in error for error in report.baseline_errors)


def test_a_fork_record_whose_predecessor_has_one_successor_is_stale() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _selector("pin-ks", _PIN)
    record = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split")
    report = _check(
        ssi, nyc, ks, baseline=_baseline(ssi, ks, pinned=[nyc], forks={"pin-ssi": (record,)})
    )
    assert report.forks == ()
    assert report.baseline_errors == (
        "the baseline records a fork at pin-ssi (pin-ks, pin-nyc), but 1 tracked "
        "selector(s) name it as their predecessor",
    )


@pytest.mark.parametrize("stale", ["digest", "successors"])
def test_an_ended_branch_is_reported_even_when_its_fork_record_no_longer_holds(
    stale: str,
) -> None:
    """A stale fork record still says which branches ended, so the check fails closed."""
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    late = _successor("pin-late", "pin-ssi", _PIN)
    follow = _successor("pin-ks-followup", "pin-ks", _PIN)
    record = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split")
    selectors = [ssi, nyc, ks, follow]
    baseline = _baseline(ssi, pinned=[nyc, ks, late], forks={"pin-ssi": (record,)})
    if stale == "digest":
        baseline = _with_digest(baseline, "pin-nyc", "0" * 64)
    else:
        selectors.append(late)
    report = _check(*selectors, baseline=baseline)
    assert report.recorded_forks == ()
    assert report.ended_branches == (
        EndedBranch("pin-ks-followup", "pin-ks", "pin-ssi", ("pin-nyc",), ("pin-nyc",)),
    )


def _recorded_ssi_fork() -> tuple[list[ReleaseManifest], RecordedFork]:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    head = _successor("pin-mt", "pin-nyc", _MT)
    record = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split")
    return [ssi, nyc, ks, head], record


def test_a_later_entry_records_a_new_successor_of_a_recorded_fork() -> None:
    """Records are append-only: a third successor gets its own dated entry."""
    selectors, record = _recorded_ssi_fork()
    late = _successor("pin-late", "pin-ssi", _PIN)
    pinned = [*selectors[1:], late]
    report = _check(
        *selectors,
        late,
        baseline=_baseline(selectors[0], pinned=pinned, forks={"pin-ssi": (record,)}),
    )
    assert report.forks == (
        Fork("pin-ssi", ("pin-ks", "pin-late", "pin-nyc"), ("pin-ks", "pin-nyc"), ("pin-mt",)),
    )

    added = RecordedFork("pin-ssi", ("pin-late",), (), "2026-11-03", "a third branch, on purpose")
    entries = {"pin-ssi": (record, added)}
    report = _check(
        *selectors, late, baseline=_baseline(selectors[0], pinned=pinned, forks=entries)
    )
    assert report.ok
    assert report.recorded_forks == (
        Fork("pin-ssi", ("pin-ks", "pin-late", "pin-nyc"), ("pin-ks", "pin-late", "pin-nyc")),
    )

    # The line did not go on through pin-late, so extending it is an ended branch.
    follow = _successor("pin-late-followup", "pin-late", _PIN)
    report = _check(
        *selectors, late, follow, baseline=_baseline(selectors[0], pinned=pinned, forks=entries)
    )
    assert report.ended_branches == (
        EndedBranch("pin-late-followup", "pin-late", "pin-ssi", ("pin-nyc",), ("pin-mt",)),
    )


def test_a_later_entry_continues_a_branch_the_line_ended() -> None:
    selectors, record = _recorded_ssi_fork()
    follow = _successor("pin-ks-followup", "pin-ks", _PIN)
    pinned = selectors[1:]
    report = _check(
        *selectors,
        follow,
        baseline=_baseline(selectors[0], pinned=pinned, forks={"pin-ssi": (record,)}),
    )
    assert [branch.selector for branch in report.ended_branches] == ["pin-ks-followup"]

    goes_on = RecordedFork(
        "pin-ssi", (), ("pin-ks",), "2026-11-03", "the line goes on through pin-ks"
    )
    entries = {"pin-ssi": (record, goes_on)}
    report = _check(
        *selectors, follow, baseline=_baseline(selectors[0], pinned=pinned, forks=entries)
    )
    assert report.ok
    assert report.ended_branches == ()


def test_heads_follow_only_the_branches_a_recorded_fork_continued_through() -> None:
    predecessors: dict[str, str | None] = {
        "root": None,
        "kept": "root",
        "ended": "root",
        "kept-next": "kept",
        "ended-next": "ended",
        "side": "kept",
    }
    continued = {"root": ("kept",), "kept": ("kept-next",)}
    assert line_heads(predecessors, continued, ["kept"]) == ("kept-next",)
    assert line_heads(predecessors, {}, ["kept"]) == ("kept-next", "side")
    assert line_heads(predecessors, continued, ["kept", "ended"]) == ("ended-next", "kept-next")
    assert line_heads(predecessors, continued, ["untracked"]) == ()
    # Starting above a recorded fork, the walk still follows only its continued branch.
    assert line_heads(predecessors, continued, ["root"]) == ("kept-next",)
    # A recorded fork none of whose continued branches is tracked is a head itself.
    assert line_heads(predecessors, {"root": ("gone",)}, ["root"]) == ("root",)
    # A cycle names no head, and the walk ends.
    assert line_heads({"a": "b", "b": "a"}, {}, ["a"]) == ()


def test_a_fork_record_for_an_edited_predecessor_no_longer_holds() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    record = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split")
    baseline = _with_digest(
        _baseline(ssi, pinned=[nyc, ks], forks={"pin-ssi": (record,)}), "pin-ssi", "0" * 64
    )
    report = _check(ssi, nyc, ks, baseline=baseline)
    assert report.forks == (
        Fork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-ks", "pin-nyc"), ("pin-nyc",)),
    )
    assert report.recorded_forks == ()


def test_a_stale_fork_record_names_every_successor_its_entries_record() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _selector("pin-ks", _PIN)
    late = _selector("pin-late", _PIN)
    entries = (
        RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split"),
        RecordedFork("pin-ssi", ("pin-late",), (), "2026-11-03", "a third branch"),
    )
    baseline = _baseline(ssi, ks, late, pinned=[nyc], forks={"pin-ssi": entries})
    assert _check(ssi, nyc, ks, late, baseline=baseline).baseline_errors == (
        "the baseline records a fork at pin-ssi (pin-ks, pin-late, pin-nyc), but 1 tracked "
        "selector(s) name it as their predecessor",
    )


def test_heads_skip_a_branch_a_recorded_fork_further_down_ended() -> None:
    """A fork or ended branch names no head on a branch a recorded fork below it ended."""
    p = _selector("nest-p", _ONE_SCOPE)
    a = _successor("nest-a", "nest-p", _ONE_SCOPE)
    b = _successor("nest-b", "nest-p", _ONE_SCOPE)
    a1 = _successor("nest-a1", "nest-a", _ONE_SCOPE)
    a2 = _successor("nest-a2", "nest-a", _ONE_SCOPE)
    a1x = _successor("nest-a1x", "nest-a1", _ONE_SCOPE)
    tree = [p, a, b, a1, a2, a1x]
    below = RecordedFork("nest-a", ("nest-a1", "nest-a2"), ("nest-a1",), "2026-11-02", "split")
    top = RecordedFork("nest-p", ("nest-a", "nest-b"), ("nest-a",), "2026-11-02", "split")
    both = {"nest-a": (below,), "nest-p": (top,)}
    assert _check(*tree, baseline=_baseline(p, pinned=[a, b, a1, a2], forks=both)).ok

    new = _successor("nest-n", "nest-p", _ONE_SCOPE)
    extension = _successor("nest-b-next", "nest-b", _ONE_SCOPE)
    report = _check(*tree, new, extension, baseline=_baseline(p, pinned=[a, b, a1, a2], forks=both))
    assert report.forks == (
        Fork("nest-p", ("nest-a", "nest-b", "nest-n"), ("nest-a", "nest-b"), ("nest-a1x",)),
    )
    assert report.ended_branches == (
        EndedBranch("nest-b-next", "nest-b", "nest-p", ("nest-a",), ("nest-a1x",)),
    )

    # With only the fork below recorded, the one at nest-p lists every successor's
    # newest selectors, still without the branch nest-a's line ended.
    only_below = {"nest-a": (below,)}
    report = _check(*tree, new, baseline=_baseline(p, pinned=[a, a1, a2], forks=only_below))
    assert report.forks == (
        Fork("nest-p", ("nest-a", "nest-b", "nest-n"), (), ("nest-a1x", "nest-b", "nest-n")),
    )


@_SETTINGS
@given(parents=_PARENTS, data=st.data())
def test_line_heads_finds_what_a_walk_up_finds(
    parents: list[int | None], data: st.DataObject
) -> None:
    """Differential: line_heads walks down from the branches; the reference walks up to them.

    Any selector with successors may be recorded, continuing any of them, or only a
    name no selector has (a stale record).
    """
    selectors, _, named = _tree(parents)
    predecessors = _check(*selectors).predecessors
    continued = {
        predecessor: tuple(
            sorted(data.draw(st.sets(st.sampled_from([*successors, "gone-cut"]), min_size=1)))
        )
        for predecessor, successors in sorted(named.items())
        if data.draw(st.booleans())
    }
    branches = data.draw(st.sets(st.sampled_from([s.name for s in selectors]), min_size=1))
    assert line_heads(predecessors, continued, branches) == _heads_walking_up(
        predecessors, continued, branches
    )


def test_a_first_cut_record_for_an_edited_selector_no_longer_holds() -> None:
    ssi = _selector("pin-ssi", _PIN)
    report = _check(ssi, baseline=_with_digest(_baseline(ssi), "pin-ssi", "0" * 64))
    assert report.unnamed == (UnnamedPredecessor("pin-ssi"),)
    assert report.recorded_first_cuts == ()
    assert any("digest is" in error for error in report.baseline_errors)


def test_selectors_must_be_keyed_by_their_names() -> None:
    with pytest.raises(ValueError, match="holds a manifest named"):
        check_selector_lineage({"other": _selector("pin-ssi", _PIN)})


# --- bases: a pair's base is carried unchanged while the pair is carried ---

_US_CODE: ScopeKey = ("us", "statute", "2026-05-01-us-code")
_ECFR: ScopeKey = ("us", "regulation", "2026-05-01-ecfr")
_NEW_US_CODE: ScopeKey = ("us", "statute", "2026-11-01-us-code")
_LAYERED_PRIMARIES: list[ScopeKey] = [
    ("us", "regulation", "2026-10-29-ecfr-section-text"),
    ("us", "statute", "2026-09-29-election-statute-uocava-nvra-title-52"),
    ("us", "statute", "2026-10-06-w6-federal-public-laws"),
    ("us-mt", "statute", "2026-07-13-recovery"),
]


def _layered(
    name: str,
    primaries: Iterable[ScopeKey],
    bases: Iterable[ScopeKey] = (),
    description: str | None = None,
) -> ReleaseManifest:
    scopes = [ReleaseScope(*key) for key in primaries]
    scopes += [ReleaseScope(*key, layer=LAYER_BASE) for key in bases]
    return ReleaseManifest(
        name=name,
        scopes=tuple(sorted(scopes, key=lambda scope: scope.key)),
        description=description,
    )


def _layered_predecessor() -> ReleaseManifest:
    return _layered("pin-layered", _LAYERED_PRIMARIES, [_US_CODE, _ECFR])


def _layered_successor(
    primaries: Iterable[ScopeKey], bases: Iterable[ScopeKey], name: str = "pin-next"
) -> ReleaseManifest:
    return _layered(name, primaries, bases, "Successor to pin-layered. It adds what it adds.")


def _base_report(successor: ReleaseManifest) -> LineageReport:
    predecessor = _layered_predecessor()
    return _check(predecessor, successor, baseline=_baseline(predecessor))


_DROPPED_US_CODE = DroppedBase("pin-next", "pin-layered", ("us", "statute"), _US_CODE[2])


@pytest.mark.parametrize(
    ("primaries", "bases"),
    [
        (_LAYERED_PRIMARIES, [_ECFR]),
        (_LAYERED_PRIMARIES, [_ECFR, _NEW_US_CODE]),
        ([*_LAYERED_PRIMARIES, _US_CODE], [_ECFR]),
    ],
    ids=["base-left-out", "base-version-changed", "base-flipped-to-primary"],
)
def test_a_kept_pair_whose_base_changes_is_a_dropped_base(
    primaries: list[ScopeKey], bases: list[ScopeKey]
) -> None:
    report = _base_report(_layered_successor(primaries, bases))
    assert report.dropped_bases == (_DROPPED_US_CODE,)
    assert report.dropped == () and report.layer_changes == ()
    assert report.problems() == [
        "pin-next does not select us/statute/2026-05-01-us-code as a base scope, which its "
        "predecessor pin-layered selects as the base of us/statute: a base is carried "
        "unchanged while its pair is carried"
    ]


def test_a_primary_flipped_to_base_is_a_layer_change() -> None:
    moved: ScopeKey = ("us-mt", "statute", "2026-07-13-recovery")
    primaries = [key for key in _LAYERED_PRIMARIES if key != moved]
    report = _base_report(_layered_successor(primaries, [_US_CODE, _ECFR, moved]))
    assert report.layer_changes == (LayerChanged("pin-next", "pin-layered", moved),)
    assert report.dropped_bases == () and report.dropped == ()
    assert report.problems() == [
        "pin-next selects us-mt/statute/2026-07-13-recovery as a base scope, which its "
        "predecessor pin-layered selects as a primary scope"
    ]


def test_a_primary_moved_into_a_pairs_base_also_drops_the_old_base() -> None:
    moved: ScopeKey = ("us", "statute", "2026-10-06-w6-federal-public-laws")
    primaries = [key for key in _LAYERED_PRIMARIES if key != moved]
    report = _base_report(_layered_successor(primaries, [_ECFR, moved]))
    assert report.dropped_bases == (_DROPPED_US_CODE,)
    assert report.layer_changes == (LayerChanged("pin-next", "pin-layered", moved),)


@pytest.mark.parametrize(
    "primaries",
    [
        [*_LAYERED_PRIMARIES, ("us", "statute", "2026-11-11-new-public-laws")],
        [
            ("us", "regulation", "2026-11-11-ecfr-section-text"),
            *_LAYERED_PRIMARIES[1:],
        ],
        _LAYERED_PRIMARIES[1:],
    ],
    ids=["primary-added", "primary-replaced", "primary-removed-base-keeps-the-pair"],
)
def test_a_base_carried_unchanged_is_not_a_finding(primaries: list[ScopeKey]) -> None:
    successor = _layered_successor(primaries, [_US_CODE, _ECFR])
    assert base_changes(_layered_predecessor(), successor) == ({}, ())
    assert _base_report(successor).ok


def test_a_base_added_to_a_pair_with_none_is_not_a_finding() -> None:
    """A restore puts a base under a pair whose predecessor has none (PR5)."""
    predecessor = _layered("pin-layered", _LAYERED_PRIMARIES, [_US_CODE])
    successor = _layered_successor(_LAYERED_PRIMARIES, [_US_CODE, _ECFR])
    assert base_changes(predecessor, successor) == ({}, ())
    assert _check(predecessor, successor, baseline=_baseline(predecessor)).ok


def test_a_pair_dropped_whole_drops_its_base_as_a_dropped_pair_only() -> None:
    kept = [key for key in _LAYERED_PRIMARIES if key[:2] != ("us", "statute")]
    report = _base_report(_layered_successor(kept, [_ECFR]))
    assert report.dropped == (
        DroppedPair(
            "pin-next",
            "pin-layered",
            ("us", "statute"),
            (
                "2026-05-01-us-code",
                "2026-09-29-election-statute-uocava-nvra-title-52",
                "2026-10-06-w6-federal-public-laws",
            ),
        ),
    )
    assert report.dropped_bases == () and report.layer_changes == ()


def _replacement(**changes: object) -> RecordedBaseReplacement:
    values: dict[str, object] = {
        "selector": "pin-next",
        "predecessor": "pin-layered",
        "pair": ("us", "statute"),
        "replaced": _US_CODE[2],
        "replaced_by": _NEW_US_CODE,
        "listed_on": "2026-11-17",
        "reason": "The reviewed restore replaces the May base.",
    }
    values.update(changes)
    return RecordedBaseReplacement(**values)  # type: ignore[arg-type]


def _replacement_baseline(
    *roots: ReleaseManifest,
    pinned: Iterable[ReleaseManifest],
    replacement: RecordedBaseReplacement,
) -> LineageBaseline:
    """Record ``roots`` as first cuts, pin them and ``pinned``, and record ``replacement``."""
    baseline = _baseline(*roots, pinned=pinned)
    return replace(
        baseline, base_replacements={(replacement.selector, replacement.pair): replacement}
    )


def test_a_pinned_base_replacement_is_recorded_not_reported() -> None:
    predecessor = _layered_predecessor()
    successor = _layered_successor(_LAYERED_PRIMARIES, [_ECFR, _NEW_US_CODE])
    baseline = _replacement_baseline(predecessor, pinned=[successor], replacement=_replacement())
    report = _check(predecessor, successor, baseline=baseline)
    assert report.ok, report.problems()
    assert report.recorded_base_replacements == (_DROPPED_US_CODE,)
    assert report.dropped_bases == ()


_REPLACING = "us/statute/2026-05-01-us-code"
_NOT_A_BASE = (
    "the baseline names us/statute/{version} as the base replacing "
    f"{_REPLACING} in pin-next, which does not select it as a base scope"
)


@pytest.mark.parametrize(
    ("primaries", "bases", "changes", "stale", "error"),
    [
        pytest.param(
            _LAYERED_PRIMARIES,
            [_ECFR, _NEW_US_CODE],
            {},
            "pin-next",
            "the baseline pins pin-next at",
            id="stale-pin-of-the-selector",
        ),
        pytest.param(
            _LAYERED_PRIMARIES,
            [_ECFR, _NEW_US_CODE],
            {},
            "pin-layered",
            "the baseline pins pin-layered at",
            id="stale-pin-of-the-predecessor",
        ),
        pytest.param(
            _LAYERED_PRIMARIES,
            [_ECFR, _NEW_US_CODE],
            {"replaced_by": ("us", "statute", "2026-12-01-us-code")},
            None,
            _NOT_A_BASE.format(version="2026-12-01-us-code"),
            id="replaced-by-not-selected",
        ),
        pytest.param(
            [*_LAYERED_PRIMARIES, _NEW_US_CODE],
            [_ECFR],
            {},
            None,
            _NOT_A_BASE.format(version=_NEW_US_CODE[2]),
            id="replaced-by-selected-as-a-primary-scope",
        ),
        pytest.param(
            _LAYERED_PRIMARIES,
            [_ECFR, _NEW_US_CODE],
            {"replaced": "2026-04-01-us-code"},
            None,
            "the baseline records pin-next replacing the base us/statute/2026-04-01-us-code "
            "of pin-layered, but it does not drop that base",
            id="replaced-is-not-the-predecessors-base",
        ),
        pytest.param(
            _LAYERED_PRIMARIES,
            [_ECFR, _NEW_US_CODE],
            {"predecessor": "pin-other"},
            None,
            f"the baseline records pin-next replacing the base {_REPLACING} of pin-other, "
            "but pin-next names pin-layered as its predecessor",
            id="another-predecessor",
        ),
    ],
)
def test_a_base_replacement_record_that_no_longer_holds_is_a_baseline_error(
    primaries: list[ScopeKey],
    bases: list[ScopeKey],
    changes: dict[str, object],
    stale: str | None,
    error: str,
) -> None:
    """The finding stays a problem, and the record that no longer holds is one error."""
    predecessor = _layered_predecessor()
    other = _layered("pin-other", _LAYERED_PRIMARIES, [_US_CODE, _ECFR])
    successor = _layered_successor(primaries, bases)
    baseline = _replacement_baseline(
        predecessor, other, pinned=[successor], replacement=_replacement(**changes)
    )
    if stale is not None:
        baseline = replace(
            baseline, selector_digests={**baseline.selector_digests, stale: "0" * 64}
        )
    report = _check(predecessor, other, successor, baseline=baseline)
    assert report.dropped_bases == (_DROPPED_US_CODE,)
    assert report.recorded_base_replacements == ()
    assert len(report.baseline_errors) == 1, report.baseline_errors
    assert report.baseline_errors[0].startswith(error), report.baseline_errors


@pytest.mark.parametrize(
    ("bases", "key", "changes", "message"),
    [
        pytest.param(
            [_ECFR],
            ("pin-next", ("us", "statute")),
            {"replaced_by": _ECFR},
            r"base_replacements\[pin-next, us/statute\]\.replaced_by must be a scope of "
            r"us/statute",
            id="replaced-by-another-pairs-base",
        ),
        pytest.param(
            [_ECFR],
            ("pin-next", ("us", "statute")),
            {"pair": ("us", "regulation"), "replaced_by": _ECFR},
            r"base_replacements\[pin-next, us/regulation\]: keyed by "
            r"\('pin-next', \('us', 'statute'\)\)",
            id="another-pairs-record-under-this-key",
        ),
        pytest.param(
            [_ECFR, _NEW_US_CODE],
            ("pin-next", ("us", "statute")),
            {"selector": "pin-other"},
            r"base_replacements\[pin-other, us/statute\]: keyed by",
            id="another-selectors-record-under-this-key",
        ),
        pytest.param(
            [_ECFR, _NEW_US_CODE],
            ("pin-next", ("us", "statute")),
            {"predecessor": "pin-next"},
            r": a selector cannot succeed itself",
            id="selector-succeeds-itself",
        ),
        pytest.param(
            [_ECFR, _NEW_US_CODE],
            ("pin-next", ("us", "statute")),
            {"replaced_by": _US_CODE},
            r"\.replaced_by must differ from the base it replaces",
            id="replaced-by-the-base-it-replaces",
        ),
    ],
)
def test_a_base_replacement_built_in_code_is_held_to_the_files_rules(
    bases: list[ScopeKey],
    key: tuple[str, tuple[str, str]],
    changes: dict[str, object],
    message: str,
) -> None:
    """A baseline built in code meets the loader's rules before the check compares anything."""
    predecessor = _layered_predecessor()
    successor = _layered_successor(_LAYERED_PRIMARIES, bases)
    baseline = replace(
        _baseline(predecessor, pinned=[successor]),
        base_replacements={key: _replacement(**changes)},
    )
    with pytest.raises(SelectorLineageError, match=message):
        _check(predecessor, successor, baseline=baseline)


@pytest.mark.parametrize(
    "replaced_by", sorted({*_LAYERED_PRIMARIES, _US_CODE, _ECFR, _NEW_US_CODE})
)
@pytest.mark.parametrize(
    "bases",
    [[_ECFR], [_ECFR, _NEW_US_CODE]],
    ids=["us-code-left-out", "us-code-replaced"],
)
def test_a_base_replacement_allows_only_a_base_of_its_own_pair(
    bases: list[ScopeKey], replaced_by: ScopeKey
) -> None:
    predecessor = _layered_predecessor()
    successor = _layered_successor(_LAYERED_PRIMARIES, bases)
    baseline = _replacement_baseline(
        predecessor, pinned=[successor], replacement=_replacement(replaced_by=replaced_by)
    )
    if replaced_by[:2] != ("us", "statute") or replaced_by == _US_CODE:
        with pytest.raises(SelectorLineageError):
            _check(predecessor, successor, baseline=baseline)
        return
    report = _check(predecessor, successor, baseline=baseline)
    allowed = replaced_by in bases
    assert report.recorded_base_replacements == ((_DROPPED_US_CODE,) if allowed else ())
    assert report.dropped_bases == (() if allowed else (_DROPPED_US_CODE,))


@st.composite
def _layered_scopes(draw: st.DrawFn) -> tuple[ReleaseScope, ...]:
    """A scope set with at most one base per pair."""
    keys = sorted(draw(_SCOPE_SETS))
    members: dict[tuple[str, str], list[ScopeKey]] = defaultdict(list)
    for key in keys:
        members[key[:2]].append(key)
    bases: set[ScopeKey] = set()
    for pair in sorted(members):
        if draw(st.booleans()):
            bases.add(draw(st.sampled_from(members[pair])))
    return tuple(
        ReleaseScope(*key, layer=LAYER_BASE if key in bases else LAYER_PRIMARY) for key in keys
    )


@_SETTINGS
@given(before=_layered_scopes(), after=_layered_scopes())
def test_a_base_never_changes_without_a_report(
    before: tuple[ReleaseScope, ...], after: tuple[ReleaseScope, ...]
) -> None:
    """Each base is carried unchanged, leaves with its pair, or is a dropped base: one of them."""
    predecessor = ReleaseManifest("line-a", before)
    successor = ReleaseManifest("line-b", after, "Successor to line-a.")
    report = _check(predecessor, successor, baseline=_baseline(predecessor))
    pairs_dropped = {finding.pair for finding in report.dropped}
    bases_dropped = {finding.pair: finding.base_version for finding in report.dropped_bases}
    for base in (scope for scope in before if scope.is_base):
        outcomes = [
            base in after,
            base.pair in pairs_dropped,
            bases_dropped.get(base.pair) == base.version,
        ]
        assert outcomes.count(True) == 1, (base, outcomes)
    assert set(bases_dropped) <= {scope.pair for scope in before if scope.is_base}
    primary = {scope.key for scope in before if not scope.is_base}
    assert {finding.scope for finding in report.layer_changes} == {
        scope.key for scope in after if scope.is_base and scope.key in primary
    }
    for finding in (*report.dropped_bases, *report.layer_changes):
        assert (finding.selector, finding.predecessor) == ("line-b", "line-a")
    assert base_changes(predecessor, predecessor) == ({}, ())


# --- the baseline file ---

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64
_DIGEST_D = "d" * 64

_VALID = f"""\
schema_version: {LINEAGE_BASELINE_SCHEMA}
selector_digests:
  line-a: {_DIGEST_A}
  line-b: {_DIGEST_B}
  line-c: {_DIGEST_C}
  line-d: {_DIGEST_D}
dropped_pairs:
  - selector: line-b
    predecessor: line-a
    pair: uk-shropshire/manual
    listed_on: 2026-11-02
    reason: >-
      Retired by omission.
forks:
  - predecessor: line-a
    successors:
      - line-b
      - line-c
    continued_by:
      - line-c
    listed_on: 2026-11-02
    reason: The line splits.
first_cuts:
  - listed_on: 2026-11-02
    reason: The first cut of its line.
    selectors:
      - line-d
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "selector-lineage-baseline.yaml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_the_baseline_file_parses(tmp_path: Path) -> None:
    baseline = load_lineage_baseline(_write(tmp_path, _VALID))
    assert baseline.selector_digests == {
        "line-a": _DIGEST_A,
        "line-b": _DIGEST_B,
        "line-c": _DIGEST_C,
        "line-d": _DIGEST_D,
    }
    assert baseline.drops == {
        ("line-b", ("uk-shropshire", "manual")): RecordedDrop(
            "line-b", "line-a", ("uk-shropshire", "manual"), "2026-11-02", "Retired by omission."
        )
    }
    assert baseline.forks == {
        "line-a": (
            RecordedFork(
                "line-a", ("line-b", "line-c"), ("line-c",), "2026-11-02", "The line splits."
            ),
        )
    }
    assert baseline.first_cuts == {
        "line-d": RecordedFirstCut("line-d", "2026-11-02", "The first cut of its line.")
    }


def test_a_checkout_without_the_baseline_records_nothing(tmp_path: Path) -> None:
    assert LineageBaseline.load(tmp_path) == LineageBaseline()


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (f"schema_version: {LINEAGE_BASELINE_SCHEMA}", "schema_version: v0", "schema_version"),
        ("selector_digests:", "extra: 1\nselector_digests:", "unsupported fields"),
        (
            "selector_digests:",
            "extra: 1\n2026: x\nselector_digests:",
            r"unsupported fields \[2026, 'extra'\]",
        ),
        (
            f"  line-a: {_DIGEST_A}\n  line-b",
            f"  line-b: {_DIGEST_B}\n  line-a: {_DIGEST_A}\n  line-x",
            "sorted",
        ),
        (f"  line-c: {_DIGEST_C}\n", "", "line-c has no selector_digests entry"),
        (f"  line-d: {_DIGEST_D}\n", f"  line-d: {_DIGEST_D}\n  line-e: {_DIGEST_D}\n", "unused"),
        (f"line-a: {_DIGEST_A}", "line-a: not-a-digest", "sha256"),
        ("pair: uk-shropshire/manual", "pair: uk-shropshire", "jurisdiction/document_class"),
        ("pair: uk-shropshire/manual", "pair: uk-shropshire/leaflet", "document_class"),
        (
            "    listed_on: 2026-11-02\n    reason: >-",
            "    listed_on: soon\n    reason: >-",
            "ISO date",
        ),
        ("    reason: >-\n      Retired by omission.\n", "", r"missing \['reason'\]"),
        (
            "    pair: uk-shropshire/manual\n",
            "    pair: uk-shropshire/manual\n    replaced-by: [uk/manual/v1]\n",
            r"dropped_pairs\[0\]: unsupported fields \['replaced-by'\]",
        ),
        (
            "    predecessor: line-a\n    pair",
            "    predecessor: line-b\n    pair",
            "cannot succeed itself",
        ),
        ("      - line-b\n      - line-c", "      - line-c\n      - line-b", "sorted"),
        ("      - line-b\n      - line-c", "      - line-b", "at least two"),
        (
            "    reason: The line splits.",
            "    note: The line splits.",
            r"forks\[0\]: unsupported fields \['note'\]",
        ),
        ("    continued_by:\n      - line-c", "    continued_by: []", "continued_by must name"),
        (
            "    continued_by:\n      - line-c",
            "    continued_by:\n      - line-c\n      - line-b",
            r"continued_by must be sorted",
        ),
        ("    reason: The line splits.\n", "", r"forks\[0\]: missing \['reason'\]"),
        ("    reason: The first cut of its line.\n", "", "must have exactly"),
        (
            "    continued_by:\n      - line-c",
            "    continued_by:\n      - line-d",
            "only successors",
        ),
        (
            "    pair: uk-shropshire/manual\n",
            "    pair: uk-shropshire/manual\n    replaced_by: uk/manual/x\n",
            "must be a list",
        ),
        (
            "    pair: uk-shropshire/manual\n",
            "    pair: uk-shropshire/manual\n    replaced_by: 0\n",
            r"dropped_pairs\[0\]\.replaced_by must be a list",
        ),
        (
            "    pair: uk-shropshire/manual\n",
            "    pair: uk-shropshire/manual\n    replaced_by: [uk/manual]\n",
            "jurisdiction/document_class/version",
        ),
        ("    selectors:\n      - line-d", "    selectors: []", "at least one selector"),
        (
            "    selectors:\n      - line-d",
            "    selectors:\n      - line-d\n      - line-d",
            "sorted",
        ),
        ("    reason: The first cut of its line.", "    note: x", "must have exactly"),
        (
            "  - predecessor: line-a\n    successors:",
            "  - predecessor: line-b\n    successors:",
            "cannot succeed itself",
        ),
        (
            "    pair: uk-shropshire/manual\n",
            "    pair: uk-shropshire/manual\n    replaced_by: [uk/manual/v2, uk/manual/v1]\n",
            r"replaced_by must be sorted",
        ),
        (
            "    pair: uk-shropshire/manual\n",
            "    pair: uk-shropshire/manual\n    replaced_by: [uk/leaflet/v1]\n",
            "invalid document_class",
        ),
        (
            f"  line-d: {_DIGEST_D}\n",
            f"  line-d: {_DIGEST_D}\n  current: {_DIGEST_D}\n",
            "reserved",
        ),
        (
            "    continued_by:\n      - line-c",
            "    continued_by:\n      - Line-C",
            "lowercase alphanumeric",
        ),
    ],
)
def test_a_malformed_baseline_is_refused(tmp_path: Path, old: str, new: str, message: str) -> None:
    assert old in _VALID, old
    with pytest.raises(SelectorLineageError, match=message):
        load_lineage_baseline(_write(tmp_path, _VALID.replace(old, new, 1)))


def test_a_duplicate_drop_record_is_refused(tmp_path: Path) -> None:
    drop = _VALID.split("dropped_pairs:\n", 1)[1].split("forks:", 1)[0]
    text = _VALID.replace(drop, drop + drop, 1)
    with pytest.raises(
        SelectorLineageError, match="dropped_pairs .* sorted and free of duplicates"
    ):
        load_lineage_baseline(_write(tmp_path, text))


def test_forks_must_be_sorted_by_predecessor(tmp_path: Path) -> None:
    fork = _VALID.split("forks:\n", 1)[1].split("first_cuts:", 1)[0]
    later = fork.replace("  - predecessor: line-a\n", "  - predecessor: line-d\n", 1)
    text = _VALID.replace(fork, later + fork, 1)
    with pytest.raises(
        SelectorLineageError, match="forks must be sorted by predecessor, then listed_on"
    ):
        load_lineage_baseline(_write(tmp_path, text))


@pytest.mark.parametrize("value", ["not-a-list", "''", "{}", "0", "false"])
@pytest.mark.parametrize(
    "section", ["dropped_pairs", "forks", "first_cuts", "successions", "base_replacements"]
)
def test_a_section_that_is_not_a_list_is_refused(tmp_path: Path, section: str, value: str) -> None:
    """Only an absent or null section reads as empty, as for a fork entry's lists."""
    text = f"schema_version: {LINEAGE_BASELINE_SCHEMA}\n{section}: {value}\n"
    with pytest.raises(SelectorLineageError, match=f"{section} must be a list"):
        load_lineage_baseline(_write(tmp_path, text))


@pytest.mark.parametrize("value", ["not-a-mapping", "''", "[]", "0"])
def test_selector_digests_that_is_not_a_mapping_is_refused(tmp_path: Path, value: str) -> None:
    text = f"schema_version: {LINEAGE_BASELINE_SCHEMA}\nselector_digests: {value}\n"
    with pytest.raises(SelectorLineageError, match="selector_digests must be a mapping"):
        load_lineage_baseline(_write(tmp_path, text))


def test_an_absent_or_null_section_reads_as_empty(tmp_path: Path) -> None:
    sections = [
        "selector_digests",
        "dropped_pairs",
        "forks",
        "first_cuts",
        "successions",
        "base_replacements",
    ]
    text = f"schema_version: {LINEAGE_BASELINE_SCHEMA}\n" + "".join(f"{s}:\n" for s in sections)
    assert load_lineage_baseline(_write(tmp_path, text)) == LineageBaseline()
    only_schema = f"schema_version: {LINEAGE_BASELINE_SCHEMA}\n"
    assert load_lineage_baseline(_write(tmp_path, only_schema)) == LineageBaseline()


def test_a_first_cut_listed_in_two_groups_is_refused(tmp_path: Path) -> None:
    group = _VALID.split("first_cuts:\n", 1)[1]
    with pytest.raises(SelectorLineageError, match="line-d is listed twice"):
        load_lineage_baseline(_write(tmp_path, _VALID + group))


_DATED = f"""\
schema_version: {LINEAGE_BASELINE_SCHEMA}
selector_digests:
  line-a: {_DIGEST_A}
  line-b: {_DIGEST_B}
  line-c: {_DIGEST_C}
  line-d: {_DIGEST_D}
forks:
  - predecessor: line-a
    successors:
      - line-b
      - line-c
    continued_by:
      - line-c
    listed_on: 2026-11-02
    reason: The line splits.
  - predecessor: line-a
    successors:
      - line-d
    listed_on: 2026-11-03
    reason: A third branch, on purpose.
  - predecessor: line-a
    continued_by:
      - line-b
    listed_on: 2026-11-04
    reason: The line now goes on through line-b too.
"""


def test_a_misplaced_entry_is_named_where_another_forks_entry_follows_it(
    tmp_path: Path,
) -> None:
    """The sort refusal names the entry before it, so a misplaced later entry is named."""
    text = f"""\
schema_version: {LINEAGE_BASELINE_SCHEMA}
selector_digests:
  line-a: {_DIGEST_A}
  line-b: {_DIGEST_B}
  line-c: {_DIGEST_C}
  line-d: {_DIGEST_D}
forks:
  - predecessor: line-b
    successors: [line-d]
    listed_on: 2026-11-03
    reason: A later decision, placed first.
  - predecessor: line-a
    successors: [line-b, line-c]
    continued_by: [line-c]
    listed_on: 2026-11-02
    reason: The line splits.
  - predecessor: line-b
    successors: [line-c, line-d]
    continued_by: [line-c]
    listed_on: 2026-11-02
    reason: The line splits.
"""
    with pytest.raises(
        SelectorLineageError,
        match=r"forks\[1\]: forks must be sorted by predecessor, then listed_on, but "
        r"forks\[0\] \(the fork at line-b, listed on 2026-11-03\) comes before this entry "
        r"for line-a",
    ):
        load_lineage_baseline(_write(tmp_path, text))


def test_a_forks_later_entries_are_kept_in_order_and_merged(tmp_path: Path) -> None:
    baseline = load_lineage_baseline(_write(tmp_path, _DATED))
    assert baseline.forks == {
        "line-a": (
            RecordedFork(
                "line-a", ("line-b", "line-c"), ("line-c",), "2026-11-02", "The line splits."
            ),
            RecordedFork("line-a", ("line-d",), (), "2026-11-03", "A third branch, on purpose."),
            RecordedFork(
                "line-a", (), ("line-b",), "2026-11-04", "The line now goes on through line-b too."
            ),
        )
    }
    assert baseline.fork_successors("line-a") == ("line-b", "line-c", "line-d")
    assert baseline.fork_continued_by("line-a") == ("line-b", "line-c")
    assert baseline.fork_successors("line-b") == baseline.fork_continued_by("line-b") == ()


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            "    listed_on: 2026-11-04",
            "    listed_on: 2026-11-01",
            r"forks\[2\]: the fork at line-a has an entry listed on 2026-11-03 \(forks\[1\]\) "
            r"before this one, listed on 2026-11-01",
        ),
        (
            "  - predecessor: line-a\n    successors:\n      - line-b\n      - line-c\n    continued_by:\n      - line-c\n    listed_on: 2026-11-02\n    reason: The line splits.\n  - predecessor: line-a\n    successors:\n      - line-d\n    listed_on: 2026-11-03\n    reason: A third branch, on purpose.\n",
            "  - predecessor: line-a\n    successors:\n      - line-d\n    listed_on: 2026-11-03\n    reason: A third branch, on purpose.\n  - predecessor: line-a\n    successors:\n      - line-b\n      - line-c\n    continued_by:\n      - line-c\n    listed_on: 2026-11-02\n    reason: The line splits.\n",
            r"forks\[1\]: the fork at line-a has an entry listed on 2026-11-03 \(forks\[0\]\) "
            r"before this one, listed on 2026-11-02",
        ),
        (
            "    listed_on: 2026-11-04",
            "    listed_on: 2026-11-03",
            r"forks\[2\]: the fork at line-a already has an entry listed on 2026-11-03",
        ),
        (
            "    successors:\n      - line-d\n",
            "    successors:\n      - line-b\n",
            r"forks\[1\]: an earlier entry for the fork at line-a already records line-b",
        ),
        (
            "    continued_by:\n      - line-b\n",
            "    continued_by:\n      - line-c\n",
            r"forks\[2\]: an earlier entry for the fork at line-a already records line-c",
        ),
        (
            "  - predecessor: line-a\n    continued_by:\n      - line-b\n",
            "  - predecessor: line-a\n",
            r"forks\[2\] must add a successor or a continued_by branch to the fork at line-a",
        ),
        (
            "    continued_by:\n      - line-b\n",
            "    continued_by:\n      - line-x\n",
            r"forks\[2\]\.continued_by must name only successors of the fork at line-a",
        ),
        (
            "    reason: A third branch, on purpose.\n",
            "",
            r"forks\[1\]: missing \['reason'\]",
        ),
        (
            "    listed_on: 2026-11-03\n",
            "",
            r"forks\[1\]: missing \['listed_on'\]",
        ),
        (
            # A predecessor's first entry, placed in order, with too few successors.
            "  - predecessor: line-a\n    continued_by:\n      - line-b\n",
            "  - predecessor: line-d\n    continued_by:\n      - line-b\n",
            r"forks\[2\]\.successors must list at least two selectors",
        ),
        (
            "    successors:\n      - line-d\n",
            "    successors:\n      - line-d\n      - line-a\n",
            r"forks\[1\]\.successors must be sorted",
        ),
        (
            "    successors:\n      - line-d\n",
            "    successors:\n      - line-a\n",
            r"forks\[1\]: a selector cannot succeed itself",
        ),
        (
            "  - predecessor: line-a\n    continued_by:\n      - line-b\n",
            "  - predecessor: line-a\n    successors: 0\n    continued_by:\n      - line-b\n",
            r"forks\[2\]\.successors must be a list",
        ),
        (
            "    successors:\n      - line-d\n",
            "    successors:\n      - line-d\n    continued_by: ''\n",
            r"forks\[1\]\.continued_by must be a list",
        ),
        (
            "  - predecessor: line-a\n    successors:\n      - line-d\n",
            "  - successors:\n      - line-d\n",
            r"forks\[1\]: missing \['predecessor'\]",
        ),
    ],
)
def test_a_malformed_later_fork_entry_is_refused(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert _DATED.count(old) == 1, old
    with pytest.raises(SelectorLineageError, match=message):
        load_lineage_baseline(_write(tmp_path, _DATED.replace(old, new, 1)))


# --- the base_replacements section ---

_REPLACEMENT = """\
base_replacements:
  - selector: line-c
    predecessor: line-a
    pair: us/statute
    replaced: 2026-05-01-us-code
    replaced_by: us/statute/2026-11-01-us-code
    listed_on: 2026-11-17
    reason: The reviewed restore replaces the May base.
"""
_LAYERED_VALID = _VALID + _REPLACEMENT


def test_a_base_replacement_parses(tmp_path: Path) -> None:
    baseline = load_lineage_baseline(_write(tmp_path, _LAYERED_VALID))
    assert baseline.base_replacements == {
        ("line-c", ("us", "statute")): RecordedBaseReplacement(
            "line-c",
            "line-a",
            ("us", "statute"),
            "2026-05-01-us-code",
            ("us", "statute", "2026-11-01-us-code"),
            "2026-11-17",
            "The reviewed restore replaces the May base.",
        )
    }
    assert load_lineage_baseline(_write(tmp_path, _VALID)).base_replacements == {}


def test_a_date_only_replaced_version_reads_as_its_text(tmp_path: Path) -> None:
    """YAML reads an unquoted 2026-08-07 as a date; the version is its ISO text."""
    for spelled in ("2026-08-07", "'2026-08-07'"):
        text = _LAYERED_VALID.replace("replaced: 2026-05-01-us-code", f"replaced: {spelled}")
        baseline = load_lineage_baseline(_write(tmp_path, text))
        (replacement,) = baseline.base_replacements.values()
        assert replacement.replaced == "2026-08-07"


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("    replaced: 2026-05-01-us-code\n", "", r"missing \['replaced'\]"),
        (
            "    replaced_by: us/statute/2026-11-01-us-code\n",
            "",
            r"missing \['replaced_by'\]",
        ),
        (
            "    reason: The reviewed restore replaces the May base.\n",
            "    reason: The reviewed restore replaces the May base.\n    note: x\n",
            r"base_replacements\[0\]: unsupported fields \['note'\]",
        ),
        (
            "    replaced_by: us/statute/2026-11-01-us-code",
            "    replaced_by: [us/statute/2026-11-01-us-code]",
            r"replaced_by must be a non-empty string",
        ),
        (
            "    replaced_by: us/statute/2026-11-01-us-code",
            "    replaced_by: us/statute",
            "jurisdiction/document_class/version",
        ),
        (
            "    replaced_by: us/statute/2026-11-01-us-code",
            "    replaced_by: us/regulation/2026-11-01-ecfr",
            "replaced_by must be a scope of us/statute",
        ),
        (
            "    replaced_by: us/statute/2026-11-01-us-code",
            "    replaced_by: us/statute/2026-05-01-us-code",
            "replaced_by must differ from the base it replaces",
        ),
        (
            "    replaced: 2026-05-01-us-code",
            "    replaced: Bad-Version",
            r"replaced: .*invalid version",
        ),
        ("    replaced: 2026-05-01-us-code", "    replaced: 20260501", "must be a version string"),
        ("    pair: us/statute\n", "    pair: us\n", "jurisdiction/document_class"),
        (
            "  - selector: line-c\n    predecessor: line-a\n    pair: us/statute",
            "  - selector: line-a\n    predecessor: line-a\n    pair: us/statute",
            "cannot succeed itself",
        ),
        (
            "  - selector: line-c\n    predecessor: line-a\n    pair: us/statute",
            "  - selector: line-e\n    predecessor: line-a\n    pair: us/statute",
            "line-e has no selector_digests entry",
        ),
        ("    listed_on: 2026-11-17", "    listed_on: soon", "ISO date"),
    ],
)
def test_a_malformed_base_replacement_is_refused(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert _REPLACEMENT.count(old) == 1 and _VALID.count(old) == 0, old
    with pytest.raises(SelectorLineageError, match=message):
        load_lineage_baseline(_write(tmp_path, _LAYERED_VALID.replace(old, new, 1)))


def test_base_replacements_are_sorted_by_selector_then_pair_and_unique(tmp_path: Path) -> None:
    entry = _REPLACEMENT.split("base_replacements:\n", 1)[1]
    earlier = entry.replace("  - selector: line-c\n", "  - selector: line-b\n", 1)
    for entries in (entry + entry, entry + earlier):
        text = _VALID + "base_replacements:\n" + entries
        with pytest.raises(
            SelectorLineageError,
            match=r"base_replacements \(by selector, then pair\) must be sorted and free of",
        ):
            load_lineage_baseline(_write(tmp_path, text))
    in_order = _VALID + "base_replacements:\n" + earlier + entry
    assert len(load_lineage_baseline(_write(tmp_path, in_order)).base_replacements) == 2
