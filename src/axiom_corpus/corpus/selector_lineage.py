"""Selector lineage: each cut names its predecessor and keeps every pair it carries.

Tracked selectors under ``manifests/releases/`` are cut as lines: each cut
names the selector it succeeds and carries its scopes forward. Two consumers
take a release whole or by ``(jurisdiction, document_class)`` pair. A rules
repository pins one release at a time and reads only what that release
selects. Activation repoints, for each pair the release carries, the pair's
serving pointer to the release, so the pair serves exactly the versions that
release selects; pairs it does not carry keep their release
(``corpus.activate_corpus_release``, ``corpus.current_release_scopes``). A cut
derived from a superseded base therefore drops what the newer cuts of its line
added, and whichever release is pinned or activated last decides what remains
(axiom-corpus#935).

This module checks, from the selector files alone:

``dropped_pair``
    The selector selects no version of a pair its predecessor selects: the
    pair's last version leaves the line, and nothing in the same pair replaces
    it.
``fork``
    Two or more selectors name the same predecessor. At most one of them can be
    the newest cut of the line; the others were cut from a base that another
    cut had already superseded, which is how the 2026-10-25 cuts diverged.
``ended_branch``
    The selector names a successor of a recorded fork that the line did not
    continue through, so it extends a branch no cut follows.
``unnamed_predecessor``
    The description names no tracked selector, and no record says the selector
    is the first cut of a line, so nothing would be compared with it.
``cycle``
    Selectors name each other as predecessors, so their line has no first cut.

The comparison is per pair. A pair the successor still carries, with any of its
versions, is not a drop, so one document can leave a pair the successor keeps
without a finding. The activation gate's ``scope_monotonicity`` check
(``scripts/check_release_gate.py``) compares only a pair's newest version, so
it does not report that case either.

A selector's predecessor is the first tracked selector its description names
("Successor to <name>", "after <name>", "<name>'s scope set"). On ``main``,
every selector that names another tracked selector names its predecessor first.

``manifests/selector-lineage-baseline.yaml`` records the drops, forks and first
cuts a release decision allows, each pinned to the digest
(``axiom_corpus.release.manifest.selector_sha256``) of every selector it names,
so a record holds only for those exact selectors. A drop record names the
scopes that carry the pair's text in its place (``replaced_by``), or says in
its reason why nothing does. A fork record lists every successor and the ones
the line continued through. The entries listed on 2026-11-02 are what ``main``
held when the check began.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.releases import (
    ReleaseManifest,
    ReleaseScope,
    ScopeKey,
    validate_release_name,
)
from axiom_corpus.release.manifest import selector_sha256

LINEAGE_BASELINE_PATH = Path("manifests") / "selector-lineage-baseline.yaml"
LINEAGE_BASELINE_SCHEMA = "axiom-corpus/selector-lineage-baseline/v1"

Pair = tuple[str, str]

# A run of the characters a release name may hold (lowercase alphanumeric
# segments joined by single hyphens, axiom_corpus.corpus.releases), so a name
# followed by "'s", a comma or a period still reads as that name.
_NAME_RUN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SHA256 = re.compile(r"[0-9a-f]{64}")

_BASELINE_FIELDS = {
    "schema_version",
    "selector_digests",
    "dropped_pairs",
    "forks",
    "first_cuts",
}
_DROP_FIELDS = {"selector", "predecessor", "pair", "listed_on", "reason", "replaced_by"}
_DROP_REQUIRED = {"selector", "predecessor", "pair", "listed_on", "reason"}
_FORK_FIELDS = {"predecessor", "successors", "continued_by", "listed_on", "reason"}
_FIRST_CUT_FIELDS = {"selectors", "listed_on", "reason"}


class SelectorLineageError(ValueError):
    """The selector lineage baseline is malformed."""


def pair_label(pair: Pair) -> str:
    return "/".join(pair)


def pair_versions(release: ReleaseManifest) -> dict[Pair, frozenset[str]]:
    """Each ``(jurisdiction, document_class)`` pair the selector carries, with its versions."""
    grouped: dict[Pair, set[str]] = defaultdict(set)
    for scope in release.scopes:
        grouped[(scope.jurisdiction, scope.document_class)].add(scope.version)
    return {pair: frozenset(versions) for pair, versions in grouped.items()}


def declared_predecessor(release: ReleaseManifest, tracked: Collection[str]) -> str | None:
    """The first tracked selector other than ``release`` that its description names."""
    for match in _NAME_RUN.finditer(release.description or ""):
        name = match.group(0)
        if name != release.name and name in tracked:
            return name
    return None


def dropped_pairs(
    predecessor: ReleaseManifest, successor: ReleaseManifest
) -> dict[Pair, frozenset[str]]:
    """Pairs ``predecessor`` carries and ``successor`` has no version of.

    Each maps to the predecessor's versions of the pair, all of which the
    successor drops.
    """
    kept = pair_versions(successor)
    return {
        pair: versions for pair, versions in pair_versions(predecessor).items() if pair not in kept
    }


def lineage_cycles(predecessors: Mapping[str, str | None]) -> tuple[tuple[str, ...], ...]:
    """Each cycle of selectors that name each other as predecessors, sorted, once."""
    cycles: set[tuple[str, ...]] = set()
    settled: set[str] = set()
    for start in sorted(predecessors):
        path: list[str] = []
        position: dict[str, int] = {}
        node: str | None = start
        while node is not None and node not in settled and node not in position:
            position[node] = len(path)
            path.append(node)
            node = predecessors.get(node)
        if node is not None and node in position:
            cycles.add(tuple(sorted(path[position[node] :])))
        settled.update(path)
    return tuple(sorted(cycles))


@dataclass(frozen=True)
class DroppedPair:
    """A pair whose last version leaves the line at ``selector``."""

    selector: str
    predecessor: str
    pair: Pair
    versions: tuple[str, ...]

    def describe(self) -> str:
        versions = ", ".join(f"{pair_label(self.pair)}/{version}" for version in self.versions)
        return (
            f"{self.selector} selects no {pair_label(self.pair)} scope, which its predecessor "
            f"{self.predecessor} carries ({versions})"
        )


@dataclass(frozen=True)
class Fork:
    """A predecessor that more than one selector names."""

    predecessor: str
    successors: tuple[str, ...]

    def describe(self) -> str:
        return (
            f"{len(self.successors)} selectors name {self.predecessor} as their predecessor "
            f"({', '.join(self.successors)}): at most one can be the newest cut of the line, "
            "and whichever is pinned or activated last drops what the others add"
        )


@dataclass(frozen=True)
class EndedBranch:
    """A selector that extends a fork's branch the line did not continue through."""

    selector: str
    predecessor: str
    fork: str
    continued_by: tuple[str, ...]

    def describe(self) -> str:
        return (
            f"{self.selector} names {self.predecessor}, a branch of the fork at {self.fork} "
            f"that the line did not continue: it continued through "
            f"{', '.join(self.continued_by)}"
        )


