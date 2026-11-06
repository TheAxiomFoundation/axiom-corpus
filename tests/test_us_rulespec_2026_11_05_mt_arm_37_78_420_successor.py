from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.selector_lineage import declared_predecessor
from scripts.repro.us_rulespec_2026_11_05_mt_arm_37_78_420_successor import (
    BASE_RELEASE,
    PREDECESSOR,
    RELEASE,
    SUCCESSOR,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
RELEASE_DIR = ROOT / "manifests/releases"

# Literal, so a change to the reproducer's constants cannot also change what is checked.
EXPECTED_BASE = "us-rulespec-2026-10-29-ecfr-section-text"
EXPECTED_RELEASE = "us-rulespec-2026-11-05-mt-arm-37-78-420-successor"
EXPECTED_PREDECESSOR = ("us-mt", "regulation", "2026-07-13-recovery")
EXPECTED_SUCCESSOR = ("us-mt", "regulation", "2026-07-13-recovery-r2026-09-27-chrome-free")
MONTANA_REGULATION = ("us-mt", "regulation")
CITATION_PATH = "us-mt/regulation/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420"


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _scope(key: tuple[str, str, str]) -> dict[str, str]:
    return {"jurisdiction": key[0], "document_class": key[1], "version": key[2]}


def _keys(release: str) -> list[tuple[str, str, str]]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return [_key(scope) for scope in payload["scopes"]]


def _lock(key: tuple[str, str, str]) -> Path:
    return ROOT / ".axiom/corpus-locks" / key[0] / key[1] / f"{key[2]}.json"


def _rows(key: tuple[str, str, str]) -> list[dict[str, object]]:
    path = CORPUS / "provisions" / key[0] / key[1] / f"{key[2]}.jsonl"
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _montana_regulation_report(selector: str) -> dict[str, object]:
    """Validate the selector's us-mt/regulation scopes under its profile, with strict warnings."""
    payload = json.loads((RELEASE_DIR / f"{selector}.json").read_text(encoding="utf-8"))
    release = ReleaseManifest(
        name=f"{selector}-montana-regulation",
        quality_profile=payload["quality_profile"],
        scopes=tuple(
            ReleaseScope(*key) for key in _keys(selector) if key[:2] == MONTANA_REGULATION
        ),
    )
    return validate_release(CORPUS, release, strict_warnings=True).to_mapping()


def test_reproducer_constants_are_the_expected_swap() -> None:
    assert (BASE_RELEASE, RELEASE, PREDECESSOR, SUCCESSOR) == (
        EXPECTED_BASE,
        EXPECTED_RELEASE,
        EXPECTED_PREDECESSOR,
        EXPECTED_SUCCESSOR,
    )


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{EXPECTED_RELEASE}.json").read_bytes()


def test_selector_is_the_base_with_exactly_the_swap() -> None:
    base, release = _keys(EXPECTED_BASE), _keys(EXPECTED_RELEASE)
    assert set(base) - set(release) == {EXPECTED_PREDECESSOR}
    assert set(release) - set(base) == {EXPECTED_SUCCESSOR}
    assert len(release) == len(base) == 276
    assert release == sorted(release)


def test_the_description_names_the_base_as_the_predecessor() -> None:
    """The lineage check compares a cut with the first tracked selector its description names."""
    tracked = {path.stem for path in RELEASE_DIR.glob("*.json")}
    release = ReleaseManifest.load(RELEASE_DIR / f"{EXPECTED_RELEASE}.json")
    assert declared_predecessor(release, tracked) == EXPECTED_BASE


def test_selector_loads_and_keeps_the_quality_profile() -> None:
    release = ReleaseManifest.load(RELEASE_DIR / f"{EXPECTED_RELEASE}.json")
    base = json.loads((RELEASE_DIR / f"{EXPECTED_BASE}.json").read_text(encoding="utf-8"))
    ours = json.loads((RELEASE_DIR / f"{EXPECTED_RELEASE}.json").read_text(encoding="utf-8"))
    assert release.name == EXPECTED_RELEASE
    assert ours["quality_profile"] == base["quality_profile"]
    assert set(ours) == set(base)


def test_the_successor_is_locked_and_not_withdrawn() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    assert _lock(EXPECTED_PREDECESSOR).is_file()
    assert _lock(EXPECTED_SUCCESSOR).is_file()
    assert EXPECTED_SUCCESSOR not in withdrawn


def test_the_swap_keeps_the_rows_citation_path_and_expression_date() -> None:
    old, new = _rows(EXPECTED_PREDECESSOR), _rows(EXPECTED_SUCCESSOR)
    assert [row["citation_path"] for row in old] == [CITATION_PATH]
    assert [row["citation_path"] for row in new] == [CITATION_PATH]
    assert new[0]["expression_date"] == old[0]["expression_date"]


def test_the_montana_regulations_validate_with_strict_warnings_and_drop_the_finding() -> None:
    """Both selectors' two us-mt/regulation scopes pass; the swap removes the pin's one notice."""
    before = _montana_regulation_report(EXPECTED_BASE)
    after = _montana_regulation_report(EXPECTED_RELEASE)
    assert (before["ok"], before["issue_count"]) == (True, 0), before["issues"][:3]
    assert (after["ok"], after["issue_count"]) == (True, 0), after["issues"][:3]
    assert [notice["version"] for notice in before["notices"]] == [EXPECTED_PREDECESSOR[2]]
    assert "notices" not in after


def test_it_selects_no_withdrawn_scope_the_base_does_not() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    kept = {key for key in _keys(EXPECTED_RELEASE) if key in withdrawn}
    assert not kept - set(_keys(EXPECTED_BASE))


KEPT_WITHDRAWN = {"us-me", "us-mi", "us-mn"}  # 2026-07-13 recovery scopes, until rulespec-us#1365


def test_every_withdrawn_scope_it_keeps_has_its_own_exception() -> None:
    """Allowances don't carry forward: each kept withdrawn scope needs an exception for this selector."""
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    release = ReleaseManifest.load(RELEASE_DIR / f"{EXPECTED_RELEASE}.json")
    kept = [key for key in _keys(EXPECTED_RELEASE) if key in withdrawn]
    assert {key[0] for key in kept} == KEPT_WITHDRAWN
    for key in kept:
        allowance = withdrawn[key].allowance_for(release)
        assert allowance is not None and allowance.is_exception, key


def _write_base(release_dir: Path, scopes: list[dict[str, str]]) -> None:
    base = {"description": "base", "name": EXPECTED_BASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{EXPECTED_BASE}.json").write_text(json.dumps(base), encoding="utf-8")


def test_build_release_refuses_a_base_with_a_duplicate_scope(tmp_path: Path) -> None:
    scope = _scope(EXPECTED_PREDECESSOR)
    _write_base(tmp_path, [scope, scope])
    with pytest.raises(ValueError, match="duplicate scopes"):
        build_release(release_dir=tmp_path)


# Other pairs select the same version strings, as 40 pairs of the real base do. A swap that matches
# on the version alone, or on the version and one more field, rewrites one of them and fails.
_OTHER_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["manual", "regulation", "statute"]),
        "jurisdiction": st.sampled_from(["us", "us-me", "us-mt"]),
        "version": st.one_of(
            st.sampled_from([EXPECTED_PREDECESSOR[2], EXPECTED_SUCCESSOR[2]]),
            st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
        ),
    }
).filter(lambda scope: _key(scope) not in {EXPECTED_PREDECESSOR, EXPECTED_SUCCESSOR})


