"""Sequence continuity against the extractor it replaced.

``provision-anchors/2.0.0`` changes where a printed label lands only where
``1.0.1`` filed it under the wrong parent. These tests hold it to that:

1. Differential. ``tests/_reference_anchors_v1.py`` is the 1.0.1 module,
   verbatim. For every body whose truth is known (eCFR's published paragraph
   ids, or the outline a generated body was rendered from), each top-level
   paragraph that 1.0.1 already read right keeps every anchor: same path,
   offsets, text, label and depth. A section 1.0.1 read right keeps them all.
2. Property. In document order a paragraph opens at most one level below the
   one before it, for any input text: continuity can close many levels at
   once but never skips one going down.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import tests._reference_anchors_v1 as v1
from axiom_corpus.corpus.anchors import (
    AnchorVerificationError,
    ProvisionAnchor,
    generate_anchors_for_provision,
)
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import ProvisionRecord
from tests.test_provision_anchor_outline import (
    FRAGMENTS,
    PROPERTY_SETTINGS,
    Para,
    _expected_paths,
    _render,
    outlines,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "provision_anchors"
ECFR_SECTIONS = json.loads((FIXTURES / "ecfr_paragraph_ids.json").read_text())
CFR_273_9 = json.loads((FIXTURES / "ecfr_paragraph_ids_7_cfr_273_9.json").read_text())
CFR_273_9_PROVISIONS = (
    REPO_ROOT
    / "data/corpus/provisions/us/regulation"
    / "2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained.jsonl"
)
SECTION = "us/regulation/1/1/1"


def _provision(body: str, citation_path: str = SECTION) -> ProvisionRecord:
    return ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path=citation_path,
        id="00000000-0000-0000-0000-000000000001",
        version="test",
        body=body,
    )


def _relative(anchor: ProvisionAnchor) -> str:
    return anchor.citation_path.removeprefix(anchor.parent_citation_path + "/")


def _comparable(anchor: ProvisionAnchor) -> dict[str, object]:
    # extractor_version differs by construction. ordinal counts siblings, so it
    # moves when 2.0.0 recovers a sibling 1.0.1 had filed elsewhere; the paths,
    # spans and depth are what a citation resolves to.
    mapping = anchor.to_mapping()
    mapping.pop("extractor_version")
    mapping.pop("ordinal")
    return mapping


def _by_top_level(anchors: list[ProvisionAnchor]) -> dict[str, dict[str, dict[str, object]]]:
    grouped: dict[str, dict[str, dict[str, object]]] = {}
    for anchor in anchors:
        path = _relative(anchor)
        grouped.setdefault(path.split("/")[0], {})[path] = _comparable(anchor)
    return grouped


def _unchanged_where_1_0_1_was_right(
    record: ProvisionRecord, truth: set[str]
) -> tuple[int, int]:
    """Assert the differential for one body; return (subtrees checked, total)."""
    old = _by_top_level(v1.generate_anchors_for_provision(record))
    new = _by_top_level(generate_anchors_for_provision(record))
    true_tops: dict[str, set[str]] = {}
    for path in truth:
        true_tops.setdefault(path.split("/")[0], set()).add(path)
    checked = 0
    for top, true_paths in true_tops.items():
        if set(old.get(top, {})) != true_paths:
            continue
        checked += 1
        assert new.get(top) == old[top], (
            f"{record.citation_path}({top}): 1.0.1 already matched eCFR here, "
            "so 2.0.0 must leave its anchors unchanged"
        )
    return checked, len(true_tops)


def test_top_level_paragraphs_1_0_1_read_right_keep_their_anchors() -> None:
    checked = total = 0
    for section in ECFR_SECTIONS:
        record = _provision(section["body"], section["citation_path"])
        section_checked, section_total = _unchanged_where_1_0_1_was_right(
            record, set(section["ecfr_paragraph_ids"])
        )
        checked += section_checked
        total += section_total
    # Anti-vacuous: most top-level paragraphs of the fixtures were already right.
    assert (checked, total) == (33, 46)


@pytest.mark.parametrize(
    "section", ECFR_SECTIONS, ids=[section["citation"] for section in ECFR_SECTIONS]
)
def test_a_section_1_0_1_read_right_keeps_every_anchor(section: dict) -> None:
    record = _provision(section["body"], section["citation_path"])
    old = v1.generate_anchors_for_provision(record)
    if {_relative(anchor) for anchor in old} != set(section["ecfr_paragraph_ids"]):
        pytest.skip("1.0.1 mis-nests this section; the subtree differential covers it")
    new = generate_anchors_for_provision(record)
    assert [a.to_mapping() for a in new] == [
        {**a.to_mapping(), "extractor_version": new[0].extractor_version} for a in old
    ]


def test_the_fixtures_hold_a_section_1_0_1_already_read_right() -> None:
    # Anti-vacuous for the whole-section differential above: 26 CFR 1.62-1.
    exact = [
        section["citation"]
        for section in ECFR_SECTIONS
        if {
            _relative(anchor)
            for anchor in v1.generate_anchors_for_provision(
                _provision(section["body"], section["citation_path"])
            )
        }
        == set(section["ecfr_paragraph_ids"])
    ]
    assert exact == ["26 CFR 1.62-1"]


def test_7_cfr_273_9_keeps_the_paragraphs_1_0_1_read_right() -> None:
    record = next(
        row
        for row in load_provisions(CFR_273_9_PROVISIONS)
        if row.citation_path == CFR_273_9["citation_path"]
    )
    checked, total = _unchanged_where_1_0_1_was_right(
        record, set(CFR_273_9["ecfr_paragraph_ids"])
    )
    # 1.0.1 read (a) and (b) right. It filed (c)(2)-(c)(11) under (c)(1)(vii)(C)
    # and (d)(6)(iii)(E)-(G) under (d)(6)(iii)(D)(3)(vii).
    assert (checked, total) == (2, 4)


@settings(PROPERTY_SETTINGS, max_examples=150)
@given(outlines())
def test_a_generated_outline_1_0_1_read_right_parses_identically(outline: list[Para]) -> None:
    body = _render(outline)
    try:
        old = v1.generate_anchors_for_provision(_provision(body))
    except v1.AnchorVerificationError:
        old = None
    assume(old is not None and [_relative(a) for a in old] == _expected_paths(outline))
    assert old is not None
    new = generate_anchors_for_provision(_provision(body))
    assert [_comparable(a) for a in new] == [_comparable(a) for a in old]


def _assert_depth_steps_down_one_level_at_a_time(body: str) -> None:
    try:
        anchors = generate_anchors_for_provision(_provision(body))
    except AnchorVerificationError as exc:
        assert "duplicate anchor citation paths" in str(exc)
        return
    depths = [anchor.depth for anchor in anchors]
    if depths:
        assert depths[0] == 0, "the first paragraph is top level"
    for before, after in zip(depths, depths[1:], strict=False):
        assert after <= before + 1, f"depth jumped from {before} to {after}"
    for anchor in anchors:
        assert anchor.depth == _relative(anchor).count("/")


@PROPERTY_SETTINGS
@given(outlines())
def test_a_printed_outline_never_skips_a_level(outline: list[Para]) -> None:
    _assert_depth_steps_down_one_level_at_a_time(_render(outline))


@PROPERTY_SETTINGS
@given(st.lists(st.sampled_from(FRAGMENTS), max_size=40).map("".join))
def test_label_soup_never_skips_a_level(body: str) -> None:
    _assert_depth_steps_down_one_level_at_a_time(body)


@PROPERTY_SETTINGS
@given(st.text(max_size=200))
def test_arbitrary_text_never_skips_a_level(body: str) -> None:
    _assert_depth_steps_down_one_level_at_a_time(body)


@pytest.mark.parametrize(
    "section", ECFR_SECTIONS, ids=[section["citation"] for section in ECFR_SECTIONS]
)
def test_real_sections_never_skip_a_level(section: dict) -> None:
    _assert_depth_steps_down_one_level_at_a_time(section["body"])


def test_the_depth_check_can_fail() -> None:
    # Anti-vacuous: the check rejects a jump when one is fed to it.
    depths = [0, 2]
    with pytest.raises(AssertionError):
        for before, after in zip(depths, depths[1:], strict=False):
            assert after <= before + 1
