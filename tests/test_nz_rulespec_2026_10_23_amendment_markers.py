from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import (
    WITHDRAWN_SCOPES_PATH,
    WithdrawnScope,
    load_withdrawn_scopes,
)
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from scripts.repro.nz_rulespec_2026_10_23_amendment_markers import (
    BASE_RELEASE,
    NEW_SCOPE,
    OLD_SCOPE,
    RELEASE,
    build_release,
    select_scopes,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"
Key = tuple[str, str, str]


def _scope(key: Key) -> dict[str, str]:
    return {"jurisdiction": key[0], "document_class": key[1], "version": key[2]}


def _payload(name: str) -> dict:
    return json.loads((RELEASE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_changes_exactly_one_scope_and_preserves_the_quality_profile() -> None:
    base, release = _payload(BASE_RELEASE), _payload(RELEASE)
    expected = [
        {**scope, "version": NEW_SCOPE[2]} if scope == _scope(OLD_SCOPE) else scope
        for scope in base["scopes"]
    ]
    assert len(base["scopes"]) == len(release["scopes"]) == 9
    assert release["scopes"] == expected
    assert _scope(OLD_SCOPE) not in release["scopes"]
    assert release["scopes"].count(_scope(NEW_SCOPE)) == 1
    assert {k: v for k, v in release.items() if k not in {"scopes", "name", "description"}} == {
        k: v for k, v in base.items() if k not in {"scopes", "name", "description"}
    }
    assert "publish-only pin release for rulespec-nz; do not activate it" in release["description"]
    assert ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json").name == RELEASE


def test_selector_selects_no_withdrawn_scope() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    release = ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json")
    assert not {scope.key for scope in release.scopes} & withdrawn.keys()


def test_exact_scope_delta_keeps_concurrent_nz_statute_versions() -> None:
    """Follow the FS pilot's exact-delta check while retaining NZ's scope order."""
    base = _payload(BASE_RELEASE)["scopes"]
    selected = select_scopes(base, {})
    base_keys = [
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in base
    ]
    selected_keys = [
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in selected
    ]
    retained_statutes = {
        ("nz", "statute", "2026-06-16-rulespec-nz-pco"),  # Principal Act.
        ("nz", "statute", "2026-07-19-rulespec-nz-pco"),
        ("nz", "statute", "2026-07-25-rulespec-nz-pco"),
    }

    assert len(base_keys) == len(selected_keys) == 9
    assert set(base_keys) - set(selected_keys) == {OLD_SCOPE}
    assert set(selected_keys) - set(base_keys) == {NEW_SCOPE}
    assert {key for key in selected_keys if key[:2] == ("nz", "statute")} == (
        retained_statutes | {NEW_SCOPE}
    )
    assert [key for key in selected_keys if key != NEW_SCOPE] == [
        key for key in base_keys if key != OLD_SCOPE
    ]
    assert selected_keys.index(NEW_SCOPE) == base_keys.index(OLD_SCOPE)
    assert selected == _payload(RELEASE)["scopes"]


_KEY = st.tuples(
    st.sampled_from(["nz", "nz-wgn", "us", "uk"]),
    st.sampled_from(["statute", "regulation", "guidance", "district-plan"]),
    st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,6}", fullmatch=True),
)


@settings(max_examples=300, deadline=None)
@given(keys=st.lists(_KEY, max_size=30, unique=True), position=st.integers(0, 30))
def test_for_any_base_only_the_named_scope_is_swapped(keys: list[Key], position: int) -> None:
    """Every eligible base keeps its order and values, with exactly one substitution."""
    keys = [key for key in keys if key not in {OLD_SCOPE, NEW_SCOPE}]
    index = min(position, len(keys))
    keys.insert(index, OLD_SCOPE)
    base = [_scope(key) for key in keys]
    # Extra values must survive too, including values on the replaced scope.
    for i, scope in enumerate(base):
        scope["label"] = str(i)
    original = [dict(scope) for scope in base]

    out = select_scopes(base, {})

    assert base == original
    assert len(out) == len(base)
    assert out[:index] == base[:index]
    assert out[index] == {**base[index], "version": NEW_SCOPE[2]}
    assert out[index + 1 :] == base[index + 1 :]
    assert sum(before != after for before, after in zip(base, out, strict=True)) == 1


@pytest.mark.parametrize("base", [[], [_scope(("nz", "regulation", OLD_SCOPE[2]))]])
def test_missing_predecessor_is_rejected(base: list[dict[str, str]]) -> None:
    with pytest.raises(ValueError, match="base release must select nz/statute/"):
        select_scopes(base, {})


def test_duplicate_base_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate scopes"):
        select_scopes([_scope(OLD_SCOPE), _scope(OLD_SCOPE)], {})


def test_already_selected_successor_is_rejected() -> None:
    with pytest.raises(ValueError, match="already exists"):
        select_scopes([_scope(OLD_SCOPE), _scope(NEW_SCOPE)], {})


@pytest.mark.parametrize("key", [NEW_SCOPE, ("nz", "guidance", "2026-07-25-rulespec-nz-guidance")])
def test_withdrawn_selected_scope_is_rejected(key: Key) -> None:
    entry = WithdrawnScope(
        scope=ReleaseScope(*key),
        withdrawn_on="2026-10-22",
        listed_on="2026-10-22",
        decision="test mutation",
        reason="test mutation",
        run_note="test mutation",
    )
    base = [_scope(OLD_SCOPE)] + ([_scope(key)] if key != NEW_SCOPE else [])
    with pytest.raises(ValueError, match=f"withdrawn scope {'/'.join(key)}"):
        select_scopes(base, {key: entry})