@dataclass(frozen=True)
class UnnamedPredecessor:
    """A selector compared with nothing: no predecessor named, no first-cut record."""

    selector: str

    def describe(self) -> str:
        return (
            f"{self.selector} names no tracked selector in its description, and no record "
            "says it is the first cut of a line, so nothing is compared with it"
        )


@dataclass(frozen=True)
class Cycle:
    """Selectors that name each other as predecessors."""

    selectors: tuple[str, ...]

    def describe(self) -> str:
        return (
            f"{', '.join(self.selectors)} name each other as predecessors, so their line "
            "has no first cut"
        )


@dataclass(frozen=True)
class RecordedDrop:
    selector: str
    predecessor: str
    pair: Pair
    listed_on: str
    reason: str
    replaced_by: tuple[ScopeKey, ...] = ()


@dataclass(frozen=True)
class RecordedFork:
    predecessor: str
    successors: tuple[str, ...]
    continued_by: tuple[str, ...]
    listed_on: str
    reason: str


@dataclass(frozen=True)
class RecordedFirstCut:
    selector: str
    listed_on: str
    reason: str


@dataclass(frozen=True)
class LineageBaseline:
    """The drops, forks and first cuts a release decision allows, pinned to selector digests."""

    selector_digests: Mapping[str, str] = field(default_factory=dict)
    drops: Mapping[tuple[str, Pair], RecordedDrop] = field(default_factory=dict)
    forks: Mapping[str, RecordedFork] = field(default_factory=dict)
    first_cuts: Mapping[str, RecordedFirstCut] = field(default_factory=dict)

    @classmethod
    def load(cls, repo_root: str | Path) -> LineageBaseline:
        """The checkout's baseline; a checkout without the file records nothing."""
        path = Path(repo_root) / LINEAGE_BASELINE_PATH
        return load_lineage_baseline(path) if path.exists() else cls()


