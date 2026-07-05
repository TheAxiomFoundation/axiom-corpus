"""Tests for the derived provision_anchors leaf layer (B3a).

Structure mirrors ``test_citation_path_grammar.py``:

1. Positive — the generator produces addressable leaves for the two issue-14
   targets (``7 CFR 273.9(d)(6)(iii)`` and ``us-ma 106 CMR 365.180(A)``), the
   mechanical gates hold, and the resolver's exact/descendant/ancestor semantics
   work.
2. Negative / anti-vacuous — a corrupted offset FAILS verification, a wrong
   label at the head is REJECTED, a drifted parent body is caught, and each
   target yields at least a floor number of anchors. A green suite therefore
   means the checks can actually fail, not that there was nothing to check.

Both targets are read from the real committed provision JSONL so the test
exercises production data, and the committed anchor JSONL is checked to be
exactly what the generator reproduces (the derived artifact is in sync).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from axiom_corpus.corpus.anchors import (
    EXTRACTOR_VERSION,
    AnchorResolver,
    AnchorVerificationError,
    ProvisionAnchor,
    anchor_for_stored_leaf,
    anchor_to_supabase_row,
    generate_anchors_for_provision,
    generate_stored_leaf_anchors,
    load_anchors,
    verify_anchor,
    verify_anchors_against_provisions,
    write_anchors_jsonl,
)
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import ProvisionRecord

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVISIONS_DIR = REPO_ROOT / "data" / "corpus" / "provisions"
ANCHORS_DIR = REPO_ROOT / "data" / "corpus" / "anchors"

# --- Target 1: 7 CFR 273.9 (federal, paragraph-tree parse) ---
CFR_PROVISIONS = (
    PROVISIONS_DIR / "us" / "regulation" / "2026-05-10-snap-7-cfr-273.jsonl"
)
CFR_ANCHORS = ANCHORS_DIR / "us" / "regulation" / "2026-05-10-snap-7-cfr-273.jsonl"
CFR_SECTION = "us/regulation/7/273/9"
CFR_LEAF = "us/regulation/7/273/9/d/6/iii"

# --- Target 2: us-ma 106 CMR 365.180 (state, stored block leaf) ---
MA_PROVISIONS = (
    PROVISIONS_DIR
    / "us-ma"
    / "regulation"
    / "2026-05-28-365-180-children.jsonl"
)
MA_ANCHORS = (
    ANCHORS_DIR / "us-ma" / "regulation" / "2026-05-28-365-180-children.jsonl"
)
MA_LEAF = "us-ma/regulation/106-cmr/365/180/A"


# --------------------------------------------------------------------------- #
# Fixtures                                                                       #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def cfr_section() -> ProvisionRecord:
    records = load_provisions(CFR_PROVISIONS)
    for record in records:
        if record.citation_path == CFR_SECTION:
            return record
    pytest.skip(f"{CFR_SECTION} not present in {CFR_PROVISIONS}")


@pytest.fixture(scope="module")
def cfr_anchors(cfr_section: ProvisionRecord) -> list[ProvisionAnchor]:
    return generate_anchors_for_provision(cfr_section)


@pytest.fixture(scope="module")
def ma_leaf_provision() -> ProvisionRecord:
    records = load_provisions(MA_PROVISIONS)
    for record in records:
        if record.citation_path == MA_LEAF:
            return record
    pytest.skip(f"{MA_LEAF} not present in {MA_PROVISIONS}")


@pytest.fixture(scope="module")
def ma_anchors(ma_leaf_provision: ProvisionRecord) -> list[ProvisionAnchor]:
    return generate_stored_leaf_anchors(ma_leaf_provision)


# --------------------------------------------------------------------------- #
# Positive: generation + mechanical gates                                       #
# --------------------------------------------------------------------------- #


def test_cfr_generates_paragraph_tree(cfr_anchors: list[ProvisionAnchor]) -> None:
    assert len(cfr_anchors) >= 100, "273.9 should yield many paragraph leaves"
    paths = {a.citation_path for a in cfr_anchors}
    # The motivating leaf and its ancestors are all addressable.
    assert CFR_LEAF in paths
    assert "us/regulation/7/273/9/d" in paths
    assert "us/regulation/7/273/9/d/6" in paths


def test_cfr_paths_are_unique(cfr_anchors: list[ProvisionAnchor]) -> None:
    # The leaf path is the PRIMARY KEY; no two anchors may collide.
    paths = [a.citation_path for a in cfr_anchors]
    assert len(paths) == len(set(paths)), "duplicate citation paths would break the PK"


def test_cfr_top_level_is_a_through_d(cfr_anchors: list[ProvisionAnchor]) -> None:
    # 7 CFR 273.9 has exactly four top-level paragraphs: (a)-(d).
    tops = sorted(a.label for a in cfr_anchors if a.depth == 0)
    assert tops == ["a", "b", "c", "d"]


def test_cfr_inline_first_child_is_captured(
    cfr_anchors: list[ProvisionAnchor],
) -> None:
    # eCFR runs (iii)'s first child (A) inline after "allowances. "; it and its
    # numbered children must nest under (iii), not escape to a shallower level.
    by_path = {a.citation_path: a for a in cfr_anchors}
    assert f"{CFR_LEAF}/A" in by_path
    assert by_path[f"{CFR_LEAF}/A"].text.lstrip().startswith("(A)")
    assert f"{CFR_LEAF}/A/1" in by_path
    # The siblings that follow the inline (A) stay under (iii) too.
    assert f"{CFR_LEAF}/B" in by_path
    assert f"{CFR_LEAF}/D/3/vii" in by_path


def test_resolver_descendant_over_real_data(
    cfr_anchors: list[ProvisionAnchor],
) -> None:
    # Real descendant fallback: (d)(6)(iii)(D) has children (1),(2),(3); querying
    # it returns the span covering them, from a single parent provision.
    resolver = AnchorResolver(cfr_anchors)
    parent_of_d = f"{CFR_LEAF}/D"
    by_path = {a.citation_path: a for a in cfr_anchors}
    if parent_of_d in by_path:
        # (D) itself is drafted (intermediate), so this is an exact hit; assert
        # its span covers its (1)..(3) children.
        res = resolver.resolve(parent_of_d)
        assert res is not None
        child = by_path[f"{parent_of_d}/3"]
        assert res.span[0] <= child.char_start
        assert res.span[1] >= child.char_end


def test_cfr_leaf_is_the_standard_utility_allowance(
    cfr_anchors: list[ProvisionAnchor],
) -> None:
    by_path = {a.citation_path: a for a in cfr_anchors}
    leaf = by_path[CFR_LEAF]
    assert leaf.text.lstrip().startswith("(iii)")
    assert "Standard utility allowances" in leaf.text
    assert leaf.label == "iii"
    assert leaf.depth == 2  # (d)=0 > (6)=1 > (iii)=2, 0-based within the section


def test_cfr_every_anchor_is_byte_equal_and_label_headed(
    cfr_section: ProvisionRecord, cfr_anchors: list[ProvisionAnchor]
) -> None:
    body = cfr_section.body or ""
    for anchor in cfr_anchors:
        # Byte-equal gate.
        assert body[anchor.char_start : anchor.char_end] == anchor.text
        # Label-at-head gate.
        assert anchor.text.lstrip().startswith(f"({anchor.label})")
        # verify_anchor agrees (single source of truth for the gates).
        verify_anchor(anchor, body)


def test_cfr_confidence_is_label_inferred(
    cfr_anchors: list[ProvisionAnchor],
) -> None:
    # eCFR asserts only to the section; the paragraph tree is inferred.
    assert {a.confidence for a in cfr_anchors} == {"label_inferred"}


def test_cfr_parent_linkage_is_the_stored_provision(
    cfr_section: ProvisionRecord, cfr_anchors: list[ProvisionAnchor]
) -> None:
    for anchor in cfr_anchors:
        assert anchor.parent_provision_id == cfr_section.id
        assert anchor.parent_citation_path == CFR_SECTION


def test_ma_stored_leaf_and_children(ma_anchors: list[ProvisionAnchor]) -> None:
    by_path = {a.citation_path: a for a in ma_anchors}
    assert MA_LEAF in by_path
    leaf = by_path[MA_LEAF]
    assert leaf.confidence == "machine_asserted", (
        "a publisher-asserted block leaf carries a machine boundary"
    )
    assert leaf.text.lstrip().startswith("(A)")
    assert "categorically eligible" in leaf.text
    # Run-in numbered children resolve as label_inferred sub-leaves.
    assert f"{MA_LEAF}/1" in by_path
    assert by_path[f"{MA_LEAF}/1"].confidence == "label_inferred"


def test_ma_children_are_byte_equal(
    ma_leaf_provision: ProvisionRecord, ma_anchors: list[ProvisionAnchor]
) -> None:
    body = ma_leaf_provision.body or ""
    for anchor in ma_anchors:
        assert body[anchor.char_start : anchor.char_end] == anchor.text
        verify_anchor(anchor, body)


# --------------------------------------------------------------------------- #
# Positive: resolver semantics                                                  #
# --------------------------------------------------------------------------- #


def test_resolver_exact_match(cfr_anchors: list[ProvisionAnchor]) -> None:
    resolver = AnchorResolver(cfr_anchors)
    res = resolver.resolve(CFR_LEAF)
    assert res is not None
    assert res.match == "exact"
    assert res.provision_id  # (asserted provision id, leaf path, span)
    assert res.parent_citation_path == CFR_SECTION
    assert res.span[0] < res.span[1]
    assert "Standard utility allowances" in res.text


def test_resolver_descendant_fallback() -> None:
    # Query an ancestor path when only a deeper leaf is drafted.
    parent = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/273/9",
        id="00000000-0000-0000-0000-000000000001",
        version="v",
        body="(d) Income deductions. (6) Shelter costs (iii) Standard utility.",
    )
    only_leaf = ProvisionAnchor(
        citation_path="us/regulation/7/273/9/d/6/iii",
        parent_provision_id=parent.id,
        parent_citation_path=parent.citation_path,
        char_start=0,
        char_end=3,
        text="(d)",
        label="d",
        depth=0,
    )
    resolver = AnchorResolver([only_leaf])
    res = resolver.resolve("us/regulation/7/273/9/d")
    assert res is not None
    assert res.match == "descendant"
    assert res.provision_id == parent.id


def test_resolver_ancestor_fallback(cfr_anchors: list[ProvisionAnchor]) -> None:
    resolver = AnchorResolver(cfr_anchors)
    # Drill BELOW the drafted frontier: no such leaf, but its ancestor exists.
    res = resolver.resolve(CFR_LEAF + "/Z/9")
    assert res is not None
    assert res.match == "ancestor"
    assert res.anchor.citation_path == CFR_LEAF


def test_resolver_unresolved_returns_none(
    cfr_anchors: list[ProvisionAnchor],
) -> None:
    resolver = AnchorResolver(cfr_anchors)
    assert resolver.resolve("us/regulation/7/273/9/zzz") is None
    assert resolver.resolve("us/regulation/99/999/9") is None


def test_ma_leaf_resolves(ma_anchors: list[ProvisionAnchor]) -> None:
    resolver = AnchorResolver(ma_anchors)
    res = resolver.resolve(MA_LEAF)
    assert res is not None
    assert res.match == "exact"
    assert res.parent_citation_path == MA_LEAF


# --------------------------------------------------------------------------- #
# Negative / anti-vacuous                                                       #
# --------------------------------------------------------------------------- #


def test_min_anchor_count_per_target(
    cfr_anchors: list[ProvisionAnchor], ma_anchors: list[ProvisionAnchor]
) -> None:
    # Anti-vacuous floor: the generator produced real work per target.
    assert len(cfr_anchors) >= 50
    assert len(ma_anchors) >= 2


def test_restarted_numbered_list_does_not_collide() -> None:
    # A body with two separate (1),(2) lists at the same outline level (a
    # restarted list) must not produce colliding paths — the monotonic-sibling
    # rule re-attaches the second list correctly. Regression for the
    # 273.9(c)(1)(vii)... collision.
    body = (
        "(a) First. (1) one item, (2) two item.\n\n"
        "(b) Second. (1) alpha again, (2) beta again."
    )
    provision = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/1/1/1",
        id="00000000-0000-0000-0000-000000000009",
        version="v",
        body=body,
    )
    anchors = generate_anchors_for_provision(provision)
    paths = [a.citation_path for a in anchors]
    assert len(paths) == len(set(paths))
    path_set = set(paths)
    # The two (1)s live under different parents, so both are addressable.
    assert "us/regulation/1/1/1/a/1" in path_set
    assert "us/regulation/1/1/1/b/1" in path_set


def test_corrupted_offset_fails_verification(
    cfr_section: ProvisionRecord, cfr_anchors: list[ProvisionAnchor]
) -> None:
    body = cfr_section.body or ""
    good = next(a for a in cfr_anchors if a.citation_path == CFR_LEAF)
    corrupted = dataclasses.replace(good, char_start=good.char_start + 7)
    with pytest.raises(AnchorVerificationError, match="byte-equal"):
        verify_anchor(corrupted, body)


def test_corrupted_end_offset_fails_verification(
    cfr_section: ProvisionRecord, cfr_anchors: list[ProvisionAnchor]
) -> None:
    body = cfr_section.body or ""
    good = next(a for a in cfr_anchors if a.citation_path == CFR_LEAF)
    corrupted = dataclasses.replace(good, char_end=good.char_end - 11)
    with pytest.raises(AnchorVerificationError):
        verify_anchor(corrupted, body)


def test_wrong_label_at_head_is_rejected(
    cfr_section: ProvisionRecord, cfr_anchors: list[ProvisionAnchor]
) -> None:
    body = cfr_section.body or ""
    good = next(a for a in cfr_anchors if a.citation_path == CFR_LEAF)
    # Same span, but the anchor claims a label that is not at the head.
    wrong = dataclasses.replace(good, label="xiv")
    with pytest.raises(AnchorVerificationError, match="label"):
        verify_anchor(wrong, body)


def test_drifted_parent_body_is_caught(
    ma_leaf_provision: ProvisionRecord, ma_anchors: list[ProvisionAnchor]
) -> None:
    # A parent whose body changed since generation must trigger a rebuild.
    drifted = dataclasses.replace(
        ma_leaf_provision, body=(ma_leaf_provision.body or "") + " EDIT"
    )
    with pytest.raises(AnchorVerificationError, match="hash drifted"):
        verify_anchors_against_provisions(ma_anchors, [drifted])


def test_stored_leaf_missing_label_raises() -> None:
    bad = ProvisionRecord(
        jurisdiction="us-ma",
        document_class="regulation",
        citation_path="us-ma/regulation/106-cmr/365/180/A",
        id="00000000-0000-0000-0000-000000000002",
        version="v",
        body="No printed label paragraph here at all.",
    )
    with pytest.raises(AnchorVerificationError, match="not found"):
        anchor_for_stored_leaf(bad)


def test_invalid_confidence_rejected() -> None:
    with pytest.raises(ValueError, match="confidence"):
        ProvisionAnchor(
            citation_path="x/y/z",
            parent_provision_id="id",
            parent_citation_path="x/y",
            char_start=0,
            char_end=1,
            text="(z)",
            label="z",
            depth=0,
            confidence="totally-made-up",
        )


def test_invalid_span_rejected() -> None:
    with pytest.raises(ValueError, match="span"):
        ProvisionAnchor(
            citation_path="x/y/z",
            parent_provision_id="id",
            parent_citation_path="x/y",
            char_start=10,
            char_end=5,
            text="",
            label="z",
            depth=0,
        )


# --------------------------------------------------------------------------- #
# Derived-artifact discipline: committed JSONL == regenerated output            #
# --------------------------------------------------------------------------- #


def test_committed_cfr_anchors_match_generator(
    cfr_anchors: list[ProvisionAnchor],
) -> None:
    if not CFR_ANCHORS.exists():
        pytest.skip("committed CFR anchors artifact not present")
    committed = load_anchors(CFR_ANCHORS)
    got = {a.citation_path: a.to_mapping() for a in cfr_anchors}
    have = {a.citation_path: a.to_mapping() for a in committed}
    assert got == have, (
        "committed data/corpus/anchors is stale; rerun generate-anchors"
    )


def test_committed_ma_anchors_match_generator(
    ma_anchors: list[ProvisionAnchor],
) -> None:
    if not MA_ANCHORS.exists():
        pytest.skip("committed us-ma anchors artifact not present")
    committed = load_anchors(MA_ANCHORS)
    got = {a.citation_path: a.to_mapping() for a in ma_anchors}
    have = {a.citation_path: a.to_mapping() for a in committed}
    assert got == have


def test_roundtrip_jsonl(
    tmp_path: Path, cfr_anchors: list[ProvisionAnchor]
) -> None:
    out = tmp_path / "anchors.jsonl"
    n = write_anchors_jsonl(out, cfr_anchors)
    assert n == len(cfr_anchors)
    back = load_anchors(out)
    assert [a.to_mapping() for a in back] == [a.to_mapping() for a in cfr_anchors]


def test_extractor_version_is_stamped(cfr_anchors: list[ProvisionAnchor]) -> None:
    assert all(a.extractor_version == EXTRACTOR_VERSION for a in cfr_anchors)
    # The parent-body hash is recorded for the staleness guard.
    assert all(len(a.parent_body_sha256) == 64 for a in cfr_anchors)


def test_generation_is_deterministic(cfr_section: ProvisionRecord) -> None:
    a1 = generate_anchors_for_provision(cfr_section)
    a2 = generate_anchors_for_provision(cfr_section)
    assert [a.to_mapping() for a in a1] == [a.to_mapping() for a in a2]


# The columns declared in the DDL (supabase migration), minus server-managed
# ``created_at``. The supabase-row mapping must stay a subset of these so a
# PostgREST upsert never references a nonexistent column.
_DDL_COLUMNS = frozenset(
    {
        "citation_path",
        "parent_provision_id",
        "parent_citation_path",
        "char_start",
        "char_end",
        "anchor_text",
        "label",
        "depth",
        "confidence",
        "status",
        "extractor_version",
        "parent_body_sha256",
        "jurisdiction",
        "document_class",
        "version",
        "ordinal",
        "metadata",
    }
)


def test_supabase_row_renames_text_to_anchor_text() -> None:
    anchor = ProvisionAnchor(
        citation_path="x/y/z",
        parent_provision_id="00000000-0000-0000-0000-000000000003",
        parent_citation_path="x/y",
        char_start=0,
        char_end=3,
        text="(z)",
        label="z",
        depth=0,
    )
    row = anchor_to_supabase_row(anchor)
    # The DB column is anchor_text, not text (text is a Postgres type keyword).
    assert "text" not in row
    assert row["anchor_text"] == "(z)"


def test_supabase_row_columns_are_a_subset_of_the_ddl(
    ma_anchors: list[ProvisionAnchor],
) -> None:
    for anchor in ma_anchors:
        row_columns = set(anchor_to_supabase_row(anchor))
        unknown = row_columns - _DDL_COLUMNS
        assert not unknown, f"row has columns not in the DDL: {unknown}"


def test_migration_ddl_matches_expected_columns() -> None:
    # Guard the DDL itself: every expected column must appear in the migration
    # so the table the loader targets actually has them.
    migration = (
        REPO_ROOT
        / "supabase"
        / "migrations"
        / "20260704120000_corpus_provision_anchors.sql"
    )
    if not migration.exists():
        pytest.skip("migration not present")
    sql = migration.read_text()
    for column in _DDL_COLUMNS:
        assert column in sql, f"DDL is missing column {column!r}"
    # citation_path must be the primary key (the stable leaf key, not a surrogate).
    assert "citation_path         TEXT PRIMARY KEY" in sql
