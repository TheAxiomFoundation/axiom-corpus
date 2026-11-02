from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.us_rulespec_2026_10_29_ecfr_section_text import (
    BASE_RELEASE,
    RELEASE,
    REPLACEMENTS,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"

# Literal, so a change to the reproducer's constants cannot also change what is checked.
EXPECTED_REPLACEMENTS = {
    ("us", "regulation", "2026-06-18-title-47-part-54-r2026-07-15-self-contained"): (
        "us",
        "regulation",
        "2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54",
    ),
    ("us", "regulation", "2026-06-24-title-45-part-1302"): (
        "us",
        "regulation",
        "2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302",
    ),
    ("us", "regulation", "2026-07-13-recovery-r2026-07-17-dedup"): (
        "us",
        "regulation",
        "2026-07-13-recovery-r2026-07-17-dedup-r2026-10-29-ecfr-section-text",
    ),
}
PAIRS = sorted(EXPECTED_REPLACEMENTS.items())


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _scope(key: tuple[str, str, str]) -> dict[str, str]:
    return {"jurisdiction": key[0], "document_class": key[1], "version": key[2]}


def _keys(release: str) -> list[tuple[str, str, str]]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return [_key(scope) for scope in payload["scopes"]]


def _lock(key: tuple[str, str, str]) -> Path:
    return ROOT / ".axiom/corpus-locks" / key[0] / key[1] / f"{key[2]}.json"


def _citation_paths(key: tuple[str, str, str]) -> set[str]:
    path = ROOT / "data/corpus/provisions" / key[0] / key[1] / f"{key[2]}.jsonl"
    with path.open(encoding="utf-8") as handle:
        return {json.loads(line)["citation_path"] for line in handle if line.strip()}


def test_reproducer_constants_are_the_expected_swaps() -> None:
    assert {
        ("us", "regulation", old): ("us", "regulation", new) for old, new in REPLACEMENTS.items()
    } == (EXPECTED_REPLACEMENTS)


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_is_the_base_with_exactly_the_three_swaps() -> None:
    base, release = _keys(BASE_RELEASE), _keys(RELEASE)
    assert set(base) - set(release) == set(EXPECTED_REPLACEMENTS)
    assert set(release) - set(base) == set(EXPECTED_REPLACEMENTS.values())
    assert len(release) == len(base) == 276
    assert release == sorted(release)


def test_selector_never_holds_a_predecessor_with_its_successor() -> None:
    release = set(_keys(RELEASE))
    for old, new in PAIRS:
        assert old not in release and new in release, (old, new)


@pytest.mark.parametrize(
    ("old", "new"), PAIRS, ids=lambda key: key[2] if isinstance(key, tuple) else key
)
def test_each_successor_is_locked_and_not_withdrawn(
    old: tuple[str, str, str], new: tuple[str, str, str]
) -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    assert _lock(old).is_file(), f"{old} must stay locked"
    assert _lock(new).is_file(), f"{new} must be signed and locked"
    assert new not in withdrawn


@pytest.mark.parametrize(
    ("old", "new"), PAIRS, ids=lambda key: key[2] if isinstance(key, tuple) else key
)
def test_each_successor_carries_its_predecessors_citation_paths(
    old: tuple[str, str, str], new: tuple[str, str, str]
) -> None:
    """A swap that changed the path set could orphan a cited path or collide with another scope."""
    assert _citation_paths(new) == _citation_paths(old)


def test_it_selects_no_withdrawn_scope_the_base_does_not() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    assert not {key for key in _keys(RELEASE) if key in withdrawn} - set(_keys(BASE_RELEASE))


KEPT_WITHDRAWN = {"us-me", "us-mi", "us-mn"}  # 2026-07-13 recovery scopes, until rulespec-us#1365


def test_every_withdrawn_scope_it_keeps_has_its_own_exception() -> None:
    """Allowances don't carry forward: each kept withdrawn scope needs an exception for this selector."""
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    release = ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json")
    kept = [key for key in _keys(RELEASE) if key in withdrawn]
    assert {key[0] for key in kept} == KEPT_WITHDRAWN
    for key in kept:
        allowance = withdrawn[key].allowance_for(release)
        assert allowance is not None and allowance.is_exception, key


def test_selector_loads_and_keeps_the_quality_profile() -> None:
    release = ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json")
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    ours = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text(encoding="utf-8"))
    assert release.name == RELEASE
    assert ours["quality_profile"] == base["quality_profile"]
    assert set(ours) == set(base)


def _write_base(release_dir: Path, scopes: list[dict[str, str]]) -> None:
    base = {"description": "base", "name": BASE_RELEASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{BASE_RELEASE}.json").write_text(json.dumps(base), encoding="utf-8")


def test_build_release_refuses_a_base_with_a_duplicate_scope(tmp_path: Path) -> None:
    scopes = [_scope(old) for old in EXPECTED_REPLACEMENTS]
    _write_base(tmp_path, [*scopes, scopes[0]])
    with pytest.raises(ValueError, match="duplicate scopes"):
        build_release(release_dir=tmp_path)


_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["manual", "regulation", "statute"]),
        "jurisdiction": st.sampled_from(["us", "us-me", "us-ny"]),
        "version": st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
    }
)


@settings(max_examples=200, deadline=None)
@given(
    others=st.lists(_SCOPE, max_size=25, unique_by=_key),
    dropped=st.sets(st.integers(min_value=0, max_value=len(PAIRS) - 1), max_size=len(PAIRS)),
    preselected=st.sets(st.integers(min_value=0, max_value=len(PAIRS) - 1), max_size=len(PAIRS)),
)
def test_build_release_swaps_on_any_base(
    tmp_path_factory: pytest.TempPathFactory,
    others: list[dict[str, str]],
    dropped: set[int],
    preselected: set[int],
) -> None:
    """For any duplicate-free base that holds every predecessor and no successor: the output
    replaces exactly the predecessors, keeps every other scope, and is sorted. A base missing a
    predecessor, or already holding a successor, is refused."""
    scopes = [
        *others,
        *(_scope(old) for i, (old, _) in enumerate(PAIRS) if i not in dropped),
        *(_scope(new) for i, (_, new) in enumerate(PAIRS) if i in preselected),
    ]
    release_dir = tmp_path_factory.mktemp("releases")
    _write_base(release_dir, scopes)
    if dropped:
        with pytest.raises(ValueError, match="does not select"):
            build_release(release_dir=release_dir)
        return
    if preselected:
        with pytest.raises(ValueError, match="already selects"):
            build_release(release_dir=release_dir)
        return
    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_key(scope) for scope in output["scopes"]]
    expected = [EXPECTED_REPLACEMENTS.get(_key(scope), _key(scope)) for scope in scopes]
    assert identities == sorted(expected)
    assert output["name"] == RELEASE
    assert output["quality_profile"] == "q"
