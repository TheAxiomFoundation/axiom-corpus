"""The South Carolina chapter 6 scope that carries S.C. Code Section 12-6-520.

``2026-09-27-sc-act110-with-12-6-520-us-sc-title-12-chapter-6`` is the 2026-07-24
Act 110 scope extracted again from the same retained bytes, without that scope's
``excluded_sections: ["12-6-520"]``. It replaces both that scope and
``us-sc/statute/2026-07-13-recovery``, whose only row at the section's path is
an empty document root. Run note:
``docs/ingest-runs/2026-09-27-us-sc-12-6-520-successor.md``.
"""

from __future__ import annotations

import hashlib
import json
import socket
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.state_adapters.south_carolina import (
    parse_south_carolina_chapter_html,
    parse_south_carolina_session_law_overlay,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
MANIFEST = ROOT / "manifests/state-income-tax-recovery.yaml"
RELEASES = ROOT / "manifests/releases"

NEW = "2026-09-27-sc-act110-with-12-6-520-us-sc-title-12-chapter-6"
ACT110 = "2026-07-24-sc-act110-us-sc-title-12-chapter-6"
RECOVERY = "2026-07-13-recovery"
SECTION = "us-sc/statute/12-6-520"
PROFILE = "complete-expression-dates-v1"
# The sections 2026 Act No. 110 amends; the manifest overlays each one.
OVERLAID = ("12-6-510", "12-6-50", "12-6-1140", "12-6-4910", "12-6-1720", "12-6-3632")
# The row "Deduplicate PIT release citations" (fbc9f07da) removed from
# 2026-07-16-pit-central-us-sc-title-12-chapter-6 had this heading and body.
HEADING = "Annual adjustments to individual state income tax brackets; inflation adjustments"
BODY_SHA256 = "74a4b7ac7883d9b0972cfa27dad8918271efe30c7b9ce61c235fe9133381328c"
CHAPTER_HTML_SHA256 = "ae31dbc10579d61076ca1b6a48a5a240eab85547ad42df8642e99affbf31909d"
# Fields that name the scope's version and nothing else.
VERSION_FIELDS = ("id", "parent_id", "version", "source_path")


def _artifacts(base: Path, version: str) -> dict[str, bytes]:
    paths = [
        base / f"inventory/us-sc/statute/{version}.json",
        base / f"provisions/us-sc/statute/{version}.jsonl",
        base / f"coverage/us-sc/statute/{version}.json",
        *sorted(p for p in (base / f"sources/us-sc/statute/{version}").rglob("*") if p.is_file()),
    ]
    return {str(path.relative_to(base)): path.read_bytes() for path in paths}


def _rows(version: str) -> list[dict[str, Any]]:
    path = CORPUS / f"provisions/us-sc/statute/{version}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _without_version(row: dict[str, Any], version: str) -> dict[str, Any]:
    stripped = {key: value for key, value in row.items() if key not in VERSION_FIELDS}
    return dict(json.loads(json.dumps(stripped).replace(version, "<version>")))


def _statute(version: str) -> tuple[str, str, str]:
    return ("us-sc", "statute", version)


def _validate(*scopes: tuple[str, str, str]) -> dict[str, Any]:
    release = ReleaseManifest(
        name="us-sc-12-6-520-successor-validation",
        quality_profile=PROFILE,
        scopes=tuple(ReleaseScope(*scope) for scope in scopes),
    )
    return dict(validate_release(CORPUS, release, strict_warnings=True).to_mapping())


def _selected(name: str) -> list[tuple[str, str, str]]:
    payload = json.loads((RELEASES / f"{name}.json").read_text(encoding="utf-8"))
    return [(s["jurisdiction"], s["document_class"], s["version"]) for s in payload["scopes"]]


# Every tracked selector that carries the Act 110 scope (each also carries the
# recovery scope): the cuts a later one takes the paired swap from. Older cuts
# carry the pit-central scope instead and are not successors' bases.
SELECTORS = sorted(
    path.stem for path in RELEASES.glob("*.json") if _statute(ACT110) in _selected(path.stem)
)
# The newest cut of each line the run note names.
KEY_LINES = (
    "us-rulespec-2026-08-08-obbb-alien-snap",
    "us-rulespec-2026-09-24-snap-fy2027-cola",
    "us-rulespec-2026-08-23-canada-338-suspension-union",
    "us-rulespec-2026-09-14-wave4-union",
    "us-rulespec-2026-09-14-wave4-r2-union",
    "us-rulespec-2026-09-24-irs-sales-tax-tables-union",
    "us-rulespec-2026-10-07-w6-bundle-gaps-union",
)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("network access is disabled in this test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _extract(tmp_path: Path, manifest: Path) -> None:
    code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path),
            "--manifest",
            str(manifest),
            "--only-source-id",
            "us-sc-code",
        ]
    )
    assert code == 0


