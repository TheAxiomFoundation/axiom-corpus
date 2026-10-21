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
from axiom_corpus.release.manifest import selector_sha256
from scripts.repro.us_rulespec_2026_10_20_fs_pilot_reg_e_f import (
    ADDITIONS,
    BASE_RELEASE,
    KEPT,
    RELEASE,
    build_release,
    select_scopes,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"

Key = tuple[str, str, str]


def _key(scope: dict[str, str]) -> Key:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _keys(release: str) -> list[Key]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return [_key(scope) for scope in payload["scopes"]]


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_is_the_base_with_the_registry_applied() -> None:
    """Derived here without the reproducer: drop every withdrawn scope the base selects
    except the kept exceptions, select the dropped scopes' replacements, add Reg E and F."""
    withdrawn = load_withdrawn_scopes(WITHDRAWN_SCOPES_PATH)
    base = set(_keys(BASE_RELEASE))
    dropped = {key for key in base if key in withdrawn and key not in KEPT}
    replacements = {r.key for key in dropped for r in withdrawn[key].replace_with}

    expected = (base - dropped) | replacements | {_key(a) for a in ADDITIONS}
    assert set(_keys(RELEASE)) == expected
    assert len(dropped) == 13
    assert {key for key in base if key in withdrawn} == dropped | set(KEPT)


def test_delta_against_the_pin_is_exact() -> None:
    base, release = set(_keys(BASE_RELEASE)), set(_keys(RELEASE))
    assert len(base) == 274
    assert len(release) == 267
    assert release - base == {
        ("us", "regulation", "2026-10-19-title-12-part-1005"),
        ("us", "regulation", "2026-10-19-title-12-part-1006"),
        ("us-co", "regulation", "2026-07-13-recovery-r2026-09-11-tanf-consolidated"),
        ("us-ny", "statute", "2026-09-14-income-tax-chapter"),
        ("us-sc", "statute", "2026-09-27-sc-act110-with-12-6-520-us-sc-title-12-chapter-6"),
        ("us-ut", "statute", "2026-09-14-income-tax-chapter-title-59"),
    }
    assert base - release == {
        ("us-co", "regulation", "2026-07-13-recovery"),
        ("us-fl", "regulation", "2026-07-13-recovery"),
        ("us-il", "manual", "2026-07-13-recovery-r2026-07-17-dedup"),
        ("us-in", "manual", "2026-07-13-recovery"),
        (
            "us-ny",
            "statute",
            "2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616",
        ),
        ("us-ny", "statute", "2026-07-13-recovery"),
        ("us-sc", "manual", "2026-07-13-recovery"),
        ("us-sc", "regulation", "2026-07-13-recovery"),
        ("us-sc", "statute", "2026-07-13-recovery"),
        ("us-sc", "statute", "2026-07-24-sc-act110-us-sc-title-12-chapter-6"),
        ("us-tn", "regulation", "2026-07-13-recovery"),
        ("us-ut", "manual", "2026-07-13-recovery"),
        ("us-ut", "statute", "2026-07-13-recovery"),
    }


def test_kept_scopes_are_exceptions_pinned_to_this_selector() -> None:
    withdrawn = load_withdrawn_scopes(WITHDRAWN_SCOPES_PATH)
    release = ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json")
    selected = set(_keys(RELEASE))
    for key in KEPT:
        entry = withdrawn[key]
        allowance = entry.allowance_for(release)
        assert allowance is not None and allowance.is_exception
        assert allowance.selector_sha256 == selector_sha256(release)
        assert "axiom-corpus#911" in (allowance.reason or "")
        assert key in selected
        # Their replacements would duplicate citation paths, so none is selected.
        assert not {r.key for r in entry.replace_with} & selected


def test_only_the_kept_scopes_are_withdrawn_in_the_selector() -> None:
    withdrawn = load_withdrawn_scopes(WITHDRAWN_SCOPES_PATH)
    assert {key for key in _keys(RELEASE) if key in withdrawn} == set(KEPT)


_CLASSES = ["guidance", "manual", "regulation", "statute"]
_JURISDICTIONS = ["us", "us-az", "us-me", "us-ny"]
_KEY = st.tuples(
    st.sampled_from(_JURISDICTIONS),
    st.sampled_from(_CLASSES),
    st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,6}", fullmatch=True),
)


def _scope(key: Key) -> dict[str, str]:
    return {"document_class": key[1], "jurisdiction": key[0], "version": key[2]}


def _entry(key: Key, replace_with: list[Key]) -> WithdrawnScope:
    return WithdrawnScope(
        scope=ReleaseScope(*key),
        withdrawn_on="2026-10-03",
        listed_on="2026-10-13",
        decision="test",
        reason="test",
        run_note="test",
        replace_with=tuple(ReleaseScope(*r) for r in replace_with),
    )


@settings(max_examples=300, deadline=None)
@given(data=st.data())
def test_select_scopes_applies_any_registry(data: st.DataObject) -> None:
    """For every duplicate-free base and registry: the result is sorted and unique; it
    keeps every base scope that isn't withdrawn and every kept one; it drops every other
    withdrawn scope and selects that scope's replacements; it adds the additions; and it
    selects nothing else."""
    keys = data.draw(st.lists(_KEY, min_size=0, max_size=30, unique=True))
    split = data.draw(st.integers(min_value=0, max_value=len(keys)))
    base, pool = keys[:split], keys[split:]
    withdrawn_keys = data.draw(st.lists(st.sampled_from(base), unique=True)) if base else []
    kept = tuple(
        data.draw(st.lists(st.sampled_from(withdrawn_keys), unique=True)) if withdrawn_keys else []
    )
    fresh = list(pool)
    additions = tuple(_scope(k) for k in fresh[: data.draw(st.integers(0, min(2, len(fresh))))])
    replacement_pool = [k for k in fresh if _scope(k) not in additions]
    withdrawn = {
        key: _entry(
            key,
            data.draw(st.lists(st.sampled_from(replacement_pool), max_size=2, unique=True))
            if replacement_pool
            else [],
        )
        for key in withdrawn_keys
    }

    out = select_scopes([_scope(k) for k in base], withdrawn, additions=additions, kept=kept)
    out_keys = [_key(s) for s in out]

    assert out_keys == sorted(set(out_keys))
    dropped = {k for k in withdrawn_keys if k not in kept}
    replacements = {r.key for k in dropped for r in withdrawn[k].replace_with}
    expected = (set(base) - dropped) | replacements | {_key(a) for a in additions}
    assert set(out_keys) == expected
    assert not dropped & set(out_keys)


def test_select_scopes_refuses_an_addition_already_in_the_base() -> None:
    base = [dict(ADDITIONS[0])]
    with pytest.raises(ValueError, match="already exists"):
        select_scopes(base, {})


def test_select_scopes_refuses_a_withdrawn_replacement() -> None:
    a = ("us-ny", "statute", "2026-01-01-a")
    b = ("us-ny", "statute", "2026-01-02-b")
    withdrawn = {a: _entry(a, [b]), b: _entry(b, [])}
    with pytest.raises(ValueError, match="itself withdrawn"):
        select_scopes([_scope(a)], withdrawn, additions=(), kept=())
