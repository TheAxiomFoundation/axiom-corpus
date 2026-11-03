"""The selector lineage check on generated and hand-built selectors (axiom-corpus#935).

Invariants:

- a pair's last version never leaves a line silently: every pair a predecessor
  carries is in its successor, or the check reports the drop, or a pinned
  record allows it;
- along a line of cuts, a pair that leaves is reported at the cut it leaves;
- a predecessor named by two or more selectors is a fork, unless a pinned
  record lists exactly those successors;
- a selector that names a fork's successor the line did not continue through is
  reported;
- a selector that names no tracked predecessor is reported unless a pinned
  record says it is the first cut of a line;
- selectors that name each other in a cycle are reported;
- a record holds only for the exact selectors it pins, and a record that no
  longer matches a finding fails.

The comparison is per pair: a pair the successor still carries is not a drop,
even when one of its documents leaves (``test_a_document_can_leave_a_kept_pair``
pins that limit).

The differential test holds the check's grouping of scopes into pairs to the
activation gate's (``scripts/check_release_gate.py``), so the pairs the check
protects are the pairs activation repoints.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from collections.abc import Iterable
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.models import DocumentClass
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope, ScopeKey
from axiom_corpus.corpus.selector_lineage import (
    LINEAGE_BASELINE_SCHEMA,
    Cycle,
    DroppedPair,
    EndedBranch,
    Fork,
    LineageBaseline,
    LineageReport,
    RecordedDrop,
    RecordedFirstCut,
    RecordedFork,
    SelectorLineageError,
    UnnamedPredecessor,
    check_selector_lineage,
    declared_predecessor,
    dropped_pairs,
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
    forks: dict[str, RecordedFork] | None = None,
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


@_SETTINGS
@given(
    parents=st.lists(st.one_of(st.none(), st.integers(min_value=0)), min_size=1, max_size=12),
    data=st.data(),
)
def test_forks_and_ended_branches_follow_the_named_predecessors(
    parents: list[int | None], data: st.DataObject
) -> None:
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

    expected = {
        predecessor: tuple(sorted(successors))
        for predecessor, successors in named.items()
        if len(successors) > 1
    }
    unrecorded = _check(*selectors, baseline=_baseline(*roots))
    assert {fork.predecessor: fork.successors for fork in unrecorded.forks} == expected
    assert unrecorded.dropped == () and unrecorded.ended_branches == ()

    continued = {
        predecessor: tuple(sorted(data.draw(st.sets(st.sampled_from(successors), min_size=1))))
        for predecessor, successors in expected.items()
    }
    recorded = _check(
        *selectors,
        baseline=_baseline(
            *roots,
            pinned=selectors,
            forks={
                predecessor: RecordedFork(
                    predecessor, successors, continued[predecessor], "2026-11-02", "split"
                )
                for predecessor, successors in expected.items()
            },
        ),
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
    assert report.forks == (Fork("pin-ssi", ("pin-ks", "pin-nyc")),)
    assert report.dropped == ()
    assert "2 selectors name pin-ssi as their predecessor" in report.problems()[0]


def test_extending_a_branch_the_line_did_not_continue_is_refused() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    follow = _successor("pin-ks-followup", "pin-ks", _PIN)
    head = _successor("pin-mt", "pin-nyc", _MT)
    fork = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), ("pin-nyc",), "2026-11-02", "split")
    baseline = _baseline(ssi, pinned=[nyc, ks], forks={"pin-ssi": fork})
    assert _check(ssi, nyc, ks, head, baseline=baseline).ok

    report = _check(ssi, nyc, ks, head, follow, baseline=baseline)
    assert report.ended_branches == (
        EndedBranch("pin-ks-followup", "pin-ks", "pin-ssi", ("pin-nyc",)),
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


def test_a_record_for_an_edited_selector_no_longer_holds() -> None:
    mt, stale = _drop_case()
    baseline = _baseline(mt, pinned=[stale], drops={("pin-stale", ("us-mt", "form")): _record()})
    digests = dict(baseline.selector_digests)
    digests["pin-stale"] = "0" * 64
    edited = LineageBaseline(digests, baseline.drops, first_cuts=baseline.first_cuts)
    report = _check(mt, stale, baseline=edited)
    assert [finding.pair for finding in report.dropped] == [("us-mt", "form")]
    assert any("digest is" in error for error in report.baseline_errors)


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
        ssi, nyc, ks, baseline=_baseline(ssi, pinned=[nyc, ks], forks={"pin-ssi": record})
    ).ok

    report = _check(
        ssi,
        nyc,
        ks,
        late,
        baseline=_baseline(ssi, pinned=[nyc, ks, late], forks={"pin-ssi": record}),
    )
    assert report.forks == (Fork("pin-ssi", ("pin-ks", "pin-late", "pin-nyc")),)
    assert report.baseline_errors == (
        "the baseline records pin-ks, pin-nyc as the successors of pin-ssi, but "
        "pin-ks, pin-late, pin-nyc name it",
    )


def test_selectors_must_be_keyed_by_their_names() -> None:
    with pytest.raises(ValueError, match="holds a manifest named"):
        check_selector_lineage({"other": _selector("pin-ssi", _PIN)})


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
        "line-a": RecordedFork(
            "line-a", ("line-b", "line-c"), ("line-c",), "2026-11-02", "The line splits."
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
        ("    reason: The line splits.", "    note: The line splits.", "must have exactly"),
        ("    continued_by:\n      - line-c", "    continued_by: []", "continued_by must name"),
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


def test_a_first_cut_listed_in_two_groups_is_refused(tmp_path: Path) -> None:
    group = _VALID.split("first_cuts:\n", 1)[1]
    with pytest.raises(SelectorLineageError, match="line-d is listed twice"):
        load_lineage_baseline(_write(tmp_path, _VALID + group))
