"""Compose a successor selector that carries its predecessor's base scopes unchanged.

A new cut of a selector line takes its predecessor's scopes and changes only
primary scopes: it adds new ones, replaces a version within the same
``(jurisdiction, document_class)`` pair, or removes one. It may also add a base
scope for a pair that has none. Every base scope of the predecessor
(``layer: base``) is carried into the successor as the same ``ReleaseScope``,
so a successor can neither omit a base nor change one. Replacing a base is a
reviewed change that this module does not make.

A tracked selector is a ``*.json`` file committed at HEAD under a checkout's
``manifests/releases``; any other directory, inside a checkout or not, is read
from disk as given. A selectors directory that is a symlink, whose parent
directory is one, that is spelled with ``..``, or that holds a ``.git`` entry
or whose parent directory does raises ``ValueError``, and one at which git
answers with another toplevel, or cannot run, while a ``.git`` entry sits two
levels above it raises ``FileNotFoundError``: git would read another
repository than the checkout's, or none, and the disk would answer for it.
``tracked_selector_texts`` and ``tracked_selector_text`` read them, so a
sparse checkout, a file hidden from disk, an edit, an untracked file and a
staged one change nothing.

``compose_successor`` checks every requested change against the predecessor
and raises ``SuccessorError`` for any it refuses. Unless the caller passes
the tracked selector names, it reads them from ``releases_dir``, the
``manifests/releases`` of the checkout the cut is committed to, which
defaults to ``DEFAULT_RELEASES_DIR``; that directory must hold the
predecessor as given, committed at HEAD when it is a checkout's. It also
refuses a new primary scope, added or a replacement, that a tracked selector
marks as a base, so a base that another cut replaced cannot come back as
primary. Unless the caller passes those bases as ``tracked_bases``, it reads
them from the same directory, and only for a cut that adds or replaces a
primary scope. A cut under the name of a selector the directory already
tracks is refused unless it reproduces that selector's file byte for byte. It
writes no file, so a refused cut leaves nothing behind.

``render_selector`` returns the selector text a new cut commits: keys sorted,
a two-space indent and a final newline, the layout of
``us-rulespec-2026-11-11-cms-w6-federal-guidance`` and many other tracked
selectors. Other tracked selectors use other layouts, so the builders under
``scripts/repro/`` that reproduce them keep their own code.

``canonical_scope_key`` returns the key of a scope named outside a selector,
such as on a command line, and refuses a spelling no selector can hold, so a
comparison against the tracked bases is exact.

``guard_scope_artifacts`` checks the artifact paths a scope tool reads or
writes before it opens any: an artifact that resolves to another artifact's
path, a link at a checkout's guarded place that leads into no checkout, and a
rewritten file with more than one link are refused. It returns the
``manifests/releases`` of the checkout that physically holds each path and of
each checkout holding a link on it as spelled (``checkouts_holding``; the
threat model's stated limits 11 and 15), other than the caller's own, so the
tool reads their tracked bases too.
``refuse_links_into_bases`` compares the artifact paths of the bases a tool
knows with the files it rewrites, moves or unlinks, and refuses a base's file
that leads to one of them through a link.

``tracked_base_scopes`` reads which scopes are bases from the tracked
selectors. Corpus locks carry no layer, so the selectors are the only record,
and a directory that holds no selector file is refused rather than read as
holding no base. Only HEAD is read: a selector main committed after the
checkout's branch point, a selector that is only staged, and one a commit on
the branch deleted do not count. ``refuse_tracked_bases_as_primary`` refuses
any of those bases that a selector selects as a primary scope; the composer
and ``scripts/deduplicate_release_selector.py`` call it.
"""

from __future__ import annotations

import json
import os
import subprocess
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
    validate_release_name,
)
from axiom_corpus.corpus.resolver import _existing_ancestor, _standing_places
from axiom_corpus.corpus.selector_lineage import declared_predecessor

