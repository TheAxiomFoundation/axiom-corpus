"""Stale references to the July 2026 recovery scopes the wave4 line superseded.

``scripts/mark_superseded_tax_matrix_citations.py`` points the 2026-09-11 tax
matrix's recovery citations at the chapter-scope sections that carry the same
text, and the CA queue row records that the chapter supersedes only the R&TC
half of the CA recovery scope.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from functools import cache
from pathlib import Path

import yaml

from scripts.mark_superseded_tax_matrix_citations import (
    CARRIERS,
    MARKER,
    MATRIX,
    RECOVERY,
    carried_at,
    carrier_paths,
    mark,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from state_tax_ty2026_amounts import CA_RECOVERY_SUPERSESSION, STATUTE_ROWS  # noqa: E402


def _matrix_text() -> str:
    with (REPO_ROOT / MATRIX).open(encoding="utf-8", newline="") as handle:
        return handle.read()


@cache
def _recovery_paths(jurisdiction: str) -> tuple[str, ...]:
    path = CORPUS_ROOT / "provisions" / jurisdiction / "statute" / f"{RECOVERY}.jsonl"
    return tuple(
        json.loads(line)["citation_path"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def test_marking_the_committed_matrix_again_changes_nothing() -> None:
    text = _matrix_text()
    assert mark(text, CORPUS_ROOT) == text


def test_every_superseded_recovery_citation_names_a_carrier_row() -> None:
    rows = list(csv.DictReader(io.StringIO(_matrix_text())))
    marked = [
        row for row in rows if row["jurisdiction"] in CARRIERS and row["scope_version"] == RECOVERY
    ]
    assert len(marked) == 39
    assert sum(MARKER in row["evidence_note"] for row in rows) == 39
    for row in marked:
        jurisdiction = row["jurisdiction"]
        # The 2026-09-11 citation itself is unchanged and still a recovery row.
        assert row["citation_path"] in _recovery_paths(jurisdiction)
        path = carried_at(row["citation_path"], carrier_paths(CORPUS_ROOT, jurisdiction))
        assert path is not None
        version, pr = CARRIERS[jurisdiction]
        assert row["evidence_note"].endswith(
            f"as {path} in {jurisdiction}/statute/{version}; see axiom-corpus#{pr}]"
        )


def test_chapter_scopes_carry_every_recovery_section_but_the_ca_wic_rows() -> None:
    """Backs the queue's ``supersedes`` entries for the audited states."""
    for jurisdiction in CARRIERS:
        carried = carrier_paths(CORPUS_ROOT, jurisdiction)
        uncarried = {
            path
            for path in _recovery_paths(jurisdiction)
            if "/recovery/" not in path and carried_at(path, carried) is None
        }
        if jurisdiction == "us-ca":
            assert uncarried == {
                "us-ca/statute/wic/11450/a/1/A",
                "us-ca/statute/wic/11450/a/1/A/block-1",
                "us-ca/statute/wic/11450/a/1/A/block-2",
            }
        else:
            assert uncarried == set(), jurisdiction
        spec = STATUTE_ROWS[jurisdiction]
        assert f"{jurisdiction}/statute/{RECOVERY}" in spec["supersedes"]
        assert CARRIERS[jurisdiction][0] in spec["versions"]


def test_the_ca_queue_row_records_the_partial_supersession() -> None:
    queue = yaml.safe_load((REPO_ROOT / "manifests/tax-agent-queue.yaml").read_text())
    [ca] = [
        row
        for row in queue["states"]
        if row["jurisdiction"] == "us-ca" and "income_tax_chapter_scope" in row
    ]
    chapter = ca["income_tax_chapter_scope"]
    assert chapter["supersedes_note"] == CA_RECOVERY_SUPERSESSION
    assert STATUTE_ROWS["us-ca"]["supersedes_note"] == CA_RECOVERY_SUPERSESSION
    assert "us-ca/statute/2026-07-13-recovery" in chapter["supersedes"]
    others = [
        row["income_tax_chapter_scope"]
        for row in queue["states"]
        if row["jurisdiction"] in CARRIERS
        and row["jurisdiction"] != "us-ca"
        and "income_tax_chapter_scope" in row
    ]
    assert len(others) == 5
    assert all("supersedes_note" not in scope for scope in others)
