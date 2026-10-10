from __future__ import annotations

import json
from pathlib import Path

from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id

ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = (
    ROOT
    / "manifests/releases/"
    "us-rulespec-2026-07-24-cms-435-correction-immutable-scopes.json"
)
SUCCESSOR = (
    ROOT / "manifests/releases/us-rulespec-2026-07-24-sc-act110-current.json"
)
OLD_VERSION = "2026-07-16-pit-central-us-sc-title-12-chapter-6"
NEW_VERSION = "2026-07-24-sc-act110-us-sc-title-12-chapter-6"
OLD_SCOPE = ("us-sc", "statute", OLD_VERSION)
NEW_SCOPE = ("us-sc", "statute", NEW_VERSION)


def _scope_keys(path: Path) -> list[tuple[str, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in payload["scopes"]
    ]


def test_release_successor_replaces_only_south_carolina_act110_scope() -> None:
    predecessor_keys = _scope_keys(PREDECESSOR)
    successor_keys = _scope_keys(SUCCESSOR)

    assert successor_keys == [
        NEW_SCOPE if scope == OLD_SCOPE else scope for scope in predecessor_keys
    ]
    assert len(successor_keys) == len(set(successor_keys)) == 198


def test_act110_scope_is_self_contained_and_deterministic() -> None:
    provisions = load_provisions(
        ROOT / f"data/corpus/provisions/us-sc/statute/{NEW_VERSION}.jsonl"
    )
    inventory = load_source_inventory(
        ROOT / f"data/corpus/inventory/us-sc/statute/{NEW_VERSION}.json"
    )
    scope_prefix = f"sources/us-sc/statute/{NEW_VERSION}/"

    assert len(provisions) == len(inventory) == 158
    assert all(record.citation_path != "us-sc/statute/12-6-520" for record in provisions)
    assert all(record.version == NEW_VERSION for record in provisions)
    assert all(
        record.source_path is None or record.source_path.startswith(scope_prefix)
        for record in provisions
    )
    assert all(item.source_path.startswith(scope_prefix) for item in inventory)
    for record in provisions:
        assert record.id == deterministic_provision_id(
            record.citation_path,
            NEW_VERSION,
        )
        if record.parent_citation_path is not None:
            assert record.parent_id == deterministic_provision_id(
                record.parent_citation_path,
                NEW_VERSION,
            )
        assert OLD_VERSION not in json.dumps(record.metadata or {})


def test_act110_scope_contains_operational_2026_income_tax_text() -> None:
    provisions = {
        record.citation_path: record
        for record in load_provisions(
            ROOT / f"data/corpus/provisions/us-sc/statute/{NEW_VERSION}.jsonl"
        )
    }

    section_50 = provisions["us-sc/statute/12-6-50"].body or ""
    section_1140 = provisions["us-sc/statute/12-6-1140"].body or ""
    section_4910 = provisions["us-sc/statute/12-6-4910"].body or ""
    section_1720 = provisions["us-sc/statute/12-6-1720"].body or ""
    section_3632 = provisions["us-sc/statute/12-6-3632"].body or ""

    assert "Section 63(b) through (g)" in section_50
    assert "fifteen thousand dollars" in section_1140
    assert "twenty-two thousand five hundred dollars" in section_1140
    assert "thirty thousand dollars" in section_1140
    assert "forty thousand dollars" in section_1140
    assert "sixty thousand dollars" in section_1140
    assert "eighty thousand dollars" in section_1140
    assert "rounded to the next lowest ten dollars" in section_1140
    assert "whose South Carolina gross income for the taxable year is more than" in section_4910
    assert "(2) a corporation subject to taxation under this chapter." in section_4910
    assert "2026 Act No. 110 (H.4216), SECTION 4" in section_4910
    assert "South Carolina Income Adjusted Deduction (SCIAD)" in section_1720
    assert "(a)(i) For a nonresident individual" in section_1720
    assert (
        "(ii) For a nonresident estate or nonresident trust, the personal exemption "
        "and itemized deductions"
    ) in section_1720
    assert "2026 Act No. 110 (H.4216), SECTION 5" in section_1720
    assert "not to exceed two hundred dollars" in section_3632
    assert "2026 Act No. 110 (H.4216), SECTION 7" in section_3632
