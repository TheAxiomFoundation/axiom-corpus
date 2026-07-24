from __future__ import annotations

import json
from pathlib import Path

from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id

ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = (
    ROOT / "manifests/releases/us-rulespec-2026-07-24-cms-435-correction.json"
)
SUCCESSOR = (
    ROOT
    / "manifests/releases/"
    "us-rulespec-2026-07-24-cms-435-correction-immutable-scopes.json"
)
REPLACEMENTS = {
    (
        "us-ia",
        "statute",
        "2026-07-16-pit-east-us-ia-title-x-chapter-422",
    ): "2026-07-16-pit-east-us-ia-title-x-chapter-422-r2026-07-24-immutable",
    (
        "us-md",
        "statute",
        "2026-07-13-recovery",
    ): "2026-07-13-recovery-r2026-07-24-immutable",
    (
        "us-ok",
        "statute",
        "2026-07-16-pit-central-us-ok-title-68",
    ): "2026-07-16-pit-central-us-ok-title-68-r2026-07-24-immutable",
}


def _scope_keys(path: Path) -> list[tuple[str, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in payload["scopes"]
    ]


def test_successor_replaces_only_the_mutated_released_scopes() -> None:
    predecessor_keys = _scope_keys(PREDECESSOR)
    predecessor = set(predecessor_keys)
    successor_keys = _scope_keys(SUCCESSOR)
    successor = set(successor_keys)
    old_scopes = set(REPLACEMENTS)
    new_scopes = {
        (jurisdiction, document_class, version)
        for (jurisdiction, document_class, _), version in REPLACEMENTS.items()
    }

    assert successor == (predecessor - old_scopes) | new_scopes
    assert len(successor_keys) == len(successor) == 198
    assert successor_keys == [
        (
            jurisdiction,
            document_class,
            REPLACEMENTS.get(scope, version),
        )
        for scope in predecessor_keys
        for jurisdiction, document_class, version in (scope,)
    ]


def test_successor_artifacts_are_self_contained_and_deterministic() -> None:
    for (
        jurisdiction,
        document_class,
        source_version,
    ), version in REPLACEMENTS.items():
        scope_prefix = f"sources/{jurisdiction}/{document_class}/{version}/"
        old_scope_prefix = (
            f"sources/{jurisdiction}/{document_class}/{source_version}/"
        )
        provisions = load_provisions(
            ROOT
            / "data/corpus/provisions"
            / jurisdiction
            / document_class
            / f"{version}.jsonl"
        )
        inventory = load_source_inventory(
            ROOT
            / "data/corpus/inventory"
            / jurisdiction
            / document_class
            / f"{version}.json"
        )

        assert provisions
        assert inventory
        assert all(record.version == version for record in provisions)
        assert all(
            record.source_path is None or record.source_path.startswith(scope_prefix)
            for record in provisions
        )
        assert all(
            item.source_path is None or item.source_path.startswith(scope_prefix)
            for item in inventory
        )
        for record in provisions:
            assert record.id == deterministic_provision_id(
                record.citation_path, version
            )
            if record.parent_citation_path is not None:
                assert record.parent_id == deterministic_provision_id(
                    record.parent_citation_path, version
                )
            metadata_json = json.dumps(record.metadata or {})
            assert old_scope_prefix not in metadata_json


def test_successors_preserve_the_corrected_state_content() -> None:
    iowa_version = REPLACEMENTS[
        (
            "us-ia",
            "statute",
            "2026-07-16-pit-east-us-ia-title-x-chapter-422",
        )
    ]
    iowa = {
        record.citation_path: record
        for record in load_provisions(
            ROOT / f"data/corpus/provisions/us-ia/statute/{iowa_version}.jsonl"
        )
    }
    assert (iowa["us-ia/statute/422.7"].metadata or {}).get("status") is None

    maryland_version = REPLACEMENTS[
        ("us-md", "statute", "2026-07-13-recovery")
    ]
    maryland = {
        record.citation_path: record
        for record in load_provisions(
            ROOT / f"data/corpus/provisions/us-md/statute/{maryland_version}.jsonl"
        )
    }
    assert "6.50%" in (maryland["us-md/statute/gtg/10-105/block-1"].body or "")
    assert "$3,200" in (maryland["us-md/statute/gtg/10-211/block-1"].body or "")

    oklahoma_version = REPLACEMENTS[
        (
            "us-ok",
            "statute",
            "2026-07-16-pit-central-us-ok-title-68",
        )
    ]
    oklahoma = {
        record.citation_path: record
        for record in load_provisions(
            ROOT / f"data/corpus/provisions/us-ok/statute/{oklahoma_version}.jsonl"
        )
    }
    assert [
        (oklahoma[f"us-ok/statute/68-2358v{version}"].metadata or {}).get(
            "status"
        )
        for version in (1, 2, 3)
    ] == ["superseded", "superseded", "operative"]
