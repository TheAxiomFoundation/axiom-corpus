"""The selector lineage check on generated and hand-built selectors (axiom-corpus#935).

Invariants:

- a pair's last version never leaves a line silently: every pair a predecessor
  carries is in its successor, or the check reports the drop, or a pinned
  record allows it;
- along a line of cuts, a pair that leaves is reported at the cut it leaves;
- a predecessor named by two or more selectors is a fork, unless a pinned
  record lists exactly those successors;
- a record holds only for the exact selectors it pins.

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
    DroppedPair,
    Fork,
    LineageBaseline,
    RecordedDrop,
    RecordedFork,
    SelectorLineageError,
    check_selector_lineage,
    declared_predecessor,
    dropped_pairs,
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


# --- the brief's property: a pair's last version never disappears unnamed ---


@_SETTINGS
@given(before=_SCOPE_SETS, after=_SCOPE_SETS)
def test_a_pairs_last_version_never_leaves_without_a_report(
    before: frozenset[ScopeKey], after: frozenset[ScopeKey]
) -> None:
    predecessor = _selector("line-2026-01-01", before)
    successor = _successor("line-2026-02-01", predecessor.name, after)
    report = check_selector_lineage({s.name: s for s in (predecessor, successor)})

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
    baseline = LineageBaseline(
        selector_digests=_pin(predecessor, successor),
        drops={
            (successor.name, pair): RecordedDrop(
                successor.name, predecessor.name, pair, "2026-11-02", "decided", replaced_by
            )
            for pair in recorded
        },
    )
    report = check_selector_lineage({s.name: s for s in (predecessor, successor)}, baseline)

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
    report = check_selector_lineage({cut.name: cut for cut in cuts})
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
    assert report.forks == ()


@_SETTINGS
@given(parents=st.lists(st.one_of(st.none(), st.integers(min_value=0)), min_size=1, max_size=12))
def test_a_predecessor_named_by_several_selectors_is_a_fork(
    parents: list[int | None],
) -> None:
    selectors: list[ReleaseManifest] = []
    named: dict[str, list[str]] = {}
    for index, parent in enumerate(parents):
        name = f"tree-cut-{index}"
        if parent is None or index == 0:
            selectors.append(_selector(name, [("us", "statute", "2026-10-25-a")]))
            continue
        predecessor = selectors[parent % index].name
        named.setdefault(predecessor, []).append(name)
        selectors.append(_successor(name, predecessor, [("us", "statute", "2026-10-25-a")]))
    report = check_selector_lineage({s.name: s for s in selectors})

    expected = {
        predecessor: tuple(sorted(successors))
        for predecessor, successors in named.items()
        if len(successors) > 1
    }
    assert {fork.predecessor: fork.successors for fork in report.forks} == expected
    assert report.dropped == ()

    pinned = (
        LineageBaseline(
            selector_digests=_pin(*selectors),
            forks={
                predecessor: RecordedFork(predecessor, successors, "2026-11-02", "the line splits")
                for predecessor, successors in expected.items()
            },
        )
        if expected
        else LineageBaseline()
    )
    if pinned.forks:
        # Unused digests are a loader error, not a check error; the check only
        # needs every named selector pinned.
        recorded = check_selector_lineage({s.name: s for s in selectors}, pinned)
        assert recorded.forks == ()
        assert {fork.predecessor for fork in recorded.recorded_forks} == set(expected)
        assert recorded.ok


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
        ("No other selector is named here.", None),
        (None, None),
    ],
)
def test_the_predecessor_is_the_first_tracked_selector_named(
    description: str | None, expected: str | None
) -> None:
    release = _selector("self-cut", [("us", "statute", "2026-10-25-a")], description)
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


def test_replacing_a_pairs_version_is_not_a_drop_but_leaving_the_pair_is() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    mt = _successor("pin-mt", "pin-nyc", _MT)
    stale = _successor("pin-stale", "pin-mt", _NYC)
    report = check_selector_lineage({s.name: s for s in (ssi, nyc, mt, stale)})
    assert report.dropped == (
        DroppedPair(
            "pin-stale", "pin-mt", ("us-mt", "form"), ("2026-10-06-w6-income-tax-forms-mt",)
        ),
    )
    assert "pin-stale selects no us-mt/form scope" in report.problems()[0]
    assert report.forks == ()


def test_a_cut_from_a_superseded_base_is_a_fork() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", [*_PIN, ("us-ks", "policy", "2026-10-02-plan")])
    report = check_selector_lineage({s.name: s for s in (ssi, nyc, ks)})
    assert report.forks == (Fork("pin-ssi", ("pin-ks", "pin-nyc")),)
    assert report.dropped == ()
    assert "2 selectors name pin-ssi as their predecessor" in report.problems()[0]


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
    digests = _pin(mt, stale)
    digests["pin-stale"] = "0" * 64
    baseline = LineageBaseline(digests, {("pin-stale", ("us-mt", "form")): _record()})
    report = check_selector_lineage({s.name: s for s in (mt, stale)}, baseline)
    assert [finding.pair for finding in report.dropped] == [("us-mt", "form")]
    assert any("digest is" in error for error in report.baseline_errors)


def test_a_record_must_name_replacements_the_selector_selects() -> None:
    mt, stale = _drop_case()
    replaced = _record(replaced_by=(("us-mt", "guidance", "2026-10-06-w6"),))
    baseline = LineageBaseline(_pin(mt, stale), {("pin-stale", ("us-mt", "form")): replaced})
    report = check_selector_lineage({s.name: s for s in (mt, stale)}, baseline)
    assert [finding.pair for finding in report.dropped] == [("us-mt", "form")]
    assert report.baseline_errors == (
        "the baseline names us-mt/guidance/2026-10-06-w6 as replacing us-mt/form in "
        "pin-stale, which does not select it",
    )

    carried = _successor("pin-stale", "pin-mt", [*_NYC, ("us-mt", "guidance", "2026-10-06-w6")])
    baseline = LineageBaseline(_pin(mt, carried), {("pin-stale", ("us-mt", "form")): replaced})
    report = check_selector_lineage({s.name: s for s in (mt, carried)}, baseline)
    assert report.ok and [f.pair for f in report.recorded_drops] == [("us-mt", "form")]


def test_a_record_that_matches_no_drop_is_stale() -> None:
    mt = _selector("pin-mt", _MT)
    keeps = _successor("pin-stale", "pin-mt", _MT)
    baseline = LineageBaseline(_pin(mt, keeps), {("pin-stale", ("us-mt", "form")): _record()})
    report = check_selector_lineage({s.name: s for s in (mt, keeps)}, baseline)
    assert report.baseline_errors == (
        "the baseline records pin-stale dropping us-mt/form from pin-mt, but it does not "
        "drop that pair",
    )


def test_a_fork_record_holds_only_for_the_successors_it_lists() -> None:
    ssi = _selector("pin-ssi", _PIN)
    nyc = _successor("pin-nyc", "pin-ssi", _NYC)
    ks = _successor("pin-ks", "pin-ssi", _PIN)
    late = _successor("pin-late", "pin-ssi", _PIN)
    record = RecordedFork("pin-ssi", ("pin-ks", "pin-nyc"), "2026-11-02", "the line splits")
    selectors = {s.name: s for s in (ssi, nyc, ks)}
    assert check_selector_lineage(
        selectors, LineageBaseline(_pin(ssi, nyc, ks), forks={"pin-ssi": record})
    ).ok

    selectors[late.name] = late
    report = check_selector_lineage(
        selectors, LineageBaseline(_pin(ssi, nyc, ks, late), forks={"pin-ssi": record})
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

_VALID = f"""\
schema_version: {LINEAGE_BASELINE_SCHEMA}
selector_digests:
  line-a: {_DIGEST_A}
  line-b: {_DIGEST_B}
  line-c: {_DIGEST_C}
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
    listed_on: 2026-11-02
    reason: The line splits.
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
    }
    assert baseline.drops == {
        ("line-b", ("uk-shropshire", "manual")): RecordedDrop(
            "line-b", "line-a", ("uk-shropshire", "manual"), "2026-11-02", "Retired by omission."
        )
    }
    assert baseline.forks == {
        "line-a": RecordedFork("line-a", ("line-b", "line-c"), "2026-11-02", "The line splits.")
    }


