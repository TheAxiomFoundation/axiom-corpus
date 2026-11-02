from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.us_rulespec_2026_10_22_ca_concurrent_versions import (
    ADDITION,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"
LOCK = (
    ROOT
    / ".axiom/corpus-locks"
    / ADDITION["jurisdiction"]
    / ADDITION["document_class"]
    / f"{ADDITION['version']}.json"
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _keys(release: str) -> list[tuple[str, str, str]]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return [_key(scope) for scope in payload["scopes"]]


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_is_the_pin_plus_exactly_the_concurrent_versions_scope() -> None:
    base, release = _keys(BASE_RELEASE), _keys(RELEASE)
    assert set(release) == set(base) | {_key(ADDITION)}
    assert len(release) == len(base) + 1 == 268
    assert release == sorted(release)


def test_the_added_scope_is_locked_and_not_withdrawn() -> None:
    assert LOCK.is_file(), "the concurrent-versions scope must be signed and locked (#752)"
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    assert _key(ADDITION) not in withdrawn
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


_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["guidance", "manual", "regulation", "statute"]),
        "jurisdiction": st.sampled_from(["us", "us-az", "us-ca", "us-ny"]),
        "version": st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
    }
)


@settings(max_examples=200, deadline=None)
@given(scopes=st.lists(_SCOPE, max_size=25, unique_by=_key), with_addition=st.booleans())
def test_build_release_adds_exactly_one_scope_to_any_base(
    tmp_path_factory: pytest.TempPathFactory, scopes: list[dict[str, str]], with_addition: bool
) -> None:
    """For any duplicate-free base: output = base + ADDITION, sorted, nothing dropped;
    a base that already holds the addition is refused."""
    if with_addition:
        scopes = [*scopes, dict(ADDITION)]
    release_dir = tmp_path_factory.mktemp("releases")
    base = {"description": "base", "name": BASE_RELEASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{BASE_RELEASE}.json").write_text(json.dumps(base), encoding="utf-8")
    if with_addition:
        with pytest.raises(ValueError):
            build_release(release_dir=release_dir)
        return
    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_key(scope) for scope in output["scopes"]]
    assert identities == sorted(identities)
    assert sorted(identities) == sorted([*map(_key, scopes), _key(ADDITION)])
    assert output["name"] == RELEASE
    assert output["quality_profile"] == "q"
