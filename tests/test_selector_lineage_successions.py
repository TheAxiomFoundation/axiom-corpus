"""Recorded prose successions obey the same lineage rules as named edges.

Invariants: each selector has at most one effective predecessor; shuffling
selector files or mappings cannot change findings; a complete line exposes a
new cut from an older base and names its newest cut; named predecessors take
precedence over records; changing either pinned endpoint invalidates a record.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import selector_lineage as lineage
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.release.manifest import selector_sha256

_SETTINGS = settings(max_examples=150, deadline=None)
_SCOPE = ReleaseScope("uk", "statute", "2026-08-07")


def _selector(name: str, predecessor: str | None = None) -> ReleaseManifest:
    description = (
        f"Successor to {predecessor}."
        if predecessor is not None
        else "Earlier scope set plus the additional provisions."
    )
    return ReleaseManifest(name=name, scopes=(_SCOPE,), description=description)


def _record(selector: str, predecessor: str) -> Any:
    # Resolve lazily so the initial red run reports each missing behavior,
    # rather than stopping the entire module at import time.
    return lineage.RecordedSuccession(
        selector, predecessor, "2026-11-05", 'Description says "Earlier scope set plus".'
    )


def _baseline(
    selectors: Iterable[ReleaseManifest],
    parents: dict[str, str],
    *,
    roots: Iterable[str] = (),
    first_cuts: Iterable[str] = (),
    forks: dict[str, tuple[lineage.RecordedFork, ...]] | None = None,
) -> lineage.LineageBaseline:
    selected = tuple(selectors)
    successions = {name: _record(name, parent) for name, parent in sorted(parents.items())}
    for cut in selected:
        if cut.name in successions and (cut.description or "").startswith("Successor to "):
            # Isolate named precedence: valid quoted evidence must not mask an
            # incorrectly accepted record by failing a different validation.
            successions[cut.name] = replace(
                successions[cut.name], reason=f'Description says "{cut.description}".'
            )
    return lineage.LineageBaseline(
        selector_digests={cut.name: selector_sha256(cut) for cut in selected},
        first_cuts={
            name: lineage.RecordedFirstCut(name, "2026-11-02", "Historical first-cut claim.")
            for name in sorted({*roots, *first_cuts})
        },
        forks=forks or {},
        successions=successions,
    )


def _check(
    selectors: Iterable[ReleaseManifest], baseline: lineage.LineageBaseline
) -> lineage.LineageReport:
    return lineage.check_selector_lineage({cut.name: cut for cut in selectors}, baseline)


def _data(selectors: list[ReleaseManifest], parents: dict[str, str]) -> dict[str, Any]:
    children = set(parents)
    return {
        "schema_version": lineage.LINEAGE_BASELINE_SCHEMA,
        "selector_digests": {
            cut.name: selector_sha256(cut) for cut in sorted(selectors, key=lambda cut: cut.name)
        },
        "first_cuts": [
            {
                "selectors": sorted(cut.name for cut in selectors if cut.name not in children),
                "listed_on": "2026-11-02",
                "reason": "The original first cut.",
            }
        ],
        "successions": [
            {
                "selector": name,
                "predecessor": parent,
                "listed_on": "2026-11-05",
                "reason": 'Description says "Earlier scope set plus".',
            }
            for name, parent in sorted(parents.items())
        ],
    }


def _write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _write_selector(directory: Path, selector: ReleaseManifest) -> None:
    directory.mkdir(exist_ok=True)
    (directory / f"{selector.name}.json").write_text(
        json.dumps(
            {
                "name": selector.name,
                "description": selector.description,
                "scopes": [
                    {
                        "jurisdiction": scope.jurisdiction,
                        "document_class": scope.document_class,
                        "version": scope.version,
                    }
                    for scope in selector.scopes
                ],
            }
        ),
        encoding="utf-8",
    )


def test_recorded_edges_check_dropped_pairs_and_supersede_old_first_cut_claims() -> None:
    root = _selector("line-root")
    cut = replace(
        _selector("line-cut"),
        scopes=(ReleaseScope("de", "statute", "2026-08-08"),),
    )
    baseline = _baseline(
        [root, cut], {cut.name: root.name}, roots=[root.name], first_cuts=[cut.name]
    )
    report = _check([root, cut], baseline)

    assert report.predecessors == {root.name: None, cut.name: root.name}
    assert report.dropped == (
        lineage.DroppedPair(cut.name, root.name, ("uk", "statute"), ("2026-08-07",)),
    )
    assert report.baseline_errors == ()
    assert report.recorded_first_cuts == (root.name,)
    assert report.unnamed == ()


def test_recorded_edges_extend_ended_branches_and_find_the_continued_head() -> None:
    root, kept, ended, head, extension = [
        _selector(name)
        for name in ["line-root", "line-kept", "line-ended", "line-head", "line-extension"]
    ]
    cuts = [root, kept, ended, head, extension]
    parents = {
        kept.name: root.name,
        ended.name: root.name,
        head.name: kept.name,
        extension.name: ended.name,
    }
    fork = lineage.RecordedFork(
        root.name,
        tuple(sorted([kept.name, ended.name])),
        (kept.name,),
        "2026-11-05",
        "Continues the kept branch.",
    )
    baseline = _baseline(cuts, parents, roots=[root.name], forks={root.name: (fork,)})
    report = _check(cuts, baseline)

    assert report.ended_branches == (
        lineage.EndedBranch(extension.name, ended.name, root.name, (kept.name,), (head.name,)),
    )
    assert report.forks == ()


def test_a_later_succession_replaces_a_historical_first_cut_without_stale_error() -> None:
    root, cut = _selector("line-root"), _selector("line-cut")
    baseline = _baseline(
        [root, cut], {cut.name: root.name}, roots=[root.name], first_cuts=[cut.name]
    )
    report = _check([root, cut], baseline)

    assert report.ok, report.problems()
    assert report.recorded_first_cuts == (root.name,)
    assert report.predecessors[cut.name] == root.name
    assert cut.name in baseline.first_cuts


@pytest.mark.parametrize("endpoint", ["line-root", "line-cut"])
def test_an_edited_succession_endpoint_fails_with_actionable_guidance(endpoint: str) -> None:
    root, cut = _selector("line-root"), _selector("line-cut")
    cuts = [root, cut]
    baseline = _baseline(cuts, {cut.name: root.name}, roots=[root.name])
    changed = [
        replace(item, scopes=(replace(_SCOPE, version="2026-11-05"),))
        if item.name == endpoint
        else item
        for item in cuts
    ]
    report = _check(changed, baseline)

    assert not report.ok
    assert any(endpoint in error and "undo" in error.lower() for error in report.baseline_errors)


def test_a_named_predecessor_is_never_overridden_and_its_record_must_be_removed() -> None:
    named, recorded = _selector("line-named"), _selector("line-recorded")
    cut = _selector("line-cut", named.name)
    baseline = _baseline(
        [named, recorded, cut], {cut.name: recorded.name}, roots=[named.name, recorded.name]
    )
    report = _check([named, recorded, cut], baseline)

    assert report.predecessors[cut.name] == named.name
    assert not report.ok
    assert any(
        "remove" in error.lower() and "succession" in error.lower()
        for error in report.baseline_errors
    )


def test_even_a_record_matching_the_named_predecessor_is_an_error() -> None:
    root = _selector("line-root")
    cut = _selector("line-cut", root.name)
    baseline = _baseline([root, cut], {cut.name: root.name}, roots=[root.name])
    report = _check([root, cut], baseline)

    assert report.predecessors[cut.name] == root.name
    assert not report.ok
    assert any(
        "remove" in error.lower() and "succession" in error.lower()
        for error in report.baseline_errors
    )


def test_the_loader_reads_successions_and_resolves_sibling_selector_files(tmp_path: Path) -> None:
    root, cut = _selector("line-root"), _selector("line-cut")
    cuts = [root, cut]
    for selector in cuts:
        _write_selector(tmp_path / "releases", selector)
    path = _write(tmp_path / "selector-lineage-baseline.yaml", _data(cuts, {cut.name: root.name}))
    baseline = lineage.load_lineage_baseline(path)

    assert baseline.successions == {cut.name: _record(cut.name, root.name)}
    assert _check(cuts, baseline).ok


@pytest.mark.parametrize("missing", ["line-root", "line-cut"])
def test_a_succession_with_no_endpoint_selector_file_fails_to_load(
    tmp_path: Path, missing: str
) -> None:
    root, cut = _selector("line-root"), _selector("line-cut")
    cuts = [root, cut]
    for selector in cuts:
        if selector.name != missing:
            _write_selector(tmp_path / "releases", selector)
    path = _write(tmp_path / "selector-lineage-baseline.yaml", _data(cuts, {cut.name: root.name}))

    with pytest.raises(lineage.SelectorLineageError, match=missing):
        lineage.load_lineage_baseline(path)


@pytest.mark.parametrize("mixed", [False, True])
def test_a_recorded_or_mixed_cycle_fails_to_load(tmp_path: Path, mixed: bool) -> None:
    left = _selector("line-left", "line-right" if mixed else None)
    right = _selector("line-right")
    cuts = [left, right]
    parents = {right.name: left.name}
    if not mixed:
        parents[left.name] = right.name
    data = _data(cuts, parents)
    data["first_cuts"] = []
    path = _write(tmp_path / "baseline.yaml", data)

    with pytest.raises(lineage.SelectorLineageError, match="cycle"):
        lineage.load_lineage_baseline(path, selectors={cut.name: cut for cut in cuts})


@pytest.mark.parametrize("listed_on", ["2026-11-01", "2026-11-02"])
def test_a_succession_must_postdate_the_first_cut_claim_it_replaces(
    tmp_path: Path, listed_on: str
) -> None:
    root, cut = _selector("line-root"), _selector("line-cut")
    cuts = [root, cut]
    data = _data(cuts, {cut.name: root.name})
    data["first_cuts"][0]["selectors"] = sorted([root.name, cut.name])
    data["successions"][0]["listed_on"] = listed_on
    path = _write(tmp_path / "baseline.yaml", data)

    with pytest.raises(lineage.SelectorLineageError, match="later|after|postdate"):
        lineage.load_lineage_baseline(path, selectors={item.name: item for item in cuts})


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing-selector", "missing"),
        ("missing-predecessor", "missing"),
        ("missing-listed-on", "missing"),
        ("missing-reason", "missing"),
        ("extra-field", "unsupported"),
        ("empty-reason", "non-empty"),
        ("invalid-date", "ISO date"),
        ("selector-unpinned", "selector_digests"),
        ("predecessor-unpinned", "selector_digests"),
        ("duplicate", "duplicate|twice|already"),
        ("self", "itself|cycle"),
        ("unsorted", "sorted"),
        ("not-list", "list"),
    ],
)
def test_the_loader_rejects_malformed_successions(tmp_path: Path, case: str, message: str) -> None:
    root, cut = _selector("line-root"), _selector("line-cut")
    cuts = [root, cut]
    data = _data(cuts, {cut.name: root.name})
    record = data["successions"][0]
    if case.startswith("missing-"):
        del record[case.removeprefix("missing-").replace("-", "_")]
    elif case == "extra-field":
        record["unexpected"] = True
    elif case == "empty-reason":
        record["reason"] = " "
    elif case == "invalid-date":
        record["listed_on"] = "yesterday"
    elif case.endswith("-unpinned"):
        del data["selector_digests"][record[case.removesuffix("-unpinned")]]
    elif case == "duplicate":
        data["successions"].append(dict(record))
    elif case == "self":
        record["predecessor"] = cut.name
    elif case == "unsorted":
        later = _selector("line-z")
        cuts.append(later)
        data = _data(cuts, {cut.name: root.name, later.name: root.name})
        data["successions"].reverse()
    elif case == "not-list":
        data["successions"] = {}
    path = _write(tmp_path / "baseline.yaml", data)

    with pytest.raises(lineage.SelectorLineageError, match=message):
        lineage.load_lineage_baseline(path, selectors={item.name: item for item in cuts})


@_SETTINGS
@given(
    parents=st.lists(st.one_of(st.none(), st.integers(min_value=0)), min_size=2, max_size=10),
    recorded=st.lists(st.booleans(), min_size=10, max_size=10),
    data=st.data(),
)
def test_one_predecessor_and_findings_are_invariant_under_file_order(
    parents: list[int | None], recorded: list[bool], data: st.DataObject
) -> None:
    cuts: list[ReleaseManifest] = []
    expected: dict[str, str | None] = {}
    successions: dict[str, str] = {}
    roots: list[str] = []
    for index, raw_parent in enumerate(parents):
        name = f"tree-cut-{index}"
        parent = None if index == 0 or raw_parent is None else cuts[raw_parent % index].name
        cuts.append(_selector(name, None if recorded[index] else parent))
        expected[name] = parent
        if parent is None:
            roots.append(name)
        elif recorded[index]:
            successions[name] = parent
    baseline = _baseline(cuts, successions, roots=roots)
    expected_report = _check(cuts, baseline)
    shuffled = list(data.draw(st.permutations(cuts)))
    assert expected_report.predecessors == expected
    assert _check(shuffled, baseline) == expected_report
    # File creation and filesystem traversal order also cannot change the result.
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        for cut in shuffled:
            _write_selector(directory / "releases", cut)
        loaded = lineage.load_tracked_selectors(directory / "releases")
        assert lineage.check_selector_lineage(loaded, baseline) == expected_report


@_SETTINGS
@given(length=st.integers(min_value=2, max_value=10), data=st.data())
def test_a_cut_from_any_recorded_old_base_reports_the_newest_head(
    length: int, data: st.DataObject
) -> None:
    cuts = [_selector(f"line-cut-{index}") for index in range(length)]
    parents = {cuts[index].name: cuts[index - 1].name for index in range(1, length)}
    baseline = _baseline(
        cuts, parents, roots=[cuts[0].name], first_cuts=[cut.name for cut in cuts[1:]]
    )
    old = data.draw(st.integers(min_value=0, max_value=length - 2))
    stale = _selector("line-stale-copy", cuts[old].name)
    report = _check([*cuts, stale], baseline)

    assert report.forks or report.ended_branches
    relevant = [finding for finding in report.forks if finding.predecessor == cuts[old].name]
    assert len(relevant) == 1
    assert cuts[old + 1].name in relevant[0].successors
    assert stale.name in relevant[0].successors
    assert cuts[-1].name in relevant[0].heads


@_SETTINGS
@given(
    parent_index=st.integers(min_value=0, max_value=5),
    recorded_index=st.integers(min_value=0, max_value=5),
)
def test_named_beats_recorded_for_every_generated_choice(
    parent_index: int, recorded_index: int
) -> None:
    roots = [_selector(f"line-root-{index}") for index in range(6)]
    cut = _selector("line-cut", roots[parent_index].name)
    baseline = _baseline(
        [*roots, cut], {cut.name: roots[recorded_index].name}, roots=[root.name for root in roots]
    )
    report = _check([*roots, cut], baseline)

    assert report.predecessors[cut.name] == roots[parent_index].name
    assert not report.ok
    assert any(
        "remove" in error.lower() and "succession" in error.lower()
        for error in report.baseline_errors
    )


@_SETTINGS
@given(
    endpoint=st.sampled_from(["line-root", "line-cut"]),
    version=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=20),
)
def test_every_changed_endpoint_invalidates_its_pinned_succession(
    endpoint: str, version: str
) -> None:
    root, cut = _selector("line-root"), _selector("line-cut")
    baseline = _baseline([root, cut], {cut.name: root.name}, roots=[root.name])
    cuts = [
        replace(item, scopes=(replace(_SCOPE, version=version),)) if item.name == endpoint else item
        for item in [root, cut]
    ]
    report = _check(cuts, baseline)

    assert not report.ok
    assert any(endpoint in error and "undo" in error.lower() for error in report.baseline_errors)