@dataclass(frozen=True)
class LineageReport:
    """What the check found across a set of tracked selectors.

    ``dropped``, ``forks``, ``ended_branches``, ``unnamed`` and ``cycles`` are
    the findings no record allows, and ``baseline_errors`` the records that no
    longer hold; any of them fails the check. ``recorded_drops``,
    ``recorded_forks`` and ``recorded_first_cuts`` are allowed by the baseline.
    """

    predecessors: Mapping[str, str | None]
    dropped: tuple[DroppedPair, ...] = ()
    forks: tuple[Fork, ...] = ()
    ended_branches: tuple[EndedBranch, ...] = ()
    unnamed: tuple[UnnamedPredecessor, ...] = ()
    cycles: tuple[Cycle, ...] = ()
    recorded_drops: tuple[DroppedPair, ...] = ()
    recorded_forks: tuple[Fork, ...] = ()
    recorded_first_cuts: tuple[str, ...] = ()
    baseline_errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.problems()

    @property
    def roots(self) -> tuple[str, ...]:
        """Selectors that name no tracked predecessor, so nothing is compared with them."""
        return tuple(sorted(name for name, prior in self.predecessors.items() if prior is None))

    def problems(self) -> list[str]:
        return [
            *(finding.describe() for finding in self.dropped),
            *(fork.describe() for fork in self.forks),
            *(branch.describe() for branch in self.ended_branches),
            *(unnamed.describe() for unnamed in self.unnamed),
            *(cycle.describe() for cycle in self.cycles),
            *self.baseline_errors,
        ]


