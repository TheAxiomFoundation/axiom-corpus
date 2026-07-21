from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "manifests/releases/ca-rulespec-2026-07-21-complete.json"
CONTRACT_PATH = (
    ROOT / "tests/fixtures/releases/ca-rulespec-2026-07-21-complete-citations.json"
)


def test_complete_canadian_release_contains_each_pinned_rulespec_citation_once() -> None:
    release = ReleaseManifest.load(RELEASE_PATH)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    required = set(contract["citation_paths"])
    actual: Counter[str] = Counter()

    for scope in release.scopes:
        provisions_path = (
            ROOT
            / "data/corpus/provisions"
            / scope.jurisdiction
            / scope.document_class
            / f"{scope.version}.jsonl"
        )
        for line in provisions_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                actual[json.loads(line)["citation_path"]] += 1

    assert len(required) == 103
    assert required - actual.keys() == set()
    assert {citation: actual[citation] for citation in required if actual[citation] != 1} == {}
