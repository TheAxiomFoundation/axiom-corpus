"""Regression checks for the 2026-11-03 Belgian statute promotion and be-rulespec-2026-11-03."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.be_rulespec_2026_11_03_promotion import (
    ADDED_PAGES,
    CIR_INPUT_NAME,
    CIR_PARENT,
    FULL_VERSION,
    NEW_VERSION,
    OLD_VERSION,
    REQUESTED_PAGES,
    article_closure,
    article_spans,
    build_promotion,
    build_release,
    promote_rows,
    row_line,
    select_input_lines,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/corpus"
RELEASE_DIR = ROOT / "manifests/releases"
BASE_RELEASE_PATH = RELEASE_DIR / "be-rulespec-2026-08-29.json"
RELEASE_PATH = RELEASE_DIR / "be-rulespec-2026-11-03.json"
INGEST_MANIFEST_PATH = ROOT / ".axiom/ingest-manifests/be/statute" / f"{NEW_VERSION}.json"
LOCK_PATH = ROOT / ".axiom/corpus-locks/be/statute" / f"{NEW_VERSION}.json"
OLD_PROVISIONS_PATH = BASE / "provisions/be/statute" / f"{OLD_VERSION}.jsonl"
NEW_PROVISIONS_PATH = BASE / "provisions/be/statute" / f"{NEW_VERSION}.jsonl"
FULL_PROVISIONS_PATH = BASE / "provisions/be/statute" / f"{FULL_VERSION}.jsonl"
OLD_INPUTS = BASE / "sources/be/statute" / OLD_VERSION / "inputs"
NEW_INPUTS = BASE / "sources/be/statute" / NEW_VERSION / "inputs"
PAGE_PREFIX = f"{CIR_PARENT}/page-"

# Written out, not taken from the reproducer, so a wrong page there fails here.
EXPECTED_REQUESTED = frozenset(
    {75, 77, 80, 91, 92, 93, 94, 98, 157, 158, 159, 175, 176, 191, 273, 274}
)
EXPECTED_PAGES = EXPECTED_REQUESTED | frozenset(
    {74, 76, 78, 79, 81, 82, 97, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 155, 156}
)
EXPECTED_CITATIONS = frozenset(f"{PAGE_PREFIX}{page}" for page in EXPECTED_PAGES)
# The articles the release description names: 24 to 39 except 32/1 and 32/2, 75 to 80,
# 103 to 111, 143 to 145 and 171.
EXPECTED_ARTICLES = [
    "24", "25", "25/1", "26", "27", "27/1", "28", "29", "30", "31", "31bis", "32",
    "33", "33bis", "34", "35", "36", "37", "37bis", "38", "38/1", "39",
    "75", "76", "77", "78", "79", "80",
    "103", "104", "105", "106", "107 à 111",
    "143", "144", "145",
    "171",
]  # fmt: skip


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def _rows_by_citation(path: Path) -> dict[str, dict[str, object]]:
    rows = _load_jsonl(path)
    result = {str(row["citation_path"]): row for row in rows}
    assert len(result) == len(rows)
    return result


def _raw_rows_by_citation(path: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for line in path.read_bytes().splitlines():
        citation = str(json.loads(line)["citation_path"])
        assert citation not in result
        result[citation] = line
    return result


def _cir_pages(rows: dict[str, dict[str, object]]) -> set[int]:
    return {
        int(citation[len(PAGE_PREFIX) :]) for citation in rows if citation.startswith(PAGE_PREFIX)
    }


def _scope_files(base: Path, version: str) -> set[str]:
    files = {
        f"provisions/be/statute/{version}.jsonl",
        f"inventory/be/statute/{version}.json",
        f"coverage/be/statute/{version}.json",
    }
    inputs = base / "sources/be/statute" / version / "inputs"
    files.update(path.relative_to(base).as_posix() for path in inputs.iterdir())
    return files


def test_reproducer_rebuilds_the_committed_scope(tmp_path: Path) -> None:
    written = build_promotion(base=BASE, output_base=tmp_path)
    rebuilt = {path.relative_to(tmp_path).as_posix() for path in written}

    assert rebuilt == _scope_files(BASE, NEW_VERSION)
    assert len(rebuilt) == 14
    for name in rebuilt:
        assert (tmp_path / name).read_bytes() == (BASE / name).read_bytes(), name


def test_reproducer_rebuilds_the_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == RELEASE_PATH.read_bytes()


def test_selector_moves_only_the_statute_scope() -> None:
    old = ReleaseManifest.load(BASE_RELEASE_PATH)
    new = ReleaseManifest.load(RELEASE_PATH)
    old_scopes = {(scope.jurisdiction, scope.document_class): scope.version for scope in old.scopes}
    new_scopes = {(scope.jurisdiction, scope.document_class): scope.version for scope in new.scopes}

    assert new.name == "be-rulespec-2026-11-03"
    assert new.quality_profile == old.quality_profile == "complete-expression-dates-v1"
    assert len(old_scopes) == len(new_scopes) == 13
    assert old_scopes[("be", "statute")] == OLD_VERSION
    assert new_scopes == {**old_scopes, ("be", "statute"): NEW_VERSION}
    assert [scope.version for scope in new.scopes] == [
        NEW_VERSION if scope.version == OLD_VERSION else scope.version for scope in old.scopes
    ]


def test_added_pages_finish_every_article_on_them() -> None:
    full = _rows_by_citation(FULL_PROVISIONS_PATH)
    bodies = {
        int(citation[len(PAGE_PREFIX) :]): str(row.get("body") or "")
        for citation, row in full.items()
        if citation.startswith(PAGE_PREFIX)
    }
    present = _cir_pages(_rows_by_citation(OLD_PROVISIONS_PATH))
    carried = present | EXPECTED_PAGES
    touched = [
        (label, first, last)
        for label, first, last in article_spans(bodies)
        if EXPECTED_PAGES & set(range(first, last + 1))
    ]

    assert REQUESTED_PAGES == EXPECTED_REQUESTED
    assert ADDED_PAGES == EXPECTED_PAGES
    assert not EXPECTED_PAGES & present
    assert article_closure(bodies, EXPECTED_REQUESTED, present) == EXPECTED_PAGES
    assert [label for label, _, _ in touched] == EXPECTED_ARTICLES
    assert all(set(range(first, last + 1)) <= carried for _, first, last in touched)


def test_new_scope_keeps_old_rows_and_adds_the_pages() -> None:
    old = _rows_by_citation(OLD_PROVISIONS_PATH)
    new = _rows_by_citation(NEW_PROVISIONS_PATH)
    full = _rows_by_citation(FULL_PROVISIONS_PATH)

    assert len(old) == 184
    assert len(new) == 220
    assert new.keys() - old.keys() == EXPECTED_CITATIONS
    assert old.keys() <= new.keys()
    assert list(new) == sorted(new)

    for citation, old_row in old.items():
        expected = dict(old_row)
        expected["version"] = NEW_VERSION
        expected["source_path"] = str(expected["source_path"]).replace(
            f"sources/be/statute/{OLD_VERSION}/inputs/",
            f"sources/be/statute/{NEW_VERSION}/inputs/",
            1,
        )
        assert new[citation] == expected

    for citation in EXPECTED_CITATIONS:
        expected = dict(full[citation])
        expected["version"] = NEW_VERSION
        expected["expression_date"] = "2026-06-30"
        expected["source_path"] = f"sources/be/statute/{NEW_VERSION}/inputs/{CIR_INPUT_NAME}"
        assert new[citation] == expected
        assert new[citation]["parent_citation_path"] == CIR_PARENT
        assert str(new[citation]["parent_id"]) == str(new[CIR_PARENT]["id"])

    assert NEW_PROVISIONS_PATH.read_bytes() == b"".join(
        row_line(row).encode() + b"\n" for row in new.values()
    )


def test_cir_input_is_the_full_exports_lines_for_old_and_added_pages() -> None:
    old_cir = _raw_rows_by_citation(OLD_INPUTS / CIR_INPUT_NAME)
    new_cir = _raw_rows_by_citation(NEW_INPUTS / CIR_INPUT_NAME)
    full_cir = _raw_rows_by_citation(FULL_PROVISIONS_PATH)
    selected = old_cir.keys() | EXPECTED_CITATIONS
    expected_lines = [
        line
        for line in FULL_PROVISIONS_PATH.read_bytes().splitlines()
        if str(json.loads(line)["citation_path"]) in selected
    ]

    assert len(old_cir) == 52
    assert len(new_cir) == 88
    assert new_cir.keys() == selected
    assert (NEW_INPUTS / CIR_INPUT_NAME).read_bytes().splitlines() == expected_lines
    assert all(new_cir[citation] == line for citation, line in old_cir.items())
    assert all(new_cir[citation] == full_cir[citation] for citation in EXPECTED_CITATIONS)

    old_other = {path.name: path for path in OLD_INPUTS.iterdir() if path.name != CIR_INPUT_NAME}
    new_other = {path.name: path for path in NEW_INPUTS.iterdir() if path.name != CIR_INPUT_NAME}
    assert old_other.keys() == new_other.keys()
    assert len(old_other) == 10
    for name, old_path in old_other.items():
        assert new_other[name].read_bytes() == old_path.read_bytes()


def test_selector_passes_strict_release_validation() -> None:
    report = validate_release(
        BASE, ReleaseManifest.load(RELEASE_PATH), strict_warnings=True, max_issues=500
    )

    assert report.to_mapping() == {
        "release": "be-rulespec-2026-11-03",
        "scope_count": 13,
        "ok": True,
        "error_count": 0,
        "warning_count": 0,
        "strict_warnings": True,
        "issue_count": 0,
        "issues_returned": 0,
        "issues_truncated": False,
        "issues": [],
    }


def test_new_scope_is_locked_and_not_withdrawn() -> None:
    assert LOCK_PATH.is_file()
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    keys = [
        (scope.jurisdiction, scope.document_class, scope.version)
        for scope in ReleaseManifest.load(RELEASE_PATH).scopes
    ]
    assert not [key for key in keys if key in withdrawn]


def test_ingest_manifest_covers_every_artifact() -> None:
    manifest = json.loads(INGEST_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = {
        (BASE / name).relative_to(ROOT).as_posix() for name in _scope_files(BASE, NEW_VERSION)
    }
    applied = {item["path"]: item["sha256"] for item in manifest["applied_files"]}

    assert manifest["coverage"] == {
        "complete": True,
        "extra_count": 0,
        "matched_count": 220,
        "missing_count": 0,
        "provision_count": 220,
        "source_count": 220,
    }
    assert applied.keys() == expected
    assert all(
        hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
        for path, digest in applied.items()
    )


# Synthetic scopes for the properties below: a parent row and pages 1..PAGES of one export.
PAGES = 12
_PARENT_ID = "parent-uuid"


def _full_row(page: int) -> dict[str, object]:
    return {
        "citation_path": f"{PAGE_PREFIX}{page}",
        "body": f"page {page}",
        "expression_date": "2025-01-01",
        "id": f"id-{page}",
        "parent_citation_path": CIR_PARENT,
        "parent_id": _PARENT_ID,
        "source_path": f"sources/be/statute/{FULL_VERSION}/inputs/full.jsonl",
        "version": FULL_VERSION,
    }


def _old_row(citation: str, page: int | None) -> dict[str, object]:
    row = _full_row(page) if page is not None else {"citation_path": citation, "id": _PARENT_ID}
    row = {**row, "version": OLD_VERSION}
    row["source_path"] = f"sources/be/statute/{OLD_VERSION}/inputs/{CIR_INPUT_NAME}"
    return row


_pages = st.sets(st.integers(min_value=1, max_value=PAGES))


@settings(max_examples=200, deadline=None)
@given(old_pages=_pages, added=_pages)
def test_promote_rows_moves_old_rows_and_adds_each_page_once(
    old_pages: set[int], added: set[int]
) -> None:
    """For any old page set and any added set: the old rows change only in version and
    source_path, each added page arrives as the export's row, and the output is sorted;
    an added page the old scope already holds is refused."""
    full = {f"{PAGE_PREFIX}{page}": _full_row(page) for page in range(1, PAGES + 1)}
    old = [_old_row(CIR_PARENT, None), *(_old_row("", page) for page in sorted(old_pages))]
    if old_pages & added:
        with pytest.raises(ValueError):
            promote_rows(old, full, added)
        return
    rows = promote_rows(old, full, added)
    by_citation = {str(row["citation_path"]): row for row in rows}
    citations = [str(row["citation_path"]) for row in rows]

    assert citations == sorted(citations)
    assert set(citations) == {CIR_PARENT} | {f"{PAGE_PREFIX}{page}" for page in old_pages | added}
    for row in old:
        moved = by_citation[str(row["citation_path"])]
        assert {key for key in row if row[key] != moved[key]} <= {"version", "source_path"}
        assert moved["version"] == NEW_VERSION
    for page in added:
        row = by_citation[f"{PAGE_PREFIX}{page}"]
        assert row == {
            **full[f"{PAGE_PREFIX}{page}"],
            "expression_date": "2026-06-30",
            "source_path": f"sources/be/statute/{NEW_VERSION}/inputs/{CIR_INPUT_NAME}",
            "version": NEW_VERSION,
        }


@settings(max_examples=200, deadline=None)
@given(
    order=st.permutations(list(range(1, PAGES + 1))),
    old_pages=_pages,
    added=_pages,
    tamper=st.booleans(),
)
def test_select_input_lines_keeps_the_exports_order(
    order: list[int], old_pages: set[int], added: set[int], tamper: bool
) -> None:
    """The output is the export's lines for old and added pages, in the export's order; an
    old line that differs from the export's, or an overlap, is refused."""
    full_lines = [row_line(_full_row(page)).encode() for page in order]
    by_page = dict(zip(order, full_lines, strict=True))
    old_lines = [by_page[page] for page in sorted(old_pages)]
    if tamper and old_lines:
        old_lines[0] = old_lines[0].replace(b"page ", b"PAGE ")
        with pytest.raises(ValueError):
            select_input_lines(full_lines, old_lines, added)
        return
    if old_pages & added:
        with pytest.raises(ValueError):
            select_input_lines(full_lines, old_lines, added)
        return
    selected = select_input_lines(full_lines, old_lines, added)
    assert selected == [by_page[page] for page in order if page in old_pages | added]


