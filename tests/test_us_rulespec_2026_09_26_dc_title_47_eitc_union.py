from __future__ import annotations

import json
from pathlib import Path

from scripts.repro.us_rulespec_2026_09_26_dc_title_47_eitc_union import (
    ADDITIONS,
    BASE_RELEASE,
    RELEASE,
    REMOVALS,
    build_release,
    sibling_additions,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"


def _identities(scopes: list[dict[str, str]]) -> set[tuple[str, str, str]]:
    return {(s["jurisdiction"], s["document_class"], s["version"]) for s in scopes}


def _paths(scope: dict[str, str]) -> list[str]:
    provisions = (
        ROOT
        / "data/corpus/provisions"
        / scope["jurisdiction"]
        / scope["document_class"]
        / f"{scope['version']}.jsonl"
    )
    return [
        json.loads(line)["citation_path"]
        for line in provisions.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_is_base_plus_fy2027_minus_stale_title_47_plus_additions() -> None:
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())
    sibling = sibling_additions(RELEASE_DIR)

    assert _identities(sibling) == {("us", "guidance", "2026-09-24-snap-fy2027-cola")}
    expected = (
        _identities(base["scopes"]) | _identities(sibling) | _identities(list(ADDITIONS))
    ) - _identities(list(REMOVALS))
    assert _identities(release["scopes"]) == expected
    assert len(release["scopes"]) == len(base["scopes"]) + 1 - 1 + 3
    assert release["quality_profile"] == "complete-expression-dates-v1"


def test_additions_have_unique_paths_disjoint_from_retained_scopes() -> None:
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())
    added = _identities(list(ADDITIONS))
    retained_paths: set[str] = set()
    for scope in release["scopes"]:
        if _identities([scope]) <= added:
            continue
        retained_paths.update(_paths(scope))

    counts = {
        "2026-09-26-codified-title-47": 2179,
        "2026-09-26-dc-otr-d-40-booklets-ty2022-ty2023": 182,
        "2026-09-26-irs-rev-procs-2021-45-2022-38": 59,
    }
    for scope in ADDITIONS:
        paths = _paths(scope)
        assert len(paths) == counts[scope["version"]]
        assert len(paths) == len(set(paths))
        assert retained_paths.isdisjoint(paths)


def test_title_47_scope_is_current_and_leaves_47_1806_03_to_recovery_scope() -> None:
    title_47 = {
        json.loads(line)["citation_path"]: json.loads(line)
        for line in (
            ROOT / "data/corpus/provisions/us-dc/statute/2026-09-26-codified-title-47.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    }
    recovery = _paths(
        {"jurisdiction": "us-dc", "document_class": "statute", "version": "2026-07-13-recovery"}
    )

    assert "us-dc/statute/47/47-1806.03" not in title_47
    assert "us-dc/statute/47/47-1806.03/block-1" in recovery
    eitc = title_47["us-dc/statute/47/47-1806.04"]
    assert eitc["expression_date"] == "2026-09-16"
    assert "(B-1) If a return is filed" in eitc["body"]
    assert "refundable to the individual claiming the credit" in eitc["body"]
