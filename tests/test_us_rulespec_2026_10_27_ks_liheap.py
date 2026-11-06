from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.us_rulespec_2026_10_27_ks_liheap import (
    ADDITIONS,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"
SUPERSEDED = "us-rulespec-2026-10-23-ks-liheap"
# The superseded selector's base held the older NYC Administrative Code capture; the pin
# line has since moved to 2026-09-28, which this release keeps.
OLDER_NYC = ("us-ny", "statute", "2026-06-05-nyc-admin-code")
# The base replaced these three eCFR scopes with section-text successors (axiom-corpus#945),
# which this release keeps.
REPLACED_BY_BASE = {
    ("us", "regulation", "2026-06-18-title-47-part-54-r2026-07-15-self-contained"),
    ("us", "regulation", "2026-06-24-title-45-part-1302"),
    ("us", "regulation", "2026-07-13-recovery-r2026-07-17-dedup"),
}

# Literal, so a change to the reproducer's constants cannot also change what is checked.
EXPECTED_ADDITIONS = {
    ("us", "guidance", "2026-10-02-hhs-poverty-2024-2025"),
    ("us", "statute", "2026-09-13-liheap-statute-chapter-94-title-42"),
    ("us-ks", "manual", "2026-10-02-ks-lieap-historical"),
    ("us-ks", "policy", "2026-09-10"),
    ("us-ks", "policy", "2026-09-14-liheap-benefit-matrix"),
    ("us-ks", "policy", "2026-10-02-ks-liheap-matrix-fy2025"),
    ("us-ks", "policy", "2026-10-02-ks-liheap-plan-fy2025"),
}


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


def _rows(key: tuple[str, str, str]) -> list[dict]:
    jurisdiction, document_class, version = key
    path = ROOT / "data/corpus/provisions" / jurisdiction / document_class / f"{version}.jsonl"
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_reproducer_constants_are_the_expected_delta() -> None:
    assert {_key(scope) for scope in ADDITIONS} == EXPECTED_ADDITIONS


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_is_the_base_plus_the_kansas_scopes() -> None:
    base, release = _keys(BASE_RELEASE), _keys(RELEASE)
    assert set(release) == set(base) | EXPECTED_ADDITIONS
    assert not set(base) & EXPECTED_ADDITIONS
    assert len(release) == len(base) + 7 == 283
    assert release == sorted(release)


def test_it_carries_everything_the_superseded_selector_added() -> None:
    """Nothing of us-rulespec-2026-10-23-ks-liheap is lost except scopes the pin line has
    since replaced: its older NYC capture and the three pre-section-text eCFR scopes."""
    superseded, release = set(_keys(SUPERSEDED)), set(_keys(RELEASE))
    assert superseded - release == {OLDER_NYC} | REPLACED_BY_BASE
    assert ("us-ny", "statute", "2026-09-28-nyc-admin-code") in release
    assert not REPLACED_BY_BASE & set(_keys(BASE_RELEASE))


@pytest.mark.parametrize("scope", ADDITIONS, ids=lambda scope: "/".join(_key(scope)))
def test_each_added_scope_is_locked_and_not_withdrawn(scope: dict[str, str]) -> None:
    assert _lock(scope).is_file(), f"{_key(scope)} must be signed and locked"
    assert _key(scope) not in load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)


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


def test_cited_kansas_and_federal_paths_are_selected() -> None:
    """The Kansas encoding request cites the October 2024 income table and 42 USC 8624(b)(2)(B)."""
    keesm = {
        row["citation_path"]: row
        for row in _rows(("us-ks", "manual", "2026-10-02-ks-lieap-historical"))
    }
    table = keesm["us-ks/manual/dcf/keesm/2024-10-01/keesm13360/block-1"]["body"]
    assert all(amount in table for amount in ("1,882.50", "6,590.00", "672.50"))
    statute = {
        row["citation_path"]
        for row in _rows(("us", "statute", "2026-09-13-liheap-statute-chapter-94-title-42"))
    }
    assert "us/statute/42/8624/b/2/B" in statute


def test_build_release_refuses_a_base_with_a_duplicate_scope(tmp_path: Path) -> None:
    scope = {"document_class": "statute", "jurisdiction": "us-ny", "version": "2026-01-01-a"}
    base = {
        "description": "base",
        "name": BASE_RELEASE,
        "quality_profile": "q",
        "scopes": [scope, scope],
    }
    (tmp_path / f"{BASE_RELEASE}.json").write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate scopes"):
        build_release(release_dir=tmp_path)


_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["guidance", "manual", "policy", "statute"]),
        "jurisdiction": st.sampled_from(["us", "us-ks", "us-mt", "us-ny"]),
        "version": st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
    }
)


@settings(max_examples=200, deadline=None)
@given(
    scopes=st.lists(_SCOPE, max_size=25, unique_by=_key),
    preselected=st.sets(st.integers(min_value=0, max_value=len(ADDITIONS) - 1), max_size=4),
)
def test_build_release_adds_on_any_base(
    tmp_path_factory: pytest.TempPathFactory,
    scopes: list[dict[str, str]],
    preselected: set[int],
) -> None:
    """For any duplicate-free base that holds no addition: output = base + ADDITIONS, sorted,
    nothing dropped. A base that already holds an addition is refused."""
    scopes = [*scopes, *(dict(ADDITIONS[i]) for i in sorted(preselected))]
    release_dir = tmp_path_factory.mktemp("releases")
    base = {"description": "base", "name": BASE_RELEASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{BASE_RELEASE}.json").write_text(json.dumps(base), encoding="utf-8")
    if preselected:
        with pytest.raises(ValueError, match="already selects"):
            build_release(release_dir=release_dir)
        return
    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_key(scope) for scope in output["scopes"]]
    assert identities == sorted(identities)
    assert sorted(identities) == sorted([*map(_key, scopes), *map(_key, ADDITIONS)])
    assert output["name"] == RELEASE
    assert output["quality_profile"] == "q"