def _body(labels: list[str], lead: bool) -> str:
    text = "texte suivi. " if lead else ""
    return text + " ".join(f"Article {label}, CIR 92 (revenus 2025) Texte." for label in labels)


@settings(max_examples=200, deadline=None)
@given(
    headings=st.lists(st.integers(min_value=0, max_value=2), min_size=PAGES, max_size=PAGES),
    leads=st.lists(st.booleans(), min_size=PAGES, max_size=PAGES),
    requested=_pages,
    present=_pages,
)
def test_article_closure_is_closed_and_idempotent(
    headings: list[int], leads: list[bool], requested: set[int], present: set[int]
) -> None:
    """Every article with text on a closure page has its other pages in the closure or
    already present; the closure holds the requested pages that are not present, holds no
    present page, and a second pass adds nothing."""
    bodies, number = {}, 1
    for page, (count, lead) in enumerate(zip(headings, leads, strict=True), start=1):
        bodies[page] = _body([str(number + index) for index in range(count)], lead)
        number += count
    closure = article_closure(bodies, requested, present)

    assert requested - present <= closure
    assert not closure & present
    for _, first, last in article_spans(bodies):
        span = set(range(first, last + 1))
        if span & closure:
            assert span <= closure | present
    assert article_closure(bodies, closure, present) == closure
