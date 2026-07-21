from __future__ import annotations

import json
from pathlib import Path

from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "manifests/releases/ca-rulespec-2026-07-21-source-complete.json"
CONTRACT_PATH = (
    ROOT / "tests/fixtures/releases/ca-rulespec-2026-07-21-complete-citations.json"
)


def test_source_complete_release_has_composable_contracted_program_roots() -> None:
    release = ReleaseManifest.load(RELEASE_PATH)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    required = set(contract["citation_paths"])
    assert len(release.scopes) == 1
    scope = release.scopes[0]
    provisions = load_provisions(
        ROOT
        / "data/corpus/provisions"
        / scope.jurisdiction
        / scope.document_class
        / f"{scope.version}.jsonl"
    )
    by_path = {record.citation_path: record for record in provisions}

    assert len(required) == 103
    assert required <= by_path.keys()
    for citation_path in required:
        assert by_path[citation_path].body is None
        assert any(
            record.body is not None
            and record.citation_path.startswith(f"{citation_path}/")
            for record in provisions
        )
