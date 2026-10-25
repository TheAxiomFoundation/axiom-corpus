from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.uk_rulespec_2026_10_25_pe_child_definitions import (
    ADDITIONS,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _keys(release: str) -> list[tuple[str, str, str]]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return [_key(scope) for scope in payload["scopes"]]


def _lock(scope: dict[str, str]) -> Path:
    return (
        ROOT
        / ".axiom/corpus-locks"
        / scope["jurisdiction"]
        / scope["document_class"]
        / f"{scope['version']}.json"
    )


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_is_the_pin_plus_exactly_the_two_scopes() -> None:
    base, release = _keys(BASE_RELEASE), _keys(RELEASE)
    assert set(release) == set(base) | {_key(scope) for scope in ADDITIONS}
    assert len(release) == len(base) + 2 == 193
    assert release == sorted(release)


@pytest.mark.parametrize("scope", ADDITIONS, ids=lambda scope: scope["document_class"])
def test_each_added_scope_is_locked_and_not_withdrawn(scope: dict[str, str]) -> None:
    assert _lock(scope).is_file(), f"{_key(scope)} must be signed and locked"
    assert _key(scope) not in load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)


def test_it_selects_no_withdrawn_scope() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    assert not [key for key in _keys(RELEASE) if key in withdrawn]


def test_selector_loads_and_keeps_the_quality_profile() -> None:
    release = ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json")
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    ours = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text(encoding="utf-8"))
    assert release.name == RELEASE
    assert ours["quality_profile"] == base["quality_profile"]


_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["guidance", "manual", "regulation", "statute"]),
        "jurisdiction": st.sampled_from(["uk", "uk-leeds", "uk-wakefield", "uk-wirral"]),
        "version": st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
    }
)


@settings(max_examples=200, deadline=None)
@given(
    scopes=st.lists(_SCOPE, max_size=25, unique_by=_key),
    preselected=st.sets(st.integers(min_value=0, max_value=len(ADDITIONS) - 1), max_size=2),
)
def test_build_release_adds_exactly_the_two_scopes_to_any_base(
    tmp_path_factory: pytest.TempPathFactory, scopes: list[dict[str, str]], preselected: set[int]
) -> None:
    """For any duplicate-free base: output = base + ADDITIONS, sorted, nothing dropped;
    a base that already holds any addition is refused."""
    scopes = [*scopes, *(dict(ADDITIONS[i]) for i in sorted(preselected))]
    release_dir = tmp_path_factory.mktemp("releases")
    base = {"description": "base", "name": BASE_RELEASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{BASE_RELEASE}.json").write_text(json.dumps(base), encoding="utf-8")
    if preselected:
        with pytest.raises(ValueError):
            build_release(release_dir=release_dir)
        return
    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_key(scope) for scope in output["scopes"]]
    assert identities == sorted(identities)
    assert sorted(identities) == sorted([*map(_key, scopes), *map(_key, ADDITIONS)])
    assert output["name"] == RELEASE
    assert output["quality_profile"] == "q"
