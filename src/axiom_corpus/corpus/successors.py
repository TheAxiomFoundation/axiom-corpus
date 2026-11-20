"""Compose a successor selector that carries its predecessor's base scopes unchanged.

A new cut of a selector line takes its predecessor's scopes and changes only
primary scopes: it adds new ones, replaces a version within the same
``(jurisdiction, document_class)`` pair, or removes one. It may also add a base
scope for a pair that has none. Every base scope of the predecessor
(``layer: base``) is carried into the successor as the same ``ReleaseScope``,
so a successor can neither omit a base nor change one. Replacing a base is a
reviewed change that this module does not make.

``compose_successor`` checks every requested change against the predecessor
and raises ``SuccessorError`` for any it refuses. Unless the caller passes
the tracked selector names, it reads them from ``releases_dir``, the
``manifests/releases`` of the checkout the cut is committed to, which
defaults to ``DEFAULT_RELEASES_DIR``; that directory must hold the
predecessor as given. It writes no file, so a refused cut leaves nothing
behind.

``render_selector`` returns the selector text a new cut commits: keys sorted,
a two-space indent and a final newline, the layout of
``us-rulespec-2026-11-11-cms-w6-federal-guidance`` and many other tracked
selectors. Other tracked selectors use other layouts, so the builders under
``scripts/repro/`` that reproduce them keep their own code.

``canonical_scope_key`` returns the key of a scope named outside a selector,
such as on a command line, and refuses a spelling no selector can hold, so a
comparison against the tracked bases is exact.

``tracked_base_scopes`` reads which scopes are bases from the tracked
selectors. Corpus locks carry no layer, so the selectors are the only record,
and a directory that holds no selector file is refused rather than read as
holding no base.
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

# The tracked selectors of the checkout this module is imported from.
DEFAULT_RELEASES_DIR = Path(__file__).resolve().parents[3] / "manifests" / "releases"


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


def _selector_files(releases_dir: Path) -> dict[str, Path]:
    """Return the selector files of ``releases_dir`` by name, refusing an unusable directory.

    Each ``*.json`` entry must be a file. A directory that is missing or holds
    no selector file raises ``FileNotFoundError``, since reading no selector
    would report no name and no base.
    """
    if not releases_dir.is_dir():
        raise FileNotFoundError(f"Release selector directory not found: {releases_dir}")
    files: dict[str, Path] = {}
    for path in sorted(releases_dir.glob("*.json")):
        if not path.is_file():
            raise ValueError(f"{path} is not a selector file")
        files[path.stem] = path
    if not files:
        raise FileNotFoundError(f"No release selector in {releases_dir}")
    return files


def _tracked_selector_names(releases_dir: Path, predecessor: ReleaseManifest) -> frozenset[str]:
    """Return the selector names of ``releases_dir``, which must hold ``predecessor`` as given.

    Reading no names would check the description against the predecessor's
    name alone, so a directory that is missing or holds no selector file
    raises. A directory without the predecessor's file, or whose file loads to
    another selector, belongs to another checkout or another state of this
    one, so its names are not the ones the cut is checked against.
    """
    try:
        files = _selector_files(releases_dir)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"{exc}; pass tracked, the names of the tracked selectors, or releases_dir, "
            "the manifests/releases of the checkout the cut is committed to"
        ) from exc
    path = files.get(predecessor.name)
    if path is None or ReleaseManifest.load(path) != predecessor:
        raise SuccessorError(
            f"{releases_dir} does not hold the predecessor {predecessor.name} as given; "
            "pass releases_dir, the manifests/releases of the checkout the cut is "
            "committed to, or tracked"
        )
    return frozenset(files)


def canonical_scope_key(jurisdiction: str, document_class: str, version: str) -> ScopeKey:
    """Return the scope key a selector spells with these parts, refusing any other spelling.

    Artifact paths pass each part through ``artifacts.safe_segment``, which
    strips surrounding whitespace and ``/`` and rewrites ``\\`` and ``:``,
    and APFS folds case. So ``v ``, ``v/`` or ``V`` can name the files of
    ``v`` while comparing unequal to it, and a check that compares names
    would let such a spelling read or write a base's files. For a part a
    selector can spell, ``safe_segment`` is the identity, so the key names its
    own files. Raises ``ValueError`` naming the parts and the reason.
    """
    try:
        return ReleaseScope(
            jurisdiction=jurisdiction, document_class=document_class, version=version
        ).key
    except ValueError as exc:
        raise ValueError(
            f"not a canonical scope: {jurisdiction!r}/{document_class!r}/{version!r} ({exc})"
        ) from exc


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
    tracked: Collection[str] | None = None,
    releases_dir: Path | None = None,
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
    description against the tracked selector names plus ``predecessor.name``
    and refuses it unless the result is the predecessor. A description that
    names another tracked selector before the predecessor is therefore refused
    here rather than by the lineage check.

    With ``tracked`` left as ``None``, each call reads the tracked selector
    names as the stems of ``releases_dir/*.json``. ``releases_dir`` names the
    ``manifests/releases`` directory of the checkout the cut is committed to;
    ``None`` means ``DEFAULT_RELEASES_DIR``, that directory in the checkout
    this module is imported from. The directory must hold the predecessor's
    selector file, and that file must load to ``predecessor`` itself, or a
    ``SuccessorError`` says so. It raises ``FileNotFoundError`` when the
    directory is missing or holds no selector file, and ``ValueError`` when a
    ``*.json`` entry is not a file, so a copy installed outside a checkout
    must pass ``releases_dir`` or ``tracked``. The default directory decides
    only what it holds: when it holds the predecessor but lacks a selector the
    destination tracks, a description that names that selector first still
    passes, so a cut for another checkout passes that checkout's
    ``releases_dir``. An explicit ``tracked`` replaces those names and skips
    the predecessor check, and ``tracked=()`` checks the predecessor's own
    name alone.

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
    names = (
        tracked
        if tracked is not None
        else _tracked_selector_names(
            DEFAULT_RELEASES_DIR if releases_dir is None else releases_dir, predecessor
        )
    )

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

    declared = declared_predecessor(successor, {*names, predecessor.name})
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
    so a selector that does not load raises instead of being skipped. A
    directory that is missing or holds no selector file raises
    ``FileNotFoundError``, since reading no selector would report no base,
    and a ``*.json`` entry that is not a file raises ``ValueError``.
    """
    bases: set[ScopeKey] = set()
    for path in _selector_files(releases_dir).values():
        release = ReleaseManifest.load(path)
        bases.update(scope.key for scope in release.scopes if scope.is_base)
    return frozenset(bases)
