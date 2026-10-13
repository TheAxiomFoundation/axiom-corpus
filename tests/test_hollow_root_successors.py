"""Committed-artifact checks for the 2026-10-13 hollow-document-root successor scopes.

Each successor rebuilds one merged scope from its retained bytes with the fixed
extractors (``scripts/repro/hollow_root_successors.py``; run note
``docs/ingest-runs/2026-10-13-hollow-root-successors.md``). The originals stay
unchanged, and the draft selectors swap each selected original for its successor.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.corpus_locks import load_locks
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.hollow_root_successors import (
    REVISION,
    SuccessorSpec,
    block_network,
    build_one,
    compare_rows,
    source_prefix_map,
    successor_specs,
    swap_successors,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
RUN_NOTE = REPO_ROOT / "docs/ingest-runs/2026-10-13-hollow-root-successors.md"
SUMMARY = REPO_ROOT / "docs/ingest-runs/2026-10-13-hollow-root-successors.json"
DRAFT_SELECTORS = {
    "us-rulespec-2026-10-13-w7-bundle-gaps-union": REPO_ROOT
    / "docs/ingest-runs/2026-10-13-hollow-root-successors-union.selector.json",
    "us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected": REPO_ROOT
    / "docs/ingest-runs/2026-10-13-hollow-root-successors-snap.selector.json",
    "ca-rulespec-2026-07-21-source-complete": REPO_ROOT
    / "docs/ingest-runs/2026-10-13-hollow-root-successors-ca.selector.json",
}
SPECS = successor_specs()
LETTER = re.compile(r"[^\W\d_]")


@cache
def _summary() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return payload


@cache
def _locks() -> Any:
    return load_locks(REPO_ROOT)


def _lock_files(spec: SuccessorSpec, version: str) -> dict[str, tuple[str, int]]:
    lock = _locks().locks[(spec.jurisdiction, spec.document_class, version)]
    return {entry.path: (entry.sha256, entry.size) for entry in lock.files}


def _rows(spec: SuccessorSpec, version: str) -> list[dict[str, Any]]:
    path = CORPUS_ROOT / "provisions" / spec.jurisdiction / spec.document_class / f"{version}.jsonl"
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_specs_name_one_successor_per_original() -> None:
    originals = [spec.original_key for spec in SPECS]
    assert len(originals) == len(set(originals)) == 108
    for spec in SPECS:
        assert spec.version == f"{spec.original_version}-{REVISION}"
        # The release gate orders a line's versions by date, then by string: the
        # successor keeps its original's capture date and sorts after it.
        assert spec.version > spec.original_version
        assert spec.version.startswith(spec.original_version[:10])


def test_every_successor_is_locked_and_signed() -> None:
    for spec in SPECS:
        key = (spec.jurisdiction, spec.document_class, spec.version)
        assert key in _locks().locks, spec.key
        manifest = REPO_ROOT / ".axiom/ingest-manifests" / f"{spec.key}.json"
        signed = json.loads(manifest.read_text(encoding="utf-8"))
        applied = {row["path"]: row["sha256"] for row in signed["applied_files"]}
        assert applied == {path: sha for path, (sha, _) in _lock_files(spec, spec.version).items()}
        assert "scripts/repro/hollow_root_successors.py" in signed["command"]["text"]


def test_successor_sources_are_the_retained_bytes() -> None:
    """Every successor source file is a byte-identical copy of one of its original's."""
    for spec in SPECS:
        old_prefix, new_prefix = source_prefix_map(spec, spec.original_version, spec.version)
        original = {
            path.replace(f"data/corpus/{old_prefix}", f"data/corpus/{new_prefix}"): value
            for path, value in _lock_files(spec, spec.original_version).items()
            if path.startswith(f"data/corpus/{old_prefix}")
        }
        successor = {
            path: value
            for path, value in _lock_files(spec, spec.version).items()
            if path.startswith("data/corpus/sources/")
        }
        assert successor == original, spec.key