def test_the_manifest_rebuilds_the_committed_scope_offline(
    tmp_path: Path, no_network: None
) -> None:
    _extract(tmp_path / "out", MANIFEST)
    rebuilt = _artifacts(tmp_path / "out", NEW)
    assert len(rebuilt) == 7
    assert rebuilt == _artifacts(CORPUS, NEW)


def _entry_manifest(directory: Path, *, version: str | None, excluded: list[str]) -> Path:
    """The us-sc-code entry alone, optionally re-versioned and with exclusions."""
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    (entry,) = [source for source in manifest["sources"] if source["source_id"] == "us-sc-code"]
    assert "excluded_sections" not in entry["options"]
    if version is not None:
        entry["version"] = version
    if excluded:
        entry["options"]["excluded_sections"] = excluded
    entry["options"]["source_dir"] = str(
        (MANIFEST.parent / entry["options"]["source_dir"]).resolve()
    )
    manifest["sources"] = [entry]
    path = directory / "us-sc-code.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def test_the_same_entry_with_the_exclusion_rebuilds_the_act110_scope(
    tmp_path: Path, no_network: None
) -> None:
    """Differential check: the predecessor is this entry plus ``excluded_sections``."""
    copy = _entry_manifest(tmp_path, version="2026-07-24-sc-act110", excluded=["12-6-520"])
    _extract(tmp_path / "out", copy)
    assert _artifacts(tmp_path / "out", ACT110) == _artifacts(CORPUS, ACT110)


def _section_key(row: dict[str, Any]) -> str | None:
    return (row.get("metadata") or {}).get("section")


def _excludable() -> st.SearchStrategy[set[str]]:
    sections = sorted({_section_key(row) for row in _rows(NEW)} - {None, *OVERLAID}, key=str)
    assert len(sections) == 157 - len(OVERLAID)
    return st.sets(st.sampled_from(sections), max_size=4)


@settings(max_examples=12, deadline=None)
@given(excluded=st.deferred(_excludable))
def test_excluding_sections_drops_exactly_their_rows(excluded: set[str]) -> None:
    """For any set of sections the overlay does not target, ``excluded_sections``
    removes exactly those sections' rows and items and changes no other byte of
    any other row: the property the Act 110 scope and this successor rest on."""
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        manifest = _entry_manifest(base, version=None, excluded=sorted(excluded))
        _extract(base / "out", manifest)
        out = base / "out"
        provisions = (out / f"provisions/us-sc/statute/{NEW}.jsonl").read_text(encoding="utf-8")
        inventory = load_source_inventory(out / f"inventory/us-sc/statute/{NEW}.json")
        coverage = json.loads((out / f"coverage/us-sc/statute/{NEW}.json").read_text())
    rows = [json.loads(line) for line in provisions.splitlines() if line]
    assert rows == [row for row in _rows(NEW) if _section_key(row) not in excluded]
    assert [item.citation_path for item in inventory] == [
        item.citation_path
        for item in load_source_inventory(CORPUS / f"inventory/us-sc/statute/{NEW}.json")
        if item.citation_path.removeprefix("us-sc/statute/") not in excluded
    ]
    assert coverage["complete"] is True
    assert coverage["matched_count"] == 159 - len(excluded)


def test_only_the_restored_section_differs_from_the_act110_scope() -> None:
    new, old = _rows(NEW), _rows(ACT110)
    assert len(new) == len(old) + 1 == 159
    assert [row["citation_path"] for row in new if row["citation_path"] != SECTION] == [
        row["citation_path"] for row in old
    ]
    assert [_without_version(row, NEW) for row in new if row["citation_path"] != SECTION] == [
        _without_version(row, ACT110) for row in old
    ]

    new_items = load_source_inventory(CORPUS / f"inventory/us-sc/statute/{NEW}.json")
    old_items = load_source_inventory(CORPUS / f"inventory/us-sc/statute/{ACT110}.json")
    assert [item.citation_path for item in new_items if item.citation_path != SECTION] == [
        item.citation_path for item in old_items
    ]
    assert [item.sha256 for item in new_items if item.citation_path != SECTION] == [
        item.sha256 for item in old_items
    ]

    coverage = json.loads((CORPUS / f"coverage/us-sc/statute/{NEW}.json").read_text())
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["provision_count"] == 159


def test_the_scope_is_self_contained_with_versioned_ids() -> None:
    prefix = f"sources/us-sc/statute/{NEW}/"
    for record in load_provisions(CORPUS / f"provisions/us-sc/statute/{NEW}.jsonl"):
        assert record.version == NEW
        assert record.source_path is None or record.source_path.startswith(prefix)
        assert record.id == deterministic_provision_id(record.citation_path, NEW)
        if record.parent_citation_path is not None:
            assert record.parent_id == deterministic_provision_id(record.parent_citation_path, NEW)
        assert ACT110 not in json.dumps(record.metadata or {})
    for item in load_source_inventory(CORPUS / f"inventory/us-sc/statute/{NEW}.json"):
        assert item.source_path.startswith(prefix)


