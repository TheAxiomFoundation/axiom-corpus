from __future__ import annotations

import json
from pathlib import Path

from scripts.repro.us_rulespec_2026_09_29_election_uocava_nvra import (
    ADDITION,
    BASE_RELEASE,
    RELEASE,
    US_CA_ADDITION,
    US_CA_REMOVALS,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"


def _identity(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _row_list(scope: dict[str, str]) -> list[dict]:
    provisions = (
        ROOT
        / "data/corpus/provisions"
        / scope["jurisdiction"]
        / scope["document_class"]
        / f"{scope['version']}.jsonl"
    )
    return [
        json.loads(line) for line in provisions.read_text(encoding="utf-8").splitlines() if line
    ]


def _rows(scope: dict[str, str]) -> dict[str, dict]:
    return {row["citation_path"]: row for row in _row_list(scope)}


def _us_ca_statute_versions(release: dict) -> set[str]:
    return {
        scope["version"]
        for scope in release["scopes"]
        if (scope["jurisdiction"], scope["document_class"]) == ("us-ca", "statute")
    }


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_adds_title_52_and_applies_only_the_us_ca_swap() -> None:
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())

    assert release["quality_profile"] == base["quality_profile"]
    base_ids = {_identity(scope) for scope in base["scopes"]}
    release_ids = {_identity(scope) for scope in release["scopes"]}
    assert len(release_ids) == len(release["scopes"])
    assert release_ids - base_ids == {_identity(ADDITION), _identity(US_CA_ADDITION)}
    assert base_ids - release_ids == {_identity(scope) for scope in US_CA_REMOVALS}


def test_us_ca_statute_scopes_match_the_wave4_cut() -> None:
    """The swap leaves the same us-ca statute set the wave4 consolidation selected."""
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())
    wave4 = json.loads((RELEASE_DIR / "us-rulespec-2026-09-14-wave4-union.json").read_text())

    assert _us_ca_statute_versions(release) == _us_ca_statute_versions(wave4)


def test_title_52_scope_has_unique_noncolliding_citation_paths() -> None:
    row_list = _row_list(ADDITION)
    paths = {row["citation_path"] for row in row_list}

    assert len(row_list) == 162
    assert len(paths) == len(row_list)
    assert all(path == "us/statute/52" or path.startswith("us/statute/52/") for path in paths)
    for target in (
        "us/statute/52/20302/a/8",
        "us/statute/52/20310/1",
        "us/statute/52/20310/5",
        "us/statute/52/20507/a/1",
    ):
        assert target in paths

    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())
    other_paths: set[str] = set()
    for scope in release["scopes"]:
        if scope != ADDITION:
            other_paths.update(_rows(scope))

    assert other_paths.isdisjoint(paths)


def test_us_ca_chapter_scope_carries_the_replaced_sections() -> None:
    """The swap drops only the recovery's synthetic block rows and its WIC root.

    docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md: the chapter
    scope carries every R&TC section of the recovery and PIT core scopes (the
    ten R&TC block-2 texts at their section paths), no code cites a block-N
    path, and the WIC 11450 root resolves by ancestor slice.
    """
    chapter = _rows(US_CA_ADDITION)
    recovery, pit_core = (_rows(scope) for scope in US_CA_REMOVALS)

    for path, row in pit_core.items():
        assert chapter[path]["body"] == row["body"]
    dropped = set(recovery) - set(chapter)
    assert dropped == {path for path in recovery if "/block-" in path} | {
        "us-ca/statute/wic/11450/a/1/A"
    }
    rtc_sections = {
        path for path in recovery if path.startswith("us-ca/statute/rtc/") and "/block-" not in path
    }
    assert len(rtc_sections) == 10
    assert rtc_sections <= set(chapter)