def test_a_checkout_without_the_baseline_records_nothing(tmp_path: Path) -> None:
    assert LineageBaseline.load(tmp_path) == LineageBaseline()


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (f"schema_version: {LINEAGE_BASELINE_SCHEMA}", "schema_version: v0", "schema_version"),
        ("selector_digests:", "extra: 1\nselector_digests:", "unsupported fields"),
        (
            f"  line-a: {_DIGEST_A}\n  line-b",
            f"  line-b: {_DIGEST_B}\n  line-a: {_DIGEST_A}\n  line-x",
            "sorted",
        ),
        (f"  line-c: {_DIGEST_C}\n", "", "line-c has no selector_digests entry"),
        (f"  line-c: {_DIGEST_C}\n", f"  line-c: {_DIGEST_C}\n  line-d: {_DIGEST_C}\n", "unused"),
        (f"line-a: {_DIGEST_A}", "line-a: not-a-digest", "sha256"),
        ("pair: uk-shropshire/manual", "pair: uk-shropshire", "jurisdiction/document_class"),
        ("pair: uk-shropshire/manual", "pair: uk-shropshire/leaflet", "document_class"),
        (
            "    listed_on: 2026-11-02\n    reason: >-",
            "    listed_on: soon\n    reason: >-",
            "ISO date",
        ),
        ("    reason: >-\n      Retired by omission.\n", "", "missing ['reason']"),
        (
            "    predecessor: line-a\n    pair",
            "    predecessor: line-b\n    pair",
            "cannot succeed itself",
        ),
        ("      - line-b\n      - line-c", "      - line-c\n      - line-b", "sorted"),
        ("      - line-b\n      - line-c", "      - line-b", "at least two"),
        ("    reason: The line splits.", "    note: The line splits.", "must have exactly"),
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
    ],
)
def test_a_malformed_baseline_is_refused(tmp_path: Path, old: str, new: str, message: str) -> None:
    assert old in _VALID, old
    with pytest.raises(SelectorLineageError, match=message.replace("[", r"\[").replace("]", r"\]")):
        load_lineage_baseline(_write(tmp_path, _VALID.replace(old, new, 1)))


def test_a_duplicate_drop_record_is_refused(tmp_path: Path) -> None:
    drop = _VALID.split("dropped_pairs:\n", 1)[1].split("forks:", 1)[0]
    text = _VALID.replace(drop, drop + drop, 1)
    with pytest.raises(
        SelectorLineageError, match="dropped_pairs .* sorted and free of duplicates"
    ):
        load_lineage_baseline(_write(tmp_path, text))
