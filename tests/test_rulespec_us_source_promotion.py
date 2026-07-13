"""Fail-closed checks for the RuleSpec-US source-promotion audit."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "manifests/migrations/rulespec-us-source-promotion.json"
RELEASE = ROOT / "manifests/releases/us-rulespec-2026-07-13.json"


def test_us_promotion_classifies_every_gap_without_promoting_unsourced_text() -> None:
    migration = json.loads(MIGRATION.read_text(encoding="utf-8"))
    entries = migration["entries"]

    assert migration["schema_version"] == "axiom-corpus/source-promotion/v1"
    assert migration["counts"] == {
        "external_fetch_required": 711,
        "external_fetch_with_bodyless_corpus_placeholder": 24,
        "external_fetch_with_unprovenanced_encoder_cache_text": 129,
        "external_fetch_without_retained_text": 582,
        "promotable_repo_local_snapshot": 0,
        "total": 711,
        "widen_existing_scope": 0,
        "widened_scopes": 0,
    }
    assert len(entries) == 711
    assert len({entry["citation_path"] for entry in entries}) == 711
    assert {entry["classification"] for entry in entries} == {
        "external_fetch_required"
    }
    assert migration["scope_additions"] == []
    assert migration["rulespec_source_audit"]["tracked_source_candidate_count"] == 0


def test_us_release_does_not_claim_an_empty_promotion_scope() -> None:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))

    assert not any(
        scope["version"] == "2026-07-13-us-rulespec-source-promotion"
        for scope in release["scopes"]
    )