def check_selector_lineage(
    selectors: Mapping[str, ReleaseManifest],
    baseline: LineageBaseline | None = None,
) -> LineageReport:
    """Compare every selector with its declared predecessor, and check the line's shape.

    ``selectors`` maps each tracked selector's name to its manifest; a name
    must equal its manifest's name.
    """
    baseline = baseline or LineageBaseline()
    for name, release in selectors.items():
        if release.name != name:
            raise ValueError(f"selector {name!r} holds a manifest named {release.name!r}")
    names = frozenset(selectors)
    predecessors = {
        name: declared_predecessor(release, names) for name, release in sorted(selectors.items())
    }
    errors: list[str] = []
    pinned: set[str] = set()
    for name, digest in sorted(baseline.selector_digests.items()):
        tracked = selectors.get(name)
        if tracked is None:
            errors.append(f"the baseline pins {name}, which is not a tracked selector")
        elif selector_sha256(tracked) != digest:
            errors.append(
                f"the baseline pins {name} at {digest}, but the selector's digest is "
                f"{selector_sha256(tracked)}; its records no longer hold"
            )
        else:
            pinned.add(name)

    dropped: list[DroppedPair] = []
    recorded_drops: list[DroppedPair] = []
    matched_drops: set[tuple[str, Pair]] = set()
    for name, predecessor in predecessors.items():
        if predecessor is None:
            continue
        lost = dropped_pairs(selectors[predecessor], selectors[name])
        for pair in sorted(lost):
            finding = DroppedPair(name, predecessor, pair, tuple(sorted(lost[pair])))
            record = baseline.drops.get((name, pair))
            if (
                record is not None
                and record.predecessor == predecessor
                and {name, predecessor} <= pinned
                and set(record.replaced_by) <= set(selectors[name].scope_keys)
            ):
                matched_drops.add((name, pair))
                recorded_drops.append(finding)
            else:
                dropped.append(finding)
    for key, record in sorted(baseline.drops.items()):
        if key in matched_drops:
            continue
        name, pair = key
        recorded = selectors.get(name)
        prior = selectors.get(record.predecessor)
        if recorded is None or prior is None:
            continue  # already reported: the baseline pins a selector that is not tracked
        missing = sorted(set(record.replaced_by) - set(recorded.scope_keys))
        if missing:
            errors.append(
                f"the baseline names {', '.join('/'.join(scope) for scope in missing)} as "
                f"replacing {pair_label(pair)} in {name}, which does not select it"
            )
        elif predecessors.get(name) != record.predecessor:
            errors.append(
                f"the baseline records {name} dropping {pair_label(pair)} from "
                f"{record.predecessor}, but {name} names "
                f"{predecessors.get(name) or 'no tracked selector'} as its predecessor"
            )
        elif pair not in dropped_pairs(prior, recorded):
            errors.append(
                f"the baseline records {name} dropping {pair_label(pair)} from "
                f"{record.predecessor}, but it does not drop that pair"
            )

    successors: dict[str, list[str]] = defaultdict(list)
    for name, predecessor in predecessors.items():
        if predecessor is not None:
            successors[predecessor].append(name)
    forks: list[Fork] = []
    recorded_forks: list[Fork] = []
    for predecessor, names_of in sorted(successors.items()):
        if len(names_of) < 2:
            continue
        fork = Fork(predecessor, tuple(sorted(names_of)))
        fork_record = baseline.forks.get(predecessor)
        if (
            fork_record is not None
            and fork_record.successors == fork.successors
            and {predecessor, *fork.successors} <= pinned
        ):
            recorded_forks.append(fork)
        else:
            forks.append(fork)
    ended_branches: list[EndedBranch] = []
    for predecessor, fork_record in sorted(baseline.forks.items()):
        actual = tuple(sorted(successors.get(predecessor, ())))
        if len(actual) < 2:
            errors.append(
                f"the baseline records a fork at {predecessor} "
                f"({', '.join(fork_record.successors)}), but "
                f"{len(actual)} tracked selector(s) name it as their predecessor"
            )
        elif actual != fork_record.successors:
            errors.append(
                f"the baseline records {', '.join(fork_record.successors)} as the successors "
                f"of {predecessor}, but {', '.join(actual)} name it"
            )
        for branch in sorted(set(fork_record.successors) - set(fork_record.continued_by)):
            for extension in sorted(successors.get(branch, ())):
                ended_branches.append(
                    EndedBranch(extension, branch, predecessor, fork_record.continued_by)
                )

    unnamed: list[UnnamedPredecessor] = []
    recorded_first_cuts: list[str] = []
    for name, predecessor in predecessors.items():
        if predecessor is not None:
            continue
        if name in baseline.first_cuts and name in pinned:
            recorded_first_cuts.append(name)
        else:
            unnamed.append(UnnamedPredecessor(name))
    for name in sorted(baseline.first_cuts):
        if name in selectors and predecessors[name] is not None:
            errors.append(
                f"the baseline records {name} as the first cut of a line, but its "
                f"description names {predecessors[name]}"
            )

    return LineageReport(
        predecessors=predecessors,
        dropped=tuple(dropped),
        forks=tuple(forks),
        ended_branches=tuple(ended_branches),
        unnamed=tuple(unnamed),
        cycles=tuple(Cycle(members) for members in lineage_cycles(predecessors)),
        recorded_drops=tuple(recorded_drops),
        recorded_forks=tuple(recorded_forks),
        recorded_first_cuts=tuple(recorded_first_cuts),
        baseline_errors=tuple(errors),
    )


def load_tracked_selectors(releases_dir: str | Path) -> dict[str, ReleaseManifest]:
    """Every ``<name>.json`` selector in ``releases_dir``, keyed by name."""
    selectors: dict[str, ReleaseManifest] = {}
    for path in sorted(Path(releases_dir).glob("*.json")):
        release = ReleaseManifest.load(path)
        if release.name != path.stem:
            raise ValueError(f"{path} holds a selector named {release.name!r}")
        selectors[release.name] = release
    return selectors


def _mapping(value: object, where: str) -> Mapping[Any, Any]:
    if not isinstance(value, Mapping):
        raise SelectorLineageError(f"{where} must be a mapping")
    return value


