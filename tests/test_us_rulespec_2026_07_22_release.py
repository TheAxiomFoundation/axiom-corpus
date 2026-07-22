from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = REPO_ROOT / "manifests/releases/us-rulespec-2026-07-21-az-140es-current.json"
SUCCESSOR = REPO_ROOT / "manifests/releases/us-rulespec-2026-07-22-current.json"
SUPERSEDED = {
    ("us", "statute", "2026-05-10-snap-sections"),
    (
        "us",
        "statute",
        "2026-07-17-hr6644-dependency-closure-title-7-title-7",
    ),
}
CONSOLIDATED = ("us", "statute", "2026-07-22-rulespec-title-7-consolidated")
CONSOLIDATED_INPUTS = (
    "2026-07-17-hr6644-dependency-closure-title-7-title-7",
    "2026-07-21-snap-chapter-51-title-7-title-7",
)


def _scope_keys(path: Path) -> list[tuple[str, str, str]]:
    payload = json.loads(path.read_text())
    return [
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in payload["scopes"]
    ]


def _citation_paths(version: str) -> set[str]:
    path = REPO_ROOT / f"data/corpus/provisions/us/statute/{version}.jsonl"
    return {json.loads(line)["citation_path"] for line in path.read_text().splitlines()}


def test_successor_replaces_partial_title_7_scopes() -> None:
    predecessor = set(_scope_keys(PREDECESSOR))
    successor_keys = _scope_keys(SUCCESSOR)
    successor = set(successor_keys)

    assert predecessor >= SUPERSEDED
    assert successor == (predecessor - SUPERSEDED) | {CONSOLIDATED}
    assert len(successor_keys) == len(successor) == 199
    assert successor_keys == sorted(successor_keys)


def test_consolidated_title_7_scope_is_the_unique_input_union() -> None:
    input_paths = [_citation_paths(version) for version in CONSOLIDATED_INPUTS]
    consolidated = _citation_paths(CONSOLIDATED[2])

    assert input_paths[0] & input_paths[1] == {"us/statute/7"}
    assert consolidated == input_paths[0] | input_paths[1]
    assert len(consolidated) == 862
    assert {f"us/statute/7/{section}" for section in range(2011, 2037)} <= consolidated
    assert {"us/statute/7/1928", "us/statute/7/1929"} <= consolidated
