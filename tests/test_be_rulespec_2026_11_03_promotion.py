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
    ARTICLE_HEADING,
    CIR_INPUT_NAME,
    CIR_PARENT,
    FULL_VERSION,
    NEW_VERSION,
    OLD_VERSION,
    REQUESTED_PAGES,
    SECTION_LABEL,
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
# Every span end the section-label rule decides around the added pages: each pair of
# consecutive headings on different pages, where the pages from the first heading to the next
# take in an added page. A row gives the article and its heading's page, the next heading and
# its page, and the text above that heading when the rule reads it as labels and nothing else,
# so the article ends on the page before. None marks article text above it; the article then
# ends on that page, which can only add pages.
LABEL_DECIDED_ENDS = [
    ("24", 73, "25", 75, None),
    ("25/1", 75, "26", 76, None),
    ("26", 76, "27", 77, "C. - Profits "),
    ("27", 77, "27/1", 78, ""),
    ("28", 78, "29", 79, None),
    ("29", 79, "30", 80, None),
    ("31", 80, "31bis", 81, None),
    ("31bis", 81, "32", 82, None),
    ("32", 82, "32/1", 83, ""),
    ("32/2", 87, "33", 91, ""),
    ("34", 91, "35", 94, None),
    ("36", 94, "37", 96, None),
    ("37", 96, "37bis", 97, None),
    ("37bis", 97, "38", 98, None),
    ("38", 98, "38/1", 106, None),
    ("38/1", 106, "39", 108, None),
    ("39", 108, "40", 110, ""),
    ("74", 154, "75", 155, ""),
    ("75", 155, "76", 156, None),
    ("77", 156, "78", 157, None),
    ("78", 157, "79", 159, None),
    ("80", 159, "81 à 85", 160, None),
    ("102bis", 174, "103", 175, "Sous-section 3. - Pertes déductibles "),
    ("104", 175, "105", 176, ""),
    ("107 à 111", 176, "112", 177, "C. - (...) "),
    ("143", 190, "144", 191, None),
    ("145", 191, "145^1", 192, None),
    ("171", 268, "171/1", 275, None),
]
# Articles a scope holds in part, as (article, first page, last page). The 08-23 scope holds 37.
# This promotion finishes the seven with text on an added page; the other 30 sit on pages the
# 07-10 and 08-23 promotions added.
FINISHED_HERE = [
    ("24", 73, 75), ("36", 94, 96), ("37", 96, 97), ("80", 159, 160), ("143", 190, 191),
    ("145", 191, 192), ("171", 268, 275),
]  # fmt: skip
STILL_IN_PART = [
    ("2", 33, 49), ("5/2", 52, 53), ("7", 53, 54), ("18", 61, 64), ("21", 68, 72),
    ("52", 122, 124), ("90", 162, 165), ("117 à 125", 177, 178), ("145^3", 193, 195),
    ("145^6", 198, 199), ("145^8", 200, 201), ("145^30", 224, 225), ("145^32", 225, 227),
    ("145^33", 227, 230), ("145^34", 230, 231), ("145^35", 231, 233), ("145^48", 248, 249),
    ("145^50", 250, 252), ("154bis", 258, 259), ("253", 445, 446), ("267", 460, 461),
    ("269", 461, 464), ("289quater", 515, 516), ("292", 518, 519), ("304", 525, 526),
    ("304/1", 526, 527), ("464", 685, 686), ("470/1", 688, 689), ("517", 720, 721),
    ("519ter", 721, 722),
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


def _cir_bodies() -> dict[int, str]:
    full = _rows_by_citation(FULL_PROVISIONS_PATH)
    return {
        int(citation[len(PAGE_PREFIX) :]): str(row.get("body") or "")
        for citation, row in full.items()
        if citation.startswith(PAGE_PREFIX)
    }


def _held_in_part(spans: list[tuple[str, int, int]], pages: set[int]) -> list[tuple[str, int, int]]:
    return [
        (label, first, last)
        for label, first, last in spans
        if pages & set(range(first, last + 1)) and not set(range(first, last + 1)) <= pages
    ]


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
    bodies = _cir_bodies()
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


def test_section_label_rule_reads_these_texts_where_it_ends_an_article() -> None:
    bodies = _cir_bodies()
    headings = [
        (page, match.start(), match.group("label"))
        for page in sorted(bodies)
        for match in ARTICLE_HEADING.finditer(bodies[page])
    ]
    decided = []
    for (page, _, label), (next_page, offset, next_label) in zip(
        headings[:-1], headings[1:], strict=True
    ):
        if next_page > page and EXPECTED_PAGES & set(range(page, next_page + 1)):
            above = bodies[next_page][:offset]
            labels = above if SECTION_LABEL.fullmatch(above) else None
            decided.append((label, page, next_label, next_page, labels))

    assert decided == LABEL_DECIDED_ENDS


def test_scope_holds_in_part_only_articles_the_earlier_scopes_held_in_part() -> None:
    spans = article_spans(_cir_bodies())
    old = _held_in_part(spans, _cir_pages(_rows_by_citation(OLD_PROVISIONS_PATH)))
    new = _held_in_part(spans, _cir_pages(_rows_by_citation(NEW_PROVISIONS_PATH)))

    assert new == STILL_IN_PART
    assert [span for span in old if span not in new] == FINISHED_HERE
    assert set(new) <= set(old)
    assert not [span for span in new if EXPECTED_PAGES & set(range(span[1], span[2] + 1))]


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
        assert moved["source_path"] == f"sources/be/statute/{NEW_VERSION}/inputs/{CIR_INPUT_NAME}"
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


@pytest.mark.parametrize(
    ("text", "labels_only"),
    [
        pytest.param("", True, id="nothing"),
        pytest.param("(...) ", True, id="ellipsis"),
        pytest.param("C. - Profits ", True, id="letter"),
        pytest.param("C. - (...) ", True, id="repealed-title"),
        pytest.param("Sous-section 3. - Pertes déductibles ", True, id="sous-section"),
        pytest.param("CHAPITRE 4. - Calcul de l'impôt ", True, id="chapitre"),
        pytest.param(
            "Sous-section 2vicies semel. - Réduction pour primes ", True, id="latin-ordinal"
        ),
        pytest.param("1°bis. - Stage en entreprise ", True, id="numbered"),
        pytest.param(
            "Section 4/1.- Détermination de l'impôt étranger ....... 510 ",
            True,
            id="table-of-contents",
        ),
        pytest.param(
            "Section 4. - Revenu professionnel Sous-section 1. - Revenus imposables "
            "A. - Généralités ",
            True,
            id="three-labels",
        ),
        pytest.param("(...) Section 2. - (...) ", True, id="ellipsis-then-label"),
        pytest.param("C. - Profits\nSous-section 3. - Pertes\n", True, id="label-lines"),
        pytest.param(
            "B. - Revenus Le contribuable déclare ses revenus. Il paie l'impôt. ",
            False,
            id="label-then-sentences",
        ),
        pytest.param(
            "Sous-section 3. - Pertes déductibles\nLes pertes sont déduites. ",
            False,
            id="label-line-then-sentence",
        ),
        pytest.param(
            "L'article 24. - tel que modifié, s'applique aux revenus. ",
            False,
            id="article-text-after-an-apostrophe",
        ),
        pytest.param("L'article 24. - tel que modifié ", False, id="letter-marker-runs-on"),
        pytest.param("2°bis. - les rémunérations. ", False, id="enumerated-sentence"),
        pytest.param("C. - Profits; et ", False, id="semicolon"),
        pytest.param("C. - Profits: ", False, id="colon"),
        pytest.param("texte de l'article. C. - Profits ", False, id="text-then-label"),
    ],
)
def test_section_label_matches_labels_and_nothing_else(text: str, labels_only: bool) -> None:
    assert bool(SECTION_LABEL.fullmatch(text)) is labels_only


def _heading(label: str) -> str:
    return f"Article {label}, CIR 92 (revenus 2025)"


@pytest.mark.parametrize(
    ("bodies", "spans"),
    [
        pytest.param(
            {1: f"{_heading('1')} Texte.", 2: f"C. - Profits {_heading('2')} Texte."},
            [("1", 1, 1), ("2", 2, 2)],
            id="label-above-the-next-heading",
        ),
        pytest.param(
            {1: f"{_heading('1')} Texte", 2: f"suite du texte. {_heading('2')} Texte."},
            [("1", 1, 2), ("2", 2, 2)],
            id="article-text-above-the-next-heading",
        ),
        pytest.param(
            {
                1: f"{_heading('1')} Texte.",
                2: f"B. - Revenus Le texte continue. Encore. {_heading('2')} Texte.",
                3: "Suite.",
            },
            [("1", 1, 2), ("2", 2, 3)],
            id="label-then-article-text",
        ),
        pytest.param(
            {
                1: f"{_heading('1')} Texte.",
                2: f"L'article 24. - tel que modifié, s'applique. {_heading('2')} Texte.",
            },
            [("1", 1, 2), ("2", 2, 2)],
            id="article-text-after-an-apostrophe",
        ),
        pytest.param(
            {1: f"{_heading('1')} Texte:", 2: f"2°bis. - les rémunérations. {_heading('2')} X."},
            [("1", 1, 2), ("2", 2, 2)],
            id="enumerated-sentence",
        ),
        pytest.param(
            {1: f"{_heading('1')} Texte. {_heading('2')} Texte.", 2: "Suite."},
            [("1", 1, 1), ("2", 1, 2)],
            id="two-headings-on-one-page",
        ),
        pytest.param(
            {1: "Articles 107 à 111, CIR 92 (revenus 2025) Texte.", 2: f"{_heading('112')} X."},
            [("107 à 111", 1, 1), ("112", 2, 2)],
            id="plural-heading",
        ),
        pytest.param(
            {1: f"{_heading('1')} Texte.", 2: "Suite.", 3: "Suite."},
            [("1", 1, 3)],
            id="last-heading-runs-to-the-last-page",
        ),
        pytest.param(
            {1: f"{_heading('1')} Texte visé à l'article 24, CIR 92 (revenus 2025).", 2: "S."},
            [("1", 1, 2)],
            id="cross-reference",
        ),
        pytest.param(
            {
                1: f"{_heading('1')} Texte.",
                2: "Article 2, CIR 92\n(revenus 2025) Texte.",
                3: f"{_heading('3')} Texte.",
            },
            [("1", 1, 2), ("3", 3, 3)],
            id="split-heading-lengthens-the-article-before-it",
        ),
        pytest.param(
            {
                1: f"{_heading('1')} .......... 4",
                2: f"Section 2. - Base de l'impôt .......... 5 {_heading('2')} .......... 5",
                3: "Avant-propos.",
                4: f"TITRE 1. - Dispositions générales {_heading('1')} Texte.",
                5: f"Section 2. - Base de l'impôt {_heading('2')} Texte.",
            },
            [("1", 1, 1), ("2", 2, 3), ("1", 4, 4), ("2", 5, 5)],
            id="table-of-contents",
        ),
    ],
)
def test_article_spans(bodies: dict[int, str], spans: list[tuple[str, int, int]]) -> None:
    assert article_spans(bodies) == spans


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
