"""Pin the NYC Administrative Code scope refreshed for chapter 127 of 2026.

Chapter 127 (A.11561 Part D, signed 2026-06-05) moved the NYC resident rate
switch and the 14% additional tax sunset from 2027 to 2030. The earlier scope,
``2026-06-05-nyc-admin-code``, still carries the pre-amendment text; this scope
is its successor for the same three citation paths (axiom-corpus#766).
"""

import hashlib
import re
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.nyc_admin_code import extract_nyc_admin_code

CORPUS_ROOT = Path("data/corpus")
VERSION = "2026-09-28-nyc-admin-code"
PRIOR_VERSION = "2026-06-05-nyc-admin-code"
SCOPE = "us-ny/statute"
SECTIONS = ("11-1701", "11-1704.1", "11-1706")
PROVISIONS = CORPUS_ROOT / f"provisions/{SCOPE}/{VERSION}.jsonl"
INVENTORY = CORPUS_ROOT / f"inventory/{SCOPE}/{VERSION}.json"
COVERAGE = CORPUS_ROOT / f"coverage/{SCOPE}/{VERSION}.json"
SOURCE_DIR = CORPUS_ROOT / f"sources/{SCOPE}/{VERSION}"
CH127_NOTE = "Am. 2026 N.Y. Laws Ch. 127, 6/5/2026, eff. 6/5/2026"
B_HEADER = "For taxable years beginning after two thousand twenty-nine:"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bodies(path: Path) -> dict[str, str]:
    return {record.citation_path: record.body or "" for record in load_provisions(path)}


def test_scope_reproduces_from_retained_codelibrary_html(tmp_path):
    report = extract_nyc_admin_code(
        CorpusArtifactStore(tmp_path),
        version=VERSION.removesuffix("-nyc-admin-code"),
        sections=SECTIONS,
        source_dir=SOURCE_DIR,
        source_as_of="2026-09-28",
        expression_date="2026-09-28",
    )

    assert report.coverage.complete
    assert report.errors == ()
    for rebuilt, committed in (
        (report.provisions_path, PROVISIONS),
        (report.inventory_path, INVENTORY),
        (report.coverage_path, COVERAGE),
    ):
        assert _digest(rebuilt) == _digest(committed), committed


def test_inventory_hashes_match_retained_sources():
    items = load_source_inventory(INVENTORY)
    assert [item.citation_path for item in items] == [f"{SCOPE}/NYC/{s}" for s in SECTIONS]
    for item in items:
        assert item.source_path.startswith(f"sources/{SCOPE}/{VERSION}/")
        assert _digest(CORPUS_ROOT / item.source_path) == item.sha256


def test_rows_are_parentless_sections():
    records = load_provisions(PROVISIONS)
    assert [record.citation_path for record in records] == [f"{SCOPE}/NYC/{s}" for s in SECTIONS]
    assert all(record.version == VERSION for record in records)
    assert all(record.kind == "section" and record.level == 1 for record in records)
    assert all(record.parent_citation_path is None for record in records)
    assert all(record.source_as_of == record.expression_date == "2026-09-28" for record in records)


def test_section_11_1701_carries_chapter_127_years():
    body = _bodies(PROVISIONS)[f"{SCOPE}/NYC/11-1701"]
    opening = next(line for line in body.splitlines() if line.startswith("A tax is hereby imposed"))

    assert (
        "subdivision (a) of this section for taxable years beginning before two thousand thirty,"
        in opening
    )
    assert (
        "subdivision (b) of this section for taxable years beginning after two thousand"
        " twenty-nine." in opening
    )
    assert (
        "Provided, however, that if, for any taxable year beginning after two thousand twenty-nine,"
        in opening
    )
    assert not re.search(r"two thousand twenty-(six|seven)\b", opening)
    # One header precedes each of the (b)(1), (b)(2) and (b)(3) rate tables.
    assert body.splitlines().count(B_HEADER) == 3
    assert "after two thousand twenty-six:" not in body
    # Part D section 7 also replaced "his or her spouse" in (b)(1) and (b)(3).
    assert body.count("jointly with such individual's spouse") == 2
    assert CH127_NOTE in body


def test_section_11_1704_1_additional_tax_runs_to_2030():
    body = _bodies(PROVISIONS)[f"{SCOPE}/NYC/11-1704.1"]
    paragraph = next(line for line in body.splitlines() if line.startswith("(a) (1) "))

    assert (
        "for each taxable year beginning after nineteen hundred ninety but before two thousand"
        " thirty, an additional tax" in paragraph
    )
    assert "twenty-seven" not in paragraph
    assert CH127_NOTE in body


def test_section_11_1706_carries_local_law_2026_133():
    # Not part of chapter 127: the same capture picks up Local Law 133 of 2026,
    # which splits the § 11-1706(c)(2)(A) unincorporated business tax credit
    # schedule at 2026 and phases it from 23 to 15 percent above $1,000,000.
    body = _bodies(PROVISIONS)[f"{SCOPE}/NYC/11-1706"]

    assert "Am. L.L. 2026/133, 8/18/2026, retro. eff. 1/1/2026" in body
    assert "(iii) For taxable years beginning on or after January 1, 2026:" in body
    assert (
        "If the city taxable income is $1,250,000 or greater, the credit shall be 15 percent"
        in body
    )


def test_prior_scope_is_the_pre_chapter_127_text():
    prior = _bodies(CORPUS_ROOT / f"provisions/{SCOPE}/{PRIOR_VERSION}.jsonl")
    current = _bodies(PROVISIONS)

    assert prior.keys() == current.keys()
    assert "before two thousand twenty-seven" in prior[f"{SCOPE}/NYC/11-1701"]
    assert "before two thousand twenty-seven" in prior[f"{SCOPE}/NYC/11-1704.1"]
    assert all(CH127_NOTE not in body for body in prior.values())
