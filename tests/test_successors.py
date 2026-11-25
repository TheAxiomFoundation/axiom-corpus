"""Shared successor composer: base scopes carried unchanged, refusals, and a golden cut.

The golden test reproduces a committed selector byte for byte from its
predecessor. The synthetic predecessors carry base scopes, which no tracked
selector does yet, so the carry-forward and refusal tests build their own
layered selector files and load them through ``ReleaseManifest.load``.

The tracked-selector tests build small checkouts with ``make_checkout`` and
check that a checkout's tracked selectors are the files committed at HEAD,
whatever its disk holds, while any other directory is read from disk as
given. The byte-rule tests check that a cut under a tracked selector's name
must reproduce that selector's file byte for byte.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import successors
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import DocumentClass
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    LAYER_BASE,
    LAYER_PRIMARY,
    ReleaseManifest,
    ReleaseScope,
    ScopeKey,
    parse_release_scope,
)
from axiom_corpus.corpus.selector_lineage import declared_predecessor
from axiom_corpus.corpus.successors import (
    SuccessorError,
    compose_successor,
    render_selector,
    tracked_base_scopes,
)
from axiom_corpus.release.manifest import selector_sha256

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"

# Literal, so a change elsewhere cannot also change what the golden test checks.
GOLDEN_PREDECESSOR = "us-rulespec-2026-10-27-ks-liheap"
GOLDEN_SUCCESSOR = "us-rulespec-2026-11-11-cms-w6-federal-guidance"
GOLDEN_ADDED: ScopeKey = ("us", "guidance", "2026-10-06-w6-federal-cms-guidance")
# The first Kansas LIHEAP cut, which the golden predecessor's description also names.
KS_LIHEAP_FIRST_CUT = "us-rulespec-2026-10-23-ks-liheap"
UNTRACKED_SUCCESSOR = "us-rulespec-2099-01-01-composer-check"

PREDECESSOR_NAME = "zz-rulespec-2026-11-01-layered"
SUCCESSOR_NAME = "zz-rulespec-2026-11-02-layered"
DESCRIPTION = f"Successor to {PREDECESSOR_NAME}; it keeps every base scope."

BASE_STATUTE = ReleaseScope("us", "statute", "2026-05-01-uscode", layer=LAYER_BASE)
BASE_REGULATION = ReleaseScope("us", "regulation", "2026-05-01-ecfr", layer=LAYER_BASE)
PRIMARY_STATUTE = ReleaseScope("us", "statute", "2026-10-01-26-usc-1")
PRIMARY_REGULATION = ReleaseScope("us", "regulation", "2026-10-02-7-cfr-273")
PRIMARY_GUIDANCE = ReleaseScope("us", "guidance", "2026-10-03-snap-memo")
LAYERED_SCOPES = (
    BASE_STATUTE,
    BASE_REGULATION,
    PRIMARY_STATUTE,
    PRIMARY_REGULATION,
    PRIMARY_GUIDANCE,
)
NEW_FORM: ScopeKey = ("us", "form", "2026-11-02-new-form")


def _write_selector(path: Path, name: str, scopes: tuple[ReleaseScope, ...], **extra: Any) -> Path:
    """Write a selector by hand, independently of ``render_selector``."""
    raw_scopes = []
    for scope in scopes:
        raw = {
            "jurisdiction": scope.jurisdiction,
            "document_class": scope.document_class,
            "version": scope.version,
        }
        if scope.is_base:
            raw["layer"] = "base"
        raw_scopes.append(raw)
    payload = {"name": name, "description": f"Fixture selector {name}.", **extra}
    payload["scopes"] = raw_scopes
    path.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")
    return path


def _layered_predecessor(directory: Path) -> ReleaseManifest:
    path = _write_selector(
        directory / f"{PREDECESSOR_NAME}.json",
        PREDECESSOR_NAME,
        LAYERED_SCOPES,
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
    )
    return ReleaseManifest.load(path)


def _compose(predecessor: ReleaseManifest, **changes: Any) -> ReleaseManifest:
    changes.setdefault("name", SUCCESSOR_NAME)
    changes.setdefault("description", DESCRIPTION)
    # The synthetic predecessors are not tracked selectors, so the default
    # inventory would refuse them; a test of that default passes tracked=None.
    changes.setdefault("tracked", ())
    # Reading every tracked selector on each call would slow the property test;
    # a test of the default tracked bases passes tracked_bases=None.
    changes.setdefault("tracked_bases", frozenset())
    return compose_successor(predecessor, **changes)


def _mapping_bytes(scope: ReleaseScope) -> bytes:
    return json.dumps(scope.to_selector_mapping(), sort_keys=True).encode("utf-8")


def _tracked_names() -> frozenset[str]:
    """The tracked selector names, as a repro script passes them."""
    return frozenset(path.stem for path in RELEASE_DIR.glob("*.json"))


# Golden reproduction of a committed cut.


def test_golden_reproduces_committed_cms_w6_selector_bytes() -> None:
    committed_path = RELEASE_DIR / f"{GOLDEN_SUCCESSOR}.json"
    predecessor = ReleaseManifest.load(RELEASE_DIR / f"{GOLDEN_PREDECESSOR}.json")
    committed = ReleaseManifest.load(committed_path)
    # The committed cut is exactly its predecessor plus the one added scope.
    assert set(committed.scope_keys) == set(predecessor.scope_keys) | {GOLDEN_ADDED}
    assert GOLDEN_ADDED not in predecessor.scope_keys
    assert committed.description is not None
    tracked = _tracked_names()

    successor = compose_successor(
        predecessor,
        name=committed.name,
        description=committed.description,
        add=[GOLDEN_ADDED],
        tracked=tracked,
    )

    assert render_selector(successor).encode("utf-8") == committed_path.read_bytes()
    assert successor == committed
    assert selector_sha256(successor) == selector_sha256(committed)
    assert successor.quality_profile == predecessor.quality_profile
    assert declared_predecessor(successor, tracked) == GOLDEN_PREDECESSOR


# The description resolves to the predecessor against every tracked selector name.


FIRST_CUT_NAMED_FIRST = (
    f"Adds one scope to the Kansas LIHEAP scopes first cut in {KS_LIHEAP_FIRST_CUT}; "
    f"successor to {GOLDEN_PREDECESSOR}."
)
PREDECESSOR_NAMED_FIRST = (
    f"Successor to {GOLDEN_PREDECESSOR}; it adds one scope to the Kansas LIHEAP "
    f"scopes first cut in {KS_LIHEAP_FIRST_CUT}."
)
NAMED_FIRST_REFUSAL = (
    f"must name its predecessor {GOLDEN_PREDECESSOR} before the tracked "
    f"selector {KS_LIHEAP_FIRST_CUT}"
)


def _compose_golden_addition(description: str, **tracked: Any) -> ReleaseManifest:
    predecessor = ReleaseManifest.load(RELEASE_DIR / f"{GOLDEN_PREDECESSOR}.json")
    return compose_successor(
        predecessor,
        name=UNTRACKED_SUCCESSOR,
        description=description,
        add=[GOLDEN_ADDED],
        **tracked,
    )


# With no tracked argument the composer reads the repository's tracked selector names.
@pytest.mark.parametrize("pass_tracked", [True, False], ids=["tracked-passed", "tracked-default"])
@pytest.mark.parametrize(
    ("description", "refused"),
    [
        pytest.param(FIRST_CUT_NAMED_FIRST, True, id="other-tracked-selector-named-first"),
        pytest.param(PREDECESSOR_NAMED_FIRST, False, id="predecessor-named-first"),
    ],
)
def test_description_resolves_to_the_predecessor_among_tracked_selectors(
    description: str, refused: bool, pass_tracked: bool
) -> None:
    tracked = _tracked_names()
    assert {GOLDEN_PREDECESSOR, KS_LIHEAP_FIRST_CUT} <= tracked
    assert UNTRACKED_SUCCESSOR not in tracked
    arguments = {"tracked": tracked} if pass_tracked else {}

    if refused:
        with pytest.raises(SuccessorError, match=NAMED_FIRST_REFUSAL):
            _compose_golden_addition(description, **arguments)
        return
    successor = _compose_golden_addition(description, **arguments)
    assert declared_predecessor(successor, tracked) == GOLDEN_PREDECESSOR


def test_default_releases_dir_is_this_checkouts_selectors() -> None:
    # An import from another checkout would read that checkout's selectors instead.
    assert successors.DEFAULT_RELEASES_DIR == RELEASE_DIR


def test_default_tracked_names_are_read_from_the_releases_dir_at_each_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    releases = tmp_path / "releases"
    releases.mkdir()
    shutil.copy(RELEASE_DIR / f"{GOLDEN_PREDECESSOR}.json", releases)
    monkeypatch.setattr(successors, "DEFAULT_RELEASES_DIR", releases)

    # The first cut is not tracked here, so the predecessor is the first tracked name.
    successor = _compose_golden_addition(FIRST_CUT_NAMED_FIRST)
    assert declared_predecessor(successor, {GOLDEN_PREDECESSOR}) == GOLDEN_PREDECESSOR

    shutil.copy(RELEASE_DIR / f"{KS_LIHEAP_FIRST_CUT}.json", releases)
    with pytest.raises(SuccessorError, match=NAMED_FIRST_REFUSAL):
        _compose_golden_addition(FIRST_CUT_NAMED_FIRST)


@pytest.mark.parametrize("state", ["missing", "no-selector"])
def test_default_tracked_names_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    releases = tmp_path / "releases"
    if state == "no-selector":
        releases.mkdir()
        (releases / "README.md").write_text("Not a selector.\n", encoding="utf-8")
    monkeypatch.setattr(successors, "DEFAULT_RELEASES_DIR", releases)
    predecessor = _layered_predecessor(tmp_path)

    with pytest.raises(FileNotFoundError, match="pass tracked"):
        _compose(predecessor, tracked=None)
    # Passing the names, even none, still works without the directory.
    assert _compose(predecessor, tracked=()).name == SUCCESSOR_NAME
    assert _compose(predecessor, tracked=[PREDECESSOR_NAME]).name == SUCCESSOR_NAME


PLACEHOLDER_REFUSAL = r"placeholder\.json is not a selector file"
NOT_HELD_REFUSAL = f"does not hold the predecessor {PREDECESSOR_NAME} as given"


@pytest.mark.parametrize(
    ("layout", "error", "message"),
    [
        pytest.param("placeholder-only", ValueError, PLACEHOLDER_REFUSAL, id="placeholder-only"),
        pytest.param(
            "placeholder-beside-predecessor",
            ValueError,
            PLACEHOLDER_REFUSAL,
            id="placeholder-beside-predecessor",
        ),
        pytest.param(
            "predecessor-absent", SuccessorError, NOT_HELD_REFUSAL, id="predecessor-absent"
        ),
        pytest.param(
            "predecessor-differs", SuccessorError, NOT_HELD_REFUSAL, id="predecessor-differs"
        ),
    ],
)
def test_default_inventory_must_hold_the_predecessor_as_selector_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
    error: type[Exception],
    message: str,
) -> None:
    releases = tmp_path / "releases"
    releases.mkdir()
    monkeypatch.setattr(successors, "DEFAULT_RELEASES_DIR", releases)
    predecessor = _layered_predecessor(tmp_path)
    if layout.startswith("placeholder"):
        # A directory whose name ends in .json is not a selector.
        (releases / "placeholder.json").mkdir()
    if layout == "placeholder-beside-predecessor":
        assert _layered_predecessor(releases) == predecessor
    if layout == "predecessor-absent":
        _write_selector(
            releases / "zz-rulespec-2026-10-01-plain.json",
            "zz-rulespec-2026-10-01-plain",
            (PRIMARY_STATUTE,),
        )
    if layout == "predecessor-differs":
        _write_selector(releases / f"{PREDECESSOR_NAME}.json", PREDECESSOR_NAME, (PRIMARY_STATUTE,))

    with pytest.raises(error, match=message) as raised:
        _compose(predecessor, tracked=None)
    assert type(raised.value) is error


def test_explicit_tracked_replaces_the_default_names() -> None:
    # The repository tracks the first cut, so the default names refuse this
    # description. Names passed explicitly replace them, even while the
    # default directory is readable.
    with pytest.raises(SuccessorError, match=NAMED_FIRST_REFUSAL):
        _compose_golden_addition(FIRST_CUT_NAMED_FIRST)
    for tracked in ((), [GOLDEN_PREDECESSOR]):
        successor = _compose_golden_addition(FIRST_CUT_NAMED_FIRST, tracked=tracked)
        assert successor.name == UNTRACKED_SUCCESSOR


def test_releases_dir_names_the_destination_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default = tmp_path / "a"
    destination = tmp_path / "b"
    default.mkdir()
    destination.mkdir()
    shutil.copy(RELEASE_DIR / f"{GOLDEN_PREDECESSOR}.json", default)
    for name in (GOLDEN_PREDECESSOR, KS_LIHEAP_FIRST_CUT):
        shutil.copy(RELEASE_DIR / f"{name}.json", destination)
    monkeypatch.setattr(successors, "DEFAULT_RELEASES_DIR", default)

    # Without releases_dir the default inventory decides. It lacks the first
    # cut, so this description passes: the residual the docstring names.
    assert _compose_golden_addition(FIRST_CUT_NAMED_FIRST).name == UNTRACKED_SUCCESSOR
    # The destination tracks the first cut, so its names refuse the description.
    with pytest.raises(SuccessorError, match=NAMED_FIRST_REFUSAL):
        _compose_golden_addition(FIRST_CUT_NAMED_FIRST, releases_dir=destination)
    successor = _compose_golden_addition(PREDECESSOR_NAMED_FIRST, releases_dir=destination)
    assert successor.name == UNTRACKED_SUCCESSOR


def test_default_releases_dir_does_not_depend_on_the_working_directory(
    tmp_path: Path,
) -> None:
    # A script run from another directory still reads this checkout's selectors.
    source_root = Path(successors.__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(source_root), environment.get("PYTHONPATH", "")) if part
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from axiom_corpus.corpus import successors; print(successors.DEFAULT_RELEASES_DIR)",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(result.stdout.strip()) == RELEASE_DIR.resolve()


# Rendering pins JSON's ASCII escapes for non-ASCII text.


def test_render_selector_escapes_non_ascii_description(tmp_path: Path) -> None:
    predecessor = _layered_predecessor(tmp_path)
    # Built with chr() so this file stays ASCII: u-umlaut, section sign, em dash.
    description = (
        f"Nachfolger von {PREDECESSOR_NAME} {chr(0xFC)}ber {chr(0xA7)} 1 {chr(0x2014)} "
        "keeps every base."
    )
    successor = _compose(predecessor, description=description, add=[NEW_FORM])

    rendered = render_selector(successor)

    backslash = chr(92)
    assert rendered.isascii()
    assert (
        f'  "description": "Nachfolger von {PREDECESSOR_NAME} {backslash}u00fcber '
        f'{backslash}u00a7 1 {backslash}u2014 keeps every base.",'
    ) in rendered.splitlines()
    path = tmp_path / f"{SUCCESSOR_NAME}.json"
    path.write_text(rendered, encoding="utf-8")
    assert ReleaseManifest.load(path).description == description


# Carry-forward of base scopes on a layered predecessor.


def test_primary_changes_carry_each_base_unchanged(tmp_path: Path) -> None:
    predecessor = _layered_predecessor(tmp_path)
    by_key = {scope.key: scope for scope in predecessor.scopes}
    replaced_to: ScopeKey = ("us", "statute", "2026-11-02-26-usc-1")

    successor = _compose(
        predecessor,
        add=[NEW_FORM],
        replace={PRIMARY_STATUTE.key: replaced_to[2]},
        remove=[PRIMARY_GUIDANCE.key],
    )

    carried = {scope.key: scope for scope in successor.scopes if scope.is_base}
    assert set(carried) == {BASE_STATUTE.key, BASE_REGULATION.key}
    for key, scope in carried.items():
        assert scope is by_key[key]
        assert scope == by_key[key]
        assert _mapping_bytes(scope) == _mapping_bytes(by_key[key])
        assert scope.to_selector_mapping()["layer"] == LAYER_BASE
    assert {scope.key for scope in successor.scopes if not scope.is_base} == {
        PRIMARY_REGULATION.key,
        replaced_to,
        NEW_FORM,
    }
    assert list(successor.scope_keys) == sorted(successor.scope_keys)
    assert successor.quality_profile == COMPLETE_EXPRESSION_DATES_PROFILE

    rendered = json.loads(render_selector(successor))
    assert [scope for scope in rendered["scopes"] if "layer" in scope] == [
        BASE_REGULATION.to_selector_mapping(),
        BASE_STATUTE.to_selector_mapping(),
    ]


def test_add_base_adds_a_base_for_a_pair_without_one(tmp_path: Path) -> None:
    predecessor = _layered_predecessor(tmp_path)
    guidance_base: ScopeKey = ("us", "guidance", "2026-05-01-guidance-base")

    successor = _compose(predecessor, add_base=[guidance_base])

    bases = {scope.key: scope for scope in successor.scopes if scope.is_base}
    assert set(bases) == {BASE_STATUTE.key, BASE_REGULATION.key, guidance_base}
    assert bases[guidance_base].layer == LAYER_BASE
    assert set(successor.scope_keys) == set(predecessor.scope_keys) | {guidance_base}


def test_layered_successor_round_trips_through_its_rendered_selector(tmp_path: Path) -> None:
    predecessor = _layered_predecessor(tmp_path)
    successor = _compose(predecessor, add=[NEW_FORM])
    path = tmp_path / f"{SUCCESSOR_NAME}.json"
    path.write_text(render_selector(successor), encoding="utf-8")

    loaded = ReleaseManifest.load(path)

    assert loaded == successor
    assert selector_sha256(loaded) == selector_sha256(successor)
    assert render_selector(loaded) == path.read_text(encoding="utf-8")


def test_parse_release_scope_reads_the_canonical_layer_encoding() -> None:
    where = Path("<test>")
    for scope in (BASE_STATUTE, PRIMARY_STATUTE):
        assert parse_release_scope(scope.to_selector_mapping(), manifest_path=where) == scope
    explicit_primary = {**PRIMARY_STATUTE.to_selector_mapping(), "layer": LAYER_PRIMARY}
    with pytest.raises(ValueError, match="layer must be 'base' or absent"):
        parse_release_scope(explicit_primary, manifest_path=where)


# Refusals: each raises SuccessorError with its own message.


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        pytest.param(
            {"replace": {BASE_STATUTE.key: "2026-11-02-uscode"}},
            "base scopes are carried unchanged",
            id="base-in-replace",
        ),
        pytest.param(
            {"remove": [BASE_REGULATION.key]},
            "base scopes are carried unchanged",
            id="base-in-remove",
        ),
        pytest.param(
            {"add": [PRIMARY_GUIDANCE.key]},
            "already selects us/guidance/2026-10-03-snap-memo as a primary scope",
            id="add-selected-primary",
        ),
        pytest.param(
            {"add": [BASE_STATUTE.key]},
            "already selects us/statute/2026-05-01-uscode as a base scope",
            id="add-selected-base",
        ),
        pytest.param(
            {"add_base": [PRIMARY_GUIDANCE.key]},
            "already selects us/guidance/2026-10-03-snap-memo as a primary scope",
            id="add-base-selected-primary",
        ),
        pytest.param(
            {"replace": {NEW_FORM: "2026-11-03-new-form"}},
            "is not a primary scope of",
            id="replace-non-member",
        ),
        pytest.param(
            {"remove": [NEW_FORM]},
            "is not a primary scope of",
            id="remove-non-member",
        ),
        pytest.param(
            {"replace": {PRIMARY_STATUTE.key: PRIMARY_STATUTE.version}},
            "must be a different version",
            id="replacement-equals-old",
        ),
        pytest.param(
            {"replace": {PRIMARY_STATUTE.key: BASE_STATUTE.version}},
            "is already selected by",
            id="replacement-already-selected-as-base",
        ),
        pytest.param(
            {
                "replace": {
                    PRIMARY_REGULATION.key: "2026-11-02-7-cfr-273",
                    BASE_REGULATION.key: "2026-11-02-ecfr",
                }
            },
            "base scopes are carried unchanged",
            id="base-among-replacements",
        ),
        pytest.param(
            {"add": [PRIMARY_GUIDANCE.key], "remove": [PRIMARY_GUIDANCE.key]},
            "may appear in only one of add, replace, remove and add_base",
            id="add-and-remove",
        ),
        pytest.param(
            {
                "replace": {PRIMARY_GUIDANCE.key: "2026-11-02-snap-memo"},
                "remove": [PRIMARY_GUIDANCE.key],
            },
            "may appear in only one of add, replace, remove and add_base",
            id="replace-and-remove",
        ),
        pytest.param(
            {"add": [NEW_FORM], "add_base": [NEW_FORM]},
            "may appear in only one of add, replace, remove and add_base",
            id="add-and-add-base",
        ),
        pytest.param(
            {"add": [NEW_FORM, NEW_FORM]},
            "may appear in only one of add, replace, remove and add_base",
            id="add-twice",
        ),
        pytest.param(
            {"add_base": [("us", "statute", "2026-11-02-uscode")]},
            "already has a base scope for us/statute",
            id="add-base-pair-has-base",
        ),
        pytest.param(
            {
                "add_base": [
                    ("us", "guidance", "2026-05-01-guidance-base"),
                    ("us", "guidance", "2026-05-02-guidance-base"),
                ]
            },
            "add_base names more than one base for us/guidance",
            id="add-base-two-for-one-pair",
        ),
        pytest.param(
            {
                "add": [("us", "statute", "2026-11-02-26-usc-1")],
                "replace": {PRIMARY_STATUTE.key: "2026-11-02-26-usc-1"},
            },
            "would be selected more than once",
            id="replacement-collides-with-add",
        ),
        pytest.param(
            {"add": [("us", "not-a-class", "2026-11-02-x")]},
            "invalid document_class",
            id="invalid-scope",
        ),
        pytest.param(
            {"description": "Successor to a selector this test does not name."},
            f"must name its predecessor {PREDECESSOR_NAME}",
            id="description-omits-predecessor",
        ),
        pytest.param(
            {"description": f"Successor to {PREDECESSOR_NAME}-x, a longer name."},
            f"must name its predecessor {PREDECESSOR_NAME}",
            id="description-names-only-a-longer-run",
        ),
        pytest.param(
            {"name": PREDECESSOR_NAME},
            "must have a new name",
            id="successor-reuses-predecessor-name",
        ),
        pytest.param(
            {"name": "Bad Name"},
            "lowercase alphanumeric segments separated by single hyphens",
            id="invalid-name",
        ),
        pytest.param(
            {"name": "current"},
            "Release name 'current' is reserved",
            id="reserved-name-current",
        ),
        pytest.param(
            {"add": ("us", "guidance", "v")},
            "add must name each scope as a",
            id="bare-triple-in-add",
        ),
        pytest.param(
            {"remove": [["us", "guidance", "2026-10-03-snap-memo"]]},
            "remove must name each scope as a",
            id="list-in-remove",
        ),
        pytest.param(
            {"add_base": [("us", "guidance")]},
            "add_base must name each scope as a",
            id="pair-in-add-base",
        ),
        pytest.param(
            {"replace": {("us", "statute", 1): "2026-11-02-26-usc-1"}},
            "replace must name each scope as a",
            id="non-string-part-in-replace-key",
        ),
        pytest.param(
            {"replace": {PRIMARY_STATUTE.key: ["2026-11-02-26-usc-1"]}},
            "replace must map us/statute/2026-10-01-26-usc-1 to a version string",
            id="non-string-replacement-version",
        ),
        pytest.param(
            {"tracked": PREDECESSOR_NAME},
            "tracked must be a collection of selector names, not one string",
            id="tracked-is-one-string",
        ),
    ],
)
def test_refusals(tmp_path: Path, changes: dict[str, Any], message: str) -> None:
    predecessor = _layered_predecessor(tmp_path)
    before = sorted(path.name for path in tmp_path.iterdir())

    with pytest.raises(SuccessorError, match=message):
        _compose(predecessor, **changes)

    assert sorted(path.name for path in tmp_path.iterdir()) == before


# A base that another cut replaced is still a tracked base, so no cut may select it as primary.
REPLACED_BASE: ScopeKey = ("us", "statute", "2026-04-29-uscode")
TRACKED_BASE_REFUSAL = (
    f"{SUCCESSOR_NAME} selects a tracked base scope as a primary scope: "
    'us/statute/2026-04-29-uscode; a scope that a tracked selector marks "layer": "base" '
    "is selected only as a base"
)


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"add": [REPLACED_BASE]}, id="re-add-a-replaced-base"),
        pytest.param(
            {"replace": {PRIMARY_STATUTE.key: REPLACED_BASE[2]}}, id="replace-into-a-tracked-base"
        ),
        pytest.param({"add": [NEW_FORM, REPLACED_BASE]}, id="tracked-base-among-additions"),
    ],
)
def test_refuses_a_tracked_base_as_a_new_primary_scope(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    predecessor = _layered_predecessor(tmp_path)
    tracked_bases = frozenset({REPLACED_BASE, BASE_STATUTE.key, BASE_REGULATION.key})

    with pytest.raises(SuccessorError) as raised:
        _compose(predecessor, tracked_bases=tracked_bases, **changes)

    assert str(raised.value) == TRACKED_BASE_REFUSAL


def test_default_tracked_bases_are_read_only_when_a_cut_adds_a_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replaced = tmp_path / "replaced"
    replaced.mkdir()
    predecessor = _layered_predecessor(replaced)
    _write_selector(
        replaced / "zz-rulespec-2026-10-01-replaced.json",
        "zz-rulespec-2026-10-01-replaced",
        (ReleaseScope(*REPLACED_BASE, layer=LAYER_BASE), PRIMARY_STATUTE),
    )
    monkeypatch.setattr(successors, "DEFAULT_RELEASES_DIR", replaced)

    # _compose passes tracked_bases=frozenset(); None reads the default directory.
    with pytest.raises(SuccessorError) as raised:
        _compose(predecessor, add=[REPLACED_BASE], tracked_bases=None)
    assert str(raised.value) == TRACKED_BASE_REFUSAL
    assert NEW_FORM in _compose(predecessor, add=[NEW_FORM], tracked_bases=None).scope_keys

    monkeypatch.setattr(successors, "DEFAULT_RELEASES_DIR", tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        _compose(predecessor, add=[NEW_FORM], tracked_bases=None)
    assert NEW_FORM in _compose(predecessor, add=[NEW_FORM], tracked_bases=()).scope_keys
    # A cut that adds no primary scope reads no selector.
    assert _compose(predecessor, tracked_bases=None).name == SUCCESSOR_NAME
    # releases_dir names the inventory the bases are read from, as it does for the names.
    with pytest.raises(SuccessorError) as raised:
        _compose(predecessor, add=[REPLACED_BASE], tracked_bases=None, releases_dir=replaced)
    assert str(raised.value) == TRACKED_BASE_REFUSAL


def test_add_base_may_name_a_tracked_base_for_a_pair_without_one(tmp_path: Path) -> None:
    # A restore brings a tracked base back as a base, which the refusal leaves alone.
    predecessor = _layered_predecessor(tmp_path)
    guidance_base: ScopeKey = ("us", "guidance", "2026-05-01-guidance-base")

    successor = _compose(
        predecessor, add_base=[guidance_base], tracked_bases=frozenset({guidance_base})
    )

    assert guidance_base in {scope.key for scope in successor.scopes if scope.is_base}


def test_refuses_a_successor_with_no_scope(tmp_path: Path) -> None:
    path = _write_selector(
        tmp_path / f"{PREDECESSOR_NAME}.json",
        PREDECESSOR_NAME,
        (PRIMARY_GUIDANCE,),
    )
    predecessor = ReleaseManifest.load(path)

    with pytest.raises(SuccessorError, match="would select no scope"):
        _compose(predecessor, remove=[PRIMARY_GUIDANCE.key])


# Property: any allowed set of primary changes keeps the bases and applies exactly the changes.

_PAIRS = (("us", "statute"), ("us", "regulation"), ("us", "guidance"), ("us-ca", "statute"))
_VERSIONS = ("2026-01-01-a", "2026-02-01-b", "2026-03-01-c", "2026-04-01-d")


@st.composite
def _layered_cases(
    draw: st.DrawFn,
) -> tuple[ReleaseManifest, list[ScopeKey], dict[ScopeKey, str], list[ScopeKey]]:
    scopes: list[ReleaseScope] = []
    for index, (jurisdiction, document_class) in enumerate(_PAIRS):
        present = draw(
            st.lists(st.sampled_from(_VERSIONS), unique=True, min_size=int(index == 0), max_size=3)
        )
        base = draw(st.none() | st.sampled_from(present)) if present else None
        scopes.extend(
            ReleaseScope(
                jurisdiction,
                document_class,
                version,
                layer=LAYER_BASE if version == base else LAYER_PRIMARY,
            )
            for version in present
        )
    predecessor = ReleaseManifest(
        name=PREDECESSOR_NAME,
        scopes=tuple(scopes),
        description=f"Fixture selector {PREDECESSOR_NAME}.",
        quality_profile=draw(st.sampled_from((None, COMPLETE_EXPRESSION_DATES_PROFILE))),
    )

    taken = set(predecessor.scope_keys)
    replace: dict[ScopeKey, str] = {}
    remove: list[ScopeKey] = []
    for scope in predecessor.scopes:
        if scope.is_base:
            continue
        action = draw(st.sampled_from(("keep", "remove", "replace")))
        if action == "remove":
            remove.append(scope.key)
            continue
        free = [v for v in _VERSIONS if (scope.jurisdiction, scope.document_class, v) not in taken]
        if action == "replace" and free:
            version = draw(st.sampled_from(free))
            replace[scope.key] = version
            taken.add((scope.jurisdiction, scope.document_class, version))
    unselected = [
        (jurisdiction, document_class, version)
        for jurisdiction, document_class in _PAIRS
        for version in _VERSIONS
        if (jurisdiction, document_class, version) not in taken
    ]
    add = draw(st.lists(st.sampled_from(unselected), unique=True, max_size=3)) if unselected else []
    return predecessor, add, replace, remove


@settings(max_examples=100, deadline=None)
@given(_layered_cases())
def test_allowed_primary_changes_keep_bases_and_apply_exactly(
    case: tuple[ReleaseManifest, list[ScopeKey], dict[ScopeKey, str], list[ScopeKey]],
) -> None:
    predecessor, add, replace, remove = case
    pred_bases = [scope for scope in predecessor.scopes if scope.is_base]
    pred_primaries = {scope.key for scope in predecessor.scopes if not scope.is_base}
    replacements = {(key[0], key[1], version) for key, version in replace.items()}
    expected_primaries = (pred_primaries - set(remove) - set(replace)) | set(add) | replacements

    if not pred_bases and not expected_primaries:
        with pytest.raises(SuccessorError, match="would select no scope"):
            _compose(predecessor, add=add, replace=replace, remove=remove)
        return

    successor = _compose(predecessor, add=add, replace=replace, remove=remove)

    assert sorted(
        (scope for scope in successor.scopes if scope.is_base), key=lambda s: s.key
    ) == sorted(pred_bases, key=lambda s: s.key)
    assert {scope.key for scope in successor.scopes if not scope.is_base} == expected_primaries
    assert list(successor.scope_keys) == sorted(successor.scope_keys)
    assert successor.quality_profile == predecessor.quality_profile

    rendered = render_selector(successor)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"{SUCCESSOR_NAME}.json"
        path.write_text(rendered, encoding="utf-8")
        loaded = ReleaseManifest.load(path)
    assert loaded == successor
    assert render_selector(loaded) == rendered
    again = _compose(predecessor, add=add, replace=replace, remove=remove)
    assert selector_sha256(loaded) == selector_sha256(successor) == selector_sha256(again)


# Tracked base scopes.


def test_tracked_base_scopes_reads_layers_from_selector_files(tmp_path: Path) -> None:
    releases = tmp_path / "releases"
    releases.mkdir()
    _write_selector(releases / f"{PREDECESSOR_NAME}.json", PREDECESSOR_NAME, LAYERED_SCOPES)
    _write_selector(
        releases / "zz-rulespec-2026-10-01-plain.json",
        "zz-rulespec-2026-10-01-plain",
        (PRIMARY_STATUTE, PRIMARY_GUIDANCE),
    )
    (releases / "README.md").write_text("Not a selector.\n", encoding="utf-8")

    assert tracked_base_scopes(releases) == frozenset({BASE_STATUTE.key, BASE_REGULATION.key})


def test_tracked_base_scopes_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        tracked_base_scopes(tmp_path / "missing")
    releases = tmp_path / "releases"
    releases.mkdir()
    (releases / "zz-rulespec-2026-10-01-broken.json").write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        tracked_base_scopes(releases)


@pytest.mark.parametrize(
    ("layout", "error", "message"),
    [
        pytest.param(
            "empty-directory", FileNotFoundError, "No release selector in", id="empty-directory"
        ),
        pytest.param(
            "no-selector-file", FileNotFoundError, "No release selector in", id="no-selector-file"
        ),
        pytest.param(
            "placeholder-directory", ValueError, PLACEHOLDER_REFUSAL, id="placeholder-directory"
        ),
    ],
)
def test_tracked_base_scopes_refuses_an_inventory_without_selector_files(
    tmp_path: Path, layout: str, error: type[Exception], message: str
) -> None:
    # Reading no selector would report no base, so every base would pass as primary.
    releases = tmp_path / "releases"
    releases.mkdir()
    if layout == "no-selector-file":
        (releases / "README.md").write_text("Not a selector.\n", encoding="utf-8")
    if layout == "placeholder-directory":
        (releases / "placeholder.json").mkdir()

    with pytest.raises(error, match=message) as raised:
        tracked_base_scopes(releases)
    assert type(raised.value) is error


def test_tracked_base_scopes_loads_every_tracked_selector() -> None:
    bases = tracked_base_scopes(RELEASE_DIR)

    assert all(isinstance(key, tuple) and len(key) == 3 for key in bases)


# A checkout's tracked selectors are the ones committed at HEAD, whatever its disk holds.

HEAD_P: ScopeKey = ("us", "statute", "p")
HEAD_B: ScopeKey = ("us", "regulation", "b")
HEAD_Q: ScopeKey = ("us", "guidance", "q")


def _payload(
    name: str, scopes: tuple[tuple[ScopeKey, bool], ...], description: str | None = None
) -> dict[str, object]:
    """A selector mapping; each scope is ``(key, is_base)``."""
    raw_scopes: list[dict[str, str]] = []
    for key, is_base in scopes:
        raw = {"jurisdiction": key[0], "document_class": key[1], "version": key[2]}
        if is_base:
            raw["layer"] = LAYER_BASE
        raw_scopes.append(raw)
    payload: dict[str, object] = {"name": name, "scopes": raw_scopes}
    if description is not None:
        payload["description"] = description
    return payload


HEAD_SELECTORS = {
    "earlier": _payload("earlier", ((HEAD_P, False),)),
    "pred": _payload("pred", ((HEAD_P, False),), "Successor to earlier."),
    "layered": _payload("layered", ((HEAD_P, False), (HEAD_B, True)), "Successor to pred."),
}


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clear_resolver_cache() -> None:
    from axiom_corpus.corpus import resolver

    resolver._repo_root_for_dir.cache_clear()


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        pytest.param("full", {HEAD_B}, id="full"),
        pytest.param("sparse-hidden", {HEAD_B}, id="sparse-hidden"),
        pytest.param("skip-worktree-removed", {HEAD_B}, id="skip-worktree-removed"),
        pytest.param("unstaged-removal", {HEAD_B}, id="unstaged-removal"),
        pytest.param("dirty-edit", {HEAD_B}, id="dirty-edit"),
        pytest.param("untracked-scratch", {HEAD_B}, id="untracked-scratch"),
        pytest.param("staged-uncommitted", {HEAD_B}, id="staged-uncommitted"),
        pytest.param("cached-removal", {HEAD_B}, id="cached-removal"),
        pytest.param("manifests-excluded", {HEAD_B}, id="manifests-excluded"),
        pytest.param("linked-worktree", {HEAD_B}, id="linked-worktree"),
        pytest.param("linked-worktree-removed", {HEAD_B}, id="linked-worktree-removed"),
        pytest.param("deleted-on-the-branch", set(), id="deleted-on-the-branch"),
        pytest.param("git-env-dir-index", {HEAD_B}, id="git-env-dir-index"),
        pytest.param("git-env-work-tree", {HEAD_B}, id="git-env-work-tree"),
    ],
)
def test_tracked_selectors_are_read_as_committed_at_head(
    make_checkout: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
    expected: set[ScopeKey],
) -> None:
    from tests.conftest import fixture_git

    repo = make_checkout("repo", HEAD_SELECTORS)
    releases = repo / "manifests" / "releases"
    layered = releases / "layered.json"
    read = releases
    if layout == "sparse-hidden":
        fixture_git(
            repo, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/releases/layered.json"
        )
        _clear_resolver_cache()
        assert not layered.exists()
    elif layout == "skip-worktree-removed":
        fixture_git(repo, "update-index", "--skip-worktree", "manifests/releases/layered.json")
        layered.unlink()
    elif layout in {"unstaged-removal", "git-env-dir-index", "git-env-work-tree"}:
        layered.unlink()
    elif layout == "dirty-edit":
        _write_payload(layered, _payload("layered", ((HEAD_P, False),), "Successor to pred."))
    elif layout == "untracked-scratch":
        _write_payload(releases / "scratch.json", _payload("scratch", ((HEAD_P, True),)))
    elif layout == "staged-uncommitted":
        _write_payload(releases / "new.json", _payload("new", ((HEAD_Q, True),)))
        fixture_git(repo, "add", "--", "manifests/releases/new.json")
    elif layout == "cached-removal":
        fixture_git(repo, "rm", "-q", "--cached", "manifests/releases/layered.json")
        assert layered.exists()
    elif layout == "manifests-excluded":
        fixture_git(repo, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
        _clear_resolver_cache()
        assert not releases.exists()
    elif layout == "linked-worktree":
        fixture_git(repo, "worktree", "add", "-q", "../wt")
        _write_payload(releases / "later.json", _payload("later", ((HEAD_Q, True),)))
        fixture_git(repo, "add", "--", "manifests/releases/later.json")
        fixture_git(repo, "commit", "-q", "-m", "Main commits a later base")
        read = tmp_path / "wt" / "manifests" / "releases"
    elif layout == "linked-worktree-removed":
        fixture_git(repo, "worktree", "add", "-q", "../wt")
        (tmp_path / "wt" / "manifests" / "releases" / "layered.json").unlink()
        read = tmp_path / "wt" / "manifests" / "releases"
    elif layout == "deleted-on-the-branch":
        fixture_git(repo, "rm", "-q", "--", "manifests/releases/layered.json")
        fixture_git(repo, "commit", "-q", "-m", "Delete the layered selector")
    if layout.startswith("git-env"):
        other = make_checkout("other", {"plain": _payload("plain", ((HEAD_P, False),))})
        # Exported after every fixture git command, as a hook or a shell might.
        monkeypatch.setenv("GIT_DIR", str(other / ".git"))
        monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))
        if layout == "git-env-work-tree":
            monkeypatch.setenv("GIT_WORK_TREE", str(other))

    assert successors.tracked_base_scopes(read) == frozenset(expected)


@pytest.mark.parametrize(
    "layout", ["committed-symlink", "committed-directory", "unborn-head", "git-missing"]
)
def test_tracked_selectors_refuse_what_head_cannot_hold_as_a_selector(
    make_checkout: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    from tests.conftest import fixture_git

    if layout == "unborn-head":
        repo = tmp_path / "unborn"
        releases = repo / "manifests" / "releases"
        releases.mkdir(parents=True)
        for name, payload in HEAD_SELECTORS.items():
            _write_payload(releases / f"{name}.json", payload)
        fixture_git(repo, "init", "-q", "-b", "main")
        fixture_git(repo, "add", "--", "manifests")
        with pytest.raises(FileNotFoundError, match="Cannot list the selectors of"):
            successors.tracked_base_scopes(releases)
        return

    repo = make_checkout("repo", HEAD_SELECTORS)
    releases = repo / "manifests" / "releases"
    if layout == "committed-symlink":
        (releases / "zz-link.json").symlink_to("layered.json")
        fixture_git(repo, "add", "--", "manifests/releases/zz-link.json")
        fixture_git(repo, "commit", "-q", "-m", "Commit a link")
        with pytest.raises(ValueError, match=r"zz-link\.json is not a selector file"):
            successors.tracked_base_scopes(releases)
    elif layout == "committed-directory":
        (releases / "dir.json").mkdir()
        (releases / "dir.json" / "x").write_text("x\n", encoding="utf-8")
        fixture_git(repo, "add", "--", "manifests/releases/dir.json/x")
        fixture_git(repo, "commit", "-q", "-m", "Commit a directory")
        with pytest.raises(ValueError, match=r"dir\.json is not a selector file"):
            successors.tracked_base_scopes(releases)
    elif layout == "git-missing":
        plain = tmp_path / "plain"
        plain.mkdir()
        _write_payload(plain / "layered.json", HEAD_SELECTORS["layered"])
        empty = tmp_path / "no-git-here"
        empty.mkdir()
        monkeypatch.setenv("PATH", str(empty))
        with pytest.raises(FileNotFoundError, match="git cannot read the checkout at"):
            successors.tracked_base_scopes(releases)
        # A directory in no checkout is read from disk without git.
        assert successors.tracked_base_scopes(plain) == frozenset({HEAD_B})


# A selector directory reached through a link, spelled with "..", or at which git
# would answer for another repository is refused: git runs in, and the disk shows,
# the directory a path resolves to, so another checkout's HEAD, or a directory no
# HEAD holds, would answer for this checkout's tracked selectors.

LINK_B: ScopeKey = ("us", "statute", "b")
LINK_REFUSAL = "^selector directory leads through a link: "
DOTDOT_REFUSAL = r"^selector directory is spelled with '\.\.': "
GIT_ENTRY_REFUSAL = "^selector directory sits at a git entry: "


def _swap_for_link(path: Path, target: Path) -> None:
    """Replace the directory ``path`` with a symlink to ``target``."""
    shutil.rmtree(path)
    path.symlink_to(target, target_is_directory=True)


def _link_checkouts(make_checkout: Any) -> tuple[Path, Path]:
    """A commits ``a-sel``, which marks ``us/statute/b`` as a base; B's ``b-sel`` marks none."""
    a = make_checkout("a", {"a-sel": _payload("a-sel", ((HEAD_P, False), (LINK_B, True)))})
    b = make_checkout("b", {"b-sel": _payload("b-sel", ((HEAD_P, False),))})
    return a, b