def _fields(item: Mapping[Any, Any], allowed: set[str], where: str) -> None:
    extra = set(item) - allowed
    if extra:
        # YAML can read a key as a number or a date, so sort by text.
        raise SelectorLineageError(f"{where}: unsupported fields {sorted(extra, key=str)}")


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SelectorLineageError(f"{where} must be a non-empty string")
    return " ".join(value.split())


def _name(value: object, where: str) -> str:
    text = _text(value, where)
    try:
        return validate_release_name(text)
    except ValueError as exc:
        raise SelectorLineageError(f"{where}: {exc}") from exc


def _digest(value: object, where: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise SelectorLineageError(f"{where} must be a lowercase hex sha256")
    return value


def _iso_date(value: object, where: str) -> str:
    text = value.isoformat() if isinstance(value, date) else value
    if not isinstance(text, str):
        raise SelectorLineageError(f"{where} must be an ISO date")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise SelectorLineageError(f"{where} must be an ISO date") from exc


def _pair(value: object, where: str) -> Pair:
    text = _text(value, where)
    parts = text.split("/")
    if len(parts) != 2:
        raise SelectorLineageError(f"{where} must be jurisdiction/document_class")
    try:
        ReleaseScope(parts[0], parts[1], "pair-check")
    except ValueError as exc:
        raise SelectorLineageError(f"{where}: {exc}") from exc
    return (parts[0], parts[1])


def _scope(value: object, where: str) -> ScopeKey:
    text = _text(value, where)
    parts = text.split("/", 2)
    if len(parts) != 3:
        raise SelectorLineageError(f"{where} must be jurisdiction/document_class/version")
    try:
        return ReleaseScope(*parts).key
    except ValueError as exc:
        raise SelectorLineageError(f"{where}: {exc}") from exc


def _list(value: object, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise SelectorLineageError(f"{where} must be a list")
    return value


def _sorted_unique(values: Iterable[Any], where: str) -> None:
    items = list(values)
    if items != sorted(items) or len(set(items)) != len(items):
        raise SelectorLineageError(f"{where} must be sorted and free of duplicates")


def load_lineage_baseline(path: str | Path) -> LineageBaseline:
    """Parse ``manifests/selector-lineage-baseline.yaml``; reject anything malformed."""
    where = str(path)
    data = _mapping(yaml.safe_load(Path(path).read_text(encoding="utf-8")), where)
    _fields(data, _BASELINE_FIELDS, where)
    if data.get("schema_version") != LINEAGE_BASELINE_SCHEMA:
        raise SelectorLineageError(f"{where}: schema_version must be {LINEAGE_BASELINE_SCHEMA}")
    digests = {
        _name(name, f"{where}: selector_digests"): _digest(
            digest, f"{where}: selector_digests.{name}"
        )
        for name, digest in _mapping(
            data.get("selector_digests") or {}, f"{where}: selector_digests"
        ).items()
    }
    _sorted_unique(digests, f"{where}: selector_digests")
    named: set[str] = set()

    def pinned_name(value: object, entry_where: str) -> str:
        name = _name(value, entry_where)
        if name not in digests:
            raise SelectorLineageError(f"{entry_where}: {name} has no selector_digests entry")
        named.add(name)
        return name

    drops: dict[tuple[str, Pair], RecordedDrop] = {}
    drop_keys: list[tuple[str, Pair]] = []
    for index, raw in enumerate(_list(data.get("dropped_pairs") or [], f"{where}: dropped_pairs")):
        entry_where = f"{where}: dropped_pairs[{index}]"
        item = _mapping(raw, entry_where)
        _fields(item, _DROP_FIELDS, entry_where)
        missing = _DROP_REQUIRED - set(item)
        if missing:
            raise SelectorLineageError(f"{entry_where}: missing {sorted(missing)}")
        replaced_by = tuple(
            _scope(value, f"{entry_where}.replaced_by[{position}]")
            for position, value in enumerate(
                _list(item.get("replaced_by") or [], f"{entry_where}.replaced_by")
            )
        )
        _sorted_unique(replaced_by, f"{entry_where}.replaced_by")
        record = RecordedDrop(
            selector=pinned_name(item["selector"], f"{entry_where}.selector"),
            predecessor=pinned_name(item["predecessor"], f"{entry_where}.predecessor"),
            pair=_pair(item["pair"], f"{entry_where}.pair"),
            listed_on=_iso_date(item["listed_on"], f"{entry_where}.listed_on"),
            reason=_text(item["reason"], f"{entry_where}.reason"),
            replaced_by=replaced_by,
        )
        if record.selector == record.predecessor:
            raise SelectorLineageError(f"{entry_where}: a selector cannot succeed itself")
        drop_keys.append((record.selector, record.pair))
        drops[(record.selector, record.pair)] = record
    _sorted_unique(drop_keys, f"{where}: dropped_pairs (by selector, then pair)")

    forks: dict[str, RecordedFork] = {}
    fork_keys: list[str] = []
    for index, raw in enumerate(_list(data.get("forks") or [], f"{where}: forks")):
        entry_where = f"{where}: forks[{index}]"
        item = _mapping(raw, entry_where)
        if set(item) != _FORK_FIELDS:
            raise SelectorLineageError(f"{entry_where} must have exactly {sorted(_FORK_FIELDS)}")
        fork_successors = tuple(
            pinned_name(value, f"{entry_where}.successors[{position}]")
            for position, value in enumerate(_list(item["successors"], f"{entry_where}.successors"))
        )
        if len(fork_successors) < 2:
            raise SelectorLineageError(f"{entry_where}.successors must list at least two selectors")
        _sorted_unique(fork_successors, f"{entry_where}.successors")
        continued_by = tuple(
            _name(value, f"{entry_where}.continued_by[{position}]")
            for position, value in enumerate(
                _list(item["continued_by"], f"{entry_where}.continued_by")
            )
        )
        _sorted_unique(continued_by, f"{entry_where}.continued_by")
        if not continued_by or not set(continued_by) <= set(fork_successors):
            raise SelectorLineageError(
                f"{entry_where}.continued_by must name at least one of its successors, "
                "and only successors"
            )
        fork_record = RecordedFork(
            predecessor=pinned_name(item["predecessor"], f"{entry_where}.predecessor"),
            successors=fork_successors,
            continued_by=continued_by,
            listed_on=_iso_date(item["listed_on"], f"{entry_where}.listed_on"),
            reason=_text(item["reason"], f"{entry_where}.reason"),
        )
        if fork_record.predecessor in fork_record.successors:
            raise SelectorLineageError(f"{entry_where}: a selector cannot succeed itself")
        fork_keys.append(fork_record.predecessor)
        forks[fork_record.predecessor] = fork_record
    _sorted_unique(fork_keys, f"{where}: forks (by predecessor)")

    first_cuts: dict[str, RecordedFirstCut] = {}
    for index, raw in enumerate(_list(data.get("first_cuts") or [], f"{where}: first_cuts")):
        entry_where = f"{where}: first_cuts[{index}]"
        item = _mapping(raw, entry_where)
        if set(item) != _FIRST_CUT_FIELDS:
            raise SelectorLineageError(
                f"{entry_where} must have exactly {sorted(_FIRST_CUT_FIELDS)}"
            )
        listed_on = _iso_date(item["listed_on"], f"{entry_where}.listed_on")
        reason = _text(item["reason"], f"{entry_where}.reason")
        selectors = tuple(
            pinned_name(value, f"{entry_where}.selectors[{position}]")
            for position, value in enumerate(_list(item["selectors"], f"{entry_where}.selectors"))
        )
        if not selectors:
            raise SelectorLineageError(f"{entry_where}.selectors must list at least one selector")
        _sorted_unique(selectors, f"{entry_where}.selectors")
        for name in selectors:
            if name in first_cuts:
                raise SelectorLineageError(f"{entry_where}: {name} is listed twice")
            first_cuts[name] = RecordedFirstCut(name, listed_on, reason)

    unused = sorted(set(digests) - named)
    if unused:
        raise SelectorLineageError(f"{where}: selector_digests lists unused selectors {unused}")
    return LineageBaseline(
        selector_digests=digests, drops=drops, forks=forks, first_cuts=first_cuts
    )
