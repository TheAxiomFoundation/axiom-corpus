from __future__ import annotations

import json
from pathlib import Path

from scripts.repro.us_rulespec_2026_08_08_obbb_alien_snap import (
    ADDITION,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_preserves_base_and_adds_only_memo_scope() -> None:
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())

    assert len(release["scopes"]) == len(base["scopes"]) + 1
    assert {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in release["scopes"]
    } == {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in [*base["scopes"], ADDITION]
    }


def test_memo_scope_has_unique_noncolliding_citation_paths() -> None:
    provisions = (
        ROOT
        / "data/corpus/provisions"
        / ADDITION["jurisdiction"]
        / ADDITION["document_class"]
        / f"{ADDITION['version']}.jsonl"
    )
    paths = [
        json.loads(line)["citation_path"]
        for line in provisions.read_text(encoding="utf-8").splitlines()
        if line
    ]

    assert len(paths) == 12
    assert len(paths) == len(set(paths))

    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    predecessor_paths: set[str] = set()
    for scope in base["scopes"]:
        predecessor = (
            ROOT
            / "data/corpus/provisions"
            / scope["jurisdiction"]
            / scope["document_class"]
            / f"{scope['version']}.jsonl"
        )
        predecessor_paths.update(
            json.loads(line)["citation_path"]
            for line in predecessor.read_text(encoding="utf-8").splitlines()
            if line
        )

    assert predecessor_paths.isdisjoint(paths)
