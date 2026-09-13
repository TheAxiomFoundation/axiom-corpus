from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.repro.us_rulespec_2026_08_29_usc_469_release import (
    BASE_RELEASE,
    RELEASE,
    REPLACED_SCOPE,
    REPLACEMENT_SCOPE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"
PROVISIONS_DIR = ROOT / "data/corpus/provisions/us/statute"
PRIOR_TITLE_26 = "2026-08-03-rulespec-title-26-current-union"
USC_469 = "2026-08-29-usc-469-title-26"
SUCCESSOR_TITLE_26 = "2026-08-29-rulespec-title-26-with-469-union"


def _records(version: str) -> dict[str, dict[str, object]]:
    return {
        record["citation_path"]: record
        for record in (
            json.loads(line)
            for line in (PROVISIONS_DIR / f"{version}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        )
    }


def _portable_content(record: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"id", "parent_id", "source_path", "version"}
    }


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_replaces_only_prior_title_26_scope() -> None:
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text())
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())

    assert REPLACED_SCOPE in base["scopes"]
    assert REPLACED_SCOPE not in release["scopes"]
    assert REPLACEMENT_SCOPE not in base["scopes"]
    assert REPLACEMENT_SCOPE in release["scopes"]
    assert len(release["scopes"]) == len(base["scopes"]) == 275
    assert {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in release["scopes"]
    } == {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in [
            REPLACEMENT_SCOPE if scope == REPLACED_SCOPE else scope
            for scope in base["scopes"]
        ]
    }


def test_selector_has_one_citation_carrier() -> None:
    release = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text())
    carriers: Counter[str] = Counter()
    for scope in release["scopes"]:
        provisions = (
            ROOT
            / "data/corpus/provisions"
            / scope["jurisdiction"]
            / scope["document_class"]
            / f"{scope['version']}.jsonl"
        )
        assert provisions.is_file(), scope
        for line in provisions.read_text(encoding="utf-8").splitlines():
            if line:
                carriers[json.loads(line)["citation_path"]] += 1

    assert [path for path, count in carriers.items() if count != 1] == []
    assert carriers["us/statute/26/469"] == 1
    assert carriers["us/statute/26/469/c/1"] == 1
    assert carriers["us/statute/26/469/h"] == 1


def test_title_26_successor_is_exact_prior_union_plus_section_469() -> None:
    prior = _records(PRIOR_TITLE_26)
    section_469 = _records(USC_469)
    successor = _records(SUCCESSOR_TITLE_26)

    assert set(successor) == set(prior) | set(section_469)
    assert len(prior) == 804
    assert len(section_469) == 164
    assert len(successor) == 967
    for path, record in prior.items():
        assert _portable_content(successor[path]) == _portable_content(record)
    for path, record in section_469.items():
        if path != "us/statute/26":
            assert _portable_content(successor[path]) == _portable_content(record)

    target_version = SUCCESSOR_TITLE_26
    for _path, record in successor.items():
        assert record["version"] == target_version
        if parent_path := record.get("parent_citation_path"):
            assert record["parent_id"] == successor[parent_path]["id"]