@settings(max_examples=200, deadline=None)
@given(
    others=st.lists(_OTHER_SCOPE, max_size=25, unique_by=_key),
    holds_predecessor=st.booleans(),
    holds_successor=st.booleans(),
)
def test_build_release_swaps_on_any_base(
    tmp_path_factory: pytest.TempPathFactory,
    others: list[dict[str, str]],
    holds_predecessor: bool,
    holds_successor: bool,
) -> None:
    """For any duplicate-free base that holds the predecessor and not the successor: the output
    replaces exactly the predecessor, keeps every other scope, and is sorted. A base missing the
    predecessor, or already holding the successor, is refused."""
    scopes = [
        *others,
        *([_scope(EXPECTED_PREDECESSOR)] if holds_predecessor else []),
        *([_scope(EXPECTED_SUCCESSOR)] if holds_successor else []),
    ]
    release_dir = tmp_path_factory.mktemp("releases")
    _write_base(release_dir, scopes)
    if not holds_predecessor:
        with pytest.raises(ValueError, match="does not select"):
            build_release(release_dir=release_dir)
        return
    if holds_successor:
        with pytest.raises(ValueError, match="already selects"):
            build_release(release_dir=release_dir)
        return
    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_key(scope) for scope in output["scopes"]]
    expected = [
        EXPECTED_SUCCESSOR if _key(scope) == EXPECTED_PREDECESSOR else _key(scope)
        for scope in scopes
    ]
    assert identities == sorted(expected)
    assert output["name"] == EXPECTED_RELEASE
    assert output["quality_profile"] == "q"
