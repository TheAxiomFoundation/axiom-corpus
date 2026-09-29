"""Pin the NYC Administrative Code scope refreshed for chapter 127 of 2026.

Chapter 127 (A.11561 Part D, signed 2026-06-05) moved the NYC resident rate
switch and the 14% additional tax sunset from 2027 to 2030. The earlier scope,
``2026-06-05-nyc-admin-code``, still carries the pre-amendment text; this scope
is its successor for the same three citation paths (axiom-corpus#766).
"""

import difflib
import hashlib
import re
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.nyc_admin_code import extract_nyc_admin_code

CORPUS_ROOT = Path(__file__).resolve().parents[1] / "data" / "corpus"
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
# A.11561 Part D § 7 re-enacts the (b)(1), (b)(2) and (b)(3) tables unchanged
# (bill pages 9-10); each header is followed by these rows.
B_TABLES = (
    (
        "Not over $21,600",
        "1.18% of the city taxable income",
        "Over $21,600 but not over $45,000",
        "$255 plus 1.435% of excess over $21,600",
        "Over $45,000 but not over $90,000",
        "$591 plus 1.455% of excess over $45,000",
        "Over $90,000",
        "$1,245 plus 1.48% of excess over $90,000",
    ),
    (
        "Not over $14,400",
        "1.18% of the city taxable income",
        "Over $14,400 but not over $30,000",
        "$170 plus 1.435% of excess over $14,400",
        "Over $30,000 but not over $60,000",
        "$394 plus 1.455% of excess over $30,000",
        "Over $60,000",
        "$830 plus 1.48% of excess over $60,000",
    ),
    (
        "Not over $12,000",
        "1.18% of the city taxable income",
        "Over $12,000 but not over $25,000",
        "$142 plus 1.435% of excess over $12,000",
        "Over $25,000 but not over $50,000",
        "$328 plus 1.455% of excess over $25,000",
        "Over $50,000",
        "$692 plus 1.48% of excess over $50,000",
    ),
)
# Every word-level change from the 2026-06-05 text, in order. §§ 6-8 of
# A.11561 Part D make all of them except the history notes, which Code
# Library adds; nothing else in either section differs.
EXPECTED_WORD_CHANGES = {
    "11-1701": [
        ("twenty-seven,", "thirty,"),
        ("twenty-six.", "twenty-nine."),
        ("twenty-six,", "twenty-nine,"),
        ("his or her", "such individual's"),
        ("twenty-six:", "twenty-nine:"),
        ("twenty-six:", "twenty-nine:"),
        ("his or her", "such individual's"),
        ("twenty-six:", "twenty-nine:"),
        ("8/23/2023)", f"8/23/2023; {CH127_NOTE})"),
    ],
    "11-1704.1": [
        ("twenty-seven,", "thirty,"),
        ("8/23/2023)", f"8/23/2023; {CH127_NOTE})"),
    ],
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bodies(path: Path) -> dict[str, str]:
    return {record.citation_path: record.body or "" for record in load_provisions(path)}


def _prior_and_current(section: str) -> tuple[str, str]:
    path = f"{SCOPE}/NYC/{section}"
    prior = _bodies(CORPUS_ROOT / f"provisions/{SCOPE}/{PRIOR_VERSION}.jsonl")[path]
    return prior, _bodies(PROVISIONS)[path]


def _word_changes(before: str, after: str) -> list[tuple[str, str]]:
    old, new = before.split(), after.split()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return [
        (" ".join(old[i1:i2]), " ".join(new[j1:j2]))
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]


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
    lines = body.splitlines()
    starts = [index for index, line in enumerate(lines) if line == B_HEADER]
    for start, table in zip(starts, B_TABLES, strict=True):
        assert tuple(lines[start + 3 : start + 11]) == table


def test_section_11_1704_1_additional_tax_runs_to_2030():
    body = _bodies(PROVISIONS)[f"{SCOPE}/NYC/11-1704.1"]
    paragraph = next(line for line in body.splitlines() if line.startswith("(a) (1) "))

    assert (
        "for each taxable year beginning after nineteen hundred ninety but before two thousand"
        " thirty, an additional tax" in paragraph
    )
    assert "twenty-seven" not in paragraph
    assert CH127_NOTE in body


def test_sections_11_1701_and_11_1704_1_change_only_by_chapter_127():
    for section, expected in EXPECTED_WORD_CHANGES.items():
        prior, current = _prior_and_current(section)
        assert _word_changes(prior, current) == expected, section
        assert len(prior.splitlines()) == len(current.splitlines())


def test_section_11_1706_changes_only_in_the_ubt_credit_schedules():
    # Not part of chapter 127. The same capture picks up Local Law 133 of 2026:
    # § 11-1706(c)(2)(A), the unincorporated business tax credit, now has three
    # schedules where the 2026-06-05 text had one open-ended 1997 schedule.
    prior, current = _prior_and_current("11-1706")
    old, new = prior.splitlines(), current.splitlines()
    first = old.index(
        "(i) For taxable years beginning on or after January first, nineteen hundred ninety-seven:"
    )
    limit = next(
        index
        for index, line in enumerate(old)
        if index > first and line.startswith("(B) Notwithstanding anything to the contrary")
    )
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    changed = [(i1, i2) for tag, i1, i2, _j1, _j2 in matcher.get_opcodes() if tag != "equal"]
    history = next(index for index, line in enumerate(old) if line.startswith("(Am. 2015 "))
    assert changed[-1] == (history, history + 1)
    assert all(first <= i1 and i2 <= limit for i1, i2 in changed[:-1])
    assert new[len(new) - len(old) + history] == old[history].removesuffix(")") + (
        "; Am. L.L. 2026/133, 8/18/2026, retro. eff. 1/1/2026)"
    )
    for header in (
        "(i) For taxable years beginning on or after January 1, 1997, and before January 1, 2007:",
        "(ii) For taxable years beginning on or after January 1, 2007, and before January 1, 2026:",
        "(iii) For taxable years beginning on or after January 1, 2026:",
    ):
        assert header in new
    # Published wording, kept as is: (iii)(III) lacks the "or greater" that
    # (ii)(III) and (iii)(V) carry.
    assert (
        "(III) If the city taxable income is $142,000 but less than $1,000,000, the amount of "
        "the credit shall be 23 percent of the amount determined in paragraph 3 of this "
        "subdivision." in new
    )
    assert (
        "(V) If the city taxable income is $1,250,000 or greater, the credit shall be 15 percent "
        "of the amount determined in paragraph 3 of this subdivision." in new
    )


def test_prior_scope_is_the_pre_chapter_127_text():
    prior = _bodies(CORPUS_ROOT / f"provisions/{SCOPE}/{PRIOR_VERSION}.jsonl")
    current = _bodies(PROVISIONS)

    assert prior.keys() == current.keys()
    assert "before two thousand twenty-seven" in prior[f"{SCOPE}/NYC/11-1701"]
    assert "before two thousand twenty-seven" in prior[f"{SCOPE}/NYC/11-1704.1"]
    assert all(CH127_NOTE not in body for body in prior.values())
