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
from scripts.repro.us_rulespec_2026_11_11_cms_w6_federal_guidance import (
    ADDED,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
RELEASE_DIR = ROOT / "manifests/releases"

# Literal, so a change to the reproducer's constants cannot also change what is checked.
EXPECTED_BASE = "us-rulespec-2026-10-27-ks-liheap"
EXPECTED_PIN = "us-rulespec-2026-10-29-ecfr-section-text"
EXPECTED_RELEASE = "us-rulespec-2026-11-11-cms-w6-federal-guidance"
EXPECTED_ADDED = ("us", "guidance", "2026-10-06-w6-federal-cms-guidance")
BULLETIN_PATH = "us/guidance/cms/cib/2025-12-08"
BULLETIN_SOURCE_ID = "cms-cib-2025-12-08"


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


def test_reproducer_constants_are_the_expected_addition() -> None:
    assert (BASE_RELEASE, RELEASE, ADDED) == (EXPECTED_BASE, EXPECTED_RELEASE, EXPECTED_ADDED)


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{EXPECTED_RELEASE}.json").read_bytes()


def test_selector_is_the_base_with_exactly_the_addition() -> None:
    base, release = _keys(EXPECTED_BASE), _keys(EXPECTED_RELEASE)
    assert set(base) - set(release) == set()
    assert set(release) - set(base) == {EXPECTED_ADDED}
    assert (len(base), len(release)) == (283, 284)
    assert release == sorted(release)


def test_selector_carries_every_scope_of_the_rulespec_us_pin() -> None:
    """rulespec-us pins the base's predecessor; a re-pin to this selector loses none of it."""
    pin, release = _keys(EXPECTED_PIN), _keys(EXPECTED_RELEASE)
    assert len(pin) == 276
    assert set(pin) <= set(release)
    assert EXPECTED_ADDED not in pin


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
    assert ours["quality_profile"] == base["quality_profile"] == "complete-expression-dates-v1"
    assert set(ours) == set(base)


def test_the_added_scope_is_locked_and_not_withdrawn() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    assert _lock(EXPECTED_ADDED).is_file()
    assert EXPECTED_ADDED not in withdrawn


def test_the_added_scope_holds_the_bulletin() -> None:
    """The CMCS Informational Bulletin of 2025-12-08: one document row and its 13 blocks."""
    rows = _rows(EXPECTED_ADDED)
    bulletin = [
        row
        for row in rows
        if row["citation_path"] == BULLETIN_PATH
        or str(row["citation_path"]).startswith(f"{BULLETIN_PATH}/")
    ]
    assert len(rows) == 352
    assert len(bulletin) == 14
    assert {row["source_id"] for row in bulletin} == {BULLETIN_SOURCE_ID}
    assert {row["expression_date"] for row in bulletin} == {"2025-12-08"}
    assert sum(1 for row in bulletin if row["body"]) == 13


def test_no_citation_path_of_the_added_scope_is_already_in_the_base() -> None:
    added = {row["citation_path"] for row in _rows(EXPECTED_ADDED)}
    assert len(added) == 352
    for key in _keys(EXPECTED_BASE):
        shared = added & {row["citation_path"] for row in _rows(key)}
        assert not shared, (key, sorted(shared)[:3])


def test_the_added_scope_validates_alone_with_strict_warnings() -> None:
    """No error and no warning; its one notice is the content findings the baseline records."""
    release = ReleaseManifest(
        name=f"{EXPECTED_RELEASE}-added-scope",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope(*EXPECTED_ADDED),),
    )
    report = validate_release(CORPUS, release, strict_warnings=True).to_mapping()
    assert (report["ok"], report["issue_count"]) == (True, 0), report["issues"][:3]
    assert [notice["code"] for notice in report["notices"]] == ["baselined_content_findings"]


def test_it_selects_no_withdrawn_scope_the_base_does_not() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    kept = {key for key in _keys(EXPECTED_RELEASE) if key in withdrawn}
    assert not kept - set(_keys(EXPECTED_BASE))


KEPT_WITHDRAWN = {"us-me", "us-mi", "us-mn"}  # 2026-07-13 recovery scopes the pin line still cites


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
    scope = _scope(("us", "guidance", "2026-09-13-snap-fns-guidance"))
    _write_base(tmp_path, [scope, scope])
    with pytest.raises(ValueError, match="duplicate scopes"):
        build_release(release_dir=tmp_path)


# Other pairs select the added scope's version string, and us/guidance selects other versions, as
# 15 scopes of the real base do. A refusal that matches on less than the whole scope fails.
_OTHER_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["guidance", "manual", "regulation"]),
        "jurisdiction": st.sampled_from(["us", "us-ks", "us-mt"]),
        "version": st.one_of(
            st.just(EXPECTED_ADDED[2]),
            st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
        ),
    }
).filter(lambda scope: _key(scope) != EXPECTED_ADDED)


@settings(max_examples=200, deadline=None)
@given(
    others=st.lists(_OTHER_SCOPE, max_size=25, unique_by=_key),
    holds_added=st.booleans(),
)
def test_build_release_adds_on_any_base(
    tmp_path_factory: pytest.TempPathFactory,
    others: list[dict[str, str]],
    holds_added: bool,
) -> None:
    """For any duplicate-free base without the added scope: the output is the base plus exactly
    that scope, sorted. A base that already holds it is refused."""
    scopes = [*others, *([_scope(EXPECTED_ADDED)] if holds_added else [])]
    release_dir = tmp_path_factory.mktemp("releases")
    _write_base(release_dir, scopes)
    if holds_added:
        with pytest.raises(ValueError, match="already selects"):
            build_release(release_dir=release_dir)
        return
    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_key(scope) for scope in output["scopes"]]
    assert identities == sorted([*(_key(scope) for scope in scopes), EXPECTED_ADDED])
    assert output["name"] == EXPECTED_RELEASE
    assert output["quality_profile"] == "q"
