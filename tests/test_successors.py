"""Shared successor composer: base scopes carried unchanged, refusals, and a golden cut.

The golden test reproduces a committed selector byte for byte from its
predecessor. The synthetic predecessors carry base scopes, which no tracked
selector does yet, so the carry-forward and refusal tests build their own
layered selector files and load them through ``ReleaseManifest.load``.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import successors
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
        _compose(predecessor)
    # Passing the names, even none, still works without the directory.
    assert _compose(predecessor, tracked=()).name == SUCCESSOR_NAME
    assert _compose(predecessor, tracked=[PREDECESSOR_NAME]).name == SUCCESSOR_NAME


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


def test_tracked_base_scopes_loads_every_tracked_selector() -> None:
    bases = tracked_base_scopes(RELEASE_DIR)

    assert all(isinstance(key, tuple) and len(key) == 3 for key in bases)
