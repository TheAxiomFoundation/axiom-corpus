from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

import pytest

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.selector_lineage import declared_predecessor
from scripts.repro.us_rulespec_2026_11_24_tier1_source_text import (
    ADDED,
    BASE_RELEASE,
    RELEASE,
    REPLACED,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
RELEASE_DIR = ROOT / "manifests/releases"

# Literal, so a change to the reproducer's constants cannot also change what is checked.
EXPECTED_BASE = "us-rulespec-2026-11-11-cms-w6-federal-guidance"
EXPECTED_PIN = "us-rulespec-2026-10-29-ecfr-section-text"
EXPECTED_UNION = "us-rulespec-2026-10-13-w7-bundle-gaps-union"
EXPECTED_RELEASE = "us-rulespec-2026-11-24-tier1-source-text"
EXPECTED_ADDED_COUNT = 149
EXPECTED_ADDED_SHA256 = "6dc1c80e2dad002182bc1287b3980d493f0be9603e585cf82cadae8d157fe3ea"
EXPECTED_REPLACED = {
    ("us-co", "statute", "2026-07-19-rulespec-us-co-title-39-consolidated"): (
        "us-co",
        "statute",
        "2026-07-19-rulespec-us-co-title-39-consolidated-r2026-10-07-w6-title-10-consolidated",
    ),
    ("us-wa", "regulation", "2026-06-25-388-450-r2026-07-15-self-contained"): (
        "us-wa",
        "regulation",
        "2026-06-25-388-450-r2026-07-15-self-contained"
        "-r2026-10-07-388-400-424-470-w6-110-15-182-consolidated",
    ),
}
# The 80 U.S. Code sections of the Tier 1 SNAP, Medicaid, CHIP and UI bundles that the pin
# serves no text for (counted 2026-11-24).
USC_SECTIONS = {
    "8": "1611 1645",
    "25": "1603 1679",
    "26": (
        "23 25 25F 31 33 34 35 36 37 101 103 105 106 107 108 109 110 111 115 117 118 119 121 "
        "122 123 125 126 127 128 129 130 131 132 134 135 136 137 138 139 139A 139B 139C 139D "
        "139E 139F 139G 139H 139I 139J 139K 139L 140"
    ),
    "29": "206",
    "38": "101",
    "42": (
        "601 602 603 604 604a 605 606 607 608 608a 609 610 611 611a 612 613 615 616 617 618 "
        "619 1396"
    ),
}
USC_PATHS = sorted(
    f"us/statute/{title}/{section}"
    for title, sections in USC_SECTIONS.items()
    for section in sections.split()
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _keys(release: str) -> list[tuple[str, str, str]]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return [_key(scope) for scope in payload["scopes"]]


def _lock(key: tuple[str, str, str]) -> Path:
    return ROOT / ".axiom/corpus-locks" / key[0] / key[1] / f"{key[2]}.json"


@cache
def _bodies(key: tuple[str, str, str]) -> dict[str, str]:
    """Citation path -> body text of one scope's provision rows."""
    path = CORPUS / "provisions" / key[0] / key[1] / f"{key[2]}.jsonl"
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return {row["citation_path"]: row.get("body") or "" for row in rows}


def test_reproducer_constants_are_the_expected_addition() -> None:
    assert (BASE_RELEASE, RELEASE) == (EXPECTED_BASE, EXPECTED_RELEASE)
    assert len(ADDED) == EXPECTED_ADDED_COUNT
    digest = hashlib.sha256(json.dumps(sorted(ADDED)).encode()).hexdigest()
    assert digest == EXPECTED_ADDED_SHA256
    assert set(REPLACED) == set(EXPECTED_REPLACED)
    assert set(EXPECTED_REPLACED.values()) <= set(ADDED)


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{EXPECTED_RELEASE}.json").read_bytes()


def test_selector_is_the_base_with_the_additions_and_the_two_replacements() -> None:
    base, release = _keys(EXPECTED_BASE), _keys(EXPECTED_RELEASE)
    assert set(base) - set(release) == set(EXPECTED_REPLACED)
    assert set(release) - set(base) == set(ADDED)
    assert (len(base), len(release)) == (284, 431)
    assert release == sorted(release)


def test_selector_keeps_a_version_of_every_pair_of_the_pin_and_the_base() -> None:
    """A re-pin of rulespec-us to this selector loses no (jurisdiction, document_class) pair."""
    pairs = {key[:2] for key in _keys(EXPECTED_RELEASE)}
    assert {key[:2] for key in _keys(EXPECTED_PIN)} <= pairs
    assert {key[:2] for key in _keys(EXPECTED_BASE)} <= pairs
    assert set(_keys(EXPECTED_PIN)) - set(_keys(EXPECTED_RELEASE)) == set(EXPECTED_REPLACED)


@pytest.mark.parametrize("replaced", sorted(EXPECTED_REPLACED))
def test_each_replacement_holds_every_row_of_the_scope_it_replaces(
    replaced: tuple[str, str, str],
) -> None:
    """Same citation paths, same body text: a module that cites the old scope reads the same."""
    old, new = _bodies(replaced), _bodies(EXPECTED_REPLACED[replaced])
    assert old.keys() <= new.keys()
    assert {path for path in old if old[path] != new[path]} == set()


def test_every_added_scope_is_signed_locked_selected_by_the_union_and_not_withdrawn() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    union = set(_keys(EXPECTED_UNION))
    for key in ADDED:
        manifest = ROOT / ".axiom/ingest-manifests" / key[0] / key[1] / f"{key[2]}.json"
        assert _lock(key).is_file(), key
        assert json.loads(manifest.read_text(encoding="utf-8"))["signature"]["value"], key
        assert key in union, key
        assert key not in withdrawn, key


def test_no_citation_path_is_in_two_selected_scopes_because_of_an_addition() -> None:
    owner: dict[str, tuple[str, str, str]] = {}
    for key in _keys(EXPECTED_RELEASE):
        if key[0] not in {added[0] for added in ADDED}:
            continue
        for path in _bodies(key):
            if path in owner and (key in ADDED or owner[path] in ADDED):
                raise AssertionError((path, owner[path], key))
            owner.setdefault(path, key)


def test_the_selector_serves_text_for_the_80_us_code_sections_and_the_pin_does_not() -> None:
    assert len(USC_PATHS) == 80

    def served(release: str) -> set[str]:
        scopes = [key for key in _keys(release) if key[:2] == ("us", "statute")]
        return {
            path
            for path in USC_PATHS
            if any(
                body.strip() and (found == path or found.startswith(f"{path}/"))
                for key in scopes
                for found, body in _bodies(key).items()
            )
        }

    assert served(EXPECTED_PIN) == set()
    assert served(EXPECTED_RELEASE) == set(USC_PATHS)


def test_the_description_names_the_base_as_the_predecessor() -> None:
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


KEPT_WITHDRAWN = {"us-me", "us-mi", "us-mn"}  # 2026-07-13 recovery scopes the pin line still cites


def test_every_withdrawn_scope_it_keeps_is_from_the_base_and_has_its_own_exception() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    release = ReleaseManifest.load(RELEASE_DIR / f"{EXPECTED_RELEASE}.json")
    kept = [key for key in _keys(EXPECTED_RELEASE) if key in withdrawn]
    assert {key[0] for key in kept} == KEPT_WITHDRAWN
    assert set(kept) <= set(_keys(EXPECTED_BASE))
    for key in kept:
        allowance = withdrawn[key].allowance_for(release)
        assert allowance is not None and allowance.is_exception, key


def _write_base(release_dir: Path, keys: list[tuple[str, str, str]]) -> None:
    scopes = [{"jurisdiction": k[0], "document_class": k[1], "version": k[2]} for k in keys]
    base = {"description": "base", "name": EXPECTED_BASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{EXPECTED_BASE}.json").write_text(json.dumps(base), encoding="utf-8")


def test_build_release_refuses_a_base_with_a_duplicate_scope(tmp_path: Path) -> None:
    _write_base(tmp_path, [*EXPECTED_REPLACED, next(iter(EXPECTED_REPLACED))])
    with pytest.raises(ValueError, match="duplicate scopes"):
        build_release(release_dir=tmp_path)


def test_build_release_refuses_a_base_that_already_holds_an_added_scope(tmp_path: Path) -> None:
    _write_base(tmp_path, [*EXPECTED_REPLACED, ADDED[0]])
    with pytest.raises(ValueError, match="already selects"):
        build_release(release_dir=tmp_path)


def test_build_release_refuses_a_base_without_a_replaced_scope(tmp_path: Path) -> None:
    _write_base(tmp_path, [next(iter(EXPECTED_REPLACED))])
    with pytest.raises(ValueError, match="does not select"):
        build_release(release_dir=tmp_path)
