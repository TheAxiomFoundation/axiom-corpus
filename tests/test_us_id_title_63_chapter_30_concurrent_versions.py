"""Committed-artifact checks for the Idaho Title 63 chapter 30 concurrent-versions scope.

The official pages for Idaho Code §§63-3022E and 63-3025D print the text in force
until January 1, 2027 and the text effective that day. This scope, re-extracted
from the bytes retained by the 2026-09-14 chapter scope, keeps the first at the
plain path and the second at ``<section>--effective-2027-01-01``. See
docs/ingest-runs/2026-09-27-id-title-63-chapter-30-concurrent-versions.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.state_adapters.idaho import (
    _clean_text,
    _rendition_starts,
    _section_content_divs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
VERSION = "2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30"
CHAPTER_VERSION = "2026-09-14-income-tax-chapter-us-id-title-63-chapter-30"
SUCCESSOR_VERSION = "2026-07-31-id-title-63-chapter-30-successor"
SOURCES = CORPUS_ROOT / f"sources/us-id/statute/{VERSION}"
MANIFEST = REPO_ROOT / "manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml"
CHAPTER_SOURCES = CORPUS_ROOT / f"sources/us-id/statute/{CHAPTER_VERSION}"
SECTION_PAGES = "idaho-statutes-section-html/title-63/chapter-30"
VARIANTS = {
    "us-id/statute/63-3022E--effective-2027-01-01": "us-id/statute/63-3022E",
    "us-id/statute/63-3025D--effective-2027-01-01": "us-id/statute/63-3025D",
}


def _jsonl(version: str) -> list[dict]:
    path = CORPUS_ROOT / f"provisions/us-id/statute/{version}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rows(version: str = VERSION) -> dict[str, dict]:
    return {row["citation_path"]: row for row in _jsonl(version)}


def _without_scope_identity(row: dict, version: str) -> dict:
    row = dict(row)
    row.pop("version")
    row["source_path"] = row["source_path"].replace(version, "<version>")
    return row


def test_the_committed_manifest_rebuilds_the_scope_offline_byte_for_byte(
    tmp_path, monkeypatch, capsys
) -> None:
    """``extract-state-statutes`` with the committed manifest, its options and
    its ``source_dir`` (the 2026-09-14 retained pages) and the network blocked,
    reproduces the provisions, inventory, coverage and sources."""

    def offline(*args, **kwargs):
        raise AssertionError("network used")

    monkeypatch.setattr("axiom_corpus.corpus.state_adapters.idaho.requests.get", offline)
    base = tmp_path / "corpus"
    exit_code = main(["extract-state-statutes", "--base", str(base), "--manifest", str(MANIFEST)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["successful"] is True
    assert payload["coverage_complete"] is True
    assert payload["provisions_written"] == 166
    [row] = payload["rows"]
    assert row["version"] == "2026-09-27-income-tax-concurrent-versions"
    assert row["errors"] == []
    for relative in (
        f"inventory/us-id/statute/{VERSION}.json",
        f"provisions/us-id/statute/{VERSION}.jsonl",
        f"coverage/us-id/statute/{VERSION}.json",
    ):
        assert (base / relative).read_bytes() == (CORPUS_ROOT / relative).read_bytes(), relative
    rebuilt = base / f"sources/us-id/statute/{VERSION}"
    committed = {
        path.relative_to(SOURCES).as_posix(): path.read_bytes()
        for path in SOURCES.rglob("*")
        if path.is_file()
    }
    assert {
        path.relative_to(rebuilt).as_posix(): path.read_bytes()
        for path in rebuilt.rglob("*")
        if path.is_file()
    } == committed
    assert committed == {
        path.relative_to(CHAPTER_SOURCES).as_posix(): path.read_bytes()
        for path in CHAPTER_SOURCES.rglob("*")
        if path.is_file()
    }
    assert len(committed) == 165


def test_the_scope_is_the_chapter_scope_plus_the_two_later_versions() -> None:
    """Every row of the superseded chapter scope is here unchanged and in order,
    apart from the scope's version and source path; the only additions are the
    two variant rows, each right after its plain row."""
    old = _jsonl(CHAPTER_VERSION)
    new = _jsonl(VERSION)
    old_paths = [row["citation_path"] for row in old]
    new_paths = [row["citation_path"] for row in new]

    assert [path for path in new_paths if path not in VARIANTS] == old_paths
    assert len(new) == len(old) + len(VARIANTS) == 166
    for variant, plain in VARIANTS.items():
        assert new_paths.index(variant) == new_paths.index(plain) + 1
    new_by_path = {row["citation_path"]: row for row in new}
    for row in old:
        assert _without_scope_identity(
            new_by_path[row["citation_path"]], VERSION
        ) == _without_scope_identity(row, CHAPTER_VERSION)


def test_the_2026_07_31_successor_rows_are_carried_with_the_same_text() -> None:
    """The five sections, title and chapter of the other carrier are here with
    the same heading, body, label, parent and section metadata."""
    new = _rows()
    for path, row in _rows(SUCCESSOR_VERSION).items():
        mine = new[path]
        for field in (
            "heading",
            "body",
            "citation_label",
            "legal_identifier",
            "identifiers",
            "kind",
            "level",
        ):
            assert mine[field] == row[field], (path, field)
        assert mine.get("parent_citation_path") == row.get("parent_citation_path")
        if row["kind"] == "section":
            assert mine["metadata"] == row["metadata"], path


def test_the_variant_rows_carry_the_text_effective_january_1_2027() -> None:
    rows = _rows()
    for variant, plain in VARIANTS.items():
        later, current = rows[variant], rows[plain]
        metadata = later["metadata"]
        assert metadata["variant"] == "effective-2027-01-01"
        assert metadata["canonical_citation_path"] == plain
        assert metadata["effective_note"] == "effective January 1, 2027"
        assert metadata["status"] == "future_or_conditional"
        assert "variant" not in current["metadata"]
        assert "status" not in current["metadata"]
        for field in (
            "parent_citation_path",
            "parent_id",
            "level",
            "ordinal",
            "kind",
            "heading",
            "citation_label",
            "legal_identifier",
            "identifiers",
            "source_url",
            "source_path",
            "source_format",
        ):
            assert later[field] == current[field], (variant, field)
        assert later["source_id"] == variant.rsplit("/", 1)[1]
        assert later["id"] != current["id"]
        assert current["body"].startswith("[effective until January 1, 2027] (1) ")
        assert later["body"].startswith("[effective January 1, 2027] (1) ")
        for field in ("source_history", "references_to", "section", "title", "chapter"):
            assert metadata[field] == current["metadata"][field], (variant, field)


def test_the_two_versions_differ_only_in_the_marker_and_the_66_402_reference() -> None:
    """Word for word, the 2027 text replaces "subsection (5) of section 66-402" with
    "section 66-402 (4)" and nothing else: every amount, count, age and fraction
    is the same in both versions."""
    rows = _rows()
    old_reference, new_reference = "subsection (5) of section 66-402 ,", "section 66-402 (4),"
    for variant, plain in VARIANTS.items():
        before, after = rows[plain]["body"], rows[variant]["body"]
        # Each version cites the definition twice, in (1) and (4).
        assert before.count(old_reference) == after.count(new_reference) == 2
        assert new_reference not in before and old_reference not in after
        assert before.replace("[effective until January 1, 2027]", "[marker]").replace(
            old_reference, "<66-402 definition>"
        ) == after.replace("[effective January 1, 2027]", "[marker]").replace(
            new_reference, "<66-402 definition>"
        )


def test_only_these_two_retained_chapter_30_pages_print_more_than_one_rendition() -> None:
    """All 162 section pages the chapter scope retained, read three ways:
    rendition starts, bracketed effective-date markers anywhere in the statute
    text, and 2026 session laws in the History notes. Only §§63-3022E and
    63-3025D print two renditions, only they carry such markers, and only they
    cite 2026 ch. 79."""
    import re

    marker = re.compile(
        r"\[[^\]]*\b(?:effective|until|repeal|expire|operative|contingent|terminat|null)[^\]]*\]",
        re.I,
    )
    counts: dict[str, int] = {}
    markers: dict[str, set[str]] = {}
    session_laws: dict[str, set[str]] = {}
    for page in sorted((CHAPTER_SOURCES / SECTION_PAGES).glob("*.html")):
        divs = _section_content_divs(BeautifulSoup(page.read_bytes().decode("utf-8"), "lxml"))
        starts, _ = _rendition_starts(divs, section=page.stem)
        counts[page.stem] = len(starts)
        text = " ".join(_clean_text(div) for div in divs)
        if found := set(marker.findall(text)):
            markers[page.stem] = found
        for chapter in re.findall(r"am\. 2026, ch\. (\d+)", text):
            session_laws.setdefault(chapter, set()).add(page.stem)
    assert len(counts) == 162
    assert {section: n for section, n in counts.items() if n != 1} == {
        "63-3022E": 2,
        "63-3025D": 2,
    }
    two_markers = {"[effective until January 1, 2027]", "[effective January 1, 2027]"}
    assert markers == {"63-3022E": two_markers, "63-3025D": two_markers}
    assert sorted(session_laws, key=int) == ["1", "79", "81", "153", "184", "302"]
    assert session_laws["79"] == {"63-3022E", "63-3025D"}
    assert all(
        counts[section] == 1
        for chapter, pages in session_laws.items()
        if chapter != "79"
        for section in pages
    )


def test_no_other_us_id_scope_carries_a_variant_path() -> None:
    carriers: dict[str, list[str]] = {}
    for path in sorted((CORPUS_ROOT / "provisions/us-id").rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            citation_path = json.loads(line)["citation_path"]
            if "--" in citation_path:
                carriers.setdefault(citation_path, []).append(path.stem)
    assert carriers == {variant: [VERSION] for variant in VARIANTS}


# The selectors that carry an Idaho chapter 30 scope and that no other selector
# names as its predecessor (line heads), on origin/main eabe4ed94.
LINE_HEADS = {
    "us-rulespec-2026-09-24-snap-fy2027-cola": SUCCESSOR_VERSION,
    "us-rulespec-2026-09-24-irs-sales-tax-tables-union": SUCCESSOR_VERSION,
    "us-rulespec-2026-10-11-w5-remainder-union": CHAPTER_VERSION,
}


@pytest.mark.parametrize(("cut", "replaced"), sorted(LINE_HEADS.items()))
def test_the_scope_replaces_each_line_heads_chapter_30_scope_cleanly(
    cut: str, replaced: str
) -> None:
    """With the head's chapter 30 carrier replaced by this scope, the head's us-id
    scopes (every document class, other us-id statute scopes included) validate
    with strict warnings and no issue, and every citation path the replaced
    scope carried is still carried. This checks the Idaho slice of the cut, not
    the whole release: no scope of another jurisdiction carries a us-id path."""
    manifest = ReleaseManifest.load(REPO_ROOT / f"manifests/releases/{cut}.json")
    us_id = [scope for scope in manifest.scopes if scope.jurisdiction == "us-id"]
    target = ReleaseScope("us-id", "statute", replaced)
    assert target in us_id
    release = ReleaseManifest(
        name=f"{cut}-us-id-with-concurrent-versions",
        quality_profile="complete-expression-dates-v1",
        scopes=tuple(
            ReleaseScope("us-id", "statute", VERSION) if scope == target else scope
            for scope in us_id
        ),
    )
    report = validate_release(CORPUS_ROOT, release, strict_warnings=True, max_issues=50)
    assert report.to_mapping()["issue_count"] == 0, report.to_mapping()["issues"]
    assert set(_rows(replaced)) <= set(_rows())


def test_every_line_head_carrying_chapter_30_is_listed() -> None:
    """Pins LINE_HEADS: a new selector that carries a chapter 30 carrier and
    succeeds a listed head makes this fail, so the cut list is refreshed."""
    import re

    carriers = {CHAPTER_VERSION, SUCCESSOR_VERSION}
    named: set[str] = set()
    carrying: set[str] = set()
    for path in (REPO_ROOT / "manifests/releases").glob("us-rulespec-*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        match = re.search(r"us-rulespec-[0-9a-z-]+", payload.get("description") or "")
        if match:
            named.add(match.group(0))
        if any(
            scope.get("jurisdiction") == "us-id"
            and scope.get("document_class") == "statute"
            and scope.get("version") in carriers
            for scope in payload.get("scopes", [])
        ):
            carrying.add(path.stem)
    assert carrying - named == set(LINE_HEADS)
