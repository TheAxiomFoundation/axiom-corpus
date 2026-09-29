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


def _rows(scope: dict[str, str]) -> dict[str, dict]:
    provisions = (
        ROOT
        / "data/corpus/provisions"
        / scope["jurisdiction"]
        / scope["document_class"]
        / f"{scope['version']}.jsonl"
    )
    rows = [
        json.loads(line) for line in provisions.read_text(encoding="utf-8").splitlines() if line
    ]
    return {row["citation_path"]: row for row in rows}


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


def test_title_52_scope_has_unique_noncolliding_citation_paths() -> None:
    rows = _rows(ADDITION)
    paths = set(rows)

    assert len(rows) == 162
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
    """The swap drops only the recovery block rows and its empty WIC 11450 root.

    docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md: the chapter
    scope carries every R&TC section of the recovery and PIT core scopes.
    """
    chapter = _rows(US_CA_ADDITION)
    recovery, pit_core = (_rows(scope) for scope in US_CA_REMOVALS)

    for path, row in pit_core.items():
        assert chapter[path]["body"] == row["body"]
    dropped = set(recovery) - set(chapter)
    assert dropped == {path for path in recovery if "/block-" in path} | {
        "us-ca/statute/wic/11450/a/1/A"
    }
    assert {path for path in recovery if path.startswith("us-ca/statute/rtc/")} - dropped <= set(
        chapter
    )
