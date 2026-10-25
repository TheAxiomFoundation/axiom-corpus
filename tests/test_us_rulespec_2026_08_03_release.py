from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.repro.us_rulespec_2026_08_03_release import (
    ADDITIONS,
    BASE_RELEASE,
    RELEASE,
    REPLACEMENTS,
    Scope,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_replaces_obsolete_scopes_once_and_adds_reviewed_union() -> None:
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())
    base_scopes = [Scope.from_mapping(scope) for scope in base["scopes"]]
    release_scopes = [Scope.from_mapping(scope) for scope in release["scopes"]]

    assert all(base_scopes.count(scope) == 1 for scope in REPLACEMENTS)
    assert all(scope not in release_scopes for scope in REPLACEMENTS)
    assert all(scope in release_scopes for scope in REPLACEMENTS.values())
    assert all(scope in release_scopes for scope in ADDITIONS)
    assert len(release_scopes) == len(base_scopes) + len(ADDITIONS)


def test_selector_has_one_citation_carrier() -> None:
    payload = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())
    carriers: Counter[str] = Counter()
    for raw_scope in payload["scopes"]:
        scope = Scope.from_mapping(raw_scope)
        provisions = (
            ROOT
            / "data/corpus/provisions"
            / scope.jurisdiction
            / scope.document_class
            / f"{scope.version}.jsonl"
        )
        assert provisions.is_file(), scope
        for line in provisions.read_text(encoding="utf-8").splitlines():
            if line:
                carriers[json.loads(line)["citation_path"]] += 1

    duplicates = sorted(path for path, count in carriers.items() if count != 1)
    assert duplicates == []
