from __future__ import annotations

import json
from pathlib import Path

from scripts.repro.us_rulespec_2026_09_29_election_uocava_nvra import (
    ADDITION,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"


def _provision_paths(scope: dict[str, str]) -> list[str]:
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


def test_selector_preserves_base_and_adds_only_title_52_scope() -> None:
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())

    assert release["quality_profile"] == base["quality_profile"]
    assert len(release["scopes"]) == len(base["scopes"]) + 1
    assert {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in release["scopes"]
    } == {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in [*base["scopes"], ADDITION]
    }


def test_title_52_scope_has_unique_noncolliding_citation_paths() -> None:
    paths = _provision_paths(ADDITION)

    assert len(paths) == 162
    assert len(paths) == len(set(paths))
    assert all(path == "us/statute/52" or path.startswith("us/statute/52/") for path in paths)
    for target in (
        "us/statute/52/20302/a/8",
        "us/statute/52/20310/1",
        "us/statute/52/20310/5",
        "us/statute/52/20507/a/1",
    ):
        assert target in paths

    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    predecessor_paths: set[str] = set()
    for scope in base["scopes"]:
        predecessor_paths.update(_provision_paths(scope))

    assert predecessor_paths.isdisjoint(paths)