@pytest.mark.parametrize(
    "layout",
    [
        "releases-link",
        "manifests-link",
        "relative-releases-link",
        "relative-manifests-link",
        "chain",
        "sparse-manifests-link",
        "plain-dir-in-unrelated-repo",
        "linked-worktree-to-main",
        "case-alias",
        "outside-spelling",
        "dotdot-releases",
        "dotdot-manifests",
        "full",
        "manifests-excluded-sparse",
        "relative-from-checkout",
        "linked-worktree-real",
    ],
)
def test_a_selector_directory_reached_through_a_link_is_refused(
    make_checkout: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    from tests.conftest import fixture_git

    a, b = _link_checkouts(make_checkout)
    releases = a / "manifests" / "releases"
    directory = releases
    # The link the refusal names; None for a ".." spelling and for a control.
    link: Path | None = None
    refusal: str | None = LINK_REFUSAL
    if layout == "releases-link":
        _swap_for_link(releases, b / "manifests" / "releases")
        link = releases
    elif layout == "manifests-link":
        _swap_for_link(a / "manifests", b / "manifests")
        link = a / "manifests"
    elif layout == "relative-releases-link":
        _swap_for_link(releases, Path("..") / ".." / "b" / "manifests" / "releases")
        link = releases
    elif layout == "relative-manifests-link":
        _swap_for_link(a / "manifests", Path("..") / "b" / "manifests")
        link = a / "manifests"
    elif layout == "chain":
        c = make_checkout("c", {"c-sel": _payload("c-sel", ((HEAD_P, False),))})
        _swap_for_link(c / "manifests", b / "manifests")
        _swap_for_link(a / "manifests", c / "manifests")
        link = a / "manifests"
    elif layout == "sparse-manifests-link":
        fixture_git(a, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
        assert not (a / "manifests").exists()
        (a / "manifests").symlink_to(b / "manifests", target_is_directory=True)
        link = a / "manifests"
    elif layout == "plain-dir-in-unrelated-repo":
        unrelated = tmp_path / "unrelated"
        unrelated.mkdir()
        (unrelated / "README.md").write_text("Not a checkout.\n", encoding="utf-8")
        fixture_git(unrelated, "init", "-q", "-b", "main")
        fixture_git(unrelated, "add", "--", "README.md")
        fixture_git(unrelated, "commit", "-q", "-m", "Unrelated repository")
        (unrelated / "selectors").mkdir()
        _write_payload(unrelated / "selectors" / "x.json", _payload("x", ((HEAD_P, False),)))
        _swap_for_link(releases, unrelated / "selectors")
        link = releases
    elif layout == "linked-worktree-to-main":
        worktree = tmp_path / "wt"
        fixture_git(a, "worktree", "add", "-q", str(worktree))
        _swap_for_link(worktree / "manifests", a / "manifests")
        directory = worktree / "manifests" / "releases"
        link = worktree / "manifests"
    elif layout == "case-alias":
        _swap_for_link(a / "manifests", b / "manifests")
        if not os.path.lexists(a / "Manifests"):
            pytest.skip("the filesystem keeps manifests and Manifests apart")
        directory = a / "Manifests" / "Releases"
        link = a / "Manifests"
    elif layout == "outside-spelling":
        directory = link = tmp_path / "sel"
        directory.symlink_to(releases, target_is_directory=True)
    elif layout == "dotdot-releases":
        directory = releases / ".." / "releases"
        refusal = DOTDOT_REFUSAL
    elif layout == "dotdot-manifests":
        directory = a / "manifests" / ".." / "manifests" / "releases"
        refusal = DOTDOT_REFUSAL
    elif layout == "manifests-excluded-sparse":
        fixture_git(a, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
        assert not (a / "manifests").exists()
        refusal = None
    elif layout == "relative-from-checkout":
        monkeypatch.chdir(a)
        directory = Path("manifests/releases")
        refusal = None
    elif layout == "linked-worktree-real":
        fixture_git(a, "worktree", "add", "-q", str(tmp_path / "wt"))
        directory = tmp_path / "wt" / "manifests" / "releases"
        refusal = None
    else:
        assert layout == "full"
        refusal = None
    _clear_resolver_cache()

    if refusal is None:
        assert successors.tracked_base_scopes(directory) == frozenset({LINK_B})
        assert sorted(successors.tracked_selector_texts(directory)) == ["a-sel"]
        assert successors.tracked_selector_text(directory, "a-sel") is not None
        return
    if link is not None:
        refusal += re.escape(f"{link} -> ")
    with pytest.raises(ValueError, match=refusal):
        successors.tracked_base_scopes(directory)
    with pytest.raises(ValueError, match=refusal):
        successors.tracked_selector_texts(directory)
    with pytest.raises(ValueError, match=refusal):
        successors.tracked_selector_text(directory, "a-sel")


def test_compose_successor_refuses_a_releases_dir_reached_through_a_link(
    make_checkout: Any,
) -> None:
    a, b = _link_checkouts(make_checkout)
    _swap_for_link(a / "manifests", b / "manifests")
    _clear_resolver_cache()
    predecessor = ReleaseManifest.load(b / "manifests" / "releases" / "b-sel.json")

    # Through the link, B's HEAD would answer, and B marks no base.
    with pytest.raises(ValueError, match=LINK_REFUSAL + re.escape(f"{a / 'manifests'} -> ")):
        compose_successor(
            predecessor,
            name="next",
            description="Successor to b-sel.",
            add=[LINK_B],
            releases_dir=a / "manifests" / "releases",
        )


def _toplevel_refusal(top: Path, checkout: Path) -> str:
    return (
        r"^selector directory is not the manifests/releases of the toplevel git names \("
        + re.escape(str(top))
        + r"\), while a \.git entry sits two levels up at "
        + re.escape(str(checkout / ".git"))
    )


def _git_fails_refusal(checkout: Path) -> str:
    return "^git cannot read the checkout at " + re.escape(str(checkout))


def _break_git_config(checkout: Path) -> None:
    """Append a line git cannot parse to the checkout's own configuration."""
    with (checkout / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write("[core\n")


@pytest.mark.parametrize(
    "layout",
    [
        "nested-repo-at-manifests",
        "nested-repo-at-releases",
        "gitfile-at-manifests",
        "core-worktree-redirect",
        "standalone-inside-checkout",
        "standalone-two-below-checkout",
        "ceiling-at-manifests",
        "bare-at-manifests-case",
        "broken-config-case",
        "git-fails-two-below-checkout",
        "full",
        "manifests-excluded-sparse",
        "linked-worktree-real",
        "linked-worktree-manifests-excluded",
        "plain-directory",
        "standalone-three-below-checkout",
        "git-fails-three-below-checkout",
    ],
)
def test_a_selector_directory_git_would_read_elsewhere_is_refused(
    make_checkout: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    from tests.conftest import fixture_git

    a = make_checkout("a", HEAD_SELECTORS)
    other = make_checkout("other", {"plain": _payload("plain", ((HEAD_P, False),))})
    releases = a / "manifests" / "releases"
    directory = releases
    # A refusal (its type and pattern), or what a control reads: the bases and
    # whether "layered" is there.
    refusal: tuple[type[Exception], str] | None = None
    expected: frozenset[ScopeKey] = frozenset({HEAD_B})
    has_layered = True
    clean_status = False

    def hide_manifests_beside_a_plain_selector() -> None:
        fixture_git(a, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
        releases.mkdir(parents=True)
        _write_payload(releases / "plain.json", _payload("plain", ((HEAD_P, False),)))

    def hide_layered() -> None:
        fixture_git(a, "update-index", "--skip-worktree", "manifests/releases/layered.json")
        (releases / "layered.json").unlink()

    def scratch(path: Path) -> Path:
        path.mkdir(parents=True)
        _write_payload(path / "scratch.json", _payload("scratch", ((HEAD_Q, True),)))
        return path

    if layout == "nested-repo-at-manifests":
        hide_manifests_beside_a_plain_selector()
        fixture_git(a / "manifests", "init", "-q")
        refusal = (ValueError, GIT_ENTRY_REFUSAL + re.escape(str(a / "manifests" / ".git")))
        clean_status = True
    elif layout == "nested-repo-at-releases":
        hide_layered()
        fixture_git(releases, "init", "-q")
        refusal = (ValueError, GIT_ENTRY_REFUSAL + re.escape(str(releases / ".git")))
        clean_status = True
    elif layout == "gitfile-at-manifests":
        hide_manifests_beside_a_plain_selector()
        (a / "manifests" / ".git").write_text(f"gitdir: {other / '.git'}\n", encoding="utf-8")
        refusal = (ValueError, GIT_ENTRY_REFUSAL + re.escape(str(a / "manifests" / ".git")))
        clean_status = True
    elif layout == "core-worktree-redirect":
        hide_layered()
        fixture_git(a, "config", "core.worktree", str(other))
        refusal = (FileNotFoundError, _toplevel_refusal(other, a))
    elif layout == "standalone-inside-checkout":
        directory = scratch(a / "scratch-releases")
        refusal = (ValueError, GIT_ENTRY_REFUSAL + re.escape(str(a / ".git")))
    elif layout == "standalone-two-below-checkout":
        directory = scratch(a / "scratch" / "releases")
        refusal = (FileNotFoundError, _toplevel_refusal(a, a))
    elif layout == "ceiling-at-manifests":
        # Exported after every fixture git command; the readers drop it, so HEAD is read.
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(a / "manifests"))
    elif layout == "bare-at-manifests-case":
        fixture_git(a, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
        fixture_git(a, "init", "-q", "--bare", "manifests")
        releases.mkdir()
        _write_payload(releases / "plain.json", _payload("plain", ((HEAD_P, False),)))
        if not os.path.lexists(a / "Manifests"):
            pytest.skip("the filesystem keeps manifests and Manifests apart")
        directory = a / "Manifests" / "Releases"
        refusal = (FileNotFoundError, _git_fails_refusal(a))
        clean_status = True
    elif layout == "broken-config-case":
        hide_layered()
        if not os.path.lexists(a / "Manifests"):
            pytest.skip("the filesystem keeps manifests and Manifests apart")
        _break_git_config(a)
        directory = a / "Manifests" / "Releases"
        refusal = (FileNotFoundError, _git_fails_refusal(a))
    elif layout == "git-fails-two-below-checkout":
        directory = scratch(a / "scratch" / "releases")
        _break_git_config(a)
        refusal = (FileNotFoundError, _git_fails_refusal(a))
    elif layout == "manifests-excluded-sparse":
        fixture_git(a, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
        assert not (a / "manifests").exists()
    elif layout in {"linked-worktree-real", "linked-worktree-manifests-excluded"}:
        worktree = tmp_path / "wt"
        fixture_git(a, "worktree", "add", "-q", str(worktree))
        directory = worktree / "manifests" / "releases"
        if layout == "linked-worktree-manifests-excluded":
            fixture_git(worktree, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
            assert not (worktree / "manifests").exists()
    elif layout == "plain-directory":
        directory = tmp_path / "plain"
        directory.mkdir()
        _write_payload(directory / "layered.json", HEAD_SELECTORS["layered"])
    elif layout == "standalone-three-below-checkout":
        directory = scratch(a / "scratch" / "deeper" / "releases")
        expected, has_layered = frozenset({HEAD_Q}), False
    elif layout == "git-fails-three-below-checkout":
        directory = scratch(a / "scratch" / "deeper" / "releases")
        _break_git_config(a)
        expected, has_layered = frozenset({HEAD_Q}), False
    else:
        assert layout == "full"
    if clean_status:
        assert fixture_git(a, "status", "--porcelain", "--untracked-files=no").stdout == ""
    _clear_resolver_cache()

    if refusal is not None:
        error, pattern = refusal
        with pytest.raises(error, match=pattern):
            successors.tracked_base_scopes(directory)
        with pytest.raises(error, match=pattern):
            successors.tracked_selector_texts(directory)
        with pytest.raises(error, match=pattern):
            successors.tracked_selector_text(directory, "layered")
        return
    assert successors.tracked_base_scopes(directory) == expected
    assert ("layered" in successors.tracked_selector_texts(directory)) is has_layered
    assert (successors.tracked_selector_text(directory, "layered") is not None) is has_layered
    if layout == "linked-worktree-manifests-excluded":
        monkeypatch.chdir(tmp_path / "wt")
        assert successors.tracked_base_scopes(Path("manifests/releases")) == expected


def test_the_composer_reads_committed_names_and_bases_in_a_sparse_checkout(
    make_checkout: Any,
) -> None:
    from tests.conftest import fixture_git

    repo = make_checkout("repo", HEAD_SELECTORS)
    releases = repo / "manifests" / "releases"
    fixture_git(
        repo,
        "sparse-checkout",
        "set",
        "--no-cone",
        "/*",
        "!/manifests/releases/layered.json",
        "!/manifests/releases/earlier.json",
    )
    _clear_resolver_cache()
    assert sorted(path.name for path in releases.iterdir()) == ["pred.json"]
    predecessor = ReleaseManifest.load(releases / "pred.json")

    with pytest.raises(SuccessorError, match="selects a tracked base scope as a primary scope"):
        compose_successor(
            predecessor,
            name="next",
            description="Successor to pred.",
            add=[HEAD_B],
            releases_dir=releases,
        )
    with pytest.raises(
        SuccessorError, match="must name its predecessor pred before the tracked selector earlier"
    ):
        compose_successor(
            predecessor,
            name="next",
            description="Compare earlier, successor to pred.",
            add=[HEAD_Q],
            releases_dir=releases,
        )


def test_a_checkout_without_the_committed_predecessor_says_commit_it_first(
    make_checkout: Any,
) -> None:
    selectors = {name: HEAD_SELECTORS[name] for name in ("earlier", "layered")}
    repo = make_checkout("repo", selectors)
    releases = repo / "manifests" / "releases"
    _write_payload(releases / "pred.json", HEAD_SELECTORS["pred"])
    predecessor = ReleaseManifest.load(releases / "pred.json")

    with pytest.raises(
        SuccessorError, match="as given at HEAD of .*; commit the predecessor's selector first"
    ):
        compose_successor(
            predecessor, name="next", description="Successor to pred.", releases_dir=releases
        )


# A cut under a tracked selector's name must reproduce that file byte for byte.

BYTE_RULE_REFUSAL = (
    r"cut is a tracked selector of .*, and this cut is not its committed file byte for byte"
)
CUT_DESCRIPTION = "Successor to root."


def _byte_rule_selectors() -> tuple[ReleaseManifest, ReleaseManifest]:
    root = ReleaseManifest(
        name="root", scopes=(ReleaseScope(*HEAD_P),), description="Fixture selector root."
    )
    cut = ReleaseManifest(
        name="cut",
        scopes=tuple(
            sorted(
                (ReleaseScope(*HEAD_P), ReleaseScope(*HEAD_B, layer=LAYER_BASE)),
                key=lambda scope: scope.key,
            )
        ),
        description=CUT_DESCRIPTION,
    )
    return root, cut


@pytest.mark.parametrize(
    "case",
    [
        "finding",
        "tracked-names",
        "tracked-empty",
        "default-inventory",
        "drop-the-base",
        "description",
        "add",
        "layout",
        "no-final-newline",
        "reproduce",
        "tracked-without-file",
        "directory",
        "dangling-link",
        "committed-differs",
    ],
)
def test_a_cut_under_a_tracked_name_must_be_its_committed_file_byte_for_byte(
    make_checkout: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    root, cut = _byte_rule_selectors()
    cut_text = render_selector(cut)
    directory = tmp_path / "selectors"
    directory.mkdir()
    (directory / "root.json").write_text(render_selector(root), encoding="utf-8")
    cut_path = directory / "cut.json"
    cut_path.write_text(cut_text, encoding="utf-8")
    # The call that reproduces the committed cut.
    call: dict[str, Any] = {
        "name": "cut",
        "description": CUT_DESCRIPTION,
        "add_base": [HEAD_B],
        "releases_dir": directory,
    }
    refusal: tuple[type[Exception], str] | None = (SuccessorError, BYTE_RULE_REFUSAL)
    if case == "finding":
        # The finding: a re-cut of the committed name that drops its base.
        del call["add_base"]
    elif case == "tracked-names":
        del call["add_base"]
        call["tracked"] = ["root", "cut"]
    elif case == "tracked-empty":
        del call["add_base"]
        call["tracked"] = ()
    elif case == "default-inventory":
        del call["add_base"], call["releases_dir"]
        monkeypatch.setattr(successors, "DEFAULT_RELEASES_DIR", directory)
    elif case == "drop-the-base":
        del call["add_base"]
    elif case == "description":
        call["description"] = CUT_DESCRIPTION + " Amended."
    elif case == "add":
        call["add"] = [HEAD_Q]
    elif case == "layout":
        cut_path.write_text(json.dumps(json.loads(cut_text), indent=4) + "\n", encoding="utf-8")
        assert ReleaseManifest.load(cut_path) == cut
    elif case == "no-final-newline":
        cut_path.write_text(cut_text.removesuffix("\n"), encoding="utf-8")
    elif case == "reproduce":
        refusal = None
    elif case == "tracked-without-file":
        cut_path.unlink()
        call["tracked"] = ["root", "cut"]
        refusal = (SuccessorError, r"holds no cut\.json to compare this cut with")
    elif case == "directory":
        cut_path.unlink()
        cut_path.mkdir()
        call["tracked"] = ()
        refusal = (ValueError, r"cut\.json is not a selector file")
    elif case == "dangling-link":
        cut_path.unlink()
        cut_path.symlink_to(directory / "missing.json")
        call["tracked"] = ()
        refusal = (ValueError, r"cut\.json is not a selector file")
    elif case == "committed-differs":
        repo = make_checkout(
            "repo", {"root": json.loads(render_selector(root)), "cut": json.loads(cut_text)}
        )
        releases = repo / "manifests" / "releases"
        # The working tree drops the base; HEAD still holds it.
        without_base = ReleaseManifest(
            name="cut", scopes=(ReleaseScope(*HEAD_P),), description=CUT_DESCRIPTION
        )
        (releases / "cut.json").write_text(render_selector(without_base), encoding="utf-8")
        del call["add_base"]
        call["releases_dir"] = releases

    if refusal is None:
        successor = compose_successor(root, **call)
        assert render_selector(successor) == cut_path.read_text(encoding="utf-8")
        return
    error, message = refusal
    with pytest.raises(error, match=message):
        compose_successor(root, **call)


def test_the_golden_cut_reproduces_under_the_default_inventory() -> None:
    committed_path = RELEASE_DIR / f"{GOLDEN_SUCCESSOR}.json"
    predecessor = ReleaseManifest.load(RELEASE_DIR / f"{GOLDEN_PREDECESSOR}.json")
    committed = ReleaseManifest.load(committed_path)
    assert committed.description is not None

    successor = compose_successor(
        predecessor, name=committed.name, description=committed.description, add=[GOLDEN_ADDED]
    )

    assert render_selector(successor).encode("utf-8") == committed_path.read_bytes()


# Canonical scope names: what a selector can spell, and nothing that only names its files.


@pytest.mark.parametrize(
    "parts",
    [
        *(
            pytest.param(("us", "statute", version), id=f"version-{name}")
            for name, version in (
                ("trailing-space", "v "),
                ("leading-space", " v"),
                ("tab", "v\t"),
                ("newline", "v\n"),
                ("trailing-slash", "v/"),
                ("leading-slash", "/v"),
                ("colon", "a:b"),
                ("backslash", "a\\b"),
                ("upper-case", "V"),
                ("empty", ""),
                ("dot-dot", ".."),
            )
        ),
        pytest.param(("us ", "statute", "v"), id="jurisdiction-trailing-space"),
        pytest.param(("us", "statute/", "v"), id="document-class-slash"),
        pytest.param(("us", "Statute", "v"), id="document-class-case"),
        pytest.param(("us", "not-a-class", "v"), id="document-class-unknown"),
    ],
)
def test_canonical_scope_key_refuses_a_name_a_selector_cannot_spell(
    parts: tuple[str, str, str],
) -> None:
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        successors.canonical_scope_key(*parts)


_CANONICAL_PART = st.from_regex(r"[a-z0-9][a-z0-9._-]{0,40}", fullmatch=True)


@settings(max_examples=200, deadline=None)
@given(
    jurisdiction=_CANONICAL_PART,
    document_class=st.sampled_from([member.value for member in DocumentClass]),
    version=_CANONICAL_PART,
)
def test_canonical_scope_key_keeps_a_selector_scope_and_its_paths(
    jurisdiction: str, document_class: str, version: str
) -> None:
    key = successors.canonical_scope_key(jurisdiction, document_class, version)

    assert key == (jurisdiction, document_class, version)
    # For a canonical name safe_segment is the identity, so the key names its own files.
    assert (
        CorpusArtifactStore(Path("/r")).provisions_path(jurisdiction, document_class, version)
        == Path("/r/provisions") / jurisdiction / document_class / f"{version}.jsonl"
    )