def test_summary_records_every_successor() -> None:
    rows = {row["scope"]: row for row in _summary()["scopes"]}
    assert set(rows) == {spec.original_key for spec in SPECS}
    for spec in SPECS:
        row = rows[spec.original_key]
        assert row["successor"] == spec.key
        assert row["sources_identical"] is True
        assert row["coverage_complete"] is True
        assert row["control_reproduces_original"] is True


def test_successor_coverage_is_complete() -> None:
    for spec in SPECS:
        coverage = json.loads(
            (
                CORPUS_ROOT
                / "coverage"
                / spec.jurisdiction
                / spec.document_class
                / f"{spec.version}.json"
            ).read_text(encoding="utf-8")
        )
        assert coverage["complete"] is True, spec.key
        assert coverage["version"] == spec.version


def test_only_the_documented_rows_disappear() -> None:
    """Successors keep every original citation path except the ones the fixes retire."""
    documented = {
        (row["scope"], path)
        for row in _summary()["scopes"]
        for path in row["provisions"]["removed"]
    }
    assert documented == set(map(tuple, _summary()["expected_removed"]))
    for spec in SPECS:
        before = [row["citation_path"] for row in _rows(spec, spec.original_version)]
        after = [row["citation_path"] for row in _rows(spec, spec.version)]
        kept = [path for path in before if path in set(after)]
        assert set(before) - set(after) == {
            path for scope, path in documented if scope == spec.original_key
        }, spec.key
        # The surviving rows keep their order.
        assert [path for path in after if path in set(before)] == kept, spec.key


def _has_text(row: dict[str, Any]) -> bool:
    return bool(LETTER.search(row.get("body") or ""))


def test_audited_hollow_roots_now_carry_text() -> None:
    """Each fixed audit finding's root has text at or below it, or is retired."""
    by_scope = {spec.original_key: spec for spec in SPECS}
    for scope, path, outcome in _summary()["fixed_findings"]:
        rows = _rows(by_scope[scope], by_scope[scope].version)
        here = [
            row
            for row in rows
            if row["citation_path"] == path or row["citation_path"].startswith(f"{path}/")
        ]
        if outcome == "retired":
            assert not here, (scope, path)
        else:
            assert outcome == "text"
            assert any(_has_text(row) for row in here), (scope, path)


@pytest.mark.parametrize("base_name", sorted(DRAFT_SELECTORS))
def test_draft_selectors_swap_exactly_the_originals(base_name: str) -> None:
    base = json.loads((REPO_ROOT / "manifests/releases" / f"{base_name}.json").read_text("utf-8"))
    draft = json.loads(DRAFT_SELECTORS[base_name].read_text(encoding="utf-8"))
    expected, swapped = swap_successors(base)
    assert swapped
    assert draft["scopes"] == expected["scopes"]
    assert draft["quality_profile"] == base["quality_profile"]
    assert base_name in draft["description"]
    ReleaseManifest.load(DRAFT_SELECTORS[base_name])