# The tracked selectors of the checkout this module is imported from.
DEFAULT_RELEASES_DIR = Path(__file__).resolve().parents[3] / "manifests" / "releases"
# The variables that point git at another repository, index or working tree. A
# hook or a shell may export them; the readers here ignore them, so git reads
# the checkout that holds the directory it runs in.
_GIT_LOCATION_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")
# Those, and the variable that stops git's search for a repository below a
# checkout's root, so git fails where it should answer.
_GIT_IGNORED_VARIABLES = (*_GIT_LOCATION_VARIABLES, "GIT_CEILING_DIRECTORIES")
_SELECTORS_PATH = "manifests/releases"
# The artifact files of a scope that a base comparison checks, with their suffixes.
_BASE_FILES = (("provisions", ".jsonl"), ("inventory", ".json"), ("coverage", ".json"))
# The modes of a regular file in a git tree; a symlink (120000) and a
# directory (040000) are not selector files.
_SELECTOR_FILE_MODES = frozenset({"100644", "100755"})


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
    would report no name and no base. This reads a directory that is not a
    checkout's ``manifests/releases`` (``_checkout_of``) from disk.
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


def _git(cwd: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    """Run git in ``cwd`` without the inherited ``GIT_*`` location variables or
    ``GIT_CEILING_DIRECTORIES``.

    The output is captured and a non-zero exit is returned, not raised. An
    ``OSError``, such as no ``git`` on ``PATH``, propagates to the caller.
    """
    environment = {
        key: value for key, value in os.environ.items() if key not in _GIT_IGNORED_VARIABLES
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=environment, input=stdin, capture_output=True, check=False
    )


def _stderr(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stderr.decode("utf-8", "replace").strip()


def _refuse_selector_directory_link(releases_dir: Path) -> None:
    """Refuse a selector directory spelled with ``..``, one that is a symlink or
    whose parent directory is one, and one that holds a ``.git`` entry or whose
    parent directory does.

    git runs in, and the disk shows, the directory a path resolves to, and git
    answers for the repository the nearest ``.git`` entry names, so a link or a
    nested repository or gitfile at a checkout's ``manifests`` or
    ``manifests/releases`` would let another checkout's HEAD, or a directory no
    HEAD holds, answer for this one. A selectors directory directly in a git
    working tree's root is refused by the same rule; no command line passes one.
    Raises ``ValueError``.
    """
    probe = releases_dir if releases_dir.is_absolute() else Path.cwd() / releases_dir
    if ".." in probe.parts:
        raise ValueError(
            f"selector directory is spelled with '..': {releases_dir}; spell it as "
            "<checkout>/manifests/releases"
        )
    for place in (probe.parent, probe):
        if place.is_symlink():
            raise ValueError(
                f"selector directory leads through a link: {place} -> "
                f"{os.path.realpath(place)}; a checkout's tracked selectors are the files "
                "its own HEAD commits under its own manifests/releases, so make "
                f"{place.name} a directory of that checkout, not a link"
            )
        if os.path.lexists(place / ".git"):
            raise ValueError(
                f"selector directory sits at a git entry: {place / '.git'}; git there "
                "reads the repository that entry names, so pass "
                "<checkout>/manifests/releases, where only <checkout> holds .git"
            )


def _checkout_of(releases_dir: Path) -> Path | None:
    """Return the checkout whose ``manifests/releases`` ``releases_dir`` is, or None.

    The checkout is the git toplevel of the nearest existing directory, and
    ``releases_dir`` must be that toplevel's ``manifests/releases``, as the
    same file or the same realpath. None means "read from disk": a standalone
    directory, even one inside a checkout, is read as given. It first refuses a
    ``releases_dir`` reached through a link, spelled with ``..``, or at a
    ``.git`` entry (``_refuse_selector_directory_link``). When a ``.git`` entry
    sits two levels above ``releases_dir``, whatever the directory's names, and
    git cannot run there or answers with a toplevel that does not hold
    ``releases_dir`` as its ``manifests/releases`` (a ``core.worktree``
    setting, a bare git directory at ``manifests``, a ``.git/config`` git
    cannot parse, or a selectors directory two levels below a working tree's
    root that is not its ``manifests/releases``), it raises
    ``FileNotFoundError`` rather than read the disk, which may hide or add
    selectors.
    """
    _refuse_selector_directory_link(releases_dir)
    probe = releases_dir if releases_dir.is_absolute() else Path.cwd() / releases_dir
    # git runs from the nearest existing directory, found as the resolver finds it.
    start = _existing_ancestor(probe)
    if not start.is_dir():
        start = start.parent
    try:
        result = _git(start, "rev-parse", "--show-toplevel")
    except OSError as exc:
        reason = str(exc)
    else:
        if result.returncode == 0:
            top = Path(os.fsdecode(result.stdout.rstrip(b"\n")))
            selectors = top / "manifests" / "releases"
            if os.path.realpath(probe) == os.path.realpath(selectors):
                return top
            try:
                if probe.exists() and os.path.samefile(probe, selectors):
                    return top
            except OSError:
                pass
            if os.path.lexists(probe.parent.parent / ".git"):
                raise FileNotFoundError(
                    "selector directory is not the manifests/releases of the toplevel "
                    f"git names ({top}), while a .git entry sits two levels up at "
                    f"{probe.parent.parent / '.git'}: {releases_dir}; pass "
                    "<checkout>/manifests/releases, where git answers with <checkout>"
                )
            return None
        reason = _stderr(result)
    if os.path.lexists(probe.parent.parent / ".git"):
        raise FileNotFoundError(
            f"git cannot read the checkout at {probe.parent.parent}, so its committed "
            f"selectors cannot be listed: {reason}"
        )
    return None


def _head_entries(top: Path, releases_dir: Path, path: str) -> list[tuple[str, str]]:
    """Return ``(name, object id)`` for each selector file ``path`` lists at HEAD of ``top``.

    Only direct entries of ``manifests/releases`` whose name ends in
    ``.json`` count. One that is not a regular file in the tree, such as a
    committed symlink or directory, raises ``ValueError``. A HEAD that cannot
    be listed, an unborn one included, raises ``FileNotFoundError``.
    """
    listing = _git(top, "ls-tree", "-z", "--full-tree", "HEAD", "--", path)
    if listing.returncode != 0:
        raise FileNotFoundError(
            f"Cannot list the selectors of {releases_dir} at HEAD of {top}: {_stderr(listing)}"
        )
    entries: list[tuple[str, str]] = []
    for record in listing.stdout.split(b"\0"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        mode, kind, oid = meta.decode("ascii").split(" ")
        entry = os.fsdecode(raw_path)
        directory, _, filename = entry.rpartition("/")
        if directory != _SELECTORS_PATH or not filename.endswith(".json"):
            continue
        if mode not in _SELECTOR_FILE_MODES or kind != "blob":
            raise ValueError(f"{top / entry} is not a selector file")
        entries.append((filename.removesuffix(".json"), oid))
    return entries


def _read_blobs(top: Path, releases_dir: Path, oids: list[str]) -> list[str]:
    """Return the UTF-8 text of each blob, in order, with one ``git cat-file --batch``."""
    batch = _git(top, "cat-file", "--batch", stdin=b"".join(f"{oid}\n".encode() for oid in oids))
    if batch.returncode != 0:
        raise FileNotFoundError(
            f"Cannot read the selectors of {releases_dir} at HEAD of {top}: {_stderr(batch)}"
        )
    output = batch.stdout
    texts: list[str] = []
    position = 0
    for oid in oids:
        end = output.index(b"\n", position)
        header = output[position:end].split(b" ")
        if len(header) != 3 or header[1] != b"blob":
            raise FileNotFoundError(
                f"Cannot read the selector blob {oid} of {releases_dir} at HEAD of {top}"
            )
        size = int(header[2])
        texts.append(output[end + 1 : end + 1 + size].decode("utf-8"))
        position = end + 1 + size + 1
    return texts


def _selector_texts(releases_dir: Path) -> tuple[Path | None, dict[str, str]]:
    """Return the checkout ``releases_dir`` belongs to (or None) and its selector texts."""
    top = _checkout_of(releases_dir)
    if top is None:
        return None, {
            name: path.read_text(encoding="utf-8")
            for name, path in _selector_files(releases_dir).items()
        }
    entries = _head_entries(top, releases_dir, f"{_SELECTORS_PATH}/")
    if not entries:
        raise FileNotFoundError(f"No release selector in {releases_dir} at HEAD of {top}")
    texts = _read_blobs(top, releases_dir, [oid for _, oid in entries])
    return top, {name: text for (name, _), text in zip(entries, texts, strict=True)}


def tracked_selector_texts(releases_dir: Path) -> dict[str, str]:
    """Return the text of every tracked selector in ``releases_dir``, by name.

    A tracked selector is a ``*.json`` file committed at HEAD under the
    checkout's ``manifests/releases``; any other directory, inside a checkout
    or not, is read from disk as given. For a checkout, an entry that is not
    a regular file at HEAD (a committed symlink or directory) raises
    ``ValueError``, and a HEAD that cannot be listed or holds no selector
    raises ``FileNotFoundError``. For another directory, one that is missing
    or holds no selector file raises ``FileNotFoundError``, and a ``*.json``
    entry that is not a file raises ``ValueError``. Either raises
    ``ValueError`` when the directory is reached through a link, spelled with
    ``..``, or at a ``.git`` entry, and ``FileNotFoundError`` when git answers
    with a toplevel that does not hold the directory, or cannot run there,
    while a ``.git`` entry sits two levels above it.
    """
    return _selector_texts(releases_dir)[1]


def tracked_selector_text(releases_dir: Path, name: str) -> str | None:
    """Return the text of the tracked selector ``name`` in ``releases_dir``, or None.

    The caller validates ``name``. For a checkout's ``manifests/releases``
    this is the file committed at HEAD, None when HEAD has no such file. For
    any other directory it is the file on disk, None when nothing is there.
    An entry that is not a selector file (a committed symlink or directory,
    or on disk a directory or a dangling link) raises ``ValueError``, as does
    a directory reached through a link, spelled with ``..``, or at a ``.git``
    entry. It raises ``FileNotFoundError`` when git answers with a toplevel
    that does not hold the directory, or cannot run there, while a ``.git``
    entry sits two levels above it.
    """
    top = _checkout_of(releases_dir)
    if top is None:
        path = releases_dir / f"{name}.json"
        if not os.path.lexists(path):
            return None
        if not path.is_file():
            raise ValueError(f"{path} is not a selector file")
        return path.read_text(encoding="utf-8")
    entries = _head_entries(top, releases_dir, f"{_SELECTORS_PATH}/{name}.json")
    oids = [oid for stem, oid in entries if stem == name]
    if not oids:
        return None
    return _read_blobs(top, releases_dir, oids[:1])[0]


def _tracked_selector_names(releases_dir: Path, predecessor: ReleaseManifest) -> frozenset[str]:
    """Return the tracked selector names of ``releases_dir``, which must hold ``predecessor``.

    Reading no names would check the description against the predecessor's
    name alone, so a directory that is missing or holds no selector file
    raises. A directory without the predecessor's selector, or whose selector
    loads to another one, belongs to another checkout or another state of
    this one, so its names are not the ones the cut is checked against. For a
    checkout the names and the predecessor are read as committed at HEAD
    (``tracked_selector_texts``), so an uncommitted predecessor is refused.
    """
    try:
        top, texts = _selector_texts(releases_dir)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"{exc}; pass tracked, the names of the tracked selectors, or releases_dir, "
            "the manifests/releases of the checkout the cut is committed to"
        ) from exc
    text = texts.get(predecessor.name)
    if (
        text is None
        or ReleaseManifest.loads(text, manifest_path=releases_dir / f"{predecessor.name}.json")
        != predecessor
    ):
        if top is not None:
            raise SuccessorError(
                f"{releases_dir} does not hold the predecessor {predecessor.name} as given "
                f"at HEAD of {top}; commit the predecessor's selector first, or pass "
                "releases_dir, the manifests/releases of the checkout the cut is committed "
                "to, or tracked"
            )
        raise SuccessorError(
            f"{releases_dir} does not hold the predecessor {predecessor.name} as given; "
            "pass releases_dir, the manifests/releases of the checkout the cut is "
            "committed to, or tracked"
        )
    return frozenset(texts)


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
    tracked_bases: Collection[ScopeKey] | None = None,
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
    names from ``releases_dir`` (``tracked_selector_texts``): a tracked
    selector is a ``*.json`` file committed at HEAD under the checkout's
    ``manifests/releases``, and any other directory, inside a checkout or
    not, is read from disk as given. ``releases_dir`` names the
    ``manifests/releases`` directory of the checkout the cut is committed to;
    ``None`` means ``DEFAULT_RELEASES_DIR``, that directory in the checkout
    this module is imported from. The directory must hold the predecessor's
    selector, committed at HEAD for a checkout, and it must load to
    ``predecessor`` itself, or a ``SuccessorError`` says so; a chained cut
    from a cut not yet committed is refused until that cut is committed. It
    raises ``FileNotFoundError`` when the directory is missing or holds no
    selector, or when git answers with a toplevel that does not hold the
    directory, or cannot run there, while a ``.git`` entry sits two levels
    above it, and ``ValueError`` when a selector entry is not a file, or when
    the directory is a symlink, sits in one, is spelled with ``..``, or holds
    a ``.git`` entry or sits in a directory that does, so a copy installed
    outside a checkout must pass ``releases_dir`` or ``tracked``. The default
    directory decides only what it holds: when it holds the predecessor but
    lacks a selector the destination tracks, a description that names that
    selector first still passes, so a cut for another checkout passes that
    checkout's ``releases_dir``. An explicit ``tracked`` replaces those names
    and skips the predecessor check, and ``tracked=()`` checks the
    predecessor's own name alone.

    A new primary scope, one in ``add`` or a replacement, may not be a scope
    that a tracked selector marks as a base: a scope has one layer across the
    tracked selectors (the lineage check reports a ``LayerConflict``
    otherwise), so a base that another cut replaced cannot come back as
    primary. ``tracked_bases`` names those bases. With ``tracked_bases`` left
    as ``None``, they are read with ``tracked_base_scopes`` from
    ``releases_dir``, or ``DEFAULT_RELEASES_DIR`` when that is ``None``, and
    only when the cut adds or replaces a primary scope, so only such a cut
    needs that directory. ``add_base`` is not checked, so a restore may bring
    a tracked base back as a base.

    A tracked selector is never rewritten, so a name already tracked in the
    destination (``tracked_selector_text`` of ``releases_dir``, or
    ``DEFAULT_RELEASES_DIR``) is accepted only for an exact reproduction of
    that file: the rendered cut (``render_selector``) must equal its text byte
    for byte, whether or not ``tracked`` is passed. A name in ``tracked`` with
    no file there is refused, since there is nothing to compare the cut with.
    The byte rule reads the same directory as the name and base checks.
    Without ``releases_dir`` that is the checkout the module is imported from,
    so a caller cutting for another checkout must pass ``releases_dir``, or
    ``tracked`` (a tracked name with no file in the default directory is then
    refused).

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
    try:
        validate_release_name(name)
    except ValueError as exc:
        raise SuccessorError(str(exc)) from exc
    directory = DEFAULT_RELEASES_DIR if releases_dir is None else releases_dir
    existing = tracked_selector_text(directory, name)
    if existing is None and name in names:
        raise SuccessorError(
            f"{name} is a tracked selector, but {directory} holds no {name}.json to compare "
            "this cut with; pass releases_dir, the manifests/releases of the checkout the "
            "cut is committed to"
        )

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

    new_primaries = [*added, *replacement_keys.values()]
    if new_primaries:
        refuse_tracked_bases_as_primary(
            [_scope(key, layer=LAYER_PRIMARY) for key in new_primaries],
            tracked_base_scopes(DEFAULT_RELEASES_DIR if releases_dir is None else releases_dir)
            if tracked_bases is None
            else tracked_bases,
            selector=name,
        )

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
    if existing is not None and render_selector(successor) != existing:
        raise SuccessorError(
            f"{name} is a tracked selector of {directory}, and this cut is not its committed "
            "file byte for byte; a tracked selector is never rewritten, so a new cut takes a "
            "new name"
        )

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
    """Return every scope that a tracked selector of ``releases_dir`` marks as a base.

    A tracked selector is a ``*.json`` file committed at HEAD under the
    checkout's ``manifests/releases``; any other directory, inside a checkout
    or not, is read from disk as given (``tracked_selector_texts``). Only
    HEAD is read: a selector main committed after this checkout's branch
    point, a selector that is only staged, and one a commit on this branch
    deleted do not count.

    Each selector is loaded with ``ReleaseManifest.loads``, in name order, so
    a selector that does not load raises instead of being skipped. A
    directory that is missing or holds no selector raises
    ``FileNotFoundError``, since reading no selector would report no base,
    as does one at which git answers with a toplevel that does not hold the
    directory, or cannot run there, while a ``.git`` entry sits two levels
    above it. A selector entry that is not a file raises ``ValueError``, as
    does a directory reached through a link, spelled with ``..``, or at a
    ``.git`` entry.
    """
    bases: set[ScopeKey] = set()
    for name, text in sorted(tracked_selector_texts(releases_dir).items()):
        release = ReleaseManifest.loads(text, manifest_path=releases_dir / f"{name}.json")
        bases.update(scope.key for scope in release.scopes if scope.is_base)
    return frozenset(bases)


def checkouts_holding(
    path: Path, *, memo: dict[Path, Path | None] | None = None
) -> tuple[frozenset[Path], Path | None]:
    """The checkouts that hold ``path``: those whose guarded place it stands at below a
    symlink (the resolver's ``_standing_places``), and the one it physically resolves into.

    A checkout here is a git working tree whose HEAD commits a
    ``manifests/releases/*.json``. The physical holder is the git toplevel of
    the nearest existing directory of ``path``'s realpath, found with the
    ``GIT_*`` location variables ignored and accepted only when its HEAD lists
    such a selector; markers on disk play no part, so a sparse checkout
    without ``src/`` and ``.axiom/`` counts, while an unrelated git repository
    and a plain directory do not. A link holder is a checkout at whose guarded
    place (``data``, ``data/corpus``, ``data/corpus/<artifact class>`` or below)
    ``path``, as spelled, passes a symlink. Link holders share the resolver's
    link walk and are found by its rules: a checkout it recognises by
    ``src/axiom_corpus`` or ``.axiom/corpus-locks`` on disk, with any inherited
    ``GIT_*`` variables followed. Only the path as given is walked, so a
    checkout whose own link leads to this path, and a link the resolver does
    not recognise, are not found (the threat model's stated limits 15 and 11).
    ``memo`` keeps physical holders by directory across calls. An ``OSError``
    from git, such as no ``git`` on ``PATH``, propagates.
    """
    spelled = path if path.is_absolute() else Path.cwd() / path
    physical = Path(os.path.realpath(spelled))
    places, _ = _standing_places(spelled, physical, None)
    return frozenset(checkout for checkout, _ in places), _physical_holder(physical, memo)


def _physical_holder(physical: Path, memo: dict[Path, Path | None] | None) -> Path | None:
    """The checkout that holds ``physical``, by git toplevel and HEAD, or None."""
    directory = _existing_ancestor(physical)
    if not directory.is_dir():
        directory = directory.parent
    if memo is not None and directory in memo:
        return memo[directory]
    holder: Path | None = None
    found = _git(directory, "rev-parse", "--show-toplevel")
    if found.returncode == 0:
        top = Path(os.fsdecode(found.stdout.rstrip(b"\n")))
        listing = _git(
            top, "ls-tree", "-z", "--full-tree", "--name-only", "HEAD", "--", f"{_SELECTORS_PATH}/"
        )
        if listing.returncode == 0 and any(
            directory_name == _SELECTORS_PATH and filename.endswith(".json")
            for directory_name, _, filename in (
                os.fsdecode(entry).rpartition("/") for entry in listing.stdout.split(b"\0") if entry
            )
        ):
            holder = top
    if memo is not None:
        memo[directory] = holder
    return holder


def guard_scope_artifacts(
    paths: Iterable[Path],
    *,
    releases_dir: Path,
    rewritten: Iterable[Path] = (),
    holders_of: Iterable[Path] = (),
) -> tuple[Path, ...]:
    """Refuse aliased scope artifact paths and return the other holders' selector inventories.

    ``paths`` are the scope artifact paths a tool reads or writes, spelled
    through the corpus it uses; ``rewritten`` are the files among them it
    rewrites in place. It opens no file and raises ``ValueError``, in order:

    1. when a path resolves to a path whose last four parts (the artifact
       kind or ``ingest-manifests``, jurisdiction, document class and version
       file or directory) differ from its own: a symlink or a directory alias
       makes it another scope's artifact;
    2. when a path passes a link at a checkout's guarded place and resolves
       into no checkout: no inventory can say what that directory holds, so
       to share a corpus kept elsewhere, make that directory part of an
       axiom-corpus checkout;
    3. when a rewritten file has more than one link (a hard link).

    It returns the ``manifests/releases`` of each checkout that
    ``checkouts_holding`` finds for ``paths`` and for each path in
    ``holders_of`` (such as the working directory or a selector file),
    de-duplicated by realpath and sorted, leaving out ``releases_dir``. It
    first refuses ``releases_dir`` and each holder's ``manifests/releases``
    when either it or its parent directory is a symlink or holds a ``.git``
    entry, so a holder whose selectors directory links to another checkout's,
    or holds a nested repository or a gitfile, is refused, not dropped as a
    duplicate or read at another repository's HEAD. A holder is found by the
    toplevel git names for the path, so with a ``core.worktree`` setting it is
    the directory git names (the threat model's stated limit 11).
    Link holders are found by the resolver's rules and the physical holder by
    HEAD; only the paths as given are walked, so a checkout whose own link
    leads into these paths, and a link the resolver does not recognise, are
    not found (the threat model's stated limits 15 and 11). The caller reads
    each returned inventory with the same refusal it applied to
    ``releases_dir``.
    """
    memo: dict[Path, Path | None] = {}
    holders: list[Path] = []
    for path in paths:
        spelled = path if path.is_absolute() else Path.cwd() / path
        physical = Path(os.path.realpath(spelled))
        if physical.parts[-4:] != spelled.parts[-4:]:
            raise ValueError(f"scope artifact resolves to another path: {spelled} -> {physical}")
        links, physical_holder = checkouts_holding(spelled, memo=memo)
        if links and physical_holder is None:
            raise ValueError(
                "scope artifact leads through a link outside every axiom-corpus checkout: "
                f"{spelled} -> {physical}; no tracked selectors say whether it is a base"
            )
        holders.extend(links)
        if physical_holder is not None:
            holders.append(physical_holder)
    for path in rewritten:
        spelled = path if path.is_absolute() else Path.cwd() / path
        try:
            status = os.stat(spelled)
        except FileNotFoundError:
            continue
        if status.st_nlink > 1:
            raise ValueError(
                f"scope artifact shares its file with another path: {spelled} "
                f"({status.st_nlink} links)"
            )
    for path in holders_of:
        links, physical_holder = checkouts_holding(path, memo=memo)
        holders.extend(links)
        if physical_holder is not None:
            holders.append(physical_holder)
    _refuse_selector_directory_link(releases_dir)
    seen = {os.path.realpath(releases_dir)}
    inventories: list[Path] = []
    for checkout in holders:
        inventory = checkout / "manifests" / "releases"
        _refuse_selector_directory_link(inventory)
        real = os.path.realpath(inventory)
        if real in seen:
            continue
        seen.add(real)
        inventories.append(inventory)
    return tuple(sorted(inventories, key=str))


def _link_target(path: Path) -> tuple[Path, str, os.stat_result | None]:
    """``path`` as the caller passed it, its realpath, and its status when it exists."""
    spelled = path if path.is_absolute() else Path.cwd() / path
    try:
        status: os.stat_result | None = os.stat(spelled)
    except FileNotFoundError:
        status = None
    return path, os.path.realpath(spelled), status


def _same_entry(
    real: str, status: os.stat_result | None, target: tuple[Path, str, os.stat_result | None]
) -> bool:
    """Equal realpaths, or two existing paths with one status (a hard link, a case alias)."""
    _, target_real, target_status = target
    if real == target_real:
        return True
    return (
        status is not None and target_status is not None and os.path.samestat(status, target_status)
    )


def _within(real: str, directory: str) -> bool:
    return real == directory or real.startswith(directory.rstrip(os.sep) + os.sep)


def refuse_links_into_bases(
    *,
    corpus: Path,
    bases: Iterable[ScopeKey],
    rewritten: Iterable[Path] = (),
    moved: Iterable[Path] = (),
    ingest_manifests: Path | None = None,
) -> None:
    """Refuse a file the caller changes that is also a base's artifact through a link.

    Refuses when a file the caller rewrites, moves or unlinks is also the
    provisions, inventory, coverage, ingest manifest or sources of a base in
    ``bases``, through a symlink, a directory alias or a hard link. Only the
    bases passed are compared, and only at their paths in ``corpus`` and
    ``ingest_manifests``: a base that no selector the caller read marks, and a
    base's file in another directory, are not seen (stated limits 3 and 15).
    Nothing is compared with a file the caller creates (stated limit 18).

    ``rewritten`` are the files the caller rewrites in place or unlinks;
    ``moved`` are the directories it moves; ``ingest_manifests`` is the
    directory of ingest manifests whose files it unlinks, or None. A base's
    file matches a rewritten file when their realpaths are equal or both
    exist with one status, and a moved directory when its realpath equals or
    lies under the directory's. With ``moved`` given, a base's sources
    directory matches a moved directory when its realpath equals, lies under
    or contains the directory's, or both exist with one status; otherwise each
    symlink below it is compared with every moved directory (equal or under)
    and every rewritten file (equal). The first match raises ``ValueError``
    naming the caller's path, the base and the artifact. It opens no file.
    """
    rewritten_targets = [_link_target(path) for path in rewritten]
    moved_targets = [_link_target(path) for path in moved]
    for key in sorted(set(bases)):
        jurisdiction, document_class, version = key
        files = [
            (artifact, corpus / artifact / jurisdiction / document_class / f"{version}{suffix}")
            for artifact, suffix in _BASE_FILES
        ]
        if ingest_manifests is not None:
            files.append(
                (
                    "ingest manifest",
                    ingest_manifests / jurisdiction / document_class / f"{version}.json",
                )
            )
        for artifact, base_path in files:
            _, real, status = _link_target(base_path)
            for target in rewritten_targets:
                if _same_entry(real, status, target):
                    raise ValueError(
                        f"{target[0]} is also {_label(key)}'s {artifact} through a link"
                    )
            for target in moved_targets:
                if _within(real, target[1]):
                    raise ValueError(
                        f"{target[0]} is also {_label(key)}'s {artifact} through a link"
                    )
        if not moved_targets:
            continue
        sources = corpus / "sources" / jurisdiction / document_class / version
        _, sources_real, sources_status = _link_target(sources)
        for target in moved_targets:
            if (
                _within(sources_real, target[1])
                or _within(target[1], sources_real)
                or (
                    sources_status is not None
                    and target[2] is not None
                    and os.path.samestat(sources_status, target[2])
                )
            ):
                raise ValueError(f"{target[0]} is also {_label(key)}'s sources through a link")
        if not os.path.isdir(sources):
            continue
        for root, directories, filenames in os.walk(sources, followlinks=False):
            for entry in (*directories, *filenames):
                path = os.path.join(root, entry)
                if not os.path.islink(path):
                    continue
                entry_real = os.path.realpath(path)
                for target in moved_targets:
                    if _within(entry_real, target[1]):
                        raise ValueError(
                            f"{target[0]} is also {_label(key)}'s sources through a link"
                        )
                for target in rewritten_targets:
                    if entry_real == target[1]:
                        raise ValueError(
                            f"{target[0]} is also {_label(key)}'s sources through a link"
                        )


def refuse_tracked_bases_as_primary(
    scopes: Iterable[ReleaseScope],
    tracked_bases: Collection[ScopeKey],
    *,
    selector: str,
) -> None:
    """Refuse every primary scope in ``scopes`` that ``tracked_bases`` holds.

    ``tracked_bases`` is the set ``tracked_base_scopes`` returns. A scope
    that a tracked selector marks as a base is selected only as a base, so
    this raises ``SuccessorError`` naming ``selector`` and each such scope,
    sorted. Base scopes in ``scopes`` are not checked.
    """
    refused = sorted(
        {scope.key for scope in scopes if not scope.is_base and scope.key in tracked_bases}
    )
    if refused:
        raise SuccessorError(
            f"{selector} selects a tracked base scope as a primary scope: "
            + ", ".join(_label(key) for key in refused)
            + '; a scope that a tracked selector marks "layer": "base" is selected only '
            "as a base"
        )
