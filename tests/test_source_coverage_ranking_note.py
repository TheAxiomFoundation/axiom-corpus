"""The 2026-10-13 source-coverage run note and its ranking CSV agree.

The note quotes figures from the CSV that ``scripts/measure_source_coverage.py`` wrote.
These tests keep the two in step: the CSV has the script's columns and order, and every
scope row in the note's tables, and the note's totals, are the CSV's.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import scripts.measure_source_coverage as script

RUNS = Path(__file__).resolve().parents[1] / "docs" / "ingest-runs"
NOTE = RUNS / "2026-10-13-source-coverage-ranking.md"
CSV = RUNS / "2026-10-13-source-coverage-ranking.csv"

_TABLE_ROW = re.compile(
    r"^\| `(?P<scope>[^`]+)` \| (?P<sources>[\d,]+) \| (?P<median>[\d.]+) \| (?P<p10>[\d.]+) \| "
    r"(?P<under>[\d,]+) \| (?P<body>[\d,]+) \| (?P<selectors>\w+) \|$"
)


def _rows() -> list[dict[str, str]]:
    with CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(text: str) -> int:
    return int(text.replace(",", ""))


def test_the_ranking_csv_has_the_scripts_columns_and_order() -> None:
    rows = _rows()
    assert list(rows[0]) == list(script._CSV_FIELDS)
    assert len(rows) == 711
    assert len({row["scope"] for row in rows}) == len(rows)
    typed = [
        {**row, "needs_review": int(row["needs_review"]), "median": float(row["median"])}
        for row in rows
    ]
    assert [row["scope"] for row in script.rank(typed)] == [row["scope"] for row in rows]
    for row in rows:
        assert 0.0 <= float(row["minimum"]) <= float(row["p10"]) <= 1.0
        assert float(row["minimum"]) <= float(row["median"]) <= 1.0
        assert int(row["needs_review_with_body"]) <= int(row["needs_review"]) <= int(row["sources"])
        assert int(row["needs_review_missing_words"]) <= int(row["missing_words"])
        assert int(row["missing_words"]) <= int(row["region_words"])


def test_every_scope_row_in_the_note_is_the_csvs() -> None:
    by_scope = {row["scope"]: row for row in _rows()}
    quoted = [match for line in NOTE.read_text().splitlines() if (match := _TABLE_ROW.match(line))]
    assert len(quoted) == 20 + 20
    for match in quoted:
        row = by_scope[match["scope"]]
        assert _number(match["sources"]) == int(row["sources"]), match["scope"]
        assert match["median"] == f"{float(row['median']):.2f}", match["scope"]
        assert match["p10"] == f"{float(row['p10']):.2f}", match["scope"]
        assert _number(match["under"]) == int(row["needs_review"]), match["scope"]
        assert _number(match["body"]) == int(row["needs_review_with_body"]), match["scope"]
        expected = (
            "withdrawn"
            if row["withdrawn"] == "True"
            else (row["selectors"] if int(row["selectors"]) else "none")
        )
        assert match["selectors"] == expected, match["scope"]


def test_the_notes_totals_are_the_csvs() -> None:
    rows = _rows()
    note = NOTE.read_text()

    assert sum(int(row["sources"]) for row in rows) == 33_525
    assert "33,525 pages in all" in note
    assert sum(int(row["needs_review"]) for row in rows) == 23 + 255 + 3_411
    assert round(sum(int(row["region_words"]) for row in rows) / 1e6, 1) == 43.0
    assert round(sum(int(row["missing_words"]) for row in rows) / 1e6, 2) == 7.75
    assert "43.0 million" in note and "7.75 million" in note

    manifest_only = [row for row in rows if "whole_page" not in row["region"]]
    whole_only = [row for row in rows if row["region"] == "whole_page"]
    assert len(manifest_only) == 495 and len(whole_only) == 213
    assert sum(1 for row in manifest_only if row["needs_review"] == "0") == 374
    assert sum(1 for row in whole_only if row["needs_review"] == "0") == 113
    assert "Of the 495 scopes read only through manifests, 374 have no page under the bar" in note
    assert "Of the 213 scopes read only as whole pages, 113 have no page under the bar" in note

    cms = [
        row
        for row in manifest_only
        if "state-plan" in row["scope"]
        and "2026-09-13" in row["scope"]
        and row["needs_review"] != "0"
    ]
    assert (
        len(cms),
        sum(int(row["sources"]) for row in cms),
        sum(int(row["needs_review"]) for row in cms),
    ) == (
        101,
        239,
        231,
    )
    assert (
        "| The 2026-09-13 CMS state-plan scopes (101 with a page under the bar) | 239 | | | 231 | 231 | |"
        in note
    )
    maine = next(row for row in rows if row["scope"].endswith("us-me-title-36"))
    assert (maine["region_words"], maine["missing_words"]) == ("579623", "372653")
    assert "372,653 of 579,623 region words are missing" in note