def test_the_restored_row_is_the_codified_section() -> None:
    (row,) = [row for row in _rows(NEW) if row["citation_path"] == SECTION]
    assert row["heading"] == HEADING
    assert hashlib.sha256(row["body"].encode("utf-8")).hexdigest() == BODY_SHA256
    assert (row["kind"], row["level"], row["ordinal"]) == ("section", 2, 9)
    assert row["parent_citation_path"] == "us-sc/statute/title-12/chapter-6"
    assert row["source_path"] == (
        f"sources/us-sc/statute/{NEW}/south-carolina-code-html/title-12/chapter-6.html"
    )
    assert row["metadata"] == {
        "chapter": "6",
        "kind": "section",
        "notes": ["Editor's Note", "Effect of Amendment"],
        "references_to": ["us-sc/statute/12-6-510"],
        "section": "12-6-520",
        "source_history": [
            "HISTORY: 1995 Act No. 76, SECTION 1; 2018 Act No. 266 (H.5341), "
            "SECTION 4.A, eff October 3, 2018."
        ],
        "title": "12",
    }
    # The two amounts us-sc/statutes/12-6-520.yaml in rulespec-us quotes.
    assert "the adjustment may not exceed four percent a year" in row["body"]
    assert "the rounding amount is ten dollars" in row["body"]
    (item,) = [
        item
        for item in load_source_inventory(CORPUS / f"inventory/us-sc/statute/{NEW}.json")
        if item.citation_path == SECTION
    ]
    assert item.sha256 == CHAPTER_HTML_SHA256


def test_the_recovery_scopes_retained_page_is_the_same_chapter() -> None:
    """The recovery scope kept the chapter page this row is read from."""
    page = CORPUS / (f"sources/us-sc/statute/{RECOVERY}/official-documents/us-sc-code-12-6-520")
    raw = page.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CHAPTER_HTML_SHA256
    sections = {
        section.citation_path: section
        for section in parse_south_carolina_chapter_html(raw, title=12, chapter="6")
    }
    (row,) = [row for row in _rows(NEW) if row["citation_path"] == SECTION]
    assert (sections[SECTION].heading, sections[SECTION].body) == (row["heading"], row["body"])
    (recovery_root,) = [row for row in _rows(RECOVERY) if row["citation_path"] == SECTION]
    assert recovery_root["kind"] == "document" and not recovery_root["body"]


def test_act110_does_not_amend_the_section() -> None:
    act = (
        CORPUS
        / f"sources/us-sc/statute/{NEW}/south-carolina-code-html/session-laws/2026-act-110-h4216.html"
    ).read_bytes()
    with pytest.raises(ValueError, match="does not amend South Carolina section 12-6-520"):
        parse_south_carolina_session_law_overlay(act, section="12-6-520")
    (row,) = [row for row in _rows(NEW) if row["citation_path"] == SECTION]
    assert "session_law_overlay" not in row["metadata"]
    assert "source_components" not in row["metadata"]


def test_the_successor_carries_no_path_its_predecessors_did_not() -> None:
    """With the paired swap, no cut that validated before can gain a duplicate."""
    new = {row["citation_path"] for row in _rows(NEW)}
    act110 = {row["citation_path"] for row in _rows(ACT110)}
    recovery = {row["citation_path"] for row in _rows(RECOVERY)}
    assert new == act110 | {SECTION}
    assert SECTION in recovery and not act110 & recovery
    assert recovery - new == {f"{SECTION}/block-1", f"{SECTION}/block-2"}


def test_every_act110_selector_also_selects_the_recovery_scope() -> None:
    assert set(KEY_LINES) <= set(SELECTORS)
    for name in SELECTORS:
        statute = {scope for scope in _selected(name) if scope[:2] == ("us-sc", "statute")}
        assert _statute(RECOVERY) in statute, name
        assert _statute(NEW) not in statute, name
        payload = json.loads((RELEASES / f"{name}.json").read_text(encoding="utf-8"))
        assert payload["quality_profile"] == PROFILE, name


@pytest.mark.parametrize("name", SELECTORS)
def test_the_paired_swap_validates_on_every_act110_selector(name: str) -> None:
    """Every us-sc scope of the cut, with both predecessors swapped for the successor."""
    predecessors = {_statute(RECOVERY), _statute(ACT110)}
    us_sc = [
        scope for scope in _selected(name) if scope[0] == "us-sc" and scope not in predecessors
    ]
    report = _validate(*us_sc, _statute(NEW))
    assert (report["ok"], report["issue_count"]) == (True, 0), report["issues"][:3]


def test_keeping_either_predecessor_beside_it_is_a_duplicate_citation() -> None:
    with_recovery = _validate(_statute(RECOVERY), _statute(NEW))
    assert Counter(issue["code"] for issue in with_recovery["issues"]) == {
        "duplicate_release_citation": 1
    }
    assert SECTION in with_recovery["issues"][0]["message"]
    with_act110 = _validate(_statute(ACT110), _statute(NEW))
    assert with_act110["error_count"] == 158
    assert {issue["code"] for issue in with_act110["issues"]} == {"duplicate_release_citation"}
