"""Compose a successor selector that carries its predecessor's base scopes unchanged.

A new cut of a selector line takes its predecessor's scopes and changes only
primary scopes: it adds new ones, replaces a version within the same
``(jurisdiction, document_class)`` pair, or removes one. It may also add a base
scope for a pair that has none. Every base scope of the predecessor
(``layer: base``) is carried into the successor as the same ``ReleaseScope``,
so a successor can neither omit a base nor change one. Replacing a base is a
reviewed change that this module does not make.

``compose_successor`` checks every requested change against the predecessor
and raises ``SuccessorError`` for any it refuses. It writes no file, so a
refused cut leaves nothing behind.

``render_selector`` returns the selector text a new cut commits: keys sorted,
a two-space indent and a final newline, the layout of
``us-rulespec-2026-11-11-cms-w6-federal-guidance`` and many other tracked
selectors. Other tracked selectors use other layouts, so the builders under
``scripts/repro/`` that reproduce them keep their own code.

``tracked_base_scopes`` reads which scopes are bases from the tracked
selectors. Corpus locks carry no layer, so the selectors are the only record.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.releases import (
    LAYER_BASE,
    LAYER_PRIMARY,
    ReleaseManifest,
    ReleaseScope,
    ScopeKey,
)
from axiom_corpus.corpus.selector_lineage import declared_predecessor


class SuccessorError(ValueError):
    """A requested successor would change its predecessor in a way this module refuses."""


def _label(key: ScopeKey) -> str:
    return "/".join(key)


def _scope_keys(argument: str, values: Iterable[object]) -> tuple[ScopeKey, ...]:
    """Return ``values`` as scope keys, refusing anything but 3-tuples of strings.

    A bare triple passed where a list of triples belongs would otherwise be
    read as three one-string keys.
    """
    keys: list[ScopeKey] = []
    for value in values:
        if not (
            isinstance(value, tuple)
            and len(value) == 3
            and all(isinstance(part, str) for part in value)
        ):
            raise SuccessorError(
                f"{argument} must name each scope as a (jurisdiction, document_class, "
                f"version) tuple of strings, not {value!r}"
            )
        keys.append((value[0], value[1], value[2]))
    return tuple(keys)


def _scope(key: ScopeKey, *, layer: str) -> ReleaseScope:
    try:
        return ReleaseScope(jurisdiction=key[0], document_class=key[1], version=key[2], layer=layer)
    except ValueError as exc:
        raise SuccessorError(str(exc)) from exc


def compose_successor(
    predecessor: ReleaseManifest,
    *,
    name: str,
    description: str,
    add: Iterable[ScopeKey] = (),
    replace: Mapping[ScopeKey, str] | None = None,
    remove: Iterable[ScopeKey] = (),
    add_base: Iterable[ScopeKey] = (),
    tracked: Collection[str] = (),
) -> ReleaseManifest:
    """Return the successor of ``predecessor`` with the given primary-scope changes.

    ``add`` names new primary scopes. ``replace`` maps a primary scope of the
    predecessor to a new version in the same pair. ``remove`` names primary
    scopes of the predecessor to drop. ``add_base`` names a base scope for a
    pair the predecessor has no base for. Each scope is a
    ``(jurisdiction, document_class, version)`` tuple of strings. Every base
    scope of the predecessor is carried unchanged, the quality profile is
    inherited, and the scopes are sorted by
    ``(jurisdiction, document_class, version)``.

    ``description`` must name ``predecessor.name`` as a whole release name, so
    the selector lineage check resolves the cut's predecessor
    (``selector_lineage.declared_predecessor``). That check takes the first
    tracked selector a description names, so the composer resolves the
    description against ``tracked`` plus ``predecessor.name`` and refuses it
    unless the result is the predecessor. A repro script passes the names of
    the tracked selectors, the stems of ``manifests/releases/*.json``, so a
    description that names another tracked selector before the predecessor is
    refused here rather than by the lineage check. With the default, empty
    ``tracked``, only the predecessor's own name is checked.

    Raises ``SuccessorError`` for any refused change. Nothing is written.
    """
    added = _scope_keys("add", add)
    replacements: dict[ScopeKey, str] = dict(replace or {})
    replaced = _scope_keys("replace", replacements)
    for old in replaced:
        version = replacements[old]
        if not isinstance(version, str):
            raise SuccessorError(
                f"replace must map {_label(old)} to a version string, not {version!r}"
            )
    removed = _scope_keys("remove", remove)
    added_bases = _scope_keys("add_base", add_base)
    if isinstance(tracked, str):
        raise SuccessorError("tracked must be a collection of selector names, not one string")

    if name == predecessor.name:
        raise SuccessorError(f"A successor must have a new name, not {predecessor.name!r}")

    selected = {scope.key: scope for scope in predecessor.scopes}
    base_pairs = {scope.pair for scope in predecessor.scopes if scope.is_base}

    listed = Counter([*added, *replacements, *removed, *added_bases])
    repeated = sorted(key for key, count in listed.items() if count > 1)
    if repeated:
        raise SuccessorError(
            "A scope may appear in only one of add, replace, remove and add_base, once: "
            + ", ".join(_label(key) for key in repeated)
        )

    for key in (*replacements, *removed):
        scope = selected.get(key)
        if scope is not None and scope.is_base:
            raise SuccessorError(
                f"{_label(key)} is a base scope of {predecessor.name}; base scopes are "
                "carried unchanged and cannot be replaced or removed"
            )
        if scope is None:
            raise SuccessorError(
                f"{_label(key)} is not a primary scope of {predecessor.name}, so it cannot "
                "be replaced or removed"
            )

    for key in (*added, *added_bases):
        if key in selected:
            layer = selected[key].layer
            raise SuccessorError(
                f"{predecessor.name} already selects {_label(key)} as a {layer} scope"
            )

    new_keys: list[ScopeKey] = [*added, *added_bases]
    replacement_keys: dict[ScopeKey, ScopeKey] = {}
    for old, version in replacements.items():
        new = (old[0], old[1], version)
        if version == old[2]:
            raise SuccessorError(f"The replacement for {_label(old)} must be a different version")
        if new in selected:
            raise SuccessorError(
                f"The replacement {_label(new)} for {_label(old)} is already selected by "
                f"{predecessor.name}"
            )
        replacement_keys[old] = new
        new_keys.append(new)
    colliding = sorted(key for key, count in Counter(new_keys).items() if count > 1)
    if colliding:
        raise SuccessorError(
            "These scopes would be selected more than once: "
            + ", ".join(_label(key) for key in colliding)
        )

    new_base_pairs = Counter((key[0], key[1]) for key in added_bases)
    for pair, count in sorted(new_base_pairs.items()):
        if pair in base_pairs:
            raise SuccessorError(
                f"{predecessor.name} already has a base scope for {'/'.join(pair)}; "
                "replacing a base is a reviewed change the composer does not make"
            )
        if count > 1:
            raise SuccessorError(f"add_base names more than one base for {'/'.join(pair)}")

    dropped = {*removed, *replacement_keys}
    scopes = [scope for scope in predecessor.scopes if scope.key not in dropped]
    scopes.extend(_scope(key, layer=LAYER_PRIMARY) for key in added)
    scopes.extend(_scope(key, layer=LAYER_PRIMARY) for key in replacement_keys.values())
    scopes.extend(_scope(key, layer=LAYER_BASE) for key in added_bases)
    if not scopes:
        raise SuccessorError(f"The successor of {predecessor.name} would select no scope")
    scopes.sort(key=lambda scope: scope.key)

    try:
        successor = ReleaseManifest(
            name=name,
            scopes=tuple(scopes),
            description=description,
            quality_profile=predecessor.quality_profile,
        )
    except ValueError as exc:
        raise SuccessorError(str(exc)) from exc

    declared = declared_predecessor(successor, {*tracked, predecessor.name})
    if declared is None:
        raise SuccessorError(
            f"The description of {name} must name its predecessor {predecessor.name}"
        )
    if declared != predecessor.name:
        raise SuccessorError(
            f"The description of {name} must name its predecessor {predecessor.name} "
            f"before the tracked selector {declared}; the selector lineage check takes "
            "the first tracked selector a description names"
        )
    return successor


def render_selector(release: ReleaseManifest) -> str:
    """Return the selector file text for ``release``.

    Keys are sorted at every level, with a two-space indent and a final newline,
    and each scope uses its one canonical encoding
    (``ReleaseScope.to_selector_mapping``). ``description`` and
    ``quality_profile`` appear when set.

    Non-ASCII characters are written as JSON escapes (``json.dumps``' default
    ``ensure_ascii=True``), as the rulespec-us builders under ``scripts/repro/``
    write them, so the file is ASCII and reads the same under any locale.
    """
    payload: dict[str, Any] = {
        "name": release.name,
        "scopes": [scope.to_selector_mapping() for scope in release.scopes],
    }
    if release.description is not None:
        payload["description"] = release.description
    if release.quality_profile is not None:
        payload["quality_profile"] = release.quality_profile
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def tracked_base_scopes(releases_dir: Path) -> frozenset[ScopeKey]:
    """Return every scope that a selector under ``releases_dir`` marks as a base.

    Each ``*.json`` file in the directory is loaded with ``ReleaseManifest.load``,
    so a selector that does not load raises instead of being skipped.
    """
    if not releases_dir.is_dir():
        raise FileNotFoundError(f"Release selector directory not found: {releases_dir}")
    bases: set[ScopeKey] = set()
    for path in sorted(releases_dir.glob("*.json")):
        release = ReleaseManifest.load(path)
        bases.update(scope.key for scope in release.scopes if scope.is_base)
    return frozenset(bases)