def test_no_tracked_selector_selects_an_original_with_its_successor() -> None:
    pairs = {(spec.original_key, spec.key) for spec in SPECS}
    for path in sorted((REPO_ROOT / "manifests/releases").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        keys = {
            f"{s['jurisdiction']}/{s['document_class']}/{s['version']}" for s in payload["scopes"]
        }
        assert not any(old in keys and new in keys for old, new in pairs), path.name


# --------------------------------------------------------------------------- offline rebuilds

# Scopes small enough to rebuild in the suite; none needs Tesseract.
REBUILT = (
    "us-md/statute/2026-07-03-md-tca-statutes",
    "us-ma/regulation/2026-06-27-ma-tafdc-regulations",
    "us-ny/regulation/2026-07-17-ny-snap-regulations",
    "ca/policy/2026-07-21-ca-rulespec-source-complete",
)


@pytest.fixture
def offline() -> Iterator[None]:
    restore = block_network()
    try:
        yield
    finally:
        restore()


@pytest.mark.timeout(300)
@pytest.mark.parametrize("original", REBUILT)
def test_successors_rebuild_byte_for_byte_offline(
    original: str, tmp_path: Path, offline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    spec = next(spec for spec in SPECS if spec.original_key == original)
    result = build_one(spec, base=tmp_path, source_base=CORPUS_ROOT)
    assert result["coverage_complete"]
    for kind, suffix in (("inventory", ".json"), ("provisions", ".jsonl"), ("coverage", ".json")):
        rebuilt = (
            tmp_path / kind / spec.jurisdiction / spec.document_class / f"{spec.version}{suffix}"
        )
        committed = (
            CORPUS_ROOT / kind / spec.jurisdiction / spec.document_class / f"{spec.version}{suffix}"
        )
        assert rebuilt.read_bytes() == committed.read_bytes(), (original, kind)


# --------------------------------------------------------------------------- properties

_ORIGINALS = [
    {
        "jurisdiction": s.jurisdiction,
        "document_class": s.document_class,
        "version": s.original_version,
    }
    for s in SPECS
]
_OTHERS = st.builds(
    lambda j, v: {"jurisdiction": j, "document_class": "policy", "version": v},
    st.sampled_from(["us", "us-zz", "ca"]),
    st.from_regex(r"2026-0[1-9]-[0-2][1-9]-[a-z]{1,8}", fullmatch=True),
)


@settings(max_examples=200, deadline=None)
@given(
    originals=st.lists(
        st.sampled_from(_ORIGINALS), unique_by=lambda s: s["version"] + s["jurisdiction"]
    ),
    others=st.lists(_OTHERS, max_size=12),
    seed=st.randoms(use_true_random=False),
)
def test_swap_replaces_each_original_in_place(
    originals: list[dict[str, str]], others: list[dict[str, str]], seed: Any
) -> None:
    others = [o for o in others if o not in originals]
    scopes = originals + others
    seed.shuffle(scopes)
    selector = {"name": "x", "scopes": scopes}
    if not originals:
        result, swapped = swap_successors(selector)
        assert swapped == [] and result["scopes"] == scopes
        return
    result, swapped = swap_successors(selector)
    by_original = {spec.original_key: spec.version for spec in SPECS}
    assert len(result["scopes"]) == len(scopes)
    for before, after in zip(scopes, result["scopes"], strict=True):
        key = f"{before['jurisdiction']}/{before['document_class']}/{before['version']}"
        if key in by_original:
            assert after == {**before, "version": by_original[key]}
        else:
            assert after == before
    assert sorted(swapped) == sorted(
        f"{s['jurisdiction']}/{s['document_class']}/{s['version']}" for s in originals
    )
    # A swapped selector already carries the successors, so it is never swapped twice.
    with pytest.raises(ValueError, match="already selects successor"):
        swap_successors(result)


@settings(max_examples=200, deadline=None)
@given(
    rows=st.lists(
        st.fixed_dictionaries(
            {
                "citation_path": st.from_regex(r"us-zz/policy/[a-z]{1,4}", fullmatch=True),
                "body": st.one_of(st.none(), st.text(max_size=20)),
            }
        ),
        unique_by=lambda r: r["citation_path"],
        max_size=8,
    )
)
def test_compare_rows_finds_no_change_after_a_pure_reversion(rows: list[dict[str, Any]]) -> None:
    """Moving rows to a new version (version and source paths only) is no change."""
    spec = SPECS[2]
    old, new = source_prefix_map(spec, spec.original_version, spec.version)
    left = [
        {
            **row,
            "version": spec.original_version,
            "source_path": f"{old}x/{i}.pdf",
            "metadata": {"text_source_path": f"{old}a.pdf"},
        }
        for i, row in enumerate(rows)
    ]
    right = [
        {
            **row,
            "version": spec.version,
            "source_path": f"{new}x/{i}.pdf",
            "metadata": {"text_source_path": f"{new}a.pdf"},
        }
        for i, row in enumerate(rows)
    ]
    result = compare_rows(
        left,
        right,
        left_version=spec.original_version,
        right_version=spec.version,
        prefixes=(old, new),
    )
    assert result["changed"] == result["added"] == result["removed"] == []
    assert result["order_preserved"]
